# SAFY Phase 5 Validation Checklist

## Status
Status: Approved for Phase 5 implementation. This document was originally a planning document and remains the canonical validation baseline. It does not claim Phase 5 has already been implemented.

## Static Validation
- [ ] `python -m compileall .` passes.
- [ ] `python -m pytest Tests/phase1 Tests/phase1_5 Tests/phase2 Tests/phase2_5 Tests/phase3 Tests/phase4 Tests/phase4_5` still passes.
- [ ] New Phase 5 tests exist and pass.
- [ ] Secret scan finds no raw API keys, passwords, Bearer tokens, or connection-string passwords outside intentional redaction tests.
- [ ] Docs do not claim Phase 5 implementation before tests prove it.

## SQL Guard Validation
- [ ] `/query/check` never executes SQL.
- [ ] `/query/execute` fails without valid `check_id`.
- [ ] `/query/execute` fails on mismatched `sql_hash`.
- [ ] `/query/execute` fails on mismatched `target`.
- [ ] `/query/execute` fails on mismatched `database_profile_id`.
- [ ] `/query/execute` fails on expired check.
- [ ] `/query/execute` fails on consumed check.
- [ ] Ambiguous SQL fails closed.
- [ ] Multi-statement mutation fails closed.

## Agent Connected Database Validation
- [ ] Agent SELECT/read-only connected database prompt can complete through SQL Guard and read-only adapter.
- [ ] Agent INSERT prompt against connected database is blocked.
- [ ] Agent UPDATE prompt against connected database is blocked.
- [ ] Agent DELETE prompt against connected database is blocked.
- [ ] Agent DROP/ALTER/TRUNCATE prompt against connected database is blocked.
- [ ] Agent admin/privilege/maintenance prompt against connected database is blocked.
- [ ] Agent destructive connected database prompts never request a confirmation code.
- [ ] Agent sandbox Create_database still works.

## User Query Validation
- [ ] User read-only connected database query executes only after `/query/check`.
- [ ] User high-risk query requiring confirmation blocks without code.
- [ ] User high-risk query blocks with wrong code.
- [ ] User high-risk query blocks with expired code.
- [ ] User high-risk query blocks when code is reused.
- [ ] User high-risk query blocks when profile changes after check.
- [ ] User high-risk query blocks when SQL hash changes after check.
- [ ] User cancellation is audited and does not execute SQL.

## Secret and Audit Validation
- [ ] Profile JSON stores env references only.
- [ ] API responses never include raw secrets.
- [ ] Audit records contain SQL hash and redacted metadata, not raw credentials.
- [ ] Logs redact passwords, API keys, tokens, Bearer headers, and connection-string secrets.
- [ ] Test fixtures contain placeholders only.

## UI Validation
- [ ] Static UI can run without bundling.
- [ ] Event listeners target existing DOM ids.
- [ ] Query execute payload sends matching `check_id`, `sql_hash`, `target`, and `database_profile_id`.
- [ ] Confirmation UI appears only when backend requires it.
- [ ] Unknown risk does not render as safe.
- [ ] User/model/backend text is rendered safely.

## Phase Gate
Phase 5 implementation may be reported only when every mandatory item above either passes or has a documented, user-approved exception.
