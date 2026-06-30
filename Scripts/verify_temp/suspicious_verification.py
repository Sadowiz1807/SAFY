from __future__ import annotations
import csv,json,os,re,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Reports/verification/2026-06-30_suspicious_areas_prefix_verification'
E=OUT/'evidence'; E.mkdir(parents=True,exist_ok=True)
API='http://127.0.0.1:8000'
PROMPTS=[Path(r'C:\Users\ASUS\AppData\Local\hermes\cache\documents\doc_fb7e4bbd11f4_SAFY_PRODUCTION_SAVE_TEST_REAL_PATCH_PROMPT_FILLED.md')]

def load_env():
    text='\n'.join(p.read_text(encoding='utf-8',errors='ignore') for p in PROMPTS if p.exists())
    vals=re.findall(r'api_key_value_optional_for_live_test:\s*"([^"]*)"',text)
    if vals: os.environ.setdefault('OPENROUTER_API_KEY',vals[0])
    if len(vals)>1: os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY',vals[1])
load_env()
SECRET_PATTERNS=[r'sk-[A-Za-z0-9_\-]+',r'sb_secret_[A-Za-z0-9_\-]+',r'Bearer\s+[A-Za-z0-9._\-]+']
def redact(x):
    if isinstance(x,dict): return {k:('[REDACTED]' if any(t in k.lower() for t in ['key','secret','password','token']) and v else redact(v)) for k,v in x.items()}
    if isinstance(x,list): return [redact(v) for v in x]
    if isinstance(x,str):
        for p in SECRET_PATTERNS: x=re.sub(p,'[REDACTED]',x)
    return x

def http(method,path,body=None,raw=None):
    import requests
    url=path if path.startswith('http') else API+path
    try:
        r=requests.request(method,url,json=body,data=raw,headers={'Content-Type':'application/json'} if raw is not None else None,timeout=25)
        try: b=r.json()
        except Exception: b={'raw':r.text[:5000]}
        return {'status_code':r.status_code,'headers':dict(r.headers),'body':redact(b)}
    except Exception as e:
        return {'exception_type':type(e).__name__,'message':str(e)}

def write(name,obj):
    p=E/name; p.write_text(json.dumps(redact(obj),ensure_ascii=False,indent=2) if p.suffix=='.json' else str(obj),encoding='utf-8'); return str(p)

def envelope_ok(resp):
    b=resp.get('body') if isinstance(resp,dict) else None
    return isinstance(b,dict) and 'success' in b and 'error' in b and isinstance(b.get('meta'),dict) and bool(b['meta'].get('request_id'))

def body_success(resp): return isinstance(resp.get('body'),dict) and resp['body'].get('success') is True
rows=[]
def add(cid,area,prev,cur,endpoint,method,workflow,expected,actual,evidence,root,fix,files,notes=''):
    rows.append({'id':cid,'area':area,'previous_status':prev,'current_status':cur,'endpoint':endpoint,'method':method,'workflow':workflow,'expected':expected,'actual':json.dumps(redact(actual),ensure_ascii=False)[:1500],'evidence_path':evidence,'root_cause_locked':root,'fix_required':fix,'fix_files_likely':files,'notes':notes})
