# SAFY Phase 5 Contracts

## Contract Status
Status: Approved for Phase 5 implementation. These contracts were originally planning documents and now define the canonical implementation baseline. They do not claim Phase 5 has already been implemented.

## Separation of Paths
Phase 5 has two independent execution paths:

| Path | Actor | Target | Allowed SQL | Required Gate |
| --- | --- | --- | --- | --- |
| Agent read-only query | AgentCore | connected_database | Read-only only | Intent policy, SQL Guard, permission checker, adapter read-only proof |
| User query execution | Human user via UI/API | connected_database | According to profile permission and SQL Guard | `/query/check` then `/query/execute` |
| Sandbox creation | AgentCore | sandbox | Sandbox DDL only | SkillPolicy, SQL Guard, sandbox path confinement |

## Universal SQL Guard Contract
- Every SQL statement must be classified before execution.
- SQL Guard must run before adapter access.
- SQL Guard must fail closed on parse ambiguity, multi-statement mutation, unsupported dialect features, or unknown risk.
- `/query/check` must not execute SQL.
- Any execution attempt without a current check state must return an explicit blocked error.

## Agent Connected Database Contract
- Agent connected database SQL must be read-only.
- Agent must never execute DML, DDL, destructive, admin, privilege, transaction-control, maintenance, or extension-management SQL against connected databases.
- Agent must not request, store, or return raw database passwords, tokens, API keys, or connection-string credentials.
- Agent responses must include enough provenance for review: target, database profile id, SQL hash, audit id when available, and redacted summary.
- Agent destructive connected database requests must return a blocked result, not a confirmation prompt.

## User Query Contract
- User query execution remains user-controlled through `/query/check` and `/query/execute`.
- `/query/check` returns `check_id`, `sql_hash`, `target`, `database_profile_id`, risk details, decision, expiry, and confirmation metadata when required.
- `/query/execute` must require matching `check_id`, `sql_hash`, `target`, and `database_profile_id`.
- Check state is one-time and expires.
- User cancellation consumes or closes the check state according to the implementation contract.

## High-risk Confirmation Contract
- Confirmation code generation is backend-only.
- Code must be random numeric code or stronger project-approved equivalent.
- Code must bind to `check_id`, `sql_hash`, `target`, `database_profile_id`, and expiry.
- Code must be one-time.
- Code generation, validation success, validation failure, expiration, and consumption must be audited with redaction.
- LLM/model output must never generate, validate, or bypass confirmation codes.

## Secret Handling Contract
- JSON profile stores may contain only env references such as `api_key_env` or `password_env`.
- API responses must never include raw secrets.
- Logs and audit metadata must be redacted before persistence.
- Test fixtures and docs must use placeholders, not real credentials.
- Connection strings with embedded passwords must not be stored or returned.

## Audit Contract
Audit events must record decisions and evidence without secrets:

- `query_check`
- `confirmation_code_generated`
- `query_execute_pre`
- `query_execute_blocked`
- `query_execute_post`
- `agent_connected_readonly_check`
- `agent_connected_readonly_execute`
- `agent_connected_blocked`

Required audit fields: event type, action, target, database profile id, SQL hash, decision/status, redacted metadata, timestamp.
