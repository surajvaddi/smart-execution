"""Backtest orchestration for data, features, signals, execution, and TCA."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Backtester:
    """Coordinates multi-ticker, multi-strategy execution simulations."""

    tickers: list[str]
    period: str = "60d"
    interval: str = "5m"

    def run(self) -> None:
        """Run the backtest."""
        raise NotImplementedError("Backtest orchestration will be implemented in Phase 8.")
