from __future__ import annotations

import re
import unicodedata
from typing import Any

SUPPORTED_TYPES = {"operation_forbidden", "column_required", "column_forbidden", "table_required", "schema_assertion", "naming_convention"}
DESTRUCTIVE_FIX_WORDS = {"drop", "delete", "truncate", "remove"}


class SandboxRuleEngine:
    def parse_rules(self, raw_text: str) -> tuple[list[dict[str, Any]], list[str]]:
        text = raw_text or ""
        warnings: list[str] = []
        parsed: list[dict[str, Any]] = []
        structured = self._parse_structured(text)
        if structured:
            for rule in structured:
                if rule.get("type") not in SUPPORTED_TYPES:
                    warnings.append(f"Unsupported rule type: {rule.get('type')}")
                parsed.append(rule)
            return parsed, warnings

        lower = text.lower()
        norm = _normalize_rule_text(text)
        lower_norm_pairs = (lower, norm)

        # Operation-forbidden rules. Use both original and accent-stripped text so
        # xóa/xoá, hủy/huỷ and no-diacritic user input are handled consistently.
        drop_patterns = [
            r"\bdrop\s+table\b",
            r"\bdrop\s+bang\b",
            r"(?:khong\s+(?:duoc|cho)|cam)\s+(?:xoa|huy)\s+bang",
        ]
        if any(re.search(pattern, norm, re.I) for pattern in drop_patterns):
            parsed.append({"id": "forbid_drop_table", "type": "operation_forbidden", "severity": "block", "operation": "DROP_TABLE"})

        truncate_patterns = [
            r"\btruncate\b",
            r"(?:khong\s+(?:duoc|cho)|cam)\s+(?:lam\s+rong|xoa\s+sach|xoa\s+sach\s+du\s+lieu)\s+(?:bang|table)",
        ]
        if any(re.search(pattern, norm, re.I) for pattern in truncate_patterns):
            parsed.append({"id": "forbid_truncate", "type": "operation_forbidden", "severity": "block", "operation": "TRUNCATE"})

        if any(phrase in norm for phrase in ("khoa chinh", "primary key")):
            parsed.append({"id": "require_primary_key", "type": "schema_assertion", "severity": "block", "applies_to": "create_table", "assertion": "every_new_table_must_have_primary_key"})

        # Natural-language rule for every/new table requiring a column.
        # Examples:
        # - "Mỗi bảng phải có id."
        # - "Bảng nào cũng phải có id."
        # - "Mọi bảng bắt buộc có ID."
        # Identifier comparisons are case-insensitive, so SQL column "ID" satisfies rule column "id".
        every_table_column_patterns = [
            r"(?:moi|mọi|tat\s*ca|tất\s*cả)\s+(?:bang|bảng|table)\s+(?:moi\s+|mới\s+)?(?:bat\s*buoc\s*(?:phai\s*)?co|bắt\s*buộc\s*(?:phải\s*)?có|phai\s+co|phải\s+có|can\s+co|cần\s+có)\s+(?:cot\s+|cột\s+)?([A-Za-z_][\w]*)",
            r"(?:bang|bảng)\s+nao\s+cung\s+(?:bat\s*buoc\s*(?:phai\s*)?co|bắt\s*buộc\s*(?:phải\s*)?có|phai\s+co|phải\s+có|can\s+co|cần\s+có)\s+(?:cot\s+|cột\s+)?([A-Za-z_][\w]*)",
            r"(?:every|all)\s+(?:new\s+)?table\s+(?:must\s+have|requires?|required\s+to\s+have)\s+(?:column\s+)?([A-Za-z_][\w]*)",
        ]
        seen_assertions: set[str] = set()
        for pattern in every_table_column_patterns:
            for haystack in lower_norm_pairs:
                for m in re.finditer(pattern, haystack, re.I):
                    column = m.group(1)
                    key = _normalize_identifier(column)
                    if key not in seen_assertions:
                        seen_assertions.add(key)
                        parsed.append({
                            "id": f"require_new_table_{key}_column",
                            "type": "schema_assertion",
                            "severity": "block",
                            "applies_to": "create_table",
                            "assertion": "every_new_table_must_have_column",
                            "column": column,
                        })

        # Vietnamese/English natural-language column requirements for a specific table.
        # Examples:
        # - "Bảng customers phải có email."
        # - "Bảng customers bắt buộc có email."
        # - "customers phải có cột email."
        column_patterns = [
            r"(?:bang|bảng|table)\s+([A-Za-z_][\w]*)\s+(?:bat\s*buoc\s*(?:phai\s*)?co|bắt\s*buộc\s*(?:phải\s*)?có|phai\s+co|phải\s+có|can\s+co|cần\s+có|must\s+have|requires?|required\s+to\s+have)\s+(?:cot\s+|cột\s+|column\s+)?([A-Za-z_][\w]*)",
            r"([A-Za-z_][\w]*)\s+(?:bat\s*buoc\s*(?:phai\s*)?co|bắt\s*buộc\s*(?:phải\s*)?có|phai\s+co|phải\s+có|can\s+co|cần\s+có|must\s+have|requires?)\s+(?:cot\s+|cột\s+|column\s+)([A-Za-z_][\w]*)",
            r"(?:trong\s+)?(?:bang|bảng)\s+([A-Za-z_][\w]*)\s+(?:bat\s*buoc\s*(?:phai\s*)?co|bắt\s*buộc\s*(?:phải\s*)?có|phai\s+co|phải\s+có|can\s+co|cần\s+có)\s+(?:cot\s+|cột\s+)?([A-Za-z_][\w]*)",
        ]
        seen_columns: set[tuple[str, str]] = set()
        for pattern in column_patterns:
            for haystack in lower_norm_pairs:
                for m in re.finditer(pattern, haystack, re.I):
                    table = m.group(1)
                    column = m.group(2)
                    key = (_normalize_identifier(table), _normalize_identifier(column))
                    if key not in seen_columns:
                        seen_columns.add(key)
                        parsed.append({"id": f"require_{key[0]}_{key[1]}", "type": "column_required", "severity": "block", "table": table, "column": column})

        # Natural-language forbidden-column rules, mainly for conflict detection.
        column_forbidden_patterns = [
            r"(?:bang|bảng|table)\s+([A-Za-z_][\w]*)\s+(?:khong\s+(?:duoc|cho)|không\s+(?:được|cho)|cam|cấm)\s+(?:co|có)\s+(?:cot\s+|cột\s+|column\s+)?([A-Za-z_][\w]*)",
        ]
        seen_forbidden_columns: set[tuple[str, str]] = set()
        for pattern in column_forbidden_patterns:
            for haystack in lower_norm_pairs:
                for m in re.finditer(pattern, haystack, re.I):
                    table = m.group(1)
                    column = m.group(2)
                    key = (_normalize_identifier(table), _normalize_identifier(column))
                    if key not in seen_forbidden_columns:
                        seen_forbidden_columns.add(key)
                        parsed.append({"id": f"forbid_{key[0]}_{key[1]}", "type": "column_forbidden", "severity": "block", "table": table, "column": column})

        # Natural-language required table rules, used for rule-vs-rule conflicts.
        table_patterns = [
            r"(?:database|csdl|cơ\s*sở\s*dữ\s*liệu|co\s*so\s*du\s*lieu|he\s*thong|hệ\s*thống)?\s*(?:bat\s*buoc\s*(?:phai\s*)?co|bắt\s*buộc\s*(?:phải\s*)?có|phai\s+co|phải\s+có|can\s+co|cần\s+có|must\s+have|requires?)\s+(?:bang|bảng|table)\s+([A-Za-z_][\w]*)",
            r"(?:bat\s*buoc\s+ton\s*tai|bắt\s*buộc\s+tồn\s*tại|phai\s+ton\s*tai|phải\s+tồn\s+tại)\s+(?:bang|bảng|table)\s+([A-Za-z_][\w]*)",
            r"(?:bang|bảng|table)\s+([A-Za-z_][\w]*)\s+(?:bat\s*buoc\s*(?:phai\s*)?ton\s*tai|bắt\s*buộc\s*(?:phải\s*)?tồn\s*tại|phai\s+ton\s*tai|phải\s+tồn\s+tại|must\s+exist|required)",
        ]
        seen_tables: set[str] = set()
        for pattern in table_patterns:
            for haystack in lower_norm_pairs:
                for m in re.finditer(pattern, haystack, re.I):
                    table = m.group(1)
                    key = _normalize_identifier(table)
                    if key not in seen_tables:
                        seen_tables.add(key)
                        parsed.append({"id": f"require_table_{key}", "type": "table_required", "severity": "block", "table": table})

        # Natural-language CREATE TABLE forbid rules with table name.
        create_forbid_patterns = [
            r"(?:khong\s+(?:cho|duoc)|không\s+(?:cho|được)|cam|cấm|forbid|do\s+not\s+allow)\s+(?:tao|tạo|create)\s+(?:bang|bảng|table)\s+([A-Za-z_][\w]*)",
        ]
        for pattern in create_forbid_patterns:
            for haystack in lower_norm_pairs:
                create_forbid = re.search(pattern, haystack, re.I)
                if create_forbid:
                    table = create_forbid.group(1)
                    parsed.append({"id": f"forbid_create_{_normalize_identifier(table)}", "type": "operation_forbidden", "severity": "block", "operation": "CREATE_TABLE", "table": table})
                    break
        if not parsed:
            warnings.append("Ambiguous rule could not be parsed into deterministic constraints.")
        return parsed, warnings

    def validate_rule(self, rule: dict[str, Any], active_rules: list[dict[str, Any]] | None = None, schema_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        parsed, warnings = self.parse_rules(rule.get("raw_text") or "")
        conflicts = self._rule_conflicts(parsed, active_rules or [])
        schema_conflicts = self._schema_conflicts(parsed, schema_graph or {})
        status = "draft"
        options: list[str] = []
        if conflicts:
            status = "conflict_rule"
            options = ["Edit new rule", "Edit active rule", "Disable active rule", "Replace active rule", "Keep new rule as draft", "Cancel"]
        elif schema_conflicts:
            status = "pending_user_decision"
            options = ["Edit rule to match schema", "Generate additive schema draft", "Activate future-only", "Save as warning", "Keep draft", "Cancel"]
        elif warnings or not parsed:
            status = "warning_only"
        else:
            status = "draft"
        return {
            "rule_id": rule.get("rule_id"),
            "status": status,
            "parsed_rules": parsed,
            "warnings": warnings,
            "conflict_type": "rule" if conflicts else "schema" if schema_conflicts else None,
            "conflicts": conflicts + schema_conflicts,
            "options": options,
        }

    def activate(self, rule: dict[str, Any], active_rules: list[dict[str, Any]] | None = None, schema_graph: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        report = self.validate_rule(rule, active_rules, schema_graph)
        rule = {**rule, "parsed_rules": report["parsed_rules"], "validated_at": _now(), "status": report["status"]}
        if report["status"] == "draft":
            rule["status"] = "active"
            rule["activated_at"] = _now()
            report["status"] = "active"
        return rule, report

    def check_sql(self, sql: str, active_rules: list[dict[str, Any]]) -> dict[str, Any]:
        violations = []
        normalized = sql.lower()
        create_table_columns = _create_table_columns(sql)
        has_create_table = bool(re.search(r"\bcreate\s+table\b", normalized))
        for rule in active_rules:
            if rule.get("status") != "active":
                continue
            for parsed in rule.get("parsed_rules") or []:
                typ = parsed.get("type")
                op = str(parsed.get("operation") or "").upper()
                if typ == "operation_forbidden" and op == "DROP_TABLE" and re.search(r"\bdrop\s+table\b", normalized):
                    violations.append(_violation(rule, "DROP TABLE is forbidden by active sandbox rule."))
                if typ == "operation_forbidden" and op == "TRUNCATE" and re.search(r"\btruncate\b", normalized):
                    violations.append(_violation(rule, "TRUNCATE is forbidden by active sandbox rule."))
                if typ == "schema_assertion" and parsed.get("assertion") == "every_new_table_must_have_primary_key":
                    if has_create_table and "primary key" not in normalized:
                        violations.append(_violation(rule, "CREATE TABLE must include a primary key by active sandbox rule."))
                if typ == "schema_assertion" and parsed.get("assertion") == "every_new_table_must_have_column":
                    required = _normalize_identifier(parsed.get("column"))
                    if has_create_table and required and required not in create_table_columns:
                        violations.append(_violation(rule, f"CREATE TABLE must include column {parsed.get('column')} by active sandbox rule."))
        return {"status": "failed" if violations else "passed", "violations": violations}

    def generate_additive_schema_draft(self, rule: dict[str, Any]) -> dict[str, Any]:
        parsed, _warnings = self.parse_rules(rule.get("raw_text") or "")
        statements = []
        for item in parsed:
            if item.get("type") == "column_required":
                table = _ident(item.get("table"))
                column = _ident(item.get("column"))
                statements.append(f"ALTER TABLE {table} ADD COLUMN {column} text;")
            if item.get("type") == "table_required":
                table = _ident(item.get("table"))
                statements.append(f"CREATE TABLE {table} (id bigint PRIMARY KEY);")
        sql = "\n".join(statements)
        if any(word in sql.lower() for word in DESTRUCTIVE_FIX_WORDS):
            return {"success": False, "code": "DESTRUCTIVE_SCHEMA_FIX_FORBIDDEN", "sql": ""}
        return {"success": bool(sql), "sql": sql, "draft_only": True}

    def _parse_structured(self, text: str) -> list[dict[str, Any]]:
        if "rules:" not in text:
            return []
        items: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                if current:
                    items.append(current)
                current = {}
                stripped = stripped[2:].strip()
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    current[k.strip()] = v.strip().strip('"\'')
            elif current is not None and ":" in stripped:
                k, v = stripped.split(":", 1)
                current[k.strip()] = v.strip().strip('"\'')
        if current:
            items.append(current)
        return items

    def _rule_conflicts(self, parsed: list[dict[str, Any]], active_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conflicts = []
        for new in parsed:
            for active in active_rules:
                for old in active.get("parsed_rules") or []:
                    old_table = _normalize_identifier(old.get("table"))
                    new_table = _normalize_identifier(new.get("table"))
                    old_column = _normalize_identifier(old.get("column"))
                    new_column = _normalize_identifier(new.get("column"))
                    if old.get("type") == "operation_forbidden" and old.get("operation") == "CREATE_TABLE" and new.get("type") == "table_required" and old_table == new_table:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"Active rule forbids table {new.get('table')} but new rule requires it."})
                    if old.get("type") == "table_required" and new.get("type") == "operation_forbidden" and new.get("operation") == "CREATE_TABLE" and old_table == new_table:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"New rule forbids table {old.get('table')} required by active rule."})
                    if old.get("type") == "column_forbidden" and new.get("type") == "column_required" and old_table == new_table and old_column == new_column:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"Active rule forbids column {new.get('table')}.{new.get('column')} but new rule requires it."})
                    if old.get("type") == "column_required" and new.get("type") == "column_forbidden" and old_table == new_table and old_column == new_column:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"New rule forbids column {old.get('table')}.{old.get('column')} required by active rule."})
        return conflicts

    def _schema_conflicts(self, parsed: list[dict[str, Any]], schema_graph: dict[str, Any]) -> list[dict[str, Any]]:
        tables = _schema_tables(schema_graph)
        conflicts = []
        for item in parsed:
            if item.get("type") == "column_required":
                table = str(item.get("table") or "")
                column = str(item.get("column") or "")
                table_key = _normalize_identifier(table)
                column_key = _normalize_identifier(column)
                if table_key in tables and column_key not in tables[table_key]:
                    conflicts.append({"message": f"Schema table {table} is missing required column {column}.", "table": table, "column": column})
        return conflicts


