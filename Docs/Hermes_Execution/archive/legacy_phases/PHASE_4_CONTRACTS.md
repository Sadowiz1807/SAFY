# Phase 4 Contracts

## `/agent/chat` Request

```json
{
  "chat_id": "optional-string",
  "message": "create database for an online store",
  "model_profile_id": "optional-string",
  "database_profile_id": null,
  "target": "sandbox",
  "options": {"return_sql": false, "dialect": "sqlite|postgresql|mysql"}
}
```

Rules:

- `target` must be `sandbox` for create_database in Phase 4.
- `database_profile_id` must not enable connected execution in Phase 4.
- Raw secrets are never accepted in this request.

## `/agent/chat` Response Envelope

All `/agent/chat` responses must use the standard Safy envelope: `success`, `data`, `error`, `meta`.

```json
{
  "success": true,
  "data": {
    "chat_id": "chat_...",
    "workflow_id": "wf_...",
    "intent": "create_database",
    "assumptions": ["Domain not provided; using default e-commerce domain."],
    "workspace_id": "ws_...",
    "risk_level": "sandbox_schema_change",
    "summary": "Created a sandbox e-commerce schema.",
    "technical_result": {
      "target": "sandbox",
      "dialect": "sqlite",
      "tables": [],
      "relationships": [],
      "validation": {"sql_guard": "passed", "schema_readback": "passed"},
      "sql_returned": false
    }
  },
  "error": null,
  "meta": {
    "request_id": "req_...",
    "duration_ms": 0,
    "provider": "mock|configured",
    "redaction": "applied"
  }
}
```

Error responses also use the same envelope with `success: false`, `data: null`, structured `error`, and redacted `meta`.

No raw API key, DB password, token, connection string, provider prompt secret, or unredacted credential value may appear in `data`, `error`, or `meta`.

## Agent Core Interfaces

- `AgentExecutionContext`: chat_id, workflow_id, user_message, target, profile refs, options, redaction context.
- `IntentResult`: intent, confidence, missing_critical_fields, assumptions, blocked_reason.
- `PlanStep`: step_id, tool_name, inputs_ref, policy_requirements, produces.
- `AgentResult`: summary, technical_result, workspace_id, audit_refs, errors.

## Provider Contracts

- `ProviderRegistry` resolves configured provider profile without exposing raw secret values.
- `ModelClient.generate_structured()` accepts schema-bound prompts and returns parsed untrusted output.
- `MockProvider` is required for deterministic tests.
- Real transports are disabled until secrets/profile integration and network behavior are explicitly implemented.

## Skill Contracts

- `SkillManifest`: name, version, intents, input_schema, output_schema, required_toolsets, denied_targets, policy_rules.
- `SkillRouter`: maps `create_database` to Create_database skill only.
- `SkillPolicy`: deterministic compiled policy with allowed tools, allowed targets, denied tools/patterns, sandbox-only flag, SQL Guard requirement, audit requirement, max steps, timeout, and redaction profile.

## Tool Contracts

- `ToolRegistry`: registers exact callable tools by name.
- `ToolExecutor`: checks SkillPolicy, validates target, redacts input/output, calls SQL Guard for SQL, records audit, and blocks unknown tools.
- Tool outputs are structured and never include secrets.

## Create Database Toolset

Allowed Phase 4 tools:

- `sanitize_identifier_tool`
- `validate_sql_tool`
- `create_workspace_tool`
- `execute_sandbox_sql_tool`
- `read_schema_tool`
- `summarize_schema_tool`
- `record_agent_audit_tool`

Denied Phase 4 tools:

- connected database DDL/DML execution
- connected database read-only agent query execution
- credential privilege probing
- Docker host/network privileged actions
- direct SQL execution outside ToolExecutor
