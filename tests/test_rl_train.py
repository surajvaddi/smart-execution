"""Tests for tabular RL training utilities."""

from __future__ import annotations

from src.rl_train import build_training_envs, load_q_table, save_q_table, train_q_policy
from test_rl_env import sample_market_data


def test_train_q_policy_saves_and_loads_table(tmp_path) -> None:
    envs = build_training_envs(
        sample_market_data(),
        max_orders_per_ticker=1,
    )

    q_table = train_q_policy(
        envs,
        episodes=1,
        epsilon=0.5,
        seed=7,
    )
    output_path = save_q_table(q_table, tmp_path / "q_policy.pkl")
    loaded = load_q_table(output_path)

    assert output_path.exists()
    assert q_table
    assert loaded == q_table
