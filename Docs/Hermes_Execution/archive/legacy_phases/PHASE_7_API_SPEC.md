# SAFY Phase 7 API Consistency Specification

Executed by main-agent only. No sub-agents used.

Phase 7 implementation is now approved by the user.
Real connected DB adapter execution remains deferred and is not part of this implementation. Phase 7 does not require new endpoints by default.

## Standard Envelope Requirement
All existing endpoints should return the SAFY envelope: `success`, `data`, `error`, and `meta`. Error responses must use a stable `error.code` and safe `error.message`.

## Error Code Normalization Requirement
Phase 7 implementation should audit endpoint groups for stable error codes and remove ambiguous string-only failures. `WORKSPACE_ACTIVE_LOCKED` is the canonical active locked cleanup code.

## Redaction Requirement
All endpoint output must pass through appropriate redaction before reaching JSON responses, including nested metadata.

## Audit Requirement
Safety-relevant endpoint groups must preserve audit/provenance IDs when available and must not log raw secrets.

## Per-endpoint Final Acceptance Checklist
### Profiles
- Envelope returned for list/save/get paths.
- Env var names allowed; raw keys/passwords disallowed.
- Errors are safe and do not expose provider credentials.

### Chat/Agent
- Envelope returned for `/agent/chat`.
- Agent cannot execute destructive connected DB actions.
- Connected DB remains mock/preview only unless separately approved.
- Session history stores redacted messages and metadata.

### Query Check/Execute
- `/query/check` never executes SQL.
- `/query/execute` requires valid bound check state.
- Expired, consumed, mismatched, missing, or ambiguous state fails closed.
- High-risk confirmation code remains backend-generated and one-time.

### Sessions
- List, detail, and timeline use standard envelope.
- Missing sessions return `SESSION_NOT_FOUND`.
- Output is redacted.

### Workspaces
- List, detail, and cleanup use standard envelope.
- Missing workspaces return `WORKSPACE_NOT_FOUND`.
- Active locked cleanup returns `WORKSPACE_ACTIVE_LOCKED` and does not delete the workspace.
- Output is redacted and audit/provenance evidence preserved.

### Recovery
- Status, scan, and resolve paths use standard envelope.
- Recovery scan does not execute SQL.
- Recovery does not revive expired/consumed checks or confirmation codes.
- Ambiguous recovery state fails closed.

### Health/Status If Present
- Must use the standard envelope or explicitly documented compatibility shape.
- Must not expose raw environment, secrets, stack traces, or database connection strings.

## Optional Endpoint Proposals
Any optional endpoint discovered during Phase 7 must be marked planning-only and not implemented until user approval.
