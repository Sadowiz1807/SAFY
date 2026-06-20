from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re
import unicodedata

from Core.agent_state import AgentWorkflowState


@dataclass
class WorkflowDecision:
    handled: bool
    action: str = ""
    answer: str = ""
    sql: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class WorkflowEngine:
    """Deterministic slot-filling workflow layer for high-value DB tasks."""

    _create_table_patterns = [
        r"\bcreate\s+table\b",
        r"\bnew\s+table\b",
        r"\btạo\s+(?:1\s+)?bảng\b",
        r"\btao\s+(?:1\s+)?bang\b",
    ]

    _check_patterns = [
        r"\bcheck\s+safety\b",
        r"\bsafety\s+check\b",
        r"\bkiểm\s+tra\s+an\s+toàn\b",
        r"\bkiem\s+tra\s+an\s+toan\b",
        r"\bkiểm\s+tra\s+sql\b",
        r"\bkiem\s+tra\s+sql\b",
    ]

    _execute_patterns = [
        r"^\s*execute\s*$",
        r"^\s*/execute\s*$",
        r"\bexecute\s+checked\b",
        r"\bchạy\s+thật\b",
        r"\bchay\s+that\b",
        r"\bthực\s+thi\b",
        r"\bthuc\s+thi\b",
    ]

    _read_query_patterns = [
        r"\bselect\b[\s\S]+\bfrom\b",
        r"\bshow\s+(?:ra\s+)?(?:.*?)(?:data|rows|records|dữ\s+liệu|du\s+lieu)\b",
        r"\bdisplay\s+(?:data|rows|records)\b",
        r"\blist\s+(?:data|rows|records)\b",
        r"\bhiển\s+thị\b",
        r"\bhien\s+thi\b",
        r"\bxem\s+(?:tất\s+cả\s+)?(?:dữ\s+liệu|du\s+lieu|bảng|bang)\b",
        r"\blấy\s+(?:tất\s+cả\s+)?(?:dữ\s+liệu|du\s+lieu|.*(?:row|hàng|hang))\b",
        r"\blay\s+(?:du\s+lieu|.*(?:row|hang))\b",
    ]

    _insert_row_patterns = [
        r"\binsert\s+into\b",
        r"\bnhập\s+dữ\s+liệu\b",
        r"\bnhap\s+du\s+lieu\b",
        r"\bthêm\s+dữ\s+liệu\b",
        r"\bthem\s+du\s+lieu\b",
        r"\bthêm\s+(?:1\s+)?(?:dòng|hang|hàng|row)\b",
        r"\badd\s+(?:a\s+)?row\b",
    ]

    def decide(self, message: str, state: AgentWorkflowState) -> WorkflowDecision:
        text = (message or "").strip()
        if not text:
            return WorkflowDecision(False)
        lower = text.lower()

        if state.pending_action == "create_table":
            return self._continue_create_table(text, state)
        if self._matches(lower, self._create_table_patterns):
            return self._continue_create_table(text, state)
        if self._matches(lower, self._insert_row_patterns):
            return self._draft_insert_row(text, state)
        if self._matches(lower, self._read_query_patterns):
            return self._draft_read_query(text, state)
        if self._matches(lower, self._check_patterns):
            if state.last_sql:
                return WorkflowDecision(True, action="check_safety", answer="Running SQL Guard for the latest draft.")
            return WorkflowDecision(True, action="missing_last_sql", answer="Chưa có SQL draft để Check Safety. Hãy tạo hoặc dán SQL trước.")
        if self._matches(lower, self._execute_patterns):
            if state.last_check_id and state.last_sql_hash:
                return WorkflowDecision(True, action="execute_checked", answer="Executing the last checked SQL through SAFY runtime.")
            if state.last_sql:
                return WorkflowDecision(True, action="missing_check", answer="SQL draft đã có, nhưng chưa có Check Safety hợp lệ. Hãy chạy Check Safety trước khi Execute.")
        return WorkflowDecision(False)

    def _draft_read_query(self, message: str, state: AgentWorkflowState) -> WorkflowDecision:
        table = self._extract_table_name(message) or state.last_table_name
        if not table:
            return WorkflowDecision(True, action="ask_slots", answer="Bạn muốn hiển thị dữ liệu từ bảng nào?")
        limit = self._extract_limit(message, default=100)
        sql = f"SELECT * FROM {self._sanitize_identifier(table)} LIMIT {limit};"
        state.remember_sql(sql, intent="read_query")
        return WorkflowDecision(True, action="direct_read", answer="Đang đọc dữ liệu an toàn từ database đã kết nối.", sql=sql, data={"table_name": table, "limit": limit})

    def _draft_insert_row(self, message: str, state: AgentWorkflowState) -> WorkflowDecision:
        table = self._extract_table_name(message) or state.last_table_name
        if not table:
            return WorkflowDecision(True, action="ask_slots", answer="Bạn muốn nhập dữ liệu vào bảng nào?")
        pairs = self._extract_value_pairs(message)
        if not pairs:
            return WorkflowDecision(True, action="ask_slots", answer=f"Bảng `{table}` cần dữ liệu theo dạng cột = giá trị. Ví dụ: id=1, name='An'.")
        columns = [self._resolve_column_name(name, state.last_table_columns) for name, _ in pairs]
        values = [self._sql_literal(value) for _, value in pairs]
        sql = f"INSERT INTO {self._sanitize_identifier(table)} (" + ", ".join(columns) + ") VALUES (" + ", ".join(values) + ");"
        state.remember_sql(sql, intent="insert_row")
        state.remember_table(table_name=table, columns=state.last_table_columns, summary=f"insert_row:{table}")
        return WorkflowDecision(
            True,
            action="draft_sql",
            answer="Đã dựng draft SQL nhập dữ liệu dựa trên bảng gần nhất trong session. Hãy chạy Check Safety trước khi Execute.",
            sql=sql,
            data={"table_name": table, "columns": columns, "next_step": "check_safety"},
        )

    def _extract_table_name(self, message: str) -> str | None:
        text = (message or "").strip()
        patterns = [
            r"\bfrom\s+([A-Za-z_][A-Za-z0-9_\.]*)",
            r"\binto\s+([A-Za-z_][A-Za-z0-9_\.]*)",
            r"\btable\s+([A-Za-z_][A-Za-z0-9_\.]*)",
            r"\bbảng\s+([A-Za-z_][A-Za-z0-9_\.]*)",
            r"\bbang\s+([A-Za-z_][A-Za-z0-9_\.]*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                candidate = self._sanitize_identifier(match.group(1).split(".")[-1])
                if candidate.lower() not in {"id", "ngay", "gio", "date", "time", "row", "data", "du", "dữ"}:
                    return candidate
        return None

    def _extract_limit(self, message: str, default: int = 100) -> int:
        lower = (message or "").lower()
        match = re.search(r"\b(?:limit|top|first|lấy|lay|show|hiển\s+thị|hien\s+thi)\s+(\d{1,4})\b", lower)
        if not match:
            return default
        return max(1, min(int(match.group(1)), 100))

    def _extract_value_pairs(self, message: str) -> list[tuple[str, str]]:
        text = (message or "").strip()
        pattern = re.compile(r"([A-Za-z_À-ỹ][A-Za-z0-9_À-ỹ]*)\s*(?:=|bằng|bang|là|la)\s*('[^']*'|\"[^\"]*\"|\d+(?:\.\d+)?|[^,;.]+)", re.I)
        pairs: list[tuple[str, str]] = []
        for match in pattern.finditer(text):
            name = self._normalize_identifier(match.group(1))
            value = match.group(2).strip()
            if name:
                pairs.append((name, value))
        return pairs

    def _resolve_column_name(self, name: str, known_columns: list[dict[str, Any]] | None) -> str:
        normalized = self._normalize_identifier(name)
        for col in known_columns or []:
            candidate = str(col.get("name") or "")
            if self._normalize_identifier(candidate) == normalized:
                return self._sanitize_identifier(candidate)
        return self._sanitize_identifier(normalized)

    def _normalize_identifier(self, value: str) -> str:
        raw = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = raw.encode("ascii", "ignore").decode("ascii")
        return self._sanitize_identifier(ascii_text.lower())

    def _sql_literal(self, value: str) -> str:
        raw = str(value or "").strip().strip('"')
        if raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
            return raw
        escaped = raw.replace("'", "''")
        return f"'{escaped}'"

    def _continue_create_table(self, message: str, state: AgentWorkflowState) -> WorkflowDecision:
        slots = dict(state.filled_slots or {}) if state.pending_action == "create_table" else {}
        extracted = self._extract_create_table_slots(message, slots)
        slots.update({k: v for k, v in extracted.items() if v not in (None, "", [])})

        required = ["table_name", "columns"]
        missing = [slot for slot in required if not slots.get(slot)]
        if missing:
            state.set_pending(skill="create_database", action="create_table", required_slots=required, filled_slots=slots)
            question = self._slot_question(missing, slots)
            return WorkflowDecision(True, action="ask_slots", answer=question, data={"required_slots": required, "filled_slots": slots, "missing_slots": missing})

        sql = self._build_create_table_sql(str(slots["table_name"]), slots["columns"])
        table_name = str(slots["table_name"])
        columns = list(slots["columns"] or [])
        state.clear_pending()
        state.remember_sql(sql, intent="create_table")
        state.remember_table(table_name=table_name, columns=columns, summary=f"create_table:{table_name}")
        return WorkflowDecision(
            True,
            action="draft_sql",
            answer="Đã dựng draft SQL tạo bảng từ thông tin bạn cung cấp. Hãy chạy Check Safety trước khi Execute.",
            sql=sql,
            data={"filled_slots": slots, "next_step": "check_safety"},
        )

    def _slot_question(self, missing: list[str], slots: dict[str, Any]) -> str:
        if missing == ["table_name", "columns"]:
            return "Bạn muốn tạo bảng tên gì và gồm những cột nào? Ví dụ: students có id, name, age."
        if "table_name" in missing:
            return "Bạn muốn đặt tên bảng là gì?"
        if "columns" in missing:
            table = slots.get("table_name")
            prefix = f"Bảng `{table}`" if table else "Bảng này"
            return f"{prefix} cần những cột nào? Ví dụ: id, name, age."
        return "Bạn bổ sung thêm thông tin còn thiếu cho workflow này nhé."

    def _extract_create_table_slots(self, message: str, existing: dict[str, Any]) -> dict[str, Any]:
        text = (message or "").strip()
        lower = text.lower()
        slots: dict[str, Any] = {}
        table_text = re.sub(r"(bảng|bang|table)\s+(mới|moi|new)(?=\s|$)", r"\1 ", text, flags=re.I)

        table_patterns = [
            r"create\s+table\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"table\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"bảng\s+(?:tên\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            r"bang\s+(?:ten\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            r"tên\s+bảng\s+(?:là\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            r"ten\s+bang\s+(?:la\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        ]
        for pattern in table_patterns:
            match = re.search(pattern, table_text, re.I)
            if match:
                candidate = self._sanitize_identifier(match.group(1))
                if candidate not in {"moi", "mới", "new", "name", "ten", "tên"}:
                    slots["table_name"] = candidate
                    break
        if not slots.get("table_name") and not existing.get("table_name"):
            words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
            if len(words) == 1 and words[0].lower() not in {"id", "name", "age", "columns", "cols"}:
                slots["table_name"] = self._sanitize_identifier(words[0])

        columns = self._extract_columns(text, lower)
        if columns:
            slots["columns"] = columns
        return slots

    def _extract_columns(self, text: str, lower: str) -> list[dict[str, str]]:
        candidate = ""
        markers = ["có", "co", "gồm", "gom", "columns", "cols", "fields", "cột", "cot", "with"]
        for marker in markers:
            idx = lower.find(marker)
            if idx >= 0:
                candidate = text[idx + len(marker):].strip(" :;-\n\t")
                break
        if not candidate and "," in text:
            candidate = text
        if not candidate:
            return []
        parts = [p.strip(" .;\n\t") for p in re.split(r",|\band\b|\bvà\b|\bva\b", candidate, flags=re.I) if p.strip(" .;\n\t")]
        columns: list[dict[str, str]] = []
        for part in parts:
            cleaned = re.sub(r"^(cột|cot|field|column)\s+", "", part.strip(), flags=re.I)
            tokens = re.findall(r"[A-Za-z_À-ỹ][A-Za-z0-9_À-ỹ]*", cleaned)
            if not tokens:
                continue
            name = self._normalize_identifier(tokens[0])
            if name.lower() in {"table", "bang", "bảng", "co", "có", "gom", "gồm", "with"}:
                continue
            explicit_type = self._explicit_sql_type(cleaned)
            columns.append({"name": name, "type": explicit_type or self._infer_type(name)})
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for col in columns:
            key = col["name"].lower()
            if key not in seen:
                deduped.append(col)
                seen.add(key)
        return deduped

    def _build_create_table_sql(self, table_name: str, columns: list[dict[str, str]]) -> str:
        safe_table = self._sanitize_identifier(table_name)
        lines = []
        for col in columns:
            name = self._sanitize_identifier(str(col.get("name") or ""))
            if not name:
                continue
            col_type = str(col.get("type") or self._infer_type(name)).upper()
            lines.append(f"    {name} {col_type}")
        if not lines:
            lines = ["    id INTEGER PRIMARY KEY"]
        return "CREATE TABLE " + safe_table + " (\n" + ",\n".join(lines) + "\n);"

    def _explicit_sql_type(self, text: str) -> str | None:
        match = re.search(r"\b(integer|int|bigint|smallint|text|varchar\s*\(\s*\d+\s*\)|varchar|date|datetime|timestamp|boolean|bool|decimal\s*\([^)]*\)|numeric\s*\([^)]*\)|float|double)\b", text, re.I)
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).upper()
        if value == "INT":
            return "INTEGER"
        if value == "BOOL":
            return "BOOLEAN"
        if value == "VARCHAR":
            return "VARCHAR(255)"
        return value

    def _infer_type(self, name: str) -> str:
        lower = name.lower()
        if lower == "id" or lower.endswith("_id"):
            return "INTEGER PRIMARY KEY" if lower == "id" else "INTEGER"
        if lower in {"age", "count", "quantity", "qty", "number", "year", "month", "day"} or lower.endswith("_count"):
            return "INTEGER"
        if lower in {"price", "amount", "total", "balance", "score"} or lower.endswith("_price") or lower.endswith("_amount"):
            return "DECIMAL(18,2)"
        if lower.startswith("is_") or lower.startswith("has_") or lower in {"active", "enabled", "deleted"}:
            return "BOOLEAN"
        if lower.endswith("_at") or lower in {"created_at", "updated_at", "datetime", "timestamp"}:
            return "TIMESTAMP"
        if lower.endswith("_date") or lower == "date":
            return "DATE"
        return "TEXT"

    def _sanitize_identifier(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(value or "").strip())
        if not cleaned:
            return "unnamed"
        if cleaned[0].isdigit():
            cleaned = "t_" + cleaned
        return cleaned

    def _matches(self, lower: str, patterns: list[str]) -> bool:
        return any(re.search(pattern, lower, re.I) for pattern in patterns)
