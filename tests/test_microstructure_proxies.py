from __future__ import annotations

import pytest

from src.microstructure_proxies import (
    compute_hidden_liquidity_proxy,
    compute_passive_fill_risk_proxy,
    compute_queue_pressure_proxy,
)
from test_rl_env import sample_market_data


def test_compute_queue_pressure_proxy_returns_named_column() -> None:
    result = compute_queue_pressure_proxy(sample_market_data())

    assert "queue_pressure_proxy" in result.columns
    assert len(result) == len(sample_market_data())


def test_compute_hidden_liquidity_proxy_returns_named_column() -> None:
    result = compute_hidden_liquidity_proxy(sample_market_data())

    assert "hidden_liquidity_proxy" in result.columns
    assert result["hidden_liquidity_proxy"].notna().all()


def test_compute_passive_fill_risk_proxy_returns_named_column() -> None:
    result = compute_passive_fill_risk_proxy(sample_market_data())

    assert "passive_fill_risk_proxy" in result.columns
    assert len(result) == len(sample_market_data())


def test_microstructure_proxies_validate_required_columns() -> None:
    with pytest.raises(ValueError, match="Missing required microstructure proxy columns"):
        compute_queue_pressure_proxy(sample_market_data().drop(columns=["volume"]))
