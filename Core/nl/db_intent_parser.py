import re, unicodedata
from Core.contracts import ActionPlan

def _norm(s):
    s=s.strip().replace('đ','d').replace('Đ','D')
    s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    return s.lower()

def parse_db_intent(text):
    raw=text; s=_norm(text)
    if any(x in s for x in ['research','tim thong tin']) and any(x in s for x in ['schema','thiet ke']): return ActionPlan(intent='research_then_schema_design')
    if any(x in s for x in ['xoa bang','drop bang','drop table']):
        m=re.search(r'(?:xoa bang|drop bang|drop table)\\s+([a-zA-Z_][\w]*)',s); return ActionPlan(intent='drop_table',table=m.group(1) if m else None,risk_level='high',requires_confirmation=True)
    if 'them cot' in s:
        m=re.search(r'them cot\s+([a-zA-Z_][\w]*)\s+vao bang\s+([a-zA-Z_][\w]*)',s); return ActionPlan(intent='alter_table_add_column',table=m.group(2) if m else None,columns=[m.group(1)] if m else [])
    if any(x in s for x in ['cap nhat','update']): return ActionPlan(intent='update',risk_level='high',requires_confirmation=True)
    if re.search(r'\bxoa\b.*\bid\b|delete',s): return ActionPlan(intent='delete',risk_level='high',requires_confirmation=True)
    if any(x in s for x in ['xem bang','liet ke','select']): return ActionPlan(intent='select')
    if 'index' in s: return ActionPlan(intent='create_index')
    if 'khoa ngoai' in s: return ActionPlan(intent='alter_table_add_fk')
    if ('tao' in s and 'bang' in s) or 'create table' in s:
        m=re.search(r'tao(?:\s+cho\s+toi)?\s+bang\s+([a-zA-Z_][\w]*)',s); table=m.group(1) if m else None
        cols=[]
        if any(k in s for k in ['thuoc tinh','gom','cac cot','co ']):
            tail=re.split(r'thuoc tinh|gom|cac cot|\sco\s',s,maxsplit=1)[-1]
            if 'thuoc tinh' in tail:
                tail=tail.split('thuoc tinh',1)[1]
            tail=re.sub(r'\b(voi|va|add)\b', lambda x: ',' if x.group(1) in ['va'] else x.group(0), tail)
            parts=re.split(r'[,;]|\s+va\s+',tail)
            stop={'giup','toi','bang','thuoc','tinh','voi','gia','khong','am','nhung','khong','luu','password','tho'}
            for p in parts:
                tok=p.strip().split()[0] if p.strip() else ''
                if tok and tok not in stop and re.match(r'^[a-zA-Z_][\w]*$',tok): cols.append(tok)
        return ActionPlan(intent='create_table',table=table,columns=list(dict.fromkeys(cols)))
    if any(x in s for x in ['toi uu','chuan hon','phai chuan']): return ActionPlan(intent='ambiguous',clarification='AMBIGUOUS_USER_REQUEST')
    return ActionPlan(intent='chat')
