from __future__ import annotations

import pandas as pd
import pytest

from src.futures_tca import normalize_fill_to_dollars, normalize_fill_to_ticks, normalize_parent_tca_for_futures
from src.instruments import load_builtin_instrument_specs


def future_spec():
    return load_builtin_instrument_specs()["FUT_ESU26"]


def test_normalize_fill_to_ticks_converts_price_difference() -> None:
    ticks = normalize_fill_to_ticks(fill_price=5001.0, reference_price=5000.0, spec=future_spec())

    assert ticks == pytest.approx(4.0)


def test_normalize_fill_to_dollars_scales_by_contract_count() -> None:
    dollars = normalize_fill_to_dollars(
        fill_price=5001.0,
        reference_price=5000.0,
        contracts=2.0,
        spec=future_spec(),
    )

    assert dollars == pytest.approx(100.0)


def test_normalize_parent_tca_for_futures_adds_ticks_and_dollars() -> None:
    results = pd.DataFrame(
        [
            {
                "avg_fill_price": 5001.0,
                "arrival_price": 5000.0,
                "quantity": 2.0,
                "implementation_shortfall_bps": 2.0,
            }
        ]
    )

    normalized = normalize_parent_tca_for_futures(results, future_spec())

    assert normalized.loc[0, "implementation_shortfall_ticks"] == pytest.approx(4.0)
    assert normalized.loc[0, "implementation_shortfall_dollars"] == pytest.approx(100.0)
