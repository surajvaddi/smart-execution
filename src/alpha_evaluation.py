"""Evaluation scorecards for predictive alpha models."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rank_ic(
    data: pd.DataFrame,
    score_column: str,
    target_column: str,
) -> float:
    """Return the Spearman rank correlation between model scores and targets."""
    valid = _valid_score_target_data(data, score_column, target_column)
    if len(valid) < 2:
        return np.nan
    return float(valid[score_column].corr(valid[target_column], method="spearman"))


def bucket_return_spread(
    data: pd.DataFrame,
    score_column: str,
    target_column: str,
    n_buckets: int = 10,
) -> float:
    """Return the average target spread between top and bottom score buckets."""
    valid = _valid_score_target_data(data, score_column, target_column).copy()
    if len(valid) < n_buckets or valid[score_column].nunique() < 2:
        return np.nan

    valid["bucket"] = pd.qcut(valid[score_column], n_buckets, labels=False, duplicates="drop")
    by_bucket = valid.groupby("bucket")[target_column].mean()
    if len(by_bucket) < 2:
        return np.nan
    return float(by_bucket.iloc[-1] - by_bucket.iloc[0])


def calibration_table(
    data: pd.DataFrame,
    score_column: str,
    target_column: str,
    n_buckets: int = 5,
) -> pd.DataFrame:
    """Group predictions into score buckets and summarize realized outcomes."""
    valid = _valid_score_target_data(data, score_column, target_column).copy()
    if valid.empty:
        return pd.DataFrame(columns=["bucket", "n_obs", "mean_score", "mean_target"])

    valid["bucket"] = pd.qcut(valid[score_column], n_buckets, labels=False, duplicates="drop")
    return (
        valid.groupby("bucket")
        .agg(
            n_obs=(target_column, "size"),
            mean_score=(score_column, "mean"),
            mean_target=(target_column, "mean"),
        )
        .reset_index()
        .sort_values("bucket")
    )


def model_scorecard(
    data: pd.DataFrame,
    score_column: str,
    target_column: str,
) -> pd.DataFrame:
    """Return a one-row scorecard for one model score and one horizon target."""
    valid = _valid_score_target_data(data, score_column, target_column)
    return pd.DataFrame(
        [
            {
                "score_column": score_column,
                "target_column": target_column,
                "n_obs": len(valid),
                "rank_ic": rank_ic(data, score_column, target_column),
                "bucket_return_spread": bucket_return_spread(data, score_column, target_column),
                "mean_score": np.nan if valid.empty else float(valid[score_column].mean()),
                "mean_target": np.nan if valid.empty else float(valid[target_column].mean()),
            }
        ]
    )


def _valid_score_target_data(
    data: pd.DataFrame,
    score_column: str,
    target_column: str,
) -> pd.DataFrame:
    """Return finite score/target observations for evaluation calculations."""
    missing = [column for column in [score_column, target_column] if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required alpha evaluation columns: {missing}")
    return data[[score_column, target_column]].replace([np.inf, -np.inf], np.nan).dropna()
