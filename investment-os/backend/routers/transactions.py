"""
Transactions router — buy/sell history, CSV import, temporal analytics, XIRR, P&L.
"""
from datetime import date, datetime
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


# ── XIRR helper ────────────────────────────────────────────────────────────

def _xirr(cashflows: list[tuple]) -> Optional[float]:
    """
    Calculate XIRR from list of (date, amount) tuples.
    Buys = negative amounts, sells/terminal = positive amounts.
    Returns annualised rate or None if insufficient data.
    """
    if not cashflows or len(cashflows) < 2:
        return None
    dates = [cf[0] for cf in cashflows]
    amounts = [float(cf[1]) for cf in cashflows]
    if not any(a < 0 for a in amounts) or not any(a > 0 for a in amounts):
        return None
    min_date = min(dates)
    years = [(d - min_date).days / 365.0 for d in dates]

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** t for a, t in zip(amounts, years))

    try:
        from scipy.optimize import brentq
        return brentq(npv, -0.9999, 100.0, maxiter=1000)
    except Exception:
        return None

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


@router.get("/xirr")
def get_xirr():
    """
    Compute overall XIRR and per-bucket XIRR using transaction cashflows
    + current holdings value as terminal cashflow.
    """
    db = get_db()
    today = date.today()

    # All transactions (buy = negative cashflow, sell = positive)
    txns = db.execute("""
        SELECT transaction_date, transaction_type,
               COALESCE(amount, quantity * price, 0) AS amount,
               COALESCE(bucket, 'Other') AS bucket
        FROM transactions
        WHERE COALESCE(amount, quantity * price, 0) > 0
        ORDER BY transaction_date ASC
    """).fetchall()

    # Only use holdings for tickers that appear in transactions (scope terminal value correctly)
    holdings = db.execute("""
        SELECT
            UPPER(COALESCE(h.ticker, h.asset_name)) AS ticker,
            COALESCE(h.current_value, 0)             AS current_value
        FROM holdings h
        WHERE h.current_value IS NOT NULL AND h.current_value > 0
          AND UPPER(COALESCE(h.ticker, h.asset_name)) IN (
              SELECT DISTINCT UPPER(COALESCE(ticker, asset_name)) FROM transactions
          )
    """).fetchall()

    # Build ticker → current_value lookup
    holding_map: dict[str, float] = {r[0]: float(r[1]) for r in holdings}

    # Build per-bucket current values from holdings using BUCKET_MAP
    bucket_current: dict[str, float] = {}
    for ticker, val in holding_map.items():
        b = BUCKET_MAP.get(ticker, "Other")
        bucket_current[b] = bucket_current.get(b, 0.0) + val

    total_current = sum(bucket_current.values())

    # ── Overall XIRR ─────────────────────────────────────────────────────
    all_cfs: list[tuple] = []
    for txn_date, txn_type, amount, _ in txns:
        sign = -1 if txn_type == "buy" else 1
        all_cfs.append((txn_date, sign * float(amount)))
    if total_current > 0:
        all_cfs.append((today, total_current))
    overall = _xirr(all_cfs)

    # ── Per-bucket XIRR ───────────────────────────────────────────────────
    from collections import defaultdict
    bucket_cfs: dict[str, list] = defaultdict(list)
    for txn_date, txn_type, amount, bucket in txns:
        sign = -1 if txn_type == "buy" else 1
        bucket_cfs[bucket].append((txn_date, sign * float(amount)))
    for b, val in bucket_current.items():
        if val > 0:
            bucket_cfs[b].append((today, val))

    per_bucket = {b: _xirr(cfs) for b, cfs in bucket_cfs.items()}

    # ── Simple money-weighted return (honest for short portfolios) ───────────
    total_invested = sum(float(a) for _, txn_type, a, _ in txns if txn_type == "buy")
    total_redeemed = sum(float(a) for _, txn_type, a, _ in txns if txn_type == "sell")
    simple_return_pct = (
        round((total_redeemed + total_current - total_invested) / total_invested * 100, 2)
        if total_invested > 0 else None
    )

    # Per-bucket simple return
    bucket_invested: dict[str, float] = {}
    bucket_redeemed: dict[str, float] = {}
    for _, txn_type, amount, bucket in txns:
        if txn_type == "buy":
            bucket_invested[bucket] = bucket_invested.get(bucket, 0.0) + float(amount)
        else:
            bucket_redeemed[bucket] = bucket_redeemed.get(bucket, 0.0) + float(amount)

    per_bucket_simple: dict[str, float | None] = {}
    for b in set(list(bucket_invested.keys()) + list(bucket_current.keys())):
        inv = bucket_invested.get(b, 0.0)
        red = bucket_redeemed.get(b, 0.0)
        cur = bucket_current.get(b, 0.0)
        per_bucket_simple[b] = round((red + cur - inv) / inv * 100, 2) if inv > 0 else None

    # Days since first trade — for context
    dates_only = [cf[0] for cf in all_cfs if cf[1] < 0]
    days_active = (today - min(dates_only)).days if dates_only else 0

    return {
        "overall_xirr": round(overall * 100, 2) if overall is not None else None,
        "simple_return_pct": simple_return_pct,
        "per_bucket": {
            b: round(v * 100, 2) if v is not None else None
            for b, v in per_bucket.items()
        },
        "per_bucket_simple": per_bucket_simple,
        "total_current_value": round(total_current, 2),
        "total_invested": round(total_invested, 2),
        "days_active": days_active,
    }


