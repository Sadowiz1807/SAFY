# SAFY Current State

**Document status:** `CURRENT` / operational implementation snapshot  
**Project:** SAFY — Local AI Database Agent and Database Safety Gateway  
**Application version:** `1.2.0`  
**Snapshot date:** `2026-06-25`  
**Primary audience:** Hermes and any coding/review agent working on SAFY  
**Required action:** Read this file before planning, editing, testing, or packaging SAFY.

---

## 0. Purpose and non-conflict rule

This file records the **currently implemented and verified state** of SAFY. It is not a new product specification and must not silently redefine product or security policy.

Use this authority order when information differs:

1. Explicit current user decisions.
2. `SOUL.md` for non-negotiable product and safety contract.
3. `SAFY_source.md` for canonical source ownership and runtime entry points.
4. `current_state.md` for implemented status, verified behavior, known limitations, and the next safe work boundary.
5. `README.md` for setup and operator instructions.
6. `Docs/SAFY_AGENT_WORKFLOW_ARCHITECTURE.md` and `Docs/SAFY_TOOL_REGISTRY_AND_REVIEWERS.md` for current architecture details.
7. `Safy_Docs/` files are target/specification documents unless their content is explicitly marked implemented here.
8. `Docs/Hermes_Execution/` root files are process/planning artifacts.
9. `Docs/Hermes_Execution/report/` files are patch history and evidence only.
10. Backup, archive, phase, cache, and suffixed duplicate files are never authoritative.

The source code and tests are technical evidence, but an agent must not use an accidental implementation detail to weaken an explicit user decision or a safety invariant in `SOUL.md`.

When a contradiction is discovered:

```text
Stop the affected change
→ identify exact files and behavior
→ compare against user decision + SOUL.md + SAFY_source.md
→ preserve the safer behavior
→ ask the user if product behavior, permissions, secret storage, UI flow,
  database execution scope, or confirmation boundaries would change
→ update current_state.md after the resolution is implemented and verified
```

---

## 1. Executive state summary

SAFY is currently a **functional local beta in integration-hardening stage**.

Implemented core capabilities:

- Local FastAPI backend.
- Local browser UI with separate login, dashboard, and Schema Graph implementations; Schema Graph now replaces the Dashboard view at a nested Dashboard route instead of opening a popup.
- Model profile configuration for local and OpenAI-compatible providers.
- Database profile management with a database-type-aware UI, unified payload contract, and provider/driver routing.
- Agent chat workflow with document-driven skills, shared actions, and compiled domain-intelligence context retrieval.
- Guarded direct read-only database queries.
- User-controlled DDL/DML through the Execute Box.
- Sandbox-first validation before real write/DDL execution.
- Bounded multi-statement schema batches.
- Separate Supabase RPC and native PostgreSQL paths.
- Schema Graph v2 persistence, refresh, canonical JSON contract, relationship metadata, interactive grid canvas, pan, and cursor-centered zoom.
- Session state, workflow trace, audit, privacy redaction, and one-time execution checks.
- Native OS file context (`.md`/`.txt` only) and public URL context for one request only.
- CLI entry point through `safy run`.

Not certified yet:

- Production multi-user deployment.
- Full live integration matrix for every advertised database.
- Autonomous skill/plugin execution as isolated runtimes.
- Real server-side token streaming.
- Complete accessibility, responsive, and cross-browser certification.
- Unrestricted administrative database operations.

### Maturity matrix

| Area | Current state | Evidence boundary |
|---|---|---|
| FastAPI local runtime | Implemented | Unit/static validation |
| Login gate | Implemented for local use | Not production authentication |
| Split UI pages and nested Schema route | Implemented | Automated route/UI source tests |
| Sidebar collapse | Implemented | Automated layout rule test + owner screenshot-driven fix |
| Read-only connected DB workflow | Implemented | Regression tested; live coverage varies by driver |
| User DDL/DML workflow | Implemented | Sandbox/guard tests + owner UAT on latest schema flow |
| Multi-statement schema batch | Implemented | Regression tested, max 64 statements |
| Supabase RPC write/DDL | Implemented | Owner-tested for current workflow; OpenAPI schema parsing now captures explicit PK/FK annotations; not CI-certified against every project configuration |
| PostgreSQL native | Implemented | Driver and policy tests; schema introspection now includes constraints, indexes, inheritance, and partitions; broader live certification pending |
| SQLite | Implemented | Rollback and restore tests |
| MySQL | Structured connection profile + driver path present | Host/port/database/user/password UI and backend classification implemented; broader live certification pending |
| SQL Server | Structured connection profile + read/write driver path present | Read-only Execute Box uses SQL Server dialect adaptation; sandbox-validated user DDL/DML has a transactional native driver path; live write certification pending |
| Oracle | Structured connection profile + read driver present | Service Name/SID/schema UI and backend classification implemented; write workflow not certified |
| Skills | 11 active document-driven packs | `real_skill_execution: false` |
| Privacy/audit boundary | Implemented | Regression tested |
| Production readiness | Not certified | Integration-hardening remains |

---

## 2. Non-negotiable product contract

SAFY separates **agent automation** from **user-controlled database execution**.

### 2.1 Agent-direct database path

```text
Agent/chat request
→ read-only query only
→ SQL guard
→ selected connected database
→ bounded result
→ no autonomous DDL/DML
```

The agent may:

- inspect schema;
- generate SQL drafts;
- execute safe read-only SQL when the workflow permits it;
- explain or repair SQL;
- display query results.

The agent must not:

- autonomously execute write or DDL statements on a real database;
- bypass the Execute Box;
- authorize its own SQL;
- bypass sandbox validation;
- expose secrets;
- escalate a saved database profile's permissions;
- change the SQL after the user-approved safety check.

### 2.2 User Execute Box path

```text
User SQL / generated SQL draft
→ classify and normalize
→ analyze each statement
→ enforce saved profile permission
→ validate exact SQL in sandbox
→ issue check_id + sql_hash
→ user explicitly presses Execute
→ execute the exact checked SQL on the selected real database
→ consume the one-time check
```

### 2.3 Destructive and administrative SQL

The current ordinary Execute Box must continue to block:

- `DROP`;
- `TRUNCATE`;
- `GRANT` and `REVOKE`;
- user, role, login, and privilege administration;
- database/server administration;
- functions, procedures, policies, and security-definer/security-invoker changes;
- row-level-security administration;
- unknown SQL;
- transaction-control statements submitted by the user when SAFY owns the transaction boundary.

A separate explicitly designed administrative workflow is required before these operations may be enabled.

---

## 3. Runtime topology

```text
Browser
├─ /login
├─ /dashboard and /Dashboard
└─ /Dashboard/{schema_ui_name}
   └─ /schema-graph-ui is a legacy redirect
      │
      ▼
FastAPI: Apps/Api/safy_api/main.py
      │
      ├─ Auth/profile/session APIs
      ├─ Model/database profile APIs
      ├─ Context URL fetch boundary
      ├─ Agent chat and skill/tool metadata
      ├─ Query check/execute boundary
      └─ Schema Graph and sandbox APIs
      │
      ▼
Agent/agent_runtime.py + Core/
      │
      ├─ Skill registry
      ├─ Tool registry
      ├─ Context pack
      ├─ Workflow plan/review
      └─ State/trace recording
      │
      ▼
Gateway/query_orchestrator.py
      │
      ├─ SQL normalization/classification
      ├─ Target extraction
      ├─ Risk and permission analysis
      ├─ Sandbox validation
      ├─ One-time check binding
      └─ Real execution gate
      │
      ├───────────────┬──────────────────┐
      ▼               ▼                  ▼
Sandbox/        Gateway/db_drivers/   Audit + State + DataStore
```

---

## 4. Canonical source ownership

