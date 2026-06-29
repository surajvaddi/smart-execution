"""Latency helpers for synthetic exchange events."""

from __future__ import annotations

import random

import pandas as pd

from src.lob_events import CancelEvent, EventBatch, LimitAddEvent, LobEvent, MarketOrderEvent, ModifyEvent
from src.lob_simulator_config import LatencyModelConfig


def sample_gateway_latency(rng: random.Random, config: LatencyModelConfig) -> int:
    """Sample gateway latency in microseconds."""
    lo, hi = config.gateway_latency_us
    return int(rng.randint(lo, hi))


def sample_exchange_latency(rng: random.Random, config: LatencyModelConfig) -> int:
    """Sample exchange latency in microseconds."""
    lo, hi = config.exchange_latency_us
    return int(rng.randint(lo, hi))


def apply_event_latency(
    event: LobEvent,
    gateway_latency_us: int,
    exchange_latency_us: int,
) -> LobEvent:
    """Return a copy of an event with effective time shifted by latency."""
    total_latency = pd.to_timedelta(int(gateway_latency_us) + int(exchange_latency_us), unit="us")
    effective_time = event.event_time + total_latency

    common = {
        "event_id": event.event_id,
        "event_time": event.event_time,
        "effective_time": effective_time,
        "instrument_id": event.instrument_id,
        "source": event.source,
        "random_seed": event.random_seed,
    }

    if isinstance(event, LimitAddEvent):
        order = event.order
        updated_order = type(order)(
            order_id=order.order_id,
            parent_order_id=order.parent_order_id,
            child_order_id=order.child_order_id,
            side=order.side,
            price=order.price,
            visible_quantity=order.visible_quantity,
            reserve_quantity=order.reserve_quantity,
            submitted_at=order.submitted_at,
            effective_at=effective_time,
            owner_type=order.owner_type,
            instrument_id=order.instrument_id,
        )
        return LimitAddEvent(order=updated_order, **common)
    if isinstance(event, MarketOrderEvent):
        return MarketOrderEvent(
            side=event.side,
            quantity=event.quantity,
            parent_order_id=event.parent_order_id,
            child_order_id=event.child_order_id,
            **common,
        )
    if isinstance(event, CancelEvent):
        return CancelEvent(order_id=event.order_id, cancel_quantity=event.cancel_quantity, **common)
    if isinstance(event, ModifyEvent):
        return ModifyEvent(
            order_id=event.order_id,
            new_price=event.new_price,
            new_visible_quantity=event.new_visible_quantity,
            new_reserve_quantity=event.new_reserve_quantity,
            **common,
        )
    raise ValueError(f"Unsupported event type for latency application: {type(event)!r}.")


def sort_events_by_effective_time(events: list[LobEvent] | tuple[LobEvent, ...]) -> EventBatch:
    """Return a deterministically ordered event batch."""
    return EventBatch(tuple(events))
