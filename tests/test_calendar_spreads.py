from __future__ import annotations

import pandas as pd
import pytest

from src.calendar_spreads import price_calendar_spread, spread_notional, spread_tick_value
from src.instruments import InstrumentSpec, load_builtin_instrument_specs


def front_spec():
    return load_builtin_instrument_specs()["FUT_ESU26"]


def back_spec() -> InstrumentSpec:
    return InstrumentSpec(
        instrument_id="FUT_ESZ26",
        ticker="ESZ26",
        instrument_type="future",
        quote_currency="USD",
        base_currency="ES",
        tick_size=0.25,
        contract_multiplier=50.0,
        session_timezone="America/Chicago",
        trading_hours="17:00-16:00",
        expiry_date=pd.Timestamp("2026-12-18 17:00:00", tz="America/Chicago"),
        roll_rule="volume_based",
    )


def test_price_calendar_spread_uses_back_minus_front() -> None:
    assert price_calendar_spread(5000.0, 5010.0) == pytest.approx(10.0)


def test_spread_tick_value_uses_compatible_futures_tick_value() -> None:
    assert spread_tick_value(front_spec(), back_spec()) == pytest.approx(12.5)


def test_spread_notional_adds_both_legs() -> None:
    notional = spread_notional(5000.0, 5010.0, 2.0, front_spec(), back_spec())

    assert notional == pytest.approx((5000.0 * 2.0 * 50.0) + (5010.0 * 2.0 * 50.0))


def test_calendar_spread_rejects_incompatible_legs() -> None:
    fx_spec = load_builtin_instrument_specs()["FX_EURUSD_SPOT"]

    with pytest.raises(ValueError, match="future InstrumentSpecs"):
        spread_tick_value(front_spec(), fx_spec)
