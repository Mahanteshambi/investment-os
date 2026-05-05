from fastapi import APIRouter, Depends, Query
import duckdb

from database.connection import get_db
from models.schemas import AllocationBreakdown, DailySnapshot, HoldingResponse, PortfolioSummary
from services.analytics_service import calculate_portfolio_summary, calculate_sector_exposure

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _fetch_holdings(db: duckdb.DuckDBPyConnection) -> list[HoldingResponse]:
    from datetime import datetime
    rows = db.execute("""
        SELECT id, asset_name, ticker, asset_class, sub_class, source, platform, 
               quantity, avg_cost, current_price, current_value, invested_value, 
               unrealized_pnl, unrealized_pnl_pct, sector, last_updated 
        FROM holdings ORDER BY current_value DESC NULLS LAST
    """).fetchall()
    return [
        HoldingResponse(
            id=r[0], asset_name=r[1], ticker=r[2], asset_class=r[3], sub_class=r[4],
            source=r[5], platform=r[6], quantity=r[7], avg_cost=r[8], current_price=r[9],
            current_value=r[10], invested_value=r[11], unrealized_pnl=r[12],
            unrealized_pnl_pct=r[13], sector=r[14], last_updated=r[15] or datetime.now(),
        )
        for r in rows
    ]


def _fetch_previous_snapshot(db: duckdb.DuckDBPyConnection) -> dict | None:
    row = db.execute(
        "SELECT total_value FROM daily_snapshots ORDER BY snapshot_date DESC LIMIT 1 OFFSET 1"
    ).fetchone()
    return {"total_value": row[0]} if row else None


def _fetch_last_sync(db: duckdb.DuckDBPyConnection):
    row = db.execute(
        "SELECT MAX(synced_at) FROM sync_log WHERE status != 'failed'"
    ).fetchone()
    return row[0] if row else None


@router.get("/summary", response_model=PortfolioSummary)
def get_portfolio_summary(db: duckdb.DuckDBPyConnection = Depends(get_db)):
    holdings = _fetch_holdings(db)
    prev_snapshot = _fetch_previous_snapshot(db)
    last_synced = _fetch_last_sync(db)
    return calculate_portfolio_summary(holdings, prev_snapshot, last_synced=last_synced)


@router.get("/allocation", response_model=AllocationBreakdown)
def get_allocation(db: duckdb.DuckDBPyConnection = Depends(get_db)):
    holdings = _fetch_holdings(db)
    total_value = sum(h.current_value or 0 for h in holdings)

    by_class: dict[str, float] = {}
    if total_value > 0:
        class_totals: dict[str, float] = {}
        for h in holdings:
            class_totals[h.asset_class] = class_totals.get(h.asset_class, 0.0) + (h.current_value or 0)
        by_class = {k: round(v, 2) for k, v in class_totals.items()}

    by_sector = calculate_sector_exposure(holdings)
    return AllocationBreakdown(by_class=by_class, by_sector=by_sector)


@router.get("/performance", response_model=list[DailySnapshot])
def get_performance(days: int = Query(default=90, ge=1, le=1825), db: duckdb.DuckDBPyConnection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT snapshot_date, total_value, invested_value, total_pnl, total_pnl_pct,
               equity_pct, mf_pct, gold_pct, cash_pct, debt_pct, nifty50_value
        FROM daily_snapshots
        WHERE snapshot_date >= CURRENT_DATE - (? * INTERVAL '1 day')
        ORDER BY snapshot_date ASC
        """,
        [days],
    ).fetchall()
    return [
        DailySnapshot(
            snapshot_date=r[0], total_value=r[1], invested_value=r[2],
            total_pnl=r[3], total_pnl_pct=r[4], equity_pct=r[5],
            mf_pct=r[6], gold_pct=r[7], cash_pct=r[8], debt_pct=r[9],
            nifty50_value=r[10],
        )
        for r in rows
    ]
