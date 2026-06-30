"""Queue-aware execution child-order state helpers for the synthetic LOB path."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from src.lob_types import BookSnapshot, ExecutionReport, RestingOrder, TradePrint
from src.matching_engine import cancel_order, execute_market_order, submit_limit_order


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


def place_passive_child_order(
    book: BookSnapshot,
    state: ChildOrderState,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Post a child order at the same-side touch without crossing the spread."""
    return submit_limit_execution_child(book, state, price=_passive_limit_price(book, state.side))


def place_aggressive_child_order(
    book: BookSnapshot,
    state: ChildOrderState,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Post a child order at the opposite-side touch so it crosses immediately."""
    return submit_limit_execution_child(book, state, price=_aggressive_limit_price(book, state.side))


def place_midpoint_child_order(
    book: BookSnapshot,
    state: ChildOrderState,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Post a child order at the current midpoint between the best bid and ask."""
    return submit_limit_execution_child(book, state, price=_midpoint_limit_price(book))


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


def cancel_execution_child_order(
    book: BookSnapshot,
    state: ChildOrderState,
    updated_at: pd.Timestamp,
    cancel_quantity: float | None = None,
) -> tuple[BookSnapshot, ChildOrderState]:
    """Cancel all or part of a resting child order and sync queue-aware state."""
    if updated_at.tzinfo is None:
        raise ValueError("updated_at must be timezone-aware.")
    if updated_at < state.last_updated_at:
        raise ValueError("updated_at must be on or after the prior last_updated_at.")
    if cancel_quantity is not None and cancel_quantity <= 0:
        raise ValueError("cancel_quantity must be positive when provided.")

    updated_book = cancel_order(
        book,
        state.child_order_id,
        cancel_quantity=cancel_quantity,
        timestamp=updated_at,
    )
    queue_position = _queue_position_for_order(updated_book, state.child_order_id)
    remaining_quantity = _remaining_quantity_for_order(updated_book, state.child_order_id)
    updated_state = update_queue_position(
        state,
        queue_position=queue_position,
        updated_at=updated_at,
        remaining_quantity=remaining_quantity,
    )
    return updated_book, updated_state


def cancel_replace_child_order(
    book: BookSnapshot,
    state: ChildOrderState,
    updated_at: pd.Timestamp,
    replacement_price: float,
) -> tuple[BookSnapshot, ChildOrderState, list[TradePrint]]:
    """Cancel a resting child order and repost the remainder at a new price."""
    canceled_book, canceled_state = cancel_execution_child_order(
        book,
        state,
        updated_at=updated_at,
    )
    replacement_state = update_queue_position(
        canceled_state,
        queue_position=None,
        updated_at=updated_at,
        remaining_quantity=state.remaining_quantity,
    )
    return submit_limit_execution_child(
        canceled_book,
        replacement_state,
        price=replacement_price,
    )


def cancel_stale_child_orders(
    book: BookSnapshot,
    child_states: list[ChildOrderState],
    updated_at: pd.Timestamp,
    stale_after: pd.Timedelta,
) -> tuple[BookSnapshot, list[ChildOrderState]]:
    """Cancel still-resting child orders whose last update is older than a threshold."""
    if updated_at.tzinfo is None:
        raise ValueError("updated_at must be timezone-aware.")
    if stale_after <= pd.Timedelta(0):
        raise ValueError("stale_after must be positive.")

    next_book = book
    next_states: list[ChildOrderState] = []
    for state in child_states:
        age = updated_at - state.last_updated_at
        should_cancel = state.remaining_quantity > 0 and state.queue_position is not None and age >= stale_after
        if should_cancel:
            next_book, canceled_state = cancel_execution_child_order(
                next_book,
                state,
                updated_at=updated_at,
            )
            next_states.append(canceled_state)
            continue
        next_states.append(state)
    synced_states = [_sync_child_state_to_book(next_book, state, updated_at) for state in next_states]
    return next_book, synced_states


def build_child_execution_report(
    initial_state: ChildOrderState,
    updated_state: ChildOrderState,
    prints: list[TradePrint],
    timestamp: pd.Timestamp,
    execution_id: str | None = None,
    execution_venue: str = "synthetic_primary",
    simulation_model: str = "lob_backtest",
    data_basis: str = "synthetic",
    latency_us: int | None = None,
) -> ExecutionReport:
    """Build one normalized execution report from a child-order state transition."""
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware.")

    filled_quantity = float(initial_state.remaining_quantity - updated_state.remaining_quantity)
    if filled_quantity < 0:
        raise ValueError("updated_state cannot have more remaining quantity than initial_state.")

    fill_price = None
    if filled_quantity > 0:
        total_notional = sum(print_.price * print_.quantity for print_ in prints)
        total_quantity = sum(print_.quantity for print_ in prints)
        if total_quantity <= 0:
            raise ValueError("prints must include positive quantity when a fill occurred.")
        fill_price = float(total_notional / total_quantity)

    if updated_state.remaining_quantity == 0:
        fill_status = "filled"
    elif filled_quantity > 0:
        fill_status = "partial"
    else:
        fill_status = "unfilled"

    maker_flag, taker_flag = _liquidity_flags(initial_state, filled_quantity)
    book_level = fill_price if fill_price is not None else None

    return ExecutionReport(
        execution_id=execution_id or f"{initial_state.child_order_id}_report",
        instrument_id=initial_state.instrument_id,
        timestamp=timestamp,
        order_id=initial_state.child_order_id,
        parent_order_id=initial_state.parent_order_id,
        child_order_id=initial_state.child_order_id,
        side=initial_state.side,
        submitted_quantity=initial_state.submitted_quantity,
        filled_quantity=filled_quantity,
        remaining_quantity=updated_state.remaining_quantity,
        fill_price=fill_price,
        fill_status=fill_status,
        execution_venue=execution_venue,
        simulation_model=simulation_model,
        data_basis=data_basis,
        queue_position_at_submit=initial_state.queue_position,
        queue_position_at_fill=updated_state.queue_position,
        latency_us=latency_us,
        book_level=book_level,
        maker_flag=maker_flag,
        taker_flag=taker_flag,
    )


def _queue_position_for_order(book: BookSnapshot, order_id: str) -> int | None:
    """Return the current queue slot for one resting order."""
    for side_levels in [book.bids, book.asks]:
        for level in side_levels:
            for queue_position, order in enumerate(level.orders, start=1):
                if order.order_id == order_id:
                    return queue_position
    return None


def _remaining_quantity_for_order(book: BookSnapshot, order_id: str) -> float:
    """Return the current total resting quantity for one order, or zero if absent."""
    for side_levels in [book.bids, book.asks]:
        for level in side_levels:
            for order in level.orders:
                if order.order_id == order_id:
                    return order.total_quantity
    return 0.0


def _passive_limit_price(book: BookSnapshot, side: str) -> float:
    """Resolve the same-side top-of-book price for passive posting."""
    if side == "buy":
        if book.best_bid is None:
            raise ValueError("cannot place passive buy without a best bid.")
        return book.best_bid
    if book.best_ask is None:
        raise ValueError("cannot place passive sell without a best ask.")
    return book.best_ask


def _aggressive_limit_price(book: BookSnapshot, side: str) -> float:
    """Resolve the opposite-side top-of-book price for aggressive posting."""
    if side == "buy":
        if book.best_ask is None:
            raise ValueError("cannot place aggressive buy without a best ask.")
        return book.best_ask
    if book.best_bid is None:
        raise ValueError("cannot place aggressive sell without a best bid.")
    return book.best_bid


def _midpoint_limit_price(book: BookSnapshot) -> float:
    """Resolve the midpoint between the current best bid and ask."""
    if book.best_bid is None or book.best_ask is None:
        raise ValueError("cannot place midpoint order without both best bid and best ask.")
    return float((book.best_bid + book.best_ask) / 2.0)


def _liquidity_flags(state: ChildOrderState, filled_quantity: float) -> tuple[bool | None, bool | None]:
    """Infer simple maker/taker flags from placement style for current LOB slices."""
    if filled_quantity <= 0:
        return None, None
    if state.placement_style == "market":
        return False, True
    if "aggressive" in state.placement_style:
        return False, True
    return True, False


def _sync_child_state_to_book(
    book: BookSnapshot,
    state: ChildOrderState,
    updated_at: pd.Timestamp,
) -> ChildOrderState:
    """Refresh queue position and resting quantity for a child order from the book."""
    queue_position = _queue_position_for_order(book, state.child_order_id)
    remaining_quantity = _remaining_quantity_for_order(book, state.child_order_id)
    if queue_position == state.queue_position and remaining_quantity == state.remaining_quantity:
        return state
    return update_queue_position(
        state,
        queue_position=queue_position,
        updated_at=updated_at,
        remaining_quantity=remaining_quantity,
    )
