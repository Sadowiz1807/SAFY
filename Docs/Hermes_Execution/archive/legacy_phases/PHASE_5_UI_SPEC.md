# SAFY Phase 5 UI Spec

## Status
Status: Approved for Phase 5 implementation. This document was originally a planning document and is now the canonical implementation baseline for UI work. It does not claim Phase 5 has already been implemented.

## Goals
- Keep the existing static UI usable for Phase 5 connected read-only query flows.
- Clearly separate agent read-only connected database answers from user-controlled query execution.
- Display risk and confirmation state without unsafe rendering.

## Agent Panel
For `POST /agent/chat` responses, the UI should render these fields when present:

- `summary`
- `message`
- `schema_summary`
- `created_objects`
- `target`
- `database_profile_id`
- `sql_hash`
- `audit_id`
- `workspace_id`
- `blocked_reason`

Rules:

- Use `textContent` or explicit escaping for user/model/backend text.
- Do not use raw backend stack traces in visible UI.
- Do not render raw secrets.
- Show a distinct blocked state for agent destructive connected database requests.

## User Query Panel
The query panel must preserve the binding from check to execute:

```js
{
  check_id: safyCurrentCheck.check_id,
  sql_hash: safyCurrentCheck.sql_hash,
  target: safyCurrentCheck.target || 'connected_database',
  database_profile_id: safyCurrentCheck.database_profile_id,
  user_decision: userDecision,
  confirmation_code: code || null
}
```

Rules:

- Disable execute until `/query/check` succeeds.
- Reset saved check state when SQL text, target, or database profile changes.
- Show risk status as safe, warning, danger, or blocked; unknown must not appear safe.
- Show confirmation code input only when backend says `confirmation_required: true`.
- Do not trust frontend-only risk classification for execution.

## Safety Report Display
Display:

- statement type
- target
- database profile id
- risk level
- safety status
- decision
- warnings
- affected tables
- confirmation requirement and expiry
- audit id after execution, if provided

## Error Display
Normalize backend errors:

- show error code
- show short user-safe message
- optionally show redacted details
- never show raw tracebacks, connection strings, passwords, API keys, tokens, or Authorization headers

## Non-goals
- No Phase 6 UI.
- No destructive agent confirmation UI, because agent destructive connected database SQL remains forbidden.
- No credential display UI beyond env-reference/profile identifiers.
