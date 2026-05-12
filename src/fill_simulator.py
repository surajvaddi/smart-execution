"""Limit-order placement and deterministic fill simulation.

The strategy layer decides when and how much to trade. This module decides where
each child order is placed and whether that placed order fills in the OHLCV bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random

import pandas as pd

from src.execution import ParentOrder
from src.strategies import validate_child_orders
from src.tca import (
    add_synthetic_bid_ask,
    fill_price_for_child_order,
    permanent_market_impact,
    temporary_market_impact,
)


PLACEMENT_STYLES = [
    "market",
    "marketable_limit",
    "aggressive_limit",
    "midpoint_limit",
    "passive_limit",
    "primary_peg",
    "midpoint_peg",
    "adaptive_limit",
]

DEFAULT_FILL_MODEL = "volume_capped_touch"
QUEUE_WEIGHTED_FILL_MODEL = "queue_weighted_touch"
STOCHASTIC_QUEUE_FILL_MODEL = "stochastic_queue_touch"
VALID_FILL_MODELS = {
    DEFAULT_FILL_MODEL,
    QUEUE_WEIGHTED_FILL_MODEL,
    STOCHASTIC_QUEUE_FILL_MODEL,
}
DEFAULT_RANDOM_SEED = 42


@dataclass(frozen=True)
class FillModelConfig:
    """Configurable assumptions for deterministic and stochastic fill models."""

    capacity_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "aggressive_limit": 1.00,
            "midpoint_limit": 0.50,
            "midpoint_peg": 0.50,
            "passive_limit": 0.25,
            "primary_peg": 0.25,
        }
    )
    queue_priorities: dict[str, float] = field(
        default_factory=lambda: {
            "aggressive_limit": 0.85,
            "midpoint_limit": 0.55,
            "midpoint_peg": 0.55,
            "passive_limit": 0.30,
            "primary_peg": 0.30,
        }
    )
    default_capacity_multiplier: float = 0.25
    default_queue_priority: float = 0.30


DEFAULT_FILL_CONFIG = FillModelConfig()


def add_order_placement(
    child_orders: pd.DataFrame,
    market_data: pd.DataFrame,
    placement_style: str,
    parent_order: ParentOrder | None = None,
) -> pd.DataFrame:
    """Add limit-order placement fields to strategy child-order intent."""
    validate_child_orders(child_orders)
    if placement_style not in PLACEMENT_STYLES:
        raise ValueError(f"placement_style must be one of {PLACEMENT_STYLES}, got {placement_style!r}.")

    quoted = _market_lookup(market_data)
    placed = child_orders.merge(quoted, on=["timestamp", "ticker"], how="left")
    required_quote_cols = [
        "high",
        "low",
        "volume",
        "mid_price",
        "half_spread",
        "synthetic_bid",
        "synthetic_ask",
    ]
    if placed[required_quote_cols].isna().any().any():
        raise ValueError("Some child orders could not be matched to market data for placement.")

    if parent_order is not None:
        placed["participation_cap"] = parent_order.participation_cap
    elif "participation_cap" not in placed.columns:
        placed["participation_cap"] = 0.10

    spread_median = float(quoted["spread_proxy"].median()) if "spread_proxy" in quoted.columns else 0.0
    liquidity_75pct = (
        float(quoted["liquidity_score"].quantile(0.75))
        if "liquidity_score" in quoted.columns
        else float("inf")
    )

    resolved_styles = []
    order_types = []
    limit_prices = []

    for _, row in placed.iterrows():
        resolved_style = _resolve_placement_style(
            row=row,
            requested_style=placement_style,
            spread_median=spread_median,
            liquidity_75pct=liquidity_75pct,
        )
        resolved_styles.append(resolved_style)
        order_type, limit_price = _placement_price(row, resolved_style)
        order_types.append(order_type)
        limit_prices.append(limit_price)

    placed["placement_style"] = placement_style
    placed["resolved_placement_style"] = resolved_styles
    placed["order_type"] = order_types
    placed["limit_price"] = limit_prices
    return placed


def simulate_fills(
    placed_orders: pd.DataFrame,
    market_data: pd.DataFrame | None = None,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig = DEFAULT_FILL_CONFIG,
    random_seed: int | None = DEFAULT_RANDOM_SEED,
) -> pd.DataFrame:
    """Simulate child-order fills from placed orders and OHLCV touch rules."""
    if fill_model not in VALID_FILL_MODELS:
        raise ValueError(f"fill_model must be one of {sorted(VALID_FILL_MODELS)}, got {fill_model!r}.")

    required = [
        "timestamp",
        "ticker",
        "side",
        "strategy",
        "quantity",
        "placement_style",
        "resolved_placement_style",
        "order_type",
        "limit_price",
        "high",
        "low",
        "volume",
        "mid_price",
        "synthetic_bid",
        "synthetic_ask",
    ]
    missing = [col for col in required if col not in placed_orders.columns]
    if missing:
        raise ValueError(f"Missing required placed-order columns: {missing}")

    fills = placed_orders.copy()
    submitted_quantities = []
    filled_quantities = []
    unfilled_quantities = []
    fill_statuses = []
    fill_prices = []
    spread_costs = []
    temporary_impacts = []
    permanent_impacts = []
    touch_depths = []
    queue_priorities = []
    fill_probabilities = []
    random_draws = []
    rng = random.Random(random_seed)

    for _, row in fills.iterrows():
        submitted_quantity = float(row["quantity"])
        fill_context = _fill_context(row, fill_model, fill_config, rng)
        filled_quantity = _filled_quantity(row, submitted_quantity, fill_context, fill_config)
        unfilled_quantity = max(submitted_quantity - filled_quantity, 0.0)

        if filled_quantity <= 0:
            fill_price = float("nan")
            spread_cost = 0.0
            temporary_impact = 0.0
            permanent_impact = 0.0
            fill_status = "unfilled"
        else:
            temporary_impact = temporary_market_impact(
                mid_price=float(row["mid_price"]),
                child_quantity=filled_quantity,
                market_volume=float(row["volume"]),
            )
            permanent_impact = permanent_market_impact(
                mid_price=float(row["mid_price"]),
                child_quantity=filled_quantity,
                market_volume=float(row["volume"]),
            )
            fill_price = _simulated_fill_price(row, temporary_impact)
            spread_cost = _spread_cost(row, fill_price)
            fill_status = "filled" if unfilled_quantity <= 1e-9 else "partial"

        submitted_quantities.append(submitted_quantity)
        filled_quantities.append(filled_quantity)
        unfilled_quantities.append(unfilled_quantity)
        fill_statuses.append(fill_status)
        fill_prices.append(fill_price)
        spread_costs.append(spread_cost)
        temporary_impacts.append(temporary_impact)
        permanent_impacts.append(permanent_impact)
        touch_depths.append(fill_context["touch_depth"])
        queue_priorities.append(fill_context["queue_priority"])
        fill_probabilities.append(fill_context["fill_probability"])
        random_draws.append(fill_context["random_draw"])

    fills["submitted_quantity"] = submitted_quantities
    fills["filled_quantity"] = filled_quantities
    fills["unfilled_quantity"] = unfilled_quantities
    fills["fill_status"] = fill_statuses
    fills["fill_model"] = fill_model
    fills["random_seed"] = random_seed
    fills["fill_price"] = fill_prices
    fills["spread_cost"] = spread_costs
    fills["temporary_impact"] = temporary_impacts
    fills["permanent_impact"] = permanent_impacts
    fills["impact_cost"] = fills["temporary_impact"] + fills["permanent_impact"]
    fills["touch_depth"] = touch_depths
    fills["queue_priority"] = queue_priorities
    fills["fill_probability"] = fill_probabilities
    fills["random_draw"] = random_draws

    # TCA functions use `quantity` as executed quantity. Preserve the submitted
    # amount separately so reports can show what was missed.
    fills["quantity"] = fills["filled_quantity"]
    return fills


def place_and_simulate_fills(
    child_orders: pd.DataFrame,
    market_data: pd.DataFrame,
    placement_style: str,
    parent_order: ParentOrder | None = None,
    fill_model: str = DEFAULT_FILL_MODEL,
    fill_config: FillModelConfig = DEFAULT_FILL_CONFIG,
    random_seed: int | None = DEFAULT_RANDOM_SEED,
) -> pd.DataFrame:
    """Apply placement and fill simulation to child-order intent."""
    placed = add_order_placement(child_orders, market_data, placement_style, parent_order)
    return simulate_fills(
        placed,
        market_data=market_data,
        fill_model=fill_model,
        fill_config=fill_config,
        random_seed=random_seed,
    )


def _market_lookup(market_data: pd.DataFrame) -> pd.DataFrame:
    """Return market data with synthetic quotes and timestamp as a column."""
    required = ["ticker", "high", "low", "volume", "close", "spread_proxy"]
    missing = [col for col in required if col not in market_data.columns]
    if missing:
        raise ValueError(f"Missing required fill-simulator market columns: {missing}")

    quoted = add_synthetic_bid_ask(market_data)
    lookup = quoted.reset_index()
    timestamp_col = market_data.index.name or "index"
    lookup = lookup.rename(columns={timestamp_col: "timestamp"})

    cols = [
        "timestamp",
        "ticker",
        "high",
        "low",
        "volume",
        "spread_proxy",
        "mid_price",
        "half_spread",
        "synthetic_bid",
        "synthetic_ask",
    ]
    optional_cols = [col for col in ["alpha_signal", "liquidity_score"] if col in lookup.columns]
    return lookup[cols + optional_cols]


def _resolve_placement_style(
    row: pd.Series,
    requested_style: str,
    spread_median: float,
    liquidity_75pct: float,
) -> str:
    """Resolve adaptive placement into a concrete limit style."""
    if requested_style != "adaptive_limit":
        return requested_style

    alpha = float(row.get("alpha_signal", 0.0))
    side = str(row["side"]).lower()
    volume_capacity = float(row["participation_cap"]) * float(row["volume"])
    cap_usage = float(row["quantity"]) / volume_capacity if volume_capacity > 0 else 1.0

    adverse_alpha = (side == "buy" and alpha > 0) or (side == "sell" and alpha < 0)
    favorable_alpha = (side == "buy" and alpha < 0) or (side == "sell" and alpha > 0)
    low_spread = float(row.get("spread_proxy", 0.0)) <= spread_median
    high_liquidity = float(row.get("liquidity_score", 0.0)) >= liquidity_75pct

    if adverse_alpha or cap_usage >= 0.8:
        return "aggressive_limit"
    if favorable_alpha and low_spread and high_liquidity:
        return "passive_limit"
    return "midpoint_limit"


def _placement_price(row: pd.Series, resolved_style: str) -> tuple[str, float]:
    """Return order type and limit price for a concrete placement style."""
    side = str(row["side"]).lower()
    mid = float(row["mid_price"])
    bid = float(row["synthetic_bid"])
    ask = float(row["synthetic_ask"])
    half_spread = float(row["half_spread"])

    if resolved_style == "market":
        return "market", float("nan")
    if resolved_style == "marketable_limit":
        return "limit", ask if side == "buy" else bid
    if resolved_style == "aggressive_limit":
        return "limit", mid + 0.75 * half_spread if side == "buy" else mid - 0.75 * half_spread
    if resolved_style in {"midpoint_limit", "midpoint_peg"}:
        return "limit", mid
    if resolved_style in {"passive_limit", "primary_peg"}:
        return "limit", bid if side == "buy" else ask

    raise ValueError(f"Unsupported resolved placement style: {resolved_style!r}.")


def _fill_context(
    row: pd.Series,
    fill_model: str,
    fill_config: FillModelConfig,
    rng: random.Random,
) -> dict[str, float]:
    """Return touch and queue inputs used by the selected fill model."""
    resolved_style = str(row["resolved_placement_style"])
    if resolved_style in {"market", "marketable_limit"}:
        return {
            "is_fill_eligible": 1.0,
            "touch_depth": 1.0,
            "queue_priority": 1.0,
            "fill_probability": 1.0,
            "random_draw": float("nan"),
            "scale_capacity_by_probability": 0.0,
        }

    if not _bar_touches_limit(row):
        return {
            "is_fill_eligible": 0.0,
            "touch_depth": 0.0,
            "queue_priority": 0.0,
            "fill_probability": 0.0,
            "random_draw": float("nan"),
            "scale_capacity_by_probability": 0.0,
        }

    if fill_model == DEFAULT_FILL_MODEL:
        return {
            "is_fill_eligible": 1.0,
            "touch_depth": 1.0,
            "queue_priority": 1.0,
            "fill_probability": 1.0,
            "random_draw": float("nan"),
            "scale_capacity_by_probability": 0.0,
        }

    touch_depth = _touch_depth(row)
    queue_priority = _queue_priority(resolved_style, fill_config)
    fill_probability = max(0.0, min(1.0, touch_depth * queue_priority))
    random_draw = rng.random() if fill_model == STOCHASTIC_QUEUE_FILL_MODEL else float("nan")
    is_fill_eligible = 1.0
    if fill_model == STOCHASTIC_QUEUE_FILL_MODEL and random_draw > fill_probability:
        is_fill_eligible = 0.0

    return {
        "is_fill_eligible": is_fill_eligible,
        "touch_depth": touch_depth,
        "queue_priority": queue_priority,
        "fill_probability": fill_probability,
        "random_draw": random_draw,
        "scale_capacity_by_probability": 1.0 if fill_model == QUEUE_WEIGHTED_FILL_MODEL else 0.0,
    }


def _filled_quantity(
    row: pd.Series,
    submitted_quantity: float,
    fill_context: dict[str, float],
    fill_config: FillModelConfig,
) -> float:
    """Return simulated filled quantity for one placed child order."""
    if submitted_quantity <= 0:
        return 0.0

    resolved_style = str(row["resolved_placement_style"])
    if resolved_style in {"market", "marketable_limit"}:
        return submitted_quantity

    if fill_context["is_fill_eligible"] <= 0:
        return 0.0

    participation_cap = float(row.get("participation_cap", 0.10))
    volume = float(row["volume"])
    if volume <= 0:
        return 0.0

    capacity_multiplier = fill_config.capacity_multipliers.get(
        resolved_style,
        fill_config.default_capacity_multiplier,
    )
    fill_capacity = participation_cap * volume * capacity_multiplier
    if fill_context["scale_capacity_by_probability"] > 0:
        fill_capacity *= fill_context["fill_probability"]
    return float(min(submitted_quantity, fill_capacity))


def _bar_touches_limit(row: pd.Series) -> bool:
    """Return whether an OHLCV bar touches a child order's limit price."""
    side = str(row["side"]).lower()
    limit_price = float(row["limit_price"])
    if side == "buy":
        return float(row["low"]) <= limit_price
    if side == "sell":
        return float(row["high"]) >= limit_price
    raise ValueError(f"Unsupported side: {side!r}.")


