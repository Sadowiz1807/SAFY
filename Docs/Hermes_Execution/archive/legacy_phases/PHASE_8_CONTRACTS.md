# Phase 8 Contracts

Executed by main-agent only. No sub-agents used.

## Real DB profile contract

- Owner module(s): `DataStore/profile_store.py`, planned database profile service, planned API profile endpoints
- Inputs: DBMS type, host metadata, port, database name, username, env var reference fields, optional session-local transient credential reference
- Outputs: validated profile metadata with stable `database_profile_id`
- Allowed behavior: store non-secret metadata and env var names; return redacted profile display data
- Blocked behavior: storing raw password, raw DSN, raw token, or raw secret in profile JSON
- Error codes: `VALIDATION_ERROR`, `SECRET_VALUE_REJECTED`, `DB_PROFILE_NOT_FOUND`
- Safety invariants: profile persistence never contains raw secrets; returned payloads remain redacted
- Regression risks: accidental schema expansion that starts persisting raw DSN or password values
- Acceptance criteria: profile contract supports real DB read-only planning without weakening current raw-secret rejection behavior

## Credential / secret contract

- Owner module(s): `DataStore/profile_store.py`, `Logging/redact.py`, planned transient credential handler, API layer
- Inputs: env var name references, transient UI/API password entry
- Outputs: redacted runtime-safe secret handling state
- Allowed behavior: resolve env var references at execution time; accept transient password only for one-session or one-test usage without persistence
- Blocked behavior: writing raw credentials to runtime DB, audit log, session history, UI snapshots, or reports
- Error codes: `VALIDATION_ERROR`, `DB_AUTH_FAILED`, `DB_DRIVER_ERROR_REDACTED`
- Safety invariants: transient secrets are redacted immediately; no raw secret leaves the request boundary
- Regression risks: exception surfaces or debug logging leaking raw inputs
- Acceptance criteria: planning defines exactly where credentials may appear and where they must never persist

## Adapter interface contract

- Owner module(s): planned adapter module set, `Gateway/query_orchestrator.py`
- Inputs: validated profile, optional transient secret material, query request, timeout and row-limit parameters
- Outputs: normalized connection, schema, explain, and read-only query results
- Allowed behavior: connect, test, introspect, explain if safe, execute read-only SQL, close resources
- Blocked behavior: executing INSERT/write/destructive SQL; bypassing SQL Guard; returning raw driver exceptions
- Error codes: `DB_CONNECTION_FAILED`, `DB_TIMEOUT`, `DB_READONLY_VIOLATION`, `DB_DRIVER_ERROR_REDACTED`
- Safety invariants: adapters execute only after SQL Guard approval; all error surfaces are normalized and redacted
- Regression risks: engine-specific driver errors bypassing normalization
- Acceptance criteria: adapter contract defines stable methods and normalized models for all three DBMS subphases

## Schema introspection contract

- Owner module(s): planned adapter modules, planned schema service, agent planning layer
- Inputs: database profile, connection context, introspection options
- Outputs: normalized schema metadata package
- Allowed behavior: return tables, columns, types, PK/FK, indexes, views, constraints, comments, schemas, estimated row counts
- Blocked behavior: returning unredacted secrets, fetching sample rows without approval, executing mutation SQL during introspection
- Error codes: `DB_SCHEMA_INTROSPECTION_FAILED`, `DB_CONNECTION_FAILED`, `DB_DRIVER_ERROR_REDACTED`
- Safety invariants: introspection remains read-only and redacted
- Regression risks: DB-specific metadata SQL using unsafe commands or leaking comments/names without filtering
- Acceptance criteria: schema metadata coverage and redaction behavior are fully documented

## User direct SQL textbox contract

