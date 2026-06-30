from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import unicodedata
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

SUPPORTED_TYPES = {
    "operation_forbidden",
    "required_column_on_create_table",
    "required_primary_key_on_create_table",
    "column_required",
    "column_forbidden",
    "column_type_required",
    "table_required",
    "table_forbidden",
    "naming_convention",
    "row_mutation_guard",
    # V1 compatibility names accepted at boundaries.
    "schema_assertion",
}
DESTRUCTIVE_FIX_WORDS = {"drop", "delete", "truncate", "remove"}

SEMANTIC_ALIASES = {
    "identifier": {"id", "identifier", "dinh danh", "định danh", "ma_dinh_danh", "ma dinh danh", "mã định danh", "khoa dinh danh", "khóa định danh", "khoa dinh_danh"},
    "primary_key": {"primary key", "khoa chinh", "khóa chính", "pk"},
    "email": {"email", "mail", "email_address", "dia chi email", "địa chỉ email"},
    "created_timestamp": {"created_at", "created_date", "ngay tao", "ngày tạo"},
    "updated_timestamp": {"updated_at", "updated_date", "ngay cap nhat", "ngày cập nhật"},
}

TYPE_ALIASES = {
    "float": "float",
    "real": "real",
    "double": "double precision",
    "double precision": "double precision",
    "bigint": "bigint",
    "int8": "bigint",
    "integer": "integer",
    "int": "integer",
    "int4": "integer",
    "text": "text",
    "string": "text",
    "varchar": "varchar",
    "uuid": "uuid",
    "boolean": "boolean",
    "bool": "boolean",
    "timestamp": "timestamp",
    "timestamptz": "timestamptz",
    "date": "date",
    "numeric": "numeric",
    "decimal": "numeric",
}


@dataclass(frozen=True)
class NormalizedRuleText:
    original: str
    text: str
    tokens: list[str]


@dataclass(frozen=True)
class RuleIntent:
    scope: str
    modality: str
    object: str
    target: dict[str, Any] = field(default_factory=dict)
    severity: str = "block"
    confidence: float = 1.0


