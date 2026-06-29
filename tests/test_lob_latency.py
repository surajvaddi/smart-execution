from __future__ import annotations

import random

import pandas as pd

from src.lob_events import MarketOrderEvent
from src.lob_latency import apply_event_latency, sample_exchange_latency, sample_gateway_latency, sort_events_by_effective_time
from src.lob_simulator_config import LatencyModelConfig


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="America/New_York")


def test_latency_sampling_stays_within_bounds() -> None:
    rng = random.Random(17)
    config = LatencyModelConfig(gateway_min_us=10, gateway_max_us=20, exchange_min_us=30, exchange_max_us=40)

    gateway = sample_gateway_latency(rng, config)
    exchange = sample_exchange_latency(rng, config)

    assert 10 <= gateway <= 20
    assert 30 <= exchange <= 40


def test_apply_event_latency_shifts_effective_time() -> None:
    event = MarketOrderEvent(
        event_id="e1",
        event_time=ts("2026-01-02 10:00:00"),
        effective_time=ts("2026-01-02 10:00:00"),
        instrument_id="XYZ",
        source="simulator",
        random_seed=17,
        side="buy",
        quantity=5.0,
    )

    shifted = apply_event_latency(event, gateway_latency_us=100, exchange_latency_us=200)

    assert shifted.effective_time == ts("2026-01-02 10:00:00") + pd.Timedelta(microseconds=300)


def test_sort_events_by_effective_time_reorders_when_latency_differs() -> None:
    later = MarketOrderEvent(
        event_id="e2",
        event_time=ts("2026-01-02 10:00:01"),
        effective_time=ts("2026-01-02 10:00:03"),
        instrument_id="XYZ",
        source="simulator",
        random_seed=17,
        side="buy",
        quantity=5.0,
    )
    earlier = MarketOrderEvent(
        event_id="e1",
        event_time=ts("2026-01-02 10:00:00"),
        effective_time=ts("2026-01-02 10:00:02"),
        instrument_id="XYZ",
        source="simulator",
        random_seed=17,
        side="sell",
        quantity=3.0,
    )

    ordered = sort_events_by_effective_time([later, earlier])

    assert [event.event_id for event in ordered] == ["e1", "e2"]
