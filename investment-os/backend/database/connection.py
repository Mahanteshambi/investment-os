import os
import threading
import duckdb
from pathlib import Path

_connection: duckdb.DuckDBPyConnection | None = None
_init_lock = threading.Lock()


def _run_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(stmt)


def get_connection() -> duckdb.DuckDBPyConnection:
    global _connection
    if _connection is None:
        with _init_lock:
            if _connection is None:
                db_path = os.getenv("DATABASE_PATH", "./data/investment_os.duckdb")
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                _connection = duckdb.connect(db_path)
                _run_migrations(_connection)
    return _connection


def get_db() -> duckdb.DuckDBPyConnection:
    """Return a per-request cursor from the shared connection.
    DuckDB cursors from the same connection are isolated across threads."""
    return get_connection().cursor()


def close_connection() -> None:
    global _connection
    with _init_lock:
        if _connection is not None:
            _connection.close()
            _connection = None
