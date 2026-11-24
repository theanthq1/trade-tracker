"""Safe SQLite backup and restore helpers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_backup(database_path: str | Path, backup_dir: str | Path | None = None) -> Path:
    source_path = Path(database_path)
    target_dir = Path(backup_dir) if backup_dir else source_path.parent / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"trades-{_timestamp()}.db"
    with sqlite3.connect(str(source_path)) as source, sqlite3.connect(str(target)) as destination:
        source.backup(destination)
    return target


def export_database_copy(database_path: str | Path, target_path: str | Path) -> Path:
    """Write a complete, point-in-time SQLite copy to a user-selected path."""
    source_path = Path(database_path).resolve()
    target = Path(target_path).resolve()
    if source_path == target:
        raise ValueError("Choose a different file from the active database.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(source_path)) as source, sqlite3.connect(str(target)) as destination:
        source.backup(destination)
    return target


def restore_backup(
    database_path: str | Path,
    backup_path: str | Path,
    confirmed: bool = False,
) -> Path:
    """Restore only after explicit confirmation, returning a safety backup path."""
    if not confirmed:
        raise PermissionError("Restoring would replace the active database; confirmation is required.")
    active = Path(database_path).resolve()
    backup = Path(backup_path).resolve()
    if active == backup:
        raise ValueError("The backup and active database must be different files.")
    safety_backup = create_backup(active)
    with sqlite3.connect(str(backup)) as source, sqlite3.connect(str(active)) as destination:
        source.backup(destination)
    return safety_backup
