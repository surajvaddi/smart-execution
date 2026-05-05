"""Parent and child order domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class ParentOrder:
    """Large order to execute over a fixed intraday window."""

    ticker: str
    side: str
    quantity: float
    start_time: time
    end_time: time
    participation_cap: float
