"""Synthetic event generators for the LOB simulator."""

from __future__ import annotations

import random

import pandas as pd

from src.lob_events import CancelEvent, LimitAddEvent, MarketOrderEvent
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig, CancellationProcessConfig
from src.lob_types import BookLevel, BookSnapshot, RestingOrder


def build_initial_book_snapshot(
    instrument_id: str,
    timestamp: pd.Timestamp,
    config: BookInitializationConfig,
) -> BookSnapshot:
    """Build a symmetric synthetic initial book."""
    bids = seed_symmetric_depth(instrument_id, timestamp, config, side="buy")
    asks = seed_symmetric_depth(instrument_id, timestamp, config, side="sell")
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=bids, asks=asks)


def seed_symmetric_depth(
    instrument_id: str,
    timestamp: pd.Timestamp,
    config: BookInitializationConfig,
    side: str,
) -> tuple[BookLevel, ...]:
    """Seed one side of the book with evenly spaced levels."""
    levels = []
    half_spread = config.tick_size * config.spread_ticks / 2.0
    if side == "buy":
        start_price = config.mid_price - half_spread
        prices = [start_price - config.tick_size * idx for idx in range(config.levels_per_side)]
    elif side == "sell":
        start_price = config.mid_price + half_spread
        prices = [start_price + config.tick_size * idx for idx in range(config.levels_per_side)]
    else:
        raise ValueError("side must be 'buy' or 'sell'.")

    for level_index, price in enumerate(prices):
        order = RestingOrder(
            order_id=f"{instrument_id}_{side}_{level_index}",
            parent_order_id=None,
            child_order_id=None,
            side=side,
            price=float(price),
            visible_quantity=float(config.visible_quantity),
            reserve_quantity=0.0,
            submitted_at=timestamp,
            effective_at=timestamp,
            owner_type="simulator",
            instrument_id=instrument_id,
        )
        levels.append(BookLevel(side=side, price=float(price), orders=(order,)))
    return tuple(levels)


def seed_imbalanced_depth(
    instrument_id: str,
    timestamp: pd.Timestamp,
    config: BookInitializationConfig,
    buy_multiplier: float = 1.5,
    sell_multiplier: float = 0.75,
) -> BookSnapshot:
    """Build an imbalanced initial book for regime testing."""
    if buy_multiplier <= 0 or sell_multiplier <= 0:
        raise ValueError("buy_multiplier and sell_multiplier must be positive.")

    bid_levels = []
    for level in seed_symmetric_depth(instrument_id, timestamp, config, side="buy"):
        scaled_order = level.orders[0]
        bid_levels.append(
            BookLevel(
                side=level.side,
                price=level.price,
                orders=(
                    RestingOrder(
                        order_id=scaled_order.order_id,
                        parent_order_id=scaled_order.parent_order_id,
                        child_order_id=scaled_order.child_order_id,
                        side=scaled_order.side,
                        price=scaled_order.price,
                        visible_quantity=scaled_order.visible_quantity * buy_multiplier,
                        reserve_quantity=scaled_order.reserve_quantity,
                        submitted_at=scaled_order.submitted_at,
                        effective_at=scaled_order.effective_at,
                        owner_type=scaled_order.owner_type,
                        instrument_id=scaled_order.instrument_id,
                    ),
                ),
            )
        )
    ask_levels = []
    for level in seed_symmetric_depth(instrument_id, timestamp, config, side="sell"):
        scaled_order = level.orders[0]
        ask_levels.append(
            BookLevel(
                side=level.side,
                price=level.price,
                orders=(
                    RestingOrder(
                        order_id=scaled_order.order_id,
                        parent_order_id=scaled_order.parent_order_id,
                        child_order_id=scaled_order.child_order_id,
                        side=scaled_order.side,
                        price=scaled_order.price,
                        visible_quantity=scaled_order.visible_quantity * sell_multiplier,
                        reserve_quantity=scaled_order.reserve_quantity,
                        submitted_at=scaled_order.submitted_at,
                        effective_at=scaled_order.effective_at,
                        owner_type=scaled_order.owner_type,
                        instrument_id=scaled_order.instrument_id,
                    ),
                ),
            )
        )
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=tuple(bid_levels), asks=tuple(ask_levels))


