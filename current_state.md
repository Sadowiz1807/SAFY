# SAFY Current State

**Snapshot date:** 2026-06-28  
**Application version:** 1.2.0  
**Canonical product:** SAFY — Human-in-the-Loop AI Database Safety Agent  
**Runtime authority:** Dashboard / CLI → FastAPI → AgentRuntime → deterministic safety core  
**Python runtime for tests:** `C:\Program Files\Python312\python.exe` with `PYTHONNOUSERSITE=1`

## Current Package Verification Status

This package has been corrected to avoid overclaiming old acceptance results that are not bundled with the current handoff. Earlier Hermes reports may have reported PASS, but the current package must be revalidated locally because `Tests/` and `Reports/` artifacts may be omitted from lightweight handoff archives.

Current source-level fixes prepared in this package:

- Context file store now rejects cross-session binding for session-scoped files and filters corrupted session indexes before UI/session retrieval.
- `session_files()` and `resolve_context_files_for_chat()` no longer trust stale `sessions_index.json` entries that point to files owned by another chat session.
- Context file recall has a backend store-aware fallback: active, inactive, and not-found file states are distinguished instead of returning generic no-memory chatbot text.
- Natural-language write/DDL routing drafts SQL into the Execute Box when SQL generation succeeds, without auto-executing real DB.
- Schema/table-count style questions can be answered from Schema Graph instead of being routed into a failed semantic write/read plan.
- LLM provider adapter now validates chat payload shape/size and returns more diagnostic errors such as `LLM_CONTEXT_TOO_LARGE`, `LLM_MESSAGE_CONTENT_INVALID`, and `LLM_PROVIDER_BAD_REQUEST`.
- SQL artifact card is now copy-icon-only in the top-right of the code block; old Copy/Collapse/Focus action buttons are removed from the generated SQL card.
- Clean packaging helper added at `Scripts/build_clean_package.py` to prevent `.env`, secrets, sessions, context runtime files, caches, and database artifacts from being packaged.

Required local verification before calling this stable:

```text
1. safy run starts successfully.
2. Upload prompt.md in session A.
3. Same session asks "bạn còn nhớ file prompt.md không?" and receives an answer based on file content.
4. Session B does not see or recall session A file.
5. Switch back to session A restores recall.
6. Natural prompt "tạo bảng A có id và address" fills Execute Box with SQL draft and Execute remains disabled before Check Safety.
7. Prompt "database hiện tại có bao nhiêu bảng" answers from Schema Graph.
8. SQL card shows one copy icon only at the code block top-right.
9. Clean package script refuses secrets and excludes runtime Data.
```


## Latest Regression Fixes - 2026-06-28

The port-8000 regression reported two remaining blockers: `CTX006 remove file prevents injection` and `NDB003 natural DDL draft`. The source now includes focused fixes for those blockers:

- Context file detach now deactivates a session-scoped file for that owning session, updates indexes/storage stats, and prevents fallback `chat_id` resolution from reinjecting the removed file.
- The dashboard Remove action now awaits the backend detach request and restores the chip if server-side detach fails, so the UI cannot silently hide a file that remains active on the backend.
- Simple natural-language CREATE TABLE requests such as `tạo cho tôi bảng A có 2 cột id và address` now have a deterministic draft path that does not depend on an LLM provider. The draft is still `draft_only`; it fills the Execute Box and still requires Check Safety before Execute.
- Regression tests were added for detach/deactivation and deterministic CREATE TABLE draft generation.

Verification performed in the patch workspace:

```text
python -m compileall -q DataStore/context_file_store.py Core/skill_actions.py Agent/agent_runtime.py Apps/Api/safy_api/main.py
node --check Apps/Web/dashboard.js
python -m pytest -q Tests/test_safy_integrity_regressions.py
# 5 passed
```

Full browser UAT on `http://127.0.0.1:8000/dashboard` must still be rerun locally before marking the release PASS.

## Current Architecture Decision

SAFY is a bounded, human-in-the-loop AI database safety agent. It is not a plain ToolCLI and not an autonomous agent. AI is allowed to understand requests, resolve domains, explain, and draft SQL/schema as `UNTRUSTED_DRAFT`. Deterministic safety code owns SQL classification, policy, sandbox validation, check artifacts, one-time binding, Execute authorization, database drivers/RPC and audit.

Source of Truth prose is exactly:

1. `SOUL.md`
2. `SAFY_source.md`
3. `current_state.md`

`README.md`, JSON/YAML schemas, runtime configs, domain packs and `Skills/*/SKILL.md` are operator/runtime assets, not competing prose Source of Truth. `Docs/` and `Safy_Docs/` must not be recreated.

## File Prompt Reader / Context File Store Status

File Prompt Reader and context store features are implemented in source, but acceptance evidence must be regenerated for the current package. Do not treat old PASS counts as current-package evidence unless the corresponding `Tests/` and `Reports/` artifacts are present.

## Current Architecture/Feature Status

- Local FastAPI runtime and Dashboard UI are implemented.
- Single active AgentRuntime path is the runtime authority; legacy AgentCore/Providers are not runtime authority.
- Model profiles use OpenAI-compatible timeout normalized to 180 seconds.
- Database profile management uses explicit driver/dbms/dialect fields.
- Domain Intelligence schema drafting uses compiled packs.
- Execute Box remains the canonical user-reviewable SQL draft.
- Deterministic SQL policy and sandbox-first validation remain authoritative.
- `check_id`/`sql_hash` binding and one-time Execute attempt consumption remain enforced.
- Supabase RPC driver path uses canonical `safy_execute_sql(sql text)` / JSON argument `sql`.
- Audit and structured error envelopes are implemented.
- Responsive layout hardening and SQL artifact cards remain implemented.

