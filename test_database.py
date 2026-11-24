import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import ensure_trade_schema
from app.database.backup import export_database_copy
from app.database.schema import TRADE_COLUMNS


class TradeDatabaseMigrationTests(unittest.TestCase):
    def test_migration_preserves_rows_adds_fields_and_removes_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.db"
            with sqlite3.connect(path) as connection:
                connection.execute("""
                    CREATE TABLE trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_entry REAL NOT NULL,
                        option_entry REAL NOT NULL,
                        stock_exit REAL NOT NULL,
                        option_exit REAL NOT NULL,
                        screenshot BLOB,
                        created_at TEXT NOT NULL,
                        ticker_symbol TEXT,
                        option_type TEXT,
                        exit_timer_started_at TEXT,
                        option_entry_typed_at TEXT,
                        option_exit_typed_at TEXT,
                        length_of_trade_seconds REAL,
                        status TEXT NOT NULL DEFAULT 'closed'
                    )
                """)
                connection.execute(
                    "INSERT INTO trades (stock_entry, option_entry, stock_exit, option_exit, created_at, ticker_symbol, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (100.0, 1.25, 101.0, 1.75, "2026-09-18T13:30:00+00:00", "AAA", "closed"),
                )
                connection.commit()
                ensure_trade_schema(connection)
                columns = [row[1] for row in connection.execute("PRAGMA table_info(trades)")]
                row = connection.execute("SELECT ticker_symbol, premarket_high, previous_day_low FROM trades").fetchone()

            self.assertNotIn("status", columns)
            self.assertIn("premarket_high", columns)
            self.assertIn("premarket_low", columns)
            self.assertIn("regular_session_open", columns)
            self.assertIn("previous_day_open", columns)
            self.assertIn("previous_day_high", columns)
            self.assertIn("previous_day_low", columns)
            self.assertEqual(row[0], "AAA")
            self.assertIsNone(row[1])
            self.assertIsNone(row[2])

    def test_market_values_can_be_inserted_and_retrieved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.db"
            with sqlite3.connect(path) as connection:
                ensure_trade_schema(connection)
                connection.execute(
                    """
                    INSERT INTO trades (
                        stock_entry, option_entry, stock_exit, option_exit, created_at,
                        premarket_high, premarket_low, regular_session_open,
                        previous_day_open, previous_day_high, previous_day_low
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (100, 1, 101, 1.5, "2026-09-18T13:30:00+00:00", 102, 99, 100, 98, 105, 95),
                )
                row = connection.execute(
                    "SELECT premarket_high, premarket_low, regular_session_open, previous_day_open, previous_day_high, previous_day_low FROM trades"
                ).fetchone()
            self.assertEqual(tuple(row), (102.0, 99.0, 100.0, 98.0, 105.0, 95.0))

    def test_export_database_copy_preserves_all_trade_columns_and_values(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.db"
            target = Path(directory) / "exported.db"
            with sqlite3.connect(source) as connection:
                ensure_trade_schema(connection)
                connection.execute(
                    """
                    INSERT INTO trades (
                        stock_entry, option_entry, stock_exit, option_exit,
                        created_at, length_of_trade_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (100, 1.5, 101, 1.8, "2026-10-17T15:00:00+00:00", 420.0),
                )
                connection.commit()
            export_database_copy(source, target)
            with sqlite3.connect(target) as connection:
                columns = [row[1] for row in connection.execute("PRAGMA table_info(trades)")]
                duration = connection.execute("SELECT length_of_trade_seconds FROM trades").fetchone()[0]
            self.assertEqual(columns, [name for name, _ in TRADE_COLUMNS])
            self.assertEqual(duration, 420.0)


if __name__ == "__main__":
    unittest.main()