| Responsibility | Current canonical source |
|---|---|
| FastAPI routes and composition root | `Apps/Api/safy_api/main.py` |
| API request schemas | `Apps/Api/safy_api/schemas.py` |
| CLI | `Apps/Api/safy_api/cli.py` |
| Login page | `Apps/Web/login.html`, `Apps/Web/login.js` |
| Dashboard page | `Apps/Web/dashboard.html`, `Apps/Web/dashboard.js` |
| Schema Graph page | `Apps/Web/schema-graph.html`, `Apps/Web/schema-graph.js` |
| Shared UI styling | `Apps/Web/styles.css` |
| Old browser compatibility loader | `Apps/Web/safy-ui.js` |
| Agent orchestration | `Agent/agent_runtime.py` |
| Agent schema context | `Agent/schema_context.py` |
| Skill discovery/runtime attachment | `Core/skill_loader.py`, `Core/skill_registry.py`, `Core/skill_actions.py` |
| Tool metadata registry | `Tools/registry.py` and runtime registration in `Agent/agent_runtime.py` |
| Query safety/execution gate | `Gateway/query_orchestrator.py` |
| SQL classification | `Gateway/sql_classifier.py` |
| SQL normalization | `Gateway/sql_normalizer.py` |
| Target extraction | `Gateway/statement_target_extractor.py` |
| Risk analysis | `Gateway/risk_analyzer.py` |
| Permission checks | `Gateway/permission_checker.py` |
| Agent real-DB read-only policy | `Gateway/real_db_policy.py` |
| Driver routing | `Gateway/db_drivers/factory.py`, `Gateway/db_drivers/provider_profiles.py` |
| Supabase RPC driver | `Gateway/db_drivers/supabase_rest_driver.py` |
| Native database drivers | `Gateway/db_drivers/postgres_driver.py`, `mysql_driver.py`, `sqlite_driver.py`, `sqlserver_driver.py`, `oracle_driver.py` |
| Sandbox orchestration | `Sandbox/sandbox_manager.py` |
| Docker lifecycle | `Sandbox/docker_manager.py` |
| Restore safety | `Sandbox/restore_manager.py` |
| Runtime/session persistence | `State/json_runtime_db.py`, `State/runtime_db.py` |
| Audit persistence/redaction | `Audit/`, `Logging/redact.py` |
| Profiles and secret references | `DataStore/profile_store.py`, `env_writer.py`, `env_secret_resolver.py` |
| Schema Graph persistence | `DataStore/schema_graph_store.py` |
| Product contract | `SOUL.md` |
| Source map | `SAFY_source.md` |
| Operational state | `current_state.md` |

### Non-runtime artifacts

- `Apps/Web_backup_before_split/` is a backup snapshot and is not served by current routes.
- Historical patch reports under `Docs/Hermes_Execution/report/` must not be used as live implementation instructions.
- Runtime data under `Data/` may be reset and must not be treated as source code.

---

## 5. UI current state

### 5.1 Page separation

The UI is no longer implemented as one combined page.

| Route | HTML | JavaScript | Responsibility |
|---|---|---|---|
| `/` | served as login page | `login.js` | Local entry point |
| `/login` | `login.html` | `login.js` | Username/password gate |
| `/dashboard` and `/Dashboard` | `dashboard.html` | `dashboard.js` | Chat, profiles, Execute Box, settings, context attachment |
| `/Dashboard/{schema_ui_name}` | `schema-graph.html` | `schema-graph.js` | Replaces the Dashboard view with the active database Schema Graph while preserving browser Back navigation |
| `/schema-graph-ui` | redirect only | none | Legacy compatibility redirect to `/Dashboard/schema-graph` |

`schema_ui_name` is presentation-only, restricted to a bounded safe slug, and is never used as a file path or trusted database selector. Schema data still resolves from the authenticated active database profile.

`Apps/Web/index.html` remains a redirect shell for static compatibility.  
`Apps/Web/safy-ui.js` remains a compatibility shim that loads `dashboard.js` for stale cached HTML.

### 5.2 Dashboard layout

The dashboard has:

- top bar with active model, active database, mode, user, backend status, and safety badge;
- left sidebar for sessions, model connection, database connection, and settings;
- central chat thread and input;
- right-side Execute Box and related runtime panels;
- explicit buttons for Check Safety and Execute;
- button to replace the current Dashboard view with Schema Graph at `/Dashboard/{schema_ui_name}`; no popup or new window is used;
- after a saved database profile is switched successfully, the database configuration panel closes, while the independent Model configuration panel keeps the open/closed state it had before the switch;
- while `/agent/chat` is pending, the thread shows an assistant-side three-dot vertical bounce indicator, the send button is disabled to prevent duplicate requests, and the busy state is always cleared in `finally` after success or failure.

### 5.3 Sidebar behavior

The left and right sidebars are independently collapsible.

Current requirement and implementation:

```text
Collapsed left sidebar width = 0
Collapsed right sidebar width = 0
Main content receives the released layout width
State is persisted in localStorage under safy_sidebar_state_v1
```

Do not reintroduce a fake collapse that only hides content while preserving the sidebar grid width.

### 5.4 UI settings

Current settings persisted in `localStorage`:

- theme: dark/light;
- the light theme uses a complete surface remap so panels, result cards, schema cards, configuration panels, overlays, and composer controls do not retain dark-mode backgrounds; login and Schema Graph read the same saved theme key;
- streaming presentation toggle;
- auto-run read-only toggle;
- sidebar open/closed state.

Current “streaming” is primarily client-side typewriter presentation. It is not proof of backend token streaming.

### 5.5 Current UI code organization limitation

Pages are separated, but the dashboard implementation remains large:

- `dashboard.js` still contains profile management, session management, chat, context sources, Execute Box, sandbox controls, schema route launch behavior, error mapping, and UI state.
- `schema-graph.js` now owns canonical graph normalization, deterministic layout, relationship rendering, background pan, draggable table nodes, fit/reset, and cursor-centered zoom.
- `styles.css` remains shared and broad, including the graph design tokens and light/dark graph surfaces.

Future modularization is appropriate, but it must preserve endpoint semantics, safety status mapping, nested Dashboard routing, cursor-centered zoom mathematics, and current UAT behavior.

---

## 6. Local OS file and public URL context

The dashboard supports real context sources rather than mock-only entries. Local-file selection and public-URL entry intentionally use different UI paths.

### 6.1 Local file context

Browser behavior:

- clicking the paperclip immediately opens the browser/operating-system native file chooser;
- SAFY does not render a custom file-browser table or a file-selection modal;
- the native chooser is limited to Markdown and plain-text files through `accept=".md,.txt,text/markdown,text/plain"`;
- client validation also rejects every extension except `.md` and `.txt`;
- the backend ignores forged local context entries whose file names do not end in `.md` or `.txt`;
- maximum 5 total context sources;
- maximum 1 MiB per selected browser file;
- selected sources appear as small removable chips inside the composer, not as a management table;
- content is attached to the next chat request only;
- all attached sources are cleared after a successful send.

### 6.2 Public URL context

Public URLs use a separate compact URL dialog opened from the link icon. The dialog contains only the URL input, fetch action, security note, and validation error; it does not contain local-file controls.

Endpoint:

```text
POST /context/fetch-url
```

Server-side controls:

- only `http` and `https`;
- embedded URL credentials are rejected;
- DNS must resolve;
- loopback, private, link-local, multicast, reserved, and unspecified IP ranges are blocked;
- `.localhost` and `.local` hosts are blocked;
- every redirect target is revalidated;
- request timeout is bounded;
- fetched response is capped at 512 KiB;
- only text, HTML, Markdown, CSV, JSON, XML, and compatible text content types are accepted;
- scripts, styles, `noscript`, and SVG text are excluded from HTML extraction;
- URL query strings are not persisted in prompt labels or session metadata.

### 6.3 Context prompt and persistence boundary

Backend limits:

- maximum 5 sources;
- maximum 40,000 characters per source;
- maximum 120,000 characters total;
- content is redacted before insertion;
- context is wrapped as untrusted reference data;
- context is for the current request only;
- the original user message is restored before response/state presentation;
- session metadata stores only bounded summaries such as kind, name, host, and character count;
- raw file/URL content is not persisted in session history.

