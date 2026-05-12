import logging
from datetime import datetime, timedelta
import pandas as pd
from database.connection import get_db
from services.kite_service import KiteService

logger = logging.getLogger(__name__)

# Predefined Kite instrument tokens for the watchlist
WATCHLIST_TOKENS = {
    "NIFTYBEES": 1057537,
    "GOLDBEES": 2841601,
    "JUNIORBEES": 2661633,
    "BANKBEES": 2736129,
    "LIQUIDBEES": 2939649
}

def prefetch_kite_historical_data():
    """Fetches end-of-day OHLC data for the watchlist and stores it in DuckDB."""
    logger.info("Starting Kite historical data prefetch...")
    kite_service = KiteService()
    
    if not kite_service.is_connected():
        logger.warning("Kite is not connected. Falling back to yfinance for historical data prefetch.")
        con = get_db()
        yf_tickers = {
            "NIFTYBEES": "NIFTYBEES.NS",
            "GOLDBEES": "GOLDBEES.NS",
            "JUNIORBEES": "JUNIORBEES.NS",
            "BANKBEES": "BANKBEES.NS",
            "LIQUIDBEES": "LIQUIDBEES.NS"
        }
        for symbol, yf_ticker in yf_tickers.items():
            try:
                import yfinance as yf
                t = yf.Ticker(yf_ticker)
                df = t.history(period="30d")
                df.reset_index(inplace=True)
                for _, row in df.iterrows():
                    date_str = str(row['Date'].date())
                    con.execute("""
                        INSERT INTO historical_prices (symbol, price_date, open_price, high_price, low_price, close_price, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (symbol, price_date) DO UPDATE SET 
                            open_price = excluded.open_price,
                            high_price = excluded.high_price,
                            low_price = excluded.low_price,
                            close_price = excluded.close_price,
                            volume = excluded.volume
                    """, (
                        symbol, date_str, row['Open'], row['High'], row['Low'], row['Close'], row['Volume']
                    ))
                logger.info(f"Successfully stored yfinance fallback data for {symbol}.")
            except Exception as e:
                logger.error(f"yfinance fallback failed for {symbol}: {e}")
        return

    con = get_db()
    to_date = datetime.now().strftime("%Y-%m-%d")
    # Fetch last 30 days of daily candles
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    for symbol, token in WATCHLIST_TOKENS.items():
        try:
            logger.info(f"Fetching historical data for {symbol}...")
            candles = kite_service.get_historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            for candle in candles:
                date_str = str(candle['date']).split(' ')[0]
                con.execute("""
                    INSERT INTO historical_prices (symbol, price_date, open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (symbol, price_date) DO UPDATE SET 
                        open_price = excluded.open_price,
                        high_price = excluded.high_price,
                        low_price = excluded.low_price,
                        close_price = excluded.close_price,
                        volume = excluded.volume
                """, (
                    symbol, date_str, candle['open'], candle['high'], candle['low'], candle['close'], candle['volume']
                ))
            logger.info(f"Successfully stored {len(candles)} days of data for {symbol}.")
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol} via Kite: {e}. Falling back to yfinance.")
            # Yfinance fallback
            yf_tickers = {
                "NIFTYBEES": "NIFTYBEES.NS",
                "GOLDBEES": "GOLDBEES.NS",
                "JUNIORBEES": "JUNIORBEES.NS",
                "BANKBEES": "BANKBEES.NS",
                "LIQUIDBEES": "LIQUIDBEES.NS"
            }
            yf_ticker = yf_tickers.get(symbol)
            if yf_ticker:
                try:
                    import yfinance as yf
                    t = yf.Ticker(yf_ticker)
                    df = t.history(period="30d")
                    df.reset_index(inplace=True)
                    for _, row in df.iterrows():
                        date_str = str(row['Date'].date())
                        con.execute("""
                            INSERT INTO historical_prices (symbol, price_date, open_price, high_price, low_price, close_price, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (symbol, price_date) DO UPDATE SET 
                                open_price = excluded.open_price,
                                high_price = excluded.high_price,
                                low_price = excluded.low_price,
                                close_price = excluded.close_price,
                                volume = excluded.volume
                        """, (
                            symbol, date_str, row['Open'], row['High'], row['Low'], row['Close'], row['Volume']
                        ))
                    logger.info(f"Successfully stored yfinance fallback data for {symbol}.")
                except Exception as yf_e:
                    logger.error(f"yfinance fallback failed for {symbol}: {yf_e}")

    logger.info("Kite historical data prefetch complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    prefetch_kite_historical_data()
