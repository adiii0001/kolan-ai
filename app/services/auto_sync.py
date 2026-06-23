import logging
import threading
import time

import httpx
from app.core.database import init_db
from app.services.shopify_sync import upsert_product

logger = logging.getLogger(__name__)

STORE_URL = "https://kolan.co.in"
SYNC_INTERVAL_SECONDS = 300  # 5 minutes


def fetch_all_products():
    products = []
    page = 1
    while True:
        try:
            resp = httpx.get(f"{STORE_URL}/products.json", params={"limit": 250, "page": page}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("products", [])
            if not items:
                break
            products.extend(items)
            page += 1
        except Exception as e:
            logger.error("Auto-sync fetch error on page %d: %s", page, e)
            break
    return products


def sync_once():
    try:
        products = fetch_all_products()
        if not products:
            logger.warning("Auto-sync fetched 0 products")
            return
        for p in products:
            upsert_product(p)
        logger.info("Auto-sync: synced %d products", len(products))
    except Exception as e:
        logger.error("Auto-sync failed: %s", e)


def sync_loop():
    init_db()
    logger.info("Auto-sync thread started (interval=%ds)", SYNC_INTERVAL_SECONDS)
    while True:
        sync_once()
        time.sleep(SYNC_INTERVAL_SECONDS)


def start_auto_sync():
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    logger.info("Auto-sync background thread launched")