Do not allow this feature to become an SSRF route, a secret exfiltration route, or a mechanism for persistent untrusted prompt injection.

---

## 7. Authentication and local access boundary

### 7.1 HTTP locality

By default SAFY accepts loopback requests only.

Allowed local hosts include:

- `127.0.0.1`;
- `localhost`;
- `::1`;
- test client hosts during tests.

Remote requests are blocked unless the operator explicitly sets:

```text
SAFY_ALLOW_REMOTE=1
```

This flag must not be enabled casually. The current login layer is not production multi-user authentication.

### 7.2 Login behavior

Routes:

```text
GET  /auth/profile
GET  /user/profile
POST /auth/login
```

Current behavior:

- one active local user profile;
- password is resolved from `.env`/environment through an environment variable reference;
- raw password is not returned by the API;
- UI receives a password mask and configuration status;
- browser stores the signed-in username in `localStorage` to guard dashboard/schema navigation;
- successful login redirects to `/dashboard`;
- sign-out clears browser state and returns to `/login`.

Limitation:

- this is a local application gate, not a hardened identity/session/token system;
- there is no production-grade cookie/session authentication or multi-user authorization model.

---

## 8. Model profile state

Supported UI choices currently include:

- LM Studio;
- Ollama Local;
- OpenAI;
- OpenRouter;
- generic OpenAI-compatible endpoint.

Core model profile fields:

```text
profile_id
display_name
provider
base_url
model_name
api_key_env
temperature
max_tokens
context_window
active
```

Rules:

- raw API keys must be moved to environment storage before profile JSON persistence;
- profile JSON stores environment variable references and masked status only;
- save, activate, test, and active-profile endpoints remain separate operations;
- model/provider errors must render in model/chat context, not as Execute Box database errors.

Primary endpoints:

```text
GET  /model-profiles
GET  /model-profiles/active
POST /model-profiles
POST /model-profiles/{profile_id}/activate
POST /model-profiles/{profile_id}/test
GET  /model-providers
POST /model-providers
PATCH /model-providers/{profile_id}
POST /model-providers/{profile_id}/activate
DELETE /model-providers/{profile_id}
```

Some legacy compatibility endpoints remain under `/profiles/model/*`. Do not add a third competing profile store.

---

## 9. Database profile state

### 9.1 Permission modes

The saved database profile is authoritative.

Allowed values:

```text
credential_permissions
read_only
disabled
```

A request payload must never upgrade a saved `read_only` or `disabled` profile to `credential_permissions`.

### 9.2 Database connection UI and unified payload contract

The Dashboard database form now starts with `Type Database` and renders only the fields applicable to the selected type. Inline description/help paragraphs under database fields are intentionally omitted to keep the panel compact; labels, placeholders, validation errors, and type-specific visibility remain authoritative. Canonical values:

```text
postgresql
supabase_rpc
mysql
sqlite
sqlserver
oracle
```

The UI sends one complete JSON shape for all database types. Important fields include:

```text
database_type, provider, driver, dbms, engine
connection_kind, execution_transport, base_url
host, port, instance, database, schema
sqlite_path, allowed_root, service_name, sid
authentication, trusted_connection, username
password, api_key, preserve_secret
ssl_mode, encrypt, trust_server_certificate, odbc_driver
sql_rpc_function, timeout_seconds
user_query_access_mode, read_only, active, real_db_readonly
```

Backend classification in `DataStore/profile_store.py` treats structured fields and `database_type` as authoritative. URL inference remains only for legacy compatibility. Irrelevant empty fields are ignored by the selected driver.

Database username mapping is intentional: password-authenticated native database profiles use the authenticated SAFY login username. The UI shows that username in a read-only field, and the backend reapplies it during preview, save, test, and runtime materialization so a client payload cannot substitute a different native database username. Exceptions are Supabase API/RPC, SQLite, and SQL Server Windows Authentication, which do not use this mapping.

Type-specific field rules:

- PostgreSQL: host, port, database, SAFY login username (read-only in the form), password, and SSL mode.
- Supabase API/RPC: HTTPS project Base URL, API key, SQL RPC function.
- MySQL/MariaDB: host, port, database, SAFY login username (read-only in the form), password, and SSL mode.
- SQLite: existing local `.db`/`.sqlite` path and optional allowed root; no credentials.
- SQL Server: host, optional named instance/port, database, SQL Server or Windows Authentication, encryption, trust-certificate flag, and ODBC driver.
- Oracle: host, port, Service Name or SID, optional schema/owner, SAFY login username (read-only in the form), and password.

### 9.3 Provider/driver matrix

Current routing matrix:

| Provider | Allowed drivers |
|---|---|
| `self_hosted` | `sqlite`, `mysql`, `postgresql`, `sqlserver`, `oracle`, `fake` |
| `supabase` | `supabase_rpc`, `postgresql` |
| `google_cloud_sql` | `mysql`, `postgresql`, `sqlserver` |
| `aws_aurora` | `mysql`, `postgresql` |

### 9.4 Supabase routing rule

Two distinct modes must remain separate.

```text
Supabase HTTPS project URL + API key
→ supabase_rpc
→ PostgREST RPC transport
→ safy_execute_sql
```

```text
Supabase-hosted native PostgreSQL connection string/host
→ postgresql
→ native PostgreSQL driver
```

Do not infer RPC mode from the word “Supabase” alone. Driver routing must use the actual connection kind and URL scheme.

### 9.5 Database secrets

Rules:

- UI may accept a password/API key for save/test workflow;
- backend moves the secret to `.env`/environment storage;
- profile JSON stores only environment variable references;
- raw secret fields are rejected at the persistence boundary;
- audit/session/UI responses must not contain raw database secrets.

### 9.6 Profile endpoints

Primary current endpoints:

```text
GET  /database-profiles
GET  /database-profiles/active
POST /database-profiles
POST /database-profiles/test
POST /database-profiles/{profile_id}/activate
POST /database-profiles/{profile_id}/test
POST /database-profiles/{profile_id}/ensure-sandbox
```

Compatibility endpoints remain under `/profiles/database/*`. New work must converge behavior rather than create another profile contract.

---

## 10. Agent runtime, skills, and tools

### 10.1 Agent runtime

`Agent/agent_runtime.py` currently coordinates:

- command routing;
- active database/sandbox context;
- schema context;
- semantic action planning before SQL generation;
- model-backed or deterministic SQL draft generation;
- intent-to-SQL consistency enforcement;
- SQL guard;
- Execute Box draft creation;
- checked execution;
- explanation and basic repair;
- workflow plan/review;
- session state and tool/workflow trace.

### 10.2 Skill system

`Configs/skills.yaml` currently declares:

```yaml
stage: 15
real_skill_execution: false
document_driven_skill_packs: true
```

Active skills:

1. `command_router`
2. `create_database`
3. `database_context`
4. `database_switch`
5. `execute_box`
6. `execute_query`
7. `query_explain`
8. `query_guard`
9. `query_repair`
10. `schema_graph`
11. `text_to_sql`

Canonical terminology:

```text
text_to_sql
```

Do not rename it back to `text_to_query` unless the user explicitly approves a project-wide migration including config, folder names, references, tests, and documentation.

Current skill behavior:

