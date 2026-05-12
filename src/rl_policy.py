"""Simple policies for the adaptive ensemble RL execution environment."""

from __future__ import annotations

import random
from typing import Iterable

import pandas as pd

from src.rl_env import ACTION_SPACE


class RandomPolicy:
    """Random valid-action policy for exploration baselines."""

    def __init__(self, seed: int | None = 42) -> None:
        """Create a reproducible random policy."""
        self.rng = random.Random(seed)

    def select_action(self, state: pd.Series, valid_actions: Iterable[int] | None = None) -> int:
        """Return a random action from valid actions."""
        actions = list(valid_actions) if valid_actions is not None else ACTION_SPACE
        if not actions:
            raise ValueError("valid_actions cannot be empty.")
        return int(self.rng.choice(actions))


class HeuristicExecutionPolicy:
    """Rule-based policy that blends rate, limit, and urgency behavior."""

    def select_action(self, state: pd.Series, valid_actions: Iterable[int] | None = None) -> int:
        """Return a heuristic action for the current state."""
        actions = set(valid_actions) if valid_actions is not None else set(ACTION_SPACE)
        if not actions:
            raise ValueError("valid_actions cannot be empty.")

        urgency = self._urgency(state)
        spread = float(state.get("spread_proxy", 0.0))
        volatility = float(state.get("rolling_vol", 0.0))
        liquidity = float(state.get("liquidity_score", 0.0))
        remaining = float(state.get("remaining_quantity_fraction", 0.0))

        if urgency >= 0.75:
            return self._first_valid([8, 4, 3, 1], actions)
        if spread >= 0.02 and volatility >= 0.02:
            return self._first_valid([0, 5, 7], actions)
        if spread >= 0.015 and urgency < 0.45:
            return self._first_valid([6, 5, 2], actions)
        if liquidity >= 0.75 and remaining > 0.25:
            return self._first_valid([4, 3, 2], actions)
        if volatility >= 0.02:
            return self._first_valid([5, 0, 1], actions)
        return self._first_valid([2, 3, 1], actions)

    @staticmethod
    def _urgency(state: pd.Series) -> float:
        """Return a simple urgency score from time and remaining inventory."""
        time_remaining = max(float(state.get("time_remaining", 0.0)), 1e-9)
        remaining = float(state.get("remaining_quantity_fraction", 0.0))
        return max(0.0, min(1.0, remaining / time_remaining))

    @staticmethod
    def _first_valid(preferred: list[int], valid_actions: set[int]) -> int:
        """Return the first preferred action that is valid."""
        for action in preferred:
            if action in valid_actions:
                return action
        return min(valid_actions)
