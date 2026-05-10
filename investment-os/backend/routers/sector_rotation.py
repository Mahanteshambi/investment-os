import logging
from fastapi import APIRouter, HTTPException

from services import sector_rotation_service as srs
from services.kite_service import KiteService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sector-rotation", tags=["sector-rotation"])

_kite = KiteService()


@router.get("")
def get_sector_rotation():
    try:
        return srs.load()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to load sector_rotation.json: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
def sync_sector_rotation():
    """Fetch fresh OHLCV from Kite and recompute technical scores.
    Qualitative fundamental and FII/DII scores are preserved from the last Claude analysis."""
    try:
        data = srs.sync_technical_scores(_kite)
        errors = data.get("_sync_errors", [])
        return {
            "status": "ok",
            "synced_at": data.get("_last_technical_sync"),
            "sectors_updated": len(data["current_month"]["scores"]),
            "errors": errors,
            "data": data,
        }
    except RuntimeError as e:
        # Kite not connected or credentials missing
        raise HTTPException(status_code=503, detail=f"Kite unavailable: {e}")
    except Exception as e:
        logger.error(f"Sector rotation sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
