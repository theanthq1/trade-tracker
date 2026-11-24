"""Canonical SQLite schema helpers for the trade journal."""

from __future__ import annotations

import sqlite3
from pathlib import Path

TRADE_COLUMNS = (
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("stock_entry", "REAL NOT NULL"),
    ("option_entry", "REAL NOT NULL"),
    ("stock_exit", "REAL NOT NULL"),
    ("option_exit", "REAL NOT NULL"),
    ("screenshot", "BLOB"),
    ("created_at", "TEXT NOT NULL"),
    ("ticker_symbol", "TEXT"),
    ("option_type", "TEXT"),
    ("exit_timer_started_at", "TEXT"),
    ("option_entry_typed_at", "TEXT"),
    ("option_exit_typed_at", "TEXT"),
    ("length_of_trade_seconds", "REAL"),
    ("premarket_high", "REAL"),
    ("premarket_low", "REAL"),
    ("regular_session_open", "REAL"),
    ("previous_day_open", "REAL"),
    ("previous_day_high", "REAL"),
    ("previous_day_low", "REAL"),
)


def _create_trades(connection: sqlite3.Connection, table_name: str = "trades") -> None:
    definitions = ",\n                ".join(f"{name} {definition}" for name, definition in TRADE_COLUMNS)
    connection.execute(f"CREATE TABLE {table_name} (\n                {definitions}\n            )")


def ensure_trade_schema(connection: sqlite3.Connection) -> None:
    """Create or safely migrate ``trades`` without losing existing rows."""
    connection.execute("PRAGMA foreign_keys = ON")
    table = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'trades'").fetchone()
    if table is None:
        _create_trades(connection)
        connection.commit()
        return
    existing = {row[1]: row for row in connection.execute("PRAGMA table_info(trades)").fetchall()}
    desired_names = [name for name, _ in TRADE_COLUMNS]
    if "status" not in existing and all(name in existing for name in desired_names):
        return
    old_columns = [name for name in desired_names if name in existing]
    connection.execute("BEGIN")
    try:
        _create_trades(connection, "trades_new")
        if old_columns:
            columns_sql = ", ".join(old_columns)
            connection.execute(f"INSERT INTO trades_new ({columns_sql}) SELECT {columns_sql} FROM trades")
        connection.execute("DROP TABLE trades")
        connection.execute("ALTER TABLE trades_new RENAME TO trades")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def initialize_database(db_path: str | Path) -> None:
    with sqlite3.connect(str(db_path)) as connection:
        ensure_trade_schema(connection)
