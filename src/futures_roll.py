"""Continuous-contract roll helpers for futures research datasets."""

from __future__ import annotations

import pandas as pd


def compute_roll_dates(
    contracts: dict[str, pd.DataFrame],
    volume_column: str = "volume",
) -> dict[str, pd.Timestamp]:
    """Compute roll dates using a simple volume-crossover rule on adjacent contracts."""
    if len(contracts) < 2:
        return {}

    ordered = sorted(contracts.items(), key=lambda item: item[1].index.min())
    roll_dates: dict[str, pd.Timestamp] = {}
    for (front_name, front_data), (next_name, next_data) in zip(ordered[:-1], ordered[1:]):
        _require_columns(front_data, [volume_column, "close"])
        _require_columns(next_data, [volume_column, "close"])
        overlap = front_data[[volume_column]].join(
            next_data[[volume_column]],
            how="inner",
            lsuffix="_front",
            rsuffix="_next",
        )
        if overlap.empty:
            raise ValueError(f"Contracts {front_name} and {next_name} do not overlap for roll computation.")

        crossover = overlap[overlap[f"{volume_column}_next"] >= overlap[f"{volume_column}_front"]]
        roll_dates[front_name] = crossover.index.min() if not crossover.empty else overlap.index.max()
    return roll_dates


def back_adjust_series(
    contracts: dict[str, pd.DataFrame],
    roll_dates: dict[str, pd.Timestamp],
    price_column: str = "close",
) -> pd.DataFrame:
    """Build a back-adjusted continuous series from ordered contract frames."""
    _require_multiple_contracts(contracts)
    ordered = sorted(contracts.items(), key=lambda item: item[1].index.min())

    adjusted_parts = []
    cumulative_adjustment = 0.0
    for idx, (name, frame) in enumerate(ordered):
        _require_columns(frame, [price_column])
        roll_date = roll_dates.get(name)
        segment = frame.copy()
        if idx < len(ordered) - 1:
            segment = segment.loc[segment.index < roll_date]
            next_frame = ordered[idx + 1][1]
            price_gap = float(next_frame.loc[roll_date, price_column] - frame.loc[roll_date, price_column])
            cumulative_adjustment += price_gap
        segment[price_column] = segment[price_column] + cumulative_adjustment
        segment["source_contract"] = name
        adjusted_parts.append(segment)

    last_name, last_frame = ordered[-1]
    last_segment = last_frame.copy()
    last_segment[price_column] = last_segment[price_column] + cumulative_adjustment
    last_segment["source_contract"] = last_name
    adjusted_parts.append(last_segment)

    return _deduplicate_continuous_parts(adjusted_parts)


def ratio_adjust_series(
    contracts: dict[str, pd.DataFrame],
    roll_dates: dict[str, pd.Timestamp],
    price_column: str = "close",
) -> pd.DataFrame:
    """Build a ratio-adjusted continuous series from ordered contract frames."""
    _require_multiple_contracts(contracts)
    ordered = sorted(contracts.items(), key=lambda item: item[1].index.min())

    adjusted_parts = []
    cumulative_ratio = 1.0
    for idx, (name, frame) in enumerate(ordered):
        _require_columns(frame, [price_column])
        roll_date = roll_dates.get(name)
        segment = frame.copy()
        if idx < len(ordered) - 1:
            segment = segment.loc[segment.index < roll_date]
            next_frame = ordered[idx + 1][1]
            front_price = float(frame.loc[roll_date, price_column])
            next_price = float(next_frame.loc[roll_date, price_column])
            if front_price == 0:
                raise ValueError("Cannot compute ratio adjustment with zero front price.")
            cumulative_ratio *= next_price / front_price
        segment[price_column] = segment[price_column] * cumulative_ratio
        segment["source_contract"] = name
        adjusted_parts.append(segment)

    last_name, last_frame = ordered[-1]
    last_segment = last_frame.copy()
    last_segment[price_column] = last_segment[price_column] * cumulative_ratio
    last_segment["source_contract"] = last_name
    adjusted_parts.append(last_segment)

    return _deduplicate_continuous_parts(adjusted_parts)


def build_continuous_contract(
    contracts: dict[str, pd.DataFrame],
    adjustment: str = "back",
    volume_column: str = "volume",
    price_column: str = "close",
) -> pd.DataFrame:
    """Build a continuous contract using the requested roll-adjustment method."""
    roll_dates = compute_roll_dates(contracts, volume_column=volume_column)
    if adjustment == "back":
        return back_adjust_series(contracts, roll_dates, price_column=price_column)
    if adjustment == "ratio":
        return ratio_adjust_series(contracts, roll_dates, price_column=price_column)
    raise ValueError("adjustment must be 'back' or 'ratio'.")


def _deduplicate_continuous_parts(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate stitched parts and keep the final segment for duplicated timestamps."""
    continuous = pd.concat(parts).sort_index()
    return continuous[~continuous.index.duplicated(keep="last")]


def _require_columns(data: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required futures roll columns: {missing}")


def _require_multiple_contracts(contracts: dict[str, pd.DataFrame]) -> None:
    if len(contracts) < 2:
        raise ValueError("At least two contracts are required to build a continuous series.")
