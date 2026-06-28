from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re

from DataStore.schema_graph_store import summarize_schema_graph
from LLM.provider_health import adapter_for
from Gateway.sql_normalizer import sanitize_sql_input
from Core.semantic_action_plan import (
    CHAT,
    READ,
    CREATE_OBJECT,
    UNKNOWN_OPERATION,
    SemanticActionPlan,
    plan_from_explicit_sql,
    render_deterministic_sql,
    semantic_planner_contract,
    validate_sql_against_plan,
)


@dataclass
class ParsedCommand:
    mode: str
    action: str
    message: str
    raw_message: str
    is_database_task: bool
    requires_execute: bool


@dataclass
class DatabaseContext:
    target: str
    sandbox_id: str | None
    database_profile_id: str | None
    database_profile: dict[str, Any] | None
    has_real_database: bool


class CommandRouterSkill:
    database_keywords = [
        "database", "db", "sql", "query", "table", "schema", "column", "row", "select",
        "insert", "update", "delete", "drop", "mysql", "postgres", "postgresql", "sqlite",
        "oracle", "sql server", "dữ liệu", "du lieu", "bảng", "bang", "truy vấn", "truy van",
        "cột", "cot", "hàng", "hang", "orders", "users", "customers",
        "bao nhiêu bảng", "bao nhieu bang", "có mấy bảng", "co may bang", "tạo", "tao", "thêm", "them",
    ]
    execute_patterns = [
        r"create\s+table", r"alter\s+table", r"drop\s+table", r"truncate\s+table",
        r"insert\s+into", r"update\s+\w+", r"delete\s+from", r"select\s+.+\s+from",
        r"show\s+tables", r"show\s+(?:ra\s+)?(?:.*?)(?:data|rows|records|dữ\s+liệu|du\s+lieu)",
        r"describe\s+\w+", r"explain\s+select", r"run\s+query", r"execute\s+query",
        r"generate\s+sql", r"truy\s+vấn", r"truy\s+van", r"liệt\s+kê", r"liet\s+ke",
        r"hiển\s+thị", r"hien\s+thi", r"xem\s+(?:dữ\s+liệu|du\s+lieu|bảng|bang)", r"tạo\s+bảng", r"tao\s+bang",
        r"thêm\s+cột", r"them\s+cot", r"kiểm\s+tra\s+(?:database|db)", r"kiem\s+tra\s+(?:database|db)",
        r"bao\s+nhiêu\s+bảng", r"bao\s+nhieu\s+bang", r"có\s+mấy\s+bảng", r"co\s+may\s+bang",
    ]

    def parse(self, message: str, command_mode: str | None = None) -> ParsedCommand:
        raw = message or ""
        stripped = raw.strip()
        lower = stripped.lower()
        mode = (command_mode or "chat").strip().lower()
        action = "chat"
        normalized_message = stripped
        if lower.startswith("/execute"):
            mode = "execute"; action = "execute_sql_draft"; normalized_message = stripped[len("/execute"):].strip()
        elif lower == "/reset_schema":
            mode = "schema"; action = "reset_schema"
        elif lower == "/delete_schema":
            mode = "schema"; action = "delete_active_schema"
        elif mode == "execute":
            action = "execute_sql_draft"
        is_database_task = any(keyword in lower for keyword in self.database_keywords)
        requires_execute = any(re.search(pattern, lower, re.I) for pattern in self.execute_patterns)
        if mode == "execute":
            requires_execute = False
        return ParsedCommand(mode, action, normalized_message or stripped, raw, is_database_task, requires_execute)


