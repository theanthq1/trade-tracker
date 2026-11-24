"""Application paths and runtime settings."""

from __future__ import annotations

from pathlib import Path

from app.config import load_environment

load_environment()

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_DIR / "trades.db"


def app_data_dir() -> Path:
    """Return the directory containing the app's local database."""
    return PROJECT_DIR


def database_path() -> Path:
    return DATABASE_PATH


def prepare_database_path() -> Path:
    """Return the database path, creating its parent directory if needed."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH


def diagnostic_summary() -> str:
    return f"Database: {database_path()}"
