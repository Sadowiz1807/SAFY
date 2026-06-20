# Safy API Specification

## Purpose
Define the FastAPI/frontend/backend API contract for Safy v1.0.0.

## Scope
Covers common response formats, required endpoints, optional profile endpoints, Manual SQL behavior, recovery behavior, status conventions, and security notes.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Overview
The API exposes chat lifecycle, runtime recovery, sandbox health, database connection testing, agent chat, and Manual SQL execution. All responses must use a common envelope. API routes must delegate orchestration to Gateway and must not bypass SQL Guard, ToolRegistry, Permission Checker, audit, or runtime lock policy.

## 2. Base URL
Default local API base URL:

```txt
http://localhost:8000
```

Versioning may be added later. v1.0.0 docs assume unversioned local endpoints.

## 3. Common Headers
Recommended headers:

```txt
Content-Type: application/json
X-Request-ID: optional client-provided request ID
```

If `X-Request-ID` is not provided, the API must generate `request_id` and include it in response metadata.

## 4. Common Response Format
Success response:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "req_...",
    "timestamp": "..."
  }
}
```

## 5. Error Response Format
Error response:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "WORKSPACE_NOT_FOUND",
    "message": "...",
    "details": {}
  },
  "meta": {
    "request_id": "req_...",
    "timestamp": "..."
  }
}
```

## 6. HTTP Status Code Convention
Recommended conventions:
- `200`: successful operation.
- `201`: new chat/workspace/profile created if applicable.
- `400`: invalid input or policy validation failure.
- `403`: permission/policy block.
- `404`: missing chat/workspace/profile.
- `409`: state conflict, workspace ownership conflict, lock conflict, migration required.
- `422`: schema validation error.
- `500`: unexpected controlled server error.
- `503`: sandbox/audit/provider unavailable.

## 7. Error Code Table
Required error codes include:

```txt
INVALID_REQUEST
PROFILE_NOT_FOUND
SECRET_NOT_FOUND
DB_CONNECTION_FAILED
WORKSPACE_NOT_FOUND
WORKSPACE_LOCKED
WORKSPACE_CLOSING
WORKSPACE_OWNERSHIP_CONFLICT
CHAT_NOT_FOUND
CHAT_RECOVERED_OR_TRANSFERRED
SQL_PARSE_FAILED
SQL_VALIDATION_FAILED
SQL_POLICY_BLOCKED
SQL_RISK_CONFIRMATION_REQUIRED
AUDIT_WRITE_FAILED
AUDIT_REPAIR_REQUIRED
CONNECTED_DB_READ_ONLY_VIOLATION
MANUAL_WRITE_NOT_ENABLED
MIGRATION_REQUIRED
MIGRATION_FAILED
SANDBOX_UNAVAILABLE
TOOL_NOT_ALLOWED
TOOL_EXECUTION_FAILED
```

## 8. Required Endpoints
Required endpoints:

```txt
POST /chat/new
POST /chat/end
GET /runtime/recoverable-workspaces
POST /chat/recover
GET /sandbox/health
POST /db/test-connection
POST /agent/chat
POST /query/check
POST /query/execute
POST /manual-sql/execute  # compatibility/future alias, not primary API contract right-sidebar contract
```

## 9. Optional Recommended Endpoints
Optional but recommended profile endpoints:

```txt
GET /profiles
PUT /profiles/user
PUT /profiles/database
```

If enabled, profile endpoints must validate schema, redact secrets, store only env variable names, and audit profile changes.

## 10. Endpoint Details
### POST /chat/new
Purpose: Explicit UI new session.

Request:

```json
{
  "user_profile_id": "default",
  "database_profile_id": "local_postgres_dev"
}
```

Response data:

```json
{
  "chat_id": "chat_...",
  "status": "active"
}
```

Rules:
- Creates a new chat runtime record.
- Does not automatically create a sandbox unless workflow needs it.

