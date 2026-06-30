from __future__ import annotations

import pandas as pd
import pytest

from src.lob_execution import (
    build_child_execution_report,
    create_child_order_state,
    place_aggressive_child_order,
    place_passive_child_order,
)
from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def seeded_book():
    return build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())


def test_build_child_execution_report_marks_aggressive_fill_as_taker() -> None:
    initial_state = create_child_order_state(
        child_order_id="child_aggressive",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=4.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="aggressive_limit",
    )
    _, updated_state, prints = place_aggressive_child_order(seeded_book(), initial_state)

    report = build_child_execution_report(
        initial_state,
        updated_state,
        prints,
        timestamp=ts("2026-01-02 10:00:00"),
    )

    assert report.fill_status == "filled"
    assert report.filled_quantity == pytest.approx(4.0)
    assert report.fill_price == pytest.approx(100.5)
    assert report.maker_flag is False
    assert report.taker_flag is True


def test_build_child_execution_report_marks_resting_passive_order_as_unfilled() -> None:
    initial_state = create_child_order_state(
        child_order_id="child_passive",
        parent_order_id="parent_1",
        instrument_id="XYZ",
        side="buy",
        quantity=3.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        placement_style="passive_limit",
    )
    _, updated_state, prints = place_passive_child_order(seeded_book(), initial_state)

    report = build_child_execution_report(
        initial_state,
        updated_state,
        prints,
        timestamp=ts("2026-01-02 10:00:00"),
    )

    assert report.fill_status == "unfilled"
    assert report.filled_quantity == pytest.approx(0.0)
    assert report.remaining_quantity == pytest.approx(3.0)
    assert report.fill_price is None
    assert report.queue_position_at_fill == 2
    assert report.maker_flag is None
    assert report.taker_flag is None
