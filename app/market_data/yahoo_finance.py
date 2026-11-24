"""Yahoo Finance chart-data adapter used behind the local TradingView UDF API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, time as dt_time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooFinanceError(RuntimeError):
    pass


class YahooFinanceClient:
    """Fetch one-minute Yahoo Finance candles for a selected trade date."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_atr14(self, symbol: str, end_date: str | None = None) -> dict:
        """Return daily Wilder ATR(14) and related values for ``symbol``."""
        if not symbol:
            raise YahooFinanceError("A stock ticker is required for ATR data.")
        end_dt = (
            datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
            if end_date else datetime.now(UTC)
        )
        start_dt = end_dt - timedelta(days=75)
        query = urlencode({
            "period1": int(start_dt.timestamp()),
            "period2": int((end_dt + timedelta(days=1)).timestamp()),
            "interval": "1d",
            "includePrePost": "false",
            "events": "div,splits",
        })
        url = YAHOO_CHART_URL.format(symbol=quote(symbol.upper(), safe="")) + "?" + query
        request = Request(url, headers={"User-Agent": "TradeTrackerDesktop/1.0"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise YahooFinanceError(f"Yahoo Finance request failed with HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise YahooFinanceError(f"Yahoo Finance connection failed: {error}") from error
        except json.JSONDecodeError as error:
            raise YahooFinanceError("Yahoo Finance returned invalid JSON.") from error

        chart = payload.get("chart") or {}
        if chart.get("error"):
            description = chart["error"].get("description") or "Unknown Yahoo Finance error"
            raise YahooFinanceError(str(description))
        result = (chart.get("result") or [None])[0]
        if not result:
            raise YahooFinanceError(f"No daily data was returned for {symbol.upper()}.")
        timestamps = result.get("timestamp") or []
        quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        bars = []
        for index, timestamp in enumerate(timestamps):
            values = {
                key: (quote_data.get(key) or [None] * len(timestamps))[index]
                for key in ("high", "low", "close")
            }
            if any(value is None for value in values.values()):
                continue
            bars.append({key: float(value) for key, value in values.items()})
        if len(bars) < 15:
            raise YahooFinanceError(f"Not enough daily data to calculate ATR(14) for {symbol.upper()}.")

        true_ranges = []
        for current, previous in zip(bars[1:], bars[:-1]):
            true_ranges.append(max(
                current["high"] - current["low"],
                abs(current["high"] - previous["close"]),
                abs(current["low"] - previous["close"]),
            ))
        atr = sum(true_ranges[:14]) / 14
        for true_range in true_ranges[14:]:
            atr = (atr * 13 + true_range) / 14
        last_close = bars[-1]["close"]
        return {
            "ticker": symbol.upper(),
            "atr14": atr,
            "last_close": last_close,
            "atr_percent": (atr / last_close * 100) if last_close else 0.0,
            "days_used": len(true_ranges),
        }

    def get_one_minute_bars(self, symbol: str, trade_date: str, start: datetime, end: datetime) -> list[dict]:
        if not symbol:
            raise YahooFinanceError("A stock ticker is required for Yahoo Finance data.")
        period1 = int(start.astimezone(UTC).timestamp())
        # Yahoo's period2 is exclusive; add one minute to retain the 10:30 bar.
        period2 = int(end.astimezone(UTC).timestamp()) + 60
        query = urlencode({
            "period1": period1,
            "period2": period2,
            "interval": "1m",
            # Yahoo labels premarket candles as pre/post-market data.
            "includePrePost": "true",
            "events": "div,splits",
        })
        url = YAHOO_CHART_URL.format(symbol=quote(symbol.upper(), safe="")) + "?" + query
        request = Request(url, headers={"User-Agent": "TradeTrackerDesktop/1.0"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise YahooFinanceError(f"Yahoo Finance request failed with HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise YahooFinanceError(f"Yahoo Finance connection failed: {error}") from error
        except json.JSONDecodeError as error:
            raise YahooFinanceError("Yahoo Finance returned invalid JSON.") from error

        chart = (payload.get("chart") or {})
        if chart.get("error"):
            description = chart["error"].get("description") or "Unknown Yahoo Finance error"
            raise YahooFinanceError(str(description))
        result = (chart.get("result") or [None])[0]
        if not result:
            return []
        timestamps = result.get("timestamp") or []
        quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        bars = []
        for index, raw_timestamp in enumerate(timestamps):
            values = {key: (quote_data.get(key) or [None] * len(timestamps))[index] for key in ("open", "high", "low", "close", "volume")}
            if any(values[key] is None for key in ("open", "high", "low", "close")):
                continue
            timestamp = int(raw_timestamp)
            candle_dt = datetime.fromtimestamp(timestamp, tz=UTC).astimezone(EASTERN)
            if candle_dt.date().isoformat() != trade_date:
                continue
            if not (dt_time(4, 0) <= candle_dt.time() <= dt_time(10, 30)):
                continue
            bars.append({
                "time": timestamp,
                "open": float(values["open"]),
                "high": float(values["high"]),
                "low": float(values["low"]),
                "close": float(values["close"]),
                "volume": int(values["volume"] or 0),
            })
        return bars
