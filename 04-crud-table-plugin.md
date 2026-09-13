# CRUD Table plugin (`crud.table.plugin`)

> 📐 **Field evidence — how tables are really configured:** [03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md) · [04-forms-actions-validation.md](references/04-forms-actions-validation.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> ⛔ **ONE table per PAGE — the ONLY exception is separate tabs.** The rule is about *tables*, not about
> *this plugin*: it covers `crud.table.plugin`, `crud.tree.plugin` and `process.table.pluin` **in any
> combination**. Two `crud.table.plugin` collide technically (shared type-scoped Settings panel +
> `getKey()` sync channel, both page-wide); a crud-table next to a **process-table** does not collide —
> and is still forbidden, because a page is one workplace answering one question. The one way to
> co-locate two tables is **each in its own tab** (`nct.tab.plugin`); otherwise give each its own page.
> And a **dashboard (charts) carries no table** — the `dynaform` filter drives tables, not charts.
> `mrjun.py validate` **ERRORs** on two tables in one container (same type or mixed). The dashboard rule is only
> a **WARN**, and only when the page carries 3+ charts and 1+ table — below that nothing flags it, so keeping
> dashboards table-free is on you. Full mechanism + rule:
> [14-plugin-catalog-all.md §2.3–2.4](14-plugin-catalog-all.md).

## What it is / when to use

`crud.table.plugin` is the platform's primary table/list control: it renders an HTML table of
rows of a single CRUD (by `crudAlias`), with pagination, columns, filters and an action menu
(Create / Edit / Delete / custom actions) on every row and in the header. It does not read data
directly from the CRUD service; instead it **runs an EXECUTION rule** (`findRuleIdentifier`, the "fetch rule"),
which returns a page (`content` / `totalElements` / `totalPages`) — so the same control
works both with a static CRUD and with a dynamic one, see
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

Use it for any "main entity page" (a list of invoices, declarations, orders, tickets, documents). The tree variant
(`crud.tree.plugin`) and the process table (`process.table.pluin`, the plugin's spelling is
exactly that) are in [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md);
generating the form for Create/Edit is in [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md);
form groups and predicate→form mapping, where non-direct actions lead, are in
[06-form-groups-and-mapping.md](06-form-groups-and-mapping.md); rules and context are in
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md); the form controls that make up
the Create/Edit form are in [02-form-controls-reference.md](02-form-controls-reference.md).

⚠️ If you are also handed older platform documentation on table plugins, actions, CRUD or icons, treat it as
partially outdated — the notes below flag each place it diverges from what the code actually does.

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `node add --plugin crud.table.plugin --model @model.json`, `node set-model <id>`, `node patch-model <id> --set rowsPerPage=num:25` (table config lives in `properties.model`, the CLI picks the slot itself).
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.

Plugin registration:
`@PluginConfig(pluginName = "crud.table.plugin", displayName = "CRUD Table", group = "Lists", renderBodyOnly = false)`
(`CrudTablePlugin.java`).

## Export shape

In the content tree a `crud.table.plugin` node stores its ENTIRE configuration as a JSON string in
`properties.model.stringValue` (**not `settings`** — unlike form controls! see
[01-content-model-and-pages.md](01-content-model-and-pages.md) about `properties` slots). The plugin renders
specifically **from `properties.model`** (`CrudTablePlugin.java`), yet the same model is **additionally
mirrored** into a `rep-objects.settings[]` object with field `type:"CrudTable"` (the join key is
`setting.name == node.uniqueIdentifier`). Expect roughly one such `CrudTable` object per table node (plus
leftovers of deleted nodes). **The mirror is not decoration.** The node RENDERS from `properties.model`, but the
FORM a non-direct action opens reads the **mirror**: the action navigates with `settingsName=<node.uniqueIdentifier>`
and the form loads `settings[name == that]` to learn the `crudAlias`, `contextIdentifier`, the action's button
label, its `predicateIdentifier`, its `onBeforeStart`/`onBeforeComplete` rules and `submitForm`
(`SettingsNavigationHelper`). So: **missing mirror ⇒** the form never enters CRUD mode — no entity is loaded,
no predicate re-check, no persist rule, nothing is written; **stale mirror ⇒** the form runs the OLD action
config while the table renders the new one (an action id the mirror doesn't know gives a blank submit button
and no rules, yet the submit still reports success). Keep the two in sync — `node set-model`/`patch-model` do it
for you.

> ⚠️ **The mirror's `content` is a JSON OBJECT, not a string.** `SettingsDto.content` is a Jackson `ObjectNode`,
> so the mirror stores the parsed model **object** — the OPPOSITE of `properties.model.stringValue`, which is a
> JSON *string*. If you edit a table by hand and write the mirror `content` as a string (e.g. by copying the node's
> model stringValue), the platform IMPORTER dies with `MismatchedInputException: Cannot deserialize ObjectNode from
> String value` (chain `Qss["settings"]->SettingsDto["content"]`, `CmsProjectServiceImpl.initAllObjects`). That
> exception aborts the ENTIRE REPORT-path import (`readOtherFilesFromFolder`→`initAllObjects`): sources are never
> saved (business logic shows "No source selected"), `project-db.dump` is never restored (all data/dates look
> gone), even though the dynamic-CRUD replay still runs. **`mrjun.py node set-model`/`patch-model` keep this mirror
> in sync as an object** — prefer them over hand-editing. `validate` flags a string `content` as an ERROR, but is
> not a substitute for a live import + a scan of the platform's `log/ui.log`.

The `fieldPanelClass`
of the `model` slot = `com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel`.
The design-time `properties` keys on the node are
`className`, `model`, `styleName`, `tagProperties` — three of them empty. That is the full **design-time** slot
set; **import-touched nodes additionally carry** the runtime-written STRING slots `importMapping` and/or
`lastImportReport` (see the Import sections below), so such a node shows five slots, e.g.
`["className","lastImportReport","model","styleName","tagProperties"]`.

Node schema (trimmed to the relevant parts):

```
{ "pluginName": "crud.table.plugin", "name": "CRUD Table", "identifier": "...", ...
  "properties": {
    "model": {
      "key": "model", "propertyType": "STRING",
      "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
      "stringValue": "<JSON — CrudTablePluginModel>"          // <-- parse this
    },
    "className": {...}, "styleName": {...}, "tagProperties": {...}
    // import-touched nodes ALSO carry runtime STRING slots "importMapping" and/or "lastImportReport"
  } }
```

The parsed `model.stringValue` = **`CrudTablePluginModel`**:

```
{ contextIdentifier, crudAlias,
  columnSettings: [ CrudTableColumnSettings ],
  filterSettings: [ CrudTableFilterSettings ],
  createActions: { actions: [ ActionDto ] },
  editActions:   { actions: [ ActionDto ] },
  rowsPerPage: 15,
  findRuleIdentifier,                 // fetch rule (may be absent → auto-created)
  importSettings: CrudTableImportSettingsDto }
```

### Worked example (truncated — a static CRUD `inventoryCount`)

> ⚠️ This is a **truncated** example: the full `inventoryCount` node is larger. It has **5 columns**
> (`documentNumber`, `status`, `plant.code`, `countDate` `java.time.LocalDate`, `totalLines`
> `java.lang.Integer`), the `status` enum has **5 constants** (`DRAFT`, `COUNTING`, `ADJUSTMENT_PENDING`,
> `COMPLETED`, `CANCELLED`), and `editActions` contains **5 actions**: `Edit` (non-direct), `Delete`,
> `Start`, `Post Adjustments`, **`Cancel`** (the last three are direct with different predicates). Not all
> are shown below for readability; the full list of the five edit actions is in the "All edit actions
> of the `inventoryCount` node" table. This is typical: a single `crud.table` node usually carries several custom
> direct actions with different visibility predicates.

```json
{
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "inventoryCount",
  "columnSettings": [
    {
      "id": "70609b84-b813-407e-a85c-b7fbc19ace36",
      "localizedNames": { "en_US": "Document Number", "hy_AM": "Փաստաթղթի համարը", "ru_RU": "Номер документа" },
      "fieldExpression": "documentNumber",
      "dataClass": "java.lang.String"
    },
    {
      "id": "b398d7a5-1641-4e3b-ab75-36b3ea8e48a5",
      "localizedNames": { "en_US": "Status", "hy_AM": "Կարգավիճակ", "ru_RU": "Статус" },
      "fieldExpression": "status",
      "dataClass": "com.devsegment.erp.dto.enums.CountStatus",
      "enumDisplayField": "displayName",
      "enumValues": {
        "DRAFT":              { "displayName": "Draft",              "name": "DRAFT" },
        "COUNTING":           { "displayName": "Counting",           "name": "COUNTING" },
        "ADJUSTMENT_PENDING": { "displayName": "Adjustment Pending", "name": "ADJUSTMENT_PENDING" },
        "COMPLETED":          { "displayName": "Completed",          "name": "COMPLETED" },
        "CANCELLED":          { "displayName": "Cancelled",          "name": "CANCELLED" }
      },
      "enumName": "CountStatus"
    },
    { "id": "63abd9e2-96bc-4ac6-a6d1-13d8f9a98be8",
      "localizedNames": { "en_US": "Plant" },
      "fieldExpression": "plant.code", "dataClass": "java.lang.String" },
    { "id": "07d5064e-58e4-4c91-bc16-fd1c34de1f58",
      "localizedNames": { "en_US": "Count Date" },
      "fieldExpression": "countDate", "dataClass": "java.time.LocalDate",
      "dateFormat": "DD/MM/YYYY" },
    { "id": "4beb0d63-dd35-432a-be60-a5ed9d068cf6",
      "localizedNames": { "en_US": "Total Lines" },
      "fieldExpression": "totalLines", "dataClass": "java.lang.Integer" },
    { "id": "9f2c7a10-5d31-4f0e-9a44-2b6f7c1e88d0",
      "localizedNames": { "en_US": "Stock Value" },
      "fieldExpression": "stockValue", "dataClass": "java.math.BigDecimal",
      "money": true, "currency": "$", "moneyFormat": "US", "moneyDecimals": 2 }
  ],
  "filterSettings": [],
  "createActions": {
    "actions": [
      { "id": "97b8d816-c3fa-4a3f-8dad-df5f2bda6768",
        "localizedNames": { "en_US": "Create Inventory Count", "ru_RU": "Создать учет запасов", "hy_AM": "..." },
        "localizedButtonNames": { "en_US": "Create Inventory Count", "ru_RU": "Создать учет запасов", "hy_AM": "..." },
        "icon": "pe-7s-plus",
        "formGroupIdentifier": "0ff5ec4c-e9c4-431f-a817-28d8547aa993",
        "direct": false,
        "onBeforeCompleteRuleIdentifier": "60bb96bf-fb63-499a-a1b8-f4a264e38920" }
    ]
  },
  "editActions": {
    "actions": [
      { "id": "2aff4c25-0283-48b3-8302-63ce0517a6fc",
        "localizedNames": { "en_US": "Edit Inventory Count" },
        "localizedButtonNames": { "en_US": "Edit Inventory Count" },
        "icon": "pe-7s-pen",
        "formGroupIdentifier": "0ff5ec4c-e9c4-431f-a817-28d8547aa993",
        "direct": false,
        "predicateIdentifier": "7fcdc152-dc10-4708-837c-a441ea6fb946",
        "onBeforeCompleteRuleIdentifier": "ce7c2851-d8cc-44a5-a95e-8a89a80543d1" },
      { "id": "ba4e285f-1025-4811-95eb-438139d553d2",
        "localizedNames": { "en_US": "Delete Inventory Count" },
        "localizedButtonNames": { "en_US": "Delete Inventory Count" },
        "icon": "pe-7s-trash",
        "direct": true,
        "onBeforeCompleteRuleIdentifier": "1851ea31-034d-4485-a9aa-8048e1548959" },
      { "id": "2eadd39a-e761-4b1f-8bc9-573db7dba3b9",
        "localizedNames": { "en_US": "Start" },
        "localizedButtonNames": { "en_US": "Start" },
        "icon": "pe-7s-exapnd2",
        "direct": true,
        "predicateIdentifier": "7fcdc152-dc10-4708-837c-a441ea6fb946",
        "onBeforeCompleteRuleIdentifier": "876e9436-3462-4083-b8c0-d460d0c15009" },
      { "id": "5441208e-c9a0-419b-a829-a607f98098f2",
        "localizedNames": { "en_US": "Post Adjustments" },
        "localizedButtonNames": { "en_US": "Post Adjustments" },
        "direct": true,
        "predicateIdentifier": "869f17aa-d451-4c7b-bddb-c35abcd2f632",
        "onBeforeStartRuleIdentifier": "39b56126-1e7e-4b2f-9601-547cc2e7d345" },
      { "id": "cb39b172-be37-451e-a6dd-a97b083ca7fa",
        "localizedNames": { "en_US": "Cancel" },
        "localizedButtonNames": { "en_US": "Cancel" },
        "icon": "pe-7s-exapnd2",
        "direct": true,
        "predicateIdentifier": "8807b62b-7ca0-40ec-80ab-51cdf3ccda8c",
        "onBeforeCompleteRuleIdentifier": "0bf6e749-ba8a-42a8-9cbf-85b2acf9780f" }
    ]
  },
  "findRuleIdentifier": "1eb749c2-8cf2-4450-be77-41ddafcff599",
  "rowsPerPage": 15
}
```

