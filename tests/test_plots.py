"""Tests for static report plot generation."""

from __future__ import annotations

import pandas as pd

from src.plots import (
    generate_report_plots,
    plot_execution_grid_heatmap,
    plot_monte_carlo_interval,
    plot_strategy_cost_summary,
)


def test_strategy_cost_plot_writes_png(tmp_path) -> None:
    summary = pd.DataFrame(
        {
            "strategy": ["TWAP", "VWAP"],
            "implementation_shortfall_bps": [10.0, 8.0],
            "spread_cost_bps": [1.0, 1.2],
            "impact_cost_bps": [2.0, 1.8],
        }
    )

    output_path = plot_strategy_cost_summary(summary, tmp_path / "costs.png")

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_execution_grid_heatmap_writes_png(tmp_path) -> None:
    summary = pd.DataFrame(
        {
            "strategy": ["TWAP", "TWAP", "VWAP", "VWAP"],
            "placement_style": ["market", "passive_limit", "market", "passive_limit"],
            "fill_rate": [1.0, 0.7, 1.0, 0.8],
        }
    )

    output_path = plot_execution_grid_heatmap(summary, "fill_rate", tmp_path / "heatmap.png")

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_monte_carlo_interval_writes_png(tmp_path) -> None:
    summary = pd.DataFrame(
        {
            "strategy": ["TWAP", "VWAP"],
            "placement_style": ["market", "passive_limit"],
            "fill_rate_mean": [1.0, 0.75],
            "fill_rate_p10": [1.0, 0.60],
            "fill_rate_p90": [1.0, 0.85],
        }
    )

    output_path = plot_monte_carlo_interval(summary, "fill_rate", tmp_path / "mc.png")

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_generate_report_plots_skips_missing_optional_inputs(tmp_path) -> None:
    backtest = pd.DataFrame(
        {
            "strategy": ["TWAP", "VWAP"],
            "implementation_shortfall_bps": [10.0, 8.0],
            "spread_cost_bps": [1.0, 1.2],
            "impact_cost_bps": [2.0, 1.8],
            "fill_rate": [1.0, 0.98],
        }
    )
    backtest_path = tmp_path / "backtest.csv"
    backtest.to_csv(backtest_path, index=False)

    generated = generate_report_plots(
        backtest_summary_csv=backtest_path,
        execution_grid_summary_csv=tmp_path / "missing_grid.csv",
        monte_carlo_summary_csv=tmp_path / "missing_mc.csv",
        output_dir=tmp_path / "figures",
    )

    assert len(generated) == 2
    assert all(path.exists() for path in generated)
