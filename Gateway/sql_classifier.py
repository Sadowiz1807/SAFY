from __future__ import annotations

from dataclasses import dataclass, field
import re

from .sql_normalizer import NormalizedSQL, normalize_sql

SELECT = "SELECT"
INSERT = "INSERT"
UPDATE = "UPDATE"
DELETE = "DELETE"
MERGE = "MERGE"
CREATE = "CREATE"
ALTER = "ALTER"
DROP = "DROP"
TRUNCATE = "TRUNCATE"
RENAME = "RENAME"
GRANT = "GRANT"
REVOKE = "REVOKE"
ADMIN_SECURITY = "ADMIN_SECURITY"
TRANSACTION_CONTROL = "TRANSACTION_CONTROL"
SESSION_CONTROL = "SESSION_CONTROL"
CROSS_DATABASE_OR_SERVER_LEVEL = "CROSS_DATABASE_OR_SERVER_LEVEL"
UNKNOWN = "UNKNOWN"
MULTI_STATEMENT = "MULTI_STATEMENT"
BATCH = "BATCH"

READ_ONLY_TYPES = {SELECT}
MUTATING_TYPES = {INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE, RENAME}
BLOCKED_TYPES = {GRANT, REVOKE, ADMIN_SECURITY, CROSS_DATABASE_OR_SERVER_LEVEL, UNKNOWN, MULTI_STATEMENT}

ADMIN_PREFIXES = {"EXEC", "EXECUTE", "CALL", "COPY", "VACUUM", "ANALYZE", "REINDEX", "PRAGMA"}
TRANSACTION_PREFIXES = {"BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE"}
SESSION_PREFIXES = {"SET", "RESET", "SHOW", "EXPLAIN", "DESCRIBE"}
CROSS_PREFIXES = {"USE", "ATTACH", "DETACH"}
KNOWN_PREFIXES = {SELECT, INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE, RENAME, GRANT, REVOKE}


@dataclass(frozen=True)
class SQLClassification:
    statement_type: str
    normalized: NormalizedSQL
    is_read_only: bool
    is_mutating_cte: bool = False
    is_select_into: bool = False
    has_returning: bool = False
    is_multi_statement: bool = False
    reasons: list[str] = field(default_factory=list)


def _first_token(statement: str) -> str:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", statement.strip())
    return match.group(1).upper() if match else ""


def _has_word(sql: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", sql, re.IGNORECASE) is not None


_SECURITY_DDL_RE = re.compile(
    r"^\s*(?:CREATE|ALTER)\s+(?:OR\s+REPLACE\s+)?"
    r"(?:USER|ROLE|LOGIN|DATABASE|TABLESPACE|SERVER|EXTENSION|LANGUAGE|"
    r"FUNCTION|PROCEDURE|POLICY|PUBLICATION|SUBSCRIPTION)\b",
    re.IGNORECASE,
)
_SECURITY_CLAUSE_RE = re.compile(
    r"\b(?:ALTER\s+SYSTEM|ALTER\s+DEFAULT\s+PRIVILEGES|"
    r"(?:ENABLE|DISABLE|FORCE|NO\s+FORCE)\s+ROW\s+LEVEL\s+SECURITY|"
    r"(?:ENABLE|DISABLE)\s+TRIGGER|OWNER\s+TO|SECURITY\s+(?:DEFINER|INVOKER)|"
    r"BYPASSRLS|AUTHORIZATION\s+[A-Za-z_])\b",
    re.IGNORECASE,
)


def _is_security_sensitive_statement(statement: str) -> bool:
    return bool(_SECURITY_DDL_RE.search(statement) or _SECURITY_CLAUSE_RE.search(statement))


def _classify_single(statement: str) -> tuple[str, list[str], bool, bool, bool]:
    upper = statement.upper()
    first = _first_token(statement)
    reasons: list[str] = []
    is_mutating_cte = False
    is_select_into = False
    has_returning = _has_word(statement, "RETURNING")

    # User-approved DDL may reach sandbox validation, but account, server,
    # executable-code, and row-level-security changes require a distinct
    # administrative workflow. Classify them before generic CREATE/ALTER.
    if _is_security_sensitive_statement(statement):
        return ADMIN_SECURITY, ["admin_or_security_statement"], is_mutating_cte, is_select_into, has_returning

    if first == "WITH":
        # Ordered by risk: mutating CTEs must never collapse to SELECT.
        for token in (DELETE, UPDATE, INSERT, MERGE, DROP, ALTER, TRUNCATE, CREATE, RENAME):
            if _has_word(statement, token):
                is_mutating_cte = True
                reasons.append("mutating_cte_detected")
                return token, reasons, is_mutating_cte, is_select_into, has_returning
        if _has_word(statement, SELECT):
            return SELECT, reasons, is_mutating_cte, is_select_into, has_returning
        return UNKNOWN, ["cte_without_known_terminal_statement"], is_mutating_cte, is_select_into, has_returning

    if re.search(r"\b[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+\b", statement):
        return CROSS_DATABASE_OR_SERVER_LEVEL, ["cross_database_or_server_level_statement"], is_mutating_cte, is_select_into, has_returning

    if first == SELECT:
        if re.search(r"\bSELECT\b.+\bINTO\b", upper, re.DOTALL):
            is_select_into = True
            reasons.append("select_into_detected")
            return CREATE, reasons, is_mutating_cte, is_select_into, has_returning
        return SELECT, reasons, is_mutating_cte, is_select_into, has_returning
    if first in KNOWN_PREFIXES:
        return first, reasons, is_mutating_cte, is_select_into, has_returning
    if first in ADMIN_PREFIXES:
        return ADMIN_SECURITY, ["admin_or_security_statement"], is_mutating_cte, is_select_into, has_returning
    if first in TRANSACTION_PREFIXES:
        return TRANSACTION_CONTROL, ["transaction_control_statement"], is_mutating_cte, is_select_into, has_returning
    if first in SESSION_PREFIXES:
        return SESSION_CONTROL, ["session_control_statement"], is_mutating_cte, is_select_into, has_returning
    if first in CROSS_PREFIXES:
        return CROSS_DATABASE_OR_SERVER_LEVEL, ["cross_database_or_server_level_statement"], is_mutating_cte, is_select_into, has_returning
    return UNKNOWN, ["unknown_statement_type"], is_mutating_cte, is_select_into, has_returning


def classify_sql(sql: str) -> SQLClassification:
    normalized = normalize_sql(sql)
    if not normalized.statements:
        return SQLClassification(UNKNOWN, normalized, False, reasons=["empty_sql"])
    if normalized.is_multi_statement:
        return SQLClassification(MULTI_STATEMENT, normalized, False, is_multi_statement=True, reasons=["multi_statement_detected"])
    if re.search(r"/\*\s*!", normalized.original_sql):
        return SQLClassification(UNKNOWN, normalized, False, reasons=["executable_comment_detected"])
    stype, reasons, is_mutating_cte, is_select_into, has_returning = _classify_single(normalized.statements[0])
    is_read_only = stype == SELECT and not is_mutating_cte and not is_select_into
    return SQLClassification(stype, normalized, is_read_only, is_mutating_cte, is_select_into, has_returning, False, reasons)
