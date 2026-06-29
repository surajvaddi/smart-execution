from __future__ import annotations

import pandas as pd
import pytest

from src.lob_types import RestingOrder
from src.matching_engine import create_empty_book, submit_limit_order


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


def test_crossing_limit_order_matches_and_rests_residual() -> None:
    book = create_empty_book("XYZ", ts())
    book, _, _ = submit_limit_order(book, order("a1", "sell", 101.0, 5.0))

    book, prints, residual = submit_limit_order(book, order("b1", "buy", 102.0, 8.0))

    assert len(prints) == 1
    assert prints[0].price == pytest.approx(101.0)
    assert prints[0].quantity == pytest.approx(5.0)
    assert residual is not None
    assert residual.visible_quantity == pytest.approx(3.0)
    assert book.bids[0].orders[0].order_id == "b1"
    assert book.bids[0].orders[0].visible_quantity == pytest.approx(3.0)
    assert book.asks == ()
