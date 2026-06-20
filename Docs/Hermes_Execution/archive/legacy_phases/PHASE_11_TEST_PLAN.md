# Phase 11 Test Plan

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Future Test Categories

- `Tests/phase11/test_sqlserver_driver.py`
- `Tests/phase11/test_oracle_driver.py`
- `Tests/phase11/test_provider_profiles.py`
- `Tests/phase11/test_public_test_data_plan.py`
- `Tests/phase11/test_supabase_backup_restore_plan.py`
- `Tests/phase11/test_phase11_ui_provider_mapping.py`
- `Tests/phase11/test_phase11_security_boundary.py`
- `Tests/phase11/test_phase11_cloud_live_contract.py`

## Required Coverage

- SQL Server driver contract tests
- SQL Server integration tests with AdventureWorks
- Oracle driver contract tests
- Oracle integration tests with Oracle Sample Schemas
- Provider profile mapping tests
- Supabase local backup restore plan/tests
- Supabase live env-gated tests
- Cloud SQL profile mapping tests with public seed mapping
- Aurora profile mapping tests with public seed mapping
- UI invalid combination tests
- SQL Guard dialect tests
- Credential redaction tests
- No password persistence tests
- No result row persistence tests
- No raw SQL persistence by default tests
- Agent guarded auto SELECT tests across new dialects where feasible
- Full Phase 10 regression tests

## Strategy

- Mandatory local/Docker tests validate real dialect drivers when local targets are available.
- Public data restore tests validate official sample data setup and read-only SAFY users.
- Env-gated cloud live tests run only with explicit flags and user credentials.
- Manual smoke tests document profile shape, connection method, expected PASS/BLOCKED reporting, and redaction evidence.
