from typing import Optional, Dict, Any

from app.core.database import get_connection


def get_policy(policy_type: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT policy_type, title, content, updated_at
        FROM policies
        WHERE policy_type = ?
    """, (policy_type,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "policy_type": row["policy_type"],
        "title": row["title"],
        "content": row["content"],
        "updated_at": row["updated_at"],
    }
