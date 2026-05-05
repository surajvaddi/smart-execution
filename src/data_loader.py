"""Data loading utilities for intraday Yahoo Finance OHLCV data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "returns",
    "dollar_volume",
    "date",
    "time",
    "bar_index",
    "ticker",
]

RAW_DATA_DIR = Path("data/raw")
PROCESSED_DATA_DIR = Path("data/processed")


def _get_yfinance():
    """Import yfinance only when a download is requested."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - exercised only before dependencies are installed.
        raise ImportError("Install project dependencies with `pip install -r requirements.txt`.") from exc
    return yf


def load_intraday_data(ticker: str, period: str = "60d", interval: str = "5m") -> pd.DataFrame:
    """Download and clean intraday OHLCV data from Yahoo Finance."""
    raw = download_raw_intraday_data(ticker=ticker, period=period, interval=interval)
    return clean_intraday_data(raw, ticker)


def download_raw_intraday_data(
    ticker: str,
    period: str = "60d",
    interval: str = "5m",
) -> pd.DataFrame:
    """Download raw intraday Yahoo Finance data without project-specific cleaning."""
    yf = _get_yfinance()
    return yf.download(
        tickers=ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="column",
    )


def clean_intraday_data(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalize Yahoo Finance OHLCV data into the project's canonical schema."""
    if raw.empty:
        raise ValueError(f"No intraday data returned for {ticker}.")

    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    rename_map = {
        "adj_close": "adj_close",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    df = df.rename(columns=rename_map)

    ohlcv_cols = ["open", "high", "low", "close", "volume"]
    missing = [col for col in ohlcv_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required Yahoo columns for {ticker}: {missing}")

    df = df[ohlcv_cols].dropna(subset=["open", "high", "low", "close"])
    df = df[df["volume"].fillna(0) > 0]
    if df.empty:
        raise ValueError(f"No usable intraday bars after cleaning for {ticker}.")

    df = df.sort_index()
    df["returns"] = df["close"].pct_change()
    df["dollar_volume"] = df["close"] * df["volume"]
    df["date"] = df.index.date
    df["time"] = df.index.time
    df["bar_index"] = df.groupby("date").cumcount()
    df["ticker"] = ticker.upper()

    return df[REQUIRED_COLUMNS]


def save_intraday_data(
    df: pd.DataFrame,
    ticker: str,
    period: str,
    interval: str,
    data_dir: Path,
) -> Path:
    """Save intraday data to CSV and return the output path."""
    data_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{ticker.upper()}_{period}_{interval}.csv"
    output_path = data_dir / filename
    df.to_csv(output_path, index=True)
    return output_path


def load_and_save_intraday_data(
    ticker: str,
    period: str = "60d",
    interval: str = "5m",
) -> tuple[pd.DataFrame, Path, Path]:
    """Download, clean, and save raw and processed intraday data."""
    raw = download_raw_intraday_data(ticker=ticker, period=period, interval=interval)
    processed = clean_intraday_data(raw, ticker)
    raw_path = save_intraday_data(raw, ticker, period, interval, RAW_DATA_DIR)
    processed_path = save_intraday_data(processed, ticker, period, interval, PROCESSED_DATA_DIR)
    return processed, raw_path, processed_path
