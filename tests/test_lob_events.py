from __future__ import annotations

import pandas as pd

from src.lob_events import CancelEvent, EventBatch, LimitAddEvent, MarketOrderEvent, ModifyEvent
from src.lob_types import RestingOrder


def sample_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="America/New_York")


def sample_order() -> RestingOrder:
    return RestingOrder(
        order_id="o1",
        parent_order_id=None,
        child_order_id=None,
        side="buy",
        price=100.0,
        visible_quantity=10.0,
        reserve_quantity=0.0,
        submitted_at=sample_timestamp("2026-01-02 10:00:00"),
        effective_at=sample_timestamp("2026-01-02 10:00:01"),
        owner_type="external",
        instrument_id="XYZ",
    )


def test_event_batch_sorts_by_effective_time_then_event_time() -> None:
    later = MarketOrderEvent(
        event_id="e2",
        event_time=sample_timestamp("2026-01-02 10:00:02"),
        effective_time=sample_timestamp("2026-01-02 10:00:03"),
        instrument_id="XYZ",
        source="external",
        random_seed=7,
        side="buy",
        quantity=5.0,
    )
    earlier = LimitAddEvent(
        event_id="e1",
        event_time=sample_timestamp("2026-01-02 10:00:00"),
        effective_time=sample_timestamp("2026-01-02 10:00:01"),
        instrument_id="XYZ",
        source="external",
        random_seed=7,
        order=sample_order(),
    )

    batch = EventBatch(events=(later, earlier))

    assert [event.event_id for event in batch.sorted_events()] == ["e1", "e2"]


def test_cancel_and_modify_events_capture_expected_fields() -> None:
    cancel = CancelEvent(
        event_id="e3",
        event_time=sample_timestamp("2026-01-02 10:00:03"),
        effective_time=sample_timestamp("2026-01-02 10:00:04"),
        instrument_id="XYZ",
        source="strategy",
        random_seed=None,
        order_id="o1",
        cancel_quantity=4.0,
    )
    modify = ModifyEvent(
        event_id="e4",
        event_time=sample_timestamp("2026-01-02 10:00:04"),
        effective_time=sample_timestamp("2026-01-02 10:00:05"),
        instrument_id="XYZ",
        source="strategy",
        random_seed=None,
        order_id="o1",
        new_price=100.1,
    )

    assert cancel.cancel_quantity == 4.0
    assert modify.new_price == 100.1
