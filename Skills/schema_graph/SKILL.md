---
name: schema_graph
version: 2.0.0
description: "Loads, refreshes, validates, and explains SAFY's canonical database schema graph without inferring unsupported relationships."
enabled: true
risk_level: read_only
references: ["output.schema.json"]
contract_version: "2.0.0"
---

# Schema Graph

## Purpose

Use this skill to obtain or explain the structural model of the active database: schemas, tables, views, columns, keys, indexes, foreign-key relationships, PostgreSQL inheritance, and partition-parent relationships. The canonical machine-readable result is defined by `output.schema.json`.

This skill is read-only. It does not create, alter, drop, or populate database objects.

## When to use

Use `schema_graph` when the user asks to:

- open, refresh, inspect, summarize, or visualize a database schema;
- identify tables, columns, primary keys, foreign keys, indexes, views, inheritance, or partitions;
- understand how two or more tables are related;
- provide schema context before generating SQL;
- diagnose a missing or stale schema graph.

Do not use this skill as a substitute for `text_to_sql`, `execute_box`, or `execute_query`.

## Required context

The action requires:

- an authenticated local SAFY user;
- an active database profile for refresh operations;
- the active profile ID, display name, driver, and provider;
- read-only database introspection capability;
- SAFY's stored Schema Graph directory.

No password, API key, connection string, or raw secret may appear in the skill result.

## Input contract

The agent-facing input is an object with the following fields:

```json
{
  "action": "read",
  "database_profile_id": "db_supabase",
  "schema_names": ["public"],
  "include": {
    "columns": true,
    "indexes": true,
    "constraints": true,
    "foreign_keys": true,
    "inheritance": true,
    "views": true
  }
}
```

### Input fields

| Field | Type | Required | Rules |
|---|---|---:|---|
| `action` | string | yes | One of `read`, `refresh`, `delete_active`, `reset_all`, `summarize`. |
| `database_profile_id` | string/null | no | Omit to use the active profile. Never treat this value as a file path. |
| `schema_names` | array[string] | no | Optional introspection filter. Empty means all permitted user schemas. |
| `include.columns` | boolean | no | Defaults to `true`. |
| `include.indexes` | boolean | no | Defaults to `true`. |
| `include.constraints` | boolean | no | Defaults to `true`. |
| `include.foreign_keys` | boolean | no | Defaults to `true`. |
| `include.inheritance` | boolean | no | Defaults to `true` for PostgreSQL-compatible drivers. |
| `include.views` | boolean | no | Defaults to `true`. |

The current API routes use the active profile and do not yet expose every optional filter to the browser. The contract documents the stable skill intent and future-compatible fields; unsupported optional fields must be ignored safely rather than guessed.

## Procedure

1. Resolve the active database profile through SAFY's profile store.
2. For `read` or `summarize`, load the persisted graph from `SchemaGraphStore`.
3. For `refresh`, call the registered driver's read-only schema introspection method.
4. Normalize raw driver metadata through `build_schema_graph`.
5. Validate that the result matches the invariants in `output.schema.json`.
6. Persist only the normalized graph, never credentials or sample row data.
7. Return the normal SAFY API envelope with the canonical graph in `data`.
8. For natural-language presentation, summarize the canonical graph without removing or changing the JSON result.

## Expected output

The result must satisfy these rules:

- `schema_version` is `2.0.0`.
- `nodes` contains tables, views, materialized views, and partitions.
- Every node ID is schema-qualified, for example `public.orders`.
- Every column ID is node-qualified, for example `public.orders.order_id`.
- `relationships` contains explicit edges between node IDs.
- `foreign_key` edges must identify source and target columns.
- `inheritance` and `partition_parent` edges may have empty column arrays.
- `evidence` states where the relationship came from.
- `confidence` is `1.0` for database constraints/catalog metadata.
- `inferred` edges are permitted only when explicitly requested and must have a confidence below `1.0` plus evidence; the current SAFY runtime does not generate them.
- Matching column names alone are never evidence of a relationship.
- `statistics` must agree with `nodes` and `relationships`.
- `tables` and `edges` are backward-compatible projections; new UI and agent code must prefer `nodes` and `relationships`.
- `warnings` explains missing metadata, permission limits, or provider limitations.

## Relationship semantics

