"""DuckDB connection manager for the src/investment_os package.

Provides a thread-safe singleton connection and a context-manager helper
for short-lived cursors.  The existing `database/connection.py` at the
backend root is untouched — this module is used only by code under
`src/investment_os/`.

Usage:
    from investment_os.data_layer.db import get_cursor, engine

    with get_cursor() as cur:
        rows = cur.execute("SELECT * FROM holdings").fetchall()
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import duckdb

from investment_os.core.config import settings
from investment_os.core.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_connection: duckdb.DuckDBPyConnection | None = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    """Return (or lazily create) the singleton DuckDB connection."""
    global _connection
    if _connection is not None:
        return _connection

    with _lock:
        # Double-checked locking: another thread might have created it while
        # we were waiting on the lock.
        if _connection is not None:
            return _connection

        db_path: Path = settings.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Opening DuckDB at %s", db_path)
        try:
            conn = duckdb.connect(str(db_path), read_only=False)
            logger.debug("DuckDB opened read-write")
        except duckdb.IOException:
            # Another process (e.g. FastAPI server) holds the write lock.
            # Fall back to read-only — writes will raise, but reads work fine.
            logger.warning(
                "DuckDB write lock unavailable — opening read-only. "
                "Stop the FastAPI server before running ingestion scripts."
            )
            conn = duckdb.connect(str(db_path), read_only=True)

        # Reasonable defaults for a single-writer workload
        conn.execute("PRAGMA threads=4")
        conn.execute("PRAGMA memory_limit='512MB'")

        _connection = conn
        return _connection


@contextmanager
def get_cursor() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Yield a short-lived cursor derived from the singleton connection.

    DuckDB cursors are lightweight and can be used concurrently; each
    cursor has its own transaction context.  Always prefer this over
    using `engine` directly.

    Example::

        with get_cursor() as cur:
            cur.execute("INSERT INTO ...")
    """
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def engine() -> duckdb.DuckDBPyConnection:
    """Return the raw singleton connection.

    Use only when you need DuckDB's DataFrame/Arrow integration directly
    (e.g., `conn.execute(...).df()`).  For regular queries prefer `get_cursor()`.
    """
    return _get_connection()


def close() -> None:
    """Close the singleton connection.  Call during application shutdown."""
    global _connection
    with _lock:
        if _connection is not None:
            logger.info("Closing DuckDB connection")
            _connection.close()
            _connection = None
