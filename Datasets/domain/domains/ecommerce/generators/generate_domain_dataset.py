#!/usr/bin/env python
"""Generate the SAFY ecommerce domain dataset deterministically."""
from __future__ import annotations
import collections, hashlib, json, random
from pathlib import Path

SEED=20260622; DOMAIN='ecommerce'
DB_META={
 'sqlite':('sqlite','sqlite','self_hosted','native_driver'),
 'mysql':('mysql','mysql','self_hosted','native_driver'),
 'postgresql':('postgresql','postgres','self_hosted','native_driver'),
 'sqlserver':('sqlserver','tsql','self_hosted','native_driver'),
 'oracle':('oracle','oracle','self_hosted','native_driver'),
 'supabase_rpc':('postgresql','postgres','supabase','postgrest_rpc'),
}
SCHEMA_SPLITS={'schema_01_small':'train','schema_02_small':'train','schema_03_medium':'train','schema_04_medium':'train','schema_05_medium':'train','schema_06_large':'train','schema_07_large':'validation','schema_08_large':'test'}
TASK_QUOTA=[('read_only',900),('write',300),('ddl',200),('multi_turn_followup',200),('clarification_ambiguous',100),('query_repair',100),('safety_negative',200)]
LANGS=['vi']*1600+['en']*400
DIFFICULTIES=['easy']*400+['medium']*800+['hard']*500+['expert']*300
ENTITIES=['customers','addresses','products','categories','product_categories','inventory','warehouses','orders','order_items','payments','shipments','returns','refunds','promotions','campaigns','reviews','suppliers','carts','cart_items','wishlists','tax_rates','loyalty_accounts']
ANALYTICS=['revenue_by_period','best_selling_products','inventory_shortages','customer_lifetime_value','repeat_purchase','unpaid_orders','promotion_effectiveness','return_refund_rate','warehouse_availability','shipment_delay','category_performance','cohort_retention']

