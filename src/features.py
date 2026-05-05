"""OHLCV-derived market microstructure proxy features."""

from __future__ import annotations

import pandas as pd


def add_microstructure_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add spread, volume, imbalance, volatility, liquidity, and momentum proxies."""
    raise NotImplementedError("Feature engineering will be implemented in Phase 2.")
