from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json
import re

from Gateway.sql_classifier import (
    ADMIN_SECURITY,
    ALTER,
    CREATE,
    DELETE,
    DROP,
    GRANT,
    INSERT,
    MERGE,
    MULTI_STATEMENT,
    RENAME,
    REVOKE,
    SELECT,
    TRUNCATE,
    UNKNOWN,
    UPDATE,
    classify_sql,
)


CHAT = "CHAT"
READ = "READ"
INSERT_ROWS = "INSERT_ROWS"
UPDATE_ROWS = "UPDATE_ROWS"
DELETE_ROWS = "DELETE_ROWS"
TRUNCATE_TABLE = "TRUNCATE_TABLE"
CREATE_OBJECT = "CREATE_OBJECT"
ALTER_OBJECT = "ALTER_OBJECT"
DROP_OBJECT = "DROP_OBJECT"
DROP_TABLES = "DROP_TABLES"
DROP_DATABASE = "DROP_DATABASE"
GRANT_PERMISSION = "GRANT_PERMISSION"
REVOKE_PERMISSION = "REVOKE_PERMISSION"
ADMIN_OPERATION = "ADMIN_OPERATION"
UNKNOWN_OPERATION = "UNKNOWN"

VALID_OPERATIONS = {
    CHAT,
    READ,
    INSERT_ROWS,
    UPDATE_ROWS,
    DELETE_ROWS,
    TRUNCATE_TABLE,
    CREATE_OBJECT,
    ALTER_OBJECT,
    DROP_OBJECT,
    DROP_TABLES,
    DROP_DATABASE,
    GRANT_PERMISSION,
    REVOKE_PERMISSION,
    ADMIN_OPERATION,
    UNKNOWN_OPERATION,
}

VALID_SCOPES = {
    "NONE",
    "SINGLE_OBJECT",
    "MULTIPLE_OBJECTS",
    "ALL_TABLES",
    "SCHEMA",
    "DATABASE",
}

VALID_EFFECTS = {
    "NONE",
    "READ_ONLY",
    "DATA_WRITE",
    "DATA_DESTRUCTIVE",
    "SCHEMA_WRITE",
    "SCHEMA_DESTRUCTIVE",
    "SECURITY",
    "UNKNOWN",
}

_EXPECTED_STATEMENT_TYPES: dict[str, set[str]] = {
    READ: {SELECT},
    INSERT_ROWS: {INSERT},
    UPDATE_ROWS: {UPDATE, MERGE},
    DELETE_ROWS: {DELETE},
    TRUNCATE_TABLE: {TRUNCATE},
    CREATE_OBJECT: {CREATE},
    ALTER_OBJECT: {ALTER, RENAME},
    DROP_OBJECT: {DROP},
    DROP_TABLES: {DROP},
    DROP_DATABASE: {DROP},
    GRANT_PERMISSION: {GRANT},
    REVOKE_PERMISSION: {REVOKE},
    ADMIN_OPERATION: {ADMIN_SECURITY},
}

def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "1", "on"}:
        return True
    if normalized in {"false", "no", "0", "off"}:
        return False
    return default


_DEFAULT_EFFECTS: dict[str, tuple[str, str]] = {
    CHAT: ("NONE", "NONE"),
    READ: ("READ_ONLY", "NONE"),
    INSERT_ROWS: ("DATA_WRITE", "NONE"),
    UPDATE_ROWS: ("DATA_WRITE", "NONE"),
    DELETE_ROWS: ("DATA_DESTRUCTIVE", "NONE"),
    TRUNCATE_TABLE: ("DATA_DESTRUCTIVE", "NONE"),
    CREATE_OBJECT: ("NONE", "SCHEMA_WRITE"),
    ALTER_OBJECT: ("NONE", "SCHEMA_WRITE"),
    DROP_OBJECT: ("NONE", "SCHEMA_DESTRUCTIVE"),
    DROP_TABLES: ("NONE", "SCHEMA_DESTRUCTIVE"),
    DROP_DATABASE: ("NONE", "SCHEMA_DESTRUCTIVE"),
    GRANT_PERMISSION: ("NONE", "SECURITY"),
    REVOKE_PERMISSION: ("NONE", "SECURITY"),
    ADMIN_OPERATION: ("NONE", "SECURITY"),
    UNKNOWN_OPERATION: ("UNKNOWN", "UNKNOWN"),
}


