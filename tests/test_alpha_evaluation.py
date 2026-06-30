from __future__ import annotations

import pandas as pd
import pytest

from src.alpha_evaluation import bucket_return_spread, calibration_table, model_scorecard, rank_ic


def sample_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "alpha_model_score": [-0.9, -0.5, -0.2, 0.1, 0.4, 0.8],
            "fwd_return_1": [-0.03, -0.02, -0.01, 0.01, 0.02, 0.04],
        }
    )


def test_rank_ic_returns_positive_rank_correlation_for_monotone_scores() -> None:
    ic = rank_ic(sample_predictions(), "alpha_model_score", "fwd_return_1")

    assert ic == pytest.approx(1.0)


def test_bucket_return_spread_compares_top_and_bottom_score_buckets() -> None:
    spread = bucket_return_spread(
        sample_predictions(),
        "alpha_model_score",
        "fwd_return_1",
        n_buckets=3,
    )

    expected_bottom = (-0.03 + -0.02) / 2
    expected_top = (0.02 + 0.04) / 2
    assert spread == pytest.approx(expected_top - expected_bottom)


def test_calibration_table_groups_rows_by_score_bucket() -> None:
    table = calibration_table(
        sample_predictions(),
        "alpha_model_score",
        "fwd_return_1",
        n_buckets=3,
    )

    assert table["bucket"].tolist() == [0, 1, 2]
    assert table["n_obs"].tolist() == [2, 2, 2]
    assert table.iloc[-1]["mean_target"] > table.iloc[0]["mean_target"]


def test_model_scorecard_returns_one_row_summary() -> None:
    scorecard = model_scorecard(sample_predictions(), "alpha_model_score", "fwd_return_1")

    assert len(scorecard) == 1
    assert scorecard.loc[0, "rank_ic"] == pytest.approx(1.0)
    assert scorecard.loc[0, "n_obs"] == 6
