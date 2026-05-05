"""OHLCV-derived market microstructure proxy features."""

from __future__ import annotations

import numpy as np
import pandas as pd


BASE_COLUMNS = ["open", "high", "low", "close", "volume", "returns", "ticker"]

FEATURE_COLUMNS = [
    "spread_proxy",
    "signed_volume",
    "ofi_proxy",
    "rolling_vol",
    "volume_zscore",
    "momentum_3",
    "reversal_3",
    "liquidity_score",
    "alpha_signal",
]


def validate_base_columns(df: pd.DataFrame) -> None:
    """Validate that the input data contains the cleaned data-loader schema."""
    missing = [col for col in BASE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required base columns for feature engineering: {missing}")


def validate_feature_columns(df: pd.DataFrame) -> None:
    """Validate that all Phase 2 feature columns were created."""
    missing = [col for col in FEATURE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    invalid_spread = df["spread_proxy"].dropna() < 0
    if invalid_spread.any():
        raise ValueError("spread_proxy must be non-negative.")

    invalid_liquidity = df["liquidity_score"].dropna().replace([np.inf, -np.inf], np.nan).isna()
    if invalid_liquidity.any():
        raise ValueError("liquidity_score contains infinite values.")


def estimate_volume_curve(df: pd.DataFrame) -> pd.Series:
    """Estimate average intraday volume share by bar index."""
    if "bar_index" not in df.columns:
        raise ValueError("Missing required column for volume curve: bar_index")
    if "volume" not in df.columns:
        raise ValueError("Missing required column for volume curve: volume")

    volume_by_bar = df.groupby("bar_index")["volume"].mean()
    total_volume = volume_by_bar.sum()
    if total_volume <= 0:
        raise ValueError("Cannot estimate volume curve from non-positive volume.")

    volume_curve = volume_by_bar / total_volume
    volume_curve.name = "expected_volume_share"
    return volume_curve


def add_microstructure_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add spread, volume, imbalance, volatility, liquidity, and momentum proxies."""
    validate_base_columns(df)
    featured = (
        df.copy()
        .groupby("ticker", group_keys=False)
        .apply(_add_features_for_ticker)
    )
    validate_feature_columns(featured)
    return featured



def _add_features_for_ticker(df: pd.DataFrame) -> pd.DataFrame:
    """Add feature columns for one ticker's time-ordered bars."""
    out = df.sort_index().copy()

    out["spread_proxy"] = (out["high"] - out["low"]) / out["close"]
    out["signed_volume"] = np.sign(out["close"] - out["open"]) * out["volume"]

    rolling_volume = out["volume"].rolling(5, min_periods=5).sum()
    out["ofi_proxy"] = out["signed_volume"].rolling(5, min_periods=5).sum() / rolling_volume

    out["rolling_vol"] = out["returns"].rolling(12, min_periods=12).std()
    out["volume_zscore"] = (
        out["volume"] - out["volume"].rolling(20, min_periods=20).mean()
    ) / out["volume"].rolling(20, min_periods=20).std()

    out["momentum_3"] = out["close"].pct_change(3)
    out["reversal_3"] = -out["momentum_3"]

    out["liquidity_score"] = (
        out["volume"].rank(pct=True)
        - out["spread_proxy"].rank(pct=True)
        - out["rolling_vol"].rank(pct=True)
    )

    out["alpha_signal"] = (
        0.40 * out["ofi_proxy"].rank(pct=True)
        + 0.25 * out["momentum_3"].rank(pct=True)
        + 0.20 * out["volume_zscore"].rank(pct=True)
        + 0.15 * out["liquidity_score"].rank(pct=True)
    )
    out["alpha_signal"] = out["alpha_signal"] - out["alpha_signal"].mean()

    return out
