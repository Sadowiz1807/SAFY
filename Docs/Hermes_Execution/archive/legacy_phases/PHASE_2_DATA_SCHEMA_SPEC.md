# Phase 2 Data Schema Spec

Source of truth: `SAFY_source.md`.

## 1. JSON Profile Container Format

Current v1 format for `Data/User/user_profiles.json` and `Data/Database_management/database_profiles.json`:

Profile JSON `schema_version` is independent from `runtime_schema_version` and `audit_schema_version`. Profile JSON remains schema version `1` unless a separate profile-schema migration is approved.


```json
{
  "schema_version": 1,
  "profiles": []
}
```

- `schema_version` is required integer, current value `1`.
- `profiles` is a required array.
- Unknown top-level fields are rejected unless a migration explicitly allows them.
- Raw secrets are forbidden in profile JSON.

## 2. Model Profile JSON Schema

| Field | Type | Required | Nullable | Default | Validation | Example |
|---|---|---:|---:|---|---|---|
| `profile_id` | string | yes | no | none | unique; `^[A-Za-z0-9_-]{1,80}$` | `local_openai` |
| `display_name` | string | yes | no | none | 1..120 chars | `Local OpenAI` |
| `provider` | string | yes | no | none | non-empty provider id | `openai` |
| `base_url` | string | yes | no | none | URL/mock URI accepted by policy | `https://api.openai.com/v1` |
| `model` | string | yes | no | none | non-empty model id | `gpt-4.1` |
| `api_key_env` | string | yes | no | none | env name `^[A-Z_][A-Z0-9_]*$` | `SAFY_MODEL_LOCAL_OPENAI_API_KEY` |
| `temperature` | number | no | no | `0.2` | `0.0..2.0` | `0.2` |
| `max_tokens` | integer | no | no | provider default | positive integer | `4096` |

Constraints: `profile_id` unique; no raw `api_key`; no unknown profile fields unless migration allows.

## 3. Database Profile JSON Schema

Supported DBMS v1.0.0: `postgresql`, `mysql`, `sqlite`. Future/unsupported in v1.0.0: `sqlserver`, `oracle`.

| Field | Type | Required | Nullable | Default | Validation | Example |
|---|---|---:|---:|---|---|---|
| `profile_id` | string | yes | no | none | unique; `^[A-Za-z0-9_-]{1,80}$` | `local_postgres` |
| `display_name` | string | yes | no | none | 1..120 chars | `Local Postgres` |
| `dbms` | string | yes | no | none | enum: `postgresql`, `mysql`, `sqlite` | `postgresql` |
| `host` | string | conditional | no | none | hostname/IP for network DB; safe path policy for SQLite | `localhost` |
| `port` | integer | conditional | yes | DBMS default | `1..65535` when present | `5432` |
| `database` | string | yes | no | none | non-empty database name/path | `safy_demo` |
| `username` | string | conditional | yes | none | required for network DB unless auth mode says otherwise | `safy_user` |
| `password_env` | string | conditional | yes | none | env name `^[A-Z_][A-Z0-9_]*$` | `SAFY_DB_LOCAL_POSTGRES_PASSWORD` |
| `ssl` | boolean | no | no | `false` | boolean only | `false` |
| `user_query_access_mode` | string | yes | no | `credential_permissions` | enum: `credential_permissions`, `read_only`, `disabled` | `credential_permissions` |

Constraints:
- `access_mode` is deprecated alias for `user_query_access_mode` only during migration.
- `sandbox_only` is not valid for connected database profile.
- Agent connected database access is fixed read-only and not stored in profile.
- No raw `password` field.

## 4. Runtime DB Schema

DB path: `Data/safy_runtime.db`. Historical foundation schema version: `1`. Final refined target schema version: `2`.

### `schema_version`

| Column | SQL Type | Nullable | Default | Key | Constraints |
|---|---|---:|---|---|---|
| `component` | TEXT | no | none | primary | component name |
| `version` | INTEGER | no | none | none | positive integer |
| `applied_at` | TEXT | no | app UTC | none | ISO-8601 |
| `notes` | TEXT | yes | null | none | migration notes |

