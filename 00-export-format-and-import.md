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
> `mrjun.py validate`. `inspect` opens with what the file carries, part by part, exactly as the Import dialog
> will read it ([§Which parts a file carries](#which-parts-a-file-carries)).

> **⚠️ An archive is made of PARTS.** The Export dialog writes exactly the parts its author ticks, and the Import
> dialog replaces exactly the ticked parts the file carries — every other part of the target project stays as it
> is ([§The Export and Import dialogs](#-the-export-and-import-dialogs--and-why-an-automated-import-must-set-them)).
> So an archive may legitimately lack `branches.json`, the dump or any `rep-objects` key; what is absent is not
> "none", it is "not in this file".

> **⚠️ Two owners.** The base export layer (`tenant.json`, `branches.json`, `branch-metadata.json`, the zip
> itself) belongs to the **CMS library** the platform embeds; everything else (`rep-objects`,
> `project-db.dump`, `dynamic-cruds`, favicon, tenant-files, template-files, the history and audit files) belongs
> to the **Dokie application**.

> **⚠️ Key precondition (see Gotcha #12): only a project with the tenant property `type == REPORT` has every
> part.** A project of any other type is offered — and exports — only Pages, forms and rules; Mail and PDF
> templates; Roles and access; Integration services; Business logic — and even its Pages carry only the content
> trees and files, never the rules, contexts, queries, forms or settings of `rep-objects`. A populated
> `rep-objects` plus a DB riding in the dump is itself evidence that the source project was a REPORT project. If
> the target tenant on import is **not** REPORT, everything but the content trees and files, the roles, the
> templates and the business logic is silently skipped. When building by hand, target a REPORT tenant.

---

## Export shape — what's inside the archive

`.mrjun` is a flat ZIP (entries relative to the root, no nested wrapper folder) of the **parts** its author ticked
in the Export dialog. A full export, unpacked — each entry with the part (the dialog's box) it belongs to:

```
<archive>/
  tenant.json              ← base layer — ALWAYS
  branches.json            ← base layer — content trees of the branches            [Pages, forms and rules]
  branch-metadata.json     ← base layer                                            [Pages, forms and rules]
  rep-objects.json         ← one list per kind of object — ALWAYS; each key only with its part (§6)
  project-db.dump          ← JSON dump of the PRIMARY project DB (nct-jdbc-dump-v1) [Database]
  project-db-<db>.dump     ← dump of each ADDITIONAL distinct CRUD-source DB        [Database]
  project-db-meta.json     ← {databaseName, databases:[…], schemaPrefix, rimmSourceIdentifier} — the re-linking
                             metadata, written with or WITHOUT the dump (§4)
  dynamic-cruds.json       ← DYNAMIC ONLY — the CRUDs and the enumerations          [Business logic]
  integrations.json        ← the execution-platform integrations                    [Integration services]
  workflow-history.json    ← every version of every workflow, oldest first          [Version history]
  processes.json           ← the project's processes, running and ended             [Processes]
  process-audit-logs.json  ← the audit-log entries of those processes               [Process audit log]
  data-audit-logs.json     ← the data change history: who changed which record      [Data change history]
  favicon/                 ← favicon assets (tenant/{id}/favicon/*)                 [Pages, forms and rules]
  tenant-files/            ← the project's own files (t/{id}/*)                     [Pages, forms and rules]
  template-files/          ← the images the mail and PDF templates show            [Mail and PDF templates]
```

**Always present: `tenant.json` and `rep-objects.json` — and, from a REPORT project, `project-db-meta.json`.** Every
other entry is there only when its part was ticked AND the project has something for it (a zip carries no empty
folder):

| Entry | Present when |
|---|---|
| `branches.json`, `branch-metadata.json` | Pages, forms and rules is ticked. Absent, an import leaves the target's pages, its published branch **and its languages** as they are |
| `tenant-files/`, `favicon/` | Pages, forms and rules is ticked and the project has such files ([§8](#8-favicon-and-tenant-files)) |
| `template-files/` | Mail and PDF templates is ticked and the templates show images ([§13](#13-template-files--the-images-the-templates-show)) |
| `dynamic-cruds.json` | Business logic is ticked, the project has a dynamic CRUD or an enumeration, and its business logic could be read WHOLE (a file missing some CRUDs would delete them on import, so it carries none instead); absent too when `bl` is not deployed — a static project never has it ([§7](#7-dynamic-crudsjson--dynamic-only)) |
| `integrations.json` | Integration services is ticked and the project has at least one integration (their data-source bindings travel in `project-db-meta.json` either way) ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)) |
| `project-db.dump` (+ `project-db-<db>.dump`) | Database is ticked and at least one project database could be dumped |
| `rimm-data.json` | legacy last resort: Database ticked and NOTHING was dumpable |
| `project-db-meta.json` | every export of a REPORT project, Database ticked or not — it says whether the file carries the database (`database`) and what the other parts are re-linked through ([§4](#4-project-db-metajson)) |
| `workflow-history.json` | Version history is ticked; also absent when the workflow service could not be read — the file then carries the current workflows only ([§10](#10-workflow-historyjson--every-version-of-every-workflow)) |
| `processes.json` | Processes is ticked — the export FAILS rather than leave them out ([§11](#11-processesjson-and-process-audit-logsjson--the-projects-processes)) |
| `process-audit-logs.json` | Process audit log is ticked (it needs Processes) |
| `data-audit-logs.json` | Data change history is ticked (it needs Database) ([§12](#12-data-audit-logsjson--the-data-change-history)) |

A part whose data could not be read when the file was made — the business logic, the mail or PDF templates, the
integrations, the feature grants, the API endpoints — is left OUT rather than written empty (empty would delete the
target's on import); when the file is ready, the Export dialog lists the business logic, templates or integrations it
left out, and why.

- `integrations.json` — the bundled baseline already carries one (the **Business Logic** integration). ⛔ **Keep
  it.** When Integration services is imported, the integrations the target lacks are created and started, and the
  dynamic CRUDs are bound to a **running** integration — in a second pass when one had to be brought up. Drop this
  file from a hand-assembled archive and nothing brings an integration up for the CRUDs.
- `workflow-history.json`, `processes.json`, `process-audit-logs.json` — ⛔ **never author or edit them**; see
  [§10](#10-workflow-historyjson--every-version-of-every-workflow) and
  [§11](#11-processesjson-and-process-audit-logsjson--the-projects-processes).
- `project-db.dump` — the export dumps the **DISTINCT UNION** of the primary project DB (`projectDatabaseName`) **and
  every dynamic-CRUD's own `sourceDb`**: the first → `project-db.dump`, each
  additional distinct source DB → `project-db-<db>.dump`, and `project-db-meta.json.databases[]` lists them all.
  This fixed the old data-loss bug where an export whose tenant snapshot lacked `projectDatabaseName` (async/tag
  export) — or whose CRUDs lived under a non-main source — fell through to the row-by-row `rimm-data.json` export,
  which dumps ONLY the RIMM schema and so shipped `tables:[]` (all CRUD data gone). `rimm-data.json` (legacy) is
  now a **last resort** only when nothing is dumpable. A healthy export with the Database therefore carries
  `project-db.dump` **and** `project-db-meta.json` together — if you see `rimm-data.json` instead, the dump path
  failed and data is missing.

**What an export nobody chose carries.** A project created from a template, a version-tag snapshot and an
environment copy export **everything except Processes, Process audit log and Data change history** — none of them is a
copy of a running project, and a template would hand one project's cases and change history to every project created
from it. Their import takes every part the file carries except those three, restores the database **additively**
(it never empties a schema), and never recreates an integration or rebuilds a table.

**⚠️ The `type==REPORT` gate.** The `rep-objects.json` keys `sources`, `queries`, `rules`, `contexts`,
`formGroups`, `forms`, `settings`, `schedulers`, `workflows`, `processGroups` and `apiExposures` are written **only**
when the tenant property `type` is `REPORT`. A project of any other type leaves every one of them **out** (an older
platform wrote them as empty arrays); only `roleGroups`, `userRoleGroupAssignments`, `featureAccesses`,
`mailTemplates` and `pdfTemplates` are written for any type — each with its part. So a `rep-objects.json` that holds
rules or queries at all came from a REPORT-type tenant — and one that lacks them although `branches.json` is there is
the first symptom to check.

**⚠️ A malformed rep-object fails the whole import — before anything changes.** Even against a REPORT tenant, if any
rep-object fails Jackson deserialization while reading `rep-objects.json`, the import stops before it touches the
project — not one page, source, rule or row is replaced — and ends **Import failed** with *"The file's
rep-objects.json could not be read (<the Jackson message>). Nothing has been changed."*; the file is kept and Retry
runs it again. The same happens when the import cannot read the project to decide what it replaces, or cannot remove
what it replaces. An older platform skipped the block instead and reported success, and the symptoms were
**scattered and data-shaped, not error-shaped** — they show up together, and on the current platform they point at
the other causes in the right column:

| Symptom (in the app / business-logic UI) | Actually caused by |
|---|---|
| "No source selected" in Business Logic; sources list empty | the source rep-object was never saved |
| The project's context (whatever you named it) shows **no CRUDs**; rules fail at runtime with `No CRUD found with alias X in context Y` | **Two causes.** (a) the context rep-object (its `crudAliases`) was never saved — cruds carry **no** context reference, so `crudAliases` is the ONLY crud↔context link (see [08](08-groovy-rules-and-context.md)). (b) **the dominant cause even for a byte-correct export:** the import STRIPPED `crudAliases`. Each dynamic-CRUD delete/recreate fires `crud.unregister`, which removes the CRUD's alias from every context, and `crud.register` never re-adds it; the inline import path self-heals but the pass-2 dynamic-CRUD import (the orchestrator REIMPORTING stage — every empty→dynamic and every re-import) historically did NOT, leaving `crudAliases=[]`. **Fix:** re-save the context in the Contexts UI (writes `crudAliases` straight to the entity), or import on a build where the pass-2 dynamic-CRUD import snapshots+restores `crudAliases`. Do NOT "fix" the export — the linkage is already correct. |
| All data / dates "gone" | `project-db.dump` was not restored |

All three at once after an import that reported success (an older platform) ⇒ suspect **one deserialization
abort**, not three separate bugs; find the Jackson stack in `log/ui.log` (`Cannot deserialize … from …`). The gotcha
we actually hit: `rep-objects.settings[].content` is a
Jackson **`ObjectNode` (JSON object)**, NOT a string — a JSON *string* there throws `MismatchedInputException:
Cannot deserialize ObjectNode from String value` (at `settings[].content`). It is
the exact inverse of the node's `properties.model.stringValue`, which IS a string. **The import's failure names only
the Jackson message; the stack is in `log/ui.log`**, and
`mrjun.py validate` sees it only partly (validate ERRORs on a string `content` AND on any rep-object
field that is a string where the same field is an object/array elsewhere — but it does not deserialize into the
DTOs, so a live import + `log/ui.log` scan remains the real test). Don't be misled by `Saved Context … {id}` — that
log prints the DB **id** (freshly assigned; `id=null` on export), not the `identifier`, which is preserved. Prefer
`mrjun.py node set-model`/`patch-model` — they keep the `settings[]` mirror in sync as an object.

### File write order on export

1. **The base export** creates a temp folder (UUID), writes `tenant.json` — and, with Pages, forms and rules,
   `branches.json` + `branch-metadata.json` — then calls the application hook that appends its own files, then zips
   the folder (files only: an empty folder does not reach the zip).
2. **The application hook** appends into the same folder, part by part in the dialog's order (the order the
   export's progress names them in): the content's lists and `sources` (held for `rep-objects.json`),
   `tenant-files/` + `favicon/`; the templates' lists and `template-files/`; the roles; the API endpoints, the
   schedulers, the workflows — then **`rep-objects.json`**, once every part has put its keys there; then
   `workflow-history.json`, `processes.json` (+ `process-audit-logs.json`); `integrations.json`;
   `project-db.dump` (+ `project-db-<db>.dump`, or the legacy `rimm-data.json`) and `project-db-meta.json`;
   `data-audit-logs.json`; `dynamic-cruds.json`.

### Which parts a file carries

The Import dialog decides it from **the file itself** — there is no manifest. A part whose evidence is missing is
drawn **"Not in this file"**, disabled and unticked, and is never imported: the target keeps its own. This is also
how an archive exported before the parts existed, and one assembled by hand, is read — as carrying exactly what it
does carry. The evidence, part by part (`mrjun.py inspect` prints the same reading):

| Part | Carried when the file has |
|---|---|
| Pages, forms and rules | `branches.json` |
| Mail and PDF templates | a `mailTemplates` **or** a `pdfTemplates` list in `rep-objects.json` |
| Roles and access | a `roleGroups` list |
| Public API endpoints | an `apiExposures` list — `null` reads exactly as absent; `[]` IS carried (and deletes every endpoint) |
| Schedulers | a `schedulers` list |
| Workflows | a `workflows` list |
| Version history | `workflow-history.json` |
| Deployment | any workflow version marked `deployed: true` — in `workflow-history.json` when the file has it, else in `rep-objects.workflows` |
| Processes | `processes.json` |
| Process audit log | `process-audit-logs.json` |
| Integration services | `integrations.json` |
| Database | `project-db-meta.json` → `"database": true`. A file whose meta lacks that key (older exports, the baseline): `project-db.dump` **together with** `project-db-meta.json`, or the legacy `rimm-data.json`, or any source in `rep-objects.sources` not named `RIMM_*`. A dump without its meta is NOT a database ([§4](#4-project-db-metajson)) |
| Data change history | `data-audit-logs.json` |
| Business logic | `dynamic-cruds.json` |

A part is offered only together with the parts it needs (Version history and Deployment need Workflows; Processes
need Version history **and** Deployment; Process audit log needs Processes; Data change history needs Database): a
file with `processes.json` but no `workflow-history.json` carries processes nobody can tick, and their switch says so —
*"Needs version history, not in this file"*. An entry whose JSON cannot be read is evidence of nothing: the part it
would carry is "Not in this file", and the rest of the file is still offered. A file that carries nothing the project
can take is refused outright — *"This file is not a project export, or it is damaged: nothing in it can be
imported."*

---

## Per-file reference

### 1. `tenant.json`

Project metadata. Takes only `name, alias, description,
domain, status, importedFrom, locales, defaultLocale, icon` (id, owner, publishedBranchId, etc. are **not**
exported). The `template` flag is **not** copied — `template:false` in the export is always a
hardcoded default (not the source tenant's value); import overwrites it with
`isTemplate` anyway. A populated project's `tenant.json`:

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
| `name` | string | Project name. **Overwritten on import** by the `projectName` parameter | yes | — |
| `alias` | string | Project URL alias; part of schema names (`rimm_<realm>_<client>`, the system schema) | yes | — |
| `description` | string | Description | no | — |
| `domain` | string | Domain `<realm>.<client>` (e.g. `acme.tradefin`) | yes | — |
| `status` | string | Status; forced to `published` on import | no | `published` |
| `template` | boolean | Overwritten on import by the `isTemplate` flag | no | false |
| `importedFrom` | array | Import history | no | `[]` |
| `locales` | string[] | Project locales (`en_US`, `hy_AM`, `ru_RU`…). Always read on import | yes | — |
| `defaultLocale` | string | The project's DEFAULT/authoritative locale (e.g. `hy_AM`). Exported and applied on import, but only when it is one of `locales`; absent ⇒ consumers fall back to `locales[0]`. Author it with `mrjun.py locale set-default` — see [20-localization.md](20-localization.md) | no | — |
| `icon` | string | Icon | no | null |

### 2. `branch-metadata.json`

```json
{"publishedBranchName":"master","totalBranches":1}
```

| Field | Type | Meaning |
|---|---|---|
| `publishedBranchName` | string | Name of the published branch; on import selects the published branch by name |
| `totalBranches` | int | Branch count |

Published-branch selection logic on import: first by the name from the metadata → otherwise the `master` branch
→ otherwise the first one. A single-branch project — the normal case — is
`{"publishedBranchName":"master","totalBranches":1}`.

### 3. `branches.json` — an **array** of branches

Each branch is a serialized branch. Branch keys:

```json
{ "name": "master", "tenantId": 1, "virtualPlugins": [ ... ],
  "rootContent": { ... recursive content tree ... },
  "globalAssets": { "version": 3, "storageId": "…", "folders": [ ... ], "assets": [ ... ] } }
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Branch name (`master`) |
| `tenantId` | int | id of the source tenant. **Overwritten on import** with the new one |
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
base-layer file and node ids are **not** remapped on import — they are preserved as-is.

### 4. `project-db-meta.json`

Metadata for DB remapping on import — what the archive says about the storage of the project it came from, and
whether it carries that project's database at all. Written by **every** export of a REPORT project, **whether or not
the Database was ticked**: an import that takes the pages or the business logic without the database still re-points
their SQL and their data sources through it ([§Re-linking](#re-linking--when-one-part-arrives-without-the-other)).
Without a dump, `databases` is `[]` and `databaseName` names the project's own database.

```json
{"databaseName":"org_<realm>_<hash>",
 "databases":["org_<realm>_<hash>"],
 "schemaPrefix":"<realm>_<client>_<hash>",
 "rimmSourceIdentifier":"74f8ea9d-9e06-4a05-9f89-3144d3321e18",
 "database":true,
 "businessSchemas":["<realm>_<client>_<hash>_app"],
 "integrationSources":[{"name":"erp","dockerImage":"dokie/erp","external":false,
                        "dbSchemaName":"int_<realm>_<client>_5557500e",
                        "dataSourceIdentifiers":["d403c908-…"],"dataSourceNames":["<source-name>"]}]}
```

| Field | Type | Meaning | Required |
|---|---|---|---|
| `databaseName` | string | Name of the donor's project DB. On the current storage model one database holds a whole **organisation** and each project is a set of prefixed schemas inside it, so this is an org-level name — not `prj_<realm>_<client>`. Used to remap `dbName` in source rows and to locate the RIMM schema in the dump | yes |
| `databases` | array | every database the archive carries a dump for (a multi-source project has more than one); `[]` without a dump | yes |
| `schemaPrefix` | string | **the DONOR's schema prefix.** This is the single field that tells the import which of the dump's schemas belong to this project; the import renames each one into the RECIPIENT's own prefix. A schema you add to the dump by hand must carry it. Absent only for a legacy donor whose schemas were unprefixed — the import then infers the prefix from the dump's own `_system`/`_rimm`/`_data` names | yes, whenever the dump's schemas are prefixed |
| `rimmSourceIdentifier` | string(uuid) | identifier of the RIMM-source source. Written **only if** a RIMM source was found. On import, old `query.sourceIdentifier == this` → remapped to the project's own RIMM source (every import has one under a new identifier) | no (only if a RIMM source exists) |
| `database` | boolean | **whether the archive carries the Database part.** The import trusts it over any other evidence ([§Which parts a file carries](#which-parts-a-file-carries)) — `true` even when nothing could be dumped, `false` while the file still has data sources (they travel with the pages and the business logic too, for re-linking). Absent from every archive written before the parts existed | no — absent: the import reads the file as an older one |
| `businessSchemas` | string[] | the schemas the business logic reads — the ONLY ones a database replace may empty or drop when the archive carries no `dynamic-cruds.json` (with it, the CRUDs' `sourceSchema` decide). Written when the database is exported and those schemas could be read | no |
| `integrationSources` | array | per integration that provides data sources, its binding fields — `name`, `dockerImage`, `external`, `dbSchemaName`, `dataSourceIdentifiers`, `dataSourceNames`, the same shape as an `integrations.json` entry ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)). What the import binds those sources through when the archive has no `integrations.json`. Written whenever any integration provides data sources | no |

See [10-database-management.md](10-database-management.md) §"Import-time source materialization" — the two
sections describe one file and must not drift.

**⚠️ The Database part.** A file with `"database"` in its meta carries the Database exactly when that says `true`.
A file without the key (every older export, and the bundled baseline) carries it when `project-db.dump` and
`project-db-meta.json` are both there, or the legacy `rimm-data.json`, or `rep-objects.sources` holds any source not
named `RIMM_*` — an older archive whose database could not be dumped imports its data sources as it always did. A dump
without its meta is never staged nor restored. When building by hand, write `project-db.dump` and
`project-db-meta.json` as a pair; to ship an archive that leaves the target's database alone, write `"database": false`
(what an export writes with Database unticked) — removing the dump alone is not enough while `sources` holds a source
of the project's own.

### 5. `project-db.dump` — the `nct-jdbc-dump-v1` format

A JSON dump of the project DB (**not** a `pg_dump` binary; a custom JSON format). Top level:

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
and except `excludeSchemas` passed by the export.
`excludeSchemas` is populated with the schemas of `INTEGRATION`/`SYSTEM` sources — they are recreated on the target side and don't ride in the dump.
The tables `users`, `role_groups`, `users_has_role_groups` are skipped at the
table/FK/index level — they are recreated on import.

Schema sets you can expect (inspect any dump with `jq -r '.schemas[]|.name'`):

| Project kind | Schemas in the dump |
|---|---|
| Empty baseline | `<prefix>_data`, `<prefix>_rimm` — **both empty** |
| **DYNAMIC** build | the **business schema** (`<prefix>_<your name>`) with tables/sequences/FKs, one `<prefix>_<hash>` per dynamic-integration, `<prefix>_rimm` (a few lookup tables), `<prefix>_data`(empty). The registry `<prefix>_system` is deliberately EXCLUDED from the export |
| **STATIC** build | only `<prefix>_<hash>` integration schemas (large, FK-heavy — generated) and an empty `<prefix>_rimm` — **no business schema** |

`<prefix>` throughout is `project-db-meta.json.schemaPrefix`. Older archives predating the org-per-database
model carry unprefixed `public` / `rimm_<realm>_<client>` / `system_<realm>_<client>` instead; the import
handles both.

**The key static ↔ dynamic difference at the dump level** (see §Static vs Dynamic below):
in a dynamic project the business schema (tables *with data*) rides **inside the dump**; in a static project
there is no business schema — only `int_*` (schemas of INTERNAL/INTEGRATION sources) and an empty
`rimm_*`, because the business logic is compiled Java CRUD beans in a separate
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
| `columns` | string[] | Column names (in column order) |
| `columnTypes` | int[] | JDBC `java.sql.Types` codes for each column (5=SMALLINT, 12=VARCHAR, -7=BIT/boolean, 1111=OTHER/jsonb) |
| `rows` | `Array<Map<string,string\|null>>` | Data; **all values are strings**, null is preserved as `null` |
| `rowCount` | int | Number of rows |

Tables are dumped in FK dependency order.

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

### 6. `rep-objects.json` — object

All project objects except content and DB, one list per kind. **Every key is optional and belongs to one part**
([§Which parts a file carries](#which-parts-a-file-carries)): an export writes the keys of the parts it was asked
for — each list complete, `[]` when the project has none — and leaves every other key **out** (never `null`, never
`[]`). An archive written before the parts existed carries all of them. The keys, by part (their order in the
file means nothing):

```
rules, queries, sources, contexts, formGroups, forms, settings,   <- Pages / Business logic / Database (below)
mailTemplates, pdfTemplates,                                     <- Mail and PDF templates
roleGroups, userRoleGroupAssignments, featureAccesses,          <- Roles and access
apiExposures,                                                    <- Public API endpoints — LEAVE IT OUT of anything you author (below)
schedulers,                                                      <- Schedulers
workflows, processGroups                                         <- Workflows
```

What each key does on import — **"evidence"** marks the keys that decide whether their part is carried at all; for
the others the part's evidence is elsewhere (`branches.json`, the dump, `dynamic-cruds.json`), and once that part is
imported an **absent key means "none"**, not "keep the target's":

| Key | Part | When its part is imported |
|---|---|---|
| `sources` | Database — and written with Pages or Business logic too, as what their references are re-linked through | with Database: the target's sources are replaced by the list (a live integration's own rows are kept unless its integrations are recreated). Without it the list is only READ, to re-link ([§Re-linking](#re-linking--when-one-part-arrives-without-the-other)) |
| `rules`, `queries` | split: the ones a dynamic-CRUD method names (`ruleIdentifier` / `queryIdentifier`) belong to **Business logic**, every other one — hidden ones included — to **Pages, forms and rules** | each half replaces the target's same half; the other half stays |
| `contexts`, `formGroups`, `forms`, `settings` | Pages, forms and rules | replaced |
| `mailTemplates` | Mail and PDF templates — **evidence** (either list) | a non-empty list replaces EVERY mail template of the target (the four system ones are put back if it lacks them); `[]` clears them in a REPORT project (the system ones are re-created) and leaves them in any other; absent = the target's mail templates stay |
| `pdfTemplates` | Mail and PDF templates — **evidence** (either list) | a NON-EMPTY list replaces every PDF template; `[]` or absent = the target's stay |
| `roleGroups` | Roles and access — **evidence** | reconciled **by name**: a group on both sides keeps its id and its members and takes the file's roles; a new one is created; one the list lacks is DELETED with everyone's membership of it (Author and Developer never) |
| `userRoleGroupAssignments` | Roles and access | ADDED to what each member already holds — never removed; the member is found by external id, else by `userEmail` |
| `featureAccesses` | Roles and access | absent = the target's grants stay; a list REPLACES every grant — a feature it does not name is granted to no group; `[]` takes every grant away |
| `apiExposures` | Public API endpoints — **evidence** (a list; `null` = absent) | reconciled by `identifier` as ONE list — see the box below |
| `schedulers` | Schedulers — **evidence** | replaced |
| `workflows` | Workflows — **evidence** | replaced; the target's processes go with its workflows |
| `processGroups` | Workflows | replaced |

⛔ **The rule for a hand-built archive: write every key of every part it carries; leave a key out only together
with its part.** An archive with `branches.json` and no `settings` key does not keep the target's settings rows — it
removes them and brings none, and every plugin that reads its settings on the backend comes up empty.

> ⛔ **`apiExposures` — the project's public API endpoints — is the one key whose ABSENCE is the safe value.**
> An export writes it when Public API endpoints is ticked (a REPORT project only; it is left out when the export
> could not read the endpoints), and an import reads it like this:
>
> | in the archive | on import |
> |---|---|
> | absent, or `null` | the target's API endpoints and their key bindings are left exactly as they are — the part is "Not in this file" |
> | a list | the target's endpoints become exactly that list — matched by `identifier`; the ones not listed are **deleted with their key bindings** |
> | `[]` — what a project with no endpoints exports | ⛔ **every endpoint of the target is deleted, with every key binding** |
>
> API keys never travel, so a binding deleted by an import comes back from no archive: every integration calling
> those endpoints answers `404` until somebody rebinds each key by hand. **Never author the key, and delete it from
> a base exported from a live project** unless the import is meant to restore exactly that list — how, and what an
> entry looks like: [32](32-public-api.md) §6. No `mrjun.py` command writes it, and none may default it to `[]`;
> `mrjun.py api-exposures show` says what it would do, `api-exposures drop` removes it, and `validate` refuses `[]`
> and a list until it is gone. An entry may carry `aiDescriptions` — the texts for AI assistants, one per
> operation; absent or `null` there keeps the target's, `{}` clears them ([32](32-public-api.md) §3.16, §6).

(`mailTemplates[]`/`pdfTemplates[]`, `roleGroups[]`, `userRoleGroupAssignments[]` and `featureAccesses[]` travel for
**all** project types, and are imported for all types (not gated on REPORT); see [15](15-pdf-and-mail.md).)

**⚠️ Population is gated on `type==REPORT`.** `sources/queries/schedulers/workflows/rules/contexts/
formGroups/forms/settings/processGroups/apiExposures` are written only if the tenant is REPORT-type — for any other
type they are absent (see §Export shape).

**⚠️ `id` is nulled, but the KEY IS PRESENT as `null`.** On export, each object's `id` is set to null, which serializes the field as `"id": null` — the key is **not
removed**. Check it yourself on any export: `jq '.rules[0]|has("id")'` == `true`, `.rules[0].id` == `null`
(same for `queries`, `sources`, `forms`, and the nested `forms[].formGroup.id`). On import, ids
are regenerated. Relationships hold on **`identifier`** (the business key, a UUID). When building by hand, write
`"id": null` and fill in consistent `identifier`s.

**⚠️ forms filter + nested `formGroup.id=null`.** Forms export additionally:
(a) **drops** forms whose `formGroup.identifier` is non-null but is not among the exported
`formGroups` (a soft-deleted group); forms with `formGroup == null` or `formGroup.identifier == null`
are **kept** — so `forms.length` can be smaller than the number of authored
forms only because of forms with a "dangling" group; (b) nulls the nested `built.formGroup.id`
so import binds the form to the group by `identifier`, not by numeric id.

Sub-object schemas (verified by the SPEC, details in the topical docs):

| Key | Element shape (abbr.) | Topical doc |
|---|---|---|
| `sources` | `{id, identifier, name, sourceType, dbType, hostName, port, dbName, schemaName, userName, password, ...}` | [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) |
| `queries` | `{id, identifier, name, query, parameters, attributes, aggregations, sourceIdentifier, wrapInPaging, itemsPerPage, offset, schedule, statementTimeoutSeconds}` | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `schedulers` | a schedule object | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `workflows` | `{id, identifier, name, bpmnContent, elements, processDefinitionId, externalId, deployed, contextIdentifiers[]}` | [07-workflows-and-tasks.md](07-workflows-and-tasks.md) |
| `rules` | `{id, identifier, name, description, status, ruleType, executor, contextIdentifiers[], rule:{ruleScriptStr}, hidden, access?, realmName, clientName, ...}` — `access` = who may RUN it (below) | [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) |
| `contexts` | `{id, identifier, name, alias, crudAliases[]}` | [08-...](08-groovy-rules-and-context.md) |
| `formGroups` | `{id, identifier, name, contentPageIdentifier, formGroupsPageIdentifier, contextIdentifiers[], predicateFormMapping, placeFormsNextToLanding}` | [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) |
| `forms` | `{id, identifier, name, formGroup, contentIdentifier, contextIdentifiers[], validators, actionValidators, hiddenConfigs, allowDrafts, multiLanguage}` | [06-...](06-form-groups-and-mapping.md) |
| `settings` | a settings object | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `processGroups` | a process-group object | [07-...](07-workflows-and-tasks.md) |
| `roleGroups` | a role-group object (id is **not** nulled on export — the only exception to the id=null rule) | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `userRoleGroupAssignments` | `{userId, userEmail, roleGroupId, roleGroupName}` — `userId` is the member's external id in the DONOR's realm; `userEmail` is what finds the member in a project on another realm. Bound by `roleGroupName` | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `featureAccesses` | `{feature, roleGroups[]}` — who may use which feature (Settings → Accesses): `feature` is the feature's NAME (`USER_MANAGEMENT`, `ROLE_MANAGEMENT`), `roleGroups` the group names. A name this platform does not know is skipped on import, never refused | — |
| `mailTemplates` | a mail-template object | [12-...](12-queries-sources-schedulers-and-rest.md) |
| `pdfTemplates` | a PDF-template object (`id` nulled on export; saved into the PDF service on import for **all** project types) | [15-pdf-and-mail.md](15-pdf-and-mail.md) |
| `apiExposures` | one public API endpoint: `kind`, `name`, `slug`, `enabled`, `tableUid`, the operations and actions switched on, who calls act as — or, for a rule call (`kind:"RULE"`, no table), its `operations` (method, path, rule identifier, inputs) and the `roleGroups` it is open to; `aiDescriptions` — one text per operation, for AI assistants; never a credential (`id` nulled, `identifier` kept). **Optional — leave it out** | [32-public-api.md](32-public-api.md) |

**Execution access — `rules[].access`.** Who may RUN the rule, whoever asks (a page, the public API, a workflow
step, MCP): `{"publicAccess": bool, "authenticatedUserAccess": bool, "roleGroups": ["<Group>", …]}` —
anyone / any signed-in user / members of those groups; administrators and authors always. **Absent or `null` =
signed-in users.** Archives exported before the platform had the setting carry no `access` key at all, so they
import as signed-in users — every rule an anonymous visitor triggers on a public page is then refused until it is
opened to anyone (`mrjun.py rule access <rule> --access anyone`; `validate` warns on each one). A platform that
predates the feature ignores the key. On a `hidden: true` rule (a CRUD method's body) it is ignored — the method's
access decides (`dynamic-cruds.json`, §7). Model and recipe: [08 §"Execution access"](08-groovy-rules-and-context.md),
[11 §"Execution access"](11-business-logic-dynamic-crud.md).

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
| `rules` | Groovy authored by hand, plus one hidden rule per GROOVY method of a dynamic CRUD (with Business logic) and the hidden rules autocomplete controls and tree settings generate for themselves (with Pages) |
| `contexts` | usually exactly 1 per project |
| `formGroups` / `forms` | the number of authored form pages |
| `settings` | one per settings-bearing plugin node |
| `processGroups` / `roleGroups` / `mailTemplates` | the baseline defaults plus whatever you add |
| `userRoleGroupAssignments` | number of users with an explicit role-group binding |
| `featureAccesses` | one per feature that has a grant (Settings → Accesses) — at most the platform's features |
| `apiExposures` | absent from anything you author; in an export of a live project, the API endpoints configured there |

**Why a dynamic project has hundreds of queries**: every **SQL method** of a dynamic CRUD references a saved
`query`. With the standard method set (`findAll`, `count`, `get`, `create`, `update`, `delete`) that is
6 queries per CRUD, all named `crud_<alias>_<methodName>`; the Groovy `find` wrapper creates none.
So *queries ≈ CRUDs × 6* plus any hand-written ones. Breakdown in
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

**Hidden rules ARE in rep-objects — and the `hidden` flag says nothing about whose they are.** The export carries
every rule, hidden ones included, and splits `rules[]` and `queries[]` by **who names them**: the rule a GROOVY CRUD
method runs (its `ruleIdentifier`) and the query a SQL method is edited through (its `queryIdentifier`) travel with
**Business logic**; every other rule and query — the hidden ones an autocomplete control or a tree's settings generate
for themselves among them — travels with **Pages, forms and rules**. So an export of the pages alone carries no
`crud_<alias>_<method>` rule or query, and one of the business logic alone carries nothing else. An archive built
by hand carries no hidden CRUD-method rule at all: the import creates it from the method's own `script`
([§The hidden Groovy rule](#the-hidden-groovy-rule)).

### 7. `dynamic-cruds.json` — **DYNAMIC only**

The **Business logic** part. Written when it is ticked, the system CRUD `bl` (dynamic-integration) is deployed,
and the project has a dynamic CRUD or an enumeration. Present in dynamic projects; **absent** in static ones and in
the empty baseline. Top level:

```json
{ "exportVersion": 1, "cruds": [ { CRUD }, ... ], "enums": [ { enumeration }, ... ] }
```

`exportVersion` is `1`, `cruds[]` holds one entry per CRUD (`[]` in a project that has enumerations and no CRUD),
and `enums[]` — optional — the enumerations (below). Imported, the business logic is a **clean slate**: every
dynamic CRUD of the target is deleted and the file's are created. One full CRUD:

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
  "methods": [ {method}, ... 7 methods: find, findAll, count, get, create, update, delete ] }
```

| CRUD field | Type | Meaning |
|---|---|---|
| `alias` | string | Technical alias of the CRUD (`service.crud.<alias>`) |
| `name` | string | Human-readable name |
| `sourceIdentifier` | string(uuid) | identifier of the DB source. On import, **live** creds are taken from src_source by this |
| `sourceHost`/`sourcePort`/`sourceDb`/`sourceSchema`/`sourceUser`/`sourcePassword` | string/int | Copy of the connection (fallback if the source is not found) |
| `localizationField` | string | Localization column (`localized` jsonb). Set via `bl.setLocalizationField` |
| `access` | object\|absent | Who may RUN the CRUD's methods (`{publicAccess, authenticatedUserAccess, roleGroups}`), inherited by every method without its own. Absent/null = signed-in users. `mrjun.py crud access` |
| `dtoFields` | array | DTO fields |
| `filterFields` | array | Filter fields |
| `methods` | array | CRUD methods |

A field entry: `{fieldName, displayName, fieldType, fieldOrder}`.

A SQL method (real `findAll`):

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
| `parameters` | array | `{parameterName, parameterType, parameterOrder}` |
| `inheritAccess` | boolean\|absent | Absent/null/`true` = runs with the CRUD's `access`; `false` = with the method's own `access` |
| `access` | object\|absent | The method's own access, read **only** when `inheritAccess` is `false` (then absent = signed-in users). `mrjun.py crud method-access` |

**Execution access on import.** The three access keys are new: an archive exported before the platform had
execution access carries none of them, and absent/`null` means **signed-in users** — so an old archive imports with
every CRUD and method at signed-in users, as before. A platform that predates the feature ignores the keys. A
GROOVY method's hidden rule (`crud_<alias>_<method>`) is governed by the METHOD's access, never its own; a Java
(static) CRUD's access is declared in code and is not in the archive. Model, defaults and what `validate`
reports: [11 §"Execution access"](11-business-logic-dynamic-crud.md).

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

#### `enums[]` — the enumerations

The enumerations the CRUD fields are typed with (a field's `fieldType` names one). Optional: absent from every
archive written before they travelled.

```json
{ "name": "invoice_status", "kind": "FREE", "baseType": "STRING",
  "extraFieldDefs": [ { ... } ],
  "values": [ { "name": "DRAFT", "intCode": null, "displayName": "Draft",
                "extras": { "<extra field>": "<value>" },
                "localizations": { "hy_AM": { "displayName": "<text>" } },
                "valueOrder": 0 } ] }
```

| Field | Meaning |
|---|---|
| `name` | the enumeration's name — what a field's `fieldType` and `service.enums['<name>']` refer to |
| `kind` | `FREE` — a list kept by the business logic itself (absent = `FREE`); `DB` — mirrors a PostgreSQL enum type, whose definition travels in the dump (`enumTypes[]`) |
| `baseType` | `STRING` or `INTEGER` (then each value carries an `intCode`) |
| `sourceSchema`, `sourceType` | `DB` only: the schema and the type it mirrors |
| `extraFieldDefs` | the extra columns each value carries in `extras` |
| `values[]` | `name` (the constant; fixed for a `DB` one), `intCode`, `displayName`, `extras`, `localizations` (`{locale → {field → text}}`), `valueOrder` |

On import, with Business logic — and before the CRUDs, which no longer use any by then:

| in the archive | on import |
|---|---|
| absent | the target's enumerations are left as they are |
| a list | it replaces the target's: a `FREE` one is replaced whole, values and all; a `DB` one is materialised over the type the database already has (it cannot be deleted while the type exists) and its values take the file's labels, extras, translations and order; a `FREE` enumeration the list lacks is **deleted**. A name that is `FREE` in the file but `DB` in the target is left as it is, and the report says so |
| `[]` | every `FREE` enumeration of the target is deleted |

So a FREE enumeration **can** be authored by hand now: write it here, with its values, and type the field with its
`name`.

### 8. `favicon/` and `tenant-files/`

Flat file trees (binaries) of the **Pages, forms and rules** part: copied recursively on export when it is
ticked, and on import when it is taken — files are ADDED and OVERWRITTEN, never deleted, so a file the target has and
the archive lacks stays. Unticked, the import leaves both folders out of the archive before reading it.

- `favicon/` ← from the storage `tenant/{tenantId}/favicon`; on import placed in
  `tenant/{newTenantId}/favicon`. Several dozen files: `favicon.ico`
  `apple-icon.png`, `pwa-icon-*.png`, `favicon-16x16.png`, etc.).
- `tenant-files/webassets/<storageId>/` ← the project's own js, css, html, fonts and images, one subtree
  per BRANCH. Registered on the branch in `branches.json` → `globalAssets`; the two halves line up only
  because the registry stores the path RELATIVE to the tenant root — an absolute `t/{id}/…` survives the
  import unchanged and then reads, successfully, from the DONOR project. See
  [29-global-resources.md](29-global-resources.md)
- `tenant-files/static-pages/<sha256>/<name>` ← the uploaded file of a STATIC page (a page answering its URL
  with a file); the page node keeps that path RELATIVE to the tenant root in `staticFilePath`, and the sha256
  in the path must be the hash of the bytes. See [34-static-pages.md](34-static-pages.md)
- `tenant-files/` ← from `t/{tenantId}`; on import → `t/{newTenantId}`. Logos
  (`fixed/90-60/logo1.png`), the 404 image (`fixed/400-250/404.png`), avatars
  (`{id}/profile/camera_*.png`).

⚠️ What `tenant-files/` does NOT carry: the project's version-tag snapshots (`t/{tenantId}/tags/…`, each one a
whole `.mrjun` holding every earlier one) and a database dump an earlier import left at the top of the project's
files (`project-db.dump`, `project-db-<db>.dump` — the import stages the dump there). The current export leaves
both out; an archive exported before may still carry `tenant-files/tags/` and a stray `tenant-files/*.dump` — delete
them from a base you build on: they are junk, and heavy.

### 9. `integrations.json` — the project's integrations, and the data sources they provide

An **array** of the project's execution-platform integrations — the **Integration services** part. Imported, the
ones the target does not have yet are created and started (always at the registry's latest version) and the dynamic
CRUDs are bound to a running one — after the object import, in a second pass, when an integration had to be brought
up; before it when the table structure is rebuilt. Unticked, no integration is created, recreated or waited for. The
data sources they provide are bound (below) on every import that takes the pages, the database, the business logic or
the integrations — whether or not Integration services is ticked, because the charts that read an integration's data
come with the pages — from `integrations.json`, or, when the archive has none, from the same binding fields
`project-db-meta.json` carries in `integrationSources` ([§4](#4-project-db-metajson)). An import of the templates or
the roles alone binds nothing.

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

### 10. `workflow-history.json` — every version of every workflow

```json
{ "versions": [
  { "id": "6f0c…",                       // the DONOR's version id — what processes.json binds to; the target mints its own
    "identifier": "<workflow-identifier>", // the same identifier as in rep-objects.json
    "name": "…", "description": "…", "contextIdentifiers": ["…"],
    "bpmnContent": "<definitions …>",
    "deployed": true,                      // deployed on the donor → deployed again on import (with Deployment)
    "latest": false,                       // true on the workflow's current version — the one rep-objects.json carries
    "workflowStatus": "ACTIVE",            // DELETED on a deleted workflow's versions
    "creationTime": "2026-05-01T10:15:30Z" } ] }
```

The **Version history** part (it needs Workflows). Oldest first. An export that leaves **Deployment** out writes
every version — here and in `rep-objects.workflows` — as `deployed: false`, so the file then says nothing was
deployed. On import (REPORT only, Version history ticked) every version of each workflow `rep-objects.json` also has
comes back in this order, and — with Deployment ticked — each one marked `deployed` is deployed again (unticked,
every version comes back a draft) — so a process comes back on the version it was
started on, and a call activity reaches the callee version it reached on the donor. A deploy the engine refuses
is named in the import's report, and that version comes back undeployed. A **deleted** workflow's versions
(`workflowStatus: "DELETED"`) come back as rows only, never deployed: deleting a workflow deleted its deployments,
and deployed again its timer or message start events would start cases again. A workflow whose current version
the restore could not bring back (named in the report) is imported from `rep-objects.json` instead, as it would
have been without the history — it is never lost with its versions.

⛔ **Change a workflow in `rep-objects.json`, never here.** `rep-objects.json` keeps the last word on each
workflow's current version: when its row differs from this file's current one (`latest: true`) — name,
description, BPMN, contexts or the `deployed` mark — the import saves it on top, as the newest version, and
deploys it when it is marked `deployed: true`. A workflow taken out of `rep-objects.json` does not come back from
its history; a workflow only `rep-objects.json` has imports as it always did. Deleting the whole file is legal
(and so is unticking Version history): the workflows then come back from `rep-objects.json` alone, current versions
only — and Processes can no longer be ticked, because no process would have a version to land on.

### 11. `processes.json` and `process-audit-logs.json` — the project's processes

```json
{ "processes": [
  { "identifier": "…",                    // KEPT on import: business data and audit entries name it
    "workflowVersionId": "6f0c…",         // a workflow-history.json "id" — the version it was started on
    "workflowIdentifier": "…", "workflowName": "…", "groupIdentifier": "…", "businessKey": "PO-1",
    "status": "STARTED",                  // or COMPLETED, CANCELED, …
    "paramsToFilter": {}, "contextData": {}, "data": {},
    "accesses": [], "snapshots": [],      // who may see it; its node-by-node history
    "runtime": {} } ] }                   // ONLY on a running process: where it waits, its variables, tasks, timers
```

`process-audit-logs.json` is `{"logs": [ … ]}`: the audit-log entries that name one of those processes, oldest
first.

The **Processes** part (it needs Version history and Deployment) and the **Process audit log** part (it needs
Processes). ⚠️ An import that takes **Workflows** removes the target's processes with its workflows, whatever the
Processes box says — only the file's come back, and only with Processes ticked; an import that leaves Workflows
unticked leaves the target's processes alone. The import takes them only into a REPORT project, and as the very LAST
step of the whole import — after the integrations and their CRUDs — because a restored process may be due at once
and its next step calls what the rest of the import brings in
([order](#how-import-restores-it-operation-order-and-id-remapping), the last step):

- a **running** process comes back where it waited, on the version it was started on, and nothing it already did
  runs again: its tasks keep assignee, owner, priority and due date; its variables keep their types; its timers are
  due when they were due on the donor (one that fell due in the meantime fires right after the import), a repeating
  one keeps its cycle and the repetitions it has left, and a reminder that had already fired does not fire again;
  an asynchronous user task comes back entered, or still queued if it was; a failed step stays failed; a suspended
  process — or the process it called — stays suspended; and its next rule step runs as the user who completed its
  last task on the donor, as it would have there;
- an **ended** one comes back as an ended row with its data and its node history;
- then — with Process audit log ticked — their audit-log entries, moved into this project.

A process that cannot come back exactly as it was is **not imported at all**, and the import's report names it
with the reason: a multi-instance activity or an event sub-process in progress, a call activity waiting in
parallel with other branches, a called process that itself waits on a call activity or waits inside a
sub-process, a sub-process running twice at once, a step that also waits after it has run (an asynchronous leave,
a triggerable service task), a timer that failed and waits for its retry, a variable of a type an archive cannot
carry, a version that did not come back, an identifier the project already has. The rest still come. The same
checks run again on import against the version the process is rebuilt on, so a file edited since the export cannot
get a process rebuilt on a step that would run.

Processes come back only once the import has finished everything else. When its object import did not finish (the
report says why), they are not restored at all and the report says that too: retry once the cause is fixed. A
Retry — and an import resumed after a restart — imports the processes from the file again, so a step that fell
due and ran after the first attempt runs once more.

An export with Processes ticked fails rather than leave them out — when the processes, their audit log or the
workflow history they are bound to cannot be read, there is no file. An export without them never fails for want of
the history: the file then carries the current workflows only.

⛔ **Never author, edit or merge these two files.** They carry engine state only the platform writes and reads; a
changed byte can get a process refused, and a hand-made one is a process that never ran. To ship an archive without
processes, delete BOTH files; to import one without them, untick Processes. Keep `workflow-history.json` beside
them — every process names one of its versions.


### 12. `data-audit-logs.json` — the data change history

```json
{ "logs": [
  { "identifier": "…",                     // KEPT on import; an entry the target already has is skipped
    "service": "crud-service",             // every entry of this file is a change to a record
    "level": "INFO", "userId": "…", "traceId": "…",
    "logTimestamp": "…", "creationTime": "…", "modificationTime": "…",
    "content": { "scope": "CRUD", "crudAlias": "invoice", "entityId": "42", "action": "…",
                 "userId": "…", "timestamp": "…", "totalDifferences": 2, "diffs": [ … ] } } ] }
```

The **Data change history** part (it needs Database): who changed which record, and when — the history a CRUD
table's record shows, oldest first. It goes with the database it describes: imported, it **replaces** the target's
own data change history, because the records that history was about have just been replaced by the file's, under the
same ids — and so it is imported ONLY when the database restore really replaced the data. A restore that added to the
project's rows instead (no schema to scope the replace with, an import nobody chose, a database service that did not
confirm the replace) leaves the target's own history, and the report says why. The target's entries are removed first
— when that fails, nothing is imported and the report says so — then the file's are written as this project's (their
realm and client rewritten, their original times kept). The processes' audit entries are not in it; they travel in
`process-audit-logs.json`. Never author it: to ship an archive without it, delete the file; to import one without it,
untick Data change history.

### 13. `template-files/` — the images the templates show

```
template-files/
  mail-templates/<path>     ← from t/<realm>-<client>/mail-templates/<path>
  pdf-templates/<path>      ← from t/<realm>-<client>/pdf-templates/<path>
```

The images the mail and PDF templates show live outside the project's own files — under the project's realm and
client, not under its tenant id — so they travel in a folder of their own, with the **Mail and PDF templates**
part. On import (when that part is taken) they are copied into the TARGET's two folders (added and overwritten,
never deleted), and every stored image path inside a template — `t/<anything>/mail-templates/<path>` or
`t/<anything>/pdf-templates/<path>`, in a mail template's HTML, CSS and editor data and in a PDF template's JSON and
preview image — whose image the archive CARRIES here (`template-files/mail-templates/<path>`) is rewritten to point at
the target's copy. A path to an image the archive does not carry stays exactly as authored: it keeps showing whatever
that path holds (a project made from a template still shows the template project's images). A hand-built template
that shows an image therefore puts the file here and writes its path as
`t/<any realm>-<any client>/mail-templates/<path>`; the import fixes the prefix.

---

## ⛔ The Export and Import dialogs — and why an automated import must SET them

**One Export dialog and one Import dialog**, both opened from Settings → Import / Export and from the site toolbar's
Export / Import. Both draw the same switches under four headings — **Content**, **Schedulers**, **Workflows**,
**Integrations** — each heading with a switch of its own that ticks or unticks all of it ("2 of 4" beside it), and an
**Everything** switch at the top. A part that needs another is drawn under it and can be ticked only while that one
is; unticking a part unticks every part under it. A heading with a single part (Schedulers) is that part's switch.
The labels are not translated — they read the same in every interface language:

| Heading | Part (label) | What it carries | Needs |
|---|---|---|---|
| Content | `Pages, forms and rules` | the pages with their files, forms, rules, contexts, queries, plugin settings and the project's languages | — |
| Content | `Mail and PDF templates` | with the images they show | — |
| Content | `Roles and access` | role groups, who is in them, who may use which feature (Settings → Accesses) | — |
| Content | `Public API endpoints` | the endpoints only — API keys never travel | — |
| Schedulers | `Schedulers` | the schedulers (they run rules by identifier: the rules they name must be in the project) | — |
| Workflows | `Workflows` | each workflow's current version, and the process groups | — |
| Workflows | `Version history` | every earlier version of each workflow | Workflows |
| Workflows | `Deployment` | which versions were deployed — deployed again | Workflows |
| Workflows | `Processes` | the cases, running ones continuing where they stopped, on the version they were started on | Version history, Deployment |
| Workflows | `Process audit log` | the audit entries of those processes | Processes |
| Integrations | `Integration services` | the integrations the project runs | — |
| Integrations | `Database` | the project's schemas, their tables and data, and its data sources | — |
| Integrations | `Data change history` | who changed which record, and when | Database |
| Integrations | `Business logic` | the dynamic CRUDs with their SQL and Groovy methods, and the enumerations | — |

A project that is not a REPORT project shows only Pages, forms and rules; Mail and PDF templates; Roles and access;
Integration services; Business logic.

**Export.** Everything starts ticked. **Export** collects the file in the background, like an import, and the PAGE
shows it (below), not the dialog: the progress card says the part being collected with a live line within it, and
under the four headings each part's state — collected (with what it brought: *"12 workflows · 3 process groups"*,
*"48 versions"*), being collected, or still to come (*"Waiting for another project's export to finish…"* while it
queues). The file downloads by itself when it is ready, once, to the person who started it; **Your export is ready**
then stays with **Download** and **Dismiss** (and what the file does NOT carry after all, and why — business logic,
templates or integrations that could not be read are left out rather than written empty). The file waits thirty
minutes; a platform restart loses it. One export of a project runs at a time — anyone who opens the project sees it
running, and who started it. An export that would split the rules and
queries between Pages and Business logic (one ticked without the other) fails with a message saying so when the
business logic cannot be read: nothing could tell its rules from the pages'. Leaving a part out leaves its entries
out of the file (§Export shape), and an import of the file then leaves that part of the target as it is.

**Import.** Every upload opens the dialog — there is no import without it. The uploaded file is staged on the
server and the import runs exactly that file; Cancel — or closing the dialog by its X, Esc or the backdrop — discards
it. Opening the dialog clears the outcome of the previous import (its Retry would otherwise run the new file). A part
the file does not carry is drawn disabled and unticked, and says why: **"Not in this file"**, or **"Needs <parts>, not
in this file"** for one whose parents are missing ([§Which parts a file carries](#which-parts-a-file-carries));
everything the file carries starts ticked, with how many beside it ("12", or "12 · 3 running" for the processes). A
line under a ticked part says what importing it does beyond bringing it in, and a summary under the switches says
the whole import in one sentence ("Imports … Leaves … as they are."). **The import replaces exactly the ticked parts
the file carries and leaves every other part of the project exactly as it is.** Two options belong to the Import
dialog alone and sit under their part. **`Rebuild the table structure from the file` starts ticked** whenever
Database is — also when Database is unticked and ticked again; **`Recreate them from scratch` never does** (no "tick
all" ticks it):

| Option (label) | Under | Starts | What it does |
|---|---|---|---|
| `Recreate them from scratch` | Integration services | off | undeploys and deletes the project's integrations first, then creates and starts the file's — adds several minutes; only needed when an integration is broken or must come back on a newer version |
| `Rebuild the table structure from the file` | Database | **on** | DROPS each business schema and builds it again from the dump, so the tables are exactly the file's; unticked, each is emptied and reloaded and the tables keep their current structure |

What a ticked part does to the project beyond bringing its objects in (each one is said under its switch):

- **Roles and access** — groups the file does not have are removed, and with them everyone's membership of them.
- **Public API endpoints** — endpoints the file does not have are removed, together with the keys bound to them.
- **Workflows** — the project's processes are removed with the workflows they run on; only the file's come back,
  and only with Processes ticked. **Deployment** unticked: every workflow comes back a draft.
- **Integration services** — the ones this project does not have yet are created and started.
- **Database** — the data in the business schemas is **replaced**, and this project's own schemas the file does not
  contain are removed along with their data (on the storage model where a project's schemas carry its prefix; never
  the platform's own schemas). The replace reaches only the schemas the file names as its business logic's — the
  CRUDs' `sourceSchema` in `dynamic-cruds.json`, else `project-db-meta.json` → `businessSchemas`; a file with neither
  restores its dump ADDITIVELY, removes nothing, and the report says so as an error. With Pages unticked, the schemas
  this project's own data sources pointed at are kept; with Business logic unticked, the schemas this project's own
  business logic reads are kept — and when that business logic cannot be read, no schema is removed at all, and the
  report says so. The project's queries, chart copies and CRUDs that stay are re-linked to the sources the file
  brought (§Re-linking).
- **Data change history** — replaces this project's, because its data is replaced — and only when the restore really
  replaced it; otherwise the project keeps its own history and the report says why.
- **Business logic** with Database unticked: the CRUDs are attached to this project's own data sources and schemas
  (§Re-linking).

A file that carries nothing the project can take is refused before the dialog opens, and so is any upload while an
export, an import, a version tag or an environment job of the project is running (the message says which); the
Export dialog likewise refuses to start while an import runs — an export and an import of one project never overlap.
**While anything of the project runs that Export and Import wait for — an import, an export, a version tag, an
environment job — neither button is drawn**, in Settings → Import / Export or on the site toolbar. Settings shows the
running job's progress card in their place (or a line saying what else runs); the toolbar shows a small ring with
"Importing" / "Exporting" and the percentage — a click opens the same card in a dialog. A page reloaded meanwhile
draws the same card: it is read from the job itself. The card lists the job's steps under the four headings, with
the step running now and what each finished one brought — inside Workflows: the workflows, the version history, the
deployment, the processes, the process audit log, each on its own. An import that succeeded reloads the page; one that
failed or ended with warnings shows its outcome with **Retry** and **Dismiss** (on the toolbar: "Import failed" /
"Imported with warnings"). Unticking a whole heading is how to keep a
part of the target: Integrations off keeps the live database, the
CRUDs and the sources (what the old dialog's "Ignore" did), and only the content, templates, roles, endpoints,
schedulers and workflows are replaced.

Two consequences, both of which have cost a real debugging session:

* **Unticking `Rebuild the table structure from the file` keeps the project's tables as they are, and nothing tells
  you what that costs.** It starts ticked. Untick it over a schema change — a column whose type changed, one the
  file dropped or renamed — and the import reports **success**: the new SQL arrives, the old table stays, and the
  first page that reads it fails (`column t.<new> does not exist`, a type mismatch). The failure surfaces in the UI,
  minutes later, looking like a code defect. So: **leave it ticked; untick it only to keep tables the file must not
  reshape**, or a schema the rebuild refuses (Gotcha #19). The same goes for the SQL itself: it travels with
  **Business logic** — unticked, every table keeps the SQL it runs now (Gotcha #19).
* **An automated importer must set the switches explicitly, not inherit the defaults.** They
  are defaults of a dialog, not a contract — and a script that only clicks *Import* silently
  imports whatever the file happens to carry and the build happens to default to. Read each switch WITH ITS LABEL
  (match the label, never the index — the order changes), set what the change requires, log what you set and the
  summary line, and abort when a part you need is "Not in this file" or a switch you need is disabled instead of
  importing half the change. The suite's `tools/import_project.py` ([30](30-live-test-bugfix-and-autotest.md)) does
  exactly that.

⚠️ **Deployed is a mark the archive carries, not a state it ships.** With Deployment ticked, the import clears every
engine id and deploys again exactly what the archive marks deployed — every version `workflow-history.json` marks so,
in order, or, without that file, each workflow `rep-objects.json` marks `deployed: true` (its current version only).
A file in which nothing is marked deployed carries no Deployment at all ("Not in this file"). A workflow marked
`deployed: false`, one imported with Deployment unticked, and one whose deploy the engine refused (named in the
import's report) comes back a draft: every worklist on it is empty and every `service.workflow.start` throws
`workflow_is_not_deployed` until it is deployed (`nct_workflow_deploy`, or the BPMN editor).

## How import restores it (operation order and id remapping)

The full import, in the order it runs. **Every step acts only when the import takes its part — ticked in the
Import dialog AND carried by the file** ([§The Export and Import dialogs](#-the-export-and-import-dialogs--and-why-an-automated-import-must-set-them));
a step whose part is not taken leaves that part of the project exactly as it is. A Retry, and an import resumed after
a restart, replay the same choice.

**Before the file is read:**

1. Read what the file carries ([§Which parts a file carries](#which-parts-a-file-carries)) and narrow the choice to
   it. Then the entries of every part NOT taken are **left out of the archive** before anything reads it:
   `branches.json`, `branch-metadata.json`, `tenant-files/`, `favicon/` (Pages, forms and rules); `template-files/`
   (Mail and PDF templates); `workflow-history.json` (Version history); `processes.json` and
   `process-audit-logs.json` (Processes); `process-audit-logs.json` (Process audit log); `project-db.dump` and every
   `project-db-<db>.dump` (Database); `data-audit-logs.json` (Data change history). `rep-objects.json`,
   `project-db-meta.json`, `rimm-data.json`, `dynamic-cruds.json` and `integrations.json` always stay: the parts that
   ARE taken are re-linked through what they say.
2. **Recreate them from scratch** ticked: every integration of the project is undeployed and deleted.
3. **Rebuild the table structure from the file** ticked (the default) with Integration services: the integrations
   are brought up now, before the objects, so the business logic goes in with them (step 15) in one pass — the
   project's running one reused (matched by name, then by docker image, so a second pod of the same type is never
   started), a stopped one deployed, and one the project does not have — a new project's first import, a file from
   another project — created (always at the registry's latest version); each waited for until RUNNING.

**The objects** — the CMS library reads `tenant.json` (`status=published`, `name=projectName`,
`template=isTemplate`; with `branches.json` also the languages: `locales`, and `defaultLocale` when it is one of
them — without it the target keeps its own), then hands over to the application, which stages its files into tenant
properties — `rep-objects.json`; `project-db.dump` into file storage **only together with** `project-db-meta.json`
(the meta is staged on its own too, as re-linking metadata); each `project-db-<db>.dump`; `rimm-data.json` when
there is no dump; `dynamic-cruds.json` — and (for a non-admin realm) runs the object import. **⚠️ Steps 4–11 run
only into a REPORT project**; into any other type the object import is steps 12–15 alone (steps 16–18 run for every
type). When the file cannot be staged, `rep-objects.json` cannot be read, or the project cannot be read to tell what
to replace, the import stops HERE — **Import failed**, nothing changed, not even the pages; the file is kept and
Retry runs it again. A failure later in the object import is reported (*"Project object import failed: …"*, the
import ends with warnings) and is never replayed at the next sign-in.

4. **Clean-up** — exactly the parts about to be replaced, nothing else: forms, form groups, plugin settings rows
   and contexts (Pages, forms and rules); schedulers (Schedulers); workflows — with their processes — and process
   groups (Workflows); data sources (Database; a live integration's own source rows are kept unless its
   integrations are recreated); rules and queries — the content's half with Pages, the business logic's half (the
   ones its CRUD methods name) with Business logic, all of them with both, none with neither; with Business logic
   alone, also whatever the project holds under the identifiers of the file's business-logic rules and queries, so no
   rule exists twice. A clean-up that fails half-way stops the import as above (**Import failed**, the pages not
   touched, Retry).
5. **Database** (Database): the sources first — RIMM rows skipped (the restore rebuilds the RIMM source); every
   INTERNAL row moved onto THIS project's database (and, where a project's schemas carry its prefix, onto the
   prefixed schema name) and rewritten to this project's database role, whose credentials are taken from the
   project record and never rotated; an EXTERNAL row, which travels without its password, keeps this project's own
   password when the project had the very same connection (identifier, host, port, database, user); then saved.
   The SYSTEM schema is (re)provisioned. Then the dump: build the schema remap (`public→null` (skip);
   `rimm_<old>→rimm_<realm>_<client>`; **and `int_*`/`system_*`→null (skip)** unless the name is the target's own
   `system_<realm>_<client>` — a schema mapped to null is silently dropped, so a business schema must never carry
   those prefixes, see [10-database-management.md](10-database-management.md) §Export shape) and restore. Each
   schema in its own transaction; the order within a schema: `CREATE SCHEMA` → enums → sequences → tables (DDL,
   then data) → `setval` sequences → unique → check → FK → indexes → views. Schema-qualified names in the DDL are
   rewritten on remap. Imported from the dialog, each business schema the file names — the CRUDs' `sourceSchema` in
   `dynamic-cruds.json`, else `project-db-meta.json` → `businessSchemas` — is **emptied and reloaded inside that
   transaction**, or DROPPED and rebuilt with *Rebuild the table structure from the file*; an import nobody chose
   (template, tag revert, environment), and a file that names no business schema, restore **additively** (the latter
   reported as an error). Then each `project-db-<db>.dump`, the security tables and the RIMM source, the grants, the
   internal-source hosts; and — only once the restore confirmed it replaced the data — this project's own schemas
   the file does not bring are dropped: never a platform schema, never one the project's own data sources pointed at
   when Pages is not imported, never one this project's business logic still reads when Business logic is not
   imported — and none at all when that business logic cannot be read (reported). Then, when Pages or Business logic
   stays, what the project keeps is **re-linked** to the sources the file brought: its queries and its CRUDs
   ([§Re-linking](#re-linking--when-one-part-arrives-without-the-other)); a query whose source nothing stands for is
   named in the report. Database not taken: the staged dump is discarded unread.
6. **Data change history** (Data change history) — only when step 5 really replaced the data (else reported): the
   project's own is removed, the file's written ([§12](#12-data-audit-logsjson--the-data-change-history)).
7. **Re-linking** is decided — which source of this project each of the file's stands for, and where each of the
   file's schemas lands here ([§Re-linking](#re-linking--when-one-part-arrives-without-the-other)).
8. **Queries, then rules** — the halves taken: each query re-pointed at this project's source and schemas, then
   saved; an object the project keeps under the same identifier (its own business logic's, when only the pages are
   imported) is not imported over it. Then (Pages) the **contexts**, the **form groups → forms** (save the groups,
   build an `identifier→saved` map, rebind `form.formGroup` by identifier, save the forms; a form whose group the
   file lacks is dropped) and the **plugin settings rows**.
9. **Schedulers** (Schedulers).
10. **Workflows** (Workflows): every workflow `workflow-history.json` does not cover saved as a draft, then the
    process groups, then the **deploy step** — LAST of the object kinds, because a deployed workflow's first step
    resolves rules, forms, settings and process groups. With Version history: every version restored oldest first,
    and — with Deployment — each one the donor had deployed deployed again; then each workflow whose
    `rep-objects.json` row differs from the history's current one saved on top and deployed if marked; then the
    workflows only `rep-objects.json` has, deployed if marked. Without the history: every workflow marked
    `deployed: true` is deployed ([§10](#10-workflow-historyjson--every-version-of-every-workflow)). Without
    Deployment nothing is deployed.
11. **Public API endpoints** (Public API endpoints — `apiExposures` a list) — the last object step of the block,
    after every definition an endpoint names. The archive's list replaces the project's endpoints in ONE step:
    matched by `identifier`, the ones it lacks deleted with their key bindings, the kept ones keeping theirs. All or
    nothing — one invalid entry refuses the whole list, changes nothing, and the import's failure report names each
    endpoint with its reason. Keys never travel, so an endpoint new to the project arrives with none
    ([32](32-public-api.md) §6). End of the REPORT-only block.
12. **Roles and access** (any type): role groups reconciled BY NAME (§6 — the ones the file lacks deleted, Author
    and Developer never); members ADDED by external id, else by `userEmail`; feature grants replaced when
    `featureAccesses` is there.
13. **Mail and PDF templates** (any type): with a non-empty `mailTemplates` list every mail template is deleted and
    the file's saved (in a REPORT project an empty list clears them too); PDF templates are replaced only by a
    non-empty `pdfTemplates` list; every image path whose image the file carries in `template-files/` is re-pointed at
    this project's copy, every other path stays as authored ([§13](#13-template-files--the-images-the-templates-show),
    [15](15-pdf-and-mail.md)).
14. **Always**, whatever was imported: the four system mail templates put back if missing (one the file brought
    under a system alias is kept as the file has it); the Author and Developer groups with the platform's roles,
    the configured accounts in them, the project's owner among the authors and both platform accounts as members;
    the importing user becomes the owner.
15. **Business logic** (any type): imported here when the project's integration already runs — or when no second
    pass will follow (Integration services not taken, or the table structure rebuilt): see below. Otherwise at
    step 17.
16. The base layer finishes: the project's files (`tenant-files/`, `favicon/`) and the templates' images
    (`template-files/`) copied — added and overwritten, never deleted; the tenant saved; with `branches.json`, every
    branch and virtual plugin of the project deleted and the file's saved (`tenantId` overwritten,
    `virtualContent=true` recursively — **content node ids are NOT remapped**), and the published branch chosen
    from `branch-metadata.json` (by name → `master` → the first). Without `branches.json` the content is not touched.

**After the objects:**

17. **Integration services** (taken, table structure not rebuilt): the integrations the file has and the project
    does not run are created (always at the registry's latest version), deployed and waited for until RUNNING;
    when one had to be brought up and Business logic is taken, a second pass imports the CRUDs into it.
18. **Integration data sources** — on every import that takes the pages, the database, the business logic or the
    integrations: every source declared in `dataSourceIdentifiers` (of `integrations.json`, or of
    `project-db-meta.json` → `integrationSources` when the file has no `integrations.json`) is pointed at THIS
    tenant's integration schema — repointing the imported row, or recreating it under the same identifier
    ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)). Without it a statically
    integrated project imports with its charts still querying the donor's database.
19. **Processes** (Processes, REPORT only) — after every step that brings something in, the integrations' second
    CRUD pass included: a restored process may be due at once (a timer that fell due while the archive travelled)
    and its next step calls rules, CRUDs, mail templates and integrations. Each process on the version step 10
    restored it from, then — with Process audit log — their audit-log entries
    ([§11](#11-processesjson-and-process-audit-logsjson--the-projects-processes)). Every refusal is named in the
    import's report; the import then finishes "with errors".
20. **Charts** (Pages or Database): the copy of its query every chart keeps is re-synced from the query the project
    now holds and re-pointed at this project's schemas and sources — only now, because step 16 replaced the content
    tree wholesale.
21. **Feature grants onto the pages** (Roles and access): the imported grants are applied to the pages that carry
    each feature's plugin and to the sidebar links to them, once the tree is final.

The import ends **Import complete**, or **Imported with warnings** when a step recorded a problem it swallowed (the
message names each one), or **Import failed**. The progress card shows one step per part being imported (*Saving
pages and files…* whenever pages or templates are; *Deploying workflows…* only with Deployment), in this
order — *Removing old integrations…* (Recreate them from scratch), *Importing project…*, *Restoring the database…*,
*Importing the data change history…*, *Importing pages, forms and rules…*,
*Importing schedulers…*, *Importing workflows…*, *Deploying workflows…*, *Importing API endpoints…*, *Importing roles
and access…*, *Importing mail and PDF templates…*, *Importing the business logic…*, *Saving pages and files…*,
*Creating integrations…*, *Deploying integrations…*, *Waiting for integrations to start…*, *Importing the business
logic…* (the second pass), *Restoring processes…* — and a part not taken has no step. With the table structure
rebuilt, the three integration steps come right after *Importing project…* instead, and there is no second pass; an
integration step nothing needs — the pod already runs — is dropped before it starts.

### Re-linking — when one part arrives without the other

Nothing in a project points at another part by database id — a query names its source by `sourceIdentifier`, a CRUD
its source and `sourceSchema`, a context its CRUDs by alias, a rule its context by identifier. So when one half
arrives and the other stays, the import re-links what arrives to what stays:

| Arrives | Stays | How it is re-linked |
|---|---|---|
| queries, CRUDs (Pages, Business logic) | the data sources (Database not imported) | each of the file's `sources` is matched to one of THIS project's: by `identifier`; for an INTERNAL source, by the schema it lands in here; else by the same type and name. A reference to a source matched to nothing is imported as it is, and the report names the queries that read it ("Import the database too, or add the source"). The donor's RIMM source (`project-db-meta.json` → `rimmSourceIdentifier`) always maps to this project's own |
| the SQL — queries, SQL method scripts, CRUDs' `sourceSchema`, charts' own queries | the schemas | every `<donor schema>.` qualifier rewritten to where that schema lives here: the map the restore used when a dump was restored, else the one derived from the file's INTERNAL `sources` and the donor's `schemaPrefix` in `project-db-meta.json` — which is why the meta travels without the dump |
| the business logic | the database | each CRUD bound to this project's source the mapping above names; a RIMM-backed one to the project's RIMM source; else to the project's own INTERNAL source on the schema the CRUD reads. The dialog says it: *"The database stays as it is: the CRUDs are attached to this project's own data sources and schemas, matched by name."* |
| the database | the business logic | the schemas this project's own CRUDs read are never dropped by the database replace — and when that business logic cannot be read, no schema is dropped at all (the report says so) |
| the database | the pages | the schemas this project's own data sources pointed at are never dropped by the database replace |
| the pages (their contexts) | the business logic | each context exposes what it exposed here plus what the file's context exposes — minus only the aliases of DYNAMIC CRUDs that are gone; a static integration's CRUDs and `bl` itself always stay |
| the business logic | the pages | each of the project's contexts gets back what it exposed before, plus what the file's context of the same identifier exposed — minus only the aliases of dynamic CRUDs that are gone now |
| the database (its sources) | the pages or the business logic | each source the import replaced is mapped to the one standing for it now — the RIMM source to the rebuilt one, any other to the same type on the same schema, then the same type and name — and the project's own queries, the copies its charts hold and its CRUDs are re-pointed to it. A query whose source nothing stands for is named in the report |
| the pages (their rules and queries) | the business logic | the project's own CRUD-method rules and queries are spared by the clean-up and never imported over |
| the business logic | the pages | only the CRUD-method rules and queries are replaced; every other rule and query stays |
| schedulers | the rules | nothing to re-link — a scheduler names its rules by identifier, and they must be in the project |
| role assignments | the members | a member is found by the external id the file names, else by `userEmail` (the id is the donor realm's) |

### The dynamic-CRUD import — in detail

The **Business logic** part, at step 15 or step 17 above:

1. Parse `dynamic-cruds.json`.
2. No integration deployed for the project yet → skipped here, for the second pass to do; then a probe
   `bl.getCruds` checks that `bl` (dynamic-integration) answers — otherwise skipped. On the LAST pass either skip is
   reported ("…none of the N integration table(s) could be imported").
3. **Clean slate**: every dynamic CRUD of this (realm, client) is deleted — `cruds: []` in the file leaves the
   project with none.
4. The enumerations — when the file has `enums` — replace the project's ([§7](#7-dynamic-crudsjson--dynamic-only)).
5. Load the live sources by identifier.
6. For each GROOVY method with a `ruleIdentifier` and a `script`: **ensure the hidden Groovy rule** (below).
7. Every CRUD with its whole graph in ONE call (an older `bl` gets the per-CRUD calls instead: `bl.create({alias,
   name[, access]})` — `access` only when the archive carries one; absent = signed-in users — `bl.setSource`,
   `bl.setLocalizationField`, `bl.addMethod({methodName, methodType, script, returnType, returnsArray, methodOrder,
   ruleIdentifier, queryIdentifier, contextIdentifiers[, inheritAccess, access]})`, `bl.addParameter`,
   `bl.setReturnFields`, `bl.addDtoField` / `bl.addFilterField`). Each CRUD is bound to a source of THIS project —
   the one its `sourceIdentifier` is re-linked to ([§Re-linking](#re-linking--when-one-part-arrives-without-the-other)),
   a RIMM-backed CRUD to the project's own RIMM source, else the project's INTERNAL source on its `sourceSchema` —
   and **its credentials are taken from that live source**; the exported coordinates are only a fallback, and carry
   no password. A CRUD that resolves to no source is left without credentials (logged only).
8. Rebind every CRUD to its source: push the current credentials of the source each one names — or, when the
   project has no source of that identifier, of its own source on the schema the CRUD reads — into every
   `dynamic_crud` row via `bl.setSource`.
9. The contexts get their CRUDs back. Deleting a CRUD strips its alias from every context, and creating it never
   adds it back; so with Pages imported, the file's contexts get the `crudAliases` the file gives them; without
   Pages, every context of the project gets back what it exposed before the import, plus what the file's context of
   the same identifier exposed — minus only the aliases of dynamic CRUDs that are gone now (a static integration's
   CRUDs and `bl` itself always stay).
10. Fewer CRUDs than the file declares → the integration is asked what it actually holds, and a real shortfall is
    reported ("N of M integration table(s) are present after the import").

### The hidden Groovy rule

A GROOVY method runs the **hidden** rule its `ruleIdentifier` names. A platform export carries that rule in
`rep-objects.rules[]` — with Business logic — and the import saves it like any other rule; an archive built by hand
does not, and the import then **creates** it from the method's own `script`, but only when the project has no rule
of that identifier yet: a rule the file brought is never overwritten by the script. Without either, the first call to
the method fails with `"Rule not found with identifier: <ruleIdentifier>"`. The rule it creates:
`name="crud_<alias>_<methodName>"`, `executor="GroovyExecutionRule"`,
`ruleType=EXECUTION_RULE`, `status=ACTIVE`, `rule.ruleScriptStr=<script>`, `hidden=true`,
`identifier=<method.ruleIdentifier>`. It is created with **no** `access`, and
needs none: a hidden rule's own access is ignored — callers are checked against the method's
([11 §"Execution access"](11-business-logic-dynamic-crud.md)).

### What is remapped and what is not

| Entity | id/identifier on import |
|---|---|
| Content (branches.json) | node ids are **preserved as-is**; `branch.tenantId` is overwritten |
| rep-objects (all except roleGroups) | `id:null` on export (key present, value null) → new id on import; relationships by `identifier` |
| roleGroups | id is **not** nulled on export; on import reconciled BY NAME — a group the project has keeps its own id and members and takes the file's roles, a new one is created with a new id |
| userRoleGroupAssignments | the member found by `userId` (the donor realm's external id), else by `userEmail`; the group by `roleGroupName`; added, never removed |
| featureAccesses | by feature name; a name this platform does not know is skipped |
| `form.formGroup.id` | nulled on export → import maps the form to the group by `identifier` |
| `query.sourceIdentifier` (RIMM) | remap old RIMM identifier → this project's RIMM source |
| `query.sourceIdentifier`, CRUD `sourceIdentifier` (Database not imported) | re-linked to this project's source: by identifier, by the schema it lands in, by type and name; unmatched → imported as it is, named in the report ([§Re-linking](#re-linking--when-one-part-arrives-without-the-other)) |
| `query.sourceIdentifier` (integration data) | **not** remapped — the SOURCE ROW is rebound instead (repointed, or recreated under the declared identifier), so queries, chart embeds and CRUDs all follow without being touched ([§9](#9-integrationsjson--the-projects-integrations-and-the-data-sources-they-provide)) |
| schema qualifiers in SQL (queries, SQL method scripts, CRUD `sourceSchema`, charts' own queries) | rewritten donor schema → this project's — from the restore's map, else from the file's INTERNAL `sources` and `project-db-meta.json.schemaPrefix` |
| `source.dbName` | INTERNAL rows forced onto this project's database (and prefixed schema) |
| INTERNAL source creds | rewritten to the new project-level role |
| EXTERNAL source password | travels empty; kept from this project's own row when it is the same connection |
| DB schema `rimm_<old>` | remap → `rimm_<realm>_<client>` |
| DB schema `public` | **skipped** (mapped to null) — Kafka-managed tables |
| DB schema `int_*` / `system_*` (≠ the target's own `system_<realm>_<client>`) | **skipped** (mapped to null) — assumed to be the donor's integration/liquibase registries. Silent: logged only. A business schema named this way loses ALL its tables and rows on import ([10](10-database-management.md) §Export shape) |
| dynamic CRUD | recreated entirely via `bl.*`; new ids; source creds from the live src_source |
| hidden Groovy rules of methods | carried in `rules[]` with Business logic; created from the method's `script` only when the project lacks the `ruleIdentifier` |
| contexts' `crudAliases` (Pages without Business logic, or the reverse) | what the context exposed here plus what the file's exposes, minus only the aliases of dynamic CRUDs that are gone (static CRUDs and `bl` stay) |
| the project's own queries, chart copies and CRUDs (Database imported, Pages or Business logic kept) | re-pointed from each replaced source to the one standing for it now: RIMM → the rebuilt RIMM source, else same type + schema, else same type + name |
| template images (`template-files/`) | copied into this project's folders; the path of each image the file carries rewritten to its copy here, every other path left as authored ([§13](#13-template-files--the-images-the-templates-show)) |
| workflow versions (`workflow-history.json`) | each gets a new id; `identifier`, order and creation times kept; the deployed ones deployed again (with Deployment), under new engine ids |
| processes (`processes.json`) | new row ids and new engine instances; `identifier`, business key, data and node history kept; the process's own row id among its variables rewritten to the new row |
| process audit entries (`process-audit-logs.json`) | moved into this project; `identifier` kept; an entry the project already has is skipped |
| data change entries (`data-audit-logs.json`) | moved into this project (realm and client rewritten); `identifier` and times kept; an entry the project already has is skipped |
| `apiExposures` (API endpoints) | `id` nulled on export, `identifier` kept; reconciled by `identifier` as one list; their descriptions for AI assistants travel with them; key bindings never travel and survive only on the endpoints the list keeps, and the keys themselves (with their marks) are never touched by an import ([32](32-public-api.md) §6) |

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
[…]: {…}`) pushes the one
actionable sentence out of sight and turns a fixable report into a shrug. If you add a hop, unwrap.

## Static vs Dynamic — the exact difference at the file level

| Aspect | STATIC | DYNAMIC |
|---|---|---|
| `dynamic-cruds.json` | **absent** | **present** (`exportVersion:1`, N CRUD) |
| CRUD business logic | compiled Java CRUD beans in a separate microservice; resolved by name (`service.crud.product.find`) | defined in the project (`bl`/Business Logic); stored in `dynamic-cruds.json`; methods = SQL(→query) or Groovy |
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
   - `sources[]`: one INTERNAL source object per business schema (`identifier`=UUID,
     `dbType:"POISTGRESQL"`, `dbName`, `schemaName=<prefix>_app`, `hostName`, `port`, a non-blank
     `userName` — a blank one makes the platform REJECT the object). ⚠️ The baseline
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
   import via authoring **into a REPORT tenant**, with every part the file carries ticked (the dialog's default —
   `mrjun.py inspect` lists them first). Import itself will: restore the DB, remap
   ids/source creds, recreate dynamic CRUD via `bl` and the hidden Groovy rules of methods. Keep every
   `rep-objects` key the baseline has: a part's key left out is "none", not "keep" (Gotcha #20).

---

## Gotchas

1. **`id` = `null`, but the key is present.** In rep-objects, an object's `id` field serializes as `"id": null`
   — the key is **not** removed. Verified:
   `jq '.rules[0]|has("id")'` == `true`, `.rules[0].id` == `null`. Relationships hold on `identifier`
   (UUID). Write `"id": null` by hand and set consistent `identifier`s. Exception:
   `roleGroups` (id not nulled on export, but still created with a null id on import).
2. **Content ids are NOT remapped.** `branches.json` nodes are saved with their `id`/`identifier` as-is.
   Ensure uniqueness of page `identifier`/`uniqueIdentifier`/aliases yourself
   (an alias collision breaks routing — a known form-page problem).
3. **The config slot depends on the plugin.** Form controls → `properties.settings.stringValue`; table
   plugins (`crud.table.plugin`/`crud.tree.plugin`/`process.table.pluin`) → `properties.model.stringValue`.
   Confusing the two = the plugin won't read its config.
4. **`dynamic-cruds.json` may be absent.** It's absent if `bl` isn't deployed, the project has no
   dynamic CRUD and no enumeration, or the export left Business logic out — and then an import leaves the target's
   business logic exactly as it is. For a static project it should not be there. An import that takes it into a
   target where no `bl` answers skips it — and says so in the report once no later pass will try again; then the
   CRUDs are not created.

   ⛔ **A type error in the envelope is skipped just as silently, and it is the worse one.**
   `exportVersion` is the **integer** `1` — a platform-produced export carries `1`, and the toolkit
   writes `1`. A STRING there — `"1"`, and certainly `"1.0"`, which does not
   coerce — throws while the file is parsed. Because the dynamic-CRUD import is the LAST step of
   the object import, everything else has already landed: pages, rules, queries, contexts, forms,
   workflows, mail/PDF templates and the restored database all arrive, and only the business logic is
   missing. What the customer reports is not "the import failed" but **"every register shows headers and
   no rows"**, with `No RSocket connection found for CRUD alias: <alias>` in the UI and an empty
   Business Logic console — a symptom that reads like a dead runtime rather than two characters in the
   archive. `validate` now ERRORs on it; nothing else does — `pack`
   never reads the file's types and the import report does not name the step it skipped.
5. **Hidden Groovy rules of methods travel in rep-objects — with the Business logic.** A platform export carries
   every hidden rule; the ones a CRUD method names go with Business logic, the rest (autocomplete, tree settings)
   with Pages. The import saves the archive's copy as it is and creates a method's rule from its `script` ONLY when
   the project has no rule of that identifier — so in a base exported from a live project, **a changed `script`
   alone changes nothing**: change the rule in `rules[]` with it, or delete that rule so the import builds it from the
   script (`validate` ERRORs while they differ). A hand-built archive carries none and gets every one from the
   scripts ([§The hidden Groovy rule](#the-hidden-groovy-rule)).
6. **SQL placeholder syntax differs.** `method.script` in `dynamic-cruds.json` uses
   `:param`; `query.query` in `rep-objects.json` uses `{name:'param', type:'integer'}`. These are **different**
   representations of the same query; keep them consistent.
7. **project-db.dump is not pg_dump.** It's a custom JSON `nct-jdbc-dump-v1`; a `pg_dump` binary
   import won't understand it. Row values are **always strings** (`rows[].col` is string|null); restore typing
   is driven by `columnTypes` (JDBC `Types`).

   ⛔ **An unquoted number in `rows[]` loses the whole schema.** This is not a tidiness rule — it is the
   restorer's signature. The restore reads every row value as a string, so a JSON `1` arrives as a number and
   throws `class java.lang.Integer cannot be cast to class java.lang.String`. That is a type error, **not** a
   SQL error, so it misses the per-table savepoint that exists to keep one bad table from poisoning the rest —
   it unwinds the whole schema restore and the caller reports:

   > Imported with warnings — The database was NOT replaced. Schema(s) `[x]` were rolled back to their
   > previous contents … Cause: class java.lang.Integer cannot be cast to class java.lang.String

   The import otherwise "succeeds": content, rules and CRUDs all land, so the project opens with every
   page rendering and **every table, chart and worklist empty**. Read as a database-shape problem; caused
   by one unquoted integer.

   | field | JSON type the restore requires |
   |---|---|
   | `tables[].rows[].<col>` | **string** or `null` — including integers (`"1"`), booleans (`"true"`/`"false"`), numerics (`"1200.00"`) and jsonb (the JSON **as a string**) |
   | `tables[].columnTypes[]` | **number** (JDBC `java.sql.Types` code) |
   | `sequences[].lastValue` | **number** |
   | `tables[].columns[]`, `foreignKeys[]`, `indexes[]`, `checkConstraints[]`, `uniqueConstraints[]`, `triggers[]`, `views[]`, `functions[]` | string |

   Every dump the platform EXPORTS is string-typed by construction, so
   **no reference export can show you this by contrast** — only a generated or hand-edited dump can carry it,
   and it is invisible to any offline check that loads the file with Python's `json`, where `1` and `"1"`
   behave alike. Build the rows through `db_cmds.normalise_rows(columns, rows)` / `db_cmds.dump_cell(v)`,
   and `mrjun.py validate` ERRORs if one slips through.
8. **`public` and Kafka tables.** The `public` schema is skipped on restore (`public→null`), and
   the tables `users`/`role_groups`/`users_has_role_groups` are excluded from the dump and
   recreated on import. Don't put business tables in `public` — they won't be restored.
9. **INTEGRATION/SYSTEM source schemas are excluded from the dump** (by source type) —
   managed by the execution platform and recreated on the target side. The exclusion goes by
   the schema name of those sources that are actually present and of type INTEGRATION/SYSTEM.
   Note: `int_*` schemas routinely **still end up in the dump** when `rep-objects.sources` is empty —
   i.e. no INTEGRATION/SYSTEM source row was found for those schemas to exclude them. Conclusion: the mere
   presence of `int_*` in the dump doesn't mean the exclusion mechanism failed; it only works when
   there's a corresponding source row of the required type. When building by hand, don't rely on
   automatic exclusion — put in the dump only what should be restored. **But an `int_`-prefixed schema
   can also be the *business* schema** — see Gotcha #16.
10. **`tenant-files/*.dump` and `tenant-files/tags/` are junk.** The current export leaves both out; an archive
    exported before may still carry a `project-db.dump` left over from import staging (`t/{tenantId}/project-db.dump`)
    and every version-tag snapshot of the project (`tags/`, each a whole `.mrjun`) — delete them when building.
11. **Source creds are overwritten on import.** Don't count on `sourcePassword`/`sourceUser` from
    the export surviving: INTERNAL sources and dynamic CRUD get the project-level role of the target cluster. `sourceIdentifier` must point to an
    actually existing (imported) source, otherwise it falls back to stale exported creds with
    a warning.
12. **⚠️ The `type==REPORT` gate — the most important precondition.** Only a REPORT project has every part. If
    the source tenant is not REPORT, its export carries only the pages (content trees and files, no rules, forms,
    contexts, queries or settings), the templates, the roles, the integrations and the business logic — the other
    `rep-objects` keys are absent; if the target is not REPORT, its Import dialog offers only those five parts, and an
    import nobody chose skips everything else (sources/DB/queries/rules/contexts/forms/settings/schedulers/workflows/
    endpoints) silently. Build for a REPORT tenant.
13. **DB staging requires BOTH files.** `project-db.dump` **and** `project-db-meta.json` must
    both be present, otherwise the dump is never staged nor restored — and the file carries the Database at most
    through its own data sources (an older file without the meta's `"database"` mark), which then replace the
    target's with no data behind them. Write them as a pair ([§4](#4-project-db-metajson)).
14. **`branch-metadata.publishedBranchName` must match** `branches[].name`, otherwise the published
    branch is selected by fallback (`master` → the first).
15. **A form with a "dangling" group is dropped.** The `forms` export drops a form only if its
    `formGroup.identifier` is **non-null** and not among the exported `formGroups`; forms
    with `formGroup == null` or `formGroup.identifier == null` are **kept**.
    So the number of forms in the export can be smaller than the authored one. Keep each form bound to
    an existing group.
16. **⚠️ Don't identify the business schema by name prefix — an `int_`-looking name can be the business
    schema.** A *dynamic* project built on top of a schema that an integration service originally created keeps that
    schema's generated name (`int_<realm>_<client>_<hash>`): its tables and rows ride **inside**
    `project-db.dump`, and every dynamic CRUD points `sourceSchema` at it (`dynamic-cruds.json`). This is *not* an excluded INTEGRATION/SYSTEM schema (contrast Gotcha #9).
    **Identify the business schema by which schema the CRUDs' `sourceSchema` points at, NOT by name prefix** —
    an `int_`/`system_`/`app_` prefix is just a name, not a type. (In a *static* project the `int_*`
    schemas really are integration schemas with no CRUDs behind them; the two cases are distinguished only
    via `dynamic-cruds.json` → `sourceSchema`.) **But the importer does not make that distinction** — it skips
    every `int_*`/`system_*` schema on restore (step 4 above). So an `int_`-named business schema is readable and
    correct as a *description*, and yet cannot be re-imported: rename it first
    ([10-database-management.md](10-database-management.md) §Adding an entity to a FILLED dump).
17. **⚠️ Import is DESTRUCTIVE — every part it takes is a full REPLACE, not a merge.** Into a REPORT tenant, the
    clean-up the object import opens with ([§How import restores it](#how-import-restores-it-operation-order-and-id-remapping),
    step 4) **wipes the target's objects of every part it takes** before saving the file's; and the dynamic-CRUD
    import runs its own clean-slate — `bl.deleteCrud` for **every** existing dynamic CRUD of the (realm, client)
    before recreating. What the import does NOT take stays exactly as it is — that, not a merge, is how to keep a part:
    untick it. Within a part there is no "merge" mode: you cannot import ONE changed rule into a populated tenant,
    only the whole list it belongs to. To change one entity in a live project, edit the source `.mrjun` and re-import
    the part that holds it (the modify-and-reimport scenario C in
    [19-build-decision-procedure.md](19-build-decision-procedure.md)) — which parts and options you need depends on
    what your delta touched, Gotcha #19.

18. **⚠️ The file is not the platform — and "the setting didn't save" usually means "the archive was never
    imported".** Editing `branches.json`/`rep-objects.json` and re-packing changes **nothing** in a running
    tenant until the archive is imported (and the import replaces every part it takes, Gotcha #17). The failure looks
    like a platform bug: the settings panel shows the field **empty**, because a stored rule identifier is
    looked up by identifier — an id that
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

19. **⚠️ Every upload asks which parts the file replaces — and the answer decides whether your DB and CRUD work
    lands at all.** Settings → Import/Export (or the site toolbar's Import) is the only route a hand-assembled
    `.mrjun` takes into the platform, and every upload opens the Import dialog first
    ([§The Export and Import dialogs](#-the-export-and-import-dialogs--and-why-an-automated-import-must-set-them)).
    Everything the file carries starts ticked, so an archive built on the baseline replaces its whole project by
    default; what decides the rest is what you untick, and the two options:

    | What your delta touched | Tick | What the platform does |
    |---|---|---|
    | everything — a first import, a build from the empty baseline, the fix loop after a schema change | everything (the defaults, **Rebuild the table structure from the file** included) | every part replaced; each business schema DROPPED and rebuilt from the dump, so the tables are exactly the archive's; the project's running integration reused, or — on a project that has none — the file's created and started before the objects. Refuses a schema, changing nothing in it, that holds something the archive cannot put back (see below) |
    | only the rows — the project's tables must keep the structure they have | **Database**, with **Rebuild the table structure from the file** unticked | the business schemas' ROWS replaced from the dump with their **structure preserved** — tables the dump carries are emptied and reloaded, and a column the archive adds is added, but a column whose type changed, or one the archive dropped, stays as the project has it |
    | only pages, forms, rules, templates — a project whose live database must survive | untick the **Integrations** heading (Integration services, Database, Data change history, Business logic) | the live integration, its schema, its data, the CRUDs and the data sources are left untouched — what the old dialog's "Ignore" did. ⛔ Your SQL does not arrive either (below) |
    | SQL, a CRUD, a method | **Business logic** — with **Database** also ticked, the rows go back to the dump; unticked, the CRUDs attach to the project's own schemas | the CRUDs replaced as a clean slate, with their SQL and their hidden rules |
    | a broken integration, or one that must come back on a newer version | **Integration services** + **Recreate them from scratch** | the project's integrations torn down and recreated before anything else — adds several minutes (a wait allowed ten minutes) |
    | — | **Cancel** | nothing is imported, and the uploaded file is discarded |

    ⛔ **Business logic unticked does not merely skip the CRUDs — it skips your SQL.** A dynamic CRUD's SQL method
    runs the `script` stored on the METHOD (`dynamic-cruds.json` → the `bl` integration), **not** the `queries[]` entry
    in `rep-objects.json` that carries the same statement — and that query travels with the business logic too. Proven
    live: saving a new statement onto the query row (its id, its identifier, accepted and echoed back by the API)
    changed nothing — the method kept returning what the old text selected. The `queries[]` copy is what the import
    writes and what an offline validator can diff; the method's own script is what executes. Two consequences. First,
    an import without Business logic leaves every SELECT exactly as it was while the pages, forms and rules become the
    new ones — and it reports success either way. Second, the only live channel for a SQL change is the method itself
    (`updateMethod` in the business-logic API), so a query-level write is not a shortcut around a full import. The
    failure is silent and the screen cannot show it — a register looks identical whether or not the join you added
    took effect. **Check a SQL change by calling the method** (execute it over MCP, or open a row and read the field
    the change was supposed to add), never by reloading the page. When the delta touches any SQL, Business logic has
    to be ticked — and with Database ticked too it will replace the rows, so plan the live test data you will have to
    re-enter afterwards (untick Database to keep them).

    ⚠️ **A full import is not free, and a series of them can exhaust the server.** Each one restores the
    dump and replays the business logic inside the same JVM; after roughly a dozen in one working day an
    environment answered `Import failed — Java heap space`, then stopped answering database queries for
    several minutes while the pool drained, and logged the browser session out. The failure landed at the
    TAIL of the pipeline — content, rules, cruds, queries, the dump and the workflows had all been applied,
    only roles and deployment had not — so the project was left running but undeployed rather than broken,
    and the "Retry" button failed the same way. Two practical consequences: **batch your edits** so one
    import carries many of them instead of one each — and untick what the delta did not touch, which is also
    the cheapest import — and after such a failure **check what actually landed**
    (call a changed method, list the workflows) before assuming the import did nothing.

    **Rebuild the table structure from the file** starts ticked, and it is the only choice that makes the archive
    authoritative about **structure** — after you change a column's type, drop a column, or rename one, the import
    without it leaves the project's old shape in place and the reload then fails or half-lands, while the rebuild
    produces exactly the tables the archive describes. Untick it only to keep the project's tables as they are.

    ⚠️ **With the rebuild, the integrations come up BEFORE the objects** — when Integration services is ticked and
    Recreate them from scratch is not — because the business logic then goes in in one pass, into a running pod. The
    project's live integration is reused (matched by name, then by docker image, so a second pod of the same type is
    never started), a stopped one is deployed, and one `integrations.json` names that the project does not have — a
    new project's first import, a file from another project — is created and waited for until RUNNING. One that
    cannot be brought up does not cost the rest: the import goes on, says the business logic was not imported, and
    Retry runs it all again.

    ⚠️ **Rebuild refuses rather than destroys.** Before dropping anything it inventories what the dump format
    provably cannot recreate, and if the schema holds any of it the import stops with those objects named and
    the schema untouched: a table called `users`, `role_groups` or `users_has_role_groups` (skipped by bare name
    on both dump and restore, so it is never exported); a materialized view, foreign table or partitioned table;
    an identity or `GENERATED … STORED` column; a column with a non-default `COLLATE`; a standalone composite
    type or domain; an aggregate or window function; or a foreign key with one end in another schema, in either
    direction. Every one of those survives the default (Database without the rebuild) — that is what "preserves
    structure" buys — so a refusal is a signal to import that project without the rebuild, not a bug. A schema built
    through the platform's own CRUD builder trips none of them.

    Rebuild is also stricter about the reload itself: after a drop, "already exists" is impossible, so a table,
    constraint, index, view, function or trigger the archive describes and that does not come back is a hard
    failure for that schema (rolled back intact) rather than a line in a service log. The default keeps warning
    and carrying on, because there the object it failed to create is usually still there from before.
    ⚠️ **A part left unticked succeeds silently.** Nothing errors, the import reports done, and the symptoms of
    the wrong answer — data missing, CRUDs unchanged, sources untouched — are the same set the deserialization-abort
    table above attributes to a different cause, so the post-mortem starts in the wrong place. Whoever drives the
    browser must be told which switches to set; the summary line under them says what the import will do — read it
    before pressing Import — and after the import, verify that a table you changed really carries its new rows.

20. **Leave a `rep-objects` key out only together with its part.** Only the evidence keys (`mailTemplates`,
    `pdfTemplates`, `roleGroups`, `apiExposures`, `schedulers`, `workflows`) decide whether their part is carried;
    every other key is read once its part is imported, and absent then means **none** — an archive with
    `branches.json` and no `settings` removes the target's settings rows and brings none (§6). Equally, ADDING one
    object to a list the archive does not carry turns that part ON: `mailtemplate add` into an archive without
    `mailTemplates` makes it carry the templates, and the import then replaces every mail template of the target
    with that one.
21. **`[]` is a statement; absent is not.** `apiExposures: []` deletes every endpoint with its key bindings;
    `roleGroups: []` deletes every role group but Author and Developer, with everyone's membership of them;
    `featureAccesses: []` takes every feature grant away; `mailTemplates: []` deletes every mail template of a REPORT
    project (the four system ones come back); `enums: []` deletes every FREE enumeration. Only `pdfTemplates: []`
    leaves the target's PDF templates alone. Absent keeps the target's in every one of these cases.
22. **What a file carries is read from the file — so a missing piece silently drops a whole part, and a stray one
    adds a part.** A dump without `project-db-meta.json`, no workflow version marked `deployed: true` (Deployment),
    `processes.json` without `workflow-history.json`, an entry whose JSON does not parse — each makes its part "Not in
    this file" ("Needs …, not in this file"), and the import never takes it. The other way round, a meta without the
    `"database"` key and a `rep-objects.sources` holding any source of the project's own make the file carry the
    Database even with no dump — and its import replaces the target's data sources; say `"database": false` to keep
    them. `mrjun.py inspect` prints what the file carries before you upload it.
