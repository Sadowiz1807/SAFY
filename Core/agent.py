from __future__ import annotations

from pathlib import Path
import tempfile

from Audit.audit_store import AuditStore
from Providers.base_provider import ProviderRequest
from Providers.model_client import ModelClient
from Tools.registry import ToolRegistry
from Tools.tool_executor import ToolExecutor
from Tools.sandbox.create_workspace_tool import CreateWorkspaceTool
from Tools.sandbox.execute_sandbox_sql_tool import ExecuteSandboxSQLTool
from Tools.sandbox.inspect_workspace_tool import InspectWorkspaceTool
from Tools.sandbox.cleanup_workspace_tool import CleanupWorkspaceTool
from Tools.database.read_schema_tool import ReadSchemaTool
from Tools.sql.validate_sql_tool import ValidateSQLTool
from Tools.sql.sanitize_identifier_tool import SanitizeIdentifierTool
from State.runtime_db import RuntimeDB
from Logging.redact import redact_obj

from .agent_execution_context import AgentExecutionContext
from .intent_detector import detect_intent
from .intent_planner import plan_intent
from .prompt_builder import build_provider_prompt
from .result_summarizer import summarize_create_database
from .skill_loader import load_skill
from .skill_policy import SkillPolicy
from .skill_router import route_skill
from .skill_actions import resolve_domain
from Gateway.query_orchestrator import QueryOrchestrator, QueryOrchestratorContext
from DataStore.config_loader import ConfigLoader, get_repo_root
from DataStore.profile_store import database_profile_store, ProfileStoreError


def split_ddl_batch(ddl: list[str] | str, target: str) -> list[str]:
    if target != "sandbox" and isinstance(ddl, str) and ";" in ddl.strip().rstrip(";"):
        raise ValueError("SQL_BLOCKED")
    if isinstance(ddl, list):
        items = ddl
    else:
        items = [part + ";" for part in ddl.split(";") if part.strip()]
    return [item.strip() for item in items if item.strip()]


