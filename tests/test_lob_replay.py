from __future__ import annotations

import pandas as pd
import pytest

from src.lob_events import CancelEvent, EventBatch, LimitAddEvent, MarketOrderEvent, ModifyEvent
from src.lob_replay import events_to_frame, replay_events, snapshot_to_frame
from src.lob_types import BookLevel, BookSnapshot, RestingOrder


def sample_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="America/New_York")


def make_order(
    order_id: str,
    side: str,
    price: float,
    visible_quantity: float,
) -> RestingOrder:
    return RestingOrder(
        order_id=order_id,
        parent_order_id=None,
        child_order_id=None,
        side=side,
        price=price,
        visible_quantity=visible_quantity,
        reserve_quantity=0.0,
        submitted_at=sample_timestamp("2026-01-02 10:00:00"),
        effective_at=sample_timestamp("2026-01-02 10:00:00"),
        owner_type="external",
        instrument_id="XYZ",
    )


def initial_snapshot() -> BookSnapshot:
    return BookSnapshot(
        instrument_id="XYZ",
        timestamp=sample_timestamp("2026-01-02 10:00:00"),
        bids=(
            BookLevel(side="buy", price=100.0, orders=(make_order("b1", "buy", 100.0, 10.0),)),
        ),
        asks=(
            BookLevel(side="sell", price=101.0, orders=(make_order("a1", "sell", 101.0, 8.0),)),
        ),
    )


def test_snapshot_to_frame_returns_queue_positions() -> None:
    frame = snapshot_to_frame(initial_snapshot())

    assert {"queue_position", "order_id", "side", "price"}.issubset(frame.columns)
    assert frame["queue_position"].tolist() == [1, 1]


def test_events_to_frame_is_sorted_deterministically() -> None:
    event_late = MarketOrderEvent(
        event_id="e2",
        event_time=sample_timestamp("2026-01-02 10:00:02"),
        effective_time=sample_timestamp("2026-01-02 10:00:03"),
        instrument_id="XYZ",
        source="external",
        random_seed=1,
        side="buy",
        quantity=2.0,
    )
    event_early = LimitAddEvent(
        event_id="e1",
        event_time=sample_timestamp("2026-01-02 10:00:01"),
        effective_time=sample_timestamp("2026-01-02 10:00:01"),
        instrument_id="XYZ",
        source="external",
        random_seed=1,
        order=make_order("b2", "buy", 99.5, 6.0),
    )

    frame = events_to_frame(EventBatch(events=(event_late, event_early)))

    assert frame["event_id"].tolist() == ["e1", "e2"]


def test_replay_events_reconstructs_final_book_state_and_trade_prints() -> None:
    add_event = LimitAddEvent(
        event_id="e1",
        event_time=sample_timestamp("2026-01-02 10:00:01"),
        effective_time=sample_timestamp("2026-01-02 10:00:01"),
        instrument_id="XYZ",
        source="external",
        random_seed=1,
        order=make_order("b2", "buy", 99.5, 6.0),
    )
    modify_event = ModifyEvent(
        event_id="e2",
        event_time=sample_timestamp("2026-01-02 10:00:02"),
        effective_time=sample_timestamp("2026-01-02 10:00:02"),
        instrument_id="XYZ",
        source="strategy",
        random_seed=None,
        order_id="b2",
        new_price=100.5,
    )
    market_event = MarketOrderEvent(
        event_id="e3",
        event_time=sample_timestamp("2026-01-02 10:00:03"),
        effective_time=sample_timestamp("2026-01-02 10:00:03"),
        instrument_id="XYZ",
        source="external",
        random_seed=1,
        side="buy",
        quantity=5.0,
    )
    cancel_event = CancelEvent(
        event_id="e4",
        event_time=sample_timestamp("2026-01-02 10:00:04"),
        effective_time=sample_timestamp("2026-01-02 10:00:04"),
        instrument_id="XYZ",
        source="strategy",
        random_seed=None,
        order_id="b1",
    )

    final_snapshot, prints = replay_events(
        initial_snapshot(),
        EventBatch(events=(add_event, modify_event, market_event, cancel_event)),
    )

    assert len(prints) == 1
    assert prints[0].price == pytest.approx(101.0)
    assert prints[0].quantity == pytest.approx(5.0)

    final_frame = snapshot_to_frame(final_snapshot)
    assert "a1" in final_frame["order_id"].tolist()
    ask_row = final_frame[final_frame["order_id"] == "a1"].iloc[0]
    assert ask_row["visible_quantity"] == pytest.approx(3.0)
    assert "b1" not in final_frame["order_id"].tolist()
    assert "b2" in final_frame["order_id"].tolist()
