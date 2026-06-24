# SAFY CURRENT BLOCKERS FIX REPORT — 2026-06-25

**Repo:** `C:\Users\ASUS\SAFY`  
**Completed at:** 2026-06-25 03:18:09 SEAST  
**Input reports:** `SAFY_PROMPT_HERMES_FIX_TUNG_LOI_2026-06-25.md`, `SAFY_BAO_CAO_LOI_HIEN_TAI_2026-06-25.md`  
**Final status:** `PASS_CORE_WITH_BLOCKED_LIVE_VALIDATION`

---

## 1. Executive summary

Implemented the core in-place fixes for current SAFY blockers around cross-database state, stale Execute Box checks, frontend routing authority, WorkflowEngine SQL bypass, semantic plan coherence, target consistency, multi-target extraction, Supabase complex-read capability signaling, and stable query-check mismatch codes.

Validation completed:

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

Live DB/Docker certification was not executed in this environment, so the correct final status is not absolute production PASS; it is `PASS_CORE_WITH_BLOCKED_LIVE_VALIDATION`.

---

## 2. Baseline

Initial observed state in current repo:

```text
pytest collect: 8 tests collected
existing dirty working tree: yes
```

Important user decisions preserved:

- Did not restore the seven tests user intentionally deleted.
- Did not weaken DROP/TRUNCATE/admin/security policy.
- Did not allow agent-direct DDL/DML on real DB.
- Did not merge Supabase RPC and native PostgreSQL routes.
- Did not change the SAFY-login username mapping design.
- Did not expose or persist raw secrets.

---

## 3. Changed files

Changed/touched project files after this pass plus existing snapshot changes total 25 files, so packaging follows the user rule: **over 20 files changed → full clean project handoff**.

Files in final changed set:

```text
Agent/agent_runtime.py
Apps/Api/safy_api/main.py
Apps/Api/safy_api/schemas.py
Apps/Web/dashboard.html
Apps/Web/dashboard.js
Apps/Web/styles.css
Core/agent_state.py
Core/semantic_action_plan.py
Core/skill_actions.py
Core/workflow_engine.py
DataStore/profile_store.py
Gateway/db_drivers/base.py
Gateway/db_drivers/factory.py
Gateway/db_drivers/mysql_driver.py
Gateway/db_drivers/oracle_driver.py
Gateway/db_drivers/postgres_driver.py
Gateway/db_drivers/sqlserver_driver.py
Gateway/db_drivers/supabase_rest_driver.py
Gateway/query_orchestrator.py
Gateway/statement_target_extractor.py
SAFY_source.md
Skills/text_to_sql/SKILL.md
Tests/test_current_blocker_regressions.py
Tests/test_project_packaging.py
current_state.md
Docs/Hermes_Execution/report/SAFY_CURRENT_BLOCKERS_FIX_REPORT_2026-06-25.md
```

New regression test file:

```text
Tests/test_current_blocker_regressions.py
```

---

## 4. Architecture changes

### 4.1 Context state transition

Added `AgentWorkflowState.transition_context()` and `invalidate_execution_context()`.

Implemented invariant:

```text
target=connected_database
→ database_profile_id required
→ sandbox_id cleared

target=sandbox
→ sandbox_id required
→ connected database_profile_id cleared as execution target
```

When context changes:

```text
context_generation += 1
last_sql cleared
last_sql_hash cleared
last_check_id cleared
last_safety_result cleared
pending_confirmation cleared
```

### 4.2 Frontend Execute Box invalidation

Added canonical frontend reset:

```javascript
resetExecuteContext({ clearSql, reason })
```

Database switch now resets the Execute Box/check state before using the newly active profile.

### 4.3 Routing authority

Frontend no longer blocks natural-language DB intents with the old regex-only guard. It sends active database profile context as a safe hint, while backend remains authority for whether the request is chat or database work.

### 4.4 WorkflowEngine bypass removal

