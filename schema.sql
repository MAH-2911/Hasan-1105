CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    preparation_expense REAL NOT NULL DEFAULT 0,
    profit_margin REAL NOT NULL DEFAULT 75,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price_per_unit REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'g'
);

CREATE TABLE IF NOT EXISTS dish_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dish_id INTEGER,
    ingredient_id INTEGER,
    quantity REAL DEFAULT 1,
    price REAL DEFAULT 0,
    FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

DROP VIEW IF EXISTS dish_summary;
CREATE VIEW dish_summary AS
SELECT
    d.id, d.name,
    COALESCE(SUM(di.quantity * di.price), 0) AS ingredient_cost,
    d.preparation_expense,
    (COALESCE(SUM(di.quantity * di.price), 0) + d.preparation_expense) AS cogs,
    d.profit_margin,
    (COALESCE(SUM(di.quantity * di.price), 0) + d.preparation_expense + d.profit_margin) AS selling_price
FROM dishes d
LEFT JOIN dish_ingredients di ON d.id = di.dish_id
GROUP BY d.id;