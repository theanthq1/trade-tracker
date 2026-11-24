"""Versioned SQLite migrations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from database import ensure_trade_schema


LATEST_VERSION = 5


def _migration_001_initial_schema(connection: sqlite3.Connection) -> None:
    ensure_trade_schema(connection)


def _migration_002_add_market_levels(connection: sqlite3.Connection) -> None:
    ensure_trade_schema(connection)


def _migration_003_legacy(connection: sqlite3.Connection) -> None:
    # Retained as a no-op so existing databases can advance through the
    # historical migration sequence after chart storage was removed.
    return None


def _migration_004_add_session_reference_prices(connection: sqlite3.Connection) -> None:
    ensure_trade_schema(connection)


def _migration_005_market_data_snapshots(connection: sqlite3.Connection) -> None:
    """Add immutable, provider-neutral market-data snapshots."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_data_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            provider TEXT NOT NULL,
            data_type TEXT NOT NULL,
            resolution TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            raw_response TEXT,
            error_message TEXT,
            coverage_note TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (trade_id) REFERENCES trades(id)
        );

        CREATE TABLE IF NOT EXISTS market_data_candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            candle_time TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL,
            FOREIGN KEY (snapshot_id) REFERENCES market_data_snapshots(id) ON DELETE CASCADE,
            UNIQUE(snapshot_id, candle_time)
        );

        CREATE INDEX IF NOT EXISTS idx_market_data_snapshot_lookup
        ON market_data_snapshots(
            trade_id, symbol, trade_date, provider, data_type,
            resolution, start_time, end_time, status, is_active
        );
        CREATE INDEX IF NOT EXISTS idx_market_data_candles_snapshot
        ON market_data_candles(snapshot_id, candle_time);
        """
    )


MIGRATIONS = {
    1: _migration_001_initial_schema,
    2: _migration_002_add_market_levels,
    3: _migration_003_legacy,
    4: _migration_004_add_session_reference_prices,
    5: _migration_005_market_data_snapshots,
}


def run_migrations(connection: sqlite3.Connection) -> int:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    current = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
    for version in range(current + 1, LATEST_VERSION + 1):
        MIGRATIONS[version](connection)
        connection.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    return LATEST_VERSION


def initialize_database(connection: sqlite3.Connection) -> int:
    return run_migrations(connection)
