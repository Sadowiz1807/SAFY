# SAFY Tool Registry and Reviewer Model

SAFY tools are described with schema metadata plus safety metadata:

- `risk_class`
- `read_only`
- `writes_database`
- `requires_sandbox`
- `requires_confirmation`
- `touches_secret`

The registry is inspired by Hermes' tool registry, but SAFY adds SQL-specific risk gates. The current runtime exposes `/agent/tools` for inspection.

Reviewer roles:

1. `policy_reviewer`: checks that READ_ONLY_SQL skips sandbox and WRITE/DDL cannot auto-execute.
2. `state_reviewer`: checks route context such as active database profile.
3. `result_reviewer`: checks display-only result policy and execution warnings.

Reviewer output is included in `workflow_review` and recorded in the workflow trace.
