CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ingredient_cost REAL NOT NULL DEFAULT 0,
    preparation_expense REAL NOT NULL DEFAULT 0,
    profit_margin REAL NOT NULL DEFAULT 75,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dish_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE
);

-- View for dashboard (SAFE calculations using COALESCE)
CREATE VIEW IF NOT EXISTS dish_summary AS
SELECT
    id,
    name,
    ingredient_cost,
    preparation_expense,

    -- Safe COGS calculation
    (COALESCE(ingredient_cost, 0) + COALESCE(preparation_expense, 0)) AS cogs,

    profit_margin,

    -- Safe Selling Price calculation
    (
        COALESCE(ingredient_cost, 0) +
        COALESCE(preparation_expense, 0) +
        COALESCE(profit_margin, 0)
    ) AS selling_price

FROM dishes;
