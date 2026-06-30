from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from src.execution import ParentOrder
from src.strategies_adaptive_participation import (
    AdaptiveParticipationStrategy,
    generate_adaptive_participation_schedule,
    target_participation_rate,
)
from src.strategy_config import AdaptiveParticipationConfig


def sample_market_data() -> pd.DataFrame:
    index = pd.date_range("2026-01-02 10:00:00", periods=4, freq="5min", tz="America/New_York")
    return pd.DataFrame(
        {
            "ticker": ["XYZ"] * 4,
            "date": [pd.Timestamp("2026-01-02").date()] * 4,
            "time": [ts.time() for ts in index],
            "close": [100.0, 100.1, 100.2, 100.3],
            "volume": [1_000.0, 1_000.0, 1_000.0, 1_000.0],
            "alpha_signal": [0.8, 0.3, -0.4, -0.7],
            "rolling_vol": [0.01, 0.02, 0.04, 0.05],
            "liquidity_score": [0.8, 0.6, 0.3, 0.1],
        },
        index=index,
    )


def sample_parent_order(side: str = "buy", participation_cap: float = 0.20) -> ParentOrder:
    return ParentOrder(
        ticker="XYZ",
        side=side,
        quantity=300.0,
        start_time=time(10, 0),
        end_time=time(10, 15),
        participation_cap=participation_cap,
        date=pd.Timestamp("2026-01-02").date(),
        order_id=f"adaptive_participation_{side}",
    )


def test_target_participation_rate_rises_with_signal_and_liquidity() -> None:
    config = AdaptiveParticipationConfig(base_participation_rate=0.10)
    low = target_participation_rate(
        pd.Series({"alpha_signal": 0.0, "liquidity_score": 0.1, "rolling_vol": 0.01}),
        "buy",
        config,
    )
    high = target_participation_rate(
        pd.Series({"alpha_signal": 1.0, "liquidity_score": 0.8, "rolling_vol": 0.01}),
        "buy",
        config,
    )

    assert high > low


def test_target_participation_rate_falls_with_volatility() -> None:
    config = AdaptiveParticipationConfig(base_participation_rate=0.10)
    calm = target_participation_rate(
        pd.Series({"alpha_signal": 0.2, "liquidity_score": 0.5, "rolling_vol": 0.01}),
        "buy",
        config,
    )
    volatile = target_participation_rate(
        pd.Series({"alpha_signal": 0.2, "liquidity_score": 0.5, "rolling_vol": 0.10}),
        "buy",
        config,
    )

    assert calm > volatile


def test_generate_adaptive_participation_schedule_varies_child_quantities() -> None:
    schedule = generate_adaptive_participation_schedule(sample_parent_order(), sample_market_data())

    assert schedule["quantity"].sum() == pytest.approx(300.0)
    assert schedule["quantity"].nunique() > 1
    assert schedule.iloc[0]["quantity"] > schedule.iloc[-1]["quantity"]


def test_sell_target_participation_rate_accelerates_under_negative_signal() -> None:
    config = AdaptiveParticipationConfig(base_participation_rate=0.10)
    weaker_sell = target_participation_rate(
        pd.Series({"alpha_signal": 0.3, "liquidity_score": 0.5, "rolling_vol": 0.02}),
        "sell",
        config,
    )
    stronger_sell = target_participation_rate(
        pd.Series({"alpha_signal": -0.8, "liquidity_score": 0.5, "rolling_vol": 0.02}),
        "sell",
        config,
    )

    assert stronger_sell > weaker_sell
