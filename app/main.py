import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db, get_connection
from app.core.security import configure_cors
from app.routes.health import router as health_router
from app.routes.chat import router as chat_router, ChatRequest, chat_endpoint
from app.routes.webhook import router as webhook_router
from app.routes.seed import router as seed_router


logger = logging.getLogger(__name__)

app = FastAPI(title="Kolan AI Shop Assistant", version="1.0.0")

configure_cors(app)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(webhook_router)
app.include_router(seed_router)


def _check_and_seed():
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
            logger.info("Auto-seeded products on startup")

        if policy_count == 0:
            from app.services.shopify_sync import fetch_shopify_policies
            fetch_shopify_policies()
            logger.info("Auto-seeded policies on startup")
    except Exception as e:
        logger.error("Auto-seed failed: %s", e)


@app.post("/")
async def root_chat(req: ChatRequest):
    return await chat_endpoint(req)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    threading.Thread(target=_check_and_seed, daemon=True).start()
    logger.info("Database initialized")
