"""Backtest orchestration for data, features, signals, execution, and TCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.execution import ParentOrder, generate_parent_orders
from src.features import add_microstructure_features
from src.fill_simulator import (
    DEFAULT_FILL_MODEL,
    DEFAULT_RANDOM_SEED,
    PLACEMENT_STYLES,
    FillModelConfig,
    place_and_simulate_fills,
)
from src.strategies import AdaptiveStrategy, ExecutionStrategy, POVStrategy, TWAPStrategy, VWAPStrategy
from src.tca import apply_transaction_cost_model, compute_tca_metrics


SUMMARY_METRIC_COLUMNS = [
    "implementation_shortfall_bps",
    "vwap_slippage_bps",
    "spread_cost_bps",
    "impact_cost_bps",
    "adverse_selection_cost_bps",
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
    placement_styles: list[str] = field(default_factory=lambda: PLACEMENT_STYLES.copy())
    fill_model: str = DEFAULT_FILL_MODEL
    fill_config: FillModelConfig = field(default_factory=FillModelConfig)
    random_seed: int | None = DEFAULT_RANDOM_SEED
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

    def alignment_report(self, data: pd.DataFrame) -> pd.DataFrame:
        """Summarize timestamp coverage and missing bars by ticker."""
        if data.empty:
            raise ValueError("Cannot build alignment report for empty data.")
        if "ticker" not in data.columns:
            raise ValueError("Alignment report requires a ticker column.")

        unique_timestamps = pd.Index(data.index.unique()).sort_values()
        rows = []
        for ticker, ticker_data in data.groupby("ticker"):
            ticker_timestamps = pd.Index(ticker_data.index.unique()).sort_values()
            missing_timestamps = unique_timestamps.difference(ticker_timestamps)
            rows.append(
                {
                    "ticker": ticker,
                    "first_timestamp": ticker_timestamps.min(),
                    "last_timestamp": ticker_timestamps.max(),
                    "bar_count": len(ticker_data),
                    "unique_timestamp_count": len(ticker_timestamps),
                    "common_grid_count": len(unique_timestamps),
                    "missing_timestamp_count": len(missing_timestamps),
                    "missing_timestamp_rate": (
                        len(missing_timestamps) / len(unique_timestamps)
                        if len(unique_timestamps) > 0
                        else 0.0
                    ),
                }
            )

        return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)

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

    def run_order_strategy_placement(
        self,
        order: ParentOrder,
        strategy: ExecutionStrategy,
        placement_style: str,
        data: pd.DataFrame,
    ) -> tuple[dict, pd.DataFrame]:
        """Run one parent order through one schedule and one placement style."""
        child_orders = strategy.generate_child_orders(order, data)
        simulated_fills = place_and_simulate_fills(
            child_orders=child_orders,
            market_data=data,
            placement_style=placement_style,
            parent_order=order,
            fill_model=self.fill_model,
            fill_config=self.fill_config,
            random_seed=self.random_seed,
        )
        metrics = compute_tca_metrics(order, simulated_fills, data)
        metrics["parent_order_id"] = order.order_id
        metrics["placement_style"] = placement_style
        metrics["fill_model"] = self.fill_model
        metrics["random_seed"] = self.random_seed

        simulated_fills["parent_order_id"] = order.order_id
        simulated_fills["parent_date"] = order.date
        simulated_fills["parent_quantity"] = order.quantity
        simulated_fills["parent_start_time"] = order.start_time
        simulated_fills["parent_end_time"] = order.end_time
        simulated_fills["participation_cap"] = order.participation_cap
        return metrics, simulated_fills

    def run_single_ticker_csv(self, input_csv: str | Path) -> pd.DataFrame:
        """Run all configured strategies on parent orders from one processed CSV."""
        data = self.prepare_data_from_csv(input_csv)
        return self.run_single_ticker_data(data)

    def run_multiple_csvs(self, input_csvs: list[str | Path]) -> pd.DataFrame:
        """Run independent backtests for multiple processed CSVs and combine results."""
        if not input_csvs:
            raise ValueError("At least one input CSV is required.")

        results = []
        for input_csv in input_csvs:
            ticker_results = self.run_single_ticker_csv(input_csv)
            ticker_results["source_csv"] = str(input_csv)
            results.append(ticker_results)

        return pd.concat(results, ignore_index=True)

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

    def run_execution_grid_data(self, data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Run every strategy against every placement style for one data set."""
        if "spread_proxy" not in data.columns:
            data = add_microstructure_features(data)

        parent_orders = generate_parent_orders(
            data,
            max_orders_per_ticker=self.max_orders_per_ticker,
        )
        if not parent_orders:
            raise ValueError("No parent orders generated from input data.")

        result_rows = []
        fill_parts = []
        for order in parent_orders:
            for strategy in self.strategies:
                for placement_style in self.placement_styles:
                    metrics, fills = self.run_order_strategy_placement(
                        order=order,
                        strategy=strategy,
                        placement_style=placement_style,
                        data=data,
                    )
                    result_rows.append(metrics)
                    fill_parts.append(fills)

        return pd.DataFrame(result_rows), pd.concat(fill_parts, ignore_index=True)

    def run_execution_grid_csv(self, input_csv: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Run the execution grid for one processed CSV."""
        data = self.prepare_data_from_csv(input_csv)
        results, fills = self.run_execution_grid_data(data)
        results["source_csv"] = str(input_csv)
        fills["source_csv"] = str(input_csv)
        return results, fills

    def run_execution_grid_csvs(self, input_csvs: list[str | Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Run independent execution grids for multiple processed CSVs."""
        if not input_csvs:
            raise ValueError("At least one input CSV is required.")

        result_parts = []
        fill_parts = []
        for input_csv in input_csvs:
            results, fills = self.run_execution_grid_csv(input_csv)
            result_parts.append(results)
            fill_parts.append(fills)

        return pd.concat(result_parts, ignore_index=True), pd.concat(fill_parts, ignore_index=True)

    def execution_tape_for_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate long-form child-order tape for one prepared or processed DataFrame."""
        if "spread_proxy" not in data.columns:
            data = add_microstructure_features(data)

        parent_orders = generate_parent_orders(
            data,
            max_orders_per_ticker=self.max_orders_per_ticker,
        )
        if not parent_orders:
            raise ValueError("No parent orders generated from input data.")

        tape_parts = []
        for order in parent_orders:
            for strategy in self.strategies:
                child_orders = strategy.generate_child_orders(order, data).copy()
                child_orders["parent_order_id"] = order.order_id
                child_orders["parent_date"] = order.date
                child_orders["parent_quantity"] = order.quantity
                child_orders["parent_start_time"] = order.start_time
                child_orders["parent_end_time"] = order.end_time
                child_orders["participation_cap"] = order.participation_cap
                child_orders["notional"] = (
                    child_orders["quantity"] * child_orders["reference_price"]
                )
                tape_parts.append(child_orders)

        return pd.concat(tape_parts, ignore_index=True)

    def execution_tape_for_csv(self, input_csv: str | Path) -> pd.DataFrame:
        """Generate child-order tape for one processed CSV."""
        data = self.prepare_data_from_csv(input_csv)
        tape = self.execution_tape_for_data(data)
        tape["source_csv"] = str(input_csv)
        return tape

    def execution_tape_for_csvs(self, input_csvs: list[str | Path]) -> pd.DataFrame:
        """Generate child-order tape for multiple processed CSVs."""
        if not input_csvs:
            raise ValueError("At least one input CSV is required.")

        tapes = [self.execution_tape_for_csv(path) for path in input_csvs]
        return pd.concat(tapes, ignore_index=True)

    def summarize_execution_by_timestamp(self, execution_tape: pd.DataFrame) -> pd.DataFrame:
        """Aggregate child-order activity by timestamp and strategy."""
        if execution_tape.empty:
            raise ValueError("Cannot summarize an empty execution tape.")

        required = ["timestamp", "strategy", "ticker", "quantity", "notional"]
        missing = [col for col in required if col not in execution_tape.columns]
        if missing:
            raise ValueError(f"Missing required execution summary columns: {missing}")

        summary = (
            execution_tape.groupby(["timestamp", "strategy"])
            .agg(
                active_tickers=("ticker", "nunique"),
                child_orders=("quantity", "size"),
                total_quantity=("quantity", "sum"),
                total_notional=("notional", "sum"),
            )
            .reset_index()
            .sort_values(["timestamp", "strategy"])
        )
        return summary

    def summarize_by_strategy(self, results: pd.DataFrame) -> pd.DataFrame:
        """Aggregate parent-order TCA result rows by strategy."""
        return self._summarize_results(results, ["strategy"])

    def summarize_by_ticker(self, results: pd.DataFrame) -> pd.DataFrame:
        """Aggregate parent-order TCA result rows by ticker."""
        return self._summarize_results(results, ["ticker"])

    def summarize_by_ticker_strategy(self, results: pd.DataFrame) -> pd.DataFrame:
        """Aggregate parent-order TCA result rows by ticker and strategy."""
        return self._summarize_results(results, ["ticker", "strategy"])

    def summarize_by_placement(self, results: pd.DataFrame) -> pd.DataFrame:
        """Aggregate execution-grid result rows by placement style."""
        return self._summarize_results(results, ["placement_style"])

    def summarize_by_strategy_placement(self, results: pd.DataFrame) -> pd.DataFrame:
        """Aggregate execution-grid result rows by strategy and placement style."""
        return self._summarize_results(results, ["strategy", "placement_style"])

    def _summarize_results(self, results: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
        """Aggregate TCA result rows over the requested grouping columns."""
        if results.empty:
            raise ValueError("Cannot summarize empty backtest results.")

        required = [*group_cols, *SUMMARY_METRIC_COLUMNS]
        missing = [col for col in required if col not in results.columns]
        if missing:
            raise ValueError(f"Missing required summary columns: {missing}")

        summary = (
            results.groupby(group_cols)[SUMMARY_METRIC_COLUMNS]
            .mean()
            .reset_index()
        )
        counts = results.groupby(group_cols).size().rename("num_simulations").reset_index()
        return summary.merge(counts, on=group_cols)

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
