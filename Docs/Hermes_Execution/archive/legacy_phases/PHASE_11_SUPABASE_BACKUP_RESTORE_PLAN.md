# Phase 11 Supabase Backup Restore Plan

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Backup Handling

Backup filename: `db_cluster-27-01-2026@16-06-46.backup.gz`

Planned repository location if the user approves local fixture placement:

```text
Data/TestFixtures/supabase/db_cluster-27-01-2026@16-06-46.backup.gz
```

Rules:

- Do not assume the backup is already in the repository.
- Do not inspect, decompress, or restore it during planning.
- Treat it as private test data.
- Do not commit backup contents unless the user explicitly approves.
- Do not store Supabase secrets in profile JSON, sessions, audit, logs, reports, or frontend JS.

## Validation Modes

### A. Local Restore Validation

- Restore the backup into a local PostgreSQL/Supabase-compatible test database.
- Create or use a restricted read-only SAFY test user.
- Validate provider profile maps to PostgreSQL driver.
- Validate schema loading, safe SELECT, blocked writes/DDL/procedure-like execution, and redaction.

Recommended gate: `SAFY_PHASE11_SUPABASE_BACKUP_REQUIRED=1`.

If required and the backup is missing or restore fails, report `BLOCKED_SUPABASE_BACKUP_RESTORE`.

### B. Live Supabase Validation

- Run only when `SAFY_PHASE11_SUPABASE_LIVE_REQUIRED=1` and all required env vars are present.
- Required variables: `SAFY_SUPABASE_PASSWORD`, `SAFY_SUPABASE_HOST`, `SAFY_SUPABASE_PORT`, `SAFY_SUPABASE_DATABASE`, `SAFY_SUPABASE_USER`.
- Use `ssl_mode=require`.
- Report `BLOCKED_CLOUD_VALIDATION` when the flag is set but credentials are missing.
- If the flag is not set, report NOT RUN / WAITING_FOR_CREDENTIALS, not PASS.