- `text_to_sql` is semantic-plan-first: natural language is converted to a canonical operation/scope/effect plan before SQL generation;
- semantic routing is model-based and language/synonym aware; keyword classification is retained only for coarse metadata and deterministic workflow shortcuts, not as the primary safety decision;
- generated SQL is independently classified and compared with the semantic plan; mismatches such as `DROP_TABLES → SELECT` fail closed with no executable SQL;
- `DROP_TABLES + ALL_TABLES` uses the full stored Schema Graph and a deterministic single-statement renderer for PostgreSQL/Supabase, SQL Server, and MySQL/MariaDB;
- low-confidence, malformed, unknown, missing-schema, unsupported deterministic batch, and unclassifiable/multi-statement outputs fail closed;
- skills are discovered from canonical lowercase directories at `Skills/<name>/SKILL.md`;
- all 11 skill documents pass `python Scripts/validate_skills.py`;
- `schema_graph` exposes the required `## Required context` and `## Expected output` contract sections plus its JSON output schema;
- references are loaded with path and size controls;
- active skills attach shared action handlers;
- skills do not own isolated processes or dependency environments;
- `real_skill_execution: false` means they must not be described as fully autonomous executable plugins;
- repositories whose Git index still tracks legacy `Skills/Schema_graph/Skill.md`-style casing must run `Scripts/normalize_skill_git_case.ps1` once before commit. The script only stages canonical case-only renames and then restores the prior `core.ignorecase` setting.

### 10.3 Runtime tool registry

Current runtime-visible tools:

| Tool | Risk | Behavior |
|---|---|---|
| `sql.guard` | variable | classify/validate SQL |
| `database.read` | read-only | execute guarded connected-DB reads |
| `sandbox.validate` | write/DDL validation | validate in sandbox |
| `database.execute` | write | execute exact sandbox-validated SQL after confirmation |
| `schema.graph.read` | read-only | load cached schema graph |
| `execute_box.set_draft` | metadata/UI | place SQL draft in Execute Box |

The tool registry is metadata and routing support. It does not override `Gateway/query_orchestrator.py` safety enforcement.

### 10.4 Compiled domain intelligence

`Datasets/domain/` remains the read-only canonical source dataset for reviewed/synthetic domain assets such as manifests, glossaries, task templates, logical schemas, canonical cases, safety cases, provider overlays, samples, and train/validation/test splits.

Current runtime truth:

- compiled runtime artifacts are produced outside the source dataset under `DomainIntelligence/packs/`;
- `DomainIntelligence/packs/registry.json` is the canonical runtime registry path;
- `.safy-domain` files live under `DomainIntelligence/packs/<domain_id>/<version>/<domain_id>.safy-domain`;
- `DomainIntelligence/reports/` stores domain build, validation, and benchmark reports;
- `DomainIntelligence/work/` stores build-time staging and temporary repair proposals, not runtime source;
- `DomainIntelligence/` owns the pack contracts, compiler, registry, secure pack reader, lexical router, lexical retriever, schema fingerprint cache, context builder, and CLI handlers;
- `safy domain build --all`, `safy domain validate --all`, and `safy domain benchmark --all` operate on compiled packs without modifying `Datasets/domain/`;
- `Agent/agent_runtime.py` builds a bounded `DomainContext` from the user question plus live schema summary and attaches it to `ContextPack` before `text_to_sql` prompt construction;
- workflow trace records `domain_context` metadata: domain id, pack version, router confidence, retrieved document ids, and warnings;
- the domain pack is advisory business context only. Live schema, global security policy, SQL Guard, sandbox checks, check_id/sql_hash binding, and Execute Box confirmation remain authoritative;
- the previously discussed root-level `DomainBuild/` and `DomainPacks/` directories are not the current architecture and must not be recreated for this implementation;
- `SAFY_compiled_domain_intelligence_all_domains.zip` is a historical handoff artifact, not a runtime requirement.

Implemented flow:

```text
Datasets/domain/ (read-only)
→ DomainIntelligence/work/ staging
→ DomainIntelligence/packs/ registry and .safy-domain artifacts
→ question + live schema summary
→ schema fingerprint
→ lexical domain router
→ lexical top-k retrieval
→ bounded DomainContext
→ ContextPack / text_to_sql prompt path
→ existing SQL Guard + sandbox/execute boundaries
```

Do not inject entire raw domain datasets into prompts and do not write build artifacts back into `Datasets/domain/`.

---

## 11. SQL check and execution semantics

### 11.1 Read-only path

```text
SELECT / safe read operation
→ normalize/classify
→ saved profile permission check
→ connected database driver
→ bounded row result
→ result card in chat
```

Current maximum row limit at driver boundary:

```text
1..1000
```

### 11.2 Write/DDL path

```text
CREATE / ALTER / INSERT / UPDATE / DELETE
→ Execute Box
→ Check Safety
→ sandbox validation
→ check_passed=true
→ explicit Execute
→ real database execution
```

Ordinary write/DDL confirmation boundary is the user pressing Execute after sandbox pass.

### 11.3 Multi-statement user batch

Current bounded batch rules:

- maximum 64 statements;
- every statement is normalized and classified individually;
- every statement must be allowed;
- the full batch must pass sandbox validation;
- partial approval is forbidden;
- target tables are aggregated from actual statements;
- unknown/nested fragments fail closed;
- `SELECT` mixed into a write batch is blocked;
- transaction control is blocked because SAFY owns atomicity;
- PostgreSQL and SQLite use a transaction boundary where supported;
- Supabase RPC wraps the approved batch as one atomic PostgreSQL command.

### 11.4 Response field meanings

These fields must not be conflated:

| Field | Exact meaning |
|---|---|
| `success` | API handler completed successfully; not a safety verdict |
| `check_passed` | SQL safety/sandbox check actually passed |
| `safety_status` | UI-facing safety state such as `sandbox_passed` or `blocked` |
| `decision` | Policy result such as `ALLOW_AFTER_SANDBOX` or `BLOCK_POLICY` |
| `allowed_to_attempt` | Whether the next execution action may be offered |
| `sandbox_validated` | The exact SQL passed sandbox execution |
| `check_id` | One-time check identity |
| `sql_hash` | Integrity binding for normalized SQL |
| `statement_count` | Number of analyzed statements |
| `statement_types` | Child statement classes for a batch |

Frontend invariant:

```text
Never show “Safety passed” from success=true alone.
Use check_passed=true AND allowed_to_attempt=true.
Never enable Execute for a blocked/failed check.
```

### 11.5 One-time execution binding

Real execution must remain bound to:

- `check_id`;
- `sql_hash`;
- target;
- database profile;
- sandbox identity where applicable;
- expiration;
- one-time consumption state.

Concurrent or repeated attempts using the same mutation check must not execute twice.

---

## 12. Sandbox state

Sandbox responsibilities:

- validate user write/DDL before real execution;
- isolate changes from the connected database;
- expose truthful readiness state;
- preserve provider/DBMS semantics where possible;
- fail closed when the required runtime is unavailable.

Current behavior:

- PostgreSQL/MySQL-oriented sandbox paths use Docker when available/required;
- SQLite uses a managed local temporary database path;
- PostgreSQL sandbox must not report ready when Docker is unavailable;
- SQLite validation rolls back create/insert changes;
- restore sources must be managed and valid;
- compressed restore expansion is bounded;
- sandbox metadata and secrets are separated.

Endpoints:

```text
GET    /sandbox/health
POST   /sandboxes
GET    /sandboxes
GET    /sandboxes/{sandbox_id}
POST   /sandboxes/{sandbox_id}/start
POST   /sandboxes/{sandbox_id}/stop
DELETE /sandboxes/{sandbox_id}
POST   /sandboxes/{sandbox_id}/restore
GET    /sandboxes/{sandbox_id}/schema
GET    /sandboxes/{sandbox_id}/audit
```

---

## 13. Driver state

### 13.1 PostgreSQL

- native test, schema, read-only, and user SQL paths are present;
- connection profiles honor UI-selected SSL mode and bounded connection timeout;
- schema introspection uses PostgreSQL catalogs to collect tables, views, materialized views, partitions, columns, primary/unique constraints, indexes, foreign keys, table inheritance, and partition-parent metadata;
- foreign-key column pairs are preserved for composite constraints;
- user write/DDL remains gated by QueryOrchestrator and sandbox;
- live environment coverage remains necessary.

### 13.2 Supabase RPC