@dataclass(frozen=True)
class SemanticActionPlan:
    operation: str = UNKNOWN_OPERATION
    scope: str = "NONE"
    object_type: str | None = None
    targets: list[str] = field(default_factory=list)
    data_effect: str = "UNKNOWN"
    schema_effect: str = "UNKNOWN"
    requires_schema: bool = False
    requires_confirmation: bool = False
    confidence: float = 0.0
    rationale: str = ""
    source: str = "model"
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Any, *, source: str = "model") -> "SemanticActionPlan":
        if not isinstance(payload, dict):
            return cls(source=source, warnings=["semantic_plan_not_an_object"])

        raw_operation = str(payload.get("operation") or payload.get("intent") or UNKNOWN_OPERATION).strip().upper()
        aliases = {
            "SELECT": READ,
            "READ_ONLY": READ,
            "READ_SQL": READ,
            "INSERT": INSERT_ROWS,
            "UPDATE": UPDATE_ROWS,
            "DELETE": DELETE_ROWS,
            "TRUNCATE": TRUNCATE_TABLE,
            "CREATE": CREATE_OBJECT,
            "ALTER": ALTER_OBJECT,
            "DROP": DROP_OBJECT,
            "DROP_ALL_TABLES": DROP_TABLES,
            "DELETE_TABLES": DROP_TABLES,
            "REMOVE_TABLES": DROP_TABLES,
            "PURGE_TABLES": DROP_TABLES,
            "RESET_SCHEMA": DROP_TABLES,
            "DROP_TABLE": DROP_OBJECT,
            "REMOVE_OBJECT": DROP_OBJECT,
            "GRANT": GRANT_PERMISSION,
            "REVOKE": REVOKE_PERMISSION,
            "DATABASE_TASK": UNKNOWN_OPERATION,
            "WRITE_OR_DDL": UNKNOWN_OPERATION,
        }
        operation = aliases.get(raw_operation, raw_operation)
        warnings: list[str] = []
        if operation not in VALID_OPERATIONS:
            warnings.append(f"unsupported_operation:{operation}")
            operation = UNKNOWN_OPERATION

        scope = str(payload.get("scope") or "NONE").strip().upper()
        if scope not in VALID_SCOPES:
            warnings.append(f"unsupported_scope:{scope}")
            scope = "NONE"

        object_type = (str(payload.get("object_type") or "").strip().upper() or None)
        if operation == DROP_OBJECT and scope == "ALL_TABLES" and object_type in {None, "TABLE", "TABLES"}:
            operation = DROP_TABLES
            object_type = "TABLE"

        raw_targets = payload.get("targets") or payload.get("target_names") or []
        if isinstance(raw_targets, str):
            raw_targets = [raw_targets]
        targets = [str(value).strip() for value in raw_targets if str(value).strip()] if isinstance(raw_targets, list) else []

        default_data, default_schema = _DEFAULT_EFFECTS.get(operation, ("UNKNOWN", "UNKNOWN"))
        data_effect = str(payload.get("data_effect") or default_data).strip().upper()
        schema_effect = str(payload.get("schema_effect") or default_schema).strip().upper()
        if data_effect not in VALID_EFFECTS:
            warnings.append(f"unsupported_data_effect:{data_effect}")
            data_effect = default_data
        if schema_effect not in VALID_EFFECTS:
            warnings.append(f"unsupported_schema_effect:{schema_effect}")
            schema_effect = default_schema

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
            warnings.append("invalid_confidence")
        confidence = max(0.0, min(confidence, 1.0))

        requires_schema_default = operation in {
            READ,
            INSERT_ROWS,
            UPDATE_ROWS,
            DELETE_ROWS,
            TRUNCATE_TABLE,
            CREATE_OBJECT,
            ALTER_OBJECT,
            DROP_OBJECT,
            DROP_TABLES,
        }
        requires_confirmation_default = operation in {
            INSERT_ROWS,
            UPDATE_ROWS,
            DELETE_ROWS,
            TRUNCATE_TABLE,
            CREATE_OBJECT,
            ALTER_OBJECT,
            DROP_OBJECT,
            DROP_TABLES,
            DROP_DATABASE,
            GRANT_PERMISSION,
            REVOKE_PERMISSION,
            ADMIN_OPERATION,
        }

        return cls(
            operation=operation,
            scope=scope,
            object_type=object_type,
            targets=targets,
            data_effect=data_effect,
            schema_effect=schema_effect,
            requires_schema=_as_bool(payload.get("requires_schema"), requires_schema_default),
            requires_confirmation=_as_bool(payload.get("requires_confirmation"), requires_confirmation_default),
            confidence=confidence,
            rationale=str(payload.get("rationale") or payload.get("reason") or "").strip(),
            source=source,
            warnings=warnings,
        )

    @property
    def is_database_operation(self) -> bool:
        return self.operation not in {CHAT, UNKNOWN_OPERATION}

    @property
    def is_read(self) -> bool:
        return self.operation == READ

    @property
    def is_destructive(self) -> bool:
        return self.data_effect == "DATA_DESTRUCTIVE" or self.schema_effect == "SCHEMA_DESTRUCTIVE"

    @property
    def can_generate_sql(self) -> bool:
        return self.is_database_operation and self.confidence >= 0.60 and not self.warnings and validate_plan_coherence(self).get("ok")

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "scope": self.scope,
            "object_type": self.object_type,
            "targets": list(self.targets),
            "data_effect": self.data_effect,
            "schema_effect": self.schema_effect,
            "requires_schema": self.requires_schema,
            "requires_confirmation": self.requires_confirmation,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "source": self.source,
            "warnings": list(self.warnings),
        }


