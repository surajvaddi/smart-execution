from __future__ import annotations

import pandas as pd
import pytest

from src.lob_types import RestingOrder
from src.matching_engine import create_empty_book, execute_market_order, submit_limit_order


def ts(value: str = "2026-01-02 10:00:00") -> pd.Timestamp:
    return pd.Timestamp(value, tz="America/New_York")


def order(order_id: str, side: str, price: float, qty: float) -> RestingOrder:
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


def seeded_ask_book():
    book = create_empty_book("XYZ", ts())
    book, _, _ = submit_limit_order(book, order("a1", "sell", 101.0, 5.0))
    book, _, _ = submit_limit_order(book, order("a2", "sell", 102.0, 7.0))
    return book


def test_market_order_sweeps_multiple_levels() -> None:
    book, prints, remaining = execute_market_order(seeded_ask_book(), "buy", 9.0, ts("2026-01-02 10:00:01"), order_id="m1")

    assert len(prints) == 2
    assert [trade.price for trade in prints] == [101.0, 102.0]
    assert [trade.quantity for trade in prints] == [5.0, 4.0]
    assert remaining == pytest.approx(0.0)
    assert book.asks[0].price == pytest.approx(102.0)
    assert book.asks[0].orders[0].visible_quantity == pytest.approx(3.0)


def test_market_order_can_end_partially_unfilled() -> None:
    book, prints, remaining = execute_market_order(seeded_ask_book(), "buy", 20.0, ts("2026-01-02 10:00:01"), order_id="m2")

    assert sum(trade.quantity for trade in prints) == pytest.approx(12.0)
    assert remaining == pytest.approx(8.0)
    assert book.asks == ()
