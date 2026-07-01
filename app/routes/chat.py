import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.database import get_connection
from app.services.shopify_sync import fetch_shopify_policies, sync_collections
from app.services.ai_router import route_chat

router = APIRouter()
logger = logging.getLogger(__name__)

_lazy_seeded = False


async def _ensure_seeded():
    global _lazy_seeded
    if _lazy_seeded:
        return
    try:
        conn = get_connection()
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        policy_count = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        conn.close()

        if product_count == 0:
            import httpx
            from app.services.shopify_sync import upsert_product
            page = 1
            while True:
                resp = httpx.get("https://kolan.co.in/products.json", params={"limit": 250, "page": page}, timeout=30)
                resp.raise_for_status()
                items = resp.json().get("products", [])
                if not items:
                    break
                for p in items:
                    upsert_product(p)
                page += 1
            logger.info("Lazy-seeded products")

        if policy_count == 0:
            fetch_shopify_policies()
            sync_collections()
            logger.info("Lazy-seeded policies and collections")

    except Exception as e:
        logger.error("Lazy seed failed: %s", e)
    _lazy_seeded = True
 

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
    await _ensure_seeded()
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
