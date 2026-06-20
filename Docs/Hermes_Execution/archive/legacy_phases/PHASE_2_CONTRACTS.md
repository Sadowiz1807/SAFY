# Phase 2 Contracts

## 1. Global Rules

- `SAFY_source.md` is the active source of truth.
- Agent connected database path remains read-only.
- User query box is user-controlled and is not silently blocked by `manual_write_enabled`; future execution must follow safety check, confirmation if required, and audit.
- Phase 2 does not perform real SQL execution.
- `/query/check` never executes SQL.
- `/query/execute` remains mock/no real DB execution in Phase 2.
- Raw API keys and DB passwords go only to `.env`.
- JSON profiles store only env var references.
- API responses and log-safe output must mask secrets.
- Existing profile/env overwrite requires explicit confirmation.

## 2. Shared Response and Error Contract

Successful contract result:

```txt
success: true
data: contract-specific object
error: null
meta: request_id, timestamp, schema_version when applicable
```

Failure contract result:

```txt
success: false
data: null or safe partial state
error: code, message, details without raw secrets
meta: request_id, timestamp
```

Errors must be stable string codes. Error details must not contain raw secrets, raw `.env` lines, or unredacted SQL if the contract says SQL is redacted by default.

## 3. ConfigLoader

```python
class ConfigLoader:
    def load_app_config(self) -> AppConfig: ...
    def load_policies(self) -> PolicyConfig: ...
    def load_skills(self) -> SkillsConfig: ...
    def load_toolsets(self) -> ToolsetsConfig: ...
```

- Responsibility: load and validate non-secret configuration from `Configs/app.yaml`, `Configs/policies.yaml`, `Configs/skills.yaml`, and `Configs/toolsets.yaml`.
- Inputs: project root path, config file names, optional environment name.
- Outputs: typed or validated config objects; resolved paths for `Data/User/user_profiles.json`, `Data/Database_management/database_profiles.json`, `Data/safy_runtime.db`, `Data/safy_audit.db`.
- Error codes: `CONFIG_FILE_NOT_FOUND`, `CONFIG_PARSE_ERROR`, `CONFIG_VALIDATION_ERROR`.
- Idempotency behavior: repeated reads return equivalent objects for unchanged files.
- Atomicity behavior: read-only contract; no partial write risk.
- Concurrency behavior: multiple readers are allowed; writers must use separate config update process not defined in Phase 2.
- Security constraints: must not load raw secret values into config objects; only env var names or secret references.
- Lifecycle: initialized with project root, loads files on demand, returns controlled errors, does not cache secrets.

## 4. ProfileStore

- Responsibility: common JSON profile store behavior for model and database profiles.
- Inputs: profile records, profile file path, schema/allowed fields.
- Outputs: stored profile records and masked API-facing profile views.
- Error codes: `PROFILE_VALIDATION_ERROR`, `PROFILE_STORAGE_READ_FAILED`, `PROFILE_STORAGE_WRITE_FAILED`, `PROFILE_NOT_FOUND`, `PROFILE_OVERWRITE_CONFIRMATION_REQUIRED`.
- Idempotency behavior: saving identical profile content with explicit overwrite is idempotent; duplicate save without confirmation must return overwrite-required.
- Atomicity behavior: writes must be staged to a temp file and atomically replaced where OS supports it.
- Concurrency behavior: concurrent writers require a write lock; without a lock the implementation must document single-process limitation.
- Security constraints: raw `api_key` and raw `password` fields are forbidden in JSON.
- Lifecycle: create default JSON if missing, validate input, stage write, commit, return masked profile.

## 5. UserProfileStore

- Responsibility: manage model/provider profiles.
- Inputs: `profile_id`, `display_name`, `provider`, `base_url`, `model`, `api_key_env`, `temperature`, `max_tokens`.
- Outputs: persisted model profile and masked profile view with `secret_configured`/`secret_mask` status where available.
- Error codes: inherits `ProfileStore`; may add `MODEL_PROFILE_INVALID_PROVIDER` later.
- Idempotency behavior: profile_id uniquely identifies upsert target.
- Atomicity behavior: inherited staged JSON write.
- Concurrency behavior: inherited write-lock requirement.
- Security constraints: no `api_key` field in JSON; `api_key_env` must match env naming rule.
- Lifecycle: validate, upsert, persist, return masked view.

