Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.

1|# SAFY Phase 6 Plan - Recovery, Session History, and Workspace Management
2|
3|## Status
4|Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.
5|
6|## Execution Mode
7|Main-agent only. No sub-agents used.
8|
9|## Phase 6 Objective
10|Make SAFY more robust by implementing session history persistence, recovery mechanisms for interrupted operations, and structured workspace management/cleanup. This phase transitions SAFY from a transient prototype to a session-aware system that can survive restarts and manage its local resources safely.
11|
12|## Current Baseline After Phase 5
13|- Phase 5 implemented confirmation flow enhancements and a mock/preview connected-database read-only path for the agent.
14|- API contracts for `/query/check`, `/query/execute`, and `/agent/chat` are established and verified with 129 tests.
15|- Audit store records events but session-level grouping and historical restoration are not yet implemented.
16|- Workspace locks and temporary database files are created but lacks a central management/cleanup lifecycle.
17|- Confirmation state and query check state are transient in-memory or lightly persisted but lack robust recovery.
18|
19|## In Scope
20|1. **Session History:**
21|   - Persistence of chat sessions (messages, agent intents, results).
22|   - Historical audit-linked timeline for each session.
23|   - API endpoints to list and retrieve past sessions.
24|2. **Recovery:**
25|   - Detection and safe handling of interrupted agent runs.
26|   - Restoration of metadata and timeline visibility (past messages and action logs).
27|   - **MANDATORY BOUNDARY:** Recovery must never revive consumed, expired, ambiguous, or unverified query checks or confirmation codes.
28|   - Unsafe or expired states must be explicitly closed or abandoned, requiring the user to initiate a new `/query/check` flow.
29|   - Handling of stale workspace locks.
30|   - Fail-closed logic for ambiguous or unsafe states.
31|3. **Workspace Management:**
32|   - Centralized registry/inventory of sandbox workspaces.
33|   - Lifecycle management: creation, metadata tracking, and cleanup of expired workspaces.
34|   - Protection of active workspace locks during cleanup.
35|4. **API and UI Support:**
36|   - Endpoints for session retrieval and workspace control.
37|   - UI components for history browsing and workspace monitoring.
38|   - Safe rendering and redaction preserved across all new features.
39|
40|## Out of Scope
41|- Phase 7 features (Final Hardening/MVP).
42|- Real connected-database adapter execution (remains deferred unless separately approved).
43|- Destructive connected-database execution by the agent (remains blocked).
44|- Multi-user authentication or RBAC (remains outside current project scope).
45|- Automated database migration tools for production schemas.
46|
47|## Implementation Workstreams
48|1. **Runtime Schema Review:** Document existing state tables and define necessary extensions for sessions and workspaces.
49|2. **Session History Contract:** Define how chat and action history is stored and linked to audit records.
50|3. **Recovery State Machine:** Implement logic to detect interrupted states and provide safe resolution paths.
51|4. **Workspace Management:** Implement the inventory and cleanup lifecycle for sandbox environments.
52|5. **API Endpoints:** Build the `/sessions`, `/workspaces`, and `/recovery` endpoint groups.
53|6. **UI Integration:** Add history panels and workspace controls to the mock-ui frontend.
54|7. **Audit and Redaction:** Ensure all history and recovery actions are audited and redacted.
55|8. **Validation:** Create comprehensive tests for history persistence, recovery scenarios, and workspace cleanup.
56|
57|## Phase Gate
58|Phase 6 is complete when:
59|- Sessions are persisted and correctly restored in the UI.
60|- Interrupted states (locks, stale checks) are correctly identified and resolved (or failed closed).
61|- Expired workspaces are cleaned up without affecting active ones.
62|- All Phase 1-5 regressions pass.
63|- Documentation and reports confirm pass status.
64|
65|---
66|**This plan was produced by the main-agent only. No sub-agents were used.**
67|