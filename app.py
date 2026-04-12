import os
import re
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
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024   # 64 KB max body

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

# ── DB init / migrate ─────────────────────────────────────────────────────────
if not os.path.exists("kitchen.db"):
    init_db()
else:
    migrate_db()

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

@app.route("/dishes", methods=["POST"])
@limiter.limit("60 per hour")
def add_dish():
    data, err = _require_json()
    if err: return err

    name, e = _safe_str(data.get("name", ""), "name")
    if e: return jsonify({"error": e}), 400

    prep, e = _safe_num(data.get("prep", 0), "prep")
    if e: return jsonify({"error": e}), 400

    profit, e = _safe_num(data.get("profit", 75), "profit")
    if e: return jsonify({"error": e}), 400

    raw_ings = data.get("ingredients", [])
    if not isinstance(raw_ings, list):
        return jsonify({"error": "'ingredients' must be a list."}), 400
    if len(raw_ings) > MAX_INGREDIENTS_PER_DISH:
        return jsonify({"error": f"Max {MAX_INGREDIENTS_PER_DISH} ingredients."}), 400

    validated = []
    for idx, item in enumerate(raw_ings):
        if not isinstance(item, dict):
            return jsonify({"error": f"Ingredient #{idx+1} malformed."}), 400
        ing_id, e = _safe_num(item.get("id", 0), f"ing #{idx+1} id", allow_zero=False, max_val=10_000_000)
        if e: return jsonify({"error": e}), 400
        qty, e = _safe_num(item.get("qty", 0), f"ing #{idx+1} qty", allow_zero=False)
        if e: return jsonify({"error": e}), 400
        price, e = _safe_num(item.get("price", 0), f"ing #{idx+1} price")
        if e: return jsonify({"error": e}), 400
        validated.append({"id": int(ing_id), "qty": qty, "price": price})

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO dishes (name, preparation_expense, profit_margin) VALUES (?,?,?)",
            (name, prep, profit)
        )
        dish_id = cur.lastrowid
        for item in validated:
            cur.execute(
                "INSERT INTO dish_ingredients (dish_id, ingredient_id, quantity, price) VALUES (?,?,?,?)",
                (dish_id, item["id"], item["qty"], item["price"])
            )
        conn.commit()
        return jsonify({"message": "Dish added.", "id": dish_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not save dish. " + str(e)}), 500

@app.route("/dishes/<int:id>", methods=["DELETE"])
@limiter.limit("60 per hour")
def delete_dish(id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM dishes WHERE id=?", (id,))
        conn.commit()
        return jsonify({"message": "Deleted."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not delete dish. " + str(e)}), 500

# ── Ingredients ───────────────────────────────────────────────────────────────

@app.route("/ingredients", methods=["GET"])
@limiter.limit("120 per minute")
def get_ingredients():
    conn = get_db()
    data = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
    return jsonify([dict(row) for row in data])

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

@app.route("/ingredients", methods=["POST"])
@limiter.limit("60 per hour")
def add_ingredient():
    data, err = _require_json()
    if err: return err

    name, e = _safe_str(data.get("name", ""), "name")
    if e: return jsonify({"error": e}), 400

    # price_per_unit and unit are optional — default to 0 and 'g'
    price_raw = data.get("price_per_unit", 0)
    price, e = _safe_num(price_raw if price_raw is not None else 0, "price_per_unit")
    if e: return jsonify({"error": e}), 400

    unit = data.get("unit", "g")
    if unit not in ALLOWED_UNITS:
        unit = "g"  # default to g if invalid/missing

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO ingredients (name, price_per_unit, unit) VALUES (?,?,?)",
            (name, price, unit)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM ingredients WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not save ingredient. " + str(e)}), 500

@app.route("/ingredients/<int:id>", methods=["PUT"])
@limiter.limit("60 per hour")
def update_ingredient(id):
    data, err = _require_json()
    if err: return err

    name, e = _safe_str(data.get("name", ""), "name")
    if e: return jsonify({"error": e}), 400

    price, e = _safe_num(data.get("price_per_unit", 0), "price_per_unit")
    if e: return jsonify({"error": e}), 400

    unit = data.get("unit", "g")
    if unit not in ALLOWED_UNITS:
        unit = "g"

    conn = get_db()
    try:
        conn.execute(
            "UPDATE ingredients SET name=?, price_per_unit=?, unit=? WHERE id=?",
            (name, price, unit, id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM ingredients WHERE id=?", (id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found."}), 404
        return jsonify(dict(row))
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not update ingredient. " + str(e)}), 500

@app.route("/ingredients/<int:id>", methods=["DELETE"])
@limiter.limit("60 per hour")
def delete_ingredient(id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM ingredients WHERE id=?", (id,))
        conn.commit()
        return jsonify({"message": "Deleted."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not delete ingredient. " + str(e)}), 500

# ── Stats ─────────────────────────────────────────────────────────────────────

@app.route("/stats", methods=["GET"])
@limiter.limit("60 per minute")
def get_stats():
    conn = get_db()
    dishes = conn.execute("SELECT COUNT(*) AS count FROM dishes").fetchone()
    ings   = conn.execute("SELECT COUNT(*) AS count FROM ingredients").fetchone()
    avg    = conn.execute("SELECT AVG(profit_margin) AS avg FROM dishes").fetchone()
    top    = conn.execute(
        "SELECT name, selling_price FROM dish_summary ORDER BY selling_price DESC LIMIT 1"
    ).fetchone()
    return jsonify({
        "total_dishes":      dishes["count"],
        "total_ingredients": ings["count"],
        "avg_profit_margin": round(avg["avg"] or 0, 2),
        "top_dish":          dict(top) if top else None,
    })

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)