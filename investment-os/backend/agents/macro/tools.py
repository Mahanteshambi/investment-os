import json
import logging
from database.connection import get_db

logger = logging.getLogger(__name__)

def get_latest_macro_data() -> str:
    """Returns the most recent macro metrics (DXY, Brent Crude, US 10Y Yield)."""
    try:
        cursor = get_db()
        df = cursor.execute("""
            SELECT metric, value, date 
            FROM macro_data 
            WHERE date >= current_date() - INTERVAL 7 DAY
            ORDER BY date DESC
        """).fetchdf()
        
        if df.empty:
            return "No macro data available."
            
        # Get the latest value for each metric
        latest_data = df.groupby('metric').first().to_dict(orient='index')
        result = {metric: row['value'] for metric, row in latest_data.items()}
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error fetching macro data: {e}")
        return f"Error: {e}"

def get_latest_market_news() -> str:
    """Returns the latest market intelligence news and sentiment."""
    try:
        cursor = get_db()
        df = cursor.execute("""
            SELECT title, source, description, date 
            FROM news_data 
            ORDER BY date DESC, id DESC
            LIMIT 10
        """).fetchdf()
        
        if df.empty:
            return "No news data available."
            
        # Convert to string for the LLM
        articles = []
        for _, row in df.iterrows():
            articles.append(f"- [{row['source']}] {row['title']}: {row['description']}")
        return "\\n".join(articles)
    except Exception as e:
        logger.error(f"Error fetching news data: {e}")
        return f"Error: {e}"
