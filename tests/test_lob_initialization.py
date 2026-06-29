from __future__ import annotations

import pandas as pd
import pytest

from src.lob_generators import build_initial_book_snapshot, seed_imbalanced_depth, seed_symmetric_depth
from src.lob_simulator_config import BookInitializationConfig


def ts(label: str) -> pd.Timestamp:
    return pd.Timestamp(label, tz="America/New_York")


def test_seed_symmetric_depth_builds_sorted_levels() -> None:
    config = BookInitializationConfig(mid_price=100.0, tick_size=0.5, levels_per_side=3, visible_quantity=10.0)
    bids = seed_symmetric_depth("XYZ", ts("2026-01-02 10:00:00"), config, side="buy")
    asks = seed_symmetric_depth("XYZ", ts("2026-01-02 10:00:00"), config, side="sell")

    assert [level.price for level in bids] == pytest.approx([99.5, 99.0, 98.5])
    assert [level.price for level in asks] == pytest.approx([100.5, 101.0, 101.5])


def test_build_initial_book_snapshot_returns_both_sides() -> None:
    snapshot = build_initial_book_snapshot("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig())

    assert snapshot.best_bid == pytest.approx(99.5)
    assert snapshot.best_ask == pytest.approx(100.5)


def test_seed_imbalanced_depth_scales_sides() -> None:
    snapshot = seed_imbalanced_depth("XYZ", ts("2026-01-02 10:00:00"), BookInitializationConfig(), buy_multiplier=2.0, sell_multiplier=0.5)

    assert snapshot.bids[0].orders[0].visible_quantity == pytest.approx(20.0)
    assert snapshot.asks[0].orders[0].visible_quantity == pytest.approx(5.0)
