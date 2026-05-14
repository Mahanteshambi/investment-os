import json
import logging
from database.connection import get_db

logger = logging.getLogger(__name__)

def get_latest_price_trends() -> str:
    """Returns the latest closing prices and 10-day moving averages for all tracked symbols."""
    try:
        cursor = get_db()
        # Get the latest 10 days of data for each symbol
        df = cursor.execute("""
            SELECT symbol, price_date, close_price, volume
            FROM historical_prices
            ORDER BY symbol, price_date DESC
        """).fetchdf()
        
        if df.empty:
            return "No historical price data available."
            
        summary = {}
        for symbol, group in df.groupby('symbol'):
            # Take top 10 rows (which are the most recent 10 days)
            recent = group.head(10)
            latest_price = recent.iloc[0]['close_price']
            ma_10 = recent['close_price'].mean()
            
            summary[symbol] = {
                "latest_price": latest_price,
                "10_day_ma": ma_10,
                "trend": "Bullish" if latest_price > ma_10 else "Bearish",
                "latest_date": str(recent.iloc[0]['price_date'])
            }
            
        return json.dumps(summary)
    except Exception as e:
        logger.error(f"Error fetching price trends: {e}")
        return f"Error: {e}"
