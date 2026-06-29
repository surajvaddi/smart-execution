"""Tests for the FastAPI backend."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.api import create_app
from test_rl_env import sample_market_data


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_backtest_endpoint_returns_summary(tmp_path) -> None:
    path = tmp_path / "sample.csv"
    sample_market_data().to_csv(path)
    client = TestClient(create_app())

    response = client.post(
        "/api/backtest",
        json={"input_csv": str(path), "max_orders_per_ticker": 1},
    )

    assert response.status_code == 400


def test_backtest_endpoint_accepts_project_relative_dataset(tmp_path, monkeypatch) -> None:
    import src.api as api

    data_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)
    path = data_dir / "SPY_5d_5m.csv"
    sample_market_data().to_csv(path)
    monkeypatch.setattr(api, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(api, "PROCESSED_DATA_DIR", data_dir)
    client = TestClient(api.create_app())

    response = client.post(
        "/api/backtest",
        json={"input_csv": "data/processed/SPY_5d_5m.csv", "max_orders_per_ticker": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["summary"]) == 4
    assert payload["meta"]["result_rows"] == 4


def test_dataset_endpoint_returns_metadata(tmp_path, monkeypatch) -> None:
    import src.api as api

    data_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)
    path = data_dir / "SPY_5d_5m.csv"
    sample_market_data().to_csv(path)
    monkeypatch.setattr(api, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(api, "PROCESSED_DATA_DIR", data_dir)
    client = TestClient(api.create_app())

    response = client.get("/api/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["datasets"][0]["ticker"] == "SPY"
    assert payload["datasets"][0]["period"] == "5d"
    assert payload["datasets"][0]["interval"] == "5m"
    assert payload["datasets"][0]["rows"] == len(sample_market_data())
    assert payload["datasets"][0]["tickers"]


def test_execution_grid_rejects_invalid_placement(tmp_path, monkeypatch) -> None:
    import src.api as api

    data_dir = tmp_path / "data" / "processed"
    data_dir.mkdir(parents=True)
    path = data_dir / "sample.csv"
    sample_market_data().to_csv(path)
    monkeypatch.setattr(api, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(api, "PROCESSED_DATA_DIR", data_dir)
    client = TestClient(api.create_app())

    response = client.post(
        "/api/execution-grid",
        json={
            "input_csv": "data/processed/sample.csv",
            "max_orders_per_ticker": 1,
            "placement_styles": ["market", "bad_style"],
        },
    )

    assert response.status_code == 400
