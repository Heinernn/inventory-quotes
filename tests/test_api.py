import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app.test_client()


def add_product(client, sku="KB-01", name="Keyboard", price=20.0, stock=10):
    return client.post("/api/products", json={"sku": sku, "name": name, "price": price, "stock": stock})


def test_create_and_list_products(client):
    response = add_product(client)
    assert response.status_code == 201
    products = client.get("/api/products").get_json()
    assert len(products) == 1
    assert products[0]["sku"] == "KB-01"


def test_sku_is_normalised_and_unique(client):
    add_product(client, sku=" kb-01 ")
    assert client.get("/api/products").get_json()[0]["sku"] == "KB-01"
    assert add_product(client, sku="KB-01").status_code == 409


def test_product_validation(client):
    assert client.post("/api/products", json={"sku": "X"}).status_code == 400
    assert add_product(client, price=-5).status_code == 400
    assert add_product(client, stock=-1).status_code == 400


def test_update_and_delete_product(client):
    product_id = add_product(client).get_json()["id"]
    updated = client.put(f"/api/products/{product_id}",
                         json={"sku": "KB-01", "name": "Keyboard v2", "price": 25, "stock": 8})
    assert updated.get_json()["name"] == "Keyboard v2"
    assert client.delete(f"/api/products/{product_id}").status_code == 204
    assert client.delete(f"/api/products/{product_id}").status_code == 404


def test_quote_totals_include_tax(client):
    first = add_product(client, sku="A", price=10.0, stock=5).get_json()["id"]
    second = add_product(client, sku="B", price=2.5, stock=10).get_json()["id"]
    response = client.post("/api/quotes", json={
        "customer": "Acme",
        "items": [{"product_id": first, "quantity": 2}, {"product_id": second, "quantity": 4}],
    })
    assert response.status_code == 201
    quote = response.get_json()
    assert quote["subtotal"] == 30.0
    assert quote["tax"] == 3.9
    assert quote["total"] == 33.9

    detail = client.get(f"/api/quotes/{quote['id']}").get_json()
    assert len(detail["items"]) == 2
    assert detail["items"][0]["line_total"] == 20.0


def test_quote_rejects_missing_stock_and_bad_input(client):
    product_id = add_product(client, stock=1).get_json()["id"]
    too_many = client.post("/api/quotes", json={"customer": "Acme", "items": [{"product_id": product_id, "quantity": 2}]})
    assert too_many.status_code == 409
    assert client.post("/api/quotes", json={"customer": "", "items": []}).status_code == 400
    assert client.post("/api/quotes", json={"customer": "Acme", "items": [{"product_id": 999, "quantity": 1}]}).status_code == 404


def test_product_used_in_quote_cannot_be_deleted(client):
    product_id = add_product(client).get_json()["id"]
    client.post("/api/quotes", json={"customer": "Acme", "items": [{"product_id": product_id, "quantity": 1}]})
    assert client.delete(f"/api/products/{product_id}").status_code == 409
