"""Execution strategy implementations."""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder


class ExecutionStrategy:
    """Base interface for child-order generation."""

    name = "base"

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate child orders for a parent order and market data window."""
        raise NotImplementedError


class TWAPStrategy(ExecutionStrategy):
    name = "TWAP"


class VWAPStrategy(ExecutionStrategy):
    name = "VWAP"


class POVStrategy(ExecutionStrategy):
    name = "POV"


class AdaptiveStrategy(ExecutionStrategy):
    name = "Adaptive"
