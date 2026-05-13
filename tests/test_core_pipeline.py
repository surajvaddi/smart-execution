"""Core pipeline tests for data, features, signals, and strategies."""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd
import pytest

from src.data_loader import clean_intraday_data
from src.execution import ParentOrder
from src.features import FEATURE_COLUMNS, add_microstructure_features
from src.signals import add_forward_returns, decile_spread, hit_rate, information_coefficient
from src.strategies import AdaptiveStrategy, POVStrategy, TWAPStrategy, VWAPStrategy
from test_rl_env import sample_market_data


def test_clean_intraday_data_handles_multiindex_and_timezone() -> None:
    timestamps = pd.date_range("2026-01-02 15:00:00", periods=3, freq="5min", tz="UTC")
    raw = pd.DataFrame(
        {
            ("Open", "XYZ"): [100.0, 101.0, 102.0],
            ("High", "XYZ"): [101.0, 102.0, 103.0],
            ("Low", "XYZ"): [99.0, 100.0, 101.0],
            ("Close", "XYZ"): [100.5, 101.5, 102.5],
            ("Volume", "XYZ"): [1_000.0, 0.0, 1_200.0],
        },
        index=timestamps,
    )

    cleaned = clean_intraday_data(raw, "xyz")

    assert list(cleaned["ticker"].unique()) == ["XYZ"]
    assert len(cleaned) == 2
    assert cleaned.index.tz.zone == "America/New_York"
    assert cleaned.iloc[0]["time"] == time(10, 0)
    assert cleaned["volume"].min() > 0


def test_clean_intraday_data_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="No intraday data"):
        clean_intraday_data(pd.DataFrame(), "XYZ")


def test_features_do_not_bleed_between_tickers() -> None:
    first = sample_market_data()
    second = sample_market_data().copy()
    second["ticker"] = "ABC"
    second["close"] = second["close"] * 2
    second.index = second.index + pd.Timedelta(days=1)
    combined = pd.concat([first, second])

    featured = add_microstructure_features(combined)

    assert set(FEATURE_COLUMNS).issubset(featured.columns)
    abc_first = featured[featured["ticker"] == "ABC"].iloc[0]
    xyz_first = featured[featured["ticker"] == "XYZ"].iloc[0]
    assert pd.isna(abc_first["momentum_3"])
    assert pd.isna(xyz_first["momentum_3"])


def test_signal_metrics_handle_degenerate_data() -> None:
    data = pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0, 103.0],
            "signal": [1.0, 1.0, 1.0, 1.0],
        }
    )
    with_targets = add_forward_returns(data, [1])

    assert np.isnan(decile_spread(with_targets, "signal", "fwd_return_1"))
    assert hit_rate(with_targets, "signal", "fwd_return_1") == 1.0
    assert np.isnan(information_coefficient(with_targets, "signal", "fwd_return_1"))


def test_strategy_schedules_respect_expected_quantity_behavior() -> None:
    data = sample_market_data()
    order = ParentOrder(
        ticker="XYZ",
        side="buy",
        quantity=2_000.0,
        start_time=time(10, 0),
        end_time=time(10, 25),
        participation_cap=0.10,
        date=pd.Timestamp("2026-01-02").date(),
        order_id="XYZ_test",
    )

    twap = TWAPStrategy().generate_child_orders(order, data)
    vwap = VWAPStrategy().generate_child_orders(order, data)
    pov = POVStrategy().generate_child_orders(order, data)

    assert twap["quantity"].sum() == pytest.approx(order.quantity)
    assert (vwap.set_index("timestamp")["quantity"] <= data["volume"] * order.participation_cap).all()
    assert pov["quantity"].sum() <= order.quantity


def test_adaptive_strategy_requires_feature_columns() -> None:
    data = sample_market_data().drop(columns=["alpha_signal"])
    order = ParentOrder(
        ticker="XYZ",
        side="buy",
        quantity=2_000.0,
        start_time=time(10, 0),
        end_time=time(10, 25),
        participation_cap=0.10,
        date=pd.Timestamp("2026-01-02").date(),
        order_id="XYZ_test",
    )

    with pytest.raises(ValueError, match="Missing required adaptive strategy columns"):
        AdaptiveStrategy().generate_child_orders(order, data)
