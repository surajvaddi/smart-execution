"""Parent and child order domain objects and parent-order generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd


VALID_SIDES = {"buy", "sell"}

DEFAULT_ORDER_SIZE_FRACTIONS = [0.01, 0.05, 0.10]
DEFAULT_EXECUTION_WINDOWS = [
    ("10:00", "15:30"),
    ("10:00", "12:00"),
    ("13:00", "15:30"),
]
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
    date: object | None = None
    order_id: str | None = None

    def __post_init__(self) -> None:
        """Validate parent order fields at construction time."""
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
    return pd.to_datetime(value).time()


def average_daily_volume(data: pd.DataFrame) -> pd.Series:
    """Return average daily share volume by ticker."""
    required = ["ticker", "date", "volume"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required ADV columns: {missing}")

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

    bar_times = data["time"].map(parse_time)
    return data[(bar_times >= start) & (bar_times <= end)]


def generate_parent_orders(
    data: pd.DataFrame,
    sides: list[str] | None = None,
    order_size_fractions: list[float] | None = None,
    execution_windows: list[tuple[str | time, str | time]] | None = None,
    participation_cap: float = DEFAULT_PARTICIPATION_CAP,
    max_orders_per_ticker: int | None = 20,
) -> list[ParentOrder]:
    """Generate parent orders from available ticker/date market data."""
    required = ["ticker", "date", "time", "volume"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required parent-order generation columns: {missing}")

    sides = sides or ["buy", "sell"]
    order_size_fractions = order_size_fractions or DEFAULT_ORDER_SIZE_FRACTIONS
    execution_windows = execution_windows or DEFAULT_EXECUTION_WINDOWS

    orders: list[ParentOrder] = []
    adv = average_daily_volume(data)
    sorted_data = data.sort_index()

    for ticker, ticker_data in sorted_data.groupby("ticker"):
        ticker_orders: list[ParentOrder] = []
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
                        window_data = filter_execution_window(date_data, start, end)
                        if window_data.empty:
                            continue

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
