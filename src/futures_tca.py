"""Futures-aware normalization helpers for execution fills and parent TCA outputs."""

from __future__ import annotations

import pandas as pd

from src.futures_math import price_move_to_ticks, ticks_to_dollars
from src.instruments import InstrumentSpec


def normalize_fill_to_ticks(
    fill_price: float,
    reference_price: float,
    spec: InstrumentSpec,
) -> float:
    """Convert a fill-price deviation into ticks."""
    if reference_price <= 0:
        raise ValueError("reference_price must be positive.")
    return float(price_move_to_ticks(fill_price - reference_price, spec))


def normalize_fill_to_dollars(
    fill_price: float,
    reference_price: float,
    contracts: float,
    spec: InstrumentSpec,
) -> float:
    """Convert a fill-price deviation into dollars for the given contract count."""
    ticks = normalize_fill_to_ticks(fill_price, reference_price, spec)
    return float(ticks_to_dollars(ticks, contracts, spec))


def normalize_parent_tca_for_futures(
    tca_results: pd.DataFrame,
    spec: InstrumentSpec,
) -> pd.DataFrame:
    """Add ticks and dollar normalization columns to parent-order TCA results."""
    required = ["avg_fill_price", "arrival_price", "quantity"]
    missing = [column for column in required if column not in tca_results.columns]
    if missing:
        raise ValueError(f"Missing required futures TCA columns: {missing}")

    normalized = tca_results.copy()
    normalized["implementation_shortfall_ticks"] = normalized.apply(
        lambda row: normalize_fill_to_ticks(
            fill_price=float(row["avg_fill_price"]),
            reference_price=float(row["arrival_price"]),
            spec=spec,
        ),
        axis=1,
    )
    normalized["implementation_shortfall_dollars"] = normalized.apply(
        lambda row: normalize_fill_to_dollars(
            fill_price=float(row["avg_fill_price"]),
            reference_price=float(row["arrival_price"]),
            contracts=float(row["quantity"]),
            spec=spec,
        ),
        axis=1,
    )
    return normalized