## 6. DatabaseProfileStore

- Responsibility: manage database connection profiles without storing raw DB password.
- Inputs: `profile_id`, `display_name`, `dbms`, `host`, `port`, `database`, `username`, `password_env`, `ssl`, `user_query_access_mode`.
- Allowed `user_query_access_mode` values: `credential_permissions`, `read_only`, `disabled`.
- Outputs: persisted database profile and masked profile view.
- Error codes: inherits `ProfileStore`; may add `DATABASE_PROFILE_INVALID_DBMS` later.
- Idempotency behavior: profile_id uniquely identifies upsert target.
- Atomicity behavior: inherited staged JSON write.
- Concurrency behavior: inherited write-lock requirement.
- Security constraints: no `password` field in JSON; agent connected database access is not stored in profile and agent path is always strict read-only.
- Migration rules: `access_mode` is a deprecated migration alias for `user_query_access_mode`; `sandbox_only` is invalid for connected database profile.
- Lifecycle: validate, upsert, persist, return masked view.

## 7. AtomicJsonWriter

- Responsibility: write JSON files safely.
- Inputs: destination path, JSON-serializable object, optional file mode.
- Outputs: commit success or controlled write error.
- Error codes: `JSON_STAGE_WRITE_FAILED`, `JSON_VALIDATION_FAILED`, `JSON_COMMIT_FAILED`, `JSON_ROLLBACK_FAILED`.
- Idempotency behavior: writing identical content should not alter semantic state.
- Atomicity behavior: write temp file in same directory, fsync if available, validate, replace destination atomically where supported.
- Concurrency behavior: requires exclusive write lock for same destination path.
- Security constraints: redaction must happen before data reaches the writer; writer should reject known raw-secret keys when configured for profile files.
- Lifecycle: stage, validate, commit, cleanup temp file, rollback on failure where possible.

## 8. EnvWriter

```python
class EnvWriter:
    def write_secret(
        self,
        env_name: str,
        value: str,
        overwrite_confirmed: bool
    ) -> EnvWriteResult: ...
```

- Responsibility: safely write secret values to `.env`.
- Inputs: env variable name, secret value, overwrite confirmation flag.
- Outputs: `EnvWriteResult` containing env name and masked status only.
- Error codes: `ENV_NAME_INVALID`, `PROFILE_OVERWRITE_CONFIRMATION_REQUIRED`, `SECRET_WRITE_FAILED`, `SECRET_ROLLBACK_FAILED`.
- Idempotency behavior: writing the same value with overwrite confirmation is idempotent in final state; writing existing name without confirmation must not change state.
- Atomicity behavior: validate env name, acquire lock, stage `.env` content, atomically replace if possible, rollback to previous content on failure.
- Concurrency behavior: exactly one writer per `.env` file; use process-local lock for MVP and document if cross-process file lock is absent.
- Security constraints: never return value; never log value; `.env.example` may list names only.
- Lifecycle: validate, detect overwrite, stage write, commit, cleanup/rollback.

## 9. SecretResolver

```python
class SecretResolver:
    def resolve(self, env_name: str) -> str: ...
```

- Responsibility: resolve runtime secret value from environment or `.env` source.
- Inputs: env variable name.
- Outputs: raw secret value only to trusted backend caller; never to API/UI response.
- Error codes: `MISSING_ENV_SECRET`, `ENV_NAME_INVALID`.
- Idempotency behavior: repeated resolution returns current env value for unchanged environment.
- Atomicity behavior: read-only.
- Concurrency behavior: concurrent reads allowed; behavior during write must be documented by EnvWriter lock policy.
- Security constraints: caller must not log returned value; resolver errors must not include value.
- Lifecycle: validate env name, resolve, return or controlled error.

## 10. ProfileSaveCoordinator

```python
class ProfileSaveCoordinator:
    def save_model_profile(self, request: ModelProfileSaveRequest) -> ProfileSaveResult: ...
    def save_database_profile(self, request: DatabaseProfileSaveRequest) -> ProfileSaveResult: ...
```

