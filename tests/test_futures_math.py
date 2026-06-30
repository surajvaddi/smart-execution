from __future__ import annotations

import pytest

from src.futures_math import contracts_to_notional, price_move_to_ticks, tick_value, ticks_to_dollars
from src.instruments import load_builtin_instrument_specs


def future_spec():
    return load_builtin_instrument_specs()["FUT_ESU26"]


def equity_spec():
    return load_builtin_instrument_specs()["EQ_SPY"]


def test_tick_value_uses_tick_size_and_contract_multiplier() -> None:
    assert tick_value(future_spec()) == pytest.approx(12.5)


def test_price_move_to_ticks_converts_absolute_move() -> None:
    assert price_move_to_ticks(1.0, future_spec()) == pytest.approx(4.0)


def test_contracts_to_notional_scales_by_price_and_multiplier() -> None:
    assert contracts_to_notional(5000.0, 2.0, future_spec()) == pytest.approx(5000.0 * 2.0 * 50.0)


def test_ticks_to_dollars_scales_by_contracts() -> None:
    assert ticks_to_dollars(4.0, 3.0, future_spec()) == pytest.approx(150.0)


def test_futures_math_rejects_non_future_specs() -> None:
    with pytest.raises(ValueError, match="future InstrumentSpec"):
        tick_value(equity_spec())
