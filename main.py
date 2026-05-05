"""Entry point for the smart execution backtester."""

from __future__ import annotations

import argparse

from src.backtester import Backtester
from src.data_loader import load_and_save_intraday_data


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
    return parser.parse_args()


def main() -> None:
    """Create the backtester configuration and print the current scaffold status."""
    args = parse_args()
    backtester = Backtester(tickers=DEFAULT_TICKERS)
    print("Smart Execution Backtester scaffold is ready.")
    print(f"Tickers: {', '.join(backtester.tickers)}")
    print(f"Data settings: period={backtester.period}, interval={backtester.interval}")

    if args.download_sample:
        processed, raw_path, processed_path = load_and_save_intraday_data(
            ticker=args.ticker,
            period=args.period,
            interval=args.interval,
        )
        print(f"Downloaded {len(processed):,} cleaned bars for {args.ticker.upper()}.")
        print(f"Raw data: {raw_path}")
        print(f"Processed data: {processed_path}")
    else:
        print("Phase 1 data loader is available. Use --download-sample to fetch a ticker.")


if __name__ == "__main__":
    main()
