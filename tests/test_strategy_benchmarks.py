from __future__ import annotations

import pandas as pd
import pytest

from src.strategy_benchmarks import (
    bootstrap_strategy_difference,
    compare_strategy_results,
    strategy_tail_risk_summary,
)


def sample_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"strategy": "TWAP", "implementation_shortfall_bps": 12.0, "fill_rate": 1.0},
            {"strategy": "TWAP", "implementation_shortfall_bps": 10.0, "fill_rate": 1.0},
            {"strategy": "VWAP", "implementation_shortfall_bps": 8.0, "fill_rate": 0.95},
            {"strategy": "VWAP", "implementation_shortfall_bps": 9.0, "fill_rate": 0.98},
            {"strategy": "Adaptive", "implementation_shortfall_bps": 7.0, "fill_rate": 0.97},
            {"strategy": "Adaptive", "implementation_shortfall_bps": 11.0, "fill_rate": 0.96},
        ]
    )


def test_compare_strategy_results_ranks_lower_cost_strategies_first() -> None:
    summary = compare_strategy_results(sample_results())

    assert summary.iloc[0]["strategy"] == "VWAP"
    assert summary.iloc[-1]["strategy"] == "TWAP"
    assert set(["count", "mean", "median", "std", "rank"]).issubset(summary.columns)


def test_bootstrap_strategy_difference_returns_percentile_summary() -> None:
    summary = bootstrap_strategy_difference(
        sample_results(),
        left_strategy="TWAP",
        right_strategy="VWAP",
        n_bootstrap=200,
        random_seed=7,
    )

    assert summary["left_strategy"] == "TWAP"
    assert summary["right_strategy"] == "VWAP"
    assert summary["mean_difference"] > 0
    assert summary["p95_difference"] >= summary["p05_difference"]


def test_strategy_tail_risk_summary_uses_upper_tail_of_metric_distribution() -> None:
    summary = strategy_tail_risk_summary(sample_results(), tail_quantile=0.5)

    assert set(["strategy", "tail_threshold", "tail_mean", "tail_count"]).issubset(summary.columns)
    twap_tail = summary[summary["strategy"] == "TWAP"].iloc[0]
    assert twap_tail["tail_threshold"] == pytest.approx(11.0)
    assert twap_tail["tail_mean"] == pytest.approx(12.0)