class LanguageNormalizer:
    def normalize_text(self, value: str) -> NormalizedRuleText:
        original = str(value or "")
        text = self._strip_accents(original)
        text = text.lower()
        text = text.replace("đ", "d")
        text = re.sub(r"[`\"\[\]{}()]+", " ", text)
        text = re.sub(r"[^a-z0-9_\.]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        tokens = text.split() if text else []
        return NormalizedRuleText(original=original, text=text, tokens=tokens)

    def normalize_identifier(self, value: Any) -> str:
        raw = str(value or "").strip().strip('`"[]')
        raw = self._strip_accents(raw).replace("đ", "d").replace("Đ", "D")
        return raw.lower()

    @staticmethod
    def _strip_accents(value: str) -> str:
        value = value.replace("đ", "d").replace("Đ", "D")
        decomposed = unicodedata.normalize("NFD", value)
        return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


class SemanticAliasRegistry:
    def __init__(self, aliases: dict[str, set[str]] | None = None):
        self.normalizer = LanguageNormalizer()
        raw = aliases or SEMANTIC_ALIASES
        self.aliases = {
            key: {self.normalizer.normalize_text(alias).text.replace(" ", "_") for alias in values}
            | {self.normalizer.normalize_text(alias).text for alias in values}
            for key, values in raw.items()
        }

    def canonical_column(self, value: Any) -> str:
        normalized = self.normalizer.normalize_identifier(value)
        spaced = self.normalizer.normalize_text(str(value or "").replace("_", " ")).text
        for canonical, aliases in self.aliases.items():
            if normalized in aliases or spaced in aliases:
                if canonical == "identifier":
                    return "identifier"
                if canonical == "email":
                    return "email"
                return canonical
        return normalized

    def canonical_data_type(self, value: Any) -> str:
        raw = self.normalizer.normalize_text(str(value or "")).text.replace("_", " ")
        for alias in sorted(TYPE_ALIASES, key=len, reverse=True):
            if raw == alias or raw.startswith(alias + " "):
                return TYPE_ALIASES[alias]
        return raw.split()[0] if raw else ""

    def is_identifier_alias(self, value: Any) -> bool:
        return self.canonical_column(value) == "identifier"

    def is_primary_key_alias_phrase(self, text: str) -> bool:
        norm = self.normalizer.normalize_text(text).text
        return any(alias in norm for alias in self.aliases["primary_key"])


class SemanticIntentParser:
    TABLE_QUANTIFIER_STOPWORDS = {
        "moi", "tat", "ca", "bat", "ky", "nao", "cung", "deu", "moi", "duoc", "tao",
        "new", "every", "all", "any", "table", "bang", "cac",
    }

    def __init__(self, aliases: SemanticAliasRegistry):
        self.aliases = aliases
        self.normalizer = aliases.normalizer

    def parse(self, raw_text: str) -> tuple[list[RuleIntent], list[str]]:
        norm = self.normalizer.normalize_text(raw_text)
        text = norm.text
        if not text:
            return [], ["AMBIGUOUS_RULE: empty rule"]

        intents: list[RuleIntent] = []

        type_constraint = self._column_type_constraint(text)
        if type_constraint:
            column, data_type = type_constraint
            intents.append(RuleIntent("all_tables", "required", "column_type", {"column": column, "column_semantic": self.aliases.canonical_column(column), "data_type": data_type}))
            return self._dedupe(intents), []

        if self._mutation_guard(text):
            intents.append(RuleIntent("rows", "forbidden", "row_mutation", {"guard": self._mutation_guard(text)}))
        if self._naming_convention(text):
            intents.append(RuleIntent("schema", "required", "naming_convention", self._naming_convention(text) or {}))
        if self._is_forbidden(text) and self._mentions_drop_table(text):
            intents.append(RuleIntent("any", "forbidden", "operation", {"operation": "DROP_TABLE"}))
        if self._is_forbidden(text) and self._mentions_truncate_table(text):
            intents.append(RuleIntent("any", "forbidden", "operation", {"operation": "TRUNCATE_TABLE"}))
        if self._all_or_new_tables(text) and self.aliases.is_primary_key_alias_phrase(text):
            intents.append(RuleIntent("new_tables", "required", "primary_key", {}))
        identifier = self._required_identifier_for_all_tables(text)
        if identifier:
            intents.append(RuleIntent("new_tables", "required", "column", {"column_semantic": "identifier", "accepted_columns": sorted(self.aliases.aliases["identifier"])}))
        all_table_column = self._required_semantic_column_for_all_tables(text)
        if all_table_column and all_table_column != "identifier":
            intents.append(RuleIntent("new_tables", "required", "column", {"column_semantic": all_table_column}))

        table_required = self._required_table(text)
        if table_required:
            intents.append(RuleIntent("database", "required", "table", {"table": table_required}))

        specific_column = self._specific_column_required(text)
        if specific_column:
            table, column = specific_column
            intents.append(RuleIntent("specific_table", "required", "column", {"table": table, "column": column, "column_semantic": self.aliases.canonical_column(column)}))

        forbidden_column = self._specific_column_forbidden(text)
        if forbidden_column:
            table, column = forbidden_column
            intents.append(RuleIntent("specific_table", "forbidden", "column", {"table": table, "column": column, "column_semantic": self.aliases.canonical_column(column)}))

        create_forbidden = self._forbid_create_table(text)
        if create_forbidden:
            intents.append(RuleIntent("database", "forbidden", "operation", {"operation": "CREATE_TABLE", "table": create_forbidden}))

        if intents:
            return self._dedupe(intents), []
        return [], ["AMBIGUOUS_RULE: rule intent is not deterministic"]

    @staticmethod
    def _is_forbidden(text: str) -> bool:
        return any(phrase in text for phrase in ("khong duoc", "khong cho", "cam", "forbid", "do not allow", "not allow"))

    @staticmethod
    def _is_required(text: str) -> bool:
        return any(phrase in text for phrase in ("phai co", "bat buoc co", "bat buoc phai co", "can co", "phai chua", "bat buoc chua", "must have", "required", "requires"))

    @staticmethod
    def _all_or_new_tables(text: str) -> bool:
        return any(phrase in text for phrase in (
            "moi bang", "moi table", "moi bang deu", "moi bang moi",
            "tat ca bang", "tat ca bang moi", "bang nao cung", "bat ky bang", "bat ky bang nao",
            "cac bang", "every table", "all table", "new table", "bang moi", "khi tao bang", "duoc tao",
        ))

    @staticmethod
    def _mentions_drop_table(text: str) -> bool:
        return ("drop table" in text or "drop bang" in text or (("xoa bang" in text or "huy bang" in text or "pha bang" in text) and "sach" not in text))

    @staticmethod
    def _mentions_truncate_table(text: str) -> bool:
        return "truncate" in text or "lam rong bang" in text or "xoa sach bang" in text or "xoa sach du lieu bang" in text or "don sach bang" in text or "clear table" in text

    def _column_type_constraint(self, text: str) -> tuple[str, str] | None:
        patterns = [
            r"^(?:cot\s+|truong\s+)?(id|identifier|ma\s+dinh\s+danh|khoa\s+dinh\s+danh|[a-z_][\w]*)\s+(?:phai\s+co|can\s+co|bat\s+buoc\s+co|phai\s+dung|can\s+dung|bat\s+buoc\s+dung)?\s*(?:kieu\s+(?:du\s+lieu\s+)?(?:la|=)?|type\s*(?:is|=)?|data\s+type\s*(?:is|=)?)\s+([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})",
            r"^(id|identifier|ma\s+dinh\s+danh|khoa\s+dinh\s+danh)\s+(?:la|=|is|should\s+be|must\s+be)\s+([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})$",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                column = self.aliases.canonical_column(m.group(1))
                if column == "identifier":
                    column = "id"
                data_type = self.aliases.canonical_data_type(m.group(2))
                if column and data_type:
                    return column, data_type
        return None

    def _required_identifier_for_all_tables(self, text: str) -> bool:
        if not self._all_or_new_tables(text) or not self._is_required(text):
            return False
        return any(alias.replace("_", " ") in text or alias in text for alias in self.aliases.aliases["identifier"])

    def _required_semantic_column_for_all_tables(self, text: str) -> str | None:
        if not self._all_or_new_tables(text) or not self._is_required(text):
            return None
        for semantic in ("identifier", "created_timestamp", "updated_timestamp", "email"):
            if any(alias.replace("_", " ") in text or alias in text for alias in self.aliases.aliases[semantic]):
                return semantic
        return None

    def _required_table(self, text: str) -> str | None:
        patterns = [
            r"(?:database|csdl|he thong)?\s*(?:bat buoc phai co|bat buoc co|phai co|can co|must have|requires?)\s+bang\s+([a-z_][\w]*)",
            r"(?:bat buoc ton tai|phai ton tai)\s+bang\s+([a-z_][\w]*)",
            r"bang\s+([a-z_][\w]*)\s+trong\s+database",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return self.normalizer.normalize_identifier(m.group(1))
        return None

    def _specific_column_required(self, text: str) -> tuple[str, str] | None:
        if not self._is_required(text) or self._all_or_new_tables(text):
            return None
        patterns = [
            r"(?:trong\s+)?bang\s+([a-z_][\w]*)\s+(?:bat buoc phai co|bat buoc co|phai co|can co|phai chua|must have|requires?)\s+(?:cot\s+|truong\s+)?([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})",
            r"([a-z_][\w]*)\s+(?:bat buoc phai co|bat buoc co|phai co|can co|phai chua|must have|requires?)\s+(?:cot\s+|truong\s+)?([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m and m.group(1) not in {"database", "csdl", "he", "thong"}:
                return self.normalizer.normalize_identifier(m.group(1)), self.aliases.canonical_column(m.group(2).strip())
        return None

    def _specific_column_forbidden(self, text: str) -> tuple[str, str] | None:
        if not self._is_forbidden(text):
            return None
        m = re.search(r"(?:bang\s+)?([a-z_][\w]*)\s+(?:khong duoc|khong cho|cam)\s+(?:co|chua|luu)\s+(?:cot\s+)?([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})", text)
        if m:
            return self.normalizer.normalize_identifier(m.group(1)), self.aliases.canonical_column(m.group(2))
        return None

    def _forbid_create_table(self, text: str) -> str | None:
        if not self._is_forbidden(text):
            return None
        m = re.search(r"(?:tao|create)\s+(?:bang|table)\s+([a-z_][\w]*)", text)
        return self.normalizer.normalize_identifier(m.group(1)) if m else None

    def _naming_convention(self, text: str) -> dict[str, Any] | None:
        if "ten bang" not in text and "ten cot" not in text:
            return None
        target = "table" if "ten bang" in text else "column"
        if "snake_case" in text:
            return {"target": target, "convention": "snake_case"}
        if "chu hoa" in text:
            return {"target": target, "forbid": "uppercase"}
        if "khoang trang" in text:
            return {"target": target, "forbid": "whitespace"}
        if "ky tu dac biet" in text:
            return {"target": target, "forbid": "special_characters"}
        return None

    def _mutation_guard(self, text: str) -> str | None:
        if "update" in text and ("khong co where" in text or "toan bo" in text or "toan bang" in text):
            return "UPDATE_REQUIRES_WHERE"
        if "delete" in text and ("khong co where" in text or "toan bo" in text):
            return "DELETE_REQUIRES_WHERE"
        if "xoa du lieu" in text and "khong co dieu kien" in text:
            return "DELETE_REQUIRES_WHERE"
        if "cap nhat" in text and ("toan bang" in text or "toan bo" in text):
            return "UPDATE_REQUIRES_WHERE"
        return None

    @staticmethod
    def _dedupe(intents: list[RuleIntent]) -> list[RuleIntent]:
        seen: set[tuple[str, str, str, tuple[tuple[str, str], ...]]] = set()
        out: list[RuleIntent] = []
        for intent in intents:
            key = (intent.scope, intent.modality, intent.object, tuple(sorted((k, str(v)) for k, v in intent.target.items())))
            if key not in seen:
                seen.add(key)
                out.append(intent)
        return out


class RuleDSLCompiler:
    def compile(self, intents: list[RuleIntent]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for intent in intents:
            if intent.object == "operation" and intent.modality == "forbidden":
                op = intent.target["operation"]
                rule = {"id": f"forbid_{op.lower()}", "type": "operation_forbidden", "severity": intent.severity, "operation": op}
                if intent.target.get("table"):
                    rule["table"] = intent.target["table"]
                rules.append(rule)
                if rule.get("operation") == "TRUNCATE_TABLE":
                    legacy = {**rule, "id": "forbid_truncate", "operation": "TRUNCATE", "operation_canonical": "TRUNCATE_TABLE"}
                    rules.append(legacy)
            elif intent.object == "column" and intent.scope == "new_tables" and intent.modality == "required":
                semantic = intent.target.get("column_semantic", "column")
                column_name = "id" if semantic == "identifier" else semantic
                rules.append({"id": f"require_{semantic}_on_create_table", "type": "required_column_on_create_table", "scope": "all_new_tables", "severity": intent.severity, "assertion": "every_new_table_must_have_column", "column": column_name, **intent.target})
            elif intent.object == "primary_key" and intent.modality == "required":
                rules.append({"id": "require_primary_key_on_create_table", "type": "required_primary_key_on_create_table", "severity": intent.severity, "assertion": "every_new_table_must_have_primary_key"})
            elif intent.object == "column_type" and intent.modality == "required":
                column = intent.target.get("column") or ""
                semantic = intent.target.get("column_semantic") or column
                data_type = intent.target.get("data_type") or ""
                rules.append({"id": f"require_{column}_type_{data_type}".replace(" ", "_"), "type": "column_type_required", "scope": intent.scope, "severity": intent.severity, "column": column, "column_semantic": semantic, "data_type": data_type})
            elif intent.object == "table" and intent.modality == "required":
                table = intent.target["table"]
                rules.append({"id": f"require_table_{table}", "type": "table_required", "severity": intent.severity, "table": table})
            elif intent.object == "column" and intent.scope == "specific_table" and intent.modality == "required":
                table = intent.target["table"]
                col = intent.target["column_semantic"] or intent.target["column"]
                rules.append({"id": f"require_{table}_{col}", "type": "column_required", "severity": intent.severity, **intent.target})
            elif intent.object == "column" and intent.scope == "specific_table" and intent.modality == "forbidden":
                table = intent.target["table"]
                col = intent.target["column_semantic"] or intent.target["column"]
                rules.append({"id": f"forbid_{table}_{col}", "type": "column_forbidden", "severity": intent.severity, **intent.target})
            elif intent.object == "naming_convention":
                target = intent.target.get("target", "identifier")
                rules.append({"id": f"naming_{target}", "type": "naming_convention", "severity": "warn", "not_enforced": True, **intent.target})
            elif intent.object == "row_mutation":
                guard = intent.target.get("guard", "ROW_MUTATION_REQUIRES_WHERE")
                rules.append({"id": f"row_guard_{guard.lower()}", "type": "row_mutation_guard", "severity": intent.severity, "guard": guard})
        return rules


@dataclass(frozen=True)
class CreateTableStatement:
    table: str
    columns: set[str]
    semantic_columns: set[str]
    table_constraints: list[str]
    column_types: dict[str, str] = field(default_factory=dict)
    semantic_column_types: dict[str, str] = field(default_factory=dict)
    parse_error: str | None = None


class SQLStructuralChecker:
    def __init__(self, aliases: SemanticAliasRegistry):
        self.aliases = aliases
        self.normalizer = aliases.normalizer

    def parse_create_table(self, sql: str) -> CreateTableStatement | None:
        sql = str(sql or "")
        m = re.search(r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?(?P<name>(?:[`\"\[]?[A-Za-z_][\w]*[`\"\]]?\.)?[`\"\[]?[A-Za-z_][\w]*[`\"\]]?)\s*\(", sql, re.I)
        if not m:
            return None
        table = self.normalizer.normalize_identifier(m.group("name").split(".")[-1])
        open_index = sql.find("(", m.end() - 1)
        close_index = self._matching_paren(sql, open_index)
        if close_index is None:
            return CreateTableStatement(table, set(), set(), [], {}, {}, "CREATE_TABLE_PARSE_ERROR")
        body = sql[open_index + 1:close_index]
        parts = self._split_top_level_csv(body)
        columns: set[str] = set()
        semantic_columns: set[str] = set()
        constraints: list[str] = []
        column_types: dict[str, str] = {}
        semantic_column_types: dict[str, str] = {}
        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue
            first = self._first_identifier(stripped)
            if not first:
                return CreateTableStatement(table, columns, semantic_columns, constraints, column_types, semantic_column_types, "CREATE_TABLE_PARSE_ERROR")
            if first in {"constraint", "primary", "foreign", "unique", "check", "exclude"}:
                constraints.append(stripped)
                continue
            col = self.normalizer.normalize_identifier(first)
            columns.add(col)
            semantic = self.aliases.canonical_column(col)
            semantic_columns.add(semantic)
            dtype = self._column_type(stripped)
            if dtype:
                column_types[col] = dtype
                semantic_column_types[semantic] = dtype
            if re.search(r"\bprimary\s+key\b", stripped, re.I):
                constraints.append("PRIMARY KEY")
        return CreateTableStatement(table, columns, semantic_columns, constraints, column_types, semantic_column_types)

    @staticmethod
    def _matching_paren(sql: str, open_index: int) -> int | None:
        depth = 0
        quote: str | None = None
        bracket = False
        i = open_index
        while i < len(sql):
            ch = sql[i]
            if bracket:
                if ch == "]":
                    bracket = False
                i += 1
                continue
            if quote:
                if ch == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        i += 2
                        continue
                    quote = None
                i += 1
                continue
            if ch == "[":
                bracket = True
            elif ch in {"'", '"', '`'}:
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None

    def _column_type(self, column_def: str) -> str:
        parts = column_def.strip().split()
        if len(parts) < 2:
            return ""
        # Skip first token (column name). Type may include spaces, e.g. double precision.
        rest = " ".join(parts[1:])
        m = re.match(r"([A-Za-z_][\w]*(?:\s+[A-Za-z_][\w]*)?)", rest)
        return self.aliases.canonical_data_type(m.group(1) if m else "")

    def column_type(self, sql: str, semantic: str, column: str) -> str | None:
        parsed = self.parse_create_table(sql)
        if not parsed or parsed.parse_error:
            return None
        if column and column in parsed.column_types:
            return parsed.column_types[column]
        if semantic and semantic in parsed.semantic_column_types:
            return parsed.semantic_column_types[semantic]
        return None

    def _split_top_level_csv(self, value: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        quote: str | None = None
        bracket = False
        for ch in value:
            if bracket:
                current.append(ch)
                if ch == "]":
                    bracket = False
                continue
            if quote:
                current.append(ch)
                if ch == quote:
                    quote = None
                continue
            if ch == "[":
                bracket = True
                current.append(ch)
                continue
            if ch in {'"', "'", '`'}:
                quote = ch
                current.append(ch)
                continue
            if ch == "(":
                depth += 1
            elif ch == ")" and depth:
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current))
        return parts

    def _first_identifier(self, value: str) -> str:
        stripped = value.strip()
        if stripped.startswith("["):
            end = stripped.find("]")
            return stripped[1:end] if end > 0 else ""
        if stripped.startswith(('"', '`')):
            quote = stripped[0]
            end = stripped.find(quote, 1)
            return stripped[1:end] if end > 0 else ""
        m = re.match(r"([A-Za-z_][\w]*)", stripped)
        return m.group(1) if m else ""


class SandboxRuleEngine:
    def __init__(self, aliases: SemanticAliasRegistry | None = None):
        self.aliases = aliases or SemanticAliasRegistry()
        self.normalizer = self.aliases.normalizer
        self.intent_parser = SemanticIntentParser(self.aliases)
        self.compiler = RuleDSLCompiler()
        self.sql_checker = SQLStructuralChecker(self.aliases)

    def parse_rules(self, raw_text: str) -> tuple[list[dict[str, Any]], list[str]]:
        text = raw_text or ""
        structured, structured_warnings = self._parse_structured(text)
        if structured or structured_warnings:
            return structured, structured_warnings
        intents, warnings = self.intent_parser.parse(text)
        if warnings:
            return [], warnings
        return self.compiler.compile(intents), []

    def validate_rule(self, rule: dict[str, Any], active_rules: list[dict[str, Any]] | None = None, schema_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        parsed, warnings = self.parse_rules(rule.get("raw_text") or "")
        conflicts = self._rule_conflicts(parsed, active_rules or [])
        schema_conflicts = self._schema_conflicts(parsed, schema_graph or {})
        status = "draft"
        options: list[str] = []
        if warnings or not parsed:
            status = "warning_only"
        elif conflicts:
            status = "conflict_rule"
            options = ["Edit new rule", "Edit active rule", "Disable active rule", "Replace active rule", "Keep new rule as draft", "Cancel"]
        elif schema_conflicts:
            status = "pending_user_decision"
            options = ["Edit rule to match schema", "Generate additive schema draft", "Activate future-only", "Save as warning", "Keep draft", "Cancel"]
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
        updated = {**rule, "parsed_rules": report["parsed_rules"], "validated_at": _now(), "status": report["status"]}
        if report["status"] == "draft":
            updated["status"] = "active"
            updated["activated_at"] = _now()
            report["status"] = "active"
        return updated, report

    def check_sql(self, sql: str, active_rules: list[dict[str, Any]]) -> dict[str, Any]:
        violations: list[dict[str, Any]] = []
        normalized = str(sql or "").lower()
        create_table = self.sql_checker.parse_create_table(sql)
        for rule in active_rules:
            if rule.get("status") != "active":
                continue
            for parsed in rule.get("parsed_rules") or []:
                typ = self._canonical_type(parsed)
                op = str(parsed.get("operation") or "").upper()
                if typ == "operation_forbidden" and op == "DROP_TABLE" and re.search(r"\bdrop\s+table\b", normalized):
                    violations.append(_violation(rule, "DROP TABLE is forbidden by active sandbox rule."))
                elif typ == "operation_forbidden" and op in {"TRUNCATE", "TRUNCATE_TABLE"} and re.search(r"\btruncate\b", normalized):
                    violations.append(_violation(rule, "TRUNCATE TABLE is forbidden by active sandbox rule."))
                elif typ == "operation_forbidden" and op == "CREATE_TABLE" and create_table:
                    target = self.normalizer.normalize_identifier(parsed.get("table"))
                    if create_table.parse_error:
                        violations.append(_violation(rule, "CREATE TABLE could not be parsed safely."))
                    elif not target or target == create_table.table:
                        violations.append(_violation(rule, f"CREATE TABLE {parsed.get('table') or ''} is forbidden by active sandbox rule."))
                elif typ == "required_primary_key_on_create_table" and create_table:
                    if create_table.parse_error:
                        violations.append(_violation(rule, "CREATE TABLE could not be parsed safely."))
                    elif not any(re.search(r"\bprimary\s+key\b", c, re.I) for c in create_table.table_constraints):
                        violations.append(_violation(rule, "CREATE TABLE must include a primary key by active sandbox rule."))
                elif typ == "required_column_on_create_table" and create_table:
                    semantic = parsed.get("column_semantic") or self.aliases.canonical_column(parsed.get("column"))
                    if create_table.parse_error:
                        violations.append(_violation(rule, "CREATE TABLE could not be parsed safely."))
                    elif semantic and semantic not in create_table.semantic_columns and self.normalizer.normalize_identifier(parsed.get("column")) not in create_table.columns:
                        violations.append(_violation(rule, f"CREATE TABLE must include semantic column {semantic} by active sandbox rule."))
                elif typ == "column_type_required" and create_table:
                    semantic = parsed.get("column_semantic") or self.aliases.canonical_column(parsed.get("column"))
                    column = self.normalizer.normalize_identifier(parsed.get("column"))
                    required_type = self.aliases.canonical_data_type(parsed.get("data_type"))
                    if create_table.parse_error:
                        violations.append(_violation(rule, "CREATE TABLE could not be parsed safely."))
                    else:
                        found_type = self.sql_checker.column_type(sql, semantic, column)
                        if found_type is None:
                            violations.append(_violation(rule, f"CREATE TABLE must include column {column or semantic} by active sandbox rule."))
                        elif required_type and self.aliases.canonical_data_type(found_type) != required_type:
                            violations.append(_violation(rule, f"Column {column or semantic} must use type {required_type} by active sandbox rule."))
                elif typ == "column_required" and create_table:
                    table = self.normalizer.normalize_identifier(parsed.get("table"))
                    semantic = parsed.get("column_semantic") or self.aliases.canonical_column(parsed.get("column"))
                    if create_table.parse_error:
                        violations.append(_violation(rule, "CREATE TABLE could not be parsed safely."))
                    elif (not table or table == create_table.table) and semantic not in create_table.semantic_columns and self.normalizer.normalize_identifier(parsed.get("column")) not in create_table.columns:
                        violations.append(_violation(rule, f"CREATE TABLE must include column {semantic} by active sandbox rule."))
                elif typ == "column_forbidden" and create_table:
                    table = self.normalizer.normalize_identifier(parsed.get("table"))
                    semantic = parsed.get("column_semantic") or self.aliases.canonical_column(parsed.get("column"))
                    if create_table.parse_error:
                        violations.append(_violation(rule, "CREATE TABLE could not be parsed safely."))
                    elif (not table or table == create_table.table) and (semantic in create_table.semantic_columns or self.normalizer.normalize_identifier(parsed.get("column")) in create_table.columns):
                        violations.append(_violation(rule, f"Column {parsed.get('column') or semantic} is forbidden by active sandbox rule."))
        return {"status": "failed" if violations else "passed", "violations": violations}

    def generate_additive_schema_draft(self, rule: dict[str, Any]) -> dict[str, Any]:
        parsed, warnings = self.parse_rules(rule.get("raw_text") or "")
        if warnings:
            return {"success": False, "code": "AMBIGUOUS_RULE", "sql": ""}
        statements = []
        for item in parsed:
            typ = self._canonical_type(item)
            if typ == "column_required":
                table = _ident(item.get("table"))
                column = _ident(item.get("column_semantic") if item.get("column_semantic") not in {None, "identifier"} else item.get("column") or item.get("column_semantic"))
                statements.append(f"ALTER TABLE {table} ADD COLUMN {column} text;")
            elif typ == "table_required":
                table = _ident(item.get("table"))
                statements.append(f"CREATE TABLE {table} (id bigint PRIMARY KEY);")
        sql = "\n".join(statements)
        if any(word in sql.lower() for word in DESTRUCTIVE_FIX_WORDS):
            return {"success": False, "code": "DESTRUCTIVE_SCHEMA_FIX_FORBIDDEN", "sql": ""}
        return {"success": bool(sql), "sql": sql, "draft_only": True}

    def _parse_structured(self, text: str) -> tuple[list[dict[str, Any]], list[str]]:
        if "rules:" not in text:
            return [], []
        if yaml is None:
            return [], ["Structured rule parsing requires PyYAML."]
        try:
            loaded = yaml.safe_load(text)
        except Exception as exc:
            return [], [f"Invalid structured rule YAML: {exc}"]
        if not isinstance(loaded, dict) or not isinstance(loaded.get("rules"), list):
            return [], ["Structured rule YAML must contain a rules list."]
        items: list[dict[str, Any]] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()
        for index, raw in enumerate(loaded.get("rules") or [], start=1):
            if not isinstance(raw, dict):
                warnings.append(f"Rule {index} must be an object.")
                continue
            item = dict(raw)
            rule_id = str(item.get("id") or "").strip()
            typ = str(item.get("type") or "").strip()
            severity = str(item.get("severity") or "").strip()
            if not rule_id:
                warnings.append(f"Rule {index} missing required id.")
            elif rule_id in seen_ids:
                warnings.append(f"Duplicate rule id: {rule_id}")
            else:
                seen_ids.add(rule_id)
            if not typ:
                warnings.append(f"Rule {rule_id or index} missing required type.")
            elif typ not in SUPPORTED_TYPES:
                warnings.append(f"Unsupported rule type: {typ}")
            if not severity:
                warnings.append(f"Rule {rule_id or index} missing required severity.")
            elif severity not in {"block", "warn", "warning"}:
                warnings.append(f"Rule {rule_id or index} has unsupported severity: {severity}")
            item["id"] = rule_id
            item["type"] = typ
            item["severity"] = "warn" if severity == "warning" else severity
            if typ == "schema_assertion" and item.get("assertion") == "every_new_table_must_have_primary_key":
                item["type"] = "required_primary_key_on_create_table"
            if typ == "schema_assertion" and item.get("assertion") == "every_new_table_must_have_column":
                item["type"] = "required_column_on_create_table"
                if item.get("column"):
                    item["column_semantic"] = self.aliases.canonical_column(item.get("column"))
            if item.get("column") and not item.get("column_semantic"):
                item["column_semantic"] = self.aliases.canonical_column(item.get("column"))
            items.append(item)
        if warnings:
            return [], warnings
        return items, []

    def _rule_conflicts(self, parsed: list[dict[str, Any]], active_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conflicts = []
        for new in parsed:
            for active in active_rules:
                for old in active.get("parsed_rules") or []:
                    old_table = self.normalizer.normalize_identifier(old.get("table"))
                    new_table = self.normalizer.normalize_identifier(new.get("table"))
                    old_col = old.get("column_semantic") or self.aliases.canonical_column(old.get("column"))
                    new_col = new.get("column_semantic") or self.aliases.canonical_column(new.get("column"))
                    old_type = self._canonical_type(old)
                    new_type = self._canonical_type(new)
                    if old_type == "operation_forbidden" and old.get("operation") == "CREATE_TABLE" and new_type == "table_required" and old_table == new_table:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"Active rule forbids creating table {new.get('table')} but new rule requires it."})
                    if old_type == "table_required" and new_type == "operation_forbidden" and new.get("operation") == "CREATE_TABLE" and old_table == new_table:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"New rule forbids creating table {old.get('table')} required by active rule."})
                    if old_type == "table_forbidden" and new_type == "table_required" and old_table == new_table:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"Active rule forbids table {new.get('table')} but new rule requires it."})
                    if old_type == "column_forbidden" and new_type == "column_required" and old_table == new_table and old_col == new_col:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"Active rule forbids column {new.get('table')}.{new_col} but new rule requires it."})
                    if old_type == "column_required" and new_type == "column_forbidden" and old_table == new_table and old_col == new_col:
                        conflicts.append({"active_rule_id": active.get("rule_id"), "message": f"New rule forbids column {old.get('table')}.{old_col} required by active rule."})
        return conflicts

    def _schema_conflicts(self, parsed: list[dict[str, Any]], schema_graph: dict[str, Any]) -> list[dict[str, Any]]:
        tables = _schema_tables(schema_graph, self.normalizer, self.aliases)
        conflicts = []
        for item in parsed:
            if self._canonical_type(item) == "column_required":
                table = self.normalizer.normalize_identifier(item.get("table"))
                column = item.get("column_semantic") or self.aliases.canonical_column(item.get("column"))
                if table in tables and column not in tables[table]:
                    conflicts.append({"message": f"Schema table {table} is missing required column {column}.", "table": table, "column": column})
        return conflicts

    @staticmethod
    def _canonical_type(rule: dict[str, Any]) -> str:
        typ = rule.get("type")
        if typ == "schema_assertion" and rule.get("assertion") == "every_new_table_must_have_primary_key":
            return "required_primary_key_on_create_table"
        if typ == "schema_assertion" and rule.get("assertion") == "every_new_table_must_have_column":
            return "required_column_on_create_table"
        return str(typ or "")


def _schema_tables(graph: dict[str, Any], normalizer: LanguageNormalizer, aliases: SemanticAliasRegistry) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for table in graph.get("tables") or []:
        if isinstance(table, dict):
            name = table.get("name") or table.get("table_name")
            cols = table.get("columns") or []
            values = set()
            for c in cols:
                raw = c.get("name") if isinstance(c, dict) else c
                values.add(normalizer.normalize_identifier(raw))
                values.add(aliases.canonical_column(raw))
            out[normalizer.normalize_identifier(name)] = values
    return out


def _violation(rule: dict[str, Any], message: str) -> dict[str, Any]:
    return {"rule_id": rule.get("rule_id"), "severity": rule.get("severity", "block"), "message": message}


def _ident(value: Any) -> str:
    raw = str(value or "").strip()
    if not re.match(r"^[A-Za-z_][\w]*$", raw):
        raise ValueError("Unsafe identifier for additive schema draft")
    return raw


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
