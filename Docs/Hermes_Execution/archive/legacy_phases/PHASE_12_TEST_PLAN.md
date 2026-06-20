# Phase 12 Test Plan — User Database Sandbox Runtime

## Testing Principles

- Do not fake validation.
- Do not claim `PASS_PHASE_12_SANDBOX_COMPLETE` unless implementation and validation actually run.
- Docker-heavy tests are env-gated.
- Private Supabase backup restore is env-gated.
- `/query/check` tests must prove no DB connection occurs.
- Query result rows, secrets, DSNs, passwords, and backup contents must not persist.

## Unit Tests

Cover:

- sandbox state model validation
- lifecycle transition rules
- active sandbox uniqueness per project/workspace or global fallback
- DBMS adapter selection
- policy defaults: `read_only=true`, `write_sandbox_mode=false`
- audit event redaction
- backup path validation and confinement
- query target binding serialization

## API Tests

Cover endpoints:

- `POST /sandboxes`
- `GET /sandboxes`
- `GET /sandboxes/{sandbox_id}`
- `POST /sandboxes/{sandbox_id}/start`
- `POST /sandboxes/{sandbox_id}/stop`
- `DELETE /sandboxes/{sandbox_id}`
- `POST /sandboxes/{sandbox_id}/restore`
- `GET /sandboxes/{sandbox_id}/schema`
- `GET /sandboxes/{sandbox_id}/audit`

Assertions:

- no raw DSN/password in responses
- invalid lifecycle transitions fail closed
- active sandbox conflicts return controlled errors
- delete/reset requires confirmation in UI/API contract where applicable

## Sandbox State Tests

Cover:

- files written under `Data/sandboxes/`
- sandbox state is not stored wholesale in `Data/safy_profiles.json`
- schema cache path references are valid
- restore job metadata is separated from sandbox metadata
- corrupt/missing state fails closed
- project/workspace fields exist for future scoping

## Docker Manager Tests

Env-gated tests:

- Docker available check
- container start/stop/delete
- isolated network creation
- volume creation/removal
- resource limit configuration
- health check handling

Statuses:

- Docker gate enabled and Docker unavailable -> `BLOCKED_DOCKER_ENGINE_NOT_RUNNING`
- Docker gate disabled -> `SKIPPED_DOCKER_NOT_REQUIRED`

## Restore/Import Tests

PostgreSQL/Supabase-compatible priority:

- restore `.sql`
- restore `.dump`
- restore `.backup`
- restore `.backup.gz`
- readonly role/user creation after restore
- schema cache generation after restore
- failed restore transitions to `failed`
- missing backup fails when gate enabled

Follow-up/hardened adapter tests:

- MySQL dump restore and readonly grants
- SQL Server restore/import strategy and readonly login/user
- Oracle import strategy and readonly user/schema grants
- SQLite isolated file-copy strategy and read-only connection mode

Private Supabase backup statuses:

- gate disabled -> `SKIPPED_SUPABASE_BACKUP_RESTORE_NOT_REQUIRED`
- gate enabled + missing backup -> `BLOCKED_BACKUP_MISSING`
- gate enabled + restore failure -> `BLOCKED_BACKUP_RESTORE_FAILED`
- gate enabled + successful restore -> `PASS_SUPABASE_BACKUP_RESTORE`

## Query Check/Execute Tests

`/query/check` tests:

- accepts `target=sandbox` and `sandbox_id`
- binds target and sandbox into check state
- computes `sql_hash`
- rejects blocked writes and multi-statements
- uses schema cache only
- proves no DB connection is opened, using mock driver/container sentinels

`/query/execute` tests:

- requires valid `check_id`
- requires matching `sql_hash`
- rejects expired check
- rejects consumed check
- rejects target mismatch
- rejects sandbox_id mismatch
- rejects SQL Guard denied query
- executes read-only SELECT through readonly sandbox binding
- records metadata-only audit with row count/error code

## No Persistence Tests

Verify result rows do not appear in:

- sandbox metadata
- restore job metadata
- schema cache
- audit log
- query history files
- planning/implementation reports

## No Secret Tests

Verify raw secrets do not appear in:

- API responses
- sandbox metadata
- audit log
- schema cache
- reports
- UI rendered state snapshots

Search patterns should include known fake passwords, DSNs, and backup content markers from test fixtures.

## UI Tests

Cover:

- Sandbox Manager page renders
- create sandbox form
- DBMS/type selector
- source/backup selector
- restore progress panel
- lifecycle badges
- schema viewer
- sandbox-bound query panel
- target selector with `REAL DB` vs `SANDBOX`
- warning when switching to real DB
- audit/timeline metadata
- delete/reset confirmations
- agent proposal confirmation for create/restore

## Full Regression Tests

Run existing Phase 10/11 regressions to ensure:

- real DB guarded query flow still works
- SQL Guard read-only boundary is preserved
- `/query/check` remains non-executing
- driver contracts remain compatible
- UI profile/query flow is not regressed

## Validation Status Matrix

Planning-only status:

```text
PASS_PHASE_12_PLANNING_READY
```

Later implementation-only status:

```text
PASS_PHASE_12_SANDBOX_COMPLETE
```

Blocked/skipped statuses:

```text
BLOCKED_DOCKER_ENGINE_NOT_RUNNING
BLOCKED_BACKUP_MISSING
BLOCKED_BACKUP_RESTORE_FAILED
SKIPPED_DOCKER_NOT_REQUIRED
SKIPPED_SUPABASE_BACKUP_RESTORE_NOT_REQUIRED
PASS_SUPABASE_BACKUP_RESTORE
```

`PASS_PHASE_12_SANDBOX_COMPLETE` may only be reported after implemented code passes required tests with honest Docker/backup gate accounting.
