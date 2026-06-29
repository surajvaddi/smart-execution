from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import generate_limit_add_events
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig
from src.lob_generators import seed_symmetric_depth


def ts() -> pd.Timestamp:
    return pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")


def test_generate_limit_add_events_builds_expected_count_and_fields() -> None:
    rng = random.Random(7)
    book = seed_symmetric_depth("XYZ", ts(), BookInitializationConfig())
    events = generate_limit_add_events(book, ts(), rng, ArrivalProcessConfig(events_per_step=3), random_seed=7)

    assert len(events) == 3
    assert all(event.order.instrument_id == "XYZ" for event in events)
    assert all(event.order.owner_type == "simulator" for event in events)
