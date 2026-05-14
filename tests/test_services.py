"""Tests for callable backend service contracts."""

from __future__ import annotations

import pytest

from src.backtester import Backtester
from src.rl_env import RL_STRATEGY_NAME
from src.strategies import AdaptiveModelWeights, AdaptiveStrategy
from src.services import (
    filter_market_data,
    load_processed_data,
    parent_orders,
    preview_execution_fills,
    prepare_features,
    run_backtest,
    run_execution_grid,
    run_monte_carlo_grid,
    run_rl_backtest,
    run_signal_research,
    volume_curve,
)
from test_rl_env import sample_market_data


def test_load_processed_data_applies_filters(tmp_path) -> None:
    path = tmp_path / "market.csv"
    sample_market_data().to_csv(path)

    data = load_processed_data(
        path,
        start_date="2026-01-02",
        end_date="2026-01-02",
        start_time="10:05",
        end_time="10:15",
    )

    assert len(data) == 3
    assert data.index.min().strftime("%H:%M") == "10:05"
    assert data.index.max().strftime("%H:%M") == "10:15"


def test_filter_market_data_requires_paired_filters() -> None:
    with pytest.raises(ValueError, match="start_date and end_date"):
        filter_market_data(sample_market_data(), start_date="2026-01-02")

    with pytest.raises(ValueError, match="start_time and end_time"):
        filter_market_data(sample_market_data(), start_time="10:00")


def test_feature_and_parent_order_services_return_stable_tables() -> None:
    featured = prepare_features(sample_market_data())
    curve = volume_curve(featured)
    orders = parent_orders(featured, max_orders_per_ticker=1)

    assert "alpha_signal" in featured.columns
    assert {"bar_index", "expected_volume_share"}.issubset(curve.columns)
    assert {"order_id", "ticker", "side", "quantity"}.issubset(orders.columns)
    assert len(orders) == 1


def test_backtest_service_runs_default_strategies() -> None:
    results = run_backtest(sample_market_data(), max_orders_per_ticker=1)

    assert set(results["strategy"]) == {"TWAP", "VWAP", "POV", "Adaptive"}
    assert "implementation_shortfall_bps" in results.columns


def test_execution_grid_service_returns_results_and_fills() -> None:
    grid = run_execution_grid(
        sample_market_data(),
        placement_styles=["market", "passive_limit"],
        max_orders_per_ticker=1,
    )

    assert set(grid.results["placement_style"]) == {"market", "passive_limit"}
    assert not grid.fills.empty
    assert {"submitted_quantity", "filled_quantity", "fill_status"}.issubset(grid.fills.columns)


def test_preview_execution_fills_spreads_rows_across_strategies() -> None:
    grid = run_execution_grid(
        sample_market_data(),
        placement_styles=["market", "passive_limit"],
        max_orders_per_ticker=1,
    )

    preview = preview_execution_fills(grid.fills, limit=8)

    assert len(preview) == 8
    assert set(preview["strategy"]) >= {"TWAP", "VWAP", "POV", "Adaptive"}


def test_monte_carlo_service_returns_summary() -> None:
    result = run_monte_carlo_grid(
        sample_market_data(),
        seeds=[11, 12],
        placement_styles=["market"],
        max_orders_per_ticker=1,
    )

    assert set(result.results["random_seed"]) == {11, 12}
    assert set(result.summary["num_paths"]) == {2}
    assert "fill_rate_mean" in result.summary.columns


def test_rl_and_signal_services_are_callable() -> None:
    rl_results = run_rl_backtest(
        sample_market_data(),
        max_orders_per_ticker=1,
        include_baselines=False,
    )
    signals = run_signal_research(sample_market_data(), horizons=[1])

    assert set(rl_results["strategy"]) == {RL_STRATEGY_NAME}
    assert {"evaluation", "decay", "summary"} == set(signals.__dataclass_fields__)
    assert not signals.evaluation.empty


def test_backtester_run_dispatches_in_memory_data() -> None:
    backtester = Backtester(tickers=["XYZ"], max_orders_per_ticker=1)

    results = backtester.run(data=sample_market_data())

    assert set(results["strategy"]) == {"TWAP", "VWAP", "POV", "Adaptive"}


def test_backtester_run_requires_exactly_one_input() -> None:
    backtester = Backtester(tickers=["XYZ"], max_orders_per_ticker=1)

    with pytest.raises(ValueError, match="exactly one"):
        backtester.run()
    with pytest.raises(ValueError, match="exactly one"):
        backtester.run(data=sample_market_data(), input_csv="unused.csv")


def test_adaptive_weights_change_the_multiplier() -> None:
    row = sample_market_data().iloc[1].copy()
    row["spread_proxy_75pct"] = 0.0
    row["rolling_vol_75pct"] = 0.0
    row["liquidity_score_75pct"] = 0.0

    default = AdaptiveStrategy().adaptive_multiplier(row, "buy", 1.0)
    tuned = AdaptiveStrategy(
        AdaptiveModelWeights(
            bullish_signal_multiplier=2.0,
            bearish_signal_multiplier=0.5,
            spread_penalty_multiplier=0.9,
            volatility_penalty_multiplier=0.9,
            liquidity_boost_multiplier=1.1,
            urgency_weight=1.5,
        )
    ).adaptive_multiplier(row, "buy", 1.0)

    assert tuned > default
