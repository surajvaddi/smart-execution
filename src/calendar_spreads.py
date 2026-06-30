"""Calendar spread pricing helpers for related futures contracts."""

from __future__ import annotations

from src.futures_math import contracts_to_notional, tick_value
from src.instruments import InstrumentSpec


def price_calendar_spread(front_price: float, back_price: float) -> float:
    """Return the back-minus-front calendar spread price."""
    return float(back_price - front_price)


def spread_tick_value(front_spec: InstrumentSpec, back_spec: InstrumentSpec) -> float:
    """Return the tick value for a compatible calendar spread pair."""
    _require_compatible_futures(front_spec, back_spec)
    return float(max(tick_value(front_spec), tick_value(back_spec)))


def spread_notional(
    front_price: float,
    back_price: float,
    contracts: float,
    front_spec: InstrumentSpec,
    back_spec: InstrumentSpec,
) -> float:
    """Return the gross notional represented by both legs of a calendar spread."""
    _require_compatible_futures(front_spec, back_spec)
    front_notional = contracts_to_notional(front_price, contracts, front_spec)
    back_notional = contracts_to_notional(back_price, contracts, back_spec)
    return float(front_notional + back_notional)


def _require_compatible_futures(front_spec: InstrumentSpec, back_spec: InstrumentSpec) -> None:
    """Validate that both legs are futures on the same underlying family."""
    if front_spec.instrument_type != "future" or back_spec.instrument_type != "future":
        raise ValueError("calendar spreads require two future InstrumentSpecs.")
    if front_spec.base_currency != back_spec.base_currency:
        raise ValueError("calendar spread legs must share the same base futures family.")
    if front_spec.quote_currency != back_spec.quote_currency:
        raise ValueError("calendar spread legs must share the same quote currency.")
