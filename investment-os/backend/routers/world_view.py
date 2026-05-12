from fastapi import APIRouter, HTTPException, BackgroundTasks
from database.connection import get_db
from services.world_data_fetcher import fetch_and_store_world_data
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/world-view", tags=["world_view"])

@router.get("/macro")
def get_macro_data(days: int = 30):
    con = get_db()
    start_date = (datetime.now() - timedelta(days=days)).date()
    
    # Get macro data grouped by date
    try:
        data = con.execute("""
            SELECT date, metric, value 
            FROM macro_data 
            WHERE date >= ?
            ORDER BY date ASC
        """, (start_date,)).fetchdf()
        
        if data.empty:
            return []
            
        # Group by date for frontend charts
        result = []
        for date, group in data.groupby('date'):
            entry = {"date": date.isoformat()}
            for _, row in group.iterrows():
                entry[row['metric']] = row['value']
            result.append(entry)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news")
def get_news(limit: int = 15):
    con = get_db()
    try:
        data = con.execute("""
            SELECT id, date, title, source, description 
            FROM news_data 
            ORDER BY date DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchdf()
        
        # Convert date to string for JSON serialization
        if not data.empty:
            data['date'] = data['date'].apply(lambda x: x.isoformat() if x else None)
        return data.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kite")
def get_kite_data():
    con = get_db()
    try:
        data = con.execute("""
            SELECT symbol, price_date as date, close_price 
            FROM historical_prices 
            WHERE symbol IN ('NIFTYBEES', 'GOLDBEES')
            ORDER BY date ASC
        """).fetchdf()
        
        if data.empty:
            return []
            
        result = []
        for date, group in data.groupby('date'):
            entry = {"date": date.isoformat() if isinstance(date, datetime) else str(date)}
            for _, row in group.iterrows():
                entry[row['symbol']] = row['close_price']
            result.append(entry)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from services.kite_data_fetcher import prefetch_kite_historical_data

@router.post("/sync")
def sync_world_data(background_tasks: BackgroundTasks):
    background_tasks.add_task(fetch_and_store_world_data)
    background_tasks.add_task(prefetch_kite_historical_data)
    return {"status": "Sync started in background"}
