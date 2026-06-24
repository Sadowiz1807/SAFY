from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


STATE_VERSION = 2


@dataclass
class AgentWorkflowState:
    """Small, serializable workflow memory for one chat/session.

    This state intentionally stores workflow facts only. It must not store raw
    result rows, raw secrets, API keys, passwords, DSNs, or stack traces.
    """

    version: int = STATE_VERSION
    workflow_id: str = field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:12]}")
    current_database: str | None = None
    current_target: str | None = None
    current_sandbox_id: str | None = None
    current_database_profile_id: str | None = None
    pending_skill: str | None = None
    pending_action: str | None = None
    required_slots: list[str] = field(default_factory=list)
    filled_slots: dict[str, Any] = field(default_factory=dict)
    last_user_intent: str | None = None
    last_intent: str | None = None
    last_safety_class: str | None = None
    pending_confirmation: dict[str, Any] | None = None
    last_tool_result_summary: dict[str, Any] | None = None
    workflow_history: list[dict[str, Any]] = field(default_factory=list)
    last_task_summary: str | None = None
    last_table_name: str | None = None
    last_table_columns: list[dict[str, Any]] = field(default_factory=list)
    last_sql: str | None = None
    last_sql_hash: str | None = None
    last_check_id: str | None = None
    last_safety_result: dict[str, Any] | None = None
    last_execution_result: dict[str, Any] | None = None
    last_error: dict[str, Any] | None = None
    current_driver: str | None = None
    current_dialect: str | None = None
    schema_generation: str | None = None
    context_generation: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AgentWorkflowState":
        if not isinstance(data, dict):
            return cls()
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        payload = {k: v for k, v in data.items() if k in allowed}
        state = cls(**payload)
        if not state.workflow_id:
            state.workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        if state.required_slots is None:
            state.required_slots = []
        if state.filled_slots is None:
            state.filled_slots = {}
        if state.last_table_columns is None:
            state.last_table_columns = []
        if state.workflow_history is None:
            state.workflow_history = []
        state.sanitize_restored_context()
        return state

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "workflow_id": self.workflow_id,
            "current_database": self.current_database,
            "current_target": self.current_target,
            "current_sandbox_id": self.current_sandbox_id,
            "current_database_profile_id": self.current_database_profile_id,
            "pending_skill": self.pending_skill,
            "pending_action": self.pending_action,
            "required_slots": list(self.required_slots or []),
            "filled_slots": dict(self.filled_slots or {}),
            "last_user_intent": self.last_user_intent,
            "last_intent": self.last_intent,
            "last_safety_class": self.last_safety_class,
            "pending_confirmation": self.pending_confirmation,
            "last_tool_result_summary": self.last_tool_result_summary,
            "workflow_history": list(self.workflow_history or [])[-20:],
            "last_task_summary": self.last_task_summary,
            "last_table_name": self.last_table_name,
            "last_table_columns": list(self.last_table_columns or []),
            "last_sql": self.last_sql,
            "last_sql_hash": self.last_sql_hash,
            "last_check_id": self.last_check_id,
            "last_safety_result": self.last_safety_result,
            "last_execution_result": self.last_execution_result,
            "last_error": self.last_error,
            "current_driver": self.current_driver,
            "current_dialect": self.current_dialect,
            "schema_generation": self.schema_generation,
            "context_generation": self.context_generation,
        }

    def has_pending(self) -> bool:
        return bool(self.pending_skill and self.pending_action)

    def missing_slots(self) -> list[str]:
        filled = self.filled_slots or {}
        return [slot for slot in (self.required_slots or []) if not filled.get(slot)]

    def set_pending(self, *, skill: str, action: str, required_slots: list[str], filled_slots: dict[str, Any] | None = None) -> None:
        self.pending_skill = skill
        self.pending_action = action
        self.required_slots = list(required_slots or [])
        if filled_slots:
            self.filled_slots.update({k: v for k, v in filled_slots.items() if v not in (None, "", [])})

    def clear_pending(self) -> None:
        self.pending_skill = None
        self.pending_action = None
        self.required_slots = []
        self.filled_slots = {}

    def invalidate_execution_context(self) -> None:
        self.last_sql = None
        self.last_sql_hash = None
        self.last_check_id = None
        self.last_safety_result = None
        self.pending_confirmation = None

    def invalidate_bound_context(self, *, clear_context: bool = False) -> None:
        """Invalidate state that was bound to a database/schema generation.

        External events such as profile activation and schema refresh may occur
        outside the current chat. They must revoke any draft/check material in
        every session. Profile activation additionally clears the selected
        target so a later request has to resolve the active profile again.
        """
        self.invalidate_execution_context()
        self.last_execution_result = None
        self.schema_generation = None
        if clear_context:
            self.current_database = None
            self.current_target = None
            self.current_sandbox_id = None
            self.current_database_profile_id = None
            self.current_driver = None
            self.current_dialect = None
        self.context_generation += 1

    def _invalidate_restored_context(self) -> None:
        self.current_target = None
        self.current_sandbox_id = None
        self.current_database_profile_id = None
        self.invalidate_execution_context()
        self.context_generation += 1

    def sanitize_restored_context(self) -> None:
        target = self.current_target
        contradictory = False
        if target == "connected_database":
            if not self.current_database_profile_id:
                self._invalidate_restored_context()
                return
            if self.current_sandbox_id is not None:
                self.current_sandbox_id = None
                contradictory = True
        elif target == "sandbox":
            if not self.current_sandbox_id:
                self._invalidate_restored_context()
                return
            if self.current_database_profile_id is not None:
                self.current_database_profile_id = None
                contradictory = True
        elif target in (None, ""):
            if self.current_sandbox_id or self.current_database_profile_id:
                self.current_sandbox_id = None
                self.current_database_profile_id = None
                contradictory = True
        else:
            self._invalidate_restored_context()
            return
        if contradictory:
            self.invalidate_execution_context()
            self.context_generation += 1

    def transition_context(
        self,
        *,
        target: str | None,
        sandbox_id: str | None = None,
        database_profile_id: str | None = None,
        database_name: str | None = None,
        driver: str | None = None,
        dialect: str | None = None,
        schema_generation: str | None = None,
    ) -> None:
        next_target = target or self.current_target
        changed = False
        if next_target == "connected_database":
            if not database_profile_id:
                raise ValueError("database_profile_id is required for connected_database context")
            changed = changed or self.current_target != next_target or self.current_database_profile_id != database_profile_id or self.current_sandbox_id is not None
            self.current_target = next_target
            self.current_database_profile_id = database_profile_id
            self.current_sandbox_id = None
        elif next_target == "sandbox":
            if not sandbox_id:
                raise ValueError("sandbox_id is required for sandbox context")
            changed = changed or self.current_target != next_target or self.current_sandbox_id != sandbox_id or self.current_database_profile_id is not None
            self.current_target = next_target
            self.current_sandbox_id = sandbox_id
            # A sandbox may be derived from a database profile, but it is not the
            # execution target. Avoid serializing an opposing connected profile.
            self.current_database_profile_id = None
        else:
            changed = changed or self.current_target != next_target
            self.current_target = next_target
            self.current_sandbox_id = None
            self.current_database_profile_id = None
        if database_name is not None:
            changed = changed or self.current_database != database_name
            self.current_database = database_name
        if driver is not None:
            changed = changed or self.current_driver != driver
            self.current_driver = driver
        if dialect is not None:
            changed = changed or self.current_dialect != dialect
            self.current_dialect = dialect
        if schema_generation is not None:
            changed = changed or self.schema_generation != schema_generation
            self.schema_generation = schema_generation
        if changed:
            self.context_generation += 1
            self.invalidate_execution_context()

    def remember_context(self, *, target: str | None, sandbox_id: str | None, database_profile_id: str | None, database_name: str | None = None) -> None:
        if target in {"connected_database", "sandbox"}:
            self.transition_context(target=target, sandbox_id=sandbox_id, database_profile_id=database_profile_id, database_name=database_name)
            return
        if target:
            self.current_target = target
        if sandbox_id:
            self.current_sandbox_id = sandbox_id
        if database_profile_id:
            self.current_database_profile_id = database_profile_id
        if database_name:
            self.current_database = database_name

    def remember_sql(self, sql: str | None, *, intent: str | None = None, safety_class: str | None = None) -> None:
        if sql:
            self.last_sql = sql
        if intent:
            self.last_user_intent = intent
            self.last_intent = intent
        if safety_class:
            self.last_safety_class = safety_class

    def remember_table(self, *, table_name: str | None, columns: list[dict[str, Any]] | None = None, summary: str | None = None) -> None:
        if table_name:
            self.last_table_name = table_name
        if columns is not None:
            self.last_table_columns = list(columns or [])
        if summary:
            self.last_task_summary = summary

    def remember_check(self, check: dict[str, Any]) -> None:
        self.last_safety_result = dict(check or {})
        if check.get("risk_class") or check.get("action_class"):
            self.last_safety_class = check.get("risk_class") or check.get("action_class")
        self.last_check_id = check.get("check_id") or self.last_check_id
        self.last_sql_hash = check.get("sql_hash") or self.last_sql_hash
        if check.get("error_code"):
            self.last_error = {"code": check.get("error_code"), "message": check.get("message") or check.get("summary")}

    def remember_execute(self, result: dict[str, Any]) -> None:
        result = result or {}
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        row_count = result.get("row_count")
        if row_count is None:
            row_count = metadata.get("row_count")
        error = result.get("error") if isinstance(result.get("error"), dict) else None
        code = result.get("code") or (error or {}).get("code")
        message = result.get("message") or (error or {}).get("message")

        # Persist workflow facts only. Result rows, columns, provider payloads,
        # SQL text, and secrets remain response-scoped and never enter state.
        self.last_execution_result = {
            key: value
            for key, value in {
                "success": result.get("success") if "success" in result else not bool(code or error),
                "status": result.get("status"),
                "code": code,
                "message": message,
                "row_count": row_count,
                "read_only": result.get("read_only", metadata.get("read_only")),
                "user_controlled": result.get("user_controlled", metadata.get("user_controlled")),
                "sandbox_validated": result.get("sandbox_validated"),
                "schema_changed": result.get("schema_changed"),
                "schema_refresh_required": result.get("schema_refresh_required"),
                "audit_id": result.get("audit_id"),
                "action_class": result.get("action_class"),
            }.items()
            if value is not None
        }
        self.last_tool_result_summary = {
            "ok": not bool(code or error),
            "row_count": row_count,
            "read_only": result.get("read_only", metadata.get("read_only")),
        }
        if code or error:
            self.last_error = {"code": code, "message": message}

    def remember_plan(self, plan: dict[str, Any]) -> None:
        if not isinstance(plan, dict):
            return
        self.last_intent = plan.get("intent") or self.last_intent
        self.last_safety_class = plan.get("action_class") or self.last_safety_class
        self.workflow_history.append({k: plan.get(k) for k in ("intent", "action_class", "route", "next_step")})
        self.workflow_history = self.workflow_history[-20:]

    def remember_confirmation(self, confirmation: dict[str, Any] | None) -> None:
        self.pending_confirmation = confirmation if confirmation else None
