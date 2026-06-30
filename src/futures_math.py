"""Arithmetic helpers for futures price and contract normalization."""

from __future__ import annotations

from src.instruments import InstrumentSpec


def tick_value(spec: InstrumentSpec) -> float:
    """Return the dollar value of one tick for a futures contract."""
    _require_future(spec)
    return float(spec.tick_size * spec.contract_multiplier)


def price_move_to_ticks(price_move: float, spec: InstrumentSpec) -> float:
    """Convert an absolute futures price move into ticks."""
    _require_future(spec)
    return float(price_move / spec.tick_size)


def contracts_to_notional(price: float, contracts: float, spec: InstrumentSpec) -> float:
    """Convert futures contracts at a given price into notional dollars."""
    _require_future(spec)
    if price <= 0:
        raise ValueError("price must be positive.")
    return float(price * contracts * spec.contract_multiplier)


def ticks_to_dollars(ticks: float, contracts: float, spec: InstrumentSpec) -> float:
    """Convert a tick move across a number of contracts into dollar PnL/notional move."""
    _require_future(spec)
    return float(ticks * contracts * tick_value(spec))


def _require_future(spec: InstrumentSpec) -> None:
    """Validate that an instrument spec represents a futures contract."""
    if spec.instrument_type != "future":
        raise ValueError("futures math helpers require a future InstrumentSpec.")