@router.get("/pnl-by-symbol")
def get_pnl_by_symbol():
    """
    Per-ticker P&L summary: total invested, total redeemed, current value,
    net return, return %, avg cost.
    """
    db = get_db()

    txns = db.execute("""
        SELECT
            COALESCE(ticker, asset_name)                              AS symbol,
            COALESCE(bucket, 'Other')                                 AS bucket,
            SUM(CASE WHEN transaction_type='buy'  THEN COALESCE(amount, quantity*price, 0) ELSE 0 END) AS invested,
            SUM(CASE WHEN transaction_type='sell' THEN COALESCE(amount, quantity*price, 0) ELSE 0 END) AS redeemed,
            SUM(CASE WHEN transaction_type='buy'  THEN quantity ELSE -quantity END)                    AS net_qty,
            COUNT(*) FILTER (WHERE transaction_type='buy')                                             AS buy_count,
            COUNT(*) FILTER (WHERE transaction_type='sell')                                            AS sell_count,
            MIN(transaction_date)                                     AS first_trade,
            MAX(transaction_date)                                     AS last_trade
        FROM transactions
        GROUP BY symbol, bucket
        ORDER BY invested DESC
    """).fetchall()

    holdings = db.execute("""
        SELECT UPPER(COALESCE(ticker, asset_name)), current_value, current_price, avg_cost
        FROM holdings
        WHERE current_value IS NOT NULL
    """).fetchall()
    holding_map = {r[0]: {"current_value": float(r[1] or 0), "current_price": r[2], "avg_cost": r[3]}
                   for r in holdings}

    result = []
    for symbol, bucket, invested, redeemed, net_qty, buy_count, sell_count, first_trade, last_trade in txns:
        invested = float(invested or 0)
        redeemed = float(redeemed or 0)
        current = holding_map.get(symbol.upper(), {}).get("current_value", 0.0)
        total_return = redeemed + current - invested
        return_pct = (total_return / invested * 100) if invested > 0 else 0
        result.append({
            "symbol": symbol,
            "bucket": bucket,
            "invested": round(invested, 2),
            "redeemed": round(redeemed, 2),
            "current_value": round(current, 2),
            "total_return": round(total_return, 2),
            "return_pct": round(return_pct, 2),
            "net_qty": round(float(net_qty or 0), 4),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "first_trade": str(first_trade) if first_trade else None,
            "last_trade": str(last_trade) if last_trade else None,
        })
    return result
