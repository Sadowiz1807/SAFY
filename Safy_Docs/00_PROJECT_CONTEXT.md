# Safy Project Context

## Purpose
This document gives new agents and developers the baseline context for Safy so they do not implement outside the approved v1.0.0 scope.

## Scope
Covers product identity, scope, non-goals, source-of-truth rules, and decisions that must not be weakened during implementation.

## Source Reference
Source-of-truth: `SAFY_source.md`, last reviewed version in `Docs_prior_project`.

## 1. Project Identity
Safy is an AI Agent assisted database design, initialization, and query system. It helps users design database schemas, generate SQL, create and inspect safe sandbox DBMS workspaces, and query approved connected databases under strict policy controls.

Safy is not a general autonomous database administrator. Safy is a policy-driven local/development tool where LLM output is only a proposal and all execution must pass deterministic validation.

Core identity:
- Safy is an AI Agent for designing, initializing, and querying DBMS safely.
- Safy validates generated SQL before execution.
- Safy executes write/DDL only in sandbox workspaces for agent workflows.
- Safy treats connected databases as strict read-only for agent workflows.
- Safy records important actions through audit and runtime state.

## 2. Problem Statement
Database design work often mixes natural-language requirements, domain rules, schema design, SQL generation, environment setup, and validation. LLMs can accelerate this work, but raw LLM SQL is unsafe because it may be wrong, destructive, dialect-incompatible, or influenced by prompt injection or database content.

Safy solves this by combining:
- Requirement analysis and domain rule packs.
- Deterministic SQL Guard and permission policy.
- Sandbox-first execution and verification.
- Connected database read-only access for agent workflows.
- Manual SQL Console for explicit user-driven high-risk actions.
- Audit records and redaction.

## 3. Product Goal
The product goal is to let a local/development user safely ask an AI agent to design, create, inspect, and query databases while preventing unreviewed destructive actions against connected databases.

Design principle:

```txt
LLM suggests, Safy verifies, Sandbox tests, Policy decides, Audit records.
```

## 4. v1.0.0 Scope
Safy v1.0.0 is a single-user local/development app. It may generate schemas for multi-tenant SaaS applications, but Safy itself is not a multi-user SaaS runtime in v1.0.0.

In scope:
- Local frontend and FastAPI backend.
- Agent chat and explicit chat/session lifecycle.
- Sandbox workspace creation for PostgreSQL/MySQL through Docker.
- SQLite runner only when target DBMS is SQLite.
- Connected database test connection and read-only SELECT/EXPLAIN execution for agent workflows.
- Manual SQL Console as user-driven execution path with confirmation, SQL Guard, audit, and profile policy.
- Runtime SQLite DB and audit SQLite DB.
- User/database profile JSON files that store env variable names, not raw secrets.
- create_database, text_to_sql, schema_graph, and query_explain skill behavior.

## 5. Out of Scope
Out of scope for v1.0.0:
- Multi-user SaaS runtime for Safy itself.
- Production-grade hosted service guarantees.
- HIPAA, PCI, GDPR, or other compliance certification claims.
- Autonomous write/DDL against connected databases by the agent.
- Using SQLite as a fallback validator for PostgreSQL/MySQL SQL.
- Storing raw API keys, DB passwords, or raw SQL with sensitive literals in JSON/runtime/audit by default.

## 6. Core Design Philosophy
Safy must be conservative where execution is risky and helpful where design is exploratory.

Core philosophy:
- Prefer sandbox execution for generated DDL/DML.
- Treat every LLM output as untrusted until validated.
- Treat database content as untrusted input.
- Use deterministic policies for execution decisions.
- Keep credentials outside JSON and outside frontend state.
- Audit high-risk operations before execution.
- Preserve enough runtime state to recover workspaces safely, but avoid durable active connection handles.

## 7. Critical Distinctions
These distinctions are non-negotiable:
- Apps/Api is the FastAPI HTTP layer; Gateway coordinates application use cases.
- Core is orchestration and reasoning; Providers are transports/model/database adapters.
- Skill is workflow instruction; Tool is executable capability.
- State is runtime lifecycle data; DataStore is persistence access.
- Audit is security/action record; system logging is operational debugging.
- Sandbox execution is separate from connected database execution.
- Agent workflow is separate from Manual SQL Console.
- Manual SQL Console is user-driven, not agent-driven.

## 8. Source-of-Truth Rules
`SAFY_source.md` is the current source-of-truth. Older drafts or reference packages may provide background only and must not override decisions in `SAFY_source.md`.

Rules:
- Do not weaken mandatory security policy into recommendation language.
- Do not remove implementation-relevant decisions because they are long.
- If source conflicts are found later, report them instead of silently choosing unsafe behavior.
- Generated implementation docs must preserve the second-pass hidden conflict fixes already applied to `SAFY_source.md`.

## 9. Recommended Reading Order
Recommended order:
1. `00_PROJECT_CONTEXT.md`
2. `01_ARCHITECTURE.md`
3. `05_SECURITY_POLICY.md`
4. `10_RUNTIME_AND_SANDBOX_SPEC.md`
5. `03_DATA_SCHEMA.md`
6. `04_CONFIG_SPEC.md`
7. `02_API_SPEC.md`
8. `06_DATABASE_DESIGN_POLICY.md`
9. `07_DOMAIN_RULE_PACKS.md`
10. `08_SKILLS_SPEC.md`
11. `09_TOOLS_SPEC.md`

## 10. Non-negotiable Decisions
Non-negotiable decisions:
- Safy v1.0.0 is single-user local/development software.
- Agent write/DDL is allowed only in sandbox workflows.
- Agent connected_database path is strict read-only.
- Manual SQL Console is explicit user-driven execution, not agent-driven execution.
- High-risk Manual SQL requires confirmation and audit pre-write.
- High-risk audit pre-write failure is fail-closed.
- Tool calls must pass ToolRegistry, Permission Checker, SQL Guard, and Risk Analyzer where applicable.
- Toolsets YAML is source-of-truth; Python wrappers must not independently add tools.
- Raw SQL is not persisted by default.
- Raw API keys and DB passwords are never stored in JSON/runtime/audit/frontend/API responses.
- Safy must not claim HIPAA/PCI/GDPR compliance.

## Implementation Notes
Implementation should build from policy outward: configs and schemas first, then tool registry, then SQL Guard, then agent workflows. Any feature that cannot pass policy should be blocked by deterministic code, not by prompt wording.

## Related Documents
- `01_ARCHITECTURE.md`
- `03_DATA_SCHEMA.md`
- `04_CONFIG_SPEC.md`
- `05_SECURITY_POLICY.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`
