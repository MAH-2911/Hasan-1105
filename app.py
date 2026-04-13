import os
import re
import sqlite3  # ✅ ADDED
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database import get_db, init_db, migrate_db, init_app as init_db_app

app = Flask(__name__)

# ── Secret key ────────────────────────────────────────────────────────────────
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError(
        "SECRET_KEY is not set. Generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.config["SECRET_KEY"] = _secret
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]
if not ALLOWED_ORIGINS:
    raise RuntimeError("ALLOWED_ORIGINS env var is not set.")
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=False)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address, app=app,
    default_limits=["2000 per day", "500 per hour"],
    headers_enabled=True,
)

# ── DB teardown ───────────────────────────────────────────────────────────────
init_db_app(app)

# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({"error": "Too many requests. Please slow down."}), 429

@app.errorhandler(413)
def payload_too_large(e):
    return jsonify({"error": "Request body too large (max 64 KB)."}), 413

# ── Constants ─────────────────────────────────────────────────────────────────
ALLOWED_UNITS = {"g", "kg", "ml", "L", "piece", "tbsp", "tsp"}
MAX_NAME_LEN  = 100
MAX_SEARCH_LEN = 100
MAX_INGREDIENTS_PER_DISH = 50

# ── Validators ────────────────────────────────────────────────────────────────
def _safe_str(value, field, max_len=MAX_NAME_LEN):
    if not isinstance(value, str):
        return None, f"'{field}' must be a string."
    v = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value.strip())
    if not v:
        return None, f"'{field}' cannot be blank."
    if len(v) > max_len:
        return None, f"'{field}' too long (max {max_len} chars)."
    return v, None

def _safe_num(value, field, allow_zero=True, max_val=1_000_000):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None, f"'{field}' must be a number."
    if n < 0:
        return None, f"'{field}' cannot be negative."
    if not allow_zero and n == 0:
        return None, f"'{field}' must be > 0."
    if n > max_val:
        return None, f"'{field}' too large."
    return n, None

def _require_json():
    if not request.is_json:
        return None, (jsonify({"error": "Content-Type must be application/json."}), 415)
    data = request.get_json(silent=True)
    if data is None:
        return None, (jsonify({"error": "Invalid JSON body."}), 400)
    return data, None

# ── DB init / migrate (FIXED) ─────────────────────────────────────────────────
def setup_database():
    if not os.path.exists("kitchen.db"):
        init_db()
    migrate_db()

setup_database()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
@limiter.limit("120 per minute")
def index():
    return render_template("index.html")

# ── Dishes ────────────────────────────────────────────────────────────────────

@app.route("/dishes", methods=["GET"])
@limiter.limit("120 per minute")
def get_dishes():
    conn = get_db()
    data = conn.execute("SELECT * FROM dish_summary ORDER BY name").fetchall()
    return jsonify([dict(row) for row in data])

@app.route("/dishes/<int:id>", methods=["GET"])
@limiter.limit("120 per minute")
def get_dish(id):
    conn = get_db()
    dish = conn.execute("SELECT * FROM dish_summary WHERE id=?", (id,)).fetchone()
    if not dish:
        return jsonify({"error": "Dish not found."}), 404
    ings = conn.execute("""
        SELECT di.quantity, di.price AS price_per_base_unit,
               i.name, i.unit AS ingredient_unit
        FROM dish_ingredients di
        JOIN ingredients i ON di.ingredient_id = i.id
        WHERE di.dish_id = ?
    """, (id,)).fetchall()
    result = dict(dish)
    result["ingredients"] = [dict(r) for r in ings]
    return jsonify(result)

# ── Ingredients ───────────────────────────────────────────────────────────────

@app.route("/ingredients", methods=["GET"])
@limiter.limit("120 per minute")
def get_ingredients():
    conn = get_db()
    data = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
    return jsonify([dict(row) for row in data])

@app.route("/ingredients", methods=["POST"])
@limiter.limit("60 per hour")
def add_ingredient():
    data, err = _require_json()
    if err: return err

    name, e = _safe_str(data.get("name", ""), "name")
    if e: return jsonify({"error": e}), 400

    # ✅ normalize name
    name = name.lower().strip()
    name = " ".join(name.split())

    price_raw = data.get("price_per_unit", 0)
    price, e = _safe_num(price_raw if price_raw is not None else 0, "price_per_unit")
    if e: return jsonify({"error": e}), 400

    unit = data.get("unit", "g")
    if unit not in ALLOWED_UNITS:
        unit = "g"

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO ingredients (name, price_per_unit, unit) VALUES (?,?,?)",
            (name, price, unit)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM ingredients WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({"error": "Ingredient already exists."}), 400

    except Exception as e:
        conn.rollback()
        print("ERROR:", str(e))
        return jsonify({"error": "Server error: " + str(e)}), 500

@app.route("/ingredients/search", methods=["GET"])
@limiter.limit("120 per minute")
def search_ingredients():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    if len(q) > MAX_SEARCH_LEN:
        return jsonify({"error": "Query too long."}), 400
    conn = get_db()
    data = conn.execute(
        "SELECT * FROM ingredients WHERE name LIKE ? ORDER BY name LIMIT 10",
        (f"%{q}%",)
    ).fetchall()
    return jsonify([dict(row) for row in data])

# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)