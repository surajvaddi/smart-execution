"""Plotting utilities for execution analysis and reports."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "smart_execution_matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "smart_execution_cache"))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


# All report-ready figures should be written here so the markdown report can
# reference stable relative paths.
FIGURES_DIR = Path("reports/figures")


def generate_report_plots(
    backtest_summary_csv: str | Path | None = None,
    execution_grid_summary_csv: str | Path | None = None,
    monte_carlo_summary_csv: str | Path | None = None,
    output_dir: str | Path = FIGURES_DIR,
) -> list[Path]:
    """Generate report-ready PNG figures from existing summary CSV files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    if backtest_summary_csv and Path(backtest_summary_csv).exists():
        summary = pd.read_csv(backtest_summary_csv)
        generated.append(
            plot_strategy_cost_summary(
                summary,
                output_path / "strategy_tca_costs.png",
            )
        )
        generated.append(
            plot_strategy_fill_rates(
                summary,
                output_path / "strategy_fill_rates.png",
            )
        )

    if execution_grid_summary_csv and Path(execution_grid_summary_csv).exists():
        grid = pd.read_csv(execution_grid_summary_csv)
        generated.append(
            plot_execution_grid_heatmap(
                grid,
                "implementation_shortfall_bps",
                output_path / "execution_grid_shortfall_heatmap.png",
            )
        )
        generated.append(
            plot_execution_grid_heatmap(
                grid,
                "fill_rate",
                output_path / "execution_grid_fill_rate_heatmap.png",
            )
        )

    if monte_carlo_summary_csv and Path(monte_carlo_summary_csv).exists():
        monte_carlo = pd.read_csv(monte_carlo_summary_csv)
        generated.append(
            plot_monte_carlo_interval(
                monte_carlo,
                "implementation_shortfall_bps",
                output_path / "monte_carlo_shortfall_intervals.png",
            )
        )
        generated.append(
            plot_monte_carlo_interval(
                monte_carlo,
                "fill_rate",
                output_path / "monte_carlo_fill_rate_intervals.png",
            )
        )

    return generated


def plot_strategy_cost_summary(summary: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot strategy-level implementation shortfall, spread, and impact costs."""
    required = ["strategy", "implementation_shortfall_bps", "spread_cost_bps", "impact_cost_bps"]
    _require_columns(summary, required)
    ordered = summary.sort_values("implementation_shortfall_bps")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = range(len(ordered))
    width = 0.25
    ax.bar(
        [idx - width for idx in x],
        ordered["implementation_shortfall_bps"],
        width=width,
        label="Implementation shortfall",
        color="#1f77b4",
    )
    ax.bar(
        x,
        ordered["spread_cost_bps"],
        width=width,
        label="Spread cost",
        color="#2ca02c",
    )
    ax.bar(
        [idx + width for idx in x],
        ordered["impact_cost_bps"],
        width=width,
        label="Impact cost",
        color="#d62728",
    )
    ax.set_title("Strategy TCA Costs")
    ax.set_ylabel("Basis points")
    ax.set_xticks(list(x))
    ax.set_xticklabels(ordered["strategy"], rotation=30, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    return _save_figure(fig, output_path)


def plot_strategy_fill_rates(summary: pd.DataFrame, output_path: str | Path) -> Path:
    """Plot strategy-level fill rates."""
    required = ["strategy", "fill_rate"]
    _require_columns(summary, required)
    ordered = summary.sort_values("fill_rate", ascending=False)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(ordered["strategy"], ordered["fill_rate"], color="#4c78a8")
    ax.set_title("Strategy Fill Rates")
    ax.set_ylabel("Fill rate")
    ax.set_ylim(0, max(1.0, float(ordered["fill_rate"].max()) * 1.05))
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    return _save_figure(fig, output_path)


def plot_execution_grid_heatmap(
    summary: pd.DataFrame,
    metric: str,
    output_path: str | Path,
) -> Path:
    """Plot one strategy-by-placement metric as a heatmap."""
    required = ["strategy", "placement_style", metric]
    _require_columns(summary, required)
    pivot = summary.pivot(index="strategy", columns="placement_style", values=metric)

    fig_width = max(8.0, 0.85 * len(pivot.columns) + 3.5)
    fig_height = max(4.5, 0.6 * len(pivot.index) + 2.5)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="viridis")
    ax.set_title(_title_from_metric(metric))
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    for row_idx, strategy in enumerate(pivot.index):
        for col_idx, placement in enumerate(pivot.columns):
            value = pivot.loc[strategy, placement]
            label = "" if pd.isna(value) else f"{value:.2f}"
            ax.text(col_idx, row_idx, label, ha="center", va="center", color="white", fontsize=8)

    fig.colorbar(image, ax=ax, label=metric)
    return _save_figure(fig, output_path)


def plot_monte_carlo_interval(
    summary: pd.DataFrame,
    metric: str,
    output_path: str | Path,
) -> Path:
    """Plot Monte Carlo mean with p10/p90 interval by strategy-placement pair."""
    mean_col = f"{metric}_mean"
    p10_col = f"{metric}_p10"
    p90_col = f"{metric}_p90"
    required = ["strategy", "placement_style", mean_col, p10_col, p90_col]
    _require_columns(summary, required)

    frame = summary.copy()
    frame["label"] = frame["strategy"] + " / " + frame["placement_style"]
    frame = frame.sort_values(mean_col)
    lower = frame[mean_col] - frame[p10_col]
    upper = frame[p90_col] - frame[mean_col]

    fig_height = max(5.0, 0.35 * len(frame) + 1.5)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    ax.errorbar(
        frame[mean_col],
        frame["label"],
        xerr=[lower, upper],
        fmt="o",
        color="#1f77b4",
        ecolor="#9ecae1",
        capsize=3,
    )
    ax.set_title(f"Monte Carlo {_title_from_metric(metric)}")
    ax.set_xlabel(metric)
    ax.grid(axis="x", alpha=0.25)
    return _save_figure(fig, output_path)


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    """Raise a clear error when a plot input is missing required columns."""
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        raise ValueError(f"Missing required plot columns: {missing}")


def _title_from_metric(metric: str) -> str:
    """Return a human-readable title fragment for a metric column."""
    return metric.replace("_", " ").replace("bps", "(bps)").title()


def _save_figure(fig: plt.Figure, output_path: str | Path) -> Path:
    """Save and close a matplotlib figure."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
