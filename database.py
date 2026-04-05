import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "kitchen.db")

def get_db():
   conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("DB initialized at", DB_PATH)
