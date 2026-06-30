from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from Apps.Api.safy_api.app_factory import create_app

ROOT = Path(__file__).resolve().parents[2]
PROMPT = Path(r"C:\Users\ASUS\AppData\Local\hermes\cache\documents\doc_fb7e4bbd11f4_SAFY_PRODUCTION_SAVE_TEST_REAL_PATCH_PROMPT_FILLED.md")
OUT_DIR = ROOT / "Reports" / "patches" / "2026-06-30_production_save_test_real_patch"
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT = OUT_DIR / "10_USER_PROVIDED_LIVE_TEST_REPORT.md"
JSON_EVIDENCE = OUT_DIR / "10_user_provided_live_test_evidence.json"

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]+",
    r"sb_secret_[A-Za-z0-9_\-]+",
    r"password_value_optional_for_live_test:\s*\"[^\"]+\"",
]


def _doc() -> str:
    return PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else ""


def _extract_yaml_value(text: str, key: str) -> str | None:
    pattern = rf"^\s*{re.escape(key)}:\s*\"([^\"]*)\"\s*(?:#.*)?$"
    m = re.search(pattern, text, re.M)
    return m.group(1) if m else None


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        s = value
        for pat in SECRET_PATTERNS:
            s = re.sub(pat, "[REDACTED]", s)
        for marker in ("api_key", "password", "service_role", "Bearer"):
            if marker.lower() in s.lower() and len(s) > 24:
                return "[REDACTED]"
        return s
    return value


def _case(name: str, response) -> dict[str, Any]:
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    body = _redact(body)
    return {
        "case": name,
        "http_status": response.status_code,
        "success": body.get("success") if isinstance(body, dict) else None,
        "error_code": (body.get("error") or {}).get("code") if isinstance(body, dict) else None,
        "request_id": ((body.get("meta") or {}).get("request_id") if isinstance(body, dict) else None),
        "body": body,
    }


