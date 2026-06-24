# SAFY Full Skills Workflow Fix Report

## Scope

This pass creates and wires SAFY's runtime skill layer under the `Skills/` directory.

It does not change login, environment-secret storage, database profile storage, or the Schema Graph UI layout from the previous pass.

## New runtime skill folders

- `Skills/Command_router`
- `Skills/Database_context`
- `Skills/Database_switch`
- `Skills/Schema_graph`
- `Skills/Text_to_query`
- `Skills/Query_guard`
- `Skills/Execute_box`
- `Skills/Execute_query`
- `Skills/Query_explain`
- `Skills/Query_repair`
- `Skills/common`

Existing legacy skill retained:

- `Skills/Create_database`

## Workflow now wired in `Agent/agent_runtime.py`

### `/Execute` workflow

```text
command_router
→ database_context
→ schema_graph
→ text_to_sql
→ execute_box
→ user Check Safety
→ query_guard
→ user Execute
→ execute_query
```

`/Execute` now returns a SQL draft only. It no longer performs SQL Guard check during chat generation. The UI still places the draft into the Execute Box, and the user must manually run Check Safety then Execute.

### Normal database chat

Normal DB-related chat without `/Execute` is routed by `command_router` and returns the existing instruction to use `/Execute`.

### Normal non-database chat

Normal non-database chat uses the active model without touching database runtime.

## Skill contracts added

Each skill folder includes:

- `Skill.md`
- `runtime.py`

`Skill.md` documents policy and boundaries.
`runtime.py` contains the callable runtime implementation.

## Config updates

Updated:

```text
Configs/skills.yaml
```

Now marks:

```text
real_skill_execution: true
```

and lists all active runtime skills.

## Core router update

Updated:

```text
Core/skill_router.py
```

to route all new skill names and intents.

## SOUL update

Added a runtime skill workflow contract so Hermes/agents understand the intended workflow and do not collapse the steps back into direct execution.

## Files changed/new

- `SOUL.md`
- `Agent/agent_runtime.py`
- `Configs/skills.yaml`
- `Core/skill_router.py`
- `Skills/__init__.py`
- `Skills/common/__init__.py`
- `Skills/common/types.py`
- `Skills/Command_router/__init__.py`
- `Skills/Command_router/Skill.md`
- `Skills/Command_router/runtime.py`
- `Skills/Database_context/__init__.py`
- `Skills/Database_context/Skill.md`
- `Skills/Database_context/runtime.py`
- `Skills/Database_switch/__init__.py`
- `Skills/Database_switch/Skill.md`
- `Skills/Database_switch/runtime.py`
- `Skills/Schema_graph/__init__.py`
- `Skills/Schema_graph/Skill.md`
- `Skills/Schema_graph/runtime.py`
- `Skills/Text_to_query/__init__.py`
- `Skills/Text_to_query/Skill.md`
- `Skills/Text_to_query/runtime.py`
- `Skills/Query_guard/__init__.py`
- `Skills/Query_guard/Skill.md`
- `Skills/Query_guard/runtime.py`
- `Skills/Execute_box/__init__.py`
- `Skills/Execute_box/Skill.md`
- `Skills/Execute_box/runtime.py`
- `Skills/Execute_query/__init__.py`
- `Skills/Execute_query/Skill.md`
- `Skills/Execute_query/runtime.py`
- `Skills/Query_explain/__init__.py`
- `Skills/Query_explain/Skill.md`
- `Skills/Query_explain/runtime.py`
- `Skills/Query_repair/__init__.py`
- `Skills/Query_repair/Skill.md`
- `Skills/Query_repair/runtime.py`

## Verification

Executed:

```bash
python -m py_compile Agent/agent_runtime.py Core/skill_router.py Skills/**/runtime.py Skills/**/__init__.py Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py Gateway/query_orchestrator.py
node --check Apps/Web/safy-ui.js
```

Result: PASS.

## Final status

SAFY_FULL_SKILLS_WORKFLOW_FIXED
