from .action_plan_to_sql import generate_sql
def repair(plan, constraints=None, sql=None): return sql or generate_sql(plan,constraints)
