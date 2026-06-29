"""Characterization tests that pin current backtester strategy outputs."""

from __future__ import annotations

import pytest

from src.backtester import Backtester
from test_rl_env import sample_market_data


def test_backtester_keeps_current_strategy_shortfall_profile() -> None:
    results = Backtester(tickers=["XYZ"], max_orders_per_ticker=1).run(sample_market_data())
    profile = {
        row["strategy"]: row["implementation_shortfall_bps"]
        for row in results[["strategy", "implementation_shortfall_bps"]].to_dict("records")
    }

    assert profile == pytest.approx(
        {
            "TWAP": 186.5715934709,
            "VWAP": 186.0892336320,
            "POV": 298.9979919679,
            "Adaptive": 194.7787481297,
        }
    )


def test_backtester_keeps_current_full_fill_baseline_on_sample_data() -> None:
    results = Backtester(tickers=["XYZ"], max_orders_per_ticker=1).run(sample_market_data())

    assert set(results["strategy"]) == {"TWAP", "VWAP", "POV", "Adaptive"}
    assert results["fill_rate"].tolist() == pytest.approx([1.0, 1.0, 1.0, 1.0])
