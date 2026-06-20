# Phase 2 Main-Agent Decision Ledger

Mode A artifact. This ledger records canonical decisions before repair. It is not a source of truth; core artifacts remain authoritative according to the authority map.

| Concept | Canonical decision | Canonical owner | Other references | Historical wording | Implementation status | User decision needed |
|---|---|---|---|---|---|---|
| Source authority hierarchy | SAFY_source owns product intent/policy/module ownership; contracts/schema/security/plan own their domains; reports/tasks are evidence only. | SAFY_source.md; PHASE_2_PLAN.md | Reports, matrix, checklists | Reports may say PASS but cannot override specs. | Documentation only | No |
| Agent connected-DB authority | Agent connected database is strict read-only. | SAFY_source.md; PHASE_2_SECURITY_SPEC.md | CONTRACTS, PLAN | None | Documentation only | No |
| User query authority | Selected credential permission + safety check + explicit confirmation + high-risk challenge when required + audit pre-write. | SAFY_source.md; SECURITY_SPEC | CONTRACTS, PLAN | manual_write_enabled legacy wording must not grant authority. | Documentation only | No |
| manual_write_enabled role | Legacy/migration/UI/future-policy metadata only; not current execution authority. | SAFY_source.md; DATA_SCHEMA_SPEC | PLAN, VALIDATION | Historical aliases may mention it only as migration-only. | Documentation only | No |
| Profile JSON schema version | Independent domain, remains v1 unless separate profile migration approved. | DATA_SCHEMA_SPEC | SOURCE, PLAN, DELTA | Do not conflate with DB schema. | Documentation only | No |
| Runtime DB schema version | Historical foundation v1; final refined target v2; hybrid rebuild/migration policy. | DATA_SCHEMA_SPEC | SOURCE, PLAN, SECURITY, DELTA | Historical evidence v1 allowed when marked. | Final refinement NOT_VERIFIED | No |
| Audit DB schema version | Historical foundation v1; final refined target v2; hybrid rebuild/migration policy. | DATA_SCHEMA_SPEC | SOURCE, PLAN, SECURITY, DELTA | Historical evidence v1 allowed when marked. | Final refinement NOT_VERIFIED | No |
| Audit repair location | Product v1.0.0 stores repair state in audit_log fields introduced by audit schema v2; separate queue future-only. | DATA_SCHEMA_SPEC; SECURITY_SPEC | PLAN, CONTRACTS, VALIDATION, REPORTS | Old audit repair v2 wording must be removed or marked historical only. | Final refinement NOT_VERIFIED | No |
| High-risk confirmation lifecycle | create -> atomic validate_and_reserve -> execute -> mark_consumed; release/invalidate on pre-side-effect failure. | CONTRACTS; SECURITY_SPEC | PLAN, DELTA | None | Final refinement NOT_VERIFIED | No |
| Confirmation persistence | Backend remains open; atomicity still mandatory for every backend. | CONTRACTS; PLAN matrix | DELTA | None | Open decision | Yes |
| Atomicity requirement | Mandatory, not conditional on persistence/multi-worker. | CONTRACTS; SECURITY_SPEC | DELTA, PLAN | None | Final refinement NOT_VERIFIED | No |
| Runtime/audit artifact policy | Controls generated DB files/fixtures commit/local/operator-managed only; does not reopen v1->v2 migration strategy. | PLAN; matrix | DELTA | None | Open decision | Yes |
| Historical task dispatchability | TASKS is historical task board; no current dispatch from it. | PHASE_2_TASKS.yaml | PLAN, reports | Historical dispatchability may be retained under historical namespace only. | Historical evidence | No |
| Report evidence boundary | Reports validate original v1 foundation only, not final v2 refinements. | Historical reports | Final reports | Evidence only | Historical evidence | No |
| Report authority | Reports are summaries/evidence only; specs override. | PLAN; report banners | FINAL_* | PASS language must be bounded. | Documentation only | No |
| Project tree paths | Distinguish existing artifacts, target implementation paths, and conceptual future docs. | SAFY_source.md | DELTA | N/A | Documentation only | No |
| Test paths | Proposed paths under Tests/phase2; may be created/replaced by equivalent tests. | DELTA | Checklist | N/A | Proposed only | No |
| State responsibilities | Runtime state in runtime DB; schema v2 target tables are final refinement. | DATA_SCHEMA_SPEC; CONTRACTS | PLAN | v1 evidence historical. | Final refinement NOT_VERIFIED | No |
| Audit responsibilities | Audit DB owns redacted audit events, schema v2 repair fields, no raw SQL by default. | DATA_SCHEMA_SPEC; SECURITY_SPEC | CONTRACTS | v1 evidence historical. | Final refinement NOT_VERIFIED | No |
| Phase 3 dispatch rule | Phase 3 and Delta implementation remain NOT_DISPATCHED unless explicitly approved. | PLAN; ACCEPTANCE | DELTA | N/A | Not dispatched | No |
