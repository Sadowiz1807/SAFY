from __future__ import annotations


def detect_intent(message: str) -> str:
    text = (message or "").lower()
    if any(term in text for term in ["create database", "create a database", "create db", "create a db", "database for", "schema for", "online store", "e-commerce", "ecommerce"]):
        return "create_database"
    if any(term in text for term in ["show me", "list ", "select ", "find ", "search ", "what are", "display "]):
        return "connected_read_only_query"
    if any(term in text for term in ["delete ", "drop ", "truncate ", "update ", "insert ", "alter "]):
        return "connected_destructive_query"
    return "unknown"
