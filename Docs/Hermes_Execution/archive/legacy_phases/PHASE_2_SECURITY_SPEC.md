# Phase 2 Security Spec

## 1. Scope

This document defines Phase 2 security requirements for config loading, profile storage, `.env` secrets, runtime DB, audit DB, redaction, and high-risk confirmation state. It documents requirements and evidence expectations; it does not authorize real LLM calls, sandbox execution, or real database execution.

## 2. Threat Model

Phase 2 must consider:
- Raw secret leak through JSON, API response, audit DB, logs, UI, or error details.
- Accidental log exposure of Authorization headers or provider/database credentials.
- Malformed profile JSON causing unsafe runtime behavior.
- Path traversal through profile/config/database paths.
- Concurrent profile writes causing lost update.
- Partial write causing corrupt `.env` or JSON.
- Corrupt `.env` preventing secret resolution.
- Corrupt SQLite runtime/audit DB.
- Audit DB unavailable or locked during high-risk action.
- Confirmation code replay.
- Confirmation brute force.
- Confirmation code expiry bypass.
- Multi-worker in-memory confirmation state mismatch.
- Runtime provenance, schema snapshot, or workspace lock tampering.

## 3. Secret Handling

- Raw API key is accepted only as inbound profile save input and written only to `.env`.
- Raw DB password is accepted only as inbound profile save input and written only to `.env`.
- JSON profile stores only `api_key_env` or `password_env`.
- API/UI responses return `secret_configured`, `secret_mask`, and env var name where safe, never raw secret.
- Backend callers receiving resolved secret must not log or return it.
- Missing secret returns `MISSING_ENV_SECRET` without exposing env file content.

## 4. Environment File Security

Recommended local permissions:
- `.env`: only app user should read/write where OS supports it.
- `.env.example`: may contain variable names only, no placeholder that resembles a real secret.

Do not claim OS permission enforcement unless implementation explicitly sets and verifies permissions.

`.env` write requirements:
- Validate env variable name.
- Require overwrite confirmation for existing name.
- Stage write before commit.
- Use atomic replace where OS supports it.
- Roll back or preserve previous content on failure where possible.
- Redact secret values in all errors/logs.

## 5. Profile Storage Security

- Model profile JSON must reject raw `api_key`.
- Database profile JSON must reject raw `password`.
- Unknown fields should be rejected unless a migration explicitly allows them.
- Profile paths must resolve under expected project data directories.
- `profile_id` must be constrained to safe characters.
- `api_key_env` and `password_env` must match env naming rule.
- Database profile execution authority uses `user_query_access_mode`; legacy permission fields are migration-only.

## 6. Atomicity and Rollback

Profile save uses transaction-like coordination, not full ACID filesystem transaction:
1. Validate request.
2. Stage `.env` change.
3. Stage profile JSON change.
4. Validate staged outputs.
5. Commit staged files.
6. Roll back or preserve prior state on failure where possible.
7. Return controlled error if rollback fails.

Relevant errors:
- `SECRET_WRITE_FAILED`.
- `PROFILE_STORAGE_WRITE_FAILED`.
- `PROFILE_SAVE_ROLLBACK_FAILED`.
- `SECRET_ROLLBACK_FAILED`.

## 7. File Locking and Concurrency

- Writers to the same `.env` or profile JSON file require exclusive lock.
- Process-local lock is sufficient only for single-process local MVP.
- Multi-process/multi-worker deployment requires file lock library or SQLite coordination.
- Concurrent write failures must return controlled errors and must not expose partial secret values.

Open decision: Windows locking strategy is not finalized.

## 8. Path Validation

- Config/profile/runtime/audit paths must resolve under the project root or approved data root.
- Reject `..` traversal where user-controlled input affects paths.
- Reject absolute paths unless explicitly allowed by a future policy.
- SQLite file paths for sandbox workspaces must be validated before future execution use.

## 9. Runtime DB Security

Runtime DB stores:
- chat runtime state,
- sandbox workspace state,
- workflow object provenance,
- schema snapshots,
- workspace locks,
- confirmation challenge state only if persistent option is selected.

Runtime DB must not store raw API key, DB password, or raw SQL literals by default. `active_connection_id` must not be persisted as durable recovery state. DB file recommended permission is local app-only access where OS supports it. Corrupt DB initialization must return `DATABASE_INITIALIZATION_FAILED` or migration error without unsafe fallback execution.

