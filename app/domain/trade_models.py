from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trade:
    id: int
    ticker_symbol: str | None
    option_type: str | None
    stock_entry: float | None
    option_entry: float | None
    stock_exit: float | None
    option_exit: float | None
    option_entry_typed_at: datetime | None = None
    option_exit_typed_at: datetime | None = None


@dataclass(frozen=True)
class MarketContext:
    premarket_high: float | None = None
    premarket_low: float | None = None
    regular_session_open: float | None = None
    previous_day_open: float | None = None
    previous_day_high: float | None = None
    previous_day_low: float | None = None
