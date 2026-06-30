class ToolPlanner:
    def plan_tools(self, action_plan, skills=None):
        if action_plan.intent == 'research_then_schema_design': return ['web_research','sql_draft_generation']
        if action_plan.intent in ['create_table','alter_table_add_column','create_index','alter_table_add_fk']: return ['sql_draft_generation','sandbox_check']
        return []
