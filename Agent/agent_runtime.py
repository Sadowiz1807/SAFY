from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path
import json
import re

from Gateway.query_orchestrator import QueryOrchestrator
from Gateway.db_drivers.provider_profiles import resolve_database_capability
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
from DomainIntelligence.context_builder import DomainContextBuilder
from DomainIntelligence.schema_workflow import (
    CATALOG_INTENT,
    SCHEMA_INTENT,
    DomainSchemaResolution,
    DomainSchemaWorkflow,
    DomainSchemaWorkflowError,
)
from Core.semantic_action_plan import CREATE_OBJECT, SemanticActionPlan
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
Never replace a requested write, DDL, destructive, permission, or administrative operation with a SELECT.
Generate SQL only after a canonical semantic action plan exists, and keep SQL consistent with that plan.
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


def _context_file_recall_answer(message: str) -> dict[str, Any] | None:
    text = str(message or "")
    lower = text.lower()
    asks_file_recall = any(term in lower for term in ("còn nhớ file", "nhớ file", "remember file", "attached file", "file prompt"))
    if not asks_file_recall:
        return None
    if "USER PROVIDED CONTEXT FILES" not in text:
        return {
            "success": True,
            "answer": "File prompt.md từng có thể đã được upload, nhưng hiện không active trong session này hoặc chưa được gửi kèm request hiện tại.",
            "generated_sql": None,
            "check": None,
            "execute": None,
            "safety": {"workflow": "context_file_recall", "context_file_active": False},
        }

    file_match = re.search(r"File:\s*(.+)", text)
    file_name = (file_match.group(1).strip() if file_match else "file context")
    content_match = re.search(r"Content:\s*(.*?)(?:\nEND USER PROVIDED CONTEXT FILE|\Z)", text, re.S)
    content = (content_match.group(1).strip() if content_match else "")
    summary = " ".join(content.split())[:700]
    answer = f"Mình thấy file `{file_name}` đang được gắn trong session này. Nội dung chính là: {summary}"
    return {
        "success": True,
        "answer": answer,
        "generated_sql": None,
        "check": None,
        "execute": None,
        "safety": {"workflow": "context_file_recall", "context_file_active": True},
    }


def should_auto_execute(*, auto_execute: bool, plan: Any, target: dict[str, Any] | None, consistency: dict[str, Any] | None, capability: dict[str, Any] | None) -> bool:
    if not auto_execute or not plan or not getattr(plan, "is_read", False):
        return False
    if not consistency or not consistency.get("ok"):
        return False
    target = target or {}
    capability = capability or {}
    if not target.get("database_profile_id") or target.get("context_stale"):
        return False
    if capability.get("supports_native_sql") is False and capability.get("supports_simple_rest_select") is False:
        return False
    return True


