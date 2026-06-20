from __future__ import annotations

import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = os.getenv("SAFY_E2E_URL", "http://127.0.0.1:8000").rstrip("/")
DB_URL = os.getenv("SAFY_E2E_DB_URL", "").strip()
DB_PASSWORD = os.getenv("SAFY_E2E_DB_PASSWORD", "").strip()
DB_USERNAME = os.getenv("SAFY_E2E_DB_USERNAME", "postgres").strip() or "postgres"
DB_DISPLAY_NAME = os.getenv("SAFY_E2E_DB_DISPLAY_NAME", "supabase_direct_e2e").strip() or "supabase_direct_e2e"
LOGIN_USERNAME = os.getenv("SAFY_E2E_USERNAME", "HermesE2E")
LOGIN_PASSWORD = os.getenv("SAFY_E2E_PASSWORD", "")
EXECUTE_REAL = os.getenv("SAFY_E2E_EXECUTE_REAL", "1") == "1"
TABLE_NAME = os.getenv("SAFY_E2E_TABLE", f"safy_e2e_{int(time.time())}")


def request(path: str, payload: dict | None = None, method: str | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        BASE_URL + path,
        data=body,
        method=method or ("POST" if payload is not None else "GET"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {raw}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach SAFY at {BASE_URL}: {exc.reason}") from exc
    data = json.loads(raw) if raw else {}
    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError(f"SAFY error at {path}: {json.dumps(data.get('error') or data, ensure_ascii=False)}")
    return data.get("data", data) if isinstance(data, dict) else data


def main() -> int:
    if not DB_URL:
        print("Missing SAFY_E2E_DB_URL. Use a direct PostgreSQL URL, for example:")
        print("  postgresql://postgres:<db-password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require")
        return 2
    if not DB_PASSWORD and "://" in DB_URL and "@" not in DB_URL:
        print("Missing SAFY_E2E_DB_PASSWORD. This must be the database password, not a Supabase REST API key.")
        return 2

    if LOGIN_PASSWORD:
        request("/auth/login", {"username": LOGIN_USERNAME, "password": LOGIN_PASSWORD, "use_saved_password": False})
        print("login: ok")

    profile_id = "db_" + "".join(ch if ch.isalnum() else "_" for ch in DB_DISPLAY_NAME.lower()).strip("_")
    save_payload = {
        "profile_id": profile_id,
        "display_name": DB_DISPLAY_NAME,
        "provider": "supabase" if "supabase.co" in DB_URL else "self_hosted",
        "driver": "postgresql",
        "dbms": "postgresql",
        "base_url": DB_URL,
        "username": DB_USERNAME,
        "password": DB_PASSWORD,
        "raw_secret": DB_PASSWORD,
        "secret_mode": "env" if DB_PASSWORD else "none",
        "password_mode": "env" if DB_PASSWORD else "none",
        "ssl_mode": "require" if "supabase.co" in DB_URL else "preferred",
        "user_query_access_mode": "credential_permissions",
        "active": True,
        "read_only": True,
        "real_db_readonly": True,
    }
    saved = request("/database-profiles", save_payload)
    print("save_database:", saved.get("profile_id"), saved.get("connection_kind"), saved.get("driver"), saved.get("host"), saved.get("database"), saved.get("username"))
    if saved.get("connection_kind") != "native_sql":
        raise RuntimeError(f"Expected native_sql profile, got {saved.get('connection_kind')}")

    sql = f'CREATE TABLE "{TABLE_NAME}" (id INTEGER, note TEXT);'
    checked = request("/query/check", {
        "sql": sql,
        "target": "connected_database",
        "sandbox_id": f"db_{profile_id}",
        "database_profile_id": profile_id,
        "user_query_access_mode": "credential_permissions",
        "real_db_mode": True,
    })
    print("check_safety:", checked.get("safety_status"), checked.get("decision"))
    if checked.get("safety_status") != "sandbox_passed":
        raise RuntimeError(f"Check Safety did not pass: {json.dumps(checked, ensure_ascii=False)}")

    if not EXECUTE_REAL:
        print("execute skipped because SAFY_E2E_EXECUTE_REAL != 1")
        return 0

    executed = request("/query/execute", {
        "check_id": checked.get("check_id"),
        "sql_hash": checked.get("sql_hash"),
        "target": "connected_database",
        "sandbox_id": checked.get("sandbox_id"),
        "database_profile_id": profile_id,
        "user_decision": "yes",
        "confirmation_code": None,
        "real_db_mode": True,
    })
    print("execute:", executed.get("driver"), executed.get("metadata", {}).get("statement_type"), executed.get("row_count"))
    print("created_table:", TABLE_NAME)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
