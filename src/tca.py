"""Transaction cost analysis and synthetic cost model utilities.

Yahoo Finance does not provide real bid/ask quotes. Phase 6 therefore starts
with deterministic synthetic quotes derived from close price and the OHLCV-based
`spread_proxy` feature. This is a modeling approximation, not quoted market data.
"""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder, parse_time


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


def average_fill_price(fills: pd.DataFrame) -> float:
    """Return quantity-weighted average fill price for executed child orders."""
    required = ["fill_price", "quantity"]
    missing = [col for col in required if col not in fills.columns]
    if missing:
        raise ValueError(f"Missing required average fill columns: {missing}")

    executable_fills = fills[fills["quantity"] > 0]
    filled_quantity = executable_fills["quantity"].sum()
    if filled_quantity <= 0:
        raise ValueError("Cannot compute average fill price with non-positive filled quantity.")

    return float((executable_fills["fill_price"] * executable_fills["quantity"]).sum() / filled_quantity)


def arrival_price(order: ParentOrder, market_data: pd.DataFrame) -> float:
    """Return close price at the parent order start time."""
    window = _parent_order_market_window(order, market_data)
    return float(window.iloc[0]["close"])


def market_vwap(order: ParentOrder, market_data: pd.DataFrame) -> float:
    """Return market VWAP over the parent order execution window."""
    window = _parent_order_market_window(order, market_data)
    total_volume = window["volume"].sum()
    if total_volume <= 0:
        raise ValueError("Cannot compute market VWAP with non-positive market volume.")

    return float((window["close"] * window["volume"]).sum() / total_volume)


def implementation_shortfall_bps(side: str, avg_fill_price: float, arrival_px: float) -> float:
    """Return implementation shortfall in basis points."""
    _validate_price_metric_inputs(side, avg_fill_price, arrival_px)
    normalized_side = side.lower()

    if normalized_side == "buy":
        shortfall = avg_fill_price - arrival_px
    else:
        shortfall = arrival_px - avg_fill_price

    return float(10_000 * shortfall / arrival_px)


def vwap_slippage_bps(side: str, avg_fill_price: float, market_vwap_price: float) -> float:
    """Return slippage versus market VWAP in basis points."""
    _validate_price_metric_inputs(side, avg_fill_price, market_vwap_price)
    normalized_side = side.lower()

    if normalized_side == "buy":
        slippage = avg_fill_price - market_vwap_price
    else:
        slippage = market_vwap_price - avg_fill_price

    return float(10_000 * slippage / market_vwap_price)


def weighted_cost_bps(fills: pd.DataFrame, cost_col: str, reference_price: float) -> float:
    """Return quantity-weighted per-share cost in basis points."""
    required = ["quantity", cost_col]
    missing = [col for col in required if col not in fills.columns]
    if missing:
        raise ValueError(f"Missing required cost columns: {missing}")
    if reference_price <= 0:
        raise ValueError("reference_price must be positive.")

    filled_quantity = fills["quantity"].sum()
    if filled_quantity <= 0:
        return 0.0

    avg_cost = (fills[cost_col] * fills["quantity"]).sum() / filled_quantity
    return float(10_000 * avg_cost / reference_price)


def timing_cost_bps(order: ParentOrder, fills: pd.DataFrame, arrival_px: float) -> float:
    """Return quantity-weighted timing cost in basis points."""
    required = ["quantity", "mid_price"]
    missing = [col for col in required if col not in fills.columns]
    if missing:
        raise ValueError(f"Missing required timing cost columns: {missing}")
    if arrival_px <= 0:
        raise ValueError("arrival_px must be positive.")

    filled_quantity = fills["quantity"].sum()
    if filled_quantity <= 0:
        return 0.0

    if order.side == "buy":
        per_share_timing = fills["mid_price"] - arrival_px
    else:
        per_share_timing = arrival_px - fills["mid_price"]

    avg_timing = (per_share_timing * fills["quantity"]).sum() / filled_quantity
    return float(10_000 * avg_timing / arrival_px)


def fill_rate(order: ParentOrder, fills: pd.DataFrame) -> float:
    """Return filled quantity divided by parent order quantity."""
    if "quantity" not in fills.columns:
        raise ValueError("Missing required fill-rate column: quantity")
    if order.quantity <= 0:
        raise ValueError("order quantity must be positive.")

    raw_fill_rate = fills["quantity"].sum() / order.quantity
    return float(max(0.0, min(1.0, raw_fill_rate)))


