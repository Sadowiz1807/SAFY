# Phase 12 UI Spec — Sandbox Manager

## UI Goals

The Sandbox Manager gives users explicit control over persistent sandbox runtimes. It must make the target boundary obvious, prevent accidental real database execution, and require confirmation for creation, restore/import, delete/reset, and real DB target switching.

## Sandbox Manager Page

Primary elements:

- sandbox list grouped by project/workspace
- active sandbox banner
- lifecycle status badge
- DBMS/provider compatibility badge
- quick actions: start, stop, restore, view schema, query, audit, delete
- empty state explaining why sandbox exists and how it differs from real DB and Docker tests

The page should explain that a sandbox is a persistent runtime, not a new container per agent request.

## Create Sandbox Form

Fields:

- sandbox name
- project/workspace
- DBMS type: PostgreSQL, Supabase-compatible PostgreSQL, MySQL, SQL Server, Oracle, SQLite
- provider compatibility hint where applicable
- activate after create checkbox
- resource profile selection if available

Confirmations:

- creating a sandbox is user-initiated
- activating it may deactivate another sandbox in the same project/workspace
- agent cannot silently create a sandbox

## Source/Backup Selector

Fields:

- source type: empty init, backup file, dump file, SQLite file copy, future external source
- approved local path or configured import root reference
- format: `.sql`, `.dump`, `.backup`, `.backup.gz`, DBMS-native format
- private Supabase restore gate status

Privacy UI rules:

- do not display full private backup contents
- avoid showing raw secrets or DSNs
- show redacted path/name metadata only
- warn that private backups are not committed or stored in reports

## Restore Progress Panel

Display:

- restore state: queued, validating, starting runtime, restoring, creating readonly user, generating schema cache, ready, failed
- progress messages without raw data
- elapsed time
- last metadata-only error code
- retry/reset controls where safe

Required statuses:

- `SKIPPED_SUPABASE_BACKUP_RESTORE_NOT_REQUIRED`
- `BLOCKED_BACKUP_MISSING`
- `BLOCKED_BACKUP_RESTORE_FAILED`
- `PASS_SUPABASE_BACKUP_RESTORE`
- `BLOCKED_DOCKER_ENGINE_NOT_RUNNING`

## Status/Lifecycle Badge

Lifecycle states:

- `created`
- `starting`
- `restoring`
- `ready`
- `failed`
- `stopping`
- `stopped`
- `deleting`
- `deleted`

Badges must distinguish:

- `SANDBOX READY`
- `SANDBOX STOPPED`
- `SANDBOX FAILED`
- `REAL DB TARGET`
- `SANDBOX TARGET`

## Schema Viewer

The schema viewer uses `GET /sandboxes/{sandbox_id}/schema` and displays cached schema only:

- schemas/namespaces
- tables/views
- columns and types
- indexes/keys if available
- cache generated timestamp
- refresh action only if implemented as a separate controlled operation

No row previews are persisted in schema cache.

## Query Panel Bound to Sandbox

The query panel must show target binding clearly:

- selected target: `SANDBOX`
- selected sandbox id/name
- DBMS type
- readonly policy badge
- active sandbox indicator

Execution flow:

1. user/agent submits SQL
2. UI calls `/query/check` with `target=sandbox` and `sandbox_id`
3. UI displays guard result
4. UI calls `/query/execute` with `check_id`, `sql_hash`, `target`, and `sandbox_id`
5. UI displays returned rows temporarily
6. UI does not persist result rows

## Target Selector: REAL DB vs SANDBOX

Target selector requirements:

- default to active sandbox when available for sandbox workflows
- show large visible `SANDBOX` vs `REAL DB` badge
- require warning/confirmation when switching from sandbox to real DB
- never imply sandbox safety applies to real DB
- prevent executing a sandbox check against a real DB target

Warning example:

```text
You are switching from SANDBOX to REAL DB. SAFY will not use the sandbox runtime for this query. Continue?
```

## Audit/Timeline

Timeline displays metadata-only events:

- created
- started
- restore/import requested
- restore/import completed/failed
- readonly user created
- schema cache generated
- query checked
- query executed
- stopped
- deleted

Do not display raw rows, raw secrets, raw DSNs, raw passwords, or backup contents.

## Delete/Reset Controls

Delete/reset controls must require confirmation and explain effects:

- delete removes sandbox runtime resources according to retention policy
- delete does not delete the original backup/source
- reset/restore may overwrite sandbox runtime data
- active sandbox deletion deactivates it

## Agent Interaction UI

When the agent proposes sandbox work:

- show proposal card for create/restore/import
- require explicit user confirmation before create or restore/import
- allow the agent to use an existing active sandbox for read-only SELECT through guarded query flow
- block write queries in Phase 12

## Error and Safety Messaging

UI must surface fail-closed states:

- Docker unavailable when gate enabled
- backup missing when restore gate enabled
- restore failed
- readonly user creation failed
- active sandbox conflict
- `/query/check` rejected by SQL Guard
- `/query/execute` rejected because check expired, consumed, hash mismatch, target mismatch, or sandbox mismatch
