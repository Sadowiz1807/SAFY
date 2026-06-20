# Safy Runtime and Sandbox Specification

## Purpose
Define runtime IDs, workspace lifecycle, recovery, sandbox execution, SQLite policy, multi-statement handling, cleanup, audit interaction, and failure modes.

## Scope
Covers chat_id, workflow_id, workspace_id, ownership, recovery, Docker sandbox, SQLite runner, one-container-many-workspaces isolation, multi-statement SQL, cleanup policy, audit interaction, and failure modes.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Runtime Overview
Safy runtime tracks chats, workflows, workspaces, schema snapshots, object provenance, locks, and migrations. Runtime state exists to safely connect user intent to sandbox and connected database execution without persisting unsafe connection handles or secrets.

## 2. Runtime IDs
Required IDs:
- `request_id`: per API request.
- `chat_id`: user session/conversation lifecycle.
- `workflow_id`: agent workflow or Manual SQL execution flow.
- `workspace_id`: sandbox workspace.
- `schema_snapshot_id`: read-back schema snapshot.
- `audit_id`: audit record.

IDs should be opaque strings with prefixes such as `req_`, `chat_`, `wf_`, `ws_`, `snap_`, `audit_`.

## 3. chat_id Lifecycle
Lifecycle:
- Created by explicit `/chat/new` or lazy-created by `/agent/chat` if missing.
- Active while user works.
- Ended by `/chat/end`.
- May become recovered/transferred when workspace ownership transfers.

Rules:
- API must not crash when frontend has no `chat_id`.
- Lazy creation is allowed for `/agent/chat`.
- Recovery flow handles old workspace access.

## 4. workflow_id Lifecycle
A workflow_id is created for each agent workflow or Manual SQL execution. It links skill/tool actions, audit, created objects, and result summaries.

Rules:
- Created objects must reference workflow_id.
- Audit events should reference workflow_id.
- Rollback-safe object drops require workflow/object provenance.

## 5. workspace_id Lifecycle
Lifecycle:
- Created when sandbox workflow needs execution.
- Active during chat.
- May expire by TTL.
- Cleanup transitions active -> closing -> deleted.

Rules:
- Workspace mutation invalidates schema_snapshot_id.
- Cleanup and Manual SQL mutation require workspace lock.
- Queries rejected while workspace is closing.

## 6. Workspace Ownership
Required rule:

```txt
one workspace → one active chat_id
```

A workspace belongs to exactly one active chat at a time. Ownership prevents stale chats from executing into recovered workspaces.

## 7. Recovery Flow
Recovery rules:
- `GET /runtime/recoverable-workspaces` lists recoverable workspaces.
- `POST /chat/recover` transfers workspace ownership atomically.
- Old chat status becomes `recovered` or `transferred`.
- Stale old chat cannot execute into recovered workspace.
- Recovery must update runtime DB atomically.

## 8. Docker Sandbox Policy
PostgreSQL/MySQL sandbox:
- Use Docker.
- One-container-many-workspaces is allowed for v1.0.0.
- PostgreSQL isolation uses explicit workspace schema and `search_path`.
- MySQL isolation uses selected workspace database.
- Cross-workspace qualified names must be blocked.
- Cleanup requires lock and safe status transition.

## 9. SQLite Runner Policy
SQLite rules:
- SQLite runner is used only when target DBMS is SQLite.
- SQLite must not validate PostgreSQL/MySQL SQL.
- `sandbox_sqlite_path` is generated inside workspace and not user-supplied.
- `connected_sqlite_path` comes from database profile, is explicit, normalized, and validated.
- Block `../` traversal and protected paths such as secrets/source/config/cache.

Path policy:

```txt
sandbox_sqlite_path:
- generated inside workspace.
- not user-supplied.

connected_sqlite_path:
- explicit from database profile.
- normalized/validated.
- block ../ and protected paths.
```

## 10. One-container-many-workspaces Isolation
Workspace mapping:

```txt
PostgreSQL:
workspace = schema inside sandbox database

MySQL:
workspace = database/schema inside sandbox container

SQLite:
workspace = file-based temporary DB
```

Isolation rules:
- PostgreSQL must set `search_path` explicitly.
- MySQL must select current workspace database and block qualified names outside it.
- SQLite path must stay inside approved workspace directory.
- TTL cleanup, chat_end cleanup, and Manual SQL mutation must not run while another execution holds workspace lock.

## 11. Multi-statement Handling
Agent connected DB:
- Block multi-statement.

Manual SQL:
- Split/risk-analyze each statement.
- Validate every statement.
- Aggregate risk by highest-risk statement.
- Execute only after target policy, confirmation, audit, and permissions pass.

Sandbox create workflow:
- Multi-statement allowed only after split/parse/validate per statement.
- Use transaction if supported by DBMS and statement set.

## 12. Cleanup Policy
Cleanup triggers:
- `/chat/end` with cleanup.
- TTL expiration.
- Internal rollback/failed workflow cleanup.

Rules:
- Cleanup requires workspace lock.
- Cleanup can drop only owned workspace objects/workspaces.
- Workspace status transitions active -> closing -> deleted.
- Queries and mutations rejected while closing.
- Audit cleanup action.

## 13. Audit Interaction
Audit is required for:
- High-risk Manual SQL pre-write.
- Sandbox workflow execution metadata.
- Connected database query metadata.
- Cleanup and recovery actions.
- Blocked high-risk attempts when relevant.

High-risk audit failure:
- Pre-execution failure blocks execution.
- Post-execution update failure returns `audit_result_update_status = failed` and records retryable repair task.

## 14. Failure Modes
Required controlled failures:
- `WORKSPACE_NOT_FOUND`.
- `WORKSPACE_LOCKED`.
- `WORKSPACE_CLOSING`.
- `WORKSPACE_OWNERSHIP_CONFLICT`.
- `CHAT_RECOVERED_OR_TRANSFERRED`.
- `SANDBOX_UNAVAILABLE`.
- `SQL_PARSE_FAILED`.
- `SQL_POLICY_BLOCKED`.
- `AUDIT_WRITE_FAILED`.
- `MIGRATION_REQUIRED`.
- `MIGRATION_FAILED`.

Race-condition tests needed later:
- Cleanup vs query.
- Cleanup vs Manual SQL mutation.
- Concurrent Manual SQL.
- Audit timeout after execution.

## Implementation Notes
Implement locks and status checks before enabling cleanup and Manual SQL mutation. Treat recovery transfer as an atomic DB transaction.

## Related Documents
- `01_ARCHITECTURE.md`
- `02_API_SPEC.md`
- `03_DATA_SCHEMA.md`
- `04_CONFIG_SPEC.md`
- `05_SECURITY_POLICY.md`
- `09_TOOLS_SPEC.md`
