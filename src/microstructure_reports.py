"""Report helpers for bar-data microstructure proxy analysis."""

from __future__ import annotations

import pandas as pd


DEFAULT_MICROSTRUCTURE_COLUMNS = [
    "spread_proxy",
    "ofi_proxy",
    "rolling_vol",
    "liquidity_score",
    "alpha_signal",
    "queue_pressure_proxy",
    "hidden_liquidity_proxy",
    "passive_fill_risk_proxy",
]


def summarize_microstructure_regimes(
    data: pd.DataFrame,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Summarize available microstructure proxy regimes with simple statistics."""
    columns = [column for column in (columns or DEFAULT_MICROSTRUCTURE_COLUMNS) if column in data.columns]
    if not columns:
        raise ValueError("No microstructure columns are available to summarize.")

    rows = []
    for column in columns:
        series = data[column].dropna()
        if series.empty:
            continue
        rows.append(
            {
                "feature": column,
                "mean": float(series.mean()),
                "std": float(series.std(ddof=0)),
                "p10": float(series.quantile(0.10)),
                "p50": float(series.quantile(0.50)),
                "p90": float(series.quantile(0.90)),
                "n_obs": int(series.shape[0]),
                "data_basis": "proxy",
            }
        )
    return pd.DataFrame(rows)


def microstructure_metric_scorecard(
    metric_frames: list[pd.DataFrame],
) -> pd.DataFrame:
    """Concatenate metric summary frames into a report-friendly scorecard."""
    if not metric_frames:
        raise ValueError("At least one metric frame is required.")

    scorecard = pd.concat(metric_frames, ignore_index=True, sort=False)
    if "metric" in scorecard.columns:
        return scorecard.sort_values("metric").reset_index(drop=True)
    if "feature" in scorecard.columns:
        return scorecard.sort_values("feature").reset_index(drop=True)
    return scorecard.reset_index(drop=True)
