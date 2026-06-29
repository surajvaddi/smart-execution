"""Serialization and deterministic replay helpers for LOB events."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

import pandas as pd

from src.lob_events import CancelEvent, EventBatch, LimitAddEvent, LobEvent, MarketOrderEvent, ModifyEvent
from src.lob_types import BookLevel, BookSnapshot, ExecutionReport, RestingOrder, TradePrint


def snapshot_to_frame(snapshot: BookSnapshot) -> pd.DataFrame:
    """Flatten one book snapshot into one row per resting order."""
    rows = []
    for side_levels in [snapshot.bids, snapshot.asks]:
        for level in side_levels:
            for queue_position, order in enumerate(level.orders, start=1):
                rows.append(
                    {
                        "timestamp": snapshot.timestamp,
                        "instrument_id": snapshot.instrument_id,
                        "side": level.side,
                        "price": level.price,
                        "queue_position": queue_position,
                        "order_id": order.order_id,
                        "parent_order_id": order.parent_order_id,
                        "child_order_id": order.child_order_id,
                        "visible_quantity": order.visible_quantity,
                        "reserve_quantity": order.reserve_quantity,
                        "owner_type": order.owner_type,
                    }
                )
    return pd.DataFrame(rows)


def events_to_frame(events: EventBatch | list[LobEvent] | tuple[LobEvent, ...]) -> pd.DataFrame:
    """Flatten events into a deterministic table."""
    normalized = _sorted_events(events)
    rows = []
    for event in normalized:
        row = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "instrument_id": event.instrument_id,
            "source": event.source,
            "event_time": event.event_time,
            "effective_time": event.effective_time,
            "random_seed": event.random_seed,
        }
        if isinstance(event, LimitAddEvent):
            row.update(
                {
                    "order_id": event.order.order_id,
                    "side": event.order.side,
                    "price": event.order.price,
                    "visible_quantity": event.order.visible_quantity,
                    "reserve_quantity": event.order.reserve_quantity,
                }
            )
        elif isinstance(event, MarketOrderEvent):
            row.update({"side": event.side, "quantity": event.quantity})
        elif isinstance(event, CancelEvent):
            row.update({"order_id": event.order_id, "cancel_quantity": event.cancel_quantity})
        elif isinstance(event, ModifyEvent):
            row.update(
                {
                    "order_id": event.order_id,
                    "new_price": event.new_price,
                    "new_visible_quantity": event.new_visible_quantity,
                    "new_reserve_quantity": event.new_reserve_quantity,
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def execution_reports_to_frame(reports: list[ExecutionReport] | tuple[ExecutionReport, ...]) -> pd.DataFrame:
    """Flatten normalized execution reports to a table."""
    return pd.DataFrame([asdict(report) for report in reports])


def replay_events(
    initial_snapshot: BookSnapshot,
    events: EventBatch | list[LobEvent] | tuple[LobEvent, ...],
) -> tuple[BookSnapshot, list[TradePrint]]:
    """Reconstruct a final book snapshot by replaying events deterministically."""
    working_orders = _snapshot_order_lists(initial_snapshot)
    prints: list[TradePrint] = []

    for event in _sorted_events(events):
        if isinstance(event, LimitAddEvent):
            working_orders[event.order.side].append(event.order)
        elif isinstance(event, CancelEvent):
            _apply_cancel(working_orders, event)
        elif isinstance(event, ModifyEvent):
            _apply_modify(working_orders, event)
        elif isinstance(event, MarketOrderEvent):
            prints.extend(_apply_market_order(working_orders, event))

    final_snapshot = _build_snapshot(
        instrument_id=initial_snapshot.instrument_id,
        timestamp=_final_timestamp(initial_snapshot.timestamp, events),
        orders_by_side=working_orders,
    )
    return final_snapshot, prints


def _sorted_events(events: EventBatch | list[LobEvent] | tuple[LobEvent, ...]) -> tuple[LobEvent, ...]:
    """Normalize event input into a deterministic tuple."""
    if isinstance(events, EventBatch):
        return events.sorted_events()
    return EventBatch(tuple(events)).sorted_events()


def _snapshot_order_lists(snapshot: BookSnapshot) -> dict[str, list[RestingOrder]]:
    """Convert snapshot levels into mutable per-side order lists."""
    orders_by_side: dict[str, list[RestingOrder]] = {"buy": [], "sell": []}
    for level in snapshot.bids:
        orders_by_side["buy"].extend(level.orders)
    for level in snapshot.asks:
        orders_by_side["sell"].extend(level.orders)
    return orders_by_side


def _apply_cancel(orders_by_side: dict[str, list[RestingOrder]], event: CancelEvent) -> None:
    """Apply a cancellation to the current order state."""
    for side, orders in orders_by_side.items():
        for idx, order in enumerate(orders):
            if order.order_id != event.order_id:
                continue
            if event.cancel_quantity is None or event.cancel_quantity >= order.total_quantity:
                del orders[idx]
                return
            remaining_total = order.total_quantity - event.cancel_quantity
            visible_quantity = min(order.visible_quantity, remaining_total)
            reserve_quantity = max(remaining_total - visible_quantity, 0.0)
            orders[idx] = RestingOrder(
                order_id=order.order_id,
                parent_order_id=order.parent_order_id,
                child_order_id=order.child_order_id,
                side=order.side,
                price=order.price,
                visible_quantity=visible_quantity,
                reserve_quantity=reserve_quantity,
                submitted_at=order.submitted_at,
                effective_at=order.effective_at,
                owner_type=order.owner_type,
                instrument_id=order.instrument_id,
            )
            return


def _apply_modify(orders_by_side: dict[str, list[RestingOrder]], event: ModifyEvent) -> None:
    """Apply a modification to a current resting order."""
    for side, orders in orders_by_side.items():
        for idx, order in enumerate(orders):
            if order.order_id != event.order_id:
                continue
            new_order = RestingOrder(
                order_id=order.order_id,
                parent_order_id=order.parent_order_id,
                child_order_id=order.child_order_id,
                side=order.side,
                price=order.price if event.new_price is None else event.new_price,
                visible_quantity=(
                    order.visible_quantity if event.new_visible_quantity is None else event.new_visible_quantity
                ),
                reserve_quantity=(
                    order.reserve_quantity if event.new_reserve_quantity is None else event.new_reserve_quantity
                ),
                submitted_at=order.submitted_at,
                effective_at=event.effective_time if event.new_price is not None else order.effective_at,
                owner_type=order.owner_type,
                instrument_id=order.instrument_id,
            )
            del orders[idx]
            orders.append(new_order)
            return


def _apply_market_order(
    orders_by_side: dict[str, list[RestingOrder]],
    event: MarketOrderEvent,
) -> list[TradePrint]:
    """Apply a market order against the opposite side of the book."""
    passive_side = "sell" if event.side == "buy" else "buy"
    ordered_book = _sorted_orders(orders_by_side[passive_side])
    prints: list[TradePrint] = []
    remaining_quantity = event.quantity
    updated_orders: list[RestingOrder] = []

    for order in ordered_book:
        if remaining_quantity <= 0:
            updated_orders.append(order)
            continue
        traded_quantity = min(order.visible_quantity, remaining_quantity)
        if traded_quantity > 0:
            trade_id = f"{event.event_id}:{order.order_id}"
            prints.append(
                TradePrint(
                    trade_id=trade_id,
                    instrument_id=event.instrument_id,
                    timestamp=event.effective_time,
                    price=order.price,
                    quantity=traded_quantity,
                    aggressor_side=event.side,
                    buy_order_id=None if event.side == "sell" else event.child_order_id or event.event_id,
                    sell_order_id=None if event.side == "buy" else event.child_order_id or event.event_id,
                )
            )
            remaining_quantity -= traded_quantity
        remaining_total = order.total_quantity - traded_quantity
        if remaining_total > 0:
            updated_orders.append(
                RestingOrder(
                    order_id=order.order_id,
                    parent_order_id=order.parent_order_id,
                    child_order_id=order.child_order_id,
                    side=order.side,
                    price=order.price,
                    visible_quantity=min(order.visible_quantity - traded_quantity, remaining_total),
                    reserve_quantity=max(remaining_total - max(order.visible_quantity - traded_quantity, 0.0), 0.0),
                    submitted_at=order.submitted_at,
                    effective_at=order.effective_at,
                    owner_type=order.owner_type,
                    instrument_id=order.instrument_id,
                )
            )

    orders_by_side[passive_side] = updated_orders
    return prints


def _sorted_orders(orders: list[RestingOrder]) -> list[RestingOrder]:
    """Sort resting orders into price-time priority."""
    if not orders:
        return []
    side = orders[0].side
    reverse = side == "buy"
    return sorted(orders, key=lambda order: ((-order.price) if reverse else order.price, order.effective_at, order.order_id))


def _build_snapshot(
    instrument_id: str,
    timestamp: pd.Timestamp,
    orders_by_side: dict[str, list[RestingOrder]],
) -> BookSnapshot:
    """Build a new snapshot from current mutable order lists."""
    levels_by_side: dict[str, dict[float, list[RestingOrder]]] = {
        "buy": defaultdict(list),
        "sell": defaultdict(list),
    }
    for side, orders in orders_by_side.items():
        for order in _sorted_orders(orders):
            levels_by_side[side][order.price].append(order)

    bids = tuple(
        BookLevel(side="buy", price=price, orders=tuple(levels_by_side["buy"][price]))
        for price in sorted(levels_by_side["buy"].keys(), reverse=True)
    )
    asks = tuple(
        BookLevel(side="sell", price=price, orders=tuple(levels_by_side["sell"][price]))
        for price in sorted(levels_by_side["sell"].keys())
    )
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=bids, asks=asks)


def _final_timestamp(
    fallback: pd.Timestamp,
    events: EventBatch | list[LobEvent] | tuple[LobEvent, ...],
) -> pd.Timestamp:
    """Return the final effective timestamp after replay."""
    normalized = _sorted_events(events)
    if not normalized:
        return fallback
    return normalized[-1].effective_time
