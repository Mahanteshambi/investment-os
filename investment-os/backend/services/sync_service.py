import logging
import uuid
from datetime import datetime, date

import duckdb

from database.connection import get_db
from models.schemas import HoldingCreate, SyncResponse
from services.kite_service import KiteService
from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

_kite_service = KiteService()
_sheets_service = SheetsService()


def _upsert_holdings(conn: duckdb.DuckDBPyConnection, holdings: list[HoldingCreate], source: str) -> int:
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM holdings WHERE source = ?", [source])
        for h in holdings:
            conn.execute(
                """
                INSERT INTO holdings (
                    id, asset_name, ticker, asset_class, sub_class, source,
                    quantity, avg_cost, current_price, current_value,
                    invested_value, unrealized_pnl, unrealized_pnl_pct,
                    sector, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    h.id, h.asset_name, h.ticker, h.asset_class, h.sub_class, h.source,
                    h.quantity, h.avg_cost, h.current_price, h.current_value,
                    h.invested_value, h.unrealized_pnl, h.unrealized_pnl_pct,
                    h.sector, datetime.now(),
                ],
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(holdings)


def _write_sync_log(conn: duckdb.DuckDBPyConnection, source: str, status: str, records: int, error: str | None):
    conn.execute(
        """
        INSERT INTO sync_log (id, synced_at, source, status, records_updated, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [str(uuid.uuid4()), datetime.now(), source, status, records, error],
    )


def take_daily_snapshot(conn: duckdb.DuckDBPyConnection) -> None:
    today = date.today()
    row = conn.execute(
        """
        SELECT
            SUM(current_value) AS total_value,
            SUM(invested_value) AS invested_value,
            SUM(current_value) - SUM(invested_value) AS total_pnl,
            CASE WHEN SUM(invested_value) > 0
                 THEN (SUM(current_value) - SUM(invested_value)) / SUM(invested_value) * 100
                 ELSE 0 END AS total_pnl_pct,
            SUM(CASE WHEN asset_class = 'equity' THEN current_value ELSE 0 END) / NULLIF(SUM(current_value), 0) * 100 AS equity_pct,
            SUM(CASE WHEN asset_class = 'mf' THEN current_value ELSE 0 END) / NULLIF(SUM(current_value), 0) * 100 AS mf_pct,
            SUM(CASE WHEN asset_class = 'gold' THEN current_value ELSE 0 END) / NULLIF(SUM(current_value), 0) * 100 AS gold_pct,
            SUM(CASE WHEN asset_class = 'cash' THEN current_value ELSE 0 END) / NULLIF(SUM(current_value), 0) * 100 AS cash_pct,
            SUM(CASE WHEN asset_class = 'debt' THEN current_value ELSE 0 END) / NULLIF(SUM(current_value), 0) * 100 AS debt_pct
        FROM holdings
        """
    ).fetchone()

    if row is None or row[0] is None:
        return

    conn.execute(
        """
        INSERT OR REPLACE INTO daily_snapshots (
            snapshot_date, total_value, invested_value, total_pnl, total_pnl_pct,
            equity_pct, mf_pct, gold_pct, cash_pct, debt_pct, nifty50_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        [today, *row],
    )


BUCKET_MAP = {
    "NIFTYBEES": "Large Cap", "SETFNIF50": "Large Cap",
    "JUNIORBEES": "Mid/Small", "MOM100": "Mid/Small",
    "CPSEETF": "Sector", "PHARMABEES": "Sector", "MODEFENCE": "Sector",
    "PSUBNKBEES": "Sector", "ITBEES": "Sector", "BANKBEES": "Sector",
    "GOLDBEES": "Gold",
    "ICICIB22": "International",
    "LIQUIDBEES": "Debt",
}


def _capture_kite_orders(conn: duckdb.DuckDBPyConnection) -> int:
    """Capture today's completed Kite orders into transactions table."""
    try:
        orders = _kite_service.get_completed_orders()
    except Exception as e:
        logger.warning(f"Could not fetch Kite orders: {e}")
        return 0

    inserted = 0
    for o in orders:
        ticker = o.get("tradingsymbol", "")
        txn_type = "buy" if o.get("transaction_type", "").upper() == "BUY" else "sell"
        qty = float(o.get("filled_quantity") or o.get("quantity") or 0)
        price = float(o.get("average_price") or 0)
        order_id = str(o.get("order_id", ""))
        txn_date = date.today()

        # Skip if already captured
        existing = conn.execute(
            "SELECT id FROM transactions WHERE gtt_id = ? OR (transaction_date = ? AND ticker = ? AND transaction_type = ? AND quantity = ?)",
            [order_id, txn_date, ticker, txn_type, qty]
        ).fetchone()
        if existing:
            continue

        bucket = BUCKET_MAP.get(ticker.upper(), "Other")
        amount = qty * price + float(o.get("charges", 0) or 0)

        conn.execute("""
            INSERT INTO transactions
                (id, transaction_date, asset_name, ticker, asset_class,
                 transaction_type, quantity, price, amount, fees,
                 bucket, gtt_id, exchange, source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            str(uuid.uuid4()), txn_date, ticker, ticker, "etf",
            txn_type, qty, price, amount, 0,
            bucket, order_id, o.get("exchange", "NSE"), "kite", None,
        ])
        inserted += 1

    return inserted


def sync_kite() -> tuple[int, str | None]:
    conn = get_db()
    try:
        holdings = _kite_service.get_holdings()
        count = _upsert_holdings(conn, holdings, "kite")
        captured = _capture_kite_orders(conn)
        if captured:
            logger.info(f"Captured {captured} new Kite orders into transactions")
        _write_sync_log(conn, "kite", "success", count, None)
        return count, None
    except Exception as e:
        err = str(e)
        logger.error(f"sync_kite error: {err}")
        _write_sync_log(conn, "kite", "failed", 0, err)
        return 0, err


def sync_sheets() -> tuple[int, str | None]:
    conn = get_db()
    try:
        holdings = _sheets_service.get_all_manual_holdings()
        count = _upsert_holdings(conn, holdings, "sheets")
        _write_sync_log(conn, "sheets", "success", count, None)
        return count, None
    except Exception as e:
        err = str(e)
        logger.error(f"sync_sheets error: {err}")
        _write_sync_log(conn, "sheets", "failed", 0, err)
        return 0, err


def sync_all() -> SyncResponse:
    sources_synced = []
    errors = []
    total_records = 0

    kite_count, kite_err = sync_kite()
    sources_synced.append("kite")
    total_records += kite_count
    if kite_err:
        errors.append(f"kite: {kite_err}")

    sheets_count, sheets_err = sync_sheets()
    sources_synced.append("sheets")
    total_records += sheets_count
    if sheets_err:
        errors.append(f"sheets: {sheets_err}")

    conn = get_db()
    take_daily_snapshot(conn)

    status = "success" if not errors else ("partial" if total_records > 0 else "failed")
    return SyncResponse(
        status=status,
        sources_synced=sources_synced,
        records_updated=total_records,
        errors=errors,
        synced_at=datetime.now(),
    )
