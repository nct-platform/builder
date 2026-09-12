# 14 · Full plugin catalog — every `pluginName`, one by one

> 📐 **Field evidence — which plugins are actually used, and how often:** [09-studio-components.md](references/09-studio-components.md) · [10-visual-design.md](references/10-visual-design.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> 📕 **Field-level config reference:** [14a-plugin-config-reference.md](14a-plugin-config-reference.md) documents
> **63 of nct-ui's 64 plugin names** at chart-doc depth (`calendar.plugin` is covered in THIS doc only) — each one's
> **settings panel + editor + JSON config slot + field-by-field
> table**, source-grounded from the plugin class + editor + config DTO. Use THIS doc (14) as the catalog/overview;
> use **14a** when you need the exact JSON and what every field does to hand-author a node.

## What this is / When to use

This is the **index of every platform plugin**. Each content-tree node
(`branches.json[].rootContent … .children[]`) selects a plugin via the `pluginName` field
(see [01-content-model-and-pages.md](01-content-model-and-pages.md) — the node model). The plugin defines:

1. **how the node renders** (which Java class, from which module: `nct-ui` / `mrjun` / `richwicket`),
2. **where its config lives** — a slot in `properties`. The slot is **plugin-dependent**, not universal:
   - form controls → `properties.settings.stringValue` (JSON string),
   - table/chart/tree/process/dynamic-cruds/db/rule-script → `properties.model.stringValue` **or** a named property (`Javascript`, `html`, `tabModel`, `helpSettings`, …),
   - "raw" HTML plugin → `properties.html.stringValue`,
   - most admin plugins → an **empty** config (this is a scaffold, there is no config).

Use this file to answer: **"which `pluginName` do I need, and what is its node shape?"**
For plugins documented in detail in other docs, this file gives one line + a link.

> **Where the "Real node" examples come from.** Nodes tagged (`erp`) below are decoded from the sample bundle
> decoded from a fictional ERP demo bundle that **no longer ships** ([23](23-distribution-and-known-gaps.md)):
> it failed `validate`, so it was withdrawn rather than left in place as a model. The shapes are unchanged.
> To see the same slots populated in something you can actually unpack, use
> `initialtemplates/empty.mrjun` (`mrjun.py unpack initialtemplates/empty.mrjun /tmp/base` — two positional arguments, no
> flag) and you can verify every one of them: `mrjun.py find --plugin <pluginName> --project /tmp/erp` prints each
> match's `identifier=` (this doc never prints them), then `mrjun.py show node <identifier> --project /tmp/erp`
> dumps the node. They are examples of a *shape*, never a statement about how your project must be organised.

> **Convention for the source of `pluginName`.** Each plugin class declares the string once, in its
> `@PluginConfig(pluginName = "…")` annotation. Two classes — `SiteMapPage` and `SiteMapPageRaven` — share the one
> name `siteMapPage`, so **nct-ui's 64 distinct plugin names** — the ones you author — come from 65 annotated
> classes (the CMS and admin layers under it declare more — catalogued here only so you recognise them); add the 2 base
> plugins that also appear in tenant exports (`html.plugin`, `parsis.plugin`) → the **66 = 64 + 2** in the README.
> The generic content plugins (`nct.html/label/image/…`, `parsis.plugin`, `html.plugin`, `grid.plugin`,
> `tabs.plugin`, …) come from the CMS layer; the business plugins come from the application layer. You never write
> these names by hand except in `properties.pluginName` — copy them from the catalog below.

---

## Real inventory: which `pluginName` values appear in a project export

The list below is the set of `pluginName` values that actually occur inside project exports, with how often you
should expect to meet each. Run the histogram on your own bundle at any time:
`jq '.. | objects | select(has("pluginName")) | .pluginName' branches.json | sort | uniq -c`.
The rule this encodes: if a `pluginName` is in this table — it is authored into the project; if it is not — it is
platform/admin-level and never written into a project export.

| `pluginName` | typical count in a project | config slot | documented in |
|---|---|---|---|
| `siteMapPage` | 1 per page | top-level props | below + [01](01-content-model-and-pages.md) |
| `nct.parsis.plugin` | 2–3 per page (content slots) | — (drop container) | below |
| `parsis.plugin` | 1 per page (the page's top-level slot) | — (drop container) | below |
| `html.plugin` | 1 per page (site scaffold) | `properties.html` | below (site scaffold) |
| `nct.html.plugin` | as many as you author — every layout row / component | `properties.html` | below (**"how html is created"**) |
| `nct.image.plugin` | 1 per page (the shared logo stub) + your own | named props | below |
| `nct.label.plugin` | as many as you author | named props | below |
| `nct.label.link.plugin` | rare | named props | below |
| `nct.tab.plugin` | 1 per tabbed page | `properties.tabModel` | below |
| `nct.help.plugin` | rare | `properties.helpSettings` | below + [03](03-generate-fields-from-crud.md) |
| `chart.js.plugin` | **0 in the current baseline** — every chart is yours to author | `properties.Javascript` | [22](22-charts-params-and-filters.md) |
| `global.replacement.plugin` | **0 in the current baseline**; 1 per filter bar | — (no content blob; the editor edits query parameters) | [22](22-charts-params-and-filters.md) |
| `action.button.plugin` | 1 per standalone button (rare) | `properties.settings` | below |
| `crud.table.plugin` | 1 per list page (0 in the baseline) | `properties.model` | [04](04-crud-table-plugin.md) |
| `crud.tree.plugin` | 1 per hierarchy page (rare) | `properties.model` | [05](05-crud-tree-and-process-table.md) |
| `calendar.plugin` | 1 per scheduling/booking page (0 in the baseline) | `properties.model` | see the note below — not yet covered in depth |
| `process.table.pluin` *(yes, with the typo)* | 1–2 (console + your process lists) | `properties.model` | [05](05-crud-tree-and-process-table.md) |
| `dynaform.form.plugin` | 1 per form | `properties.formModeIdentifier` (STRING → FormDto rep-object; no settings/model blob) | [02](02-form-controls-reference.md),[06](06-form-groups-and-mapping.md) |
| `dynaform.form.text.field.plugin` | 1 per text field — the most numerous control | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.textarea.field.plugin` | 1 per multi-line field | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.rimm.drop.down.field.plugin` | 1 per dropdown | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.rimm.autocomplete.field.plugin` | 1 per autocomplete (rare) | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.datepicker.field.plugin` | 1 per date field | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.tree.picker.plugin` | 1 per hierarchy picker (rare) | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.list.field.plugin` | 1 per sub-grid | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.list.item.plugin` | 1 per sub-grid row form | — (form container; no config blob) | [02](02-form-controls-reference.md) |
| `dynaform.form.file.upload.field.plugin` | 1 per upload field | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.comments.field.plugin` | 1 per comments field | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.form.gantt.chart.plugin` | 0 unless you author one | `properties.settings` | [02](02-form-controls-reference.md) |
| `dynaform.filter.form.plugin` | 1 per standalone filter panel | `properties.filterFormModel` (`FilterFormDto`) | [04](04-crud-table-plugin.md#standalone-filter-form-filter-panel-above-the-table) |
| `dynaform.filter.submit.button.plugin` | 1 per filter panel | `properties.settings` (`{"buttonName":…}`) | [04](04-crud-table-plugin.md#standalone-filter-form-filter-panel-above-the-table) |
| `dynaform.form.groups.landingplugin` | 1 per form-group landing page | — (no settings blob; FormGroupDto via the `?group=<identifier>` URL parameter) | [06](06-form-groups-and-mapping.md) |
| `dynaform.form.groups.plugin` | 1 (console skeleton) | admin scaffold | [06](06-form-groups-and-mapping.md) |
| `dynaform.context.list.plugin` | 1 (console skeleton) | admin scaffold | [08](08-groovy-rules-and-context.md) |
| `bpmn2modeler.plugin` | 1 (console skeleton) | admin scaffold | [07](07-workflows-and-tasks.md) |
| `workflows.plugin` | 1 (console skeleton) | admin scaffold | [07](07-workflows-and-tasks.md) |
| `processes.plugin` ⚠️ *(dead — no class)* | 1 (console skeleton) | ⚠️ none → `mrjun.plugin.not.found` | [07](07-workflows-and-tasks.md) |
| `processes.selectedplugin` | 1 (console skeleton) | admin scaffold | [07](07-workflows-and-tasks.md) |
| `executor.rule.list.plugin` | 1 (console skeleton) | `ContentChooserPanelModel` `{editorPageContentIdentifier}` (landing = the `executor.rule.script.plugin` editor page) | [08](08-groovy-rules-and-context.md) |
| `executor.rule.script.plugin` | 1 (console skeleton) | — (no model/settings blob; RuleDto is a rep-object, `?rule=<identifier>`) | [08](08-groovy-rules-and-context.md) |
| `database.management.plugin` | 1 (console skeleton) | `properties.model` | [10](10-database-management.md) |
| `dynamic.cruds.plugin` | 1 (console skeleton; absent in a truncated one) | `properties.model` | [11](11-business-logic-dynamic-crud.md) |
| `admin.queries.plugin` | 1 (console skeleton) | admin scaffold | [12](12-queries-sources-schedulers-and-rest.md) |
| `admin.query.plugin` | 1 (console skeleton) | admin scaffold | [12](12-queries-sources-schedulers-and-rest.md) |
| `query.results.plugin` | 1 (console skeleton) | admin scaffold | [12](12-queries-sources-schedulers-and-rest.md) |
| `admin.sources.plugin` | 1 (console skeleton) | admin scaffold | [12](12-queries-sources-schedulers-and-rest.md) |
| `admin.schedulers.plugin` | 1 (console skeleton) | admin scaffold | [12](12-queries-sources-schedulers-and-rest.md) |
| `admin.user.management.plugin` | 1 (console skeleton) | admin scaffold | below |
| `admin.rolegroup.management.plugin` | 1 (console skeleton) | admin scaffold | below + [12](12-queries-sources-schedulers-and-rest.md) |
| `audit.log.list.plugin` | 1 (console skeleton) | admin scaffold | below |
| `ontology.viewer.plugin` | **0 in the current baseline** (the `Ontology` demo page is gone) | admin scaffold | below |
| `user.profile.plugin` | 1 (console skeleton) | admin scaffold | below |
| `project.settings.plugin` | 1 (console skeleton) | admin scaffold | below + [12](12-queries-sources-schedulers-and-rest.md) |
| `messaging.mail.templates.plugin` | 1 (console skeleton) | admin scaffold | [12](12-queries-sources-schedulers-and-rest.md),[15](15-pdf-and-mail.md) |
| `report.pdf.templates.plugin` | 1 (console skeleton; absent in a truncated one) | admin scaffold | [15](15-pdf-and-mail.md) |
| `pdf.report.plugin` ⚠️ *(dead — no class)* | **0 in the current baseline** (the `reports` demo page is gone) | ⚠️ none → `mrjun.plugin.not.found` | [15](15-pdf-and-mail.md),[01](01-content-model-and-pages.md) |
| `pdf.report.page.plugin` ⚠️ *(dead — no class)* | **0 in the current baseline** | ⚠️ none → `mrjun.plugin.not.found` | [15](15-pdf-and-mail.md),[01](01-content-model-and-pages.md) |
| `site.header.plugin` | 1 per page (site chrome) | — (site chrome) | below |
| `site.footer.plugin` | 1 per page (site chrome) | — (site chrome) | below |
| `site.kicker.plugin` | 1 per page (site chrome) | `properties.modelGroups` when `id=left-nav` (quick-links tree); else — (site chrome) | [17](17-left-nav-quick-links.md), below |
| `site.right.kicker.plugin` | 1 per page (site chrome) | `properties.showFromNonAuthMode` (BOOLEAN, default true → set `false` to hide the right drawer for non-authoring visitors) | below |
| `site.breadcrumb.plugin` | 1 per page (site chrome) | — (site chrome) | below |

> **`calendar.plugin` — the one authorable plugin these docs do not yet cover field-by-field.** Config slot
> `properties.model` (`CalendarPluginModel`). It binds to ONE CRUD (`contextIdentifier` + `crudAlias`) and
> fetches through an EXECUTION find rule (`findRuleIdentifier`, or `findMethodName` on the CRUD); the visible
> date window arrives in the rule's `attrs` as `rangeStart`/`rangeEnd`. Rows become events through a field
> mapping (`titleField`, `startField`, `endField`, `allDayField`, `colorField`, `locationField`,
> `descriptionField`), and `createActions`/`editActions` are the same `CrudTableActionsDto` shape as on the
> table ([04](04-crud-table-plugin.md)). Presentation: `initialView`, `firstDay`, `slotMinTime`/`slotMaxTime`,
> `showWeekends`. If a PRD asks for appointments/bookings/shifts, evaluate this before hand-building a table or
> an HTML component; check the field names against your platform build before you rely on them.

**Plugins that exist in the `nct-ui`/`mrjun` code but do NOT appear in any project export**
(these are platform/admin-application nodes; you do **not** author them by hand):
`admin.organizations.plugin`, `admin.projects.plugin`, `admin.integrations.list.plugin`,
`discovery.plugin`, `project.template.management.plugin`, `grid.plugin`, `html.localized.plugin`,
`nct.link.plugin`, `admin.dashboard.*` (mrjun-admin),
`admin.createsite.*` (mrjun-admin), `mrjun.plugin.not.found`, `mrjun.empty.plugin`. Check any of them the same
way: `jq '[.. | objects | select(.pluginName=="admin.projects.plugin")] | length'` → `0`.

Also **`dynaform.form.gantt.chart.plugin`** is easy to mistake for one of the above, because most projects contain
none — but unlike them it is a **real, hand-authorable form control** (full detail in
[02](02-form-controls-reference.md)); it is simply rarely needed, not platform-level.

---

# Group 1 · Content / layout plugins (mrjun-side)

These are the page's "building bricks". Key fact: **a `siteMapPage` page does not contain form
controls / crud tables directly** — it contains **a single `html.plugin`** (the site-layout scaffold),
inside whose HTML the `site.*` plugins are inserted via the `<plugin>` tag, along with **a single `nct.parsis.plugin`** —
a container slot into which authors "drop" business plugins (crud tables, forms, charts).

## 1.1 · `nct.html.plugin` — **how HTML is created** (raw HTML with embedded `<plugin>`)

| | |
|---|---|
| Class | `NctHtmlPlugin extends HtmlPlugin` (mrjun) |
| Where | `NctHtmlPlugin` (its `@PluginConfig` annotation carries the pluginName); base classes `HtmlPlugin` → `AbstractHtmlPlugin` in the CMS library |
| Config slot | `properties.html.stringValue` (type `STRING`) |
| Extra props | `editorWidth` (default `"100%"`), `editorHeight` (default `"700px"`), `reuseItems` (bool, default `false`) — from `HtmlPropertiesBuilder`; plus `className`, `styleName`, `tagProperties` from the base builder. **Not `isParsis`** — that is a marker set on `nct.parsis.plugin` nodes (§1.2), not an html-plugin prop. |
| UI group | `Common` |

> **Component Studio (2026-07-28):** the SAME plugin can additionally carry a **JS-library + isolated-script + per-theme-CSS** project — including **calling the project's rules and business logic from JS** (`ctx.callRule` / `ctx.callBl`) — via a `properties.studioModel` JSON property (+ vendored files under `tenant-files/studio/…`). It is purely additive (no `studioModel` ⇒ classic raw HTML, exactly as below). Full schema, runtime API, and `.mrjun` recipe → **[24-html-component-studio.md](24-html-component-studio.md)** (`mrjun.py node set-studio` / `asset add`).
>
> **`<include src="…">` (studio components only).** One document can pull in another document of the **same**
> component: `<include src="detail.html"/>` is substituted **server side, before parsing**, so a `<plugin>` tag
> written in the included document becomes a real child node exactly as if it stood here, to any nesting depth of
> includes. `<include src="boot.js"/>` instead declares which author scripts run, and at runtime
> `await ctx.include('detail.html', '#host')` renders a document into an element the same way. The `src` always
> carries the extension.
>
> The five docs that together cover everything you can do with this plugin:
> **[24](24-html-component-studio.md)** schema + runtime API + rule/BL calls + **breadcrumb actions** (`ctx.breadcrumb`) + lifecycle ·
> **[24a](24a-theming-and-dark-mode.md)** ⚠️ **read before writing any CSS** — the five skins, the token contract, `css.byTheme` ·
> **[24b](24b-html-composition-and-plugin-tags.md)** the `<plugin>` grammar below, in full, + how to reuse a whole component ·
> **[24c](24c-html-data-tables-and-paging.md)** server-paged tables inside a component ·
> **[24d](24d-html-component-structure.md)** splitting one component into documents and scripts — `<include>`, `ctx.include`, when to split.

**This is the answer to "how html is created".** `nct.html.plugin` is an editable block of raw HTML.
Inside the HTML you can insert **`<plugin>` tags**, and each such tag is parsed (Jsoup) into a **real
child content node**. The parsing mechanism is `AbstractHtmlPlugin`:

- the body is parsed as `Jsoup.parse("<div>" + htmlString + "</div>")`;
- `allElements.select("plugin")` — all `<plugin>` tags;
- only the **top-level** `<plugin>` tags are taken (not those nested inside another `<plugin>`);
- the attributes `id`, `name` (= the child's `pluginName`), `vp` (virtual-plugin id) are read;
- `plugin.select(":root > property,:root > prop")` — child `<property>` / `<prop>` → the child's properties;
- `plugin.select(":root > behavior")` — child `<behavior>` → behaviour nodes;
- each property tag contributes `name` + `type` (`PropertyType.of(...)`, default `STRING`) + `value`;
- by `(id, name)` a **child content node** is created or found under this html plugin; if `vp` is set,
  the virtualPlugin is used instead.

**Real example** (from the withdrawn ERP demo's `branches.json`, an `nct.html.plugin` node, `properties.html.stringValue` — a
two-column layout with two parsis slots):

```json
"html": {
  "key": "html", "propertyType": "STRING", "required": false, "hidden": false,
  "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
  "stringValue": "<div style=\"display: flex;\"> \r\n        <div style=\"width: 300px;\">\r\n            <plugin id=\"left\" name=\"nct.parsis.plugin\"/>\r\n        </div>\r\n        <div style=\"flex-grow: 1;\">\r\n            <plugin id=\"right\" name=\"nct.parsis.plugin\"/>\r\n        </div>\r\n    </div>",
  "localizedStringValue": {}, "arguments": {}
}
```

Decoded `html`:

```html
<div style="display: flex;">
    <div style="width: 300px;">
        <plugin id="left" name="nct.parsis.plugin"/>
    </div>
    <div style="flex-grow: 1;">
        <plugin id="right" name="nct.parsis.plugin"/>
    </div>
</div>
```

The property syntax inside `<plugin>` (real example from the site-layout, see `html.plugin` below):

```html
<plugin name="nct.image.plugin" id="logo-plugin">
    <prop name="tooltip", value="Logo", type="STRING"/>
    <prop name="width", value="90", type="INTEGER"/>
    <prop name="url", value="abs(/architectui-html-pro/images/logo-inverse.png)", type="STRING"/>
</plugin>
<plugin id="header" name="site.header.plugin">
    <property name="className" value="app-header__content"></property>
</plugin>
```

> ⚠️ Authors write both `<prop name="x", value="y", type="STRING"/>` (with commas) and
> `<property name="x" value="y"/>` (without commas). Jsoup parses both (the commas end up in the attribute
> names and are ignored), but **prefer the clean** `<prop name="x" value="y" type="STRING"/>`.

### How to create from scratch
1. Create a content node `pluginName:"nct.html.plugin"`, fresh `identifier`/`uniqueIdentifier`,
   `id=null`, `order`=the next sibling, `branchId` from the parent (see [01](01-content-model-and-pages.md)).
2. In `properties.html.stringValue` put the HTML. To embed a business plugin, insert
   `<plugin id="<slotId>" name="nct.parsis.plugin"/>` (a slot) **or** directly
   `<plugin id="<id>" name="crud.table.plugin"/>` (a hard insert).
3. For each top-level `<plugin id="x" name="<pluginName>">` add a **child content node** to that html node's
   `children[]` whose **`identifier` == `x` (the tag `id`)** and `pluginName` == the tag `name`, and put that
   child's config (settings/model/Javascript/text) on it.
   > ⛔ **This child is the ONE you do NOT give a fresh `identifier`** (contrast step 1). The html plugin links
   > tag→child by `child.identifier == <plugin id>` (`AbstractHtmlPlugin.java` reads the id → passes it
   > to `getOrCreateChildContent`, which matches `Objects.equals(child.getIdentifier(), id)` at `PluginUtils`
   >). If the child identifier does not equal the tag id, the platform auto-creates a **blank** child with
   > `identifier`=id at render and your authored plugin is orphaned → **the slot renders EMPTY while import stays
   > clean**. Set `name`=id too (the platform does `setName(identifier)`). For a parsis-slot (`<plugin id="x"
   > name="nct.parsis.plugin"/>`): the child `nct.parsis.plugin` must have `identifier`==x, and the business
   > plugin (crud.table/chart/form) goes as a child **under** that identifier-matched parsis. Live-render and
   > confirm the slot is populated — an empty slot with a clean import means an identifier mismatch (same rule as
   > §2.4's grid cells: child `identifier` == that `<plugin id>`).
4. The remaining `properties.*` (className/styleName/…) — as in the example (empty strings are allowed).

## 1.2 · `parsis.plugin` / `nct.parsis.plugin` — drop containers (slots)

| | |
|---|---|
| Classes | `ParsisPlugin` (CMS library, name = `Constants.Plugins.PARSIS_PLUGIN = "parsis.plugin"`); `NctParsisPlugin extends ParsisPlugin` (platform UI, name `nct.parsis.plugin`) |
| Config slot | — (no JSON config; the config = **children**) |
| Props | **Shared by BOTH `parsis.plugin` and `nct.parsis.plugin`** (from `ParsisPluginDefPropBuilder`): `minHeight`, `style`, `emptyPlaceholder`, `reuseItems`; plus `isParsis:true`, `className`, `styleName`, `tagProperties`. `NctParsisPlugin` adds only **behavior** (role-aware `canEditParsis`, drag sources, move-confirm) + `hideInKicker=true` — **no** new config props (`emptyPlaceholder`/`minHeight`/`style` are NOT nct.parsis-only). |

Parsis is a **container slot**: it shows nothing itself, but renders its `children[]` (each one a plugin).
In authoring, plugins are "dropped" into it via drag-and-drop. `nct.parsis.plugin` is the nct-ui subclass of
`parsis.plugin`; it declares the **same** `defaultPropertiesBuilder`, so the config surface is **identical** — it adds
only authoring behaviour (`canEditParsis` takes the `ADMIN`/`NCT_AUTHOR` role into account, drag sources,
move-confirm, `NctParsisPlugin.java`) and `hideInKicker=true`. **`properties.isParsis` = `true`** distinguishes a
parsis from a plain html.

Real node (`erp`, `nct.parsis.plugin`, one child):

```json
{ "pluginName": "nct.parsis.plugin", "name": "parsis", "children": [ /* business plugin */ ],
  "properties": {
    "isParsis":   { "key":"isParsis", "propertyType":"BOOLEAN", "booleanValue": true },
    "className":  { "key":"className", "propertyType":"STRING", "stringValue": "" },
    "emptyPlaceholder": { "key":"emptyPlaceholder", "propertyType":"STRING", "stringValue": "" },
    "minHeight":  { "key":"minHeight", "propertyType":"INTEGER" },
    "reuseItems": { "key":"reuseItems", "propertyType":"BOOLEAN", "booleanValue": false },
    "styleName":  { "key":"styleName", "propertyType":"STRING", "stringValue": "" },
    "style":      { "key":"style", "propertyType":"STRING" },
    "tagProperties": { "key":"tagProperties", "propertyType":"STRING", "stringValue": "" }
  } }
```

### How to create from scratch
Usually **not created by hand on its own** — a parsis slot appears from `<plugin name="nct.parsis.plugin"/>`
in the site-layout HTML (see `page add` in the tooling). To **add a business plugin to a page**, find an
existing `nct.parsis.plugin` on the page and add the plugin to its `children[]` (this is exactly what
`mrjun.py node add --parent <page>` does: "if parent is a page it drops into the page's content container").

## 1.3 · `html.plugin` — site-layout scaffold (mrjun raw HTML)

| | |
|---|---|
| Class | `HtmlPlugin` (CMS library, name `Constants.Plugins.HTML_PLUGIN = "html.plugin"`) |
| Config slot | `properties.html.stringValue` |
| Role | **the top-level layout of every page**: header/sidebar/footer/parsis slot |

The same mechanism as `nct.html.plugin` (the shared `AbstractHtmlPlugin`), but this is the **base mrjun class**.
In practice `html.plugin` is precisely the **page's layout skeleton** (one per `siteMapPage`), inside
which `site.header.plugin`, `site.kicker.plugin`, `site.breadcrumb.plugin`,
`site.footer.plugin`, `site.right.kicker.plugin` and `nct.parsis.plugin` (the content slot) are embedded.

Real `properties.html.stringValue` (`erp`, an `html.plugin` layout node, decoded, abridged):

```html
<div class="app-container app-theme-white body-tabs-shadow fixed-header fixed-sidebar">
    <div class="app-header header-shadow">
        <div class="app-header__logo">
            <a href="/">
                <plugin name="nct.image.plugin" id="logo-plugin">
                    <prop name="tooltip", value="Logo", type="STRING"/>
                    <prop name="width", value="90", type="INTEGER"/>
                    <prop name="height", value="60", type="INTEGER"/>
                    <prop name="url", value="abs(/architectui-html-pro/images/logo-inverse.png)", type="STRING"/>
                </plugin>
            </a>
            ...
        </div>
        <plugin id="header" name="site.header.plugin">
            <property name="className" value="app-header__content"></property>
        </plugin>
    </div>
    <div class="app-main">
        <plugin id="left-nav" name="site.kicker.plugin"></plugin>
        <div class="app-main__outer">
            <div class="app-main__inner">
                <plugin id="breadcrumb" name="site.breadcrumb.plugin"></plugin>
                <plugin id="parsis" name="nct.parsis.plugin"></plugin>
            </div>
            <plugin id="footer" name="site.footer.plugin"></plugin>
        </div>
    </div>
</div>
<plugin id="right-kicker" name="site.right.kicker.plugin">
    <property name="className" value="app-drawer-wrapper"></property>
</plugin>
```

### How to create from scratch
**Not written by hand.** The `html.plugin` layout is cloned from the page template when a `siteMapPage` is created
(tooling: `mrjun.py page add … --layout <vp>` "clones the standard layout scaffold, empties the content
container"). You only change the `nct.parsis.plugin` slot inside (into which you place business plugins).

## 1.4 · `nct.label.plugin` — static text/caption

| | |
|---|---|
| Class | `NctLabelPlugin` (`nct-ui/.../plugin/common/NctLabelPlugin.java`, name) |
| Slot | named props: `text` (LOCALIZED), `tagName`, `className`, `styleName`, `tagProperties` |

`text` is a localized string (`localizedStringValue`) **emitted as raw HTML** (unescaped — you may embed inline
markup). `tagName` is the wrapper HTML tag, from a fixed dropdown set
**`[h1,h2,h3,h4,h5,h6,p,span,i,label,small]`** (`LocalizedHeaderPropertiesBuilder.java`) — **`div` is NOT an
allowed value** (only if hand-injected). **The default `tagName` is `p`**, so a label with no `tagName` renders
`<p>`, not `<label>` — set `tagName:"label"` for a form caption. It is often generated as a form-field caption
("Generate fields", see [03](03-generate-fields-from-crud.md)) — there `className:"form-label"`, `tagName:"label"`.

Real node (`erp`, a generated field caption):

```json
{ "pluginName": "nct.label.plugin", "name": "lbl_gen_slot_4143cc62_2_0",
  "properties": {
    "text":      { "key":"text", "propertyType":"LOCALIZED_STRING",
                   "localizedStringValue": { "en_US":"Description", "ru_RU":"Описание" } },
    "tagName":   { "key":"tagName", "propertyType":"STRING", "stringValue":"label" },
    "className": { "key":"className", "propertyType":"STRING", "stringValue":"form-label" },
    "styleName": { "key":"styleName", "propertyType":"STRING", "stringValue":"" },
    "tagProperties": { "key":"tagProperties", "propertyType":"STRING", "stringValue":"" }
  } }
```

### How to create from scratch
Node `pluginName:"nct.label.plugin"`; fill in `text.localizedStringValue` (one pair per project locale,
keys like `en_US`/`ru_RU`), `tagName` (one of `label`/`span`/`p`/`h1`…`h6`/`i`/`small`; **default `p`**), and
optionally `className`.

## 1.5 · `nct.image.plugin` — image

| | |
|---|---|
| Class | `NctImagePlugin extends ImagePlugin` (`nct-ui/.../plugin/common/NctImagePlugin.java`, name); base mrjun `ImagePlugin` (`Constants.Plugins.IMAGE_PLUGIN = "image.plugin"`) |
| Slot | named props: `url`, `description`, `tooltip`, `width` (INTEGER, **default 400**), `height` (INTEGER, **default 250**) — ⚠️ **neither reaches the rendered `<img>`**, see below — `className`, `styleName`, `tagProperties` |

`url` supports the `abs(...)` macro (absolute path to a template resource). **In an export the `url` is stored
TENANT-STRIPPED** (`TenantDomain.stripTenantPrefix`, called from `ImagePlugin` on save, re-prefixed with the
importing tenant via `tenant().resolveImagePath` on render) — which is why an export's image `url` carries no realm/tenant prefix and
ports cleanly; the actual image file lives in **nct-file-storage** (`tenant-files/`), so a ported project needs the
file present. `width`/`height` (INTEGER, defaults 400 / 250) are **NOT applied to the rendered `<img>`** — those lines
are commented out in `ImagePlugin.initPluginContent`. They are read only to size the `getImageFakeFile_{w}_{h}`
placeholder shown when `url` is unset, and to seed the gallery editor's dimension config. **To size an image use
`className`/`styleName` + CSS**, not these props — which is why the `width=90` on the logo in the §1.1 / §1.3 layout
examples (verbatim from the sample export) has no rendering effect.
Real node (`erp`, logo):

```json
{ "pluginName": "nct.image.plugin", "name": "logo-plugin",
  "properties": {
    "url":         { "key":"url", "propertyType":"STRING",
                     "stringValue":"abs(/architectui-html-pro/images/logo-inverse.png)" },
    "description": { "key":"description", "propertyType":"STRING", "stringValue":"Logo" },
    "tooltip":     { "key":"tooltip", "propertyType":"STRING", "stringValue":"Logo" },
    "width":       { "key":"width", "propertyType":"INTEGER" },
    "height":      { "key":"height", "propertyType":"INTEGER" },
    "className":   { "key":"className", "propertyType":"STRING", "stringValue":"" }
  } }
```

## 1.6 · `nct.link.plugin` — link · `nct.label.link.plugin` — link with a caption

| | |
|---|---|
| Classes | `NctLinkPlugin` (`nct-ui/.../plugin/common/NctLinkPlugin.java`, name `nct.link.plugin`); `NctLabeledLinkPlugin` (`nct-ui/.../plugin/common/NctLabeledLinkPlugin.java`, name `nct.label.link.plugin`) |
| Slot | named props |

`nct.link.plugin` **does not appear in project exports** — in practice its labeled variant is used, and even that
one is rare. A node looks like this:

```json
{ "pluginName": "nct.label.link.plugin", "name": "Link Label",
  "properties": {
    "label":   { "key":"label", "propertyType":"LOCALIZED_STRING",
                 "localizedStringValue": { "en_US":"sdfsdfgsdfg", "ru_RU":"sdfsdfgsdfg", "hy_AM":"սդֆսդֆգսդֆգ" } },
    "link":    { "key":"link", "propertyType":"LOCALIZED_STRING", "localizedStringValue": {} },
    "params":  { "key":"params", "propertyType":"STRING", "stringValue":"" },
    "internal":{ "key":"internal", "propertyType":"BOOLEAN", "booleanValue": true },
    "identifier": { "key":"identifier", "propertyType":"STRING", "stringValue":"641b5dde-96b8-4cd3-b37a-42478cf521ec" },
    "style":   { "key":"style", "propertyType":"STRING", "stringValue":"" },
    "className": { "key":"className", "propertyType":"STRING", "stringValue":"" }
  } }
```

Fields: `label` (LOCALIZED caption), `link` (LOCALIZED_STRING — URL/path per locale, not a plain STRING),
`params` (query parameters), `internal` (bool —
an internal link), `identifier` (the **destination** content node's `identifier` — the node this link navigates to,
resolved via `contentService.findOneByIdentifier`, `LinkPlugin.java`; **NOT** the link node's own uuid, and
honoured **only** when `internal:true`. For an external link set `internal:false` and put the URL in the `link`
LOCALIZED_STRING; `identifier` is then ignored). The mrjun base is `LinkPlugin`
(`Constants.Plugins.LINK_PLUGIN = "link.plugin"`) and `LocalizedLinkLabelPlugin`
(`localized.link.label.plugin`).

## 1.7 · `nct.help.plugin` — help icon with a message

| | |
|---|---|
| Class | `HelpPlugin` (`nct-ui/.../plugin/common/help/HelpPlugin.java`, name) |
| Slot | `properties.helpSettings.stringValue` (JSON) |

Real node (`erp`):

```json
{ "pluginName": "nct.help.plugin", "name": "help_gen_slot_b8035f65_0_2",
  "properties": {
    "helpSettings": { "key":"helpSettings", "propertyType":"STRING",
      "stringValue": "{\"alwaysVisible\":true,\"showMessageOn\":\"CLICK\",\"needToBeSaved\":false,\"localizedMap\":{\"message\":{\"en_US\":\"SHARE, not %: 0.15 = 15%; precision 5, scale 4\",\"ru_RU\":\"ДОЛЯ, а не %: 0,15 = 15%; точность 5, масштаб 4\",\"hy_AM\":\"ԲԱԺԻՆ, ...\"}}}" } } }
```

`helpSettings` (decoded): `alwaysVisible` (bool), `showMessageOn` (`CLICK`/`HOVER`),
`localizedMap.message.<locale>` (localized text). Programmatic creation is already described in
[03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) (the Info column): the help plugin is placed
to the right of the field caption — `HelpPluginSettings.setLocalizedProperty("message", map)` + `setJsonProperty("helpSettings")`.

## 1.8 · `nct.tab.plugin` / `tabs.plugin` — tabs

| | |
|---|---|
| Classes | `TabPlugin` (platform UI, name `nct.tab.plugin`); `TabsPlugin` (CMS library, name `tabs.plugin`) |
| Slot | `properties.tabModel.stringValue` (JSON) |

`nct.tab.plugin` is the nct-ui tab set; `tabs.plugin` is the base mrjun one (in real projects only
`nct.tab.plugin` appears). **Each tab = a named child slot**: the tab's content is a child parsis.
Real `tabModel` (`erp`):

```json
"tabModel": { "key":"tabModel", "propertyType":"STRING", "stringValue":
"{\"items\":[
  {\"id\":\"5b7fd1bc-136f-4f70-9388-578029065e9a\",\"name\":\"Stock\",\"order\":0,\"iconClass\":\"\",\"needToBeSaved\":false,\"localizedMap\":{\"name\":{\"en_US\":\"Stock\",\"ru_RU\":\"Остатки\",\"hy_AM\":\"Պահեստի Մնացորդ\"}}},
  {\"id\":\"7af19caa-1eb9-4372-ad19-bce366f1eb67\",\"name\":\"Stock Movement\",\"order\":1,\"iconClass\":\"\",\"localizedMap\":{\"name\":{\"en_US\":\"Stock Movement\",\"ru_RU\":\"Движение остатков\"}}},
  {\"id\":\"22ae6ae8-aa07-4dd3-9e07-8009793eb246\",\"name\":\"Lot\",\"order\":2,\"iconClass\":\"\",\"localizedMap\":{\"name\":{\"en_US\":\"Lot\",\"ru_RU\":\"Партия\"}}}
],\"size\":\"SMALL\"}" }
```

Item fields: `id` (the tab's uuid), `name`, `order`, `iconClass`, `localizedMap.name.<locale>`.

> ### ⛔ ALWAYS AUTHOR `"size": "SMALL"` — BIG is what you get by accident, never by choice
>
> `size` is `BIG`/`SMALL` (`TabSize.java`). **Every path that is not an explicit `"SMALL"` lands on
> `BIG`:** the field initialiser is `private TabSize size = TabSize.BIG` (`TabModel.java`) *and*
> `getSize()` coerces null→`BIG` (`TabModel.java`). So a hand-authored `tabModel` that simply omits
> `size` — the normal way a build writes tabs — renders the heavy tab bar. That is a default, not a
> decision, and it is wrong for a business screen: BIG is a chunky full-height bar that eats vertical
> space above every grid and reads like a wizard step-header rather than a section switcher.
>
> **House rule: emit `"size": "SMALL"` in every `tabModel` you author.** SMALL is the compact
> `nav-tabs` strip — the one you see in the platform's own screens. Opt into `BIG` only when a page
> genuinely has 2-3 top-level *modes* (not sections) and you want them to read as a header.
>
> Only `node add --plugin nct.tab.plugin --model '{"items":[…]}'` injects `"size":"SMALL"` for you.
> Hand-written JSON gets nothing — this is the single most common reason a whole project ships with
> BIG tabs. In the UI the same switch is the **Size** dropdown in the tab editor ("Edit Tabs" toolbar
> button → `TabPluginEditor`), so an author can see and change it after the fact; the point of the
> rule is not to make them.
Extra node props: `showCard` (bool), `isParsis`, `className`, `styleName`. **Two same-type tables (e.g. two
`crud.table.plugin`) SHOULD be split across tabs — one per tab pane** — never stacked in one parsis (§2.3).
Each tab's content lives in a child `nct.parsis.plugin` node whose **`identifier` AND `name` MUST equal that
tab's `tabModel.items[].id`**. The tab body is resolved by `PluginWrapperOfContentPanel(…,"nct.parsis.plugin",
item.id)` → `getOrCreateChildContentComponent(…, item.id)`, matched on `child.identifier == item.id`
(`TabPlugin.java`, `PluginUtils.getOrCreateChildContent`). **Order is irrelevant — the identifier match
is load-bearing, NOT the count/order**: in the shipped `erp` sample the child parsis are often in a different order than
the items (Stock/Stock-Movement/Lot node: items `5b7fd1bc,7af19caa,22ae6ae8` but children `7af19caa,5b7fd1bc,
22ae6ae8`) yet each identifier still matches. So: create N child parsis, one per item, each `identifier` == `name`
== its item id; put the tab's business plugin (crud table/form/chart) **inside** that matching parsis.

> ⛔ **This is the ONE place the general "mint a fresh `identifier`/`uniqueIdentifier`" rule (§1.1) does NOT
> apply to a tab child.** Mint a fresh `uniqueIdentifier` only — the `identifier` MUST reuse the tab item id
> verbatim. If identifiers do not match, at first render `getOrCreateChildContent` auto-creates a blank parsis
> per tab and orphans your content, so **every tab renders EMPTY** (same mechanism as §2.4's grid cells).
> `mrjun.py validate` only WARNs on a mismatch — it does NOT error — so this passes a 0-error validate;
> **live-render and confirm each tab pane is populated.**

Other props: see `erp` (`children`=3 with 3 items, each child `identifier` == its item id).

## 1.9 · `grid.plugin` — grid layout (mrjun)

| | |
|---|---|
| Class | `GridPlugin extends PluginPanel` (CMS library) |
| Slot | `properties.model.stringValue` (`GridPluginModel`, `GridPlugin.java`) |

The model is a grid of rows/columns (`GridPropertyBuilder`/`GridPluginModel`), each cell rendering
`Constants.Plugins.PARSIS_PLUGIN` as a nested slot (`GridPlugin.java`, `"el" + index`).
**Does not appear in project exports** — in practice the layout is done via `nct.html.plugin`
(flex/grid CSS) + parsis slots (see 1.1). If needed — the config is in `properties.model.stringValue`.

## 1.10 · `html.localized.plugin` — localized HTML (mrjun)

| | |
|---|---|
| Class | `LocalizedHtmlPlugin extends AbstractHtmlPlugin` (CMS library) |
| Slot | `properties.html` (LOCALIZED — html per locale) |

The same as `html.plugin`, but `html` is a localized string (different HTML per locale). **Does not appear
in practice** — instead nct-ui localizes individual `text`/`label` properties. Related mrjun plugins:
`localized.rich.text.plugin` (`LocalizedRichTextPlugin`), `header.plugin`/
`localized.header.plugin` (`HeaderPlugin`/`LocalizedHeaderPlugin`) — also platform-level, absent from project
exports.

## 1.11 · `global.replacement.plugin` — global $$-replacements

| | |
|---|---|
| Class | `GlobalReplacementPlugin extends NctBasePlugin<ChartJsModel>` (`nct-ui/.../plugin/chart/GlobalReplacementPlugin.java`, name) |
| Slot | — (no content blob; the editor edits query parameters) |

> **Catalog stub.** The page **filter bar** — full params + filtering-through-params + click-to-cross-filter
> recipe → **[22 §4-§5](22-charts-params-and-filters.md)**.

The page-wide **filter bar**: it stores no configuration of its own and builds one control per distinct SQL
parameter declared by the QUERY replacements of the charts on the same page ([22 §4](22-charts-params-and-filters.md)).
This is **not** a plugin with a config blob: in an export its `properties` are only `className/styleName/tagProperties`
(there is no `Javascript`/`model`/`settings` key on it). The class does not do
`getJsonProperty`/`saveContent` into any content slot — instead the form (`ParamsPanel`,
`GlobalReplacementPlugin.java`) edits query parameters and on submit triggers the event
`parametersOfQueryHasBeenChanged` over the affected `QueryDto`. So this is a
behaviour/admin editor of query parameters, not a persist into content-Javascript. One per dashboard page that
has a filter bar.

---

# Group 2 · Action / visual plugins

## 2.1 · `action.button.plugin` — standalone action button

| | |
|---|---|
| Class | `ActionButtonPlugin extends NctBaseModelObjectObjectSyncedPlugin<ActionButtonSettings>` (`nct-ui/.../plugin/dynaform/action/ActionButtonPlugin.java`, the annotation) |
| Settings class | `ActionButtonSettings` (`nct-ui/.../plugin/dynaform/action/ActionButtonSettings.java`; `localizedLabels` = `Map<String,String>`) |
| Settings editor | `ActionButtonSettingsPanel.java` — the per-locale button label is edited via `LocalizedTextFieldsPanel("localizedLabels", …)`; the key persisted in `settings` is **`localizedLabels`** (`{locale → label}`) |
| Config slot | `properties.settings.stringValue` (JSON) |
| Group | `Form Controls` (it is a form control, but a standalone one — not bound to a CRUD field) |

A button that on click **runs an EXECUTION rule** (`ruleIdentifier`) and, optionally, refreshes the
listed components (`refreshTargets`). Unlike crud-table actions (which open a formGroup, see
[04](04-crud-table-plugin.md)), this is a standalone button on a page/in a form.

> ⚠️ **The rule sees CRUD/context data only INSIDE a form.** The button resolves its rule context from the nearest
> `IFormContextProvider` ancestor: inside a `dynaform.form.plugin` the rule runs against the **form's full
> `contextData`** (CRUD row + context attrs, folding in live edits); a **standalone** action button (no form
> ancestor) runs with an **empty `ContextDataDto`** — `context.<ctx>.<crud>.data.get()` is empty, only globals /
> `service.*` calls work. Put the button inside the form when its rule needs the row.

Real node (`erp`, the only instance — "Pull from PO"):

```json
{ "pluginName": "action.button.plugin", "name": "Action Button",
  "properties": { "settings": { "key":"settings", "propertyType":"STRING", "stringValue":
    "{\"localizedLabels\":{\"en_US\":\"Pull from PO\",\"ru_RU\":\"Забрать из PO\",\"hy_AM\":\"Քաշեք պատվերի կետից\"},\"ruleIdentifier\":\"14265d38-d7e4-4300-82cf-38aad872a9d4\",\"variant\":\"PRIMARY\",\"outline\":false,\"gradient\":false,\"shadow\":false,\"size\":\"DEFAULT\",\"shape\":\"DEFAULT\",\"wide\":true,\"iconOnly\":false,\"submitForm\":false,\"showWaitIcon\":false,\"refreshTargets\":\"526ac33a-8e73-4d3e-a31a-78db09252e99\"}"
  } } }
```

The `settings` fields (class `ActionButtonSettings`):

| Field · type | Value · default | Meaning |
|---|---|---|
| `localizedLabels` · Map<locale,String> | — | the button caption per locale (`en_US`/`ru_RU`/…) |
| `iconClass` · String | null | Pe-7s icon CSS class (e.g. `pe-7s-rocket`); empty → no icon |
| `ruleIdentifier` · String | — | **the identifier of the EXECUTION rule**, run on click ([08](08-groovy-rules-and-context.md)) |
| `variant` · enum `ButtonStyleVariant` | `PRIMARY` | `PRIMARY,SECONDARY,SUCCESS,INFO,WARNING,DANGER,LIGHT,DARK,LINK,ALTERNATE,FOCUS` (`ButtonStyleVariant.java`) |
| `outline` · bool | `false` | outline button |
| `gradient` · bool | `false` | gradient |
| `shadow` · bool | `false` | shadow |
| `size` · enum `ButtonSize` | `DEFAULT` | `DEFAULT("")`, `SM("btn-sm")`, `LG("btn-lg")` (`ButtonSize.java`) |
| `shape` · enum `ButtonShape` | `DEFAULT` | `DEFAULT("")`, `PILL("btn-pill")`, `SQUARE("btn-square")` (`ButtonShape.java`) |
| `wide` · bool | `false` | `btn-wide` |
| `iconOnly` · bool | `false` | icon only |
| `submitForm` · bool | `false` | if inside a form — submits the form before the rule |
| `showWaitIcon` · bool | `false` | a spinner on the button during the click (attribute `icon-wait="true"`) |
| `blockSelector` · String | null | CSS selector whose elements are blocked by an overlay for the duration of the action |
| `refreshTargets` · String | null | CSV of `uniqueIdentifier`s of `IRefreshable` components, re-rendered after the rule |

### How to create from scratch
1. Create an EXECUTION rule (`ruleType:"EXECUTION_RULE"`, `executor:"GroovyExecutionRule"`,
   `contextIdentifiers:[<context>]`), and record its `identifier` — see [08](08-groovy-rules-and-context.md).
2. Node `pluginName:"action.button.plugin"`; `properties.settings.stringValue` = the JSON above with your
   `ruleIdentifier`, `localizedLabels` and `variant`. `refreshTargets` — CSV of `uniqueIdentifier`s of the
   nodes to refresh (for example, the crud table below the button).
3. Place the node into the page's `nct.parsis.plugin` slot (or into a form).

> 🔧 **Tooling.** There is no dedicated command for `action.button.plugin` in `mrjun.py`; it is a form-control plugin
> with a `settings` slot — use `node add --parent <page/parsis> --plugin action.button.plugin
> --settings @settings.json`, then `node patch-settings <id> --set ruleIdentifier=str:<uuid>`
> (the tooling auto-picks the `settings` slot, since it is not table/chart). The rule — `rule add --type EXECUTION_RULE`.

## 2.2 · `chart.js.plugin` — chart / arbitrary JS widget with data binding

| | |
|---|---|
| Class | `ChartJsPlugin extends NctBasePlugin<ChartJsModel>` (`nct-ui/.../plugin/chart/ChartJsPlugin.java`) |
| Model class | `ChartJsModel` (`ChartJsModel.java`) |
| Config slot | `properties.Javascript.stringValue` (JSON `ChartJsModel`) — **not `model`, not `settings`**, but the named property `Javascript` (`ChartJsPlugin.java`, `ReportServiceUtils.JS_MODEL_NAME`) |
| Group | `Reporting` |

> **Catalog stub.** Full recipe — the `ChartJsModel`/`ChartJsReplacement` schema, `$$('name', default, 'Type')`
> data binding, `QUERY`/`LABEL` strategy, query params, the `global.replacement` filter bar, click-to-cross-filter,
> and theme-safe rendering — is in **[22-charts-params-and-filters.md](22-charts-params-and-filters.md)**.

A universal "block with HTML + JS + data". Despite the name, this is **not only charts** — it is any
custom widget: an HTML template + JS logic + `replacements` (data from SQL queries). It is the most frequent
business plugin in a real project. `ChartJsModel`: `id`, `js`, `html`, `css`, `schedule` (`ScheduleDto`),
`replacements` (`List<ChartJsReplacement>`).

**Data binding** goes through `replacements`: the JS accesses the data via `$$('name', default, 'Type')`, and
each `replacement` is bound to a saved `query` (`queryIdentifier` + an embedded **MINIMAL 12-field `QueryDto`**
copy of `query` — NOT the 21-field rep-object; see the ⛔ below and doc 22) with a
`replaceStrategy` (`LABEL`/…), `columnName`, `defaultValue`, `maxItemsCount`. Real node (`erp`,
"Strategic Planning Health" — collapsible with 1 replacement from the query `Recommendation`), `Javascript`
decoded (abridged):

```json
{
  "id": "0c00d7c0-5110-46f7-9be3-578ac3a53504",
  "js":  "var self = this;\r\nthis.$find('.collapsible').on('click', function() { ... });\r\nvar count = $$('1.epic_desc', 0, 'Integer[]')[0];\r\nif(count >= 0) { this.$find('.adv_cnt').show(); }",
  "html": "<div><style>.collapsible{background-color:#0069B3;color:white;...}</style></div><div><button class=\"collapsible\">...</button><div class=\"content container\">...</div></div>",
  "replacements": [
    { "name": "1.epic_desc",
      "group": "$$('1.epic_desc', 0, 'Integer[]')",
      "type": "Integer[]",
      "replaceStrategy": "LABEL",
      "queryIdentifier": "a1fabdde-93b1-4ff4-b56f-61ca43bacc70",
      "query": { "name":"Recommendation", "query":"select 1 as numrow, ... union all ...",
                 "sourceIdentifier":"da6ff14b-62b5-45aa-ad58-4e2a60af3614", "offset":0,
                 "itemsPerPage":1000, "parameters":{"Project name":{"value":"<the current preview value>"}},
                 "identifier":"a1fabdde-93b1-4ff4-b56f-61ca43bacc70",
                 "realmName":"<realm>", "clientName":"<client>" },
      "defaultValue": "0", "columnName": "count", "order": 0, "maxItemsCount": 1000 }
  ]
}
```

> ⛔ The embedded `replacements[].query` above is **abridged**. A real embedded copy carries **exactly the 12
> `QueryDto` fields** — `{id, identifier, realmName, clientName, name, query, sourceIdentifier, offset,
> itemsPerPage, parameters, attributes:{}, aggregations:{aggregations:[],groupByList:[],orderByList:[]}}`
> (`aggregations`=`[]` not null, `attributes`=`{}`). **Do NOT paste the 21-field saved-query rep-object from
> `rep-objects.queries[]`** — its rep-metadata (`creationTime`/`modificationTime`/`errors`/`message`/`hidden`/
> `schedule`/`lastScheduledTime`/`statementTimeoutSeconds`/`wrapInPaging`) fails `ChartJsModel` deserialization,
> which `ChartJsPlugin` silently swallows into an empty model → **the chart renders EMPTY as a "Modify
> html" cell** while import stays clean. See [22-charts-params-and-filters.md](22-charts-params-and-filters.md)
> §embedded-query.

Key `ChartJsModel` fields:

| Field · type | Meaning |
|---|---|
| `id` · String | the chart model's uuid |
| `html` · String | the widget's HTML template (with `<style>`, the `.collapsible`, `.content` classes, …) |
| `js` · String | JS: `this.$find('.sel')`, `this.$component()`, data access via `$$('name', default, 'Type')` |
| `css` · String | LEGACY single CSS block; still honoured (read as `cssByTheme["*"]`) |
| `cssByTheme` · Map | **per-theme CSS**, key `"*"` or an exact `Skin.getName()`. Editor: the **Css** tab. Only `"*"` + the active skin are emitted, each **scoped** to the chart instance -- so unlike a `<style>` inside `html` (which is GLOBAL) it cannot leak onto other charts. See [24a](24a-theming-and-dark-mode.md) |
| `schedule` · `ScheduleDto` | the recompute schedule (usually empty) |
| `replacements[]` · `ChartJsReplacement` | data bindings (see below) |

`ChartJsReplacement` fields: `name`, `group` (the `$$(...)` call itself), `type` (`Integer[]`/`String[]`/…),
`replaceStrategy` (`LABEL`/…), `queryIdentifier` (**+ a MINIMAL 12-field `QueryDto` copy in `query`** — ONLY
`{id, identifier, realmName, clientName, name, query, sourceIdentifier, offset, itemsPerPage, parameters,
attributes:{}, aggregations:{aggregations:[],groupByList:[],orderByList:[]}}`; **do NOT paste the 21-field saved-query
rep-object from `rep-objects.queries[]`** — its rep-metadata `creationTime/modificationTime/errors/message/hidden/
schedule/lastScheduledTime/statementTimeoutSeconds/wrapInPaging` fails `ChartJsModel` deserialization, which
`ChartJsPlugin` silently swallows → the chart renders EMPTY as a "Modify html" cell; see doc 22
§embedded-query), `defaultValue`, `columnName`, `order`, `maxItemsCount`, `futureReplacements[]`.

**"Chart types"**: the chart type is not a model field — it is a consequence of which JS library the
`js` calls (Chart.js/Plotly/**ECharts**/arbitrary DOM — those, plus `chartjs-adapter-date-fns` and mermaid, are the libs `renderHead` injects, `ChartJsPlugin.java`; ApexCharts is **not** loaded here). The model stores only html+js+data; the chart type
is determined by the code in `js`.

### How to create from scratch
1. Save an SQL query → `rep-objects.queries[]` (see [12](12-queries-sources-schedulers-and-rest.md)),
   and remember its `identifier`.
2. Node `pluginName:"chart.js.plugin"`; into `properties.Javascript.stringValue` put the JSON `ChartJsModel`:
   a fresh `id`, your `html`, `js` (data access via `$$('<name>', <default>, '<Type>')`), and one
   `replacement` per data source (`name` = the key in `$$(...)`, `queryIdentifier` = your query,
   `columnName` = the result column, `type`, `defaultValue`, `maxItemsCount`).
3. Place the node into the page's `nct.parsis.plugin` slot.

> 🔧 **Tooling.** The `chart.js.plugin` config lives in **`properties.Javascript.stringValue`**, NOT in `model`.
> The toolkit knows this: `node add --plugin chart.js.plugin --model <json>` automatically puts the JSON into the
> `Javascript` slot (see [`tools/README.md`](tools/README.md)). To make a targeted edit to an existing chart,
> edit `properties.Javascript` directly (`node set-model` writes into `model` — the wrong slot for a chart).
> Data queries — via `query add`. **`global.replacement.plugin` is a different thing:** it has no
> content blob (only `className/styleName/tagProperties`), its editor edits query parameters and does not
> persist into `Javascript`; do not create a `--model` slot for it (see 1.11 above).

### ⛔ Theme-aware charts & KPI cards (do NOT hardcode white)

A chart renders into the page over the **active theme** (dark-blue, white, gray — the tenant picks). The
rendering library decides the default background:

- **Chart.js** (`new Chart(ctx, …)`, canvas): background is **transparent by default** → it already inherits
  the theme. Its default text/grid colors are mid-gray and read on most themes. Nothing extra needed.
- **Plotly** (`Plotly.newPlot(id, data, layout, …)`, used for `indicator` KPI tiles): `paper_bgcolor` /
  `plot_bgcolor` default to **WHITE** → a white box that clashes with a dark theme. This is the "white square
  reports" bug. You **must** make it theme-aware — never leave the default and never hardcode a bg hex.

**The fix (verified live on delivered KPI tiles):**

1. Style the container via the chart's **`css`** field using the **house theme-var convention** (the
   `themes/*.css` contract, verified across all 5 themes) — a *raised surface* is
   `var(--current-line, var(--bs-light))` (the 4 dark themes set `--current-line` to a proper card color —
   `#262f36` dark-blue, `#2d2d2d` dark, `#44475a` dracula, `#2c302e` forest; light `standard.css` omits it and
   falls back to `--bs-light:#f4f7fb`), text is `--bs-body-color` (light `--foreground` in dark themes, `#495057`
   in light), border is `--bs-border-color`:
   ```css
   .kpi{background:var(--current-line,var(--bs-light));
        color:var(--bs-body-color);
        border:1px solid var(--bs-border-color);
        border-radius:.5rem;box-shadow:0 1px 3px rgba(0,0,0,.10);overflow:hidden}
   ```
2. Make Plotly **transparent** and read the text color **live from the themed element** (never a literal), so
   the number/title are legible on every theme:
   ```js
   var fg = getComputedStyle(this.$find('.kpi')[0]).color || '#c8d3e0';   // resolves --bs-body-color
   var layout = {autosize:true,height:120,margin:{t:30,r:5,l:5,b:5},
                 paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{color:fg}};
   ```
   `layout.font.color` cascades to the title; the KPI number keeps its own **semantic** color (below).
3. Pick **semantic number colors that read on BOTH light and dark** — mid-lightness/mid-saturation. Dark
   maroons/navies (`#8b1a2b`, `#c23728`) vanish on a dark theme; use e.g. `#e2725b`/`#e0483a` (warn/danger),
   `#47CC29` (ok), `#F2BB30` (caution), `#22a7f0` (info), `#d1495b` (alert). The status/bar/pie palettes in the
   Chart.js charts are already mid-tone and need no change.

Same rule for the container `.card`/panel around any chart: bind bg/text/border to theme vars, never a literal
`background:#fff`. House theme tokens (`themes/*.css`): `--bs-body-color` (text), `--bs-body-bg` (page bg),
`var(--current-line, var(--bs-light))` (raised panel/card), `--bs-border-color` (hairline), `--purple`/`--bs-primary`
(accent), `--red`/`--bs-danger` (danger). ⛔ Only the dark themes define the semantic `--current-line`/`--foreground`
/`--comment`/`--purple` vars; light `standard.css` defines only `--bs-*` — so ALWAYS write
`var(--current-line, var(--bs-light))` with the `--bs-*` fallback, never a bare `var(--current-line)`.

---

## 2.3 · ⛔ At most ONE `crud.table` / `crud.tree` / `process.table` per **PAGE** — TABS are the only exception

**Two tables of the same type may NOT sit on the same page — the one exception is when each is in its own TAB
(`nct.tab.plugin`).** That is the intended way to co-locate several tables on a page; there is no other (two in
two grid cells, or two stacked, both break — see below). (Different types do not collide on the sync key, but
they are still forbidden on one page — see THE RULE below, which `validate` enforces for the mixed case too.)

**Why (root cause) — and why tabs are enough.** Each of these plugins keys its *authoring / live-settings
machinery* by plugin **type**, not by instance, and broadcasts **page-wide**:

- Its **Settings panel** is registered under a constant nav name — `"CRUD Table Settings"`
  (`CrudTablePlugin.showSettings()` → `EventUtils.trigger(..., "openGloseRightGroup", "CRUD Table Settings")`).
  The right-nav registry **dedupes by (name, tabName)** (`NctRightKickerPanel`), so a second instance's
  registration **evicts the first** — only ONE settings panel survives (last-rendered wins).
- Its **live-sync channel** is a constant `getKey()` — `"CrudTableSynced"` (`CrudTablePlugin.getKey()`). Every
  instance subscribes; `EventUtils` broadcasts page-wide and the listener does `setModelObject(...)`
  **unconditionally on every instance** (`NctBaseModelObjectObjectSyncedPlugin`).
- (Conditional) a `dynaform.filter.form` submit `onFilterSubmit` refreshes **both** tables with the **same**
  filter map.

`crud.tree.plugin` uses `"CrudTreeSynced"` / `"CRUD Tree Settings"`; `process.table.pluin` uses
`"ProcessTableSynced"` / `"Process Table Settings"` — same for two trees / two process tables. **Crucial nuance:
this collision only bites the *interactive Site-Authoring UI*** (opening a table's Settings panel, or a live
CRUD-alias change syncing across instances). A **pre-built, imported project** where the tables are already
configured and just **display** data does not hit it: two configured tables in two **tabs** render, page and
filter fine, because only one tab is visible at a time (verified on a pre-built imported project holding two
configured `crud.table` instances in two tabs of one page). Per-instance rendering/paging/AJAX is always isolated
(unique Wicket markupIds, no DataTables).

> ### ⛔ THE RULE, AND THE HALF OF IT THAT KEEPS GETTING LOST
>
> **ONE table per page. The only exception is separate tabs. This is true of ANY two table plugins —
> `crud.table.plugin`, `crud.tree.plugin`, `process.table.pluin` — in ANY combination.**
>
> The mechanism above is *type-scoped*, so it is tempting to conclude that a crud-table beside a
> process-table is fine because their sync keys differ. **Technically true, and irrelevant.** The
> product rule is not derived from the collision; the collision is only why the same-type case is
> additionally *broken*. A page is one workplace answering one question, and two stacked grids force
> the reader to work out which one they are looking at before they can read either.
>
> Shipped once for real: a register page carrying a `crud.table.plugin` of the documents **and** a
> `process.table.pluin` of the matching workflow instances, stacked in one parsis. Every same-type
> page in that same project had been split into tabs correctly — the builder had read the rule, seen
> "same type", and concluded the mixed pair was exempt. It was reading this section. That is the
> failure mode to design against: a rule scoped to a plugin name reads as "does not apply" the moment
> the second plugin has a different name.
>
> So, when a page needs a second table: **put each in its own `nct.tab.plugin` tab, or give each its
> own page.** `mrjun.py validate` ERRORs on both the same-type and the mixed-type case
> (`_check_one_table_plugin_per_page`; a tab pane counts as its own container, so tables in
> DIFFERENT tabs pass).

## 2.4 · Dashboards carry **charts only** — no data tables, no dynaform filter

A dashboard page (KPIs + charts) must **not** also host a `crud.table`/`crud.tree`/`process.table` — put
drill-down tables on their **own** pages and link to them (keeps 2.3 satisfied and the page fast). And a
`dynaform.filter.form` is **inert on a chart dashboard**: its `onFilterSubmit` drives **tables**, not charts —
`chart.js.plugin` only re-queries on the `parametersOfQueryHasBeenChanged` event (the report query-parameter /
`global.replacement.plugin` mechanism, `ChartJsPlugin.java`), never on `onFilterSubmit`. So a filter bar on a
table-less dashboard filters nothing — drop it. To make dashboard **charts** filterable, parameterize the SQL of
the chart's QUERY replacement with an inline placeholder — e.g.
`WHERE branch = {name:'Branch', type:'dropdown-string', dropDownPopulation:{query:'Branches', value:'code', name:'name'}}` —
and put a `global.replacement.plugin` (the filter bar) on the same page; it builds one control per distinct
parameter and re-runs the charts ([22 §4](22-charts-params-and-filters.md)). `$$('name', default, 'Type')` is the
separate **JS** data binding inside the chart script ([22 §2](22-charts-params-and-filters.md)) — it is never
looked for in SQL.

**Dashboard layout recipe** (the shape that works for a Home / overview page): the page's content
`nct.parsis.plugin` (id `parsis`) holds a header `nct.html.plugin` then one or more **grid-row** `nct.html.plugin`
nodes. Each grid-row's inline HTML is `<div class="row m-2"><div class="col-md-4"><plugin id="<UUID>"
name="nct.parsis.plugin"></plugin></div>…</div>`, and its children are `nct.parsis.plugin` cells whose
`identifier` == that `<plugin id>`; each cell holds exactly one `chart.js.plugin`. KPI tiles = Plotly
`indicator` (theme-safe template, §2.2); charts = Chart.js (transparent by default). See
[21-homepage-and-redirect.md](21-homepage-and-redirect.md).

---

# Group 3 · Site chrome (header/sidebar/footer/breadcrumbs)

These are parts of the site layout, embedded into `html.plugin` via `<plugin>` (see 1.3). All are `NctBasePlugin`
without a user JSON config; the only setup is `className`/`styleName` (passed in from
the `<property>` in the layout HTML). **All are scaffold, not created by hand** (cloned by the page template).

| `pluginName` | Class · where | Purpose |
|---|---|---|
| `site.header.plugin` | `NctHeaderPlugin` · `nct-ui/.../plugin/admin/header/NctHeaderPlugin.java` | the page's top header |
| `site.footer.plugin` | `NctFooterPlugin` · `nct-ui/.../plugin/admin/NctFooterPlugin.java` | footer (`editBorderSelector=".app-footer__inner"`) |
| `site.kicker.plugin` | `NctKickerPlugin` · `nct-ui/.../plugin/admin/kicker/NctKickerPlugin.java` | the left navigation sidebar (site menu); quick-links tree in `properties.modelGroups` — see [17-left-nav-quick-links.md](17-left-nav-quick-links.md) |
| `site.right.kicker.plugin` | `NctRightKickerPlugin` · `nct-ui/.../plugin/admin/kicker/right/NctRightKickerPlugin.java` | the right slide-out panel (drawer) |
| `site.breadcrumb.plugin` | `BreadCrumbPlugin` · `nct-ui/.../plugin/report/BreadCrumbPlugin.java` | breadcrumbs |

`footer`/`kicker`/`right-kicker` have `hideInKicker=true`; `header` — `hideInKicker=false`;
`breadcrumb` does not set the attribute (default `false`). They are configured via `<property name="className" value="…">`
in the layout HTML — for example `site.header.plugin` gets `className="app-header__content"`, and
`site.right.kicker.plugin` — `className="app-drawer-wrapper"` (see the example in 1.3).

`siteMapPage` (the page class) — see it separately below (it is not chrome, but the page container itself).

---

# Group 4 · `siteMapPage` — the page

| | |
|---|---|
| Classes | `SiteMapPage` (`SiteMapPage.java`, template `ARCHITECTUI_HTML_PRO`) and `SiteMapPageRaven` (`SiteMapPageRaven.java`, template `RAVEN`) — **both** share the name `CmsServiceConstants.SITE_MAP_PAGE_PLUGIN_NAME = "siteMapPage"` (`mrjun-.../CmsServiceConstants.java`) |
| Config slot | `alias` — **a top-level node field** (sibling of `properties`/`roleAccess`); while `pageTitle`, `pageDescription`, `layout`, `metaTags`, `additionalCss`, `Redirect`, `isParsis` — are entries under `properties` |
| Children | `html.plugin` (layout scaffold) + optionally nested `siteMapPage` (subpages) |

Every page is a `siteMapPage` node. The tree root (`rootContent`) is also a `siteMapPage` (in empty:
`name:"Home"`, 25 children). Real node (`empty`, the "Database" page):

```json
{ "pluginName": "siteMapPage", "name": "Database", "order": 20,
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": false,
    "accessors": { "admin": {"view":true,"edit":true,"advancedEdit":true}, "nct_author": {"view":true,"edit":true,"advancedEdit":true}, "...": {} },
    "roleGroupAccessors": { "Author": {"view":true,"edit":true,"advancedEdit":true}, "Developer": {"view":false,...} } },
  "properties": {
    "pageTitle":       { "propertyType":"LOCALIZED_STRING", "localizedStringValue": {} },
    "pageDescription": { "propertyType":"LOCALIZED_STRING", "localizedStringValue": {} },
    "layout":          { "propertyType":"STRING", "stringValue":"Main" },
    "metaTags":        { "propertyType":"STRING", "stringValue":"" },
    "additionalCss":   { "propertyType":"STRING", "stringValue":"" },
    "Redirect":        { "propertyType":"STRING", "stringValue":"" },
    "isParsis":        { "propertyType":"BOOLEAN" }
  } }
```

`roleAccess` (page access) in detail — [01-content-model-and-pages.md](01-content-model-and-pages.md):
`publicReadAccess=false` + `authenticatedUserAccess=true` = authenticated users only.

### How to create from scratch
> 🔧 **Tooling.** `mrjun.py page add --parent <id|name|root> --name <s> [--alias <s>] [--auth|--public]
> [--layout <vp>]` — "Add a real, renderable siteMapPage (clones the standard layout scaffold, empties the
> content container)". This is the **only correct way** — assembling `siteMapPage` +
> the `html.plugin` scaffold + a parsis slot by hand is hard and easy to get wrong. After `page add`, business plugins are placed
> inside via `node add --parent <page>`.

---

# Group 5 · Admin / system plugins (scaffold — not authored by hand)

All of these are **one instance each** in a project export — they are the fixed admin pages of the empty
scaffold. A **truncated** scaffold is possible (a project created before a console page existed, or with it
removed): there the `dynamic.cruds.plugin` (Business Logic) or `report.pdf.templates.plugin` (Pdf Templates)
page is simply missing. Their nodes are already present in the empty baseline; you **do not create or
configure them** — just **keep them as-is** and append business pages next to them. Their config is empty (`className`/
`styleName`/`tagProperties`), and the platform itself manages the data (users/roles/sources/… live in
`rep-objects` and the DB, not in the node).

The `siteMapPage → plugin` table (from `empty/branches.json`, `.rootContent.children[]`):

| Admin page (name) | `pluginName` inside | Class · where (nct-ui) | What it does | In depth |
|---|---|---|---|---|
| User management | `admin.user.management.plugin` | `UserManagementPlugin` · `plugin/admin/usermanagement/UserManagementPlugin.java` | managing project users | — |
| Role Management | `admin.rolegroup.management.plugin` | `RoleGroupManagementPlugin` · `plugin/admin/usermanagement/RoleGroupManagementPlugin.java` | role groups | [12](12-queries-sources-schedulers-and-rest.md) |
| Sources | `admin.sources.plugin` | `SourcesPlugin` · `plugin/report/sources/SourcesPlugin.java` | DB sources (rep-objects.sources) | [12](12-queries-sources-schedulers-and-rest.md) |
| Schedulers | `admin.schedulers.plugin` | `SchedulerPlugin` · `plugin/report/schedulers/SchedulerPlugin.java` | schedulers | [12](12-queries-sources-schedulers-and-rest.md) |
| Queries (list) | `admin.queries.plugin` | `QueriesPlugin` · `plugin/report/queries/list/QueriesPlugin.java` | the list of saved queries | [12](12-queries-sources-schedulers-and-rest.md) |
| Queries (editor) | `admin.query.plugin` | `QueryPlugin` · `plugin/report/queries/viewedit/QueryPlugin.java` | the editor for a single query | [12](12-queries-sources-schedulers-and-rest.md) |
| Queries (results) | `query.results.plugin` | `QueryResultsPlugin` · `plugin/report/queries/viewedit/QueryResultsPlugin.java` | the query results table | [12](12-queries-sources-schedulers-and-rest.md) |
| Settings | `project.settings.plugin` | `ProjectSettingsPlugin` · `plugin/dynamic/projectsettings/ProjectSettingsPlugin.java` | project settings (rep-objects.settings) | [12](12-queries-sources-schedulers-and-rest.md) |
| Audit Logs | `audit.log.list.plugin` | `AuditLogListPlugin` · `plugin/auditlog/AuditLogListPlugin.java` | the audit log | — |
| Profile | `user.profile.plugin` | `UserProfilePlugin` · `plugin/profile/UserProfilePlugin.java` | the current user's profile | — |
| ~~Ontology~~ *(page removed from the baseline)* | `ontology.viewer.plugin` | `OntologyViewerPlugin` · `plugin/ontology/OntologyViewerPlugin.java` | ontology viewer — **no config slot** (empty properties: `className`/`styleName`/`tagProperties`); the `NctBasePlugin<OntologyModel>` type param is **vestigial**, `initPluginContent` never reads `properties.model` (`OntologyViewerPlugin.java`) | — |
| Contexts | `dynaform.context.list.plugin` | `ContextListPlugin` · `plugin/context/ContextListPlugin.java` | the list of contexts | [08](08-groovy-rules-and-context.md) |
| Rules (list) | `executor.rule.list.plugin` | `RuleListPlugin` · `plugin/executor/rule/RuleListPlugin.java` | the list of rules | [08](08-groovy-rules-and-context.md) |
| Rules (editor) | `executor.rule.script.plugin` | `RuleScriptPlugin` · `plugin/executor/rule/RuleScriptPlugin.java` | the rule script editor (no model/settings blob; `RuleDto` is a rep-object, resolved via `?rule=<identifier>`, `RuleScriptPlugin.java`) | [08](08-groovy-rules-and-context.md) |
| Form Groups | `dynaform.form.groups.plugin` | `FormGroupsPlugin` · `plugin/dynaform/formfroups/FormGroupsPlugin.java` | the list of form groups | [06](06-form-groups-and-mapping.md) |
| Processes (list) ⚠️ | `processes.plugin` | **⚠️ no `@PluginConfig` class** | ⚠️ **dead/legacy** — the process list was merged into the single master-detail `processes.selectedplugin`; the baseline node renders as `mrjun.plugin.not.found`. Leave it alone; author new process screens with `processes.selectedplugin` or `process.table.pluin` | [07](07-workflows-and-tasks.md) |
| Processes | `processes.selectedplugin` | `ProcessSelectedPlugin` · `plugin/workflow/processes/ProcessSelectedPlugin.java` | the whole Processes screen: one self-contained master-detail panel — process list on the left, process detail on the right | [07](07-workflows-and-tasks.md) |
| Workflows | `workflows.plugin` | `WorkflowsPlugin` · `plugin/workflow/workflows/list/WorkflowsPlugin.java` | the list of workflows | [07](07-workflows-and-tasks.md) |
| Workflows (BPMN) | `bpmn2modeler.plugin` | `WorkflowBpmn2ModelerPlugin` · `plugin/workflow/workflows/bpmn2editor/WorkflowBpmn2ModelerPlugin.java` | the BPMN2 modeler | [07](07-workflows-and-tasks.md) |
| Database | `database.management.plugin` | `DatabaseManagementPlugin` · `plugin/dynamic/database/DatabaseManagementPlugin.java` | DB schema management (`properties.model`) | [10](10-database-management.md) |
| Business Logic | `dynamic.cruds.plugin` | `DynamicCrudsPlugin` · `plugin/dynamic/dynamiccruds/DynamicCrudsPlugin.java` | dynamic CRUD / business logic (`properties.model`) | [11](11-business-logic-dynamic-crud.md) |
| Mail Templates | `messaging.mail.templates.plugin` | `MailTemplatesPlugin` · `plugin/mailtemplate/MailTemplatesPlugin.java` | mail-template **management scaffold** — the node carries **no** `properties.model` (properties = `className`/`styleName`/`tagProperties` only); the templates live in `rep-objects.mailTemplates[]`, saved via `mailTemplateService` (see [15]) | [12](12-queries-sources-schedulers-and-rest.md),[15](15-pdf-and-mail.md) |
| Pdf Templates | `report.pdf.templates.plugin` | `PdfTemplatesPlugin` · `plugin/pdftemplate/PdfTemplatesPlugin.java` | PDF-template **management scaffold** — the node carries **no** `properties.model` (properties = `className`/`styleName`/`tagProperties` only); the templates live in `rep-objects.pdfTemplates[]`, saved via `pdfTemplateService` (see [15]) | [15](15-pdf-and-mail.md) |
| ~~Branches~~ *(page removed from the baseline)* | `process.table.pluin` | `ProcessTablePlugin` · `plugin/process/ProcessTablePlugin.java` | the branches table (reused the process table) | [05](05-crud-tree-and-process-table.md) |
| ~~reports~~ ⚠️ *(page removed from the baseline)* | `pdf.report.plugin`, `pdf.report.page.plugin` | **⚠️ no `@PluginConfig` class** (none declared anywhere in the platform sources) | ⚠️ **dead/legacy** — render as `mrjun.plugin.not.found`; for PDFs use `report.pdf.templates.plugin` | [15](15-pdf-and-mail.md),[01](01-content-model-and-pages.md) |

> ⚠️ **`pdf.report.plugin` / `pdf.report.page.plugin` are orphan/dead — do NOT author new nodes with them.**
> They appeared once each in OLDER project exports (a `Home → reports → Pdf → html.plugin →
> pdf.report.plugin → pdf.report.page.plugin` subtree) and are **absent from the current baseline**, but
> **no class registers either name** via `@PluginConfig` anywhere in
> `nct-ui`/`mrjun`/`richwicket` (grep = 0), so on the current code they render as `mrjun.plugin.not.found` (registry
> miss). The live PDF plugin is **`report.pdf.templates.plugin`** (`PdfTemplatesPlugin.java`); write new PDF nodes
> under it. Same fact in [01-content-model-and-pages.md](01-content-model-and-pages.md) (the legacy-PDF-pair note) and
> [15-pdf-and-mail.md](15-pdf-and-mail.md).
>
> ⚠️ **`processes.plugin` is orphan/dead in the same way — do NOT author new nodes with it.** The Workflows-console
> process **list** was merged into the single master-detail `processes.selectedplugin`, and no class registers
> `processes.plugin` via `@PluginConfig` any more, so the one node every baseline inherits renders as
> `mrjun.plugin.not.found` next to the working Processes panel. Leave the inherited node where it is (removing it is
> a cosmetic change, not a fix you owe anyone); for a process list of your own use `processes.selectedplugin` or the
> live `process.table.pluin` ([05](05-crud-tree-and-process-table.md)).
>
> **One** plugin carries a `properties.model` whose DTO shape is documented **nowhere**: `discovery.plugin`
> (`DiscoveryPluginModel`, genuinely read at `DiscoveryPlugin.java` via `getJsonProperty("model", …)`) — in the
> absent-table below, an admin scaffold that never appears in a project export and is **not hand-authored**, so no construction recipe exists; if
> ever needed, its model must be reverse-engineered from the class. (`ontology.viewer.plugin` does **not** carry a
> model — its `NctBasePlugin<OntologyModel>` type param is vestigial and never read from `properties`; it renders as
> an empty admin scaffold. It appeared once in older exports and is absent from the current baseline.)

**Plugins from the code that are absent from project exports** (platform-level — they belong to the
admin application/orgs, not the project; so they are not written into a project export):

| `pluginName` | Class · where | Purpose | Status |
|---|---|---|---|
| `admin.organizations.plugin` | `OrganizationsPlugin` · `nct-ui/.../plugin/admin/orgabnizations/OrganizationsPlugin.java` | managing organizations (cross-project level) | scaffold, **never** in a project export |
| `admin.projects.plugin` | `ProjectsPlugin` · `nct-ui/.../plugin/admin/projects/ProjectsPlugin.java` | managing projects | scaffold, **0** |
| `admin.integrations.list.plugin` | `IntegrationsListPlugin` · `nct-ui/.../plugin/admin/integrations/IntegrationsListPlugin.java` | the list of integrations | scaffold, **0** |
| `admin.localization.plugin` | `LocalizationPlugin` · `nct-ui/.../plugin/admin/localization/LocalizationPlugin.java` | localization | scaffold, **0** |
| `project.template.management.plugin` | `ProjectTemplateManagementPlugin` · `nct-ui/.../plugin/admin/projecttemplate/ProjectTemplateManagementPlugin.java` | template management | scaffold, **0** |
| `discovery.plugin` | `DiscoveryPlugin` · `nct-ui/.../plugin/discovery/DiscoveryPlugin.java` | Customer Discovery (`properties.model` `DiscoveryPluginModel`) | scaffold, **0** |

All six are `NctBasePlugin`/`NctBaseModelObjectObjectSyncedPlugin` without a project config. If such a node
does appear, it comes from the platform template, not authored into a project export.

---

## Gotchas

1. **The config slot is plugin-dependent — there is no single rule.** form controls → `settings`; table/tree/
   process/db/dynamic-cruds → `model`; **chart → `Javascript`**; html/nct-html → `html`; tab → `tabModel`;
   help → `helpSettings`; label → `text`; image → `url`+props; siteMapPage → top-level props. Separately:
   `rule-script`/landing/form-plugin/`global.replacement`/`list.item` have **no config blob at all** — their
   DTO comes as a rep-object via a URL parameter (`?rule=`, `?group=`, `formModeIdentifier`) or it is a
   container/behaviour editor (`global.replacement` edits query parameters). Do not write the crud config into
   `settings`, the chart config into `model`, and do not invent a `model`/`Javascript` slot where there is none
   (the tooling flags it as "settings-vs-model misuse").
2. **`process.table.pluin` is a real typo** (`ProcessTablePlugin.java`). Do not "fix" it —
   the import will break. The tooling deliberately preserves it (`validate` catches `process.table.pluin` typo altered).
3. **A `<plugin>` in html is not text but child nodes.** Each top-level `<plugin id name>` inside
   `nct.html.plugin`/`html.plugin` spawns a **real content node** via
   `getOrCreateChildContentComponent` (`AbstractHtmlPlugin.java`). Nested `<plugin>` (inside another
   `<plugin>`) are ignored at the top level. This means: for a plugin from the html to actually render,
   the corresponding child content node must exist **and its `identifier` must equal the `<plugin id>`** (the match
   is `Objects.equals(child.getIdentifier(), id)` — not by `name`, not by count/order; §1.1 step 3). A fresh-uuid
   child never matches → a blank child is auto-created and your plugin is orphaned (renders empty, import clean).
4. **Site chrome and layout are scaffold.** The `html.plugin` layout, the `site.*` plugins and the root parsis are cloned
   at `page add`. Do not assemble them by hand — use `mrjun.py page add`.
5. **The admin pages are already in empty.** 24+ `siteMapPage` nodes with admin plugins are part of the empty scaffold. Keep
   them unchanged; append business pages next to them.
6. **`nct.parsis.plugin` vs `parsis.plugin`.** The former is the nct-ui subclass of the latter; both are drop containers
   without a JSON config (the config = `children`). In business pages the content slot is usually `nct.parsis.plugin`.
7. **`chart.js.plugin` is not only charts.** It is an html+js+data widget; the chart type is set in `js`, not
   as a separate field. The data — via `replacements[]` → `$$('name', default, 'Type')`, each bound to a `query`.
8. **Localization in content plugins.** `text`/`label`/`message`/`tabModel.items[].name` are a
   `localizedStringValue`/`localizedMap` with locale keys (`en_US`,`ru_RU`,`hy_AM`), not a plain string.
9. **Many plugins exist in the code but never in a project export.** Before "authoring" a plugin, check it
   against the inventory above — if a `pluginName` is not there, it is platform-level, not written by hand into a
   project.

---

### See also
- [01-content-model-and-pages.md](01-content-model-and-pages.md) — the node model, `properties`, `roleAccess`, pages, parsis.
- [02-form-controls-reference.md](02-form-controls-reference.md) — all `dynaform.form.*` controls (the `settings` slot).
- [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) — field generation + `nct.label`/`nct.help` around them.
- [04-crud-table-plugin.md](04-crud-table-plugin.md) / [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) — `crud.table`/`crud.tree`/`process.table.pluin` (the `model` slot).
- [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) — `dynaform.form.groups.*`.
- [07-workflows-and-tasks.md](07-workflows-and-tasks.md) — `workflows.plugin`/`processes.*`/`bpmn2modeler.plugin`.
- [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) — `executor.rule.*`, `dynaform.context.list.plugin`.
- [10-database-management.md](10-database-management.md) — `database.management.plugin`.
- [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) — `dynamic.cruds.plugin`.
- [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) — `admin.sources/queries/query/schedulers`, `project.settings.plugin`, `messaging.mail.templates.plugin`.
- [15-pdf-and-mail.md](15-pdf-and-mail.md) — `report.pdf.templates.plugin`, `pdf.report.plugin`, `pdf.report.page.plugin`.
