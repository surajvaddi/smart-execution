"""Characterization tests for current backtester result shape and ordering."""

from __future__ import annotations

import pytest

from src.backtester import Backtester
from test_rl_env import sample_market_data


def test_single_ticker_backtest_returns_current_strategy_set() -> None:
    backtester = Backtester(tickers=["XYZ"], max_orders_per_ticker=1)

    results = backtester.run_single_ticker_data(sample_market_data())

    assert results["strategy"].tolist() == ["TWAP", "VWAP", "POV", "Adaptive"]
    assert results["implementation_shortfall_bps"].tolist() == pytest.approx(
        [186.57159292430805, 186.08923387096752, 298.99799195977437, 194.77874805227628]
    )
    assert results["fill_rate"].tolist() == pytest.approx([1.0, 1.0, 1.0, 1.0])