### POST /chat/end
Purpose: End current chat and trigger cleanup policy.

Request:

```json
{
  "chat_id": "chat_...",
  "cleanup_workspace": true
}
```

Rules:
- Workspace cleanup must acquire workspace lock.
- Workspace status transitions must be safe and auditable.

### GET /runtime/recoverable-workspaces
Purpose: List workspaces recoverable after frontend lost chat state.

Response data:

```json
{
  "workspaces": [
    {
      "workspace_id": "ws_...",
      "chat_id": "chat_...",
      "status": "active",
      "created_at": "...",
      "expires_at": "..."
    }
  ]
}
```

### POST /chat/recover
Purpose: Atomically transfer a recoverable workspace to a new active chat.

Request:

```json
{
  "workspace_id": "ws_...",
  "new_chat_id": "chat_..."
}
```

Rules:
- One workspace -> one active chat_id.
- Old chat status becomes recovered/transferred.
- Stale old chat cannot execute into recovered workspace.

### GET /sandbox/health
Purpose: Check sandbox infrastructure.

Response data:

```json
{
  "healthy": true,
  "docker_available": true,
  "sqlite_runner_available": true
}
```

### POST /db/test-connection
Purpose: Test database profile connectivity.

Rules:
- Resolve secrets from env variable names.
- Do not expose raw credentials.
- For agent path, prefer/require read-only credentials.

### POST /agent/chat
Purpose: Main agent interaction endpoint.

Rules:
- If frontend has not called `/chat/new`, `/agent/chat` may lazy-create `chat_id`.
- Lazy-created chat_id is recovery-safe runtime state.
- Agent write/DDL is only allowed in sandbox.
- Agent connected database path is strict read-only.

Request:

```json
{
  "chat_id": "chat_...",
  "message": "Create an ecommerce schema",
  "target": "sandbox",
  "database_profile_id": "local_postgres_dev",
  "options": {
    "return_sql": true
  }
}
```

Response data should include relevant IDs:

```json
{
  "chat_id": "chat_...",
  "workflow_id": "wf_...",
  "workspace_id": "ws_...",
  "answer": "...",
  "skill_result": {}
}
```

### POST /manual-sql/execute
Purpose: Older compatibility endpoint or future alias for the user-controlled right-sidebar query flow. API contract primary contracts are `POST /query/check` and `POST /query/execute`.

Rules:
- Manual SQL Console is not an agent workflow.
- User must select target.
- SQL Guard parses/splits/validates every statement.
- High-risk requires safety check, visible 4-digit confirmation code, Yes decision, and audit pre-write.
- Sandbox mutation requires workspace lock.
- Connected database execution follows selected credential permission after safety gates.
- If the credential lacks permission, return `DB_PERMISSION_DENIED`.
- `manual_write_enabled` may remain profile metadata or UI warning; it must not silently block user query execution unless explicitly configured as a separate future policy.
- Agent path must never use `manual_write_enabled` to write connected DB.

Request:

```json
{
  "target": "sandbox",
  "chat_id": "chat_...",
  "workspace_id": "ws_...",
  "database_profile_id": null,
  "sql": "DROP TABLE temp_import;",
  "confirm_high_risk": true
}
```

Response data:

```json
{
  "execution_id": "exec_...",
  "risk_level": "destructive_schema",
  "confirmation_status": "confirmed",
  "execution_status": "succeeded",
  "audit_result_update_status": "succeeded",
  "rows_affected": 0
}
```

## 11. User Query Box API Behavior
Primary API contract right-sidebar query contracts are `POST /query/check` and `POST /query/execute`.

User query target behavior:
- `sandbox`: may allow SELECT/INSERT/UPDATE/DELETE/CREATE/ALTER/DROP owned workspace objects under user query rules.
- `connected_database`: executes according to selected credential permission after safety check, Yes decision, high-risk confirmation when required, and audit.
- If selected DB credential lacks permission, return `DB_PERMISSION_DENIED`.
- `manual_write_enabled` may remain as profile metadata or UI warning, but must not silently block user query execution unless explicitly configured as a separate future policy.
- Agent connected database path remains strict read-only and separate from this user-controlled path.

