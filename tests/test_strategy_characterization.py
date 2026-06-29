"""Characterization tests for current schedule-generation behavior.

These tests intentionally pin today's behavior so future refactors can prove
they did not silently change the existing bar-based baseline.
"""

from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from src.execution import ParentOrder
from src.strategies import AdaptiveStrategy, POVStrategy, TWAPStrategy, VWAPStrategy
from test_rl_env import sample_market_data


def sample_parent_order(quantity: float = 2_000.0) -> ParentOrder:
    """Return a parent order aligned with ``sample_market_data``."""
    return ParentOrder(
        ticker="XYZ",
        side="buy",
        quantity=quantity,
        start_time=time(10, 0),
        end_time=time(10, 25),
        participation_cap=0.10,
        date=pd.Timestamp("2026-01-02").date(),
        order_id="XYZ_characterization",
    )


def test_twap_schedule_is_even_across_all_bars() -> None:
    child_orders = TWAPStrategy().generate_child_orders(sample_parent_order(), sample_market_data())

    assert len(child_orders) == 6
    assert child_orders["quantity"].sum() == pytest.approx(2_000.0)
    assert child_orders["quantity"].tolist() == pytest.approx([333.333333] * 6, abs=1e-6)


def test_vwap_schedule_matches_current_volume_curve_split() -> None:
    child_orders = VWAPStrategy().generate_child_orders(sample_parent_order(), sample_market_data())

    assert child_orders["quantity"].sum() == pytest.approx(2_000.0)
    assert child_orders["quantity"].tolist() == pytest.approx(
        [322.580645, 387.096774, 290.322581, 354.838710, 338.709677, 306.451613],
        abs=1e-6,
    )


def test_pov_schedule_finishes_in_two_bars_for_current_sample() -> None:
    child_orders = POVStrategy().generate_child_orders(sample_parent_order(), sample_market_data())

    assert len(child_orders) == 2
    assert child_orders["quantity"].tolist() == pytest.approx([1_000.0, 1_000.0])


def test_adaptive_schedule_matches_current_heuristic_profile() -> None:
    child_orders = AdaptiveStrategy().generate_child_orders(sample_parent_order(), sample_market_data())

    assert child_orders["quantity"].sum() == pytest.approx(2_000.0)
    assert child_orders["quantity"].tolist() == pytest.approx(
        [333.333333, 560.0, 123.4625, 550.594333, 96.526069, 336.083764],
        abs=1e-6,
    )
