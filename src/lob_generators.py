"""Synthetic event and initial-state generators for the LOB simulator."""

from __future__ import annotations

import random
from typing import Iterable

import pandas as pd

from src.lob_events import CancelEvent, LimitAddEvent, MarketOrderEvent
from src.lob_simulator_config import ArrivalProcessConfig, BookInitializationConfig, CancellationProcessConfig
from src.lob_types import BookLevel, BookSnapshot, RestingOrder


def build_initial_book_snapshot(
    instrument_id: str,
    timestamp: pd.Timestamp,
    config: BookInitializationConfig,
    mode: str = "symmetric",
) -> BookSnapshot:
    """Return an initial book using the requested shape mode."""
    if mode == "symmetric":
        return seed_symmetric_depth(instrument_id, timestamp, config)
    if mode == "imbalanced":
        return seed_imbalanced_depth(instrument_id, timestamp, config)
    raise ValueError("mode must be either 'symmetric' or 'imbalanced'.")


def seed_symmetric_depth(
    instrument_id: str,
    timestamp: pd.Timestamp,
    config: BookInitializationConfig,
) -> BookSnapshot:
    """Create a symmetric visible-depth book around the configured midpoint."""
    bids = []
    asks = []
    for level_index in range(config.levels_per_side):
        quantity = config.base_quantity + level_index * config.quantity_step
        bid_price = config.mid_price - config.tick_size * (level_index + 1)
        ask_price = config.mid_price + config.tick_size * (level_index + 1)
        bids.append(BookLevel(side="buy", price=bid_price, orders=(_seed_order("buy", bid_price, quantity, instrument_id, timestamp, f"bid_{level_index + 1}"),)))
        asks.append(BookLevel(side="sell", price=ask_price, orders=(_seed_order("sell", ask_price, quantity, instrument_id, timestamp, f"ask_{level_index + 1}"),)))
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=tuple(bids), asks=tuple(asks))


def seed_imbalanced_depth(
    instrument_id: str,
    timestamp: pd.Timestamp,
    config: BookInitializationConfig,
) -> BookSnapshot:
    """Create an imbalanced book using the configured imbalance ratio."""
    bids = []
    asks = []
    for level_index in range(config.levels_per_side):
        base_quantity = config.base_quantity + level_index * config.quantity_step
        bid_quantity = base_quantity * config.imbalance_ratio
        ask_quantity = base_quantity / config.imbalance_ratio
        bid_price = config.mid_price - config.tick_size * (level_index + 1)
        ask_price = config.mid_price + config.tick_size * (level_index + 1)
        bids.append(BookLevel(side="buy", price=bid_price, orders=(_seed_order("buy", bid_price, bid_quantity, instrument_id, timestamp, f"imb_bid_{level_index + 1}"),)))
        asks.append(BookLevel(side="sell", price=ask_price, orders=(_seed_order("sell", ask_price, ask_quantity, instrument_id, timestamp, f"imb_ask_{level_index + 1}"),)))
    return BookSnapshot(instrument_id=instrument_id, timestamp=timestamp, bids=tuple(bids), asks=tuple(asks))


def generate_limit_add_events(
    book: BookSnapshot,
    event_time: pd.Timestamp,
    rng: random.Random,
    config: ArrivalProcessConfig,
    random_seed: int | None = None,
    source: str = "simulator",
) -> tuple[LimitAddEvent, ...]:
    """Generate synthetic resting limit-order arrivals around the current touch."""
    best_bid_price = book.bids[0].price if book.bids else 0.0
    best_ask_price = book.asks[0].price if book.asks else 0.0
    if best_bid_price <= 0 or best_ask_price <= 0:
        raise ValueError("Book must contain both bid and ask depth to generate arrivals.")
    tick_size = best_ask_price - best_bid_price if best_ask_price > best_bid_price else 0.5
    events = []
    for event_number in range(config.events_per_step):
        side = rng.choice(["buy", "sell"])
        offset = sample_price_offset(rng, config)
        quantity = sample_limit_size(rng, config)
        if side == "buy":
            price = best_bid_price - offset * tick_size
        else:
            price = best_ask_price + offset * tick_size
        order_id = f"arr_{source}_{event_time.value}_{event_number + 1}"
        order = RestingOrder(
            order_id=order_id,
            parent_order_id=None,
            child_order_id=None,
            side=side,
            price=price,
            visible_quantity=quantity,
            reserve_quantity=0.0,
            submitted_at=event_time,
            effective_at=event_time,
            owner_type="simulator",
            instrument_id=book.instrument_id,
        )
        events.append(
            LimitAddEvent(
                event_id=f"limit_add_{event_number + 1}_{event_time.value}",
                event_time=event_time,
                effective_time=event_time,
                instrument_id=book.instrument_id,
                source=source,
                random_seed=random_seed,
                order=order,
            )
        )
    return tuple(events)


