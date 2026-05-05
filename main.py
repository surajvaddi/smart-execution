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
from src.signals import DEFAULT_HORIZONS, add_forward_returns, evaluate_signals, signal_decay_table


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
        print(ranked[display_cols].head(12).to_string(index=False))
    else:
        print("Phase 1 data loader is available. Use --download-sample to fetch a ticker.")
        print("Phase 2 feature engineering is available. Use --feature-sample to test a CSV.")
        print("Phase 3 signal evaluation is available. Use --signal-sample to test signals.")


if __name__ == "__main__":
    main()
