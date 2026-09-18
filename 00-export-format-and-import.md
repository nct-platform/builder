# Export/Import & the `.mrjun` anatomy

> 📐 **Field evidence — what four deliveries actually shipped:** [README.md](references/README.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / When to use

`.mrjun` is a **ZIP archive of an entire project** on the platform (Dokie / NCT / mrjun). It can be
*exported* from authoring and *imported* back, yielding a working project (pages, forms,
CRUD logic, a DB schema with data). This document is a **map**: it describes every file inside the archive,
its exact JSON schema, the order of export and import operations, id remapping, and the precise difference between
**static** and **dynamic** integration at the file level.

Read this document first. Every other doc hangs off it: the contents of `branches.json`
are covered in [01-content-model-and-pages.md](01-content-model-and-pages.md), `dynamic-cruds.json` —
in [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md), `project-db.dump` —
in [10-database-management.md](10-database-management.md), `rep-objects.*` — in
[06-form-groups-and-mapping.md](06-form-groups-and-mapping.md),
[07-workflows-and-tasks.md](07-workflows-and-tasks.md),
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md),
[12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).

We document **DYNAMIC** integration. Differences in the **static** style are noted
explicitly, but the target build scenario is dynamic. A breakdown of the two styles is in
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md); the master build is
[13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md).

> **🔧 Tooling.** For these entities, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of manually
> editing JSON: `unpack <f.mrjun> <dir>`, `pack <dir> <f.mrjun>`, `inspect`, `validate`.
> The full index and rules are in [`tools/README.md`](tools/README.md); before re-importing, always run
> `mrjun.py validate`.

> **⚠️ Two owners.** The base export layer (`tenant.json`, `branches.json`, `branch-metadata.json`, the zip
> itself) belongs to the **mrjun CMS library** the platform embeds; everything else (`rep-objects`,
> `project-db.dump`, `dynamic-cruds`, favicon, tenant-files) belongs to the **Dokie application** (`nct-*`).
> That is why component names below carry an `mrjun-`/`nct-` prefix — it tells you which side owns a behaviour
> when you report a bug.

