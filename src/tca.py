"""Transaction cost analysis and synthetic cost model utilities.

Yahoo Finance does not provide real bid/ask quotes. Phase 6 therefore starts
with deterministic synthetic quotes derived from close price and the OHLCV-based
`spread_proxy` feature. This is a modeling approximation, not quoted market data.
"""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder


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


def apply_transaction_cost_model(fills: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    """Estimate fill prices and cost components for child orders."""
    # Phase 6 will synthesize bid/ask prices from close and spread_proxy because
    # Yahoo Finance does not provide quoted markets.
    raise NotImplementedError("Transaction cost model will be implemented in Phase 6.")


def compute_tca_metrics(order: ParentOrder, fills: pd.DataFrame, market_data: pd.DataFrame) -> dict:
    """Compute one TCA result row for a parent order and strategy."""
    # Phase 7 will summarize implementation shortfall, VWAP slippage, cost
    # decomposition, opportunity cost, and fill rate for each parent order.
    raise NotImplementedError("TCA metrics will be implemented in Phase 7.")