### `chat_runtime`

| Column | SQL Type | Nullable | Default | Key/Index | Constraints |
|---|---|---:|---|---|---|
| `chat_id` | TEXT | no | none | primary | stable chat id |
| `current_workspace_id` | TEXT | yes | null | index/fk draft | workspace id |
| `last_workflow_id` | TEXT | yes | null | none | workflow id |
| `chat_status` | TEXT | no | `active` | index | enum below |
| `target_dbms` | TEXT | yes | null | none | `postgresql`, `mysql`, `sqlite` |
| `execution_target` | TEXT | yes | null | none | `sandbox`, `connected_database`, `none` |
| `created_at` | TEXT | no | app UTC | none | ISO-8601 |
| `last_active_at` | TEXT | no | app UTC | index | ISO-8601 |
| `expires_at` | TEXT | yes | null | index | ISO-8601 |

`chat_status`: `active`, `ended`, `expired`, `recovered`, `transferred`, `error`.
Indexes: `chat_runtime(last_active_at)`, `chat_runtime(expires_at)`.

### `sandbox_workspaces`

| Column | SQL Type | Nullable | Default | Key/Index | Constraints |
|---|---|---:|---|---|---|
| `workspace_id` | TEXT | no | none | primary | stable workspace id |
| `chat_id` | TEXT | yes | null | index | owner chat |
| `dbms` | TEXT | yes | null | none | `postgresql`, `mysql`, `sqlite` |
| `container_name` | TEXT | yes | null | none | sandbox metadata |
| `container_id` | TEXT | yes | null | none | sandbox metadata |
| `database_name` | TEXT | yes | null | none | target database |
| `schema_name` | TEXT | yes | null | none | target schema |
| `sqlite_file_path` | TEXT | yes | null | none | validated path |
| `host` | TEXT | yes | null | none | sandbox host |
| `port` | INTEGER | yes | null | none | `1..65535` |
| `workspace_status` | TEXT | no | `creating` | index | enum below |
| `created_at` | TEXT | no | app UTC | none | ISO-8601 |
| `last_active_at` | TEXT | no | app UTC | none | ISO-8601 |
| `expires_at` | TEXT | yes | null | index | ISO-8601 |

`workspace_status`: `creating`, `active`, `idle`, `closing`, `expired`, `deleted`, `orphaned`, `error`.
Transitions: `creating -> active`; `active -> idle`; `active/idle -> closing`; `closing -> deleted`; `active/idle -> expired`; `expired -> closing/deleted`; `any -> error`.
Indexes: `sandbox_workspaces(chat_id)`, `sandbox_workspaces(workspace_status)`, `sandbox_workspaces(expires_at)`.

### `workflow_object_provenance`

Purpose: track which object was created by which workflow for safe rollback/drop.

| Column | SQL Type | Nullable | Default | Key/Index | Constraints |
|---|---|---:|---|---|---|
| `object_id` | TEXT | no | generated | primary | stable object identity hash/id |
| `workflow_id` | TEXT | no | none | index | owning workflow |
| `chat_id` | TEXT | yes | null | none | chat context |
| `workspace_id` | TEXT | no | none | index | workspace context |
| `object_type` | TEXT | no | none | composite index | table/view/index/schema/etc. |
| `object_name` | TEXT | no | none | composite index | object name |
| `parent_object_name` | TEXT | yes | null | none | parent object if any |
| `database_name` | TEXT | no | none | unique identity component | database context |
| `schema_name` | TEXT | yes | null | unique identity component | schema context |
| `created_by_skill` | TEXT | yes | null | none | skill id |
| `created_at` | TEXT | no | app UTC | none | ISO-8601 |
| `ownership_status` | TEXT | no | `created` | index | enum below |
| `rollback_allowed` | INTEGER | no | `1` | none | boolean |
| `last_verified_at` | TEXT | yes | null | none | ISO-8601 |
| `metadata_json` | TEXT | yes | null | none | redacted, size-limited |