def generate_cancel_events(
    book: BookSnapshot,
    event_time: pd.Timestamp,
    rng: random.Random,
    config: CancellationProcessConfig,
    random_seed: int | None = None,
    source: str = "simulator",
) -> tuple[CancelEvent, ...]:
    """Generate synthetic cancellations against currently resting orders."""
    cancel_candidates = list(sample_cancel_candidates(book))
    if not cancel_candidates:
        return ()

    events = []
    for event_number in range(min(config.events_per_step, len(cancel_candidates))):
        if rng.random() > config.cancel_probability:
            continue
        order = cancel_candidates[event_number % len(cancel_candidates)]
        cancel_quantity = max(order.visible_quantity * config.partial_cancel_ratio, 1e-9)
        events.append(
            CancelEvent(
                event_id=f"cancel_{event_number + 1}_{event_time.value}",
                event_time=event_time,
                effective_time=event_time,
                instrument_id=book.instrument_id,
                source=source,
                random_seed=random_seed,
                order_id=order.order_id,
                cancel_quantity=min(cancel_quantity, order.total_quantity),
            )
        )
    return tuple(events)


def generate_market_order_events(
    book: BookSnapshot,
    event_time: pd.Timestamp,
    rng: random.Random,
    num_events: int,
    min_quantity: float = 1.0,
    max_quantity: float = 10.0,
    random_seed: int | None = None,
    source: str = "simulator",
) -> tuple[MarketOrderEvent, ...]:
    """Generate synthetic aggressive market-order flow."""
    if num_events < 0:
        raise ValueError("num_events must be non-negative.")
    if min_quantity <= 0 or max_quantity <= 0:
        raise ValueError("market-order quantities must be positive.")
    if min_quantity > max_quantity:
        raise ValueError("min_quantity must be less than or equal to max_quantity.")

    events = []
    for event_number in range(num_events):
        side = sample_market_order_side(rng)
        quantity = sample_market_order_size(rng, min_quantity, max_quantity)
        events.append(
            MarketOrderEvent(
                event_id=f"market_{event_number + 1}_{event_time.value}",
                event_time=event_time,
                effective_time=event_time,
                instrument_id=book.instrument_id,
                source=source,
                random_seed=random_seed,
                side=side,
                quantity=quantity,
            )
        )
    return tuple(events)


def sample_price_offset(rng: random.Random, config: ArrivalProcessConfig) -> int:
    """Sample a level offset from the configured discrete distribution."""
    return rng.choices(config.price_offsets, weights=config.price_offset_probabilities, k=1)[0]


def sample_limit_size(rng: random.Random, config: ArrivalProcessConfig) -> float:
    """Sample one synthetic limit-order quantity."""
    return float(rng.uniform(config.min_quantity, config.max_quantity))


def sample_cancel_candidates(book: BookSnapshot) -> Iterable[RestingOrder]:
    """Yield current resting orders in deterministic side/price/queue order."""
    for level in book.bids:
        for order in level.orders:
            yield order
    for level in book.asks:
        for order in level.orders:
            yield order


def sample_market_order_side(rng: random.Random) -> str:
    """Sample one market-order side."""
    return rng.choice(["buy", "sell"])


def sample_market_order_size(rng: random.Random, min_quantity: float, max_quantity: float) -> float:
    """Sample one market-order quantity."""
    return float(rng.uniform(min_quantity, max_quantity))


def _seed_order(
    side: str,
    price: float,
    quantity: float,
    instrument_id: str,
    timestamp: pd.Timestamp,
    order_id: str,
) -> RestingOrder:
    """Build a one-order level for initial book seeding."""
    return RestingOrder(
        order_id=order_id,
        parent_order_id=None,
        child_order_id=None,
        side=side,
        price=price,
        visible_quantity=quantity,
        reserve_quantity=0.0,
        submitted_at=timestamp,
        effective_at=timestamp,
        owner_type="simulator",
        instrument_id=instrument_id,
    )
