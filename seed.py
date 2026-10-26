"""Load a few example products so the app has something to show.

Usage:  python seed.py
"""
from app import create_app

SAMPLE = [
    ("LAP-001", "Laptop 14 inch", 549.00, 12),
    ("MON-024", "Monitor 24 inch", 139.90, 25),
    ("KEY-USB", "USB keyboard", 18.50, 60),
    ("MOU-WLS", "Wireless mouse", 12.75, 80),
    ("DOC-USBC", "USB-C docking station", 74.00, 15),
]

if __name__ == "__main__":
    app = create_app()
    client = app.test_client()
    for sku, name, price, stock in SAMPLE:
        response = client.post("/api/products", json={"sku": sku, "name": name, "price": price, "stock": stock})
        print(sku, "created" if response.status_code == 201 else "already there")
