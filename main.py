"""Entry point for incremental smart execution backtester development.

The CLI exposes small phase-specific smoke checks while the full backtester is
being built. This keeps each phase testable before the final orchestration code
exists.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtester import Backtester
from src.data_loader import load_and_save_intraday_data
from src.features import add_microstructure_features, estimate_volume_curve
from src.fill_simulator import DEFAULT_FILL_MODEL, DEFAULT_RANDOM_SEED, PLACEMENT_STYLES, VALID_FILL_MODELS
from src.execution import generate_parent_orders, parent_orders_to_frame, parse_time
from src.rl_backtester import run_rl_backtest_data
from src.rl_policy import HeuristicExecutionPolicy, QTablePolicy, RandomPolicy
from src.rl_train import build_training_envs, load_q_table, save_q_table, train_q_policy
from src.signals import (
    DEFAULT_HORIZONS,
    add_forward_returns,
    evaluate_signals,
    signal_decay_table,
    signal_quality_summary,
)
from src.strategies import AdaptiveStrategy, POVStrategy, TWAPStrategy, VWAPStrategy
from src.tca import apply_transaction_cost_model, compute_tca_metrics


DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Smart Execution Backtester")
    parser.add_argument(
        "--download-sample",
        action="store_true",
        help="Download and save a small sample ticker dataset.",
    )
    parser.add_argument("--ticker", default="SPY", help="Ticker to download in sample mode.")
    parser.add_argument("--period", default="5d", help="Yahoo Finance period for sample mode.")
    parser.add_argument("--interval", default="5m", help="Yahoo Finance interval for sample mode.")
    parser.add_argument(
        "--feature-sample",
        action="store_true",
        help="Compute Phase 2 features for a processed sample CSV.",
    )
    parser.add_argument(
        "--signal-sample",
        action="store_true",
        help="Compute Phase 3 signal metrics for a processed sample CSV.",
    )
    parser.add_argument(
        "--orders-sample",
        action="store_true",
        help="Generate Phase 4 parent orders for a processed sample CSV.",
    )
    parser.add_argument(
        "--twap-sample",
        action="store_true",
        help="Generate a Phase 5 TWAP child-order schedule for one parent order.",
    )
    parser.add_argument(
        "--vwap-sample",
        action="store_true",
        help="Generate a Phase 5 VWAP child-order schedule for one parent order.",
    )
    parser.add_argument(
        "--pov-sample",
        action="store_true",
        help="Generate a Phase 5 POV child-order schedule for one parent order.",
    )
    parser.add_argument(
        "--adaptive-sample",
        action="store_true",
        help="Generate a Phase 5 Adaptive child-order schedule for one parent order.",
    )
    parser.add_argument(
        "--strategy-compare-sample",
        action="store_true",
        help="Compare Phase 5 child-order schedules for one parent order.",
    )
    parser.add_argument(
        "--tca-sample",
        action="store_true",
        help="Apply the Phase 6 transaction cost model to one TWAP schedule.",
    )
    parser.add_argument(
        "--tca-metrics-sample",
        action="store_true",
        help="Compute Phase 7 TCA metrics for one TWAP parent order.",
    )
    parser.add_argument(
        "--backtest-sample",
        action="store_true",
        help="Run a Phase 8 one-ticker backtest sample across all strategies.",
    )
    parser.add_argument(
        "--alignment-report",
        action="store_true",
        help="Create a timestamp alignment report for multiple processed CSVs.",
    )
    parser.add_argument(
        "--backtest-multi",
        action="store_true",
        help="Run an independent multi-CSV backtest across all strategies.",
    )
    parser.add_argument(
        "--download-tickers",
        nargs="+",
        default=None,
        help="Download and save processed data for multiple tickers.",
    )
    parser.add_argument(
        "--execution-tape",
        action="store_true",
        help="Create a multi-ticker child-order execution tape and timestamp summary.",
    )
    parser.add_argument(
        "--execution-grid-sample",
        action="store_true",
        help="Run one processed CSV through every strategy and placement style.",
    )
    parser.add_argument(
        "--execution-grid-multi",
        action="store_true",
        help="Run independent execution grids for multiple processed CSVs.",
    )
    parser.add_argument(
        "--rl-backtest-sample",
        action="store_true",
        help="Run a sample Adaptive Ensemble RL backtest.",
    )
    parser.add_argument(
        "--rl-train-q",
        action="store_true",
        help="Train a tabular Q policy for Adaptive Ensemble RL execution.",
    )
    parser.add_argument(
        "--rl-policy",
        choices=["heuristic", "random", "qtable"],
        default="heuristic",
        help="Policy to use with --rl-backtest-sample.",
    )
    parser.add_argument(
        "--q-table-path",
        default="artifacts/models/q_policy.pkl",
        help="Q-table path for --rl-policy qtable.",
    )
    parser.add_argument(
        "--q-episodes",
        type=int,
        default=10,
        help="Number of Q-learning training episodes for --rl-train-q.",
    )
    parser.add_argument(
        "--q-epsilon",
        type=float,
        default=0.20,
        help="Exploration rate for --rl-train-q.",
    )
    parser.add_argument(
        "--q-alpha",
        type=float,
        default=0.10,
        help="Learning rate for --rl-train-q.",
    )
    parser.add_argument(
        "--q-gamma",
        type=float,
        default=0.90,
        help="Discount factor for --rl-train-q.",
    )
    parser.add_argument(
        "--placement-styles",
        nargs="+",
        choices=PLACEMENT_STYLES,
        default=None,
        help="Placement styles to include in execution-grid commands.",
    )
    parser.add_argument(
        "--fill-model",
        choices=sorted(VALID_FILL_MODELS),
        default=DEFAULT_FILL_MODEL,
        help="Fill model to use in execution-grid commands.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Random seed for stochastic execution-grid fill models.",
    )
    parser.add_argument(
        "--orders-output-csv",
        default=None,
        help="Optional CSV path for --orders-sample parent orders.",
    )
    parser.add_argument(
        "--twap-output-csv",
        default=None,
        help="Optional CSV path for --twap-sample child orders.",
    )
    parser.add_argument(
        "--vwap-output-csv",
        default=None,
        help="Optional CSV path for --vwap-sample child orders.",
    )
    parser.add_argument(
        "--pov-output-csv",
        default=None,
        help="Optional CSV path for --pov-sample child orders.",
    )
    parser.add_argument(
        "--adaptive-output-csv",
        default=None,
        help="Optional CSV path for --adaptive-sample child orders.",
    )
    parser.add_argument(
        "--strategy-compare-output-csv",
        default=None,
        help="Optional CSV path for --strategy-compare-sample summary.",
    )
    parser.add_argument(
        "--tca-output-csv",
        default=None,
        help="Optional CSV path for --tca-sample enriched fills.",
    )
    parser.add_argument(
        "--tca-metrics-output-csv",
        default=None,
        help="Optional CSV path for --tca-metrics-sample result row.",
    )
    parser.add_argument(
        "--backtest-results-output-csv",
        default=None,
        help="Optional CSV path for --backtest-sample detailed results.",
    )
    parser.add_argument(
        "--backtest-summary-output-csv",
        default=None,
        help="Optional CSV path for --backtest-sample strategy summary.",
    )
    parser.add_argument(
        "--alignment-output-csv",
        default=None,
        help="Optional CSV path for --alignment-report output.",
    )
    parser.add_argument(
        "--backtest-multi-results-output-csv",
        default=None,
        help="Optional CSV path for --backtest-multi detailed results.",
    )
    parser.add_argument(
        "--backtest-multi-summary-strategy-output-csv",
        default=None,
        help="Optional CSV path for --backtest-multi summary by strategy.",
    )
    parser.add_argument(
        "--backtest-multi-summary-ticker-output-csv",
        default=None,
        help="Optional CSV path for --backtest-multi summary by ticker.",
    )
    parser.add_argument(
        "--backtest-multi-summary-ticker-strategy-output-csv",
        default=None,
        help="Optional CSV path for --backtest-multi summary by ticker and strategy.",
    )
    parser.add_argument(
        "--execution-tape-output-csv",
        default=None,
        help="Optional CSV path for --execution-tape child orders.",
    )
    parser.add_argument(
        "--execution-summary-output-csv",
        default=None,
        help="Optional CSV path for --execution-tape timestamp summary.",
    )
    parser.add_argument(
        "--execution-grid-fills-output-csv",
        default=None,
        help="Optional CSV path for execution-grid simulated fills.",
    )
    parser.add_argument(
        "--execution-grid-results-output-csv",
        default=None,
        help="Optional CSV path for execution-grid TCA results.",
    )
    parser.add_argument(
        "--execution-grid-summary-strategy-output-csv",
        default=None,
        help="Optional CSV path for execution-grid strategy summary.",
    )
    parser.add_argument(
        "--execution-grid-summary-placement-output-csv",
        default=None,
        help="Optional CSV path for execution-grid placement summary.",
    )
    parser.add_argument(
        "--execution-grid-summary-strategy-placement-output-csv",
        default=None,
        help="Optional CSV path for execution-grid strategy-placement summary.",
    )
    parser.add_argument(
        "--rl-backtest-output-csv",
        default=None,
        help="Optional CSV path for --rl-backtest-sample results.",
    )
    parser.add_argument(
        "--input-csv",
        default="data/processed/SPY_5d_5m.csv",
        help="Processed CSV to use with --feature-sample.",
    )
    parser.add_argument(
        "--input-csvs",
        nargs="+",
        default=None,
        help="Processed CSVs to use with multi-ticker commands.",
    )
    parser.add_argument(
        "--max-orders-per-ticker",
        type=int,
        default=1,
        help="Maximum parent orders per ticker for backtest sample commands.",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Inclusive start date filter for processed CSV commands, YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Inclusive end date filter for processed CSV commands, YYYY-MM-DD.",
    )
    parser.add_argument(
        "--start-time",
        default=None,
        help="Inclusive start time filter for processed CSV commands, HH:MM.",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="Inclusive end time filter for processed CSV commands, HH:MM.",
    )
    parser.add_argument(
        "--signal-output-csv",
        default=None,
        help="Optional CSV path for --signal-sample results.",
    )
    parser.add_argument(
        "--signal-decay-output-csv",
        default=None,
        help="Optional CSV path for --signal-sample IC decay results.",
    )
    parser.add_argument(
        "--signal-summary-output-csv",
        default=None,
        help="Optional CSV path for --signal-sample quality summary results.",
    )
    parser.add_argument(
        "--signal-notes-output-md",
        default=None,
        help="Optional markdown path for --signal-sample interpretation notes.",
    )
    args = parser.parse_args()
    _validate_filter_args(parser, args)
    return args


def _validate_filter_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Require date and time filters to be provided as explicit start/end pairs."""
    if bool(args.start_date) != bool(args.end_date):
        parser.error("--start-date and --end-date must be provided together.")
    if bool(args.start_time) != bool(args.end_time):
        parser.error("--start-time and --end-time must be provided together.")
    if (
        args.alignment_report
        or args.backtest_multi
        or args.execution_tape
        or args.execution_grid_multi
    ) and not args.input_csvs:
        parser.error(
            "--input-csvs is required for --alignment-report, --backtest-multi, "
            "--execution-tape, and --execution-grid-multi."
        )


