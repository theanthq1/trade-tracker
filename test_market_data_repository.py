import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.database.connection import connect
from app.database.market_data_repository import MarketDataRepository, MarketDataRequest
from app.migrations import run_migrations


class MarketDataRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "trades.db"
        with connect(self.path) as connection:
            run_migrations(connection)
            connection.execute(
                """INSERT INTO trades(stock_entry, option_entry, stock_exit, option_exit, created_at, ticker_symbol)
                   VALUES (100, 1, 101, 1.5, ?, 'AAPL')""",
                ("2026-10-15T13:30:00+00:00",),
            )
        self.request = MarketDataRequest(
            trade_id=1, symbol="AAPL", trade_date="2026-10-15", provider="Massive",
            data_type="candles", resolution="1m",
            start_time=datetime.fromisoformat("2026-10-15T08:00:00-04:00"),
            end_time=datetime.fromisoformat("2026-10-15T10:31:00-04:00"),
        )
        self.records = [
            {"symbol": "AAPL", "time": "2026-10-15T12:00:00+00:00", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 10},
            {"symbol": "AAPL", "time": "2026-10-15T12:01:00+00:00", "open": 100.5, "high": 102, "low": 100, "close": 101, "volume": 12},
        ]

    def tearDown(self):
        self.directory.cleanup()

    def test_first_request_saves_and_second_request_uses_cache(self):
        repository = MarketDataRepository(self.path)
        calls = []

        def fetch():
            calls.append(1)
            return self.records

        first = repository.load_or_fetch(self.request, fetch)
        second = repository.load_or_fetch(self.request, fetch)
        self.assertEqual(first["status"], "Downloaded and saved")
        self.assertEqual(second["status"], "Loaded from saved data")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(second["candles"]), 2)

    def test_provider_is_part_of_cache_key(self):
        repository = MarketDataRepository(self.path)
        repository.load_or_fetch(self.request, lambda: self.records)
        schwab_request = self.request.__class__(**{**self.request.__dict__, "provider": "Schwab"})
        calls = []
        result = repository.load_or_fetch(schwab_request, lambda: calls.append(1) or self.records)
        self.assertEqual(result["status"], "Downloaded and saved")
        self.assertEqual(len(calls), 1)

    def test_refresh_creates_new_active_snapshot_and_preserves_old(self):
        repository = MarketDataRepository(self.path)
        first = repository.load_or_fetch(self.request, lambda: self.records)
        refreshed = repository.load_or_fetch(self.request, lambda: self.records, force_refresh=True)
        self.assertNotEqual(first["snapshot_id"], refreshed["snapshot_id"])
        with sqlite3.connect(self.path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM market_data_snapshots").fetchone()[0]
            active = connection.execute("SELECT COUNT(*) FROM market_data_snapshots WHERE is_active = 1").fetchone()[0]
        self.assertEqual(count, 2)
        self.assertEqual(active, 1)

    def test_invalid_data_is_failed_and_not_rendered(self):
        repository = MarketDataRepository(self.path)
        result = repository.load_or_fetch(self.request, lambda: [{**self.records[0], "high": 1}])
        self.assertEqual(result["status"], "Provider request failed")
        self.assertEqual(result["candles"], [])
        with sqlite3.connect(self.path) as connection:
            status = connection.execute("SELECT status FROM market_data_snapshots").fetchone()[0]
            candle_count = connection.execute("SELECT COUNT(*) FROM market_data_candles").fetchone()[0]
        self.assertEqual(status, "failed")
        self.assertEqual(candle_count, 0)

    def test_provider_failure_is_recorded(self):
        repository = MarketDataRepository(self.path)
        result = repository.load_or_fetch(self.request, lambda: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
        self.assertEqual(result["status"], "Provider request failed")
        self.assertIn("provider unavailable", result["error_message"])


if __name__ == "__main__":
    unittest.main()