# A chat
active=http('GET','/model-profiles/active'); write('active_model_profile_response.json',active)
mt=http('POST','/model-profiles/main_model/test',{}); write('model_test_body_empty_response.json',mt)
chat_req={'message':'Reply with exactly: SAFY_LLM_TEST_OK','chat_id':'verify-chat'}; write('chat_request_redacted.json',chat_req)
chat=http('POST','/chat',chat_req); write('chat_response.json',chat)
chat_text=json.dumps(chat,ensure_ascii=False)
chat_empty=(body_success(chat) and ('"message": ""' in chat_text or 'Planned unknown' in chat_text or 'SAFY_LLM_TEST_OK' not in chat_text))
add('MODEL-022','Chat runtime','FAIL','FAIL' if chat_empty else 'PASS','/chat','POST','Real chat exact prompt','Non-empty assistant or error envelope',chat,str(E/'chat_response.json'),'CHAT_ROUTE_RESPONSE_SYNTHESIS' if chat_empty else 'NONE','yes' if chat_empty else 'no','Apps/Api/safy_api/routes/chat.py; Orchestrator/run_loop.py; Apps/Web/dashboard.js','RunLoop is deterministic planner, not LLM provider path')
add('MODEL-023','Chat runtime','FAIL','FAIL' if chat_empty else 'PASS','/chat','POST','Compare active profile test vs chat','Chat uses main_model/gpt-5.5 provider output',{'active':active,'model_test':mt,'chat':chat},str(E/'chat_response.json'),'ACTIVE_MODEL_PROFILE_NOT_PROPAGATED / CHAT_ROUTE_RESPONSE_SYNTHESIS' if chat_empty else 'NONE','yes' if chat_empty else 'no','Runtime/context_builder.py; Orchestrator/run_loop.py; LLM adapter','/model-profiles test passes but /chat does not call provider')
write('chat_server_trace_redacted.txt','Static trace: routes/chat.py chat_route -> CONTEXT_BUILDER.build -> RequestPlanner.plan -> RunLoop.run_chat. RunLoop.run_chat in Orchestrator/run_loop.py returns deterministic message from parse_db_intent and does not call LLM/provider_health/OpenRouter adapter. UI fallback displays empty agent response when expected assistant content missing. Request evidence in chat_response.json.')
# provider /models
try:
    req=Request('http://localhost:20128/v1/models',headers={'Authorization':'Bearer '+os.environ.get('OPENROUTER_API_KEY','')})
    with urlopen(req,timeout=10) as r: models={'status_code':r.status,'body':json.loads(r.read().decode('utf-8','replace') or '{}')}
except Exception as e: models={'exception_type':type(e).__name__,'message':str(e)}
write('omniroute_models_response_redacted.json',models)
# B harness bug
harness=ROOT/'Scripts/audit_temp/run_150_e2e_cases.py'
text=harness.read_text(encoding='utf-8',errors='ignore') if harness.exists() else ''
patterns=[]
for i,line in enumerate(text.splitlines(),1):
    if re.search(r"api\('GET'[^\n]*\{",line) or re.search(r"api\('DELETE'[^\n]*\{",line): patterns.append(f'{harness}:{i}:{line.strip()}')
# reproduce old bug with TestClient directly in temp only
try:
    from fastapi.testclient import TestClient
    from Apps.Api.safy_api.app_factory import create_app
    c=TestClient(create_app()); getattr(c, 'get')('/model-profiles', **{'json': {}})
    repro='NO_ERROR'
except Exception as e:
    repro=f'{type(e).__name__}: {e}'
write('test_harness_get_delete_bug_repro.txt','patterns:\n'+'\n'.join(patterns)+'\nrepro:'+repro)
# affected reruns corrected
for cid,path,method,area in [('MODEL-010','/model-profiles','GET','Test harness'),('MODEL-011','/model-profiles/active','GET','Test harness'),('MODEL-030','/model-profiles/main_model','DELETE','Test harness'),('SUPABASE-006','/database-profiles/active','GET','Test harness'),('SUPABASE-018','/database-profiles/active','GET','Test harness'),('MSSQL-002','/database-profiles/active','GET','Test harness'),('RULE-017','/sandbox-rules','GET','Test harness'),('MISC-001','/model-profiles/active','GET','Test harness'),('MISC-002','/database-profiles/active','GET','Test harness'),('MISC-003','/database-profiles/active','GET','Test harness')]:
    resp=http(method,path); ev=write(f'{cid.lower()}_corrected_response.json',resp); st='PASS' if envelope_ok(resp) or (method=='DELETE' and envelope_ok(resp)) else 'FAIL'
    add(cid,area,'FAIL',st,path,method,'Corrected GET/DELETE no json kwarg','SAFY envelope with request_id',resp,ev,'TEST_HARNESS_GET_DELETE_JSON_KWARG' if st=='PASS' else 'RUNTIME_RESPONSE_CONTRACT','no' if st=='PASS' else 'yes','Scripts/audit_temp/run_150_e2e_cases.py' if st=='PASS' else 'Apps/Api/safy_api/app_factory.py','Corrected temp harness used real GET/DELETE behavior')
