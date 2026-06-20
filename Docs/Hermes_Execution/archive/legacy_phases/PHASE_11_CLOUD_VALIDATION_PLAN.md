# Phase 11 Cloud Validation Plan

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Rule

Cloud live tests are required eventually, but credentials are not available now. Do not run cloud tests or claim cloud live PASS during planning.

## Env Gates

- `SAFY_PHASE11_CLOUD_LIVE_REQUIRED=1`
- `SAFY_PHASE11_SUPABASE_BACKUP_REQUIRED=1`
- `SAFY_PHASE11_SUPABASE_LIVE_REQUIRED=1`
- `SAFY_PHASE11_CLOUDSQL_LIVE_REQUIRED=1`
- `SAFY_PHASE11_AURORA_LIVE_REQUIRED=1`

Credential examples:

- `SAFY_SUPABASE_PASSWORD`
- `SAFY_CLOUDSQL_PASSWORD`
- `SAFY_AURORA_PASSWORD`
- `SAFY_SQLSERVER_PASSWORD`
- `SAFY_ORACLE_PASSWORD`

## Status Logic

- If a required live flag is set and credentials are missing, report `BLOCKED_CLOUD_VALIDATION`.
- If a live flag is not set, skip live tests and report NOT RUN / WAITING_FOR_CREDENTIALS.
- Do not store credentials in profiles, sessions, audit, logs, reports, or frontend JS.

## Manual Smoke Expectations

For each provider, document profile JSON shape, env vars required, network/SSL requirements, read-only user requirement, safe SELECT smoke, blocked write/DDL smoke, and redaction evidence.

## Final Gate Question

Before implementation/final release, the user must decide whether `PASS_PHASE_11_SQL_DIALECT_PROVIDER_EXPANSION` requires cloud live validation in the same phase or whether cloud live validation is a follow-up gate.