def system_database_grounding_error(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    profile = profile or {}
    driver = str(profile.get("driver") or profile.get("dbms") or "").strip().lower()
    database = str(profile.get("database") or "").strip()
    if driver in {"sqlserver", "mssql"} and database.lower() in {"master", "model", "msdb", "tempdb"}:
        return {
            "code": "SQLSERVER_SYSTEM_DATABASE_GROUNDING_BLOCKED",
            "message": "Select an application SQL Server database before generating SQL. System databases cannot be used for application grounding.",
            "details": {"driver": driver, "database": database},
        }
    return None


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
        project_root = Path(__file__).resolve().parents[1]
        self.domain_context_builder = DomainContextBuilder(project_root)
        self.domain_schema_workflow = DomainSchemaWorkflow(project_root, self.provider_store)
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
            "create_database",
            {
                "resolve_domain_schema_request": self.domain_schema_workflow.resolve_request,
                "design_domain_schema": self.domain_schema_workflow.design_schema,
                "list_domain_catalog": self.domain_schema_workflow.catalog_dicts,
            },
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
            ("domain.context", "domain", "Route domain packs and retrieve bounded business context for prompt packing.", "META", True, False, False, False),
            ("domain.schema.design", "domain", "Classify a business domain and generate a validated multi-table DDL draft from compiled DomainIntelligence packs.", "WRITE_SQL", False, False, True, True),
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

    def invalidate_all_execution_contexts(self, *, reason: str, clear_context: bool = False) -> dict[str, Any]:
        """Invalidate drafts/checks in memory and persisted chat sessions.

        Profile activation and schema refresh happen outside an individual chat.
        Keeping old check material in any session would allow a stale Execute Box
        to outlive the context it was checked against.
        """
        session_ids: set[str] = {key for key in self._memory_states if key != "__default__"}
        if self.runtime_db and hasattr(self.runtime_db, "list_sessions"):
            try:
                session_ids.update(
                    str(item.get("chat_id"))
                    for item in self.runtime_db.list_sessions(limit=10000)
                    if isinstance(item, dict) and item.get("chat_id")
                )
            except Exception:
                pass

        invalidated = 0
        for session_id in sorted(session_ids):
            try:
                state = self._load_state(session_id)
                state.invalidate_bound_context(clear_context=clear_context)
                self._save_state(session_id, state)
                invalidated += 1
            except Exception:
                continue

        if "__default__" in self._memory_states:
            state = AgentWorkflowState.from_dict(self._memory_states.get("__default__"))
            state.invalidate_bound_context(clear_context=clear_context)
            self._memory_states["__default__"] = state.to_dict()
            invalidated += 1

        return {
            "invalidated_sessions": invalidated,
            "reason": str(reason or "context_changed"),
            "context_cleared": bool(clear_context),
        }

    def _schema_generation_for_context(self, target: str | None, sandbox_id: str | None, database_profile_id: str | None) -> str | None:
        schema = self._schema_for(target or "", sandbox_id, database_profile_id)
        if not isinstance(schema, dict):
            return None
        graph = schema.get("schema_graph") if isinstance(schema.get("schema_graph"), dict) else schema
        return str(
            graph.get("schema_hash")
            or graph.get("updated_at")
            or graph.get("generated_at")
            or ""
        ) or None

    @staticmethod
    def _semantic_block_next_step(code: str | None, policy_blocked: bool = False) -> str:
        normalized = str(code or "").upper()
        if policy_blocked or normalized in {"DESTRUCTIVE_SQL_BLOCKED", "SEMANTIC_PLAN_POLICY_BLOCKED"}:
            return "review_policy"
        if normalized in {"SCHEMA_REQUIRED", "SCHEMA_TARGET_NOT_FOUND", "INTENT_SQL_TARGET_UNRESOLVED"}:
            return "refresh_schema"
        if normalized in {"SEMANTIC_PLAN_INCOHERENT", "AMBIGUOUS_INTENT", "SEMANTIC_PLAN_BLOCKED"}:
            return "clarify_intent"
        if normalized in {"CAPABILITY_UNSUPPORTED", "SEMANTIC_PLAN_CAPABILITY_UNSUPPORTED"}:
            return "change_database_capability"
        if normalized == "SQLSERVER_SYSTEM_DATABASE_GROUNDING_BLOCKED":
            return "select_application_database"
        if normalized in {"DIALECT_MISMATCH", "INTENT_SQL_MISMATCH", "INTENT_SQL_TARGET_MISMATCH", "INTENT_SQL_TARGET_SET_MISMATCH", "SQL_GENERATION_FAILED"}:
            return "regenerate_sql"
        if normalized in {"CONTEXT_STALE", "QUERY_CHECK_CONTEXT_STALE", "PROFILE_MISMATCH", "QUERY_CHECK_PROFILE_MISMATCH", "TARGET_MISMATCH", "QUERY_CHECK_TARGET_MISMATCH"}:
            return "run_check_safety_again"
        if normalized in {"SCHEMA_GENERATION_STALE", "QUERY_CHECK_SCHEMA_STALE"}:
            return "refresh_schema"
        if normalized in {"RPC_NOT_CONFIGURED", "SUPABASE_READ_RPC_NOT_CONFIGURED", "SUPABASE_WRITE_RPC_NOT_CONFIGURED"}:
            return "configure_rpc"
        if normalized in {"RPC_FAILED", "SUPABASE_READ_RPC_FAILED", "SUPABASE_WRITE_RPC_FAILED"}:
            return "review_rpc_error"
        if normalized in {"SANDBOX_NOT_READY", "SANDBOX_SCHEMA_NOT_READY", "SANDBOX_VALIDATION_NOT_READY"}:
            return "prepare_sandbox"
        return "review_error"

    def _build_context_pack(self, *, session_id: str | None, message: str, state: AgentWorkflowState, target: str | None, sandbox_id: str | None, database_profile_id: str | None) -> ContextPack:
        resolved_ctx = self.database_context_skill.resolve(target, sandbox_id, database_profile_id)
        schema_text = self._schema_context_text(resolved_ctx.target, resolved_ctx.sandbox_id, resolved_ctx.database_profile_id)
        domain_context_payload = None
        try:
            db_type = None
            if resolved_ctx.database_profile:
                db_type = resolved_ctx.database_profile.get("driver") or resolved_ctx.database_profile.get("dbms")
            domain_context = self.domain_context_builder.build(
                question=message,
                schema_summary=schema_text,
                database_profile_id=resolved_ctx.database_profile_id,
                database_type=db_type,
            )
            domain_context_payload = domain_context.to_dict()
            domain_context_payload["prompt_text"] = domain_context.to_prompt_text()
        except Exception as exc:
            domain_context_payload = {"warnings": [f"domain_context_error:{type(exc).__name__}"]}
        database_name = None
        if isinstance(domain_context_payload, dict):
            self._record_workflow_event(
                session_id,
                state,
                "domain_context",
                status="ok" if domain_context_payload.get("domain_id") else "none",
                metadata={
                    "domain_id": domain_context_payload.get("domain_id"),
                    "domain_pack_version": domain_context_payload.get("domain_pack_version"),
                    "router_confidence": domain_context_payload.get("router_confidence"),
                    "retrieved_doc_ids": domain_context_payload.get("retrieved_doc_ids", []),
                    "warnings": domain_context_payload.get("warnings", []),
                },
            )
        if resolved_ctx.database_profile:
            database_name = str(resolved_ctx.database_profile.get("database") or resolved_ctx.database_profile.get("display_name") or "") or None
        profile = resolved_ctx.database_profile or {}
        driver = profile.get("driver") or profile.get("dbms")
        dialect = profile.get("dialect") or driver
        schema_generation = self._schema_generation_for_context(
            resolved_ctx.target,
            resolved_ctx.sandbox_id,
            resolved_ctx.database_profile_id,
        )
        state.transition_context(
            target=resolved_ctx.target,
            sandbox_id=resolved_ctx.sandbox_id,
            database_profile_id=resolved_ctx.database_profile_id,
            database_name=database_name,
            driver=str(driver or "") or None,
            dialect=str(dialect or "") or None,
            schema_generation=schema_generation,
        )
        return ContextPack(
            session_id=session_id,
            user_message=message,
            target=resolved_ctx.target,
            sandbox_id=resolved_ctx.sandbox_id,
            database_profile_id=resolved_ctx.database_profile_id,
            database_profile=resolved_ctx.database_profile,
            schema_summary=schema_text,
            domain_context=domain_context_payload,
            state=state,
            available_skills=self.skill_registry.active_names(),
        )

    def _target_from_context_pack(self, context_pack: ContextPack) -> dict[str, Any]:
        profile = context_pack.database_profile or {}
        return {
            "target": context_pack.target,
            "sandbox_id": context_pack.sandbox_id,
            "database_profile_id": context_pack.database_profile_id,
            "database_type": profile.get("database_type") or profile.get("driver") or profile.get("dbms"),
            "context_generation": context_pack.state.context_generation,
            "schema_generation": context_pack.state.schema_generation,
            "driver": profile.get("driver") or profile.get("dbms") or context_pack.state.current_driver,
            "dialect": profile.get("dialect") or profile.get("driver") or profile.get("dbms") or context_pack.state.current_dialect,
        }

    def _record_workflow_event(self, session_id: str | None, state: AgentWorkflowState, stage: str, status: str = "ok", metadata: dict[str, Any] | None = None) -> None:
        event = {"stage": stage, "status": status, "metadata": metadata or {}}
        state.workflow_history.append(event)
        state.workflow_history = state.workflow_history[-20:]
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

    def _refresh_checked_database_profile(self, check_id: str | None, database_profile_id: str | None) -> bool:
        """Reload the materialized profile immediately before driver execution.

        Test Connection, schema loading, Execute Box, and direct chat reads must all
        resolve the same current env-backed secret. The safety check stays bound to
        the same profile id; only its runtime credential snapshot is refreshed.
        """
        if not check_id or not database_profile_id or not self.database_profile_loader:
            return False
        check_record = self.query_orchestrator.checks.get(check_id)
        if not check_record or check_record.get("database_profile_id") != database_profile_id:
            return False
        try:
            profile = self.database_profile_loader(database_profile_id)
        except Exception:
            return False
        if not profile:
            return False
        check_record["database_profile"] = profile
        check_record["real_db_mode"] = True
        return True

    def _ensure_direct_read_limit(
        self,
        sql: str,
        limit: int = 100,
        database_profile: dict[str, Any] | None = None,
    ) -> str:
        """Apply a bounded preview using the selected database dialect.

        SQL Server uses TOP, Oracle uses FETCH FIRST, and PostgreSQL/MySQL/SQLite
        use LIMIT. A model-generated trailing LIMIT is converted for SQL Server
        and Oracle rather than being passed to the driver as invalid SQL.
        """
        text = (sql or "").strip()
        if not text:
            return text
        if not re.match(r"^(SELECT|WITH)\b", text, re.I):
            return text

        requested_limit = max(1, min(int(limit or 100), 1000))
        had_semicolon = text.endswith(";")
        body = text[:-1].rstrip() if had_semicolon else text.rstrip()
        trailing_limit = re.search(r"\s+LIMIT\s+(\d+)\s*$", body, re.I)
        if trailing_limit:
            requested_limit = min(requested_limit, max(1, int(trailing_limit.group(1))))
            body = body[: trailing_limit.start()].rstrip()

        profile = database_profile or {}
        driver = str(profile.get("driver") or profile.get("dbms") or profile.get("database_type") or "").strip().lower()
        if driver == "postgres":
            driver = "postgresql"

        if driver == "sqlserver":
            # Existing SQL Server pagination/limit syntax remains authoritative.
            if re.search(r"\bOFFSET\s+\d+\s+ROWS\b", body, re.I) or re.search(
                r"\bFETCH\s+(?:FIRST|NEXT)\s+\d+\s+ROWS\s+ONLY\b", body, re.I
            ):
                return body + (";" if had_semicolon else "")

            select_match = re.match(r"^(\s*SELECT\s+)(DISTINCT\s+)?", body, re.I)
            if not select_match and re.match(r"^\s*WITH\b", body, re.I):
                # For a CTE, use the final top-level SELECT in the common
                # `WITH ... ) SELECT ...` shape.
                matches = list(re.finditer(r"\)\s*(SELECT\s+)(DISTINCT\s+)?", body, re.I))
                if matches:
                    match = matches[-1]
                    select_start = match.start(1)
                    select_match = re.match(r"(SELECT\s+)(DISTINCT\s+)?", body[select_start:], re.I)
                    if select_match:
                        prefix = body[:select_start]
                        suffix = body[select_start:]
                        if re.match(r"^SELECT\s+(?:DISTINCT\s+)?TOP\s*(?:\(|\d)", suffix, re.I):
                            return body + (";" if had_semicolon else "")
                        distinct = select_match.group(2) or ""
                        suffix = select_match.group(1) + distinct + f"TOP ({requested_limit}) " + suffix[select_match.end():]
                        body = prefix + suffix
                        return body + ";"

            if select_match:
                if re.match(r"^\s*SELECT\s+(?:DISTINCT\s+)?TOP\s*(?:\(|\d)", body, re.I):
                    return body + (";" if had_semicolon else "")
                distinct = select_match.group(2) or ""
                body = select_match.group(1) + distinct + f"TOP ({requested_limit}) " + body[select_match.end():]
            return body + ";"

        if driver == "oracle":
            if re.search(r"\bFETCH\s+(?:FIRST|NEXT)\s+\d+\s+ROWS\s+ONLY\b", body, re.I):
                return body + (";" if had_semicolon else "")
            return body + f" FETCH FIRST {requested_limit} ROWS ONLY;"

        # PostgreSQL, MySQL/MariaDB, SQLite, Supabase/PostgREST SQL RPC, and
        # unknown SQL-like profiles use LIMIT for bounded direct reads.
        return body + f" LIMIT {requested_limit};"

    def _direct_read_response_from_sql(self, *, sql: str, context_pack: ContextPack, state: AgentWorkflowState) -> dict[str, Any]:
        if context_pack.target == "connected_database" and context_pack.database_profile_id:
            fresh_profile = self._database_profile_for_runtime(context_pack.database_profile_id)
            if fresh_profile:
                context_pack.database_profile = fresh_profile
        sql = self._ensure_direct_read_limit(sql, limit=100, database_profile=context_pack.database_profile)
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
        check_id = check.get("check_id") or ""
        self._refresh_checked_database_profile(check_id, context_pack.database_profile_id)
        ok, result = self.execute_query_skill.execute_checked(
            check_id=check_id,
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


    def _maybe_schema_summary_answer(self, message: str, context_pack: ContextPack) -> dict[str, Any] | None:
        lower = str(message or "").lower()
        asks_table_count = any(term in lower for term in (
            "bao nhiêu bảng", "bao nhieu bang", "có mấy bảng", "co may bang",
            "kiểm tra database", "kiem tra database", "liệt kê bảng", "liet ke bang", "show tables"
        ))
        if not asks_table_count:
            return None
        graph = None
        try:
            graph = self.schema_graph_loader(context_pack.database_profile_id) if self.schema_graph_loader and context_pack.database_profile_id else None
        except Exception:
            graph = None
        if not graph or graph.get("status") not in {"ready", "partial"}:
            return None
        tables = graph.get("tables") or []
        table_names = [str(t.get("name") or t.get("key") or "") for t in tables if t]
        answer = f"Database hiện tại có {len(table_names)} bảng trong Schema Graph."
        if table_names:
            answer += " Các bảng gồm: " + ", ".join(table_names[:30]) + ("..." if len(table_names) > 30 else "")
        return {
            "success": True,
            "answer": answer,
            "generated_sql": None,
            "check": None,
            "execute": {"executed": False, "read_only": True},
            "safety": {"workflow": "schema_graph_summary", "blocked": False, "skills": ["schema_graph"]},
            "schema_graph": {"table_count": len(table_names), "tables": table_names[:50]},
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
        auto_execute: bool,
    ) -> dict[str, Any] | None:
        """Allow natural-language read-only database questions without requiring /Execute.

        Write/DDL still goes through the draft-only Execute Box path. This helper is
        intentionally conservative: it only direct-runs SQL if the generated draft is
        classified read-only. Otherwise it returns None so the normal safety path can
        handle it.
        """
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
        action_plan = generated.get("action_plan") or {}
        consistency = generated.get("consistency") or {}
        operation = str(action_plan.get("operation") or "UNKNOWN").upper()
        sql = generated.get("generated_sql") or ""

        if generated.get("policy_blocked"):
            code = str(generated.get("reason") or consistency.get("code") or "POLICY_BLOCKED")
            return {
                "success": True,
                "answer": generated.get("answer") or "This operation is blocked by SAFY policy.",
                "generated_sql": None,
                "check": None,
                "execute": {"executed": False, "blocked": True, "executable": False},
                "execute_box": {
                    "draft_ready": False,
                    "sql": "",
                    "policy_blocked": True,
                    "executable": False,
                    "check_allowed": False,
                },
                "action_plan": action_plan,
                "consistency": consistency,
                "safety": {
                    "workflow": "policy_blocked",
                    "next_step": self._semantic_block_next_step(code, policy_blocked=True),
                    "blocked": True,
                    "policy_blocked": True,
                    "executable": False,
                    "check_allowed": False,
                    "warnings": [code],
                    "skills": ["semantic_action_planner", "text_to_sql", "policy"],
                },
            }
        block_code = str(generated.get("reason") or consistency.get("code") or "")
        if generated.get("blocked") and block_code == "SQLSERVER_SYSTEM_DATABASE_GROUNDING_BLOCKED":
            return {
                "success": True,
                "answer": generated.get("answer") or "Select an application database before generating SQL.",
                "generated_sql": None,
                "check": None,
                "execute": {"executed": False, "blocked": True, "executable": False},
                "execute_box": {"draft_ready": False, "sql": "", "executable": False, "check_allowed": False},
                "action_plan": action_plan,
                "consistency": consistency,
                "safety": {
                    "workflow": "database_grounding_blocked",
                    "next_step": self._semantic_block_next_step(block_code),
                    "blocked": True,
                    "executable": False,
                    "check_allowed": False,
                    "warnings": [block_code],
                    "skills": ["database_context", "schema_graph", "policy"],
                },
            }
        if operation in {"CHAT", "UNKNOWN"}:
            return None
        if operation != "READ":
            if sql and consistency.get("ok"):
                context_for_draft = self._build_context_pack(
                    session_id=session_id,
                    message=message,
                    state=state,
                    target=resolved_ctx.target,
                    sandbox_id=resolved_ctx.sandbox_id,
                    database_profile_id=resolved_ctx.database_profile_id,
                )
                return self._draft_response_from_sql(
                    sql=sql,
                    answer=WRITE_OPERATION_BLOCKED_REPLY,
                    context_pack=context_for_draft,
                    state=state,
                    extra_safety={
                        "workflow": "natural_write_draft",
                        "requires_execute": True,
                        "next_step": "check_safety",
                        "skills": ["semantic_action_planner", "text_to_sql", "execute_box"],
                    },
                )
            return {
                "success": True,
                "answer": WRITE_OPERATION_BLOCKED_REPLY,
                "generated_sql": None,
                "check": None,
                "execute": {"executed": False, "requires_execute_box": True},
                "execute_box": {"draft_ready": False, "sql": "", "executable": False, "check_allowed": False},
                "action_plan": action_plan,
                "consistency": consistency,
                "safety": {
                    "workflow": "semantic_write_requires_execute",
                    "blocked": True,
                    "requires_execute": True,
                    "skills": ["semantic_action_planner", "text_to_sql"],
                },
            }
        if not sql or not consistency.get("ok"):
            return {
                "success": True,
                "answer": generated.get("answer") or "Semantic read plan did not produce safe matching SQL.",
                "generated_sql": None,
                "check": None,
                "execute": {"executed": False, "blocked": True},
                "action_plan": action_plan,
                "consistency": consistency,
                "safety": {
                    "workflow": "semantic_plan_blocked",
                    "next_step": self._semantic_block_next_step(str(generated.get("reason") or consistency.get("code") or "SEMANTIC_PLAN_BLOCKED")),
                    "blocked": True,
                    "warnings": [str(generated.get("reason") or consistency.get("code") or "SEMANTIC_PLAN_BLOCKED")],
                    "skills": ["semantic_action_planner", "text_to_sql", "intent_sql_consistency_guard"],
                },
            }
        try:
            from Gateway.sql_classifier import classify_sql
            classification = classify_sql(sql)
            if not classification.is_read_only:
                return {
                    "success": True,
                    "answer": "Semantic READ plan produced non-read SQL. SAFY blocked execution.",
                    "generated_sql": None,
                    "check": None,
                    "execute": {"executed": False, "blocked": True},
                    "action_plan": action_plan,
                    "consistency": {**consistency, "ok": False, "code": "READ_PLAN_PRODUCED_MUTATION"},
                    "safety": {"workflow": "intent_sql_mismatch", "blocked": True},
                }
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
        from Core.semantic_action_plan import SemanticActionPlan

        plan_obj = SemanticActionPlan.from_payload(action_plan, source="runtime")
        profile = context_for_read.database_profile or {}
        driver = str(profile.get("driver") or profile.get("dbms") or "").lower()
        capability = {
            "supports_native_sql": driver not in {"supabase_rpc", "supabase_rest"},
            "supports_simple_rest_select": driver in {"supabase_rpc", "supabase_rest"},
        }
        target_payload = self._target_from_context_pack(context_for_read)
        if not should_auto_execute(
            auto_execute=auto_execute,
            plan=plan_obj,
            target=target_payload,
            consistency=consistency,
            capability=capability,
        ):
            return self._draft_response_from_sql(
                sql=sql,
                answer="Read-only SQL draft generated. Auto-run read-only is disabled; review it before running Check Safety.",
                context_pack=context_for_read,
                state=state,
                extra_safety={
                    "workflow": "auto_execute_disabled",
                    "auto_execute": False,
                    "next_step": "check_safety",
                },
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

    def _domain_schema_blocked_response(
        self,
        *,
        code: str,
        message: str,
        state: AgentWorkflowState,
        session_id: str | None,
        resolution: DomainSchemaResolution | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state.invalidate_execution_context()
        self._save_state(session_id, state)
        return {
            "success": True,
            "answer": message,
            "generated_sql": None,
            "check": None,
            "execute": {"executed": False, "blocked": True, "executable": False},
            "execute_box": {
                "draft_ready": False,
                "sql": "",
                "summary": message,
                "policy_blocked": False,
                "executable": False,
                "check_allowed": False,
            },
            "domain_schema": {
                "status": "blocked",
                "resolution": resolution.to_dict() if resolution else None,
                "details": details or {},
            },
            "safety": {
                "workflow": "domain_schema_blocked",
                "blocked": True,
                "executable": False,
                "check_allowed": False,
                "next_step": self._semantic_block_next_step(code),
                "warnings": [code],
                "skills": ["create_database", "domain_intelligence"],
            },
            "agent_state": state.to_dict(),
        }

    def _domain_schema_failed_response(
        self,
        *,
        code: str,
        message: str,
        state: AgentWorkflowState,
        session_id: str | None,
        resolution: DomainSchemaResolution | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = True,
    ) -> dict[str, Any]:
        state.invalidate_execution_context()
        state.last_user_intent = SCHEMA_INTENT
        state.last_intent = SCHEMA_INTENT
        state.last_error = {"code": code, "message": "Domain schema generation failed safely."}
        state.last_task_summary = "Domain schema generation failed before producing executable SQL."
        self._record_workflow_event(
            session_id,
            state,
            "domain_schema_generation_failed",
            status="failed",
            metadata={"code": code, "retryable": retryable, "details": details or {}},
        )
        self._save_state(session_id, state)
        return {
            "success": False,
            "answer": "SAFY không tạo được schema an toàn ở bước thiết kế. SQL cũ đã bị vô hiệu hóa; bạn có thể thử lại hoặc đổi model profile.",
            "generated_sql": None,
            "check": None,
            "execute": {"executed": False, "blocked": False, "executable": False},
            "execute_box": {
                "draft_ready": False,
                "sql": "",
                "summary": "Schema generation failed safely.",
                "policy_blocked": False,
                "executable": False,
                "check_allowed": False,
            },
            "domain_schema": {
                "status": "failed",
                "resolution": resolution.to_dict() if resolution else None,
                "details": details or {},
            },
            "safety": {
                "workflow": "domain_schema_failed",
                "blocked": False,
                "executable": False,
                "check_allowed": False,
                "next_step": "retry_schema_design",
                "warnings": [code],
                "skills": ["create_database", "domain_intelligence"],
            },
            "error": {
                "code": code,
                "stage": "schema_design",
                "retryable": retryable,
                "message": "Domain schema generation failed safely.",
                "details": details or {},
            },
            "agent_state": state.to_dict(),
        }

    def _domain_schema_clarification_response(
        self,
        *,
        resolution: DomainSchemaResolution,
        request_text: str,
        command_mode: str,
        model_profile_id: str | None,
        state: AgentWorkflowState,
        session_id: str | None,
    ) -> dict[str, Any]:
        state.invalidate_execution_context()
        state.set_pending(
            skill="create_database",
            action="select_domain",
            required_slots=["domain_id"],
            filled_slots={
                "original_request": request_text,
                "origin_command_mode": command_mode,
                "candidates": list(resolution.candidates or []),
                "model_profile_id": model_profile_id,
            },
        )
        self._record_workflow_event(
            session_id,
            state,
            "domain_schema_clarification",
            status="waiting",
            metadata={"candidates": resolution.candidates, "confidence": resolution.confidence},
        )
        self._save_state(session_id, state)
        answer = self.domain_schema_workflow.clarification_question(resolution.candidates)
        return {
            "success": True,
            "answer": answer,
            "generated_sql": None,
            "check": None,
            "execute": None,
            "execute_box": {
                "draft_ready": False,
                "sql": "",
                "summary": answer,
                "executable": False,
                "check_allowed": False,
            },
            "domain_schema": {"status": "clarification_required", "resolution": resolution.to_dict()},
            "safety": {
                "workflow": "domain_schema_clarification",
                "blocked": False,
                "requires_clarification": True,
                "next_step": "select_domain",
                "skills": ["create_database", "domain_intelligence"],
            },
            "agent_state": state.to_dict(),
        }

    def _domain_schema_preview_response(
        self,
        *,
        resolution: DomainSchemaResolution,
        request_text: str,
        state: AgentWorkflowState,
        session_id: str | None,
    ) -> dict[str, Any]:
        preview = self.domain_schema_workflow.preview(resolution.domain_id or "")
        state.invalidate_execution_context()
        state.clear_pending()
        state.last_user_intent = SCHEMA_INTENT
        state.last_intent = SCHEMA_INTENT
        self._save_state(session_id, state)
        entities = ", ".join(preview.get("entities") or []) or "the compiled domain entities"
        answer = (
            f"SAFY nhận diện yêu cầu thiết kế schema thuộc domain {preview['domain_name']} "
            f"(`{preview['domain_id']}`). Các thực thể tiêu biểu: {entities}. "
            "Đây là bước xem trước; SAFY chưa tạo hoặc thực thi SQL. "
            "Dùng `/Execute` với yêu cầu này để tạo DDL nhiều bảng trong Execute Box. "
            "Sau đó bạn review, chạy Check Safety trong sandbox và chỉ khi sandbox pass mới có thể Execute lên database đã kết nối."
        )
        return {
            "success": True,
            "answer": answer,
            "generated_sql": None,
            "check": None,
            "execute": None,
            "execute_box": {
                "draft_ready": False,
                "sql": "",
                "summary": answer,
                "executable": False,
                "check_allowed": False,
            },
            "domain_schema": {
                "status": "preview",
                "request": request_text,
                "resolution": resolution.to_dict(),
                "preview": preview,
            },
            "safety": {
                "workflow": "domain_schema_preview",
                "blocked": False,
                "auto_executed": False,
                "next_step": "use_execute_command",
                "skills": ["create_database", "domain_intelligence"],
            },
            "agent_state": state.to_dict(),
        }

    def _domain_schema_draft_response(
        self,
        *,
        resolution: DomainSchemaResolution,
        request_text: str,
        model_profile_id: str | None,
        target: str | None,
        sandbox_id: str | None,
        database_profile_id: str | None,
        state: AgentWorkflowState,
        session_id: str | None,
    ) -> dict[str, Any]:
        resolved_ctx = self.database_context_skill.resolve(target, sandbox_id, database_profile_id)
        if resolved_ctx.target != "connected_database" or not resolved_ctx.has_real_database or not resolved_ctx.database_profile_id:
            return self._domain_schema_blocked_response(
                code="DATABASE_PROFILE_REQUIRED_FOR_SCHEMA_DESIGN",
                message="Hãy Save, Test và activate một database profile thật trước khi tạo DDL. SAFY cần DBMS/dialect đích để sinh schema đúng cú pháp; hệ thống sẽ không tự chạy CREATE DATABASE cấp server.",
                state=state,
                session_id=session_id,
                resolution=resolution,
            )
        grounding_error = system_database_grounding_error(resolved_ctx.database_profile)
        if grounding_error:
            return self._domain_schema_blocked_response(
                code=grounding_error["code"],
                message=grounding_error["message"],
                state=state,
                session_id=session_id,
                resolution=resolution,
                details=grounding_error.get("details"),
            )

        profile = resolved_ctx.database_profile or {}
        capability = resolve_database_capability(profile)
        dialect = str(profile.get("dialect") or capability.dialect).strip()
        schema_generation = self._schema_generation_for_context(
            resolved_ctx.target,
            resolved_ctx.sandbox_id,
            resolved_ctx.database_profile_id,
        )
        try:
            state.transition_context(
                target="connected_database",
                database_profile_id=resolved_ctx.database_profile_id,
                database_name=profile.get("database"),
                driver=capability.driver,
                dialect=dialect,
                schema_generation=schema_generation,
            )
            design = self.domain_schema_workflow.design_schema(
                request=request_text,
                domain_id=resolution.domain_id or "",
                dialect=dialect,
                model_profile_id=model_profile_id,
            )
        except DomainSchemaWorkflowError as exc:
            runtime_failure = exc.code in {
                "DOMAIN_SCHEMA_MODEL_FAILED",
                "MODEL_TIMEOUT",
                "MODEL_PROFILE_REQUIRED",
                "MODEL_JSON_INVALID",
                "DOMAIN_SCHEMA_DDL_INVALID",
                "DOMAIN_SCHEMA_DDL_EMPTY",
                "DOMAIN_SCHEMA_DOMAIN_MISMATCH",
                "DOMAIN_SCHEMA_DIALECT_MISMATCH",
            }
            if runtime_failure:
                return self._domain_schema_failed_response(
                    code="DOMAIN_SCHEMA_GENERATION_FAILED" if exc.code != "MODEL_TIMEOUT" else "MODEL_TIMEOUT",
                    message=str(exc),
                    state=state,
                    session_id=session_id,
                    resolution=resolution,
                    details={"source_code": exc.code, **(exc.details or {})},
                    retryable=exc.code not in {"MODEL_PROFILE_REQUIRED"},
                )
            return self._domain_schema_blocked_response(
                code=exc.code,
                message=str(exc),
                state=state,
                session_id=session_id,
                resolution=resolution,
                details=exc.details,
            )

        context_pack = self._build_context_pack(
            session_id=session_id,
            message=request_text,
            state=state,
            target="connected_database",
            sandbox_id=None,
            database_profile_id=resolved_ctx.database_profile_id,
        )
        target_payload = self._target_from_context_pack(context_pack)
        explanation = (
            f"Đã tạo DDL nhiều bảng cho domain {design.domain_name} ({design.dialect}). "
            f"Batch gồm {len(design.statements)} câu lệnh và {len(design.table_names)} target. "
            "SAFY chưa thực thi. Hãy review SQL, chạy Check Safety; Check Safety sẽ kiểm tra batch trong sandbox và chỉ khi pass bạn mới có thể bấm Execute lên database thật."
        )
        draft = self.execute_box_skill.set_draft(
            sql=design.sql,
            explanation=explanation,
            target=target_payload,
            provider_profile_id=design.model_profile_id,
        )
        draft.update(
            {
                "statement_count": len(design.statements),
                "domain_id": design.domain_id,
                "domain_name": design.domain_name,
                "dialect": design.dialect,
                "executable": True,
                "check_allowed": True,
                "sandbox_required": True,
                "server_level_create_database": False,
            }
        )
        semantic_plan = SemanticActionPlan(
            operation=CREATE_OBJECT,
            scope="MULTIPLE_OBJECTS",
            object_type="TABLE",
            targets=list(design.table_names),
            data_effect="NONE",
            schema_effect="SCHEMA_WRITE",
            requires_schema=False,
            requires_confirmation=True,
            confidence=1.0,
            rationale=f"Validated multi-table DDL from compiled DomainIntelligence pack {design.domain_id}.",
            source="domain_schema_workflow",
            warnings=list(design.warnings),
        )
        consistency = {
            "ok": True,
            "code": "DOMAIN_SCHEMA_BATCH_VALIDATED",
            "message": "Every generated statement was restricted to CREATE TABLE or CREATE INDEX and has an extractable target.",
            "statement_count": len(design.statements),
            "targets": list(design.table_names),
        }
        plan, review = self._plan_review_payload(sql=design.sql, context_pack=context_pack, state=state)
        state.clear_pending()
        state.remember_sql(design.sql, intent=SCHEMA_INTENT, safety_class=plan.get("action_class"))
        self._record_tool_call(
            session_id,
            state,
            "domain.schema.design",
            status="ok",
            risk_class=plan.get("action_class"),
            metadata={
                "domain_id": design.domain_id,
                "dialect": design.dialect,
                "statement_count": len(design.statements),
                "table_count": len(design.table_names),
            },
        )
        self._save_state(session_id, state)
        return {
            "success": True,
            "answer": explanation,
            "generated_sql": design.sql,
            "check": None,
            "execute": {"executed": False, "draft_only": True, "sandbox_required": True, "executable": False},
            "execute_box": draft,
            "action_plan": semantic_plan.to_dict(),
            "consistency": consistency,
            "workflow_plan": plan,
            "workflow_review": review,
            "domain_schema": {"status": "drafted", "resolution": resolution.to_dict(), "design": design.to_dict()},
            "safety": {
                "workflow": "domain_schema_draft",
                "next_step": "check_safety",
                "target": "connected_database",
                "blocked": False,
                "auto_executed": False,
                "sandbox_required": True,
                "server_level_create_database": False,
                "warnings": list(design.warnings),
                "skills": ["create_database", "domain_intelligence", "execute_box", "query_guard"],
            },
            "agent_state": state.to_dict(),
            "context_pack": context_pack.to_dict(),
        }

    def _handle_domain_schema_request(
        self,
        *,
        message: str,
        command_mode: str,
        session_id: str | None,
        model_profile_id: str | None,
        target: str | None,
        sandbox_id: str | None,
        database_profile_id: str | None,
        state: AgentWorkflowState,
    ) -> dict[str, Any] | None:
        pending = state.pending_skill == "create_database" and state.pending_action == "select_domain"
        slots = dict(state.filled_slots or {}) if pending else {}
        request_text = str(slots.get("original_request") or message).strip()
        effective_mode = str(slots.get("origin_command_mode") or command_mode or "chat").strip().lower()
        effective_model_profile_id = model_profile_id or slots.get("model_profile_id")
        candidates = slots.get("candidates") if isinstance(slots.get("candidates"), list) else None

        resolution = self.domain_schema_workflow.resolve_request(
            message,
            model_profile_id=effective_model_profile_id,
            pending_candidates=candidates,
            original_request=request_text if pending else None,
        )
        if not resolution.relevant:
            return None
        if resolution.intent == CATALOG_INTENT:
            state.invalidate_execution_context()
            state.clear_pending()
            self._save_state(session_id, state)
            catalog_answer = self.domain_schema_workflow.catalog_answer()
            return {
                "success": True,
                "answer": catalog_answer,
                "generated_sql": None,
                "check": None,
                "execute": None,
                "execute_box": {
                    "draft_ready": False,
                    "sql": "",
                    "summary": catalog_answer,
                    "executable": False,
                    "check_allowed": False,
                },
                "domain_schema": {"status": "catalog", "catalog": self.domain_schema_workflow.catalog_dicts()},
                "safety": {"workflow": "domain_schema_catalog", "blocked": False, "skills": ["create_database", "domain_intelligence"]},
                "agent_state": state.to_dict(),
            }
        if resolution.decision == "blocked":
            return self._domain_schema_blocked_response(
                code="DOMAIN_SCHEMA_WORKFLOW_UNAVAILABLE",
                message=resolution.rationale or "Domain schema workflow is unavailable.",
                state=state,
                session_id=session_id,
                resolution=resolution,
            )
        if resolution.decision != "selected" or not resolution.domain_id:
            return self._domain_schema_clarification_response(
                resolution=resolution,
                request_text=request_text,
                command_mode=effective_mode,
                model_profile_id=effective_model_profile_id,
                state=state,
                session_id=session_id,
            )
        if effective_mode != "execute":
            return self._domain_schema_preview_response(
                resolution=resolution,
                request_text=request_text,
                state=state,
                session_id=session_id,
            )
        return self._domain_schema_draft_response(
            resolution=resolution,
            request_text=request_text,
            model_profile_id=effective_model_profile_id,
            target=target,
            sandbox_id=sandbox_id,
            database_profile_id=database_profile_id,
            state=state,
            session_id=session_id,
        )

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

    def _is_identity_question(self, message: str) -> bool:
        text = (message or '').strip().lower()
        return text in {'bạn là ai', 'ban la ai', 'safy là ai', 'safy la ai', 'who are you', 'what are you'}

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
        grounding_error = system_database_grounding_error(context_pack.database_profile)
        if grounding_error:
            state.invalidate_execution_context()
            self._save_state(session_id, state)
            return {
                "generated_sql": "",
                "answer": grounding_error["message"],
                "model_output": {
                    "intent": "UNKNOWN",
                    "sql": "",
                    "explanation": grounding_error["message"],
                    "target_hint": context_pack.target,
                    "requires_confirmation": False,
                    "blocked": True,
                },
                "action_plan": {
                    "operation": "UNKNOWN",
                    "scope": "UNKNOWN",
                    "object_type": "UNKNOWN",
                    "targets": [],
                    "confidence": 1.0,
                    "rationale": grounding_error["message"],
                    "warnings": [grounding_error["code"]],
                },
                "consistency": {
                    "ok": False,
                    "code": grounding_error["code"],
                    "message": grounding_error["message"],
                    "statement_type": None,
                    "expected_statement_types": [],
                },
                "target": target_payload,
                "schema_graph": {"status": "blocked", "schema_hash": None, "subset_used": False},
                "context_pack": context_pack.to_dict(),
                "agent_state": state.to_dict(),
                "blocked": True,
                "policy_blocked": False,
                "executable": False,
                "check_allowed": False,
                "execute_allowed": False,
                "reason": grounding_error["code"],
                "check_id": None,
                "sql_hash": None,
            }
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
            # Full graph is retained for deterministic ALL_TABLES planning;
            # the bounded subset remains the only schema text sent to the model.
            schema_graph=graph,
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
        if self._is_identity_question(message):
            return {
                "success": True,
                "answer": "Tôi là Safy, AI Database Agent cục bộ giúp bạn thiết kế schema, viết/truy vấn SQL an toàn, kiểm tra trong sandbox và chỉ execute lên database thật khi bạn xác nhận.",
                "generated_sql": None,
                "check": None,
                "execute": None,
                "execute_box": {"draft_ready": False, "sql": "", "executable": False, "check_allowed": False},
                "safety": {"workflow": "identity", "blocked": False},
            }

        recall_response = _context_file_recall_answer(parsed_command.message or message)
        if recall_response is not None:
            return recall_response

        state = self._load_state(session_id)
        request_message = parsed_command.message or message
        self._record_workflow_event(session_id, state, "perceive", metadata={"text_intent": classify_text_intent(request_message), "command_mode": command_mode})
        # Skip domain_schema_request for execution-level SQL commands
        # e.g., "create table", "insert into" — these are not domain design requests
        domain_schema_response = None
        if not parsed_command.requires_execute:
            domain_schema_response = self._handle_domain_schema_request(
                message=request_message,
                command_mode=command_mode,
                session_id=session_id,
                model_profile_id=model_profile_id,
                target=target,
                sandbox_id=sandbox_id,
                database_profile_id=database_profile_id,
                state=state,
            )
        if domain_schema_response is not None:
            return domain_schema_response
        context_pack = self._build_context_pack(
            session_id=session_id,
            message=parsed_command.message or message,
            state=state,
            target=target,
            sandbox_id=sandbox_id,
            database_profile_id=database_profile_id,
        )
        schema_summary_response = self._maybe_schema_summary_answer(request_message, context_pack)
        if schema_summary_response is not None:
            return schema_summary_response

        # Skip workflow_engine for explicit /execute commands
        workflow_response = None
        if command_mode != "execute":
            workflow_decision = self.workflow_engine.decide(parsed_command.message or message, state)
            workflow_response = self._handle_workflow_decision(workflow_decision, context_pack, state)
        if workflow_response is not None:
            return workflow_response

        direct_read_response = None
        if command_mode != "execute":
            direct_read_response = self._maybe_direct_read_chat(
                message=parsed_command.message or message,
                session_id=session_id,
                model_profile_id=model_profile_id,
                target=target,
                sandbox_id=sandbox_id,
                database_profile_id=database_profile_id,
                state=state,
                auto_execute=auto_execute,
            )
        if direct_read_response is not None:
            return direct_read_response

        if command_mode != "execute" and parsed_command.requires_execute:
            command_mode = "execute"

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
            action_plan = generated.get("action_plan") or {}
            consistency = generated.get("consistency") or {}
            operation = str(action_plan.get("operation") or "UNKNOWN").upper()
            explanation = model_output.get("explanation") or generated.get("answer") or ("SQL draft generated. Review it before running Check Safety." if sql else LLM_UNSTRUCTURED_REPLY)

            if not sql:
                block_code = str(generated.get("reason") or consistency.get("code") or "SEMANTIC_PLAN_BLOCKED")
                policy_blocked = bool(generated.get("policy_blocked"))
                return {
                    "success": True,
                    "answer": explanation,
                    "generated_sql": None,
                    "check": None,
                    "execute": {"executed": False, "blocked": True, "executable": False},
                    "execute_box": {
                        "draft_ready": False,
                        "sql": "",
                        "summary": explanation,
                        "policy_blocked": policy_blocked,
                        "executable": False,
                        "check_allowed": False,
                    },
                    "action_plan": action_plan,
                    "consistency": consistency,
                    "safety": {
                        "workflow": "semantic_plan_blocked",
                        "next_step": self._semantic_block_next_step(block_code, policy_blocked=policy_blocked),
                        "target": resolved_ctx.target,
                        "blocked": True,
                        "policy_blocked": policy_blocked,
                        "executable": False,
                        "check_allowed": False,
                        "warnings": [block_code],
                        "skills": ["semantic_action_planner", "schema_graph", "text_to_sql", "intent_sql_consistency_guard"],
                    },
                    "schema_graph": generated.get("schema_graph"),
                    "agent_state": generated.get("agent_state"),
                    "context_pack": generated.get("context_pack"),
                }

            try:
                from Gateway.sql_classifier import classify_sql
                classification = classify_sql(sql)
                if classification.is_read_only:
                    if operation != "READ" or not consistency.get("ok"):
                        return {
                            "success": True,
                            "answer": "SQL read-only không khớp với semantic action plan. SAFY đã chặn thay vì tự đổi ý định người dùng.",
                            "generated_sql": None,
                            "check": None,
                            "execute": {"executed": False, "blocked": True},
                            "action_plan": action_plan,
                            "consistency": {**consistency, "ok": False, "code": "MUTATION_PLAN_PRODUCED_READ"},
                            "safety": {
                                "workflow": "intent_sql_mismatch",
                                "blocked": True,
                                "skills": ["semantic_action_planner", "intent_sql_consistency_guard"],
                            },
                        }
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
                # Any parser/classifier uncertainty remains on the draft-only path.
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
                "action_plan": action_plan,
                "consistency": consistency,
                "workflow_plan": plan,
                "workflow_review": review,
                "safety": {
                    "workflow": "draft_only",
                    "next_step": "check_safety",
                    "target": (generated.get("target") or {}).get("target"),
                    "provider_profile_id": (generated.get("profile") or {}).get("profile_id"),
                    "blocked": False,
                    "warnings": [] if sql else ["llm_returned_no_sql"],
                    "skills": ["command_router", "database_context", "semantic_action_planner", "schema_graph", "text_to_sql", "intent_sql_consistency_guard", "execute_box"],
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

