class SkillRegistry:
    DEFAULT=['web_research','file_context_retrieval','database_introspection','schema_graph','sql_draft_generation','sandbox_check','rule_compile','rule_validate','package_build','audit_write']
    def __init__(self): self.skills={n:{"name":n,"input_schema":{"type":"object"},"output_schema":{"type":"object"},"risk_level":"low","requires_confirmation": n in ['sandbox_check','package_build']} for n in self.DEFAULT}
    def list(self): return list(self.skills.values())
    def get(self,name): return self.skills.get(name)
    def validate_call(self,name,args):
        if name not in self.skills: return {"ok":False,"error":{"code":"UNKNOWN_SKILL"}}
        if not isinstance(args,dict): return {"ok":False,"error":{"code":"INVALID_SKILL_INPUT"}}
        return {"ok":True}
