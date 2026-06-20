# Safy Domain Rule Packs

## Purpose
Define domain-specific schema rules used by Create_database and related schema-design workflows.

## Scope
Covers domain pack format and reviewed packs for e-commerce, clinic/appointment booking, inventory/warehouse, school/course enrollment, accounting/ledger, multi-tenant SaaS, blog/CMS, and generic domains.

## Source Reference
Source-of-truth: `SAFY_source.md`.

## 1. Overview
Domain rule packs provide implementation-ready modeling guidance. They do not override global security policy. When a pack requests a risky concept, global security policy wins.

## 2. Domain Pack Format
Each domain pack should include:
- When to use.
- Entities.
- Relationships.
- Mandatory rules.
- Constraints.
- Index suggestions.
- Security notes.
- Common mistakes.
- Questions to ask user.

## 3. E-commerce
When to use:
- Products, carts, orders, payments, shipping, customers, promotions.

Entities:
- customers/users
- products
- product_variants
- categories
- product_categories
- carts
- cart_items
- orders
- order_items
- payments
- shipments
- addresses
- coupons/discounts
- inventory_movements when inventory is in scope

Relationships:
- Customer has many orders.
- Order has many order_items.
- Product has many variants.
- Product/category is many-to-many.
- Payment belongs to order.
- Shipment belongs to order.

Mandatory rules:
- Order line items store price snapshot.
- Payment records use provider references/tokens, not raw card data.
- Order status lifecycle should be constrained.
- Quantity and price must be non-negative/positive as appropriate.

Constraints:
- UNIQUE SKU.
- CHECK quantity > 0 for line items.
- CHECK price >= 0.
- FK order_items -> orders/products/variants.

Index suggestions:
- FK columns.
- SKU/product name search.
- order date/status/customer.
- payment provider reference.

Security notes:
- No raw card number or CVV.
- Do not claim PCI compliance.

Common mistakes:
- Storing current product price only instead of order price snapshot.
- Missing line-item table.
- Storing card data.

Questions to ask user:
- Physical or digital goods?
- Inventory tracking needed?
- Multi-vendor/marketplace?
- Coupons/returns/refunds needed?

## 4. Clinic / Appointment Booking
When to use:
- Clinics, doctors, patients, appointment schedules, prescriptions, medical services.

Entities:
- patients
- providers/doctors
- clinics/locations
- services
- appointments
- appointment_status_history
- prescriptions
- medical_notes if requested
- rooms/resources
- schedules/availability

Relationships:
- Patient has many appointments.
- Provider has many appointments.
- Appointment belongs to service/location.
- Prescription belongs to patient/provider/appointment.

Mandatory rules:
- Appointment time cannot be invalid.
- Avoid double-booking provider/resource where modeled.
- Status lifecycle should be constrained.
- PHI-sensitive domain caveat required.

Constraints:
- FK appointments -> patients/providers/services.
- CHECK appointment_end > appointment_start.
- UNIQUE provider/time slot if exact slot model is used.

Index suggestions:
- appointment date/time.
- patient/provider FK.
- status.

Security notes:
- Contains PHI/PII-sensitive data.
- Do not claim HIPAA compliance.
- Suggest audit/access logs for production designs.

Common mistakes:
- No status lifecycle.
- No schedule/resource model.
- Compliance claims.

Questions:
- Single clinic or multiple locations?
- Need recurring appointments?
- Need prescriptions/medical records?

## 5. Inventory / Warehouse
When to use:
- Stock, warehouses, suppliers, movements, purchase orders, shipments.

Entities:
- products/items
- warehouses
- locations/bins
- stock_balances
- stock_movements
- suppliers
- purchase_orders
- purchase_order_items
- adjustments
- transfers

Relationships:
- Product has stock in many warehouses/locations.
- Stock movements affect product/location.
- Purchase order has line items.

Mandatory rules:
- Prefer append-only stock movements.
- Direct stock quantity edits should be modeled as adjustment records.
- Quantity cannot be negative unless domain explicitly allows backorder.

Constraints:
- FK movement -> product/location.
- CHECK movement quantity != 0.
- UNIQUE product/location balance row.

Index suggestions:
- product_id, warehouse_id, location_id.
- movement timestamp.
- supplier and PO status.

Security notes:
- Audit stock adjustments.

Common mistakes:
- Only storing current quantity with no movement history.
- No warehouse/location granularity.

Questions:
- Need serial/lot tracking?
- Allow negative stock?
- Need transfers between warehouses?

## 6. School / Course Enrollment
When to use:
- Students, teachers, courses, classes, enrollment, grades.

Entities:
- students
- instructors
- courses
- terms/semesters
- course_sections/classes
- enrollments
- grades
- departments
- rooms/schedules

Relationships:
- Course has many sections.
- Student enrolls in many sections through enrollments.
- Instructor teaches sections.

Mandatory rules:
- Enrollment is junction between student and section.
- Unique student/section enrollment.
- Grade/status lifecycle constrained.
- Capacity rules when requested.

