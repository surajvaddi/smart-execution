"""Monte Carlo helpers for stochastic execution-grid analysis.

This module reruns the existing execution grid across multiple random seeds.
It is a research simulator layer: it summarizes modeled fill uncertainty from
OHLCV-derived synthetic fills, not real order-book execution outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.backtester import Backtester, SUMMARY_METRIC_COLUMNS
from src.fill_simulator import (
    PLACEMENT_STYLES,
    FillModelConfig,
    STOCHASTIC_QUEUE_FILL_MODEL,
)


MONTE_CARLO_STATS = ["mean", "median", "p10", "p90", "std"]


@dataclass(frozen=True)
class MonteCarloConfig:
    """Configuration for repeated stochastic execution-grid simulations."""

    seeds: list[int]
    placement_styles: list[str] | None = None
    fill_model: str = STOCHASTIC_QUEUE_FILL_MODEL
    fill_config: FillModelConfig = field(default_factory=FillModelConfig)
    max_orders_per_ticker: int | None = 1


def run_monte_carlo_execution_grid(
    data: pd.DataFrame,
    config: MonteCarloConfig,
    tickers: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the execution grid once per seed and return detailed rows and fills."""
    if not config.seeds:
        raise ValueError("At least one Monte Carlo seed is required.")

    result_parts = []
    fill_parts = []
    for path_id, seed in enumerate(config.seeds, start=1):
        backtester = Backtester(
            tickers=tickers or sorted(data["ticker"].unique().tolist()),
            placement_styles=config.placement_styles or PLACEMENT_STYLES.copy(),
            fill_model=config.fill_model,
            fill_config=config.fill_config,
            random_seed=seed,
            max_orders_per_ticker=config.max_orders_per_ticker,
        )
        results, fills = backtester.run_execution_grid_data(data)
        results["path_id"] = path_id
        results["random_seed"] = seed
        fills["path_id"] = path_id
        fills["random_seed"] = seed
        result_parts.append(results)
        fill_parts.append(fills)

    return (
        pd.concat(result_parts, ignore_index=True),
        pd.concat(fill_parts, ignore_index=True),
    )


def summarize_monte_carlo_results(
    results: pd.DataFrame,
    group_cols: list[str] | None = None,
    metric_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Summarize repeated-path TCA results with distribution statistics."""
    if results.empty:
        raise ValueError("Cannot summarize empty Monte Carlo results.")

    groups = group_cols or _default_group_cols(results)
    metrics = metric_cols or [col for col in SUMMARY_METRIC_COLUMNS if col in results.columns]
    required = [*groups, *metrics]
    missing = [col for col in required if col not in results.columns]
    if missing:
        raise ValueError(f"Missing required Monte Carlo summary columns: {missing}")

    rows = []
    for group_values, group in results.groupby(groups, dropna=False):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        row = dict(zip(groups, group_values))
        row["num_paths"] = group["random_seed"].nunique() if "random_seed" in group.columns else 0
        row["num_simulations"] = len(group)

        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="coerce")
            row[f"{metric}_mean"] = values.mean()
            row[f"{metric}_median"] = values.median()
            row[f"{metric}_p10"] = values.quantile(0.10)
            row[f"{metric}_p90"] = values.quantile(0.90)
            row[f"{metric}_std"] = values.std()
        rows.append(row)

    return pd.DataFrame(rows).sort_values(groups).reset_index(drop=True)


def _default_group_cols(results: pd.DataFrame) -> list[str]:
    """Choose the natural grouping for execution-grid Monte Carlo output."""
    if "strategy" in results.columns and "placement_style" in results.columns:
        return ["strategy", "placement_style"]
    if "strategy" in results.columns:
        return ["strategy"]
    raise ValueError("Monte Carlo results must include at least a strategy column.")