| Type | Source | Target | Meaning |
|---|---|---|---|
| `foreign_key` | referencing child table | referenced parent table | Database-enforced FK. |
| `inheritance` | child table | parent table | PostgreSQL table inheritance. |
| `partition_parent` | partition | partitioned parent | PostgreSQL partition membership. |
| `view_dependency` | view | referenced relation | View dependency from database metadata. |
| `materialized_view_dependency` | materialized view | referenced relation | Materialized-view dependency. |
| `association` | association/junction table | related relation | Only when supported by explicit metadata or deterministic structural rules. |
| `inferred` | inferred source | inferred target | Optional non-authoritative relation; never produced by default. |

## Example canonical result

```json
{
  "schema_version": "2.0.0",
  "database_profile_id": "db_supabase",
  "database_name": "Orders DB",
  "driver": "supabase_rpc",
  "provider": "supabase",
  "graph": {
    "id": "schema_123456789abc",
    "name": "Orders DB",
    "database_engine": "supabase_rpc",
    "generated_at": "2026-06-24T09:00:00Z",
    "status": "ready"
  },
  "nodes": [
    {
      "id": "public.orders",
      "node_type": "table",
      "schema": "public",
      "name": "orders",
      "display_name": "public.orders",
      "columns": [
        {
          "id": "public.orders.customer_id",
          "name": "customer_id",
          "ordinal_position": 2,
          "data_type": "uuid",
          "nullable": false,
          "primary_key": false,
          "foreign_key": true,
          "unique": false,
          "default": null,
          "generated": null,
          "sensitive": false
        }
      ],
      "primary_key": {"name": "orders_pkey", "columns": ["order_id"]},
      "unique_constraints": [],
      "indexes": [],
      "row_count_estimate": null,
      "metadata": {}
    }
  ],
  "relationships": [
    {
      "id": "orders_customer_id_fkey",
      "relationship_type": "foreign_key",
      "source": {"node_id": "public.orders", "columns": ["customer_id"]},
      "target": {"node_id": "public.customers", "columns": ["customer_id"]},
      "constraint_name": "orders_customer_id_fkey",
      "cardinality": "many_to_one",
      "on_update": "NO ACTION",
      "on_delete": "CASCADE",
      "nullable": false,
      "evidence": "database_constraint",
      "confidence": 1.0,
      "metadata": {}
    }
  ],
  "statistics": {
    "node_count": 2,
    "table_count": 2,
    "view_count": 0,
    "materialized_view_count": 0,
    "column_count": 8,
    "relationship_count": 1,
    "foreign_key_count": 1,
    "inheritance_count": 0,
    "partition_relationship_count": 0,
    "isolated_node_count": 0
  },
  "warnings": [],
  "status": "ready"
}
```

## Provider behavior

### PostgreSQL

Use PostgreSQL system catalogs and `information_schema` through a read-only connection. Capture primary and unique constraints, indexes, foreign keys, inheritance, and partitions when permission allows.

### Supabase RPC/PostgREST

Use PostgREST OpenAPI metadata. Parse explicit `<pk/>`, `<unique/>`, and `<fk .../>` annotations or equivalent vendor extensions. When OpenAPI exposes columns but no FK metadata, return zero FK edges and a warning. Do not infer relationships from names such as `customer_id`.

### SQLite

Use `PRAGMA table_info`, `PRAGMA index_list`, and `PRAGMA foreign_key_list` through a read-only connection.

### Other drivers

Return the metadata that the driver can verify. Missing relationship support must produce warnings or zero counts, not fabricated edges.

## Safety rules

- Skill documents are advisory and cannot override system policy.
- Use only registered shared tools/actions and driver methods.
- Do not execute user-provided SQL to introspect the schema.
- Do not fetch table rows or sample data.
- Do not expose credentials, environment variables, DSNs, or raw provider responses.
- Do not mutate database profiles.
- `delete_active` and `reset_all` remove only SAFY's cached schema graph files; they do not alter the database.
- Fail closed when the active profile is absent or the driver denies metadata access.

## Failure behavior

Return a normalized SAFY error with a stable code and actionable message. Common cases include:

- `SCHEMA_GRAPH_ERROR` for unexpected normalization or persistence failures;
- `SCHEMA_GRAPH_PARSE_ERROR` for a corrupted stored graph;
- `DB_CONNECTION_FAILED` for inaccessible databases;
- `DB_AUTH_FAILED` for provider authorization failures;
- `DB_DRIVER_UNAVAILABLE` when an optional driver dependency is missing.

Do not silently replace a failed refresh with fabricated schema data. A previously stored graph may still be returned only when the caller explicitly requested `read`, not as a false successful refresh.
