Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.

1|# SAFY Phase 6 Security Boundary
2|
3|## Status
4|Approved for Phase 6 implementation. This document is the canonical implementation baseline and does not claim Phase 6 is already implemented.
5|
6|
7|## 1. Hard Phase 6 Boundary
8|- Phase 6 planning and implementation focus strictly on **Recovery, Session History, and Workspace Management**.
9|- **Real connected-database adapter execution remains out of scope** unless explicitly approved and separately gated.
10|- Phase 7 (Final Hardening/MVP) is not part of this phase.
11|
12|## 2. Main-Agent-Only Execution Boundary
13|- All Phase 6 activities must be performed by the **main-agent**.
14|- Sub-agent delegation is strictly forbidden for planning and implementation of Phase 6 features.
15|- Verification of security invariants is a non-delegable responsibility of the main-agent.
16|
17|## 3. Recovery Boundary
18|- Recovery must **fail closed** if state is inconsistent or unverified.
19|- Recovery **cannot revive** expired or consumed confirmation codes or query checks.
20|- Recovery must not skip any existing security gate (SQL Guard, Permission Check).
21|- Recovery actions must be audited before execution.
22|
23|## 4. Session History Boundary
24|- History is a **record of evidence**, not a bypass for security checks.
25|- Re-executing an action from history must re-trigger all security gates (SQL Guard, Check/Execute flow).
26|- **No raw secrets** are allowed in session storage.
27|
28|## 5. Workspace Cleanup Boundary
29|- Cleanup must not delete **active locked** workspaces.
30|- Cleanup must preserve workspaces containing artifacts required for **audit or provenance**.
31|- Cleanup actions must be audited.
32|
33|## 6. Audit/Redaction Boundary
34|- Redaction of sensitive data is mandatory for all Phase 6 storage and API outputs.
35|- Audit trails must link session history to physical workspace and database actions.
36|
37|## 7. Confirmation State Boundary
38|- Recovery must not allow a user to bypass a confirmation requirement by "restoring" a past check state.
39|- Confirmation codes remain backend-generated and one-time use.
40|
41|## 8. Non-Boundaries (Out of Scope for Security)
42|- Multi-user authentication/authorization.
43|- Production-grade credential vaulting.
44|- Network-level database firewalls.
45|
46|## 9. Preservation of Prior Boundaries
47|Phase 6 preserves all Phase 1-5 boundaries:
48|- `/query/check` never executes SQL.
49|- `/query/execute` binds `check_id`, `sql_hash`, `target`, and `database_profile_id`.
50|- Agent connected-DB path is read-only only.
51|- Agent destructive connected-DB requests are blocked.
52|- Sandbox mutation remains isolated to `Sandbox/` path.
53|
54|---
55|**This document was produced by the main-agent only. No sub-agents used.**
56|