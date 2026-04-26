from fastapi import APIRouter, Depends
import duckdb

from database.connection import get_db
from models.schemas import SyncRequest, SyncResponse, SyncStatus
from services import sync_service

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("", response_model=SyncResponse)
def trigger_sync(body: SyncRequest):
    sources = [s.lower() for s in body.sources]
    if "all" in sources:
        return sync_service.sync_all()

    from datetime import datetime
    sources_synced = []
    errors = []
    total_records = 0

    if "kite" in sources:
        count, err = sync_service.sync_kite()
        sources_synced.append("kite")
        total_records += count
        if err:
            errors.append(f"kite: {err}")

    if "sheets" in sources:
        count, err = sync_service.sync_sheets()
        sources_synced.append("sheets")
        total_records += count
        if err:
            errors.append(f"sheets: {err}")

    status = "success" if not errors else ("partial" if total_records > 0 else "failed")
    return SyncResponse(
        status=status,
        sources_synced=sources_synced,
        records_updated=total_records,
        errors=errors,
        synced_at=datetime.now(),
    )


@router.get("/status", response_model=list[SyncStatus])
def get_sync_status(db: duckdb.DuckDBPyConnection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT source, status, records_updated, synced_at, error_message
        FROM sync_log
        WHERE (source, synced_at) IN (
            SELECT source, MAX(synced_at) FROM sync_log GROUP BY source
        )
        ORDER BY source
        """
    ).fetchall()
    return [
        SyncStatus(
            source=r[0], status=r[1], records_updated=r[2],
            synced_at=r[3], error_message=r[4],
        )
        for r in rows
    ]
