"""Backtest orchestration for data, features, signals, execution, and TCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.features import add_microstructure_features
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

    def prepare_data_from_csv(self, input_csv: str | Path) -> pd.DataFrame:
        """Load a processed CSV and add Phase 2 features for backtesting."""
        data = pd.read_csv(input_csv, index_col=0, parse_dates=True)
        return add_microstructure_features(data)

    def run(self) -> None:
        """Run the backtest."""
        raise NotImplementedError("Backtest orchestration will be implemented in Phase 8.")
