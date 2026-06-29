"""Configuration objects for the synthetic LOB simulator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArrivalProcessConfig:
    """Config for synthetic limit-order arrivals."""

    events_per_step: int = 4
    price_offsets: tuple[int, ...] = (0, 1, 2)
    price_offset_probabilities: tuple[float, ...] = (0.5, 0.3, 0.2)
    min_quantity: float = 1.0
    max_quantity: float = 10.0

    def __post_init__(self) -> None:
        if self.events_per_step < 0:
            raise ValueError("events_per_step must be non-negative.")
        if not self.price_offsets:
            raise ValueError("price_offsets must not be empty.")
        if len(self.price_offsets) != len(self.price_offset_probabilities):
            raise ValueError("price_offsets and price_offset_probabilities must have equal length.")
        if any(probability < 0 for probability in self.price_offset_probabilities):
            raise ValueError("price_offset_probabilities must be non-negative.")
        if abs(sum(self.price_offset_probabilities) - 1.0) > 1e-9:
            raise ValueError("price_offset_probabilities must sum to 1.")
        if self.min_quantity <= 0 or self.max_quantity <= 0:
            raise ValueError("arrival quantities must be positive.")
        if self.min_quantity > self.max_quantity:
            raise ValueError("min_quantity must be less than or equal to max_quantity.")


@dataclass(frozen=True)
class CancellationProcessConfig:
    """Config for synthetic cancellations."""

    events_per_step: int = 2
    cancel_probability: float = 0.5
    partial_cancel_ratio: float = 0.5

    def __post_init__(self) -> None:
        if self.events_per_step < 0:
            raise ValueError("events_per_step must be non-negative.")
        if not 0.0 <= self.cancel_probability <= 1.0:
            raise ValueError("cancel_probability must be between 0 and 1.")
        if not 0.0 < self.partial_cancel_ratio <= 1.0:
            raise ValueError("partial_cancel_ratio must be in the interval (0, 1].")


@dataclass(frozen=True)
class LatencyModelConfig:
    """Config for gateway and exchange latency sampling."""

    gateway_min_us: int = 50
    gateway_max_us: int = 250
    exchange_min_us: int = 100
    exchange_max_us: int = 500

    def __post_init__(self) -> None:
        for field_name in [
            "gateway_min_us",
            "gateway_max_us",
            "exchange_min_us",
            "exchange_max_us",
        ]:
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative.")
        if self.gateway_min_us > self.gateway_max_us:
            raise ValueError("gateway_min_us must be less than or equal to gateway_max_us.")
        if self.exchange_min_us > self.exchange_max_us:
            raise ValueError("exchange_min_us must be less than or equal to exchange_max_us.")


@dataclass(frozen=True)
class BookInitializationConfig:
    """Config for initial synthetic book shape."""

    mid_price: float = 100.0
    tick_size: float = 0.5
    levels_per_side: int = 3
    base_quantity: float = 10.0
    quantity_step: float = 2.0
    imbalance_ratio: float = 1.0

    def __post_init__(self) -> None:
        if self.mid_price <= 0:
            raise ValueError("mid_price must be positive.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive.")
        if self.levels_per_side <= 0:
            raise ValueError("levels_per_side must be positive.")
        if self.base_quantity <= 0:
            raise ValueError("base_quantity must be positive.")
        if self.quantity_step < 0:
            raise ValueError("quantity_step must be non-negative.")
        if self.imbalance_ratio <= 0:
            raise ValueError("imbalance_ratio must be positive.")
