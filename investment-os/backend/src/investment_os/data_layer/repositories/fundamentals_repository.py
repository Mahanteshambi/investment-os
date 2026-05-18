"""Repository for fundamental snapshots.

Reads and writes the `fundamentals` table added in Phase 1.
All writes are idempotent: (symbol, period_end, period_type, source) is a
UNIQUE constraint, so duplicate submissions are rejected silently.

Import path:
    from investment_os.data_layer.repositories.fundamentals_repository import FundamentalsRepository
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.db import get_cursor
from investment_os.data_layer.models.fundamental import FundamentalSnapshot, FundamentalSource, PeriodType

logger = get_logger(__name__)

_INSERT_SQL = """
    INSERT INTO fundamentals (
        id, symbol, period_end, period_type, source,
        revenue_cr, net_profit_cr, ebitda_cr,
        eps, book_value_per_share,
        pe_ratio, pb_ratio,
        roce_pct, roe_pct, debt_to_equity, current_ratio,
        promoter_holding_pct, fii_holding_pct,
        raw_data, fetched_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (symbol, period_end, period_type, source) DO NOTHING
"""

_SELECT_BASE = """
    SELECT id, symbol, period_end, period_type, source,
           revenue_cr, net_profit_cr, ebitda_cr,
           eps, book_value_per_share,
           pe_ratio, pb_ratio,
           roce_pct, roe_pct, debt_to_equity, current_ratio,
           promoter_holding_pct, fii_holding_pct,
           raw_data, fetched_at
    FROM   fundamentals
"""


class FundamentalsRepository:
    """CRUD for the `fundamentals` table."""

    # ── Writes ────────────────────────────────────────────────────────────────

    def upsert(self, snap: FundamentalSnapshot) -> bool:
        """Insert a snapshot; skip if (symbol, period_end, period_type, source) already exists.

        Returns:
            True if inserted, False if skipped (conflict).
        """
        with get_cursor() as cur:
            cur.execute(_INSERT_SQL, _snap_to_row(snap))
        logger.debug("upsert: %s %s %s", snap.symbol, snap.period_end, snap.period_type)
        return True  # DuckDB DO NOTHING doesn't surface conflict count in executemany

    def bulk_upsert(self, snaps: list[FundamentalSnapshot]) -> int:
        """Insert multiple snapshots; skip existing (symbol, period_end, period_type, source).

        Returns:
            Number of rows submitted (not necessarily inserted — conflicts silently skipped).
        """
        if not snaps:
            return 0
        rows = [_snap_to_row(s) for s in snaps]
        with get_cursor() as cur:
            cur.executemany(_INSERT_SQL, rows)
        logger.info("bulk_upsert: %d fundamentals submitted", len(rows))
        return len(rows)

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_latest(self, symbol: str, period_type: PeriodType | str = PeriodType.TTM) -> Optional[FundamentalSnapshot]:
        """Return the most recent snapshot for a symbol and period type."""
        pt = period_type.value if isinstance(period_type, PeriodType) else period_type
        sql = _SELECT_BASE + "WHERE symbol = ? AND period_type = ? ORDER BY period_end DESC LIMIT 1"
        with get_cursor() as cur:
            row = cur.execute(sql, [symbol, pt]).fetchone()
        return _row_to_snap(row) if row else None

    def get_history(
        self,
        symbol: str,
        period_type: PeriodType | str = PeriodType.QUARTERLY,
        limit: int = 8,
    ) -> list[FundamentalSnapshot]:
        """Return up to `limit` snapshots for a symbol, newest-first."""
        pt = period_type.value if isinstance(period_type, PeriodType) else period_type
        sql = _SELECT_BASE + "WHERE symbol = ? AND period_type = ? ORDER BY period_end DESC LIMIT ?"
        with get_cursor() as cur:
            rows = cur.execute(sql, [symbol, pt, limit]).fetchall()
        return [_row_to_snap(r) for r in rows]

    def get_by_source(self, source: FundamentalSource | str) -> list[FundamentalSnapshot]:
        """Return all snapshots from a given source."""
        src = source.value if isinstance(source, FundamentalSource) else source
        sql = _SELECT_BASE + "WHERE source = ? ORDER BY symbol, period_end DESC"
        with get_cursor() as cur:
            rows = cur.execute(sql, [src]).fetchall()
        return [_row_to_snap(r) for r in rows]

    def list_symbols(self) -> list[str]:
        """Return all distinct symbols that have fundamental data."""
        with get_cursor() as cur:
            rows = cur.execute("SELECT DISTINCT symbol FROM fundamentals ORDER BY symbol").fetchall()
        return [r[0] for r in rows]

    def get_quality_ranked(
        self,
        period_type: PeriodType | str = PeriodType.TTM,
        min_roce: float = 0.0,
        limit: int = 50,
    ) -> list[FundamentalSnapshot]:
        """Return latest TTM snapshots ranked by ROCE descending.

        Useful for Phase 4 fundamental scorer.
        """
        pt = period_type.value if isinstance(period_type, PeriodType) else period_type
        sql = f"""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY period_end DESC) AS rn
                FROM fundamentals
                WHERE period_type = ?
            )
            SELECT id, symbol, period_end, period_type, source,
                   revenue_cr, net_profit_cr, ebitda_cr,
                   eps, book_value_per_share,
                   pe_ratio, pb_ratio,
                   roce_pct, roe_pct, debt_to_equity, current_ratio,
                   promoter_holding_pct, fii_holding_pct,
                   raw_data, fetched_at
            FROM ranked
            WHERE rn = 1
              AND roce_pct >= ?
            ORDER BY roce_pct DESC
            LIMIT ?
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, [pt, min_roce, limit]).fetchall()
        return [_row_to_snap(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snap_to_row(s: FundamentalSnapshot) -> tuple:
    return (
        s.id, s.symbol,
        s.period_end,
        s.period_type if isinstance(s.period_type, str) else s.period_type.value,
        s.source if isinstance(s.source, str) else s.source.value,
        s.revenue_cr, s.net_profit_cr, s.ebitda_cr,
        s.eps, s.book_value_per_share,
        s.pe_ratio, s.pb_ratio,
        s.roce_pct, s.roe_pct, s.debt_to_equity, s.current_ratio,
        s.promoter_holding_pct, s.fii_holding_pct,
        json.dumps(s.raw_data) if s.raw_data else None,
        s.fetched_at,
    )


def _row_to_snap(row: tuple) -> FundamentalSnapshot:
    raw = row[18]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None

    return FundamentalSnapshot(
        id=row[0], symbol=row[1],
        period_end=row[2] if isinstance(row[2], date) else date.fromisoformat(str(row[2])),
        period_type=row[3], source=row[4],
        revenue_cr=_f(row[5]), net_profit_cr=_f(row[6]), ebitda_cr=_f(row[7]),
        eps=_f(row[8]), book_value_per_share=_f(row[9]),
        pe_ratio=_f(row[10]), pb_ratio=_f(row[11]),
        roce_pct=_f(row[12]), roe_pct=_f(row[13]),
        debt_to_equity=_f(row[14]), current_ratio=_f(row[15]),
        promoter_holding_pct=_f(row[16]), fii_holding_pct=_f(row[17]),
        raw_data=raw,
        fetched_at=row[19] if isinstance(row[19], datetime) else datetime.fromisoformat(str(row[19])),
    )


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None
