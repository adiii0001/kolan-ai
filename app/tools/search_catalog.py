import re
from typing import List, Dict, Any

from app.core.database import get_connection


def _word_like_conditions(column: str, words: List[str]) -> str:
    if not words:
        return "1=1"
    return " AND ".join(f"{column} LIKE ?" for _ in words)


def _build_query(words: List[str], available_only: bool, limit: int) -> tuple:
    if not words:
        base = "SELECT shopify_id, title, handle, description, price, compare_at_price, first_variant_id, vendor, product_type, tags, image_url, inventory_quantity, available FROM products"
        if available_only:
            base += " WHERE available = 1"
        return base + " ORDER BY title LIMIT ?", [limit]

    title_conditions = _word_like_conditions("title", words)
    desc_conditions = _word_like_conditions("description", words)
    tags_conditions = _word_like_conditions("tags", words)

    sql = f"""
        SELECT shopify_id, title, handle, description, price,
               compare_at_price, first_variant_id, vendor, product_type, tags,
               image_url, inventory_quantity, available
        FROM products
        WHERE ({title_conditions} OR {desc_conditions} OR {tags_conditions})
    """

    params = []
    for _ in range(3):
        for w in words:
            params.append(f"%{w}%")

    if available_only:
        sql += " AND available = 1"

    sql += """
        ORDER BY available DESC,
            CASE
                WHEN title LIKE ? THEN 1
                WHEN description LIKE ? THEN 2
                ELSE 3
            END
        LIMIT ?
    """
    params.append(f"%{words[0]}%")
    params.append(f"%{words[0]}%")
    params.append(limit)

    return sql, params


def _strip_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()


def _short_description(desc: str, max_len: int = 100) -> str:
    clean = _strip_html(desc)
    if len(clean) <= max_len:
        return clean
    return clean[:max_len].rsplit(' ', 1)[0] + '...'


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "shopify_id": row["shopify_id"],
        "title": row["title"],
        "handle": row["handle"],
        "description": row["description"],
        "short_description": _short_description(row["description"]),
        "price": row["price"],
        "compare_at_price": row["compare_at_price"],
        "first_variant_id": row["first_variant_id"],
        "vendor": row["vendor"],
        "product_type": row["product_type"],
        "tags": row["tags"],
        "image_url": row["image_url"],
        "inventory_quantity": row["inventory_quantity"],
        "available": bool(row["available"]),
    }


def _search(query: str, available_only: bool, limit: int) -> List[Dict[str, Any]]:
    words = [w.lower() for w in query.split() if len(w) > 1]
    if not words:
        words = []

    conn = get_connection()
    cursor = conn.cursor()
    sql, params = _build_query(words, available_only, limit)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    results = [_row_to_dict(r) for r in rows]
    return results


def search_catalog(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    return _search(query, available_only=False, limit=limit)


def search_available(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    return _search(query, available_only=True, limit=limit)


def search_deals(limit: int = 12) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT shopify_id, title, handle, description, price,
               compare_at_price, first_variant_id, vendor, product_type, tags,
               image_url, inventory_quantity, available
        FROM products
        WHERE compare_at_price IS NOT NULL AND compare_at_price > price AND compare_at_price > 0
        ORDER BY (compare_at_price - price) DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


_CURATED_NEW = [
    "pet-wipes",
    "kolan-eco-friendly-pet-wipes-grooming-wipes-for-dogs-cats-and-other-pets-60-pcs-pack-pack-of-2",
    "no-rinse-floor-cleaner",
    "bathroom-cleaner",
    "kitchen-cleaner",
    "all-purpose-surface-spray",
]

_CURATED_BESTSELLERS = [
    "kolan-pet-wipes-grooming-wipes-for-dogs-cats-60-count-pack-of-5",
    "kolan-eco-friendly-pet-wipes-grooming-wipes-for-dogs-cats-and-other-pets-60-pcs-pack-pack-of-12",
    "no-streak-glass-cleaner",
    "laundry-detergent",
    "bathroom-cleaner",
    "no-rinse-floor-cleaner",
]


def _fetch_by_handles(handles: List[str]) -> List[Dict[str, Any]]:
    if not handles:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in handles)
    cursor.execute(f"""
        SELECT shopify_id, title, handle, description, price,
               compare_at_price, first_variant_id, vendor, product_type, tags,
               image_url, inventory_quantity, available
        FROM products
        WHERE handle IN ({placeholders})
        ORDER BY available DESC
    """, handles)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def search_new_products(limit: int = 12) -> List[Dict[str, Any]]:
    return _fetch_by_handles(_CURATED_NEW)


def search_best_sellers(limit: int = 12) -> List[Dict[str, Any]]:
    return _fetch_by_handles(_CURATED_BESTSELLERS)


def search_deals_in_collection(handle: str, limit: int = 12) -> List[Dict[str, Any]]:
    try:
        import httpx
        resp = httpx.get(
            f"https://kolan.co.in/collections/{handle}/products.json",
            params={"limit": 250},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        collection_products = resp.json().get("products", [])
        if not collection_products:
            return []
        shopify_ids = [str(p["id"]) for p in collection_products if p.get("id")]
        handles = [p["handle"] for p in collection_products if p.get("handle")]
        if not shopify_ids:
            return []

        conn = get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in shopify_ids)
        cursor.execute(f"""
            SELECT shopify_id, title, handle, description, price,
                   compare_at_price, first_variant_id, vendor, product_type, tags,
                   image_url, inventory_quantity, available
            FROM products
            WHERE (shopify_id IN ({placeholders}) OR handle IN ({placeholders}))
              AND compare_at_price IS NOT NULL AND compare_at_price > price AND compare_at_price > 0
            ORDER BY (compare_at_price - price) DESC
            LIMIT ?
        """, shopify_ids + handles + [limit])
        rows = cursor.fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("search_deals_in_collection error for %s: %s", handle, e)
        return []


def get_all_products() -> List[Dict[str, Any]]:
    return _search("", available_only=True, limit=100)
