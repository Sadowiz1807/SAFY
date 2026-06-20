# Hermes Agent Roster

## Purpose
Define sub-agent responsibilities, allowed paths, and hard boundaries.

## Source Reference
`SAFY_source.md` and `HERMES_MAIN_AGENT_EXECUTION_PLAN.md`.

## Main Agent: Hermes
Responsibilities:
- Own orchestration, task assignment, validation, conflict handling, and stage gate reports.
- Preserve source-of-truth and user decisions.
- Validate sub-agent reports before accepting work.
- Run Gate 0 before dispatching any sub-agent task.
- Refuse to dispatch tasks whose task board entry is incomplete or `dispatchable: false`.
- Ask user before major product/security policy changes.

## Architect-Agent
Allowed paths:
- `Docs/`
- `README.md`
- `Configs/`

Responsibilities:
- Architecture consistency.
- Documentation structure.
- Source-of-truth alignment.
- Cross-module conflict detection.

## Backend-API-Agent
Allowed paths:
- `Apps/Api/`
- `Gateway/`
- `Contracts/`

Responsibilities:
- FastAPI app/routes.
- Pydantic schemas.
- CommonResponse/ErrorResponse.
- Profile save/test endpoints.
- Query check/execute endpoints.
- Gateway routing.

## Runtime-Data-Agent
Allowed paths:
- `DataStore/`
- `State/`
- `Audit/`
- `Logging/`
- `Data/`
- `Configs/`

Responsibilities:
- Config loader.
- Profile stores.
- `.env` writer.
- Atomic JSON writer.
- Secret resolver.
- Runtime/audit DB.
- Redaction.
- High-risk confirmation code storage/validation.

## Guard-Tools-Sandbox-Agent
Allowed paths:
- `Guard/`
- `Tools/`
- `Toolsets/`
- `Sandbox/`
- `Database/`
- `Docker/`

Responsibilities:
- SQL parser/classifier/risk analyzer.
- Permission checker.
- Multi-statement splitter.
- ToolRegistry/ToolExecutor.
- Sandbox manager.
- Database connector.
- Query Safety Pipeline.

## Agent-Skills-Provider-Agent
Allowed paths:
- `Core/`
- `Providers/`
- `Skills/`

Responsibilities:
- AgentExecutionContext.
- Intent detector/planner.
- Skill loader/router.
- SkillPolicy compiler.
- Provider registry.
- Create_database/Text_to_sql/Read_schema/Explain_query skills.

## Frontend-UX-Agent
Allowed paths:
- `Apps/Web/`

Responsibilities:
- Chat-first UI.
- Left sidebar.
- Main chat area.
- Right execution sidebar.
- Connection modals.
- Safety Report UI.
- 4-digit confirmation UI.
- Recovery UI.
