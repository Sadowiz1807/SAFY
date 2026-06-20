from __future__ import annotations

from .base_provider import ProviderRequest, ProviderResponse


class DemoProvider:
    """Deterministic demo provider used for local smoke tests and fixtures.

    This is runtime support code, not a pytest test module. The provider keeps
    the historical provider id `test` as a compatibility alias for older configs.
    """

    provider_id = "test"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        target = "sandbox" if request.target == "sandbox" else "connected_database"
        tables = ["customers", "addresses", "categories", "products", "orders", "order_items", "payments"]
        ddl = [
            "CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL);",
            "CREATE TABLE addresses (address_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, line1 TEXT NOT NULL, city TEXT NOT NULL, country TEXT NOT NULL, FOREIGN KEY(customer_id) REFERENCES customers(customer_id));",
            "CREATE TABLE categories (category_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);",
            "CREATE TABLE products (product_id INTEGER PRIMARY KEY, category_id INTEGER, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL, price_cents INTEGER NOT NULL, FOREIGN KEY(category_id) REFERENCES categories(category_id));",
            "CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(customer_id) REFERENCES customers(customer_id));",
            "CREATE TABLE order_items (order_item_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(order_id), FOREIGN KEY(product_id) REFERENCES products(product_id));",
            "CREATE TABLE payments (payment_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL, status TEXT NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(order_id));",
        ]
        return ProviderResponse(self.provider_id, {
            "intent": request.intent,
            "target": target,
            "dialect": "sqlite",
            "domain": request.domain,
            "tables": tables,
            "ddl": ddl,
            "tools": ["sandbox.execute_sql", "database.read_schema"],
        })


TestProvider = DemoProvider
