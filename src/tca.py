"""Transaction cost analysis and synthetic cost model utilities."""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder


def apply_transaction_cost_model(fills: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    """Estimate fill prices and cost components for child orders."""
    raise NotImplementedError("Transaction cost model will be implemented in Phase 6.")


def compute_tca_metrics(order: ParentOrder, fills: pd.DataFrame, market_data: pd.DataFrame) -> dict:
    """Compute one TCA result row for a parent order and strategy."""
    raise NotImplementedError("TCA metrics will be implemented in Phase 7.")
