"""Tests for the adaptive ensemble RL execution environment."""

from __future__ import annotations

from datetime import time
import math

import pandas as pd

from src.execution import ParentOrder
from src.rl_backtester import run_rl_policy_on_data
from src.rl_env import ACTION_SPACE, ExecutionEnv
from src.rl_policy import HeuristicExecutionPolicy


def sample_market_data() -> pd.DataFrame:
    """Return a small feature-complete intraday market sample."""
    timestamps = pd.date_range(
        "2026-01-02 10:00:00",
        periods=6,
        freq="5min",
        tz="America/New_York",
    )
    closes = [100.0, 100.2, 100.1, 100.4, 100.3, 100.5]
    data = pd.DataFrame(
        {
            "ticker": ["XYZ"] * len(timestamps),
            "date": [timestamps[0].date()] * len(timestamps),
            "time": [ts.time() for ts in timestamps],
            "open": closes,
            "high": [px + 0.5 for px in closes],
            "low": [px - 0.5 for px in closes],
            "close": closes,
            "volume": [10_000.0, 12_000.0, 9_000.0, 11_000.0, 10_500.0, 9_500.0],
            "returns": [0.0, 0.002, -0.001, 0.003, -0.001, 0.002],
            "spread_proxy": [0.01, 0.012, 0.015, 0.011, 0.013, 0.012],
            "rolling_vol": [0.01, 0.012, 0.02, 0.011, 0.013, 0.012],
            "volume_zscore": [0.0, 0.7, -0.5, 0.3, 0.1, -0.2],
            "liquidity_score": [0.5, 0.9, 0.2, 0.8, 0.6, 0.4],
            "alpha_signal": [0.0, 0.2, -0.1, 0.1, -0.2, 0.0],
            "bar_index": list(range(len(timestamps))),
        },
        index=pd.Index(timestamps, name="timestamp"),
    )
    return data


def sample_order(quantity: float = 2_000.0) -> ParentOrder:
    """Return a parent order matching the sample data."""
    return ParentOrder(
        ticker="XYZ",
        side="buy",
        quantity=quantity,
        start_time=time(10, 0),
        end_time=time(10, 25),
        participation_cap=0.10,
        date=pd.Timestamp("2026-01-02").date(),
        order_id="XYZ_rl_test",
    )


def test_reset_returns_valid_state() -> None:
    env = ExecutionEnv(sample_order(), sample_market_data(), strategies={})
    state = env.reset()

    assert list(state.index) == env.state_schema
    assert len(state) == len(env.state_schema)
    assert state.notna().all()


def test_step_advances_exactly_one_bar() -> None:
    env = ExecutionEnv(sample_order(), sample_market_data(), strategies={})
    env.reset()

    _, reward, done, info = env.step(0)

    assert env.current_index == 1
    assert done is False
    assert math.isfinite(reward)
    assert info["submitted_quantity"] == 0.0


def test_actions_never_exceed_participation_cap() -> None:
    env = ExecutionEnv(sample_order(quantity=10_000.0), sample_market_data(), strategies={})
    env.reset()
    row = env.window.iloc[0]

    _, _, _, info = env.step(3)

    assert info["submitted_quantity"] <= env.order.participation_cap * row["volume"]


def test_actions_never_exceed_remaining_quantity() -> None:
    env = ExecutionEnv(sample_order(quantity=100.0), sample_market_data(), strategies={})
    env.reset()

    _, _, _, info = env.step(3)

    assert info["submitted_quantity"] <= 100.0
    assert env.remaining_quantity >= 0.0


def test_environment_terminates_by_end_of_market_window() -> None:
    env = ExecutionEnv(sample_order(quantity=1_000_000.0), sample_market_data(), strategies={})
    env.reset()

    done = False
    for _ in range(len(env.window)):
        _, reward, done, _ = env.step(0)
        assert math.isfinite(reward)

    assert done is True
    assert env.current_index == len(env.window)


def test_filled_quantity_never_exceeds_parent_quantity() -> None:
    env = ExecutionEnv(sample_order(quantity=500.0), sample_market_data(), strategies={})
    env.reset()

    while not env.done:
        env.step(3)

    assert env.filled_quantity <= env.order.quantity
    assert env.remaining_quantity >= 0.0


def test_reward_is_finite_for_all_actions() -> None:
    for action in ACTION_SPACE:
        env = ExecutionEnv(sample_order(), sample_market_data(), strategies={})
        env.reset()
        _, reward, _, _ = env.step(action)
        assert math.isfinite(reward)


def test_state_schema_has_no_future_fields() -> None:
    env = ExecutionEnv(sample_order(), sample_market_data(), strategies={})

    forbidden = {"future_close", "future_volume", "future_return", "next_mid_price"}

    assert forbidden.isdisjoint(set(env.state_schema))


def test_rl_results_include_main_tca_columns() -> None:
    results = run_rl_policy_on_data(
        sample_market_data(),
        HeuristicExecutionPolicy(),
        max_orders_per_ticker=1,
    )
    required = {
        "strategy",
        "implementation_shortfall_bps",
        "vwap_slippage_bps",
        "spread_cost_bps",
        "impact_cost_bps",
        "adverse_selection_cost_bps",
        "timing_cost_bps",
        "opportunity_cost_bps",
        "fill_rate",
    }

    assert required.issubset(results.columns)
    assert set(results["strategy"]) == {"RLAdaptiveEnsemble"}
