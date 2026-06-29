"""Characterization tests for the current bar-based fill simulator."""

from __future__ import annotations

from datetime import time

import pandas as pd
import pytest

from src.execution import ParentOrder
from src.fill_simulator import place_and_simulate_fills
from src.strategies import TWAPStrategy
from src.tca import compute_tca_metrics
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
        order_id="XYZ_fill_characterization",
    )


def test_market_fill_path_matches_current_twap_cost_profile() -> None:
    data = sample_market_data()
    order = sample_parent_order()
    child_orders = TWAPStrategy().generate_child_orders(order, data)

    fills = place_and_simulate_fills(child_orders, data, "market", parent_order=order)
    metrics = compute_tca_metrics(order, fills, data)

    assert fills["fill_status"].tolist() == ["filled"] * 6
    assert fills["filled_quantity"].sum() == pytest.approx(2_000.0)
    assert metrics["avg_fill_price"] == pytest.approx(102.66643854020145)
    assert metrics["implementation_shortfall_bps"] == pytest.approx(266.64385402014545)
    assert metrics["spread_cost_bps"] == pytest.approx(60.98499999999991)
    assert metrics["impact_cost_bps"] == pytest.approx(187.18450105017905)
    assert metrics["fill_rate"] == pytest.approx(1.0)


def test_passive_limit_path_matches_current_partial_fill_profile() -> None:
    data = sample_market_data()
    order = sample_parent_order()
    child_orders = TWAPStrategy().generate_child_orders(order, data)

    fills = place_and_simulate_fills(child_orders, data, "passive_limit", parent_order=order)
    metrics = compute_tca_metrics(order, fills, data)

    assert fills["fill_status"].tolist() == ["partial", "unfilled", "unfilled", "unfilled", "unfilled", "unfilled"]
    assert fills["filled_quantity"].tolist() == pytest.approx([250.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert metrics["fill_rate"] == pytest.approx(0.125)
    assert metrics["opportunity_cost_bps"] == pytest.approx(43.75)
    assert metrics["adverse_selection_cost_bps"] == pytest.approx(88.11388300841827)


def test_queue_weighted_touch_is_more_conservative_than_volume_capped_touch() -> None:
    data = sample_market_data()
    order = sample_parent_order()
    child_orders = TWAPStrategy().generate_child_orders(order, data)

    base_fills = place_and_simulate_fills(child_orders, data, "passive_limit", parent_order=order)
    queue_fills = place_and_simulate_fills(
        child_orders,
        data,
        "passive_limit",
        parent_order=order,
        fill_model="queue_weighted_touch",
    )

    assert queue_fills["filled_quantity"].sum() < base_fills["filled_quantity"].sum()
    assert queue_fills["filled_quantity"].sum() == pytest.approx(0.0)
    assert queue_fills["fill_probability"].max() == pytest.approx(0.0)
