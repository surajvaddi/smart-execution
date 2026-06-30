from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from src.execution import ParentOrder
from src.lob_execution_runner import execute_parent_order_on_lob, run_schedule_against_lob_episode
from src.lob_generators import build_initial_book_snapshot
from src.lob_simulator import run_lob_simulation_episode
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def sample_parent_order() -> ParentOrder:
    return ParentOrder(
        ticker="XYZ",
        side="buy",
        quantity=7.0,
        start_time=time(10, 0),
        end_time=time(10, 5),
        participation_cap=0.10,
        date=pd.Timestamp("2026-01-02").date(),
        order_id="parent_1",
    )


def sample_child_orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": ts("2026-01-02 10:00:00"),
                "quantity": 4.0,
                "reference_price": 100.5,
            },
            {
                "timestamp": ts("2026-01-02 10:00:01"),
                "quantity": 3.0,
                "reference_price": 100.5,
            },
        ]
    )


def test_execute_parent_order_on_lob_returns_normalized_reports() -> None:
    result = execute_parent_order_on_lob(
        sample_parent_order(),
        sample_child_orders(),
        build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig()),
        placement_style="market",
    )

    assert len(result.execution_reports) == 2
    assert set(["submitted_quantity", "filled_quantity", "fill_status", "simulation_model"]).issubset(
        result.execution_reports.columns
    )
    assert result.execution_reports["filled_quantity"].sum() == pytest.approx(7.0)
    assert set(result.execution_reports["fill_status"]) == {"filled"}
    assert len(result.trade_prints) == 2


def test_run_schedule_against_lob_episode_uses_opening_snapshot() -> None:
    episode = run_lob_simulation_episode(
        instrument_id="XYZ",
        start_time=ts("2026-01-02 10:00:00"),
        num_steps=1,
        random_seed=7,
    )
    child_orders = pd.DataFrame(
        [
            {
                "timestamp": ts("2026-01-02 10:00:00"),
                "quantity": 2.0,
                "reference_price": 99.5,
            }
        ]
    )

    result = run_schedule_against_lob_episode(
        sample_parent_order(),
        child_orders,
        episode,
        placement_style="passive_limit",
    )

    assert len(result.execution_reports) == 1
    assert result.execution_reports.iloc[0]["fill_status"] == "unfilled"
    assert result.execution_reports.iloc[0]["queue_position_at_fill"] == 2
