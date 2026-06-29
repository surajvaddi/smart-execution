from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import generate_market_order_events, seed_symmetric_depth
from src.lob_simulator_config import BookInitializationConfig


def ts() -> pd.Timestamp:
    return pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")


def test_generate_market_order_events_builds_expected_count() -> None:
    rng = random.Random(13)
    book = seed_symmetric_depth("XYZ", ts(), BookInitializationConfig())
    events = generate_market_order_events(book, ts(), rng, num_events=4, min_quantity=1.0, max_quantity=3.0, random_seed=13)

    assert len(events) == 4
    assert all(1.0 <= event.quantity <= 3.0 for event in events)
    assert {event.side for event in events}.issubset({"buy", "sell"})
