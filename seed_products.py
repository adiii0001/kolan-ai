"""One-time script to seed SQLite with all products from the public Shopify storefront.

Usage:
    python seed_products.py
"""

import httpx
from app.core.database import get_connection, init_db

STORE_URL = "https://kolan.co.in"


def fetch_all_products():
    products = []
    url = f"{STORE_URL}/products.json"
    page = 1
    while url:
        resp = httpx.get(url, params={"limit": 250, "page": page})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("products", [])
        if not items:
            break
        products.extend(items)
        page += 1
    return products


def seed():
    from app.services.shopify_sync import upsert_product

    init_db()
    products = fetch_all_products()
    for p in products:
        upsert_product(p)
    print(f"Seeded {len(products)} products.")


if __name__ == "__main__":
    seed()
