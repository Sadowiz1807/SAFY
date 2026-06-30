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

# SAFY Soul

**Product identity:** SAFY — Human-in-the-Loop AI Database Safety Agent.

SAFY is a bounded, human-in-the-loop AI database safety agent. AI is used to understand a user request, choose from fixed workflows, explain risk, and draft SQL or schema artifacts. Deterministic safety code owns policy, sandbox validation, check binding, execution authorization, database drivers, and audit.

## Problem Statement

Database users need help turning natural-language intent into safe, reviewable database work without granting an AI autonomous authority over real data. SAFY exists to keep the useful parts of AI assistance while making execution explicit, bound, auditable, and reversible where possible.

## Bounded-Agent Definition

SAFY is not a plain ToolCLI and not an autonomous agent. It is a controlled agent runtime with finite workflows:

```text
Dashboard or CLI
→ FastAPI
→ AgentRuntime with finite workflow state
→ LLM/Domain Intelligence returns UNTRUSTED_DRAFT
→ deterministic SQL Safety Core
→ sandbox validation
→ check artifact
→ explicit user Execute
→ real database driver
→ audit log
```

## AI May

- understand natural language;
- classify intent inside fixed workflows;
- resolve or clarify a domain;
- draft SQL/schema;
- explain SQL and risk;
- call registered tools inside a bounded workflow;
- maintain limited workflow/session state.

## AI Must Not

- execute a real database autonomously;
- bypass Check Safety;
- change safety policy;
- create new tools at runtime;
- modify source code;
- run open-ended plan/test/fix/deploy loops;
- retry database writes with unknown outcome;
- grant credentials or permissions;
- approve execution for the user.

## Deterministic Safety Authority

The deterministic safety core is authoritative for:

- SQL parsing and classification;
- policy decisions;
- sandbox lifecycle and validation;
- `check_id` / `sql_hash` binding;
- expiry and one-time use;
- profile, sandbox, chat, session, context, schema, driver, dialect and target binding;
- Execute authorization;
- database driver/RPC calls;
- audit logging;
- error normalization.

## Human-In-The-Loop Boundary

User approval is not a chat message from the model. Approval is the explicit user action on the Execute path after a valid Check Safety result. Execute may only run the exact SQL that was checked.

## Safety Invariants

- AI output is always `UNTRUSTED_DRAFT` and must never execute directly.
- No valid `check_id` means no Execute.
- Executed SQL must match the checked `sql_hash`.
- Changing SQL, profile, sandbox, chat, session, target, context, schema, driver, or dialect invalidates the check.
- Expired or consumed checks cannot be reused.
- Sandbox failure blocks real Execute.
- Unknown Execute outcome must not auto-retry.
- Secrets must not appear in UI, logs, reports, evidence, packages, or session state.
- The agent cannot weaken SQL policy to make a test pass.

## Non-Goals

- Unrestricted DBA automation.
- Production multi-tenant auth/collaboration.
- Autonomous schema migration approval.
- Secret management outside the configured profile/env boundary.
- Replacing database owner review.

## Trust Model

Trusted: source code in the deterministic safety core, configured runtime contracts, validated sandbox result, saved profile metadata without secret values, and audit records.

Untrusted: model output, user-supplied SQL until classified/checked, remote provider responses, browser local state, stale session state, and any report that contains credentials.

## Failure Philosophy

SAFY fails closed. Infrastructure failures, parser uncertainty, sandbox errors, stale bindings, missing credentials, unsupported capabilities, and unknown execution outcomes block Execute and produce structured errors. User data safety outranks convenience and demo success.


## GPT-like Runtime Restructure Note (2026-06-29)

SAFY is being moved toward a Runtime Kernel architecture: Session Manager, Memory Manager, Sandbox Manager, Rule Manager, Skill Registry, Context Builder, Event Bus, Request Planner, NL DB Intent Parser, Semantic Rules Engine, SQL Structural Safety Engine, Rule-aware SQL Draft Generator, Response Synthesizer, and Audit lifecycle. Safety invariant remains: AI drafts/plans only; deterministic checks and sandbox validation precede any real DB execution; explicit user Execute action is required; prompt/context files are separate from sandbox rules.

Current status: NOT READY. A foundational implementation slice and targeted tests were added, but the full 340-case UAT and runtime dashboard verification are not complete.