`WorkflowEngine` no longer generates natural-language read SQL such as:

```sql
SELECT * FROM a LIMIT 100;
```

Natural-language database tasks now flow to semantic planning and dialect/capability-aware generation instead of deterministic regex SQL drafting.

### 4.5 Semantic coherence and target consistency

Added deterministic coherence validation:

```python
validate_plan_coherence(plan)
```

`SemanticActionPlan.can_generate_sql` no longer trusts model confidence alone.

`validate_sql_against_plan()` now checks target mismatch when plan targets are present.

### 4.6 Stable binding/mismatch codes

`QueryOrchestrator.execute()` now emits stable context mismatch codes:

```text
QUERY_CHECK_TARGET_MISMATCH
QUERY_CHECK_PROFILE_MISMATCH
QUERY_CHECK_CONTEXT_MISMATCH
QUERY_CHECK_SQL_HASH_MISMATCH
QUERY_CHECK_CONSUMED
```

### 4.7 Supabase capability signaling

Supabase REST complex SELECT failure now returns:

```text
SUPABASE_COMPLEX_READ_RPC_REQUIRED
```

instead of the ambiguous legacy `SUPABASE_SQL_REQUIRES_RPC` path. UI mapping now separates complex read RPC, read RPC failure, write RPC missing/failure, and REST unsupported cases.

---

## 5. Issue status by ID

