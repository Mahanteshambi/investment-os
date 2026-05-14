import json
import logging
from database.connection import get_db
from agents.macro.agent import MacroAgent
from agents.tech_fund.agent import TechFundAgent

logger = logging.getLogger(__name__)

def get_portfolio_summary() -> str:
    """Returns the current portfolio value, invested value, and PnL."""
    try:
        cursor = get_db()
        cursor.execute("SELECT sum(current_value), sum(invested_value), sum(unrealized_pnl) FROM holdings")
        res = cursor.fetchone()
        if not res or res[0] is None:
            return "Portfolio is empty or not synced yet."
        return f"Total Value: ₹{res[0]:.2f}, Invested: ₹{res[1]:.2f}, Unrealized PnL: ₹{res[2]:.2f}"
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        return f"Error: {e}"

def run_data_prefetch() -> str:
    """Fetches and updates the DuckDB database with the latest macro data, market news, and Kite historical OHLCV data. Use this when the user asks to sync or run daily analysis."""
    try:
        from services.world_data_fetcher import prefetch_world_data
        from services.kite_data_fetcher import prefetch_kite_historical_data
        
        prefetch_world_data()
        prefetch_kite_historical_data()
        
        return "Successfully fetched and synced all macro, news, sentiment, and historical price data into DuckDB."
    except Exception as e:
        logger.error(f"Error prefetching data: {e}")
        return f"Error: {e}"

def run_macro_analysis() -> str:
    """Runs the Macro Economist agent to analyze global trends and market regime."""
    try:
        agent = MacroAgent()
        return agent.analyze()
    except Exception as e:
        logger.error(f"Error running MacroAgent: {e}")
        return f"Error: {e}"

def run_technical_analysis() -> str:
    """Runs the Quantitative Analyst agent to evaluate technical momentum."""
    try:
        agent = TechFundAgent()
        return agent.analyze()
    except Exception as e:
        logger.error(f"Error running TechFundAgent: {e}")
        return f"Error: {e}"