Constraints:
- FK enrollments -> students/sections.
- UNIQUE student_id + section_id.
- CHECK capacity >= 0.

Index suggestions:
- student_id, section_id, instructor_id.
- term/status.

Security notes:
- Student data may be sensitive; do not claim regulatory compliance.

Common mistakes:
- Direct many columns for course1/course2 instead of enrollment table.
- Missing term/section distinction.

Questions:
- Need grading?
- Need attendance?
- Need prerequisites/capacity/waitlist?

## 7. Accounting / Ledger
When to use:
- Chart of accounts, journal entries, ledger, invoices, payments, financial postings.

Entities:
- accounts
- journal_entries
- journal_entry_lines
- fiscal_periods
- customers/vendors if needed
- invoices/payments if requested
- reversal_entries

Relationships:
- Journal entry has many lines.
- Line references account.
- Entry belongs to fiscal period.

Mandatory rules:
- Journal entry must balance debit = credit.
- Posted entries are immutable.
- Corrections use reversal entries.
- Fiscal period lock.
- High-risk domain.

Constraints:
- CHECK debit >= 0 and credit >= 0.
- CHECK not both debit and credit positive on same line if chosen model requires it.
- FK lines -> journal_entries/accounts.

Index suggestions:
- account_id.
- entry date.
- fiscal period.
- posting status.

Security notes:
- Financial domain needs audit and permission design.
- Do not claim compliance.

Common mistakes:
- No line table.
- Allow updating posted entries.
- No balance validation.

Questions:
- Single currency or multi-currency?
- Need fiscal periods?
- Need invoices/payments integration?

## 8. Multi-tenant SaaS
When to use:
- Organizations, tenants, users, memberships, roles, subscriptions, plans, usage.

Entities:
- tenants/organizations
- users
- memberships
- roles
- permissions
- subscriptions
- plans
- invoices
- usage_events
- audit_logs
- api_keys
- invitations

Relationships:
- User belongs to tenant through membership.
- Membership has role.
- Tenant has subscription.
- Plan has subscriptions.

Mandatory rules:
- Tenant-owned tables include `tenant_id`.
- Unique constraints scoped by tenant where appropriate.
- Tenant-aware indexes.
- Safy v1.0.0 runtime remains single-user local.
- RLS is apply-later for PostgreSQL production designs.

Constraints:
- FK tenant-owned tables -> tenants.
- UNIQUE tenant_id + business identifier.

Index suggestions:
- tenant_id prefix where common.
- membership user/tenant.
- subscription status/date.

Security notes:
- Generated schema can be multi-tenant; Safy itself is not multi-user SaaS runtime.

Common mistakes:
- Global uniqueness where tenant-scoped uniqueness is required.
- Missing tenant_id on tenant-owned tables.

Questions:
- Single org per user or multiple?
- Role model complexity?
- Billing/subscription needed?

## 9. Blog / CMS
When to use:
- Posts, pages, tags, comments, media, revisions, redirects.

Entities:
- users/authors
- posts
- pages
- categories
- tags
- post_tags
- comments
- media_assets
- revisions
- settings
- redirects

Relationships:
- Author has many posts/pages.
- Posts have many tags through post_tags.
- Comments belong to post and maybe parent comment.

Mandatory rules:
- Slug uniqueness by site/type/scope.
- Publish/moderation status lifecycle.
- Tags/categories through junction tables.
- Revisions table if versioning is needed.
- Avoid WordPress meta-table pattern unless flexibility is explicitly needed.

Constraints:
- UNIQUE slug by scope.
- FK post_tags -> posts/tags.
- CHECK status in allowed states.

Index suggestions:
- slug.
- published_at.
- author_id.
- status.
- full-text index can be suggested per DBMS.

Security notes:
- Generated CMS content is untrusted; frontend must escape or sanitize rendered HTML/Markdown.

Common mistakes:
- No revisions/moderation.
- Rendering raw HTML without sanitization.

Questions:
- Need pages as separate entity from posts?
- Need comments/moderation?
- Need multi-site support?

## 10. Generic Domain
When no reviewed pack fits, use generic relational modeling:
- Identify major nouns/entities.
- Identify transactions and line items.
- Identify relationships and cardinalities.
- Generate PK/FK/UNIQUE/CHECK/INDEX rules.
- Ask for clarification if domain-specific safety matters.

## 11. Cross-domain Patterns
Patterns:
- Status lifecycle uses constrained status fields plus optional history table.
- Transaction header/details uses line items.
- Many-to-many uses junction table.
- Audit log table suggested for high-risk domains.
- Tenant isolation uses `tenant_id` and scoped unique constraints.
- Sensitive data requires caveat and no compliance claims.

## Implementation Notes
Represent packs as structured data plus narrative guidance. The Create_database skill should load pack rules before generating schema.

## Related Documents
- `06_DATABASE_DESIGN_POLICY.md`
- `08_SKILLS_SPEC.md`
- `05_SECURITY_POLICY.md`
