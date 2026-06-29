from __future__ import annotations

import pytest

from src.microstructure_metrics import (
    compute_kyle_lambda_proxy,
    compute_order_flow_autocorrelation_proxy,
    compute_signed_return_impact_proxy,
    compute_vpin_proxy,
)
from test_rl_env import sample_market_data


def test_compute_kyle_lambda_proxy_returns_scalar_summary() -> None:
    result = compute_kyle_lambda_proxy(sample_market_data())

    assert result.loc[0, "metric"] == "kyle_lambda_proxy"
    assert result.loc[0, "data_basis"] == "proxy"
    assert result.loc[0, "n_obs"] == len(sample_market_data())


def test_compute_vpin_proxy_returns_row_level_series() -> None:
    result = compute_vpin_proxy(sample_market_data(), bucket_window=3)

    assert "vpin_proxy" in result.columns
    assert result["bucket_window"].iloc[-1] == 3
    assert result["data_basis"].iloc[-1] == "proxy"
    assert result["vpin_proxy"].iloc[0] != result["vpin_proxy"].iloc[0]


def test_compute_order_flow_autocorrelation_proxy_returns_summary() -> None:
    result = compute_order_flow_autocorrelation_proxy(sample_market_data(), lag=1)

    assert result.loc[0, "metric"] == "order_flow_autocorrelation_proxy"
    assert result.loc[0, "lag"] == 1
    assert result.loc[0, "data_basis"] == "proxy"


def test_compute_signed_return_impact_proxy_returns_feature_frame() -> None:
    result = compute_signed_return_impact_proxy(sample_market_data())

    assert {"signed_volume_proxy", "signed_return_impact_proxy", "data_basis"}.issubset(result.columns)
    assert set(result["data_basis"]) == {"proxy"}


def test_microstructure_metrics_require_expected_columns() -> None:
    with pytest.raises(ValueError, match="Missing required microstructure metric columns"):
        compute_kyle_lambda_proxy(sample_market_data().drop(columns=["returns"]))
