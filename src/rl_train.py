"""Small tabular trainer for adaptive ensemble execution policies."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import pickle
import random
from typing import Dict, Iterable, Tuple

import pandas as pd

from src.execution import generate_parent_orders
from src.features import add_microstructure_features
from src.fill_simulator import DEFAULT_FILL_CONFIG, DEFAULT_FILL_MODEL, FillModelConfig
from src.rl_env import ACTION_SPACE, ExecutionEnv


QTable = Dict[Tuple, Dict[int, float]]


def bucket_state(state: pd.Series) -> tuple:
    """Discretize a continuous execution state into stable buckets."""
    return (
        _bucket(float(state["time_remaining"]), [0.25, 0.75]),
        _bucket(float(state["remaining_quantity_fraction"]), [0.25, 0.75]),
        _bucket(float(state["spread_proxy"]), [0.01, 0.02]),
        _bucket(float(state["liquidity_score"]), [0.33, 0.66]),
        _bucket(float(state["rolling_vol"]), [0.01, 0.02]),
        _alpha_bucket(float(state["alpha_signal"])),
        int(float(state["prior_limit_filled"]) > 0),
    )


def choose_action(
    q_table: QTable,
    state_bucket: tuple,
    epsilon: float,
    rng: random.Random,
    valid_actions: Iterable[int] | None = None,
) -> int:
    """Choose an action using epsilon-greedy exploration."""
    actions = list(valid_actions) if valid_actions is not None else ACTION_SPACE
    if not actions:
        raise ValueError("valid_actions cannot be empty.")
    if rng.random() < epsilon:
        return int(rng.choice(actions))

    action_values = q_table.setdefault(state_bucket, {action: 0.0 for action in ACTION_SPACE})
    return max(actions, key=lambda action: action_values.get(action, 0.0))


def update_q(
    q_table: QTable,
    state_bucket: tuple,
    action: int,
    reward: float,
    next_bucket: tuple,
    alpha: float = 0.1,
    gamma: float = 0.9,
) -> None:
    """Apply one tabular Q-learning update."""
    current_values = q_table.setdefault(state_bucket, {candidate: 0.0 for candidate in ACTION_SPACE})
    next_values = q_table.setdefault(next_bucket, {candidate: 0.0 for candidate in ACTION_SPACE})
    current = current_values.get(action, 0.0)
    target = reward + gamma * max(next_values.values())
    current_values[action] = current + alpha * (target - current)


def train_q_policy(
    envs: list[ExecutionEnv],
    episodes: int = 10,
    epsilon: float = 0.20,
    alpha: float = 0.10,
    gamma: float = 0.90,
    seed: int = 42,
) -> QTable:
    """Train a small Q-table over provided execution environments."""
    rng = random.Random(seed)
    q_table: QTable = defaultdict(lambda: {action: 0.0 for action in ACTION_SPACE})

    for _ in range(episodes):
        for env in envs:
            state = env.reset()
            done = False
            while not done:
                state_bucket = bucket_state(state)
                action = choose_action(q_table, state_bucket, epsilon, rng)
                next_state, reward, done, _ = env.step(action)
                next_bucket = bucket_state(next_state)
                update_q(q_table, state_bucket, action, reward, next_bucket, alpha, gamma)
                state = next_state

    return dict(q_table)


def build_training_envs(
    data: pd.DataFrame,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    max_orders_per_ticker: int | None = 1,
) -> list[ExecutionEnv]:
    """Build one RL environment per generated parent order."""
    fill_config = fill_config or DEFAULT_FILL_CONFIG
    featured = add_microstructure_features(data) if "spread_proxy" not in data.columns else data
    parent_orders = generate_parent_orders(
        featured,
        max_orders_per_ticker=max_orders_per_ticker,
    )
    if not parent_orders:
        raise ValueError("No parent orders generated from input data.")
    return [
        ExecutionEnv(
            order=order,
            market_data=featured,
            strategies={},
            fill_model=fill_model,
            fill_config=fill_config,
        )
        for order in parent_orders
    ]


def save_q_table(q_table: QTable, path: str | Path = "artifacts/models/q_policy.pkl") -> Path:
    """Persist a learned Q-table to disk."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        pickle.dump(q_table, handle)
    return output_path


def load_q_table(path: str | Path) -> QTable:
    """Load a learned Q-table from disk."""
    with Path(path).open("rb") as handle:
        return pickle.load(handle)


def _bucket(value: float, thresholds: list[float]) -> str:
    """Bucket a numeric value using two thresholds."""
    if value < thresholds[0]:
        return "low"
    if value < thresholds[1]:
        return "medium"
    return "high"


def _alpha_bucket(value: float) -> str:
    """Bucket alpha into negative, neutral, and positive."""
    if value < -1e-9:
        return "negative"
    if value > 1e-9:
        return "positive"
    return "neutral"
