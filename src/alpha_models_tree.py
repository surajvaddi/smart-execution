"""Nonlinear tree-based alpha models for intraday prediction research."""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor


def fit_random_forest_alpha_model(
    train_data: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    n_estimators: int = 50,
    max_depth: int | None = 4,
    random_seed: int = 42,
) -> RandomForestRegressor:
    """Fit a deterministic random-forest alpha model."""
    _validate_training_inputs(train_data, feature_columns, target_column)
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_seed,
    )
    model.fit(train_data[feature_columns], train_data[target_column])
    return model


def fit_gradient_boosted_alpha_model(
    train_data: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    n_estimators: int = 50,
    learning_rate: float = 0.05,
    max_depth: int = 2,
    random_seed: int = 42,
) -> GradientBoostingRegressor:
    """Fit a deterministic gradient-boosted alpha model."""
    _validate_training_inputs(train_data, feature_columns, target_column)
    model = GradientBoostingRegressor(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        random_state=random_seed,
    )
    model.fit(train_data[feature_columns], train_data[target_column])
    return model


def predict_tree_alpha(
    model: RandomForestRegressor | GradientBoostingRegressor,
    data: pd.DataFrame,
    feature_columns: list[str],
    prediction_column: str = "alpha_model_score",
) -> pd.DataFrame:
    """Attach tree-model predictions to an alpha dataset frame."""
    missing = [column for column in feature_columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required tree model feature columns: {missing}")

    predicted = data.copy()
    predicted[prediction_column] = model.predict(predicted[feature_columns])
    return predicted


def _validate_training_inputs(
    train_data: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> None:
    """Validate training data for tree-based alpha models."""
    if not feature_columns:
        raise ValueError("feature_columns must be non-empty.")
    missing = [column for column in [*feature_columns, target_column] if column not in train_data.columns]
    if missing:
        raise ValueError(f"Missing required tree model columns: {missing}")
    if train_data.empty:
        raise ValueError("train_data must be non-empty.")
