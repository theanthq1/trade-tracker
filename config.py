"""Backward-compatible import shim; use :mod:`app.config`."""

from app.config import APP_DIR, ENV_FILE, load_environment

__all__ = ["APP_DIR", "ENV_FILE", "load_environment"]
