from __future__ import annotations

DEFAULT_ECOMMERCE_TABLES = ["customers", "addresses", "categories", "products", "orders", "order_items", "payments"]


def resolve_domain(message: str) -> tuple[str, list[str]]:
    text = (message or "").lower()
    if any(term in text for term in ["store", "shop", "commerce", "e-commerce", "ecommerce", "online store"]):
        return "ecommerce", []
    return "ecommerce", ["Domain not provided; using default e-commerce domain."]
