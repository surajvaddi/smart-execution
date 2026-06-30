"""Queue-aware execution child-order state helpers for the synthetic LOB path."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd


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
