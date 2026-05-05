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

        remaining_quantity = order.quantity
        quantities = []

        for bar_number, (_, row) in enumerate(window.iterrows()):
            remaining_bars = len(window) - bar_number
            remaining_expected = expected_shares.iloc[bar_number:].sum()
            if remaining_expected > 0:
                target_quantity = remaining_quantity * expected_shares.iloc[bar_number] / remaining_expected
            else:
                target_quantity = remaining_quantity / remaining_bars

            # VWAP follows the volume curve, but it still must respect the same
            # participation cap as the other execution strategies.
            child_quantity = min(
                remaining_quantity,
                target_quantity,
                order.participation_cap * row["volume"],
            )

            # On the final bar, try to complete the order if the cap allows it.
            if remaining_bars == 1:
                child_quantity = min(remaining_quantity, order.participation_cap * row["volume"])

            quantities.append(float(child_quantity))
            remaining_quantity -= child_quantity

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

    def adaptive_multiplier(self, row: pd.Series, side: str, urgency: float) -> float:
        """Return an execution speed multiplier from signals and conditions."""
        signal = row.get("alpha_signal", 0.0)
        spread = row.get("spread_proxy", 0.0)
        volatility = row.get("rolling_vol", 0.0)
        liquidity = row.get("liquidity_score", 0.0)

        multiplier = 1.0

        # Directional alpha changes speed by side. For buys, bullish signal
        # means trade faster before price rises; for sells, bearish signal means
        # sell faster before price falls.
        if side == "buy":
            if signal > 0:
                multiplier *= 1.4
            elif signal < 0:
                multiplier *= 0.7
        elif side == "sell":
            if signal < 0:
                multiplier *= 1.4
            elif signal > 0:
                multiplier *= 0.7

        # High spread and high volatility make trading more expensive or risky,
        # so slow down unless urgency later pushes the multiplier back up.
        if spread > row.get("spread_proxy_75pct", float("inf")):
            multiplier *= 0.75
        if volatility > row.get("rolling_vol_75pct", float("inf")):
            multiplier *= 0.85

        # High liquidity is the condition where taking more quantity is least
        # likely to create avoidable impact.
        if liquidity > row.get("liquidity_score_75pct", float("inf")):
            multiplier *= 1.2

        multiplier *= urgency
        return float(max(0.25, min(2.5, multiplier)))

    def generate_child_orders(self, order: ParentOrder, data: pd.DataFrame) -> pd.DataFrame:
        """Generate an adaptive schedule using signals, liquidity, and urgency."""
        window = self.market_window(order, data).copy()

        required_features = [
            "alpha_signal",
            "spread_proxy",
            "rolling_vol",
            "liquidity_score",
            "volume",
        ]
        missing = [col for col in required_features if col not in window.columns]
        if missing:
            raise ValueError(f"Missing required adaptive strategy columns: {missing}")

        window["spread_proxy_75pct"] = data["spread_proxy"].quantile(0.75)
        window["rolling_vol_75pct"] = data["rolling_vol"].quantile(0.75)
        window["liquidity_score_75pct"] = data["liquidity_score"].quantile(0.75)

        remaining_quantity = order.quantity
        timestamps = []
        quantities = []
        reference_prices = []

        for bar_number, (timestamp, row) in enumerate(window.iterrows()):
            if remaining_quantity <= 0:
                break

            remaining_bars = len(window) - bar_number
            base_quantity = remaining_quantity / remaining_bars

            target_completed = bar_number / len(window)
            actual_completed = (order.quantity - remaining_quantity) / order.quantity
            urgency = 1.0 + max(0.0, target_completed - actual_completed)

            if remaining_bars == 1:
                # On the final bar, attempt to complete the parent order. The
                # participation cap below still limits the child quantity.
                child_quantity = remaining_quantity
            else:
                child_quantity = base_quantity * self.adaptive_multiplier(row, order.side, urgency)
            child_quantity = min(child_quantity, remaining_quantity)
            child_quantity = min(child_quantity, order.participation_cap * row["volume"])
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
