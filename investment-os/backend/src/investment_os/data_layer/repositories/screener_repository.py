"""Repository for screener CSV export data.

Reads and writes the `screener_exports` table added in Phase 1.
Designed for bulk ingestion from Tickertape Pro CSV exports.
UNIQUE constraint on (symbol, export_date, source) prevents duplicate rows.

Import path:
    from investment_os.data_layer.repositories.screener_repository import ScreenerRepository
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.db import get_cursor, engine
from investment_os.data_layer.models.screener import ScreenerRow, ScreenerSource

logger = get_logger(__name__)

_INSERT_SQL = """
    INSERT INTO screener_exports (
        id, imported_at, source, symbol, company_name, sector,
        market_cap_cr, pe_ratio, pb_ratio,
        roce_pct, roe_pct, debt_to_equity,
        revenue_growth_1y, profit_growth_1y, dividend_yield_pct,
        score_raw, export_date, raw_row
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (symbol, export_date, source) DO NOTHING
"""

_SELECT_BASE = """
    SELECT id, imported_at, source, symbol, company_name, sector,
           market_cap_cr, pe_ratio, pb_ratio,
           roce_pct, roe_pct, debt_to_equity,
           revenue_growth_1y, profit_growth_1y, dividend_yield_pct,
           score_raw, export_date, raw_row
    FROM   screener_exports
"""


class ScreenerRepository:
    """CRUD for the `screener_exports` table."""

    # ── Writes ────────────────────────────────────────────────────────────────

    def bulk_insert(self, rows: list[ScreenerRow]) -> int:
        """Insert rows; skip any (symbol, export_date, source) already present.

        Returns:
            Number of rows submitted (conflicts silently skipped).
        """
        if not rows:
            return 0
        db_rows = [_row_to_tuple(r) for r in rows]
        with get_cursor() as cur:
            cur.executemany(_INSERT_SQL, db_rows)
        symbols = {r.symbol for r in rows}
        logger.info("bulk_insert: %d screener rows for %s", len(rows), symbols)
        return len(rows)

    def bulk_insert_from_df(self, df, source: ScreenerSource | str, export_date: date) -> int:
        """Insert from a pandas DataFrame produced by TickertapeLoader.

        The DataFrame must have columns matching ScreenerRow field names
        (column normalisation is the loader's responsibility).

        Returns:
            Number of rows submitted.
        """
        import uuid
        import pandas as pd  # noqa: PLC0415

        src = source.value if isinstance(source, ScreenerSource) else source
        rows: list[ScreenerRow] = []

        for _, r in df.iterrows():
            rows.append(ScreenerRow(
                id=str(uuid.uuid4()),
                source=src,
                symbol=str(r.get("symbol", "")).upper().strip(),
                export_date=export_date,
                company_name=_str(r.get("company_name")),
                sector=_str(r.get("sector")),
                market_cap_cr=_f(r.get("market_cap_cr")),
                pe_ratio=_f(r.get("pe_ratio")),
                pb_ratio=_f(r.get("pb_ratio")),
                roce_pct=_f(r.get("roce_pct")),
                roe_pct=_f(r.get("roe_pct")),
                debt_to_equity=_f(r.get("debt_to_equity")),
                revenue_growth_1y=_f(r.get("revenue_growth_1y")),
                profit_growth_1y=_f(r.get("profit_growth_1y")),
                dividend_yield_pct=_f(r.get("dividend_yield_pct")),
                score_raw=_f(r.get("score_raw")),
                raw_row=r.to_dict(),
            ))

        return self.bulk_insert([r for r in rows if r.symbol])

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_latest_export(
        self,
        source: ScreenerSource | str,
        limit: int = 500,
    ) -> list[ScreenerRow]:
        """Return all rows from the most recent export for a given source."""
        src = source.value if isinstance(source, ScreenerSource) else source
        sql = f"""
            WITH latest AS (
                SELECT MAX(export_date) AS max_date
                FROM screener_exports
                WHERE source = ?
            )
            {_SELECT_BASE}
            WHERE source = ?
              AND export_date = (SELECT max_date FROM latest)
            ORDER BY symbol
            LIMIT ?
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, [src, src, limit]).fetchall()
        return [_tuple_to_row(r) for r in rows]

    def get_by_sector(
        self,
        sector: str,
        source: Optional[ScreenerSource | str] = None,
    ) -> list[ScreenerRow]:
        """Return latest-export rows for a specific sector."""
        src = source.value if isinstance(source, ScreenerSource) else source if source else None
        if src:
            sql = f"""
                WITH latest AS (
                    SELECT MAX(export_date) AS max_date
                    FROM screener_exports
                    WHERE source = ?
                )
                {_SELECT_BASE}
                WHERE source = ?
                  AND sector = ?
                  AND export_date = (SELECT max_date FROM latest)
                ORDER BY market_cap_cr DESC NULLS LAST
            """
            with get_cursor() as cur:
                rows = cur.execute(sql, [src, src, sector]).fetchall()
        else:
            sql = f"""
                {_SELECT_BASE}
                WHERE sector = ?
                ORDER BY export_date DESC, market_cap_cr DESC NULLS LAST
                LIMIT 200
            """
            with get_cursor() as cur:
                rows = cur.execute(sql, [sector]).fetchall()
        return [_tuple_to_row(r) for r in rows]

    def get_top_by_roce(
        self,
        source: ScreenerSource | str,
        min_roce: float = 15.0,
        limit: int = 30,
    ) -> list[ScreenerRow]:
        """Return top instruments by ROCE from the latest export.

        Useful as a quick quality screen before Phase 4 scoring.
        """
        src = source.value if isinstance(source, ScreenerSource) else source
        sql = f"""
            WITH latest AS (
                SELECT MAX(export_date) AS max_date
                FROM screener_exports WHERE source = ?
            )
            {_SELECT_BASE}
            WHERE source = ?
              AND export_date = (SELECT max_date FROM latest)
              AND roce_pct >= ?
            ORDER BY roce_pct DESC
            LIMIT ?
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, [src, src, min_roce, limit]).fetchall()
        return [_tuple_to_row(r) for r in rows]

    def list_export_dates(self, source: ScreenerSource | str) -> list[date]:
        """Return all distinct export dates for a source, newest-first."""
        src = source.value if isinstance(source, ScreenerSource) else source
        with get_cursor() as cur:
            rows = cur.execute(
                "SELECT DISTINCT export_date FROM screener_exports WHERE source = ? ORDER BY export_date DESC",
                [src],
            ).fetchall()
        return [r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0])) for r in rows]

    def as_dataframe(self, source: ScreenerSource | str, export_date: Optional[date] = None):
        """Return screener data as a pandas DataFrame for analysis.

        If export_date is None, returns the latest export.
        """
        src = source.value if isinstance(source, ScreenerSource) else source

        if export_date:
            sql = _SELECT_BASE + "WHERE source = ? AND export_date = ?"
            params = [src, export_date]
        else:
            sql = f"""
                WITH latest AS (
                    SELECT MAX(export_date) AS max_date
                    FROM screener_exports WHERE source = ?
                )
                {_SELECT_BASE}
                WHERE source = ? AND export_date = (SELECT max_date FROM latest)
            """
            params = [src, src]

        return engine().execute(sql, params).df()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_tuple(r: ScreenerRow) -> tuple:
    return (
        r.id, r.imported_at,
        r.source if isinstance(r.source, str) else r.source.value,
        r.symbol, r.company_name, r.sector,
        r.market_cap_cr, r.pe_ratio, r.pb_ratio,
        r.roce_pct, r.roe_pct, r.debt_to_equity,
        r.revenue_growth_1y, r.profit_growth_1y, r.dividend_yield_pct,
        r.score_raw,
        r.export_date,
        json.dumps(r.raw_row) if r.raw_row else None,
    )


def _tuple_to_row(row: tuple) -> ScreenerRow:
    raw = row[17]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None

    return ScreenerRow(
        id=row[0],
        imported_at=row[1] if isinstance(row[1], datetime) else datetime.fromisoformat(str(row[1])),
        source=row[2],
        symbol=row[3],
        company_name=row[4],
        sector=row[5],
        market_cap_cr=_f(row[6]),
        pe_ratio=_f(row[7]),
        pb_ratio=_f(row[8]),
        roce_pct=_f(row[9]),
        roe_pct=_f(row[10]),
        debt_to_equity=_f(row[11]),
        revenue_growth_1y=_f(row[12]),
        profit_growth_1y=_f(row[13]),
        dividend_yield_pct=_f(row[14]),
        score_raw=_f(row[15]),
        export_date=row[16] if isinstance(row[16], date) else date.fromisoformat(str(row[16])),
        raw_row=raw,
    )


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None


def _str(v) -> Optional[str]:
    return str(v).strip() if v is not None and str(v).strip() else None
