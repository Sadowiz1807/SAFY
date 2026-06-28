# Profile Runtime Contract

## 1. Authority and storage

The active profile contracts are implemented by:

- `Apps/Api/safy_api/schemas.py`
- `LLM/provider_profiles.py`
- `LLM/provider_store.py`
- `DataStore/profile_store.py`
- `Gateway/db_drivers/provider_profiles.py`

Canonical stores:

| Profile kind | Store |
|---|---|
| Local login user | `Data/User/user_profiles.json` |
| Model provider | `Data/model_profiles/model_profiles.json` |
| Database provider | `Data/Database_management/database_profiles.json` |
| Legacy model compatibility only | `Data/safy_profiles.json` |

All stores are runtime data and are excluded from clean handoff packages. Example files may be shipped only with non-secret placeholder values.

## 2. Local user profile

A persisted local user profile contains metadata only:

- `profile_id`
- `profile_type = user`
- `display_name`
- `username`
- `password_env`
- `active`
- `created_at`
- `updated_at`

The login password value is stored in `.env` under `SAFY_LOGIN_PASSWORD` by default. The JSON profile never stores the raw password.

## 3. Model-provider profile

Canonical persisted fields are:

- `profile_id`
- `display_name`
- `provider_type`
- `base_url`
- `model`
- `api_key_env` or `null`
- `auth_mode`: `local_no_auth` or `env_api_key`
- `is_active`
- `capabilities`
- `context_window`
- `created_at`
- `updated_at`

Rules:

- `local_no_auth` is accepted only for a local URL.
- Remote providers require an uppercase environment-variable reference.
- Raw API keys are accepted only as transient API request input and are moved to `.env` before profile persistence.
- Public API responses redact the environment reference and never return the raw key.

## 4. Database profile

`DatabaseProfilePayload` accepts a unified transient request for:

- `postgresql`
- `supabase_rpc`
- `mysql`
- `sqlite`
- `sqlserver`
- `oracle`

The normalization layer persists the canonical connection identity and capability metadata, including as applicable:

- profile identity and display fields;
- `database_type`, `provider`, `driver`, `dbms`, `engine`;
- `connection_kind`, `execution_transport`;
- structured host, port, instance, database, schema, SQLite path, Oracle service/SID;
- authentication mode and trusted-connection flags;
- username;
- environment secret references;
- TLS/driver/RPC settings;
- query access mode and read-only metadata;
- active state, activation/context generations and timestamps;
- cached connection-test status.

Structured fields are authoritative. `base_url` inference exists only for compatibility and to fill missing structured values.

### 4.1 Secret handling

The API may receive `api_key`, `password`, or `raw_secret` transiently. Before normalization or persistence, the API writes the value to `.env` and replaces it with one of:

- `api_key_env`
- `password_env`
- `secret_env`

Persisted profiles must not contain raw secret values. The legacy boolean `has_raw_secret` may be retained as a configured-secret status flag for UI compatibility; it never contains the secret itself. API responses are redacted and contain only configuration status/masks.

### 4.2 Access modes

`user_query_access_mode` is one of:

- `credential_permissions`
- `read_only`
- `disabled`

The agent's direct connected-database route remains read-only regardless of credential capability. User-controlled write or non-destructive DDL uses the Check Safety → sandbox validation → explicit Execute workflow.

### 4.3 Provider/driver distinction

- Supabase HTTPS/API-key profiles use `supabase_rpc` and PostgREST/RPC transport.
- A native PostgreSQL connection to a Supabase project uses the PostgreSQL driver.
- The two routes must not be inferred solely from the word “Supabase”.

## 5. Activation contract

Database activation:

1. validates that the target profile exists;
2. atomically writes exactly one active database profile;
3. increments activation/context generation on the target;
4. invalidates session, schema and query-check bindings that depend on the previous active profile;
5. returns only a redacted public profile.

Model activation similarly keeps one active model profile in the canonical model-provider store.

## 6. Connection testing

- `GET /database-profiles/active` returns metadata and cached test status only; it performs no hidden network I/O.
- Live connection checks occur only through explicit test endpoints.
- Test requests may use transient raw credentials, but the raw values are not persisted in profile JSON or returned to the caller.

## 7. Public response contract

Responses may expose:

```json
{
  "profile_id": "local_postgres",
  "password_env": "***ENV_REF***",
  "secret_configured": true,
  "secret_mask": "****"
}
```

Responses must not contain raw API keys, passwords, tokens, connection strings with embedded credentials, or resolved environment values.
