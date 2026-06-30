from pathlib import Path
import csv, json
OUT=Path('Reports/audits/2026-06-29_full_save_test_audit')
EVD=OUT/'evidence'
rows=list(csv.DictReader((OUT/'02_SAVE_TEST_MATRIX.csv').open(encoding='utf-8')))
summary={s:sum(1 for r in rows if r['status']==s) for s in ['PASS','FAIL','PARTIAL','NOT_RUN','BLOCKED']}
summary['total']=len(rows)

def w(name, text):
    (OUT/name).write_text(text.strip()+"\n", encoding='utf-8')

w('01_STATIC_FLOW_MAP.md', r'''
# 01 Static Flow Map — SAFY Save/Test Audit

Scope: Model LLM Save/Test, Database Profile Save/Test, Rule Save/Test. Audit-only; no runtime source patched.

## 1. Model LLM Save/Test flow

- UI file: `Apps/Web/dashboard.html` model profile panel.
- JS handlers: `Apps/Web/dashboard.js`
  - Initial load: `loadProfiles()` around lines 454-458 calls `GET /model-profiles` and `GET /model-profiles/active`.
  - Save handler: `saveModelConfig()` around lines 1921-1925 calls `POST /model-profiles`, then `POST /model-profiles/{profile_id}/activate`.
  - Test handler: `testModelConnection()` around lines 1949-1951 calls `POST /model-profiles/{profile_id}/test`.
- Expected request fields: provider/profile name, provider type OpenRouter, base_url, model_id, mode, secret/api_key or masked api key.
- Current backend route owner: `Apps/Api/safy_api/app_factory.py` only defines:
  - `GET /model-profiles`
  - `GET /model-profiles/active`
- Missing backend handlers:
  - `POST /model-profiles`
  - `POST /model-profiles/{profile_id}/activate`
  - `POST /model-profiles/{profile_id}/test`
- Expected storage: `LLM/provider_store.py` or profile store plus env secret storage.
- Expected provider test: `LLM/provider_health.py::test_profile`, then OpenRouter `/v1/models` or chat completions.
- Response parser/UI render: `apiRequest()` in `Apps/Web/dashboard.js`; errors rendered through normalized error helpers.

## 2. Database Save/Test flow

### Supabase save/test

- UI file: `Apps/Web/dashboard.html` database profile form.
- JS handlers: `Apps/Web/dashboard.js`
  - Initial load: lines 454-458 call `GET /database-profiles` and `GET /database-profiles/active`.
  - Activate selected DB: around line 2429 calls `POST /database-profiles/{profile_id}/activate`.
  - Save DB: around lines 2577 calls `POST /database-profiles`.
  - Test DB: around lines 2597-2598 calls `POST /database-profiles/test`.
- Expected request fields: driver/supabase project URL, key/secret env ref, RPC function, mode REST/RPC/direct PG.
- Current backend route owner: `Apps/Api/safy_api/app_factory.py` only defines:
  - `GET /database-profiles`
  - `GET /database-profiles/active`
  - `POST /database-profiles/{profile_id}/ensure-sandbox`
- Missing backend handlers:
  - `POST /database-profiles`
  - `POST /database-profiles/test`
  - `POST /database-profiles/{profile_id}/activate`
- Expected storage: `DataStore/database_profile_store.py`, `DataStore/env_writer.py`.
- Expected test driver: `Gateway/db_drivers/supabase_rest_driver.py`, with RPC install check returning `SUPABASE_RPC_NOT_INSTALLED` when absent.
- Runtime selected profile flow: `Gateway/query_orchestrator.py`, `Apps/Api/safy_api/routes/query.py` should receive selected `database_profile_id` and not mix it with `sandbox_id`.

### SQL Server save/test

- Same UI/API path as database profiles.
- Expected request fields: host/instance/port/database/auth mode/user/password env/encrypt/trust cert.
- Expected driver: `Gateway/db_drivers/sqlserver_driver.py`.
- Missing official POST save/test/activate routes block runtime verification.

## 3. Rule Save/Test flow

- UI file: `Apps/Web/dashboard.html` lines 507-534 define sandbox rules panel and list.
- JS handlers: `Apps/Web/dashboard.js`
  - Load rules: line 517 calls `GET /sandbox-rules`.
  - Save rule: line 573 calls `POST /sandbox-rules/save`.
  - Validate/test rule: line 616 calls `POST /sandbox-rules/validate`.
  - Activate rule: line 629 calls `POST /sandbox-rules/activate`.
  - Disable rule: line 639 calls `POST /sandbox-rules/disable`.
- Backend owner: `Apps/Api/safy_api/routes/rules.py`.
- Rule compile/test backend:
  - `Runtime/strict_services.py`
  - `Core/rules/semantic_compiler.py`
  - legacy adapter: `Core/sandbox_rule_engine.py`
- SQL structural checker/fail closed entrypoint:
  - `Apps/Api/safy_api/routes/query.py`
  - `Runtime/strict_services.py::check_query`
  - `Core/sql/*` and Gateway adapters.
- Current issue: rules route uses both `Runtime.strict_services.RULE_STORE` and `Runtime.live_runtime.RULE_MANAGER`, creating split rule source-of-truth.
''')

