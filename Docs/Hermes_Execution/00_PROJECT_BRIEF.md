# Safy Hermes Project Brief

## Purpose
Stage 0 source-of-truth brief for Hermes main-agent orchestration.

## Source Used
- `C:\Users\ASUS\SAFY\Docs_prior_project\SAFY_source.md`
- `HERMES_MAIN_AGENT_EXECUTION_PLAN.md`

## Product Mission
Safy is an AI Agent assisted DBMS design, initialization, and query system with sandbox-first execution and strict safety boundaries.

## Current Source-of-truth
`SAFY_source.md` remains the current source-of-truth. The Hermes plan adds orchestration/UI/query workflow decisions from the user and must not weaken existing source safety rules.

## Mandatory User Decisions
- UI is chat-first with left sidebar and right execution sidebar.
- Left sidebar contains session history, new session, settings, model connection, and database connection.
- Main area contains chat, prompt box, agent responses, technical explanations, and schema explanations.
- Right sidebar contains agent result/execution panel and user query execution box.
- Agent execution path: connected database always read-only; write/DDL only in sandbox.
- User query path: user-controlled through right sidebar query box; executes according to selected credential permission after check/confirmation/audit.
- `/query/check` never executes SQL.
- High-risk user query execution requires backend-generated random 4-digit numeric confirmation code.
- Model profile save writes raw API key to `.env`; JSON stores only `api_key_env`; response never returns raw key.
- Database profile save writes raw password to `.env`; JSON stores only `password_env`; response never returns raw password.
- Profile overwrite requires explicit confirmation.
- Secrets entered from UI are saved permanently into local `.env` and `.env` must be gitignored.
- Agent behaves adaptively; no quick-or-guided mode switch.
- Default domain is e-commerce when user asks to create a database without specifying a domain, and agent states the assumption.
- Hermes reports by stage gate.

## Non-negotiable Security Rules
- Agent cannot mutate connected databases.
- Manual/user query path is separate from agent path.
- Raw secrets must not be stored in JSON, logs, audit, runtime DB, API response, or frontend state beyond form entry.
- High-risk user query execution requires valid prior check, Yes decision, and 4-digit code.
- LLM cannot generate or validate confirmation codes.
- LLM cannot override SkillPolicy, ToolRegistry, SQL Guard, or Permission Checker.
- Safy v1.0.0 must not become a multi-user SaaS runtime.

## Stage 0 Status
This brief freezes user decisions for sub-agent tasking and validation gates.
