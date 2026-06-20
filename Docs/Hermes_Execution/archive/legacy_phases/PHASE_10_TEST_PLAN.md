# Phase 10 Test Plan

- Unit test base driver contract, secret redaction, SQL policy, profile storage, query binding, UI contract, session/audit metadata.
- SQLite integration creates a real local DB and validates connection, schema, SELECT, and blocked INSERT.
- MySQL/PostgreSQL integration use Docker services and readonly users; absence of Docker blocks final PASS.
- Validation: compileall, node check, `Tests/phase10`, full `Tests`, secret scan, API smoke.
