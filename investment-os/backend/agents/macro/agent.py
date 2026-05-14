import os
import logging
from google.adk.agents.llm_agent import Agent
from agents.macro.config import AGENT_NAME, MODEL_NAME, DESCRIPTION
from agents.macro.tools import get_latest_macro_data, get_latest_market_news

logger = logging.getLogger(__name__)

class MacroAgent:
    def __init__(self):
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY is not set in environment.")
            
        with open(os.path.join(os.path.dirname(__file__), "instructions.md"), "r") as f:
            instruction = f.read()
            
        self.agent = Agent(
            model=MODEL_NAME,
            name=AGENT_NAME,
            description=DESCRIPTION,
            instruction=instruction,
            tools=[get_latest_macro_data, get_latest_market_news]
        )
        
    def analyze(self) -> str:
        """Triggers the agent to generate a macro report."""
        logger.info("MacroAgent is analyzing data...")
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        import asyncio
        
        session_service = InMemorySessionService()
        asyncio.run(session_service.create_session(app_name="investment_os", user_id="system", session_id="macro_session"))
        
        runner = Runner(agent=self.agent, app_name="investment_os", session_service=session_service)
        msg = types.Content(role='user', parts=[types.Part.from_text(text="Please generate the daily macro analysis report based on the latest data.")])
        events = runner.run(user_id="system", session_id="macro_session", new_message=msg)
        
        response_text = ""
        for event in events:
            if hasattr(event, "content") and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
        return response_text
