# Phase 11 Public Test Data Plan

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Policy

Use official/public sample datasets restored into local test databases. Do not use random public database endpoints, unstable demo servers, or third-party credentials.

| Database/provider target | Dataset source | Source type | Validation use | Blocking requirement |
| --- | --- | --- | --- | --- |
| SQL Server | Microsoft AdventureWorks | Official Microsoft sample database | Local SQL Server seed; driver contract and read-only guard validation | SQL Server Docker/local target and ODBC Driver 18 available |
| Oracle | Oracle Database Sample Schemas | Official Oracle sample schemas | Oracle local/Docker seed; driver contract and read-only guard validation | Suitable Oracle Free/XE/local target and sample schema install available |
| Cloud SQL MySQL profile | MySQL Sakila | Official MySQL sample database | Local MySQL seed for mapping tests; future live smoke | Cloud live waits for user Google credentials |
| Cloud SQL PostgreSQL profile | Pagila | Public PostgreSQL sample adapted from Sakila | Local PostgreSQL seed for mapping tests; future live smoke | Cloud live waits for user Google credentials |
| Cloud SQL SQL Server profile | Microsoft AdventureWorks | Official Microsoft sample database | Local SQL Server seed for mapping tests; future live smoke | Cloud live waits for user Google credentials |
| Aurora MySQL profile | MySQL Sakila | Official MySQL sample database | Local MySQL seed for mapping tests; future live smoke | Cloud live waits for user AWS credentials |
| Aurora PostgreSQL profile | Pagila | Public PostgreSQL sample adapted from Sakila | Local PostgreSQL seed for mapping tests; future live smoke | Cloud live waits for user AWS credentials |
| Supabase profile | `db_cluster-27-01-2026@16-06-46.backup.gz` | User-provided private backup | Local PostgreSQL/Supabase-compatible restore; future live Supabase smoke | Backup present locally for restore; live waits for Supabase credentials |

## Documentation Required During Implementation

For each dataset, record source URL, license/terms, checksum where feasible, restore commands, schema names, and read-only SAFY user creation steps.
