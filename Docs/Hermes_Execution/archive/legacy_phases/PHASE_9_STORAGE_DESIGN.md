# Phase 9 Storage Design

## Target Layout

```text
Data/
  safy_profiles.json
  sessions/
    session_<session_id>.json
  audit/
    safy_audit.jsonl
```

This is a planning target only. Phase 9 planning does not migrate existing data.

## Profile JSON Shape

```json
{
  "schema_version": 1,
  "updated_at": "...",
  "model_profiles": [],
  "database_profiles": []
}
```

Profiles store metadata and environment variable names only. Raw API keys, DB passwords, raw DSNs, bearer tokens, and transient secrets must be rejected before write. Existing `Data/User/` and `Data/Database_management/` are migration sources to inventory and normalize.

## Session JSON Shape

```json
{
  "schema_version": 1,
  "session_id": "...",
  "created_at": "...",
  "updated_at": "...",
  "status": "active",
  "metadata": {},
  "messages": [],
  "runtime": {},
  "workspaces": [],
  "recovery_records": [],
  "query_events": []
}
```

Messages and query events must be redacted before write. Query result rows must not be persisted. Query event metadata may include db profile ID, DBMS, `sql_hash`, redacted SQL/summary, row count, truncation, timing, audit ID, timestamp, and confirmation state.

## Audit Target

`Data/audit/safy_audit.jsonl` is append-only, one redacted JSON object per line. It replaces/adapts the current SQLite audit store in implementation Pass 2 after compatibility tests exist.

## Atomic Writes

Profile and per-session JSON writes should use write-to-temp plus fsync/rename where feasible. Writes must avoid partial file replacement. Audit JSONL should append one full line at a time, with flush/fsync policy chosen for SAFY safety vs performance.

## Corruption Recovery

Plan backup files before migration, schema-version checks, JSON parse validation, and recovery records when a file is unreadable. Corrupt JSON should fail closed for safety-sensitive state instead of silently creating empty state.

## Redaction Before Write

All storage entrypoints must call existing redaction utilities or a Phase 9-safe equivalent before persisting user text, SQL, errors, driver messages, profile metadata, and runtime metadata.

## No Raw Secrets / No Result-row Persistence

Raw secrets are never written. Result rows are UI-temporary only and excluded from session JSON, runtime JSON, and audit JSONL.

## Migration Strategy

- Profile migration: read existing profile JSON/temp stores, normalize into `safy_profiles.json`, preserve IDs, reject raw secret fields.
- Session migration: read `runtime.sqlite`/`runtime.sqlite3` sources only during approved implementation, map tables to per-session JSON.
- Audit migration: adapt/write new JSONL events; historical SQLite import may be optional if safe and redacted.
- Legacy compatibility: implementation should support read-only fallback from legacy stores during migration or provide explicit one-time migration tooling with backups.

## Hermes Request Dump Distinction

Hermes request dump JSON may inspire SAFY session/debug event structure. SAFY must not store full prompts, tool schemas, or large tool payloads by default because they are too large and may retain sensitive data.

## Test Strategy

Plan tests for schema versions, atomic write recovery, raw secret rejection, redacted messages, result-row non-persistence, legacy profile migration, session migration, audit JSONL append behavior, and corruption fail-closed behavior.
