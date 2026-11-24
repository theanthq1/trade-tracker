"""User-specific paths and runtime settings."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from platformdirs import user_data_dir

from app.config import load_environment

load_environment()

PROJECT_DIR = Path(__file__).resolve().parents[1]


def app_data_dir() -> Path:
    override = os.environ.get("TRADE_TRACKER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(user_data_dir("trade-tracker", appauthor=False, roaming=True))


def database_path() -> Path:
    return app_data_dir() / "trades.db"


def prepare_database_path() -> Path:
    """Create the data directory and preserve a legacy repository database.

    Existing repository-local databases are copied with SQLite's backup API on
    first launch; the original file is never deleted or overwritten.
    """
    target = database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy = PROJECT_DIR / "trades.db"
    if not target.exists() and legacy.exists() and legacy.resolve() != target.resolve():
        with sqlite3.connect(str(legacy)) as source, sqlite3.connect(str(target)) as destination:
            source.backup(destination)
    return target


def diagnostic_summary() -> str:
    return f"Database: {database_path()}"