Runtime metadata requirements:
- `workflow_object_provenance` metadata must be redacted and size-limited; writes require workflow/workspace identity checks.
- `schema_snapshots` schema JSON must be redacted and size-limited; target context must be validated; mutation invalidates relevant snapshots.
- `workspace_locks` metadata must be redacted and size-limited; acquisition is atomic; expired locks may be reclaimed only by documented policy.


## 9.1. Runtime and Audit Schema Version Security

- Historical implementation foundation uses runtime schema `1` and audit schema `1`.
- Final refined target uses runtime schema `2` and audit schema `2`.
- Planning/development may destructively rebuild local runtime/audit DB files, but only with explicit operator/developer action and never as a silent startup side effect.
- Before release v1.0.0, formal v1 -> v2 runtime/audit migrations are required.
- Production startup must not silently delete, downgrade, or rebuild runtime/audit DB files to bypass migration errors.
- Audit DB migration or rebuild failure blocks high-risk Manual SQL execution.

## 10. Audit Security

- Audit DB stores security-sensitive evidence.
- Audit stores `statement_hash` and `redacted_sql`, not raw SQL by default.
- `raw_sql_stored` defaults false.
- `metadata_json` must be redacted and size-limited.
- High-risk action requires audit pre-write success before it can become executable.
- If audit DB is unavailable, high-risk execution fails closed with `AUDIT_WRITE_FAILED`.

V1 audit_log repair fields:
- Post-execution audit update failure after side effect marks repair fields in `audit_log`.
- Required fields include `audit_result_update_status`, `audit_repair_required`, `audit_repair_status`, `audit_repair_attempt_count`, `last_repair_error`, and `last_repair_at`.
- A separate audit repair queue is future work only if retry orchestration becomes complex.

Recommended DB file permission: local app-only access where OS supports it.

## 11. Redaction Rules

Required redaction coverage:
- Authorization header.
- Bearer token.
- `api_key` fields and query params.
- `password` fields and query params.
- `secret` fields and query params.
- DSN password segments.
- PostgreSQL URI credentials.
- MySQL URI credentials.
- URL-encoded credentials.
- Nested JSON values for secret-like keys.
- Query-string secrets.
- Multiline tokens.

Output contract:

```txt
redacted_value: original shape with sensitive value replaced
redactions: list of {category, path_or_location, reason}
```

Example replacement: `[REDACTED:password]`, `[REDACTED:authorization]`, `[REDACTED:dsn_password]`.

## 12. High-risk Confirmation Security

Requirements:
- Cryptographically secure random source preferred.
- Exactly 4 numeric digits.
- Backend-generated only; no LLM generation.
- Visible to UI only as part of challenge flow.
- Bound to `check_id`, `sql_hash`, `target`, and `expires_at`.
- Short TTL.
- Limited attempts.
- Lockout/invalidation after repeated failures.
- Atomic `validate_and_reserve`.
- Single active reservation per challenge.
- Reservation expiry fails closed.
- Single-use consume semantics.
- Cancel support.
- No reuse across different SQL statements.

Because 4 digits provide only 10,000 combinations, attempt limit and TTL are mandatory before production use. Values remain open decisions unless set by `SAFY_source.md`.

## 13. Failure Behavior

- Config failure: return controlled config error, do not continue with guessed defaults for sensitive paths.
- Secret write failure: do not write profile JSON that references missing/uncommitted secret.
- Profile write failure after env stage: roll back `.env` if possible or return rollback-required error.
- Audit pre-write failure for high-risk: return `AUDIT_WRITE_FAILED` and keep execution non-executable.
- Confirmation failure: block execution.
- SQLite locked/unavailable: return controlled error; do not silently skip audit/runtime state.

## 14. Deployment Constraints

If confirmation state is in-memory:
- single worker only,
- backend reload invalidates active challenges,
- multi-worker deployment unsupported until persistent/shared state exists.

If profile write locking is process-local:
- single process writer only,
- multi-process deployment requires stronger locking.

If runtime/audit DB files are generated at startup:
- artifact commit policy must be decided separately.

## 15. Deferred Security Work

- Encryption at rest for `.env`, profile JSON, runtime DB, and audit DB.
- Production authentication/authorization.
- Strong cross-platform file permissions enforcement.
- Persistent/shared high-risk challenge state.
- SQL Guard implementation.
- Real DB connector permission enforcement.
- Audit retention/legal policy.
- Dedicated audit repair queue only if v1 `audit_log` repair fields become insufficient.
- Tamper-evident audit chain.
