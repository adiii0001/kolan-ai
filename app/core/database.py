import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "kolan.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
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
