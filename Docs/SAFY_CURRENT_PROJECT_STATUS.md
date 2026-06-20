# SAFY CURRENT PROJECT STATUS REPORT

**Document status:** Canonical project review document  
**Purpose:** Dùng làm tài liệu chuẩn để đánh giá, kiểm tra lại, audit, refactor và tiếp tục phát triển SAFY.  
**Project:** SAFY — Local AI Database Agent / Database Safety Gateway  
**Prepared for:** Sadowiz / ruka maija  
**Generated date:** 2026-06-21  
**Scope:** Tổng hợp trạng thái SAFY sau các phase gần đây: read-only direct workflow, UI settings, Hermes-inspired workflow restructure, deterministic policy/reviewer, sandbox secret repair, project cleanup.

> Tài liệu này là bản đánh giá chuẩn. Nó không phải patch report tạm thời. Khi check lại dự án, hãy dùng file này như checklist kiến trúc, workflow, sandbox, security, compatibility, test matrix và roadmap tiếp theo.

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Scope and Project Stage](#2-current-scope-and-project-stage)
3. [Project Architecture Overview](#3-project-architecture-overview)
4. [Canonical Project Structure](#4-canonical-project-structure)
5. [Runtime Components by Folder](#5-runtime-components-by-folder)
6. [API Endpoint Map](#6-api-endpoint-map)
7. [Data Storage Map](#7-data-storage-map)
8. [Model Provider Workflow](#8-model-provider-workflow)
9. [Database Profile Workflow](#9-database-profile-workflow)
10. [Agent Workflow Model](#10-agent-workflow-model)
11. [Skill Registry and Skill Runtime](#11-skill-registry-and-skill-runtime)
12. [Tool Registry and Tool Runtime](#12-tool-registry-and-tool-runtime)
13. [SQL Safety Policy](#13-sql-safety-policy)
14. [Query Workflows](#14-query-workflows)
15. [Sandbox Architecture](#15-sandbox-architecture)
16. [Supabase RPC Architecture](#16-supabase-rpc-architecture)
17. [UI/UX Current State](#17-uiux-current-state)
18. [Security, Secrets and Redaction Boundary](#18-security-secrets-and-redaction-boundary)
19. [Audit, Logging and Workflow Trace](#19-audit-logging-and-workflow-trace)
20. [Compatibility Matrix](#20-compatibility-matrix)
21. [Test and Validation Matrix](#21-test-and-validation-matrix)
22. [Known Issues and Technical Debt](#22-known-issues-and-technical-debt)
23. [Next Phases](#23-next-phases)
24. [Push-clean and Git Safety](#24-push-clean-and-git-safety)
25. [Troubleshooting](#25-troubleshooting)
26. [Documentation Cleanup Policy](#26-documentation-cleanup-policy)
27. [Migration, Backup and Recovery](#27-migration-backup-and-recovery)
28. [Glossary](#28-glossary)
29. [Final Review Checklist](#29-final-review-checklist)

---

# 1. Executive Summary

SAFY hiện là một **local AI Database Agent + Database Safety Gateway** chạy qua FastAPI backend và Web UI tại:

```text
http://127.0.0.1:8000/
```

Mục tiêu của SAFY:

```text
Cho phép user trò chuyện với database bằng natural language / SQL,
nhưng vẫn giữ boundary an toàn:
- read-only query được chạy trực tiếp theo guard
- write/DDL bắt buộc sandbox validation trước real execution
- destructive action cần confirmation hoặc block
- secrets không được ghi vào git/audit/session/UI
```

Kiến trúc hiện tại đã chuyển dần từ “chat + execute box” sang mô hình:

```text
Perceive → Plan → Slot-fill → Route → Act → Verify → Present → Remember
```

Trong đó:

| Layer | Vai trò |
|---|---|
| UI/Web | Chat, Execute Box, settings, result card, schema graph |
| API | FastAPI boundary, session/profile/query endpoints |
| Agent Runtime | Điều phối chat, skills, workflow state, context pack |
| Core Workflow | State, policy, reviewer, skill/tool registry |
| Gateway | SQL guard, query orchestrator, DB driver routing |
| Sandbox | Validate write/DDL trước khi chạm real DB |
| DataStore/State/Audit | Profile, env secret reference, runtime state, audit trace |
| LLM/Providers | OpenAI-compatible/local/router model profile |
| Skills/Tools | Capability layer cho text-to-query, guard, execute, schema, repair |

Trạng thái quan trọng hiện tại:

- **Read-only direct workflow đã pass**: user có thể hỏi “show/xem/hiển thị dữ liệu bảng…” và kết quả hiện trực tiếp trong chat dạng result card.
- **Write/DDL vẫn đúng policy**: `CREATE`, `INSERT`, `UPDATE`, `DELETE` không được auto-run; phải qua Check Safety sandbox.
- **Sandbox secret repair đã được bổ sung**: metadata sandbox stale nhưng mất internal secret sẽ không còn được tin mù quáng; hệ thống phải repair/recreate sandbox.
- **Hermes-inspired restructure đã thực hiện một phần lớn**: Agent State, Tool Registry metadata, Workflow Policy, deterministic reviewer.
- **Phase 4 Text_to_query v2 chưa thực hiện theo chủ ý**: phần này sẽ xử lý sau bằng skill package có examples/tests/templates, không dùng một prompt khổng lồ.

---

# 2. Current Scope and Project Stage

## 2.1 Scope hiện tại

SAFY đang bao gồm các nhóm chức năng:

```text
1. Local web dashboard
2. Model profile management
3. Database profile management
4. Supabase RPC execution
5. PostgreSQL/MySQL/SQLite/native DB contracts
6. Read-only direct query path
7. Write/DDL sandbox-first workflow
8. Agent state/session memory
9. Skill registry
10. Tool registry
11. SQL guard/policy/reviewer
12. Sandbox manager
13. Audit/runtime trace
14. Settings UI: dark/light, streaming UI, auto-run read-only
15. Schema graph
16. Push-clean/git safety workflow
```

## 2.2 Stage interpretation

Có thể có lệch giữa README cũ và code mới. Một số tài liệu cũ còn mô tả stage trước, trong khi source hiện đã có:

```text
- Hermes workflow restructure
- Workflow trace endpoint
- Tool registry endpoint
- Read-only direct chat result card
- Sandbox secret repair
```

Vì vậy khi đánh giá dự án, dùng trạng thái này làm source-of-truth:

```text
Current stage = SAFY after Hermes-inspired Workflow Restructure + Read-only Direct + Sandbox Secret Repair
```

## 2.3 Phase đã làm

| Phase | Tình trạng | Ghi chú |
|---|---:|---|
| Phase 1: Agent State + Runtime Trace DB | Done / partially integrated | Cần test thêm persistence edge cases |
| Phase 2: Tool Registry có safety metadata | Done / needs canonicalization | Có registry nhưng cần tránh duplicate source-of-truth |
| Phase 3: Workflow Policy Engine | Done | Risk class + route decision |
| Phase 4: Text_to_query v2 | Not done intentionally | Là phase sau |
| Phase 5: Deterministic Reviewer/Subagent-style layer | Done basic | Reviewer không có quyền execute |
| UI read-only result card | Done | Cần polish dần |
| Settings dark/light/streaming/auto-run read-only | Done basic | Streaming hiện là UI typewriter |
| Sandbox secret repair | Done | Cần live test lại Docker/DB |

---

# 3. Project Architecture Overview

## 3.1 High-level runtime pipeline

```text
User
→ Web UI / Execute Box / Settings
→ FastAPI backend
→ AgentRuntime / QueryOrchestrator
→ WorkflowPolicy + SQLGuard + Reviewer
→ Tool/Skill Registry
→ Sandbox or Connected DB
→ Result/Audit/State
→ UI presentation
```

## 3.2 Database safety split

SAFY phải giữ tách biệt hai luồng:

```text
READ_ONLY:
User asks to show/select/read
→ classify READ_ONLY_SQL
→ SQL Guard
→ connected DB read-only execution
→ chat result card
→ no sandbox
```

```text
WRITE/DDL:
User asks create/insert/update/delete/alter/drop
→ classify WRITE_SQL / DDL_SQL / DESTRUCTIVE_SQL
→ generate SQL draft
→ user review in Execute Box
→ Check Safety in sandbox
→ if sandbox passes, execute real DB
→ audit result
```

## 3.3 Why SAFY is not just a chatbot

SAFY phải enforce database policy independently of the model:

```text
Model can propose SQL.
Model cannot authorize real execution.
Policy/reviewer/sandbox decide execution permission.
```

LLM có thể hỗ trợ:

- natural language interpretation
- SQL generation
- explanation
- repair suggestion
- schema-aware answer

LLM không được tự quyết:

- bypass sandbox
- execute write/DDL
- access secrets
- ignore confirmation
- trust stale sandbox metadata

---

# 4. Canonical Project Structure

```text
SAFY/
├─ Agent/
│  ├─ agent_runtime.py
│  └─ schema_context.py
├─ Apps/
│  ├─ Api/
│  │  └─ safy_api/
│  └─ Web/
├─ Audit/
├─ Configs/
├─ Contracts/
├─ Core/
├─ Data/
├─ DataStore/
├─ Docker/
├─ Docs/
├─ Gateway/
├─ LLM/
├─ Logging/
├─ Providers/
├─ Safy_Docs/
├─ Sandbox/
├─ Scripts/
├─ Skills/
├─ State/
├─ Tools/
├─ Toolsets/
├─ README.md
├─ SAFY_source.md
├─ SOUL.md
├─ requirements.txt
├─ requirements-db.txt
└─ pyproject.toml
```

## 4.1 Canonical vs runtime-generated folders

| Path | Type | Commit? |
|---|---|---:|
| `Agent/` | source | yes |
| `Apps/` | source | yes |
| `Audit/` | source | yes |
| `Configs/` | config source | yes if no secrets |
| `Core/` | source | yes |
| `DataStore/` | source | yes |
| `Gateway/` | source | yes |
| `Sandbox/` | source | yes |
| `Skills/` | source | yes |
| `Tools/` | source | yes |
| `Data/secrets/` | runtime secret | no |
| `Data/sessions/` | runtime session | no |
| `Data/sandboxes/` | runtime sandbox metadata | no |
| `Sandbox/workspaces/` | runtime workspace | no |
| `Data/*.db` | runtime DB | no |
| `Docker/.env` | local secret config | no |
| `.env` | local secrets | no |

---

# 5. Runtime Components by Folder

## 5.1 `Apps/Api/safy_api`

FastAPI backend.

Expected responsibilities:

```text
- Serve Web UI
- Auth/session boundary
- Profile APIs
- Model APIs
- Database APIs
- Agent APIs
- Query check/execute APIs
- Schema graph APIs
- Sandbox APIs
- Recovery APIs
```

Important endpoints:

```text
GET  /
GET  /health

GET  /model-profiles
POST /model-profiles
POST /model-profiles/{profile_id}/activate
POST /model-profiles/{profile_id}/test

GET  /database-profiles
POST /database-profiles
POST /database-profiles/{profile_id}/activate
POST /database-profiles/{profile_id}/test
POST /database-profiles/{profile_id}/ensure-sandbox

GET  /schema-graph
GET  /schema-graph/active
POST /schema-graph/active/refresh

GET  /agent/skills
GET  /agent/tools
GET  /agent/state/{chat_id}
GET  /agent/workflow/{chat_id}
POST /agent/chat
POST /agent/generate-sql

POST /query/check
POST /query/execute

GET  /sandboxes
POST /sandboxes
GET  /sandboxes/{sandbox_id}
POST /sandboxes/{sandbox_id}/start
POST /sandboxes/{sandbox_id}/stop
DELETE /sandboxes/{sandbox_id}
POST /sandboxes/{sandbox_id}/restore
```

## 5.2 `Apps/Web`

Static UI:

```text
Apps/Web/index.html
Apps/Web/styles.css
Apps/Web/safy-ui.js
```

Features:

```text
- Chat UI
- Session list
- Model/database status
- Execute Box
- Check Safety / Execute
- Schema Graph button
- Read-only result card
- Dark/light mode
- Streaming UI typewriter
- Auto-run read-only setting
- Runtime status badges
```

Known limitation:

```text
Streaming hiện tại là UI-level typewriter, chưa phải backend token streaming.
```

## 5.3 `Agent`

Key files:

```text
Agent/agent_runtime.py
Agent/schema_context.py
```

Responsibilities:

```text
- Receive chat messages
- Build context pack
- Route to skills/tools
- Manage session workflow state
- Direct read-only execution
- Draft write/DDL into Execute Box
- Present structured chat_display payload
```

## 5.4 `Core`

Key files:

```text
Core/agent_state.py
Core/context_pack.py
Core/workflow_policy.py
Core/workflow_review.py
Core/workflow_engine.py
Core/skill_registry.py
Core/skill_contract.py
Core/skill_router.py
Core/intent_detector.py
Core/intent_planner.py
Core/result_summarizer.py
```

Responsibilities:

```text
- Typed state model
- Context packaging
- SQL risk policy
- Deterministic workflow review
- Skill contract and registry
- Intent planning
- Result summarization
```

## 5.5 `Gateway`

Key files:

```text
Gateway/query_orchestrator.py
Gateway/sql_guard.py
Gateway/sql_classifier.py
Gateway/sql_normalizer.py
Gateway/risk_analyzer.py
Gateway/permission_checker.py
Gateway/real_db_policy.py
Gateway/sandbox_adapter.py
Gateway/connected_db_adapter.py
Gateway/statement_target_extractor.py
Gateway/db_drivers/
```

Responsibilities:

```text
- SQL guard/classification
- Check Safety
- Execute real DB
- Sandbox adapter
- Connected DB adapter
- Driver factory
- SQL hash/check_id enforcement
```

## 5.6 `Sandbox`

Key files:

```text
Sandbox/sandbox_manager.py
Sandbox/docker_manager.py
Sandbox/sandbox_store.py
Sandbox/secret_store.py
Sandbox/sandbox_state.py
Sandbox/workspace_lifecycle.py
Sandbox/schema_cache.py
Sandbox/sqlite_runner.py
Sandbox/restore_manager.py
Sandbox/mock_sandbox.py
```

Responsibilities:

```text
- Ensure sandbox
- Repair stale sandbox state
- Manage Docker-backed validation
- Manage internal sandbox secrets
- Manage workspace lifecycle
- Validate write/DDL before real DB
```

## 5.7 `DataStore`

Key files:

```text
DataStore/profile_store.py
DataStore/database_profile_store.py
DataStore/env_secret_resolver.py
DataStore/env_writer.py
DataStore/schema_graph_store.py
DataStore/user_store.py
DataStore/config_loader.py
```

Responsibilities:

```text
- Save/load profiles
- Resolve env var names to values at runtime
- Write local env if user config requires
- Load schema graph
- User profile local store
```

## 5.8 `State`

Key files:

```text
State/runtime_db.py
State/json_runtime_db.py
State/high_risk_code_state.py
```

Responsibilities:

```text
- Session messages
- Agent state persistence
- Workflow trace persistence
- Confirmation code TTL
- Strip rows/secrets before persist
```

## 5.9 `Audit`

Key files:

```text
Audit/audit_logger.py
Audit/audit_schema.py
Audit/audit_store.py
Audit/json_audit_store.py
```

Responsibilities:

```text
- Security/action audit
- Query decision audit
- Blocked attempts audit
- Redacted metadata logs
```

## 5.10 `LLM` and `Providers`

Key files:

```text
LLM/provider_profiles.py
LLM/provider_store.py
LLM/provider_health.py
LLM/provider_adapters/openai_compatible.py

Providers/base_provider.py
Providers/model_client.py
Providers/provider_registry.py
Providers/mock_provider.py
Providers/test_provider.py
```

Responsibilities:

```text
- OpenAI-compatible provider support
- Model profile health check
- Mock provider for test
- Local/remote router compatibility
```

## 5.11 `Skills`

Current skills:

```text
Command_router
Create_database
Database_context
Database_switch
Execute_box
Execute_query
Query_explain
Query_guard
Query_repair
Schema_graph
Text_to_query
common
```

Current status:

```text
- Skill.md exists
- runtime.py exists
- Registry exists
- Text_to_query v2 not yet done
```

## 5.12 `Tools`

Key files:

```text
Tools/registry.py
Tools/tool_executor.py
Tools/tool_schema.py
Tools/tool_result.py
Tools/base_tool.py
Tools/database/read_schema_tool.py
Tools/sandbox/create_workspace_tool.py
Tools/sandbox/execute_sandbox_sql_tool.py
Tools/sandbox/cleanup_workspace_tool.py
Tools/sandbox/inspect_workspace_tool.py
Tools/sql/validate_sql_tool.py
Tools/sql/sanitize_identifier_tool.py
```

Responsibilities:

```text
- Tool registration
- Tool metadata
- Tool result typing
- Database/sandbox/sql utilities
```

---

# 6. API Endpoint Map

## 6.1 Runtime / health

| Method | Endpoint | Purpose | Risk | State |
|---|---|---|---|---|
| GET | `/` | Serve app | low | no |
| GET | `/health` | Check backend health | low | no |

## 6.2 Agent

| Method | Endpoint | Purpose | Risk | Uses DB? | Uses model? |
|---|---|---|---|---:|---:|
| POST | `/agent/chat` | Main chat workflow | variable | maybe | maybe |
| POST | `/agent/generate-sql` | Generate SQL draft | medium | maybe schema | yes/maybe |
| GET | `/agent/skills` | List skills | low | no | no |
| GET | `/agent/tools` | List registered tools | low | no | no |
| GET | `/agent/state/{chat_id}` | Inspect state | medium privacy | no | no |
| GET | `/agent/workflow/{chat_id}` | Inspect workflow trace | medium privacy | no | no |

## 6.3 Query

| Method | Endpoint | Purpose | Risk | Sandbox? | Real DB? |
|---|---|---|---|---:|---:|
| POST | `/query/check` | Check SQL safety | variable | yes for write/DDL | no |
| POST | `/query/execute` | Execute checked SQL | high | verify previous check | yes |

Policy:

```text
SELECT/read-only: /query/check can return read_only_verified without sandbox.
DDL/write: /query/check must sandbox.
```

## 6.4 Database profiles

| Method | Endpoint | Purpose | Risk |
|---|---|---|---|
| GET | `/database-profiles` | List redacted profiles | medium |
| POST | `/database-profiles` | Save profile | high if secret handling wrong |
| POST | `/database-profiles/{id}/activate` | Activate target DB | medium |
| POST | `/database-profiles/{id}/test` | Test connection | high |
| POST | `/database-profiles/{id}/ensure-sandbox` | Prepare sandbox | high |

## 6.5 Model profiles

| Method | Endpoint | Purpose | Risk |
|---|---|---|---|
| GET | `/model-profiles` | List redacted model profiles | medium |
| POST | `/model-profiles` | Save model profile | high if secret handling wrong |
| POST | `/model-profiles/{id}/activate` | Activate model | medium |
| POST | `/model-profiles/{id}/test` | Test model | medium |

## 6.6 Schema graph

| Method | Endpoint | Purpose | Risk |
|---|---|---|---|
| GET | `/schema-graph` | Read schema graph | low/medium |
| GET | `/schema-graph/active` | Active graph | low/medium |
| POST | `/schema-graph/active/refresh` | Re-introspect DB | medium |

## 6.7 Sandbox

| Method | Endpoint | Purpose | Risk |
|---|---|---|---|
| GET | `/sandboxes` | List sandboxes | medium |
| POST | `/sandboxes` | Create sandbox | high |
| GET | `/sandboxes/{id}` | Inspect sandbox | medium |
| POST | `/sandboxes/{id}/start` | Start sandbox | high |
| POST | `/sandboxes/{id}/stop` | Stop sandbox | high |
| DELETE | `/sandboxes/{id}` | Remove sandbox | high |
| POST | `/sandboxes/{id}/restore` | Restore sandbox | high |

---

# 7. Data Storage Map

| Path | Owner | Contains | Commit? | Notes |
|---|---|---|---:|---|
| `.env` | local runtime | API keys/passwords/base URLs | no | local only |
| `Data/model_profiles/model_profiles.json` | LLM/Profile Store | model profile metadata/env var names | yes if no raw secret | verify redaction |
| `Data/Database_management/database_profiles.json` | Database Profile Store | DB profile metadata/env var names | yes if no raw secret | may need example-only |
| `Data/User/user_profiles.json` | User store | local users/preferences | maybe | no passwords if hashed/redacted |
| `Data/SchemaGraph/index.json` | Schema graph store | schema graph snapshot | maybe no | if generated runtime, ignore |
| `Data/safy_runtime.db` | Runtime DB | sessions/state/workflow | no | runtime |
| `Data/safy_audit.db` | Audit DB | audit events | no | runtime |
| `Data/sessions/` | Session store | chat sessions | no | runtime |
| `Data/secrets/` | Secret store | internal sandbox secret refs | no | runtime only |
| `Data/sandboxes/` | Sandbox store | sandbox metadata | no | runtime only |
| `Sandbox/workspaces/` | Sandbox lifecycle | temp validation workspace | no | runtime |
| `Docker/.env` | Docker local | DB passwords/local ports | no | use `.env.example` |
| `Docker/.env.example` | Docker docs | example config | yes | no real secret |
| `Scripts/prepare_push_clean.ps1` | Git safety | cleanup script | yes | should remove runtime secret dirs |

---

# 8. Model Provider Workflow

## 8.1 Supported model direction

SAFY currently aims at:

```text
OpenAI-compatible API
OpenRouter / 9router / OmniRoute if OpenAI-compatible
Local model routers if they expose /v1/chat/completions
Mock/test provider
```

## 8.2 Model profile lifecycle

```text
User saves model profile
→ profile stores base_url/model/env key name
→ raw key stays in env
→ test provider health
→ activate profile
→ AgentRuntime uses active profile when LLM needed
```

## 8.3 Model should not break deterministic DB workflows

If model profile is invalid, SAFY should still allow deterministic operations that do not need model:

```text
- read-only SQL already typed by user
- Execute Box check/execute
- schema graph if DB available
- settings/profile management
```

Model should only be required for:

```text
- natural language to SQL
- explanation
- repair suggestion
- summarization
```

## 8.4 Future true streaming

Current streaming is UI typewriter. True backend streaming needs:

```text
SSE or WebSocket endpoint
provider streaming adapter
stream lifecycle event model
tool event streaming
cancel/stop generation control
frontend event parser
```

---

# 9. Database Profile Workflow

## 9.1 Profile save

```text
UI Database Settings
→ save profile
→ secret written to .env or selected env var
→ profile JSON stores env var name, not raw secret
→ connection test
→ activate profile
```

## 9.2 Profile fields

Common fields:

```text
id
name
provider
driver
engine
host/base_url
port
database
username
api_key_env
password_env
secret_env
connection_kind
execution_transport
sql_rpc_function
```

## 9.3 Redaction rule

Frontend may receive:

```text
profile id
display name
provider
driver
base_url hostname
username
env var names
connected status
```

Frontend must not receive:

```text
raw api key
raw password
raw DSN containing password
service role key
connection string with secret
```

## 9.4 Database profile and sandbox

A profile can be connected for read-only but still require sandbox repair for write/DDL. These are separate states:

```text
connected_database_ok = real DB secret/env works
sandbox_ready = sandbox metadata + sandbox internal secret + runtime runner valid
```

---

# 10. Agent Workflow Model

## 10.1 Canonical workflow

```text
Perceive
→ Plan
→ Slot-fill
→ Route
→ Act
→ Verify
→ Present
→ Remember
```

## 10.2 Perceive

Inputs:

```text
chat message
slash command
Execute Box SQL
button event
settings action
```

Output:

```text
normalized intent candidate
raw user intent
possible target database/table/action
```

## 10.3 Plan

Output is `WorkflowPlan` or equivalent:

```text
intent
statement_type
risk_class
route
required_slots
provided_slots
requires_sandbox
requires_confirmation
can_auto_execute
next_step
reasons
```

## 10.4 Slot-fill

Missing slots can include:

```text
database profile
table name
columns
values
where condition
confirmation code
target output format
```

If missing, agent should ask a targeted clarification, not guess.

## 10.5 Route

Route according to policy:

```text
READ_ONLY_SQL   → direct read-only DB
WRITE_SQL       → sandbox check then real execute
DDL_SQL         → sandbox check then real execute
DESTRUCTIVE_SQL → confirmation/block
SECRET_ACCESS   → block/redact
UNKNOWN_RISK    → clarify/block
META            → normal answer
```

## 10.6 Act

Act only through tools/orchestrator:

```text
database.read
sql.guard
sandbox.validate
database.execute
schema.graph.read
execute_box.set_draft
```

No direct model-to-driver execution.

## 10.7 Verify

Before execution:

```text
SQL hash matches check
check_id is valid
sandbox passed if required
risk class is allowed
confirmation passed if required
target profile is active
secret is not exposed
audit is recorded
```

## 10.8 Present

Response types:

```text
plain assistant message
SQL draft
read-only result card
execute status
error card
confirmation prompt
tool trace summary
```

## 10.9 Remember

Persist:

```text
last_table_name
last_table_columns
last_sql
last_sql_hash
last_check_id
last_safety_class
last_safety_result
last_execution_result summary
pending_skill
pending_slots
workflow_history
```

Do not persist:

```text
raw secrets
raw rows
unredacted stack trace
service role key
password
```

---

# 11. Skill Registry and Skill Runtime

## 11.1 Current skills

| Skill | Purpose | Status |
|---|---|---|
| `Command_router` | slash/command routing | basic |
| `Create_database` | create DB/table workflow | needs tests |
| `Database_context` | DB context/schema awareness | basic |
| `Database_switch` | switch active DB | basic |
| `Execute_box` | draft/execute box workflow | used |
| `Execute_query` | execute SQL workflow | used |
| `Query_explain` | explain query/result | basic |
| `Query_guard` | guard SQL | used |
| `Query_repair` | repair invalid SQL | basic |
| `Schema_graph` | schema graph flow | used |
| `Text_to_query` | NL → SQL | weak / Phase 4 pending |

## 11.2 Desired lifecycle

Every serious DB skill should eventually implement:

```text
can_handle(context, message)
collect_slots(context, message)
plan(context, slots)
act(context, plan)
verify(context, result)
present(context, result)
remember(context, result)
```

## 11.3 Text_to_query not yet final

Known weakness:

```text
Text_to_query still depends too much on heuristic/LLM.
It needs deterministic templates and regression examples.
```

Target structure:

```text
Skills/Text_to_query/
  Skill.md
  runtime.py
  examples.json
  tests.json
  templates/
  references/
```

---

# 12. Tool Registry and Tool Runtime

## 12.1 Current expected tools

| Tool | Purpose | Risk class |
|---|---|---|
| `sql.guard` | classify/validate SQL | low/medium |
| `database.read` | read-only DB query | READ_ONLY_SQL |
| `sandbox.validate` | validate write/DDL | WRITE/DDL |
| `database.execute` | real DB execute | high |
| `schema.graph.read` | schema graph | low |
| `execute_box.set_draft` | put SQL draft into UI | low |

## 12.2 Tool metadata required

Each tool should have:

```text
name
description
input_schema
output_schema
risk_class
read_only
writes_database
requires_sandbox
requires_confirmation
touches_secret
timeout
audit_required
```

## 12.3 Source-of-truth issue

Need verify no divergence between:

```text
Tools/registry.py
Configs/toolsets.yaml
AgentRuntime._register_runtime_tools()
```

If duplicate exists, choose one canonical registry path.

---

# 13. SQL Safety Policy

## 13.1 Safety classes

```text
READ_ONLY_SQL
WRITE_SQL
DDL_SQL
DESTRUCTIVE_SQL
SECRET_ACCESS
UNKNOWN_RISK
META
```

## 13.2 Policy matrix

| SQL/action | Class | Sandbox | Confirmation | Auto-run from chat | Real DB |
|---|---|---:|---:|---:|---|
| `SELECT ... LIMIT 100` | READ_ONLY_SQL | no | no | yes if enabled | read-only |
| `SELECT * FROM table` | READ_ONLY_SQL | no | maybe auto-limit | yes if enabled | read-only |
| `CREATE TABLE` | DDL_SQL | yes | maybe | no | after pass |
| `INSERT` | WRITE_SQL | yes | maybe | no | after pass |
| `UPDATE ... WHERE` | WRITE_SQL | yes | maybe | no | after pass |
| `UPDATE` no WHERE | WRITE_SQL/high | yes | yes | no | after pass or block |
| `DELETE ... WHERE` | WRITE_SQL | yes | yes/maybe | no | after pass |
| `DELETE` no WHERE | DESTRUCTIVE_SQL | yes/maybe | strong | no | block/confirm |
| `DROP TABLE` | DESTRUCTIVE_SQL | maybe | strong | no | block/confirm |
| secret request | SECRET_ACCESS | no | no | no | block |
| unknown SQL | UNKNOWN_RISK | no | no | no | clarify/block |

## 13.3 Non-negotiable rules

```text
SELECT must not be blocked by sandbox mismatch.
Write/DDL must not bypass sandbox.
Destructive SQL must not auto-run.
Secrets must not be exposed to UI/model/audit/git.
```

---

# 14. Query Workflows

## 14.1 Natural language read-only

Example:

```text
hãy show ra các dữ liệu trong bảng datatest
```

Flow:

```text
Chat
→ detect read-only intent
→ resolve table datatest
→ generate SELECT * FROM datatest LIMIT 100
→ SQL guard
→ direct read connected DB
→ chat result card
→ remember summary
```

## 14.2 Execute Box SELECT

```sql
SELECT * FROM datatest;
```

Flow:

```text
Execute Box
→ Check Safety
→ read_only_verified
→ sandbox skipped
→ Execute
→ connected DB read-only
→ row result
```

## 14.3 Natural language DDL

```text
tạo bảng student có thne text
```

Flow:

```text
Chat
→ classify DDL
→ generate CREATE TABLE ...
→ put SQL draft in Execute Box
→ user reviews
→ user clicks Check Safety
→ sandbox validate
→ if pass, user clicks Execute
→ real DB execute
```

## 14.4 Execute Box DDL

```sql
CREATE TABLE STUDENT (
  thne TEXT
);
```

Flow:

```text
Check Safety
→ DDL_SQL
→ ensure sandbox
→ validate SQL in sandbox
→ if pass, generate check_id/sql_hash
→ Execute real DB only if hash matches
```

## 14.5 Query repair

Expected future:

```text
SQL fails
→ classify error
→ suggest repair
→ user reviews repaired SQL
→ repeat safety flow
```

---

# 15. Sandbox Architecture

## 15.1 Why sandbox exists

Sandbox protects real database from unsafe write/DDL.

It allows:

```text
- syntax validation
- schema compatibility check
- high-risk detection
- safe dry-run
- DDL/write preview
```

## 15.2 Sandbox components

```text
Sandbox/sandbox_manager.py
Sandbox/docker_manager.py
Sandbox/sandbox_store.py
Sandbox/secret_store.py
Sandbox/workspace_lifecycle.py
Sandbox/sqlite_runner.py
Sandbox/schema_cache.py
Data/sandboxes/
Data/secrets/
Sandbox/workspaces/
Docker/
```

## 15.3 Real DB secret vs sandbox secret

Important distinction:

```text
Real DB secret:
  .env
  env var names referenced by database profile

Sandbox internal secret:
  Data/secrets/...
  credential refs used by sandbox metadata

Sandbox metadata:
  Data/sandboxes/.../metadata.json
```

Having real DB key in `.env` does not automatically mean sandbox internal credential refs are valid.

## 15.4 Recent sandbox repair behavior

Problem fixed:

```text
Data/sandboxes metadata existed
Data/secrets was cleaned
Sandbox was incorrectly considered ready
Check Safety failed with SANDBOX_SECRET_MISSING
```

Expected after fix:

```text
ensure_sandbox()
→ detect missing internal sandbox secret
→ invalidate stale ready state
→ repair/recreate sandbox credential metadata
→ continue validation
```

## 15.5 Sandbox lifecycle

```text
ensure_sandbox
→ create/repair metadata
→ create/repair internal credential refs
→ start runtime/container if needed
→ load/schema sync if needed
→ validate SQL
→ return pass/fail
→ persist non-secret metadata
```

## 15.6 Sandbox failure codes

| Code | Meaning | Fix |
|---|---|---|
| `SANDBOX_SECRET_MISSING` | Internal sandbox secret missing | repair/recreate sandbox |
| `SANDBOX_VALIDATION_FAILED` | SQL failed in sandbox | inspect SQL/schema |
| `SANDBOX_UNAVAILABLE` | Docker/runner unavailable | start Docker/runtime |
| `WORKSPACE_NOT_FOUND` | Workspace missing | recreate |
| `WORKSPACE_LOCKED` | Concurrent operation | wait/retry |
| `SQL_POLICY_BLOCKED` | Policy denied | review risk |
| `SQL_PARSE_FAILED` | SQL invalid | repair SQL |

---

# 16. Supabase RPC Architecture

## 16.1 Why Supabase is separate

Supabase with base URL + API key is not the same as native PostgreSQL password connection.

Supabase path:

```text
Supabase URL + API key
→ PostgREST/RPC
→ safy_execute_sql function for write/DDL
```

Native PostgreSQL path:

```text
host + port + db + username + password
→ native driver
```

## 16.2 Required Supabase RPC

SQL function:

```sql
public.safy_execute_sql(sql text)
```

Used for:

```text
CREATE/INSERT/UPDATE/DELETE/DDL through RPC
```

## 16.3 Safety requirement

Supabase write/DDL still needs:

```text
Check Safety sandbox pass
→ then execute RPC on real Supabase
```

---

# 17. UI/UX Current State

## 17.1 Current UI features

```text
- Chat layout
- Session list
- Model status
- Database status
- Read-only guard badge
- Execute Box
- Check Safety / Execute buttons
- Result card for read-only query
- Dark/light setting
- Streaming UI setting
- Auto-run read-only setting
- Schema Graph button
- Error cards
```

## 17.2 ChatGPT-like mapping already adopted

```text
- Assistant/user bubbles
- Structured result card
- Code block with copy button
- Table result rendering
- Badges for status/read-only/row count
```

## 17.3 Needed UI improvements

```text
- Tool trace/debug panel
- Timeline of workflow lifecycle
- Confirmation modal for destructive SQL
- Better pending task indicator
- Better schema graph integration
- True streaming from backend
- Stop/cancel generation
- Better error recovery action buttons
```

---

# 18. Security, Secrets and Redaction Boundary

## 18.1 Secret locations

Allowed:

```text
.env
OS env variables
Data/secrets runtime-only internal store
```

Not allowed:

```text
git-tracked JSON
audit logs
session history
UI response
report files
error messages
```

## 18.2 Redaction zones

| Zone | Must redact? |
|---|---:|
| UI | yes |
| API response | yes |
| Audit | yes |
| Runtime DB | yes |
| Logs | yes |
| Reports | yes |
| Git repo | yes |
| Model prompt | yes unless absolutely required and redacted |

## 18.3 Git safety

Must ignore:

```text
.env
.env.*
Data/secrets/
Data/sessions/
Data/sandboxes/
Sandbox/workspaces/
Data/**/*.db
Data/**/*.sqlite
Data/**/*.sqlite3
*.local.json
Docker/.env
*.log
```

## 18.4 Gitleaks

Before push:

```powershell
cd C:\Users\ASUS\SAFY
gitleaks detect --source . --verbose
```

---

# 19. Audit, Logging and Workflow Trace

## 19.1 Audit should track

```text
request_id
chat_id
workflow_id
profile_id
statement_type
risk_class
sql_hash
decision
sandbox_status
execute_status
row_count
error_code
timestamp
```

## 19.2 Audit should not track

```text
raw rows
raw secrets
passwords
service role keys
full stack traces with env
unredacted connection strings
```

## 19.3 Workflow trace

`/agent/workflow/{chat_id}` should show:

```text
perceived intent
plan
route
tool calls
policy decisions
review decisions
presented result type
remembered state summary
```

---

# 20. Compatibility Matrix

## 20.1 OS/runtime

| Target | Status |
|---|---|
| Windows 10/11 | supported target |
| PowerShell/CMD | supported |
| Python local runtime | supported |
| Docker Desktop | required for Docker-backed sandbox |
| Linux/macOS | likely possible but not primary tested target |

## 20.2 Model providers

| Provider type | Status |
|---|---|
| OpenAI-compatible API | supported direction |
| OpenRouter | supported if compatible |
| 9router | supported if compatible |
| OmniRoute | supported if compatible |
| Local model server | supported if OpenAI-compatible |
| Mock/test provider | supported for tests |

## 20.3 Databases

| Database | Status |
|---|---|
| SQLite | supported / local runner |
| PostgreSQL | supported direction / native driver |
| MySQL | supported direction / native driver |
| Supabase | supported through RPC/REST path |
| SQL Server | contract/driver present, needs live validation |
| Oracle | contract/driver present, needs live validation |
| Google Cloud SQL | provider profile direction |
| Amazon Aurora | provider profile direction |

## 20.4 Compatibility status meanings

| Status | Meaning |
|---|---|
| supported | implemented and expected to work |
| partially supported | implemented but may have edge cases |
| contract-only | files/contracts exist, live runtime not verified |
| not tested | no validation evidence |
| blocked | missing dependency/driver/runtime |
| deprecated | old path should not be used |

---

# 21. Test and Validation Matrix

## 21.1 Required local tests

| Test | Expected |
|---|---|
| App starts | `GET /health` ok |
| Read-only chat | result card in chat |
| Read-only Execute Box | `read_only_verified`, no sandbox |
| CREATE Check Safety | sandbox validation pass/fail correctly |
| CREATE Execute after pass | real DB execute |
| SQL hash mismatch | execute blocked |
| Supabase RPC execute | RPC called after safety pass |
| Reconnect database | profile active + schema graph refresh |
| Sandbox secret repair | no stale `SANDBOX_SECRET_MISSING` |
| Dark/light setting | UI changes |
| Streaming UI setting | typewriter on/off |
| Auto-run read-only off | chat read-only should draft/ask instead |
| Schema graph | opens/loads current graph |
| `/agent/tools` | tools listed |
| `/agent/workflow/{chat_id}` | trace visible |
| gitleaks | pass |

## 21.2 Suggested commands

```powershell
python -m compileall -q Agent Core Tools State Apps/Api/safy_api Gateway Skills Audit DataStore LLM Providers Sandbox Toolsets
node --check Apps/Web/safy-ui.js
gitleaks detect --source . --verbose
```

## 21.3 Manual SQL tests

```sql
SELECT * FROM datatest;
CREATE TABLE STUDENT (thne TEXT);
INSERT INTO STUDENT (thne) VALUES ('abc');
UPDATE STUDENT SET thne = 'def' WHERE thne = 'abc';
DELETE FROM STUDENT WHERE thne = 'def';
DROP TABLE STUDENT;
```

Expected:

```text
SELECT: direct/read-only
CREATE/INSERT/UPDATE/DELETE: sandbox first
DROP: destructive confirmation/block
```

---

# 22. Known Issues and Technical Debt

## 22.1 Text_to_query v2 not done

Main remaining intelligence weakness.

Need:

```text
examples.json
tests.json
templates
schema-aware table/column resolver
deterministic intent parser
LLM fallback only when needed
```

## 22.2 True backend streaming not done

Current streaming is visual/typewriter.

Need:

```text
SSE/WebSocket
provider streaming adapter
tool event stream
cancel button
```

## 22.3 Tool registry source-of-truth

Need reduce duplication between:

```text
Tools/registry.py
Configs/toolsets.yaml
AgentRuntime runtime registration
```

## 22.4 Docs not fully canonical

Need update README and archive/label stale docs.

## 22.5 Tests folder cleanup

Files named `test_*` inside runtime folders may cause confusion.

Need decide:

```text
move to Tests/
or rename smoke/helper files if runtime-needed
```

## 22.6 Live DB validation

Some drivers/provider modes need live tests:

```text
SQL Server
Oracle
Aurora
Cloud SQL
Docker-backed MySQL/Postgres sandbox
```

---

# 23. Next Phases

## Phase A: Documentation canonicalization

```text
Add this file to Docs/SAFY_CURRENT_PROJECT_STATUS.md
Update README.md to reference it
Mark legacy docs
Add API/data/tool/skill tables
```

## Phase B: Test matrix automation

```text
Create Tests/
Add regression tests for:
- read-only route
- write sandbox
- hash mismatch
- secret redaction
- sandbox secret repair
```

## Phase C: Tool trace UI

```text
Add lifecycle panel:
Perceive → Plan → Guard → Sandbox → Execute → Present
```

## Phase D: Text_to_query v2

```text
Skill package with examples/tests/templates
Vietnamese intent normalization
Schema-aware table/column resolver
Deterministic SQL templates
LLM fallback
```

## Phase E: True streaming

```text
Backend SSE/WebSocket
Provider streaming
UI event renderer
Stop generation
Tool status streaming
```

## Phase F: Reviewer/subagent expansion

```text
Planner
SQL generator
Guard reviewer
Execution reviewer
But executor remains deterministic and policy-bound
```

---

# 24. Push-clean and Git Safety

## 24.1 Before push

Run:

```powershell
cd C:\Users\ASUS\SAFY
powershell -ExecutionPolicy Bypass -File Scripts\prepare_push_clean.ps1
gitleaks detect --source . --verbose
git status
```

## 24.2 Should be removed before push

```text
.env
Data/secrets/
Data/sessions/
Data/sandboxes/
Sandbox/workspaces/
Data/*.db
Data/*.sqlite
Docker/.env
logs
```

## 24.3 If secret was committed before

Required:

```text
rotate/revoke secret
rewrite git history if needed
force-with-lease push only after careful check
```

---

# 25. Troubleshooting

## 25.1 `SANDBOX_SECRET_MISSING`

Meaning:

```text
Real DB env may exist, but sandbox internal secret ref is missing/stale.
```

Fix:

```text
restart backend
reconnect/save database
ensure sandbox
delete stale Data/sandboxes and Data/secrets if safe
let SAFY recreate sandbox
```

## 25.2 SELECT blocked by sandbox

Should not happen now.

If happens:

```text
check risk classification
check /query/check response
ensure statement is classified READ_ONLY_SQL
ensure sandbox skip path still active
```

## 25.3 CREATE fails but SELECT works

Likely sandbox issue, not DB connection issue.

Check:

```text
Docker running?
sandbox secret repair?
Data/sandboxes stale?
Data/secrets missing?
Supabase RPC installed?
```

## 25.4 Read-only result not showing in chat

Check:

```text
chat_display payload
frontend renderDatabaseResultCard
browser hard refresh Ctrl+F5
stale safy-ui.js cache
```

## 25.5 Model profile error blocks DB task

Should not block deterministic SQL execution.

Check:

```text
AgentRuntime fallback
model profile required only for NL-to-SQL
Execute Box SQL path should not require model
```

---

# 26. Documentation Cleanup Policy

## 26.1 Doc categories

Every doc should be labeled:

```text
CURRENT
TARGET
LEGACY
ARCHIVE
PROCESS
PATCH_REPORT
```

## 26.2 Recommended canonical docs

```text
Docs/SAFY_CURRENT_PROJECT_STATUS.md
Docs/SAFY_ARCHITECTURE.md
Docs/SAFY_SQL_SAFETY_POLICY.md
Docs/SAFY_SANDBOX_ARCHITECTURE.md
Docs/SAFY_API_MAP.md
Docs/SAFY_TEST_MATRIX.md
Docs/SAFY_TROUBLESHOOTING.md
```

## 26.3 Legacy docs

Do not delete blindly. Move or mark:

```text
Docs/archive/
Docs/Hermes_Execution/report/
```

## 26.4 Phase-numbered docs

If phase doc represents current runtime, rename to canonical name.

If phase doc is only patch history, keep under report/archive.

---

# 27. Migration, Backup and Recovery

## 27.1 Backup before major patch

Backup:

```text
.env
Data/model_profiles/
Data/Database_management/
Data/User/
Data/SchemaGraph if needed
```

Do not upload/share secrets.

## 27.2 Reset stale sandbox safely

```text
stop backend
backup local runtime if needed
remove Data/sandboxes/
remove Data/secrets/
remove Sandbox/workspaces/
restart backend
save/connect database
ensure sandbox
```

## 27.3 Recover after full project zip

After applying full clean zip:

```text
restore .env
reinstall dependencies if needed
restart backend
save/connect database profile
ensure sandbox
test read-only
test CREATE Check Safety
```

## 27.4 Runtime DB migration

If schema changes in runtime DB:

```text
backup Data/safy_runtime.db
run migration script if provided
verify /agent/workflow endpoint
```

---

# 28. Glossary

| Term | Meaning |
|---|---|
| AgentRuntime | Main chat/workflow orchestrator |
| ContextPack | Redacted task/database/state context for skills/model |
| SQLGuard | SQL classification/validation layer |
| WorkflowPolicy | Deterministic route/risk decision |
| WorkflowReview | Deterministic reviewer that checks plan/policy consistency |
| Check Safety | Sandbox validation step before write/DDL |
| Execute Box | UI panel for SQL draft/check/execute |
| Read-only direct | SELECT/show data path that skips sandbox |
| Sandbox | Safe validation environment for write/DDL |
| Sandbox secret | Internal runtime credential ref used by sandbox |
| Real DB secret | `.env` secret used to connect active database |
| Supabase RPC | PostgREST RPC function path for executing SQL |
| Tool Registry | Registered callable tools with schema/metadata |
| Skill Registry | Registered higher-level skill runtimes |
| Audit | Redacted security/action history |
| Workflow trace | Trace of plan/route/tool/policy decisions |

---

# 29. Final Review Checklist

Use this before deciding project is stable:

```text
[ ] README matches current architecture.
[ ] This status document is committed as Docs/SAFY_CURRENT_PROJECT_STATUS.md.
[ ] .env is not committed.
[ ] Data/secrets is not committed.
[ ] Data/sandboxes is not committed.
[ ] Sandbox/workspaces is not committed.
[ ] gitleaks passes.
[ ] Read-only chat works without Execute Box.
[ ] SELECT in Execute Box skips sandbox.
[ ] CREATE TABLE Check Safety uses sandbox.
[ ] CREATE TABLE Execute real DB only after safety pass.
[ ] SQL hash mismatch blocks execute.
[ ] Supabase RPC still works.
[ ] Sandbox secret repair works after clean zip.
[ ] /agent/tools returns expected tools.
[ ] /agent/workflow/{chat_id} returns useful trace.
[ ] Dark/light setting works.
[ ] Streaming UI setting works.
[ ] Auto-run read-only setting works.
[ ] Schema graph opens.
[ ] Stale docs are marked or archived.
[ ] Test matrix exists or is scheduled.
[ ] Text_to_query v2 is listed as next phase, not considered complete.
```

---

# 30. Final Conclusion

SAFY hiện đã đạt một architecture direction tương đối rõ:

```text
Database-specialized local AI agent
+ read-only direct query
+ sandbox-first write/DDL
+ deterministic SQL safety policy
+ structured agent state
+ tool/skill registry direction
+ UI result presentation
+ audit/workflow trace direction
```

Trọng tâm tiếp theo không nên là thêm prompt lớn, mà là:

```text
1. Cố định tài liệu canonical.
2. Tạo regression test matrix.
3. Hoàn thiện Text_to_query v2 bằng examples/tests/templates.
4. Thêm tool trace UI.
5. Thêm true backend streaming nếu cần.
6. Kiểm tra live sandbox/DB/driver compatibility.
```

Tài liệu này nên được dùng làm baseline để check lại dự án sau mỗi patch lớn.
