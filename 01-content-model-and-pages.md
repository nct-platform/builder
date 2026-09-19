# 01 — Content tree, pages, tabs, layout, access

> 📐 **Field evidence — the page and nav shapes production converged on:** [01-solution-shapes.md](references/01-solution-shapes.md) · [02-navigation-and-front-door.md](references/02-navigation-and-front-door.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> Siblings: [00-export-format-and-import.md](00-export-format-and-import.md) ·
> [02-form-controls-reference.md](02-form-controls-reference.md) ·
> [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) ·
> [04-crud-table-plugin.md](04-crud-table-plugin.md) ·
> [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) ·
> [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) ·
> [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)

> **About the component names below.** Claims are stated as behaviour you can observe in a running project or
> in the export JSON; class names are given only so you can ask the platform team a precise question. Two
> families of names appear: `mrjun-*` components belong to the **mrjun CMS library** (the content/page/plugin
> engine the platform embeds), `nct-*` components belong to the **Dokie application** on top of it. That split
> matters when you report a bug — it tells the platform team which side owns the behaviour. Export shapes
> below are stated as they appear in real exported projects; you can confirm every one of them with `jq`
> against your own export.

## What it is / when to use

Each project is **one content tree** (`branches.json[0].rootContent`), a recursive structure of
`ContentDomain` nodes. Each node is a "plugin": `pluginName` selects the Java class, and all configuration
lives in `properties` (typed slots). Pages (`siteMapPage`), tabs (`nct.tab.plugin`), grids
(`nct.html.plugin`/`html.plugin`), texts (`nct.label.plugin`), images (`nct.image.plugin`), and content
"holes" (`nct.parsis.plugin`, `parsis.plugin`) — all of these are nodes of one tree. CRUD tables, forms, filters —
also nodes, just with a different `pluginName` (see [04-crud-table-plugin.md](04-crud-table-plugin.md),
[02-form-controls-reference.md](02-form-controls-reference.md)).

**This is the skeleton on which every page is built.** Before placing a CRUD table or form, you need to:
create a `siteMapPage` → put an `html.plugin` (layout) into its `parsis` → inside the layout, in the
`nct.parsis.plugin` (`id="parsis"`), place the business plugins. This document describes exactly these "pipes".

Read this doc when you need to **manually add a page, tab, column grid, set access
(public/authenticated/roles), hide content, or assemble a layout from HTML + `<plugin>` tags**.

> **🔧 Tooling.** For these entities, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `tree`, `find --plugin <n>`, `show node <id>`, `page add/rm`, `node add/rm`, `roleaccess show/set`.
> Full index and rules — [`tools/README.md`](tools/README.md); before re-import — `mrjun.py validate`.

---

## ⛔ `identifier` vs `uniqueIdentifier` — read this before you reference a node

Two id fields on every node. They are **not** interchangeable, and swapping them fails
**silently** — no exception, no log line, just an empty panel or a "not found" from a tool.
This is the most expensive confusion in the whole content model, so it is stated here with
the source that decides it.

| | `identifier` | `uniqueIdentifier` |
|---|---|---|
| **Scope** | unique **only among one parent's children** | unique **across the entire project** |
| **Shape** | a UUID **or a plain string** (`"parsis"`, `"header"`, `"left-nav"`) | always a UUID |
| **Who sets it** | **you** — it is the `id=` you type in `<plugin id="…">` | the platform (`@PrePersist`), or you by hand |
| **Column** | `s_identifier` — no NOT NULL, no unique constraint | `content_unique_identifier` — **`nullable = false`** |
| **Getter** | `getIdentifier()` **lazily mints a random UUID** when null | `getUniqueIdentifier()` returns the field as-is, never generates |
| **Referenced by** | `<plugin id=…>` tags · a form's `contentIdentifier` · a form group's `contentPageIdentifier` | MCP `nct_ui_*` content lookups · `componentIdentifier` refresh targets · Hidden-Content `contentIdentifiers` · the settings-mirror `name` |

### The code that decides it

`<plugin id="X" name="nct.parsis.plugin">` in a layout's HTML is parsed by
`AbstractHtmlPlugin.constructListModel` (`mrjun-cms-view/.../html/AbstractHtmlPlugin.java`):

```java
String id = plugin.attr("id");                     // the id you typed
ListModel.createPlugin(id, name, vpId, props, behaviors);
```

and resolved by `PluginUtils.getOrCreateChildContent`
(`mrjun-cms-view/.../kicker/utils/PluginUtils.java`) — note the parameter is literally
named `identifier`, and the search set is **this parent's children only**:

```java
private ContentDomain getOrCreateChildContent(..., String identifier, ...) {
    Set<ContentDomain> parsisContents = parent.getChildren();      // ← scope: ONE html plugin
    for (ContentDomain child : parsisContents) {
        if (Objects.equals(child.getIdentifier(), identifier)) {   // ← matched on identifier
            ...
            return child;
        }
    }
    ContentDomain contant = ...;
    contant.setIdentifier(identifier);
    contant.setName(identifier);                                   // ← name == identifier on creation
    ...
}
```

So: **the `id` in your markup IS the child's `identifier`, and it only has to be unique
inside that one html plugin.** That is why `"header"`, `"parsis"` and `"left-nav"` legitimately
repeat on every page in the tree.

> Because auto-created children get `name == identifier`, some tooling matches slots by
> `name`/`alias` instead — e.g. `ContentMcpTools.resolveParsisSlots` (`nct-ui`) indexes
> parsis children by name and alias and reports `parsisSlots: {slotId → uniqueIdentifier}`.
> That map is the bridge between the two worlds: **key = what you write in HTML, value = what
> the MCP tools want.**

### Measured on a delivered project (3 809 content nodes)

```
uniqueIdentifier : 3 809 nodes → 3 809 distinct values, 0 duplicates
identifier       : 3 809 nodes → only 1 952 distinct values
                   left-nav ×154 · logo-plugin ×154 · footer ×153 · breadcrumb ×153
                   header ×153 · right-kicker ×153 · parsis ×152 · siteMapPageParsis ×151
                   form-label ×124 · field ×123 …
identifier among children of ONE parent : 0 collisions
```

Reproduce it on any unpacked export:

```python
import json, collections
d = json.load(open('work/branches.json')); nodes = []
def walk(n):
    if isinstance(n, dict):
        if 'pluginName' in n and ('uniqueIdentifier' in n or 'identifier' in n):
            nodes.append(n)
            for c in (n.get('children') or []): walk(c)
        else:
            for v in n.values(): walk(v)
    elif isinstance(n, list):
        for v in n: walk(v)
walk(d)
uid   = collections.Counter(n.get('uniqueIdentifier') for n in nodes if n.get('uniqueIdentifier'))
ident = collections.Counter(n.get('identifier')       for n in nodes if n.get('identifier'))
print('uid  dups:', {k: v for k, v in uid.items()   if v > 1})          # expect {}
print('ident dups:', sorted(((v, k) for k, v in ident.items() if v > 1), reverse=True)[:10])
for n in nodes:                                                          # expect nothing
    c = collections.Counter(k.get('identifier') for k in (n.get('children') or []) if k.get('identifier'))
    for k, v in c.items():
        if v > 1: print('SIBLING COLLISION in', n.get('name'), '->', k, v)
```

### Which one does this API want?

| You are… | Pass |
|---|---|
| writing `<plugin id=…>` in a layout | **`identifier`** (any string, unique in that html plugin) |
| pointing a form at its fields page (`contentIdentifier`) | **`identifier`** |
| pointing a form group at its page (`contentPageIdentifier`) | **`identifier`** |
| calling `nct_ui_get_content_by_identifier` / `set_plugin_properties` over MCP | **`uniqueIdentifier`** |
| naming a refresh target (`componentIdentifier`, [02](02-form-controls-reference.md)) | **`uniqueIdentifier`** |
| listing Hidden Content (`contentIdentifiers`, [06](06-form-groups-and-mapping.md)) | **`uniqueIdentifier`** |
| matching a CRUD-tree / process-table settings mirror (`setting.name`, [05](05-crud-tree-and-process-table.md)) | **`uniqueIdentifier`** |

> **The symptom to recognise.** Pass an `identifier` where a `uniqueIdentifier` is wanted and
> you get `Content not found` — which reads like a broken reference and sends you hunting for
> a dangling link that does not exist. Pass a `uniqueIdentifier` into `<plugin id=…>` and the
> renderer simply **creates a new empty child** under that id (see the code above: no match →
> create) — the slot renders blank and nothing is logged. Both failures look like data loss.
> They are id-kind mistakes.

---

> **Don't confuse "Page" with the MCP `PageDto`.** The persistent page model is a `ContentDomain` with
> `pluginName="siteMapPage"` and a typed `properties` map (see below). The class
> `PageDto.java` (fields `layoutName`, `navigationGroup`,
> `sortOrder`, `hasForms`, `hasWorkflows`) is a **read-only projection for MCP**, not a serializable
> configuration. Menu order comes from `ContentDomain.order`, grouping from the property `group`,
> position in navigation from the tree structure (`parentId`/nesting). When assembling by hand, write
> `ContentDomain` properties, not `PageDto` fields.

## Export shape — a tree node

The tree lives in `branches.json` — this is an **array of branches** (usually one; `branch-metadata.json`
confirms `totalBranches:1`). A branch:

```json
{
  "name": "master",
  "tenantId": 1,
  "rootContent": { /* root siteMapPage node, recursively */ },
  "virtualPlugins": [ /* reusable fragments, see below */ ]
}
```

`tenantId` is an integer assigned by the platform per tenant — a different number in every project; read yours
with `jq '.[0].tenantId'` and keep it as exported. The branch `name` is `"master"`. Key order in JSON doesn't
matter — the platform reads by name.

> ⚠️ "Branch" is overloaded: (a) a business location (warehouse/store; conceptual docs) and (b) a **CMS container
> for a version of content** — that's what's in `branches.json` (`{name, rootContent, tenantId, virtualPlugins}`).
> In the export it always means (b).

### Full schema of a single node (`ContentDomain`)

```jsonc
{
  "id":                "f0f13c04-06e5-4c29-87be-49575782d32f",  // technical PK, UUID
  "identifier":        "34c97297-185b-41b7-a255-f37895984a1c",  // logical id (references point to it)
  "uniqueIdentifier":  "1fff8460-c128-4af7-82cb-9695008a9267",  // globally unique UUID
  "name":              "Home",                                   // human-readable name (not alias)
  "pluginName":        "siteMapPage",                            // selects the Java class from the registry
  "isBehaviour":       false,                                    // true = behaviour plugin, not visual
  "active":            true,
  "treeOpened":        true,                                     // UI state of the authoring tree
  "treeDisabled":      false,
  "treeSelected":      false,
  "includedInParsis":  false,
  "children":          [ /* child nodes */ ],
  "properties":        { /* typed slots, see below */ },
  "order":             0,                                        // order among siblings (important!)
  "branchId":          "6bc2ef69-8ed2-4756-a222-67cb699568b7",
  "childPluginAdded":  false,
  "roleAccess":        { /* access, see below */ },
  "virtualContent":    false
}
```

**Full set of a node's JSON keys** (`jq keys` on any node in `branches.json`): `active`,
`branchId`, `childPluginAdded`, `children`, `id`, `identifier`, `includedInParsis`, `isBehaviour`, `name`,
`order`, `pluginName`, `properties`, `roleAccess`, `treeDisabled`, `treeOpened`, `treeSelected`,
`uniqueIdentifier`, `virtualContent`. Additional `ContentDomain` model fields, not always serialized:
`alias`, `parentId`, `depth`, `linkContentIdentifier` (reference to a common vp), `tenantId`
`createdDate`/`updatedDate`.

Field names and types are from `ContentDomain.java`: `id/identifier/uniqueIdentifier/name/pluginName`
`isBehaviour` (getter `getBehaviour`), `active`, `alias`
`children` = `Set<ContentDomain>` with `@OrderBy("order")`, `order`, `branchId`
`roleAccess`, `virtualContent`.

**Key facts:**
- `id` vs `identifier` vs `uniqueIdentifier`: `id` is the surrogate PK; `identifier` is what
  forms/groups/`<plugin>` tags reference; `uniqueIdentifier` is a global UUID. If `identifier` is not set,
  `getIdentifier()` **lazily** generates a random UUID right in the getter (`ContentDomain.java`).
  `getUniqueIdentifier()`, unlike `getIdentifier()`, does **not** generate in the getter —
  it returns the field as-is. However `@PrePersist`, when saving to the DB, auto-fills `id`
  `uniqueIdentifier` **and** `virtualContent` if they are `null`. **When assembling by hand, set all three to explicit
  UUIDs**, otherwise references (e.g. a form's `contentPageIdentifier`) won't match and will depend on the
  UUIDs assigned on persist.
- `children` are sorted by `order` (`ContentDomain.java` `@OrderBy`). Duplicate `order` values → undefined
  ordering; keep them unique within a single parent.
- `linkContentIdentifier` — if the node references a common virtualPlugin, its identifier is here.
- Some "service" nodes use a **string identifier instead of a UUID**: a page's parsis is always
  `identifier = "siteMapPageParsis"` (`SiteMapPage.SITE_MAP_PAGE_PARSIS`, `nct-ui/.../page/SiteMapPage.java`),
  the internal layout slots — `"parsis"`, `"header"`, `"footer"`, `"logo-plugin"` etc. (they match the `id`
  in `<plugin id=…>`).

### Schema of `properties` — typed slots

`properties` is an object `{key → ContentProperty}`; in the DB the column `g_properties` is TEXT
(`columnDefinition = "text"`), a JSON string serialized via `ContentPropertiesLinkedHashMapConverter`
(`ContentDomain.java`). Each slot carries **exactly one** typed value, the type given by
`propertyType`:

```jsonc
"settings": {
  "key": "settings",
  "propertyType": "STRING",                 // which *Value to read
  "required": false,
  "hidden": false,
  "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
  "arguments": {},
  "stringValue": "<JSON string — the real plugin config>",  // <-- parse this
  "localizedStringValue": {}
}
```

Correspondence of `propertyType → value field` (from `PropertyType.java` + `ContentProperty.java`):

| `propertyType` | Carrier field | Java type | Example slot |
|---|---|---|---|
| `STRING` | `stringValue` | `String` | `settings`, `model`, `html`, `className`, `Redirect` |
| `BOOLEAN` | `booleanValue` | `Boolean` | `isParsis`, `showCard`, `reuseItems` |
| `INTEGER` | `intValue` | `Integer` | `width`, `height`, `minHeight`, `aliasParamsMaxCount` |
| `LONG` | `longValue` | `Long` | — |
| `FLOAT` | `floatValue` | `Float` | — |
| `DOUBLE` | `doubleValue` | `Double` | — |
| `BIG_DECIMAL` | `bigDecimalValue` | `BigDecimal` | — |
| `LOCALIZED_STRING` | `localizedStringValue` | `Map<String,String>` (key = `Locale.toString()`, e.g. `en_US`) | `pageTitle`, `pageDescription`, `text` (label) |
| `LOCAL_DATE` | `dateValue` | `LocalDate` | — |
| `LOCAL_DATE_TIME` | `dateTimeValue` | `LocalDateTime` | — |
| `LOCAL_TIME` | `timeValue` | `LocalTime` | — |

`fieldPanelClass` — which Wicket panel edits the property in authoring; for hand-assembly it's enough
to set the default by type (`PropertyBaseTextFieldPanel` for STRING/INTEGER, `PropertyBaseCheckboxFieldPanel`
for BOOLEAN, `PropertyBaseLocalizedTextFieldPanel` for LOCALIZED_STRING, `PropertyBaseTextAreaFieldPanel`
for `metaTags`) — if you leave it `null`, the platform substitutes it itself
(`ContentDomain.java`). `arguments` is usually `{}`. (In exports, `metaTags` may carry
`PropertyBaseTextFieldPanel` — an authoring artifact; `fieldPanelClass` is not load-bearing, any value
imports fine.)

> **The platform's main pattern: a complex plugin's config is a JSON string inside the `stringValue`
> of a STRING slot.** And **the slot depends on the kind of plugin**:
> - **form controls** (`dynaform.form.*`), the filter, buttons — in `properties.settings.stringValue`
>   (see [02-form-controls-reference.md](02-form-controls-reference.md));
> - **table plugins** — `crud.table.plugin`, `crud.tree.plugin`, `process.table.pluin` — in
>   **`properties.model.stringValue`** (NOT `settings`; see
>   [04-crud-table-plugin.md](04-crud-table-plugin.md), [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md));
> - **`chart.js.plugin`** — in **`properties.Javascript.stringValue`** (NOT `model`;
>   `ChartJsPlugin` writes `setJsonProperty(JS_MODEL_NAME="Javascript", …)`). A chart written into `model` renders empty;
> - tabs — `properties.tabModel.stringValue` (below).
>
> This is `getJsonProperty/setJsonProperty` (`ContentDomain.java`). So to change a setting,
> you edit the JSON **inside** JSON.

A real example of an "empty" slot (from `empty/branches.json`, any page):

```json
"Redirect": {
  "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
  "arguments": {}, "key": "Redirect", "stringValue": "",
  "localizedStringValue": {}, "propertyType": "STRING", "required": false, "hidden": false
}
```

---

## Pages — `siteMapPage`

A page = a `ContentDomain` with `pluginName="siteMapPage"`. Every export has
`rootContent.pluginName="siteMapPage"` and a common base set of property keys.

### Full example (root `Home`, `empty/branches.json` `rootContent`)

```jsonc
{
  "id": "f0f13c04-06e5-4c29-87be-49575782d32f",
  "identifier": "34c97297-185b-41b7-a255-f37895984a1c",
  "uniqueIdentifier": "1fff8460-c128-4af7-82cb-9695008a9267",
  "name": "Home",
  "pluginName": "siteMapPage",
  "isBehaviour": false, "active": true,
  "treeOpened": true, "treeDisabled": false, "treeSelected": false,
  "includedInParsis": false,
  "order": 0,
  "branchId": "6bc2ef69-8ed2-4756-a222-67cb699568b7",
  "childPluginAdded": false,
  "virtualContent": false,
  "properties": {
    "Redirect":        { …STRING "" },
    "additionalCss":   { …STRING "" },
    "group":           { …STRING (no stringValue) },
    "isParsis":        { …BOOLEAN false, PropertyBaseCheckboxFieldPanel },
    "layout":          { …STRING "Nct layout" },
    "metaTags":        { …STRING "" },
    "pageDescription": { …LOCALIZED_STRING {"en_US":"<Project> - Home","hy_AM":"<Project>"} },
    "pageTitle":       { …LOCALIZED_STRING {"en_US":"<Project> - Home","hy_AM":"<Project>"} }
  },
  "roleAccess": { … },
  "children": [ /* usually parsis.plugin "siteMapPageParsis" + child siteMapPage pages */ ]
}
```

> ⚠️ **`pageTitle`/`pageDescription` arrive carrying the DONOR project's name.** They are the browser
> `<title>` and the meta description, and nothing fills or checks them: `locale fill` reports 0 for them and
> `validate` stays green (doc 20 §L2). So whatever the baseline you unpacked happened to ship is what your
> project publishes to the browser tab and to every search engine. **Set both, for every locale, as part of
> the Home page work** — this is the one property pair no gate will ever remind you about.

The `empty` root `Home` actually has **20 children**: one `parsis.plugin` (`identifier="siteMapPageParsis"`)
+ 19 admin pages `siteMapPage` (`Sources`, `Queries`, `Database`, …); four more admin pages hang off those,
for 23 in all. So navigation is a tree of `siteMapPage` nodes, not a flat list.

> ⛔ **On an admin page, ADD THE REPLACEMENT FIRST — then delete.** Some plugin classes on those
> pages cannot be re-created through the API at all: `nct_ui_add_plugin` only accepts names the site
> template **registers in its palette**, and an inherited baseline node may carry a name that is not in
> it (`processes.plugin` is exactly that — see [14](14-plugin-catalog-all.md), "dead/legacy"). Remove
> such a node and only an **import** can put it back. So the order is always: look the plugin up in
> [14](14-plugin-catalog-all.md) **before** touching it → add the replacement → open the page and see it
> render → only then remove what it replaced. A real 2026 failure ran that backwards and left the
> Processes console blank: the author had merged the list plugin into a single self-contained
> master-detail plugin years earlier, the catalog said so in one line, and nobody read the line.
> The generalisation worth keeping: **an admin page's node is not yours — it is the console's, it is
> undocumented in your own project, and the catalog is the only place that says what it is.**

> ⛔ **NEVER delete the admin/system pages — ADD, don't replace.** Those admin children (Settings, Rules, Form
> Groups + Landing, PDF/Mail Templates, Sources, Queries, Contexts, Workflows, Schedulers, Roles, Users, Database,
> Business Logic, …) are the **management console** — deleting them breaks `/settings`, the form-group `?group=`
> landing, and template/rule admin (a real 2026 failure). **APPEND** your business pages to the existing
> `rootContent.children` (via `page add`, or by pushing onto the array in place); do NOT rebuild `rootContent` from
> scratch — a generator that reassigns `rootContent.children = [...my pages...]` drops the whole console. `validate`
> now ERRORs when a required admin page alias is missing.

### `siteMapPage` properties — by field

The set of property keys **varies from page to page** — this is the set of the root `Home`/`rootContent`
(`Redirect`, `additionalCss`, `group`, `isParsis`, `layout`, `metaTags`, `pageDescription`, `pageTitle`),
not a single complete list: `jq` over `siteMapPage` nodes yields 8–12 different key sets per export.
Besides those listed, `Body Class` occurs as a real property key (a separate slot, not the same as
`additionalCss`), `aliasParamsMaxCount`, and also **`formModeIdentifier`** (STRING, `stringValue` = identifier
of the form-mode rule; carried by form pages only, so its node count tracks how many forms the project has; see
[06-form-groups-and-mapping.md](06-form-groups-and-mapping.md)).

| Key | Type | Meaning | Req.? | Default | Source |
|---|---|---|---|---|---|
| `Redirect` | STRING | A non-empty value → the page does `setResponsePage(redirect)` (server-side redirect). | no | `""` | client-side `nct-ui/.../page/SiteMapPage.java`; `SiteMapPageDefaultPropertiesBuilder.REDIRECT="Redirect"` |
| `Body Class` / `additionalCss` | STRING | Extra CSS class/string on `<body>`. The builder declares **`"Body Class"`**; in exports the slot is called `additionalCss` (not declared by any builder — manual). | no | `""` | `SiteMapPageDefaultPropertiesBuilder.java` |
| `pageTitle` | LOCALIZED_STRING | `<title>` by locale. | no | `{}` | `PluginPage.PAGE_TITLE="pageTitle"` (`PluginPage.java`); builder; read at `PluginPage.java` |
| `pageDescription` | LOCALIZED_STRING | `<meta description>` by locale. | no | `{}` | `PluginPage.PAGE_DESCRIPTION="pageDescription"`; builder |
| `aliasParamsMaxCount` | INTEGER | How many URL segments after the alias to treat as parameters. | no | — | `SiteMapPageDefaultPropertiesBuilder.java` |
| `metaTags` | STRING | Raw `<meta>` tags. Declared **only** by the nct-ui builder. | no | `""` | `SiteMapPageNctPropertyBuilder.java` |
| `layout` | STRING | **Name of the virtualPlugin layout** for client rendering (see "Layout"). Value = one of the vp names. Not declared by any default builder. | no | `""` (default on read, `SiteMapPage.java`) | observed on all pages |
| `group` | STRING | Grouping in the left menu. Not declared by a builder; empty in exports. | no | `""` | observed |
| `isParsis` | BOOLEAN | Service flag "this node is a parsis container". For a page usually `false`. | no | `false` | `ParsisPlugin.java` |
| `alias` | (**node field, not property**) | **The page's URL segment — set it on EVERY page you author.** In `ContentDomain` this is a separate field `alias`, not in `properties`. A page's URL is the `alias` of each ancestor joined down from the root, so a page with a null alias has **no reachable URL**: its left-nav/quick-link entry lands on the project root, no `Redirect` can target it ([21](21-homepage-and-redirect.md)), and a typed path never resolves it. Lowercase slug, unique among its siblings (form + landing pages: unique **project-wide** — see [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md)). Only the structural root `Home` legitimately has none: in `empty` all 29 other `siteMapPage` nodes carry one (`sources`, `queries`, `bl`, `database`, …). | **yes** | — | `ContentDomain.java` |

**Page `layout` values (`siteMapPage`)** — run `jq` over your own `siteMapPage` nodes and you get a small set:
`null`, `"Nct layout"`, `"Main"`, `"Form"`, plus whatever an author once typed by hand (stray one-off names do
occur — they simply find no vp and fall through). (The value `"portrait"` also occurs, but **not on `siteMapPage`,
rather on PDF nodes** `pdf.report.page.plugin`/`pdf.report.plugin` — this is a PDF page orientation, not a site
layout.) This is **not a clean admin/client split**: the admin page `Sources` in `empty` uses
`layout="Nct layout"` (the same `fdcdca35…` as the client pages), while other admin pages use `"Main"`. The names
correspond to virtualPlugins (see "virtualPlugins"); the fictitious `default`/`two-column`/`dashboard`/`full-width`
**do not exist**.

### Page structure: page → parsis → layout → inner parsis → content

Each `siteMapPage` contains **exactly one** child `parsis.plugin` with
`identifier = "siteMapPageParsis"` — it is materialized via `pluginUtils.getOrCreateParsis(...,
SITE_MAP_PAGE_PARSIS, "parsis")` (`nct-ui/.../page/SiteMapPage.java`). An empty admin page
(`empty`, `Sources`) looks like this (the order of the layout children matches the real export):

```
siteMapPage "Sources"
└── parsis.plugin  identifier="siteMapPageParsis"   (isParsis=true)
    └── html.plugin "Layout"  identifier="fdcdca35-9820-426a-bd7e-ce7e36a6fd22"   (vp "Nct layout")
        ├── nct.image.plugin       id="logo-plugin"
        ├── site.header.plugin     id="header"
        ├── site.right.kicker.plugin id="right-kicker"
        ├── site.breadcrumb.plugin id="breadcrumb"
        ├── site.kicker.plugin     id="left-nav"
        ├── nct.parsis.plugin      id="parsis"   ← THE PAGE CONTENT GOES HERE
        └── site.footer.plugin     id="footer"
```

A real business page (say `Products` in an ERP, or `Invoices` in a finance system) — the same schema, but in the inner `nct.parsis.plugin`
(`id="parsis"`) sit the business plugins, plus the page has a child `siteMapPage` for forms:

```
siteMapPage "Products"
├── parsis.plugin  identifier="siteMapPageParsis"
│   └── html.plugin "Layout"  identifier="fdcdca35-…"   (page property layout "ddd")
│       └── … nct.parsis.plugin id="parsis"
│           ├── dynaform.filter.form.plugin   (Filter Form)
│           └── crud.table.plugin             (CRUD Table)   ← see 04-crud-table-plugin.md
└── siteMapPage "Product Forms"   (child page for forms, see 06-form-groups-and-mapping.md)
```

> **`site.*` — the template "chrome".** `site.header.plugin`, `site.footer.plugin`, `site.kicker.plugin`
> (left menu), `site.right.kicker.plugin`, `site.breadcrumb.plugin` are present on almost every page — roughly
> one of each per page, since they come in with the layout. Their config is minimal (`className` etc.); they build the navigation content
> from the page tree. When assembling by hand, take them from a ready layout node as-is.

### Client rendering of `layout`: cloning a virtualPlugin (important for Step-2)

The client-side `SiteMapPage.getParsis()` (`nct-ui/.../page/SiteMapPage.java`), on render:

1. finds/creates `siteMapPageParsis`
2. **only if it has 0 children** — reads the property `layout` (default `""`), looks for a
   virtualPlugin with that name (`findAllVirtualPluginsByBranchId`);
3. if the vp is found — **clones its `content`** (`contentService.cloneContent(vp.get().getContent())`),
   assigns new `uniqueIdentifier`s, places the clone into parsis, saves and re-renders.

The consequence for hand-assembly — **two valid variants**:

- **(A) Materialized layout.** You put the layout node `html.plugin` into `siteMapPageParsis.children`
  explicitly (parsis non-empty → the clone doesn't trigger). This is what every authored project ships.
- **(B) Lazy layout.** You set `layout="Nct layout"` and **leave `siteMapPageParsis` empty** —
  on the first render the platform clones the vp "Nct layout" into parsis itself.

An export taken from a project that was already rendered in authoring always shows variant (A).

> **(C) Built on demand — only on a LIVE project, never in an export.** In support mode
> `nct_ui_apply_layout_to_page` performs steps (2)–(3) on the spot, so the page has its tree before anybody
> opens it in a browser. It stops exactly where step (3) stops: the shell's own `<plugin>` slots are still
> created by `AbstractHtmlPlugin` at render time, so the inner `nct.parsis.plugin` appears on first view and
> not before. It exists because `nct_ui_create_page` does the naming half only: a page created
> over MCP IS variant (B), stays empty until a human renders it, and until then the plugin tools have no
> parsis to address. This is not a route for a generated export — nothing in a `.mrjun` executes, so (A) is
> still the only safe shape to ship. → [28 §5b](28-support-mode-over-mcp.md).

> ⛔ **For any generated export that must SHIP business content, (A) is REQUIRED.** (B) always yields an
> **EMPTY content parsis** on import: the platform clones the vp `"Nct layout"` only on first live render, and that vp is
> **CHROME-ONLY** — its `content.children` is `[]` (open the vp and check: the inner
> `nct.parsis.plugin id="parsis"` exists only inside the layout's `html` string, so the clone materializes empty).
> A page shipped as (B) imports clean (valid JSON, CRUDs validate) but renders as **bare chrome with NO business
> content** — the classic "renders empty" bug. Use (B) **only** when the page's content will be authored LIVE in the
> UI after materialization, never for a self-contained generated export. Ship pages as (A).

---

## Layout — how embedded HTML + `<plugin>` assembles the page

The nodes `html.plugin` and `nct.html.plugin` carry an **HTML string** in the property `html` (STRING). Inside it,
`<plugin id="X" name="Y">…</plugin>` tags are allowed. On render, `AbstractHtmlPlugin`:

1. parses the HTML via Jsoup (`AbstractHtmlPlugin.java`);
2. for each root `<plugin>` (not nested inside another `<plugin>`) creates/finds a **child
   ContentDomain** with `identifier = id` and `pluginName = name` (`getOrCreateChildContentComponent`)
   and renders it in place of the tag;
3. child `<property name= value= type=/>` / `<prop …/>` inside the tag become properties of that
   child node.

**That is, `<plugin id="parsis" name="nct.parsis.plugin">` in the layout's HTML string ↔ a child node
`nct.parsis.plugin` with `identifier="parsis"`.** This is exactly how the `id` from the HTML is stitched to the real child node.
Both must be present: the `<plugin>` in the string and the corresponding child in `children`. Forgot the child →
"Not valid plugin …" in place of the tag.

> ### ⛔⛔ THE TYPE-SWAP TRAP — the html's `name=` WINS and **wipes the node's properties**
>
> The tag carries **two** bindings: `id` selects the child, `name` declares its plugin type. When they
> disagree, the platform does not warn. It matches the child by `identifier`, and if that child's plugin
> type differs from the `name=` in the html, it **clears every property of the node** — settings, model,
> html, all of it — and sets the type to the one named in the html.
>
> So **changing a node's `pluginName` in an authored export is a TWO-PLACE edit**: the node itself *and*
> the `name=` of the `<plugin>` tag in its parent's `html`. Edit only the node and the page silently renders
> the OLD control with an EMPTY settings blob — for a form control that reads as "the field lost its
> mapping": no `scope`/`crudAlias`/`fieldExpression`, so it neither displays nor submits any value. Nothing
> in validate/import/export flags it; it only shows up at render time.
>
> The same applies when you clone a laid-out subtree and swap one control's type in the copy (e.g. a plain
> text field → autocomplete in a process-start form): fix the slot's `name=` in the clone too.
> `mrjun.py validate` now ERRORs on a node/`name=` mismatch — see [23](23-distribution-and-known-gaps.md).

> ### ⛔⛔ THE CLONING TRAP — regenerating an identifier EMPTIES THE PAGE
>
> The binding above is **by `identifier`, from a plain string**. Nothing enforces it: a child whose
> `identifier` no longer matches any `<plugin id=…>` in its parent's html stays in the tree, exports,
> imports and **validates** — and is simply never drawn.
>
> This is the single most expensive mistake when you build pages by **cloning** a laid-out page (the usual
> recipe — clone the shared `Landing` so the new page inherits the Layout chrome, then empty its content
> parsis). The baked Layout addresses **seven** children by name:
>
> ```
> header · logo-plugin · breadcrumb · left-nav · parsis · footer · right-kicker
> ```
>
> A clone helper that regenerates identifiers "except the symbolic ones" and keeps only a hardcoded subset
> (say `left-nav` + `parsis`) silently strips the header, logo, breadcrumb, footer and right kicker off
> **every page it creates**. This has actually shipped: thousands of dangling references across the whole
> site, and the first words after importing were *"all pages are empty"* — while `validate` reported 0 errors,
> `coverage` was complete and `crud verify` was green. No offline gate looked at the html↔children relationship.
>
> ### The one it costs you twice: `siteMapPageParsis`
>
> A `siteMapPage` resolves its content container from the child `parsis.plugin` whose identifier is the
> well-known **`siteMapPageParsis`**. That id appears in **no html at all** — the page looks it up by name —
> so the "preserve what the html references" rule above does **not** save it, and a clone helper drops it.
>
> When it is missing the platform does not error: it **creates a fresh empty `siteMapPageParsis` and renders
> that**, leaving the cloned subtree beside it as an unrendered orphan. Symptom: a completely blank page whose
> live DOM has **two** `parsis.plugin` children — one with your Layout and content, one empty and rendered.
> Every offline gate stays green (that is how it shipped: most of the site blank).
>
> ```
> siteMapPage
>   ├─ parsis.plugin  identifier="siteMapPageParsis"   <- ONLY this one is rendered
>   │    └─ html.plugin "Layout" ─ … ─ nct.parsis.plugin "parsis"  <- your content goes here
>   └─ parsis.plugin  identifier="<regenerated uuid>"  <- orphan: present, exported, never drawn
> ```
>
> So the preserve-set is **`siteMapPageParsis` + `Layout` + `parsis` + `left-nav` + `form.parsis` +
> `filter.parsis` + every id any html in the subtree references.**
> `validate._check_page_top_parsis` ERRORs on a page whose top parsis lost the name, and on a page carrying
> more than one top-level `parsis.plugin`.
>
> ### Just call `core.regen_ids` — it already gets this right
>
> ```python
> from mrjunkit import core
> page = json.loads(json.dumps(donor))     # clone a laid-out page
> core.regen_ids(page, p.branch_id())      # <- the ONE correct way
> ```
>
> Its rule is simpler and stricter than any allowlist: **regenerate ONLY uuid-shaped identifiers; keep every
> non-uuid identifier verbatim**, because a non-uuid identifier IS a layout anchor resolved by name. Symbolic
> ids are meant to repeat across pages — that is not a collision. Every blank-page incident on record came from a
> generator hand-rolling this with its own list. Don't. (`core.regen_ids` / `core.looks_uuid`.)
>
> **Rule (if you ever must write it yourself): never regenerate an identifier that is not uuid-shaped, and never
> one that any html inside the subtree references.** Don't maintain a list — derive it:
>
> ```python
> import re
> PLUGIN_REF = re.compile(r'<plugin[^>]*\bid="([^"]+)"')
>
> def html_plugin_refs(subtree):          # every id addressed from any html in the subtree
>     refs = set()
>     for n, _p, _t in core.iter_nodes(subtree):
>         for slot in (n.get("properties") or {}).values():
>             v = isinstance(slot, dict) and slot.get("stringValue")
>             if isinstance(v, str) and "<plugin" in v:
>                 refs.update(PLUGIN_REF.findall(v))
>     return refs
>
> keep = {"siteMapPageParsis", "left-nav", "form.parsis", "filter.parsis",
>         "parsis", "Layout"} | html_plugin_refs(page)
> # regenerate identifier ONLY when it is not in `keep`
> ```
>
> The same applies to the row/column/slot shells you emit yourself (`gen_row_*` → `gen_col*` → `gen_slot_*`):
> the `<plugin id="…">` inside each wrapper's html **must** equal the child node's `identifier`.
>
> `mrjun.py validate` now catches this (`_check_html_plugin_refs`): a dangling `<plugin id>` paired with an
> unreferenced child of the same plugin type is an **ERROR** (that pairing means an id was regenerated — it never
> occurs in a healthy export, and appears in the thousands once the bug is present); a merely-absent optional
> plugin, or a child an html deliberately does not draw, is a **WARN**.

### `html.plugin` "Layout" (Nct layout) — the real `html` (node `fdcdca35-…`)

```html
<div class="app-container app-theme-white body-tabs-shadow fixed-header fixed-sidebar">
    <div class="app-header header-shadow">
        <div class="app-header__logo">
            <a href="/">
              <plugin name="nct.image.plugin" id="logo-plugin">
                <prop name="tooltip", value="Logo", type="STRING"/>
                <prop name="description", value="Logo", type="STRING"/>
                <prop name="width", value="90", type="INTEGER"/>
                <prop name="height", value="60", type="INTEGER"/>
                <prop name="url", value="abs(/architectui-html-pro/images/logo-inverse.png)", type="STRING"/>
              </plugin>
            </a>
            …hamburger buttons…
        </div>
        …
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
<div class="app-drawer-overlay d-none animated fadeIn"></div>
```

Note: `<prop>` and `<property>` are both supported, `type` is parsed into `PropertyType`
(`AbstractHtmlPlugin.java`), default STRING if the type is unknown. `abs(...)` in `url` is
a macro for the absolute path to an asset.

### `html.plugin` — by field

| Property key | Type | Meaning | Default |
|---|---|---|---|
| `html` | STRING | HTML markup with embedded `<plugin>` tags. | `""` |
| `className` | STRING | CSS class on the plugin wrapper. | `""` |
| `styleName` | STRING | inline style. | `""` |
| `tagProperties` | STRING | extra tag attributes. | `""` |
| `reuseItems` | BOOLEAN | reuse Wicket ListItems (`AbstractHtmlPlugin.java`). | `false` |
| `editorHeight` / `editorWidth` | STRING | code editor size in authoring (e.g. `"700px"`/`"100%"`). Doesn't affect rendering. | — |
| `isParsis` | BOOLEAN | service flag. | `false` |

`nct.html.plugin` — the same mechanism, the NCT/architectui variant; used as a grid container and as a
"label field". In `empty` most layout virtualPlugins (`4-col`, `3-col`, `2-col`, `1-col`, `Card`,
`Drop Down Label Field` etc.) are `nct.html.plugin`.

### Bootstrap grid inside `html` (this IS the "form layout")

**Form layout is done with Bootstrap markup in the `html` string, and NOT with a `width`/`sections` field on the control.**
(The old `form-layout.md` described YAML `fields:`/`width`/`mobileWidth`/`sections`/`collapsible`/
`iconPosition`/`hiddenConfigs` — all of that is **fiction**; on real control nodes there is only `className`,
`settings`, `styleName`, `tagProperties`.) Each column contains `<plugin name="nct.parsis.plugin">` for
content; the width = a `col-md-N` class (12/6/4/3/2 → 100/50/33/25/16%). The real "4-col Layout" virtualPlugin
(`empty`, `nct.html.plugin`):

```html
<div class="row">
  <div class="col-md-3"><plugin id="first"  name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-3"><plugin id="second" name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-3"><plugin id="third"  name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-3"><plugin id="forth"  name="nct.parsis.plugin"></plugin></div>
</div>
```

Generated forms (Generate-fields-from-CRUD, see
[03-generate-fields-from-crud.md](03-generate-fields-from-crud.md)) use the same trick: a
`col-md-*` wrapper with `<plugin>` parsis nodes:

```html
<div class="row">
  <div class="col-md-3"><plugin id="gen_col1_4143cc62" name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-3"><plugin id="gen_col2_4143cc62" name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-3"><plugin id="gen_col3_4143cc62" name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-3"><plugin id="gen_col4_4143cc62" name="nct.parsis.plugin"></plugin></div>
</div>
```

And a single form field is an `nct.html.plugin` with an `mb-3` wrapper, embedding the label + control:

```html
<div class="mb-3">
  <plugin id="lbl_gen_slot_4143cc62_2_0" name="nct.label.plugin"></plugin>
  <plugin id="fld_gen_slot_4143cc62_2_0" name="dynaform.form.textarea.field.plugin"></plugin>
</div>
```

(the corresponding child nodes `nct.label.plugin` and `dynaform.form.textarea.field.plugin` sit in the `children`
of this `nct.html.plugin`; their `identifier` = `lbl_gen_slot_…` / `fld_gen_slot_…`).

### Grammar of `<plugin>`/`<prop>` with type and localized value

A label/field can be declared right in the HTML via nested `<prop>`. An example label declaration inside `html`:

```html
<plugin id="lbl_x" name="nct.label.plugin">
  <prop name="text"      type="LOCALIZED_STRING" value='{"en_US":"Description","ru_RU":"Описание"}'></prop>
  <prop name="tagName"   value="label"></prop>
  <prop name="className" value="form-label"></prop>
</plugin>
```

`type="LOCALIZED_STRING"` → the value is parsed as JSON `{locale→text}` (`PropertyType.parse`,
`PropertyType.java`). Without `type` — STRING.

---

## Parsis — a "content hole"

`parsis.plugin` (mrjun, `Constants.Plugins.PARSIS_PLUGIN`) and `nct.parsis.plugin`
(nct-ui `NctParsisPlugin extends ParsisPlugin`, `nct-ui/.../plugin/common/NctParsisPlugin.java`) are
containers into which an ordered list of child plugins is placed. Parsis is exactly what gives the
drag-and-drop zone in authoring and renders children by `order` with an access check on each
(`ParsisPlugin.java`).

### `nct.parsis.plugin` / `parsis.plugin` — by field (all properties optional)

| Key | Type | Meaning | Default | Source |
|---|---|---|---|---|
| `isParsis` | BOOLEAN | Marks the node as parsis; if `false`, the plugin sets `true` itself and saves (`ParsisPlugin.java`). | `true` (in export) | `ParsisPlugin.java` |
| `reuseItems` | BOOLEAN | reuse Wicket ListItems. | `false` | `ParsisPlugin.java` |
| `minHeight` | INTEGER | min-height of the empty zone in authoring (px). | `40` | `ParsisPlugin.java` |
| `emptyPlaceholder` | STRING | "Drop … here" text for an empty parsis. | `""` | `ParsisPlugin.java` |
| `style` | STRING | inline style; when non-empty renders a wrapper (`ParsisPlugin.java`). | — | `ParsisPlugin.java` |
| `className` / `styleName` / `tagProperties` | STRING | styling. | `""` | observed |

**Important:** parsis checks access **on each child** (`cmsSecurityService.hasAccess(listContent,
tenant(), RoleAccess.RoleAccessType.view)`, `ParsisPlugin.java`). A child without view access for the current
role simply doesn't render — this is the "hide a plugin from a role" mechanism, separate from the page's own
`roleAccess`. `includedInParsis` (a node flag) marks that a node is materialized inside parsis (e.g.
a cloned layout, `SiteMapPage.java`).

---

## Tabs — `nct.tab.plugin`

Tabs. The `nct.tab.plugin` node carries a property `tabModel` (STRING with **nested JSON**), and **each
tab = a child `nct.parsis.plugin` whose `identifier` equals the tab item's `id`**
(`TabPlugin.java` creates an `nct.parsis.plugin` with identifier = `modelObject.getId()`).

> ⛔ **Always write `"size": "SMALL"`.** Omit it and you get `BIG` twice over — the field initialiser is
> `TabSize.BIG` (`TabModel.java`) and `getSize()` coerces null→`BIG` . BIG is a chunky bar that
> eats vertical space above every grid; SMALL is the compact `nav-tabs` strip the platform's own screens
> use. Full rule → [14 §1.8](14-plugin-catalog-all.md).
>
> ⛔ **Tabs are also the ONLY way two tables may share a page** — any two of
> `crud.table.plugin` / `crud.tree.plugin` / `process.table.pluin`, same type or mixed, one per tab pane.
> Otherwise give each its own page. → [14 §2.3](14-plugin-catalog-all.md).

### Full example (an `nct.tab.plugin` node "Tabs" on a warehouse page)

`properties.tabModel.stringValue` (parsed JSON, note the `localizedMap.name` values):

```json
{
  "items": [
    { "id": "5b7fd1bc-136f-4f70-9388-578029065e9a", "name": "Stock", "order": 0, "iconClass": "",
      "needToBeSaved": false,
      "localizedMap": { "name": { "en_US": "Stock", "ru_RU": "Остатки", "hy_AM": "Պահեստի Մնացորդ" } } },
    { "id": "7af19caa-1eb9-4372-ad19-bce366f1eb67", "name": "Stock Movement", "order": 1, "iconClass": "",
      "needToBeSaved": false,
      "localizedMap": { "name": { "en_US": "Stock Movement", "ru_RU": "Движение остатков", "hy_AM": "Պահեստի շарժ" } } },
    { "id": "22ae6ae8-aa07-4dd3-9e07-8009793eb246", "name": "Lot", "order": 2, "iconClass": "",
      "needToBeSaved": false,
      "localizedMap": { "name": { "en_US": "Lot", "ru_RU": "Партия", "hy_AM": "Խմբաքանակ" } } }
  ],
  "size": "SMALL"
}
```

The `children` of this node (one parsis per tab, identifier = the tab's `id`):

```json
[
  { "name": "5b7fd1bc-…", "pluginName": "nct.parsis.plugin", "identifier": "5b7fd1bc-136f-4f70-9388-578029065e9a", "order": 2 },
  { "name": "7af19caa-…", "pluginName": "nct.parsis.plugin", "identifier": "7af19caa-1eb9-4372-ad19-bce366f1eb67", "order": 1 },
  { "name": "22ae6ae8-…", "pluginName": "nct.parsis.plugin", "identifier": "22ae6ae8-aa07-4dd3-9e07-8009793eb246", "order": 0 }
]
```

### `tabModel` / `TabItem` — by field

The class `TabModel` (`nct-ui/.../switcher/TabModel.java`), `TabSize` (`TabSize.java`):

| Field | Type | Meaning | Default |
|---|---|---|---|
| `items` | `List<TabItem>` | List of tabs; sorted by `order` on render (`TabPlugin.java`). | `[]` (`TabModel.java`) |
| `size` | enum `TabSize` | `"BIG"` or `"SMALL"` — tab size (`TabPlugin.java`, `TabSize.java`). | `BIG` (`TabModel.java`) |
| `TabItem.id` | String (UUID) | tab id = identifier of the child `nct.parsis.plugin`. | random UUID (`TabModel.java`) |
| `TabItem.name` | String | base tab name (fallback). | — (`TabModel.java`) |
| `TabItem.order` | int | tab order. | 0 (`TabModel.java`) |
| `TabItem.iconClass` | String | icon CSS class (e.g. `fa fa-box`); when non-empty an `<i>` is rendered (`TabPlugin.java`). | — (`TabModel.java`) |
| `TabItem.localizedNames` | `Map<String,String>` | per-locale caption (key `Locale.toString()`), the canonical storage (`TabModel.java`). | `{}` |
| `localizedMap.name` | `Map<String,String>` | Legacy caption storage (`TabItem extends MicroserviceTranslatedLocalizedBean`, `TabModel.java`) — **this is what authored exports actually carry** (see example; the exported items usually have no `localizedNames` key at all). | — |
| `needToBeSaved` | boolean | authoring UI flag; `false` in export. | `false` |

> In exports, tabs store captions under the key `localizedMap.name` (legacy), while the new code writes
> `localizedNames`. When assembling by hand it's safer to specify **both**: `"localizedMap":{"name":{…}}` and
> `"localizedNames":{…}` — the render reads either.

### Other `nct.tab.plugin` properties

| Key | Type | Meaning | Default | Source |
|---|---|---|---|---|
| `showCard` | BOOLEAN | Wrap the tab content in a bootstrap `card`. | `false` | `TabPlugin.java` |
| `tabModel` | STRING (JSON) | see above. | `{"items":[],"size":"BIG"}` | `TabPlugin.java` |
| `className` / `styleName` / `tagProperties` | STRING | styling. | `""` | observed |

The active tab is remembered in session metadata (the first by default) — it doesn't affect the export.

---

## Access — `roleAccess`

`roleAccess` (`RoleAccess.java`) — access to the node (JSONB on the node itself, doesn't require a separate
save). Present on **any** node and honoured on any node: a `siteMapPage` gates the whole page, and every other
node gates the one component it belongs to (see §"Hidden content" below).

```jsonc
"roleAccess": {
  "publicReadAccess": false,          // public (anonymous) read access
  "authenticatedUserAccess": false,   // any logged-in user
  "accessors": {                      // by system roles (permission roles)
    "admin":      { "view": true,  "edit": true,  "advancedEdit": true  },
    "nct_author": { "view": true,  "edit": true,  "advancedEdit": true  },
    "user_view":  { "view": true,  "edit": false, "advancedEdit": false }
  },
  "roleGroupAccessors": {             // by the project's role groups
    "Author":      { "view": false, "edit": false, "advancedEdit": false },
    "ERP Manager": { "view": false, "edit": false, "advancedEdit": false }
  }
}
```

### Fields

| Field | Type | Meaning | **Default (Java)** | Source |
|---|---|---|---|---|
| `publicReadAccess` | boolean | Page accessible anonymously (public). | **`true`** | `RoleAccess.java` |
| `authenticatedUserAccess` | boolean | Accessible to any logged-in user. | **`false`** | `RoleAccess.java` |
| `accessors` | `Map<String, {view,edit,advancedEdit}>` | Access by system roles. | `{}` | `RoleAccess.java` |
| `roleGroupAccessors` | `Map<String, {view,edit,advancedEdit}>` | Keyed by role-group name; membership **is** checked, so this is the map that gates a business **persona** (see the note below). | `{}` | `RoleAccess.java` |

`RoleAccessor`/`RoleGroupAccessor`: fields `view`/`edit`/`advancedEdit`, all default `false`.

**System roles occurring in `accessors` (across the exports):** `admin`, `nct_author`, `user_view`,
`user_edit`, `user_create`, `user_delete`, `role_group_view/edit/create/delete`, `file_storage_view/edit`,
`source_view/edit/view_any/edit_any`, `scheduler_view/edit/view_any/edit_any`,
`report_view/edit/view_any/edit_any`, `store_execute/store_execute_any`, `oyo_project_configuration`,
`project_view/project_edit`.
The client-side `SiteMapPage` additionally gates rendering with **three** disjuncts (`SiteMapPage.java`:
`isPublicReadAccess() || user() != null || !sso()`): anonymous access is allowed with `publicReadAccess`, with the
presence of a user, **or when SSO is disabled** (`!sso()`) — so with SSO off the parsis renders for anonymous
visitors regardless of `roleAccess`.

### Three page access policies

1. **Public** (anonymous): `"publicReadAccess": true`. This is how a new `ContentDomain` page is created
 by default. The 401/404 pages in `empty` are public
   (`404: publicReadAccess=true, authenticatedUserAccess=false`).
2. **Authenticated only:** `"publicReadAccess": false, "authenticatedUserAccess": true`. This is the **newer
   platform behavior for auto-created form-group landing/form pages**, but older projects were authored before
   it existed: form and landing pages in an existing export are frequently still **public**
   (`publicReadAccess=true`), and the admin scaffolding pages that host them are often `false/false`. So
   **don't assume a form page inherited "authenticated-only" — set page access deliberately** on every page
   you author.
3. **Specific roles/groups only:** `publicReadAccess=false, authenticatedUserAccess=false` +
   set `view:true` for the needed keys in `accessors`. This is how private business pages are normally done
   (`admin`/`nct_author` = all true + a subset of `user_view`/`user_edit`/… system permission-roles; the rest
   false).

> ✅ **`roleGroupAccessors` gates by role GROUP, and membership IS checked.** An entry whose `view` (or `edit`,
> or `advancedEdit`) is `true` grants the node to the **members of that group** — the check resolves the
> current user's role groups and compares. So `"Back Office": {"view": true}` next to `publicReadAccess=false`
> + `authenticatedUserAccess=false` does produce a back-office-only node. This is the knob for a **business
> persona**; `accessors` is the parallel map for the platform's fixed **system** roles (`admin`/`nct_author` =
> author visibility, `user_view`/`user_edit`/… = permission-role visibility), and a project persona can never
> appear there.
>
> ⚠️ Two behaviours to author around, both deliberate:
> * **Unresolved ≠ empty.** While membership cannot be resolved at all (identity store unreachable), the check
>   keeps the legacy grant and lets any authenticated user through, rather than locking the real members out
>   for the length of an outage. A project that simply *has* no role groups resolves to an empty membership and
>   fails **closed** — such a node is then reachable only through the public / authenticated / `accessors`
>   branches.
> * **Admin bypasses everything.** A user granted the `admin` system role passes every access check, for every
>   access type, whatever the maps say. Author with a non-admin account when you want to see what an end user
>   sees.
>
> ⛔ This is still **not** row-level security: it decides whether a node renders, never which rows a list
> returns. For "the clerk sees only their own" see [19](19-build-decision-procedure.md) Phase 6.

> **RoleAccess defaults**: `new RoleAccess()` gives `publicReadAccess=true` (`RoleAccess.java`). So
> if you simply **omit** `roleAccess` in a JSON node, the page becomes **public**. For a private
> page, always serialize `roleAccess` with `publicReadAccess=false` and the needed accessors.

### Hidden content — access on a single component

Access is stored **per content node and is not inherited**, so any node — not just a page — can carry its own
`roleAccess`. That is how you hide **one component** from a persona while the page around it stays visible:
give the component's own node `publicReadAccess:false`, `authenticatedUserAccess:false` and `view:true` only
for the groups that may see it. Every plugin applies its own node's view gate before it renders, in whatever
container it sits (and a parsis additionally skips a child without view), so the setting holds everywhere.

**In the authoring UI**: the component's own context menu → **Role access**, next to *Settings*. It opens the
same editor pages and quick links use. (The content tree also has a **Role access** item, but only on **page**
nodes — it is hidden for parsis/plugin nodes, so the component menu is the only route to a component's access.)

It edits the component's **resolved** node. For a plain component that is simply the node in the page. For one
saved as a **common component** it is the **shared** node, so the access applies **everywhere that component is
used** — the dialog title says so. To give one placement its own access, *Detach from virtual template* first,
then set access on the detached copy.

⛔ **Do not hand-edit `roleAccess` onto the page-local stub of a linked common component** expecting it to gate
that placement. Only a parsis checks its children one by one; an HTML-component layout places its `<plugin>`
children with no such check, and the component's own gate reads the resolved (shared) node. So a per-placement
grant is honoured inside a parsis and silently ignored under an HTML component.

⚠️ **Nothing happens until you untick "Public view access".** A node that has never had access set defaults to
`publicReadAccess=true`, and the check short-circuits on it before any role or group is read — so ticking a
group while public view is still on changes nothing. Untick public (and, for a persona, authenticated too),
*then* grant the groups. And check the project **has** role groups first: with none defined the group table
opens empty, and the individual-roles table behind the ⚙ toggle is shown only to the project's admin/author
accounts — untick public there and the component is hidden from everyone with nothing to grant.

ℹ️ **Lock-out.** A user holding the `admin` platform role passes every access check unconditionally, and the
dialog's `admin` / `nct_author` rows are disabled so you cannot untick them — so in practice you keep seeing
the component and its menu. Worth knowing anyway: the menu lives *on* the component, so a component you did
manage to hide from yourself takes its own editor with it, and there is no tree fallback for a non-page node.
The way back is `mrjun.py roleaccess set` on the export, or another account with `admin`.

Hiding form fields by predicate (prohibited/hidden) is a runtime form mechanism, see
[02-form-controls-reference.md](02-form-controls-reference.md), not `roleAccess`.

---

## virtualPlugins — reusable fragments

`branches.json[0].virtualPlugins` is an array of `VirtualPluginDomain` (`VirtualPluginDomain.java`):
named, grouped content templates (layouts, label fields, "Card", the logo, ready form controls). A client
page references a layout vp by **name** via the property `layout`, and on the first render of an empty
parsis the platform clones its content (see "Client rendering of `layout`").

### Element schema — all 9 keys (verbatim, `empty`, vp "Nct layout")

```json
{
  "id": "06e1f176-6e62-4f66-ac76-a4bcb54b38ae",
  "name": "Nct layout",
  "group": "Layout",
  "commonContent": false,
  "hidden": false,
  "isLayout": false,
  "useContentChildren": false,
  "templateNames": ["architectui-html-pro"],
  "content": { "pluginName": "html.plugin", "identifier": "fdcdca35-9820-426a-bd7e-ce7e36a6fd22", "…": "…" }
}
```

| Field | Type | Meaning | Default | Source |
|---|---|---|---|---|
| `id` | String (UUID) | vp id. | random UUID | `VirtualPluginDomain.java` |
| `name` | String | Name; page.`layout` = this name. | — | |
| `group` | String | Group in the palette: `Layout`, `Layouts`, `Label Fields`, `Form Controls`, `Logo`, `Common`. | — | |
| `commonContent` | Boolean | `true` = a shared template (referenceable via `linkContentIdentifier`); `false` = tenant-specific. | `false` | |
| `content` | ContentDomain | A tree fragment (same node format). Its `identifier` is materialized in the page (e.g. `fdcdca35-…`). | — | |
| `templateNames` | `List<String>` | For which site-templates it's available (e.g. `["architectui-html-pro"]`). | — | |
| `hidden` | Boolean | Hidden in the palette. | `false` | |
| `isLayout` | Boolean | Marks the vp as a layout. **⚠ not a reliable marker: "Nct layout" has `isLayout=false`**; `isLayout=true` only on `Main`/`Form`. | `false` | |
| `useContentChildren` | Boolean | Use the content's children directly. | `false` | |

`commonContent` and `isLayout` are **independent** booleans (e.g. `Nct left nav`: `commonContent=true`,
`isLayout=false`), not a mutually exclusive triple "Common/Layout/Standard".

Full list of vps in `empty` (all projects start with it):

| group | name | commonContent | isLayout | content.pluginName |
|---|---|---|---|---|
| Layout | 4-col Layout | false | false | nct.html.plugin |
| Layout | 3-col Layout | false | false | nct.html.plugin |
| Layout | 2-col Layout | false | false | nct.html.plugin |
| Layout | 1-col Layout | false | false | nct.html.plugin |
| Layout | Nct left nav | true | false | site.kicker.plugin |
| Layout | Nct layout | false | false | html.plugin |
| Layouts | Main | false | **true** | html.plugin |
| Layouts | Pdf | false | false | html.plugin |
| Layouts | Form | false | **true** | html.plugin |
| Logo | Logo | true | false | nct.image.plugin |
| Common | Card | false | false | nct.html.plugin |
| Form Controls | Sparepart List Control | true | false | dynaform.form.list.field.plugin |
| Label Fields | Drop Down Label Field | false | false | nct.html.plugin |
| Label Fields | Auto Complete Label Field | false | false | nct.html.plugin |
| Label Fields | Date Picher Label Field | false | false | nct.html.plugin |
| Label Fields | Text Label Field | false | false | nct.html.plugin |
| Label Fields | Text Area Label Field | false | false | nct.html.plugin |
| Label Fields | Checkbox Label Field | false | false | nct.html.plugin |
| Label Fields | File Upload Label Field | false | false | nct.html.plugin |
| Label Fields | Form Submit Button | false | false | nct.html.plugin |

> For Step-2 assembly **don't touch `virtualPlugins`** — take them from `empty` as-is. New pages
> reference existing names (`layout="Nct layout"`) and/or carry a materialized copy of the layout node
> in their own parsis.

---

## Other layout plugins (for reference)

| pluginName | Class/purpose | Key properties |
|---|---|---|
| `nct.label.plugin` | Text label (form label, header). `NctLabelPlugin extends LocalizedHeaderPlugin`. | `text` (LOCALIZED_STRING), `tagName` (STRING, **default `"p"`**), `className`, `styleName`, `tagProperties` |
| `nct.image.plugin` | Image. | `url` (STRING, supports `abs(...)`), `width`/`height` (INTEGER), `tooltip`/`description` (STRING), `className`, `styleName`, `tagProperties` |
| `nct.html.plugin` | HTML container (grids, label fields, Card). | `html` (STRING with `<plugin>`), `className`, `styleName`, `tagProperties`, `reuseItems` |
| `html.plugin` | Top-level HTML container (page layout). | same + `editorHeight`/`editorWidth` |
| `nct.parsis.plugin` / `parsis.plugin` | Content zone (see "Parsis"). | `isParsis`, `reuseItems`, `minHeight`, `emptyPlaceholder`, `style` |
| `nct.link.plugin` / `nct.label.link.plugin` | Link / label-link. | `link` (LOCALIZED), `params` (LOCALIZED), `internal` (BOOLEAN, default `true`), `identifier` (the **destination** content node for an internal link — not the link node's own id; only used when `internal:true`), `style`, `className` — plus `label` (LOCALIZED) for the label-link variant (**not** `text`/`url`; see [14 §1.6](14-plugin-catalog-all.md)) |
| `nct.help.plugin` | Help icon with a message (the "?" tooltip beside a generated field label). | `message` (LOCALIZED), `helpSettings` (JSON) |
| `global.replacement.plugin` | Global replacements plugin (visual `@PluginConfig`, `isBehaviour=false`; in `empty` — 2 nodes inside the pages' content parsis, `nct.parsis.plugin` `id="parsis"`). | `className`, `styleName`, `tagProperties` |

**`tagName` on `nct.label.plugin`:** allowed values — `[h1, h2, h3, h4, h5, h6, p, span, i, label,
small]`, **default `"p"`** (`LocalizedHeaderPropertiesBuilder.java`; runtime fallback to `"p"` when
empty — `LocalizedHeaderPlugin.java`). In exports you see `label`/`h5`/`span` — these are specific
set values, not the default. Generated Generate-fields labels get `tagName="label"` explicitly
(`nct-ui/.../form/generate/FormFieldsGenerator.java`). **A hand-written label without `tagName` renders as
`<p>`, not `<label>`.**

`nct.label.plugin` example (a generated form label, verbatim):

```json
{
  "id": "393360ac-ab79-4a76-a957-46a60dd729ff",
  "identifier": "lbl_gen_slot_4143cc62_2_0",
  "uniqueIdentifier": "fbf47d09-411b-4fa5-9213-6f5ae5942857",
  "name": "lbl_gen_slot_4143cc62_2_0", "pluginName": "nct.label.plugin",
  "properties": {
    "className":  { …STRING "form-label" },
    "tagName":    { …STRING "label" },
    "styleName":  { …STRING "" },
    "tagProperties": { …STRING "" },
    "text":       { …LOCALIZED_STRING {"en_US":"Description","ru_RU":"Описание"} }
  }
}
```

---

## Plugin = `@PluginConfig` (mrjun) + optional `@NctPlugin` (nct-ui)

> 📚 **The full catalog of all `pluginName`s one by one** (content/layout, `action.button`, `chart.js`,
> `global.replacement`, PDF/mail, all `admin.*`/system — with class, config slot, and node example) —
> [14-plugin-catalog-all.md](14-plugin-catalog-all.md). Below — how the annotation itself is structured.

A plugin's identity (its `pluginName`) is defined by the annotation **`@PluginConfig`** (mrjun
`...cms.kicker.utils.PluginConfig`): `pluginName`, `displayName`, `group`, plus `siteTemplate`,
`renderBodyOnly`, `hideInKicker`, `editBorderSelector`, `defaultPropertiesBuilder`. Example:
`NctLabelPlugin.java`. A separate nct-ui annotation **`@NctPlugin`** carries only `icon` (default
`"lnr-cog"`, Linear Icons), `canDelete` (default true), `projectTypes` (default
`{ORGANIZATION_MANAGER, PRODUCTS_MANAGER, REPORT}` — exactly `REPORT`, not `REPORT_APP`). Example:
`NctLabelPlugin.java`. **Don't confuse them** — the registry is built by `@PluginConfig.pluginName`.

### Full catalog of `pluginName` (64 nct-ui `pluginName`s + 2 mrjun: `parsis.plugin`, `html.plugin` — the authoritative list)

Below — all the real `pluginName`s from nct-ui (`@PluginConfig`). Lines with `sic` contain a **real typo
in the code** — keep it verbatim. These are registry keys; the "corrected" spelling doesn't resolve.

**Page / containers:** `siteMapPage`, `nct.parsis.plugin`, `parsis.plugin` (mrjun), `html.plugin`
(mrjun), `nct.html.plugin`, `nct.tab.plugin`, `nct.label.plugin`, `nct.label.link.plugin`, `nct.link.plugin`,
`nct.image.plugin`, `nct.help.plugin`, `global.replacement.plugin`.

**Template chrome (`site.*`):** `site.header.plugin`, `site.footer.plugin`, `site.kicker.plugin` (left menu),
`site.right.kicker.plugin`, `site.breadcrumb.plugin`.

**Tables (config in `properties.model`):** `crud.table.plugin`, `crud.tree.plugin`,
`process.table.pluin` **(sic — "pluin")**.

**Forms and form groups:** `dynaform.form.plugin`, `dynaform.form.groups.plugin`,
`dynaform.form.groups.landingplugin`, `dynaform.filter.form.plugin`, `dynaform.filter.submit.button.plugin`,
`dynaform.context.list.plugin`, `dynaform.list.item.plugin`.

**Form controls (extends `BaseFormControl<FormControlSettings>`; config in `properties.settings`):**
`dynaform.form.text.field.plugin`, `dynaform.form.textarea.field.plugin`,
`dynaform.form.rimm.drop.down.field.plugin`, `dynaform.form.rimm.autocomplete.field.plugin`,
`dynaform.form.datepicker.field.plugin`, `dynaform.form.file.upload.field.plugin`,
`dynaform.form.comments.field.plugin`, `dynaform.form.list.field.plugin`,
`dynaform.form.tree.picker.plugin`, `dynaform.form.gantt.chart.plugin`, `action.button.plugin`.

**Workflow / processes:** `workflows.plugin`, `bpmn2modeler.plugin`, `processes.selectedplugin` (the process
list — one self-contained master-detail node, list + detail together; see the legacy note below for
`processes.plugin`).

**Calendar:** `calendar.plugin` (config in `properties.model`; registered, but not covered field-by-field in this
library — catalogued in [14-plugin-catalog-all.md](14-plugin-catalog-all.md)).

**Rules:** `executor.rule.list.plugin`, `executor.rule.script.plugin`.

**Data / integration / DB:** `dynamic.cruds.plugin`, `admin.integrations.list.plugin`,
`admin.sources.plugin`, `database.management.plugin`, `ontology.viewer.plugin`.

**Queries / reports / charts:** `admin.queries.plugin`, `admin.query.plugin`, `query.results.plugin`,
`admin.schedulers.plugin`, `chart.js.plugin`, `report.pdf.templates.plugin`,
`messaging.mail.templates.plugin`.

**Admin / other:** `admin.user.management.plugin`, `admin.rolegroup.management.plugin`,
`admin.projects.plugin`, `admin.organizations.plugin`, `admin.localization.plugin`,
`project.settings.plugin`, `project.template.management.plugin`, `discovery.plugin`,
`user.profile.plugin`, `audit.log.list.plugin`.

> **Nonexistent plugins** (don't invent them — they're in no repository and no export):
> `FormCreationPlugin`, `FormEditPlugin`, `FormFieldPlugin`, `FormSubmissionHistoryPlugin`,
> `ContextSelectorPlugin`, `SystemSettingsPlugin`. Friendly names like `ChartPanel`/`ContentPanel`/
> `ProcessTable` are also not `pluginName`s; static content = `nct.html.plugin`.
>
> **Separately — the legacy PDF pair `pdf.report.plugin`/`pdf.report.page.plugin`.** This is NOT a fabrication: a
> node of each is carried over into practically every project (they have `layout="portrait"` — the PDF orientation,
> see above about "portrait"). But no class declares these names via `@PluginConfig`, so on the current code they
> render as `mrjun.plugin.not.found`. **The current PDF plugin is `report.pdf.templates.plugin`** (pdfme,
> `@PluginConfig` present — `PdfTemplatesPlugin.java`); write new nodes under it.
>
> **Separately — the legacy `processes.plugin`.** Same story: a node of it survives in the baseline admin scaffold
> (on the `Processes` page, beside a live `processes.selectedplugin` sibling), but **no class declares that name
> via `@PluginConfig`** on the current platform, so it too renders as `mrjun.plugin.not.found`. The old two-plugin
> layout it belonged to (a list node firing an event at a sibling diagram node) is gone. **The process list plugin
> to author is `processes.selectedplugin`** (`ProcessSelectedPlugin.java`) — one self-contained master-detail node.

**What dominates a real tree** (run `jq '.. | .pluginName? // empty' branches.json | sort | uniq -c | sort -rn`
on your own export): the wrappers win by a wide margin — `nct.html.plugin`, `nct.label.plugin` and
`nct.parsis.plugin` are several times more numerous than anything else, because every form field is a label +
control inside an `mb-3` wrapper. Then come the form controls (`dynaform.form.text.field.plugin`,
`dynaform.form.rimm.drop.down.field.plugin`, `dynaform.form.textarea.field.plugin`), then one of each
`site.*` chrome plugin, `html.plugin`, `parsis.plugin` and `siteMapPage` **per page**. The business plugins you
actually author (`crud.table.plugin`, `dynaform.form.plugin`, `dynaform.form.groups.landingplugin`,
`chart.js.plugin`) are an order of magnitude rarer, `nct.tab.plugin`/`dynaform.filter.form.plugin` rarer still,
and almost every admin/report plugin is a singleton. **A tree whose wrapper count is not far above its control
count means the forms were not really laid out.**

---

## How to construct from scratch — recipe

Task: add a new business page "Invoices" with a CRUD table, accessible only to
authenticated users, to the project. Below — the exact sequence of nodes (mark the placeholder values for UUIDs
as your own; don't change `pluginName`/structure).

**Step 1. Create a `siteMapPage`** as a child of the needed container (e.g. under a business section in
`rootContent.children`). `order` — the next free one among siblings; `alias` — the page's URL segment, **required**
(a page without one is unreachable — see the properties table above).

```json
{
  "id": "PAGE-ID-uuid",
  "identifier": "PAGE-IDENTIFIER-uuid",
  "uniqueIdentifier": "PAGE-UNIQUE-uuid",
  "name": "Invoices",
  "alias": "invoices",
  "pluginName": "siteMapPage",
  "isBehaviour": false, "active": true,
  "treeOpened": false, "treeDisabled": false, "treeSelected": false,
  "includedInParsis": false,
  "order": 1,
  "branchId": "BRANCH-ID-uuid",
  "childPluginAdded": false,
  "virtualContent": false,
  "properties": {
    "Redirect":        { "key":"Redirect","propertyType":"STRING","required":false,"hidden":false,"stringValue":"","localizedStringValue":{},"arguments":{},"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel" },
    "layout":          { "key":"layout","propertyType":"STRING","required":false,"hidden":false,"stringValue":"Nct layout","localizedStringValue":{},"arguments":{},"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel" },
    "isParsis":        { "key":"isParsis","propertyType":"BOOLEAN","required":false,"hidden":false,"booleanValue":false,"localizedStringValue":{},"arguments":{},"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseCheckboxFieldPanel" },
    "pageTitle":       { "key":"pageTitle","propertyType":"LOCALIZED_STRING","required":false,"hidden":false,"localizedStringValue":{"en_US":"Invoices"},"arguments":{},"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseLocalizedTextFieldPanel" },
    "pageDescription": { "key":"pageDescription","propertyType":"LOCALIZED_STRING","required":false,"hidden":false,"localizedStringValue":{"en_US":"Invoices"},"arguments":{},"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseLocalizedTextFieldPanel" }
  },
  "roleAccess": {
    "publicReadAccess": false,
    "authenticatedUserAccess": true,
    "accessors": { "admin": {"view":true,"edit":true,"advancedEdit":true}, "nct_author": {"view":true,"edit":true,"advancedEdit":true} },
    "roleGroupAccessors": {}
  },
  "children": [ /* Step 2 */ ]
}
```

**Step 2. Inside the page — a `parsis.plugin` `siteMapPageParsis`** (required, exactly one):

```json
{
  "id": "SMPP-ID-uuid",
  "identifier": "siteMapPageParsis",
  "uniqueIdentifier": "SMPP-UNIQUE-uuid",
  "name": "parsis", "pluginName": "parsis.plugin",
  "isBehaviour": false, "active": true, "includedInParsis": false,
  "order": 0, "branchId": "BRANCH-ID-uuid", "virtualContent": false,
  "properties": {
    "isParsis": { "key":"isParsis","propertyType":"BOOLEAN","booleanValue":true,"localizedStringValue":{},"arguments":{},"required":false,"hidden":false,"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseCheckboxFieldPanel" },
    "className": { "key":"className","propertyType":"STRING","stringValue":"","localizedStringValue":{},"arguments":{},"required":false,"hidden":false,"fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel" }
  },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true, "accessors": {}, "roleGroupAccessors": {} },
  "children": [ /* Step 3 — variant A */ ]
}
```

**Step 3. Inside `siteMapPageParsis` — the layout `html.plugin`.** Two valid paths:

- **(A) Materialize** (recommended, deterministic): copy the "Nct layout" layout node in full
  from a **content/table/landing** page (in `empty` → the `Sources` page; in an authored project → any list page or the `Landing`).
  This is a node `pluginName="html.plugin"`, `identifier="fdcdca35-9820-426a-bd7e-ce7e36a6fd22"`, whose `html`
  contains `<plugin id="parsis" name="nct.parsis.plugin">`, and whose `children` are nodes
  `logo-plugin`/`header`/`footer`/`breadcrumb`/`left-nav`/`right-kicker` + **an `nct.parsis.plugin`
  `identifier="parsis"`**. Place it as the sole child of `siteMapPageParsis`.
  > ⛔ **Only the CONTENT flavor of `fdcdca35` has the `id="parsis"` hole — copy `fdcdca35` ONLY from a
  > content/table/landing page, NEVER from a `*Form` page.** The same identifier `fdcdca35` is materialized on
  > every page of the project, but only the list/landing pages carry the `id="parsis"` hole: form pages
  > (`Invoice Form`, `Declaration Form`, `Ticket Form`, …) carry a **FORM flavor** whose `html` has
  > `<plugin id="form" name="dynaform.form.plugin">` and **NO** `id="parsis"`, and a PDF page carries a
  > **PDF flavor** (`<plugin id="pdf" name="pdf.report.plugin">`).
  > Same identifier, structurally incompatible internals. Before copying, grep the candidate node's `html`: it MUST
  > contain `<plugin id="parsis">`, else Step 4 has no node to receive the table/chart. (See Gotcha #8.)
- **(B) Lazy:** leave `siteMapPageParsis.children` **empty** and rely on the property
  `layout="Nct layout"` (Step 1) — the client-side `SiteMapPage.getParsis()` (`SiteMapPage.java`) on
  the first render clones the vp "Nct layout" into parsis. The export files always carry (A); (B) is convenient if you
  don't want to duplicate the large layout node, but then the result depends on the presence of a vp named "Nct layout".
  > ⛔ **(B) is valid ONLY for a page you will populate LIVE in the authoring UI — NEVER for a self-contained import
  > that must render business content; use (A).** Under (B) the inner `nct.parsis.plugin id="parsis"` **does NOT exist in
  > the export** — the platform clones the `"Nct layout"` vp only on first live render, and that vp is **CHROME-ONLY**
  > (its `content.children` is `[]` — open the vp and see), so the cloned inner parsis materializes
  > **EMPTY**. Step 4's filter/CRUD/chart then have no parent node in the export: the page imports clean but renders as
  > bare chrome with NO business content.

**Step 4. Into the inner `nct.parsis.plugin` (`identifier="parsis"`) place the business plugins** —
the CRUD table and (optionally) the filter:

*(Step 4 presupposes variant (A): the inner `nct.parsis.plugin id="parsis"` must be a materialized node in the export. Under (B) it does not exist — see the ⛔ callout in Step 3B.)*

```json
[
  { "name":"Filter Form", "pluginName":"dynaform.filter.form.plugin", "identifier":"FILTER-uuid", "order":1, … },
  { "name":"CRUD Table",  "pluginName":"crud.table.plugin",           "identifier":"CRUD-uuid",   "order":2, … }
]
```

The CRUD table config — in `properties.model.stringValue` (see [04-crud-table-plugin.md](04-crud-table-plugin.md));
the filter/fields config — `properties.settings.stringValue` (see [02-form-controls-reference.md](02-form-controls-reference.md)).
Result: the page renders the Bootstrap app-shell + navigation on the left + a CRUD table in the center.

**To add tabs** instead of flat content — instead of the CRUD table, place into the inner parsis
an `nct.tab.plugin` node with `properties.tabModel` (JSON `{"items":[{"id":"TAB1-uuid","name":"Stock","order":0,
"iconClass":"","localizedMap":{"name":{"en_US":"Stock"}},"localizedNames":{"en_US":"Stock"}}],"size":"SMALL"}`)
and in its `children` — one `nct.parsis.plugin` per tab with an `identifier` equal to the tab's `id`
(`"TAB1-uuid"`). Each tab's content goes into its parsis. **These per-tab child `nct.parsis.plugin` nodes
must be PRE-POPULATED in the export with the tab's actual content** (in the "Tabs" example above each tab-parsis
already holds a `crud.table.plugin` with its `properties.model`). If you omit a tab's child parsis, the
platform auto-creates it **EMPTY** on first render (`PluginWrapperOfContentPanel` →
`getOrCreateChildContentComponent`, `mrjun-.../PluginWrapperOfContentPanel.java`; identifier =
`modelObject.getId()`, `TabPlugin.java`) — useless for a self-contained import.

> **MODIFY (add/remove a tab).** To **add** a tab: push `{id,name,order,iconClass,localizedMap,localizedNames}`
> to `tabModel.items[]` AND add a sibling `nct.parsis.plugin` in the tab node's `children` whose
> `identifier == that id`, holding the new table + its `properties.model` config. To **remove** a tab:
> delete BOTH (the `items[]` entry and its matching child parsis). Editing only `tabModel` leaves an
> orphan/empty tab (see Gotcha #3).

**To make a 2-column layout inside a tab/parsis** — place an `nct.html.plugin` with
`html` = `<div class="row"><div class="col-md-6"><plugin id="left" name="nct.parsis.plugin"></plugin></div>
<div class="col-md-6"><plugin id="right" name="nct.parsis.plugin"></plugin></div></div>` and in `children` —
two `nct.parsis.plugin` with `identifier` `"left"` and `"right"`.

---

## Gotchas

1. **The `identifier` in `<plugin id="X">` must match the `identifier` of the real child node.** The tag in HTML
   and the node in `children` are the same place, stitched by id (`AbstractHtmlPlugin.java`). Forgot the child →
   "Not valid plugin …".
2. **`siteMapPageParsis` must strictly be `identifier="siteMapPageParsis"`** — otherwise `getOrCreateParsis` creates its own
   parallel one (`nct-ui/.../page/SiteMapPage.java`) and your content "disappears".
3. **Tab ↔ parsis by `id`.** The identifier of the child `nct.parsis.plugin` must be equal to the `id`
   of the `tabModel.items[]` element (`TabPlugin.java`). A mismatch → an empty tab.
4. **`tabModel` captions: in exports the key is `localizedMap.name`, in the code — `localizedNames`.** Specify
   both, so as not to lose the localized captions (exported items typically carry no `localizedNames` key at all).
5. **RoleAccess defaults `publicReadAccess=true`** (`RoleAccess.java`). Omitting `roleAccess` = making the
   page public. For a private one always serialize `publicReadAccess:false` + accessors.
6. **`order` is unique within a parent.** children are sorted by `order` (`ContentDomain.java`
   `@OrderBy`); collisions → undefined ordering of tabs/fields/actions.
7. **layout is a runtime lookup, not just a label.** The client-side `SiteMapPage.getParsis()` reads the property
   `layout` (`SiteMapPage.java`), finds the vp by name and **clones** it into an empty parsis.
   **(A) — a materialized html.plugin child — is REQUIRED for any page whose business content ships in the export.**
   (B) (an empty parsis + `layout="Nct layout"`) only DEFERS materialization to the first live render and always clones an
   **EMPTY content parsis** on import (the `"Nct layout"` vp carries only the chrome; its `content.children` is `[]`) — it
   is valid ONLY for pages populated live in the authoring UI, never for a self-contained generated export. Ship every
   page as (A). The default of the `layout` property on read is `""`.
8. **One layout `identifier` does NOT mean one layout.** In the bundled `empty`, **four** vps share the
   content.identifier `fdcdca35-…` — `"Nct layout"`, `"Main"`, `"Form"` and `"Pdf"` — and every materialized
   page-level layout node in that file carries the same `fdcdca35` too (there is no second layout identifier
   anywhere in the baseline). So the identifier discriminates nothing; **only the `html` string does.**
   ⛔ **Those four share the identifier but have STRUCTURALLY DIFFERENT `html` and are NOT
   interchangeable.** `"Nct layout"`/`"Main"` = **CONTENT** layout (`<plugin id="parsis" name="nct.parsis.plugin">`
   hole — use for tables, landings, charts, tabs). `"Form"` = **FORM** layout
   (`<plugin id="form" name="dynaform.form.plugin">`, **NO** parsis hole — used by individual form pages). `"Pdf"` =
   **PDF** layout (`<plugin id="pdf" name="pdf.report.plugin">`). When reusing/copying, match the page type and verify the
   `html` has the slot Step 4 needs: **NEVER place a `crud.table`/`chart`/`tab` into a Form/Pdf-flavor `fdcdca35` node** —
   there is no `id="parsis"` hole to receive it, so the plugin is orphaned and the page renders the empty form/pdf shell
   (imports clean, renders broken). To see it for yourself, diff the `fdcdca35` node of a `… Form` page (form slot, no
   parsis) against the `fdcdca35` node of the corresponding list page (parsis slot). (See Step 3A.)
9. **Table plugins store config in `properties.model`, not `settings`.** This applies to
   `crud.table.plugin`/`crud.tree.plugin`/`process.table.pluin`. **`chart.js.plugin` is an exception: its config is
   in `properties.Javascript`** (not `model`, `JS_MODEL_NAME="Javascript"`). Form controls — in
   `settings`. Tabs — in `tabModel`. Mixing up the slot = the plugin reads an empty config.
10. **`process.table.pluin` is a real typo** (`pluin`, not `plugin`). Keep it verbatim; the "corrected"
    name doesn't resolve in the registry.
11. **`nct.label.plugin` without `tagName` renders `<p>`, not `<label>`** (`LocalizedHeaderPlugin.java`).
    For a form always set `tagName="label"`. Allowed set: `[h1..h6,p,span,i,label,small]`.
12. **`alias` is a node field, not a property** (`ContentDomain.java`) — **and it is what routes the page.** The
    URL is the `alias` of every ancestor joined down from the root, so a page with no alias is unreachable: its
    nav link lands on the project root and no `Redirect` can target it. Set one on **every** page you author
    (`page add` does it for you — `--alias`, else a slug of the name); only the structural root `Home`
    legitimately has none. Uniqueness of child-page aliases matters for form groups — see
 [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md).
13. **`ContentProperty.fieldPanelClass` can be left null** — the platform substitutes the default by type
    (`ContentDomain.java`). But `propertyType` and the correct `*Value` field are required:
    STRING→`stringValue`, BOOLEAN→`booleanValue`, INTEGER→`intValue`, LOCALIZED_STRING→`localizedStringValue`.
14. **The settings of complex plugins are a JSON string in `stringValue`**, not separate properties
    (`getJsonProperty`, `ContentDomain.java`). You edit JSON inside JSON.
15. **The MCP `PageDto` ≠ the persistent model.** `layoutName`/`navigationGroup`/`sortOrder`/`hasForms`/
    `hasWorkflows` are a read-only projection (`nct-ui/.../mcp/dto/PageDto.java`); they can't be written into the
    export. Write `ContentDomain.properties`.
16. **`isBehaviour=true` / behaviour plugins** don't render visible content; don't confuse them with the visual
    plugins in parsis. (In practice you will not meet one: authored trees carry visual nodes only.
    In particular `global.replacement.plugin` is an ordinary visual `@PluginConfig` plugin
    `isBehaviour=false`, and NOT a behaviour plugin.)
