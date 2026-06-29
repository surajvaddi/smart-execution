from __future__ import annotations

import pytest

from src.report_provenance import (
    ReportProvenance,
    attach_provenance_columns,
    build_provenance_record,
    validate_provenance_record,
)
from test_rl_env import sample_market_data


def test_build_provenance_record_returns_dataclass() -> None:
    record = build_provenance_record(
        research_mode="bar_backtest",
        data_basis="proxy",
        source_dataset="data/processed/SPY_5d_5m.csv",
        model_name="Adaptive",
        simulation_model="volume_capped_touch",
        random_seed=42,
        config_id="default",
        generated_at="2026-01-02T15:30:00+00:00",
    )

    assert isinstance(record, ReportProvenance)
    assert record.random_seed == 42


def test_attach_provenance_columns_adds_constant_fields() -> None:
    attached = attach_provenance_columns(
        sample_market_data(),
        build_provenance_record(
            research_mode="bar_backtest",
            data_basis="proxy",
            source_dataset="dataset.csv",
            model_name="Adaptive",
            simulation_model="volume_capped_touch",
            generated_at="2026-01-02T15:30:00+00:00",
        ),
    )

    assert set(attached["research_mode"]) == {"bar_backtest"}
    assert set(attached["simulation_model"]) == {"volume_capped_touch"}


def test_validate_provenance_record_rejects_invalid_basis() -> None:
    with pytest.raises(ValueError, match="data_basis"):
        validate_provenance_record(
            {
                "research_mode": "bar_backtest",
                "data_basis": "unknown",
                "source_dataset": "dataset.csv",
                "model_name": "Adaptive",
                "simulation_model": "volume_capped_touch",
                "random_seed": None,
                "config_id": "default",
                "generated_at": "2026-01-02T15:30:00+00:00",
            }
        )


def test_validate_provenance_record_requires_integer_seed() -> None:
    with pytest.raises(ValueError, match="random_seed"):
        validate_provenance_record(
            {
                "research_mode": "bar_backtest",
                "data_basis": "proxy",
                "source_dataset": "dataset.csv",
                "model_name": "Adaptive",
                "simulation_model": "volume_capped_touch",
                "random_seed": "forty-two",
                "config_id": "default",
                "generated_at": "2026-01-02T15:30:00+00:00",
            }
        )
