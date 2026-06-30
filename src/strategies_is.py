"""Implementation shortfall schedule for bar-based execution research."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.execution import ParentOrder
from src.strategies import ExecutionStrategy


def frontload_fraction_from_alpha(
    alpha_signal: float,
    side: str,
    max_frontload: float = 0.30,
) -> float:
    """Map directional alpha into a bounded front-loading fraction."""
    if max_frontload < 0:
        raise ValueError("max_frontload must be non-negative.")

    directional_alpha = float(alpha_signal if side == "buy" else -alpha_signal)
    scaled = np.tanh(directional_alpha)
    return float(max(-max_frontload, min(max_frontload, max_frontload * scaled)))


def compute_risk_adjusted_urgency(
    rolling_volatility: float,
    participation_cap: float,
    risk_aversion: float = 1.0,
) -> float:
    """Return an urgency multiplier from volatility, liquidity cap, and risk aversion."""
    if participation_cap <= 0:
        raise ValueError("participation_cap must be positive.")
    if risk_aversion < 0:
        raise ValueError("risk_aversion must be non-negative.")

    volatility_term = max(float(rolling_volatility), 0.0)
    cap_term = max(float(participation_cap), 1e-9)
    urgency = 1.0 + risk_aversion * volatility_term / cap_term
    return float(max(1.0, urgency))


def generate_is_schedule(
    order: ParentOrder,
    data: pd.DataFrame,
    risk_aversion: float = 1.0,
    max_frontload: float = 0.30,
) -> pd.DataFrame:
    """Generate a front-loaded schedule for implementation shortfall control."""
    strategy = ImplementationShortfallStrategy(
        risk_aversion=risk_aversion,
        max_frontload=max_frontload,
    )
    return strategy.generate_child_orders(order, data)


class ImplementationShortfallStrategy(ExecutionStrategy):
    """Front-loaded schedule that reacts to alpha and volatility."""

    name = "ImplementationShortfall"

    def __init__(self, risk_aversion: float = 1.0, max_frontload: float = 0.30) -> None:
        if risk_aversion < 0:
            raise ValueError("risk_aversion must be non-negative.")
        if max_frontload < 0:
            raise ValueError("max_frontload must be non-negative.")
        self.risk_aversion = float(risk_aversion)
        self.max_frontload = float(max_frontload)

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate a risk-aware front-loaded child-order schedule."""
        window = self.market_window(order, data).copy()
        required_features = ["alpha_signal", "rolling_vol", "volume", "close"]
        missing = [column for column in required_features if column not in window.columns]
        if missing:
            raise ValueError(f"Missing required implementation shortfall columns: {missing}")

        mean_alpha = float(window["alpha_signal"].mean())
        mean_volatility = float(window["rolling_vol"].fillna(0.0).mean())
        urgency = compute_risk_adjusted_urgency(
            mean_volatility,
            order.participation_cap,
            risk_aversion=self.risk_aversion,
        )
        frontload = frontload_fraction_from_alpha(
            mean_alpha,
            order.side,
            max_frontload=self.max_frontload,
        )

        n_bars = len(window)
        profile = np.linspace(1.0, -1.0, n_bars)
        raw_weights = 1.0 + urgency * frontload * profile
        clipped_weights = np.clip(raw_weights, 0.05, None)
        normalized_weights = clipped_weights / clipped_weights.sum()

        remaining_quantity = order.quantity
        timestamps = []
        quantities = []
        reference_prices = []

        for bar_number, (timestamp, row) in enumerate(window.iterrows()):
            remaining_bars = n_bars - bar_number
            target_fraction = normalized_weights[bar_number:].sum()
            target_quantity = remaining_quantity if remaining_bars == 1 else remaining_quantity * (
                normalized_weights[bar_number] / target_fraction
            )
            child_quantity = min(
                remaining_quantity,
                float(target_quantity),
                float(order.participation_cap * row["volume"]),
            )
            if remaining_bars == 1:
                child_quantity = min(remaining_quantity, float(order.participation_cap * row["volume"]))
            if child_quantity <= 0:
                continue

            timestamps.append(timestamp)
            quantities.append(float(child_quantity))
            reference_prices.append(float(row["close"]))
            remaining_quantity -= child_quantity

        return self.child_order_frame(
            order=order,
            timestamps=pd.Index(timestamps),
            quantities=quantities,
            reference_prices=reference_prices,
        )
