"""Execution strategy implementations.

Phase 5 converts parent orders into timestamped child orders. This module starts
with shared helpers so TWAP, VWAP, POV, and Adaptive all emit the same schema.
"""

from __future__ import annotations

import pandas as pd

from src.execution import ParentOrder, filter_execution_window
from src.features import estimate_volume_curve


CHILD_ORDER_COLUMNS = [
    "timestamp",
    "ticker",
    "side",
    "strategy",
    "quantity",
    "reference_price",
]


def validate_child_orders(child_orders: pd.DataFrame) -> None:
    """Validate the common child-order output schema."""
    missing = [col for col in CHILD_ORDER_COLUMNS if col not in child_orders.columns]
    if missing:
        raise ValueError(f"Missing required child-order columns: {missing}")

    if child_orders.empty:
        return

    if (child_orders["quantity"] <= 0).any():
        raise ValueError("Child order quantities must be positive.")
    if child_orders["reference_price"].isna().any():
        raise ValueError("Child orders must have reference prices.")


class ExecutionStrategy:
    """Base interface for child-order generation."""

    name = "base"

    def market_window(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Return rows matching a parent order's ticker, date, and time window."""
        required = ["ticker", "date", "time", "close"]
        missing = [col for col in required if col not in data.columns]
        if missing:
            raise ValueError(f"Missing required strategy data columns: {missing}")

        ticker_data = data[data["ticker"] == order.ticker]
        if order.date is not None:
            ticker_data = ticker_data[ticker_data["date"] == order.date]

        window = filter_execution_window(ticker_data, order.start_time, order.end_time)
        if window.empty:
            raise ValueError(f"No market data available for parent order {order.order_id}.")

        return window.sort_index()

    def child_order_frame(
        self,
        order: ParentOrder,
        timestamps: pd.Index,
        quantities: list[float],
        reference_prices: list[float],
    ) -> pd.DataFrame:
        """Build and validate a child-order DataFrame for one parent order."""
        child_orders = pd.DataFrame(
            {
                "timestamp": timestamps,
                "ticker": order.ticker,
                "side": order.side,
                "strategy": self.name,
                "quantity": quantities,
                "reference_price": reference_prices,
            }
        )
        validate_child_orders(child_orders)
        return child_orders[CHILD_ORDER_COLUMNS]

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate child orders for a parent order and market data window."""
        # Concrete strategies will return one row per child order with timestamp,
        # ticker, side, strategy, quantity, and reference price.
        raise NotImplementedError


class TWAPStrategy(ExecutionStrategy):
    # Evenly allocates quantity across time bars.
    name = "TWAP"

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate an even time-weighted schedule across the execution window."""
        window = self.market_window(order, data)
        n_bars = len(window)
        base_quantity = order.quantity / n_bars
        quantities = [base_quantity] * n_bars

        # Floating point division can leave tiny residuals. Adjust the final
        # child order so the TWAP schedule exactly sums to the parent quantity.
        quantities[-1] += order.quantity - sum(quantities)

        return self.child_order_frame(
            order=order,
            timestamps=window.index,
            quantities=quantities,
            reference_prices=window["close"].tolist(),
        )


class VWAPStrategy(ExecutionStrategy):
    # Allocates quantity using the historical volume curve from Phase 2.
    name = "VWAP"

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate a volume-weighted schedule using the historical volume curve."""
        window = self.market_window(order, data)
        volume_curve = estimate_volume_curve(data)

        expected_shares = window["bar_index"].map(volume_curve).fillna(0.0)
        window_share_total = expected_shares.sum()
        if window_share_total <= 0:
            raise ValueError(f"No positive expected volume shares for parent order {order.order_id}.")

        # Renormalize inside the execution window. The full-day volume curve sums
        # to one, but a parent order may cover only part of the day.
        quantities = (order.quantity * expected_shares / window_share_total).tolist()
        quantities[-1] += order.quantity - sum(quantities)

        return self.child_order_frame(
            order=order,
            timestamps=window.index,
            quantities=quantities,
            reference_prices=window["close"].tolist(),
        )


class POVStrategy(ExecutionStrategy):
    # Trades as a capped percentage of realized market volume.
    name = "POV"

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate a participation-of-volume schedule using realized bar volume."""
        window = self.market_window(order, data)
        remaining_quantity = order.quantity
        timestamps = []
        quantities = []
        reference_prices = []

        for timestamp, row in window.iterrows():
            if remaining_quantity <= 0:
                break

            # POV uses actual bar volume, capped by the parent order's maximum
            # participation rate. This controls footprint but does not guarantee
            # completion when the market is too quiet.
            child_quantity = min(
                remaining_quantity,
                order.participation_cap * row["volume"],
            )
            if child_quantity <= 0:
                continue

            timestamps.append(timestamp)
            quantities.append(float(child_quantity))
            reference_prices.append(float(row["close"]))
            remaining_quantity -= child_quantity

        return self.child_order_frame(
            order=order,
            timestamps=pd.Index(timestamps),
            quantities=quantities,
            reference_prices=reference_prices,
        )


class AdaptiveStrategy(ExecutionStrategy):
    # Adjusts speed using alpha, liquidity, spread, volatility, and urgency.
    name = "Adaptive"
