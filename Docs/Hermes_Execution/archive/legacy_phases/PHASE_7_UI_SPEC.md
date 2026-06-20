# SAFY Phase 7 UI Hardening Specification

Executed by main-agent only. No sub-agents used.

Phase 7 implementation is now approved by the user.
Real connected DB adapter execution remains deferred and is not part of this implementation. No UI changes are implemented in this run.

## Goals
- Display backend envelopes consistently.
- Render errors safely without raw tracebacks.
- Prevent raw secret rendering.
- Improve session history usability.
- Clarify workspace status and cleanup restrictions.
- Clarify recovery warnings and fail-closed outcomes.
- Clarify high-risk confirmation UX without exposing backend codes.
- Disable unsafe actions when state is missing, expired, consumed, locked, or ambiguous.
- Visually distinguish sandbox execution, mock connected DB preview, and real connected DB deferred state.

## UI/Backend Consistency Requirements
- Successful responses render only `data` fields after redaction.
- Failed responses render `error.code` and safe `error.message` as text.
- Unknown or malformed responses show a generic safe error.
- Workspace cleanup buttons are disabled or fail safely for active locked workspaces.
- Recovery actions show abandon/resolve semantics without implying SQL execution.

## Session History Usability
- Session list previews must be redacted and concise.
- Timeline entries should show audit/workspace IDs when present.
- Missing sessions should show the `SESSION_NOT_FOUND` code safely.

## Workspace Status Clarity
- Active, locked, cleaned, stale, and ambiguous states should be visually distinct.
- Active locked cleanup must show `WORKSPACE_ACTIVE_LOCKED` semantics.

## Recovery Warning Clarity
- Recovery scan should communicate that it does not execute SQL.
- Expired/consumed checks and confirmation codes should remain unrecoverable.

## High-Risk Confirmation UX Clarity
- UI must not generate or reveal backend confirmation codes.
- Manual confirmation should be state-bound and one-time.
- Expired/consumed/mismatched states should display safe errors.

## Final Smoke Checklist For `Apps/Web/mock-ui.js`
- `node --check Apps/Web/mock-ui.js` passes.
- No raw traceback rendering.
- No `innerHTML` use for untrusted API output unless explicitly sanitized.
- Unsafe actions have clear disabled/error states.
- Real connected DB remains described as deferred unless separately approved.
