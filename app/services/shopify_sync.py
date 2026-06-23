import re
import logging
from typing import Dict, Any

import httpx

from app.core.database import get_connection

logger = logging.getLogger(__name__)


def strip_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', text).strip()


def fetch_shopify_policies():
    policy_map = {
        "shipping_policy": "shipping-policy",
        "return_policy": "refund-policy",
        "refund_policy": "refund-policy",
        "privacy_policy": "privacy-policy",
        "terms_of_service": "terms-of-service",
    }

    for policy_type, handle in policy_map.items():
        try:
            resp = httpx.get(f"https://kolan.co.in/policies/{handle}.json", timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("policy", {})
                title = data.get("title", policy_type.replace("_", " ").title())
                body = strip_html(data.get("body", ""))
                if body:
                    upsert_policy(policy_type, title, body)
                    logger.info("Fetched Shopify policy: %s", policy_type)
        except Exception as e:
            logger.warning("Failed to fetch policy %s: %s", handle, e)


def upsert_product(payload: Dict[str, Any]) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    shopify_id = str(payload.get("id"))
    title = payload.get("title", "")
    handle = payload.get("handle", "")
    description = payload.get("body_html", "").strip()
    vendor = payload.get("vendor", "")
    product_type = payload.get("product_type", "")
    raw_tags = payload.get("tags", "")
    tags = ", ".join(raw_tags) if isinstance(raw_tags, list) else str(raw_tags)

    variants = payload.get("variants", [])
    price = 0.0
    compare_at_price = 0.0
    inventory_quantity = 0
    available = 1

    if variants:
        v = variants[0]
        price = float(v.get("price", 0))
        compare_price = v.get("compare_at_price")
        if compare_price is not None:
            compare_at_price = float(compare_price)
        inventory_quantity = v.get("inventory_quantity", 0) or 0
        available = 1 if v.get("available", True) else 0

    image_url = ""
    images = payload.get("images", [])
    if images:
        image_url = images[0].get("src", "")

    cursor.execute("""
        INSERT INTO products (
            shopify_id, title, handle, description, price,
            compare_at_price, vendor, product_type, tags,
            image_url, inventory_quantity, available, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(shopify_id) DO UPDATE SET
            title = excluded.title,
            handle = excluded.handle,
            description = excluded.description,
            price = excluded.price,
            compare_at_price = excluded.compare_at_price,
            vendor = excluded.vendor,
            product_type = excluded.product_type,
            tags = excluded.tags,
            image_url = excluded.image_url,
            inventory_quantity = excluded.inventory_quantity,
            available = excluded.available,
            updated_at = datetime('now')
    """, (
        shopify_id, title, handle, description, price,
        compare_at_price, vendor, product_type, tags,
        image_url, inventory_quantity, available
    ))

    conn.commit()
    conn.close()
    logger.info("Product upserted: %s (%s)", title, shopify_id)


def delete_product(shopify_id: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE shopify_id = ?", (shopify_id,))
    conn.commit()
    conn.close()
    logger.info("Product deleted: %s", shopify_id)


def upsert_policy(policy_type: str, title: str, content: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO policies (policy_type, title, content, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(policy_type) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            updated_at = datetime('now')
    """, (policy_type, title, content))
    conn.commit()
    conn.close()
    logger.info("Policy upserted: %s", policy_type)


def sync_collections():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            handle TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            product_count INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    conn.commit()

    try:
        resp = httpx.get("https://kolan.co.in/collections.json", timeout=15)
        if resp.status_code == 200:
            collections = resp.json().get("collections", [])
            for col in collections:
                handle = col.get("handle", "")
                title = col.get("title", "")
                body = strip_html(col.get("body_html", ""))
                if not handle or handle == "all":
                    continue

                try:
                    prod_resp = httpx.get(
                        f"https://kolan.co.in/collections/{handle}/products.json",
                        params={"limit": 250},
                        timeout=15,
                    )
                    product_count = 0
                    if prod_resp.status_code == 200:
                        product_count = len(prod_resp.json().get("products", []))
                except Exception:
                    product_count = 0

                cursor.execute("""
                    INSERT INTO collections (handle, title, description, product_count, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(handle) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        product_count = excluded.product_count,
                        updated_at = datetime('now')
                """, (handle, title, body[:500] if body else "", product_count))
                logger.info("Collection synced: %s (%d products)", title, product_count)

            conn.commit()
    except Exception as e:
        logger.warning("Failed to sync collections: %s", e)
    finally:
        conn.close()


def get_all_collections():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT handle, title, description, product_count FROM collections ORDER BY title")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"handle": r["handle"], "title": r["title"], "description": r["description"] or "", "product_count": r["product_count"]}
        for r in rows
    ]


def get_collection_products(handle: str, limit: int = 20):
    try:
        resp = httpx.get(
            f"https://kolan.co.in/collections/{handle}/products.json",
            params={"limit": limit},
            timeout=15,
        )
        if resp.status_code == 200:
            products = resp.json().get("products", [])
            results = []
            for p in products:
                variants = p.get("variants", [])
                price = float(variants[0].get("price", 0)) if variants else 0
                available = any(v.get("available", False) for v in variants) if variants else False
                images = p.get("images", [])
                image_url = images[0].get("src", "") if images else ""
                results.append({
                    "title": p.get("title", ""),
                    "price": price,
                    "handle": p.get("handle", ""),
                    "image_url": image_url,
                    "available": available,
                })
            return results
    except Exception:
        pass
    return []
