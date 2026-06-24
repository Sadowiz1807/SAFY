from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path
import json
import re

from Gateway.query_orchestrator import QueryOrchestrator
from Core.agent_state import AgentWorkflowState
from Core.context_pack import ContextPack
from Core.skill_registry import SkillRegistry
from Tools.registry import ToolRegistry, ToolMetadata
from Core.workflow_engine import WorkflowEngine
from Core.workflow_policy import plan_for_sql, classify_text_intent
from Core.workflow_review import WorkflowReviewCoordinator
from LLM.provider_health import adapter_for
from .schema_context import summarize_schema
from DataStore.schema_graph_store import summarize_schema_graph
from Core.skill_actions import (
    CommandRouterSkill,
    DatabaseContextSkill,
    SchemaGraphSkill,
    TextToSqlSkill,
    QueryGuardSkill,
    ExecuteBoxSkill,
    ExecuteQuerySkill,
    QueryExplainSkill,
    QueryRepairSkill,
)

DEFAULT_SYSTEM_PROMPT = """You are Safy, an AI Database Agent.
Be concise, practical, and safety-first.
Never execute destructive SQL automatically.
For write/DDL requests, draft SQL only for review; SQL Guard will block execution in read-only mode.
Prefer read-only SQL.
Use SQL Guard before execution.
If the user intent is unclear, ask a short clarification question instead of blocking.
Do not expose raw secrets, API keys, DSN strings, or internal stack traces.
Do not pretend a database is connected when only a test-support profile exists.
Do not show model/provider/chat errors as query execution errors.
Return JSON only with keys: intent, sql, explanation, target_hint, requires_confirmation."""

GREETING_REPLY = "Chào bạn, tôi là Safy. Hãy kết nối database hoặc mô tả tác vụ database bạn muốn thực hiện."
DATABASE_MISSING_REPLY = "Bạn cần kết nối database thật trước khi Safy có thể truy vấn hoặc kiểm tra dữ liệu."
DATABASE_COMMAND_REQUIRES_EXECUTE_REPLY = "Database đã kết nối. Read-only/show data có thể chạy trực tiếp trong chat nếu Auto-run read-only bật. Với thao tác ghi/DDL, SAFY sẽ đặt SQL vào Execute Box để bạn review, Check Safety bằng sandbox rồi mới Execute."
CLARIFY_REPLY = "Bạn muốn Safy hỗ trợ tác vụ database nào? Hãy mô tả ngắn bảng, dữ liệu, hoặc câu hỏi cần kiểm tra."
WRITE_OPERATION_BLOCKED_REPLY = "Yêu cầu này là thao tác ghi/DDL. SAFY không tự chạy trực tiếp trong chat; hệ thống sẽ tạo SQL draft trong Execute Box để bạn review, chạy Check Safety bằng sandbox, rồi chỉ Execute real database sau khi sandbox pass và bạn bấm Execute."
LLM_UNSTRUCTURED_REPLY = "Model không trả về SQL có cấu trúc. SAFY đã giữ an toàn và không thực thi gì. Hãy thử yêu cầu cụ thể hơn, ví dụ: /Execute select 5 rows from users."