- Responsibility: coordinate the two-step secret/profile save flow.
- Inputs: profile save request including raw secret and overwrite confirmation flag.
- Outputs: masked profile result; never raw secret.
- Error codes: `PROFILE_VALIDATION_ERROR`, `ENV_NAME_INVALID`, `PROFILE_OVERWRITE_CONFIRMATION_REQUIRED`, `SECRET_WRITE_FAILED`, `PROFILE_STORAGE_WRITE_FAILED`, `PROFILE_SAVE_ROLLBACK_FAILED`.
- Idempotency behavior: repeated request with same profile and confirmed overwrite reaches same final state; unconfirmed overwrite is a no-op returning overwrite-required.
- Atomicity behavior: transaction-like coordination only, not fully ACID filesystem transaction.
- Concurrency behavior: acquire a write lock covering both `.env` and profile JSON target; without cross-process lock, deployment is single-writer only.
- Security constraints: raw secret exists only in request memory and `.env`; JSON stores env reference; response masks secret.
- Lifecycle/workflow:
  1. Validate request.
  2. Generate/validate env name.
  3. Acquire write lock.
  4. Stage `.env` change.
  5. Stage JSON profile change.
  6. Validate staged files.
  7. Commit both.
  8. Roll back if one commit fails where possible.
  9. Return masked profile result.

## 11. RuntimeDB

Required methods:

```txt
initialize()
migrate()
get_schema_version()
upsert_chat_runtime()
get_chat_runtime()
upsert_workspace()
get_workspace()
transfer_workspace_ownership()
expire_records()
record_object_provenance()
get_object_provenance()
mark_object_rolled_back()
mark_object_deleted()
create_schema_snapshot()
get_latest_schema_snapshot()
invalidate_schema_snapshot()
acquire_workspace_lock()
renew_workspace_lock()
release_workspace_lock()
get_workspace_lock()
reclaim_expired_lock()
```

- Responsibility: persist chat/session/workspace runtime state, object provenance, schema snapshots, and workspace locks.
- Inputs: chat runtime records, sandbox workspace records, provenance records, snapshot records, and lock records without raw secrets or raw SQL by default.
- Outputs: persisted records, schema version status, lock acquisition status, latest snapshot, and provenance lookup result.
- Error codes: `DATABASE_INITIALIZATION_FAILED`, `MIGRATION_REQUIRED`, `SCHEMA_VERSION_UNSUPPORTED`, `MIGRATION_FAILED`, `MIGRATION_ROLLBACK_FAILED`, `RUNTIME_RECORD_NOT_FOUND`, `WORKSPACE_LOCK_BUSY`, `WORKSPACE_LOCK_EXPIRED`, `PROVENANCE_NOT_FOUND`, `SCHEMA_SNAPSHOT_NOT_FOUND`.
- Idempotency behavior: initialization/migration repeat safely; upsert by primary key reaches stable state; mark rolled_back/deleted is idempotent for the same terminal status; snapshot invalidation can be repeated for the same target context.
- Atomicity behavior: migrations, lock acquisition, provenance writes, snapshot invalidation, and multi-table updates run inside SQLite transactions; `acquire_workspace_lock` and `reclaim_expired_lock` are compare-and-set operations.
- Concurrency behavior: SQLite single-writer/multi-reader behavior; workspace locks coordinate query/mutation/cleanup/recovery; concurrent acquisition of the same `(workspace_id, lock_type)` returns controlled busy/error unless reclaim policy applies.
- Security constraints: no raw API keys/passwords; no raw SQL literals by default; provenance metadata and snapshot JSON are redacted/size-limited; snapshot target paths/context must be validated; lock metadata must be redacted to reduce lock poisoning risk.
- Lifecycle: initialize, migrate, read/write state, record provenance after verified DDL result, create/invalidate snapshots, acquire/renew/release/reclaim locks, expire stale records, close connection.

Per-method contract summary:

