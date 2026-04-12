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
    pass  # each route closes its own connection

def init_db():
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialised.")

def migrate_db():
    conn = get_db()

    # Fix bad schema: if ingredients has dish_id column, rebuild the table
    cols = [row[1] for row in conn.execute("PRAGMA table_info(ingredients)").fetchall()]
    if "dish_id" in cols:
        print("Migration: fixing bad ingredients schema (removing dish_id)...")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ingredients_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price_per_unit REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT 'g'
            );
            INSERT OR IGNORE INTO ingredients_new (id, name, price_per_unit, unit)
                SELECT id, name,
                       COALESCE(price_per_unit, 0),
                       COALESCE(unit, 'g')
                FROM ingredients;
            DROP TABLE ingredients;
            ALTER TABLE ingredients_new RENAME TO ingredients;
        """)
        conn.commit()
        print("Migration: ingredients table fixed.")

    # Add columns if missing
    cols = [row[1] for row in conn.execute("PRAGMA table_info(ingredients)").fetchall()]
    for col, defn in [
        ("price_per_unit", "REAL DEFAULT 0"),
        ("unit",           "TEXT DEFAULT 'g'"),
    ]:
        if col not in cols:
            try:
                conn.execute(f"ALTER TABLE ingredients ADD COLUMN {col} {defn}")
                conn.commit()
                print(f"Migration: added '{col}' to ingredients.")
            except Exception:
                pass

    conn.close()

if __name__ == "__main__":
    init_db()