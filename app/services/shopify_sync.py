import logging
from typing import Dict, Any

from app.core.database import get_connection

logger = logging.getLogger(__name__)


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
