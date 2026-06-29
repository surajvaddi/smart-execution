"""Core limit-order-book domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


VALID_BOOK_SIDES = {"buy", "sell"}
VALID_OWNER_TYPES = {"external", "strategy", "simulator"}
VALID_FILL_STATUSES = {"filled", "partial", "unfilled", "cancelled", "rejected"}
VALID_DATA_BASIS = {"real", "synthetic", "proxy"}


@dataclass(frozen=True)
class RestingOrder:
    """One resting order in the simulated book."""

    order_id: str
    parent_order_id: str | None
    child_order_id: str | None
    side: Literal["buy", "sell"]
    price: float
    visible_quantity: float
    reserve_quantity: float
    submitted_at: pd.Timestamp
    effective_at: pd.Timestamp
    owner_type: str
    instrument_id: str

    def __post_init__(self) -> None:
        if self.side not in VALID_BOOK_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_BOOK_SIDES)}, got {self.side!r}.")
        if self.price <= 0:
            raise ValueError("price must be positive.")
        if self.visible_quantity < 0:
            raise ValueError("visible_quantity must be non-negative.")
        if self.reserve_quantity < 0:
            raise ValueError("reserve_quantity must be non-negative.")
        if self.visible_quantity + self.reserve_quantity <= 0:
            raise ValueError("order must have positive total quantity.")
        if self.owner_type not in VALID_OWNER_TYPES:
            raise ValueError(
                f"owner_type must be one of {sorted(VALID_OWNER_TYPES)}, got {self.owner_type!r}."
            )
        _require_timestamp(self.submitted_at, "submitted_at")
        _require_timestamp(self.effective_at, "effective_at")
        if self.effective_at < self.submitted_at:
            raise ValueError("effective_at must be on or after submitted_at.")
        if not self.order_id:
            raise ValueError("order_id must be non-empty.")
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")

    @property
    def total_quantity(self) -> float:
        """Return displayed plus reserve quantity."""
        return float(self.visible_quantity + self.reserve_quantity)


@dataclass(frozen=True)
class BookLevel:
    """One price level on one side of the book."""

    side: Literal["buy", "sell"]
    price: float
    orders: tuple[RestingOrder, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.side not in VALID_BOOK_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_BOOK_SIDES)}, got {self.side!r}.")
        if self.price <= 0:
            raise ValueError("price must be positive.")
        for order in self.orders:
            if order.side != self.side:
                raise ValueError("All orders in a level must share the level side.")
            if order.price != self.price:
                raise ValueError("All orders in a level must share the level price.")

    @property
    def total_visible_quantity(self) -> float:
        """Return total visible quantity resting at this level."""
        return float(sum(order.visible_quantity for order in self.orders))

    @property
    def total_reserve_quantity(self) -> float:
        """Return total reserve quantity resting at this level."""
        return float(sum(order.reserve_quantity for order in self.orders))


@dataclass(frozen=True)
class BookSnapshot:
    """One timestamped view of the book."""

    instrument_id: str
    timestamp: pd.Timestamp
    bids: tuple[BookLevel, ...] = field(default_factory=tuple)
    asks: tuple[BookLevel, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")
        _require_timestamp(self.timestamp, "timestamp")
        _validate_side_levels(self.bids, "buy", descending=True)
        _validate_side_levels(self.asks, "sell", descending=False)

    @property
    def best_bid(self) -> float | None:
        """Return best bid price when present."""
        return None if not self.bids else float(self.bids[0].price)

    @property
    def best_ask(self) -> float | None:
        """Return best ask price when present."""
        return None if not self.asks else float(self.asks[0].price)


@dataclass(frozen=True)
class TradePrint:
    """One matched trade in the synthetic market."""

    trade_id: str
    instrument_id: str
    timestamp: pd.Timestamp
    price: float
    quantity: float
    aggressor_side: Literal["buy", "sell"]
    buy_order_id: str | None
    sell_order_id: str | None

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("price must be positive.")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive.")
        if self.aggressor_side not in VALID_BOOK_SIDES:
            raise ValueError(
                f"aggressor_side must be one of {sorted(VALID_BOOK_SIDES)}, got {self.aggressor_side!r}."
            )
        if not self.trade_id:
            raise ValueError("trade_id must be non-empty.")
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")
        _require_timestamp(self.timestamp, "timestamp")


@dataclass(frozen=True)
class ExecutionReport:
    """Normalized execution result row for simulated fills."""

    execution_id: str
    instrument_id: str
    timestamp: pd.Timestamp
    order_id: str
    parent_order_id: str | None
    child_order_id: str | None
    side: Literal["buy", "sell"]
    submitted_quantity: float
    filled_quantity: float
    remaining_quantity: float
    fill_price: float | None
    fill_status: str
    execution_venue: str
    simulation_model: str
    data_basis: str
    queue_position_at_submit: int | None = None
    queue_position_at_fill: int | None = None
    latency_us: int | None = None
    book_level: float | None = None
    maker_flag: bool | None = None
    taker_flag: bool | None = None

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("execution_id must be non-empty.")
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")
        if not self.order_id:
            raise ValueError("order_id must be non-empty.")
        if self.side not in VALID_BOOK_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_BOOK_SIDES)}, got {self.side!r}.")
        if self.submitted_quantity <= 0:
            raise ValueError("submitted_quantity must be positive.")
        if self.filled_quantity < 0 or self.remaining_quantity < 0:
            raise ValueError("filled_quantity and remaining_quantity must be non-negative.")
        if self.filled_quantity + self.remaining_quantity > self.submitted_quantity + 1e-9:
            raise ValueError("filled_quantity plus remaining_quantity cannot exceed submitted_quantity.")
        if self.fill_status not in VALID_FILL_STATUSES:
            raise ValueError(
                f"fill_status must be one of {sorted(VALID_FILL_STATUSES)}, got {self.fill_status!r}."
            )
        if self.fill_price is not None and self.fill_price <= 0:
            raise ValueError("fill_price must be positive when provided.")
        if not self.execution_venue:
            raise ValueError("execution_venue must be non-empty.")
        if not self.simulation_model:
            raise ValueError("simulation_model must be non-empty.")
        if self.data_basis not in VALID_DATA_BASIS:
            raise ValueError(
                f"data_basis must be one of {sorted(VALID_DATA_BASIS)}, got {self.data_basis!r}."
            )
        _require_timestamp(self.timestamp, "timestamp")


def _require_timestamp(value: pd.Timestamp, label: str) -> None:
    """Validate that a timestamp is timezone-aware and concrete."""
    if not isinstance(value, pd.Timestamp):
        raise ValueError(f"{label} must be a pandas Timestamp.")
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware.")


def _validate_side_levels(
    levels: tuple[BookLevel, ...],
    expected_side: str,
    descending: bool,
) -> None:
    """Validate one side of a book snapshot."""
    prices = []
    for level in levels:
        if level.side != expected_side:
            raise ValueError(f"All levels on this side must be {expected_side}.")
        prices.append(level.price)
    ordered = sorted(prices, reverse=descending)
    if prices != ordered:
        direction = "descending" if descending else "ascending"
        raise ValueError(f"{expected_side} levels must be sorted in {direction} price order.")