- Owner module(s): `Apps/Web/mock-ui.js`, `Apps/Api/safy_api/main.py`, `Gateway/query_orchestrator.py`
- Inputs: SQL text, database profile ID, user decision, confirmation token if required
- Outputs: query-check decision or temporary read-only result payload
- Allowed behavior: `/query/check` followed by explicit user-triggered `/query/execute`
- Blocked behavior: direct execution without prior check binding; hidden auto-execution in real DB mode
- Error codes: `QUERY_CHECK_REQUIRED`, `SQL_HASH_MISMATCH`, `DB_UNSAFE_SQL_BLOCKED`, `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED`, `DB_INSERT_BLOCKED`
- Safety invariants: `/query/check` never executes SQL; `/query/execute` requires check binding and policy approval
- Regression risks: UI shortcut paths bypassing explicit execution button or confirmation step
- Acceptance criteria: textbox flow remains explicit, state-bound, and read-only

## Agent real DB query contract

- Owner module(s): `Core/agent.py`, planned agent DB workflow service, `Gateway/query_orchestrator.py`
- Inputs: user natural-language request, database profile context, schema metadata
- Outputs: explanation, SQL preview, blocked warning, or temporary read-only result
- Allowed behavior: inspect schema, generate SQL, explain it, send through SQL Guard, execute only allowed read-only SQL
- Blocked behavior: executing blocked SQL, skipping introspection, bypassing `/query/check`
- Error codes: `DB_UNSAFE_SQL_BLOCKED`, `DB_INSERT_BLOCKED`, `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED`, `DB_SCHEMA_INTROSPECTION_FAILED`
- Safety invariants: agent cannot bypass SQL Guard and cannot execute blocked SQL
- Regression risks: prompt or workflow changes that let the agent call adapters directly
- Acceptance criteria: agent path is documented as schema-first, SQL-previewed, and read-only only

## SQL Guard real DB enforcement contract

- Owner module(s): `Gateway/sql_guard.py`, planned classifier/risk extensions, `Gateway/query_orchestrator.py`
- Inputs: normalized SQL, classification, target DB mode, execution path
- Outputs: allow, require-confirmation, or blocked decision with reasons
- Allowed behavior: permit safe read-only SQL and safe metadata/introspection requests
- Blocked behavior: INSERT, UPDATE, DELETE, DDL, permission changes, CALL, COPY, multi-statement, SELECT FOR UPDATE, side-effect SQL
- Error codes: `DB_UNSAFE_SQL_BLOCKED`, `DB_INSERT_BLOCKED`, `DB_READONLY_VIOLATION`
- Safety invariants: Phase 8 is strictly read-only and INSERT is always blocked
- Regression risks: treating INSERT as ambiguous or allowing DBMS-specific mutation syntax through gaps
- Acceptance criteria: read-only enforcement covers all stated blocked categories and documents EXPLAIN policy limitations

## Confirmation for sensitive SELECT contract

- Owner module(s): `Gateway/query_orchestrator.py`, confirmation state service, API layer, UI layer
- Inputs: query-check decision, risk signals, user approval action
- Outputs: one-time confirmation requirement or cleared execution approval
- Allowed behavior: require confirmation for sensitive tables/columns, broad scans, large limits, sample rows, or other elevated read risks
- Blocked behavior: reusing stale confirmations, using UI-only confirmations without backend binding
- Error codes: `DB_SENSITIVE_SELECT_CONFIRMATION_REQUIRED`, `QUERY_CHECK_EXPIRED`, `MANUAL_CONFIRMATION_INVALID`
- Safety invariants: confirmation remains backend-generated, expiring, one-time, and state-bound
- Regression risks: confirmation sprawl across unrelated operations or missing coverage for broad scans
- Acceptance criteria: triggers and lifecycle for sensitive SELECT confirmation are explicitly documented

## Read-only result contract

- Owner module(s): planned adapter layer, API execute endpoint, UI result renderer
- Inputs: allowed read-only SQL plus adapter execution metadata
- Outputs: row payload, row count, truncation flag, execution time, timeout/redaction notes
- Allowed behavior: return temporary result rows to the active UI session
- Blocked behavior: persisting result rows in session history; returning raw driver traceback
- Error codes: `DB_TIMEOUT`, `DB_RESULT_LIMIT_EXCEEDED`, `DB_DRIVER_ERROR_REDACTED`
- Safety invariants: results are temporary, bounded, and redacted where required
- Regression risks: storing row payloads in runtime history or analytics by accident
- Acceptance criteria: result contract documents temporary display, truncation, timeout, and non-persistence rules

