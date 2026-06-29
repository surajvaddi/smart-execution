"""Configuration models for synthetic LOB simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArrivalProcessConfig:
    """Controls exogenous limit-order arrival behavior."""

    events_per_step: int = 4
    buy_probability: float = 0.5
    price_offset_levels: tuple[int, ...] = (0, 1, 2)
    price_offset_probabilities: tuple[float, ...] = (0.5, 0.3, 0.2)
    min_quantity: float = 1.0
    max_quantity: float = 10.0

    def __post_init__(self) -> None:
        if self.events_per_step < 0:
            raise ValueError("events_per_step must be non-negative.")
        _require_probability(self.buy_probability, "buy_probability")
        _require_matching_weights(self.price_offset_levels, self.price_offset_probabilities, "price offsets")
        if self.min_quantity <= 0 or self.max_quantity <= 0:
            raise ValueError("min_quantity and max_quantity must be positive.")
        if self.min_quantity > self.max_quantity:
            raise ValueError("min_quantity must be less than or equal to max_quantity.")


@dataclass(frozen=True)
class CancellationProcessConfig:
    """Controls exogenous order cancellation behavior."""

    events_per_step: int = 2
    cancel_partial_probability: float = 0.5
    partial_cancel_fraction: float = 0.5

    def __post_init__(self) -> None:
        if self.events_per_step < 0:
            raise ValueError("events_per_step must be non-negative.")
        _require_probability(self.cancel_partial_probability, "cancel_partial_probability")
        if not 0 < self.partial_cancel_fraction <= 1:
            raise ValueError("partial_cancel_fraction must be in the interval (0, 1].")


@dataclass(frozen=True)
class LatencyModelConfig:
    """Controls gateway and exchange latency for synthetic events."""

    gateway_latency_us: tuple[int, int] = (50, 150)
    exchange_latency_us: tuple[int, int] = (100, 300)

    def __post_init__(self) -> None:
        _require_latency_range(self.gateway_latency_us, "gateway_latency_us")
        _require_latency_range(self.exchange_latency_us, "exchange_latency_us")


@dataclass(frozen=True)
class BookInitializationConfig:
    """Controls synthetic initial depth construction."""

    mid_price: float = 100.0
    tick_size: float = 0.5
    levels_per_side: int = 3
    visible_quantity: float = 10.0
    spread_ticks: int = 2

    def __post_init__(self) -> None:
        if self.mid_price <= 0:
            raise ValueError("mid_price must be positive.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive.")
        if self.levels_per_side <= 0:
            raise ValueError("levels_per_side must be positive.")
        if self.visible_quantity <= 0:
            raise ValueError("visible_quantity must be positive.")
        if self.spread_ticks <= 0:
            raise ValueError("spread_ticks must be positive.")


def _require_probability(value: float, label: str) -> None:
    """Validate a probability-like value."""
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{label} must be between 0 and 1, got {value!r}.")


def _require_matching_weights(levels: tuple[int, ...], weights: tuple[float, ...], label: str) -> None:
    """Validate paired categorical weights."""
    if not levels:
        raise ValueError(f"{label} must contain at least one level.")
    if len(levels) != len(weights):
        raise ValueError(f"{label} levels and probabilities must have the same length.")
    if any(level < 0 for level in levels):
        raise ValueError(f"{label} levels must be non-negative.")
    if any(weight < 0 for weight in weights):
        raise ValueError(f"{label} probabilities must be non-negative.")
    if sum(weights) <= 0:
        raise ValueError(f"{label} probabilities must sum to a positive value.")


def _require_latency_range(value: tuple[int, int], label: str) -> None:
    """Validate inclusive integer latency range."""
    if len(value) != 2:
        raise ValueError(f"{label} must be a two-item tuple.")
    lo, hi = value
    if lo < 0 or hi < 0:
        raise ValueError(f"{label} values must be non-negative.")
    if lo > hi:
        raise ValueError(f"{label} lower bound must be less than or equal to upper bound.")
