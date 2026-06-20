# Safy Architecture

## Purpose
Define Safy's system architecture, module boundaries, folder layout, and main runtime flows for implementation.

## Scope
Covers frontend/backend flow, API vs gateway, core vs providers, skills vs tools, state vs datastore, audit vs logging, and sandbox vs connected database execution.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Architecture Overview
Safy is organized as a local single-user application with a frontend UI, FastAPI API layer, gateway/use-case layer, agent core, skill routing, tool execution, providers/transports, SQL Guard, sandbox runners, connected database readers, state storage, and audit.

The architecture must keep policy enforcement outside LLM prompts. LLMs may suggest SQL or actions, but deterministic modules decide whether execution is allowed.

## 2. High-level Runtime Flow
Required flow:

```txt
User Browser
↓
Frontend UI
↓
Apps/Api - FastAPI HTTP Layer
↓
Gateway
↓
DataStore + Secret Resolver
↓
Agent Core
↓
Intent Detector / Intent Planner
↓
Skill Router / Skill.md
↓
ToolExecutor / ToolRegistry / Toolsets
↓
Providers / Transports
↓
SQL Guard / Permission Checker / Risk Analyzer
↓
Sandbox or Connected Database
↓
Result Summarizer
↓
State Store / Audit / Logging
↓
Response
```

## 3. Folder Structure
Recommended implementation structure:

```txt
Apps/
  Api/
    main.py
    routers/
    schemas/
    dependencies/
  Frontend/
Core/
  Agent/
  Gateway/
  Intent/
  Skills/
  Tools/
  Policy/
  SQLGuard/
  Runtime/
  Audit/
  DataStore/
Providers/
  LLM/
  Database/
  Sandbox/
Skills/
  Create_database/
  Text_to_sql/
  Read_schema/
  Explain_query/
Configs/
  app.yaml
  skills.yaml
  toolsets.yaml
  policies.yaml
Data/
  User/
  Database_management/
  safy_runtime.db
  safy_audit.db
Safy_Docs/
```

`Configs/toolsets.yaml` is the source of truth for toolsets. Python modules may load/compile from YAML but must not declare extra tools independently.

## 4. Module Responsibilities
Frontend UI:
- Starts/ends chats.
- Calls `/agent/chat` and Manual SQL APIs.
- Displays warnings, confirmations, workspace state, query results, and errors.
- Must not store secrets.

Apps/Api:
- FastAPI HTTP layer.
- Request validation and response formatting.
- Auth/profile/session dependency wiring for local app.
- No deep orchestration or policy shortcuts.

Gateway:
- Application use-case orchestration.
- Coordinates DataStore, Secret Resolver, Agent Core, audit, and runtime.
- Owns transactional application flow, not HTTP details.

Agent Core:
- Intent detection and planning.
- Skill routing.
- Calls ToolExecutor through policy-constrained interfaces.
- Never executes raw tool action bypassing registry.

ToolRegistry and ToolExecutor:
- Load tools from YAML-defined toolsets.
- Validate tool availability, target, risk, approval, and context.
- Return ToolResult.

SQL Guard / Permission Checker / Risk Analyzer:
- Parse SQL using target dialect.
- Split and validate multi-statement flows where allowed.
- Classify risk and statement class.
- Enforce target-specific policy.

DataStore:
- Access runtime SQLite DB, audit SQLite DB, and profile JSON files.
- Does not own policy.

Secret Resolver:
- Resolves env variable names to secret values at runtime.
- Never exposes raw secrets to frontend/API response/audit logs.

Providers:
- LLM, database, Docker/sandbox, SQLite runner adapters.
- Do not decide business policy.

## 5. Apps/Api vs Gateway
Apps/Api is the HTTP boundary. Gateway is the application orchestration boundary.

Rules:
- Apps/Api validates HTTP request shape and maps exceptions to API errors.
- Gateway executes use cases such as start chat, recover workspace, run agent chat, run manual SQL.
- Apps/Api must not directly call database tools to bypass Gateway.

## 6. Core vs Providers
Core contains Safy-specific orchestration, policy integration, skills, and tool execution. Providers are replaceable adapters for LLMs, DBMS connections, Docker, and SQLite execution.

