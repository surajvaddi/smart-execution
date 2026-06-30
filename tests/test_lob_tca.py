from __future__ import annotations

import pandas as pd
import pytest

from src.lob_tca import (
    fill_probability_by_queue_position,
    queue_wait_time_stats,
    realized_impact_from_trade_path,
    realized_spread_bps,
)


def sample_execution_reports() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "side": "buy",
                "fill_price": 100.2,
                "filled_quantity": 5.0,
                "fill_status": "filled",
                "latency_us": 120,
                "queue_position_at_submit": 1,
            },
            {
                "side": "buy",
                "fill_price": 100.1,
                "filled_quantity": 3.0,
                "fill_status": "partial",
                "latency_us": 200,
                "queue_position_at_submit": 2,
            },
            {
                "side": "buy",
                "fill_price": None,
                "filled_quantity": 0.0,
                "fill_status": "unfilled",
                "latency_us": 350,
                "queue_position_at_submit": 2,
            },
        ]
    )


def sample_trade_prints() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"price": 100.0, "quantity": 4.0},
            {"price": 100.2, "quantity": 6.0},
        ]
    )


def test_queue_wait_time_stats_summarizes_latency() -> None:
    stats = queue_wait_time_stats(sample_execution_reports())

    assert stats["count"] == pytest.approx(3.0)
    assert stats["mean_latency_us"] == pytest.approx((120 + 200 + 350) / 3)
    assert stats["max_latency_us"] == pytest.approx(350.0)


def test_realized_spread_bps_uses_quantity_weighted_fill_prices() -> None:
    spread_bps = realized_spread_bps(sample_execution_reports(), reference_mid_price=100.0)

    expected_avg_spread = ((0.2 * 5.0) + (0.1 * 3.0)) / 8.0
    assert spread_bps == pytest.approx(10_000 * expected_avg_spread / 100.0)


def test_realized_impact_from_trade_path_uses_average_trade_price() -> None:
    impact_bps = realized_impact_from_trade_path(sample_trade_prints(), arrival_mid_price=100.0)

    expected_avg_trade_price = ((100.0 * 4.0) + (100.2 * 6.0)) / 10.0
    assert impact_bps == pytest.approx(10_000 * (expected_avg_trade_price - 100.0) / 100.0)


def test_fill_probability_by_queue_position_groups_queue_slots() -> None:
    summary = fill_probability_by_queue_position(sample_execution_reports())

    assert summary["queue_position_at_submit"].tolist() == [1, 2]
    assert summary["n_orders"].tolist() == [1, 2]
    assert summary["fill_probability"].tolist() == pytest.approx([1.0, 0.5])
