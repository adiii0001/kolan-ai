import logging

import httpx
from fastapi import APIRouter, HTTPException
from app.core.database import init_db, get_connection
from app.services.shopify_sync import upsert_product, fetch_shopify_policies

logger = logging.getLogger(__name__)
router = APIRouter()

STORE_URL = "https://kolan.co.in"


def fetch_all_products():
    products = []
    page = 1
    while True:
        resp = httpx.get(f"{STORE_URL}/products.json", params={"limit": 250, "page": page}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("products", [])
        if not items:
            break
        products.extend(items)
        page += 1
    return products


@router.get("/seed")
@router.post("/seed")
async def seed_products():
    try:
        init_db()
        products = fetch_all_products()
        for p in products:
            upsert_product(p)
        fetch_shopify_policies()
        return {"status": "ok", "products_seeded": len(products), "policies_seeded": 5}
    except Exception as e:
        logger.error("Seed failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
