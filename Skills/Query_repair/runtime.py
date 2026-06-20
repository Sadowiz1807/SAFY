from __future__ import annotations

from typing import Any
import re


class QueryRepairSkill:
    def repair_basic(self, sql: str, error: dict[str, Any] | None = None, schema_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        repaired = (sql or "").strip()
        notes: list[str] = []
        if repaired and not repaired.endswith(";"):
            repaired += ";"
            notes.append("Added trailing semicolon.")
        if re.match(r"^select\b", repaired, re.I) and " limit " not in repaired.lower():
            repaired = repaired.rstrip(";") + " LIMIT 100;"
            notes.append("Added LIMIT 100 for safer preview.")
        return {"sql": repaired, "notes": notes, "draft_only": True, "schema_hash": schema_graph.get("schema_hash") if isinstance(schema_graph, dict) else None}
