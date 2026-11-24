"""Versioned SQLite migrations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from database import ensure_trade_schema


LATEST_VERSION = 4


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


MIGRATIONS = {
    1: _migration_001_initial_schema,
    2: _migration_002_add_market_levels,
    3: _migration_003_legacy,
    4: _migration_004_add_session_reference_prices,
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