def _touch_depth(row: pd.Series) -> float:
    """Return how deeply the bar traded through the limit price."""
    high = float(row["high"])
    low = float(row["low"])
    limit_price = float(row["limit_price"])
    bar_range = high - low
    if bar_range <= 0:
        return 1.0

    side = str(row["side"]).lower()
    if side == "buy":
        raw_depth = (limit_price - low) / bar_range
    elif side == "sell":
        raw_depth = (high - limit_price) / bar_range
    else:
        raise ValueError(f"Unsupported side: {side!r}.")
    return float(max(0.0, min(1.0, raw_depth)))


def _queue_priority(resolved_style: str, fill_config: FillModelConfig) -> float:
    """Return a deterministic queue priority proxy for one placement style."""
    return fill_config.queue_priorities.get(
        resolved_style,
        fill_config.default_queue_priority,
    )


def _simulated_fill_price(row: pd.Series, temporary_impact: float) -> float:
    """Return fill price using placement-specific execution assumptions."""
    resolved_style = str(row["resolved_placement_style"])
    if resolved_style == "market":
        return fill_price_for_child_order(
            side=str(row["side"]),
            synthetic_bid=float(row["synthetic_bid"]),
            synthetic_ask=float(row["synthetic_ask"]),
            temporary_impact=temporary_impact,
        )

    limit_price = float(row["limit_price"])
    side = str(row["side"]).lower()
    if side == "buy":
        return float(limit_price + temporary_impact)
    if side == "sell":
        return float(limit_price - temporary_impact)
    raise ValueError(f"Unsupported side: {side!r}.")


def _spread_cost(row: pd.Series, fill_price: float) -> float:
    """Return signed execution spread cost versus synthetic mid."""
    side = str(row["side"]).lower()
    mid = float(row["mid_price"])
    resolved_style = str(row["resolved_placement_style"])

    if resolved_style == "market":
        limit_or_quote = (
            float(row["synthetic_ask"])
            if side == "buy"
            else float(row["synthetic_bid"])
        )
    else:
        limit_or_quote = float(row["limit_price"])

    if side == "buy":
        return float(max(limit_or_quote - mid, 0.0))
    if side == "sell":
        return float(max(mid - limit_or_quote, 0.0))
    raise ValueError(f"Unsupported side: {side!r}.")
