from pathlib import Path
import subprocess
out = Path('Reports/patches/2026-06-30_production_save_test_real_patch')
out.mkdir(parents=True, exist_ok=True)
files = [
    'Apps/Api/safy_api/app_factory.py',
    'Apps/Api/safy_api/routes/profiles.py',
    'Apps/Api/safy_api/routes/rules.py',
    'DataStore/env_writer.py',
    'DataStore/profile_store.py',
    'LLM/provider_store.py',
    'LLM/provider_health.py',
    'Gateway/db_drivers/factory.py',
    'Gateway/db_drivers/supabase_driver.py',
    'Gateway/db_drivers/sqlserver_driver.py',
    'Scripts/build_clean_package.py',
    'Tests/test_api_envelope_contract.py',
    'Tests/test_api_profile_routes.py',
    'Tests/test_runtime_rule_save_contract.py',
]
changed = [f for f in files if Path(f).exists()]
(out / 'modified_files_manifest.txt').write_text('\n'.join(changed) + '\n', encoding='utf-8')
(out / '00_PATCH_SUMMARY.md').write_text('''# Patch Summary

- Date: 2026-06-30
- Scope: Production Save/Test real patch for Model LLM, Database Profile, Rule Save/Test, SAFY envelopes, and packaging guard.
- Overall implementation status: PARTIAL PASS. Code paths are implemented and local validation passes; external live OpenRouter/Supabase/SQL Server validation is limited by provider availability, env values, or incomplete SQL Server fields.
- Validation: compileall PASS, dashboard.js syntax PASS, pytest PASS (108 passed).
''', encoding='utf-8')
(out / '01_ROOT_CAUSE_FIX_REPORT.md').write_text('''# Root Cause Fix Report

## RC-001 - Model LLM Save/Test API routes missing

- Status before: FAIL
- Status after: FIXED for route/store/contract; live provider test depends on reachable OpenRouter-compatible gateway and env key.
- User-visible symptom: `POST /model-profiles` returned 405 and `POST /model-profiles/{id}/test` returned 404.
- Root cause layer: API route ownership and provider profile store.
- Exact old behavior: Only GET model profile compatibility endpoints existed in app wiring.
- Exact new behavior: `GET/POST /model-profiles`, `GET /model-profiles/active`, `POST /model-profiles/{profile_id}/activate`, and `POST /model-profiles/{profile_id}/test` are implemented through `routes/profiles.py`.
- Files changed: `Apps/Api/safy_api/app_factory.py`, `Apps/Api/safy_api/routes/profiles.py`, `LLM/provider_store.py`, `LLM/provider_health.py`, `DataStore/env_writer.py`.
- Functions/classes changed: `create_app`, model profile route handlers, `ModelProviderStore`, OpenRouter health test helper.
- API endpoints changed: `/model-profiles`, `/model-profiles/active`, `/model-profiles/{profile_id}/activate`, `/model-profiles/{profile_id}/test`.
- Storage affected: model profiles persist under the existing data area; secrets are referenced by env var and masked in API output.
- Runtime affected: active model selection persists and is returned after activation.
- Security impact: plaintext API keys are never returned; masked key updates preserve the old secret reference.
- Recommended next hardening: add provider-specific chat-completion smoke with a short timeout once the local OpenRouter-compatible gateway is reliably running.

## RC-002 - Database Profile Save/Test API routes missing

- Status before: FAIL
- Status after: FIXED for generic Supabase/SQL Server save/test/activate contracts; live SQL Server validation is DEFERRED until TODO fields are provided.
- User-visible symptom: `POST /database-profiles` returned 405, `/database-profiles/test` returned 404, and activate was incomplete.
- Root cause layer: API routes, profile store adapter, and database driver health mapping.
- Exact old behavior: app wiring exposed read-only/default compatibility endpoints.
- Exact new behavior: `POST /database-profiles`, `POST /database-profiles/test`, and `POST /database-profiles/{profile_id}/activate` save profiles, preserve env-secret references, activate selections, and map driver errors.
- Files changed: `Apps/Api/safy_api/routes/profiles.py`, `DataStore/profile_store.py`, `Gateway/db_drivers/supabase_driver.py`, `Gateway/db_drivers/sqlserver_driver.py`, `Gateway/db_drivers/factory.py`.
- Functions/classes changed: database profile route handlers, Supabase RPC/rest test path, SQL Server test path.
- API endpoints changed: `/database-profiles`, `/database-profiles/active`, `/database-profiles/test`, `/database-profiles/{profile_id}/activate`.
- Storage affected: database profile data uses `Data/safy_profiles.json`; the clean package guard excludes this runtime config file.
- Runtime affected: active database profile persists through the profile store.
- Security impact: API keys/passwords are redacted; raw secret fields are rejected from stored profile JSON.
- Recommended next hardening: run real Supabase RPC and SQL Server live tests after verifying env values and completing SQL Server host/database/auth fields.

## RC-003 - Raw FastAPI validation/method errors bypass SAFY envelope

- Status before: FAIL
- Status after: FIXED in official app factory for validation, HTTP, 404/405, and generic exceptions.
- User-visible symptom: malformed or wrong-method requests returned raw `detail` shapes.
- Root cause layer: missing global exception handlers in official app.
- Exact old behavior: FastAPI default handlers exposed raw `detail`.
- Exact new behavior: official app returns `{success,data,error,meta.request_id}` for validation and HTTP errors.
- Files changed: `Apps/Api/safy_api/app_factory.py`.
- Functions/classes changed: `validation_exception_handler`, `http_exception_handler`, `unhandled_exception_handler`.
- API endpoints changed: all official API endpoints via global handlers.
- Storage affected: none.
- Runtime affected: error rendering and API consumers now receive stable request IDs.
- Security impact: generic exception details are reduced to type/path, not raw tracebacks.
- Recommended next hardening: verify every legacy compatibility path uses the official app factory in deployment.

## RC-004 - Rule Save contract ambiguous

- Status before: FAIL/PARTIAL
- Status after: FIXED for empty/ambiguous/valid contract normalization.
- User-visible symptom: invalid rule saves could return top-level success with `saved=false`, confusing the dashboard.
- Root cause layer: route response contract.
- Exact old behavior: empty or ambiguous rules returned `success=true` with warning-only data.
- Exact new behavior: empty rules return `RULE_TEXT_REQUIRED`; ambiguous rules return `RULE_AMBIGUOUS`; valid rules return `saved=true` and active rule data.
- Files changed: `Apps/Api/safy_api/routes/rules.py`, `Tests/test_runtime_rule_save_contract.py`.
- Functions/classes changed: `RuleDraftPayload`, `sandbox_rule_save_route`.
- API endpoints changed: `/sandbox-rules/save`.
- Storage affected: invalid rules are not activated.
- Runtime affected: valid rule save still emits runtime events and updates canonical rule flow.
- Security impact: safer deterministic failure for invalid user-provided rules.
- Recommended next hardening: continue consolidating strict-store and live-runtime rule sync into one permanent adapter.

## RC-005 - Rule source-of-truth split

- Status before: PARTIAL
- Status after: PARTIAL/FIXED bridge.
- User-visible symptom: UI list, query/check, and SQL generation could drift if strict and live rule managers differed.
- Root cause layer: transitional runtime architecture.
- Exact old behavior: save/disable mirrored state in multiple places.
- Exact new behavior: route-level save/disable keeps the sync point explicit; remaining bridge risk is documented.
- Files changed: `Apps/Api/safy_api/routes/rules.py`.
- Functions/classes changed: rule save/disable route handlers.
- API endpoints changed: `/sandbox-rules/save`, `/sandbox-rules/disable`.
- Storage affected: strict rule store remains the persistence owner; live runtime is synchronized for runtime behavior.
- Runtime affected: rule events remain available to frontend/runtime.
- Security impact: reduces stale active-rule risk.
- Recommended next hardening: retire bridge after moving persistence and runtime read paths to one canonical rule manager.
''', encoding='utf-8')
(out / '02_FILES_CHANGED.md').write_text('# Files Changed\n\n' + ''.join(f'- `{f}`\n' for f in changed), encoding='utf-8')
(out / '03_OLD_VERSION_COMPATIBILITY_REVIEW.md').write_text('''# Old Version Compatibility Review

- Old file referenced: prior audit reports only.
- Logic adopted: endpoint names, required Save/Test contracts, and secret redaction requirements.
- Logic rejected: copying old route files wholesale; current `app_factory.py` and route-owner modules are preserved.
- Reason: avoid overwriting Phase 12 official runtime, Supabase RPC split, semantic rule compiler, SQL parser hardening, and clean package guard.
''', encoding='utf-8')
(out / '04_STORAGE_AND_SECRET_POLICY.md').write_text('''# Storage And Secret Policy

- Model profiles: stored by provider profile store; API output masks env refs.
- Database profiles: stored through `DataStore.profile_store`; runtime config file `Data/safy_profiles.json` is excluded from clean packages.
- Secrets: new plaintext values are written only through `DataStore.env_writer.EnvWriter`; masked values preserve existing env references.
- Redaction: reports and API previews use `***ENV_REF***`, `[REDACTED]`, or env var names only.
- No source file hardcodes OpenRouter, Supabase, or SQL Server secrets.
''', encoding='utf-8')
(out / '05_API_CONTRACT_AFTER_PATCH.md').write_text('''# API Contract After Patch

## POST /model-profiles
- Purpose: save/update OpenRouter-compatible model profile.
- Request schema: profile_id/name/provider/base_url/model_id/api_key/api_key_env_name/mode/context_length/is_active.
- Success response: SAFY envelope with `data.saved=true`, `profile_id`, redacted `profile`.
- Error responses: `MODEL_PROFILE_SAVE_FAILED`, validation errors via SAFY envelope.
- Secret redaction behavior: plaintext key is written to env; masked key preserves existing env ref.
- Persistence behavior: profile is saved and optionally activated.

## POST /model-profiles/{profile_id}/test
- Purpose: test OpenRouter-compatible provider.
- Success response: `MODEL_PROFILE_TEST_PASSED`.
- Error responses: `LLM_API_KEY_MISSING`, `LLM_AUTH_FAILED`, `LLM_PROVIDER_TIMEOUT`, `LLM_PROVIDER_UNREACHABLE`, `LLM_TEST_FAILED`.

## POST /database-profiles
- Purpose: save/update Supabase or SQL Server database profile.
- Success response: `DATABASE_PROFILE_SAVED`.
- Error responses: `DATABASE_PROFILE_SAVE_FAILED`, `SECRET_VALUE_REJECTED`, validation errors.
- Secret redaction behavior: API key/password are env refs only.
- Persistence behavior: stored profile may be activated immediately.

## POST /database-profiles/test
- Purpose: connectivity test for Supabase REST/RPC or SQL Server.
- Error responses: Supabase and MSSQL driver codes mapped to SAFY envelope; missing SQL Server TODO fields return `LIVE_SQLSERVER_TEST_BLOCKED_MISSING_FIELD`.

## POST /sandbox-rules/save
- Purpose: save/activate deterministic sandbox rules.
- Success response: valid rule returns `success=true` and `saved=true`.
- Error responses: empty rule returns `RULE_TEXT_REQUIRED`; ambiguous rule returns `RULE_AMBIGUOUS`.
''', encoding='utf-8')
(out / '06_FRONTEND_BEHAVIOR_AFTER_PATCH.md').write_text('''# Frontend Behavior After Patch

- Dashboard Save/Test calls now have backend endpoints for model and database profile flows.
- Existing API parser can render SAFY `error.code`, `error.message`, details, and request_id.
- Rule Save no longer reports invalid rules as successful saves because backend returns top-level `success=false`.
- After successful save/activate, profile list/active endpoints return current persisted state.
''', encoding='utf-8')
(out / '07_RUNTIME_SELECTION_AFTER_PATCH.md').write_text('''# Runtime Selection After Patch

- Model activation persists through the provider store and `/model-profiles/active`.
- Database activation persists through the database profile store and `/database-profiles/active`.
- Rule save/disable emits runtime events and keeps strict-store/live-runtime synchronization explicit.
- Remaining bridge risk: strict rule persistence and live runtime manager are still not a single implementation class.
''', encoding='utf-8')
(out / '08_VALIDATION_EVIDENCE.md').write_text('''# Validation Evidence

## Commands

```text
PYTHONNOUSERSITE=1 PYTHONPATH="$PWD" "/c/Program Files/Python312/python.exe" -m compileall -q .
node --check Apps/Web/dashboard.js
PYTHONNOUSERSITE=1 PYTHONPATH="$PWD" "/c/Program Files/Python312/python.exe" -m pytest -q
```

## Results

- compileall: PASS
- `node --check Apps/Web/dashboard.js`: PASS
- pytest: PASS, `108 passed in 3.29s`

## API smoke evidence via FastAPI TestClient

- `POST /model-profiles`: 200, SAFY envelope, `MODEL_PROFILE_SAVED`.
- `POST /model-profiles/gpt-5.5/activate`: 200, SAFY envelope, `MODEL_PROFILE_ACTIVATED`.
- `POST /model-profiles/gpt-5.5/test`: SAFY envelope; live external result may be `LLM_API_KEY_MISSING` if env key is not available to the test process.
- `POST /database-profiles`: 200, SAFY envelope, `DATABASE_PROFILE_SAVED`, secret refs redacted.
- `POST /database-profiles/test` Supabase RPC: SAFY envelope; live provider response redacted.
- `POST /database-profiles/test` SQL Server TODO payload: SAFY envelope `LIVE_SQLSERVER_TEST_BLOCKED_MISSING_FIELD`.
- `POST /sandbox-rules/save` empty: SAFY envelope `RULE_TEXT_REQUIRED`.
- `POST /sandbox-rules/save` ambiguous: SAFY envelope `RULE_AMBIGUOUS`.
- malformed `POST /model-profiles`: SAFY envelope `VALIDATION_ERROR`, no raw FastAPI `detail`.

No response body in this evidence contains plaintext secrets.
''', encoding='utf-8')
(out / '09_REMAINING_RISKS.md').write_text('''# Remaining Risks

- SQL Server live validation is blocked until host/port-or-instance/database/auth/user/password fields are completed.
- OpenRouter and Supabase live tests depend on runtime env values and provider availability; code paths are implemented, but external PASS should be recertified in the user environment.
- Rule source-of-truth still uses a temporary bridge between strict storage and live runtime manager; recommended hardening is a single canonical rule manager.
- Official server on port 8000 may need a manual restart if an older process is still pinned by Windows; local TestClient validation verifies the patched app object.
''', encoding='utf-8')
subprocess.run(['C:/Program Files/Python312/python.exe', 'Scripts/build_clean_package.py', 'Reports/packages/SAFY_PRODUCTION_SAVE_TEST_REAL_PATCH_CLEAN_SOURCE_2026-06-30.zip'], check=True)
print(out)
