import yfinance as yf
import pandas as pd
import requests
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
import logging

from database.connection import get_db

logger = logging.getLogger(__name__)

def fetch_and_store_world_data():
    load_dotenv()
    news_api_key = os.getenv("NEWS_API_KEY")
    con = get_db()
    
    logger.info("Fetching Macro Data (DXY, Brent, US10Y)...")
    tickers = {"DXY": "DX-Y.NYB", "Brent_Crude": "BZ=F", "US_10Y": "^TNX"}
    
    # Process macro data
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="7d")
            df.reset_index(inplace=True)
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            
            for _, row in df.iterrows():
                # Upsert to macro_data table
                con.execute("""
                    INSERT INTO macro_data (date, metric, value) 
                    VALUES (?, ?, ?)
                    ON CONFLICT (date, metric) DO UPDATE SET value = excluded.value
                """, (row['Date'], name, row['Close']))
        except Exception as e:
            logger.error(f"Failed to fetch {name}: {e}")
            
    logger.info("Fetching Market News...")
    try:
        if news_api_key:
            url = f"https://newsapi.org/v2/everything?q=markets OR finance OR economy&language=en&sortBy=publishedAt&apiKey={news_api_key}&pageSize=10"
            response = requests.get(url)
            data = response.json()
            
            if 'articles' in data:
                for article in data['articles']:
                    pub_date = pd.to_datetime(article['publishedAt']).date()
                    title = article.get('title')
                    source = article.get('source', {}).get('name')
                    description = article.get('description')
                    
                    if title:
                        con.execute("""
                            INSERT INTO news_data (id, date, title, source, description) 
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT (id) DO NOTHING
                        """, (str(uuid.uuid4()), pub_date, title, source, description))
            else:
                logger.warning(f"News API returned no articles: {data}")
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        
    logger.info("Fetching Alpha Vantage Market Sentiment...")
    av_api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if av_api_key:
        try:
            av_url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=FOREX:USD&apikey={av_api_key}"
            av_res = requests.get(av_url)
            av_data = av_res.json()
            if "feed" in av_data:
                for article in av_data["feed"][:5]:  # Top 5 sentiment articles
                    pub_date_str = article.get("time_published", "")
                    if pub_date_str:
                        # AV format is YYYYMMDDTHHMMSS
                        pub_date = datetime.strptime(pub_date_str, "%Y%m%dT%H%M%S").date()
                        title = article.get("title")
                        source = article.get("source")
                        description = article.get("summary")
                        con.execute("""
                            INSERT INTO news_data (id, date, title, source, description) 
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT (id) DO NOTHING
                        """, (str(uuid.uuid4()), pub_date, f"[AV Sentiment] {title}", source, description))
        except Exception as e:
            logger.error(f"Failed to fetch Alpha Vantage data: {e}")
            
    logger.info("World data fetch complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetch_and_store_world_data()
