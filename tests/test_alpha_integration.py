from __future__ import annotations

import pandas as pd

from src.features import add_microstructure_features, attach_alpha_model_score
from src.services import attach_model_scores, prepare_features
from test_rl_env import sample_market_data


def test_attach_alpha_model_score_adds_column_without_replacing_alpha_signal() -> None:
    featured = add_microstructure_features(sample_market_data())
    scores = pd.Series(range(len(featured)), index=featured.index, dtype=float)

    enriched = attach_alpha_model_score(featured, scores)

    assert "alpha_model_score" in enriched.columns
    assert "alpha_signal" in enriched.columns
    assert enriched["alpha_model_score"].tolist() == scores.tolist()


def test_attach_model_scores_service_returns_execution_ready_frame() -> None:
    featured = prepare_features(sample_market_data())
    scores = [0.1] * len(featured)

    enriched = attach_model_scores(featured, scores)

    assert "alpha_model_score" in enriched.columns
    assert len(enriched) == len(featured)
