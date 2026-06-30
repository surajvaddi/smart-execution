"""OHLCV-derived market microstructure proxy features.

These features approximate microstructure concepts from bar data. They should
not be interpreted as true spread, order flow, depth, or liquidity measures
because Yahoo Finance does not provide limit order book data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.microstructure_proxies import (
    compute_hidden_liquidity_proxy,
    compute_passive_fill_risk_proxy,
    compute_queue_pressure_proxy,
)


# Feature engineering starts from the cleaned data-loader schema. `ticker` is
# required so rolling calculations can be isolated per symbol.
BASE_COLUMNS = ["open", "high", "low", "close", "volume", "returns", "ticker"]

# Centralizing expected feature names gives later phases a single validation
# point before they depend on signals or execution controls.
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

EXTENDED_PROXY_COLUMNS = [
    "queue_pressure_proxy",
    "hidden_liquidity_proxy",
    "passive_fill_risk_proxy",
]


def attach_alpha_model_score(
    data: pd.DataFrame,
    scores: pd.Series | list[float] | np.ndarray,
    score_column: str = "alpha_model_score",
) -> pd.DataFrame:
    """Attach model scores to a feature frame without replacing heuristic alpha_signal."""
    if len(scores) != len(data):
        raise ValueError("scores length must match the number of rows in data.")

    enriched = data.copy()
    enriched[score_column] = list(scores)
    return enriched


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

    # A high-low range can be zero, but it should never be negative if the input
    # OHLC bars are sane.
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

    # This is the historical schedule a VWAP strategy will follow later. It is
    # based on average volume by intraday bar, not future realized volume.
    volume_by_bar = df.groupby("bar_index")["volume"].mean()
    total_volume = volume_by_bar.sum()
    if total_volume <= 0:
        raise ValueError("Cannot estimate volume curve from non-positive volume.")

    volume_curve = volume_by_bar / total_volume
    volume_curve.name = "expected_volume_share"
    return volume_curve


def add_microstructure_features(
    df: pd.DataFrame,
    include_extended_proxies: bool = False,
) -> pd.DataFrame:
    """Add spread, volume, imbalance, volatility, liquidity, and momentum proxies."""
    validate_base_columns(df)
    # Grouping by ticker prevents rolling windows, ranks, and returns from
    # accidentally blending symbols when multi-ticker data is concatenated.
    featured = (
        df.copy()
        .groupby("ticker", group_keys=False)
        .apply(_add_features_for_ticker, include_extended_proxies=include_extended_proxies)
    )
    validate_feature_columns(featured)
    if include_extended_proxies:
        missing = [col for col in EXTENDED_PROXY_COLUMNS if col not in featured.columns]
        if missing:
            raise ValueError(f"Missing required extended proxy columns: {missing}")
    return featured



def _add_features_for_ticker(
    df: pd.DataFrame,
    include_extended_proxies: bool = False,
) -> pd.DataFrame:
    """Add feature columns for one ticker's time-ordered bars."""
    out = df.sort_index().copy()

    # High-low range is a crude proxy for trading cost and uncertainty within
    # the bar. It is not a quoted bid-ask spread.
    out["spread_proxy"] = (out["high"] - out["low"]) / out["close"]

    # Bar direction is used as an approximate trade-sign classifier because
    # Yahoo Finance does not expose buyer/seller initiated volume.
    out["signed_volume"] = np.sign(out["close"] - out["open"]) * out["volume"]

    # OFI proxy compares signed volume to total volume over a short rolling
    # window. Leading NaNs are expected until five bars are available.
    rolling_volume = out["volume"].rolling(5, min_periods=5).sum()
    out["ofi_proxy"] = out["signed_volume"].rolling(5, min_periods=5).sum() / rolling_volume

    # Twelve 5-minute bars represent roughly one trading hour in the default
    # project setting. The same function still works for other bar intervals.
    out["rolling_vol"] = out["returns"].rolling(12, min_periods=12).std()

    # Volume z-score flags unusual activity relative to the recent bar history.
    out["volume_zscore"] = (
        out["volume"] - out["volume"].rolling(20, min_periods=20).mean()
    ) / out["volume"].rolling(20, min_periods=20).std()

    # Short-horizon momentum and reversal are simple baselines for signal
    # research before introducing more complex alpha models.
    out["momentum_3"] = out["close"].pct_change(3)
    out["reversal_3"] = -out["momentum_3"]

    # Higher volume improves the score while wider bars and higher volatility
    # reduce it. This ranks conditions within one ticker's sample, not globally.
    out["liquidity_score"] = (
        out["volume"].rank(pct=True)
        - out["spread_proxy"].rank(pct=True)
        - out["rolling_vol"].rank(pct=True)
    )

    # First-pass composite signal used by the adaptive strategy. Phase 3 will
    # test whether this has predictive value before it is trusted in execution.
    out["alpha_signal"] = (
        0.40 * out["ofi_proxy"].rank(pct=True)
        + 0.25 * out["momentum_3"].rank(pct=True)
        + 0.20 * out["volume_zscore"].rank(pct=True)
        + 0.15 * out["liquidity_score"].rank(pct=True)
    )
    # Centering makes the signal easier to interpret: positive means relatively
    # bullish pressure and negative means relatively bearish pressure.
    out["alpha_signal"] = out["alpha_signal"] - out["alpha_signal"].mean()

    if include_extended_proxies:
        out = out.join(compute_queue_pressure_proxy(out))
        out = out.join(compute_hidden_liquidity_proxy(out))
        out = out.join(compute_passive_fill_risk_proxy(out))

    return out
