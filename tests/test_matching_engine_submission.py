from __future__ import annotations

import pandas as pd

from src.lob_types import BookSnapshot, RestingOrder
from src.matching_engine import create_empty_book, submit_limit_order


def ts(value: str = "2026-01-02 10:00:00") -> pd.Timestamp:
    return pd.Timestamp(value, tz="America/New_York")


def order(order_id: str, side: str, price: float, effective_at: str) -> RestingOrder:
    return RestingOrder(
        order_id=order_id,
        parent_order_id=None,
        child_order_id=None,
        side=side,
        price=price,
        visible_quantity=10.0,
        reserve_quantity=0.0,
        submitted_at=ts(effective_at),
        effective_at=ts(effective_at),
        owner_type="external",
        instrument_id="XYZ",
    )


def test_submit_limit_order_rests_non_crossing_order() -> None:
    book = create_empty_book("XYZ", ts())

    book, prints, rested = submit_limit_order(book, order("b1", "buy", 100.0, "2026-01-02 10:00:00"))

    assert prints == []
    assert rested is not None
    assert book.bids[0].orders[0].order_id == "b1"


def test_submit_limit_order_keeps_fifo_within_price_level() -> None:
    book = create_empty_book("XYZ", ts())
    book, _, _ = submit_limit_order(book, order("b1", "buy", 100.0, "2026-01-02 10:00:00"))
    book, _, _ = submit_limit_order(book, order("b2", "buy", 100.0, "2026-01-02 10:00:01"))

    assert [resting.order_id for resting in book.bids[0].orders] == ["b1", "b2"]
