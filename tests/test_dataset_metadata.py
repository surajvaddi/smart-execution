from __future__ import annotations

import pytest

from src.dataset_metadata import (
    DatasetMetadata,
    attach_dataset_metadata,
    build_dataset_metadata,
    validate_dataset_metadata,
)
from test_rl_env import sample_market_data


def test_build_dataset_metadata_returns_valid_dataclass() -> None:
    metadata = build_dataset_metadata(
        dataset_name="SPY_5d_5m",
        source_name="yahoo_finance",
        frequency="5m",
        timezone="America/New_York",
        instrument_type="equity",
        data_basis="proxy",
    )

    assert isinstance(metadata, DatasetMetadata)
    assert metadata.data_basis == "proxy"
    assert metadata.contains_quotes is False


def test_attach_dataset_metadata_adds_constant_columns() -> None:
    attached = attach_dataset_metadata(
        sample_market_data(),
        build_dataset_metadata(
            dataset_name="XYZ_sample",
            source_name="unit_test",
            frequency="5m",
            timezone="America/New_York",
            instrument_type="equity",
            data_basis="proxy",
        ),
    )

    assert "dataset_name" in attached.columns
    assert set(attached["dataset_name"]) == {"XYZ_sample"}
    assert set(attached["data_basis"]) == {"proxy"}


def test_validate_dataset_metadata_rejects_invalid_basis() -> None:
    with pytest.raises(ValueError, match="data_basis"):
        validate_dataset_metadata(
            {
                "dataset_name": "bad",
                "source_name": "unit_test",
                "frequency": "5m",
                "timezone": "America/New_York",
                "instrument_type": "equity",
                "data_basis": "guessed",
                "contains_quotes": False,
                "contains_depth": False,
                "contains_order_events": False,
                "contains_trade_events": False,
            }
        )


def test_validate_dataset_metadata_requires_quotes_for_depth() -> None:
    with pytest.raises(ValueError, match="contains_quotes"):
        validate_dataset_metadata(
            {
                "dataset_name": "depth_only",
                "source_name": "synthetic_book",
                "frequency": "event",
                "timezone": "America/New_York",
                "instrument_type": "future",
                "data_basis": "synthetic",
                "contains_quotes": False,
                "contains_depth": True,
                "contains_order_events": True,
                "contains_trade_events": True,
            }
        )