**All edit actions of the `inventoryCount` node**, to show a typical set of custom
direct actions and the **reuse of a single predicate by multiple actions**:

| Action (`en_US`) | `id` | `direct` | `icon` | `predicateIdentifier` | rule |
|---|---|---|---|---|---|
| Edit Inventory Count | `2aff4c25-…` | `false` | `pe-7s-pen` | `7fcdc152-…` | `onBeforeComplete=ce7c2851-…` |
| Delete Inventory Count | `ba4e285f-…` | `true` | `pe-7s-trash` | — | `onBeforeComplete=1851ea31-…` |
| Start | `2eadd39a-…` | `true` | `pe-7s-exapnd2` | `7fcdc152-…` | `onBeforeComplete=876e9436-…` |
| Post Adjustments | `5441208e-…` | `true` | (none) | `869f17aa-…` | `onBeforeStart=39b56126-…` |
| Cancel | `cb39b172-…` | `true` | `pe-7s-exapnd2` | `8807b62b-…` | `onBeforeComplete=0bf6e749-…` |

Note: **Edit and Start use the SAME predicate** `7fcdc152-…` (`Inventory Count Action Can Edit`,
`status == 'DRAFT'`). The runtime deduplicates distinct non-empty `predicateIdentifier` values and evaluates
each unique one once per row (see "Visibility predicate"), so reusing a predicate
across actions is a normal and cheap pattern.

> ⛔⛔ **LOAD-BEARING — `onBeforeCompleteRuleIdentifier` IS the PERSIST hook; a Create/Edit/Delete action
> WITHOUT it submits and SAVES NOTHING.** "Create Default Actions" does **not** only create the form group + form
> — it also creates **three EXECUTION rules** and wires one onto each default action
> (`CrudDefaultActionsService.buildCreate/Update/DeleteScript` + `CrudTableSettingsControlPanel.finalizeDefaultActions`,
>):
>
> | action | `onBeforeCompleteRuleIdentifier` → rule body | rule name | `direct` |
> |---|---|---|---|
> | **Create** | `def created = context.<ctx>.<crud>.service.create(context.<ctx>.<crud>.data.get())`<br>`context.<ctx>.<crud>.data.put(created)` | `"<Crud> Action Create"` | `false` |
> | **Edit** | `context.<ctx>.<crud>.service.update(context.<ctx>.<crud>.data.get())` | `"<Crud> Action Update"` | `false` |
> | **Delete** | `context.<ctx>.<crud>.service.delete(context.<ctx>.<crud>.data.get().id)` | `"<Crud> Action Delete"` | **`true`** |
>
> These are `EXECUTION_RULE` / `GroovyExecutionRule` and — critically — **context-scoped**:
> `contextIdentifiers=[<the CRUD's context>]`, so `context.<ctx>.<crud>` resolves at submit (an **empty-context**
> persist rule throws — "cannot resolve context.<ctx>.<crud>"). On submit, `FormPlugin` (`FormPlugin.java`)
> runs the action's `onBeforeCompleteRuleIdentifier` — **that rule IS the database write; there is no separate
> auto-persist.** So a Create/Edit form action with **NO** onBeforeCompleteRule (or one whose rule never calls
> `.service.create/update/delete(...)` / a custom persist method) opens the form, accepts input, submits — and
> **persists nothing**; a `direct:true` Delete with no onBeforeCompleteRule does nothing on click. Import, `validate`,
> `coverage` and `crud verify` all stay GREEN — only a live submit reveals it. When hand-building a CRUD table wire
> **all three** (create→create rule, edit→update rule, delete→delete rule). `validate` now **WARNs** on a
> Create/Edit form action or a direct action with no `onBeforeCompleteRuleIdentifier` (`_check_action_persist`)
> — and on the reverse shape, a `submitForm:false` action that DOES carry an `onBeforeCompleteRuleIdentifier`,
> because that rule can never run (see §`ActionDto`: `submitForm:false` skips validation *and* rule execution).
> Legit exceptions (not flagged): `submitForm:false` with **no** rule (a read-only Back button), and a
> workflow-**start** action on a **process** table (the workflow persists, not onBeforeComplete).

Note: the `contextIdentifier` above (`77cd568d-…`) is the UUID of a context whose alias is `rimmContext`;
rules read the row via `context.rimmContext.inventoryCount.data.get()` (see below). Each project has its own
context UUID and alias — in the dynamic example below the context is `catalog_context` (`871f974f-…`) and the
`crudAlias` is `product_categories_cruid`.

### Dynamic example (a dynamic CRUD `product_categories_cruid`)

