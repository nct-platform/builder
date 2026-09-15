# 24b · Composition — embedding plugins in HTML, and reusing a component

> ⛔ **`identifier` or `uniqueIdentifier`?** They are different ids with different scopes and swapping them fails silently. The rule, the source that decides it and the measured evidence: [01 — `identifier` vs `uniqueIdentifier`](01-content-model-and-pages.md#-identifier-vs-uniqueidentifier--read-this-before-you-reference-a-node).

> 📐 **Field evidence — the composition vocabulary production actually uses:** [10-visual-design.md](references/10-visual-design.md) · [09-studio-components.md](references/09-studio-components.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> **Scope.** The two tags that live inside an html body — `<plugin>` and `<include>`: the complete grammar of
> both, the tag↔child-node binding contract, how to nest, how one body is composed out of several documents, and
> the four mechanisms for **reusing** a component across pages. Read it whenever an `html.plugin` /
> `nct.html.plugin` must **host** something — a chart grid, a CRUD table under a custom header, a form-field
> slot — whenever a body has grown too big for one string, or whenever you catch yourself about to copy-paste a
> component onto a second page.
> This is the composition half of [24](24-html-component-studio.md); that doc owns `studioModel`, the `ctx`
> runtime, rules/BL calls and breadcrumb actions.
> **Not here:** theme tokens and CSS scoping → [24a](24a-theming-and-dark-mode.md); server-paged tables drawn
> by your own JS → [24c](24c-html-data-tables-and-paging.md); how to lay a component out across documents and
> scripts, and when splitting is worth it → [24d](24d-html-component-structure.md); the content tree, pages and
> the cloning trap → [01](01-content-model-and-pages.md).

| | |
|---|---|
| Parser | `AbstractHtmlPlugin.constructListModel()` — Jsoup + a sentinel split, **not** a regex — over the html **after** `<include>` expansion |
| Renderer | `AbstractHtmlPlugin.initPluginContent()` — a `ListView` alternating raw-HTML `Label`s with `PluginWrapperPanel`s |
| Tag → node | `PluginUtils.getOrCreateChildContentComponent` (VP variant: `getOrCreateChildContentForVirtualPlugin`; behaviours: `getOrCreateChildContentBehavior`) |
| Config slot | `properties.html.stringValue` (STRING) on the `html.plugin` / `nct.html.plugin` node. `<plugin>` tags live **inside that string** — or inside any document it includes |
| Documents | The `html` property is `main.html`; further documents are `studioModel.docs[]`, addressed by **name + extension** (`src="detail.html"`), spliced in server-side **before** the parse (§2.7) |
| Include limits | Depth 20, 500 include tags per expansion, 2 000 000 characters of expanded output; a breach degrades to an HTML comment, never an exception (§2.7) |
| Hosts | `html.plugin`, `nct.html.plugin` and `html.localized.plugin` — all extend `AbstractHtmlPlugin`. `html.localized.plugin` has **no** `studioModel`, so it has no documents and no includes |
| Reuse | `ContentDomain.linkContentIdentifier`, resolved on every read in `PluginPanel.getContent` |

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `node add --parent <html-node> --plugin <pluginName> --identifier <tag-id>` (the child that a `<plugin id>` tag
> binds to — **always pass `--identifier`**, the default is a fresh uuid and the slot then renders blank),
> `node add --parent <html-node> --plugin nct.parsis.plugin --identifier <slot-id>` (a drop-zone slot),
> `node set-model` / `node set-settings` / `node set-studio` for the embedded child's own config,
> `find --plugin nct.html.plugin`, `tree --all`, `show node <id>`.
> ⚠️ There is **no** command that writes `properties.html`, **no** command that writes `studioModel.docs[]` (so
> none that writes an `<include>` either) and **no** command for virtual plugins / `linkContentIdentifier` — the
> html string, the documents and the reuse wiring are hand-edited JSON (§2.6, §2.7, §6.6), and `validate` checks
> the include **graph** but never expands it (§2.7).
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`,
> then `mrjun.py pack <dir> out.mrjun`.

---

## 1 · The mental model — an html body is a LAYOUT that hosts plugins

An `nct.html.plugin` node is not "a block of static markup". It is a **layout host**: the platform parses its
`html` string, and every `<plugin>` tag inside it is replaced at render time by a **real, live plugin instance**
whose configuration lives in a **child content node**.

```
nct.html.plugin  "Dashboard shell"        properties.html = "<div class=row> … <plugin id=kpi1 name=chart.js.plugin/> … </div>"
├── chart.js.plugin   identifier="kpi1"   properties.Javascript = { … the chart model … }
├── chart.js.plugin   identifier="kpi2"   properties.Javascript = { … }
└── nct.parsis.plugin identifier="main"   (a drop zone — whatever you put under it renders here)
```

Two strings — the tag's `id` and the child's `identifier` — are the entire binding. Nothing else connects them:
not a wicket id, not a DOM id, not an order, not a uuid.

**Why this matters for a builder.** It is the mechanism that lets you compose a screen out of **your own shell +
platform plugins you did not have to write**. A custom dashboard that hand-draws nine KPI boxes is nine
hand-written fetch/format/theme problems; the same dashboard as an html shell with nine
`<plugin name="chart.js.plugin">` tags is nine *configured* charts that already page, already theme, already
localize their captions, already cross-filter ([22](22-charts-params-and-filters.md)). The best manager
dashboards built this way are exactly that: a Bootstrap grid with **zero** data JS (the studio script calls
neither `ctx.callRule` nor `ctx.callBl`) hosting the embedded charts.

The same mechanism is what the platform itself runs on. The page **Layout** is an `html.plugin` whose html
addresses seven children by name; the generated form grid is a chain of html plugins and parsis slots
([03](03-generate-fields-from-crud.md)); a filter-form cell is an html plugin holding a label + a field
([04](04-crud-table-plugin.md)). If you understand this section you understand how every page in the product is
assembled.

**Rendering is a WRITE.** `PluginWrapperPanel` resolves its plugin through `getOrCreateChildContent`, which
`contentService.save(...)`s a brand-new child when the tag has no matching node. So
**opening the page in a browser mutates the content tree.** A tag whose child you forgot to author does not
error — it silently materialises an empty one.

---

## 2 · The `<plugin>` grammar, complete

### 2.1 What the parser actually does

`AbstractHtmlPlugin.constructListModel()`, in order:

1. **Expand `<include>`** — every `<include src="…html">` in the body is replaced, **server side**, by the text of
   the named document, recursively. This is a textual splice and it happens **before anything is parsed**, so a
   `<plugin>` tag that arrives from an included document is indistinguishable from one you typed here (§2.7).
2. **Cache probe** — a **static, never-cleared** `HashMap` keyed by the whole **expanded** html string. See the
   trap in §8.3.
3. **Parse** — `Jsoup.parse("<div>" + htmlString + "</div>")`, then `doc.body().children()`. Note
   the injected wrapper `<div>`: it ends up in the rendered output.
4. **Select root plugins** — every `<plugin>` element that has **no `<plugin>` ancestor**.
   A nested one is dropped entirely (§5) — including one an `<include>` brought in (§2.7).
5. **Split** — each root `<plugin>` is replaced by a per-JVM random sentinel tag and the serialized markup is
   split on it. The fragments and the plugins are then interleaved into one
   `ListView`, so the rendered output is `html-fragment, plugin, html-fragment, plugin, …`.
6. **Read attributes** and cache the result.

Each fragment renders as a raw `Label` with `setEscapeModelStrings(false)` — your HTML is emitted
verbatim. Each plugin renders as a `PluginWrapperPanel` that resolves the child node and instantiates
the plugin reflectively (`PluginUtils.createPlugin`).

> ⚠️ **Your surrounding HTML is re-serialized by Jsoup, not passed through.** Verified by driving the parser
> directly (the CMS library and the host application pin different jsoup versions — 1.12.1 and 1.17.2 — and the
> behaviour below is identical on both): input
> `<div class="mb-3">\n <plugin …/>\n <table><tr><td><plugin …/></td></tr></table>\n</div>\n<p>tail<b>x</p>`
> comes back **pretty-printed and re-indented**, wrapped in the extra parse `<div>`, with a `<tbody>`
> synthesized inside the table and the unclosed `<b>` auto-closed. Consequences: never rely on exact whitespace
> (e.g. `white-space: pre` content), never ship deliberately malformed markup, and expect an extra block-level
> `<div>` around your body. A `<plugin>` inside `<td>` **does** survive — jsoup does not hoist unknown elements
> out of a cell.

### 2.2 Attributes on `<plugin>`

| Attribute | Meaning | Required |
|---|---|---|
| `id` | The **child node's `identifier`** (the platform also copies it into the node's `name`). Not a wicket id, not a DOM id. Missing ⇒ `""`, so every id-less tag in one body collides on identifier `""` | **yes, in practice** |
| `name` | The child node's **`pluginName`**. Must be a plugin registered for the tenant's template. Also the `message` sentinel (§2.5) | **yes** |
| `vp` | A **virtual-plugin id** (`VirtualPluginDomain.id`). Non-empty ⇒ the VP resolution path (§6.3) | no |
| anything else | **Ignored.** There is no `class`, `style`, `order` or `wicket:id` attribute on a `<plugin>` tag | — |

Both spellings render identically and both ship in real exports:
`<plugin id="x" name="p"></plugin>` and `<plugin id="x" name="p"/>`. Jsoup lowercases tag and attribute names,
so `<PLUGIN ID="x" NAME="p"/>` also works — do not rely on it, write lower-case.

### 2.3 `<prop>` / `<property>` — direct children only

Selected with `plugin.select(":root > property,:root > prop")` — **direct children of the tag only**;
one wrapped in a `<div>` is invisible. Parsed by `initPluginProps`:

| Attribute | Meaning |
|---|---|
| `name` | The property key on the child node |
| `type` | `PropertyType.of(...)` — an **exact** enum-name match. Legal: `BOOLEAN, LONG, INTEGER, FLOAT, DOUBLE, BIG_DECIMAL, STRING, LOCALIZED_STRING, LOCAL_DATE, LOCAL_DATE_TIME, LOCAL_TIME`. Unknown or absent ⇒ `STRING` |
| `value` | Parsed by `PropertyType.parse`. `LOCALIZED_STRING` ⇒ GSON of a `{locale→text}` map, with `\'` pre-replaced by `"` |
| `override` | `Boolean.valueOf(...)`. **Decides whether the HTML wins over the stored node property** — §4. Absent ⇒ `false` |

⚠️ **Value fallback.** If `value` is absent, fails to parse, or is a STRING that trims to `""`, the property value
becomes **the element's inner HTML**, forced to `STRING`. That is how a multi-line/HTML value is
authored — and also why a typo'd `type="INT"` silently yields a STRING and a mis-typed `value` silently yields
the tag body instead of erroring.

```html
<plugin name="nct.image.plugin" id="logo-plugin">
    <prop name="tooltip" value="Logo" type="STRING"/>
    <prop name="width"   value="90"   type="INTEGER"/>
    <prop name="url"     value="abs(/architectui-html-pro/images/logo-inverse.png)" type="STRING"/>
</plugin>

<plugin id="lbl_x" name="nct.label.plugin">
  <prop name="text" type="LOCALIZED_STRING" value='{"en_US":"Description","hy_AM":"Նկարագրություն"}'></prop>
</plugin>
```

⚠️ Some shipped exports write `<prop name="x", value="y", type="STRING"/>` with commas — a page Layout written
by an older authoring UI does.
Jsoup folds the commas into attribute *names* and ignores them, so it works by accident. **Write the clean form.**

### 2.4 `<behavior>` — direct children of `<plugin>` only

`plugin.select(":root > behavior")`, attributes `id` and `name`, with its own
`<prop>`/`<property>` children; each becomes a `behaviour=true` child node
(`PluginUtils.getOrCreateChildContentBehavior`) attached by `PluginPanel.initBehaviors()`.

> ⚠️ **There is exactly ONE registered behaviour in the whole platform** — `background.image.behavior`
> (a repo-wide search for the `@PluginBehaviorConfig` annotation returns that one class). Unless you are setting
> a background image, you will never write a `<behavior>` tag. An unknown `name` throws while the wrapper builds
> the plugin and degrades to the literal text `Not valid plugin <name>`.

### 2.5 `name="message"` — the resource-bundle pseudo-plugin

```html
<plugin name="message" id="some.bundle.key">Fallback text</plugin>
```

This is **not a plugin**. It renders `getString(<id>, null, <tag inner HTML>)` with
`setEscapeModelStrings(true)`: a Wicket resource-bundle lookup keyed by the `id`,
defaulting to the tag body, HTML-escaped. No child node is created. (It is also the only place the parser keeps
a tag's inner HTML at all.)

> ⚠️ **Do not reach for this in a `.mrjun`.** The keys resolve against Wicket `.properties` bundles that ship
> with the application — a project export cannot add one, so you always get the fallback text and a
> single-language screen. For project text use `nct.label.plugin` with a `LOCALIZED_STRING` `text` property
> (§2.3) or a localized property on the plugin itself → [20](20-localization.md).

### 2.6 The `html` property envelope

`mrjun.py node add` creates the node and the baseline `className`/`styleName`/`tagProperties` slots, but it does
**not** create `html` (there is no `--html` argument). Add it by hand, exactly like a real node — the shape below
is the one the platform itself writes for a generated form-grid row:

```json
"html": {
  "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
  "arguments": {},
  "key": "html",
  "stringValue": "<div class=\"row\">\n  <div class=\"col-md-3\">\n    <plugin id=\"gen_col1_4143cc62\" name=\"nct.parsis.plugin\"></plugin>\n  </div>\n</div>\n",
  "localizedStringValue": {},
  "propertyType": "STRING",
  "required": false,
  "hidden": false
}
```

`fieldPanelClass` is cosmetic — the platform overwrites it from the plugin's declared `DefaultProperty` list on
first render (for `html` that is `PropertyBaseHtmlCodeFieldPanel`). The html plugin's own default-property
builder declares exactly four slots — `html`, `reuseItems` (BOOLEAN, default `false` — §8.6), `editorWidth`
(default `"100%"`) and `editorHeight` (default `"700px"`) — and those are the four the platform auto-creates on
first render. `className` / `styleName` / `tagProperties` are the universal baseline STRING slots that every real
node carries (and that `mrjun.py node add` writes for you); `studioModel` is added by the studio, not by this
builder.

> ⛔ **A studio-active node with no `html` property renders EMPTY.** Mechanism: `nct.html.plugin` falls back to
> the classic placeholder `<div>Html content here</div>` only while `studioModel` is empty; as soon as the node
> carries a non-empty `studioModel`, the fallback becomes `""` (matching `docs["main"] = ""`). The mount wrapper
> is still emitted and your scripts still run — into an empty root, so every `ctx.root.querySelector(...)`
> returns `null`. Symptom: a blank area, no placeholder, no import error, and JS that fails on the first
> `null.addEventListener`. Always author `properties.html`, even if it is only the container your JS fills.

### 2.7 · `<include>` — composing a body out of several documents

An html body does not have to be one string. A studio component holds the `html` property **plus** any number of
further documents in `studioModel.docs[]`, and `<include>` splices them into one body before the parser ever runs.

```html
<div class="ord-wrap">
  <include src="head.html"/>
  <include src="table.html"/>
</div>
```

| Aspect | Rule |
|---|---|
| Spellings | `<include src="x.html"/>`, `<include src="x.html"></include>` and `<include src="x.html">` are equivalent. Single quotes, double quotes and unquoted values all parse; tag and attribute case is free — write lower-case |
| Body | **Whitespace only.** `<include src="x.html"></include>` is fine, but real content between the tags is **not** dropped — it survives into the expanded body and renders right after the included document (only the `</include>` itself disappears, in the parse). Never park a placeholder or a fallback inside the tag |
| Attributes | `src` and nothing else. Every other attribute is **ignored** — there is no parameter, condition, wrapper-class or `as` attribute |
| `src` extension | **Required.** `.html` / `.htm` ⇒ a document, `.js` / `.mjs` ⇒ an author script. An extension-less `src` is refused with a warning, not guessed |
| `main.html` | Addresses the plugin's own `html` property. (A `docs[]` entry named `main` is ignored, as before) |

The extension is mandatory because **documents and scripts are two independent name spaces**: one component may
hold a document `report` and a script `report`, and an extension-less `src` cannot choose between them.

**Where it is expanded.** Anywhere in any document — the `html` property and every `studioModel.docs[]` entry.
It is **skipped** (left exactly as written) inside `<!-- … -->`, `<script>`, `<style>` and `<textarea>`. It **is**
expanded inside `<pre>`, so an include you want to *show* as example text must be escaped as
`&lt;include src="…"&gt;`.

**Resolution — one rule**, used identically by the renderer, the cycle check and `mrjun.py validate`:

1. no known extension ⇒ unresolved;
2. the extension selects the name space, and the rest of the `src` is matched **verbatim** against the stored names;
3. if that misses, the **whole** `src` is matched verbatim too — so a document an author literally named
   `report.html` is reachable as `src="report.html"` as well.

A leading `./` is ignored. A slash in a name (`charts/bar`) is a **display folder** in the studio navigator, not a
path: there is no directory traversal, no `..`, and nothing is resolved relative to the including document.
`src` only ever addresses documents of the **same** component — there is **no cross-component include**.

> ⚠️ **Stored names stay extension-less — the extension lives only in the `src`.** `studioModel.docs[].name` and
> `scripts[].name` keep reading `detail`, `charts/bar`, `main`: **no schema change, no migration**, and every
> existing `.mrjun` keeps working untouched. So you store `detail` and write `src="detail.html"`. The studio only
> *displays* the extension (navigators, rename field) and accepts either spelling when renaming;
> `ctx.showHtml` accepts both `'detail'` and `'detail.html'`.

**Expansion is server side and happens BEFORE parsing** — §2.1 step 1. The included text replaces the tag,
recursively, and only then does jsoup see the result. That is the whole point of the feature: a `<plugin>` tag
written in an included document is **indistinguishable** from one written in the main body and becomes a **real,
live child component**, at any include depth. Two consequences to hold on to:

* The child node still hangs off the **hosting `nct.html.plugin` node** — the one that owns the `studioModel`.
  Documents are text, not nodes; there is nothing else to parent a child to, so `node add --parent` always takes
  the hosting node's id no matter which document the tag sits in. The binding contract of §3 is unchanged and
  entirely unaware that includes exist.
* Render order follows the **expanded** text, so moving an `<include>` moves its plugins.

**The `.js` form is a declaration, not content.** `<include src="chart.js"/>` renders nothing at all; it states
that the named script belongs to this component's program — and its presence switches script selection into
include mode:

| Mode | When | Which scripts run | In what order |
|---|---|---|---|
| **Legacy** (default) | **No** document reachable from `main.html` declares a `.js` include | every **enabled** script | the studio's own up/down ordering |
| **Include** | at least one reachable document declares a `.js` include | **only** included scripts — an included-but-**disabled** script still stays off | the order the `<include src="<name>.js">` tags appear, depth-first from `main.html` |

Nothing built before this feature changes behaviour: with no `.js` include anywhere, you are in legacy mode.
Reachability is a fixpoint — a document reached only through a script's `ctx.include('x.html')` **literal** also
contributes its own script includes. Either way, all selected scripts of one instance still run as **ONE program
in one shared scope** ([24](24-html-component-studio.md) §3).

**Limits, and what a failure looks like.** Depth 20, 500 include tags per expansion, 2 000 000 characters of
expanded output. A breach — and every other failure: a missing target, an extension-less `src`, a cycle — degrades
to an HTML comment `<!-- dokie: … -->` carrying the diagnosis, plus a warning in the studio. It never throws and
never hangs. The catch for a builder: **an HTML comment renders as nothing**, so a broken include is invisible on
the page. You find it in the page source, or by opening the component in the studio.

A **script** `src` is the one to read differently: it renders nothing on the page even when it works, so a missing
`.js` target leaves no hole to find — it shrinks the **program** instead. And the `.js` extension puts the
component in include mode whether or not the `src` resolves, so a single misspelt script include can leave a
component with **no author JS at all** ([24d](24d-html-component-structure.md) §3.2).

> ⚠️ **`mrjun.py validate` resolves the include graph; only the studio sees the expansion.** A cycle is an offline
> **ERROR**, a dangling or extension-less `src` and an enabled-but-never-included script are offline **WARNs**.
> The two that need expansion — an `<include>` inside a `<plugin>`, and a `<plugin id>` duplicated after
> expansion — are reported **only** by the studio, and it saves anyway. Treat those two as your own pre-flight
> list. In the studio only a **document→document cycle** blocks the save; a loop that runs through a script is
> reported (expansion stops at a script, so nothing can recurse), and everything else is reported **and saved
> anyway**.

**Worked example — a shell, a header and a rows document.** Three documents on **one** node; two of them carry a
`<plugin>` tag.

`main.html` — the `html` property, pure layout:

```html
<div class="inv-wrap">
  <include src="head.html"/>
  <div class="inv-body">
    <include src="rows.html"/>
  </div>
</div>
```

`head.html` — `studioModel.docs[]` entry stored as `head`:

```html
<div class="inv-head d-flex align-items-center justify-content-between mb-3">
  <h1 class="inv-h1">&lt;Invoice&gt; register</h1>
  <plugin id="inv_kpi" name="chart.js.plugin"></plugin>
</div>
```

`rows.html` — `studioModel.docs[]` entry stored as `rows`:

```html
<div class="inv-card">
  <plugin id="inv_table" name="crud.table.plugin"></plugin>
</div>
```

What the parser sees is the concatenation, and `inv_kpi` / `inv_table` are ordinary root plugins of the hosting
node. So both child nodes are created against **that** node:

```bash
python3 mrjun.py node add --parent <html-node-id> --plugin chart.js.plugin \
    --identifier inv_kpi   --name "<Invoice> KPI"   --model @kpi.chart.json   --project ./app
python3 mrjun.py node add --parent <html-node-id> --plugin crud.table.plugin \
    --identifier inv_table --name "<Invoice> table" --model @table-model.json --project ./app
```

Same `--parent` for both, because `head.html` and `rows.html` are documents of that node, not nodes of their own.

> ⛔ **An `<include>` inside a `<plugin>` tag brings in components that are silently DROPPED.**
>
> **Mechanism:** expansion runs first, so the included markup really does land *inside* the `<plugin>` element;
> the parser then collects only `<plugin>` elements with **no `<plugin>` ancestor** (§5), so every plugin the
> include carried in vanishes — no child node, no error, no log line. The outer plugin renders normally, which is
> what makes it hard to see.
> **Symptom:** the region you expected inside the hosted plugin is simply absent, and the child nodes you authored
> for those tags sit in the export unreferenced and undrawn.
> **Caught by `validate`?** **No.** (The studio reports it as a warning and saves anyway; the nesting rule itself
> is enforced only by the renderer, silently — §5.)
> **Fix:** move the `<include>` out from between `<plugin>` and `</plugin>`. If you genuinely need a second level,
> use **node depth**: give the outer plugin its own `nct.html.plugin` / `nct.parsis.plugin` child and let *that*
> node's html do the including (§5).
> **Rule:** an `<include>` belongs at document level. Never between a `<plugin>` open and close tag.

> ⛔ **INCLUDING THE SAME DOCUMENT TWICE DUPLICATES ITS `<plugin id>`s — AND BOTH TAGS RESOLVE TO ONE CHILD NODE.**
>
> **Mechanism:** expansion is textual, so two `<include src="rows.html"/>` tags produce two copies of every tag
> inside `rows.html`. Two tags with the same `id` both render and both resolve to the **same** `ContentDomain`
> (the lookup returns the first identifier match — §8.1): one configuration driving two components, in violation
> of the one-tag-one-node assumption the binding contract of §3 is built on.
> **Symptom:** two slots that always show the *same* thing; editing one child node changes both. If the
> duplicated tags ever differ in `name=`, every render flips `pluginName` and clears `properties` — permanent
> config thrash.
> **Caught by `validate`?** **No.** The duplicate only exists *after* expansion and nothing offline expands; it
> also keys refs by identifier, so duplicates collapse. The studio warns after expansion and saves anyway.
> **Fix:** keep a document that carries `<plugin>` tags a **singleton** — include it exactly once, or move the
> tags into `main.html`. A plugin-free document (pure markup: a card frame, a legend, an empty-state block) is
> freely reusable as often as you like.
> **Rule: count `<plugin>` ids on the EXPANDED body, not per file.**

---

## 3 · ⛔ The binding contract

> ⛔ **`child.identifier` MUST equal the tag's `id`, and `child.pluginName` MUST equal the tag's `name`.**
>
> **Mechanism.** `getOrCreateChildContent` walks `parent.getChildren()` and matches on
> `Objects.equals(child.getIdentifier(), identifier)`. Two divergences, two different
> disasters:
>
> **(a) identifier mismatch** → no match → the platform builds a **blank** child from the plugin's default
> properties and saves it. Your authored node stays in the tree, is exported, and is **never
> drawn**. What the user sees: **an empty slot** — an empty card, a missing chart, a form field that isn't
> there — while import, `pack` and the browser console all stay clean. On a page **Layout** this strips the
> chrome off the whole page (a real incident: a clone helper regenerated identifiers and every page lost its chrome after
> regenerated identifiers, with `validate` reporting 0 errors at the time — which is why the check below now
> exists).
>
> **(b) pluginName mismatch** → matched, then `child.getProperties().clear(); child.setPluginName(pluginName);`.
> The **html wins**: your `model` / `settings` / `studioModel` / `html` blob is
> gone and the node reverts to the type named in the tag. A form control silently loses its
> scope/crudAlias/fieldExpression and stops mapping to anything. Changing a node's plugin type is therefore a
> **two-place edit**: the node *and* the `name=` of its tag.
>
> **Does `validate` catch it?** Yes — its html-plugin-refs check, and it is the only
> offline gate that looks at the html↔children relationship. Precisely:
> * tag `name=` ≠ child `pluginName` → **ERROR**;
> * dangling tag id **while** the node holds an unreferenced child of that same pluginName → **ERROR** (the
>   regenerated-identifier signature);
> * dangling tag id with no such sibling → **WARN** — legitimate for a deliberately optional plugin;
> * a child no tag references → **WARN**.
>   It walks only nodes **under a `siteMapPage`** and it does **not** detect duplicate tag ids or
>   duplicate child identifiers (§8.1).

Three consequences worth internalising:

* Set `name` = `identifier` on the child. The platform does `setName(identifier)` itself when it creates one, so
  anything else is noise that the next render may overwrite.
* Identifiers only need to be unique **among the siblings of one parent** — the lookup is
  `parent.getChildren()`. It is perfectly normal — and correct — for dozens of pages to carry nodes with the
  *same* wrapper identifier, one per page.
* An identifier that any html references is **not** a uuid you may regenerate. When you clone a laid-out
  subtree, collect `re.findall(r'<plugin[^>]*\bid="([^"]+)"', html)` over the whole subtree first and preserve
  exactly those.

---

## 4 · ⛔ `<prop>` is a SEED, not a setting

> ⛔ **A `<prop>` only writes a key that does not exist yet.** The merge writes the property only when
> the node has no property under that name — or when the tag carries `override="true"`.
> And on **first** creation the platform immediately creates a key for **every**
> `DefaultProperty` the plugin declares. So from the second render onward, essentially every key the plugin owns
> already exists and **your `<prop>` is dead text**.
>
> What you see: you edit `<prop name="width" value="120"/>` in the html, re-import, and the image is still 90px
> wide — no error, no log line. `validate` does not check it (nothing offline links a `<prop>` to a node
> property).
>
> **Rules.** Real configuration lives on the **child node's `properties`**, not in the tag. Use a `<prop>` only
> to seed a value on a node you are creating in the same breath (or never — just author the property). If you
> genuinely want the html to be authoritative for a key, write `override="true"` and accept that the html then
> re-stamps that property on **every render**, overwriting whatever an author changed in the UI.

Corollary for the `vp=` path: `<prop>` children are **discarded entirely** — the renderer passes no `PluginProp[]`
at all on that branch, and neither does the unknown-`vp` fallback.

---

## 5 · Nesting — you cannot nest tags, you nest NODES

> ⛔ **A `<plugin>` inside a `<plugin>` is silently DROPPED.** Only elements with no `<plugin>` ancestor are
> collected; the nested one survives nowhere except in the tag's inner HTML, which is used **only** for the
> `message` pseudo-plugin (§2.5). No child node, no error, no log —
> **the inner plugin simply does not exist**. `validate` does not flag it (its `<plugin …>` regex treats the
> inner tag as a normal reference and will instead emit a *dangling id* WARN for it, which is the only visible
> smell).

Real nesting is achieved by **node depth**: embed a container plugin and put the next level in **its own** html
(or under its own parsis). Depth is unbounded; each level costs one `ContentDomain` and one Jsoup parse.

**`<include>` does not change any of this.** It composes **documents**; node depth composes **plugins**. Because
expansion is textual and happens before the parse (§2.7), an include can move a `<plugin>` tag into another
document — it can never put one plugin *inside* another, and an `<include>` written between `<plugin>` and
`</plugin>` loses everything it brings in (§2.7). Which to reach for:

| Your problem | Reach for | Cost |
|---|---|---|
| One html string has grown unreadable / two people edit different regions | **`<include>`**: split into documents, splice them from `main.html` (§2.7, §7.5) | none at runtime — same node, same children, **one** parse of the expanded body |
| A hosted plugin must itself contain plugins, or an author must be able to drop content into a region | **node depth**: an `nct.html.plugin` / `nct.parsis.plugin` child with its own html or children | one `ContentDomain` and one extra parse per level |

### Worked two-level example

This is the platform's own generated form grid: an html row → four parsis columns → an html slot per column →
label + field.
Abridged to the load-bearing keys — every `stringValue` shown is the exact shape the platform emits; each node also
carries `id`, `branchId`, `roleAccess`, `isBehaviour`, `treeOpened/Disabled/Selected`, `includedInParsis`,
`childPluginAdded`, `virtualContent`:

```jsonc
{
  "identifier": "gen_row_4143cc62",
  "uniqueIdentifier": "db8ee7a3-053e-4a82-abfc-f83f554fca21",
  "name": "gen_row_4143cc62",
  "pluginName": "nct.html.plugin",
  "order": 0, "active": true,
  "properties": {
    "html": { "key": "html", "propertyType": "STRING", "localizedStringValue": {}, "arguments": {},
      "required": false, "hidden": false,
      "stringValue": "<div class=\"row\">\n  <div class=\"col-md-3\">\n    <plugin id=\"gen_col1_4143cc62\" name=\"nct.parsis.plugin\"></plugin>\n  </div>\n  <div class=\"col-md-3\">\n    <plugin id=\"gen_col2_4143cc62\" name=\"nct.parsis.plugin\"></plugin>\n  </div>\n  <div class=\"col-md-3\">\n    <plugin id=\"gen_col3_4143cc62\" name=\"nct.parsis.plugin\"></plugin>\n  </div>\n  <div class=\"col-md-3\">\n    <plugin id=\"gen_col4_4143cc62\" name=\"nct.parsis.plugin\"></plugin>\n  </div>\n</div>\n" },
    "className":     { "key": "className",     "propertyType": "STRING",  "stringValue": "", "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false },
    "styleName":     { "key": "styleName",     "propertyType": "STRING",  "stringValue": "", "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false },
    "tagProperties": { "key": "tagProperties", "propertyType": "STRING",  "stringValue": "", "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false },
    "reuseItems":    { "key": "reuseItems",    "propertyType": "BOOLEAN", "booleanValue": false, "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false },
    "isParsis":      { "key": "isParsis",      "propertyType": "BOOLEAN", "booleanValue": false, "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false },
    "editorWidth":   { "key": "editorWidth",   "propertyType": "STRING",  "stringValue": "100%", "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false },
    "editorHeight":  { "key": "editorHeight",  "propertyType": "STRING",  "stringValue": "100%", "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false }
  },
  "children": [
    { "identifier": "gen_col1_4143cc62", "pluginName": "nct.parsis.plugin", "name": "gen_col1_4143cc62", "order": 0, "active": true, "children": [ /* … */ ], "properties": { /* className/styleName/tagProperties/emptyPlaceholder */ } },
    { "identifier": "gen_col2_4143cc62", "pluginName": "nct.parsis.plugin", "name": "gen_col2_4143cc62", "order": 1, "active": true, "children": [], "properties": { } },
    { "identifier": "gen_col3_4143cc62", "pluginName": "nct.parsis.plugin", "name": "gen_col3_4143cc62", "order": 2, "active": true,
      "children": [
        {
          "identifier": "gen_slot_4143cc62_2_0",
          "uniqueIdentifier": "8c4b6b55-ff12-42f2-9a80-975f7b1033c0",
          "name": "gen_slot_4143cc62_2_0",
          "pluginName": "nct.html.plugin",
          "order": 0, "active": true,
          "properties": {
            "html": { "key": "html", "propertyType": "STRING", "localizedStringValue": {}, "arguments": {},
              "required": false, "hidden": false,
              "stringValue": "<div class=\"mb-3\">\n  <plugin id=\"lbl_gen_slot_4143cc62_2_0\" name=\"nct.label.plugin\"></plugin>\n  <plugin id=\"fld_gen_slot_4143cc62_2_0\" name=\"dynaform.form.textarea.field.plugin\"></plugin>\n</div>\n" }
          },
          "children": [
            { "identifier": "lbl_gen_slot_4143cc62_2_0", "pluginName": "nct.label.plugin",
              "name": "lbl_gen_slot_4143cc62_2_0", "order": 0, "active": true, "children": [],
              "properties": { "text": { "key": "text", "propertyType": "LOCALIZED_STRING", "localizedStringValue": { "en_US": "Description" }, "stringValue": null, "arguments": {}, "required": false, "hidden": false } } },
            { "identifier": "fld_gen_slot_4143cc62_2_0", "pluginName": "dynaform.form.textarea.field.plugin",
              "uniqueIdentifier": "8abae3c4-b440-447b-b521-80a178de2a70",
              "name": "fld_gen_slot_4143cc62_2_0", "order": 1, "active": true, "children": [],
              "properties": { "settings": { "key": "settings", "propertyType": "STRING", "localizedStringValue": {}, "arguments": {}, "required": false, "hidden": false,
                "stringValue": "{\"scope\":\"CRUD\",\"contextIdentifier\":\"77cd568d-75b0-48e7-8fcc-d760b3a06219\",\"crudAlias\":\"inventoryCount\",\"fieldExpression\":\"description\",\"mandatoryValidationMessages\":{},\"eventComponentMappings\":[],\"conditionalValidations\":[],\"name\":\"Description\",\"filterKey\":\"description\",\"dataClass\":\"java.lang.String\"}" } } }
          ]
        }
      ] },
    { "identifier": "gen_col4_4143cc62", "pluginName": "nct.parsis.plugin", "name": "gen_col4_4143cc62", "order": 3, "active": true, "children": [], "properties": { } }
  ]
}
```

Read the chain: **row html → `<plugin name="nct.parsis.plugin">` → parsis node → (anything, in `order`) → slot
html → `<plugin name="nct.label.plugin">` + `<plugin name="dynaform.form.textarea.field.plugin">`**.

**Which container for the second level?**

| Want | Use | Why |
|---|---|---|
| A fixed structure you control from the html | another `nct.html.plugin` child | you keep markup, classes and grid in one string |
| A **drop zone** whose contents vary (or that an author will fill in the UI) | `nct.parsis.plugin` child | it renders **all** its children in `order` with no markup of its own; it is the platform's own slot idiom (`siteMapPageParsis`, `form.parsis`, `filter.parsis`) |

⚠️ `nct.parsis.plugin` is declared `hideInKicker = true` — it is invisible in the authoring
palette and only ever appears because an html tag or the platform created it.

---

## 6 · Reusing a whole component

You built one `nct.html.plugin` that does the job — markup + `studioModel` scripts + CSS. Now a second page (or
a second slot on the same page) needs it. There are **four** mechanisms and they are genuinely different; picking
the wrong one is how projects end up with six drifted copies of the same widget.

### 6.1 Decision table

| # | Mechanism | What it really is | Edits propagate? | Per-placement config? | Use when |
|---|---|---|---|---|---|
| **a** | **Shared common virtual plugin** — VP with `commonContent:true`, placements are stubs carrying `linkContentIdentifier` | **ONE live node**, N stubs pointing at it (resolved in `PluginPanel.getContent`) | **Yes, instantly, everywhere** | **No** — impossible by construction | The component is the *same thing* on every page: a nav, a logo, a house-styled shell, a KPI console you want to fix in one place |
| **b** | **Per-instance VP** — VP with `commonContent:false`, referenced by `vp="<id>"` or dropped from the palette | A **one-time clone** at first render | **No** — it diverges from that moment | Yes | A *starting template*: the same skeleton, then each page tunes it |
| **c** | **Duplicated child node** — copy the node into each parent | **Independent copies** | **No** | Yes | Two or three placements that were never going to stay identical; anything you must be able to change on one page without touching the other |
| **d** | **Shared LOGIC, not markup** — one component exports `ctx.api`, others call it | Not reuse of markup at all | n/a | n/a | The duplication you actually have is *behaviour* (a formatter, a fetch, a cache), not layout |

**The blunt advice.** For a `.mrjun` build, prefer **(c) copies** for 2–3 placements and **(a) shared** for
"this is one component that lives on N pages". Avoid **(b)** — it looks like sharing and is not, and the `vp=`
attribute is an **authoring-UI path, not an export idiom**: real exports, including large multi-hundred-page
ones, do not use it.

### 6.2 (a) Shared — `commonContent:true` + `linkContentIdentifier`

A node's `linkContentIdentifier` is resolved on **every** content read, not once at import: the platform
looks the target up by its global `uniqueIdentifier` and hands back that node instead. If the target
cannot be found, the link is **cleared and persisted** — the stub silently stops being a stub and starts
behaving as an ordinary empty node, which is what a dangling shared reference looks like at render time.

So the **placed node is a stub**: every property read, every `children` read, every render goes to the *linked*
node, addressed by its global `uniqueIdentifier`. Place the stub on N pages ⇒ N renders of **one live
component**; edit it once and all N change.

**This is not exotic — it is how the platform itself ships the logo and the left nav.** In any real project the
`Logo` (`nct.image.plugin`) and `Nct left nav` (`site.kicker.plugin`) are `commonContent:true` virtual plugins,
and every page carries a **stub** for each: a project with N pages therefore holds ≈N logo stubs and ≈N left-nav
stubs, all resolving to a single live node. Check yours:

```bash
jq '[.. | objects | select(.linkContentIdentifier != null) | .name] | group_by(.) | map({name:.[0], stubs:length})' \
   branches.json
```

> ⛔ **On a linked stub, the node's own `properties` and `children` are DEAD DATA.** `cloneContent` copies the
> properties into the stub *and then* sets the link, so the export looks
> like every placement carries a full config — but `getContent()` never reads it. Edit
> `properties.modelGroups` on a per-page `left-nav` node and **nothing changes**; the render came from the VP's
> content. The toolkit states this in exactly those words and writes quick links to the shared node instead
> (*"the per-page `modelGroups` are DEAD DATA — never read at runtime"*). `mrjun.py validate` does not check it.
> **Rule: to change a shared component, edit `branches[0].virtualPlugins[] → content`, never a placement.**

> ⚠️ **A dangling link self-heals destructively.** If the target `uniqueIdentifier` no longer exists,
> `PluginPanel` logs `SEVERE "Common VP resolution failed"`, **nulls the link and saves the stub**.
> The stub then renders from its own leftover properties — fine for a chrome plugin, **an empty
> component** for anything whose real content lived in `children`. This is not hypothetical: real exports routinely
> ship a handful of dangling links — `footer`/`header` stubs pointing at ids that exist nowhere in the bundle —
> and the offline gates are silent about all of them.

**Where the link gets written** (three places, all verified):

1. `ContentServiceImpl.cloneContent(content, commonVirtual)`:
   `commonVirtual ? setLinkContentIdentifier(content.getUniqueIdentifier()) : setLinkContentIdentifier(content.getLinkContentIdentifier())`.
   Every palette drop calls it with `vp.getCommonContent()` (the plugin palette, the site-authoring panel and the
   html editor's plugin chooser all go through it).
2. The `vp=` attribute path (§6.3).
3. The authoring action *"Save as Common Component / choose existing"* (`NctPluginUtils`),
   which also repoints every sibling that still carried the old link. Its inverse is *"Detach from
   virtual template"*: copy children + properties in, `setLinkContentIdentifier(null)`.

> Same rule as §6.2 for the **Role access** item in that menu: on a linked component it edits the **shared**
> node, so the access applies to every placement. Detach first if one placement must differ — and note that a
> per-placement grant is ignored under an HTML layout anyway
> ([01](01-content-model-and-pages.md) §"Hidden content").

### 6.3 (b) The `vp="<uuid>"` tag form — and why it is a trap for exports

```html
<plugin name="site.kicker.plugin" vp="06e1f176-6e62-4f66-ac76-a4bcb54b38ae" id="site.kicker.plugin.1"/>
```

Emitted by the authoring UI's plugin chooser (`PluginSnippetBuilder`, which writes an `id` sentinel that the
editor JS replaces client-side with `<pluginName>.<N+1>`). Resolution —
`PluginUtils.getOrCreateChildContentForVirtualPlugin`:

* **Fast path**: an existing child whose `identifier` matches **and** whose `__vpId` property
  equals `vp` is returned as-is.
* **`commonContent:true`**: a stub is created with
  `setLinkContentIdentifier(vp.getContent().getUniqueIdentifier())` ⇒ mechanism (a), live shared.
* **`commonContent:false`**: `contentService.cloneContent(vp.getContent(), false)` ⇒ **a one-time
  clone**. From then on the placement and the VP are unrelated; editing the VP changes nothing.
* Either way the child gets `identifier`/`name` = the tag id and a marker property `__vpId`.
* **Unknown `vp`** ⇒ a warn and a plain `getOrCreateChildContentComponent` fallback — i.e. a blank
  child of `name=`'s type. `name=` is only a class-lookup hint on this path.
* The VP is looked up **in the same branch**, and **all `<prop>` children are discarded** (§4).

> ⚠️ **Do not author `vp=` in a `.mrjun`.** It couples the html string to a `virtualPlugins[].id` uuid, it is
> invisible to `validate`, its semantics flip entirely on a flag stored somewhere else (`commonContent`), and
> real exports do not use it. Write the resolved shape instead: a normal `<plugin id name>` tag plus either a
> plain child node (c) or a stub child carrying `linkContentIdentifier` (a).

### 6.4 (c) Duplicated child nodes — the honest default

Copy the node (fresh `uniqueIdentifier`, fresh `id`, keep or choose the `identifier`, fix `order` and
`branchId`) into each parent, and make sure each parent's html has a matching `<plugin>` tag. Independent from
the first render.

Real-world scale: on a large project a single wrapper component is routinely copied into dozens of pages, with
`linkContentIdentifier` null on every copy — and those copies **drift**, so what began as one component ends up as
several near-identical html bodies nobody edits together. That is the cost of (c) — priced correctly, it is fine;
assumed to be sharing, it is a bug factory. Audit yours before you rely on it:
`jq '[.. | objects | select(.pluginName=="nct.html.plugin") | .identifier] | group_by(.) | map(select(length>1))' branches.json`.

### 6.5 (d) Reuse the LOGIC, not the markup

Often what repeats is behaviour, not layout. The runtime already has a page-global registry: a component
publishes `ctx.api` and everyone else reaches it by content **identifier**.

```js
// component "<entity>_ui" (the owner of the data)
ctx.api.reload   = load;
ctx.api.getRows  = () => state.rows.slice();

// any other component on the page
const owner = ctx.byName('<entity>_ui');       // the page-global registry, keyed by ctx.name
if (owner) { await owner.reload(); }
ctx.on('<entity>:changed', () => render());    // bus, auto-removed at teardown
ctx.emit('<entity>:changed', { id });
```

`window.Dokie.plugins` is keyed by `ctx.name` and the entry is removed at teardown (only if it is still the same
api object). Full API, lifecycle and teardown rules → [24](24-html-component-studio.md) §3, §6.

⚠️ `ctx.name` is the node's **identifier**, and it falls back to the numeric content id when the node has none —
at which point `ctx.byName('<symbolic>')` returns `undefined` and every cross-component call silently no-ops.
Always author an `identifier` on a studio node (§3), which `node add --identifier` does for you.

### 6.6 ⛔ A shared node reports the SAME `ctx.name` on every placement

> ⛔ **`ctx.name` is the content identifier, resolved through the link — so all shared placements collide in
> `window.Dokie.plugins`.** The plugin derives the studio instance id from `getContent().getIdentifier()`, and
> `getContent()` resolves through `linkContentIdentifier`, so every placement of one shared node reports the
> **same** name. The runtime stores `D.plugins[name] = ctx.api` — **last mount wins**.
> The **wrapper id is not affected**: it is `"dokie-plug-" + getMarkupId()`, a session-scoped Wicket sequence, so
> DOM ids, the CSS scope and the runtime's per-node bookkeeping stay per-placement and the two instances really
> do both run.
>
> What you see: `ctx.byName('<id>')` reaches whichever placement mounted last; a "refresh the other panel"
> button drives the wrong one; teardown of the first instance can `delete D.plugins[name]` out from under the
> second only if the api object still matches (the runtime guards with `===`, so usually it silently leaks
> instead). `validate` cannot see any of this.
> **Mitigation:** for cross-component wiring on a page that shares one node twice, use `ctx.bus` events
> (broadcast, placement-agnostic) rather than `ctx.byName`, or place two *copies* (mechanism c) with distinct
> identifiers.

### 6.7 Authoring a shared component by hand

There is no CLI for this. In `branches.json`:

1. Put the real component **once** in `branches[0].virtualPlugins[]`:
   ```jsonc
   { "id": "<uuid-vp>", "name": "<Component name>", "group": "Common", "commonContent": true,
     "hidden": false, "isLayout": false, "templateNames": ["<tenant template>"],
     "branchId": "<branchId>",
     "content": { "identifier": "<symbolic>", "uniqueIdentifier": "<uuid-target>",
                  "name": "<symbolic>", "pluginName": "nct.html.plugin",
                  "properties": { "html": { … }, "studioModel": { … } }, "children": [ … ] } }
   ```
   (the field list is `VirtualPluginDomain`'s).
2. In each hosting html add a normal tag: `<plugin id="<symbolic>" name="nct.html.plugin"></plugin>`.
3. Under each host node add the **stub** child:
   ```jsonc
   { "identifier": "<symbolic>", "uniqueIdentifier": "<fresh-uuid>", "name": "<symbolic>",
     "pluginName": "nct.html.plugin",
     "linkContentIdentifier": "<uuid-target>",
     "children": [], "properties": { "className": {…}, "styleName": {…}, "tagProperties": {…} },
     "order": 0, "active": true, "branchId": "<branchId>" }
   ```
   The stub needs **no** `html`, no `studioModel`, no children — those are read from the target.
4. Keep `<uuid-target>` alive. If it ever disappears, every stub silently degrades (§6.2).

---

## 7 · Recipes

### 7.1 A chart grid inside a custom shell

The highest-value use of the whole mechanism: you own the layout, the platform owns the charts. Structure of a
manager dashboard done right (an `nct.html.plugin` whose studio script calls neither `ctx.callRule` nor
`ctx.callBl` — **no data JS at all** — hosting eight `chart.js.plugin` children). Pick one prefix per
component (`<pfx>-`, here `dash-`) for every class you invent, so your styles cannot collide with another
component's. (Note the `&lt;…&gt;` in the visible text: a literal `<Screen>` in an html body is parsed by Jsoup
as an unknown *element* and disappears — §2.1.)

⛔ **The card goes on the ROW, never on each chart** — one framed band per group of charts, with the group's
question in its header, and flat charts inside it. The rule and the two reasons behind it are
[22](22-charts-params-and-filters.md) §6A; the short version is that a frame authored into a chart's own `html`
arrives with that chart's second round-trip, so a page of them assembles one lazily-loaded cell at a time, while
this shell is ordinary markup and paints whole in the first frame.

```html
<div class="dash-wrap">
  <div class="dash-head">
    <div><h1 class="dash-h1">&lt;Screen&gt; dashboard</h1></div>
    <plugin id="dash_status_pill" name="chart.js.plugin"></plugin>
  </div>

  <!-- the KPI band: one card, four flat tiles, no header — labelled numbers explain themselves -->
  <div class="dash-row">
    <div class="row g-4">
      <div class="col-md-6 col-xl-3"><plugin id="dash_kpi_1" name="chart.js.plugin"></plugin></div>
      <div class="col-md-6 col-xl-3"><plugin id="dash_kpi_2" name="chart.js.plugin"></plugin></div>
      <div class="col-md-6 col-xl-3"><plugin id="dash_kpi_3" name="chart.js.plugin"></plugin></div>
      <div class="col-md-6 col-xl-3"><plugin id="dash_kpi_4" name="chart.js.plugin"></plugin></div>
    </div>
  </div>

  <!-- a themed band: the header states what its two charts answer TOGETHER -->
  <div class="dash-row">
    <div class="dash-row-h"><plugin id="dash_row_now_h" name="nct.label.plugin"></plugin></div>
    <div class="row g-4">
      <div class="col-lg-7"><plugin id="dash_alert_list" name="chart.js.plugin"></plugin></div>
      <div class="col-lg-5"><plugin id="dash_breakdown"  name="chart.js.plugin"></plugin></div>
    </div>
  </div>

  <div class="dash-row">
    <div class="dash-row-h"><plugin id="dash_row_trend_h" name="nct.label.plugin"></plugin></div>
    <div class="row g-4">
      <div class="col-12"><plugin id="dash_trend" name="chart.js.plugin"></plugin></div>
    </div>
  </div>
</div>
```

Then one child node per tag, config in `properties.Javascript` ([22](22-charts-params-and-filters.md)):

```bash
python3 mrjun.py node add --parent <html-node-id> --plugin chart.js.plugin \
    --identifier dash_kpi_1 --name "<KPI> tile" --model @kpi1.chart.json --project ./app
python3 mrjun.py node add --parent <html-node-id> --plugin nct.label.plugin \
    --identifier dash_row_now_h --name "Band header" --project ./app
```

(`node add` routes `--model` to `chart.js.plugin`'s real slot, `properties.Javascript` — [`tools/README.md`](tools/README.md).)

The band header is a `nct.label.plugin` and not text in this html for one reason: it is the sentence a reader
actually reads, and only a label node has a per-locale `text` map ([20](20-localization.md)). Give it
`tagName:"span"` — the plugin's default tag is `p` (§1.4 of [14](14-plugin-catalog-all.md)), whose
`margin-bottom:1rem` opens a gap under your header row.

> **Own classes or the theme's?** `dash-row` above is your own, so it must take its surface, border and radius
> from theme tokens (⚠️ (1) below). The zero-CSS alternative is the skin's own card — `<div class="main-card mb-3
> card">` + `<div class="card-header">` + `<div class="card-body">` — which follows every skin for free and is
> what a platform dashboard uses ([22](22-charts-params-and-filters.md) §6A). Reach for your own prefix when the
> band needs something the theme's card cannot express, not by default.

⚠️ Two mistakes to design out of a shell like this. **(1) Do not put the shell's CSS in an inline `<style>`
block inside the `html` property.** That block is global — it is not scoped like `css.byTheme` — so it leaks onto
every other component on the page, and any literal hex in it (`background:#fff`) makes the dashboard white on the
four dark skins. Put it in `studioModel.css.byTheme` and use theme tokens ([24a](24a-theming-and-dark-mode.md));
`mrjun.py validate` WARNs when it finds an inline `<style>` in an `nct.html.plugin`'s html.
**(2) Do not build the band grid with `h-100`** — ArchitectUI redefines it as `height:100vh`, not `100%`, so
every band becomes a full viewport tall; the full-height helper is `he-100`
([24a](24a-theming-and-dark-mode.md) §7.1).

### 7.2 A `crud.table.plugin` under a custom header

```html
<div class="x-shell">
  <div class="x-shell-head d-flex align-items-center justify-content-between mb-3">
    <h2 class="mb-0"><plugin id="x-title" name="nct.label.plugin"></plugin></h2>
  </div>
  <plugin id="x-table" name="crud.table.plugin"></plugin>
</div>
```

```bash
python3 mrjun.py node add --parent <html-node-id> --plugin nct.label.plugin \
    --identifier x-title --name "Title" --project ./app
python3 mrjun.py node add --parent <html-node-id> --plugin crud.table.plugin \
    --identifier x-table --name "<Entity> table" --model @table-model.json --project ./app
```

The embedded table is a **full** `crud.table.plugin`: fetch rule, paging, filters, row and header actions, role
gating — nothing is lost by hosting it ([04](04-crud-table-plugin.md)). `node set-model` additionally syncs the
`rep-objects.settings[]` mirror keyed by the node's `uniqueIdentifier`; do not hand-roll that.

> ⛔ **Embedding does not buy you a second table.** The ⛔ *one table per PAGE* rule ([04](04-crud-table-plugin.md))
> counts `crud.table.plugin` + `crud.tree.plugin` + `process.table.pluin` **per page in any combination**,
> wherever they sit in the tree — wrapping one in your own html changes nothing, and `mrjun.py validate` ERRORs.
> The only exception is separate `nct.tab.plugin` tabs.

### 7.3 A drop-zone slot (`nct.parsis.plugin`)

Use this when the contents are not fixed at build time — a page container, a form body, a filter row, anything a
human will fill in the authoring UI later.

```html
<div class="row">
  <div class="col-md-8"><plugin id="main-slot"  name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-4"><plugin id="aside-slot" name="nct.parsis.plugin"></plugin></div>
</div>
```

```bash
python3 mrjun.py node add --parent <html-node-id> --plugin nct.parsis.plugin --identifier main-slot  --project ./app
python3 mrjun.py node add --parent <html-node-id> --plugin nct.parsis.plugin --identifier aside-slot --project ./app
# then drop the real content UNDER the parsis
python3 mrjun.py node add --parent <main-slot-node-id> --plugin dynaform.form.plugin --project ./app
```

The parsis renders every child in `order` and contributes no markup of its own; in authoring mode an empty one
shows a placeholder child. Some symbolic slot names are
**contractual** and must be spelled exactly: `siteMapPageParsis` (a page's content container),
`form.parsis` / `filter.parsis` (a form's / filter form's field anchor) — `validate` ERRORs when they are wrong
([01](01-content-model-and-pages.md), [04](04-crud-table-plugin.md)).

### 7.4 A reusable "card" wrapper used N times

Pure layout, no logic — the case where copies (mechanism c) are right:

```html
<div class="main-card mb-3 card">
  <div class="card-body">
    <h5 class="card-title"><plugin id="card-title" name="nct.label.plugin"></plugin></h5>
    <plugin id="card-body" name="nct.parsis.plugin"></plugin>
  </div>
</div>
```

Give each placement its own node with the **same two child identifiers** (`card-title`, `card-body`) — they only
need to be unique among that node's own children (§3). Placement N then differs only in what sits under its
`card-body` parsis and in the label's `text`.

The moment the *wrapper itself* needs to change everywhere (a class rename, a new header row), stop copying and
promote it to a shared common VP (§6.7) — otherwise you get the shipped-project outcome: 36 copies, 4 divergent
bodies, and no way to tell which is canonical.

### 7.5 Splitting a large component into documents

When one html string has grown past the point where you can find anything in it, split it into a **shell plus
parts** and let `<include>` put it back together (§2.7). The shell stays pure layout; the `<plugin>` tags live in
the parts.

```
main.html         the shell: grid + one <include> per region, plus the .js declarations
parts/head        title strip           — carries <plugin id="ord_kpi"   name="chart.js.plugin">
parts/table       the list region       — carries <plugin id="ord_table" name="crud.table.plugin">
parts/card        a plugin-free card frame (pure markup) — included from BOTH parts/head and parts/table,
                  which is safe precisely because it carries no <plugin> tag
views/detail      NOT included statically — pulled in on demand by ctx.include
boot.js           declared from main.html ⇒ include mode
```

`main.html`:

```html
<div class="ord-wrap">
  <include src="parts/head.html"/>
  <div class="row">
    <div class="col-lg-8"><include src="parts/table.html"/></div>
    <div class="col-lg-4"><div class="ord-card" id="ord-detail"></div></div>
  </div>
  <include src="boot.js"/>
</div>
```

`boot.js` — the on-demand region is a **server-rendered** include, so `views/detail` may carry `<plugin>` tags too:

```js
ctx.on('ord:pick', async ({ id }) => {
  const host = ctx.root.querySelector('#ord-detail');
  host.innerHTML = '';                             // empty the container FIRST — see §8.5
  if ((window.Dokie.__v || 0) < 3) {               // an older cached runtime has no ctx.include
    host.textContent = 'Please reload this page (Ctrl+F5).';
    return;
  }
  try {
    await ctx.include('views/detail.html', host);  // server-rendered: its <plugin> tags come alive
  } catch (e) {
    host.textContent = String((e && e.message) || e);
  }
});
```

Five rules that make a split safe:

1. **Every `<plugin>` tag lives in exactly one document, and that document is included exactly once** (§2.7). The
   parts you include repeatedly must be plugin-free.
2. **Child nodes are still parented to the hosting node** — `node add --parent <html-node-id>` for every tag,
   whichever document it sits in. Documents are text; only the node has children (§2.7, §3).
3. **Declare every script once you declare one** — the first `<include src="<name>.js">` reachable from
   `main.html` flips the component into include mode and any enabled script you did not declare stops running
   (§2.7); the manifest convention is [24d §3](24d-html-component-structure.md).
4. **Splitting does not shrink the parse cache entry** — the key is the whole *expanded* body (§8.3), so a region
   that is not needed on every render is genuinely cheaper as a runtime `ctx.include` — the size threshold is
   [24d §7](24d-html-component-structure.md).
5. **A rename that orphans an `src` is a `validate` WARN, not silence** — but a document included twice, or an
   `<include>` that ended up inside a `<plugin>`, still ships green (§2.7).

The file-layout conventions — how to name documents, what belongs in a part, and when a split is worth doing at
all — are in [24d](24d-html-component-structure.md).

---

## 8 · Traps

### 8.1 ⚠️ Duplicate ids — in the html, and in `children`

Two tags with the **same `id`** in one body both render, and both resolve to the **same** `ContentDomain` (the
lookup returns the first identifier match): two Wicket components sharing one config. If their
`name=` also differs, every single render flips `pluginName` and clears `properties` — permanent
config thrash. Symmetrically, two **children** with the same identifier: the first always wins and the second is
dead weight (this really happens in the wild — a page Layout node that ended up with two `right-kicker` children).
`validate` does **not** detect either case (it builds a dict keyed by identifier, so
duplicates collapse silently); nor does the MCP slot resolver, which says so in its own message
("duplicate id — first match wins").

### 8.2 ⚠️ Jsoup rewrites your markup

See §2.1. Pretty-printing, an injected outer `<div>`, synthesized `<tbody>`, auto-closed tags. Design the CSS so
none of that matters; never depend on exact text nodes or whitespace.

### 8.3 ⚠️ The static, unbounded parse cache

The parse cache is a plain `HashMap` (not concurrent), `static`, keyed by the **entire expanded html string**
(after every `<include>` has been spliced in — §2.7), and **never cleared or evicted** — there is no other
reference to it anywhere in mrjun or nct-ui. Consequences:

* It grows for the lifetime of the JVM, one entry per distinct html string ever rendered.
* **Splitting a component into documents does not shrink the entry.** The key *is* the expanded body, so ten
  200-line documents cost exactly what one 2 000-line string costs — same key length, same parse, same cached
  model. Includes buy authoring ergonomics, not runtime economy, and a component that grew from one big string to
  a shell plus twelve parts has not become cheaper to render. What actually costs less: keep the **expanded** body
  small; pull regions that are not needed on every render with `ctx.include` at runtime so they are not part of
  the main expansion at all; and split a genuinely huge screen across separate nodes (or tabs) rather than one
  node with an enormous expanded body.
* **For a studio-active `nct.html.plugin` it grows per render.** That plugin wraps the body in
  `<div id="dokie-plug-<markupId>" …>`, and `markupId` comes from a session-scoped Wicket sequence
  — so every page instance produces a *new* cache key that will never be hit again. Practical effect: extra
  memory, plus the Jsoup parse runs on **every** render for studio components (no caching benefit at all).
* It is safe semantically only because the cached model carries no content or tenant identity — resolution to a
  `ContentDomain` happens per plugin instance, later.

Nothing you author can fix this; know it so you do not blame your markup for a slow render, and keep studio
component bodies small — "small" now meaning small **after** include expansion.

### 8.4 ⛔ Rendering writes child nodes

> ⛔ **First render of a `<plugin>` tag creates and SAVES a child node** (the wrapper panel resolves its plugin
> through `getOrCreateChildContent`, which saves). A typo'd `id` therefore does not fail — it *creates* a blank node with that
> identifier, permanently, in the live branch. Re-exporting that tenant then ships the mistake back into your
> bundle. Symptom: an export that grew children you never authored, and an empty slot on the page. Fix the html
> **and** delete the stray node (`mrjun.py node rm`).

Note also that the *existing-child* branch never calls `contentService.save` — it mutates the live
in-memory `ContentDomain` the branch content index holds, and that is persisted on the branch's next save. So a
type-swap wipe (§3b) can appear "not saved yet" and still land.

### 8.5 ⛔ `ctx.setHtml` / `ctx.showHtml` destroy server-rendered children

> ⛔ Both assign `ctx.root.innerHTML`. `ctx.root` is the wrapper containing the **main**
> document — including every `<plugin>` child the server rendered inside it. The assignment deletes their DOM
> while Wicket still holds the components server-side: the embedded chart/table/form vanishes and any later AJAX
> update targeting it updates nothing. Symptom: *"my embedded plugin disappears the moment the component loads
> its data"*, fixed only by a full page reload. `validate` cannot catch it.
> **Rule: if the main document contains `<plugin>` tags, never call `setHtml`/`showHtml`.** Render into a child
> container (`ctx.root.querySelector('.x-body').innerHTML = …`) and keep the `<plugin>` slots outside it.
> Details → [24](24-html-component-studio.md) §6.4.
>
> **Swapping a whole document at runtime? Use `ctx.include`, not `showHtml`.** `ctx.showHtml` is a plain
> client-side `innerHTML` assignment: it cannot render a `<plugin>`, cannot expand an `<include>` and does not run
> `<script>` (its console warning now says exactly that and points at `ctx.include`).
> `await ctx.include('<doc>.html', '#host')` renders **server side** — the document's own includes expanded, its
> `<plugin>` tags materialised as live components (§8.7). It replaces the target's content by default, so empty
> the container yourself or pass `{ mode: 'append' }`; **never point it at a target that already holds
> server-rendered components** — that destroys them exactly as `setHtml` does (the runtime warns only if that
> target holds another studio HTML component; over an embedded chart/table/form it is silent).

Related: a Wicket AJAX `refresh()` rebuilds the whole ListView (the html plugin re-adds it in
`initPluginContent`), so **every** embedded child is recreated with a new markupId and loses its component state
(open dialogs, typed input, feedback).

### 8.6 ⚠️ `reuseItems`

The renderer calls `listView.setReuseItems(getContent().getProperty("reuseItems", PropertyType.BOOLEAN, false))`.
With the default `false`, ListItems are re-created on every render, so the wrapper re-resolves — and possibly
re-creates/re-saves — the child content on **every request**. Setting it `true` keeps items across renders,
which stops that churn but also stops the list from noticing an html change. `false` is the shipped default
everywhere; leave it alone unless you have measured a reason.

### 8.7 ⛔ A document is inert only through `ctx.showHtml`

> ⛔ **`<include>` and `ctx.include` server-render a document, `<plugin>` tags and all; `ctx.showHtml` is the one
> path that leaves it inert.**
>
> **Mechanism.** A `studioModel.docs[]` document reached from `main.html` through `<include src="…html">` is
> spliced in **before** the parse, so its `<plugin>` tags are ordinary root plugins of the hosting node (§2.7).
> `ctx.include(doc, selector)` does the same rendering on demand: server side, the document's own includes
> expanded, its plugins materialised as live components. `ctx.showHtml(doc)` is a different animal — a raw
> client-side `innerHTML` assignment with no server round-trip: `<plugin>` renders as **literally nothing**,
> `<include>` is not expanded, and `<script>` does not run. The runtime `console.warn`s and points at
> `ctx.include`.
> **Symptom:** a slot that produces no element and no error, in a document you put on screen with `showHtml`.
> **Caught by `validate`?** **Partly** — it ERRORs on a cycle and WARNs on a dangling/extension-less `src`; it
> cannot see that you put the document on screen with `showHtml` (§2.7).
> **Fix:** for a plugin that must be there from the start, put its tag in a document reachable from `main.html`
> by `<include>`. For one that appears later, `await ctx.include('<doc>.html', '#host')` — into an **empty**
> container, or with `{ mode: 'append' }` (§8.5). Keep `showHtml` for markup that contains neither `<plugin>`,
> `<include>` nor `<script>`.
> **Rule:** `<plugin>` in a document ⇒ that document arrives by include — static or runtime. `showHtml` ⇒ inert
> markup only.

Four more things about the runtime form. The document name **must** carry `.html`, and the target may be a CSS
selector string (resolved inside `ctx.root` first, then document-wide), a jQuery object or an element. It
**resolves with the inserted element** and **rejects** with an `Error` — missing document, no matching element, a
cycle, a limit — but it always settles, so `await` it inside a `try` and you will always know. It is guarded: a
document already open above the target is refused, nesting is capped at 10 and one component instance may hold 50
included documents; nodes it inserted are removed when the component re-renders, so a Wicket refresh leaves no
orphans behind. And it needs runtime surface **v3** — if your component must survive on an older host, guard with
`if ((window.Dokie.__v || 0) < 3) { … }`. Full runtime surface → [24](24-html-component-studio.md).

### 8.8 ⚠️ Other scanners disagree with the renderer

Two independent re-implementations exist; do not calibrate your html against them.
The authoring **plugin preview** panel pre-materialises children for
the preview modal and reads only `id`/`name` + `prop`/`property` — **no `vp`, no `behavior`, no `override`**.
The MCP content tools use a plain regex and consider only `nct.parsis.plugin` tags. `mrjun.py validate` uses a
third regex. Only `AbstractHtmlPlugin` decides what renders.

---

## 9 · Decision rule — embed a platform plugin, or draw it yourself?

Ask in this order and stop at the first **yes**:

1. **Does a stock plugin already answer this box?** A list of one entity → `crud.table.plugin`. A hierarchy →
   `crud.tree.plugin`. A number, a series, a pie, a mini-table over a query → `chart.js.plugin`. A create/edit
   form → a form group. **Embed it.** You inherit paging, filters, role gating, per-locale captions, actions,
   audit, drafts and theme-correctness for the price of one tag plus one child node.
2. **Is the box just layout/typography** (a title, a card, a grid cell, static help text)? Write it as plain
   markup in the html string, or use `nct.label.plugin` / `nct.image.plugin` for anything that must be
   localized or authorable.
3. **Does the box need data the stock plugin cannot shape** (a fused KPI strip, a timeline, a board, a canvas,
   a wizard), or a JS library? **Draw it yourself** in the same component and feed it with **one**
   `ctx.callRule` ([24](24-html-component-studio.md) §4).
4. **Is it a table you would have to page yourself?** Re-read (1). If it truly must be hand-drawn, the paging
   contract, the sort/filter push-down and the row-action idiom are in
   [24c](24c-html-data-tables-and-paging.md) — and you have just signed up for all of it.

**The business judgement.** Every embedded plugin is a screen the customer can still change without you: the
CRUD table's columns, captions and actions are edited in the authoring UI, and a new field is a config change.
Everything you hand-draw is a **code change forever** — a new column means editing a JS string inside a JSON
string inside an export, and re-importing. So the default is: *host, don't redraw*. Hand-draw only the part that
genuinely cannot be configured, and keep it as small as possible — a shell around configured plugins beats a
monolith that reimplements them. The cheapest dashboard you will ever own is the one with **zero** data JS and
nine `<plugin>` tags; the most expensive screens are always the ones that hand-drew a table the platform
already had.

---

## 10 · Done when

**Done when:** every `<plugin id>` in every authored html — main document or included one — has a child node on
the **hosting** node with exactly that `identifier` and exactly that `pluginName`; every `<include src>` carries an
extension and resolves; no configuration is expressed as a `<prop>`; nothing is nested tag-inside-tag;
reuse is a deliberate choice among (a)/(b)/(c)/(d) and is written in the shape that mechanism actually requires;
and `mrjun.py validate` exits 0 with no `<plugin>`-related WARNs you have not consciously accepted — and with
every include WARN read, not skipped.

- [ ] Every tag id ↔ child `identifier` pair matches, and every child `name` == its `identifier` (§3)
- [ ] Every tag `name` ↔ child `pluginName` pair matches — a type change was made in **both** places (§3)
- [ ] No `<plugin>` inside a `<plugin>` — and no `<include>` inside one either; second levels are real child nodes
      (`nct.html.plugin` or `nct.parsis.plugin`) with their own html/children (§5, §2.7)
- [ ] No duplicate `id` in the **expanded** body; no two children of one node sharing an `identifier` (§8.1)
- [ ] Every `<include src>` carries an extension (`.html`/`.htm`/`.js`/`.mjs`) and names a document or script of
      the **same** component; the include graph is acyclic and inside depth 20 / 500 tags / 2 000 000 chars — a
      cycle is an offline ERROR and a dangling/extension-less `src` a WARN; the limits and anything
      post-expansion are not checked (§2.7)
- [ ] No document carrying `<plugin>` tags is included twice; anything included more than once is plugin-free
      (§2.7, §8.1)
- [ ] Child nodes for tags that live in included documents are parented to the **hosting** html node (§2.7, §7.5)
- [ ] If any reachable document declares `<include src="<name>.js">`, **every** script that must run is declared —
      include mode ignores the rest (§2.7)
- [ ] Configuration lives in the child node's `properties` (`model` / `settings` / `Javascript` / `studioModel`),
      **not** in `<prop>`; any surviving `<prop>` is a deliberate seed or carries `override="true"` (§4)
- [ ] No `vp=` attribute in any authored html; sharing is expressed as `linkContentIdentifier` (§6.3)
- [ ] For every shared placement: the stub carries **only** `linkContentIdentifier` + baseline slots, the real
      content lives once in `virtualPlugins[].content`, and that `uniqueIdentifier` exists in the bundle (§6.2, §6.7)
- [ ] Nothing edits a linked stub's own properties expecting a visible change (§6.2)
- [ ] If one node is placed twice on one page, cross-component wiring uses `ctx.bus`, not `ctx.byName` (§6.6)
- [ ] The main `html` of any studio component with `<plugin>` tags is never rewritten by
      `ctx.setHtml`/`ctx.showHtml` (§8.5)
- [ ] A document containing `<plugin>` tags is placed by `<include>` or `ctx.include`, never by `ctx.showHtml`;
      the rendered page source carries no `<!-- dokie: … -->` include diagnosis (§8.7, §2.7)
- [ ] Embedded `crud.table`/`crud.tree`/`process.table` still respect ONE table per page (§7.2)
- [ ] `mrjun.py validate --project ./app` exits 0; then `mrjun.py pack`
- [ ] **Live-rendered**: every slot is populated (an empty card is the classic identifier mismatch), and the
      export was re-checked afterwards for child nodes the render created on its own (§8.4)

---

**See also:** [24](24-html-component-studio.md) (`studioModel`, the `ctx` runtime, rules/BL, breadcrumb actions) ·
[24a](24a-theming-and-dark-mode.md) (theme tokens, CSS scoping, the five skins) ·
[24c](24c-html-data-tables-and-paging.md) (hand-built tables and server paging) ·
[24d](24d-html-component-structure.md) (files, includes and when to split a component) ·
[01](01-content-model-and-pages.md) (content tree, pages, the cloning trap, virtual plugins) ·
[03](03-generate-fields-from-crud.md) (the generated row/col/slot chain this doc dissects) ·
[04](04-crud-table-plugin.md) (the stock table, filter-form cells, one-table-per-page) ·
[14](14-plugin-catalog-all.md) (every `pluginName` you may put in a `name=`) ·
[14a](14a-plugin-config-reference.md) (field-level config for the child you embed) ·
[17](17-left-nav-quick-links.md) (the shared left nav — mechanism (a) in production) ·
[20](20-localization.md) (`LOCALIZED_STRING` values and per-locale text) ·
[21](21-homepage-and-redirect.md) (homepage grid rows built this way) ·
[22](22-charts-params-and-filters.md) (the charts you embed) ·
[`tools/README.md`](tools/README.md) (`node add --identifier`, `set-model`, `set-studio`, `validate`, `pack`)
