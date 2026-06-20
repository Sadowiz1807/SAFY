# Hermes File Ownership

## Purpose
Prevent sub-agent file conflicts and define shared contract approval rules.

## Ownership Map
| Path | Owner |
|---|---|
| `Apps/Api/` | Backend-API-Agent |
| `Gateway/` | Backend-API-Agent |
| `Contracts/` | Backend-API-Agent |
| `DataStore/` | Runtime-Data-Agent |
| `State/` | Runtime-Data-Agent |
| `Audit/` | Runtime-Data-Agent |
| `Logging/` | Runtime-Data-Agent |
| `Data/` | Runtime-Data-Agent |
| `Configs/` | Runtime-Data-Agent primary; Architect-Agent review |
| `Guard/` | Guard-Tools-Sandbox-Agent |
| `Tools/` | Guard-Tools-Sandbox-Agent |
| `Toolsets/` | Guard-Tools-Sandbox-Agent |
| `Sandbox/` | Guard-Tools-Sandbox-Agent |
| `Database/` | Guard-Tools-Sandbox-Agent |
| `Docker/` | Guard-Tools-Sandbox-Agent |
| `Core/` | Agent-Skills-Provider-Agent |
| `Providers/` | Agent-Skills-Provider-Agent |
| `Skills/` | Agent-Skills-Provider-Agent |
| `Apps/Web/` | Frontend-UX-Agent |
| `Docs/` | Architect-Agent primary; Hermes controls `Docs/Hermes_Execution/` |
| `README.md` | Architect-Agent |

## Shared Contracts Requiring Hermes Approval
- API request/response schema.
- AgentExecutionContext.
- SkillResult.
- ToolResult.
- ErrorResponse.
- Config schema.
- `policies.yaml`.
- `toolsets.yaml`.

## Rules
- Sub-agents must not modify files outside assigned paths unless Hermes grants explicit permission.
- Assigned paths come from the task's `allowed_paths` in `04_TASK_BOARD.yaml`, not only from this ownership overview.
- `must_not_modify` in the task board is a hard block for that task.
- If two agents need the same file, Hermes assigns primary owner and reviewer.
- Security policy changes require Hermes validation and may require user decision.
- File ownership does not override `SAFY_source.md`.
