from Core.nl.db_intent_parser import parse_db_intent
from Core.sql_generation.action_plan_to_sql import generate_sql
from Core.sql_generation.rule_constraints import constraints_from_rules
from Core.contracts import TaskFrame

class RunLoop:
    def run_chat(self, text, snapshot):
        plan=parse_db_intent(text)
        constraints=constraints_from_rules([r.get('dsl', r) for r in snapshot.rules.get('active', [])]) if snapshot else []
        sql=None; message=''
        if plan.intent == 'ambiguous': message='AMBIGUOUS_USER_REQUEST'
        elif plan.intent in ['create_table']:
            sql=generate_sql(plan,constraints); message='SQL draft generated.'
        elif plan.intent == 'research_then_schema_design': message='Planned research_then_schema_design; no execute.'
        else: message=f'Planned {plan.intent}.'
        execute_box={"sql": sql, "draft_ready": True, "summary": "Review generated SQL before Check Safety."} if sql else None
        return {"action_plan": plan.to_dict(), "sql": sql, "generated_sql": sql, "execute_box": execute_box, "message": message, "ui_patch": {"op":"merge","target":"execute","value":{"sql": sql or "","check": None}} if sql else None}
