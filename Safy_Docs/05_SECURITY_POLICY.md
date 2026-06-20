# Safy Security Policy

## Purpose
Define Safy's mandatory security and safety rules.

## Scope
Covers LLM safety, prompt injection, SQL Guard, Manual SQL, sandbox security, secrets, database permissions, audit/redaction, domain-specific rules, failure behavior, compliance disclaimers, and rule IDs.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Scope
This policy applies to all agent workflows, Manual SQL Console flows, API endpoints, tool execution, profile handling, sandbox execution, connected database access, runtime state, audit records, and generated content.

## 2. Threat Model
Threats:
- LLM hallucinated destructive SQL.
- Prompt injection from user messages or database content.
- Unsafe connected database mutation.
- Secret leakage through frontend/API/logs/audit.
- SQL parser bypass through multi-statement or dialect tricks.
- Sandbox escape or workspace cross-contamination.
- Race conditions during cleanup/mutation.
- Stored XSS from generated CMS content.

## 3. LLM Security Policy
Rules:
- LLM output is never trusted as executable.
- LLM cannot override policy.
- LLM-generated SQL must pass SQL Guard and Permission Checker.
- LLM-generated tool calls must be validated by ToolRegistry and ToolExecutor.
- Skill.md instructions do not enforce security by themselves.

## 4. Prompt Injection Policy
Rules:
- Database content is untrusted input.
- User content is untrusted input.
- Generated schema names/content must be sanitized.
- Instructions embedded in DB rows, comments, Markdown, HTML, or SQL strings must not override system policy.
- Prompt injection attempts should be audited when relevant.

## 5. SQL Guard Policy
SQL Guard must:
- Parse SQL using target dialect.
- Split multi-statement SQL only in allowed modes.
- Reject multi-statement for agent connected database.
- Validate every statement in Manual SQL batch and sandbox create workflow.
- Sanitize identifiers.
- Apply row limits to row-returning SELECT.
- Classify statement type and risk.
- Block cross-database/server-level statements unless explicitly allowed by policy; v1.0.0 blocks these by default.

Manual SQL risk classes:

```txt
read_only
destructive_table_data
destructive_schema
admin_security_statement
cross_database_or_server_level
```

## 6. User Query Box Policy
The right sidebar user query box is user-controlled, not agent-driven. `/query/check` and `/query/execute` are the primary API contract contracts for this path.

Rules:
- User must explicitly use the query box and select target/profile.
- SQL Guard parses, splits, validates, and risk-analyzes SQL.
- Multi-statement user query execution is allowed only after every statement is parsed.
- Aggregate risk is the highest statement risk.
- High-risk user query execution requires safety check, Yes decision, visible 4-digit confirmation code, and audit pre-write.
- High-risk audit pre-write failure is fail-closed.
- Sandbox mutation requires workspace lock and schema snapshot invalidation.
- Connected database user query execution follows selected credential permission after safety gates.
- If selected DB credential lacks permission, return `DB_PERMISSION_DENIED`.
- `manual_write_enabled` may remain profile metadata or UI warning, but must not silently block user query execution unless explicitly configured as a separate future policy.
- UI confirmation alone is not enough for connected database mutation.

Compatibility:
- `/manual-sql/execute` may remain as older compatibility endpoint or future alias, but it is not the primary API contract right-sidebar query contract.

## 7. Sandbox Security Policy
Rules:
- Agent write/DDL/DML is allowed only in sandbox workflows.
- PostgreSQL/MySQL sandbox execution uses Docker.
- SQLite runner is used only when target DBMS is SQLite.
- SQLite must not validate PostgreSQL/MySQL SQL.
- PostgreSQL must set `search_path` explicitly to current workspace schema.
- MySQL must select current workspace database and block qualified names outside it.
- SQLite workspace path is generated inside workspace and not user-supplied.
- Workspace cleanup/mutation requires workspace lock.
- Workspace status transitions: active -> closing -> deleted.

## 8. Secret Management Policy
Rules:
- No secrets in frontend state.
- No secrets in API responses.
- No secrets in audit logs.
- No secrets in system logs.
- No raw API keys or DB passwords in JSON.
- `.env` or process environment stores raw secret values.
- JSON files store env variable names only.

