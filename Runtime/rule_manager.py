from Core.rules.semantic_compiler import compile_rule
class RuleManager:
    def __init__(self): self.rules={}; self.versions={}
    def key(self, db, sandbox): return f"{db or 'default'}::{sandbox or 'default'}"
    def list_rules(self, db=None, sandbox=None): return self.rules.get(self.key(db,sandbox), [])
    def save_rule(self, rule, db=None, sandbox=None):
        k=self.key(db,sandbox); item=dict(rule or {})
        raw=item.get('raw_text') or item.get('raw') or item.get('text') or ''
        item.setdefault('raw_text', raw); item['dsl']=compile_rule(raw); item['status']='active' if item['dsl'].get('active') else 'draft'
        if not item.get('rule_id'):
            item['rule_id'] = f"runtime_rule_{self.versions.get(k,0)+1}"
        self.rules.setdefault(k,[]).append(item); self.versions[k]=self.versions.get(k,0)+1; return {"rule":item,"rules_version":self.versions[k]}
    def disable_rule(self, rule_id, db=None, sandbox=None):
        k=self.key(db,sandbox)
        for r in self.rules.get(k,[]):
            if r.get('rule_id')==rule_id: r['status']='disabled'; self.versions[k]=self.versions.get(k,0)+1; return {"rule":r,"rules_version":self.versions[k]}
        return None
    def version(self, db=None, sandbox=None): return self.versions.get(self.key(db,sandbox),0)
