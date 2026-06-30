from __future__ import annotations

import pandas as pd
import pytest

from src.lob_execution import create_child_order_state, update_queue_position


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_create_child_order_state_initializes_remaining_quantity_and_queue() -> None:
    state = create_child_order_state(
        child_order_id="child_1",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=50.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
        queue_position=3,
    )

    assert state.remaining_quantity == pytest.approx(50.0)
    assert state.queue_position == 3
    assert state.placement_style == "passive_limit"


def test_update_queue_position_can_move_forward_and_track_partial_fill() -> None:
    state = create_child_order_state(
        child_order_id="child_1",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=50.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
        queue_position=5,
    )

    updated = update_queue_position(
        state,
        queue_position=2,
        updated_at=ts("2026-01-02 10:00:01"),
        remaining_quantity=20.0,
    )

    assert updated.queue_position == 2
    assert updated.remaining_quantity == pytest.approx(20.0)
    assert updated.last_updated_at == ts("2026-01-02 10:00:01")


def test_update_queue_position_rejects_backwards_timestamp() -> None:
    state = create_child_order_state(
        child_order_id="child_1",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=50.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )

    with pytest.raises(ValueError, match="last_updated_at"):
        update_queue_position(
            state,
            queue_position=1,
            updated_at=ts("2026-01-02 09:59:59"),
        )
