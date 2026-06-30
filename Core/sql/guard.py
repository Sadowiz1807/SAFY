import re
from Core.sql.structural_parser import strip_literals_comments, split_statements, parse_create_table
from Core.rules.enforcer import enforce_sql

def check_sql(sql, rules=None):
    try:
        clean=strip_literals_comments(sql).lower(); reasons=[]; risk='low'
        stmts=split_statements(sql)
        if len(stmts)>1 and any(re.search(r'\b(drop|truncate|update|delete|alter|create)\b', strip_literals_comments(s), re.I) for s in stmts[1:]): reasons.append('multi-statement mutation'); risk='high'
        if re.search(r'\bupdate\b',clean) and ' where ' not in clean: reasons.append('UPDATE without WHERE')
        if re.search(r'\bdelete\s+from\b',clean) and ' where ' not in clean: reasons.append('DELETE without WHERE')
        er=enforce_sql(sql, rules or [])
        reasons += er.get('reasons',[])
        return {"success":True,"data":{"allowed":not reasons,"status":"pass" if not reasons else "block","reasons":reasons,"risk_level":risk,"parsed":parse_create_table(sql)},"error":None,"meta":{"request_id":"local-check"}}
    except Exception as e:
        return {"success":False,"data":None,"error":{"code":"SQL_CHECK_FAILED","message":"SQL could not be checked safely","details":{"type":type(e).__name__}},"meta":{"request_id":"local-check"}}
