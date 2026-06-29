"""Price-time priority matching engine primitives."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

import pandas as pd

from src.lob_types import BookLevel, BookSnapshot, RestingOrder, TradePrint


def create_empty_book(instrument_id: str, timestamp: pd.Timestamp) -> BookSnapshot:
    """Return an empty book snapshot for one instrument."""
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=(), asks=())


def best_bid(book: BookSnapshot) -> BookLevel | None:
    """Return the top bid level when available."""
    return book.bids[0] if book.bids else None


def best_ask(book: BookSnapshot) -> BookLevel | None:
    """Return the top ask level when available."""
    return book.asks[0] if book.asks else None


def add_price_level(book: BookSnapshot, level: BookLevel) -> BookSnapshot:
    """Insert or replace one price level while preserving side ordering."""
    levels_by_side = _levels_to_dict(book)
    levels_by_side[level.side][level.price] = list(level.orders)
    return _build_snapshot(book.instrument_id, book.timestamp, levels_by_side)


def remove_price_level_if_empty(book: BookSnapshot, side: str, price: float) -> BookSnapshot:
    """Remove a side/price level only if it currently exists and is empty."""
    levels_by_side = _levels_to_dict(book)
    orders = levels_by_side[side].get(price)
    if orders == []:
        del levels_by_side[side][price]
    return _build_snapshot(book.instrument_id, book.timestamp, levels_by_side)


def submit_limit_order(
    book: BookSnapshot,
    order: RestingOrder,
) -> tuple[BookSnapshot, list[TradePrint], RestingOrder | None]:
    """Submit a limit order, matching immediately if it crosses."""
    _require_same_instrument(book, order.instrument_id)
    if _is_marketable(book, order):
        return match_crossing_limit_order(book, order)

    levels_by_side = _levels_to_dict(book)
    levels_by_side[order.side].setdefault(order.price, [])
    levels_by_side[order.side][order.price].append(order)
    return _build_snapshot(order.instrument_id, order.effective_at, levels_by_side), [], order


def execute_market_order(
    book: BookSnapshot,
    side: str,
    quantity: float,
    timestamp: pd.Timestamp,
    order_id: str = "market_order",
) -> tuple[BookSnapshot, list[TradePrint], float]:
    """Execute a market order against the opposite side of the book."""
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    passive_side = "sell" if side == "buy" else "buy"
    levels_by_side = _levels_to_dict(book)
    ordered_prices = sorted(levels_by_side[passive_side].keys(), reverse=(passive_side == "buy"))
    prints: list[TradePrint] = []
    remaining_quantity = quantity

    for price in ordered_prices:
        if remaining_quantity <= 0:
            break
        next_orders = []
        for order in levels_by_side[passive_side][price]:
            if remaining_quantity <= 0:
                next_orders.append(order)
                continue
            consumed = min(order.visible_quantity, remaining_quantity)
            if consumed > 0:
                prints.append(
                    TradePrint(
                        trade_id=f"{order_id}:{order.order_id}:{len(prints) + 1}",
                        instrument_id=book.instrument_id,
                        timestamp=timestamp,
                        price=order.price,
                        quantity=consumed,
                        aggressor_side=side,
                        buy_order_id=order_id if side == "buy" else order.order_id,
                        sell_order_id=order_id if side == "sell" else order.order_id,
                    )
                )
                remaining_quantity -= consumed
            residual = _reduce_order(order, consumed)
            if residual is not None:
                next_orders.append(residual)
        if next_orders:
            levels_by_side[passive_side][price] = next_orders
        else:
            del levels_by_side[passive_side][price]

    return _build_snapshot(book.instrument_id, timestamp, levels_by_side), prints, remaining_quantity


def match_crossing_limit_order(
    book: BookSnapshot,
    order: RestingOrder,
) -> tuple[BookSnapshot, list[TradePrint], RestingOrder | None]:
    """Match a crossing limit order and rest any unfilled residual."""
    _require_same_instrument(book, order.instrument_id)
    remaining_order = order
    working_book = book
    prints: list[TradePrint] = []

    while remaining_order is not None and remaining_order.visible_quantity > 0 and _is_marketable(working_book, remaining_order):
        passive_level = best_ask(working_book) if remaining_order.side == "buy" else best_bid(working_book)
        assert passive_level is not None
        passive_order = passive_level.orders[0]
        traded_quantity = min(remaining_order.visible_quantity, passive_order.visible_quantity)
        prints.append(
            TradePrint(
                trade_id=f"{remaining_order.order_id}:{passive_order.order_id}:{len(prints) + 1}",
                instrument_id=order.instrument_id,
                timestamp=remaining_order.effective_at,
                price=passive_order.price,
                quantity=traded_quantity,
                aggressor_side=remaining_order.side,
                buy_order_id=remaining_order.order_id if remaining_order.side == "buy" else passive_order.order_id,
                sell_order_id=remaining_order.order_id if remaining_order.side == "sell" else passive_order.order_id,
            )
        )
        working_book = _consume_passive_order(working_book, passive_order.order_id, traded_quantity, remaining_order.effective_at)
        remaining_order = _reduce_order(remaining_order, traded_quantity)

    if remaining_order is None:
        return working_book, prints, None
    if remaining_order.visible_quantity <= 0:
        return working_book, prints, None

    rested_book, _, rested_order = submit_limit_order(working_book, remaining_order)
    return rested_book, prints, rested_order


def cancel_order(
    book: BookSnapshot,
    order_id: str,
    cancel_quantity: float | None = None,
    timestamp: pd.Timestamp | None = None,
) -> BookSnapshot:
    """Cancel part or all of one resting order."""
    levels_by_side = _levels_to_dict(book)
    for side, levels in levels_by_side.items():
        for price, orders in list(levels.items()):
            updated_orders = []
            removed = False
            for order in orders:
                if order.order_id != order_id:
                    updated_orders.append(order)
                    continue
                removed = True
                if cancel_quantity is None or cancel_quantity >= order.total_quantity:
                    continue
                reduced = _reduce_order(order, cancel_quantity)
                if reduced is not None:
                    updated_orders.append(reduced)
            if removed:
                if updated_orders:
                    levels[price] = updated_orders
                else:
                    del levels[price]
                snapshot_time = timestamp or book.timestamp
                return _build_snapshot(book.instrument_id, snapshot_time, levels_by_side)
    return book


def modify_order_quantity(
    book: BookSnapshot,
    order_id: str,
    new_visible_quantity: float,
    new_reserve_quantity: float | None = None,
    timestamp: pd.Timestamp | None = None,
) -> BookSnapshot:
    """Modify order quantity while preserving current queue spot."""
    if new_visible_quantity < 0:
        raise ValueError("new_visible_quantity must be non-negative.")
    if new_reserve_quantity is not None and new_reserve_quantity < 0:
        raise ValueError("new_reserve_quantity must be non-negative.")

    levels_by_side = _levels_to_dict(book)
    for side, levels in levels_by_side.items():
        for price, orders in levels.items():
            for idx, order in enumerate(orders):
                if order.order_id != order_id:
                    continue
                reserve_quantity = order.reserve_quantity if new_reserve_quantity is None else new_reserve_quantity
                orders[idx] = replace(
                    order,
                    visible_quantity=new_visible_quantity,
                    reserve_quantity=reserve_quantity,
                )
                return _build_snapshot(book.instrument_id, timestamp or book.timestamp, levels_by_side)
    return book


def modify_order_price(
    book: BookSnapshot,
    order_id: str,
    new_price: float,
    timestamp: pd.Timestamp,
) -> tuple[BookSnapshot, list[TradePrint], RestingOrder | None]:
    """Modify order price, losing queue priority and possibly crossing."""
    if new_price <= 0:
        raise ValueError("new_price must be positive.")

    levels_by_side = _levels_to_dict(book)
    for side, levels in levels_by_side.items():
        for price, orders in list(levels.items()):
            for idx, order in enumerate(orders):
                if order.order_id != order_id:
                    continue
                del orders[idx]
                if not orders:
                    del levels[price]
                else:
                    levels[price] = orders
                modified = replace(order, price=new_price, effective_at=timestamp)
                stripped_book = _build_snapshot(book.instrument_id, timestamp, levels_by_side)
                return submit_limit_order(stripped_book, modified)
    return book, [], None


def refresh_iceberg_peak(order: RestingOrder, peak_size: float) -> RestingOrder:
    """Refresh visible quantity from reserve for an iceberg-style order."""
    if peak_size <= 0:
        raise ValueError("peak_size must be positive.")
    if order.reserve_quantity <= 0:
        return order

    refreshed_visible = min(float(peak_size), float(order.reserve_quantity))
    refreshed_reserve = max(float(order.reserve_quantity) - refreshed_visible, 0.0)
    return replace(
        order,
        visible_quantity=refreshed_visible,
        reserve_quantity=refreshed_reserve,
    )


def is_hidden_order(order: RestingOrder) -> bool:
    """Return whether an order contains reserve liquidity."""
    return bool(order.reserve_quantity > 0)


def _consume_passive_order(
    book: BookSnapshot,
    passive_order_id: str,
    consumed_quantity: float,
    timestamp: pd.Timestamp,
) -> BookSnapshot:
    """Reduce or remove one passive order after a trade."""
    levels_by_side = _levels_to_dict(book)
    for side, levels in levels_by_side.items():
        for price, orders in list(levels.items()):
            updated_orders = []
            changed = False
            for order in orders:
                if order.order_id != passive_order_id:
                    updated_orders.append(order)
                    continue
                changed = True
                residual = _reduce_order(order, consumed_quantity)
                if residual is not None:
                    updated_orders.append(residual)
            if changed:
                if updated_orders:
                    levels[price] = updated_orders
                else:
                    del levels[price]
                return _build_snapshot(book.instrument_id, timestamp, levels_by_side)
    return book


def _reduce_order(order: RestingOrder, consumed_quantity: float) -> RestingOrder | None:
    """Reduce a resting order by a traded or canceled quantity."""
    if consumed_quantity < 0:
        raise ValueError("consumed_quantity must be non-negative.")
    if consumed_quantity >= order.total_quantity:
        return None

    visible_remainder = max(order.visible_quantity - consumed_quantity, 0.0)
    total_remainder = order.total_quantity - consumed_quantity
    reserve_remainder = max(total_remainder - visible_remainder, 0.0)
    return replace(
        order,
        visible_quantity=visible_remainder,
        reserve_quantity=reserve_remainder,
    )


def _is_marketable(book: BookSnapshot, order: RestingOrder) -> bool:
    """Return whether a limit order crosses the opposite best level."""
    if order.side == "buy":
        ask = best_ask(book)
        return ask is not None and order.price >= ask.price
    bid = best_bid(book)
    return bid is not None and order.price <= bid.price


def _require_same_instrument(book: BookSnapshot, instrument_id: str) -> None:
    """Validate instrument consistency."""
    if book.instrument_id != instrument_id:
        raise ValueError("Book instrument_id must match order instrument_id.")


def _levels_to_dict(book: BookSnapshot) -> dict[str, dict[float, list[RestingOrder]]]:
    """Convert immutable snapshot levels into mutable side maps."""
    levels_by_side: dict[str, dict[float, list[RestingOrder]]] = {
        "buy": defaultdict(list),
        "sell": defaultdict(list),
    }
    for level in book.bids:
        levels_by_side["buy"][level.price] = list(level.orders)
    for level in book.asks:
        levels_by_side["sell"][level.price] = list(level.orders)
    return levels_by_side


def _build_snapshot(
    instrument_id: str,
    timestamp: pd.Timestamp,
    levels_by_side: dict[str, dict[float, list[RestingOrder]]],
) -> BookSnapshot:
    """Build an immutable book snapshot from mutable side maps."""
    bids = tuple(
        BookLevel(side="buy", price=price, orders=tuple(levels_by_side["buy"][price]))
        for price in sorted(levels_by_side["buy"].keys(), reverse=True)
    )
    asks = tuple(
        BookLevel(side="sell", price=price, orders=tuple(levels_by_side["sell"][price]))
        for price in sorted(levels_by_side["sell"].keys())
    )
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=bids, asks=asks)