class AgentCore:
    def __init__(self, runtime_dir: Path | None = None, model_client: ModelClient | None = None) -> None:
        self.runtime_dir = Path(runtime_dir or Path(tempfile.gettempdir()) / "safy_agent_runtime_agent")
        self.model_client = model_client or ModelClient()
        self.audit = AuditStore(self.runtime_dir / "audit.sqlite3")
        self.runtime_db = RuntimeDB(self.runtime_dir / "runtime.sqlite3")

    def _registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        for tool in [
            CreateWorkspaceTool(),
            ExecuteSandboxSQLTool(),
            ReadSchemaTool(),
            ValidateSQLTool(),
            SanitizeIdentifierTool(),
            InspectWorkspaceTool(),
            CleanupWorkspaceTool(),
        ]:
            registry.register(tool)
        return registry

    def _agent_auto_select_sql(self, message: str) -> str | None:
        text = message.strip()
        lower = text.lower()
        allowed_starts = ("select ", "with ", "show ", "describe ", "explain select ")
        return text if lower.startswith(allowed_starts) else None

    def chat(self, ctx: AgentExecutionContext) -> dict:
        chat_id = ctx.ensure_chat_id()
        self.runtime_db.create_session(chat_id)
        self.runtime_db.add_message(chat_id, "user", ctx.message)

        intent = detect_intent(ctx.message)
        plan = plan_intent(intent, ctx.target)
        if plan["status"] == "connected_read_only":
            auto_sql = self._agent_auto_select_sql(ctx.message)
            if auto_sql and ctx.database_profile_id:
                try:
                    profile = database_profile_store(ConfigLoader(get_repo_root()).load().data_path("profiles_json")).get(ctx.database_profile_id)
                    orchestrator = QueryOrchestrator(QueryOrchestratorContext(self.runtime_dir / "agent_real_db", test_runtime_mode=False))
                    checked = orchestrator.check(auto_sql, target="connected_database", database_profile_id=ctx.database_profile_id, permission_mode="credential_permissions", execution_path="agent_auto_select", real_db_mode=True, database_profile=profile)
                    if checked.get("allowed_to_attempt"):
                        ok, result = orchestrator.execute(checked["check_id"], checked["sql_hash"], "connected_database", None, None, ctx.database_profile_id, 50)
                        if ok:
                            audit_id = self.audit.write_event(event_type="agent_auto_select", actor_type="agent", actor_id="runtime_test", action="guarded_auto_select", target_type="database_profile", target_id=ctx.database_profile_id, risk_level="read_only", status="success", metadata=redact_obj({"chat_id": chat_id, "workflow_id": ctx.workflow_id, "database_profile_id": ctx.database_profile_id, "guard_path": "/query/check -> /query/execute", "row_count": result.get("metadata", {}).get("row_count"), "result_rows_persisted": False, "raw_sql_persisted": False}))
                            message = "Guarded read-only SELECT executed against the active database profile."
                            self.runtime_db.add_message(chat_id, "assistant", message, audit_id=audit_id["audit_id"], metadata={"summary": message, "target": "connected_database", "result_rows_persisted": False})
                            return {"success": True, "target": "connected_database", "blocked_reason": None, "result_preview": {"mode": "real_db_auto_select", "message": message, "rows": result.get("rows", [])}, "audit_id": audit_id["audit_id"], "runtime_preview_only": False, "no_real_execution": False, "guard_path": "/query/check -> /query/execute"}
                except ProfileStoreError:
                    pass
            audit_id = self.audit.write_event(
                event_type="agent_workflow",
                actor_type="agent",
                actor_id="api_runtime",
                action="connected_read_only_preview",
                target_type="database_profile",
                target_id=ctx.database_profile_id or "unknown",
                risk_level="read_only",
                status="success",
                metadata=redact_obj(
                    {
                        "chat_id": chat_id,
                        "workflow_id": ctx.workflow_id,
                        "intent": intent,
                        "target": ctx.target,
                        "database_profile_id": ctx.database_profile_id,
                        "runtime_preview_only": True,
                        "no_real_execution": True,
                    }
                ),
            )
            result_preview = {
                "mode": "agent_read_only_preview",
                "message": f"Read-only connected database preview prepared for: {ctx.message}",
                "rows": [],
            }
            self.runtime_db.add_message(
                chat_id, 
                "assistant", 
                result_preview["message"], 
                audit_id=audit_id["audit_id"], 
                metadata={"summary": result_preview["message"], "target": "connected_database"}
            )
            return {
                "success": True,
                "target": "connected_database",
                "blocked_reason": None,
                "result_preview": result_preview,
                "audit_id": audit_id["audit_id"],
                "runtime_preview_only": True,
                "no_real_execution": True,
            }
        if plan["status"] != "ready":
            err_code = plan["error_code"]
            self.runtime_db.add_message(chat_id, "assistant", f"Request blocked: {err_code}", metadata={"blocked_reason": err_code})
            return {
                "success": False,
                "target": ctx.target,
                "blocked_reason": err_code,
                "data": None,
                "error": {"code": err_code, "message": "Request cannot be executed in Agent runtime."},
                "meta": {"request_id": ctx.request_id, "timestamp": ctx.created_at},
            }

        skill_name = route_skill(intent)
        skill = load_skill(skill_name)
        policy = SkillPolicy.compile(skill["frontmatter"])
        if not policy.allows_intent(intent) or not policy.allows_target(ctx.target):
            self.runtime_db.add_message(chat_id, "assistant", "Skill policy blocked.", metadata={"blocked_reason": "SKILL_POLICY_BLOCKED"})
            raise ValueError("SKILL_POLICY_BLOCKED")

        domain, assumptions = resolve_domain(ctx.message)
        provider_prompt = build_provider_prompt(ctx.message, domain, assumptions)
        provider_response = self.model_client.generate(
            ProviderRequest(provider_prompt, intent, domain, ctx.target, policy.data["redaction_profile"])
        )
        output = provider_response.output
        if output.get("target") != "sandbox" or not isinstance(output.get("ddl"), (list, str)):
            self.runtime_db.add_message(chat_id, "assistant", "Provider output invalid.", metadata={"blocked_reason": "PROVIDER_OUTPUT_INVALID"})
            raise ValueError("PROVIDER_OUTPUT_INVALID")

        executor = ToolExecutor(self._registry())
        ws_result = executor.execute(
            "sandbox.create_workspace", policy, ctx.target, chat_id=chat_id, workflow_id=ctx.workflow_id
        )
        if not ws_result.success:
            self.runtime_db.add_message(chat_id, "assistant", "Sandbox workspace creation failed.", metadata={"blocked_reason": ws_result.error_code or "SANDBOX_WORKSPACE_FAILED"})
            raise ValueError(ws_result.error_code or "SANDBOX_WORKSPACE_FAILED")

        workspace_id = ws_result.data["workspace_id"]
        db_path = ws_result.data["db_path"]
        
        # Register workspace in registry
        self.runtime_db.register_workspace(
            workspace_id, 
            chat_id, 
            path_redacted=f"Sandbox/{workspace_id}", 
            metadata={"workflow_id": ctx.workflow_id}
        )

        lock = self.runtime_db.acquire_workspace_lock(
            workspace_id,
            owner=chat_id,
            reason="agent_runtime_create_database",
            metadata={"workflow_id": ctx.workflow_id, "target": ctx.target},
        )
        warnings: list[str] = []
        statements = split_ddl_batch(output["ddl"], ctx.target)
        try:
            for statement in statements:
                validate = executor.execute("sql.validate", policy, ctx.target, statement=statement)
                if not validate.success:
                    raise ValueError(validate.error_code or "SQL_BLOCKED")
                warnings.extend(validate.warnings)
                exec_result = executor.execute(
                    "sandbox.execute_sql", policy, ctx.target, db_path=db_path, statement=validate.data["statement"]
                )
                if not exec_result.success:
                    raise ValueError(exec_result.error_code or "TOOL_EXECUTION_FAILED")
            schema_result = executor.execute("database.read_schema", policy, ctx.target, db_path=db_path)
            if not schema_result.success:
                raise ValueError(schema_result.error_code or "SANDBOX_SCHEMA_READBACK_FAILED")
        finally:
            self.runtime_db.release_workspace_lock(lock["lock_id"])

        schema = schema_result.data["schema"]
        technical_result = {
            "target": "sandbox",
            "dialect": "sqlite",
            "provider_profile": provider_response.provider_id,
            "tools_attempted": executor.attempted,
            "sql_guard_decisions": "validated_each_statement",
            "ddl_statement_count": len(statements),
        }
        audit_id = self.audit.write_event(
            event_type="agent_workflow",
            actor_type="agent",
            actor_id="agent_runtime",
            action="create_database",
            target_type="sandbox_workspace",
            target_id=workspace_id,
            risk_level="sandbox_schema_change",
            status="success",
            metadata=redact_obj(
                {
                    "chat_id": chat_id,
                    "workflow_id": ctx.workflow_id,
                    "intent": intent,
                    "skill": skill_name,
                    "policy_version": policy.version,
                    "target": ctx.target,
                    "workspace_id": workspace_id,
                    "tools_attempted": executor.attempted,
                    "sql_guard_decisions": "validated_each_statement",
                    "redaction_status": "redacted",
                }
            ),
        )["audit_id"]
        self.runtime_db.record_provenance(
            workspace_id,
            "sandbox_workspace",
            "agent_core",
            "agent_runtime_agent",
            stage="Agent runtime",
            metadata={"chat_id": chat_id, "workflow_id": ctx.workflow_id, "intent": intent, "target": ctx.target},
        )
        data = summarize_create_database(
            chat_id, ctx.workflow_id, workspace_id, assumptions, schema, technical_result, sorted(set(warnings))
        )
        self.runtime_db.add_message(
            chat_id, 
            "assistant", 
            data["summary"], 
            audit_id=audit_id, 
            workspace_id=workspace_id,
            metadata=data
        )
        return {"success": True, "data": data, "error": None, "meta": {"request_id": ctx.request_id, "timestamp": ctx.created_at}}
