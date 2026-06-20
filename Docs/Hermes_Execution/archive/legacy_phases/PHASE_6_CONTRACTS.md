Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.

1|# SAFY Phase 6 Contracts
2|
3|## Status
4|Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.
5|
6|
7|## 1. Execution Mode Contract
8|- Phase 6 planning and implementation must be performed by the **main-agent only**.
9|- No delegation to sub-agents is permitted unless explicitly unlocked by the user in a future turn.
10|- The main-agent retains total responsibility for verifying safety boundaries and contract integrity.
11|
12|## 2. Session History Contract
13|- **Persistence:** Chat messages, agent intents, and execution results must be persisted in the runtime database (`Data/safy_runtime.db`).
14|- **Identity:** Every session must have a unique `chat_id` (UUID).
15|- **Redaction:** History records must not contain raw secrets. Only redacted summaries and references (audit IDs) are stored.
16|- **Immutability:** Once written to history, a message or event record should not be modified, only appended.
17|
18|## 3. Recovery Contract
19|- **Detection:** The system must detect interrupted states (e.g., a workspace lock held by a non-existent process or an abandoned `/query/check`).
20|- **Fail Closed:** If a state is ambiguous or safety cannot be proven (e.g., a corrupted check binding), the operation must fail and require a new session or check.
21|- **Revival Prohibited:** Recovery may restore visibility of past metadata, messages, and action timelines, but it must **NEVER** revive consumed, expired, ambiguous, or unverified query checks or confirmation codes.
22|- **Explicit Abandonment:** Any unsafe or expired check/confirmation state must be transitioned to a closed/abandoned status. The user must initiate a fresh `/query/check` to proceed.
23|- **No Bypass:** Recovery must NOT be used as a mechanism to bypass existing one-time-use or expiry gates.
24|- **Audit:** Every recovery attempt and outcome must be recorded in the audit store.
25|
26|## 4. Workspace Management Contract
27|- **Registry:** All sandbox workspaces must be registered in the runtime state with metadata (owner session, creation time, status, path).
28|- **Isolation:** Workspace management actions must respect the path confinement established in Phase 4.
29|- **Listing:** Users can list workspaces associated with their active or past sessions.
30|
31|## 5. Cleanup/Retention Contract
32|- **Lock Protection:** No workspace can be deleted if an active lock (`.lock` file) exists and the process is still running.
33|- **Retention:** Cleanup must preserve workspaces that contain artifacts explicitly marked for retention by the user or required for audit evidence.
34|- **Deterministic Deletion:** Deletion must follow a "move to trash" or "mark for deletion" pattern before physical removal when possible.
35|
36|## 6. Audit Contract
37|- All Phase 6 actions (session creation, history read, workspace cleanup, recovery scan) must produce audit events.
38|- Audit records must be linked to the `chat_id` and `workspace_id`.
39|
40|## 7. Secret/Redaction Contract
41|- No raw connection strings, API keys, or passwords may be stored in session history, workspace metadata, or recovery logs.
42|- Redaction must happen at the point of ingestion (before storage).
43|
44|## 8. Failure/Fail-Closed Contract
45|- Any error in the session or recovery layer must result in a `FAILED` response with a standard SAFY error envelope.
46|- Recovery must not skip security gates (SQL Guard, Permission Check).
47|
48|## 9. Backward Compatibility Contract
49|- Phase 6 implementation must not break the existing behavior of `/agent/chat`, `/query/check`, or `/query/execute`.
50|- Existing tests (Phases 1-5) must pass without modification (unless documentation updates require it).
51|
52|---
53|**Main-agent confirmation: These contracts were defined by the main-agent only. No sub-agents used.**
54|