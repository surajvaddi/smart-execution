"""Data loading utilities for intraday Yahoo Finance OHLCV data."""

from __future__ import annotations

import pandas as pd


def load_intraday_data(ticker: str, period: str = "60d", interval: str = "5m") -> pd.DataFrame:
    """Download and clean intraday OHLCV data from Yahoo Finance."""
    raise NotImplementedError("Yahoo Finance data loading will be implemented in Phase 1.")
