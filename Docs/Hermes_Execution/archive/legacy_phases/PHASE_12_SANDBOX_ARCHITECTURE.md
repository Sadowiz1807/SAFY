# Phase 12 Sandbox Architecture — User Database Sandbox Runtime

## Architecture Summary

Phase 12 introduces a persistent user/project sandbox runtime. Docker-backed databases become managed runtime resources instead of developer-only integration test containers. SAFY creates, starts, restores/imports, observes, and binds these runtimes to the existing guarded query flow.

The sandbox is not a driver replacement. It supplies an isolated database target; SAFY still uses the DBMS driver appropriate to the sandbox engine.

## Runtime Components

- Sandbox Manager: orchestration layer for lifecycle, active sandbox policy, metadata, and API operations.
- Docker Sandbox Manager: container/network/volume lifecycle when Docker runtime is enabled.
- Restore/Import Manager: backup validation, restore execution, readonly user setup, schema cache generation, and progress tracking.
- Sandbox State Store: JSON state under `Data/sandboxes/`, separate from `Data/safy_profiles.json`.
- Schema Cache: stored schema summaries generated after restore/load for `/query/check` and UI schema browsing.
- Sandbox Profile Binding: runtime connection binding using generated readonly credentials.
- Query Integration: target-aware `/query/check` and `/query/execute` flow.
- Audit Writer: metadata-only action and query event records.
- UI Sandbox Manager: user-facing management console.

## Sandbox Manager

Responsibilities:

- create sandbox records with project/workspace scope
- enforce one active sandbox per project/workspace, or one active sandbox globally until workspace support is complete
- coordinate start/stop/delete transitions
- dispatch restore/import jobs
- expose status, schema, and audit metadata
- prevent per-agent-call sandbox creation
- fail closed on invalid state transitions

## Docker Sandbox Manager

Responsibilities:

- verify Docker availability when the Docker gate is enabled
- create isolated containers, volumes, and networks for sandbox runtime
- apply resource limits such as CPU, memory, storage, and timeout controls
- expose container connection details only internally
- provide lifecycle operations for start, stop, health, and delete
- distinguish runtime sandbox containers from developer test containers

Docker gate behavior:

- If runtime Docker validation is enabled and Docker is not running: `BLOCKED_DOCKER_ENGINE_NOT_RUNNING`.
- If Docker gate is disabled: Docker-heavy validation may be skipped as `SKIPPED_DOCKER_NOT_REQUIRED` and reports must not claim Docker runtime validation passed.

## Restore/Import Manager

Responsibilities:

- accept supported backup/source descriptors without persisting private contents
- confine backup paths to approved import directories or explicit user-selected paths
- run DBMS-appropriate restore commands with owner/admin credentials only for setup
- create generated readonly runtime query user after restore/init
- grant minimum required read privileges to readonly user
- revoke or avoid write privileges for runtime query user
- generate schema cache after restore/import
- write restore progress and final status metadata

Initial implementation priority should support PostgreSQL/Supabase-compatible restores first, including `.sql`, `.dump`, `.backup`, and `.backup.gz`. Follow-up adapters harden MySQL, SQL Server, Oracle, and SQLite.

## Sandbox State Store

Sandbox state must be stored separately from profile storage:

```text
Data/sandboxes/
Data/sandboxes/sandbox_<id>.json
Data/sandboxes/<sandbox_id>/metadata.json
Data/sandboxes/<sandbox_id>/restore_job.json
Data/sandboxes/<sandbox_id>/schema_cache.json
Data/sandboxes/<sandbox_id>/audit.jsonl
```

Recommended metadata fields:

- `sandbox_id`
- `project_id` / `workspace_id`
- `name`
- `dbms`
- `provider_compatibility` such as `supabase_postgres`
- `state`
- `active`
- `created_at`, `updated_at`
- `created_by`
- `container_ref` or runtime handle, not raw DSN
- `readonly_profile_ref` or runtime binding id
- `schema_cache_path`
- `restore_job_path`
- `last_error_code`
- `policy` with `read_only: true` and `write_sandbox_mode: false`

