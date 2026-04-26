import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import duckdb

from database.connection import get_db
from models.schemas import HoldingCreate, HoldingResponse

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


def _row_to_holding(row) -> HoldingResponse:
    return HoldingResponse(
        id=row[0],
        asset_name=row[1],
        ticker=row[2],
        asset_class=row[3],
        sub_class=row[4],
        source=row[5],
        quantity=row[6],
        avg_cost=row[7],
        current_price=row[8],
        current_value=row[9],
        invested_value=row[10],
        unrealized_pnl=row[11],
        unrealized_pnl_pct=row[12],
        sector=row[13],
        last_updated=row[14],
    )


SORT_MAP = {
    "pnl": "unrealized_pnl",
    "pnl_pct": "unrealized_pnl_pct",
    "value": "current_value",
    "name": "asset_name",
    "invested": "invested_value",
}


@router.get("", response_model=list[HoldingResponse])
def get_holdings(
    asset_class: Optional[str] = None,
    source: Optional[str] = None,
    sort: Optional[str] = None,
    db: duckdb.DuckDBPyConnection = Depends(get_db),
):
    where_clauses = []
    params = []
    if asset_class:
        where_clauses.append("asset_class = ?")
        params.append(asset_class)
    if source:
        where_clauses.append("source = ?")
        params.append(source)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sort_col = SORT_MAP.get(sort or "", "asset_name")
    order_sql = f"ORDER BY {sort_col} DESC" if sort in SORT_MAP else f"ORDER BY {sort_col} ASC"

    rows = db.execute(
        f"SELECT * FROM holdings {where_sql} {order_sql}", params
    ).fetchall()
    return [_row_to_holding(r) for r in rows]


@router.get("/{holding_id}", response_model=HoldingResponse)
def get_holding(holding_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)):
    row = db.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    return _row_to_holding(row)


@router.post("", response_model=HoldingResponse, status_code=201)
def create_holding(body: HoldingCreate, db: duckdb.DuckDBPyConnection = Depends(get_db)):
    body.source = "manual"
    now = datetime.now()
    db.execute(
        """
        INSERT INTO holdings (
            id, asset_name, ticker, asset_class, sub_class, source,
            quantity, avg_cost, current_price, current_value,
            invested_value, unrealized_pnl, unrealized_pnl_pct, sector, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            body.id, body.asset_name, body.ticker, body.asset_class, body.sub_class, body.source,
            body.quantity, body.avg_cost, body.current_price, body.current_value,
            body.invested_value, body.unrealized_pnl, body.unrealized_pnl_pct, body.sector, now,
        ],
    )
    row = db.execute("SELECT * FROM holdings WHERE id = ?", [body.id]).fetchone()
    return _row_to_holding(row)


@router.put("/{holding_id}", response_model=HoldingResponse)
def update_holding(holding_id: str, body: HoldingCreate, db: duckdb.DuckDBPyConnection = Depends(get_db)):
    existing = db.execute("SELECT id FROM holdings WHERE id = ?", [holding_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    now = datetime.now()
    db.execute(
        """
        UPDATE holdings SET
            asset_name=?, ticker=?, asset_class=?, sub_class=?, source=?,
            quantity=?, avg_cost=?, current_price=?, current_value=?,
            invested_value=?, unrealized_pnl=?, unrealized_pnl_pct=?,
            sector=?, last_updated=?
        WHERE id=?
        """,
        [
            body.asset_name, body.ticker, body.asset_class, body.sub_class, body.source,
            body.quantity, body.avg_cost, body.current_price, body.current_value,
            body.invested_value, body.unrealized_pnl, body.unrealized_pnl_pct,
            body.sector, now, holding_id,
        ],
    )
    row = db.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    return _row_to_holding(row)


@router.delete("/{holding_id}", status_code=204)
def delete_holding(holding_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)):
    existing = db.execute("SELECT id FROM holdings WHERE id = ?", [holding_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.execute("DELETE FROM holdings WHERE id = ?", [holding_id])
