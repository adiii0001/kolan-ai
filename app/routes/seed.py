import logging
from fastapi import APIRouter, HTTPException
from seed_products import seed

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/seed")
async def seed_products():
    try:
        count = seed()
        return {"status": "ok", "products_seeded": count}
    except Exception as e:
        logger.error("Seed failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
