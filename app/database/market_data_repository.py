"""Provider-neutral persistent market-data snapshot repository."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

UTC = timezone.utc


@dataclass(frozen=True)
class MarketDataRequest:
    trade_id: int
    symbol: str
    trade_date: str
    provider: str
    data_type: str
    resolution: str
    start_time: datetime
    end_time: datetime

    @property
    def start_key(self) -> str:
        return as_utc(self.start_time).isoformat()

    @property
    def end_key(self) -> str:
        return as_utc(self.end_time).isoformat()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Market-data timestamps must be timezone-aware.")
    return value.astimezone(UTC)


class MarketDataRepository:
    """Stores immutable snapshots and decides cache-vs-fetch.

    The repository accepts a callable returning normalized records. It does
    not import, identify, or call any market-data provider.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)

    def load_or_fetch(
        self,
        request: MarketDataRequest,
        fetcher: Callable[[], Iterable[dict]],
        force_refresh: bool = False,
    ) -> dict:
        if not force_refresh:
            cached = self._load_active_complete(request)
            if cached is not None:
                return cached

        snapshot_id = self._create_pending(request)
        try:
            returned = list(fetcher())
            candles, coverage_note = validate_candles(returned, request)
            return self._save_complete(request, snapshot_id, candles, coverage_note)
        except Exception as error:
            message = safe_error_message(error)
            self._mark_failed(snapshot_id, message)
            return {
                "status": "Provider request failed",
                "provider": request.provider,
                "snapshot_id": snapshot_id,
                "fetched_at": utc_now().isoformat(),
                "error_message": message,
                "candles": [],
                "request": request,
            }

    def get_snapshot_details(self, snapshot_id: int) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM market_data_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_snapshot(self, snapshot_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM market_data_snapshots WHERE id = ?", (snapshot_id,))

    def _load_active_complete(self, request: MarketDataRequest) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM market_data_snapshots
                WHERE trade_id = ? AND symbol = ? AND trade_date = ?
                  AND provider = ? AND data_type = ? AND resolution = ?
                  AND start_time = ? AND end_time = ?
                  AND status = 'complete' AND is_active = 1
                ORDER BY id DESC LIMIT 1
                """,
                (
                    request.trade_id, request.symbol, request.trade_date,
                    request.provider, request.data_type, request.resolution,
                    request.start_key, request.end_key,
                ),
            ).fetchone()
            if row is None:
                return None
            candle_rows = connection.execute(
                """
                SELECT symbol, candle_time, open, high, low, close, volume
                FROM market_data_candles
                WHERE snapshot_id = ? ORDER BY candle_time
                """,
                (row["id"],),
            ).fetchall()
        try:
            candles, _ = validate_candles([dict(item) for item in candle_rows], request)
        except ValueError as error:
            self._mark_failed(row["id"], f"Cached data failed validation: {error}")
            return None
        if not candles:
            self._mark_failed(row["id"], "Cached snapshot contains no candles.")
            return None
        return {
            "status": "Loaded from saved data",
            "provider": row["provider"],
            "snapshot_id": row["id"],
            "fetched_at": row["fetched_at"],
            "coverage_note": row["coverage_note"],
            "candles": candles,
            "request": request,
        }

    def _create_pending(self, request: MarketDataRequest) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO market_data_snapshots(
                    trade_id, symbol, trade_date, provider, data_type,
                    resolution, start_time, end_time, fetched_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    request.trade_id, request.symbol, request.trade_date,
                    request.provider, request.data_type, request.resolution,
                    request.start_key, request.end_key, utc_now().isoformat(),
                ),
            )
            return cursor.lastrowid

    def _save_complete(self, request, snapshot_id, candles, coverage_note):
        fetched_at = utc_now().isoformat()
        raw_response = json.dumps({"normalized_records": [serialize_candle(candle) for candle in candles]})
        with self._connection() as connection:
            connection.execute(
                "UPDATE market_data_snapshots SET is_active = 0 WHERE trade_id = ? AND symbol = ? AND trade_date = ? AND provider = ? AND data_type = ? AND resolution = ? AND start_time = ? AND end_time = ?",
                (
                    request.trade_id, request.symbol, request.trade_date,
                    request.provider, request.data_type, request.resolution,
                    request.start_key, request.end_key,
                ),
            )
            connection.executemany(
                """
                INSERT INTO market_data_candles(
                    snapshot_id, symbol, candle_time, open, high, low, close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_id, candle["symbol"], candle["time"].isoformat(), candle["open"],
                        candle["high"], candle["low"], candle["close"], candle.get("volume"),
                    ) for candle in candles
                ],
            )
            connection.execute(
                """
                UPDATE market_data_snapshots
                SET fetched_at = ?, status = 'complete', raw_response = ?,
                    coverage_note = ?, error_message = NULL, is_active = 1
                WHERE id = ?
                """,
                (fetched_at, raw_response, coverage_note, snapshot_id),
            )
        return {
            "status": "Downloaded and saved",
            "provider": request.provider,
            "snapshot_id": snapshot_id,
            "fetched_at": fetched_at,
            "coverage_note": coverage_note,
            "candles": candles,
            "request": request,
        }

    def _mark_failed(self, snapshot_id, message):
        with self._connection() as connection:
            connection.execute(
                "UPDATE market_data_snapshots SET status = 'failed', error_message = ?, is_active = 0 WHERE id = ?",
                (message, snapshot_id),
            )

    def _connection(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection


def validate_candles(records: Iterable[dict], request: MarketDataRequest) -> tuple[list[dict], str]:
    normalized = []
    seen = set()
    requested_symbol = request.symbol.upper()
    for record in records:
        symbol = str(record.get("symbol") or requested_symbol).upper()
        if symbol != requested_symbol:
            raise ValueError("Returned symbol does not match the requested trade.")
        raw_time = record.get("time", record.get("timestamp", record.get("candle_time")))
        timestamp = parse_time(raw_time)
        if timestamp in seen:
            raise ValueError(f"Duplicate candle timestamp: {timestamp}")
        seen.add(timestamp)
        values = {key: record.get(key) for key in ("open", "high", "low", "close")}
        if any(value is None or not math.isfinite(float(value)) for value in values.values()):
            raise ValueError("OHLC values must be numeric.")
        open_, high, low, close = (float(values[key]) for key in ("open", "high", "low", "close"))
        if high < max(open_, low, close) or low > min(open_, high, close):
            raise ValueError("OHLC high/low bounds are invalid.")
        volume = record.get("volume")
        if volume is not None and not math.isfinite(float(volume)):
            raise ValueError("Volume must be numeric.")
        normalized.append({
            "provider": request.provider,
            "symbol": symbol,
            "time": timestamp,
            "open": open_, "high": high, "low": low, "close": close,
            "volume": float(volume) if volume is not None else 0.0,
        })
    if not normalized:
        raise ValueError("Provider returned no market data.")
    normalized.sort(key=lambda item: item["time"])
    start, end = as_utc(request.start_time), as_utc(request.end_time)
    if normalized[0]["time"] > end or normalized[-1]["time"] < start:
        raise ValueError("Returned data does not overlap the requested time range.")
    coverage = (
        f"Returned {normalized[0]['time'].isoformat()} through "
        f"{normalized[-1]['time'].isoformat()} for requested range "
        f"{start.isoformat()} through {end.isoformat()}."
    )
    return normalized, coverage


def parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return as_utc(value)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return as_utc(parsed)


def serialize_candle(candle):
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in candle.items()}


def utc_now():
    return datetime.now(UTC)


def safe_error_message(error: Exception) -> str:
    message = str(error)
    for secret_name in ("MASSIVE_API_KEY", "apiKey", "Authorization"):
        if secret_name in message:
            return "Provider request failed without exposing credential details."
    return message[:500] or error.__class__.__name__
