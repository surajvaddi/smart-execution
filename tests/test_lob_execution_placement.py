from __future__ import annotations

import pandas as pd
import pytest

from src.lob_execution import (
    create_child_order_state,
    place_aggressive_child_order,
    place_midpoint_child_order,
    place_passive_child_order,
)
from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def seeded_book():
    return build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())


def test_place_passive_child_order_posts_at_same_side_touch() -> None:
    state = create_child_order_state(
        child_order_id="child_passive",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=3.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )

    updated_book, updated_state, prints = place_passive_child_order(seeded_book(), state)

    assert prints == []
    assert updated_book.bids[0].price == pytest.approx(99.5)
    assert updated_state.queue_position == 2
    assert updated_state.remaining_quantity == pytest.approx(3.0)


def test_place_aggressive_child_order_crosses_at_opposite_touch() -> None:
    state = create_child_order_state(
        child_order_id="child_aggressive",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=4.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="aggressive_limit",
    )

    updated_book, updated_state, prints = place_aggressive_child_order(seeded_book(), state)

    assert len(prints) == 1
    assert prints[0].price == pytest.approx(100.5)
    assert updated_state.remaining_quantity == pytest.approx(0.0)
    assert updated_state.queue_position is None
    assert updated_book.best_ask is None or updated_book.best_ask >= 100.5


def test_place_midpoint_child_order_posts_between_touch_prices() -> None:
    state = create_child_order_state(
        child_order_id="child_mid",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=2.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="midpoint_limit",
    )

    updated_book, updated_state, prints = place_midpoint_child_order(seeded_book(), state)

    assert prints == []
    assert updated_book.bids[0].price == pytest.approx(100.0)
    assert updated_state.queue_position == 1
    assert updated_state.remaining_quantity == pytest.approx(2.0)