| Method | Inputs | Outputs | Errors | Idempotency | Atomicity | Concurrency behavior | Security constraints |
|---|---|---|---|---|---|---|---|
| `record_object_provenance()` | provenance fields | `object_id` | `PROVENANCE_WRITE_FAILED` | same object identity updates same record | transaction | one writer per object identity | redacted metadata only |
| `get_object_provenance()` | object identity/workflow | provenance record | `PROVENANCE_NOT_FOUND` | read-only | read transaction | concurrent reads allowed | no raw secrets |
| `mark_object_rolled_back()` | `object_id` | updated status | `PROVENANCE_NOT_FOUND` | repeated call stable | transaction | serializes status update | verify workflow ownership |
| `mark_object_deleted()` | `object_id` | updated status | `PROVENANCE_NOT_FOUND` | repeated call stable | transaction | serializes status update | verify workflow ownership |
| `create_schema_snapshot()` | target context, redacted `schema_json` | `snapshot_id` | `SCHEMA_SNAPSHOT_WRITE_FAILED` | same hash may reuse/return latest by policy | transaction | writer lock | size limit, no secrets |
| `get_latest_schema_snapshot()` | target context | snapshot/null | `SCHEMA_SNAPSHOT_NOT_FOUND` | read-only | read transaction | concurrent reads allowed | no secrets returned |
| `invalidate_schema_snapshot()` | target context/reason | invalidation count | `SCHEMA_SNAPSHOT_INVALIDATION_FAILED` | repeat stable | transaction | serializes invalidation | reason redacted |
| `acquire_workspace_lock()` | workspace, lock type, owner, ttl | lock result | `WORKSPACE_LOCK_BUSY` | same owner may renew by policy | compare-and-set transaction | only one active lock per key | metadata redacted |
| `renew_workspace_lock()` | workspace, lock type, owner, ttl | lock result | `WORKSPACE_LOCK_EXPIRED` | repeated renew extends owned lock | transaction | owner-only | metadata redacted |
| `release_workspace_lock()` | workspace, lock type, owner | release result | `WORKSPACE_LOCK_NOT_FOUND` | repeated release stable | transaction | owner-only unless force policy | metadata redacted |
| `get_workspace_lock()` | workspace, lock type | lock/null | none | read-only | read transaction | concurrent reads allowed | no secrets |
| `reclaim_expired_lock()` | workspace, lock type, owner | lock result | `WORKSPACE_LOCK_BUSY` | stable if already reclaimed by owner | compare-and-set transaction | only expired locks reclaimed | audit reclaim metadata |

## 12. AuditStore

Required methods:

```txt
initialize()
write_pre_execution_event()
write_post_execution_event()
write_failure_event()
mark_audit_repair_required()
record_audit_repair_attempt()
mark_audit_repaired()
mark_audit_repair_failed_permanent()
health_check()
```

- Responsibility: persist security/audit events. For Safy product v1.0.0, audit repair state is stored in `audit_log` fields introduced by audit schema v2.
- Inputs: endpoint/action/context, statement hash, redacted SQL, risk metadata, confirmation metadata, error metadata, repair status/update metadata.
- Outputs: audit id, audit status, repair status, health status.
- Error codes: `AUDIT_WRITE_FAILED`, `AUDIT_DB_UNAVAILABLE`, `AUDIT_SCHEMA_INVALID`, `AUDIT_METADATA_TOO_LARGE`, `AUDIT_REPAIR_REQUIRED`, `AUDIT_REPAIR_FAILED_PERMANENT`.
- Idempotency behavior: audit writes are append-only for execution events; repair status updates are idempotent by `audit_id` and terminal state.
- Atomicity behavior: each audit event/repair update is a SQLite transaction.
- Concurrency behavior: SQLite writer lock must be handled with retry/controlled failure; concurrent repair attempts serialize by `audit_id`.
- Security constraints: raw SQL is not stored by default; raw secrets must be redacted; repair errors are redacted and size-limited.
- Lifecycle: initialize, health check, write pre-execution event, write post-execution event, mark repair required on post-execution update failure, record repair attempts, mark repaired or failed permanent, close.
- V1.0.0 audit repair design: repair state uses fields in `audit_log`; a separate `audit_repair_queue` is a future enhancement, not a current alternative.

## 13. AuditLogger

- Responsibility: orchestrate redaction, statement hashing, and audit store writes.
- Inputs: sensitive action request and SQL/context if applicable.
- Outputs: audit result or controlled error.
- Error codes: inherits `AuditStore`; adds `REDACTION_FAILED` if redaction cannot complete.
- Idempotency behavior: logging is append-only; repeated calls create repeated evidence unless caller supplies future idempotency key.
- Atomicity behavior: redaction/hash happens before DB write; DB write is transactional.
- Concurrency behavior: follows AuditStore.
- Security constraints: high-risk pre-write failure must fail closed.
- Lifecycle: redact, hash, write pre/post/failure event.

High-risk rule:

