from __future__ import annotations

import pandas as pd
import pytest

from src.futures_sessions import session_liquidity_profile, session_mask_for_instrument
from src.instruments import load_builtin_instrument_specs


def sample_session_data() -> pd.DataFrame:
    timestamps = pd.date_range("2026-01-02 15:55:00", periods=6, freq="5min", tz="America/Chicago")
    return pd.DataFrame(
        {
            "time": [ts.time() for ts in timestamps],
            "bar_index": list(range(len(timestamps))),
            "close": [5000.0, 5001.0, 5002.0, 5003.0, 5004.0, 5005.0],
            "volume": [100.0, 120.0, 140.0, 160.0, 180.0, 200.0],
        },
        index=timestamps,
    )


def equity_spec():
    return load_builtin_instrument_specs()["EQ_SPY"]


def future_spec():
    return load_builtin_instrument_specs()["FUT_ESU26"]


def test_session_mask_for_instrument_handles_regular_equity_hours() -> None:
    timestamps = pd.date_range("2026-01-02 09:25:00", periods=4, freq="5min", tz="America/New_York")
    data = pd.DataFrame({"time": [ts.time() for ts in timestamps]}, index=timestamps)

    mask = session_mask_for_instrument(data, equity_spec())

    assert mask.tolist() == [False, True, True, True]


def test_session_mask_for_instrument_handles_overnight_future_hours() -> None:
    mask = session_mask_for_instrument(sample_session_data(), future_spec())

    assert mask.tolist() == [True, True, False, False, False, False]


def test_session_liquidity_profile_summarizes_only_in_session_rows() -> None:
    profile = session_liquidity_profile(sample_session_data(), future_spec())

    assert profile["bar_index"].tolist() == [0, 1]
    assert profile["mean_volume"].tolist() == pytest.approx([100.0, 120.0])
    assert profile["session_share"].sum() == pytest.approx(1.0)
