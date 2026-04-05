# ☁ Cloud Kitchen Manager

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python app.py
```

## Open in browser
http://localhost:5000

## File Structure
```
cloud-kitchen/
├── app.py           ← Flask backend + API
├── database.py      ← DB connection + init
├── schema.sql       ← SQLite schema
├── kitchen.db       ← auto-created on first run
├── requirements.txt
└── templates/
    └── index.html   ← Frontend UI
```

## COGS Formula
- COGS = ingredient_cost + preparation_expense
- Selling Price = COGS + profit_margin (auto-calculated, overrideable)
- Profit = Selling Price − COGS
