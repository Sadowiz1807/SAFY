# SAFY Phase 7 Validation Checklist

Executed by main-agent only. No sub-agents used.

Phase 7 implementation is now approved by the user.
Real connected DB adapter execution remains deferred and is not part of this implementation.

## Static Validation
- [ ] Run `python -m compileall .`.
- [ ] Run import checks for API, runtime DB, query orchestrator, audit store, agent core, and redaction helpers.
- [ ] Run syntax checks for changed Python files.
- [ ] Run `node --check Apps/Web/mock-ui.js`.

## Test Validation
- [ ] Run full Phase 1 -> Phase 6 suite: `python -m pytest Tests/phase1 Tests/phase1_5 Tests/phase2 Tests/phase2_5 Tests/phase3 Tests/phase4 Tests/phase4_5 Tests/phase5 Tests/phase6 -q --basetemp=tmp/pytest_phase7_final`.
- [ ] Add planned Phase 7 test suite only after user approval.
- [ ] Endpoint envelope tests cover profiles, chat/agent, query check/execute, sessions, workspaces, recovery, and health/status if present.
- [ ] Redaction tests cover session history, workspace metadata, recovery records, audit records, API responses, UI payloads, logs, and reports.
- [ ] Recovery fail-closed tests cover expired/consumed checks and confirmation codes.
- [ ] Workspace cleanup block tests cover active locked workspaces and ambiguous lock/path state.
- [ ] UI smoke tests cover safe error rendering and disabled unsafe states.

## Security Validation
- [ ] Run repository-wide secret scan for credential-like patterns.
- [ ] Classify every hit as real secret, fake fixture, redaction test, documentation, or false positive.
- [ ] Run audit scan for missing pre/post/block evidence.
- [ ] Run raw traceback scan in API/UI/report output.
- [ ] Verify no unapproved real DB execution path is enabled.
- [ ] Verify no sub-agent evidence in Phase 7 reports.
- [ ] Verify Phase 7 out-of-scope enforcement remains documented.

## Release Readiness
- [ ] Required reports complete.
- [ ] Docs consistent and free of stale canonical counts.
- [ ] Known warnings documented.
- [ ] Acceptance criteria met.
- [ ] User review completed before implementation or release claim.
