# Phase 9 Migration Plan

Phase 9 is split into two implementation passes after this planning package is approved.

## Pass 1: Clean Repo, JSON Scaffold, Project Restructuring, Dashboard, Launcher

### Scope

- Clean repo planning execution after approval.
- Inventory generated artifacts and remove only approved generated files.
- Archive/merge legacy docs/folders with verification.
- Create JSON storage scaffold code plan without migrating data yet.
- Update config path plan for repo-root/Data resolution.
- Fix FastAPI metadata/version plan to `SAFY` / `1.1.0`.
- Serve dashboard at `/`.
- Add `/health`.
- Fix `mock_only` semantics plan so real read-only mode is distinguishable from mocks.
- Improve request ID generation plan where needed.
- Improve error redaction plan where needed.
- Add `safy run` launcher plan.
- Auto-open dashboard plan.
- Update README plan after implementation.
- Create `Tests/phase9` plan.

### Dependencies

Phase 8 final state and safety boundary, package metadata feasibility, static UI path verification, no unresolved user decision on tracked file deletions.

### Risk Level

Medium: route/launcher/path changes can break tests or developer docs if not carefully bound.

### Rollback Strategy

Keep route changes small, preserve `/docs` and existing API endpoints, isolate launcher code, and revert only Phase 9 files if validation fails. Do not alter Phase 8 safety code beyond required path/config integration.

### Acceptance Criteria

`safy run` works from `C:\Users\ASUS`, dashboard loads at `/`, `/docs` remains developer docs, `/health` returns standard envelope, generated cleanup is documented and safe, and full Phase 1-9 tests pass.

### Test Strategy

Compile/static checks, node check, endpoint checks, launcher checks from outside repo, generated artifact inventory, and full pytest suite including new Phase 9 tests.

## Pass 2: JSON Storage Migration

### Scope

- Migrate profile stores to `Data/safy_profiles.json`.
- Migrate session/runtime state to `Data/sessions/session_<id>.json`.
- Migrate or adapt audit to `Data/audit/safy_audit.jsonl`.
- Preserve recovery/workspace/session behavior.
- Preserve query check/execute state safety.
- Preserve no result-row persistence.
- Update tests and validate Phase 1-9 suite.

### Dependencies

Pass 1 path/config consistency, backups of existing JSON/SQLite stores, schema mapping documents, corruption recovery tests.

### Risk Level

High: changing state storage can affect sessions, audit, recovery, workspaces, profile persistence, and query execution binding.

### Rollback Strategy

Use backups, migration dry-run mode, legacy read compatibility or feature flag, one-way write switch only after validation, and rollback to existing SQLite/JSON stores if consistency checks fail.

### Acceptance Criteria

Profile/session/audit JSON stores are canonical, raw secrets rejected, query execute binding preserved, result rows not persisted, audit JSONL append works, legacy data migrates or is safely ignored with user-visible report, and full Phase 1-9 suite passes.

### Test Strategy

Migration unit tests, legacy fixture migration, corruption tests, atomic write tests, redaction tests, query state binding regression tests, audit JSONL tests, and full suite.
