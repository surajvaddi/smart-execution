"""Instrument specification helpers for equities, futures, and FX spot."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


VALID_INSTRUMENT_TYPES = {"equity", "future", "fx_spot"}


@dataclass(frozen=True)
class InstrumentSpec:
    """Canonical instrument metadata for execution research workflows."""

    instrument_id: str
    ticker: str
    instrument_type: str
    quote_currency: str
    base_currency: str
    tick_size: float
    contract_multiplier: float
    session_timezone: str
    trading_hours: str
    expiry_date: pd.Timestamp | None = None
    roll_rule: str | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")
        if not self.ticker:
            raise ValueError("ticker must be non-empty.")
        if self.instrument_type not in VALID_INSTRUMENT_TYPES:
            raise ValueError(
                f"instrument_type must be one of {sorted(VALID_INSTRUMENT_TYPES)}, got {self.instrument_type!r}."
            )
        if not self.quote_currency:
            raise ValueError("quote_currency must be non-empty.")
        if not self.base_currency:
            raise ValueError("base_currency must be non-empty.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive.")
        if self.contract_multiplier <= 0:
            raise ValueError("contract_multiplier must be positive.")
        if not self.session_timezone:
            raise ValueError("session_timezone must be non-empty.")
        if not self.trading_hours:
            raise ValueError("trading_hours must be non-empty.")
        if self.instrument_type == "future" and self.roll_rule is None:
            raise ValueError("future instruments must define a roll_rule.")
        if self.expiry_date is not None and self.expiry_date.tzinfo is None:
            raise ValueError("expiry_date must be timezone-aware when provided.")


def load_builtin_instrument_specs() -> dict[str, InstrumentSpec]:
    """Return a small built-in registry of representative research instruments."""
    expiry = pd.Timestamp("2026-09-18 17:00:00", tz="America/Chicago")
    specs = [
        InstrumentSpec(
            instrument_id="EQ_SPY",
            ticker="SPY",
            instrument_type="equity",
            quote_currency="USD",
            base_currency="SPY",
            tick_size=0.01,
            contract_multiplier=1.0,
            session_timezone="America/New_York",
            trading_hours="09:30-16:00",
        ),
        InstrumentSpec(
            instrument_id="FUT_ESU26",
            ticker="ESU26",
            instrument_type="future",
            quote_currency="USD",
            base_currency="ES",
            tick_size=0.25,
            contract_multiplier=50.0,
            session_timezone="America/Chicago",
            trading_hours="17:00-16:00",
            expiry_date=expiry,
            roll_rule="volume_based",
        ),
        InstrumentSpec(
            instrument_id="FX_EURUSD_SPOT",
            ticker="EURUSD",
            instrument_type="fx_spot",
            quote_currency="USD",
            base_currency="EUR",
            tick_size=0.0001,
            contract_multiplier=1.0,
            session_timezone="UTC",
            trading_hours="00:00-24:00",
        ),
    ]
    return {spec.instrument_id: spec for spec in specs}


def lookup_instrument_spec(
    instrument_id: str | None = None,
    ticker: str | None = None,
    specs: dict[str, InstrumentSpec] | None = None,
) -> InstrumentSpec:
    """Lookup an instrument spec by canonical id or ticker."""
    registry = specs or load_builtin_instrument_specs()
    if not instrument_id and not ticker:
        raise ValueError("Provide instrument_id or ticker.")

    if instrument_id is not None:
        try:
            return registry[instrument_id]
        except KeyError as exc:
            raise KeyError(f"Unknown instrument_id: {instrument_id}") from exc

    normalized_ticker = str(ticker).upper()
    for spec in registry.values():
        if spec.ticker.upper() == normalized_ticker:
            return spec
    raise KeyError(f"Unknown ticker: {ticker}")