```txt
If audit pre-write fails:
- return AUDIT_WRITE_FAILED
- execution state must remain non-executable
- fail closed
```

## 14. Redactor

- Responsibility: redact secrets and sensitive tokens from strings/objects before logging or audit persistence.
- Inputs: text, JSON-like object, headers, DSN/URI strings, SQL string.
- Outputs: redacted value plus redaction reason/category.
- Error codes: `REDACTION_FAILED`, `REDACTION_INPUT_UNSUPPORTED`.
- Idempotency behavior: redacting already-redacted content leaves it safe.
- Atomicity behavior: pure transformation.
- Concurrency behavior: stateless and safe for concurrent calls.
- Security constraints: must redact Authorization headers, bearer tokens, api_key, password, secret, DSN passwords, URI credentials, URL query secrets, nested JSON secrets, multiline tokens.
- Lifecycle: detect, replace with `[REDACTED:<category>]`, return metadata.

## 15. HighRiskCodeState

```python
class HighRiskCodeState:
    def create(
        self,
        check_id: str,
        sql_hash: str,
        target: str,
        ttl_seconds: int
    ) -> ConfirmationChallenge: ...

    def validate_and_reserve(
        self,
        check_id: str,
        code: str,
        sql_hash: str,
        target: str,
        requester_id: str
    ) -> ConfirmationAuthorizationResult: ...

    def mark_consumed(self, authorization_id: str) -> None: ...

    def release_reservation(
        self,
        authorization_id: str,
        reason: str
    ) -> None: ...

    def cancel(self, check_id: str) -> None: ...
```

- Responsibility: create, atomically validate/reserve, consume, release, and cancel backend-generated high-risk confirmation challenges.
- Inputs: check id, SQL hash, target, code, TTL, authorization id, release reason.
- Outputs: challenge with visible 4-digit code for UI in mock/dev contract, authorization result, lifecycle status.
- Error codes: `CONFIRMATION_CODE_REQUIRED`, `CONFIRMATION_CODE_INVALID`, `CONFIRMATION_CODE_EXPIRED`, `CONFIRMATION_CODE_ALREADY_USED`, `QUERY_SQL_CHANGED`, `QUERY_TARGET_MISMATCH`, `QUERY_CHECK_CANCELLED`.
- Idempotency behavior: replay after `consumed` returns already-used; release on a non-active reservation returns a controlled no-op/error according to policy.
- Atomicity behavior: `validate_and_reserve` must be atomic and must prevent two concurrent reservations for the same challenge.
- Concurrency behavior: reserved challenge cannot be used by another request; single-worker in-memory state is valid only for MVP; multi-worker requires shared/persistent state.
- Security constraints: backend-generated only, no LLM generation, exactly 4 numeric digits, limited attempts, short TTL, single-use, no reuse across SQL statements.
- Lifecycle: `created -> active -> reserved -> consumed | expired | cancelled | invalidated`; execution failure before side effect calls `release_reservation` or invalidates by policy.

## 16. RuntimeDB Final Methods

Additional required methods:

```txt
record_object_provenance()
get_object_provenance()
mark_object_rolled_back()
create_schema_snapshot()
get_latest_schema_snapshot()
invalidate_schema_snapshot()
acquire_workspace_lock()
release_workspace_lock()
renew_workspace_lock()
get_workspace_lock()
```

- Object provenance methods enforce workflow ownership before rollback/drop.
- Schema snapshot methods provide verification/Text-to-SQL context and invalidation after mutation.
- Workspace lock methods atomically coordinate cleanup, query, schema mutation, recovery, and ownership transfer.
- Migration errors are standardized as `MIGRATION_REQUIRED`, `SCHEMA_VERSION_UNSUPPORTED`, `MIGRATION_FAILED`, `MIGRATION_ROLLBACK_FAILED`, and `DATABASE_INITIALIZATION_FAILED`.

## 17. Permission and Audit Repair Contract Updates

- Database profiles use `user_query_access_mode`; `access_mode` is deprecated alias only.
- Supported DBMS v1.0.0 are `postgresql`, `mysql`, and `sqlite`; `sqlserver` and `oracle` are future/unsupported.
- High-risk audit pre-write failure fails closed before execution.
- Post-execution audit update failure may happen after side effects; return SQL result only if side effect already occurred, mark audit repair required, and create a retryable repair record/task.
