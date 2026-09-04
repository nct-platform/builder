# Business Logic plugin & dynamic CRUDs

## What it is / when to use

This is the **heart of dynamic integration**. The *Business Logic* plugin (`pluginName = "dynamic.cruds.plugin"`,
displayName "Business Logic Dynamic Integration") is the UI where a project **defines its own business logic
right in the browser, without a single line of Java**: dynamic CRUDs, their methods (SQL or Groovy), DTO fields,
filter fields, sources, and enums. All of this is exported into a separate file **`dynamic-cruds.json`**
(only for dynamic projects; see [00-export-format-and-import.md](00-export-format-and-import.md)).

A dynamic CRUD = a record in the project DB (tables `dynamic_crud`/`dynamic_method`/`dynamic_field`), from which
the runtime synthesizes a "virtual `@Crud` bean" with the same `ICrud` contract as static Java CRUDs.
That is why `crud.table.plugin`, forms, Groovy rules, and processes address a dynamic CRUD **exactly the same way**
as a static one — through `service.crud.<alias>.<method>(...)`. The only difference is where the method's
implementation lives: compiled Java code (static) vs a string of SQL/Groovy in the project DB (dynamic). All of this is managed
through the **system CRUD `bl`** (see below) — a thin RSocket wrapper over the `dynamic-integration-core` module
(the `dynamic-integration*` family of modules; the bean classes — `BlCrud`, `DynamicMethodExecutor`, etc. — live in `-core`).

