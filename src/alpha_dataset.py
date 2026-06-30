"""Leakage-safe alpha dataset builder for intraday prediction research."""

from __future__ import annotations

import pandas as pd

from src.features import EXTENDED_PROXY_COLUMNS, FEATURE_COLUMNS
from src.signals import add_forward_returns


DEFAULT_ALPHA_FEATURE_COLUMNS = FEATURE_COLUMNS + EXTENDED_PROXY_COLUMNS
LEAKY_COLUMN_PREFIXES = ("fwd_return_",)
DEFAULT_METADATA_COLUMNS = ["ticker", "date", "time", "bar_index", "close", "volume"]


def attach_forward_targets(
    data: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    """Attach forward-return targets to a feature frame."""
    if "close" not in data.columns:
        raise ValueError("data must include close to compute forward targets.")
    return add_forward_returns(data, horizons)


def drop_leaky_columns(
    data: pd.DataFrame,
    target_columns: list[str] | None = None,
    extra_leaky_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Remove forward targets and explicitly leaky columns from a feature frame."""
    target_columns = target_columns or [column for column in data.columns if column.startswith(LEAKY_COLUMN_PREFIXES)]
    leaky_columns = set(target_columns)
    for column in extra_leaky_columns or []:
        leaky_columns.add(column)
    kept_columns = [column for column in data.columns if column not in leaky_columns]
    return data.loc[:, kept_columns].copy()


def build_alpha_feature_matrix(
    data: pd.DataFrame,
    horizons: list[int],
    feature_columns: list[str] | None = None,
    include_extended_proxies: bool = False,
) -> pd.DataFrame:
    """Build a feature/target research frame for alpha modeling."""
    required = ["ticker", "date", "time", "bar_index", "close"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required alpha dataset columns: {missing}")

    target_ready = attach_forward_targets(data, horizons)
    target_columns = [f"fwd_return_{horizon}" for horizon in horizons]
    selected_features = feature_columns or FEATURE_COLUMNS.copy()
    if include_extended_proxies:
        selected_features = [*selected_features, *EXTENDED_PROXY_COLUMNS]

    missing_features = [column for column in selected_features if column not in target_ready.columns]
    if missing_features:
        raise ValueError(f"Missing required alpha feature columns: {missing_features}")

    dataset_columns = [
        *[column for column in DEFAULT_METADATA_COLUMNS if column in target_ready.columns],
        *selected_features,
        *target_columns,
    ]
    alpha_dataset = target_ready.loc[:, dataset_columns].copy()
    alpha_dataset.attrs["feature_columns"] = selected_features
    alpha_dataset.attrs["target_columns"] = target_columns
    alpha_dataset.attrs["split_metadata"] = {"date_based_only": True}
    return alpha_dataset


def validate_alpha_dataset(
    alpha_dataset: pd.DataFrame,
    feature_columns: list[str] | None = None,
    target_columns: list[str] | None = None,
) -> None:
    """Validate a leakage-safe alpha dataset contract."""
    feature_columns = feature_columns or list(alpha_dataset.attrs.get("feature_columns", []))
    target_columns = target_columns or list(alpha_dataset.attrs.get("target_columns", []))
    if not feature_columns:
        raise ValueError("alpha_dataset must declare feature_columns.")
    if not target_columns:
        raise ValueError("alpha_dataset must declare target_columns.")

    missing = [column for column in [*feature_columns, *target_columns] if column not in alpha_dataset.columns]
    if missing:
        raise ValueError(f"Missing required alpha dataset columns: {missing}")

    leaking_features = [column for column in feature_columns if column.startswith(LEAKY_COLUMN_PREFIXES)]
    if leaking_features:
        raise ValueError(f"Feature columns contain leaky targets: {leaking_features}")

    split_metadata = alpha_dataset.attrs.get("split_metadata")
    if not isinstance(split_metadata, dict) or not split_metadata.get("date_based_only"):
        raise ValueError("alpha_dataset must declare date-based split metadata.")
