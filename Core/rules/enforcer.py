import re
from Core.rules.semantic_compiler import compile_rule, canonical_type


def _parse_columns(sql):
    from Core.sql.structural_parser import parse_create_table
    parsed = parse_create_table(sql) or {}
    columns = [str(c).lower() for c in parsed.get('columns', [])]
    column_types = {}
    # Lightweight local extraction for type checks; structural parser in this slice
    # returns names only, so extract top-level CREATE TABLE body safely enough for tests.
    m = re.search(r'\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?[\w".]+\s*\((.*)\)\s*;?\s*$', sql, re.I | re.S)
    if m:
        body = m.group(1)
        depth = 0; cur = [] ; parts=[]; quote=None
        for ch in body:
            if quote:
                cur.append(ch)
                if ch == quote: quote = None
                continue
            if ch in {'"', "'", '`'}:
                quote = ch; cur.append(ch); continue
            if ch == '(': depth += 1
            elif ch == ')' and depth: depth -= 1
            if ch == ',' and depth == 0:
                parts.append(''.join(cur)); cur=[]
            else: cur.append(ch)
        if cur: parts.append(''.join(cur))
        for part in parts:
            toks = part.strip().split()
            if len(toks) >= 2 and toks[0].lower().strip('"`[]') not in {'constraint','primary','foreign','unique','check'}:
                col = toks[0].lower().strip('"`[]')
                dtype = canonical_type(' '.join(toks[1:3]))
                if dtype: column_types[col] = dtype
    return columns, column_types


def enforce_sql(sql, rules):
    low=sql.lower(); reasons=[]
    columns, column_types = _parse_columns(sql)
    for r in rules:
        if isinstance(r,str): r=compile_rule(r)
        k=r.get('kind')
        if k=='operation_forbidden' and r.get('operation')=='DROP_TABLE' and re.search(r'\bdrop\s+table\b',low): reasons.append('DROP_TABLE forbidden')
        if k=='operation_forbidden' and r.get('operation')=='TRUNCATE_TABLE' and re.search(r'\btruncate\b',low): reasons.append('TRUNCATE_TABLE forbidden')
        if k=='row_mutation_guard' and r.get('operation')=='UPDATE' and re.search(r'\bupdate\b',low) and ' where ' not in low: reasons.append('UPDATE without WHERE')
        if k=='row_mutation_guard' and r.get('operation')=='DELETE' and re.search(r'\bdelete\s+from\b',low) and ' where ' not in low: reasons.append('DELETE without WHERE')
        if k=='required_column_on_create_table' and 'create table' in low:
            if r.get('column','').lower() not in columns:
                reasons.append(f"missing {r.get('column')}")
        if k=='column_type_required' and 'create table' in low:
            col = str(r.get('column') or '').lower()
            required = canonical_type(r.get('data_type') or '')
            actual = column_types.get(col)
            if not actual:
                reasons.append(f"missing {col}")
            elif required and canonical_type(actual) != required:
                reasons.append(f"column {col} must be {required}")
        if k=='required_primary_key_on_create_table' and 'create table' in low and 'primary key' not in low: reasons.append('missing primary key')
        if k=='column_forbidden' and r.get('column','').lower() in low: reasons.append(f"forbidden column {r.get('column')}")
    return {"allowed":not reasons,"status":"pass" if not reasons else "block","reasons":reasons}
