# Phase 8 Adapter Design

Executed by main-agent only. No sub-agents used.

## Design goal

Define a generic real connected DB adapter contract for read-only SAFY execution in Phase 8 without selecting implementation dependencies blindly. Current repository behavior is mock-only, so this document is a planning artifact only.

## Recommended conceptual interface

```text
ConnectedDBAdapter
  - connect()
  - test_connection()
  - introspect_schema()
  - explain(sql)
  - execute_readonly(sql, params, limits)
  - close()
```

## Normalized models

Planned normalized models:

```text
ConnectionProfile
ConnectionStatus
SchemaIntrospectionResult
TableInfo
ColumnInfo
QueryCheckResult
ReadonlyQueryResult
AdapterError
```

### `ConnectionProfile`

Suggested fields:

- `database_profile_id`
- `dbms`
- `host`
- `port`
- `database`
- `username`
- `password_env`
- optional `dsn_env`
- optional SSL metadata flags
- `read_only_required`
- optional transient secret binding metadata

### `ConnectionStatus`

Suggested fields:

- `connected`
- `dbms`
- `database`
- `host_redacted`
- `read_only_verified`
- `server_version_redacted`
- `latency_ms`
- `error` as normalized `AdapterError | null`

### `SchemaIntrospectionResult`

Suggested fields:

- `schemas`
- `tables`
- `views`
- `indexes`
- `constraints`
- `estimated_row_counts`
- `comments`
- `introspection_time_ms`
- `redaction_applied`

### `TableInfo`

Suggested fields:

- `schema_name`
- `table_name`
- `table_type`
- `estimated_row_count`
- `comment_redacted`
- `columns`
- `primary_key`
- `foreign_keys`
- `indexes`

### `ColumnInfo`

Suggested fields:

- `schema_name`
- `table_name`
- `column_name`
- `data_type`
- `nullable`
- `default_redacted`
- `is_primary_key`
- `is_foreign_key`
- `comment_redacted`

### `QueryCheckResult`

This remains the normalized output from `/query/check`, not from adapters directly. Adapters consume only validated read-only execution requests.

### `ReadonlyQueryResult`

Suggested fields:

- `execution_id`
- `rows`
- `row_count`
- `truncated`
- `execution_time_ms`
- `timeout_applied`
- `redaction_applied`
- `columns`
- `warnings`

### `AdapterError`

Suggested fields:

- `code`
- `message_redacted`
- `retryable`
- `dbms`
- `safe_details`

## DBMS-specific adapters

Planned adapter classes:

```text
MySQLAdapter
PostgresAdapter
SQLiteConnectedFileAdapter
```

## Sync vs async recommendation

Recommendation:

- keep adapter methods synchronous in the first Phase 8 implementation unless an existing async boundary in FastAPI already requires async wrappers
- synchronous DB drivers are simpler to validate for strict read-only control and timeout handling in the current SAFY codebase
- if async endpoints are later needed, wrap sync adapter execution in controlled worker boundaries rather than designing fully separate async adapter contracts immediately

Reasoning from current repository state:

- existing API and orchestration code is synchronous-first
- current mock adapter path does not establish an async contract worth preserving

## Dependency recommendation

Do not choose final dependencies blindly. Recommended options by DBMS:

- MySQL: prefer a maintained DB-API compatible driver with predictable timeout and transaction controls
- PostgreSQL: prefer a maintained driver with explicit read-only transaction/session controls
- SQLite: use the standard library `sqlite3` in read-only URI mode if repository constraints permit

Selection criteria:

- stable Windows compatibility
- straightforward timeout support
- ability to normalize driver errors cleanly
- ability to enforce read-only transaction/session behavior
- acceptable packaging burden for SAFY local development

## Timeout handling

Adapter plan must support:

- connection timeout
- statement timeout
- introspection timeout
- clear distinction between timeout during check-phase metadata retrieval and execute-phase query execution
- normalized timeout error code: `DB_TIMEOUT`

Timeout policy should be set at adapter call sites and echoed into result metadata.

## Row limit handling

Adapter plan must support:

- enforced maximum row count per execution
- result truncation metadata
- optional server-side and client-side safety caps
- broad-scan confirmation when requested or inferred limits exceed policy thresholds

`ReadonlyQueryResult` should include row count and truncation flags even when the underlying DBMS reports partial counts differently.

## Redaction boundary

Redaction must occur at multiple layers:

- credential input boundary
- driver error normalization boundary
- schema metadata boundary for comments/descriptions where needed
- result rendering boundary
- audit/session persistence boundary

Adapters must never emit raw secrets into exceptions that cross module boundaries.

## Driver error normalization

Each adapter must map engine-specific failures to normalized SAFY errors, including:

- `DB_CONNECTION_FAILED`
- `DB_AUTH_FAILED`
- `DB_SSL_REQUIRED`
- `DB_TIMEOUT`
- `DB_READONLY_VIOLATION`
- `DB_SCHEMA_INTROSPECTION_FAILED`
- `DB_DRIVER_ERROR_REDACTED`

Raw stack traces and raw DSNs must be stripped before errors are returned to API/UI/audit/session layers.

## Read-only transaction enforcement

Plan DBMS-specific enforcement:

- MySQL: use DB/session settings and DB user privileges that enforce read-only behavior where possible
- PostgreSQL: use read-only transaction or session settings and read-only DB roles where possible
- SQLite: use read-only file open mode and path confinement

Read-only safety should not rely only on SQL text classification. DB privilege and session-level enforcement should be a second boundary.

## DB privilege expectation

Planned operating assumption:

- SAFY should connect using DB credentials that are themselves read-only whenever possible
- SQL Guard remains mandatory even when DB credentials are read-only
- Phase 8 should not assume read-only credentials alone are sufficient safety protection

## Optional Docker integration strategy

Plan optional integration by subphase:

- Phase 8.1 MySQL first: Docker-backed read-only test database
- Phase 8.2 PostgreSQL second: Docker-backed read-only test database
- Phase 8.3 SQLite: temporary path-confined files, no Docker required

Integration tests must:

- skip cleanly when Docker or env vars are absent
- never exercise write support as a success path
- verify normalized errors and redaction behavior

## Explicit blocking of INSERT / write / destructive SQL

The adapter design assumes SQL Guard blocks unsafe SQL before adapter execution. Even so, adapter-facing execution entry points should remain named and scoped to read-only use only.

Required design rule:

- do not expose a generic `execute(sql)` method for Phase 8
- expose only `execute_readonly(...)`

This keeps the implementation boundary aligned with the user requirement that INSERT and all data-changing SQL remain blocked in Phase 8.

## Integration with existing SAFY modules

Planned integration points:

- `Gateway/query_orchestrator.py` remains the policy and confirmation gate
- `Gateway/sql_guard.py` remains mandatory before any adapter execution
- `Apps/Api/safy_api/main.py` exposes planned profile, status, schema, check, and execute endpoints
- `Core/agent.py` must use schema introspection plus guarded execution only
- `Audit/audit_store.py` and `State/runtime_db.py` persist redacted summaries, not result rows

## Recommendation summary

Recommended first implementation order remains:

1. `MySQLAdapter`
2. `PostgresAdapter`
3. `SQLiteConnectedFileAdapter`

Recommendation remains planning-only until the user explicitly approves implementation.
