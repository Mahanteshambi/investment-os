import os
import json
from google.adk.agents.llm_agent import Agent
from database.connection import get_db
from services.data_fetcher import DataFetcherService

def get_portfolio_summary() -> str:
    """Returns the current portfolio value, invested value, and PnL."""
    cursor = get_db()
    cursor.execute("SELECT sum(current_value), sum(invested_value), sum(unrealized_pnl) FROM holdings")
    res = cursor.fetchone()
    if not res or res[0] is None:
        return "Portfolio is empty or not synced yet."
    return f"Total Value: ₹{res[0]:.2f}, Invested: ₹{res[1]:.2f}, Unrealized PnL: ₹{res[2]:.2f}"

def run_data_prefetch() -> str:
    """Fetches and updates historical OHLCV data from Kite API to the local database for major ETFs. Use this when the user asks to run daily analysis."""
    fetcher = DataFetcherService()
    # Note: Tokens are normally fetched dynamically from a watchlist.
    # Hardcoded known Kite tokens for testing:
    tokens = {"NIFTYBEES": 10577154, "GOLDBEES": 3812865, "CPSEETF": 2921985} 
    results = []
    for sym, token in tokens.items():
        res = fetcher.fetch_and_persist_historical_data(sym, token, 10)
        results.append(f"{sym}: {res}")
    return json.dumps(results)

class AgentService:
    def __init__(self):
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY is not set in environment.")
        
        self.cio_agent = Agent(
            model='gemini-2.5-flash',
            name='cio_agent',
            description="Chief Investment Officer",
            instruction="You are the CIO Agent for Mahantesh's Investment OS. Help manage his portfolio. You operate in Malaysia time. Always use the provided tools if the user asks for portfolio status or asks to run daily analysis. Do not hallucinate data. Be concise.",
            tools=[get_portfolio_summary, run_data_prefetch]
        )
        
    def chat(self, user_message: str) -> str:
        # ADK agents are callable.
        response = self.cio_agent(user_message)
        
        # Handle the ADK response type
        if hasattr(response, "text"):
            return response.text
        elif hasattr(response, "content"):
            return response.content
        elif isinstance(response, dict) and "response" in response:
            return response["response"]
        elif isinstance(response, dict) and "text" in response:
            return response["text"]
        return str(response)

