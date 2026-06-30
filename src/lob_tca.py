"""Execution evaluation helpers for synthetic LOB outputs."""

from __future__ import annotations

import pandas as pd


def queue_wait_time_stats(execution_reports: pd.DataFrame) -> dict[str, float]:
    """Summarize queue wait time in microseconds from execution reports."""
    _require_columns(execution_reports, ["latency_us"])
    valid = execution_reports["latency_us"].dropna()
    if valid.empty:
        return {
            "count": 0.0,
            "mean_latency_us": 0.0,
            "median_latency_us": 0.0,
            "max_latency_us": 0.0,
        }

    return {
        "count": float(len(valid)),
        "mean_latency_us": float(valid.mean()),
        "median_latency_us": float(valid.median()),
        "max_latency_us": float(valid.max()),
    }


def realized_spread_bps(
    execution_reports: pd.DataFrame,
    reference_mid_price: float,
) -> float:
    """Return quantity-weighted realized spread in basis points versus a reference mid."""
    _require_columns(execution_reports, ["side", "fill_price", "filled_quantity"])
    if reference_mid_price <= 0:
        raise ValueError("reference_mid_price must be positive.")

    fills = execution_reports[execution_reports["filled_quantity"] > 0].copy()
    if fills.empty:
        return 0.0

    def signed_spread(row: pd.Series) -> float:
        if row["side"] == "buy":
            return float(row["fill_price"] - reference_mid_price)
        return float(reference_mid_price - row["fill_price"])

    fills["signed_spread"] = fills.apply(signed_spread, axis=1)
    avg_spread = (fills["signed_spread"] * fills["filled_quantity"]).sum() / fills["filled_quantity"].sum()
    return float(10_000 * avg_spread / reference_mid_price)


def realized_impact_from_trade_path(
    trade_prints: pd.DataFrame,
    arrival_mid_price: float,
) -> float:
    """Return average trade-path impact versus arrival mid in basis points."""
    _require_columns(trade_prints, ["price", "quantity"])
    if arrival_mid_price <= 0:
        raise ValueError("arrival_mid_price must be positive.")

    prints = trade_prints[trade_prints["quantity"] > 0].copy()
    if prints.empty:
        return 0.0

    avg_trade_price = (prints["price"] * prints["quantity"]).sum() / prints["quantity"].sum()
    return float(10_000 * (avg_trade_price - arrival_mid_price) / arrival_mid_price)


def fill_probability_by_queue_position(execution_reports: pd.DataFrame) -> pd.DataFrame:
    """Estimate empirical fill rate by queue position at submit."""
    _require_columns(execution_reports, ["queue_position_at_submit", "fill_status"])
    reports = execution_reports.dropna(subset=["queue_position_at_submit"]).copy()
    if reports.empty:
        return pd.DataFrame(columns=["queue_position_at_submit", "n_orders", "fill_probability"])

    reports["filled_flag"] = reports["fill_status"].isin({"filled", "partial"}).astype(float)
    grouped = (
        reports.groupby("queue_position_at_submit")
        .agg(
            n_orders=("fill_status", "size"),
            fill_probability=("filled_flag", "mean"),
        )
        .reset_index()
        .sort_values("queue_position_at_submit")
    )
    return grouped


def _require_columns(data: pd.DataFrame, columns: list[str]) -> None:
    """Validate required columns."""
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required LOB TCA columns: {missing}")
