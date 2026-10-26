"""Small inventory and quotation manager.

Flask + SQLite. Products can be created and edited, and quotes are built from
products with the tax applied on the server side so the totals are always
consistent no matter which client sends the request.
"""
import os
import sqlite3
from contextlib import closing

from flask import Flask, g, jsonify, render_template, request

TAX_RATE = 0.13  # Costa Rica VAT; change it here if you need another rate

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0)
);
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal REAL NOT NULL,
    tax REAL NOT NULL,
    total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS quote_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL
);
"""


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or os.path.join(app.root_path, "inventory.db")

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with closing(sqlite3.connect(app.config["DATABASE"])) as setup:
        setup.executescript(SCHEMA)

    def error(message, status=400):
        return jsonify({"error": message}), status

    def read_product(data):
        """Validate the body of a product request. Returns (clean, error)."""
        try:
            clean = {
                "sku": str(data["sku"]).strip().upper(),
                "name": str(data["name"]).strip(),
                "price": float(data["price"]),
                "stock": int(data.get("stock", 0)),
            }
        except (KeyError, TypeError, ValueError):
            return None, "sku, name and price are required; price and stock must be numbers"
        if not clean["sku"] or not clean["name"]:
            return None, "sku and name cannot be empty"
        if clean["price"] < 0 or clean["stock"] < 0:
            return None, "price and stock cannot be negative"
        return clean, None

    @app.get("/")
    def index():
        return render_template("index.html", tax_rate=int(TAX_RATE * 100))

    # ---- products -------------------------------------------------------
    @app.get("/api/products")
    def list_products():
        rows = get_db().execute("SELECT * FROM products ORDER BY name").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.post("/api/products")
    def create_product():
        clean, problem = read_product(request.get_json(silent=True) or {})
        if problem:
            return error(problem)
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO products (sku, name, price, stock) VALUES (?, ?, ?, ?)",
                (clean["sku"], clean["name"], clean["price"], clean["stock"]),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return error("a product with that SKU already exists", 409)
        return jsonify({"id": cur.lastrowid, **clean}), 201

    @app.put("/api/products/<int:product_id>")
    def update_product(product_id):
        clean, problem = read_product(request.get_json(silent=True) or {})
        if problem:
            return error(problem)
        db = get_db()
        try:
            cur = db.execute(
                "UPDATE products SET sku=?, name=?, price=?, stock=? WHERE id=?",
                (clean["sku"], clean["name"], clean["price"], clean["stock"], product_id),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return error("a product with that SKU already exists", 409)
        if cur.rowcount == 0:
            return error("product not found", 404)
        return jsonify({"id": product_id, **clean})

    @app.delete("/api/products/<int:product_id>")
    def delete_product(product_id):
        db = get_db()
        try:
            cur = db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            db.commit()
        except sqlite3.IntegrityError:
            return error("the product is used in a quote and cannot be deleted", 409)
        if cur.rowcount == 0:
            return error("product not found", 404)
        return "", 204

    # ---- quotes ---------------------------------------------------------
    @app.post("/api/quotes")
    def create_quote():
        data = request.get_json(silent=True) or {}
        customer = str(data.get("customer", "")).strip()
        items = data.get("items") or []
        if not customer:
            return error("customer is required")
        if not items:
            return error("a quote needs at least one item")

        db = get_db()
        lines, subtotal = [], 0.0
        for item in items:
            try:
                product_id, quantity = int(item["product_id"]), int(item["quantity"])
            except (KeyError, TypeError, ValueError):
                return error("each item needs product_id and quantity")
            if quantity <= 0:
                return error("quantity must be greater than zero")
            product = db.execute(
                "SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if product is None:
                return error(f"product {product_id} not found", 404)
            if quantity > product["stock"]:
                return error(f"not enough stock for {product['name']} (available: {product['stock']})", 409)
            subtotal += product["price"] * quantity
            lines.append((product["id"], quantity, product["price"]))

        subtotal = round(subtotal, 2)
        tax = round(subtotal * TAX_RATE, 2)
        total = round(subtotal + tax, 2)
        cur = db.execute(
            "INSERT INTO quotes (customer, subtotal, tax, total) VALUES (?, ?, ?, ?)",
            (customer, subtotal, tax, total),
        )
        quote_id = cur.lastrowid
        db.executemany(
            "INSERT INTO quote_items (quote_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            [(quote_id, pid, qty, price) for pid, qty, price in lines],
        )
        db.commit()
        return jsonify({"id": quote_id, "customer": customer, "subtotal": subtotal, "tax": tax, "total": total}), 201

    @app.get("/api/quotes")
    def list_quotes():
        rows = get_db().execute("SELECT * FROM quotes ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.get("/api/quotes/<int:quote_id>")
    def get_quote(quote_id):
        db = get_db()
        quote = db.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
        if quote is None:
            return error("quote not found", 404)
        items = db.execute(
            """SELECT p.sku, p.name, qi.quantity, qi.unit_price,
                      ROUND(qi.quantity * qi.unit_price, 2) AS line_total
               FROM quote_items qi JOIN products p ON p.id = qi.product_id
               WHERE qi.quote_id = ?""",
            (quote_id,),
        ).fetchall()
        return jsonify({**dict(quote), "items": [dict(i) for i in items]})

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
