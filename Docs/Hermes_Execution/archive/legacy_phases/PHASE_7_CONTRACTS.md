# SAFY Phase 7 Cross-Phase Contracts

Executed by main-agent only. No sub-agents used.

Phase 7 is planning-only until the user approves implementation.

## 1. SAFY Response Envelope Contract
Owner module(s): `Apps/Api/safy_api/main.py`, `Apps/Api/safy_api/mock_store.py`
Inputs: API request payloads and runtime results.
Outputs: `success`, `data`, `error`, and `meta` envelope.
Error codes: endpoint-specific stable codes.
Safety invariants: errors do not leak tracebacks or secrets.
Regression risks: ad hoc responses bypass envelope.
Acceptance criteria: every existing endpoint group has envelope tests.

## 2. API Error Shape Contract
Owner module(s): API handlers and `RuntimeDBError`/orchestrator errors.
Inputs: validation, runtime, query, workspace, and recovery failures.
Outputs: `error.code`, `error.message`, optional redacted details.
Error codes: `SESSION_NOT_FOUND`, `WORKSPACE_NOT_FOUND`, `WORKSPACE_ACTIVE_LOCKED`, `RECOVERY_RECORD_NOT_FOUND`, query guard errors.
Safety invariants: fail closed on ambiguity.
Regression risks: mismatched or string-only errors.
Acceptance criteria: normalized error assertions across endpoint groups.

## 3. Query Check/Execute State-Binding Contract
Owner module(s): `Gateway/query_orchestrator.py`, `Gateway/sql_guard.py`.
Inputs: SQL, `target`, `database_profile_id`, `check_id`, `sql_hash`.
Outputs: check records, execution previews, audit records.
Error codes: missing/expired/consumed/mismatched check errors and guard blocks.
Safety invariants: `/query/check` never executes SQL; `/query/execute` requires bound state.
Regression risks: executing with stale or mismatched checks.
Acceptance criteria: tests for missing, expired, consumed, mismatched, and ambiguous state.

## 4. High-Risk Confirmation Contract
Owner module(s): `Gateway/query_orchestrator.py`, `State/high_risk_code_state.py`.
Inputs: high-risk check state and backend-generated confirmation code.
Outputs: one-time confirmation validation result.
Error codes: missing, expired, consumed, or mismatched confirmation errors.
Safety invariants: LLM/model output never generates, recovers, validates, or bypasses confirmation codes.
Regression risks: code leakage through UI, logs, reports, or session history.
Acceptance criteria: confirmation code lifecycle tests and redaction scan.

## 5. Agent Connected DB Read-Only/Mock Boundary
Owner module(s): `Core/agent.py`, database tools, query orchestrator.
Inputs: agent chat intent, target, database profile ID.
Outputs: mock/preview read-only results only.
Error codes: destructive connected DB block codes.
Safety invariants: destructive connected DB execution remains blocked; real adapter deferred.
Regression risks: agent bypasses SQL Guard or mock boundary.
Acceptance criteria: destructive agent connected DB tests remain blocked.

## 6. Sandbox Mutation Boundary
Owner module(s): sandbox tools and `Gateway/sandbox_adapter.py`.
Inputs: sandbox workspace IDs and SQL/tool requests.
Outputs: isolated mock/sandbox results and workspace metadata.
Error codes: path confinement and sandbox availability errors.
Safety invariants: mutation remains isolated and path-confined.
Regression risks: writing outside workspace.
Acceptance criteria: path confinement and sandbox mutation tests.

## 7. Session History Contract
Owner module(s): `State/runtime_db.py`, session API endpoints.
Inputs: chat messages, agent results, audit/workspace IDs.
Outputs: redacted session list, detail, and timeline.
Error codes: `SESSION_NOT_FOUND`.
Safety invariants: no raw secrets in stored or returned history.
Regression risks: metadata leaks.
Acceptance criteria: session API and redaction tests.

## 8. Workspace Metadata/Cleanup Contract
Owner module(s): `State/runtime_db.py`, workspace APIs, sandbox tools.
Inputs: workspace lifecycle records, locks, cleanup requests.
Outputs: redacted workspace list/detail/cleanup result.
Error codes: `WORKSPACE_NOT_FOUND`, `WORKSPACE_ACTIVE_LOCKED` for active locked cleanup.
Safety invariants: active locked workspace cleanup remains blocked and fail-closed.
Regression risks: deleting active locked workspaces or ambiguous paths.
Acceptance criteria: cleanup block and path confinement tests.

## 9. Recovery Fail-Closed Contract
Owner module(s): `State/runtime_db.py`, recovery APIs, query confirmation state.
Inputs: recovery records, interrupted state, query check/code state.
Outputs: status, scan, resolve/abandon records.
Error codes: `RECOVERY_RECORD_NOT_FOUND` and recovery state errors.
Safety invariants: recovery does not execute SQL and does not revive expired/consumed checks or codes.
Regression risks: restoring unsafe state.
Acceptance criteria: fail-closed recovery tests.

## 10. Audit Event Contract
Owner module(s): `Audit/audit_store.py`, `Audit/audit_logger.py`, orchestrator/tools.
Inputs: pre/post/block events and provenance.
Outputs: redacted audit records with IDs and statuses.
Error codes: audit store errors.
Safety invariants: pre/post/block evidence exists for relevant actions.
Regression risks: missing audit coverage or raw secret logging.
Acceptance criteria: audit coverage scan and tests.

## 11. Redaction Contract
Owner module(s): `Logging/redact.py`, runtime/audit/API/UI surfaces.
Inputs: text, dict, list, metadata, messages, reports.
Outputs: redacted values with placeholders.
Error codes: not applicable; redaction must be defensive.
Safety invariants: raw secrets never persist or render.
Regression risks: new metadata fields bypass redaction.
Acceptance criteria: secret scan and redaction fixtures.

## 12. UI Rendering Safety Contract
Owner module(s): `Apps/Web/mock-ui.js`.
Inputs: API envelopes, errors, session/workspace/recovery data.
Outputs: safe DOM rendering.
Error codes: displayed as safe text.
Safety invariants: no raw traceback or secret rendering; use text-safe rendering.
Regression risks: unsafe HTML injection or confusing real/mock state.
Acceptance criteria: UI smoke and manual checklist.

## 13. Test/Report Evidence Contract
Owner module(s): `Tests`, `Docs/Hermes_Execution/report`.
Inputs: validation commands and outputs.
Outputs: exact commands, counts, exit codes, warnings.
Error codes: failed validation status.
Safety invariants: reports do not expose secrets and do not cite repair reports as canonical Phase 7 evidence.
Regression risks: stale counts or missing final evidence.
Acceptance criteria: final report review before release.
