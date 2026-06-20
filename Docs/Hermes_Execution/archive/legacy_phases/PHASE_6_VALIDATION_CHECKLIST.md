Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.

1|# SAFY Phase 6 Validation Checklist
2|
3|## Status
4|Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.
5|
6|
7|## 1. Execution Mode Validation
8|- [ ] Phase 6 plan states main-agent only.
9|- [ ] Phase 6 task file (`PHASE_6_TASKS.yaml`) sets `sub_agents_allowed: false`.
10|- [ ] Planning report states no sub-agents were used.
11|- [ ] Double-check report confirms no sub-agent delegation occurred.
12|
13|## 2. Static Validation
14|- [ ] `python -m compileall .` passes after implementation.
15|- [ ] Phase 1 → Phase 5 tests still pass.
16|- [ ] No raw secrets found in new code or documentation.
17|- [ ] All required Phase 6 planning files exist in `Docs/Hermes_Execution/`.
18|
19|## 3. Session History Validation
20|- [ ] `/sessions` returns redacted metadata.
21|- [ ] `/sessions/{chat_id}` returns historical messages with timestamps.
22|- [ ] History records include `audit_id` and `workspace_id` links.
23|- [ ] Requesting a non-existent session returns `SESSION_NOT_FOUND`.
24|
25|## 4. Recovery Validation
26|- [ ] Stale workspace locks are correctly identified in `/recovery/status`.
27|- [ ] Unsafe recovery attempts (expired codes, corrupted check state) are blocked.
28|- [ ] Recovery actions produce audit records.
29|- [ ] Ambiguous state results in `RECOVERY_STATE_AMBIGUOUS` and fail-closed behavior.
30|
31|## 5. Workspace Validation
32|- [ ] `/workspaces` lists all active and inactive workspaces.
33|- [ ] Attempting to clean an active locked workspace returns `WORKSPACE_ACTIVE_LOCKED`.
34|- [ ] Cleanup correctly removes files while preserving audit evidence.
35|- [ ] Path confinement (isolation to `Sandbox/`) is maintained.
36|
37|## 6. UI Validation
38|- [ ] Session list renders safely with `textContent`.
39|- [ ] Workspace management panel displays correct statuses.
40|- [ ] Cleanup requires user confirmation in the UI.
41|- [ ] No raw secrets or unredacted traces shown in the timeline.
42|
43|## 7. Security Boundary Verification
44|- [ ] Real connected-DB execution remains mock/preview.
45|- [ ] SQL Guard is invoked for all history-restored actions.
46|- [ ] Confirmation codes are not revived by recovery.
47|
48|---
49|**This checklist was produced by the main-agent only. No sub-agents used.**
50|