def _load_processed_csv(
    input_csv: str,
    start_date: str | None = None,
    end_date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> tuple[Path, pd.DataFrame]:
    """Load a processed data-loader CSV for offline phase smoke checks."""
    input_path = Path(input_csv)
    data = pd.read_csv(input_path, index_col=0, parse_dates=True)
    data = _filter_processed_data(data, start_date, end_date, start_time, end_time)
    return input_path, data


def _filter_processed_data(
    data: pd.DataFrame,
    start_date: str | None,
    end_date: str | None,
    start_time: str | None,
    end_time: str | None,
) -> pd.DataFrame:
    """Apply optional inclusive date and time filters to processed market data."""
    filtered = data.copy()

    if start_date and end_date:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        if start > end:
            raise ValueError("--start-date must be on or before --end-date.")
        filtered_dates = pd.to_datetime(filtered["date"]).dt.date
        filtered = filtered[(filtered_dates >= start) & (filtered_dates <= end)]

    if start_time and end_time:
        start = parse_time(start_time)
        end = parse_time(end_time)
        if start > end:
            raise ValueError("--start-time must be on or before --end-time.")
        filtered_times = filtered["time"].map(parse_time)
        filtered = filtered[(filtered_times >= start) & (filtered_times <= end)]

    if filtered.empty:
        raise ValueError("No rows remain after applying date/time filters.")

    return filtered


def _load_processed_csv_from_args(args: argparse.Namespace) -> tuple[Path, pd.DataFrame]:
    """Load a processed CSV using the CLI's optional date/time filters."""
    return _load_processed_csv(
        input_csv=args.input_csv,
        start_date=args.start_date,
        end_date=args.end_date,
        start_time=args.start_time,
        end_time=args.end_time,
    )


def _require_input_csvs(args: argparse.Namespace) -> list[str]:
    """Return multi-CSV inputs or raise a clear CLI error."""
    if not args.input_csvs:
        raise ValueError("--input-csvs is required for this command.")
    return args.input_csvs


def _load_processed_csvs_from_args(args: argparse.Namespace) -> pd.DataFrame:
    """Load multiple processed CSVs using the CLI's optional date/time filters."""
    frames = []
    for input_csv in _require_input_csvs(args):
        _, data = _load_processed_csv(
            input_csv=input_csv,
            start_date=args.start_date,
            end_date=args.end_date,
            start_time=args.start_time,
            end_time=args.end_time,
        )
        frames.append(data)

    return pd.concat(frames).sort_index()


def _default_signal_output_path(input_path: Path) -> Path:
    """Create a stable default report path for signal evaluation output."""
    return Path("reports") / f"signal_evaluation_{input_path.stem}.csv"


def _default_signal_decay_output_path(input_path: Path) -> Path:
    """Create a stable default report path for signal decay output."""
    return Path("reports") / f"signal_decay_{input_path.stem}.csv"


def _default_signal_summary_output_path(input_path: Path) -> Path:
    """Create a stable default report path for signal quality summary output."""
    return Path("reports") / f"signal_summary_{input_path.stem}.csv"


def _default_signal_notes_output_path(input_path: Path) -> Path:
    """Create a stable default report path for signal interpretation notes."""
    return Path("reports") / f"signal_notes_{input_path.stem}.md"


def _default_orders_output_path(input_path: Path) -> Path:
    """Create a stable default report path for generated parent orders."""
    return Path("reports") / f"parent_orders_{input_path.stem}.csv"


def _default_twap_output_path(input_path: Path) -> Path:
    """Create a stable default report path for a TWAP sample schedule."""
    return Path("reports") / f"twap_child_orders_{input_path.stem}.csv"


def _default_vwap_output_path(input_path: Path) -> Path:
    """Create a stable default report path for a VWAP sample schedule."""
    return Path("reports") / f"vwap_child_orders_{input_path.stem}.csv"


def _default_pov_output_path(input_path: Path) -> Path:
    """Create a stable default report path for a POV sample schedule."""
    return Path("reports") / f"pov_child_orders_{input_path.stem}.csv"


def _default_adaptive_output_path(input_path: Path) -> Path:
    """Create a stable default report path for an Adaptive sample schedule."""
    return Path("reports") / f"adaptive_child_orders_{input_path.stem}.csv"


def _default_strategy_compare_output_path(input_path: Path) -> Path:
    """Create a stable default report path for strategy schedule comparison."""
    return Path("reports") / f"strategy_schedule_comparison_{input_path.stem}.csv"


def _default_tca_output_path(input_path: Path) -> Path:
    """Create a stable default report path for transaction-cost-enriched fills."""
    return Path("reports") / f"tca_fills_{input_path.stem}.csv"


def _default_tca_metrics_output_path(input_path: Path) -> Path:
    """Create a stable default report path for parent-order TCA metrics."""
    return Path("reports") / f"tca_metrics_{input_path.stem}.csv"


def _default_backtest_results_output_path(input_path: Path) -> Path:
    """Create a stable default report path for sample backtest results."""
    return Path("reports") / f"backtest_results_{input_path.stem}.csv"


def _default_backtest_summary_output_path(input_path: Path) -> Path:
    """Create a stable default report path for sample backtest summary."""
    return Path("reports") / f"backtest_summary_{input_path.stem}.csv"


def _default_alignment_output_path() -> Path:
    """Create a stable default report path for multi-ticker alignment output."""
    return Path("reports") / "alignment_report_multi.csv"


def _default_backtest_multi_results_output_path() -> Path:
    """Create a stable default report path for multi-ticker detailed results."""
    return Path("reports") / "backtest_results_multi.csv"


def _default_backtest_multi_summary_strategy_output_path() -> Path:
    """Create a stable default report path for multi-ticker strategy summary."""
    return Path("reports") / "backtest_summary_by_strategy_multi.csv"


def _default_backtest_multi_summary_ticker_output_path() -> Path:
    """Create a stable default report path for multi-ticker ticker summary."""
    return Path("reports") / "backtest_summary_by_ticker_multi.csv"


def _default_backtest_multi_summary_ticker_strategy_output_path() -> Path:
    """Create a stable default report path for multi-ticker ticker-strategy summary."""
    return Path("reports") / "backtest_summary_by_ticker_strategy_multi.csv"


def _default_execution_tape_output_path() -> Path:
    """Create a stable default report path for multi-ticker execution tape."""
    return Path("reports") / "execution_tape_multi.csv"


def _default_execution_summary_output_path() -> Path:
    """Create a stable default report path for timestamp-level execution summary."""
    return Path("reports") / "execution_summary_by_timestamp_multi.csv"


def _default_execution_grid_fills_output_path() -> Path:
    """Create a stable default report path for execution-grid simulated fills."""
    return Path("reports") / "execution_grid_fills.csv"


def _default_execution_grid_results_output_path() -> Path:
    """Create a stable default report path for execution-grid TCA results."""
    return Path("reports") / "execution_grid_results.csv"


def _default_execution_grid_summary_strategy_output_path() -> Path:
    """Create a stable default report path for execution-grid strategy summary."""
    return Path("reports") / "execution_grid_summary_by_strategy.csv"


def _default_execution_grid_summary_placement_output_path() -> Path:
    """Create a stable default report path for execution-grid placement summary."""
    return Path("reports") / "execution_grid_summary_by_placement.csv"


def _default_execution_grid_summary_strategy_placement_output_path() -> Path:
    """Create a stable default report path for execution-grid strategy-placement summary."""
    return Path("reports") / "execution_grid_summary_by_strategy_placement.csv"


def _default_rl_backtest_output_path(input_path: Path) -> Path:
    """Create a stable default report path for RL backtest results."""
    return Path("reports") / f"rl_backtest_results_{input_path.stem}.csv"


def _rl_policy_from_args(args: argparse.Namespace):
    """Create the requested RL policy object from CLI arguments."""
    if args.rl_policy == "random":
        return RandomPolicy(seed=args.random_seed)
    if args.rl_policy == "qtable":
        return QTablePolicy(load_q_table(args.q_table_path))
    return HeuristicExecutionPolicy()


def _write_signal_notes(
    output_path: Path,
    input_path: Path,
    evaluation: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    """Write concise interpretation notes for the current signal sample."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    top = summary.head(3)
    alpha_row = summary[summary["signal"] == "alpha_signal"]
    alpha_note = "alpha_signal was not present in the summary."
    if not alpha_row.empty:
        alpha = alpha_row.iloc[0]
        alpha_note = (
            f"alpha_signal mean absolute IC was {alpha['mean_abs_ic']:.6f}; "
            f"its strongest horizon was {int(alpha['best_horizon'])} bars "
            f"with IC {alpha['best_horizon_ic']:.6f}."
        )

    lines = [
        "# Phase 3 Signal Research Notes",
        "",
        f"Input data: `{input_path}`",
        f"Signal-horizon tests: {len(evaluation)}",
        "",
        "## Top Signals By Mean Absolute IC",
        "",
    ]
    for _, row in top.iterrows():
        lines.append(
            "- "
            f"{row['signal']}: mean absolute IC {row['mean_abs_ic']:.6f}, "
            f"best horizon {int(row['best_horizon'])} bars, "
            f"best-horizon IC {row['best_horizon_ic']:.6f}, "
            f"mean hit rate {row['mean_hit_rate']:.6f}."
        )

    lines.extend(
        [
            "",
            "## Alpha Signal",
            "",
            alpha_note,
            "",
            "## Interpretation",
            "",
            "- These results are preliminary because the current sample is only the saved local sample, not the full multi-ticker 60-day research set.",
            "- IC values are small, which is normal for short-horizon intraday signals and means the adaptive strategy should treat alpha as one input, not a standalone trading rule.",
            "- Signals based on spread, volume, volatility, and imbalance are OHLCV proxies, not true order book measurements.",
            "- Phase 4 onward should evaluate whether any weak signal value survives spread, impact, timing, and opportunity costs.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines))


def _strategy_schedule_summary(
    strategy_name: str,
    child_orders: pd.DataFrame,
    order_quantity: float,
    market_window: pd.DataFrame,
) -> dict:
    """Summarize one strategy schedule before transaction costs are modeled."""
    if child_orders.empty:
        return {
            "strategy": strategy_name,
            "child_orders": 0,
            "filled_quantity": 0.0,
            "fill_rate": 0.0,
            "min_child_quantity": 0.0,
            "max_child_quantity": 0.0,
            "max_participation": 0.0,
        }

    participation = (
        child_orders.set_index("timestamp")["quantity"]
        / market_window.loc[child_orders["timestamp"], "volume"]
    )
    filled_quantity = child_orders["quantity"].sum()
    return {
        "strategy": strategy_name,
        "child_orders": len(child_orders),
        "filled_quantity": filled_quantity,
        "fill_rate": filled_quantity / order_quantity,
        "min_child_quantity": child_orders["quantity"].min(),
        "max_child_quantity": child_orders["quantity"].max(),
        "max_participation": participation.max(),
    }


def _save_execution_grid_outputs(
    args: argparse.Namespace,
    grid_backtester: Backtester,
    results: pd.DataFrame,
    fills: pd.DataFrame,
) -> tuple[Path, Path, Path, Path, Path, pd.DataFrame]:
    """Save execution-grid fills, detailed TCA rows, and aggregate summaries."""
    summary_by_strategy = grid_backtester.summarize_by_strategy(results)
    summary_by_placement = grid_backtester.summarize_by_placement(results)
    summary_by_strategy_placement = grid_backtester.summarize_by_strategy_placement(results)

    fills_path = (
        Path(args.execution_grid_fills_output_csv)
        if args.execution_grid_fills_output_csv
        else _default_execution_grid_fills_output_path()
    )
    results_path = (
        Path(args.execution_grid_results_output_csv)
        if args.execution_grid_results_output_csv
        else _default_execution_grid_results_output_path()
    )
    strategy_path = (
        Path(args.execution_grid_summary_strategy_output_csv)
        if args.execution_grid_summary_strategy_output_csv
        else _default_execution_grid_summary_strategy_output_path()
    )
    placement_path = (
        Path(args.execution_grid_summary_placement_output_csv)
        if args.execution_grid_summary_placement_output_csv
        else _default_execution_grid_summary_placement_output_path()
    )
    strategy_placement_path = (
        Path(args.execution_grid_summary_strategy_placement_output_csv)
        if args.execution_grid_summary_strategy_placement_output_csv
        else _default_execution_grid_summary_strategy_placement_output_path()
    )

    for output_path, frame in [
        (fills_path, fills),
        (results_path, results),
        (strategy_path, summary_by_strategy),
        (placement_path, summary_by_placement),
        (strategy_placement_path, summary_by_strategy_placement),
    ]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)

    return (
        fills_path,
        results_path,
        strategy_path,
        placement_path,
        strategy_placement_path,
        summary_by_strategy_placement,
    )


def main() -> None:
    """Create the backtester configuration and print the current scaffold status."""
    args = parse_args()
    backtester = Backtester(tickers=DEFAULT_TICKERS)
    print("Smart Execution Backtester scaffold is ready.")
    print(f"Tickers: {', '.join(backtester.tickers)}")
    print(f"Data settings: period={backtester.period}, interval={backtester.interval}")

    if args.download_sample:
        # Phase 1 smoke path: touches Yahoo Finance, writes raw/processed CSVs,
        # and verifies the cleaned schema can be produced end to end.
        processed, raw_path, processed_path = load_and_save_intraday_data(
            ticker=args.ticker,
            period=args.period,
            interval=args.interval,
        )
        print(f"Downloaded {len(processed):,} cleaned bars for {args.ticker.upper()}.")
        print(f"Raw data: {raw_path}")
        print(f"Processed data: {processed_path}")
    elif args.download_tickers:
        # Multi-ticker download path. Each ticker is saved as its own raw and
        # processed CSV, which keeps downstream independent backtests explicit.
        rows = []
        for ticker in args.download_tickers:
            processed, raw_path, processed_path = load_and_save_intraday_data(
                ticker=ticker,
                period=args.period,
                interval=args.interval,
            )
            rows.append(
                {
                    "ticker": ticker.upper(),
                    "rows": len(processed),
                    "raw_path": raw_path,
                    "processed_path": processed_path,
                }
            )

        downloads = pd.DataFrame(rows)
        print(f"Downloaded {len(downloads):,} tickers.")
        print(downloads.to_string(index=False))
    elif args.feature_sample:
        # Phase 2 smoke path: stays offline by reading a processed CSV and then
        # validating the feature pipeline against saved sample data.
        input_path, data = _load_processed_csv_from_args(args)
        featured = add_microstructure_features(data)
        volume_curve = estimate_volume_curve(featured)

        non_null_alpha = featured["alpha_signal"].notna().sum()
        print(f"Loaded {len(featured):,} processed bars from {input_path}.")
        print(f"Added Phase 2 features. Non-null alpha_signal rows: {non_null_alpha:,}.")
        print(f"Estimated volume curve bars: {len(volume_curve):,}.")
    elif args.signal_sample:
        # Phase 3 smoke path: evaluates whether Phase 2 proxy features have
        # short-horizon predictive value before adaptive execution uses them.
        input_path, data = _load_processed_csv_from_args(args)
        featured = add_microstructure_features(data)
        signal_data = add_forward_returns(featured, DEFAULT_HORIZONS)
        results = evaluate_signals(signal_data)
        output_path = (
            Path(args.signal_output_csv)
            if args.signal_output_csv
            else _default_signal_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output_path, index=False)

        decay = signal_decay_table(results)
        decay_output_path = (
            Path(args.signal_decay_output_csv)
            if args.signal_decay_output_csv
            else _default_signal_decay_output_path(input_path)
        )
        decay_output_path.parent.mkdir(parents=True, exist_ok=True)
        decay.to_csv(decay_output_path, index=False)

        summary = signal_quality_summary(results)
        summary_output_path = (
            Path(args.signal_summary_output_csv)
            if args.signal_summary_output_csv
            else _default_signal_summary_output_path(input_path)
        )
        summary_output_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(summary_output_path, index=False)

        notes_output_path = (
            Path(args.signal_notes_output_md)
            if args.signal_notes_output_md
            else _default_signal_notes_output_path(input_path)
        )
        _write_signal_notes(notes_output_path, input_path, results, summary)

        ranked = results.sort_values(
            ["information_coefficient", "hit_rate"],
            ascending=False,
        )
        display_cols = [
            "signal",
            "horizon",
            "n_obs",
            "information_coefficient",
            "hit_rate",
            "decile_spread",
        ]

        print(f"Loaded {len(signal_data):,} processed bars from {input_path}.")
        print(f"Evaluated {len(results):,} signal-horizon combinations.")
        print(f"Saved signal evaluation results to {output_path}.")
        print(f"Saved signal decay results to {decay_output_path}.")
        print(f"Saved signal summary results to {summary_output_path}.")
        print(f"Saved signal notes to {notes_output_path}.")
        print(ranked[display_cols].head(12).to_string(index=False))
    elif args.orders_sample:
        # Phase 4 smoke path: creates parent orders from available market dates.
        # Strategies in Phase 5 will all consume this same order set.
        input_path, data = _load_processed_csv_from_args(args)
        orders = generate_parent_orders(data)
        orders_frame = parent_orders_to_frame(orders)

        # Saving the order grid makes it easier to audit the simulation demand
        # before comparing TWAP/VWAP/POV/adaptive execution schedules.
        output_path = (
            Path(args.orders_output_csv)
            if args.orders_output_csv
            else _default_orders_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        orders_frame.to_csv(output_path, index=False)

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Generated {len(orders):,} parent orders.")
        print(f"Saved parent orders to {output_path}.")
        print(orders_frame.head(12).to_string(index=False))
    elif args.twap_sample:
        # Phase 5 TWAP smoke path only. It intentionally runs one parent order so
        # the child schedule is easy to inspect before other strategies exist.
        input_path, data = _load_processed_csv_from_args(args)
        order = generate_parent_orders(data, max_orders_per_ticker=1)[0]
        child_orders = TWAPStrategy().generate_child_orders(order, data)
        output_path = (
            Path(args.twap_output_csv)
            if args.twap_output_csv
            else _default_twap_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        child_orders.to_csv(output_path, index=False)

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Generated TWAP schedule for parent order {order.order_id}.")
        print(f"Child orders: {len(child_orders):,}.")
        print(f"Parent quantity: {order.quantity:,.6f}.")
        print(f"Child quantity sum: {child_orders['quantity'].sum():,.6f}.")
        print(f"Saved TWAP child orders to {output_path}.")
        print(child_orders.head(8).to_string(index=False))
    elif args.vwap_sample:
        # Phase 5 VWAP smoke path only. It uses the historical volume curve from
        # Phase 2 and saves one child schedule for inspection.
        input_path, data = _load_processed_csv_from_args(args)
        order = generate_parent_orders(data, max_orders_per_ticker=1)[0]
        child_orders = VWAPStrategy().generate_child_orders(order, data)
        output_path = (
            Path(args.vwap_output_csv)
            if args.vwap_output_csv
            else _default_vwap_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        child_orders.to_csv(output_path, index=False)

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Generated VWAP schedule for parent order {order.order_id}.")
        print(f"Child orders: {len(child_orders):,}.")
        print(f"Parent quantity: {order.quantity:,.6f}.")
        print(f"Child quantity sum: {child_orders['quantity'].sum():,.6f}.")
        print(f"Min child quantity: {child_orders['quantity'].min():,.6f}.")
        print(f"Max child quantity: {child_orders['quantity'].max():,.6f}.")
        print(f"Saved VWAP child orders to {output_path}.")
        print(child_orders.head(8).to_string(index=False))
    elif args.pov_sample:
        # Phase 5 POV smoke path only. POV trades as a capped share of realized
        # bar volume, so fill rate is an important validation output.
        input_path, data = _load_processed_csv_from_args(args)
        order = generate_parent_orders(data, max_orders_per_ticker=1)[0]
        strategy = POVStrategy()
        child_orders = strategy.generate_child_orders(order, data)
        output_path = (
            Path(args.pov_output_csv)
            if args.pov_output_csv
            else _default_pov_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        child_orders.to_csv(output_path, index=False)

        market_window = strategy.market_window(order, data)
        participation = (
            child_orders.set_index("timestamp")["quantity"]
            / market_window.loc[child_orders["timestamp"], "volume"]
        )

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Generated POV schedule for parent order {order.order_id}.")
        print(f"Child orders: {len(child_orders):,}.")
        print(f"Parent quantity: {order.quantity:,.6f}.")
        print(f"Child quantity sum: {child_orders['quantity'].sum():,.6f}.")
        print(f"Fill rate: {child_orders['quantity'].sum() / order.quantity:,.6f}.")
        print(f"Max participation: {participation.max():,.6f}.")
        print(f"Saved POV child orders to {output_path}.")
        print(child_orders.head(8).to_string(index=False))
    elif args.adaptive_sample:
        # Phase 5 Adaptive smoke path only. Adaptive needs Phase 2 features, so
        # this path enriches the processed data before generating child orders.
        input_path, data = _load_processed_csv_from_args(args)
        featured = add_microstructure_features(data)
        order = generate_parent_orders(featured, max_orders_per_ticker=1)[0]
        strategy = AdaptiveStrategy()
        child_orders = strategy.generate_child_orders(order, featured)
        output_path = (
            Path(args.adaptive_output_csv)
            if args.adaptive_output_csv
            else _default_adaptive_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        child_orders.to_csv(output_path, index=False)

        market_window = strategy.market_window(order, featured)
        participation = (
            child_orders.set_index("timestamp")["quantity"]
            / market_window.loc[child_orders["timestamp"], "volume"]
        )

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Generated Adaptive schedule for parent order {order.order_id}.")
        print(f"Child orders: {len(child_orders):,}.")
        print(f"Parent quantity: {order.quantity:,.6f}.")
        print(f"Child quantity sum: {child_orders['quantity'].sum():,.6f}.")
        print(f"Fill rate: {child_orders['quantity'].sum() / order.quantity:,.6f}.")
        print(f"Max participation: {participation.max():,.6f}.")
        print(f"Saved Adaptive child orders to {output_path}.")
        print(child_orders.head(8).to_string(index=False))
    elif args.strategy_compare_sample:
        # Phase 5 comparison path: same parent order, same market data, all
        # implemented strategies. This compares schedules only, not TCA quality.
        input_path, data = _load_processed_csv_from_args(args)
        featured = add_microstructure_features(data)
        order = generate_parent_orders(featured, max_orders_per_ticker=1)[0]
        strategies = [TWAPStrategy(), VWAPStrategy(), POVStrategy(), AdaptiveStrategy()]
        rows = []

        for strategy in strategies:
            strategy_data = featured if isinstance(strategy, AdaptiveStrategy) else data
            child_orders = strategy.generate_child_orders(order, strategy_data)
            market_window = strategy.market_window(order, strategy_data)
            rows.append(
                _strategy_schedule_summary(
                    strategy_name=strategy.name,
                    child_orders=child_orders,
                    order_quantity=order.quantity,
                    market_window=market_window,
                )
            )

        comparison = pd.DataFrame(rows)
        output_path = (
            Path(args.strategy_compare_output_csv)
            if args.strategy_compare_output_csv
            else _default_strategy_compare_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(output_path, index=False)

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Compared schedules for parent order {order.order_id}.")
        print(f"Saved strategy schedule comparison to {output_path}.")
        print(comparison.to_string(index=False))
    elif args.tca_sample:
        # Phase 6 TCA smoke path: run one TWAP schedule through the synthetic
        # bid/ask and impact model. Full parent-order metrics are Phase 7.
        input_path, data = _load_processed_csv_from_args(args)
        featured = add_microstructure_features(data)
        order = generate_parent_orders(featured, max_orders_per_ticker=1)[0]
        child_orders = TWAPStrategy().generate_child_orders(order, featured)
        enriched_fills = apply_transaction_cost_model(child_orders, featured)
        output_path = (
            Path(args.tca_output_csv)
            if args.tca_output_csv
            else _default_tca_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        enriched_fills.to_csv(output_path, index=False)

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Applied TCA model to TWAP parent order {order.order_id}.")
        print(f"Enriched fills: {len(enriched_fills):,}.")
        print(f"Average fill price: {enriched_fills['fill_price'].mean():,.6f}.")
        print(f"Average spread cost: {enriched_fills['spread_cost'].mean():,.6f}.")
        print(f"Average impact cost: {enriched_fills['impact_cost'].mean():,.6f}.")
        print(f"Saved TCA-enriched fills to {output_path}.")
        print(
            enriched_fills[
                [
                    "timestamp",
                    "side",
                    "strategy",
                    "quantity",
                    "mid_price",
                    "synthetic_bid",
                    "synthetic_ask",
                    "fill_price",
                    "spread_cost",
                    "impact_cost",
                ]
            ]
            .head(8)
            .to_string(index=False)
        )
    elif args.tca_metrics_sample:
        # Phase 7 smoke path: compute one parent-order-level TCA result row.
        # Multi-strategy and multi-order aggregation comes later in backtesting.
        input_path, data = _load_processed_csv_from_args(args)
        featured = add_microstructure_features(data)
        order = generate_parent_orders(featured, max_orders_per_ticker=1)[0]
        child_orders = TWAPStrategy().generate_child_orders(order, featured)
        enriched_fills = apply_transaction_cost_model(child_orders, featured)
        metrics = compute_tca_metrics(order, enriched_fills, featured)
        metrics_frame = pd.DataFrame([metrics])
        output_path = (
            Path(args.tca_metrics_output_csv)
            if args.tca_metrics_output_csv
            else _default_tca_metrics_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_frame.to_csv(output_path, index=False)

        print(f"Loaded {len(data):,} processed bars from {input_path}.")
        print(f"Computed TCA metrics for TWAP parent order {order.order_id}.")
        print(f"Saved TCA metrics to {output_path}.")
        print(metrics_frame.to_string(index=False))
    elif args.backtest_sample:
        # Phase 8 smoke path: one processed CSV, limited parent orders, all
        # registered strategies, one TCA result row per order/strategy pair.
        input_path, data = _load_processed_csv_from_args(args)
        sample_backtester = Backtester(
            tickers=backtester.tickers,
            period=backtester.period,
            interval=backtester.interval,
            max_orders_per_ticker=1,
        )
        results = sample_backtester.run_single_ticker_data(data)
        results_path = (
            Path(args.backtest_results_output_csv)
            if args.backtest_results_output_csv
            else _default_backtest_results_output_path(input_path)
        )
        summary_path = (
            Path(args.backtest_summary_output_csv)
            if args.backtest_summary_output_csv
            else _default_backtest_summary_output_path(input_path)
        )
        saved_results_path, saved_summary_path = sample_backtester.save_results(
            results,
            results_path,
            summary_path,
        )
        summary = sample_backtester.summarize_by_strategy(results)

        print(f"Ran sample backtest from {input_path}.")
        print(f"Detailed result rows: {len(results):,}.")
        print(f"Saved detailed results to {saved_results_path}.")
        print(f"Saved strategy summary to {saved_summary_path}.")
        print(summary.to_string(index=False))
    elif args.alignment_report:
        # Multi-ticker data quality path: report timestamp coverage before
        # running cross-ticker comparisons.
        data = _load_processed_csvs_from_args(args)
        prepared = add_microstructure_features(data)
        report = backtester.alignment_report(prepared)
        output_path = (
            Path(args.alignment_output_csv)
            if args.alignment_output_csv
            else _default_alignment_output_path()
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(output_path, index=False)

        print(f"Loaded {len(prepared):,} rows across {prepared['ticker'].nunique():,} tickers.")
        print(f"Saved alignment report to {output_path}.")
        print(report.to_string(index=False))
    elif args.backtest_multi:
        # Independent multi-ticker path: each ticker CSV is backtested on its own,
        # then detailed TCA rows are concatenated for cross-ticker summaries.
        input_csvs = _require_input_csvs(args)
        multi_backtester = Backtester(
            tickers=backtester.tickers,
            period=backtester.period,
            interval=backtester.interval,
            max_orders_per_ticker=args.max_orders_per_ticker,
        )

        if args.start_date or args.start_time:
            frames = []
            for input_csv in input_csvs:
                _, data = _load_processed_csv(
                    input_csv=input_csv,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    start_time=args.start_time,
                    end_time=args.end_time,
                )
                result = multi_backtester.run_single_ticker_data(data)
                result["source_csv"] = input_csv
                frames.append(result)
            results = pd.concat(frames, ignore_index=True)
        else:
            results = multi_backtester.run_multiple_csvs(input_csvs)

        summary_by_strategy = multi_backtester.summarize_by_strategy(results)
        summary_by_ticker = multi_backtester.summarize_by_ticker(results)
        summary_by_ticker_strategy = multi_backtester.summarize_by_ticker_strategy(results)

        results_path = (
            Path(args.backtest_multi_results_output_csv)
            if args.backtest_multi_results_output_csv
            else _default_backtest_multi_results_output_path()
        )
        strategy_path = (
            Path(args.backtest_multi_summary_strategy_output_csv)
            if args.backtest_multi_summary_strategy_output_csv
            else _default_backtest_multi_summary_strategy_output_path()
        )
        ticker_path = (
            Path(args.backtest_multi_summary_ticker_output_csv)
            if args.backtest_multi_summary_ticker_output_csv
            else _default_backtest_multi_summary_ticker_output_path()
        )
        ticker_strategy_path = (
            Path(args.backtest_multi_summary_ticker_strategy_output_csv)
            if args.backtest_multi_summary_ticker_strategy_output_csv
            else _default_backtest_multi_summary_ticker_strategy_output_path()
        )

        for output_path, frame in [
            (results_path, results),
            (strategy_path, summary_by_strategy),
            (ticker_path, summary_by_ticker),
            (ticker_strategy_path, summary_by_ticker_strategy),
        ]:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(output_path, index=False)

        print(f"Ran independent multi-CSV backtest for {len(input_csvs):,} input files.")
        print(f"Detailed result rows: {len(results):,}.")
        print(f"Saved detailed results to {results_path}.")
        print(f"Saved strategy summary to {strategy_path}.")
        print(f"Saved ticker summary to {ticker_path}.")
        print(f"Saved ticker-strategy summary to {ticker_strategy_path}.")
        print(summary_by_ticker_strategy.to_string(index=False))
    elif args.execution_tape:
        # Multi-ticker execution tape path: save all generated child orders and a
        # timestamp-level activity summary. This still uses independent parent
        # order generation per ticker; it does not model cross-asset impact.
        input_csvs = _require_input_csvs(args)
        tape_backtester = Backtester(
            tickers=backtester.tickers,
            period=backtester.period,
            interval=backtester.interval,
            max_orders_per_ticker=args.max_orders_per_ticker,
        )

        if args.start_date or args.start_time:
            tape_parts = []
            for input_csv in input_csvs:
                _, data = _load_processed_csv(
                    input_csv=input_csv,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    start_time=args.start_time,
                    end_time=args.end_time,
                )
                tape = tape_backtester.execution_tape_for_data(data)
                tape["source_csv"] = input_csv
                tape_parts.append(tape)
            execution_tape = pd.concat(tape_parts, ignore_index=True)
        else:
            execution_tape = tape_backtester.execution_tape_for_csvs(input_csvs)

        execution_summary = tape_backtester.summarize_execution_by_timestamp(execution_tape)
        tape_path = (
            Path(args.execution_tape_output_csv)
            if args.execution_tape_output_csv
            else _default_execution_tape_output_path()
        )
        summary_path = (
            Path(args.execution_summary_output_csv)
            if args.execution_summary_output_csv
            else _default_execution_summary_output_path()
        )

        tape_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        execution_tape.to_csv(tape_path, index=False)
        execution_summary.to_csv(summary_path, index=False)

        print(f"Generated execution tape for {len(input_csvs):,} input files.")
        print(f"Child-order rows: {len(execution_tape):,}.")
        print(f"Timestamp summary rows: {len(execution_summary):,}.")
        print(f"Saved execution tape to {tape_path}.")
        print(f"Saved timestamp summary to {summary_path}.")
        print(execution_summary.head(12).to_string(index=False))
    elif args.execution_grid_sample:
        # Placement-grid path: compare the existing schedule algorithms against
        # market, limit, pegged, and adaptive placement behavior.
        input_path, data = _load_processed_csv_from_args(args)
        grid_backtester = Backtester(
            tickers=backtester.tickers,
            period=backtester.period,
            interval=backtester.interval,
            placement_styles=args.placement_styles or PLACEMENT_STYLES.copy(),
            fill_model=args.fill_model,
            random_seed=args.random_seed,
            max_orders_per_ticker=args.max_orders_per_ticker,
        )
        results, fills = grid_backtester.run_execution_grid_data(data)
        (
            fills_path,
            results_path,
            strategy_path,
            placement_path,
            strategy_placement_path,
            summary_by_strategy_placement,
        ) = _save_execution_grid_outputs(args, grid_backtester, results, fills)

        print(f"Ran execution grid from {input_path}.")
        print(f"Placement styles: {', '.join(grid_backtester.placement_styles)}")
        print(f"Detailed result rows: {len(results):,}.")
        print(f"Simulated fill rows: {len(fills):,}.")
        print(f"Saved simulated fills to {fills_path}.")
        print(f"Saved detailed results to {results_path}.")
        print(f"Saved strategy summary to {strategy_path}.")
        print(f"Saved placement summary to {placement_path}.")
        print(f"Saved strategy-placement summary to {strategy_placement_path}.")
        print(summary_by_strategy_placement.to_string(index=False))
    elif args.execution_grid_multi:
        # Multi-ticker execution grid. Each ticker is still simulated
        # independently, then results are combined for cross-ticker comparison.
        input_csvs = _require_input_csvs(args)
        grid_backtester = Backtester(
            tickers=backtester.tickers,
            period=backtester.period,
            interval=backtester.interval,
            placement_styles=args.placement_styles or PLACEMENT_STYLES.copy(),
            fill_model=args.fill_model,
            random_seed=args.random_seed,
            max_orders_per_ticker=args.max_orders_per_ticker,
        )

        if args.start_date or args.start_time:
            result_parts = []
            fill_parts = []
            for input_csv in input_csvs:
                _, data = _load_processed_csv(
                    input_csv=input_csv,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    start_time=args.start_time,
                    end_time=args.end_time,
                )
                results, fills = grid_backtester.run_execution_grid_data(data)
                results["source_csv"] = input_csv
                fills["source_csv"] = input_csv
                result_parts.append(results)
                fill_parts.append(fills)
            grid_results = pd.concat(result_parts, ignore_index=True)
            grid_fills = pd.concat(fill_parts, ignore_index=True)
        else:
            grid_results, grid_fills = grid_backtester.run_execution_grid_csvs(input_csvs)

        (
            fills_path,
            results_path,
            strategy_path,
            placement_path,
            strategy_placement_path,
            summary_by_strategy_placement,
        ) = _save_execution_grid_outputs(args, grid_backtester, grid_results, grid_fills)

        print(f"Ran independent execution grids for {len(input_csvs):,} input files.")
        print(f"Placement styles: {', '.join(grid_backtester.placement_styles)}")
        print(f"Detailed result rows: {len(grid_results):,}.")
        print(f"Simulated fill rows: {len(grid_fills):,}.")
        print(f"Saved simulated fills to {fills_path}.")
        print(f"Saved detailed results to {results_path}.")
        print(f"Saved strategy summary to {strategy_path}.")
        print(f"Saved placement summary to {placement_path}.")
        print(f"Saved strategy-placement summary to {strategy_placement_path}.")
        print(summary_by_strategy_placement.to_string(index=False))
    elif args.rl_backtest_sample:
        # Adaptive Ensemble RL path: compare the selected RL policy against the
        # standard baseline strategies on the same generated parent orders.
        input_path, data = _load_processed_csv_from_args(args)
        policy = _rl_policy_from_args(args)
        results = run_rl_backtest_data(
            data=data,
            policy=policy,
            fill_model=args.fill_model,
            max_orders_per_ticker=args.max_orders_per_ticker,
            include_baselines=True,
        )
        output_path = (
            Path(args.rl_backtest_output_csv)
            if args.rl_backtest_output_csv
            else _default_rl_backtest_output_path(input_path)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output_path, index=False)

        print(f"Ran RL backtest from {input_path}.")
        print(f"RL policy: {args.rl_policy}.")
        print(f"Fill model: {args.fill_model}.")
        print(f"Result rows: {len(results):,}.")
        print(f"Saved RL backtest results to {output_path}.")
        display_cols = [
            "strategy",
            "fill_rate",
            "implementation_shortfall_bps",
            "vwap_slippage_bps",
            "opportunity_cost_bps",
        ]
        print(results[display_cols].to_string(index=False))
    elif args.rl_train_q:
        # Tabular Q-learning path: build one environment per generated parent
        # order and save the resulting Q-table for later qtable-policy runs.
        input_path, data = _load_processed_csv_from_args(args)
        envs = build_training_envs(
            data=data,
            fill_model=args.fill_model,
            max_orders_per_ticker=args.max_orders_per_ticker,
        )
        q_table = train_q_policy(
            envs=envs,
            episodes=args.q_episodes,
            epsilon=args.q_epsilon,
            alpha=args.q_alpha,
            gamma=args.q_gamma,
            seed=args.random_seed,
        )
        output_path = save_q_table(q_table, args.q_table_path)

        print(f"Trained tabular Q policy from {input_path}.")
        print(f"Training environments: {len(envs):,}.")
        print(f"Episodes: {args.q_episodes:,}.")
        print(f"State buckets learned: {len(q_table):,}.")
        print(f"Saved Q-table to {output_path}.")
    else:
        print("Phase 1 data loader is available. Use --download-sample to fetch a ticker.")
        print("Phase 2 feature engineering is available. Use --feature-sample to test a CSV.")
        print("Phase 3 signal evaluation is available. Use --signal-sample to test signals.")
        print("Phase 4 parent order generation is available. Use --orders-sample to test orders.")
        print("Phase 5 TWAP generation is available. Use --twap-sample to test TWAP.")
        print("Phase 5 VWAP generation is available. Use --vwap-sample to test VWAP.")
        print("Phase 5 POV generation is available. Use --pov-sample to test POV.")
        print("Phase 5 Adaptive generation is available. Use --adaptive-sample to test Adaptive.")
        print("Phase 5 strategy comparison is available. Use --strategy-compare-sample.")
        print("Phase 6 TCA enrichment is available. Use --tca-sample.")
        print("Phase 7 TCA metrics are available. Use --tca-metrics-sample.")
        print("Phase 8 sample backtest is available. Use --backtest-sample.")
        print("Multi-ticker alignment report is available. Use --alignment-report --input-csvs ...")
        print("Independent multi-ticker backtest is available. Use --backtest-multi --input-csvs ...")
        print("Multi-ticker download is available. Use --download-tickers SPY QQQ ...")
        print("Multi-ticker execution tape is available. Use --execution-tape --input-csvs ...")
        print("Execution-grid simulation is available. Use --execution-grid-sample.")
        print("Adaptive Ensemble RL backtest is available. Use --rl-backtest-sample.")
        print("Adaptive Ensemble RL Q-training is available. Use --rl-train-q.")


if __name__ == "__main__":
    main()
