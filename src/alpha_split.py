"""Date-based split helpers for leakage-safe alpha model evaluation."""

from __future__ import annotations

import pandas as pd


def split_by_date(
    alpha_dataset: pd.DataFrame,
    train_end_date: str,
    validation_end_date: str,
    test_end_date: str,
) -> dict[str, pd.DataFrame]:
    """Split an alpha dataset into non-overlapping train, validation, and test windows."""
    if "date" not in alpha_dataset.columns:
        raise ValueError("alpha_dataset must include a date column.")

    train_end = pd.to_datetime(train_end_date).date()
    validation_end = pd.to_datetime(validation_end_date).date()
    test_end = pd.to_datetime(test_end_date).date()
    if not train_end < validation_end < test_end:
        raise ValueError("Split end dates must satisfy train < validation < test.")

    dates = pd.to_datetime(alpha_dataset["date"]).dt.date
    train = alpha_dataset.loc[dates <= train_end].copy()
    validation = alpha_dataset.loc[(dates > train_end) & (dates <= validation_end)].copy()
    test = alpha_dataset.loc[(dates > validation_end) & (dates <= test_end)].copy()

    return {
        "train": train,
        "validation": validation,
        "test": test,
    }


def rolling_walk_forward_splits(
    alpha_dataset: pd.DataFrame,
    train_days: int,
    validation_days: int,
    test_days: int,
) -> list[dict[str, pd.DataFrame]]:
    """Generate sequential non-overlapping walk-forward splits by unique date."""
    if "date" not in alpha_dataset.columns:
        raise ValueError("alpha_dataset must include a date column.")
    if min(train_days, validation_days, test_days) <= 0:
        raise ValueError("train_days, validation_days, and test_days must be positive.")

    unique_dates = sorted(pd.to_datetime(alpha_dataset["date"]).dt.date.unique())
    window = train_days + validation_days + test_days
    if len(unique_dates) < window:
        return []

    splits = []
    for start_idx in range(0, len(unique_dates) - window + 1):
        train_dates = unique_dates[start_idx : start_idx + train_days]
        validation_dates = unique_dates[start_idx + train_days : start_idx + train_days + validation_days]
        test_dates = unique_dates[
            start_idx + train_days + validation_days : start_idx + train_days + validation_days + test_days
        ]
        dates = pd.to_datetime(alpha_dataset["date"]).dt.date
        splits.append(
            {
                "train": alpha_dataset.loc[dates.isin(train_dates)].copy(),
                "validation": alpha_dataset.loc[dates.isin(validation_dates)].copy(),
                "test": alpha_dataset.loc[dates.isin(test_dates)].copy(),
            }
        )
    return splits