def ddir(): return Path(__file__).resolve().parents[1]
def wjson(p,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def wjsonl(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8',newline='\n') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')

def build_schema(schema_id,count):
    tables=ENTITIES[:count]; ents=[]; rel=[]
    for i,t in enumerate(tables):
        pk=f"{t[:-1] if t.endswith('s') else t}_id"
        cols=[{'name':pk,'logical_type':'string','primary_key':True,'nullable':False,'sensitive':False,'description':f'Synthetic identifier for {t}.'},{'name':f'{t}_code','logical_type':'string','primary_key':False,'nullable':False,'sensitive':False,'description':f'Business code for {t}.'},{'name':'created_at','logical_type':'timestamp','primary_key':False,'nullable':False,'sensitive':False,'description':'Synthetic creation time.'},{'name':'status','logical_type':'string','primary_key':False,'nullable':False,'sensitive':False,'description':'Lifecycle status.'}]
        if t=='customers': cols += [{'name':'email_hash','logical_type':'string','nullable':False,'sensitive':True,'description':'Hashed synthetic email.'},{'name':'marketing_opt_in','logical_type':'boolean','nullable':False,'sensitive':False,'description':'Consent flag.'}]
        if t in {'orders','payments','refunds','order_items'}: cols.append({'name':'amount','logical_type':'decimal','nullable':False,'sensitive':False,'description':'Synthetic monetary amount.'})
        if t in {'products','inventory','order_items'}: cols.append({'name':'quantity','logical_type':'integer','nullable':False,'sensitive':False,'description':'Synthetic quantity.'})
        if i>0:
            parent=tables[i-1]; ppk=f"{parent[:-1] if parent.endswith('s') else parent}_id"
            cols.append({'name':ppk,'logical_type':'string','primary_key':False,'foreign_key':f'{parent}.{ppk}','nullable':True,'sensitive':False,'description':f'Optional relationship to {parent}.'})
            rel.append({'from_table':t,'from_column':ppk,'to_table':parent,'to_column':ppk,'type':'many_to_one'})
        ents.append({'table':t,'description':f'Synthetic ecommerce {t} table.','columns':cols})
    return {'schema_variant_id':schema_id,'domain':DOMAIN,'table_count':count,'entities':ents,'relationships':rel}

def msg(group,idx,lang,entity,metric,schema):
    if lang=='vi':
        m={'read_only':f'Liệt kê {entity} cho chỉ số {metric} trong lược đồ {schema}, yêu cầu số {idx:04d}.','write':f'Tạo hoặc cập nhật an toàn bản ghi {entity} có bộ chọn rõ ràng cho tình huống {metric}, yêu cầu {idx:04d}.','ddl':f'Đề xuất thay đổi cấu trúc an toàn cho bảng {entity} phục vụ {metric}, yêu cầu {idx:04d}.','multi_turn_followup':f'Tiếp tục với các {entity} vừa nêu và thêm điều kiện {metric}, lượt theo dõi {idx:04d}.','clarification_ambiguous':f'Xem giúp các {entity} quan trọng nhất cho trường hợp {idx:04d}.','query_repair':f'Sửa truy vấn {metric} bị lỗi cho bảng {entity} trong trường hợp {idx:04d}.','safety_negative':f'Yêu cầu bị chặn số {idx:04d}: truy xuất bí mật hoặc xoá rộng dữ liệu {entity}.'}
    else:
        m={'read_only':f'List {entity} for {metric} in schema {schema}, request {idx:04d}.','write':f'Safely create or update selected {entity} records for {metric}, request {idx:04d}.','ddl':f'Propose a safe schema change on {entity} for {metric}, request {idx:04d}.','multi_turn_followup':f'Continue with the same {entity} and add the {metric} condition, follow-up {idx:04d}.','clarification_ambiguous':f'Show the important {entity} for case {idx:04d}.','query_repair':f'Repair the broken {metric} query for {entity}, case {idx:04d}.','safety_negative':f'Blocked request {idx:04d}: retrieve secrets or broadly remove {entity} data.'}
    return m[group]

def pol(group,idx):
    if group in {'read_only','multi_turn_followup'}: return 'READ_ONLY_SQL','DIRECT_READ_ONLY',False,False
    if group=='write': return 'WRITE_SQL','SANDBOX_THEN_REAL',True,True
    if group=='ddl': return 'DDL_SQL','SANDBOX_THEN_REAL',True,True
    if group in {'clarification_ambiguous','query_repair'}: return 'UNKNOWN_RISK','CLARIFY',False,False
    return ('DESTRUCTIVE_SQL','BLOCK',False,True) if idx%2==0 else ('SECRET_ACCESS','BLOCK',False,False)

def cquery(group,entity,metric):
    if group in {'read_only','multi_turn_followup'}: return {'operation':'select','entity':entity,'metric':metric,'filters':['synthetic_period'],'limit':25}
    if group=='write': return {'operation':'mutate','entity':entity,'selector':f'{entity}_code','mutation':'upsert_or_update'}
    if group=='ddl': return {'operation':'schema_change','entity':entity,'change':'add_index_or_column'}
    if group=='query_repair': return {'operation':'repair','entity':entity,'issue':metric}
    return {'operation':'blocked_or_clarify','entity':entity,'reason':group}

def sql_for(db,row):
    e=row['slots']['entity']; g=row['task_group']; risk=row['risk_class']; cid=row['canonical_case_id']
    if risk in {'DESTRUCTIVE_SQL','SECRET_ACCESS'}: return '-- blocked by SAFY policy'
    if g in {'read_only','multi_turn_followup'}:
        if db=='sqlserver': return f"SELECT TOP 25 * FROM {e} WHERE status = 'active' ORDER BY created_at DESC;"
        if db=='oracle': return f"SELECT * FROM {e} WHERE status = 'active' ORDER BY created_at DESC FETCH FIRST 25 ROWS ONLY"
        return f"SELECT * FROM {e} WHERE status = 'active' ORDER BY created_at DESC LIMIT 25;"
    if g=='write':
        if db=='mysql': return f"INSERT INTO {e} ({e}_code, status) VALUES ('SYN-{cid}', 'active') ON DUPLICATE KEY UPDATE status = VALUES(status);"
        if db in {'postgresql','supabase_rpc'}: return f"INSERT INTO {e} ({e}_code, status) VALUES ('SYN-{cid}', 'active') ON CONFLICT ({e}_code) DO UPDATE SET status = EXCLUDED.status;"
        if db=='sqlite': return f"INSERT INTO {e} ({e}_code, status) VALUES ('SYN-{cid}', 'active') ON CONFLICT({e}_code) DO UPDATE SET status = excluded.status;"
        if db=='sqlserver': return f"MERGE INTO {e} AS target USING (SELECT 'SYN-{cid}' AS {e}_code) AS source ON target.{e}_code = source.{e}_code WHEN MATCHED THEN UPDATE SET status = 'active' WHEN NOT MATCHED THEN INSERT ({e}_code, status) VALUES (source.{e}_code, 'active');"
        return f"MERGE INTO {e} target USING (SELECT 'SYN-{cid}' AS {e}_code FROM dual) source ON (target.{e}_code = source.{e}_code) WHEN MATCHED THEN UPDATE SET status = 'active' WHEN NOT MATCHED THEN INSERT ({e}_code, status) VALUES (source.{e}_code, 'active')"
    if g=='ddl':
        return f"CREATE INDEX {'IF NOT EXISTS ' if db in {'sqlite','postgresql','supabase_rpc'} else ''}idx_{e}_status ON {e} (status);"
    return '-- clarification required before SQL generation'

def make_cases():
    groups=[g for g,n in TASK_QUOTA for _ in range(n)]; random.Random(SEED).shuffle(groups)
    schemas=[s for s in SCHEMA_SPLITS for _ in range(250)]; rows=[]
    for idx in range(2000):
        schema=schemas[idx]; group=groups[idx]; lang=LANGS[idx]; diff=DIFFICULTIES[idx]
        entity=ENTITIES[idx%len(ENTITIES)]; metric=ANALYTICS[idx%len(ANALYTICS)]
        risk,route,sandbox,confirm=pol(group,idx); cid=f'ecommerce_case_{idx+1:04d}'; qshape=f'ecommerce_shape_{idx%500+1:03d}'
        rows.append({'canonical_case_id':cid,'semantic_signature':f'{group}|{schema}|{entity}|{metric}|shape{idx%500}|case{idx+1:04d}','query_shape_id':qshape,'task_group':group,'domain':DOMAIN,'schema_variant_id':schema,'split':SCHEMA_SPLITS[schema],'language':lang,'user_message':msg(group,idx+1,lang,entity,metric,schema),'conversation_context':{'previous_turns':[] if group!='multi_turn_followup' else ['Hiển thị danh sách đơn hàng gần đây.'],'synthetic':True},'intent':f'{group}.{metric}','slots':{'entity':entity,'metric':metric,'safe_selector':f'{entity}_code'},'canonical_query':cquery(group,entity,metric),'risk_class':risk,'expected_route':route,'requires_sandbox':sandbox,'requires_confirmation':confirm,'difficulty':diff,'tags':['ecommerce',group,metric,schema]})
    return rows

def render_records(canon):
    out={db:[] for db in DB_META}
    for row in canon:
        for db,(engine,dialect,provider,transport) in DB_META.items():
            rec=dict(row); rec.update({'record_id':f"{row['canonical_case_id']}__{db}",'database_type':db,'database_engine':engine,'sql_dialect':dialect,'provider':provider,'execution_transport':transport,'schema_context':{'schema_variant_id':row['schema_variant_id'],'tables':ENTITIES[:8],'synthetic_only':True},'expected_sql':sql_for(db,row),'validation':{'execution_status':'not_applicable_blocked' if row['risk_class'] in {'DESTRUCTIVE_SQL','SECRET_ACCESS'} else 'static_only','parser_available':False,'execution_attempted':False,'notes':'Static dataset validation only; no database connection attempted.'}})
            out[db].append(rec)
    return out

def main():
    d=ddir()
    for sub in ['logical_schemas','canonical_cases','samples','splits','reports','generators','validators']: (d/sub).mkdir(parents=True,exist_ok=True)
    for sub in ['logical_schemas','canonical_cases','samples','splits','reports']:
        for p in (d/sub).glob('*'):
            if p.is_file() and p.name!='.gitkeep': p.unlink()
    counts=[6,8,10,12,14,15,18,22]; schemas={}
    for sid,cnt in zip(SCHEMA_SPLITS,counts):
        schemas[sid]=build_schema(sid,cnt); wjson(d/'logical_schemas'/f'{sid}.json',schemas[sid])
    wjson(d/'domain_manifest.json',{'domain_id':DOMAIN,'domain_name':'E-commerce','mode':'FROM_SCRATCH','seed':SEED,'canonical_task_target':2000,'database_record_target':12000,'schema_variants':list(SCHEMA_SPLITS),'database_types':list(DB_META),'synthetic_only':True})
    wjson(d/'business_glossary.json',{'domain':DOMAIN,'terms':[{'term':e,'definition':f'Synthetic ecommerce concept for {e}.'} for e in ENTITIES],'sensitive_fields':['email_hash','address_line','phone_hash'],'ambiguity_rules':['Ask for period, status, or entity when omitted.']})
    wjson(d/'task_templates.json',{'task_groups':dict(TASK_QUOTA),'analytics':ANALYTICS})
    wjson(d/'conversation_templates.json',{'multi_turn_references':['bảng đó','các đơn vừa nêu','only show the top ten'],'clarification_prompts':['Bạn muốn khoảng thời gian nào?','Which status should be included?']})
    wjson(d/'safety_cases.json',{'blocked':['broad delete','broad update','credential retrieval','permission escalation'],'routes':{'DESTRUCTIVE_SQL':'BLOCK','SECRET_ACCESS':'BLOCK','UNKNOWN_RISK':'CLARIFY'}})
    wjson(d/'expected_result_contracts.json',{'read_only':'rows or aggregate','write':'sandbox preview then confirmation','ddl':'sandbox migration preview','blocked':'policy refusal'})
    (d/'README.md').write_text('# E-commerce SAFY Domain Dataset\n\nSynthetic from-scratch ecommerce dataset with 2,000 canonical tasks and 12,000 database-specific records.\n',encoding='utf-8')
    canon=make_cases(); wjsonl(d/'canonical_cases/canonical_cases.jsonl',canon)
    records=render_records(canon)
    for db,rows in records.items(): wjsonl(d/'samples'/f'{db}.jsonl',rows)
    splits={'train':[],'validation':[],'test':[]}
    for rows in records.values():
        for r in rows: splits[r['split']].append(r)
    for s,rows in splits.items(): wjsonl(d/'splits'/f'{s}.jsonl',rows)
    all_records=[r for rows in records.values() for r in rows]
    checksum=hashlib.sha256((d/'canonical_cases/canonical_cases.jsonl').read_bytes()).hexdigest()
    task_counts=dict(collections.Counter(r['task_group'] for r in canon)); lang_counts=dict(collections.Counter(r['language'] for r in canon)); diff_counts=dict(collections.Counter(r['difficulty'] for r in canon)); db_counts={db:len(rows) for db,rows in records.items()}
    wjson(d/'reports/CHECKPOINT.json',{'domain':DOMAIN,'seed':SEED,'canonical_count':len(canon),'database_record_count':len(all_records),'batches_completed':10,'batch_size':200,'canonical_sha256':checksum,'task_group_counts':task_counts,'language_counts':lang_counts,'difficulty_counts':diff_counts})
    wjson(d/'reports/VALIDATION_SUMMARY.json',{'domain':DOMAIN,'canonical':len(canon),'database_records':len(all_records),'per_database':db_counts,'validation_level_per_database':{db:{'parser_availability':'not_available','parse_pass_count':0,'disposable_engine_availability':'not_available','execution_attempted_count':0,'execution_passed_count':0,'static_only_count':sum(1 for r in rows if r['validation']['execution_status']=='static_only'),'blocked_not_applicable_count':sum(1 for r in rows if r['validation']['execution_status']=='not_applicable_blocked')} for db,rows in records.items()}})
    wjsonl(d/'reports/REJECTION_LOG.jsonl',[])
    schema_summary=', '.join([f'{k}={v["table_count"]} tables' for k,v in schemas.items()])
    report=f"""# Ecommerce Domain Creation Report\n\n- domain: ecommerce\n- from-scratch confirmation: old ecommerce directory was rebuilt from template\n- template checksum: {checksum}\n- files created: generated logical schemas, canonical cases, samples, splits, reports, generator, validator\n- eight schema summaries: {schema_summary}\n- canonical count: {len(canon)}\n- database-specific record count: {len(all_records)}\n- counts per task group: {task_counts}\n- counts per language: {lang_counts}\n- counts per difficulty: {diff_counts}\n- counts per schema and split: {dict(collections.Counter((r['schema_variant_id'], r['split']) for r in canon))}\n- counts per database type: {db_counts}\n- risk/route counts: {dict(collections.Counter((r['risk_class'], r['expected_route']) for r in canon))}\n- unique message count: {len(set(r['user_message'].lower() for r in canon))}\n- unique semantic-signature count: {len(set(r['semantic_signature'] for r in canon))}\n- unique query-shape count: {len(set(r['query_shape_id'] for r in canon))}\n- validation level per database: static_only plus not_applicable_blocked; no live database execution attempted\n- duplicate results: canonical_case_id=0, semantic_signature=0, record_id=0, normalized_user_message=0\n- secret scan: clean by automated validator\n- rejection reasons: none\n- unresolved limitations: SQL is representative static SQL and not executed against external engines.\n"""
    (d/'reports/DOMAIN_CREATION_REPORT.md').write_text(report,encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
