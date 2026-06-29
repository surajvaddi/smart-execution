from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import build_initial_book_snapshot, generate_limit_add_events
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_generate_limit_add_events_returns_requested_count() -> None:
    snapshot = build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())
    events = generate_limit_add_events(
        snapshot,
        ts("2026-01-02 10:00:01"),
        ArrivalProcessConfig(events_per_step=3),
        random.Random(7),
    )

    assert len(events) == 3
    assert all(event.event_type == "limit_add" for event in events)
    assert all(event.order.instrument_id == "XYZ" for event in events)
