from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from database import get_db, init_db

app = Flask(__name__)
CORS(app)
import os

if not os.path.exists("kitchen.db"):
    init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/dishes", methods=["GET"])
def get_dishes():
    with get_db() as db:
        rows = db.execute("SELECT * FROM dish_summary ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route("/api/dishes", methods=["POST"])
def add_dish():
    d = request.json
    margin = d.get("profit_margin", 75)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO dishes (name, ingredient_cost, preparation_expense, profit_margin) VALUES (?,?,?,?)",
            (d["name"], d["ingredient_cost"], d["preparation_expense"], margin)
        )
        dish_id = cur.lastrowid
        for ing in d.get("ingredients", []):
            db.execute("INSERT INTO ingredients (dish_id, name, cost) VALUES (?,?,?)",
                       (dish_id, ing["name"], ing["cost"]))
        db.commit()
        row = db.execute("SELECT * FROM dish_summary WHERE id=?", (dish_id,)).fetchone()
        return jsonify(dict(row)), 201

@app.route("/api/dishes/<int:id>", methods=["PUT"])
def update_dish(id):
    d = request.json
    margin = d.get("profit_margin", 75)
    with get_db() as db:
        db.execute(
            "UPDATE dishes SET name=?, ingredient_cost=?, preparation_expense=?, profit_margin=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (d["name"], d["ingredient_cost"], d["preparation_expense"], margin, id)
        )
        db.execute("DELETE FROM ingredients WHERE dish_id=?", (id,))
        for ing in d.get("ingredients", []):
            db.execute("INSERT INTO ingredients (dish_id, name, cost) VALUES (?,?,?)",
                       (id, ing["name"], ing["cost"]))
        db.commit()
        row = db.execute("SELECT * FROM dish_summary WHERE id=?", (id,)).fetchone()
        return jsonify(dict(row))

@app.route("/api/dishes/<int:id>", methods=["DELETE"])
def delete_dish(id):
    with get_db() as db:
        db.execute("DELETE FROM dishes WHERE id=?", (id,))
        db.commit()
        return jsonify({"deleted": id})

@app.route("/api/dishes/<int:id>/ingredients", methods=["GET"])
def get_ingredients(id):
    with get_db() as db:
        rows = db.execute("SELECT * FROM ingredients WHERE dish_id=?", (id,)).fetchall()
        return jsonify([dict(r) for r in rows])

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)