## Remaining Limitations

1. Proprietary DB live-certification for Oracle and SQL Server requires dedicated local/live services.
2. Business-rule assertion engine is not implemented; SAFY currently enforces technical SQL/database safety only.
3. OCR/scanned PDF support is out of scope for File Prompt Reader V1.
4. No auto-retry is performed for unknown write outcomes by design.

## Packaging Rule

```text
<= 6 source files modified → send the modified source files
> 6 source files modified  → send a full clean project package
```

Packages must exclude `.env`, secrets, passwords, service-role keys, runtime sessions, sandbox data, database files, `__pycache__`, `.pytest_cache`, `node_modules`, and temporary logs that may contain secrets.

## Current Known Limitations

1. Business-rule assertion engine is not implemented; SAFY currently enforces technical SQL/database safety only.
2. OCR/scanned PDF support is out of scope for File Prompt Reader V1.
3. Proprietary DB live-certification for Oracle and SQL Server requires dedicated local/live services.
4. Old runtime data in `Data/` should not be treated as source-of-truth; clean packages must exclude runtime context files, sessions, secrets, and database artifacts.

## Packaging Rule

```text
<= 6 source files modified → send the modified source files
> 6 source files modified  → send a full clean project package
```

Packages must exclude `.env`, secrets, passwords, service-role keys, runtime sessions, sandbox data, database files, user-uploaded context file contents, `__pycache__`, `.pytest_cache`, `node_modules`, and temporary logs that may contain secrets.

## Sandbox Rules V1

- Sandbox status is visible in the dashboard.
- Sandbox rules are stored by database_profile_id + sandbox_id, not by chat session.
- Rule panel can load/save manual text or .md/.txt rule files.
- Rule conflicts require explicit user decision.
- Active rules are not automatically modified by new conflicting rules.
- Schema conflicts do not auto-modify rules or schema.
- Schema fixes are additive-only drafts and still require Check Safety + user Execute.


## Sandbox Rules V1 parser follow-up - 2026-06-28

- Natural-language rule parsing now recognizes Vietnamese required-column phrasing such as `Bảng customers bắt buộc có email`.
- The parsed rule becomes a deterministic `column_required` rule, allowing schema validation to return `pending_user_decision` when the column is missing.
- Additive schema draft generation now supports the same phrase and produces an `ALTER TABLE ... ADD COLUMN ...` draft only; it does not auto-execute or create destructive schema changes.
- Natural required-table phrasing such as `Database bắt buộc phải có bảng users` is parsed as `table_required` without creating a spurious column rule.

## Sandbox Rules V1 UI placement follow-up - 2026-06-28

- Sandbox Rules panel is positioned above the Execute Box in the right sidebar.
- Rule file upload control is styled as a compact `Load .md/.txt` action instead of exposing the browser default file input text.
- Rule actions are grouped in a compact grid and rule list/report areas use dashboard-native card styling.
- The rule panel remains scoped to database_profile_id + sandbox_id and is still independent of chat session.

## Sandbox Rules V1 save/sync and UI follow-up - 2026-06-28

- Sandbox Rules UI now uses an icon-only `.md/.txt` loader consistent with the main chat attachment button.
- Rule panel now exposes only `Save` and `Disable`; `Save` performs validation before persistence.
- If validation returns a rule/schema conflict or ambiguous `warning_only` result, the rule is not saved/activated and the UI displays the validation report plus an error toast.
- Successful `Save` activates the deterministic rule, refreshes the database/sandbox rule list, and shows a success toast so rule changes are visibly synchronized.
- Active sandbox rules display an explicit green status dot in the rule list.
- Sandbox rule identifier matching is case-insensitive for schema/SQL identifiers, so a rule requiring `id` accepts SQL columns such as `ID`, `"ID"`, or `id`.
- Natural-language parsing now supports table-wide column requirements such as `Mỗi bảng phải có id` / `Mọi bảng bắt buộc có ID` as deterministic create-table assertions.

## Sandbox Rules V1 deep parser/enforcement follow-up - 2026-06-28

- Sandbox rule parsing now normalizes Vietnamese accents and identifier case for deterministic rule recognition.
- DROP TABLE synonyms such as `Không cho xóa bảng`, `Cấm xóa bảng`, `Không được xoá bảng`, and `Không được huỷ bảng` are parsed as `operation_forbidden` / `DROP_TABLE`.
- TRUNCATE-style synonyms such as `Không cho làm rỗng bảng` and `Không được xóa sạch bảng` are parsed as `operation_forbidden` / `TRUNCATE`.
- Required-column/table phrasing now covers `Bảng nào cũng phải có id`, `Bắt buộc tồn tại bảng users`, and bare table phrasing such as `customers phải có cột email`.
- Rule-vs-rule conflict detection now handles `column_forbidden` versus `column_required` for the same normalized table/column.
- Create-table enforcement blocks missing required global columns such as `id`, while still treating `id`, `ID`, `"ID"`, and `"Id"` as the same identifier.
- The Sandbox Rules file attach icon is now positioned inside the rule textarea, matching the chat input attachment pattern more closely.
