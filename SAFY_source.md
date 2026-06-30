# SAFY Phase 12 Official Production Runtime — 2026-06-29

Status: The GPT-like Runtime Kernel is now the official production path.

Official runtime command:

```powershell
cd C:\Users\ASUS\SAFY
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONPATH = (Get-Location).Path
& "C:\Program Files\Python312\python.exe" -m Apps.Api.safy_api.cli run --port 8000
```

Production ownership:
- `Apps/Api/safy_api/app_factory.py` creates the official FastAPI app used by the CLI.
- `Apps/Api/safy_api/main.py` is app wiring/compatibility only and imports the official app factory.
- Route-owner modules are primary for `/chat`, `/agent/chat`, `/query/check`, `/sandbox-rules/*`, `/runtime/health`, files, sessions, and auth/profile support.
- `Runtime/live_runtime.py` is the canonical Runtime Kernel owner for session, memory, sandbox, rules, skills, context builder, and event bus.
- `Runtime/meta.py` is removed; import scan for `Runtime.meta` is clean.
- `run_strict_runtime.py` is retained only as a dev/test harness; it is not the official production path.
- Dashboard assets are mounted by the official app and use relative API URLs on port 8000, not hardcoded 8100.

Safety invariants remain unchanged:
- AI drafts/plans/explains but never auto-executes real DB changes.
- Check Safety is required before Execute.
- User explicit Execute is required for real DB execution.
- Active sandbox rules affect SQL generation and deterministic safety checks.
- Rule conflicts are user-decision states; rules do not auto-modify real schema.
- Prompt/context files and sandbox rule files remain separate flows.
- Errors use SAFY JSON envelopes with request_id.

Phase 12 evidence:
- Final report: `Reports/SAFY_PHASE12_OFFICIAL_PRODUCTION_FINAL_REPORT_2026-06-29.md`
- UAT CSV: `Tests/SAFY_PHASE12_OFFICIAL_PRODUCTION_UAT_RESULTS_2026-06-29.csv`
- Evidence folder: `Tests/evidence/2026-06-29/phase12-official/`

---

# SAFY Canonical Source

SAFY is a bounded, human-in-the-loop AI database safety agent. This document is the technical Source of Truth for runtime ownership and contracts. Current application version: `1.2.0`.

## System Boundaries

Runtime authority is:

```text
Dashboard / CLI
→ FastAPI (`Apps/Api/safy_api/main.py`)
→ AgentRuntime (`Agent/agent_runtime.py`)
→ deterministic safety core (`Gateway/`, `Sandbox/`, `Audit/`)
```

Legacy `AgentCore`, legacy intent files, and `Providers/` are not active runtime authority.

## Module Ownership

- `Apps/Web/`: Dashboard, login, Schema Graph UI, responsive layout, browser safety-binding state.
- `Apps/Api/safy_api/`: FastAPI routes, request/response envelopes, profile APIs, query check/execute endpoints.
- `Agent/agent_runtime.py`: bounded workflow orchestration and state recording.
- `DomainIntelligence/`: compiled domain catalog, domain resolution, schema draft workflow.
- `LLM/`: OpenAI-compatible provider profiles/adapters; timeout is `request_timeout_seconds = 180`.
- `Gateway/`: SQL normalization, policy, driver/dialect resolution, query orchestrator, database drivers.
- `Sandbox/`: sandbox lifecycle and SQL validation.
- `Audit/`: structured audit storage and redaction.
- `DataStore/`: profile/session/schema graph persistence contracts.
- `Tests/`: regression, integration, UI helper, packaging and Source-of-Truth tests.
- `Reports/` and `Tests/evidence/`: task reports and sanitized evidence only.

## Request Flow

```text
User request
→ Dashboard command or CLI
→ FastAPI envelope
→ AgentRuntime finite workflow
→ optional model/domain draft (UNTRUSTED_DRAFT)
→ Execute Box draft
→ /query/check
→ sandbox validation and immutable check artifact
→ explicit user Execute
→ /query/execute binding validation
→ real database driver/RPC
→ audit and UI result
```

## AgentRuntime Scope

