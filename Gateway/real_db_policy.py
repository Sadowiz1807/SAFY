
from __future__ import annotations

import re
from Gateway.sql_classifier import INSERT, SELECT, SESSION_CONTROL, classify_sql

DIALECT_BLOCK_RE = re.compile(r"\b(EXEC|EXECUTE|CALL|BULK\s+INSERT|BACKUP|RESTORE|MERGE|REPLACE|LOAD\s+DATA|COPY|BEGIN|DECLARE|GRANT|REVOKE)\b|\b(?:sp|xp)_[A-Za-z0-9_]+\b", re.I)

SENSITIVE_RE = re.compile(r"password|token|secret|email|phone|ssn|salary|dob|address|credit|card", re.I)


def real_db_policy(sql: str, schema: dict | None = None) -> dict:
    c = classify_sql(sql)
    warnings = list(c.reasons)
    upper = c.normalized.normalized_sql.upper()
    readonly_metadata = c.statement_type == SESSION_CONTROL and (
        upper.startswith("SHOW ") or upper.startswith("DESCRIBE ") or upper.startswith("EXPLAIN SELECT")
    )
    if DIALECT_BLOCK_RE.search(upper):
        return blocked("DB_UNSAFE_SQL_BLOCKED", c, warnings + ["dialect_dangerous_statement_blocked"])
    if c.statement_type == INSERT:
        return blocked("DB_INSERT_BLOCKED", c, warnings + ["insert_blocked_agent_direct_read_only"])
    if not ((c.statement_type == SELECT and c.is_read_only) or readonly_metadata):
        return blocked("DB_UNSAFE_SQL_BLOCKED", c, warnings + ["agent_direct_real_db_readonly_only"])
    if " FOR UPDATE" in upper or "LOCK IN SHARE MODE" in upper:
        return blocked("DB_READONLY_VIOLATION", c, warnings + ["select_locking_clause_blocked"])
    sensitive = bool(SENSITIVE_RE.search(c.normalized.normalized_sql))
    broad = " LIMIT " not in upper and any(tok in upper for tok in ["SELECT *", " FROM "])
    confirmation = sensitive or broad
    return {"allowed": True, "error_code": None, "statement_type": c.statement_type, "normalized_sql": c.normalized.normalized_sql, "confirmation_required": confirmation, "warnings": warnings + (["sensitive_or_broad_select_requires_confirmation"] if confirmation else []), "sensitive_select": sensitive, "broad_select": broad}


def blocked(code: str, c, warnings: list[str]) -> dict:
    return {"allowed": False, "error_code": code, "statement_type": c.statement_type, "normalized_sql": c.normalized.normalized_sql, "confirmation_required": False, "warnings": warnings, "blocked_sql_display_allowed": True, "blocked_message": "This operation is blocked for agent-direct execution because real database agent actions are read-only. User Execute Box operations must pass sandbox validation before real execution."}
