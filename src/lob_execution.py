"""Queue-aware execution child-order state helpers for the synthetic LOB path."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from src.lob_types import BookSnapshot, RestingOrder, TradePrint
from src.matching_engine import execute_market_order, submit_limit_order


@dataclass(frozen=True)
class ChildOrderState:
    """State carried by one execution child order across LOB steps."""

    child_order_id: str
    parent_order_id: str
    instrument_id: str
    side: str
    submitted_quantity: float
    remaining_quantity: float
    queue_position: int | None
    submitted_at: pd.Timestamp
    last_updated_at: pd.Timestamp
    placement_style: str

    def __post_init__(self) -> None:
        if not self.child_order_id:
            raise ValueError("child_order_id must be non-empty.")
        if not self.parent_order_id:
            raise ValueError("parent_order_id must be non-empty.")
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty.")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'.")
        if self.submitted_quantity <= 0:
            raise ValueError("submitted_quantity must be positive.")
        if self.remaining_quantity < 0 or self.remaining_quantity > self.submitted_quantity:
            raise ValueError("remaining_quantity must be between 0 and submitted_quantity.")
        if self.queue_position is not None and self.queue_position < 1:
            raise ValueError("queue_position must be positive when provided.")
        if self.submitted_at.tzinfo is None or self.last_updated_at.tzinfo is None:
            raise ValueError("submitted_at and last_updated_at must be timezone-aware.")
        if self.last_updated_at < self.submitted_at:
            raise ValueError("last_updated_at must be on or after submitted_at.")
        if not self.placement_style:
            raise ValueError("placement_style must be non-empty.")


def create_child_order_state(
    child_order_id: str,
    parent_order_id: str,
    instrument_id: str,
    side: str,
    quantity: float,
    submitted_at: pd.Timestamp,
    placement_style: str,
    queue_position: int | None = None,
) -> ChildOrderState:
    """Create a new queue-aware child-order state."""
    return ChildOrderState(
        child_order_id=child_order_id,
        parent_order_id=parent_order_id,
        instrument_id=instrument_id,
        side=side,
        submitted_quantity=quantity,
        remaining_quantity=quantity,
        queue_position=queue_position,
        submitted_at=submitted_at,
        last_updated_at=submitted_at,
        placement_style=placement_style,
    )


def update_queue_position(
    state: ChildOrderState,
    queue_position: int | None,
    updated_at: pd.Timestamp,
    remaining_quantity: float | None = None,
) -> ChildOrderState:
    """Return an updated child-order state after queue movement or partial fill."""
    if updated_at.tzinfo is None:
        raise ValueError("updated_at must be timezone-aware.")
    if updated_at < state.last_updated_at:
        raise ValueError("updated_at must be on or after the prior last_updated_at.")
    if queue_position is not None and queue_position < 1:
        raise ValueError("queue_position must be positive when provided.")

    next_remaining = state.remaining_quantity if remaining_quantity is None else remaining_quantity
    if next_remaining < 0 or next_remaining > state.submitted_quantity:
        raise ValueError("remaining_quantity must stay between 0 and submitted_quantity.")

    return replace(
        state,
        queue_position=queue_position,
        remaining_quantity=next_remaining,
        last_updated_at=updated_at,
    )


def submit_execution_child_order(
    book: BookSnapshot,
    state: ChildOrderState,
    price: float | None = None,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Submit a child order using market or limit semantics from its placement style."""
    if state.placement_style == "market":
        return submit_market_execution_child(book, state)
    if price is None:
        raise ValueError("price is required for non-market child-order submission.")
    return submit_limit_execution_child(book, state, price=price)


def submit_market_execution_child(
    book: BookSnapshot,
    state: ChildOrderState,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Execute a child order aggressively against the current book."""
    updated_book, prints, remaining_quantity = execute_market_order(
        book,
        side=state.side,
        quantity=state.remaining_quantity,
        timestamp=state.last_updated_at,
        order_id=state.child_order_id,
    )
    updated_state = update_queue_position(
        state,
        queue_position=None,
        updated_at=state.last_updated_at,
        remaining_quantity=remaining_quantity,
    )
    return updated_book, updated_state, prints


def submit_limit_execution_child(
    book: BookSnapshot,
    state: ChildOrderState,
    price: float,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Submit a resting limit child order into the matching engine."""
    resting_order = RestingOrder(
        order_id=state.child_order_id,
        parent_order_id=state.parent_order_id,
        child_order_id=state.child_order_id,
        side=state.side,
        price=price,
        visible_quantity=state.remaining_quantity,
        reserve_quantity=0.0,
        submitted_at=state.submitted_at,
        effective_at=state.last_updated_at,
        owner_type="strategy",
        instrument_id=state.instrument_id,
    )
    updated_book, prints, residual_order = submit_limit_order(book, resting_order)
    next_queue_position = None
    next_remaining = 0.0
    if residual_order is not None:
        next_remaining = residual_order.total_quantity
        next_queue_position = _queue_position_for_order(updated_book, residual_order.order_id)

    updated_state = update_queue_position(
        state,
        queue_position=next_queue_position,
        updated_at=state.last_updated_at,
        remaining_quantity=next_remaining,
    )
    return updated_book, updated_state, prints


def _queue_position_for_order(book: BookSnapshot, order_id: str) -> int | None:
    """Return the current queue slot for one resting order."""
    for side_levels in [book.bids, book.asks]:
        for level in side_levels:
            for queue_position, order in enumerate(level.orders, start=1):
                if order.order_id == order_id:
                    return queue_position
    return None