def opportunity_cost_bps(
    order: ParentOrder,
    fills: pd.DataFrame,
    market_data: pd.DataFrame,
    arrival_px: float,
) -> float:
    """Return opportunity cost for unfilled shares in basis points."""
    if arrival_px <= 0:
        raise ValueError("arrival_px must be positive.")

    unfilled_quantity = max(order.quantity - fills["quantity"].sum(), 0.0)
    if unfilled_quantity == 0:
        return 0.0

    window = _parent_order_market_window(order, market_data)
    close_at_end = float(window.iloc[-1]["close"])
    opportunity_cost = unfilled_quantity * abs(close_at_end - arrival_px)
    notional = order.quantity * arrival_px
    return float(10_000 * opportunity_cost / notional)


def _validate_price_metric_inputs(side: str, price_a: float, price_b: float) -> None:
    """Validate common signed price metric inputs."""
    if side.lower() not in VALID_TCA_SIDES:
        raise ValueError(f"side must be one of {sorted(VALID_TCA_SIDES)}, got {side!r}.")
    if price_a <= 0 or price_b <= 0:
        raise ValueError("price inputs must be positive.")


def _parent_order_market_window(order: ParentOrder, market_data: pd.DataFrame) -> pd.DataFrame:
    """Return ticker/date/time-filtered market data for a parent order."""
    required = ["ticker", "date", "time", "close", "volume"]
    missing = [col for col in required if col not in market_data.columns]
    if missing:
        raise ValueError(f"Missing required parent-order market columns: {missing}")

    window = market_data[market_data["ticker"] == order.ticker]
    if order.date is not None:
        window = window[window["date"] == order.date]

    bar_times = window["time"].map(parse_time)
    window = window[(bar_times >= order.start_time) & (bar_times <= order.end_time)]
    if window.empty:
        raise ValueError(f"No market data available for parent order {order.order_id}.")

    return window.sort_index()


def compute_tca_metrics(order: ParentOrder, fills: pd.DataFrame, market_data: pd.DataFrame) -> dict:
    """Compute one TCA result row for a parent order and strategy."""
    if fills.empty:
        raise ValueError("Cannot compute TCA metrics for empty fills.")
    required = ["timestamp", "strategy", "quantity", "fill_price", "spread_cost", "impact_cost", "mid_price"]
    missing = [col for col in required if col not in fills.columns]
    if missing:
        raise ValueError(f"Missing required TCA metric columns: {missing}")

    arrival_px = arrival_price(order, market_data)
    market_vwap_px = market_vwap(order, market_data)
    strategy = fills["strategy"].iloc[0]
    placement_style = fills["placement_style"].iloc[0] if "placement_style" in fills.columns else None
    fill_model = fills["fill_model"].iloc[0] if "fill_model" in fills.columns else None
    filled_fills = fills[fills["quantity"] > 0]
    filled_quantity = filled_fills["quantity"].sum()

    if filled_quantity > 0:
        avg_fill = average_fill_price(fills)
        implementation_shortfall = implementation_shortfall_bps(
            order.side,
            avg_fill,
            arrival_px,
        )
        vwap_slippage = vwap_slippage_bps(
            order.side,
            avg_fill,
            market_vwap_px,
        )
        timestamps = pd.to_datetime(filled_fills["timestamp"])
        execution_duration = timestamps.max() - timestamps.min()
    else:
        # A passive or pegged limit placement can miss every bar. Keep a valid
        # TCA row so the grid can compare opportunity cost against filled paths.
        avg_fill = float("nan")
        implementation_shortfall = float("nan")
        vwap_slippage = float("nan")
        execution_duration = pd.Timedelta(0)

    metrics = {
        "ticker": order.ticker,
        "date": order.date,
        "side": order.side,
        "quantity": order.quantity,
        "strategy": strategy,
        "avg_fill_price": avg_fill,
        "arrival_price": arrival_px,
        "market_vwap": market_vwap_px,
        "implementation_shortfall_bps": implementation_shortfall,
        "vwap_slippage_bps": vwap_slippage,
        "spread_cost_bps": weighted_cost_bps(fills, "spread_cost", arrival_px),
        "impact_cost_bps": weighted_cost_bps(fills, "impact_cost", arrival_px),
        "timing_cost_bps": timing_cost_bps(order, fills, arrival_px),
        "opportunity_cost_bps": opportunity_cost_bps(order, fills, market_data, arrival_px),
        "fill_rate": fill_rate(order, fills),
        "execution_duration": execution_duration,
    }
    if placement_style is not None:
        metrics["placement_style"] = placement_style
    if fill_model is not None:
        metrics["fill_model"] = fill_model

    return metrics
