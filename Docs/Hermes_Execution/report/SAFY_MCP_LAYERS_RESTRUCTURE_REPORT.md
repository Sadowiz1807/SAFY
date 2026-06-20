# SAFY MCP-like Layers Restructure Report

## Scope

Implemented the requested MCP-like internal architecture in ordered layers without converting SAFY into an external MCP server. The goal is to make the existing SAFY agent remember workflow state, make skills inspectable/executable through a registry, and send a redacted context pack into downstream skill/model calls.

## Phase 1 — Agent State + Workflow Memory

### Implemented

- Added `Core/agent_state.py` with `AgentWorkflowState`.
- Added per-session workflow state fields:
  - `workflow_id`
  - `current_database`
  - `current_target`
  - `current_sandbox_id`
  - `current_database_profile_id`
  - `pending_skill`
  - `pending_action`
  - `required_slots`
  - `filled_slots`
  - `last_user_intent`
  - `last_sql`
  - `last_sql_hash`
  - `last_check_id`
  - `last_safety_result`
  - `last_execution_result`
  - `last_error`
- Added persistence helpers to both runtime stores:
  - `JsonRuntimeDB.get_agent_state/update_agent_state/clear_agent_state`
  - `RuntimeDB.get_agent_state/update_agent_state/clear_agent_state`
- Integrated state into `AgentRuntime.chat()` and `AgentRuntime.generate_sql()`.

### Result

SAFY can now remember a pending workflow across chat turns. Example:

1. User: `tạo bảng mới`
2. SAFY stores `pending_skill=create_database`, `pending_action=create_table`, missing slots `table_name`, `columns`.
3. User: `students`
4. SAFY fills `table_name=students` and asks for columns.
5. User: `có id, name, age`
6. SAFY generates a draft SQL and stores it as `last_sql`.

## Phase 2 — Skill Registry + Runtime Contract

### Implemented

- Added `Core/skill_contract.py` with common `SkillInput` and `SkillResult` types.
- Added `Core/skill_registry.py` with `SkillRegistry` and `RegisteredSkill`.
- Registered existing skills in `AgentRuntime`:
  - `command_router`
  - `database_context`
  - `schema_graph`
  - `text_to_query`
  - `query_guard`
  - `execute_box`
  - `execute_query`
  - `query_explain`
  - `query_repair`
- Added API endpoint `GET /agent/skills` to inspect active skill registrations.

### Result

Existing skills are now visible through a central registry. This avoids the previous hidden/direct wiring problem where skills existed in folders but did not have an inspectable runtime contract.

## Phase 3 — Context Pack

### Implemented

- Added `Core/context_pack.py` with redacted `ContextPack`.
- Context pack includes:
  - session id
  - target
  - sandbox id
  - database profile id
  - redacted database profile metadata
  - schema summary
  - current agent workflow state
  - active skill names
- `TextToQuerySkill.generate_sql_draft()` now accepts `context_pack_text`.
- `AgentRuntime.generate_sql()` builds a context pack before calling the model.
- `AgentRuntime.chat()` returns `context_pack` and `agent_state` metadata in workflow responses.

### Result

Model calls no longer receive only a raw user prompt and schema text. They receive structured SAFY runtime context, including pending workflow and last SQL/check state.

## Workflow Engine Added

Added `Core/workflow_engine.py` to support deterministic slot filling for high-value database tasks without requiring a model call.

Currently implemented deterministic workflow:

- Create table draft:
  - detect `create table`, `tạo bảng`, `tao bang`, `new table`
  - collect `table_name`
  - collect `columns`
  - infer conservative SQL types
  - generate draft SQL only
  - never execute automatically

Supported follow-up flow:

```text
User: tạo bảng mới
SAFY: Bạn muốn tạo bảng tên gì và gồm những cột nào?
User: students
SAFY: Bảng `students` cần những cột nào?
User: có id, name, age
SAFY: CREATE TABLE students (...)
```

## Safety Boundary

- Chat-level `execute` does not execute against a connected real database.
- For `connected_database`, SAFY returns instruction to use the Execute Box, preserving the existing Check Safety → Execute path.
- Sandbox execution can still use checked runtime execution.
- Real DB execution remains bound to `/query/execute` and the existing orchestrator protections.

## API Additions

Added:

- `GET /agent/skills`
- `GET /agent/state/{chat_id}`
- `DELETE /agent/state/{chat_id}`

Extended request schemas:

- `QueryCheckRequest` now accepts optional `chat_id` and `session_id`.
- `QueryExecuteRequest` now accepts optional `chat_id` and `session_id`.

When these ids are supplied, Check Safety and Execute results are recorded back into the agent state.

## Conflict Report

### Conflict 1 — Model profile resolver blocked deterministic workflows

**Observed:** During API validation, `POST /agent/chat` failed before slot filling because `model_profiles.json` was present but not in the expected object shape. The deterministic create-table workflow does not need a model call, but the API tried to resolve the active model before reaching the workflow.

**Fix:** Changed model profile auto-resolution in `/agent/chat` to tolerate any model profile load failure and continue. Model errors are now surfaced only when a path actually needs the model.

### Conflict 2 — Real DB execution could conflict with chat workflow semantics

**Observed:** Adding chat-level memory made it possible for a user to say `execute` after `check safety`. Letting chat call real connected DB execution directly would conflict with the existing SAFY security boundary, where real DB execution belongs to the Execute Box and `/query/execute`.

**Fix:** Chat-level `execute` is blocked for `connected_database` and returns a safe instruction to use the Execute Box. Sandbox execution remains possible through checked runtime execution.

### Conflict 3 — `Data/SchemaGraph/.gitkeep` versus generated schema graph files

**Observed:** `.gitignore` ignored the whole `Data/SchemaGraph/` directory, which can cause `.gitkeep` to disappear during push cleanup.

**Fix:** Changed ignore rules to:

```gitignore
Data/SchemaGraph/*
!Data/SchemaGraph/.gitkeep
```

Generated schema graph data stays ignored, while `.gitkeep` remains trackable.

### Conflict 4 — Docker local `.env` contains runtime credentials

**Observed:** `Docker/.env` contains local test-service passwords. These should not be pushed as project source.

**Fix:** Added `Docker/.env` to `.gitignore` and added `Docker/.env.example` as a safe template.

## Validation Performed

- `python -m compileall -q Agent Core Skills State Apps/Api/safy_api`
- Direct `AgentRuntime` deterministic workflow test:
  - `tạo bảng mới`
  - `students`
  - `có id, name, age`
- Direct API function validation through `agent_chat(AgentChatRequest(...))`.
- Checked `GET /agent/skills` returns registered skills.
- Ran a simple secret-pattern grep; no raw high-confidence API keys were found in modified source files.

## Changed Files

- `.gitignore`
- `Agent/agent_runtime.py`
- `Apps/Api/safy_api/main.py`
- `Apps/Api/safy_api/schemas.py`
- `Core/agent_state.py`
- `Core/context_pack.py`
- `Core/skill_contract.py`
- `Core/skill_registry.py`
- `Core/workflow_engine.py`
- `Docker/.env.example`
- `Docs/Hermes_Execution/report/SAFY_MCP_LAYERS_RESTRUCTURE_REPORT.md`
- `Skills/Text_to_query/runtime.py`
- `State/json_runtime_db.py`
- `State/runtime_db.py`

## Packaging Decision

The number of changed files is greater than 6, so the deliverable is a full cleaned project zip, not a changed-files-only zip.
