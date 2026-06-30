"""Adaptive participation schedule for bar-based execution research."""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder
from src.strategies import ExecutionStrategy
from src.strategy_config import AdaptiveParticipationConfig


def target_participation_rate(
    row: pd.Series,
    side: str,
    config: AdaptiveParticipationConfig | None = None,
) -> float:
    """Return a bounded participation target from signal, liquidity, and volatility."""
    config = config or AdaptiveParticipationConfig()

    signal = float(row.get("alpha_signal", 0.0))
    liquidity = float(row.get("liquidity_score", 0.0))
    volatility = max(float(row.get("rolling_vol", 0.0)), 0.0)

    directional_signal = signal if side == "buy" else -signal
    raw_rate = (
        config.base_participation_rate
        + config.signal_weight * directional_signal * config.base_participation_rate
        + config.liquidity_weight * liquidity * config.base_participation_rate
        - config.volatility_penalty_weight * volatility
    )
    bounded_rate = min(config.max_participation_rate, max(config.min_participation_rate, raw_rate))
    return float(bounded_rate)


def generate_adaptive_participation_schedule(
    order: ParentOrder,
    data: pd.DataFrame,
    config: AdaptiveParticipationConfig | None = None,
) -> pd.DataFrame:
    """Generate a variable-rate participation schedule from market conditions."""
    strategy = AdaptiveParticipationStrategy(config=config)
    return strategy.generate_child_orders(order, data)


class AdaptiveParticipationStrategy(ExecutionStrategy):
    """Participation schedule that varies its target rate with market state."""

    name = "AdaptiveParticipation"

    def __init__(self, config: AdaptiveParticipationConfig | None = None) -> None:
        self.config = config or AdaptiveParticipationConfig()

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate child orders from dynamic participation targets."""
        window = self.market_window(order, data).copy()
        required_columns = ["alpha_signal", "rolling_vol", "liquidity_score", "volume", "close"]
        missing = [column for column in required_columns if column not in window.columns]
        if missing:
            raise ValueError(f"Missing required adaptive participation columns: {missing}")

        remaining_quantity = order.quantity
        timestamps = []
        quantities = []
        reference_prices = []

        for bar_number, (timestamp, row) in enumerate(window.iterrows()):
            if remaining_quantity <= 0:
                break

            remaining_bars = len(window) - bar_number
            target_rate = min(
                order.participation_cap,
                target_participation_rate(row, order.side, self.config),
            )
            child_quantity = min(remaining_quantity, float(row["volume"]) * target_rate)
            if remaining_bars == 1:
                child_quantity = min(remaining_quantity, float(row["volume"]) * order.participation_cap)
            if child_quantity <= 0:
                continue

            timestamps.append(timestamp)
            quantities.append(float(child_quantity))
            reference_prices.append(float(row["close"]))
            remaining_quantity -= child_quantity

        return self.child_order_frame(
            order=order,
            timestamps=pd.Index(timestamps),
            quantities=quantities,
            reference_prices=reference_prices,
        )
