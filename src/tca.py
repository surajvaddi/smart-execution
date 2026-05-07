"""Transaction cost analysis and synthetic cost model utilities.

Yahoo Finance does not provide real bid/ask quotes. Phase 6 therefore starts
with deterministic synthetic quotes derived from close price and the OHLCV-based
`spread_proxy` feature. This is a modeling approximation, not quoted market data.
"""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder


DEFAULT_TEMPORARY_IMPACT_ETA = 0.10
DEFAULT_TEMPORARY_IMPACT_BETA = 0.5
DEFAULT_PERMANENT_IMPACT_GAMMA = 0.02
VALID_TCA_SIDES = {"buy", "sell"}


def synthetic_bid_ask_from_row(row: pd.Series) -> tuple[float, float, float]:
    """Return synthetic mid, bid, and ask prices for one market-data row."""
    missing = [col for col in ["close", "spread_proxy"] if col not in row.index]
    if missing:
        raise ValueError(f"Missing required synthetic quote columns: {missing}")

    mid_price = float(row["close"])
    spread_proxy = float(row["spread_proxy"])
    if mid_price <= 0:
        raise ValueError("close must be positive to synthesize bid/ask prices.")
    if spread_proxy < 0:
        raise ValueError("spread_proxy must be non-negative.")

    # The proxy spread is centered around close. With spread_proxy defined as
    # (high - low) / close, `spread_proxy * mid_price` approximates the bar range.
    half_spread = 0.5 * spread_proxy * mid_price
    synthetic_bid = mid_price - half_spread
    synthetic_ask = mid_price + half_spread
    return mid_price, synthetic_bid, synthetic_ask


def add_synthetic_bid_ask(market_data: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic synthetic mid, bid, and ask columns to market data."""
    required = ["close", "spread_proxy"]
    missing = [col for col in required if col not in market_data.columns]
    if missing:
        raise ValueError(f"Missing required synthetic quote columns: {missing}")

    if (market_data["close"] <= 0).any():
        raise ValueError("close must be positive to synthesize bid/ask prices.")
    if (market_data["spread_proxy"] < 0).any():
        raise ValueError("spread_proxy must be non-negative.")

    out = market_data.copy()
    out["mid_price"] = out["close"]
    out["half_spread"] = 0.5 * out["spread_proxy"] * out["mid_price"]
    out["synthetic_bid"] = out["mid_price"] - out["half_spread"]
    out["synthetic_ask"] = out["mid_price"] + out["half_spread"]
    return out


def temporary_market_impact(
    mid_price: float,
    child_quantity: float,
    market_volume: float,
    eta: float = DEFAULT_TEMPORARY_IMPACT_ETA,
    beta: float = DEFAULT_TEMPORARY_IMPACT_BETA,
) -> float:
    """Estimate temporary impact for one child order."""
    _validate_impact_inputs(mid_price, child_quantity, market_volume)
    if eta < 0:
        raise ValueError("eta must be non-negative.")
    if beta <= 0:
        raise ValueError("beta must be positive.")

    participation = child_quantity / market_volume
    return float(eta * mid_price * participation**beta)


def permanent_market_impact(
    mid_price: float,
    child_quantity: float,
    market_volume: float,
    gamma: float = DEFAULT_PERMANENT_IMPACT_GAMMA,
) -> float:
    """Estimate permanent impact proxy for one child order."""
    _validate_impact_inputs(mid_price, child_quantity, market_volume)
    if gamma < 0:
        raise ValueError("gamma must be non-negative.")

    participation = child_quantity / market_volume
    return float(gamma * mid_price * participation)


def _validate_impact_inputs(
    mid_price: float,
    child_quantity: float,
    market_volume: float,
) -> None:
    """Validate common market impact inputs."""
    if mid_price <= 0:
        raise ValueError("mid_price must be positive.")
    if child_quantity < 0:
        raise ValueError("child_quantity must be non-negative.")
    if market_volume <= 0:
        raise ValueError("market_volume must be positive.")


def fill_price_for_child_order(
    side: str,
    synthetic_bid: float,
    synthetic_ask: float,
    temporary_impact: float,
) -> float:
    """Estimate the fill price for one buy or sell child order."""
    normalized_side = side.lower()
    if normalized_side not in VALID_TCA_SIDES:
        raise ValueError(f"side must be one of {sorted(VALID_TCA_SIDES)}, got {side!r}.")
    if synthetic_bid <= 0 or synthetic_ask <= 0:
        raise ValueError("synthetic bid and ask must be positive.")
    if synthetic_bid > synthetic_ask:
        raise ValueError("synthetic_bid must be less than or equal to synthetic_ask.")
    if temporary_impact < 0:
        raise ValueError("temporary_impact must be non-negative.")

    if normalized_side == "buy":
        return float(synthetic_ask + temporary_impact)
    return float(synthetic_bid - temporary_impact)


def apply_transaction_cost_model(fills: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    """Estimate fill prices and cost components for child orders."""
    required_fills = ["timestamp", "side", "quantity"]
    missing_fills = [col for col in required_fills if col not in fills.columns]
    if missing_fills:
        raise ValueError(f"Missing required fill columns: {missing_fills}")

    quoted_market = add_synthetic_bid_ask(market_data)
    required_market = [
        "volume",
        "mid_price",
        "synthetic_bid",
        "synthetic_ask",
        "half_spread",
    ]
    missing_market = [col for col in required_market if col not in quoted_market.columns]
    if missing_market:
        raise ValueError(f"Missing required market cost columns: {missing_market}")

    market_lookup = quoted_market[required_market]
    enriched = fills.copy()
    enriched = enriched.join(market_lookup, on="timestamp", how="left")
    if enriched[required_market].isna().any().any():
        raise ValueError("Some child orders could not be matched to market data timestamps.")

    temporary_impacts = []
    permanent_impacts = []
    fill_prices = []
    spread_costs = []

    for _, row in enriched.iterrows():
        temporary_impact = temporary_market_impact(
            mid_price=row["mid_price"],
            child_quantity=row["quantity"],
            market_volume=row["volume"],
        )
        permanent_impact = permanent_market_impact(
            mid_price=row["mid_price"],
            child_quantity=row["quantity"],
            market_volume=row["volume"],
        )
        fill_price = fill_price_for_child_order(
            side=row["side"],
            synthetic_bid=row["synthetic_bid"],
            synthetic_ask=row["synthetic_ask"],
            temporary_impact=temporary_impact,
        )

        spread_cost = (
            row["synthetic_ask"] - row["mid_price"]
            if row["side"] == "buy"
            else row["mid_price"] - row["synthetic_bid"]
        )

        temporary_impacts.append(temporary_impact)
        permanent_impacts.append(permanent_impact)
        fill_prices.append(fill_price)
        spread_costs.append(spread_cost)

    enriched["temporary_impact"] = temporary_impacts
    enriched["permanent_impact"] = permanent_impacts
    enriched["impact_cost"] = enriched["temporary_impact"] + enriched["permanent_impact"]
    enriched["spread_cost"] = spread_costs
    enriched["fill_price"] = fill_prices
    return enriched


def compute_tca_metrics(order: ParentOrder, fills: pd.DataFrame, market_data: pd.DataFrame) -> dict:
    """Compute one TCA result row for a parent order and strategy."""
    # Phase 7 will summarize implementation shortfall, VWAP slippage, cost
    # decomposition, opportunity cost, and fill rate for each parent order.
    raise NotImplementedError("TCA metrics will be implemented in Phase 7.")
