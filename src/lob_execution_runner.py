"""Minimal parent-order execution runner for the synthetic LOB path."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.execution import ParentOrder
from src.lob_execution import (
    build_child_execution_report,
    create_child_order_state,
    place_aggressive_child_order,
    place_midpoint_child_order,
    place_passive_child_order,
    submit_execution_child_order,
)
from src.lob_simulator import LobSimulationResult
from src.lob_types import BookSnapshot, TradePrint


REQUIRED_SCHEDULE_COLUMNS = ["timestamp", "quantity", "reference_price"]


@dataclass(frozen=True)
class LobParentExecutionResult:
    """Normalized outputs from running one parent-order schedule on the LOB."""

    final_snapshot: BookSnapshot
    execution_reports: pd.DataFrame
    trade_prints: pd.DataFrame
    child_states: list[object]


def execute_parent_order_on_lob(
    parent_order: ParentOrder,
    child_orders: pd.DataFrame,
    initial_book: BookSnapshot,
    placement_style: str = "market",
) -> LobParentExecutionResult:
    """Execute a child-order schedule against one mutable LOB state."""
    _validate_schedule(child_orders)

    book = initial_book
    reports = []
    trade_prints: list[TradePrint] = []
    child_states = []

    ordered_children = child_orders.sort_values("timestamp").reset_index(drop=True)
    for child_index, row in ordered_children.iterrows():
        submitted_at = row["timestamp"]
        state = create_child_order_state(
            child_order_id=f"{parent_order.order_id or 'parent'}_child_{child_index:03d}",
            parent_order_id=parent_order.order_id or "parent_order",
            instrument_id=initial_book.instrument_id,
            side=parent_order.side,
            quantity=float(row["quantity"]),
            submitted_at=submitted_at,
            placement_style=placement_style,
        )
        book, updated_state, prints = _submit_child_by_style(
            book,
            state,
            reference_price=float(row["reference_price"]),
        )
        child_states.append(updated_state)
        trade_prints.extend(prints)
        reports.append(
            build_child_execution_report(
                state,
                updated_state,
                prints,
                timestamp=submitted_at,
            )
        )

    return LobParentExecutionResult(
        final_snapshot=book,
        execution_reports=pd.DataFrame([report.__dict__ for report in reports]),
        trade_prints=pd.DataFrame([print_.__dict__ for print_ in trade_prints]),
        child_states=child_states,
    )


def run_schedule_against_lob_episode(
    parent_order: ParentOrder,
    child_orders: pd.DataFrame,
    episode: LobSimulationResult,
    placement_style: str = "market",
) -> LobParentExecutionResult:
    """Execute a schedule against the opening book state from one LOB episode."""
    if not episode.snapshots:
        raise ValueError("episode must contain at least one opening snapshot.")
    return execute_parent_order_on_lob(
        parent_order,
        child_orders,
        initial_book=episode.snapshots[0],
        placement_style=placement_style,
    )


def _submit_child_by_style(
    book: BookSnapshot,
    state,
    reference_price: float,
) -> tuple[BookSnapshot, object, list[TradePrint]]:
    """Route child orders to the requested LOB placement style."""
    if state.placement_style == "passive_limit":
        return place_passive_child_order(book, state)
    if state.placement_style == "aggressive_limit":
        return place_aggressive_child_order(book, state)
    if state.placement_style == "midpoint_limit":
        return place_midpoint_child_order(book, state)
    return submit_execution_child_order(book, state, price=reference_price)


def _validate_schedule(child_orders: pd.DataFrame) -> None:
    """Validate the minimal child-order schedule schema used by the LOB runner."""
    missing = [column for column in REQUIRED_SCHEDULE_COLUMNS if column not in child_orders.columns]
    if missing:
        raise ValueError(f"Missing required LOB schedule columns: {missing}")
    if child_orders.empty:
        raise ValueError("child_orders must contain at least one row.")
    if (child_orders["quantity"] <= 0).any():
        raise ValueError("child order quantities must be positive.")
    if child_orders["timestamp"].isna().any():
        raise ValueError("child orders must provide timestamps.")
