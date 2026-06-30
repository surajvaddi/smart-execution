from __future__ import annotations

import pandas as pd
import pytest

from src.lob_execution import (
    cancel_execution_child_order,
    create_child_order_state,
    submit_limit_execution_child,
)
from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def seeded_book():
    return build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())


def test_cancel_execution_child_order_reduces_resting_quantity() -> None:
    state = create_child_order_state(
        child_order_id="child_limit",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=5.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )
    resting_book, resting_state, _ = submit_limit_execution_child(seeded_book(), state, price=99.5)

    updated_book, updated_state = cancel_execution_child_order(
        resting_book,
        resting_state,
        updated_at=ts("2026-01-02 10:00:01"),
        cancel_quantity=2.0,
    )

    assert updated_state.remaining_quantity == pytest.approx(3.0)
    assert updated_state.queue_position == 2
    assert updated_book.bids[0].orders[1].visible_quantity == pytest.approx(3.0)


def test_cancel_execution_child_order_removes_resting_child_when_fully_canceled() -> None:
    state = create_child_order_state(
        child_order_id="child_limit",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=5.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )
    resting_book, resting_state, _ = submit_limit_execution_child(seeded_book(), state, price=99.5)

    updated_book, updated_state = cancel_execution_child_order(
        resting_book,
        resting_state,
        updated_at=ts("2026-01-02 10:00:01"),
    )

    assert updated_state.remaining_quantity == pytest.approx(0.0)
    assert updated_state.queue_position is None
    assert len(updated_book.bids[0].orders) == 1
    assert updated_book.bids[0].orders[0].order_id != "child_limit"
