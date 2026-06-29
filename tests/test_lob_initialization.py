from __future__ import annotations

import pandas as pd
import pytest

from src.lob_generators import build_initial_book_snapshot, seed_imbalanced_depth, seed_symmetric_depth
from src.lob_simulator_config import BookInitializationConfig


def ts() -> pd.Timestamp:
    return pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")


def test_seed_symmetric_depth_builds_balanced_book() -> None:
    book = seed_symmetric_depth("XYZ", ts(), BookInitializationConfig())

    assert [level.price for level in book.bids] == pytest.approx([99.5, 99.0, 98.5])
    assert [level.price for level in book.asks] == pytest.approx([100.5, 101.0, 101.5])
    assert book.bids[0].orders[0].visible_quantity == pytest.approx(book.asks[0].orders[0].visible_quantity)


def test_seed_imbalanced_depth_uses_imbalance_ratio() -> None:
    book = seed_imbalanced_depth("XYZ", ts(), BookInitializationConfig(imbalance_ratio=2.0))

    assert book.bids[0].orders[0].visible_quantity == pytest.approx(20.0)
    assert book.asks[0].orders[0].visible_quantity == pytest.approx(5.0)


def test_build_initial_book_snapshot_supports_both_modes() -> None:
    symmetric = build_initial_book_snapshot("XYZ", ts(), BookInitializationConfig(), mode="symmetric")
    imbalanced = build_initial_book_snapshot("XYZ", ts(), BookInitializationConfig(imbalance_ratio=1.5), mode="imbalanced")

    assert symmetric.instrument_id == "XYZ"
    assert imbalanced.instrument_id == "XYZ"
