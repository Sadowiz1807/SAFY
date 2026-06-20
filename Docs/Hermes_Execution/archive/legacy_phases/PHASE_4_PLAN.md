# Phase 4 Plan - Agent Core, Skills, Provider, Create Database

Status: PLANNING_READY_NOT_DISPATCHED
Implementation dispatch: BLOCKED until explicit user approval.

## Scope

Phase 4 plans provider registry/model client, Agent Core, real `/agent/chat`, intent detection/planning, skill loader/router, deterministic `SkillPolicy`, ToolExecutor, domain rule pack, sandbox workflow, runtime/audit/provenance integration, result summarizer, and Create_database workflow that creates a sandbox schema and returns UI technical result.

## Out Of Scope

- Connected database write execution.
- Connected database read-only agent query execution; this is deferred to Phase 5.
- Visualization/dashboard generation is out of scope for Phase 4 and is not assigned to Phase 6 unless later approved.
- Real LLM provider calls during planning.
- Runtime DB/audit DB modification during planning.
- Apps/Web UI changes during planning.
- SQL execution during planning.

## Required Order

1. Provider contracts and mock provider.
2. Agent Core data contracts.
3. Skill loader/router and `SkillPolicy` compiler.
4. Domain rule pack contract.
5. Tool registry/executor policy envelope.
6. Create_database skill contract.
7. Sandbox workspace + SQL validation + schema readback contracts.
8. Result summarizer and Safy envelope response contract.
9. Runtime/audit/provenance integration contract.
10. `/agent/chat` API integration contract.
11. Tests and validation gates.

## Non-Negotiable Boundaries

- LLM/provider output is never executable by itself.
- Every generated SQL statement must go through SQL Guard before execution.
- `ToolExecutor` is the only tool execution path.
- `Skill.md` is instruction, not authority; `SkillPolicy` is deterministic enforcement.
- Create_database may execute only in sandbox workspace.
- Connected database agent execution, including read-only connected DB query, is out of scope for Phase 4 and deferred to Phase 5.
- Raw secrets must not be returned, logged, audited, or sent to provider.

## Domain Rule Pack Plan

- Define a deterministic domain rule pack for `create_database` so missing domain defaults to e-commerce.
- Include canonical e-commerce entities such as users/customers, products, categories, orders, order_items, payments, and addresses unless user prompt narrows scope.
- Record assumptions in `data.assumptions` and audit/provenance metadata.
- Keep rule packs declarative and non-authoritative; `SkillPolicy` still controls tools and targets.
- Add validation that generated names pass identifier sanitizer and relationship rules before SQL generation/execution.

## API Integration Plan

- `/agent/chat` accepts chat/message/model profile/database profile/target/options but Phase 4 permits only sandbox Create_database execution.
- `/agent/chat` response must use Safy envelope: `success`, `data`, `error`, `meta`.
- Keep `technical_result` inside `data`.
- Error responses must be structured and redacted.
- Existing `/query/check` and `/query/execute` safety semantics remain unchanged.

## UI Technical Result Compatibility

- The API must return fields the existing UI can render without Phase 4 UI implementation: `workflow_id`, `workspace_id`, `intent`, `summary`, `assumptions`, `risk_level`, and `technical_result`.
- `technical_result` must include target, dialect, tables, relationships, validation summary, SQL visibility flag, and schema readback status.
- No generated secret, provider credential, DB credential, or connection string may be displayed.
- Phase 4 does not add quick/guided mode UI.

## Runtime/Audit/Provenance Integration

- Runtime state must track workflow id, chat id, target, workspace id, policy id/version, provider profile id, skill name/version, result status, and redaction status.
- Audit must record tool attempts, policy decisions, SQL Guard result metadata, sandbox workspace id, and final outcome.
- Provenance must link the user prompt, domain assumptions, provider/mock output id, SQL Guard decision, schema readback, and response metadata.
- Audit/provenance must store redacted references, not raw secrets or full unredacted provider prompts.

## Create Database Target Workflow

1. `/agent/chat` receives prompt and profile/context ids.
2. Agent Core creates `workflow_id` and `AgentExecutionContext`.
3. Intent detector returns `create_database` or asks for critical missing details only.
4. If domain is missing, planner applies default e-commerce and states assumption.
5. Skill router loads Create_database skill.
6. SkillPolicy compiles toolset allow-list: sandbox, sql_guard, db_core, audit.
7. Provider receives minimized/redacted prompt and returns schema plan/DDL candidate.
8. Agent Core validates provider output as untrusted data.
9. ToolExecutor sanitizes identifiers.
10. ToolExecutor validates SQL via SQL Guard using target dialect.
11. Permission checker verifies sandbox-only execution.
12. ToolExecutor creates sandbox workspace.
13. ToolExecutor executes validated sandbox SQL.
14. ToolExecutor reads schema back and compares to plan.
15. Runtime/audit/provenance records workflow metadata with redaction.
16. Result summarizer builds Safy envelope with `technical_result` inside `data`.

## Testing Strategy

- Unit tests for provider registry, mock provider, intent detection, domain rule pack, Skill loader/router, SkillPolicy compiler, ToolExecutor policy enforcement, and result summarizer.
- Integration tests for `/agent/chat` create database sandbox success and Safy envelope shape.
- Security tests for connected DB read/write denial, SQL Guard bypass denial, unknown tool denial, prompt injection resistance, and secret redaction.
- Regression tests for Phases 1-3 must remain passing after implementation.
- Validation task must include artifact checks proving all Phase 4 implementation tasks remain blocked until explicit user approval.

## Open Decisions

- Whether real provider transport is implemented in Phase 4 after mock provider tests or deferred behind a separate approval gate.
- Exact sandbox backend order: existing mock/SQLite-compatible harness first versus Docker PostgreSQL/MySQL later.
- Whether `return_sql` is ever enabled in Phase 4 responses; default remains false.
- Runtime/audit storage schema details must be confirmed before implementation.

## Stop Conditions

- Any need to execute connected database reads/writes from agent workflow.
- Any need to bypass SQL Guard or ToolExecutor.
- Any need to store, display, log, audit, or send raw secrets to provider.
- Any need to implement UI changes during planning.
- Any need to dispatch implementation before explicit user approval.
- Any conflict with Phase 0-3 PASS behavior.

## Definition Of Done

Phase 4 implementation is complete only when all future implementation tasks pass their gates and a create database prompt produces a sandbox schema and UI technical result in the Safy envelope, with tests proving no connected database execution, no SQL Guard bypass, deterministic SkillPolicy enforcement, secret redaction, audit/provenance recording, and Phase 1-3 regression safety.

## Completion Gate

Planning completion requires all Phase 4 artifacts to be internally consistent, non-dispatchable, double-checked read-only, and free of unresolved P0/P1/P2 planning conflicts.
