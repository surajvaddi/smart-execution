"""Backtest orchestration for data, features, signals, execution, and TCA."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.strategies import AdaptiveStrategy, ExecutionStrategy, POVStrategy, TWAPStrategy, VWAPStrategy


def default_strategies() -> list[ExecutionStrategy]:
    """Return the default strategy set used in the assignment."""
    return [
        TWAPStrategy(),
        VWAPStrategy(),
        POVStrategy(),
        AdaptiveStrategy(),
    ]


@dataclass
class Backtester:
    """Coordinates multi-ticker, multi-strategy execution simulations."""

    # These defaults match the README's main research setting. The backtester
    # itself is implemented later once data, features, signals, strategies, and
    # TCA each have tested standalone behavior.
    tickers: list[str]
    period: str = "60d"
    interval: str = "5m"
    strategies: list[ExecutionStrategy] = field(default_factory=default_strategies)
    max_orders_per_ticker: int | None = 20

    def run(self) -> None:
        """Run the backtest."""
        raise NotImplementedError("Backtest orchestration will be implemented in Phase 8.")
