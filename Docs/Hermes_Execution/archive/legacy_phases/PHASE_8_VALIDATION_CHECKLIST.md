# Phase 8 Validation Checklist

Executed by main-agent only. No sub-agents used.

## Static validation

Planned validation commands:

- `python -m compileall .`
- import checks for planned Python modules
- `node --check Apps/Web/mock-ui.js`

Notes:

- compileall warnings about historical cache artifacts should be recorded if they occur
- no tracked `.pyc` artifacts should be intentionally created as a planning deliverable

## Unit tests planned

Mandatory fake adapter tests:

- fake adapter connection
- fake adapter schema introspection
- fake adapter `SELECT` execution
- blocked `INSERT`
- blocked write SQL
- SQL Guard integration
- profile secret redaction
- transient password non-persistence
- sensitive `SELECT` confirmation
- sample rows approval
- no result-row persistence in session
- audit redacted SQL + `sql_hash`
- UI mode labels

## Optional integration tests planned

Optional integration suites:

- Docker MySQL integration
- Docker PostgreSQL integration
- SQLite path-confined connected-file integration
- skip integration tests if env vars / Docker missing

Integration expectations:

- MySQL optional integration is first priority
- PostgreSQL optional integration is second priority
- SQLite connected-file tests use temporary path-confined files

## Security scans

Planned scans:

- secret scan
- traceback scan
- driver error redaction scan
- raw result persistence scan

Minimum evidence to capture:

- no raw credentials stored in profile JSON
- no raw credentials stored in runtime/audit/session tables
- no raw traceback or driver error exposed in API/UI output
- no result rows persisted in session history

## Release acceptance

Release acceptance after future implementation requires:

- all mandatory fake adapter tests pass
- optional integration tests pass when environment exists
- docs and reports complete
- final report declares `v1.1.0 Real Connected DB Read-only` only after implementation validation
- implementation still proves writes remain blocked and `INSERT` remains blocked

## Optional planning-run baseline validation

For this planning run, optional baseline validation may record results from:

- `python -m compileall .`
- `python -m pytest Tests/phase1 Tests/phase1_5 Tests/phase2 Tests/phase2_5 Tests/phase3 Tests/phase4 Tests/phase4_5 Tests/phase5 Tests/phase6 Tests/phase7 -q --basetemp=tmp/pytest_phase8_planning_baseline`
- `node --check Apps/Web/mock-ui.js`

If run, record exit codes and outputs in the planning report.
If not run, state why not.
