from __future__ import annotations

import random

import pandas as pd

from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator import advance_book_one_step
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig, CancellationProcessConfig, LatencyModelConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_advance_book_one_step_returns_snapshot_batch_and_trades() -> None:
    snapshot = build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())
    next_snapshot, batch, trades = advance_book_one_step(
        snapshot,
        event_time=ts("2026-01-02 10:00:01"),
        arrival_config=ArrivalProcessConfig(events_per_step=2),
        cancellation_config=CancellationProcessConfig(events_per_step=1),
        latency_config=LatencyModelConfig(),
        rng=random.Random(3),
        market_order_events_per_step=1,
    )

    assert next_snapshot.instrument_id == "XYZ"
    assert len(batch.events) == 4
    assert isinstance(trades, list)