w('03_RESPONSE_CONTRACT_AUDIT.md', r'''
# 03 Response Contract Audit

Expected prompt contract: `{ ok, code, message, details, request_id }` for Save/Test endpoints.

Actual observed patterns:

1. Current SAFY official app usually returns Phase 12 envelope:
   `{ success, data, error, meta: { request_id } }`.
2. Missing routes return raw FastAPI 405 body:
   `{ "detail": "Method Not Allowed" }`.
3. Pydantic validation can return raw FastAPI 422 body:
   `{ "detail": [...] }`.
4. Some rule save warnings return `success=true` with `saved=false` inside data, not top-level `ok=false` / code.

Contract gaps:

- Model Save/Test endpoints are missing and return raw 405.
- Database Save/Test endpoints are missing and return raw 405.
- `/query/check {}` returns raw 422 instead of SAFY envelope.
- Rule ambiguous/empty handling is structured but not normalized to a clear top-level code.

Required baseline fix:

- Add global exception handlers in `app_factory.py` for validation/HTTP/generic exceptions.
- Standardize route helper to optionally emit prompt-required `ok/code/message/details/request_id`, or document and adapt frontend to SAFY `success/data/error/meta` everywhere.
- Add tests for malformed body, missing fields, method not allowed, and provider-specific failures.
''')

w('04_STORAGE_PERSISTENCE_AUDIT.md', r'''
# 04 Storage Persistence Audit

## Model LLM profiles

Status: FAIL / not implemented on official app.

- UI calls save/test/activate endpoints.
- Official backend exposes only read-only hardcoded model profile helpers.
- Persistence to provider store or env secret store was not verified because save endpoint is absent.

## Database profiles

Status: FAIL / not implemented on official app.

- UI calls `POST /database-profiles` and `POST /database-profiles/test`.
- Official backend exposes only hardcoded GET helpers.
- Supabase and SQL Server profile persistence cannot be verified.

## Rules

Status: PARTIAL.

- Rules can be saved through `/sandbox-rules/save`.
- Persistence/restart reload was not verified in audit-only run.
- There are two stores involved: strict services store and Runtime RuleManager mirror.

Recommended persistence tests:

- Save model profile, restart app, verify profile exists and key remains redacted but usable.
- Save Supabase/SQL Server profile, restart app, verify active selection and test route still works.
- Save active rule, restart app, verify query/check still enforces rule.
''')

w('05_RUNTIME_SELECTION_AUDIT.md', r'''
# 05 Runtime Selection Audit

## Model runtime selection

Status: NOT_RUN / blocked by missing save/select/test endpoints.

- `/agent/chat` can run, but selected OpenRouter profile cannot be saved/activated through official API.
- Therefore runtime use of the requested OpenRouter/Openroute profile was not verified.

## Database runtime selection

Status: NOT_RUN / blocked by missing save/select/test endpoints.

- Official profile GET endpoints return hardcoded `db_default` / `Official Runtime DB`.
- Supabase and SQL Server selected profile flows are not verifiable through official Save/Test endpoints.

## Rule runtime selection

Status: PARTIAL.

- `/sandbox-rules/save` can save rules.
- `/query/check` can evaluate SQL safety.
- Split ownership between strict_services and Runtime RuleManager creates risk that chat generation and rules list diverge.

Recommended runtime selection tests:

- Save/select OpenRouter profile, call `/agent/chat`, assert provider/model id in evidence.
- Save/select Supabase profile, call check/execute path, assert driver and RPC/direct PG path.
- Save/select SQL Server profile, call check/execute path, assert SQL Server driver path.
- Save/disable rule, assert generation constraints update immediately and after restart.
''')

