from __future__ import annotations

import pytest

from src.lob_simulator_config import (
    ArrivalProcessConfig,
    BookInitializationConfig,
    CancellationProcessConfig,
    LatencyModelConfig,
)


def test_arrival_process_config_validates_probability_sum() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        ArrivalProcessConfig(price_offset_probabilities=(0.4, 0.4, 0.4))


def test_cancellation_process_config_validates_probability() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        CancellationProcessConfig(cancel_probability=1.5)


def test_latency_model_config_validates_bounds() -> None:
    with pytest.raises(ValueError, match="gateway_min_us"):
        LatencyModelConfig(gateway_min_us=10, gateway_max_us=1)


def test_book_initialization_config_validates_positive_values() -> None:
    with pytest.raises(ValueError, match="mid_price"):
        BookInitializationConfig(mid_price=0.0)
