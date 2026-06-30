from __future__ import annotations

import pandas as pd
import pytest

from src.instruments import InstrumentSpec, load_builtin_instrument_specs, lookup_instrument_spec


def test_instrument_spec_can_represent_equity_future_and_fx() -> None:
    specs = load_builtin_instrument_specs()

    assert specs["EQ_SPY"].instrument_type == "equity"
    assert specs["FUT_ESU26"].instrument_type == "future"
    assert specs["FX_EURUSD_SPOT"].instrument_type == "fx_spot"


def test_future_instrument_requires_roll_rule() -> None:
    with pytest.raises(ValueError, match="roll_rule"):
        InstrumentSpec(
            instrument_id="FUT_BAD",
            ticker="BAD",
            instrument_type="future",
            quote_currency="USD",
            base_currency="BAD",
            tick_size=0.25,
            contract_multiplier=50.0,
            session_timezone="America/Chicago",
            trading_hours="17:00-16:00",
            expiry_date=pd.Timestamp("2026-09-18 17:00:00", tz="America/Chicago"),
        )


def test_lookup_instrument_spec_supports_id_and_ticker() -> None:
    by_id = lookup_instrument_spec(instrument_id="EQ_SPY")
    by_ticker = lookup_instrument_spec(ticker="ESU26")

    assert by_id.ticker == "SPY"
    assert by_ticker.instrument_id == "FUT_ESU26"


def test_lookup_instrument_spec_rejects_unknown_values() -> None:
    with pytest.raises(KeyError, match="Unknown instrument_id"):
        lookup_instrument_spec(instrument_id="UNKNOWN")
    with pytest.raises(KeyError, match="Unknown ticker"):
        lookup_instrument_spec(ticker="UNKNOWN")
