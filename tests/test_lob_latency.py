from __future__ import annotations

import random

import pandas as pd

from src.lob_events import MarketOrderEvent
from src.lob_latency import apply_event_latency, sample_exchange_latency, sample_gateway_latency, sort_events_by_effective_time
from src.lob_simulator_config import LatencyModelConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_latency_sampling_uses_config_ranges() -> None:
    rng = random.Random(5)
    config = LatencyModelConfig(gateway_latency_us=(10, 20), exchange_latency_us=(30, 40))

    gateway = sample_gateway_latency(rng, config)
    exchange = sample_exchange_latency(rng, config)

    assert 10 <= gateway <= 20
    assert 30 <= exchange <= 40


def test_apply_event_latency_updates_effective_time() -> None:
    event = MarketOrderEvent(
        event_id="m1",
        event_time=ts("2026-01-02 10:00:00"),
        effective_time=ts("2026-01-02 10:00:00"),
        instrument_id="XYZ",
        source="external_flow",
        random_seed=None,
        side="buy",
        quantity=5.0,
    )

    delayed = apply_event_latency(event, 50, 150)

    assert delayed.effective_time == ts("2026-01-02 10:00:00") + pd.to_timedelta(200, unit="us")


def test_sort_events_by_effective_time_returns_ordered_batch() -> None:
    first = MarketOrderEvent(
        event_id="b",
        event_time=ts("2026-01-02 10:00:00"),
        effective_time=ts("2026-01-02 10:00:01"),
        instrument_id="XYZ",
        source="external_flow",
        random_seed=None,
        side="buy",
        quantity=1.0,
    )
    second = MarketOrderEvent(
        event_id="a",
        event_time=ts("2026-01-02 10:00:00"),
        effective_time=ts("2026-01-02 10:00:00.500000"),
        instrument_id="XYZ",
        source="external_flow",
        random_seed=None,
        side="sell",
        quantity=1.0,
    )

    batch = sort_events_by_effective_time([first, second])
    assert [event.event_id for event in batch.sorted_events()] == ["a", "b"]