class DatabaseContextSkill:
    def __init__(self, database_profile_loader=None, sandbox_manager=None):
        self.database_profile_loader = database_profile_loader
        self.sandbox_manager = sandbox_manager

    def get_profile(self, profile_id: str | None) -> dict[str, Any] | None:
        if not profile_id or not self.database_profile_loader:
            return None
        try:
            return self.database_profile_loader(profile_id)
        except Exception:
            return None

    def has_real_database(self, profile_id: str | None) -> bool:
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        driver = str(profile.get("driver") or profile.get("dbms") or "").lower()
        return bool(profile.get("real_db_readonly")) and driver not in {"", "fake", "test"}

    def resolve(self, target: str | None, sandbox_id: str | None, database_profile_id: str | None) -> DatabaseContext:
        resolved_target = target
        profile = self.get_profile(database_profile_id)
        has_real = self.has_real_database(database_profile_id)
        if not resolved_target or resolved_target == "auto":
            resolved_target = "connected_database" if has_real else "sandbox"
        if resolved_target == "connected_database":
            return DatabaseContext("connected_database", None, database_profile_id, profile, has_real)
        resolved_sandbox_id = sandbox_id or "sandbox_default"
        if self.sandbox_manager and not sandbox_id:
            try:
                active = [s for s in self.sandbox_manager.list() if s.get("active") and s.get("state") != "deleted"]
                if active:
                    resolved_sandbox_id = active[0].get("sandbox_id") or active[0].get("id") or resolved_sandbox_id
            except Exception:
                pass
        return DatabaseContext("sandbox", resolved_sandbox_id, None, None, False)


class DatabaseSwitchSkill:
    def __init__(self, database_store=None, schema_graph_skill=None):
        self.database_store = database_store; self.schema_graph_skill = schema_graph_skill
    def list_profiles(self) -> list[dict[str, Any]]:
        return [] if not self.database_store else self.database_store.read_all()
    def active_profile(self) -> dict[str, Any] | None:
        return next((p for p in self.list_profiles() if p.get("active")), None)
    def load_active_schema_if_exists(self) -> dict[str, Any] | None:
        profile = self.active_profile()
        if not profile or not self.schema_graph_skill:
            return None
        return self.schema_graph_skill.load(profile.get("profile_id"), profile)


class SchemaGraphSkill:
    def __init__(self, schema_graph_loader=None):
        self.schema_graph_loader = schema_graph_loader
    def load(self, database_profile_id: str | None, database_profile: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not database_profile_id or not self.schema_graph_loader:
            return None
        try:
            return self.schema_graph_loader(database_profile_id)
        except Exception:
            return None
    def summarize(self, graph: dict[str, Any] | None) -> str:
        return summarize_schema_graph(graph)
    def select_relevant_subset(self, graph: dict[str, Any] | None, user_query: str, max_tables: int = 8, max_edges: int = 16) -> dict[str, Any] | None:
        if not graph or graph.get("status") != "ready":
            return graph
        text = (user_query or "").lower(); tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text)); tables = graph.get("tables") or []
        scored: list[tuple[int, dict[str, Any]]] = []
        for table in tables:
            score = 0; names = {str(table.get("name") or "").lower(), str(table.get("key") or "").lower()}
            if any(name and name in text for name in names): score += 10
            for token in tokens:
                if token in names: score += 8
            for col in table.get("columns") or []:
                col_name = str(col.get("name") or "").lower()
                if col_name and (col_name in tokens or col_name in text): score += 2
            if score: scored.append((score, table))
        selected = [t for _, t in sorted(scored, key=lambda item: item[0], reverse=True)[:max_tables]] if scored else tables[:max_tables]
        selected_keys = {str(t.get("key") or t.get("name")) for t in selected}
        edges = [e for e in (graph.get("edges") or []) if str(e.get("from_table")) in selected_keys or str(e.get("to_table")) in selected_keys][:max_edges]
        return {**graph, "tables": selected, "edges": edges, "table_count": len(selected), "edge_count": len(edges), "subset": True, "source_schema_hash": graph.get("schema_hash")}