def generate_limit_add_events(
    snapshot: BookSnapshot,
    event_time: pd.Timestamp,
    config: ArrivalProcessConfig,
    rng: random.Random,
    event_prefix: str = "limit_add",
) -> tuple[LimitAddEvent, ...]:
    """Generate exogenous resting-order arrivals around the touch."""
    events = []
    for idx in range(config.events_per_step):
        side = "buy" if rng.random() < config.buy_probability else "sell"
        offset = rng.choices(list(config.price_offset_levels), weights=list(config.price_offset_probabilities), k=1)[0]
        quantity = float(rng.uniform(config.min_quantity, config.max_quantity))
        price = _arrival_price(snapshot, side, offset)
        order = RestingOrder(
            order_id=f"{event_prefix}_order_{idx}",
            parent_order_id=None,
            child_order_id=None,
            side=side,
            price=price,
            visible_quantity=quantity,
            reserve_quantity=0.0,
            submitted_at=event_time,
            effective_at=event_time,
            owner_type="simulator",
            instrument_id=snapshot.instrument_id,
        )
        events.append(
            LimitAddEvent(
                event_id=f"{event_prefix}_{idx}",
                event_time=event_time,
                effective_time=event_time,
                instrument_id=snapshot.instrument_id,
                source="external_flow",
                random_seed=None,
                order=order,
            )
        )
    return tuple(events)


def generate_cancel_events(
    snapshot: BookSnapshot,
    event_time: pd.Timestamp,
    config: CancellationProcessConfig,
    rng: random.Random,
    event_prefix: str = "cancel",
) -> tuple[CancelEvent, ...]:
    """Generate exogenous cancellations targeting currently live orders."""
    live_orders = [order for level in snapshot.bids + snapshot.asks for order in level.orders]
    if not live_orders:
        return ()

    events = []
    for idx in range(min(config.events_per_step, len(live_orders))):
        order = live_orders[idx % len(live_orders)]
        cancel_quantity = None
        if rng.random() < config.cancel_partial_probability:
            cancel_quantity = max(order.visible_quantity * config.partial_cancel_fraction, 1e-9)
        events.append(
            CancelEvent(
                event_id=f"{event_prefix}_{idx}",
                event_time=event_time,
                effective_time=event_time,
                instrument_id=snapshot.instrument_id,
                source="external_flow",
                random_seed=None,
                order_id=order.order_id,
                cancel_quantity=cancel_quantity,
            )
        )
    return tuple(events)


def generate_market_order_events(
    snapshot: BookSnapshot,
    event_time: pd.Timestamp,
    num_events: int,
    rng: random.Random,
    buy_probability: float = 0.5,
    min_quantity: float = 1.0,
    max_quantity: float = 10.0,
    event_prefix: str = "market",
) -> tuple[MarketOrderEvent, ...]:
    """Generate exogenous market-order flow."""
    if num_events < 0:
        raise ValueError("num_events must be non-negative.")
    if min_quantity <= 0 or max_quantity <= 0:
        raise ValueError("min_quantity and max_quantity must be positive.")
    if min_quantity > max_quantity:
        raise ValueError("min_quantity must be less than or equal to max_quantity.")

    events = []
    for idx in range(num_events):
        side = "buy" if rng.random() < buy_probability else "sell"
        quantity = float(rng.uniform(min_quantity, max_quantity))
        events.append(
            MarketOrderEvent(
                event_id=f"{event_prefix}_{idx}",
                event_time=event_time,
                effective_time=event_time,
                instrument_id=snapshot.instrument_id,
                source="external_flow",
                random_seed=None,
                side=side,
                quantity=quantity,
            )
        )
    return tuple(events)


def _arrival_price(snapshot: BookSnapshot, side: str, offset: int) -> float:
    """Return arrival price at or behind the touch on one side."""
    if side == "buy":
        reference = snapshot.best_bid if snapshot.best_bid is not None else snapshot.best_ask
        if reference is None:
            raise ValueError("Cannot generate arrival price on an empty book.")
        tick = _tick_size(snapshot, side="buy")
        return float(reference - tick * offset)
    reference = snapshot.best_ask if snapshot.best_ask is not None else snapshot.best_bid
    if reference is None:
        raise ValueError("Cannot generate arrival price on an empty book.")
    tick = _tick_size(snapshot, side="sell")
    return float(reference + tick * offset)


def _tick_size(snapshot: BookSnapshot, side: str) -> float:
    """Infer tick size from adjacent levels when possible."""
    levels = snapshot.bids if side == "buy" else snapshot.asks
    if len(levels) >= 2:
        return abs(levels[0].price - levels[1].price)
    other = snapshot.asks if side == "buy" else snapshot.bids
    if len(other) >= 2:
        return abs(other[1].price - other[0].price)
    return 0.5