- RPC driver is separate from PostgreSQL native;
- expected RPC function is `safy_execute_sql` unless profile overrides the configured function field;
- project root URLs are normalized safely;
- hostname substring attacks are rejected;
- raw RPC response payload is not exposed/persisted;
- multi-statement approved batches use an atomic wrapper;
- schema introspection parses explicit PostgREST OpenAPI `<pk/>`, `<unique/>`, and `<fk .../>` annotations plus supported vendor extensions;
- when OpenAPI exposes columns but no explicit FK metadata, SAFY returns zero FK edges with a warning instead of inferring relationships from column names.

### 13.3 SQLite

- read-only and checked user execution are present;
- managed path validation and rollback behavior are tested;
- path traversal and unmanaged restore sources are rejected.

### 13.4 MySQL

- structured UI/profile fields and native driver path are present;
- user execution path is present;
- broader Docker/live integration certification is pending.

### 13.5 SQL Server

- structured profile fields support SQL Server Authentication and Windows Authentication;
- env-backed SQL Server passwords survive the normalize/test/save pipeline; the secret preparation path is idempotent and legacy profiles affected by the former double-normalization bug can recover their deterministic `.env` reference at runtime;
- direct chat reads refresh the materialized database profile immediately before execution so Test Connection, schema, Execute Box, and agent read paths use the same current credential;
- a fixed port is authoritative and produces `tcp:host,port`; a named instance is used only when no fixed port is configured;
- direct read previews and read-only Execute Box checks use SQL Server `TOP (n)` and convert a trailing `LIMIT n` before computing the safety hash;
- read query/driver failures are converted into structured SAFY error envelopes instead of escaping as HTTP 500;
- SQL Server result rows are normalized to JSON-safe values for decimals, temporal values, UUIDs, and binary columns;
- SQL Server authentication, untrusted-domain, connection-refused, syntax, object-not-found, and permission failures return specific driver error codes without exposing the connection string;
- encryption, trust-server-certificate, and configurable ODBC Driver 18 selection are represented in the profile;
- schema/read paths and a transactional `execute_user_sql` path for sandbox-validated user DDL/DML are present;
- live SQL Server write/DDL and sandbox compatibility certification remain pending.

### 13.6 Oracle

- structured profile fields support Service Name or SID and optional schema/owner;
- read-oriented driver and schema paths are present;
- write/DDL end-to-end workflow and Oracle sandbox are not certified.

Do not advertise SQL Server or Oracle as fully supported for guarded writes without live evidence.

### 13.6 Fake driver

- fake/test-support profile may return preview data for read paths;
- fake driver cannot execute real user SQL;
- UI/database status must distinguish fake/mock from real connected state.

---

## 14. Schema Graph state

Current Schema Graph behavior:

- stored per database profile;
- active graph can be read and refreshed;
- graph can be deleted for the active database;
- all graphs can be reset;
- schema-changing real execution invalidates the affected graph;
- filename/path generation is bounded and collision-tested;
- canonical contract version is `2.0.0`;
- the primary machine-readable collections are `nodes` and `relationships`;
- backward-compatible `tables` and `edges` projections remain for existing agent/API code;
- every node ID is schema-qualified, for example `public.orders`;
- column metadata includes PK/FK flags, type, nullability, uniqueness, defaults, generated values, sensitivity heuristic, and ordinal position;
- relationship metadata supports `foreign_key`, `inheritance`, `partition_parent`, `view_dependency`, `materialized_view_dependency`, `association`, and `inferred` types;
- the current runtime creates only metadata-backed relationships and does not infer edges from matching column names;
- foreign-key edges preserve source/target column arrays, constraint name, cardinality, update/delete actions, nullability, evidence, and confidence;
- old v1 graph files are upgraded in memory and are rewritten only after an explicit refresh;
- `Skills/schema_graph/output.schema.json` is the canonical JSON Schema reference;
- `Skills/schema_graph/SKILL.md` version `2.0.0` defines the read-only agent procedure and failure behavior.

Schema Graph UI behavior:

- selecting Schema Graph replaces the current Dashboard view instead of opening a popup;
- canonical route is `/Dashboard/{schema_ui_name}`;
- `/schema-graph-ui` is a legacy redirect only;
- an arrow icon returns to `/Dashboard` and browser Back also works;
- the graph canvas has synchronized small/large grid layers;
- tables/views render as nodes with column-level PK/FK badges;
- relationships render as typed SVG edges connected to source/target column rows when visible;
- wheel zoom is centered on the mouse cursor and affects only the graph viewport;
- `Ctrl + wheel` remains available to the browser for page zoom;
- background drag pans the graph;
- dragging a table by its header repositions that node in graph coordinates, compensates for the current zoom scale, expands the positive canvas when needed, and redraws connected relationship edges live;
- node positions are currently session/view state only and reset after graph reload or refresh;
- controls provide zoom in, zoom out, fit, and reset;
- scale is bounded from `0.25` to `2.5`.

Primary data endpoints:

```text
GET    /schema-graph
GET    /schema-graph/active
POST   /schema-graph/active/refresh
DELETE /schema-graph/active
DELETE /schema-graph
```

UI routes:

```text
/Dashboard
/Dashboard/{schema_ui_name}
/schema-graph-ui  -> 307 /Dashboard/schema-graph
```

---

## 15. Sessions, workflow trace, and recovery

Session/runtime capabilities include:

- create or lazy-create chat session;
- list sessions;
- read session/history/messages/timeline;
- delete a session;
- persist sanitized agent state;
- record workflow events and tool calls;
- inspect agent state/workflow;
- scan/resolve recovery state;
- manage workspace cleanup.

Key endpoints:

```text
POST   /chat/new
GET    /sessions
POST   /sessions
GET    /sessions/{chat_id}
DELETE /sessions/{chat_id}
GET    /sessions/{chat_id}/history
GET    /sessions/{chat_id}/messages
POST   /sessions/{chat_id}/messages
GET    /sessions/{chat_id}/timeline
GET    /agent/state/{chat_id}
DELETE /agent/state/{chat_id}
GET    /agent/workflow/{chat_id}
GET    /recovery/status
POST   /recovery/scan
POST   /recovery/resolve
GET    /workspaces
GET    /workspaces/{workspace_id}
POST   /workspaces/{workspace_id}/cleanup
```

Do not persist full database result rows or raw provider payloads in runtime session state.

---

## 16. Audit, privacy, and secret boundary

Current verified protections:

- raw SQL is recursively removed from audit metadata where persistence is not required;
- sandbox audit removes nested SQL and result rows;
- runtime state stores compact execution summaries rather than rows;
- raw provider/RPC responses are not stored in session state;
- sensitive SQL literals are redacted;
- schema snapshot and workspace-lock metadata are sanitized;
- session filenames and schema graph filenames are collision-protected;
- raw API keys and passwords are not stored in profile JSON;
- UI/API responses use masked secret status;
- external context is redacted and not persisted as raw content.

Any new logging, telemetry, trace, analytics, screenshot, or debug feature must be reviewed against this boundary before merge.

---

## 17. API route inventory

### UI and health

```text
GET / 
GET /login
GET /dashboard
GET /Dashboard
GET /Dashboard/{schema_ui_name}
GET /schema-graph-ui  (legacy 307 redirect)
GET /styles.css
GET /safy-ui.js
GET /health
```

### Authentication and combined profiles

```text
GET  /auth/profile
GET  /user/profile
POST /auth/login
GET  /profiles
```

### Model profiles/providers

```text
GET    /model-profiles
GET    /model-profiles/active
POST   /model-profiles
POST   /model-profiles/{profile_id}/activate
POST   /model-profiles/{profile_id}/test
GET    /profiles/model
POST   /profiles/model/save
POST   /profiles/model/test
GET    /model-providers
POST   /model-providers
PATCH  /model-providers/{profile_id}
POST   /model-providers/{profile_id}/activate
DELETE /model-providers/{profile_id}
```

### Database profiles

