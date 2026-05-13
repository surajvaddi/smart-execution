"""Offline CLI smoke tests."""

from __future__ import annotations

import sys

import pytest

import main
from test_rl_env import sample_market_data


def test_parse_args_requires_paired_date_filters(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "--feature-sample", "--start-date", "2026-01-02"])

    with pytest.raises(SystemExit):
        main.parse_args()


def test_feature_sample_cli_smoke(tmp_path, monkeypatch, capsys) -> None:
    input_csv = tmp_path / "market.csv"
    sample_market_data().to_csv(input_csv)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--feature-sample", "--input-csv", str(input_csv)],
    )

    main.main()

    output = capsys.readouterr().out
    assert "Added Phase 2 features" in output
    assert "Estimated volume curve bars" in output


def test_orders_sample_cli_writes_requested_csv(tmp_path, monkeypatch) -> None:
    input_csv = tmp_path / "market.csv"
    output_csv = tmp_path / "orders.csv"
    sample_market_data().to_csv(input_csv)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--orders-sample",
            "--input-csv",
            str(input_csv),
            "--orders-output-csv",
            str(output_csv),
        ],
    )

    main.main()

    assert output_csv.exists()
    assert "XYZ" in output_csv.read_text()
