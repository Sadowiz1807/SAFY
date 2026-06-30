import re

def strip_literals_comments(sql):
    out=[]; i=0; n=len(sql); in_s=False
    while i<n:
        if not in_s and sql.startswith('--',i):
            j=sql.find('\n',i); out.extend(' '*(n-i if j<0 else j-i)); i=n if j<0 else j; continue
        if not in_s and sql[i]=='$':
            m=re.match(r'\$[A-Za-z_]*\$',sql[i:])
            if m:
                tag=m.group(0); j=sql.find(tag, i+len(tag))
                end=n if j<0 else j+len(tag); out.extend(' '*(end-i)); i=end; continue
        if sql[i]=="'": in_s=not in_s; out.append(' '); i+=1; continue
        out.append(' ' if in_s else sql[i]); i+=1
    return ''.join(out)

def split_statements(sql):
    clean=strip_literals_comments(sql); parts=[]; start=0
    for i,ch in enumerate(clean):
        if ch==';': parts.append(sql[start:i].strip()); start=i+1
    tail=sql[start:].strip()
    if tail: parts.append(tail)
    return [p for p in parts if strip_literals_comments(p).strip()]

def parse_create_table(sql):
    m=re.search(r'create\s+table\s+(?:if\s+not\s+exists\s+)?("[^"]+"|[\w.]+)\s*\((.*)\)',sql,re.I|re.S)
    if not m: return None
    body=m.group(2); cols=[]; constraints=[]; cur=''; depth=0; quote=False
    for ch in body:
        if ch=="'": quote=not quote
        if not quote and ch=='(': depth+=1
        if not quote and ch==')': depth-=1
        if ch==',' and depth==0 and not quote:
            item=cur.strip(); (constraints if re.match(r'(constraint|primary|foreign|check|unique)\b',item,re.I) else cols).append(item); cur=''
        else: cur+=ch
    if cur.strip():
        item=cur.strip(); (constraints if re.match(r'(constraint|primary|foreign|check|unique)\b',item,re.I) else cols).append(item)
    names=[]
    for c in cols:
        mm=re.match(r'("[^"]+"|[\w]+)',c); names.append(mm.group(1).strip('"') if mm else c)
    return {"table":m.group(1).strip('"'),"columns":names,"constraints":constraints,"raw_columns":cols}
