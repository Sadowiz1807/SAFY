# Safy Config Specification

## Purpose
Define all required configuration files and defaults so implementation does not guess policy or runtime behavior.

## Scope
Covers `app.yaml`, `skills.yaml`, `toolsets.yaml`, `policies.yaml`, `.env.example`, `.gitignore`, loading order, and override rules.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Config Overview
Safy configuration must be explicit and policy-first. YAML config defines app behavior, skill routing, toolsets, and execution policies. Environment variables hold raw secrets.

Required config files:

```txt
Configs/app.yaml
Configs/skills.yaml
Configs/toolsets.yaml
Configs/policies.yaml
.env.example
.gitignore
```

## 2. app.yaml
Required sections:

```yaml
app:
  name: safy
  version: 1.0.0
  mode: local_dev

server:
  host: 127.0.0.1
  port: 8000

frontend:
  dev_url: http://localhost:3000

chat:
  lazy_create_chat_id: true
  allow_recovery: true

runtime:
  runtime_schema_version: 1
  audit_schema_version: 1
  workspace_ttl_minutes: 120

data:
  user_profiles_path: Data/User/user_profiles.json
  database_profiles_path: Data/Database_management/database_profiles.json
  runtime_db_path: Data/safy_runtime.db
  audit_db_path: Data/safy_audit.db

secrets:
  resolver: env
  allow_secrets_in_response: false

sandbox:
  postgres_mysql_runner: docker
  sqlite_runner_enabled: true
  one_container_many_workspaces: true
  cleanup_requires_lock: true

query:
  default_limit: 100
  max_limit: 1000
  timeout_seconds: 30

business_rule_engine:
  enabled: true
  require_constraints_for_major_tables: true
  require_fk_for_dependent_entities: true

audit:
  mask_sql_literals: true
  store_statement_hash: true
  store_redacted_sql: true
  store_raw_sql: false

agent:
  connected_database_mode: read_only
  sandbox_write_enabled: true
```

## 3. skills.yaml
`skills.yaml` indexes document-driven skill packs. Each built-in skill uses
`Skills/<skill_name>/SKILL.md`; optional references stay inside the same skill
directory and load lazily only when the skill is selected.

Example:

```yaml
skills_root: Skills
skill_filename: SKILL.md
enable_legacy_skill_loading: false
skills:
  create_database:
    path: Skills/create_database
    status: active
  text_to_sql:
    path: Skills/text_to_sql
    status: active
  schema_graph:
    path: Skills/schema_graph
    status: active
  query_explain:
    path: Skills/query_explain
    status: active
```

## 4. toolsets.yaml
Configs/toolsets.yaml is the source of truth.

`Configs/toolsets.yaml` is the source of truth. Toolsets/Python modules may only load/compile from YAML. Python wrappers must not declare additional tools independently.

Required toolsets:

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

## 5. policies.yaml
Required policy groups:

```yaml
policies:
  agent_workflow_sandbox_ddl:
    allow_select: true
    allow_insert: true
    allow_update: true
    allow_delete: true
    allow_create: true
    allow_alter: true
    allow_drop_owned_workspace_objects: true
    require_sandbox: true
    require_sql_guard: true
    require_created_object_provenance: true

  sandbox_cleanup_internal:
    allow_drop_owned_workspace_objects: true
    require_workspace_lock: true
    require_audit: true

  manual_console_sandbox:
    allow_select: true
    allow_insert: true
    allow_update: true
    allow_delete: true
    allow_create: true
    allow_alter: true
    allow_drop_owned_workspace_objects: true
    require_explicit_target: true
    require_risk_analysis: true
    require_confirmation_for_high_risk: true
    require_workspace_lock_for_mutation: true
    invalidate_schema_snapshot_after_mutation: true
    block_server_level_statements: true

  connected_database:
    agent_read_only: true
    agent_allow_select: true
    agent_allow_explain: true
    agent_block_insert_update_delete_drop_alter_truncate: true
    agent_ignore_manual_write_enabled: true

  user_query_box:
    primary_api_contract_endpoints: [/query/check, /query/execute]
    require_explicit_target: true
    require_sql_guard: true
    check_never_executes_sql: true
    high_risk_returns_visible_confirmation_code: true
    confirmation_code_digits: 4
    confirmation_code_generated_by_backend: true
    confirmation_code_bound_to: [check_id, sql_hash, target, expiry]
    execute_requires_yes_decision: true
    high_risk_requires_confirmation: true
    high_risk_requires_audit_prewrite: true
    high_risk_audit_failure: fail_closed
    read_only_audit_failure: configurable_fail_open_with_warning
    connected_database_execution_authority: selected_credential_permission
    db_permission_denied_error: DB_PERMISSION_DENIED
    manual_write_enabled_role: metadata_or_ui_warning_only_unless_future_policy_configured
```

## 6. .env.example
Example:

```env
SAFY_OPENAI_API_KEY=
SAFY_DB_PASSWORD=
SAFY_DB_READONLY_PASSWORD=
SAFY_DB_MANUAL_PASSWORD=
```

Rules:
- `.env` stores raw secret values.
- JSON config stores env variable names only.
- `.env.example` must not contain real secrets.

## 7. .gitignore Rules
Required entries:

```gitignore
.env
Data/safy_runtime.db
Data/safy_audit.db
Data/User/user_profiles.json
Data/Database_management/database_profiles.json
Data/User/*.local.json
Data/Database_management/*.local.json
```

## 8. Config Loading Order
Recommended loading order:
1. Built-in safe defaults.
2. `Configs/app.yaml`.
3. `Configs/skills.yaml`.
4. `Configs/toolsets.yaml`.
5. `Configs/policies.yaml`.
6. Environment variables.
7. Local development overrides if explicitly allowed.

## 9. Override Rules
Rules:
- Overrides must not enable agent writes to connected database.
- Overrides must not set raw SQL persisted by default.
- Overrides must not set audit high-risk fail-open.
- Overrides must not let Python tool wrappers add tools outside YAML.
- Local debug mode may exist but must be explicit and must not be default.

## Implementation Notes
Load config at startup and compile into immutable runtime policy objects. Refuse startup on invalid dangerous config values.

## Related Documents
- `03_DATA_SCHEMA.md`
- `05_SECURITY_POLICY.md`
- `08_SKILLS_SPEC.md`
- `09_TOOLS_SPEC.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`
