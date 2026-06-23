import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.core.security import configure_cors
from app.routes.health import router as health_router
from app.routes.chat import router as chat_router
from app.routes.webhook import router as webhook_router
from app.services.auto_sync import start_auto_sync

logger = logging.getLogger(__name__)

app = FastAPI(title="Kolan AI Shop Assistant", version="1.0.0")

configure_cors(app)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(webhook_router)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    start_auto_sync()
    logger.info("Auto product sync started (every 5 minutes)")
