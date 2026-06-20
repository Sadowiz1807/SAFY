# Safy Database Design Policy

## Purpose
Define how Safy's agent designs database schemas from natural-language requirements.

## Scope
Covers input requirements, domain detection, entity/attribute extraction, business rule classification, relationships, constraints, indexes, naming, dialect mapping, sample data, views/procedures, clarification triggers, and validation checklist.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Scope
This policy applies to Create_database and related schema-design workflows. It governs design output before SQL execution and applies across PostgreSQL, MySQL, and SQLite with dialect-specific mapping.

## 2. Input Requirement
Agent should extract:
- Domain and product type.
- Major entities.
- Roles/users.
- Business processes.
- Required reports/queries.
- Data sensitivity.
- Target DBMS.
- Whether sample data is requested.

Ask user if the missing requirement would change schema materially, especially domain, tenant scope, payment/PHI handling, or target DBMS.

## 3. Domain Detection
Detect domain using explicit words and entity patterns. Supported reviewed packs:
- ecommerce
- clinic_booking
- inventory_warehouse
- school_enrollment
- accounting_ledger
- multi_tenant_saas
- blog_cms
- generic

When multiple domains match, use cross-domain patterns and ask clarification if core modeling choices conflict.

## 4. Entity Extraction
Extract nouns and process objects as candidate entities. Keep major business tables distinct from lookup tables and line-item tables.

Rules:
- Use separate tables for dependent entities.
- Use line-item tables for transaction details.
- Use junction tables for many-to-many relationships.
- Avoid dumping unrelated attributes into one table.

## 5. Attribute Extraction
Attributes must include data type, nullability, default, uniqueness, and whether the field is derived, sensitive, or business identifier.

Rules:
- Do not store raw card numbers/CVV.
- Mark PHI/PII-sensitive fields in design notes.
- Use timestamps where lifecycle matters.
- Use status fields with constraints where finite states exist.

## 6. Business Rule Classification
Classify rules into:

```txt
Field-level
Record-level
Relationship-level
Process-level
Temporal/capacity
Financial/ledger
Tenant isolation
```

Examples:
- Field-level: quantity must be positive.
- Record-level: order total cannot be negative.
- Relationship-level: enrollment references student and course.
- Process-level: posted ledger entries are immutable.
- Temporal/capacity: appointment cannot exceed clinic schedule/capacity.
- Financial/ledger: debit total equals credit total.
- Tenant isolation: tenant-owned rows include tenant_id.

## 7. Relationship and Cardinality Policy
Rules:
- One-to-many uses FK on child table.
- Many-to-many uses junction table with composite unique constraint.
- Transaction header/details use header table plus line-item table.
- Optional relationships must be explicitly nullable.
- Cascades must be conservative and domain-appropriate.

## 8. Constraint Generation Policy
Required rules:
- Every major business table needs a primary key.
- Use foreign keys for dependent entities.
- Use many-to-many junction tables.
- Use line-item tables for transaction details.
- Use UNIQUE for business identifiers.
- Use CHECK for numeric/range/status constraints.
- CHECK does not replace NOT NULL.
- Use DEFAULT when appropriate.
- Index FK/search/date fields.

Constraint names should be descriptive, e.g. `fk_order_items_order_id`, `ck_products_price_non_negative`, `uq_users_email`.

## 9. Index Generation Policy
Suggest indexes for:
- Foreign keys.
- Lookup/search fields.
- Dates used for filtering.
- Status fields frequently filtered.
- Tenant scoping fields.
- Junction tables.
- Unique business identifiers.

Avoid over-indexing tiny lookup tables unless justified.

## 10. Naming Convention
Rules:
- Use `snake_case`.
- No spaces.
- Avoid reserved keywords.
- Use plural or consistent table naming; pick one convention per schema.
- Use descriptive constraint names.
- Avoid ambiguous abbreviations.

## 11. Dialect Mapping
PostgreSQL:
- Prefer `GENERATED`/identity or serial-equivalent based on chosen style.
- Use schemas/search_path for sandbox isolation.

MySQL:
- Use workspace database isolation.
- Block qualified names outside workspace database.
- Map CHECK support carefully by version.

SQLite:
- Use SQLite-compatible types and constraints.
- SQLite runner only for SQLite target.
- Do not validate PostgreSQL/MySQL DDL through SQLite.

## 12. Sample Data Policy
Rules:
- Sample data may be inserted in sandbox.
- Use fake data only.
- Do not include real secrets, PHI, card numbers, or credentials.
- Keep sample row counts modest.
- Sample data should satisfy constraints.

## 13. View and Procedure Policy
Views may be generated when they clarify common reporting use cases. Stored procedures/functions are optional and DBMS-specific; generate only when user asks or the domain strongly benefits. For v1.0.0, prefer portable tables/constraints/indexes over complex procedures.

## 14. When to Ask User
Ask clarification when:
- Target DBMS is unknown and dialect matters.
- Domain is ambiguous.
- Multi-tenant requirements are unclear.
- Sensitive/regulatory data is requested.
- Payment card/CVV storage is requested.
- Destructive action on connected database is requested.
- Required business process changes schema substantially.

## 15. Validation Checklist
Before execution:
- Domain detected or generic fallback justified.
- Major entities extracted.
- Relationships/cardinality identified.
- PK/FK/UNIQUE/CHECK/NOT NULL/DEFAULT considered.
- FK/search/date/tenant indexes considered.
- Names sanitized.
- SQL parsed with target dialect.
- Sandbox workspace selected for agent write/DDL.
- Schema read back and verification result generated.

## Implementation Notes
The design policy should be encoded into Create_database workflow and domain rule packs. Do not rely only on freeform LLM reasoning for constraints and safety-sensitive domain rules.

## Related Documents
- `07_DOMAIN_RULE_PACKS.md`
- `08_SKILLS_SPEC.md`
- `09_TOOLS_SPEC.md`
- `10_RUNTIME_AND_SANDBOX_SPEC.md`

## Addendum: Default Domain Decision

If the user asks Safy to create a database without specifying a domain, default domain is e-commerce. The agent must state the assumption:

```txt
User did not specify a domain. Safy assumes e-commerce as the default domain.
```

If critical information is missing beyond domain and safe assumptions are not possible, the agent asks follow-up questions.