```text
GET  /database-profiles
GET  /database-profiles/active
POST /database-profiles
POST /database-profiles/test
POST /database-profiles/{profile_id}/activate
POST /database-profiles/{profile_id}/test
POST /database-profiles/{profile_id}/ensure-sandbox
GET  /profiles/database
GET  /profiles/database/{database_profile_id}/status
GET  /profiles/database/{database_profile_id}/schema
POST /profiles/database/save
POST /profiles/database/test
```

### Agent, skills, tools, context

```text
GET  /agent/skills
GET  /agent/tools
GET  /agent/state/{chat_id}
DELETE /agent/state/{chat_id}
GET  /agent/workflow/{chat_id}
POST /context/fetch-url
POST /agent/chat
POST /agent/generate-sql
POST /agent/explain-result
POST /legacy/agent/chat
```

### Query safety and execution

```text
POST /query/check
POST /query/execute
```

### Schema Graph

```text
GET    /schema-graph
GET    /schema-graph/active
POST   /schema-graph/active/refresh
DELETE /schema-graph/active
DELETE /schema-graph
```

### Sessions, workspaces, recovery

```text
POST   /chat/new
GET    /sessions
POST   /sessions
GET    /sessions/{chat_id}
DELETE /sessions/{chat_id}
GET    /sessions/{chat_id}/history
GET    /sessions/{chat_id}/messages
POST   /sessions/{chat_id}/messages
GET    /sessions/{chat_id}/timeline
GET    /workspaces
GET    /workspaces/{workspace_id}
POST   /workspaces/{workspace_id}/cleanup
GET    /recovery/status
POST   /recovery/scan
POST   /recovery/resolve
```

### Sandbox

```text
GET    /sandbox/health
POST   /sandboxes
GET    /sandboxes
GET    /sandboxes/{sandbox_id}
POST   /sandboxes/{sandbox_id}/start
POST   /sandboxes/{sandbox_id}/stop
DELETE /sandboxes/{sandbox_id}
POST   /sandboxes/{sandbox_id}/restore
GET    /sandboxes/{sandbox_id}/schema
GET    /sandboxes/{sandbox_id}/audit
```

Compatibility routes exist because the project has evolved through several API shapes. New code should prefer the current primary routes and avoid introducing another parallel contract.

---

## 18. Configuration state

### Application

`Configs/app.yaml` currently defines local paths for:

- user profiles;
- database profiles;
- schema graph directory;
- combined/legacy profile store;
- sessions;
- audit JSONL;
- runtime/audit database paths;
- high-risk code TTL.

### Policies

`Configs/policies.yaml` currently expresses:

```yaml
agent_connected_database: read_only
user_query_box: credential_permissions_after_check_confirmation_audit
manual_write_enabled: future_policy_explicit_only
```

Interpretation:

- agent-connected database actions remain read-only;
- user Execute Box may use credential permissions only after check/confirmation/audit;
- no broad global manual-write bypass exists.

### Toolsets

`Configs/toolsets.yaml` currently states:

- real sandbox execution is enabled;
- real database execution is enabled through guarded paths;
- read-only direct workflow is enabled;
- write/DDL requires sandbox;
- destructive SQL is blocked by default.

### Development/test runtime

`SAFY_DEV_MODE=1` alone is insufficient. Explicit test runtime also requires:

```text
SAFY_ALLOW_TEST_RUNTIME=1
```

This prevents accidental exposure of test-only behavior.

---

## 19. CLI and packaging

Project metadata:

```text
package: safy
version: 1.1.0
Python: >=3.10
console script: safy = Apps.Api.safy_api.cli:main
```

Expected commands:

```powershell
python -m pip install -e .
safy run
safy run --no-browser
safy info
safy domain list
safy domain validate --all
safy domain build --all
safy domain benchmark --all
```

CLI/path logic must not depend on the operator starting inside one specific working directory.

Wheel/source distribution state:

- `pyproject.toml` includes runtime packages and package-data declarations for `Configs/`, `Apps/Web/`, `Skills/`, and `DomainIntelligence/packs/`;
- a non-editable wheel installed into an isolated target can load 10 domain packs, import the FastAPI app, resolve bundled web assets, and validate all packs from outside the repository working directory;
- editable-install success alone is not accepted as packaging evidence;
- `current_state.md` is canonical project documentation and is no longer ignored by Git.

Safe source handoff:

```powershell
python Scripts/package_clean_handoff.py
```

The packager excludes `.git`, `.env` variants other than explicit templates/examples, credentials, runtime profiles, sessions, databases, logs, caches, build outputs, and Python bytecode. Do not create public/shareable handoff archives by manually zipping the repository root.

Line-ending policy:

- `.gitattributes` preserves committed bytes to prevent automatic cross-platform mass LF/CRLF churn;
- Windows command scripts remain explicitly CRLF;
- do not run a repository-wide renormalization as part of an unrelated feature commit.

### User packaging rule

Current user decision:

```text
If more than 20 files are modified → send the full project.
If 20 files or fewer are modified → send only the modified files,
preserving their relative project paths.
```

This rule must be applied to every SAFY handoff unless the user changes it again.

---

## 20. Current verification evidence

Current blocker fix pass (`2026-06-25`):

```text
python -m pytest -q
16 passed

python -m compileall Agent Core Gateway Sandbox State DataStore Apps/Api/safy_api Tests -q
PASS

node --check Apps/Web/dashboard.js
PASS

node --check Apps/Web/schema-graph.js
PASS

node --check Apps/Web/login.js
PASS

python Scripts/validate_skills.py
PASS; skills=11; canonical_text_skill=text_to_sql

python Scripts/package_clean_handoff.py
PASS; created C:\Users\ASUS\SAFY_clean_handoff.zip
```

Verified current blocker contracts:

- `AgentWorkflowState.transition_context()` clears opposing connected/sandbox fields, increments context generation, and invalidates stale SQL/check/hash state.
- Switching database in the dashboard resets Execute Box check/draft state before using the new active profile.
- Frontend no longer blocks natural-language database intents with a regex-only guard; active database profile context is sent as a backend hint while backend remains the authority.
- `WorkflowEngine` no longer generates natural-language read SQL before semantic planning.
- Semantic plan coherence is deterministic and blocks incoherent high-confidence model plans.
- Intent-to-SQL consistency checks target mismatch for generated SQL.
- Multi-target `DROP TABLE a, b, c` extraction returns all targets while destructive policy remains blocked.
- Supabase complex read failures now use a stable capability code indicating read RPC/native PostgreSQL is required.
- Query execution mismatch errors use stable `QUERY_CHECK_*` codes.

Live validation boundary: no production/live PostgreSQL, Supabase, SQL Server, MySQL, Oracle, or Docker sandbox was used in this pass; live DBMS certification remains blocked by environment and must not be claimed as production PASS.

Semantic action planning and intent-to-SQL consistency validation (`2026-06-25`):

```text
pytest -q Tests/test_semantic_action_planning.py
8 passed

pytest -q
29 passed

python -m py_compile \
  Core/semantic_action_plan.py \
  Core/skill_actions.py \
  Agent/agent_runtime.py \
  Apps/Api/safy_api/main.py \
  Tests/test_semantic_action_planning.py
PASS

python Scripts/validate_skills.py
PASS
```

Verified contracts:

- natural-language synonyms are interpreted by a structured semantic planner rather than enumerated deletion keywords;
- canonical plans carry operation, scope, target/effect, schema requirement, confirmation requirement, confidence, and rationale;
- a mutating/destructive plan cannot be silently replaced by `SELECT`;
- read plans cannot emit mutating SQL;
- unknown or low-confidence plans return no executable SQL;
- `DROP_TABLES + ALL_TABLES` uses the full Schema Graph and deterministic dialect rendering;
- PostgreSQL and SQL Server drop-all plans are single statements compatible with the existing fail-closed SQL classifier;
- `/Execute` returns a draft requiring Check Safety and never auto-runs destructive SQL;
- `/agent/generate-sql` exposes `action_plan`, `consistency`, and `blocked` for diagnostics.

Database-switch panel-state regression validation (`2026-06-25`):

