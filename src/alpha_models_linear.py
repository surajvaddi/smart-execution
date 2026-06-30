"""Baseline linear alpha models for intraday prediction research."""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import Lasso, Ridge


def fit_ridge_alpha_model(
    train_data: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    alpha: float = 1.0,
) -> Ridge:
    """Fit a deterministic ridge regression alpha model."""
    _validate_training_inputs(train_data, feature_columns, target_column)
    model = Ridge(alpha=alpha)
    model.fit(train_data[feature_columns], train_data[target_column])
    return model


def fit_lasso_alpha_model(
    train_data: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    alpha: float = 0.001,
    max_iter: int = 10_000,
) -> Lasso:
    """Fit a deterministic lasso regression alpha model."""
    _validate_training_inputs(train_data, feature_columns, target_column)
    model = Lasso(alpha=alpha, max_iter=max_iter)
    model.fit(train_data[feature_columns], train_data[target_column])
    return model


def predict_linear_alpha(
    model: Ridge | Lasso,
    data: pd.DataFrame,
    feature_columns: list[str],
    prediction_column: str = "alpha_model_score",
) -> pd.DataFrame:
    """Attach linear-model predictions to an alpha dataset frame."""
    missing = [column for column in feature_columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required linear model feature columns: {missing}")

    predicted = data.copy()
    predicted[prediction_column] = model.predict(predicted[feature_columns])
    return predicted


def _validate_training_inputs(
    train_data: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> None:
    """Validate training data for linear alpha models."""
    if not feature_columns:
        raise ValueError("feature_columns must be non-empty.")
    missing = [column for column in [*feature_columns, target_column] if column not in train_data.columns]
    if missing:
        raise ValueError(f"Missing required linear model columns: {missing}")
    if train_data.empty:
        raise ValueError("train_data must be non-empty.")
