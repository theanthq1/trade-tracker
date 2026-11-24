"""Small local UDF-compatible HTTP server for the embedded TradingView chart."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, time as dt_time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
LOGGER = logging.getLogger("trade_tracker.tradingview")


class UDFDataService:
    def __init__(self, database_path: str | Path, static_root: str | Path):
        self.database_path = str(database_path)
        self.static_root = Path(static_root).resolve()
        self._trade = None
        self._lock = Lock()
        self.server = None
        self.thread = None

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise RuntimeError("The TradingView UDF server has not started.")
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self) -> None:
        handler = self._handler_type()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = Thread(target=self.server.serve_forever, name="tradingview-udf", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None

    def set_trade(self, trade: dict) -> None:
        required = {
            "id": trade.get("id"),
            "ticker": (trade.get("ticker_symbol") or "").strip().upper(),
            "trade_date": self._trade_date(trade),
            "entry_timestamp": trade.get("option_entry_typed_at"),
            "exit_timestamp": trade.get("option_exit_typed_at"),
            "entry_price": trade.get("stock_entry"),
            "exit_price": trade.get("stock_exit"),
        }
        if required["trade_date"]:
            trade_day = datetime.fromisoformat(required["trade_date"]).date()
            required["from_seconds"] = int(datetime.combine(trade_day, dt_time(9, 30), tzinfo=EASTERN).timestamp())
            required["to_seconds"] = int(datetime.combine(trade_day, dt_time(10, 30), tzinfo=EASTERN).timestamp())
        else:
            required["from_seconds"] = None
            required["to_seconds"] = None
        with self._lock:
            self._trade = required
        LOGGER.info(
            "trade_id=%s ticker=%s trade_date=%s entry_timestamp=%s entry_price=%s exit_timestamp=%s exit_price=%s",
            required["id"], required["ticker"], required["trade_date"],
            required["entry_timestamp"], required["entry_price"],
            required["exit_timestamp"], required["exit_price"],
        )

    def context(self) -> dict:
        with self._lock:
            return dict(self._trade or {})

    def history(self, query: dict[str, list[str]]) -> dict:
        trade = self.context()
        symbol = (query.get("symbol", [""])[0] or "").upper()
        resolution = query.get("resolution", [""])[0]
        trade_date = trade.get("trade_date")
        if not trade or symbol != trade.get("ticker") or resolution != "1" or not trade_date:
            return {"s": "no_data"}

        start = datetime.combine(datetime.fromisoformat(trade_date).date(), dt_time(9, 30), tzinfo=EASTERN)
        end = datetime.combine(datetime.fromisoformat(trade_date).date(), dt_time(10, 30), tzinfo=EASTERN)
        start_seconds = int(start.timestamp())
        end_seconds = int(end.timestamp())
        requested_url = "/udf/history?" + urlencode({key: values[0] for key, values in query.items() if values})
        LOGGER.info(
            "UDF /history URL=%s trade_id=%s ticker=%s trade_date=%s resolution=%s from=%s to=%s",
            requested_url, trade["id"], symbol, trade_date, resolution, start_seconds, end_seconds,
        )

        try:
            with sqlite3.connect(self.database_path) as connection:
                rows = connection.execute(
                    """
                    SELECT candle_time, open, high, low, close, COALESCE(volume, 0)
                    FROM stock_candles
                    WHERE upper(symbol) = ? AND trading_date = ?
                      AND datetime(candle_time) >= datetime(?)
                      AND datetime(candle_time) < datetime(?)
                    ORDER BY datetime(candle_time)
                    """,
                    (symbol, trade_date, start.isoformat(), end.isoformat()),
                ).fetchall()
        except sqlite3.Error as error:
            LOGGER.error("Local candle history failed for trade_id=%s: %s", trade["id"], error)
            return {"s": "error", "errmsg": f"Unable to read local stock_candles data: {error}"}

        normalized = []
        for candle_time, open_, high, low, close, volume in rows:
            parsed = datetime.fromisoformat(str(candle_time))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=EASTERN)
            normalized.append({
                "time": int(parsed.astimezone(UTC).timestamp()),
                "open": float(open_), "high": float(high), "low": float(low),
                "close": float(close), "volume": int(volume or 0),
            })

        LOGGER.info("UDF /history returned %s local regular-session candles", len(normalized))
        if not normalized:
            return {"s": "no_data"}
        return {
            "s": "ok",
            "t": [row["time"] for row in normalized],
            "o": [row["open"] for row in normalized],
            "h": [row["high"] for row in normalized],
            "l": [row["low"] for row in normalized],
            "c": [row["close"] for row in normalized],
            "v": [row["volume"] for row in normalized],
        }

    def _handler_type(self):
        service = self

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(service.static_root), **kwargs)

            def log_message(self, format, *args):
                LOGGER.debug("TradingView static request: " + format, *args)

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/udf/config":
                    return self._json({
                        "supports_search": False,
                        "supports_group_request": False,
                        "supports_marks": False,
                        "supports_timescale_marks": False,
                        "supports_time": True,
                        "supported_resolutions": ["1"],
                    })
                if parsed.path == "/udf/symbols":
                    trade = service.context()
                    symbol = parse_qs(parsed.query).get("symbol", [trade.get("ticker", "")])[0]
                    return self._json({
                        "name": symbol,
                        "ticker": symbol,
                        "description": f"{symbol} stock",
                        "type": "stock",
                        "session": "0930-1030",
                        "timezone": "America/New_York",
                        "exchange": "LOCAL",
                        "minmov": 1,
                        "pricescale": 100,
                        "has_intraday": True,
                        "has_daily": False,
                        "has_empty_bars": False,
                        "supported_resolutions": ["1"],
                    })
                if parsed.path == "/udf/history":
                    return self._json(service.history(parse_qs(parsed.query)))
                if parsed.path == "/udf/context":
                    return self._json(service.context())
                if parsed.path == "/udf/time":
                    return self._json(int(datetime.now(UTC).timestamp()), content_type="text/plain")
                return super().do_GET()

            def _json(self, payload, content_type="application/json"):
                body = json.dumps(payload).encode("utf-8") if content_type != "text/plain" else str(payload).encode("ascii")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    @staticmethod
    def _trade_date(trade: dict) -> str | None:
        timestamp = trade.get("option_entry_typed_at") or trade.get("created_at")
        if not timestamp:
            return None
        parsed = datetime.fromisoformat(str(timestamp))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=EASTERN)
        return parsed.astimezone(EASTERN).date().isoformat()
