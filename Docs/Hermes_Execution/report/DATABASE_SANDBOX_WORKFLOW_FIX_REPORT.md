# SAFY Database + Sandbox Workflow Fix Report

## Final status

`SAFY_DATABASE_CONNECTION_WORKFLOW_FIXED_WITH_SUPABASE_REST_SANDBOX_NOT_READY`

This pass fixes the pointed database profile / sandbox workflow issue without broad refactoring. Supabase REST real connection is tested directly, database profile store usage is unified for the current `/database-profiles*` workflow, and sandbox preparation no longer turns a successful real connection into a false database failure.

## Files modified

1. `Apps/Api/safy_api/main.py`
2. `DataStore/profile_store.py`
3. `Apps/Web/mock-ui.js`

No changes were made to model provider storage, LLM profile activation, `/Execute` safety logic, or backend chat runtime.

## What was fixed

### 1. Canonical database profile store

Added one canonical database profile store path in `main.py`:

```python
DB_PROFILE_STORE_PATH = CONFIG.data_path("database_profiles")

def _database_store():
    return database_profile_store(DB_PROFILE_STORE_PATH)
```

The current database routes now use this canonical store instead of mixing `profiles_json` and `database_profiles`:

- `GET /database-profiles`
- `GET /database-profiles/active`
- `POST /database-profiles`
- `POST /database-profiles/{profile_id}/activate`
- `POST /database-profiles/{profile_id}/test`
- `POST /database-profiles/{profile_id}/ensure-sandbox`
- `/profiles/database/{database_profile_id}/status`
- `/profiles/database/{database_profile_id}/schema`
- database profile lookup in `target=auto` and `/query/check`

This directly addresses the `PROFILE_NOT_FOUND: validation_db` issue where one route saved to the canonical store while `ensure_sandbox` looked in the legacy store.

### 2. Supabase REST real connection test

Added backend real connection testing for Supabase REST profiles.

Detection rule:

```text
base_url contains supabase.co and /rest/v1
```

Test behavior:

- Uses HTTP GET to the Supabase REST Base URL.
- Sends headers:
  - `apikey: <raw_secret>`
  - `Authorization: Bearer <raw_secret>`
- Treats HTTP 2xx as connected.
- Does not log or echo the raw API key.

This prevents Supabase REST from being incorrectly tested as a PostgreSQL socket connection.

### 3. Save Database now tests before save

`POST /database-profiles` now follows this workflow:

```text
normalize payload without writing
→ test real connection
→ if connection fails: return error and do not save
→ if connection passes: save profile
→ activate/deactivate profile state through canonical store
→ prepare sandbox after connection success
→ return connection_status and sandbox_status separately
```

### 4. Test Connection now tests before sandbox

`POST /database-profiles/{profile_id}/test` now follows this workflow:

```text
load profile from canonical store
→ test real connection
→ if connection fails: return database error
→ if connection passes: prepare sandbox
→ return connection_status + sandbox_status
```

Sandbox preparation no longer decides whether the real database connection is valid.

### 5. Sandbox result is separated from connection result

Successful real connection returns:

```json
{
  "connection_status": "connected",
  "sandbox_status": "ready | not_ready | failed",
  "sandbox_error": null
}
```

For Supabase REST, because the current codebase does not implement restore/import/schema cache hydration from REST metadata, the backend returns:

```json
{
  "connection_status": "connected",
  "sandbox_status": "not_ready",
  "sandbox_error": {
    "code": "SUPABASE_REST_SCHEMA_CACHE_NOT_IMPLEMENTED"
  }
}
```

This is intentional. It does not fake sandbox readiness.

### 6. Frontend Save/Test flow fixed

In `Apps/Web/mock-ui.js`:

- Save Database no longer calls `activate` and `ensureActiveSandbox` separately after backend save.
- Test Connection no longer calls `ensureActiveSandbox` separately after backend test.
- UI uses backend `connection_status` and `sandbox_status` from the database workflow response.
- Database can show `Real connected` even if sandbox is `not_ready`.
- Sandbox status is surfaced as a toast rather than turning the database card into a false connection failure.

### 7. Removed unintended chat endpoint fallback

The unintended `/agent/chat` → `/chat` fallback introduced earlier was removed. Chat uses canonical `/agent/chat` directly again. This prevents accidental fallback into legacy/mock chat routes.

## Raw secret handling

`DataStore/profile_store.py` now marks Supabase REST profiles with:

```text
connection_kind = supabase_rest
```

For Supabase REST profiles, blank username is normalized to:

```text
username = supabase_rest
```

This prevents a REST API profile from failing database-profile validation because SQL-style username is irrelevant.

Raw secret behavior from the previous pass remains intact:

- `raw_secret` / `api_key` accepted for database profiles.
- `password_env` is kept empty when `password_mode = raw_secret`.
- Raw secret is not returned to the browser in public profile payloads.

## Verification run

Commands executed in the sandbox package directory:

```bash
python -m py_compile main.py schemas.py profile_store.py sandbox_manager.py schema_cache.py
node --check mock-ui.js
```

Result:

```text
PASS
```

## Remaining limitation

Supabase REST sandbox restore/import/schema cache is not implemented in the current codebase. This pass does not fake it.

Current behavior for Supabase REST after this fix:

```text
Database: Real connected
Sandbox: not_ready
Reason: SUPABASE_REST_SCHEMA_CACHE_NOT_IMPLEMENTED
```

A future pass should implement one of these explicitly:

1. Supabase REST schema introspection adapter.
2. Supabase metadata/OpenAPI pull into schema cache.
3. Supabase REST → local sandbox hydration pipeline.
4. Direct Postgres connection workflow using Supabase DB password instead of REST key.

## Copy instructions

Copy the fixed files to these locations:

```text
Apps/Api/safy_api/main.py
DataStore/profile_store.py
Apps/Web/mock-ui.js
```

Then restart the backend/frontend and test:

```text
Save Database → should test real Supabase REST connection first.
If connection passes → profile is saved/active and UI shows Real connected.
Sandbox may show not_ready for Supabase REST without causing database failure.
```