class TextToSqlSkill:
    """Semantic-plan-first text-to-SQL action.

    Natural language is first converted into a canonical action plan. SQL is
    generated only after the plan is valid, then independently classified and
    checked against the plan. This prevents a model from weakening a write/DDL
    request into a harmless-looking SELECT.
    """

    def __init__(
        self,
        provider_store: Any | None = None,
        system_prompt_loader: Any | None = None,
    ) -> None:
        self.provider_store = provider_store
        self.system_prompt_loader = system_prompt_loader

    def _system_prompt(self) -> str:
        if callable(self.system_prompt_loader):
            return str(self.system_prompt_loader() or "")
        return str(self.system_prompt_loader or "")

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
        match = re.search(
            r"\b(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN|CREATE|ALTER|DROP|TRUNCATE|INSERT|UPDATE|DELETE|MERGE|GRANT|REVOKE)\b[\s\S]+",
            text,
            re.I,
        )
        return match.group(0).strip().rstrip("`") if match else ""

    def _extract_explicit_sql(self, content: str) -> str:
        text = (content or "").strip()
        fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)```", text, re.I | re.S)
        if fenced:
            text = fenced.group(1).strip()
        if not re.match(
            r"^(SELECT|WITH|CREATE|ALTER|DROP|TRUNCATE|INSERT|UPDATE|DELETE|MERGE|GRANT|REVOKE)\b",
            text,
            re.I,
        ):
            return ""
        return text.rstrip("`").strip()

    def _identifier(self, name: str) -> str | None:
        candidate = re.sub(r"[^A-Za-z0-9_]", "_", str(name or "").strip())
        candidate = re.sub(r"_+", "_", candidate).strip("_")
        if not candidate or not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$", candidate):
            return None
        return candidate

    def _maybe_deterministic_create_table(self, request: str, target_payload: dict[str, Any]) -> dict[str, Any] | None:
        """Draft simple CREATE TABLE SQL without calling an LLM.

        This covers the common UAT/user path: Vietnamese/English requests such as
        "tạo bảng A có 2 cột id và address". It is intentionally narrow: only
        simple table identifiers and column identifiers are accepted, and all
        non-id columns default to TEXT so the draft remains reviewable before
        Check Safety.
        """
        text = str(request or "").strip()
        if not text:
            return None
        match = re.search(r"(?:tạo|tao|create)\s+(?:cho\s+tôi\s+|cho\s+toi\s+)?(?:bảng|bang|table)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.I)
        if not match:
            return None
        table = self._identifier(match.group(1))
        if not table:
            return None
        tail = text[match.end():]
        col_part_match = re.search(r"(?:có|co|gồm|gom|với|voi|with|columns?|cột|cot)\s+(.*)$", tail, re.I)
        col_part = col_part_match.group(1) if col_part_match else tail
        col_part = re.sub(r"\b\d+\s*(?:cột|cot|columns?)\b", " ", col_part, flags=re.I)
        col_part = re.sub(r"\b(?:cột|cot|columns?|gồm|gom|có|co|với|voi|là|la|and)\b", " ", col_part, flags=re.I)
        raw_cols = re.split(r"\s*(?:,|;|\bvà\b|\bva\b|\band\b)\s*", col_part, flags=re.I)
        cols: list[str] = []
        for raw in raw_cols:
            value = re.sub(r"\b(?:primary\s+key|pk|text|int|integer|varchar|address|địa\s+chỉ|dia\s+chi)\b", lambda m: m.group(0), raw, flags=re.I).strip()
            # Pick the first identifier token from each segment.
            token_match = re.search(r"[A-Za-z_][A-Za-z0-9_]*", value)
            if not token_match:
                continue
            ident = self._identifier(token_match.group(0))
            if ident and ident.lower() not in {"bang", "bảng", "cot", "cột", "co", "có", "gom", "gồm"} and ident not in cols:
                cols.append(ident)
        if not cols:
            # A CREATE TABLE with no columns is not useful; fail to normal planner.
            return None
        dialect = str(target_payload.get("dialect") or target_payload.get("driver") or target_payload.get("database_type") or "").lower()
        int_type = "INT" if dialect in {"mysql", "mariadb", "sqlserver"} else "INTEGER"
        lines = []
        has_pk = False
        for col in cols:
            if col.lower() == "id" and not has_pk:
                lines.append(f"    {col} {int_type} PRIMARY KEY")
                has_pk = True
            else:
                lines.append(f"    {col} TEXT")
        sql = f"CREATE TABLE {table} (\n" + ",\n".join(lines) + "\n);"
        plan = SemanticActionPlan(
            operation=CREATE_OBJECT,
            scope="SINGLE_OBJECT",
            object_type="TABLE",
            targets=[table],
            schema_effect="SCHEMA_WRITE",
            requires_schema=False,
            requires_confirmation=True,
            confidence=0.95,
            rationale="Deterministic parser recognized a simple create-table request.",
            source="deterministic_create_table",
        )
        consistency = validate_sql_against_plan(sql, plan)
        if not consistency.get("ok"):
            return None
        parsed = {
            "intent": plan.operation,
            "sql": sql,
            "explanation": "Generated a deterministic CREATE TABLE draft. Review it, then run Check Safety before Execute.",
            "target_hint": target_payload.get("target"),
            "requires_confirmation": True,
            "deterministic": True,
        }
        return {
            "generated_sql": sql,
            "answer": parsed["explanation"],
            "model_output": parsed,
            "action_plan": plan.to_dict(),
            "consistency": consistency,
            "profile": None,
            "target": target_payload,
            "schema_context_used": False,
            "skill_context_used": False,
            "draft_only": True,
            "blocked": False,
            "deterministic_plan": {"ok": True, "code": "DETERMINISTIC_CREATE_TABLE", "table": table, "columns": cols},
        }

    def _parse_json_object(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = self._llm_content_as_text(content).strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _parse_model_json(self, content: Any) -> dict[str, Any]:
        parsed = self._parse_json_object(content)
        if parsed:
            return parsed
        text = self._llm_content_as_text(content).strip()
        sql = self._extract_sql_candidate(text)
        return {
            "intent": "database_task" if sql else "chat",
            "sql": sql,
            "explanation": text or "Model returned no structured SQL draft.",
            "target_hint": None,
            "requires_confirmation": False,
        }

    def _profile(self, model_profile_id: str | None) -> dict[str, Any] | None:
        if self.provider_store is None:
            return None
        return (
            self.provider_store.get(model_profile_id, redacted=False)
            if model_profile_id
            else self.provider_store.active(redacted=False)
        )

    def _plan_semantic_action(
        self,
        *,
        request: str,
        profile: dict[str, Any],
        target_payload: dict[str, Any],
        context_text: str,
        schema_context_text: str,
    ) -> SemanticActionPlan:
        planner_system = (
            "You are SAFY Semantic Action Planner. Interpret the meaning of the "
            "user request before any SQL is generated. Return one JSON object only. "
            "Choose a canonical operation from the supplied contract. Do not weaken "
            "a requested write, deletion, reset, purge, schema removal, permission "
            "change, or destructive action into READ. Different languages, synonyms, "
            "and indirect phrasing must map to the same semantic operation. If the "
            "request is ambiguous, unrelated to databases, or confidence is low, use "
            "UNKNOWN or CHAT. Use scope ALL_TABLES only when every user table is "
            "targeted; use DATABASE only for the database object itself and SCHEMA "
            "only for a schema object. Do not return SQL."
        )
        messages = [
            {"role": "system", "content": planner_system},
            {
                "role": "user",
                "content": (
                    f"Semantic plan contract:\n{semantic_planner_contract()}\n\n"
                    f"Active target:\n{json.dumps(target_payload, ensure_ascii=False)}\n\n"
                    f"Schema summary:\n{schema_context_text or '[not available]'}\n\n"
                    f"Runtime context:\n{context_text}\n\n"
                    f"User request:\n{request}\n\n"
                    "Return the semantic action plan JSON only."
                ),
            },
        ]
        try:
            payload = adapter_for(profile).chat(messages, temperature=0.0)
            raw_content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_json_object(raw_content)
            return SemanticActionPlan.from_payload(parsed, source="semantic_model")
        except Exception as exc:
            return SemanticActionPlan(
                operation=UNKNOWN_OPERATION,
                confidence=0.0,
                rationale="Semantic planner failed safely.",
                source="semantic_model",
                warnings=[f"semantic_planner_error:{type(exc).__name__}"],
            )

    def _blocked_result(
        self,
        *,
        plan: SemanticActionPlan,
        profile: dict[str, Any] | None,
        target_payload: dict[str, Any],
        schema_context_text: str,
        skill_context_text: str,
        explanation: str,
        consistency: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        consistency_payload = consistency or {
            "ok": False,
            "code": "SEMANTIC_PLAN_BLOCKED",
            "message": explanation,
            "statement_type": None,
            "expected_statement_types": [],
        }
        model_output = {
            "intent": plan.operation,
            "sql": "",
            "explanation": explanation,
            "target_hint": target_payload.get("target"),
            "requires_confirmation": plan.requires_confirmation,
            "blocked": True,
        }
        policy_blocked = bool(plan.is_destructive)
        return {
            "generated_sql": "",
            "answer": explanation,
            "model_output": model_output,
            "action_plan": plan.to_dict(),
            "consistency": consistency_payload,
            "profile": profile,
            "target": target_payload,
            "schema_context_used": bool(schema_context_text),
            "skill_context_used": bool(skill_context_text),
            "draft_only": True,
            "blocked": True,
            "policy_blocked": policy_blocked,
            "executable": False,
            "check_allowed": False if policy_blocked else False,
            "execute_allowed": False,
            "reason": "DESTRUCTIVE_SQL_BLOCKED" if policy_blocked else consistency_payload.get("code"),
            "check_id": None,
            "sql_hash": None,
        }

    def generate_sql_draft(
        self,
        request: str,
        model_profile_id: str | None = None,
        target: dict[str, Any] | None = None,
        schema_context_text: str = "",
        schema_graph: dict[str, Any] | None = None,
        context_pack_text: str = "",
        skill_context_text: str = "",
    ) -> dict[str, Any]:
        target_payload = target or {}
        explicit_sql = self._extract_explicit_sql(request)
        if explicit_sql:
            sql = sanitize_sql_input(explicit_sql)
            plan = plan_from_explicit_sql(sql)
            consistency = validate_sql_against_plan(sql, plan)
            if not consistency.get("ok"):
                return self._blocked_result(
                    plan=plan,
                    profile=None,
                    target_payload=target_payload,
                    schema_context_text=schema_context_text,
                    skill_context_text=skill_context_text,
                    explanation=str(consistency.get("message") or "Explicit SQL could not be classified safely."),
                    consistency=consistency,
                )
            if plan.is_destructive:
                return self._blocked_result(
                    plan=plan,
                    profile=None,
                    target_payload=target_payload,
                    schema_context_text=schema_context_text,
                    skill_context_text=skill_context_text,
                    explanation="DROP and TRUNCATE are blocked by SAFY policy and cannot enter Check Safety or Execute.",
                    consistency={
                        **consistency,
                        "ok": False,
                        "code": "DESTRUCTIVE_SQL_BLOCKED",
                        "message": "Destructive SQL is non-executable in the ordinary Execute Box workflow.",
                    },
                )
            parsed = {
                "intent": plan.operation,
                "sql": sql,
                "explanation": (
                    "Using the explicit read-only SQL supplied by the user."
                    if plan.is_read
                    else "Using the explicit SQL as a draft. SQL Guard, sandbox, and confirmation rules still apply."
                ),
                "target_hint": target_payload.get("target"),
                "requires_confirmation": plan.requires_confirmation,
            }
            return {
                "generated_sql": sql,
                "answer": parsed["explanation"],
                "model_output": parsed,
                "action_plan": plan.to_dict(),
                "consistency": consistency,
                "profile": None,
                "target": target_payload,
                "schema_context_used": bool(schema_context_text),
                "skill_context_used": bool(skill_context_text),
                "draft_only": True,
                "blocked": False,
            }

        deterministic_create = self._maybe_deterministic_create_table(request, target_payload)
        if deterministic_create is not None:
            return deterministic_create

        profile = self._profile(model_profile_id)
        if profile is None:
            plan = SemanticActionPlan(
                operation=UNKNOWN_OPERATION,
                confidence=0.0,
                rationale="No semantic model provider is configured.",
                source="runtime",
                warnings=["semantic_model_unavailable"],
            )
            return self._blocked_result(
                plan=plan,
                profile=None,
                target_payload=target_payload,
                schema_context_text=schema_context_text,
                skill_context_text=skill_context_text,
                explanation="Không có model semantic planner; SAFY không đoán SQL từ ngôn ngữ tự nhiên.",
            )

        context_text = context_pack_text or (
            f"Active database target: {target_payload.get('target')}\n"
            f"Database profile id: {target_payload.get('database_profile_id') or 'none'}\n\n"
            f"Schema context:\n{schema_context_text}"
        )
        plan = self._plan_semantic_action(
            request=request,
            profile=profile,
            target_payload=target_payload,
            context_text=context_text,
            schema_context_text=schema_context_text,
        )

        if plan.operation == CHAT:
            return self._blocked_result(
                plan=plan,
                profile=profile,
                target_payload=target_payload,
                schema_context_text=schema_context_text,
                skill_context_text=skill_context_text,
                explanation=plan.rationale or "Yêu cầu không phải tác vụ database.",
                consistency={
                    "ok": False,
                    "code": "SEMANTIC_PLAN_CHAT",
                    "message": "No SQL is generated for a chat request.",
                    "statement_type": None,
                    "expected_statement_types": [],
                },
            )
        if not plan.can_generate_sql:
            return self._blocked_result(
                plan=plan,
                profile=profile,
                target_payload=target_payload,
                schema_context_text=schema_context_text,
                skill_context_text=skill_context_text,
                explanation=(
                    "SAFY chưa xác định đủ chắc chắn thao tác database. Yêu cầu chưa được chuyển thành SQL."
                    if plan.operation == UNKNOWN_OPERATION or plan.confidence < 0.60
                    else "Semantic action plan không hợp lệ; SAFY đã fail closed."
                ),
            )

        if plan.is_destructive:
            return self._blocked_result(
                plan=plan,
                profile=profile,
                target_payload=target_payload,
                schema_context_text=schema_context_text,
                skill_context_text=skill_context_text,
                explanation="Yêu cầu destructive đã được nhận diện nhưng bị chặn bởi SAFY policy. Không tạo Check Safety hoặc Execute cho DROP/TRUNCATE.",
                consistency={
                    "ok": False,
                    "code": "DESTRUCTIVE_SQL_BLOCKED",
                    "message": "Destructive semantic plans are non-executable in the ordinary workflow.",
                    "statement_type": None,
                    "expected_statement_types": ["DROP", "TRUNCATE"],
                },
            )

        deterministic = render_deterministic_sql(plan, schema_graph, target_payload)
        if deterministic is not None:
            sql = sanitize_sql_input(deterministic.get("sql"))
            if not deterministic.get("ok") or not sql:
                return self._blocked_result(
                    plan=plan,
                    profile=profile,
                    target_payload=target_payload,
                    schema_context_text=schema_context_text,
                    skill_context_text=skill_context_text,
                    explanation=str(deterministic.get("message") or "Deterministic SQL planning failed safely."),
                    consistency={
                        "ok": False,
                        "code": deterministic.get("code") or "DETERMINISTIC_PLAN_FAILED",
                        "message": deterministic.get("message") or "Deterministic SQL planning failed safely.",
                        "statement_type": None,
                        "expected_statement_types": ["DROP"],
                    },
                )
            consistency = validate_sql_against_plan(sql, plan)
            if not consistency.get("ok"):
                return self._blocked_result(
                    plan=plan,
                    profile=profile,
                    target_payload=target_payload,
                    schema_context_text=schema_context_text,
                    skill_context_text=skill_context_text,
                    explanation=str(consistency.get("message") or "Deterministic SQL did not match the plan."),
                    consistency=consistency,
                )
            parsed = {
                "intent": plan.operation,
                "sql": sql,
                "explanation": deterministic.get("message"),
                "target_hint": target_payload.get("target"),
                "requires_confirmation": True,
                "deterministic": True,
            }
            return {
                "generated_sql": sql,
                "answer": str(parsed["explanation"] or ""),
                "model_output": parsed,
                "action_plan": plan.to_dict(),
                "consistency": consistency,
                "profile": profile,
                "target": target_payload,
                "schema_context_used": bool(schema_context_text),
                "skill_context_used": bool(skill_context_text),
                "draft_only": True,
                "blocked": False,
                "deterministic_plan": deterministic,
            }

        generator_system = (
            f"{self._system_prompt()}\n\n"
            "The semantic action plan below is authoritative. Generate SQL that "
            "implements exactly that operation and scope. Never replace a write, "
            "DDL, destructive, permission, or administrative plan with SELECT. "
            "If exact SQL cannot be generated from the available schema, return an "
            "empty sql field and explain why. Return JSON only."
        )
        messages = [
            {"role": "system", "content": generator_system},
            {
                "role": "user",
                "content": (
                    f"{skill_context_text}\n\n"
                    f"{context_text}\n\n"
                    f"Canonical semantic action plan:\n{json.dumps(plan.to_dict(), ensure_ascii=False)}\n\n"
                    f"User request:\n{request}\n\n"
                    "Return JSON only with keys: intent, sql, explanation, "
                    "target_hint, requires_confirmation."
                ),
            },
        ]
        try:
            payload = adapter_for(profile).chat(messages, temperature=0.0)
            raw_content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_model_json(raw_content)
        except Exception as exc:
            return self._blocked_result(
                plan=plan,
                profile=profile,
                target_payload=target_payload,
                schema_context_text=schema_context_text,
                skill_context_text=skill_context_text,
                explanation=f"SQL generator failed safely: {type(exc).__name__}.",
            )

        sql = sanitize_sql_input(parsed.get("sql"))
        consistency = validate_sql_against_plan(sql, plan)
        if not consistency.get("ok"):
            return self._blocked_result(
                plan=plan,
                profile=profile,
                target_payload=target_payload,
                schema_context_text=schema_context_text,
                skill_context_text=skill_context_text,
                explanation=str(consistency.get("message") or "Generated SQL did not match the semantic action plan."),
                consistency=consistency,
            )

        parsed["intent"] = plan.operation
        parsed["sql"] = sql
        parsed["requires_confirmation"] = plan.requires_confirmation
        return {
            "generated_sql": sql,
            "answer": str(parsed.get("explanation") or ""),
            "model_output": parsed,
            "action_plan": plan.to_dict(),
            "consistency": consistency,
            "profile": profile,
            "target": target_payload,
            "schema_context_used": bool(schema_context_text),
            "skill_context_used": bool(skill_context_text),
            "draft_only": True,
            "blocked": False,
        }


class QueryGuardSkill:
    def __init__(self, query_orchestrator): self.query_orchestrator = query_orchestrator
    def check(self, sql: str, target: dict[str, Any], database_profile: dict[str, Any] | None = None, permission_mode: str = "read_only", execution_path: str = "skill_query_guard") -> dict[str, Any]:
        return self.query_orchestrator.check(
            sql=sql,
            target=target.get("target") or "connected_database",
            database_profile_id=target.get("database_profile_id"),
            permission_mode=permission_mode,
            execution_path=execution_path,
            sandbox_id=target.get("sandbox_id"),
            real_db_mode=bool(target.get("target") == "connected_database" and database_profile),
            database_profile=database_profile,
            context_generation=target.get("context_generation"),
            schema_generation=target.get("schema_generation"),
            driver=target.get("driver"),
            dialect=target.get("dialect"),
        )


class ExecuteBoxSkill:
    def set_draft(self, sql: str, explanation: str, target: dict[str, Any], provider_profile_id: str | None = None) -> dict[str, Any]:
        return {"draft_ready": bool(sql), "sql": sql, "summary": explanation or "SQL draft generated. Review it before running Check Safety.", "next_steps": ["review_sql", "check_safety", "execute_if_allowed"], "target": target.get("target"), "database_profile_id": target.get("database_profile_id"), "provider_profile_id": provider_profile_id, "auto_executed": False}


class ExecuteQuerySkill:
    def __init__(self, query_orchestrator): self.query_orchestrator = query_orchestrator
    def execute_checked(self, check_id: str, sql_hash: str, target: dict[str, Any], user_decision: str | None = None, confirmation_code: str | None = None, row_limit: int = 100) -> tuple[bool, dict[str, Any]]:
        return self.query_orchestrator.execute(
            check_id=check_id,
            sql_hash=sql_hash,
            target=target.get("target") or "connected_database",
            user_decision=user_decision,
            confirmation_code=confirmation_code,
            database_profile_id=target.get("database_profile_id"),
            row_limit=row_limit,
            sandbox_id=target.get("sandbox_id"),
            context_generation=target.get("context_generation"),
            schema_generation=target.get("schema_generation"),
            driver=target.get("driver"),
            dialect=target.get("dialect"),
        )


class QueryExplainSkill:
    def explain(self, sql: str, schema_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        text = sql or ""; tables = re.findall(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_\.]*)|\bjoin\s+([A-Za-z_][A-Za-z0-9_\.]*)", text, re.I); flattened = [a or b for a, b in tables if (a or b)]
        return {"summary": "This SQL draft is intended for review before safety check and execution.", "tables": list(dict.fromkeys(flattened)), "has_where": bool(re.search(r"\bwhere\b", text, re.I)), "has_join": bool(re.search(r"\bjoin\b", text, re.I)), "schema_hash": schema_graph.get("schema_hash") if isinstance(schema_graph, dict) else None}


class QueryRepairSkill:
    def repair_basic(self, sql: str, error: dict[str, Any] | None = None, schema_graph: dict[str, Any] | None = None) -> dict[str, Any]:
        repaired = (sql or "").strip(); notes: list[str] = []
        if repaired and not repaired.endswith(";"): repaired += ";"; notes.append("Added trailing semicolon.")
        if re.match(r"^select\b", repaired, re.I) and " limit " not in repaired.lower(): repaired = repaired.rstrip(";") + " LIMIT 100;"; notes.append("Added LIMIT 100 for safer preview.")
        return {"sql": repaired, "notes": notes, "draft_only": True, "schema_hash": schema_graph.get("schema_hash") if isinstance(schema_graph, dict) else None}


def resolve_domain(message: str) -> tuple[str, list[str]]:
    text = (message or "").lower()
    if any(term in text for term in ["store", "shop", "commerce", "e-commerce", "ecommerce", "online store"]):
        return "ecommerce", []
    return "ecommerce", ["Domain not provided; using default e-commerce domain."]
