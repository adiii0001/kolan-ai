import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.ai_router import route_chat

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    answer: str
    products: List[Dict[str, Any]] = []


_sessions: Dict[str, List[Dict[str, str]]] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or "default"
    if session_id not in _sessions:
        _sessions[session_id] = []

    history = _sessions[session_id]

    result = await route_chat(req.message, history, context=req.context)

    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": result["answer"]})

    if len(history) > 40:
        history[:] = history[-40:]

    return ChatResponse(answer=result["answer"], products=result["products"])
