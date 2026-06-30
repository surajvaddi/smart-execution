from __future__ import annotations

import pandas as pd
import pytest

from src.lob_execution import (
    cancel_replace_child_order,
    cancel_stale_child_orders,
    create_child_order_state,
    submit_limit_execution_child,
)
from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def seeded_book():
    return build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())


def test_cancel_replace_child_order_reposts_remaining_quantity_at_new_price() -> None:
    initial_state = create_child_order_state(
        child_order_id="child_limit",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=3.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )
    resting_book, resting_state, _ = submit_limit_execution_child(seeded_book(), initial_state, price=99.5)

    replaced_book, replaced_state, prints = cancel_replace_child_order(
        resting_book,
        resting_state,
        updated_at=ts("2026-01-02 10:00:01"),
        replacement_price=100.0,
    )

    assert prints == []
    assert replaced_state.remaining_quantity == pytest.approx(3.0)
    assert replaced_state.queue_position == 1
    assert replaced_book.bids[0].price == pytest.approx(100.0)
    assert replaced_book.bids[0].orders[0].order_id == "child_limit"


def test_cancel_stale_child_orders_only_cancels_resting_orders_past_threshold() -> None:
    state_one = create_child_order_state(
        child_order_id="child_old",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=2.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )
    state_two = create_child_order_state(
        child_order_id="child_recent",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=2.0,
        submitted_at=ts("2026-01-02 10:00:02"),
        placement_style="passive_limit",
    )

    book, stale_state, _ = submit_limit_execution_child(seeded_book(), state_one, price=99.5)
    book, fresh_state, _ = submit_limit_execution_child(book, state_two, price=99.5)

    updated_book, updated_states = cancel_stale_child_orders(
        book,
        [stale_state, fresh_state],
        updated_at=ts("2026-01-02 10:00:03"),
        stale_after=pd.Timedelta(seconds=2),
    )

    old_state, recent_state = updated_states
    assert old_state.remaining_quantity == pytest.approx(0.0)
    assert old_state.queue_position is None
    assert recent_state.remaining_quantity == pytest.approx(2.0)
    assert recent_state.queue_position == 2
    assert [order.order_id for order in updated_book.bids[0].orders] == ["XYZ_buy_0", "child_recent"]
