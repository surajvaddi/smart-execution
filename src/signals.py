"""Short-horizon alpha signal research utilities."""

from __future__ import annotations

import pandas as pd


def add_forward_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """Add forward return targets for the requested bar horizons."""
    out = df.copy()
    for horizon in horizons:
        out[f"fwd_return_{horizon}"] = out["close"].shift(-horizon) / out["close"] - 1
    return out


def information_coefficient(df: pd.DataFrame, signal_col: str, target_col: str) -> float:
    """Return the Pearson correlation between a signal and a forward return target."""
    return df[[signal_col, target_col]].corr().iloc[0, 1]
