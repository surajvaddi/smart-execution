"""Short-horizon alpha signal research utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_HORIZONS = [1, 3, 6, 12]

DEFAULT_SIGNAL_COLUMNS = [
    "ofi_proxy",
    "momentum_3",
    "reversal_3",
    "volume_zscore",
    "rolling_vol",
    "spread_proxy",
    "liquidity_score",
    "alpha_signal",
]


def add_forward_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """Add forward return targets for the requested bar horizons."""
    out = df.copy()
    for horizon in horizons:
        # Forward returns are the Phase 3 prediction targets. For 5-minute bars,
        # horizons [1, 3, 6, 12] correspond to 5, 15, 30, and 60 minutes.
        out[f"fwd_return_{horizon}"] = out["close"].shift(-horizon) / out["close"] - 1
    return out


def _valid_signal_target_data(
    df: pd.DataFrame,
    signal_col: str,
    target_col: str,
) -> pd.DataFrame:
    """Return finite signal/target observations for metric calculations."""
    missing = [col for col in [signal_col, target_col] if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required signal metric columns: {missing}")

    valid = df[[signal_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
    return valid


def information_coefficient(df: pd.DataFrame, signal_col: str, target_col: str) -> float:
    """Return the Pearson correlation between a signal and a forward return target."""
    # IC is the first lightweight check for whether a signal has directional
    # information before it is used in adaptive execution.
    valid = _valid_signal_target_data(df, signal_col, target_col)
    if len(valid) < 2:
        return np.nan
    return valid[signal_col].corr(valid[target_col])


def hit_rate(df: pd.DataFrame, signal_col: str, target_col: str) -> float:
    """Return the share of observations where signal and target signs match."""
    valid = _valid_signal_target_data(df, signal_col, target_col)
    if valid.empty:
        return np.nan

    signal_sign = np.sign(valid[signal_col])
    target_sign = np.sign(valid[target_col])
    non_zero = (signal_sign != 0) & (target_sign != 0)
    if not non_zero.any():
        return np.nan

    return (signal_sign[non_zero] == target_sign[non_zero]).mean()


def decile_spread(df: pd.DataFrame, signal_col: str, target_col: str) -> float:
    """Return average target spread between highest and lowest signal deciles."""
    valid = _valid_signal_target_data(df, signal_col, target_col).copy()
    if len(valid) < 10 or valid[signal_col].nunique() < 2:
        return np.nan

    valid["decile"] = pd.qcut(valid[signal_col], 10, labels=False, duplicates="drop")
    by_decile = valid.groupby("decile")[target_col].mean()
    if len(by_decile) < 2:
        return np.nan

    return by_decile.iloc[-1] - by_decile.iloc[0]


def evaluate_signals(
    df: pd.DataFrame,
    signal_cols: list[str] | None = None,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """Evaluate each signal against each forward return horizon."""
    signal_cols = signal_cols or DEFAULT_SIGNAL_COLUMNS
    horizons = horizons or DEFAULT_HORIZONS

    rows = []
    for signal_col in signal_cols:
        for horizon in horizons:
            target_col = f"fwd_return_{horizon}"
            valid = _valid_signal_target_data(df, signal_col, target_col)
            rows.append(
                {
                    "signal": signal_col,
                    "horizon": horizon,
                    "target": target_col,
                    "n_obs": len(valid),
                    "information_coefficient": information_coefficient(
                        df,
                        signal_col,
                        target_col,
                    ),
                    "hit_rate": hit_rate(df, signal_col, target_col),
                    "decile_spread": decile_spread(df, signal_col, target_col),
                }
            )

    return pd.DataFrame(rows)


def signal_decay_table(
    evaluation: pd.DataFrame,
    metric_col: str = "information_coefficient",
) -> pd.DataFrame:
    """Pivot signal evaluation results into signal-by-horizon decay format."""
    required = ["signal", "horizon", metric_col]
    missing = [col for col in required if col not in evaluation.columns]
    if missing:
        raise ValueError(f"Missing required decay table columns: {missing}")

    decay = evaluation.pivot(index="signal", columns="horizon", values=metric_col)
    decay = decay.sort_index(axis=1)
    decay.columns = [f"horizon_{horizon}" for horizon in decay.columns]
    decay = decay.reset_index()
    return decay