Secrets, raw DSNs, passwords, result rows, and backup contents must not be persisted in sandbox state.

## Schema Cache

Schema cache is generated during restore/import or explicit schema refresh. It may include table names, column names, types, nullable flags, indexes, and row-count estimates when safe. It must not include raw data rows.

`/query/check` may read schema cache for static validation hints but must not connect to the DB.

`GET /sandboxes/{sandbox_id}/schema` returns cache content or cache metadata. Refresh, if implemented, belongs to a separate controlled operation, not to `/query/check`.

## Sandbox Database Profile Binding

A sandbox binding links guarded query execution to the sandbox database using the readonly runtime user.

Rules:

- restore/setup may use owner/admin internally
- runtime query binding must use generated readonly credentials
- query execution must never use the owner/admin restore identity
- binding may be ephemeral/in-memory or referenced by a generated profile id
- durable sandbox runtime state remains under `Data/sandboxes/`

## Query Integration

`/query/check` accepts target metadata:

```json
{
  "target": "sandbox",
  "sandbox_id": "sandbox_123",
  "sql": "SELECT ..."
}
```

`/query/check` performs SQL Guard and metadata/cache validation only. It records target and `sandbox_id` binding in check state and returns `check_id` plus `sql_hash`.

`/query/execute` requires the matching `check_id`, `sql_hash`, target, and `sandbox_id`. Only then may it resolve the sandbox readonly binding and execute through the appropriate driver.

## Lifecycle State Machine

Recommended states:

```text
created
starting
restoring
ready
failed
stopping
stopped
deleting
deleted
```

Allowed transitions:

- `created -> starting`
- `starting -> restoring` when a restore/import is requested
- `starting -> ready` when initialized without restore
- `restoring -> ready` on successful restore/import and readonly user setup
- `starting/restoring -> failed` on setup error
- `ready -> stopping`
- `stopping -> stopped`
- `stopped -> starting`
- `created/stopped/failed/ready -> deleting`
- `deleting -> deleted`

Invalid transitions fail closed and emit metadata-only audit events.

## Active Sandbox Policy

Preferred enforcement is one active sandbox per project/workspace:

- `workspace_id + project_id + active=true` must be unique.
- Activating a new sandbox requires stopping/deactivating the previous active sandbox or explicit user confirmation.
- Agent cannot create or activate a sandbox silently.

Temporary fallback if project/workspace scoping is incomplete:

- Enforce one active sandbox globally.
- Keep `project_id`/`workspace_id` fields in the data model for future migration.

## Project/Workspace Model

Every sandbox record should carry project/workspace metadata even if the initial UI only exposes a default workspace. Query requests must include or resolve project/workspace context so target binding cannot accidentally cross projects.

## DBMS Adapter Plan

Planned support:

- PostgreSQL/Supabase-compatible PostgreSQL: Docker PostgreSQL runtime, `pg_restore`/`psql`, readonly role grants.
- MySQL: Docker MySQL runtime, `mysql` restore, readonly grants.
- SQL Server: Docker SQL Server runtime, `sqlcmd`/backup restore strategy, readonly login/user.
- Oracle: Oracle container/runtime strategy, Data Pump/import strategy, readonly user/schema grants.
- SQLite: file-copy sandbox strategy with isolated working copy and read-only connection mode where possible.

Implementation priority is PostgreSQL/Supabase-compatible first.

## Future Write-Sandbox Extension Point

Architecture may include a disabled policy shape:

```json
{
  "read_only": true,
  "write_sandbox_mode": false,
  "future_write_mode_allowed": false
}
```

No Phase 12 endpoint, UI control, or agent action may enable write execution. Future phases must add separate policy gates, UI confirmations, audit fields, and validation before write-sandbox mode can be used.