AgentRuntime may resolve intent, ask clarification, call bounded tools, request model drafts, populate Execute Box, and record workflow history. It cannot approve real execution, weaken policy, bypass sandbox, or retry unknown database writes.

## LLM Boundary

All LLM output is `UNTRUSTED_DRAFT`. The model may draft SQL/schema and narrative, but deterministic parsing, policy, sandbox, binding and execution decide whether anything can run.

## Domain Resolution

`DomainIntelligence/packs/registry.json` is the runtime domain catalog. Clear domains can be selected; ambiguous, unknown, typo, or multi-domain requests ask clarification. SAFY must not default ambiguous schema creation to e-commerce.

## Execute Box Contract

The Execute Box is the canonical editable SQL draft. Chat artifacts are read-only snapshots. Check Safety operates on the exact current Execute Box SQL. Manual edits invalidate previous checks.

## Policy Engine

The deterministic SQL policy blocks destructive/admin/unknown operations unless a separately designed workflow exists. CREATE TABLE and CREATE INDEX can be drafted and sandbox-validated; server-level `CREATE DATABASE`, DROP, TRUNCATE, GRANT, REVOKE, role/user/admin, procedure/function/policy, unsafe transaction control, and mixed unsafe batches fail closed.

## Sandbox Lifecycle

Save/activate may ensure or resolve a sandbox when a DBMS has an adapter. Sandbox errors must be specific: `DOCKER_DAEMON_NOT_RUNNING`, `SANDBOX_CONTAINER_NOT_RUNNING`, `SANDBOX_CONTAINER_MISSING`, `SANDBOX_RECOVERY_FAILED`, `SANDBOX_HEALTHCHECK_FAILED`, `SANDBOX_SQL_VALIDATION_FAILED`. `executed_in_sandbox=true` only when SQL was actually sent to the sandbox database.

## Check Artifact Schema

A valid check artifact includes at least:

```text
check_id
sql_hash
target
database_profile_id
sandbox_id
chat_id/session_id context via request binding
context_generation
schema_generation
driver
dialect
user_query_access_mode
expires_at
safety_status
check_passed
allowed_to_attempt
sandbox_validated
```

The backend is authority; browser state is only a convenience cache.

## Execute Binding

Execute requires a valid unexpired, unconsumed check. The submitted SQL hash, profile, sandbox, target, context generation, schema generation, driver, dialect, chat/session binding and target must match the check. Frontend invalidates the binding before dispatching Execute. Backend consumes the check before real user-controlled execution attempts.

## Database Profile Contract

Profiles distinguish:

```text
provider
connection_kind
transport
driver
dbms
dialect
sandbox_adapter
capabilities
live_certification
```

`driver != dialect`. `supabase_rpc` is a driver/transport path. `postgresql` is the DBMS/dialect for Supabase PostgreSQL. MariaDB aliases to MySQL where supported.

## Supabase RPC Contract

Canonical write/DDL RPC:

```text
function: safy_execute_sql
argument: sql
signature: public.safy_execute_sql(sql text)
```

The driver sends PostgREST body `{ "sql": "..." }`. `sql_text` is not canonical for this function.

## Audit Contract

Audit records must include request/check correlation, profile/sandbox/driver/dialect, policy decision, sandbox result and execution result where available. Audit must never store API keys, Authorization headers, service-role keys, passwords, full DSNs, raw secret env values, or unnecessary result rows.

## Error Taxonomy

Errors are structured envelopes. Examples: `QUERY_CHECK_REQUIRED`, `QUERY_CHECK_NOT_FOUND`, `QUERY_CHECK_EXPIRED`, `QUERY_CHECK_STALE`, `QUERY_SQL_HASH_MISMATCH`, `SANDBOX_SQL_VALIDATION_FAILED`, `SUPABASE_RPC_NOT_INSTALLED`, `MODEL_TIMEOUT`. Runtime failures must not be reported as success.

## UI State Model

Dashboard state mirrors server authority. Browser safety bindings are ephemeral and invalidated on SQL edit, new draft, profile/sandbox/session/chat change, reload, expiry, failed check, execute dispatch, or backend stale/mismatch response. Execute buttons must be physically disabled, not only restyled.

## Responsive Layout Rules

