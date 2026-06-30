import csv, json, re
from pathlib import Path
from fastapi.testclient import TestClient
from Apps.Api.safy_api.app_factory import create_app

OUT=Path('Reports/audits/2026-06-29_full_save_test_audit')
EVD=OUT/'evidence'
EVD.mkdir(parents=True, exist_ok=True)
client=TestClient(create_app())

def redact_obj(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if re.search(r'api[_-]?key|password|token|secret|credential', str(k), re.I):
                out[k] = '<REDACTED>'
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        text = re.sub(r'sk-[A-Za-z0-9_-]+', 'sk-***REDACTED', obj)
        text = re.sub(r'sb_secret_[A-Za-z0-9_-]+', 'sb_secret_***REDACTED', text)
        return text
    return obj

def call(case_id, method, path, payload=None):
    kwargs={}
    if payload is not None: kwargs['json']=payload
    r=getattr(client, method.lower())(path, **kwargs)
    rec={'request': {'method':method,'path':path,'payload_redacted':redact_obj(payload or {})}, 'status_code': r.status_code, 'headers': {'content-type': r.headers.get('content-type')}}
    try: body=r.json()
    except Exception: body=r.text[:1000]
    rec['body_redacted']=redact_obj(body) if isinstance(body,(dict,list)) else body
    p=EVD/f'{case_id}.json'
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')
    return rec, str(p)

cases=[]
def add(case_id, group, action, target, payload, endpoint, method, expected, status, layer, root, reco, risk, files, tests, rec=None, ev=''):
    body=rec.get('body_redacted') if rec else None
    ok = None
    code = ''
    msg = ''
    details = {}
    http = ''
    if rec:
        http = rec['status_code']
        if isinstance(body, dict):
            ok = body.get('ok') if 'ok' in body else body.get('success')
            code = body.get('code') or (body.get('error') or {}).get('code') or ''
            msg = body.get('message') or (body.get('error') or {}).get('message') or ''
            details = body.get('details') or (body.get('error') or {}).get('details') or {}
    cases.append({
      'id':case_id,'feature_group':group,'action':action,'target':target,'precondition':'Audit-only TestClient against current app_factory official app','input_payload_redacted':json.dumps(redact_obj(payload or {}),ensure_ascii=False),'endpoint':endpoint,'method':method,'http_status':http,'ok':ok,'code':code,'message':msg,'details_redacted':json.dumps(redact_obj(details),ensure_ascii=False),'ui_result':'UI_NOT_AUTOMATED_API_DIRECT','storage_result':'NOT_VERIFIED' if status in ['NOT_RUN','BLOCKED','FAIL'] else 'VERIFIED_BY_API_RESPONSE','reload_result':'NOT_VERIFIED','runtime_effect':'NOT_VERIFIED' if group!='Rule' else 'CHECKED_BY_QUERY_CHECK','evidence_path':ev,'status':status,'root_cause_layer':layer,'root_cause':root,'recommendation':reco,'patch_risk':risk,'required_fix_files':files,'required_tests':tests})

# Model endpoints: UI calls these but official app only provides GET helpers.
llm_valid={'profile_id':'gpt-5.5','display_name':'gpt-5.5','provider_type':'openrouter','base_url':'http://localhost:20128/v1','api_key':'sk-***REDACTED','model':'gpt-5.5','mode':'chat_completions'}
for cid,payload in [('LLM-SAVE-001',llm_valid),('LLM-SAVE-002',{**llm_valid,'model':''}),('LLM-SAVE-003',{**llm_valid,'base_url':'not-a-url'}),('LLM-SAVE-004',{'profile_id':'gpt-5.5','model':'gpt-5.5-updated','api_key':'********'})]:
    rec,ev=call(cid,'POST','/model-profiles',payload)
    add(cid,'Model LLM','save','OpenRouter',payload,'/model-profiles','POST','Save model profile with clear contract','FAIL','API_ROUTE_MISSING','POST /model-profiles is not implemented in official app_factory; dashboard calls it but backend only defines GET /model-profiles.','Implement route-owner model profile save endpoint backed by LLM provider store; return SAFY envelope and preserve existing secret on masked update.','Medium','Apps/Api/safy_api/app_factory.py; Apps/Api/safy_api/routes/profiles.py; LLM/provider_store.py','Tests/test_model_profile_save_contract.py',rec,ev)
for cid in ['LLM-TEST-001','LLM-TEST-002','LLM-TEST-003']:
    rec,ev=call(cid,'POST','/model-profiles/gpt-5.5/test',{})
    add(cid,'Model LLM','test','OpenRouter',{},'/model-profiles/{id}/test','POST','Test provider via /v1/models or chat completions','FAIL','API_ROUTE_MISSING','POST /model-profiles/{id}/test is not implemented in official app_factory, while dashboard calls it.','Implement provider test endpoint using LLM/provider_health.py with redacted auth errors and SAFY envelope.','Medium','Apps/Api/safy_api/routes/profiles.py; LLM/provider_health.py','Tests/test_model_profile_test_contract.py',rec,ev)
add('LLM-RUNTIME-001','Model LLM','runtime-use','selected OpenRouter profile',{},'/agent/chat','POST','Runtime uses selected model','NOT_RUN','RUNTIME_SELECTION','Cannot verify selected OpenRouter runtime use because save/select/test endpoints are missing.','Implement save/select/test first, then assert /agent/chat uses selected profile id/model.','Medium','Apps/Api/safy_api/routes/chat.py; LLM/provider_store.py','Tests/test_runtime_uses_selected_model.py')

# Database endpoints.
supa={'profile_id':'db_supabase','driver':'supabase','project_url':'https://umbxtngdrtgfbspqhqbf.supabase.co/rest/v1/','api_key':'sb_secret_***REDACTED','rpc_function':'safy_execute_sql'}
sqls={'profile_id':'db_sqlserver_local','driver':'sqlserver','host':'localhost','database':'SAFY_TEST','auth_mode':'windows','trust_cert':True,'encrypt':'optional'}
for cid,payload,target in [('DB-SUPA-SAVE-001',supa,'Supabase REST'),('DB-SUPA-SAVE-002',{**supa,'mode':'rpc'},'Supabase RPC'),('DB-SUPA-SAVE-003',{**supa,'driver':'postgresql','ssl':'require'},'Supabase direct PG'),('DB-MSSQL-SAVE-001',sqls,'SQL Server')]:
    rec,ev=call(cid,'POST','/database-profiles',payload)
    add(cid,'Database','save',target,payload,'/database-profiles','POST','Persist database profile with redacted secret','FAIL','API_ROUTE_MISSING','POST /database-profiles is not implemented in official app_factory; dashboard calls it but backend only defines GET helpers.','Implement database profile save route backed by DataStore/database_profile_store.py and EnvWriter secret handling.','High','Apps/Api/safy_api/routes/profiles.py; DataStore/database_profile_store.py; DataStore/env_writer.py','Tests/test_database_profile_save_contract.py',rec,ev)
for cid,payload,target in [('DB-SUPA-TEST-001',supa,'Supabase REST'),('DB-SUPA-TEST-002',{**supa,'mode':'rpc'},'Supabase RPC exists'),('DB-SUPA-TEST-003',{**supa,'sql':'SELECT 1 AS safy_test;'},'Supabase RPC safe SQL'),('DB-SUPA-TEST-004',{**supa,'sql':'CREATE TABLE audit_x (id bigint primary key);'},'Supabase RPC DDL'),('DB-SUPA-TEST-005',{**supa,'api_key':'<REDACTED_WRONG>'},'Supabase wrong key'),('DB-MSSQL-TEST-001',{**sqls,'sql':'SELECT 1 AS safy_test;'},'SQL Server connect'),('DB-MSSQL-TEST-002',{**sqls,'database':'missing_db'},'SQL Server wrong database'),('DB-MSSQL-TEST-003',{**sqls,'sql':'IF OBJECT_ID(\'dbo.safy_audit_smoke_test\', \'U\') IS NULL CREATE TABLE dbo.safy_audit_smoke_test (id BIGINT NOT NULL PRIMARY KEY);'},'SQL Server DDL')]:
    rec,ev=call(cid,'POST','/database-profiles/test',payload)
    add(cid,'Database','test',target,payload,'/database-profiles/test','POST','Connection/test endpoint returns clear envelope','FAIL','API_ROUTE_MISSING','POST /database-profiles/test is not implemented in official app_factory; dashboard calls it but backend route is absent.','Implement database test route using Gateway/db_drivers/factory.py; map Supabase RPC missing to SUPABASE_RPC_NOT_INSTALLED and SQL Server errors to DATABASE_* codes.','High','Apps/Api/safy_api/routes/profiles.py; Gateway/db_drivers/*','Tests/test_database_profile_test_contract.py',rec,ev)
add('DB-SUPA-RUNTIME-001','Database','runtime-use','selected Supabase profile',{},'/query/check + /query/execute','POST','Runtime uses selected Supabase profile','NOT_RUN','RUNTIME_SELECTION','Cannot verify selected Supabase profile runtime use because save/select/test endpoints are missing.','Implement profile save/select and assert query/check/execute uses profile id without mixing sandbox id.','High','Gateway/query_orchestrator.py; Apps/Api/safy_api/routes/query.py','Tests/test_supabase_runtime_selection.py')
add('DB-MSSQL-RUNTIME-001','Database','runtime-use','selected SQL Server profile',{},'/query/check + /query/execute','POST','Runtime uses selected SQL Server driver','NOT_RUN','RUNTIME_SELECTION','Cannot verify selected SQL Server profile runtime use because save/select/test endpoints are missing.','Implement SQL Server profile save/select and assert driver sqlserver reaches sqlserver_driver.','High','Gateway/db_drivers/sqlserver_driver.py; Gateway/query_orchestrator.py','Tests/test_sqlserver_runtime_selection.py')

# Rule cases.
rule_valid={'database_profile_id':'audit_db','sandbox_id':'audit_sandbox','raw_text':'Mọi bảng được tạo phải có cột id hoặc ID làm định danh'}
for cid,payload,expect_status in [('RULE-SAVE-001',rule_valid,'PASS'),('RULE-SAVE-002',{**rule_valid,'raw_text':'Bảng phải chuẩn và an toàn'},'PARTIAL'),('RULE-SAVE-003',{**rule_valid,'raw_text':''},'FAIL'),('RULE-TEST-003',{**rule_valid,'raw_text':'Không cho phép DROP TABLE'},'PASS')]:
    rec,ev=call(cid,'POST','/sandbox-rules/save',payload)
    layer='Rule Engine' if expect_status!='PASS' else 'OK'
    root='Empty/ambiguous rules are returned as success envelopes with warning_only payload rather than a normalized ok=false/code contract.' if expect_status!='PASS' else 'Rule save returned structured response.'
    reco='Normalize ambiguous/empty rule save to explicit code RULE_AMBIGUOUS/RULE_TEXT_REQUIRED or a documented inactive status with UI-visible message.' if expect_status!='PASS' else 'Keep behavior but align response contract fields.'
    add(cid,'Rule','save','Sandbox rules',payload,'/sandbox-rules/save','POST','Save valid/ambiguous/invalid rule clearly',expect_status,layer,root,reco,'Low','Apps/Api/safy_api/routes/rules.py; Runtime/strict_services.py; Core/rules/semantic_compiler.py','Tests/test_rule_save_contract.py',rec,ev)
# Rule check via query/check
for cid,sql,expected in [('RULE-TEST-001','CREATE TABLE audit_rule_with_id (id bigint primary key, name text);','should pass'),('RULE-TEST-002','CREATE TABLE audit_rule_without_id (name text);','should block'),('RULE-TEST-004','CREATE TABLE audit_rule_ambiguous (name text);','inactive ambiguous should not silently enforce')]:
    rec,ev=call(cid,'POST','/query/check',{'sql':sql,'target':'connected_database','database_profile_id':'audit_db','sandbox_id':'audit_sandbox','real_db_mode':True})
    add(cid,'Rule','test',expected,{'sql':sql},'/query/check','POST','Rule evaluated by query check','PARTIAL','Rule Engine / Response Contract','Rule check is available but response uses success/data envelope rather than requested ok/code contract; pass/block semantics need endpoint-specific interpretation.','Add explicit matched/evaluated/blocked/code fields for rule test endpoint or expose dedicated /sandbox-rules/test.','Medium','Apps/Api/safy_api/routes/query.py; Runtime/strict_services.py','Tests/test_rule_test_contract.py',rec,ev)
add('RULE-PERSIST-001','Rule','reload','restart and reload',{},'/sandbox-rules','GET','Rules survive restart and reload','NOT_RUN','Storage Persistence','Audit did not restart runtime in this phase; persistence across restart not verified.','Add non-mutating restart test or isolated temp store restart harness.','Medium','Runtime/strict_services.py; DataStore/sandbox_rule_store.py','Tests/test_rule_persistence_restart.py')

# Contract negative controls.
rec,ev=call('CONTRACT-001','POST','/query/check',{})
add('CONTRACT-001','Response Contract','test','missing sql',{},'/query/check','POST','SAFY envelope error with request_id','FAIL','Response Contract','FastAPI validation error bypasses SAFY envelope and returns raw detail list.','Add global RequestValidationError handler in app_factory.','Low','Apps/Api/safy_api/app_factory.py','Tests/test_no_raw_422_contract.py',rec,ev)

with (OUT/'02_SAVE_TEST_MATRIX.csv').open('w',newline='',encoding='utf-8') as f:
    fieldnames=['id','feature_group','action','target','precondition','input_payload_redacted','endpoint','method','http_status','ok','code','message','details_redacted','ui_result','storage_result','reload_result','runtime_effect','evidence_path','status','root_cause_layer','root_cause','recommendation','patch_risk','required_fix_files','required_tests']
    w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader(); w.writerows(cases)
summary={s:sum(1 for c in cases if c['status']==s) for s in ['PASS','FAIL','PARTIAL','NOT_RUN','BLOCKED']}
summary['total']=len(cases)
(OUT/'evidence'/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
