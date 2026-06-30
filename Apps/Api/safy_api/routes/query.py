from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from Apps.Api.safy_api.runtime_store import envelope, error_envelope
from Runtime.strict_services import check_query, execute_query

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
    check_id: str | None = None
    sql_hash: str | None = None
    user_decision: str | None = None
    confirmation_code: str | None = None
    row_limit: int = 100


@router.post("/query/check")
def query_check_route(payload: QueryCheckPayload):
    try:
        return envelope(check_query(payload.model_dump()))
    except Exception as exc:
        return error_envelope("SANDBOX_RULE_ENGINE_ERROR", "Sandbox rule engine failed safely during Check Safety.", {"error_type": type(exc).__name__})


@router.post("/query/execute")
def query_execute_route(payload: QueryExecutePayload):
    try:
        ok, result = execute_query(payload.model_dump())
        if not ok:
            return error_envelope(result.get("code") or "QUERY_EXECUTION_BLOCKED", result.get("message") or "Query execution was blocked.", result.get("details") or result)
        return envelope(result)
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
