import logging
from datetime import datetime, timedelta
from database.connection import get_db
from services.kite_service import KiteService

logger = logging.getLogger(__name__)

class DataFetcherService:
    def __init__(self):
        self.kite_service = KiteService()

    def fetch_and_persist_historical_data(self, symbol: str, instrument_token: int, default_days_back: int = 200):
        """
        Fetches historical data for a symbol as a delta from the last fetched date.
        If no data exists, fetches the default_days_back.
        """
        cursor = get_db()
        
        # Check the last fetched date for this symbol
        cursor.execute("SELECT MAX(price_date) FROM historical_prices WHERE symbol = ?", (symbol,))
        result = cursor.fetchone()
        
        last_date = result[0] if result and result[0] else None
        
        today = datetime.now().date()
        
        if last_date:
            # We already have data, start from the day after the last date
            if isinstance(last_date, str):
                last_date = datetime.strptime(last_date, "%Y-%m-%d").date()
            from_date = last_date + timedelta(days=1)
        else:
            # No data, fetch historical backfill
            from_date = today - timedelta(days=default_days_back)
            
        if from_date > today:
            logger.info(f"{symbol}: Historical data is already up to date.")
            return {"status": "up_to_date", "fetched_records": 0}

        logger.info(f"Fetching historical data for {symbol} from {from_date} to {today}")
        
        try:
            candles = self.kite_service.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=today.strftime("%Y-%m-%d"),
                interval="day"
            )
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return {"status": "error", "message": str(e)}

        if not candles:
            return {"status": "success", "fetched_records": 0}

        # Persist the delta to the database
        records_inserted = 0
        for candle in candles:
            # Kite returns date as datetime object or string depending on client version
            # e.g., {'date': datetime.datetime(2023, 10, 10, 0, 0, tzinfo=tzoffset(None, 19800)), 'open': 100, ...}
            candle_date = candle['date']
            if isinstance(candle_date, str):
                parsed_date = datetime.fromisoformat(candle_date.replace("Z", "+00:00")).date()
            else:
                parsed_date = candle_date.date()
                
            cursor.execute("""
                INSERT OR IGNORE INTO historical_prices 
                (symbol, price_date, open_price, high_price, low_price, close_price, volume) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                parsed_date.isoformat(),
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume']
            ))
            records_inserted += 1

        cursor.commit()
        logger.info(f"Persisted {records_inserted} records for {symbol}.")
        
        return {"status": "success", "fetched_records": records_inserted}
