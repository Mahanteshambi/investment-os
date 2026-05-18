"""Repository for portfolio holdings.

Reads and writes the `holdings` table from the existing Investment OS schema.
The sync pattern is a full replace per source: all rows for a given source
are deleted, then the new batch is inserted.  This keeps the table clean
without needing a complex merge.

Import path:
    from investment_os.data_layer.repositories.holdings_repository import HoldingsRepository
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.db import get_cursor
from investment_os.data_layer.models.holding import AssetClass, Holding, HoldingSource

logger = get_logger(__name__)

_INSERT_SQL = """
    INSERT INTO holdings (
        id, asset_name, ticker, asset_class, sub_class,
        source, platform, quantity, avg_cost, current_price,
        current_value, invested_value, unrealized_pnl, unrealized_pnl_pct,
        sector, last_updated
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_ALL_SQL = """
    SELECT id, asset_name, ticker, asset_class, sub_class,
           source, platform, quantity, avg_cost, current_price,
           current_value, invested_value, unrealized_pnl, unrealized_pnl_pct,
           sector, last_updated
    FROM   holdings
    ORDER BY asset_class, asset_name
"""

_SELECT_BY_SOURCE_SQL = _SELECT_ALL_SQL.replace(
    "ORDER BY", "WHERE source = ? ORDER BY"
)

_SELECT_BY_ASSET_CLASS_SQL = _SELECT_ALL_SQL.replace(
    "ORDER BY", "WHERE asset_class = ? ORDER BY"
)

_SELECT_BY_TICKER_SQL = """
    SELECT id, asset_name, ticker, asset_class, sub_class,
           source, platform, quantity, avg_cost, current_price,
           current_value, invested_value, unrealized_pnl, unrealized_pnl_pct,
           sector, last_updated
    FROM   holdings
    WHERE  ticker = ?
    LIMIT 1
"""

_DELETE_BY_SOURCE_SQL = "DELETE FROM holdings WHERE source = ?"


class HoldingsRepository:
    """CRUD for the `holdings` table."""

    # ── Writes ────────────────────────────────────────────────────────────────

    def replace_source(self, holdings: list[Holding], source: HoldingSource | str) -> int:
        """Atomically replace all holdings for a given source.

        Deletes all existing rows for `source`, then inserts the new batch.
        Equivalent to the existing sync_service._upsert_holdings() behaviour.

        Returns:
            Number of rows inserted.
        """
        src = source.value if isinstance(source, HoldingSource) else source
        rows = [_holding_to_row(h) for h in holdings]

        with get_cursor() as cur:
            cur.execute(_DELETE_BY_SOURCE_SQL, [src])
            if rows:
                cur.executemany(_INSERT_SQL, rows)

        logger.info("replace_source(%s): deleted old rows, inserted %d", src, len(rows))
        return len(rows)

    def upsert(self, holding: Holding) -> None:
        """Insert or replace a single holding by id."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM holdings WHERE id = ?", [holding.id])
            cur.execute(_INSERT_SQL, _holding_to_row(holding))

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_all(self) -> list[Holding]:
        """Return all holdings across all sources."""
        with get_cursor() as cur:
            rows = cur.execute(_SELECT_ALL_SQL).fetchall()
        return [_row_to_holding(r) for r in rows]

    def get_by_source(self, source: HoldingSource | str) -> list[Holding]:
        """Return holdings from a specific source (kite / sheets / manual)."""
        src = source.value if isinstance(source, HoldingSource) else source
        with get_cursor() as cur:
            rows = cur.execute(_SELECT_BY_SOURCE_SQL, [src]).fetchall()
        return [_row_to_holding(r) for r in rows]

    def get_by_asset_class(self, asset_class: AssetClass | str) -> list[Holding]:
        """Return all holdings of a specific asset class (equity/etf/mf/gold/cash/debt)."""
        cls = asset_class.value if isinstance(asset_class, AssetClass) else asset_class
        with get_cursor() as cur:
            rows = cur.execute(_SELECT_BY_ASSET_CLASS_SQL, [cls]).fetchall()
        return [_row_to_holding(r) for r in rows]

    def get_by_ticker(self, ticker: str) -> Optional[Holding]:
        """Return the first holding matching a ticker symbol, or None."""
        with get_cursor() as cur:
            row = cur.execute(_SELECT_BY_TICKER_SQL, [ticker.upper()]).fetchone()
        return _row_to_holding(row) if row else None

    def get_by_bucket(self, bucket: str) -> list[Holding]:
        """Return holdings that belong to a named bucket (Large Cap, Gold, etc.).

        Bucket is stored as `sub_class` in the holdings table.
        Maps bucket display names to sub_class values used in the DB.
        """
        bucket_map: dict[str, str] = {
            "Large Cap":   "large_cap",
            "Mid/Small":   "mid_small_cap",
            "Gold":        "gold_etf",
            "Debt":        "liquid",
            "International": "international",
            "Sector":      "sector",
        }
        sub = bucket_map.get(bucket, bucket.lower().replace(" ", "_"))
        sql = """
            SELECT id, asset_name, ticker, asset_class, sub_class,
                   source, platform, quantity, avg_cost, current_price,
                   current_value, invested_value, unrealized_pnl, unrealized_pnl_pct,
                   sector, last_updated
            FROM   holdings
            WHERE  sub_class = ?
            ORDER BY asset_name
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, [sub]).fetchall()
        return [_row_to_holding(r) for r in rows]

    # ── Aggregates ────────────────────────────────────────────────────────────

    def total_value(self) -> float:
        """Sum of current_value across all holdings."""
        with get_cursor() as cur:
            row = cur.execute("SELECT SUM(current_value) FROM holdings").fetchone()
        return float(row[0] or 0)

    def total_invested(self) -> float:
        """Sum of invested_value across all holdings."""
        with get_cursor() as cur:
            row = cur.execute("SELECT SUM(invested_value) FROM holdings").fetchone()
        return float(row[0] or 0)

    def count(self) -> int:
        with get_cursor() as cur:
            row = cur.execute("SELECT COUNT(*) FROM holdings").fetchone()
        return int(row[0] or 0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _holding_to_row(h: Holding) -> tuple:
    """Convert Holding → tuple matching _INSERT_SQL parameter order."""
    return (
        h.id, h.asset_name, h.ticker,
        h.asset_class if isinstance(h.asset_class, str) else h.asset_class.value,
        h.sub_class,
        h.source if isinstance(h.source, str) else h.source.value,
        h.platform,
        h.quantity, h.avg_cost, h.current_price,
        h.current_value, h.invested_value, h.unrealized_pnl, h.unrealized_pnl_pct,
        h.sector, h.last_updated,
    )


def _row_to_holding(row: tuple) -> Holding:
    """Convert a DB row tuple → Holding.

    Column order matches _SELECT_ALL_SQL.
    """
    return Holding(
        id=row[0],
        asset_name=row[1],
        ticker=row[2],
        asset_class=row[3],
        sub_class=row[4],
        source=row[5],
        platform=row[6],
        quantity=float(row[7] or 0),
        avg_cost=float(row[8] or 0),
        current_price=float(row[9] or 0),
        current_value=float(row[10] or 0),
        invested_value=float(row[11] or 0),
        unrealized_pnl=float(row[12] or 0),
        unrealized_pnl_pct=float(row[13] or 0),
        sector=row[14],
        last_updated=row[15] if isinstance(row[15], datetime) else datetime.fromisoformat(str(row[15])),
    )