Indexes: `workflow_object_provenance(workflow_id)`, `workflow_object_provenance(workspace_id)`, `workflow_object_provenance(object_type, object_name)`.
Lifecycle/status: `created`, `verified`, `modified`, `rolled_back`, `deleted`, `orphaned`.
Rules: rollback/drop checks provenance; objects outside workflow cannot be rolled back unless policy allows; identity includes DB/schema/object type/name.

### `schema_snapshots`

Purpose: store schema snapshots for verification, Text-to-SQL context, and invalidation after mutation.

| Column | SQL Type | Nullable | Default | Key/Index | Constraints |
|---|---|---:|---|---|---|
| `snapshot_id` | TEXT | no | generated | primary | unique snapshot id |
| `workspace_id` | TEXT | yes | null | index | workspace target |
| `database_profile_id` | TEXT | yes | null | index | connected DB target |
| `database_name` | TEXT | no | none | target identity | database context |
| `schema_name` | TEXT | yes | null | target identity | schema context |
| `snapshot_hash` | TEXT | no | none | index | hash of schema_json |
| `schema_json` | TEXT | no | none | none | redacted, size limit required |
| `source` | TEXT | no | none | none | `sandbox`, `connected_database`, `manual_fixture` |
| `created_at` | TEXT | no | app UTC | index | ISO-8601 |
| `expires_at` | TEXT | yes | null | none | ISO-8601 |
| `invalidated_at` | TEXT | yes | null | none | ISO-8601 |
| `invalidation_reason` | TEXT | yes | null | none | mutation/recovery reason |

Indexes: `schema_snapshots(workspace_id)`, `schema_snapshots(database_profile_id)`, `schema_snapshots(snapshot_hash)`, `schema_snapshots(created_at)`.
Rules: no raw secrets; `schema_json` size limit required; mutation invalidates relevant snapshot; identity includes target context.

### `workspace_locks`

Purpose: prevent cleanup, query, schema mutation, and recovery from operating concurrently on one workspace.

| Column | SQL Type | Nullable | Default | Key/Index | Constraints |
|---|---|---:|---|---|---|
| `workspace_id` | TEXT | no | none | primary composite | workspace id |
| `lock_type` | TEXT | no | none | primary composite | `cleanup`, `query`, `mutation`, `recovery` |
| `owner_id` | TEXT | no | none | none | request/worker id |
| `owner_type` | TEXT | no | none | none | `request`, `worker`, `recovery` |
| `acquired_at` | TEXT | no | app UTC | none | ISO-8601 |
| `expires_at` | TEXT | no | none | index | ISO-8601 |
| `heartbeat_at` | TEXT | yes | null | none | ISO-8601 |
| `lock_status` | TEXT | no | `active` | index | enum below |
| `metadata_json` | TEXT | yes | null | none | redacted, size-limited |

Primary/unique rule: `(workspace_id, lock_type)`.
Status: `active`, `released`, `expired`, `force_released`, `error`.
Rules: acquisition must be atomic; expired lock may be reclaimed by policy; cleanup cannot run while mutation/query lock is active if policy forbids; recovery/ownership transfer checks locks.

## 5. Confirmation Challenge Persistence Option

Option A: in-memory single-worker MVP. Option B: runtime SQLite-backed state. User decision required before multi-worker deployment.

Draft only; persistence option not selected. Draft persistent table: `confirmation_challenges` is NOT selected for implementation until user decision.

| Column | SQL Type | Nullable | Default | Key/Index | Constraints |
|---|---|---:|---|---|---|
| `check_id` | TEXT | no | none | primary | query check id |
| `authorization_id` | TEXT | yes | null | unique | current reservation id |
| `code_hash` | TEXT | no | none | none | never plaintext |
| `sql_hash` | TEXT | no | none | index | SQL/check hash |
| `target` | TEXT | no | none | index | execution target |
| `status` | TEXT | no | `active` | index | `active`, `reserved`, `consumed`, `expired`, `cancelled`, `invalidated` |
| `created_at` | TEXT | no | app UTC | none | ISO-8601 |
| `expires_at` | TEXT | no | none | index | ISO-8601 |
| `reserved_at` | TEXT | yes | null | none | ISO-8601 |
| `reservation_expires_at` | TEXT | yes | null | none | ISO-8601 |
| `reserved_by` | TEXT | yes | null | none | request/worker id |
| `consumed_at` | TEXT | yes | null | none | ISO-8601 |
| `cancelled_at` | TEXT | yes | null | none | ISO-8601 |
| `attempt_count` | INTEGER | no | `0` | none | non-negative |