High-risk flow:
1. `/query/check` parses and risk-analyzes SQL without executing it.
2. Backend returns visible 4-digit numeric `confirmation_code` for high-risk queries.
3. Code is generated by backend, not LLM.
4. Code is bound to `check_id` + SQL hash + target + expiry.
5. `/query/execute` requires valid `check_id`, unchanged SQL/target, Yes decision, valid code, target permission pass, and audit pre-write.
6. Fail closed if audit pre-write fails.
7. Update audit result.
8. If result update fails after SQL executed, return `audit_result_update_status = failed` and record retryable audit repair task.

Compatibility note:
- `/manual-sql/execute` may remain as older compatibility endpoint or future alias, but it is not the primary API contract right-sidebar query contract.

## 12. Recovery API Behavior
Recovery rules:
- API must not crash when frontend request has no `chat_id`.
- If no `chat_id`, `/agent/chat` creates a new chat_id.
- If user wants old workspace, UI calls recovery flow.
- Recovery atomically transfers workspace ownership.
- Old chat must not execute after transfer.

## 13. Security Notes
API must enforce:
- No secrets in API responses.
- No raw API keys/passwords in profile JSON.
- No agent INSERT/UPDATE/DELETE/DROP on connected database.
- No raw SQL persisted by default.
- Manual SQL high-risk audit pre-write fail-closed.
- Request validation before Gateway orchestration.

## Implementation Notes
Implement API schemas as typed request/response models. Do not put policy checks only in route comments; Gateway/Core must enforce them.

## Related Documents
- `01_ARCHITECTURE.md`
- `03_DATA_SCHEMA.md`
- `04_CONFIG_SPEC.md`
- `05_SECURITY_POLICY.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`

## Addendum: Right Sidebar User Query Box API

Source update: `HERMES_MAIN_AGENT_EXECUTION_PLAN.md` adds explicit user query box endpoints. These endpoints refine the older Manual SQL Console contract without weakening safety.

### POST /query/check
Purpose: Check user-entered SQL from the right sidebar. This endpoint must never execute SQL.

Required behavior:
- Parse SQL.
- Classify statement type.
- Risk analyze.
- Validate target.
- Check schema snapshot if available.
- Return Safety Report.
- If high-risk, backend generates and returns a visible random 4-digit numeric `confirmation_code` for the UI to display to the user.
- `confirmation_code` is generated by backend, not LLM.
- `confirmation_code` is bound to `check_id` + SQL hash + target + expiry.

Response fields include:
- `check_id`
- `statement_type`
- `target`
- `risk_level`
- `affected_tables`
- `warnings`
- `confirmation_required`
- `confirmation_code` = visible backend-generated 4-digit numeric code when high-risk, otherwise null/omitted
- `confirmation_code_length` = 4 when high-risk
- `confirmation_expires_at`
- `allowed_to_attempt`

### POST /query/execute
Purpose: Execute a previously checked user query according to selected credential permission.

Required behavior:
- Requires valid prior `check_id`.
- Requires explicit Yes decision.
- Requires 4-digit code for high-risk checks.
- Wrong/expired code blocks execution.
- Changed SQL or target invalidates check/code.
- Executes according to actual DB credential permission.
- DB permission denial returns `DB_PERMISSION_DENIED`.
- Audits attempt and result.

Required error codes:
- `QUERY_CHECK_REQUIRED`
- `QUERY_CHECK_EXPIRED`
- `CONFIRMATION_CODE_REQUIRED`
- `CONFIRMATION_CODE_INVALID`
- `CONFIRMATION_CODE_EXPIRED`
- `SQL_RISK_CONFIRMATION_REQUIRED`
- `DB_PERMISSION_DENIED`