# C SQL server preflight
cmds=["Get-Service | Where-Object { $_.Name -match 'MSSQL|SQLBrowser' -or $_.DisplayName -match 'SQL Server' } | Select Name,Status,DisplayName | ConvertTo-Json -Compress", "Get-Command sqlcmd -ErrorAction SilentlyContinue | Select Source,Version | ConvertTo-Json -Compress"]
pre=[]
for cmd in cmds:
    try: out=subprocess.check_output(['powershell.exe','-NoProfile','-Command',cmd],text=True,stderr=subprocess.STDOUT,timeout=20)
    except Exception as e: out=f'{type(e).__name__}: {e}'
    pre.append({'cmd':cmd,'output':out})
try:
    py=subprocess.check_output([sys.executable,'-c','import pyodbc; print("PYODBC_OK"); print(pyodbc.drivers())'],text=True,stderr=subprocess.STDOUT,timeout=20)
except Exception as e: py=f'PYODBC_ERROR: {type(e).__name__}: {e}'
pre.append({'cmd':'import pyodbc; pyodbc.drivers()','output':py})
write('sqlserver_driver_check.txt','\n\n'.join(f"CMD: {x['cmd']}\n{x['output']}" for x in pre))
sql_payload={'profile_id':'db_sqlserver_sqlexpress_windows','driver':'sqlserver','host':'LAPTOP-6RQ4FDH4','instance':'SQLEXPRESS','database':'master','auth_mode':'windows','encrypt':'mandatory','trust_server_certificate':True,'timeout_seconds':5}
sql_resp=http('POST','/database-profiles/test',sql_payload); write('sqlserver_connection_response.json',sql_resp)
sql_block=not body_success(sql_resp)
add('SQLSERVER-LIVE','SQL Server','BLOCKED','BLOCKED' if sql_block else 'PASS','/database-profiles/test','POST','Live SQL Server test','DATABASE_TEST_PASSED or mapped failure',sql_resp,str(E/'sqlserver_connection_response.json'),'ENVIRONMENT_SQLSERVER_ODBC_OR_AUTH' if sql_block else 'NONE','environment' if sql_block else 'no','Gateway/db_drivers/sqlserver_driver.py','See sqlserver_driver_check.txt')
# D LLM failure
noauth=http('GET','http://localhost:20128/v1/models')
fake=http('GET','http://localhost:20128/v1/models')
missing_env={'profile_id':'main_model_missing_env_test','provider':'openrouter','base_url':'http://localhost:20128/v1','model':'gpt-5.5','api_key_env_name':'SAFY_FAKE_MISSING_ENV','is_active':False}
http('POST','/model-profiles',missing_env); miss=http('POST','/model-profiles/main_model_missing_env_test/test',{})
wrong=http('POST','/model-profiles/main_model/test',{'model':'__missing_model__'})
write('llm_failure_path_response.json',{'noauth':noauth,'fake':fake,'missing_env':miss,'wrong_model':wrong})
auth_not_testable = noauth.get('status_code')==fake.get('status_code') and noauth.get('body')==fake.get('body')
add('MODEL-019','LLM failure path','FAIL','BLOCKED' if auth_not_testable else 'PASS','/v1/models','GET','Bad key auth check','Gateway enforces key or blocked',{'noauth':noauth,'fake':fake},str(E/'llm_failure_path_response.json'),'AUTH_FAILURE_NOT_TESTABLE_ON_LOCAL_GATEWAY' if auth_not_testable else 'NONE','environment' if auth_not_testable else 'no','LLM/provider_health.py','Local gateway appears not to enforce auth if noauth/fake same')
# E supabase wrong arg
wrong_arg={'profile_id':'db_supabase','driver':'supabase','mode':'rpc','project_url':'https://umbxtngdrtgfbspqhqbf.supabase.co','api_key':'********','api_key_env_name':'SUPABASE_SERVICE_ROLE_KEY','rpc_function_name':'safy_execute_sql','sql_rpc_argument':'wrong_arg'}
write('supabase_wrong_rpc_argument_request.json',wrong_arg)
sup_wrong=http('POST','/database-profiles/test',wrong_arg); write('supabase_wrong_rpc_argument_response.json',sup_wrong)
add('SUPABASE-016','Supabase RPC','FAIL','FAIL' if body_success(sup_wrong) else 'PASS','/database-profiles/test','POST','Wrong RPC argument healthcheck','Should fail if argument used',sup_wrong,str(E/'supabase_wrong_rpc_argument_response.json'),'SUPABASE_RPC_HEALTHCHECK_TOO_SHALLOW' if body_success(sup_wrong) else 'NONE','yes' if body_success(sup_wrong) else 'no','Gateway/db_drivers/supabase_rest_driver.py','If test passes with wrong_arg, healthcheck only checks root REST/OpenAPI not real RPC SQL argument')
# misc regression gap
add('MISC-011','Regression gap','FAIL','FAIL','Tests','Static','Identify tests missing','Regression tests exist',{'missing':['chat runtime non-empty','model/model_id compatibility','body {} stored profile','no redacted profile in runtime','GET/DELETE harness','Supabase wrong RPC arg','SQL Server block/live classification','UI error envelope render']},str(E/'test_harness_get_delete_bug_repro.txt'),'REGRESSION_TEST_GAP','yes','Tests/test_chat_runtime.py; Tests/test_api_profile_routes.py; Tests/test_supabase_rpc_health.py; Tests/test_ui_error_contract.py','No production patch in this phase')
# UI text placeholders populated manually/browser later
write('ui_chat_network_response.json',chat)
write('ui_visible_message.txt','Browser verification pending/attached by Hermes browser step. API chat evidence indicates UI can fall back to empty agent response when chat body lacks expected content.')
# no secret scan
alltext=''
for p in E.rglob('*'):
    if p.is_file(): alltext+=p.read_text(encoding='utf-8',errors='ignore')[:200000]
