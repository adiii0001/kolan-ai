import sqlite3
from pathlib import Path

from app.core.config import settings


def get_db_path() -> Path:
    return Path(settings.database_url).resolve()


def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shopify_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            handle TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0.0,
            compare_at_price REAL DEFAULT 0.0,
            first_variant_id TEXT DEFAULT '',
            vendor TEXT DEFAULT '',
            product_type TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            inventory_quantity INTEGER DEFAULT 0,
            available INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("SELECT COUNT(*) AS cnt FROM pragma_table_info('products') WHERE name='first_variant_id'")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("ALTER TABLE products ADD COLUMN first_variant_id TEXT DEFAULT ''")

    cursor.execute("SELECT COUNT(*) AS cnt FROM pragma_table_info('products') WHERE name='shopify_created_at'")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("ALTER TABLE products ADD COLUMN shopify_created_at TEXT DEFAULT ''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_type TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
