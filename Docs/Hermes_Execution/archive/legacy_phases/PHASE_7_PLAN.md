# SAFY Phase 7 Plan - Final Integration, Hardening, and Release Readiness

Executed by main-agent only. No sub-agents used.

## Status
Phase 7 implementation is now approved by the user.
Real connected DB adapter execution remains deferred and is not part of this implementation.

## Purpose
Define the final SAFY integration, hardening, release-readiness, documentation cleanup, and end-to-end validation plan across Phases 1 through 6.

## Current Baseline
- Phase 1 through Phase 6 are implemented and validated from repository evidence.
- Phase 6 final status: `PASS_WITH_WARNINGS`.
- Phase 6 validation: `136 passed`, exit code `0`.
- `Tests/phase6` exists.
- Session history, workspace metadata, timeline, and recovery scan/resolve are implemented.
- Connected DB execution remains mock/preview only.
- Real connected DB adapter execution remains deferred and is not automatically included in Phase 7.

## Scope
1. Final system integration review.
2. Cross-phase contract consolidation.
3. End-to-end safety validation planning.
4. UI/backend consistency hardening plan.
5. Audit/redaction completeness plan.
6. Test-suite consolidation plan.
7. Release-readiness checklist.
8. Documentation cleanup plan.
9. Known limitations and deferred features.
10. Final acceptance gates.

## Non-scope
- Real connected database write execution.
- Agent destructive connected DB execution.
- Production credential vault migration.
- Production auth/RBAC/multi-user SaaS.
- Cloud deployment, billing, provider marketplace, and long-running background orchestration.
- Irreversible destructive cleanup or unreviewed network/provider changes.

## Safety Boundaries
- `/query/check` never executes SQL.
- `/query/execute` requires a valid, unexpired, unconsumed prior check bound to `check_id`, `sql_hash`, `target`, and `database_profile_id`.
- High-risk confirmation remains backend-generated, one-time, expiring, and state-bound.
- LLM/model output must never generate, recover, validate, or bypass confirmation codes.
- Agent destructive connected DB execution remains blocked.
- Recovery cannot revive expired/consumed checks or confirmation codes and must not execute SQL.
- Active locked workspace cleanup remains blocked and fails closed if ambiguous.
- Raw secrets must never appear in stores, API responses, UI, logs, audit records, reports, or tests except fake redaction fixtures.

## Phase 7 Workstreams
- Baseline verification and inventory.
- Cross-phase contract audit.
- API envelope and error normalization audit.
- UI/backend consistency review.
- Audit/redaction audit.
- Recovery/workspace fail-closed audit.
- End-to-end validation planning.
- Test suite consolidation.
- Documentation cleanup.
- Release-readiness review.
- Final acceptance criteria.

## Required Deliverables
- Planning docs: plan, tasks, contracts, API spec, UI spec, security boundary, validation checklist.
- Reports: planning report and planning double-check report.
- No implementation code or executable `Tests/phase7` test directory in this run.

## Validation Strategy
Use static validation, full Phase 1 through Phase 6 regression validation, planned Phase 7 test coverage, secret/audit/traceback scans, UI syntax checks, and release evidence review.

## Release-readiness Criteria
- All response envelopes and error shapes are consistent.
- Safety invariants remain preserved.
- No raw secrets or traceback leaks are present.
- Audit/redaction evidence is complete.
- Known warnings and deferred work are explicit.
- User review approves any future implementation.

## Rollback/Continuation Strategy
Because this run creates planning documents only, rollback is limited to reverting Phase 7 planning files. Future implementation must start from a fresh user approval gate and must not assume planning approval implies implementation approval.

## Open Questions
- Which warnings should be acceptable for a first release candidate?
- Should Phase 7 include only tests/docs or also small UI/API consistency changes after user review?
- What release artifact format does the user want: report-only, tagged commit, or packaged snapshot?

## User Approval Gate
Implementation is blocked until the user explicitly approves Phase 7 implementation in a later run.
