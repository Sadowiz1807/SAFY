# Safy Tools Specification

## Purpose
Define Safy's tool contract, registry, executor, toolsets, and security rules.

## Scope
Covers BaseTool, ToolResult, ToolRegistry, ToolExecutor, risk/approval, toolsets, database tools, SQL tools, sandbox tools, audit tools, and tool security.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Tool System Overview
Tools are executable capabilities. Skills and LLM plans may request tool calls, but ToolExecutor and ToolRegistry decide whether a tool can run in the current context.

Rules:
- Tool calls must be validated by ToolRegistry and Permission Checker.
- Toolsets come from `Configs/toolsets.yaml`.
- Python wrappers must not declare additional tools independently.
- ToolResult must normalize success/error/risk/audit metadata.

## 2. BaseTool Contract
Required contract:

```python
class BaseTool:
    name: str
    description: str
    input_schema: dict
    risk_level: str
    requires_approval: bool

    async def run(self, input_data: dict, context: AgentExecutionContext) -> ToolResult:
        ...
```

## 3. ToolResult Contract
Required shape:

```json
{
  "success": true,
  "tool_name": "validate_sql_tool",
  "data": {},
  "error": null,
  "risk_level": "read_only",
  "audit_ref": "audit_...",
  "metadata": {}
}
```

Error shape:

```json
{
  "success": false,
  "tool_name": "execute_select_tool",
  "data": null,
  "error": {
    "code": "SQL_POLICY_BLOCKED",
    "message": "...",
    "details": {}
  },
  "risk_level": "destructive_schema",
  "audit_ref": null,
  "metadata": {}
}
```

## 4. ToolRegistry
ToolRegistry responsibilities:
- Load tools from YAML-defined toolsets.
- Register allowed tool metadata.
- Validate tool name exists.
- Validate tool is allowed by current SkillPolicy and target.
- Validate required approvals.
- Prevent direct provider execution bypass.

## 5. ToolExecutor
ToolExecutor responsibilities:
- Receive tool call request and AgentExecutionContext.
- Validate against ToolRegistry.
- Validate target and risk policy.
- Call SQL Guard/Risk Analyzer where applicable.
- Call audit tools before high-risk execution.
- Return normalized ToolResult.

## 6. Risk and Approval
Tool risk levels should align with SQL risk and action risk:
- low/read_only
- sandbox_mutation
- destructive_table_data
- destructive_schema
- admin_security_statement
- cross_database_or_server_level

Rules:
- Approval text alone is not enough to bypass policy.
- High-risk Manual SQL requires confirmation and audit pre-write.
- Agent connected database mutation remains blocked even with approval.

## 7. Toolsets
Required toolsets:

```txt
db_core
sandbox
sql_guard
manual_console
```

YAML source-of-truth example:

```yaml
toolsets:
  db_core:
    tools:
      - test_connection_tool
      - read_schema_tool
      - execute_select_tool
      - explain_query_tool
  sandbox:
    tools:
      - sandbox_health_tool
      - create_workspace_tool
      - execute_sandbox_sql_tool
      - inspect_workspace_tool
      - cleanup_workspace_tool
  sql_guard:
    tools:
      - generate_sql_tool
      - sanitize_identifier_tool
      - validate_sql_tool
      - risk_analyze_tool
      - apply_limit_tool
  manual_console:
    tools:
      - validate_sql_tool
      - risk_analyze_tool
      - execute_manual_sql_tool
      - write_audit_log_tool
```

## 8. Database Tools
Required database tools:
- `test_connection_tool`
- `read_schema_tool`
- `execute_select_tool`
- `explain_query_tool`

Rules:
- Connected database agent tools are read-only.
- `execute_select_tool` must reject non-SELECT and mutation statements.
- `explain_query_tool` must not mutate.
- Secrets resolved at runtime must not appear in ToolResult.

## 9. SQL Tools
Required SQL tools:
- `generate_sql_tool`
- `validate_sql_tool`
- `sanitize_identifier_tool`
- `apply_limit_tool`
- `risk_analyze_tool`

Rules:
- `validate_sql_tool` parses target dialect.
- `risk_analyze_tool` classifies statement risk.
- `apply_limit_tool` applies safe limits to row-returning SELECT.
- `sanitize_identifier_tool` blocks unsafe identifiers and reserved-key mistakes where possible.

## 10. Sandbox Tools
Required sandbox tools:
- `sandbox_health_tool`
- `create_workspace_tool`
- `execute_sandbox_sql_tool`
- `inspect_workspace_tool`
- `cleanup_workspace_tool`

Rules:
- PostgreSQL/MySQL sandbox uses Docker.
- SQLite runner only when target DBMS is SQLite.
- Workspace lock required for cleanup/mutation.
- Workspace object provenance must be recorded for created/dropped objects.

## 11. Audit Tools
Required audit tool:
- `write_audit_log_tool`

Recommended additional behavior:
- audit pre-write for high-risk operations.
- audit result update after execution.
- audit repair task when post-execution update fails.

## 12. Tool Security Rules
Rules:
- LLM cannot call arbitrary tools.
- Tool calls must pass compiled SkillPolicy.
- Tool calls must pass SQL Guard/Permission Checker when SQL is involved.
- ToolResult must not contain raw secrets.
- ToolResult must not persist raw SQL by default.
- Tools must not independently expand toolsets beyond YAML.
- Connected database write tools must not be available to agent workflows.

## Implementation Notes
Build ToolRegistry before implementing skills. Add tests that compare loaded Python tools against `Configs/toolsets.yaml` to prevent drift.

## Related Documents
- `01_ARCHITECTURE.md`
- `04_CONFIG_SPEC.md`
- `05_SECURITY_POLICY.md`
- `08_SKILLS_SPEC.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`
