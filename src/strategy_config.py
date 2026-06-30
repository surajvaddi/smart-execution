"""Explicit configuration surfaces for execution strategy families."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TWAPConfig:
    """Configuration for TWAP schedules."""

    complete_on_last_bar: bool = True


@dataclass(frozen=True)
class VWAPConfig:
    """Configuration for VWAP schedules."""

    complete_on_last_bar: bool = True
    minimum_expected_volume_share: float = 0.0

    def __post_init__(self) -> None:
        if self.minimum_expected_volume_share < 0:
            raise ValueError("minimum_expected_volume_share must be non-negative.")


@dataclass(frozen=True)
class POVConfig:
    """Configuration for POV schedules."""

    skip_zero_quantity_bars: bool = True


@dataclass(frozen=True)
class AdaptiveConfig:
    """Configuration for the heuristic adaptive schedule."""

    bullish_signal_multiplier: float = 1.4
    bearish_signal_multiplier: float = 0.7
    spread_penalty_multiplier: float = 0.75
    volatility_penalty_multiplier: float = 0.85
    liquidity_boost_multiplier: float = 1.2
    urgency_weight: float = 1.0
    min_multiplier: float = 0.25
    max_multiplier: float = 2.5

    def __post_init__(self) -> None:
        if self.min_multiplier <= 0:
            raise ValueError("min_multiplier must be positive.")
        if self.max_multiplier < self.min_multiplier:
            raise ValueError("max_multiplier must be at least min_multiplier.")


@dataclass(frozen=True)
class ImplementationShortfallConfig:
    """Configuration for implementation shortfall schedules."""

    risk_aversion: float = 1.0
    max_frontload: float = 0.30

    def __post_init__(self) -> None:
        if self.risk_aversion < 0:
            raise ValueError("risk_aversion must be non-negative.")
        if self.max_frontload < 0:
            raise ValueError("max_frontload must be non-negative.")


@dataclass(frozen=True)
class AdaptiveParticipationConfig:
    """Configuration for adaptive participation schedules."""

    base_participation_rate: float = 0.10
    min_participation_rate: float = 0.02
    max_participation_rate: float = 0.25
    signal_weight: float = 0.50
    liquidity_weight: float = 0.30
    volatility_penalty_weight: float = 0.40

    def __post_init__(self) -> None:
        for field_name in [
            "base_participation_rate",
            "min_participation_rate",
            "max_participation_rate",
        ]:
            value = getattr(self, field_name)
            if value <= 0 or value > 1:
                raise ValueError(f"{field_name} must be in the interval (0, 1].")
        if self.min_participation_rate > self.base_participation_rate:
            raise ValueError("min_participation_rate cannot exceed base_participation_rate.")
        if self.max_participation_rate < self.base_participation_rate:
            raise ValueError("max_participation_rate cannot be below base_participation_rate.")
