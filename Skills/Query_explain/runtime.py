from __future__ import annotations

from typing import Any
import re


class QueryExplainSkill:
    def explain(self, sql: str, schema_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        text = sql or ""
        tables = re.findall(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_\.]*)|\bjoin\s+([A-Za-z_][A-Za-z0-9_\.]*)", text, re.I)
        flattened = [a or b for a, b in tables if (a or b)]
        return {
            "summary": "This SQL draft is intended for review before safety check and execution.",
            "tables": list(dict.fromkeys(flattened)),
            "has_where": bool(re.search(r"\bwhere\b", text, re.I)),
            "has_join": bool(re.search(r"\bjoin\b", text, re.I)),
            "schema_hash": schema_graph.get("schema_hash") if isinstance(schema_graph, dict) else None,
        }
