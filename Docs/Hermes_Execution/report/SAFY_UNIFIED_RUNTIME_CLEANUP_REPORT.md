# SAFY Unified Runtime Cleanup Report

## Scope

Applied the requested unification pass to the uploaded `SAFY(5).zip`.

This pass:

- removed saved database/runtime state,
- synchronized the project to `.env` and removed `.env.example`,
- renamed phase/mock-named files that were still required,
- removed historical phase execution documents/reports,
- fixed soft-deleted sandbox recreation,
- added duplicate endpoint identity checking during Save Database,
- changed HTML topbar defaults from static status text to dynamic loading state,
- rechecked project syntax/import consistency after cleanup.

## Database/runtime data removal

Reset or removed:

- `.env` was rewritten with only safe local defaults.
- `.env.example` was removed.
- `Data/Database_management/database_profiles.json` was reset to an empty profile list.
- `Data/safy_profiles.json` was reset to an empty profile list.
- `Data/safy_profiles.local.json` was removed.
- `Data/sandboxes/` was cleared.
- `Data/secrets/` was cleared.
- `Data/SchemaGraph/` was cleared.
- `Data/sessions/` was cleared.
- `Data/safy_audit.db` and `Data/safy_runtime.db` were removed.

No stored database Base URL/API key from the uploaded project is retained in the fixed package.

## .env policy

The project now ships with `.env` only:

```text
SAFY_LOGIN_PASSWORD=123456
SAFY_DEV_MODE=0
SAFY_ALLOW_TEST_RUNTIME=0
```

`.env.example` is removed.

## File/name cleanup

Renamed:

- `Apps/Api/safy_api/mock_store.py` → `Apps/Api/safy_api/runtime_store.py`
- `Providers/mock_provider.py` → `Providers/test_provider.py`
- `Sandbox/mock_sandbox.py` → `Sandbox/test_sandbox.py`
- `Contracts/phase1_api_contract.json` → `Contracts/api_contract.json`
- `MOCK_LEGACY_AUDIT_REPORT.md` → `LEGACY_RUNTIME_AUDIT_REPORT.md`
- `Docker/docker-compose.phase10.yml` → `Docker/docker-compose.test-databases.yml`
- `Docker/docker-compose.phase11.yml` → `Docker/docker-compose.database-services.yml`
- `Docker/phase11/` → `Docker/database-services/`
- `Toolsets/phase4.py` → `Toolsets/runtime_toolsets.py`
- phase-named PowerShell scripts were renamed to runtime/database-service names.

Removed old phase planning/report docs from `Docs/Hermes_Execution/`.

## Save Database sandbox fix

Fixed soft-deleted sandbox lifecycle:

```text
deleted sandbox metadata exists
→ remove stale deleted metadata
→ create replacement sandbox
→ start sandbox
→ return sandbox_recreated
```

Save Database now reports:

- `sandbox_created`
- `sandbox_recreated`
- `sandbox_started`
- `sandbox_already_ready`
- `sandbox_not_ready`
- `sandbox_failed`

## Duplicate endpoint check

Save Database now rejects duplicate endpoint identity, not just duplicate display name.

New error:

```text
DATABASE_ENDPOINT_ALREADY_EXISTS
```

Endpoint keys are normalized by database type:

- Supabase REST: normalized base URL
- PostgreSQL/MySQL/SQL Server/Oracle: driver + host + port + database + username
- SQLite: resolved DB path

Test Connection remains permissive and does not save or reject duplicates.

## Dynamic HTML status

Initial topbar values are now `Loading...`, then JS resolves real runtime state.

Connected DB label is now:

```text
Agent readonly · User sandbox-then-real
```

This removes the misleading static `Real runtime read-only` status.

## Validation performed

Passed:

```bash
python -m py_compile <all project .py files>
node --check Apps/Web/safy-ui.js
python -c "from Gateway.db_drivers import execute_user_sql; from Gateway.query_orchestrator import QueryOrchestrator"
```

## Conflict scan

Runtime source/file scan result:

```text
phase/mock filename conflicts: 0
phase/mock content conflicts: 0
```

## Final status

SAFY_UNIFIED_RUNTIME_CLEANUP_FIXED
