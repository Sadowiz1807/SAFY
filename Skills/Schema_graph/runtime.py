from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from DataStore.schema_graph_store import summarize_schema_graph


class SchemaGraphSkill:
    def __init__(self, schema_graph_loader=None):
        self.schema_graph_loader = schema_graph_loader

    def load(self, database_profile_id: str | None, database_profile: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not database_profile_id or not self.schema_graph_loader:
            return None
        try:
            return self.schema_graph_loader(database_profile_id)
        except Exception:
            return None

    def summarize(self, graph: dict[str, Any] | None) -> str:
        return summarize_schema_graph(graph)

    def select_relevant_subset(self, graph: dict[str, Any] | None, user_query: str, max_tables: int = 8, max_edges: int = 16) -> dict[str, Any] | None:
        if not graph or graph.get("status") != "ready":
            return graph
        text = (user_query or "").lower()
        tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text))
        tables = graph.get("tables") or []
        scored: list[tuple[int, dict[str, Any]]] = []
        for table in tables:
            score = 0
            names = {str(table.get("name") or "").lower(), str(table.get("key") or "").lower()}
            if any(name and name in text for name in names):
                score += 10
            for token in tokens:
                if token in names:
                    score += 8
            for col in table.get("columns") or []:
                col_name = str(col.get("name") or "").lower()
                if col_name and (col_name in tokens or col_name in text):
                    score += 2
            if score:
                scored.append((score, table))
        if scored:
            selected = [table for _, table in sorted(scored, key=lambda item: item[0], reverse=True)[:max_tables]]
        else:
            selected = tables[:max_tables]
        selected_keys = {str(t.get("key") or t.get("name")) for t in selected}
        edges = [
            edge for edge in (graph.get("edges") or [])
            if str(edge.get("from_table")) in selected_keys or str(edge.get("to_table")) in selected_keys
        ][:max_edges]
        return {
            **graph,
            "tables": selected,
            "edges": edges,
            "table_count": len(selected),
            "edge_count": len(edges),
            "subset": True,
            "source_schema_hash": graph.get("schema_hash"),
        }
