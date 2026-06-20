# Phase 10 UI Spec

Single active database profile for Phase 10. The database form includes driver, host, port, database/path, username, password mode, password env, SSL mode, test connection, and save profile.

UI status states: Not configured, Configured, Testing connection, Connection failed, Connected read-only, Schema loaded.

Schema viewer shows database/schema, tables, columns, data types, nullable, primary keys, foreign keys, indexes, row count estimate when available. Sample rows are not auto-fetched.

Query panel includes SQL editor, Check, Execute, result table, risk warning, blocked reason, safe alternative/limit suggestions, timeout warning, and retry.
