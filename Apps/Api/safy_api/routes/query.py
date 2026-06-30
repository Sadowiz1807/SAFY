from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from Apps.Api.safy_api.runtime_store import envelope, error_envelope
from DataStore.profile_store import database_profile_store
from Gateway.db_drivers.factory import execute_readonly, execute_user_sql
from Gateway.sql_classifier import classify_sql
from Gateway.sql_normalizer import normalize_sql
from Runtime.strict_services import check_query

router = APIRouter()


class QueryCheckPayload(BaseModel):
    sql: str
    target: str = "sandbox"
    database_profile_id: str | None = None
    sandbox_id: str | None = None
    session_id: str | None = None
    chat_id: str | None = None
    user_query_access_mode: str = "credential_permissions"
    real_db_mode: bool = False
    context_generation: int | None = None
    schema_generation: int | None = None
    driver: str | None = None
    dialect: str | None = None
    model_config = ConfigDict(extra="allow")


class QueryExecutePayload(QueryCheckPayload):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _database_store():
    return database_profile_store(_repo_root() / "Data" / "safy_profiles.json")


def _active_or_requested_profile(profile_id: str | None) -> dict:
    store = _database_store()
    if profile_id:
        return store.get(profile_id)
    for profile in store.read_all():
        if profile.get("active") or profile.get("is_active"):
            return profile
    raise RuntimeError("DATABASE_PROFILE_REQUIRED")


@router.post("/query/check")
def query_check_route(payload: QueryCheckPayload):
    try:
        return envelope(check_query(payload.model_dump()))
    except Exception as exc:
        return error_envelope("SANDBOX_RULE_ENGINE_ERROR", "Sandbox rule engine failed safely during Check Safety.", {"error_type": type(exc).__name__})


@router.post("/query/execute")
def query_execute_route(payload: QueryExecutePayload):
    try:
        profile = _active_or_requested_profile(payload.database_profile_id)
        normalized = normalize_sql(payload.sql)
        first = normalized.statements[0] if normalized.statements else payload.sql
        classification = classify_sql(first)
        if len(normalized.statements) == 1 and classification.is_read_only:
            result = execute_readonly(first, profile, None, {"row_limit": 50})
        else:
            result = execute_user_sql(payload.sql, profile, None, {"row_limit": 50})
        return envelope({"executed": True, "database_profile_id": profile.get("profile_id"), "result": result})
    except Exception as exc:
        code = getattr(exc, "error_code", None) or str(exc)
        message = str(exc)
        code_text = str(code)
        if code_text == "DATABASE_PROFILE_REQUIRED":
            return error_envelope("DATABASE_PROFILE_REQUIRED", "No active database profile is configured.")
        if "SYNTAX" in code_text.upper() or "syntax" in message.lower() or "incorrect" in message.lower():
            return error_envelope("SQL_SYNTAX_ERROR", "SQL syntax error during execution.", {"driver_code": code_text})
        if "PERMISSION" in code_text.upper() or "permission" in message.lower():
            return error_envelope("DATABASE_PERMISSION_DENIED", "Database permission denied during execution.", {"driver_code": code_text})
        return error_envelope(code_text if code_text else "DATABASE_EXECUTION_FAILED", message, {"error_type": type(exc).__name__})