# Root causes from matrix.
fails=[r for r in rows if r['status'] in ('FAIL','PARTIAL','BLOCKED')]
root = ['# 06 Root Cause Report\n']
rc_defs=[
('RC-001','Model profile Save/Test API routes missing','High','Model LLM','Save/Test','FAIL','Dashboard Save/Test cannot work for OpenRouter profiles.','POST /model-profiles and POST /model-profiles/{id}/test should persist/test OpenRouter profile.','POST routes return 405 Method Not Allowed.','API_ROUTE_MISSING','Apps/Api/safy_api/app_factory.py','create_app inline model profile helpers','/model-profiles, /model-profiles/{id}/test','evidence/LLM-SAVE-001.json, evidence/LLM-TEST-001.json','Official app only implements GET model helpers, while dashboard JS calls POST save/activate/test.','Implement route-owner model profile routes backed by LLM provider store and provider_health; preserve masked key on update.','Medium','Apps/Api/safy_api/routes/profiles.py; LLM/provider_store.py; LLM/provider_health.py','Tests/test_model_profile_save_contract.py; Tests/test_model_profile_test_contract.py'),
('RC-002','Database profile Save/Test API routes missing','High','Database Supabase / SQL Server','Save/Test','FAIL','Supabase/SQL Server Save/Test buttons cannot complete against official backend.','POST /database-profiles and POST /database-profiles/test should save/test drivers.','POST routes return 405 Method Not Allowed.','API_ROUTE_MISSING','Apps/Api/safy_api/app_factory.py','create_app inline database profile helpers','/database-profiles, /database-profiles/test','evidence/DB-SUPA-SAVE-001.json, evidence/DB-MSSQL-TEST-001.json','Official app only implements hardcoded GET database helpers, while dashboard JS calls POST save/test/activate.','Implement database profile routes backed by DataStore and Gateway db drivers; map Supabase RPC/SQL Server errors to clear codes.','High','Apps/Api/safy_api/routes/profiles.py; DataStore/database_profile_store.py; Gateway/db_drivers/*','Tests/test_database_profile_save_contract.py; Tests/test_database_profile_test_contract.py'),
('RC-003','Raw FastAPI validation/method errors bypass SAFY envelope','High','UI Contract','Save/Test','FAIL','Malformed requests or missing fields show raw `detail` instead of SAFY error contract.','All errors should return envelope with request_id.','Missing SQL gives 422 detail list; missing routes give 405 detail.','Response Contract','Apps/Api/safy_api/app_factory.py','create_app missing exception handlers','/query/check and missing save/test endpoints','evidence/CONTRACT-001.json','Route-level handlers do not catch Pydantic validation or method-not-allowed errors.','Add global RequestValidationError/HTTPException handlers and no-raw-500/422 tests.','Low','Apps/Api/safy_api/app_factory.py','Tests/test_no_raw_422_contract.py'),
('RC-004','Rule save contract ambiguous for empty/ambiguous rules','Medium','Rule','Save/Test','PARTIAL','Empty or ambiguous rule can return success envelope with nested warning state rather than clear top-level code.','Invalid empty rule should be ok=false/RULE_TEXT_REQUIRED or documented inactive status.','Observed `success=true` with saved=false / warning_only body for invalid input.','Rule Engine / Response Contract','Apps/Api/safy_api/routes/rules.py; Runtime/strict_services.py','sandbox_rule_save_route / save_rule','/sandbox-rules/save','evidence/RULE-SAVE-003.json','Rule service encodes validation result inside data instead of normalizing top-level save result.','Normalize rule save statuses and UI rendering for active/inactive/ambiguous/invalid.','Low','Apps/Api/safy_api/routes/rules.py; Runtime/strict_services.py','Tests/test_rule_save_contract.py'),
('RC-005','Rule source-of-truth split between strict_services and live Runtime RuleManager','Medium','Rule / Runtime Selection','Runtime Use','PARTIAL','Saved rules may diverge between list/validation and chat generation/runtime constraints.','One canonical RuleManager should own active rules.','Rules route writes strict store and mirrors live RuleManager.','Runtime Selection','Apps/Api/safy_api/routes/rules.py','sandbox_rule_save_route / sandbox_rule_disable_route','/sandbox-rules/save, /sandbox-rules/disable','01_STATIC_FLOW_MAP.md','Two mutable stores must stay synchronized manually.','Make strict_services an adapter over Runtime RuleManager or vice versa; add save/disable/generation consistency tests.','Medium','Runtime/strict_services.py; Runtime/rule_manager.py; Apps/Api/safy_api/routes/rules.py','Tests/test_rule_manager_single_source.py'),
]
for rid,title,severity,group,action,status,sym,exp,act,layer,file,func,endpoint,evidence,why,fix,risk,files,tests in rc_defs:
    root.append(f'''## {rid} — {title}

- Severity: {severity}
- Feature group: {group}
- Action affected: {action}
- Status: {status}
- User-visible symptom: {sym}
- Expected behavior: {exp}
- Actual behavior: {act}
- Root cause layer: {layer}
- Exact location:
  - File: {file}
  - Function/Class: {func}
  - Approx lines: see static flow map and source references
- Endpoint: {endpoint}
- Payload redacted: see evidence files
- Evidence:
  - {evidence}
- Why it happens: {why}
- Recommended fix:
  1. {fix}
  2. Add/expand contract tests and frontend render tests before patching more providers.
- Patch risk: {risk}
- Files likely to change:
  - {files}
- Tests to add/update:
  - {tests}
''')
w('06_ROOT_CAUSE_REPORT.md','\n'.join(root))

