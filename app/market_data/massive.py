"""Read-only Massive market-data client for historical trade charts."""

from __future__ import annotations

import json
import os
from datetime import datetime, time as dt_time, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.config import load_environment

EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
MASSIVE_API_URL = "https://api.massive.com"
# The Stocks Basic (free) plan includes historical aggregate bars, but serves
# them end-of-day and only for the most recent two years.
FREE_PLAN_HISTORY = timedelta(days=366 * 2 + 1)


class MassiveDataError(RuntimeError):
    """Raised when Massive cannot provide chart data."""


class MassiveClient:
    def __init__(self, timeout: int = 30, api_key: str | None = None):
        load_environment()
        self.timeout = timeout
        self.api_key = api_key

    def get_first_hour_candles(self, symbol: str, trade_date: str) -> list[dict]:
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise MassiveDataError("A stock ticker is required for chart data.")
        try:
            day = datetime.strptime(trade_date, "%Y-%m-%d").date()
        except (TypeError, ValueError) as error:
            raise MassiveDataError("A valid trade date is required for chart data.") from error

        self._validate_free_plan_date(day)

        start = datetime.combine(day, dt_time(4, 0), tzinfo=EASTERN)
        end = datetime.combine(day, dt_time(10, 31), tzinfo=EASTERN)
        path = (
            f"/v2/aggs/ticker/{symbol}/range/1/minute/"
            f"{int(start.timestamp() * 1000)}/{int(end.timestamp() * 1000)}"
        )
        payload = self._get(path, {
            "adjusted": "false",
            "sort": "asc",
            "limit": "50000",
        })
        if str(payload.get("status", "")).upper() not in {"OK", "SUCCESS"}:
            raise MassiveDataError(payload.get("error") or "Massive returned an unsuccessful response.")

        candles = []
        for item in payload.get("results") or []:
            timestamp = item.get("t")
            if timestamp is None:
                continue
            candle_time = datetime.fromtimestamp(float(timestamp) / 1000, tz=UTC)
            candles.append({
                "provider": "Massive",
                "time": candle_time,
                "open": float(item["o"]),
                "high": float(item["h"]),
                "low": float(item["l"]),
                "close": float(item["c"]),
                "volume": float(item.get("v") or 0),
            })
        if not candles:
            raise MassiveDataError(f"Massive returned no candles for {symbol} on {trade_date}.")
        return candles

    def get_historical_bars(self, symbol, start, end, interval):
        if interval not in {"1m", "1min", "minute"}:
            raise MassiveDataError("Massive provider currently supports one-minute bars for charts.")
        start = self._as_datetime(start)
        end = self._as_datetime(end)
        self._validate_free_plan_date(start.astimezone(EASTERN).date())
        if end.astimezone(EASTERN).date() != start.astimezone(EASTERN).date():
            raise MassiveDataError("Massive free-plan chart requests must stay within one completed trading day.")
        payload = self._get(
            f"/v2/aggs/ticker/{symbol.upper()}/range/1/minute/"
            f"{int(start.timestamp() * 1000)}/{int(end.timestamp() * 1000)}",
            {"adjusted": "false", "sort": "asc", "limit": "50000"},
        )
        return self._normalize_results(payload)

    @staticmethod
    def _validate_free_plan_date(requested_day):
        """Prevent a Basic-plan 403 before sending an ineligible request.

        Massive's free Stocks Basic plan has minute aggregates, but its data
        recency is end-of-day. A trading date becomes available just after
        midnight Eastern, so the current Eastern date must not be requested.
        """
        today = MassiveClient._free_plan_today()
        if requested_day >= today:
            raise MassiveDataError(
                "Massive's free Stocks Basic plan provides chart data after "
                "midnight ET. The selected trade date is not available yet."
            )
        if requested_day < today - FREE_PLAN_HISTORY:
            raise MassiveDataError(
                "The selected trade date is outside Massive's free Stocks Basic "
                "plan history window (two years)."
            )

    @staticmethod
    def _free_plan_today():
        return datetime.now(EASTERN).date()

    def get_historical_trades(self, symbol, start, end):
        raise MassiveDataError("Massive tick trades require a plan with historical trade access.")

    def get_historical_quotes(self, symbol, start, end):
        raise MassiveDataError("Massive historical quotes require a plan with quote access.")

    def get_atr14(self, symbol, end_date=None):
        end_day = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        start_day = end_day - timedelta(days=75)
        payload = self._get(
            f"/v2/aggs/ticker/{symbol.upper()}/range/1/day/"
            f"{start_day.date().isoformat()}/{end_day.date().isoformat()}",
            {"adjusted": "false", "sort": "asc", "limit": "5000"},
        )
        bars = self._normalize_results(payload)
        if len(bars) < 15:
            raise MassiveDataError(f"Not enough daily data to calculate ATR(14) for {symbol.upper()}.")
        ranges = []
        for current, previous in zip(bars[1:], bars[:-1]):
            ranges.append(max(
                current["high"] - current["low"],
                abs(current["high"] - previous["close"]),
                abs(current["low"] - previous["close"]),
            ))
        atr = sum(ranges[:14]) / 14
        for true_range in ranges[14:]:
            atr = (atr * 13 + true_range) / 14
        close = bars[-1]["close"]
        return {"ticker": symbol.upper(), "atr14": atr, "last_close": close,
                "atr_percent": atr / close * 100 if close else 0.0,
                "days_used": len(ranges)}

    def get_watchlist_statistics(self, symbols):
        """Return current-session range statistics in one batch request.

        Massive's snapshot endpoint accepts multiple stock tickers in a single
        request.  This intentionally returns a one-session range rather than
        calling the historical aggregate endpoint once per symbol.  A true
        ATR(14) requires historical bars and therefore cannot be calculated
        accurately from this one-request batch response.
        """
        requested = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        if not requested:
            raise MassiveDataError("At least one stock ticker is required for watchlist data.")

        payload = self._get("/v3/snapshot", {
            "ticker.any_of": ",".join(requested),
            "type": "stocks",
            "limit": str(len(requested)),
        })
        if str(payload.get("status", "")).upper() not in {"OK", "SUCCESS"}:
            raise MassiveDataError(payload.get("error") or "Massive returned an unsuccessful response.")

        results_by_ticker = {
            str(item.get("ticker", "")).upper(): item
            for item in payload.get("results") or []
            if item.get("ticker")
        }
        rows = []
        errors = []
        for ticker in requested:
            item = results_by_ticker.get(ticker)
            session = (item or {}).get("session") or {}
            try:
                high = float(session["high"])
                low = float(session["low"])
                close = float(session.get("close", session.get("price")))
                if high < low:
                    raise ValueError("session high is below session low")
                daily_range = high - low
                rows.append({
                    "ticker": ticker,
                    "daily_range": daily_range,
                    "range_percent": daily_range / close * 100 if close else 0.0,
                    "last_close": close,
                    "days_used": 1,
                })
            except (KeyError, TypeError, ValueError) as error:
                errors.append(f"{ticker}: Massive returned incomplete snapshot data ({error})")
        return rows, errors

    def _get(self, path: str, params: dict[str, str]) -> dict:
        load_environment()
        api_key = self.api_key or os.environ.get("MASSIVE_API_KEY")
        if not api_key:
            raise MassiveDataError("MASSIVE_API_KEY is not configured.")
        query = dict(params)
        query["apiKey"] = api_key
        url = f"{MASSIVE_API_URL}{path}?{urlencode(query)}"
        request = Request(url, headers={"User-Agent": "TradeTrackerDesktop/1.0"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise MassiveDataError(f"Massive request failed with HTTP {error.code}: {detail[:240]}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise MassiveDataError(f"Massive connection failed: {error}") from error
        except json.JSONDecodeError as error:
            raise MassiveDataError("Massive returned invalid JSON.") from error

    @staticmethod
    def _as_datetime(value):
        if isinstance(value, datetime):
            return value
        raise MassiveDataError("Massive date ranges must be datetime values.")

    @staticmethod
    def _normalize_results(payload):
        if str(payload.get("status", "")).upper() not in {"OK", "SUCCESS"}:
            raise MassiveDataError(payload.get("error") or "Massive returned an unsuccessful response.")
        normalized = []
        for item in payload.get("results") or []:
            if item.get("t") is None:
                continue
            normalized.append({
                "provider": "Massive",
                "time": datetime.fromtimestamp(float(item["t"]) / 1000, tz=UTC),
                "open": float(item["o"]), "high": float(item["h"]),
                "low": float(item["l"]), "close": float(item["c"]),
                "volume": float(item.get("v") or 0),
            })
        return normalized
