import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database.backup import create_backup, restore_backup
from app.database.connection import connect
from app.migrations import run_migrations
from app.settings import database_path


class AppPlatformTests(unittest.TestCase):
    def test_first_run_database_creation_and_migrations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.db"
            with connect(path) as connection:
                self.assertEqual(run_migrations(connection), 4)
                tables = {
                    row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            self.assertTrue(path.exists())
            self.assertTrue({"schema_version", "trades"}.issubset(tables))

    def test_database_path_uses_configured_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"TRADE_TRACKER_DATA_DIR": directory}):
                self.assertEqual(database_path(), Path(directory) / "trades.db")

    def test_sqlite_backup_and_confirmed_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            active = Path(directory) / "trades.db"
            source = Path(directory) / "source.db"
            with sqlite3.connect(active) as connection:
                connection.execute("CREATE TABLE values_table(value TEXT)")
                connection.execute("INSERT INTO values_table VALUES ('before')")
            backup = create_backup(active, Path(directory) / "backups")
            self.assertTrue(backup.exists())
            with sqlite3.connect(source) as connection:
                connection.execute("CREATE TABLE values_table(value TEXT)")
                connection.execute("INSERT INTO values_table VALUES ('after')")
            with self.assertRaises(PermissionError):
                restore_backup(active, source)
            safety = restore_backup(active, source, confirmed=True)
            self.assertTrue(safety.exists())
            with sqlite3.connect(active) as connection:
                self.assertEqual(connection.execute("SELECT value FROM values_table").fetchone()[0], "after")


if __name__ == "__main__":
    unittest.main()