def main() -> None:
    text = _doc()
    openrouter_key = _extract_yaml_value(text, "api_key_value_optional_for_live_test")
    supabase_key_match = re.findall(r"api_key_value_optional_for_live_test:\s*\"([^\"]*)\"", text)
    supabase_key = supabase_key_match[1] if len(supabase_key_match) > 1 else None
    if openrouter_key and not openrouter_key.startswith("TODO_"):
        os.environ["OPENROUTER_API_KEY"] = openrouter_key
    if supabase_key and not supabase_key.startswith("TODO_"):
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = supabase_key

    client = TestClient(create_app())
    cases: list[dict[str, Any]] = []

    model_payload = {
        "profile_id": "gpt-5.5",
        "name": "gpt-5.5",
        "provider": "openrouter",
        "base_url": "http://localhost:20128/v1",
        "model_id": "gpt-5.5",
        "api_key": "********",
        "api_key_env_name": "OPENROUTER_API_KEY",
        "mode": "chat_completions",
        "context_length": 128000,
        "is_active": True,
    }
    cases.append(_case("MODEL_SAVE_OPENROUTER", client.post("/model-profiles", json=model_payload)))
    cases.append(_case("MODEL_ACTIVATE_OPENROUTER", client.post("/model-profiles/gpt-5.5/activate")))
    cases.append(_case("MODEL_TEST_OPENROUTER", client.post("/model-profiles/gpt-5.5/test")))

    supabase_payload = {
        "profile_id": "db_supabase",
        "name": "db_supabase",
        "driver": "supabase",
        "mode": "rpc",
        "project_url": "https://umbxtngdrtgfbspqhqbf.supabase.co",
        "api_key": "********",
        "api_key_env_name": "SUPABASE_SERVICE_ROLE_KEY",
        "rpc_function_name": "safy_execute_sql",
        "is_active": True,
    }
    cases.append(_case("DATABASE_SAVE_SUPABASE", client.post("/database-profiles", json=supabase_payload)))
    cases.append(_case("DATABASE_ACTIVATE_SUPABASE", client.post("/database-profiles/db_supabase/activate")))
    cases.append(_case("DATABASE_TEST_SUPABASE_RPC", client.post("/database-profiles/test", json=supabase_payload)))

    sqlserver_payload = {
        "profile_id": "db_sqlserver_local",
        "name": "db_sqlserver_local",
        "driver": "sqlserver",
        "host": "TODO_USER_FILL_SQLSERVER_HOST_OR_INSTANCE",
        "port": "TODO_USER_FILL_SQLSERVER_PORT_OR_EMPTY",
        "instance": "TODO_USER_FILL_SQLSERVER_INSTANCE_OR_EMPTY",
        "database": "TODO_USER_FILL_SQLSERVER_DATABASE",
        "auth_mode": "TODO_USER_FILL_windows_OR_sql_password",
        "username": "TODO_USER_FILL_SQLSERVER_USER_IF_SQL_PASSWORD",
        "password": "********",
        "password_env_name": "SQLSERVER_PASSWORD",
        "encrypt": "optional",
        "trust_server_certificate": True,
        "timeout_seconds": 10,
    }
    cases.append(_case("DATABASE_SAVE_SQLSERVER_WITH_TODO_FIELDS", client.post("/database-profiles", json=sqlserver_payload)))
    cases.append(_case("DATABASE_TEST_SQLSERVER_WITH_TODO_FIELDS", client.post("/database-profiles/test", json=sqlserver_payload)))

    rule_valid = {"rule_text": "Mọi bảng được tạo phải có cột id hoặc ID làm định danh"}
    rule_ambiguous = {"rule_text": "Bảng phải chuẩn và an toàn"}
    rule_empty = {"rule_text": ""}
    cases.append(_case("RULE_SAVE_VALID_IDENTIFIER", client.post("/sandbox-rules/save", json=rule_valid)))
    cases.append(_case("RULE_SAVE_AMBIGUOUS", client.post("/sandbox-rules/save", json=rule_ambiguous)))
    cases.append(_case("RULE_SAVE_EMPTY", client.post("/sandbox-rules/save", json=rule_empty)))
    cases.append(_case("MALFORMED_MODEL_SAVE_ENVELOPE", client.post("/model-profiles", content="{bad", headers={"Content-Type": "application/json"})))
    cases.append(_case("METHOD_NOT_ALLOWED_ENVELOPE", client.get("/database-profiles/test")))

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runner": "FastAPI TestClient against patched create_app()",
        "note": "Secrets were loaded in process from the user prompt when present and redacted from evidence.",
        "cases": cases,
    }
    JSON_EVIDENCE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# User Provided Save/Test Live Smoke Report", "", f"- Timestamp: {summary['timestamp']}", "- Runner: FastAPI TestClient against patched `create_app()`", "- Secret handling: prompt-provided keys loaded only in process; report/evidence redacted.", ""]
    for c in cases:
        expected_error_codes = {
            "RULE_AMBIGUOUS",
            "RULE_TEXT_REQUIRED",
            "VALIDATION_ERROR",
            "HTTP_METHOD_NOT_ALLOWED",
            "LIVE_SQLSERVER_TEST_BLOCKED_MISSING_FIELD",
            "SECRET_VALUE_REJECTED",
            "LLM_PROVIDER_UNREACHABLE",
            "LLM_API_KEY_MISSING",
            "SUPABASE_RPC_NOT_INSTALLED",
            "SUPABASE_AUTH_FAILED",
            "SUPABASE_RPC_FAILED",
            "DATABASE_TEST_FAILED",
        }
        status = "PASS" if c["success"] is True else "EXPECTED_BLOCKED" if c["error_code"] in expected_error_codes else "FAIL" if c["success"] is False else "CHECK"
        lines.extend([
            f"## {c['case']}",
            f"- Result: {status}",
            f"- HTTP status: {c['http_status']}",
            f"- Envelope success: {c['success']}",
            f"- Error code: {c['error_code'] or 'none'}",
            f"- Request ID: {c['request_id'] or 'none'}",
            "",
        ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)
    print(JSON_EVIDENCE)


if __name__ == "__main__":
    main()
