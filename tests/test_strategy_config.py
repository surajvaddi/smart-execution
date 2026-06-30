from __future__ import annotations

import pytest

from src.strategy_config import (
    AdaptiveConfig,
    AdaptiveParticipationConfig,
    ImplementationShortfallConfig,
    POVConfig,
    TWAPConfig,
    VWAPConfig,
)


def test_strategy_config_defaults_are_constructible() -> None:
    assert TWAPConfig().complete_on_last_bar is True
    assert VWAPConfig().minimum_expected_volume_share == pytest.approx(0.0)
    assert POVConfig().skip_zero_quantity_bars is True
    assert AdaptiveConfig().max_multiplier == pytest.approx(2.5)
    assert ImplementationShortfallConfig().max_frontload == pytest.approx(0.30)
    assert AdaptiveParticipationConfig().base_participation_rate == pytest.approx(0.10)


def test_adaptive_config_rejects_inverted_multiplier_bounds() -> None:
    with pytest.raises(ValueError, match="max_multiplier"):
        AdaptiveConfig(min_multiplier=1.5, max_multiplier=1.0)


def test_implementation_shortfall_config_rejects_negative_parameters() -> None:
    with pytest.raises(ValueError, match="risk_aversion"):
        ImplementationShortfallConfig(risk_aversion=-1.0)
    with pytest.raises(ValueError, match="max_frontload"):
        ImplementationShortfallConfig(max_frontload=-0.1)


def test_adaptive_participation_config_validates_rate_bounds() -> None:
    with pytest.raises(ValueError, match="base_participation_rate"):
        AdaptiveParticipationConfig(base_participation_rate=0.0)
    with pytest.raises(ValueError, match="min_participation_rate"):
        AdaptiveParticipationConfig(min_participation_rate=0.20, base_participation_rate=0.10)
    with pytest.raises(ValueError, match="max_participation_rate"):
        AdaptiveParticipationConfig(max_participation_rate=0.05, base_participation_rate=0.10)


def test_vwap_config_rejects_negative_expected_volume_floor() -> None:
    with pytest.raises(ValueError, match="minimum_expected_volume_share"):
        VWAPConfig(minimum_expected_volume_share=-0.01)
