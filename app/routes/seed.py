import logging

import httpx
from fastapi import APIRouter, HTTPException
from app.core.database import init_db, get_connection
from app.services.shopify_sync import upsert_product

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
        from app.services.shopify_sync import upsert_policy
        upsert_policy("shipping_policy", "Shipping Policy", "We ship across India via trusted courier partners. Free shipping on orders above Rs499. Standard delivery takes 3-7 business days. Expedited shipping available at checkout for Rs99 extra.")
        upsert_policy("return_policy", "Return Policy", "You can return any product within 7 days of delivery if you are not satisfied. Products must be unused and in original packaging. To initiate a return, contact our support team with your order number. Refunds are processed within 5-7 business days after we receive the returned item.")
        upsert_policy("refund_policy", "Refund Policy", "Refunds are processed within 5-7 business days after we receive the returned product. The refund will be credited to your original payment method. For cash-on-delivery orders, refunds are processed via bank transfer.")
        upsert_policy("privacy_policy", "Privacy Policy", "We respect your privacy. Your personal information is used only for order processing and improving your shopping experience. We do not share your data with third parties except for payment processing and delivery partners as necessary.")
        upsert_policy("terms_of_service", "Terms of Service", "By using our website and purchasing our products, you agree to these terms. All products are for pet use unless specified otherwise. We reserve the right to update these terms at any time.")
        return {"status": "ok", "products_seeded": len(products), "policies_seeded": 5}
    except Exception as e:
        logger.error("Seed failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
