"""Backtest orchestration for data, features, signals, execution, and TCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.execution import ParentOrder, generate_parent_orders
from src.features import add_microstructure_features
from src.strategies import AdaptiveStrategy, ExecutionStrategy, POVStrategy, TWAPStrategy, VWAPStrategy
from src.tca import apply_transaction_cost_model, compute_tca_metrics


SUMMARY_METRIC_COLUMNS = [
    "implementation_shortfall_bps",
    "vwap_slippage_bps",
    "spread_cost_bps",
    "impact_cost_bps",
    "timing_cost_bps",
    "opportunity_cost_bps",
    "fill_rate",
]


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

    def prepare_data_from_csvs(self, input_csvs: list[str | Path]) -> pd.DataFrame:
        """Load and combine multiple processed CSVs with Phase 2 features."""
        if not input_csvs:
            raise ValueError("At least one input CSV is required.")

        prepared = [self.prepare_data_from_csv(path) for path in input_csvs]
        combined = pd.concat(prepared).sort_index()
        if "ticker" not in combined.columns:
            raise ValueError("Combined data must include a ticker column.")
        return combined

    def run_order_strategy(
        self,
        order: ParentOrder,
        strategy: ExecutionStrategy,
        data: pd.DataFrame,
    ) -> dict:
        """Run one parent order through one strategy and return TCA metrics."""
        child_orders = strategy.generate_child_orders(order, data)
        enriched_fills = apply_transaction_cost_model(child_orders, data)
        return compute_tca_metrics(order, enriched_fills, data)

    def run_single_ticker_csv(self, input_csv: str | Path) -> pd.DataFrame:
        """Run all configured strategies on parent orders from one processed CSV."""
        data = self.prepare_data_from_csv(input_csv)
        return self.run_single_ticker_data(data)

    def run_single_ticker_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Run all configured strategies on one prepared or processed DataFrame."""
        if "spread_proxy" not in data.columns:
            data = add_microstructure_features(data)

        parent_orders = generate_parent_orders(
            data,
            max_orders_per_ticker=self.max_orders_per_ticker,
        )
        if not parent_orders:
            raise ValueError("No parent orders generated from input data.")

        results = []
        for order in parent_orders:
            for strategy in self.strategies:
                # Every strategy receives the same feature-enriched data and the
                # same parent order. This keeps schedule/TCA comparisons fair.
                results.append(self.run_order_strategy(order, strategy, data))

        return pd.DataFrame(results)

    def summarize_by_strategy(self, results: pd.DataFrame) -> pd.DataFrame:
        """Aggregate parent-order TCA result rows by strategy."""
        if results.empty:
            raise ValueError("Cannot summarize empty backtest results.")

        required = ["strategy", *SUMMARY_METRIC_COLUMNS]
        missing = [col for col in required if col not in results.columns]
        if missing:
            raise ValueError(f"Missing required summary columns: {missing}")

        summary = (
            results.groupby("strategy")[SUMMARY_METRIC_COLUMNS]
            .mean()
            .reset_index()
        )
        counts = results.groupby("strategy").size().rename("num_simulations").reset_index()
        return summary.merge(counts, on="strategy")

    def save_results(
        self,
        results: pd.DataFrame,
        results_path: str | Path,
        summary_path: str | Path,
    ) -> tuple[Path, Path]:
        """Save detailed backtest results and strategy-level summary CSVs."""
        if results.empty:
            raise ValueError("Cannot save empty backtest results.")

        results_output = Path(results_path)
        summary_output = Path(summary_path)
        results_output.parent.mkdir(parents=True, exist_ok=True)
        summary_output.parent.mkdir(parents=True, exist_ok=True)

        summary = self.summarize_by_strategy(results)
        results.to_csv(results_output, index=False)
        summary.to_csv(summary_output, index=False)
        return results_output, summary_output

    def run(self) -> None:
        """Run the backtest."""
        raise NotImplementedError("Backtest orchestration will be implemented in Phase 8.")
