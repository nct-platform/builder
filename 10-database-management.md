# 10 — Database Management plugin & `project-db.dump`

## What it is / when to use

This document is about the **project's business DB schema** — where the tables physically live that are later
managed by dynamic-CRUD sources (see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)).

Two artifacts:

1. **`project-db.dump`** — a JSON file inside `.mrjun` (format `nct-jdbc-dump-v1`). This is a **full logical
   dump** of all schemas of the project database: tables (as `CREATE TABLE` DDL + the data rows themselves), sequences, foreign
   keys, unique/check constraints, indexes, enum types, views, functions, triggers. On `.mrjun` import
   this file is exactly what **recreates the schema and loads the data** into the project DB.
2. **`database.management.plugin`** — a Wicket authoring plugin (the "Database" page in the admin scaffold). In
   the browser it provides a visual ERD + dialogs *Create Schema / Create Table / Add Column / Create Constraint /
   Create Index / Create Trigger*. It **does not store the schema itself** — it executes DDL directly against the project DB via
   `ProjectDatabaseService`, and the plugin node in the content tree only carries the ERD canvas state (table positions,
   zoom). The schema makes it into the export from the **live DB**, not from the node.

**When to use this document:** when you construct `project-db.dump` by hand so that Step-2 Claude
assembles the business schema (whatever you name it — `app_schema`, `finance_schema`, `customs_schema`, …)
before dynamic-CRUDs are attached to it. Everything
needed to recreate the tables is here; logic (CRUD methods, SQL/Groovy) is in
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md); sources/queries are in
[12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).

