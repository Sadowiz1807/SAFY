from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


@dataclass
class ParsedCommand:
    mode: str
    action: str
    message: str
    raw_message: str
    is_database_task: bool
    requires_execute: bool


class CommandRouterSkill:
    database_keywords = [
        "database", "db", "sql", "query", "table", "schema", "column", "row", "select",
        "insert", "update", "delete", "drop", "mysql", "postgres", "postgresql", "sqlite",
        "oracle", "sql server", "dữ liệu", "du lieu", "bảng", "bang", "truy vấn", "truy van",
        "cột", "cot", "hàng", "hang", "orders", "users", "customers"
    ]

    execute_patterns = [
        r"create\s+table", r"alter\s+table", r"drop\s+table", r"truncate\s+table",
        r"insert\s+into", r"update\s+\w+", r"delete\s+from", r"select\s+.+\s+from",
        r"show\s+tables", r"show\s+(?:ra\s+)?(?:.*?)(?:data|rows|records|dữ\s+liệu|du\s+lieu)",
        r"describe\s+\w+", r"explain\s+select", r"run\s+query",
        r"execute\s+query", r"generate\s+sql", r"truy\s+vấn", r"truy\s+van",
        r"liệt\s+kê", r"liet\s+ke", r"hiển\s+thị", r"hien\s+thi", r"xem\s+(?:dữ\s+liệu|du\s+lieu|bảng|bang)",
        r"tạo\s+bảng", r"tao\s+bang"
    ]

    def parse(self, message: str, command_mode: str | None = None) -> ParsedCommand:
        raw = message or ""
        stripped = raw.strip()
        lower = stripped.lower()
        mode = (command_mode or "chat").strip().lower()
        action = "chat"
        normalized_message = stripped

        if lower.startswith("/execute"):
            mode = "execute"
            action = "execute_sql_draft"
            normalized_message = stripped[len("/execute"):].strip()
        elif lower == "/reset_schema":
            mode = "schema"
            action = "reset_schema"
        elif lower == "/delete_schema":
            mode = "schema"
            action = "delete_active_schema"
        elif mode == "execute":
            action = "execute_sql_draft"

        is_database_task = any(keyword in lower for keyword in self.database_keywords)
        requires_execute = any(re.search(pattern, lower, re.I) for pattern in self.execute_patterns)

        return ParsedCommand(
            mode=mode,
            action=action,
            message=normalized_message or stripped,
            raw_message=raw,
            is_database_task=is_database_task,
            requires_execute=requires_execute,
        )
