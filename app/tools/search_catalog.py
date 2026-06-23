from typing import List, Dict, Any

from app.core.database import get_connection


def _word_like_conditions(column: str, words: List[str]) -> str:
    if not words:
        return "1=1"
    return " AND ".join(f"{column} LIKE ?" for _ in words)


def _build_query(words: List[str], available_only: bool, limit: int) -> tuple:
    if not words:
        base = "SELECT shopify_id, title, handle, description, price, compare_at_price, vendor, product_type, tags, image_url, inventory_quantity, available FROM products"
        if available_only:
            base += " WHERE available = 1"
        return base + " ORDER BY title LIMIT ?", [limit]

    title_conditions = _word_like_conditions("title", words)
    desc_conditions = _word_like_conditions("description", words)
    tags_conditions = _word_like_conditions("tags", words)

    sql = f"""
        SELECT shopify_id, title, handle, description, price,
               compare_at_price, vendor, product_type, tags,
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


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "shopify_id": row["shopify_id"],
        "title": row["title"],
        "handle": row["handle"],
        "description": row["description"],
        "price": row["price"],
        "compare_at_price": row["compare_at_price"],
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


def get_all_products() -> List[Dict[str, Any]]:
    return _search("", available_only=True, limit=100)
