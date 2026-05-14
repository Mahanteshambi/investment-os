import logging
from agents.cio.agent import CIOAgent

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        try:
            self.cio_agent = CIOAgent()
        except Exception as e:
            logger.error(f"Failed to initialize CIO Agent: {e}")
            self.cio_agent = None
            
    def chat(self, user_message: str) -> str:
        """Sends a message to the CIO agent and returns the response."""
        if not self.cio_agent:
            return "Error: CIO Agent is not properly configured. Check API keys."
            
        try:
            return self.cio_agent.chat(user_message)
        except Exception as e:
            logger.error(f"CIO Agent chat failed: {e}")
            return f"I encountered an error processing your request: {e}"
