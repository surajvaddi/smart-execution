from __future__ import annotations

import pytest

from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig, CancellationProcessConfig, LatencyModelConfig


def test_arrival_process_config_validates_inputs() -> None:
    config = ArrivalProcessConfig()
    assert config.events_per_step == 4

    with pytest.raises(ValueError, match="buy_probability"):
        ArrivalProcessConfig(buy_probability=1.5)


def test_cancellation_config_validates_fraction() -> None:
    with pytest.raises(ValueError, match="partial_cancel_fraction"):
        CancellationProcessConfig(partial_cancel_fraction=0.0)


def test_latency_model_config_validates_ranges() -> None:
    with pytest.raises(ValueError, match="lower bound"):
        LatencyModelConfig(gateway_latency_us=(10, 5))


def test_book_initialization_config_requires_positive_values() -> None:
    with pytest.raises(ValueError, match="tick_size"):
        BookInitializationConfig(tick_size=0.0)
