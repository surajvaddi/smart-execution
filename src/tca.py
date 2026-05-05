"""Transaction cost analysis and synthetic cost model utilities."""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder


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
