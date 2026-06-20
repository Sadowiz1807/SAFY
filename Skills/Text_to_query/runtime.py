from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re

from LLM.provider_health import adapter_for


LLM_UNSTRUCTURED_REPLY = "Model không trả về SQL có cấu trúc. SAFY đã giữ an toàn và không thực thi gì. Hãy thử yêu cầu cụ thể hơn."


class TextToQuerySkill:
    def __init__(self, provider_store: Any, system_prompt_loader):
        self.provider_store = provider_store
        self.system_prompt_loader = system_prompt_loader

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
        match = re.search(r"\b(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN|CREATE|ALTER|DROP|INSERT|UPDATE|DELETE)\b[\s\S]+", text, re.I)
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

    def _fallback_sql(self, request: str, schema_graph: dict[str, Any] | None) -> str:
        text = (request or "").strip()
        lower = text.lower()
        limit_match = re.search(r"\b(?:limit|top|first|lấy|lay|show)\s+(\d{1,4})\b", lower)
        limit = int(limit_match.group(1)) if limit_match else 10
        limit = max(1, min(limit, 100))
        from_match = re.search(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_\.]*)(?:\b|$)", text, re.I)
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
            if not table and tables and any(k in lower for k in ["show", "list", "rows", "select", "lấy", "liet", "liệt"]):
                table = str(tables[0].get("key") or tables[0].get("name") or "")
        if table:
            safe_table = re.sub(r"[^A-Za-z0-9_\.]", "", table)
            return f"SELECT * FROM {safe_table} LIMIT {limit};"
        return ""

    def generate_sql_draft(self, request: str, model_profile_id: str | None, target: dict[str, Any], schema_context_text: str, schema_graph: dict[str, Any] | None = None, context_pack_text: str | None = None) -> dict[str, Any]:
        profile = self.provider_store.get(model_profile_id, redacted=False) if model_profile_id else self.provider_store.active(redacted=False)
        context_text = context_pack_text or f"Active database target: {target.get('target')}\nDatabase profile id: {target.get('database_profile_id') or 'none'}\n\nSchema context:\n{schema_context_text}"
        messages = [
            {"role": "system", "content": self.system_prompt_loader()},
            {"role": "user", "content": f"{context_text}\n\nUser request:\n{request}\n\nReturn JSON only with keys: intent, sql, explanation, target_hint, requires_confirmation."},
        ]
        payload = adapter_for(profile).chat(messages, temperature=0.0)
        raw_content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = self._parse_model_json(raw_content)
        sql = str(parsed.get("sql") or "").strip()
        if not sql:
            fallback = self._fallback_sql(request, schema_graph)
            if fallback:
                sql = fallback
                parsed = {**parsed, "intent": "database_task", "sql": sql, "explanation": "Generated a conservative SELECT draft from the active schema context.", "target_hint": target.get("target"), "requires_confirmation": False, "fallback": True}
        return {
            "generated_sql": sql,
            "model_output": parsed,
            "profile": profile,
            "target": target,
            "schema_context_used": True,
            "draft_only": True,
        }