def _schema_tables(graph: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for table in graph.get("tables") or []:
        if isinstance(table, dict):
            name = table.get("name") or table.get("table_name")
            cols = table.get("columns") or []
            out[_normalize_identifier(name)] = {_normalize_identifier(c.get("name") if isinstance(c, dict) else c) for c in cols}
    return out


def _create_table_columns(sql: str) -> set[str]:
    """Best-effort column extraction for simple CREATE TABLE statements.

    This intentionally normalizes quoted/unquoted identifiers case-insensitively so
    rules like "mỗi bảng phải có id" accept SQL using `ID`, `"ID"`, or `id`.
    """
    match = re.search(r"\bcreate\s+table\b[\s\S]*?\((?P<body>[\s\S]*)\)", sql, re.I)
    if not match:
        return set()
    body = match.group("body")
    columns: set[str] = set()
    for part in _split_sql_csv(body):
        stripped = part.strip()
        if not stripped:
            continue
        first = stripped.split(None, 1)[0].strip('`"[]')
        if first.lower() in {"constraint", "primary", "foreign", "unique", "check", "exclude"}:
            continue
        normalized = _normalize_identifier(first)
        if normalized:
            columns.add(normalized)
    return columns


def _split_sql_csv(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in value:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in {'"', "'", '`'}:
            quote = ch
            current.append(ch)
            continue
        if ch == '(':
            depth += 1
        elif ch == ')' and depth:
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append(''.join(current))
    return parts



def _normalize_rule_text(value: str) -> str:
    """Normalize Vietnamese/English rule text for lightweight deterministic parsing.

    It removes accents, normalizes đ/Đ, lowercases and collapses whitespace so
    user wording variants like xóa/xoá/xoa and huỷ/hủy/huy are treated alike.
    """
    raw = str(value or "")
    raw = raw.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", raw)
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_marks.lower()).strip()

def _normalize_identifier(value: Any) -> str:
    raw = str(value or "").strip().strip('`"[]')
    return raw.lower()


def _violation(rule: dict[str, Any], message: str) -> dict[str, Any]:
    return {"rule_id": rule.get("rule_id"), "severity": rule.get("severity", "block"), "message": message}


def _ident(value: Any) -> str:
    raw = str(value or "").strip()
    if not re.match(r"^[A-Za-z_][\w]*$", raw):
        raise ValueError("Unsafe identifier for additive schema draft")
    return raw


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
