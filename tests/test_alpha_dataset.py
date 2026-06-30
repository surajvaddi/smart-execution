from __future__ import annotations

import pandas as pd
import pytest

from src.alpha_dataset import (
    attach_forward_targets,
    build_alpha_feature_matrix,
    drop_leaky_columns,
    validate_alpha_dataset,
)
from src.features import add_microstructure_features
from test_rl_env import sample_market_data


def featured_market_data() -> pd.DataFrame:
    return add_microstructure_features(sample_market_data(), include_extended_proxies=True)


def test_attach_forward_targets_adds_requested_horizons() -> None:
    target_ready = attach_forward_targets(featured_market_data(), horizons=[1, 3])

    assert {"fwd_return_1", "fwd_return_3"}.issubset(target_ready.columns)


def test_drop_leaky_columns_removes_forward_targets_and_explicit_leaks() -> None:
    target_ready = attach_forward_targets(featured_market_data(), horizons=[1])
    dropped = drop_leaky_columns(target_ready, extra_leaky_columns=["close"])

    assert "fwd_return_1" not in dropped.columns
    assert "close" not in dropped.columns


def test_build_alpha_feature_matrix_preserves_features_and_targets_without_mixup() -> None:
    alpha_dataset = build_alpha_feature_matrix(
        featured_market_data(),
        horizons=[1],
        include_extended_proxies=True,
    )

    feature_columns = alpha_dataset.attrs["feature_columns"]
    target_columns = alpha_dataset.attrs["target_columns"]

    assert "alpha_signal" in feature_columns
    assert "queue_pressure_proxy" in feature_columns
    assert target_columns == ["fwd_return_1"]
    assert "fwd_return_1" in alpha_dataset.columns


def test_validate_alpha_dataset_rejects_leaky_feature_columns() -> None:
    alpha_dataset = build_alpha_feature_matrix(featured_market_data(), horizons=[1])
    alpha_dataset.attrs["feature_columns"] = ["alpha_signal", "fwd_return_1"]

    with pytest.raises(ValueError, match="leaky targets"):
        validate_alpha_dataset(alpha_dataset)


def test_validate_alpha_dataset_accepts_date_based_contract() -> None:
    alpha_dataset = build_alpha_feature_matrix(featured_market_data(), horizons=[1])

    validate_alpha_dataset(alpha_dataset)
