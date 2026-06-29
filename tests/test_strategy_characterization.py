"""Characterization tests that pin current schedule-generation behavior."""

from __future__ import annotations

import pytest

from src.strategies import AdaptiveStrategy, POVStrategy, TWAPStrategy, VWAPStrategy
from test_rl_env import sample_market_data, sample_order


def test_twap_schedule_stays_even_and_sums_to_parent_quantity() -> None:
    child_orders = TWAPStrategy().generate_child_orders(sample_order(), sample_market_data())

    assert child_orders["quantity"].tolist() == pytest.approx([333.3333333333] * 6)
    assert child_orders["quantity"].sum() == pytest.approx(2000.0)


def test_vwap_schedule_stays_on_current_volume_curve() -> None:
    child_orders = VWAPStrategy().generate_child_orders(sample_order(), sample_market_data())

    assert child_orders["quantity"].tolist() == pytest.approx(
        [
            322.5806451613,
            387.0967741935,
            290.3225806452,
            354.8387096774,
            338.7096774194,
            306.4516129032,
        ]
    )
    assert child_orders["quantity"].sum() == pytest.approx(2000.0)


def test_pov_schedule_keeps_current_two_slice_completion_pattern() -> None:
    child_orders = POVStrategy().generate_child_orders(sample_order(), sample_market_data())

    assert child_orders["quantity"].tolist() == pytest.approx([1000.0, 1000.0])
    assert child_orders["quantity"].sum() == pytest.approx(2000.0)


def test_adaptive_schedule_keeps_current_quantity_profile() -> None:
    child_orders = AdaptiveStrategy().generate_child_orders(sample_order(), sample_market_data())

    assert child_orders["quantity"].tolist() == pytest.approx(
        [
            333.3333333333,
            560.0,
            123.4625,
            550.5943333333,
            96.5260694444,
            336.0837638889,
        ]
    )
    assert child_orders["quantity"].sum() == pytest.approx(2000.0)
