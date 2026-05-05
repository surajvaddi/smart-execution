"""Entry point for the smart execution backtester."""

from __future__ import annotations

from src.backtester import Backtester


DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


def main() -> None:
    """Create the backtester configuration and print the current scaffold status."""
    backtester = Backtester(tickers=DEFAULT_TICKERS)
    print("Smart Execution Backtester scaffold is ready.")
    print(f"Tickers: {', '.join(backtester.tickers)}")
    print(f"Data settings: period={backtester.period}, interval={backtester.interval}")
    print("Next implementation step: Phase 1 data loading.")


if __name__ == "__main__":
    main()
