from __future__ import annotations

import pandas as pd
import pytest

from src.alpha_dataset import validate_alpha_dataset
from src.alpha_models_tree import (
    fit_gradient_boosted_alpha_model,
    fit_random_forest_alpha_model,
    predict_tree_alpha,
)
from src.alpha_split import split_by_date


def alpha_train_validation_test():
    rows = []
    for day_offset in range(4):
        date = (pd.Timestamp("2026-01-02") + pd.Timedelta(days=day_offset)).date()
        for bar_index in range(8):
            timestamp = pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York") + pd.Timedelta(
                days=day_offset,
                minutes=5 * bar_index,
            )
            signal = 0.12 * (bar_index - 3)
            spread = 0.01 + 0.001 * bar_index
            liquidity = 0.2 + 0.05 * bar_index
            target = (signal * liquidity) - spread + 0.001 * day_offset
            rows.append(
                {
                    "ticker": "XYZ",
                    "date": date,
                    "time": timestamp.time(),
                    "bar_index": bar_index,
                    "close": 100.0 + day_offset + 0.1 * bar_index,
                    "volume": 1_000.0 + 10.0 * bar_index,
                    "alpha_signal": signal,
                    "spread_proxy": spread,
                    "liquidity_score": liquidity,
                    "fwd_return_1": target,
                }
            )
    dataset = pd.DataFrame(rows)
    dataset.attrs["feature_columns"] = ["alpha_signal", "spread_proxy", "liquidity_score"]
    dataset.attrs["target_columns"] = ["fwd_return_1"]
    dataset.attrs["split_metadata"] = {"date_based_only": True}
    validate_alpha_dataset(dataset)
    splits = split_by_date(
        dataset,
        train_end_date="2026-01-03",
        validation_end_date="2026-01-04",
        test_end_date="2026-01-05",
    )
    feature_columns = ["alpha_signal", "spread_proxy", "liquidity_score"]
    target_column = "fwd_return_1"
    return splits, feature_columns, target_column


def test_fit_random_forest_alpha_model_trains_deterministically() -> None:
    splits, feature_columns, target_column = alpha_train_validation_test()

    model_one = fit_random_forest_alpha_model(splits["train"], feature_columns, target_column, random_seed=7)
    model_two = fit_random_forest_alpha_model(splits["train"], feature_columns, target_column, random_seed=7)

    predicted_one = model_one.predict(splits["validation"][feature_columns])
    predicted_two = model_two.predict(splits["validation"][feature_columns])
    assert predicted_one.tolist() == pytest.approx(predicted_two.tolist())


def test_fit_gradient_boosted_alpha_model_trains_deterministically() -> None:
    splits, feature_columns, target_column = alpha_train_validation_test()

    model_one = fit_gradient_boosted_alpha_model(splits["train"], feature_columns, target_column, random_seed=7)
    model_two = fit_gradient_boosted_alpha_model(splits["train"], feature_columns, target_column, random_seed=7)

    predicted_one = model_one.predict(splits["validation"][feature_columns])
    predicted_two = model_two.predict(splits["validation"][feature_columns])
    assert predicted_one.tolist() == pytest.approx(predicted_two.tolist())


def test_predict_tree_alpha_adds_model_score_column() -> None:
    splits, feature_columns, target_column = alpha_train_validation_test()
    model = fit_random_forest_alpha_model(splits["train"], feature_columns, target_column, random_seed=7)

    predicted = predict_tree_alpha(model, splits["validation"], feature_columns)

    assert "alpha_model_score" in predicted.columns
    assert len(predicted) == len(splits["validation"])
