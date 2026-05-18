"""Repository for OHLCV price data.

Reads and writes the `historical_prices` table that already exists in the
Investment OS DuckDB schema.  All methods are idempotent — repeated inserts
of the same (symbol, price_date) pair are silently ignored (ON CONFLICT DO NOTHING).

Import path:
    from investment_os.data_layer.repositories.price_repository import PriceRepository
"""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.db import get_cursor
from investment_os.data_layer.models.price import OHLCBar, PriceHistory

logger = get_logger(__name__)

# Matches the historical_prices table column order used in INSERT statements
_INSERT_SQL = """
    INSERT INTO historical_prices
        (symbol, price_date, open_price, high_price, low_price, close_price, volume)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (symbol, price_date) DO NOTHING
"""

_SELECT_RANGE_SQL = """
    SELECT symbol, price_date, open_price, high_price, low_price, close_price, volume
    FROM   historical_prices
    WHERE  symbol = ?
      AND  price_date BETWEEN ? AND ?
    ORDER BY price_date ASC
"""

_SELECT_LATEST_SQL = """
    SELECT symbol, price_date, open_price, high_price, low_price, close_price, volume
    FROM   historical_prices
    WHERE  symbol = ?
    ORDER BY price_date DESC
    LIMIT 1
"""

_SELECT_SYMBOLS_SQL = "SELECT DISTINCT symbol FROM historical_prices ORDER BY symbol"

_SELECT_LATEST_DATE_SQL = """
    SELECT MAX(price_date) FROM historical_prices WHERE symbol = ?
"""


def _norm(symbol: str) -> str:
    """Strip exchange suffixes so DB always stores bare symbols (e.g. NIFTYBEES)."""
    return symbol.upper().removesuffix(".NS").removesuffix(".BSE").strip()


class PriceRepository:
    """CRUD for the `historical_prices` table."""

    # ── Writes ────────────────────────────────────────────────────────────────

    def upsert_bars(self, bars: list[OHLCBar]) -> int:
        """Insert bars; skip any (symbol, price_date) that already exist.

        Symbols are normalized (strip .NS/.BSE suffix) before storage.

        Returns:
            Number of rows actually inserted (conflicts excluded).
        """
        if not bars:
            return 0

        rows = [
            (_norm(b.symbol), b.date, b.open, b.high, b.low, b.close, b.volume)
            for b in bars
        ]
        with get_cursor() as cur:
            cur.executemany(_INSERT_SQL, rows)
            # DuckDB executemany doesn't expose rowcount reliably; use len as proxy
        logger.info("upsert_bars: %d bars submitted for %s", len(bars), {b.symbol for b in bars})
        return len(rows)

    def upsert_history(self, history: PriceHistory) -> int:
        """Convenience wrapper: insert all bars from a PriceHistory object."""
        return self.upsert_bars(history.bars)

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_bars(
        self,
        symbol: str,
        from_date: date,
        to_date: Optional[date] = None,
    ) -> PriceHistory:
        """Fetch OHLCV bars for a symbol between two dates (inclusive).

        Args:
            symbol:    Instrument symbol (bare or with .NS suffix — normalized automatically).
            from_date: Start date (inclusive).
            to_date:   End date (inclusive). Defaults to today.

        Returns:
            PriceHistory with bars sorted oldest-first.
        """
        symbol = _norm(symbol)
        to = to_date or date.today()
        with get_cursor() as cur:
            rows = cur.execute(_SELECT_RANGE_SQL, [symbol, from_date, to]).fetchall()

        bars = [_row_to_bar(r) for r in rows]
        logger.debug("get_bars(%s): %d rows from %s to %s", symbol, len(bars), from_date, to)
        return PriceHistory(symbol=symbol, bars=bars)

    def get_latest_bar(self, symbol: str) -> Optional[OHLCBar]:
        """Return the most recent bar for a symbol, or None if not in DB."""
        with get_cursor() as cur:
            row = cur.execute(_SELECT_LATEST_SQL, [_norm(symbol)]).fetchone()
        return _row_to_bar(row) if row else None

    def get_latest_close(self, symbol: str) -> Optional[float]:
        """Return the latest closing price for a symbol, or None."""
        bar = self.get_latest_bar(symbol)
        return bar.close if bar else None

    def get_latest_date(self, symbol: str) -> Optional[date]:
        """Return the date of the most recent bar for a symbol."""
        with get_cursor() as cur:
            row = cur.execute(_SELECT_LATEST_DATE_SQL, [_norm(symbol)]).fetchone()
        return row[0] if row and row[0] else None

    def list_symbols(self) -> list[str]:
        """Return all distinct symbols present in historical_prices."""
        with get_cursor() as cur:
            rows = cur.execute(_SELECT_SYMBOLS_SQL).fetchall()
        return [r[0] for r in rows]

    def get_multi(
        self,
        symbols: list[str],
        from_date: date,
        to_date: Optional[date] = None,
    ) -> dict[str, PriceHistory]:
        """Fetch price histories for multiple symbols in a single query.

        Returns:
            Dict keyed by symbol.
        """
        if not symbols:
            return {}

        symbols = [_norm(s) for s in symbols]
        to = to_date or date.today()
        placeholders = ", ".join("?" * len(symbols))
        sql = f"""
            SELECT symbol, price_date, open_price, high_price, low_price, close_price, volume
            FROM   historical_prices
            WHERE  symbol IN ({placeholders})
              AND  price_date BETWEEN ? AND ?
            ORDER BY symbol, price_date ASC
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, [*symbols, from_date, to]).fetchall()

        result: dict[str, list[OHLCBar]] = {s: [] for s in symbols}
        for row in rows:
            result[row[0]].append(_row_to_bar(row))

        return {sym: PriceHistory(symbol=sym, bars=bars) for sym, bars in result.items()}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_bar(row: tuple) -> OHLCBar:
    """Convert a DB row tuple → OHLCBar.

    Column order: symbol, price_date, open_price, high_price, low_price, close_price, volume
    """
    return OHLCBar(
        symbol=row[0],
        date=row[1] if isinstance(row[1], date) else date.fromisoformat(str(row[1])),
        open=float(row[2] or 0),
        high=float(row[3] or 0),
        low=float(row[4] or 0),
        close=float(row[5] or 0),
        volume=int(row[6] or 0),
    )
