"""Event schema for the synthetic limit-order-book stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from src.lob_types import RestingOrder, VALID_BOOK_SIDES


VALID_EVENT_TYPES = {"limit_add", "market_order", "cancel", "modify"}


@dataclass(frozen=True)
class LobEvent:
    """Base event fields shared across all LOB events."""

    event_id: str
    event_time: pd.Timestamp
    effective_time: pd.Timestamp
    instrument_id: str
    source: str
    random_seed: int | None
    event_type: str

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be non-empty.")
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")
        if not self.source:
            raise ValueError("source must be non-empty.")
        if self.event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of {sorted(VALID_EVENT_TYPES)}, got {self.event_type!r}."
            )
        _require_timestamp(self.event_time, "event_time")
        _require_timestamp(self.effective_time, "effective_time")
        if self.effective_time < self.event_time:
            raise ValueError("effective_time must be on or after event_time.")
        if self.random_seed is not None and not isinstance(self.random_seed, int):
            raise ValueError("random_seed must be an integer or None.")


@dataclass(frozen=True)
class LimitAddEvent(LobEvent):
    """Resting limit-order submission."""

    order: RestingOrder

    def __init__(
        self,
        event_id: str,
        event_time: pd.Timestamp,
        effective_time: pd.Timestamp,
        instrument_id: str,
        source: str,
        random_seed: int | None,
        order: RestingOrder,
    ) -> None:
        super().__init__(event_id, event_time, effective_time, instrument_id, source, random_seed, "limit_add")
        object.__setattr__(self, "order", order)
        if order.instrument_id != instrument_id:
            raise ValueError("order.instrument_id must match event instrument_id.")


@dataclass(frozen=True)
class MarketOrderEvent(LobEvent):
    """Aggressive market-order submission."""

    side: Literal["buy", "sell"]
    quantity: float
    parent_order_id: str | None = None
    child_order_id: str | None = None

    def __init__(
        self,
        event_id: str,
        event_time: pd.Timestamp,
        effective_time: pd.Timestamp,
        instrument_id: str,
        source: str,
        random_seed: int | None,
        side: Literal["buy", "sell"],
        quantity: float,
        parent_order_id: str | None = None,
        child_order_id: str | None = None,
    ) -> None:
        super().__init__(event_id, event_time, effective_time, instrument_id, source, random_seed, "market_order")
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "parent_order_id", parent_order_id)
        object.__setattr__(self, "child_order_id", child_order_id)
        if side not in VALID_BOOK_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_BOOK_SIDES)}, got {side!r}.")
        if quantity <= 0:
            raise ValueError("quantity must be positive.")


@dataclass(frozen=True)
class CancelEvent(LobEvent):
    """Cancellation of part or all of a resting order."""

    order_id: str
    cancel_quantity: float | None = None

    def __init__(
        self,
        event_id: str,
        event_time: pd.Timestamp,
        effective_time: pd.Timestamp,
        instrument_id: str,
        source: str,
        random_seed: int | None,
        order_id: str,
        cancel_quantity: float | None = None,
    ) -> None:
        super().__init__(event_id, event_time, effective_time, instrument_id, source, random_seed, "cancel")
        object.__setattr__(self, "order_id", order_id)
        object.__setattr__(self, "cancel_quantity", cancel_quantity)
        if not order_id:
            raise ValueError("order_id must be non-empty.")
        if cancel_quantity is not None and cancel_quantity <= 0:
            raise ValueError("cancel_quantity must be positive when provided.")


@dataclass(frozen=True)
class ModifyEvent(LobEvent):
    """Modification of a resting order."""

    order_id: str
    new_price: float | None = None
    new_visible_quantity: float | None = None
    new_reserve_quantity: float | None = None

    def __init__(
        self,
        event_id: str,
        event_time: pd.Timestamp,
        effective_time: pd.Timestamp,
        instrument_id: str,
        source: str,
        random_seed: int | None,
        order_id: str,
        new_price: float | None = None,
        new_visible_quantity: float | None = None,
        new_reserve_quantity: float | None = None,
    ) -> None:
        super().__init__(event_id, event_time, effective_time, instrument_id, source, random_seed, "modify")
        object.__setattr__(self, "order_id", order_id)
        object.__setattr__(self, "new_price", new_price)
        object.__setattr__(self, "new_visible_quantity", new_visible_quantity)
        object.__setattr__(self, "new_reserve_quantity", new_reserve_quantity)
        if not order_id:
            raise ValueError("order_id must be non-empty.")
        if new_price is not None and new_price <= 0:
            raise ValueError("new_price must be positive when provided.")
        if new_visible_quantity is not None and new_visible_quantity < 0:
            raise ValueError("new_visible_quantity must be non-negative when provided.")
        if new_reserve_quantity is not None and new_reserve_quantity < 0:
            raise ValueError("new_reserve_quantity must be non-negative when provided.")
        if new_price is None and new_visible_quantity is None and new_reserve_quantity is None:
            raise ValueError("ModifyEvent must change at least one field.")


@dataclass(frozen=True)
class EventBatch:
    """Deterministic ordered batch of events."""

    events: tuple[LobEvent, ...] = field(default_factory=tuple)

    def sorted_events(self) -> tuple[LobEvent, ...]:
        """Return events sorted by effective time, event time, and id."""
        return tuple(
            sorted(
                self.events,
                key=lambda event: (event.effective_time, event.event_time, event.event_id),
            )
        )


def _require_timestamp(value: pd.Timestamp, label: str) -> None:
    """Validate that a timestamp is timezone-aware and concrete."""
    if not isinstance(value, pd.Timestamp):
        raise ValueError(f"{label} must be a pandas Timestamp.")
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware.")