def plan_from_explicit_sql(sql: str) -> SemanticActionPlan:
    classification = classify_sql(sql)
    operation_by_statement = {
        SELECT: READ,
        INSERT: INSERT_ROWS,
        UPDATE: UPDATE_ROWS,
        MERGE: UPDATE_ROWS,
        DELETE: DELETE_ROWS,
        TRUNCATE: TRUNCATE_TABLE,
        CREATE: CREATE_OBJECT,
        ALTER: ALTER_OBJECT,
        RENAME: ALTER_OBJECT,
        DROP: DROP_OBJECT,
        GRANT: GRANT_PERMISSION,
        REVOKE: REVOKE_PERMISSION,
        ADMIN_SECURITY: ADMIN_OPERATION,
    }
    operation = operation_by_statement.get(classification.statement_type, UNKNOWN_OPERATION)
    data_effect, schema_effect = _DEFAULT_EFFECTS.get(operation, ("UNKNOWN", "UNKNOWN"))
    return SemanticActionPlan(
        operation=operation,
        scope="SINGLE_OBJECT",
        data_effect=data_effect,
        schema_effect=schema_effect,
        requires_schema=False,
        requires_confirmation=operation != READ,
        confidence=1.0 if operation != UNKNOWN_OPERATION else 0.0,
        rationale="Derived from explicit SQL supplied by the user.",
        source="explicit_sql",
        warnings=[] if operation != UNKNOWN_OPERATION else ["explicit_sql_unclassified"],
    )


def validate_plan_coherence(plan: SemanticActionPlan) -> dict[str, Any]:
    errors: list[str] = []
    object_type = (plan.object_type or "").upper()
    if plan.operation == READ:
        if object_type and object_type not in {"TABLE", "VIEW", "UNKNOWN"}:
            errors.append("read_requires_table_or_view")
        if plan.scope in {"SINGLE_OBJECT", "MULTIPLE_OBJECTS"} and not plan.targets:
            errors.append("read_target_missing")
    if plan.operation == DROP_DATABASE:
        if object_type != "DATABASE":
            errors.append("drop_database_requires_database_object")
        if plan.scope != "DATABASE":
            errors.append("drop_database_requires_database_scope")
    if plan.operation == DROP_TABLES:
        if object_type not in {"TABLE", "TABLES"}:
            errors.append("drop_tables_requires_table_object")
        if plan.scope == "ALL_TABLES" and not plan.requires_schema:
            errors.append("drop_all_tables_requires_schema")
    if plan.operation in {DROP_OBJECT, TRUNCATE_TABLE, DELETE_ROWS, UPDATE_ROWS} and plan.scope == "SINGLE_OBJECT" and not plan.targets:
        errors.append("target_missing")
    if errors:
        return {
            "ok": False,
            "code": "SEMANTIC_PLAN_INCOHERENT",
            "message": "Semantic action plan fields are inconsistent.",
            "errors": errors,
        }
    return {"ok": True, "code": "SEMANTIC_PLAN_COHERENT", "message": "Semantic action plan is coherent."}


def _normalize_target_name(value: str) -> str:
    return ".".join(part.strip().strip('"`[]').lower() for part in str(value or "").strip().split(".") if part.strip())


