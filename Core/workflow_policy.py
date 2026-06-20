from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re


READ_ONLY_SQL = "READ_ONLY_SQL"
WRITE_SQL = "WRITE_SQL"
DDL_SQL = "DDL_SQL"
DESTRUCTIVE_SQL = "DESTRUCTIVE_SQL"
SECRET_ACCESS = "SECRET_ACCESS"
UNKNOWN_RISK = "UNKNOWN_RISK"
META = "META"


@dataclass
class WorkflowPlan:
    """Deterministic workflow plan for one SAFY turn.

    This object is intentionally model-agnostic. It is safe to persist because it
    stores only redacted routing facts, not raw result rows or secrets.
    """

    intent: str = "unknown"
    action_class: str = UNKNOWN_RISK
    route: str = "clarify"
    requires_sandbox: bool = False
    requires_confirmation: bool = False
    can_auto_execute: bool = False
    statement_type: str | None = None
    target: str | None = None
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    next_step: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "action_class": self.action_class,
            "route": self.route,
            "requires_sandbox": self.requires_sandbox,
            "requires_confirmation": self.requires_confirmation,
            "can_auto_execute": self.can_auto_execute,
            "statement_type": self.statement_type,
            "target": self.target,
            "skills": list(self.skills),
            "tools": list(self.tools),
            "reasons": list(dict.fromkeys(self.reasons)),
            "next_step": self.next_step,
        }


_WRITE_WORDS = re.compile(r"\b(insert|update|delete|merge|upsert|replace)\b", re.I)
_DDL_WORDS = re.compile(r"\b(create|alter|rename|comment)\b", re.I)
_DESTRUCTIVE_WORDS = re.compile(r"\b(drop|truncate|grant|revoke|vacuum|analyze|reindex)\b", re.I)
_SECRET_WORDS = re.compile(r"\b(api[_ -]?key|secret|password|token|credential|dsn|connection string)\b", re.I)
_READ_WORDS = re.compile(r"\b(select|show|describe|explain|list|hiển\s+thị|hien\s+thi|xem|lấy|lay)\b", re.I)


def classify_text_intent(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return "empty"
    if _SECRET_WORDS.search(value):
        return "secret_access"
    if _DESTRUCTIVE_WORDS.search(value):
        return "destructive_sql"
    if _DDL_WORDS.search(value):
        return "ddl_sql"
    if _WRITE_WORDS.search(value):
        return "write_sql"
    if _READ_WORDS.search(value):
        return "read_sql"
    return "chat"


def classify_sql_action(sql: str, statement_type: str | None = None, is_read_only: bool | None = None) -> tuple[str, list[str]]:
    text = (sql or "").strip()
    lower = text.lower()
    reasons: list[str] = []
    if not text:
        return UNKNOWN_RISK, ["empty_sql"]
    if _SECRET_WORDS.search(text):
        return SECRET_ACCESS, ["secret_keyword_detected"]
    if _DESTRUCTIVE_WORDS.search(text):
        return DESTRUCTIVE_SQL, ["destructive_sql_keyword"]
    if is_read_only is True or lower.startswith(("select", "show", "describe", "explain")):
        return READ_ONLY_SQL, ["read_only_sql"]
    st = (statement_type or "").upper()
    if st in {"CREATE", "ALTER", "RENAME", "COMMENT"} or _DDL_WORDS.search(text):
        return DDL_SQL, ["ddl_sql"]
    if st in {"INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "REPLACE"} or _WRITE_WORDS.search(text):
        return WRITE_SQL, ["write_sql"]
    return UNKNOWN_RISK, ["unknown_sql_risk"]


def plan_for_sql(*, sql: str, statement_type: str | None = None, is_read_only: bool | None = None, target: str | None = None) -> WorkflowPlan:
    action_class, reasons = classify_sql_action(sql, statement_type=statement_type, is_read_only=is_read_only)
    if action_class == READ_ONLY_SQL:
        return WorkflowPlan(
            intent="read_sql",
            action_class=READ_ONLY_SQL,
            route="direct_read",
            requires_sandbox=False,
            requires_confirmation=False,
            can_auto_execute=True,
            statement_type=statement_type,
            target=target,
            skills=["query_guard", "execute_query"],
            tools=["sql.guard", "database.read"],
            reasons=reasons,
            next_step="present_result",
        )
    if action_class in {WRITE_SQL, DDL_SQL}:
        # Ordinary write/DDL is not auto-executed and does not use a separate
        # numeric confirmation code by default. The confirmation boundary is:
        # user-reviewed Execute Box + successful sandbox validation + explicit
        # Execute click. Destructive classes keep the stronger confirmation/block
        # route below.
        return WorkflowPlan(
            intent="write_sql" if action_class == WRITE_SQL else "ddl_sql",
            action_class=action_class,
            route="sandbox_then_explicit_execute",
            requires_sandbox=True,
            requires_confirmation=False,
            can_auto_execute=False,
            statement_type=statement_type,
            target=target,
            skills=["query_guard", "execute_box", "execute_query"],
            tools=["sql.guard", "sandbox.validate", "database.execute"],
            reasons=reasons + ["write_requires_sandbox_then_explicit_execute"],
            next_step="check_safety",
        )
    if action_class == DESTRUCTIVE_SQL:
        return WorkflowPlan(
            intent="destructive_sql",
            action_class=DESTRUCTIVE_SQL,
            route="strong_confirmation_or_block",
            requires_sandbox=True,
            requires_confirmation=True,
            can_auto_execute=False,
            statement_type=statement_type,
            target=target,
            skills=["query_guard"],
            tools=["sql.guard"],
            reasons=reasons + ["destructive_sql_needs_strong_confirmation"],
            next_step="blocked_or_manual_review",
        )
    if action_class == SECRET_ACCESS:
        return WorkflowPlan(
            intent="secret_access",
            action_class=SECRET_ACCESS,
            route="block_or_redact",
            requires_sandbox=False,
            requires_confirmation=False,
            can_auto_execute=False,
            statement_type=statement_type,
            target=target,
            skills=["query_guard"],
            tools=[],
            reasons=reasons + ["secret_access_not_allowed"],
            next_step="redact_or_refuse",
        )
    return WorkflowPlan(
        intent="unknown",
        action_class=UNKNOWN_RISK,
        route="clarify",
        requires_sandbox=False,
        requires_confirmation=False,
        can_auto_execute=False,
        statement_type=statement_type,
        target=target,
        skills=["command_router"],
        tools=[],
        reasons=reasons,
        next_step="ask_clarification",
    )