## Sample row approval contract

- Owner module(s): planned schema/sample row service, API layer, UI layer
- Inputs: approved sample-row request bound to schema/table context
- Outputs: limited, redacted sample rows
- Allowed behavior: return sample rows only after explicit approval
- Blocked behavior: automatic sample-row retrieval during introspection or agent planning
- Error codes: `DB_SAMPLE_ROWS_APPROVAL_REQUIRED`, `DB_TIMEOUT`, `DB_DRIVER_ERROR_REDACTED`
- Safety invariants: sample rows require approval, redaction, and strict limits
- Regression risks: sample row retrieval becoming a hidden side path around SELECT confirmation policy
- Acceptance criteria: approval requirement and storage restrictions are documented

## Blocked INSERT / write / destructive SQL display contract

- Owner module(s): agent response layer, query-check endpoint, UI blocked-operation panel
- Inputs: blocked SQL request from user textbox or agent path
- Outputs: safe blocked response with non-executed SQL text and warning
- Allowed behavior: display blocked SQL text as non-executed output if user requested it
- Blocked behavior: executing or queueing the blocked SQL in SAFY
- Error codes: `DB_INSERT_BLOCKED`, `DB_UNSAFE_SQL_BLOCKED`, `DB_READONLY_VIOLATION`
- Safety invariants: blocked SQL display never implies execution and always states manual external execution is required
- Regression risks: UI wording that suggests later retry inside SAFY or treats INSERT as pending approval
- Acceptance criteria: INSERT is documented as blocked, not ambiguous, and display-only when requested

## Audit / session contract

- Owner module(s): `Audit/audit_store.py`, `State/runtime_db.py`, API layer
- Inputs: query check metadata, execute metadata, redacted SQL summary, sql hash, result summary
- Outputs: audit event and session-history summary records
- Allowed behavior: persist `db_profile_id`, DBMS, `sql_hash`, redacted SQL or summary, row count, truncated flag, execution time, audit ID, timestamp
- Blocked behavior: persisting raw credentials or result rows in session history
- Error codes: `DB_DRIVER_ERROR_REDACTED`, `DB_CONNECTION_FAILED`
- Safety invariants: audit stores redacted SQL + `sql_hash`; session history stores summary only
- Regression risks: metadata expansion silently storing row payloads
- Acceptance criteria: persistence boundaries are explicit and consistent with Phase 8 safety rules

## UI real DB mode contract

- Owner module(s): `Apps/Web/mock-ui.js`, planned web UI components, API presentation layer
- Inputs: real DB connection status, schema payload, query-check response, execute result
- Outputs: mode-specific safe UI rendering
- Allowed behavior: show redacted host, DBMS, database name, read-only status, warning banner, schema browser, preview, results, and confirmation UX
- Blocked behavior: rendering raw traceback, raw driver errors, raw credentials, or untrusted HTML
- Error codes: `DB_CONNECTION_FAILED`, `DB_AUTH_FAILED`, `DB_DRIVER_ERROR_REDACTED`, `DB_INSERT_BLOCKED`
- Safety invariants: UI clearly distinguishes sandbox, mock connected preview, and real connected read-only modes
- Regression risks: reusing mock-mode language that hides real DB context or weakens user caution
- Acceptance criteria: real DB mode UI requirements and blocked-operation UX are fully documented

## Optional Docker integration test contract

- Owner module(s): planned `Tests/phase8` integration suite, test harness configuration
- Inputs: Docker availability, env vars, adapter configuration
- Outputs: optional integration results or clean skips
- Allowed behavior: run MySQL-first optional integration tests, PostgreSQL-second optional integration tests, and SQLite path-confined connected-file tests
- Blocked behavior: failing the mandatory suite solely because Docker/env vars are absent
- Error codes: test-layer skip markers only; no runtime-specific user-facing error codes required
- Safety invariants: integration tests remain read-only and never exercise write support in Phase 8
- Regression risks: optional tests becoming mandatory by accident in environments without Docker
- Acceptance criteria: skip policy and DBMS priority are documented in the planning package