def validate_sql_against_plan(sql: str, plan: SemanticActionPlan) -> dict[str, Any]:
    coherence = validate_plan_coherence(plan)
    if not coherence.get("ok"):
        return coherence
    if not sql:
        return {
            "ok": False,
            "code": "SQL_MISSING",
            "message": "No SQL was generated for the semantic action plan.",
            "statement_type": None,
            "expected_statement_types": sorted(_EXPECTED_STATEMENT_TYPES.get(plan.operation, set())),
        }

    classification = classify_sql(sql)
    expected = _EXPECTED_STATEMENT_TYPES.get(plan.operation, set())
    if plan.operation in {CHAT, UNKNOWN_OPERATION}:
        return {
            "ok": False,
            "code": "SEMANTIC_PLAN_NOT_EXECUTABLE",
            "message": "The semantic action plan is not an executable database operation.",
            "statement_type": classification.statement_type,
            "expected_statement_types": [],
        }
    if classification.statement_type in {UNKNOWN, MULTI_STATEMENT}:
        return {
            "ok": False,
            "code": "SQL_UNCLASSIFIABLE" if classification.statement_type == UNKNOWN else "SQL_MULTI_STATEMENT_REQUIRES_DETERMINISTIC_BATCH",
            "message": "Generated SQL could not be safely classified as one operation.",
            "statement_type": classification.statement_type,
            "expected_statement_types": sorted(expected),
            "reasons": list(classification.reasons),
        }
    if classification.statement_type not in expected:
        return {
            "ok": False,
            "code": "INTENT_SQL_MISMATCH",
            "message": f"Semantic operation {plan.operation} is incompatible with SQL statement {classification.statement_type}.",
            "statement_type": classification.statement_type,
            "expected_statement_types": sorted(expected),
            "reasons": list(classification.reasons),
        }
    if plan.is_read and not classification.is_read_only:
        return {
            "ok": False,
            "code": "READ_PLAN_PRODUCED_MUTATION",
            "message": "A read plan produced mutating SQL.",
            "statement_type": classification.statement_type,
            "expected_statement_types": sorted(expected),
        }
    if not plan.is_read and classification.is_read_only:
        return {
            "ok": False,
            "code": "MUTATION_PLAN_PRODUCED_READ",
            "message": "A write or schema plan produced read-only SQL.",
            "statement_type": classification.statement_type,
            "expected_statement_types": sorted(expected),
        }
    if plan.targets:
        from Gateway.statement_target_extractor import extract_targets
        extraction = extract_targets(classification)
        sql_targets = {_normalize_target_name(target) for target in extraction.targets}
        plan_targets = {_normalize_target_name(target) for target in plan.targets}
        if not sql_targets:
            return {
                "ok": False,
                "code": "INTENT_SQL_TARGET_UNRESOLVED",
                "message": "Generated SQL target could not be extracted safely for comparison with the semantic action plan.",
                "statement_type": classification.statement_type,
                "expected_targets": sorted(plan_targets),
                "actual_targets": [],
                "warnings": list(extraction.warnings),
            }
        if sql_targets and plan_targets and not sql_targets.issubset(plan_targets):
            return {
                "ok": False,
                "code": "INTENT_SQL_TARGET_MISMATCH",
                "message": "Generated SQL targets do not match the semantic action plan targets.",
                "statement_type": classification.statement_type,
                "expected_targets": sorted(plan_targets),
                "actual_targets": sorted(sql_targets),
            }
        if plan.scope in {"MULTIPLE_OBJECTS", "ALL_TABLES"} and sql_targets != plan_targets:
            return {
                "ok": False,
                "code": "INTENT_SQL_TARGET_SET_MISMATCH",
                "message": "Generated SQL target set does not exactly match the semantic action plan scope.",
                "statement_type": classification.statement_type,
                "expected_targets": sorted(plan_targets),
                "actual_targets": sorted(sql_targets),
            }
    return {
        "ok": True,
        "code": "PLAN_SQL_CONSISTENT",
        "message": "Generated SQL matches the semantic action plan.",
        "statement_type": classification.statement_type,
        "expected_statement_types": sorted(expected),
        "read_only": classification.is_read_only,
    }


def database_dialect(target: dict[str, Any] | None) -> str:
    payload = target or {}
    value = str(
        payload.get("database_type")
        or payload.get("driver")
        or payload.get("dbms")
        or ""
    ).strip().lower()
    aliases = {
        "postgres": "postgresql",
        "supabase": "postgresql",
        "supabase_rpc": "postgresql",
        "mariadb": "mysql",
        "mssql": "sqlserver",
        "sql_server": "sqlserver",
    }
    return aliases.get(value, value)


def _qualified_table_name(table: dict[str, Any], dialect: str) -> str:
    key = str(table.get("key") or "").strip()
    schema = str(table.get("schema") or table.get("schema_name") or "").strip()
    name = str(table.get("name") or table.get("table_name") or "").strip()
    if key and "." in key:
        parts = [part for part in key.split(".") if part]
    elif schema and name:
        parts = [schema, name]
    elif key:
        parts = [key]
    elif name:
        parts = [name]
    else:
        return ""

    if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$#@]*", part) for part in parts):
        return ""
    if dialect == "sqlserver":
        return ".".join(f"[{part}]" for part in parts)
    if dialect == "mysql":
        return ".".join(f"`{part}`" for part in parts)
    return ".".join(f'"{part}"' for part in parts)


