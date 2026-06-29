from __future__ import annotations

from src.microstructure_metrics import compute_kyle_lambda_proxy, compute_order_flow_autocorrelation_proxy
from src.microstructure_reports import microstructure_metric_scorecard, summarize_microstructure_regimes
from src.services import prepare_features
from test_rl_env import sample_market_data


def test_summarize_microstructure_regimes_returns_feature_rows() -> None:
    featured = prepare_features(sample_market_data(), include_extended_proxies=True)

    summary = summarize_microstructure_regimes(featured)

    assert not summary.empty
    assert {"feature", "mean", "p50", "n_obs", "data_basis"}.issubset(summary.columns)
    assert set(summary["data_basis"]) == {"proxy"}


def test_microstructure_metric_scorecard_concatenates_metric_frames() -> None:
    scorecard = microstructure_metric_scorecard(
        [
            compute_kyle_lambda_proxy(sample_market_data()),
            compute_order_flow_autocorrelation_proxy(sample_market_data()),
        ]
    )

    assert not scorecard.empty
    assert {"metric", "value", "data_basis"}.issubset(scorecard.columns)