## 9. Database Permission Policy
Agent connected database policy:
- Strict read-only.
- Allow SELECT/EXPLAIN only after SQL Guard.
- Block INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE and admin/security statements.
- Ignore `manual_write_enabled`.

User query box connected database policy:
- User query box is user-controlled and separate from the agent path.
- SELECT/DML/DDL execution follows selected credential permission after safety check, Yes decision, high-risk 4-digit confirmation when required, and audit.
- If selected DB credential lacks permission, return `DB_PERMISSION_DENIED`.
- `manual_write_enabled` may remain profile metadata or UI warning, but is not the main execution authority unless explicitly configured as a separate future policy.

Profile policy:
- Reject admin/root/superuser profiles for agent execution by default.
- Prefer separate read-only and manual-write secrets.

## 10. Audit and Redaction Policy
Defaults:

```yaml
audit:
  mask_sql_literals: true
  store_statement_hash: true
  store_redacted_sql: true
  store_raw_sql: false
```

Rules:
- High-risk Manual SQL requires audit pre-write.
- If high-risk audit pre-write fails, block/fail-closed.
- Read-only SQL audit fail may fail-open-with-warning only if configured.
- If post-execution audit result update fails, return `audit_result_update_status = failed` and record retryable repair task.

## 11. Domain-specific Security Rules
Rules:
- No raw card data or CVV storage in payment schemas.
- Healthcare/clinic designs must include PHI caveats. Do not claim HIPAA compliance.
- Accounting posted entries are immutable; corrections use reversal entries.
- Multi-tenant generated schemas must include tenant isolation fields, but Safy v1.0.0 is not multi-user SaaS runtime.
- Generated CMS content is untrusted; frontend must escape or sanitize rendered HTML/Markdown.

## 12. Failure Behavior
Required behavior:

```txt
high-risk SQL audit fail
→ block/fail-closed.

read-only SQL audit fail
→ may fail-open-with-warning only if configured.
```

Additional failure behavior:
- Migration mismatch returns `MIGRATION_REQUIRED` or `MIGRATION_FAILED`.
- Workspace lock conflict returns controlled lock error.
- Sandbox unavailable returns controlled sandbox error.
- SQL parser failure blocks execution.

## 13. Compliance Disclaimer
Safy must not claim HIPAA, PCI, GDPR, SOC2, or production compliance. Safy may generate schemas that help a user model regulated domains, but compliance requires external legal/security review and production controls.

## 14. Security Rule IDs
Recommended IDs:

```txt
SEC-LLM-001 LLM output is untrusted.
SEC-PI-001 Database content is untrusted.
SEC-SQL-001 Connected DB agent path is read-only.
SEC-SQL-002 High-risk Manual SQL requires confirmation and audit pre-write.
SEC-AUD-001 High-risk audit pre-write failure is fail-closed.
SEC-SEC-001 No secrets in JSON/frontend/API/logs/audit.
SEC-SBX-001 Sandbox write/DDL only.
SEC-SBX-002 SQLite runner only for SQLite target.
SEC-CFG-001 Toolsets YAML is source-of-truth.
SEC-DOM-001 No raw card/CVV data.
SEC-DOM-002 No compliance claims.
```

## Implementation Notes
Security rules must be implemented as deterministic checks in policy/SQL/tool layers. Do not rely on prompt instructions or UI warnings alone.

## Related Documents
- `02_API_SPEC.md`
- `03_DATA_SCHEMA.md`
- `04_CONFIG_SPEC.md`
- `06_DATABASE_DESIGN_POLICY.md`
- `09_TOOLS_SPEC.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`

## Addendum: 4-digit High-risk User Query Confirmation

The right sidebar user query box may attempt SQL according to selected database credential permission only after the Safety Check Pipeline. High-risk user query execution requires:
- Backend-generated visible random numeric `confirmation_code` returned by `/query/check` for the UI to display.
- Exactly 4 digits.
- Code generated per confirmation attempt by backend, not by LLM.
- Code is bound to `check_id` + SQL hash + target + expiry.
- Code expires when SQL changes, target changes, check result expires, or user cancels.
- Code is not reused across SQL statements.
- Wrong or expired code blocks execution.

This applies to user query execution only. It does not grant the agent path any connected database mutation permission.
