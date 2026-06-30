from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from src.execution import ParentOrder
from src.strategies_is import (
    ImplementationShortfallStrategy,
    compute_risk_adjusted_urgency,
    frontload_fraction_from_alpha,
    generate_is_schedule,
)


def sample_market_data(alpha_signal: float, rolling_vol: float) -> pd.DataFrame:
    index = pd.date_range("2026-01-02 10:00:00", periods=4, freq="5min", tz="America/New_York")
    return pd.DataFrame(
        {
            "ticker": ["XYZ"] * 4,
            "date": [pd.Timestamp("2026-01-02").date()] * 4,
            "time": [ts.time() for ts in index],
            "close": [100.0, 100.1, 100.2, 100.3],
            "volume": [1_000.0] * 4,
            "alpha_signal": [alpha_signal] * 4,
            "rolling_vol": [rolling_vol] * 4,
        },
        index=index,
    )


def sample_parent_order(side: str = "buy", participation_cap: float = 1.0) -> ParentOrder:
    return ParentOrder(
        ticker="XYZ",
        side=side,
        quantity=400.0,
        start_time=time(10, 0),
        end_time=time(10, 15),
        participation_cap=participation_cap,
        date=pd.Timestamp("2026-01-02").date(),
        order_id=f"parent_{side}",
    )


def test_frontload_fraction_from_alpha_is_directional_by_side() -> None:
    assert frontload_fraction_from_alpha(1.0, "buy") > 0
    assert frontload_fraction_from_alpha(-1.0, "sell") > 0
    assert frontload_fraction_from_alpha(-1.0, "buy") < 0


def test_compute_risk_adjusted_urgency_increases_with_volatility_and_risk() -> None:
    low = compute_risk_adjusted_urgency(rolling_volatility=0.01, participation_cap=0.5, risk_aversion=0.5)
    high = compute_risk_adjusted_urgency(rolling_volatility=0.05, participation_cap=0.5, risk_aversion=2.0)

    assert high > low > 1.0


def test_generate_is_schedule_frontloads_buy_on_positive_alpha() -> None:
    schedule = generate_is_schedule(
        sample_parent_order(side="buy"),
        sample_market_data(alpha_signal=1.5, rolling_vol=0.02),
        risk_aversion=1.0,
    )

    assert schedule["quantity"].sum() == pytest.approx(400.0)
    assert schedule.iloc[0]["quantity"] > schedule.iloc[-1]["quantity"]


def test_generate_is_schedule_frontloads_sell_on_negative_alpha() -> None:
    schedule = generate_is_schedule(
        sample_parent_order(side="sell"),
        sample_market_data(alpha_signal=-1.5, rolling_vol=0.02),
        risk_aversion=1.0,
    )

    assert schedule["quantity"].sum() == pytest.approx(400.0)
    assert schedule.iloc[0]["quantity"] > schedule.iloc[-1]["quantity"]


def test_implementation_shortfall_strategy_frontloads_more_under_higher_risk_aversion() -> None:
    data = sample_market_data(alpha_signal=1.0, rolling_vol=0.05)
    low_risk = ImplementationShortfallStrategy(risk_aversion=0.5).generate_child_orders(
        sample_parent_order(side="buy"),
        data,
    )
    high_risk = ImplementationShortfallStrategy(risk_aversion=2.0).generate_child_orders(
        sample_parent_order(side="buy"),
        data,
    )

    assert high_risk.iloc[0]["quantity"] > low_risk.iloc[0]["quantity"]
