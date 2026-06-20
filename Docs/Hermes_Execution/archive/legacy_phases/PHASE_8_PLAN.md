# Phase 8 Plan

Executed by main-agent only. No sub-agents used.

## 1. Purpose

Plan Phase 8 as the design package for SAFY real connected database read-only support without implementing runtime code. Phase 8 is planning-only until the user approves implementation.

## 2. Current baseline

Baseline verified from repository evidence:

- Phase 7 final status is `PASS_WITH_WARNINGS`
- `PHASE_7_FINAL_REPORT.md` records `151 passed`, exit code `0`
- connected DB adapter execution remains deferred / mock-only
- SAFY may be described as `v1.0.0 Safety MVP / Release Candidate`
- SAFY is not yet a real connected DB MVP

Runtime code also confirms the current state:

- `Apps/Api/safy_api/main.py` saves database profiles only as mock metadata and does not open real DB connections
- `Gateway/query_orchestrator.py` still uses `SandboxAdapter()` and marks responses `mock_only` / `no_real_execution`
- `Gateway/sandbox_adapter.py` returns mock execution results only
- `Core/agent.py` only provides mock connected DB preview behavior

## 3. User requirements summary

Phase 8 target is a real connected DB read-only adapter with MySQL first, PostgreSQL second, and SQLite third. Real DB `SELECT` must use the existing `/query/check -> SQL Guard -> confirmation if needed -> /query/execute` path. Credentials may come from `.env` or transient UI/API entry, but raw secrets must never persist. INSERT is not part of Phase 8. Phase 8 does not support INSERT or any other write/data-changing SQL.

## 4. Scope

In scope for planning:

- real connected DB read-only adapter architecture
- MySQL / PostgreSQL / SQLite subphase plan
- credential and profile model
- schema introspection model
- read-only query execution flow
- agent flow for real schema + read-only SQL
- user direct SQL textbox flow
- UI specification for real DB mode
- audit and session-history rules
- validation and testing strategy
- release definition for `v1.1.0 Real Connected DB Read-only`

## 5. Non-scope

Not in scope for this run:

- runtime implementation
- real DB adapter code
- executable `Tests/phase8`
- unlocked implementation gate
- real DB write support
- `INSERT`, `UPDATE`, `DELETE`, or destructive SQL execution
- changes to Phase 1 through Phase 7 behavior
- cloud DB / SSH tunnel / VPN / managed provider support unless explicitly approved later

## 6. Subphase strategy

### 8.1 MySQL

First implementation target because the user selected MySQL priority first. Plan DB-specific connection policy, introspection queries, read-only session settings, and Docker-backed optional integration tests first.

### 8.2 PostgreSQL

Second implementation target with matching read-only enforcement, introspection, confirmation, and optional Docker-backed integration coverage.

### 8.3 SQLite

Third implementation target for connected-file read-only mode only, with strict path confinement and read-only open semantics.

## 7. Adapter architecture overview

Plan a generic `ConnectedDBAdapter` abstraction with DBMS-specific implementations. The adapter layer should normalize connection status, schema introspection, redacted errors, read-only execution, timeout handling, row-limit enforcement, and result metadata while leaving safety gating in SQL Guard and orchestrator layers.

## 8. Credential model

Planned credential model:

- profile stores metadata plus env var references only
- optional DSN is referenced by env var name, not raw DSN value
- transient password input may be accepted for test or one-session use only
- transient secrets are never persisted to JSON profile store, runtime DB, audit store, session history, UI snapshots, or logs
- all failures involving credentials must be redacted at ingestion and display boundaries

## 9. Database profile model

Plan a database profile shape with stable profile ID, DBMS type, host metadata, database name, port, read-only intent, SSL metadata if later needed, env var reference fields, and optional session-local transient secret binding. The model must preserve current no-raw-secret invariants from `DataStore/profile_store.py`.

## 10. Query flow

Planned real DB query flow:

1. user submits SQL
2. `/query/check` classifies SQL and enforces read-only policy
3. SQL Guard blocks unsafe SQL, multi-statement SQL, `INSERT`, and all write/destructive forms
4. broad or sensitive `SELECT` may require one-time confirmation
5. `/query/execute` verifies check binding and executes only read-only SQL via adapter
6. result rows return to UI temporarily only
7. session history stores summary, not result rows

## 11. Agent flow

Planned agent flow:

1. resolve database profile and confirm real DB read-only mode
2. introspect real schema before generating SQL
3. generate and explain SQL based on current schema
4. send SQL through `/query/check`
5. execute only if SQL Guard allows it and confirmation requirements are satisfied
6. if SQL is blocked, show non-executed SQL text plus warning that the user must run it outside SAFY

## 12. User direct SQL textbox flow

Planned user direct SQL textbox flow:

1. user writes SQL in dedicated textbox
2. UI sends it to `/query/check`
3. backend returns decision, warnings, and confirmation requirement if any
4. UI requires explicit user action before execution in real DB mode
5. UI sends `/query/execute` only with valid check binding and user decision
6. backend executes read-only SQL only

## 13. UI flow

Planned UI additions:

- real DB mode indicator
- red warning banner for real DB read-only mode
- DB profile panel with connection status and redacted host
- schema browser
- query preview panel
- confirmation modal for sensitive `SELECT`
- blocked operation panel for `INSERT` / write / destructive SQL
- temporary result table with limit / timeout / truncation indicators

## 14. Audit / session flow

Planned persistence policy:

- audit stores redacted SQL plus `sql_hash`
- session history stores query summary only
- result rows are not persisted in session history
- failed connection / driver errors are normalized and redacted
- sample row retrieval is tracked but its row payload is not retained in session history

## 15. Testing strategy

Planned test structure:

- mandatory fake adapter unit tests
- optional Docker MySQL integration tests
- optional Docker PostgreSQL integration tests
- SQLite path-confined connected-file integration tests
- skip optional integration tests when Docker or env vars are absent
- release validation continues to use `compileall`, Python tests, and `node --check` for the web mock UI

## 16. Release definition

After implementation and successful validation, SAFY may be called `v1.1.0 Real Connected DB Read-only`.

This phase must not claim:

- real connected DB write support
- destructive DB administration
- production-grade DB management coverage

## 17. Risks

- DBMS-specific read-only enforcement differs and must not be generalized too aggressively
- `EXPLAIN` safety varies by DBMS and may need per-engine gating
- schema introspection may expose sensitive names or comments unless redacted consistently
- broad `SELECT` queries can leak sensitive or large-scale data without strong confirmation rules
- transient secrets can leak through error surfaces unless redaction is enforced end-to-end
- current orchestrator logic allows non-read-only execution in mock mode and therefore must be tightened for real DB mode in a future implementation phase

## 18. Open decisions

- whether Phase 8 should support `EXPLAIN` at launch or defer it unless each adapter guarantees read-only semantics
- whether profile storage should prefer split host/database fields, DSN env var references, or support both from the start
- whether sensitive-table policy starts with heuristics only or includes user-configurable allowlist / denylist controls in the same phase
- whether sample rows approval uses a dedicated approval endpoint or existing confirmation mechanics with a new operation type

## 19. User approval gate

Phase 8 is planning-only until the user approves implementation.

Implementation must remain locked behind explicit user review of these planning documents, and `implementation_allowed` must remain `false` in the task manifest.
