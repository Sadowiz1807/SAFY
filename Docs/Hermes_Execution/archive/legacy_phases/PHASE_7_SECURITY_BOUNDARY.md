# SAFY Phase 7 Security Boundary

Executed by main-agent only. No sub-agents used.

Phase 7 implementation is now approved by the user.
Real connected DB adapter execution remains deferred and is not part of this implementation.

## Final Release-Readiness Boundaries
- No raw secret persistence in JSON stores, runtime DB, audit DB, logs, reports, UI, or API responses.
- Redaction is required for all outputs, including nested metadata.
- SQL Guard is mandatory for query safety.
- Query execution remains state-bound to `check_id`, `sql_hash`, `target`, and `database_profile_id`.
- Confirmation code lifecycle is backend-generated, one-time, expiring, and state-bound.
- Agent destructive connected DB execution remains blocked.
- Real connected DB adapter execution remains deferred.
- Sandbox mutation remains isolated and path-confined.
- Active locked workspace cleanup remains blocked.
- Recovery fails closed and never executes SQL.
- Audit pre/post/block coverage is required for safety-relevant actions.
- Test evidence must include commands, counts, exit codes, warnings, and redacted scan findings.

## Phase 7 Must Not Weaken
- `/query/check` never executes SQL.
- `/query/execute` cannot run with missing, expired, consumed, mismatched, or ambiguous check state.
- LLM/model output cannot generate, recover, validate, or bypass confirmation codes.
- Recovery cannot revive expired/consumed query checks or confirmation codes.
- Workspace cleanup cannot delete active locked workspaces.
- Reports and tests cannot contain real secrets.
- Phase 7 cannot include real connected DB execution without separate user approval.
- Phase 7 cannot include cloud deployment, production auth/RBAC, billing, provider marketplace, or long-running job orchestration as automatic scope.

## Evidence Requirements
Future implementation must prove every boundary with static checks, full regression tests, planned Phase 7 tests, secret scans, UI smoke checks, and final reports.
