from __future__ import annotations

import pandas as pd
import pytest

from src.futures_roll import (
    back_adjust_series,
    build_continuous_contract,
    compute_roll_dates,
    ratio_adjust_series,
)


def sample_contracts() -> dict[str, pd.DataFrame]:
    index_front = pd.to_datetime(
        ["2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
    ).tz_localize("America/Chicago")
    index_next = pd.to_datetime(
        ["2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07"],
    ).tz_localize("America/Chicago")
    front = pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0, 103.0],
            "volume": [200.0, 180.0, 120.0, 90.0],
        },
        index=index_front,
    )
    nxt = pd.DataFrame(
        {
            "close": [105.0, 106.0, 107.0, 108.0],
            "volume": [100.0, 190.0, 220.0, 250.0],
        },
        index=index_next,
    )
    return {"ESH26": front, "ESM26": nxt}


def test_compute_roll_dates_uses_volume_crossover() -> None:
    roll_dates = compute_roll_dates(sample_contracts())

    assert roll_dates["ESH26"] == pd.Timestamp("2026-01-05", tz="America/Chicago")


def test_back_adjust_series_applies_price_gap_to_front_history() -> None:
    contracts = sample_contracts()
    roll_dates = compute_roll_dates(contracts)
    continuous = back_adjust_series(contracts, roll_dates)

    assert continuous.loc[pd.Timestamp("2026-01-02", tz="America/Chicago"), "close"] == pytest.approx(103.0)
    assert continuous.loc[pd.Timestamp("2026-01-05", tz="America/Chicago"), "source_contract"] == "ESM26"


def test_ratio_adjust_series_scales_front_history_by_roll_ratio() -> None:
    contracts = sample_contracts()
    roll_dates = compute_roll_dates(contracts)
    continuous = ratio_adjust_series(contracts, roll_dates)

    expected_ratio = 106.0 / 103.0
    assert continuous.loc[pd.Timestamp("2026-01-02", tz="America/Chicago"), "close"] == pytest.approx(
        100.0 * expected_ratio
    )


def test_build_continuous_contract_supports_back_and_ratio_adjustments() -> None:
    contracts = sample_contracts()

    back = build_continuous_contract(contracts, adjustment="back")
    ratio = build_continuous_contract(contracts, adjustment="ratio")

    assert len(back) == 6
    assert len(ratio) == 6
    assert back.index.min() == pd.Timestamp("2026-01-02", tz="America/Chicago")
    assert ratio.index.max() == pd.Timestamp("2026-01-07", tz="America/Chicago")
