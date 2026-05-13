"""Tests for Monte Carlo execution-grid summaries."""

from __future__ import annotations

from src.fill_simulator import STOCHASTIC_QUEUE_FILL_MODEL
from src.monte_carlo import (
    MonteCarloConfig,
    run_monte_carlo_execution_grid,
    summarize_monte_carlo_results,
)
from test_rl_env import sample_market_data


def test_monte_carlo_execution_grid_runs_each_seed() -> None:
    config = MonteCarloConfig(
        seeds=[3, 4],
        placement_styles=["market", "passive_limit"],
        fill_model=STOCHASTIC_QUEUE_FILL_MODEL,
        max_orders_per_ticker=1,
    )

    results, fills = run_monte_carlo_execution_grid(sample_market_data(), config)

    assert set(results["random_seed"]) == {3, 4}
    assert set(fills["random_seed"]) == {3, 4}
    assert set(results["placement_style"]) == {"market", "passive_limit"}
    assert results["path_id"].nunique() == 2
    assert not fills.empty


def test_monte_carlo_summary_includes_distribution_stats() -> None:
    config = MonteCarloConfig(
        seeds=[5, 6],
        placement_styles=["market", "passive_limit"],
        fill_model=STOCHASTIC_QUEUE_FILL_MODEL,
        max_orders_per_ticker=1,
    )
    results, _ = run_monte_carlo_execution_grid(sample_market_data(), config)

    summary = summarize_monte_carlo_results(results)

    required = {
        "strategy",
        "placement_style",
        "num_paths",
        "num_simulations",
        "fill_rate_mean",
        "fill_rate_median",
        "fill_rate_p10",
        "fill_rate_p90",
        "implementation_shortfall_bps_mean",
        "implementation_shortfall_bps_std",
    }
    assert required.issubset(summary.columns)
    assert set(summary["num_paths"]) == {2}
