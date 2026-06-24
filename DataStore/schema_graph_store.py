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


SCHEMA_GRAPH_VERSION = "2.0.0"


class SchemaGraphStoreError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_profile_id(value: str) -> str:
    raw = str(value or "").strip()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-")
    if not safe:
        safe = "main_database"
    if safe == raw and len(safe) <= 80:
        return safe
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    prefix = safe[:64].rstrip("._-") or "profile"
    return f"{prefix}_{digest}"


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


def _text(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "y"}:
            return True
        if lowered in {"false", "no", "0", "n"}:
            return False
    if value is None:
        return default
    return bool(value)


def _schema_name(value: Any) -> str:
    return _text(value, "public") or "public"


def _node_id(schema: Any, name: Any) -> str:
    return f"{_schema_name(schema)}.{_text(name)}"


def _column_name(column: dict[str, Any]) -> str:
    return _text(column.get("name") or column.get("column_name"))


def _column_type(column: dict[str, Any]) -> str:
    return _text(column.get("data_type") or column.get("type") or column.get("db_type") or "unknown")


def _node_type(value: Any) -> str:
    raw = _text(value, "table").lower().replace(" ", "_")
    aliases = {
        "base_table": "table",
        "foreign_table": "table",
        "materialized_view": "materialized_view",
        "partitioned_table": "partition",
    }
    return aliases.get(raw, raw if raw in {"table", "view", "materialized_view", "partition"} else "table")


def _normalize_index(index: Any) -> dict[str, Any] | None:
    if not isinstance(index, dict):
        return None
    name = _text(index.get("name") or index.get("index_name"))
    columns = index.get("columns") or index.get("column_names") or []
    if isinstance(columns, str):
        columns = [columns]
    columns = [_text(item) for item in columns if _text(item)]
    if not name and not columns and not index.get("definition"):
        return None
    return {
        "name": name or None,
        "columns": columns,
        "unique": _bool(index.get("unique")),
        "definition": index.get("definition") or index.get("index_definition"),
        "method": index.get("method"),
    }


