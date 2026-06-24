from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re

from DataStore.schema_graph_store import summarize_schema_graph
from LLM.provider_health import adapter_for
from Gateway.sql_normalizer import sanitize_sql_input


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
    ]
    execute_patterns = [
        r"create\s+table", r"alter\s+table", r"drop\s+table", r"truncate\s+table",
        r"insert\s+into", r"update\s+\w+", r"delete\s+from", r"select\s+.+\s+from",
        r"show\s+tables", r"show\s+(?:ra\s+)?(?:.*?)(?:data|rows|records|dữ\s+liệu|du\s+lieu)",
        r"describe\s+\w+", r"explain\s+select", r"run\s+query", r"execute\s+query",
        r"generate\s+sql", r"truy\s+vấn", r"truy\s+van", r"liệt\s+kê", r"liet\s+ke",
        r"hiển\s+thị", r"hien\s+thi", r"xem\s+(?:dữ\s+liệu|du\s+lieu|bảng|bang)", r"tạo\s+bảng", r"tao\s+bang",
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
    """Shared text-to-SQL action used by the document-driven skill pack."""

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
            r"\b(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN|CREATE|ALTER|DROP|INSERT|UPDATE|DELETE)\b[\s\S]+",
            text,
            re.I,
        )
        return match.group(0).strip().rstrip("`") if match else ""

    def _parse_model_json(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = self._llm_content_as_text(content).strip()
        if not text:
            return {
                "intent": "unknown",
                "sql": "",
                "explanation": "Model returned no structured SQL draft.",
                "target_hint": None,
                "requires_confirmation": False,
            }
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
        return {
            "intent": "database_task" if sql else "chat",
            "sql": sql,
            "explanation": text,
            "target_hint": None,
            "requires_confirmation": False,
        }

    def _fallback_sql(
        self,
        request: str,
        schema_graph: dict[str, Any] | None,
    ) -> str:
        text = (request or "").strip()
        lower = text.lower()
        limit_match = re.search(
            r"\b(?:limit|top|first|lấy|lay|show)\s+(\d{1,4})\b",
            lower,
        )
        limit = int(limit_match.group(1)) if limit_match else 10
        limit = max(1, min(limit, 100))

        from_match = re.search(
            r"\bfrom\s+([A-Za-z_][A-Za-z0-9_\.]*)(?:\b|$)",
            text,
            re.I,
        )
        table = from_match.group(1) if from_match else ""

        if not table and schema_graph and schema_graph.get("status") == "ready":
            tables = schema_graph.get("tables") or []
            for candidate in tables:
                key = str(candidate.get("key") or candidate.get("name") or "")
                name = str(candidate.get("name") or "")
                if key and key.lower() in lower:
                    table = key
                    break
                if name and name.lower() in lower:
                    table = key or name
                    break
            if not table and tables and any(
                token in lower
                for token in ["show", "list", "rows", "select", "lấy", "liet", "liệt"]
            ):
                table = str(tables[0].get("key") or tables[0].get("name") or "")

        if not table:
            return ""
        safe_table = re.sub(r"[^A-Za-z0-9_\.]", "", table)
        return f"SELECT * FROM {safe_table} LIMIT {limit};" if safe_table else ""

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
        explicit_sql = self._extract_sql_candidate(request)
        if explicit_sql:
            read_only = bool(
                re.match(
                    r"^(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)\b",
                    explicit_sql,
                    re.I,
                )
            )
            parsed = {
                "intent": "read_only" if read_only else "write_or_ddl",
                "sql": explicit_sql,
                "explanation": (
                    "Using the explicit read-only SQL supplied by the user."
                    if read_only
                    else "Using the explicit SQL as a draft. SQL Guard, sandbox, and confirmation rules still apply."
                ),
                "target_hint": target_payload.get("target"),
                "requires_confirmation": not read_only,
            }
            return {
                "generated_sql": explicit_sql,
                "answer": parsed["explanation"],
                "model_output": parsed,
                "profile": None,
                "target": target_payload,
                "schema_context_used": bool(schema_context_text),
                "skill_context_used": bool(skill_context_text),
                "draft_only": True,
            }

        if self.provider_store is None:
            fallback = self._fallback_sql(request, schema_graph)
            parsed = {
                "intent": "database_task" if fallback else "chat",
                "sql": fallback,
                "explanation": (
                    "Generated a conservative SELECT draft from the active schema context."
                    if fallback
                    else "No model provider is configured and no safe schema-grounded fallback was available."
                ),
                "target_hint": target_payload.get("target"),
                "requires_confirmation": False,
                "fallback": bool(fallback),
            }
            return {
                "generated_sql": fallback,
                "answer": parsed["explanation"],
                "model_output": parsed,
                "profile": None,
                "target": target_payload,
                "schema_context_used": bool(schema_context_text),
                "skill_context_used": bool(skill_context_text),
                "draft_only": True,
            }

        profile = (
            self.provider_store.get(model_profile_id, redacted=False)
            if model_profile_id
            else self.provider_store.active(redacted=False)
        )
        context_text = context_pack_text or (
            f"Active database target: {target_payload.get('target')}\n"
            f"Database profile id: {target_payload.get('database_profile_id') or 'none'}\n\n"
            f"Schema context:\n{schema_context_text}"
        )
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": (
                    f"{skill_context_text}\n\n"
                    f"{context_text}\n\n"
                    f"User request:\n{request}\n\n"
                    "Return JSON only with keys: intent, sql, explanation, "
                    "target_hint, requires_confirmation."
                ),
            },
        ]
        payload = adapter_for(profile).chat(messages, temperature=0.0)
        raw_content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = self._parse_model_json(raw_content)
        sql = sanitize_sql_input(parsed.get("sql"))
        if sql:
            parsed["sql"] = sql
        if not sql:
            fallback = self._fallback_sql(request, schema_graph)
            if fallback:
                sql = fallback
                parsed = {
                    **parsed,
                    "intent": "database_task",
                    "sql": sql,
                    "explanation": "Generated a conservative SELECT draft from the active schema context.",
                    "target_hint": target_payload.get("target"),
                    "requires_confirmation": False,
                    "fallback": True,
                }
        return {
            "generated_sql": sql,
            "answer": str(parsed.get("explanation") or ""),
            "model_output": parsed,
            "profile": profile,
            "target": target_payload,
            "schema_context_used": bool(schema_context_text),
            "skill_context_used": bool(skill_context_text),
            "draft_only": True,
        }


