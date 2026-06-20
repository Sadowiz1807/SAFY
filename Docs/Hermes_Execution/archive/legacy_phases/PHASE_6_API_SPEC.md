Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.

1|# SAFY Phase 6 API Specification
2|
3|## Status
4|Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.
5|
6|
7|## Overview
8|Phase 6 adds endpoints for session management, workspace monitoring, and state recovery. All responses use the standard SAFY envelope.
9|
10|## Standard Envelope
11|All endpoints must use this exact structure:
12|```json
13|{
14|  "success": true|false,
15|  "data": object | null,
16|  "error": {
17|    "code": string,
18|    "message": string
19|  } | null,
20|  "meta": {
21|    "audit_id": "...",
22|    "timestamp": "iso",
23|    "version": "1.0"
24|  }
25|}
26|```
27|
28|## 1. Session Endpoints
29|
30|### `GET /sessions`
31|- **Purpose:** List all stored chat sessions.
32|- **Response Data:** `[{"chat_id": "uuid", "created_at": "iso", "last_message_preview": "redacted text", "status": "active|archived"}]`
33|- **Audit:** Record session list access.
34|- **Redaction:** Truncate/redact message previews for sensitive content.
35|
36|### `GET /sessions/{chat_id}`
37|- **Purpose:** Retrieve the full message history for a session.
38|- **Response Data:** `{"chat_id": "uuid", "messages": [{"role": "user|assistant", "content": "redacted", "timestamp": "iso", "audit_id": "...", "workspace_id": "..."}]}`
39|- **Audit:** Record full history retrieval for specific chat_id.
40|- **Redaction:** All message content must be filtered for raw secrets.
41|
42|### `GET /sessions/{chat_id}/timeline`
43|- **Purpose:** Retrieve a granular timeline of all events (messages + agent actions + query checks) linked to a session.
44|- **Response Data:** `{"chat_id": "uuid", "events": [{"type": "message|action|check", "timestamp": "iso", "content": "redacted summary", "audit_id": "...", "status": "success|failed"}]}`
45|- **Audit:** Record timeline retrieval.
46|- **Redaction:** Action summaries and check results must be redacted.
47|
48|## 2. Workspace Endpoints
49|
50|### `GET /workspaces`
51|- **Purpose:** List all sandbox workspaces and their status.
52|- **Response Data:** `[{"workspace_id": "...", "chat_id": "...", "status": "active|locked|expired", "created_at": "iso"}]`
53|- **Audit:** Record workspace inventory access.
54|- **Redaction:** Paths and metadata must not expose internal host secrets.
55|
56|### `GET /workspaces/{workspace_id}`
57|- **Purpose:** Retrieve detailed metadata for a specific workspace.
58|- **Response Data:** `{"workspace_id": "...", "chat_id": "...", "status": "...", "path_redacted": "...", "created_at": "iso", "lock_info": null|object}`
59|- **Audit:** Record workspace metadata inspection.
60|- **Redaction:** Real filesystem paths must be redacted to relative sandbox paths.
61|
62|### `POST /workspaces/{workspace_id}/cleanup`
63|- **Purpose:** Manually trigger cleanup for a specific workspace.
64|- **Response Data:** `{"message": "Workspace [id] successfully removed."}`
65|- **Audit:** Record cleanup intent and outcome. Mandatory audit pre-write.
66|- **Redaction:** Ensure no file content snippets appear in error logs if cleanup fails.
67|
68|## 3. Recovery Endpoints
69|
70|### `POST /recovery/scan`
71|- **Purpose:** Scan the runtime environment for interrupted runs, stale locks, or inconsistent state.
72|- **Response Data:** `{"scan_id": "uuid", "found_issues": [{"type": "stale_lock", "id": "...", "severity": "high"}]}`
73|- **Audit:** Record start of recovery scan and findings.
74|- **Redaction:** Redact issue details (e.g., raw SQL in a stalled check).
75|
76|### `GET /recovery/status`
77|- **Purpose:** Retrieve the status of current recovery operations or pending issues.
78|- **Response Data:** `{"pending_recoveries": [{"type": "workspace_lock", "id": "...", "severity": "low|high"}]}`
79|- **Audit:** Record recovery status check.
80|- **Redaction:** Standard redaction applies.
81|
82|### `POST /recovery/resolve`
83|- **Purpose:** Attempt to resolve an identified interrupted state.
84|- **Body:** `{"recovery_id": "...", "action": "cleanup|restore|abandon"}`
85|- **Response Data:** `{"status": "resolved|failed", "detail": "..."}`
86|- **Audit:** Mandatory audit of the resolution action taken and its result.
87|- **Redaction:** Resolution details must not expose unverified data.
88|
89|## Error Codes
90|- `SESSION_NOT_FOUND`: The requested chat session does not exist.
91|- `WORKSPACE_NOT_FOUND`: The requested workspace does not exist.
92|- `WORKSPACE_ACTIVE_LOCKED`: Cannot delete a workspace with an active lock.
93|- `WORKSPACE_CLEANUP_BLOCKED`: Deletion failed due to permission or audit constraints.
94|- `RECOVERY_SCAN_REQUIRED`: No recovery state available; run scan first.
95|- `RECOVERY_UNSAFE_TO_RESOLVE`: State is too ambiguous to resolve safely.
96|- `RECOVERY_STATE_AMBIGUOUS`: Conflicting state information found.
97|- `AUDIT_PREWRITE_FAILED`: Failed to record the action before execution.
98|- `SECRET_REDACTION_REQUIRED`: Request contained unredacted secrets.
99|
100|---
101|**This spec was produced by the main-agent only. No sub-agents used.**
102|