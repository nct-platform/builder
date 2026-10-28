# 14 · Full plugin catalog — every `pluginName`, one by one

> 📐 **Field evidence — which plugins are actually used, and how often:** [09-studio-components.md](references/09-studio-components.md) · [10-visual-design.md](references/10-visual-design.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> 📕 **Field-level config reference:** [14a-plugin-config-reference.md](14a-plugin-config-reference.md) documents
> **Every plugin name except `calendar.plugin` and `nct.mailbox.plugin`** at chart-doc depth (those two are covered in THIS doc and in [31](31-email-integration-and-mailbox.md)) — each one's
> **settings panel + editor + JSON config slot + field-by-field
> table**. Use THIS doc (14) as the catalog/overview;
> use **14a** when you need the exact JSON and what every field does to hand-author a node.

## What this is / When to use

This is the **index of every platform plugin**. Each content-tree node
(`branches.json[].rootContent … .children[]`) selects a plugin via the `pluginName` field
(see [01-content-model-and-pages.md](01-content-model-and-pages.md) — the node model). The plugin defines:

1. **how the node renders**,
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

> **Convention for the source of `pluginName`.** Each plugin declares its name once. Two page implementations
> share the one name `siteMapPage`. *(This paragraph used to give exact totals; a census of plugin names drifts between platform builds, and a stale number reads as a promise. Count them in your own build if you need one:
> the platform also declares more plugins than are authored into projects —
> catalogued here only so you recognise them. Two base plugins also appear in tenant exports:
> `html.plugin` and `parsis.plugin`.)*
> The generic content plugins (`nct.html/label/image/…`, `parsis.plugin`, `html.plugin`, `grid.plugin`,
> `tabs.plugin`, …) are the general-purpose ones; the business plugins are application-specific. You never write
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
| `nct.mailbox.plugin` | 1 per mail page (0 in the baseline) | `properties.model` | [31](31-email-integration-and-mailbox.md) |
| `process.table.pluin` *(yes, with the typo)* | 1–2 (console + your process lists) | `properties.model` | [05](05-crud-tree-and-process-table.md) |
| `dynaform.form.plugin` | 1 per form | `properties.formModeIdentifier` (STRING → the form rep-object; no settings/model blob) | [02](02-form-controls-reference.md),[06](06-form-groups-and-mapping.md) |
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
| `dynaform.form.html.field.plugin` | 0 unless an input needs an interaction no stock control has | `properties.settings` (binding + `custom`, the values its settings sections wrote) + `properties.html` / `properties.studioModel` (the component) + `properties.fieldModel` (the value types) | [24e](24e-html-field-control.md) |
| `dynaform.html.field.section.plugin` | 0+ per Html Field — a CHILD of it, one per item of its settings drawer | `name` (title) + `properties.html` / `properties.studioModel` (the section's component) + `properties.sectionModel` (icon, defaults) | [24e](24e-html-field-control.md) §5 |
| `dynaform.filter.form.plugin` | 1 per standalone filter panel | `properties.filterFormModel` | [04](04-crud-table-plugin.md#standalone-filter-form-filter-panel-above-the-table) |
| `dynaform.filter.submit.button.plugin` | 1 per filter panel | `properties.settings` (`{"buttonName":…}`) | [04](04-crud-table-plugin.md#standalone-filter-form-filter-panel-above-the-table) |
| `dynaform.form.groups.landingplugin` | 1 per form-group landing page | — (no settings blob; the form group comes via the `?group=<identifier>` URL parameter) | [06](06-form-groups-and-mapping.md) |
| `dynaform.form.groups.plugin` | 1 (console skeleton) | admin scaffold | [06](06-form-groups-and-mapping.md) |
| `dynaform.context.list.plugin` | 1 (console skeleton) | admin scaffold | [08](08-groovy-rules-and-context.md) |
| `bpmn2modeler.plugin` | 1 (console skeleton) | admin scaffold | [07](07-workflows-and-tasks.md) |
| `workflows.plugin` | 1 (console skeleton) | admin scaffold | [07](07-workflows-and-tasks.md) |
| `processes.plugin` ⚠️ *(dead)* | 1 (console skeleton) | ⚠️ none → `mrjun.plugin.not.found` | [07](07-workflows-and-tasks.md) |
| `processes.selectedplugin` | 1 (console skeleton) | admin scaffold | [07](07-workflows-and-tasks.md) |
| `executor.rule.list.plugin` | 1 (console skeleton) | model `{editorPageContentIdentifier}` (landing = the `executor.rule.script.plugin` editor page) | [08](08-groovy-rules-and-context.md) |
| `executor.rule.script.plugin` | 1 (console skeleton) | — (no model/settings blob; the rule is a rep-object, `?rule=<identifier>`) | [08](08-groovy-rules-and-context.md) |
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
| `pdf.report.plugin` ⚠️ *(dead)* | **0 in the current baseline** (the `reports` demo page is gone) | ⚠️ none → `mrjun.plugin.not.found` | [15](15-pdf-and-mail.md),[01](01-content-model-and-pages.md) |
| `pdf.report.page.plugin` ⚠️ *(dead)* | **0 in the current baseline** | ⚠️ none → `mrjun.plugin.not.found` | [15](15-pdf-and-mail.md),[01](01-content-model-and-pages.md) |
| `site.header.plugin` | 1 per page (site chrome) | — (site chrome) | below |
| `site.footer.plugin` | 1 per page (site chrome) | — (site chrome) | below |
| `site.kicker.plugin` | 1 per page (site chrome) | `properties.modelGroups` when `id=left-nav` (quick-links tree); else — (site chrome) | [17](17-left-nav-quick-links.md), below |
| `site.right.kicker.plugin` | 1 per page (site chrome) | `properties.showFromNonAuthMode` (BOOLEAN, default true → set `false` to hide the right drawer for non-authoring visitors) | below |
| `site.breadcrumb.plugin` | 1 per page (site chrome) | — (site chrome) | below |

> **`calendar.plugin` — the one authorable plugin these docs do not yet cover field-by-field.** Config slot
> `properties.model`. It binds to ONE CRUD (`contextIdentifier` + `crudAlias`) and
> fetches through an EXECUTION find rule (`findRuleIdentifier`, or `findMethodName` on the CRUD); the visible
> date window arrives in the rule's `attrs` as `rangeStart`/`rangeEnd`. Rows become events through a field
> mapping (`titleField`, `startField`, `endField`, `allDayField`, `colorField`, `locationField`,
> `descriptionField`), and `createActions`/`editActions` are the same action-set shape as on the
> table ([04](04-crud-table-plugin.md)). Presentation: `initialView`, `firstDay`, `slotMinTime`/`slotMaxTime`,
> `showWeekends`. If a PRD asks for appointments/bookings/shifts, evaluate this before hand-building a table or
> an HTML component; check the field names against your platform build before you rely on them.

> **`nct.mailbox.plugin` — a mail client on a page.** Config slot `properties.model`, field-by-field in
> [31 §6](31-email-integration-and-mailbox.md). Three panes (accounts and folders, the list, the reading
> pane) over the mailboxes the project has connected. It renders correctly with an **empty** config — every
> setting takes something away rather than being the price of a first render — so a page can be authored
> before anybody has connected an account. ⛔ The accounts themselves are **not** in the export; they are
> configured live after import, which also means `accountIds` can only be narrowed once ids exist. One per
> page: it is a workplace, not a widget.

**Plugins that exist in the platform but do NOT appear in any project export**
(these are platform/admin-application nodes; you do **not** author them by hand):
`admin.organizations.plugin`, `admin.projects.plugin`, `admin.integrations.list.plugin`,
`discovery.plugin`, `project.template.management.plugin`, `grid.plugin`, `html.localized.plugin`,
`nct.link.plugin`, `admin.dashboard.*`,
`admin.createsite.*`, `mrjun.plugin.not.found`, `mrjun.empty.plugin`. Check any of them the same
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
| Config slot | `properties.html.stringValue` (type `STRING`) |
| Extra props | `editorWidth` (default `"100%"`), `editorHeight` (default `"700px"`), `reuseItems` (bool, default `false`); plus `className`, `styleName`, `tagProperties`. **Not `isParsis`** — that is a marker set on `nct.parsis.plugin` nodes (§1.2), not an html-plugin prop. |
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
child content node**. The parsing works like this:

- the body is parsed as HTML wrapped in a `<div>`;
- all `<plugin>` tags are collected;
- only the **top-level** `<plugin>` tags are taken (not those nested inside another `<plugin>`);
- the attributes `id`, `name` (= the child's `pluginName`), `vp` (virtual-plugin id) are read;
- direct child `<property>` / `<prop>` tags → the child's properties;
- direct child `<behavior>` tags → behaviour nodes;
- each property tag contributes `name` + `type` (default `STRING`) + `value`;
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
   > tag→child by `child.identifier == <plugin id>` (an exact match on the identifier).
   > If the child identifier does not equal the tag id, the platform auto-creates a **blank** child with
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
| Config slot | — (no JSON config; the config = **children**) |
| Props | **Shared by BOTH `parsis.plugin` and `nct.parsis.plugin`**: `minHeight`, `style`, `emptyPlaceholder`, `reuseItems`; plus `isParsis:true`, `className`, `styleName`, `tagProperties`. `nct.parsis.plugin` adds only **behavior** (role-aware editing, drag sources, move-confirm) + `hideInKicker=true` — **no** new config props (`emptyPlaceholder`/`minHeight`/`style` are NOT nct.parsis-only). |

Parsis is a **container slot**: it shows nothing itself, but renders its `children[]` (each one a plugin).
In authoring, plugins are "dropped" into it via drag-and-drop. `nct.parsis.plugin` is the platform-UI variant of
`parsis.plugin`; it has the **same** property set, so the config surface is **identical** — it adds
only authoring behaviour (editing takes the `ADMIN`/`NCT_AUTHOR` role into account, drag sources,
move-confirm) and `hideInKicker=true`. **`properties.isParsis` = `true`** distinguishes a
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
| Config slot | `properties.html.stringValue` |
| Role | **the top-level layout of every page**: header/sidebar/footer/parsis slot |

The same mechanism as `nct.html.plugin`, but this is the **base plugin**.
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
| Slot | named props: `text` (LOCALIZED), `tagName`, `className`, `styleName`, `tagProperties` |

`text` is a localized string (`localizedStringValue`) **emitted as raw HTML** (unescaped — you may embed inline
markup). `tagName` is the wrapper HTML tag, from a fixed dropdown set
**`[h1,h2,h3,h4,h5,h6,p,span,i,label,small]`** — **`div` is NOT an
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
| Slot | named props: `url`, `description`, `tooltip`, `width` (INTEGER, **default 400**), `height` (INTEGER, **default 250**) — ⚠️ **neither reaches the rendered `<img>`**, see below — `className`, `styleName`, `tagProperties` |

`url` supports the `abs(...)` macro (absolute path to a template resource). **In an export the `url` is stored
TENANT-STRIPPED** (stripped on save, re-prefixed with the
importing tenant on render) — which is why an export's image `url` carries no realm/tenant prefix and
ports cleanly; the actual image file lives in the project's file storage (`tenant-files/`), so a ported project needs the
file present. `width`/`height` (INTEGER, defaults 400 / 250) are **NOT applied to the rendered `<img>`** — the platform
ignores them there. They are read only to size the
placeholder image shown when `url` is unset, and to seed the gallery editor's dimension config. **To size an image use
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

### Different image per theme (`perTheme`, `urlByTheme`)

For an image that cannot work on every skin — typically a logo drawn for a light background that vanishes on the
dark ones — the image can carry its own version per theme. Two optional props; **both absent = the image behaves
exactly as above** (every image made before the option existed is in that state):

| Prop | Type | Meaning |
|---|---|---|
| `perTheme` | BOOLEAN | The editor's **"Different image per theme"** switch. Absent / `false` → `url` under every skin. |
| `urlByTheme` | STRING holding a JSON object | Skin name → image path. Keys are the **exact** skin names (`Standard`, `Dracula`, `Forest`, `Dark`, `Dark Blue` — doc [24a](24a-theming-and-dark-mode.md)); paths follow the same rules as `url` (tenant-stripped, file in `tenant-files/`). |

- A skin with **no entry shows `url`** — `url` is the default, so give your own entries only to the skins that need
  them (usually the light `Standard`, or the four dark ones).
- `perTheme:false` with a filled `urlByTheme` is legal: the entries are **kept but ignored** (the author switched the
  option off; switching it back on restores them).
- The theme switch in the header changes skin **without reloading the page**; a per-theme image follows it on the
  spot, so nothing else is needed.
- Every version is cropped to the same `width`×`height`, so the layout does not move when the theme changes.

```json
{ "pluginName": "nct.image.plugin", "name": "logo-plugin",
  "properties": {
    "url":        { "key":"url", "propertyType":"STRING", "stringValue":"images/logo-dark-ink.png" },
    "perTheme":   { "key":"perTheme", "propertyType":"BOOLEAN", "booleanValue":true },
    "urlByTheme": { "key":"urlByTheme", "propertyType":"STRING",
                    "stringValue":"{\"Dracula\":\"images/logo-light-ink.png\",\"Forest\":\"images/logo-light-ink.png\",\"Dark\":\"images/logo-light-ink.png\",\"Dark Blue\":\"images/logo-light-ink.png\"}" }
  } }
```

⛔ Do **not** solve a light/dark logo with a `byTheme` CSS block or two image nodes toggled by CSS: these props are
the supported way, and they are what the image editor shows and edits.

**In the editor:** the switch sits above the gallery; when on, a row of slots appears — *Default* plus one per
theme, each drawn on that theme's own background so the author sees at once where the default does not read. Pick a
slot, then pick / upload / crop an image (or press the upload button on the slot itself); it goes to that slot, the
editor stays open and the gallery lists the new upload. "×" on a slot sends that theme back to the default.

## 1.6 · `nct.link.plugin` — link · `nct.label.link.plugin` — link with a caption

| | |
|---|---|
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
resolved by identifier; **NOT** the link node's own uuid, and
honoured **only** when `internal:true`. For an external link set `internal:false` and put the URL in the `link`
LOCALIZED_STRING; `identifier` is then ignored). The base plugins are `link.plugin` and
`localized.link.label.plugin`.

## 1.7 · `nct.help.plugin` — help icon with a message

| | |
|---|---|
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
to the right of the field caption.

## 1.8 · `nct.tab.plugin` / `tabs.plugin` — tabs

| | |
|---|---|
| Slot | `properties.tabModel.stringValue` (JSON) |

`nct.tab.plugin` is the platform tab set; `tabs.plugin` is the base one (in real projects only
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
> `size` is `BIG`/`SMALL`. **Every path that is not an explicit `"SMALL"` lands on
> `BIG`:** the default is `BIG` *and*
> a null `size` is read as `BIG`. So a hand-authored `tabModel` that simply omits
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
> button), so an author can see and change it after the fact; the point of the
> rule is not to make them.
> **Which tab opens.** `?tab=<tab id | name>` in the URL (or `?tab.<tab-set identifier>=…` for one set), else the
> session's last tab on this node, else the first by `order`. The session remembers the tab per tab-set node, not per
> record, so every navigation that lands on a record page should name its tab (`…?id=<id>&tab=<tabId>`). Full rules —
> [14a](14a-plugin-config-reference.md) §`nct.tab.plugin`.

Extra node props: `showCard` (bool), `isParsis`, `className`, `styleName`. **Two same-type tables (e.g. two
`crud.table.plugin`) SHOULD be split across tabs — one per tab pane** — never stacked in one parsis (§2.3).
Each tab's content lives in a child `nct.parsis.plugin` node whose **`identifier` AND `name` MUST equal that
tab's `tabModel.items[].id`**. The tab body is resolved as the child `nct.parsis.plugin` node matched on
`child.identifier == item.id`. **Order is irrelevant — the identifier match
is load-bearing, NOT the count/order**: in the shipped `erp` sample the child parsis are often in a different order than
the items (Stock/Stock-Movement/Lot node: items `5b7fd1bc,7af19caa,22ae6ae8` but children `7af19caa,5b7fd1bc,
22ae6ae8`) yet each identifier still matches. So: create N child parsis, one per item, each `identifier` == `name`
== its item id; put the tab's business plugin (crud table/form/chart) **inside** that matching parsis.

> ⛔ **This is the ONE place the general "mint a fresh `identifier`/`uniqueIdentifier`" rule (§1.1) does NOT
> apply to a tab child.** Mint a fresh `uniqueIdentifier` only — the `identifier` MUST reuse the tab item id
> verbatim. If identifiers do not match, at first render the platform auto-creates a blank parsis
> per tab and orphans your content, so **every tab renders EMPTY** (same mechanism as §2.4's grid cells).
> `mrjun.py validate` only WARNs on a mismatch — it does NOT error — so this passes a 0-error validate;
> **live-render and confirm each tab pane is populated.**

Other props: see `erp` (`children`=3 with 3 items, each child `identifier` == its item id).

## 1.9 · `grid.plugin` — grid layout (mrjun)

| | |
|---|---|
| Slot | `properties.model.stringValue` |

The model is a grid of rows/columns, each cell rendering
a `parsis.plugin` as a nested slot (id `"el" + index`).
**Does not appear in project exports** — in practice the layout is done via `nct.html.plugin`
(flex/grid CSS) + parsis slots (see 1.1). If needed — the config is in `properties.model.stringValue`.

## 1.10 · `html.localized.plugin` — localized HTML (mrjun)

| | |
|---|---|
| Slot | `properties.html` (LOCALIZED — html per locale) |

The same as `html.plugin`, but `html` is a localized string (different HTML per locale). **Does not appear
in practice** — instead individual `text`/`label` properties are localized. Related mrjun plugins:
`localized.rich.text.plugin`, `header.plugin`/
`localized.header.plugin` — also platform-level, absent from project
exports.

## 1.11 · `global.replacement.plugin` — global $$-replacements

| | |
|---|---|
| Slot | — (no content blob; the editor edits query parameters) |

> **Catalog stub.** The page **filter bar** — full params + filtering-through-params + click-to-cross-filter
> recipe → **[22 §4-§5](22-charts-params-and-filters.md)**.

The page-wide **filter bar**: it stores no configuration of its own and builds one control per distinct SQL
parameter declared by the QUERY replacements of the charts on the same page ([22 §4](22-charts-params-and-filters.md)).
This is **not** a plugin with a config blob: in an export its `properties` are only `className/styleName/tagProperties`
(there is no `Javascript`/`model`/`settings` key on it). The plugin does not write
into any content slot — instead its form edits query parameters and on submit notifies the
charts whose queries are affected. So this is a
behaviour/admin editor of query parameters, not a persist into content-Javascript. One per dashboard page that
has a filter bar.

---

# Group 2 · Action / visual plugins

## 2.1 · `action.button.plugin` — standalone action button

| | |
|---|---|
| Settings key | the per-locale button label is persisted in `settings` as **`localizedLabels`** (`{locale → label}`) |
| Config slot | `properties.settings.stringValue` (JSON) |
| Group | `Form Controls` (it is a form control, but a standalone one — not bound to a CRUD field) |

A button that on click **runs an EXECUTION rule** (`ruleIdentifier`) and, optionally, refreshes the
listed components (`refreshTargets`). Unlike crud-table actions (which open a formGroup, see
[04](04-crud-table-plugin.md)), this is a standalone button on a page/in a form.

> ⚠️ **The rule sees CRUD/context data only INSIDE a form.** The button resolves its rule context from the nearest
> form ancestor: inside a `dynaform.form.plugin` the rule runs against the **form's full
> `contextData`** (CRUD row + context attrs, folding in live edits); a **standalone** action button (no form
> ancestor) runs with an **empty context data** — `context.<ctx>.<crud>.data.get()` is empty, only globals /
> `service.*` calls work. Put the button inside the form when its rule needs the row.

Real node (`erp`, the only instance — "Pull from PO"):

```json
{ "pluginName": "action.button.plugin", "name": "Action Button",
  "properties": { "settings": { "key":"settings", "propertyType":"STRING", "stringValue":
    "{\"localizedLabels\":{\"en_US\":\"Pull from PO\",\"ru_RU\":\"Забрать из PO\",\"hy_AM\":\"Քաշեք պատվերի կետից\"},\"ruleIdentifier\":\"14265d38-d7e4-4300-82cf-38aad872a9d4\",\"variant\":\"PRIMARY\",\"outline\":false,\"gradient\":false,\"shadow\":false,\"size\":\"DEFAULT\",\"shape\":\"DEFAULT\",\"wide\":true,\"iconOnly\":false,\"submitForm\":false,\"showWaitIcon\":false,\"refreshTargets\":\"526ac33a-8e73-4d3e-a31a-78db09252e99\"}"
  } } }
```

The `settings` fields:

| Field · type | Value · default | Meaning |
|---|---|---|
| `localizedLabels` · Map<locale,String> | — | the button caption per locale (`en_US`/`ru_RU`/…) |
| `iconClass` · String | null | Pe-7s icon CSS class (e.g. `pe-7s-rocket`); empty → no icon |
| `ruleIdentifier` · String | — | **the identifier of the EXECUTION rule**, run on click ([08](08-groovy-rules-and-context.md)) |
| `variant` · enum | `PRIMARY` | `PRIMARY,SECONDARY,SUCCESS,INFO,WARNING,DANGER,LIGHT,DARK,LINK,ALTERNATE,FOCUS` |
| `outline` · bool | `false` | outline button |
| `gradient` · bool | `false` | gradient |
| `shadow` · bool | `false` | shadow |
| `size` · enum | `DEFAULT` | `DEFAULT("")`, `SM("btn-sm")`, `LG("btn-lg")` |
| `shape` · enum | `DEFAULT` | `DEFAULT("")`, `PILL("btn-pill")`, `SQUARE("btn-square")` |
| `wide` · bool | `false` | `btn-wide` |
| `iconOnly` · bool | `false` | icon only |
| `submitForm` · bool | `false` | if inside a form — submits the form before the rule |
| `showWaitIcon` · bool | `false` | a spinner on the button during the click (attribute `icon-wait="true"`) |
| `blockSelector` · String | null | CSS selector whose elements are blocked by an overlay for the duration of the action |
| `refreshTargets` · String | null | CSV of `uniqueIdentifier`s of refreshable components, re-rendered after the rule |

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
| Config slot | `properties.Javascript.stringValue` (JSON) — **not `model`, not `settings`**, but the named property `Javascript` |
| Group | `Reporting` |

> **Catalog stub.** Full recipe — the chart-model / replacement schema, `$$('name', default, 'Type')`
> data binding, `QUERY`/`LABEL` strategy, query params, the `global.replacement` filter bar, click-to-cross-filter,
> and theme-safe rendering — is in **[22-charts-params-and-filters.md](22-charts-params-and-filters.md)**.

A universal "block with HTML + JS + data". Despite the name, this is **not only charts** — it is any
custom widget: an HTML template + JS logic + `replacements` (data from SQL queries). It is the most frequent
business plugin in a real project. The model: `id`, `js`, `html`, `css`, `schedule`,
`replacements` (a list).

**Data binding** goes through `replacements`: the JS accesses the data via `$$('name', default, 'Type')`, and
each `replacement` is bound to a saved `query` (`queryIdentifier` + an embedded **MINIMAL 12-field**
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
> fields** — `{id, identifier, realmName, clientName, name, query, sourceIdentifier, offset,
> itemsPerPage, parameters, attributes:{}, aggregations:{aggregations:[],groupByList:[],orderByList:[]}}`
> (`aggregations`=`[]` not null, `attributes`=`{}`). **Do NOT paste the 21-field saved-query rep-object from
> `rep-objects.queries[]`** — its rep-metadata (`creationTime`/`modificationTime`/`errors`/`message`/`hidden`/
> `schedule`/`lastScheduledTime`/`statementTimeoutSeconds`/`wrapInPaging`) fails parsing of the chart model,
> which the platform silently swallows into an empty model → **the chart renders EMPTY as a "Modify
> html" cell** while import stays clean. See [22-charts-params-and-filters.md](22-charts-params-and-filters.md)
> §embedded-query.

Key chart-model fields:

| Field · type | Meaning |
|---|---|
| `id` · String | the chart model's uuid |
| `html` · String | the widget's HTML template (with `<style>`, the `.collapsible`, `.content` classes, …) |
| `js` · String | JS: `this.$find('.sel')`, `this.$component()`, data access via `$$('name', default, 'Type')` |
| `css` · String | LEGACY single CSS block; still honoured (read as `cssByTheme["*"]`) |
| `cssByTheme` · Map | **per-theme CSS**, key `"*"` or an exact skin name. Editor: the **Css** tab. Only `"*"` + the active skin are emitted, each **scoped** to the chart instance -- so unlike a `<style>` inside `html` (which is GLOBAL) it cannot leak onto other charts. See [24a](24a-theming-and-dark-mode.md) |
| `schedule` · object | the recompute schedule (usually empty) |
| `replacements[]` · list | data bindings (see below) |

Replacement fields: `name`, `group` (the `$$(...)` call itself), `type` (`Integer[]`/`String[]`/…),
`replaceStrategy` (`LABEL`/…), `queryIdentifier` (**+ a MINIMAL 12-field copy of the query in `query`** — ONLY
`{id, identifier, realmName, clientName, name, query, sourceIdentifier, offset, itemsPerPage, parameters,
attributes:{}, aggregations:{aggregations:[],groupByList:[],orderByList:[]}}`; **do NOT paste the 21-field saved-query
rep-object from `rep-objects.queries[]`** — its rep-metadata `creationTime/modificationTime/errors/message/hidden/
schedule/lastScheduledTime/statementTimeoutSeconds/wrapInPaging` fails parsing of the chart model, which
the platform silently swallows → the chart renders EMPTY as a "Modify html" cell; see doc 22
§embedded-query), `defaultValue`, `columnName`, `order`, `maxItemsCount`, `futureReplacements[]`.

**"Chart types"**: the chart type is not a model field — it is a consequence of which JS library the
`js` calls (Chart.js/Plotly/**ECharts**/arbitrary DOM — those, plus `chartjs-adapter-date-fns` and mermaid, are the libs the plugin injects; ApexCharts is **not** loaded here). The model stores only html+js+data; the chart type
is determined by the code in `js`.

### How to create from scratch
1. Save an SQL query → `rep-objects.queries[]` (see [12](12-queries-sources-schedulers-and-rest.md)),
   and remember its `identifier`.
2. Node `pluginName:"chart.js.plugin"`; into `properties.Javascript.stringValue` put the JSON chart model:
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

- Its **Settings panel** is registered under a constant nav name — `"CRUD Table Settings"`.
  The right-nav registry **dedupes by (name, tabName)**, so a second instance's
  registration **evicts the first** — only ONE settings panel survives (last-rendered wins).
- Its **live-sync channel** is a constant key — `"CrudTableSynced"`. Every
  instance subscribes; updates are broadcast page-wide and the listener applies the new model
  **unconditionally on every instance**.
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
`global.replacement.plugin` mechanism), never on `onFilterSubmit`. So a filter bar on a
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

These are parts of the site layout, embedded into `html.plugin` via `<plugin>` (see 1.3). None has a user JSON config; the only setup is `className`/`styleName` (passed in from
the `<property>` in the layout HTML). **All are scaffold, not created by hand** (cloned by the page template).

| `pluginName` | Purpose |
|---|---|
| `site.header.plugin` | the page's top header |
| `site.footer.plugin` | footer (`editBorderSelector=".app-footer__inner"`) |
| `site.kicker.plugin` | the left navigation sidebar (site menu); quick-links tree in `properties.modelGroups` — see [17-left-nav-quick-links.md](17-left-nav-quick-links.md) |
| `site.right.kicker.plugin` | the right slide-out panel (drawer) |
| `site.breadcrumb.plugin` | breadcrumbs |

`footer`/`kicker`/`right-kicker` have `hideInKicker=true`; `header` — `hideInKicker=false`;
`breadcrumb` does not set the attribute (default `false`). They are configured via `<property name="className" value="…">`
in the layout HTML — for example `site.header.plugin` gets `className="app-header__content"`, and
`site.right.kicker.plugin` — `className="app-drawer-wrapper"` (see the example in 1.3).

`siteMapPage` (the page node) — see it separately below (it is not chrome, but the page container itself).

---

# Group 4 · `siteMapPage` — the page

| | |
|---|---|
| Variants | two page implementations, one per page template (`ARCHITECTUI_HTML_PRO` and `RAVEN`) — **both** share the name `siteMapPage` |
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

| Admin page (name) | `pluginName` inside | What it does | In depth |
|---|---|---|---|
| User management | `admin.user.management.plugin` | managing project users | — |
| Role Management | `admin.rolegroup.management.plugin` | role groups | [12](12-queries-sources-schedulers-and-rest.md) |
| Sources | `admin.sources.plugin` | DB sources (rep-objects.sources) | [12](12-queries-sources-schedulers-and-rest.md) |
| Schedulers | `admin.schedulers.plugin` | schedulers | [12](12-queries-sources-schedulers-and-rest.md) |
| Queries (list) | `admin.queries.plugin` | the list of saved queries | [12](12-queries-sources-schedulers-and-rest.md) |
| Queries (editor) | `admin.query.plugin` | the editor for a single query | [12](12-queries-sources-schedulers-and-rest.md) |
| Queries (results) | `query.results.plugin` | the query results table | [12](12-queries-sources-schedulers-and-rest.md) |
| Settings | `project.settings.plugin` | project settings (rep-objects.settings) | [12](12-queries-sources-schedulers-and-rest.md) |
| Audit Logs | `audit.log.list.plugin` | the audit log | — |
| Profile | `user.profile.plugin` | the current user's profile | — |
| ~~Ontology~~ *(page removed from the baseline)* | `ontology.viewer.plugin` | ontology viewer — **no config slot** (empty properties: `className`/`styleName`/`tagProperties`); the plugin never reads `properties.model` | — |
| Contexts | `dynaform.context.list.plugin` | the list of contexts | [08](08-groovy-rules-and-context.md) |
| Rules (list) | `executor.rule.list.plugin` | the list of rules | [08](08-groovy-rules-and-context.md) |
| Rules (editor) | `executor.rule.script.plugin` | the rule script editor (no model/settings blob; the rule is a rep-object, resolved via `?rule=<identifier>`) | [08](08-groovy-rules-and-context.md) |
| Form Groups | `dynaform.form.groups.plugin` | the list of form groups | [06](06-form-groups-and-mapping.md) |
| Processes (list) ⚠️ | `processes.plugin` | ⚠️ **dead/legacy** — the process list was merged into the single master-detail `processes.selectedplugin`; the baseline node renders as `mrjun.plugin.not.found`. Leave it alone; author new process screens with `processes.selectedplugin` or `process.table.pluin` | [07](07-workflows-and-tasks.md) |
| Processes | `processes.selectedplugin` | the whole Processes screen: one self-contained master-detail panel — process list on the left, process detail on the right | [07](07-workflows-and-tasks.md) |
| Workflows | `workflows.plugin` | the list of workflows | [07](07-workflows-and-tasks.md) |
| Workflows (BPMN) | `bpmn2modeler.plugin` | the BPMN2 modeler | [07](07-workflows-and-tasks.md) |
| Database | `database.management.plugin` | DB schema management (`properties.model`) | [10](10-database-management.md) |
| Business Logic | `dynamic.cruds.plugin` | dynamic CRUD / business logic (`properties.model`) | [11](11-business-logic-dynamic-crud.md) |
| Mail Templates | `messaging.mail.templates.plugin` | mail-template **management scaffold** — the node carries **no** `properties.model` (properties = `className`/`styleName`/`tagProperties` only); the templates live in `rep-objects.mailTemplates[]` (see [15]) | [12](12-queries-sources-schedulers-and-rest.md),[15](15-pdf-and-mail.md) |
| Pdf Templates | `report.pdf.templates.plugin` | PDF-template **management scaffold** — the node carries **no** `properties.model` (properties = `className`/`styleName`/`tagProperties` only); the templates live in `rep-objects.pdfTemplates[]` (see [15]) | [15](15-pdf-and-mail.md) |
| ~~Branches~~ *(page removed from the baseline)* | `process.table.pluin` | the branches table (reused the process table) | [05](05-crud-tree-and-process-table.md) |
| ~~reports~~ ⚠️ *(page removed from the baseline)* | `pdf.report.plugin`, `pdf.report.page.plugin` | ⚠️ **dead/legacy** — render as `mrjun.plugin.not.found`; for PDFs use `report.pdf.templates.plugin` | [15](15-pdf-and-mail.md),[01](01-content-model-and-pages.md) |

> ⚠️ **`pdf.report.plugin` / `pdf.report.page.plugin` are orphan/dead — do NOT author new nodes with them.**
> They appeared once each in OLDER project exports (a `Home → reports → Pdf → html.plugin →
> pdf.report.plugin → pdf.report.page.plugin` subtree) and are **absent from the current baseline**, but
> **the platform no longer registers either name**, so they render as `mrjun.plugin.not.found` (registry
> miss). The live PDF plugin is **`report.pdf.templates.plugin`**; write new PDF nodes
> under it. Same fact in [01-content-model-and-pages.md](01-content-model-and-pages.md) (the legacy-PDF-pair note) and
> [15-pdf-and-mail.md](15-pdf-and-mail.md).
>
> ⚠️ **`processes.plugin` is orphan/dead in the same way — do NOT author new nodes with it.** The Workflows-console
> process **list** was merged into the single master-detail `processes.selectedplugin`, and the platform no longer registers
> `processes.plugin`, so the one node every baseline inherits renders as
> `mrjun.plugin.not.found` next to the working Processes panel. Leave the inherited node where it is (removing it is
> a cosmetic change, not a fix you owe anyone); for a process list of your own use `processes.selectedplugin` or the
> live `process.table.pluin` ([05](05-crud-tree-and-process-table.md)).
>
> **One** plugin carries a `properties.model` whose shape is documented **nowhere**: `discovery.plugin`
> (it genuinely reads `properties.model`) — in the
> absent-table below, an admin scaffold that never appears in a project export and is **not hand-authored**, so no construction recipe exists; if
> ever needed, its model shape would have to be established first. (`ontology.viewer.plugin` does **not** carry a
> model — it never reads `properties`; it renders as
> an empty admin scaffold. It appeared once in older exports and is absent from the current baseline.)

**Plugins known to the platform that are absent from project exports** (platform-level — they belong to the
admin application/orgs, not the project; so they are not written into a project export):

| `pluginName` | Purpose | Status |
|---|---|---|
| `admin.organizations.plugin` | managing organizations (cross-project level) | scaffold, **never** in a project export |
| `admin.projects.plugin` | managing projects | scaffold, **0** |
| `admin.integrations.list.plugin` | the list of integrations | scaffold, **0** |
| `admin.localization.plugin` | localization | scaffold, **0** |
| `project.template.management.plugin` | template management | scaffold, **0** |
| `discovery.plugin` | Customer Discovery (carries a `properties.model`) | scaffold, **0** |

All six have no project config. If such a node
does appear, it comes from the platform template, not authored into a project export.

---

## Gotchas

1. **The config slot is plugin-dependent — there is no single rule.** form controls → `settings`; table/tree/
   process/db/dynamic-cruds → `model`; **chart → `Javascript`**; html/nct-html → `html`; tab → `tabModel`;
   help → `helpSettings`; label → `text`; image → `url`+props; siteMapPage → top-level props. Separately:
   `rule-script`/landing/form-plugin/`global.replacement`/`list.item` have **no config blob at all** — their
   object comes as a rep-object via a URL parameter (`?rule=`, `?group=`, `formModeIdentifier`) or it is a
   container/behaviour editor (`global.replacement` edits query parameters). Do not write the crud config into
   `settings`, the chart config into `model`, and do not invent a `model`/`Javascript` slot where there is none
   (the tooling flags it as "settings-vs-model misuse").
2. **`process.table.pluin` is a real typo.** Do not "fix" it —
   the import will break. The tooling deliberately preserves it (`validate` catches `process.table.pluin` typo altered).
3. **A `<plugin>` in html is not text but child nodes.** Each top-level `<plugin id name>` inside
   `nct.html.plugin`/`html.plugin` spawns a **real content node**. Nested `<plugin>` (inside another
   `<plugin>`) are ignored at the top level. This means: for a plugin from the html to actually render,
   the corresponding child content node must exist **and its `identifier` must equal the `<plugin id>`** (the match
   is an exact `identifier` equality — not by `name`, not by count/order; §1.1 step 3). A fresh-uuid
   child never matches → a blank child is auto-created and your plugin is orphaned (renders empty, import clean).
4. **Site chrome and layout are scaffold.** The `html.plugin` layout, the `site.*` plugins and the root parsis are cloned
   at `page add`. Do not assemble them by hand — use `mrjun.py page add`.
5. **The admin pages are already in empty.** 24+ `siteMapPage` nodes with admin plugins are part of the empty scaffold. Keep
   them unchanged; append business pages next to them.
6. **`nct.parsis.plugin` vs `parsis.plugin`.** The former is the platform-UI variant of the latter; both are drop containers
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