| ID | Status | Files changed | Root cause | Implementation | Tests/result | Remaining limitation |
|---|---|---|---|---|---|---|
| P0-01 Frontend regex authority | FIXED_CORE | `Apps/Web/dashboard.js`, `Apps/Api/safy_api/main.py`, `Tests/test_current_blocker_regressions.py` | Frontend regex decided route before backend semantic authority | Removed blocking regex gate from send path; sends active profile hint; backend preserves hint | `test_dashboard_switch_database...`, pytest 16 passed | Full browser E2E not run |
| P0-02 Cross-profile/session contamination | FIXED_CORE | `Core/agent_state.py`, tests | `remember_context()` set fields independently | Added atomic `transition_context()`, opposing target clear, generation increment, stale state invalidation | `test_context_transition...`, pytest 16 passed | Runtime DB persisted old sessions may need natural transition on next context update |
| P0-03 Stale Execute Box/check after switch | FIXED_CORE | `Apps/Web/dashboard.js`, tests | DB switch did not reset `safyCurrentCheck`/draft | Added `resetExecuteContext()` and call on DB switch | source regression test + `node --check` PASS | Full browser click test not run |
| P0-04 WorkflowEngine bypass/dialect SQL | FIXED_CORE | `Core/workflow_engine.py`, tests | Regex engine generated SQL before semantic planner | Removed natural-language read/insert SQL fast-path from engine | `test_workflow_engine...`, pytest 16 passed | Existing semantic generator live behavior not DB-tested |
| P0-05 SQL Server sandbox adapter gap | PARTIAL/BLOCKED_LIVE | existing SQL Server files from snapshot | Live SQL Server sandbox not available | Kept capability boundary; no fake live PASS claimed | compile/tests pass | Live SQL Server write/sandbox certification blocked by environment |
| P0-06 DROP ALL dead workflow | PARTIAL_CORE | `Core/semantic_action_plan.py`, `Gateway/query_orchestrator.py` | Destructive plans could be generated then blocked later | Semantic coherence/consistency added; destructive policy remains blocked | pytest 16 passed | Full UX “policy_blocked draft” E2E not browser-tested |
| P0-07 Supabase complex read gap | FIXED_SIGNALING | `Gateway/db_drivers/supabase_rest_driver.py`, `Apps/Web/dashboard.js`, tests | Ambiguous RPC-required error for complex read | Stable `SUPABASE_COMPLEX_READ_RPC_REQUIRED`; clearer UI mapping | `test_supabase_complex_read...`, pytest 16 passed | Actual read RPC execution route not live-tested |
| P0-08 Supabase false-ready sandbox | PARTIAL/BLOCKED_LIVE | docs/report only in this pass | Existing runtime metadata could overstate readiness | No fake ready claim added; live boundary recorded | validation pass | Requires sandbox readiness refactor/live fixtures |
| P1-01 Semantic field coherence | FIXED_CORE | `Core/semantic_action_plan.py`, tests | No deterministic invariant validation | Added `validate_plan_coherence()` | high-confidence incoherent plan rejected | More invariants can be added incrementally |
| P1-02 Model confidence trusted | FIXED_CORE | `Core/semantic_action_plan.py` | `can_generate_sql` trusted confidence + no warnings | `can_generate_sql` requires coherence validator | pytest 16 passed | Model telemetry confidence still retained as metadata |
| P1-03 Intent–SQL target/scope gap | PARTIAL_CORE | `Core/semantic_action_plan.py`, tests | only statement type was compared | Added best-effort target mismatch check | target mismatch test passes | Full SQL AST/schema scope parser not implemented |
| P1-04 Multi-target extractor gap | FIXED_CORE | `Gateway/statement_target_extractor.py`, tests | regex captured only first table | Added comma-list extraction for DROP/TRUNCATE TABLE | `DROP TABLE a,b,c` test passes | Best-effort regex, not full AST |
| P1-05 Legacy classifier routing influence | PARTIAL_CORE | `Apps/Web/dashboard.js`, `Core/workflow_engine.py` | legacy regex/keyword could influence route | Removed frontend blocking gate and WorkflowEngine SQL fast path | tests pass | CommandRouter still has metadata keywords |
| P1-06 Dead auto_execute parameter | PARTIAL_CORE | `Apps/Web/dashboard.js` | frontend sent `auto_execute=true` broadly | now sends `auto_execute=readOnlyDbRequest` only for DB runtime path | node/check + pytest pass | API/runtime deeper contract still should be consolidated |
| P1-07 Generic blocked UX | PARTIAL_CORE | `Apps/Web/dashboard.js`, `Agent/agent_runtime.py` existing | generic next step for semantic blocks | Supabase and mismatch mappings improved | tests/static pass | Full taxonomy not exhaustively wired |
| P1-08 Supabase error mapping | FIXED_CORE | `Apps/Web/dashboard.js` | RPC/REST errors collapsed | Added separate mappings for read/write RPC and complex REST | node/check PASS | Browser visual UAT not run |
| P1-09 Non-atomic activation | PARTIAL | existing profile files from snapshot | activation/store atomicity broader than this pass | Execute reset + backend context hint improved | tests pass | Store-level crash injection not implemented in this pass |
| P1-10 Hidden live test on GET active | NOT_CHANGED/REVIEWED | none in this pass | endpoint semantics require deeper API audit | not modified | not specifically tested | Must be addressed with endpoint-specific regression later if still present |
| P1-11 SQL Server master grounding | NOT_CHANGED/BLOCKED_LIVE | none in this pass | requires schema/profile live grounding checks | not modified | not specifically tested | Needs live SQL Server/schema fixture |
| P2-01 Stale current_state test claims | FIXED_CORE | `current_state.md` | evidence did not reflect current pass | Added current blocker pass evidence + live boundary | report/docs updated | Historical sections retained as evidence |
| P2-02 Missing regression coverage | FIXED_CORE | `Tests/test_current_blocker_regressions.py` | no tests for current blockers | Added 8 targeted blocker regression tests | pytest 16 passed | No browser/live DB tests |
| P2-03 Secret/runtime artifacts in ZIP | FIXED_CORE | packager existing + validation | manual zip risk | Used `Scripts/package_clean_handoff.py` | clean ZIP created; forbidden runtime dirs absent | `Docker/.env.example` intentionally included as template |
| P2-04 Dirty baseline/handoff ambiguity | FIXED_CORE | report | dirty tree existed | report records changed files and packaging threshold | changed count 25 → full clean project | baseline was already dirty |

