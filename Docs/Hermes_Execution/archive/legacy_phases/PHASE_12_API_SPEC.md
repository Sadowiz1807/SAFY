# Phase 12 API Spec — User Database Sandbox Runtime

## API Principles

- Sandbox APIs manage persistent runtime state.
- Query APIs remain guarded by `/query/check -> /query/execute`.
- `/query/check` never connects to a database or container.
- `/query/execute` uses the sandbox readonly runtime binding only after validating `check_id` and `sql_hash`.
- API responses and audit logs must not persist raw result rows, secrets, DSNs, passwords, or backup contents.

## Common Sandbox Object

Example shape:

```json
{
  "sandbox_id": "sandbox_123",
  "name": "Project copy",
  "project_id": "project_default",
  "workspace_id": "workspace_default",
  "dbms": "postgresql",
  "provider_compatibility": "supabase_postgres",
  "state": "ready",
  "active": true,
  "read_only": true,
  "write_sandbox_mode": false,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:10:00Z",
  "schema_cache_available": true,
  "last_error_code": null
}
```

Do not include raw DSN or passwords in this object.

## POST `/sandboxes`

Create a sandbox metadata record. This must not be silently invoked by the agent without user confirmation.

Request:

```json
{
  "name": "Supabase restore sandbox",
  "project_id": "project_default",
  "workspace_id": "workspace_default",
  "dbms": "postgresql",
  "provider_compatibility": "supabase_postgres",
  "activate": true
}
```

Behavior:

- creates state `created`
- enforces active sandbox policy if `activate=true`
- may require user confirmation if another sandbox is active
- does not restore data unless restore is explicitly requested

Responses:

- `201 Created` with sandbox object
- `409 Conflict` for active sandbox policy violation
- `400 Bad Request` for unsupported DBMS or invalid project/workspace

## GET `/sandboxes`

List sandboxes visible in the current project/workspace.

Query parameters:

- `project_id`
- `workspace_id`
- `state`
- `active`

Response:

```json
{
  "sandboxes": []
}
```

## GET `/sandboxes/{sandbox_id}`

Return sandbox metadata and current lifecycle state. Must not expose secrets or raw DSNs.

## POST `/sandboxes/{sandbox_id}/start`

Start the sandbox runtime.

Request:

```json
{
  "activate": true
}
```

Behavior:

- checks Docker availability when required
- transitions `created/stopped -> starting -> ready` if no restore is pending
- enforces active sandbox policy
- writes metadata-only audit

Errors:

- `BLOCKED_DOCKER_ENGINE_NOT_RUNNING` if Docker gate enabled and Docker unavailable
- `409 Conflict` for invalid lifecycle transition or active sandbox conflict

## POST `/sandboxes/{sandbox_id}/stop`

Stop the sandbox runtime.

Behavior:

- transitions `ready -> stopping -> stopped`
- deactivates if it was active
- writes metadata-only audit

## DELETE `/sandboxes/{sandbox_id}`

Delete sandbox runtime resources and metadata.

Behavior:

- transitions to `deleting -> deleted`
- removes containers/volumes according to retention policy
- removes or archives sandbox metadata according to audit retention policy
- does not delete source backups

## POST `/sandboxes/{sandbox_id}/restore`

Start restore/import for a sandbox. Requires explicit user confirmation in UI/agent flows.

Request:

```json
{
  "source_type": "backup_file",
  "source_ref": "redacted-or-approved-path-ref",
  "format": "backup_gz",
  "confirm_restore": true,
  "env_gate": "SAFY_ENABLE_SUPABASE_BACKUP_RESTORE"
}
```

Behavior:

- validates source path without persisting backup contents
- starts runtime if needed
- transitions to `restoring`
- runs restore/import with owner/admin setup identity only
- creates generated readonly runtime user
- generates schema cache
- transitions to `ready` on success

Statuses:

- `SKIPPED_SUPABASE_BACKUP_RESTORE_NOT_REQUIRED`
- `BLOCKED_BACKUP_MISSING`
- `BLOCKED_BACKUP_RESTORE_FAILED`
- `PASS_SUPABASE_BACKUP_RESTORE`

## GET `/sandboxes/{sandbox_id}/schema`

Return sandbox schema cache. This endpoint should not be confused with `/query/check`; `/query/check` still does not connect to DB.

Response:

```json
{
  "sandbox_id": "sandbox_123",
  "generated_at": "2026-01-01T00:12:00Z",
  "dbms": "postgresql",
  "tables": [
    {
      "schema": "public",
      "name": "customers",
      "columns": [
        {"name": "id", "type": "uuid", "nullable": false}
      ]
    }
  ]
}
```

No result rows are included.

## GET `/sandboxes/{sandbox_id}/audit`

Return metadata-only audit events.

Response:

```json
{
  "events": [
    {
      "timestamp": "2026-01-01T00:15:00Z",
      "action": "query_execute",
      "sandbox_id": "sandbox_123",
      "project_id": "project_default",
      "dbms": "postgresql",
      "status": "allowed",
      "check_id": "check_abc",
      "sql_hash": "sha256:...",
      "row_count": 25,
      "error_code": null
    }
  ]
}
```

No raw rows, secrets, DSNs, passwords, or backup contents are allowed.

## Query Flow Extension

### POST `/query/check`

Request extension:

```json
{
  "target": "sandbox",
  "sandbox_id": "sandbox_123",
  "sql": "SELECT * FROM customers LIMIT 10"
}
```

Behavior:

- validates SQL with SQL Guard
- validates target metadata and sandbox state from store/cache only
- binds `target=sandbox` and `sandbox_id` into check state
- computes `sql_hash`
- does not connect to DB
- does not execute SQL
- does not refresh live schema

Response:

```json
{
  "check_id": "check_abc",
  "sql_hash": "sha256:...",
  "allowed": true,
  "target": "sandbox",
  "sandbox_id": "sandbox_123",
  "expires_at": "2026-01-01T00:20:00Z"
}
```

### POST `/query/execute`

Request extension:

```json
{
  "check_id": "check_abc",
  "sql_hash": "sha256:...",
  "target": "sandbox",
  "sandbox_id": "sandbox_123"
}
```

Behavior:

- verifies `check_id`
- verifies exact `sql_hash`
- verifies unexpired and unconsumed check
- verifies target and sandbox binding match check state
- verifies SQL Guard approval and read-only policy
- resolves sandbox readonly database binding
- executes through the DBMS driver
- returns rows in HTTP response only
- persists metadata-only audit event with row count/error code

Response:

```json
{
  "columns": ["id", "name"],
  "rows": [["...", "..."]],
  "row_count": 1,
  "target": "sandbox",
  "sandbox_id": "sandbox_123"
}
```

Rows must not be stored after the response lifecycle.
