# SAFY Backend Mock/Legacy Runtime Cleanup Fix Report

## Scope

This pass fixes the highest-risk backend mock/fake/legacy runtime surfaces identified in `MOCK_LEGACY_AUDIT_REPORT.md`.

This pass does **not** rename frontend `mock-ui.js`, does **not** change chat UI, and does **not** change the database Save/Test workflow that already passed. It only patches backend runtime paths where mock/fake/fallback behavior could affect real execution.

## Files modified

- `Apps/Api/safy_api/main.py`
- `Apps/Api/safy_api/schemas.py`
- `Gateway/query_orchestrator.py`
- `Gateway/connected_db_adapter.py`
- `Gateway/sandbox_adapter.py`

## 1. `SAFY_DEV_MODE` hard-gated

### Before

`SAFY_DEV_MODE=1` directly enabled mock runtime behavior inside query orchestration.

### After

`SAFY_DEV_MODE=1` alone no longer enables mock runtime behavior.

Mock runtime now requires an explicit second flag:

```text
SAFY_ALLOW_MOCK_RUNTIME=1
```

If `SAFY_DEV_MODE=1` is set without `SAFY_ALLOW_MOCK_RUNTIME=1`, the backend emits a runtime warning and keeps mock runtime disabled.

## 2. Removed `sandbox_mock` rewrite from `/query/check`

### Before

`/query/check` could rewrite `credential_permissions` to `sandbox_mock` when mock dev mode was enabled.

### After

`/query/check` no longer rewrites permission mode into `sandbox_mock`.

Also, if the request targets `connected_database` and has a valid `database_profile_id`, the backend treats it as real DB check mode automatically.

## 3. Query IDs and SQL hashes no longer use mock prefixes

### Before

- `hash_mock_...`
- `check_mock_...`

### After

- `hash_...`
- `check_...`

This removes mock-era naming from runtime safety checks.

## 4. Query check response no longer marks runtime checks as mock-only

### Before

Non-real-db checks returned:

```json
{
  "mock_only": true,
  "no_real_execution": true,
  "phase3_check": true
}
```

### After

Runtime safety checks now use neutral metadata:

```json
{
  "execution_available": true,
  "runtime_check": true
}
```

## 5. Removed mock sandbox adapter execution fallback

### Before

If execution reached the fallback adapter path, `SandboxAdapter.execute()` could return a successful-looking mock result.

### After

If a checked target has no real runtime adapter available, execution fails closed with:

```json
{
  "code": "RUNTIME_EXECUTION_UNAVAILABLE"
}
```

No successful mock execution result is returned.

## 6. Sandbox test adapter disabled by default

### Before

`Gateway/sandbox_adapter.py` returned:

```text
exec_mock_phase3_001
mock_success
mock: true
no_real_execution: true
```

### After

The adapter is disabled by default.

It can only run if explicitly enabled for test/dev:

```text
SAFY_ALLOW_MOCK_SANDBOX_ADAPTER=1
```

When enabled, it returns clearly labeled test-fixture data, not production-looking success.

## 7. Fake database adapter disabled by default

### Before

`dbms == "fake"` returned `FakeConnectedDBAdapter`.

### After

`dbms == "fake"` is blocked unless explicitly enabled:

```text
SAFY_ALLOW_FAKE_DB_ADAPTER=1
```

Without that flag, backend returns:

```text
FAKE_DB_ADAPTER_DISABLED
```

## 8. `fake` driver removed from public database schema

`Apps/Api/safy_api/schemas.py` no longer allows `driver="fake"` in `DatabaseMockSaveRequest`.

## 9. `/profiles/model/test` no longer returns `mock_success`

### Before

If no active model profile existed, `/profiles/model/test` returned:

```json
{
  "status": "mock_success",
  "provider_called": false
}
```

### After

It returns a normal error envelope from `ModelProfileError`, such as `PROFILE_NOT_FOUND`.

## 10. Canonical model store now takes priority

### Before

`_canonical_model_profiles()` preferred legacy `profiles_json` model profiles if any existed.

### After

Canonical `MODEL_PROVIDER_STORE` is preferred. Legacy model profiles are used only as a compatibility fallback when the canonical provider store is empty.

This prevents stale legacy profiles from shadowing active LM Studio profiles.

## 11. `/sandbox/health` no longer reports `phase1_mock`

### Before

```json
{
  "mode": "phase1_mock",
  "real_sandbox_execution": false
}
```

### After

The endpoint reports real runtime availability from `SANDBOX_MANAGER`:

```json
{
  "mode": "runtime",
  "real_sandbox_execution": true,
  "sandbox_count": 0,
  "ready_count": 0,
  "status": "available"
}
```

If sandbox manager errors, it returns `healthy:false` and a real unavailable status.

## 12. `/profiles` now uses canonical stores

`/profiles` now returns canonical model/database profile data instead of reading legacy `profiles_json` directly.

## Explicitly not changed

- Frontend runtime filename `mock-ui.js` was not renamed in this backend pass.
- Deprecated route `/legacy/agent/chat` was not removed because it already returns an explicit deprecation error.
- Raw database secrets remain allowed for local/UAT as previously chosen by the user.
- Database Save/Test real connection workflow was not changed.
- Chat command UI was not changed.
- `/Execute` query-draft workflow was not changed.

## Verification

Syntax check passed for:

```text
main.py
schemas.py
query_orchestrator.py
connected_db_adapter.py
sandbox_adapter.py
provider_store.py
provider_profiles.py
provider_health.py
profile_store.py
```

Command used:

```bash
python -m py_compile main.py schemas.py query_orchestrator.py connected_db_adapter.py sandbox_adapter.py provider_store.py provider_profiles.py provider_health.py profile_store.py
```

## Remaining follow-up work

Recommended next pass:

1. Rename frontend `mock-ui.js` to `safy-ui.js` or `app-ui.js`, while keeping `/mock-ui.js` as a temporary alias if needed.
2. Update UI labels so fake/mock profile states do not appear as normal runtime states.
3. Move `/profiles/*/mock-save` aliases behind explicit deprecation warnings or remove after migration.
4. Add integration tests for:
   - active LM Studio profile
   - `/profiles/model/test` no-active error
   - `/query/check` real DB mode
   - fake DB blocked unless explicit env flag is enabled

## Final status

SAFY_BACKEND_MOCK_LEGACY_RUNTIME_CLEANUP_FIXED
