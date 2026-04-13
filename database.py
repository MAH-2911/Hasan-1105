import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "kitchen.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_app(app):
    pass

def init_db():
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialised.")

def migrate_db():
    conn = get_db()
    cursor = conn.cursor()

    # Check existing columns safely
    cursor.execute("PRAGMA table_info(ingredients)")
    cols = [row[1] for row in cursor.fetchall()]

    # Add missing columns (SAFE)
    if "price_per_unit" not in cols:
        cursor.execute("ALTER TABLE ingredients ADD COLUMN price_per_unit REAL DEFAULT 0")
        print("Migration: added price_per_unit")

    if "unit" not in cols:
        cursor.execute("ALTER TABLE ingredients ADD COLUMN unit TEXT DEFAULT 'g'")
        print("Migration: added unit")

    conn.commit()
    conn.close()
    print("Migration complete.")