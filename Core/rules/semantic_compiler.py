import re, unicodedata

IDENTIFIER_ALIASES = {"id", "identifier", "ma dinh danh", "ma_dinh_danh", "khoa dinh danh", "khoa_dinh_danh", "dinh danh"}
TYPE_ALIASES = {
    "float": "float", "double": "double precision", "double precision": "double precision", "real": "real",
    "bigint": "bigint", "int8": "bigint", "integer": "integer", "int": "integer", "int4": "integer",
    "text": "text", "string": "text", "varchar": "varchar", "uuid": "uuid", "boolean": "boolean", "bool": "boolean",
    "timestamp": "timestamp", "timestamptz": "timestamptz", "date": "date", "numeric": "numeric", "decimal": "numeric",
}

def norm(s):
    s=str(s or '').replace('đ','d').replace('Đ','D')
    s=''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
    s=re.sub(r'[`"\[\]{}()]+',' ',s)
    s=re.sub(r'[^a-z0-9_\.]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def canonical_column(value):
    v=norm(value).replace('_',' ')
    if v in IDENTIFIER_ALIASES:
        return ('id','identifier')
    if v in {'mail','email','email address','dia chi email'}:
        return ('email','email')
    if v in {'created at','created_at','ngay tao'}:
        return ('created_at','created_timestamp')
    if v in {'updated at','updated_at','ngay cap nhat'}:
        return ('updated_at','updated_timestamp')
    return (v.replace(' ','_'), v.replace(' ','_'))

def canonical_type(value):
    raw=norm(value).replace('_',' ')
    # Prefer longest known type prefix so "float." / "float type" still works.
    for alias in sorted(TYPE_ALIASES, key=len, reverse=True):
        if raw == alias or raw.startswith(alias + ' '):
            return TYPE_ALIASES[alias]
    return raw.split()[0] if raw else ''

def compile_rule(text):
    s=norm(text)
    raw=text
    def d(kind, **kw): return {"active": True, "kind": kind, **kw, "raw": raw}

    # Column type constraints must be parsed before generic "id required" rules.
    m=re.search(r'^(?:cot\s+|truong\s+)?(id|identifier|ma\s+dinh\s+danh|khoa\s+dinh\s+danh|[a-z_][\w]*)\s+(?:phai\s+co|can\s+co|bat\s+buoc\s+co|phai\s+dung|can\s+dung|bat\s+buoc\s+dung)?\s*(?:kieu\s+(?:du\s+lieu\s+)?(?:la|=)?|type\s*(?:is|=)?|data\s+type\s*(?:is|=)?)\s+([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})', s)
    if m:
        col, sem = canonical_column(m.group(1))
        dtype = canonical_type(m.group(2))
        return d('column_type_required', scope='all_tables', column=col, semantic=sem, data_type=dtype)

    # English/Vietnamese variants: "id là float", "id should be float".
    m=re.search(r'^(id|identifier|ma\s+dinh\s+danh|khoa\s+dinh\s+danh)\s+(?:la|=|is|should\s+be|must\s+be)\s+([a-z_][\w]*(?:\s+[a-z_][\w]*){0,2})$', s)
    if m:
        col, sem = canonical_column(m.group(1))
        return d('column_type_required', scope='all_tables', column=col, semantic=sem, data_type=canonical_type(m.group(2)))

    if any(x in s for x in ['khong duoc xoa bang','cam huy bang']) or re.search(r'\b(drop\s+table|xoa\s+bang|huy\s+bang)\b',s):
        return d('operation_forbidden',operation='DROP_TABLE')
    if any(x in s for x in ['lam rong bang','truncate bang']) or re.search(r'\btruncate\b',s):
        return d('operation_forbidden',operation='TRUNCATE_TABLE')
    if 'update khong co where' in s: return d('row_mutation_guard',operation='UPDATE')
    if 'delete khong co where' in s: return d('row_mutation_guard',operation='DELETE')
    if 'khoa chinh' in s or 'primary key' in s: return d('required_primary_key_on_create_table',scope='all_new_tables')
    if any(x in s for x in ['created_at','ngay tao']): return d('required_column_on_create_table',scope='all_new_tables',column='created_at',semantic='created_timestamp')
    if any(x in s for x in ['updated_at','ngay cap nhat']): return d('required_column_on_create_table',scope='all_new_tables',column='updated_at',semantic='updated_timestamp')
    if any(x in s for x in ['ma dinh danh','identifier']) or re.search(r'\b(id)\b',s):
        return d('required_column_on_create_table',scope='all_new_tables',column='id',semantic='identifier')
    m=re.search(r'(?:bang\s+)?([a-zA-Z_][\w]*)\s+khong duoc co\s+([a-zA-Z_][\w]*)',s)
    if m and m.group(1) not in {'moi','deu','nao','cung','tat','ca','bat','ky','bang'}: return d('column_forbidden',table=m.group(1),column=m.group(2))
    m=re.search(r'(?:bang\s+|trong bang\s+)?([a-zA-Z_][\w]*)\s+(?:phai co|can co|bat buoc co)\s+(?:cot\s+)?([a-zA-Z_][\w]*)',s)
    if m and m.group(1) not in {'moi','deu','nao','cung','tat','ca','bat','ky','bang'}:
        col,_sem=canonical_column(m.group(2)); return d('column_required',table=m.group(1),column=col,semantic=_sem)
    m=re.search(r'(?:database phai co bang|bat buoc ton tai bang)\s+([a-zA-Z_][\w]*)',s)
    if m: return d('table_required',table=m.group(1))
    if 'snake_case' in s: return {"active": False, "kind": "naming_convention", "style": "snake_case", "status": "warning", "raw": raw}
    return {"active": False, "kind": "ambiguous", "raw": raw}