def _table_keys_in_dependency_order(graph: dict[str, Any]) -> list[str]:
    tables = graph.get("tables") or []
    keys = [str(table.get("key") or table.get("name") or "").strip() for table in tables]
    keys = [key for key in keys if key]
    key_set = set(keys)
    adjacency: dict[str, set[str]] = {key: set() for key in keys}
    indegree: dict[str, int] = {key: 0 for key in keys}

    # Schema Graph edges are child/from -> parent/to. Drop children before parents.
    for edge in graph.get("edges") or graph.get("relationships") or []:
        child = str(edge.get("from_table") or edge.get("source_table") or "").strip()
        parent = str(edge.get("to_table") or edge.get("target_table") or "").strip()
        if child in key_set and parent in key_set and parent not in adjacency[child]:
            adjacency[child].add(parent)
            indegree[parent] += 1

    queue = [key for key in keys if indegree[key] == 0]
    ordered: list[str] = []
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for parent in adjacency[current]:
            indegree[parent] -= 1
            if indegree[parent] == 0:
                queue.append(parent)
    if len(ordered) != len(keys):
        return keys
    return ordered


def render_deterministic_sql(
    plan: SemanticActionPlan,
    schema_graph: dict[str, Any] | None,
    target: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if plan.operation != DROP_TABLES or plan.scope != "ALL_TABLES":
        return None
    if not schema_graph or schema_graph.get("status") != "ready":
        return {
            "ok": False,
            "code": "SCHEMA_REQUIRED_FOR_DROP_ALL_TABLES",
            "message": "A ready Schema Graph is required before generating DROP statements for all tables.",
            "sql": "",
        }

    dialect = database_dialect(target)
    tables = schema_graph.get("tables") or []
    by_key = {
        str(table.get("key") or table.get("name") or "").strip(): table
        for table in tables
        if str(table.get("key") or table.get("name") or "").strip()
    }
    ordered_keys = _table_keys_in_dependency_order(schema_graph)
    qualified = [
        _qualified_table_name(by_key[key], dialect)
        for key in ordered_keys
        if key in by_key
    ]
    qualified = [name for name in qualified if name]
    if not qualified:
        return {
            "ok": False,
            "code": "NO_USER_TABLES_IN_SCHEMA_GRAPH",
            "message": "The active Schema Graph does not contain any safe user table identifiers.",
            "sql": "",
        }

    if dialect in {"postgresql", "mysql", "sqlserver"}:
        suffix = " CASCADE" if dialect == "postgresql" else ""
        sql = f"DROP TABLE IF EXISTS {', '.join(qualified)}{suffix};"
        return {
            "ok": True,
            "code": "DETERMINISTIC_DROP_ALL_TABLES",
            "message": "Generated a deterministic single-statement DROP plan from the active Schema Graph.",
            "sql": sql,
            "dialect": dialect,
            "targets": qualified,
        }

    if len(qualified) == 1 and dialect in {"sqlite", "oracle"}:
        return {
            "ok": True,
            "code": "DETERMINISTIC_DROP_SINGLE_TABLE",
            "message": "Generated a deterministic DROP statement from the active Schema Graph.",
            "sql": f"DROP TABLE {qualified[0]};",
            "dialect": dialect,
            "targets": qualified,
        }

    return {
        "ok": False,
        "code": "DETERMINISTIC_BATCH_NOT_SUPPORTED",
        "message": f"Dialect {dialect or 'unknown'} requires a dedicated guarded batch executor for dropping multiple tables.",
        "sql": "",
        "dialect": dialect,
        "targets": qualified,
    }


def semantic_planner_contract() -> str:
    return json.dumps(
        {
            "operation": sorted(VALID_OPERATIONS),
            "scope": sorted(VALID_SCOPES),
            "object_type": "TABLE|VIEW|INDEX|SCHEMA|DATABASE|ROW|UNKNOWN|null",
            "targets": ["schema.object"],
            "data_effect": sorted(VALID_EFFECTS),
            "schema_effect": sorted(VALID_EFFECTS),
            "requires_schema": "boolean",
            "requires_confirmation": "boolean",
            "confidence": "number from 0 to 1",
            "rationale": "short explanation",
        },
        ensure_ascii=False,
    )
