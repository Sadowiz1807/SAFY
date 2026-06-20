from __future__ import annotations

from typing import Any

SENSITIVE_TOKENS = ("password", "secret", "token", "api_key", "dsn", "connection")


def _safe_name(value: Any) -> str:
    text = str(value or "")
    lowered = text.lower()
    if any(token in lowered for token in SENSITIVE_TOKENS):
        return "[redacted]"
    return text[:120]


def summarize_schema(schema: dict[str, Any] | None, max_tables: int = 24, max_columns: int = 24) -> str:
    if not schema:
        return "No schema cache is available. Ask the user to connect a database or create a sandbox."
    tables = schema.get("tables") or schema.get("objects") or []
    lines = []
    for table in tables[:max_tables]:
        name = _safe_name(table.get("name") or table.get("table_name"))
        columns = table.get("columns") or []
        col_names = []
        for col in columns[:max_columns]:
            if isinstance(col, dict):
                col_names.append(_safe_name(col.get("name") or col.get("column_name")))
            else:
                col_names.append(_safe_name(col))
        lines.append(f"- {name}({', '.join(col_names)})")
    return "\n".join(lines) if lines else "Schema cache contains no table summaries."
