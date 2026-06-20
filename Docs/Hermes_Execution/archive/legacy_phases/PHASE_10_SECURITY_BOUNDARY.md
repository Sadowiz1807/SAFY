# Phase 10 Security Boundary

Defense in depth: SQL Guard + checked state binding + driver readonly connection/session settings + readonly database users.

`/query/check` must not open a database connection. `/query/execute` is the only execution path and must fail closed on missing/expired/consumed checks, hash mismatch, profile mismatch, target mismatch, or unsafe SQL.

Never persist raw passwords, raw DSNs, raw SQL by default, result rows, traceback details, or secret values.