```text
pytest -q Tests/test_dashboard_database_switch.py
1 passed

pytest -q
21 passed

node --check Apps/Web/dashboard.js
PASS
```

Verified UI contract:

- switching to a saved database profile closes the Database configuration panel only after activation and profile refresh succeed;
- the Model configuration panel preserves its prior open/closed state across the database switch;
- a failed switch leaves both configuration panels unchanged and renders the normalized error.

SQL Server execute/read HTTP-500 hardening validation (`2026-06-25`):

```text
pytest -q Tests/test_sqlserver_runtime_regressions.py
12 passed

pytest -q
20 passed

python -m py_compile \
  Agent/agent_runtime.py \
  Apps/Api/safy_api/main.py \
  Gateway/query_orchestrator.py \
  Gateway/db_drivers/base.py \
  Gateway/db_drivers/factory.py \
  Gateway/db_drivers/sqlserver_driver.py \
  Tests/test_sqlserver_runtime_regressions.py
PASS

node --check Apps/Web/dashboard.js
PASS

Verified contracts:
- SELECT ... LIMIT n is adapted to SELECT TOP (n) before safety hashing;
- the exact adapted SQL is passed to Execute;
- SQL Server user DDL/DML uses an explicit transaction with commit/rollback;
- unexpected Execute failures return a structured QUERY_EXECUTION_FAILED envelope;
- database-native result values are JSON-safe.
```

This validation confirms the credential materialization, fixed-port target construction, SQL Server dialect adaptation in both direct-read and Execute Box paths, transactional user execution support, and HTTP-500 containment. A live SQL Server write was not executed inside the isolated handoff environment.

Database profile workflow regression after the type-aware connection patch:

```text
pytest: 16 passed
Python compileall: PASS
dashboard.js syntax: PASS
skill validation: 11/11 PASS
FastAPI import/routes: PASS
```

This verifies payload classification and static/runtime contracts; it is not a live connection certification for every DBMS.


Validation executed on this Domain Intelligence fix snapshot:

```text
python -m compileall DomainIntelligence Core Agent Apps/Api/safy_api Tests
PASS

python -m pytest --collect-only -q
8 tests collected

python -m pytest -q
8 passed
```

Current test scope note:

```text
The 7 historical tests deleted from `Tests/` were intentionally removed by the user for this pass and were not restored.
The current automated pass contains the five Domain Intelligence tests plus three project-packaging/skill/handoff safety tests. Older audit/privacy, driver routing, sandbox, schema graph, skill document, and SQL safety tests are historical evidence, not active tests in this working tree because the user intentionally removed those seven files.
```

Domain Intelligence and distribution validation executed on this snapshot:

```text
python Scripts/validate_skills.py: PASS, 11 skills
python -m Apps.Api.safy_api.cli domain list: PASS
python -m Apps.Api.safy_api.cli domain validate --all: PASS, 10/10 valid
python -m Apps.Api.safy_api.cli domain benchmark --all: PASS, local lexical benchmark only
python -m pip install -e .: PASS
safy domain list: PASS
safy domain validate --all: PASS, 10/10 valid
safy domain benchmark --all: PASS, local lexical benchmark only
python -m pip wheel . --no-deps: PASS
isolated wheel resource inspection: PASS
isolated installed-target `domain list`: PASS, 10 domains
isolated installed-target `domain validate --all`: PASS, 10/10 valid
isolated installed-target FastAPI import/web-root resolution: PASS
python Scripts/package_clean_handoff.py: PASS; secret/runtime exclusion inspection: PASS
```

Headless browser smoke validation used the real `schema-graph.html`, `schema-graph.js`, and `styles.css` with a mocked canonical API response:

```text
3 schema nodes rendered: PASS
2 relationship edges rendered: PASS
Back link target /Dashboard: PASS
light-theme grid rendered: PASS
cursor-centered wheel zoom: PASS (node-center drift below 1 px in the test)
grid scale changed with graph zoom: PASS
table-node drag changes node coordinates and connected edge geometry: PASS
```

This browser smoke test validates UI behavior in Chromium, but it is not a live-database integration test.

### Test coverage inventory

#### Audit/privacy

- recursive raw SQL removal;
- nested sandbox audit sanitization.

#### Driver routing

- Supabase RPC routing;
- Supabase native PostgreSQL routing;
- HTTPS Supabase normalization;
- read-only factory blocking;
- fake-driver user execution rejection;
- Supabase hostname substring attack rejection.

#### Runtime state privacy

- execution summary without rows;
- provider response omission;
- Supabase RPC payload omission;
- sensitive literal redaction;
- snapshot/lock metadata sanitization;
- session filename collision prevention.

#### Sandbox validation

- SQLite create rollback;
- SQLite insert rollback;
- unmanaged restore rejection;
- non-database restore rejection;
- gzip expansion limit;
- truthful PostgreSQL Docker readiness;
- Docker use when available.

#### Schema Graph storage and contract

- sanitized path collision prevention;
- bounded filename length;
- v2 canonical `nodes`/`relationships` contract;
- FK and partition-parent relationship normalization;
- PK/FK column flags and statistics consistency;
- no relationship inference from matching column names;
- in-memory upgrade of v1 stored graphs;
- JSON contract presence and skill reference loading;
- Supabase OpenAPI FK annotation parsing;
- nested `/Dashboard/{schema_ui_name}` route and legacy redirect;
- grid/relationship/cursor-centered zoom source invariants;
- draggable table-node source invariants and live relationship-redraw hooks.

#### Skills

- valid and disabled discovery;
- malformed skill isolation;
- secure lazy reference loading;
- missing/traversal reference failure;
- registry/router behavior.

#### SQL safety workflow

- Markdown fence normalization;
- prose around fenced SQL fails closed;
- fenced `CREATE` reaches sandbox;
- schema batch reaches sandbox with real targets;
- unsafe child statement blocks entire batch;
- atomic Supabase batch wrapper;
- transaction-control blocking;
- cancellation consumes check;
- row mutations do not invalidate schema snapshot;
- read-only/disabled permission enforcement;
- concurrent double-execution prevention;
- row-limit rejection;
- security-sensitive DDL blocking;
- failed mutation consumes one-time check.

#### UI and context

- login/dashboard/schema implementations remain separated;
- Schema Graph replaces Dashboard at a nested route and has explicit Back navigation;
- collapsed sidebar releases all width;
- dashboard script does not implement login/schema page rendering;
- split and nested page routes work;
- Schema Graph grid, typed relationships, pan, draggable table nodes, live edge redraw, fit/reset, and cursor-centered zoom source invariants are covered;
- private context URLs are rejected;
- URL query is not persisted or inserted into prompt labels;
- ephemeral context is bounded, redacted, and not persisted;
- chat request pending state exposes three bouncing dots and clears/disables controls deterministically.

### Owner UAT

The project owner confirmed the latest Check Safety + schema batch workflow passed after the `success` versus `check_passed` status conflict was fixed.

This is evidence for the tested workflow, not certification for every provider, database version, or deployment topology.

The latest light-theme remap and native `.md`/`.txt` picker change are covered by automated source/API tests. Owner visual UAT for this exact UI revision is still pending.

---

## 21. Known limitations and technical debt

### Current conflict-hardening boundary

The June 24 conflict-hardening pass resolved the known active inconsistencies:

- canonical skill directory/file casing is defined and validated;
- the `schema_graph` skill contract passes the current validator;
- wheel package data includes required static/config/skill/domain-pack assets;
- `current_state.md` is trackable;
- the pre-fix failed audit report is explicitly marked superseded;
- clean handoff packaging excludes local secrets and runtime state;
- line-ending automation no longer causes implicit repository-wide normalization.

One repository-local action may still be required before the next commit on Windows: run `Scripts/normalize_skill_git_case.ps1` if `git ls-files Skills` still shows legacy capitalized directories or `Skill.md` filenames. This is a Git-index migration, not a runtime code change.

### Priority 0 — preserve current behavior

