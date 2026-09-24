# CRUD Tree & Process Table plugins

> ⛔ **`identifier` or `uniqueIdentifier`?** They are different ids with different scopes and swapping them fails silently. The rule, the source that decides it and the measured evidence: [01 — `identifier` vs `uniqueIdentifier`](01-content-model-and-pages.md#-identifier-vs-uniqueidentifier--read-this-before-you-reference-a-node).

> 📐 **Field evidence — trees, process tables, and what replaced them:** [03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md) · [05-process-and-scheduling.md](references/05-process-and-scheduling.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

`crud.tree.plugin` and `process.table.pluin` are two "list" plugins, siblings of
`crud.table.plugin` (see [04-crud-table-plugin.md](04-crud-table-plugin.md)). Both reuse
most of the CRUD-table model (columns, filters, actions, fetch-rule), so **this document
describes only the DELTA** — what differs — and points to 04 for the shared parts.

> ⛔ **ONE table per PAGE — the ONLY exception is separate tabs. This applies to ANY two table
> plugins, same type or not.** Do NOT put two `crud.tree.plugin`, two `process.table.pluin`, **or a
> mix** (a crud-table next to a process-table, a tree next to a table…) in one container. The one way
> to co-locate two tables is **each in its own tab** (`nct.tab.plugin`); otherwise give each its own page.
>
> Two independent reasons, and the second is the one that gets forgotten:
> 1. **Same type** — a hard technical collision: type-scoped `"CrudTreeSynced"` / `"ProcessTableSynced"`
>    sync + shared Settings-panel names broadcast page-wide, so the 2nd instance is unconfigurable and
>    they cross-bind.
> 2. **Mixed types** — the sync keys are distinct, so nothing *breaks*; it is still forbidden. A page is
>    one workplace answering one question, and two stacked grids make the reader work out which one they
>    are looking at. "No key collision" is not a licence to stack.
>
> `mrjun.py validate` ERRORs on both. Full mechanism: [14-plugin-catalog-all.md §2.3](14-plugin-catalog-all.md).

- **`crud.tree.plugin`** — the same CRUD, but with a self-referential hierarchy (`parent.id`). Roots are loaded
  via `findByParent(parentId=null)`, children via `findByParent(parentId=<parent's id>)`, lazily on clicking
  "expand". Separate action sets: `createActions` (breadcrumb buttons) and `editActions`
  (dropdown on each tree row).
- **`process.table.pluin`** — a table NOT over CRUD rows, but over **workflow process instances**
  (Flowable). Rows = processes, filtered by `processGroupIdentifier` + an optional
  `filterExpression`. Columns read values from the **process context** (GLOBAL / CONTEXT / CRUD
  scope), not from a flat CRUD row. Two kinds of actions: `userStartProcessActions` (start a process,
  breadcrumb buttons) and `globalActions` (actions over an existing process + task-actions of the
  workflow itself). Plus fields unique to the process: `indexSettings` (indexable context values) and
  `filterExpression` (a filter language over those indexes).

> ⚠️ The process plugin name is spelled **`process.table.pluin`** — this is a typo in
> `@PluginConfig(pluginName = "process.table.pluin", ...)` (`ProcessTablePlugin.java`). In the export
> `pluginName` must be exactly this, otherwise the node won't render.

> **🔧 Tooling.** For these entities, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `node add --plugin crud.tree.plugin --model @f` / `--plugin process.table.pluin` (the typo is preserved by the CLI), `node set-model`, `node patch-model`.
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.

## Export shape — where the node config lives

Both plugins **serialize the entire configuration into `properties.model.stringValue`** (a JSON string), NOT into
`properties.settings` like most form controls. ⚠️ The same config is **additionally mirrored** into the
`rep-objects.settings[]` object — and this applies to **all three** table plugins, not just the Process Table:
`crud.table.plugin` → `type:"CrudTable"`, `crud.tree.plugin` → `type:"CrudTree"`, `process.table.pluin` →
`type:"ProcessTable"` (the field is called `type`, not `settingsType`; `content` = the same keys). **The join key is
`setting.name == node.uniqueIdentifier`** — the mirror's `name` matches the node's `uniqueIdentifier`, never its
`identifier`. The node renders from
`properties.model`, and the settings object stores a named/reusable copy (a persistence artifact). The mirror is
**not strictly 1:1** with live nodes — a project that has been edited for a while carries orphan settings with no
backing node (leftovers of deleted nodes) and the importer
tolerates them; the required invariant is node→setting, not the reverse.
This is the key difference from the form controls in
[02](02-form-controls-reference.md): the node is read via `getContent().getJsonProperty("model", ...)`
(`CrudTreePlugin.java`, `ProcessTablePlugin.java`) and written via
`getContent().setJsonProperty("model", ...)` (`ProcessTablePlugin.java`).

**When the two disagree, `properties.model` wins.** That is not a convention you may choose differently — the
mirror's key carries no branch, and a branch clone keeps node unique identifiers, so a draft and the published
branch address the SAME mirror object; were the mirror authoritative, editing a table on a draft would change the
live page on save. A node whose configuration exists ONLY in the mirror is the legacy shape and still resolves —
it is read from the mirror once and rendered — but anything you AUTHOR belongs in `properties.model`, and the
platform refreshes the mirror from it on every save. See
[28-support-mode-over-mcp.md](28-support-mode-over-mcp.md) §4a for what that means when you edit a live project.

> ⛔⛔ **The MIRROR is read at RUNTIME, not just by the editor — keep it IN SYNC with the model.** The node, its
> columns and its rows render from `properties.model.stringValue` (`ProcessTablePlugin.java`), and so do **direct**
> actions (they execute inside the table plugin). But the **FORM that every NON-direct action opens is configured
> from the `rep-objects.settings[]` mirror**, never from the node: the platform loads the setting by
> `settingsService.findByName(node.uniqueIdentifier)` and reads `settings.content` (`SettingsNavigationHelper`,
> consumed by `FormPlugin` and `FormGroupLandingPlugin`) to obtain that action's `crudAlias`/`contextIdentifier`/
> `formGroupIdentifier`, its `onBeforeStart`/`onBeforeComplete` rule ids, its `predicateIdentifier`, and — for
> `process.table.pluin` — the `indexSettings` that get written into `paramsToFilter`. **There is no fallback to
> `properties.model` on that path.** So a generator/script that rewrites a node's `model` and leaves the mirror
> untouched ships a page that **renders the NEW config while the form runs the OLD one** — silently; and a
> *missing* mirror row leaves the form with no crud metadata at all, so it opens, fills, submits and writes
> NOTHING (server-side there is only a log warning). The author-side settings dialog reads the same row
> (`ProcessTableSettingsControlPanel.java`; the CrudTable/Tree panels do the same), which is why a stale mirror
> **also** shows the OLD config in the editor — for a `process.table.pluin` inherited from a starting-point
> baseline that means its **placeholder junk**: `filterExpression: "like(cusromerName, %{customer_name}%) && assigned=={assigned}
> && createdDate > {created_date}"` over non-existent fields, and a dangling `globalAction`. **Whenever you set a
> `crud.table`/`crud.tree`/`process.table` model programmatically, ALSO set
> `settings[name==node.uniqueIdentifier].content` to the SAME object, in the same step** (`node set-model` /
> `node patch-model` do it for you) — and scrub any orphan `type:"ProcessTable"`
> settings that no node's `uniqueIdentifier` matches (the baseline ships those with the same junk).

The `model` property on the node:

```json
"model": {
  "key": "model",
  "propertyType": "STRING",
  "required": false,
  "hidden": false,
  "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
  "arguments": {},
  "stringValue": "<JSON — the whole plugin configuration, as a JSON *string*>",
  "localizedStringValue": {}
}
```

The `crud.table.plugin` node from [04](04-crud-table-plugin.md) uses the same `properties.model` schema —
these three plugins are isomorphic at the wrapper level, differing only in the inner JSON.

The full set of `properties` slots on a process node: `className`, `styleName`, `tagProperties`, `model`,
**`isParsis`** (the tree/table
have no `isParsis` — this is specific to the process). The tree node has the standard `className`/`styleName`/`tagProperties`/`model`.

> ⚠️ **An "empty" starting-point export is usually NOT empty of process nodes.** Even an admin-scaffold baseline
> (see [SPEC / starting point Step-2](00-export-format-and-import.md)) typically ships a couple of
> **`process.table.pluin` nodes** whose `model.stringValue` is already populated
> (with `columnSettings`/`indexSettings`/`filterExpression`).
> Before you build on such a baseline, **decide: reuse those nodes (overwrite their `model`) or
> delete them and create your own** — they are not a "neutral template" but a concrete demo
> process configuration referencing `workflowIdentifier`/`contextIdentifier` UUIDs
> for which the baseline has **no** backing objects in `workflows[]`/`contexts[]` —
> the UUID strings survive only as dangling references in the mirror copies of `settings[].content` of the same
> process. So always grep a baseline for `process.table.pluin` before assuming it is blank.

The process node additionally carries a boolean `isParsis` property (participation in the parsis snapshot, see
[01](01-content-model-and-pages.md)); it is normally `false`:

```json
"isParsis": { "key":"isParsis", "propertyType":"BOOLEAN", "booleanValue":false,
  "fieldPanelClass":"...PropertyBaseCheckboxFieldPanel", "required":false, "hidden":false }
```

---

# Part 1. `crud.tree.plugin`

## Full example (a `category` taxonomy tree — node `name:"CRUD Tree"`, `identifier: e45f8ac2-6bab-42b6-a1dd-c816481c7a9c`)

`properties.model.stringValue`, parsed:

```json
{
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "category",
  "parentFieldExpression": "parent.id",
  "parentFilterFieldExpression": "parentId",
  "columnSettings": [
    { "id": "aed6e5c0-4da5-4441-88b4-137133569b9e", "name": "Code", "fieldExpression": "code", "dataClass": "java.lang.String" },
    { "id": "3791fe0f-abea-485c-bb44-a6fc2bc5d56c", "name": "Name", "fieldExpression": "name", "dataClass": "java.lang.String" }
  ],
  "filterSettings": [
    { "id": "917e2644-7330-4d47-9dad-abee4a31e015", "name": "Active", "filterField": "active", "dataClass": "java.lang.Boolean", "defaultValue": "true" }
  ],
  "createActions": {
    "actions": [
      { "id": "f42030a6-cd7e-4661-b479-2dab65479929",
        "localizedNames": { "en_US": "Create Category", "hy_AM": "Ստեղծել կատեգորիա", "ru_RU": "Создать категорию" },
        "localizedButtonNames": { "en_US": "Create Category", "hy_AM": "Ստեղծել կատեգորիա", "ru_RU": "Создать категорию" },
        "icon": "pe-7s-plus",
        "formGroupIdentifier": "25df6591-5cde-4dfe-8079-ed089d9d5773",
        "direct": false,
        "onBeforeCompleteRuleIdentifier": "16361f3b-d55a-4dd6-b6c9-5e671180f8e7" }
    ]
  },
  "editActions": {
    "actions": [
      { "id": "7c07bac1-3ab3-4edc-970b-1a1d481332d7",
        "localizedNames": { "ru_RU": "Редактировать категорию", "en_US": "Edit Category", "hy_AM": "Խմբագրել կատեգորիան" },
        "localizedButtonNames": { "ru_RU": "Редактировать категорию", "en_US": "Edit Category", "hy_AM": "Խմբագրել կատեգորիան" },
        "icon": "pe-7s-pen",
        "formGroupIdentifier": "25df6591-5cde-4dfe-8079-ed089d9d5773",
        "direct": false,
        "onBeforeCompleteRuleIdentifier": "a76e8fc5-a5b6-4ea1-a4dc-6a918f5d39a6" },
      { "id": "70e51d09-e792-40da-bcfd-431cc7d53b74",
        "localizedNames": { "ru_RU": "Создать ребенка", "en_US": "Create Child", "hy_AM": "Ստեղծել երեխա" },
        "localizedButtonNames": { "ru_RU": "Создать ребенка", "en_US": "Create Child", "hy_AM": "Ստեղծել երեխա" },
        "icon": "pe-7s-plus",
        "formGroupIdentifier": "25df6591-5cde-4dfe-8079-ed089d9d5773",
        "direct": false,
        "onBeforeStartRuleIdentifier": "71245949-8be1-454c-9943-751a86d12a49",
        "onBeforeCompleteRuleIdentifier": "a76e8fc5-a5b6-4ea1-a4dc-6a918f5d39a6" },
      { "id": "f20a266a-c76c-48d0-9901-19277973536e",
        "localizedNames": { "ru_RU": "Удалить категорию", "en_US": "Delete Category", "hy_AM": "Ջնջել կատեգորիան" },
        "localizedButtonNames": { "ru_RU": "Удалить категорию", "en_US": "Delete Category", "hy_AM": "Ջնջել կատեգորիան" },
        "icon": "pe-7s-trash",
        "direct": true,
        "onBeforeCompleteRuleIdentifier": "d16fdb47-5a03-412b-afb6-71d64a2affe4" }
    ]
  },
  "rowsPerPage": 2147483647,
  "findRuleIdentifier": "da08c1ea-17a9-4a69-abce-fcfe7d8e825a"
}
```

## Field-by-field: `CrudTreePluginModel`

Backing: `CrudTreePluginModel.java`.

| Field | Type | Meaning | Req. | Default | Backing |
|---|---|---|---|---|---|
| `contextIdentifier` | String | Context for Groovy rules to access other CRUDs; when empty — falls back to `crudAlias` when computing action visibility predicates (`CrudTreePlugin.java`). | no | — | `CrudTreePluginModel.java` |
| `crudAlias` | String | Alias of the main CRUD shown by the tree. **Without it the node renders the placeholder** "CRUD Tree (not configured)" (`CrudTreePlugin.java`). | yes (for data) | — | |
| `parentFieldExpression` | String | **DTO-side** of the parent reference, e.g. `"parent.id"` — a path in the data row. Used as a fallback filter key if `parentFilterFieldExpression` is empty. | yes¹ | — | |
| `parentFilterFieldExpression` | String | **FILTER-side** — the field name in the filter class, e.g. `"parentId"`. It is exactly this that the provider puts into the filter map when calling `findByParent` (`CrudTreeDataProvider.java`). | yes¹ | — | |
| `columnSettings[]` | `CrudTableColumnSettings[]` | Columns. The **first** becomes the tree column (expand icon + value), the rest are ordinary. See [04](04-crud-table-plugin.md) — the type is fully shared. | no | `[]` | |
| `filterSettings[]` | `CrudTableFilterSettings[]` | CRUD filters (the same as the table's). Their `defaultValue` is mixed into every `findByParent` call (`CrudTreeDataProvider.java`). | no | `[]` | |
| `createActions` | `CrudTableActionsDto` | **Create** actions — rendered as breadcrumb buttons (`CrudTreePlugin.breadcrumbButtons`; loop over `createActions`). | no | — | |
| `editActions` | `CrudTableActionsDto` | **Row** actions — dropdown in the last column (`CrudTreePlugin.java`). | no | — | |
| `rowsPerPage` | int | **DEAD FIELD on a tree — never read.** `CrudTreePlugin.java` hardcodes `Long.MAX_VALUE` as the page size instead of the model value, so a tree **has no pagination at all** and setting this to 15 changes nothing. (Contrast `CrudTablePlugin.java`, which passes `getModelObject().getRowsPerPage()`.) Keep the `2147483647` default so the JSON does not imply a setting that works. | no | `2147483647` | |
| `findRuleIdentifier` | String | Identifier of the EXECUTION rule the tree runs to fetch a node's children (`service.crud.<alias>.findByParent(...)`). Auto-created on render if empty (see below). | yes² | — | |


> **The tree's FIRST column is rendered by a different code path.** `CrudTreePlugin.newContentComponent`
> draws it as a bare `Label` next to the expand/collapse junction, so it never reaches the shared cell
> factory: **boolean icons and right-alignment do NOT apply to column 0** (they do to every other
> column). `money` and `dateFormat` DO apply to it, because those are resolved inside
> `extractColumnValue`, which the first column does call. If you need a boolean icon on the first
> column, move that column down and put a text column first.

¹ **Either one** of `parentFieldExpression` / `parentFilterFieldExpression` is enough for the tree
to start rendering (`CrudTreePlugin.java`). The data provider prefers
`parentFilterFieldExpression`, and in its absence falls back to `parentFieldExpression`
(`CrudTreeDataProvider.effectiveFilterKey`). In practice specify **both**: the DTO path and
the filter name often differ (`parent.id` vs `parentId`).

² On render, if `crudAlias` is set but `findRuleIdentifier` is empty, the plugin calls
`crudDataRuleService.ensureFindByParentRule(...)` and writes the resulting id back into the model
(`CrudTreePlugin.java`). So you can OMIT it from the export — the rule will be created on first
render. But for a fully self-contained export it's better to specify both the rule and `findRuleIdentifier`.

## Tree fetch-rule (`findRuleIdentifier`) — the key difference from the table

The table (04) runs `find(filter)`; the tree runs **`findByParent(...)`** to fetch a node's children
(`null` parent = the root nodes). The rule is an `EXECUTION_RULE` / `GroovyExecutionRule`, **context-free**
(context-free `service.crud.<alias>`), auto-named `"Find children — <CrudName>"` (`CrudDataRuleServiceImpl.java`).

> ⭐ **CANONICAL, LIVE-VERIFIED recipe — COPY THIS.** It is the shape that drives a real tree end-to-end,
> TWO pieces and nothing else:
>
> **(1) The fetch RULE** — read `parentId`, pass the raw parentId **STRING (or null) DIRECTLY** to `findByParent`
> (a scalar, **NOT a filter map**):
> ```groovy
> def parentId = attrs?.get('parentId')
> def pid = (parentId != null && !parentId.isNull()) ? parentId.asText() : null
> return service.crud.<alias>.findByParent(pid)
> ```
> **(2) The `findByParent` METHOD** — a **SQL** method, a **SINGLE `parentId` (String)** param, **NO `LIMIT`/`OFFSET`**,
> a null-safe text cast:
> ```sql
> SELECT t.* FROM <table> t
> WHERE t.parent_id IS NOT DISTINCT FROM CAST(NULLIF(:parentId, '') AS uuid)
> ORDER BY <col>
> ```
> `CAST(NULLIF(:parentId,'') AS uuid)`: a null/empty `parentId` → `NULL` → `IS NOT DISTINCT FROM NULL` → the **root**
> rows; a real uuid string casts cleanly. **No pagination** — a tree shows ALL children of a node. That's the whole
> thing.
>
> 🧭 **META-RULE, learned the hard way (two failed attempts): for a tree / any dynamic-CRUD method, TRANSCRIBE the
> method + rule from a KNOWN-WORKING tree** (the shape above, or `jq` a working project's `dynamic-cruds.json` +
> its `Find children — X` rule), byte-for-byte. **Do NOT hand-derive the SQL from platform source** — both failure modes in TRAP #1/#2 below came
> from deriving (`:parentId::uuid` raw cast; a paginated `:pageNumber * :rowsInPage`; a filter-map arg whose null
> parent unpacks to `{}`).

**The platform's auto-gen variant (also valid, but subtler — prefer the recipe above).** When `findRuleIdentifier`
is blank, `CrudTreePlugin` calls `ensureFindByParentRule` → `buildFindByParentScript`
(`CrudDataRuleServiceImpl.java`), which builds a rule that forwards a filter **MAP** and calls
`findByParent(filter)`; its paired method uses the **type-aware query-DSL** placeholder
`IS NOT DISTINCT FROM {name:'parentId', type:'uuid'}` (`CrudTreeMethodService.buildFindByParentSql`), which binds
null-safely. This works in the auto-gen path — but ONLY because the method SQL uses that DSL (not a raw
`:parentId::uuid`) and tolerates the map's null→`{}` unpacking. Here it is for reference, as generated for a
`category` tree (rule `da08c1ea-17a9-4a69-abce-fcfe7d8e825a`):

```groovy
// Platform AUTO-GEN (map form). Works with the type-aware DSL method SQL; do NOT copy this together with a
// hand-written `:parentId::uuid` method SQL — the map's null parent unpacks to `{}` and crashes (TRAP #2).
def parent = attrs?.get('parentId')
def filter = [
    'rowsInPage': attrs?.get('rowsInPage')?.asInt(),
    'pageNumber': attrs?.get('pageNumber')?.asInt(),
    'parentId': (parent == null || parent.isNull()) ? null : parent.asText()
]
attrs?.each { k, v ->
    if (k != 'rowsInPage' && k != 'pageNumber' && k != 'parentId' && v != null && !v.isNull()) {
        filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText())
    }
}
return service.crud.category.findByParent(filter)
```

> ⛔ **TRAP — do NOT reuse a flat table's generic `find(filter)` fetch rule as a tree's `findRuleIdentifier`.** A
> tree's rule MUST call **`findByParent(filter)`**, not `find(filter)`. `find()` is `WHERE 1=1` — it can't filter
> children by parent, AND on expand the tree adds `parentId` to the filter, which `find` doesn't declare, so the
> call breaks. **Symptom: the tree fills fine at the root, but the moment you EXPAND a node the whole table
> re-renders with EMPTY values.** (A generator that builds ONE generic `find`-based fetch rule for every CRUD will
> ship this exact bug for its tree.) Either leave `findRuleIdentifier` blank (the plugin auto-creates the correct
> `findByParent` rule on render, footnote ²) or author the `findByParent` script above. `validate` now WARNs when a
> `crud.tree.plugin` fetch rule calls `.find(`/`.findAll(` but not `.findByParent(` (`_check_tree_config`).

> ⛔⛔ **TRAP #2 — build `findByParent` EXACTLY like the canonical recipe above.
> Two independent bugs bite a hand-derived version, both showing as an EMPTY tree / "no records found".** The
> canonical, verified shape:
>
> - **`findByParent` is a SQL method with a SINGLE `parentId` (String) param and NO pagination:**
>   `SELECT t.* FROM <table> t WHERE t.parent_id IS NOT DISTINCT FROM CAST(NULLIF(:parentId, '') AS uuid) ORDER BY <col>`
>   — a tree shows ALL children of a node, so there is **no `LIMIT`/`OFFSET`**. (Bug A: a paginated form with
>   `OFFSET (:pageNumber * :rowsInPage)` multiplies two untyped bind params → Postgres **`operator is not unique:
>   unknown * unknown`**.)
> - **The fetch RULE passes the raw parentId STRING directly — NOT a filter map:**
>   ```groovy
>   def parentId = attrs?.get('parentId')
>   def pid = (parentId != null && !parentId.isNull()) ? parentId.asText() : null
>   return service.crud.<alias>.findByParent(pid)
>   ```
>   (Bug B: passing a `[parentId: null, …]` **map** makes the executor's Map-arg unpacking turn the null parent into
>   an empty JSON object `{}`, then `:parentId::uuid` runs `UUID.fromString("{}")` → **`Invalid UUID string`**.)
> - **`CAST(NULLIF(:parentId, '') AS uuid)`** — the `NULLIF(:parentId,'')` anchors `:parentId` to a text literal so
>   the executor binds it as TEXT; a null/empty parentId → `NULL` → `IS NOT DISTINCT FROM NULL` → the **root** rows; a
>   real uuid string casts cleanly. **Never `... IS NOT DISTINCT FROM :parentId::uuid`** (raw cast → uuid bind →
>   crashes on the empty root value). (Platform equivalent: the type-aware query-DSL placeholder
>   `IS NOT DISTINCT FROM {name: 'parentId', type: 'uuid'}`, `CrudTreeMethodService.buildFindByParentSql`.)
>
> `validate` WARNs on a tree parent-method that uses a raw `:<param>::uuid` cast OR multiplies two bind params
> (`_check_tree_config`).

> ⚠️ **This is a data-tree FETCH rule — it deliberately returns RAW child rows (correct here).** Do NOT confuse
> it with a form **treepicker**/dropdown/autocomplete **CHOICES** rule: a choices rule MUST end by converting rows
> to option pairs — `return service.global.conversion.toSelectOptions(list,"<key>","<display>")`
> (`toSelectOptionsLocalized` for a localized CRUD; `toAutoCompleteOptions` for autocomplete) — never a raw
> `findByParent`/`findAll` entity list (which renders "No results found" **and** hides Show Nav). And never pass a
> PARTIAL filter map to `findAll`/`findByParent` — use `findAll([:])` (all keys absent) or the `acFindBy<X>Like`
> pipeline, or the unbound `:col` first appears as `$1 IS NULL` → Postgres "could not determine data type of
> parameter $1". Full recipe + naming table: [02-form-controls-reference.md §4a](02-form-controls-reference.md).

The provider (`CrudTreeDataProvider.fetchNodes`) puts into `filterMap`: `pageNumber=0`
`rowsInPage=Integer.MAX_VALUE`, `<filterKey>=parentId`, plus the `filterSettings` defaults; and passes them as
additional-params into `workflowExecutionService.execute(...)`. The result is accepted either as a **List**
(preferred — `findByParent` returns a list directly), or as a **Map with the key
`content`** (legacy page wrapper of `find`). Otherwise — an empty list + a warn log.

> For a **dynamic** CRUD, the target CRUD must have a `findByParent` method (a GROOVY wrapper over
> `findAllByParent`, constant `CrudTreeDataProvider.FIND_BY_PARENT_METHOD = "findByParent"`),
> or the rule must be rewritten to fit an existing method. See [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

### ⛔ Who sees which rows (tree)

The tree's children come from an EXECUTION rule exactly like a table's, so the scoping doctrine of
[04](04-crud-table-plugin.md#-who-sees-which-rows--decide-it-here-never-in-the-browser) applies unchanged —
decide it in the rule, never in the browser. One tree-specific consequence: hiding a **parent** hides its whole
subtree, so a row the user owns under a parent they do not own becomes unreachable — decide from the PRD whether
ownership applies to the branch or to the leaf.

## Tree actions vs table actions

Actions use **the same type** `CrudTableActionsDto.ActionDto` as the CRUD table (see
`CrudTableActionsDto.java`). Field annotations (shared for create/edit):

| Field | Type | Meaning | Backing |
|---|---|---|---|
| `id` | String | Unique action id (UUID). | `CrudTableActionsDto.java` (`private String id`) |
| `localizedNames` | Map<locale,String> | Name in the dropdown/button/audit. Key — full locale `"en_US"`. | (`private Map<String,String> localizedNames`) |
| `localizedButtonNames` | Map<locale,String> | Label of the form's submit button (non-direct). Default — falls back to `localizedNames` via `getLocalizedButtonName()`. | (`private Map<String,String> localizedButtonNames`) |
| `icon` | String | Icon CSS class (`pe-7s-plus`, `pe-7s-pen`, `pe-7s-trash`). | (`private String icon`) |
| `formGroupIdentifier` | String | Form group to navigate to (non-direct). The form receives `crud`+`crudId`. | (`private String formGroupIdentifier`) |
| `direct` | **boolean** | `true` → execute without a form (for tree edit: a direct action via rule + confirm dialog). In JSON — `true`/`false`. | (`private boolean direct`) |
| `predicateIdentifier` | String | Optional visibility predicate; the action is shown only if the predicate is `true` for this node (`CrudTreePlugin.evaluatePredicates`). | (`private String predicateIdentifier`) |
| `onBeforeStartRuleIdentifier` | String | Optional rule before showing the form / start. | (`private String onBeforeStartRuleIdentifier`) |
| `onBeforeCompleteRuleIdentifier` | String | Optional rule before the CRUD operation. | (`private String onBeforeCompleteRuleIdentifier`) |
| `submitForm` | Boolean | Non-direct: whether to submit the form on the action's button. `null` = `true` (`shouldSubmitForm()`). | (`private Boolean submitForm`) |
| `formInModal` | Boolean | Non-direct: `true` → the form opens in a DIALOG over the tree; submit refreshes the tree in place instead of navigating back. `null`=`false`. | (`private Boolean formInModal`, `shouldOpenInModal()`) |
| `modalWidth` | String | Width of that dialog — any CSS length (`"90%"`, `"400px"`). Blank → `80%`. Only read when `formInModal:true`. | (`private String modalWidth`) |

> The dialog behaves exactly as for the CRUD table — the form's breadcrumb buttons move to the bottom of the
> dialog and a successful submit closes it and refreshes the tree in place; see the `formInModal` note in
> [04-crud-table-plugin.md](04-crud-table-plugin.md).

> **A CRUD-TREE action opens its form the same way a table action does** — in CRUD mode, with every control on
> that form bound to this tree's CRUD, and with the action's rule reading the submitted values off the row
> (`context.<ctx>.<alias>.data.get()`) — never `context.data.getAttr("<field>")` for one of that form's OWN
> fields (the attrs stay valid for `service.actionId`/`__actionName` and for anything an `onBeforeStart` rule
> set). See
> [02-form-controls-reference.md](02-form-controls-reference.md) §Where the value LANDS.
>
> A **process.table** start or global action is the other case: like a workflow user task it opens its form
> WITHOUT a row, so `initCrudMode()` never runs and every control keeps its persisted scope: a `GLOBAL`/`CONTEXT`
> control lands in the attrs the rule reads with `context.data.getAttr`, while a `CRUD`-scoped control on a START
> form still writes into `crudDataMap[<alias>]` — which is how a start form seeds the case's entity
> ([07-workflows-and-tasks.md](07-workflows-and-tasks.md)) — see the ⛔ note under §"Process actions: `UserTaskActionsDto.ActionDto`" below.
> Wiring one form group to both kinds of action is normal (decide it from the worklist or straight from the row)
> — then the rule must read both, attrs first
> ([08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)).

Differences from the table:
- The tree's **create actions** are `createActions` (breadcrumb buttons), exactly like the table's; they navigate to
  a form group without `crudId` (create mode, `navigateToForm(..., entityId=null, ...)`,
  `CrudTreePlugin.java`).
- ⚠️ **A `direct:true` CREATE action on the tree still performs a BUILT-IN create** — unlike the CRUD table (where a
  direct action is rules-only), a tree runs the `onBefore*` rules and then calls the built-in
  `reactorCrudService.executeCrudMethod(realm, client, crudAlias, "create", [ {} ])` + logs a create
  (`CrudTreePlugin.java`, → nct-executor `/api/crud` → RSocket → the dynamic-integration BL pod). So a direct
  tree-create inserts a blank node (usually then renamed), it does not merely run a rule.
- The tree's **edit actions** (`editActions`) are rendered in the **last column of the tree** as a dropdown
  (`CrudTreeActionsPanel`), not as a separate set. Each node lazily requests its visible
  actions (`fetchActions`, the JS sends `entityIds` of visible nodes, the server returns `{rowActions:{<id>:[...]}}`
  accounting for predicates, `CrudTreePlugin.java`).
- "Create Child" is an ordinary **edit action** with `onBeforeStartRule` that navigates to the same
  create form, but in the context of the selected parent (see the `70e51d09-...` example above).

## Tree HTML (render)

The plugin (`CrudTreePlugin.html`):

```html
<div class="row crud-tree-plugin">
    <div class="card-body">
        <h5 wicket:id="crudName" class="card-title">CRUD Tree</h5>
        <div wicket:id="tree">[tree goes here]</div>
    </div>
</div>
```

The row actions dropdown (`CrudTreeActionsPanel.html`) — a placeholder `action-loading-item` with a spinner,
which the JS replaces with real actions after `fetchActions`:

```html
<div class="dropdown d-inline-block crud-tree-actions-cell">
    <button type="button" data-bs-toggle="dropdown" class="dropdown-toggle me-2 btn-icon btn-icon-only btn btn-sm btn-secondary">
        <i class="pe-7s-edit btn-icon-wrapper"></i>
    </button>
    <div tabindex="-1" role="menu" aria-hidden="true" class="dropdown-menu-xl dropdown-menu">
        <ul class="nav flex-column">
            <li class="nav-item-header nav-item">Actions</li>
            <li class="nav-item action-loading-item">
                <span class="nav-link text-center">
                    <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
                </span>
            </li>
        </ul>
    </div>
</div>
```

---

# Part 2. `process.table.pluin`

## Full example (a service-desk ticket monitor — node `name:"Process Table"`, `identifier-b99a-42de-9b06-332e852ff348`)

`properties.model.stringValue`, parsed (the rich variant with `indexSettings` + `filterExpression`):

```json
{
  "workflowIdentifier": "6c0b4335-a996-4b83-8374-68556dc6f53e",
  "processGroupIdentifier": "32d9be5f-8e28-458c-b2d8-2baf05fbd0f0",
  "columnSettings": [
    { "id": "3cab4d6e-bbbc-47db-8db1-7f0000cd4bb0", "name": "Customer Name", "dataClass": "java.lang.String",
      "scope": "CRUD", "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553", "crudAlias": "ticket", "fieldExpression": "customerName" },
    { "id": "1b903b87-85ba-4da3-963a-a2d1c9ac4ce4", "name": "Created Date", "dataClass": "java.time.LocalDateTime",
      "scope": "CONTEXT", "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553", "crudAlias": "ticket", "fieldExpression": "createdDate" },
    { "id": "68d65df8-b0da-4d01-af52-3c0782e07b6b", "name": "Assigned", "dataClass": "java.lang.String",
      "scope": "CRUD", "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553", "crudAlias": "ticket", "fieldExpression": "assignedTechnician" }
  ],
  "indexSettings": [
    { "id": "0844226f-46d8-48f1-a911-17070f974ce3", "indexName": "cusromerName", "scope": "CRUD",
      "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553", "fieldExpression": "customerName", "dataClass": "java.lang.String" },
    { "id": "ad9800cf-edb6-438b-b91d-3ba6b4055cc0", "indexName": "assigned", "scope": "CRUD",
      "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553", "fieldExpression": "assignedTechnician", "dataClass": "java.lang.String" },
    { "id": "9a856235-db32-4bbd-9212-18c63e08dc64", "indexName": "createdDate", "scope": "CONTEXT",
      "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553", "fieldExpression": "createdDate", "dataClass": "java.time.LocalDateTime" }
  ],
  "filterExpression": "like(cusromerName, %{customer_name}%) && assigned=={assigned} && createdDate > {created_date}",
  "userStartProcessActions": {
    "actions": [
      { "id": "930f4f5e-966c-4699-8bcc-e33d1f62d845",
        "localizedNames": { "en_US": "Intake", "hy_AM": "Մուտք" },
        "localizedButtonNames": { "en_US": "Intake", "hy_AM": "Մուտք" },
        "predicateIdentifier": "c25bc2d6-e431-4f28-9777-ddc1adc692d5",
        "direct": "off",
        "formGroupIdentifier": "a3bcfb80-6422-425f-ab86-38fb4e89ae38",
        "icon": "pe-7s-news-paper" }
    ],
    "errors": []
  },
  "globalActions": {
    "actions": [
      { "id": "9ef80d55-8423-4d1d-b0fa-101fa79214a8",
        "localizedNames": { "en_US": "Edit", "hy_AM": "Խմբագրել" },
        "localizedButtonNames": { "en_US": "Edit", "hy_AM": "Խմբագրել" },
        "predicateIdentifier": "4f75a151-292c-49ad-b0d2-f5159465431b",
        "onBeforeUserTaskCompleteRuleIdentifier": "694b564b-62c5-4ef6-ab48-9df14b2e7052",
        "direct": "off",
        "formGroupIdentifier": "a3bcfb80-6422-425f-ab86-38fb4e89ae38",
        "icon": "pe-7s-edit" }
    ],
    "errors": []
  }
}
```

A second, leaner variant of the same node shape drops the index machinery: `indexSettings: []` (empty) and
`filterExpression` **absent** (the key is not in the JSON, not `null`), while `globalActions.actions[0]`
additionally carries `onBeforeUserTaskStartRuleIdentifier`, `onBeforeUserTaskCompleteRuleIdentifier` and
`validationRuleIdentifiers` (and `userStartProcessActions` has only `predicateIdentifier`/`direct`/
`formGroupIdentifier`/`icon`/`id`/`name`). **The name form of the actions also varies with the node's age**:
older nodes use a **legacy single `"name"`**, newer ones `localizedNames`/
`localizedButtonNames`. Both forms parse (see below on the mixed
reality of names) — author the localized one.

## Field-by-field: `ProcessTablePluginModel`

Backing: `nct-ui/.../process/ProcessTablePluginModel.java`.

| Field | Type | Meaning | Req. | Default | Backing |
|---|---|---|---|---|---|
| `workflowIdentifier` | String | Identifier of the workflow (Flowable) whose instances we show and start. Resolved via `flowableWorkflowService.findByIdentifier` (`ProcessTablePlugin.java`). Without it, start-actions error out. | yes | — | `ProcessTablePluginModel.java` |
| `processGroupIdentifier` | String | Process group — the row filter (`ProcessFilter.processGroupIdentifier`). If empty/invalid — the plugin **auto-creates** a group named = `content.uniqueIdentifier` and saves the model (`ProcessTablePlugin.java`). | yes¹ | auto | |
| `columnSettings[]` | `ProcessTableFormControlSettings[]` | Table columns. They differ from CRUD columns by having a `scope` (see below). | no | `[]` | |
| `indexSettings[]` | `ProcessIndexSettings[]` | Indexable process context values — what `filterExpression` works over. Forwarded into start/actions as `ProcessIndexSettingsDto` (`ProcessTablePlugin.java`). | no | `[]` | |
| `filterExpression` | String | A filter expression string over the `indexName`s (grammar below). Placed into `ProcessFilter.expression` (`ProcessTablePlugin.java`). | no | — | |
| `userStartProcessActions` | `UserTaskActionsDto` | Process **start** actions — breadcrumb buttons (`ProcessTablePlugin.java`). | no | — | |
| `globalActions` | `UserTaskActionsDto` | Actions over an **existing** process (in addition to the workflow's task-actions). Shown in the row dropdown, only if their predicate is `true` (`ProcessTablePlugin.java`). | no | — | |

¹ Technically not required in the export: on render the plugin will create the group itself and rewrite the
model. But for a self-contained export, set `processGroupIdentifier` and add the corresponding object to
`rep-objects.json > processGroups[]` (see the recipe).

> **The Settings ID — how a Groovy rule names this table.** The node's own `uniqueIdentifier` is the table's
> **settings ID**, and it is the one string that lets everything above be inherited rather than restated. A
> rule passes it to `service.workflow.list / actions / startActions / complete`
> ([16](16-groovy-service-api.md) §2.13) and gets this table's workflow, process group, filter expression,
> index settings and — nowhere else obtainable — its **global actions**.
>
> The settings panel shows it under **Workflow binding → Settings ID**, with a copy button; the rule editor
> also offers the project's process tables by name inside the quotes, and picking one writes the whole call.
>
> Two consequences worth knowing. The model is mirrored into the settings store under this id whenever it is
> saved, so a rule sees what the panel last wrote. And a table's global actions are meaningless outside it: a
> rule that does not pass the settings ID cannot see them, which is correct rather than a limitation.

> ⛔ **Both node buckets empty is a defect, not a default.** `userStartProcessActions: {"actions":[]}` means
> nothing can be started from this page; `globalActions: {"actions":[]}` means a row offers nothing except
> what its current task happens to expose. Decide both deliberately — who may open a case here, and what a
> user can do to a case regardless of where it stands. See [27](27-event-driven-process-start.md) §2 for the
> decision, and note that a `direct:"on"` start action starts the process with **no context data at all**.
> `validate` WARNs when both are empty and ERRORs when nothing in the whole project starts the workflow.
>
> ⛔⛔ **A `userStartProcessActions` action opens a BLANK form — so its rule must be able to
> CREATE the subject, not just find it.** The start button on a process table is "open a new
> case", and with `direct: "off"` the platform first shows the action's form group with nothing
> in it. The rule then runs against a record that does not exist yet.
>
> The failure is silent and total. A start rule written for an existing document begins
>
> ```groovy
> def id = SUBJECT()                       // reads the form's `id`
> if (id == null) { throw new RuntimeException('The record could not be identified') }
> ```
>
> and on a blank form `id` is null on every press. Measured live: the user fills the whole form,
> presses the button, and **nothing happens at all** — no document, no case, no message. The
> same rule works perfectly from the register's row action, where the draft already exists, so
> the defect survives every test that drives the happy path.
>
> Decide which one the button is, and make the objects say so:
>
> * **"submit THIS document"** — it belongs on the register as a row action, gated on the
>   document's status. Do not also put it on the process table: the queue's start button then
>   promises something it cannot do.
> * **"open a case for a NEW document"** — the rule must persist the form first (create the
>   record, take its id) and only then claim and start. `submitForm` (null → true) makes the
>   platform persist the form group before the complete-rule runs, so the rule can read the
>   fresh row — but only if the form group is bound to a crud that the acting role may create.
>
> `validate` cannot see this: the action is well-formed, the rule compiles, the form group
> exists. Only pressing the button on an empty form does.

> **The THREE action origins on a process table** — the row action menu is assembled from three sources, but
> only **two** live in this node (`ProcessTablePlugin.fetchBulkActions`):
> 1. **`userStartProcessActions`** — "start a new process" breadcrumb buttons.
> 2. **`globalActions`** — row actions the plugin defines itself, available on **every** row regardless of the
>    process's current task.
> 3. **per-userTask actions** — **NOT in the node/settings**: they live in the workflow BPMN as
>    `flowable:userActions` ([07](07-workflows-and-tasks.md)) and are fetched at runtime
> (`flowableTaskService.getAvailableActionsBulk`, `ProcessTablePlugin.java`); each only shows while the
>    case is parked at that task. So don't look for task actions in the node — author always-available ones as
>    `globalActions`.
>
> **`direct` on a PROCESS action is a STRING `"on"`/`"off"`, not a boolean** (`UserTaskActionsDto.isDirect() =
> StringUtils.equals(direct,"on")`, `UserTaskActionsDto.java`; writing `true`/`false` silently
> disables it — contrast the **tree** action's boolean `direct` in the section above). A **DIRECT** global
> action runs a rule with no form; a **NON-DIRECT** one navigates to a form group:
> ```json
> // DIRECT (rule, no form): omit formGroupIdentifier, bind the work to a rule, choose completeUserTask
> { "id":"<uuid>", "localizedNames":{"en_US":"Escalate"}, "localizedButtonNames":{"en_US":"Escalate"},
>   "predicateIdentifier":"<REQUIRED>", "direct":"on",
>   "onBeforeUserTaskCompleteRuleIdentifier":"<execution rule>", "completeUserTask":"off", "icon":"pe-7s-up-arrow" }
> // NON-DIRECT (opens a form group)
> { "id":"<uuid>", "localizedNames":{"en_US":"Open worksheet"}, "localizedButtonNames":{"en_US":"Open worksheet"},
>   "predicateIdentifier":"<REQUIRED>", "direct":"off", "formGroupIdentifier":"<form-group uuid>", "icon":"pe-7s-look" }
> ```
> `completeUserTask` is `"on"`/`"off"` (`"off"` runs the rule without advancing the task). `validationRuleIdentifiers`
> is a valid export field even though the settings UI doesn't surface it.
>
> ⚠️ **Platform prerequisite — global actions need nct-workflow ≥ the 2026-08-28 fix.** Executing a
> globalAction takes the *no-taskId* branch of `FlowableProcessServiceImpl.executeAction`, which ended in
> `runtimeService.createExecutionQuery().processInstanceId(id).singleResult()`. That query matches EVERY
> execution of the instance — the root execution PLUS one child per active token — so any case parked at an
> activity (every live case) returned 2 and the click failed with Flowable's
> `Query return 2 results instead of max 1`, surfaced as *"Failed to execute action: Failed to execute
> action: …"*. The task branch never showed it (it goes through `updateProcessVariables`), so per-task
> buttons worked while every global action failed. Fixed by adding `.onlyProcessInstanceExecutions()`. If you
> meet that error on a tenant, the export is not at fault — the deployed `nct-workflow` is stale.
>
> ⛔ **Every `globalAction` MUST carry a non-blank `predicateIdentifier`** — a blank one is **skipped and never
> shown** (fail-closed, `ProcessTablePlugin.java`), the #1 reason a hand-authored global action "does
> nothing." Use a `return true` PREDICATE rule for always-visible. (Start actions differ: a blank predicate
> there means always-allowed.)

## Field-by-field: `ProcessTableFormControlSettings` (column) — DIFFERENT from a CRUD column

Backing: `nct-ui/.../process/ProcessTableFormControlSettings.java`. The key difference from
`CrudTableColumnSettings` (04) is the **`scope`** field: the column value is taken not from a flat row, but
from the process context data via one of three sources.

| Field | Type | Meaning | Backing |
|---|---|---|---|
| `id` | String | Unique column id. | `ProcessTableFormControlSettings.java` |
| `name` | String | ⚠️ Legacy header name (fallback). Marked `@Deprecated`. | |
| `localizedNames` | Map<locale,String> | Localized headers. Resolved via `getLocalizedName(Locale)`. | |
| `dataClass` | String | FQCN of the value type, e.g. `java.lang.String`, `java.time.LocalDateTime`. Mapped to `ValueType` for conversion (`ProcessTablePlugin.java`). | |
| `scope` | `FormControlScope` enum | **`GLOBAL` / `CONTEXT` / `CRUD`** — where to read the value from (see the source table below). | |
| `contextIdentifier` | String | Context identifier for `CONTEXT`/`CRUD` scope. | |
| `crudAlias` | String | CRUD alias for `CRUD` scope. | |
| `fieldExpression` | String | Path to the value (e.g. `customerName`, `createdDate`; for GLOBAL — special keys, see below). | |
| `enumDisplayField` | String | For enum columns: the enum property to display (semantics as for a CRUD column). | |
| `enumValues` | Map<String,Map<String,String>> | Snapshot of the enum's property table. | |
| `enumName` | String | Registry name of the project Enumeration. | |
| `trueIcon` | String | **Boolean columns only** (`dataClass == java.lang.Boolean`): Pe-7s CSS class rendered **instead of** raw `true` text; blank → raw text. Same helper as the CRUD table. | |
| `falseIcon` | String | Boolean columns only: Pe-7s CSS class for a `false` value; blank on this side → raw text. | |
| `money` | boolean | **Numeric columns only**: render the cell as money. Same semantics and same helper as the CRUD table. | |
| `currency` | String | Money columns: symbol (`$`, `€`, `֏`) or ISO code (`USD`); free text. | |
| `moneyFormat` | String | Money columns: `US` / `EUROPEAN` / `SPACE_COMMA` / `SPACE_DOT` / `SWISS` / `INDIAN` / `PLAIN`. Blank → `US`. | |
| `moneyDecimals` | Integer | Money columns: decimal places `0`–`6`; null → `2`. | |
| `dateFormat` | String | **Temporal columns only** (`java.time.LocalDate` / `LocalDateTime` / `Instant`): moment.js display pattern, e.g. `DD/MM/YYYY HH:mm`. Blank → the raw ISO value. | |

> **Boolean icons + alignment** apply here identically to the CRUD table via the shared `BooleanIconColumnUtils`,
> called at `ProcessTablePlugin.java`: a boolean column with `trueIcon`/`falseIcon` renders the Pe-7s icon
> (defaults `pe-7s-check`/`pe-7s-close`) instead of raw `true`/`false`, and numeric/boolean cells are
> right-aligned (CSS `text-end`, `isRightAligned`). Full semantics in [04-crud-table-plugin.md](04-crud-table-plugin.md)
> §`CrudTableColumnSettings`. Note the sibling `ProcessIndexSettings` (below) has **no** `trueIcon`/`falseIcon` —
> only columns do.

> ⛔ **A `GLOBAL` money or date column is authored `java.lang.String` by default, and that makes both
> formatters inert.** The attrs document is a string map, so the natural-looking column type is String —
> but `money` needs a numeric `dataClass` and `dateFormat` needs a temporal one, and neither reports the
> mismatch. Declare the COLUMN `java.math.BigDecimal` / `java.time.LocalDate`; the extractor converts the
> stored value, so the bind rule can keep writing the attr as a string. See
> [10-database-management.md](10-database-management.md) §*Money is `NUMERIC`*.
>
> **Money + date format** apply here identically too, through the same
> `ColumnCellFormatUtils` seam — full semantics in [04-crud-table-plugin.md](04-crud-table-plugin.md)
> §`CrudTableColumnSettings`. One thing is specific to the process table: the controls work in
> **every scope** — `GLOBAL`/`CONTEXT` columns pick their type in the "Field Expression" type
> dropdown, `CRUD` columns get it from the picked field. (In `CRUD` scope the value reaching the
> formatter is typed only for **dotted** expressions; a flat one goes through the localization
> lookup, which returns text. Both formatters read either, so it makes no difference to the output.)
> `ProcessIndexSettings` has none of these keys — only columns do.

How `scope` determines the value source (`ProcessTablePlugin.extractColumnValue`):

| `scope` | Where the value comes from | Special cases |
|---|---|---|
| `GLOBAL` | From process properties or global context attributes by `fieldExpression`. | Special keys: `businessKey`, `workflowName`, `status`, `identifier`, `id`; otherwise — `contextData.attrs[fieldExpression]`. |
| `CONTEXT` | `contextData.contextDataMap[contextIdentifier].attrs[fieldExpression]`. | — |
| `CRUD` | `contextDataMap[contextIdentifier].crudDataMap[crudAlias]` → field `fieldExpression`. | Renders whatever the process's stored document holds under that alias — **and nothing refreshes it**; see below. |

> ⚠️ **All three scopes DO resolve. A `CRUD`-scoped column is blank only when nothing seeded that alias.**
> `extractColumnValue` switches on the column's `scope` and reads the process's **stored context-data
> document** (bulk-prefetched by the data provider, one call per page): `GLOBAL` → the document's root
> `attrs`, except for five names intercepted before your attrs are ever consulted (`businessKey`,
> `workflowName`, `status`, `identifier`, `id` — those come off the process row itself); `CONTEXT` →
> `contextDataMap[ctx].attrs`; `CRUD` → `contextDataMap[ctx].crudDataMap[alias]` → `value`. Whoever filled
> that document decides what renders:
> * a **start FORM with CRUD-scoped controls** (shape A) — `collectContextDataFromForm` writes those values
>   into `crudDataMap` even with no row bound, so the CRUD columns render. ⚠️ It writes only the controls the
>   user actually FILLED (a null value returns early), so a column over a control the user left empty is blank
>   even though the offline check counts that control as seeding the alias
>   ([07-workflows-and-tasks.md](07-workflows-and-tasks.md) → *What a process can see*);
> * a **start RULE** whose document seeds `crudDataMap` (shape C, `service.workflow.start` —
>   [27-event-driven-process-start.md](27-event-driven-process-start.md) §4/§6) — same, immediately;
> * a **picker start form** (shape B) or any start that seeds nothing under that alias — blank in every row,
>   forever. That one looks like missing data rather than a wiring mistake, so it survives review.
>
> ⛔ **BOTH are snapshots of the same stored document. Choose by WHERE THE VALUE LIVES, not by scope name.**
> The plugin reads the PROCESS's context data, never the table, and nothing in the workflow runtime writes a
> record back into the document by itself. So a `CRUD` column shows what the start (or the last CRUD-mode task
> form) put there, and a `GLOBAL` column shows what somebody last `setAttr`'d — neither refreshes on its own.
>
> | The value is… | Use | Because |
> |---|---|---|
> | a **field of a document the case carries** (`requestNo`, `title`, `amount`, `category.name`) | `CRUD` over that alias, with the same `fieldExpression`s the entity's own crud table uses | it is the ONLY branch that localizes (`localizedValueUtil.getLocalizedValue`) and projects enums, the only one that honours `dataClass` per field, and `crudDataMap` is rewritten by every CRUD-mode task form — so it needs no maintenance |
> | **derived or computed for the worklist** (a stage label, an SLA countdown, a name assembled from three records) | `GLOBAL` over an attr — **plus a bind rule that RE-PUBLISHES it** | there is no record to read it from; one bind rule can feed the worklist, the case card and the index at once |
>
> ⛔ **`GLOBAL` is only correct WITH the bind rule, and the bind rule must run on more than one step.** A bind
> rule wired to the first service task alone publishes once and never again: that is a snapshot with extra
> steps, and it is worse than the CRUD column it replaced — unlocalized, untyped, and a hand-maintained
> duplicate of fields that already exist. This is a real 2026-08 failure: five worklist columns copied out of
> the request at case start, frozen from then on, while every other screen showed the live record.
>
> A `CRUD` column renders only keys the `crudDataMap` literal actually seeded, so adding a column means adding
> the key to **every** rule that starts a case — the normal start AND any repair sweep.
>
> `mrjun.py validate` enforces this: **ERROR** when a `GLOBAL` column's attr is written nowhere; **WARN** when
> it is published at one BPMN task or fewer (it counts the distinct tasks whose `flowable:rule` rules
> `setAttr` it); **WARN** when a `CRUD` column's field is in no `crudDataMap` literal for that alias.
>
> **`indexSettings` resolve the same three scopes**, one step removed: `paramsToFilter` is extracted from the
> document by `IndexValueExtractor` (nct-workflow) **when the process starts and again after each action
> execution** — so a CRUD-scoped index is filled exactly when the document carried that alias at that moment,
> and a rule-started case passes no index settings at all and stays unfilterable by `filterExpression` until
> its first user-task submission backfills it.
>
> `mrjun.py validate` WARNs on a `scope:"CRUD"` process **column** whose alias is seeded by NEITHER a start
> action's form group (a `scope:"CRUD"` control) NOR any rule that passes it inside a `crudDataMap` literal to
> `service.workflow.start` — so it forgives shape A and shape C alike, and flags the rest. No put-back is
> required for a column; that extra condition applies only to the separate warning about CRUD-scoped READ-ONLY
> fields on a process FORM, which really do need a serviceTask to write the value back.
> An **index** is judged more strictly: only a start form's seeding clears it, because a rule-started case
> passes no index settings at all, so a rule-seeded alias buys a column but leaves the index empty.

`FormControlScope` — the same enum as for form controls (see [02](02-form-controls-reference.md)),
with exactly three values: **`GLOBAL`** (displayName "Global"), **`CONTEXT`** ("Context"), **`CRUD`** ("CRUD");
package `com.devsegment.nctui.plugin.dynaform.form.controls.config.FormControlScope`. In JSON it serializes
**by the constant name** — `"GLOBAL"`/`"CONTEXT"`/`"CRUD"`, NOT the displayName.

Required fields by scope (matches form controls):

| `scope` | Required column/index fields |
|---|---|
| `GLOBAL` | `fieldExpression` (+ `indexName`/`dataClass` for an index) |
| `CONTEXT` | `contextIdentifier`, `fieldExpression` |
| `CRUD` | `contextIdentifier`, `crudAlias`, `fieldExpression` |

> ⛔ **A `scope:"CRUD"` entry with NO `crudAlias` carries nothing at all.** `extractColumnValue` takes the CRUD
> branch only when `contextIdentifier`, `crudAlias` and `fieldExpression` are all non-blank, so such an entry is
> blank in every row whatever the case holds. Real exports ship them — the JSON above is one, and the reference
> bundles each carry two — so `validate` now names them separately from the seeded/unseeded case. Set the alias,
> or move the entry to `GLOBAL` over an attribute a serviceTask publishes.
>
> ⚠️ **`crudAlias` is ignored for a `CONTEXT`/`GLOBAL` column, but is present in real exports.**
> In the example above the `Created Date` column has `scope:"CONTEXT"`, yet still carries
> `crudAlias:"ticket"` (the settings UI writes the alias into all columns, while `extractColumnValue` reads it only
> when `scope==CRUD`). When generating manually, you can omit `crudAlias` for non-CRUD scope — the node will
> render identically; when diffing against a real export, this is an expected discrepancy, not a bug.

> **Mixed reality of names.** In process columns and actions you will meet **both** forms of the
> header: a legacy single `"name"` and a localized `localizedNames` (`{"en_US":...,"hy_AM":...}`).
> Columns most often still carry the legacy `"name"`; actions come both ways depending on when the node was
> authored. The resolver `getLocalizedName(Locale)`
> (`ProcessTableFormControlSettings.java`) tries `localizedNames` first, then falls back to `name`.
> Both forms are valid in the export; prefer `localizedNames`.

## Field-by-field: `ProcessIndexSettings` (index)

Backing: `nct-ui/.../process/ProcessIndexSettings.java`. Indexes are **named values extracted
from the process context** over which `filterExpression` later filters. On process start
and action execution, the index list is forwarded to the backend as `ProcessIndexSettingsDto`
(`ProcessTablePlugin.getIndexSettingsDtoList`).

| Field | Type | Meaning | Backing |
|---|---|---|---|
| `id` | String | Unique index id. | `ProcessIndexSettings.java` |
| `indexName` | String | Index name — used **on the left-hand side of `filterExpression`** (e.g. `customerName`). | |
| `scope` | `FormControlScope` | `GLOBAL` / `CONTEXT` / `CRUD` — where to extract the value from. | |
| `contextIdentifier` | String | Context for `CONTEXT`/`CRUD` scope. | |
| `crudAlias` | String | CRUD alias for `CRUD` scope. | |
| `fieldExpression` | String | Path to the value in the context. | |
| `dataClass` | String | FQCN of the value type. | |
| `enumDisplayField` / `enumValues` / `enumName` | — | Enum support (as for a column). | |

> ⚠️ `indexName` in the example above is `"cusromerName"` — a typo made by whoever authored that node. In the export
> write exactly what stands on the left-hand side of `filterExpression` — placeholders are matched by
> name, not by correct spelling.

## `filterExpression` grammar

`filterExpression` is a **separate DSL, unique to `process.table.pluin`**. `crud.table.plugin`/
`crud.tree.plugin` do NOT have it — they filter via `filterSettings` (a mapping to the CRUD filter class) and
via a fetch-rule. The DSL works over `indexSettings` (process context values, extracted into the
JSONB column `paramsToFilter`). To the left of the operator is an **`indexName`** (must exactly match
`indexSettings[].indexName`), to the right a placeholder `{name}` (a value from the filter form at runtime).

**Comparison operators:** `==`, `!=`, `>`, `>=`, `<`, `<=`.
**Logic (precedence from high to low):** `!` (NOT) > `&&` (AND) > `||` (OR); grouping — `()`.
**Functions:**

| Function / form | Meaning | Example |
|---|---|---|
| Basic comparison | comparing an index with a placeholder/literal | `customerName == {filter_customerName}` |
| `&&` / `\|\|` / `!` | logical composition | `status == {filter_status} && orderTotal >= {filter_minAmount}` |
| `ignoreNull(expr)` | if any `{ref}` inside resolves to null → the whole sub-expression becomes TRUE (the condition "drops out") — the idiom for optional filters | `ignoreNull(customerName == {filter_customerName})` |
| `like(index, pattern)` | SQL-like LIKE with `%`, case-insensitive: `%v%`=contains, `v%`=startsWith, `%v`=endsWith, bare `v` (no `%`)=**contains** as well — there is no "exact" form of `like`, use `==` for that | `like(customerName, %{c}%)` · `like(code, {c}%)` · `like(email, %{d})` |
| `contains(index, value)` | element is in the array/list | `contains(tags, {filter_tag})` |
| `anyMatch(index, "path", op, value)` | search within an array of objects: `path` — dot notation, `op` — one of the comparison operators | `anyMatch(lineItems, "name", ==, {filter_itemName})` |
| Date/number comparison | `>`, `<`, `>=`, `<=` over `LocalDateTime`/numbers | `createdDate > {filter_fromDate}` |

Literals: `"string"`, integer, decimal, `true`/`false`, `null`. `{name}` can be a dot-path
(`{customer.address.city}`). ValueType of values: `STRING`, `INTEGER`, `LONG`, `DOUBLE`, `FLOAT`, `BOOLEAN`.

`{name}` values are resolved from `ProcessFilter.filterValues` (a Map coming from the filter form of the
`onFilterSubmit` event, `ProcessTablePlugin.java`). In the full example above:
`like(cusromerName, %{customer_name}%) && assigned=={assigned} && createdDate > {created_date}` —
three placeholders over three indexes.

> ⛔ **A `filterExpression` does NOTHING without a filter form on the same page.** `ProcessFilterSpecification.fromExpression`
> returns `Specification.allOf()` (no filtering) whenever `filterValues` is null **or empty**; combined
> with `ignoreNull()` this is a **silent no-op** — no error, the table just shows every row. Always pair a
> non-empty `filterExpression` with a `dynaform.filter.form.plugin` on the page (see [04](04-crud-table-plugin.md#standalone-filter-form-filter-panel-above-the-table)).
>
> ⛔ **The `{token}` is looked up VERBATIM in `filterValues` — the `filter_` prefix is NOT stripped**
> (`FilterExpressionLexer.readFilterRef` keeps the whole brace content; `ProcessFilterSpecification.java`
> does `filterValues.get(path)`). So the filter control feeding `{filter_branch}` must have
> **`filterKey:"filter_branch"`** — character-for-character, prefix included. This is the OPPOSITE convention
> from crud tables, where `filterKey` is the raw filter-class field name (`branch`). A common trap: copying a
> crud table's `branch`/`status` filter form onto a process page filters nothing because `branch` ≠ `{filter_branch}`.

> ℹ️ **The grammar above IS the parser's own grammar.** `FilterExpressionParser` is a recursive-descent parser
> (its productions are exactly the ones listed here), `FilterExpressionLexer` tokenises exactly
> `ignoreNull`/`contains`/`anyMatch`/`like`/`true`/`false`/`null` plus the six comparison operators, and
> `ProcessFilterSpecification.fromExpression` compiles the AST into a JPA `Specification` over the JSONB
> `paramsToFilter`. Concretely: `!` binds tighter than `&&`, which binds tighter than `||`, and `()` groups;
> inside `like(...)` a `%` is recognised only immediately before/after the value ref and matching is
> case-insensitive. One behaviour worth knowing: a comparison/`like`/`contains`/`anyMatch` whose `{ref}` resolves
> to null is **already** dropped (the condition evaluates TRUE), so `ignoreNull(...)` largely restates that —
> **write `ignoreNull` anyway**: it is the only form that stays unambiguous under `!` (a bare null-dropped
> condition flips to FALSE once negated), and it states the intent. And note that a filter control which submits
> `""` rather than `null` defeats the null check entirely — the empty string is a value.
>
> ⛔ **You cannot test a `filterExpression` offline.** A freshly imported project has no process instances, so
> nothing — import, `validate`, `coverage` — ever evaluates the expression; a wrong `indexName` or a mismatched
> `{token}` is invisible until a real instance exists. Keep the expression to one or two
> `ignoreNull(index=={filter_x})` clauses and verify it live after the first process has been started.

> ℹ️ **The `like(cusromerName, %{customer_name}%) && assigned=={assigned} && createdDate > {created_date}`
> filterExpression in the "Full example" above is BASELINE PLACEHOLDER junk** (note the `cusromerName` typo and
> the `assigned`/`created_date` fields that match nothing in a real project) — a starting-point baseline ships
> exactly this on its demo `process.table.pluin`, and it survives every copy of that node. Do NOT copy it. A real
> one references your own `indexName`s via `ignoreNull`, e.g. `ignoreNull(status=={filter_status})`.

## ⭐ Working process-monitor recipe (verified live)

A process-monitor page (a `process.table.pluin` a user actually works from) needs THREE things wired together.
The shape is the same whatever the domain — a "<Entity> Cases" queue, a claims desk, a customs-declaration
intake monitor:

1. **The `process.table.pluin` model** (`properties.model.stringValue`) — and the **synced mirror** (above):
   ```jsonc
   {
     "workflowIdentifier": "<wf>", "processGroupIdentifier": "<pg>",
     "columnSettings": [ /* scope:"CRUD" cols over the workflow's entity, or scope:"GLOBAL" businessKey/status */ ],
     "indexSettings": [ { "id":"…", "indexName":"status", "scope":"CRUD", "contextIdentifier":"<ctx>",
                          "crudAlias":"incomingDocument", "fieldExpression":"status", "dataClass":"java.lang.String" } ],
     "filterExpression": "ignoreNull(status=={filter_status})",   // {filter_status} = the filter-form field's filterKey
     "userStartProcessActions": { "actions": [ {
        "id":"…",
        "localizedNames": {"en_US":"New Incoming Document","ru_RU":"…","hy_AM":"…"},   // ⛔ NOT a flat "name"
        "localizedButtonNames": {"en_US":"Register","ru_RU":"…","hy_AM":"…"},
        "predicateIdentifier":"<start pred|null>", "direct":"off",   // direct:"off" + a formGroupIdentifier → OPENS the start form
        "formGroupIdentifier":"<the intake form group>", "icon":"pe-7s-news-paper" } ], "errors": [] },
     "globalActions": { "actions": [], "errors": [] }   // optional; each needs localizedNames + a non-blank predicate
   }
   ```
   > ⛔ **`userStartProcessActions`/`globalActions` MUST use `localizedNames` (a Map), NOT a flat `name`.** The
   > UserTask `ActionDto` `@JsonIgnoreProperties` a legacy `name` (`UserTaskActionsDto`), so a `{"name":"Intake",…}`
   > start button renders with a **BLANK label**. And `direct:"off"` + `formGroupIdentifier` is what makes the
   > button OPEN the start form (the intake form group) — `direct:"on"` runs with no form (see [06](06-form-groups-and-mapping.md) ActionDto).

2. **A `dynaform.filter.form.plugin`** as a **sibling BEFORE** the process-table, inside the same content parsis
   (`… → html "Layout" → nct.parsis.plugin "parsis" → [ dynaform.filter.form.plugin, process.table.pluin ]`):
   - `properties.filterFormModel` = `{"name":"…Filter","description":"","waitSelector":".process-table-plugin"}` —
     `waitSelector` is the CSS class of the process-table it drives (the platform tags the table `.process-table-plugin`).
   - inside: `nct.parsis.plugin "filter.parsis" → html layout → per-filter { nct.label + a field }`, plus a
     `dynaform.filter.submit.button.plugin` (settings `{"buttonName":"Filter"}`).
   - each filter field's settings carry **`filterKey:"filter_status"`** = the `{filter_status}` in the
     filterExpression (character-for-character, the `filter_` prefix included). A dropdown filter is a
     `dynaform.form.rimm.drop.down.field.plugin` with `enumName` + an `enumValues` snapshot for its options.

3. **Placement**: put the monitor on a REAL, reachable page — **its own business page AND a quick link to that
   page** in the shared `Nct left nav` node (`quicklink add --page "<Entity> Cases" --group "<business group>"
   --label-loc <locale>=<text>`, [17](17-left-nav-quick-links.md); per-page kicker nodes are dead data).
   ⛔ NOT `--group "Pages"` — that group is the authoring console, not the user's menu (doc 17). A Home page that
   `Redirect`s elsewhere never renders its process-table. Don't leave it on a baseline's `Home`/`Branches` demo
   nodes. Every workflow owes the user exactly one such page —
   [07](07-workflows-and-tasks.md) §"Step 5 — the worklist page (NOT optional)".

   > ⛔ **A process table parked in a secondary TAB behind a crud table is NOT a worklist page — neither the user
   > nor the unlinked-page check finds it.** `TabPlugin` opens the FIRST tab by `order` and materialises **only**
   > the active pane (`getActiveTab()` = the first item after `getItems().sort(comparingInt(getOrder))`, cached in
   > a session attribute; every inactive pane gets a `BlockPanel` instead of its parsis — `TabPlugin.java`), and
   > the switch is an `AjaxLink`, so **no URL — hence no quick link — can address tab 2**: `linkModel.identifier`
   > addresses a `siteMapPage` and nothing finer ([17](17-left-nav-quick-links.md)). The reachability check misses
   > it for the same reason: it warns per **`siteMapPage`** not reached by a quick link or a redirect
   > (`_check_homepage_and_nav`, `validate_cmds.py`), and the HOST page is already linked — so the buried worklist
   > passes as "reachable" while the user never opens it. Tabs are for co-locating tables someone already on that
   > page wants side by side; a worklist is a **destination** — own page, own link.

`ignoreNull(status=={filter_status})` means the table shows **all** processes until the user picks a status and
submits — so the page works even before anyone touches the filter.

> ⛔ **A process table CANNOT be scoped per user.** `process.table.pluin` has no fetch rule: its row set is
> fixed by `workflowIdentifier` + `processGroupIdentifier` + `filterExpression` evaluated over the values the
> FILTER FORM submitted — every input is either static config or client-supplied, and the result is cached per
> (realm, client, filter), so the same filter yields the same rows for every user. If the PRD says "each
> <actor> sees only their own <cases>", the queue must be a `crud.table.plugin` over the workflow's entity with
> a scoped fetch rule ([04](04-crud-table-plugin.md#-who-sees-which-rows--decide-it-here-never-in-the-browser),
> [19](19-build-decision-procedure.md) Phase 6) or a hand-built table in an HTML component
> ([24c](24c-html-data-tables-and-paging.md)); keep the process table for group-wide monitoring and gate only
> its ACTIONS by predicate.

> **Do not confuse with Query Builder.** `QueryBuilderDto`
> (`nct-ui/.../component/querybuilder/QueryBuilderDto.java`) is a separate visual component for
> nested conditions (`condition`/`rules`/`not`/`flags`/`data`, its own operator vocabulary
> `equal/not_equal/begins_with/contains/between/in/...`). It is **NOT** one of the three table plugins and is not
> used by either `filterExpression` or `filterSettings`. Don't mix it up with the process DSL.

## Process actions: `UserTaskActionsDto.ActionDto` — DIFFERENT from a CRUD action

Backing: `UserTaskActionsDto.java`
(nested `class ActionDto`). This is a **different** type than `CrudTableActionsDto.ActionDto`
the key differences:

| Field | Type | Meaning | Difference from CRUD action |
|---|---|---|---|
| `id` | String | Unique id. | — |
| `localizedNames` / `localizedButtonNames` | Map<locale,String> | Name/button label. | same |
| `predicateIdentifier` | String | Visibility predicate. For `globalActions` it is **required**: an action without a predicate is NEVER shown (fail-closed, `ProcessTablePlugin.java`). | for CRUD the predicate is optional |
| `onBeforeUserTaskStartRuleIdentifier` | String | Rule before starting a user-task. | for CRUD — `onBeforeStartRuleIdentifier` |
| `onBeforeUserTaskCompleteRuleIdentifier` | String | Rule before completing a user-task. | for CRUD — `onBeforeCompleteRuleIdentifier` |
| `validationRuleIdentifiers` | String | Identifier(s) of the validation rule. | not in CRUD |
| `direct` | **String** `"on"`/`"off"` | Direct execution. **Read via `isDirect()` = `StringUtils.equals(direct,"on")`** (`UserTaskActionsDto.java`; field `private String direct`). | for CRUD `direct` is a `boolean` |
| `formGroupIdentifier` | String | Form group to navigate to (non-direct). | same |
| `taskId` | String | Id of the workflow task (for task-actions). Field. | not in CRUD |
| `completeUserTask` | String `"on"`/`"off"` | Whether to complete the user-task. `shouldCompleteUserTask()` = `!StringUtils.equals(completeUserTask,"off")` — i.e. completes anything NOT equal to `"off"` (default = complete). Field. | not in CRUD |
| `icon` | String | Icon. | same |
| `submitForm` | Boolean | Whether to submit the form. `null`=`true`. | same |
| `formInModal` | Boolean | Non-direct: `true` → the form opens in a DIALOG over the process table; submit refreshes the table in place. `null`=`false`. **Boolean here, unlike `direct`.** | same field name/semantics as CRUD |
| `modalWidth` | String | Width of that dialog — any CSS length (`"90%"`, `"400px"`). Blank → `80%`. | same |

> `formInModal` works on BOTH process-table sets — the per-row/global actions above and the
> `userStartProcessActions` below (a start form in a dialog: it starts the process on submit and the new row
> appears in the refreshed table). Dialog behaviour is the same as for the CRUD table, see the `formInModal`
> note in [04-crud-table-plugin.md](04-crud-table-plugin.md).

> ⚠️ The main export pitfall: for process actions `direct` is a **string** `"on"`/`"off"`,
> not a boolean. In the examples: `"direct": "off"`. If you write `true`/`false`, `isDirect()` returns
> `false` (not equal to `"on"`). For tree/table CRUD actions it's the opposite — `direct` is `true`/`false`.

Two sets:
- **`userStartProcessActions`** — start a new process (`processService.startProcess(...)` with
  `groupIdentifier` + `indexSettings`, `ProcessTablePlugin.java`) for `direct`, or navigate
  to a form group for non-direct. Rendered as breadcrumb buttons.
- **`globalActions`** — actions over a process row, merged with the workflow's own task-actions
  (`fetchBulkActions`). Visibility strictly by predicate.

> ⛔ **A global action cannot open a form that shows an existing record.** Its form is launched with the
> `processIdentifier` but with **no row**: the launcher passes the PROCESS table's `settingsName`, so
> `FormPlugin.resolveSettingsNavigation` finds the action in `globalActions` (not in a crud-table settings
> object), `crudTableNavData` stays null and `initCrudMode()` never runs. Point one at a CRUD form group and
> the user gets a page of empty, greyed-out fields. Give it a GLOBAL-scope card fed by process attributes,
> or don't add it.
>
> ⛔ **And check it is not a duplicate of a task action.** `globalActions` are MERGED into the same row menu
> as the workflow's own user-task actions (`fetchBulkActions`), so a global action named like the current
> task's action shows the user two identical buttons that do different things. Name each for what it does,
> and prefer putting the affordance on the task — the task action at least knows which step the case is on.

`UserTaskActionsDto` also carries `errors: []` next to `actions` — in the export keep
`"errors": []`.

## Process HTML (render)

`ProcessTablePlugin.html` — a table with an Actions column (a dropdown, lazily filled via
`fetchBulkActions`) and headers from `columnHeaders`:

```html
<div class="row process-table-plugin">
    <div class="card-body">
        <h5 wicket:id="workflowName" class="card-title">Table with hover</h5>
        <div wicket:id="paging"></div>
        <table class="mb-0 table table-hover">
            <thead><tr>
                <th>Actions</th>
                <th wicket:id="columnHeaders"><span wicket:id="columnName">Column Name</span></th>
            </tr></thead>
            <tbody>
            <tr wicket:id="processes">
                <td style="width: 125px;" class="process-actions-cell">
                    <div class="dropdown d-inline-block">
                        <button type="button" data-bs-toggle="dropdown" class="dropdown-toggle me-2 btn-icon btn-icon-only btn btn-sm btn-secondary">
                            <i class="pe-7s-edit btn-icon-wrapper"></i>
                        </button>
                        <div tabindex="-1" role="menu" aria-hidden="true" class="dropdown-menu-xl dropdown-menu">
                            <ul class="nav flex-column">
                                <li class="nav-item-header nav-item">Actions</li>
                                <li class="nav-item action-loading-item">
                                    <span class="nav-link text-center"><div class="spinner-border spinner-border-sm text-secondary" role="status"></div></span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </td>
                <td wicket:id="columns"><span wicket:id="value">Value</span></td>
            </tr>
            </tbody>
        </table>
    </div>
</div>
```

## Process group: binding and auto-creation

`processGroupIdentifier` points to an object in `rep-objects.json > processGroups[]`. Important: when
the plugin renders without a valid group, it **creates one itself**:
`processGroupService.save(... name(getContent().getUniqueIdentifier()) ...)`
(`ProcessTablePlugin.java`) — that is, **the group name = the plugin node's `uniqueIdentifier`**.

So for a process node whose `uniqueIdentifier = 9621d3e1-ce0e-4720-b42d-d6b6f4227453`, `processGroups[]` ends up
holding an object with `name = "9621d3e1-ce0e-4720-b42d-d6b6f4227453"`. The shape
of the process-group object in rep-objects:

```json
{
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "2b09545d-d17e-4776-9f40-fbd1224e1797",
  "name": "9621d3e1-ce0e-4720-b42d-d6b6f4227453",
  "description": "9621d3e1-ce0e-4720-b42d-d6b6f4227453",
  "creationTime": "2026-07-06T21:52:55.376584Z",
  "modificationTime": "2026-07-06T21:52:55.376596Z"
}
```

`ProcessGroupSelectionPanel` — a modal for manually selecting/creating a group (`ProcessGroupSelectionPanel.java`)
— in the current code is **commented out** in `showProcessGroupSelectionDialog` (`ProcessTablePlugin.java`):
in effect, when there is no group, auto-creation always happens and the dialog is not shown.

---

## How to construct from scratch

### Recipe A. `crud.tree.plugin` for a self-referential CRUD `category` (parent.id / parentId)

1. **Make sure the CRUD has a `findByParent` method.** For dynamic — add a GROOVY method
   `findByParent` to `dynamic-cruds.json` (a wrapper over `findAllByParent`), see
   [11](11-business-logic-dynamic-crud.md). For static — a method in the `@Crud` bean.

2. **Create the fetch-rule** in `rep-objects.json > rules[]` (or rely on auto-creation — then
   skip the step and don't set `findRuleIdentifier`):

   ```json
   {
     "identifier": "da08c1ea-17a9-4a69-abce-fcfe7d8e825a",
     "name": "Find children — Category",
     "ruleType": "EXECUTION_RULE",
     "executor": "GroovyExecutionRule",
     "status": "ACTIVE",
     "rule": { "ruleScriptStr": "def parent = attrs?.get('parentId')\ndef filter = ['rowsInPage': attrs?.get('rowsInPage')?.asInt(), 'pageNumber': attrs?.get('pageNumber')?.asInt(), 'parentId': (parent == null || parent.isNull()) ? null : parent.asText()]\nattrs?.each { k, v -> if (k != 'rowsInPage' && k != 'pageNumber' && k != 'parentId' && v != null && !v.isNull()) { filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText()) } }\nreturn service.crud.category.findByParent(filter)" }
   }
   ```
   The rule is **context-free** (no `contextIdentifiers`), see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).

3. **Add the node** `crud.tree.plugin` to the content tree (`branches.json`) **INSIDE THE PAGE's Layout
   content parsis** (NOT as a direct child of the siteMapPage), `pluginName: "crud.tree.plugin"`, and put the
   JSON into `properties.model.stringValue`:

   > ⛔ **Placement is load-bearing — a `crud.tree.plugin` is NOT a page by itself.** The node must be the child
   > of the page's content `nct.parsis.plugin`, exactly as every real export nests it:
   > `siteMapPage → parsis.plugin(name="parsis") → html.plugin(name="Layout") → nct.parsis.plugin(name="parsis") → crud.tree.plugin`.
   > That same `html.plugin(name="Layout")` also holds the page chrome (`site.header`, `nct.image` logo,
   > `site.breadcrumb`, `site.kicker` left-nav, `site.footer`, `site.right.kicker`) as siblings of the content
   > parsis. Attaching the tree **directly under `siteMapPage`**, or directly under `parsis.plugin` (skipping the
   > `html.plugin("Layout")` wrapper), **imports clean (validate 0-err, crud-verify OK) but renders an EMPTY page**
   > with no chrome and no tree — the #1 failure mode here. Full page skeleton:
   > [01-content-model-and-pages.md](01-content-model-and-pages.md) (`html.plugin "Layout" → nct.parsis.plugin
   > id="parsis"` ← THE PAGE CONTENT GOES HERE). Every working taxonomy tree nests this way. **Live-render the page
   > after import and confirm the rows draw** before calling it done.

   ```json
   {
     "contextIdentifier": "<optional context>",
     "crudAlias": "category",
     "parentFieldExpression": "parent.id",
     "parentFilterFieldExpression": "parentId",
     "columnSettings": [
       { "id": "<uuid>", "localizedNames": {"en_US":"Code"}, "fieldExpression": "code", "dataClass": "java.lang.String" },
       { "id": "<uuid>", "localizedNames": {"en_US":"Name"}, "fieldExpression": "name", "dataClass": "java.lang.String" }
     ],
     "filterSettings": [
       { "id": "<uuid>", "name": "Active", "filterField": "active", "dataClass": "java.lang.Boolean", "defaultValue": "true" }
     ],
     "createActions": { "actions": [
       { "id": "<uuid>", "localizedNames": {"en_US":"Create Category"}, "localizedButtonNames": {"en_US":"Create Category"},
         "icon": "pe-7s-plus", "formGroupIdentifier": "<form-group id>", "direct": false }
     ] },
     "editActions": { "actions": [
       { "id": "<uuid>", "localizedNames": {"en_US":"Edit Category"}, "localizedButtonNames": {"en_US":"Edit Category"},
         "icon": "pe-7s-pen", "formGroupIdentifier": "<form-group id>", "direct": false },
       { "id": "<uuid>", "localizedNames": {"en_US":"Delete Category"}, "localizedButtonNames": {"en_US":"Delete Category"},
         "icon": "pe-7s-trash", "direct": true, "onBeforeCompleteRuleIdentifier": "<delete rule id>" }
     ] },
     "rowsPerPage": 2147483647,
     "findRuleIdentifier": "da08c1ea-17a9-4a69-abce-fcfe7d8e825a"
   }
   ```
   The whole string must be **escaped** and placed in `properties.model.stringValue` (a JSON string inside
   JSON). `columnSettings`/`filterSettings`/`ActionDto` are types shared with the CRUD table (04).

   > ⚠️ **Column headers are `localizedNames`, not the deprecated flat `name`** — write one key per entry in
   > `tenant.json.locales` (the block above shows only `en_US` for brevity, as do its actions). A column authored
   > with the flat `name` renders that ONE string under every locale, and nothing catches it: `locale fill` only
   > completes maps that already exist, and `validate` only warns about a map that is *partially* filled.
   > `filterSettings` is the exception — that type has only a flat `name` (no localized map), so the entry above
   > is correct as written.

4. The first column (`Code` in the example) becomes the tree column with the expand icon.

5. **DONE-WHEN — append the settings mirror.** After the node exists you MUST also append to
   `rep-objects.json.settings[]` one object `{ "type":"CrudTree", "name":"<node.uniqueIdentifier>",
   "content": <the SAME model, as a parsed JSON object> }` (plus the full
   `AbstractSecuredDto` housekeeping set: `identifier`, `realmName`, `clientName`, `creationTime`,
   `modificationTime`, `deleted` (`false`), `message`/`errors`/`id` (`null`)). Join key = `setting.name == node.uniqueIdentifier`
   (§Export shape) — exactly one `type:"CrudTree"` setting per tree node. When you
   MODIFY-FILLED a tree, patch `settings[].content` alongside the node `model`; when you delete the node,
   drop its setting.

### Recipe B. `process.table.pluin` for a workflow with index-based filtering

1. The **workflow** must exist in `rep-objects.json > workflows[]` (see
   [07-workflows-and-tasks.md](07-workflows-and-tasks.md)) — take its `identifier` for `workflowIdentifier`.

2. A **process group** in `rep-objects.json > processGroups[]`. The simplest is to set `name` = the future
   `uniqueIdentifier` of the plugin node (matches auto-creation):

   ```json
   { "realmName": "<realm>", "clientName": "<client>",
     "identifier": "<pg-uuid>", "name": "<node uniqueIdentifier>", "description": "<node uniqueIdentifier>" }
   ```
   In the plugin model set `processGroupIdentifier: "<pg-uuid>"`.

3. The **node** `process.table.pluin` in `branches.json` — placed **INSIDE THE PAGE's Layout content parsis**
   (NOT as a direct child of the siteMapPage) — `properties.model.stringValue`:

   > ⛔ **Placement is load-bearing — a `process.table.pluin` is NOT a page by itself.** The node must be the
   > child of the page's content `nct.parsis.plugin`, exactly as every real export nests it:
   > `siteMapPage → parsis.plugin(name="parsis") → html.plugin(name="Layout") → nct.parsis.plugin(name="parsis") → process.table.pluin`.
   > That inner `nct.parsis.plugin` is the same content hole that holds the `site.header` / `site.breadcrumb` /
   > `site.kicker` (left-nav) / `site.footer` chrome siblings. Attaching the node **directly under the
   > `siteMapPage`** (or at the branches root), or omitting the `html.plugin("Layout")` wrapper, **imports clean
   > but renders an EMPTY page**. Full page skeleton:
   > [01-content-model-and-pages.md](01-content-model-and-pages.md) (`html.plugin "Layout" → nct.parsis.plugin
   > id="parsis"` ← THE PAGE CONTENT GOES HERE). Every working process monitor nests this way.
   > **Live-render the page after import and confirm the table draws** before
   > calling it done.

   ```json
   {
     "workflowIdentifier": "<workflow id>",
     "processGroupIdentifier": "<pg-uuid>",
     "columnSettings": [
       { "id": "<uuid>", "localizedNames": {"en_US":"Customer Name"}, "dataClass": "java.lang.String",
         "scope": "CRUD", "contextIdentifier": "<ctx id>", "crudAlias": "ticket", "fieldExpression": "customerName" },
       { "id": "<uuid>", "localizedNames": {"en_US":"Created Date"}, "dataClass": "java.time.LocalDateTime",
         "scope": "CONTEXT", "contextIdentifier": "<ctx id>", "fieldExpression": "createdDate" }
     ],
     "indexSettings": [
       { "id": "<uuid>", "indexName": "customerName", "scope": "CRUD",
         "contextIdentifier": "<ctx id>", "fieldExpression": "customerName", "dataClass": "java.lang.String" },
       { "id": "<uuid>", "indexName": "createdDate", "scope": "CONTEXT",
         "contextIdentifier": "<ctx id>", "fieldExpression": "createdDate", "dataClass": "java.time.LocalDateTime" }
     ],
     "filterExpression": "like(customerName, %{customer_name}%) && createdDate > {created_date}",
     "userStartProcessActions": { "actions": [
       { "id": "<uuid>", "localizedNames": {"en_US":"Intake"}, "localizedButtonNames": {"en_US":"Intake"},
         "predicateIdentifier": "<predicate id>", "direct": "off",
         "formGroupIdentifier": "<form-group id>", "icon": "pe-7s-news-paper" }
     ], "errors": [] },
     "globalActions": { "actions": [
       { "id": "<uuid>", "localizedNames": {"en_US":"Edit"}, "localizedButtonNames": {"en_US":"Edit"},
         "predicateIdentifier": "<predicate id>", "onBeforeUserTaskCompleteRuleIdentifier": "<rule id>",
         "direct": "off", "formGroupIdentifier": "<form-group id>", "icon": "pe-7s-edit" }
     ], "errors": [] }
   }
   ```
   Also add the boolean `isParsis` (`booleanValue:false`) to the node's `properties`.

4. Key rules: `direct` for process actions is a **string** `"on"`/`"off"`; `globalActions` without a
   `predicateIdentifier` are not shown; `indexName` in `indexSettings` must exactly match the left-hand
   side of `filterExpression`; column headers are **`localizedNames`**, not the deprecated flat `name` — one key
   per entry in `tenant.json.locales` (the block shows only `en_US` for brevity). A flat `name` renders one
   string under every locale and neither `locale fill` nor `validate` will flag it (`locale fill` only completes
   maps that already exist).

5. **DONE-WHEN — append the settings mirror.** After the node exists you MUST also append to
   `rep-objects.json.settings[]` one object `{ "type":"ProcessTable", "name":"<node.uniqueIdentifier>",
   "content": <the SAME model, as a parsed JSON object> }` (plus the full
   `AbstractSecuredDto` housekeeping set: `identifier`, `realmName`, `clientName`, `creationTime`,
   `modificationTime`, `deleted` (`false`), `message`/`errors`/`id` (`null`)). Join key = `setting.name == node.uniqueIdentifier`
   (§Export shape) — exactly one `type:"ProcessTable"` setting per process node. When you MODIFY-FILLED,
   patch `settings[].content` alongside the node `model`; when you delete the node, drop its setting.

---

## Gotchas

0a. **⛔ A `crud.tree.plugin` has NO pagination — plan the screen around a filter, not a pager.**
   `CrudTreePlugin.java` constructs its `CrudTableTree` with a hardcoded `Long.MAX_VALUE` page
   size and never reads `model.rowsPerPage`, so every root renders at once and Wicket's
   `NavigationToolbar` (added at `CrudTableTree.java`) stays invisible because there is only ever
   one page. The data layer agrees: the generated `findByParent` carries **no `LIMIT`/`OFFSET`**,
   unlike `findAll`. Consequence: a tree over a table with many ROOTS (one root per parent-less row)
   renders all of them in one very long page. **The fix is a filter that collapses the root set**
   (typically the owning entity id, which is subtree-safe because every descendant carries it),
   never a page-size setting. Real pagination would be an nct-ui change plus LIMIT/OFFSET on the
   roots query — do not promise it from the export.

0b. **⛔ The index is written at only THREE moments, and it does not backfill.** `indexSettings[]` is the
   WRITE side; `IndexValueExtractor` projects the context into `paramsToFilter` at **process start**, at a
   **direct action**, and at **form submit** — nowhere else. Consequences you must design around:
   *(a)* instances that were started **before** an index existed are permanently unfilterable on it (the
   JSONB simply has no such key), so add `indexSettings` **before** anyone starts processes, not after;
   *(b)* a freshly imported project has **no process instances at all** — a process-table filter cannot be
   validated offline or against the DB dump, only after the first instances run, so treat it as unverified
   until then; *(c)* for a non-direct (form-opening) action the settings reach the form only through the
   `rep-objects.settings[]` mirror row (`type: "ProcessTable"`, `name` = the table node's
   `uniqueIdentifier`) — **without that row nothing is ever written and the filter is silently inert**;
   *(d)* the write **replaces** the whole JSONB rather than merging, so every index you want must be in the
   same `indexSettings[]` list. The mandate to give every table a filter, and the crud-side equivalent of
   this trap, live in [19 Phase 9](19-build-decision-procedure.md) and
   [04 §Standalone Filter Form](04-crud-table-plugin.md).

1. **The process `pluginName` is `process.table.pluin`** (a typo, not `process.table.plugin`).
   `crud.tree.plugin` has no typos. (`ProcessTablePlugin.java`, `CrudTreePlugin.java`.)

2. **The config is in `properties.model.stringValue`, NOT in `settings`.** Both plugins use the `model` slot
   (unlike form controls, [02](02-form-controls-reference.md)). It's a JSON string; escape it.

3. **Tree: DTO path ≠ filter name.** `parentFieldExpression` (`parent.id`) is a path in the row;
   `parentFilterFieldExpression` (`parentId`) is the property name in the filter class that actually goes to
   `findByParent`. If you set only the DTO path, the parent's id lands in a non-existent filter field →
   stays `null` → each parent returns all rows (`CrudTreeDataProvider.java`).

4. **Tree: `findByParent` is required on the CRUD.** The provider calls the fetch-rule, which calls
   `service.crud.<alias>.findByParent(...)`. For a dynamic CRUD this method must be defined explicitly
   (a GROOVY wrapper over `findAllByParent`, see [11](11-business-logic-dynamic-crud.md)).
   ⚠️ **Trees are rare, and a dynamic-CRUD tree rarer still** — most projects have none, so do not count on
   finding one to copy from. The `findByParent` requirement on a dynamic CRUD follows from the code
   (`CrudTreeDataProvider.FIND_BY_PARENT_METHOD`; rule body — `buildFindByParentScript`). Verify on your first
   dynamic tree that the `findByParent` method really exists in the target CRUD's `dynamic-cruds.json`.

5. **Tree: circuit breaker of 50 fetches/request** (`MAX_FETCHES_PER_REQUEST=50`,
   `CrudTreeDataProvider.java`). If the data has a parent cycle or `findByParent` ignores
   the filter — the tree is truncated and logs, rather than hanging the browser. This is a symptom of a wrong
   `parentFilterFieldExpression`.

6. **Process: `direct` is a string `"on"`/`"off"`.** `isDirect()` = `equals(direct,"on")`
   (`UserTaskActionsDto.java`). A Boolean `true`/`false` in JSON will NOT work. For tree/table CRUD
   actions it's the opposite boolean.

7. **Process: `globalActions` without a predicate are invisible.** Fail-closed: an action without a `predicateIdentifier`
   is not shown and not executed (`ProcessTablePlugin.java`). Always set
   `predicateIdentifier` for a global action.

8. **Process: columns read the context, not the row.** A column value is determined by `scope`
   (GLOBAL/CONTEXT/CRUD) and the process context data (`extractColumnValue`) — this is
   fundamentally different from the flat CRUD-row read in the table/tree. All three scopes resolve, but only
   against what the START wrote into that document: a `scope:"CRUD"` column is a snapshot of the row as it
   was at start, and it is empty for a start that seeded no `crudDataMap` entry (see the ⚠️/⛔ block above).

9. **Process: `indexName` in `filterExpression` — by name, not by "correctness".** A typo like
   `cusromerName` works if it is the same in both `indexSettings.indexName` and `filterExpression`.

10. **Process: the process group is auto-created with name = the node's `uniqueIdentifier`.** For a
    self-contained export, either place an object in `processGroups[]` with this name in advance, or
    leave `processGroupIdentifier` empty and let the plugin create the group on first render
    (then there will be no object in the export — but the imported project will be incomplete until the first render).

11. **The tree's `editComponent` returns `null`** (`CrudTreePlugin.java`) — all configuration goes
    through the settings panel. For the process, `editComponent` provides only workflow selection
    (`ProcessTablePluginEditor`), everything else — via `ProcessTableSettingsControlPanel`. For export
    generation this is irrelevant (we write JSON directly), but it explains why the node has no separate
    property slots for columns/actions — everything is in `model`.

12. **Process: access-control is NOT a plugin setting.** The concept doc `table-plugins.md` has a section
    about `ProcessAccessType` (`ROLE`/`ROLE_GROUP`/`USER`), `isOwner`, allow/deny — **this is outdated/
    misleading material**: `ProcessTablePluginModel` has no `accesses`/`ProcessAccessDto` field
    (grep — 0), those DTOs live on `FlowableProcessDto` (per-process-instance, runtime workflow), NOT in
    the plugin's `model.stringValue`. Do NOT add an access section to the process table JSON. (The process model is
    exactly 7 fields: `workflowIdentifier`, `processGroupIdentifier`, `columnSettings`, `indexSettings`,
    `filterExpression`, `userStartProcessActions`, `globalActions`.)

13. **An "empty" starting-point baseline typically already contains `process.table.pluin` nodes** with a
    populated `model` (and its own `uniqueIdentifier` per export). That `model` references a
    `workflowIdentifier`/`contextIdentifier` the baseline has **no** backing object for — i.e. **dangling**.
    When starting from such a baseline you MUST consciously either **repoint** the model to a real
    `workflowIdentifier`/`contextIdentifier` (and add the matching settings mirror, see Recipe B step 5)
    **or delete the nodes**; leaving them as-is imports a broken process table.

14. **Enum columns/indexes.** As for a CRUD column (04): `enumName` = the name of the project Enumeration in the registry,
    `enumDisplayField` = the enum property to display (empty/`"name"` → the constant name), `enumValues` =
    a snapshot of the enum's property table (needed because the gateway cannot `Class.forName` the project enum).
    Supported only when `scope==CRUD` (`extractColumnValue`, the CRUD branch).

---

## Cross-links

- [01-content-model-and-pages.md](01-content-model-and-pages.md) — the page skeleton the tree/process node MUST
  live inside: `siteMapPage → parsis.plugin → html.plugin("Layout") → nct.parsis.plugin("parsis") → <content>`.
  A node placed directly under a siteMapPage imports clean but renders an empty page (see Recipes A/B step 3).
- [04-crud-table-plugin.md](04-crud-table-plugin.md) — the base `crud.table.plugin`; the shared types
  `CrudTableColumnSettings`/`CrudTableFilterSettings`/`CrudTableActionsDto`, `findRuleIdentifier`,
  `importSettings` (the tree/process have no import).
- [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) — where non-direct actions navigate
  (`formGroupIdentifier` → form-group), predicate→form mapping.
- [07-workflows-and-tasks.md](07-workflows-and-tasks.md) — `workflowIdentifier`, task-actions, with which
  `globalActions` are merged from the workflow's own task-actions; process groups.
- [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) — the tree fetch-rule, action visibility
  predicates, `onBefore*RuleIdentifier`, `FormControlScope` GLOBAL/CONTEXT/CRUD and how rules
  read the context.
- [27-event-driven-process-start.md](27-event-driven-process-start.md) §6 — the other side of the column
  question: what a case started by a RULE (no start form) carries in its document, and therefore which of
  this node's columns and indexes have anything to show.
- [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) — the `findByParent` method on a
  dynamic CRUD (required for the tree).
- ⚠️ Older platform documentation on table plugins, process groups/instances and the filter-expression
  language is partially outdated. What is wrong in it: short field names
  (`formGroup`/`predicate`/`beforeStartRule`), a single `name`, the absence of `findRuleIdentifier`/
  `parentFilterFieldExpression`, and the access-control section — all of these
  diverge from the real code/export (see the Gotchas above).
