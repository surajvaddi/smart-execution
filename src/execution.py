"""Parent and child order domain objects and parent-order generation helpers.

Phase 4 creates the simulated demand that execution strategies must satisfy.
Nothing in this module decides *how* to trade; it only defines *what* needs to
be traded: ticker, side, size, time window, and participation cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd


VALID_SIDES = {"buy", "sell"}

# Order sizes are expressed as fractions of average daily volume. This keeps
# simulations comparable across symbols with different liquidity profiles.
DEFAULT_ORDER_SIZE_FRACTIONS = [0.01, 0.05, 0.10]

# Execution windows are written in New York market time. The data loader
# converts Yahoo timestamps into this timezone before creating the `time` column.
DEFAULT_EXECUTION_WINDOWS = [
    ("10:00", "15:30"),
    ("10:00", "12:00"),
    ("13:00", "15:30"),
]

# A 10% cap means a strategy should not trade more than 10% of the market volume
# available in a bar. Strategy code enforces the cap when it creates child orders.
DEFAULT_PARTICIPATION_CAP = 0.10


@dataclass(frozen=True)
class ParentOrder:
    """Large order to execute over a fixed intraday window."""

    # Parent orders describe intent. Strategy classes will convert them into
    # timestamped child orders while respecting remaining quantity and the
    # participation cap.
    ticker: str
    side: str
    quantity: float
    start_time: time
    end_time: time
    participation_cap: float

    # `date` and `order_id` are optional metadata for research bookkeeping. They
    # make it possible to compare multiple strategies on exactly the same parent
    # order later in the backtest.
    date: object | None = None
    order_id: str | None = None

    def __post_init__(self) -> None:
        """Validate parent order fields at construction time."""
        # Normalize side once so downstream strategy and TCA logic can compare
        # against lowercase strings without repeating case handling.
        side = self.side.lower()
        if side not in VALID_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_SIDES)}, got {self.side!r}.")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive.")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time.")
        if not 0 < self.participation_cap <= 1:
            raise ValueError("participation_cap must be in the interval (0, 1].")

        object.__setattr__(self, "side", side)


def parse_time(value: str | time) -> time:
    """Parse HH:MM strings into `datetime.time` objects."""
    if isinstance(value, time):
        return value
    # CSV round-trips store Python `time` objects as strings such as "10:00:00".
    # Pandas handles both "10:00" and "10:00:00" reliably here.
    return pd.to_datetime(value).time()


def average_daily_volume(data: pd.DataFrame) -> pd.Series:
    """Return average daily share volume by ticker."""
    required = ["ticker", "date", "volume"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required ADV columns: {missing}")

    # Algorithm:
    # 1. Sum intraday bar volume into one total per ticker/date.
    # 2. Average those daily totals by ticker.
    # The result is used to scale parent orders by liquidity.
    daily_volume = data.groupby(["ticker", "date"])["volume"].sum()
    return daily_volume.groupby("ticker").mean()


def order_quantity_from_adv(data: pd.DataFrame, ticker: str, adv_fraction: float) -> float:
    """Convert an ADV fraction into a parent order share quantity."""
    if adv_fraction <= 0:
        raise ValueError("adv_fraction must be positive.")

    adv = average_daily_volume(data)
    normalized_ticker = ticker.upper()
    if normalized_ticker not in adv.index:
        raise ValueError(f"No ADV available for ticker {normalized_ticker}.")

    # Example: if SPY ADV is 75,000,000 shares, a 1% order is 750,000 shares.
    return float(adv.loc[normalized_ticker] * adv_fraction)


def filter_execution_window(data: pd.DataFrame, start_time: str | time, end_time: str | time) -> pd.DataFrame:
    """Return market bars inside a requested intraday execution window."""
    required = ["time"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required window columns: {missing}")

    start = parse_time(start_time)
    end = parse_time(end_time)
    if start >= end:
        raise ValueError("start_time must be before end_time.")

    # Convert every bar's time defensively because in-memory data has
    # `datetime.time` objects while CSV-loaded data has strings.
    bar_times = data["time"].map(parse_time)

    # The window is inclusive on both ends. With 5-minute bars, a 10:00-12:00
    # window includes the bars stamped 10:00 and 12:00.
    return data[(bar_times >= start) & (bar_times <= end)]


def generate_parent_orders(
    data: pd.DataFrame,
    sides: list[str] | None = None,
    order_size_fractions: list[float] | None = None,
    execution_windows: list[tuple[str | time, str | time]] | None = None,
    participation_cap: float = DEFAULT_PARTICIPATION_CAP,
    max_orders_per_ticker: int | None = 20,
) -> list[ParentOrder]:
    """Generate parent orders from available ticker/date market data.

    The generation grid is deterministic:

    ticker -> date -> side -> ADV size fraction -> execution window

    This matters because every execution strategy in Phase 5 should receive the
    same parent-order set, so strategy comparisons are apples-to-apples.
    """
    required = ["ticker", "date", "time", "volume"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required parent-order generation columns: {missing}")

    # Defaults match the README assignment: buy/sell directions, 1/5/10% ADV
    # order sizes, and three intraday execution windows.
    sides = sides or ["buy", "sell"]
    order_size_fractions = order_size_fractions or DEFAULT_ORDER_SIZE_FRACTIONS
    execution_windows = execution_windows or DEFAULT_EXECUTION_WINDOWS

    orders: list[ParentOrder] = []
    # Compute ADV once up front so all orders for a ticker share the same size
    # reference. This avoids orders changing size from one date to another.
    adv = average_daily_volume(data)
    sorted_data = data.sort_index()

    for ticker, ticker_data in sorted_data.groupby("ticker"):
        ticker_orders: list[ParentOrder] = []

        # Precompute share quantities for this ticker. Each parent order uses an
        # actual share quantity, while the order ID preserves the ADV fraction.
        quantity_by_fraction = {
            fraction: float(adv.loc[ticker] * fraction)
            for fraction in order_size_fractions
        }

        for date_value, date_data in ticker_data.groupby("date"):
            for side in sides:
                for fraction in order_size_fractions:
                    for start_value, end_value in execution_windows:
                        start = parse_time(start_value)
                        end = parse_time(end_value)

                        # Some samples may not contain every requested time
                        # window, especially if timestamps are timezone-shifted
                        # or the day is partial. Skip invalid windows rather
                        # than creating orders with no executable bars.
                        window_data = filter_execution_window(date_data, start, end)
                        if window_data.empty:
                            continue

                        # The order ID encodes every simulation dimension needed
                        # to join fills/results back to the parent order later.
                        order_id = (
                            f"{ticker}_{date_value}_{side}_"
                            f"{int(fraction * 10000):04d}bp_{start:%H%M}_{end:%H%M}"
                        )

                        ticker_orders.append(
                            ParentOrder(
                                ticker=ticker,
                                side=side,
                                quantity=quantity_by_fraction[fraction],
                                start_time=start,
                                end_time=end,
                                participation_cap=participation_cap,
                                date=date_value,
                                order_id=order_id,
                            )
                        )

                        # `max_orders_per_ticker` keeps smoke checks small. The
                        # full backtest can pass None to generate the entire grid.
                        if (
                            max_orders_per_ticker is not None
                            and len(ticker_orders) >= max_orders_per_ticker
                        ):
                            break
                    if max_orders_per_ticker is not None and len(ticker_orders) >= max_orders_per_ticker:
                        break
                if max_orders_per_ticker is not None and len(ticker_orders) >= max_orders_per_ticker:
                    break
            if max_orders_per_ticker is not None and len(ticker_orders) >= max_orders_per_ticker:
                break

        orders.extend(ticker_orders)

    return orders


def parent_orders_to_frame(orders: list[ParentOrder]) -> pd.DataFrame:
    """Convert generated parent orders into a tabular summary."""
    # CSV output is useful for inspecting the simulation grid before strategies
    # begin creating child orders from it.
    return pd.DataFrame(
        [
            {
                "order_id": order.order_id,
                "ticker": order.ticker,
                "date": order.date,
                "side": order.side,
                "quantity": order.quantity,
                "start_time": order.start_time,
                "end_time": order.end_time,
                "participation_cap": order.participation_cap,
            }
            for order in orders
        ]
    )