Desktop shell uses responsive grid concepts:

```css
grid-template-columns: minmax(220px, 300px) minmax(0, 1fr) minmax(340px, 460px);
```

Main grid/flex children must use `min-width: 0` and `min-height: 0`. Page shell must not create horizontal overflow. Header chips must wrap/ellipsis. At tablet/mobile breakpoints, sidebar becomes drawer/rail and Execute becomes a sheet/full-width panel.

## File Context Ingestion Boundary

File Prompt Reader V1 is context input, not policy authority. Uploaded `.txt`, `.md`, `.docx`, and text-based `.pdf` files are validated, stored outside the web static tree, extracted to text, and assembled into bounded prompt context. File content is treated as user-provided document data only; it cannot override system/developer/project safety instructions, cannot approve Check Safety, cannot approve Execute, and cannot change SQL policy.

## Business Rule Boundary

Current SAFY implements technical SQL safety policies and database constraints. A generic business-rule assertion engine, domain fixtures, post-condition queries, and policy-as-code plugins are not currently implemented.

The LLM may suggest a business rule, but deterministic code must evaluate it before any claim is treated as enforced.

## Testing Strategy

Every task must separate baseline dirty tree from task delta. Tests can be `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, `NOT_APPLICABLE`, or `NOT_RERUN_UNAFFECTED`. No PASS may be claimed for unrun cases. Browser layout tests must include overflow assertions and screenshots where possible. Real database tests must avoid destructive cleanup and must not auto-retry unknown writes.

## Packaging Rule

```text
<= 6 source files modified → send the modified source files
> 6 source files modified  → send a full clean project package
```

Reports/evidence/test CSVs are packaged with the handoff but do not count as source files. Packages must exclude `.env`, secrets, passwords, service-role keys, runtime sessions, sandbox data, database files, caches, `node_modules`, and secret-bearing logs.

## Context Files and Natural Database Task Routing

Uploaded prompt files are user context, not policy authority. The AI may use active prompt-context files to draft and explain, but deterministic SAFY boundaries remain authoritative: SQL policy, sandbox validation, Check Safety binding, Execute authorization and audit cannot be overridden by file content.

Context file metadata includes session/database/project scope foundations (`scope`, `source_type`, `chat_id`, `database_profile_id`, `sandbox_id`, `project_id`, `is_active`, `is_pinned`). V2 only activates prompt-context retrieval; future business-rule or sandbox-rule files require explicit rule activation and are not enforced by this task.

Natural language database tasks and `/Execute` commands route into the same safe database workflow. AI drafts and routes; deterministic safety checks; the user confirms Execute. Write, DDL and DML never auto-execute against the real database from a plain chat message.

## Context File Recall Core

Active prompt-context files are session-bound user context. SAFY resolves explicit `context_file_ids` first and falls back to active files bound to the current `chat_id` when the request omits explicit ids. Session-scoped files do not leak into other sessions or new chats, and detaching a file prevents later prompt injection.

File content is user-provided context, not policy authority. Prompt files can inform the agent and be recalled inside the active session, but they cannot approve Execute, override safety policy, or change deterministic guard behavior.

## Sandbox Rules V1

Sandbox rules are deterministic safety constraints scoped to database_profile_id + sandbox_id. Prompt/context files are not sandbox rules. Rule conflict is a user-decision state, not an auto-repair trigger. SAFY may propose additive schema drafts, but must not auto-execute or delete schema/data.


## GPT-like Runtime Restructure Note (2026-06-29)

SAFY is being moved toward a Runtime Kernel architecture: Session Manager, Memory Manager, Sandbox Manager, Rule Manager, Skill Registry, Context Builder, Event Bus, Request Planner, NL DB Intent Parser, Semantic Rules Engine, SQL Structural Safety Engine, Rule-aware SQL Draft Generator, Response Synthesizer, and Audit lifecycle. Safety invariant remains: AI drafts/plans only; deterministic checks and sandbox validation precede any real DB execution; explicit user Execute action is required; prompt/context files are separate from sandbox rules.

Current status: NOT READY. A foundational implementation slice and targeted tests were added, but the full 340-case UAT and runtime dashboard verification are not complete.
