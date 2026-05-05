"""Execution strategy implementations."""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder


class ExecutionStrategy:
    """Base interface for child-order generation."""

    name = "base"

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate child orders for a parent order and market data window."""
        # Concrete strategies will return one row per child order with timestamp,
        # ticker, side, strategy, quantity, and reference price.
        raise NotImplementedError


class TWAPStrategy(ExecutionStrategy):
    # Evenly allocates quantity across time bars.
    name = "TWAP"


class VWAPStrategy(ExecutionStrategy):
    # Allocates quantity using the historical volume curve from Phase 2.
    name = "VWAP"


class POVStrategy(ExecutionStrategy):
    # Trades as a capped percentage of realized market volume.
    name = "POV"


class AdaptiveStrategy(ExecutionStrategy):
    # Adjusts speed using alpha, liquidity, spread, volatility, and urgency.
    name = "Adaptive"
