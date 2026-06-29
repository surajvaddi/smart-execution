"""Latency helpers for synthetic LOB event scheduling."""

from __future__ import annotations

import random

import pandas as pd

from src.lob_events import CancelEvent, LimitAddEvent, LobEvent, MarketOrderEvent, ModifyEvent
from src.lob_simulator_config import LatencyModelConfig


def sample_gateway_latency(rng: random.Random, config: LatencyModelConfig) -> int:
    """Sample one gateway latency in microseconds."""
    return rng.randint(config.gateway_min_us, config.gateway_max_us)


def sample_exchange_latency(rng: random.Random, config: LatencyModelConfig) -> int:
    """Sample one exchange handling latency in microseconds."""
    return rng.randint(config.exchange_min_us, config.exchange_max_us)


def apply_event_latency(
    event: LobEvent,
    gateway_latency_us: int,
    exchange_latency_us: int,
) -> LobEvent:
    """Return a copy of an event with latency added to effective time."""
    if gateway_latency_us < 0 or exchange_latency_us < 0:
        raise ValueError("latency values must be non-negative.")
    total_latency = gateway_latency_us + exchange_latency_us
    effective_time = event.event_time + pd.Timedelta(microseconds=total_latency)

    if isinstance(event, LimitAddEvent):
        order = event.order
        return LimitAddEvent(
            event_id=event.event_id,
            event_time=event.event_time,
            effective_time=effective_time,
            instrument_id=event.instrument_id,
            source=event.source,
            random_seed=event.random_seed,
            order=order.__class__(
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
            ),
        )
    if isinstance(event, MarketOrderEvent):
        return MarketOrderEvent(
            event_id=event.event_id,
            event_time=event.event_time,
            effective_time=effective_time,
            instrument_id=event.instrument_id,
            source=event.source,
            random_seed=event.random_seed,
            side=event.side,
            quantity=event.quantity,
            parent_order_id=event.parent_order_id,
            child_order_id=event.child_order_id,
        )
    if isinstance(event, CancelEvent):
        return CancelEvent(
            event_id=event.event_id,
            event_time=event.event_time,
            effective_time=effective_time,
            instrument_id=event.instrument_id,
            source=event.source,
            random_seed=event.random_seed,
            order_id=event.order_id,
            cancel_quantity=event.cancel_quantity,
        )
    if isinstance(event, ModifyEvent):
        return ModifyEvent(
            event_id=event.event_id,
            event_time=event.event_time,
            effective_time=effective_time,
            instrument_id=event.instrument_id,
            source=event.source,
            random_seed=event.random_seed,
            order_id=event.order_id,
            new_price=event.new_price,
            new_visible_quantity=event.new_visible_quantity,
            new_reserve_quantity=event.new_reserve_quantity,
        )
    raise ValueError(f"Unsupported event type: {type(event)!r}.")


def sort_events_by_effective_time(events: list[LobEvent] | tuple[LobEvent, ...]) -> tuple[LobEvent, ...]:
    """Sort events by effective time, then event time, then id."""
    return tuple(sorted(events, key=lambda event: (event.effective_time, event.event_time, event.event_id)))