**DYNAMIC vs STATIC (see [00-export-format-and-import.md](00-export-format-and-import.md)):** in the **dynamic**
style the business tables live in a project schema inside `project-db.dump`, and dynamic-CRUDs
point to it via `sourceSchema`. In the **static** style the business logic is compiled Java `@Crud`
beans in a separate microservice, and `project-db.dump` contains only the platform `int_*`/`rimm_*` schemas (without
a business schema). That is why **business tables are constructed only in the dynamic style** — as a schema in the dump.

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `db list-schemas`, `db list-tables [--schema <s>]`, **`db show <table> [--schema <s>]`** (columns + PK +
> CHECK/UNIQUE/FK — the constraints `list-tables` hides), `db add-schema <name>`, `db add-table --schema <s> --name <t> --column name:type[:pk][:notnull]...`
>
> ⚠️ **`db add-table` is a skeleton generator — it does NOT emit a working PK, sequences, or precise types**
> (`_build_ddl`/`_parse_column`, `db_cmds.py`). `id:serial:pk` → `"id" integer NOT NULL, PRIMARY KEY("id")`
> with **no `DEFAULT nextval` and no sequence object**; `id:uuid:pk` → `"id" uuid NOT NULL` with **no
> `gen_random_uuid()`**. It hardcodes **`VARCHAR(255)`** for `varchar`/`string` (no `length` support). So after
> `db add-table` you MUST hand-edit `ddl` to add either `DEFAULT nextval('<schema>.<t>_id_seq'::regclass)` **plus** a
> `sequences[]` entry (`lastValue ≥ max id`), OR decide app-set-uuid (leave bare, as ERP does) vs
> `DEFAULT gen_random_uuid()`; hand-fix VARCHAR lengths. See "Two entity styles" and "db add-table" gotchas below.
>
> ⚠️ **When wiring dynamic CRUDs over these tables, the constraints are the contract, not decoration.**
> `checkConstraints[]` (a status/enum column's allowed value set), NOT NULL + `%_not_null` checks, `uniqueConstraints[]`,
> and audit columns (`creation_time`/`modification_time`) all constrain what a `create`/`update`/lifecycle method may
> write. A method that ignores them passes an empty-table smoke test and throws on the first real row. See
> [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) and `mrjun.py validate`/`crud verify --db`.
> Full index and rules — [`tools/README.md`](tools/README.md); before reimport — `mrjun.py validate`.

> **One DBMS — PostgreSQL only.** The entire DB layer supports a single engine. The enum `DbType`
> (`nct-transfer/.../dto/DbType.java`) has **exactly one value**, and it is literally spelled with a typo
> `POISTGRESQL` (`id="postgresql_database"`, `urlOf → jdbc:postgresql://host:port/db`). Every source object
> in `rep-objects.json.sources[]` therefore carries `"dbType":"POISTGRESQL"`. The MySQL/Oracle/SQLServer/Snowflake
> support that older platform documentation promises does not exist here; when building a source by hand write
> `"dbType":"POISTGRESQL"`
> verbatim (see [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)).

---

## Export shape — `project-db.dump`

Format string: `"nct-jdbc-dump-v1"`. Assembled in `ProjectDatabaseServiceImpl`:

```json
{
  "format": "nct-jdbc-dump-v1",
  "database": "prj_<realm>_<client>",
  "schemas": [ { "name": "...", "enumTypes": [...], "foreignKeys": [...], "uniqueConstraints": [...],
                 "checkConstraints": [...], "indexes": [...], "tables": [...], "sequences": [...],
                 "views": [...], "functions": [...], "triggers": [...] }, ... ]
}
```

**Top level** (insertion order into `dump`, `LinkedHashMap`):

| Key | Type | Value |
|---|---|---|
| `format` | string | always `"nct-jdbc-dump-v1"` |
| `database` | string | name of the physical project DB (`prj_<realm>_<client>`); matches `project-db-meta.json.databaseName` and `dynamic-cruds.json.cruds[].sourceDb` |
| `schemas` | array | array of schema objects (order: as the catalog returned them) |

**Schema object** — 11 keys. `schemaDump` is also a `LinkedHashMap`, so the **key order in JSON =
the `put(...)` order**, which is as follows (verify on any dump with
`jq -r '.schemas[0]|keys_unsorted'`): `name` → `enumTypes` → `foreignKeys` → `uniqueConstraints` →
`checkConstraints` → `indexes` → `tables` → `sequences` → `views` →
`functions` → `triggers`. A typical business schema populates `tables`, `sequences`, `foreignKeys`
and `indexes`, and leaves the rest (enum/unique/check/views/functions/triggers) as empty arrays — but **all 11 keys
are always emitted**, so emit them all when building by hand.

| Key | Type | What |
|---|---|---|
| `name` | string | schema name (e.g. `app_schema`) |
| `enumTypes` | array | `[{name, labels:[...]}]` — Postgres `CREATE TYPE ... AS ENUM` |
| `foreignKeys` | array of **strings** | ready-to-run `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY (...) REFERENCES ...` DDL |
| `uniqueConstraints` | array of **strings** | `ALTER TABLE ... ADD CONSTRAINT ... UNIQUE (...)` DDL |
| `checkConstraints` | array of **strings** | `ALTER TABLE ... ADD CONSTRAINT ... CHECK (...)` DDL (except `%_not_null`) |
| `indexes` | array of **strings** | `CREATE INDEX ...` (pg `indexdef`, without PK and unique-constraint indexes) |
| `tables` | array | tables in **dependency order** (those without FK dependencies first) — see below |
| `sequences` | array | `[{name, dataType, startValue, increment, lastValue}]` |
| `views` | array | `[{name, definition}]` |
| `functions` | array | `[{name, definition}]` (pg `pg_get_functiondef`, kind f/p) |
| `triggers` | array of **strings** | pg `pg_get_triggerdef` DDL |

> ⚠️ **Key format fact:** `foreignKeys`, `uniqueConstraints`, `checkConstraints`, `indexes`, `triggers`
> are **lists of ready-to-run SQL strings** (DDL), NOT structured objects `{column, references, ...}`. On
> restore they are simply run through `Statement.execute(...)` with savepoint-per-statement. `tables` also
> carry a ready-to-run `CREATE TABLE` DDL in the `ddl` field. Structured ones are only `enumTypes`, `sequences`, `views`,
> `functions`. That is, **columns/types/nullable/default/pk are encoded as text inside `ddl`, not as separate
> fields**. (The SPEC draft is imprecise: the real table shape is `ddl`+`columns`+`columnTypes`+`rows`, not
> `columns:[{name,type,nullable,default,pk}]`.)

A dump of a dynamic project typically lists these schema families (`jq -r '.schemas[].name'`): the **business**
schema (whatever you named it — `app_schema`, `billing_schema`, `customs_schema`, …); one
`int_<realm>_<client>_<hash>` schema per dynamic-integration; `public` (empty); `rimm_<realm>_<client>` (lookup /
RIMM data); and `system_<realm>_<client>` (platform bookkeeping). Only the business schema is yours to design —
the rest are created by the platform.

> ⚠️ **The schema's NAME decides whether it survives import — name your business schema plainly.** Before
> restoring, the platform builds a schema remap and **skips** (maps to null) `public`, and **every schema whose
> name starts with `int_` or `system_`** unless it is the target project's own `system_<realm>_<client>`; it
> assumes those describe the *donor's* pods and liquibase history. `rimm_*` is remapped to the target's
> `rimm_<realm>_<client>`. Everything else is restored under its own name. The skip is **silent** — it is logged
> on the server, the import still reports success, and the only symptom is empty screens.
> So name the business schema you author `app_schema` / `finance_schema` / `customs_schema` / … — **never
> `int_*`, `system_*` or `public`**. A dump you inherited whose business tables already sit in an
> `int_<realm>_<client>_<hash>` schema must be **renamed** before it is re-imported (see
> §"Adding an entity to a FILLED dump"). Note the asymmetry: such a dump is still a perfectly valid *description*
> of a live database — the CRUDs work against the running project they were exported from — it just cannot be
> imported back.

---

## Two entity styles (MATCH the sibling already in the dump)

Business tables in a dump follow one of **two conventions**. Before you add a table, `db show` a sibling in the
same schema and **copy its style** — do not mix.

**A. Dimension / sequence style** (a hand-designed business schema, e.g. `app_schema`): **integer PK
backed by a sequence** (`"id" smallint NOT NULL DEFAULT nextval('<schema>.<t>_id_seq'::regclass)` + a
`sequences[]` entry), status/lookup via **dimension-FK** (`status_id → dim_invoice_status`), localization column spelled
**`localized`** (WITH 'd', on every table in the schema). No audit/company columns.

**B. Hibernate / entity style** (a schema generated by a JPA-backed service, e.g. `int_<realm>_<client>_<hash>`;
**no sequences at all**): **uuid PK with NO default** — `"id" uuid NOT NULL` — the app sets the uuid before INSERT (Hibernate
`@Id`), so there is nothing to `nextval`. Every table carries the same audit/tenant preamble
`creation_time`/`modification_time` (`timestamp with time zone NOT NULL`), `custom_fields jsonb`, `localize jsonb`
(**WITHOUT 'd'**), plus `created_by`/`modified_by` (`VARCHAR(100)`) and `company_id uuid NOT NULL` on the main entities;
status is a `VARCHAR` column with a **CHECK** allowed-value set, not an FK.

> **Note — spelling differs by style.** The localization jsonb column is `localized` in style A and `localize`
> (no 'd') in style B. Keep whichever the sibling uses verbatim; both are deliberate.

**Decision rule:** match the sibling. New table next to `dim_*` lookups → style A (int+sequence+FK-status+`localized`).
New table next to entity tables with a `creation_time`/`company_id` preamble → style B (uuid app-set PK, audit preamble,
`custom_fields`, `localize`, `company_id`, status CHECK).

A style-B table (inspect one with `db show <table> --schema <s>`):

```json
{
  "name": "bill_of_materials",
  "ddl": "CREATE TABLE \"int_acme_erp_47b963f7\".\"bill_of_materials\" (\n  \"id\" uuid NOT NULL,\n  \"creation_time\" timestamp with time zone NOT NULL,\n  \"custom_fields\" jsonb,\n  \"modification_time\" timestamp with time zone NOT NULL,\n  \"localize\" jsonb,\n  \"base_quantity\" NUMERIC(18,4) NOT NULL,\n  \"bom_number\" VARCHAR(50) NOT NULL,\n  \"component_groups\" jsonb,\n  \"created_by\" VARCHAR(100),\n  \"status\" VARCHAR(30) NOT NULL,\n  \"version\" integer NOT NULL,\n  \"bom_type_id\" uuid NOT NULL,\n  \"company_id\" uuid NOT NULL,\n  \"product_id\" uuid NOT NULL,\n  \"uom_id\" uuid NOT NULL,\n  PRIMARY KEY (\"id\")\n)",
  "columnTypes": [1111, 93, 1111, 93, 1111, 2, 12, 1111, 12, 12, 4, 1111, 1111, 1111, 1111]
}
```

(DDL abridged — such a table usually has more optional columns; the annotation columns above are the point.) Note:
`id uuid` has **no `DEFAULT`** (app-set), `creation_time`/`modification_time` are `timestamp with time zone NOT NULL`,
`custom_fields`+`localize` are jsonb, `company_id uuid NOT NULL`, `status VARCHAR(30) NOT NULL` — and its allowed set
is a separate CHECK in `checkConstraints[]`:

```json
"CHECK (((status)::text = ANY (ARRAY[('DRAFT'::character varying)::text, ('ACTIVE'::character varying)::text, ('HOLD'::character varying)::text, ('OBSOLETE'::character varying)::text])))"
```

plus `UNIQUE ("company_id", "product_id", "version")` and FKs `product_id→product`, `company_id→company`,
`bom_type_id→lookup_bom_type`, `uom_id→unit_of_measure` — all in the schema's `checkConstraints`/`uniqueConstraints`/
`foreignKeys` string lists, NOT inside `ddl`. `columnTypes` shows `uuid` and `jsonb` are **both** `1111`, and
`timestamp with time zone` is `93`.

---

## Table — full example + annotation

A style-A lookup table (`dim_invoice_status` in a business schema named `app_schema` — the domain here is
finance, but the shape is the same for a customs `dim_declaration_status` or an ERP `dim_order_status`):

```json
{
  "name": "dim_invoice_status",
  "ddl": "CREATE TABLE \"app_schema\".\"dim_invoice_status\" (\n  \"id\" smallint NOT NULL DEFAULT nextval('app_schema.dim_invoice_status_id_seq'::regclass),\n  \"code\" VARCHAR(30),\n  \"label\" VARCHAR(60),\n  \"sort_order\" smallint DEFAULT 0,\n  \"is_active\" boolean DEFAULT true,\n  \"localized\" jsonb,\n  PRIMARY KEY (\"id\")\n)",
  "columns": ["id", "code", "label", "sort_order", "is_active", "localized"],
  "columnTypes": [5, 12, 12, 5, -7, 1111],
  "rows": [
    { "id": "1", "code": "draft", "label": "Draft", "sort_order": "1", "is_active": "true", "localized": null },
    { "id": "5", "code": "aaa", "label": null, "sort_order": null, "is_active": null, "localized": "{\"code\": {\"en_US\": \"aaa\"}}" }
  ],
  "rowCount": 5
}
```

| Field | Type | Value | Required |
|---|---|---|---|
| `name` | string | table name (without schema) | yes |
| `ddl` | string | **full `CREATE TABLE "schema"."name" (...)`** — the only source of column structure; generated by `generateCreateTableDdl` | yes |
| `columns` | array of string | column names in `ordinal_position` order (from `ResultSetMetaData.getColumnLabel`) | yes |
| `columnTypes` | array of int | JDBC type codes (`java.sql.Types`) parallel to `columns` — needed on INSERT for `ps.setNull/setObject` | yes |
| `rows` | array of object | data: **all values are strings** (`val.toString()`, `null` for NULL), key = column name | yes (may be `[]`) |
| `rowCount` | int | `rows.size()` (for reference) | yes |

### `ddl` — how to read the column format

`generateCreateTableDdl` builds the string from the template:

```
CREATE TABLE "<schema>"."<table>" (
  "<col>" <TYPE> [NOT NULL] [DEFAULT <expr>],
  ...,
  PRIMARY KEY ("<pkcol>", ...)
)
```

Type rules:

* `character varying` → `VARCHAR(<n>)` (or `VARCHAR` without length)
* `character` → `CHAR(<n>)`
* `numeric` → `NUMERIC(<prec>,<scale>)` / `NUMERIC(<prec>)` / `NUMERIC`
* `USER-DEFINED` (enum type) → `"<udt_name>"` (pg type name in quotes)
* `ARRAY` → `<elemtype>[]`
* everything else (`integer`, `smallint`, `boolean`, `text`, `date`, `jsonb`, `timestamp with time zone`, …) → as-is from `data_type`
* `NOT NULL` is added if `is_nullable = 'NO'`
* `DEFAULT <column_default>` verbatim (e.g. `nextval('app_schema.invoices_id_seq1'::regclass)`, `0`, `true`)
* `PRIMARY KEY (...)` — from the PK constraint at the end

### `columnTypes` — the JDBC codes you will actually meet

(From `ResultSetMetaData.getColumnType()`, i.e. `java.sql.Types`.) A style-A schema typically uses
`[-7, 1, 2, 4, 5, 12, 91, 93, 1111]`; a style-B (uuid/Hibernate) schema
`[-7, 2, 4, 8, 12, 91, 93, 1111]`. Codes marked *tooling* below are what `db add-table`'s `TYPE_MAP`
(`tools/mrjunkit/db_cmds.py`) can emit but that rarely appear in a real dump.

| Code | `java.sql.Types` | Postgres type |
|---|---|---|
| `-7` | `BIT` | `boolean` |
| `2` | `NUMERIC` | `numeric` (incl. `NUMERIC(p,s)`) |
| `4` | `INTEGER` | `integer` |
| `5` | `SMALLINT` | `smallint` |
| `8` | `DOUBLE` | `double precision` (`TYPE_MAP` maps `double`/`float`→8) |
| `12` | `VARCHAR` | `character varying` (VARCHAR(n)) **and** `text` (`db add-table` emits 12 for `text`) |
| `-5` | `BIGINT` | `bigint` — *tooling*: `TYPE_MAP` emits −5 for `bigint`/`bigserial`; rare in a real dump |
| `91` | `DATE` | `date` |
| `93` | `TIMESTAMP` | `timestamp` / **`timestamp with time zone`** / `timestamp without time zone` (the driver returns all as TIMESTAMP) |
| `1111` | `OTHER` | **`jsonb` AND `uuid`** (both map to 1111; incl. the `localized`/`localize` field and every style-B `uuid` PK/FK) |
| `1` | `CHAR` | `character` (CHAR(n)) |

> When building a dump by hand: `columnTypes` must be **in the same order** as `columns`. If you do not know the code
> exactly — INSERT still goes through `ps.setObject(idx, val, sqlType)` (`setTypedParameter`),
> and Postgres casts the string. Values in `rows` are **always strings** (even numbers/boolean/json). `null` is encoded
> as JSON `null`.

---

## Sequence — full example + annotation

In style A there is one sequence per auto-generated integer id. Example (an `invoices` table in a finance schema):

```json
{
  "name": "invoices_id_seq",
  "dataType": "integer",
  "startValue": "1",
  "increment": "1",
  "lastValue": 7
}
```

| Field | Type | Value | Required |
|---|---|---|---|
| `name` | string | sequence name (usually `<table>_<col>_seq`, referenced by `DEFAULT nextval(...)` in `ddl`) | yes |
| `dataType` | string | `bigint` / `integer` / `smallint` (from `information_schema.sequences.data_type`) | yes |
| `startValue` | string | `START WITH` | yes |
| `increment` | string | `INCREMENT BY` | yes |
| `lastValue` | number | current `last_value` — on restore `setval('<schema>.<seq>', lastValue, true)` is called | yes |

> **Restore:** first `CREATE SEQUENCE IF NOT EXISTS <schema>.<seq>` (without
> START/INCREMENT — minimal), then, AFTER the tables and data, `setval(..., lastValue, true)`. That is, `dataType`
> / `startValue` / `increment` from the dump are **effectively not applied to the sequence DDL on restore** — only
> `name` matters (so that `nextval` in `ddl` resolves) and `lastValue` (so that the next id does not collide with the
> loaded rows). Keep `lastValue` ≥ the maximum `id` in `rows`.

---

## Foreign keys — full example + annotation

`foreignKeys` — an array of DDL strings, one per constraint, for the whole schema. A finance schema's list:

```json
[
  "ALTER TABLE \"app_schema\".\"invoices\" ADD CONSTRAINT \"invoices_counterparty_id_fkey\" FOREIGN KEY (\"counterparty_id\") REFERENCES \"app_schema\".\"counterparties\"(\"id\")",
  "ALTER TABLE \"app_schema\".\"invoices\" ADD CONSTRAINT \"invoices_status_id_fkey\" FOREIGN KEY (\"status_id\") REFERENCES \"app_schema\".\"dim_invoice_status\"(\"id\")",
  "ALTER TABLE \"app_schema\".\"invoice_lines\" ADD CONSTRAINT \"fk_invoice_lines_invoice\" FOREIGN KEY (\"invoice_id\") REFERENCES \"app_schema\".\"invoices\"(\"id\")",
  "ALTER TABLE \"app_schema\".\"invoice_lines\" ADD CONSTRAINT \"fk_invoice_lines_product\" FOREIGN KEY (\"product_id\") REFERENCES \"app_schema\".\"products\"(\"id\")",
  "ALTER TABLE \"app_schema\".\"payments\" ADD CONSTRAINT \"payments_invoice_id_fkey\" FOREIGN KEY (\"invoice_id\") REFERENCES \"app_schema\".\"invoices\"(\"id\")",
  "ALTER TABLE \"app_schema\".\"payments\" ADD CONSTRAINT \"fk_payments_method\" FOREIGN KEY (\"method_id\") REFERENCES \"app_schema\".\"dim_payment_method\"(\"id\")"
]
```

String format (the serializer's template):

```
ALTER TABLE "<schema>"."<child>" ADD CONSTRAINT "<name>" FOREIGN KEY ("<col>") REFERENCES "<schema>"."<parent>"("<refcol>")
```

* The FK constraint name is arbitrary; two conventions coexist in practice — `<child>_<col>_fkey`
  (the Postgres auto-name) and `fk_<child>_<parent>` (a name typed in the dialog).
* **Single-column only.** The FK query joins `information_schema.key_column_usage` ×
  `constraint_column_usage` **without aligning on `ordinal_position`**. For a single-column FK this is one row
  → one correct `ALTER`. For a **composite** FK this join produces a **Cartesian product** of pairs
  (col × refcol), and each pair is emitted as a separate single-column `ALTER` → N×M
  incorrect strings. ⚠️ So never rely on a round-trip for a composite FK: write it by hand as
  **one** string `FOREIGN KEY ("a","b") REFERENCES t("x","y")` (see Gotcha #8).
* FKs **do not set `ON DELETE/UPDATE`** — they are not in the dump.
* Restored last, after all tables+data, savepoint-per-statement — a "bad" FK is
  skipped, the schema does not collapse.

---

## Unique / Check constraints — examples

DDL strings. A hand-built business schema often leaves both lists empty; JPA-generated (style B) schemas are full of them.

**Unique** — from a `uniqueConstraints` list. ⚠️ Note the pattern below: on one table there are **two**
strings with the same `UNIQUE(realm_name, client_name, alias)` — the JPA auto-name (`uks…`) and the
human-defined one (`uq_…`):

```json
"ALTER TABLE \"int_acme_app_a9d543ee\".\"dynamic_crud\" ADD CONSTRAINT \"uks44g9kbyp2p10kmfdembdccq5\" UNIQUE (\"realm_name\", \"client_name\", \"alias\")",
"ALTER TABLE \"int_acme_app_a9d543ee\".\"dynamic_crud\" ADD CONSTRAINT \"uq_dynamic_crud_realm_client_alias\" UNIQUE (\"realm_name\", \"client_name\", \"alias\")"
```

(The duplicate `UNIQUE` does not break restore — the second `ALTER` simply fails in its own savepoint with a WARN. When building
by hand write one.)

**Check** — a `checkConstraints` entry. Note the shape: a status column's allowed set is enumerated **verbatim**,
one `::character varying` cast per value (here, 9 ticket statuses of a service-desk domain):

```json
"ALTER TABLE \"int_acme_svc_cbe6c1cf\".\"ticket\" ADD CONSTRAINT \"ticket_status_check\" CHECK (((status)::text = ANY (ARRAY[('NEW'::character varying)::text, ('PENDING_DIAGNOSTICS'::character varying)::text, ('ASSIGNED'::character varying)::text, ('UNDER_REVIEW'::character varying)::text, ('IN_PROGRESS'::character varying)::text, ('RESOLVED'::character varying)::text, ('READY_FOR_DISPATCH'::character varying)::text, ('DELIVERED'::character varying)::text, ('CLOSED'::character varying)::text])))"
```

Templates: UNIQUE `ALTER TABLE ... ADD CONSTRAINT ... UNIQUE (col, ...)`; CHECK
`ALTER TABLE ... ADD CONSTRAINT ... CHECK (<clause>)`. CHECK constraints with the `_not_null` suffix
are excluded from the dump — NOT NULL is already encoded in `ddl`. Do not duplicate them as `checkConstraints`.

---

## Index — example

`indexes` — an array of pg `indexdef` strings. Two hand-added indexes on a child table:

```json
[
  "CREATE INDEX idx_audit_log_document_id ON app_schema.audit_log USING btree (document_id)",
  "CREATE INDEX idx_audit_log_user_id ON app_schema.audit_log USING btree (user_id)"
]
```

PK indexes and indexes backing UNIQUE constraints **do not** make it into this list (filter 2400) — they are already
covered by `PRIMARY KEY (...)` in `ddl` and by the `uniqueConstraints` strings.

> ⚠️ **The exclusion subquery is schema-wide, not table-correlated.** The filter is
> `indexname NOT IN (SELECT constraint_name FROM information_schema.table_constraints WHERE table_schema = ?)` — the
> subquery is **uncorrelated to the index's own table**. So a plain (non-constraint) index whose name coincidentally
> equals a constraint name on **another** table in the same schema is silently dropped from the dump. Same serializer
> family as the composite-FK Cartesian bug (Gotcha #8); an edge case, but if a hand-built dump is missing an index that
> clearly exists, check for a name clash with a constraint elsewhere in the schema — and add the `CREATE INDEX` string
> to `indexes[]` by hand.

---

## enumTypes / views / functions / triggers — shape

These four lists are **empty in the overwhelming majority of schemas** (⚠️ **no live example observed** — the format
below is taken strictly from the serializer/restore code, so treat it as unverified).

### `enumTypes`

```json
{ "name": "task_priority_enum", "labels": ["LOW", "MEDIUM", "HIGH"] }
```

* `name` — the pg type name; `labels` — the ordered list of labels.
* Restore: `CREATE TYPE "<schema>"."<name>" AS ENUM ('LOW', 'MEDIUM', 'HIGH')`, **before** the tables,
  so that `USER-DEFINED` columns (in `ddl` — `"<name>"`) resolve.
* Such enum types are produced through the ENUM_REF flow of the dialogs (see "ENUM_REF" below): when adding a STRING-enum
  column the repository service does `CREATE TYPE … AS ENUM(...)` in the same transaction as the ALTER TABLE.

> **Write-side binding of a pg_enum column — no manual `::type` cast needed.** A dynamic CRUD's `create`/`update`
> over a `USER-DEFINED` (pg_enum) column binds a plain `:status`: the executor resolves the column's enum type from
> `ParameterMetaData`, falling back to `information_schema.columns.udt_name`
> (`DynamicMethodExecutor.lookupTargetTableColumnTypes`), and binds the value through a `PGobject` tagged with that
> type name (`bindAs` default branch, `DynamicMethodExecutor.java`), so Postgres applies the enum's input
> function. You do **not** hand-write `:status::task_priority_enum` in the SQL method. A `::<enum_type>` cast becomes
> necessary **only** for a non-canonical write whose single target table the executor cannot parse (a multi-table write
> / `INSERT … SELECT`): there the slot falls back to its declared parameter type, an enum column bound as `character
> varying` throws `column "status" is of type … but expression is of type character varying`, and the cast (or a param
> name that matches the column) fixes it. ⚠️ This rule is derived from the executor code, not from an observed dump — a schema built the way this
document recommends (dimension tables instead of pg enums) never hits it.
> [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) §Gotchas /
> [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §1.

### `views`

```json
{ "name": "v_open_invoices", "definition": "SELECT ... FROM app_schema.invoices WHERE ..." }
```

Restore: `CREATE OR REPLACE VIEW "<schema>"."<name>" AS <definition>`, with schema remapping if
the target ≠ source.

### `functions`

```json
{ "name": "trg_set_updated_at", "definition": "CREATE OR REPLACE FUNCTION ... $$ ... $$" }
```

`definition` — the full `pg_get_functiondef` (already `CREATE OR REPLACE FUNCTION`), executed as-is.

### `triggers`

An array of strings — the full `pg_get_triggerdef`:

```json
"CREATE TRIGGER set_updated BEFORE UPDATE ON app_schema.invoices FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at()"
```

Executed as-is, savepoint-per-statement.

---

## The plugin — `database.management.plugin`

### Content-tree node (ERD canvas, not schema)

The page node in `properties.model.stringValue` stores **only the ERD canvas state**
(`DatabaseManagementPluginModel`):

```json
{ "selectedSchemaId": "rimm_acme_demo", "selectedTableId": "rimm_brand", "zoomLevel": 0.5,
  "tablePositions": { "rimm_brand": {"x":30,"y":30}, "users": {"x":734,"y":25} },
  "scrollX": 0, "scrollY": 0 }
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `selectedSchemaId` | string | null | last schema selected in the UI |
| `selectedTableId` | string | null | last table selected |
| `zoomLevel` | double | `1.0` | ERD zoom (0.5–2.0) |
| `tablePositions` | map `{tableId: {x,y}}` | `{}` | table positions on the canvas |
| `scrollX` / `scrollY` | int | `0` | canvas scroll |

> **Important for construction:** this node **does not describe the schema**. When building by hand you can leave it as in
> the `empty` scaffold (or with an empty `tablePositions`) — it does not affect DB restore. The real schema
> comes **only** from `project-db.dump`. About the `model` property slot (not `settings`) on plugin nodes —
> see [01-content-model-and-pages.md](01-content-model-and-pages.md).

### What the dialogs do (to understand how the schema was authored)

The plugin dialogs execute DDL immediately via `ProjectDatabaseService` (Feign → **nct-query** /
`DatabaseController` — `ProjectDatabaseClient` (Feign → **nct-query**),
`/api/database/tenant/{realm}/{client}`), rather than writing to the export. The export is produced later by dumping the live DB. Still, their
behavior is the "source of truth" about how a particular `ddl` came to be:

* **Create Schema** (`CreateSchemaDialog`): internal mode → `createSchema({schemaName})` +
  `syncSources()` — creates a new schema in the project DB AND registers a `SourceEntity` with shared
  project credentials (`sourceType=INTERNAL`). The schema name is validated by `^[a-z][a-z0-9_]*$`. External mode
  creates an external `SourceDto` (`sourceType=EXTERNAL`, not a schema in the dump).
  → **This is exactly the mechanism by which a business schema + its associated source appear** (see the relationship below).
* **Create/Edit Table** (`CreateTableDialog`): assembles a `List<DbColumn>` + `primaryKeyColumns` into a
  `DatabaseCreateTableRequest`, sends `createTable(...)`; for columns with `uniqueConstraint=true`
  additionally `addConstraint(... "UNIQUE" ...)`. The table name is validated by `^[a-z][a-z0-9_]*$`.
  The default starting column of a new dialog is `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
* **Add Column** (`AddColumnDialog`) → `addColumn(...)`; **Create Constraint** (`CreateConstraintDialog`) →
  `addConstraint(...)` with `constraintType ∈ {UNIQUE, CHECK, FOREIGN KEY}`, for FK — `refTable`/`refColumns`;
  **Create Index** (`CreateIndexDialog`) → `createIndex(...)`, `method ∈ {btree, hash, gin, gist, brin}`,
  the `unique` flag; **Create Trigger** (`CreateTriggerDialog`) assembles
  `CREATE TRIGGER <name> <timing> <events> ON <schema>.<table> <FOR EACH ROW|STATEMENT> EXECUTE FUNCTION <fn>`
  and sends `createTrigger({triggerDdl})`.

---

## Column types (`ColumnType`)

`ColumnType` (`ColumnType.java`) — the list of Postgres types offered in the dialogs. `editableTypes()`
 excludes `SERIAL`/`BIGSERIAL` (deprecated — use INTEGER/BIGINT + IDENTITY instead). `sqlType` — the string
that goes into the DDL:

`VARCHAR, CHAR, TEXT, SMALLINT, INTEGER, BIGINT, SERIAL, BIGSERIAL, NUMERIC, REAL, DOUBLE PRECISION, BOOLEAN,
DATE, TIME, TIMESTAMP, TIMESTAMPTZ, INTERVAL, JSON, JSONB, UUID, BYTEA, INET, CIDR, MACADDR, TSVECTOR, TSQUERY,
POINT, LINE, POLYGON, BOX, CIRCLE, XML, VECTOR` (pgvector), and the virtual `ENUM_REF`.

**`ENUM_REF`** — not a real type: in the dialog it opens a sub-form for selecting a registered
project Enumeration. `resolveSqlType` turns it into `<schema>.<pg_type_name>` (for STRING-encoded
enums) or the literal `INTEGER` (for INTEGER-encoded ones); `resolveSqlType` itself does **not**
emit a CHECK constraint — the accompanying CHECK for INTEGER-encoded enums is added later during the create-flow, not by this method. ⚠️ `resolveSqlType` is defined in
`nct-ui/.../database/dialog/CreateTableDialog.java` (not in `ColumnType.java`). The corresponding DTO field is
`DbColumn.enumValues` (`List<String>`); the repository service does `CREATE TYPE … AS ENUM` in the same transaction
as the ALTER. See [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) about project Enumerations.

### Server-side type dictionary (RIMM `SqlTypeMapper`)

For RIMM tables (lookup data, `rimm_` prefix) input types are normalized by `nct-rimm/.../util/SqlTypeMapper.java`
(`toPostgresType`/`isValidType`, case-insensitive); this is the authoritative dictionary of allowed type strings:

| Input | Postgres |
|---|---|
| `VARCHAR` / `STRING` / `TEXT` | `VARCHAR(n)` if length>0 else `TEXT` |
| `INTEGER` / `INT` | `INTEGER` |
| `BIGINT` / `LONG` | `BIGINT` |
| `SMALLINT` / `SHORT` | `SMALLINT` |
| `DECIMAL` / `NUMERIC` | `DECIMAL(precision,scale)` / `DECIMAL(precision)` / `DECIMAL` |
| `FLOAT` / `REAL` | `REAL` |
| `DOUBLE` | `DOUBLE PRECISION` |
| `BOOLEAN` / `BOOL` | `BOOLEAN` |
| `DATE` | `DATE` |
| `TIME` | `TIME` |
| `TIMESTAMP` / `DATETIME` | `TIMESTAMP` |
| `TIMESTAMPTZ` / `TIMESTAMP_WITH_TIMEZONE` | `TIMESTAMPTZ` |
| `UUID` | `UUID` |
| `JSON` | `JSON` |
| `JSONB` | `JSONB` |
| `BYTEA` / `BINARY` / `BLOB` | `BYTEA` |
| everything else | used as-is (custom types) |

---

## Auto-generation (`AutoGenerationMode`)

`AutoGenerationMode` (`AutoGenerationMode.java`) — how a column gets its default value. The `name()`
string is sent as `autoGenMode` and matched against `ColumnAutoGenSqlBuilder.MODE_*` on the server.

| Mode | applicableTypes | SQL fragment that goes into `ddl` |
|---|---|---|
| `NONE` | all | — (the manual `defaultValue` is used, if set) |
| `IDENTITY_BY_DEFAULT` | SMALLINT/INTEGER/BIGINT(/SERIAL/BIGSERIAL) | ` GENERATED BY DEFAULT AS IDENTITY` |
| `IDENTITY_ALWAYS` | same | ` GENERATED ALWAYS AS IDENTITY` |
| `SEQUENCE_NEXTVAL` | same | ` DEFAULT nextval('<schema>.<seq>'::regclass)` + `CREATE SEQUENCE IF NOT EXISTS ...` before the column |
| `UUID_RANDOM` | UUID | ` DEFAULT gen_random_uuid()` |
| `CURRENT_TIMESTAMP` | TIMESTAMP/TIMESTAMPTZ/DATE/TIME | ` DEFAULT now()` |
| `CUSTOM_EXPRESSION` | all | ` DEFAULT <your expression>` |

`suggestedDefault`: UUID → `UUID_RANDOM`; integer PK → `IDENTITY_BY_DEFAULT`; otherwise `NONE`.

**`DbColumn` (`nct-transfer/.../dto/ddl/DbColumn.java`)** — the full set of column fields the dialogs send to
the server (none of this makes it into the dump as separate fields — everything is "baked" into `ddl`):

```
name, type, length, precision, scale, nullable, defaultValue,
autoGenMode,                                        // one of 7 AutoGenerationMode values
sequenceName, sequenceCreate, sequenceStart, sequenceIncrement,
sequenceMinValue, sequenceMaxValue, sequenceCache, sequenceCycle,   // SEQUENCE_NEXTVAL parameters
enumValues                                          // List<String> for ENUM_REF (type = schema.typename)
```

`AutoGenerationOptionsPanel` (`Options` in `AutoGenerationOptionsPanel.java`) — a reusable panel
providing a mode dropdown + all `sequence*` parameters.

> **In the export dump** the auto-generation mode is **not stored as a field** — it is already "baked" into the `DEFAULT`
> part of the `ddl` string (e.g. `nextval(...)`, `gen_random_uuid()`) and into the sequences list. Reverse detection of the mode
> when **editing** an existing column is done not by parsing the DEFAULT string, but from the **already server-computed**
> `autoGenMode` (from `listColumns`) via
> `AutoGenerationOptionsPanel.Options.fromListColumns(autoGenMode, sequenceName, columnDefault)`
> (`AutoGenerationOptionsPanel.java`; called in `EditColumnDialog.java`). `fromListColumns` only
> runs `AutoGenerationMode.fromString(autoGenMode)` and special-cases `SEQUENCE_NEXTVAL`
> (`sequenceCreate=false`) and `CUSTOM_EXPRESSION` (`customExpression=columnDefault`). The client does **not** parse
> `nextval(`/`gen_random_uuid()`/`now()` from the DEFAULT string.

---

## How the business schema relates to dynamic-CRUD (the most important link)

The business schema from `project-db.dump` is what the dynamic-CRUDs look at. The relationship goes through **three fields** that
must match:

1. `project-db.dump.database` == `dynamic-cruds.json.cruds[].sourceDb`
   (`prj_<realm>_<client>`).
2. `project-db.dump.schemas[].name` == `dynamic-cruds.json.cruds[].sourceSchema` — most CRUDs point at the
   business schema; the lookup/reference ones point at `rimm_<realm>_<client>`.
3. Each schema is registered as a **Source** (the `sourceIdentifier` in the CRUD references an object from
   `rep-objects.json.sources`; `sourceType=INTERNAL`). A CRUD over the business schema:

```json
{ "alias": "equipment_event_types_cruid", "sourceIdentifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c",
  "sourceSchema": "app_schema", "sourceDb": "prj_<realm>_<client>",
  "sourceHost": "<db-host>", "sourcePort": 5432, "sourceUser": "prj_<realm>_<client>_user" }
```

It is exactly **Create Schema (internal)** that does both things at once: `createSchema` creates the schema in the dumped DB, and
`syncSources` sets up a `SourceEntity` with project credentials (`CreateSchemaDialog`). So when building
a project by hand: **the schema tables go in `project-db.dump`; the schema's source object goes in `rep-objects.json.sources`;
the CRUDs go in `dynamic-cruds.json`** (see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) and
[12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)).

> **Import-time source materialization.** `project-db-meta.json` = `{"databaseName":"prj_<realm>_<client>",
> "rimmSourceIdentifier":"<uuid>"}` — `databaseName` duplicates `project-db.dump.database`; `rimmSourceIdentifier`
> points to the rimm source. At the same time `rep-objects.json.sources` is often **empty**, even though
> queries/CRUDs reference `sourceIdentifier`s: the missing INTERNAL/RIMM source records are materialized on
> import (`create-schema-sync`). A hand-built business schema normally carries exactly **one** explicit entry in
> `sources[]` — the INTERNAL source pointing at it. Details of the
> source object and its recreation on import are in
> [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).

> **Dynamic-CRUD ↔ auto-generated queries.** Each SQL method of a CRUD produces a row in `rep-objects.json.queries`
> named `crud_<alias>_<method>` — so a dynamic project's query count is roughly *CRUDs × SQL methods* (hundreds),
> while a static project has only a handful. The schema from
> `project-db.dump` is what the SQL of these queries runs against. The query↔CRUD relationship — see
> [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) and
> [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).

---

## How to construct from scratch — a new business schema in `project-db.dump`

Goal (worked here in a **customs** domain — substitute your own): add a schema `customs_schema` with a lookup
table and a related business table — so that after import the DB contains tables + data, ready for dynamic-CRUD.

### Step 0 — starting point

Take the `project-db.dump` of the empty baseline. There `schemas` contains `public`, `rimm_<realm>_<client>`,
`system_<realm>_<client>` (all empty). **Add a new schema object** to the `schemas` array (or rename
one of the empty ones). Leave `database` as in the target project.

### Step 1 — schema skeleton

Keep the key order the serializer emits:

```json
{
  "name": "customs_schema",
  "enumTypes": [],
  "foreignKeys": [],
  "uniqueConstraints": [],
  "checkConstraints": [],
  "indexes": [],
  "tables": [],
  "sequences": [],
  "views": [],
  "functions": [],
  "triggers": []
}
```

(JSON parsers do not require order, but keep it so your dump diffs cleanly against a serializer-produced one.)

### Step 2 — sequence for auto-id

One sequence per auto-id. Name = `<table>_id_seq`, `lastValue` ≥ max id in the data:

```json
{ "name": "dim_declaration_status_id_seq", "dataType": "smallint", "startValue": "1", "increment": "1", "lastValue": 5 }
```

Add one for `declarations` (`declarations_id_seq`, integer) and so on.

### Step 3 — lookup table (dimension)

```json
{
  "name": "dim_declaration_status",
  "ddl": "CREATE TABLE \"customs_schema\".\"dim_declaration_status\" (\n  \"id\" smallint NOT NULL DEFAULT nextval('customs_schema.dim_declaration_status_id_seq'::regclass),\n  \"code\" VARCHAR(30),\n  \"label\" VARCHAR(60),\n  \"sort_order\" smallint DEFAULT 0,\n  \"is_active\" boolean DEFAULT true,\n  \"localized\" jsonb,\n  PRIMARY KEY (\"id\")\n)",
  "columns": ["id", "code", "label", "sort_order", "is_active", "localized"],
  "columnTypes": [5, 12, 12, 5, -7, 1111],
  "rows": [
    { "id": "1", "code": "draft", "label": "Draft", "sort_order": "1", "is_active": "true", "localized": null },
    { "id": "2", "code": "lodged", "label": "Lodged", "sort_order": "2", "is_active": "true", "localized": null }
  ],
  "rowCount": 2
}
```

Rules:
* `ddl` — schema and names in double quotes; VARCHAR type with `(n)`; `NOT NULL DEFAULT nextval(...)` for id;
  `PRIMARY KEY ("id")` at the end. `\n` — real line breaks inside the JSON string.
* `columns` **strictly** matches the order of columns in `ddl`.
* `columnTypes` parallel to `columns` (see the JDBC-code table). `jsonb` = `1111`, `boolean` = `-7`,
  `VARCHAR` = `12`, `smallint` = `5`, `integer` = `4`, `numeric` = `2`, `date` = `91`, `timestamp` = `93`.
* Each `localized jsonb` column is a platform convention for localization (value is either `null` or
  a string of the form `"{\"code\": {\"en_US\": \"aaa\"}}"`).
* All values in `rows` are **strings** (id `"1"`, boolean `"true"`, number `"1"`); NULL → JSON `null`.

### Step 4 — child table with FK

Table `declarations` references `dim_declaration_status`:

```json
{
  "name": "declarations",
  "ddl": "CREATE TABLE \"customs_schema\".\"declarations\" (\n  \"id\" integer NOT NULL DEFAULT nextval('customs_schema.declarations_id_seq'::regclass),\n  \"reference_no\" VARCHAR(120),\n  \"status_id\" smallint,\n  \"description\" text,\n  \"is_active\" boolean DEFAULT true,\n  \"localized\" jsonb,\n  PRIMARY KEY (\"id\")\n)",
  "columns": ["id", "reference_no", "status_id", "description", "is_active", "localized"],
  "columnTypes": [4, 12, 5, 12, -7, 1111],
  "rows": [],
  "rowCount": 0
}
```

The **FK string** (in the schema's `foreignKeys`) — as a separate `ALTER TABLE`:

```json
"ALTER TABLE \"customs_schema\".\"declarations\" ADD CONSTRAINT \"declarations_status_id_fkey\" FOREIGN KEY (\"status_id\") REFERENCES \"customs_schema\".\"dim_declaration_status\"(\"id\")"
```

### Step 5 — table order

Stack `tables` **in dependency order**: first the tables without FK (the `dim_*` lookups), then the referencing ones
(`declarations`, and anything referencing *those*). The dumper does this via `getTablesInDependencyOrder`; when building
by hand keep the order yourself, so that `CREATE TABLE` does not fail on a non-existent reference (although FKs are attached
later — 2713 — so this is critical only for DEFAULT/types, not for FK).

### Step 6 — indexes (optional)

```json
"CREATE INDEX idx_declarations_status ON customs_schema.declarations USING btree (status_id)"
```

into the `indexes` array.

### Step 7 — attach source + CRUD

The schema by itself is useless without a source and CRUDs. Add:
* `sources` in `rep-objects.json` (a source pointing to `customs_schema`, `dbType="POISTGRESQL"`,
  `sourceType="INTERNAL"`) — see
  [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md);
* CRUDs in `dynamic-cruds.json` with `sourceSchema: "customs_schema"`, `sourceDb: "<database>"`,
  `sourceIdentifier: "<source uuid>"` + their SQL queries `crud_<alias>_<method>` in `rep-objects.json.queries` —
  see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

### Restore result

Provided the schema is not skipped by the name rule above (`public`, `int_*`, `system_*`), on `.mrjun` import
`restoreSingleSchema` does the following in order for this schema:
`CREATE SCHEMA IF NOT EXISTS` → enum types → `CREATE SEQUENCE IF NOT EXISTS` (one at a time) → `CREATE TABLE` (from
`ddl`) → INSERT of the data (in batches of 500, `ps.setObject(..., sqlType)`) → `setval` for sequences → unique →
check → FK → indexes → views → functions → triggers. Each statement in its own savepoint — one error does not collapse
the rest of the schema (it is only logged as `WARN`).

---

## Adding an entity to a FILLED dump (MODIFY scenario)

When the target is a **working dynamic `.mrjun`** (scenario C in [19-build-decision-procedure.md](19-build-decision-procedure.md)),
you do NOT build a schema from scratch — you extend the one that is already there. Entity-specific loop:

0. **Check the schema NAME first — `db list-schemas`.** If the CRUDs' `sourceSchema` is an `int_*` or `system_*`
   name, the whole schema is **skipped on the next import** (§"Export shape") and everything you add to it is
   thrown away silently. Rename it *everywhere* before you extend it: the dump's `schemas[].name`, every
   `tables[].ddl`, every FK / index / CHECK / UNIQUE / sequence string that carries the qualifier,
   `rep-objects.json.sources[].schemaName`, and `dynamic-cruds.json.cruds[].sourceSchema` (plus any schema-qualified
   table name inside a `methods[].script` or a saved query). Then re-run `validate`.
1. **Learn the style — `db show <sibling> --schema <s>`** on an existing table in the target schema (§"Two entity
   styles"). This tells you: int+sequence vs app-set uuid PK, `localized` vs `localize`, whether there is an audit
   preamble (`creation_time`/`modification_time`/`created_by`/`modified_by`) and `custom_fields`/`company_id`, and
   whether status is an FK (style A) or a CHECK column (style B).
2. **Skip `db add-schema`** — the schema exists. `db add-table --schema <s> --name <t> --column …` to seed the skeleton.
3. **Hand-fix the `ddl`** to the sibling's style: for style A add `DEFAULT nextval('<s>.<t>_id_seq'::regclass)` + a
   `sequences[]` entry (`lastValue ≥ max id`); for style B leave `id uuid NOT NULL` bare and prepend the audit/tenant
   preamble columns; add `custom_fields jsonb`, the correctly-spelled `localize`/`localized jsonb`, `company_id uuid`.
   Fix any `VARCHAR(255)` lengths.
4. **Add constraints as strings** to the schema's `foreignKeys[]` / `checkConstraints[]` (status allowed-set) /
   `uniqueConstraints[]` — they live in those lists, not in `ddl`.
5. **Verify — `mrjun.py validate`** (cross-file refs) **then `crud verify --db`** (fires the real NOT NULL + CHECK + FK
   contract). `validate` DOES catch a `DEFAULT nextval(...)` with no `sequences[]` entry and a `columns`/`columnTypes`
   length mismatch; it will NOT catch a `lastValue` below the max id, a `VARCHAR` too short for its data, or a bad
   CHECK — see Gotcha 14.

The full delta loop (rep-objects/CRUD/page wiring around the new table) lives in
[19-build-decision-procedure.md](19-build-decision-procedure.md); this section is only the `project-db.dump` part.

---

## Deleting a row — decide SOFT or HARD per entity, before you write the schema

A `DELETE` against a row something still references does not fail gracefully, it fails in the user's
face:

```
ERROR: update or delete on table "supplier" violates foreign key constraint "fk_item_supplier_id"
       on table "item"
DETAIL: Key (id)=(600442af-…) is still referenced from table "item".
```

And the case that "works" is often worse: a `DELETE` that Postgres happily performs on a row nothing
points at can still destroy the only explanation of a past decision — the ledger line that makes the
stock balance, the parameter version that justifies an old reorder point, the configuration band a
two-year-old order was sized against.

So the delete strategy is a **per-entity decision made at schema time**, and the FK graph is the
starting point, not the answer:

| The entity is… | Decision | Because |
|---|---|---|
| referenced by any FK | **SOFT** | a physical delete cannot succeed while any child exists, and forbidding the delete outright just moves the dead end to the user |
| an audit/ledger/history row (movements, runs, effective-dated versions, claims) | **SOFT** | nothing points at it, so Postgres would drop it — but a derived quantity computed as a *residual* silently changes, and evidence disappears |
| configuration referenced by CODE rather than by FK (bands, tariffs, categories) | **SOFT** | there is no constraint to protect it, and deleting it makes every historical document that stored the code unexplainable |
| a document LINE, owned by its header | **HARD** | `update` rewrites the lines wholesale (`deleteLines` + re-insert), so a marker would accumulate dead rows forever and collide with the `(header, line_number)` uniqueness the rewrite depends on. Lines are only reachable through their header, so a soft-deleted header hides them anyway |
| genuinely standalone and disposable | **HARD** | say so explicitly — the point is that it was decided, not that nobody thought about it |

**Write the decision down in the schema spec**, as a named set next to the tables. A reviewer must be
able to see *which* entities were judged and *why* without re-deriving the FK graph.

### The marker

`deleted boolean NOT NULL DEFAULT false`. Not a value inside the business `status` column: `status` is
a lifecycle with its own CHECK vocabulary, and overloading it corrupts every filter, chart, predicate
and printout that reads it. A separate boolean also matches the platform's own convention for its
entities (`AbstractSecuredEntity.deleted`, repositories filtering `…AndDeletedFalse`).

Three things follow, and all three are easy to forget:

1. **Every UNIQUE becomes partial.** A plain `UNIQUE (code)` keeps a deleted row's key reserved
   forever — retire `SUP-002` and that code can never be used again, which is not what the user means
   by "deleted". Postgres cannot make a table CONSTRAINT partial, so it becomes an index and moves
   from `uniqueConstraints` to `indexes` in the dump:

   ```sql
   CREATE UNIQUE INDEX "idx_supplier_code" ON "rop_schema"."supplier" ("code") WHERE (deleted = false)
   ```

2. **Index the marker.** Every read now filters on it and the engine scans whole tables.

3. **Every seeded row must carry `false`.** The column is NOT NULL and the seeders will not mention
   it; a NULL there makes the restore skip the WHOLE table with nothing louder than
   `Skipping data load for table …`, and the project imports "successfully" with one empty screen.
   Default it in one place in the dump writer, not in each seeder.

### Where the filter goes — and where it must NOT

This is the part that gets it wrong. The rule is **filter the row you are LISTING, not the row you are
DESCRIBING it with**:

* a CRUD's own `findAll` / `count` / `get` filter their own table (`AND t.deleted = false`);
* a **JOIN to a parent is left alone** — a goods receipt whose supplier was retired must stay
  readable, or retiring one supplier erases years of history from every document that mentions it;
* a **candidate scan is the exception**: when a query joins several tables to pick what to *act on*
  (the engine deciding which items to reorder, and for which supplier), every table in it is a live
  candidate and every one of them is filtered;
* a **dashboard/analytics query filters everything**, including the dimension it joins for a label. A
  dashboard reports on the business as it stands. Use the subquery form
  `FROM (SELECT * FROM {S}.<t> WHERE deleted = false) <alias>` rather than appending `AND …`: these
  queries have UNIONs, GROUP BYs and optional parameter predicates, and there is no single safe place
  to append a clause in all of them;
* a **document's `delete` must NOT clear its lines when the header is soft** — the header is only
  marked, so removing the lines leaves a restorable document with nothing in it.

### The marker is not a business field

Keep `deleted` out of `dtoFields` and out of the create/update write set. Otherwise "Generate fields"
puts a *Deleted* checkbox on every form and a user who ticks it has silently performed a delete. Exactly
one method writes it.

### A soft delete you cannot reverse is just a delete with extra steps

Generate an `undelete` method (`UPDATE … SET deleted = false … RETURNING *`) alongside `delete`. It
needs no UI action — it exists so a rule, or an operator through the Run dialog, can bring a row back
without hand-writing SQL against the project database.

`mrjun.py validate` checks the mechanical half of all this: a table with inbound FKs whose `delete`
method physically deletes, a soft table whose reads do not filter, a soft table with a non-partial
UNIQUE, and the marker leaking into `dtoFields`.

## Seeding demo-grade data into the dump

`project-db.dump` is the **only** data the export carries. Restore's second pass INSERTs exactly what stands in
`tables[].rows` — nothing on the import path generates, derives or re-bases a business row (`restoreSingleSchema`,
second pass 2642–2684; every value is bound as the string you wrote, `setTypedParameter` 2896). Every table, form,
worklist and chart in the delivered project is therefore judged on the rows you type here — a perfect build with a
one-row-per-table dump demos as an empty product.

### ⛔ Before the first row: every cell is a STRING

`the string you wrote` above is literal. The restore reads the rows as `List<Map<String, String>>` and assigns
each cell to a `String val` before binding it — so a JSON number or boolean throws
`class java.lang.Integer cannot be cast to class java.lang.String` at that assignment. It is a
`ClassCastException`, not a `SQLException`, so it escapes the per-table savepoint that exists to contain a bad
table and **rolls the entire schema back**: "The database was NOT replaced. Schema(s) [x] were rolled back."
The rest of the import succeeds, so the project arrives complete and completely empty.

```python
from mrjunkit import db_cmds

table["rows"] = db_cmds.normalise_rows(colnames, rows)   # str-ifies every cell, keys aligned to columns
```

| you have | you write | not |
|---|---|---|
| `1` (integer column) | `"1"` | `1` |
| `True` (boolean column) | `"true"` | `true` |
| `Decimal("1200.00")` (numeric) | `"1200.00"` | `1200.00` |
| `{"label": {...}}` (jsonb) | `"{\"label\": {...}}"` — the JSON **as a string** | the object |
| SQL `NULL` | `null` | `""` |

The typing is `columnTypes`' job: the parameter is bound as `Types.INTEGER`, so the driver converts `"1"` for
you. `columnTypes[]` itself and `sequences[].lastValue` go the other way — they are read as `Number` and must
stay unquoted.

A dump the platform exported can never show this (it writes `val.toString()` per cell), which also means **no
reference export teaches it by example** — and Python-side checks are blind to it, because `json.load` makes
`1` and `"1"` behave alike in every offline gate you write. `mrjun.py validate` catches it; run it before
`pack`, always.

### Story fixture vs demo-grade population

|  | **Story fixture** | **Demo-grade population** |
|---|---|---|
| Shape | one row per lookup value, one of each entity, one happy path end to end | tens–hundreds of fact rows spread across every axis a screen groups, filters or charts by |
| Proves | the **wiring**: the FK resolves, the CRUD reads, the form saves, the workflow starts | the **product**: a list that pages, a filter that discriminates, a chart with a shape |
| Costs | minutes | a generator script (below) |

Build **both, in that order** — the fixture is not a draft of the population, it is the part of it you can verify.
Keep the fixture rows as the **verifiable spine** (the records a walkthrough opens by number and an offline check
counts) and grow the population *around* them: append, never renumber, retype or restate a spine row.

> ⚠️ A dump you inherit as a baseline is almost always a story fixture: the `dim_*` lookups populated and the fact
> tables at 0–3 rows. Copy such a dump's *shape*, never its volume.

### Volume and shape — targets per USE, not per table

Size the data by what consumes it, not by the table it sits in. Sixty rows across five statuses and fourteen months
is a good demo table; five hundred rows that are all the same status is not.

| What consumes the rows | Minimum that *works* | What a demo needs |
|---|---|---|
| Categorical chart (count/sum by `<axis>`) | 1 row per category | **4–7 categories, ≥3 rows each, deliberately UNEQUAL** — equal bars read as fabricated |
| Trend / time series | 2 points | **≥12 contiguous buckets** (12–18 months, or 8–12 weeks) with visible movement; a hole only where the hole is the point |
| Dropdown / filter over a column | 1 distinct value | **≥4 distinct values with ≥2 rows behind each**, and at least one value that does *not* select everything — a filter whose every choice returns the same list is worse than no filter |
| CRUD table page | 1 row | **more than `rowsPerPage`** (default **15**, [04-crud-table-plugin.md](04-crud-table-plugin.md)) so paging, sorting and search are exercised on more than one page |
| Master → detail | 1 child | **3–8 children on most masters, 0 on one** (proves the empty state) and one master with an outsized child count |
| Worklist / queue page | 1 open item | **enough open items to fill the first page**, across more than one state and more than one owner bucket |
| KPI tile / single number | any | a value that is neither 0/1 nor suspiciously round |

The chart side of the same question — how many buckets a query must return, label cardinality, what makes a series
render flat — is [22-charts-params-and-filters.md](22-charts-params-and-filters.md) §2.6 "The data a chart needs
(demo-grade datasets)". Size the dump against that section for every chart the case ships.

### Outcome MIX — seed the failures on purpose

A generator left to itself writes the happy path, and a happy-path-only dump quietly claims a system in which
nothing ever goes wrong: the worklist has nothing to work, the "overdue" filter returns nothing, and the semantic
traffic-light palettes ([22-charts-params-and-filters.md](22-charts-params-and-filters.md) §6.1) have nothing to
colour — every slice comes out the same hue.

**Rule: every value of every vocabulary a screen groups, colours or filters by must occur in the fact rows.** That
means the whole allowed set of a status CHECK (`db show <table> --schema <s>` prints it) and every active row of a
`dim_*` lookup that a FK points at. A vocabulary value with zero rows behind it is a legend entry that never
appears, a filter choice that returns an empty list, and a colour nobody ever sees.

A workable default distribution for a status-like axis:

| Bucket | Share | Why it must exist |
|---|---|---|
| completed / normal | 50–65% | the baseline the eye compares everything else against |
| in flight / pending / awaiting | 15–25% | proves the worklist has work in it |
| adverse — rejected, failed, overdue, blocked, breached | 10–20% | the only rows that exercise the warning/danger colours and the exception screens |
| edge rows | 2–5 rows | a null optional field, a very long text value, a zero/negative amount, a very old record — proves the UI does not break on them |

Check the mix straight out of the dump, offline, no live DB needed:

```bash
jq -r '.schemas[]|select(.name=="<schema>").tables[]|select(.name=="<entity>").rows[]."<status-col>"' \
  project-db.dump | sort | uniq -c | sort -rn
```

Compare the output against the CHECK allowed set / the lookup's rows. `8 ACTIVE` under a four-value CHECK is the
failure this check exists to catch; seed the three missing values before you go further.

### Frozen time — a dump's dates are absolute

Restore binds each date/timestamp string verbatim; there is no re-basing, no "days ago" expression and no
post-import job that moves business dates. But queries are written relative — the chart-query idiom is
`WHERE <date-col> >= NOW() - INTERVAL '6 months'` ([22-charts-params-and-filters.md](22-charts-params-and-filters.md)
§1.2). So **a seeded window decays**: rows drop out of it every day after the build, and a row that reads "due
today" is due today only on the build date.

1. **Write the build date down** — in the case notes (`mrjun.py case add`), as the anchor every seeded date was
   computed from. Whoever revives the project a year later needs it to re-spread the data.
2. **Spread history backwards, generously.** Distribute the historical population over **12–18 months back** from
   the build date, not over the last 30 days. A 12-month trend keeps its shape for a year; a 30-day trend is empty
   in six weeks.
3. **Widen the window in the query rather than crowding the data into it** — and better, take the clock out of it
   altogether: anchor to the DATA (`>= (SELECT max(<date-col>) FROM …) - INTERVAL '12 months'`), which never
   decays ([22-charts-params-and-filters.md](22-charts-params-and-filters.md) §2.6 Rule 5). Where a `NOW()` window
   stays, prefer `INTERVAL '12 months'` over `INTERVAL '7 days'`. A screen that is genuinely about "this week"
   should say so through a param the viewer can change
   ([22-charts-params-and-filters.md](22-charts-params-and-filters.md) §3), not through a hardcoded 7-day window
   that silently empties.
4. **"Today" rows are perishable — keep them few, and make the semantics survive.** Anything that must read as
   *current* is true only on the build date. Seed a handful, and derive due-date semantics from a **spread** of
   future dates (say build date +1…+180 days): that still yields both "overdue" and "due soon" rows months later,
   whereas a block of rows all due on the build date turns uniformly overdue the next day. Keep future dates inside
   a horizon the domain can justify.
5. **Format:** values are strings — `YYYY-MM-DD` for `date` (91) and `YYYY-MM-DD HH:MM:SS` (optionally with an
   offset) for `timestamp` / `timestamp with time zone` (93). Copy the exact spelling a sibling row in the same
   dump already uses; the string is handed to Postgres to cast.

**Before shipping, and again whenever a build comes off the shelf:** for every screen with a relative window, count
the rows that window would select *today*. If a chart or a worklist would render empty, widen the window or
re-spread the data. It surfaces in the live drive ([26-orchestration-and-testing.md](26-orchestration-and-testing.md)
§5), but it is cheap enough to catch offline first, with the `jq` count above.

### Generating rows in bulk — constraint discipline

1. **Every row object carries a key for every name in `columns`.** Restore reads `row.get(columns[i])`; a missing
   key is **not** an error — it binds NULL (2665–2669), and against a NOT NULL column that NULL costs you the whole
   table (below).
2. **CHECK vocabularies verbatim.** Copy the allowed values out of `checkConstraints[]` character for character —
   they are compared as text and are case-sensitive.
3. **FK values must exist in the parent's `rows`.** Emit parents before children and draw the child's FK values from
   the parent ids you actually wrote.
4. **UNIQUE stays unique across the generated population** — document numbers, codes and the composite natural keys
   the schema declares (`db show` prints them).
5. **Ids: append, never renumber.** Continue from `max(existing id) + 1`, then raise the sequence's `lastValue` to
   the new maximum (Gotcha 4) — a stale `lastValue` makes the first *runtime* INSERT collide with a seeded row.
6. **Keep `rowCount` in sync** with `len(rows)`. Restore ignores it, but `db show` prints it (`db_cmds.py`), so a
   stale count lies to the next agent reading the dump.
7. **Document numbering sequential and human-plausible** — `<PFX>-<year>-00042`, ascending with the record's own
   date, no gaps that read as deletions. No `Test 1`, `aaa` or lorem ipsum anywhere a user can see: visible
   placeholder text discredits a demo faster than a missing feature.
8. **Plausible magnitudes and variety** in names, amounts, quantities and dates. Forty records named `<Entity> 1`…
   `<Entity> 40`, or every amount equal to `100.00`, read as a fixture rather than as a system.

Generate with the toolkit's own loader so the dump keeps its formatting (real exports are minified — `_detect_indent`,
`core.py`); there is no `db add-row` command, rows are yours to write:

```python
# seed.py — bulk-append demo rows to ONE table of an unpacked export.
#   run from the export dir:   PYTHONPATH=<library>/tools python3 seed.py
import datetime, random
from mrjunkit import core

BUILD_DATE = datetime.date(2026, 1, 15)        # write this into the case notes; every date below anchors to it
SCHEMA, TABLE = "<schema>", "<entity>"
STATUS  = ["<V1>", "<V2>", "<V3>", "<V4>"]     # VERBATIM from the CHECK — `db show <entity> --schema <schema>`
WEIGHTS = [0.55, 0.20, 0.15, 0.10]             # the outcome mix — the adverse value is NOT optional
PARENT_IDS = ["1", "2", "3", "4", "5"]         # ids that actually exist in the parent table's rows

p = core.Project(".")
sch = next(s for s in p.db["schemas"] if s["name"] == SCHEMA)
tbl = next(t for t in sch["tables"] if t["name"] == TABLE)
next_id = max((int(r["id"]) for r in tbl["rows"]), default=0) + 1   # APPEND — never renumber the spine

for i in range(120):
    d = BUILD_DATE - datetime.timedelta(days=random.randint(0, 540))          # ~18 months of history
    vals = {
        "id":          str(next_id + i),
        "doc_no":      "<PFX>-%d-%05d" % (d.year, next_id + i),
        "<parent>_id": random.choice(PARENT_IDS),
        "status":      random.choices(STATUS, WEIGHTS)[0],
        "amount":      "%.2f" % round(random.uniform(120, 9800), 2),
        "created_at":  "%s 09:%02d:00" % (d.isoformat(), random.randint(0, 59)),
    }
    tbl["rows"].append({c: vals.get(c) for c in tbl["columns"]})   # EVERY column keyed; absent -> NULL
tbl["rowCount"] = len(tbl["rows"])                                 # db show prints this — keep it honest
seq = next((s for s in sch["sequences"] if s["name"] == TABLE + "_id_seq"), None)
if seq:
    seq["lastValue"] = max(int(r["id"]) for r in tbl["rows"])      # Gotcha 4
p.mark(core.F_DB_DUMP); p.save()
```

(All values are strings, including numbers and booleans — Gotcha 2.) Re-run `mrjun.py validate` afterwards.

> ⛔ **Rows load BEFORE the constraints are added, so a bad row never fails loudly — it fails in one of two silent
> ways.** Restore order per schema is CREATE TABLE → INSERT rows → `setval` → UNIQUE → CHECK → FK → indexes
> (2619–2717). Therefore:
> * a row violating a **CHECK / UNIQUE / FK** inserts happily, and it is the later `ALTER TABLE … ADD CONSTRAINT`
>   that throws — in its own savepoint, logged `WARN`, import still reported successful
>   (`restoreConstraintListWithSavepoints`, 2780–2783). The project comes up **without that constraint**, and the
>   first real user write is what discovers it.
> * a row violating the **table itself** (a type `columnTypes` cannot cast, a NULL in a NOT NULL column, a value
>   longer than its `VARCHAR(n)`) fails the batch, and the table's **entire** data load is rolled back in one
>   savepoint (2660–2683) — the table restores **empty**, again with only a `WARN`. Symptom: exactly one screen is
>   blank while everything around it works.
>
> Neither is caught offline: `validate` has **no row-level checks at all** — it never reads `tables[].rows`
> (`validate_cmds.py`), and `crud verify --db` tests the *methods* against its own rolled-back fixture, not your
> population. Check the generated rows against the constraints yourself, and confirm the row counts after a live
> import ([26-orchestration-and-testing.md](26-orchestration-and-testing.md) §5).

> ⛔ **Do not break the verifiable spine.** If the project pins expected values to specific seeded rows — an offline
> arithmetic/UAT check asserting a total, a count behind a KPI tile, a record a scripted walkthrough opens by number
> — then **new rows must not move those numbers**. Two legal moves, no third:
> 1. grow the population in a partition the pinned check excludes (a different period, owner, entity or status than
>    the pinned rows select), leaving the spine rows *and their aggregates* untouched; or
> 2. recompute and update the pinned expectations **in the same commit** as the seeding.
>
> Shipping a dump whose data and pinned check disagree is worse than shipping the bare fixture: the one artifact
> that was supposed to prove the numbers now disproves them. **Not machine-checkable** — nothing in `validate` knows
> what your check asserts. It is a review rule, and it belongs in the case notes next to the check itself.

---

## Gotchas

1. **Format — DDL strings, not structured objects.** `foreignKeys`/`uniqueConstraints`/`checkConstraints`/
   `indexes`/`triggers` are **arrays of ready-to-run SQL strings**. Columns/types/nullable/default/pk are **not** separate
   fields — they are text inside `tables[].ddl`. Do not look for `columns:[{name,type,nullable,default,pk}]` — such
   a structure does not exist in `nct-jdbc-dump-v1` (the real shape is `ddl`+`columns`+`columnTypes`+`rows`).
2. **All values in `rows` are strings.** Even numbers/boolean/json. `null` → JSON `null`. INSERT casts via
   `ps.setObject(idx, "value", sqlType)`.
3. **`columns` and `columnTypes` must be parallel and match `ddl`.** A desync → INSERT binds
   values to the wrong columns or fails on type.
4. **Sequence `lastValue` is required and must be ≥ the max id.** Otherwise `nextval` on the first INSERT at runtime
   returns a value that conflicts with an already-loaded row. `dataType`/`startValue`/`increment` on restore
   are effectively not applied (a default sequence is created), what matters is `name` + `lastValue`.
5. **Table order.** Stack dependent ones after independent ones; FKs are attached later in a separate pass, but
   the `CREATE TABLE` itself must not reference a non-existent sequence/enum type (those are created earlier).
6. **Plugin node ≠ schema.** `database.management.plugin.properties.model.stringValue` is only the ERD canvas
   (`zoomLevel`, `tablePositions`). Changing it **does not change the DB**. The schema is only in `project-db.dump`.
7. **`database` in the dump must match** `project-db-meta.json.databaseName` and
   `dynamic-cruds.json.cruds[].sourceDb`, and `schemas[].name` — `cruds[].sourceSchema`. Otherwise the CRUDs will not
   find the tables.
8. **Composite FKs.** The serializer's FK query joins `key_column_usage × constraint_column_usage`
   **without aligning on `ordinal_position`** → a composite FK turns into a Cartesian product
   (col × refcol), each emitted as a separate single-column `ALTER`.
   When building by hand write a composite FK as **one** string `FOREIGN KEY ("a","b") REFERENCES t("x","y")`.
9. **Kafka-managed tables** (`KAFKA_MANAGED_TABLES = {"users","role_groups","users_has_role_groups"}`)
   are excluded from both the dump and the restore. There is no need to add them by hand.
10. **enumTypes/views/functions/triggers — format UNVERIFIED against live data.** These lists are empty in
    practically every schema; the shape above is derived from the serializer/restore code, not from a real dump. Marked ⚠️.
11. **CHECK `_not_null`** are excluded from the dump — NOT NULL is already in `ddl`. Do not duplicate them as
    checkConstraints.
12. **Duplicate UNIQUE constraints.** On one table there may be both a JPA auto-name (`uks…`) and a
    human-defined one (`uq_…`) with identical `UNIQUE(...)` (example — `dynamic_crud`). On restore the extra one
    fails in its own savepoint (WARN) and does not collapse the schema; when building by hand write one.
13. **One DBMS — PostgreSQL.** The source object's `dbType` is always `"POISTGRESQL"` (with the typo). There is no
    MySQL/Oracle/SQLServer/Snowflake — do not write other values.
14. **`validate` checks only PART of dump-internal integrity.** `mrjun.py validate` DOES ERROR on
    `len(columns) != len(columnTypes)` and on a DDL `DEFAULT nextval('<seq>')` whose sequence is missing from that
    schema's `sequences[]`, and it WARNs when `project-db.dump.database` disagrees with
    `project-db-meta.json.databaseName` or with a crud's `sourceDb` (`_check_db_dump`, `validate_cmds.py`) —
    on top of the cross-file refs and the dynamic-CRUD SQL-vs-schema checks (`_check_dynamic_cruds`).
    It still does **not** verify that a table has a PRIMARY KEY, that `sequences[].lastValue ≥ max id` in `rows`,
    that a column's declared length fits its data, or that `columns` names the same columns as the `ddl`
    (only that the two arrays are the same LENGTH). Verify those by hand. For the create/update **NOT NULL + CHECK** contract (constraints that pass an empty-table smoke test and throw
    on the first real row) run `crud verify --db "host=… dbname=… user=…"` — it executes each SQL method against a live
    DB inside a rolled-back transaction, seeding a fixture row so CHECK/NOT NULL/FK actually fire (`crudverify_cmds.py`).
15. **`db add-table` is a skeleton, not a finished table.** It emits **no `DEFAULT`/no sequence** for a PK (serial→bare
    `integer`, uuid→bare `uuid`) and hardcodes `VARCHAR(255)` (`db_cmds.py`). After it, hand-add the PK default +
    sequence (style A) or leave the uuid app-set / add `gen_random_uuid()` (style B), fix VARCHAR lengths, and add
    FK/CHECK/UNIQUE strings to the schema lists. See "Two entity styles" and the tooling callout at the top.
