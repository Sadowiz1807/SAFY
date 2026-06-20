# Phase 9 Requirements

## 1. Phase 9 Purpose

Phase 9 is named: Storage Consolidation, Repository Cleanup, Runtime Consistency, Dashboard Launcher, and JSON Migration Planning. It prepares a low-risk implementation path for repository cleanup, a user-facing launcher/dashboard, and migration from scattered SQLite/temp JSON storage into SAFY-owned JSON storage.

## 2. User-approved Two-pass Structure

Pass 1: clean repository, create JSON scaffold plan, plan project restructuring, plan generated/temp cleanup, serve the dashboard from the backend root, and design the `safy run` launcher.

Pass 2: migrate profile, session/runtime, and audit storage to JSON targets after Pass 1 stabilizes paths and launch behavior.

## 3. `safy run` Requirement

`cd C:\Users\ASUS` followed by `safy run` must start SAFY without requiring `cd C:\Users\ASUS\SAFY`. The launcher must resolve the installed package/repository root, load config/data paths deterministically, start uvicorn, and default to opening the dashboard.

## 4. Dashboard Auto-open Requirement

`safy run` must start the FastAPI gateway/backend, serve the dashboard from the backend, and automatically open the dashboard in the default browser unless `--no-browser` is passed. The user-facing entrypoint should be `http://127.0.0.1:8000/`.

## 5. `/docs` Developer-only Requirement

`/docs` remains available for developer/API validation. It is not the main user dashboard. `/openapi.json` remains the OpenAPI schema. `/health` should return JSON health/status.

## 6. JSON Storage Requirement

Plan SAFY-owned JSON storage under `Data/`, including `Data/safy_profiles.json`, `Data/sessions/session_<session_id>.json`, and append-only `Data/audit/safy_audit.jsonl`. Include schema versioning, atomic writes, corruption recovery, redaction before write, no raw secrets, no result-row persistence, migration and compatibility strategy.

## 7. Repository Cleanup Requirement

Plan cleanup without deleting anything during planning. Classify source, tests, docs, generated artifacts, SQLite/DB artifacts, temp folders, and legacy/scaffold folders into keep/merge/archive/delete-generated-only/needs further verification.

## 8. No Database Driver Creation in Phase 9

Phase 9 must not create MySQL/PostgreSQL/SQLite driver implementation, Docker DB integration implementation, external DB production hardening, or write-capable execution. Any real MySQL/PostgreSQL driver completion is deferred to a later phase such as Phase 10.

## 9. Phase 8 Safety Boundaries Preserved

- `real_connected_db_write_allowed: false`
- `insert_allowed: false`
- `result_row_session_persistence_allowed: false`
- `raw_secret_persistence_allowed: false`
- `agent_sql_guard_bypass_allowed: false`
- `query_check_executes_sql: false`
- `database_driver_creation_allowed: false`

## 10. Explicit Out of Scope

- MySQL driver implementation
- PostgreSQL driver implementation
- new DBMS driver support
- real DB write support
- INSERT support
- UPDATE/DELETE/DDL support
- external DB production hardening
- cloud DB provider support
- SSH tunnel/proxy/VPN support
- moving or deleting files during planning
- storage migration execution during planning

## 11. Acceptance Criteria

- Phase 9 planning docs and reports exist.
- Two-pass plan is clear and implementation remains locked.
- `safy run` and dashboard auto-open requirements are captured.
- JSON migration is planned but not executed.
- Cleanup plan separates source/tests/docs from generated artifacts.
- No database driver creation, write support, or INSERT support is planned for Phase 9.
