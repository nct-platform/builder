# 14a — Full Plugin Config Reference (every plugin: settings + editor + JSON + field-by-field)

> 📐 **Field evidence — the configurations that shipped:** [09-studio-components.md](references/09-studio-components.md) · [10-visual-design.md](references/10-visual-design.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> Auto-derived from the nct-ui source (each plugin's class + editor + settings panel + config DTO). Companion to [14](14-plugin-catalog-all.md) (catalog) — this is the **field-level config reference** at the depth [22](22-charts-params-and-filters.md) gives charts. nct-ui declares **64 distinct plugin names**; there is a field-level entry here for **63** of them (`calendar.plugin` is catalogued in [14](14-plugin-catalog-all.md) only), plus a ⚠️ stub for the dead name `processes.plugin`. `authoredInMrjun` marks whether a project builder hand-writes this node's config (vs a fixed base-skeleton/admin plugin).
>
> Config-JSON examples tagged (`erp`) were decoded from a fictional ERP demo bundle that **no longer ships** ([23](23-distribution-and-known-gaps.md) explains why it was withdrawn); the shapes are unchanged. unpack it and check any of them yourself. They illustrate a node *shape* — the entity names in them are sample values, not a vocabulary your project has to adopt.

## Contents

- **Charts & reporting** — `chart.js.plugin`, `global.replacement.plugin`
- **Form controls** — `action.button.plugin`, `dynaform.filter.submit.button.plugin`, `dynaform.form.comments.field.plugin`, `dynaform.form.datepicker.field.plugin`, `dynaform.form.file.upload.field.plugin`, `dynaform.form.gantt.chart.plugin`, `dynaform.form.list.field.plugin`, `dynaform.form.rimm.autocomplete.field.plugin`, `dynaform.form.rimm.drop.down.field.plugin`, `dynaform.form.text.field.plugin`, `dynaform.form.textarea.field.plugin`, `dynaform.form.tree.picker.plugin`
- **Form infrastructure** — `dynaform.filter.form.plugin`, `dynaform.form.groups.landingplugin`, `dynaform.form.plugin`, `dynaform.list.item.plugin`
- **CRUD tables & trees** — `crud.table.plugin`, `crud.tree.plugin`, `process.table.pluin`
- **Layout & content** — `nct.help.plugin`, `nct.html.plugin`, `nct.image.plugin`, `nct.label.link.plugin`, `nct.label.plugin`, `nct.link.plugin`, `nct.parsis.plugin`, `nct.tab.plugin`, `siteMapPage`
- **Site chrome** — `site.breadcrumb.plugin`, `site.footer.plugin`, `site.header.plugin`, `site.kicker.plugin`, `site.right.kicker.plugin`
- **Rules / executor** — `executor.rule.script.plugin`
- **Workflow & process** — `bpmn2modeler.plugin`, `processes.plugin` ⚠️ *(dead name)*, `processes.selectedplugin`
- **Lists & system** — `admin.queries.plugin`, `audit.log.list.plugin`, `dynaform.context.list.plugin`, `executor.rule.list.plugin`, `workflows.plugin`
- **Admin console** — `admin.integrations.list.plugin`, `admin.localization.plugin`, `admin.organizations.plugin`, `admin.projects.plugin`, `admin.query.plugin`, `admin.rolegroup.management.plugin`, `admin.schedulers.plugin`, `admin.sources.plugin`, `admin.user.management.plugin`, `database.management.plugin`, `discovery.plugin`, `dynaform.form.groups.plugin`, `dynamic.cruds.plugin`, `messaging.mail.templates.plugin`, `ontology.viewer.plugin`, `project.settings.plugin`, `project.template.management.plugin`, `query.results.plugin`, `report.pdf.templates.plugin`, `user.profile.plugin`


---

## Charts & reporting

### `chart.js.plugin` — the universal "HTML + JS + data" widget (every chart, KPI tile, gauge, hand-coded dashboard block)

- **Config slot:** `properties.Javascript` (`stringValue` = a GSON-encoded **`ChartJsModel`** JSON string; key = `ReportServiceUtils.JS_MODEL_NAME = "Javascript"`, NOT `model`/`settings`) · **Editor:** yes — `ChartJsEditor` in a 95% modal, template gallery + 5 tabs (HTML / JS / **Css** / Replacements / Caching) · **Hand-authored in .mrjun:** **yes** — a builder places the node and hand-writes the whole `ChartJsModel` blob (`{id,html,js,css?,cssByTheme?,schedule?,replacements[]}`); there is no chart CLI command, the JSON is written by hand.
- **Function:** One chart/widget on a page: raw JS/HTML/CSS authored by the builder, data bound through `$$('name', default, 'Type')` placeholders that each map to a `ChartJsReplacement` (its own embedded query + column). At render, the server re-parses the `$$()` markers, runs each `QUERY` replacement, and substitutes typed JS literals; the browser then runs the script via `Function(jsConfig).call(this)`. Reacts to the page filter bar via the `parametersOfQueryHasBeenChanged` event and supports click-to-cross-filter (`this.crossFilter`) and drill-down (`this.showFutureQuery`). `renderHead` loads four charting cores: Chart.js 3.9.1, Plotly 2.27.0, ECharts 5.6.0, Mermaid 10 (+ Chart.js date-fns adapter) — the chart *type* is decided by the `js`, there is no engine field.
- **Config JSON** (decoded `Javascript.stringValue` = `ChartJsModel`):
```jsonc
{
  "id": "56b6bab4-8b66-4e53-9ac2-08c9378b7015",         // model uuid (auto-assigned if null on init)
  "html": "<canvas width=\"100\" height=\"100\"></canvas>", // mount markup: <canvas> Chart.js · <div> Plotly/ECharts · <pre class=\"mermaid\"> Mermaid
  "js":   "const labels=$$('Labels',[],'String[]');const v=$$('valuesf',[1],'Integer[]');const ctx=this.$find('canvas')[0].getContext('2d');this.chart=new Chart(ctx,{type:'line',data:{labels:labels,datasets:[{data:v}]}});",
  "css":  "",                                            // LEGACY single CSS block (theme-safe container styling); the ONE key omitted when empty — folded in as the "*" entry below
  "cssByTheme": { "*": ".<pfx>-wrap{padding:8px}",       // per-theme CSS: "*" = every skin ...
                  "Dark Blue": ".<pfx>-wrap{background:var(--bs-body-bg)}" },  // ... any other key = ONE exact skin display name. Every rule is auto-scoped to this chart instance at render, so it cannot leak; still name your classes with a per-component prefix so two charts on one page stay readable
  "schedule": { "job": {} },                             // caching — edited on the Caching tab, which copies it onto every replacements[].query; present as an empty object in exports (getSchedule() lazy-inits)
  "replacements": [                                       // one ChartJsReplacement per distinct $$() name
    {
      "name": "Labels",                                  // = 1st arg of $$()  (binding key)
      "group": "$$('Labels',[],'String[]')",             // EXACT literal $$() text copied out of `js` char-for-char (comma spacing, quote style AND the arg#2 default `[]` all included) — server does a literal js.replace(group,value) (ChartJsServiceImpl.java); mergeReplacements re-syncs only name/type, NEVER group, so one stray space silently blanks this series (the $$() survives to the browser where window.$$(name,default) returns the inline default)
      "type": "String[]",                                // a ReplacementType string -> how the fetched value becomes a JS literal
      "replaceStrategy": "QUERY",                         // QUERY (run query, pull columnName) | LABEL (inject value verbatim)
      "queryIdentifier": "64813fd2-0855-435e-a276-054dac4b1110",
      "query": { /* embedded MINIMAL 12-field QueryDto (NOT the 21-field saved rep-object): id, identifier, realmName, clientName, name, query, sourceIdentifier, offset, itemsPerPage, parameters, attributes, aggregations{aggregations:[]} — this copy is what runs; see ⛔ below */ },
      "columnName": "monthsn",                            // lowercased result column to pull; ABSENT for type 'Full'
      "defaultValue": "[]",                               // arg #2 of $$() stored verbatim as a string ('[]','[1]','0') — must be byte-identical to arg#2 inside `group`/`js`
      "value": null,                                      // literal injected when replaceStrategy==LABEL (runtime/cross-filter; usually not serialized)
      "currentFutureRepNumber": null,                    // drill-step pointer (advanced by showFutureQuery); null when no drill in progress
      "futureReplacements": [],                           // drill-down chain: list of same-shaped ChartJsReplacement; [] = no drill
      "order": 0,                                          // display/eval order (reorder() stamps by index)
      "maxItemsCount": 1000                               // row cap -> set as query.itemsPerPage before running
    },
    {
      "name": "valuesf",                                 // EVERY $$('name',…) in `js` needs its OWN replacement — the js above binds two ($$('Labels',…) and $$('valuesf',…)), so there are TWO entries
      "group": "$$('valuesf',[1],'Integer[]')",          // byte-for-byte the $$('valuesf',…) text from `js` (arg#2 default `[1]` included)
      "type": "Integer[]",
      "replaceStrategy": "QUERY",
      "queryIdentifier": "…",
      "query": { /* embedded MINIMAL 12-field QueryDto — see ⛔ below */ },
      "columnName": "amount",
      "defaultValue": "[1]",                              // arg#2 verbatim, byte-identical to arg#2 inside `group`/`js`
      "value": null,
      "currentFutureRepNumber": null,
      "futureReplacements": [],
      "order": 1,
      "maxItemsCount": 1000
    }
  ]
}
```
> ⛔ **The embedded `replacements[].query` MUST be a minimal 12-field QueryDto** — ONLY `id, identifier, realmName, clientName, name, query, sourceIdentifier, offset, itemsPerPage, parameters, attributes, aggregations` (with `aggregations.aggregations = []`, not `null`). **Do NOT embed the whole saved query REP-OBJECT** — its 21-field rep metadata (`creationTime`, `modificationTime`, `errors`, `message`, `hidden`, `schedule`, `lastScheduledTime`, `statementTimeoutSeconds`, `wrapInPaging`) breaks deserialization. `ChartJsPlugin` reads the model via `getContent().getJsonProperty("Javascript", ChartJsModel.class, ()->emptyModel)`, which **swallows** the failure and returns an EMPTY model, so the chart renders as a blank `nct.html.plugin` "Modify html" cell (config present in `properties.Javascript` but never drawn) — imports 0-err and passes validate. `validate_cmds.py` ERRORs on any extra key. See doc [22](22-charts-params-and-filters.md) §1.
- **Fields** (top-level `ChartJsModel`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `id` | String | model uuid (auto-assigned if null in `initPluginContent`) | — (required) |
| `js` | String | render script; data via `$$('name',default,'Type')`; runs with `this` = the panel (`this.$find`, `this.chart`, `this.crossFilter`, `this.showFutureQuery`) | — (required) |
| `html` | String | mount markup — `<canvas>` (Chart.js) / `<div>` (Plotly/ECharts) / `<pre class="mermaid">` (Mermaid). It *can* hold a `<style>`, but that style is **global to the page**; put styling in `cssByTheme` instead, which is scoped and theme-aware | — (required) |
| `css` | String | LEGACY single CSS block, still honoured: folded in as the `cssByTheme["*"]` block when that entry is absent or blank (an explicit `"*"` block wins) | omitted |
| `cssByTheme` | `Map<string,string>` | **per-theme CSS.** Keys: `"*"` (every theme) plus **exact skin display names** — the Css tab lists them all, currently `Standard` · `Dracula` · `Forest` · `Dark` · `Dark Blue`. At render only the `"*"` block **and the active skin's block** are emitted, each auto-scoped to this chart instance's wrapper id (so it cannot bleed into the page, and an inline `<style>` in `html` — which is global — is the mistake it replaces). A skin is a whole-stylesheet swap with no theme class to select on, so this map is the ONLY way authored chart CSS can differ per theme. See [24a](24a-theming-and-dark-mode.md) | omitted |
| `schedule` | `ScheduleDto` | **Result caching, applied indirectly.** The editor's **Caching** tab edits this object (cron expression + the rest of `ScheduleDto`), and every change **copies it onto EVERY `replacements[].query.schedule`** — that per-query copy is what the render path actually sends. A replacement query that carries a cron expression is served from the query service's result cache (first run fills it, later renders with the same query+params reuse it); a query with no expression is executed on every render. Consequences for a builder: (a) set the schedule only **after** the replacements exist — one added later keeps its own `query.schedule` unset until you re-touch the tab; (b) `schedule` on the model alone changes nothing; (c) ⛔ **do not hand-author caching in the `.mrjun`** — a `schedule` key inside `replacements[].query` is exactly one of the rep-object fields the ⛔ note above rejects (and `validate` ERRORs on it), so enable caching in the live Caching tab after import, not in the export. Present as an empty `{"job":{}}` in exports (lazy-init) | empty `{}` |
| `replacements[]` | `ChartJsReplacement` | one entry per distinct `$$()` name | `[]` |

  Nested **`ChartJsReplacement`**: `name`, `group` (exact `$$()` text), `type` (ReplacementType string), `replaceStrategy` (`QUERY`/`LABEL` enum, `ReplaceStrategy.java`), `queryIdentifier`, `query` (embedded **minimal 12-field** `QueryDto` — NOT the 21-field saved rep-object; see ⛔ above), `columnName` (lowercased; absent for `Full`), `defaultValue` (Object, arg#2 as string), `value` (Object, LABEL literal), `currentFutureRepNumber` (Integer, drill pointer), `futureReplacements[]` (drill chain), `order` (int), `maxItemsCount` (Integer, default **1000**).

- **Editor / settings panel:** `ChartJsEditor extends NctFormBasePanel<ChartJsModel>` (`ChartJsPlugin.editComponent`, `editorShownInModal()=true`, `modalWidth()="95%"`). A **template gallery** ("Start from a template", 88 starters from `chart-templates.json` — chartjs 29 · plotly 24 · echarts 20 · mermaid 15, grouped by engine→category) sets `model.html`+`model.js` and jumps to the JS tab. **FIVE tabs** (each one's visibility + which opens first come from `JsChartEditorConfig`: `showHtmlTab`/`showJsTab`/`showCssTab`/`showReplacementsTab`/`showCachingTab`, all `true` by default, `activeTab` default `JS`): **HTML** (CodeMirror → `model.html`), **JS** (CodeMirror → `model.js`; editing re-parses `$$()` and auto-syncs the Replacements list via `mergeReplacements`), **Css** (per-theme CSS → `model.cssByTheme`, see below), **Replacements** (`JsReplacementsPanel` → `model.replacements[]`; each row shows the placeholder name, the QUERY/LABEL strategy and either the LABEL value or a query chooser + **Configure**, which opens the query pane beside the list for query/column/groupBy/orderBy/aggregations/`maxItemsCount`/drill; a toolbar input sets `maxItemsCount` on every row at once; drag reorders), **Caching** (`ChartCachingPanel` → `model.schedule`, fanned onto every replacement query — see the `schedule` row above). The **Css** tab is a pill strip of theme keys — **"All themes"** (`"*"`) followed by every skin display name, taken from the `Skin` enum so a newly added skin appears by itself — beside ONE CodeMirror bound to the selected key; a pill that already carries CSS is marked, and switching pills submits first so the text you just typed lands under the theme that was selected. `onSubmit(model)` writes `content.setJsonProperty("Javascript", model)`, saves, closes the modal, and `refresh()`es. The same editor reopens in a reduced form for the drill-down (`showFutureQuery`) preview: HTML/JS/Caching hidden, **Replacements** active and **read-only** (`replacementsEditable=false`). The plugin also re-runs and re-persists on the page `parametersOfQueryHasBeenChanged` event when a filtered replacement query changes.
- **See also / source:** **doc [22](22-charts-params-and-filters.md)** (the full recipe — `$$()` binding, params, filter bar `global.replacement.plugin`, cross-filter, drill-down, theme-safe rendering, editor, Chart.js config); **per-theme CSS in [24a](24a-theming-and-dark-mode.md)**; catalog stub in doc [14](14-plugin-catalog-all.md) §2.2; slot note in doc [01](01-content-model-and-pages.md) / [00](00-export-format-and-import.md). · `ChartJsPlugin`, `ChartJsModel`, `ChartJsReplacement`, `ReplaceStrategy`, `ChartJsEditor`, `ChartCachingPanel`, `NctThemeCss` (per-theme scoping, shared with `nct.html.plugin`), `ReportServiceUtils` (`JS_MODEL_NAME`).

### `global.replacement.plugin` — the dashboard page **filter bar** for chart.js charts

- **Config slot:** `properties.<none>` (`stringValue` = **no config blob** — only `className/styleName/tagProperties` boilerplate) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **yes** — a builder *places* one node per dashboard page (`node add --plugin global.replacement.plugin --parent <page/parsis>`), but writes **no config**: it is in `NO_CONFIG_SLOT_PLUGINS`, so `--model`/`--settings` are rejected. Not base-skeleton chrome; it is deliberately added to reporting/BI pages next to the charts.
- **Function:** Runtime-built filter bar for the `chart.js.plugin` charts on the **same Wicket page**. Each chart, on init, fires `addFieldsToParametersPanel(query)` for every `QUERY` replacement; this node's `ParamsPanel` listens, derives one control per distinct SQL placeholder param (dropdown for `dropdown-*`, typed input otherwise), and on submit fires page-wide `parametersOfQueryHasBeenChanged(changedQueries)` so every bound chart re-runs its query with the new param values. It is also the sink for **click-to-cross-filter** (`applyChartFilter`). The event bus is page-scoped, so it must sit on the same page as the charts.
- **Config JSON** (decoded):
```jsonc
{ "pluginName": "global.replacement.plugin", "name": "Global replacements",
  "children": [],
  "properties": { "className": { "stringValue": "" },
                  "styleName": { "stringValue": "" },
                  "tagProperties": { "stringValue": "" } }   // no model / settings / Javascript key — nothing to author
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config blob. `NctBasePlugin<ChartJsModel>` type param is only a form model; it is **never** deserialized from a slot (no `getJsonProperty`/`saveContent`). Filter controls are emergent from the charts' query params. | — |
- **Editor / settings panel:** No config editor — `editComponent()` returns `null` (despite `editorShownInModal()=true`/`modalWidth()=95%`, there is no panel to show). The **plugin body itself** renders the parameters form (`ParamsPanel`), which builds one control per placeholder from the charts' `QueryDto` placeholders and accumulates edited `QueryDto`s into a page-`MetaDataKey` set; `onSubmit` triggers `parametersOfQueryHasBeenChanged` and clears the set. A ctor `applyChartFilter` listener takes `CrossFilterData(field,value)`, calls `paramsPanel.applyFilterFromChart(...)`, and re-fires `parametersOfQueryHasBeenChanged` for the affected queries. `@PluginConfig(group="Reporting")`, icon `lnr-keyboard`.
- **See also / source:** [22 §4–§5](22-charts-params-and-filters.md) (deep: filter-bar node, the one-string-in-five-places contract, re-run chain, cross-filter), [14 §1.11](14-plugin-catalog-all.md), [01](01-content-model-and-pages.md) · `GlobalReplacementPlugin.java` (`plugin/chart/`), `ParamsPanel.java`, `QueryDto.java`


---

## Form controls

### `action.button.plugin` — standalone button that runs an EXECUTION rule on click
- **Config slot:** `properties.settings` (`stringValue` = serialized `ActionButtonSettings` JSON) · **Editor:** no — `editComponent()` returns `null`; config is a right-nav settings panel (`ActionButtonSettingsPanel`, a single form, no tabs, save-as-you-type) · **Hand-authored in .mrjun:** yes — a builder drops this node into a page's `nct.parsis.plugin` slot (or into a `dynaform.form.plugin`) and writes the `settings` blob (rule id, labels, styling).
- **Function:** Renders one Bootstrap button (`btn-*`). On click it executes the EXECUTION rule named by `ruleIdentifier` via `RuleExecutionService.executeRuleWithContextData(...)`, then optionally re-renders the `IRefreshable` components listed in `refreshTargets`. Rule context comes from the nearest `IFormContextProvider` ancestor: **inside a form** the rule sees the form's full `contextData` (CRUD row + attrs); **standalone** (no form ancestor) it runs with an **empty `ContextDataDto`** (only globals / `service.*` work). If `submitForm` is set and a parent `Form` exists, the button is an `AjaxButton` that validates+submits the form first (validation failure → error toast, rule not run); otherwise it is a plain `AjaxLink`.
- **Config JSON** (decoded from `settings.stringValue`):
```jsonc
{
  "localizedLabels": { "en_US": "Pull from PO", "ru_RU": "Забрать из PO", "hy_AM": "Քաշեք պատվերից" },
  "iconClass": "pe-7s-rocket",          // Pe-7s icon; blank => no icon
  "ruleIdentifier": "14265d38-d7e4-4300-82cf-38aad872a9d4", // EXECUTION rule run on click
  "variant": "PRIMARY",                  // ButtonStyleVariant
  "outline": false,
  "gradient": false,
  "shadow": false,
  "size": "DEFAULT",                     // ButtonSize
  "shape": "DEFAULT",                    // ButtonShape
  "wide": true,
  "iconOnly": false,
  "submitForm": false,                   // only honored when inside a Form
  "showWaitIcon": false,
  "blockSelector": null,                 // CSS selector overlaid while the action runs
  "refreshTargets": "526ac33a-8e73-4d3e-a31a-78db09252e99" // CSV of content uniqueIdentifiers
}
```
- **Fields** (class `ActionButtonSettings`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `localizedLabels` | `Map<locale,String>` | Button caption per locale key (`en_US`, `ru_RU`, `hy_AM`…). Resolution: exact locale → language → first non-blank; **empty map → renders literal "Action"** | null (no seed) |
| `iconClass` | String | Pe-7s icon CSS class (e.g. `pe-7s-rocket`); adds `btn-icon` + icon wrapper. Blank → icon holder hidden | null |
| `ruleIdentifier` | String | Identifier of the EXECUTION rule invoked on click (blank → warning toast "No rule configured") | null |
| `variant` | enum `ButtonStyleVariant` | Color token → `btn-<token>`: `PRIMARY,SECONDARY,SUCCESS,INFO,WARNING,DANGER,LIGHT,DARK,LINK,ALTERNATE,FOCUS` (token lowercased; null → `primary`) | `PRIMARY` |
| `outline` | boolean | Use `btn-outline-<token>` instead of solid (wins over gradient) | `false` |
| `gradient` | boolean | Use `btn-gradient-<token>` (only if not outline) | `false` |
| `shadow` | boolean | Add `btn-shadow-<token>` | `false` |
| `size` | enum `ButtonSize` | `DEFAULT("")`, `SM("btn-sm")`, `LG("btn-lg")` | `DEFAULT` |
| `shape` | enum `ButtonShape` | `DEFAULT("")`, `PILL("btn-pill")`, `SQUARE("btn-square")` | `DEFAULT` |
| `wide` | boolean | Add `btn-wide` | `false` |
| `iconOnly` | boolean | Add `btn-icon-only` and **hide the text label** | `false` |
| `submitForm` | boolean | If inside a `Form`, click submits+validates the form before running the rule (ignored with no parent form). Settings-panel checkbox only shown when `inForm` | `false` |
| `showWaitIcon` | boolean | Emit `icon-wait="true"` → spinner on the button while the click is in flight | `false` |
| `blockSelector` | String | Emit `block-wait-selector="<sel>"` → matched elements get a blocking overlay for the action's duration | null |
| `refreshTargets` | String | Comma-separated content `uniqueIdentifier`s of `IRefreshable` plugins on the page; after a successful rule each target's own `refresh()` re-renders it (e.g. reload the list a "Pull from PO" rule just populated) | null |

- **Editor / settings panel:** No double-click editor (`editComponent` → null). Authors get a right-nav panel (`ActionButtonSettingsPanel`, opened via the `showSettings` AJAX event, author/admin roles only) bound to `ActionButtonSettings`: `LocalizedTextFieldsPanel` for `localizedLabels`, `Pe7sDropDownField` icon chooser (`iconClass`), variant/size/shape `DropDownChoice`s, checkboxes for `outline/gradient/shadow/wide/iconOnly/submitForm/showWaitIcon`, a `RuleIdentifierSelectorField` (filtered to `EXECUTION_RULE`, with a create-name suggestion "Button <label> Action Rule"), a `TextField` for `blockSelector`, and a `RefreshableContentSelectorField` multi-picker for `refreshTargets`. Every control uses the synced framework (`getKey()` = `"ActionButtonSynced"`); any change fires `refresh()`, which persists via `contentService.save(...)` into `properties.settings`, re-inits the button, and re-renders (single autosave chokepoint + "Settings saved" toast).
- **See also / source:** doc [14](14-plugin-catalog-all.md) §2.1 (already has a field-level table) · `ActionButtonPlugin.java`, `ActionButtonSettings.java`, `ActionButtonSettingsPanel.java`, `ButtonStyleVariant.java`, `ButtonSize.java`, `ButtonShape.java` (all in `nct-ui/.../plugin/dynaform/action/`).

### `dynaform.filter.submit.button.plugin` — submit button that fires a filter form's values as an `onFilterSubmit` event

- **Config slot:** `properties.settings` (`stringValue` = `FilterSubmitButtonSettings` JSON) · **Editor:** no (`editComponent` returns `null`; configured via a right-nav settings panel, tab **"Submit Button"**, author/admin only) · **Hand-authored in .mrjun:** **yes** — a builder drops this node inside a filter form's inner `nct.parsis.plugin` and writes its `settings` JSON (it is a "Form Controls"-group control, not base skeleton).
- **Function:** Renders a `<button class="btn btn-primary">` whose label is `buttonName`. On click it locates the enclosing `Form` and parent `IFilterFormProvider` (the `FilterFormPlugin`), reads `provider.getFilterValues()`, and triggers the `onFilterSubmit` event carrying that value map (`FilterSubmitButtonPlugin.java`); the sibling CRUD table's fetch rule then re-queries with those keys. If no parent form is found it renders an inert `WebMarkupContainer` instead of a button; if there is a form but no `IFilterFormProvider`, click shows `nctError`. Optionally overlays a loading/wait indicator during submit (see fields). Validation failures call `onError` → "Form validation failed".
- **Config JSON** (decoded):
```jsonc
{
  "buttonName": "Filter",                 // button caption
  "waitComponentIdentifier": "crud-tbl-uid" // OPTIONAL: uniqueIdentifier of an IRefreshable sibling to spin
}
```
Common minimal form is just `{"buttonName":"Filter"}`.
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `buttonName` | String | Button display text. If blank at render, falls back to the literal `"Filter"` (`FilterSubmitButtonPlugin.java`). | `"Filter"` (`@Builder.Default`) |
| `waitComponentIdentifier` | String | `uniqueIdentifier` of an `IRefreshable` sibling plugin (e.g. the CRUD table); resolves that plugin's markup id and attaches a loading/wait overlay on it during submit via `ButtonUtils.addWait("#"+markupId)`. Superseded by the parent `FilterFormPlugin`'s `waitSelector` (a raw CSS selector) when that is set — the parent's selector wins. Picked in the settings panel from a list of refreshable siblings, or cleared. | `null` (no wait overlay) |
- **Editor / settings panel:** No inline editor. Authors/admins get a gear (`showSettings` AJAX event → `FilterSubmitButtonSettingsPanel` in the right nav, plus a `ContentHighlightBehavior`). The panel is a form bound to `FilterSubmitButtonSettings` with: a `buttonName` `TextField`; a "wait component" chooser that lists every `IRefreshable` `PluginPanel` under the parent `FilterFormPlugin` (shown as pluginName, value = its `uniqueIdentifier`) with select / clear links writing `waitComponentIdentifier`; and a submit link that fires `save_filter_submit_settings_<uuid>` → `saveSettings()` (writes `properties.settings`) then `refresh()` (re-inits content and re-renders).
- **See also / source:** [04-crud-table-plugin.md § standalone filter form](04-crud-table-plugin.md) (field-level: both `buttonName` + `waitComponentIdentifier`, and the `onFilterSubmit` → fetch-rule `attrs` wiring) · catalog [14](14-plugin-catalog-all.md) · `FilterSubmitButtonPlugin.java`, `FilterSubmitButtonSettings.java`, `FilterSubmitButtonSettingsPanel.java`

### `dynaform.form.comments.field.plugin` — threaded comments/answers form control (bound to an `ObjectNode` field)

- **Config slot:** `properties.settings` (`stringValue` = escaped-JSON of `FormControlSettings` — the **base** DTO, no per-plugin delta subclass) · **Editor:** no (`editComponent()` inherited from `BaseFormControl` returns `null`; config is via the shared right-nav **Form Settings** panel) · **Hand-authored in .mrjun:** yes — a builder drops a Comments control into a form (usually via *Generate fields* or manually) and writes its `settings` scope/mapping like any other form control.
- **Function:** Renders an "Add a Comment" card (textarea + button) followed by a list of comments, each with author/timestamp, a reply box, and nested answers. Two AJAX listeners mutate the bound value: `addComment` (payload = `String` text) appends `{id:UUID, text, author, timestamp}` with an empty `answers[]`; `addAnswer` (payload = `Map{commentId,text}`) finds the comment by id and appends an answer. `author` = current user's email (`ReportSecurityService.getUser(tenant()).getEmail()`, fallback `"Anonymous"`), `timestamp` = `Instant.now().toEpochMilli()`. After a mutation it `reRender`s the container and calls `initComments()`. The control initializes an empty `{comments:[]}` shape on the field only when `fieldExpression` is set. `supportedDataClasses()` = **`com.fasterxml.jackson.databind.node.ObjectNode` only**.
- **Config JSON** (decoded — a real node; the doc's only CONTEXT-scope form control). ⛔ `CONTEXT` here is
  correct because this form is opened WITHOUT a row (a workflow user task / `process.table` action). On a form a
  `crud.table`/`crud.tree` action opens, every control — this one included — is bound by the platform to that
  table's `contextIdentifier` + `crudAlias`, so it is authored `scope:"CRUD"` over a `jsonb` column
  ([02](02-form-controls-reference.md) §Where the value LANDS):
```jsonc
{
  "scope": "CONTEXT",                                   // GLOBAL | CONTEXT | CRUD
  "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553",
  "fieldExpression": "comments",                        // key holding the {comments:[…]} ObjectNode
  "localized": false,
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  "name": "Comments",                                   // authoring label
  "dataClass": "com.fasterxml.jackson.databind.node.ObjectNode"  // the ONLY allowed dataClass
}
```
The **field value** (runtime data, NOT config) is the `ObjectNode` written to the mapped slot — for CONTEXT scope `contextDataMap[contextIdentifier].value[fieldExpression]`:
```jsonc
{ "comments": [
  { "id": "uuid", "text": "comment text", "author": "user@email.com", "timestamp": 1723456789000,
    "answers": [ { "id": "uuid", "text": "answer text", "author": "u2@email.com", "timestamp": 1723456790000 } ] }
] }
```
- **Fields:** (base `FormControlSettings`; only the mapping keys are meaningful for this control — the value type is fixed to `ObjectNode`, so `between`/`enum*`/`jsonNode*`/`defaultValue*` are inapplicable. Full base table incl. validation/events → doc 02.)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `scope` | enum `GLOBAL`\|`CONTEXT`\|`CRUD` | Where the `ObjectNode` value is stored (GLOBAL→`attrs`, CONTEXT→`contextDataMap[ctxId].value`, CRUD→`crudDataMap[crudAlias].value`). Serialized as the constant name. | null |
| `contextIdentifier` | String (UUID) | Context (`rep-objects.contexts[].identifier`); required for CONTEXT/CRUD. | null |
| `crudAlias` | String | CRUD alias within the context; CRUD scope only (nulled on save if `contextIdentifier==null`). | null |
| `fieldExpression` | String | Field/key that holds the `{comments:[…]}` ObjectNode. Init only happens when this is non-blank. | null |
| `name` | String | Authoring label (drawn by a sibling `nct.label.plugin`). | null |
| `dataClass` | String (FQN) | Value type — must be `com.fasterxml.jackson.databind.node.ObjectNode`. | null |
| `localized` | Boolean | Base field; kept `false` for Comments. | null |
| `mandatoryValidationMessages` / `conditionalValidations` / `eventComponentMappings` | Map / List / List | Inherited base validation/event scaffolding; typically empty for this control. | `{}` / `[]` / `[]` |

- **Editor / settings panel:** No custom editor panel. Selecting the node opens the **shared** `FormControlSettingsControlPanel` (right-nav "Form Settings", `getSettingsControlPanel()` default) which writes the base `FormControlSettings` — scope + context/crud/field mapping, name, dataClass, and the optional Prohibited / Mandatory / Default / Validation / Event accordions. All of it lands back in `properties.settings.stringValue`.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §11 (dedicated section + base field table) · `comments/CommentsFieldFormControlPlugin.java`, config `config/FormControlSettings.java` (base), shared panel `FormControlSettingsControlPanel`.

### `dynaform.form.datepicker.field.plugin` — form-control that renders a date / date-time / date-range picker bound to a temporal CRUD field

- **Config slot:** `properties.settings` (`stringValue` = JSON of `DatePickerFormControlSettings` = `FormControlSettings` + one delta field `dateFormat`) · **Editor:** no (`editComponent` not overridden; configured via the right-side Form-Control settings panel `DatePickerFormControlSettingsControlPanel`, not editor tabs) · **Hand-authored in .mrjun:** yes — a builder drops this control into a form page / form-group and hand-writes its `settings` blob (scope + binding + `dataClass` + `dateFormat`); most instances are emitted by the Generate-Fields dialog but the node stays builder-editable.
- **Function:** Draws a Bootstrap `input-group` (text input + calendar button) backed by the `daterangepicker` JS lib (`moment.min.js` + `daterangepicker.min.js`/`.css` loaded in `renderHead`). Reads/writes `LocalDate`, `LocalDateTime`, `Instant` (or an `ObjectNode` JSON path). Date-vs-date-time is driven by `dataClass` (there is no separate DATE/DATETIME plugin) and by whether `dateFormat` carries a time token. With `between:true` a single range input opens a **two-calendar** picker (`singleDatePicker:!between`) and writes `"from - to"`, split server-side on `" - "` into the primary (from) and `betweenMapping` (to) targets. In prohibited/view mode it renders a read-only `<label>` with the formatted value.
- **Config JSON** (decoded):
```jsonc
{
  "scope": "CRUD",                                  // FormControlScope: GLOBAL | CONTEXT | CRUD
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "stockMovement",
  "fieldExpression": "documentDate",                // bound CRUD field
  "filterKey": "documentDate",                      // key in filter/param map (filter usage)
  "name": "Document Date",                          // display caption
  "dataClass": "java.time.LocalDate",               // LocalDate | LocalDateTime | Instant | ObjectNode
  "dateFormat": "DD/MM/YYYY",                        // ← the ONLY datepicker-specific field (Moment.js pattern)
  "prohibitedPredicateIdentifier": "2566c158-01b1-4cc9-bf49-73bff0d4bab9",
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": []
  // range mode adds: "between": true, "betweenMapping": { …upper-bound target… }
  // ObjectNode fields add: "jsonNodeExpression": "…", "jsonNodeValueType": "java.time.LocalDate"
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `dateFormat` | String | **Only field this plugin adds.** Moment.js pattern for display + parsing. ⛔ **A Java pattern is accepted and renders literally** — `dd.MM.yyyy` becomes `dd.11.yyyy` *inside the input's value*, with no error and no log; see [02 §5](02-form-controls-reference.md). Empty → defaulted by `dataClass`: `LocalDate`→`"DD/MM/YYYY"`, `LocalDateTime`/`Instant`→`"DD/MM/YYYY HH:mm:ss"`. Presence of a time token (`HH`/`hh`/`:mm`/`:ss`/`A`) turns on the time picker. Panel offers a *curated, dataClass-gated* catalog (10 date-only + 17 date-time patterns) as an autocomplete — a pattern of your own is still accepted, and moment's `[literal]` escaping works. The catalog is shared with the CRUD Table / CRUD Tree / Process Table column `dateFormat` (`utils/DateFormatColumnUtils.java`). | null |
| `dataClass` | String (FQN) | Temporal type bound: `java.time.LocalDate`, `java.time.LocalDateTime`, `java.time.Instant`, or `…node.ObjectNode`. Gates which formats the panel shows and whether a time picker appears. | null |
| `scope` | enum `GLOBAL`\|`CONTEXT`\|`CRUD` | Binding scope of the value. | null |
| `contextIdentifier` / `crudAlias` / `fieldExpression` | String | Context UUID, CRUD alias, and field path the value maps to (CRUD/CONTEXT scope). | null |
| `filterKey` | String | Value key in the filter/page-param map (filter usage). | null |
| `name` | String | Display caption. | null |
| `between` | Boolean | Range mode: renders one input → two-calendar picker; submits `"from - to"`. Always offered for this control. | null (false) |
| `betweenMapping` | `BetweenFieldMapping` | Upper-bound ("to") target; used only when `between`. Type/pattern shared from primary. | null |
| `jsonNodeExpression` / `jsonNodeValueType` | String | JSON path + value FQN when `dataClass` is `ObjectNode`. | null |
| _shared base_ | — | All remaining keys come from `FormControlSettings` and behave identically across every form control: `prohibitedPredicateIdentifier`/`alwaysProhibited`, `alwaysMandatory`/`mandatoryPredicateIdentifier`/`mandatoryValidationMessages`, `conditionalValidations`, `eventComponentMappings`, `localized`, `defaultValueEnabled`/`defaultValueStatic`/`defaultValue`/`defaultValueLocalized`/`defaultValueRuleIdentifier`, `enumValues`/`enumFieldNames`/`enumName` (unused for dates). Documented once in the shared form-control base section. | see base |
- **Editor / settings panel:** No `editComponent`; config is edited in the right-hand **Form-Control settings panel**, which shows a single `DateFormatAutoCompleteField` for `dateFormat` (`synced`, autosaves) rendering a categorized picker — captions "Date formats"/"Date & time formats", filtered by `dataClass` (`LocalDate`→date-only, `LocalDateTime`→date-time, `Instant`→all) — plus the standard shared config accordion (Prohibited / Mandatory / Default value / Conditional validation / Event mappings / Between). `betweenSupported()` and `betweenTypeEligible()` both return true, so Between is always available. In filter usage it swaps to `DatePickerFilterControlSettingsControlPanel`. The control exposes `pattern`, `showTimePicker`, `between` to the JS. Textual tokens (`MMMM`/`MMM`) render in **English** here, not the session locale: the same formatter also PARSES what the picker wrote, and the JS hard-codes English month names. (Table columns only format, so they use the viewer's locale.)
- **See also / source:** [02-form-controls-reference.md §5](02-form-controls-reference.md) (field table + range-mode + `dateFormat`/`dataClass` gotcha — already field-level complete) · `DatePickerFormControlPlugin.java`, `DatePickerFormControlSettings.java` (empty → `DatePickerFilterControlSettings.dateFormat` → `FormControlSettings`), `DatePickerFormControlSettingsControlPanel.java`, `DatePickerFormControlPlugin.js`, `utils/DateFormatColumnUtils.java` (the catalog + moment→java.time translation, shared with the table columns), `component/field/DateFormatAutoCompleteField.java` (the picker itself)

### `dynaform.form.file.upload.field.plugin` — form-control that uploads files to nct-file-storage and stores their storage PATHS as the field value
- **Config slot:** `properties.settings` (`stringValue` = `FormControlFileUploadFieldSettings` JSON) · **Editor:** no editComponent — config via the right-hand Form-Control **Settings** drawer (`FormControlSettingsFileUploadFieldControlPanel`) · **Hand-authored in .mrjun:** yes — a builder drops it onto a form page (usually via Generate-Fields for a file/image column) and configures its upload/type/size settings + CRUD binding
- **Function:** Renders a file-upload input + progress bar + list of uploaded files (download/remove links). On upload it validates extension + size, persists bytes to the file-storage microservice (`fileStorageService.upload(bytes, uploadPath + fileName)`), and keeps the **returned storage path** in the field value — so the field holds a **list of paths**, not bytes. `group = "Form Controls"`, extends `BaseFormControl<FormControlFileUploadFieldSettings>`; supported data classes = `ArrayList` / `ObjectNode` (**but exports write `java.util.List`** — same ArrayList-vs-List trap as List control). Download via `fileStorageService.getFile`, remove via `fileStorageService.delete`.
- **Config JSON** (decoded — 5 delta fields + inherited CRUD-binding fields):
```jsonc
{
  // --- delta (FormControlFileUploadFieldSettings) ---
  "uploadPath": "uploads/",                                   // base storage path prefix
  "allowedFileTypes": "jpg,jpeg,png,gif,bmp",                 // CSV of allowed extensions
  "maxFileSize": 10485760,                                    // max bytes (10 MB)
  "allowMultiple": true,                                      // NOTE: field is "allowMultiple", NOT "multiple"
  "showProgress": true,
  // --- inherited (FormControlSettings) binding ---
  "name": "Images",
  "dataClass": "java.util.List",                              // exports write List; whitelist is ArrayList/ObjectNode
  "scope": "CRUD",
  "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553",
  "crudAlias": "ticket",
  "fieldExpression": "images"
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `uploadPath` | String | Base storage-path prefix; final key = `uploadPath + clientFileName`. | `"uploads/"` |
| `allowedFileTypes` | String | Comma-separated allowed extensions; empty ⇒ all allowed. Compared case-insensitively. | `"pdf,doc,docx,xls,xlsx,jpg,jpeg,png,gif"` |
| `maxFileSize` | long | Max upload size in **bytes**; over-limit files are rejected with a toast. | `10485760` (10 MB) |
| `allowMultiple` | boolean | Allow selecting/uploading multiple files. **Config key is `allowMultiple` (not `multiple`)**. | `true` |
| `showProgress` | boolean | Show the Wicket `UploadProgressBar` during upload. | `true` |
| *(inherited)* `scope` / `contextIdentifier` / `crudAlias` / `fieldExpression` / `name` / `dataClass` | — | Standard form-control mapping (which CRUD/context field the paths write to). | — |

> Fields `maxFiles` / `showPreview` / `acceptedFileTypes` do **NOT** exist (fiction of old docs). A ported project needs the referenced files present in the target file-storage, since the field value is just storage paths.
- **Editor / settings panel:** No `editComponent` (view-only in the canvas). Config is edited in the Form-Control Settings drawer via `FormControlSettingsFileUploadFieldControlPanel` — a "File Upload Settings" fieldset with: Upload Path (TextField), Allowed File Types (TextField), Maximum File Size in bytes (NumberTextField, null ⇒ 10485760), Allow Multiple Files (CheckBox), Show Upload Progress (CheckBox). All wired with `synced(..., true)` autosave (writes straight back into the settings DTO on change). The generic CRUD/context binding (scope/field) is set by the shared base form-control settings, not this panel.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §9 (field-level table + worked example + file-storage runtime note) · `fileupload/FileUploadFieldFormControlPlugin.java`, `fileupload/FormControlFileUploadFieldSettings.java`, `fileupload/FormControlSettingsFileUploadFieldControlPanel.java`

### `dynaform.form.gantt.chart.plugin` — interactive Gantt/timeline form control (vis-timeline), one JSON field holding a project schedule

- **Config slot:** `properties.settings` (`stringValue` = JSON of `GanttChartFormControlSettings` — base `FormControlSettings` + gantt deltas) · **Editor:** no editComponent override; config is edited in the form-control **Settings panel** (`GanttChartFormControlSettingsPanel`, a single form, **no tabs**). A separate **runtime** "New/Edit Task" modal (`GanttItemEditPanel`, 640px) edits the field *data*, not config. · **Hand-authored in .mrjun:** **yes** — a builder drops this control into a form page and configures its `settings`. (Most projects contain none, but doc 14 confirms it as a real hand-authorable control — simply rarely needed.)
- **Function:** Renders a drag-editable Gantt chart (loads `vis-timeline-graph2d.min.js/.css` + `GanttChartFormControlPlugin.css`). Bound field value is JSON (`dataClass` = `ObjectNode` **only** — `JsonNode` abstract is rejected by the backend `getFieldList` check). The whole schedule (tasks, view window, dependencies, per-task attachments) is serialized into the single field. `getFormComponent()` returns `Optional.empty()` — there is no plain input; the control drives the field via `getFieldModel()` from AJAX events. It handles six client events — edit / add / delete an item, drag-move-or-resize (with progress), persist pan+zoom, and link two tasks (self-links rejected). After one of those it redraws **itself only**: a content re-init plus a re-render, deliberately not the full plugin `refresh()`, which would re-init the parent form and wipe the not-yet-saved in-memory value. The control feeds the JS: `ganttJson()`, the 7 boolean toggles, `chartHeight()`, `defaultColor()`, `localeKey()`, `languageCode()`, and an `i18n()` label map.
- **Config JSON** (decoded — the `settings` blob; gantt deltas shown, inherited base fields abbreviated):
```jsonc
{
  // --- binding (inherited FormControlSettings) ---
  "scope": "CRUD",                 // GLOBAL | CONTEXT | CRUD
  "contextIdentifier": "<uuid>",
  "crudAlias": "project",
  "fieldExpression": "schedule",
  "dataClass": "com.fasterxml.jackson.databind.node.ObjectNode",  // required, ObjectNode only
  "name": "Schedule",
  "localized": false,
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  // --- gantt-specific deltas ---
  "allowDragMove": true,
  "allowDragResize": true,
  "allowAddDelete": true,
  "showDependencies": true,
  "showProgress": true,
  "showTodayLine": true,
  "attachmentsEnabled": true,
  "stackItems": true,
  "maxItems": 500,
  "defaultColor": "#3498db",
  "palette": ["#3498db","#2ecc71","#e74c3c","#f39c12","#9b59b6","#1abc9c","#34495e","#e67e22"],
  "chartHeight": "480px"
}
```
- **Fields** (gantt deltas — all `@Builder.Default`; Boolean getters null-coalesce to the default via `isX()`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `allowDragMove` | Boolean | Allow dragging a task bar along the timeline (fires `updateItemBar`). | `true` |
| `allowDragResize` | Boolean | Allow resizing a bar's start/end edges. | `true` |
| `allowAddDelete` | Boolean | Show Add-Task affordance + per-task delete; gate `addItem`/`deleteItem`. | `true` |
| `showDependencies` | Boolean | Draw dependency arrows and enable the "link as dependency" action. | `true` |
| `showProgress` | Boolean | Render the per-task progress fill (0–100). | `true` |
| `showTodayLine` | Boolean | Draw the "today" marker line. | `true` |
| `attachmentsEnabled` | Boolean | Enable the per-task attachments tab in the edit modal (uploads to `gantt/<itemId>/<uuid>-<name>`). | `true` |
| `stackItems` | Boolean | Stack overlapping tasks vertically vs. overlay them. | `true` |
| `maxItems` | Integer | Upper bound on task count. | `500` |
| `defaultColor` | String | Color assigned to a newly created task (input type=`color`). | `"#3498db"` |
| `palette` | `List<String>` | Quick-pick swatches beside the per-item color picker. | 8 colors `#3498db…#e67e22` |
| `chartHeight` | String | Initial chart height (CSS units); JS falls back to `480px` if blank. | `"480px"` |

  Inherited base binding/validation/event fields (`scope`, `contextIdentifier`, `crudAlias`, `fieldExpression`, `dataClass`, `name`, `localized`, `mandatoryValidationMessages`, `eventComponentMappings`, `conditionalValidations`, `enumName`/`enumValues` [unused here], etc.) — see doc 02 header + §"Nested objects".

- **Runtime field-value shape** (NOT config — this is the `ObjectNode` stored in the bound field, `GanttDataDto`):
```jsonc
{
  "items": [
    { "id": "<uuid>",
      "name": {"en": "Design"},          // locale → string
      "description": {"en": "..."},       // locale → string
      "start": "2026-01-05", "end": "2026-01-12",
      "progress": 40,                      // 0..100
      "color": "#3498db",
      "dependencies": ["<otherItemId>"],   // predecessor item ids
      "attachments": [                      // GanttAttachmentDto
        {"fileId": "gantt/<itemId>/<uuid>-plan.pdf", "fileName": "plan.pdf", "size": 12345, "contentType": "application/pdf"}
      ],
      "milestone": false }
  ],
  "viewStart": "2026-01-01", "viewEnd": "2026-03-01",  // persisted pan/zoom window
  "lastModified": "2026-01-31T10:00:00Z"
}
```

- **Editor / settings panel:** `GanttChartFormControlSettingsPanel` — a single form, every input `synced(...)` (autosave on change): 8 `CheckBox` toggles, a `NumberTextField<Integer>` (`maxItems`), a `TextField` with `getInputTypes()={"color"}` (`defaultColor`), and a plain `TextField` (`chartHeight`). Writes straight back into the `GanttChartFormControlSettings` model → persisted to `properties.settings`. (`palette` has no panel input — it is only editable in code/JSON.) `getSettingsControlPanel()` returns this class. The runtime task modal `GanttItemEditPanel` edits `GanttItemDto` (name/description per-locale, dates, progress, color, dependencies, attachments) and calls `writeData()` + `redrawChart()` on save/delete — that touches field data, never `settings`.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §10 (already field-complete) · doc 14 catalog note ("real, hand-authorable, unused in samples") · `gantt/GanttChartFormControlPlugin.java`, `gantt/GanttChartFormControlSettings.java`, `gantt/GanttChartFormControlSettingsPanel.java`, `gantt/dto/{GanttDataDto,GanttItemDto,GanttAttachmentDto}.java`, `gantt/dialog/GanttItemEditPanel.java`.

### `dynaform.form.list.field.plugin` — repeatable sub-grid form control (a nested list/child-table with per-row + create actions and reusable inline forms)

- **Config slot:** `properties.settings` (`stringValue` = JSON of `ListFormControlSettings extends FormControlSettings`) · **Editor:** no modal editor — configured via the right-hand form-control settings panel `ListFormControlSettingsPanel` (`getSettingsControlPanel()`; no `editComponent` override) · **Hand-authored in .mrjun:** yes — a builder places this control inside a form/parsis grid, binds it to a collection field, and hand-writes `settings` (columns, actions, subforms). It is a "Form Controls" plugin (`@PluginConfig(group="Form Controls")`), not base skeleton.
- **Function:** Renders a bound List/`ArrayNode` field as a card with a header, a paginated table (10/page) whose columns are `columnSettings`, "Create new" buttons above it (`createNewActions`), and a per-row actions dropdown (`userActions`). Non-direct actions open a nested `dynaform.list.item.plugin` sub-form (create/edit an item) via `FormPlugin.replaceContentWith`; direct actions (e.g. Delete) mutate the array in place. Actions can share one reusable form via `subforms`/`formIdByActionId`. Action visibility is gated by per-action predicates; `refreshOnCompleteByActionId` re-renders other components when an action completes. Reads config through `getContent().getJsonProperty("settings", ListFormControlSettings.class)`.
- **Config JSON** (decoded — `erp`, `inventoryCount.lines`, abbreviated):
```jsonc
{
  "userActions": { "actions": [
    { "id": "b6fe9f83-…", "localizedNames": {"en_US":"Edit","ru_RU":"Редактировать"},
      "localizedButtonNames": {"en_US":"Edit"}, "direct": "off", "icon": "pe-7s-pen" },
    { "id": "d5312dfb-…", "localizedNames": {"en_US":"Delete"}, "direct": "on", "icon": "pe-7s-trash" }
  ], "errors": [] },
  "createNewActions": { "actions": [
    { "id": "58d4dbc0-…", "localizedNames": {"en_US":"Create"}, "direct": "off", "icon": "pe-7s-plus" }
  ], "errors": [] },
  "columnSettings": [
    { "id": "3a0818a2-…", "localizedNames": {"en_US":"Line Number"}, "fieldExpression": "lineNumber" },
    { "id": "ffe37c3e-…", "localizedNames": {"en_US":"Product"},     "fieldExpression": "product.code" },
    { "id": "1c4316b1-…", "localizedNames": {"en_US":"Quantity"},    "fieldExpression": "countedQuantity" }
  ],
  "localizedHeaderLabel": { "en_US":"Lines", "ru_RU":"Позиции" },
  "headerIcon": "pe-7s-list",
  "subforms": [ { "id": "c167f25e-…", "localizedNames": {"en_US":"Item Form"} } ],
  "formIdByActionId": { "58d4dbc0-…":"c167f25e-…", "b6fe9f83-…":"c167f25e-…" },
  "refreshOnCompleteByActionId": { "d5312dfb-…":"totalsPanelId,relatedListId" },
  // ---- inherited from FormControlSettings (the field binding) ----
  "scope": "CRUD",
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "inventoryCount",
  "fieldExpression": "lines",
  "name": "Lines",
  "dataClass": "java.util.List"
}
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `userActions` | `UserTaskActionsDto` `{actions:[ActionDto…], errors:[]}` | Per-row actions (Edit/Delete). Non-direct → opens the item form; `direct:"on"` → deletes/mutates the row inline. | `{}` (lazy) |
| `createNewActions` | `UserTaskActionsDto` | "Create new item" buttons shown above the table (open the item form to append). | `{}` (lazy) |
| `columnSettings` | array `ProcessTableFormControlSettings` | Table columns. Each carries `id`, `localizedNames`, `fieldExpression` (dotted paths supported, e.g. `product.code`); also `dataClass`, `scope`, `contextIdentifier`, `crudAlias`, `enumName`/`enumValues`/`enumDisplayField`, `trueIcon`/`falseIcon` for boolean cells, and `money`/`currency`/`moneyFormat`/`moneyDecimals`/`dateFormat` for money and date cells. ⚠️ This control's column panel does **not** persist a `dataClass`, and every one of those render capabilities (boolean icons, right-alignment, money, date format) is gated on it — so hand-write `dataClass` on the column if you want them here. | `[]` (lazy) |
| `localizedHeaderLabel` | `Map<localeString,String>` | Heading above the list per locale (3-tier locale fallback). Blank → `"List Items"`. | null |
| `headerIcon` | String | Pe-7s heading icon class. Blank → `"pe-7s-list"`. | null |
| `subforms` | array `SubformSettings` `{id, localizedNames}` | Reusable inline forms. `id` = the child-content identifier the item-form fields live on (a UUID, or an action id for migrated legacy forms). Author-facing name only. | null (lazy `[]`) |
| `formIdByActionId` | `Map<actionId,subformId>` | Which subform each action renders. Missing entry → `getRenderFormId()` falls back to the action's own id (legacy). Lets Create+Edit share one form. | null (lazy `{}`) |
| `refreshOnCompleteByActionId` | `Map<actionId, CSV>` | Per-action CSV of IRefreshable component identifiers to re-render when that action completes (create/edit saved, or direct action confirmed). | null (lazy `{}`) |
| *(inherited)* `scope` | enum `GLOBAL`\|`CONTEXT`\|`CRUD` | Binding scope of the list field. | null |
| *(inherited)* `contextIdentifier` / `crudAlias` / `fieldExpression` | String | Locate the bound collection (`fieldExpression` = the array field, e.g. `lines`). | null |
| *(inherited)* `name` / `dataClass` | String | Control label; `dataClass` written as `java.util.List` (whitelist is `ArrayList`/`ObjectNode`). | null |

`ActionDto` (`UserTaskActionsDto.ActionDto`) used here: `id` (UUID), `localizedNames`, `localizedButtonNames` (in-form button caption; defaults to `localizedNames`), `predicateIdentifier` (visibility predicate; `"null"`→null), `onBeforeUserTaskStartRuleIdentifier` (EXECUTION rule before opening; `"null"`→null), `direct` (`"on"`/`"off"`; `isDirect()`=`equals("on")`), `icon` (Pe-7s class), `submitForm` (Boolean; default true).

- **Editor / settings panel:** `ListFormControlSettingsPanel` (right-hand, a form + autosave `sync(true)` on change). Sections: per-locale **Header label** (`LocalizedTextFieldsPanel`) + **Header icon** (`Pe7sDropDownField`); **Columns** accordion (`ListColumnPanel` — column name + Field-Expression dropdown fed by the item type's `crudAlias.fieldExpression`); **Forms** management (`ListSubformsPanel` — list/rename/create; "Delete unused forms" modal `DeleteUnusedFormsPanel` offers only forms no action references); **Table Item Actions** + **Create New Actions** (`ProcessTableUserActionsPanel`, each action getting a per-action **Form** picker `ListActionFormSelectorPanel` and a multi-select **Refresh On Complete** picker `RefreshableContentSelectorField`); and a one-click **Create default actions** button that seeds Create/Edit (sharing one "Item Form" subform) + a direct Delete. Legacy per-action forms are auto-migrated to first-class subforms on open (`migrateLegacyForms`). All writes go back into the `settings` blob.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §7 (field-level tables) and §8 (the `dynaform.list.item.plugin` sub-form node + id-linkage invariant); also [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md). · `ListFormControlPlugin.java`, `ListFormControlSettings.java`, `SubformSettings.java`, `ListFormControlSettingsPanel.java`, `FormControlSettings.java`.

### `dynaform.form.rimm.autocomplete.field.plugin` — type-ahead text field whose suggestions are fetched server-side from an EXECUTION rule on every keystroke

- **Config slot:** `properties.settings` (`stringValue` = `FormControlRimmAutoCompleteFieldSettings` JSON) · **Editor:** no editor — configured via the form-control **settings right-panel** (`FormControlSettingsRimmAutoCompleteFieldControlPanel`) · **Hand-authored in .mrjun:** **yes** — a builder drops this control into a `FormPlugin`/filter form and writes its `settings` blob (bound `ruleIdentifier` + `key`/`displayName` + field mapping).
- **Function:** Renders a richwicket `AutoCompleteField` (`<input>`, not `<select>`). As the user types, `getChoices(s)` calls `workflowExecutionService.execute(realm, client, ctx, ruleIdentifier, {filterBy: s})` — the typed text reaches the rule as `attrs.get('filterBy')` (the **only** path that propagates it as an attr; the CRUD-mode branch was removed because it dropped `filterBy` and returned all rows). The rule must end in `service.global.conversion.toAutoCompleteOptions(list,"<display>")` (or `…Localized`); `convertToValueMap(response, key, displayName)` turns the result into suggestions. Supports GLOBAL/CONTEXT/CRUD scope and filter-form mode. Data classes: String, Integer, Long, Short, Float, Double, Boolean, ObjectNode. Optional "Show Nav" hover icon opens the source CRUD's page in a new tab (only when the bound rule matches the canonical Choices-From-CRUD autocomplete shape, `ChoicesRuleShape.forAutocomplete`).
- **Config JSON** (decoded — a real node: field "Brand" over CRUD `ticket`):
```jsonc
{
  "ruleIdentifier": "68249981-bc65-46df-a253-18ed1b0e1957", // EXECUTION rule; gets attrs.filterBy = typed text
  "key": "name",              // response field stored as the form value
  "displayName": "name",      // response field shown as suggestion text
  "showChoicesOnClick": true, // pop the list on focus/click, before typing
  "searchField": "name",      // CRUD column the rule's LIKE filters on (usually = display)
  "showNav": false,           // hover icon → open source CRUD page (only for CRUD-shape rules)
  "name": "Brand",            // control label
  "dataClass": "java.lang.String",
  "scope": "CRUD",            // GLOBAL | CONTEXT | CRUD
  "contextIdentifier": "fe5e9b03-5b46-4fde-846b-6a01362bc553",
  "crudAlias": "ticket",
  "fieldExpression": "brand", // bound CRUD column
  "eventComponentMappings": []
}
// Minimal (Gson omits absent fields): { "ruleIdentifier":"…", "key":"code", "displayName":"name", "scope":"CRUD" }
```
- **Fields:** (own + autocomplete-specific; the shared `FormControlSettings` block — mandatory/prohibited/default-value/localized/between/enum/jsonNode/conditionalValidations/eventComponentMappings — is documented once in doc 25 and applies identically here)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `ruleIdentifier` | String | EXECUTION rule that returns option pairs; receives typed text as `attrs.get('filterBy')`. Must tail in `toAutoCompleteOptions[Localized]`. | null |
| `key` | String | Response field used as the **stored** value. For Choices-From-CRUD both `key` and `displayName` are set to the display field (one suggestion per row). | null |
| `displayName` | String | Response field **shown** in the suggestion list. | null |
| `showChoicesOnClick` | boolean | Show the suggestion list immediately on click/focus without typing. | false |
| `searchField` | String | CRUD column the server-side LIKE filters on (the rule's `filterBy` target). Auto-mirrors `displayName` unless overridden to search a different column. | null (mirrors display) |
| `showNav` | boolean | Runtime hover icon that opens the page hosting the source CRUD table/tree in a new tab. Panel only surfaces the checkbox when the rule body is a canonical Choices-From-CRUD autocomplete shape. | false |
| `name` | String | Control label / display name. | null |
| `filterKey` | String | Filter-form only: key for the value in the filter map / page params. | null |
| `dataClass` | String | FQN of the value type (e.g. `java.lang.String`). | null |
| `scope` | enum | `GLOBAL` \| `CONTEXT` \| `CRUD` — where the value binds. | null |
| `contextIdentifier` | String | Context id (CONTEXT/CRUD scope). | null |
| `crudAlias` | String | Target CRUD alias (CRUD scope). | null |
| `fieldExpression` | String | Bound CRUD column. | null |

- **Editor / settings panel:** `FormControlSettingsRimmAutoCompleteFieldControlPanel` (Rimm Settings fieldset). **Rimm Rule** = `RuleIdentifierSelectorField` (EXECUTION rules) with a create-suggestion `<Crud> <Field> Choices`; a **Choices From CRUD** button opens `AutoCompleteChoicesFromCrudDialog` which generates the Groovy autocomplete rule and writes back `ruleIdentifier`, `key`=`displayName`=chosen display field, and `searchField`. **Show Choices On Click** checkbox → `showChoicesOnClick`. **Show Nav** checkbox (row visible only when `isNavCandidate()`) → `showNav`. **Display Field** + **Search Field** render as a `DropDownChoice` when the rule preview yields option keys, else a `TextField`; Display drives both `key` and `displayName` (and mirrors into `searchField` when blank), Search sets `searchField` independently. All inputs autosave via the synced framework (`sync(true)`), which persists to `properties.settings` and re-renders the live control.
- **See also / source:** [doc 02 §4](02-form-controls-reference.md) (field-level table, real examples, HTML, the Choices-rule contract & searchable-pipeline in §4a) · doc 25 (shared mandatory/validation/default/events block) · `RimmAutoCompleteFieldFormControlPlugin.java`, `FormControlRimmAutoCompleteFieldSettings.java`, `AutocompleteFilterControlSettings.java`, `FormControlSettings.java`, `FormControlSettingsRimmAutoCompleteFieldControlPanel.java`, `AutoCompleteChoicesFromCrudDialog.java`

### `dynaform.form.rimm.drop.down.field.plugin` — rule- or enum-driven single-select `<select>` form control

- **Config slot:** `properties.settings` (`stringValue` = JSON of `FormControlRimmDropDownFieldSettings`) · **Editor:** no inline `editComponent` — configured via the right-hand settings panel (`FormControlSettingsRimmDropDownFieldControlPanel`, and the **Choices From CRUD** sub-dialog); the filter-form variant uses `DropdownFilterControlSettingsPanel` · **Hand-authored in .mrjun:** yes — a builder drops it into a form/filter (usually via Generate-Fields-from-CRUD for FK/enum columns) and hand-writes the `settings` blob.
- **Function:** Renders a bound field as a dropdown. Three option sources, resolved in this order at runtime (`initEditable`): **(1) enum-bound** — if the field carries `enumName`/`enumValues`, options come straight from the project enum registry (no rule); **(2) search-enabled** — if `searchEnabled`, a Select2 picker re-fetches options server-side on every keystroke via a generated `RIMM_FILT_<alias>_<field>` LIKE rule; **(3) rule-based** — otherwise it executes `ruleIdentifier` (an EXECUTION rule that MUST end in `service.global.conversion.toSelectOptions(list,"<key>","<display>")`) with the live form context, so dependent/cascading dropdowns see fields the user just changed. Read-only forms render a `<label>` instead of the `<select>`. Optional `showNav` hover icon opens the source CRUD page (new tab) or the enum-values editor modal. Emits a `change` event for event-component mappings.
- **Config JSON** (decoded — rule-based, the common case):
```jsonc
{
  "scope": "CRUD",                    // GLOBAL | CONTEXT | CRUD
  "contextIdentifier": "77cd568d-…",  // context/CRUD this control binds into
  "crudAlias": "inventoryCount",
  "fieldExpression": "plant.id",      // bound field (dot-path)
  "dataClass": "java.lang.String",    // bound value type (or enum FQN in enum mode)
  "name": "Plant",                    // label / caption
  "filterKey": "plant.id",            // key in the filter map (filter-form mode)
  "ruleIdentifier": "996e41a0-…",     // EXECUTION rule → toSelectOptions(list,key,display)
  "key": "id",                        // option property STORED as the value
  "displayName": "name",              // option property SHOWN to the user
  "rowsInPage": 99,                   // option page size, clamped 1..99
  "searchEnabled": false,
  "showNav": false,
  "eventComponentMappings": [ { "eventName": "change", "componentIdentifier": "569b322b-…" } ],
  "mandatoryValidationMessages": {}, "conditionalValidations": []
}
```
Enum-bound mode replaces `ruleIdentifier` with `enumName` + `enumValues` (`{CONSTANT:{prop:value}}`) + `enumFieldNames`; `key`/`displayName` then point at enum **properties** (usually `name`/`displayName`), `dataClass` is the real enum FQN (e.g. `com.devsegment.erp.dto.enums.BomType`) or synthetic `dynamic.<EnumName>` for a class-less FREE/DB enum. The stored value is always the constant's `name()`.
- **Fields:** (own + dropdown-specific; shared base fields at bottom)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `ruleIdentifier` | String (UUID) | EXECUTION rule producing option pairs; body MUST end in `toSelectOptions(list,"<key>","<display>")` (`…Localized` for localized CRUD) — NOT a raw `findAll` (→ "No results found"). Absent in enum mode. | null |
| `key` | String | Option property whose value is **stored** (usually `id`; in enum mode an enum property). | null |
| `displayName` | String | Option property **shown** as the label (`name`, `label`; enum-property in enum mode). Blank → constant name only. | null |
| `showNav` | boolean | Renders the hover "open source" icon (CRUD page in new tab, or enum editor modal). Panel surfaces the checkbox only when the rule body matches a Choices-From-CRUD/Enum shape (`ChoicesRuleShape`). | false |
| `rowsInPage` | Integer | Page size for the option fetch; passed as the rule's `rowsInPage` attr. Clamped ≤99 on save; legacy null → 99. | null (→99) |
| `searchEnabled` | boolean | ON → Select2 picker with per-keystroke server-side LIKE search (swaps `ruleIdentifier` to `searchRuleIdentifier`). OFF → plain `DropDownChoice`. Forced OFF when bound field becomes enum. | false |
| `searchField` | String | Source-CRUD field the LIKE filter runs on; drives generation of `acFindBy<X>Like` + the `RIMM_FILT` rule. Required with `searchEnabled`. | null |
| `prevRuleIdentifier` | String (UUID) | Snapshot of the original `ruleIdentifier`, restored when search is unchecked (originals are never deleted). | null |
| `searchRuleIdentifier` | String (UUID) | Identifier of the generated `RIMM_FILT_<alias>_<field>` search rule (kept for O(1) re-toggle). | null |
| `enumName` | String | Registry name of the bound project Enumeration; switches panel + runtime into enum mode (skips the rule). | null |
| `enumValues` | Map<String,Map<String,String>> | Per-constant property snapshot `{CONSTANT:{prop:value}}` (mirror of `FieldDto.enumValues`); drives enum rendering offline. | null |
| `enumFieldNames` | List<String> | Enum property names (`name` + declared fields) used to populate the Key/DisplayName pickers. | null |
| `scope` | enum | `GLOBAL` / `CONTEXT` / `CRUD` — binding target family. | null |
| `contextIdentifier` / `crudAlias` / `fieldExpression` | String | Bound context/CRUD id, CRUD alias, and dot-path field expression. | null |
| `dataClass` | String | Bound value type FQN (`java.lang.String`, `…Integer`, `ObjectNode`, or an enum FQN / `dynamic.<Enum>`). | null |
| `name` / `filterKey` | String | Control caption; filter-map key (filter-form mode). | null |
| _shared base (all form controls, see doc 25/02):_ `alwaysMandatory`, `mandatoryPredicateIdentifier`, `mandatoryValidationMessages`, `conditionalValidations`, `eventComponentMappings` (this control fires `change`), `alwaysProhibited`, `prohibitedPredicateIdentifier`, `localized`, `defaultValueEnabled`/`defaultValueStatic`/`defaultValue`/`defaultValueLocalized`/`defaultValueRuleIdentifier`, `between`/`betweenMapping`, `jsonNodeExpression`/`jsonNodeValueType` | mixed | Mandatory/validation/prohibition/events/default-value/between/JSON-path infra inherited from `FormControlSettings`. | null/[]/{} |

- **Editor / settings panel:** No inline editor. The right-panel `FormControlSettingsRimmDropDownFieldControlPanel` (a form, autosave-on-change via `sync(true)`) exposes: a **Rimm Rule** selector (`RuleIdentifierSelectorField`, EXECUTION rules, hidden when the bound field is enum) with a **Choices From CRUD** button that generates the choices rule and writes back `ruleIdentifier`+`key`+`displayName`; a **Rows in page** `NumberTextField` (browser hint 1..99, clamped in the model setter — no `RangeValidator`, to stay autosave-compatible); **Key**/**Display Name** as populated `DropDownChoice`s when a rule preview or enum properties are available (else free-text fallback); an **"I want to search"** block (checkbox + source-CRUD field selector) that generates the LIKE methods + `RIMM_FILT` rule; and a **Show Nav** checkbox shown only for nav-candidate rules/enums. Binding to an enum field hides the Rule/Key/Search rows and drives Key/DisplayName from the enum's property names.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §3 (field-level table, enum mode, both JSON examples, HTML) · [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md), [14-plugin-catalog-all.md](14-plugin-catalog-all.md) · `dropdown/RimmDropDownFieldFormControlPlugin.java`, `dropdown/FormControlRimmDropDownFieldSettings.java`, `dropdown/FormControlSettingsRimmDropDownFieldControlPanel.java`, `filter/config/DropdownFilterControlSettings.java`, `form/controls/config/FormControlSettings.java`

### `dynaform.form.text.field.plugin` — single-line form input bound to a CRUD/context/global field (renders as text, number, checkbox, or numeric range by `dataClass`)

- **Config slot:** `properties.settings` (`stringValue` = JSON-decoded `FormControlSettings`) · **Editor:** no `editComponent` (`BaseFormControl.editComponent` returns null) — configured through the **Form Settings** right-nav panel (`TextFieldFormControlSettingsControlPanel`, tabbed) that authors open by clicking the control · **Hand-authored in .mrjun:** yes — a builder drops this node into a `FormPlugin`/`FilterFormPlugin` page (typically via Generate-Fields-from-CRUD) and writes/edits its `settings` JSON.
- **Function:** The workhorse text form control. At render time `initEditable()` picks the widget from the resolved `dataClass`: `String` → `<input>` (`cntrlStr`); a numeric boxed type (`Integer/Long/Short/Byte/Float/Double/BigDecimal/BigInteger`) → `NumberTextField` (`cntrlNum`); `Boolean` → checkbox (`cntrlCheckBox`); `ObjectNode`/`JsonNode` without a wired projection falls back to a plain text input. With `between=true` **and** a numeric type it renders a from/to pair (`cntrlNumBetween`). A prohibited control (via predicate, `alwaysProhibited`, or the always-prohibited fast path) renders a read-only `<label>` (`cntrlLabel`). Value read/write goes through `BaseFormControl.getFieldModel()` per `scope` (GLOBAL→`attrs`, CONTEXT→context attrs, CRUD→`crudDataMap[alias]`), with localization, JSON-path projection, and null-default substitution layered on. It is the **only** control offering numeric Between mode; no separate NUMBER/CHECKBOX plugins exist — those are just a Text field with the matching `dataClass`.
- **Config JSON** (decoded — real `erp` node, `alwaysMandatory` numeric field):
```jsonc
{
  "scope": "CRUD",                                  // GLOBAL | CONTEXT | CRUD (serialized as enum name)
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "billOfMaterials",
  "fieldExpression": "baseQuantity",                // field name/path within the target object
  "alwaysMandatory": true,
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  "name": "Base Quantity",                          // author-facing label
  "filterKey": "baseQuantity",                      // active only inside a FilterFormPlugin
  "dataClass": "java.math.BigDecimal"               // drives which widget renders
}
```
- **Fields:** (Text field adds **no** fields of its own — it deserializes the base `FormControlSettings`; whole applicable set below)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | Author-facing control label (the visible label is a separate `nct.label.plugin`). | null |
| `filterKey` | String | Page-param key; used only inside a `FilterFormPlugin`. Generator mirrors it to `fieldExpression` in normal forms. | null |
| `dataClass` | String (FQN) | Java type of the value; selects the widget + coercion. Whitelist: `String`, `Integer`, `Long`, `Short`, `Byte`, `Float`, `Double`, `BigDecimal`, `BigInteger`, `Boolean`, `ObjectNode`. `null`/`ObjectNode`/`JsonNode` (unprojected) → plain text input. | null |
| `scope` | enum `GLOBAL`\|`CONTEXT`\|`CRUD` | Where the value is stored (serialized as constant name). | null |
| `contextIdentifier` | String (UUID) | Target context; required for CONTEXT/CRUD. | null |
| `crudAlias` | String | CRUD alias within the context (CRUD scope only). Nulled on save if `contextIdentifier==null`. | null |
| `fieldExpression` | String | Field name/path (dotted allowed) within the target object/DTO. | null |
| `jsonNodeExpression` | String | JSON path inside an `ObjectNode`/`JsonNode` field (e.g. `metadata.category`). | null |
| `jsonNodeValueType` | String (FQN) | Value type at `jsonNodeExpression` (used with it). | null |
| `enumValues` / `enumFieldNames` / `enumName` | Map / List / String | Enum-binding snapshot + registry name (rarely relevant for a plain text field; present via base). | null |
| `between` | Boolean | Numeric range mode → renders a from/to pair; `from`=primary mapping, `to`=`betweenMapping`. Only numeric types eligible. | null (false) |
| `betweenMapping` | `BetweenFieldMapping` | Upper-bound target (scope/context/crud/field or filterKey); value type NOT stored (shared with primary). | null |
| `prohibitedPredicateIdentifier` | String (UUID) | PREDICATE rule; `true` → control renders read-only label. Runs every render. | null |
| `alwaysProhibited` | Boolean | Unconditional read-only, no executor round-trip. | null (false) |
| `localized` | Boolean | Store per-locale (`localize[field][locale]` for CRUD, `attrs.__localize__[...]` for GLOBAL/CONTEXT). Needs multi-language form + (CRUD) a `@LocalizationField` ObjectNode column. | null (false) |
| `alwaysMandatory` | Boolean | Field always required. | null (false) |
| `mandatoryValidationMessages` | `Map<String,String>` | Localized "required" messages (`locale → text`). | `{}` |
| `mandatoryPredicateIdentifier` | String (UUID) | PREDICATE; `true` → conditionally mandatory (when not `alwaysMandatory`). | null |
| `eventComponentMappings` | array `EventComponentMapping` | On a DOM event, run optional rules then refresh a target component. | `[]` |
| `conditionalValidations` | array `ConditionalValidation` | Predicate-gated validations with severity + localized messages. | `[]` |
| `defaultValueEnabled` | Boolean | Substitute a default when the bound value is null. | null (false) |
| `defaultValueStatic` | Boolean | `true`/null → static default; `false` → rule-driven. | null (=true) |
| `defaultValue` | String | Static scalar default, coerced to `dataClass` at render. | null |
| `defaultValueLocalized` | `Map<String,String>` | Per-locale static default (localized fields). | null |
| `defaultValueRuleIdentifier` | String (UUID) | EXECUTION rule whose return becomes the default (rule mode). | null |

- **Editor / settings panel:** No `editComponent`. When an author (NCT_AUTHOR/ADMIN) clicks the control it fires a `showSettings` AJAX event that opens the **Form Settings** right-nav panel (`TextFieldFormControlSettingsControlPanel`, subclass of `FormControlSettingsControlPanel<FormControlSettings>`). This panel exposes the field mapping (scope/context/crud/fieldExpression/dataClass), field configs (default value, prohibited, mandatory), validation, and events, and — because `TextFieldFormControlSettingsControlPanel.betweenSupported()` returns true and `betweenTypeEligible()` allows the eight numeric FQNs — the **Between** toggle when the bound type is numeric. Inside a filter form, `showFilterSettings` opens `TextFieldFilterControlSettingsControlPanel` instead. On submit the panel writes the mutated `FormControlSettings` back via `getContent().setJsonProperty("settings", …)` + `saveContent()` and re-attaches the fresh `ContentDomain`.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §"1. Text field" (field-level base table + HTML), [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) (how the generator emits these nodes) · `TextFieldFormControlPlugin.java`, `TextFieldFormControlSettingsControlPanel.java`, `BaseFormControl.java`, `config/FormControlSettings.java` (+ `FilterControlSettings.java`, `config/BetweenFieldMapping.java`).

### `dynaform.form.textarea.field.plugin` — multi-line text input form control (a `<textarea>`)

- **Config slot:** `properties.settings` (`stringValue` = escaped-JSON of `FormControlSettings`, the shared form-control settings DTO) · **Editor:** no inline editor (`BaseFormControl.editComponent()` returns `null`) — edited through the right-nav **Form Settings** panel (`FormControlSettingsControlPanel`), opened from the gear icon · **Hand-authored in .mrjun:** yes — a builder drops this node into a form's `nct.parsis.plugin` grid (usually via *Generate fields*, id `fld_gen_slot_<hash>_<row>_<col>`) and hand-writes its `settings` JSON to bind it to a field.
- **Function:** Renders a multi-line `<textarea wicket:id="cntrlStr">` bound to a `String` (or `ObjectNode`) field via `scope` + `contextIdentifier`/`crudAlias` + `fieldExpression` (`initEditable`). When prohibited (`alwaysProhibited`, or `prohibitedPredicateIdentifier` evaluates true) it forces `dataClass=java.lang.String`, hides the textarea and instead renders a read-only `<label wicket:id="cntrlStrLabel">` with `setEscapeModelStrings(false)` — so a prohibited textarea renders its value as **HTML**. Adds nothing to the base: identical config surface as the Text field, minus numeric/checkbox/between modes.
- **Config JSON** (decoded — a real node with a localized `description`):
```jsonc
{
  "scope": "CRUD",                                 // GLOBAL | CONTEXT | CRUD — where the value is written
  "contextIdentifier": "871f974f-e775-401a-adfc-e822110f3b99", // rep-objects.contexts[].identifier (UUID)
  "crudAlias": "product_categories",               // CRUD alias inside the context (CRUD scope only)
  "fieldExpression": "description",                // field/path on the target (dotted allowed)
  "localized": true,                               // store per-locale text (localize[field][locale])
  "name": "Description",                           // authoring label (drawn by a sibling nct.label.plugin)
  "filterKey": "description",                      // page-param key; active only in a FilterForm
  "dataClass": "java.lang.String",                // ONLY String or ObjectNode allowed here
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": []
}
```
- **Fields:** no plugin-specific delta — the entire config is the shared base `FormControlSettings` (→ `FilterControlSettings`). Fields relevant to a textarea (full backing-line table in doc 02):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `scope` | enum `"GLOBAL"`\|`"CONTEXT"`\|`"CRUD"` | Where the value is read/written; serialized as the constant name | null |
| `contextIdentifier` | String (UUID) | Target context (`rep-objects.contexts[]`); needed for CONTEXT/CRUD | null |
| `crudAlias` | String | CRUD alias within the context (CRUD scope); nulled on save if `contextIdentifier==null` | null |
| `fieldExpression` | String | Field name/path on the target object (dotted allowed) | null |
| `name` | String | Authoring label; the visible caption is a separate `nct.label.plugin` | null |
| `filterKey` | String | Page-param key; generator sets `== fieldExpression`; only used inside a FilterForm | null |
| `dataClass` | String (FQN) | Value type — **`java.lang.String` or `com.fasterxml.jackson.databind.node.ObjectNode` only** (`supportedDataClasses`); prohibited mode forces String | null |
| `jsonNodeExpression` / `jsonNodeValueType` | String / FQN | For an `ObjectNode` field: nested JSON path + the value type at that path | null |
| `localized` | Boolean | Store per locale (`localize[field][locale]` for CRUD; `attrs.__localize__[field][locale]` for GLOBAL/CONTEXT); needs a multi-language parent form (+ `@LocalizationField` column for CRUD) | null (false) |
| `alwaysProhibited` / `prohibitedPredicateIdentifier` | Boolean / UUID | Read-only unconditionally (no executor call) / via PREDICATE rule → renders the HTML label instead of the textarea | null |
| `alwaysMandatory` / `mandatoryPredicateIdentifier` / `mandatoryValidationMessages` | Boolean / UUID / `Map<locale,String>` | Required always / by predicate; localized "required" messages | null / null / `{}` |
| `conditionalValidations` | `ConditionalValidation[]` | Predicate-driven validations with severity + localized messages | `[]` |
| `eventComponentMappings` | `EventComponentMapping[]` | On a DOM event, run rules and refresh a target component | `[]` |
| `defaultValueEnabled` / `defaultValueStatic` / `defaultValue` / `defaultValueLocalized` / `defaultValueRuleIdentifier` | Boolean / Boolean / String / `Map<locale,String>` / UUID | Substitute a default when the bound value is null — static (scalar or per-locale) or an EXECUTION rule's return | null |

(`between`/`betweenMapping`, `enumName`/`enumValues`/`enumFieldNames`, dropdown/autocomplete keys are inherited on the DTO but never apply to a textarea — the textarea has no between/enum mode.)

- **Editor / settings panel:** No editor and no plugin-specific settings panel. Authors edit it through the shared right-nav **Form Settings** panel (`FormControlSettingsControlPanel`), which reads/writes this same `properties.settings` blob (`FormSettingsWithContext` carries `supportedDataClasses()` = {String, ObjectNode} + `supportsFieldConfigs()`). `saveSettings()` persists back into `properties.settings.stringValue`.
- **See also / source:** [02-form-controls-reference.md](02-form-controls-reference.md) §2 (Text Area — example JSON, HTML, `supportedDataClasses` row) and the base field-by-field table · `textarea/TextAreaFieldFormControlPlugin.java` · base `form/controls/BaseFormControl.java` · DTO `form/controls/config/FormControlSettings.java` → `filter/config/FilterControlSettings.java`

### `dynaform.form.tree.picker.plugin` — single-select hierarchical (tree) picker form control, lazy-fed by a choices rule

- **Config slot:** `properties.settings` (`stringValue` = `FormControlTreePickerSettings` JSON) · **Editor:** no (no `editComponent`; config via the Form-Control settings **right panel** `FormControlSettingsTreePickerControlPanel` + the `TreeChoicesFromCrudDialog` "Choices From CRUD" modal) · **Hand-authored in .mrjun:** yes — a builder drops this control onto a form/list page and hand-writes its `settings` (rule id, key/display, crudAlias, fieldExpression, displayMode).
- **Function:** Renders a Fancytree-backed single-select picker that binds one id into a CRUD field. Children are lazy-fetched one level at a time: each expand step runs the configured `EXECUTION_RULE` with `attrs.get('parentId')` set (empty for roots) and projects the rule's `toSelectOptions` pairwise list into Fancytree nodes. Architecturally identical to the Drop Down control, plus a parent-walk. The closed-picker label, `PATH` breadcrumb, and ancestor auto-expand resolve nodes via `service.crud.<alias>.get(id)` — the source CRUD's alias and parent-filter field are recovered by regex from the rule body (`service.crud.<alias>.findByParent([<field>: attrs.get('parentId')])`), NOT stored in settings.
- **Config JSON** (decoded):
```jsonc
{
  // --- tree-specific (FormControlTreePickerSettings) ---
  "displayMode": "NAME_ONLY",              // NAME_ONLY | PATH ; null → NAME_ONLY
  "rowsInPage": 99,                        // page size per lazy children fetch (clamp 1..99)
  // --- inherited from DropdownFilterControlSettings ---
  "ruleIdentifier": "ba630a9a-81a6-40e6-80b1-3c069fad5fb7", // EXECUTION rule; fetches one page of children by attrs.get('parentId')
  "key": "id",                            // field in the rule's option rows used as the stored value
  "displayName": "name",                  // field in the rule's option rows shown as the node label
  "showNav": false,                        // hover "open source" icon (only when rule matches a Choices-From-CRUD/Enum shape)
  // --- inherited from FormControlSettings / base mapping ---
  "scope": "CRUD",                        // CRUD | CONTEXT | GLOBAL
  "contextIdentifier": "77cd568d-…",
  "crudAlias": "product",                 // bound CRUD; must expose get(id) or the label stays blank
  "fieldExpression": "category.id",        // where the picked value is written
  "name": "Category",
  "dataClass": "java.lang.String",         // supported: String/Integer/Long/Short/Float/Double/Boolean/ObjectNode
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": []
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `displayMode` | enum `NAME_ONLY` \| `PATH` | Closed-picker label style. `PATH` walks the parent chain and renders `Root > Mid > Leaf`, capped at 20 levels (`PATH_DEPTH_CAP`). | null → `NAME_ONLY` |
| `rowsInPage` | Integer | Page size passed as `attrs.get('rowsInPage')` on every lazy children fetch; panel clamps to [1,99] on save. | null → `99` at runtime |
| `ruleIdentifier` | String | `EXECUTION_RULE` id; called per expand with `attrs.get('parentId')`, must `return service.global.conversion.toSelectOptions(list,"<key>","<display>")` (never raw `findAll`). *(inherited)* | — |
| `key` | String | Field in the rule's option rows used as the stored node value. *(inherited)* | — |
| `displayName` | String | Field in the option rows used as the visible node/label text. *(inherited)* | — |
| `showNav` | boolean | Show hover icon that opens the choices source (only surfaced when the rule matches a Choices-From-CRUD/Enum shape). *(inherited)* | `false` |
| `scope` / `contextIdentifier` / `crudAlias` / `fieldExpression` | String / enum | Standard binding target of the picked value; `crudAlias` must expose `get(id)`. *(inherited from `FormControlSettings`)* | — |
| `name` / `dataClass` | String | Control label + the JVM type the id is coerced to. *(inherited)* | — |
| `mandatory*` / `conditionalValidations` / `eventComponentMappings` / default-value / prohibited fields | see `FormControlSettings` | Full shared form-control config surface (validation, events, defaults, prohibition) applies. *(inherited)* | — |

- **Editor / settings panel:** No node-level `editComponent`. The right-side settings panel (`FormControlSettingsTreePickerControlPanel` + `.html` `Tree Picker Settings` fieldset) autosaves via `synced(...)`/`AjaxFormComponentUpdatingBehavior("change")`: a **Rimm Rule** `RuleIdentifierSelectorField` (filtered to `EXECUTION_RULE`) → writes `ruleIdentifier`; a **Choices From CRUD** button opening `TreeChoicesFromCrudDialog` which picks source CRUD + parent field, generates the recursive choices rule (and ensures `findByParent`/`findAllByParent` exist), and callbacks `ruleIdentifier`+`key`+`displayName`; a **Rows in page** `NumberTextField` (browser 1..99 hint via `AttributeModifier`, actual clamp in the LambdaModel setter — no `RangeValidator` so autosave `onUpdate` always fires) → `rowsInPage`; a **Key / Display Name** container that previews the rule with `parentId=null` and surfaces its result fields as dropdowns (free-text fallback when preview fails) → `key`/`displayName`; a **Display Mode** dropdown (`NAME_ONLY`/`PATH`) → `displayMode`. Filter-form variant uses `TreePickerFilterControlSettingsPanel`.
- **See also / source:** [02 §6 Tree Picker](02-form-controls-reference.md) (field-level table already present) · choices-rule contract §4a · `TreePickerFormControlPlugin.java`, `FormControlTreePickerSettings.java`, `TreePickerDisplayMode.java`, `FormControlSettingsTreePickerControlPanel.java`, `TreeChoicesFromCrudDialog.java`.


---

## Form infrastructure

### `dynaform.filter.form.plugin` — standalone filter-panel container that holds filter controls above a table

- **Config slot:** `properties.filterFormModel` (`stringValue` = JSON of `FilterFormDto`; empty `{}` or `{name,description,waitSelector}`) · **Editor:** no — `editComponent()` returns `null` (`FilterFormPlugin.java`); configured via the right-nav "Filter Settings" panel only · **Hand-authored in .mrjun:** yes — a project builder drops this node onto a page (group `"Forms"`), hand-writes the (usually empty) `filterFormModel`, and builds its child control subtree; NOT a base-skeleton/admin node.
- **Function:** Renders a filter panel above a CRUD/tree/process table. It is a **simplified `FormPlugin`** — `extends NctBasePlugin<FilterFormDto>` with **no ContextDataDto, no scopes, no form groups** (`FilterFormPlugin.java`, class javadoc). It holds child `dynaform.form.*.field.plugin` controls in an inner container, collects their values into a **transient** `Map<String,Object> filterValues` (never persisted), and exposes them via `IFilterFormProvider.getFilterValues()`. A sibling `dynaform.filter.submit.button.plugin` reads that map on click and broadcasts `onFilterSubmit` page-wide, so every table on the page re-queries with the values arriving in its fetch rule's `attrs`. On init it force-sets `reuseItems=true` on its content node.
- **Config JSON** (decoded):
```jsonc
// Almost always empty ({}) — the DTO is display metadata only; the real behavior
// comes from the child controls' filterKey + the submit button, not this blob.
{
  "name": "Service Center Filters",     // optional: display name/identifier
  "description": "Filter by branch/status", // optional: free text
  "waitSelector": ".blocking-result-panel"  // optional: CSS selector to block-wait on during submit
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | Display name/identifier of the filter form (labeling only; no runtime effect). | `null` |
| `description` | String | Optional free-text description of the filter form. | `null` |
| `waitSelector` | String | CSS selector for the block-wait overlay applied on submit (e.g. `.blocking-result-panel`, `#myResultPanel`). Surfaced at runtime as the filter form's wait selector. | `null` |
| ~~`crudAlias`~~ | String | **Inactive** — declared but commented out in both the DTO (`FilterFormDto.java`) and the settings panel; not read anywhere. Do not author. | — |

> Runtime-only state (NOT in the config blob): `filterValues` — a transient `Map<String,Object>` populated by the child controls' `filterKey` and read by the submit button; exposed through `IFilterFormProvider` (`getFilterValues`/`setFilterValue`/`getWaitSelector`).

- **Editor / settings panel:** No inline editor. A right-nav tab **"Filter Settings"** (`FilterFormSettingsControlPanel`, registered in `showSettings()`) with three fields bound to the settings object — **Name** (`TextField`), **Description** (`TextArea`), **Wait selector** (`TextField`). When `DynaformSettingsConfig.isAutosave()` each field fires `saveFilterFormModel` on `change` (blur) and toasts; otherwise a Save button submits. On save the plugin writes back `getContent().setJsonProperty("filterFormModel", …)` and re-sets the model (`saveFilterFormModel`). (A CRUD-alias dropdown exists in the panel source but is commented out.)
- **See also / source:** [04-crud-table-plugin.md § Standalone Filter Form](04-crud-table-plugin.md#standalone-filter-form-filter-panel-above-the-table) (full node-tree recipe: inner container must be `identifier="filter.parsis"`; child controls bind via **`filterKey`** not `filterField`; `filterKey`↔table-type mapping table; clone/id-nulling pitfalls) · catalog stub [14](14-plugin-catalog-all.md) · `FilterFormPlugin.java`, `FilterFormDto.java`, `FilterFormSettingsControlPanel.java`, `IFilterFormProvider.java`

### `dynaform.form.groups.landingplugin` — per-group form landing page: lists a form group's forms and predicate-routes the user to the right form

- **Config slot:** `properties.*` (`stringValue` = **no config blob** — only empty generic CMS slots `className`/`styleName`/`tagProperties`) · **Editor:** no (`editComponent()` returns `null`, `FormGroupLandingPlugin.java`; real editor is commented out) · **Hand-authored in .mrjun:** **yes** — a builder places this node into a per-group *landing* `siteMapPage`, but writes **no** JSON on the node: the group is bound by the URL param `?group=<identifier>` and all settings live in the linked `FormGroupDto` (rep-objects `formGroups[]`), not in `properties`.
- **Function:** The runtime landing for one form group. Resolves the `FormGroupDto` from `?group=` (`initPluginContent` → `formGroupService.findByIdentifier`) and renders the group's forms via `FormsPanel` (list with edit/delete; a click calls `goLandingPage` → navigates to that form's own content page). When opened *with* navigation params (`settingsName`+`actionId`, plus `crudId`/`processIdentifier`), `navigateToFormIfNeed` dispatches by the referenced settings' `type` (`ProcessTable`/`CrudTable`/`CrudTree`) and evaluates the group's `predicateFormMapping` (CRUD-edit, CRUD-create, workflow-task, workflow-start) to auto-redirect to the first form whose predicate returns `true` (else the blank-predicate fallback form). In authoring mode it also registers a passed `?context=` onto the group and offers a "Create new form" breadcrumb button that opens `FormEditorPanel` to create a form + its `siteMapPage` + optional mapping predicate.
- **Config JSON** (decoded): *node carries no config blob*; the effective config is the `FormGroupDto` reached via `?group=` (shown here as it appears in `rep-objects.json.formGroups[]`):
```jsonc
// content-tree node (branches.json) — empty generic slots only, group bound via ?group= on the parent page:
{ "pluginName": "dynaform.form.groups.landingplugin",
  "properties": { "className": {"stringValue": ""}, "styleName": {"stringValue": ""}, "tagProperties": {"stringValue": ""} } }

// effective config — FormGroupDto in rep-objects.json.formGroups[]:
{ "identifier": "<groupUuid>",                         // referenced by ?group=
  "name": "Bill of Materials Forms",                   // convention "<Crud> Forms"
  "contextIdentifiers": ["<ctxUuid>"],                 // predicate-context fallback
  "contentPageIdentifier": "<landingPageId>",          // this plugin's siteMapPage
  "formGroupsPageIdentifier": "<groupListPageId>",     // the dynaform.form.groups.plugin list page
  "placeFormsNextToLanding": false,                    // new form pages: child(false)/sibling(true) of landing
  "predicateFormMapping": { "mapping": [ { "predicateIdentifier": "<ruleUuid>", "formIdentifier": "<formUuid>" } ] } }
```
- **Fields** (of the resolved `FormGroupDto` — `FormGroupDto.java`; the node has none):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | Group display name; auto-gen convention `"<Crud> Forms"` | — (required in settings) |
| `contextIdentifiers` | List<String> | Group's contexts; first is used as predicate-eval context when settings/CRUD don't supply one (`getContextIdentifier`) | null/empty |
| `contentPageIdentifier` | String | CMS `ContentDomain.identifier` of THIS landing page; stamped on save | null |
| `formGroupsPageIdentifier` | String | CMS identifier of the group-LIST page (`dynaform.form.groups.plugin`) | null |
| `placeFormsNextToLanding` | boolean | Where "Create new form" anchors the new form page: `false` = child of landing, `true` = sibling | `false` |
| `predicateFormMapping` | PredicateFormMappingDto | Ordered `{predicateIdentifier, formIdentifier}` pairs; array order = priority, blank-predicate row = fallback form | null → empty on access (`getPredicateFormMapping`) |

- **Editor / settings panel:** No inline editor. Configured two ways, both writing to `formGroups[]`/`forms[]` (never the node): **(1)** the right-nav **"Form Group Settings"** panel `FormGroupSettingsControlPanel` — a form bound to `FormGroupDto` (autosave-on-change) with `RequiredTextField name`, `MultiSelectField contextIdentifiers`, `PredicateFormMappingField predicateFormMapping` (the "Form Mapping" predicate→form editor incl. "Create Action Based Rule" seeded from the originating `?settingsName=` actions), and `CheckBox placeFormsNextToLanding` (flipping it prompts to relocate existing form pages); saves via `formGroupService.save`. **(2)** the **"Create new form"** breadcrumb button (`createUpdateFormGroup`) opens `FormEditorPanel`, creates the `FormDto` + a new `siteMapPage` (unique alias, `formModeIdentifier` stamped) and optionally appends a mapping predicate.
- **See also / source:** [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) (field-level `formGroups[]` schema + navigation source-map) · `FormGroupLandingPlugin.java`, `FormGroupSettingsControlPanel.java`, `FormGroupDto.java`, `FormsPanel.java`

### `dynaform.form.plugin` — the form container node that hosts form-controls and submits their values through the workflow/CRUD engine
- **Config slot:** `properties.formModeIdentifier` (`stringValue` = **form UUID pointer — no config blob**; the real config lives server-side in a `FormDto` loaded via `formService.findByIdentifier`) · **Editor:** yes — `FormEditorPanel` (single form: name, parent page, form group, optional mapping predicate) + a rich right-nav **"Form"** settings tab (`FormSettingsControlPanel`) · **Hand-authored in .mrjun:** yes — a builder drops this node into a form page's `parsis` (a `siteMapPage`, `layout:"Form"`) and sets `formModeIdentifier`; but its field-level config is edited through the panels, not typed into the JSON.
- **Function:** The runtime form. It resolves nav-mode from URL params (`processIdentifier` / `settingsName`+`actionId` / `crudId`) into CRUD-create/edit, workflow-task, start-form or global-action mode; renders the form-control tree inside a form; on submit collects every control's value into a `ContextDataDto` and hands it to `FormSubmissionService` / `ReactorCrudService` — **but in CRUD mode (nav-mode `crudId` / `settingsName`+`actionId`) `BaseFormControl.bindToCrudMode` first re-binds EVERY control to the action's `crudAlias` + `contextIdentifier` in `CRUD` scope, whatever the persisted `scope` says** (filter forms and nested list-item subtrees are the only exemptions), so the persisted GLOBAL/CONTEXT decides the binding only on the no-row entry points ([02](02-form-controls-reference.md) §Where the value LANDS). It also evaluates `hiddenConfigs` predicates to hide content, enforces mandatory + conditional field validation, and can save/restore drafts.
- **Config JSON** (decoded):
```jsonc
// (1) the NODE placed in the .mrjun (inside a form page's parsis) — NO config blob, just a pointer:
{ "name": "form", "pluginName": "dynaform.form.plugin",
  "properties": {
    "formModeIdentifier": { "propertyType": "STRING",  "stringValue": "2c18b1c2-4016-486d-a0ca-990164624782" },
    "reuseItems":         { "propertyType": "BOOLEAN", "booleanValue": true }   // auto-set true on first render
  },
  "children": [ /* dynaform.form.*.field.plugin controls live here */ ] }

// (2) the server-side FormDto that stringValue points at — the ACTUAL configuration surface:
{
  "identifier": "2c18b1c2-4016-486d-a0ca-990164624782",
  "name": "Stock Transfer Form",
  "contentIdentifier": "<form page ContentDomain.identifier>",
  "formGroup": { "identifier": "<groupUuid>", "name": "..." },
  "contextIdentifiers": ["871f974f-e775-401a-adfc-e822110f3b99"],  // form contexts (first = default for predicates)
  "validators":       [],                                          // form-level VALIDATION_RULE ids (usually [])
  "actionValidators": [],                                          // validators bound to a specific action (usually [])
  "hiddenConfigs": [
    { "predicateIdentifier": "<ruleUuid>", "contentIdentifiers": ["<contentUuid>", "..."] }
  ],
  "multiLanguage": false,                                          // per-locale field values + language selector
  "allowDrafts":   false                                           // renders a "Drafts" dropdown button
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `formModeIdentifier` *(node property)* | STRING | The only load-bearing bit in the .mrjun: UUID linking the page/node to its `FormDto`. Set by the editor/settings save (`content.setProperty(...)`). | — (required to render a form) |
| `reuseItems` *(node property)* | BOOLEAN | Wicket list-reuse flag on the parsis wrapper; auto-forced to `true` on first render. | `true` |
| `name` *(FormDto)* | String | Form name; defaults to the page's content name if blank. | page name |
| `contentIdentifier` *(FormDto)* | String | `ContentDomain.identifier` of the owning form page. | — |
| `formGroup` *(FormDto)* | FormGroupDto | The form group this form belongs to (drives group contexts + predicate→form routing). | — |
| `contextIdentifiers` *(FormDto)* | List\<String\> | Contexts available to the form; merged with the group's contexts; first is the default context for rules. | empty (lazy) |
| `validators` *(FormDto)* | List\<String\> | Form-level VALIDATION_RULE identifiers run at submit (Global Validation Rules). | empty |
| `actionValidators` *(FormDto)* | List\<FormActionValidator\> | Validators bound to a specific `{workflowIdentifier, workflowTaskId, actionId, validator}` (Action-Based Validation). | empty |
| `hiddenConfigs` *(FormDto)* | List\<HiddenContentConfig\> | Each `{predicateIdentifier, contentIdentifiers[]}`: when the predicate is true, those content nodes are hidden (author can toggle "Show Hidden Components"). | empty |
| `multiLanguage` *(FormDto)* | Boolean | Enables per-locale field values + a language selector (only effective when tenant has >1 locale). | `false`/null |
| `allowDrafts` *(FormDto)* | Boolean | Lets end-users save/resume partial form state; adds a "Drafts" breadcrumb dropdown. | `false`/null |
- **Editor / settings panel:** Double-click opens `FormEditorPanel` (fields: `name` RequiredTextField, `parentPageIdentifier` page selector, `formGroup` dropdown, and — only in create-in-group dialogs — a "Mapping predicate" `RuleIdentifierSelectorField` defaulting to a shared "True" rule, persisted into the group's `PredicateFormMappingDto`); on submit it `formService.save`s the `FormDto` and writes its identifier back into `formModeIdentifier`. The right-nav **"Form"** tab (`FormSettingsControlPanel`, autosave-on-change) edits: `contextIdentifiers` (MultiSelect) → unlocks a **"Generate fields from CRUD"** modal (`GenerateFieldsFromCrudDialog`, pre-filled from the originating CRUD/Process settings nav-data), `formGroup`, `multiLanguage` (only if >1 locale), `allowDrafts`, `name`, a `FormValidationSettingsPanel` (global + action validators), a `HiddenContentConfigPanel` (predicate→content hiding), plus "View Audit Logs" / "Show Context Data" buttons in CRUD/process mode. Each change fires the `saveFormModel` event → `FormPlugin.saveFormModel` → `formService.save`.
- **See also / source:** deep field-level table in [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) (§ FormDto fields + representative JSON), settings/validation/events in [25-form-settings-validation-and-events.md](25-form-settings-validation-and-events.md), controls in [02-form-controls-reference.md](02-form-controls-reference.md), catalog stub [14-plugin-catalog-all.md](14-plugin-catalog-all.md) · `FormPlugin.java`, `FormDto.java`, `FormEditorPanel.java`, `FormSettingsControlPanel.java`, `HiddenContentConfig.java`, `FormActionValidator.java`

### `dynaform.list.item.plugin` — the nested Create/Edit sub-form (subform container) a List embeds for one item

- **Config slot:** `properties.*` (`stringValue` = **no config blob** — properties are exactly `className` / `isParsis`(BOOLEAN) / `styleName` / `tagProperties`, the generic parsis-container set; **NO `settings` slot**) · **Editor:** no (`editComponent()` returns `null`; `showSettings()` is empty) · **Hand-authored in .mrjun:** yes (structure only) — the builder must place this node as a child of the List node with the right `identifier`, but it holds **no config JSON of its own**; all behavior is set at runtime by the parent List.
- **Function:** Sub-form (`ListItemFormPlugin`, `group="Forms"`, `hideInKicker=true`) for creating/editing one item of a List (`dynaform.form.list.field.plugin`). It clones the parent form's `contextData`, maps the current item into a temp CRUD location, lets ordinary child form controls read/write there, validates (mandatory + conditional + custom VALIDATION rules via `FormSubmissionService`), then merges the item back into the parent list array. Implements `IFormContextProvider` (feeds child controls the item-scoped context), `INestedFormDataProvider` (feeds `NestedFormMetadata`), `IMultiLanguageForm` (per-locale field editing).
- **Config JSON** (decoded):
```jsonc
// The node itself carries NO settings blob. Its persisted properties are just:
// { "className": "...", "isParsis": true, "styleName": "...", "tagProperties": "..." }
// Everything below is set at RUNTIME by ListFormControlPlugin.getPlugin() when the
// Create/Edit action fires — it is NOT stored in the .mrjun:
//   setModelObject(action)                 // UserTaskActionsDto.ActionDto (the List action)
//   setParentContextData(getContextData()) // parent FormPlugin context (deep-cloned)
//   setCreateMode(true|false)              // create vs edit
//   setEditItemIndex(rowIndex)             // edit mode only
//   setParentListScope(settings.scope)     // GLOBAL | CONTEXT | CRUD
//   setParentListFieldExpression(...)      // e.g. "lines"
//   setParentContextIdentifier(...)        // CONTEXT/CRUD scopes
//   setParentCrudAlias(...)                // CRUD scope
//   setRefreshOnCompleteIdentifiers(...)   // per-action Refresh-On-Complete list
```
- **Fields:** — none — (no config DTO is deserialized; a content re-init never calls `getJsonProperty`). The plugin's generic `NctBasePlugin<UserTaskActionsDto.ActionDto>` model object is injected live by the parent List, not read from the node. Child fields bind to the temp location — `contextIdentifier:"__temp_list_item_context__"`, `crudAlias:"__temp_item__"`, `scope` = parent list scope (constants `TEMP_CONTEXT_IDENTIFIER`/`TEMP_CRUD_ALIAS`, `ListItemFormPlugin.java`).

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | node has no `settings` slot / no config DTO | — |

- **Editor / settings panel:** None. `editComponent()` returns `null` and `showSettings()` is a no-op, so there is no property/settings UI. At runtime the plugin renders a form wrapping a `nct.parsis.plugin id="form.parsis"` grid (`PluginWrapperOfContentPanel("content", getContent(), "nct.parsis.plugin", "form.parsis")`) plus an optional `FormLanguageSelectorPanel` when the parent form is multi-language. Breadcrumb buttons: **Submit** (localized from the action name → `handleSubmit()`), **Auto add fields** (author/admin only → `GenerateFieldsFromCrudDialog` in nested mode, generates controls from the list item type into the temp location), and **Close**. On first render it force-sets the node property `reuseItems=true` and saves the content. Nothing here is authored/persisted as config.
- **See also / source:** [02-form-controls-reference.md §8 "List item (subform)"](02-form-controls-reference.md) (node shape, id-linkage invariant `identifier == getRenderFormId(actionId)`, the two real M1/M3 shapes) · [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) (form-group framing) · `ListItemFormPlugin.java` (runtime wiring `ListFormControlPlugin.java`)


---

## CRUD tables & trees

### `crud.table.plugin` — the platform's primary paginated table/list for one CRUD

- **Config slot:** `properties.model` (`stringValue` = a JSON **string** of `CrudTablePluginModel`) · **Editor:** none — `editComponent()` returns `null` (`CrudTablePlugin.java`); all config is done through the right-side **"CRUD Table Settings"** panel (`CrudTableSettingsControlPanel`). · **Hand-authored in .mrjun:** **yes** — a builder drops a `crud.table.plugin` node onto a page's `nct.parsis.plugin` and hand-writes the whole `model` JSON (crudAlias, columns, filters, create/edit actions, import). Expect roughly one such node per list page. (Not a base-skeleton/system plugin.)
- **Function:** Renders an HTML table of rows of a **single CRUD** (`crudAlias`), with pagination, configured columns, optional inline filters, header "create" breadcrumb buttons and a per-row action dropdown (Edit/Delete/custom, direct or form-navigating). It does **not** read the CRUD service directly — it fetches each page by **running an EXECUTION rule** (`findRuleIdentifier`, "Find — <crud>") that returns `{content, totalElements, totalPages}`, so the same control works for static and dynamic CRUDs. Extends `NctBaseModelObjectObjectSyncedPlugin<CrudTablePluginModel>`; loads config via `getContent().getJsonProperty("model", CrudTablePluginModel::new)`; the same model is additionally mirrored into a `rep-objects.settings[]` object of `type:"CrudTable"` (join key `setting.name == node.uniqueIdentifier`) — an object, not a string.

- **Config JSON** (decoded — `properties.model.stringValue`):
```jsonc
{
  "contextIdentifier": "77cd568d-…",          // UUID of the context rules use for context.<ctx>.<alias>.…; blank → falls back to crudAlias
  "crudAlias": "inventoryCount",               // REQUIRED — short alias of the CRUD shown
  "columnSettings": [                           // CrudTableColumnSettings[]
    { "id": "70609b84-…", "localizedNames": { "en_US": "Document Number" },
      "fieldExpression": "documentNumber", "dataClass": "java.lang.String" },
    { "id": "b398d7a5-…", "localizedNames": { "en_US": "Status" },
      "fieldExpression": "status", "dataClass": "com.devsegment.erp.dto.enums.CountStatus",
      "enumDisplayField": "displayName", "enumName": "CountStatus",
      "enumValues": { "DRAFT": { "displayName": "Draft", "name": "DRAFT" } /* …snapshot… */ } }
  ],
  "filterSettings": [                           // CrudTableFilterSettings[] — usually []
    { "id": "e32f6918-…", "name": "Active", "filterField": "active",
      "dataClass": "java.lang.Boolean", "defaultValue": "true" }
  ],
  "createActions": { "actions": [ /* ActionDto — header breadcrumb buttons, no row context */ ] },
  "editActions":   { "actions": [ /* ActionDto — per-row dropdown menu           */
    { "id": "2aff4c25-…", "localizedNames": { "en_US": "Edit" },
      "localizedButtonNames": { "en_US": "Edit" }, "icon": "pe-7s-pen",
      "formGroupIdentifier": "0ff5ec4c-…", "direct": false,
      "predicateIdentifier": "7fcdc152-…", "onBeforeCompleteRuleIdentifier": "ce7c2851-…" },
    { "id": "ba4e285f-…", "localizedNames": { "en_US": "Delete" }, "icon": "pe-7s-trash",
      "direct": true, "onBeforeCompleteRuleIdentifier": "1851ea31-…" }
  ] },
  "rowsPerPage": 15,
  "findRuleIdentifier": "1eb749c2-…",           // fetch rule; blank → auto-created on first render
  "importSettings": { "enabled": false, "localizedButtonNames": {}, "actions": [] }
}
```
> The Excel-header→field import mapping is **not** in `model`; it is written at runtime to a separate STRING slot `properties.importMapping.stringValue` (`ImportMappingDto`), and a post-import error report to `properties.lastImportReport` — omit both when hand-authoring.

- **Fields** (root `CrudTablePluginModel`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `contextIdentifier` | String (UUID) | Context that rules/predicates use to reach other CRUDs (`context.<ctx>.<alias>.data.get()`). Blank → runtime falls back to `crudAlias`. | `null` |
| `crudAlias` | String | **Required.** Short alias of the CRUD whose rows the table shows (`inventoryCount`, `product_categories`). Blank → renders "CRUD Table (not configured)". | `null` |
| `columnSettings` | `CrudTableColumnSettings[]` | Displayed columns (see sub-table). | `[]` |
| `filterSettings` | `CrudTableFilterSettings[]` | Inline filter descriptors; values pushed into the fetch rule's `attrs` by `filterField`. Almost always `[]`. | `[]` |
| `createActions` | `CrudTableActionsDto` `{actions:ActionDto[]}` | **Header/breadcrumb** buttons above the table (run with NO selected row) — bare "Create". | `null` |
| `editActions` | `CrudTableActionsDto` `{actions:ActionDto[]}` | **Per-row** dropdown actions (Edit/Delete/View/Post/Cancel…). Any action that operates on a specific record MUST live here. | `null` |
| `rowsPerPage` | int | Pagination page size (used as SQL page size, not Wicket's clamped count). | `15` |
| `findRuleIdentifier` | String (UUID) | EXECUTION rule "Find — <crud>" returning a page. Blank + a bound CRUD → auto-created (idempotent) and persisted on first render. | `null` |
| `importSettings` | `CrudTableImportSettingsDto` | CSV/Excel import config (see sub-table). | `null` |

Nested — `CrudTableColumnSettings[]`: `id`(UUID), `localizedNames`(Map locale→String, the header), `fieldExpression`(dotted path e.g. `plant.code`), `dataClass`(FQN: `java.lang.String/Integer/Long`, `java.math.BigDecimal`, `java.time.LocalDate`, `java.lang.Boolean`, or an enum FQN), `enumDisplayField`(enum prop to render; blank/`"name"`→constant name), `enumValues`(Map constName→{prop→value} snapshot), `enumName`(project Enumeration registry name), `trueIcon`/`falseIcon`(Boolean columns only — `pe-7s-*` icon shown instead of raw true/false), `money`(boolean; numeric columns only — render the cell as money), `currency`(symbol `$`/`€`/`֏` or ISO code `USD`; free text, blank → amount only), `moneyFormat`(`US`/`EUROPEAN`/`SPACE_COMMA`/`SPACE_DOT`/`SWISS`/`INDIAN`/`PLAIN`; blank → `US`), `moneyDecimals`(Integer 0–6; null → 2), `dateFormat`(moment.js pattern for a `java.time.LocalDate`/`LocalDateTime`/`Instant` column, e.g. `DD/MM/YYYY HH:mm`; blank → the raw ISO value). Numeric+boolean cells auto right-align (render-only).

Nested — `CrudTableFilterSettings[]` (exactly 5 fields): `id`(UUID), `name`(plain String label, NOT localized), `filterField`(field of the CRUD's **filter class**, e.g. `active`/`minPrice`), `dataClass`(FQN, drives `defaultValue` coercion via `getTypedDefaultValue()`), `defaultValue`(String, coerced by dataClass).

Nested — `CrudTableActionsDto.ActionDto` (distinct from the workflow ActionDto — no `validationRuleIdentifiers`/`taskId`): `id`(UUID), `localizedNames`(Map — the label; there is NO plain `name` field, an old `"name"` renders blank), `localizedButtonNames`(Map — non-direct submit-button label, falls back to `localizedNames`), `icon`(`pe-7s-*`), `formGroupIdentifier`(UUID — non-direct target form group; form gets URL params `group`,`settingsName`,`caller`,`actionId`,and for edit `crudId`), `direct`(primitive boolean — `true`=run rules+refresh, no form; `false`=navigate to form), `predicateIdentifier`(UUID PREDICATE visibility rule, evaluated per-row with the row's CRUD context, fail-closed; blank→always visible), `onBeforeStartRuleIdentifier`+`onBeforeCompleteRuleIdentifier`(UUID EXECUTION rules — there is NO built-in create/update/delete; all writes happen explicitly in these Groovy rules), `submitForm`(nullable Boolean, `null`=true — non-direct: whether to validate+persist the form or only run rules).

Nested — `CrudTableImportSettingsDto`: `enabled`(boolean master toggle, `false`→no Import button), `localizedButtonNames`(Map, fallback `"Import"`), `buttonIcon`(`pe-7s-*`), `visibilityPredicateIdentifier`(UUID PREDICATE), `duplicateDetectionPredicateIdentifier`(UUID PREDICATE), `duplicateAction`(`DuplicateAction` enum: `OVERRIDE`/`IGNORE`/`DUPLICATE`/`ASK`), `actions`(`CrudTableImportActionDto[]` = `{id, localizedNames, ruleIdentifiers:String[]}` pre-import rule bundles).

- **Editor / settings panel:** No inline editor. Authors configure via the right-side **CRUD Table Settings** panel (`CrudTableSettingsControlPanel`, opened by the header ⚙ button; auto-shown to NCT_AUTHOR/ADMIN). Its sections write back into `CrudTablePluginModel`: CRUD chooser (`crudAlias`) + context; **fetch-rule** picker with a one-click "Find — <crud>" default (`findRuleIdentifier`); **Create Actions** and **Edit Actions** accordions (`CrudTableUserActionsPanel` — add/drag-sort actions, per-action name/icon/direct/predicate/form-group + "Add Create/Update/Delete Rule" buttons); **Columns** (`CrudTableColumnPanel`); **Filters** (`CrudTableFilterPanel`); **Import** (`CrudTableImportSettingsPanel`); a one-click **"Create Default Actions"** that seeds a True predicate + a "<crud> Forms" form group + Create/Update/Delete EXECUTION rules + the three wired actions; and a **Save Settings** button that persists the model back to `properties.model` and the `CrudTable` settings mirror (`getKey()` = `"CrudTableSynced"`).
- **See also / source:** [04-crud-table-plugin.md](04-crud-table-plugin.md) (exhaustive per-field tables, fetch-rule body, default-actions, standalone filter form, import flow) · [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) (shared column/filter types) · `CrudTablePlugin.java`, `CrudTablePluginModel.java`, `CrudTableColumnSettings.java`, `CrudTableFilterSettings.java`, `CrudTableActionsDto.java`, `CrudTableImportSettingsDto.java`, `CrudTableSettingsControlPanel.java`.

### `crud.tree.plugin` — hierarchical (self-referential) CRUD table: rows are entities of one CRUD, nested by a parent reference, children lazy-loaded on expand

- **Config slot:** `properties.model` (`stringValue` = JSON of `CrudTreePluginModel`; the *same* JSON is mirrored into a `SettingsDto` of `type:"CrudTree"` keyed by `name == node.uniqueIdentifier` — a persistence artifact, the node still renders only from `properties.model`) · **Editor:** no in-place editor — `editComponent()` returns `null` (`CrudTreePlugin.java`); all config is authored in the right-nav **CRUD Tree Settings** panel (`CrudTreeSettingsControlPanel`) · **Hand-authored in .mrjun:** **yes** — a builder drops this node into a `siteMapPage` and hand-writes the whole config into `properties.model.stringValue` (business page plugin, `group="Lists"`, not part of the console skeleton; most projects carry none — you meet it only where an entity is genuinely hierarchical, e.g. a category tree).
- **Function:** Displays one CRUD's rows as a Wicket `TableTree`. Roots load via the fetch-rule with `parentId=null`; each node's children lazy-load on expand via `findByParent(filter{parentId=<node id>})`. First column = tree column (expand junction + first field value); remaining columns are data cells. `createActions` render as breadcrumb buttons (create/create-child), `editActions` as a per-row dropdown (edit/delete/…). Read at `getContent().getJsonProperty("model", CrudTreePluginModel::new)` (`CrudTreePlugin.java`).
- **Config JSON** (decoded — `erp`/`category`):
```jsonc
{
  "contextIdentifier": "77cd568d-...",        // optional: context for Groovy-rule CRUD access; blank → falls back to crudAlias
  "crudAlias": "category",                     // REQUIRED for data — blank renders "CRUD Tree (not configured)"
  "parentFieldExpression": "parent.id",        // DTO-side parent path (read a row's parent ref)
  "parentFilterFieldExpression": "parentId",   // FILTER-side key the provider puts in the findByParent filter map
  "columnSettings": [                           // FIRST = tree column (expand + value); rest = data columns
    { "id": "aed6...", "name": "Code", "fieldExpression": "code", "dataClass": "java.lang.String" },
    { "id": "3791...", "name": "Name", "fieldExpression": "name", "dataClass": "java.lang.String" }
  ],
  "filterSettings": [                           // CRUD-filter-class controls; defaultValue folded into every findByParent call
    { "id": "917e...", "name": "Active", "filterField": "active", "dataClass": "java.lang.Boolean", "defaultValue": "true" }
  ],
  "createActions": { "actions": [               // breadcrumb buttons (create / create-child)
    { "id": "f420...", "localizedNames": {"en_US": "Create Category"},
      "localizedButtonNames": {"en_US": "Create Category"}, "icon": "pe-7s-plus",
      "formGroupIdentifier": "25df...", "direct": false,
      "onBeforeCompleteRuleIdentifier": "1636..." } ] },
  "editActions": { "actions": [                 // per-row dropdown (edit / create-child / delete)
    { "id": "7c07...", "localizedNames": {"en_US": "Edit Category"}, "icon": "pe-7s-pen",
      "formGroupIdentifier": "25df...", "direct": false, "onBeforeCompleteRuleIdentifier": "a76e..." },
    { "id": "f20a...", "localizedNames": {"en_US": "Delete Category"}, "icon": "pe-7s-trash",
      "direct": true, "onBeforeCompleteRuleIdentifier": "d16f..." } ] },
  "rowsPerPage": 2147483647,                    // Integer.MAX_VALUE — trees show all rows
  "findRuleIdentifier": "da08..."               // EXECUTION rule findByParent — auto-created on render if blank
}
```
- **Fields** (`CrudTreePluginModel`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `contextIdentifier` | String | Optional context id for Groovy rules to reach other CRUDs; when blank, action-predicate/rule execution falls back to `crudAlias` as the context. | — |
| `crudAlias` | String | Alias of the CRUD shown by the tree. Blank → placeholder "CRUD Tree (not configured)"; must be non-blank for any data. | — |
| `parentFieldExpression` | String | **DTO-side** parent path, e.g. `"parent.id"` — read a row's parent reference. Fallback filter key when `parentFilterFieldExpression` is blank (legacy configs). | — |
| `parentFilterFieldExpression` | String | **FILTER-side** parent field name, e.g. `"parentId"`. Exactly what `CrudTreeDataProvider` writes into the filter map for `findByParent`. Either parent field alone is enough to render; in practice set both. | — |
| `columnSettings[]` | `CrudTableColumnSettings[]` | Columns. `[0]` becomes the tree column (expand + first field value); the rest are data columns. Shared type with `crud.table.plugin` (nested fields below). | `[]` |
| `filterSettings[]` | `CrudTableFilterSettings[]` | CRUD-filter-class controls. Each non-blank `defaultValue` (type-coerced via `getTypedDefaultValue()`) is seeded into `filter` and mixed into every `findByParent` call. | `[]` |
| `createActions` | `CrudTableActionsDto` | Create/create-child actions → breadcrumb buttons (`breadcrumbButtons`). ⚠️ A `direct:true` CREATE on the tree runs the `onBefore*` rules **and** the built-in `create` — inserts a blank node, unlike the table. | — |
| `editActions` | `CrudTableActionsDto` | Row actions → dropdown in the leftmost column (`CrudTreeActionsPanel`). Each node lazily fetches its *visible* actions (predicate-filtered) via the `fetchActions` AJAX listener. | — |
| `rowsPerPage` | int | **DEAD on a tree — never read** (`CrudTreePlugin.java` hardcodes `Long.MAX_VALUE`); a crud tree has NO pagination and this setting does nothing. See [05](05-crud-tree-and-process-table.md). | `2147483647` |
| `findRuleIdentifier` | String | Id of the `EXECUTION_RULE` the tree runs to fetch children (`service.crud.<alias>.findByParent(...)`). Auto-created on render when `crudAlias` set and this is blank, via `crudDataRuleService.ensureFindByParentRule(...)`, then persisted into both layers. Can be omitted from the export. | — (auto) |

Nested `CrudTableColumnSettings` (shared with `crud.table.plugin`): `id`, `name` *(@Deprecated legacy header)*, `localizedNames{locale→text}`, `fieldExpression`, `dataClass` (FQCN), plus enum/boolean rendering — `enumDisplayField`, `enumValues{const→{prop→val}}`, `enumName`, `trueIcon`/`falseIcon` (Pe-7s icons for boolean cells), `money`(boolean; numeric columns only — render the cell as money), `currency`(symbol `$`/`€`/`֏` or ISO code `USD`; free text, blank → amount only), `moneyFormat`(`US`/`EUROPEAN`/`SPACE_COMMA`/`SPACE_DOT`/`SWISS`/`INDIAN`/`PLAIN`; blank → `US`), `moneyDecimals`(Integer 0–6; null → 2), `dateFormat`(moment.js pattern for a `java.time.LocalDate`/`LocalDateTime`/`Instant` column, e.g. `DD/MM/YYYY HH:mm`; blank → the raw ISO value). · Nested `CrudTableFilterSettings`: `id`, `name`, `filterField` (filter-class field), `dataClass`, `defaultValue` (String, type-coerced). · Nested `CrudTableActionsDto.ActionDto`: `id`, `localizedNames`, `localizedButtonNames` (submit-button label, falls back to name), `icon`, `formGroupIdentifier`, `direct` **(boolean — note process table uses string `"on"/"off"`)**, `predicateIdentifier` (optional visibility predicate; blank = always visible), `onBeforeStartRuleIdentifier`, `onBeforeCompleteRuleIdentifier`, `submitForm` (Boolean, `null`=true).

- **Editor / settings panel:** No `editComponent`. The gear button (author/admin) opens the right-nav **CRUD Tree Settings** panel (`CrudTreeSettingsControlPanel`, a form bound to the settings object, autosave-on-change): Context dropdown, CRUD alias dropdown (clears columns/filters/parent/find-rule on change), a **data-rule** selector (`RuleIdentifierSelectorField` over `EXECUTION_RULE`), DTO-side parent-field dropdown and filter-side parent-field dropdown/textfield (picking the DTO field mirrors into the blank filter slot), **Create Actions** / **Edit Actions** accordions (`CrudTableUserActionsPanel`), a **Create Default Actions** button (wires a shared form group + Create/Edit/Create-Child/Delete actions and their rules), a **Column** panel and a **Filter** panel. `onSubmit`/autosave write the model into `properties.model` (ContentDomain) and mirror it into the `CrudTree` `SettingsDto`, then `ensureFindByParentMethod(...)` scaffolds/diffs the CRUD's `findByParent` Groovy method (conflict modal on divergence).
- **See also / source:** **doc [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)** — already field-complete (full JSON example, `CrudTreePluginModel` table, actions-DTO table, `findByParent` fetch-rule + Groovy body, render HTML). Shared column/filter/action semantics in [04-crud-table-plugin.md](04-crud-table-plugin.md). · `CrudTreePlugin.java`, `CrudTreePluginModel.java`, `CrudTreeSettingsControlPanel.java`, `CrudTreeDataProvider.java`, `CrudTableTree.java`, `CrudTreeActionsPanel.java`, shared `CrudTableColumnSettings.java` / `CrudTableFilterSettings.java` / `CrudTableActionsDto.java`.

### `process.table.pluin` — a paged table over **workflow process instances** (not CRUD rows), with start/row actions

- **Config slot:** `properties.model` (`stringValue` = `ProcessTablePluginModel` JSON) · **Editor:** yes — minimal inline `editComponent` (workflow dropdown only) **+** the real config is the right-nav **"Process Table Settings"** accordion (6 sections) · **Hand-authored in .mrjun:** **yes** — a builder places this node on a business page and hand-writes the `model` JSON (workflow, columns, indexes, filter, start/global actions). ⚠️ Note `empty.mrjun` ships **1 seeded** Process Table node (on `Home`) with a populated `model` that must be **repointed** to the project's own workflow/group, or deleted — not left as-is.
- **Function:** Reads `properties.model` via `getContent().getJsonProperty("model", ProcessTablePluginModel::new)` (`ProcessTablePlugin.java`), then renders a `DataView` of Flowable process instances filtered by `processGroupIdentifier` + `workflowIdentifier` + `filterExpression` (over `indexSettings`). Columns are read per-row from process/context/CRUD data by `scope`. Row actions are assembled from three origins — `userStartProcessActions` (breadcrumb "start" buttons), `globalActions` (row dropdown, predicate-gated), and live per-userTask BPMN actions (fetched at runtime, **not** in the node). Base class `NctBaseModelObjectObjectSyncedPlugin<ProcessTablePluginModel>`; synced key `getKey()="ProcessTableSynced"`; settings mirror is a `SettingsDto` of `type="ProcessTable"`. If `processGroupIdentifier` is blank/invalid the plugin **auto-creates** a group named = content `uniqueIdentifier` and rewrites the model.
- **Config JSON** (decoded — the rich variant):
```jsonc
{
  "workflowIdentifier": "6c0b4335-a996-4b83-8374-68556dc6f53e",   // Flowable workflow whose instances show/start
  "processGroupIdentifier": "32d9be5f-8e28-458c-b2d8-2baf05fbd0f0", // row filter; auto-created if blank/invalid
  "columnSettings": [
    { "id": "3cab4d6e-…", "name": "Customer Name", "dataClass": "java.lang.String",
      "scope": "CRUD", "contextIdentifier": "fe5e9b03-…", "crudAlias": "ticket", "fieldExpression": "customerName" },
    { "id": "1b903b87-…", "name": "Created Date", "dataClass": "java.time.LocalDateTime",
      "scope": "CONTEXT", "contextIdentifier": "fe5e9b03-…", "fieldExpression": "createdDate" }
  ],
  "indexSettings": [
    { "id": "0844226f-…", "indexName": "customerName", "scope": "CRUD",
      "contextIdentifier": "fe5e9b03-…", "fieldExpression": "customerName", "dataClass": "java.lang.String" }
  ],
  "filterExpression": "like(customerName, %{customer_name}%) && createdDate > {created_date}",
  "userStartProcessActions": {                                     // breadcrumb "start a process" buttons
    "actions": [
      { "id": "930f4f5e-…", "localizedNames": {"en_US":"Intake"}, "localizedButtonNames": {"en_US":"Intake"},
        "predicateIdentifier": "c25bc2d6-…", "direct": "off",       // STRING "on"/"off", NOT boolean
        "formGroupIdentifier": "a3bcfb80-…", "icon": "pe-7s-news-paper" }
    ], "errors": []
  },
  "globalActions": {                                               // row dropdown, on every row, predicate-gated
    "actions": [
      { "id": "9ef80d55-…", "localizedNames": {"en_US":"Edit"}, "localizedButtonNames": {"en_US":"Edit"},
        "predicateIdentifier": "4f75a151-…",                       // REQUIRED, non-blank, else action never shows
        "onBeforeUserTaskCompleteRuleIdentifier": "694b564b-…",
        "direct": "off", "formGroupIdentifier": "a3bcfb80-…", "icon": "pe-7s-edit" }
    ], "errors": []
  }
}
```
- **Fields** (`ProcessTablePluginModel.java` — top level):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `workflowIdentifier` | String | Flowable workflow whose instances are shown and started; resolved via `flowableWorkflowService.findByIdentifier`. Blank → start actions error. | — |
| `processGroupIdentifier` | String | Process-group row filter (`ProcessFilter.processGroupIdentifier`). Blank/invalid → plugin auto-creates a group named = content `uniqueIdentifier` and rewrites the model. | auto |
| `columnSettings[]` | `ProcessTableFormControlSettings[]` | Table columns. Unlike a CRUD column each has a **`scope`** (`GLOBAL`/`CONTEXT`/`CRUD`) that selects the value source (`extractColumnValue`); also carries `dataClass`, `contextIdentifier`, `crudAlias`, `fieldExpression`, `localizedNames`/legacy `name`, `trueIcon`/`falseIcon`, `enumValues`/`enumName`/`enumDisplayField`, and `money`(boolean; numeric columns only — render the cell as money), `currency`(symbol `$`/`€`/`֏` or ISO code `USD`; free text, blank → amount only), `moneyFormat`(`US`/`EUROPEAN`/`SPACE_COMMA`/`SPACE_DOT`/`SWISS`/`INDIAN`/`PLAIN`; blank → `US`), `moneyDecimals`(Integer 0–6; null → 2), `dateFormat`(moment.js pattern for a `java.time.LocalDate`/`LocalDateTime`/`Instant` column, e.g. `DD/MM/YYYY HH:mm`; blank → the raw ISO value). | `[]` |
| `indexSettings[]` | `ProcessIndexSettings[]` | Named context values (`indexName` + `scope`/`contextIdentifier`/`crudAlias`/`fieldExpression`/`dataClass`) that `filterExpression` filters over; forwarded to backend as `ProcessIndexSettingsDto` on start/action (`getIndexSettingsDtoList`). No `trueIcon`/`falseIcon`. | `[]` |
| `filterExpression` | String | Filter DSL over `indexName`s (`==`,`!=`,`>`,…, `&&`/`\|\|`/`!`, `ignoreNull`, `like`, `contains`, `anyMatch`; `{placeholder}` = filter-form value). Placed into `ProcessFilter.expression`. Unique to this plugin. | — |
| `userStartProcessActions` | `UserTaskActionsDto` | "Start a new process" **breadcrumb** buttons (`breadcrumbButtons`). `direct:"on"` starts the workflow directly; `"off"` redirects to `formGroupIdentifier`. Blank predicate = always-allowed. | — |
| `globalActions` | `UserTaskActionsDto` | Row-dropdown actions available on **every** process row, in addition to live BPMN userTask actions. Shown **only** when `predicateIdentifier` is non-blank AND evaluates true for that process — a blank predicate is skipped and **never shows** (fail-closed), the #1 "does nothing" cause. Re-checked at execution. | — |

  Nested-DTO detail — `direct` on a process action is a **STRING `"on"`/`"off"`** (`UserTaskActionsDto.isDirect()==equals(direct,"on")`), not a boolean; `completeUserTask`/`validationRuleIdentifiers`/`onBeforeUserTask*RuleIdentifier` are valid export fields even when the UI doesn't surface them; `scope` serializes by constant name (`"GLOBAL"`/`"CONTEXT"`/`"CRUD"`). Full field-by-field tables for `ProcessTableFormControlSettings`, `ProcessIndexSettings`, the `scope` value-source matrix and the `filterExpression` grammar are in **doc 05 Part 2** — already complete.
- **Editor / settings panel:** The inline `editComponent` is a one-field `ProcessTablePluginEditor` — a form with just the **workflow** `DropDownChoice`; on submit it writes `model` back via writes `properties.model` + `contentService.save`. The full config surface is the right-nav **"Process Table Settings"** panel (`ProcessTableSettingsControlPanel`), opened by the author-only "Settings" breadcrumb button (`EventUtils.trigger openGloseRightGroup`). Its accordion has: Process Group autocomplete, Workflow dropdown, **User Start Process Actions** panel, **Global Actions** panel, **Column settings** panel, **Index settings** panel, and a **Filter Expression** textarea + a help modal. It autosaves each change (when `dynaformSettingsConfig.isAutosave()`), writing the model into `properties.model` **and** mirroring it into a `SettingsDto(type="ProcessTable")` via `doSave`.
- **See also / source:** [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) Part 2 (field-level, complete) · also referenced by [04](04-crud-table-plugin.md), [07](07-workflows-and-tasks.md), [12](12-queries-sources-schedulers-and-rest.md), [14](14-plugin-catalog-all.md) · `ProcessTablePlugin.java`, `ProcessTablePluginModel.java`, `ProcessTablePluginEditor.java`, `ProcessTableSettingsControlPanel.java`


---

## Layout & content

### `nct.help.plugin` — a "?" help icon that pops up a localized message

- **Config slot:** `properties.helpSettings` (`stringValue` = JSON of `HelpPluginSettings`) · **Editor:** yes — single-form panel in a 400 px modal (no tabs) · **Hand-authored in .mrjun:** yes — placed beside a form field/caption and its `helpSettings` JSON is written by hand or by the generate-fields generator (the `help_*` / `help_gen_slot_*` nodes; see doc 03).
- **Function:** Renders a small `pe-7s-help1` question-mark icon (`<span class="nct-help-icon">`). Clicking or hovering it shows a floating `.nct-help-popup` bubble with the localized `message` text (auto-positioned above/below the icon, HTML-escaped). Optionally the icon stays hidden until the mouse enters a designated parent element. Group `Common`; base `NctBasePlugin<HelpPluginSettings>`; JS `HelpPlugin` extends `PluginPanel`.
- **Config JSON** (decoded from `helpSettings.stringValue`):
```jsonc
{
  "alwaysVisible": true,          // icon always rendered
  "parentSelector": null,         // only used when alwaysVisible=false
  "showMessageOn": "CLICK",       // CLICK | HOVER — popup trigger
  "needToBeSaved": false,         // inherited auto-translate dirty flag
  "localizedMap": {               // inherited from LocalizedBean
    "message": {                  // the one localized field this plugin uses
      "en_US": "SHARE, not %: 0.15 = 15%; precision 5, scale 4",
      "ru_RU": "ДОЛЯ, а не %: 0,15 = 15%; точность 5, масштаб 4",
      "hy_AM": "ԲԱԺԻՆ, ..."
    }
  }
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `alwaysVisible` | boolean | If `true`, the icon is always shown. If `false`, JS hides it (`display:none`) and only reveals it while the mouse is over the `parentSelector` ancestor. | `true` |
| `parentSelector` | String (jQuery selector) | Ancestor selector used with `$icon.closest(selector)`; on that parent's `mouseenter` the icon appears, on `mouseleave` it hides. Only honoured when `alwaysVisible=false`. | `null` |
| `showMessageOn` | enum `CLICK` \| `HOVER` | Popup trigger. `CLICK` toggles on click and closes on outside-click; `HOVER` opens on `mouseenter` / schedules hide on `mouseleave`. Exposed to JS as `trigger` = `"click"`/`"hover"`. | `CLICK` |
| `needToBeSaved` | boolean | Inherited from `MicroserviceTranslatedLocalizedBean`; set `true` when `getLocalized` auto-translated a missing locale via the localization microservice, signalling the blob should be re-persisted. Not user-edited. | `false` |
| `localizedMap.message.<locale>` | Map<locale,String> | The help text per locale (`en_US`, `ru_RU`, `hy_AM`, …). Read via `settings.getLocalized("message", locale)`; a missing locale is auto-translated from another (English preferred) through `LocalizeService`. | none (empty → `""`) |
- **Editor / settings panel:** `editComponent(...)` returns `HelpPluginEditor`, a per-locale form bound to `HelpPluginSettings` shown in a 400 px modal. Controls: an **Always Visible** checkbox (AJAX toggles the parent-selector block's visibility), a **Parent Selector (jQuery)** text field (visible only when Always Visible is unchecked), a **Show Message On** dropdown (`Click`/`Hover`), and a localized **Message** textarea. On submit → `saveSettings`: `content.setJsonProperty("helpSettings", settings)` → `contentService.save(activeBranchId, content)` → `refresh()` → back to view mode. No editor tabs.
- **See also / source:** doc [14](14-plugin-catalog-all.md) §1.7 (catalog stub — covers `alwaysVisible`/`showMessageOn`/`localizedMap.message` but **not** `parentSelector`, `needToBeSaved`, or the editor panel), doc [03](03-generate-fields-from-crud.md) (the Info/help column that generates `help_*` nodes), doc [20](20-localization.md) (`helpSettings.localizedMap.message`) · `HelpPlugin.java`, `HelpPluginSettings.java`, `HelpPluginEditor.java`, `MicroserviceTranslatedLocalizedBean.java`, `HelpPlugin.js`

### `nct.html.plugin` — raw-HTML surface, evolved into a "HTML Component Studio" (uploaded JS libs + isolated author JS + rule/BL bridges + per-theme CSS)

- **Config slot:** `properties.studioModel` (`stringValue` = GSON JSON of `HtmlStudioModel`) · plus the classic `properties.html` (`stringValue` = the **"main"** HTML document) · **Editor:** yes — **5-tab** IDE (`HtmlStudioPanel`: **HTML / Scripts / Libraries / CSS / Guide**, plus a footer **Preview** button; Scripts and Libraries carry a live count badge) · **Hand-authored in .mrjun:** yes — a builder places the node and writes `properties.html.stringValue`; `studioModel` is added only when the node needs a real custom component. **Back-compatible:** with no/empty `studioModel` (`HtmlStudioModel.isEmpty()`) the plugin renders byte-for-byte like the classic raw-HTML plugin.
- **Function:** Renders author HTML. When the studio model is non-empty, `getHtml()` wraps the markup in `#dokie-plug-<markupId>` (CSS scope + runtime root), `renderHead` emits scoped per-theme CSS + loads `/dokie/dokie-runtime.js` once + publishes a per-instance mount payload to `window.__dokieMounts[domId]`. Isolated author scripts run after render (in `order`, one shared scope per instance) and reach the server ONLY through **three** sanctioned Wicket bridges — `dokieCallRule` (`ctx.callRule`), `dokieCallBl` (`ctx.callBl`) and `dokieBreadcrumb` (`ctx.breadcrumb.*`, page-title action buttons) — never a direct browser REST call. All three always answer a JSON envelope (`{"ok":true,…}` / `{"ok":false,"error":…}`), so an `await` in author JS always settles. Live form/CRUD context is projected read-only into `ctx.contextData`. A studio-active node whose `html` property is unset renders **empty** (the classic, non-studio node renders the base `<div>Html content here</div>` placeholder instead).
- **Config JSON** (`properties.studioModel.stringValue`, decoded):
```jsonc
{
  "libs": [                                  // named, reusable asset bundles
    { "name": "d3", "enabled": true, "order": 0,
      "globalVar": null,                     // JS_CLASSIC/UMD only: window global exposed as ctx.libs[name]
      "assets": [
        { "kind": "JS_ESM",                  // JS_ESM | JS_CLASSIC | CSS | FONT
          "url": "https://cdn.jsdelivr.net/npm/d3@7/+esm", // CDN url ...
          "path": null,                      // ... OR tenant-relative upload path e.g. "studio/d3/d3.esm.js"
          "fileName": null, "entry": true, "order": 0 } ] } ],
  "docs":    [ { "name": "detail", "html": "<div id=\"detail\"></div>" } ], // extra docs; "main" NOT listed here
  "scripts": [ { "name": "main", "code": "const d3 = ctx.libs.d3; ...",
                 "enabled": true, "order": 0, "libNames": ["d3"] } ],
  "css":     { "byTheme": { "*": ".card{padding:8px}",             // "*" = every theme
                            "Dark Blue": ".card{background:#13181b}" } } } // key = Skin display name
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `libs[]` | `StudioLib[]` | Named, reusable asset bundles; only `enabled` ones are mounted | `[]` |
| `libs[].name` | string | The `ctx.libs[name]` key | — |
| `libs[].enabled` | bool | Include this lib in the mount | `true` |
| `libs[].order` | int | Load order (renumbered on save) | `0` |
| `libs[].globalVar` | string | For a `JS_CLASSIC` (UMD) lib: `window[global]` exposed as `ctx.libs[name]` | `null` |
| `libs[].assets[]` | `StudioAsset[]` | Files/urls loaded together for this lib | `[]` |
| `libs[].assets[].kind` | enum | `JS_ESM` \| `JS_CLASSIC` \| `CSS` \| `FONT` | `JS_ESM` |
| `libs[].assets[].url` | string | Absolute CDN url (mutually alternative to `path`) | `null` |
| `libs[].assets[].path` | string | file-storage path RELATIVE to the tenant root (`studio/<lib>/<file>`); the current tenant id is prepended at render (`t/<tenantId>/…`) and the file is served by `/dokie-asset?p=…`. ⛔ That endpoint answers **403** for anything that is not `t/<digits>/studio/<something>` with a front-end extension (`js, mjs, css, json, map, svg, html, htm, woff, woff2, ttf, otf, eot, png, jpg, jpeg, gif, webp`) and rejects `..`. Lib and file names are also **sanitized on upload** — every character outside `[A-Za-z0-9._-]` becomes `_` — so a hand-written `path` that does not match the sanitized, `studio/`-rooted form simply never loads. `validate` cannot catch this; use the Libraries tab's upload (or a CDN `url`) rather than typing a path | `null` |
| `libs[].assets[].fileName` | string | Original upload file name (editor UI / re-download) | `null` |
| `libs[].assets[].entry` | bool | The ESM entry whose module namespace becomes `ctx.libs[name]` | `false` |
| `libs[].assets[].order` | int | Asset order within the lib | `0` |
| `docs[]` | `StudioDoc[]` | Secondary HTML documents ("main" = the `html` property, never listed here). Pulled into another document by `<include src="<name>.html">` or at runtime by `await ctx.include('<name>.html', '<selector>')` — both render **server side**, so a `<plugin>` inside an included document becomes a real child node; `ctx.showHtml(name)` remains a client-side `innerHTML` swap that renders neither `<plugin>` nor `<include>` | `[]` |
| `docs[].name` | string | Document name, **stored WITHOUT an extension** (`detail`, `charts/bar`) — unchanged schema, no migration. The studio *displays* it with `.html` and accepts either spelling when renaming; a slash-path is a display folder in the editor, **not** a path (no `..`, no relative resolution). ⛔ `<include src>` and `ctx.include` **require** the extension (`src="detail.html"`; `main.html` addresses the `html` property) — documents and scripts are two independent name spaces, so an extension-less `src` is refused with a warning rather than guessed. `ctx.showHtml` accepts both spellings | — |
| `docs[].html` | string | The document markup | `""` |
| `scripts[]` | `StudioScript[]` | Author JS; every selected script runs after render as ONE program in one shared isolated scope per instance. **Which** ones are selected: if no document reachable from `main.html` declares a script include, every `enabled` script runs in `order` (legacy, unchanged); as soon as one document contains an `<include src="<name>.js">`, **only** included scripts run, in the order those tags appear (depth-first from `main.html`) | `[]` |
| `scripts[].name` | string | Script name, **stored WITHOUT an extension** (`boot`, `table/render`); the studio displays it with `.js`, and `<include src="boot.js">` needs that extension. Slash-path = folder in editor | — |
| `scripts[].code` | string | The JS source | `""` |
| `scripts[].enabled` | bool | Run this script. Still decisive in include mode: an included-but-disabled script stays off | `true` |
| `scripts[].order` | int | Run order (renumbered on save) — the ordering used in legacy mode; in include mode the order of the `<include src="….js">` tags decides instead | `0` |
| `scripts[].libNames` | string[] | Libs that must load (as `ctx.libs[name]`) before this script runs | `[]` |
| `css` | `StudioCss` | Per-theme CSS, rendered scoped to this instance's wrapper | `{byTheme:{}}` |
| `css.byTheme` | `map<string,string>` | key `"*"` = all themes; a skin display name (currently `Standard` · `Dracula` · `Forest` · `Dark` · `Dark Blue`) = only that theme. At render the `"*"` block + the active-skin block are emitted, each auto-scoped to this instance's wrapper. Same contract as `chart.js.plugin`'s `cssByTheme` — see [24a](24a-theming-and-dark-mode.md) | `{}` |

  Classic (non-studio) properties on the same node: `properties.html.stringValue` (STRING, the "main" document), `properties.editorWidth`/`editorHeight` (STRING, `"100%"`/`"700px"` — base editor sizing hints), plus generic `className`/`styleName`/`tagProperties`. Runtime call DTOs (not config): `DokieBridge.RuleCall{rule,inputJson}`, `DokieBridge.BlCall{alias,method,argsJson}`, `DokieBridge.BreadcrumbCall{buttonsJson}`.

  **Breadcrumb buttons (`ctx.breadcrumb.*`, the third bridge).** Author JS can put its own action buttons into the page-title bar, next to the platform's own breadcrumb actions — no content node, no settings blob. The runtime keeps the wanted set per instance, debounces every `add/set/update/remove/clear` into ONE `dokieBreadcrumb` post carrying the **complete** desired set, and the server **replaces** this plugin's whole contribution with it (`"[]"`/blank clears it). Only the descriptor below travels; the click handler stays in the browser (the rendered button's `onclick` calls back into the runtime), so a button costs exactly one round-trip to declare and none to click. ⛔ The bridge is **inert on a classic (non-studio) node** — with no studio model there is no mount for the handler to resolve against, so it answers `{"ok":false,"error":"studio is not active for this component"}` and renders nothing. Fields of one button descriptor (author JS object; the same names are what the server parses):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `key` | string | Identity **within this instance** — re-declaring the same key REPLACES that button rather than appending. Sanitized server-side to `[A-Za-z0-9_.:-]`, max 64 chars; when omitted the runtime derives one from the label, else `btn<n>`. | derived |
| `label` | string \| **function** | Visible text, rendered escaped. **May be a function** (e.g. a localization lookup) — it is called ONCE at declaration time and only the resulting string is stored/sent; a function that throws leaves the button labelled with its key. Capped at 120 chars. | = `key` |
| `icon` | string | Icon class (`pe-7s-*` / `lnr-*` / `fa fa-*`). Recommended: the platform wait-spinner swaps the `<i>` element, so a button rendered without an icon can never show a spinner. Sanitized to class-safe characters. | `null` |
| `variant` | string | Bootstrap contextual variant: `primary\|secondary\|success\|info\|warning\|danger\|light\|dark\|link`. | `null` |
| `cssClass` | string | Full class override; when set, `variant` is ignored. Sanitized (max 200 chars). | `null` |
| `title` | string | `title` attribute / tooltip (max 200 chars). | `null` |
| `order` | int | Ascending sort **inside this plugin's own set**; equal values keep declaration order, so it can be ignored. | `0` |
| `disabled` | bool | Renders the button disabled — **no** `onclick` is emitted at all. | `false` |
| `onClick` | function | Browser-only, never serialized. Invoked through the runtime on click. | none |
| `wait` | bool | Browser-only. Wait visuals are opt-**out**: an async handler that forgets to ask still gets feedback; pass `false` to suppress. | `true` |
| `block` | string (selector) | Browser-only. Element to block while the handler runs — scope it to your own component. | `null` |

  Limits worth designing around: **max 20 buttons** per plugin instance (extras are dropped) and a **64 KB payload cap checked BEFORE deserialization** — an oversize publish is rejected wholesale and parses as an EMPTY set, i.e. the buttons *vanish* rather than partially appear. Publishing is **single-in-flight**: a set counts as synced only after the server acknowledges it, a newer set is re-armed until the current call settles, and a call that never answers releases the in-flight lock after ~30 s (the set stays un-synced, so the next flush retries). Declare buttons from a live instance — a superseded mount skips its flush.
- **Editor / settings panel:** `editComponent()` returns `HtmlStudioPanel(getContent())` — an IDE-style master/detail form. **HTML tab:** left tree of documents (always includes non-renamable/non-deletable **"main"** = the `html` property) + a persistent CodeMirror; rename (blur), Reformat (`HtmlReformatter`), Add/Delete doc; **and, on the right, a plugin chooser** (`HtmlPluginChooserPanel`) — the same accordion of plugin groups as the kicker, filtered to this project's `type`, each row with a **preview** (opens the plugin in a `PluginPreviewPanel` modal) and an **add** button that inserts a ready `<plugin name="…" id="…"/>` snippet **at the CodeMirror cursor**. The snippet carries every default property the plugin declares (`<prop name value type/>`) and its `id` is **auto-generated** as `<pluginName>.<N+1>`, where N is the highest `id="<pluginName>.<digits>"` already present in the document — so ids stay readable and unique without the author inventing them. Virtual plugins insert with an extra `vp="<id>"`; `nct.parsis.plugin` is re-added to the chooser even though it is hidden in the kicker, so nested sortable containers can be inserted from here. **Scripts tab:** tree + CodeMirror + header form (name, Enabled checkbox, `libNames` multi-select, Up/Down reorder, Delete). **Libraries tab:** list + detail form (name, enabled, globalVar, per-asset kind/url/entry rows with Add/Remove, and a ZIP/multi-file upload zone → `FileStorageService.upload` under `t/<tenantId>/studio/<lib>/…`, kind inferred by extension). **CSS tab:** fixed left list ("All themes" + every Skin name) + CodeMirror. **Guide tab:** a static, read-only cheat-sheet of the `ctx` API (`ctx.root`, `ctx.libs.*`, `ctx.contextData`, `ctx.callRule`, `ctx.callBl`, `ctx.showHtml`, `ctx.byName`, `ctx.bus`/`ctx.emit`/`ctx.on`, `ctx.api`, `ctx.onCleanup`) plus the slash-path folder convention — nothing is editable there. Footer **Preview** button opens a cloned node in a `PluginPreviewPanel` modal. Structural (navigation/preview/reformat) submits never write; a normal submit calls `persist()` → renumbers `order`s, writes `html` STRING + `studioModel` JSON via `contentService.save`, then `refreshPage()`.
- **See also / source:** **doc [24](24-html-component-studio.md) "HTML Component Studio"** (full field-level export schema + runtime `ctx` API; §7 = the breadcrumb API) · [24a](24a-theming-and-dark-mode.md) (per-theme CSS) · [24b](24b-html-composition-and-plugin-tags.md) (the `<plugin>` tag the HTML tab's chooser inserts) · [24c](24c-html-data-tables-and-paging.md) (paged tables) · [24d](24d-html-component-structure.md) (documents, scripts, `<include>` layout) · doc 14 §1.1 (catalog) · `NctHtmlPlugin` (extends `HtmlPlugin`), `HtmlStudioModel` (schema), `HtmlStudioPanel` (editor), `HtmlPluginChooserPanel`/`PluginSnippetBuilder` (HTML-tab plugin chooser + snippet), `HtmlStudioSupport` (rule/BL exec + context projection + CSS scoping), `HtmlStudioMount`/`DokieBridge`, `DokieBreadcrumbSupport`/`DokieBreadcrumbButton`/`DokieBreadcrumbLink` (breadcrumb bridge), runtime `static/dokie/dokie-runtime.js`.

### `nct.image.plugin` — a single static image element (logo, illustration, banner)

- **Config slot:** `properties.*` named props (`stringValue` = **no config blob** — url/dimensions/class live in discrete typed properties, not a JSON stringValue) · **Editor:** yes, but not a tab panel — an **image-gallery picker** (`ImageGalleryPanel`) reached from the node's view-edit menu · **Hand-authored in .mrjun:** **yes** — a builder drops an image node onto a page (site logo, hero, illustration) and hand-writes `url` + optional `width`/`height`/`tooltip`/`description`/`className`. Appears ~103× across exports.
- **Function:** Renders one `<img>` via richwicket `ImagePanel`. a content re-init reads `url()`, `tooltip()`, `description()`, `className` and builds the image; when `url` is unset it falls back to a sized placeholder fake-file `getImageFakeFile_{width}_{height}`. On export the stored `url` is **tenant-stripped** (`TenantDomain.stripTenantPrefix`) so it ports cleanly; on render it is re-prefixed for the importing tenant (`tenant().resolveImagePath`) and served from **nct-file-storage** (`tenant-files/`), so a ported project needs the actual file present.
- **Config JSON** (decoded — real `erp` logo node):
```jsonc
{
  "pluginName": "nct.image.plugin",
  "name": "logo-plugin",
  "properties": {
    "url":         { "key": "url",         "propertyType": "STRING",
                     "stringValue": "abs(/architectui-html-pro/images/logo-inverse.png)" },
    "description": { "key": "description", "propertyType": "STRING",  "stringValue": "Logo" },
    "tooltip":     { "key": "tooltip",     "propertyType": "STRING",  "stringValue": "Logo" },
    "width":       { "key": "width",       "propertyType": "INTEGER", "integerValue": 400 },
    "height":      { "key": "height",      "propertyType": "INTEGER", "integerValue": 250 },
    "className":   { "key": "className",   "propertyType": "STRING",  "stringValue": "" }
  }
}
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `url` | STRING | Image path. Supports the `abs(...)` macro (absolute path to a bundled/static resource). Stored **tenant-stripped** in exports; resolved with the current tenant prefix on render and served from nct-file-storage. When null → sized placeholder fake-file. | *(null → `getImageFakeFile_{width}_{height}`)* |
| `description` | STRING | Alt/description text set on the `ImagePanel` (`image.setDescription`). | `""` |
| `tooltip` | STRING | Hover tooltip / `title` set on the `ImagePanel` (`image.setTooltip`). | `""` |
| `width` | INTEGER | **Not applied to the rendered `<img>`** (that line is commented out in `initPluginContent`). Used only to size the placeholder fake-file and to seed the gallery editor's dimension config. | `400` |
| `height` | INTEGER | Same as `width` — placeholder + gallery-editor dimension only, not a rendered attribute. | `250` |
| `className` | STRING | CSS class applied to the image (`image.setStyleClass`). Constant `StandardProperties.CLASS_NAME`. | `""` |
| `styleName` | STRING | Inherited standard property (inline style) available on all plugins; optional, not read by this plugin's own code. | *(unset)* |
| `tagProperties` | STRING | Inherited standard property (extra tag attributes) available on all plugins; optional. | *(unset)* |

- **Editor / settings panel:** No tabbed settings panel. In authoring mode the node's view-edit behavior (Nct role gating via `NctSecurityUtils`) exposes an edit action; `editComponent()` returns an **`ImageGalleryPanel`** — a browse/upload image picker seeded with the current `url`/`description`/`tooltip` (`ImageGalleryPanelModel`) and `width`×`height` (`ImageGalleryPanelConfig.Builder().setDimension(w,h)`). On pick (`gotImage`) it **strips the tenant prefix and saves only the `url` STRING property**, then switches back to view mode. `width`/`height`/`description`/`tooltip`/`className` are **not** editable through the picker — set them via the generic property panel or hand-authored JSON.
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` §1.5 (field table + tenant-strip note) · `doc/builder/01-content-model-and-pages.md` (catalog row) · `NctImagePlugin.java` (`nct-ui/.../plugin/common`); base `ImagePlugin.java` + `ImagePropertiesBuilder.java` (`mrjun-cms-view/.../plugins/common/image`).

### `nct.label.link.plugin` — a hyperlink rendered with a localized text caption

- **Config slot:** none — no JSON config blob; configured via flat `properties.*` (`identifier`, `internal`, `link`, `label`, `params`, `style`, `className`) · **Editor:** yes — modal form (`NamedLinkEditorFormPanel`, `showInModal("398px")`) · **Hand-authored in .mrjun:** yes — a builder drops this content node onto a page and hand-writes its named properties (label caption + destination); it is a page-authored content plugin (listed as page content in doc 01).
- **Function:** Renders an `<a>` whose visible text is the localized `label` (aka `name`). When `internal:true` and `identifier` is set, it builds a Wicket `ContentLink` to the destination content node resolved via `contentService.findOneByIdentifier(branch, identifier)`; otherwise it renders a plain `<a href=…>` using the locale value of `link`. Caption text is emitted with `setEscapeModelStrings(false)` (HTML in the caption is allowed). Optional `style` and `className` are applied to the anchor; in authoring mode the CSS class `link_authoring_admin` is added and `link_authoring.js` is loaded via `renderHead`. Differs from plain `nct.link.plugin` only by carrying/rendering the `label` caption.
- **Config JSON** (decoded — a real node; flat named properties, not a blob):
```jsonc
{ "pluginName": "nct.label.link.plugin", "name": "Link Label",
  "properties": {
    "label":      { "key":"label",   "propertyType":"LOCALIZED_STRING",
                    "localizedStringValue": { "en_US":"Open form", "ru_RU":"…", "hy_AM":"…" } },
    "link":       { "key":"link",    "propertyType":"LOCALIZED_STRING", "localizedStringValue": {} },
    "params":     { "key":"params",  "propertyType":"STRING", "stringValue":"" },
    "internal":   { "key":"internal","propertyType":"BOOLEAN", "booleanValue": true },
    "identifier": { "key":"identifier","propertyType":"STRING",
                    "stringValue":"641b5dde-96b8-4cd3-b37a-42478cf521ec" },
    "style":      { "key":"style",   "propertyType":"STRING", "stringValue":"" },
    "className":  { "key":"className","propertyType":"STRING", "stringValue":"" }
  } }
```
- **Fields:** (seeded by `LinkLabelPropertiesBuilder` → `LinkPropertiesBuilder`)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `label` | LOCALIZED_STRING | The visible caption text of the link, per locale (the editor's `name` field maps here). Rendered as HTML (unescaped). | — (empty map) |
| `link` | LOCALIZED_STRING | External URL/href per locale. Used as the anchor `href` **only** when `internal:false` (or `identifier` is null). | — (empty map) |
| `internal` | BOOLEAN | `true` → navigate to an internal content node via `identifier` (`ContentLink`); `false` → use the raw `link` URL as `href`. | `true` |
| `identifier` | STRING | The **destination** content node's `identifier` (the node this link navigates to), resolved via `contentService.findOneByIdentifier`. NOT the link node's own uuid. Honoured only when `internal:true`. | — (null) |
| `params` | LOCALIZED_STRING (declared) / read as STRING | Query parameters appended to the internal-content link. Builder declares it LOCALIZED_STRING but `getCurrentLinkModel` reads it as `PropertyType.STRING, ""`; exports show a plain STRING. | `""` |
| `style` | STRING | Inline CSS applied to the anchor (`AttributeUtils.modifyStyle`) when non-empty. | `""` |
| `className` | STRING | CSS class(es) added to the anchor (`AttributeUtils.addCssClass`) when non-blank. Read via `Constants.StandardProperties.CLASS_NAME`. | `""` |

- **Editor / settings panel:** Overrides `editComponent()` → `NamedLinkEditorFormPanel` (a `MrjunLocalizedForm` with a per-locale language bar, opened in a 398px modal). Fields: **name** (`TextField`, localized → writes `label`), **link** (`TextField`, localized → `link`), **params** (`TextField` → `params`), **innerPage** (`ContentPageSelectorIdentifier` content-node picker → `identifier`), and a hidden **isInternal** (`HiddenField` → `internal`, toggled client-side by `doInit(...)` which shows either the innerPage picker or the link field). On submit `saveCurrentLinkModel` writes `identifier`, `internal`, `label`, `link`, `params` back onto the content and calls `contentService.save(...)`, then `switchToViewMode()`; the label variant additionally re-sets the `label` (LOCALIZED_STRING) property explicitly. Validation: if `internal:true` and no `identifier` chosen, the innerPage field errors "Field is required". No generic property/settings panel beyond this editor.
- **See also / source:** doc 14 §1.6 (real node + field notes) · doc 01 (page-content field table) · `NctLabeledLinkPlugin.java` (nct-ui) → `LocalizedLinkLabelPlugin.java` → `LinkPlugin.java` (mrjun-cms-view `plugins/common/link/`); editor `NamedLinkEditorFormPanel.java` / `LinkEditorFormPanel.java`; defaults `LinkLabelPropertiesBuilder.java` / `LinkPropertiesBuilder.java`.

### `nct.label.plugin` — static localized text / form caption / header

- **Config slot:** none (`properties.<slot>` = **no config blob**) · uses discrete named `properties.*` (`text`, `tagName`, `className`, `styleName`, `tagProperties`). **Editor:** yes — inline single-string localized text editor with a language bar (no tabs). **Hand-authored in .mrjun:** yes — builders place labels as form-field captions, section headers, and static text, and hand-write the `text`/`tagName`/`className` properties (also emitted automatically by "Generate fields").
- **Function:** Renders one localized string inside a configurable HTML tag. `NctLabelPlugin extends` mrjun `LocalizedHeaderPlugin` — a content re-init reads `text` for the current locale (auto-seeding/translating from other locales, falling back to "Sample text" on first render), wraps it in a `Label("header")` whose tag name is set from the `tagName` property (defaulting to `p`). The text is emitted **raw / unescaped** (`setEscapeModelStrings(false)`), so inline HTML in `text` is honored. The NCT subclass only adds authoring-mode plumbing (content-highlight behavior, role-scoped edit/view gating, parsis-aware edit items) — it does not change the config surface.
- **Config JSON** (decoded — discrete properties, no blob):
```jsonc
{
  "pluginName": "nct.label.plugin",
  "name": "lbl_gen_slot_4143cc62_2_0",
  "properties": {
    "text":          { "key": "text", "propertyType": "LOCALIZED_STRING",
                       "localizedStringValue": { "en_US": "Description", "ru_RU": "Описание" } },
    "tagName":       { "key": "tagName", "propertyType": "STRING", "stringValue": "label" },
    "className":     { "key": "className", "propertyType": "STRING", "stringValue": "form-label" },
    "styleName":     { "key": "styleName", "propertyType": "STRING", "stringValue": "" },
    "tagProperties": { "key": "tagProperties", "propertyType": "STRING", "stringValue": "" }
  }
}
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `text` | LOCALIZED_STRING | The displayed text, one entry per project locale in `localizedStringValue` (keys like `en_US`,`ru_RU`). Emitted as **raw HTML** — inline markup is allowed. If blank on first render, seeded from other locales (Google-translated when enabled) or literal `"Sample text"`, then persisted. | (seeded "Sample text") |
| `tagName` | STRING (dropdown) | Wrapper HTML element. Allowed set: `h1,h2,h3,h4,h5,h6,p,span,i,label,small` (`LocalizedHeaderPropertiesBuilder.java`). `div` is NOT allowed unless hand-injected. Use `label` for form captions, `h1..h6` for headers. | **`p`** |
| `className` | STRING | CSS class(es) on the tag (e.g. `form-label`). | `""` |
| `styleName` | STRING | Inline CSS `style` attribute. Standard style property (present in real nodes; not in this plugin's default-properties builder list). | `""` |
| `tagProperties` | STRING | Extra raw HTML attributes appended to the tag (e.g. `data-animation="fadeInUp" data-delay="700ms"`). | `""` |

- **Editor / settings panel:** Inline `SingleStringLocalizedFormEditPanel` bound to the `text` property with a right-side language bar (`setLanguageBarRight(4)`) — one input row per supported locale; on submit it writes each locale back via `content.saveFromLocalizedBean("text", …)`, saves the content, and switches back to view mode. `tagName`/`className`/`styleName`/`tagProperties` are edited via the generic per-node property panel, not this inline editor. Config-panel-only fields: none beyond these named properties.
- **See also / source:** deep coverage in [14-plugin-catalog-all.md §1.4](14-plugin-catalog-all.md) and [01-content-model-and-pages.md](01-content-model-and-pages.md) (catalog + `tagName` default `p` gotcha); generation context in [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md). Source: `NctLabelPlugin.java`, base `LocalizedHeaderPlugin.java`, `LocalizedHeaderPropertiesBuilder.java`.

### `nct.link.plugin` — a hyperlink `<a>` wrapping arbitrary child content

- **Config slot:** `properties.*` named props (`stringValue` = **no config blob** — six flat props, no decoded JSON) · **Editor:** yes — `LinkEditorFormPanel` in a modal (`showInModal("398px")`), localized language bar · **Hand-authored in .mrjun:** **yes** — `group="Common"`, `hideInKicker=false`; a builder drops a "Link" node into a page and sets its destination. (Note: exports show the **labeled** variant `nct.label.link.plugin` is what's actually used; the bare `nct.link.plugin` renders no caption of its own — its visible content is a child `nct.parsis.plugin`.)
- **Function:** Renders an `<a>` element. Two modes: **internal** (`internal:true` + `identifier` set) resolves the destination content node via `contentService.findOneByIdentifier(branch, identifier)` and emits a `ContentLink` to that page; **external** (`internal:false`, or `identifier==null`) emits a plain `<a href=…>` from the localized `link` value. The clickable content inside the `<a>` is a nested `parsis` slot (`getLinkContentComponent → PluginWrapperOfContentPanel(..., "nct.parsis.plugin", "parsis")`), so builders place labels/icons/HTML as children.
- **Config JSON** (decoded — internal link example; every prop is a standard `properties.<key>` entry, no wrapper blob):
```jsonc
"properties": {
  "internal":   { "key":"internal",   "propertyType":"BOOLEAN", "booleanValue": true },
  "identifier": { "key":"identifier", "propertyType":"STRING",  "stringValue":"641b5dde-96b8-4cd3-b37a-42478cf521ec" }, // destination node's identifier
  "link":       { "key":"link",       "propertyType":"LOCALIZED_STRING", "localizedStringValue": {} },                // used only when external
  "params":     { "key":"params",     "propertyType":"LOCALIZED_STRING", "localizedStringValue": {} },                // query params, localized
  "className":  { "key":"className",  "propertyType":"STRING",  "stringValue":"" },
  "style":      { "key":"style",      "propertyType":"STRING",  "stringValue":"" }
}
// External link: set internal=false and put the URL in link.localizedStringValue.<locale>; identifier is then ignored.
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `internal` | BOOLEAN | `true` = navigate to an in-project content page (uses `identifier`); `false` = external URL (uses `link`). | `true` |
| `identifier` | STRING | The **destination** content node's `identifier` (the node this link points to — **not** the link node's own uuid). Resolved via `contentService.findOneByIdentifier`; honoured **only** when `internal:true` and non-null. | `null` |
| `link` | LOCALIZED_STRING | Per-locale href URL/path. Applied to `<a href>` when external (or when `identifier` is null). | `{}` |
| `params` | LOCALIZED_STRING | Per-locale query parameters appended to the link. | `{}` |
| `className` | STRING | CSS class(es) added to the `<a>` (`AttributeUtils.addCssClass`). | `""` |
| `style` | STRING | Inline CSS applied to the `<a>` (`AttributeUtils.modifyStyle`). | `""` |

  In authoring mode the `<a>` also gets a `link_authoring_admin` class and `link_authoring.js` is rendered.
- **Editor / settings panel:** `editComponent(...)` (inherited from `LinkPlugin`) returns a `LinkEditorFormPanel<LinkModel>` opened in a **398px modal**, a `MrjunLocalizedForm` (language bar, per-locale fields). Controls: `link` (localized `TextField`), `params` (localized `TextField`), `innerPage` = `ContentPageSelectorIdentifier` (page picker, writes back to `identifier`), and a hidden `isInternal` field bound to `internal` (toggled by the authoring JS `doInit(...)`). Validation on submit: when `internal` is true and no page is chosen, `innerPage` errors "Field is required". On submit, `saveCurrentLinkModel` persists `identifier` (STRING), `internal` (BOOLEAN), `link` (LOCALIZED_STRING), `params` (LOCALIZED_STRING) and returns to view mode. `NctLinkPlugin` overrides only the authoring/permission gating (`isInAuthoringMode`, `defineCanEdit`, `getViewEditBehavior → NctViewEditBehavior`, extra view-edit items, parsis-parent detection) — it does **not** add its own settings tab.
- **See also / source:** [14 §1.6](14-plugin-catalog-all.md) (field-level table; sibling `nct.label.link.plugin`), [01 §content-model](01-content-model-and-pages.md) (catalog row) · `NctLinkPlugin.java` (`nct-ui/.../plugin/common/NctLinkPlugin.java`) extends `LinkPlugin.java` (mrjun `.../plugins/common/link/LinkPlugin.java`); config surface = `LinkPropertiesBuilder.java`; DTO = `LinkModel.java`; editor = `LinkEditorFormPanel.java`.

### `nct.parsis.plugin` — content drop-container / slot (nct-ui subclass of mrjun `parsis.plugin`)
- **Config slot:** `properties.*` (no config blob — `stringValue` = **none**; the "config" is the node's `children[]` plus a few flat named props) · **Editor:** no (no `editComponent()` override; edited via the generic property panel + drag-and-drop) · **Hand-authored in .mrjun:** **yes** — builders create parsis child nodes explicitly: each tab needs a child parsis with `identifier` = the tab item's `id`; a form needs a child `identifier="form.parsis"`; a filter form needs `identifier="filter.parsis"`; layout `<plugin name="nct.parsis.plugin"/>` slots (`left`/`right`/`first`… and generated `gen_col<N>_<batch>`) each become a child parsis with the matching `identifier`. (The page's own top-level content parsis `id="parsis"` is cloned from the layout skeleton, not typed by hand.)
- **Function:** A structural container that renders nothing itself and lays out its `children[]` (each a plugin) in `order`, with a per-child view-access check (`cmsSecurityService.hasAccess(child, tenant, view)` — a child hidden from a role simply doesn't render). In authoring mode it becomes the drag-and-drop zone (SortTarget/DropTarget accepting `parsis-inner-sort`/`parsis-outer`), clones dropped plugins, and shows a move-confirm when relocating an existing plugin between parses. `NctParsisPlugin` adds only behavior over the base: role-aware `canEditParsis` (also true for `ADMIN`/`NCT_AUTHOR` in authoring mode), drag sources, `36px` drag distance, `reloadAndRefresh()` for out-of-session (MCP/AI) mutations, and `IRefreshable`. `hideInKicker=true` (not offered in the plugin chooser palette).
- **Config JSON** (decoded — there is no JSON blob; config = children + flat props):
```jsonc
{
  "pluginName": "nct.parsis.plugin",
  "name": "parsis",              // or "form.parsis" / "filter.parsis" / a tab-item UUID
  "identifier": "parsis",        // MUST match the <plugin id="…"> in the parent layout HTML,
                                 // or the tab item's id, or exactly "form.parsis"/"filter.parsis"
  "children": [ /* the business plugins placed here */ ],
  "properties": {
    "isParsis":         { "propertyType": "BOOLEAN", "booleanValue": true },
    "minHeight":        { "propertyType": "INTEGER" },        // unset → runtime fallback 40
    "emptyPlaceholder": { "propertyType": "STRING", "stringValue": "" },
    "reuseItems":       { "propertyType": "BOOLEAN", "booleanValue": false },
    "style":            { "propertyType": "STRING" },
    "className":        { "propertyType": "STRING", "stringValue": "" },
    "styleName":        { "propertyType": "STRING", "stringValue": "" },
    "tagProperties":    { "propertyType": "STRING", "stringValue": "" }
  }
}
```
- **Fields:** (from `ParsisPluginDefPropBuilder` — `minHeight`/`style`/`emptyPlaceholder`/`reuseItems`, declared with **no `.withDefault`** so the chooser snippet is a bare tag; `isParsis` self-set at runtime; `className`/`styleName`/`tagProperties` are common styling props)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `isParsis` | BOOLEAN | Marks the node as a parsis slot; if absent/false the plugin sets it `true` and saves (`ParsisPlugin.onInitialize`). Distinguishes a parsis from a plain html node. | `true` |
| `minHeight` | INTEGER | Min-height (px) of the empty drop zone shown only in authoring mode. | `40` (runtime fallback) |
| `emptyPlaceholder` | STRING | "Drop … here" placeholder text propagated to the synthetic empty child when the parsis has no children (authoring only). | `""` |
| `reuseItems` | BOOLEAN | Passes to the Wicket `ListView.setReuseItems` for the children list. | `false` |
| `style` | STRING | Inline CSS; when non-blank the parsis renders a real wrapper element with this style (blank → `renderBodyOnly`, no wrapper). | — (unset) |
| `className` / `styleName` / `tagProperties` | STRING | Generic wrapper styling (CSS class / style-key / extra tag attributes) — common props, not parsis-specific. | `""` |

- **Editor / settings panel:** No dedicated editor panel — `editComponent()` is not overridden and there is no config DTO / `getJsonProperty` deserialization. Authors interact with it two ways: (1) **drag-and-drop** in authoring mode drops/clones/reorders child plugins (this is the primary "editing"); (2) the **generic property panel** edits the flat props above. There is no tabbed settings UI and no serialized config object.
- **See also / source:** field-level tables already in `doc/builder/01-content-model-and-pages.md` §"`nct.parsis.plugin` / `parsis.plugin` — by field" and `doc/builder/14-plugin-catalog-all.md` §1.2; slot-wiring rules in `01` (tabs/layout), `03-generate-fields-from-crud.md` (`form.parsis`, `gen_col*`), `04-crud-table-plugin.md` (`filter.parsis`) · `NctParsisPlugin.java` (nct-ui), `ParsisPlugin.java` + `ParsisPluginDefPropBuilder.java` (mrjun-cms-view)

### `nct.tab.plugin` — a tabbed layout container; each tab hosts its own child parsis slot

- **Config slot:** `properties.tabModel` (`stringValue` = a JSON `TabModel` — `{items:[TabItem…], size}`) · **Editor:** yes — a custom modal editor (`TabPluginEditor`) opened from the "Edit" view-edit toolbar action (NOTE: `editComponent()` returns `null`, so there is no inline generic-property editor; the modal is wired via `addResetDeleteItem` → `showEditModal()`) · **Hand-authored in .mrjun:** yes — a builder drops the tab node onto a page and hand-writes `tabModel` plus one child `nct.parsis.plugin` per tab.
- **Function:** Renders a Bootstrap nav-tabs strip; clicking a tab activates it and lazy-renders that tab's content. Each `TabItem.id` is the `identifier` of a child `nct.parsis.plugin` node — that parsis is the tab body (only the active tab's parsis is rendered; inactive tabs get a `BlockPanel` placeholder). The active tab is remembered per-node in session (`TabPlugin-id-<contentId>`), first tab by default — not part of the export.
- **Config JSON** (decoded from `properties.tabModel.stringValue`):
```jsonc
{
  "items": [
    {
      "id": "5b7fd1bc-136f-4f70-9388-578029065e9a", // == child nct.parsis.plugin identifier
      "name": "Stock",                    // plain fallback caption (stamped from default-locale value)
      "order": 0,                         // render order, ascending (TabPlugin sorts by this)
      "iconClass": "fa fa-box",           // optional <i> class; "" = no icon
      "localizedNames": {                 // canonical per-locale caption, key = Locale.toString()
        "en_US": "Stock", "ru_RU": "Остатки", "hy_AM": "Պահեստի Մնացորդ"
      },
      "localizedMap": { "name": {         // LEGACY store (older exports); read only as fallback
        "en_US": "Stock", "ru_RU": "Остатки" } },
      "needToBeSaved": false              // authoring flag; false in export
    }
  ],
  "size": "SMALL"                         // "BIG" (default) | "SMALL"
}
```
When hand-authoring, prefer `localizedNames`; older exports carry captions only under `localizedMap.name`, and `getLocalizedName()` reads `localizedNames` first, then the legacy map, then `name` — for max safety set both plus `name`.
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `items` | `List<TabItem>` | The tabs; sorted by `order` at render (`TabPlugin.java`). | `[]` (`TabModel.java`) |
| `size` | enum `TabSize` | `"BIG"` (large icon-over-label tabs) or `"SMALL"` (compact `nav nav-tabs mb-3`, `TabPlugin.java`). | `BIG` (`TabModel.java`) |
| `TabItem.id` | String (UUID) | Tab id; MUST equal the `identifier` of the tab's child `nct.parsis.plugin` (`TabPlugin.java`). Auto-generated if null. | random UUID (`TabModel.java`) |
| `TabItem.name` | String | Plain fallback caption; editor stamps it from the default-locale localized value (`TabPluginEditor.java`). | — (`TabModel.java`) |
| `TabItem.order` | int | Tab position (ascending). | `0` (`TabModel.java`) |
| `TabItem.iconClass` | String | Icon CSS class; when non-empty renders an `<i>` (BIG = block 1.5rem above label, SMALL = inline `me-1`) (`TabPlugin.java`). | — (`TabModel.java`) |
| `TabItem.localizedNames` | `Map<String,String>` | Canonical per-locale caption, key = `Locale.toString()` (e.g. `en_US`); edited via the localized-name modal (`TabModel.java`). | `{}` |
| `localizedMap.name` | `Map<String,String>` | Legacy caption store (inherited `MicroserviceTranslatedLocalizedBean`); back-compat fallback only (`TabModel.java`). | — |
| `TabItem.needToBeSaved` | boolean | Authoring UI flag; `false` in export. | `false` |

Other node `properties.*` (not in `tabModel`):
| Key | Type | Meaning | Default |
|---|---|---|---|
| `showCard` | BOOLEAN | Wrap the whole tab set in `mb-3 card` and each tab body in `card-body` (`TabPlugin.java`). | `false` |
| `className` / `styleName` / `tagProperties` | STRING | Standard node styling passthrough. | `""` |
| `roleAccess` | JSONB | Per-node role gating (see doc 01 "Access"). | — |
- **Editor / settings panel:** The "Edit" toolbar button opens the `TabPluginEditor` modal (a form, 600px), which writes back the `TabModel`: a **Size** dropdown (`Big`/`Small`), a **Create tab** button (opens `LocalizedNameEditPanel` — one caption field per tenant locale + auto-translate — then appends the item), and a **drag-sortable list** of tabs, each row with the localized name, an **Edit** (re-open localized-name modal), a **Pe7s icon picker** bound to `iconClass`, and a **Delete** button. Reorder/delete re-index `order` on every item. On Save (`saveTabs`, `TabPlugin.java`) it prunes child `nct.parsis.plugin` nodes whose id is no longer in the model, then writes `properties.tabModel` and `contentService.save(...)`. (Adding/removing a tab in the editor does not itself create the matching child parsis; the child is materialized as the parsis slot when the tab is edited/populated.)
- **See also / source:** doc `01-content-model-and-pages.md` §"Tabs — `nct.tab.plugin`" (full field table) · doc `14-plugin-catalog-all.md` §1.8 (mrjunkit `node add` injects `size:"SMALL"` default) · doc `19-build-decision-procedure.md` (multiple CRUDs-in-tabs recipe) · `TabPlugin.java`, `TabModel.java`, `TabSize.java`, `TabPluginEditor.java`

### `siteMapPage` — the page container node (every page IS a `siteMapPage`)

- **Config slot:** none (no `properties.<slot>.stringValue` config blob) · config lives in the **top-level node field `alias`** plus individual **`properties` entries** (each a typed `DefaultProperty`, not one JSON DTO) · **Editor:** no `editComponent` — edited through the generic page property/settings panel + the `roleAccess` editor in the mrjun right-kicker · **Hand-authored in .mrjun:** yes — a builder creates one `siteMapPage` per business page (via `mrjun.py page add`, then places business plugins inside its inner `nct.parsis.plugin`). The admin/console `siteMapPage` nodes ship in the base skeleton and must be kept, not rebuilt.
- **Function:** The renderable page. It is a Wicket `Page` (`SiteMapPage extends PluginBasePage implements IPlugin`) registered as a plugin — **not** a node placed *inside* a page. On init it materializes exactly one child `parsis.plugin` (`identifier="siteMapPageParsis"`) via `pluginUtils.getOrCreateParsis(...)`; if that parsis is empty it lazily clones the virtualPlugin named by the `layout` property into it. It gates rendering by `roleAccess` (public / authenticated / SSO), mounts the author kicker + toolbar for admins, and — if the `Redirect` property is non-blank — server-side `setResponsePage(redirect)`. Two registrations share the name `"siteMapPage"`: `SiteMapPage` (template `ARCHITECTUI_HTML_PRO`) and `SiteMapPageRaven` (template `RAVEN`); no registry clash because they differ by `siteTemplate`.
- **Config JSON** (decoded — node shape, since there is no config blob):
```jsonc
{
  "pluginName": "siteMapPage",
  "name": "Products",
  "alias": "products",                 // node field (sibling of properties), the URL segment
  "order": 20,
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true, "accessors": { }, "roleGroupAccessors": { } },
  "properties": {
    "layout":          { "propertyType": "STRING", "stringValue": "Main" },        // name of the virtualPlugin layout to clone
    "pageTitle":       { "propertyType": "LOCALIZED_STRING", "localizedStringValue": { "en_US": "Products" } },
    "pageDescription": { "propertyType": "LOCALIZED_STRING", "localizedStringValue": { } },
    "metaTags":        { "propertyType": "STRING", "stringValue": "" },
    "additionalCss":   { "propertyType": "STRING", "stringValue": "" },            // exports; builder declares the slot as "Body Class"
    "Redirect":        { "propertyType": "STRING", "stringValue": "" },
    "aliasParamsMaxCount": { "propertyType": "INTEGER" },
    "group":           { "propertyType": "STRING" },                              // left-menu grouping (manual; not builder-declared)
    "isParsis":        { "propertyType": "BOOLEAN" }                              // false for a page
  },
  "children": [ /* one parsis.plugin "siteMapPageParsis" → html.plugin layout → inner nct.parsis.plugin id="parsis" (business plugins); + optional child siteMapPage subpages */ ]
}
```
- **Fields:** (declared by `SiteMapPageDefaultPropertiesBuilder` + the nct override; plus observed manual slots)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `alias` | STRING (node field, **not** in `properties`) | The page's URL segment; nav walks child pages matching one alias segment at a time (`Objects.equals` on `alias`). Child form-page aliases must be unique. | null |
| `Redirect` | STRING | Non-blank → server-side `setResponsePage(redirect)` (`SiteMapPage.java`). Empty = normal render. | `""` |
| `Body Class` / `additionalCss` | STRING | Extra CSS class/string on `<body>`. Builder declares the slot `"Body Class"` (`SiteMapPageDefaultPropertiesBuilder.java`); exports carry it as `additionalCss` (manual slot). | `""` |
| `pageTitle` | LOCALIZED_STRING | `<title>` by locale (read `PluginPage.java`). | `{}` |
| `pageDescription` | LOCALIZED_STRING | `<meta description>` by locale (read `PluginPage.java`). | `{}` |
| `aliasParamsMaxCount` | INTEGER | How many URL segments after the alias to treat as parameters. | — |
| `metaTags` | STRING | Raw `<meta>` tags. Declared **only** by the nct-ui builder, rendered with a textarea field (`SiteMapPageNctPropertyBuilder.java`, `PropertyBaseTextAreaFieldPanel`). | `""` |
| `layout` | STRING | Name of the **virtualPlugin** whose content is cloned into the empty `siteMapPageParsis` on first render (`SiteMapPage.java`). Real values: `"Main"`, `"Nct layout"`, `"Form"`, `"ddd"`, or null. Not declared by a builder. | `""` (on read) |
| `group` | STRING | Grouping in the left menu. Not builder-declared; empty in exports. | `""` |
| `isParsis` | BOOLEAN | Service flag "this node is a parsis container"; `false` for a page. | `false` |

- **Editor / settings panel:** No dedicated editor panel — `editComponent` is not overridden. Page config is edited through the mrjun author kicker's **generic property/settings panel**, which renders each `DefaultProperty` from the `defaultPropertiesBuilder` with a field per `PropertyType` (STRING → text, `metaTags` → textarea, LOCALIZED_STRING `pageTitle`/`pageDescription` → per-locale string editor, INTEGER `aliasParamsMaxCount` → number), plus the `alias`/`name`/`order` node fields and the separate **`roleAccess` editor** (public read / authenticated-only / per-role + per-role-group view/edit/advancedEdit). Writes land back on the node's top-level fields and its `properties` map; the layout HTML scaffold lives in the child `siteMapPageParsis` subtree, not in these settings.
- **See also / source:** deep coverage in `doc/builder/01-content-model-and-pages.md` (§"Pages — `siteMapPage`": full field-level property table, page→parsis→layout→content structure, layout-clone mechanics, and a from-scratch recipe) and `doc/builder/14-plugin-catalog-all.md` Group 4 · `SiteMapPage.java` (`nct-ui/.../page/SiteMapPage.java`), `SiteMapPageRaven.java` (RAVEN template), `SiteMapPageNctPropertyBuilder.java`, `SiteMapPageDefaultPropertiesBuilder.java` (mrjun-admin-view), `CmsServiceConstants.SITE_MAP_PAGE_PLUGIN_NAME = "siteMapPage"`.


---

## Site chrome

### `site.breadcrumb.plugin` — auto-built breadcrumb trail (+ contributed action buttons) for the page

- **Config slot:** `properties.*` (`stringValue` = **no config blob** — `BreadCrumbPlugin extends NctBasePlugin` *raw*, no `<T>` DTO, no `getJsonProperty(...)`) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — part of the `html.plugin` "Nct layout" skeleton; it appears as a bare `<plugin id="breadcrumb" name="site.breadcrumb.plugin"></plugin>` inside the layout HTML (no props, not even `className`), cloned from the page template, never configured by the builder.
- **Function:** Renders the breadcrumb bar. On a content re-init it (1) emits a `home` `ContentLink` to `/`; (2) walks **up the content tree** from the current page (`contentService.findOne(branchId, parentId)` in a loop), reverses the list and drops the root, then renders each ancestor as a `ContentLink` — except the last (current page), rendered as an `active` `Label` with `aria-current="page"`; each label text = the page's localized `pageTitle` property, falling back to `content.getName()`. (3) It also renders a `buttons` list of **action buttons contributed by OTHER plugins** (e.g. CRUD-table "create/back" actions) via the events `Add_Breadcrumb_Buttons` / `ReInit_Breadcrumb_Buttons` (payload `BreadcrumbButtonsModel`), stored in page metadata keyed by the contributing plugin's `identifier` (idempotent **replace**, so AJAX re-renders don't duplicate buttons; entries whose plugin is no longer on the page are filtered out). Each `PageModel` renders either a `Component` panel or an `AbstractLink`.
- **Config JSON** (decoded):
```jsonc
— none —   // no settings/config slot; the node carries no config blob
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No configurable fields. Breadcrumb content is derived at render time from the page ancestry (content tree) + event-contributed buttons; no per-node JSON. | — |

- **Editor / settings panel:** None. `editComponent()` returns `null` (view-only). There is no settings panel and no generic property editor is meaningful — the only `properties.*` the node ever carries is optional site-chrome cosmetics (`className`/`styleName` on its wrapper, absent in the reference layout). Trail text is driven by each page's localized `pageTitle` (fallback `name`), edited on the page node, not here.
- **See also / source:** [01-content-model-and-pages.md](01-content-model-and-pages.md) (§ site `*` chrome, layout skeleton) · [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (catalog row, "— site chrome") · `BreadCrumbPlugin.java` (`nct-ui/.../plugin/report/BreadCrumbPlugin.java`), models `BreadcrumbButtonsModel.java` / `PageModel.java` (`.../plugin/admin/kicker/model/`).

### `site.footer.plugin` — the page's bottom footer bar (site chrome, view-only)
- **Config slot:** `properties` — **no config blob** (`getJsonProperty` is never called; a content re-init is empty). Only optional `className`/`styleName` passed in from the layout `<property>`. · **Editor:** no (`editComponent()` returns `null` → view-only; in-page edit border only, `editBorderSelector=".app-footer__inner"`) · **Hand-authored in .mrjun:** no — part of the base REPORT skeleton, cloned into the `html.plugin` layout by the page template; a builder never places or configures it.
- **Function:** Renders the static footer at the bottom of every `siteMapPage`. Its markup (`NctFooterPlugin.html`) is fixed chrome: an `.app-footer__inner` bar whose only live content is a copyright span (`© <vendor> <year>, all rights reserved`); all other footer widgets (notifications, language menu, mega-menu) ship commented out. `@PluginConfig`: `displayName="Report Footer"`, `group="site"`, `hideInKicker=true`.
- **Config JSON** (decoded):
```jsonc
— none — // no JSON config; the node carries only the standard site-chrome shell
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config DTO (raw `NctBasePlugin`, no `T`); nothing to author. Optional chrome-level `properties.className` / `properties.styleName` may be supplied by the layout `<property>` (the sample `<plugin id="footer">` carries none). | — |
- **Editor / settings panel:** None. `editComponent()` returns `null`, so there is no tabs/settings panel and no right-drawer editor — the plugin is purely display. In authoring mode it only shows a hover edit-border scoped to `.app-footer__inner`; there is nothing to write back.
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` (Group 3 · Site chrome) and `doc/builder/01-content-model-and-pages.md` (layout HTML) · `NctFooterPlugin.java` (+ `NctFooterPlugin.html`), base `NctBasePlugin.java`.

### `site.header.plugin` — the page's fixed top navbar (site chrome)
- **Config slot:** _none_ (`properties.stringValue` = no config blob; extends raw `NctBasePlugin` with no config DTO — never calls `getJsonProperty`) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — part of the base REPORT skeleton; the `<plugin id="header">` node is cloned into every page's layout HTML by the page template, not placed/configured by a builder.
- **Function:** Renders the top app header (`.app-header__content` navbar). Left side: an author-only **Edit site / Cancel editing** toggle (enters/exits authoring mode) and a hidden projects panel; right side: an **Edit Page** button (opens the current page's `PageEditorPanel` settings dialog with the alias read-only), a **notifications** selector, a **language** selector, and a **login/logout or user-profile** panel. It also self-manages its own `className` at render time (see below).
- **Config JSON** (decoded):
```jsonc
// — none — : no JSON settings blob.
// The only markup input is a plain className property on the <plugin> node in the layout HTML:
<plugin id="header" name="site.header.plugin">
    <property name="className" value="app-header__content"></property>
</plugin>
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `properties.className` | STRING | CSS class on the plugin's outer wrapper, set from the layout `<property>`. **Overridden at runtime** in `initPluginContent`: forced to `"app-header__content"` while in authoring mode, and to `""` (empty) when viewing — so the authored value is cosmetic only. | `app-header__content` (layout) → runtime `""` when not authoring |

- **Editor / settings panel:** No plugin editor (`editComponent` → `null`); it is not configured through a settings panel. Its interactive pieces are built in code, not from config: `editSite`/`liveEditSite` (`ConditionalAjaxLink`, gated on `ReportRole.ADMIN`/`NCT_AUTHOR`) call `securityService.setInAuthoringMode(tenant, …)` + `refreshPage()`; `editPage` loads the current page's `ContentDomain` on the active branch into a `PageEditorModel` and opens a `PageEditorPanel` in the page modal (name/layout/title/description/roleAccess saved back via `contentService.save`; alias intentionally NOT written back). Sub-panels wired in: `NotificationsHeaderSelectorPanel`, `HeaderLangSelectorPanel`, `TopUserLoginPanel`/`TopUserProfilePanel`, and a role-secured `ProjectsInHeaderPanel` (added `setVisible(false)`).
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` (Group 3 · Site chrome) and `doc/builder/01-content-model-and-pages.md` (`site.*` template chrome / layout HTML) · `NctHeaderPlugin.java` (`NctHeaderPlugin.java`) + `NctHeaderPlugin.html`

### `site.kicker.plugin` — the left-navigation sidebar (site menu / quick-links tree)

- **Config slot:** `properties.modelGroups` (`stringValue` = a JSON **string** encoding `PageModelGroupWrapper` → `{ "pagesModel": [ PageModel, … ] }`, the quick-links tree). *No `model`/`settings` slot — the whole config lives in `modelGroups`.* · **Editor:** yes — an inline sidebar **tree editor** (add group / add link / edit / delete / drag-reorder) plus a per-link form. · **Hand-authored in .mrjun:** the **node** is site chrome — it ships in the REPORT/layout skeleton (one `site.kicker.plugin` `identifier="left-nav"` per page's materialized layout, plus a shared `Nct left nav` common virtual plugin that actually renders), so a builder does **not** place the node. **But its `modelGroups` quick-links tree IS hand-authored/patched** by builders to point at business pages (the single exception to "chrome ships fixed"; see doc 17). Prefer the `mrjun.py quicklink` tooling over raw edits.
- **Function:** Renders the left sidebar menu. `NctKickerPlugin extends NctBasePlugin` → a content re-init mounts `NctKickerPanel` → `PagesPanel`, which reads `getModelObject().getJsonProperty("modelGroups", PageModelGroupWrapper::new)` and draws the sidebar as **injected management-console groups ∪ this node's `modelGroups`**. The class is shared by `site.header`/`site.footer`/`site.kicker` (all `@PluginConfig(group="Site")`); the kicker instance is `displayName="Report Kicker Plugin", hideInKicker=true, editBorderSelector=".scrollbar-sidebar"`. Each menu item is a `PageModel` that is either a **group** (heading/folder with `children`) or a **link** (carries `linkModel`); links can nest sub-links.
- **Config JSON** (decoded from `modelGroups.stringValue`):
```jsonc
{
  "pagesModel": [
    {
      "order": 0,
      "name": "Pages",                         // group (no linkModel) → collapsible section
      "uuid": "62492f05-4e61-42dd-a659-6a391504e843",
      "icon": "globe",
      "heading": false,
      "children": [
        {
          "order": 0,
          "name": "Sources",
          "uuid": "8b639b71-a51c-4daa-8a85-270a5484fa0e",
          "parentUuid": "62492f05-4e61-42dd-a659-6a391504e843",
          "icon": "pe-7s-server",
          "heading": false,
          "linkModel": {                        // present ⇒ this node is a LINK
            "name": "Sources",
            "icon": "pe-7s-server",
            "identifier": "03e4579a-f1bc-4d35-9bb2-fc5515c52c9d",  // target siteMapPage identifier
            "internal": true,
            "needToBeSaved": true,
            "localizedMap": {
              "name": { "en_US": "Sources", "ru_RU": "Источники", "hy_AM": "Աղբյուրներ" },
              "icon": { "en_US": "pe-7s-server", "ru_RU": "pe-7s-server", "hy_AM": "pe-7s-server" }
            }
          },
          "children": []
        }
      ]
    }
  ]
}
```
Empty state is the literal string `"{}"`.
- **Fields:**

`PageModel` (tree node — group **or** link; `extends LocalizedBean`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `order` | int | sort order among siblings | `0` |
| `name` | String | display label (default locale) | — |
| `uuid` | String (uuid) | this node's own id; must be unique in the tree | auto `UUID.randomUUID()` |
| `parentUuid` | String (uuid) | uuid of enclosing group; omit/`null` for a top-level item (auto-set from parent on `getChildren()`) | `null` |
| `icon` | String | icon class: Pe-icon-7-stroke `pe-7s-*`, Linearicons `lnr-*`, or plain (`globe`) | `null` |
| `heading` | boolean | `true` = non-clickable section heading | `false` |
| `linkModel` | `IconNamedLinkModel` | present ⇒ node is a **link**; absent/`null` ⇒ **group/folder** | `null` |
| `roleAccess` | `RoleAccess` | optional per-item access (same shape as node `roleAccess`); omit to inherit | lazy-init empty |
| `localizedMap` | object `{name:{loc:…}, icon:{loc:…}}` | per-locale labels for **this node** — the **only** place to localize a **group heading** (a group has no `linkModel`) | — |
| `children` | `PageModel[]` | nested items; `[]` for a leaf link | lazy `[]` |
| `link` / `component` | (transient) | runtime-only Wicket `AbstractLink`/`Component`; not part of the persisted JSON | — |

`linkModel` (`IconNamedLinkModel extends NamedLinkModel extends LinkModel extends LocalizedBean`) — present only on a link:

| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | link text (default locale) | — |
| `icon` | String | icon class | `null` |
| `identifier` | String (uuid) | **internal link:** the `identifier` of the target `siteMapPage` node (resolved in the active branch — join key is the page's identifier, not alias/URL) | `null` |
| `internal` | Boolean | `true` ⇒ internal page link by `identifier`; `false` ⇒ external URL via `link` | `true` |
| `link` | String | external URL (used only when `internal == false`) | `null` |
| `params` | String | optional query/path params appended to the internal link (`ContentLinkByIdentifierParams.params`) | `null` |
| `needToBeSaved` | boolean | authoring housekeeping flag; set `true` on hand-authored items | — |
| `localizedMap` | object | per-locale `{name:{…}, icon:{…}}` — cover every `tenant.json` locale | — |

Render (`PagesPanel`): internal ⇒ `ContentLink` from `ContentLinkByIdentifierParams(activeBranchId, identifier, params)`; external ⇒ `href = link`; unresolvable ⇒ `href = "#"`; a group ⇒ collapsible section labelled by `name`.
- **Editor / settings panel:** `editComponent()` returns `NctKickerPanel(editMode=true)` → `PagesPanel` in edit mode: an **in-place sidebar tree editor** — add group, add link, edit, delete, drag-reorder — each mutation re-serialises via `modelObject.setJsonProperty("modelGroups", pageModelGroups)` and calls `onSaved()` → plugin `refresh()`. A single link is edited through `IconNamedLinkEditorFormPanel` (extends `LinkEditorFormPanel`): fields **name** (localized `TextField`), **icon** (`Pe7sDropDownField`, Pe-icon-7-stroke picker), plus the base link-editor's internal/external target (page picker → `identifier`, or external URL) and `params`. ⚠️ Per-page `left-nav` nodes are **dead data** — the shared `Nct left nav` virtual plugin renders; author quick links on that shared node's `modelGroups` (doc 17).
- **See also / source:** [17-left-nav-quick-links.md](17-left-nav-quick-links.md) (field-level authoring guide, `quicklink` tooling), [14-plugin-catalog-all.md](14-plugin-catalog-all.md), [01-content-model-and-pages.md](01-content-model-and-pages.md) · `NctKickerPlugin.java`, `NctKickerPanel.java` / `PagesPanel.java`, `model/PageModel.java`, `model/IconNamedLinkModel.java`, `IconNamedLinkEditorFormPanel.java`

### `site.right.kicker.plugin` — the right slide-out authoring drawer (settings sidebar) that hosts the whole builder console

- **Config slot:** `properties.showFromNonAuthMode` (BOOLEAN named property — **no config blob**; the plugin extends the raw `NctBasePlugin` with no config DTO) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** no — it is site chrome cloned into every `html.plugin` page-layout skeleton (`<plugin id="right-kicker" name="site.right.kicker.plugin">`), one node per page (~112–145 nodes/export), never placed or configured by a project builder.
- **Function:** Renders `NctRightKickerPanel` (added CSS class `sidebar-right`) — the right-hand slide-out drawer that is the entire builder/authoring console. It holds the Pages tree, Version Control, Site Authoring, AI settings, and every per-node settings panel (form-control/crud-table/crud-tree/process-table/workflow/form-group/layout/… all live under this panel's `rightpanels/`). In authoring mode it always renders; for a normal (non-authoring) visitor it only renders when `showFromNonAuthMode` is true, otherwise the plugin sets itself invisible and emits an empty container.
- **Config JSON** (decoded — named properties on the node, not a JSON slot):
```jsonc
// In the html.plugin layout skeleton (typical):
<plugin id="right-kicker" name="site.right.kicker.plugin">
    <property name="className" value="app-drawer-wrapper"/>          // generic node styling hook
    <property name="showFromNonAuthMode" value="true" type="BOOLEAN"/> // written on first render if absent
</plugin>
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `showFromNonAuthMode` | BOOLEAN (named prop) | Whether the right drawer is shown to non-authoring visitors. `true` → drawer renders for everyone; `false` → only in authoring mode (otherwise `setVisible(false)` + empty `WebMarkupContainer`). If the property is missing on first render, the plugin lazily writes `true` and saves the content. | `true` |
| `className` | STRING (generic node prop) | CSS class on the drawer wrapper; the base layout sets `app-drawer-wrapper`. Not specific to this plugin. | `app-drawer-wrapper` (from template) |
- **Editor / settings panel:** No editor for the node itself — `editComponent()` returns `null` and `@PluginConfig(hideInKicker = true, editBorderSelector = ".scrollbar-sidebar")` marks it as chrome that is not placed/edited from the plugin kicker. There is nothing for a builder to configure beyond the boolean above; the drawer's *content* is the authoring UI, driven by the current page selection and the platform's settings panels, not by node config JSON.
- **See also / source:** [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (catalog row + §1.3/1.4 layout skeleton), [01-content-model-and-pages.md](01-content-model-and-pages.md) (site-chrome per-page node) · `NctRightKickerPlugin.java` (`nct-ui/.../plugin/admin/kicker/right/NctRightKickerPlugin.java`), panel `NctRightKickerPanel.java`


---

## Rules / executor

### `executor.rule.script.plugin` — the Groovy rule-script editor page (CodeMirror body + right-side rule-metadata settings panel)

- **Config slot:** `properties` — **none** (`stringValue` = **no config blob**; the node ships fixed in the skeleton and reads nothing from `properties.model`). The rule being edited is resolved at runtime from the URL: `?rule=<rule identifier>` (loaded via `ruleService.findByIdentifier`) and `?list=<rules-list content identifier>` (used only by the **Close** button to redirect back). · **Editor:** `editComponent()` returns `null` → no property-panel editor; instead a **main CodeMirror form** + a **right-nav settings panel** (`RuleScriptSettingsControlPanel`). · **Hand-authored in .mrjun:** **no** — this is the base-skeleton rule editor page (group `Technical`), reached from `executor.rule.list.plugin`. Builders author *rules through it*; they never place/configure this node or hand-write its config JSON. The rule content is persisted to the executor service via `ruleService.save`, **not** into the `.mrjun` node.
- **Function:** Full-screen editor for one Groovy rule. The center pane is a CodeMirror field (`RuleEditorField`, height `80vh`) bound through a `LambdaModel` to `rule.rule.ruleScriptStr` — the raw Groovy body (the executor wraps it in the template at run time). The right settings panel edits the rule's metadata (name, description, bound contexts). Breadcrumb buttons **Update** (`ruleService.save`, toast "Rule saved successfully") and **Close** (redirect to the `?list` content) drive persistence/navigation. Model changes are broadcast to the settings panel and back via the synced-plugin event key `RuleScriptSynced`.
- **Config JSON** (decoded):
```jsonc
— none — // node carries no config blob; edited entity (RuleDto) is fetched by ?rule= and lives in the executor DB
```
- **Fields:** (the node has no config; below is the **`RuleDto`** entity this editor reads/writes — the useful field-level reference. Node-side = nothing to author.)
| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | Rule display name (edited in the right settings panel `TextField`) | — |
| `description` | String | Free-text description (settings panel `TextArea`) | — |
| `status` | RuleStatus enum | Lifecycle state (ACTIVE / INACTIVE / DRAFT) — not editable in this panel | — |
| `ruleType` | RuleType enum | EXECUTION / VALIDATION / … — set at creation, not edited here | — |
| `executor` | String | Executor id; its `displayName` labels the settings nav ("<Executor> Settings") | — |
| `contextIdentifiers` | List\<String\> | Contexts bound to the rule (settings panel `MultiSelectField`, rendered by context name) | `[]` |
| `rule` | JsonNode | Holds the script — `rule.ruleScriptStr` is the Groovy body edited in CodeMirror; created as `{}` then `{"ruleScriptStr":""}` if absent | `null` |
| `hidden` | Boolean | Whether the rule is hidden from lists | — |
| *(inherited `AbstractSecuredDto`)* | — | `id`, `identifier`, security/audit fields — `identifier` is what `?rule=` matches | — |
- **Editor / settings panel:** No `editComponent` (returns `null`). Center = a form bound to `RuleDto` containing one `RuleEditorField` (`groovyField`, CodeMirror, `height=80vh`) two-way-bound to `rule.ruleScriptStr`; the field is pre-wired with `realm/client/rule` and calls nct-ui-mcp for autocomplete/hints. Right nav = `RuleScriptSettingsControlPanel` (icon `pe-7s-tools`, active by default) with **contextIdentifiers** (MultiSelect), **name** (TextField), **description** (TextArea) — each wrapped in `synced(...)` so a `change` autosaves via the `RuleScriptSynced` event and `ruleService.save`. Breadcrumb: **Update** (`IconAjaxSubmitLink` → `ruleService.save` + `reInitBreadcrumbButtons` + success toast) and **Close** (`IconAjaxLink` → redirect to the `?list` content).
- **See also / source:** [08 — Groovy rules & context](08-groovy-rules-and-context.md) (deep coverage of `rule.ruleScriptStr` + the template wrapper + binding API), [14 — plugin catalog](14-plugin-catalog-all.md) (notes "no model/settings blob; `RuleDto` is a rep-object, `?rule=<identifier>`") · `RuleScriptPlugin.java`, `RuleScriptSettingsControlPanel.java`, `RuleDto.java` (nct-executor-common), `RuleEditorField.java`


---

## Workflow & process

### `bpmn2modeler.plugin` — the visual BPMN2 workflow diagram editor (draw / save / deploy a Flowable workflow)

- **Config slot:** `properties.*` — **none** (`stringValue` = no config blob; state is loaded server-side, not from the node) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — it is a fixed scaffold in the workflow-section base skeleton; the `siteMapPage` node just carries the `pluginName` with no hand-written config JSON.
- **Function:** The full BPMN2 modeler canvas. On init it reads the `workflow` (identifier) and optional `version` page parameters, loads the matching `FlowableWorkflowDto` via `FlowableWorkflowService` (`findByIdentifier` / `findById`, or a fresh UUID-identified draft), and renders `WorkflowBpmnEditorPanel` + a hidden `bpmnContent` textarea. Autosave (gated by `DynaformSettingsConfig.isAutosave()` and OFF while viewing a historical `?version=`) persists the draft on every debounced canvas/node edit. Breadcrumb buttons: Download BPMN2 XML, Deploy/Re-deploy, Save (hidden when autosave on), Versions (currently hidden), and Settings (opens the right nav). Passing `?version=<id>` opens a read-only deployed version with a "Back to current" button instead of Save/Deploy.
- **Config JSON** (decoded):
```jsonc
— none —   // no getJsonProperty(...) call; the plugin holds no per-node config blob.
           // The edited data is the FlowableWorkflowDto (bpmnContent XML + elements + contextIdentifiers),
           // stored by FlowableWorkflowService in the workflow store — NOT in the content node's properties.
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config fields — the plugin carries no JSON slot. It is driven by the `workflow` / `version` **page parameters** and the server-side `FlowableWorkflowDto`. | — |
- **Editor / settings panel:** No inline editor (`editComponent` → `null`). Instead it registers two **right-nav** settings tabs via `addRightSettingsNav`: (1) **Workflow Settings** (`WorkflowSettingsControlPanel`) — authors the workflow-level `FlowableWorkflowDto.contextIdentifiers` (multi-select of contexts); (2) **Node Settings** (`BpmnSettingsPanel`) — a per-selected-node panel resolved by `BpmnTaskType` through `SettingsPanelFactory` (Service Task → delegateExpression + rule; User Task → userActions; Sequence Flow → sequence + condition/rule; Call Activity → calledElement + inheritVariables/BusinessKey; else a no-control default). Submitting these writes back into the workflow's BPMN XML / DTO; Deploy calls `flowableWorkflowService.deployWorkflow`, Save calls `saveWorkflow`.
- **See also / source:** [07-workflows-and-tasks.md](07-workflows-and-tasks.md) (field-level BPMN DTO + node-settings-panel reference) · `WorkflowBpmn2ModelerPlugin.java` (extends `NctBaseModelObjectObjectSyncedPlugin<FlowableWorkflowDto>`, `group="Workflows"`, `getKey()="WorkflowSynced"`)

### `processes.plugin` — ⚠️ DEAD NAME, no registered class
- **Config slot:** none · **Editor:** none · **Hand-authored in .mrjun:** **never.**
- The Workflows-console process **list** was merged into the single master-detail `processes.selectedplugin` (below), and no class declares `processes.plugin` in `@PluginConfig` any more — so a node carrying this name misses the plugin registry and renders as `mrjun.plugin.not.found`.
- The baseline still ships **one** such node next to the working Processes panel. Leave it; never author a new one. For a process list of your own use `processes.selectedplugin`, or the live `process.table.pluin` ([05](05-crud-tree-and-process-table.md)).
- **See also:** [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (same ⚠️ treatment as the dead `pdf.report.*` pair) · [07-workflows-and-tasks.md](07-workflows-and-tasks.md)

### `processes.selectedplugin` — the whole Processes screen: one self-contained master-detail panel (process list + process detail)

- **Config slot:** `properties.model` (`stringValue` = **no config blob** — see below) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** rarely — it already ships as a fixed node in the base workflow-admin skeleton; you *may* place a second one (it is in the `Workflows` chooser group) but there is nothing to configure — the node carries no authored config, its `T` is runtime state, not persisted JSON.
- **Function:** The complete Processes screen in **one** node dropped into **one** `nct.parsis.plugin` region, rendered full-width. Left rail = header + filter bar (search, workflow dropdown, segmented status control) + a paginated card list of process instances; right = an empty state until a card is clicked, then the detail: header (workflow name, business key with copy, status badge, live pulse, created time) + row of actions (Refresh · **Workflow** → the modeler page for the workflow it was started from · **Audit logs** → the audit-log page filtered to this process · **Cancel** · **Delete**) + nav tabs **Diagram** (BPMN viewer with the active task highlighted), **Variables** (key/value table; JSON values render read-only and foldable, edited through a modal), **Sub-processes** (child call-activity processes) and **History**. One breadcrumb button — **Start process** — opens a start-process modal and selects the process it started. A `processKey` page parameter is consumed **once** on init as a deep link (this is how the process table's "open in Processes" action lands here).
- ⚠️ **Earlier builds split this screen into two plugins** — a list plugin plus a detail plugin wired by a cross-plugin `processSelected` event. That design is gone: the list half (`processes.plugin`) has no class any more (see the stub above), and the event no longer exists. Do not reproduce the two-node layout.
- **Config JSON** (decoded):
```jsonc
// — none — : the node ships only the generic empty container properties
"properties": {
  "className":     { "stringValue": "", "propertyType": "STRING" },
  "styleName":     { "stringValue": "", "propertyType": "STRING" },
  "tagProperties": { "stringValue": "", "propertyType": "STRING" }
}
// No properties.model.stringValue blob is written in ANY export.
// The selected process is runtime state held by the plugin's own workspace
// panel (list selection / "processKey" deep link) — it is never deserialized
// from a stored JSON config.
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — (no config blob) | — | Plugin holds no authored settings. Runtime model `FlowableProcessExtendedDto` = base `FlowableProcessDto` (`workflowId`, `workflowName`, `processDefinitionId/Key`, `businessKey`, `status:ProcessStatus`, `externalId`, `processInstanceId`, `groupId`, `accesses[]`, `paramsToFilter`) + `variables:Map<String,Object>` — loaded when the user picks a process, never persisted here. | `null` until a process is selected |
| `properties.className` | STRING | Optional extra CSS class on the plugin's container (generic MrJun property, ships empty). | `""` |
| `properties.styleName` | STRING | Optional inline style on the container (generic, ships empty). | `""` |
| `properties.tagProperties` | STRING | Optional extra HTML tag attributes (generic, ships empty). | `""` |
- **Editor / settings panel:** None. `editComponent()` returns `null`, so there is no inline editor and no right-nav settings tab; everything visible (list, filters, detail tabs, action buttons, **Start process**) is runtime UI, not configuration. Nothing is written back to the content tree.
- **See also / source:** [07-workflows-and-tasks.md](07-workflows-and-tasks.md) (workflow admin section — the live fixed base-skeleton nodes are `workflows.plugin` · `bpmn2modeler.plugin` · `processes.selectedplugin` · `process.table.pluin`; the `processes.plugin` node inherited alongside them is dead, see the stub above) · `ProcessSelectedPlugin.java` (`ProcessesWorkspacePanel.java` list+filter+selection, `ProcessDetailPanel.java` header/tabs, `ChildProcessesPanel.java`, `ProcessHistoryPanel.java`, `ProcessVariablesEditPanel.java`, `StartProcessPanel.java`, `FlowableProcessExtendedDto.java` / `FlowableProcessDto.java`)


---

## Lists & system

### `admin.queries.plugin` — admin console list of all saved SQL queries in the project

- **Config slot:** none (`stringValue` = no config blob — reads/writes nothing in `properties`) · **Editor:** no (`editComponent` returns `null`) · **Hand-authored in .mrjun:** no — it is a fixed management-console node in the REPORT base skeleton; a builder never places or configures it, and it stores nothing in the export.
- **Function:** Renders the "Queries" admin list page (`@PluginConfig` group `Reporting`, displayName "Queries Plugin"). Its `QueriesPanel` (a `ListViewBasePanel<QueriesFilter, QueryDto>`) loads **every** saved query for the current project via `queryService.findByRealmNameAndClientName(realm, client)` — ignoring any filter — and shows each as a row with edit (→ `/queries/query/<identifier>`) and delete (confirm → `queryService.delete`). Also exposes a "Create new query" breadcrumb/page-group button linking to `/queries/query/` (the `admin.query.plugin` single-query editor). The saved queries themselves are the `queries` rep-object; this plugin only lists them.
- **Config JSON** (decoded):
```jsonc
— none —
// QueriesPlugin extends raw NctBasePlugin (no config DTO T); initPluginContent()
// never calls getJsonProperty(...). The panel model is `new QueriesFilter()`,
// an empty marker class (implements Serializable, zero fields). No stringValue blob.
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config fields — `QueriesFilter` is an empty marker; the row data is fetched live per project, not stored on the node | — |

- **Editor / settings panel:** None. `editComponent(wicketId)` returns `null`, so there is no per-node editor and no generic settings panel writes config here. Layout-only `properties.*` (`className`/`styleName`) may exist from the skeleton but carry no plugin config. Data mutations happen through the list rows (delete) and the linked single-query editor (`admin.query.plugin`), not through this plugin's config.
- **See also / source:** [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) §1 (Queries / `QueryDto` shape) · `QueriesPlugin.java` (`plugin/report/queries/list/QueriesPlugin.java`), `QueriesPanel.java` (same package), `QueriesFilter.java` (`nct-transfer/.../transfer/filter/QueriesFilter.java`)

### `audit.log.list.plugin` — read-only audit-log browser (filter bar + master/detail viewer)

- **Config slot:** _none_ (`stringValue` = **no config blob** — extends `NctBasePlugin` as a raw type, never calls `getJsonProperty`; all state is built at runtime) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — part of the REPORT base skeleton (admin/ops "Lists" surface). A builder never places or configures this node; it ships fixed and reads no per-node JSON.
- **Function:** Renders the platform audit trail for the current tenant. a content re-init seeds an `AuditLogFilter` with fixed defaults (`rowsInPage=20`, sort `logTimestamp` DESC), fetches the distinct service names and log levels for the current realm/client from `AuditLogService`, then wires an `AuditLogFilterPanel` (top filter bar) to an `AuditLogViewPanel` (paged list + detail). Changing any filter refreshes the view and re-selects the first row. Realm/client come from `organization().getRealmName()` / `project().getClientName()`, not from config.
- **Config JSON** (decoded):
```jsonc
— none —
```
- **Fields:** _(no persisted config. For reference, the runtime `AuditLogFilter` model — built in code, never serialized into `.mrjun` — carries these query fields:)_

| Field | Type | Meaning | Default |
|---|---|---|---|
| `rowsInPage` | int (from `PagingFilter`) | Page size for the audit list | `20` |
| `sort` | `PagingSort` | Sort spec | `logTimestamp` DESC |
| `service` | String | Filter by originating service name (dropdown of distinct services) | `null` (All) |
| `level` | String | Filter by log level (ERROR/WARN/INFO/DEBUG/TRACE) | `null` (All) |
| `userId` | String | Filter by acting user | `null` |
| `traceId` | String | Filter by distributed-tracing trace id | `null` |
| `eventTypes` | `List<String>` | Multi-select event types (e.g. `USER_DATA_CHANGE`, `RULE_DATA_CHANGE`, `TASK_STARTED`, `TASK_COMPLETED`, `WORKFLOW_STARTED`), OR-combined | `[]` |
| `jsonFilter` | `JsonFilter` | Structured filter over audit-log JSON content | `null` |
| `realmName` / `clientName` | String | Multi-tenancy scope | injected from org/project at runtime |

- **Editor / settings panel:** none. No builder-facing settings dialog and no generic property config is consumed. The only interactive UI is the runtime `AuditLogFilterPanel` (service dropdown, level dropdown, event-type `ListMultipleChoice`, userId/traceId text fields) whose `onFilterChange` refreshes `AuditLogViewPanel` — this is end-user filtering, not authoring, and nothing is written back to the node.
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` (catalog stub, "admin scaffold") · `AuditLogListPlugin.java` (`plugin/auditlog/AuditLogListPlugin.java`), with `AuditLogFilterPanel.java`, `AuditLogViewPanel.java`, `AuditLogDetailPanel.java`, and `AuditLogFilter.java` (nct-transfer).

### `dynaform.context.list.plugin` — management-console list of Groovy-rule **Contexts** (CRUD-alias bundles)
- **Config slot:** none (`stringValue` = **no config blob** — the plugin never calls `getJsonProperty(...)`; it fetches its data live from `ContextService`) · **Editor:** no node editor (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — part of the base management-console skeleton (group `Forms`). A builder does **not** place or configure this node; it ships fixed and manages Context records at runtime.
- **Function:** Renders a paged table of the project's **Contexts** — a Context is a named bundle of CRUD aliases that Groovy rules address as `context.<alias>.<crudAlias>.data`. Columns are **Name** and **Crud** (the crud aliases, comma-joined). Per-row **Delete** (confirm → `contextService.delete` → refresh) and **Edit** controls, plus a breadcrumb **"Create new context"** button. Edit/Create open the `ContextEditPanel` modal (500px). Data is loaded via `contextService.findAll(realm, client, ContextFilter)`; there is no persisted plugin configuration.
- **Config JSON** (decoded):
```jsonc
— none — (the node carries no config; it is a fixed admin scaffold. Its properties.model / stringValue is unused.)
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config blob. The plugin reads no `properties.*` config; it is a raw `NctBasePlugin` (no config DTO) driving a live `DataViewBasePanel<ContextFilter, ContextDto>`. | — |

  *Managed record shape (`ContextDto`, edited in the modal — NOT plugin config):*

| Record field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | Display name of the context (required). | — |
| `alias` | String | Stable alias used by rules to reference the context (`context.<alias>...`) (required). | — |
| `crudAliases` | List<String> | The CRUD aliases bundled into this context; multi-select of the project's CRUDs (`crudService.getCrudMap`). | `[]` |
| (`id`, security) | AbstractSecuredDto | Persisted identity + row-security metadata. | — |

- **Editor / settings panel:** No builder/config editor for the node itself. At runtime, Create/Edit opens `ContextEditPanel` — a form bound to `ContextDto` with a `RequiredTextField` **name**, `RequiredTextField` **alias**, and a `ListMultipleChoice` **crudAliases** (choices = sorted CRUD aliases, rendered by CRUD display name). On submit it calls `contextService.save(realm, client, dto)`, closes the modal, and refreshes the list. Delete confirms then calls `contextService.delete`.
- **See also / source:** [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) (how contexts feed `context.<alias>.<crud>.data`), [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (catalog stub) · `plugin/context/ContextListPlugin.java`, `plugin/context/ContextEditPanel.java`, `ContextDto.java`, `ContextFilter.java`

### `executor.rule.list.plugin` — the project-wide list of Groovy rules (Technical console)

- **Config slot:** `properties.ContentChooserPanelModel` (`stringValue` = a `ContentChooserPanelModel` JSON blob — a `PropertyType.STRING` property named `ContentChooserPanelModel`, GSON-encoded) · **Editor:** yes — single-field content-page chooser form (not tabbed) · **Hand-authored in .mrjun:** no — a base-skeleton `*.list` management page in the `Technical` plugin group; it ships fixed in the REPORT skeleton. Its one config value (the rule-editor landing page) is normally set through the plugin's author editor, not hand-written.
- **Function:** Renders a paged, searchable table of every Groovy rule in the project — columns `Name` (link), `Description`, `Executor`, `Rule type`, and a red `Not used` status badge. Breadcrumb buttons: **Create new rule** / **Mark unused rules** (starts a background usage scan with a live progress strip + 2s poller) / **Delete unused rules** (shown only when `unusedCount > 0`). Row controls Edit/Delete open a `RuleEditPanel` modal. Clicking a rule **Name** redirects to the configured editor landing page with `?rule=<ruleIdentifier>&list=<thisPageIdentifier>`.
- **Config JSON** (decoded):
```jsonc
{
  // content identifier of the page that hosts executor.rule.script.plugin (the rule editor)
  "editorPageContentIdentifier": "rule-script-editor"
}
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `editorPageContentIdentifier` | String | Content identifier of the landing page that hosts the rule editor (`executor.rule.script.plugin`). Clicking a rule Name — or Create/Edit — resolves this content via `contentService.findOneByIdentifier` and redirects there with params `rule=<ruleIdentifier>` and `list=<thisPageIdentifier>`. If blank, clicking a Name shows `"No landing page found. Please edit ... and set the landing page"`. | `null` (unset until an author picks a page) |

- **Editor / settings panel:** `editComponent()` returns a `ContentChooserFormPanel` — a single form (bound to `ContentChooserPanelModel`) wrapping one `ContentChooserPanel` → `ContentPageSelectorIdentifier` widget, a content-page picker over the active branch. On submit it calls `setEditPanelModel(...)`, which writes the chosen identifier into the `ContentChooserPanelModel` string property via `content.setJsonProperty("ContentChooserPanelModel", …)` + `contentService.save(...)`, then `switchToViewMode()`. Note: this is the **same** `ContentChooserPanelModel` slot used by `dynaform.form.groups.plugin`.
- **See also / source:** deep: `doc/builder/08-groovy-rules-and-context.md`; catalog stub: `doc/builder/14-plugin-catalog-all.md` · `RuleListPlugin.java`, `ContentChooserFormPanel.java`, `ContentChooserPanel.java`, `ContentChooserPanelModel.java`

### `workflows.plugin` — the workflows list (browse / create / edit workflows, jump to the BPMN editor page)

- **Config slot:** `properties.ContentChooserPanelModel` (`stringValue` = `ContentChooserPanelModel` JSON) · **Editor:** yes — inline single-field form (`ContentChooserFormPanel`), not tabs · **Hand-authored in .mrjun:** no — ships in the workflow-section base skeleton (a `siteMapPage` node alongside `bpmn2modeler.plugin`/`processes.*`/`process.table.pluin`); a builder only repoints its landing-page pointer via the author edit panel, it is not placed or JSON-authored like a form/table/chart node.
- **Function:** Renders the list of `FlowableWorkflowDto` workflows (`WorkflowsPanel`, seeded with an empty `WorkflowFilter`). A breadcrumb "Create new workflow" button and per-row create/edit open a `WorkflowEditPanel` modal that saves through `FlowableWorkflowService.saveWorkflow(realm, client, dto)`. Clicking a workflow row calls `goLandingPage`, which resolves the configured editor page and navigates there with `?workflow=<identifier>` so the row opens in the BPMN modeler. Each row also carries a **Deploy status** badge — `Deployed` (the latest version is the deployed one), `Draft` (a deployed version exists but the latest one is not deployed) or `Not deployed` (never deployed) — and a per-row **Deploy** button that deploys the workflow's current server-side version without opening the modeler (`FlowableWorkflowService.deployWorkflow`; it refuses a workflow whose BPMN is still empty, and asks for confirmation before re-deploying an already-deployed one).
- **Config JSON** (decoded — the `ContentChooserPanelModel` blob):
```jsonc
{
  "editorPageContentIdentifier": "6c0b4335-…-68556dc6f53e"  // content identifier of the page hosting bpmn2modeler.plugin
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `editorPageContentIdentifier` | String | Content identifier of the page that carries the `bpmn2modeler.plugin` editor. `goLandingPage` looks up that content (`contentService.findOneByIdentifier`), builds its URL, and redirects with `?workflow=<row identifier>`. If **blank**, clicking a row errors: "No landing page found. Please edit workflow plugin as author and set the landing page." | `null` (empty) |
- **Editor / settings panel:** `editComponent(...)` returns `ContentChooserFormPanel` — a form bound to `ContentChooserPanelModel` whose only control is a `ContentChooserPanel` → `ContentPageSelectorIdentifier` picker bound to `editorPageContentIdentifier` (choose the modeler page from the content tree). On submit it writes the model back via `content.setJsonProperty("ContentChooserPanelModel", …)` + `contentService.save(activeBranchId, content)` and returns to view mode. (Create/edit-workflow modal and the breadcrumb button are runtime actions, not config.)
- **See also / source:** [07-workflows-and-tasks.md](07-workflows-and-tasks.md) (config-slot warning box + workflow-section plugin set) · `WorkflowsPlugin.java` (`plugin/workflow/workflows/list/`), `ContentChooserPanelModel.java`, `ContentChooserFormPanel.java`, `ContentChooserPanel.java` (`plugin/common/`). The same `ContentChooserPanelModel` slot is reused by `dynaform.form.groups.plugin` and `executor.rule.list.plugin`.


---

## Admin console

### `admin.integrations.list.plugin` — management-console table of every deployed integration pod, with Start/Stop/Delete controls

- **Config slot:** `properties.<slot>` (`stringValue` = **no config blob**) · **Editor:** no (`editComponent` returns `null`; `pageGroups` returns `null`) · **Hand-authored in .mrjun:** **no** — system Admin plugin (`@PluginConfig(group="Admin")`, `@NctPlugin(projectTypes=ORGANIZATION_MANAGER)`). Extends the **raw** `NctBasePlugin` (no config DTO type param) and never calls `getJsonProperty`, so it reads nothing from `properties`. It ships fixed in the ORGANIZATION_MANAGER base skeleton; a project builder does not place or configure it.
- **Function:** Renders a card ("Deployed Integrations") containing a `DataViewBasePanel` that lists all integrations returned by `ExecutionPlatformService.listAllIntegrations()`. Columns: Realm, Client, Name, Type (External/Internal), Docker Image, Version, Status (colored badge), Pod Name, CRUDs (count), Created. Per-row action controls: **Start** (`fa fa-play`, shown only for internal integrations in STOPPED/SLEEP/FAILED), **Stop** (`fa fa-stop`, shown only for internal RUNNING/CONNECTING/STARTING), **Delete** (`fa fa-trash`, with confirm dialog that warns it undeploys the K8s pod + drops the DB schema for internal integrations). Rows are color-tinted by status (FAILED→`table-danger`, STOPPED/SLEEP→`table-warning`). Pagination is client-side (slices the full list). While any integration is transitional (STARTING/CONNECTING/PENDING) it arms a `PluginBasePage` poller that re-renders every 4s until statuses settle, then self-disarms.
- **Config JSON** (decoded):
```jsonc
— none — // plugin reads no properties slot; the internal query filter is built in code, not from JSON:
// IntegrationsListFilter.builder().realmName(realm()).rowsInPage(15).build()
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No JSON config. Behavior is fixed in code. The in-code `IntegrationsListFilter` (extends `PagingFilter`) carries `realmName` (current realm), `rowsInPage=15`, `pageNumber=0`, `sort` — none of these are author-editable. | — |

- **Editor / settings panel:** None. `editComponent(wicketId)` returns `null` (no tabs, no generic property panel contribution) and `pageGroups(wicketId)` returns `null`. There is no settings UI and nothing to persist back — all interactivity is the runtime Start/Stop/Delete row actions, which call `ExecutionPlatformService` and `refresh()`, not a builder configuration surface.
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` (catalog stub only: "the list of integrations · scaffold, 0"); also name-dropped in `doc/builder/01-content-model-and-pages.md` under Data/integration/DB plugins · `IntegrationsListPlugin.java`, `IntegrationsListPanel.java` (nct-ui `plugin/admin/integrations/`), `IntegrationsListFilter.java` (nct-transfer `filter/`), `PagingFilter.java` (nct-transfer `dto/paging/`).

### `admin.localization.plugin` — L1 UI-chrome translation editor (admin console grid of key × locale)

- **Config slot:** _none_ (`stringValue` = **no config blob** — `LocalizationPlugin extends NctBasePlugin` *raw*, no `T` config DTO; a content re-init never calls `getJsonProperty`) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — system/admin-console plugin, `@NctPlugin(projectTypes = ORGANIZATION_MANAGER)`, `group = "Nct"`; ships fixed in the base skeleton, a project builder never places or configures it.
- **Function:** Renders the admin grid for editing **L1 UI-chrome strings** (the localization-service key catalog). Two nested `ListView`s: a header row of `RichCoreUtils.getSettingsInstance().getLocales()` (shown as `displayLanguage/displayCountry`), then one row per `localizeService.getKeys()` with the key and, per locale, a `SimpleEditableLabel` whose current value is `localizeService.getMessage(key, locale)` (falling back to `generateDefaultMessage(key, en_US-value, locale)` when null). Inline edit → `onChanged` → `localizeService.setMessage(key, value, locale)`, which persists to the **nct-localization** microservice (`translation` table, unique on `(kkey, target_lang)`), not to `branches.json`.
- **Config JSON** (decoded):
```jsonc
— none —   // no config blob; data comes live from LocalizeService + settings locales
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config DTO / no `properties.*` config blob; all rows are read live from `LocalizeService.getKeys()` and the tenant's configured locales | — |
- **Editor / settings panel:** No editor and no settings panel. `editComponent()` returns `null`, so there is no builder-side config surface. The plugin's own runtime UI is the localization grid; the only "writes" are per-cell inline edits via `SimpleEditableLabel.onChanged → LocalizeService.setMessage(key, value, locale)`, which go to the localization-service DB — these are L1 chrome translations, out of reach of a `.mrjun` export.
- **See also / source:** [20-localization.md](20-localization.md) (§L1 chrome; loader `SiteStringResourceLoader`, Feign `LocalizationClient`, `nct-localization` service) · [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (catalog: "scaffold, 0 in exports") · `LocalizationPlugin.java` (`nct-ui/.../plugin/admin/localization/LocalizationPlugin.java`)

### `admin.organizations.plugin` — Organization Manager console: the list-and-CRUD screen for all organizations (tenants)

- **Config slot:** `properties.*` (`stringValue` = **no config blob**) · **Editor:** no (`editComponent` returns `null`) · **Hand-authored in .mrjun:** no — system plugin, ships fixed in the `ORGANIZATION_MANAGER` base skeleton; `@NctPlugin(projectTypes = ORGANIZATION_MANAGER)` self-deletes on any other project type; appears in 0 exports.
- **Function:** Renders a single `OrganizationsPanel` (a `ListViewBasePanel<OrganizationFilter, OrganizationDto>`) listing every organization except the main realm (`reportOrganizationService.findAll(filter)` filtered by `uiConfig.getMainRealmName()`). Each row links to that org's management URL (`//mainProjectUrl/realmName`) and offers edit/delete. A "Create new organization" action (registered via `pageGroups`, group "Reports") and the row edit both open a `Modal` hosting `OrganizationCreatePanel`; delete is guarded so the main realm can't be removed. This is the top-level tenant/organization admin, not a data page.
- **Config JSON** (decoded):
```jsonc
— none — // plugin extends raw NctBasePlugin (T = Serializable); initPluginContent builds an in-memory OrganizationFilter.builder().build() and never calls getJsonProperty on any slot
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config blob — the node carries no builder-authored settings | — |
- **Editor / settings panel:** No builder editor (`editComponent` → `null`; view-only in the CMS). The panel's own runtime UI is the **create/edit organization modal** (`OrganizationCreatePanel`, a form bound to `OrganizationCreateModel`) with fields: `name` (required, `^[a-zA-Z][a-zA-Z0-9]*$`), `alias` (required, lowercase `^[a-z][a-z0-9]*$`), `mainClientUrl` (required), `userCanRegister` (checkbox — when on, reveals `allowedDomains` text field; unchecking nulls it), `availableThemes` (multi-select of all `Skin` display names, defaults to `Skin.defaultSelectedNames()`), and `quotaConfig` numbers (`maxEmailsPerDay`, `maxActiveProcesses`, `maxUsersPerProject`, `maxSchedulersPerProject`, each min 1, null = unlimited). Submit calls `reportOrganizationService.createOrganization(...)` / `updateOrganization(...)` (edit also syncs the org's `TenantDomain` alias/domain/name via `tenantService.save`), then `refresh()`. None of this is persisted as node JSON.
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` (catalog stub only; also named in `01-content-model-and-pages.md`) · `OrganizationsPlugin.java`, `OrganizationsPanel.java`, `OrganizationCreatePanel.java`, `OrganizationCreateModel.java`

### `admin.projects.plugin` — the admin-console "Projects" landing grid (list, create, edit, delete projects in a realm)

- **Config slot:** `properties.*` (`stringValue` = **no config blob**) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — base management-console plugin (`group = "Admin"`, `@NctPlugin(projectTypes = PRODUCTS_MANAGER)`); ships in the products-manager skeleton, reads **nothing** from `properties`, and never appears in a project export.
- **Function:** Renders `ProjectsPanel` — a responsive card grid of every project in the current realm (`reportProjectService.findByRealm(realm)`, newest-first). Each card shows a template-derived background, status badge (Active / Setting up / Failed / Expired), and View / Delete (and Retry on a failed import) actions. A breadcrumb "Create new project" button opens a modal `ProjectCreateEditPanel`; editing a card opens the same panel pre-filled. Cards render a live import-progress overlay (%-ring + stage + bar) driven by `ProjectImportStatusService`, kept fresh by a 2 s `PluginBasePage` poller while any import is in progress.
- **Config JSON** (decoded):
```jsonc
— none — // plugin reads no properties; initPluginContent() just does
         // addOrReplace(new ProjectsPanel("projects", Model.of(new ProjectsFilter())))
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config blob. `NctBasePlugin<T>` type param is unused (raw type); the panel is seeded with a fresh empty `ProjectsFilter` (a zero-field `Serializable` marker), not deserialized from `properties`. | — |

- **Editor / settings panel:** No builder-facing editor (`editComponent` → `null`, `pageGroups` → `null`). It is instead an interactive **runtime admin console**. The Create/Edit modal (`ProjectCreateEditPanel`) binds a `ProjectCreateEditModel` — fields `template`, `htmlTemplate`, `alias`, `name`, `url`, `description`, `ssoLogin` (Boolean), `maxCountOfProjects` (Integer, default 5), `expirationTime` (LocalDateTime). On submit, **create** calls `reportProjectService.createProject(...)` (realm + alias → domain, `ProjectTemplate.REPORT_APP`); **edit** calls `reportProjectService.updateProject(...)` and writes tenant properties (`theTemplateName`, `maxCountOfProjects`, alias, domain) via `tenantService.save`. Delete confirms then `reportProjectService.delete` + `orchestrationService.dismiss`; Retry re-runs a failed import via `orchestrationService.retry`. None of this is configured in a `.mrjun`.
- **See also / source:** [14](14-plugin-catalog-all.md) (catalog stub: "scaffold, **0**"; listed among platform/admin nodes absent from exports) · `ProjectsPlugin.java`, `ProjectsPanel.java`, `ProjectCreateEditPanel.java`, `ProjectCreateEditModel.java`, `ProjectsFilter.java`

### `admin.query.plugin` — single-query view/edit editor (admin "Queries" console)

- **Config slot:** _no JSON config blob_ — reads the target query from the **URL alias** (`getAliasParam(0)` = query `identifier`, page `/queries/query/<identifier>`; null alias ⇒ new blank `QueryDto`), and one optional builder property `properties.queryFieldHeight` (`intValue`) for the SQL-editor pixel height. There is **no** `stringValue`/`tabModel` blob (the commented-out `tabModels()` is dead). · **Editor:** no (`editComponent()` returns `null`; edit/save/run happens **in-page** via breadcrumb buttons, not via a builder property panel) · **Hand-authored in .mrjun:** **no** — `admin.*` management-console plugin; part of the base REPORT skeleton (the admin "Queries" area), not placed/configured by a project builder.
- **Function:** Renders the full-page editor for ONE saved SQL query (`QueryDto`, a `queries` rep-object). Breadcrumb buttons **Edit/Cancel**, **Save**, **Run** (visibility gated by `ReportSecurityService.hasEditAccess/hasExecAccess`). In edit mode it shows `QueryEditorPanel` (SQL editor + name + source picker); in view/run mode it shows `ParamsPanel` (runtime parameter filter controls). Save persists via `QueryService.save(...)` (new queries redirect to `/queries/query/<identifier>`); Run fires the `queryNavbarRunAction` event to execute and stream results. Editing the source toggles a right-nav **"Query ddl"** panel (`QueryDdlControlPanel`).
- **Config JSON** (decoded): _— none (no config blob) —_. Only builder-settable node property:
```jsonc
// on the content node's properties (NOT a JSON string blob):
{ "queryFieldHeight": 400 }   // intValue — SQL editor height in px; default 400 when absent
```
  The edited payload is the `QueryDto` rep-object (loaded/saved by the plugin, **not** stored on the page node):
```jsonc
{
  "identifier": "<uuid>",              // query id; comes from the URL alias
  "name": "<string>",                  // required (Save blocks if blank via required field)
  "query": "<SQL text w/ placeholders>", // required (Save alerts "Query should not be empty")
  "sourceIdentifier": "<source uuid>",   // required (Save alerts "Please specify source")
  "offset": 0, "itemsPerPage": 20,       // paging (defaults 0 / 20)
  "parameters": { "<name>": { "value": <obj> } }, // saved param values (usually {})
  "attributes": { "running": "true" },   // transient run flags
  "aggregations": { ... },               // QueryAggregationsDto
  "wrapInPaging": null, "statementTimeoutSeconds": null,
  "schedule": null, "lastScheduledTime": null, "hidden": null
}
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `properties.queryFieldHeight` | Integer (`intValue`) | Pixel height of the in-page SQL code editor (`SqlQueryField`) | `400` |
| _(no config-blob fields)_ | — | Plugin has no `stringValue`/`tabModel` JSON; edited object is the `QueryDto` rep-object addressed by URL alias | — |

- **Editor / settings panel:** No builder editor panel (`editComponent` → `null`). Its "UI" is the runtime editor itself: `QueryEditorPanel` binds `query` (→ `SqlQueryField`, CodeMirror-style SQL editor sized by `queryFieldHeight`), `name` (`RequiredTextField`), and `sourceIdentifier` (`DropDownChoice` over the project's `SourceDto` list; `OnChangeAjaxBehavior` re-renders and swaps the DDL right-nav). Save writes the `QueryDto` back through `QueryService.save(realm, client, dto)`; there is no per-node config to persist on the page.
- **See also / source:** doc [12 — Queries, Sources, Schedulers & REST](12-queries-sources-schedulers-and-rest.md) §1 (full `QueryDto` shape) — the plugin itself is only a catalog stub there and in [14 — plugin catalog](14-plugin-catalog-all.md); the `queryFieldHeight` node property is currently undocumented · `QueryPlugin.java` (`@PluginConfig`, group `Reporting`), `QueryEditorPanel.java`, `ParamsPanel.java`, `QueryDto.java`.

### `admin.rolegroup.management.plugin` — role-group (permission-set) admin console

- **Config slot:** _none_ — no config blob is read (`RoleGroupManagementPlugin extends NctBasePlugin` **raw**, never calls `getJsonProperty(...)`; it fetches live data from `NctRoleGroupService`) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — it is an `admin.*` management-console node baked into the REPORT base skeleton; a project builder never places or configures it, and its page node carries no authored JSON (only fixed `properties.className/styleName`).
- **Function:** Renders the list of **role groups** for the current org/project (`nctRoleGroupService.all(realmName, clientName)`), each with **edit** and **delete** (confirmation) row links, plus a breadcrumb **"Create new role group"** button. Create/edit opens a `RoleGroupCreateEditPanel` modal. Visibility is permission-gated: groups containing `ADMIN` are hidden from non-admin-email users, groups containing `NCT_AUTHOR` are hidden from non-author/non-admin users; the built-in `"Author"` group cannot be edited or deleted. `@PluginConfig(group = "Nct")`.
- **Config JSON** (decoded):
```jsonc
— none — // page node has no config blob; the plugin reads no model/settings.
         // The *data* it manages is exported separately at rep-objects.json → .roleGroups[]
         // as an array of RoleGroupDto (documented in doc 12 §4), NOT in this page node:
// { "id": "<group-id>", "name": "Manager", "roles": ["REPORT_VIEW", "REPORT_EDIT", ...] }
```
- **Fields:** (no config-blob fields on the node; the managed **`RoleGroupDto`** data object it CRUDs — see doc 12 §4)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `id` | String (numeric) | Internal group id (Keycloak/RDBMS); referenced by `userRoleGroupAssignments.roleGroupId`. `null` on create | — |
| `name` | String | Group name. `@NotBlank`. Import matches groups **by name**, not id | — |
| `roles` | `List<ReportRole>` | Permission set (`@NotNull`); enum has 31 values (`ADMIN`, `NCT_AUTHOR`, `REPORT_*`, `SCHEDULER_*`, `SOURCE_*`, `STORE_EXECUTE*`, `FILE_STORAGE_*`, `PROJECT_*`, `ORGANIZ*`, `ROLE_GROUP_*`, `USER_*`, …) | `[]` |

- **Editor / settings panel:** No plugin editor (`editComponent → null`). The **create/edit** UI is the `RoleGroupCreateEditPanel` modal (a form bound to `RoleGroupDto`, 700px, Save/Cancel via `DokieModalUtils`): a required **name** field, plus two mutually-exclusive modes toggled by an "Advanced Role Assignment" link that is only shown to the admin/special-author email. **Basic mode** = a `RoleGroupType` dropdown (`ADMIN` / `AUTHOR` / `USER`, gated by user role) whose selection populates `roles` via `RoleGroupType.getRolesForProjectType(projectType)` / `getDefaultRoles()`. **Advanced mode** = a `MultiSelectField<ReportRole>` over `ReportRole.rolesOf(projectType)` for direct per-role selection. On submit, roles are re-derived from the type (basic mode) then written back and persisted via `nctRoleGroupService.create(...)` (id null) or `update(...)`; the plugin then `refresh()`es the list.
- **See also / source:** doc **12** §4 (`roleGroups` export shape, field-by-field `RoleGroupDto`, full `ReportRole` list) · doc 14 catalog · `RoleGroupManagementPlugin.java` · `RoleGroupCreateEditPanel.java` · `RoleGroupDto.java` (`nct-transfer`)

### `admin.schedulers.plugin` — admin console page that lists/creates/edits cron schedulers ("on cron → check predicate → run rule")

- **Config slot:** `properties.*` (`stringValue` = **no config blob** — `SchedulerPlugin extends NctBasePlugin` as a **raw type**, no config DTO, and never calls `getJsonProperty`; the node carries only base chrome props) · **Editor:** no in-page editor (`editComponent()` returns `null`); records are edited in a **modal form** (7 fields) launched from the list · **Hand-authored in .mrjun:** **no** — this is a fixed management-console page in the REPORT base skeleton; it is not placed/configured by a builder. The data it manages (`ScheduleDto` entries) lives separately in `rep-objects.json → .schedulers[]`.
- **Function:** Renders a paged admin table of the project's schedulers (`schedulerService.findAllPaged`, filter hardcoded to `rowsInPage=15`, sort `modificationTime` desc). Columns: **Name**, **Enabled** (Yes/No), **Check Schedule** (`job.explanation` ?? `job.expression`), **Last Action** (`lastActionTime`), **Cooldown Until** (`cooldownUntil`). Row actions **Edit**/**Delete** (delete confirms then `schedulerService.delete`); a breadcrumb button **"Create new scheduler"** opens the modal editor pre-seeding `actionType=RUN_RULE` and `serviceUserId`/`serviceUserEmail` = current user. It does **not** run schedules — firing happens headless in `nct-schedule`/`nct-executor`.
- **Config JSON** (decoded) — *not a page-node blob; this is the `ScheduleDto` shape the editor writes and a builder hand-authors into `.schedulers[]`*:
```jsonc
{
  "identifier": "<uuid>",            // AbstractSecuredDto; id/realmName/clientName/creationTime/modificationTime server-managed
  "name": "Nightly overdue check",
  "job": {                            // primary cron: when to CHECK
    "expression": "0 0 2 * * *",      // full 6-field Spring cron (sec min hour dom mon dow)
    "explanation": "At 02:00 every day", // auto-filled on save via cronService.explain()
    "cronType": null                  // UI-only preset; ignored at runtime — leave null
  },
  "predicateIdentifier": "<rule-uuid>",   // PREDICATE rule; blank ⇒ fires every tick
  "actionType": "RUN_RULE",               // only enum value
  "actionRuleIdentifier": "<rule-uuid>",  // EXECUTION_RULE run (async via Kafka) when predicate true
  "cooldownJob": { "expression": "0 0 8 * * *", "explanation": "…", "cronType": null }, // sets cooldownUntil = next fire; blank ⇒ no cooldown
  "enabled": false,                       // ⚠ true ⇒ live CronTrigger the moment the .mrjun imports
  "serviceUserId": "<user-uuid>",         // headless identity for BOTH predicate + action hops
  "serviceUserEmail": "svc@…",
  "cooldownUntil": null,                  // runtime state — nulled by server on save
  "lastActionTime": null,
  "lastPredicateCheckTime": null
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String | Display name (required in editor) | — |
| `job` | `CronJob` | Primary "check" schedule (`expression`, `explanation`, `cronType`) | new empty `CronJob` (lazy) |
| `predicateIdentifier` | String | PREDICATE rule UUID gating the action; blank ⇒ always true | null |
| `actionType` | `ActionType` enum | Action kind — only `RUN_RULE` | null (editor sets `RUN_RULE`, nullValid=false) |
| `actionRuleIdentifier` | String | EXECUTION_RULE UUID run when predicate passes | null |
| `cooldownJob` | `CronJob` | Secondary cron computing `cooldownUntil` (suppress window) | new empty `CronJob` (lazy) |
| `enabled` | boolean | Whether the schedule is registered/live; only `enabled==true` load on startup | false |
| `cooldownUntil` | Instant | Runtime: suppressed until this time | null (server-nulled on save) |
| `lastActionTime` | Instant | Runtime: last action fire | null |
| `lastPredicateCheckTime` | Instant | Runtime: last predicate evaluation | null |
| `serviceUserId` | String | Headless executor identity (userId) for predicate + action | null (editor sets current user) |
| `serviceUserEmail` | String | Headless executor email | null |
| `id`/`identifier`/`realmName`/`clientName`/`creationTime`/`modificationTime` | (from `AbstractSecuredDto`) | Server-managed keys/timestamps | server-set |
| **`CronJob.expression`** | String | Full 6-field Spring cron; read directly at registration | — |
| **`CronJob.explanation`** | String | Human text, auto-filled by `cronService.explain()` on submit | — |
| **`CronJob.cronType`** | `CronType` enum | UI-only preset builder (6 wildcarded presets); **has zero runtime callers** — leave null | null |
- **Editor / settings panel:** No `editComponent` (view-only in-page). Editing uses a **Wicket modal** hosting `SchedulerFormEditorPanel` — a form bound to `ScheduleDto` with: `name` (RequiredTextField), `enabled` (CheckBox), primary `CronEditorPanel` → `job`, `predicateIdentifier` (RuleIdentifierSelectorField, `PREDICATE`, create-suggestion "Scheduler <name> Predicate"), `actionType` (DropDownChoice, values=`[RUN_RULE]`), `actionRuleIdentifier` (RuleIdentifierSelectorField, `EXECUTION_RULE`, create-suggestion "Scheduler <name> Action Rule"), secondary `CronEditorPanel` → `cooldownJob`. On submit it fills both cron `explanation`s via `cronService.explain(...)`, then `schedulerService.save(realm, client, dto)`, closes the modal, refreshes the table, toasts create/update.
- **See also / source:** [12-queries-sources-schedulers-and-rest.md §3](12-queries-sources-schedulers-and-rest.md) (deep: field table, `CronType`/`ActionType`, the two-hop fire pipeline, `.schedulers[]` authoring + `enabled:true` build-safety warning + quota) · catalog stub [14-plugin-catalog-all.md](14-plugin-catalog-all.md) · `SchedulerPlugin.java`, `SchedulerFormEditorPanel.java`, `CronEditorPanel.java`, `ScheduleDto.java`, `CronJob.java`, `CronType.java`, `ActionType.java`, `SchedulerFilter.java`

### `admin.sources.plugin` — admin console listing/CRUD of a project's DB connection sources
- **Config slot:** `properties.*` — **no config blob** (the plugin never calls `getJsonProperty`; the node carries only `className`/`pluginName`). Its slot hint `model` is unused. · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — this is an `admin.*` management-console plugin in the base REPORT skeleton; a builder never places or configures it, and the source records it manages live in `rep-objects.sources`, not in the page node.
- **Function:** Renders a `SourcesPanel` (a `ListViewBasePanel<SourcesFilter, SourceDto>`) that lists every DB source for the current realm/client (`sourcesService.findByRealmAndClient`), with per-row **edit**/**delete** and a "Create new source" button (page-group + breadcrumb). Create/edit pop a `SourceEditorPanel` modal (700px) whose submit calls `sourcesService.save(realm, client, source)`; delete confirms then `sourcesService.delete`. Sources are the DB-connection objects referenced by queries (`sourceIdentifier`) and dynamic CRUDs.
- **Config JSON** (decoded):
```jsonc
// — none — the plugin node stores no config.
// Node reads no properties slot; SourcesPanel is built from a fresh, empty SourcesFilter (no fields).
// The managed records live separately in rep-objects.json → .sources[] as SourceDto (see doc 12 §2).
```
- **Fields:** (node has no config; the table below is the **`SourceDto`** record the editor modal writes — from `nct-transfer/.../dto/SourceDto.java`, inheriting `AbstractSecuredDto`)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `name` | String (`@NotBlank`) | Source name; for an internal schema = the schema name | — |
| `dbType` | enum `DbType` (`@NotNull`) | DB engine. Only value: `POISTGRESQL` (display "Postgresql", id `postgresql_database`) | — |
| `hostName` | String (`@NotBlank`) | Postgres host (overwritten on import) | — |
| `port` | Integer (`@NotBlank`) | Port | — |
| `dbName` | String (`@NotBlank`) | Database name | — |
| `schemaName` | String (`@NotBlank`) | Schema name | — |
| `userName` | String (`@NotBlank`) | DB user | — |
| `password` | String | DB password (hex-encrypted; `PasswordTextField` with `setResetPassword(false)`) | null |
| `description` | String | Free-text description — **not** in the editor form (set only by import/backend) | null |
| `sourceType` | enum `SourceType` | `INTERNAL` (project schema) / `EXTERNAL` (3rd-party) / `INTEGRATION` (pod) / `SYSTEM` (dyn-integration metadata, hidden). **Not** in the editor form | `INTERNAL` |
| `identifier`,`id`,`realmName`,`clientName`,`creationTime`,`modificationTime` | inherited `AbstractSecuredDto` | `identifier` (UUID) is the stable id referenced by queries/CRUDs | — |

- **Editor / settings panel:** No node editor. The runtime **`SourceEditorPanel`** modal is a form bound to `SourceDto` with exactly 8 inputs: `name` (RequiredTextField), `dbType` (DropDownChoice of `DbType.values()`, `ChoiceRenderer("name")`, required), `hostName` (RequiredTextField), `port` (NumberTextField, required), `dbName`, `schemaName`, `userName` (RequiredTextField each), `password` (PasswordTextField). Save/Cancel buttons wired via `DokieModalUtils.addModalSaveAndCancelButtons`. `description` and `sourceType` are **not** editable here. Submit → `sourcesService.save(...)` then `refresh()`.
- **See also / source:** [doc 12 §2 Sources](12-queries-sources-schedulers-and-rest.md) (full `SourceDto` export shape + field-by-field + `DbType`/`SourceType` semantics) · `SourcesPlugin.java` (`plugin/report/sources/SourcesPlugin.java`), `SourcesPanel.java`, `SourceEditorPanel.java`, `SourceDto.java`, `DbType.java`, `SourceType.java`

### `admin.user.management.plugin` — project user roster + create/edit/delete users and their role-group assignments

- **Config slot:** _none_ (`properties.model.stringValue` = **no config blob** — the plugin extends `NctBasePlugin` **raw**, never calls `getJsonProperty(...)`; the user list is loaded live from `NctUserService.all(realm, client)`) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — it is one of the fixed `admin.*` management-console nodes that ship in the REPORT base skeleton (`empty/branches.json → siteMapPage`); a builder never places it or writes config JSON for it.
- **Function:** Renders a table of every user in the current project (Name + comma-joined role-group names) with per-row **Edit** and **Delete** (confirm) buttons, plus a **"Create new user"** breadcrumb button. Edit/Create open a modal (`UserCreateEditPanel`) for first/last name, email, conditional password, and a role-group multi-select. New users go through `ReportSecurityService.registerNewUser(...)`; existing users through `NctUserService.update(...)`; delete via `NctUserService.delete(...)`. Data is entirely runtime; nothing is persisted into the page node.
- **Config JSON** (decoded):
```jsonc
— none — // no settings/model blob is read or written; the node is a bare skeleton entry (className/access only)
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config DTO — plugin reads zero JSON config; the modeled data is the live user roster from `NctUserService` | — |

- **Editor / settings panel:** No property/settings editor (`editComponent` → `null`; view-only in the CMS editor). Its interactive UI is runtime-only: (1) the user table (`ListView "data"` over `UserDto`, 2) the **`UserCreateEditPanel`** modal — a form bound to `UserDto` binding `RequiredTextField firstName`, `RequiredTextField lastName`, required `EmailTextField email`, a conditionally-visible `PasswordTextField password` (only shown for the admin/author system accounts, gated behind a "set password" link), and a `MultiSelectField<RoleGroupDto> roleGroups` (rendered by `RoleGroupDto::getName`). The role list is filtered by privilege — `ADMIN` groups hidden unless editing the admin account; `NCT_AUTHOR` groups hidden unless editing admin/author or the caller holds `NCT_AUTHOR`; the project owner's **Author** group is force-selected and locked (client JS re-selects on every change). On submit it writes back into the `UserDto` and calls the abstract `onSubmit`, which registers (new) or updates (existing) then `refresh()`es the table. None of this touches the `.mrjun`.
- **See also / source:** [doc 12 §5 (users, role groups, `userRoleGroupAssignments` binding)](12-queries-sources-schedulers-and-rest.md) · [doc 14 admin-page catalog](14-plugin-catalog-all.md) · `UserManagementPlugin.java`, `UserCreateEditPanel.java` (`plugin/admin/usermanagement/`)

### `database.management.plugin` — the admin "Database" page: sources/schemas/tables + ERD canvas + SQL query runner

- **Config slot:** `properties.model` (`stringValue` = `DatabaseManagementPluginModel` JSON — ERD canvas UI state only) · **Editor:** no (`editComponent()` returns `null` — view-only authoring node) · **Hand-authored in .mrjun:** **no** — part of the REPORT base skeleton (the Technical-group "Database" admin page). The `model` blob is UI state written back at runtime by the panels (`persistModel()` → writes `properties.model`), never hand-composed; it does **not** describe the schema.
- **Function:** The management console for a project's data sources. Left `SchemaTreePanel` lists internal schemas + external connections + saved queries; right side swaps between `DatabaseContentPanel` (tables list, table detail, ERD canvas with drag-positioned tables and drawable FKs) and `QueryContentPanel` (SQL runner). All DDL (create/drop/rename table, add/edit column, create index/trigger/constraint, add/delete FK) fires immediately via `ProjectDatabaseService` (Feign → nct-query), not into the export. Breadcrumb buttons "Add Source" + "Refresh" show for `NCT_AUTHOR`/`ADMIN`. A `SyncedPlugin` (`getKey()="DatabaseManagementSynced"`).
- **Config JSON** (decoded — `properties.model.stringValue`):
```jsonc
{
  "selectedSchemaId": "rimm_<realm>_<client>",   // last schema clicked in the tree
  "selectedTableId": "rimm_brand",               // last table clicked
  "zoomLevel": 0.5,                              // ERD canvas zoom (0.5–2.0)
  "tablePositions": {                            // per-table {x,y} on the ERD canvas
    "rimm_brand": { "x": 30,  "y": 30 },
    "users":      { "x": 734, "y": 25 }
  },
  "scrollX": 0,
  "scrollY": 0
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `selectedSchemaId` | string | Schema/source last selected in the tree; restored on reload (matched against `SourceDto.schemaName`). | `null` |
| `selectedTableId` | string | Table last selected under that schema; re-selected on reload. | `null` |
| `zoomLevel` | double | ERD canvas zoom, clamped 0.5–2.0. | `1.0` |
| `tablePositions` | map `{tableId: {x:int, y:int}}` (`TablePosition`) | Saved x/y of each table box on the ERD canvas. | `{}` |
| `scrollX` | int | ERD canvas horizontal scroll offset. | `0` |
| `scrollY` | int | ERD canvas vertical scroll offset. | `0` |

  Nested `TablePosition`: `x` (int), `y` (int) — pixel coordinates of a table box.
- **Editor / settings panel:** No editor and no generic property panel — `editComponent()` returns `null`. There is no builder-facing config; the whole plugin *is* its runtime UI. It also reads a plain property `projectDatabaseName` (`PropertyType.STRING`) via `getContent().getPropertyOrNull(...)`, falling back to `tenant().getProperty("projectDatabaseName")` — the physical DB name the content panel operates on. The `model` slot is persisted only as a side effect of user interaction (selecting a schema/table, dragging tables on the canvas → `onPluginModelChanged()` → `persistModel()`).
- **See also / source:** [10-database-management.md](10-database-management.md) (field-level table already present, §"The plugin", Gotcha 6) · `DatabaseManagementPlugin.java` (`plugin/dynamic/database/`), config DTO `DatabaseManagementPluginModel.java`; panels `SchemaTreePanel` / `DatabaseContentPanel` (+ `ErdCanvasPanel`) / `QueryContentPanel`.

### `discovery.plugin` — Customer Discovery workspace (record/transcribe conversation sessions, generate project docs)

- **Config slot:** `properties.model` (`stringValue` = GSON-serialized `DiscoveryPluginModel` — runtime UI state, not a builder blob) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** no — REPORT-only management-console page (`@NctPlugin(projectTypes = REPORT)`, `group = "Technical"`, icon `lnr-mic`); it ships in the base skeleton and writes its own `model` at runtime via `persistModel()` (`getContent().setJsonProperty("model", …)` → `saveContent()`). A builder never places or configures it.
- **Function:** Two-tab discovery cockpit for REPORT projects. **Sessions** tab lists recorded conversation sessions (fetched via `DiscoveryClient.listSessions()`), lets you create one (New-session modal → `createSession`), select one (opens `SessionDetailPanel` with live `AudioRecorderField` recording + 2s transcript/status polling + playback), and delete one (removes recording/transcript + best-effort audio file via `FileStorageService`). A **Finalize** button is gated by `DiscoveryClient.getFinalizeReadiness()` and, when ready, starts/opens a finalization run (`FinalizeProjectDialog`) that produces project business documentation. **Documents** tab (`DocumentsTabPanel`) shows the generated docs. All backing data lives in the `discovery` microservice via `DiscoveryClient`; the plugin's own `properties.model` only remembers which tab/session/doc the user last had open.
- **Config JSON** (decoded — this is persisted UI state, not authored config):
```jsonc
{
  "activeTab": "sessions",        // "sessions" | "documents"
  "selectedSessionId": null,      // id of the session whose detail panel is open
  "selectedDocumentSlug": null    // slug of the document open in the Documents tab
}
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `activeTab` | String | Which header tab is shown; `"sessions"` or `"documents"`. Drives `applyTabVisibility()`. | `"sessions"` |
| `selectedSessionId` | String | Id of the currently selected recording session; gates `SessionDetailPanel` (null → empty detail placeholder). | `null` |
| `selectedDocumentSlug` | String | Slug of the currently selected generated document in the Documents tab; gates the doc viewer. | `null` |

- **Editor / settings panel:** None. `editComponent(String)` returns `null`, so the builder exposes no edit dialog and no property panel for authoring config. The three model fields are set only by user interaction at runtime (tab click → `switchTab`, session click → `selectSession`, doc selection → `notifySelectionChanged`), each followed by `persistModel()`. Everything else (sessions, transcripts, readiness, finalize runs, documents) is server state served by `DiscoveryClient`, not stored in the node.
- **See also / source:** [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (absent-table stub — names `DiscoveryPluginModel` but has no field-level table until now) · `DiscoveryPlugin.java` (`initPluginContent` line 68, `getJsonProperty("model", …)` line 69, `editComponent` returns null line 460) · `DiscoveryPluginModel.java` · `DiscoveryClient` (Feign) · `SessionDetailPanel` / `DocumentsTabPanel` / `NewSessionDialog` / `FinalizeProjectDialog`.

### `dynaform.form.groups.plugin` — admin "Form Groups" list scaffold (group-LIST page)

- **Config slot:** `properties.ContentChooserPanelModel` (`stringValue` = JSON of `ContentChooserPanelModel` — a one-field blob `{editorPageContentIdentifier}`; NOT a `model` slot) · **Editor:** yes, single content-picker (no tabs) · **Hand-authored in .mrjun:** **no** — ships in the base skeleton. The node exists verbatim in every project export, with the *same* `identifier 8042da27-e264-4b43-9a4c-0882c06b3110`, on the shared admin "Form Groups" page (`alias:"form"`, `identifier e714bbd4-…`). Builders add `formGroups[]`/`forms[]` to `rep-objects.json`, they do **not** place this node; if you clone the skeleton page keep the node (and its `ContentChooserPanelModel`) unchanged.

- **Function:** Renders the runtime **list of form groups** on the admin page (`FormGroupsPanel extends ListViewBasePanel`), fed by `formGroupService.findAll(realm, client, FormGroupFilter{formGroupsPageIdentifier = this page's identifier})` — i.e. it lists the groups whose `formGroupsPageIdentifier` points at this page. Provides a breadcrumb **"Create new form group"** button and per-row Edit/Delete (delete cascades: deletes every `FormDto` in the group first) and an **Open** link that navigates to the group's landing page (`?group=<identifier>&caller=<thisPageUniqueId>`). The list data and the create/edit dialog (`FormGroupEditPanel`) are all runtime; the only *config* on the node is the default-landing pointer below.

- **Config JSON** (decoded — the `properties.ContentChooserPanelModel.stringValue` STRING, JSON-encoded):
```jsonc
// properties.ContentChooserPanelModel = { propertyType:"STRING", key:"ContentChooserPanelModel",
//   fieldPanelClass:"…PropertyBaseTextFieldPanel", stringValue: <the JSON below, escaped> }
{ "editorPageContentIdentifier": "ec99a5a0-3605-4843-94ad-cf7fb4deb5a5" }
```

- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| `editorPageContentIdentifier` | String (page `identifier`) | The **default landing page** for groups created/edited from this list. `createUpdateFormGroup`/`goLandingPage` copy it into a group's `contentPageIdentifier` (via `getEditPanelModel().getEditorPageContentIdentifier()`), and the row **Open** link uses it to resolve the landing URL. If blank, Open shows `"No landing page found. Please edit form group plugin as author and set the landing page"` and per-group saves keep whatever landing the group already had. | `null` (baseline ships `ec99a5a0-…`; keep verbatim) |

- **Editor / settings panel:** `editComponent()` returns a `ContentChooserFormPanel` (reached via "edit plugin as author"). It is a single form bound to `ContentChooserPanelModel` wrapping one `ContentChooserPanel` bound to `editorPageContentIdentifier` (a CMS content/page picker) — **no tabs**. On submit it writes the model back via `contentService.save` into `properties.ContentChooserPanelModel` and returns to view mode. The visible group **list**, the **"Create new form group"** breadcrumb button, and the per-group create/edit dialog (`FormGroupEditPanel` — name / `formGroupsPageIdentifier` selector / `placeFormsNextToLanding` flag, which on toggle prompts and relocates each form's CMS page via `FormPagePlacementUtil`) are runtime UI driven by `formGroupService`/`formService`, **not** persisted in this node's config.

- **See also / source:** [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) (the group-list node, `ContentChooserPanelModel{editorPageContentIdentifier}` = default landing, keep verbatim; `FormGroupDto.formGroupsPageIdentifier` linkage) · [07-workflows-and-tasks.md](07-workflows-and-tasks.md) (same `ContentChooserPanelModel` slot as `workflows.plugin`/`executor.rule.list.plugin`) · [14-plugin-catalog-all.md](14-plugin-catalog-all.md) ("admin scaffold") · `FormGroupsPlugin.java` (`nct-ui/.../plugin/dynaform/formfroups/`), `FormGroupsPanel.java`, `ContentChooserFormPanel.java` / `ContentChooserPanelModel.java` (`nct-ui/.../plugin/common/`).

### `dynamic.cruds.plugin` — "Business Logic Dynamic Integration" console: browser tool for defining dynamic CRUDs, methods, fields, sources & enums

- **Config slot:** `properties.model` (`stringValue` = JSON of `DynamicCrudsPluginModel` — UI navigation state only, **not** the CRUD payload) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — this is a base-skeleton *Technical* management console (`group="Technical"`, `projectTypes={REPORT}`). A builder does not place it per-page or hand-write its config; the `model` blob is just the console's own persisted view-state (last-selected CRUD, active tabs, default source, page size). The **real** artifact it edits — dynamic CRUD/method/field/source/enum definitions — lives in the project DB (`dynamic_crud`/`dynamic_method`/`dynamic_field`) and exports to a separate **`dynamic-cruds.json`**, never into this node.
- **Function:** Two-column console: a source status bar on top, a left pane that tab-switches between the **CRUDs** list (`crudClient.findAll`, static + dynamic, minus the `bl` façade) and the **Enumerations** list, and a right pane showing the selected CRUD's **Methods / DTO fields / Filter fields / Enums** tabs. All actual creation/editing happens in modal dialogs and persists through the `bl` system CRUD over RSocket (`reactorCrudService` / `crudClient`), not through this plugin's config. Static `@Crud` beans render read-only; only purely-dynamic rows expose edit/delete/clone.
- **Config JSON** (decoded — the persisted view-state, nothing more):
```jsonc
{
  "rowsPerPage": 50,                              // int, page size of the left CRUD list
  "selectedCrudId": "tasks_cruid",               // last-opened CRUD ALIAS (not a UUID); reloaded into right pane on open; null when none
  "globalSourceIdentifier": "9801cfaa-e98d-…",   // UUID of the default src_source; preselected for new CRUDs, shown in source bar; null = "No source selected"
  "leftTab": "CRUDS",                            // "CRUDS" | "ENUMS"
  "rightTab": "METHODS"                          // "METHODS" | "DTO" | "FILTER" | "ENUMS"
}
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| `rowsPerPage` | int | Page size of the left-pane CRUD list | `50` |
| `selectedCrudId` | String | Last-selected CRUD **alias** (despite the name it holds the alias, keyed by alias since a purely-static CRUD has no UUID); reloaded into the right pane on open | `null` |
| `globalSourceIdentifier` | String (UUID) | Default data source (`src_source` identifier) preselected when creating a new CRUD and shown in the source-status bar; also drives credential re-bind after rotation | `null` |
| `leftTab` | String | Active left-pane tab — `"CRUDS"` (dynamic CRUD list) or `"ENUMS"` (project Enumerations) | `"CRUDS"` |
| `rightTab` | String | Active right-pane detail tab — `"METHODS"` \| `"DTO"` \| `"FILTER"` \| `"ENUMS"` | `"METHODS"` |
- **Editor / settings panel:** **No `editComponent` editor** — the plugin body *is* the tool. All editing flows through modal dialogs: `CreateCrudDialog` (alias+name+source → `bl.create`), `CrudEditorPanel` (single SQL/Groovy method → saves paired query + hidden Groovy rule), `FieldEditorDialog` (DTO/Filter field + FK-join), `DefaultMethodsDialog` ("Create Default Methods" → 7 SQL/Groovy CRUD methods), `ConfigureSourceDialog`/change-source, `RunMethodDialog` (introspect → `bl.setReturnFields`), and the enum dialogs (`CreateEnumDialog`/`EnumValuesDialog`, kind `FREE`). These write to the project DB via `bl.*`. The plugin writes back to `properties.model` **only** navigation state, via `persistModel()` → `getContent().setJsonProperty("model", …)` + `saveContent()`. Extends `NctBaseModelObjectObjectSyncedPlugin<DynamicCrudsPluginModel>`; state is broadcast to sibling instances through the SyncedPlugin key `"DynamicCrudsSynced"` (`getKey()`).
- **See also / source:** [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) — exhaustively documents the **`dynamic-cruds.json` export payload** (CRUD/method/field/parameter shape) that this console produces, but only *names* (does not field-table) the node's own `properties.model` blob · `DynamicCrudsPlugin.java` · `DynamicCrudsPluginModel.java`

### `messaging.mail.templates.plugin` — base-skeleton admin CRUD page for HTML email templates (GrapesJS editor)
- **Config slot:** `properties.*` (`stringValue` = **no config blob**; only base `className`/`styleName`/`tagProperties`) · **Editor:** no builder `editComponent` (returns `null`) — the *page itself* is a runtime CRUD with an in-page GrapesJS visual editor · **Hand-authored in .mrjun:** **no** — it is a fixed top-level `siteMapPage` "Mail Templates" that ships in the base REPORT skeleton; a builder never places or configures this node, and the actual template data lives in `rep-objects.mailTemplates[]` (a DB-backed object saved via `mailTemplateService`), not in the node.
- **Function:** Management-console page (`group="Nct"`, icon `pe-7s-mail`). Lists mail templates in a `DataViewBasePanel` (columns Name/Subject/Description/Active, sorted by `modificationTime` desc, 15/page; row controls Delete + Edit). "Create new template" / clicking a name toggles `editorMode` and swaps in `MailTemplateEditorPanel` — a form over `MailTemplateDto` with a GrapesJS (`grapesjs-preset-newsletter`) visual HTML editor + image-upload AJAX behavior (uploads to `t/<realm>-<client>/mail-templates/…`). Breadcrumb buttons switch between Save/Back-to-list and Create. A right-nav `MailTemplateSettingsPanel` gives a live template picker. All persistence goes through `mailTemplateService.findAll/save/delete/findByName/findByAlias` (nct-messaging DB `mail_templates`); state is broadcast via the `NctBaseModelObjectObjectSyncedPlugin` sync key `"MailTemplateSynced"`.
- **Config JSON** (decoded):
```jsonc
// The plugin NODE has no config blob — properties are only the base slots:
//   { "className": "...", "styleName": "...", "tagProperties": {...} }   (all optional, usually empty)
//
// The substantive data it manages is NOT in the node; it is a MailTemplateDto object,
// exported to rep-objects.mailTemplates[] and saved via mailTemplateService:
{
  "identifier": "28b15560-5da6-4c17-8059-0d8f9b663ee3",
  "name": "sendIntakeInit",
  "alias": "sendIntakeInit",            // programmatic key used to send the mail
  "subject": "Intake Init",             // may contain {{placeholder}}
  "description": "Intake Init",
  "active": true,
  "placeholders": ["firstName", "lastName"],
  "htmlContent": "<body …>Hi {{firstName}} {{lastName}}…</body>",
  "cssContent": "* { box-sizing: border-box; } …",
  "gjsData": "{\"assets\":[…],\"styles\":[…],\"pages\":[…]}"
}
```
- **Fields:** (the node carries no config fields; rows below are the base `properties.*` slots it *may* hold, all optional/empty in practice)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `properties.className` | `String` | Extra CSS class on the plugin wrapper | — (empty) |
| `properties.styleName` | `String` | Inline style on the wrapper | — (empty) |
| `properties.tagProperties` | `Map` | Extra HTML tag attributes | — (empty) |
| *(no `properties.model`/config blob)* | — | Config is not stored on the node; template data lives in `rep-objects.mailTemplates[]` (`MailTemplateDto`: `name`, `alias`, `subject`, `description`, `active`, `htmlContent`, `cssContent`, `gjsData`, `placeholders`) | — |

- **Editor / settings panel:** No builder-side `editComponent` (`editComponent()` returns `null`), so there is no property dialog when placing the node. Instead the running page provides its own editing: **`MailTemplateEditorPanel`** — a form bound to `MailTemplateDto` with fields `name` (required + uniqueness), `alias` (required, `PatternValidator("^[a-z][a-zA-Z0-9]*$")` + uniqueness), `subject`, `description` (textarea), `active` (checkbox), `htmlContent`, `cssContent`, `gjsData` (textareas driven by the GrapesJS newsletter editor). Submit calls `mailTemplateService.save(...)`, then `sync(true)` broadcasts on key `"MailTemplateSynced"`. The right-nav **`MailTemplateSettingsPanel`** is a live list of all templates (up to 100) that lets you switch the selected template.
- **See also / source:** [15-pdf-and-mail.md](15-pdf-and-mail.md) Part 3 (full field table + real export) and [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) §7 (`mailTemplates[]` export schema) · `MailTemplatesPlugin.java`, `MailTemplateEditorPanel.java`, `MailTemplateSettingsPanel.java`, `MailTemplateDto.java`

### `ontology.viewer.plugin` — read-only interactive graph of the NCT platform ontology (vis-network)

- **Config slot:** none (`properties.model` type param is **vestigial** — never read; no `getJsonProperty(...)` call; only the base `className`/`styleName`/`tagProperties` exist and are empty) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — a technical/admin scaffold viewer; it takes no builder config, appears in no `.mrjun`, and a project builder never places or configures it.
- **Function:** Renders an interactive force/hierarchical graph of the platform ontology using the bundled `vis-network` library. a content re-init just adds a fresh `OntologyViewerPanel`; the panel loads a **fixed classpath resource** `/ontology/nct-platform-ontology.jsonld` and exposes it to JS (`getOntologyData`), plus a hardcoded `layoutType`/`showLabels`. Supports node filtering by type, search, zoom/pan, and a node-details panel (all client-side in `OntologyViewerPanel.js`).
- **Config JSON** (decoded):
```jsonc
— none — (no config blob; base properties.className / styleName / tagProperties are empty)
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config blob. The `OntologyModel` DTO (`ontologyFilePath`, `layoutType`, `showLabels`) is instantiated with `new OntologyModel()` inside the panel and **never populated from `properties`** — its values are effectively constants. | `ontologyFilePath="/ontology/nct-platform-ontology.jsonld"`, `layoutType="hierarchical"`, `showLabels=true` |
- **Editor / settings panel:** None. `editComponent()` returns `null`, so there is no builder settings UI and nothing is written back. Any behavior change requires editing the class/resource, not the `.mrjun`.
- **See also / source:** doc `14-plugin-catalog-all.md` (catalog stub — already notes "no config slot" + vestigial model) · `OntologyViewerPlugin.java` (`@PluginConfig(group="Technical")`, `extends NctBasePlugin<OntologyModel>`), `OntologyViewerPanel.java` (`renderHead` loads `lib/vis-network.min.js` + `lib/ontology-viewer.css`; the control supplies the ontology data, layout type and label flag to the JS), `OntologyModel.java`.

### `project.settings.plugin` — the project-level "Settings" panel (branding, import/export, layout, localization, integrations, appearance, AI)

- **Config slot:** `properties.*` (`stringValue` = **no config blob**) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — base-skeleton management-console node; the builder copies it as-is, it stores nothing to configure.
- **Function:** Renders the project Settings UI: a left nav of sections + a right content panel. It reads/writes **tenant-level** config through Spring services (`ProjectService`, `StateService`, `ExecutionPlatformConfig`, `UiConfig`, `AiConfig`), never through the content node. It is also the launch point for the `.mrjun` **project export** (Import/Export section → `AJAXDownloadBehaviour` → `projectService.exportProjectOrTemplate(tenant())`, downloaded via a hidden iframe to dodge the `window.location` redirect-flag bug). Selected tab is persisted per user/tenant via `StateService` (`STATE_KEY = "projectSettingsSelectedTab"`).
- **Config JSON** (decoded): — none — the node carries only the standard empty slots:
```jsonc
{ "pluginName": "project.settings.plugin",
  "name": "Project Settings",
  "properties": {
    "className":     { "propertyType": "STRING", "stringValue": "" },
    "styleName":     { "propertyType": "STRING", "stringValue": "" },
    "tagProperties": { "propertyType": "STRING", "stringValue": "" }
  } }
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config DTO. Declared `NctBasePlugin<Serializable>` (T is a placeholder, not a settings class); a content re-init never calls `getJsonProperty(...)`. All state is tenant-level via services, not JSON on the node. | — |

- **Editor / settings panel:** No property editor (`editComponent()` → `null`). The runtime panel is a role-gated left-nav + section switcher (`ProjectSettingsNavItem` enum → `createSectionPanel(...)`), 10 sections: `BRANDING`, `IMPORT_EXPORT`, `LAYOUT`, `TEMPLATE_MANAGEMENT`, `GENERAL`, `LOCALIZATION`, `INTEGRATIONS`, `ZOMBIE_INTEGRATIONS`, `APPEARANCE`, `AI`. Visibility (`buildVisibleNavItems()`): `BRANDING`/`LOCALIZATION`/`APPEARANCE` always; `IMPORT_EXPORT`+`LAYOUT` for ADMIN/NCT_AUTHOR; `TEMPLATE_MANAGEMENT` when template-admin **and** the tenant maps to a `ProjectTemplate`; `GENERAL` for template-admin; `INTEGRATIONS` when `executionPlatformConfig.isEnabled()`, with `ZOMBIE_INTEGRATIONS` additionally gated to template-admin; `AI` only when `aiConfig.isEnabled()`. (`isTemplateAdmin()` = user email equals `uiConfig.adminUserEmail` or `authorUserEmail`.) Each section panel writes tenant config through its own service; nothing is written back to the node.
- **See also / source:** [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) §8 (verified "stores nothing"; **stale** — its section list omits `ZOMBIE_INTEGRATIONS`, code now has 10), [14-plugin-catalog-all.md](14-plugin-catalog-all.md) (catalog stub) · `ProjectSettingsPlugin.java` (`plugin/dynamic/projectsettings/`, `@PluginConfig group="Technical"`), `ProjectSettingsNavItem.java`, `sections/*Section.java`.

### `project.template.management.plugin` — Organization-Manager admin console for CRUD-ing project starter templates (the `.mrjun` bundles new projects are seeded from)

- **Config slot:** `properties.<none>` (`stringValue` = **no config blob**) · **Editor:** no (`editComponent()` returns `null`) · **Hand-authored in .mrjun:** **no** — system/admin plugin. `@NctPlugin(projectTypes = ORGANIZATION_MANAGER)`, group `"Nct"`; it renders live DB rows from `ProjectTemplateService.templates()`, carries zero JSON config, and appears in no `.mrjun` template. Part of the base Organization-Manager console skeleton, not builder-authored.
- **Function:** Lists every registered project template (`ProjectTemplateEntity`) in a table (template name + comma-joined content names). Each row's **Edit** button opens a modal (`ProjectTemplateManagementContentsPanel`) where an org admin adds/renames/deletes named content entries and uploads a `.mrjun` file per entry; on Save it persists via `projectTemplateService.save(...)` and refreshes. These templates are what seed new projects, so this is platform-admin tooling, not page content.
- **Config JSON** (decoded):
```jsonc
— none —   // no getJsonProperty(...) call; data is loaded live from ProjectTemplateService (DB-backed ProjectTemplateEntity, jsonb), not from plugin properties
```
- **Fields:**

| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No config blob. Plugin extends raw `NctBasePlugin` (no config DTO `T`), never deserializes a settings slot. The node carries only the standard plugin identity (`pluginName`); optional generic `className`/`styleName` apply if placed, but no plugin-specific settings exist. | — |

  *Underlying (non-config) data model it edits, for reference only:* `ProjectTemplateEntity{ id:String, projectTemplate:ProjectTemplate(enum, provides name), contents:List<ProjectTemplateContent> }`; `ProjectTemplateContent{ name:String, content:byte[] (uploaded .mrjun bytes), roleGroups:List<RoleGroupDto> }`. Stored in DB (jsonb), not in the page JSON.
- **Editor / settings panel:** No builder editor (`editComponent()` returns `null`). Its runtime UI is the plugin body itself: a Bootstrap `table` (`ProjectTemplateManagementPlugin.html`) driven by a `ListView` over `projectTemplateService.templates()`. The per-row **Edit** modal is `ProjectTemplateManagementContentsPanel` — a form bound to `ProjectTemplateEntity` with an **Add** link (appends a blank `ProjectTemplateContent`), a `ListView` of content rows each exposing a `name` `TextField` (change-updating), a `FileUploadButtonPanel` (accepts `mrjun`, sets `content` bytes), and a **Delete** link; Save calls `projectTemplateService.save(entity)` then `plugin.refresh()` and closes the modal. Writes go to the DB, never to page/plugin properties.
- **See also / source:** `doc/builder/14-plugin-catalog-all.md` (catalog stub only, "scaffold, 0"), `doc/builder/01-content-model-and-pages.md` (listed among system plugins) · `ProjectTemplateManagementPlugin.java`, `ProjectTemplateManagementContentsPanel.java` (`nct-ui/.../plugin/admin/projecttemplate/`)

### `query.results.plugin` — display-only results table for the query editor/console (runs a `QueryDto` and paginates its rows)

- **Config slot:** `properties.model` (`stringValue` = *no config blob — nominally a `QueryDto`, but nothing is persisted for this node*) · **Editor:** no (`editComponent()` returns `null`; view-only) · **Hand-authored in .mrjun:** **no** — part of the base Reporting/queries console skeleton; the builder never places it or writes its JSON. The `QueryDto` it renders is injected **live at runtime** by sibling plugins, not stored.
- **Function:** Renders the paged result grid for a query. a content re-init reads one optional content property `max-height` and mounts `ResultsPanel(getModel(), height)`. The panel listens for richwicket events `queryNavbarRunAction` (fired by `QueryNavbar` in `admin.query.plugin`, `QueryNavbar.java`) and `runQueryWithConfiguration` (fired by `ChartQueryConfigurationPanel`); on each it re-hydrates its `QueryDto` model, resets `offset=0`, calls `QueryService.run(realm, client, dto)`, builds headers from `row[0].cols`, streams rows into a Wicket `DataView`, shows a "Found N results" count + a rows-per-page dropdown (`5/10/20/30/50/100`), and pages with `B4BootstrapAjaxPagingNavigator`. `json`/`jsonb` columns render via `PrityJsonLabel`. With a null model it shows an empty grid. Stores nothing in the export.
- **Config JSON** (decoded):
```jsonc
// — none — no config blob is written for this node.
// getModel() is null until a runtime event supplies a QueryDto.
// The only author-visible knob is a plain content property:
//   properties.max-height.stringValue = "500px"   // optional; pins container height (overflow:auto). Blank = CSS flex sizing.
```
- **Fields:** *(no persisted config fields; below are the `max-height` content property + the runtime `QueryDto` model fields the panel actually consumes — none are stored in this node)*

| Field | Type | Meaning | Default |
|---|---|---|---|
| `max-height` (content prop) | String | Inline `max-height` for the scroll container; blank ⇒ no inline style, CSS flex sizing applies | `""` |
| `query` (runtime model) | String | SQL/query text run by `QueryService` | — (injected) |
| `sourceIdentifier` (runtime) | String | Which data source to run against | — |
| `parameters` (runtime) | Map<String,Parameter{value}> | Named query parameters | `{}` |
| `itemsPerPage` (runtime) | Long | Page size; bound to the rows-per-page dropdown | `20` (panel falls back to `10`) |
| `offset` (runtime) | Long | Row offset; forced to `0` on (re)load and page-size change | `0` |
| `wrapInPaging` / `statementTimeoutSeconds` / `attributes` / `aggregations` (runtime) | Boolean / Integer / Map / QueryAggregationsDto | Passed through in the `QueryDto` to `QueryService.run` | — |
| `hidden` / `schedule` / `lastScheduledTime` (runtime) | Boolean / ScheduleDto / Instant | Query metadata carried by the DTO (not used by this display panel) | — |

- **Editor / settings panel:** None. `editComponent()` returns `null` and `pageGroups()` returns an empty list, so there is no edit dialog and no property tabs — it is a pure view component. It is configured only indirectly: sibling query-editor/chart-config plugins push a `QueryDto` into it via events, and the rows-per-page dropdown mutates the live model in place (resetting to page 1, then `refresh()` re-runs the query).
- **See also / source:** doc [12](12-queries-sources-schedulers-and-rest.md) (row: *Query results table (display-only)*) · `QueryResultsPlugin.java` · `ResultsPanel.java` · model `QueryDto.java` (`nct-transfer/.../dto/QueryDto.java`)

### `report.pdf.templates.plugin` — the "Pdf Templates" admin page: a CRUD list of PDF templates plus an in-page pdfme (`@pdfme/ui@6.1.2`) template designer.
- **Config slot:** `properties.*` (`stringValue` = **no config blob** — base `className`/`styleName`/`tagProperties` only; `initPluginContent` never calls `getJsonProperty`) · **Editor:** no builder editor (`editComponent()` returns `null`); the page has its own internal pdfme designer + a right-nav template-list panel · **Hand-authored in .mrjun:** **no** — this is a base-skeleton management console node; the *templates it manages* are authored (in `rep-objects.pdfTemplates[]` / nct-pdf), but the plugin **node itself carries no per-node config**.
- **Function:** Management scaffold for PDF templates. `PdfTemplatesPlugin` (`extends NctBaseModelObjectObjectSyncedPlugin<PdfTemplateDto>`) renders a `DataViewBasePanel` list of templates fetched from `PdfTemplateService.findAll(realm, client, filter)` (columns Name/Alias/Description/Active; row actions Delete, Edit). Clicking a row (or "Create new template") switches the same node into `editorMode` and shows `PdfTemplateEditorPanel` (pdfme, CDN `https://esm.sh/@pdfme/{ui,schemas,common}@6.1.2`). Data lives in the nct-pdf service DB (`pdf_templates`), not in the node. A `?template=<alias>` page param deep-links straight into a template's editor (`applyTemplateParam`, re-pushed to the URL via `history.pushState`).
- **Config JSON** (decoded):
```jsonc
// The node has NO model/settings blob. In the empty scaffold the node is only:
{
  "name": "Pdf Templates",
  "pluginName": "report.pdf.templates.plugin",
  "properties": { "className": {…}, "styleName": {…}, "tagProperties": {…} }
}
// — none — beyond the base slots. All state is server-side (PdfTemplateService → nct-pdf).
```
- **Fields:** the node exposes only the base `properties.*` slots; there is no config DTO on the node. (The *records* it edits use `PdfTemplateDto`, documented separately in doc 15.1.2.)

| Field | Type | Meaning | Default |
|---|---|---|---|
| `properties.className.stringValue` | String | Extra CSS class(es) on the plugin wrapper (base slot) | — |
| `properties.styleName.stringValue` | String | Inline style on the wrapper (base slot) | — |
| `properties.tagProperties.stringValue` | String | Extra HTML tag attributes (base slot) | — |
| *(no `model` / `settings` slot)* | — | Plugin reads its data from `PdfTemplateService`, not from node JSON | — |

- **Editor / settings panel:** No builder property panel (`editComponent` → `null`). Instead the page owns two internal UIs, neither hand-authored: (1) **`PdfTemplateEditorPanel`** — a form bound to `PdfTemplateDto` with `RequiredTextField name` (uniqueness-validated), `RequiredTextField alias` (`PatternValidator ^[a-z][a-zA-Z0-9]*$` + uniqueness), `TextArea description`, `CheckBox active`, `TextArea templateJson`, an AJAX image-upload behavior (→ `FileStorageService`, path `t/<realm>-<client>/pdf-templates/…`), and a "Standard Templates" loader (15 seed JSONs from nct-pdf). Save → `PdfTemplateService.save(...)` then `sync(true)`. (2) **`PdfTemplateSettingsPanel`** — a right-nav (`addRightSettingsNav`) list of all templates for quick switching, kept in sync via the `PdfTemplateSynced` event key (`getKey()`). Breadcrumb buttons: Save + Back-to-list in editor mode, "Create new template" (`active(true)`) in list mode.
- **See also / source:** [15-pdf-and-mail.md](15-pdf-and-mail.md) Part 1 (full `PdfTemplateDto` field table, `templateJson`/pdfme structure, seed catalog, Groovy render flow) · also cataloged in [14](14-plugin-catalog-all.md), [01](01-content-model-and-pages.md), [09](09-groovy-hints-and-live-context.md) · `PdfTemplatesPlugin.java`, `PdfTemplateEditorPanel.java`, `PdfTemplateSettingsPanel.java`, `PdfTemplateDto.java`.

### `user.profile.plugin` — self-service "My Profile" panel for the currently logged-in user

- **Config slot:** `properties` — **no config blob** (`stringValue` unused). The class extends the **raw** `NctBasePlugin` (no `<T>` config DTO), never calls `getJsonProperty(...)`, and `editComponent()` returns `null`. · **Editor:** none (view-only) · **Hand-authored in .mrjun:** **No** — it is a fixed **Technical** management-console scaffold that ships in the base REPORT / ORGANIZATION_MANAGER / PRODUCTS_MANAGER skeleton (`@NctPlugin(projectTypes = {ORGANIZATION_MANAGER, PRODUCTS_MANAGER, REPORT})`, `group = "Technical"`, `icon = "lnr-user"`). A builder never places or configures this node; it renders the same for every project.
- **Function:** Renders the current session user's own profile card and lets them self-edit it. a content re-init just does `addOrReplace(new UserProfilePanel("profilePanel"))`. The panel loads `UserDomain user()` and offers: (1) avatar management — change photo via CropperJS `ImageEditor`, capture from webcam via `CameraCapturePanel`, or remove photo (falls back to `/architectui-html-pro/images/avatars/userco.png`); (2) an inline a form bound to `UserProfileModel` editing `firstName`/`lastName` (required) with `email` shown read-only as a `Label`; (3) a **Change Password** modal (`ChangePasswordPanel`) that verifies the old password via `securityClient.login(...)` then patches the new one. Every save writes local `UserDomain` via `userService.save(...)` **and** syncs to the backend through `nctUserService.updateByBackend(...)`, using a *preserving update* (`buildPreservingUpdate` reloads the server `UserDto` first) so the backend's "wipe + reassign roleGroups" path can't strip the user's role groups on a profile-side patch.
- **Config JSON** (decoded):
```jsonc
— none — // system scaffold node; the .mrjun node carries only pluginName
         // (+ standard optional chrome: properties.className / styleName).
         // There is no plugin-specific settings object to author.
```
- **Fields:**
| Field | Type | Meaning | Default |
|---|---|---|---|
| — | — | No configuration fields — the plugin has no config DTO and no JSON blob; all data comes live from the session `UserDomain`. | — |

  *(For orientation, the internal edit models are UI-only, never serialized into the .mrjun: `UserProfileModel{firstName, lastName, email, imageUrl}` backs the inline form; `PasswordChangeModel{oldPassword, newPassword, retypePassword}` backs the password modal.)*
- **Editor / settings panel:** None. `editComponent()` returns `null`, so the builder shows no plugin editor and no settings tabs — there is nothing to configure. The only "UI that writes" is at **runtime** for the end user: the inline profile form (persists `firstName`/`lastName`), the photo editor/camera/remove actions (persist `imageUrl`), and the change-password modal (patches password) — all writing to the user's own record, not to plugin config.
- **See also / source:** doc **14** (`14-plugin-catalog-all.md`, catalog stub row: "Profile · the current user's profile") and doc **01** (listed under Admin/other scaffolds) — no field-level section previously, this entry fills that gap. · `UserProfilePlugin.java` (`plugin/profile/UserProfilePlugin.java`), `UserProfilePanel.java`, `UserProfileModel.java`, `PasswordChangeModel.java`, `ChangePasswordPanel.java`, `CameraCapturePanel.java`.
