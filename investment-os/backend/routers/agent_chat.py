from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from services.agent_service import AgentService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@router.post("/", response_model=ChatResponse)
def handle_chat(req: ChatRequest):
    if not os.getenv("GEMINI_API_KEY"):
        return ChatResponse(response="ERROR: GEMINI_API_KEY is missing from the backend `.env` file. Please add it first.")
        
    try:
        service = AgentService()
        resp_text = service.chat(req.message)
        return ChatResponse(response=resp_text)
    except Exception as e:
        logger.error(f"Agent Chat Error: {e}")
        return ChatResponse(response=f"Agent Error: {str(e)}")
