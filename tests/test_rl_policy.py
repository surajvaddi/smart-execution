"""Tests for RL execution policies."""

from __future__ import annotations

import pandas as pd

from src.rl_env import ACTION_SPACE, ExecutionEnv
from src.rl_policy import HeuristicExecutionPolicy, RandomPolicy


def base_state(**overrides: float) -> pd.Series:
    """Return a feature-complete policy state."""
    values = {
        "time_remaining": 0.8,
        "fraction_completed": 0.2,
        "remaining_quantity_fraction": 0.8,
        "current_bar_volume": 10_000.0,
        "spread_proxy": 0.01,
        "rolling_vol": 0.01,
        "volume_zscore": 0.0,
        "liquidity_score": 0.5,
        "alpha_signal": 0.0,
        "recent_return": 0.0,
        "current_participation_used": 0.0,
        "prior_limit_filled": 0.0,
        "prior_fill_rate": 0.0,
        "prior_spread_cost": 0.0,
        "prior_impact_cost": 0.0,
    }
    values.update(overrides)
    return pd.Series(values, index=ExecutionEnv.state_schema, dtype=float)


def test_random_policy_returns_valid_action() -> None:
    policy = RandomPolicy(seed=7)

    action = policy.select_action(base_state(), valid_actions=[1, 3, 5])

    assert action in {1, 3, 5}


def test_random_policy_defaults_to_action_space() -> None:
    policy = RandomPolicy(seed=7)

    action = policy.select_action(base_state())

    assert action in ACTION_SPACE


def test_heuristic_uses_aggressive_when_urgency_is_high() -> None:
    policy = HeuristicExecutionPolicy()
    state = base_state(time_remaining=0.1, remaining_quantity_fraction=0.9)

    assert policy.select_action(state) == 8


def test_heuristic_uses_passive_when_spread_wide_and_urgency_low() -> None:
    policy = HeuristicExecutionPolicy()
    state = base_state(
        time_remaining=1.0,
        remaining_quantity_fraction=0.2,
        spread_proxy=0.02,
        rolling_vol=0.01,
    )

    assert policy.select_action(state) == 6


def test_heuristic_uses_adaptive_or_pov_in_high_liquidity() -> None:
    policy = HeuristicExecutionPolicy()
    state = base_state(
        time_remaining=1.0,
        liquidity_score=0.9,
        remaining_quantity_fraction=0.4,
    )

    assert policy.select_action(state) == 4


def test_heuristic_waits_or_trades_small_when_spread_and_volatility_high() -> None:
    policy = HeuristicExecutionPolicy()
    state = base_state(
        time_remaining=0.9,
        remaining_quantity_fraction=0.3,
        spread_proxy=0.03,
        rolling_vol=0.03,
    )

    assert policy.select_action(state) == 0


def test_heuristic_respects_valid_actions() -> None:
    policy = HeuristicExecutionPolicy()
    state = base_state(time_remaining=0.1, remaining_quantity_fraction=0.9)

    assert policy.select_action(state, valid_actions=[1, 2]) == 1
