# Phase 3 Security Spec

## 1. Security Goal

Phase 3 must advance Safy without weakening the core safety model: LLM suggests, Safy verifies, sandbox tests, policy decides, audit records, and the user explicitly authorizes risky manual actions.

## 2. Non-Negotiable Invariants

- Agent connected database access is strict read-only.
- User query execution is user-controlled and must follow selected credential permission, safety check, explicit confirmation, high-risk code when required, and audit pre-write.
- No raw API key, DB password, raw secret, raw `.env` line, or unredacted SQL may appear in JSON, API responses, logs, frontend state, reports, or audit output unless a canonical spec explicitly permits a redacted/safe representation.
- High-risk pre-write audit failure blocks execution.
- SQLite fallback must not validate PostgreSQL/MySQL SQL.
- Reports are evidence only and cannot override source/spec/contract authority.

## 3. Real Execution Guardrails

Phase 3 must stop for user approval before:

- Destructive database operation.
- Real connected-database execution.
- Real external provider call.
- Any task depending on Phase 2 `NOT_VERIFIED` final refinements.
- Any unclear product/security decision.
- Any P0/P1 conflict after review pass 2.

## 4. Phase 2 Delta Guardrail

The following are not assumed implemented:

- Runtime/audit schema v2.
- `workflow_object_provenance`.
- `schema_snapshots`.
- `workspace_locks`.
- Atomic `validate_and_reserve`.
- Audit repair fields/transitions.
- Profile container migration.
- `user_query_access_mode` migration.
- Canonical migration error behavior.

Tasks depending on them are blocked unless explicitly scoped as Phase 2 delta implementation with evidence.

## 5. Fail-Closed Rules

- Missing audit pre-write evidence blocks high-risk manual execution.
- Missing permission evidence blocks user query execution.
- Missing confirmation atomicity evidence blocks high-risk confirmation claims.
- Missing DBMS-specific validation blocks SQL safety claims.
- Missing test evidence blocks `TESTED` status.