> **⚠️ Key precondition (see Gotcha #12): the export and restore of `rep-objects`/DB work
> only for projects with the tenant property `type == REPORT`.** A populated `rep-objects` plus a DB riding
> in the dump is itself evidence that the source project was a REPORT project. If the target tenant on
> import is **not** REPORT, the entire `rep-objects`/DB block is silently skipped, and only
> `roleGroups`/`mailTemplates`/`pdfTemplates` are restored. When building by hand, target a REPORT tenant.

---

## Export shape — what's inside the archive

`.mrjun` is a flat ZIP (entries relative to the root, no nested wrapper folder: in `compress` each
file is placed under `sourceDir.relativize(file)`,
`mrjun .../util/ZipCompressUtils.java`). After unpacking:

```
<archive>/
  tenant.json              ← base layer (mrjun)
  branches.json            ← base layer (mrjun) — content trees of the branches
  branch-metadata.json     ← base layer (mrjun)
  rep-objects.json         ← nct-ui: rules, forms, contexts, queries, source, roles, mail, etc.
  project-db.dump          ← nct-ui: JSON dump of the PRIMARY project DB (nct-jdbc-dump-v1 format)
  project-db-<db>.dump     ← nct-ui: dump of each ADDITIONAL distinct CRUD-source DB (multi-source projects)
  project-db-meta.json     ← nct-ui: {databaseName (primary), databases:[…all], schemaPrefix, rimmSourceIdentifier} for remapping
  dynamic-cruds.json       ← nct-ui: DYNAMIC ONLY — CRUD business-logic definitions
  integrations.json        ← nct-ui: the execution-platform integrations (the `bl` deployable and any other)
  favicon/                 ← nct-ui: favicon assets (tenant/{id}/favicon/*)
  tenant-files/            ← nct-ui: tenant files (t/{id}/*: logos, avatars, etc.)
```

Always present: `tenant.json`, `branches.json`, `branch-metadata.json`, `rep-objects.json`,
`favicon/`, `tenant-files/`. Conditional:

- `dynamic-cruds.json` **may be absent** (static only, or the project has no dynamic CRUD, or `bl` is not
  deployed — `CmsProjectServiceImpl.java`).
- `integrations.json` is present when the project has integrations — and the bundled baseline already carries
  one (the **Business Logic** integration). ⛔ **Keep it.** The import is two-pass: the integrations are
  recreated and started FIRST, because importing `dynamic-cruds.json` binds each dynamic CRUD to a **running**
  integration. Drop this file from a hand-assembled archive and the dynamic CRUDs have nothing to bind to.
- `project-db.dump` + `project-db-meta.json` are present when at least one project DB is dumpable. The export
  now dumps the **DISTINCT UNION** of the primary project DB (`projectDatabaseName`) **and every dynamic-CRUD's
  own `sourceDb`** (`CmsProjectServiceImpl.writeOtherFilesToExportFolder`): the first → `project-db.dump`, each
  additional distinct source DB → `project-db-<db>.dump`, and `project-db-meta.json.databases[]` lists them all.
  This fixed the old data-loss bug where an export whose tenant snapshot lacked `projectDatabaseName` (async/tag
  export) — or whose CRUDs lived under a non-main source — fell through to the row-by-row `rimm-data.json` export,
  which dumps ONLY the RIMM schema and so shipped `tables:[]` (all CRUD data gone). `rimm-data.json` (legacy) is
  now a **last resort** only when nothing is dumpable. A healthy export therefore always carries
  `project-db.dump` **and** `project-db-meta.json` together — if you see `rimm-data.json` instead, the dump path
  failed and data is missing.

**⚠️ The `type==REPORT` gate.** The contents of `rep-objects.json` (`sources`, `queries`, `schedulers`,
`workflows`, `rules`, `contexts`, `formGroups`, `forms`, `settings`, `processGroups`) are assembled
**only** inside `if (ProjectType.REPORT.equals(projectType))` (`CmsProjectServiceImpl.java`, where
`projectType = ProjectType.valueOf(tenant.getProperty("type"))`). If the tenant type is not
REPORT, all of these keys are exported as **empty arrays**; only `roleGroups`,
`userRoleGroupAssignments`, `mailTemplates` and `pdfTemplates` are assembled unconditionally. So a `rep-objects.json` that is
populated at all came from a REPORT-type tenant — and an all-empty one is the first symptom to check.

**⚠️ A malformed rep-object aborts the whole import — same symptoms as a non-REPORT target.** Even against a REPORT
tenant, if any rep-object fails Jackson deserialization while reading `rep-objects.json`, the exception aborts the
entire REPORT-path block (`CmsProjectServiceImpl.initAllObjects` → `readOtherFilesFromFolder`): **contexts,
sources, and `project-db.dump` are all skipped**, and the dynamic-CRUD replay (a separate `bl/execute/importCruds`
path) still runs. Because ONE bad object skips the WHOLE block, the symptoms are **scattered and data-shaped, not
error-shaped** — they show up together:

| Symptom (in the app / business-logic UI) | Actually caused by |
|---|---|
| "No source selected" in Business Logic; sources list empty | the source rep-object was never saved |
| The project's context (whatever you named it) shows **no CRUDs**; rules fail at runtime with `No CRUD found with alias X in context Y` | **Two causes.** (a) the context rep-object (its `crudAliases`) was never saved — cruds carry **no** context reference, so `crudAliases` is the ONLY crud↔context link (see [08](08-groovy-rules-and-context.md)). (b) **the dominant cause even for a byte-correct export:** the import STRIPPED `crudAliases`. Each dynamic-CRUD delete/recreate fires `crud.unregister` → `removeCrudAliasFromAllContexts`, and `crud.register` never re-adds; the inline import path self-heals (`CmsProjectServiceImpl`) but the pass-2 `importDynamicCrudsOnly` (the orchestrator REIMPORTING stage — every empty→dynamic and every re-import) historically did NOT, leaving `crudAliases=[]`. **Fix:** re-save the context in the Contexts UI (writes `crudAliases` straight to the entity), or import on a build where `importDynamicCrudsOnly` snapshots+restores `crudAliases`. Do NOT "fix" the export — the linkage is already correct. |
| All data / dates "gone" | `project-db.dump` was not restored |

All three at once ⇒ suspect **one deserialization abort**, not three separate bugs; find the Jackson stack in
`log/ui.log` (`Cannot deserialize … from …`). The gotcha we actually hit: `rep-objects.settings[].content` is a
Jackson **`ObjectNode` (JSON object)**, NOT a string — a JSON *string* there throws `MismatchedInputException:
Cannot deserialize ObjectNode from String value` (chain `Qss["settings"]->SettingsDto["content"]`). It is
the exact inverse of the node's `properties.model.stringValue`, which IS a string. **The failure is only visible in
`log/ui.log`**, not in `mrjun.py validate` output (validate now ERRORs on a string `content` AND on any rep-object
field that is a string where the same field is an object/array elsewhere — but it does not deserialize into the
DTOs, so a live import + `log/ui.log` scan remains the real test). Don't be misled by `Saved Context … {id}` — that
log prints the DB **id** (freshly assigned; `id=null` on export), not the `identifier`, which is preserved. Prefer
`mrjun.py node set-model`/`patch-model` — they keep the `settings[]` mirror in sync as an object.

### File write order on export

1. **mrjun `exportProjectOrTemplate`** (`mrjun .../ProjectServiceImpl.java`):
   creates a temp folder (`UUID`), writes `tenant.json`, `branches.json`, `branch-metadata.json`,
   then calls the hook `writeOtherFilesToExportFolder(tenant, folder)`, then
   `ZipCompressUtils.compress` (inside the export pipeline).
2. **nct-ui `writeOtherFilesToExportFolder`** (`CmsProjectServiceImpl.java`) appends into the same
   folder: `rep-objects.json`, `project-db.dump` + `project-db-meta.json`
   `tenant-files/`, `favicon/`, `dynamic-cruds.json`.

---

## Per-file reference

### 1. `tenant.json`

Project metadata. Built by `copyTenantForExport`
(`mrjun .../TenantServiceImpl.java`) — takes only `name, alias, description,
domain, status, importedFrom, locales, defaultLocale, icon` (id, owner, publishedBranchId, etc. are **not**
exported). The `template` method does **not** copy explicitly — `template:false` in the export is always a
hardcoded default `new TenantDomain()` (not the source tenant's value); import overwrites it with
`isTemplate` anyway (`ProjectServiceImpl.java`). A populated project's `tenant.json`:

```json
{"name":"Trade Finance","alias":"tradefin","description":"Trade finance back office",
 "domain":"acme.tradefin","status":"published","template":false,
 "importedFrom":[],"locales":["en_US","hy_AM"],"defaultLocale":"en_US"}
```

Empty baseline (`initialtemplates/empty.mrjun` → `tenant.json`) — same shape; the concrete
`name`/`alias`/`domain` in the bundled copy are the source tenant's and carry no meaning for you:

```json
{"name":"emp","alias":"emp","description":"emp","domain":"acme.emp","status":"published",
 "template":false,"importedFrom":[],"locales":["en_US","hy_AM"]}
```

⚠️ The bundled baseline carries **no `defaultLocale` key** — its source tenant had none and the serializer skips
nulls. That is not evidence the field is unsupported: add it yourself (`mrjun.py locale set-default`).

| Field | Type | Meaning | Required | Default |
|---|---|---|---|---|
| `name` | string | Project name. **Overwritten on import** by the `projectName` parameter (`ProjectServiceImpl.java` `tenant.setName(projectName)`) | yes | — |
| `alias` | string | Project URL alias; part of schema names (`rimm_<realm>_<client>`, the system schema) | yes | — |
| `description` | string | Description | no | — |
| `domain` | string | Domain `<realm>.<client>` (e.g. `acme.tradefin`) | yes | — |
| `status` | string | Status; forced to `published` on import (`ProjectServiceImpl.java` `setStatus(TenantStatus.published...)`) | no | `published` |
| `template` | boolean | Overwritten on import by the `isTemplate` flag (`setTemplate(isTemplate)`) | no | false |
| `importedFrom` | array | Import history | no | `[]` |
| `locales` | string[] | Project locales (`en_US`, `hy_AM`, `ru_RU`…). Always read on import (`setLocales(...)`) | yes | — |
| `defaultLocale` | string | The project's DEFAULT/authoritative locale (`Locale.toString()`, e.g. `hy_AM`). Exported and applied on import, but only when it is one of `locales`; absent ⇒ consumers fall back to `locales[0]`. Author it with `mrjun.py locale set-default` — see [20-localization.md](20-localization.md) | no | — |
| `icon` | string | Icon | no | null |

### 2. `branch-metadata.json`

```json
{"publishedBranchName":"master","totalBranches":1}
```

| Field | Type | Meaning |
|---|---|---|
| `publishedBranchName` | string | Name of the published branch; on import selects the published branch by name (`ProjectServiceImpl.java`) |
| `totalBranches` | int | Branch count |

Published-branch selection logic on import (`determinePublishedBranchId`,
`ProjectServiceImpl.java`): first by the name from the metadata → otherwise the `master` branch
→ otherwise the first one. A single-branch project — the normal case — is
`{"publishedBranchName":"master","totalBranches":1}`.

### 3. `branches.json` — an **array** of branches

Written as `gson.toJson(clonedBranches)` (`ProjectServiceImpl.java`). Each branch is a serialization of
`BranchDomain`. Branch keys:

```json
{ "name": "master", "tenantId": 1, "virtualPlugins": [ ... ],
  "rootContent": { ... recursive content tree ... },
  "globalAssets": { "version": 3, "storageId": "…", "folders": [ ... ], "assets": [ ... ] } }
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Branch name (`master`) |
| `tenantId` | int | id of the source tenant. **Overwritten on import** with the new one (`ProjectServiceImpl.java` `br.setTenantId(tenant.getId())`) |
| `virtualPlugins` | array | Shared/reusable plugins (layout HTML, headers/footers). On import marked `virtualContent=true` recursively. The count **depends on the project** — an empty admin scaffold already ships about twenty, and a built project adds its own. See [01-content-model-and-pages.md](01-content-model-and-pages.md) |
| `rootContent` | object | **Recursive content tree** — all of the project's pages/plugins |
| `globalAssets` | object | *Optional.* The project's own files — js, css, html, fonts, images — in ONE folder tree; a script or a stylesheet in it can be switched on and then loads on every page. Links and metadata only: the bytes are in `tenant-files/webassets/<storageId>/`, and each BRANCH owns its own `storageId`. Absent means the project has none. See [29-global-resources.md](29-global-resources.md) |

**Content-tree node** (recursive, `rootContent` and each `children[]` element). The
scalar fields of a root node:

```json
{ "id": "d353a128-82bc-48ea-970a-a852f04b0ef4",
  "identifier": "34c97297-185b-41b7-a255-f37895984a1c",
  "uniqueIdentifier": "1fff8460-c128-4af7-82cb-9695008a9267",
  "name": "Home", "pluginName": "siteMapPage",
  "order": 0, "isBehaviour": false, "active": true,
  "includedInParsis": false, "virtualContent": false,
  "branchId": "d6e40fea-c1fe-4e97-a57d-26613a804675",
  "children": [ ... one node per top-level page ... ],
  "properties": { ... },
  "roleAccess": { ... },
  "treeDisabled": ..., "treeOpened": ..., "treeSelected": ..., "childPluginAdded": ... }
```

`pluginName` selects the plugin (`siteMapPage`, `crud.table.plugin`,
`dynaform.form.rimm.drop.down.field.plugin`, `nct.html.plugin` …; the full catalog of 65 real
names is in [01-content-model-and-pages.md](01-content-model-and-pages.md), keep the real misspelling
`process.table.pluin`). **All configuration is in `properties`**, where the actual config is a JSON string in
a typed slot:

- **Form controls** (`dynaform.form.*.field.plugin`) → `properties.settings.stringValue`.
- **Table plugins** (`crud.table.plugin`, `crud.tree.plugin`, `process.table.pluin`) →
  `properties.model.stringValue` (**not** `settings`!).
- **Tabs** (`nct.tab.plugin`) → `properties.tabModel.stringValue`.
- **Filter form** (`dynaform.filter.form.plugin`) → `properties.filterFormModel.stringValue`
  (present only in projects that actually use a filter form).
- **Left-nav / kicker** (`site.kicker.plugin`) → `properties.modelGroups.stringValue`.
- **Chart** (`chart.js.plugin`) → `properties.Javascript.stringValue`.
- Any node also has the slots `className`, `styleName`, `tagProperties` (usually empty).

The full node model, `properties`, `roleAccess`, `virtualContent`/parsis and the per-plugin breakdown are in
[01-content-model-and-pages.md](01-content-model-and-pages.md) and
[02-form-controls-reference.md](02-form-controls-reference.md). Table plugins (`model.stringValue`) —
in [04-crud-table-plugin.md](04-crud-table-plugin.md),
[05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md). Here we note only that this is a
base (mrjun) file and node ids are **not** remapped on import — they are preserved as-is
(`branchService.saveAll(branches)`, `ProjectServiceImpl.java`).

### 4. `project-db-meta.json`

Metadata for DB remapping on import. Written in `CmsProjectServiceImpl.java`:

```json
{"databaseName":"org_<realm>_<hash>",
 "databases":["org_<realm>_<hash>"],
 "schemaPrefix":"<realm>_<client>_<hash>",
 "rimmSourceIdentifier":"74f8ea9d-9e06-4a05-9f89-3144d3321e18"}
```

| Field | Type | Meaning | Required |
|---|---|---|---|
| `databaseName` | string | Name of the donor's project DB. On the current storage model one database holds a whole **organisation** and each project is a set of prefixed schemas inside it, so this is an org-level name — not `prj_<realm>_<client>`. Used to remap `dbName` in source rows and to locate the RIMM schema in the dump | yes |
| `databases` | array | every database the archive carries a dump for (a multi-source project has more than one) | yes |
| `schemaPrefix` | string | **the DONOR's schema prefix.** This is the single field that tells the import which of the dump's schemas belong to this project; the import renames each one into the RECIPIENT's own prefix. A schema you add to the dump by hand must carry it. Absent only for a legacy donor whose schemas were unprefixed — the import then infers the prefix from the dump's own `_system`/`_rimm`/`_data` names | yes, whenever the dump's schemas are prefixed |
| `rimmSourceIdentifier` | string(uuid) | identifier of the RIMM-source source. Written **only if** a RIMM source was found (`CmsProjectServiceImpl.java` `if (rimmSource != null)`). On import, old `query.sourceIdentifier == this` → remapped to the new RIMM source | no (only if a RIMM source exists) |

See [10-database-management.md](10-database-management.md) §"Import-time source materialization" — the two
sections describe one file and must not drift.

**⚠️ DB staging requires BOTH files.** `readOtherFilesFromFolder` puts the dump in file storage and
sets the tenant properties `initProjectDbDumpPath`/`initProjectDbMeta` only when
`projectDbDump.exists() && projectDbMeta.exists()` (`CmsProjectServiceImpl.java`, the `&&` operator).
If at least one is absent — the DB is **not** staged and not restored. When building by hand, write
`project-db.dump` and `project-db-meta.json` as a pair.

### 5. `project-db.dump` — the `nct-jdbc-dump-v1` format

A JSON dump of the project DB (**not** a `pg_dump` binary; a custom JSON format). Written as bytes via
`databaseClient.dumpDatabase(...)` → `dumpDatabaseAsJson`
(`ProjectDatabaseServiceImpl.java`). Top level:

```json
{ "format": "nct-jdbc-dump-v1",
  "database": "prj_<realm>_<client>",
  "schemas": [ { schemaDump }, ... ] }
```

Each `schemaDump` — keys in **this insertion order**: `name`, `enumTypes`
`foreignKeys`, `uniqueConstraints`, `checkConstraints`, `indexes`, `tables`, `sequences`, `views`,
`functions`, `triggers`. Empty example (the `public` schema, which is always empty in an export):

```json
{ "name": "public", "enumTypes": [], "foreignKeys": [], "uniqueConstraints": [],
  "checkConstraints": [], "indexes": [], "tables": [], "sequences": [],
  "views": [], "functions": [], "triggers": [] }
```

#### Schemas that make it into the dump

All DB schemas are dumped, **except** `information_schema`, `pg_catalog`, `pg_toast`, `pg_%`
(`ProjectDatabaseServiceImpl.java`) and except `excludeSchemas` passed by the export.
`excludeSchemas` is populated with the schemas of `INTEGRATION`/`SYSTEM` sources
(`CmsProjectServiceImpl.java`) — they are recreated on the target side and don't ride in the dump.
The tables `users`, `role_groups`, `users_has_role_groups` (`KAFKA_MANAGED_TABLES`) are skipped at the
table/FK/index level — they are recreated by
`rimmSchemaClient.createSchemaSync` on import.

Schema sets you can expect (inspect any dump with `jq -r '.schemas[]|.name'`):

| Project kind | Schemas in the dump |
|---|---|
| Empty baseline | `<prefix>_data`, `<prefix>_rimm` — **both empty** |
| **DYNAMIC** build | the **business schema** (`<prefix>_<your name>`) with tables/sequences/FKs, one `<prefix>_<hash>` per dynamic-integration, `<prefix>_rimm` (a few lookup tables), `<prefix>_data`(empty). The registry `<prefix>_system` is deliberately EXCLUDED from the export |
| **STATIC** build | only `<prefix>_<hash>` integration schemas (large, FK-heavy — Hibernate-generated) and an empty `<prefix>_rimm` — **no business schema** |

`<prefix>` throughout is `project-db-meta.json.schemaPrefix`. Older archives predating the org-per-database
model carry unprefixed `public` / `rimm_<realm>_<client>` / `system_<realm>_<client>` instead; the import
handles both.

**The key static ↔ dynamic difference at the dump level** (see §Static vs Dynamic below):
in a dynamic project the business schema (tables *with data*) rides **inside the dump**; in a static project
there is no business schema — only `int_*` (schemas of INTERNAL/INTEGRATION sources) and an empty
`rimm_*`, because the business logic is compiled Java `@Crud` beans in a separate
microservice, not tables in the project DB.

#### `enumTypes[]`

`{"name": "<typname>", "labels": ["a","b",...]}`. Created BEFORE tables. Usually empty.

#### `tables[]` — element (example: a lookup table `app_schema.dim_invoice_status`)

```json
{ "name": "dim_invoice_status",
  "ddl": "CREATE TABLE \"app_schema\".\"dim_invoice_status\" (\n  \"id\" smallint NOT NULL DEFAULT nextval('app_schema.dim_invoice_status_id_seq'::regclass),\n  \"code\" VARCHAR(30),\n  \"label\" VARCHAR(60),\n  \"sort_order\" smallint DEFAULT 0,\n  \"is_active\" boolean DEFAULT true,\n  \"localized\" jsonb,\n  PRIMARY KEY (\"id\")\n)",
  "columns": ["id","code","label","sort_order","is_active","localized"],
  "columnTypes": [5,12,12,5,-7,1111],
  "rows": [ {"id":"1","code":"draft","label":"Draft","sort_order":"1","is_active":"true","localized":null}, ... ],
  "rowCount": 5 }
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Table name (without schema) |
| `ddl` | string | Full `CREATE TABLE "schema"."table" (...)` with the schema-qualified name |
| `columns` | string[] | Column names (order from `ResultSetMetaData`) |
| `columnTypes` | int[] | JDBC `java.sql.Types` codes for each column (5=SMALLINT, 12=VARCHAR, -7=BIT/boolean, 1111=OTHER/jsonb) |
| `rows` | `Array<Map<string,string\|null>>` | Data; **all values are strings** (`val.toString()`), null is preserved as `null` |
| `rowCount` | int | `rows.size()` |

Tables are dumped in FK dependency order (`getTablesInDependencyOrder`).

#### `sequences[]` — element

```json
{ "name": "dim_invoice_status_id_seq", "dataType": "bigint",
  "startValue": "1", "increment": "1", "lastValue": 1 }
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Sequence name |
| `dataType` | string | Type (`bigint`, etc.) |
| `startValue` | string | Start value |
| `increment` | string | Increment |
| `lastValue` | long | Current `last_value` (restored via `setval(...,true)`) |

#### `foreignKeys[]`, `uniqueConstraints[]`, `checkConstraints[]`, `indexes[]`

Arrays of **ready-made DDL strings** (`ALTER TABLE ... ADD CONSTRAINT ...` / `CREATE INDEX ...`).
Applied AFTER tables and data. Examples:

```
foreignKeys[0]: ALTER TABLE "app_schema"."invoices" ADD CONSTRAINT "invoices_status_id_fkey" FOREIGN KEY ("status_id") REFERENCES "app_schema"."dim_invoice_status"("id")
indexes[0]:     CREATE INDEX idx_payments_invoice_id ON app_schema.payments USING btree (invoice_id)
```

| Array | String format |
|---|---|
| `foreignKeys` | `ALTER TABLE s.t ADD CONSTRAINT c FOREIGN KEY (col) REFERENCES s.rt(rc)` |
| `uniqueConstraints` | `ALTER TABLE s.t ADD CONSTRAINT c UNIQUE (cols)` |
| `checkConstraints` | `ALTER TABLE s.t ADD CONSTRAINT c CHECK (clause)` (except `%_not_null`) |
| `indexes` | raw `indexdef` from `pg_indexes` (excluding PK/unique-constraint indexes) |

#### `views[]`, `functions[]`, `triggers[]`

```
views[]:     {"name": "<view>", "definition": "<view_definition>"}
functions[]: {"name": "<name>", "definition": "<pg_get_functiondef>"}
triggers[]:  ["<pg_get_triggerdef>", ...]
```

Empty in practically every project. A detailed breakdown of the DB schema, DDL auto-generation and the Database
Management plugin — in [10-database-management.md](10-database-management.md).

### 6. `rep-objects.json` — object (`Qss` wrapper)

All project objects except content and DB. Serialized as `Qss`
(`CmsProjectServiceImpl.java`, fields in this order). 14 keys, **all always present**
(may be empty arrays):

```
sources, queries, schedulers, workflows, rules, contexts, formGroups, forms,
settings, processGroups, roleGroups, userRoleGroupAssignments, mailTemplates, pdfTemplates
```

(`pdfTemplates[]` — element `PdfTemplateDto`, `id` nulled on export like the rest — is exported for **all**
project types, and imported for all types alongside `roleGroups`/`mailTemplates` (not gated on REPORT); see
[15](15-pdf-and-mail.md).)

**⚠️ Population is gated on `type==REPORT`.** `sources/queries/schedulers/workflows/rules/contexts/
formGroups/forms/settings/processGroups` are populated only if the tenant is REPORT-type
(`CmsProjectServiceImpl.java`, see §Export shape). `roleGroups`/`userRoleGroupAssignments`
`mailTemplates` are assembled for any type.

**⚠️ `id` is nulled, but the KEY IS PRESENT as `null`.** On export, each object gets
`it.toBuilder().id(null).build()`, which serializes the field as `"id": null` — the key is **not
removed**. Check it yourself on any export: `jq '.rules[0]|has("id")'` == `true`, `.rules[0].id` == `null`
(same for `queries`, `sources`, `forms`, and the nested `forms[].formGroup.id`). On import, ids
are regenerated. Relationships hold on **`identifier`** (the business key, a UUID). When building by hand, write
`"id": null` and fill in consistent `identifier`s.

**⚠️ forms filter + nested `formGroup.id=null`.** Forms export additionally:
(a) **drops** forms whose `formGroup.identifier` is non-null but is not among the exported
`formGroups` (a soft-deleted group); forms with `formGroup == null` or `formGroup.identifier == null`
are **kept** (`return true`) — so `forms.length` can be smaller than the number of authored
forms only because of forms with a "dangling" group; (b) nulls the nested `built.formGroup.id`
so import binds the form to the group by `identifier`, not by numeric id.

Sub-object schemas (verified by the SPEC, details in the topical docs):

| Key | Element shape (abbr.) | Topical doc |
|---|---|---|
| `sources` | `SourceDto`: `{id, identifier, name, sourceType, dbType, hostName, port, dbName, schemaName, userName, password, ...}` | [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) |
| `queries` | `{id, identifier, name, query, parameters, attributes, aggregations, sourceIdentifier, wrapInPaging, itemsPerPage, offset, schedule, statementTimeoutSeconds}` | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `schedulers` | `ScheduleDto` | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `workflows` | `{id, identifier, name, bpmnContent, elements, processDefinitionId, externalId, deployed, contextIdentifiers[]}` | [07-workflows-and-tasks.md](07-workflows-and-tasks.md) |
| `rules` | `{id, identifier, name, description, status, ruleType, executor, contextIdentifiers[], rule:{ruleScriptStr}, hidden, realmName, clientName, ...}` | [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) |
| `contexts` | `{id, identifier, name, alias, crudAliases[]}` | [08-...](08-groovy-rules-and-context.md) |
| `formGroups` | `{id, identifier, name, contentPageIdentifier, formGroupsPageIdentifier, contextIdentifiers[], predicateFormMapping, placeFormsNextToLanding}` | [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) |
| `forms` | `{id, identifier, name, formGroup, contentIdentifier, contextIdentifiers[], validators, actionValidators, hiddenConfigs, allowDrafts, multiLanguage}` | [06-...](06-form-groups-and-mapping.md) |
| `settings` | `SettingsDto` | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `processGroups` | `ProcessGroupDto` | [07-...](07-workflows-and-tasks.md) |
| `roleGroups` | `RoleGroupDto` (id is **not** nulled on export — the only exception to the id=null rule) | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `userRoleGroupAssignments` | `{userId, roleGroupId, roleGroupName}` | — |
| `mailTemplates` | `MailTemplateDto` | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `pdfTemplates` | `PdfTemplateDto` (`id` nulled on export; saved into nct-pdf on import for **all** project types) | [15-pdf-and-mail.md](15-pdf-and-mail.md) |

#### Rule types in rep-objects (all THREE are real)

`ruleType ∈ {EXECUTION_RULE, PREDICATE, VALIDATION_RULE}` with a 1:1 executor:
`EXECUTION_RULE→GroovyExecutionRule`, `PREDICATE→GroovyPredicate`,
`VALIDATION_RULE→GroovyValidationRule`. **VALIDATION_RULE does occur in real exports** — don't
assume it's absent just because a given project has none. EXECUTION_RULE dominates in every project;
PREDICATE follows; VALIDATION_RULE is the rarest of the three.

The breakdown of the three types, templates and context is in
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).

#### What drives the counts

Rather than memorising numbers, know what each list scales with — that is how you sanity-check your own export:

| Key | Scales with |
|---|---|
| `sources` | one INTERNAL source per business schema — often 0, because missing INTERNAL/RIMM source records are materialized on import |
| `queries` | **CRUDs × SQL methods** in a dynamic project (hundreds); a handful of hand-written ones in a static project |
| `schedulers` | scheduled queries only — usually 0 |
| `workflows` | one per BPMN process |
| `rules` | Groovy authored by hand; hidden CRUD-method rules are **excluded** |
| `contexts` | usually exactly 1 per project |
| `formGroups` / `forms` | the number of authored form pages |
| `settings` | one per settings-bearing plugin node |
| `processGroups` / `roleGroups` / `mailTemplates` | the baseline defaults plus whatever you add |
| `userRoleGroupAssignments` | number of users with an explicit role-group binding |

**Why a dynamic project has hundreds of queries**: every **SQL method** of a dynamic CRUD references a saved
`query`. With the standard method set (`findAll`, `count`, `get`, `create`, `update`, `delete`) that is
6 queries per CRUD, all named `crud_<alias>_<methodName>`; the Groovy `find` wrapper creates none.
So *queries ≈ CRUDs × 6* plus any hand-written ones. Breakdown in
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

**Hidden rules are absent from rep-objects**: the rules export filters out `hidden=true`, so `rules[]`
never contains one. Hidden Groovy rules of CRUD methods are **recreated** on
import separately (`ensureHiddenGroovyRule`, see §Import).

### 7. `dynamic-cruds.json` — **DYNAMIC only**

Present only if the system CRUD `bl` (dynamic-integration) is deployed and returned a non-empty
list (`CmsProjectServiceImpl.java`). Present in dynamic projects; **absent** in static ones and in the
empty baseline. Top level (`DynamicCrudsExport`):

```json
{ "exportVersion": 1, "cruds": [ { ExportedCrud }, ... ] }
```

`exportVersion` is `1`, and `cruds[]` holds one entry per CRUD. One full CRUD (`ExportedCrud`):

```json
{ "alias": "equipment_event_types_cruid",
  "name": "Equipment Event Types Cruid",
  "sourceIdentifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c",
  "sourceHost": "<db-host>",
  "sourcePort": 5432,
  "sourceDb": "prj_<realm>_<client>",
  "sourceSchema": "app_schema",
  "sourceUser": "prj_<realm>_<client>_user",
  "sourcePassword": "<generated-on-import>",
  "localizationField": "localized",
  "dtoFields": [ {"fieldName":"id","displayName":"id","fieldType":"Integer","fieldOrder":0},
                 {"fieldName":"equipmentEventType","displayName":"equipment_event_type","fieldType":"String","fieldOrder":1},
                 {"fieldName":"localized","displayName":"localized","fieldType":"ObjectNode","fieldOrder":4}, ... 5 fields ],
  "filterFields": [],
  "methods": [ {ExportedMethod}, ... 7 methods: find, findAll, count, get, create, update, delete ] }
```

| CRUD field | Type | Meaning |
|---|---|---|
| `alias` | string | Technical alias of the CRUD (`service.crud.<alias>`) |
| `name` | string | Human-readable name |
| `sourceIdentifier` | string(uuid) | identifier of the DB source. On import, **live** creds are taken from src_source by this |
| `sourceHost`/`sourcePort`/`sourceDb`/`sourceSchema`/`sourceUser`/`sourcePassword` | string/int | Copy of the connection (fallback if the source is not found) |
| `localizationField` | string | Localization column (`localized` jsonb). Set via `bl.setLocalizationField` |
| `dtoFields` | `ExportedField[]` | DTO fields |
| `filterFields` | `ExportedField[]` | Filter fields |
| `methods` | `ExportedMethod[]` | CRUD methods |

`ExportedField`: `{fieldName, displayName, fieldType, fieldOrder}`.

`ExportedMethod` — a SQL method (real `findAll`):

```json
{ "methodName": "findAll", "methodType": "SQL", "returnType": "Object",
  "returnsArray": true, "methodOrder": 0,
  "queryIdentifier": "5476804c-1e0c-4efc-af91-009b42c72609",
  "ruleIdentifier": null, "returnFields": null,
  "parameters": [ {"parameterName":"rowsInPage","parameterType":"Integer","parameterOrder":0},
                  {"parameterName":"pageNumber","parameterType":"Integer","parameterOrder":1} ],
  "script": "SELECT * FROM dim_equipment_event_types WHERE 1=1 ORDER BY id LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))" }
```

A Groovy method (real `find`):

```json
{ "methodName": "find", "methodType": "GROOVY", "returnType": "Object",
  "returnsArray": false, "methodOrder": -1,
  "queryIdentifier": null, "ruleIdentifier": null, "contextIdentifiers": null,
  "parameters": [ {"parameterName":"rowsInPage",...}, {"parameterName":"pageNumber",...} ],
  "script": "def filter = param ?: [:]\ndef countResult = service.crud.equipment_event_types_cruid.count()\n... return [content: rows, totalElements: total, totalPages: ..., pageNumber: pageNumber]\n" }
```

| Method field | Type | Meaning |
|---|---|---|
| `methodName` | string | Method name (`find`/`findAll`/`count`/`get`/`create`/`update`/`delete`) |
| `methodType` | `"SQL"`\|`"GROOVY"` | Implementation type |
| `script` | string | SQL with `:param` (SQL) or a Groovy body (GROOVY) |
| `returnType` | string | Usually `Object` |
| `returnsArray` | boolean | Returns an array (`findAll`=true) |
| `methodOrder` | int | Order; Groovy `find`=-1, SQL 0..N |
| `ruleIdentifier` | string(uuid)\|null | identifier of the method's hidden Groovy rule (null for SQL in the export; may be set for Groovy) |
| `queryIdentifier` | string(uuid)\|null | identifier of the saved `query` (SQL only) |
| `contextIdentifiers` | string[]\|null | Contexts of a Groovy method |
| `returnFields` | `Map<col,Type>`\|null | Map of returned fields |
| `parameters` | `ExportedParameter[]` | `{parameterName, parameterType, parameterOrder}` |

**Link SQL method ↔ query**: the method's `queryIdentifier` points to a `query` in `rep-objects.json` with
the name `crud_<alias>_<methodName>` and the same `sourceIdentifier`. Note: the method's `script`
uses the `:param` syntax, while `query.query` in rep-objects uses the `{name:'rowsInPage',
type:'integer'}` syntax. The linked query for the `findAll` above, in `rep-objects.json`:

```json
{ "identifier": "5476804c-1e0c-4efc-af91-009b42c72609",
  "name": "crud_equipment_event_types_cruid_findAll",
  "sourceIdentifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c",
  "itemsPerPage": 20,
  "query": "SELECT * FROM dim_equipment_event_types WHERE 1=1 ORDER BY id LIMIT {name: 'rowsInPage', type: 'integer'} OFFSET ({name: 'pageNumber', type: 'integer'} * {name: 'rowsInPage', type: 'integer'})" }
```

The full CRUD recipe (dtoFields, filterFields, the standard set of methods) —
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md); queries —
[12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).

### 8. `favicon/` and `tenant-files/`

Flat file trees (binaries). Export — `exportFilesRecursively`
(`CmsProjectServiceImpl.java`), import — `importFilesRecursively`.

- `favicon/` ← from the storage `tenant/{tenantId}/favicon`; on import placed in
  `tenant/{newTenantId}/favicon`. Several dozen files: `favicon.ico`
  `apple-icon.png`, `pwa-icon-*.png`, `favicon-16x16.png`, etc.).
- `tenant-files/webassets/<storageId>/` ← the project's own js, css, html, fonts and images, one subtree
  per BRANCH. Registered on the branch in `branches.json` → `globalAssets`; the two halves line up only
  because the registry stores the path RELATIVE to the tenant root — an absolute `t/{id}/…` survives the
  import unchanged and then reads, successfully, from the DONOR project. See
  [29-global-resources.md](29-global-resources.md)
- `tenant-files/` ← from `t/{tenantId}`; on import → `t/{newTenantId}`. Logos
  (`fixed/90-60/logo1.png`), the 404 image (`fixed/400-250/404.png`), avatars
  (`{id}/profile/camera_*.png`).

⚠️ `tenant-files/` sometimes contains a stray `project-db.dump` — an artifact of import staging:
`readOtherFilesFromFolder` temporarily puts the dump in `t/{tenantId}/project-db.dump`
(`CmsProjectServiceImpl.java`), and if the source tenant was itself imported the file lingers there. When building
by hand, `tenant-files/*.dump` files can be ignored.

### 9. `integrations.json` — the project's integrations, and the data sources they provide

An **array** of the project's execution-platform integrations. Written by
`CmsProjectServiceImpl.writeOtherFilesToExportFolder`, read on import by
`ProjectImportOrchestrationServiceImpl` (which recreates + starts them BEFORE `dynamic-cruds.json`
is replayed) and by `CmsProjectServiceImpl.bindIntegrationDataSources` (below).

```json
[{ "identifier": "5557500e-…",        // the DONOR's id — the target mints its own
   "name": "erp",                     // free text the author chose; reconciliation matches on it first
   "dockerImage": "dokie/erp",        // the integration TYPE; null for an external integration
   "version": null,                   // the import always runs the registry's "latest"
   "external": false,                 // true = the platform neither deploys nor owns its storage
   "serviceToken": "<service-token>", // external only
   "dbSchemaName": "int_<realm>_<client>_5557500e",             // the donor's data schema (informational)
   "dataSourceIdentifiers": ["d403c908-…"],              // ← the binding (see below)
   "dataSourceNames": ["<source-name>"] }]                // parallel array, for logs/diagnostics
```

#### `dataSourceIdentifiers` — how a statically integrated project keeps its charts alive

An internal integration keeps its data in a schema execution-platform creates **per project**
(`int_<realm>_<client>_<shortId>`) and its pod fills. Neither that schema nor its `INTEGRATION`
source row travels in the archive — both are rebuilt at the target (see §Export shape, Gotcha #9).
But queries and chart embeds select their database by `sourceIdentifier`, so without a record of
*which source rows meant "this integration's data"*, an imported project keeps pointing at the
donor's row: a database the target does not have, cannot reach, or — the failure nobody notices,
because nothing errors — has and is **empty**.

`dataSourceIdentifiers` is that record. The export fills it with every source whose `schemaName`
equals the integration's `dbSchemaName` — **except `SYSTEM` and `RIMM_` rows**, which the target
rebuilds for itself under a new identifier (this is what keeps a DYNAMIC integration out of it: it has
no schema of its own, it reuses the project's `system_<realm>_<client>`, whose row is `SYSTEM` and
holds only dynamic-integration's registry, never business data). **A hand-authored archive may declare
it itself** — the import treats the declaration, not the source row's type, as the link. On import, once the
integrations are reconciled and RUNNING, each declared identifier is bound to the target's own
integration source:

| in the target | what the import does |
|---|---|
| the row exists (it was exported as `EXTERNAL`/`INTERNAL`) | its **connection** (host, port, dbName, schemaName, user, password) is rewritten to the target's integration schema. Identifier, name and type are left alone, so every query, chart embed and CRUD that already names it follows along untouched |
| the row does not exist (the donor's was an `INTEGRATION` row) | it is **created under the same identifier**, `sourceType=INTEGRATION`, named `<integration>_data` |

The target integration is matched by **name**, then by **docker image** (its type — which is what
identifies it when the target created the integration by hand under another name), and finally, if
neither matches, by falling back to the project's **single** `INTEGRATION` source. With several and
no match it binds nothing rather than guess. Anything it cannot bind is recorded as an import error
("…has no running '<name>' to read it from") instead of finishing green over empty charts.

Nothing happens for an archive that declares nothing — every export written before this existed, **and
every purely dynamic project, whose `bl` integration reuses the SYSTEM schema and is therefore never
declared** — or for a project with no `INTEGRATION` source — an external integration owning its own database is a
legitimate deployment and keeps importing exactly as before. Idempotent.

> The same reconciliation-by-image rule stops a second pod: an archive whose internal integration
> the target already runs **under a different name** reuses that pod instead of creating a duplicate
> (two pods of one type answer the same CRUD aliases).

---

## How import restores it (operation order and id remapping)

The full import pipeline (after unpacking the ZIP):

**Phase A — base layer (mrjun `importProjectOrTemplate`, `ProjectServiceImpl.java`):**
1. Unpack the ZIP. ⚠️ Everything below assumes the upload was answered **Override**; an import into an existing
   project first raises a business-logic choice dialog, and **Ignore** strips `project-db.dump`,
   `project-db-meta.json`, `dynamic-cruds.json` and `integrations.json` out of the archive before this step —
   steps 4 and 12 then do nothing at all. **Rebuild** runs every step below, but drops each business schema
   instead of emptying it at step 4, and skips the integration teardown/recreate entirely. See Gotcha #19.
2. Read `tenant.json` → `TenantDomain`; take `locales`, overwrite
   `template=isTemplate`, `status=published`, `name=projectName`.
3. Call the hook `readOtherFilesFromFolder(tenant, folder, user)` — staging of nct-ui files
   into tenant properties (**the actual import of rep-objects/db/cruds is launched from here**, see phase B).
4. `tenantService.save(tenant, user)`.
5. Read `branches.json`, remove existing virtual plugins and branches, set
   `tenantId`/`virtualContent=true` recursively, `branchService.saveAll(branches)`.
   **Content node ids are NOT remapped.**
6. Determine the published branch from `branch-metadata.json` (`determinePublishedBranchId`).

**Phase B — nct-ui objects (`readOtherFilesFromFolder` → `initAllObjects`):**

`readOtherFilesFromFolder` (`CmsProjectServiceImpl.java`) reads `rep-objects.json` into
`tenant.property("initObjectsOnFirstLogin")`, puts `project-db.dump` into file storage +
the path into `initProjectDbDumpPath` and `project-db-meta.json` into `initProjectDbMeta` **only if both files
are present** (`&&`), stages `dynamic-cruds.json` into `initDynamicCrudsOnImport`, then
(for a non-admin realm) calls `initAllObjects(tenant, val, true, currentUser)`.

`initAllObjects` — the order. **⚠️ Step 1 and steps 3–9 are gated on `isReportProject`**
(`isReportProject = ProjectType.REPORT.equals(projectType)`; the gate opens before
`deleteAllProjectData` and wraps the whole restore of sources/DB/queries/rules/contexts/formGroups/forms/
settings/processGroups, and closes at the comment "End of isReportProject condition"). For a non-REPORT
tenant, only steps **10** (roleGroups), **11** (mailTemplates) and **PdfTemplates** below run.

1. `projectCleanupService.deleteAllProjectData` — cleanup (**isReportProject only**).
2. Parse `rep-objects.json` into `Qss`.
3. **Sources** (isReportProject): skip RIMM (`RIMM_`); remap `dbName` old DB → new;
   fetch the project-level Postgres role (creds are **not** rotated — taken from
   ProjectEntity); recreate the SYSTEM schema; rewrite INTERNAL sources to
   new creds; save.
4. **Restore the project DB** from `project-db.dump` (isReportProject): build the schema remap
   (`public→null` (skip); `rimm_<old>→rimm_<realm>_<client>`; **and `int_*`/`system_*`→null (skip)** unless the
   name is the target's own `system_<realm>_<client>` — a schema mapped to null is silently dropped, so a
   business schema must never carry those prefixes, see
   [10-database-management.md](10-database-management.md) §Export shape), call
   `databaseClient.restoreDatabase(...)` → `restoreDatabaseFromJson`
   (`ProjectDatabaseServiceImpl.java`). Each schema in its own transaction; the order within a schema:
   `CREATE SCHEMA` → enums → sequences → tables (DDL, then data) → `setval` sequences → unique →
   check → FK → indexes → views. Schema-qualified names in the DDL are rewritten
   on remap.
5. Recreate the security tables and the RIMM source: `rimmSchemaClient.createSchemaSync`
   `applyGrantsAfterImport`; `syncInternalSourceHosts`; delete the staged dump file.
6. **Queries** (isReportProject): remap `sourceIdentifier` old RIMM → new;
   save with `id(null)`.
7. **Workflows, rules, contexts** (isReportProject) — save with `id(null)`.
8. **FormGroups → forms** (isReportProject): save formGroups, build an `identifier→saved` map,
   rebind `form.formGroup` by identifier, save forms.
9. **Settings, processGroups** (isReportProject). End of the `isReportProject` block.
10. **RoleGroups** (for any type): delete existing ones, recreate with `id(null)`
    ensure `Author`/`Developer`; restore `userRoleGroupAssignments` by
    role-group name.
11. **MailTemplates** (for any type): delete existing ones, recreate; ensure the
    system ones. **PdfTemplates** are restored the same any-type way (outside the
    `isReportProject` gate) — each `PdfTemplateDto` saved into nct-pdf via `pdfTemplateClient.save`
    ([15](15-pdf-and-mail.md)).
12. **Dynamic CRUDs**: call `importDynamicCruds`, then
    `rebindAllCrudsToSources`. Runs **last**, after sources/rules/queries/
    contexts are already saved (Groovy methods resolve identifiers at runtime).
13. **Integration data sources** (orchestration, after the integrations are RUNNING):
    `bindIntegrationDataSources` points every source declared in
    `integrations.json.dataSourceIdentifiers` at THIS tenant's integration schema — repointing the
    imported row, or recreating it under the same identifier ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)).
    Runs on the Override **and** the Ignore path (Ignore imports the static content, which is what
    carries the charts). Without it a statically integrated project imports with its charts still
    querying the donor's database.

### `importDynamicCruds` — in detail

1. Parse `dynamic-cruds.json` into `DynamicCrudsExport`.
2. Check that `bl` (dynamic-integration) is deployed (a probe `bl.getCruds`); otherwise — skip.
3. Delete existing dynamic CRUD of this (realm, client) — idempotency.
4. Load live sources by identifier (`sourcesByIdentifier`).
5. For each CRUD:
   - `bl.create({alias, name})` → new `crudId`.
   - `bl.setSource(crudId, sourceIdentifier, host, port, db, schema, user, password)` — **creds
     are taken from the live source by `sourceIdentifier`**, exported values are only a fallback.
   - `bl.setLocalizationField(crudId, localizationField)`.
   - For each method: **`ensureHiddenGroovyRule`** (GROOVY with ruleIdentifier+script only),
     then `bl.addMethod(crudId, {methodName, methodType, script, returnType, returnsArray,
     methodOrder, ruleIdentifier, queryIdentifier, contextIdentifiers})` → `newMethodId`;
     `bl.addParameter` for each parameter; `bl.setReturnFields`.
   - `bl.addDtoField` / `bl.addFilterField` for each field.
6. After all CRUD — `rebindAllCrudsToSources`: push the current src_source creds into
   each `dynamic_crud` row via `bl.setSource`.

### `ensureHiddenGroovyRule`

Recreates the **hidden** `RuleEntity` that authoring writes for each Groovy CRUD method but
which is filtered out of the export (`rep-objects.rules` contains no hidden=true). Without this the first call
to a Groovy method fails with `"Rule not found with identifier: <ruleIdentifier>"`. The rule:
`name="crud_<alias>_<methodName>"`, `executor="GroovyExecutionRule"`,
`ruleType=EXECUTION_RULE`, `status=ACTIVE`, `rule.ruleScriptStr=<script>`, `hidden=true`,
`identifier=<method.ruleIdentifier>`. Idempotent (save by identifier).

### What is remapped and what is not

| Entity | id/identifier on import |
|---|---|
| Content (branches.json) | node ids are **preserved as-is** (`branchService.saveAll`); `branch.tenantId` is overwritten |
| rep-objects (all except roleGroups) | `id:null` on export (key present, value null) → new id on import; relationships by `identifier` |
| roleGroups | id is **not** nulled on export, but on import created with `id(null)` |
| `form.formGroup.id` | nulled on export → import maps the form to the group by `identifier` |
| `query.sourceIdentifier` (RIMM) | remap old RIMM identifier → new |
| `query.sourceIdentifier` (integration data) | **not** remapped — the SOURCE ROW is rebound instead (repointed, or recreated under the declared identifier), so queries, chart embeds and CRUDs all follow without being touched ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)) |
| `source.dbName` | remap old DB name → new |
| INTERNAL source creds | rewritten to the new project-level role |
| DB schema `rimm_<old>` | remap → `rimm_<realm>_<client>` |
| DB schema `public` | **skipped** (mapped to null) — Kafka-managed tables |
| DB schema `int_*` / `system_*` (≠ the target's own `system_<realm>_<client>`) | **skipped** (mapped to null) — assumed to be the donor's integration/liquibase registries. Silent: logged only. A business schema named this way loses ALL its tables and rows on import ([10](10-database-management.md) §Export shape) |
| dynamic CRUD | recreated entirely via `bl.*`; new ids; source creds from the live src_source |
| hidden Groovy rules of methods | recreated by `ensureHiddenGroovyRule` from `method.ruleIdentifier` |

---

## The import reported a problem — reading the message

The person who hits this has the `.mrjun`, the import screen, and **nothing else** — no access to any
service log. So the banner is written to be the whole diagnosis, and it is the only input needed to fix
the file. Paste it verbatim; every part of it is load-bearing.

### Anatomy

```
The database was NOT replaced. Schema(s) [rop_schema] were rolled back to their previous contents,
so no data was lost and the project still holds what it held before this import.
Cause: Reset restore could not apply the rows of rop_schema.supplier:
[SQLSTATE 42703] ERROR: column "deleted" of relation "supplier" does not exist
 — the imported file has a column this database's table does not, and it could not be added
   automatically.
```

1. **What state the project is in.** A *reset* restore is atomic per schema: if it says "rolled back",
   the project holds exactly what it held before, nothing is half-imported, and re-importing a
   corrected file is safe. This sentence is there so nobody starts a recovery that isn't needed.
2. **Which object.** `<schema>.<table>` and the operation that failed (`the rows of`, `table`,
   `enum type`, `the value of sequence`, …).
3. **`[SQLSTATE nnnnn]`** — the stable, locale-independent identity of the failure. Match on this, not
   on the English text.
4. **The cause line** — what it means in terms of the FILE versus the TARGET.

### What each SQLSTATE means for the file

| SQLSTATE | Means | Usual fix in the build |
|---|---|---|
| `42703` undefined_column | the file writes a column the target table does not have | the target's table predates the file's schema. A reset import ADDs missing columns automatically, so seeing this means the add itself failed — most often an enum-typed column whose type does not exist in the target. Check the file's `enumTypes` for that schema |
| `42P01` undefined_table | the file writes to a table it never created | the table is missing from `project-db.dump.schemas[].tables[]`, or its `ddl` failed earlier in the same import |
| `23505` unique_violation | two rows in the FILE share a key | a generator minted a duplicate — the classic is a deterministic `uuid5` over a key that repeats. Fix the seed, not the database. `validate` does not read `tables[].rows`, so only a row-level audit catches this offline |
| `23503` foreign_key_violation | a row points at a row the file does not contain | a soft link was seeded without its parent, or the parent row was filtered out of the dump |
| `23502` not_null_violation | a NOT NULL column is empty for some row | the seeder never set it. If the column is infrastructure (an audit or soft-delete marker), default it in ONE place in the dump writer rather than in every seeder |
| `23514` check_violation | a value is outside a CHECK vocabulary | a status/enum literal a rule or a seeder writes is not in the constraint's list. The CHECK and every writer of that column must come from one source of truth |
| `22001` string_data_right_truncation | a value is longer than the column | widen the column in the schema spec, or trim at the seeder |
| `22P02` invalid_text_representation | a value does not parse as the column's type | a date/number/uuid emitted in the wrong format |
| `42704` undefined_object | the file uses a type the database does not have | an enum type missing from `enumTypes`, or referenced unqualified from a schema that is not on the search path |
| `57014` / `55P03` lock timeout | something still holds the table | an integration pod is running against this database. Stop it and import again — this one is NOT a file problem |
| `42501` insufficient_privilege | the service's DB user may not change that object | infrastructure, not the file |

### The rule the message is built on

Every hop passes the failing service's sentence through **unwrapped**. A layer that re-wraps
(`Failed to restore database: [500 ] during [POST] to [http://…?schemaRemap=%7B…]
[RepositoryDatabaseClient#restoreDatabaseFromJson(String,String,Boolean,Boolean,byte[])]: {…}`) pushes the one
actionable sentence out of sight and turns a fixable report into a shrug. If you add a hop, unwrap.

## Static vs Dynamic — the exact difference at the file level

| Aspect | STATIC | DYNAMIC |
|---|---|---|
| `dynamic-cruds.json` | **absent** | **present** (`exportVersion:1`, N CRUD) |
| CRUD business logic | compiled Java `@Crud` beans in a separate microservice; resolved by reflection (`service.crud.product.find` → `ProductCrud.find`) | defined in the project (`bl`/Business Logic); stored in `dynamic-cruds.json`; methods = SQL(→query) or Groovy |
| Business schema in `project-db.dump` | **no** — only `int_*` (schemas of INTERNAL/INTEGRATION sources), `public`(0), an empty `rimm_*` | **yes** — the business schema, with its tables, data, sequences and FKs, rides inside the dump |
| `rep-objects.queries` | few — only manually created queries | many — one `crud_<alias>_<method>` per SQL method + others |
| `rep-objects.sources` | 0 (INTEGRATION/SYSTEM sources are excluded; the business DB is external, in the microservice) — a project whose CHARTS read the integration's schema declares it in `integrations.json.dataSourceIdentifiers` instead, and the import rebinds it ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)) | ≥1 (an INTERNAL source on the business schema, referenced by CRUD methods) |
| Reconstructability from the export | **impossible** to restore the business logic — it's in code | **everything** for reconstruction is in the export |

This is exactly why the master playbook [13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md)
targets dynamic: from an empty export you can add `branches.json` + `dynamic-cruds.json` +
`project-db.dump` + `rep-objects.json` and get a fully working project. The full breakdown of the two styles —
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

---

## How to construct from scratch — recipe

The Step-2 starting point is the **empty baseline** bundled with this library (`initialtemplates/empty.mrjun`;
unpack it with `mrjun.py unpack`) (see [README.md](README.md), "Step 2"). This is an admin scaffold:
- `tenant.json` — the shape is
  `{"name":…,"alias":…,"description":…,"domain":…,"status":"published","template":false,"importedFrom":[],`
  `"locales":["en_US","hy_AM"]}`. ⚠️ The concrete name/alias/domain in the bundled copy are the ones of the
  tenant it was exported from and carry no meaning for you — on import the target tenant's own realm/client
  are used. The same is true of the schema names inside `project-db.dump`: they carry **that** tenant's
  `schemaPrefix`, and the import renames every one of them into the recipient's own prefix.
- `branch-metadata.json` = `{"publishedBranchName":"master","totalBranches":1}`.
- `branches.json` — one branch `master` with `rootContent` made of top-level `siteMapPage` admin
  pages (Sources, Queries, Business Logic, Database, Rules, Contexts, Form Groups, Workflows,
  Settings, etc. — 23 in all) and **20** `virtualPlugins`. No business pages/forms/CRUD.
- `rep-objects.json` — 6 default `queries` (`Countries`, `Rimm Brand Start With`,
  `Rimm Countries Start with`, `Rimm Equipments`, `Rimm Users by Role Group`,
  `Rimm User Start With`), 2 `processGroups`, 2 `roleGroups` (`Author`, `Developer`), 4 `settings`,
  5 `mailTemplates` (`Company Invitation`, `Event Reminder`, `Password Recovery`, `sendIntakeInit`,
  `User Registration`), **1 INTERNAL `source` named `data`**; everything else empty.
- `project-db.dump` — 2 **empty** schemas, `<prefix>_data` and `<prefix>_rimm`, where `<prefix>` is
  `project-db-meta.json.schemaPrefix` (no business tables — you create them).
- `integrations.json` — the pinned **Business Logic** integration (keep it; see above).
- `dynamic-cruds.json` — **absent** (we create it).

> **Precondition:** the target tenant on import must be `type==REPORT` — otherwise `rep-objects`/DB won't
> be restored (see Gotcha #12). The empty baseline is created as a REPORT project.

To build a dynamic project by hand (producing an exact `.mrjun` on output):

1. **`tenant.json`** — set `name`, `alias`, `domain=<realm>.<client>`, `locales`. Everything else — as in
   `empty/tenant.json` (`status:"published"`, `template:false`, `importedFrom:[]`).
2. **`project-db.dump`** — add the business schema to `schemas[]` **carrying the same `schemaPrefix` the
   other schemas carry** (`<prefix>_app`, not a bare `app_schema` — the import classifies a schema by that
   prefix and renames it into the recipient's own) with `enumTypes`,
   `tables[]` (`name` + `ddl`(`CREATE TABLE "<prefix>_app"."t"(...)`) + `columns` + `columnTypes` +
   `rows` + `rowCount`), `sequences[]`, `foreignKeys[]`(DDL strings), `indexes[]`, `uniqueConstraints[]`,
   `checkConstraints[]`. Leave the shipped `<prefix>_data` / `<prefix>_rimm` schemas empty. `columnTypes` —
   JDBC `java.sql.Types` codes.
   `rows[].<col>` — **strings** (even numbers/booleans); `null` = `null` — an unquoted number rolls the whole
   schema back on import, see [Gotcha 7](#gotchas). Build them with `db_cmds.normalise_rows`. Table order — by FK
   (parents before children). Don't forget the paired `project-db-meta.json` (otherwise the DB isn't staged).
   Schema recipe — [10-database-management.md](10-database-management.md).
3. **`rep-objects.json`** — add (write `"id": null` on every object — the key is required):
   - `sources[]`: one INTERNAL `SourceDto` per business schema (`identifier`=UUID,
     `dbType:"POISTGRESQL"`, `dbName`, `schemaName=<prefix>_app`, `hostName`, `port`, a non-blank
     `userName` — it is `@NotBlank` and a blank one makes the platform REJECT the object). ⚠️ The baseline
     already ships one INTERNAL source named `data`; reuse it or delete it, never leave two INTERNAL rows
     over two schemas. On import the `dbName`, `schemaName` and the creds are all rewritten onto the
     RECIPIENT's project — so whatever you write there is a placeholder, never a live coordinate.
   - `queries[]`: for each SQL method of the CRUD — a `query` with `identifier`(UUID),
     `name="crud_<alias>_<method>"`, `sourceIdentifier`=the source's UUID, `query` with placeholders
     `{name:'p', type:'integer'}`. Details — [12-...](12-queries-sources-schedulers-and-rest.md).
   - `contexts[]`, `rules[]`, `formGroups[]`, `forms[]` as needed (topical docs). In `forms[]`
     keep `formGroup.identifier` consistent with `formGroups[].identifier`; `formGroup.id=null`.
   - Leave `settings`/`roleGroups`/`processGroups`/`mailTemplates` as in `empty`.
4. **`branches.json`** — in `rootContent.children` add business `siteMapPage` pages with
   plugins. **Form controls** write config into `properties.settings.stringValue` (a JSON string);
   **table plugins** (`crud.table.plugin`/`crud.tree.plugin`/`process.table.pluin`) — into
   `properties.model.stringValue`. Node `identifier`/`uniqueIdentifier` — fresh UUIDs; `branchId` =
   the root's `branchId`. Recipes — [01-content-model-and-pages.md](01-content-model-and-pages.md),
   [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md),
   [04-crud-table-plugin.md](04-crud-table-plugin.md).
5. **`dynamic-cruds.json`** — create `{ "exportVersion": 1, "cruds": [...] }`. For each CRUD:
   `alias`, `name`, `sourceIdentifier` (= the source from step 3), opt. `sourceHost/Port/Db/Schema/User/Password`,
   `localizationField`, `dtoFields[]`, `filterFields[]`, `methods[]` (the standard set
   `find`(GROOVY, methodOrder -1, paging wrapper) + `findAll`/`count`/`get`/`create`/`update`/`delete`
   (SQL, each with `queryIdentifier` → the query from step 3)). Full CRUD recipe —
   [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).
6. **ZIP** flat (entries relative to the root; any zip tool works), extension `.mrjun`,
   import via authoring **into a REPORT tenant**. Import itself will: restore the DB, remap
   ids/source creds, recreate dynamic CRUD via `bl` and the hidden Groovy rules of methods.

---

## Gotchas

1. **`id` = `null`, but the key is present.** In rep-objects, an object's `id` field serializes as `"id": null`
   (`it.toBuilder().id(null).build()`) — the key is **not** removed. Verified:
   `jq '.rules[0]|has("id")'` == `true`, `.rules[0].id` == `null`. Relationships hold on `identifier`
   (UUID). Write `"id": null` by hand and set consistent `identifier`s. Exception:
   `roleGroups` (id not nulled on export, but still created with `id(null)` on import).
2. **Content ids are NOT remapped.** `branches.json` nodes are saved with their `id`/`identifier` as-is
   (`saveAll`). Ensure uniqueness of page `identifier`/`uniqueIdentifier`/aliases yourself
   (an alias collision breaks routing — a known form-page problem).
3. **The config slot depends on the plugin.** Form controls → `properties.settings.stringValue`; table
   plugins (`crud.table.plugin`/`crud.tree.plugin`/`process.table.pluin`) → `properties.model.stringValue`.
   Confusing the two = the plugin won't read its config.
4. **`dynamic-cruds.json` may be absent.** It's absent if `bl` isn't deployed OR the project has no
   dynamic CRUD. For a static project it should not be there. And import will silently skip it
   if `bl` isn't deployed on the target side — then the CRUD won't be created.

   ⛔ **A type error in the envelope is skipped just as silently, and it is the worse one.**
   `exportVersion` is the **integer** `1` — a platform-produced export carries `1`, and the toolkit
   writes `1`. A STRING there — `"1"`, and certainly `"1.0"`, which does not
   coerce — throws inside `DynamicCrudsExport` parsing. Because `importDynamicCruds` is the LAST step of
   `initAllObjects`, everything else has already landed: pages, rules, queries, contexts, forms,
   workflows, mail/PDF templates and the restored database all arrive, and only the business logic is
   missing. What the customer reports is not "the import failed" but **"every register shows headers and
   no rows"**, with `No RSocket connection found for CRUD alias: <alias>` in the UI and an empty
   Business Logic console — a symptom that reads like a dead runtime rather than two characters in the
   archive. `validate` now ERRORs on it (`_check_dynamic_cruds_envelope`); nothing else does — `pack`
   never reads the file's types and the import report does not name the step it skipped.
5. **Hidden Groovy rules of methods are not in rep-objects.** The export filters out `hidden=true`. They
   are recreated on import from `dynamic-cruds.json` (`ensureHiddenGroovyRule`). If you manually delete
   `dynamic-cruds.json`, Groovy CRUD methods will fail with "Rule not found".
6. **SQL placeholder syntax differs.** `method.script` in `dynamic-cruds.json` uses
   `:param`; `query.query` in `rep-objects.json` uses `{name:'param', type:'integer'}`. These are **different**
   representations of the same query; keep them consistent.
7. **project-db.dump is not pg_dump.** It's a custom JSON `nct-jdbc-dump-v1`; a `pg_dump` binary
   import won't understand it. Row values are **always strings** (`rows[].col` is string|null); restore typing
   is driven by `columnTypes` (JDBC `Types`).

   ⛔ **An unquoted number in `rows[]` loses the whole schema.** This is not a tidiness rule — it is the
   restorer's signature. `ProjectDatabaseServiceImpl.restoreSingleSchema` reads

   ```java
   List<Map<String, String>> rows = (List<Map<String, String>>) tableDump.get("rows");
   ...
   String val = row.get(columns.get(i));            // erased generics -> checkcast lands HERE
   setTypedParameter(ps, i + 1, val, sqlType);      // ps.setObject(idx, val, sqlType)
   ```

   so a JSON `1` parses to `Integer` and throws `class java.lang.Integer cannot be cast to class
   java.lang.String`. A `ClassCastException` is **not** a `SQLException`, so it misses the per-table
   `catch (SQLException insertEx)` savepoint that exists to keep one bad table from poisoning the rest —
   it unwinds `restoreSingleSchema` entirely and the caller reports:

   > Imported with warnings — The database was NOT replaced. Schema(s) `[x]` were rolled back to their
   > previous contents … Cause: class java.lang.Integer cannot be cast to class java.lang.String

   The import otherwise "succeeds": content, rules and CRUDs all land, so the project opens with every
   page rendering and **every table, chart and worklist empty**. Read as a database-shape problem; caused
   by one unquoted integer.

   | field | JSON type the restore requires | read as |
   |---|---|---|
   | `tables[].rows[].<col>` | **string** or `null` — including integers (`"1"`), booleans (`"true"`/`"false"`), numerics (`"1200.00"`) and jsonb (the JSON **as a string**) | `Map<String,String>` |
   | `tables[].columnTypes[]` | **number** (JDBC `java.sql.Types` code) | `List<Number>` → `.intValue()` |
   | `sequences[].lastValue` | **number** | `(Number)` |
   | `tables[].columns[]`, `foreignKeys[]`, `indexes[]`, `checkConstraints[]`, `uniqueConstraints[]`, `triggers[]`, `views[]`, `functions[]` | string | `List<String>` / `Map<String,String>` |

   Every dump the platform EXPORTS is string-typed by construction (`row.put(label, val.toString())`), so
   **no reference export can show you this by contrast** — only a generated or hand-edited dump can carry it,
   and it is invisible to any offline check that loads the file with Python's `json`, where `1` and `"1"`
   behave alike. Build the rows through `db_cmds.normalise_rows(columns, rows)` / `db_cmds.dump_cell(v)`,
   and `mrjun.py validate` ERRORs if one slips through.
8. **`public` and Kafka tables.** The `public` schema is skipped on restore (`public→null`), and
   the tables `users`/`role_groups`/`users_has_role_groups` are excluded from the dump and
   recreated by `createSchemaSync`. Don't put business tables in `public` — they won't be restored.
9. **INTEGRATION/SYSTEM source schemas are excluded from the dump** (by `SourceType`) —
   managed by the execution platform and recreated on the target side. The exclusion goes by
   `source.getSchemaName()` of those sources that are actually present and of type INTEGRATION/SYSTEM.
   Note: `int_*` schemas routinely **still end up in the dump** when `rep-objects.sources` is empty —
   i.e. no INTEGRATION/SYSTEM source row was found for those schemas to exclude them. Conclusion: the mere
   presence of `int_*` in the dump doesn't mean the exclusion mechanism failed; it only works when
   there's a corresponding source row of the required type. When building by hand, don't rely on
   automatic exclusion — put in the dump only what should be restored. **But an `int_`-prefixed schema
   can also be the *business* schema** — see Gotcha #16.
10. **`tenant-files/*.dump` is junk.** If `tenant-files/` got a `project-db.dump`,
    it's a leftover of import staging (`t/{tenantId}/project-db.dump`); ignore it when building.
11. **Source creds are overwritten on import.** Don't count on `sourcePassword`/`sourceUser` from
    the export surviving: INTERNAL sources and dynamic CRUD get the project-level role of the target cluster
    (`rebindAllCrudsToSources`). `sourceIdentifier` must point to an
    actually existing (imported) source, otherwise it falls back to stale exported creds with
    a warning.
12. **⚠️ The `type==REPORT` gate — the most important precondition.** `rep-objects` are assembled on export
    (`CmsProjectServiceImpl.java`) and restored on import (`isReportProject`) **only** for the REPORT type. If the source tenant is not REPORT — `rep-objects`
    exports empty; if the target is not REPORT — import restores only `roleGroups`/`mailTemplates`/`pdfTemplates`,
    and everything else (sources/DB/queries/rules/contexts/forms/settings) is skipped silently.
    Build for a REPORT tenant.
13. **DB staging requires BOTH files.** `project-db.dump` **and** `project-db-meta.json` must
    be present (`&&`), otherwise the DB isn't staged and not restored. Write them as a pair.
14. **`branch-metadata.publishedBranchName` must match** `branches[].name`, otherwise the published
    branch is selected by fallback (`master` → the first).
15. **A form with a "dangling" group is dropped.** The `forms` export drops a form only if its
    `formGroup.identifier` is **non-null** and not among the exported `formGroups`; forms
    with `formGroup == null` or `formGroup.identifier == null` are **kept** (`return true`).
    So the number of forms in the export can be smaller than the authored one. Keep each form bound to
    an existing group.
16. **⚠️ Don't identify the business schema by name prefix — an `int_`-looking name can be the business
    schema.** A *dynamic* project built on top of a schema that a JPA service originally created keeps that
    schema's generated name (`int_<realm>_<client>_<hash>`): its tables and rows ride **inside**
    `project-db.dump`, and every dynamic CRUD points `sourceSchema` at it (`dynamic-cruds.json`, backing
    `ExportedCrud.sourceSchema`). This is *not* an excluded INTEGRATION/SYSTEM schema (contrast Gotcha #9).
    **Identify the business schema by which schema the CRUDs' `sourceSchema` points at, NOT by name prefix** —
    an `int_`/`system_`/`app_` prefix is just a name, not a type. (In a *static* project the `int_*`
    schemas really are integration schemas with no CRUDs behind them; the two cases are distinguished only
    via `dynamic-cruds.json` → `sourceSchema`.) **But the importer does not make that distinction** — it skips
    every `int_*`/`system_*` schema on restore (step 4 above). So an `int_`-named business schema is readable and
    correct as a *description*, and yet cannot be re-imported: rename it first
    ([10-database-management.md](10-database-management.md) §Adding an entity to a FILLED dump).
17. **⚠️ Import is DESTRUCTIVE — a full REPLACE, not a merge.** Into a REPORT tenant, **step 1** of the import
    (`projectCleanupService.deleteAllProjectData`, [§How import restores it](#how-import-restores-it-operation-order-and-id-remapping),
    isReportProject only) **wipes ALL existing project data first**; and the dynamic-CRUD import runs its own
    clean-slate — `bl.deleteCrud` for **every** existing dynamic CRUD of the (realm, client) before recreating
    (`importDynamicCruds`). So re-importing a modified `.mrjun` **replaces the whole project**; you cannot
    incrementally import a delta into a populated tenant, and there is no "merge" mode. To change one entity in a live
    project, edit the source `.mrjun` and re-import the entire archive (the modify-and-reimport scenario C in
    [19-build-decision-procedure.md](19-build-decision-procedure.md)). That re-import first asks how to treat the
    business logic — which of Ignore / Override / Rebuild you need depends on what your delta touched, Gotcha #19.

18. **⚠️ The file is not the platform — and "the setting didn't save" usually means "the archive was never
    imported".** Editing `branches.json`/`rep-objects.json` and re-packing changes **nothing** in a running
    tenant until the archive is imported (and the import is a full replace, Gotcha #17). The failure looks
    like a platform bug: the settings panel shows the field **empty**, because a stored rule identifier is
    resolved with `ruleService.findByIdentifier` (`RuleIdentifierSelectorField.java`) — an id that
    does not exist in the tenant renders as "nothing selected", not as an error. Before debugging the
    runtime, prove what is actually in the tenant with two read-only queries against the platform DB
    (substitute your own container / database / credentials):

    ```bash
    # does the rule exist in the tenant?
    psql -tAc "select identifier, name, rule_type, status from nct_executor.nct_rule
                where identifier='<rule-uuid>'"

    # which stored content row holds the node, and what does its settings JSON say?
    psql -tAc "select s_id from nct_ui.s_branch_content_store
                where root_content::text like '%<node-identifier>%'"
    ```

    The second query returns the branch content row; dump `root_content` and walk it exactly like
    `branches.json` (same shape — `rootContent.children[]`, `properties.settings.stringValue`). If the value
    is absent there, the import never happened; if it is present and the UI still ignores it, only then is it
    a runtime question. This is a common false alarm: a List action's On Before Complete rule wired correctly
    in the file, an empty field in the panel, and both probes empty — the archive had simply never been imported.

19. **⚠️ Uploading into an existing project asks which business-logic treatment you want first — the answer
    decides whether your DB and CRUD work lands at all.** Settings → Import/Export is the only route a
    hand-assembled `.mrjun` takes into the platform, and before importing it the upload opens a choice dialog
    (`ImportBusinessLogicChoiceDialog`) whenever the archive carries business logic — a non-empty
    `dynamic-cruds.json`, **or** an `integrations.json` entry with `external:false` — or the target project
    already runs an internal integration. The bundled baseline ships exactly such an `integrations.json` entry
    (§Export shape), so in practice **every** archive built on it raises the dialog, including a first
    content-only import.

    | Choice | What the platform does |
    |---|---|
    | **Ignore** (keep the existing business logic + database) | the platform **removes `project-db.dump`, `project-db-meta.json`, `dynamic-cruds.json` and `integrations.json` from the archive** and imports only the static content (branches, rep-objects, tenant files, favicon). The live integration, its schema and its data are left untouched |
    | **Override** business logic + database | the full import described in [§How import restores it](#how-import-restores-it-operation-order-and-id-remapping): the existing integration is torn down and recreated, `project-db.dump` replaces the ROWS of every business schema it carries, `dynamic-cruds.json` is replayed. Table **structure is preserved** — tables the dump carries are emptied and reloaded, and a column the archive adds is added, but a column whose type changed, or one the archive dropped, stays as the project has it |
    | **Rebuild** business logic + database | the same replacement, done by **dropping each business schema and rebuilding it from the archive**, with the project's integration left running the whole time. Structure comes from the archive, not the project. Refuses the import — changing nothing — if a schema holds something the archive cannot put back (see below) |
    | **Cancel** | nothing is imported |

    **Which one to ask for.** **Override** whenever your delta touched `project-db.dump`, `project-db-meta.json`
    or `dynamic-cruds.json` — i.e. always for a build from the empty baseline, and for any change that adds a
    table, rows, a CRUD or a method. **Ignore** only for a content-only delta (`branches.json` /
    `rep-objects.json`) into a project whose live database must survive — there Override would restore the
    archive's older dump snapshot over live data and tear the running integration down.

    **Rebuild** is the one to reach for on the build-import-fix loop against a project you own, for two reasons.
    It is much faster: Override spends most of its wall-clock destroying the integration and waiting for a new
    one to reach RUNNING (a wait that is allowed ten minutes), and Rebuild skips all of it. And it is the only
    choice that makes the archive authoritative about **structure** — after you change a column's type, drop a
    column, or rename one, Override leaves the project's old shape in place and the reload then fails or
    half-lands, while Rebuild produces exactly the tables the archive describes.

    ⚠️ **Rebuild needs the archive's integration to be the one already running.** It reuses this project's
    live integration rather than creating one, so if `integrations.json` names an internal integration the
    project does not have, the import stops before anything is written and tells you to use Override (which
    creates it). This is deliberate: integrations are matched by name and nothing de-duplicates them, so
    proceeding would leave two pods answering the same business-logic alias.

    ⚠️ **Rebuild refuses rather than destroys.** Before dropping anything it inventories what the dump format
    provably cannot recreate, and if the schema holds any of it the import stops with those objects named and
    the schema untouched: a table called `users`, `role_groups` or `users_has_role_groups` (skipped by bare name
    on both dump and restore, so it is never exported); a materialized view, foreign table or partitioned table;
    an identity or `GENERATED … STORED` column; a column with a non-default `COLLATE`; a standalone composite
    type or domain; an aggregate or window function; or a foreign key with one end in another schema, in either
    direction. Every one of those survives **Override** — that is what "preserves structure" buys — so a refusal
    is a signal to use Override for that project, not a bug. A schema built through the platform's own CRUD
    builder trips none of them.

    Rebuild is also stricter about the reload itself: after a drop, "already exists" is impossible, so a table,
    constraint, index, view, function or trigger the archive describes and that does not come back is a hard
    failure for that schema (rolled back intact) rather than a line in a service log. Override keeps warning
    and carrying on, because there the object it failed to create is usually still there from before.
    ⚠️ **Ignore succeeds silently.** Nothing errors, the import reports done, and the symptoms of the wrong
    answer — data missing, CRUDs unchanged, sources untouched — are the same set the deserialization-abort table
    above attributes to a different cause, so the post-mortem starts in the wrong place. Whoever drives the
    browser must be told which button to press; after the import, verify that a table you changed really carries
    its new rows.