w('07_FIX_RECOMMENDATION_PLAN.md', r'''
# Fix Recommendation Plan

## Phase 1 — Response contract baseline
- Goal: guarantee every Save/Test endpoint and malformed request returns one SAFY envelope with request_id.
- Files: `Apps/Api/safy_api/app_factory.py`, `Apps/Api/safy_api/runtime_store.py`.
- Risk: Low.
- Tests: missing body, malformed JSON, method not allowed, provider failure.

## Phase 2 — Frontend render Save/Test result
- Goal: make UI display success/error code/details/request_id consistently for Model, Database, Rule.
- Files: `Apps/Web/dashboard.js`, `Apps/Web/api_client.js`, render modules.
- Risk: Medium.
- Tests: browser/API mock tests for Save/Test errors.

## Phase 3 — Storage persistence
- Goal: persist model/database profiles and rules through canonical stores with redacted secrets.
- Files: `LLM/provider_store.py`, `DataStore/database_profile_store.py`, `DataStore/env_writer.py`, `DataStore/sandbox_rule_store.py`.
- Risk: Medium.
- Tests: save/reload/restart tests.

## Phase 4 — Runtime selection/reload
- Goal: after Save/Activate, runtime uses selected model/database/rules immediately and after restart.
- Files: `Runtime/*`, `Gateway/query_orchestrator.py`, `Apps/Api/safy_api/routes/chat.py`, `Apps/Api/safy_api/routes/query.py`.
- Risk: High.
- Tests: runtime selected model/database/rule flow tests.

## Phase 5 — Provider-specific fixes

### OpenRouter
- Implement `POST /model-profiles`, `POST /model-profiles/{id}/activate`, `POST /model-profiles/{id}/test`.
- Test `/v1/models` and minimal chat completion; redact API key.

### Supabase
- Implement REST connectivity test separately from execute support.
- Implement RPC existence test and map missing RPC to `SUPABASE_RPC_NOT_INSTALLED`.
- Ensure DDL/DML never uses PostgREST direct REST path.

### SQL Server
- Implement SQL Server save/test through `Gateway/db_drivers/sqlserver_driver.py`.
- Map auth/connect/database failures to clear codes.

### Rule Engine
- Normalize ambiguous/invalid Save responses.
- Add dedicated rule test endpoint or explicit evaluated/matched/blocked fields in `/query/check`.
- Consolidate strict_services and Runtime RuleManager.
''')

w('08_SECURITY_REDACTION_AUDIT.md', r'''
# 08 Security Redaction Audit

- Audit evidence redacts OpenRouter-style keys as `sk-***REDACTED`.
- Audit evidence redacts Supabase `sb_secret_*` values as `sb_secret_***REDACTED` or `<REDACTED>`.
- Password/api_key/token/secret fields are replaced with `<REDACTED>` in generated evidence.
- No external OpenRouter/Supabase/SQL Server credentials were sent to third-party services in this audit because official Save/Test endpoints are missing.

Residual risks:

- `.env` exists in repository root and must never be packaged or printed.
- Future provider tests must redact request/response logs and avoid storing Authorization headers.
- UI screenshots should avoid showing secrets in input fields.
''')

readme=f'''# SAFY Full Save/Test Audit — 2026-06-29

Audit-only phase completed. No runtime source was patched.

## Outputs

- `01_STATIC_FLOW_MAP.md`
- `02_SAVE_TEST_MATRIX.csv`
- `03_RESPONSE_CONTRACT_AUDIT.md`
- `04_STORAGE_PERSISTENCE_AUDIT.md`
- `05_RUNTIME_SELECTION_AUDIT.md`
- `06_ROOT_CAUSE_REPORT.md`
- `07_FIX_RECOMMENDATION_PLAN.md`
- `08_SECURITY_REDACTION_AUDIT.md`
- `evidence/`

## Summary

- Total cases: {summary['total']}
- PASS: {summary.get('PASS',0)}
- FAIL: {summary.get('FAIL',0)}
- PARTIAL: {summary.get('PARTIAL',0)}
- NOT_RUN: {summary.get('NOT_RUN',0)}
- BLOCKED: {summary.get('BLOCKED',0)}

Top root causes:

1. RC-001 — Model profile Save/Test API routes missing.
2. RC-002 — Database profile Save/Test API routes missing.
3. RC-003 — Raw FastAPI validation/method errors bypass SAFY envelope.
4. RC-004 — Rule save contract ambiguous for empty/ambiguous rules.
5. RC-005 — Rule source-of-truth split between strict_services and Runtime RuleManager.
'''
w('README.md', readme)
print(json.dumps(summary, ensure_ascii=False))
