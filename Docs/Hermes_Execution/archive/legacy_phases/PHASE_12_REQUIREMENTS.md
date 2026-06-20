# Phase 12 Requirements — User Database Sandbox Runtime

## Purpose

Phase 12 defines SAFY's user-facing database sandbox runtime. The sandbox lets a user or project restore/import database data into an isolated runtime, inspect schema, and run guarded read-only queries without touching production databases.

The sandbox exists to:

- restore backups safely into an isolated database runtime
- analyze data without touching a real/production database
- test generated SQL before any future real database execution path
- isolate agent-generated SQL behind the existing SQL Guard and query check/execute flow
- convert Docker from developer validation infrastructure into a managed runtime feature
- prepare a future write-sandbox mode without enabling writes in Phase 12

## Scope

Phase 12 planning covers a full sandbox runtime, not a test fixture:

- sandbox lifecycle: create, start, restore/import, ready, stop, delete
- Docker runtime management where enabled
- restore/import workflow
- sandbox schema cache
- query binding to a sandbox target
- metadata-only audit trail
- readonly sandbox runtime user
- Sandbox Manager UI
- one active sandbox policy
- project/workspace-aware data model
- future write-sandbox extension point, disabled by policy

## Non-Goals

Phase 12 does not include:

- real LLM provider integration
- model profile implementation beyond naming boundaries
- write query enablement
- production database write operations
- automatic agent sandbox creation without user confirmation
- storing raw query result rows
- storing raw secrets, raw DSNs, raw passwords, or private backup contents
- committing private backups
- claiming cloud/provider validation unrelated to sandbox runtime
- claiming `PASS_PHASE_12_SANDBOX_COMPLETE` during planning

## Profile and Runtime Boundaries

Phase 12 must distinguish these concepts:

- `real_database_profile`: connection metadata for an external user database
- `sandbox_database_profile`: generated runtime binding for a sandbox database, using the readonly query user
- `model_profile`: future LLM/model configuration, out of scope for Phase 12
- `provider_profile` / provider mapping metadata: DB provider hints such as Supabase, Cloud SQL, or Aurora, not the sandbox state itself

Sandbox runtime state must live outside `Data/safy_profiles.json`, for example:

```text
Data/sandboxes/
Data/sandboxes/sandbox_<id>.json
Data/sandboxes/<sandbox_id>/metadata.json
Data/sandboxes/<sandbox_id>/restore_job.json
Data/sandboxes/<sandbox_id>/schema_cache.json
```

If query execution needs a profile reference, it may use a runtime binding or reference profile, but durable sandbox state remains in `Data/sandboxes/`.

## DBMS Scope

Planned support covers all DBMS already supported by SAFY:

- PostgreSQL
- Supabase-compatible PostgreSQL
- MySQL
- SQL Server
- Oracle
- SQLite

Implementation priority is staged:

- Planned support: all listed DBMS
- Implementation priority: PostgreSQL/Supabase-compatible first
- Follow-up/hardened support: MySQL, SQL Server, Oracle, SQLite

The first implementation pass must not pretend all runtime DBMS adapters are complete if only PostgreSQL/Supabase-compatible sandboxing is delivered.

## Sandbox Still Needs Drivers

Sandbox does not replace database drivers. It creates or binds an isolated runtime target, then SAFY still uses the appropriate driver:

- PostgreSQL sandbox -> PostgreSQL driver
- Supabase backup restored into PostgreSQL sandbox -> PostgreSQL driver
- MySQL sandbox -> MySQL driver
- SQL Server sandbox -> SQL Server driver
- Oracle sandbox -> Oracle driver
- SQLite sandbox -> sqlite3/file-copy strategy

## Read-Only Policy

Writes are not enabled in Phase 12. All query execution remains read-only.

Allowed baseline:

- `SELECT`
- `WITH ... SELECT`
- read-only metadata queries when already allowed by SQL Guard and driver policy

Blocked baseline:

- `INSERT`, `UPDATE`, `DELETE`
- `DROP`, `ALTER`, `CREATE`, `TRUNCATE`
- `MERGE`
- `CALL`, `EXEC`, `EXECUTE`
- procedural blocks
- multi-statement execution
- any DDL/DML/write operation

Future write-sandbox mode may be represented as a disabled policy field, but no runtime path may enable it in Phase 12.

## Active Sandbox Policy

Phase 12 enforces one active sandbox at a time, preferably one active sandbox per project/workspace. If full project/workspace support is not implemented yet, the fallback is one active sandbox globally with the data model prepared for project/workspace scoping.

