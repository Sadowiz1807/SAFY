Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.

1|# SAFY Phase 6 UI Specification
2|
3|## Status
4|Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.
5|
6|
7|## Overview
8|Phase 6 adds historical context and management controls to the mock-ui frontend.
9|
10|## 1. Session History Sidebar
11|- **Location:** Left sidebar (new component or expanded existing one).
12|- **Features:**
13|  - List of past sessions with timestamps and previews.
14|  - "New Chat" button to initialize a fresh `chat_id`.
15|  - Selection highlights and switches the main chat view.
16|- **Rendering:**
17|  - Use `textContent` for previews.
18|  - Redact potential secrets in the preview (truncate or mask).
19|
20|## 2. Chat Timeline Restoration
21|- **Behavior:**
22|  - Selecting a session loads previous messages.
23|  - Messages display linked `audit_id` (viewable on click) and `workspace_id`.
24|  - System messages indicate if a session was restored or has pending recovery.
25|
26|## 3. Workspace Management Panel
27|- **Location:** Right sidebar (tabbed with existing query status) or separate modal.
28|- **Features:**
29|  - List of workspaces: `[ID] [Status] [Created] [Cleanup Button]`.
30|  - Status indicators:
31|    - 🟢 Active (Lock held)
32|    - 🟡 Inactive (Stale lock)
33|    - ⚪ Expired
34|  - "Cleanup All Expired" global action.
35|- **Safety:**
36|  - Cleanup button is disabled for active locked workspaces.
37|  - Destructive cleanup requires a confirmation dialog.
38|
39|## 4. Recovery Warnings
40|- **Display:**
41|  - Banner at the top of the chat view if the current session has an interrupted run.
42|  - "Resolve" button linking to recovery options.
43|- **Messaging:**
44|  - `Unknown` or `Ambiguous` states must be clearly labeled as **"Unsafe to restore"**.
45|
46|## 5. Rendering & Safety Rules
47|- **No Raw Stack Traces:** Errors must show normalized messages from the API.
48|- **No Raw Secrets:** Frontend must never receive or store raw passwords or connection strings.
49|- **Escaping:** All user and model content must be escaped before rendering.
50|- **Audit Links:** Audit IDs should be clickable to show a (redacted) event log.
51|
52|---
53|**This spec was produced by the main-agent only. No sub-agents used.**
54|