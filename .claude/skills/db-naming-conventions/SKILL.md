---
name: db-naming-conventions
description: Mandatory table-prefix naming rules for every database object (md_, txn_, map_, cfg_, log_, aud_, hist_, arc_, stg_, tmp_, dim_/fact_/agg_/rpt_, plus vw_, idx_, uq_, fk_ and similar). Use whenever creating, renaming or referencing tables, views, indexes, constraints, ORM models, SQLAlchemy `__tablename__`, Alembic migrations or raw SQL, and whenever proposing a schema.
---

# Database Table Naming Conventions

You are working on a project that follows a strict table-prefix convention. Apply these rules every time you create, rename or reference database tables, views, migrations, ORM models or SQL queries.

## 0. Precedence

1. If the existing schema already uses a different convention, follow the existing schema and flag the mismatch instead of silently mixing styles.
2. Otherwise, follow this document exactly.
3. If a table could fit more than one category, use the decision guide in section 4. If it is still ambiguous, ask before creating it.

## 1. General naming rules

- Use `snake_case`, lowercase only. No camelCase, no spaces, no hyphens.
- Use singular nouns for the entity part: `txn_order`, not `txn_orders`.
- Every table has exactly one prefix from section 2. Never stack prefixes (`md_cfg_x` is not allowed).
- Use one canonical prefix per category. Do not use the alternatives (`mst_`, `tr_`, `t_`, `ref_`, `lkp_` and so on).
- Keep names descriptive and unabbreviated unless the abbreviation is standard (`uom`, `gst`, `kyc`).
- Maximum name length: 63 characters (PostgreSQL limit).
- Primary key column: `id`.
- Foreign key column: `<referenced_entity>_id`, e.g. `customer_id`, `role_id`.
- Standard audit columns on every md_, txn_ and cfg_ table: `created_at`, `updated_at`, `created_by`, `updated_by`.
- Soft delete, where needed: `is_active` (md_ tables) or `deleted_at` (txn_ tables).

## 2. Prefixes

### 2.1 Core application tables

| Prefix | Category | Use for | Examples |
|---|---|---|---|
| `md_` | Master data | Reference and lookup data that changes rarely and is referenced by foreign keys. Includes users, roles, permissions, statuses and dropdown lists. | `md_user`, `md_role`, `md_permission`, `md_country`, `md_currency`, `md_lead_status`, `md_product_category` |
| `txn_` | Transaction data | Records created continuously by normal app usage. Grows without bound. | `txn_order`, `txn_invoice`, `txn_payment`, `txn_lead` |
| `map_` | Mapping table | Pure many-to-many join tables. Name as `map_<entity_a>_<entity_b>` in the direction of ownership. | `map_user_role`, `map_role_permission`, `map_product_tag` |
| `cfg_` | Configuration | Application settings, feature flags, templates and tunable rules. | `cfg_app_setting`, `cfg_email_template`, `cfg_feature_flag` |

### 2.2 Logging, history and lifecycle

| Prefix | Category | Use for | Examples |
|---|---|---|---|
| `log_` | Technical logs | System or request-level events, high volume, safe to purge. | `log_login`, `log_api_request`, `log_job_run` |
| `aud_` | Audit trail | Business-critical change records (who changed what, when). Never purge without a retention policy. | `aud_role_change`, `aud_order_change` |
| `hist_` | History | Previous versions of rows from another table. | `hist_product_price` |
| `arc_` | Archive | Old data moved out of live tables. Suffix with the period. | `arc_txn_order_2024` |
| `stg_` | Staging | Raw imported data before validation and cleaning. | `stg_bank_statement`, `stg_customer_import` |
| `tmp_` | Temporary | Short-lived working tables. Must be dropped after use. Never referenced by app code permanently. | `tmp_bulk_update` |

### 2.3 Reporting and analytics

| Prefix | Category | Use for | Examples |
|---|---|---|---|
| `dim_` | Dimension | Descriptive attributes in a warehouse model. | `dim_customer`, `dim_date` |
| `fact_` | Fact | Measurable events in a warehouse model. | `fact_sales` |
| `agg_` | Aggregate | Pre-computed summaries. | `agg_daily_revenue` |
| `rpt_` | Report | Tables built specifically to feed a report. | `rpt_monthly_gst` |

### 2.4 Non-table database objects

| Prefix | Object | Examples |
|---|---|---|
| `vw_` | View | `vw_active_customer` |
| `mv_` | Materialized view | `mv_sales_summary` |
| `fn_` | Function | `fn_calculate_tax` |
| `sp_` | Stored procedure | `sp_close_month` |
| `trg_` | Trigger | `trg_txn_order_updated_at` |
| `idx_` | Index | `idx_txn_order_customer_id` |
| `uq_` | Unique constraint | `uq_md_user_email` |
| `fk_` | Foreign key constraint | `fk_txn_order_customer_id` |
| `seq_` | Sequence | `seq_invoice_number` |

Index and constraint names follow the pattern `<prefix>_<table_name>_<column(s)>`.

## 3. Forbidden

- `bkp_`, `bak_`, `_old`, `_new`, `_copy`, `_v2` or date-suffixed copies of live tables in application schemas. Use migrations and proper backups instead.
- Tables with no prefix (other than framework-owned tables such as `alembic_version`, which must be left as is).
- Storing transaction data in an md_ table or configuration in an md_ table.
- Creating a new md_ table for a list that already exists under another name. Search the schema first.

## 4. Decision guide

Ask these questions in order and use the first prefix that matches:

1. Is it a view, function, procedure, trigger, index, constraint or sequence? Use section 2.4.
2. Does it only link two other tables (two foreign keys plus optional metadata)? `map_`
3. Is it raw incoming data awaiting validation? `stg_`
4. Is it scratch data that will be dropped? `tmp_`
5. Is it an older version of rows from another table? `hist_`
6. Is it data moved out of a live table for retention? `arc_`
7. Does it record who changed business data and when? `aud_`
8. Is it a technical or system event log? `log_`
9. Is it built only for analytics or reporting? `dim_`, `fact_`, `agg_` or `rpt_`
10. Is it an app setting, template or flag an admin tunes? `cfg_`
11. Is it created continuously by normal usage and grows over time? `txn_`
12. Otherwise, it is a stable entity or list referenced by other tables: `md_`

## 5. Reference example (RBAC and orders)

```
md_user                 -- application users
md_role                 -- admin, sales, accounts
md_permission           -- 'lead:read', 'quotation:approve'
map_user_role           -- user_id, role_id
map_role_permission     -- role_id, permission_id
md_customer
md_lead_status
txn_lead
txn_quotation
txn_order
txn_payment
aud_role_change
log_login
cfg_app_setting
vw_open_lead
```

## 6. Output requirements

- When you create a table, state its prefix category in the migration comment, e.g. `-- md_: master data`.
- When you propose a schema, list every table with its category before writing SQL or models.
- ORM model class names drop the prefix and use PascalCase singular (`txn_order` becomes `Order`, `map_user_role` becomes `UserRole`), while `__tablename__` keeps the full prefixed name.