Correct lifecycle:

```text
Create sandbox -> restore/import data -> status READY -> user/agent query many times -> stop/delete/reset when user decides
```

Incorrect and explicitly rejected:

```text
Every agent request creates a new sandbox -> restore again -> query -> delete
```

The sandbox is persistent runtime state controlled by user/project lifecycle, not per-agent-call ephemeral infrastructure.

## Restore/Import Requirements

- Restore/import may use owner/admin credentials only internally for setup.
- Runtime query access must use a generated readonly sandbox user.
- Restore/import must generate or refresh schema cache.
- Restore/import progress and status must be observable.
- Supported source planning must include `.sql`, `.dump`, `.backup`, `.backup.gz`, DBMS-native dumps, and SQLite file-copy/import strategy where applicable.
- Supabase backup restore is private test data and env-gated.

Supabase backup rules:

- Do not commit real backup files into the repository.
- Do not persist backup contents in reports.
- Treat backup path/content as private and untracked.
- Default planning and tests may pass without private restore unless the explicit restore gate is enabled.
- If restore gate is enabled, missing backup or restore failure blocks PASS.

## `/query/check` Requirements

Hard boundary:

- `/query/check` must not open database connections.
- `/query/check` must not execute SQL.
- `/query/check` must not validate by touching a live DB/container.
- `/query/check` may use request metadata, schema cache, stored schema summaries, and SQL Guard analysis.

If schema validation is needed, use `GET /sandboxes/{sandbox_id}/schema` or the schema cache generated during restore/load.

## `/query/execute` Requirements

Sandbox execution does not bypass existing SAFY safety. `/query/execute` must require:

- valid `check_id`
- matching `sql_hash`
- unexpired check state
- target binding
- `sandbox_id` binding when target is sandbox
- no consumed check
- SQL Guard approval
- read-only policy

## UI Requirements

Phase 12 requires a full Sandbox Manager UI:

- create sandbox
- select DBMS/type
- select backup/dump/source
- start sandbox
- stop sandbox
- delete sandbox
- restore/import progress
- status badges
- schema viewer
- query panel bound to sandbox
- audit/timeline metadata
- clear `SANDBOX` vs `REAL DB` target badge
- warning when user is about to run on real DB instead of sandbox

## Agent Requirements

- Agent may use an existing active sandbox.
- Agent must not silently create a sandbox.
- Agent may propose sandbox creation, but user confirmation is required.
- Agent may request restore/import only with explicit user confirmation.
- Agent may auto-run read-only `SELECT` on sandbox only through `/query/check -> /query/execute`.
- Agent must not run write queries in Phase 12.

## Result and Audit Requirements

Result rows:

- Do not persist result rows.
- Do not store raw result data in sandbox metadata.
- Do not store query result rows in audit logs.
- API/UI may return result rows temporarily in the HTTP response.

Audit is metadata-only and may store:

- timestamp
- action
- sandbox id or sandbox id hash
- project/workspace id
- DBMS type
- operation status
- `sql_hash`
- `check_id`
- row count
- error code

Audit must not store raw secrets, raw DSNs, raw passwords, result rows, or full backup contents.

## Testing Requirements

Testing must include unit, API, state store, Docker manager, restore/import, query check/execute, no-persistence, no-secret, UI, regression, and env-gated Docker/private-backup tests.

## PASS/BLOCKED/SKIPPED Semantics

Planning status:

- `PASS_PHASE_12_PLANNING_READY`: planning artifacts are complete and internally consistent.

Implementation status for a later phase only:

- `PASS_PHASE_12_SANDBOX_COMPLETE`: implementation and validation completed.

Docker and backup statuses:

- `BLOCKED_DOCKER_ENGINE_NOT_RUNNING`: Docker gate enabled but Docker unavailable.
- `SKIPPED_DOCKER_NOT_REQUIRED`: Docker gate disabled; Docker-heavy runtime tests skipped honestly.
- `BLOCKED_BACKUP_MISSING`: Supabase restore gate enabled but backup missing.
- `BLOCKED_BACKUP_RESTORE_FAILED`: Supabase restore gate enabled but restore failed.
- `SKIPPED_SUPABASE_BACKUP_RESTORE_NOT_REQUIRED`: private Supabase restore gate disabled.
- `PASS_SUPABASE_BACKUP_RESTORE`: gated private restore actually completed successfully.
