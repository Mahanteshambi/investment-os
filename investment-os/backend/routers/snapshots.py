from fastapi import APIRouter, Depends, Query
import duckdb

from database.connection import get_db
from models.schemas import DailySnapshot

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("", response_model=list[DailySnapshot])
def get_snapshots(
    days: int = Query(default=30, ge=1, le=1825),
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    rows = db.execute(
        """
        SELECT snapshot_date, total_value, invested_value, total_pnl, total_pnl_pct,
               equity_pct, mf_pct, gold_pct, cash_pct, debt_pct, nifty50_value
        FROM daily_snapshots
        WHERE snapshot_date >= CURRENT_DATE - INTERVAL ? DAY
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