def _normalize_unique_constraint(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        return {"name": None, "columns": [value]}
    if not isinstance(value, dict):
        return None
    columns = value.get("columns") or value.get("column_names") or []
    if isinstance(columns, str):
        columns = [columns]
    columns = [_text(item) for item in columns if _text(item)]
    if not columns:
        return None
    return {"name": _text(value.get("name") or value.get("constraint_name")) or None, "columns": columns}


def _normalize_nodes(raw_schema: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = raw_schema.get("metadata") if isinstance(raw_schema.get("metadata"), dict) else {}
    raw_tables = raw_schema.get("nodes") or raw_schema.get("tables") or metadata.get("tables") or []
    nodes: list[dict[str, Any]] = []
    if not isinstance(raw_tables, list):
        return nodes

    for raw_table in raw_tables:
        if not isinstance(raw_table, dict):
            continue
        name = _text(raw_table.get("name") or raw_table.get("table_name"))
        if not name:
            continue
        schema = _schema_name(raw_table.get("schema") or raw_table.get("table_schema"))
        node_id = _text(raw_table.get("id")) or _node_id(schema, name)
        raw_columns = raw_table.get("columns") or []
        columns: list[dict[str, Any]] = []
        if isinstance(raw_columns, list):
            for position, raw_column in enumerate(raw_columns, start=1):
                if not isinstance(raw_column, dict):
                    continue
                column_name = _column_name(raw_column)
                if not column_name:
                    continue
                columns.append({
                    "id": _text(raw_column.get("id")) or f"{node_id}.{column_name}",
                    "name": column_name,
                    "ordinal_position": int(raw_column.get("ordinal_position") or position),
                    "data_type": _column_type(raw_column),
                    "nullable": _bool(raw_column.get("nullable"), True),
                    "primary_key": _bool(raw_column.get("primary_key")),
                    "foreign_key": _bool(raw_column.get("foreign_key")),
                    "unique": _bool(raw_column.get("unique")),
                    "default": raw_column.get("default") if "default" in raw_column else raw_column.get("column_default"),
                    "generated": raw_column.get("generated") or raw_column.get("generation_expression"),
                    "sensitive": _bool(raw_column.get("sensitive")),
                })

        raw_primary_keys = raw_table.get("primary_keys") or []
        if isinstance(raw_primary_keys, str):
            raw_primary_keys = [raw_primary_keys]
        primary_columns = [_text(item) for item in raw_primary_keys if _text(item)]
        if not primary_columns:
            primary_columns = [column["name"] for column in columns if column["primary_key"]]
        for column in columns:
            if column["name"] in primary_columns:
                column["primary_key"] = True

        raw_unique_constraints = raw_table.get("unique_constraints") or []
        unique_constraints = [item for item in (_normalize_unique_constraint(value) for value in raw_unique_constraints) if item]
        unique_columns = {column for constraint in unique_constraints for column in constraint["columns"]}
        for column in columns:
            if column["name"] in unique_columns:
                column["unique"] = True

        indexes = [item for item in (_normalize_index(value) for value in (raw_table.get("indexes") or [])) if item]
        nodes.append({
            "id": node_id,
            "node_type": _node_type(raw_table.get("node_type") or raw_table.get("type") or raw_table.get("table_type")),
            "schema": schema,
            "name": name,
            "display_name": f"{schema}.{name}",
            "columns": columns,
            "primary_key": {
                "name": _text(raw_table.get("primary_key_name")) or None,
                "columns": primary_columns,
            },
            "unique_constraints": unique_constraints,
            "indexes": indexes,
            "row_count_estimate": raw_table.get("row_count_estimate"),
            "metadata": raw_table.get("metadata") if isinstance(raw_table.get("metadata"), dict) else {},
            # Kept only while constructing relationships. Removed from the final node.
            "_raw_foreign_keys": raw_table.get("foreign_keys") or [],
            "_raw_inherits": raw_table.get("inherits") or raw_table.get("inheritance") or [],
        })
    nodes.sort(key=lambda item: (item["schema"], item["name"]))
    return nodes


def _qualify_node_id(value: Any, default_schema: str, known_ids: set[str]) -> str:
    raw = _text(value)
    if not raw:
        return ""
    if raw in known_ids:
        return raw
    if "." in raw:
        return raw
    candidate = _node_id(default_schema, raw)
    if candidate in known_ids:
        return candidate
    public_candidate = _node_id("public", raw)
    if public_candidate in known_ids:
        return public_candidate
    main_candidate = _node_id("main", raw)
    if main_candidate in known_ids:
        return main_candidate
    matches = [node_id for node_id in known_ids if node_id.rsplit(".", 1)[-1] == raw]
    return matches[0] if len(matches) == 1 else candidate


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return []


def _relationship_id(payload: dict[str, Any]) -> str:
    constraint = _text(payload.get("constraint_name"))
    if constraint:
        return constraint
    core = json.dumps({
        "type": payload.get("relationship_type"),
        "source": payload.get("source"),
        "target": payload.get("target"),
    }, sort_keys=True, ensure_ascii=False)
    return f"rel_{hashlib.sha256(core.encode('utf-8')).hexdigest()[:16]}"


def _relationship_from_fk(node: dict[str, Any], fk: dict[str, Any], known_ids: set[str]) -> dict[str, Any] | None:
    source_columns = _string_list(fk.get("columns") or fk.get("from_columns") or fk.get("column") or fk.get("from_column") or fk.get("from"))
    target_columns = _string_list(fk.get("references_columns") or fk.get("to_columns") or fk.get("references_column") or fk.get("to_column") or fk.get("to"))
    target_table = fk.get("references_table") or fk.get("to_table") or fk.get("table") or fk.get("target_table")
    target_schema = _schema_name(fk.get("references_schema") or fk.get("to_schema") or node.get("schema"))
    target_id = _qualify_node_id(target_table, target_schema, known_ids)
    if not source_columns or not target_id:
        return None
    if not target_columns:
        target_columns = ["id"]
    nullable_lookup = {column["name"]: column["nullable"] for column in node.get("columns") or []}
    payload = {
        "relationship_type": "foreign_key",
        "source": {"node_id": node["id"], "columns": source_columns},
        "target": {"node_id": target_id, "columns": target_columns},
        "constraint_name": _text(fk.get("constraint_name") or fk.get("name")) or None,
        "cardinality": _text(fk.get("cardinality"), "many_to_one") or "many_to_one",
        "on_update": _text(fk.get("on_update"), "NO ACTION") or "NO ACTION",
        "on_delete": _text(fk.get("on_delete"), "NO ACTION") or "NO ACTION",
        "nullable": any(nullable_lookup.get(column, True) for column in source_columns),
        "evidence": "database_constraint",
        "confidence": 1.0,
        "metadata": fk.get("metadata") if isinstance(fk.get("metadata"), dict) else {},
    }
    payload["id"] = _text(fk.get("id")) or _relationship_id(payload)
    return payload


def _normalize_relationship(raw: dict[str, Any], known_ids: set[str], default_schema: str = "public") -> dict[str, Any] | None:
    relation_type = _text(raw.get("relationship_type") or raw.get("type"), "foreign_key").lower()
    aliases = {"fk": "foreign_key", "inherits": "inheritance", "partition": "partition_parent"}
    relation_type = aliases.get(relation_type, relation_type)
    allowed = {"foreign_key", "inheritance", "view_dependency", "materialized_view_dependency", "partition_parent", "association", "inferred"}
    if relation_type not in allowed:
        return None

    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    source_node = source.get("node_id") or raw.get("source_node_id") or raw.get("from_table") or raw.get("child_table")
    target_node = target.get("node_id") or raw.get("target_node_id") or raw.get("to_table") or raw.get("parent_table")
    source_schema = _schema_name(raw.get("source_schema") or raw.get("from_schema") or default_schema)
    target_schema = _schema_name(raw.get("target_schema") or raw.get("to_schema") or default_schema)
    source_id = _qualify_node_id(source_node, source_schema, known_ids)
    target_id = _qualify_node_id(target_node, target_schema, known_ids)
    if not source_id or not target_id:
        return None

    source_columns = _string_list(source.get("columns") or raw.get("source_columns") or raw.get("from_columns") or raw.get("from_column"))
    target_columns = _string_list(target.get("columns") or raw.get("target_columns") or raw.get("to_columns") or raw.get("to_column"))
    payload = {
        "relationship_type": relation_type,
        "source": {"node_id": source_id, "columns": source_columns},
        "target": {"node_id": target_id, "columns": target_columns},
        "constraint_name": _text(raw.get("constraint_name") or raw.get("name")) or None,
        "cardinality": raw.get("cardinality") or ("many_to_one" if relation_type == "foreign_key" else None),
        "on_update": raw.get("on_update"),
        "on_delete": raw.get("on_delete"),
        "nullable": raw.get("nullable"),
        "evidence": _text(raw.get("evidence"), "database_metadata") or "database_metadata",
        "confidence": float(raw.get("confidence", 1.0 if relation_type != "inferred" else 0.5)),
        "metadata": raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
    }
    payload["id"] = _text(raw.get("id")) or _relationship_id(payload)
    return payload


def _normalize_relationships(raw_schema: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known_ids = {node["id"] for node in nodes}
    relationships: list[dict[str, Any]] = []

    for node in nodes:
        raw_foreign_keys = node.get("_raw_foreign_keys") or []
        if isinstance(raw_foreign_keys, list):
            for raw_fk in raw_foreign_keys:
                if isinstance(raw_fk, dict):
                    relationship = _relationship_from_fk(node, raw_fk, known_ids)
                    if relationship:
                        relationships.append(relationship)
        raw_inherits = node.get("_raw_inherits") or []
        if not isinstance(raw_inherits, list):
            raw_inherits = [raw_inherits]
        for parent in raw_inherits:
            if isinstance(parent, dict):
                raw_relation = {"relationship_type": "inheritance", "source_node_id": node["id"], **parent}
            else:
                raw_relation = {"relationship_type": "inheritance", "source_node_id": node["id"], "target_node_id": parent}
            relationship = _normalize_relationship(raw_relation, known_ids, node["schema"])
            if relationship:
                relationships.append(relationship)

    metadata = raw_schema.get("metadata") if isinstance(raw_schema.get("metadata"), dict) else {}
    raw_relationships = raw_schema.get("relationships") or raw_schema.get("edges") or metadata.get("relationships") or []
    if isinstance(raw_relationships, list):
        for raw_relationship in raw_relationships:
            if not isinstance(raw_relationship, dict):
                continue
            relationship = _normalize_relationship(raw_relationship, known_ids)
            if relationship:
                relationships.append(relationship)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for relationship in relationships:
        signature = (
            relationship["relationship_type"],
            relationship["source"]["node_id"],
            tuple(relationship["source"]["columns"]),
            relationship["target"]["node_id"],
            tuple(relationship["target"]["columns"]),
            relationship.get("constraint_name"),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(relationship)

    foreign_key_columns = {
        (relationship["source"]["node_id"], column)
        for relationship in deduped
        if relationship["relationship_type"] == "foreign_key"
        for column in relationship["source"]["columns"]
    }
    for node in nodes:
        for column in node.get("columns") or []:
            column["foreign_key"] = (node["id"], column["name"]) in foreign_key_columns
        node.pop("_raw_foreign_keys", None)
        node.pop("_raw_inherits", None)

    deduped.sort(key=lambda item: (item["relationship_type"], item["source"]["node_id"], item["target"]["node_id"], item["id"]))
    return deduped


def _legacy_table(node: dict[str, Any], relationships: list[dict[str, Any]]) -> dict[str, Any]:
    foreign_keys = []
    for relationship in relationships:
        if relationship["relationship_type"] != "foreign_key" or relationship["source"]["node_id"] != node["id"]:
            continue
        foreign_keys.append({
            "constraint_name": relationship.get("constraint_name"),
            "columns": relationship["source"]["columns"],
            "references_schema": relationship["target"]["node_id"].split(".", 1)[0],
            "references_table": relationship["target"]["node_id"].split(".", 1)[-1],
            "references_columns": relationship["target"]["columns"],
            "on_update": relationship.get("on_update"),
            "on_delete": relationship.get("on_delete"),
        })
    return {
        "schema": node["schema"],
        "name": node["name"],
        "key": node["id"],
        "type": node["node_type"],
        "columns": [
            {
                "name": column["name"],
                "type": column["data_type"],
                "nullable": column["nullable"],
                "primary_key": column["primary_key"],
                "foreign_key": column["foreign_key"],
                "sensitive": column["sensitive"],
            }
            for column in node["columns"]
        ],
        "primary_keys": node["primary_key"]["columns"],
        "foreign_keys": foreign_keys,
        "indexes": node["indexes"],
        "row_count_estimate": node.get("row_count_estimate"),
    }


def _legacy_edge(relationship: dict[str, Any]) -> dict[str, Any]:
    source_columns = relationship["source"]["columns"]
    target_columns = relationship["target"]["columns"]
    from_column = source_columns[0] if source_columns else ""
    to_column = target_columns[0] if target_columns else ""
    from_table = relationship["source"]["node_id"]
    to_table = relationship["target"]["node_id"]
    join_condition = None
    if from_column and to_column:
        join_condition = f"{from_table}.{from_column} = {to_table}.{to_column}"
    return {
        **relationship,
        "type": relationship["relationship_type"],
        "from_table": from_table,
        "from_column": from_column,
        "to_table": to_table,
        "to_column": to_column,
        "join_condition": join_condition,
    }


def _statistics(nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> dict[str, int]:
    connected_ids = {
        endpoint["node_id"]
        for relationship in relationships
        for endpoint in (relationship["source"], relationship["target"])
    }
    return {
        "node_count": len(nodes),
        "table_count": sum(1 for node in nodes if node["node_type"] in {"table", "partition"}),
        "view_count": sum(1 for node in nodes if node["node_type"] == "view"),
        "materialized_view_count": sum(1 for node in nodes if node["node_type"] == "materialized_view"),
        "column_count": sum(len(node["columns"]) for node in nodes),
        "relationship_count": len(relationships),
        "foreign_key_count": sum(1 for relationship in relationships if relationship["relationship_type"] == "foreign_key"),
        "inheritance_count": sum(1 for relationship in relationships if relationship["relationship_type"] == "inheritance"),
        "partition_relationship_count": sum(1 for relationship in relationships if relationship["relationship_type"] == "partition_parent"),
        "isolated_node_count": sum(1 for node in nodes if node["id"] not in connected_ids),
    }


def build_schema_graph(raw_schema: dict[str, Any], database_profile: dict[str, Any]) -> dict[str, Any]:
    raw_schema = raw_schema or {}
    nodes = _normalize_nodes(raw_schema)
    relationships = _normalize_relationships(raw_schema, nodes)
    profile_id = _text(database_profile.get("profile_id") or raw_schema.get("database_profile_id"), "main_database")
    display_name = _text(database_profile.get("display_name") or raw_schema.get("database_name"), profile_id)
    driver = database_profile.get("driver") or database_profile.get("dbms") or raw_schema.get("driver")
    provider = database_profile.get("provider") or raw_schema.get("provider")
    refreshed_at = _now_iso()
    status = "ready" if nodes else "empty"
    warnings = [str(item) for item in (raw_schema.get("warnings") or []) if str(item).strip()]
    stats = _statistics(nodes, relationships)

    canonical_core = {
        "database_profile_id": profile_id,
        "database_name": display_name,
        "driver": driver,
        "provider": provider,
        "nodes": nodes,
        "relationships": relationships,
    }
    schema_hash = hashlib.sha256(json.dumps(canonical_core, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    graph_id = f"schema_{hashlib.sha256(profile_id.encode('utf-8')).hexdigest()[:12]}"
    tables = [_legacy_table(node, relationships) for node in nodes]
    edges = [_legacy_edge(relationship) for relationship in relationships]

    return {
        "schema_version": SCHEMA_GRAPH_VERSION,
        **canonical_core,
        "graph": {
            "id": graph_id,
            "name": display_name,
            "database_engine": driver,
            "generated_at": refreshed_at,
            "status": status,
        },
        "statistics": stats,
        "warnings": warnings,
        "schema_hash": schema_hash,
        "refreshed_at": refreshed_at,
        "status": status,
        "source": "backend_introspection",
        # Backward-compatible projections used by existing agent and API code.
        "tables": tables,
        "edges": edges,
        "table_count": stats["table_count"],
        "edge_count": stats["relationship_count"],
    }


def empty_schema_graph(database_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = database_profile or {}
    profile_id = _text(profile.get("profile_id"))
    display_name = profile.get("display_name") or profile_id or None
    driver = profile.get("driver") or profile.get("dbms")
    return {
        "schema_version": SCHEMA_GRAPH_VERSION,
        "database_profile_id": profile_id or None,
        "database_name": display_name,
        "driver": driver,
        "provider": profile.get("provider"),
        "graph": {
            "id": f"schema_{hashlib.sha256((profile_id or 'empty').encode('utf-8')).hexdigest()[:12]}",
            "name": display_name,
            "database_engine": driver,
            "generated_at": None,
            "status": "empty",
        },
        "nodes": [],
        "relationships": [],
        "statistics": _statistics([], []),
        "warnings": [],
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
    nodes = graph.get("nodes") or graph.get("tables") or []
    relationships = graph.get("relationships") or graph.get("edges") or []
    lines = [
        f"Active database: {graph.get('database_name') or graph.get('database_profile_id')}",
        f"Schema hash: {graph.get('schema_hash') or 'unknown'}",
        "Tables and views:",
    ]
    for node in nodes[:max_tables]:
        columns = node.get("columns") or []
        rendered_columns = []
        for column in columns[:max_columns]:
            flags = []
            if column.get("primary_key"):
                flags.append("PK")
            if column.get("foreign_key"):
                flags.append("FK")
            if column.get("sensitive"):
                flags.append("sensitive")
            suffix = f" [{' '.join(flags)}]" if flags else ""
            column_type = column.get("data_type") or column.get("type") or ""
            rendered_columns.append(f"{column.get('name')} {column_type}{suffix}".strip())
        lines.append(f"- {node.get('id') or node.get('key') or node.get('name')}: " + ", ".join(rendered_columns))
    if relationships:
        lines.append("Relationships:")
        for relationship in relationships[:40]:
            source = relationship.get("source") or {}
            target = relationship.get("target") or {}
            source_columns = ",".join(source.get("columns") or [])
            target_columns = ",".join(target.get("columns") or [])
            relation_type = relationship.get("relationship_type") or relationship.get("type") or "relationship"
            lines.append(f"- {relation_type}: {source.get('node_id') or relationship.get('from_table')}({source_columns}) -> {target.get('node_id') or relationship.get('to_table')}({target_columns})")
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
        stored = _read_json(path, empty_schema_graph(database_profile))
        if stored.get("schema_version") == SCHEMA_GRAPH_VERSION and isinstance(stored.get("nodes"), list):
            return stored
        # Version 1 stored graphs are upgraded in memory. The next refresh saves
        # the canonical v2 contract without mutating historical data on read.
        profile = {
            "profile_id": profile_id or stored.get("database_profile_id"),
            "display_name": (database_profile or {}).get("display_name") or stored.get("database_name"),
            "driver": (database_profile or {}).get("driver") or stored.get("driver"),
            "provider": (database_profile or {}).get("provider") or stored.get("provider"),
        }
        return build_schema_graph(stored, profile)

    def save(self, graph: dict[str, Any]) -> dict[str, Any]:
        profile_id = _text(graph.get("database_profile_id"))
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
            "schema_version": graph.get("schema_version"),
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
