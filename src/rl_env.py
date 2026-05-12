"""Research environment for adaptive ensemble execution.

This module is a simulator for experimentation, not production trading logic.
It turns one parent order into a bar-by-bar episode where an agent chooses among
rate, limit, and fill behaviors using only current or prior state information.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import pandas as pd

from src.execution import ParentOrder, filter_execution_window
from src.features import estimate_volume_curve
from src.fill_simulator import DEFAULT_FILL_MODEL, place_and_simulate_fills


RL_STRATEGY_NAME = "RLAdaptiveEnsemble"
ACTION_SPACE = list(range(9))


@dataclass(frozen=True)
class RewardConfig:
    """Configurable reward weights for the RL execution simulator."""

    impact_weight: float = 0.50
    spread_weight: float = 0.25
    lag_weight: float = 2.00
    fill_rate_target: float = 0.98
    terminal_unfilled_penalty_bps: float = 500.0
    adverse_selection_weight: float = 0.50


class ExecutionEnv:
    """Bar-by-bar execution environment for one parent order.

    State construction intentionally avoids future bars. Fill outcomes and
    adverse-selection feedback can use post-action realized data because they
    are reward feedback, not policy state.
    """

    state_schema = [
        "time_remaining",
        "fraction_completed",
        "remaining_quantity_fraction",
        "current_bar_volume",
        "spread_proxy",
        "rolling_vol",
        "volume_zscore",
        "liquidity_score",
        "alpha_signal",
        "recent_return",
        "current_participation_used",
        "prior_limit_filled",
        "prior_fill_rate",
        "prior_spread_cost",
        "prior_impact_cost",
    ]

    def __init__(
        self,
        order: ParentOrder,
        market_data: pd.DataFrame,
        strategies: dict[str, Any] | None = None,
        fill_model: str | None = None,
        reward_config: RewardConfig | None = None,
    ) -> None:
        """Create one RL execution episode."""
        self.order = order
        self.market_data = market_data
        self.strategies = strategies or {}
        self.fill_model = fill_model or DEFAULT_FILL_MODEL
        self.reward_config = reward_config or RewardConfig()

        ticker_data = market_data[market_data["ticker"] == order.ticker]
        if order.date is not None:
            ticker_data = ticker_data[ticker_data["date"] == order.date]
        self.window = filter_execution_window(ticker_data, order.start_time, order.end_time).sort_index()
        if self.window.empty:
            raise ValueError(f"No market data available for parent order {order.order_id}.")

        self.volume_curve = estimate_volume_curve(market_data)
        self.reset()

    def reset(self) -> pd.Series:
        """Reset the episode and return the initial state."""
        self.current_index = 0
        self.remaining_quantity = float(self.order.quantity)
        self.filled_quantity = 0.0
        self.done = False
        self.fills: list[pd.DataFrame] = []
        self.prior_limit_filled = 0.0
        self.prior_fill_rate = 0.0
        self.prior_spread_cost = 0.0
        self.prior_impact_cost = 0.0
        self.current_participation_used = 0.0
        return self._build_state()

    def step(self, action: int) -> tuple[pd.Series, float, bool, dict[str, Any]]:
        """Apply one discrete action and advance exactly one market bar."""
        if action not in ACTION_SPACE:
            raise ValueError(f"action must be one of {ACTION_SPACE}, got {action!r}.")
        if self.done:
            return self._build_state(), 0.0, True, {"already_done": True}

        fill_result = self._apply_action(action)
        reward = self._compute_reward(fill_result)
        self.current_index += 1
        self.done = self._is_done()
        next_state = self._build_state()

        info = {
            "action": action,
            "submitted_quantity": fill_result["submitted_quantity"],
            "filled_quantity": fill_result["filled_quantity"],
            "remaining_quantity": self.remaining_quantity,
            "placement_style": fill_result["placement_style"],
            "fills": fill_result["fills"],
        }
        return next_state, float(reward), self.done, info

    def _build_state(self) -> pd.Series:
        """Build the current state vector from current and prior information."""
        row = self._current_row()
        bars_total = len(self.window)
        bars_remaining = max(bars_total - self.current_index, 0)
        fraction_completed = self.filled_quantity / self.order.quantity

        state = {
            "time_remaining": bars_remaining / bars_total if bars_total else 0.0,
            "fraction_completed": fraction_completed,
            "remaining_quantity_fraction": self.remaining_quantity / self.order.quantity,
            "current_bar_volume": float(row.get("volume", 0.0)) if row is not None else 0.0,
            "spread_proxy": float(row.get("spread_proxy", 0.0)) if row is not None else 0.0,
            "rolling_vol": float(row.get("rolling_vol", 0.0)) if row is not None else 0.0,
            "volume_zscore": float(row.get("volume_zscore", 0.0)) if row is not None else 0.0,
            "liquidity_score": float(row.get("liquidity_score", 0.0)) if row is not None else 0.0,
            "alpha_signal": float(row.get("alpha_signal", 0.0)) if row is not None else 0.0,
            "recent_return": float(row.get("returns", 0.0)) if row is not None else 0.0,
            "current_participation_used": self.current_participation_used,
            "prior_limit_filled": self.prior_limit_filled,
            "prior_fill_rate": self.prior_fill_rate,
            "prior_spread_cost": self.prior_spread_cost,
            "prior_impact_cost": self.prior_impact_cost,
        }
        clean_state = {
            key: 0.0 if pd.isna(value) else float(value)
            for key, value in state.items()
        }
        return pd.Series(clean_state, index=self.state_schema, dtype=float)

    def _apply_action(self, action: int) -> dict[str, Any]:
        """Convert one action into at most one child order and simulated fill."""
        row = self._current_row()
        timestamp = self.window.index[self.current_index]
        if action == 0 or self.remaining_quantity <= 0:
            self.current_participation_used = 0.0
            self.prior_limit_filled = 0.0
            self.prior_fill_rate = 0.0
            self.prior_spread_cost = 0.0
            self.prior_impact_cost = 0.0
            return self._empty_step_result(action, None)

        target_quantity = self._action_quantity(action, row)
        child_quantity = self._cap_quantity(target_quantity, row)
        if child_quantity <= 0:
            return self._empty_step_result(action, None)

        placement_style = self._action_placement(action)
        child_order = pd.DataFrame(
            {
                "timestamp": [timestamp],
                "ticker": [self.order.ticker],
                "side": [self.order.side],
                "strategy": [RL_STRATEGY_NAME],
                "quantity": [child_quantity],
                "reference_price": [float(row["close"])],
            }
        )
        fills = place_and_simulate_fills(
            child_orders=child_order,
            market_data=self.window,
            placement_style=placement_style,
            parent_order=self.order,
            fill_model=self.fill_model,
        )

        filled_quantity = min(float(fills["quantity"].sum()), self.remaining_quantity)
        self.remaining_quantity = max(self.remaining_quantity - filled_quantity, 0.0)
        self.filled_quantity = min(self.filled_quantity + filled_quantity, self.order.quantity)
        self.current_participation_used = child_quantity / float(row["volume"]) if float(row["volume"]) > 0 else 0.0
        self.prior_fill_rate = filled_quantity / child_quantity if child_quantity > 0 else 0.0
        self.prior_limit_filled = (
            1.0
            if placement_style in {"passive_limit", "aggressive_limit"} and filled_quantity > 0
            else 0.0
        )
        self.prior_spread_cost = float((fills["spread_cost"] * fills["quantity"]).sum() / filled_quantity) if filled_quantity > 0 else 0.0
        self.prior_impact_cost = float((fills["impact_cost"] * fills["quantity"]).sum() / filled_quantity) if filled_quantity > 0 else 0.0
        self.fills.append(fills)

        return {
            "action": action,
            "placement_style": placement_style,
            "submitted_quantity": child_quantity,
            "filled_quantity": filled_quantity,
            "fills": fills,
        }

    def _compute_reward(self, fill_result: dict[str, Any]) -> float:
        """Return negative incremental execution cost plus schedule penalties."""
        cfg = self.reward_config
        fills = fill_result["fills"]
        filled_quantity = fill_result["filled_quantity"]
        row = self._previous_row_after_apply()
        arrival_px = float(self.window.iloc[0]["close"])

        if filled_quantity > 0 and fills is not None and not fills.empty:
            avg_fill = float((fills["fill_price"] * fills["quantity"]).sum() / filled_quantity)
            if self.order.side == "buy":
                shortfall = avg_fill - arrival_px
            else:
                shortfall = arrival_px - avg_fill
            shortfall_bps = 10_000 * shortfall / arrival_px
            spread_bps = self._weighted_fill_cost_bps(fills, "spread_cost", arrival_px)
            impact_bps = self._weighted_fill_cost_bps(fills, "impact_cost", arrival_px)
            adverse_bps = self._weighted_fill_cost_bps(fills, "adverse_selection_cost", arrival_px)
        else:
            shortfall_bps = 0.0
            spread_bps = 0.0
            impact_bps = 0.0
            adverse_bps = 0.0

        elapsed_fraction = (self.current_index + 1) / len(self.window)
        completed_fraction = self.filled_quantity / self.order.quantity
        schedule_lag_penalty = max(elapsed_fraction - completed_fraction, 0.0) * 100.0
        terminal_penalty = 0.0
        if self.current_index + 1 >= len(self.window):
            fill_rate = self.filled_quantity / self.order.quantity
            shortfall_to_target = max(cfg.fill_rate_target - fill_rate, 0.0)
            terminal_penalty = shortfall_to_target * cfg.terminal_unfilled_penalty_bps

        reward = (
            -shortfall_bps
            - cfg.impact_weight * impact_bps
            - cfg.spread_weight * spread_bps
            - cfg.adverse_selection_weight * adverse_bps
            - cfg.lag_weight * schedule_lag_penalty
            - terminal_penalty
        )
        if row is None or not math.isfinite(reward):
            return 0.0
        return float(reward)

    def _is_done(self) -> bool:
        """Return whether the episode has completed."""
        return self.remaining_quantity <= 1e-9 or self.current_index >= len(self.window)

    def fill_frame(self) -> pd.DataFrame:
        """Return all simulated fills emitted by the episode."""
        if not self.fills:
            return pd.DataFrame()
        return pd.concat(self.fills, ignore_index=True)

    def _current_row(self) -> pd.Series | None:
        """Return the current market row, or the final row after episode end."""
        if self.window.empty:
            return None
        idx = min(self.current_index, len(self.window) - 1)
        return self.window.iloc[idx]

    def _previous_row_after_apply(self) -> pd.Series | None:
        """Return the row just acted on during reward calculation."""
        if self.window.empty:
            return None
        idx = min(self.current_index, len(self.window) - 1)
        return self.window.iloc[idx]

    def _empty_step_result(self, action: int, placement_style: str | None) -> dict[str, Any]:
        """Return a no-fill step result."""
        return {
            "action": action,
            "placement_style": placement_style,
            "submitted_quantity": 0.0,
            "filled_quantity": 0.0,
            "fills": pd.DataFrame(),
        }

    def _action_quantity(self, action: int, row: pd.Series) -> float:
        """Return the uncapped quantity suggested by one discrete action."""
        if action == 1:
            return self._twap_quantity()
        if action == 2:
            return self._vwap_quantity(row)
        if action == 3:
            return self._pov_quantity(row)
        if action == 4:
            return self._adaptive_quantity(row)
        if action in {5, 7}:
            return 0.25 * self._pov_quantity(row)
        if action in {6, 8}:
            return 0.50 * self._pov_quantity(row)
        return 0.0

    def _action_placement(self, action: int) -> str:
        """Map action IDs to placement styles."""
        if action in {1, 2, 3, 4}:
            return "marketable_limit"
        if action in {5, 6}:
            return "passive_limit"
        if action in {7, 8}:
            return "aggressive_limit"
        return "marketable_limit"

    def _cap_quantity(self, quantity: float, row: pd.Series) -> float:
        """Apply inventory and participation caps to a child quantity."""
        cap = self.order.participation_cap * float(row["volume"])
        return float(max(min(quantity, self.remaining_quantity, cap), 0.0))

    def _twap_quantity(self) -> float:
        """Estimate current-bar TWAP quantity from remaining inventory."""
        remaining_bars = max(len(self.window) - self.current_index, 1)
        return self.remaining_quantity / remaining_bars

    def _vwap_quantity(self, row: pd.Series) -> float:
        """Estimate current-bar VWAP quantity from the historical volume curve."""
        remaining_window = self.window.iloc[self.current_index:]
        expected = remaining_window["bar_index"].map(self.volume_curve).fillna(0.0)
        remaining_expected = expected.sum()
        current_expected = float(self.volume_curve.get(row.get("bar_index"), 0.0))
        if remaining_expected <= 0 or current_expected <= 0:
            return self._twap_quantity()
        return self.remaining_quantity * current_expected / remaining_expected

    def _pov_quantity(self, row: pd.Series) -> float:
        """Estimate current-bar POV quantity from realized bar volume."""
        return self.order.participation_cap * float(row["volume"])

    def _adaptive_quantity(self, row: pd.Series) -> float:
        """Estimate current-bar adaptive quantity from local proxy signals."""
        base = self._twap_quantity()
        multiplier = 1.0
        alpha = float(row.get("alpha_signal", 0.0))
        liquidity = float(row.get("liquidity_score", 0.0))
        spread = float(row.get("spread_proxy", 0.0))
        rolling_vol = float(row.get("rolling_vol", 0.0))

        if (self.order.side == "buy" and alpha > 0) or (self.order.side == "sell" and alpha < 0):
            multiplier *= 1.3
        elif alpha != 0:
            multiplier *= 0.8

        if liquidity > self.window["liquidity_score"].quantile(0.75):
            multiplier *= 1.2
        if spread > self.window["spread_proxy"].quantile(0.75):
            multiplier *= 0.8
        if rolling_vol > self.window["rolling_vol"].quantile(0.75):
            multiplier *= 0.85

        elapsed_fraction = self.current_index / max(len(self.window), 1)
        completed_fraction = self.filled_quantity / self.order.quantity
        urgency = 1.0 + max(elapsed_fraction - completed_fraction, 0.0)
        return base * multiplier * urgency

    @staticmethod
    def _weighted_fill_cost_bps(fills: pd.DataFrame, cost_col: str, reference_price: float) -> float:
        """Return weighted cost in bps for a single-step fill frame."""
        if cost_col not in fills.columns or fills.empty:
            return 0.0
        quantity = fills["quantity"].sum()
        if quantity <= 0 or reference_price <= 0:
            return 0.0
        weighted_cost = (fills[cost_col] * fills["quantity"]).sum() / quantity
        return float(10_000 * weighted_cost / reference_price)
