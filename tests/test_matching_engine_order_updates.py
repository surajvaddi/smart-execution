from __future__ import annotations

import pandas as pd
import pytest

from src.lob_types import RestingOrder
from src.matching_engine import cancel_order, create_empty_book, modify_order_price, modify_order_quantity, submit_limit_order


def ts(value: str = "2026-01-02 10:00:00") -> pd.Timestamp:
    return pd.Timestamp(value, tz="America/New_York")


def order(order_id: str, side: str, price: float, qty: float, effective_at: str = "2026-01-02 10:00:00") -> RestingOrder:
    return RestingOrder(
        order_id=order_id,
        parent_order_id=None,
        child_order_id=None,
        side=side,
        price=price,
        visible_quantity=qty,
        reserve_quantity=0.0,
        submitted_at=ts(effective_at),
        effective_at=ts(effective_at),
        owner_type="external",
        instrument_id="XYZ",
    )


def test_cancel_order_removes_full_order_or_reduces_partial_quantity() -> None:
    book = create_empty_book("XYZ", ts())
    book, _, _ = submit_limit_order(book, order("b1", "buy", 100.0, 10.0))
    book = cancel_order(book, "b1", cancel_quantity=4.0, timestamp=ts("2026-01-02 10:00:01"))

    assert book.bids[0].orders[0].visible_quantity == pytest.approx(6.0)

    book = cancel_order(book, "b1", timestamp=ts("2026-01-02 10:00:02"))
    assert book.bids == ()


def test_modify_order_quantity_preserves_current_queue_spot() -> None:
    book = create_empty_book("XYZ", ts())
    book, _, _ = submit_limit_order(book, order("b1", "buy", 100.0, 10.0, "2026-01-02 10:00:00"))
    book, _, _ = submit_limit_order(book, order("b2", "buy", 100.0, 8.0, "2026-01-02 10:00:01"))

    book = modify_order_quantity(book, "b1", new_visible_quantity=7.0, timestamp=ts("2026-01-02 10:00:02"))

    assert [resting.order_id for resting in book.bids[0].orders] == ["b1", "b2"]
    assert book.bids[0].orders[0].visible_quantity == pytest.approx(7.0)


def test_modify_order_price_loses_queue_priority_and_can_cross() -> None:
    book = create_empty_book("XYZ", ts())
    book, _, _ = submit_limit_order(book, order("a1", "sell", 101.0, 5.0))
    book, _, _ = submit_limit_order(book, order("b1", "buy", 100.0, 6.0))

    book, prints, residual = modify_order_price(book, "b1", 101.5, ts("2026-01-02 10:00:02"))

    assert len(prints) == 1
    assert prints[0].price == pytest.approx(101.0)
    assert prints[0].quantity == pytest.approx(5.0)
    assert residual is not None
    assert residual.visible_quantity == pytest.approx(1.0)
    assert book.bids[0].orders[0].order_id == "b1"
