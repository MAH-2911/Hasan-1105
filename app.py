from flask import Flask, request, jsonify, render_template
from database import get_db, init_db
import os

app = Flask(__name__)

# Initialize DB
if not os.path.exists("kitchen.db"):
    init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dishes", methods=["GET"])
def get_dishes():
    conn = get_db()
    try:
        data = conn.execute("SELECT * FROM dish_summary").fetchall()
        return jsonify([dict(row) for row in data])
    finally:
        conn.close()

@app.route("/dishes", methods=["POST"])
def add_dish():
    data = request.json
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dishes (name, preparation_expense, profit_margin)
            VALUES (?, ?, ?)
        """, (data["name"], data["prep"], data["profit"]))
        dish_id = cursor.lastrowid
        for item in data["ingredients"]:
            cursor.execute("""
                INSERT INTO dish_ingredients (dish_id, ingredient_id, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (dish_id, item["id"], item["qty"], item["price"]))
        conn.commit()
        return jsonify({"message": "Dish added"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Failed to add dish"}), 500
    finally:
        conn.close()

@app.route("/dishes/<int:id>", methods=["DELETE"])
def delete_dish(id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM dishes WHERE id=?", (id,))
        conn.commit()
        return jsonify({"message": "Deleted"})
    except Exception:
        conn.rollback()
        return jsonify({"error": "Failed to delete dish"}), 500
    finally:
        conn.close()

@app.route("/ingredients", methods=["GET"])
def get_ingredients():
    conn = get_db()
    try:
        data = conn.execute("SELECT * FROM ingredients").fetchall()
        return jsonify([dict(row) for row in data])
    finally:
        conn.close()

@app.route("/ingredients", methods=["POST"])
def add_ingredient():
    data = request.json
    conn = get_db()
    try:
        conn.execute("INSERT INTO ingredients (name) VALUES (?)", (data["name"],))
        conn.commit()
        return jsonify({"message": "Ingredient added"})
    except Exception:
        conn.rollback()
        return jsonify({"error": "Failed to add ingredient"}), 500
    finally:
        conn.close()

@app.route("/ingredients/search", methods=["GET"])
def search_ingredients():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    conn = get_db()
    try:
        data = conn.execute(
            "SELECT * FROM ingredients WHERE name LIKE ? ORDER BY name LIMIT 10",
            (f"%{q}%",)
        ).fetchall()
        return jsonify([dict(row) for row in data])
    finally:
        conn.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)