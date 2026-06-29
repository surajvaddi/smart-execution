from __future__ import annotations

import pandas as pd
import pytest

from src.lob_types import BookLevel, BookSnapshot, ExecutionReport, RestingOrder


def sample_timestamp() -> pd.Timestamp:
    return pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")


def sample_order(
    order_id: str = "o1",
    side: str = "buy",
    price: float = 100.0,
    visible_quantity: float = 10.0,
    reserve_quantity: float = 0.0,
) -> RestingOrder:
    return RestingOrder(
        order_id=order_id,
        parent_order_id=None,
        child_order_id=None,
        side=side,
        price=price,
        visible_quantity=visible_quantity,
        reserve_quantity=reserve_quantity,
        submitted_at=sample_timestamp(),
        effective_at=sample_timestamp(),
        owner_type="external",
        instrument_id="XYZ",
    )


def test_resting_order_validates_positive_total_quantity() -> None:
    with pytest.raises(ValueError, match="positive total quantity"):
        sample_order(visible_quantity=0.0, reserve_quantity=0.0)


def test_book_level_aggregates_visible_and_reserve_quantity() -> None:
    level = BookLevel(
        side="buy",
        price=100.0,
        orders=(sample_order("o1", reserve_quantity=5.0), sample_order("o2", visible_quantity=7.0)),
    )

    assert level.total_visible_quantity == pytest.approx(17.0)
    assert level.total_reserve_quantity == pytest.approx(5.0)


def test_book_snapshot_validates_bid_and_ask_ordering() -> None:
    snapshot = BookSnapshot(
        instrument_id="XYZ",
        timestamp=sample_timestamp(),
        bids=(BookLevel(side="buy", price=101.0, orders=(sample_order(price=101.0),)),),
        asks=(BookLevel(side="sell", price=102.0, orders=(sample_order(side="sell", price=102.0),)),),
    )

    assert snapshot.instrument_id == "XYZ"


def test_execution_report_validates_normalized_fill_quantities() -> None:
    report = ExecutionReport(
        execution_id="e1",
        instrument_id="XYZ",
        timestamp=sample_timestamp(),
        order_id="o1",
        parent_order_id=None,
        child_order_id=None,
        side="buy",
        submitted_quantity=10.0,
        filled_quantity=4.0,
        remaining_quantity=6.0,
        fill_price=100.1,
        fill_status="partial",
        execution_venue="synthetic_primary",
        simulation_model="replay",
        data_basis="synthetic",
    )

    assert report.fill_status == "partial"


def test_execution_report_rejects_overfilled_state() -> None:
    with pytest.raises(ValueError, match="cannot exceed submitted_quantity"):
        ExecutionReport(
            execution_id="e1",
            instrument_id="XYZ",
            timestamp=sample_timestamp(),
            order_id="o1",
            parent_order_id=None,
            child_order_id=None,
            side="buy",
            submitted_quantity=10.0,
            filled_quantity=8.0,
            remaining_quantity=3.0,
            fill_price=100.1,
            fill_status="partial",
            execution_venue="synthetic_primary",
            simulation_model="replay",
            data_basis="synthetic",
        )
