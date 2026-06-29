from __future__ import annotations

import pandas as pd

from src.lob_types import BookLevel, RestingOrder
from src.matching_engine import add_price_level, best_ask, best_bid, create_empty_book, remove_price_level_if_empty


def ts() -> pd.Timestamp:
    return pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")


def order(order_id: str, side: str, price: float, qty: float = 10.0) -> RestingOrder:
    return RestingOrder(
        order_id=order_id,
        parent_order_id=None,
        child_order_id=None,
        side=side,
        price=price,
        visible_quantity=qty,
        reserve_quantity=0.0,
        submitted_at=ts(),
        effective_at=ts(),
        owner_type="external",
        instrument_id="XYZ",
    )


def test_empty_book_has_no_best_levels() -> None:
    book = create_empty_book("XYZ", ts())

    assert best_bid(book) is None
    assert best_ask(book) is None


def test_add_price_level_preserves_bid_and_ask_sorting() -> None:
    book = create_empty_book("XYZ", ts())
    book = add_price_level(book, BookLevel(side="buy", price=99.5, orders=(order("b1", "buy", 99.5),)))
    book = add_price_level(book, BookLevel(side="buy", price=100.0, orders=(order("b2", "buy", 100.0),)))
    book = add_price_level(book, BookLevel(side="sell", price=101.0, orders=(order("a1", "sell", 101.0),)))
    book = add_price_level(book, BookLevel(side="sell", price=100.5, orders=(order("a2", "sell", 100.5),)))

    assert [level.price for level in book.bids] == [100.0, 99.5]
    assert [level.price for level in book.asks] == [100.5, 101.0]


def test_remove_price_level_if_empty_removes_only_empty_levels() -> None:
    book = create_empty_book("XYZ", ts())
    book = add_price_level(book, BookLevel(side="buy", price=100.0, orders=()))
    book = add_price_level(book, BookLevel(side="sell", price=101.0, orders=(order("a1", "sell", 101.0),)))

    book = remove_price_level_if_empty(book, "buy", 100.0)
    book = remove_price_level_if_empty(book, "sell", 101.0)

    assert [level.price for level in book.bids] == []
    assert [level.price for level in book.asks] == [101.0]
