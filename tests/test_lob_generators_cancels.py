from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import generate_cancel_events, seed_symmetric_depth
from src.lob_simulator_config import BookInitializationConfig, CancellationProcessConfig


def ts() -> pd.Timestamp:
    return pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")


def test_generate_cancel_events_targets_live_orders() -> None:
    rng = random.Random(11)
    book = seed_symmetric_depth("XYZ", ts(), BookInitializationConfig())
    events = generate_cancel_events(
        book,
        ts(),
        rng,
        CancellationProcessConfig(events_per_step=2, cancel_probability=1.0),
        random_seed=11,
    )

    live_order_ids = {order.order_id for level in book.bids for order in level.orders} | {
        order.order_id for level in book.asks for order in level.orders
    }
    assert len(events) == 2
    assert all(event.order_id in live_order_ids for event in events)
