# Safy Data Schema

## Purpose
Define where Safy stores data, the expected schemas, and which fields must never be persisted.

## Scope
Covers profile JSON files, runtime SQLite DB, audit SQLite DB, schema versioning, AgentExecutionContext, SkillResult, ToolResult, ErrorResponse, schema snapshots, retention, redaction, and migration rules.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Data Storage Overview
Safy v1.0.0 uses local files and local SQLite databases for profile/runtime/audit state.

Required data files:

```txt
Data/User/user_profiles.json
Data/Database_management/database_profiles.json
Data/safy_runtime.db
Data/safy_audit.db
```

Profile JSON files store metadata and environment variable names only. Raw API keys and raw DB passwords must not appear in JSON, runtime DB, audit DB, frontend state, API responses, or logs.

## 2. Data Directory Structure
Required structure:

```txt
Data/
  User/
    user_profiles.json
  Database_management/
    database_profiles.json
  safy_runtime.db
  safy_audit.db
```

Runtime DB stores local lifecycle state. Audit DB stores security/action records. Both DBs must include `schema_version` and must be checked before serving requests.

## 3. user_profiles.json Schema
Minimum shape:

```json
{
  "profiles": [
    {
      "profile_id": "default",
      "display_name": "Default User",
      "provider": "openai",
      "model": "gpt-4.1",
      "api_key_env": "SAFY_OPENAI_API_KEY"
    }
  ]
}
```

Rules:
- `api_key_env` stores the env variable name, not the key value.
- No raw API keys in this file.
- Profile API responses must redact secret-related values if any are accepted transiently.

## 4. database_profiles.json Schema
Minimum shape:

```json
{
  "profiles": [
    {
      "profile_id": "local_postgres_dev",
      "dbms": "postgresql",
      "host": "localhost",
      "port": 5432,
      "database": "app_db",
      "username": "safy_readonly",
      "password_env": "SAFY_DB_PASSWORD",
      "readonly_password_env": "SAFY_DB_READONLY_PASSWORD",
      "manual_password_env": "SAFY_DB_MANUAL_PASSWORD",
      "manual_write_enabled": false,
      "allowed_sqlite_path": null
    }
  ]
}
```

Rules:
- Default `manual_write_enabled` is `false`.
- Agent connected database execution ignores `manual_write_enabled` and remains read-only.
- User query box connected database execution follows selected credential permission after safety check, Yes decision, high-risk 4-digit confirmation when required, and audit.
- If selected DB credential lacks permission, return `DB_PERMISSION_DENIED`.
- `manual_write_enabled` may remain profile metadata/UI warning; it must not silently block user query execution unless explicitly configured as a separate future policy.
- Profile validation must reject admin/root/superuser profiles for agent execution by default.
- Connected SQLite path must be normalized and validated.

## 5. Runtime SQLite DB Schema
Runtime DB stores chat/workspace/workflow state, schema snapshots, object provenance, workspace locks, and schema version.

Required baseline tables:

```sql
CREATE TABLE chat_runtime (
    chat_id TEXT PRIMARY KEY,
    user_profile_id TEXT,
    database_profile_id TEXT,
    active_workspace_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE sandbox_workspaces (
    workspace_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    dbms TEXT NOT NULL,
    status TEXT NOT NULL,
    connection_profile_id TEXT,
    workspace_database TEXT,
    workspace_schema TEXT,
    sqlite_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE workflow_object_provenance (
    object_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    created_step_id TEXT,
    object_type TEXT NOT NULL,
    object_name TEXT NOT NULL,
    rollback_allowed_until_status TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE schema_snapshots (
    schema_snapshot_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    source TEXT NOT NULL,
    invalidated_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE workspace_locks (
    workspace_id TEXT PRIMARY KEY,
    lock_owner TEXT NOT NULL,
    lock_reason TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE schema_version (
    component TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
```

Runtime rules:
- Do not persist `active_connection_id` as durable state.
- Persist `database_profile_id` and reconnect after restart.
- Runtime DB must not store raw SQL with sensitive literals.
- Workspace mutation invalidates latest `schema_snapshot_id`.
- Cleanup and Manual SQL mutation acquire `workspace_locks`.

## 6. Audit SQLite DB Schema
Audit DB records security/action events and high-risk operations.

Required fields:

