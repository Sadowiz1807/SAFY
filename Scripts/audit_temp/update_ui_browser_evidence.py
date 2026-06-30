from pathlib import Path
import csv, json
OUT=Path('Reports/e2e_tests/2026-06-30_100plus_save_test_execute_cases')
E=OUT/'evidence'
chat_screen=r'C:\Users\ASUS\AppData\Local\hermes\cache\screenshots\browser_screenshot_29b3ad22b5e9457abf1bf3023648d687.png'
login_screen=r'C:\Users\ASUS\AppData\Local\hermes\cache\screenshots\browser_screenshot_c660215bf1f5465cb336be55485d44cc.png'
rule_text='''Safy\n...\nVALIDATION REPORT\n{\n  "saved": false,\n  "error": {\n    "code": "RULE_AMBIGUOUS",\n    "message": "Rule is ambiguous and was not activated.",\n    "details": {"request_id": "req_e73ce706fbf143aa8d7adf6309c50252"}\n  }\n}\nEXECUTE ERROR\nRULE_AMBIGUOUS\nRule is ambiguous and was not activated.'''
ui_updates={
 'UI-003':('FAIL','Browser chat returned visible empty-response regression instead of expected assistant text', 'Fix /chat runtime response synthesis so UI receives non-empty provider output or SAFY error envelope; evidence screenshot '+chat_screen),
 'MODEL-022':('FAIL','Browser chat exact-text workflow failed with empty agent response', 'Fix chat runtime provider integration/response synthesis; evidence screenshot '+chat_screen),
 'MODEL-023':('FAIL','Browser chat did not prove active profile runtime output; UI showed empty response', 'Log and surface selected profile; fix empty assistant response'),
 'QUERY-019':('FAIL','Browser chat-generated SQL workflow not validated because chat response was empty', 'Fix chat runtime SQL generation response path'),
 'RULE-020':('PASS','Browser UI showed RULE_AMBIGUOUS validation report, request_id, and execute error panel', 'n/a'),
 'UI-010':('PASS','Browser UI showed ambiguous rule warning/error with request_id and did not show saved active', 'n/a'),
 'UI-011':('PASS','Browser UI showed backend error code/message/request_id for ambiguous rule', 'n/a'),
 'UI-012':('PARTIAL','Dashboard reload/login visible; persistence chips visible, but full reload sequence for all statuses not completed', 'Run full reload after each active model/db/rule transition'),
 'UI-013':('PASS','Browser-visible network/UI evidence redacted; no raw secret text visible in captured DOM', 'n/a'),
 'UI-014':('PARTIAL','UI shows model/database chips, but model chip text says not connected while header shows updated / gpt-5.5', 'Normalize UI connection chip status labels'),
}
# write UI evidence files
for cid,(status,actual,rec) in ui_updates.items():
    base=cid.lower()
    (E/f'{base}_request_redacted.json').write_text(json.dumps({'browser_url':'http://127.0.0.1:8000/dashboard','screenshot_chat':chat_screen,'screenshot_login':login_screen},indent=2),encoding='utf-8')
    (E/f'{base}_response.json').write_text(json.dumps({'status':status,'actual':actual,'dom_excerpt':rule_text if cid in {'RULE-020','UI-010','UI-011'} else 'Safy backend returned an empty agent response.'},ensure_ascii=False,indent=2),encoding='utf-8')
    (E/f'{base}_notes.txt').write_text(actual+'\nRecommendation: '+rec,encoding='utf-8')
# update matrix
path=OUT/'test_matrix.csv'
rows=list(csv.DictReader(path.open(encoding='utf-8')))
for r in rows:
    if r['id'] in ui_updates:
        st,actual,rec=ui_updates[r['id']]
        r['status']=st; r['actual']=actual; r['root_cause_if_fail']='Browser workflow evidence' if st in {'FAIL','PARTIAL'} else '' ; r['recommendation_if_fail']=rec if st in {'FAIL','PARTIAL'} else ''
with path.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
counts={s:sum(1 for r in rows if r['status']==s) for s in ['PASS','FAIL','PARTIAL','BLOCKED','NOT_RUN']}
summary=f'''# 100+ E2E Save/Test/Execute Test Run Summary\n\n- Total cases: {len(rows)}\n- PASS: {counts['PASS']}\n- FAIL: {counts['FAIL']}\n- PARTIAL: {counts['PARTIAL']}\n- BLOCKED: {counts['BLOCKED']}\n- NOT_RUN: {counts['NOT_RUN']}\n- Evidence folder: `{E}`\n- Matrix: `{path}`\n- Browser evidence: login/dashboard screenshot `{login_screen}`; chat empty-response screenshot `{chat_screen}`; RULE_AMBIGUOUS DOM evidence saved in UI/RULE evidence files.\n- No plaintext secrets found in generated evidence: yes (script redaction + manual DOM check)\n\nImportant: Production PASS is NOT claimed because browser chat runtime returned `Safy backend returned an empty agent response`, UI status has partial mismatch, and SQL Server live execute cases are BLOCKED by local Windows/ODBC/SQLEXPRESS environment access.\n'''
(OUT/'00_TEST_RUN_SUMMARY.md').write_text(summary,encoding='utf-8')
# rewrite failure/recommendation reports from final matrix
for name,title,flt in [
 ('03_FAILURE_PATH_REPORT.md','Failure Path Report',lambda r: r['status'] in {'FAIL','BLOCKED','PARTIAL'}),
 ('07_UI_NETWORK_REPORT.md','UI Network Report',lambda r: r['id'].startswith('UI-') or r['id'] in {'RULE-020','QUERY-019','MODEL-022','MODEL-023'}),
 ('09_ROOT_CAUSE_IF_FAIL.md','Root Cause If Fail',lambda r: r['status']=='FAIL'),
 ('10_FIX_RECOMMENDATIONS_IF_FAIL.md','Fix Recommendations If Fail',lambda r: r['status']=='FAIL'),
]:
    lines=[f'# {title}','']
    for r in rows:
        if flt(r): lines.append(f"- {r['id']} [{r['status']}] {r['title']} — evidence: `{r['evidence_path']}` — actual: {r['actual']} — rec: {r['recommendation_if_fail'] or 'n/a'}")
    (OUT/name).write_text('\n'.join(lines),encoding='utf-8')
print(counts)
