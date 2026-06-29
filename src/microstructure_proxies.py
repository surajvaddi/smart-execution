"""Additional bar-data feature proxies for market microstructure concepts."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_queue_pressure_proxy(data: pd.DataFrame) -> pd.DataFrame:
    """Estimate queue pressure from volume surprise, spread, and short-term direction."""
    _require_columns(data, ["volume", "spread_proxy"])
    volume_zscore = _safe_zscore(data["volume"])
    directional_pressure = np.sign(data["returns"]) if "returns" in data.columns else 0.0
    proxy = volume_zscore - data["spread_proxy"].fillna(0.0) + directional_pressure
    return pd.DataFrame({"queue_pressure_proxy": proxy}, index=data.index)


def compute_hidden_liquidity_proxy(data: pd.DataFrame) -> pd.DataFrame:
    """Estimate hidden-liquidity conditions from high volume and muted price movement."""
    _require_columns(data, ["volume", "spread_proxy"])
    quiet_range = 1.0 / (1.0 + data["spread_proxy"].clip(lower=0.0))
    volume_rank = data["volume"].rank(pct=True)
    proxy = volume_rank * quiet_range
    return pd.DataFrame({"hidden_liquidity_proxy": proxy}, index=data.index)


def compute_passive_fill_risk_proxy(data: pd.DataFrame) -> pd.DataFrame:
    """Estimate passive-order fill risk from spread, volatility, and liquidity."""
    _require_columns(data, ["spread_proxy"])
    volatility = data["rolling_vol"] if "rolling_vol" in data.columns else data["spread_proxy"]
    liquidity = data["liquidity_score"] if "liquidity_score" in data.columns else 0.0
    proxy = data["spread_proxy"].fillna(0.0) + volatility.fillna(0.0) - liquidity
    return pd.DataFrame({"passive_fill_risk_proxy": proxy}, index=data.index)


def _safe_zscore(series: pd.Series) -> pd.Series:
    """Return a simple population z-score with zero fallback."""
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _require_columns(data: pd.DataFrame, columns: list[str]) -> None:
    """Validate that required columns are present."""
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required microstructure proxy columns: {missing}")