Rules:
- Provider failure returns controlled ToolResult/API errors.
- Provider must not weaken SQL Guard or permission policy.

## 7. Skills vs Tools
Skill is workflow instruction and planning metadata. Tool is executable capability.

Rules:
- `Skill.md` is not enforcement by itself.
- Skill frontmatter compiles into deterministic SkillPolicy.
- LLM cannot override SkillPolicy.
- Tools must be called through ToolExecutor.

## 8. DataStore vs State
State is the runtime information: chat_id, workflow_id, workspace_id, profile IDs, schema snapshots, locks, and status. DataStore is the persistence implementation used to save/read that state.

Rules:
- Do not persist `active_connection_id` as durable state.
- Persist `database_profile_id` and reconnect after restart.
- Runtime DB must include schema version checks.

## 9. Audit vs Logging
Audit is security and action history. Logging is operational diagnostics.

Rules:
- Audit records endpoint/action, workflow_id, chat_id, workspace_id, risk level, confirmation status, statement hash, redacted SQL, and timestamps.
- Logs must not include secrets or raw SQL with sensitive literals.
- Audit DB migration must succeed before high-risk Manual SQL is allowed.

## 10. Main Workflows
Agent sandbox create database:
1. User request enters `/agent/chat`.
2. Intent planner routes to `Create_database` skill.
3. SkillPolicy restricts target to sandbox.
4. SQL is generated, sanitized, parsed, validated, and risk analyzed.
5. Sandbox workspace is created.
6. DDL/DML executes only in sandbox.
7. Schema is read back and summarized.
8. Runtime and audit records are updated.

Agent connected database query:
1. User request enters `/agent/chat`.
2. Intent planner routes to text-to-sql/read-schema/explain-query.
3. Connected database profile is resolved with read-only credentials.
4. SQL Guard allows only read-only SELECT/EXPLAIN.
5. Query limit/timeout is enforced.
6. Result is summarized and audited.

Manual SQL Console:
1. User explicitly opens Manual SQL Console.
2. User selects target.
3. SQL Guard parses, splits, validates, and risk-analyzes.
4. High-risk statements require confirmation and audit pre-write.
5. Sandbox mutation acquires workspace lock.
6. Connected DB user query executes according to selected credential permission after safety check, Yes decision, high-risk 4-digit confirmation when required, and audit.
7. If selected DB credential lacks permission, return `DB_PERMISSION_DENIED`.
8. `manual_write_enabled` may remain profile metadata/UI warning; it must not silently block user query execution unless explicitly configured as a separate future policy.
9. Result and audit status are returned.

## 11. Architecture Rules
Required distinctions:
- Apps/Api != Gateway.
- Core != Provider.
- Skill != Tool.
- State != DataStore.
- Audit != System Logging.
- Sandbox execution != Connected database execution.
- Agent workflow != Manual SQL Console.

Safety rules:
- Agent write/DDL only in sandbox.
- Agent connected database is read-only.
- SQLite runner only validates SQLite target SQL.
- PostgreSQL/MySQL use Docker sandbox.
- Workspace cleanup and mutation require workspace lock.

## Implementation Notes
Implement module boundaries as code-level dependencies. The safest direction is: API -> Gateway -> Core/Policy -> ToolExecutor -> Providers. Avoid imports that let API routes call provider/database execution directly.

## Related Documents
- `00_PROJECT_CONTEXT.md`
- `02_API_SPEC.md`
- `03_DATA_SCHEMA.md`
- `04_CONFIG_SPEC.md`
- `05_SECURITY_POLICY.md`
- `08_SKILLS_SPEC.md`
- `09_TOOLS_SPEC.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`

## Addendum: Required UI Architecture

The UI direction is chat-first with a left sidebar and right execution sidebar.

Required layout:
- Header with Safy, model status, DB status, and sandbox status.
- Left sidebar with session history, new session, settings, model connection, and database connection.
- Main chat area with conversation, prompt box, agent responses, technical explanations, and schema explanations.
- Right sidebar with agent result/execution panel and user query execution box.

The right sidebar query box is user-controlled and separate from the agent execution path. It uses `/query/check` before `/query/execute`.
