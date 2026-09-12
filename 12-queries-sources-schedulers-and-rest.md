# 12 — Queries, Sources, Schedulers & other rep-objects

> 📐 **Field evidence — schedulers and idempotent sweeps as delivered:** [05-process-and-scheduling.md](references/05-process-and-scheduling.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / When to use

This document describes the "leftover" rep-objects — everything in `rep-objects.json` except
`rules`/`contexts`/`forms`/`formGroups`/`workflows`/`processGroups` (those are covered in separate docs).
Namely:

| Key in `rep-objects.json` | What it is | Admin plugin | Section below |
|---|---|---|---|
| `queries` | Saved SQL queries (used by dynamic-CRUD SQL methods, dropdown/tree-picker rules, charts) | `admin.query.plugin` / `admin.queries.plugin` | [Queries](#1-queries) |
| `sources` | DB connection config (host/port/db/schema/user/password) | `admin.sources.plugin` | [Sources](#2-sources) |
| `schedulers` | Cron jobs: "check predicate → run rule" — the action rule may write rows, notify, or OPEN A CASE (§3.2c) | `admin.schedulers.plugin` | [Schedulers](#3-schedulers) |
| `roleGroups` | Role groups (a set of `ReportRole`) | `admin.rolegroup.management.plugin` | [Role groups](#4-rolegroups) |
| `userRoleGroupAssignments` | "user ↔ role group" binding | `admin.user.management.plugin` | [User assignments](#5-userrolegroupassignments) |
| `settings` | Mirror of CRUD-table / CRUD-tree / Process-table configs (keyed by node `uniqueIdentifier`) | (no separate plugin — written from CrudTable/CrudTree/ProcessTable) | [Settings](#6-settings) |
| `mailTemplates` | HTML email templates (GrapesJS) | `messaging.mail.templates.plugin` | [Mail templates](#7-mailtemplates) |

Covered separately is the content-tree node `project.settings.plugin` — this is NOT a rep-object, but a UI
project-settings panel that **stores nothing in the export** (see [Project Settings](#8-projectsettingsplugin-not-a-rep-object)).
At the end — reference material useful when writing queries and rules: [Placeholder / FieldType reference](#9-placeholders--fieldtype-reference),
[dropDownPopulation](#10-dropdownpopulation--cascading-dropdowns), [Aggregations](#11-aggregations),
[RIMM & service.rimm](#12-rimm--servicerimm-lookup-tables), [Notifications (service.notification)](#13-notifications-servicenotification),
[REST endpoints](#14-rest-endpoints), [findControls → replaceParams](#15-findcontrols--replaceparams-pipeline).

**Queries — the central object for DYNAMIC CRUD.** Every SQL method of a dynamic CRUD references
a saved `query` by `queryIdentifier` (see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)).
So `queries[]` in a dynamic project is dominated by generated entries named `crud_<alias>_<method>` — six per
CRUD (`findAll`/`count`/`get`/`create`/`update`/`delete`), all pointing at the project's business source. A
much smaller tail points at the **RIMM** source: the default platform lookups shipped with an empty project
(`Countries`, the `Rimm …` pickers) plus any CRUD you wired to a platform table such as users
(see §1.5 and §12). Budget your query count accordingly: **entities × 6, plus the RIMM tail.**

> **🔧 Tooling.** For these entities, run [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `query add --name <s> --source <src> --sql @f`, `source add ...`, `rolegroup add/rm/list`, `list settings`.
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.

---

## 1. Queries

### 1.1 Export shape

`rep-objects.json → .queries` is an **array** of `QueryDto`. Schema (every key the exporter emits):

```
{
  "message": null, "errors": null,          // from ErrorResponse — always null in the export
  "id": null,                                // always null in the export
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid>",                    // stable query ID
  "creationTime": "<ISO-8601>", "modificationTime": "<ISO-8601>",
  "name": "<string>",                        // human-readable name (for CRUD methods — generated)
  "query": "<SQL text with placeholders>",    // the SQL itself (NOT `sql`)
  "sourceIdentifier": "<uuid of source>",     // which source to run on (NOT `dataSource`)
  "offset": 0,                               // long, default 0
  "itemsPerPage": 20,                        // long, default 20
  "parameters": {},                          // Map<String,{value}> — saved parameter values (usually {})
  "attributes": {},                          // Map<String,String> — arbitrary attributes (usually {})
  "aggregations": { "aggregations": null, "groupByList": [], "orderByList": [] },
  "wrapInPaging": null,                       // Boolean — whether to auto-wrap in LIMIT/OFFSET
  "statementTimeoutSeconds": null,            // Integer — SQL timeout
  "schedule": null,                           // ScheduleDto — schedule for running the query (see §3)
  "lastScheduledTime": null,                  // Instant — runtime state
  "hidden": null                              // Boolean
}
```

`QueryEntity` (`nct-query/.../entity/QueryEntity.java`) stores this in the `rep_query` table: `name` (NOT NULL),
`query` (column `r_query TEXT`, NOT NULL), `sourceIdentifier` (column `source_identifier`, NOT NULL),
`hidden`. Unique indexes on `(realm,client,name)` and `(realm,client,identifier)` — **the query name is unique
within a project** (important for the `crud_<alias>_<method>` convention).

### 1.2 Worked example — a `find`-support SQL query

The query referenced by the `findAll` SQL method of the dynamic CRUD `equipment_event_types` — i.e. the
`.queries[]` entry with `name == "crud_equipment_event_types_cruid_findAll"`:

```json
{
  "message": null,
  "errors": null,
  "id": null,
  "realmName": "<realm>",
  "clientName": "<client>",
  "identifier": "5476804c-1e0c-4efc-af91-009b42c72609",
  "creationTime": "2026-05-16T12:49:36.997489Z",
  "modificationTime": "2026-05-16T12:49:36.997493Z",
  "name": "crud_equipment_event_types_cruid_findAll",
  "query": "SELECT * FROM dim_equipment_event_types WHERE 1=1 ORDER BY id LIMIT {name: 'rowsInPage', type: 'integer'} OFFSET ({name: 'pageNumber', type: 'integer'} * {name: 'rowsInPage', type: 'integer'})",
  "sourceIdentifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c",
  "offset": 0,
  "itemsPerPage": 20,
  "parameters": {},
  "attributes": {},
  "aggregations": {
    "aggregations": null,
    "groupByList": [],
    "orderByList": []
  },
  "wrapInPaging": null,
  "statementTimeoutSeconds": null,
  "schedule": null,
  "lastScheduledTime": null,
  "hidden": null
}
```

Two more queries of the same CRUD (abbreviated to just `name`+`query`):

```json
{ "name": "crud_equipment_event_types_cruid_get",
  "query": "SELECT * FROM dim_equipment_event_types WHERE id = {name: 'id', type: 'integer'}" }
```
```json
{ "name": "crud_equipment_event_types_cruid_create",
  "query": "INSERT INTO dim_equipment_event_types (id, equipment_event_type, sort_order, is_active, localized) VALUES (gen_random_uuid(), {name: 'equipment_event_type', type: 'string'}, {name: 'sort_order', type: 'integer'}, {name: 'is_active', type: 'boolean'}, {name: 'localized', type: 'jsonb'}) RETURNING *" }
```

An example query running against a RIMM source (from `empty/rep-objects.json`, the default query
`"Rimm User Start With"`):

```json
{ "name": "Rimm User Start With",
  "query": "SELECT u.email as email, CONCAT(u.first_name, ' ', u.last_name) as name\r\nFROM users u\r\nWHERE \r\n (\r\n      LOWER(u.email) LIKE LOWER(CONCAT('%', {name: 'term'}, '%'))\r\n   OR LOWER(u.first_name) LIKE LOWER(CONCAT('%', {name: 'term'}, '%'))\r\n   OR LOWER(u.last_name) LIKE LOWER(CONCAT('%', {name: 'term'}, '%'))\r\n  )",
  "sourceIdentifier": "b814d61d-84b6-4611-99b3-914e0ca067db" }
```

### 1.3 Field-by-field

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `identifier` | String (UUID) | Stable query ID. This is exactly what goes into the CRUD SQL method's `queryIdentifier` | yes | — | `AbstractSecuredDto.identifier` |
| `name` | String | Name. `@NotBlank`, **unique** in the project. For CRUD methods it is generated as `crud_<alias>_<method>` (see gotcha) | yes | — | `QueryDto.name` |
| `query` | String | SQL. `@NotBlank`. Placeholders of the form `{name: 'x', type: 'y'}` (see §1.4, §9) | yes | — | `QueryDto.query` |
| `sourceIdentifier` | String (UUID) | `identifier` of the source to run the SQL on | yes (otherwise nowhere to send it) | null | `QueryDto.sourceIdentifier` |
| `offset` | Long | Default paging offset | no | `0` | `QueryDto.getOffset()` |
| `itemsPerPage` | Long | Default page size | no | `20` | `QueryDto.getItemsPerPage()` |
| `parameters` | Map<String,{`value`:Object}> | Saved query parameter values (for preview/charts). For CRUD methods it is **always `{}`** — values arrive at runtime | no | `{}` (`LinkedHashMap`) | `QueryDto.getParameters()`, `QueryDto.Parameter` |
| `attributes` | Map<String,String> | Arbitrary string attributes | no | `{}` (`HashMap`) | `QueryDto.getAttributes()` |
| `aggregations` | `QueryAggregationsDto` | Group-by / order-by / aggregations (for charts). For CRUD an **empty skeleton**. See §11 | no | `{aggregations:null, groupByList:[], orderByList:[]}` | `QueryDto.getAggregations()` |
| `aggregations.aggregations` | List<`Aggregation`>\|null | List of aggregations (`{aggCol,as,aggType}`) | no | `null` | `QueryAggregationsDto.aggregations` |
| `aggregations.groupByList` | List<`GroupBy`> | GROUP BY (`{col}`) | no | `[]` | `QueryAggregationsDto.groupByList` |
| `aggregations.orderByList` | List<`OrderBy`> | ORDER BY (`{col}`) | no | `[]` | `QueryAggregationsDto.orderByList` |
| `wrapInPaging` | Boolean\|null | Wrap SQL in auto LIMIT/OFFSET. In exports always `null` (paging is set manually inside the SQL) | no | `null` | `QueryDto.wrapInPaging` |
| `statementTimeoutSeconds` | Integer\|null | SQL execution timeout, sec | no | `null` | `QueryDto.statementTimeoutSeconds` |
| `schedule` | `ScheduleDto`\|null | Auto-run schedule of the query itself (structure — see §3) | no | `null` | `QueryDto.schedule` |
| `lastScheduledTime` | Instant\|null | Runtime: last scheduled run | no | `null` | `QueryDto.lastScheduledTime` |
| `hidden` | Boolean\|null | Hide from the UI list | no | `null` | `QueryDto.hidden` |

> **Important:** for generated CRUD queries these fields never vary — `parameters == {}`, `attributes == {}`,
> `wrapInPaging == null`, `schedule == null`, `statementTimeoutSeconds == null`, `itemsPerPage == 20`,
> `offset == 0`, `aggregations.groupByList == []`. That is, **for
> DYNAMIC CRUD these fields can simply be copied as-is**, and the only things that actually distinguish a query are
> `identifier`, `name`, `query`, `sourceIdentifier`. The fields `offset`/`itemsPerPage`/`parameters`/
> `aggregations`/`wrapInPaging` are named `sql`/`dataSource`/`limit` in early concept docs — that is obsolete.

### 1.4 Placeholders in SQL — not in `parameters`, but right in the text

Query parameters are **embedded in the SQL text** as `{name: 'paramName', type: 'sqlType'}`, NOT in the
`parameters` field (which is for saved preview values). Full Replacement syntax (`Replacement.java`):

```
{name: 'paramName', type: 'sqlType', defaultValue: '...', dropDownPopulation: {...}}
```

The `type` strings that appear in generated-CRUD SQL, roughly in order of how often you will write them:

```
integer   string   jsonb   boolean   instant   bigdecimal   date
```

⚠️ Note: `jsonb`, `instant`, `bigdecimal` are **raw SQL types from the CRUD generator**; they are
NOT `FieldType.name` names (there is no `FieldType` constant named `jsonb`; the closest to `instant` is
`dropdown-instant`). They are resolved by the dynamic-CRUD generation path, not by the report parametric
`FieldType.findByName`. For CRUD methods, write exactly the raw column types. The full `FieldType` reference
(for report/chart parameters) — see [§9](#9-placeholders--fieldtype-reference). Placeholder processing —
`PlaceholderProcessorServiceImpl` in `nct-query` (see §15). The correspondence "placeholder name ↔ CRUD-method
parameter" is described in [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)
(method `parameters[].parameterName` = placeholder name; `rowsInPage`/`pageNumber` for paging are
standard names).

### 1.5 Default (RIMM) queries in `empty`

An empty project already carries 6 queries (`empty/rep-objects.json`): `Countries`, `Rimm Brand Start With`,
`Rimm Countries Start with`, `Rimm Equipments`, `Rimm Users by Role Group`, `Rimm User Start With`. All of
them point to the **RIMM source** (in `empty`, `sourceIdentifier == "b814d61d-84b6-4611-99b3-914e0ca067db"`).
This source is **absent** from the `sources` export — it is recreated on import (see §2.4).
`Countries` is a concrete RIMM-lookup example:
`select * from rimm_country;` (in the export with newlines; see §12 about RIMM tables).

In a project of your own the RIMM source has its own `identifier`, matching
`project-db-meta.json.rimmSourceIdentifier`. Extra queries accumulate on it whenever a CRUD is wired to a
platform table instead of the business schema — a `users` CRUD, for instance, reads the platform user table via
RIMM, so its six `crud_users_*` queries carry the RIMM `sourceIdentifier`, not the business one.

---

## 2. Sources

### 2.1 Export shape

`rep-objects.json → .sources` is an **array** of `SourceDto`:

```
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid>",
  "creationTime": "<ISO>", "modificationTime": "<ISO>",
  "name": "<schema name>",
  "description": "<string>",
  "hostName": "<host>",
  "port": 5432,
  "dbName": "<database>",
  "schemaName": "<schema>",
  "userName": "<db user>",
  "password": "<db password (hex-encrypted)>",
  "dbType": "POISTGRESQL",
  "sourceType": "INTERNAL"
}
```

### 2.2 Worked example — the single business source of a dynamic project

A dynamic project normally has exactly **one** business source, `sources[0]`:

```json
{
  "message": null,
  "errors": null,
  "id": null,
  "realmName": "<realm>",
  "clientName": "<client>",
  "identifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c",
  "creationTime": "2026-05-16T12:49:34.397094Z",
  "modificationTime": "2026-05-16T12:49:34.397099Z",
  "name": "app_schema",
  "description": "Internal schema: app_schema",
  "hostName": "<db-host>",
  "port": 5432,
  "dbName": "prj_<realm>_<client>",
  "schemaName": "app_schema",
  "userName": "prj_<realm>_<client>_user",
  "password": "<hex-encrypted>",
  "dbType": "POISTGRESQL",
  "sourceType": "INTERNAL"
}
```

This `identifier` is what nearly every query's `sourceIdentifier` points at, as well as the fields
`sourceIdentifier`/`sourceHost`/`sourcePort`/… in `dynamic-cruds.json.cruds[]`
(see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)).

> ⚠️ **In practice only `sourceType=INTERNAL` is ever serialized into an export** — the other kinds are either
> absent or filtered out (§2.3). `EXTERNAL`/`INTEGRATION`/`SYSTEM` are described below from the enum + import
> code: treat their semantics as verified against the code, but the exact JSON as `⚠️ UNVERIFIED`.

### 2.3 Field-by-field

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `identifier` | String (UUID) | Stable source ID. Referenced by query.`sourceIdentifier` and CRUD.`sourceIdentifier` | yes | — | `AbstractSecuredDto.identifier` |
| `name` | String | Source name. `@NotBlank`. For an internal schema = the schema name (`app_schema`). RIMM sources are named with a `RIMM_` prefix | yes | — | `SourceDto.name` |
| `description` | String | Description | no | null | `SourceDto.description` |
| `hostName` | String | Postgres host. `@NotBlank`. Overwritten on import (see §2.4) | yes | — | `SourceDto.hostName` |
| `port` | Integer | Port. `@NotBlank` (validator on Integer) | yes | — | `SourceDto.port` |
| `dbName` | String | DB name. `@NotBlank`. Remapped to the new project DB on import (see §2.4) | yes | — | `SourceDto.dbName` |
| `schemaName` | String | Schema within the DB. `@NotBlank` | yes | — | `SourceDto.schemaName` |
| `userName` | String | DB user. `@NotBlank`. Overwritten on import for INTERNAL | yes | — | `SourceDto.userName` |
| `password` | String | Password (hex-encrypted). Overwritten on import for INTERNAL | no | null | `SourceDto.password` |
| `dbType` | enum `DbType` | DB type. `@NotNull`. The only value — `POISTGRESQL` (the typo in the enum name is canonical!) | yes | — | `SourceDto.dbType`, `DbType.java` |
| `sourceType` | enum `SourceType` | `INTERNAL` \| `EXTERNAL` \| `INTEGRATION` \| `SYSTEM` | no | `INTERNAL` | `SourceDto.sourceType`, `SourceType.java` |

`DbType.POISTGRESQL` (`DbType.java`): displayName `"Postgresql"`, id `"postgresql_database"`, JDBC url
`jdbc:postgresql://<host>:<port>/<db>`. This is the **only** enum constant — no MySQL/Oracle/etc.

`SourceType` (`nct-transfer/.../dto/SourceType.java`):
- `INTERNAL` — the project schema with user data; credentials are overwritten/synced on import.
- `EXTERNAL` — an external third-party DB; the credentials belong to the user and are **never rotated**.
- `INTEGRATION` — the integration-container schema (Liquibase pod); **excluded from the export** (recreated when the integration is deployed). A project whose CHARTS read that schema declares the source in `integrations.json.dataSourceIdentifiers`, and the import binds it to the target's own integration schema — see point 6 below and [00 §9](00-export-format-and-import.md).
- `SYSTEM` — the dynamic-integration metadata schema (tables `dynamic_crud`/`dynamic_method`/`dynamic_parameter`/`dynamic_field`, one per project); **excluded from the export**, recreated on import; hidden from the Database-Management UI.

### 2.4 What happens to sources on import (critical for building)

`CmsProjectServiceImpl` (import, `nct-ui/.../CmsProjectServiceImpl.java`):

1. **RIMM sources are excluded**: `sourcesToImport = qss.getSources().filter(name == null || !name.startsWith("RIMM_"))`. So the RIMM source **must not be put in the export** — it is recreated, and `project-db-meta.json` has a `rimmSourceIdentifier`, while queries reference the old RIMM `identifier` (see gotcha).
2. **dbName is remapped**: the old `dbName` (from `project-db-meta.json.databaseName`) is replaced by the name of the new project DB.
3. **INTERNAL credentials are rewritten**: `userName`/`password` of INTERNAL sources are replaced with the assigned project-level role (`s.getSourceType()==INTERNAL ? toBuilder().userName(un).password(pw) : s`). Whatever password string sits in the export is **ignored** on import. `EXTERNAL` — credentials are kept as-is.
4. **hostName** is normalized by the execution platform after import.
5. **SYSTEM/INTEGRATION sources** are created in place (filter them out on export), they are not in the export.
6. **Integration data sources are rebound** (`bindIntegrationDataSources`, after the integrations are RUNNING):
   every source identifier listed in `integrations.json.dataSourceIdentifiers` is pointed at THIS tenant's
   `int_<realm>_<client>_<id>` schema — the imported row is repointed (host/port/db/schema/user/password), or
   recreated under the same identifier if the donor's row was an `INTEGRATION` one. Queries and chart embeds
   keep their `sourceIdentifier`, so they follow automatically. **Without this declaration a statically
   integrated project imports with its charts still reading the database it was BUILT against** — reachable
   or not, usually empty, and silent about it. See [00 §9](00-export-format-and-import.md).

Practical takeaway for Step-2 building: the values `hostName`/`dbName`/`userName`/`password` in the
INTERNAL source can be set "as in the original export" (or any non-empty value) — the import overwrites them
anyway. Only `identifier`, `name`, `schemaName`, `sourceType=INTERNAL`, `dbType=POISTGRESQL`, and `port` matter.

---

## 3. Schedulers

> **Naming note — the `Scheduelrs` typo.** The built-in admin page node is named **`Scheduelrs`** (alias
> `schedulers`, `pluginName:"siteMapPage"`, `uniqueIdentifier` `befacaf8-19b6-4c63-aca3-128265e78d9e` in
> `empty/branches.json`) — a canonical typo to preserve (cross-ref [01-content-model-and-pages.md](01-content-model-and-pages.md)
> / [14-plugin-catalog-all.md](14-plugin-catalog-all.md)). It is **only** a content-tree page-node display name; there
> is **zero** `Scheduelr` in any Java identifier
> (grep = 0 hits). Do not confuse it with the rep-object `schedulers[]` described here.

### 3.1 Export shape

`rep-objects.json → .schedulers` is an **array** of `ScheduleDto` (persisted as `ScheduleEntity`, table
`rep_schedule`). **Most projects export it empty (`[]`)** — cron triggers are rare, so you will seldom see a
live example. The schema below is nonetheless **confirmed field-for-field** against `ScheduleEntity`
(`nct-schedule/.../entity/ScheduleEntity.java`) and `ScheduleDto` (`nct-transfer/.../ScheduleDto.java`):
`job` and `cooldownJob` are stored as **`jsonb`** columns (`ScheduleEntity.java`), so in the export
they really are the nested `{expression,explanation,cronType}` objects shown here. (The entity also carries a
**vestigial** top-level `expression` String column, `ScheduleEntity.java`, that the DTO does NOT have and
that never appears in the export — registration reads `job.expression`, not it.)

```
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid>",
  "creationTime": "<ISO>", "modificationTime": "<ISO>",
  "name": "<string>",
  "job": { "expression": "<cron>", "explanation": "<string>", "cronType": "<CronType|null>" },
  "predicateIdentifier": "<uuid rule|null>",
  "actionType": "RUN_RULE",
  "actionRuleIdentifier": "<uuid rule|null>",
  "cooldownJob": { "expression": null, "explanation": null, "cronType": null },
  "enabled": true,
  "cooldownUntil": null,
  "lastActionTime": null,
  "lastPredicateCheckTime": null,
  "serviceUserId": "<uuid>",
  "serviceUserEmail": "<email>"
}
```

> ⛔ **COPY THIS BLOCK FIELD FOR FIELD. Every wrong name fails SILENTLY.** The import deserialises
> with `FAIL_ON_UNKNOWN_PROPERTIES=false` (`nct-ui JacksonConfig`), and this is the one export object
> with **no live reference to check yourself against** — every shipped `.mrjun` carries
> `schedulers: []`. So a plausible-looking invented key is simply dropped, the scheduler imports, it
> appears in the list with its name and its two rules, and only the field it was meant to fill is
> empty. Observed for real on a live build (2026-08), all four at once:
>
> | written | what ScheduleDto actually has | consequence of getting it wrong |
> |---|---|---|
> | `cronExpression: "0 0 8 * * ?"` | `job: {expression, explanation, cronType}` | `job` stays null → `CronServiceImpl.registerSchedule` logs *"has no cron expression, skipping cron registration"* → **the schedule never fires, ever** |
> | *(omitted)* | `actionType: "RUN_RULE"` | the editor's Action Type dropdown is `setNullValid(false)` → renders **empty**, and the scheduler cannot be saved from the UI without re-picking it |
> | `description: "…"` | — (no such field) | the description is gone |
> | `contextIdentifiers: [...]` | — (no such field) | harmless, but it signals a real misunderstanding: a scheduler rule runs HEADLESS. `SchedulerExecutionServiceImpl` builds `ExecuteRequest` from the rule id + service user only, so **the context is attached to the RULE**, never to the schedule |
> | `lastRunTime: null` | `lastActionTime` / `lastPredicateCheckTime` | nothing |
>
> And the cron above is doubly wrong: `?` is a **Quartz** token and this runtime is Spring
> `CronTrigger` — see the dialect note below. `mrjun.py validate` now ERRORs on all of it: an unknown
> key, a missing `job.expression`, and an `actionType` that is not `RUN_RULE`.

> ⚠️ The obsolete concept doc `scheduled-jobs.md` describes a scheduler as cron→`ruleIdentifier`/
> `queryIdentifier` with `nextExecution` and a separate `ScheduleExecution` history. **That is not the case.** The real
> model is "on cron check the predicate → (with cooldown) run the action rule". There is no `queryIdentifier`, no
> `nextExecution`, no `ScheduleExecution`. A scheduler CANNOT run a query directly — only a rule
> (`actionType == RUN_RULE`).

### 3.2 Field-by-field

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `identifier` | String (UUID) | Schedule ID | yes | — | `AbstractSecuredDto.identifier` |
| `name` | String | Name. **UNIQUE per project** — a unique index on realm+client+name (`ScheduleEntity`). Two schedulers carrying the same non-null `name` in one export make the second save throw on import, and schedulers are saved BEFORE workflows/rules/contexts/forms/settings/templates, so everything after them is silently skipped | no (null is legal; if set, must be unique) | null | `ScheduleDto.name` |
| `job` | `CronJob` | Main run schedule | yes | `new CronJob()` (getter lazy) | `ScheduleDto.job` |
| `job.expression` | String | Cron string, **Spring `SPRING53` 6-field** `sec min hour dom mon dow` (see cron-dialect note below) | yes (blank → not registered) | null | `CronJob.expression` |
| `job.explanation` | String | Human-readable description | no | null | `CronJob.explanation` |
| `job.cronType` | enum `CronType` | Preset (see below) | no | null | `CronJob.cronType` |
| `predicateIdentifier` | String (UUID) | Predicate rule: if true → run the action. **Must be a `PREDICATE`-type rule** (UI restricts to `RuleType.PREDICATE`, `SchedulerFormEditorPanel.java`; its result is read via `response.extractBooleanResult()`, `SchedulerExecutionServiceImpl.java`). Point it at a non-`PREDICATE` rule and the result is non-boolean/blank → predicate false → the action silently never fires. **Blank/null ⇒ defaults to `true`** (`evaluatePredicate`) → action fires on EVERY tick (subject to cooldown), NOT "never" | no | null | `ScheduleDto.predicateIdentifier` |
| `actionType` | enum `ActionType` | The only value — `RUN_RULE` | no | null | `ScheduleDto.actionType`, `ActionType.java` |
| `actionRuleIdentifier` | String (UUID) | Execution rule to run. **Must be an `EXECUTION_RULE`** (UI restricts to `RuleType.EXECUTION_RULE`, `SchedulerFormEditorPanel.java`) | no | null | `ScheduleDto.actionRuleIdentifier` |
| `cooldownJob` | `CronJob` | Cooldown. `cooldownJob.expression` is a CRON whose **next fire time** becomes `cooldownUntil` (`computeCooldownUntil`) — a next-fire timestamp, **not a duration**. Blank ⇒ no cooldown | no | `new CronJob()` | `ScheduleDto.cooldownJob` |
| `enabled` | boolean | Whether it is enabled | no | `false` | `ScheduleDto.enabled` |
| `cooldownUntil` | Instant | Runtime | no | null | `ScheduleDto.cooldownUntil` |
| `lastActionTime` | Instant | Runtime | no | null | `ScheduleDto.lastActionTime` |
| `lastPredicateCheckTime` | Instant | Runtime | no | null | `ScheduleDto.lastPredicateCheckTime` |
| `serviceUserId` | String | **Execution identity for BOTH hops** — copied into `ExecuteRequest.userId` for the predicate REST call (`SchedulerExecutionServiceImpl.java`) and forwarded in the Kafka `SchedulerActionMessage` → executor `ExecuteRequest.userId` (`KafkaConsumer.java`). If the action/predicate rule calls `service.security.user()` or any user-scoped context, set this — blank ⇒ null principal | no | null | `ScheduleDto.serviceUserId` |
| `serviceUserEmail` | String | Execution-identity email (same two hops, `SchedulerExecutionServiceImpl.java`, `KafkaConsumer.java`) | no | null | `ScheduleDto.serviceUserEmail` |

> **⚠️ Cron dialect — Spring `SPRING53`, NOT Quartz.** The runtime parses cron with cron-utils
> `CronType.SPRING53` (`nct-schedule SchedulerExecutionServiceImpl.computeCooldownUntil`) and registers
> `job.expression` via `org.springframework.scheduling.support.CronTrigger` (**`nct-schedule`** `CronServiceImpl`
> — there is ALSO an `nct-ui` `CronServiceImpl`, so always name the module). 6-field `sec min hour dom mon dow`; use
> `*` and named days (`MON-FRI`). Quartz-only tokens `?` and `L` **fail**.
> **Ignore the platform's own scheduler notes** — its Quartz examples (`0 0 2 * * ?`, `L`, "Quartz format") are wrong for this
> path, and it invents `taskType`/`TaskExecutor`/`CronValidator`/`ScheduleExecution`/`/api/schedules` — none of which exist.
>
> **Registration gate** (correcting any "scheduled()" notion — no such method exists): a schedule is registered only
> if `enabled==true` AND `job.expression` is non-blank (`nct-schedule CronServiceImpl.registerSchedule` skips
> disabled OR blank, then wires a `CronTask`); on startup only `enabled==true` schedules are loaded
> (`BootstrapComponent.init` `@PostConstruct` → `registerAllEnabled` → `findAllByEnabled(true)`).

`CronType` (`nct-transfer/.../dto/chart/CronType.java`) — 6 presets, each building a cron string
(`sec min hour dom mon dow`) from a single number with min/max validation. These are a **coarse wildcarded UI
convenience**: e.g. `MINUTE_OF_EVERY_HOUR = "* %s * * * *"` leaves the `sec` field `*`, so it fires **every second
of that minute**. When hand-authoring, write the full 6-field cron in `job.expression` and leave `cronType=null`.
`cronType` is only a **UI convenience**: at runtime registration reads `job.getExpression()` directly
(`CronServiceImpl.registerSchedule`), never `cronType`. (The one method that would apply it,
`CronJob.init(int)` → `expression = cronType.expression(val)`, `CronJob.java`, has **zero callers** anywhere —
so a non-null `cronType` does NOT overwrite a hand-written `expression`. Still, leave it null to avoid confusion.)

| Constant | Template | min | max |
|---|---|---|---|
| `SECOND_OF_EVERY_MINUTE` | `"%s * * * * *"` | 0 | 59 |
| `MINUTE_OF_EVERY_HOUR` | `"* %s * * * *"` | 0 | 59 |
| `HOUR_OF_EVERY_DAY` | `"* * %s * * *"` | 0 | 23 |
| `EVERY_DAY_OF_MONTH` | `"* * * %s * *"` | 1 | 31 |
| `EVERY_MONTH` | `"* * * * %s *"` | 1 | 12 |
| `SOME_OTHER` | `"* * * * * %s"` | 0 | 6 |

`ActionType` (`ActionType.java`): the only value `RUN_RULE`.

The scheduler model: "on cron `job.expression` check `predicateIdentifier`; if true — run
`actionRuleIdentifier` (`actionType=RUN_RULE`); honor `cooldownJob`". Authoring is via `SchedulerPlugin`
(`admin.schedulers.plugin`) in nct-ui, not via the content tree. About rules (predicate/execution) —
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).

### 3.2b How a scheduler fires — the two-hop pipeline

The doc-level model "check predicate → run rule" hides a **two-hop, two-transport** pipeline in `nct-schedule` +
`nct-executor`. A builder debugging "my scheduler doesn't fire" needs the whole path:

1. **Startup** — `BootstrapComponent.init()` (`@PostConstruct`) calls `cronService.registerAllEnabled()`
   which loads only `findAllByEnabled(true)` (`CronServiceImpl.java`).
2. **Registration gate** — `CronServiceImpl.registerSchedule` skips if `!enabled` OR `job.expression` is
   blank, else wires a Spring `CronTask(() -> executeSchedule(id), new CronTrigger(expression))`
   — a **live cron trigger**.
3. **Tick** — `SchedulerExecutionServiceImpl.executeSchedule(id)`: reload → skip if disabled
   → skip if `cooldownUntil` is in the future.
4. **Predicate = SYNCHRONOUS REST to the executor.** `evaluatePredicate` builds an `ExecuteRequest`
   (`ruleIdentifier=predicateIdentifier`, realm/client, `userId=serviceUserId`, `userEmail=serviceUserEmail`) and
   calls `executorFeignClient.executeInternal(request)`, then `response.extractBooleanResult()`.
   Blank `predicateIdentifier` ⇒ returns `true`; any exception ⇒ `false`.
5. **Action = ASYNCHRONOUS via Kafka.** If the predicate is true, `fireAction` publishes a `SchedulerActionMessage`
   (`scheduleIdentifier`, `ruleIdentifier=actionRuleIdentifier`, realm/client, `userId`/`userEmail`, `triggerTime`)
   to topic **`scheduler-execute-action`** = `MessageTopics.Scheduler.EXECUTE_ACTION`
   (`SchedulerExecutionServiceImpl.java` → `MessageBrokerServiceImpl.sendAction` → `MessageTopics.java`).
6. **Executor runs the rule.** `nct-executor` `KafkaConsumer.handleSchedulerAction` consumes the topic, rebuilds an
   `ExecuteRequest` (same rule id + realm/client + `serviceUser*`), and calls `executionService.execute(request)`
   (`nct-executor/.../kafka/KafkaConsumer.java`). This is the actual "run the `EXECUTION_RULE`" step.
7. **Cooldown & persist** — sets `lastActionTime=now`, `cooldownUntil = next fire of cooldownJob.expression`
   (cron-utils `SPRING53`, `computeCooldownUntil`; blank ⇒ null), then saves.

So: **predicate = sync REST (executor Feign)**, **action = async Kafka (executor consumer)** — the action is
**fire-and-forget** (no result surfaced back to the schedule; success/failure only logged in `nct-executor`). The
security identity for BOTH hops is `serviceUserId`/`serviceUserEmail`. Debug checklist: executor reachable (predicate),
Kafka up and topic consumed (action), predicate returns a real boolean.

### 3.2c What the action rule receives — and what it may do

The tick carries **no data**, and no user beyond the `serviceUserId`/`serviceUserEmail` stamped on the schedule
row itself. `KafkaConsumer.handleSchedulerAction` rebuilds the `ExecuteRequest` from `ruleIdentifier` +
realm/client + `userId`/`userEmail` and **never calls `.contextData(...)`** (`nct-executor/.../kafka/KafkaConsumer.java`),
so the executor builds a fresh document (`ContextDataDto.builder().attrs(executionVariables).build()`,
`RuleExecutorReactor.java`) whose `contextDataMap` stays **null**. That one fact dictates the whole shape of the
rule:

| Inside the action rule | State at tick time | Backing |
|---|---|---|
| `attrs` | **empty map, never null** — `attrs.get('x')` returns null instead of throwing | `ExecuteRequest.executionVariables` defaults to an empty map; `ContextDataDto.getAttrs()` creates one lazily |
| `param` | empty map — method parameters exist only on the CRUD-GROOVY-method path | `GroovyExecutionRule` builds `paramMap` unconditionally and fills it only from the `__methodParams` marker |
| `contextDataMap` | **null**, and the binding is never made | `GroovyExecutionRule` puts it in only `if (contextData != null && contextData.getContextDataMap() != null)`; the template's `def contextDataMap` field stays null (`ExecutionRuleTemplate.groovy`), so `contextDataMap['x']` is an NPE on line 1 |
| `context.<ctx>.data`, `context.<ctx>.<alias>.data` | **throw** — `No context data available for context: <alias>` / `No CRUD data available for CRUD: <alias>` | the empty envelopes are created only when a document exists (`RuleExecutorReactor.enhanceContextDataWithCrudInfo` returns early on a null map; throw sites in `DynamicRuleContext.groovy`) |
| `service.crud.<alias>.<m>(...)`, `context.<ctx>.<alias>.service.<m>(...)` | **work** — the only way in to business logic | neither one reads the document: `context.<ctx>.<alias>.service` is a `ServiceWrapper` created on demand from the ATTACHED CONTEXT's `crudAliases` (`DynamicRuleContext.groovy`), which is why it still resolves while `.data` on the same chain throws; `service.crud.<alias>` is a separate pair, `ServiceCrudLookup`/`ServiceCrudInvoker`, gated the same way — with NO context attached it resolves against the whole realm/client CRUD registry, with ANY context attached only to that context's `crudAliases` |
| `service.security.user()`, `hasAnyRole*` / `hasAnyRoleGroup(...)` | all-null user, **every check false** and no error — unless the schedule carries `serviceUserId` | `SecurityHelper` short-circuits to `false` when `userId` is null |
| the rule's return value | **discarded** | fire-and-forget (§3.2b); an exception is caught into a FAILURE response (`ExecutionServiceImpl.java`), so the tick is consumed — no retry, no dead letter |

So the action rule **fetches everything it works on itself**, and it has no caller to report to: its only outputs
are the ones it takes deliberately — write rows through `service.crud.*`, notify (`service.notification.*` §13, or
a mail template §7), or **start a process** — and **which one is not a preference: it is read off the Phase-1a
trigger row's PRODUCT column** ([19](19-build-decision-procedure.md) Phase 1a, "What it produces"). Rows written
= a derived value somebody will look at later. A notification = news, for a named person who is already watching.
**A CASE = work somebody has to clear, and only `service.workflow.start` produces one** — if the row says CASE and
the rule ends in `service.notification.*`, the work item was never built, and nothing anywhere will say so: the
mail arrives, the schedule logs a success, and no worklist ever shows the item.

**Opening a case is a first-class action, not just mail.** `service.workflow.start('<workflowIdentifier>',
<contextDataDocument>[, <options>])` is available in an `EXECUTION_RULE`, which is what makes "the system opens the
case by itself" a scheduler job: sweep for candidate rows → shape them into a context data document → start the
workflow → mark the rows so the next tick skips them. It is deliberately **refused in a `PREDICATE`**
(`WorkflowProxy.unavailableIn("predicates")` → *"service.workflow.start is not available in predicates - they are
evaluated for their answer and must not create work"*), so the gate can never be the rule that starts anything:
trigger, gate and action stay three separate objects.

> ⚠️ **A sweep that starts a process needs an idempotency guard you write yourself.** Nothing asks "does a case
> already exist for this row" on your behalf, and `businessKey` is neither unique nor enforced. Without a guard
> in the business data (a state transition, or a marker column claimed atomically), the schedule opens a NEW
> case for the same row on **every tick, forever** — and every screen still looks correct.
>
> `service.workflow.list(...)` ([16](16-groovy-service-api.md) §2.13) can be made to look, but only through a
> process table's INDEXED values and at a query per trigger row. A claim column is exact, free, and does not
> depend on how somebody configured a screen.

The full chain — recognising it in the PRD, the order the objects must be built in, the sweep rule that gathers
rows, shapes the document and starts the process, the atomic claim that makes it idempotent, and how to make the
case findable — is [27-event-driven-process-start.md](27-event-driven-process-start.md). This section stays the
reference for the trigger OBJECT only; the workflow contract itself is
[07-workflows-and-tasks.md](07-workflows-and-tasks.md), and the `start(...)` signature and its five option keys
are [16-groovy-service-api.md](16-groovy-service-api.md) §2.12.

### 3.3 Authoring a scheduler in the export

`mrjun.py` has **no scheduler command** (the CLI covers `rule`/`query`/`source`/`context`/`rolegroup`/`form*`/
`mailtemplate`/`workflow`, but not `schedulers`). Procedure:

1. Create the predicate rule (optional) and the action rule first — `mrjun.py rule add ...` (see doc 08). The action
   rule is a **headless `EXECUTION_RULE`** (§3.2c): it has no form/CRUD context at tick time, so it must load its own
   rows via `service.crud.<alias>.find(...)` (or the RIMM/query proxies), not from `context.<ctx>.<alias>.data`. If it
   OPENS A CASE, the workflow, its `processGroups[]` entry and the method that marks a claimed row must exist before
   the rule quotes their identifiers — build order in
   [27-event-driven-process-start.md](27-event-driven-process-start.md) §3.
2. Hand-add one `ScheduleDto` to `rep-objects.json → .schedulers[]`: fresh `identifier` UUID; all runtime fields
   `null` (`cooldownUntil`/`lastActionTime`/`lastPredicateCheckTime` — the server nulls these on save anyway,
   `SchedulerServiceImpl.java`, so a stray value is harmless); point `predicateIdentifier`
   `actionRuleIdentifier` at the rule UUIDs. Remember blank `predicateIdentifier` ⇒ fires every tick (§3.2).
   **Set `enabled=false` unless the trigger is meant to be live the instant the project is imported** — see the
   build-safety warning below.

> ⚠️ **BUILD SAFETY — an imported `enabled:true` scheduler starts firing immediately.** On import each scheduler is
> saved via `schedulerService.saveBackend`/`save` (`CmsProjectServiceImpl.java`) → `nct-schedule`
> `SchedulerServiceImpl.save` → `cronService.registerSchedule(saved)` (`SchedulerServiceImpl.java`).
> `registerSchedule` activates a **live `CronTrigger` whenever `enabled==true` AND `job.expression` is non-blank**
> (`CronServiceImpl.java`). So a scheduler authored "for later" or "for testing" with a valid cron will run its
> action `EXECUTION_RULE` **on the real project, on the configured schedule, the moment the `.mrjun` is imported** — a
> side-effecting rule (create/update/notify) fires in prod with no further action. Author `enabled=false` unless you
> intend the trigger to be live on import; the registration gate is `enabled` AND non-blank `job.expression`.
>
> **Turning it on afterwards is one click, and it takes effect immediately.** The schedulers screen shows each row's
> state as an `Enabled` / `Disabled` badge and carries a power button that flips it (`SchedulerPlugin.java`); the flip
> goes through the ordinary save, and `SchedulerServiceImpl.save → CronServiceImpl.registerSchedule` builds the live
> `CronTrigger` right there — no restart. Flipping the column directly in the database does NOT work the same way:
> cron tasks live in an in-memory map inside the scheduler service, so a hand-edited row is only picked up at the next
> restart of `nct-schedule`. Until it is enabled, nothing is logged and nothing runs — the predicate is never even
> evaluated (`lastPredicateCheckTime` stays `null`), which is exactly what an imported project looks like.
>
> ⛔ **A scheduler is the ONLY object in a `.mrjun` whose import leaves the CMS process.** Everything else —
> pages, rules, CRUDs, queries, forms, workflows, templates, the DB dump — is written by the CMS itself;
> a schedule goes `CmsProjectServiceImpl → schedulerService.saveBackend/save` → **over the wire to
> `nct-schedule`**. So when that service is unreachable the import reports exactly the schedulers as rejected
> and nothing else, with a **socket** message rather than a validation one:
>
> ```
> Imported with warnings
> N objects in this archive were rejected and could not be imported:
>   • scheduler — Can't assign requested address "…" (uuid), …
> ```
>
> `Can't assign requested address` is `EADDRNOTAVAIL` — `nct-schedule` is down, its URL points at a host the
> CMS container cannot reach, or the name resolves to an IPv6 address on a host without IPv6. **It is not a
> defect in the export**, and no edit to the `ScheduleDto` changes it: the same message on every scheduler in
> the archive is the signature of an unreachable endpoint, while a per-object fault (a duplicate `name`, a
> quota) names itself. Fix the connectivity and re-import the same archive — `schedulers[]` is independent, so
> a second import only adds them — or enter them by hand on the Schedulers screen. **Check first that
> everything saved AFTER the schedulers actually landed** (workflows, rules, contexts, forms, settings,
> templates — see the `name` row above), then compare object counts against the archive.
>
> On export, schedulers leave via `.schedulers(schedulers.stream().map(it -> it.toBuilder().id(null).build())…)`
> (`CmsProjectServiceImpl.java`; the list is fetched by `schedulerService.findAllBackend`). A project
> cap `QuotaConfig.maxSchedulersPerProject` (`nct-transfer/.../dto/QuotaConfig.java`) is enforced on **create** in
> `SchedulerServiceImpl.checkSchedulerQuota` (→ `ServiceException "quota.max.schedulers.exceeded"`), so
> bulk-importing many schedulers into a quota'd project can be rejected.

**MODIFY-FILLED:** to add a scheduler to a working dynamic `.mrjun`, **append one `ScheduleDto`** to `.schedulers[]`
without touching existing entries — the array is independent of every other object; nothing references a schedule by
back-pointer, so no re-wiring is needed.

> Note: a query also has a `schedule` field (`QueryDto.schedule`) of the same `ScheduleDto` structure — this
> is a separate mechanism for auto-running the query itself. In exports it is always `null`.

---

## 4. roleGroups

### 4.1 Export shape

`rep-objects.json → .roleGroups` is an **array** of `RoleGroupDto`. This is the only DTO in the section that
does **NOT** inherit `AbstractSecuredDto` (`RoleGroupDto.java` implements `Serializable`) — it has just three
fields:

```json
{ "id": "<numeric string>", "name": "<string>", "roles": ["<ReportRole>", ...] }
```

### 4.2 Worked example — a `Manager` group

A project-defined group in `rep-objects.json → .roleGroups[]`:

```json
{
  "id": "<group-id>",
  "name": "Manager",
  "roles": [
    "REPORT_VIEW", "REPORT_VIEW_ANY", "REPORT_EDIT", "REPORT_EDIT_ANY",
    "SCHEDULER_VIEW", "SCHEDULER_VIEW_ANY", "SCHEDULER_EDIT", "SCHEDULER_EDIT_ANY",
    "SOURCE_VIEW", "SOURCE_VIEW_ANY", "SOURCE_EDIT", "SOURCE_EDIT_ANY",
    "STORE_EXECUTE", "STORE_EXECUTE_ANY", "FILE_STORAGE_VIEW", "FILE_STORAGE_EDIT",
    "PROJECT_VIEW", "PROJECT_EDIT", "ORGANIZARIONS_VIEW", "ORGANIZATIONS_EDIT",
    "OYO_PROJECT_CONFIGURATION"
  ]
}
```

### 4.3 Field-by-field

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `id` | String (numeric) | Internal group ID (Keycloak/RDBMS). Referenced by `userRoleGroupAssignments.roleGroupId` | yes | — | `RoleGroupDto.id` |
| `name` | String | Group name. `@NotBlank`. Import matches groups **by name** (`findGroupByName`), not by `id` | yes | — | `RoleGroupDto.name` |
| `roles` | List<enum `ReportRole`> | Set of roles. `@NotNull` | yes | — | `RoleGroupDto.roles` |

### 4.4 `ReportRole` — the full list of canonical role constants (31 values)

```
ADMIN, NCT_AUTHOR,
REPORT_VIEW, REPORT_VIEW_ANY, REPORT_EDIT, REPORT_EDIT_ANY,
SCHEDULER_VIEW, SCHEDULER_VIEW_ANY, SCHEDULER_EDIT, SCHEDULER_EDIT_ANY,
SOURCE_VIEW, SOURCE_VIEW_ANY, SOURCE_EDIT, SOURCE_EDIT_ANY,
STORE_EXECUTE, STORE_EXECUTE_ANY,
FILE_STORAGE_VIEW, FILE_STORAGE_EDIT,
PROJECT_VIEW, PROJECT_EDIT,
ORGANIZARIONS_VIEW, ORGANIZATIONS_EDIT,           // ORGANIZARIONS_VIEW — typo in enum, canonical
ROLE_GROUP_VIEW, ROLE_GROUP_CREATE, ROLE_GROUP_EDIT, ROLE_GROUP_DELETE,
USER_VIEW, USER_CREATE, USER_EDIT, USER_DELETE,
OYO_PROJECT_CONFIGURATION
```

Each constant is bound to one or more `ProjectType` (`ORGANIZATION_MANAGER`,
`PRODUCTS_MANAGER`, `REPORT`) — e.g. `REPORT_VIEW` only for `REPORT`, `USER_VIEW` for all three.

### 4.5 Default groups

`empty` carries 2 groups: **`Author`** (26 roles: `NCT_AUTHOR` + REPORT/SCHEDULER/SOURCE/STORE/FILE +
ROLE_GROUP_* + USER_* + `OYO_PROJECT_CONFIGURATION`, but **without** `ADMIN`) and **`Developer`** (the same + `ADMIN`).
They are created automatically on import if they do not already exist
(`CmsProjectServiceImpl.createRoleGroupIfNotExists("Author"/"Developer", …)`), so they need not be put in the
export — but it is safer to include them. On top of those two, a project adds
one group per business role it needs to gate on — e.g. `Front Office Employee`, `Credit Analyst`,
`Warehouse Clerk`, `Customs Declarant`, `Approver` — and the same names are then used in
`userRoleGroupAssignments` and in any `service.security.hasAnyRoleGroup("…")` check.

---

## 5. userRoleGroupAssignments

### 5.1 Export shape

`rep-objects.json → .userRoleGroupAssignments` is an **array** of three-field objects
(`CmsProjectServiceImpl.UserRoleGroupAssignment`, static class):

```json
{ "userId": "<user external id (uuid)>", "roleGroupId": "<group id>", "roleGroupName": "<group name>" }
```

### 5.2 Worked example — one user in several groups

`rep-objects.json → .userRoleGroupAssignments`:

```json
[
  { "userId": "2ad2c4a6-e438-4f19-90fa-405174c5c93a", "roleGroupId": "987", "roleGroupName": "Front Office Employee" },
  { "userId": "2ad2c4a6-e438-4f19-90fa-405174c5c93a", "roleGroupId": "981", "roleGroupName": "Author" }
]
```

One row per (user, group) pair — a user who belongs to several groups appears several times with the same
`userId` and different `roleGroupName`s.

### 5.3 Field-by-field

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `userId` | String (UUID) | User external ID. On import, looked up via `userClient.getByExtIdBackend(userId)` | yes | — | `UserRoleGroupAssignment.userId` |
| `roleGroupId` | String | Group ID (for reference; **not used** for matching on import) | yes | — | `UserRoleGroupAssignment.roleGroupId` |
| `roleGroupName` | String | Group name. Import finds the target group **by this** (`findGroupByName`) | yes | — | `UserRoleGroupAssignment.roleGroupName` |

### 5.4 Import (`CmsProjectServiceImpl.java`)

Import groups assignments by `userId`, for each user looks it up by external ID
(`userClient.getByExtIdBackend`), then each group by **name**
(`nctRoleGroupService.findGroupByName(roleGroupName)`), collects a list of `RoleGroupDto` and calls
`userClient.updateByBackend(...)`. If the user is not in the target realm or no group with that
name is found — the assignment is silently skipped (log `warn`). So:
- The user must **already exist** in the target organization/project (users are not created via `.mrjun` — only
  bindings are transferred).
- The target group is matched **by `roleGroupName`**, so the names in `roleGroups` and in
  `userRoleGroupAssignments` must agree.

---

## 6. settings

### 6.1 What it is

`rep-objects.json → .settings` is an **array** of `SettingsDto`. This is the **external** (extracted from the
content tree) configuration store for the table-shaped plugins — one `type` literal per plugin:
`crud.table.plugin` → `"CrudTable"`, `crud.tree.plugin` → `"CrudTree"`, `process.table.pluin` → `"ProcessTable"`.
The mechanism: the plugin on saving settings takes `settingsName = getContent().getUniqueIdentifier()` (the unique
ID of its own content-tree node) and writes `SettingsDto{ name = uniqueIdentifier, type = "CrudTable", content = {...} }`
(`CrudTablePlugin.java`).

**The settings entry is a MIRROR, not the render source.** On render each table plugin
(`CrudTablePlugin`/`CrudTreePlugin`/`ProcessTablePlugin`) reads its config from its OWN node — the
`properties.model` slot — never from `settings[]`. The mirror holds the same JSON, written on save, and is read
only by (a) the author-side settings panels and (b) the form-navigation path (`FormPlugin` +
`SettingsNavigationHelper` + `SettingsActionLoader` + `FormGroupLandingPlugin`), which resolves the action and
breadcrumb of a form opened from that table by `settings[].name == node.uniqueIdentifier`. **Author BOTH:** with no
`properties.model` the table renders unconfigured; with no mirror it renders fine, but a form opened from one of its
row/create actions gets no action context (no entity load, no create/edit mode, no `onBeforeStart`/`onBeforeComplete`
rule) and the author-side settings panel opens empty.

**The link to check first:** every `settings[].name` you author must be found verbatim as the `uniqueIdentifier` of a
`crud.table.plugin` / `crud.tree.plugin` / `process.table.pluin` node in `branches.json`. The invariant is
**directional** — node → mirror, not the reverse. A leftover mirror matching no node is inert (the importer tolerates
it, and the baseline ships some) — do not "repair" it by inventing nodes.

The full semantics of the `content` fields for CrudTable — in [04-crud-table-plugin.md](04-crud-table-plugin.md);
for CrudTree and ProcessTable — in [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md). Here we
describe only the `SettingsDto` **envelope**.

### 6.2 Export shape

```
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid — ID of the settings object itself>",
  "creationTime": "<ISO>", "modificationTime": "<ISO>",
  "name": "<uniqueIdentifier of the CrudTable/CrudTree/ProcessTable node>",
  "type": "CrudTable" | "CrudTree" | "ProcessTable",
  "content": { ... plugin-specific JSON ... },
  "deleted": false
}
```

### 6.3 Worked example — a `CrudTable` settings

An entry of `rep-objects.json → .settings[]` with `type == "CrudTable"`:

```json
{
  "identifier": "f901f2da-850b-4e28-9e8a-39d73a81f713",
  "realmName": "<realm>",
  "clientName": "<client>",
  "name": "13c2b389-a7ec-4b63-9d8b-f285b55569fc",
  "type": "CrudTable",
  "content": {
    "crudAlias": "customer_types_cruid",
    "editActions": {
      "actions": [
        { "id": "90642377-df9e-4fee-84d3-fec0da25b4da", "icon": "pe-7s-edit",
          "name": "Edit Customer Type", "direct": false,
          "formGroupIdentifier": "00109d57-1e86-40c0-8035-a9f9125eec97",
          "predicateIdentifier": null, "onBeforeStartRuleIdentifier": null,
          "onBeforeCompleteRuleIdentifier": null } ]
    },
    "rowsPerPage": 15,
    "createActions": {
      "actions": [
        { "id": "c2e5687b-ea58-45fe-bf95-e32b64fde211", "icon": "pe-7s-play",
          "name": "New Customer Type", "direct": false,
          "formGroupIdentifier": "00109d57-1e86-40c0-8035-a9f9125eec97",
          "predicateIdentifier": null, "onBeforeStartRuleIdentifier": null,
          "onBeforeCompleteRuleIdentifier": null } ]
    },
    "columnSettings": [
      { "id": "fc9e6ad2-b4b5-4ba9-8f9f-0907febc7bd6", "name": null,
        "dataClass": "java.lang.String",
        "localizedNames": { "en_US": "Customer Type", "hy_AM": "Հաճախորդի տիպը" },
        "fieldExpression": "customerType" } ],
    "filterSettings": [],
    "contextIdentifier": "871f974f-e775-401a-adfc-e822110f3b99"
  },
  "deleted": false
}
```

A `ProcessTable` envelope looks the same from the outside — see `empty/rep-objects.json → .settings[]` with
`type=="ProcessTable"`; its `content` contains `globalActions`/`indexSettings`/`columnSettings`/`filterExpression`/
`workflowIdentifier`/`processGroupIdentifier`/`userStartProcessActions` (see docs 05/07).

### 6.4 Field-by-field (envelope)

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `identifier` | String (UUID) | ID of the settings object itself | yes | — | `AbstractSecuredDto.identifier` |
| `name` | String (UUID) | The **`uniqueIdentifier` of the** CrudTable/CrudTree/ProcessTable node whose config it stores | yes | — | `SettingsDto.name`; written as `getContent().getUniqueIdentifier()` (`CrudTablePlugin.java`) |
| `type` | String | `"CrudTable"` \| `"CrudTree"` \| `"ProcessTable"` (string literal, not enum) — must match the plugin, or the form-navigation lookup and the settings panel miss it | yes | — | `SettingsDto.type`; literal `.type("CrudTable")` (`CrudTablePlugin.java`), `.type("CrudTree")` (`CrudTreePlugin.java`) |
| `content` | ObjectNode (JSON) | Plugin-specific config (columns/actions/filters/…) | yes | — | `SettingsDto.content` |
| `deleted` | Boolean | Soft-delete flag | no | `false` | `SettingsDto.deleted` |

### 6.5 How many settings objects to expect

**At most one per table node** — author exactly one mirror for every `crud.table.plugin` / `crud.tree.plugin` /
`process.table.pluin` node you add, with `name` = that node's `uniqueIdentifier` and the matching `type`.
**The total will NOT equal the node count in a real export**, so do not use the count as a check: the baseline
`empty` project ships 2 `process.table.pluin` nodes but 3 `ProcessTable` settings — one matched, one node with no
mirror at all (it renders fine from its `properties.model`), and two orphan mirrors whose `name` appears nowhere in
`branches.json` (the residue of deleted nodes). Orphans are harmless and importer-tolerated; leave them alone.
The node → mirror direction is the one that matters, and it is checked by eye or by `mrjun.py validate`'s
mirror warning — which is deliberately silent about baseline-inherited nodes and about orphans, so a clean
`validate` is not proof that the mirrors are complete.

---

## 7. mailTemplates

> Sending mail from these templates, PDF templates and the Groovy flow "generate a PDF from a template → attach to mail"
> — covered in detail in [15-pdf-and-mail.md](15-pdf-and-mail.md). Here — only the export schema of `mailTemplates[]` itself.

### 7.1 Export shape

`rep-objects.json → .mailTemplates` is an **array** of `MailTemplateDto`:

```
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid>",
  "creationTime": "<ISO>", "modificationTime": "<ISO>",
  "name": "<string>",
  "alias": "<string — programmatic key>",
  "subject": "<string, with {{placeholder}}>",
  "htmlContent": "<full email HTML, with {{placeholder}}>",
  "cssContent": "<CSS | null>",
  "gjsData": "<JSON string of the GrapesJS model | null>",
  "placeholders": ["<name>", ...],
  "active": true,
  "description": "<string>"
}
```

### 7.2 Worked example — `Company Invitation` (a system template, HTML abbreviated)

`empty/rep-objects.json → .mailTemplates[]` with `alias == "companyInvitation"`:

```json
{
  "identifier": "8d6c2727-eb0f-4929-8bf2-822e0aedad10",
  "realmName": "<realm>",
  "clientName": "<client>",
  "name": "Company Invitation",
  "alias": "companyInvitation",
  "subject": "You've been invited to {{companyName}}",
  "htmlContent": "<!DOCTYPE html>\n<html lang=\"en\">... Hi {{firstName}}, ... {{companyName}} ... href=\"{{invitationLink}}\" ...</html>",
  "cssContent": null,
  "gjsData": null,
  "placeholders": ["firstName", "companyName", "invitationLink"],
  "active": true,
  "description": "Sent when a user is invited to join a company"
}
```

A template edited in the GrapesJS editor additionally carries `cssContent` and `gjsData` (a JSON string of the
editor model). The canonical example is the system template **`sendIntakeInit`** (`name:"sendIntakeInit"`,
`alias:"sendIntakeInit"`), which ships in `empty`: its
`gjsData` contains the full GrapesJS component tree, and `htmlContent` is the markup rendered from it with
`id` attributes (`ico2`, `ilwgt`, …) and `style="box-sizing: border-box;"`. Assets (images) are referenced as
`t/<tenant-slug>/mail-templates/<uuid>.png` — a path
in `tenant-files/`. ⚠️ The middle segment is the slug of the **source** tenant, which is **not** simply
`<realm>-<client>`: a template can carry one realm/client pair in its DTO fields while its asset path spells a
different tenant slug. Copy the path exactly as it appears; do not "reconstruct" it from realm and client.

### 7.3 Field-by-field

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `identifier` | String (UUID) | Template ID | yes | — | `AbstractSecuredDto.identifier` |
| `name` | String | Display name | yes | — | `MailTemplateDto.name` |
| `alias` | String | Programmatic key by which the template is invoked from a rule/integration (`companyInvitation`, `passwordRecover`, `userRegistration`, `sendIntakeInit`) | yes | — | `MailTemplateDto.alias` |
| `subject` | String | Email subject; supports `{{placeholder}}` | yes | — | `MailTemplateDto.subject` |
| `htmlContent` | String | Full HTML of the body; `{{placeholder}}` substituted at runtime | yes | — | `MailTemplateDto.htmlContent` |
| `cssContent` | String\|null | Separate CSS (if the template is from the GrapesJS editor) | no | null | `MailTemplateDto.cssContent` |
| `gjsData` | String\|null | JSON string of the GrapesJS model (component/style/asset tree). Needed only for editing, not for sending | no | null | `MailTemplateDto.gjsData` |
| `placeholders` | List<String> | Names of available placeholders (without curly braces) | no | null | `MailTemplateDto.placeholders` |
| `active` | Boolean | Whether the template is active | no | null | `MailTemplateDto.active` |
| `description` | String | Description | no | null | `MailTemplateDto.description` |

### 7.4 Default templates

The baseline carries **5 templates**: the three auto-seeded system ones — `Company Invitation`
(`companyInvitation`), `Password Recovery` (`passwordRecover`), `User Registration` (`userRegistration`) — plus
`sendIntakeInit` (`sendIntakeInit`, the only one with `gjsData`+`cssContent`) and `Event Reminder`
(`eventReminder`). Since `empty` is the Step-2 baseline, all 5 **already exist** — they need not be built anew;
project templates are simply added on top. (Only the three system ones are guaranteed in an arbitrary project;
check before assuming any other alias resolves.)

Placeholders of the system templates: `{{firstName}}`, `{{lastName}}`, `{{companyName}}`, `{{invitationLink}}`,
`{{resetLink}}`, `{{activationLink}}`.

> ⚠️ The obsolete concept doc `notification.md` describes email as `service.mail.send([to,subject,content])`
> with a raw `MailDto` — this does NOT match the code. The real mail system is **template-driven**: templates in
> `mailTemplates[]` + `{{placeholder}}` substitution + GrapesJS. There is no confirmed `service.mail.send` API with a
> map argument in the code.

---

## 8. project.settings.plugin (NOT a rep-object)

The content-tree node `project.settings.plugin` (`branches.json`, `ProjectSettingsPlugin.java`) is a
**project-settings UI panel**, not a configuration store. Its `properties` contain only
the standard slots `className` / `styleName` / `tagProperties`, and for all three the `stringValue` is empty (`""`) —
**the node stores no project config**. At runtime the panel reads/writes tenant-level config (branding, layout,
localization, import/export, appearance, AI) via services, not via the node:

```json
{ "pluginName": "project.settings.plugin",
  "identifier": "995825bd-dabb-4c5a-9bb0-5b322c965934",
  "name": "Project Settings",
  "properties": {
    "className":     { "propertyType": "STRING", "stringValue": "" },
    "styleName":     { "propertyType": "STRING", "stringValue": "" },
    "tagProperties": { "propertyType": "STRING", "stringValue": "" }
  } }
```

Panel sections (`ProjectSettingsPlugin.createSectionPanel`): `BRANDING`, `IMPORT_EXPORT`, `LAYOUT`,
`TEMPLATE_MANAGEMENT`, `GENERAL`, `LOCALIZATION`, `INTEGRATIONS`, `APPEARANCE`, `AI`. It is from here that
the `.mrjun` export itself is launched (the Import/Export button, `AJAXDownloadBehaviour` →
`projectService.exportProjectOrTemplate(tenant())`, `ProjectSettingsPlugin.java`). For building a project
via export files, **this node is simply copied as-is** (empty config) — there is nothing
to construct in it. How to build pages in general — see [01-content-model-and-pages.md](01-content-model-and-pages.md).

> **Tenant-level project quotas — `QuotaConfig`.** Separate from this UI node, a project carries a tenant-level
> `QuotaConfig` (`nct-transfer/.../dto/QuotaConfig.java`) with four caps: `maxEmailsPerDay`, `maxActiveProcesses`
> `maxUsersPerProject`, `maxSchedulersPerProject`. It is **not** part of the `.mrjun` export, but it is
> enforced at runtime — e.g. the scheduler cap rejects a create/import once reached (§3.3).

---

## 9. Placeholders / FieldType reference

A placeholder in SQL is a JSON fragment that `PlaceholderProcessorServiceImpl` parses into a `Replacement`:

```
{name: 'paramName', type: 'sqlType', defaultValue: '...', dropDownPopulation: {...}}
```

`Replacement` (`Replacement.java`): `name`, `defaultValue`, `type`
`dropDownPopulation`. Of the four keys, only `name`+`type` actually appear in generated-CRUD SQL
(the rest are for report/chart parameter UI).

**Two different type sets:**

**(A) Raw SQL types of the dynamic-CRUD generator** (what you write in `crud_*` queries):
`integer`, `string`, `jsonb`, `boolean`, `instant`, `bigdecimal`, `date`. Resolved by the CRUD path, NOT by
`FieldType.findByName`.

**(B) `FieldType` enum** (`FieldType.java`) — for report/chart parameters. Each constant =
`ENUM(name, controlType, javaClass[, initialModelClass])`:

| Constant | name | controlType | javaClass | findByName aliases |
|---|---|---|---|---|
| `STRING` | `string` | text | String | — |
| `INTEGER` | `number` | number | Integer | `integer`, `int` |
| `LONG` | `number` | number | Long | `long` |
| `FLOAT` | `number` | number | Float | `float` |
| `DOUBLE` | `number` | number | Double | `double` |
| `BIG_DECIMAL` | `number` | number | BigDecimal | `bigdecimal`, `decimal` |
| `SHORT` | `number` | number | Short | `short` |
| `DATE` | `date` | text | LocalDate | — |
| `DATE_RANGE` | `date-range` | text | LocalDateRange / LocalDate | — |
| `TIME` | `time` | time | LocalTime | — |
| `DATE_TIME` | `datetime` | text | LocalDateTime | — |
| `DATE_TIME_RANGE` | `datetime-range` | text | LocalDateTimeRange / LocalDateTime | — |
| `DROPDOWN_STRING` | `dropdown-string` | text | String | — |
| `DROPDOWN_INSTANT` | `dropdown-instant` | text | Instant | — |
| `CHECKBOX` | `checkbox` | checkbox | Boolean | `bool`, `boolean` |

`findByName(name)` (`FieldType.java`): first an exact match on `name`, then a switch on aliases,
otherwise `null`. The commented-out ones (**do NOT document as available**): `TIME_RANGE`, `TIME_INTERVAL`,
`DATE_INTERVAL`, `DATE_TIME_INTERVAL`.

> ⚠️ `jsonb`/`instant`/`bigdecimal` from set (A) are **not** `FieldType.name` values — in
> generated-CRUD SQL they are raw SQL types. Do not confuse the two sets.

---

## 10. dropDownPopulation & cascading dropdowns

`DropDownPopulation` (`DropDownPopulation.java`) populates a report/chart dropdown parameter from one of
three sources:

| Field | Type | Mode |
|---|---|---|
| `query` | String | Populate from a **named query** (by `name`) |
| `rest` | String | Populate from a **REST endpoint** |
| `restKey` | String | Key in the REST response from which to take values |
| `choices` | List<`DropDownValDto`> | **Static** list of `{name, value}` |
| `name` | String | Display name |
| `value` | Object | Current/default value |

Three modes: **query** (`query:"MyQuery"`), **REST** (`rest:"https://…"` + `restKey`), **static**
(`choices:[{name,value},…]`). Cascading dropdowns (Country→State→City) are built by chaining: the selection in one
parameter is passed as a parameter into the next dropdown's query.

> ⚠️ **In export queries of dynamic CRUD, `dropDownPopulation` is NOT used** — it never appears in a
> generated `crud_*` query; it lives in the report/chart parameter-builder UI. This section is not needed for a
> DYNAMIC-CRUD build; it is here for completeness.

---

## 11. Aggregations

`QueryAggregationsDto` (`QueryAggregationsDto.java`) — three fields:

```json
{ "aggregations": [ { "aggCol": "amount", "as": "total", "aggType": "SUM" } ],
  "groupByList": [ { "col": "category" } ],
  "orderByList": [ { "col": "total" } ] }
```

| Field | Type | Meaning | Backing |
|---|---|---|---|
| `aggregations` | List<`Aggregation`>\|null | Aggregate functions. `Aggregation = {aggCol, as, aggType}` | `QueryAggregationsDto.aggregations` |
| `groupByList` | List<`GroupBy`> | GROUP BY. `GroupBy = {col}` | `QueryAggregationsDto.groupByList` |
| `orderByList` | List<`OrderBy`> | ORDER BY. `OrderBy = {col}` | `QueryAggregationsDto.orderByList` |

`AggregationType` (`AggregationType.java`) — **exactly five** values: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`.

> ⚠️ The obsolete `query-system.md` uses the form `[type:"SUM", field:"amount"]` and the type `GROUP_BY` — **neither
> exists**. The keys are `aggCol`/`as`/`aggType` (not `type`/`field`); GROUP BY is a separate
> `groupByList:[{col}]`, not an aggregation type. In generated CRUD queries `aggregations` is always the empty
> skeleton `{aggregations:null, groupByList:[], orderByList:[]}`.

---

## 12. RIMM & service.rimm (lookup tables)

**RIMM** (Runtime Information Management Module, `nct-rimm`) — dynamically created PostgreSQL
lookup tables (`rimm_*`) powering fast dropdown/reference lookups. Example: the query `Countries`
(`empty`) = `select * from rimm_country;` (in the export with newlines). Besides the shared lookups, a project's
dump can also contain a per-project RIMM table named `rimm_<realm>_<client>`.
The RIMM source is stored in `project-db-meta.json.rimmSourceIdentifier` and **is not put in the `.sources` export**
(see §2.4). Table operations (doc-claimed, endpoints `⚠️ UNVERIFIED`):
`POST /api/rimm/create-table`, `/upsert-row`, `/delete-row`; upsert = `INSERT … ON CONFLICT (key) DO UPDATE`.
Confirmed services: `RimmTableService(Impl)`, `RimmSchemaService(Impl)`, `RimmSecurityTableService(Impl)`,
`RimmDatabaseUserService(Impl)`, `SecuritySyncService(Impl)` in `nct-rimm`.

**Calling from rules** — via `service.rimm` = `RimmServiceProxy` (`RimmServiceProxy.java`; realm+client
are injected internally, they are NOT passed in the script):

```groovy
service.rimm.query("Rimm User Start With")
service.rimm.query("Rimm User Start With", [term: 'ann'])
service.rimm.query([name: 'Countries'])   // map form
service.rimm.run(request)   // QueryByNameRequest
service.rimm.run([name: 'Countries', parameters: [:], itemsPerPage: 100, offset: 0, aggregations: null])
```

They return `List<Object>` (each = a key/val row). `QueryByNameRequest`
(`nct-transfer/.../dto/QueryByNameRequest.java`): `name` (`@NotBlank`), `offset` (default `0L`),
`itemsPerPage` (default `100L`, getter fallback `20L` if null), `parameters` (Map),
`aggregations` (`QueryAggregationsDto`). **No top-level `limit`** — pagination via `offset`+`itemsPerPage`.

> ⚠️ The obsolete `07-query-and-rimm.md` shows `rimmService.run(realm, client, [...])` with realm/client —
> that is the signature of the **raw** `RimmService`, not the Groovy-facing `service.rimm`. In rules, do NOT
> pass realm/client. The rule-side operator DSL (`$eq/$ne/$gt/$gte/$lt/$lte/$in/$nin/$regex`) is `⚠️ UNVERIFIED`
> against the RIMM impl; verify before using.

---

## 13. Notifications (service.notification)

`service.notification` in Groovy = `PushNotificationProxy` (`PushNotificationProxy.java`; realm+client
are injected, they are NOT passed in the script). Full set of methods:

| Method | Returns | Signature (Groovy) | Line |
|---|---|---|---|
| `sendText` | void | `(userEmail, message)` | |
| `sendDownloadable` | void | `(userEmail, message, fileName, downloadUrl)` | |
| `sendAlert` | void | `(userEmail, title, message)` | |
| `sendWarning` | void | `(userEmail, title, message)` | |
| `sendError` | void | `(userEmail, title, message)` | |
| `sendReminder` | void | `(userEmail, title, description, dueDate)` | |
| `sendTextToRoleGroup` | int | `(roleGroupName, message)` | |
| `sendAlertToRoleGroup` | int | `(roleGroupName, title, message)` | |
| `sendWarningToRoleGroup` | int | `(roleGroupName, title, message)` | |
| `sendErrorToRoleGroup` | int | `(roleGroupName, title, message)` | |
| `sendReminderToRoleGroup` | int | `(roleGroupName, title, description, dueDate)` | |
| `sendTextToRole` | int | `(roleName, message)` | |
| `sendAlertToRole` | int | `(roleName, title, message)` | |
| `sendWarningToRole` | int | `(roleName, title, message)` | |
| `sendErrorToRole` | int | `(roleName, title, message)` | |
| `sendReminderToRole` | int | `(roleName, title, description, dueDate)` | |

The bulk variants (`…ToRole`/`…ToRoleGroup`) return `int` — the number of recipients. The raw interface —
`PushNotificationService` (`nct-executor/.../service/PushNotificationService.java`), where each signature
starts with `(realm, client, …)`. Notification types: TEXT / ALERT / REMINDER; alert severities:
INFO / WARNING / ERROR / CRITICAL. The Groovy binding `notification` is registered in
`HintsService.java` (`serviceMap.put("notification", …)`).

> ⚠️ The fluent chain `.correlationId(...)` from `notification.md` is `⚠️ UNVERIFIED`: the methods return
> `void`/`int`, such a chain would not compile.

---

## 14. REST endpoints

`QueryController` (`nct-query/.../controller/QueryController.java`, `@RequestMapping("/api/reports/query")`):

```
POST /tenant/{realm}/{client}/save
POST /internal/tenant/{realm}/{client}/save
GET  /tenant/{realm}/{client}/findByRealmNameAndClientName
GET  /internal/tenant/{realm}/{client}/findByRealmNameAndClientName
POST /tenant/{realm}/{client}/delete
POST /internal/tenant/{realm}/{client}/delete
GET  /tenant/{realm}/{client}/findByIdentifier/{identifier}
POST /tenant/{realm}/{client}/run
POST /tenant/{realm}/{client}/{queryName}/internal/runByName
POST /tenant/{realm}/{client}/internal/runByQuery
POST /tenant/{realm}/{client}/{queryName}/runByName
POST /tenant/{realm}/{client}/findControls
POST /internal/tenant/{realm}/{client}/removeCache
POST /tenant/{realm}/{client}/deleteAll
POST /internal/tenant/{realm}/{client}/deleteAll
```

Neighboring controllers for source/schema discovery: `SourceDatabaseController`, `DatabaseController`,
`DatabaseInternalController`, `SchemaInternalController`, `ChartReplacementController` (in `nct-query`).
For a DYNAMIC-CRUD build via export files, REST is not needed — it is for runtime/UI; the list is given for completeness.

---

## 15. findControls → replaceParams pipeline

`PlaceholderProcessorServiceImpl` (`nct-query/.../service/`) processes placeholders in two phases:

1. **`findControls(QueryDto)`** → `List<FieldControl>` for the UI: parses each `{…}` fragment into a
   `Replacement{name, defaultValue, type, dropDownPopulation}`, from which a parameter-input form is built.
2. **`replaceParams(QueryDto)`** → substitutes values into the SQL: numbers — raw; strings — in single
   quotes; `null` → an always-true sentinel comparison (a fixed literal compared against itself, so the
   predicate neutralises itself rather than becoming `= NULL`); range (DATE_RANGE/…) → `BETWEEN`.
   Before running through the JSQLParser AST, placeholders are replaced with temporary RAND+sequence tokens (so
   the parser does not trip over `{…}`).

There is no literal regex Pattern constant in `PlaceholderProcessorServiceImpl` — the syntax `{name:'…',type:'…'}`
is parsed in code; the types/syntax documented here match what the platform actually emits (see §1.4, §9).

---

## How to construct from scratch

Below are recipes that give exact JSON. For a DYNAMIC project, the main work is queries + one INTERNAL source;
the rest is copied from `empty`.

### Recipe A — INTERNAL source for the business schema

Add exactly one object to `rep-objects.json → .sources`:

```json
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "11111111-1111-1111-1111-111111111111",
  "creationTime": "2026-01-01T00:00:00Z", "modificationTime": "2026-01-01T00:00:00Z",
  "name": "my_schema",
  "description": "Internal schema: my_schema",
  "hostName": "<db-host>",
  "port": 5432,
  "dbName": "prj_<realm>_<client>",
  "schemaName": "my_schema",
  "userName": "prj_<realm>_<client>_user",
  "password": "placeholder-will-be-overwritten",
  "dbType": "POISTGRESQL",
  "sourceType": "INTERNAL"
}
```

Remember the `identifier` — it will go into every query.`sourceIdentifier` and into CRUD.`sourceIdentifier`
(`dynamic-cruds.json`). Import will overwrite `hostName`/`dbName`/`userName`/`password` — only
`identifier`, `schemaName`, `sourceType`, `dbType`, `port` matter. The table schema under this source is built via
Database Management — see [10-database-management.md](10-database-management.md).

### Recipe B — SQL query for a CRUD method

For each SQL method of a CRUD (`find`/`findAll`/`count`/`get`/`create`/`update`/`delete`, see
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)) create a query in
`rep-objects.json → .queries`:

```json
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "22222222-2222-2222-2222-222222222222",
  "creationTime": "2026-01-01T00:00:00Z", "modificationTime": "2026-01-01T00:00:00Z",
  "name": "crud_<alias>_findAll",
  "query": "SELECT * FROM <table> WHERE 1=1 ORDER BY id LIMIT {name: 'rowsInPage', type: 'integer'} OFFSET ({name: 'pageNumber', type: 'integer'} * {name: 'rowsInPage', type: 'integer'})",
  "sourceIdentifier": "11111111-1111-1111-1111-111111111111",
  "offset": 0,
  "itemsPerPage": 20,
  "parameters": {},
  "attributes": {},
  "aggregations": { "aggregations": null, "groupByList": [], "orderByList": [] },
  "wrapInPaging": null,
  "statementTimeoutSeconds": null,
  "schedule": null,
  "lastScheduledTime": null,
  "hidden": null
}
```

Method↔query correspondence rules:
- `query.identifier` = method.`queryIdentifier` (and method.`script` duplicates the same SQL) — see doc 11.
- `query.sourceIdentifier` = the `identifier` of your source from Recipe A.
- `query.name` is **unique** and follows the convention `crud_<alias>_<method>`.
- Placeholder names `{name: 'X', ...}` = the `parameterName` of the method's parameters (`rowsInPage`/`pageNumber`
  for paging; columns — for `create`/`update`; `id` — for `get`/`delete`).
- The placeholder `type` — the raw SQL type of the column (`integer`/`string`/`jsonb`/`boolean`/`instant`/`bigdecimal`/`date`, see §1.4/§9).
- The fields `offset:0`, `itemsPerPage:20`, `parameters:{}`, `attributes:{}`, `aggregations` (empty),
  `wrapInPaging:null`, `schedule:null` — copy verbatim.

### Recipe C — settings envelope for a CRUD table

A CRUD table renders from its own node (`properties.model` of the `crud.table.plugin` node in `branches.json`);
this settings object is the MIRROR of that same JSON, and it is what the form-navigation path reads (§6.1). Author
it **in addition to** `properties.model`, never instead of it — add to `rep-objects.json → .settings`:

```json
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "33333333-3333-3333-3333-333333333333",
  "creationTime": "2026-01-01T00:00:00Z", "modificationTime": "2026-01-01T00:00:00Z",
  "name": "<uniqueIdentifier of the crud.table.plugin node from branches.json>",
  "type": "CrudTable",
  "content": { "crudAlias": "...", "contextIdentifier": "...", "rowsPerPage": 15,
               "columnSettings": [...], "createActions": {"actions":[...]},
               "editActions": {"actions":[...]}, "filterSettings": [] },
  "deleted": false
}
```

Key points: `name` = the `uniqueIdentifier` of the table node; `content` = byte-for-byte the same JSON you put in
that node's `properties.model`; `type` = `"CrudTable"` for `crud.table.plugin`, `"CrudTree"` for
`crud.tree.plugin`, `"ProcessTable"` for `process.table.pluin`. Populating `content` — see docs 04/05.

### Recipe D — role group + user assignment

`rep-objects.json → .roleGroups` (a user group):

```json
{ "id": "9001", "name": "My Group",
  "roles": ["NCT_AUTHOR","REPORT_VIEW","REPORT_EDIT","USER_VIEW"] }
```

`rep-objects.json → .userRoleGroupAssignments` (binding an existing user):

```json
{ "userId": "<external user uuid>", "roleGroupId": "9001", "roleGroupName": "My Group" }
```

`roleGroupName` must match the group's `name` (import matching is by name). The user must already
exist in the target organization.

### Recipe E — mail template

`rep-objects.json → .mailTemplates`:

```json
{ "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "44444444-4444-4444-4444-444444444444",
  "creationTime": "2026-01-01T00:00:00Z", "modificationTime": "2026-01-01T00:00:00Z",
  "name": "My Notification", "alias": "myNotification",
  "subject": "Hello {{firstName}}",
  "htmlContent": "<!DOCTYPE html><html><body>Hi {{firstName}}</body></html>",
  "cssContent": null, "gjsData": null,
  "placeholders": ["firstName"], "active": true,
  "description": "My custom notification" }
```

`gjsData`/`cssContent` can be left `null` — they are needed only for re-editing in
GrapesJS; sending uses `htmlContent`+`subject`. The 5 baseline templates already exist in `empty`
(`companyInvitation`, `passwordRecover`, `userRegistration`, `sendIntakeInit`, `eventReminder`) — do not
duplicate them; a second template with the same `alias` is dropped on import with only a log warning (§7.4).

### Recipe F — schedulers

Usually not needed. If you need a cron trigger for a rule, add an object to `rep-objects.json → .schedulers` per
the §3.1 schema (live examples are rare, but the shape is **confirmed field-for-field**
against `ScheduleEntity`/`ScheduleDto` — see §3.1). Remember: a scheduler runs a **rule** (`actionType=RUN_RULE`),
not a query; the predicate must be a `PREDICATE` rule and the action an `EXECUTION_RULE` (§3.2). What that action
rule receives at tick time — and why it must fetch its own rows — is §3.2c; if it starts a process, the whole chain
plus the mandatory idempotency guard is [27-event-driven-process-start.md](27-event-driven-process-start.md).

> ⚠️ **Build safety:** if you set `enabled:true` and a valid `job.expression`, the import **auto-registers a live
> `CronTrigger` and starts firing the action rule immediately** (`CmsProjectServiceImpl.java` →
> `SchedulerServiceImpl.save` → `cronService.registerSchedule`). Author `enabled:false` unless the trigger is
> meant to be live on import — see §3.3.

---

## Gotchas

1. **`DbType.POISTGRESQL` — the typo is canonical.** The enum constant is named exactly `POISTGRESQL`
   (with "I" after "PO"), see `DbType.java`. In JSON it is always `"dbType": "POISTGRESQL"`. Do not "fix" it —
   the import will fail. There is no MySQL/Oracle/SQLServer/Snowflake (the obsolete `data-source.md` made them up).
2. **`ORGANIZARIONS_VIEW` — also a canonical typo** in `ReportRole` (`ORGANIZARIONS_VIEW`, but
   `ORGANIZATIONS_EDIT`). Write it verbatim.
3. **`process.table.pluin` — a typo in the plugin name** (`pluin`, not `plugin`). But the settings.`type` for
   it is the correct `"ProcessTable"`.
4. **The RIMM source is not put in the export.** Import filters sources by `!name.startsWith("RIMM_")`
   (`CmsProjectServiceImpl.java`) and recreates RIMM with a new `identifier`. Meanwhile the default RIMM queries
   in the export still reference the **old** RIMM `identifier` — so in `empty` the query `sourceIdentifier`
   (`b814d61d…`) and `project-db-meta.json.rimmSourceIdentifier` legitimately **differ**, which is exactly what
   demonstrates the remapping on import. This works thanks to `rimmSourceIdentifier` + the import logic. Do not
   add a RIMM source to `.sources` manually, and do not "fix" the mismatch.
5. **INTERNAL source credentials are ignored on import.** `userName`/`password`/`hostName`/`dbName` of INTERNAL
   are rewritten to the assigned project-level role. Whatever `password` secret sits in the export is unused.
   Set any non-empty values.
6. **`query.parameters` ≠ SQL parameters.** SQL parameters live right in the `query` text as
   `{name: 'x', type: 'y'}`. The `parameters` field (Map) is saved *values* for preview/charts; for
   CRUD methods it is **always `{}`**. And it is `query`/`sourceIdentifier`, not `sql`/`dataSource`.
7. **`settings.name` is the node's `uniqueIdentifier`, not a human-readable name.** Both are UUIDs, easy
   to confuse with `settings.identifier` (the ID of the settings object itself). `name` must match exactly the
   `uniqueIdentifier` of the CrudTable/CrudTree/ProcessTable node in `branches.json`, otherwise the mirror is inert:
   the table still renders (it renders from `properties.model`), but forms opened from its actions lose their
   action/breadcrumb context and the author-side settings panel opens empty (§6.1).
8. **`RoleGroupDto` does not inherit `AbstractSecuredDto`** — it has only `id`/`name`/`roles`, without
   `identifier`/`realmName`/creationTime. Do not add extra fields.
9. **`userRoleGroupAssignments` does not create users.** Via `.mrjun` only the bindings are transferred;
   the user itself must already be in the target organization, otherwise the assignment is silently skipped.
   Group matching is by `roleGroupName`, not by `roleGroupId`.
10. **`schedulers` is empty in most exports**, but the §3.1 schema is **confirmed field-for-field**
    against `ScheduleEntity` (`rep_schedule`; `job`/`cooldownJob` are `jsonb`) and `ScheduleDto` — not a guess. Query
    `schedule` is also always `null`. A scheduler runs a rule, not a query (there is no `queryIdentifier`). **Importing
    an `enabled:true` scheduler with a valid cron starts firing its action rule immediately** (§3.3).
11. **`id` is always `null` in the export**, `identifier` is a stable UUID. Do not fill in `id` when building
    (`CmsProjectServiceImpl.java` resets it before export).
12. **`project.settings.plugin` stores nothing** — it is only a UI panel. When building, copy its node
    as-is (empty `properties`).
13. **The 5 mail templates already exist in `empty`.** `Company Invitation`/`Password Recovery`/`User Registration`/
    `sendIntakeInit`/`Event Reminder` come with the baseline — do not construct them again, add only your own.
14. **Aggregations: only `COUNT/SUM/AVG/MIN/MAX`.** The form is `Aggregation={aggCol,as,aggType}`; GROUP BY is a
    separate `groupByList:[{col}]`, not `aggType`. No `{type,field}`/`GROUP_BY` (the obsolete
    `query-system.md`).
15. **Do not pass realm/client from rules.** `service.rimm.*` and `service.notification.*` inject
    realm+client inside the proxy. Signatures with realm/client from the old `07-query-and-rimm.md` are the raw
    services, not the Groovy binding.
16. **The audit API (`service.audit.*`) is `⚠️ UNVERIFIED`.** No binding was found in the code; `audit-logging.md`
    describes it as aspirational. Do not rely on it when building.
