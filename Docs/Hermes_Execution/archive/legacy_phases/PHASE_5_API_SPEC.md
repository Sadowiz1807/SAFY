# SAFY Phase 5 API Spec

## Status
Status: Approved for Phase 5 implementation. This document was originally a planning document and now defines the canonical implementation baseline for endpoint shapes and tests. It does not claim Phase 5 has already been implemented.

## Confirmation Code Delivery Mode

Local development/test mode may expose `confirmation_code_dev_hint` only when `SAFY_LOCAL_CONFIRMATION_ECHO=true`.

Production mode must never return the raw confirmation code in API responses, logs, audit, UI, reports, or snapshots.

Tests that require a code must use trusted test helpers or explicit local echo mode.

## Existing Endpoints to Preserve
- `POST /query/check`
- `POST /query/execute`
- `POST /agent/chat`
- Profile endpoints that return secret references only.

## POST /query/check
Purpose: classify and gate SQL without executing it.

### Request
```json
{
  "sql": "SELECT * FROM orders",
  "target": "connected_database",
  "database_profile_id": "database_profile_id_here",
  "user_query_access_mode": "credential_permissions"
}
```

### Response Data
```json
{
  "check_id": "check_id_here",
  "sql_hash": "hash_here",
  "statement_type": "SELECT",
  "target": "connected_database",
  "database_profile_id": "database_profile_id_here",
  "risk_level": "safe",
  "safety_status": "read_only",
  "decision": "ALLOW_READ_ONLY",
  "warnings": [],
  "confirmation_required": false,
  "confirmation_code_length": 0,
  "confirmation_expires_at": null,
  "expires_at": "timestamp_here",
  "policy_version": "version_here"
}
```

### Rules
- Must not execute SQL.
- Must not return raw secrets.
- Must return stable binding fields needed by `/query/execute`.
- If high-risk confirmation is required, return metadata only unless explicitly in local mock mode; production mode must not leak code through logs or unsafe channels.

## POST /query/execute
Purpose: execute only after a valid `/query/check`.

### Request
```json
{
  "check_id": "check_id_here",
  "sql_hash": "hash_here",
  "target": "connected_database",
  "database_profile_id": "database_profile_id_here",
  "user_decision": "yes",
  "confirmation_code": null
}
```

### Success Response Data
```json
{
  "status": "success",
  "execution_mode": "connected_read_only_or_user_confirmed",
  "target": "connected_database",
  "database_profile_id": "database_profile_id_here",
  "audit_id": "audit_id_here",
  "columns": [],
  "rows": [],
  "row_count": 0,
  "truncated": false
}
```

### Error Codes
- `QUERY_CHECK_REQUIRED`
- `QUERY_CHECK_CONSUMED`
- `QUERY_CHECK_EXPIRED`
- `SQL_HASH_MISMATCH`
- `TARGET_MISMATCH`
- `DATABASE_PROFILE_MISMATCH`
- `SQL_POLICY_BLOCKED`
- `MANUAL_CONFIRMATION_MISSING`
- `MANUAL_CONFIRMATION_INVALID`
- `CONNECTED_DATABASE_UNAVAILABLE`
- `SECRET_REFERENCE_MISSING`
- `AUDIT_PREWRITE_FAILED`

## POST /agent/chat
Purpose: preserve sandbox Create_database and add a future read-only connected database answer path.

### Request
```json
{
  "chat_id": "chat_id_here",
  "message": "Which customers ordered last week?",
  "model_profile_id": "model_profile_id_here",
  "database_profile_id": "database_profile_id_here",
  "target": "connected_database",
  "options": {}
}
```

### Connected Read-only Success Response Envelope
- The FastAPI endpoint returns the standard SAFY response envelope. The frontend helper safyApi() receives only payload.data.
```json
{
  "success": true,
  "data": {
    "summary": "Redacted natural-language answer.",
    "target": "connected_database",
    "database_profile_id": "database_profile_id_here",
    "sql_hash": "hash_here",
    "audit_id": "audit_id_here",
    "result_preview": []
  },
  "error": null,
  "meta": {
    "request_id": "request_id_here",
    "timestamp": "timestamp_here"
  }
}
```

### Connected Destructive Block Response
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "AGENT_CONNECTED_DB_DESTRUCTIVE_SQL_BLOCKED",
    "message": "Agent connected database execution is read-only only."
  },
  "meta": {
    "request_id": "request_id_here",
    "timestamp": "timestamp_here"
  }
}
```

## Response Redaction
Every endpoint must redact secrets in:

- `data`
- `error.details`
- audit ids and metadata
- logs
- test snapshots
