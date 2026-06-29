from __future__ import annotations

import pandas as pd
import pytest

from src.lob_types import RestingOrder
from src.matching_engine import is_hidden_order, refresh_iceberg_peak


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_refresh_iceberg_peak_moves_reserve_into_visible() -> None:
    order = RestingOrder(
        order_id="ice1",
        parent_order_id=None,
        child_order_id=None,
        side="sell",
        price=101.0,
        visible_quantity=0.0,
        reserve_quantity=12.0,
        submitted_at=ts("2026-01-02 10:00:00"),
        effective_at=ts("2026-01-02 10:00:00"),
        owner_type="external",
        instrument_id="XYZ",
    )

    refreshed = refresh_iceberg_peak(order, peak_size=5.0)

    assert refreshed.visible_quantity == pytest.approx(5.0)
    assert refreshed.reserve_quantity == pytest.approx(7.0)
    assert is_hidden_order(refreshed) is True
