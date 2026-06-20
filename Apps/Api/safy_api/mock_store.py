from datetime import datetime, timedelta, timezone
import hashlib
import random
import re
import uuid

from Logging.redact import redact_obj, redact_text

from .meta import now_iso, request_meta

CHECKS: dict[str, dict] = {}
HIGH_RISK = {"DELETE", "DROP", "UPDATE", "ALTER", "TRUNCATE"}
WARNING_RISK = {"INSERT", "CREATE"}


def envelope(data, request_id: str | None = None):
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": request_meta(request_id),
    }


def error_envelope(code: str, message: str, details=None, request_id: str | None = None):
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": redact_text(message), "details": redact_obj(details or {})},
        "meta": request_meta(request_id),
    }


def statement_type(sql: str) -> str:
    cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    cleaned = re.sub(r"^\s*--.*?$", " ", cleaned, flags=re.MULTILINE).strip()
    parts = cleaned.split()
    if not parts:
        return "UNKNOWN"
    first = parts[0].upper()
    if first == "WITH":
        upper_sql = cleaned.upper()
        for token in ("DELETE", "DROP", "UPDATE", "ALTER", "TRUNCATE", "INSERT", "CREATE", "SELECT"):
            if re.search(rf"\b{token}\b", upper_sql):
                return token
    return first


def make_check(sql: str, target: str, database_profile_id: str | None, access_mode: str):
    stmt = statement_type(sql)
    sql_hash = "hash_mock_" + hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
    check_id = "check_mock_" + uuid.uuid4().hex[:16]
    high = stmt in HIGH_RISK
    warning = stmt in WARNING_RISK
    risk_level = "high" if high else "warning" if warning else "safe"
    blocked = access_mode == "disabled" or (access_mode == "read_only" and stmt != "SELECT")
    status = "blocked" if blocked else "requires_confirmation" if high else "allowed"
    warnings = []
    if high:
        warnings.append("Destructive or mutating SQL requires mock manual confirmation.")
    elif warning:
        warnings.append("Statement is allowed in Phase 1 mock mode but should be reviewed.")
    else:
        warnings.append("Read-only style query detected by Phase 1 mock checker.")
    if blocked:
        warnings.append("Selected mock access mode is disabled.")
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    return {
        "check_id": check_id,
        "sql_hash": sql_hash,
        "risk_level": risk_level,
        "safety_status": status,
        "warnings": warnings,
        "confirmation_required": high and not blocked,
        "confirmation_code": f"{random.SystemRandom().randint(0, 9999):04d}" if high and not blocked else None,
        "confirmation_type": "numeric_code" if high and not blocked else None,
        "confirmation_code_length": 4 if high and not blocked else 0,
        "expires_at": expires_at,
        "statement_type": stmt,
        "database_profile_id": database_profile_id,
        "user_query_access_mode": access_mode,
        "safety_report": {
            "target": target,
            "affected_tables": ["orders"] if high else [],
            "permission_expectation": "Mock execution follows selected user query access mode.",
            "warnings": warnings,
        },
    }

