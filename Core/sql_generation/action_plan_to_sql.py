from Core.rules.semantic_compiler import canonical_type


def generate_sql(plan, constraints=None):
    constraints=constraints or []
    if getattr(plan,'intent',None)!='create_table': return None
    cols=list(getattr(plan,'columns',[]) or [])
    low=[c.lower() for c in cols]
    type_constraints={}
    need_pk=any(c.get('kind')=='required_primary_key_on_create_table' for c in constraints if isinstance(c,dict))
    for c in constraints:
        if not isinstance(c,dict):
            continue
        if c.get('kind')=='required_column_on_create_table':
            col=c.get('column','id')
            if col.lower() not in low:
                cols.insert(0 if col=='id' else len(cols), col); low.append(col.lower())
        if c.get('kind')=='column_type_required':
            col=str(c.get('column') or '').lower()
            dtype=canonical_type(c.get('data_type') or '')
            if col and dtype:
                type_constraints[col]=dtype
                if col not in low:
                    cols.insert(0 if col=='id' else len(cols), col); low.append(col)
    if 'id' not in low and need_pk: cols.insert(0,'id'); low.insert(0,'id')
    defs=[]
    for c in cols:
        lc=c.lower()
        dtype=type_constraints.get(lc)
        if lc=='id': defs.append(f'id {dtype or "bigint"} PRIMARY KEY')
        elif lc in ['created_at','updated_at']: defs.append(f'{c} {dtype or "timestamptz"} NOT NULL DEFAULT now()')
        else: defs.append(f'{c} {dtype or "text"}')
    if need_pk and not any('primary key' in d.lower() for d in defs): defs.insert(0,'id bigint PRIMARY KEY')
    return f"CREATE TABLE {plan.table or 'new_table'} (" + ', '.join(defs) + ');'