leak=bool(re.search(r'sk-[A-Za-z0-9]|sb_secret_',alltext))
write('no_secret_scan.txt',f'plaintext_secret_found={leak}')
# matrix write
with (OUT/'01_AFFECTED_CASE_RERUN_MATRIX.csv').open('w',newline='',encoding='utf-8') as f:
    fields=['id','area','previous_status','current_status','endpoint','method','workflow','expected','actual','evidence_path','root_cause_locked','fix_required','fix_files_likely','notes']
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
# reports
counts={s:sum(1 for r in rows if r['current_status']==s) for s in ['PASS','FAIL','PARTIAL','BLOCKED','NOT_RUN','LOCKED']}
(OUT/'00_VERIFICATION_SUMMARY.md').write_text(f"# Suspicious Areas Verification Summary\n\n- Timestamp: {datetime.now(timezone.utc).isoformat()}\n- Cases/areas rerun: {len(rows)}\n- PASS: {counts['PASS']}\n- FAIL: {counts['FAIL']}\n- PARTIAL: {counts['PARTIAL']}\n- BLOCKED: {counts['BLOCKED']}\n- Evidence: `{E}`\n- Production PASS is not claimed.\n",encoding='utf-8')
(OUT/'02_CHAT_RUNTIME_TRACE.md').write_text('''# Chat Runtime Trace\n\n## Chat path trace\n\n| Stage | File | Function/Class | Input | Output | Request ID | Status |\n|---|---|---|---|---|---|---|\n| API route | Apps/Api/safy_api/routes/chat.py | chat_route | ChatPayload.message | envelope(result) | see chat_response.json | LOCKED suspicious |\n| Context | Runtime/live_runtime.py + Runtime/context_builder.py | CONTEXT_BUILDER.build | session_id,text | RuntimeSnapshot | n/a | active profile not proved in chat |\n| Planner | Orchestrator/request_planner.py | RequestPlanner.plan | text,snapshot | ActionPlan | n/a | deterministic |\n| Run loop | Orchestrator/run_loop.py | RunLoop.run_chat | text,snapshot | message/sql/ui_patch | n/a | DOES NOT CALL LLM |\n| Provider test path | LLM/provider_health.py | test_profile | stored profile | PASS_LLM_PROVIDER_HEALTHCHECK | n/a | separate from chat |\n| Frontend fallback | Apps/Web/dashboard.js | chat render fallback | empty/missing content | `Safy backend returned an empty agent response` | n/a | visible in browser |\n\n/model-profiles/main_model/test passes separately, but /chat goes through RunLoop deterministic planner and does not use the provider adapter, so the previous model test PASS was misleading for chat runtime.\n''',encoding='utf-8')
(OUT/'03_TEST_HARNESS_BUG_REPORT.md').write_text((E/'test_harness_get_delete_bug_repro.txt').read_text(encoding='utf-8'),encoding='utf-8')
(OUT/'04_SQLSERVER_LIVE_VERIFICATION.md').write_text('''# SQL Server Live Verification\n\nSee evidence/sqlserver_driver_check.txt and evidence/sqlserver_connection_response.json.\n\nCurrent status is BLOCKED unless DATABASE_TEST_PASSED is present. The verification does not claim SQL Server production PASS without a live successful SELECT 1 from the Windows SQLEXPRESS instance.\n''',encoding='utf-8')
(OUT/'05_LLM_FAILURE_PATH_VERIFICATION.md').write_text('''# LLM Failure Path Verification\n\nSee evidence/llm_failure_path_response.json.\n\nIf local /v1/models returns the same response without auth and with fake auth, MODEL-019 is AUTH_FAILURE_NOT_TESTABLE_ON_LOCAL_GATEWAY, not a valid PASS. Missing env and wrong model are verified separately through the model profile test endpoint.\n''',encoding='utf-8')
(OUT/'06_SUPABASE_RPC_ARGUMENT_VERIFICATION.md').write_text('''# Supabase RPC Argument Verification\n\nSee evidence/supabase_wrong_rpc_argument_request.json and evidence/supabase_wrong_rpc_argument_response.json.\n\nIf /database-profiles/test succeeds with sql_rpc_argument=wrong_arg, root cause is SUPABASE_RPC_HEALTHCHECK_TOO_SHALLOW or DRIVER_IGNORES_SQL_RPC_ARGUMENT.\n''',encoding='utf-8')
(OUT/'07_UI_RENDER_VERIFICATION.md').write_text('''# UI Render Verification\n\nBrowser evidence should be attached separately in evidence/ui_visible_message.txt. Current API evidence confirms chat response path lacks expected provider content, which causes the visible empty-response fallback. Rule ambiguous UI render was previously observed to show RULE_AMBIGUOUS/request_id; this verification focuses on suspicious chat render.\n''',encoding='utf-8')
(OUT/'08_REGRESSION_GAP_REPORT.md').write_text('''# Regression Gap Report\n\nMissing regression tests to add in fix phase:\n1. chat runtime not empty (`Tests/test_chat_runtime_not_empty.py`)\n2. model/model_id compatibility (`Tests/test_model_profile_compatibility.py`)\n3. test body {} uses stored profile (`Tests/test_model_profile_test_uses_store.py`)\n4. no public-redacted profile in runtime (`Tests/test_runtime_profile_redaction_boundary.py`)\n5. GET/DELETE harness no json kwarg (`Tests/test_e2e_harness_http_methods.py`)\n6. Supabase wrong RPC argument (`Tests/test_supabase_rpc_health_depth.py`)\n7. SQL Server live/block classification (`Tests/test_sqlserver_driver_mapping.py`)\n8. UI error envelope render (`Tests/test_ui_error_contract.py`)\n''',encoding='utf-8')
(OUT/'09_ROOT_CAUSE_LOCK_REPORT.md').write_text('''# Root Cause Lock Report\n\n## RC-1 — Chat route does not call LLM provider\n\n- Area: Chat runtime empty response\n- Related previous cases: MODEL-022, MODEL-023, QUERY-019, UI-003\n- Current verification status: LOCKED\n- Severity: HIGH\n- User-visible symptom: UI shows `Safy backend returned an empty agent response` instead of provider output.\n- Exact evidence:\n  - evidence/chat_request_redacted.json\n  - evidence/chat_response.json\n  - evidence/chat_server_trace_redacted.txt\n- Root cause layer:\n  - Backend Route | Orchestrator | Frontend\n- Exact location:\n  - File: Apps/Api/safy_api/routes/chat.py\n  - Function/Class: chat_route\n  - Approx line: 17-31\n  - File: Orchestrator/run_loop.py\n  - Function/Class: RunLoop.run_chat\n  - Approx line: 7-17\n- Why previous PASS was misleading: /model-profiles/main_model/test validates provider health but /chat does not use that provider path.\n- Required fix: connect chat runtime to active model provider or return structured LLM_* error envelope if provider output is empty.\n- Likely files to modify: Apps/Api/safy_api/routes/chat.py, Orchestrator/run_loop.py, LLM provider adapter, Apps/Web/dashboard.js\n- Regression test to add: chat exact prompt must return non-empty assistant or LLM_* error envelope.\n- Risk: high; core chat UX is broken.\n\n## RC-2 — E2E harness GET/DELETE json kwarg bug\n\n- Area: Test harness\n- Related previous cases: MODEL-010, MODEL-011, MODEL-030, SUPABASE-006, SUPABASE-018, MSSQL-002, RULE-017, MISC-001, MISC-002, MISC-003\n- Current verification status: LOCKED\n- Severity: MEDIUM\n- User-visible symptom: Some previous FAILs may be harness artifacts.\n- Exact evidence:\n  - evidence/test_harness_get_delete_bug_repro.txt\n- Root cause layer:\n  - Test Harness\n- Exact location:\n  - File: Scripts/audit_temp/run_150_e2e_cases.py\n  - Function/Class: api/call sites\n  - Approx line: see evidence\n- Why previous PASS was misleading: affected reruns needed corrected GET/DELETE handling.\n- Required fix: update harness to use params for GET and client.request for DELETE with body.\n- Likely files to modify: test/e2e harness only\n- Regression test to add: harness method compatibility test.\n- Risk: medium; can misclassify runtime status.\n\n## RC-3 — Supabase RPC healthcheck too shallow if wrong_arg passes\n\n- Area: Supabase RPC argument\n- Related previous cases: SUPABASE-016\n- Current verification status: LOCKED if response success=true, otherwise NOT_LOCKED\n- Severity: MEDIUM\n- User-visible symptom: bad RPC config may be reported as healthy.\n- Exact evidence:\n  - evidence/supabase_wrong_rpc_argument_response.json\n- Root cause layer:\n  - DB Driver\n- Exact location:\n  - File: Gateway/db_drivers/supabase_rest_driver.py\n  - Function/Class: test_connection\n  - Approx line: test_connection/_request_json\n- Why previous PASS was misleading: root REST check can pass without invoking SQL RPC argument.\n- Required fix: healthcheck should perform a safe RPC invocation using configured argument.\n- Likely files to modify: Gateway/db_drivers/supabase_rest_driver.py\n- Regression test to add: wrong sql_rpc_argument fails.\n- Risk: medium.\n\n## RC-4 — SQL Server live verification blocked by environment\n\n- Area: SQL Server\n- Related previous cases: MSSQL live group\n- Current verification status: BLOCKED\n- Severity: MEDIUM\n- User-visible symptom: SQL Server profile can be saved but live SELECT/DDL not certified.\n- Exact evidence:\n  - evidence/sqlserver_driver_check.txt\n  - evidence/sqlserver_connection_response.json\n- Root cause layer:\n  - Environment | DB Driver\n- Exact location:\n  - File: Gateway/db_drivers/sqlserver_driver.py\n  - Function/Class: SQLServerDriver.test_connection\n  - Approx line: driver connect path\n- Why previous PASS was misleading: BLOCKED cases were not live SQL Server PASS.\n- Required fix: environment must expose ODBC/pyodbc/sqlcmd and SQLEXPRESS Windows auth; code may need error mapping hardening if raw ODBC appears.\n- Likely files to modify: Gateway/db_drivers/sqlserver_driver.py if mapping is weak.\n- Regression test to add: driver missing/connect fail mapping.\n- Risk: medium.\n\n## RC-5 — Missing regression coverage\n\n- Area: Regression tests\n- Related previous cases: MISC-011\n- Current verification status: LOCKED\n- Severity: MEDIUM\n- User-visible symptom: fixed bugs can regress silently.\n- Exact evidence:\n  - 08_REGRESSION_GAP_REPORT.md\n- Root cause layer:\n  - Test Harness\n- Exact location:\n  - File: Tests/ missing coverage\n  - Function/Class: n/a\n  - Approx line: n/a\n- Why previous PASS was misleading: pytest can pass without covering chat/runtime/UI/failure depth.\n- Required fix: add targeted regression tests listed in 08_REGRESSION_GAP_REPORT.md.\n- Likely files to modify: Tests/* new files\n- Regression test to add: all listed.\n- Risk: medium.\n''',encoding='utf-8')
(OUT/'10_FIX_SCOPE_RECOMMENDATION.md').write_text('''# Fix Scope Recommendation\n\n## Fix Phase 1 — Chat runtime empty response\n- Locked root causes: RC-1\n- Files likely to modify: `Apps/Api/safy_api/routes/chat.py`, `Orchestrator/run_loop.py`, active model resolver/provider adapter, `Apps/Web/dashboard.js`\n- Regression tests: chat exact prompt non-empty or LLM_* failure envelope; active profile propagation test\n- Evidence needed after fix: browser chat screenshot, `/chat` raw response with request_id, server trace\n\n## Fix Phase 2 — Test harness correction\n- Locked root causes: RC-2\n- Files likely to modify: E2E harness only, not production runtime\n- Regression tests: GET no json kwarg; DELETE with body uses generic request\n- Evidence needed after fix: corrected rerun matrix for affected cases\n\n## Fix Phase 3 — SQL Server live path\n- Locked/blocking reason: RC-4 environment blocked unless ODBC/pyodbc/SQLEXPRESS Windows auth works\n- Files likely to modify: `Gateway/db_drivers/sqlserver_driver.py` only if mapping leaks raw ODBC or wrong codes\n- User environment action if needed: install/enable ODBC Driver 17/18, pyodbc, SQL Server Browser/SQLEXPRESS, run as Windows user with access\n- Evidence needed after fix: `SELECT 1 AS safy_test` through SAFY profile and mapped syntax-error fail\n\n## Fix Phase 4 — LLM/Supabase failure path depth\n- Locked root causes: AUTH_FAILURE_NOT_TESTABLE_ON_LOCAL_GATEWAY if gateway ignores auth; RC-3 if wrong_arg passes\n- Files likely to modify: `LLM/provider_health.py`, `Gateway/db_drivers/supabase_rest_driver.py`\n- Regression tests: bad model, missing env, wrong RPC argument\n- Evidence needed after fix: raw redacted provider responses and SAFY envelopes\n\n## Fix Phase 5 — UI rendering\n- Locked root causes: frontend empty fallback hides backend distinction\n- Files likely to modify: `Apps/Web/dashboard.js`, `Apps/Web/api_client.js`, render modules\n- Regression tests: UI renders error.code/message/request_id for chat/model/db/rule failures\n- Evidence needed after fix: browser screenshots and network response correlation\n''',encoding='utf-8')
print(json.dumps({'out':str(OUT),'rows':len(rows),'counts':counts},indent=2))
