# 13 — Master Playbook: empty project → full dynamic-CRUD project

**What this is.** A step-by-step guide to assembling an entire project on the platform (Dokie / NCT) **directly in
the `.mrjun` export files**, without a browser. The starting point is the empty baseline bundled with this
library — `initialtemplates/empty.mrjun`, either packed or unzipped into a working directory
(referred to below simply as `empty`); the result is a filled-in set of files that the
user **reimports** to get a working application with **dynamic CRUD integration**
(business-logic inside the project: SQL/Groovy on top of its own DB).

> **This doc is the write-order + dependency layer.** The *decision* layer — what to decide, in what order, and
> when a phase is done (and which scenario you're in: empty / wire-existing / modify-filled) — is
> [19-build-decision-procedure.md](19-build-decision-procedure.md). Decide there, then assemble in the order here.

**How to use this (two-step flow).**
- **Step 1 (planning).** Another Claude reads the PRD (business requirements) + this library and writes
  an *instruction document* for the specific project: the filled-in Phase-1 inventory plus the per-phase
  Decide answers of [19](19-build-decision-procedure.md) — that IS the format, there is no separate template.
  It references the files of this library (`00`…`12`) for every "how to do X".
- **Step 2 (assembly).** Yet another Claude takes the `empty` export, unpacks it, and following the instruction document +
  this playbook **writes** `branches.json`, `rep-objects.json`, `dynamic-cruds.json`, `project-db.dump`,
  then the user reimports.

> Everything is done for the **dynamic** integration (business logic authored inside the project). The static
> path (compiled Java `@Crud` beans) is not re-created in a project from an export — see
> [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) §"dynamic vs static".

---

## 0. Map of the reference library (links for the instruction document)

| Topic | File |
|---|---|
| **Decision spine** — which scenario, what to DECIDE in what order, when each phase is DONE (routes into every file below) | [19-build-decision-procedure.md](19-build-decision-procedure.md) |
| Anatomy of `.mrjun`, all file schemas, export/import, the `type==REPORT` gate | [00-export-format-and-import.md](00-export-format-and-import.md) |
| Content tree, pages (`siteMapPage`), tabs, layout, `roleAccess`, virtualPlugins | [01-content-model-and-pages.md](01-content-model-and-pages.md) |
| All form controls: settings JSON + HTML + mapping/validation/events | [02-form-controls-reference.md](02-form-controls-reference.md) |
| Generate fields from CRUD: generating each field (HTML wrapper, label+field plugin) | [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) |
| CRUD Table plugin: settings, columns, filters, actions (default/custom, direct/non-direct), import | [04-crud-table-plugin.md](04-crud-table-plugin.md) |
| CRUD Tree + Process Table plugins (deltas relative to CRUD Table) | [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) |
| Form Groups, landing, predicate→form mapping, Create Default Actions, naming | [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) |
| Workflows, BPMN, elements, user task, all task types, processes | [07-workflows-and-tasks.md](07-workflows-and-tasks.md) |
| The 3 types of Groovy rules + templates + context model (how a rule reads context in crud/process/form/list) | [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) |
| Groovy hints (server HintsService) vs live context-data hints | [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md) |
| Database Management plugin + `project-db.dump` (schema/table/column/index/constraint/sequence/trigger) | [10-database-management.md](10-database-management.md) |
| Business Logic plugin: dynamic CRUD, dtoFields, filterFields, methods (SQL/Groovy), sources | [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) |
| Queries, sources, schedulers, roleGroups, settings, mailTemplates | [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) |
| **Full plugin catalog** — every `pluginName`, one by one (HTML/label/image/link/help/tab, `action.button`, `chart.js`, `global.replacement`, all `admin.*`/system) | [14-plugin-catalog-all.md](14-plugin-catalog-all.md) |
| **Field-level config reference** for 63 of the 64 plugin names — each one's settings panel, JSON config slot and field-by-field table | [14a-plugin-config-reference.md](14a-plugin-config-reference.md) |
| **Charts, params & filtering-through-params** — `chart.js.plugin` data binding (`$$()` -> `ChartJsReplacement` queries), query params, the `global.replacement` filter bar, click-to-cross-filter, theme-safe rendering | [22-charts-params-and-filters.md](22-charts-params-and-filters.md) |
| **PDF templates + Mail templates** + the Groovy flow "generate a PDF from a template → send it by mail" | [15-pdf-and-mail.md](15-pdf-and-mail.md) |
| **Full Groovy `service.*` capability surface** (what you can actually do in a script: crud/global/security/rimm/report/notification/…) | [16-groovy-service-api.md](16-groovy-service-api.md) |
| **Left-nav quick links** — add a sidebar quick link/group via the `modelGroups` tree on `site.kicker.plugin` (`left-nav`) | [17-left-nav-quick-links.md](17-left-nav-quick-links.md) |
| **Reverse scenario** — wiring an EXISTING populated schema + complete UI to dynamic CRUDs (CHECK/audit/single-company, enum snapshots, document lines + delete cascade, verify against real rows) | [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) |
| **Localization** — the L0–L5 layer model, key-based UI strings, entity-data `localize`, runtime resolution + Groovy locale, auto-translate | [20-localization.md](20-localization.md) |
| **Homepage & redirect** — how the bare root URL resolves + the `Redirect` content-alias path; never ship an empty Home | [21-homepage-and-redirect.md](21-homepage-and-redirect.md) |
| **Distribution, the live-debug loop & known gaps** — what a recipient still needs, where bugs surface, the runtime classes `validate` cannot catch | [23-distribution-and-known-gaps.md](23-distribution-and-known-gaps.md) |
| **Authored HTML as a component** — the HTML Component Studio (`ctx.callRule`/`ctx.callBl`, `ctx.breadcrumb`, `<include>`), theming & dark mode, `<plugin>` composition, hand-built data tables + paging, component structure | [24](24-html-component-studio.md), [24a](24a-theming-and-dark-mode.md), [24b](24b-html-composition-and-plugin-tags.md), [24c](24c-html-data-tables-and-paging.md), [24d](24d-html-component-structure.md) |
| **Form settings, validations & field events** — the control Config accordion, the Form Settings panel, validation-from-template, event → refresh | [25-form-settings-validation-and-events.md](25-form-settings-validation-and-events.md) |
| **Orchestration & testing a big PRD** — decompose into a `plan.json` ledger, test each unit, the `coverage` gate, the live acceptance run | [26-orchestration-and-testing.md](26-orchestration-and-testing.md) |
| **Process start — who opens the case** — the decision every process owes (WHO / WHEN / what INVOKES that) and the four starters: a **user start action**, a **document lifecycle rule**, a **scheduler tick**, a **service task**. Plus the sweep rule that calls `service.workflow.start`, idempotency, and making the case findable | [27-event-driven-process-start.md](27-event-driven-process-start.md) |

> **🔧 Tooling.** Do the entire assembly below with the **commands** of [`tools/mrjun.py`](tools/mrjun.py), not hand-written
> JSON — the CLI encodes all the "hard rules" (settings vs model, `id=null`, fresh uuids, `ruleType→executor`,
> the typo `process.table.pluin`). Full command index + "step → command" mapping →
> [`tools/README.md`](tools/README.md) (the last line of the mapping is the complete ordered command chain for
> assembly: `db add-schema/add-table` → `source add` → `crud add --scaffold-methods` (+`query add`) →
> `context add` → `rule add` → `formgroup/form add` → `page add`/`node add` → `validate` → `pack`).
> After edits, always run `validate`.

---

## 1. Starting point: what already exists in `empty` (do NOT re-create)

`empty` is an **admin skeleton of a REPORT project**, not a blank slate. Already present:

- **`tenant.json`**: `{name, alias, description, domain, status:"published", template:false, importedFrom:[],
  locales:["en_US","hy_AM"]}` — the shipped values are the neutral `base`/`base.template`; `locales` determine
  for which languages you need `localizedNames`. Set your own name/alias/domain; the target tenant's realm and
  client are used on import regardless.
- **`rep-objects.json`**: `queries: 6` (`Countries`, `Rimm Brand Start With`, `Rimm Countries Start with`,
  `Rimm Equipments`, `Rimm Users by Role Group`, `Rimm User Start With`), `settings: 4`, `processGroups: 2`,
  `roleGroups: 2` (`Author`, `Developer`), `mailTemplates: 5` (`Company Invitation`, `Event Reminder`,
  `Password Recovery`, `sendIntakeInit`, `User Registration`), **`sources: 1`** — one INTERNAL source named
  `data`, carrying only placeholders (`hostName: "localhost"`, `dbName: "project_db"`, `schemaName: "data"`,
  `userName: "project_user"`, empty `password`, `realmName`/`clientName` null). Everything else
  (`workflows/rules/contexts/formGroups/forms/schedulers/userRoleGroupAssignments/pdfTemplates`) is **empty**.
  ⚠️ **`sources` is NOT empty any more.** Adding "your" INTERNAL source next to it leaves the export with two
  INTERNAL sources over two different schemas, and the import materializes both. Either reuse the shipped
  `data` row (repoint its `schemaName`) or delete it before adding your own — never both.
  ⛔ **They are placeholders on purpose, and yours must be too.** The import rewrites every INTERNAL row onto
  the RECIPIENT's database, role and password before it saves it, and normalises the host afterwards — so
  nothing you write there is ever used. What you write there IS, however, published: a `.mrjun` is a file that
  gets mailed, committed and bundled into libraries. Never put a real host, role or password in one. The
  export strips them now (`sourceWithoutSecrets`), but an archive you assemble by hand is on you.
- **`integrations.json`**: the pinned **Business Logic** integration. Keep it — the import starts integrations
  before it imports `dynamic-cruds.json`, and a dynamic CRUD binds to a RUNNING integration ([00](00-export-format-and-import.md)).
- ⚠️ **Dangling `roleGroupAccessors` on the baseline pages.** Baseline page nodes carry a `roleGroupAccessors`
  block naming role groups that do **not** exist in `rep-objects.roleGroups` (only `Author`/`Developer` do),
  and `page add` clones that block onto new pages. Membership **is** checked
  ([01](01-content-model-and-pages.md)), so an entry naming a group nobody can belong to grants nothing — but
  it is not harmless noise either: create a role group with that name later and the old entry silently becomes
  live. Strip them for a clean export, and write your own persona entries deliberately.
- **`branches.json`**: a single branch `master` with `rootContent` = `Home` (`siteMapPage`) and **23** admin
  pages, by alias: `401`, `404`, `audit-logs`, `bl`, `contexts`, `database`, `form`, `landing`,
  `mail-templates`, `pdf-templates`, `processes`, `profile`, `queries`, `query`, `roles`, `rules`,
  `schedulers`, `script`, `settings`, `sources`, `users`, `workflow`, `workflows`.
  ⚠️ The platform's old demo pages are **gone** from every bundled archive in this library — the baseline and
  both ERP references alike. They are not a model for anything: a dashboard's shape is your decision under
  [21](21-homepage-and-redirect.md) and [22](22-charts-params-and-filters.md) §2B. Plus
  `virtualPlugins[]` — the palette of layout/controls (`1-col`…`4-col Layout`, `Main`, `Form`, `Nct layout`,
  `Nct left nav`, `Card`, `Logo`, `Pdf`, `Form Submit Button`, `Text Label Field`, `Drop Down Label Field`,
  `Date Picher Label Field` (sic), `Auto Complete Label Field`, `File Upload Label Field`, …).
  ⚠️ **`empty` is not content-free: `Home`'s content parsis already holds a `process.table.pluin`**, pointing
  at a `workflowIdentifier` that exists nowhere in the export (`rep-objects.workflows` is empty), i.e. dead as
  shipped. It is the only one left — the second, on the deleted `Branches` page, went with that page.
  **Before you put any table — or the dashboard grid — on `Home`, DELETE that node** (or repoint it —
  [05](05-crud-tree-and-process-table.md) Part 2, [07](07-workflows-and-tasks.md)); otherwise `validate` ERRORs with
  the one-table-per-page rule. The remedy its message suggests (put each table in its own tab) is the **wrong**
  fix here — it would ship your real table tabbed together with a dead demo process table.
- **`project-db.dump`**: 2 empty schemas, `<prefix>_data` and `<prefix>_rimm`, where `<prefix>` is the
  `schemaPrefix` recorded in `project-db-meta.json`. On the current storage model every schema of a project
  carries that prefix (`<realm>_<client>_<hash>_<name>`), and the import RENAMES each one into the recipient's
  own prefix — so a business schema you add by hand must carry the donor prefix too. An unprefixed name is
  not left alone: it still lands inside the recipient, but as `<recipientPrefix>_<the whole bare name>`,
  which no longer matches the `<prefix>_app` shape the rest of your archive assumes. Only a LEGACY
  (one-database-per-project) recipient leaves it bare.
- **No `dynamic-cruds.json`** — it appears only once you add a dynamic CRUD.

**You ADD on top of this:** the DB business schema, a source, dynamic CRUDs + their queries, a context, rules,
forms/formGroups, business pages (CRUD/Process table), workflows, roleGroups. You do not touch the admin pages and the palette.

> ⚠️ **Import precondition.** A full restore of rep-objects + DB triggers only if the receiving project has the
> tenant property `type == REPORT` (`CmsProjectServiceImpl.java`, on both the export and the import side).
> `empty` is a REPORT project, so base yourself on it. More detail — [00](00-export-format-and-import.md).

---

## 2. Dependency graph and assembly order

Everything is linked by `identifier` (UUID). An arrow = "references".

```
tenant.json(locales)
project-db.dump  ─ schema.table ◀──────────────┐
   ▲ (DB Management plugin)                     │ sourceSchema
Source (rep-objects.sources) ─ sourceIdentifier ┘
   ▲
Dynamic CRUD (dynamic-cruds.cruds[]) ── method.queryIdentifier ─▶ Query (rep-objects.queries, "crud_<alias>_<method>")
   │                              method.ruleIdentifier  ┄▶ Rule (optional and rare — and in authored projects the
   │                              few that carry one often point at nothing; GROOVY normally carries an inline `script`)
   ▼ alias
Context (rep-objects.contexts[].crudAliases[])  ◀── contextIdentifier ── everything below
   ▲
Rule (rep-objects.rules[])  ── contextIdentifiers[]
   ▲ ruleIdentifier / predicateIdentifier / onBeforeCompleteRuleIdentifier
Form (rep-objects.forms[]) ── contentIdentifier ─▶ content-tree node (the real form controls!)
   ▲ formIdentifier
FormGroup (rep-objects.formGroups[].predicateFormMapping)
   ▲ formGroupIdentifier
Content tree (branches.json[0].rootContent.children):
   siteMapPage → parsis.plugin("parsis") → html.plugin("Layout") → nct.parsis.plugin("parsis")
        ─ crud.table/crud.tree/process.table/chart.js (properties.model / Javascript) / form-group landing
        │   ↑ the plugin sits in the content parsis INSIDE the baked Layout, NEVER bare under siteMapPage
        │  all three model plugins ADDITIONALLY mirror the model into rep-objects.settings[]
        └─▶ rep-objects.settings[] {type:"CrudTable"/"CrudTree"/"ProcessTable"}
              ▲ setting.name == node.uniqueIdentifier   (persistence mirror, not the render source)
```

**Write order (10 steps):**

1. `tenant.json` — name/alias/domain/locales (usually left as in `empty`, you change name/alias/domain).
2. **DB schema** → `project-db.dump` (schema + tables + sequences + FK). → [10](10-database-management.md).
3. **Source** → `rep-objects.sources[]` pointing at that schema. → [12](12-queries-sources-schedulers-and-rest.md).
4. **Dynamic CRUDs** → `dynamic-cruds.json.cruds[]` (+ their **queries** in `rep-objects.queries[]`,
   named `crud_<alias>_<method>`). → [11](11-business-logic-dynamic-crud.md).
5. **Context** → one `rep-objects.contexts[]` with ALL aliases in `crudAliases[]`. → [08](08-groovy-rules-and-context.md).
6. **Rules** → predicates / execution / validation in `rep-objects.rules[]` (choices, actions, visibility,
   validation), each with `contextIdentifiers=[<context>]`. → [08](08-groovy-rules-and-context.md).
7. **Forms + FormGroups** → `rep-objects.forms[]`/`formGroups[]` + their content nodes (form controls).
   → [02](02-form-controls-reference.md), [03](03-generate-fields-from-crud.md), [06](06-form-groups-and-mapping.md).
8. **Business pages** → `siteMapPage` nodes with `crud.table.plugin`/`crud.tree.plugin`/`process.table.pluin`
   + landing nodes, in `branches.json[0].rootContent.children`. → [01](01-content-model-and-pages.md),
   [04](04-crud-table-plugin.md), [05](05-crud-tree-and-process-table.md).
9. **Workflows** (if needed) → `rep-objects.workflows[]` (`bpmnContent` + `elements`) + processGroups.
   → [07](07-workflows-and-tasks.md); if nobody presses Start — a scheduler tick, a written row, a step in
   another process — it is a different chain: **no start form**, an EXECUTION rule that gathers the rows and
   calls `service.workflow.start`, its own idempotency guard, and a worklist page so the case is visible at all
   → [27](27-event-driven-process-start.md).
10. **RoleGroups + assignments**, extra queries/mailTemplates/schedulers. → [12](12-queries-sources-schedulers-and-rest.md).

Orders of magnitude to expect, by project shape (use them as a sanity check on your own counts, not as targets):

| project shape | rules | forms | formGroups | queries | settings | workflows | contexts | sources | dyn-cruds |
|---|---|---|---|---|---|---|---|---|---|
| the `empty` baseline | 0 | 0 | 0 | a handful | a handful | 0 | 0 | 0 | 0 |
| workflow-first app (few screens, several processes) | tens | a few | a few | a handful | a handful | a few | 1 | 0 | 0 |
| static-CRUD app (logic compiled in Java) | hundreds | tens | tens | a handful | tens | a few | 1 | 0 | 0 |
| **dynamic-CRUD app (what this playbook builds)** | tens | tens | tens | **6 × entities + tail** | tens | a few | 1 | 1 | one per entity |

The one ratio that really matters, and the one you can check exactly: a dynamic CRUD gets **seven methods** —
one GROOVY `find` plus the six SQL ones (`findAll`/`count`/`get`/`create`/`update`/`delete`) — and only the six
SQL methods own a saved query. So a dynamic project carries **six queries per entity**, plus a small RIMM tail
([12](12-queries-sources-schedulers-and-rest.md) §1). The query count therefore dwarfs everything else; if
yours is materially lower, entities are missing methods.

---

## 3. Step by step

### Step 1 — tenant.json
You change `name`/`alias`/`domain`/`description` for the project; `locales` is the list of languages (min. `["en_US"]`);
`status:"published"`, `template:false`. All `localizedNames`/`localizedButtonNames` below must cover
exactly these locales. Details → [00](00-export-format-and-import.md).

### Step 2 — Database (`project-db.dump`)
Format `nct-jdbc-dump-v1`. You create a new business schema (e.g. `app_schema`) with tables, columns,
sequences (for auto-id), FKs, unique/check, and indexes. Each business entity = a table. The full file schema,
column types, auto-generation, and "how to write a dump from scratch" → [10](10-database-management.md).

### Step 3 — Source (`rep-objects.sources[]`)
A connection to the schema from step 2: `{identifier, name, sourceType, dbType:"POISTGRESQL", hostName, port, dbName,
schemaName, userName, password}`. ⚠️ **`dbType` = the single value `"POISTGRESQL"`** — the enum `DbType`
(`nct-transfer/.../DbType.java`) is literally spelled with a typo; do NOT "fix" it to `POSTGRESQL` (the source will not
deserialize on import), same as `process.table.pluin`. The `identifier` of this source goes into
every dynamic CRUD (`sourceIdentifier`) and every query. → [12](12-queries-sources-schedulers-and-rest.md).

### Step 4 — Dynamic CRUDs (`dynamic-cruds.json`) + queries
For each entity — one CRUD in `cruds[]`:
```
{ alias:"<name>_cruid", name, localizationField:"localized",
  sourceIdentifier:"<source>", sourceSchema:"app_schema", source*:...,
  dtoFields:[{fieldName, displayName, fieldType, fieldOrder}],   // from the table columns
  filterFields:[...],
  methods:[ find(GROOVY), findAll(SQL), count(SQL), get(SQL), create(SQL), update(SQL), delete(SQL) ] }
```
- **SQL methods** reference a query by `queryIdentifier`; you create the paired query in `rep-objects.queries[]`
  named **`crud_<alias>_<methodName>`**, with `sourceIdentifier=<source>`, the `query` field = SQL, and
  `returnFields` typing on the method.
- **`find`** — GROOVY, the standard script: `count()` + `findAll(filter)`, returns a Groovy **map**
  `[content:.., totalElements:.., totalPages:.., pageNumber:..]` (not a positional list). **Every** method
  carries an inline `script`. A SQL method additionally carries a `queryIdentifier` (both together). The GROOVY `find` can
  ADDITIONALLY carry an optional `ruleIdentifier` (an additive override on top of the script, not a replacement). The exact
  template, dtoFields/filterFields, enums, joins → [11](11-business-logic-dynamic-crud.md).

### Step 5 — Context (`rep-objects.contexts[]`)
One context per project (usually): `{identifier, name, alias:"<appCtx>", crudAliases:[all aliases from step 4]}`.
`alias` is what you write in Groovy: `context.<appCtx>.<crudAlias>...`. Its `identifier` (`contextIdentifier`)
is substituted into rules, forms, form controls, crud.table model. The context model
(`attrs / contextDataMap{crudDataMap} / returnValue`) and scopes (GLOBAL/CONTEXT/CRUD — a persisted scope is
not the last word: on a form opened from a `crud.table`/`crud.tree` action every control is re-bound to that
table's CRUD) → [08](08-groovy-rules-and-context.md).

### Step 6 — Rules (`rep-objects.rules[]`)
Three types (`ruleType` / `executor`):
- **PREDICATE / GroovyPredicate** — Boolean: action visibility, gateway, form-mapping, choices filters.
- **EXECUTION_RULE / GroovyExecutionRule** — business logic: `onBeforeStart`/`onBeforeComplete` of actions,
  choices sources of dropdowns, service tasks.
- **VALIDATION_RULE / GroovyValidationRule** — form validation (`validation.addFieldError(key,msg)`).
  A real, working executor — rare in practice, but do not treat it as unsupported.

Each rule: `{identifier, name, description, status:"ACTIVE", ruleType, executor,
contextIdentifiers:[<context>], rule:{ruleScriptStr:"<Groovy>"}, hidden}`.

**Canonical Groovy API (from real rules; NOT the made-up `context.service.<alias>`):**
```groovy
// current row / form record:
def row = context.<appCtx>.<alias>.data.get()          // Map of fields
context.<appCtx>.<alias>.data.put(dto)                 // put it back
// CRUD service:
context.<appCtx>.<alias>.service.create(dto)           // == service.crud.<alias>.create(dto)
service.crud.<alias>.findAll(filter); service.crud.<alias>.count()
//   ↳ findAll([:]) (ALL keys absent) is safe; a PARTIAL map e.g. [active:"true"] leaves other :params
//     unbound as "$1 IS NULL" → Postgres "could not determine data type of parameter $1". For a filtered
//     dropdown use the acFindBy<X>Like pipeline, not a partial findAll. (02 §4a)
// global/transient attributes — the transient process variables any rule may write and read (a service task
// setAttrs a new id, a gateway predicate getAttrs it). A SUBMITTED FORM value is here only when the form was
// opened WITHOUT a row (workflow user task, ProcessTable start/global action); opened from a
// crud.table/crud.tree ACTION the form is in CRUD mode:
// the platform binds every control on it to that table's CRUD, so the SUBMITTED values arrive on the ROW
// above (context.<appCtx>.<alias>.data.get()) and getAttr returns null there — silently (see the ⛔ below).
// the attrs themselves:
context.data.setAttr("k", v); context.data.getAttr("k", default)
// current item of a List control:
context.currentData.get()
// a rule calls a rule (by NAME, boolean):
service.rule("Is Author")
// roles:  service.security.hasAnyRoleGroup("Author")
// RIMM query:  service.rimm.run([name:"...", itemsPerPage:100, parameters:[...]])
// CHOICES RULE (dropdown/autocomplete) MUST convert rows to options — NEVER return a raw findAll/find list:
//   dropdown:         return service.global.conversion.toSelectOptions(list,"id","name")
//   localized field:  return service.global.conversion.toSelectOptionsLocalized(list,"id","name")  // session-locale labels
//   autocomplete:     return service.global.conversion.toAutoCompleteOptions(list,"name")
//   (raw entity list → picker shows "No results found" + hides Show Nav; `validate` ERRORs. Search → acFindBy<X>Like, 02 §4a)
// abort the action:  throw new RuntimeException("message")   // there is no validation.* in an execution rule
```
⚠️ The body of a PREDICATE/EXECUTION must **explicitly** `return <expr>` (the template ends with `if(true){return null;}`).
Full taxonomy, templates, context differences in crud/process/form/list → [08](08-groovy-rules-and-context.md).
Rule-editor hints (server vs live context-data) → [09](09-groovy-hints-and-live-context.md).

⛔ **Which of the two reads above a rule uses is decided by the form's ENTRY POINT, not by taste.** The
`onBeforeComplete` rule of a `crud.table`/`crud.tree` action (the only one that runs after submit — `onBeforeStart` fires at form DISPLAY) reads the values the user just
submitted from the ROW — `context.<appCtx>.<alias>.data.get()` — never `context.data.getAttr("<field>")`, which
is null on that path and fails silently (the crud method gets `''`, `COALESCE` keeps the old value, the toast
still says success). `validate` ERRORs on a literal `getAttr("<field>")` in a rule wired to a table action whose
own form carries that field (`_check_crud_action_form_values`). A rule behind a workflow user task or a
`process.table` start/global action reads the attrs, as above. One form group serving BOTH reads both — attrs
first, then the row (the `FORM` helper in [08](08-groovy-rules-and-context.md)).

### Step 7 — Forms, FormGroups, form controls
- **Form** (`rep-objects.forms[]`) is a **wrapper**: `{identifier, name, contentIdentifier, formGroup,
  contextIdentifiers[], validators[], actionValidators[], hiddenConfigs[], multiLanguage, allowDrafts}`.
  The real form fields live **not here**, but in the content-tree node that `contentIdentifier` points to.
- **Form controls** are nodes in the tree (`dynaform.form.text.field.plugin`, `...rimm.drop.down...`, …); their
  config is a JSON string in `properties.settings.stringValue` (`scope:CRUD/CONTEXT/GLOBAL, crudAlias,
  contextIdentifier, fieldExpression, key, displayName, dataClass, ruleIdentifier(choices),
  eventComponentMappings, conditionalValidations, alwaysMandatory, ...`). Each control, its settings,
  mapping, validations, between/range, default-value, prohibited → [02](02-form-controls-reference.md).

> ⛔ **A form a `crud.table`/`crud.tree` ACTION opens is in CRUD mode: the platform binds EVERY control on it to
> that table's `contextIdentifier` + `crudAlias`, whatever `scope` you persist.** Author the whole form with the
> CRUD quartet (`scope:"CRUD"` + the TABLE's pair + `fieldExpression`) — including an input no column backs (a
> reason, a note, a decision): it rides in `crudDataMap[<alias>]` as an extra key nothing persists and the rule
> reads it from the row. A `GLOBAL`/`CONTEXT` control there does not keep the value out of the entity; it only
> makes the export disagree with runtime (`validate` warns). Forms opened WITHOUT a row — a workflow user task,
> a `process.table` start/global action — are not in CRUD mode and keep `GLOBAL`/`CONTEXT`. Nested list-item
> controls keep their own `__temp_item__` binding. Detail → [02](02-form-controls-reference.md) §Where the value
> LANDS.

- **Config accordion + Form Settings** — the "Create Validation from Template" flow (51 templates →
  `GroovyPredicate` bodies + regex presets + ERROR/WARNING), field **events** (event → Execute-Rules-Before-Refresh
  → refresh fragment; several targets = several mappings), and the form-level **Hidden Content Configuration**,
  **Global vs Action-Based validation** (`validation.addFieldError(<control name>,…)`) and **Allow Drafts** →
  [25](25-form-settings-validation-and-events.md).
- Bulk field generation (dropdown/autocomplete/date/required-with-predicate, HTML wrapper
  `<div class="mb-3"><plugin id="lbl_gen_slot_..."/><plugin id="fld_gen_slot_..."/></div>`) →
  [03](03-generate-fields-from-crud.md).
- **FormGroup** (`rep-objects.formGroups[]`): `{identifier, name` (e.g. `"<Crud> Forms"` or
  `"<Crud> Form Group"` — the convention varies, not enforced; see [06](06-form-groups-and-mapping.md))`, contentPageIdentifier,
  formGroupsPageIdentifier, contextIdentifiers[], placeFormsNextToLanding,
  predicateFormMapping.mapping:[{predicateIdentifier, formIdentifier}]}` — the predicate chooses which form
  is rendered (Create/Edit usually share one form + a True branch). "Create Default Actions", the landing node,
  form-alias uniqueness → [06](06-form-groups-and-mapping.md).

### Step 8 — Business pages (content tree)
You add `siteMapPage` nodes to `branches.json[0].rootContent.children`. Inside a page — a table:

> ⛔ **MUST — a business page carries the baked page Layout chrome; the table/chart/tree/process plugin is NOT a
> direct child of `siteMapPage`.** Every real page is
> `siteMapPage → parsis.plugin("parsis") → html.plugin("Layout") → [site.header, nct.image logo, site.breadcrumb,
> site.kicker (left-nav), **nct.parsis.plugin("parsis")**, site.footer, site.right.kicker]`, and
> `crud.table.plugin` / `crud.tree.plugin` / `process.table.pluin` / `chart.js.plugin` lives **INSIDE** that content
> `nct.parsis.plugin("parsis")` (see [01](01-content-model-and-pages.md) §Layout — there are no bare
> exceptions). Build the page with `page add` (clones the Layout scaffold)
> then `node add` (drops the plugin into the content parsis) — **NEVER hand-author a bare
> `siteMapPage → crud.table.plugin`**. A bare page IMPORTS CLEAN and passes `validate` (its Layout gate
> `_check_form_page_layout` iterates ONLY `rep.forms`, so it fires for FORM pages ONLY — tables/charts/trees/process
> pages have **NO** offline chrome check), `coverage` and `crud verify`, **but renders an EMPTY shell** (no
> header/left-nav/breadcrumb, the plugin never mounts). Only a LIVE open reveals it — you MUST live-render every
> table/chart/tree/process/landing page.

- **CRUD Table** — `crud.table.plugin`, config in **`properties.model.stringValue`**:
  `{crudAlias, contextIdentifier, rowsPerPage, columnSettings:[{id,localizedNames,fieldExpression,dataClass}],
  filterSettings:[...], createActions:{actions:[ACTION]}, editActions:{actions:[ACTION]}}`.
  `ACTION = {id, localizedNames, localizedButtonNames, icon, direct(bool), formGroupIdentifier,
  onBeforeStartRuleIdentifier, onBeforeCompleteRuleIdentifier, predicateIdentifier, submitForm}` — all fields
  are optional, unset ones are not emitted: a dynamic-CRUD table typically emits only
  `{id, name, localizedNames, localizedButtonNames, icon, direct, formGroupIdentifier, onBeforeCompleteRuleIdentifier}`;
  `onBeforeStartRuleIdentifier`/`predicateIdentifier`/`submitForm` show up mostly on static CRUD. →
  [04](04-crud-table-plugin.md).
- **CRUD Tree** (`crud.tree.plugin`) — a hierarchy (find roots / findByParent). Deltas → [05](05-crud-tree-and-process-table.md).
- **Charts / KPI dashboards** — `chart.js.plugin`, config in **`properties.Javascript.stringValue`** (a `ChartJsModel`):
  `html`+`js` with `$$('name', default, 'Type')` markers, one `replacement` per marker
  (`replaceStrategy:"QUERY"` → query column → typed array). Add a `global.replacement.plugin` node for a page
  filter bar + click-to-cross-filter. Full recipe → [22](22-charts-params-and-filters.md).
- **Mirror in `rep-objects.settings[]` — for ALL three plugins, not just Process Table.** The config for
  `crud.table.plugin`, `crud.tree.plugin` AND `process.table.pluin` lives in `properties.model.stringValue`
  of the node (the plugin renders **from `properties.model`** — `CrudTablePlugin.java`, `ProcessTablePlugin.java`),
  but is **additionally mirrored** into a `rep-objects.settings[]` object with the field `type` = `"CrudTable"` /
  `"CrudTree"` / `"ProcessTable"` respectively (the field is called `type`, not `settingsType`). The join key is
  `setting.name == node.uniqueIdentifier`. This is a persistence artifact (not the render source). The invariant is
  **directional**: every table/tree/process node **you author** needs a setting, the reverse is NOT required — use
  `node set-model`, which writes the mirror for you. **Do not expect the totals to match**, and never "repair" the
  baseline: shipped `empty` already carries 3 `ProcessTable` settings for only 2 `process.table.pluin` nodes
  (two orphan mirrors, and the `Branches` node has no mirror at all), and the importer tolerates orphans. Check
  with `jq '.settings[]|.type,.name' rep-objects.json` and look up **your own** nodes' `uniqueIdentifier`s in it —
  a hit is what you want; a raw count comparison only produces false alarms.
- **Process Table** (`process.table.pluin` — **the typo in the name is real, keep it**) — a table over
  workflow processes; config in **`properties.model.stringValue`** of the node (the same slot as `crud.table` —
  `ProcessTablePlugin.java`, `getJsonProperty`/`setJsonProperty("model")`), with a mirror in
  `rep-objects.settings[]` `type:"ProcessTable"` (see above). The payload —
  `{workflowIdentifier, processGroupIdentifier, filterExpression, globalActions.actions[],
  userStartProcessActions.actions[], indexSettings[], columnSettings}` — lives **inside the `content` field** of the
  setting (the top-level keys of the setting are only metadata: `identifier/name/type/content/…`), mirroring
  the plugin's `properties.model.stringValue`, not at the root. → [05](05-crud-tree-and-process-table.md).
- Tabs (`nct.tab.plugin`), layout (`nct.html.plugin` with Bootstrap-grid markup + `nct.parsis.plugin` slots),
  `roleAccess` (public vs authenticated), hidden content → [01](01-content-model-and-pages.md).

### Step 9 — Workflows (when needed)
`rep-objects.workflows[]`: `{identifier, name, bpmnContent(XML), elements[], processDefinitionId,
contextIdentifiers[], deployed}`. The bindings inside the BPMN:
- **ServiceTask → rule(s):** `flowable:delegateExpression="${ruleTask}"` + `flowable:rule="<uuid,uuid>"`
  (order = execution order).
- **UserTask → actions/forms:** `flowable:userActions="{escaped JSON}"` with the same ACTION object (see step 8).
- Standard `startEvent`/`endEvent`/`sequenceFlow`/gateway. All task types, user task settings,
  processGroups, processes → [07](07-workflows-and-tasks.md).

### Step 10 — Roles, queries, mail, schedulers
- **roleGroups** (`rep-objects.roleGroups[]`) + **userRoleGroupAssignments[]** — needed for predicates
  `service.security.hasAnyRoleGroup("<RoleGroup>")`. Pair each auth predicate with its roleGroup.
- Extra **queries** (non-CRUD), **mailTemplates**, **schedulers** → [12](12-queries-sources-schedulers-and-rest.md).

### Step 11 — Building the `.mrjun`
**Prefer `mrjun.py pack <workdir> <out.mrjun>`** — it zips the whole working directory and therefore cannot forget
a file. If you do zip by hand, the archive root must carry: `tenant.json`, `branch-metadata.json`, `branches.json`,
`rep-objects.json`, `project-db.dump`, `project-db-meta.json`, **`integrations.json`** (the pinned Business Logic
integration — drop it and the dynamic CRUDs have no RUNNING integration to bind to and simply do not import,
silently), `dynamic-cruds.json` (if there are CRUDs), `favicon/`, `tenant-files/`.
The application order on import and id remapping → [00](00-export-format-and-import.md).

---

## 4. Golden thread (end-to-end example) — one entity in full

Take one entity — here **Declarations** in a customs system; substitute your own (Invoices, Orders, Tickets,
Consignments — the chain is identical):
1. **Table** `app_schema.declarations` (id, declarant_id, office_id, filed_date, cleared_date, status_id,
   localized, …) in `project-db.dump`.
2. **Source** `{name:"app_schema", dbType:"POISTGRESQL", schemaName:"app_schema", ...}` → `identifier S`.
3. **CRUD** `{alias:"declarations_cruid", sourceIdentifier:S, sourceSchema:"app_schema",
   dtoFields:[id,declarant_id,...], methods:[find(GROOVY), findAll(SQL→query Q1), count(SQL→Q2), get, create,
   update, delete]}`.
4. **Queries** `crud_declarations_cruid_findAll` (Q1, SELECT … JOIN dim_declaration_statuses),
   `crud_declarations_cruid_count` (Q2), … — all with `sourceIdentifier:S`.
5. **Context** `app_context.crudAliases += "declarations_cruid"`.
6. **Rules**: a choices rule for the `status` dropdown (EXECUTION — a choices rule MUST end by converting rows to
   option pairs: `return service.global.conversion.toSelectOptions(service.crud.declaration_statuses_cruid.findAll([:]), "id", "name")`;
   a **raw** `findAll` list renders **"No results found"** + hides Show Nav — see [02](02-form-controls-reference.md) §4a),
   a Create action rule — the form was opened from the table's action, so it is in CRUD mode and the
   submitted values arrive on the ROW: `def dto = context.app_context.declarations_cruid.data.get()` then
   `context.app_context.declarations_cruid.service.create(dto)` (`context.data.getAttr("<field>")` is null
   here) — and a visibility predicate.
7. **Form** + **FormGroup** "Declaration Forms" with fields (dropdown declarant/office/status, datepicker dates),
   `predicateFormMapping` True branch.
8. **Page** `siteMapPage "Declarations"` — the `crud.table.plugin` is injected into the page's content
   `nct.parsis.plugin("parsis")` inside the baked `html.plugin("Layout")` chrome (via `page add` + `node add`),
   **not placed directly under `siteMapPage`** — with `model.crudAlias="declarations_cruid"`,
   `contextIdentifier=app_context`, columns (declaration_no, status, dates), createActions→formGroup, editActions.

---

## 5. Checklist before reimport

> Most of this is checked automatically by `python3 tools/mrjun.py validate --project <dir>` (0 errors = ok;
> warnings are acceptable). Run it first; below is what it covers and what to eyeball.

- [ ] `validate` gives **0 errors**.
- [ ] The receiving project is a **REPORT type** (otherwise rep-objects/DB will not restore).
- [ ] Every `contextIdentifier` in rules/forms/controls/crud-model = the `identifier` of a real context, and its
      `crudAliases[]` contains all the aliases used.
- [ ] Every `queryIdentifier` in CRUD methods points to an existing query; name `crud_<alias>_<method>`.
- [ ] Every `sourceIdentifier` (in CRUD and queries) = the `identifier` of a real source; `sourceSchema` matches
      the schema in `project-db.dump`.
- [ ] Every `formGroupIdentifier`/`onBefore*RuleIdentifier`/`predicateIdentifier` in actions resolves.
- [ ] **Every rule wired to a `crud.table`/`crud.tree` action reads the submitted values off the ROW**
      (`context.<ctx>.<alias>.data.get()`), not `context.data.getAttr("<field>")` — unless the same form group is
      ALSO reachable without a row (task / `process.table` action), which reads BOTH, attrs first — and **every control on the
      form that action opens carries the CRUD quartet** (`scope:"CRUD"` + the table's `contextIdentifier` +
      `crudAlias` + `fieldExpression`), including input-only fields with no column. `validate` ERRORs on the
      first and WARNs on the second (`_check_crud_action_form_values`).
- [ ] Form controls are in `properties.settings`; tables are in `properties.model`.
- [ ] **Every business page (crud.table/crud.tree/process.table/chart.js/landing) carries the baked Layout chrome**
      and its plugin sits inside the content `nct.parsis.plugin("parsis")` — `validate` enforces this ONLY for FORM
      pages (`_check_form_page_layout`), so EYEBALL/LIVE-OPEN tables, charts, trees, process tables and landings: a
      bare `siteMapPage → plugin` imports clean but renders empty (see Step 8 ⛔).
- [ ] **Every page's TOP `parsis.plugin` still has `identifier == "siteMapPageParsis"`** (and there is exactly
      one). The page resolves its content container by that name and it appears in NO html, so a clone helper
      drops it silently; the platform then renders a fresh EMPTY one and your subtree is an orphan -> blank
      page. `validate._check_page_top_parsis` ERRORs on it.
- [ ] **Every `<plugin id="X">` inside every `html` resolves to a child with `identifier == X`, and every child of
      an html node is referenced by that html.** An `html.plugin` draws a child ONLY if its own html names it, so a
      **cloned** page whose child identifiers were regenerated keeps all its nodes and renders NONE of them. The
      Layout addresses seven by name (`header`, `logo-plugin`, `breadcrumb`, `left-nav`, `parsis`, `footer`,
      `right-kicker`) — when cloning, preserve every id any html in the subtree references, derived with
      `re.findall(r'<plugin[^>]*\bid="([^"]+)"', html)`, never a hardcoded list. `validate._check_html_plugin_refs`
      ERRORs on the regenerated-id signature (see [01](01-content-model-and-pages.md) ⛔⛔ THE CLONING TRAP).
- [ ] **Every authored CSS block is theme-safe** — no colour literal outside a `var(--token, <fallback>)`, no
      colour in an inline `style=`. A hardcoded light palette imports clean and looks broken on 4 of the 5 skins
      (white cards on a black page). `validate` now WARNs on a colour literal in `css.byTheme["*"]` that is
      neither a `var()` fallback nor overridden by a per-skin block, and on an inline `<style>` in a `html`
      property — but it cannot judge CONTRAST, so still open the page in all five skins
      ([24a §9](24a-theming-and-dark-mode.md)); [24a §8](24a-theming-and-dark-mode.md) has a starter block.
- [ ] **Every hand-built table pages on the SERVER** — `rowsInPage`/`pageNumber` down to SQL, not a
      `rowsInPage` fetch-everything. [24c](24c-html-data-tables-and-paging.md).
- [ ] **Page-level actions of a custom component sit in the breadcrumb** (`ctx.breadcrumb`), not in a
      home-grown toolbar inside the component. [24 §7](24-html-component-studio.md).
- [ ] Groovy bodies of PREDICATE/EXECUTION have an explicit `return`.
- [ ] **Every per-locale map covers all `tenant.json.locales`** — `localizedNames`/`localizedButtonNames` (an
      action with only a top-level `name` renders **blank**), plus `localizedStringValue`/`localizedLabels`/
      `defaultValueLocalized`/`infoText`/validation-message maps and any `localize` entity jsonb. **Auto-translate
      never runs on import** — you must hand-write every locale (blank slots stay blank). Full layer model,
      export-key inventory, and the coverage rule → [20-localization.md](20-localization.md).
- [ ] The `id` of rep objects = `null` (links only via `identifier`).
- [ ] The typo `process.table.pluin` is preserved; not "fixed".
- [ ] **Every status/enum LITERAL a SQL method writes is in the column's CHECK-constraint set** (`db show <table>`
      to see it; `validate` errors otherwise) — a lifecycle write outside the set throws on any real row.
