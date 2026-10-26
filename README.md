# Inventory & Quotes

A small web app to keep a product inventory and build customer quotes. I built it to practise the same kind of
workflow I use at work (inventory, orders and quotations), with sample data only.

![Inventory & Quotes: products, a quote being built and saved quotes](docs/screenshot.jpg)

## What it does

- Create, list, update and delete products (SKU, name, price, stock).
- Build a quote from several products. The server checks the stock and calculates subtotal, tax (13%) and total,
  so the numbers do not depend on the browser.
- List saved quotes and read the detail of any quote.
- A single page UI (plain HTML, CSS and JavaScript) on top of a JSON API: product search, stock badges, a live
  totals preview while you build the quote, and messages for every error. Everything coming from the API is
  escaped before it is drawn.

## Stack

Python 3, Flask, SQLite, vanilla JavaScript, pytest.

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python seed.py        # optional: loads example products
python app.py         # http://127.0.0.1:5000
```

## Tests

```bash
pytest
```

The tests use a temporary database, so they never touch your data.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/products` | List products |
| POST | `/api/products` | Create a product |
| PUT | `/api/products/<id>` | Update a product |
| DELETE | `/api/products/<id>` | Delete a product (not allowed if used in a quote) |
| GET | `/api/quotes` | List quotes |
| POST | `/api/quotes` | Create a quote `{customer, items:[{product_id, quantity}]}` |
| GET | `/api/quotes/<id>` | Quote with its lines |

Errors come back as JSON `{"error": "..."}` with a meaningful status code (400, 404, 409).

## Notes and next steps

- The tax rate is a constant in `app.py` (`TAX_RATE`).
- Stock is checked when a quote is created but not reduced yet; the next step would be a "confirm quote" action
  that discounts the stock.
- Authentication is not included because it is a learning project.
