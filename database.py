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
    pass  # no teardown needed — each route closes its own connection

def init_db():
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialised.")

def migrate_db():
    conn = get_db()
    for col, defn in [
        ("price_per_unit", "REAL DEFAULT 0"),
        ("unit",           "TEXT DEFAULT 'g'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE ingredients ADD COLUMN {col} {defn}")
            conn.commit()
            print(f"Migration: added '{col}' to ingredients.")
        except Exception:
            pass  # already exists
    conn.close()

if __name__ == "__main__":
    init_db()