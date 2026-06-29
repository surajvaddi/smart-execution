"""Dataset metadata helpers for research provenance and contract validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


VALID_DATA_BASIS = {"real", "synthetic", "proxy"}


@dataclass(frozen=True)
class DatasetMetadata:
    """Compact description of a research dataset and its semantic basis."""

    dataset_name: str
    source_name: str
    frequency: str
    timezone: str
    instrument_type: str
    data_basis: str
    contains_quotes: bool
    contains_depth: bool
    contains_order_events: bool
    contains_trade_events: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a plain-JSON-friendly representation."""
        return asdict(self)


def build_dataset_metadata(
    dataset_name: str,
    source_name: str,
    frequency: str,
    timezone: str,
    instrument_type: str,
    data_basis: str,
    contains_quotes: bool = False,
    contains_depth: bool = False,
    contains_order_events: bool = False,
    contains_trade_events: bool = False,
) -> DatasetMetadata:
    """Return validated dataset metadata for a research frame."""
    metadata = DatasetMetadata(
        dataset_name=str(dataset_name),
        source_name=str(source_name),
        frequency=str(frequency),
        timezone=str(timezone),
        instrument_type=str(instrument_type),
        data_basis=str(data_basis),
        contains_quotes=bool(contains_quotes),
        contains_depth=bool(contains_depth),
        contains_order_events=bool(contains_order_events),
        contains_trade_events=bool(contains_trade_events),
    )
    validate_dataset_metadata(metadata)
    return metadata


def validate_dataset_metadata(metadata: DatasetMetadata | dict[str, Any]) -> DatasetMetadata:
    """Validate metadata fields and return a normalized dataclass."""
    if isinstance(metadata, DatasetMetadata):
        normalized = metadata
    else:
        required = DatasetMetadata.__dataclass_fields__.keys()
        missing = [field_name for field_name in required if field_name not in metadata]
        if missing:
            raise ValueError(f"Missing required dataset metadata fields: {missing}")
        normalized = DatasetMetadata(**metadata)

    string_fields = [
        "dataset_name",
        "source_name",
        "frequency",
        "timezone",
        "instrument_type",
        "data_basis",
    ]
    for field_name in string_fields:
        value = getattr(normalized, field_name)
        if not str(value).strip():
            raise ValueError(f"{field_name} must be a non-empty string.")

    if normalized.data_basis not in VALID_DATA_BASIS:
        raise ValueError(
            f"data_basis must be one of {sorted(VALID_DATA_BASIS)}, got {normalized.data_basis!r}."
        )

    if normalized.contains_depth and not normalized.contains_quotes:
        raise ValueError("Datasets with depth must also declare contains_quotes=True.")
    if normalized.contains_order_events and not normalized.contains_trade_events:
        # Event streams can omit book updates or quotes, but if order events are
        # present the dataset is no longer a pure OHLCV-style bar frame.
        return normalized

    return normalized


def attach_dataset_metadata(
    data: pd.DataFrame,
    metadata: DatasetMetadata | dict[str, Any],
) -> pd.DataFrame:
    """Attach metadata fields to a DataFrame without mutating the input frame."""
    normalized = validate_dataset_metadata(metadata)
    attached = data.copy()
    attached.attrs = dict(data.attrs)
    attached.attrs["dataset_metadata"] = normalized.as_dict()
    for key, value in normalized.as_dict().items():
        attached[key] = value
    return attached


def get_dataset_metadata(data: pd.DataFrame) -> dict[str, Any] | None:
    """Return metadata from attrs or constant metadata columns when present."""
    from_attrs = data.attrs.get("dataset_metadata")
    if from_attrs is not None:
        return validate_dataset_metadata(from_attrs).as_dict()

    metadata_fields = DatasetMetadata.__dataclass_fields__.keys()
    if not set(metadata_fields).issubset(data.columns):
        return None

    if data.empty:
        return None

    record = {field_name: data[field_name].iloc[0] for field_name in metadata_fields}
    return validate_dataset_metadata(record).as_dict()


def infer_dataset_metadata(
    data: pd.DataFrame,
    source_name: str | Path,
    instrument_type: str = "equity",
    data_basis: str = "proxy",
) -> DatasetMetadata:
    """Infer a baseline metadata record from a market-data frame."""
    return build_dataset_metadata(
        dataset_name=Path(source_name).name,
        source_name=str(source_name),
        frequency=_infer_frequency(data),
        timezone=_infer_timezone(data),
        instrument_type=instrument_type,
        data_basis=data_basis,
        contains_quotes=False,
        contains_depth=False,
        contains_order_events=False,
        contains_trade_events=False,
    )


def _infer_frequency(data: pd.DataFrame) -> str:
    """Infer a readable cadence label from a datetime index when possible."""
    if not isinstance(data.index, pd.DatetimeIndex) or len(data.index) < 2:
        return "unknown"

    diffs = data.index.to_series().sort_values().diff().dropna()
    if diffs.empty:
        return "unknown"

    mode = diffs.mode()
    if mode.empty:
        return "unknown"

    delta = mode.iloc[0]
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "unknown"
    if total_seconds % 3600 == 0:
        return f"{total_seconds // 3600}h"
    if total_seconds % 60 == 0:
        return f"{total_seconds // 60}min"
    return f"{total_seconds}s"


def _infer_timezone(data: pd.DataFrame) -> str:
    """Infer timezone string from a datetime index when possible."""
    if isinstance(data.index, pd.DatetimeIndex) and data.index.tz is not None:
        return str(data.index.tz)
    return "unknown"