> **🔧 Tooling.** For these entities, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `source add --dbtype POSTGRESQL ...`, `crud add --alias <a> --source <s> --schema <s> --field n:Type... --scaffold-methods` (creates 7 methods + paired queries `crud_<alias>_<method>`), `crud add-method <a> --type SQL|GROOVY`, `crud list`, `query add`. The full index and rules are in [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.

> ⛔⛔ **Turning a scaffolded method into GROOVY leaves its paired query behind with an EMPTY body — and the
> import REJECTS it.** The scaffold creates the methods *and* the query records `crud_<alias>_<method>`; the
> SQL bodies get filled in afterwards. The moment `create`/`update`/`delete` become GROOVY orchestrators (the
> normal shape for a header+lines document) those methods carry `queryIdentifier: null`, nothing ever fills
> their query records, and they ship as `"query": ""`.
>
> `QueryDto.query` is `@NotBlank`. Queries import BEFORE workflows, rules, contexts, form groups, forms,
> settings and process groups — so on a platform that stops at the first rejected object, the project arrives
> with a database and nothing else: every screen blank, and the only clue a card that says
> `Imported with warnings`. `validate` now ERRORs on a blank body and WARNs on a leftover paired
> record; `crud verify` runs the method's own `script` and never opens the query record at all.
>
> **Before packing, drop every query whose body is blank — but assert first that no method points at it.**
> A blank body on a query a method still references is a MISSING SQL body, not an orphan, and deleting the
> record would hide a real bug instead of fixing one:
>
> ```
> referenced = { m.queryIdentifier  for every method of every crud }
> blank      = { q  for q in queries  if not q.query.strip() }
> assert not (blank & referenced)     # a live method with no SQL — fix the method, do not delete
> queries   -= blank                  # the rest are scaffold leftovers — drop them
> ```
>
> Then confirm the identifiers you dropped survive nowhere else in the export: a chart or an embed keeping a
> reference to a deleted query is as silent as the empty body was.

> 🧭 **META-RULE — for any non-trivial dynamic-CRUD method SQL (param casts, null-handling, parent filtering,
> paging), TRANSCRIBE it from a REAL working export, byte-for-byte; do NOT hand-derive it from platform Java
> source.** A method's SQL runs through `DynamicMethodExecutor`, whose **param binding is not what a raw `psql`
> test shows** — several traps only bite at runtime and pass every offline gate:
> - **null / scalar vs map args.** A method called with a single scalar arg binds that value directly; a method
>   called with a **filter MAP** whose value is null gets that null **unpacked into an empty JSON object `{}`**, and
>   `{}` then fails any typed bind (e.g. `UUID.fromString("{}")`). Pass a scalar when the method takes one param.
> - **raw `:col::uuid` casts.** The executor infers the param type from the cast and runs `UUID.fromString(value)`;
>   an empty/`{}`/null value crashes. Bind as text and cast in-SQL — `CAST(NULLIF(:col,'') AS uuid)` — or use the
>   query-DSL `{name:'col', type:'uuid'}`.
> - **untyped param arithmetic.** `OFFSET (:pageNumber * :rowsInPage)` multiplies two params PG can't type →
>   `operator is not unique: unknown * unknown`. This bites **any** paginated `findAll` — flat table, not just a
>   tree — the instant a **rule** (assemble / choices / fetch) calls `service.crud.<alias>.findAll([...])`: the UI
>   table binds paging as typed ints, but a rule leaves them unbound → untyped NULL. **Fix: cast in the method
>   script — `OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))`** (a strict superset; correct
>   from both the UI and a rule). A tree's `findByParent` needs no paging at all, so drop `LIMIT`/`OFFSET` there.
> - **`find`/`findAll` with a PARTIAL param map** → the unbound `:col` first appears as `$1 IS NULL` → `could not
>   determine data type of parameter $1`.
>
> **`crud verify --db` substitutes literal values and runs the SQL directly — it proves the SQL is valid, NOT that
> the executor binds it the same way.** So for anything with the traps above, (1) copy the working export's method
> **and** the rule that calls it, and (2) confirm with a LIVE open, not just `crud verify`. The canonical tree
> recipe is transcribed this way in [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md); `validate`
> WARNs on the raw-`::uuid` and `:x * :y` tree traps (`_check_tree_config`).
>
> ⚠️ **`--scaffold-methods` emits PLACEHOLDER SQL, not runnable SQL.** The 6 SQL scripts are literal skeletons —
> `SELECT * FROM <table> …`, `INSERT INTO <table> (...) VALUES (...)`, `UPDATE <table> SET ... WHERE id = :id`,
> `DELETE FROM <table> …` (`crud_cmds.py` `_scaffold_methods`) — and the paired queries are created with
> **empty** `query` strings. It also **hardcodes the `id` parameterType to `Integer`** (`id_params = [("id",
> "Integer")]`). You MUST hand-fill both sides of every SQL method (the method `script` in `:param` form
> AND its linked query in `{name,type}` form) and, for a uuid PK, override the `id` param to `String`, **before**
> `validate`/`crud verify`. Scaffolding only lays down the correct method skeleton, ordering, and query linkage.

> **Relationship to static.** The static path (`@Crud`-annotated Java classes, the
> `ICrud<T,F,ID>` interface, `@FormField`, `@LocalizationField`, `CrudReactor`) is described in
> older platform documentation on the CRUD pattern. Those documents describe
> the **conceptual model that the dynamic side emulates**, but they **do not mention** `dynamic-cruds.json`, `bl`,
> `MethodType`, `FieldCategory` — i.e. they cannot be used to reconstruct the real export. Rely on the code +
> the export (below), and read the static docs as background. Important discrepancy: the static `ICrud` lists only
> `create/update/get/find` (no `delete`), whereas the **dynamic skeleton always generates 7 methods, including
> `delete`** (`10-crud-pattern.md` is incomplete here).

**When to use this document.** When you are assembling `dynamic-cruds.json` by hand: one CRUD record per
domain entity (table), the standard set of **7 methods** (`find` + 6 CRUD operations), DTO fields from the
table's columns. You describe the DB schema (the tables these CRUDs read from) separately in `project-db.dump` —
see [10-database-management.md](10-database-management.md). SQL methods reference saved *queries* in
`rep-objects.json` — see [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).
How a table/form reads data from a CRUD — see [04-crud-table-plugin.md](04-crud-table-plugin.md) and
[02-form-controls-reference.md](02-form-controls-reference.md).

**Where this file exists and where it doesn't.** `dynamic-cruds.json` is present **only** in dynamic exports and
only when `bl` is deployed. A **static** project — one whose CRUDs are compiled Java `@Crud` beans — has **no**
such file at all, no matter how rich its domain is. So the presence of `dynamic-cruds.json` in the archive, not
the size or subject of the project, is what tells you which kind of project you are holding.

## Export shape

`dynamic-cruds.json` (root is an **object**, not an array; exactly 2 keys):

```
{ "exportVersion": 1,
  "cruds": [ <DynamicCrudDefinitionDto>, ... ] }
```

`exportVersion` is the integer `1`. The file is **optional**: it is written only when `bl` is deployed and returned
at least one CRUD (`CmsProjectServiceImpl.java` — if the `bl` probe throws, the export silently skips the file).

One `cruds[]` record (corresponds to `DynamicCrudDefinitionDto`, `DynamicCrudDefinitionDto.java`). On
export it is emitted **truncated** (the internal `DynamicCrudsExport.ExportedCrud` does NOT write `id`/`creationTime`/
`modificationTime`):

```
{ "alias", "name",
  "sourceIdentifier", "sourceHost", "sourcePort", "sourceDb", "sourceSchema", "sourceUser", "sourcePassword",
  "localizationField",
  "methods":       [ <DynamicMethodDto>, ... ],
  "dtoFields":     [ <DynamicFieldDto>,  ... ],
  "filterFields":  [ <DynamicFieldDto>,  ... ] }
```

`methods[]` (`DynamicMethodDto`, `DynamicMethodDto.java`; in the export without `id`/`crudId`):

```
{ "methodName", "methodType"("SQL"|"GROOVY"), "script",
  "returnType", "returnsArray",
  "methodOrder",
  "ruleIdentifier"|null, "queryIdentifier"|null, "contextIdentifiers"|null,
  "returnFields": {col:Type}|null,
  "parameters": [ {"parameterName","parameterType","parameterOrder"}, ... ] }
```

`dtoFields[]` / `filterFields[]` (`DynamicFieldDto`, `DynamicFieldDto.java` — truncated on export, without
`id`/`crudId`/`fieldCategory`; `fieldCategory` is implicit from the array: `dtoFields`→`DTO`, `filterFields`→`FILTER`):

```
{ "fieldName", "displayName", "fieldType", "fieldOrder" }
```

### Worked example — `equipment_event_types_cruid`, the simplest "enum-table" CRUD

One `cruds[]` entry of a `dynamic-cruds.json` (shortened by methods). Note:
`find.ruleIdentifier == null`, `find.returnFields == null`, `find.contextIdentifiers == null` — this is the norm for
the large majority of CRUDs (auto-find sentinel, see Step 3):

```json
{
  "alias": "equipment_event_types_cruid",
  "name": "Equipment Event Types Cruid",
  "sourceIdentifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c",
  "sourceHost": "<db-host>",
  "sourcePort": 5432,
  "sourceDb": "prj_<realm>_<client>",
  "sourceSchema": "app_schema",
  "sourceUser": "prj_<realm>_<client>_user",
  "sourcePassword": "<generated-on-import>",
  "localizationField": "localized",
  "methods": [
    {
      "methodName": "find", "methodType": "GROOVY",
      "script": "def filter = param ?: [:]\ndef countResult = service.crud.equipment_event_types_cruid.count()\ndef total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long\ndef rows = service.crud.equipment_event_types_cruid.findAll(filter) ?: []\ndef rowsInPage = (filter.rowsInPage ?: 0) as int\ndef pageNumber = (filter.pageNumber ?: 0) as int\nreturn [\n    content: rows,\n    totalElements: total,\n    totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,\n    pageNumber: pageNumber\n]\n",
      "returnType": "Object", "returnsArray": false, "methodOrder": -1,
      "ruleIdentifier": null, "queryIdentifier": null, "contextIdentifiers": null, "returnFields": null,
      "parameters": [
        { "parameterName": "rowsInPage", "parameterType": "Integer", "parameterOrder": 0 },
        { "parameterName": "pageNumber", "parameterType": "Integer", "parameterOrder": 1 }
      ]
    },
    {
      "methodName": "findAll", "methodType": "SQL",
      "script": "SELECT * FROM dim_equipment_event_types WHERE 1=1 ORDER BY id LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))",
      "returnType": "Object", "returnsArray": true, "methodOrder": 0,
      "ruleIdentifier": null, "queryIdentifier": "5476804c-1e0c-4efc-af91-009b42c72609",
      "contextIdentifiers": null, "returnFields": null,
      "parameters": [
        { "parameterName": "rowsInPage", "parameterType": "Integer", "parameterOrder": 0 },
        { "parameterName": "pageNumber", "parameterType": "Integer", "parameterOrder": 1 }
      ]
    },
    { "methodName": "count", "methodType": "SQL",
      "script": "SELECT COUNT(*) as total FROM dim_equipment_event_types WHERE 1=1",
      "returnType": "Object", "returnsArray": false, "methodOrder": 1,
      "queryIdentifier": "53dc991f-5b83-40a1-bac8-f43c29cf1096", "parameters": [] },
    { "methodName": "get", "methodType": "SQL",
      "script": "SELECT * FROM dim_equipment_event_types WHERE id = :id",
      "returnType": "Object", "returnsArray": false, "methodOrder": 2,
      "queryIdentifier": "034b1c3d-f19e-4da2-8356-d65d7f6c9164",
      "parameters": [ { "parameterName": "id", "parameterType": "Integer", "parameterOrder": 0 } ] },
    { "methodName": "create", "methodType": "SQL",
      "script": "INSERT INTO dim_equipment_event_types (id, equipment_event_type, sort_order, is_active, localized) VALUES (gen_random_uuid(), :equipment_event_type, :sort_order, :is_active, :localized) RETURNING *",
      "returnType": "Object", "returnsArray": false, "methodOrder": 3,
      "queryIdentifier": "61fa0687-aaf2-4245-ab0b-cf3d553c96b2",
      "parameters": [
        { "parameterName": "equipment_event_type", "parameterType": "String",  "parameterOrder": 0 },
        { "parameterName": "sort_order",           "parameterType": "Integer", "parameterOrder": 1 },
        { "parameterName": "is_active",            "parameterType": "Boolean", "parameterOrder": 2 },
        { "parameterName": "localized",            "parameterType": "String",  "parameterOrder": 3 } ] },
    { "methodName": "update", "methodType": "SQL",
      "script": "UPDATE dim_equipment_event_types SET equipment_event_type = :equipment_event_type, sort_order = :sort_order, is_active = :is_active, localized = :localized WHERE id = :id RETURNING *",
      "returnType": "Object", "returnsArray": false, "methodOrder": 4,
      "queryIdentifier": "aaa02ae3-5da3-4fd9-85ed-95031675915d",
      "parameters": [ /* … same as create + id last */ ] },
    { "methodName": "delete", "methodType": "SQL",
      "script": "DELETE FROM dim_equipment_event_types WHERE id = :id RETURNING *",
      "returnType": "Object", "returnsArray": false, "methodOrder": 5,
      "queryIdentifier": "97ea1fb8-c5d1-4cd2-b749-74cd4ad8373e",
      "parameters": [ { "parameterName": "id", "parameterType": "Integer", "parameterOrder": 0 } ] }
  ],
  "dtoFields": [
    { "fieldName": "id",                 "displayName": "id",                   "fieldType": "Integer",    "fieldOrder": 0 },
    { "fieldName": "equipmentEventType", "displayName": "equipment_event_type", "fieldType": "String",     "fieldOrder": 1 },
    { "fieldName": "sortOrder",          "displayName": "sort_order",           "fieldType": "Integer",    "fieldOrder": 2 },
    { "fieldName": "isActive",           "displayName": "is_active",            "fieldType": "Boolean",    "fieldOrder": 3 },
    { "fieldName": "localized",          "displayName": "localized",            "fieldType": "ObjectNode", "fieldOrder": 4 }
  ],
  "filterFields": []
}
```

> ⚠️ **Deliberate discrepancy in this CRUD's `create` script — flag for the builder.** Suppose the table's DDL is
> `"id" integer NOT NULL DEFAULT nextval('app_schema.dim_equipment_event_types_id_seq'::regclass)`
> (see `project-db.dump`, the table's `ddl`), and the DTO field `id` has
> `fieldType:"Integer"`. The `create` above nevertheless inserts `id` via `gen_random_uuid()` —
> i.e. it puts a uuid into an integer-serial column. That is **stale/inconsistent** SQL, and real exports do carry
> such drift (SQL generated before the column acquired its `nextval` default, or hand-edited afterwards). The
> **correct** result of the canonical emitter for such a column is to **omit `id` from the INSERT** (the default
> fires on its own; `isAutoGenerated`, `DefaultMethodsDialog.java`). Do not derive from any export the rule
> "PK is always gen_random_uuid". See Step 2.

A dynamic project carries one such record per domain entity; they all share this structure — **7 methods each**
(1 GROOVY `find` + 6 SQL).

## Per-variant reference

### 1. CRUD level (`cruds[]`)

> **The `_cruid` suffix used in the examples below is a project convention, NOT a platform rule.** It is just
> how one project happened to name its aliases; the runtime does not require it. The alias must match **exactly**
> what existing consumers already reference (context `crudAliases`, `service.crud.<alias>`, form/table settings).
> Other projects use **bare camelCase** — `salesOrder`, `product`, `billOfMaterials`, `invoice`. For a
> greenfield CRUD pick ONE convention and apply it identically to the alias AND every consumer.

| Field | Type | Meaning | Req.? | Default | Backing |
|---|---|---|---|---|---|
| `alias` | String | Unique CRUD identifier; `service.crud.<alias>` resolves by it. In the export **without** the realm/client prefix (e.g. `tasks_cruid`). UI validator: `^[a-zA-Z][a-zA-Z0-9_]*$`. | yes | — | `DynamicCrudDefinitionDto.alias`; the prefix is added by `CrudKeyGenerator.createAlias` at runtime |

| `name` | String | Human-readable name (title in the list). | yes | — | `.name` |
| `sourceIdentifier` | String (UUID) | Reference to a *source* in `rep-objects.json.sources[]`, from which the credentials were taken. | no¹ | null | `.sourceIdentifier` |
| `sourceHost` | String | **Snapshot** of the source host (JDBC), copied into the CRUD. | no¹ | null | `.sourceHost` |
| `sourcePort` | Integer | Snapshot of the port (usually `5432`). | no¹ | null | `.sourcePort` |
| `sourceDb` | String | Snapshot of the DB name (e.g. `prj_<realm>_<client>`). | no¹ | null | `.sourceDb` |
| `sourceSchema` | String | Snapshot of the schema (e.g. `app_schema`). | no¹ | null | `.sourceSchema` |
| `sourceUser` | String | Snapshot of the JDBC user. | no¹ | null | `.sourceUser` |
| `sourcePassword` | String | Snapshot of the JDBC password (in plaintext in the export). | no¹ | null | `.sourcePassword` |
| `localizationField` | String | Name of the jsonb column for localization (usually `localized`). Makes the CRUD "have `@LocalizationField`". | no | null | `.localizationField`; set via `bl.setLocalizationField` |
| `methods` | array | The CRUD's methods. | yes² | `[]` | `.methods` |
| `dtoFields` | array | Result fields (form/table/hints). | no | `[]` | `.dtoFields` |
| `filterFields` | array | Filter fields (for the table's filter form). | no | `[]` | `.filterFields` |

¹ All `source*` fields are a **local copy** of the source's credentials, written into `dynamic_crud`. The runtime reads JDBC
from exactly these (`DynamicMethodExecutor.executeSqlMethod`: `crud.getSourceHost()` etc.,
`DynamicMethodExecutor.java`), not from `sources[]`. If `sourceHost == null`, SQL methods throw
`"CRUD '<alias>' has no source configured"` (`DynamicMethodExecutor.java`). `sourceIdentifier` is used
to "re-bind" credentials after a password rotation (`DynamicCrudsPlugin.rebindCrudsToSource`,
`DynamicCrudsPlugin.java`), and on **import** — to take the **live** credentials from
`rep-objects.sources[]` by this UUID (import prefers live credentials over the snapshot, falling back to the snapshot if the
source is not found — `CmsProjectServiceImpl.importDynamicCruds`). **When building the export by hand,
fill in all 8 fields** with values from the corresponding `sources[]` object (there you have
`hostName/port/dbName/schemaName/userName/password`).

² Technically you can create a CRUD without methods (`ensureDynamicSide`, `DynamicCrudsPlugin.java` creates
an empty one), but such a CRUD can do nothing. A working CRUD carries the standard set of 7 methods (below).

### 2. Method level (`methods[]`)

| Field | Type | Meaning | Req.? | Default | Backing |
|---|---|---|---|---|---|
| `methodName` | String | Method name. Standard: `find`, `findAll`, `count`, `get`, `create`, `update`, `delete`. Defines the `ICrud` contract. | yes | — | `DynamicMethodDto.methodName` |
| `methodType` | String | Enum `MethodType` — **exactly two values**: `"SQL"` or `"GROOVY"`. Dispatched in `DynamicMethodExecutor.executeMethod`. | yes | — | `.methodType` |
| `script` | String | For SQL — the executable text with `:param` placeholders. For GROOVY — the body of the Groovy script. Line breaks in the export are `\r\n` (SQL from a query) or `\n` (generated Groovy). | yes | — | `.script` |
| `returnType` | String | Simple return type. In **all** observed methods it is `"Object"`. | yes | `"Object"` | `.returnType` |
| `returnsArray` | Boolean | true → the method returns a list of rows. For `findAll` = true; for the rest = false. | yes | `false`/`true`³ | `.returnsArray` |
| `methodOrder` | Integer | Display order. Convention: `find`=**-1**, `findAll`=0, `count`=1, `get`=2, `create`=3, `update`=4, `delete`=5. | no | 0 | `.methodOrder` |
| `queryIdentifier` | String\|null | SQL only: UUID of a saved *query* in `rep-objects.json.queries[]` (mirrors the SQL in `{name:'x',type:'y'}` form). | no⁴ | null | `.queryIdentifier` |
| `ruleIdentifier` | String\|null | GROOVY only, and **mandatory for every GROOVY method except `find`** — without it the method does not run its script at all (*"has no rule identifier. Apply the CRUD first."*, see §Document CRUD variant). For a generated auto-find `find` = **null** (sentinel); non-empty → `find` is a real hidden rule (see Step 3). | no⁴ | null | `.ruleIdentifier` |
| `contextIdentifiers` | array\|null | Contexts of the Groovy rule. In practice: `[]` for a GROOVY-find with a real rule, `null` for auto-find and for all SQL methods. | no | null | `.contextIdentifiers` |
| `returnFields` | {col:Type}\|null | Result schema (for Groovy hints), `Map<String,String>`. Filled as a **side effect** of running the method via the Run dialog (`CrudEditorPanel.saveReturnFields`). Before the first Run = null. | no | null | `.returnFields` |
| `parameters` | array | The method's parameter list (see below). For SQL — extracted from `:param` automatically. | yes⁵ | `[]` | `.parameters` |

³ In the UI model `MethodFormModel.returnsArray` defaults to `true` (`CrudEditorPanel.java`), but the canonical
emitter sets it explicitly: for `findAll` → true, for all others → false (`DefaultMethodsDialog.java`).

⁴ A SQL method is executable even without a query (it runs its own `:param` `script`), but the UI always creates a paired query so that the SQL
is editable. Groovy method: `find` with `ruleIdentifier==null` is executable (auto-find sentinel); **any other
Groovy method without a rule is not executable — it throws on the first call.** Give it one with
`mrjun.py crud apply`.

⁵ Parameter order is critical: `parameterOrder` = position in the SQL / in the declaration. The executor unpacks
a single-argument Map by parameter names (`DynamicMethodExecutor.java`).

> **Searchable-dropdown methods (`ac*` pipeline) are NOT in this 7-method set.** A CRUD-backed *searchable*
> dropdown/autocomplete (`settings.searchEnabled`) needs, per search field `X`, an extra SQL method
> `acFindAllBy<Cap(X)>Like` (single typed `:X` param, `defaultValue ''`, `LIMIT 100`) + a Groovy wrapper
> `acFindBy<Cap(X)>Like`, fed by a rule `RIMM_FILT_<alias>_<X>` whose body ends in
> `toSelectOptions*`/`toAutoCompleteOptions`. Do NOT substitute a raw `findAll` choices rule. Full recipe + naming
> table: [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

**Example `returnFields`** (after Run) — `tasks_cruid.findAll`:
```json
{ "id":"Long", "title":"String", "dueDate":"String", "statusId":"Long", "createdby":"String",
  "localized":"String", "assignedTo":"String", "accountId":"String", "priorityId":"Long", "taskTypeId":"String" }
```
and `find` (real rule) — a fixed PageResult schema:
```json
{ "content":"String", "pageNumber":"Long", "totalPages":"Long", "totalElements":"Long" }
```

#### 2a. Parameter (`parameters[]`)

| Field | Type | Meaning | Req.? | Backing |
|---|---|---|---|---|
| `parameterName` | String | Name = the SQL placeholder name without `:` (e.g. `rowsInPage`, `id`, `equipment_event_type`). | yes | `DynamicParameterDto.parameterName` |
| `parameterType` | String | Java type. Observed in the export: `Integer`, `String`, `Boolean`, `BigDecimal`, `Instant`, `LocalDate`. The full set from `mapParamType` (`CrudEditorPanel.java`): `Integer`/`Long`/`Boolean`/`Double`/`LocalDate`/`LocalDateTime`/`LocalTime`/`Instant`/`BigDecimal`/`String`(default). | yes | `.parameterType` |
| `parameterOrder` | Integer | 0-based position. | yes | `.parameterOrder` |

> Note: the SQL parameter names for `create`/`update` are **snake_case** (matching the column:
> `equipment_event_type`), whereas the DTO field names are **camelCase** (`equipmentEventType`). Pagination and
> filter parameters are camelCase (`rowsInPage`, `pageNumber`, `assignedTo`).

### 3. Field level (`dtoFields[]` / `filterFields[]`)

| Field | Type | Meaning | Req.? | Backing |
|---|---|---|---|---|
| `fieldName` | String | The DTO property name in **camelCase** (`toCamelCase(columnName)`). The form/table binds the value by it; this is the `expression` in `CrudExtendedDto`. | yes | `DynamicFieldDto.fieldName` |
| `displayName` | String | ⚠️ **Not a human-readable label!** Here lies the source column name in **snake_case** (`equipment_event_type`). This is the inverse of the static `@FormField.displayName`. | yes | `.displayName` |
| `fieldType` | String | The field's Java type. **Commonly seen in dtoFields**: `Integer`, `BigDecimal`, `Boolean`, `LocalDate`, `Instant`, `String`, `ObjectNode`. The mapper's full set also includes `Long`/`Float`/`Double`, and for pg_enum columns `resolveFieldType` returns the **enum's name** (e.g. `OrderStatus`). Mapping: `DefaultMethodsDialog.mapDbTypeToFieldType` : `jsonb/json→ObjectNode`, `uuid→String`, `int4/smallint→Integer`, `int8→Long`, `numeric→BigDecimal`, `timestamp*→Instant`, `date→LocalDate`, default→String. | yes | `.fieldType` |
| `fieldOrder` | Integer | 0-based order (= the table's column order). | yes | `.fieldOrder` |

`fieldCategory` — enum `FieldCategory ∈ {DTO, FILTER}` (`entity/enums/FieldCategory.java`) — is **not** written to the
export; it is implicit from which array the field lies in. `filterFields[]` has the same structure; it differs in
its origin: it is generated from the **parameters of `findAll`** (except `rowsInPage`/`pageNumber`),
see `DefaultMethodsDialog.java`. Most CRUDs carry `filterFields: []` — a filter field appears only where the
`findAll` SQL was given a real filter column (e.g. `tasks_cruid` filtering on `assigned_to`), and such fields are
typically `String`:

```json
{ "fieldName": "assignedTo", "displayName": "assignedTo", "fieldType": "String", "fieldOrder": 0 }
```

## How to construct from scratch

Task: assemble a dynamic CRUD `dim_equipment_event_types` by hand and obtain **the same JSON** that
the UI exports. The order mirrors `DefaultMethodsDialog.doCreate`.

### Step 0 — source and schema

1. In `project-db.dump` there must exist a table `dim_equipment_event_types` in the schema `app_schema`
   (see [10-database-management.md](10-database-management.md)). The columns define the DTO fields and the SQL.
2. In `rep-objects.json.sources[]` there must be a source from which the credentials are copied, e.g.:
   ```json
   { "identifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c", "name": "app_schema",
     "sourceType": "INTERNAL", "dbType": "POISTGRESQL", "hostName": "<db-host>", "port": 5432,
     "dbName": "prj_<realm>_<client>", "schemaName": "app_schema",
     "userName": "prj_<realm>_<client>_user", "password": "<hex-encrypted>" }
   ```
   Copy `hostName/port/dbName/schemaName/userName/password` → `sourceHost/sourcePort/sourceDb/`
   `sourceSchema/sourceUser/sourcePassword` of the CRUD record, and `identifier` → `sourceIdentifier`.
   > ⚠️ `dbType` is **`"POISTGRESQL"`** (with a typo) — that is the canonical enum constant, NOT `"POSTGRESQL"`.
   > Copy the value as-is; do not "fix" it. See
   > [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md).

### Step 1 — the CRUD record

```json
{ "alias": "equipment_event_types_cruid", "name": "Equipment Event Types Cruid",
  "sourceIdentifier": "…", "sourceHost": "…", "sourcePort": 5432, "sourceDb": "…",
  "sourceSchema": "app_schema", "sourceUser": "…", "sourcePassword": "…",
  "localizationField": "localized",
  "methods": [], "dtoFields": [], "filterFields": [] }
```
`localizationField` = the name of the jsonb column (or `null` if there is none).

### Step 2 — the six SQL methods (findAll/count/get/create/update/delete)

`DefaultMethodsDialog.buildMethodDefsInternal`  emits the canonical SQL from the columns and the PK. Rules:

- **PK** is determined from the table; if there is none, the first column is taken.
- **create**: columns with a DB `DEFAULT` of the form `nextval`/`gen_random_uuid`/`uuid_generate` are **skipped** from the INSERT
  (`isAutoGenerated`) — the DB will set the value itself. The column `id integer DEFAULT nextval(...)`
  (as in this table) → **skipped**. A PK of type `uuid` **without** a DB default → `gen_random_uuid()` is emitted.
  Other non-PK columns (except auto-generated) → `:param` placeholders.
- **findAll**: `SELECT * FROM t WHERE 1=1[<filter>] ORDER BY <pk> LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))`.
  ⚠️ The **platform's** Create-Default-Methods emits the paging **untyped** — `OFFSET (:pageNumber * :rowsInPage)`
  (`--scaffold-methods` already emits the CAST form shown above, so only hand-written or platform-generated
  exports need this fix). That form works when the **UI table** calls findAll (pagination bound as typed ints) but **breaks the moment a Groovy/business-logic rule calls the paginated `findAll`** (unbound `pageNumber`/`rowsInPage` → untyped NULL → `operator is not unique: unknown * unknown`). Rules calling `service.crud.<alias>.findAll([...])` are common (assemble / choices / fetch rules), so **always transcribe the paging in the CAST form above** — it is a strict superset (correct from the UI table AND from a rule), in **both** the `methods[].script` (the form the executor actually runs) and the saved query. (Trees' `findByParent` avoid this entirely — no `LIMIT`/`OFFSET`.)
- **count**: `SELECT COUNT(*) AS total FROM t WHERE 1=1[<filter>]`.
- **get/update/delete**: `WHERE <pk> = :id`; create/update/delete end with `RETURNING *`.

#### ⛔ Guard EVERY parameter that reaches a NOT NULL column

**Found on a live database.** The only gate that sees this class is **`crud verify --db`**
([26-orchestration-and-testing.md](26-orchestration-and-testing.md) §3, tier **T3** — "real-row failures: CHECK
literal, NOT NULL, FK, no-op UPDATE"); `validate` and every other offline check stay **green** on it (verified:
`mrjun.py validate` on a project carrying the defect below emits nothing about the method — its only NOT-NULL rule
is "a `create` INSERT that OMITS a NOT NULL column", `tools/mrjunkit/validate_cmds.py:3058-3070`, and an UPDATE
that *computes* NULL into one is invisible to it).

**A dynamic-CRUD parameter is not a typed null when the caller omits it or the user clears the field.** The
executor binds an absent key as `stmt.setNull(idx, Types.NULL)` (`DynamicMethodExecutor.java`) and coerces
every *present* value **out of its text form** — `bindAs` is `value.asText()` + parse in every arm
(numeric and string alike; `normalizeDecimal` even strips human thousand separators). So the value
that actually reaches the slot is SQL `NULL` (absent) or `""` (a blank input) — and **both** destroy an arithmetic
write:

```sql
-- ⛔ DEFECT — a param flowing unguarded into a NOT NULL column (`amount numeric NOT NULL`)
UPDATE <entity> SET amount = amount + CAST(:amount AS numeric) WHERE id = :id RETURNING *
```

```sql
-- ✅ FIX — the guard idiom; an absent/blank delta becomes a no-op
UPDATE <entity> SET amount = amount + COALESCE(CAST(NULLIF(:amount,'') AS numeric), 0) WHERE id = :id RETURNING *
```

What each case does (every cell below was executed against a throwaway Postgres inside `BEGIN … ROLLBACK`):

| `:amount` arrives as | ⛔ unguarded | ✅ guarded |
|---|---|---|
| **absent** (`setNull`) | `amount + NULL` → **NULL** → `ERROR: null value in column "amount" of relation "<entity>" violates not-null constraint` | delta `0` → row unchanged, `UPDATE 1` |
| **blank `""`** | slot inferred `numeric` → `new BigDecimal("")` throws; the same SQL run literally: `ERROR: invalid input syntax for type numeric: ""` | delta `0` → row unchanged, `UPDATE 1` |
| **`"2.5"`** | applies | applies (10.000 → 12.500) |

State the consequence precisely: it is **not** "the delta is skipped". The expression evaluates to NULL, the
statement **sets the NOT NULL column to NULL**, and Postgres aborts it on the constraint at runtime — the write
that the user asked for is lost and the error surfaces from the form, not from any build step.

Why `NULLIF` is what makes it work: `CAST(:amount AS numeric)` makes Postgres infer the slot as `numeric`, so
`bindAs` takes the numeric arm and chokes on `""`; `NULLIF(:amount,'')` anchors the slot to a **text** literal, so
the executor takes the `setString` arm (`:413`), `''` survives as `''` → `NULL`, and `COALESCE(…, 0)` neutralizes
it. (Verified with `PREPARE`+`SELECT parameter_types FROM pg_prepared_statements`: unguarded → `{numeric,uuid}`,
guarded → `{text,uuid}`.) It is the **same anchoring trick** as the tree's `CAST(NULLIF(:parentId,'') AS uuid)`
(the META-RULE at the top of this doc; [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)
§"Tree fetch-rule") and as the NOT-NULL defaults in
[18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §1
(`COALESCE(NULLIF(:status,''), 'DRAFT')`, `COALESCE(NULLIF(:<c>,''), '<PREFIX>-' || …)`) — the toolkit's own
verifier names it *"the canonical write guard"* (`tools/mrjunkit/crudverify_cmds.py:112-113`). The platform's
Create-Default-Methods emitter never emits it (it only COALESCEs *filters*, `DefaultMethodsDialog.java` around
`buildFilterWhere`), so on every hand-written or lifecycle method **you** must add it.

> **THE RULE.** In any SQL method, **every** `:param` that reaches a **NOT NULL** column — directly (`SET c = :c`)
> or through an expression (`c + :c`, `c * :c`, `<fn>(:c)`) — must be written
> **`COALESCE(CAST(NULLIF(:c,'') AS <pgtype>), <neutral value>)`**. Neutral value = `0` for a `+`/`-` delta, `1`
> for `*`, and the column itself for a plain overwrite (`COALESCE(:c, c)` — the
> [18](18-existing-schema-to-dynamic-wiring.md) §1 update rule). Only a **nullable** column may take a bare `:c`.

**Review sweep — a guarded param never spells `CAST(:`**, so grep the generated method SQL for the unguarded form:

```bash
jq -r '.cruds[] as $c | $c.methods[] | select(.methodType=="SQL")
       | "\($c.alias).\(.methodName)\t\(.script)"' <project>/dynamic-cruds.json \
  | grep -E 'CAST\(:' | grep -vE 'CAST\(:(pageNumber|rowsInPage) AS integer\)'
# no jq:  grep -oE 'CAST\(:[A-Za-z0-9_]+ AS [a-z ]+\)' <project>/dynamic-cruds.json | sort -u
```

`CAST(NULLIF(:x,'') AS …)` cannot match `CAST\(:`, so the sweep never *hides* an unguarded param — but it is a
wide net, not a verdict: on one clean 131-method project it printed **84 hits and none was a defect** (the bulk is
the PK cast `CAST(:id AS uuid)` in a `WHERE`). Triage each hit: only a hit on the **write** side (`SET …` /
`VALUES …`) of a NOT NULL column is the defect. The paging casts are excluded because they write no column at all
(`LIMIT NULL OFFSET (CAST(NULL AS integer) * CAST(NULL AS integer))` runs as a no-op — checked; keep the casts,
a bare `NULL * NULL` is `ERROR: operator is not unique: unknown * unknown`), and a hit inside a `WHERE` predicate
is a read. Then re-run `crud verify --db`: it reports the offending method by name with the exact constraint
message (`x <alias>.<method>: null value in column "amount" … violates not-null constraint`) while its guarded
twin passes.

The key detail about the **two forms of SQL** — the same query is stored in two representations:

1. In the saved **query** (`rep-objects.json`) the SQL is in editable form with
   `{name:'rowsInPage', type:'integer'}` placeholders (example `crud_tasks_cruid_findAll` below).
2. In `methods[].script` (`dynamic-cruds.json`) the same SQL is **already converted** to `:name` form
   (`CrudEditorPanel.convertToNamedParams`). The executor runs precisely the `:name` version through its own JDBC
   (`executeSqlMethod`), and `queryIdentifier` is a reference into the query registry — **but not a passive
   one**: opening that method in the CRUD editor loads the script FROM the saved query and saving it writes
   the regenerated script back. So a fix applied to `methods[].script` alone runs correctly and is then
   silently reverted by a screen somebody only opened to look at. The two must be kept in sync; `validate`
   WARNs when they are different statements.

For each method:

- Create a query in `rep-objects.json.queries[]` with `name = "crud_<alias>_<methodName>"`,
  `sourceIdentifier` = the same UUID, `query` = the SQL in `{name,type}` form. **`hidden` is NOT set on the default
  Create-Default-Methods path** and remains `null` — `createQuery` (`DefaultMethodsDialog.java`) does not
  call `setHidden`. So in a real export the overwhelming majority of `crud_*` queries carry `hidden: null`; the
  odd `hidden: true` marks a method that was later re-saved through the per-method editor, where
  `CrudEditorPanel.saveQuery` calls `setHidden(true)`. **When building by hand, set
  `hidden: null` (or omit the field).** Take the query's `identifier` (UUID) → this is the method's `queryIdentifier`.
  Prefix: `"crud_" + crudAlias` (`DefaultMethodsDialog.java`).
- In `methods[]` add the method object with `script` = the `:name` form, `methodType:"SQL"`, `queryIdentifier` from
  the previous point, `returnType:"Object"`, `returnsArray` (true only for `findAll`), `methodOrder`
  (findAll=0…delete=5).
- `parameters[]`: extract the names from the `{name:'…'}` placeholders **in order of first appearance, without duplicates**
  (`extractParams`); `parameterType` = `mapParamType(type-tag)`:
  `integer`→`Integer`, `long`→`Long`, `boolean`→`Boolean`, `uuid`/`jsonb`/other→`String`, …).

Example pair (`tasks_cruid.findAll`, a CRUD whose `findAll` carries a filter column): the **query** in
`rep-objects.json`. This pair shows `hidden: true` — i.e. a method that was re-saved through the per-method
editor, which is **atypical**; for the default path `hidden` would be `null`:

```json
{ "identifier": "74a2ebcb-939f-4d67-b52b-4487709e3cbf", "name": "crud_tasks_cruid_findAll",
  "query": "SELECT *\r\nFROM tasks\r\nWHERE tasks.assigned_to={name: 'assignedTo', type: 'STRING'}\r\nORDER BY id\r\nLIMIT {name: 'rowsInPage', type: 'integer'}\r\nOFFSET ({name: 'pageNumber', type: 'integer'} * {name: 'rowsInPage', type: 'integer'})",
  "sourceIdentifier": "9801cfaa-e98d-4d1a-b960-7b7366f10a0c", "hidden": true, "parameters": {}, … }
```

and the **method** in `dynamic-cruds.json`:

```json
{ "methodName": "findAll", "methodType": "SQL",
  "script": "SELECT *\r\nFROM tasks\r\nWHERE tasks.assigned_to=:assignedTo\r\nORDER BY id\r\nLIMIT :rowsInPage\r\nOFFSET (:pageNumber * :rowsInPage)",
  "queryIdentifier": "74a2ebcb-939f-4d67-b52b-4487709e3cbf", "returnsArray": true, "methodOrder": 0,
  "parameters": [
    { "parameterName": "assignedTo", "parameterType": "String",  "parameterOrder": 0 },
    { "parameterName": "rowsInPage", "parameterType": "Integer", "parameterOrder": 1 },
    { "parameterName": "pageNumber", "parameterType": "Integer", "parameterOrder": 2 } ] }
```

### Step 3 — the Groovy `find` method (auto-paging wrapper)

Add the seventh method (`methodOrder: -1`, `methodType:"GROOVY"`, `queryIdentifier:null`, `returnType:"Object"`,
`returnsArray:false`). `parameters` — the same `rowsInPage`+`pageNumber` (+ filter columns, if any).

**Two variants, both common in real exports:**

**Variant A — auto-find sentinel (the norm for the great majority of CRUDs).** `ruleIdentifier: null`,
`contextIdentifiers: null`, `returnFields: null`. The executor recognizes this case
(`isAutoFindWrapper`: `methodName=="find" && methodType==GROOVY && ruleIdentifier is empty`,
`DynamicMethodExecutor.java`) and executes `findAll`+`count` **directly on the server** (`executeAutoFindWrapper`), NOT running the Groovy. `script` is stored only as documentation/fallback. **The script form that
older emitters produced** (this is what you will see in exports generated before the current source, see below):

```groovy
def filter = param ?: [:]
def countResult = service.crud.equipment_event_types_cruid.count()
def total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long
def rows = service.crud.equipment_event_types_cruid.findAll(filter) ?: []
def rowsInPage = (filter.rowsInPage ?: 0) as int
def pageNumber = (filter.pageNumber ?: 0) as int
return [
    content: rows,
    totalElements: total,
    totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,
    pageNumber: pageNumber
]
```

> **This code is a table page-wrapper, NOT a choices source.** It deliberately returns raw rows wrapped in
> `{content, totalElements, totalPages, pageNumber}` for a `crud.table.plugin`. Do NOT copy this shape into a
> dropdown/autocomplete CHOICES rule: a choices rule must instead convert rows to option pairs —
> `service.global.conversion.toSelectOptions(list,"<key>","<display>")` (localized CRUD: `toSelectOptionsLocalized`)
> / `toAutoCompleteOptions(list,"<display>")` — and must never pass a PARTIAL filter map to `findAll` (use
> `findAll([:])`). A raw `findAll`/`find` list → "No results found" + hidden Show-Nav. Full contract:
> [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

> ⚠️ **Script vs current source.** An export produced by an older emitter carries the **fallback** form
> `def filter = param ?: [:]` and `service.crud.<alias>.count()` **without arguments** (with a filtered CRUD
> spelling its defaults as `param ?: ['assignedTo': null]`). The **current** source `buildFindGroovyScript`
> (`DefaultMethodsDialog.java`) emits the **merge** form
> `def filter = [<defaults>] + (param ?: [:])` and `.count(filter)`. For variant A the **script is not executable**
> (auto-find intercepts `find` in Java before Groovy), so the discrepancy is harmless; but if you are matching an
> existing export byte-for-byte, use whichever form that export already uses rather than "upgrading" it.

The Java semantics of auto-find (important when building a CRUD by hand without `count`): `executeAutoFindWrapper`
(`DynamicMethodExecutor.java`) **requires** a sibling `findAll` (throws at if there is none), calls
`count` with the **same** `jsonParameters` as `findAll`, and if there is no `count` method — falls back
`totalElements` to `rows.size()`. The resulting shape: `{content, totalElements, totalPages, pageNumber}`.

> ⛔⛔ **A method whose `parameters[]` holds EXACTLY ONE entry must be NAMED by the map that calls it —
> otherwise the whole map is bound into that single slot.**
>
> When a caller passes one Map argument, the executor unpacks it by parameter name. With **two or more**
> declared parameters it always does. With **exactly one** it unpacks only if the map actually mentions that
> parameter — by name, by its camelCase form, or as the root of a `<ref>__id` path. If it does not, the call
> falls back to **positional** binding, and position 0 is the serialized map.
>
> This is not an exotic shape. It is the DEFAULT shape of `count` on any table with exactly one filter:
> `count`'s parameter list is `findAll`'s minus the paging keys, so one filter ⇒ one slot. Auto-find then
> calls `count` with the same argument map as `findAll` (paragraph above). A user who has typed nothing into
> the filter bar therefore sends `{"rowsInPage":20,"pageNumber":0}`, that map never mentions the filter, and:
>
> * on a scalar column the request dies —
>   `SQL execution failed: ERROR: invalid input syntax for type boolean: "{"rowsInPage":20,"pageNumber":0}"`;
> * on a **text** column nothing errors at all. The comparison runs against that JSON text, matches nothing,
>   and the screen shows an empty list with a `totalElements` of 0. Silent, and indistinguishable from
>   "there is no data yet".
>
> **Fix it on the CALLER side and do it unconditionally** — seed the map with every declared filter key,
> `null` where the user supplied nothing. A `null` means "no filter" to the usual
> `(CAST(NULLIF(CAST(:x AS text),'') AS <type>) IS NULL OR col = …)` guard, which is exactly what an absent key
> was meant to mean, so naming the key changes no result and removes the fallback:
>
> ```groovy
> // every declared filter slot named up front — to the parameter binder, absent ≠ null
> def filter = ['rowsInPage': attrs?.get('rowsInPage')?.asInt(),
>               'pageNumber': attrs?.get('pageNumber')?.asInt(),
>               'status': null, 'department': null]   // ← the declared filters, seeded
> ```
>
> ⚠️ **Seeding inside a conditional does not count.** A row-scope block that only runs for non-privileged
> users leaves the key absent for everyone else, so the privileged path takes the positional fallback — and
> on a text scope column returns nothing, silently, to exactly the people allowed to see everything. Seed the
> key in the literal; narrow it later.
>
> An offline gate catches this cheaply: for every `service.crud.<alias>.<method>(<map>)` in every rule, expand
> `find` to `findAll` + `count`, and fail when the target declares exactly one parameter the map literal never
> names. Where the argument is a local, read its literal plus any later `name['key'] =` assignment.
>
> ⚠️ **What that gate can and cannot reach.** It reads GROOVY callers — rule bodies and GROOVY method
> scripts — because those are the only call sites an export spells out. The caller named above as the
> default one, the table plugin sending its own filter map, is NOT a call site in the file: the plugin
> assembles the map at runtime from its filter controls. So a green gate proves your rules are safe,
> not that the table is. Seed the key in the map literal AND keep the parameter list of `count` from
> being a lone scalar — a filter set of two or more is immune by construction.

**Variant B — a real hidden rule (the minority: the handful of CRUDs whose `find` needs logic).** Here the
user saved `find` as a genuine Groovy rule through the method editor → `ruleIdentifier` = UUID,
`contextIdentifiers: []`, `returnFields` filled only if the method was ever run via Run (otherwise still
`null`). `find` can then carry **arbitrary** authorization/filtering logic. Example
`tasks_cruid.find` (it READS the user before paginating — note it does not yet USE what it read; `service.security.*` is available; the script is reformatted for readability — in a real export the `hasAnyRoleGroup("Manager")` call is often split across several lines):

```groovy
def userId = service.security.user().id
def isManager = service.security.hasAnyRoleGroup("Manager")

def filter = param ?: ['assignedTo': null]
def countResult = service.crud.tasks_cruid.count()
def total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long
def rows = service.crud.tasks_cruid.findAll(filter) ?: []
def rowsInPage = (filter.rowsInPage ?: 0) as int
def pageNumber = (filter.pageNumber ?: 0) as int
return [ content: rows, totalElements: total,
         totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,
         pageNumber: pageNumber ]
```

> ⛔ As written this gates nothing: `isManager` is computed and never applied. A real gate puts the scope into
> the map passed to `findAll` **and** into `count(filter)` (not `count()`), and the scoping key must be a
> declared parameter of both — otherwise the rows come back scoped while `totalElements` still reports every
> row, or nothing is scoped at all. Full doctrine:
> [04](04-crud-table-plugin.md#-who-sees-which-rows--decide-it-here-never-in-the-browser).

> **The variant-B rule is hidden and is NOT in `rep-objects.json.rules[]`.** Every variant-B `find.ruleIdentifier`
> resolves to nothing in `rules[]` — searching the export for that UUID returns no rule object.
> The rule is `hidden:true`, and `RuleServiceImpl.findAll`
> filters hidden rules out of the export. **Import re-creates it** from the method itself:
> `ensureHiddenGroovyRule` (`CmsProjectServiceImpl.java`) builds a `RuleDto` with
> `identifier=ruleIdentifier`, `name="crud_<alias>_<methodName>"`, `executor="GroovyExecutionRule"`,
> `ruleType=EXECUTION_RULE`, `status=ACTIVE`, `hidden=true`, `rule.ruleScriptStr = method.script`. **Implication
> for the builder:** if you set `find.ruleIdentifier`, be sure to include a genuine `script` (import
> takes the rule body from exactly there) — you do NOT need to create a separate record in `rules[]`. The simplest option is to keep
> **variant A** (`ruleIdentifier: null`) — then no rule is needed at all.

### Step 4 — dtoFields

One per table column (`DefaultMethodsDialog.java`):
`fieldName = toCamelCase(columnName)`, `displayName = columnName` (snake_case!),
`fieldType = resolveFieldType(col)` (pg_enum → enum name, otherwise `mapDbTypeToFieldType`), `fieldOrder = index`.

> **⚠️ A foreign-key column keeps its `_id`/`Id` suffix in the DTO field — name it `<ref>Id`, NEVER `<ref>`.**
> `toCamelCase` (`DefaultMethodsDialog.java`) only uppercases the letter after each `_`; it does **not** strip
> the suffix. So an FK column `category_id` → field **`categoryId`** (`displayName: "category_id"`), a column
> `counterparty_id` → **`counterpartyId`**, `created_by` → `createdBy`. A CRUD over an invoice table therefore
> carries `counterpartyId` / `statusId` / `createdBy`, never `counterparty` / `status`. **Do not "helpfully"
> drop the `_id` to name the field after the referenced entity** (`category` instead of `categoryId`) — three
> things break:
> - **write side** — `create`/`update` bind `:category_id`; the field must carry that raw FK value;
> - **the Join feature** — its reference name is *derived* by dropping `Id` off the FK field
> (`categoryId` → `category`, `FieldEditorDialog.java`), and FK auto-detection tries
> `camelToSnake(fieldName)` and `<field>_id` (`findFksForField`, `CrudJoinServiceImpl.java`); a field
>   already named `category` confuses both;
> - **`displayName` = the raw column** (`category_id`) — must stay the exact column name.
>
> The **bare `<ref>`** name (`category`, `counterparty`) is reserved for two *other* things, not the FK field itself:
> (1) the **join reference name** / SQL alias prefix (§ FK-join), and (2) the **nested-object** convention for
> an FK when a form sub-object needs `{category:{id,code,name}}` — that is the hand-authored `__` scheme in
> [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §1, a deliberate exception,
> not the flat default. For a normal flat CRUD the FK column is always `<ref>Id`.

### Step 5 — filterFields

Only if `findAll` has filter parameters (other than `rowsInPage`/`pageNumber`). For each:
`fieldName = toCamelCase(paramName)`, `displayName = paramName`, `fieldType = mapParamType(paramType)`,
`fieldOrder` incrementing (`DefaultMethodsDialog.java`). For a pure enum CRUD — `filterFields: []`.

### Result

The assembled object will match the worked example above (for variant-A find — with the caveat about
the fallback form of the script from Step 3). Dynamic CRUDs immediately become available through
`service.crud.equipment_event_types_cruid.*` in rules (see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)),
`crud.table.plugin` (see [04-crud-table-plugin.md](04-crud-table-plugin.md)), and forms. The table pulls rows by
**running the CRUD's `find` rule** (see [04-crud-table-plugin.md](04-crud-table-plugin.md); rule-driven fetch).

## FK-join on a DTO field (the Field-dialog Join feature)

### What it is / when to use

Open a **DTO field** of a dynamic CRUD in Business Logic and the field editor shows a **"Join" section**. It lets
you **lift columns from a referenced table into this CRUD's own DTO without writing SQL** — the dynamic analogue
of following a foreign key to show a human label (`counterpartyName`) next to the raw FK id (`counterpartyId`).
On **Apply** the
platform (`CrudJoinServiceImpl`) does two things at once:

1. **Rewrites the CRUD's `dynamic_field` rows** — keeps the original FK field and adds one sibling flat field per
   lifted column.
2. **Regenerates the SELECT-side methods** (`findAll`, `get`, and, for a tree CRUD, `findAllByParent`) so they
   `LEFT JOIN` the target table and select its columns aliased so the executor surfaces them on the wire.

This is how a CRUD ends up with fields like `invoices_cruid.counterpartyName` / `statusStatusEn` alongside the
raw `counterpartyId` / `statusId`. Typically only a few CRUDs in a project carry a join, and each of them shows
it in exactly two methods — `findAll` and `get`.

> **There is NO toolkit command for the join.** `tools/mrjun.py` has no `crud join`; you author the joined
> methods + fields by hand (recipe below), then `validate`. The UI feature exists only in the browser; the
> export is just its result.

### ⚠️ Two join conventions in the platform — do not confuse them

The executor's `mapRow` (`DynamicMethodExecutor.java`) branches on the **SELECT alias** of a joined column:

| Convention | SELECT alias | Wire shape | Emitted by |
|---|---|---|---|
| **FLAT** (this feature, current) | `jN.<col> AS <ref>_<col>` — **single** `_` | flat key `<ref><Col>` (`counterparty_name` → `counterpartyName`) via plain `toCamelCase` (`mapRow`) | the UI Join feature — `buildJoinedSelectList` (`CrudJoinServiceImpl.java`) |
| **NESTED** (hand-authored) | `jN.<col> AS <ref>__<col>` — **double** `__` | true nested ObjectNode `{ref:{col}}` — `mapRow` splits on `__` and `container.with(...)` per segment  | hand-written SQL for a form sub-object / ObjectSelector — see [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §1 |

Both share the same `LEFT JOIN … jN … ON t.<fk> = jN.<pk>` skeleton and the base alias `t`; they differ **only**
in the number of underscores in the SELECT alias, and therefore in the wire shape (flat label vs nested object).
**The UI Join feature emits the FLAT form** (a single `_` in aliases such as `counterparty_name AS`,
`category_code AS`). Use the single-`_` flat form when you want a plain label column; use the double-`__` nested
form (doc 18) only when a consumer expects `{counterparty:{id,name}}`.

> **Stale in-code comments — trust the emitted SQL.** The `CrudJoinServiceImpl` class javadoc  and the
> `mapRow` comment  both say the Join feature emits `<ref>__<col>` / nested ObjectNodes. The
> **actual** `buildJoinedSelectList`  emits **single-`_` flat** aliases, and real exports agree. The
> comments describe an **older** scheme (there were three historically: dotted `cathegory.id`, then `__`-nested,
> now flat `<ref><Col>`); `rewriteDtoFields` even deletes leftover dotted rows on apply.

### What Apply regenerates (the crux)

`applyJoin` walks a **fixed method set** and, for each, compares the stored SQL against the freshly generated
joined SQL (`CrudJoinServiceImpl.java`):

| Method | Touched by join? | What happens |
|---|---|---|
| `findAll` | **YES** | rebuilt: explicit `t.<col>` list + `LEFT JOIN`s + `jN.<col> AS <ref>_<col>` (`buildJoinedFindAll`) |
| `get` | **YES** | same JOIN pattern, `WHERE t.<pk> = :id` (`buildJoinedGet`) |
| `findAllByParent` | **YES, only if it already exists** (tree CRUD) | JOINs + the parent-id predicate; never auto-created here — owned by `CrudTreeMethodService` |
| `create` | **NO — invariant** | FK column placeholder (`:counterparty_id`) stays; returns pre-join canonical INSERT. The original FK field carries the write value unchanged |
| `update` | **NO — invariant** | same — pre-join canonical UPDATE |
| `count` | **NEVER** | stays `SELECT COUNT(*) as total FROM <t> WHERE 1=1[filter]` — **no `t` alias, no JOIN**. Only the optional equality-filter predicate is preserved (`generateMethodSql`) |
| `find` (GROOVY) | **NO — params only** | body **untouched**; only its **paramDefs** are resynced to mirror `findAll`'s (`resyncFindMethodParams`) |

The SELECT transformation, stated precisely (base alias is always `t`):

- every base-table column becomes an explicit `t.<col>` (the pre-join `SELECT *` is expanded — needed so the
  joined columns can be added unambiguously);
- one `LEFT JOIN <target> jN ON t.<fkCol> = jN.<targetPk>` per join, **numbered `j1`, `j2`, … in join order**;
- one `jN.<col> AS <ref>_<col>` per lifted column — **except the FK target column itself** (`id`), which is
  skipped because the original FK field already carries that value (`buildJoinedSelectList` /
  `rewriteDtoFields`).

### DTO-field rewrite

`rewriteDtoFields` (`CrudJoinServiceImpl.java`): the original FK field (`counterpartyId`) **stays**; for each lifted
column it adds a sibling field inserted **immediately after** the FK field, shifting the `fieldOrder` of every
following field to make room :

| DTO field | value | source |
|---|---|---|
| `fieldName` | `<referenceName><CapitalizedCamelCol>` (e.g. `counterparty` + `Name` = `counterpartyName`) | — |
| `displayName` | the **raw target column name** in snake_case (e.g. `name`) — same "displayName = column" inversion as normal dtoFields | — |
| `fieldType` | the target column's Java type (from the target CRUD's DTO field, or `javaTypeOfPgColumn`) | — |

### Reference name

The **reference name** (`JoinRequest.referenceName`) is a user field in the dialog; it is the prefix for **both**
the SQL alias (`<ref>_<col>`) and the DTO field (`<ref><Col>`). Default (`FieldEditorDialog.java`): the FK
field name minus a trailing `Id` (`counterpartyId` → `counterparty`), else the camelCase of the target table.
On a **re-apply**, `parseJoinsFromSql` recovers the prior reference name from the SELECT alias prefix so a
user-customized name round-trips (`CrudJoinServiceImpl.java`).

### Worked example — `invoices_cruid` (two joins)

Two joins were applied to a finance CRUD: `counterparty_id → counterparties` (lift `name`) and
`status_id → dim_invoice_statuses` (lift `status_en`). **`findAll`** (single-lined by the `:name` conversion):

```sql
SELECT t.id, t.doc_number, t.counterparty_id, t.created_by, t.issue_date, t.due_date,
       t.posted_at, t.created_at, t.updated_at, t.localized, t.amount, t.status_id,
       j1.name AS counterparty_name, j2.status_en AS status_status_en
FROM invoices t
LEFT JOIN counterparties j1 ON t.counterparty_id = j1.id
LEFT JOIN dim_invoice_statuses j2 ON t.status_id = j2.id
WHERE 1=1 ORDER BY t.id LIMIT :rowsInPage OFFSET (:pageNumber * :rowsInPage)
```

The two **dtoFields** added — each sits right after its FK field; `displayName` is the raw target
column, `fieldName` is `<ref><Col>`:

```json
{ "fieldName": "counterpartyId",   "displayName": "counterparty_id", "fieldType": "Integer", "fieldOrder": 2 },
{ "fieldName": "counterpartyName", "displayName": "name",            "fieldType": "String",  "fieldOrder": 3 },
{ "fieldName": "statusId",         "displayName": "status_id",       "fieldType": "Integer", "fieldOrder": 12 },
{ "fieldName": "statusStatusEn",   "displayName": "status_en",       "fieldType": "String",  "fieldOrder": 13 }
```

Each insertion shifts the `fieldOrder` of everything after it — `status_id` was base index 11 and becomes 12
once `counterpartyName` is inserted at 3. `create` is **unchanged** by the join (`INSERT INTO invoices (..., counterparty_id, ..., status_id) VALUES (...,
:counterparty_id, ..., :status_id) RETURNING *`), and `count` stays `SELECT COUNT(*) as total FROM invoices WHERE 1=1`
— **no `t`, no JOIN**.

> **⚠️ `get` can lag `findAll` — a divergence that really occurs in the field.** The same CRUD can end up with
> `findAll` carrying **both** joins while `get` carries **only** the status join:
> `... j1.status_en AS status_status_en FROM invoices t LEFT JOIN dim_invoice_statuses j1 ON t.status_id = j1.id WHERE t.id = :id`
> — the counterparty join **missing** from `get`. Each method is classified and regenerated **independently**, and a
> user-customized (or conflict-cancelled) method keeps its own SQL (see the conflict modal below). **When
> authoring by hand, keep `get` and `findAll` carrying the SAME join set** — only `count` legitimately stays
> join-free.

### Single-join canonical form — `warehouses_ref`

A single-join `findAll` shows the **exact multi-line shape `buildJoinedFindAll` emits** (before the
`:name` conversion collapses whitespace), here lifting one column `warehouse_type` off `dim_warehouse_types`:

```sql
SELECT
    t.id, t.name, t.code, t.warehouse_type_id, t.area_m2, t.temp_min_c, t.temp_max_c,
    t.capacity_pallets, t.is_active, t.description, t.created_at, t.updated_at,
    t.localized,
    j1.warehouse_type AS warehouse_type_warehouse_type
FROM warehouses t
LEFT JOIN dim_warehouse_types j1 ON t.warehouse_type_id = j1.id
WHERE 1=1
ORDER BY t.id
LIMIT :rowsInPage
OFFSET (:pageNumber * :rowsInPage)
```

Reference name `warehouseType` (from `warehouse_type_id` minus `Id`) → alias `warehouse_type_warehouse_type`
(`camelToSnake("warehouseType")` = `warehouse_type`, `+ "_" + "warehouse_type"`) → DTO field
`warehouseTypeWarehouseType`, placed right after `warehouseTypeId`. This CRUD uses a `_ref` alias suffix rather
than `_cruid` — the suffix is arbitrary (see the alias note in §1).

### Multi-join safety & conflict resolution

- **Applying a second join must not strip the first.** `applyJoin` re-parses every prior `LEFT JOIN` out of the
  **stored `findAll` SQL** (`parseJoinsFromSql`, structural, robust against custom reference names), then
  `mergeWithInFlight`  either **replaces** the entry whose FK source column matches the new join
  (user re-edited the same FK) or **appends** it, re-numbering `j1/j2/…`. So `findAll` accretes joins. (Fallback
  when nothing parses: `discoverAllJoins` walks FK metadata + the flat-name pattern in the current DTO.)
- **User-customized methods surface a diff, never silent-overwrite.** A method whose stored SQL differs from
  **both** the new joined form **and** the pre-join canonical (modulo whitespace — `normalizeSql`) is queued into
  a single combined `MultiMethodConflictResolvePanel` diff. The user reviews every conflicting
  method side-by-side and clicks Override-all or Cancel; **Cancel leaves that method's custom SQL untouched** —
  which is one way `get` ends up lagging `findAll`.

### Manual (no-FK) join

A field **without a declared FK** can still join: pick any other table on the same source and any **type-compatible**
column to join on (`typeClassOf` groups pg types into NUMERIC/STRING/BOOL/DATE/…, `FieldEditorDialog.java`),
after acking a *"no foreign key … no referential integrity is enforced"* warning. Downstream
`applyJoin` treats it identically — the same `LEFT JOIN` template, keyed on the current field's underlying
column vs the picked column (`FieldEditorDialog.java`, the `else` branch).

### How to author a join by hand (no toolkit command)

Given a CRUD over table `t` with FK column `<fk>` (DTO field `<fkField>`) → target `<target>` (PK `<pk>`),
lifting target columns `c1,c2,…` under reference name `<ref>`:

1. **Keep** the original FK `dtoField` (`<fkField>`, e.g. `counterpartyId`) — it carries the write value.
2. **Add** one sibling `dtoField` per lifted column: `fieldName = <ref><CapitalizedCamelCol>`,
   `displayName = <raw snake column>`, `fieldType = <target column's Java type>`, `fieldOrder` = right after the
   FK field (shift the rest). **Do not** lift the target's PK/`<pk>` — it duplicates `<fkField>`.
3. **`findAll`**: expand to explicit `t.<col>` for every base column, add
   `LEFT JOIN <target> jN ON t.<fk> = jN.<pk>` per join (number `j1,j2,…`), and add `jN.<col> AS <ref>_<col>`
   to the SELECT. Same edit for **`get`** (keep its `WHERE t.<pk> = :id`). **Keep `get` and `findAll` join-set
   identical.**
4. **Leave `count` alone** (no `t`, no JOIN) and **leave `create`/`update` alone** (they keep `:<fk>`).
5. Update **both representations** of each regenerated method: the `methods[].script` (`:name` form) **and** its
   paired query `crud_<alias>_<method>` in `rep-objects.json` (`{name,type}` form) — see Step 2 above; they must
   stay in sync.
6. If the CRUD's Groovy `find` is variant B (a real rule), its paramDefs should mirror `findAll`'s (the UI
   resyncs them; for a pure auto-find `find` the JOIN doesn't add parameters so nothing changes).
7. **Underscore choice:** single `_` (`<ref>_<col>`) for a flat label field (this feature's default); double `__`
   (`<ref>__<col>`) **only** if you deliberately want a nested `{ref:{…}}` wire object — see
   [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §1. Then `validate`.

## Document CRUD variant (header + lines)

Everything above is the **flat CRUD** shape (one row = one entity). A **document**
CRUD (a header table with N child line rows — sales order, purchase order, bill of materials, goods issue,
customs declaration with consignment lines) does
NOT fit the flat shape: `create`/`update`/`delete` must orchestrate header **and** lines in one call, and
`findAll`/`get` must surface the lines as nested JSON so the form's `dynaform.form.list.field` sub-grid can render
them. The examples below use an ERP pair, `salesOrder` and `billOfMaterials`; the same shape applies to an
invoice with lines, a declaration with consignments, or any other header/detail document.

The shape:

- **`create`/`update`/`delete` are GROOVY** (`ruleIdentifier` set) — a short orchestration script, not SQL.
- They call **SQL helper methods**, each a plain SQL method with its **own paired query** (`crud_<alias>_<method>`)
  and **no `dtoFields`** of its own — the helpers are internal, not user-facing:
  - `createHeader` — INSERT the header, `RETURNING *` (GROOVY `create` reads `h.id`)
  - `updateHeader` — UPDATE the header `WHERE id = :id`
  - `insertLine` — INSERT one line row (called once per line)
  - `deleteLines` — `DELETE FROM <line> WHERE <header>_id = :id` (clears all lines for a header)
  - `_deleteHeader` — `DELETE FROM <header> WHERE id = :id RETURNING *`
- The GROOVY `create` = `createHeader(param)` then loop `insertLine` over `param.lines`; `update` =
  `updateHeader` + `deleteLines(param.id)` + re-`insertLine`; `delete` = `deleteLines(param)` then
  `_deleteHeader(param)` (**delete MUST cascade to lines** — a bare header DELETE FK-fails on any document that
  has lines). `salesOrder` also carries SQL **lifecycle** methods (`confirm`/`release`/`startPicking`/`complete`/
  `cancel`); `billOfMaterials` has `activate`/`deactivate`/`createNewVersion`.
- **`find`/`findAll`/`count`** stay as usual (auto-paging GROOVY `find` + SQL `findAll`/`count`). **`findAll`/`get`
  embed the lines** as a nested `json_agg(json_build_object(...))` subquery aliased `AS lines` — with the
  sub-grid's display fields (`product`/`uom`/`storageLocation` each `json_build_object('id',…,'code',…,'name',…)`),
  not just `id`, or every sub-grid cell renders the raw line UUID.
- **The nested `lines` array is NOT a `dtoField`** — it is surfaced only by the `findAll`/`get` SQL, never listed
  in `dtoFields`. The `dtoFields` describe only the header's own
  columns (with business-FK columns as `ObjectNode`, enum-lookup columns as `String`).

> ⛔⛔ **A GROOVY method that reads `param` MUST declare `parameters[]` — `parameters: []` silently drops the
> ENTIRE payload.** (Found on a live system. Beware: hand-built document CRUDs routinely ship
> `"parameters": []` on the GROOVY `create`/`update`/`delete`, so copying such a file verbatim reproduces the bug.)
>
> `param` inside the delegated rule is assembled **only** from `methods[].parameters`:
> `DynamicMethodExecutor.executeGroovyMethod` (`dynamic-integration-core/.../DynamicMethodExecutor.java`)
> fills its result map by iterating `paramDefs` — the DTO-unpack branch is gated on `!paramDefs.isEmpty()` and the
> positional fallback loops `i < paramDefs.size()`, so with an empty list **both branches are no-ops**. Then
> `ReactorServiceImpl.executeDelegatedRule` (`nct-executor/.../ReactorServiceImpl.groovy`) does
> `if (parameters) { executionVariables.put("__methodParams", …) }` — an empty Map is falsy in Groovy, so the
> marker is never sent — and `GroovyExecutionRule` binds `param` to an **empty HashMap**.
>
> Symptom: the form submits, the rule runs, and `createHeader(param)` writes NULL into every column →
> *"null value in column "doc_number" … violates not-null constraint"*. `delete` is worse: the single-param
> helper falls through to the positional branch and binds the literal `{}` to a uuid → *"invalid input syntax
> for type uuid"*. **No offline gate can see this** — the shape is valid, the SQL is valid, and `crud verify`
> substitutes parameters itself instead of going through the Groovy binding.
>
> **Declare one parameter per key the caller sends**, named exactly like the helper's SQL params
> (`doc_number`, `doc_date`, `partner__id`, …) plus the lines array key (`lines`) and, for update/delete, `id`.
> `mrjun.py validate` now ERRORs on a GROOVY method that mentions `param` with `parameters: []`.
>
> ⚠️ **A declared non-scalar parameter arrives as a raw Jackson `JsonNode`** — `GroovyExecutionRule` converts only
> textual/number/boolean values. Read `lines` with the JsonNode API (`.size()`, `.get(i)`, `.has(k)`, `.isNull()`,
> `.asText()`, `.numberValue()`) — the same API a `Find — …` rule uses for `attrs` — or via a
> shape-agnostic accessor; `x.someProperty` on a JsonNode throws `MissingPropertyException`.

> ⛔⛔ **Declare the FK BOTH ways: `<ref>__id` AND the plain `<ref>` — a form dropdown sends a scalar.**
> The executor fills `:<ref>__id` by WALKING the path: `walkParamPath` splits `purchaseOrder__id` into
> `purchaseOrder` → `id` and descends through the submitted map, giving up at the first non-object:
>
> ```java
> if (current == null || !current.isObject()) return null;      // DynamicMethodExecutor.walkParamPath
> ```
>
> An engine RULE passing `{purchaseOrder: {id: …}}` walks fine. A FORM does not: the dropdown bound to
> that nested dtoField (`fieldExpression: "purchaseOrder"`, `dataClass: java.lang.String`) puts the bare
> id STRING there. The walk hits `!isObject()`, the positional fallback finds neither `purchaseOrder__id`
> nor `purchaseOrderId` at the top level, the parameter is never set — and the INSERT writes NULL into
> the FK column. On a NOT NULL column that is `null value in column "po_id" … violates not-null
> constraint`, naming a column the author never typed; on a nullable one it is worse, because the row
> saves with a silently empty reference and only looks wrong later, in a table column or a chart.
>
> **No offline gate used to see this** — the SQL is right, the parameter IS declared, the script reads.
>
> Declaring both names is free: a parameter the caller does not send simply arrives absent. So do it
> unconditionally, and reconcile the two shapes in the script before calling the header helper:
>
> ```groovy
> def _id = { v ->
>     if (v == null) { return null }
>     if (v instanceof Map) { def m = v['id']; return m == null ? null : m.toString() }
>     if (v instanceof CharSequence) { def s = v.toString().trim(); return s.isEmpty() ? null : s }
>     if (v.respondsTo('isNull') && v.isNull()) { return null }
>     if (v.respondsTo('isObject') && v.isObject()) {
>         def n = v.get('id'); return (n == null || n.isNull()) ? null : n.asText() }
>     if (v.respondsTo('asText')) { def s = v.asText(); return (s == null || s.trim().isEmpty()) ? null : s }
>     def s = v.toString().trim(); return s.isEmpty() ? null : s }
> def _fk = { k -> def v = param[k + '__id']; return _id(v != null ? v : param[k]) }
>
> def hdr = new LinkedHashMap(param)
> hdr['purchaseOrder__id'] = _fk('purchaseOrder')
> hdr['supplier__id']      = _fk('supplier')
> def h = service.crud.goodsReceipt.createHeader(hdr)
> ```
>
> `_id` deliberately covers every shape the value can arrive in — scalar String, empty/whitespace String,
> Jackson `TextNode`, Jackson `ObjectNode`, Jackson `NullNode`, Groovy `Map`, absent — because the same
> method is called from both the UI and the rules, and gets a different one each way.
>
> ⚠️ **A FK the form does not ask for is not the same as a FK with no value.** A goods-receipt form asks
> for the purchase order, not the supplier — the supplier is a property of that order. Derive it rather
> than leaving it NULL, or every UI-created row is missing a reference every seeded row has:
> `if (hdr['supplier__id'] == null && hdr['purchaseOrder__id'] != null) { hdr['supplier__id'] =
> _id(service.crud.purchaseOrder.get(hdr['purchaseOrder__id'])?.get('supplier')) }`
>
> `mrjun.py validate` reports a `<ref>__id` declared without its plain `<ref>` — as an ERROR when a form
> control is actually bound to that field (the submit will fail), otherwise a WARNING.

> ⛔⛔ **A GROOVY method other than `find` MUST carry a `ruleIdentifier` — with `null` it does not run at all.**
> The `script` sitting next to the method is NOT what executes. `DynamicMethodExecutor.executeGroovyMethod`
> refuses before it looks at anything else:
>
> ```java
> if (method.getRuleIdentifier() == null || method.getRuleIdentifier().isBlank())
>     throw new IllegalStateException("Groovy method '" + name
>             + "' has no rule identifier. Apply the CRUD first.");
> ```
>
> and otherwise returns `{ruleIdentifier, status:"delegated", parameters}` — the script runs as an ordinary
> EXECUTION_RULE **looked up by that identifier**, with the arguments bound as `param`.
>
> In the UI that rule is written by the **Apply** button (`CrudEditorPanel.saveGroovyRule`, `hidden(true)`).
> Hidden rules are filtered out of the export, so `rep-objects.json` legitimately carries **none** of them —
> the importer re-creates each one from the method's own `script`
> (`CmsProjectServiceImpl.ensureHiddenGroovyRule`). But that re-creation is guarded:
>
> ```java
> if (isBlank(em.getRuleIdentifier()) || isBlank(em.getScript())) return;
> ```
>
> so **the identifier is the entire hinge**, and it is the one thing a file-first build has no reason to invent.
> Any UUID will do — the platform builds the rule around it. Absent, the method is dead in the imported project
> and the symptom never names it: a choices rule calling it renders an **empty dropdown**; a form action calling
> it reports *"Form submission failed: … Groovy method 'create' has no rule identifier. Apply the CRUD first."*
>
> `mrjun.py crud apply` mints the missing identifiers (idempotent), and `mrjun.py validate` ERRORs without them.
> Do **not** "fix" it by writing the rule into `rep-objects.json` — the importer owns that object, and a second
> copy drifts from the script.
>
> ⚠️ **`find` is the exception, and only `find`.** A GROOVY `find` with a blank `ruleIdentifier` is the
> **auto-find sentinel** of §Step 3 Variant A: `isAutoFindWrapper` catches it ahead of the delegation branch and
> `executeAutoFindWrapper` runs the sibling `findAll` + `count` in-process. Leave it null.

The full SQL bodies of these methods — the header INSERT/UPDATE with `COALESCE` NOT-NULL handling, the
`jN`/`elN` join-alias convention, the `json_agg` lines subquery, the enum-lookup `(SELECT id FROM lookup_x WHERE
code = :x)` write — live in **[18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §3**
(and the per-column rules in §1). Use that doc when the header sits over an existing populated table.

## Modifying a filled dynamic project

When the incoming `.mrjun` **already has** a working `dynamic-cruds.json` — a project handed to you with dozens
of CRUDs already wired — do not rebuild it; apply a surgical delta and re-validate:

- **`crud list --project <p>`** — inspect what already exists (alias, name, source, schema, method count) before
  touching anything.
- **`crud add --alias <a> --source <s> --schema <s> --field n:Type... --context <ctx> [--scaffold-methods]`** —
  add a NEW entity. `--context` appends the alias to that context's `crudAliases` **in the same call**
  (idempotent; `crud_cmds.py`), so the new CRUD is registered where consumers resolve it. Then hand-fill the
  scaffolded SQL (see the scaffold callout above) and add the entity's `dtoFields`.
- **`crud add-method <a> --name <m> --type SQL|GROOVY [--query <qid>|--rule <rid>] --script @file`** — add a new
  lifecycle/helper method to an existing CRUD (a new `insertLine`, a `post`/`cancel` status method, etc.).
- **Always re-run `mrjun.py validate` and `mrjun.py crud verify --db …`** afterward — a delta that breaks CHECK
  coverage, consumer wiring, or the delete-cascade only surfaces there. The full delta loop is in
  [19-build-decision-procedure.md](19-build-decision-procedure.md) (scenario C).

## `bl` — the control system CRUD (admin surface)

`bl` is a globally registered `@Crud` bean from `dynamic-integration-core`, with entry type = `DynamicCrudDefinitionDto`.
It **deliberately has no `@FormField`** (to avoid cluttering the field-expression dropdowns) and is edited only through
`DynamicCrudsPlugin`. All operations go over RSocket:
`reactorCrudService.executeCrudMethod(realm, client, "bl", <method>, args)`. The `bl` methods involved in
export/import (`CmsProjectServiceImpl`):

| `bl` method | Purpose |
|---|---|
| `getCruds()` | list of crud maps (probe of whether `bl` is deployed) |
| `create({alias,name})` | new CRUD → map with `id` |
| `deleteCrud(id)` | delete a CRUD (clean-slate on import) |
| `setSource(crudId, sourceId, host, port, db, schema, user, password)` | bind credentials |
| `setLocalizationField(crudId, columnName)` | assign the localize column |
| `getDtoFields(crudId)` / `getFilterFields(crudId)` / `getMethods(crudId)` | reading |
| `addMethod(crudId, methodDtoMap)` | method → map with method `id` |
| `addParameter(methodId, paramDtoMap)` | method parameter |
| `setReturnFields(methodId, Map<String,String>)` | result schema (hints) |
| `addDtoField(crudId, fieldDtoMap)` / `addFilterField(crudId, fieldDtoMap)` | fields |
| `addEnum({name, kind:"FREE", baseType})` | FREE enum (`CreateEnumDialog`, baseType ∈ {STRING, INTEGER}) |

**Import of `dynamic-cruds.json` — idempotent, optional** (`importDynamicCruds`, `CmsProjectServiceImpl.java`):
1. Staged during the `.mrjun` import: JSON → tenant-property `"initDynamicCrudsOnImport"`,
   replayed later, once the sources have already been created (the replay step removes the property).
2. `bl.getCruds` probe — if `bl` is not deployed (the probe throws), the entire dynamic-cruds import is **silently
   skipped** (dynamic-integration is optional).
3. Clean slate: `bl.deleteCrud(id)` for each existing dynamic CRUD (scope realm/client).
4. Pulls the live sources by `sourceIdentifier` (for fresh credentials).
5. Per crud: `bl.create` → `bl.setSource` (live credentials preferred over the snapshot) → `bl.setLocalizationField`
   (if set); per method: `ensureHiddenGroovyRule` (for GROOVY with a non-empty ruleId) → `bl.addMethod` →
   per param `bl.addParameter` → `bl.setReturnFields`; per dtoField `bl.addDtoField`; per
   filterField `bl.addFilterField`.

## Localization (`localizationField`)

- `localizationField` = the **column name** (usually `"localized"`, jsonb) or `null` (localization off) —
  the dynamic analogue of the static `@LocalizationField`. The DTO field for this column has `fieldType: "ObjectNode"`.
- On the wire the executor **aliases the chosen column to the canonical key `"localize"`** on read (in `mapRow`,
  `DynamicMethodExecutor.java`) and accepts it back under `"localize"` on write
  (`LOCALIZATION_CANONICAL_KEY = "localize"`). Therefore for all UI consumers (`LocalizedValueUtil`
  `FormPlugin`, `BaseFormControl`, `CrudTableColumnPanel`) the dynamic CRUD looks identical to a static one
  whose field is literally named `localize`.
- Value structure: `localize[fieldName][localeKey] = value` (locale keys `en_US`, `ru_RU`, `hy_AM`). In the raw DB
  rows the value is usually `null` until localization has been run.
- **Bulk "Localize" background task (`CrudDataLocalizeService`).** The "Localize" button on a DTO field kicks off a
  per-field background task (a fixed thread pool + task-id progress map) that walks **every** row of the CRUD (paged
  `find`, or recursive `find` by a parent-field filter for a tree — `CrudDataLocalizeService.java`) and, for each non-blank base value, fills the row's
  `localize[fieldExpression][localeKey]`: the default locale is copied verbatim from the base field, and each other
  target locale is machine-translated via `localizeService.translatePure(sourceValue, sourceLang, targetLang)`
  (`nct-ui/.../service/CrudDataLocalizeService.java`); a row already carrying all locales is skipped. Every changed
  row is persisted with an ordinary `service.crud.<alias>.update(entity)` call  — i.e. it writes back
  through the CRUD's own `update` method, so the localization column must be writable there (see the `:localize` /
  `COALESCE(:localize, localize)` rule in [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md)
  §1). Full localization model: [20-localization.md](20-localization.md) (see also memory
  `project_dyncrud_field_data_localize`).

## Dynamic vs static — how `service.crud.<alias>` resolves

Both styles yield the same `ICrud` contract; the difference is in the **resolver** and in what is in the export.

| Aspect | DYNAMIC | STATIC |
|---|---|---|
| Where the implementation lives | Strings of SQL/Groovy in the `dynamic_crud`/`dynamic_method` tables of the project DB | A compiled Java `@Crud` bean in a separate microservice |
| Export | Has `dynamic-cruds.json` (one record per entity) | **No** `dynamic-cruds.json`; the logic cannot be reconstructed from the export |
| Call resolution | `DynamicCrudMethodResolver` (`@Order(100)`, `DynamicCrudMethodResolver.java`) intercepts **before** reflection: if the alias has a row in `dynamic_crud` and the method exists in `dynamic_method` → `DynamicMethodExecutor.executeMethod` | The resolver returns `Optional.empty()` (no `dynamic_crud` row) → `CrudServiceImpl` defaults to reflection over the `@Crud` bean (`InvoiceCrud.find()` etc.) |
| SQL vs Groovy | `methodType` in `dynamic_method`: SQL → raw JDBC (`executeSqlMethod`); GROOVY → Groovy rule (`executeGroovyMethod`); `find` without a rule → auto-find | N/A — the method body = Java code |
| DTO fields/filters | Rows in `dynamic_field` (in the export `dtoFields`/`filterFields`) | Reflection over the DTO class's `@FormField` fields; marked `readonly=true` in `CrudExtendedDto` |
| Hybrid | An alias can have **both** a static `@Crud` bean **and** a `dynamic_crud` row (e.g. add a custom method to `TicketCrud`) — dynamic members are `readonly=false`. | Static members stay `readonly=true`; `DynamicCrudMethodResolver` returns empty for static method names → reflection over the bean (javadoc bullets, `DynamicCrudMethodResolver.java`). |

> A static export simply has **no** `dynamic-cruds.json`. Judge a project by that file's presence, never by how
> business-heavy its screens look.

The plugin shows **both** kinds in the left-hand list (`crudClient.findAll` returns everything, `DynamicCrudsPlugin.java`),
but edits only the dynamic members (Edit/Delete are hidden for `readonly` rows).

## Gotchas

- **Wiring an EXISTING schema (data already in the dump)?** That reverse scenario — converting a populated
  static schema to dynamic CRUDs — has its own playbook with the full column-handling table, enum-option snapshots, document
  lines + delete cascade, and the "verify against real rows" rule: **[18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md)**.
- **A method that writes a status/enum LITERAL must satisfy the column's CHECK constraint.** Lifecycle
  methods (`cancel`→`status='CANCELLED'`, `post`→`'POSTED'`, …) and status defaults write literal strings; if the
  literal isn't in the table's `CHECK (status IN (…))` set it throws **on any real row** (an empty-table smoke
  test never triggers it). CHECK constraints live in the dump's `schema.checkConstraints[]`, not the table `ddl` —
  inspect with `mrjun.py db show <table>`. `mrjun.py validate` flags a literal write outside the allowed set as an ERROR.
- **A parameter that reaches a NOT NULL column must be `COALESCE(CAST(NULLIF(:x,'') AS <type>), <neutral>)`.**
  Params arrive as text (`bindAs` = `asText()`+parse, `DynamicMethodExecutor.java`) and an absent one binds
  `setNull(Types.NULL)`, so `SET amount = amount + CAST(:amount AS numeric)` **sets the column to NULL**
  and aborts on the constraint the moment the delta is omitted or blank — while `validate` and every other offline
  gate stay green. Only `crud verify --db` ([26](26-orchestration-and-testing.md) §3 T3) catches it. Sweep for it:
  `grep -oE 'CAST\(:[A-Za-z0-9_]+ AS [a-z ]+\)'` over `dynamic-cruds.json` (a guarded param can never match).
  Full treatment + the neutral-value table: **[§ Step 2 — Guard EVERY parameter that reaches a NOT NULL column](#-guard-every-parameter-that-reaches-a-not-null-column)**.
- **An enum dropdown (`dataClass=<app>.dto.enums.<E>`, no `ruleIdentifier`) renders BLANK after import unless it
  carries a persisted `enumValues` snapshot.** The DynamicEnum registry is empty post-import and `Class.forName`
  of the integration enum fails in a REPORT project, so the only surviving option source is
  `settings.enumValues = {CONST:{name,displayName}}`. Populate it from the `lookup_<enum>` table's rows. `validate`
  warns on an enum dropdown with neither `enumValues` nor a choices rule. See [18](18-existing-schema-to-dynamic-wiring.md) §2.
  **A choices rule for a dropdown/autocomplete is NOT a raw row fetch — it MUST convert rows to option pairs:
  dropdown → `service.global.conversion.toSelectOptions(list,"<key>","<display>")` (localized CRUD:
  `toSelectOptionsLocalized`), autocomplete → `toAutoCompleteOptions(list,"<display>")`. Returning a raw
  `findAll`/`find` entity list → the picker shows "No results found" AND the Show-Nav affordance vanishes
  (`validate` now ERRORs on this). Searchable dropdown → the `acFindAllBy<Cap(X)>Like` pipeline. Full contract:
  [02-form-controls-reference.md](02-form-controls-reference.md) §4a.**
- **A document `delete` must cascade to its child lines.** A bare `DELETE FROM <header>` FK-fails on any document
  that has lines (the line FK is NO ACTION; the static app cascaded via JPA). Make `delete` a GROOVY method that
  calls `deleteLines` then the header delete. `validate` warns. See [18](18-existing-schema-to-dynamic-wiring.md) §3.
- **The `find` script in the export is the fallback form, not the current merge form.** Export: `def filter = param ?: [:]` +
  `.count()`. Current source (`buildFindGroovyScript`, `DefaultMethodsDialog.java`): `[<defaults>] +
  (param ?: [:])` + `.count(filter)`. For a variant-A find the script **is not executed** (auto-find intercepts in
  Java), so the discrepancy is harmless; to match the export — use the fallback form.
- **`find.ruleIdentifier == null` is a feature, not an omission.** The auto-find sentinel
  (`isAutoFindWrapper`, `DynamicMethodExecutor.java`). Do NOT add a rule for "completeness" — with a non-empty
  `ruleIdentifier` the executor will take the Groovy path and require a valid rule (re-created on import via
  `ensureHiddenGroovyRule`).
- **Auto-find requires a sibling `findAll`.** `executeAutoFindWrapper` throws if the CRUD has no `findAll`
  (`DynamicMethodExecutor.java`). `count` is optional — without it `totalElements = rows.size()`.
- **`hidden` for `crud_*` queries defaults to `null`.** The default Create-Default-Methods path (`createQuery`,
  `DefaultMethodsDialog.java`) does NOT set `hidden`. `hidden:true` appears only after re-saving
  a method in the per-method editor (`CrudEditorPanel.saveQuery`) — a small minority of the `crud_*`
  queries in any real export. When building by hand, set `hidden: null`.
- **`ruleIdentifier` (find, variant B) is absent from `rep-objects.json`.** The query for the SQL is present in
  `queries[]` (by `name = crud_<alias>_<method>`), but the hidden find-rule is **not** in `rules[]`: import creates it
  from `method.script` via `ensureHiddenGroovyRule`. Do not rely on every `ruleIdentifier` resolving in
  `rep-objects`.
- **Optional filters in SQL — only via `COALESCE`.** Write
  `<col> IS NOT DISTINCT FROM COALESCE({name:'<col>',type:'<t>'}, <col>)`, and **not** `(:col IS NULL OR col=:col)`
  and not `col = :col`. The executor hand-scans `:name` and emits a fresh `?` for **each** occurrence, plus binds a
  missing filter as `setNull(Types.NULL)` (OID 0) → Postgres "could not determine data type" precisely on
  an empty filter. The canonical emitter already does it right (`buildFilterWhere`, `DefaultMethodsDialog.java`).
  **Caller-side corollary:** the same failure fires from
  Groovy — `service.crud.<alias>.findAll(partialMap)` binds every declared filter param NOT in the map as
  `setNull(Types.NULL)` → untyped-`$1`, unless that column is COALESCE-guarded. `findAll([:])` (ALL keys absent) is
  safe; a PARTIAL map like `findAll([active:"true"])` when the CRUD declares other filter params is the trap. This
  bites choices rules especially — never `findAll([...])` in a dropdown choices rule; use `findAll([:])` or the
  `acFindBy<Cap(X)>Like` pipeline ([02-form-controls-reference.md](02-form-controls-reference.md) §4a).
- **`find`-merge vs `find`-fallback + the Java path.** The fallback script `param ?: [:]` calls `count()` without a Map, and
  `findAll(filter)` — with a partial Map (`rowsInPage`/`pageNumber`). The executor unpacks a single-argument Map by
  parameter names **only if** the key is present (`mapParam.has(onlyParam)`,
  `DynamicMethodExecutor.java`); otherwise it binds the whole Map into a single slot. But remember: for a variant-A find the script is not
  executed — the "count=0 → empty table" story is in fact decided by the **Java auto-find** (it calls `count` with the
  same `jsonParameters` as `findAll`). **Caveat — do NOT generalize "a partial Map to `findAll` is fine":** it
  is safe here ONLY because auto-find intercepts variant-A in Java. In an *executed* rule (a choices rule, a
  variant-B `find`, an action rule) a partial-map `findAll` binds unlisted filter params as `setNull` → untyped-`$1`
  unless the SQL is COALESCE-canonical (see the Optional-filters gotcha above). Use `findAll([:])` — ALL keys
  absent — for a no-filter fetch.
- **Parameter order and names are critical.** `parameterOrder` = the position of the `:param` appearance; duplicates are collapsed
  (first occurrence, `extractParams`). For `create`/`update` the parameter names are **snake_case** (matching the
  column), for pagination/filters — **camelCase**. A name mismatch will break the Map unpacking.
- **`displayName` in dtoFields is the snake_case column name, NOT a label.** The inverse of the static
  `@FormField.displayName`. `fieldName` is camelCase. Do not carry over the static meaning of `displayName`.
- **A foreign-key column keeps its `_id` suffix: field = `<ref>Id`, never `<ref>`.** `toCamelCase("counterparty_id")` =
  `counterpartyId` (the suffix is retained, not stripped). Naming the FK field after the entity (`counterparty`
  instead of `counterpartyId`) breaks the write side (`:counterparty_id`), the Join feature's reference-name derivation, and FK
  auto-detection. The bare `<ref>` form is only for the join reference name / SQL alias, or the deliberate
  nested-object convention ([18](18-existing-schema-to-dynamic-wiring.md) §1). See Step 4.
- **`source*` is a snapshot, not a reference.** The runtime reads JDBC from the CRUD record's `sourceHost/…/sourcePassword`, not from
  `sources[]`. When building by hand, duplicate the credentials; otherwise SQL methods will fail with "has no source configured"
  (`DynamicMethodExecutor.java`). `sourcePassword` in the export is in plaintext; **import** prefers
  live credentials from `sources[]` by `sourceIdentifier`, falling back to the snapshot.
- **The alias is unprefixed in the export, prefixed at runtime.** In `dynamic-cruds.json` the alias is "bare"
  (`tasks_cruid`); the full key `realm______________client______________alias` is assembled by
  `CrudKeyGenerator.createAlias`. Do not write the prefix into the export by hand.
- **`returnFields` = null until the first Run.** The result schema for Groovy hints
  (`CrudEditorPanel.saveReturnFields`; filled via the Run dialog,
  `RunMethodDialog.java`). Its absence does not hinder the method's operation — only the hints in the rule editor (see
  [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md)).
- **Enums do not live in `dynamic-cruds.json`.** STATIC/DB enums = pg_enum types in `project-db.dump` (see
  [10-database-management.md](10-database-management.md)); FREE enums are created via `bl.addEnum`
  (`CreateEnumDialog.java`, fields `name` + `baseType ∈ {STRING, INTEGER}`, `kind:"FREE"`) and stored on the
  dynamic-integration side — there is **no** separate enum section in the export at all. In a CRUD an enum is visible only as
  the `fieldType` of a DTO field (e.g. `OrderStatus` instead of `String`), if the pg_enum is registered.
  > ⚠️ **A FREE enum is NOT round-tripped — you cannot author one in a hand-built export.** `ExportedCrud`
  > (`CmsProjectServiceImpl.java`) carries **no** enum field, `DynamicCrudsExport` holds only `exportVersion` + `cruds` (no enum field),
  > and `importDynamicCruds` **never** calls `bl.addEnum` (0 hits for `addEnum` in the whole `CmsProjectServiceImpl.java`).
  > So a FREE enum lives **only** in the dynamic-integration DB — export drops it and import never recreates it. For a
  > user-editable enum in a hand-built project use a **pg_enum type** (`project-db.dump` `enumTypes[]`,
  > [10-database-management.md](10-database-management.md)) or a **`lookup_*` table**
  > ([18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) §2) instead — do NOT plan a
  > FREE enum, it produces an un-reconstructable project.
- **A pg_enum (`USER-DEFINED`) column needs NO manual `::enum_type` cast in `create`/`update`.** Bind a plain
  `:status`; the executor resolves the column's enum type from `ParameterMetaData` (fallback:
  `information_schema.columns.udt_name`, `DynamicMethodExecutor.lookupTargetTableColumnTypes`) and binds the value
  through a `PGobject` tagged with that type name (`bindAs` default branch), so Postgres applies the
  enum's input function. The `:status::<enum_type>` cast is needed **only** for a non-canonical write whose single
  target table the executor can't parse (a multi-table write / `INSERT … SELECT`), where the slot falls back to its
  declared type and an enum column bound as `character varying` throws `column "status" is of type … but expression is
  of type character varying`. This rule is derived from the executor's binding code, not from a worked example —
  pg_enum columns are rare in practice. Detail: [10-database-management.md](10-database-management.md) §enumTypes.
- **An FK-join regenerates `findAll`/`get` (and `findAllByParent`), NOT `create`/`update`/`count`.** Full
  treatment: **[§ FK-join on a DTO field](#fk-join-on-a-dto-field-the-field-dialog-join-feature)**. In short: the
  field dialog "joins" an FK → adds a `LEFT JOIN <target> jN ON t.<fk> = jN.<pk>` and columns
  `jN.<col> AS <ref>_<col>` (base alias `t`; example `invoices_cruid.findAll`:
  `LEFT JOIN counterparties j1 ON t.counterparty_id = j1.id`, flat DTO field `counterpartyName`). `create`/`update` are
  invariant (the FK placeholder `:counterparty_id` carries the write). `count` is **never** joined (no `t`, no JOIN) — so
  a join-based **filter** column must be threaded through both `findAll` and `count`, otherwise the two diverge
 (`CrudJoinServiceImpl`). **Single `_` = flat label field;
  double `__` = nested `{ref:{…}}` object** — do not mix them up.
- **The source's `dbType` in the export is `"POISTGRESQL"` (typo).** Do not "fix" it to `POSTGRESQL`; copy it as
  is from `sources[]`.
