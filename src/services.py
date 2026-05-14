"""Callable service layer for backend and frontend integrations.

The CLI remains useful for batch workflows, but API and UI code should call
these functions directly instead of shelling out to ``main.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.backtester import Backtester, default_strategies
from src.execution import generate_parent_orders, parent_orders_to_frame, parse_time
from src.features import FEATURE_COLUMNS, add_microstructure_features, estimate_volume_curve
from src.fill_simulator import (
    DEFAULT_FILL_MODEL,
    DEFAULT_RANDOM_SEED,
    PLACEMENT_STYLES,
    STOCHASTIC_QUEUE_FILL_MODEL,
    FillModelConfig,
)
from src.monte_carlo import (
    MonteCarloConfig,
    run_monte_carlo_execution_grid,
    summarize_monte_carlo_results,
)
from src.plots import FIGURES_DIR, generate_report_plots
from src.rl_backtester import run_rl_backtest_data
from src.rl_policy import HeuristicExecutionPolicy
from src.signals import (
    DEFAULT_HORIZONS,
    add_forward_returns,
    evaluate_signals,
    signal_decay_table,
    signal_quality_summary,
)
from src.strategies import AdaptiveModelWeights, AdaptiveStrategy, ExecutionStrategy


@dataclass(frozen=True)
class ExecutionGridResult:
    """Detailed execution-grid outputs."""

    results: pd.DataFrame
    fills: pd.DataFrame


@dataclass(frozen=True)
class MonteCarloResult:
    """Detailed and summarized Monte Carlo outputs."""

    results: pd.DataFrame
    fills: pd.DataFrame
    summary: pd.DataFrame


@dataclass(frozen=True)
class SignalResearchResult:
    """Signal evaluation outputs used by reports and dashboards."""

    evaluation: pd.DataFrame
    decay: pd.DataFrame
    summary: pd.DataFrame


def load_processed_data(
    input_csv: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> pd.DataFrame:
    """Load a processed market-data CSV and apply optional date/time filters."""
    data = pd.read_csv(input_csv, index_col=0, parse_dates=True)
    return filter_market_data(data, start_date, end_date, start_time, end_time)


def load_processed_datasets(
    input_csvs: list[str | Path],
    start_date: str | None = None,
    end_date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> pd.DataFrame:
    """Load and concatenate multiple processed market-data CSVs."""
    if not input_csvs:
        raise ValueError("At least one input CSV is required.")

    frames = [
        load_processed_data(path, start_date, end_date, start_time, end_time)
        for path in input_csvs
    ]
    return pd.concat(frames).sort_index()


def filter_market_data(
    data: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> pd.DataFrame:
    """Apply optional inclusive date and time filters to market data."""
    filtered = data.copy()

    if bool(start_date) != bool(end_date):
        raise ValueError("start_date and end_date must be provided together.")
    if bool(start_time) != bool(end_time):
        raise ValueError("start_time and end_time must be provided together.")

    if start_date and end_date:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        if start > end:
            raise ValueError("start_date must be on or before end_date.")
        filtered_dates = pd.to_datetime(filtered["date"]).dt.date
        filtered = filtered[(filtered_dates >= start) & (filtered_dates <= end)]

    if start_time and end_time:
        start = parse_time(start_time)
        end = parse_time(end_time)
        if start > end:
            raise ValueError("start_time must be on or before end_time.")
        filtered_times = filtered["time"].map(parse_time)
        filtered = filtered[(filtered_times >= start) & (filtered_times <= end)]

    if filtered.empty:
        raise ValueError("No rows remain after applying date/time filters.")
    return filtered


def prepare_features(data: pd.DataFrame) -> pd.DataFrame:
    """Return market data with microstructure proxy features."""
    if all(col in data.columns for col in FEATURE_COLUMNS):
        return data.copy()
    return add_microstructure_features(data)


def volume_curve(data: pd.DataFrame) -> pd.DataFrame:
    """Return the estimated intraday volume curve as a frame."""
    curve = estimate_volume_curve(data)
    return curve.reset_index()


def parent_orders(
    data: pd.DataFrame,
    max_orders_per_ticker: int | None = 20,
) -> pd.DataFrame:
    """Generate parent orders and return them in tabular form."""
    orders = generate_parent_orders(
        prepare_features(data),
        max_orders_per_ticker=max_orders_per_ticker,
    )
    return parent_orders_to_frame(orders)


def run_backtest(
    data: pd.DataFrame,
    tickers: list[str] | None = None,
    strategies: list[ExecutionStrategy] | None = None,
    adaptive_weights: dict[str, float] | None = None,
    max_orders_per_ticker: int | None = 20,
) -> pd.DataFrame:
    """Run the default strategy backtest on in-memory market data."""
    featured = prepare_features(data)
    backtester = _backtester_for_data(
        featured,
        tickers=tickers,
        strategies=strategies,
        adaptive_weights=adaptive_weights,
        max_orders_per_ticker=max_orders_per_ticker,
    )
    return backtester.run_single_ticker_data(featured)


def run_backtest_csv(
    input_csv: str | Path,
    tickers: list[str] | None = None,
    strategies: list[ExecutionStrategy] | None = None,
    adaptive_weights: dict[str, float] | None = None,
    max_orders_per_ticker: int | None = 20,
) -> pd.DataFrame:
    """Run the default strategy backtest from a processed CSV."""
    data = load_processed_data(input_csv)
    return run_backtest(data, tickers, strategies, adaptive_weights, max_orders_per_ticker)


def run_execution_grid(
    data: pd.DataFrame,
    tickers: list[str] | None = None,
    strategies: list[ExecutionStrategy] | None = None,
    adaptive_weights: dict[str, float] | None = None,
    placement_styles: list[str] | None = None,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    random_seed: int | None = DEFAULT_RANDOM_SEED,
    max_orders_per_ticker: int | None = 20,
) -> ExecutionGridResult:
    """Run every configured strategy and placement style on market data."""
    featured = prepare_features(data)
    backtester = _backtester_for_data(
        featured,
        tickers=tickers,
        strategies=strategies,
        adaptive_weights=adaptive_weights,
        placement_styles=placement_styles,
        fill_model=fill_model,
        fill_config=fill_config,
        random_seed=random_seed,
        max_orders_per_ticker=max_orders_per_ticker,
    )
    results, fills = backtester.run_execution_grid_data(featured)
    return ExecutionGridResult(results=results, fills=fills)


def run_monte_carlo_grid(
    data: pd.DataFrame,
    seeds: list[int],
    placement_styles: list[str] | None = None,
    adaptive_weights: dict[str, float] | None = None,
    fill_model: str | None = None,
    fill_config: FillModelConfig | None = None,
    max_orders_per_ticker: int | None = 1,
) -> MonteCarloResult:
    """Run repeated execution grids and return detailed and summary outputs."""
    featured = prepare_features(data)
    config = MonteCarloConfig(
        seeds=seeds,
        placement_styles=placement_styles,
        fill_model=fill_model or STOCHASTIC_QUEUE_FILL_MODEL,
        fill_config=fill_config or FillModelConfig(),
        max_orders_per_ticker=max_orders_per_ticker,
    )
    results, fills = run_monte_carlo_execution_grid(featured, config)
    summary = summarize_monte_carlo_results(results)
    return MonteCarloResult(results=results, fills=fills, summary=summary)


def run_rl_backtest(
    data: pd.DataFrame,
    policy: Any | None = None,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    max_orders_per_ticker: int | None = 1,
    include_baselines: bool = True,
) -> pd.DataFrame:
    """Run the RL execution policy and optional baseline strategies."""
    return run_rl_backtest_data(
        data=data,
        policy=policy or HeuristicExecutionPolicy(),
        fill_model=fill_model,
        fill_config=fill_config,
        max_orders_per_ticker=max_orders_per_ticker,
        include_baselines=include_baselines,
    )


def run_signal_research(
    data: pd.DataFrame,
    horizons: list[int] | None = None,
) -> SignalResearchResult:
    """Evaluate feature signals against forward returns."""
    selected_horizons = horizons or DEFAULT_HORIZONS
    featured = prepare_features(data)
    signal_data = add_forward_returns(featured, selected_horizons)
    evaluation = evaluate_signals(signal_data, horizons=selected_horizons)
    decay = signal_decay_table(evaluation)
    summary = signal_quality_summary(evaluation)
    return SignalResearchResult(evaluation=evaluation, decay=decay, summary=summary)


def generate_plots(
    backtest_summary_csv: str | Path | None = None,
    execution_grid_summary_csv: str | Path | None = None,
    monte_carlo_summary_csv: str | Path | None = None,
    output_dir: str | Path = FIGURES_DIR,
) -> list[Path]:
    """Generate static report plots from saved summary CSV files."""
    return generate_report_plots(
        backtest_summary_csv=backtest_summary_csv,
        execution_grid_summary_csv=execution_grid_summary_csv,
        monte_carlo_summary_csv=monte_carlo_summary_csv,
        output_dir=output_dir,
    )


def preview_execution_fills(
    fills: pd.DataFrame,
    limit: int = 500,
) -> pd.DataFrame:
    """Return a balanced preview of fills across strategy and placement groups."""
    if fills.empty or limit <= 0:
        return fills.head(0).copy()

    required = ["strategy", "placement_style"]
    missing = [col for col in required if col not in fills.columns]
    if missing:
        raise ValueError(f"Missing required fill preview columns: {missing}")

    ordered = fills.sort_values(["strategy", "placement_style", "timestamp"]).reset_index(drop=True)
    groups = list(ordered.groupby(["strategy", "placement_style"], sort=True, dropna=False))
    if not groups:
        return ordered.head(0)

    if limit >= len(ordered):
        return ordered

    allocation = max(1, limit // len(groups))
    leftovers = limit
    pieces = []
    used_index = set()

    for idx, ((strategy, placement), group) in enumerate(groups):
        if leftovers <= 0:
            break
        remaining_groups = len(groups) - idx
        take = min(
            len(group),
            max(1, leftovers // remaining_groups),
            allocation,
        )
        if take <= 0:
            take = 1
        part = group.head(take)
        pieces.append(part)
        used_index.update(part.index.tolist())
        leftovers -= len(part)

    if leftovers > 0:
        remaining = ordered.loc[~ordered.index.isin(used_index)]
        if not remaining.empty:
            pieces.append(remaining.head(leftovers))

    preview = pd.concat(pieces, ignore_index=True) if pieces else ordered.head(0)
    return preview.head(limit)


def _backtester_for_data(
    data: pd.DataFrame,
    tickers: list[str] | None = None,
    strategies: list[ExecutionStrategy] | None = None,
    adaptive_weights: dict[str, float] | None = None,
    placement_styles: list[str] | None = None,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    random_seed: int | None = DEFAULT_RANDOM_SEED,
    max_orders_per_ticker: int | None = 20,
) -> Backtester:
    """Build a Backtester with defaults inferred from the input data."""
    resolved_tickers = tickers or sorted(data["ticker"].unique().tolist())
    resolved_strategies = strategies or default_strategies()
    if adaptive_weights is not None:
        adapted = []
        for strategy in resolved_strategies:
            if isinstance(strategy, AdaptiveStrategy):
                adapted.append(AdaptiveStrategy(AdaptiveModelWeights(**adaptive_weights)))
            else:
                adapted.append(strategy)
        resolved_strategies = adapted
    return Backtester(
        tickers=resolved_tickers,
        strategies=resolved_strategies,
        placement_styles=placement_styles or PLACEMENT_STYLES.copy(),
        fill_model=fill_model,
        fill_config=fill_config or FillModelConfig(),
        random_seed=random_seed,
        max_orders_per_ticker=max_orders_per_ticker,
    )
