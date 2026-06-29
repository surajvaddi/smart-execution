"""Synthetic exchange-state episode runner around the matching engine."""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd

from src.lob_events import EventBatch, LimitAddEvent, LobEvent, MarketOrderEvent
from src.lob_generators import (
    build_initial_book_snapshot,
    generate_cancel_events,
    generate_limit_add_events,
    generate_market_order_events,
)
from src.lob_latency import apply_event_latency, sample_exchange_latency, sample_gateway_latency, sort_events_by_effective_time
from src.lob_replay import events_to_frame, replay_events, snapshot_to_frame
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig, CancellationProcessConfig, LatencyModelConfig
from src.lob_types import BookSnapshot, TradePrint


@dataclass(frozen=True)
class LobSimulationResult:
    """Full synthetic LOB episode outputs."""

    final_snapshot: BookSnapshot
    event_log: pd.DataFrame
    trade_prints: pd.DataFrame
    snapshots: list[BookSnapshot]
    summary: dict[str, object]


def apply_event_batch(
    snapshot: BookSnapshot,
    events: EventBatch | tuple[LobEvent, ...] | list[LobEvent],
) -> tuple[BookSnapshot, list[TradePrint]]:
    """Apply a deterministic event batch to the current snapshot."""
    batch = events if isinstance(events, EventBatch) else EventBatch(tuple(events))
    return replay_events(snapshot, batch.sorted_events())


def advance_book_one_step(
    snapshot: BookSnapshot,
    event_time: pd.Timestamp,
    arrival_config: ArrivalProcessConfig,
    cancellation_config: CancellationProcessConfig,
    latency_config: LatencyModelConfig,
    rng: random.Random,
    market_order_events_per_step: int = 1,
) -> tuple[BookSnapshot, EventBatch, list[TradePrint]]:
    """Generate exogenous flow, apply latency, and advance one simulator step."""
    raw_events: list[LobEvent] = []
    raw_events.extend(generate_limit_add_events(snapshot, event_time, arrival_config, rng))
    raw_events.extend(generate_cancel_events(snapshot, event_time, cancellation_config, rng))
    raw_events.extend(
        generate_market_order_events(
            snapshot,
            event_time,
            num_events=market_order_events_per_step,
            rng=rng,
        )
    )

    delayed_events = []
    for event in raw_events:
        gateway = sample_gateway_latency(rng, latency_config)
        exchange = sample_exchange_latency(rng, latency_config)
        delayed_events.append(apply_event_latency(event, gateway, exchange))

    ordered = sort_events_by_effective_time(delayed_events)
    next_snapshot, trade_prints = apply_event_batch(snapshot, ordered)
    return next_snapshot, ordered, trade_prints


def run_lob_simulation_episode(
    instrument_id: str,
    start_time: pd.Timestamp,
    num_steps: int,
    arrival_config: ArrivalProcessConfig | None = None,
    cancellation_config: CancellationProcessConfig | None = None,
    latency_config: LatencyModelConfig | None = None,
    initialization_config: BookInitializationConfig | None = None,
    random_seed: int = 42,
    step_delta: pd.Timedelta = pd.Timedelta(seconds=1),
    market_order_events_per_step: int = 1,
) -> LobSimulationResult:
    """Run a synthetic LOB episode and return logs, snapshots, and summary."""
    if num_steps <= 0:
        raise ValueError("num_steps must be positive.")
    if step_delta <= pd.Timedelta(0):
        raise ValueError("step_delta must be positive.")

    arrival_config = arrival_config or ArrivalProcessConfig()
    cancellation_config = cancellation_config or CancellationProcessConfig()
    latency_config = latency_config or LatencyModelConfig()
    initialization_config = initialization_config or BookInitializationConfig()

    rng = random.Random(random_seed)
    snapshot = build_initial_book_snapshot(instrument_id, start_time, initialization_config)
    snapshots = [snapshot]
    all_events: list[LobEvent] = []
    all_trades: list[TradePrint] = []

    for step in range(num_steps):
        event_time = start_time + step * step_delta
        snapshot, batch, trade_prints = advance_book_one_step(
            snapshot,
            event_time=event_time,
            arrival_config=arrival_config,
            cancellation_config=cancellation_config,
            latency_config=latency_config,
            rng=rng,
            market_order_events_per_step=market_order_events_per_step,
        )
        snapshots.append(snapshot)
        all_events.extend(batch.sorted_events())
        all_trades.extend(trade_prints)

    return LobSimulationResult(
        final_snapshot=snapshot,
        event_log=events_to_frame(all_events),
        trade_prints=pd.DataFrame([trade.__dict__ for trade in all_trades]),
        snapshots=snapshots,
        summary=collect_episode_summary(snapshots, all_events, all_trades),
    )


def collect_episode_summary(
    snapshots: list[BookSnapshot],
    events: list[LobEvent],
    trade_prints: list[TradePrint],
) -> dict[str, object]:
    """Return a compact summary for one LOB episode."""
    if not snapshots:
        raise ValueError("At least one snapshot is required.")

    final_snapshot = snapshots[-1]
    book_frame = snapshot_to_frame(final_snapshot)
    return {
        "num_snapshots": len(snapshots),
        "num_events": len(events),
        "num_trade_prints": len(trade_prints),
        "final_best_bid": final_snapshot.best_bid,
        "final_best_ask": final_snapshot.best_ask,
        "final_resting_orders": 0 if book_frame.empty else int(book_frame["order_id"].nunique()),
    }
