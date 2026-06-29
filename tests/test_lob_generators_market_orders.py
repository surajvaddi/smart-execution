from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import build_initial_book_snapshot, generate_market_order_events
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_generate_market_order_events_produces_requested_count() -> None:
    snapshot = build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())
    events = generate_market_order_events(snapshot, ts("2026-01-02 10:00:01"), 4, random.Random(11))

    assert len(events) == 4
    assert all(event.event_type == "market_order" for event in events)
    assert all(event.quantity > 0 for event in events)
