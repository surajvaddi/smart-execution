"""Short-horizon alpha signal research utilities."""

from __future__ import annotations

import pandas as pd


def add_forward_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """Add forward return targets for the requested bar horizons."""
    out = df.copy()
    for horizon in horizons:
        # Forward returns are the Phase 3 prediction targets. For 5-minute bars,
        # horizons [1, 3, 6, 12] correspond to 5, 15, 30, and 60 minutes.
        out[f"fwd_return_{horizon}"] = out["close"].shift(-horizon) / out["close"] - 1
    return out


def information_coefficient(df: pd.DataFrame, signal_col: str, target_col: str) -> float:
    """Return the Pearson correlation between a signal and a forward return target."""
    # IC is the first lightweight check for whether a signal has directional
    # information before it is used in adaptive execution.
    return df[[signal_col, target_col]].corr().iloc[0, 1]
