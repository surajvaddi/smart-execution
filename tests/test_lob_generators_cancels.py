from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import build_initial_book_snapshot, generate_cancel_events
from src.lob_simulator_config import BookInitializationConfig, CancellationProcessConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_generate_cancel_events_targets_live_orders() -> None:
    snapshot = build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())
    events = generate_cancel_events(
        snapshot,
        ts("2026-01-02 10:00:01"),
        CancellationProcessConfig(events_per_step=2),
        random.Random(7),
    )

    live_order_ids = {order.order_id for level in snapshot.bids + snapshot.asks for order in level.orders}
    assert len(events) == 2
    assert all(event.order_id in live_order_ids for event in events)
