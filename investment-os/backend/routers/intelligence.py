import uuid
import logging
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from database.connection import get_db
from models.schemas import MFProfileResponse, MFFactsheetResponse, MFAlertResponse, MFSectorWeight, MFStockHolding
from services.mf_intelligence import extract_mf_intelligence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mf", tags=["mf_intelligence"])

async def _run_intelligence_sync():
    """Background task to scrape and analyze all mutual funds in the portfolio."""
    cursor = get_db()
    try:
        # Get distinct MF names currently held
        res = cursor.execute("""
            SELECT DISTINCT asset_name, ticker 
            FROM holdings 
            WHERE asset_class = 'mf'
        """).fetchall()

        for asset_name, isin in res:
            logger.info(f"Syncing MF Intelligence for: {asset_name} ({isin})")
            data = await extract_mf_intelligence(asset_name)
            if not data:
                continue

            # Check if profile already exists to detect alerts
            existing_profile = cursor.execute("SELECT fund_manager, objective, category FROM mf_profiles WHERE isin = ?", (isin,)).fetchone()
            
            if existing_profile:
                old_manager, old_objective, old_category = existing_profile
                
                if old_manager and data.fund_manager and old_manager != data.fund_manager:
                    cursor.execute("""
                        INSERT INTO mf_alerts (id, isin, alert_type, old_value, new_value)
                        VALUES (?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), isin, 'MANAGER_CHANGE', old_manager, data.fund_manager))

                if old_objective and data.objective and old_objective != data.objective:
                    cursor.execute("""
                        INSERT INTO mf_alerts (id, isin, alert_type, old_value, new_value)
                        VALUES (?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), isin, 'OBJECTIVE_CHANGE', old_objective, data.objective))
                    
                if old_category and data.category and old_category != data.category:
                    cursor.execute("""
                        INSERT INTO mf_alerts (id, isin, alert_type, old_value, new_value)
                        VALUES (?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), isin, 'CATEGORY_CHANGE', old_category, data.category))

            # Upsert Profile
            current_time = datetime.now()
            cursor.execute("""
                INSERT INTO mf_profiles (isin, fund_name, category, sub_category, objective, fund_manager, benchmark, expense_ratio, aum_cr, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (isin) DO UPDATE SET
                    category = EXCLUDED.category,
                    sub_category = EXCLUDED.sub_category,
                    objective = EXCLUDED.objective,
                    fund_manager = EXCLUDED.fund_manager,
                    benchmark = EXCLUDED.benchmark,
                    expense_ratio = EXCLUDED.expense_ratio,
                    aum_cr = EXCLUDED.aum_cr,
                    last_updated = EXCLUDED.last_updated
            """, (
                isin, data.fund_name, data.category, data.sub_category, data.objective,
                data.fund_manager, data.benchmark, data.expense_ratio, data.aum_cr, current_time
            ))

            # Insert Factsheet (we store it as the 1st of the current month)
            current_month = date.today().replace(day=1)
            factsheet_id = str(uuid.uuid4())
            
            # Upsert factsheet using ON CONFLICT since (isin, factsheet_month) is UNIQUE
            cursor.execute("""
                INSERT INTO mf_factsheets (id, isin, factsheet_month, equity_pct, debt_pct, cash_pct, 
                                          return_1y, return_3y, return_5y, return_inception,
                                          benchmark_return_1y, benchmark_return_3y, benchmark_return_5y, benchmark_return_inception, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (isin, factsheet_month) DO UPDATE SET
                    equity_pct = EXCLUDED.equity_pct,
                    debt_pct = EXCLUDED.debt_pct,
                    cash_pct = EXCLUDED.cash_pct,
                    return_1y = EXCLUDED.return_1y,
                    return_3y = EXCLUDED.return_3y,
                    return_5y = EXCLUDED.return_5y,
                    return_inception = EXCLUDED.return_inception,
                    benchmark_return_1y = EXCLUDED.benchmark_return_1y,
                    benchmark_return_3y = EXCLUDED.benchmark_return_3y,
                    benchmark_return_5y = EXCLUDED.benchmark_return_5y,
                    benchmark_return_inception = EXCLUDED.benchmark_return_inception,
                    last_updated = EXCLUDED.last_updated
                RETURNING id
            """, (
                factsheet_id, isin, current_month, data.equity_pct, data.debt_pct, data.cash_pct,
                data.return_1y, data.return_3y, data.return_5y, data.return_inception,
                data.benchmark_return_1y, data.benchmark_return_3y, data.benchmark_return_5y, data.benchmark_return_inception, current_time
            ))
            
            res_id = cursor.fetchone()
            if res_id:
                active_factsheet_id = res_id[0]
                
                # Delete existing weights for this factsheet to replace
                cursor.execute("DELETE FROM mf_sector_weights WHERE factsheet_id = ?", (active_factsheet_id,))
                for sector in data.sector_weights:
                    cursor.execute("""
                        INSERT INTO mf_sector_weights (id, factsheet_id, sector_name, weight_pct)
                        VALUES (?, ?, ?, ?)
                    """, (str(uuid.uuid4()), active_factsheet_id, sector.sector_name, sector.weight_pct))
                    
                cursor.execute("DELETE FROM mf_stock_holdings WHERE factsheet_id = ?", (active_factsheet_id,))
                for stock in data.stock_holdings:
                    cursor.execute("""
                        INSERT INTO mf_stock_holdings (id, factsheet_id, stock_name, weight_pct)
                        VALUES (?, ?, ?, ?)
                    """, (str(uuid.uuid4()), active_factsheet_id, stock.stock_name, stock.weight_pct))

    except Exception as e:
        logger.error(f"Intelligence sync failed: {e}")
    finally:
        cursor.close()

@router.post("/sync")
async def trigger_intelligence_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_intelligence_sync)
    return {"status": "started", "message": "Mutual Fund Intelligence sync started in background."}

@router.get("/profiles", response_model=list[MFProfileResponse])
def get_mf_profiles():
    cursor = get_db()
    res = cursor.execute("SELECT * FROM mf_profiles").fetchall()
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in res]

@router.get("/alerts", response_model=list[MFAlertResponse])
def get_mf_alerts():
    cursor = get_db()
    res = cursor.execute("SELECT * FROM mf_alerts ORDER BY alert_date DESC").fetchall()
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in res]

@router.get("/factsheets/{isin}")
def get_mf_factsheets(isin: str):
    cursor = get_db()
    res = cursor.execute("SELECT * FROM mf_factsheets WHERE isin = ? ORDER BY factsheet_month DESC", (isin,)).fetchall()
    cols = [d[0] for d in cursor.description]
    factsheets = [dict(zip(cols, r)) for r in res]
    
    for fs in factsheets:
        sw = cursor.execute("SELECT * FROM mf_sector_weights WHERE factsheet_id = ?", (fs['id'],)).fetchall()
        sw_cols = [d[0] for d in cursor.description]
        fs['sector_weights'] = [dict(zip(sw_cols, s)) for s in sw]
        
        sh = cursor.execute("SELECT * FROM mf_stock_holdings WHERE factsheet_id = ?", (fs['id'],)).fetchall()
        sh_cols = [d[0] for d in cursor.description]
        fs['stock_holdings'] = [dict(zip(sh_cols, s)) for s in sh]
        
    return factsheets
