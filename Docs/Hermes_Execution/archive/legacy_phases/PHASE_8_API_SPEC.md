# Phase 8 API Spec

Executed by main-agent only. No sub-agents used.

## Overview

This document defines planned API behavior for Phase 8 real connected DB read-only support. It is planning-only and does not imply implementation is enabled.

Common API requirements:

- standard SAFY envelope
- redacted errors only
- stable error codes
- no raw secrets in request persistence or response payloads
- result rows may return to UI temporarily but are not stored in session history

## Planned endpoints

### `POST /profiles/database/save`

Purpose:

- save or update real DB profile metadata

Behavior:

- accepts DBMS metadata, connection metadata, env var references, optional mode flags
- may accept transient password input only if explicitly marked non-persistent
- persists metadata only, not raw secret values

Response:

- returns redacted profile metadata and profile ID

Errors:

- `VALIDATION_ERROR`
- `SECRET_VALUE_REJECTED`
- `DB_DRIVER_ERROR_REDACTED`

### `POST /profiles/database/test`

Purpose:

- test real DB connectivity without persisting transient credentials

Behavior:

- resolves env vars or uses transient session credential input
- verifies reachability, auth, and read-only compatibility
- returns normalized status only

Response:

- connection status
- DBMS type
- redacted host and database name
- read-only capability result

Errors:

- `DB_PROFILE_NOT_FOUND`
- `DB_CONNECTION_FAILED`
- `DB_AUTH_FAILED`
- `DB_SSL_REQUIRED`
- `DB_TIMEOUT`
- `DB_DRIVER_ERROR_REDACTED`

### `GET /profiles/database/{database_profile_id}/status`

Purpose:

- fetch last known redacted connection status for a database profile

Behavior:

- returns metadata only
- does not return raw secrets

Errors:

- `DB_PROFILE_NOT_FOUND`
- `DB_CONNECTION_FAILED`

### `GET /profiles/database/{database_profile_id}/schema`

Purpose:

- return normalized schema introspection metadata

Behavior:

- returns schema metadata only
- does not return sample rows by default
- may include counts/estimates and redacted comments if allowed

Errors:

- `DB_PROFILE_NOT_FOUND`
- `DB_SCHEMA_INTROSPECTION_FAILED`
- `DB_CONNECTION_FAILED`
- `DB_TIMEOUT`
- `DB_DRIVER_ERROR_REDACTED`

### `POST /query/check`

Purpose:

- classify and validate SQL before execution

Behavior:

- must not execute SQL
- enforces Phase 8 read-only policy
- requires database profile context for real DB mode
- detects sensitive SELECT, broad scans, row-limit issues, sample-row requests, and blocked operations
- returns one-time confirmation requirement when needed

Response fields planned:

- `check_id`
- `sql_hash`
- `statement_type`
- `decision`
- `warnings`
- `confirmation_required`
- `confirmation_expires_at`
- `allowed_to_attempt`
- `normalized_sql`
- `db_mode`

Errors:

- `DB_PROFILE_NOT_FOUND`
- `DB_UNSAFE_SQL_BLOCKED`
- `DB_INSERT_BLOCKED`
- `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED`
- `DB_SAMPLE_ROWS_APPROVAL_REQUIRED`

### `POST /query/execute`

Purpose:

- execute previously checked SQL in real DB read-only mode

Behavior:

- requires valid `check_id` + `sql_hash` binding
- requires user decision and confirmation token if applicable
- executes only allowed read-only SQL
- returns temporary rows and execution metadata
- does not store result rows in session history

Response fields planned:

- `execution_id`
- `dbms`
- `database_profile_id`
- `rows`
- `row_count`
- `truncated`
- `execution_time_ms`
- `timeout_applied`
- `redaction_applied`
- `audit_id`

Errors:

- `QUERY_CHECK_REQUIRED`
- `QUERY_CHECK_EXPIRED`
- `SQL_HASH_MISMATCH`
- `DB_PROFILE_NOT_FOUND`
- `DB_TIMEOUT`
- `DB_READONLY_VIOLATION`
- `DB_UNSAFE_SQL_BLOCKED`
- `DB_INSERT_BLOCKED`
- `DB_RESULT_LIMIT_EXCEEDED`
- `DB_DRIVER_ERROR_REDACTED`

### `POST /agent/chat`

Purpose:

- support agent-assisted real schema exploration and read-only SQL generation/execution

Behavior:

- agent must introspect real schema before SQL generation
- agent must explain SQL before execution
- agent must use `/query/check` and `/query/execute` flow
- blocked SQL may only be displayed as non-executed text with warning

Errors:

- `DB_PROFILE_NOT_FOUND`
- `DB_SCHEMA_INTROSPECTION_FAILED`
- `DB_UNSAFE_SQL_BLOCKED`
- `DB_INSERT_BLOCKED`
- `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED`
- `DB_DRIVER_ERROR_REDACTED`

## SAFY envelope

Planned standard response envelope remains:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

Planned error envelope remains:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "DB_UNSAFE_SQL_BLOCKED",
    "message": "Request blocked by SAFY read-only policy.",
    "details": {}
  },
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

## Stable error codes

Planned Phase 8 codes include:

- `DB_PROFILE_NOT_FOUND`
- `DB_CONNECTION_FAILED`
- `DB_AUTH_FAILED`
- `DB_SSL_REQUIRED`
- `DB_TIMEOUT`
- `DB_READONLY_VIOLATION`
- `DB_UNSAFE_SQL_BLOCKED`
- `DB_SCHEMA_INTROSPECTION_FAILED`
- `DB_RESULT_LIMIT_EXCEEDED`
- `DB_SAMPLE_ROWS_APPROVAL_REQUIRED`
- `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED`
- `DB_DRIVER_ERROR_REDACTED`
- `DB_INSERT_BLOCKED`

## Notes

- new endpoints beyond the suggested set may be added later if implementation needs them, but any additions remain planning-only until the user approves implementation
- sample rows require approval and should not be silently bundled into schema responses
- `INSERT` is blocked in Phase 8 and must never be returned as an executable path
