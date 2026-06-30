from Core.contracts import RuntimeSnapshot
class ContextBuilder:
    def __init__(self, sessions, memory, sandbox, rules, skills): self.sessions=sessions; self.memory=memory; self.sandbox=sandbox; self.rules=rules; self.skills=skills
    def build(self, session_id, query=''):
        s=self.sessions.get_session(session_id); db=s.get('database_profile_id'); sb=s.get('sandbox_id')
        active_rules=[r for r in self.rules.list_rules(db,sb) if r.get('status') == 'active']
        return RuntimeSnapshot(session=s,database={"database_profile_id":db},sandbox=self.sandbox.get_status(db,sb),rules={"active":active_rules,"rules_version":self.rules.version(db,sb)},memory=self.memory.build(query),skills=self.skills.list(),model={"model":s.get('model')})
