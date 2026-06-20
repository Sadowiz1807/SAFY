from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import tempfile


class SchemaGraphStoreError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_profile_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._-")
    return safe or "main_database"


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaGraphStoreError("SCHEMA_GRAPH_PARSE_ERROR", f"Invalid schema graph file: {path.name}") from exc
    if not isinstance(data, dict):
        raise SchemaGraphStoreError("SCHEMA_GRAPH_INVALID_SHAPE", f"Schema graph file must be an object: {path.name}")
    return data


def _column_name(column: dict[str, Any]) -> str:
    return str(column.get("name") or column.get("column_name") or "").strip()


def _column_type(column: dict[str, Any]) -> str:
    return str(column.get("data_type") or column.get("type") or column.get("db_type") or "").strip()


def _table_key(table: dict[str, Any]) -> str:
    schema = str(table.get("schema") or table.get("table_schema") or "").strip()
    name = str(table.get("name") or table.get("table_name") or "").strip()
    return f"{schema}.{name}" if schema and schema not in {"main", "public"} else name


def _normalize_tables(raw_schema: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = raw_schema.get("metadata") if isinstance(raw_schema.get("metadata"), dict) else {}
    raw_tables = raw_schema.get("tables") or metadata.get("tables") or []
    tables: list[dict[str, Any]] = []
    if not isinstance(raw_tables, list):
        return tables
    for table in raw_tables:
        if not isinstance(table, dict):
            continue
        name = str(table.get("name") or table.get("table_name") or "").strip()
        if not name:
            continue
        schema = str(table.get("schema") or table.get("table_schema") or "public").strip() or "public"
        columns: list[dict[str, Any]] = []
        for column in table.get("columns") or []:
            if not isinstance(column, dict):
                continue
            col_name = _column_name(column)
            if not col_name:
                continue
            columns.append({
                "name": col_name,
                "type": _column_type(column),
                "nullable": bool(column.get("nullable", False)),
                "primary_key": bool(column.get("primary_key", False)),
                "sensitive": bool(column.get("sensitive", False)),
            })
        tables.append({
            "schema": schema,
            "name": name,
            "key": _table_key({"schema": schema, "name": name}),
            "type": table.get("type") or table.get("table_type") or "table",
            "columns": columns,
            "primary_keys": table.get("primary_keys") or [c["name"] for c in columns if c.get("primary_key")],
            "foreign_keys": table.get("foreign_keys") or [],
            "indexes": table.get("indexes") or [],
            "row_count_estimate": table.get("row_count_estimate"),
        })
    return tables


def _edge_from_fk(table: dict[str, Any], fk: dict[str, Any]) -> dict[str, Any] | None:
    from_table = table.get("key") or table.get("name")
    from_column = fk.get("column") or fk.get("from_column") or fk.get("from")
    to_table = fk.get("references_table") or fk.get("to_table") or fk.get("table")
    to_column = fk.get("references_column") or fk.get("to_column") or fk.get("to")
    if not from_table or not from_column or not to_table:
        return None
    to_column = to_column or "id"
    return {
        "from_table": str(from_table),
        "from_column": str(from_column),
        "to_table": str(to_table),
        "to_column": str(to_column),
        "type": "foreign_key",
        "join_condition": f"{from_table}.{from_column} = {to_table}.{to_column}",
    }


def build_schema_graph(raw_schema: dict[str, Any], database_profile: dict[str, Any]) -> dict[str, Any]:
    tables = _normalize_tables(raw_schema or {})
    edges: list[dict[str, Any]] = []
    for table in tables:
        for fk in table.get("foreign_keys") or []:
            if isinstance(fk, dict):
                edge = _edge_from_fk(table, fk)
                if edge:
                    edges.append(edge)
    deduped_edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        key = (edge["from_table"], edge["from_column"], edge["to_table"], edge["to_column"])
        if key in seen:
            continue
        seen.add(key)
        deduped_edges.append(edge)
    profile_id = str(database_profile.get("profile_id") or "main_database")
    display_name = str(database_profile.get("display_name") or profile_id)
    graph_core = {
        "database_profile_id": profile_id,
        "database_name": display_name,
        "driver": database_profile.get("driver") or database_profile.get("dbms"),
        "provider": database_profile.get("provider"),
        "tables": tables,
        "edges": deduped_edges,
    }
    schema_hash = hashlib.sha256(json.dumps(graph_core, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        **graph_core,
        "schema_hash": schema_hash,
        "refreshed_at": _now_iso(),
        "status": "ready" if tables else "empty",
        "source": "backend_introspection",
        "table_count": len(tables),
        "edge_count": len(deduped_edges),
    }


def empty_schema_graph(database_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = database_profile or {}
    profile_id = str(profile.get("profile_id") or "")
    return {
        "schema_version": 1,
        "database_profile_id": profile_id or None,
        "database_name": profile.get("display_name") or profile_id or None,
        "driver": profile.get("driver") or profile.get("dbms"),
        "provider": profile.get("provider"),
        "tables": [],
        "edges": [],
        "schema_hash": None,
        "refreshed_at": None,
        "status": "empty",
        "source": "not_loaded",
        "table_count": 0,
        "edge_count": 0,
    }


def summarize_schema_graph(graph: dict[str, Any] | None, max_tables: int = 20, max_columns: int = 16) -> str:
    if not graph or graph.get("status") != "ready":
        return "No stored schema graph for the active database. Generate SQL from the user's request only, and prefer conservative SELECT queries."
    lines = [
        f"Active database: {graph.get('database_name') or graph.get('database_profile_id')}",
        f"Schema hash: {graph.get('schema_hash') or 'unknown'}",
        "Tables:",
    ]
    for table in (graph.get("tables") or [])[:max_tables]:
        columns = table.get("columns") or []
        rendered_cols = []
        for col in columns[:max_columns]:
            flags = []
            if col.get("primary_key"):
                flags.append("PK")
            if col.get("sensitive"):
                flags.append("sensitive")
            suffix = f" [{' '.join(flags)}]" if flags else ""
            rendered_cols.append(f"{col.get('name')} {col.get('type') or ''}{suffix}".strip())
        lines.append(f"- {table.get('key') or table.get('name')}: " + ", ".join(rendered_cols))
    edges = graph.get("edges") or []
    if edges:
        lines.append("Relationships:")
        for edge in edges[:40]:
            lines.append(f"- {edge.get('join_condition')}")
    return "\n".join(lines)


@dataclass
class SchemaGraphStore:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "schemas").mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            _write_json_atomic(self.index_path, {"schema_version": 1, "schemas": {}})

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    def _schema_path(self, profile_id: str) -> Path:
        return self.root / "schemas" / f"{_safe_profile_id(profile_id)}.schema_graph.json"

    def _read_index(self) -> dict[str, Any]:
        index = _read_json(self.index_path, {"schema_version": 1, "schemas": {}})
        if not isinstance(index.get("schemas"), dict):
            index["schemas"] = {}
        return index

    def _write_index(self, index: dict[str, Any]) -> None:
        index.setdefault("schema_version", 1)
        index.setdefault("schemas", {})
        _write_json_atomic(self.index_path, index)

    def list(self) -> list[dict[str, Any]]:
        schemas = self._read_index().get("schemas", {})
        return sorted([dict(value) for value in schemas.values()], key=lambda item: (item.get("database_name") or "", item.get("database_profile_id") or ""))

    def get(self, profile_id: str, database_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self._schema_path(profile_id)
        if not path.exists():
            return empty_schema_graph(database_profile or {"profile_id": profile_id})
        return _read_json(path, empty_schema_graph(database_profile))

    def save(self, graph: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(graph.get("database_profile_id") or "").strip()
        if not profile_id:
            raise SchemaGraphStoreError("SCHEMA_PROFILE_ID_REQUIRED", "database_profile_id is required to save a schema graph.")
        path = self._schema_path(profile_id)
        _write_json_atomic(path, graph)
        index = self._read_index()
        index["schemas"][profile_id] = {
            "database_profile_id": profile_id,
            "database_name": graph.get("database_name"),
            "schema_file": str(path.relative_to(self.root)),
            "schema_hash": graph.get("schema_hash"),
            "refreshed_at": graph.get("refreshed_at"),
            "status": graph.get("status") or "empty",
            "table_count": graph.get("table_count", len(graph.get("tables") or [])),
            "edge_count": graph.get("edge_count", len(graph.get("edges") or [])),
        }
        self._write_index(index)
        return graph

    def save_from_schema(self, raw_schema: dict[str, Any], database_profile: dict[str, Any]) -> dict[str, Any]:
        return self.save(build_schema_graph(raw_schema, database_profile))

    def delete(self, profile_id: str) -> dict[str, Any]:
        path = self._schema_path(profile_id)
        deleted = False
        if path.exists():
            path.unlink()
            deleted = True
        index = self._read_index()
        if profile_id in index.get("schemas", {}):
            index["schemas"].pop(profile_id, None)
            deleted = True
        self._write_index(index)
        return {"deleted": deleted, "database_profile_id": profile_id}

    def reset(self) -> dict[str, Any]:
        count = 0
        schema_dir = self.root / "schemas"
        if schema_dir.exists():
            for path in schema_dir.glob("*.schema_graph.json"):
                path.unlink()
                count += 1
        self._write_index({"schema_version": 1, "schemas": {}})
        return {"deleted_count": count, "schemas": []}