@dataclass
class AgentRuntime:
    query_orchestrator: QueryOrchestrator
    provider_store: Any
    sandbox_manager: Any | None = None
    database_profile_loader: Any | None = None
    schema_graph_loader: Any | None = None
    runtime_db: Any | None = None

    def __post_init__(self) -> None:
        self.command_router_skill = CommandRouterSkill()
        self.database_context_skill = DatabaseContextSkill(
            database_profile_loader=self.database_profile_loader,
            sandbox_manager=self.sandbox_manager,
        )
        self.schema_graph_skill = SchemaGraphSkill(schema_graph_loader=self.schema_graph_loader)
        self.text_to_sql_skill = TextToSqlSkill(self.provider_store, self._system_prompt)
        self.query_guard_skill = QueryGuardSkill(self.query_orchestrator)
        self.execute_box_skill = ExecuteBoxSkill()
        self.execute_query_skill = ExecuteQuerySkill(self.query_orchestrator)
        self.query_explain_skill = QueryExplainSkill()
        self.query_repair_skill = QueryRepairSkill()
        self.workflow_engine = WorkflowEngine()
        self.workflow_reviewer = WorkflowReviewCoordinator()
        self._memory_states: dict[str, dict[str, Any]] = {}
        self.skill_registry = SkillRegistry()
        self.tool_registry = ToolRegistry()
        self._attach_shared_skill_actions()
        self._register_runtime_tools()

    def _attach_shared_skill_actions(self) -> None:
        self.skill_registry.attach_actions(
            "command_router",
            {"parse": self.command_router_skill.parse},
        )
        self.skill_registry.attach_actions(
            "database_context",
            {"resolve": self.database_context_skill.resolve},
        )
        self.skill_registry.attach_actions(
            "schema_graph",
            {
                "load": self.schema_graph_skill.load,
                "summarize": self.schema_graph_skill.summarize,
                "select_relevant_subset": self.schema_graph_skill.select_relevant_subset,
            },
        )
        self.skill_registry.attach_actions(
            "text_to_sql",
            {"generate_sql_draft": self.text_to_sql_skill.generate_sql_draft},
        )
        self.skill_registry.attach_actions(
            "query_guard",
            {"check": self.query_guard_skill.check},
        )
        self.skill_registry.attach_actions(
            "execute_box",
            {"set_draft": self.execute_box_skill.set_draft},
        )
        self.skill_registry.attach_actions(
            "execute_query",
            {"execute_checked": self.execute_query_skill.execute_checked},
        )
        self.skill_registry.attach_actions(
            "query_explain",
            {"explain": self.query_explain_skill.explain},
        )
        self.skill_registry.attach_actions(
            "query_repair",
            {"repair_basic": self.query_repair_skill.repair_basic},
        )

    def _register_runtime_tools(self) -> None:
        class RuntimeToolStub:
            def __init__(self, name: str, toolset: str) -> None:
                self.name = name
                self.toolset = toolset

        tool_specs = [
            ("sql.guard", "sql", "Validate SQL and classify risk before any execution.", "UNKNOWN_RISK", True, False, False, False),
            ("database.read", "database", "Run read-only SQL against the active connected database.", "READ_ONLY_SQL", True, False, False, False),
            ("sandbox.validate", "sandbox", "Run write/DDL SQL in sandbox before real execution.", "WRITE_SQL", False, False, True, False),
            ("database.execute", "database", "Execute sandbox-validated write/DDL SQL on connected database.", "WRITE_SQL", False, True, True, True),
            ("schema.graph.read", "schema", "Read cached schema graph for context packing.", "READ_ONLY_SQL", True, False, False, False),
            ("execute_box.set_draft", "ui", "Place SQL in Execute Box for user review.", "META", True, False, False, False),
        ]
        for name, toolset, description, risk_class, read_only, writes_database, requires_sandbox, requires_confirmation in tool_specs:
            self.tool_registry.register(
                RuntimeToolStub(name, toolset),
                ToolMetadata(
                    name=name,
                    toolset=toolset,
                    description=description,
                    risk_class=risk_class,
                    read_only=read_only,
                    writes_database=writes_database,
                    requires_sandbox=requires_sandbox,
                    requires_confirmation=requires_confirmation,
                ),
            )

    def _state_key(self, session_id: str | None) -> str:
        return session_id or "__default__"

    def _load_state(self, session_id: str | None) -> AgentWorkflowState:
        key = self._state_key(session_id)
        if session_id and self.runtime_db and hasattr(self.runtime_db, "get_agent_state"):
            try:
                return AgentWorkflowState.from_dict(self.runtime_db.get_agent_state(session_id))
            except Exception:
                pass
        return AgentWorkflowState.from_dict(self._memory_states.get(key))

    def _save_state(self, session_id: str | None, state: AgentWorkflowState) -> None:
        payload = state.to_dict()
        key = self._state_key(session_id)
        self._memory_states[key] = payload
        if session_id and self.runtime_db and hasattr(self.runtime_db, "update_agent_state"):
            try:
                self.runtime_db.update_agent_state(session_id, payload)
            except Exception:
                # State persistence must not break the chat path.
                pass

    def _build_context_pack(self, *, session_id: str | None, message: str, state: AgentWorkflowState, target: str | None, sandbox_id: str | None, database_profile_id: str | None) -> ContextPack:
        resolved_ctx = self.database_context_skill.resolve(target, sandbox_id, database_profile_id)
        schema_text = self._schema_context_text(resolved_ctx.target, resolved_ctx.sandbox_id, resolved_ctx.database_profile_id)
        database_name = None
        if resolved_ctx.database_profile:
            database_name = str(resolved_ctx.database_profile.get("database") or resolved_ctx.database_profile.get("display_name") or "") or None
        state.remember_context(
            target=resolved_ctx.target,
            sandbox_id=resolved_ctx.sandbox_id,
            database_profile_id=resolved_ctx.database_profile_id,
            database_name=database_name,
        )
        return ContextPack(
            session_id=session_id,
            user_message=message,
            target=resolved_ctx.target,
            sandbox_id=resolved_ctx.sandbox_id,
            database_profile_id=resolved_ctx.database_profile_id,
            database_profile=resolved_ctx.database_profile,
            schema_summary=schema_text,
            state=state,
            available_skills=self.skill_registry.active_names(),
        )

    def _target_from_context_pack(self, context_pack: ContextPack) -> dict[str, Any]:
        return {
            "target": context_pack.target,
            "sandbox_id": context_pack.sandbox_id,
            "database_profile_id": context_pack.database_profile_id,
        }

    def _record_workflow_event(self, session_id: str | None, state: AgentWorkflowState, stage: str, status: str = "ok", metadata: dict[str, Any] | None = None) -> None:
        if not session_id or not self.runtime_db or not hasattr(self.runtime_db, "record_workflow_event"):
            return
        try:
            self.runtime_db.record_workflow_event(session_id, stage=stage, status=status, workflow_id=state.workflow_id, metadata=metadata or {})
        except Exception:
            pass

    def _record_tool_call(self, session_id: str | None, state: AgentWorkflowState, tool_name: str, status: str = "ok", risk_class: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        if not session_id or not self.runtime_db or not hasattr(self.runtime_db, "record_tool_call"):
            return
        try:
            self.runtime_db.record_tool_call(session_id, tool_name=tool_name, status=status, workflow_id=state.workflow_id, risk_class=risk_class, metadata=metadata or {})
        except Exception:
            pass

    def _plan_review_payload(self, *, sql: str, context_pack: ContextPack, state: AgentWorkflowState, check: dict[str, Any] | None = None, result: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        statement_type = check.get("statement_type") if isinstance(check, dict) else None
        is_read_only = check.get("read_only") if isinstance(check, dict) else None
        plan = plan_for_sql(sql=sql, statement_type=statement_type, is_read_only=is_read_only, target=context_pack.target)
        review = self.workflow_reviewer.review(plan=plan, check=check, result=result, context={"target": context_pack.target, "database_profile_id": context_pack.database_profile_id})
        plan_dict = plan.to_dict()
        review_dict = review.to_dict()
        state.remember_plan(plan_dict)
        self._record_workflow_event(context_pack.session_id, state, "plan", metadata=plan_dict)
        self._record_workflow_event(context_pack.session_id, state, "review", status="ok" if review.ok else "blocked", metadata=review_dict)
        return plan_dict, review_dict

    def _draft_response_from_sql(self, *, sql: str, answer: str, context_pack: ContextPack, state: AgentWorkflowState, extra_safety: dict[str, Any] | None = None) -> dict[str, Any]:
        target_payload = self._target_from_context_pack(context_pack)
        draft = self.execute_box_skill.set_draft(sql=sql, explanation=answer, target=target_payload, provider_profile_id=None)
        explain = self.query_explain_skill.explain(sql, None)
        plan, review = self._plan_review_payload(sql=sql, context_pack=context_pack, state=state)
        state.remember_sql(sql, intent=state.last_user_intent or "database_task", safety_class=plan.get("action_class"))
        self._record_tool_call(context_pack.session_id, state, "execute_box.set_draft", metadata={"draft_only": True, "action_class": plan.get("action_class")})
        self._save_state(context_pack.session_id, state)
        return {
            "success": True,
            "answer": answer,
            "generated_sql": sql,
            "check": None,
            "execute": {"executed": False, "draft_only": True},
            "execute_box": draft,
            "query_explain": explain,
            "workflow_plan": plan,
            "workflow_review": review,
            "safety": {
                "workflow": "draft_only",
                "next_step": "check_safety",
                "target": context_pack.target,
                "blocked": False,
                "warnings": [],
                "skills": ["workflow_engine", "execute_box", "query_explain"],
                **(extra_safety or {}),
            },
            "agent_state": state.to_dict(),
            "context_pack": context_pack.to_dict(),
        }

    def _format_query_result_for_chat(self, result: dict[str, Any], sql: str) -> str:
        rows = result.get("rows") or result.get("result", {}).get("rows") or []
        if not isinstance(rows, list):
            rows = []
        row_count = result.get("row_count")
        if row_count is None:
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            row_count = metadata.get("row_count", len(rows))
        return f"Đã đọc dữ liệu an toàn từ database. Row count: {row_count}."

    def _cell_for_chat(self, value: Any) -> str:
        text = "" if value is None else str(value)
        text = text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
        if len(text) > 80:
            text = text[:77] + "..."
        return text

    def _query_result_display_payload(self, result: dict[str, Any], sql: str) -> dict[str, Any]:
        rows = result.get("rows") or result.get("result", {}).get("rows") or []
        if not isinstance(rows, list):
            rows = []
        columns = result.get("columns") or []
        if not columns:
            seen: list[str] = []
            for row in rows:
                if isinstance(row, dict):
                    for key in row.keys():
                        if key not in seen:
                            seen.append(str(key))
            columns = seen
        row_count = result.get("row_count")
        if row_count is None:
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            row_count = metadata.get("row_count", len(rows))
        return {
            "type": "query_result",
            "title": "Database result",
            "mode": "read_only_direct",
            "sql": sql.strip(),
            "columns": [str(c) for c in columns],
            "rows": rows,
            "row_count": row_count,
            "read_only": True,
            "result_rows_persisted": False,
        }

    def _ensure_direct_read_limit(self, sql: str, limit: int = 100) -> str:
        text = (sql or "").strip()
        if not text:
            return text
        upper = text.upper()
        if not upper.startswith("SELECT"):
            return text
        if re.search(r"\bLIMIT\s+\d+\b", upper, re.I):
            return text
        if text.endswith(";"):
            return text[:-1].rstrip() + f" LIMIT {limit};"
        return text.rstrip() + f" LIMIT {limit};"

    def _direct_read_response_from_sql(self, *, sql: str, context_pack: ContextPack, state: AgentWorkflowState) -> dict[str, Any]:
        sql = self._ensure_direct_read_limit(sql, limit=100)
        target_payload = self._target_from_context_pack(context_pack)
        check = self.query_guard_skill.check(
            sql=sql,
            target=target_payload,
            database_profile=context_pack.database_profile,
            permission_mode="read_only",
            execution_path="agent_direct_readonly",
        )
        plan, review = self._plan_review_payload(sql=sql, context_pack=context_pack, state=state, check=check)
        state.remember_sql(sql, intent="read_query", safety_class=plan.get("action_class"))
        state.remember_check({**check, "action_class": plan.get("action_class")})
        self._record_tool_call(context_pack.session_id, state, "sql.guard", status="ok" if check.get("allowed_to_attempt") else "blocked", risk_class=plan.get("action_class"), metadata={"decision": check.get("decision")})
        if not check.get("allowed_to_attempt") or not review.get("ok", False):
            self._save_state(context_pack.session_id, state)
            return {
                "success": True,
                "answer": check.get("blocked_message") or "Read-only query was blocked by SAFY policy.",
                "generated_sql": sql,
                "check": check,
                "execute": {"executed": False, "blocked": True},
                "workflow_plan": plan,
                "workflow_review": review,
                "safety": {"workflow": "direct_read_blocked", "blocked": True, "skills": ["workflow_engine", "query_guard"]},
                "agent_state": state.to_dict(),
                "context_pack": context_pack.to_dict(),
            }
        ok, result = self.execute_query_skill.execute_checked(
            check_id=check.get("check_id") or "",
            sql_hash=check.get("sql_hash") or "",
            target=target_payload,
            user_decision="yes",
            row_limit=100,
        )
        plan, review = self._plan_review_payload(sql=sql, context_pack=context_pack, state=state, check=check, result=result)
        state.remember_execute({**(result or {}), "action_class": plan.get("action_class")})
        self._record_tool_call(context_pack.session_id, state, "database.read", status="ok" if ok else "error", risk_class=plan.get("action_class"), metadata={"row_count": (result or {}).get("row_count") or ((result or {}).get("metadata") or {}).get("row_count") if isinstance((result or {}).get("metadata"), dict) else None})
        self._save_state(context_pack.session_id, state)
        if not ok:
            return {
                "success": True,
                "answer": f"Read-only query failed: {result.get('message') or result.get('code')}",
                "generated_sql": sql,
                "check": check,
                "execute": {"executed": False, **(result or {})},
                "workflow_plan": plan,
                "workflow_review": review,
                "safety": {"workflow": "direct_read_failed", "blocked": True, "skills": ["workflow_engine", "query_guard", "execute_query"]},
                "agent_state": state.to_dict(),
                "context_pack": context_pack.to_dict(),
            }
        answer = self._format_query_result_for_chat(result, sql)
        display_payload = self._query_result_display_payload(result, sql)
        return {
            "success": True,
            "answer": answer,
            "generated_sql": sql,
            "executed_sql": sql,
            "check": check,
            "execute": {**result, "read_only": True},
            "query_result": {
                "sql": sql,
                "columns": display_payload["columns"],
                "rows": display_payload["rows"],
                "row_count": display_payload["row_count"],
                "read_only": True,
            },
            "chat_display": display_payload,
            "workflow_plan": plan,
            "workflow_review": review,
            "safety": {"workflow": "direct_read", "blocked": False, "target": context_pack.target, "skills": ["workflow_engine", "query_guard", "execute_query"]},
            "agent_state": state.to_dict(),
            "context_pack": context_pack.to_dict(),
        }

    def _maybe_direct_read_chat(
        self,
        *,
        message: str,
        session_id: str | None,
        model_profile_id: str | None,
        target: str | None,
        sandbox_id: str | None,
        database_profile_id: str | None,
        state: AgentWorkflowState,
    ) -> dict[str, Any] | None:
        """Allow natural-language read-only database questions without requiring /Execute.

        Write/DDL still goes through the draft-only Execute Box path. This helper is
        intentionally conservative: it only direct-runs SQL if the generated draft is
        classified read-only. Otherwise it returns None so the normal safety path can
        handle it.
        """
        if classify_text_intent(message) != "read_sql":
            return None
        resolved_ctx = self.database_context_skill.resolve(target, sandbox_id, database_profile_id)
        if resolved_ctx.target == "connected_database" and not resolved_ctx.has_real_database:
            return {"success": True, "answer": DATABASE_MISSING_REPLY, "generated_sql": None, "check": None, "execute": None, "safety": None}
        generated = self.generate_sql(
            message,
            model_profile_id=model_profile_id,
            target=resolved_ctx.target,
            sandbox_id=resolved_ctx.sandbox_id,
            database_profile_id=resolved_ctx.database_profile_id,
            session_id=session_id,
        )
        sql = generated.get("generated_sql") or ""
        if not sql:
            return None
        try:
            from Gateway.sql_classifier import classify_sql
            classification = classify_sql(sql)
            if not classification.is_read_only:
                return None
        except Exception:
            return None
        context_for_read = self._build_context_pack(
            session_id=session_id,
            message=message,
            state=state,
            target=resolved_ctx.target,
            sandbox_id=resolved_ctx.sandbox_id,
            database_profile_id=resolved_ctx.database_profile_id,
        )
        return self._direct_read_response_from_sql(sql=sql, context_pack=context_for_read, state=state)

    def _handle_workflow_decision(self, decision, context_pack: ContextPack, state: AgentWorkflowState) -> dict[str, Any] | None:
        if not decision.handled:
            return None
        if decision.action == "ask_slots":
            self._save_state(context_pack.session_id, state)
            return {
                "success": True,
                "answer": decision.answer,
                "generated_sql": None,
                "check": None,
                "execute": None,
                "safety": {
                    "workflow": "slot_filling",
                    "pending_skill": state.pending_skill,
                    "pending_action": state.pending_action,
                    "required_slots": state.required_slots,
                    "missing_slots": state.missing_slots(),
                    "blocked": False,
                    "skills": ["workflow_engine"],
                },
                "agent_state": state.to_dict(),
                "context_pack": context_pack.to_dict(),
            }
        if decision.action == "direct_read" and decision.sql:
            return self._direct_read_response_from_sql(sql=decision.sql, context_pack=context_pack, state=state)
        if decision.action == "draft_sql" and decision.sql:
            return self._draft_response_from_sql(sql=decision.sql, answer=decision.answer, context_pack=context_pack, state=state, extra_safety={"workflow_action": "sql_draft"})
        if decision.action == "missing_last_sql" or decision.action == "missing_check":
            self._save_state(context_pack.session_id, state)
            return {"success": True, "answer": decision.answer, "generated_sql": state.last_sql, "check": None, "execute": None, "safety": {"workflow": decision.action, "blocked": True, "skills": ["workflow_engine"]}, "agent_state": state.to_dict(), "context_pack": context_pack.to_dict()}
        if decision.action == "check_safety":
            target_payload = self._target_from_context_pack(context_pack)
            check = self.query_guard_skill.check(
                sql=state.last_sql or "",
                target=target_payload,
                database_profile=context_pack.database_profile,
                permission_mode="credential_permissions",
                execution_path="agent_workflow_check_safety",
            )
            plan, review = self._plan_review_payload(sql=state.last_sql or "", context_pack=context_pack, state=state, check=check)
            state.remember_check({**check, "action_class": plan.get("action_class")})
            self._record_tool_call(context_pack.session_id, state, "sql.guard", status="ok" if check.get("allowed_to_attempt") else "blocked", risk_class=plan.get("action_class"), metadata={"decision": check.get("decision"), "workflow": "check_safety"})
            self._save_state(context_pack.session_id, state)
            return {
                "success": True,
                "answer": "Check Safety đã chạy xong. Nếu allowed_to_attempt=true, bạn có thể Execute bằng nút Execute hoặc lệnh execute sau khi xác nhận.",
                "generated_sql": state.last_sql,
                "check": check,
                "execute": {"executed": False, "requires_user_confirmation": True},
                "workflow_plan": plan,
                "workflow_review": review,
                "safety": {"workflow": "check_safety", "skills": ["workflow_engine", "query_guard"], "target": context_pack.target},
                "agent_state": state.to_dict(),
                "context_pack": context_pack.to_dict(),
            }
        if decision.action == "execute_checked":
            # Chat-level workflows must not silently execute against a connected
            # real database. Real DB execution remains bound to the Execute Box
            # endpoint, which carries the sandbox-validated check record and the
            # user's explicit UI action. Sandbox execution can still use the
            # runtime check here.
            if context_pack.target == "connected_database":
                self._save_state(context_pack.session_id, state)
                return {
                    "success": True,
                    "answer": "SAFY đã ghi nhớ Check Safety gần nhất. Với connected database, hãy dùng nút Execute trong Execute Box để thực thi thật; chat không tự execute real DB.",
                    "generated_sql": state.last_sql,
                    "check": state.last_safety_result,
                    "execute": {"executed": False, "requires_execute_box": True},
                    "safety": {"workflow": "execute_requires_execute_box", "skills": ["workflow_engine"], "target": context_pack.target},
                    "agent_state": state.to_dict(),
                    "context_pack": context_pack.to_dict(),
                }
            target_payload = self._target_from_context_pack(context_pack)
            ok, result = self.execute_query_skill.execute_checked(
                check_id=state.last_check_id or "",
                sql_hash=state.last_sql_hash or "",
                target=target_payload,
                user_decision="yes",
                row_limit=100,
            )
            plan, review = self._plan_review_payload(sql=state.last_sql or "", context_pack=context_pack, state=state, check=state.last_safety_result or {}, result=result)
            state.remember_execute({**(result or {}), "action_class": plan.get("action_class")})
            self._record_tool_call(context_pack.session_id, state, "database.execute", status="ok" if ok else "error", risk_class=plan.get("action_class"), metadata={"workflow": "execute_checked"})
            self._save_state(context_pack.session_id, state)
            return {
                "success": bool(ok),
                "answer": "Execution succeeded." if ok else f"Execution failed: {result.get('message') or result.get('code')}",
                "generated_sql": state.last_sql,
                "check": state.last_safety_result,
                "execute": result,
                "workflow_plan": plan,
                "workflow_review": review,
                "safety": {"workflow": "execute_checked", "skills": ["workflow_engine", "execute_query"], "target": context_pack.target},
                "agent_state": state.to_dict(),
                "context_pack": context_pack.to_dict(),
            }
        return None

    def record_check_result(self, session_id: str | None, check: dict[str, Any], sql: str | None = None) -> None:
        if not session_id:
            return
        state = self._load_state(session_id)
        if sql:
            state.remember_sql(sql, intent=state.last_user_intent or "database_task")
        state.remember_check(check or {})
        self._save_state(session_id, state)

    def record_execute_result(self, session_id: str | None, result: dict[str, Any]) -> None:
        if not session_id:
            return
        state = self._load_state(session_id)
        state.remember_execute(result or {})
        self._save_state(session_id, state)

    def _soul_path(self) -> Path:
        return Path(__file__).resolve().parents[1] / 'SOUL.md'

    def _system_prompt(self) -> str:
        try:
            content = self._soul_path().read_text(encoding='utf-8').strip()
            return content or DEFAULT_SYSTEM_PROMPT
        except OSError:
            return DEFAULT_SYSTEM_PROMPT

    def _is_greeting(self, message: str) -> bool:
        text = (message or '').strip().lower()
        return text in {'hi', 'hello', 'hey', 'chào', 'chào bạn', 'xin chào'}

    def _looks_like_database_task(self, message: str) -> bool:
        text = (message or '').strip().lower()
        keywords = [
            'database', 'db', 'sql', 'query', 'table', 'schema', 'column', 'row', 'select',
            'insert', 'update', 'delete', 'drop', 'mysql', 'postgres', 'postgresql', 'sqlite',
            'oracle', 'sql server', 'dữ liệu', 'bảng', 'truy vấn', 'cột', 'hàng'
        ]
        return any(keyword in text for keyword in keywords)

    def _requires_execute_command(self, message: str) -> bool:
        text = (message or '').strip().lower()
        if not text:
            return False
        patterns = [
            r'create\s+table', r'alter\s+table', r'drop\s+table', r'truncate\s+table',
            r'insert\s+into', r'update\s+\w+', r'delete\s+from', r'select\s+.+\s+from',
            r'show\s+tables', r'describe\s+\w+', r'explain\s+select', r'run\s+query',
            r'execute\s+query', r'query\s+the', r'inspect\s+.+table', r'generate\s+sql',
            r'tạo\s+bảng', r'tao\s+bang', r'xóa\s+bảng', r'xoa\s+bang',
            r'sửa\s+bảng', r'sua\s+bang', r'thêm\s+dữ\s+liệu', r'them\s+du\s+lieu',
            r'truy\s+vấn', r'truy\s+van', r'kiểm\s+tra\s+bảng', r'kiem\s+tra\s+bang',
            r'liệt\s+kê\s+bảng', r'liet\s+ke\s+bang',
        ]
        return any(re.search(pattern, text, re.I) for pattern in patterns)

    def _is_write_operation_request(self, message: str) -> bool:
        text = (message or '').strip().lower()
        if not text:
            return False
        patterns = [
            r'create\s+(database|table|schema)',
            r'alter\s+table',
            r'drop\s+(database|table|schema)',
            r'truncate\s+table',
            r'insert\s+into',
            r'update\s+\w+',
            r'delete\s+from',
            r'grant\s+',
            r'revoke\s+',
            r'tạo\s+(database|db|bảng|bang)',
            r'tao\s+(1\s+)?(database|db|bang|bảng)',
            r'tạo\s+1\s+database',
            r'tao\s+1\s+database',
            r'thêm\s+dữ\s+liệu',
            r'them\s+du\s+lieu',
            r'xóa\s+(database|db|bảng|bang)',
            r'xoa\s+(database|db|bang|bảng)',
            r'sửa\s+(database|db|bảng|bang)',
            r'sua\s+(database|db|bang|bảng)',
        ]
        return any(re.search(pattern, text, re.I) for pattern in patterns)

    def _has_real_database(self, database_profile_id: str | None) -> bool:
        if not database_profile_id or not self.database_profile_loader:
            return False
        try:
            profile = self.database_profile_loader(database_profile_id)
        except Exception:
            return False
        if not profile:
            return False
        driver = str(profile.get('driver') or profile.get('dbms') or '').lower()
        return bool(profile.get('real_db_readonly')) and driver not in {'', 'fake', 'test'}

    def _resolve_target(self, target: str | None, sandbox_id: str | None, database_profile_id: str | None) -> dict[str, Any]:
        resolved_target = target
        if not resolved_target or resolved_target == "auto":
            if self._has_real_database(database_profile_id):
                resolved_target = "connected_database"
            else:
                resolved_target = "sandbox"

        if resolved_target == "connected_database":
            return {"target": "connected_database", "sandbox_id": None, "database_profile_id": database_profile_id}
        sandbox_id = sandbox_id or "sandbox_default"
        if self.sandbox_manager:
            active = [s for s in self.sandbox_manager.list() if s.get("active") and s.get("state") != "deleted"]
            if active and not sandbox_id:
                sandbox_id = active[0].get("sandbox_id") or active[0].get("id")
        return {"target": "sandbox", "sandbox_id": sandbox_id, "database_profile_id": None}

    def _schema_for(self, target: str, sandbox_id: str | None, database_profile_id: str | None) -> dict[str, Any] | None:
        if target == "connected_database" and self.schema_graph_loader and database_profile_id:
            try:
                graph = self.schema_graph_loader(database_profile_id)
                if graph and graph.get("status") == "ready":
                    return {"schema_graph": graph}
            except Exception:
                return None
        if target == "sandbox" and self.sandbox_manager and sandbox_id:
            try:
                return self.sandbox_manager.schema(sandbox_id)
            except Exception:
                return None
        return None

    def _database_profile_for_runtime(self, database_profile_id: str | None) -> dict[str, Any] | None:
        if not database_profile_id or not self.database_profile_loader:
            return None
        try:
            return self.database_profile_loader(database_profile_id)
        except Exception:
            return None

    def _schema_context_text(self, target: str, sandbox_id: str | None, database_profile_id: str | None) -> str:
        schema = self._schema_for(target, sandbox_id, database_profile_id)
        if isinstance(schema, dict) and isinstance(schema.get("schema_graph"), dict):
            return summarize_schema_graph(schema["schema_graph"])
        return summarize_schema(schema)

    def _llm_content_as_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            if isinstance(content.get("text"), str):
                return content["text"]
            if isinstance(content.get("content"), str):
                return content["content"]
            return json.dumps(content, ensure_ascii=False)
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    value = item.get("text") or item.get("content") or item.get("value")
                    if value is not None:
                        parts.append(str(value))
            return "\n".join(parts).strip()
        return str(content)

    def _extract_sql_candidate(self, content: str) -> str:
        text = (content or "").strip()
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.I | re.S)
        if fenced:
            text = fenced.group(1).strip()
        match = re.search(r"\bSELECT\b[\s\S]+", text, re.I)
        if match:
            return match.group(0).strip().rstrip("`")
        return ""

    def _parse_model_json(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = self._llm_content_as_text(content).strip()
        if not text:
            return {"intent": "unknown", "sql": "", "explanation": LLM_UNSTRUCTURED_REPLY, "target_hint": None, "requires_confirmation": False}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        sql = self._extract_sql_candidate(text)
        return {"intent": "database_task" if sql else "chat", "sql": sql, "explanation": text if text else LLM_UNSTRUCTURED_REPLY, "target_hint": None, "requires_confirmation": False}

    def generate_sql(self, message: str, model_profile_id: str | None = None, target: str | None = None, sandbox_id: str | None = None, database_profile_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        state = self._load_state(session_id)
        context_pack = self._build_context_pack(session_id=session_id, message=message, state=state, target=target, sandbox_id=sandbox_id, database_profile_id=database_profile_id)
        target_payload = self._target_from_context_pack(context_pack)
        graph = None
        if context_pack.target == "connected_database" and context_pack.database_profile_id:
            graph = self.schema_graph_skill.load(context_pack.database_profile_id, context_pack.database_profile)
        subset = self.schema_graph_skill.select_relevant_subset(graph, message)
        schema_text = self.schema_graph_skill.summarize(subset) if context_pack.target == "connected_database" else context_pack.schema_summary
        context_pack.schema_summary = schema_text
        skill_context_text = self.skill_registry.context_for(
            "text_to_sql",
            user_request=message,
            conversation_context=context_pack.to_prompt_text(),
            schema_context=schema_text,
        )
        generated = self.text_to_sql_skill.generate_sql_draft(
            request=message,
            model_profile_id=model_profile_id,
            target=target_payload,
            schema_context_text=schema_text,
            schema_graph=subset if isinstance(subset, dict) else graph,
            context_pack_text=context_pack.to_prompt_text(),
            skill_context_text=skill_context_text,
        )
        generated["schema_graph"] = {
            "status": graph.get("status") if isinstance(graph, dict) else "empty",
            "schema_hash": graph.get("schema_hash") if isinstance(graph, dict) else None,
            "subset_used": bool(isinstance(subset, dict) and subset.get("subset")),
        }
        generated["context_pack"] = context_pack.to_dict()
        sql = generated.get("generated_sql") or ""
        if sql:
            state.remember_sql(sql, intent=str((generated.get("model_output") or {}).get("intent") or "database_task"))
        self._save_state(session_id, state)
        generated["agent_state"] = state.to_dict()
        return generated

    def chat(self, message: str, session_id: str | None = None, model_profile_id: str | None = None, target: str | None = None, sandbox_id: str | None = None, database_profile_id: str | None = None, auto_execute: bool = True, command_mode: str | None = None) -> dict[str, Any]:
        parsed_command = self.command_router_skill.parse(message, command_mode)
        command_mode = parsed_command.mode

        if self._is_greeting(message):
            return {"success": True, "answer": GREETING_REPLY, "generated_sql": None, "check": None, "execute": None, "safety": None}

        state = self._load_state(session_id)
        self._record_workflow_event(session_id, state, "perceive", metadata={"text_intent": classify_text_intent(parsed_command.message or message), "command_mode": command_mode})
        context_pack = self._build_context_pack(
            session_id=session_id,
            message=parsed_command.message or message,
            state=state,
            target=target,
            sandbox_id=sandbox_id,
            database_profile_id=database_profile_id,
        )
        workflow_decision = self.workflow_engine.decide(parsed_command.message or message, state)
        workflow_response = self._handle_workflow_decision(workflow_decision, context_pack, state)
        if workflow_response is not None:
            return workflow_response

        direct_read_response = self._maybe_direct_read_chat(
            message=parsed_command.message or message,
            session_id=session_id,
            model_profile_id=model_profile_id,
            target=target,
            sandbox_id=sandbox_id,
            database_profile_id=database_profile_id,
            state=state,
        )
        if direct_read_response is not None:
            return direct_read_response

        if command_mode != "execute" and parsed_command.requires_execute:
            return {
                "success": True,
                "answer": DATABASE_COMMAND_REQUIRES_EXECUTE_REPLY,
                "generated_sql": None,
                "check": None,
                "execute": None,
                "safety": {"requires_execute": True, "skill": "command_router"},
            }

        if command_mode == "execute":
            resolved_ctx = self.database_context_skill.resolve(target, sandbox_id, database_profile_id)
            if resolved_ctx.target == "connected_database" and not resolved_ctx.has_real_database:
                return {"success": True, "answer": DATABASE_MISSING_REPLY, "generated_sql": None, "check": None, "execute": None, "safety": None}

            request_text = parsed_command.message or message
            generated = self.generate_sql(
                request_text,
                model_profile_id=model_profile_id,
                target=resolved_ctx.target,
                sandbox_id=resolved_ctx.sandbox_id,
                database_profile_id=resolved_ctx.database_profile_id,
                session_id=session_id,
            )
            sql = generated.get("generated_sql") or ""
            model_output = generated.get("model_output") or {}
            explanation = model_output.get("explanation") or ("SQL draft generated. Review it before running Check Safety." if sql else LLM_UNSTRUCTURED_REPLY)
            if sql:
                try:
                    from Gateway.sql_classifier import classify_sql
                    classification = classify_sql(sql)
                    if classification.is_read_only:
                        context_for_read = self._build_context_pack(
                            session_id=session_id,
                            message=request_text,
                            state=state,
                            target=resolved_ctx.target,
                            sandbox_id=resolved_ctx.sandbox_id,
                            database_profile_id=resolved_ctx.database_profile_id,
                        )
                        return self._direct_read_response_from_sql(sql=sql, context_pack=context_for_read, state=state)
                except Exception:
                    # If read-only classification fails, keep the safer draft-only path.
                    pass
            draft = self.execute_box_skill.set_draft(
                sql=sql,
                explanation=explanation,
                target=generated.get("target") or {
                    "target": resolved_ctx.target,
                    "sandbox_id": resolved_ctx.sandbox_id,
                    "database_profile_id": resolved_ctx.database_profile_id,
                },
                provider_profile_id=(generated.get("profile") or {}).get("profile_id"),
            )
            explain = self.query_explain_skill.explain(sql, generated.get("schema_graph") if isinstance(generated.get("schema_graph"), dict) else None) if sql else {}
            plan, review = ({}, {})
            if sql:
                context_for_draft = self._build_context_pack(
                    session_id=session_id,
                    message=request_text,
                    state=state,
                    target=resolved_ctx.target,
                    sandbox_id=resolved_ctx.sandbox_id,
                    database_profile_id=resolved_ctx.database_profile_id,
                )
                plan, review = self._plan_review_payload(sql=sql, context_pack=context_for_draft, state=state)
                state.remember_sql(sql, intent=str((model_output or {}).get("intent") or "database_task"), safety_class=plan.get("action_class"))
                self._record_tool_call(session_id, state, "execute_box.set_draft", metadata={"draft_only": True, "action_class": plan.get("action_class")})
                self._save_state(session_id, state)

            return {
                "success": True,
                "answer": explanation,
                "generated_sql": sql or None,
                "check": None,
                "execute": {"executed": False, "draft_only": True},
                "execute_box": draft,
                "query_explain": explain,
                "workflow_plan": plan,
                "workflow_review": review,
                "safety": {
                    "workflow": "draft_only",
                    "next_step": "check_safety",
                    "target": (generated.get("target") or {}).get("target"),
                    "provider_profile_id": (generated.get("profile") or {}).get("profile_id"),
                    "blocked": False,
                    "warnings": [] if sql else ["llm_returned_no_sql"],
                    "skills": ["command_router", "database_context", "schema_graph", "text_to_sql", "execute_box"],
                },
                "schema_graph": generated.get("schema_graph"),
                "agent_state": generated.get("agent_state"),
                "context_pack": generated.get("context_pack"),
            }

        if parsed_command.is_database_task:
            return {
                "success": True,
                "answer": DATABASE_COMMAND_REQUIRES_EXECUTE_REPLY,
                "generated_sql": None,
                "check": None,
                "execute": None,
                "safety": {"requires_execute": True, "skill": "command_router"},
            }

        # Non-database chat uses the provider normally, but still does not touch DB runtime.
        profile = self.provider_store.get(model_profile_id, redacted=False) if model_profile_id else self.provider_store.active(redacted=False)
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": message},
        ]
        payload = adapter_for(profile).chat(messages, temperature=0.2)
        raw_content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        answer = self._llm_content_as_text(raw_content).strip() or CLARIFY_REPLY
        return {
            "success": True,
            "answer": answer,
            "generated_sql": None,
            "check": None,
            "execute": None,
            "safety": {"workflow": "chat_only", "skills": ["command_router"]},
        }

