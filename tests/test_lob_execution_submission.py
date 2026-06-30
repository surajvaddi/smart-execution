from __future__ import annotations

import pandas as pd
import pytest

from src.lob_execution import (
    create_child_order_state,
    submit_execution_child_order,
    submit_limit_execution_child,
    submit_market_execution_child,
)
from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def seeded_book():
    return build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())


def test_submit_market_execution_child_consumes_book_and_updates_remaining() -> None:
    state = create_child_order_state(
        child_order_id="child_market",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=5.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="market",
    )

    updated_book, updated_state, prints = submit_market_execution_child(seeded_book(), state)

    assert len(prints) >= 1
    assert updated_state.remaining_quantity == pytest.approx(0.0)
    assert updated_state.queue_position is None
    assert updated_book.best_ask is None or updated_book.best_ask >= 100.5


def test_submit_limit_execution_child_rests_order_and_sets_queue_position() -> None:
    state = create_child_order_state(
        child_order_id="child_limit",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=3.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )

    updated_book, updated_state, prints = submit_limit_execution_child(seeded_book(), state, price=99.5)

    assert prints == []
    assert updated_state.remaining_quantity == pytest.approx(3.0)
    assert updated_state.queue_position == 2
    assert updated_book.bids[0].price == pytest.approx(99.5)


def test_submit_execution_child_order_routes_by_placement_style() -> None:
    market_state = create_child_order_state(
        child_order_id="child_market",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=2.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="market",
    )
    limit_state = create_child_order_state(
        child_order_id="child_limit",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=2.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )

    _, routed_market_state, market_prints = submit_execution_child_order(seeded_book(), market_state)
    _, routed_limit_state, limit_prints = submit_execution_child_order(seeded_book(), limit_state, price=99.5)

    assert market_prints
    assert routed_market_state.remaining_quantity == pytest.approx(0.0)
    assert limit_prints == []
    assert routed_limit_state.queue_position == 2