- Do not regress sidebar true-collapse behavior.
- Do not merge login, dashboard, and Schema Graph implementations back into one file; Schema Graph may replace the Dashboard route/view only through the dedicated `schema-graph.html` and `schema-graph.js` implementation.
- Do not replace real local-file/public-URL context with mock-only UI. Local files must keep the native OS picker and remain limited to `.md`/`.txt` until the user changes this rule.
- Do not use `success=true` as a safety-pass verdict.
- Do not allow request payload permission escalation.
- Do not merge Supabase RPC and native PostgreSQL routing.
- Do not weaken secret redaction or one-time execution binding.

### Priority 1 — integration hardening

1. Add repeatable live PostgreSQL integration tests.
2. Add repeatable live MySQL integration tests.
3. Add dedicated Supabase pre-release fixture/testing.
4. Define write/DDL certification scope for SQL Server and Oracle.
5. Add network failure injection around ambiguous commit timing.
6. Add API-level end-to-end tests beyond direct orchestrator tests.
7. Add browser automation for login, each Type Database field state, profile save/test, chat, Check Safety, Execute, sidebar, Schema Graph route replacement, column-edge rendering, pan, and cursor-centered zoom.

### Priority 2 — UI engineering

1. Split `dashboard.js` by domain without changing runtime behavior.
2. Establish a SAFY design-system document with tokens, component states, spacing, typography, and accessibility rules.
3. Run keyboard-only and screen-reader-oriented checks.
4. Verify responsive layouts at 320, 768, 1024, and 1440 px.
5. Add loading, empty, error, disabled, success, and focus states to a documented component matrix.
6. Reduce dependency on externally hosted fonts or provide a local/system fallback policy.
7. Remove or archive `Apps/Web_backup_before_split/` after the user confirms it is no longer needed.
8. Decide whether compatibility endpoints and `safy-ui.js` can be deprecated.

### Priority 3 — architecture/documentation

1. Consolidate overlapping model/database profile endpoints.
2. Reduce duplicate tool registry/config representations.
3. Add runtime/profile schema migrations.
4. Keep `current_state.md` updated after every meaningful patch.
5. Mark superseded phase/current-status documents explicitly rather than deleting evidence blindly.

### Explicit non-features

- unrestricted DBA administration;
- production remote deployment by default;
- autonomous destructive migration execution;
- persistent raw external context storage;
- full web browser/JavaScript rendering for context URLs;
- independent skill processes while `real_skill_execution` is false.

---

## 22. Recommended UI agent skills — evaluated, not installed

The following external skill sources are candidates for Hermes/UI work. They are **not SAFY dependencies and are not currently vendored into `Skills/`**.

### Recommended base set for SAFY

1. `anthropics/skills/skills/frontend-design`
   - Use for aesthetic direction and production-grade frontend generation.
   - Best as a design/build guidance layer.

2. `vercel-labs/agent-skills/skills/web-design-guidelines`
   - Use as a post-implementation UI/UX/accessibility audit.
   - Best for concise file/line findings.

3. `addyosmani/agent-skills/skills/frontend-ui-engineering`
   - Use for implementation discipline, accessibility, responsive behavior, component boundaries, state handling, and verification.

### Optional complementary skills

4. `microsoft/skills/.github/skills/frontend-design-review`
   - Use for design-system compliance and structured review.

5. `nextlevelbuilder/ui-ux-pro-max-skill`
   - Use when a richer design-system generator, palette/typography database, or multi-stack guidance is needed.
   - Heavier than SAFY currently requires; review generated files, scripts, and license before installation.

### Installation policy

Do not copy all external skills into SAFY blindly.

Required evaluation before vendoring:

- license and redistribution terms;
- prompt-instruction conflicts with `SOUL.md` and this file;
- script/network behavior;
- dependency footprint;
- whether the skill assumes React/Tailwind while SAFY currently uses vanilla HTML/CSS/JavaScript;
- duplicated or contradictory UI rules;
- test/verification value;
- exact folder name and `SKILL.md` compatibility with SAFY's loader.

Recommended combination for current SAFY UI work:

```text
Build/refactor: frontend-ui-engineering + frontend-design
Review: web-design-guidelines
Optional design-system generation: ui-ux-pro-max-skill
```

---

## 23. Agent workflow for future changes

Every Hermes/coding-agent pass should use this sequence:

### Step 1 — establish scope

Read:

```text
SOUL.md
SAFY_source.md
current_state.md
relevant source files
relevant tests
```

### Step 2 — classify the change

Choose one or more:

- UI-only;
- API contract;
- profile/secret;
- agent/skill;
- SQL safety;
- sandbox;
- database driver;
- audit/privacy;
- documentation/process.

### Step 3 — identify protected invariants

Before editing, list the invariants that must not change. For UI changes, include:

- page separation;
- safety field semantics;
- Execute button gating;
- profile secret boundary;
- current endpoint paths;
- sidebar true-collapse;
- context source security.

### Step 4 — patch minimally

- prefer the smallest correct set of files;
- do not rewrite unrelated modules;
- do not restore backup/legacy behavior;
- preserve public contracts unless the user approves a migration.

### Step 5 — validate

Minimum:

```text
pytest -q
python compile/static checks for changed Python
node --check for changed JavaScript
HTML duplicate-ID check for changed pages
```

Add targeted live/manual tests when the change touches:

- profile save/test;
- real database execution;
- Docker sandbox;
- Supabase RPC;
- sidebar/layout;
- login;
- Schema Graph;
- external context fetch.

### Step 6 — update current state

Update this file in the same patch when any of these change:

- application version;
- routes;
- canonical files;
- UI page ownership;
- safety workflow;
- supported database/provider matrix;
- skills/tools;
- test count/evidence;
- maturity assessment;
- known issues;
- packaging rule.

Do not update the test count without actually running the tests.

### Step 7 — package correctly

Count modified files relative to the user's project snapshot:

```text
<= 20 files → modified-files patch only
> 20 files  → full project
```

Preserve relative paths and include a concise change/validation report.

---

## 24. Do-not-regress checklist

Before any handoff, confirm:

```text
[ ] Natural-language database requests use a canonical semantic action plan before SQL generation.
[ ] Intent-to-SQL mismatch fails closed; mutating/destructive intent can never degrade into SELECT.
[ ] Agent real-database path remains read-only.
[ ] User write/DDL requires sandbox pass.
[ ] Destructive/admin SQL remains blocked.
[ ] check_id/sql_hash binding remains exact and one-time.
[ ] Saved profile permissions cannot be escalated by request fields.
[ ] Supabase RPC and native PostgreSQL remain separate.
[ ] Secrets are not persisted in profile JSON, audit, session, or UI.
[ ] Login/dashboard/schema pages remain separate.
[ ] Collapsed sidebar releases its full width.
[ ] Execute is gated by check_passed, not success.
[ ] Local file context uses the native picker, accepts only `.md`/`.txt`, and remains bounded/redacted/ephemeral; public URLs remain public-only and separately validated.
[ ] Schema-changing execution invalidates Schema Graph.
[ ] Runtime state does not persist result rows/provider payloads.
[ ] Tests and static checks pass.
[ ] current_state.md reflects the delivered snapshot.
[ ] Packaging follows the >20-file rule.
```

---

## 25. Current snapshot conclusion

SAFY has moved beyond a UI mock or proof-of-concept. It currently has a functioning local agent/API/UI stack, a guarded database execution model, a real sandbox-first write path, provider-aware driver routing, a versioned relationship-aware Schema Graph with an interactive canvas, document-driven skill packs, and regression coverage for critical safety/privacy behavior.

The project should now be treated as:

```text
Functional local beta
+ safety workflow implemented
+ UI architecture separated
+ Schema Graph v2 contract and interactive visualization implemented
+ integration hardening in progress
- not production certified
- not an unrestricted DBA agent
```

The next safe development focus is **UI quality and modularity, browser-level end-to-end testing, and live database integration certification**, while preserving every safety and privacy invariant documented above.
