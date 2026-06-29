"""Characterization tests that pin current bar-based fill behavior."""

from __future__ import annotations

import pytest

from src.fill_simulator import place_and_simulate_fills
from src.strategies import TWAPStrategy
from test_rl_env import sample_market_data, sample_order


def test_market_placement_keeps_full_fill_behavior() -> None:
    child_orders = TWAPStrategy().generate_child_orders(sample_order(), sample_market_data())
    fills = place_and_simulate_fills(
        child_orders,
        sample_market_data(),
        "market",
        parent_order=sample_order(),
    )

    assert fills["filled_quantity"].sum() == pytest.approx(2000.0)
    assert set(fills["fill_status"]) == {"filled"}
    assert set(fills["resolved_placement_style"]) == {"market"}


def test_passive_limit_keeps_current_partial_then_unfilled_pattern() -> None:
    child_orders = TWAPStrategy().generate_child_orders(sample_order(), sample_market_data())
    fills = place_and_simulate_fills(
        child_orders,
        sample_market_data(),
        "passive_limit",
        parent_order=sample_order(),
    )

    assert fills["filled_quantity"].tolist() == pytest.approx([250.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert fills["fill_status"].tolist() == ["partial", "unfilled", "unfilled", "unfilled", "unfilled", "unfilled"]
    assert fills["filled_quantity"].sum() == pytest.approx(250.0)


def test_aggressive_limit_keeps_current_full_fill_behavior() -> None:
    child_orders = TWAPStrategy().generate_child_orders(sample_order(), sample_market_data())
    fills = place_and_simulate_fills(
        child_orders,
        sample_market_data(),
        "aggressive_limit",
        parent_order=sample_order(),
    )

    assert fills["filled_quantity"].sum() == pytest.approx(2000.0)
    assert set(fills["fill_status"]) == {"filled"}
    assert set(fills["resolved_placement_style"]) == {"aggressive_limit"}
