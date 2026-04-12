import sqlite3
import os
from flask import g

DB_PATH = os.path.join(os.path.dirname(__file__), "kitchen.db")

def get_db():
    """Per-request connection stored on Flask g — thread-safe."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialised.")

def migrate_db():
    """Safely add new columns without losing existing data."""
    conn = sqlite3.connect(DB_PATH)
    for col, defn in [
        ("price_per_unit", "REAL DEFAULT 0"),
        ("unit",           "TEXT DEFAULT 'g'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE ingredients ADD COLUMN {col} {defn}")
            conn.commit()
            print(f"Migration: added '{col}' to ingredients.")
        except Exception:
            pass   # already exists
    conn.close()

if __name__ == "__main__":
    init_db()