import hashlib
import hmac
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException

from app.core.config import settings
from app.services.shopify_sync import upsert_product, delete_product

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_webhook(request: Request, body: bytes) -> bool:
    if not settings.shopify_webhook_secret:
        return True
    signature = request.headers.get("X-Shopify-Hmac-Sha256", "")
    expected = hmac.new(
        settings.shopify_webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


@router.post("/webhook/update")
async def webhook_update(request: Request) -> Dict[str, str]:
    body = await request.body()

    if not verify_webhook(request, body):
        raise HTTPException(status_code=401, detail="Invalid signature")

    topic = request.headers.get("X-Shopify-Topic", "")

    import json
    payload: Dict[str, Any] = json.loads(body)

    if topic == "products/create" or topic == "products/update":
        upsert_product(payload)
    elif topic == "products/delete":
        shopify_id = str(payload.get("id"))
        delete_product(shopify_id)
    else:
        logger.warning("Unhandled topic: %s", topic)

    return {"status": "ok"}