`validate_and_reserve` must atomically transition `active` to `reserved`.

## 6. Audit DB Schema

DB path: `Data/safy_audit.db`. Historical foundation schema version: `1`. Final refined target schema version: `2`.

### `audit_log`

| Field | SQL Type | Nullable | Default | Index | Requirement |
|---|---|---:|---|---|---|
| `audit_id` | TEXT | no | generated UUID | primary | unique event id |
| `timestamp` | TEXT | no | app UTC | yes | ISO-8601 |
| `chat_id` | TEXT | yes | null | yes | chat context |
| `workflow_id` | TEXT | yes | null | yes | workflow context |
| `workspace_id` | TEXT | yes | null | no | workspace context |
| `endpoint` | TEXT | yes | null | no | API endpoint |
| `action` | TEXT | yes | null | yes | action name |
| `execution_target` | TEXT | yes | null | no | `sandbox`, `connected_database`, `none` |
| `database_profile_id` | TEXT | yes | null | no | selected DB profile id |
| `risk_level` | TEXT | yes | null | yes | `low`, `medium`, `high`, `unknown` |
| `statement_type` | TEXT | yes | null | no | `select`, `ddl`, `dml`, `dangerous`, `unknown` |
| `statement_hash` | TEXT | yes | null | no | hash of raw statement |
| `redacted_sql` | TEXT | yes | null | no | redacted statement only |
| `raw_sql_stored` | INTEGER | no | `0` | no | default false |
| `confirmation_required` | INTEGER | no | `0` | no | boolean |
| `confirmation_status` | TEXT | yes | null | no | confirmation lifecycle status |
| `audit_status` | TEXT | yes | null | no | `prewrite_success`, `postwrite_success`, `failed` |
| `audit_result_update_status` | TEXT | no | `not_required` | no | repair status family |
| `audit_repair_required` | INTEGER | no | `0` | no | boolean |
| `audit_repair_status` | TEXT | no | `not_required` | no | `not_required`, `pending`, `retrying`, `repaired`, `failed_permanent` |
| `audit_repair_attempt_count` | INTEGER | no | `0` | no | non-negative |
| `last_repair_error` | TEXT | yes | null | no | redacted error |
| `last_repair_at` | TEXT | yes | null | no | ISO-8601 |
| `error_code` | TEXT | yes | null | no | stable error code |
| `metadata_json` | TEXT | yes | null | no | redacted JSON, max recommended 16 KB |

Indexes: `audit_log(timestamp)`, `audit_log(chat_id)`, `audit_log(workflow_id)`, `audit_log(risk_level)`, `audit_log(action)`.
Audit defaults: `mask_sql_literals: true`, `store_statement_hash: true`, `store_redacted_sql: true`, `store_raw_sql: false`.

## 7. Migration Rules

- Historical implementation foundation uses runtime schema `1` and audit schema `1`.
- Final refined Phase 2 documentation target uses runtime schema `2` and audit schema `2`.
- Planning/development local runtime and audit DB files may be destructively rebuilt.
- Release v1.0.0 requires formal runtime/audit migrations from `1` to `2`; destructive rebuild is not an acceptable production-only mechanism.
- During development destructive rebuild, existing local `Data/safy_runtime.db` and `Data/safy_audit.db` may be deleted/recreated only with explicit operator/developer action and only outside production.
- DB version lower than required application version returns `MIGRATION_REQUIRED`.
- DB version higher than maximum supported application version returns `SCHEMA_VERSION_UNSUPPORTED`.
- Migration execution error returns `MIGRATION_FAILED`.
- Rollback error returns `MIGRATION_ROLLBACK_FAILED`.
- Initialization failure returns `DATABASE_INITIALIZATION_FAILED`.
- Migrations apply in order and should run in SQLite transactions.
- Destructive migrations require backup or explicit operator approval.
