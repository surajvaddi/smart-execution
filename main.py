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
from src.execution import generate_parent_orders, parent_orders_to_frame
from src.signals import (
    DEFAULT_HORIZONS,
    add_forward_returns,
    evaluate_signals,
    signal_decay_table,
    signal_quality_summary,
)
from src.strategies import TWAPStrategy, VWAPStrategy


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
        "--input-csv",
        default="data/processed/SPY_5d_5m.csv",
        help="Processed CSV to use with --feature-sample.",
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
    return parser.parse_args()


def _load_processed_csv(input_csv: str) -> tuple[Path, pd.DataFrame]:
    """Load a processed data-loader CSV for offline phase smoke checks."""
    input_path = Path(input_csv)
    data = pd.read_csv(input_path, index_col=0, parse_dates=True)
    return input_path, data


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
    elif args.feature_sample:
        # Phase 2 smoke path: stays offline by reading a processed CSV and then
        # validating the feature pipeline against saved sample data.
        input_path, data = _load_processed_csv(args.input_csv)
        featured = add_microstructure_features(data)
        volume_curve = estimate_volume_curve(featured)

        non_null_alpha = featured["alpha_signal"].notna().sum()
        print(f"Loaded {len(featured):,} processed bars from {input_path}.")
        print(f"Added Phase 2 features. Non-null alpha_signal rows: {non_null_alpha:,}.")
        print(f"Estimated volume curve bars: {len(volume_curve):,}.")
    elif args.signal_sample:
        # Phase 3 smoke path: evaluates whether Phase 2 proxy features have
        # short-horizon predictive value before adaptive execution uses them.
        input_path, data = _load_processed_csv(args.input_csv)
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
        input_path, data = _load_processed_csv(args.input_csv)
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
        input_path, data = _load_processed_csv(args.input_csv)
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
        input_path, data = _load_processed_csv(args.input_csv)
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
    else:
        print("Phase 1 data loader is available. Use --download-sample to fetch a ticker.")
        print("Phase 2 feature engineering is available. Use --feature-sample to test a CSV.")
        print("Phase 3 signal evaluation is available. Use --signal-sample to test signals.")
        print("Phase 4 parent order generation is available. Use --orders-sample to test orders.")
        print("Phase 5 TWAP generation is available. Use --twap-sample to test TWAP.")
        print("Phase 5 VWAP generation is available. Use --vwap-sample to test VWAP.")


if __name__ == "__main__":
    main()