The same shape, but written in the **old action style** — the actions carry a `name` field (String) instead of
`localizedNames` (the create action's keys = `id, name, icon, formGroupIdentifier, direct`),
and there is **no** `findRuleIdentifier` (created on first render — see Gotchas). ⚠️ This is an outdated schema:
on the current code the action's `name` is ignored (the CRUD `ActionDto` has no such field), and the label renders
empty — for new nodes use `localizedNames`, not `name` (see Gotchas):

```json
{
  "contextIdentifier": "871f974f-e775-401a-adfc-e822110f3b99",
  "crudAlias": "product_categories_cruid",
  "columnSettings": [
    { "id": "39c3c447-...", "localizedNames": { "en_US": "Category name", "hy_AM": "Անվանումը" },
      "fieldExpression": "name", "dataClass": "java.lang.String" },
    { "id": "0cdc6243-...", "localizedNames": { "en_US": "Category", "hy_AM": "Կատեգորիա" },
      "fieldExpression": "categoryLabel", "dataClass": "java.lang.String" }
  ],
  "filterSettings": [],
  "createActions": { "actions": [
    { "id": "ac1e51b7-...", "name": "Create Product Categories Cruid", "icon": "pe-7s-plus",
      "formGroupIdentifier": "b7278f9c-...", "direct": false } ] },
  "editActions": { "actions": [
    { "id": "7fec0acf-...", "name": "Edit Product Categories Cruid", "icon": "pe-7s-pen",
      "formGroupIdentifier": "b7278f9c-...", "direct": false },
    { "id": "fc57ba03-...", "name": "Delete Product Categories Cruid", "icon": "pe-7s-trash",
      "direct": true, "onBeforeCompleteRuleIdentifier": "f8240612-f688-43f8-99c7-8ad804a918db" } ] },
  "rowsPerPage": 15
}
```

> **Identifiers are UUIDs, not slugs.** In a real export `contextIdentifier`,
> `formGroupIdentifier`, `predicateIdentifier`, all `on*RuleIdentifier`, `findRuleIdentifier`, and also
> the `id` of columns/filters/actions are **UUIDs**. The exception is `crudAlias`, which may be a human-readable
> alias (`inventoryCount`) OR a generated one (`product_categories_cruid`). When assembling by hand, generate
> real UUIDs (`uuidgen`), not readable slugs.

---

## Per-field reference

### `CrudTablePluginModel` (root)

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `contextIdentifier` | String (UUID) | Identifier of the context from which rules see other CRUDs via `context.<alias>.…`. Empty → fallback to `crudAlias`. | no (needed if rules/actions use context) | `null` | `CrudTablePluginModel.java`; fallback `CrudTablePlugin.java` (visibility) and (edit action) |
| `crudAlias` | String | **Short** alias of the CRUD the table shows (e.g. `inventoryCount`, `product_categories_cruid`). | yes | `null` | `CrudTablePluginModel.java` |
| `columnSettings` | `CrudTableColumnSettings[]` | Table columns. | no | `[]` | |
| `filterSettings` | `CrudTableFilterSettings[]` | Filters over the table. | no | `[]` | |
| `createActions` | `CrudTableActionsDto` = `{ actions: ActionDto[] }` | Header "create" actions, rendered as **breadcrumb buttons** above the table (`CrudTablePlugin.hasBreadcrumbButtons()`, `breadcrumbButtons()` looping `getCreateActions()`; the Import button shares the same bar). | no | `null` | |
| `editActions` | `CrudTableActionsDto` = `{ actions: ActionDto[] }` | Per-row actions in the row's dropdown menu (Edit/Delete/custom). | no | `null` | |
| `rowsPerPage` | int | Pagination page size. On `crud.tree.plugin` the default = `Integer.MAX_VALUE` (2147483647). | no | `15` | (tree: `plugin/crud/tree/CrudTreePluginModel.java`) |
| `findRuleIdentifier` | String (UUID) | EXECUTION rule `Find — <crudName>` returning a page of rows. Empty → auto-created at render time. | no | `null` |; auto `CrudTablePlugin.java` |
| `importSettings` | `CrudTableImportSettingsDto` | CSV/Excel import settings. | no | `null` | |

### `CrudTableColumnSettings` (element of `columnSettings[]`)

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `id` | String (UUID) | Unique column id. | yes | — | `CrudTableColumnSettings.java` |
| `name` | String | **@Deprecated** legacy header; fallback if `localizedNames` is empty. | no | `null` | |
| `localizedNames` | Map\<locale,String\> | Header per locale (`en_US`, `ru_RU`, `hy_AM`, …). | yes (in practice) | `null` |; resolve `getLocalizedName` |
| `fieldExpression` | String | Path to the row DTO field, supports nesting: `documentNumber`, `plant.code`, `address.city`, `categoryLabel`. | yes | `null` | |
| `dataClass` | String (FQN) | Java field type: `java.lang.String`, `java.lang.Integer`, `java.lang.Long`, `java.math.BigDecimal`, `java.time.LocalDate`, `java.lang.Boolean`, or an enum class FQN (`com.devsegment.erp.dto.enums.CountStatus`). | yes | `null` | |
| `enumDisplayField` | String | For an enum column — which enum property to draw in the cell. `null`/`""`/`"name"` → render the constant name; otherwise (e.g. `displayName`) — the value from `enumValues`. | no | `null` |; render `EnumColumnUtils.formatEnumCellValue` (`EnumColumnUtils.java`) |
| `enumValues` | Map\<constName, Map\<prop,String\>\> | Snapshot of the enum's property table (the gateway cannot `Class.forName` the enum class, since it lives in the integration service). Projects the raw name through `enumDisplayField`. Snapshotted at design time from `FieldDto.enumValues`. | no | `null` | |
| `enumName` | String | Registry name of the project Enumeration (for dynamic enums). Mirrors `FieldDto.enumName`. `null` for non-enum columns. | no | `null` | |
| `trueIcon` | String | **Boolean columns only** (`dataClass == java.lang.Boolean`): Pe-7s CSS class rendered **instead of** the raw `true` text (e.g. `pe-7s-check`). Blank → raw text. | no | `null` |; render `BooleanIconColumnUtils.buildCell` (`utils/BooleanIconColumnUtils.java`) |
| `falseIcon` | String | Boolean columns only: Pe-7s CSS class rendered instead of the raw `false` text (e.g. `pe-7s-close`). Blank on this side → that value falls back to raw text. | no | `null` | |
| `money` | boolean | **Numeric columns only** (`Integer/Long/Short/Byte/Double/Float/BigDecimal/BigInteger` + primitives): render the cell as money — grouped digits, fixed decimals, optional `currency` marker. `false` → the number is drawn as-is. | no | `false` |; render `ColumnCellFormatUtils.format` → `MoneyColumnUtils.formatCellValue` (`utils/MoneyColumnUtils.java`) |
| `currency` | String | Money columns: the marker drawn with the amount — a symbol (`$`, `€`, `֏`, `₹`) or an ISO code (`USD`, `AMD`). **Free text** — the settings control is an autocomplete over suggestions, not a closed list. Blank → amount only. | no | `null` | |
| `moneyFormat` | String (enum name) | Money columns: the grouping/decimal standard. One of `US` (1,234.56) · `EUROPEAN` (1.234,56) · `SPACE_COMMA` (1 234,56) · `SPACE_DOT` (1 234.56) · `SWISS` (1'234.56) · `INDIAN` (12,34,567.89) · `PLAIN` (1234.56). Blank → `US`. | no | `null` (= `US`) | |
| `moneyDecimals` | Integer | Money columns: decimal places, `0`–`6`. Null → `2`. Needed as its own key because the DB scale is already lost before the UI sees the value (a `BigDecimal(1234.50)` arrives as the double `1234.5`), so this is the only authority on how many decimals show. | no | `null` (= `2`) | |
| `dateFormat` | String (moment.js) | **Temporal columns only** (`dataClass` = `java.time.LocalDate` / `LocalDateTime` / `Instant`): display pattern, e.g. `DD/MM/YYYY HH:mm:ss`. **Same catalogue and same vocabulary as the Date Picker form control** (doc [14a](14a-plugin-config-reference.md) §Date Picker). Blank → the raw stored ISO value. | no | `null` | ; render `DateFormatColumnUtils.formatCellValue` (`utils/DateFormatColumnUtils.java`) |

> **Enum render** (`extractColumnValue` → `EnumColumnUtils.formatEnumCellValue`): for an enum column
> the "live" projection from the integration service (`enumProjections`) is taken; if absent — the snapshot
> `enumValues` from the column setting. The enum path takes priority over value localization
> (`CrudTablePlugin.java` — the `extractColumnValue` method, enum branch before localization). Non-enum
> columns must **omit** `enumDisplayField/enumValues/enumName`.

> **Localization of DATA (not the header):** if a row column has a localized value (a CRUD with
> `localizationField`, see [11](11-business-logic-dynamic-crud.md)), the runtime first takes it via
> `localizedValueUtil.getLocalizedValue(rowData, fieldExpression, locale)`, otherwise — the direct field
> (`CrudTablePlugin.java`). This is the column's "localize" feature; it does not apply to enums.

> **Boolean icons** (`BooleanIconColumnUtils.buildCell`, `utils/BooleanIconColumnUtils.java`, called from
> `CrudTablePlugin.java`): for a boolean column (`dataClass == java.lang.Boolean`) with at least one of
> `trueIcon`/`falseIcon` set, the cell renders that Pe-7s icon (as `<i class="…">`, escaping off) **instead of**
> the raw `true`/`false` text — `trueIcon` for a truthy value, `falseIcon` for falsy. A side with a **blank**
> icon falls back to the raw text; both blank → plain `true`/`false`. Icons come from the fixed
> `Pe7sDropDownField.PE7S_ICONS` set; defaults `pe-7s-check`/`pe-7s-close`, with a name-aware prefill
> `defaultIconsFor` (e.g. `lock → pe-7s-lock/pe-7s-unlock`). The tree and process table render this
> identically via the same helper. Omit both keys for non-boolean columns.

> **Cell alignment.** Numeric (`Integer/Long/Short/Byte/Double/Float/BigDecimal/BigInteger` + their primitives)
> and boolean cells are **right-aligned** at render (CSS `text-end`, `BooleanIconColumnUtils.isRightAligned`
> / `RIGHT_ALIGN_CLASS`), spreadsheet-style; string/enum cells stay left. Pure render CSS — no
> settings key.

> ⛔ **The column's `dataClass` must be numeric because the VALUE is money — not the other way round.**
> `money: true` on a `java.lang.String` column is inert and silent, and the underlying mistake is that a
> money value is being carried as text at some layer below. Fix the type everywhere it appears (DB column,
> CRUD `dtoFields`, form control, column) rather than only here — the full rule and the `validate` check
> are in [10-database-management.md](10-database-management.md) §*Money is `NUMERIC`*.
>
> **Money render** (`MoneyColumnUtils.formatCellValue`, reached from `extractColumnValue` via
> `ColumnCellFormatUtils`): with `money: true` on a numeric column the amount is grouped per
> `moneyFormat`, rounded HALF_UP to `moneyDecimals` places, and the `currency` marker is attached —
> **a letters-only marker (an ISO code) always trails** the amount after a non-breaking space
> (`1,234.50 USD`), **a symbol follows the standard**: leading for `US`/`SWISS`/`INDIAN`/`PLAIN`
> (`$1,234.50`), trailing for `EUROPEAN`/`SPACE_COMMA`/`SPACE_DOT` (`1.234,56 €`). A negative amount
> keeps its minus in front of everything (`-$1,234.50`). A value that is not a number is drawn
> unchanged — a mis-typed column degrades, it never breaks the row. Money columns are numeric, so
> they are right-aligned by the rule above with no extra key.

> **Date render** (`DateFormatColumnUtils.formatCellValue`, same seam): with a non-blank `dateFormat`
> on a temporal column the stored ISO value is re-drawn through that moment.js pattern. An `Instant`
> renders at **UTC**, matching what the Date Picker form control writes, so a table never disagrees
> with the form that filled it. Textual tokens (`MMMM`, `MMM`) render in the **viewer's locale**
> (`31 декабря 2024` for a ru session). A date-only value under a pattern that wants a time gets
> start-of-day; an unparseable value is drawn unchanged. Blank `dateFormat` = the raw ISO string,
> which is what every column saved before this feature keeps doing.

> **Where the author sets these.** The column accordion in the right-hand settings panel shows the
> money block only when the picked field is numeric and the date-format picker only when it is
> temporal — the same conditional-reveal as the enum Display Field and the boolean icons. Picking a
> temporal field **prefills** `dateFormat` (`DD/MM/YYYY` for `LocalDate`, `DD/MM/YYYY HH:mm:ss`
> otherwise); ticking **Is money** prefills `currency: "$"`, `moneyFormat: "US"`, `moneyDecimals: 2`.
> Both prefills fire on the CHANGE only, never on a plain Save — a blank `dateFormat` is a
> legitimate "show the raw value" choice and must survive re-saving the panel. (With
> `nct.ui.dynaform.settings.autosave=false` there is no change event at all, so nothing is
> prefilled and the author picks every value explicitly.)
> Repointing a column at a different type scrubs the keys that no longer apply. CRUD Tree and Process
> Table offer the identical controls; the List form control carries the keys but has no UI for them
> (it does not persist a `dataClass` at all, so its boolean icons are equally dormant).

### `CrudTableFilterSettings` (element of `filterSettings[]`)

> ⚠️ The concept document `table-plugins.md` (section "Filter Controls", lines ~585-662) describes rich
> filter types (Text/Dropdown/Date/Autocomplete, `ruleIdentifier`, `key`, `displayName`, `dateFormat`
> etc.) — **those fields DO NOT exist on the `CrudTableFilterSettings` model**. The real filter model = exactly the five
> fields below. In practice `filterSettings` is almost always `[]` — real filtering is done by a standalone
> filter form (see below); the inline descriptor only carries a plain scalar default such as an `active` flag.

Example (a rare populated inline filter):
```json
{ "id": "e32f6918-4ddb-49c6-8c71-de98f4b4ed4d", "name": "Active",
  "filterField": "active", "dataClass": "java.lang.Boolean", "defaultValue": "true" }
```

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `id` | String (UUID) | Unique filter id. | yes | — | `CrudTableFilterSettings.java` |
| `name` | String | Filter control label (**plain String**, NOT localized). | yes | `null` | |
| `filterField` | String | Field of the CRUD's **filter class** (not the entity!) — `companyId`, `active`, `minPrice`. Goes into the fetch rule's `attrs`/`filter` under this key. The filter class is separate from the row DTO: the entity may have `price`, while the filter has `minPrice`/`maxPrice`. | yes | `null` | |
| `dataClass` | String (FQN) | Filter type. Controls the conversion of `defaultValue`. | yes | `null` | |
| `defaultValue` | String | Default value, stored as a string; converted per `dataClass` via `getTypedDefaultValue()`. | no | `null` |; convert |

`getTypedDefaultValue()` converts per `dataClass`: `java.lang.Boolean`/`boolean` →
`Boolean.parseBoolean`, `Integer`/`int`, `Long`/`long`, `Double`/`double`, `Float`/`float`,
`Short`/`short`; everything else stays a String.

### `ActionDto` (element of `createActions.actions[]` / `editActions.actions[]`)

This is a **dedicated** class `CrudTableActionsDto.ActionDto`, distinct from the workflow `ActionDto` from
[07-workflows-and-tasks.md](07-workflows-and-tasks.md). The CRUD `ActionDto` does **NOT** have the fields
`validationRuleIdentifiers`, `completeUserTask`, `taskId`, `onBeforeUserTaskStartRuleIdentifier`,
`onBeforeUserTaskCompleteRuleIdentifier` — those belong only to the workflow action. Do not carry them over here.
`direct` here is a primitive `boolean` (serialized as `"direct":true/false`), NOT the string `"on"/"off"`
(the strings `"on"/"off"` belong to the workflow action; `action.md` mixes both classes — don't confuse them).

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `id` | String (UUID) | Unique action id. | yes | — | `CrudTableActionsDto.java` |
| `localizedNames` | Map\<locale,String\> | Action label in the menu/breadcrumb/audit. **In practice REQUIRED** for a visible label: the CRUD `ActionDto` has NO `name` field, and `getLocalizedName` reads ONLY `localizedNames`, with no legacy fallback. An old-schema action carrying a single `name` is broken: GSON silently drops the unknown key, the label renders EMPTY. | yes | `null` |; resolve `getLocalizedName` |
| `localizedButtonNames` | Map\<locale,String\> | Label of the SUBMIT button in the form (non-direct only). Empty → falls back to `localizedNames`. | no | `null` |; resolve `getLocalizedButtonName` |
| `icon` | String | CSS class of the `pe-7s-*` icon (`pe-7s-plus`, `pe-7s-pen`, `pe-7s-trash`, `pe-7s-exapnd2`). | no | `null` | |
| `formGroupIdentifier` | String (UUID) | Form group a non-direct action leads to; the form receives URL params `group`, `settingsName`, `caller`, `actionId` and (for edit) `crudId` (`navigateToForm` `CrudTablePlugin.java`). The field's javadoc (`CrudTableActionsDto.java` "crud and crudId") is outdated — `crud` is not passed. | no (non-direct only) | `null` | |
| `direct` | boolean | `true` → execute immediately (rules + refresh), no form. `false` → navigate to a form. | no | `false` |; branching `CrudTablePlugin.java` |
| `predicateIdentifier` | String (UUID) | PREDICATE visibility rule. The action is visible only if the rule returned true for this row. Empty → always visible. | no | `null` |; eval `CrudTablePlugin.java` |
| `onBeforeStartRuleIdentifier` | String (UUID) | EXECUTION rule before opening the form / before the direct operation. | no | `null` |; run `CrudTablePlugin.java` |
| `onBeforeCompleteRuleIdentifier` | String (UUID) | EXECUTION rule before saving (form submit / direct create/update/delete). | no | `null` |; run `CrudTablePlugin.java` |
| `submitForm` | Boolean (nullable) | Non-direct: `true`/`null` → validate the form and run `onBeforeComplete`; `false` → skip validation **and** rule execution entirely (the submit button becomes a Back). `null` = `true` (`shouldSubmitForm()`). | no | `null`(=true) |; `shouldSubmitForm()` |
| `formInModal` | Boolean (nullable) | Non-direct: `true` → the form opens in a DIALOG over the table (no page navigation) and a successful submit refreshes the table in place; `null`/`false` → the classic navigation to the form group's page. Ignored for `direct:true`. | no | `null`(=false) |; `shouldOpenInModal()` |
| `modalWidth` | String | Width of that dialog — any CSS length (`"90%"`, `"400px"`), applied as `max-width` on the modal. Only read when `formInModal:true`; blank → `80%`. | no | `null`(=`80%`) | |

> **What `formInModal:true` looks like at runtime.** The list stays on screen; the form the group's
> predicates resolve to is rendered inside a dialog over it — the SAME form node, so every control, rule,
> validation and localization behaves exactly as on the form page. ⚠️ Only the FORM node is rendered:
> anything else the form's page carries (a header, a breadcrumb, sibling HTML blocks, a second plugin)
> is NOT in the dialog. If the page composes the form with context around it, that context is lost —
> either move it inside the form or leave the action on the page route. Two more consequences:
> * the buttons the form page puts on its **breadcrumb** move to the **bottom of the dialog** — the action's
>   submit button (`localizedButtonNames`), `Drafts` when the form allows them, and, while a **List** control's
>   item form is open, that item form's own Submit/Close instead;
> * a successful submit **closes the dialog and refreshes the list in place** — it does NOT navigate, so no
>   `caller` page is involved and any "return to" wiring is irrelevant for this action. Dismissing the dialog
>   (✕ / Esc) does nothing at all: no rule runs and the list is not refreshed, so an action whose
>   `onBeforeStartRuleIdentifier` already wrote something must not rely on the submit to show it.
>
> Use it for create/edit forms over a list the user wants to keep in view (a long form simply scrolls the
> dialog). Leave `formInModal` off when the form's page carries content around the form, or when a rule has to
> navigate somewhere else.

> ⚠️ **Outdated javadoc in the source.** `CrudTableActionsDto.java` (javadoc of the `direct` field)
> claims "For create: calls ICrud.create() with default/empty DTO" — this is an **outdated comment**:
> the current runtime does NOT call the built-in create/update/delete. All writes are done EXPLICITLY by the body
> of a Groovy rule (`onBeforeStart`/`onBeforeComplete`), see below. Do not rely on this javadoc.

> **Example of a non-direct action with `submitForm:false`** (open a form, change nothing) — here a
> read-only "View Stock Movement" drill-down:
> ```json
> { "id": "5c3533ec-fa69-4ca1-b8f5-78eabc9c3987",
>   "localizedNames": { "en_US": "View Stock Movement" },
>   "localizedButtonNames": { "en_US": "Back" }, "icon": "pe-7s-bottom-arrow",
>   "formGroupIdentifier": "4969525d-5bda-46d8-a8b0-49e0d8a3ea8a",
>   "direct": false, "submitForm": false }
> ```
> When the form's SUBMIT button is clicked with `submitForm:false`, the platform skips **everything**: no
> validation, no `onBeforeComplete` rule, no write — it clears the validation panel and redirects back to the
> `caller` page. The button is a Back/Cancel with the action's branding, which is exactly right for a read-only
> drill-down (`View …`); every other action leaves `submitForm` = `null` (default `true`).
> ⛔ It is **NOT** a "run the rules without saving" shape. An action that must only fire rules has to be
> `direct:true` with its rule on `onBeforeCompleteRuleIdentifier` (a direct action runs `onBeforeStart`, then
> `onBeforeComplete`, then `refresh()`). Wiring `Release`/`Post`/`Approve` as `direct:false` +
> `submitForm:false` + `onBeforeCompleteRuleIdentifier` ships a button that returns to the table and does
> nothing — import, `coverage` and `crud verify` all stay GREEN (`validate` WARNs on that exact pair but does
> not fail), and the redirect looks like success. (The remaining route — putting the work on `onBeforeStartRuleIdentifier`, which runs when the form
> initialises — carries a side effect: a row action with an `onBeforeStartRule` is treated as CREATE, so
> `crudId` becomes a parent/source id and no entity is loaded into the form.)

> **Storage direction — this decides whether the action is per-ROW or a header button, NOT just a style choice.**
> `editActions.actions[]` render in **each row's action menu** (they operate on the clicked row — its `data.get()`
> is in scope). `createActions.actions[]` are **breadcrumb buttons** (the bar above the table) that run with **no
> selected row**.
> So **any action that operates on a specific record — `View Details`, `Edit`, `Delete`, `Post`, `Cancel`,
> `Adjust`, `Release`, and every read-only-log `View Details` — MUST go in `editActions`**; only "new-record" /
> table-wide actions (a bare `Create`) belong in `createActions`. A `View Details` placed in `createActions` has
> no row context and **does not appear as a row action** (a real gotcha: it silently "isn't there"). A read-only
> log or ledger screen (stock movements, payment postings, audit entries) therefore carries its `View Details` in
> `editActions` (`direct:false`, `submitForm:false`) — mirror that. The runtime for direct: first (if present) `onBeforeStartRule`,
> then `onBeforeCompleteRule`, then `refresh()` (`CrudTablePlugin.java`, method `executeEditAction`). There
> is NO built-in `create/update/delete` call — all writes are done EXPLICITLY by the body of a Groovy rule.

### `CrudTableImportSettingsDto` (`importSettings`)

> ⚠️ `importSettings.enabled=true` is rare — most projects never switch Excel import on, so you will seldom find
> a populated example to copy. Everything below is
> documented from the DTO + code (`CrudTableImportSettingsDto.java`, `CrudTablePlugin.java`).

Example (Import disabled — the typical default):
```json
{ "enabled": false, "localizedButtonNames": {}, "actions": [] }
```

| Field | Type | Meaning | Required | Default | Backing |
|---|---|---|---|---|---|
| `enabled` | boolean | Master toggle. `false` → the Import button in the breadcrumb is hidden. | no | `false` | `CrudTableImportSettingsDto.java` |
| `localizedButtonNames` | Map\<locale,String\> | Import button label per locale; fallback → `"Import"`. | no | `{}` |; resolve `getLocalizedButtonName` |
| `buttonIcon` | String | `pe-7s-*` icon of the Import button (chosen via `Pe7sDropDownField`). | no | `null` | |
| `visibilityPredicateIdentifier` | String (UUID) | PREDICATE — who to show the button to. Empty → everyone. | no | `null` |; eval `shouldShowImportButton` `CrudTablePlugin.java` |
| `duplicateDetectionPredicateIdentifier` | String (UUID) | PREDICATE detecting row duplicates on import. Empty → no dedup. | no | `null` | |
| `duplicateAction` | `DuplicateAction` enum | What to do if the dedup predicate returned true. Meaningful only when `duplicateDetectionPredicateIdentifier` is set. | no | `null` |; runtime map `CrudTablePlugin.java` |
| `actions` | `CrudTableImportActionDto[]` | Pre-import rule bundles: 0 → no rules; 1 → auto; N\>1 → selection dialog (`ImportActionChoiceDialog`). | no | `[]` | |

`DuplicateAction` (enum, `DuplicateAction.java`), **all values**: `OVERRIDE` (update on the found
row) · `IGNORE` (skip, counter `skippedRows`) · `DUPLICATE` (`create` anyway) · `ASK` (pause the worker
+ `ImportDuplicateDecisionDialog`, only the import owner responds). At runtime it is mapped
1:1 to `DuplicateActionType.valueOf(name())` (`CrudTablePlugin.java`).

`CrudTableImportActionDto` (`CrudTableImportActionDto.java`):
`{ id, localizedNames: Map, ruleIdentifiers: String[] }` — a named set
of EXECUTION rules (by UUID), run before the import starts.

> **The Excel-header → CRUD-field mapping is stored SEPARATELY**, NOT in `model`. The runtime writes it via
> `getContent().setJsonProperty("importMapping", mapping)` (`CrudTablePlugin.java`) +
> `contentService.save`. Since `setJsonProperty(name, value)` puts the JSON into the STRING slot
> `getProperties().put(name, ...)` (`ContentDomain.java` → `setProperty`), it lands
> as **`properties.importMapping.stringValue`** — the same envelope as `properties.model`
> (`ContentProperty` of type STRING, JSON inside `stringValue`), NOT as a separate top-level key.
> The content = `ImportMappingDto` `{ headerToField: Map, ignoredHeaders: Set, lastSavedAtEpochMillis }`
> (`ImportMappingDto.java`). **An `importMapping` key does not belong in a hand-built export** — it is user
> data, written when a file is uploaded at runtime, not carried
> with the page template. When building a page, we omit this slot.

---

## Default actions: Create / Edit / Delete + their rules

The **"Create Default Actions"** button in one click does: (1) a `True` predicate rule, (2) a form group
`"<crudName> Forms"` + a form `"<crudName> Form"` + a True mapping, (3) three EXECUTION rules, (4) three
actions. Orchestration — `CrudDefaultActionsService`; assembling the actions —
`CrudTableSettingsControlPanel.finalizeDefaultActions`.

**Rule names** (`CrudTableSettingsControlPanel.java`) — the convention `"<crudName> Action <Kind>"`:

| Kind | Rule name | Body (Groovy) | Builder |
|---|---|---|---|
| Create | `<crudName> Action Create` | `def created = context.<ctx>.<alias>.service.create(context.<ctx>.<alias>.data.get())`<br>`context.<ctx>.<alias>.data.put(created)` | `CrudDefaultActionsService.buildCreateScript(contextAlias, crudAlias)` |
| Update | `<crudName> Action Update` | `context.<ctx>.<alias>.service.update(context.<ctx>.<alias>.data.get())` | `buildUpdateScript(contextAlias, crudAlias)` |
| Delete | `<crudName> Action Delete` | `context.<ctx>.<alias>.service.delete(context.<ctx>.<alias>.data.get().id)` | `buildDeleteScript(contextAlias, crudAlias)` |

Here `<ctx>` = `context.getAlias()` (e.g. `catalog_context`), `<alias>` = the short CRUD alias. All three are
`EXECUTION_RULE` / `executor=GroovyExecutionRule`, `contextIdentifiers=[<contextIdentifier>]`,
`status=ACTIVE`, `description="Auto-generated by Create Default Actions"`
(`CrudDefaultActionsService.java`).

A delete rule as stored (id `f8240612-…`):
```json
{ "name": "Delete — Product Categories Cruid", "ruleType": "EXECUTION_RULE",
  "executor": "GroovyExecutionRule", "contextIdentifiers": ["871f974f-e775-401a-adfc-e822110f3b99"],
  "rule": { "ruleScriptStr": "context.catalog_context.product_categories_cruid.service.delete(context.catalog_context.product_categories_cruid.data.get().id)" } }
```
(⚠️ the name here is `Delete — Product Categories Cruid` (with a dash) — an older naming convention you may still
meet in an existing project; the button's current convention is `<crudName> Action Delete`.
The body is identical.)

**The three assembled actions** (`finalizeDefaultActions`):

| Action | List | `direct` | `icon` | `formGroupIdentifier` | `onBeforeCompleteRuleIdentifier` | name |
|---|---|---|---|---|---|---|
| Create | `createActions` | `false` | `pe-7s-plus` | id of the new form group | Create rule | `Create <crudName>` |
| Edit | `editActions` | `false` | `pe-7s-pen` | id of the new form group | Update rule | `Edit <crudName>` |
| Delete | `editActions` | `true` | `pe-7s-trash` | — | Delete rule | `Delete <crudName>` |

The `localizedButtonNames` of each = a **copy** of `localizedNames` (so the form's submit
button is not empty). Clicking the button again removes the previous default actions by name before adding new ones
(`removeDefaultActions`, `CrudTableSettingsControlPanel.java`) — so as not to clone them.

## Fetch rule (the row source rule)

`findRuleIdentifier` points to an EXECUTION rule `Find — <crudName>` (auto-named from
`CrudDataRuleServiceImpl.java`, `ensureFindRule`) returning a page. The body is generated by
`buildFindScript(alias)` (`CrudDataRuleServiceImpl.java`) — the exact text (here for the rule
`Find — Inventory Count`, `contextIdentifiers: []`):

```groovy
// Pagination + filter values arrive from the table via attrs (Jackson JsonNode).
def filter = [
    'rowsInPage': attrs?.get('rowsInPage')?.asInt(),
    'pageNumber': attrs?.get('pageNumber')?.asInt()
]
// Forward any other filter values (filter form + configured filters):
attrs?.each { k, v ->
    if (k != 'rowsInPage' && k != 'pageNumber' && v != null && !v.isNull()) {
        filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText())
    }
}
// Add your own computed params here, e.g.:
//   filter['assignedTo'] = service.security.user().id
return service.crud.inventoryCount.find(filter)
```

⚠️ The generated comment suggests `user().id`; prefer `user().email` as the ownership key — see the warning
under "Who sees which rows" below.

### ⛔ Who sees which rows — decide it HERE, never in the browser

This rule is the **only** place row visibility can be decided. An action visibility predicate hides a *button*;
it does not remove a row. Hiding rows in JS does not remove them either — they were already sent to the browser.
The PRD sentence "*the clerk sees only their own, the manager sees all and can filter by clerk*" is built like
this, appended to the generated body above:

```groovy
// … generated pagination + attrs forwarding above …
if (!service.security.hasAnyRoleGroup('<Manager>')) {
    filter['ownerEmail'] = service.security.user().email   // a clerk: OVERWRITE what the page sent
}
return service.crud.<alias>.find(filter)
```

Four rules:

1. **Write the scope AFTER the `attrs?.each` forwarding.** That loop copies in whatever the page submitted, so a
   scope written before it can be widened by a crafted request. Last write wins — make it yours.
2. **The manager's optional "filter by clerk" is just another filter-form field**; the clerk's own scope must
   never be expressible as one.
3. ⛔ **The scoping key is DROPPED unless the SQL declares it** — exactly like a filter-form key. On a dynamic
   CRUD it must be a declared `parameters[]` entry AND used in a `:name` predicate in **BOTH** `findAll` **and**
   `count` (see "A filter key … is DECORATIVE until the SQL declares the key" below). Get this wrong and the
   list returns **every** row with no error, no warning and a clean `validate` — the worst failure shape there is.
   Verify it live: sign in as a non-manager and count the rows.
4. **A column the viewer may not see** (a cost/salary field) is the same problem one level down: leave it out of
   the projection, don't hide the cell. Per-column role gating does **not** exist on `crud.table.plugin` —
   `CrudTableColumnSettings` has no predicate — so the supported answers are a second, group-gated screen (or
   tab) carrying the extra column, or a hand-built table in an HTML component
   ([24c](24c-html-data-tables-and-paging.md)) whose rule projects the field only for permitted viewers.

> ⚠️ `service.security.user()` is not the same in every kind of rule. In a FETCH rule the platform hands the
> executor only the signed-in principal, so `user().id` and `user().email` both carry that principal; in an
> ACTION predicate / form rule `user().id` is instead the platform's internal user-row id. **Use the email as
> the ownership key on both sides** — an ownership column filled with `user().id` from a form rule can never
> match `user().id` here, and the symptom is an always-empty list with no error.
> ⚠️ Smoke-test `hasAnyRoleGroup` live before you build a permission model on
> it — see [24](24-html-component-studio.md) §9a.

> **NB — a fetch rule ≠ a choices rule.** A table/tree fetch rule returns **RAW rows** (a `PageResult`) on
> purpose. A dropdown/autocomplete **choices** rule is the OPPOSITE: it MUST convert rows to option pairs as its
> last statement — `return service.global.conversion.toSelectOptions(list,"<key>","<display>")` (localized CRUD:
> `toSelectOptionsLocalized`) / `toAutoCompleteOptions(list,"<display>")`. **Never** return a raw `find`/`findAll`
> entity list from a choices rule (the picker shows "No results found" AND the Show Nav toggle disappears). Full
> recipe + naming table: [02-form-controls-reference.md §4a](02-form-controls-reference.md).

The rule is **context-free** (`contextIdentifiers: []`), it uses `service.crud.<alias>.find(...)`
directly. Pagination (`rowsInPage`/`pageNumber`), all `filterField` values from the inline `filterSettings` **and**
values from a standalone `dynaform.filter.form.plugin` (see "Standalone Filter Form" below) arrive in
`attrs` — they are transparently forwarded by the `attrs?.each { … }` loop above. Returns a `PageResult` (exactly 4 fields: `content`/`pageNumber`/`totalElements`/`totalPages`).
For a dynamic CRUD `service.crud.<alias>.find` resolves to the GROOVY method `find` from `dynamic-cruds.json`
(count+findAll paging, see [11](11-business-logic-dynamic-crud.md)); for a static one — to the Java `@Crud`
(see [11](11-business-logic-dynamic-crud.md) about static vs dynamic).

`crud.tree.plugin` uses the analog `buildFindByParentScript` → `Find children — <crudName>` via
`service.crud.<alias>.findByParent(...)` (`CrudDataRuleServiceImpl.java`), see
[05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md).

## Standalone Filter Form (filter panel above the table)

Besides the inline `filterSettings` (see above — 5 fields, they live **inside the table's own `model`**), there is
a **second, independent** filtering mechanism: a separate plugin `dynaform.filter.form.plugin`, which
renders a full panel of filter controls **above** the table. This is NOT `filterSettings`:

| | inline `filterSettings` | standalone filter form |
|---|---|---|
| Where it lives | in `crud.table.plugin` → `properties.model.filterSettings[]` | a separate sibling node `dynaform.filter.form.plugin` |
| What it is | a 5-field descriptor (`id/name/filterField/dataClass/defaultValue`) | a container with real form controls + a submit button |
| Config slot | part of the table's `model` | `properties.filterFormModel` (`FilterFormDto`; empty `{}` or `{name,description,waitSelector}`) — see `FilterFormPlugin.java` |
| How values reach the fetch rule | the table puts them in `attrs` by `filterField` | on submit-button click it reads `provider.getFilterValues()` and triggers a refresh → values into the same `attrs` |

**Node structure — the layout is INLINE HTML with `<plugin>` tags, matched to child nodes by SYMBOLIC id.**
The filter form is a **sibling** of `crud.table.plugin`
under a shared parent `nct.parsis.plugin`. Inside `filter.parsis`, an `nct.html.plugin` holds a Bootstrap **row**
whose inline `<plugin id="cellN" name="nct.parsis.plugin">` tags reference cell `nct.parsis.plugin` nodes; each
cell is another `nct.html.plugin` whose inline `<plugin id="field" …>` / `<plugin id="form-label" …>` /
`<plugin id="button" …>` tags reference its child control/label/button nodes:

```
nct.parsis.plugin                              ← shared page content slot
├── dynaform.filter.form.plugin                ← filter panel (properties.filterFormModel; the plugin sets reuseItems)
│   └── nct.parsis.plugin  id="filter.parsis"   ← inner drop container (MUST be this literal id)
│       └── nct.html.plugin  html=<div class="row"><div class="col-md-4"><plugin id="first"  name="nct.parsis.plugin"></plugin></div>…<plugin id="second"…><plugin id="third"…></div>
│           ├── nct.parsis.plugin  id="first"    ← a CELL (id matches the row's <plugin id="first">)
│           │   └── nct.html.plugin  html=<div class="mb-3"><plugin id="form-label" name="nct.label.plugin"><prop name="text" .../><prop name="tagName" value="label"/></plugin><plugin id="field" name="dynaform.form.rimm.drop.down.field.plugin"></plugin></div>
│           │       ├── nct.label.plugin              id="form-label"
│           │       └── dynaform.form.*.field.plugin  id="field"   (settings.filterKey = …)
│           ├── nct.parsis.plugin  id="second"   → same shape, another field
│           └── nct.parsis.plugin  id="third"    → the SUBMIT cell:
│               └── nct.html.plugin  html=<div class="mb-3"><plugin id="form-label" …></plugin><div style="margin-top:8px;"></div><plugin id="button" name="dynaform.filter.submit.button.plugin"></plugin></div>
│                   ├── nct.label.plugin                     id="form-label"
│                   └── dynaform.filter.submit.button.plugin id="button"   (settings {"buttonName":"Filter"})
└── crud.table.plugin                          ← the table itself (its findRule reads values from attrs)
```

> ⛔ **The `<plugin id="X">` in an `nct.html.plugin`'s `html` MUST equal the child node's `identifier`** — that is
> how the CMS binds the inline placeholder to the real node. The symbolic ids are literally `field`, `form-label`,
> `button`, and the cell ids (`first`/`second`/…). If you generate a filter form by CLONING and then regenerate
> node identifiers, you break these HTML→node references and **the controls render NOTHING** (empty filter — the
> exact "no fields in the filter" bug). Either keep the symbolic ids, or author the layout HTML and node ids
> together. The label **text** lives in the HTML `<prop name="text" …>`, not on the label node. The cheapest way
> to build one is to copy an existing filter subtree and swap only the `field` control `settings` + the label
> `<prop name="text">`, keeping every symbolic id.
>
> ⚠️ **On a greenfield build there is nothing to copy.** The bundled `empty` baseline contains **no**
> `dynaform.filter.form.plugin` and no filter-control subtree (its `virtualPlugins` palette does carry a
> "Form Submit Button" and the label-field fragments, which is where the shapes come from). So the first filter
> form is hand-authored: `node add` the `dynaform.filter.form.plugin`, its inner
> `nct.parsis.plugin identifier="filter.parsis"`, the three column slots, the `nct.html.plugin` cells and the
> field/label/button nodes — and hand-write the two `properties.html` strings that reference them
> ([24b](24b-html-composition-and-plugin-tags.md) gives the `<plugin>` grammar and the property JSON shape;
> there is no toolkit command for `properties.html`). Keep the symbolic ids exactly as shown above; once one
> filter form exists in your project, every later one is a copy of it.
>
> ⛔ **When you CLONE a subtree from another export, NULL the persisted `id` on EVERY node** (and give each a
> fresh `uniqueIdentifier`; regenerate non-symbolic `identifier`s). The `id` is a per-project DB primary key —
> the source export's nodes carry that project's real ids, and copying them makes the importer **drop the
> node** (the "no filter form anywhere after import" bug), or collide when the same template is cloned N times.
> New content nodes must have `id=null` so the platform assigns one on import (just like `page add`/`node add`
> output). `mrjun.py validate` now ERRORs on duplicate content ids and WARNs on a form/filter subtree with a
> non-null id.

Key facts (verified against the code):

- `FilterFormPlugin extends NctBasePlugin<FilterFormDto>` (**not** `FormPlugin` — no ContextDataDto, no
  scopes/form groups). The filter values are a plain `Map<String,Object> filterValues`, **transient**,
  not persisted (`FilterFormPlugin.java`). Its own config slot is `properties.filterFormModel`
  (`getJsonProperty("filterFormModel", …)`), NOT `settings`/`model`.
- The filter controls are ordinary `dynaform.form.*.field.plugin` (`text`/`dropdown`/`datepicker`/…). Their
  binding field is **`filterKey`** in the control's `settings` (`FilterControlSettings.java`;
  `BaseFormControl` reads/writes `provider.getFilterValues().get(getSettings().getFilterKey())`)
  — NOT `filterField` (that is the inline `filterSettings` field) and NOT `key` (that is the
  enum key-field). `filterKey` is the value key in `filterValues`. Controls live in the **inner**
  `nct.parsis.plugin` whose identifier **must be exactly `filter.parsis`** (`FilterFormPlugin.java`
  the plugin creates this drop container by that literal id — with `mrjun.py` use `node add --identifier filter.parsis`).
- `dynaform.filter.submit.button.plugin` (slot `properties.settings` = `{"buttonName":"Filter"}` + an optional
  `waitComponentIdentifier` — the `uniqueIdentifier` of an `IRefreshable` sibling to overlay a loading indicator on
  during submit, `FilterSubmitButtonSettings.java`, picked via a component chooser in its settings panel)
  on click finds the parent `IFilterFormProvider` (= FilterFormPlugin),
  reads `getFilterValues()` and triggers the `onFilterSubmit(filterValues)` event
  (`FilterSubmitButtonPlugin.java`) → the table re-queries rows, values arrive in the fetch rule's `attrs`
  under the same keys.
- The table's fetch rule is **already** ready to accept these values: the loop `attrs?.each { k, v -> … filter[k] = … }`
  (in the generated fetch-rule listing above, §"Fetch rule") transparently forwards any keys from the filter
  form into the `filter` map.

**Minimal how-to.**
1. Into the page's shared `nct.parsis.plugin` put two sibling nodes: `dynaform.filter.form.plugin` and, below it,
   `crud.table.plugin` (an ordinary CRUD table).
2. Inside the filter form (its inner `nct.parsis.plugin`) add the needed `dynaform.form.*.field.plugin`
   as filter controls + one `dynaform.filter.submit.button.plugin` (`settings: {"buttonName":"Filter"}`).
3. Set each control's **`filterKey`** to the name of the parameter the fetch rule expects (it forwards every
   key via `attrs?.each` anyway, so `filterSettings` in `model` is OPTIONAL when a filter form is present —
   it only supplies inline defaults). Don't duplicate the two paths.

> ⚠️ **A dropdown/autocomplete filter control still needs an option SOURCE.** `filterKey` only binds the
> *chosen* value into `filterValues`; it does **not** populate the options. A CRUD-backed filter dropdown needs
> either an `enumValues` snapshot (for a static enum) or a **choices rule that ENDS in
> `service.global.conversion.toSelectOptions*`/`toAutoCompleteOptions`** (searchable → the `acFindAllBy<X>Like`
> pipeline). A raw `service.crud.<alias>.findAll(...)` choices rule renders "No results found" and hides Show Nav.
> Full recipe: [02-form-controls-reference.md §4a](02-form-controls-reference.md); see also
> [18-existing-schema-to-dynamic-wiring.md §2](18-existing-schema-to-dynamic-wiring.md).

> **Filter-form binding across table types — one filter form drives EVERY table on its page.** The submit
> button fires `onFilterSubmit` as a **page-wide broadcast** (`EventUtils.java` → `page.visitChildren`),
> so the form and its tables only need to be on the **same page**, not siblings. What `filterKey` must equal
> depends on the table it feeds:
>
> | Table plugin | `filterKey` must equal | flows into |
> |---|---|---|
> | `crud.table.plugin` | the CRUD **filter-class field name** (`branch`, `status`, `customerName`) — raw, no prefix | fetch rule `attrs` → `service.crud.<alias>.find(filter)` |
> | `crud.tree.plugin` | same (a filter-class field); do NOT reuse the `parentFilterFieldExpression` key | `additionalFilter` → `findByParent(filter)` |
> | `process.table.pluin` | the **exact `{token}`** inside the table's `filterExpression`, **prefix included and NOT stripped** (`{filter_branch}` ⇒ `filterKey:"filter_branch"`) | `ProcessFilter.filterValues` → the filter expression (see [05](05-crud-tree-and-process-table.md)) |
>
> So a control with `filterKey:"branch"` satisfies a crud table filtering on `branch`, but does **NOT** satisfy
> a process expression `{filter_branch}` — that needs `filterKey:"filter_branch"`.

### ⛔ ANY filter key — from a filter form OR computed in the fetch rule — is DECORATIVE until the SQL declares it

This is the step that gets skipped, and it fails **silently** — the control renders, the user types, the
submit button flashes, and the table returns exactly the same rows.

The fetch rule needs no edit: the auto-find wrapper forwards the whole filter map. But
`DynamicMethodExecutor` builds its parameter values **only from the method's declared `parameters[]`** and
substitutes a `:name` **only when that name is declared**. An undeclared key evaporates between the form and
the SQL — and this is true of **every** key in that map, including one your fetch rule computed itself (a
role scope, a tenant/branch restriction), not just the ones a filter form submitted. So for every filter key,
edit **BOTH** methods of the CRUD:

| Method | What to add | Why both |
|---|---|---|
| `findAll` | the `parameters[]` entry **and** a `:name` predicate | it returns the rows |
| `count` | the same | the auto-find wrapper runs findAll and count with the **same** map. Filter one and not the other and the pager lies: page 1 looks right, the page count is the unfiltered total, and page 2 is empty |

Use the canonical optional-filter predicate from
[11 §"Optional filters in SQL"](11-business-logic-dynamic-crud.md) — `COALESCE`, never
`(:x IS NULL OR col = :x)` and never a bare `col = :x`, both of which throw *"could not determine data type
of parameter $1"* in exactly the unfiltered case. Prefer the `IS NOT DISTINCT FROM` form so rows whose column
is NULL survive an unfiltered render.

Two arithmetic traps that follow from this:

- **Never leave `count` with exactly ONE declared filter parameter.** The single-argument map is unpacked by
  declared parameter NAME automatically when the method declares 2+ parameters; with exactly ONE declared
  parameter the executor unpacks only if the map actually carries that name (snake_case or camelCase) —
  otherwise it falls back to positional binding and jams the WHOLE map into that one slot (opaque "value too
  long" / type errors). And the generated fetch rule forwards a filter key **only when its value is non-null**,
  so on the unfiltered first render the map is just `{rowsInPage, pageNumber}` and a `count` whose only
  parameter is a filter takes the positional branch. Two filters per table keeps you clear; with one, add a
  second (paging) parameter so the name is always matched.
- **Never set `ruleIdentifier` on a `find` method to "make filtering work".** A blank `ruleIdentifier` is the
  auto-find sentinel; filling it flips the executor onto the Groovy path, where the exported `find` script
  typically calls `count()` with no arguments — an unfiltered total against filtered rows.

### Placement: one form per rendered container, above its table

- The binding is by **Wicket page**, not parentage — but each table does `filter = map`, a wholesale
  **replacement**, so **two filter forms on one page clobber each other**. One form per container.
- **A tab pane is a hard isolation boundary.** `nct.tab.plugin` materialises only the ACTIVE pane, so a table
  in an inactive pane is not in the component tree: it is never filtered and loses its filter on tab switch.
  **Every tabbed table needs its own filter form INSIDE its own pane** — a single form above the tab strip is
  always wrong.
- A parsis renders children ascending by `order`, so give the form a **lower `order`** than its table.
  Renumber the siblings; do not rely on ties or negative orders.

## Visibility predicate (per-row)

For each row the runtime evaluates ALL distinct non-empty `predicateIdentifier` values in a single call to
`executePredicatesWithCrudContext` (plural), which loads the FULL entity by id and substitutes it into
`context.<ctx>.<alias>.data` (`CrudTablePlugin.java`, method `evaluatePredicates` — distinct
via `!predicateIds.contains(...)`; `contextIdentifier` empty → fallback to `crudAlias`).
A single predicate used by several
actions (like `7fcdc152-…` for Edit and Start above) is evaluated once per row.

Example predicate (`7fcdc152-…`, `Inventory Count Action Can Edit`):
```groovy
context.rimmContext.inventoryCount.data.get().status == 'DRAFT'
```
PREDICATE / `GroovyPredicate`, `contextIdentifiers: ["77cd568d-…"]`. The predicate MUST return a
Boolean via an explicit `return`/an expression that yields a Boolean — see
`ExecutionRuleTemplate` in [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).

✅ **This is a real gate, not decoration.** The check is re-run server-side in the execute endpoint itself
(`executeEditAction` → `isActionVisibleForEntity`), fail-closed: a crafted/stale request naming a hidden action is
rejected. A **form-based** action is re-checked a second time, **at submit**: the form's submit path re-evaluates
the predicate, taking its id from the saved CRUD settings (not from the request) and matching the context by
whether an entity id is present, and blocks with "This action is not available." on `false` **or on any error**.
So a form URL reached directly with someone else's row id does not slip through.

## Action lifecycle

Checked against `executeEditAction` (`CrudTablePlugin.java`):

- **Form-based** (`direct:false`): click → visibility predicate → `onBeforeStartRule` (before opening) →
  navigate to the form group `formGroupIdentifier` → the user submits → **the visibility predicate is
  re-evaluated server-side, fail-closed** → (if `submitForm≠false`) form validation → `onBeforeCompleteRule`
  (before persist) → write by the rule → audit → `refresh()`. With `submitForm:false` the submit does **none**
  of that — not the validation and not the rule; it clears the message panel and redirects back.
- **Direct** (`direct:true`): click → re-check visibility (fail-closed) → `onBeforeStartRule` (opt.) →
  `onBeforeCompleteRule` (opt.) → audit (`crudAuditService.logDirectAction`, before/after entity + traceId)
  → `refresh()` of the whole table. No form.

A visibility predicate error → the action is hidden (`nctError` + `return false`). An error / `!isSuccess()` of the
`onBeforeStart`/`onBeforeComplete` rule → `nctError` for each and abort without write/refresh.

> **⛔ The submitted values arrive on the ROW, not in the attrs.** A form opened from a table action is bound to
> this table's CRUD (every control on it — see [02](02-form-controls-reference.md) §Where the value LANDS), so
> the `onBeforeCompleteRule` reads what the user typed from `context.<ctx>.<alias>.data.get()`. A rule that reads
> the same field with `context.data.getAttr("<field>")` gets **null on every submit**, and nothing tells you:
> the rule hands the CRUD method a null for that field, `COALESCE(NULLIF(:x,''), x)` keeps the old value, the form redirects
> and the toast says the action succeeded — while the record did not change. Live it looks like a permission or
> a status-guard problem, which is why `validate` errors on it offline.
>
> When the same form group is ALSO wired to a workflow task (offering one decision from both the worklist and
> the table row), read **both**, attrs first — the helper is in
> [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).

---

## How to construct from scratch (recipe)

Goal: a dynamic-CRUD table for `<entity>` in the context `<ctx>` (`contextIdentifier=<ctx-uuid>`) with
standard Create/Edit/Delete. Substitute your own names throughout: `<entity>` is the CRUD alias exactly as it
appears in `dynamic-cruds.json`, `<ctx>` the context alias, `<Entity>` its human-readable form. Every
`localized*` map below shows **two** locales — write **one key per entry in `tenant.json.locales`**, whatever
your project's set is ([20](20-localization.md)).

1. **The CRUD + context** already exist (see [11](11-business-logic-dynamic-crud.md) and
   [08](08-groovy-rules-and-context.md)); we know the short `crudAlias=<entity>`, the context alias `<ctx>`,
   and its UUID.

2. **Fetch rule** — add to `rep-objects.json.rules[]` an object with
   `ruleType=EXECUTION_RULE`, `executor=GroovyExecutionRule`, `name="Find — <Entity>"`,
   `contextIdentifiers: []`, `rule.ruleScriptStr` = the body of `buildFindScript("<entity>")` verbatim
   (replacing `inventoryCount` with `<entity>` in the last line). Remember its `identifier` →
   `findRuleIdentifier`. (It can be omitted: on the first render the plugin creates it itself,
   `CrudTablePlugin.java`, and writes it back into `model`.)

3. **True predicate** — if not present yet: an object in `rep-objects.json.rules[]` with `name="True"`,
   `ruleType=PREDICATE`, `executor=GroovyPredicate`, `rule.ruleScriptStr="return true"`
   (⚠️ exactly `return true`, not bare `true`).

4. **Three EXECUTION rules** in `rep-objects.json.rules[]` (`executor=GroovyExecutionRule`,
   `contextIdentifiers=["<ctx-uuid>"]`):
   - `"<Entity> Action Create"` → `def created = context.<ctx>.<entity>.service.create(context.<ctx>.<entity>.data.get())\ncontext.<ctx>.<entity>.data.put(created)`
   - `"<Entity> Action Update"` → `context.<ctx>.<entity>.service.update(context.<ctx>.<entity>.data.get())`
   - `"<Entity> Action Delete"` → `context.<ctx>.<entity>.service.delete(context.<ctx>.<entity>.data.get().id)`
   Remember their UUIDs.

5. **Form group + form + True mapping** — see [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md).
   Get the `formGroupIdentifier` of the group `"<Entity> Forms"`. The form is built from form controls
   ([02](02-form-controls-reference.md)); they can be generated with "Generate fields from CRUD"
   ([03](03-generate-fields-from-crud.md)).

6. **The `crud.table.plugin` node** in the content tree (see the node shape in [01](01-content-model-and-pages.md)):
   `pluginName="crud.table.plugin"`, and `properties.model.stringValue` = the model JSON string:

```json
{
  "contextIdentifier": "<ctx-uuid>",
  "crudAlias": "<entity>",
  "columnSettings": [
    { "id": "<uuid>", "localizedNames": { "en_US": "Title", "hy_AM": "Վերնագիր" }, "fieldExpression": "title", "dataClass": "java.lang.String" }
  ],
  "filterSettings": [],
  "createActions": { "actions": [
    { "id": "<uuid>", "localizedNames": { "en_US": "Create <Entity>", "hy_AM": "<Create translation>" },
      "localizedButtonNames": { "en_US": "Create <Entity>", "hy_AM": "<Create translation>" }, "icon": "pe-7s-plus",
      "formGroupIdentifier": "<formGroupIdentifier>", "direct": false,
      "onBeforeCompleteRuleIdentifier": "<createRuleId>" } ] },
  "editActions": { "actions": [
    { "id": "<uuid>", "localizedNames": { "en_US": "Edit <Entity>", "hy_AM": "<Edit translation>" },
      "localizedButtonNames": { "en_US": "Edit <Entity>", "hy_AM": "<Edit translation>" }, "icon": "pe-7s-pen",
      "formGroupIdentifier": "<formGroupIdentifier>", "direct": false,
      "onBeforeCompleteRuleIdentifier": "<updateRuleId>" },
    { "id": "<uuid>", "localizedNames": { "en_US": "Delete <Entity>", "hy_AM": "<Delete translation>" },
      "localizedButtonNames": { "en_US": "Delete <Entity>", "hy_AM": "<Delete translation>" }, "icon": "pe-7s-trash",
      "direct": true, "onBeforeCompleteRuleIdentifier": "<deleteRuleId>" } ] },
  "findRuleIdentifier": "<findRuleId>",
  "rowsPerPage": 15
}
```

   This string is placed into `properties.model.stringValue` (JSON-escaped inside `branches.json`);
   the `properties.model` slot also carries `"key":"model"`, `"propertyType":"STRING"`,
   `"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel"`.

7. **Custom direct action** (e.g. "Start" visible only for a status): into
   `editActions.actions[]` add `{ id, localizedNames, localizedButtonNames, icon, "direct": true,
   "predicateIdentifier": "<predId>", "onBeforeCompleteRuleIdentifier": "<startRuleId>" }` —
   without `formGroupIdentifier`. Separately create a PREDICATE rule of the form
   `context.<ctx>.<entity>.data.get().status == 'DRAFT'` and an EXECUTION rule for the action.
   A single predicate can be reused by multiple actions (see Edit+Start in the `inventoryCount` example).

8. **DONE-WHEN — the settings mirror exists.** Every table node needs one `rep-objects.json.settings[]` object
   `{ "type":"CrudTable", "name":"<node.uniqueIdentifier>", "content": <the SAME model> }` plus the
   `AbstractSecuredDto` housekeeping keys every `settings[]` object carries (`identifier`, `realmName`,
   `clientName`, `creationTime`, `modificationTime`, `deleted:false`, `message`/`errors`/`id` all `null`).

   ⛔ **Do not write it by hand — let the toolkit do it.** Place the node with
   `node add --parent <slot> --plugin crud.table.plugin --name "<Screen>"`, then write its config with
   `node set-model <node-id> --json @model.json`: `set-model` (and `patch-model`, and `locale fill`) create or
   update the mirror for you, with the right `type`, `name` and — critically — `content` as a JSON **object**.
   The one failure mode you cannot recover from cheaply is `content` written as a *string*: it aborts the entire
   REPORT import with a Jackson error, leaving sources unsaved and the DB unrestored
   ([19](19-build-decision-procedure.md) Phase 14). `validate` ERRORs on it, and `node add --model` alone leaves
   the mirror missing altogether. The shape above is documented so you can *read* an export — not so you can
   type it.

   The join key is `setting.name == node.uniqueIdentifier` (§Export shape). Every `crud.table.plugin` node must
   have exactly one matching `type:"CrudTable"` setting by `uniqueIdentifier`.
   Skipping this leaves the table rendering but makes every non-direct Create/Edit action a form that loads
   nothing and persists nothing (§Export shape).
   The invariant is **directional** — every node needs a setting, but the reverse is NOT required: a project that
   has been edited for a while carries **orphan** settings with no backing node (leftovers of deleted nodes),
   and the importer tolerates them. For MODIFY-FILLED edits the same rule
   applies in reverse: when you change a node's `model`, patch the matching `settings[].content` too (and when you
   delete a node, dropping its setting is good hygiene, not a hard requirement).

The resulting render (`CrudTablePlugin.html`): `<div class="row crud-table-plugin"> … <table class="mb-0
table table-hover">` with `<th>` per column, `<tr>` per row and a per-row `<div class="dropdown d-inline-block">`
action menu.

## Icons (`pe-7s-*`)

The icons are Pixeden Stroke 7 (`pe-7s-*`).
Defaults: create → `pe-7s-plus`, edit → `pe-7s-pen`,
delete → `pe-7s-trash`.

Action-oriented: `pe-7s-check` (approve/submit) · `pe-7s-close` / `pe-7s-close-circle` (reject/cancel) ·
`pe-7s-plus` (create/add) · `pe-7s-pen` / `pe-7s-edit` (edit) · `pe-7s-trash` (delete) ·
`pe-7s-diskette` (save) · `pe-7s-refresh-2` (refresh) · `pe-7s-repeat` (retry) · `pe-7s-file` (document) ·
`pe-7s-mail` (send) · `pe-7s-user` (assign) · `pe-7s-config` (settings) · `pe-7s-search` (search) ·
`pe-7s-right-arrow` / `pe-7s-angle-right` (next) · `pe-7s-upload` / `pe-7s-cloud-upload` (export/upload) ·
`pe-7s-download` (import) · `pe-7s-copy-file` (clone) · `pe-7s-rocket` (page menu) · `pe-7s-look` ·
`pe-7s-info` / `pe-7s-attention` · `pe-7s-note` / `pe-7s-note2` / `pe-7s-comment` · `pe-7s-link` ·
`pe-7s-back` · `pe-7s-keypad`.
Bootstrap button styles: `btn-info` (blue) · `btn-success` (green) · `btn-warning` · `btn-danger` (delete) ·
`btn-secondary` (default in the row menu).

> ⚠️ **Some icon names are misspelled in the icon set itself** — `pe-7s-exapnd2` (exactly so). Copy the string
> from the icon set / an existing node, don't "fix" it.

## Gotchas

- **The property key is `model`, NOT `settings`.** Form controls put their config in
  `properties.settings.stringValue`; `crud.table.plugin`/`crud.tree.plugin`/`process.table.pluin` — in
  `properties.model.stringValue` (`CrudTablePlugin.java`). Putting it in `settings` is useless — the plugin
  does not read it.
- **`crudAlias` is the short alias.** At runtime the CRUD is resolved by the short alias; the full
  realm/client-prefixed key (`crud.getAlias()`) is trimmed by `CrudKeyGenerator.extractSimpleAlias`
  (`CrudTableSettingsControlPanel.java`). In `model` we write the short one.
- **`findRuleIdentifier` can be omitted** — at render time, if `crudAlias` is set and the rule is empty,
  the plugin creates `Find — <crudName>` and writes the id back into `model`. But then the rule
  will appear in the DB, not in your export, until you re-export. For a reproducible export
  it is better to create the rule and the id explicitly. An older export may have no `findRuleIdentifier` at all.
- **True predicate: only `return true`.** A bare `true` in a GroovyPredicate body is discarded
  by the template trailer → `null` → "Predicate rule must return Boolean"
 (`CrudDefaultActionsService.java`).
- **Writes are done by rules, not by the plugin.** The plugin has no built-in create/update/delete — direct and
  non-direct actions only run the `onBeforeStart`/`onBeforeComplete` rules
  (`CrudTablePlugin.java`), which themselves call `context.<ctx>.<alias>.service.create/update/delete`.
  Forget the rule → the action saves nothing. (The outdated javadoc `CrudTableActionsDto.java` says
  otherwise — ignore it.)
- **The fetch rule is context-free** (`contextIdentifiers: []`) and uses `service.crud.<alias>`,
  whereas the action rules are context-bound and use `context.<ctx>.<alias>.service` — these are different
  access paths, don't mix them up (see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)).
- **The visibility predicate loads the FULL row** (not only the form fields) — `.status` is available even if
  it is not in the columns/form (`CrudTablePlugin.java`). The predicate MUST return a Boolean.
- **One predicate — multiple actions.** The runtime deduplicates distinct non-empty
  `predicateIdentifier` values per row, so reusing a single predicate (Edit+Start in
  `inventoryCount`) is a normal pattern, it does not duplicate the evaluation.
- **`localizedButtonNames` empty → `localizedNames` is used** (`CrudTableActionsDto.java`).
  Default actions copy the names into button-names so the form's submit button is not empty; when building by
  hand a non-direct action without either map will show an empty submit button — fill in both.
- **Import mapping is not in `model`.** `headerToField`/`ignoredHeaders` live in
  `properties.importMapping.stringValue` (`ImportMappingDto`, the same STRING envelope as `model`),
  written at runtime when a file is uploaded (`CrudTablePlugin.java` → `ContentDomain.setJsonProperty`);
  they are runtime data, not part of a page template. When building a page — omit them.
- **`lastImportReport` is a runtime-only slot too.** After an import that produced row errors the plugin writes
  an `ImportErrorReportDto` into `properties.lastImportReport.stringValue` (`CrudTablePlugin.java`), reads
  it to gate the "View upload errors" button (→ `ImportErrorReportDialog`), and clears it to the string
  `"null"` on dismiss. Unlike `importMapping` it **can** survive into an export — a node that once had a failed
  import carries the slot with `stringValue:"null"` (a cleared residue). Like `importMapping`, it is NOT part of
  the design-time template — omit it when building a page.
- **`duplicateAction` is meaningful only with `duplicateDetectionPredicateIdentifier`.** Without a predicate the dedup
  is not performed, and the value is ignored (`CrudTableImportSettingsDto.java`).
- **There is no "refresh-on-complete" on CRUD-table actions.** A direct action does an unconditional
  `refresh()` of the whole table (`CrudTablePlugin.java`). A configurable multi-select refresh is a
 feature of the List form control and form events, not of this plugin.
- **An action carrying a single `name` uses an outdated/broken schema.** The
  CRUD `ActionDto` has NO `name` field: GSON silently drops that key on parsing, and `getLocalizedName`
  (`CrudTableActionsDto.java`) reads only `localizedNames` with no legacy fallback → such an
  action renders with an EMPTY label. Always write `localizedNames` (+`localizedButtonNames`), not `name`.
  (The fallback to the legacy `name` exists only for COLUMNS — `CrudTableColumnSettings.getLocalizedName` — but not for
  actions; don't confuse them.)
- **CRUD `ActionDto` ≠ workflow `ActionDto`.** In the CRUD version `direct` is a boolean (`true`/`false`), and there is NO
  `validationRuleIdentifiers`/`completeUserTask`/`taskId`/`onBeforeUserTask*`. `action.md` mixes both
  classes — don't carry workflow fields over to the CRUD table (see [07](07-workflows-and-tasks.md)).
- **`filterSettings` — only 5 fields** (`id`/`name`/`filterField`/`dataClass`/`defaultValue`).
  Rich filters (Dropdown/Autocomplete/Date, `ruleIdentifier`, `key`, `dateFormat`) from `table-plugins.md`
  do NOT exist on this model — don't add them.
- **`crud.tree.plugin` is a close relative.** The same model + `parentFieldExpression` (DTO-side,
  `"parent.id"`) and `parentFilterFieldExpression` (filter-side, `"parentId"`, exactly the one the provider puts
  into the filter for `findByParent`); `rowsPerPage` default = `Integer.MAX_VALUE`; fetch = `Find children —
  <crud>` via `findByParent`. Details — in [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md).
