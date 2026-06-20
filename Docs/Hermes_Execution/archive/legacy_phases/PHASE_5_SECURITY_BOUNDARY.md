# SAFY Phase 5 Security Boundary

## Status
Status: Approved for Phase 5 implementation. This document was originally a planning document and remains the mandatory security boundary for implementation. It does not claim Phase 5 has already been implemented.

## Hard Boundary
Phase 5 may introduce connected database read-only agent queries and user-controlled query execution through the check/execute gate. It must not introduce connected database destructive execution by the agent.

## Agent Boundary
Allowed:

- Read-only connected database SQL after intent policy, SQL Guard, permission checks, and adapter read-only proof.
- Sandbox DDL only through existing sandbox tools and path confinement.

Forbidden:

- Agent DML against connected databases.
- Agent DDL against connected databases.
- Agent admin, privilege, extension, maintenance, transaction-control, or destructive SQL against connected databases.
- Agent bypass of `/query/check` for user query execution.
- Agent generation or validation of high-risk confirmation codes.

## User Query Boundary
Allowed only through:

1. `/query/check`
2. Backend state binding and audit
3. `/query/execute`
4. Matching `check_id`, `sql_hash`, `target`, and `database_profile_id`
5. Confirmation code when required

Any missing, expired, consumed, or mismatched binding fails closed.

## Confirmation Code Boundary
- Backend generated only.
- Bound to `check_id`, `sql_hash`, `target`, and `database_profile_id`.
- One-time use.
- Expiring.
- Audited.
- Not generated, interpreted, or bypassed by LLM.

## Secret Boundary
Forbidden in JSON, logs, audit, reports, fixtures, frontend files, and API responses:

- raw API keys
- raw database passwords
- Bearer tokens
- connection-string passwords
- provider tokens

Allowed:

- env variable names such as `SAFY_DB_PASSWORD`
- profile ids
- SQL hashes
- redacted placeholders

## Adapter Boundary
Connected database adapter must:

- Receive only the minimal profile reference and resolved secret at the last responsible moment.
- Never persist raw secret material.
- Reject non-read-only agent SQL before opening a connection.
- Fail closed on unsupported DBMS, missing secret reference, parse uncertainty, or permission mismatch.
- Return redacted errors.

## Audit Boundary
Audit must record enough for review without secrets:

- event type
- actor type
- target
- database profile id
- SQL hash
- safety decision
- confirmation state transition
- adapter status
- redacted metadata

## Explicit Non-boundaries
These are not Phase 5 permissions:

- Phase 6 implementation
- Production auth/RBAC
- Destructive agent connected database execution
- Secret vault migration beyond existing env-reference contract
- Unreviewed real provider network behavior changes
