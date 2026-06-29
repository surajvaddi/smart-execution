"""Dataset metadata helpers for research provenance and contract validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
    normalized = metadata if isinstance(metadata, DatasetMetadata) else DatasetMetadata(**metadata)

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
    for key, value in normalized.as_dict().items():
        attached[key] = value
    return attached
