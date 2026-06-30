"""Session helpers for futures-aware intraday filtering and profiling."""

from __future__ import annotations

from datetime import time

import pandas as pd

from src.execution import parse_time
from src.instruments import InstrumentSpec


def session_mask_for_instrument(
    data: pd.DataFrame,
    spec: InstrumentSpec,
) -> pd.Series:
    """Return a boolean mask for rows that fall inside an instrument's session."""
    if data.empty:
        return pd.Series(dtype=bool, index=data.index)
    if "time" not in data.columns:
        raise ValueError("data must include a time column.")

    start_time, end_time = _parse_trading_hours(spec.trading_hours)
    bar_times = data["time"].map(parse_time)

    if start_time == end_time:
        return pd.Series(True, index=data.index)
    if start_time < end_time:
        return (bar_times >= start_time) & (bar_times <= end_time)
    return (bar_times >= start_time) | (bar_times <= end_time)


def session_liquidity_profile(
    data: pd.DataFrame,
    spec: InstrumentSpec,
) -> pd.DataFrame:
    """Summarize in-session volume and dollar volume by intraday bar."""
    required = ["bar_index", "volume", "close", "time"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required session liquidity columns: {missing}")

    mask = session_mask_for_instrument(data, spec)
    session_data = data.loc[mask].copy()
    if session_data.empty:
        return pd.DataFrame(columns=["bar_index", "mean_volume", "mean_dollar_volume", "session_share"])

    session_data["dollar_volume"] = session_data["close"] * session_data["volume"]
    grouped = (
        session_data.groupby("bar_index")
        .agg(
            mean_volume=("volume", "mean"),
            mean_dollar_volume=("dollar_volume", "mean"),
        )
        .reset_index()
        .sort_values("bar_index")
    )
    total_volume = grouped["mean_volume"].sum()
    grouped["session_share"] = 0.0 if total_volume <= 0 else grouped["mean_volume"] / total_volume
    return grouped


def _parse_trading_hours(trading_hours: str) -> tuple[time, time]:
    """Parse `HH:MM-HH:MM` trading-hour windows, including overnight sessions."""
    if "-" not in trading_hours:
        raise ValueError("trading_hours must use the format HH:MM-HH:MM.")
    start_value, end_value = trading_hours.split("-", maxsplit=1)
    return parse_time(start_value), _normalize_end_time(end_value)


def _normalize_end_time(value: str) -> time:
    """Treat 24:00 as end-of-day for 24-hour sessions."""
    if value == "24:00":
        return time(0, 0)
    return parse_time(value)
