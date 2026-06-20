# SAFY Phase 5 Plan - Connected Database Read-only Agent Query and User Query Execution

## Status
Status: Approved for Phase 5 implementation. This document was originally a planning document and is now the canonical implementation baseline. It does not claim Phase 5 has already been implemented.

## Phase 5 Objective
Add a guarded connected-database path with two separate flows:

1. Agent connected database read-only query path.
2. User query execution path through `/query/check` and `/query/execute`.

Phase 5 must preserve all earlier phase boundaries: profile secrets remain reference-only outside local secret storage, SQL Guard remains mandatory, sandbox mutation remains isolated, and connected database destructive execution by the agent remains forbidden.

## Current Baseline
Observed current runtime contracts:

- `/query/check` classifies SQL, extracts targets, evaluates risk, applies SQL Guard and permission checks, records check state, and does not execute SQL.
- `/query/execute` requires prior check state with matching `check_id`, `sql_hash`, `target`, and `database_profile_id` before reaching the sandbox/mock adapter.
- `AgentCore` currently supports the Create_database sandbox flow and rejects unsupported connected database mutation paths.
- `Gateway/README.md` documents that connected database execution is not implemented in the current phase.
- Phase 4.5 tests validate current safety gates and mock execution behavior.

## In Scope
- Add a connected database read-only adapter contract for agent use.
- Add agent intent handling for read-only connected database questions only.
- Route agent connected database SQL through SQL Guard before any execution attempt.
- Require query classification to prove the statement is read-only before connected database agent execution.
- Keep user query execution behind `/query/check` and `/query/execute`.
- Bind high-risk confirmation to backend-generated code, `check_id`, `sql_hash`, `target`, and `database_profile_id`.
- Audit check, confirmation generation, execution allow/block decisions, and adapter results with redacted metadata.
- Return normalized, redacted API responses suitable for the existing static UI.

## Out of Scope
- Phase 6 features.
- Agent DML, DDL, admin, maintenance, or destructive SQL on connected databases.
- Any LLM-generated or LLM-validated confirmation code.
- Raw secret return, log, audit, fixture, report, or frontend storage.
- Provider network changes unrelated to the existing model client contract.
- Background migrations that alter existing local data without explicit implementation review.
- Multi-user auth, role-based access control, and production credential vault integration unless already present.

## Implementation Workstreams
1. Contract hardening: define request/response schemas and adapter interfaces before code changes.
2. SQL Guard enforcement: centralize read-only proof and destructive block decisions.
3. Agent read-only route: add intent planning for connected database questions that can only produce SELECT-like SQL.
4. Connected read-only adapter: execute only against configured profile references and never expose secrets.
5. User query execute path: preserve check/execute binding and add real connected execution only after guard and permission pass.
6. Audit and redaction: extend audit events without raw SQL secrets or connection credentials.
7. UI updates: display safety reports, confirmation requirements, and results without unsafe HTML or backend stack traces.
8. Validation: add tests before enabling any connected database execution path.

## Phase Gate
Phase 5 can be considered implemented only after all checklist items in `PHASE_5_VALIDATION_CHECKLIST.md` pass and reports record real command output. Until then, the project status remains Phase 5 planned, not implemented.