```sql
CREATE TABLE audit_events (
    audit_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    chat_id TEXT,
    workspace_id TEXT,
    endpoint TEXT,
    action TEXT NOT NULL,
    target TEXT,
    risk_level TEXT,
    confirmation_status TEXT,
    statement_hash TEXT,
    redacted_sql TEXT,
    raw_sql_stored INTEGER NOT NULL DEFAULT 0,
    execution_status TEXT,
    audit_result_update_status TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_repair_tasks (
    repair_task_id TEXT PRIMARY KEY,
    audit_id TEXT,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE schema_version (
    component TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
```

Audit rules:
- Store `statement_hash` and `redacted_sql`.
- Raw SQL is not stored by default.
- High-risk Manual SQL requires audit pre-write.
- If audit pre-write fails, execution fails closed.
- If post-execution audit update fails after SQL executed, return `audit_result_update_status = failed` and create retryable audit repair task.

## 7. schema_version Table
Initial versions:

```txt
runtime_schema_version = 1
audit_schema_version = 1
```

Startup must check schema versions before serving requests. Version mismatch returns controlled `MIGRATION_REQUIRED` or `MIGRATION_FAILED`.

## 8. AgentExecutionContext Schema
Required logical shape:

```python
agent_execution_context = {
    "request_id": "req_...",
    "chat_id": "chat_...",
    "workflow_id": "wf_...",
    "workspace_id": "ws_...",
    "user_profile_id": "default",
    "database_profile_id": "local_postgres_dev",
    "target": "sandbox|connected_database",
    "dbms": "postgresql|mysql|sqlite",
    "skill_name": "Create_database",
    "skill_policy": {},
    "toolsets": [],
    "schema_snapshot_id": "snap_...",
    "permissions": {},
    "risk_context": {}
}
```

Rules:
- Generated SQL is in-memory only by default.
- Store only statement hash, redacted SQL, schema snapshot ID, and verification result unless explicit local debug mode is enabled.

## 9. SkillResult Schema
SkillResult must include:

```json
{
  "success": true,
  "skill_name": "Create_database",
  "workflow_id": "wf_...",
  "workspace_id": "ws_...",
  "created_tables": ["users", "products"],
  "created_tables_note": "Backward-compatible summary; created_objects is canonical.",
  "created_objects": {
    "tables": [],
    "views": [],
    "indexes": [],
    "constraints": []
  },
  "schema_snapshot_id": "snap_...",
  "verification_result": {},
  "risk_level": "low",
  "warnings": []
}
```

`created_objects` is canonical and must preserve tables, views, indexes, and constraints.

## 10. ToolResult Schema
ToolResult must be normalized:

```json
{
  "success": true,
  "tool_name": "execute_select_tool",
  "data": {},
  "error": null,
  "risk_level": "read_only",
  "audit_ref": "audit_...",
  "metadata": {}
}
```

## 11. ErrorResponse Schema
ErrorResponse uses the common API error envelope:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "SQL_POLICY_BLOCKED",
    "message": "...",
    "details": {}
  },
  "meta": {
    "request_id": "req_...",
    "timestamp": "..."
  }
}
```

## 12. Schema Snapshot Structure
Schema snapshots summarize current workspace/connected DB schema for planning and verification.

Required fields:

```json
{
  "schema_snapshot_id": "snap_...",
  "workspace_id": "ws_...",
  "source": "sandbox|connected_database",
  "dbms": "postgresql",
  "tables": [],
  "views": [],
  "indexes": [],
  "constraints": [],
  "created_at": "...",
  "invalidated_at": null
}
```

## 13. Retention and Redaction Rules
Rules:
- No raw API keys or DB passwords anywhere in JSON/runtime/audit.
- Runtime DB must not store raw SQL with sensitive literals.
- Audit stores statement hash and redacted SQL.
- Raw SQL is not persisted by default.
- Redaction must cover passwords, API keys, bearer tokens, DSNs, nested JSON secrets, and SQL string literals when configured.

## 14. Migration Rules
Rules:
- Runtime DB and Audit DB must both include schema_version.
- Startup checks schema version before serving requests.
- Migration failure returns controlled startup/runtime error.
- Audit DB migration must succeed before high-risk Manual SQL is allowed.
- Version mismatch returns `MIGRATION_REQUIRED` or `MIGRATION_FAILED`.

## Implementation Notes
Create DB migrations before API implementation. Implement schema checks as startup gates, not optional runtime warnings.

## Related Documents
- `01_ARCHITECTURE.md`
- `02_API_SPEC.md`
- `04_CONFIG_SPEC.md`
- `05_SECURITY_POLICY.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`