- [ ] **Every UI field expression is surfaced by `findAll`** — cross-check `crud.table`/`crud.tree` columns,
      form controls, AND **`dynaform.form.list.field` sub-grid columns**; a dotted `ref.code` needs the ref
      object to carry that leaf, not just `{id}` (`validate` warns). **One legitimate exception:** an
      input-only field on a CRUD-mode form (a reason, a note, a decision) that has no column — keep it
      `scope:"CRUD"`, it rides in `crudDataMap[<alias>]` as an extra key the rule reads and nothing persists;
      accept the warning, do not invent a column and do not switch it to GLOBAL.
- [ ] **Enum dropdowns carry a `settings.enumValues` snapshot** (or a choices rule) — else they render blank
      after import (`validate` warns).
- [ ] **Document `delete` cascades to child lines** (GROOVY `deleteLines` + header delete), not a bare
      `DELETE FROM <header>` (`validate` warns).
- [ ] **Verified against a POPULATED DB**, not just empty tables: `mrjun.py crud verify --db "…"` (seeds a
      fixture row so CHECK/NOT NULL/FK fire). Empty transactional tables hide every one of the above.
- [ ] Wiring an existing schema+UI? Follow [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md).

## 6. Pitfalls (summary)

1. **`properties.model` (tables) vs `properties.settings` (form controls)** — different slots.
2. **The `type==REPORT` gate** — without it the import skips rep-objects + DB.
3. **`id` is present, but `= null`** — not a "missing key"; links are via `identifier`.
4. **The typo `process.table.pluin`** — a real registry key, don't touch it.
5. **Explicit `return`** in predicates/execution (the template collapses a "bare" value to `null`).
6. **The form is a wrapper**: fields are in the content tree (`form.contentIdentifier`), not in `rep-objects.forms`.
7. **One context per project** with a complete `crudAliases[]` — the typical pattern (there are exceptions).
8. **VALIDATION_RULE really exists** (executor `GroovyValidationRule`) — don't treat it as "missing".
9. **Every auth predicate** `hasAnyRoleGroup("X")` requires roleGroup `X` + an assignment.
10. **Component names, not line numbers** — every claim here is stated as behaviour you can observe; class
    names are given only so you can ask the platform team a precise question.

---

_Related material: the id-link graph in §2 above, and [26](26-orchestration-and-testing.md) for the `plan.json`
coverage ledger that a Step-1 instruction document feeds._
