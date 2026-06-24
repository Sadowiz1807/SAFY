# SAFY Source Map

**Document status:** `CURRENT`  
**Purpose:** Canonical ownership map for SAFY product/runtime source.  
**Operational snapshot:** Read `current_state.md` immediately after this file.

## Authority

- Explicit current user decisions are highest priority.
- `SOUL.md` owns non-negotiable product and safety rules.
- This file owns canonical runtime source locations and module ownership.
- `current_state.md` records the implemented/verified state of those sources.
- `Safy_Docs/` files are target specifications unless `current_state.md` marks the capability implemented.
- `Docs/Hermes_Execution/report/` files are historical patch evidence only.

## Canonical runtime source files

### API and application composition

- `Apps/Api/safy_api/main.py`: FastAPI routes, auth/profile lifecycle, context fetch boundary, agent APIs, query check/execute APIs, sandbox APIs, and Schema Graph APIs.
- `Apps/Api/safy_api/schemas.py`: API request models.
- `Apps/Api/safy_api/cli.py`: `safy run` and CLI behavior.

### Web UI

- `Apps/Web/login.html` + `Apps/Web/login.js`: login page.
- `Apps/Web/dashboard.html` + `Apps/Web/dashboard.js`: dashboard, chat, profile controls, context sources, Execute Box, and sidebar behavior.
- `Apps/Web/schema-graph.html` + `Apps/Web/schema-graph.js`: dedicated Schema Graph implementation served at `/Dashboard/{schema_ui_name}`, replacing the Dashboard view while preserving browser Back navigation; owns grid rendering, node dragging, relationship redraw, pan, and cursor-centered zoom.
- `Apps/Web/styles.css`: shared UI styles.
- `Apps/Web/index.html`: compatibility redirect to login.
- `Apps/Web/safy-ui.js`: compatibility shim for stale cached dashboard HTML; the maintained implementation is `dashboard.js`.

`Apps/Web_backup_before_split/` is backup-only and is not runtime source.

### Agent and workflow

- `Agent/agent_runtime.py`: unified agent workflow orchestration, including bounded compiled-domain context routing before SQL draft generation.
- `Agent/schema_context.py`: schema context summarization.
- `Core/`: workflow state, context packs, skill loading/registry/actions, planning, policy, and deterministic review.
- `DomainIntelligence/`: compiled SAFY domain-pack contracts, compiler, registry, router, retriever, context builder, cache, security checks, CLI handlers, and canonical artifact subdirectories: `packs/`, `reports/`, and `work/`. Root-level `DomainBuild/` and `DomainPacks/` are not current runtime source locations.
- `Skills/`: canonical skill directories and `SKILL.md` filenames are lowercase directory names plus uppercase `SKILL.md`; `Scripts/normalize_skill_git_case.ps1` is the one-time Windows Git-index migration helper.
- Wheel resources are declared in `pyproject.toml`; bundled runtime assets include `Configs/`, `Apps/Web/`, `Skills/`, and `DomainIntelligence/packs/`.
- `Scripts/package_clean_handoff.py` is the canonical secret-safe source handoff packager; do not archive the repository root manually.

### Database safety and execution

- `Gateway/query_orchestrator.py`: authoritative SQL check, sandbox validation, one-time check binding, and real execution gate.
- `Gateway/sql_normalizer.py`: SQL normalization.
- `Gateway/sql_classifier.py`: SQL classification.
- `Gateway/statement_target_extractor.py`: statement target extraction.
- `Gateway/risk_analyzer.py`: risk classification.
- `Gateway/permission_checker.py`: saved profile permission enforcement.
- `Gateway/real_db_policy.py`: agent-direct real database read-only policy.
- `Gateway/db_drivers/`: provider/driver routing and real database drivers.

### Sandbox, state, profiles, and audit

- `Sandbox/sandbox_manager.py`: sandbox lifecycle and validation.
- `Sandbox/docker_manager.py`: Docker runtime management.
- `Sandbox/restore_manager.py`: restore validation and bounded extraction.
- `State/`: session/runtime persistence and sanitized workflow state.
- `Audit/`: audit schema/store/logger.
- `Logging/redact.py`: redaction boundary.
- `DataStore/`: profile, environment secret reference, and Schema Graph persistence.

### Skills and tools

- `Skills/`: document-driven skill packs. The current canonical SQL skill name is `text_to_sql`.
- `Configs/skills.yaml`: skill loading configuration.
- `Tools/` and runtime registration in `Agent/agent_runtime.py`: shared tool implementations and metadata.
- `Configs/toolsets.yaml`: declarative toolset/policy mirror; it does not override the QueryOrchestrator.

## Runtime data boundary

Runtime data is stored under `Data/` and is intentionally resettable. Secrets, sessions, sandboxes, local databases, caches, logs, and generated runtime state must not be treated as source code or committed with real values.

## Required reading order for agents

```text
SOUL.md
→ SAFY_source.md
→ current_state.md
→ relevant source files
→ relevant tests
```
