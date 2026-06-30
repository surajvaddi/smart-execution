"""Statistical comparison helpers for execution strategy result frames."""

from __future__ import annotations

import random

import pandas as pd


def compare_strategy_results(
    results: pd.DataFrame,
    metric: str = "implementation_shortfall_bps",
    lower_is_better: bool = True,
) -> pd.DataFrame:
    """Aggregate one metric by strategy and rank the strategies."""
    _require_columns(results, ["strategy", metric])

    summary = (
        results.groupby("strategy", dropna=False)[metric]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .reset_index()
    )
    summary["rank"] = summary["mean"].rank(method="dense", ascending=lower_is_better)
    return summary.sort_values(["rank", "strategy"]).reset_index(drop=True)


def bootstrap_strategy_difference(
    results: pd.DataFrame,
    left_strategy: str,
    right_strategy: str,
    metric: str = "implementation_shortfall_bps",
    n_bootstrap: int = 1_000,
    random_seed: int = 42,
) -> dict[str, float]:
    """Bootstrap the difference in mean metric values between two strategies."""
    _require_columns(results, ["strategy", metric])
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be positive.")

    left = results.loc[results["strategy"] == left_strategy, metric].dropna().tolist()
    right = results.loc[results["strategy"] == right_strategy, metric].dropna().tolist()
    if not left or not right:
        raise ValueError("Both strategies must have at least one metric observation.")

    rng = random.Random(random_seed)
    deltas = []
    for _ in range(n_bootstrap):
        left_sample = [left[rng.randrange(len(left))] for _ in range(len(left))]
        right_sample = [right[rng.randrange(len(right))] for _ in range(len(right))]
        deltas.append(float(sum(left_sample) / len(left_sample) - sum(right_sample) / len(right_sample)))

    deltas.sort()
    mean_delta = float(sum(deltas) / len(deltas))
    return {
        "left_strategy": left_strategy,
        "right_strategy": right_strategy,
        "metric": metric,
        "mean_difference": mean_delta,
        "p05_difference": _quantile(deltas, 0.05),
        "p50_difference": _quantile(deltas, 0.50),
        "p95_difference": _quantile(deltas, 0.95),
    }


def strategy_tail_risk_summary(
    results: pd.DataFrame,
    metric: str = "implementation_shortfall_bps",
    tail_quantile: float = 0.90,
) -> pd.DataFrame:
    """Summarize downside tail behavior for one strategy metric."""
    _require_columns(results, ["strategy", metric])
    if tail_quantile <= 0 or tail_quantile >= 1:
        raise ValueError("tail_quantile must be between 0 and 1.")

    rows = []
    for strategy, group in results.groupby("strategy", dropna=False):
        values = group[metric].dropna()
        if values.empty:
            continue
        threshold = float(values.quantile(tail_quantile))
        tail = values[values >= threshold]
        rows.append(
            {
                "strategy": strategy,
                "metric": metric,
                "tail_quantile": tail_quantile,
                "tail_threshold": threshold,
                "tail_mean": float(tail.mean()),
                "tail_count": int(len(tail)),
            }
        )

    return pd.DataFrame(rows).sort_values("strategy").reset_index(drop=True)


def _quantile(values: list[float], q: float) -> float:
    """Return a simple linear-interpolated quantile from sorted values."""
    if not values:
        raise ValueError("values must be non-empty.")
    if q <= 0:
        return float(values[0])
    if q >= 1:
        return float(values[-1])

    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return float(values[lower] * (1.0 - weight) + values[upper] * weight)


def _require_columns(data: pd.DataFrame, columns: list[str]) -> None:
    """Validate required input columns for strategy benchmark helpers."""
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required strategy benchmark columns: {missing}")
