"""Backtest helpers for adaptive ensemble RL execution research."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.backtester import Backtester
from src.execution import ParentOrder, generate_parent_orders
from src.features import add_microstructure_features
from src.fill_simulator import DEFAULT_FILL_CONFIG, DEFAULT_FILL_MODEL, FillModelConfig
from src.rl_env import ExecutionEnv, RL_STRATEGY_NAME
from src.tca import compute_tca_metrics


def run_rl_backtest(
    input_csv: str | Path,
    policy: Any,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    max_orders_per_ticker: int | None = 1,
    include_baselines: bool = True,
) -> pd.DataFrame:
    """Run baselines and an RL policy on the same generated parent orders."""
    data = pd.read_csv(input_csv, index_col=0, parse_dates=True)
    return run_rl_backtest_data(
        data=data,
        policy=policy,
        fill_model=fill_model,
        fill_config=fill_config,
        max_orders_per_ticker=max_orders_per_ticker,
        include_baselines=include_baselines,
    )


def run_rl_backtest_data(
    data: pd.DataFrame,
    policy: Any,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    max_orders_per_ticker: int | None = 1,
    include_baselines: bool = True,
) -> pd.DataFrame:
    """Run baselines and an RL policy on an in-memory market DataFrame."""
    fill_config = fill_config or DEFAULT_FILL_CONFIG
    featured = add_microstructure_features(data)
    parent_orders = generate_parent_orders(
        featured,
        max_orders_per_ticker=max_orders_per_ticker,
    )
    if not parent_orders:
        raise ValueError("No parent orders generated from input data.")

    result_parts = []
    if include_baselines:
        baseline = Backtester(
            tickers=sorted(featured["ticker"].unique()),
            fill_config=fill_config,
            max_orders_per_ticker=max_orders_per_ticker,
        )
        result_parts.append(baseline.run_single_ticker_data(featured))

    rl_rows = []
    for order in parent_orders:
        env = ExecutionEnv(
            order=order,
            market_data=featured,
            strategies={},
            fill_model=fill_model,
            fill_config=fill_config,
        )
        state = env.reset()
        done = False
        while not done:
            action = policy.select_action(state)
            state, _, done, _ = env.step(action)

        fills = env.fill_frame()
        if fills.empty:
            fills = _empty_rl_fills(order, featured)
        metrics = compute_tca_metrics(order, fills, featured)
        metrics["strategy"] = RL_STRATEGY_NAME
        metrics["parent_order_id"] = order.order_id
        metrics["fill_model"] = fill_model
        rl_rows.append(metrics)

    result_parts.append(pd.DataFrame(rl_rows))
    return pd.concat(result_parts, ignore_index=True)


def run_rl_policy_on_data(
    data: pd.DataFrame,
    policy: Any,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig | None = None,
    max_orders_per_ticker: int | None = 1,
) -> pd.DataFrame:
    """Run only the RL policy on an in-memory market DataFrame."""
    fill_config = fill_config or DEFAULT_FILL_CONFIG
    featured = add_microstructure_features(data) if "spread_proxy" not in data.columns else data
    parent_orders = generate_parent_orders(
        featured,
        max_orders_per_ticker=max_orders_per_ticker,
    )
    rows = []
    for order in parent_orders:
        env = ExecutionEnv(
            order,
            featured,
            strategies={},
            fill_model=fill_model,
            fill_config=fill_config,
        )
        state = env.reset()
        done = False
        while not done:
            action = policy.select_action(state)
            state, _, done, _ = env.step(action)
        fills = env.fill_frame()
        if fills.empty:
            fills = _empty_rl_fills(order, featured)
        metrics = compute_tca_metrics(order, fills, featured)
        metrics["strategy"] = RL_STRATEGY_NAME
        metrics["parent_order_id"] = order.order_id
        metrics["fill_model"] = fill_model
        rows.append(metrics)
    return pd.DataFrame(rows)


def _empty_rl_fills(order: ParentOrder, market_data: pd.DataFrame) -> pd.DataFrame:
    """Create a zero-fill placeholder so TCA can score a no-trade episode."""
    window = market_data[market_data["ticker"] == order.ticker]
    if order.date is not None:
        window = window[window["date"] == order.date]
    first = window.sort_index().iloc[0]
    return pd.DataFrame(
        {
            "timestamp": [first.name],
            "ticker": [order.ticker],
            "side": [order.side],
            "strategy": [RL_STRATEGY_NAME],
            "quantity": [0.0],
            "fill_price": [float("nan")],
            "spread_cost": [0.0],
            "impact_cost": [0.0],
            "adverse_selection_cost": [0.0],
            "mid_price": [float(first["close"])],
            "placement_style": ["wait"],
            "fill_model": ["none"],
        }
    )
