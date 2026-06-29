"""Provenance helpers for research outputs and saved report artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.dataset_metadata import VALID_DATA_BASIS


@dataclass(frozen=True)
class ReportProvenance:
    """Standard provenance fields for research artifacts."""

    research_mode: str
    data_basis: str
    source_dataset: str
    model_name: str
    simulation_model: str
    random_seed: int | None
    config_id: str
    generated_at: str

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict representation."""
        return {
            "research_mode": self.research_mode,
            "data_basis": self.data_basis,
            "source_dataset": self.source_dataset,
            "model_name": self.model_name,
            "simulation_model": self.simulation_model,
            "random_seed": self.random_seed,
            "config_id": self.config_id,
            "generated_at": self.generated_at,
        }


def build_provenance_record(
    research_mode: str,
    data_basis: str,
    source_dataset: str,
    model_name: str,
    simulation_model: str,
    random_seed: int | None = None,
    config_id: str = "default",
    generated_at: str | None = None,
) -> ReportProvenance:
    """Return a validated provenance object."""
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    record = ReportProvenance(
        research_mode=str(research_mode),
        data_basis=str(data_basis),
        source_dataset=str(source_dataset),
        model_name=str(model_name),
        simulation_model=str(simulation_model),
        random_seed=random_seed,
        config_id=str(config_id),
        generated_at=str(timestamp),
    )
    validate_provenance_record(record)
    return record


def validate_provenance_record(
    record: ReportProvenance | dict[str, Any],
) -> ReportProvenance:
    """Validate provenance fields and return a normalized record."""
    normalized = record if isinstance(record, ReportProvenance) else ReportProvenance(**record)

    for field_name in [
        "research_mode",
        "data_basis",
        "source_dataset",
        "model_name",
        "simulation_model",
        "config_id",
        "generated_at",
    ]:
        value = getattr(normalized, field_name)
        if not str(value).strip():
            raise ValueError(f"{field_name} must be a non-empty string.")

    if normalized.data_basis not in VALID_DATA_BASIS:
        raise ValueError(
            f"data_basis must be one of {sorted(VALID_DATA_BASIS)}, got {normalized.data_basis!r}."
        )
    if normalized.random_seed is not None and not isinstance(normalized.random_seed, int):
        raise ValueError("random_seed must be an integer or None.")

    return normalized


def attach_provenance_columns(
    data: pd.DataFrame,
    record: ReportProvenance | dict[str, Any],
) -> pd.DataFrame:
    """Attach provenance fields to a DataFrame without mutating the input."""
    normalized = validate_provenance_record(record)
    attached = data.copy()
    for key, value in normalized.as_dict().items():
        attached[key] = value
    return attached
