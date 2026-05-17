"""
Transactions router — buy/sell history, CSV import, temporal analytics.
"""
from datetime import date, datetime
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database.connection import get_db

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


# ── Schemas ────────────────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    transaction_date: date
    asset_name: str
    ticker: Optional[str] = None
    asset_class: str          # equity | etf | mf | gold | debt | cash
    transaction_type: str     # buy | sell
    quantity: Optional[float] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    fees: float = 0.0
    bucket: Optional[str] = None   # Large Cap | Mid/Small | Sector | Gold | International | Debt
    gtt_id: Optional[str] = None
    exchange: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None


class TransactionOut(TransactionIn):
    id: str
    amount: Optional[float] = None   # computed if missing


class BulkImportRequest(BaseModel):
    transactions: list[TransactionIn]


class BulkImportResponse(BaseModel):
    inserted: int
    skipped: int
    errors: list[str]


class DeploymentPoint(BaseModel):
    date: str
    bucket: str
    amount: float
    cumulative: float


# ── Helpers ────────────────────────────────────────────────────────────────

BUCKET_MAP = {
    "NIFTYBEES": "Large Cap", "SETFNIF50": "Large Cap",
    "JUNIORBEES": "Mid/Small", "MOM100": "Mid/Small",
    "CPSEETF": "Sector", "PHARMABEES": "Sector", "MODEFENCE": "Sector",
    "PSUBNKBEES": "Sector", "ITBEES": "Sector", "BANKBEES": "Sector",
    "GOLDBEES": "Gold",
    "ICICIB22": "International",
    "LIQUIDBEES": "Debt",
}


def infer_bucket(ticker: Optional[str], asset_class: str) -> str:
    if ticker:
        t = ticker.upper().replace("NSE:", "").replace("BSE:", "")
        return BUCKET_MAP.get(t, "Other")
    if asset_class == "gold":
        return "Gold"
    if asset_class == "debt":
        return "Debt"
    if asset_class == "mf":
        return "MF"
    return "Other"


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TransactionOut])
def get_transactions(
    ticker: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    bucket: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(500, le=2000),
):
    db = get_db()
    where = ["1=1"]
    params: list = []

    if ticker:
        where.append("ticker ILIKE ?")
        params.append(f"%{ticker}%")
    if transaction_type:
        where.append("transaction_type = ?")
        params.append(transaction_type.lower())
    if bucket:
        where.append("bucket = ?")
        params.append(bucket)
    if from_date:
        where.append("transaction_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("transaction_date <= ?")
        params.append(to_date)

    sql = f"""
        SELECT id, transaction_date, asset_name, ticker, asset_class,
               transaction_type, quantity, price, amount, fees,
               bucket, gtt_id, exchange, source, notes
        FROM transactions
        WHERE {" AND ".join(where)}
        ORDER BY transaction_date DESC, id DESC
        LIMIT {limit}
    """
    rows = db.execute(sql, params).fetchall()
    cols = ["id", "transaction_date", "asset_name", "ticker", "asset_class",
            "transaction_type", "quantity", "price", "amount", "fees",
            "bucket", "gtt_id", "exchange", "source", "notes"]
    return [TransactionOut(**dict(zip(cols, r))) for r in rows]


@router.get("/summary")
def get_transaction_summary():
    """Aggregate stats for header cards."""
    db = get_db()
    rows = db.execute("""
        SELECT
            COUNT(*) FILTER (WHERE transaction_type = 'buy')  AS total_buys,
            COUNT(*) FILTER (WHERE transaction_type = 'sell') AS total_sells,
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'buy'), 0)  AS total_deployed,
            COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'sell'), 0) AS total_redeemed,
            MIN(transaction_date) AS first_trade,
            MAX(transaction_date) AS last_trade
        FROM transactions
    """).fetchone()
    return {
        "total_buys": rows[0],
        "total_sells": rows[1],
        "total_deployed": rows[2],
        "total_redeemed": rows[3],
        "net_deployed": rows[2] - rows[3],
        "first_trade": str(rows[4]) if rows[4] else None,
        "last_trade": str(rows[5]) if rows[5] else None,
    }


@router.get("/deployment-series")
def get_deployment_series():
    """
    Returns daily cumulative deployment per bucket — for the area chart.
    Only buy transactions counted (deployment = capital put to work).
    """
    db = get_db()
    rows = db.execute("""
        SELECT
            transaction_date::VARCHAR AS date,
            COALESCE(bucket, 'Other') AS bucket,
            SUM(COALESCE(amount, quantity * price, 0)) AS daily_amount
        FROM transactions
        WHERE transaction_type = 'buy'
        GROUP BY transaction_date, bucket
        ORDER BY transaction_date ASC
    """).fetchall()

    # Build cumulative per bucket
    from collections import defaultdict
    cumulative: dict[str, float] = defaultdict(float)
    series: list[dict] = []
    for date_str, bucket, amt in rows:
        cumulative[bucket] += float(amt or 0)
        series.append({
            "date": date_str,
            "bucket": bucket,
            "amount": float(amt or 0),
            "cumulative": cumulative[bucket],
        })
    return series


@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import(req: BulkImportRequest):
    """
    Bulk insert transactions. Skips duplicates (same date + ticker + type + qty).
    Use this to import historical trades from Zerodha Console P&L CSV.
    """
    db = get_db()
    inserted = 0
    skipped = 0
    errors: list[str] = []

    for t in req.transactions:
        try:
            # Deduplicate check
            existing = db.execute("""
                SELECT id FROM transactions
                WHERE transaction_date = ?
                  AND ticker = ?
                  AND transaction_type = ?
                  AND quantity = ?
            """, [t.transaction_date, t.ticker, t.transaction_type, t.quantity]).fetchone()

            if existing:
                skipped += 1
                continue

            amt = t.amount or (
                (t.quantity or 0) * (t.price or 0) + (t.fees or 0)
            )
            bucket = t.bucket or infer_bucket(t.ticker, t.asset_class)
            tid = str(uuid.uuid4())

            db.execute("""
                INSERT INTO transactions
                    (id, transaction_date, asset_name, ticker, asset_class,
                     transaction_type, quantity, price, amount, fees,
                     bucket, gtt_id, exchange, source, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                tid, t.transaction_date, t.asset_name, t.ticker, t.asset_class,
                t.transaction_type.lower(), t.quantity, t.price, amt, t.fees,
                bucket, t.gtt_id, t.exchange, t.source or "manual", t.notes,
            ])
            inserted += 1
        except Exception as e:
            errors.append(f"{t.ticker} {t.transaction_date}: {e}")

    return BulkImportResponse(inserted=inserted, skipped=skipped, errors=errors)
