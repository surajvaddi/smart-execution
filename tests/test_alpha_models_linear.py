from __future__ import annotations

import pandas as pd
import pytest

from src.alpha_dataset import validate_alpha_dataset
from src.alpha_models_linear import fit_lasso_alpha_model, fit_ridge_alpha_model, predict_linear_alpha
from src.alpha_split import split_by_date


def alpha_train_validation_test():
    rows = []
    for day_offset in range(4):
        date = (pd.Timestamp("2026-01-02") + pd.Timedelta(days=day_offset)).date()
        for bar_index in range(6):
            timestamp = pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York") + pd.Timedelta(
                days=day_offset,
                minutes=5 * bar_index,
            )
            rows.append(
                {
                    "ticker": "XYZ",
                    "date": date,
                    "time": timestamp.time(),
                    "bar_index": bar_index,
                    "close": 100.0 + day_offset + 0.1 * bar_index,
                    "volume": 1_000.0 + 10.0 * bar_index,
                    "alpha_signal": 0.1 * (bar_index - 2),
                    "spread_proxy": 0.01 + 0.001 * bar_index,
                    "liquidity_score": 0.2 + 0.05 * bar_index,
                    "fwd_return_1": 0.001 * (bar_index + day_offset),
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

    cleaned = {
        name: frame.dropna(subset=[*feature_columns, target_column]).copy()
        for name, frame in splits.items()
    }
    return cleaned, feature_columns, target_column


def test_fit_ridge_alpha_model_trains_deterministically() -> None:
    splits, feature_columns, target_column = alpha_train_validation_test()

    model_one = fit_ridge_alpha_model(splits["train"], feature_columns, target_column, alpha=1.0)
    model_two = fit_ridge_alpha_model(splits["train"], feature_columns, target_column, alpha=1.0)

    assert model_one.coef_.tolist() == pytest.approx(model_two.coef_.tolist())
    assert model_one.intercept_ == pytest.approx(model_two.intercept_)


def test_fit_lasso_alpha_model_trains_deterministically() -> None:
    splits, feature_columns, target_column = alpha_train_validation_test()

    model_one = fit_lasso_alpha_model(splits["train"], feature_columns, target_column, alpha=0.0001)
    model_two = fit_lasso_alpha_model(splits["train"], feature_columns, target_column, alpha=0.0001)

    assert model_one.coef_.tolist() == pytest.approx(model_two.coef_.tolist())
    assert model_one.intercept_ == pytest.approx(model_two.intercept_)


def test_predict_linear_alpha_adds_model_score_column() -> None:
    splits, feature_columns, target_column = alpha_train_validation_test()
    model = fit_ridge_alpha_model(splits["train"], feature_columns, target_column, alpha=1.0)

    predicted = predict_linear_alpha(model, splits["validation"], feature_columns)

    assert "alpha_model_score" in predicted.columns
    assert len(predicted) == len(splits["validation"])
