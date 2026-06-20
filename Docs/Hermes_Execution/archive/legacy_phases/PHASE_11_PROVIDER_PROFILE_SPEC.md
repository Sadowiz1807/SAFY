# Phase 11 Provider Profile Spec

Phase: `Phase 11: SQL Dialect & Cloud Database Provider Expansion`  
Target release: `v1.3.0 SQL Dialect & Cloud Provider Expansion`  
Planning status: `PLANNING_COMPLETE`  
Implementation allowed: `false`

This is a planning artifact only. It does not authorize code changes, driver logic changes, SQL Guard changes, Docker service changes, test execution, cloud connections, or credential collection.

## Architecture Decision

Providers are compatibility profiles over real dialect drivers. The provider profile selects defaults, validates compatible engine choices, controls credential handling, and documents live validation requirements.

## Provider Mapping

| Provider | Supported engines | Driver mapping |
| --- | --- | --- |
| Self-hosted / Direct | SQLite, MySQL, PostgreSQL, SQL Server, Oracle | Same as selected driver |
| Supabase | PostgreSQL | `postgresql` |
| Google Cloud SQL | MySQL, PostgreSQL, SQL Server | `mysql`, `postgresql`, `sqlserver` |
| Amazon Aurora | MySQL, PostgreSQL | `mysql`, `postgresql` |

## Invalid Combinations

- Supabase + MySQL
- Supabase + SQL Server
- Supabase + Oracle
- Aurora + SQL Server
- Aurora + Oracle
- Cloud SQL + Oracle

## Supabase Profile

```json
{
  "id": "supabase_main",
  "type": "database",
  "driver": "postgresql",
  "provider": "supabase",
  "host": "db.<project-ref>.supabase.co",
  "port": 5432,
  "database": "postgres",
  "username": "postgres",
  "password_mode": "env",
  "password_env": "SAFY_SUPABASE_PASSWORD",
  "ssl_mode": "require",
  "read_only": true,
  "active": true
}
```

Support direct connection and pooler connection when the user supplies host/port.

## Google Cloud SQL Profile Fields

- `provider: google_cloud_sql`
- `engine: mysql | postgresql | sqlserver`
- `connection_mode: direct | cloud_sql_proxy`
- `cloud_sql_instance_connection_name`
- host, port, database, username, `password_env`, `ssl_mode`

Cloud SQL Auth Proxy is deployment/configuration, not a DB query driver.

## Amazon Aurora Profile Fields

- `provider: aws_aurora`
- `engine: aurora_mysql | aurora_postgresql`
- `cluster_endpoint`, `reader_endpoint`
- host, port, database, username, `password_env`, `ssl_mode`

Aurora is protocol-compatible with MySQL/PostgreSQL for this SAFY use case.