class QueryGuardSkill:
    def __init__(self, query_orchestrator): self.query_orchestrator = query_orchestrator
    def check(self, sql: str, target: dict[str, Any], database_profile: dict[str, Any] | None = None, permission_mode: str = "read_only", execution_path: str = "skill_query_guard") -> dict[str, Any]:
        return self.query_orchestrator.check(sql=sql, target=target.get("target") or "connected_database", database_profile_id=target.get("database_profile_id"), permission_mode=permission_mode, execution_path=execution_path, sandbox_id=target.get("sandbox_id"), real_db_mode=bool(target.get("target") == "connected_database" and database_profile), database_profile=database_profile)


class ExecuteBoxSkill:
    def set_draft(self, sql: str, explanation: str, target: dict[str, Any], provider_profile_id: str | None = None) -> dict[str, Any]:
        return {"draft_ready": bool(sql), "sql": sql, "summary": explanation or "SQL draft generated. Review it before running Check Safety.", "next_steps": ["review_sql", "check_safety", "execute_if_allowed"], "target": target.get("target"), "database_profile_id": target.get("database_profile_id"), "provider_profile_id": provider_profile_id, "auto_executed": False}


class ExecuteQuerySkill:
    def __init__(self, query_orchestrator): self.query_orchestrator = query_orchestrator
    def execute_checked(self, check_id: str, sql_hash: str, target: dict[str, Any], user_decision: str | None = None, confirmation_code: str | None = None, row_limit: int = 100) -> tuple[bool, dict[str, Any]]:
        return self.query_orchestrator.execute(check_id=check_id, sql_hash=sql_hash, target=target.get("target") or "connected_database", user_decision=user_decision, confirmation_code=confirmation_code, database_profile_id=target.get("database_profile_id"), row_limit=row_limit, sandbox_id=target.get("sandbox_id"))


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
