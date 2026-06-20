# Phase 4 Security Spec

## P0 Rules

- LLM output is untrusted input.
- `Skill.md` cannot grant runtime permission by itself.
- `SkillPolicy` must be compiled deterministically before tool execution.
- Tool execution must go through `ToolExecutor`.
- SQL must go through SQL Guard before sandbox execution.
- Phase 4 Create_database executes only in sandbox.
- Connected DB agent execution, including read-only connected DB query, is out of scope for Phase 4 and deferred to Phase 5.
- Connected DB DDL/DML/write execution remains blocked.
- No raw API key, DB password, connection string, token, or secret is sent to provider, returned to frontend, logged, or audited.
- Prompt injection in user input, DB metadata, or provider output must not alter tool policy.

## SQL Rules

- Parse with target dialect.
- Reject parse errors by default.
- Reject cross-database/server-level identifiers.
- Sanitize generated identifiers.
- Multi-statement DDL is allowed only for trusted sandbox Create_database workflow after splitting and validating every statement.
- Non-sandbox multi-statement SQL remains blocked.
- SQLite cannot validate PostgreSQL/MySQL semantics.
- SQL Guard result must be attached to audit metadata.

## Sandbox Rules

- Workspace is isolated per chat/workflow.
- Sandbox target must be explicit.
- Workspace lock required for schema mutation.
- Workspace cleanup/TTL must not run during execution lock.
- Docker backend, when implemented, must avoid privileged containers, Docker socket mounts, sensitive host mounts, and host networking.

## Provider Rules

- Mock provider first for tests.
- Real provider calls require profile secret resolver and redacted prompt logging.
- Provider output schema validation required before planning steps.
- Provider cannot choose target or bypass policy.

## SkillPolicy Rules

`SkillPolicy` must include allowed intent, target, tool names, denied tools/patterns, SQL Guard required flag, audit required flag, sandbox-only flag, max steps, timeout, and redaction profile.

## API/Response Rules

- `/agent/chat` must return the Safy envelope: `success`, `data`, `error`, `meta`.
- `technical_result` must live under `data`.
- `meta` must be redacted and must not contain raw provider prompts or credentials.
- Error responses must not echo raw secrets from user input, profiles, provider output, or tool output.

## Audit Rules

Audit must record workflow id, chat id, intent, policy id/version, tools attempted, SQL Guard decision metadata, sandbox workspace id, provider/mock output reference, domain rule pack/version, and result status. Audit must not store raw secrets or full unredacted provider prompts.