---

## 6. Test commands and output

```text
python -m pytest -q
................                                                         [100%]
16 passed in 2.02s
```

```text
python -m compileall Agent Core Gateway Sandbox State DataStore Apps/Api/safy_api Tests -q
PASS
```

```text
node --check Apps/Web/dashboard.js
PASS

node --check Apps/Web/schema-graph.js
PASS

node --check Apps/Web/login.js
PASS
```

```text
python Scripts/validate_skills.py
PASS
skills=11
canonical_text_skill=text_to_sql
```

```text
python Scripts/package_clean_handoff.py
Created: C:\Users\ASUS\SAFY_clean_handoff.zip
Included files: 1098
Excluded files: 1489
```

---

## 7. Live validation boundary

Not run in this environment:

- live PostgreSQL integration;
- live Supabase REST/RPC project;
- live SQL Server sandbox/write validation;
- live MySQL/Oracle validation;
- Docker-backed DBMS sandbox certification;
- browser automation click-path UAT.

Reason:

```text
No dedicated non-production live DB/Docker fixture was provided for this run.
```

Therefore final status is:

```text
PASS_CORE_WITH_BLOCKED_LIVE_VALIDATION
```

---

## 8. Security scan

Security grep over added diff lines did not find hardcoded secrets/tokens/password assignments. It reported only non-secret text/code references:

```text
+ dsn = oracledb.makedsn(...)
+ ... without exposing the connection string
```

No `.env`, `Data/secrets/`, `Data/sessions/`, `Data/sandboxes/`, `.git/`, `.pytest_cache/`, `__pycache__`, or `*.egg-info` was included in the clean handoff ZIP. The only `.env`-named file found in the ZIP is the allowed template:

```text
SAFY/Docker/.env.example
```

---

## 9. Packaging decision

Changed file count including untracked new files:

```text
tracked_modified_count: 23
untracked_count: 2
changed_plus_untracked_count: 25
```

User rule:

```text
>20 files changed → full project clean handoff
<=20 files changed → changed files only
```

Decision:

```text
Full clean project handoff ZIP
```

Artifact:

```text
C:\Users\ASUS\SAFY_clean_handoff.zip
```

SHA-256:

```text
934b1ccb6ef898ea8b92ac3d66e91316a37ae8388ef51cbb1284183c86fb4314
```

---

## 10. Remaining limitations

1. SQL Server sandbox/write path still needs real live certification before production claim.
2. Supabase complex read now has stable capability signaling, but a full read-RPC execution path still requires live/configured Supabase validation.
3. Target extraction is improved for multi-target DROP/TRUNCATE but remains regex/best-effort, not a complete SQL AST parser.
4. Browser source checks pass, but no Playwright/browser interaction test was run.
5. GET active-profile hidden live-test behavior was not deeply refactored in this pass; verify separately if it remains active in current API code paths.
6. Existing dirty baseline contained many already-modified files; this report identifies final changed set rather than claiming a clean pre-task tree.

---

## 11. Rollback notes

Rollback this pass by reverting the specific modifications to:

```text
Core/agent_state.py
Core/workflow_engine.py
Core/semantic_action_plan.py
Gateway/statement_target_extractor.py
Gateway/query_orchestrator.py
Gateway/db_drivers/supabase_rest_driver.py
Apps/Web/dashboard.js
Apps/Api/safy_api/main.py
Tests/test_current_blocker_regressions.py
Tests/test_project_packaging.py
current_state.md
Docs/Hermes_Execution/report/SAFY_CURRENT_BLOCKERS_FIX_REPORT_2026-06-25.md
```

Do not restore the seven user-deleted historical tests unless the user explicitly changes that decision.

---

## 12. Final status

```text
PASS_CORE_WITH_BLOCKED_LIVE_VALIDATION
```

Core regressions are covered by automated tests and static checks. Live DB/Docker certification remains blocked by environment and is explicitly not claimed.
