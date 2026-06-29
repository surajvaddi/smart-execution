from __future__ import annotations

import pandas as pd

from src.lob_simulator import run_lob_simulation_episode
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig, CancellationProcessConfig, LatencyModelConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_run_lob_simulation_episode_returns_logs_snapshots_and_summary() -> None:
    result = run_lob_simulation_episode(
        instrument_id="XYZ",
        start_time=ts("2026-01-02 10:00:00"),
        num_steps=3,
        arrival_config=ArrivalProcessConfig(events_per_step=2),
        cancellation_config=CancellationProcessConfig(events_per_step=1),
        latency_config=LatencyModelConfig(),
        initialization_config=BookInitializationConfig(),
        random_seed=7,
        market_order_events_per_step=1,
    )

    assert result.final_snapshot.instrument_id == "XYZ"
    assert len(result.snapshots) == 4
    assert "num_events" in result.summary
    assert not result.event_log.empty
