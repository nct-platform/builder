# 24 · HTML Component Studio — `nct.html.plugin` as a real component (libraries, isolated JS, rule/BL calls, per-theme CSS, breadcrumb actions)

> 📐 **Field evidence — when a hand-built console is justified, and the anatomy of one that works:** [09-studio-components.md](references/09-studio-components.md) · [10-visual-design.md](references/10-visual-design.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> **Scope.** Everything you need to ship a hand-authored interactive component inside a `.mrjun`: the
> `properties.studioModel` schema, the complete `ctx` runtime surface (including the **breadcrumb-button API**
> and **`ctx.include`**), which scripts a component actually runs,
> how author JS reaches rules and business logic, lifecycle/teardown, wait UX, localization,
> **per-role behaviour** (any requirement phrased "for role X…" → §9a), vendoring library
> files, and a full worked example. **Read it before** you decide to hand-build a screen — §1 is the
> decision, not the syntax. This EXTENDS [14 §1.1](14-plugin-catalog-all.md) (the classic raw-HTML plugin and
> the `<plugin>` tag): the Studio is **purely additive** — a node with no `studioModel` renders byte-for-byte
> as before (the plugin hands back the raw `html` property untouched, with no wrapper and no runtime).
> **Not here:** the theme/CSS token contract → [24a](24a-theming-and-dark-mode.md); the `<plugin>` embedding
> grammar and component reuse → [24b](24b-html-composition-and-plugin-tags.md); server-paged tables inside a
> component → [24c](24c-html-data-tables-and-paging.md); the `<include>`/`<plugin>` tag grammar →
> [24b](24b-html-composition-and-plugin-tags.md); how to lay a component out across documents and scripts and
> when splitting is worth it → [24d](24d-html-component-structure.md).

| | |
|---|---|
| Plugin name | `nct.html.plugin` (display name "Html") — the same node type as a plain HTML block; it becomes a *component* the moment `properties.studioModel` is present |
| Config slots | `properties.html.stringValue` (STRING) — the **"main" document**;  `properties.studioModel.stringValue` (STRING holding JSON) — the component project (libs/docs/scripts/css) |
| Editor | a tabbed authoring panel (documents · scripts · libraries · CSS) reached from the node's gear icon as author/admin |
| Runtime | one small runtime is loaded once per page and mounts every component on it — after a **full page render and after an ajax re-render**, so a component delivered inside a tab or a re-rendered panel still mounts; a component whose mount runs before the runtime has finished loading is mounted as soon as it is ready |
| UI group | `Common` |

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `node add --parent <slot> --plugin nct.html.plugin --name "<Screen> UI" --identifier <symbolic>`,
> `node set-studio <id> --json @studioModel.json` (writes `properties.studioModel`; same STRING-holds-JSON
> mechanism as `set-model`), `asset add <relpath> <localfile>` / `asset ls` (vendor a library file through
> `tenant-files/`), `find --plugin nct.html.plugin`, `show node <id>`,
> `rule add --name "<Screen> Data" --type EXECUTION_RULE --context <ctx> --script @screen.groovy`.
> Every entity command takes `--project <unpacked-dir>` (`unpack`/`pack` take positional paths instead).
> ⚠️ `show node` decodes only the `settings`/`model` slots — `studioModel` prints as
> one escaped string, so read it back with `python3 -c 'import json,sys;print(json.loads(...))'` or keep the
> `studioModel.json` you fed to `set-studio` as the source of truth.
> Full index and rules — [`tools/README.md`](tools/README.md);
> before re-importing — `mrjun.py validate`, then `mrjun.py pack <dir> out.mrjun`.

**Philosophy.** This is the platform's **escape hatch for the 10 %** (visual builders for the 90 %, code for the
10 %). Author JS runs **first-party** — the runtime header says so verbatim: *"Trust model is FIRST-PARTY: this is
NOT a security sandbox"*. Libraries are CDN-first (no npm); uploaded files ride
`tenant-files/`. Author JS reaches the server **only** through the sanctioned Wicket channel
(author JS → the plugin bridge → a server-side service) — never a direct browser REST call.

---

## 1 · What this is, and when to reach for it instead of the visual builder

### 1.1 The 90/10 rule

The stock plugins already answer the overwhelming majority of screens, and each one you use for free carries a
long tail of behaviour you would otherwise have to write yourself:

| Need | Stock answer | What you get for free |
|---|---|---|
| List / create / edit / delete one entity | `crud.table.plugin` + a form group → [04](04-crud-table-plugin.md), [06](06-form-groups-and-mapping.md) | server paging, filters, row+header actions, role gating, per-locale column captions, drafts, validation, audit |
| A hierarchy | `crud.tree.plugin` → [05](05-crud-tree-and-process-table.md) | lazy children, same action model |
| A chart / KPI / dashboard | `chart.js.plugin` (+ `global.replacement.plugin` filter bar) → [22](22-charts-params-and-filters.md) | query params, cross-filter, theme-safe rendering |
| Page layout, cards, grid | a **classic** `nct.html.plugin` (no `studioModel`) + `nct.parsis.plugin` slots → [01](01-content-model-and-pages.md), [24b](24b-html-composition-and-plugin-tags.md) | server-rendered children, authoring UI, reuse |
| Process/task workbench | `process.table.pluin`, workflows → [07](07-workflows-and-tasks.md) | BPMN, user tasks, history |

**Reach for a studio component only when at least one of these is true:**

1. **One screen must fuse several entities into a non-tabular workspace** — e.g. a KPI strip + a list + a
   lifecycle timeline + an inline create form, all from ONE server call. Stock plugins cannot do that on one
   page: the ⛔ *one table per page* rule ([04](04-crud-table-plugin.md), enforced by `mrjun.py validate`)
   forbids stacking two tables, and each stock plugin fetches independently.
2. **The interaction is not "row → form"** — a board, a canvas, a map, a calendar-like grid, a wizard, a
   drag-and-drop planner, a diff viewer.
3. **You need a JS library** (d3/echarts/…) or a bespoke rendering that no plugin config can express.
4. **You need page-level actions whose behaviour is code**, not a CRUD action — see §7.

**Do NOT reach for it when** the ask is really "list + CRUD one entity" (you will spend a week reimplementing
paging, filters, validation, localization and role gating, badly), or when it is a chart (→ [22](22-charts-params-and-filters.md)),
or when it is only layout (a classic html plugin with no `studioModel` is the right tool — §12).

### 1.2 The cost you take on

Everything the platform did for you becomes yours: **paging and filtering** ([24c](24c-html-data-tables-and-paging.md)),
**validation**, **localization** (§9 — `ctx` has no locale), **theming across 5 skins** ([24a](24a-theming-and-dark-mode.md)),
**empty/loading/error states** (§4.4), **teardown of your own listeners** (§6), and **accessibility**. Offline
`validate` checks that the `studioModel` *parses*, that every `libNames` entry is declared, that asset
paths are relative, that the component's `<include>` graph resolves (§3.2), and it WARNs on bare colour literals
in the **all-themes** `css.byTheme["*"]` block only
(per-skin blocks and every chart's CSS are never scanned — [24a](24a-theming-and-dark-mode.md) §9). It can
**not** tell you that
`ctx.callRule('<Screen> Data')` names a rule that exists, and — beyond the include graph it now walks (§3.2) — it
does not expand a single include, so nothing that only exists *after* expansion is checked.
And a customer can no longer change the screen from
the authoring UI: every future field is a code edit.

> **Good default.** Keep the entity's normal `crud.table.plugin` page **and** its form group. Add the studio
> component as a *cockpit/console* page on top: read-optimised, action-rich, fed by one EXECUTION rule.
> If the component breaks, the boring page still runs the business.

---

## 2 · Export schema — `properties.studioModel.stringValue`

The value is a JSON string; the platform reads it with GSON via
`content.getJsonProperty("studioModel", HtmlStudioModel.class, HtmlStudioModel::new)`, coalescing a stored
`null`/`""` to an empty model. Shape (`HtmlStudioModel`):

```jsonc
{
  "libs": [                      // named, reusable asset bundles
    {
      "name": "d3",              // the key you use as ctx.libs.d3. REQUIRED, unique per component
      "enabled": true,           // default true; disabled libs are dropped from the mount payload
      "order": 0,                // sorts the libs array server-side. NOT a load barrier — see §12
      "globalVar": null,         // for a JS_CLASSIC (UMD) lib: window[globalVar] becomes ctx.libs[name]
      "assets": [
        { "kind": "JS_ESM",      // JS_ESM | JS_CLASSIC | CSS | FONT; default JS_ESM
          "url": "https://cdn.jsdelivr.net/npm/d3@7/+esm",  // absolute CDN url
          "path": null,          // OR a vendored file, RELATIVE to the tenant root: "studio/<lib>/<file>".
                                 //    url WINS when both are set.
          "fileName": null,      // original upload name; stored, never rendered
          "entry": true,         // the ESM module whose namespace becomes ctx.libs[name]
          "order": 0 }           // assets of ONE lib load strictly sequentially in this order
      ]
    }
  ],
  "docs": [                      // ADDITIONAL documents. "main" is the html property, NOT listed here
    { "name": "detail",          // stored WITHOUT an extension; addressed as "detail.html" by includes.
                                 //    a doc literally named "main" is DROPPED from the mount
      "html": "<div class=\"x-detail\"></div>" }   // no enabled flag, no order; duplicate names collapse
  ],
  "scripts": [                   // author JS; ALL scripts that RUN share ONE scope — which ones run: §3.2
    {
      "name": "main",            // stored WITHOUT an extension; included as "main.js".
                                 //    appears only as a `//# script: main` comment in the compiled body
      "code": "…",
      "enabled": true,
      "order": 0,                // concatenation order in legacy mode (§3.2)
      "libNames": ["d3"]         // libs that must resolve BEFORE this script runs
    }
  ],
  "css": {                       // per-theme CSS, auto-scoped to this instance's wrapper
    "byTheme": {
      "*": ".x-card{padding:8px}",     // ALL_THEMES, emitted first
      "Dark Blue": ".x-card{…}"        // an exact Skin display name; only the ACTIVE skin's block is emitted
    }
  }
}
```

**Names are STORED bare and DISPLAYED with an extension.** `docs[].name` and `scripts[].name` keep holding
`detail`, `charts/bar`, `main` — exactly as they always did. **There is no schema change and no migration:** every
existing `.mrjun`, every `ctx.showHtml('detail')` call and every folder path keeps working untouched. What changed
is presentation — the studio now *shows* those names as `main.html`, `charts/bar.html`, `boot.js` in the document
and script navigators and in the rename field, and rename accepts either spelling and stores the bare one. A `/`
in a name is a **display folder** in the navigator, not a path: no traversal, no `..`, no relative resolution.

> ⚠️ **`<include src="…">` and `ctx.include(…)` REQUIRE the extension — a bare name is refused, not guessed.**
> Documents and scripts are two independent name spaces, so one component may legitimately hold a document
> `report` **and** a script `report`; an extension-less `src` cannot choose between them. `.html`/`.htm` selects a
> document, `.js`/`.mjs` a script, and `main.html` addresses the plugin's own `html` property. Symptom of getting
> it wrong in markup: the tag leaves only an HTML comment in the page source and the studio reports a warning —
> no exception, no console error, just a section missing from the screen. From
> `ctx.include` the same mistake **rejects**. `ctx.include` is §3.1, script selection is §3.2, the tag's full
> grammar is [24b §2.7](24b-html-composition-and-plugin-tags.md), the file layout is
> [24d](24d-html-component-structure.md).

Wrapped as an ordinary content property in `branches.json`:

```json
"studioModel": {
  "key": "studioModel", "propertyType": "STRING", "required": false, "hidden": false,
  "stringValue": "{\"libs\":[],\"docs\":[],\"scripts\":[{\"name\":\"main\",\"code\":\"const d=await ctx.callRule('Screen Data',{});\",\"enabled\":true,\"order\":0,\"libNames\":[]}],\"css\":{\"byTheme\":{\"*\":\".x-page{padding:12px}\"}}}",
  "localizedStringValue": {}, "arguments": {}
}
```

**Defaults and emptiness.** The model is "empty" when `libs`, `docs`, `scripts` are all empty **and** every
`css.byTheme` value is blank. It deliberately does **not** look at the `html` property. *Studio-active* is simply
"not empty" — that single boolean decides wrapper, runtime, head CSS, mount payload **and** whether the breadcrumb
bridge answers at all (§7.5). A trivial `{"libs":[],"docs":[],"scripts":[],"css":{"byTheme":{}}}` is therefore
*classic* — harmless, but noise; it accumulates by the dozen on auto-generated `gen_row_*`/`gen_slot_*`
form-layout nodes.

> ⛔ **A studio-active node whose `html` property is unset renders EMPTY.** The two modes differ in their default:
> a *classic* node with no `html` falls back to the platform placeholder `<div>Html content here</div>`, while a
> studio-active node falls back to `""` (so `docs["main"]` is empty too). Symptom: you add scripts, reload, and the
> component is an invisible empty wrapper with no console error — your JS then fails on the first
> `ctx.root.querySelector('.x-…')` returning `null`. **Always author the main markup in `properties.html`**, even
> if it is only the containers your JS fills (§11 step 2). `validate` does not catch it.

**Skin keys for `css.byTheme`** are the exact `Skin` display names — `Standard`, `Dracula`, `Forest`,
`Dark`, `Dark Blue` (space!) — or `"*"`. Only `"*"` **plus the currently active skin's** block is emitted (the
active skin is the logged-in user's stored `skin` preference, defaulting to `Dark`); an unmatched key is
silently ignored. Four of the five skins are dark. **Prefer one `"*"` block written against theme tokens** — the
full token contract, the `:root/html/body` rewrite and the `@keyframes` exemption are in
[24a](24a-theming-and-dark-mode.md).

---

## 3 · The runtime API — the complete `ctx` surface

Each **selected** script (§3.2 — by default that is every enabled one) runs **after the host HTML and its
server-rendered `<plugin>` children have rendered**, in ONE shared `AsyncFunction` body per component instance. The runtime calls it as
`fn.call(ctx, ctx, ctx.libs, ctx.contextData, D)` — so the injected parameters are
`(ctx, libs, contextData, dokie)` and **`this === ctx`**. `AsyncFunction` means **top-level `await` is legal**.

This table is the whole surface — `ctx` has nothing else:

| `ctx.*` | Meaning |
|---|---|
| `ctx.id` / `ctx.name` | the content **identifier** of this node (both are the same string) — see the ⛔ below when it is unset |
| `ctx.root` | this instance's wrapper element `#dokie-plug-<markupId>` — scope every DOM query to it |
| `ctx.contextData` | frozen projection of the live form/CRUD context; `{}` standalone — §5 |
| `ctx.libs[name]` | resolved library value (ESM entry namespace, or `window[globalVar]`, else `null`) |
| `ctx.bus` | page-global event target shared by every component (usually an `EventTarget` — see the shim note below) |
| `ctx.byName(n)` / `ctx.all()` | another component's exported `ctx.api`, keyed by **identifier** |
| `ctx.getHtml()` / `ctx.setHtml(html)` | read / **replace** `root.innerHTML` — destructive, see §6.4 |
| `ctx.showHtml(docName)` | swap in a `docs[]` document via `innerHTML` — **client-side only**; takes `'detail'` or `'detail.html'`; unknown name → `console.warn`; §6.4 |
| **`await ctx.include(doc, sel[, opts])`** | insert a **server-rendered** document — its own includes expanded, its `<plugin>` tags live — into a target element; §3.1 |
| `ctx.docNames()` | `["main", …]` |
| `ctx.activeDoc` | writable string; `showHtml` sets it |
| `ctx.on(evt, fn)` | bus listener, **auto-removed at teardown** (and refused after teardown — §6.3) |
| `ctx.emit(evt, detail)` | dispatch a `CustomEvent` on the bus |
| `ctx.onCleanup(fn)` | register a teardown callback — §6 |
| `await ctx.callRule(rule, input)` | run an EXECUTION rule — §4 |
| `await ctx.callBl(alias, method, args)` | run a dynamic-CRUD method — §4 |
| **`ctx.breadcrumb.*`** | declare page-title-bar buttons — §7 |
| **`ctx.addBreadcrumbButton(def)`** | alias of `ctx.breadcrumb.add(def)` |
| **`ctx.busy(elOrSelector, {block})`** | show the platform wait indicator, returns `done()` — §8 |
| `ctx.api` | your export object; published as `window.Dokie.plugins[ctx.name]` |

Page-global registry:

```js
window.Dokie.__v        // runtime version marker — 3 since ctx.include shipped; guard on it, see below
window.Dokie.plugins    // identifier -> the ctx.api of the most recent instance of that component
window.Dokie.libs       // lib name -> the loaded library, page-wide (first requester wins)
window.Dokie.bus        // the cross-component event bus behind ctx.bus / ctx.emit / ctx.on
```

Everything else on the object is runtime bookkeeping (per-instance mount state, asset de-duplication,
breadcrumb sync) — do not read or write it: it is not part of the author surface and changes without
notice.

`__v` exists so author code can survive a browser holding a **cached older runtime**: without a guard the first
`ctx.<new thing>` is a bare `TypeError`, and because all of an instance's scripts share ONE `AsyncFunction` that
aborts the whole author program, not just the new call. Compare against the feature you need: a runtime reporting
`2` has the breadcrumb API (§7) but **no `ctx.include`**. The idiom the runtime itself documents:

```js
if ((window.Dokie.__v || 0) < 3) {          // old cached runtime: ctx.include may be missing
  ctx.root.querySelector('.x-body').textContent = 'Please reload this page (Ctrl+F5).';
} else {
  await ctx.include('detail.html', '.x-body');
  syncBar();
}
```

> ⛔ **`ctx.el` and `ctx.data` do not exist.** The DOM root is **`ctx.root`** and the context projection is
> **`ctx.contextData`**. `ctx.el` is simply `undefined`, so the first
> `ctx.el.querySelector(…)` throws `TypeError: Cannot read properties of undefined` inside the AsyncFunction;
> the runtime catches it and logs
> `[Dokie] runtime error in "<identifier>"` — **the component renders its static HTML and then does
> nothing**, with no server-side error. `mrjun.py validate` does not catch it (it never parses your JS).

> ⛔ **Always give the node an identifier.** `ctx.id`/`ctx.name` is the content **identifier**, but when the node
> has none the plugin falls back to the numeric content **id** (e.g. `"10473"`) — which is assigned by the
> database and differs after every re-import. Consequences: `ctx.byName('<entity>_ui')` in a sibling component
> returns `undefined` (no error, just a dead integration), and `window.Dokie.plugins` is keyed by a number nobody
> can predict. Set it once at creation: `mrjun.py node add … --identifier <entity>_ui` (§11).

> ⚠️ **`ctx.bus` is not guaranteed to be a real `EventTarget`.** On engines where `new EventTarget()` throws
> (older Safari/WebViews) the runtime falls back to a minimal shim with only `addEventListener` /
> `removeEventListener` / `dispatchEvent`. The shim ignores the options bag, so `{ once: true }`,
> `{ signal }` and capture do **nothing** — a `once` listener keeps firing. Use `ctx.on()` (auto-removed at
> teardown) and unregister explicitly rather than relying on listener options.

Also absent by construction, so do not plan around them: **no user / locale / tenant / skin** on the mount
payload (it carries only `id, domId, activeDoc, docs, libs, scripts, contextData`);
no DOM-query or event-delegation helper; no way to ask Wicket to re-render anything (the plugin's Java-side
`IRefreshable.refresh()` is not reachable from author JS); no `onMount`/`onDestroy` hooks other than
`ctx.onCleanup`.

### 3.1 `ctx.include(doc, selector[, opts])` — pull in a document, server-rendered

```js
const el = await ctx.include('detail.html', '#host');           // REPLACES the target's content
await ctx.include('row.html', '#list', { mode: 'append' });     // appends instead
```

* **It renders on the server**, exactly like the static `<include>` tag: the document's own includes are expanded
  and its `<plugin>` tags come back as **real, live child components**. That is the whole point — and it is the
  only way to bring a `<plugin>` into the page after mount, because `ctx.showHtml` cannot (§6.4).
* **The document name must carry `.html`** — `'detail.html'`, never `'detail'` (§2).
* **`selector`** may be a CSS selector string — resolved **inside `ctx.root` first, then document-wide** — or a
  jQuery object, or an element.
* **Replace is the default**; `{ mode: 'append' }` adds instead of replacing.
* It **resolves with the inserted element** and **rejects with an `Error`** — missing document, no matching
  element, a cycle, a limit. It **always settles**, so `await` it inside `try/catch` like any bridge call (§4.4).
* **Runtime cycle guard:** a document that is already open *above* the target element is refused. Nesting is
  capped at **10**, and at **50** included documents per component instance.
* **Cleanup is automatic:** the nodes it inserted are removed when the component re-renders, so a Wicket AJAX
  refresh leaves no orphaned copies (§6.2).

> ⛔ **Including OVER server-rendered components destroys them — same failure as §6.4.** Replace mode overwrites
> whatever the target holds, and if that includes live `<plugin>` children their DOM goes while Wicket still tracks
> them server-side: the embedded table/chart/form vanishes and later ajax updates land nowhere. The runtime warns
> **only** when the target holds another *studio* HTML component. Replacing over an embedded **stock** plugin — a
> chart, a table, a form — is completely **silent**: no warning, no error, the component simply disappears until a
> full page reload. **Fix:** include into an **empty** container, or use `{ mode: 'append' }`.

### 3.2 Which scripts run — legacy mode and include mode

A component is in exactly one of two selection modes, and the mode is decided by the documents, not by a setting:

* **Legacy — the default, and unchanged.** If **no** document reachable from `main.html` contains an
  `<include src="….js">`, **every enabled script runs**, in the studio's own up/down ordering (`scripts[].order`).
  This is exactly how it worked before includes existed: **nothing built before this changes behaviour.**
* **Include mode.** As soon as one document declares a script include, **only included scripts run**, in the order
  the `<include src="….js">` tags appear, depth-first from `main.html`. The `enabled` switch still wins — an
  included-but-disabled script stays off. What declares the mode is the **extension**, not the resolution: a
  `src` ending `.js` that names **no** script of the component still flips it, so one misspelt include in a
  component whose whole manifest is that tag leaves the program **empty** — markup renders, no JS runs
  ([24d](24d-html-component-structure.md) §3.2).
* **Reachability is a fixpoint.** A document reached only through a **literal** `ctx.include('x.html')` in a
  script contributes its own script includes too.
* Unchanged in both modes: **all selected scripts of one instance are still ONE program in one shared scope**
  (§12). Includes decide *which* scripts run, never *how* they run.

> ⚠️ **Switching modes is a cliff, not a slope.** The first `<include src="boot.js"/>` you add *anywhere* in the
> component silently demotes every script you did not include: they stay `enabled` in the model and simply never
> execute. Symptom: half the screen stops working the moment you split one document, with a clean console. The
> studio warns about an enabled script that nothing includes (§12), and so does `validate`, as a WARN — read it.

> ⛔ **`mrjun.py validate` CHECKS THE INCLUDE GRAPH — AND NOTHING THAT NEEDS EXPANSION.**
> **Mechanism:** it walks every studio component from `main.html`, resolving each `<include src>` and each
> **literal** `ctx.include('…')` by the same extension rule the platform uses. An include **cycle** is an
> **ERROR** (printed as the loop path, `main.html -> a.html -> a.html`); an extension-less `src`, an `src` that
> names no document/script of the component, an enabled script nothing includes (in include mode), and an include
> mode in which **no** script include resolves at all — an empty program — are **WARNings**.
> **Symptom when it stays silent:** it never expands anything, so an `<include>` inside a `<plugin>`, a
> `<plugin id>` that only collides after expansion, the depth-20 / 500-tag / 2 000 000-character limits, and a
> computed `ctx.include(name + '.html')` are all invisible offline — each renders an HTML comment
> (`<!-- dokie: … -->`) or silently drops content, never an exception.
> **Caught by `validate`?** **Cycle: yes (ERROR). Dangling / extension-less / never-run script: yes (WARN).
> Everything above: no.**
> **Fix:** run `validate` before every pack; then live-render and search the page source for `dokie:`.
> **Rule: `validate` green means the graph resolves, not that the expansion is what you meant.**

---

## 4 · Calling rules and business logic

Both go **author JS → the plugin bridge → a server-side service** and both return a `Promise`. All three
listeners (`dokieCallRule`, `dokieCallBl`, `dokieBreadcrumb`) are added **unconditionally**, even on a classic
node — but only the first two do work there; the breadcrumb one refuses unless the studio is active (§7.5).

### 4.1 `ctx.callRule(ruleNameOrIdentifier, inputObject)` — the workhorse

```js
const data = await ctx.callRule('<Screen> Data', { entityId: 42, mode: 'open' });
```

* **Resolution**: the server tries `findByIdentifier` first; otherwise a fuzzy
  `findAll(ruleName=…)` from which **only an exact case-insensitive NAME match** is accepted. It never
  falls back to "first row" — an unresolvable token returns `{"ok":false,"error":"Rule not found: <token>"}`.
  Prefer the **identifier**; a display name is fine but renaming the rule in the UI silently breaks the
  component.
* **Marshalling**: every top-level field of the input object becomes its own
  attr, **then** the whole object is set under the reserved key `input` — in that order, so a field literally
  named `input` cannot clobber the whole-payload contract.
* **Locale**: the server stamps the session locale onto the rule context before executing (the value is the
  Wicket page locale as `language_COUNTRY`, e.g. `en_US`/`hy_AM`). This is the ONLY way a component learns the
  locale — §9. Read it in Groovy with **`service.global.locale.getKey()`** ([16](16-groovy-service-api.md)): the
  Groovy executor copies the context's `localeKey` into the thread-local `LocaleContext` before running the body
  and restores the previous value after. ⛔ **`context.data.localeKey` returns `null`** —
  `context.data.<x>` is an *attribute* lookup (`GlobalDataWrapper.propertyMissing → getAttr("localeKey")`)
  and nothing ever writes an attr by that name. The raw DTO field is reachable as
  `context.contextData.localeKey` if you prefer it.
* **Return value** = the rule's `returnValue` — the value of an **explicit `return`**. The executor appends
  its own `return null` after your body, so a bare final expression is discarded and the component silently
  receives `null` ([08](08-groovy-rules-and-context.md)). Use an **EXECUTION_RULE** (a PREDICATE only ever
  returns a boolean).

```groovy
// '<Screen> Data' — EXECUTION_RULE
def input   = context.data.getAttr('input')       // the whole object: [entityId:42, mode:'open']
def entityId = context.data.getAttr('entityId')   // per-field convenience: 42
def locale  = service.global.locale.getKey() ?: 'en_US'   // NOT context.data.localeKey (always null)
return [ok: true, locale: locale, rows: service.crud.<alias>.findAll([rowsInPage: 500, pageNumber: 0])]
```

### 4.2 `ctx.callBl(alias, method, argsObjectOrArray)` — the direct dynamic-CRUD call

```js
await ctx.callBl('<alias>', 'create', { name: 'X' });   // one object -> a ONE-element positional list
await ctx.callBl('<alias>', 'findAll', [{ rowsInPage: 50, pageNumber: 0 }]);
```

The runtime wraps a non-array into `[args]`; the server parses the JSON array into
positional parameters and calls the dynamic-CRUD executor's **user-authenticated** entry point — the
`…Internal` (service-token) variant is deliberately not used, so the call is subject to the logged-in user's
rights.

> ⚠️ Positional args must match the CRUD method's declared `parameters[].parameterOrder`
> ([11](11-business-logic-dynamic-crud.md)). A scaffolded `findAll` declares `rowsInPage` + `pageNumber`;
> calling it with `[]` sends unbound parameters and Postgres fails with
> `operator is not unique: unknown * unknown`. Paging contract → [24c](24c-html-data-tables-and-paging.md).

### 4.3 Which to use

| | `callRule` | `callBl` |
|---|---|---|
| Reads several CRUDs in one round-trip | ✅ the reason it exists | ❌ one call per entity |
| Business logic / validation / side effects before the write | ✅ | ❌ raw method only |
| Shapes the payload for the UI (KPIs, joins, localized labels) | ✅ | ❌ raw rows |
| Reusable from workflows, schedulers, table fetch | ✅ same rule | ➖ |
| Trivial single-entity write with no logic | ➖ | ✅ shortest path |

**Default: one `<Screen> Data` EXECUTION rule per component for reads, one rule per mutating action** — i.e.
a `… Screen Data` rule plus `Save …`/`Activate …`/`Delete …`. Components that reach for `callBl` instead
typically end up hand-rolling retries, because `callBl` runs as the logged-in user and fails for unprivileged
accounts (§4.4, security posture).

### 4.4 The envelope, the timeout, and error handling

Every server path returns a JSON envelope: `{"ok":true,"result":…}` or
`{"ok":false,"error":"…"}`. The bridge resolves `result` and **rejects** with `new Error(error)`.
Belt and braces: the support service catches everything, and all three listener bodies catch again into an error
envelope — because the richwicket ajax callback has no error channel.

> ⛔ **A bridge call rejects after exactly 30 s** (hard-coded in the runtime, no cancel, no retry).
> Cause: an unknown handler name or a lost twin makes the server return HTTP 200 with **no callback at all**, so
> without the timer `await` would hang forever. Symptom the user sees: the screen sits on "Loading…" for half a
> minute, then your `catch` fires with `Error: dokieCallRule timed out`. `validate` cannot catch it. **Always
> `try/catch` every bridge call and render the message.**

> ⛔ **Return only plain maps / lists / scalars from a rule.** The envelope is built with Jackson, and a value it
> cannot write — the classic case being an object graph with a **cycle** — does **not** come back as `null`: the
> server converts the failure into `{"ok":false,"error":"result is not serializable: …"}`, so
> `await ctx.callRule(...)` **rejects**. Note there are *two* distinct origins of "works in the rule editor
> preview, fails from the component": this envelope error, and a value the rule executor itself cannot marshal
> back (a Groovy `Closure`, a live JDBC/Hibernate handle, a lazy proxy) — that one fails earlier, at the executor
> boundary, and surfaces as an ordinary rule-execution error with a different message. Both have the same fix, in
> the rule: project into `[key: value]` maps and lists of maps before you `return`, and convert dates/enums to
> strings. Same rule for `callBl` results.

```js
async function load() {
  try {
    const d = await ctx.callRule('<Screen> Data', {});
    if (!d || d.ok === false) { return fail(d && d.message || 'No data'); }
    render(d);
  } catch (e) {
    fail(String(e && e.message || e));   // rule-not-found, rule exception, or the 30s timeout
  }
}
function fail(msg) {
  ctx.root.querySelector('.x-body').innerHTML =
    '<div class="alert alert-danger mb-0"></div>';
  ctx.root.querySelector('.alert').textContent = msg;   // textContent — never innerHTML with server text
}
```

Two more shape rules that pay off: make the rule return `[ok:false, message:…]` instead of throwing (you get a
readable message instead of a stack trace), and tolerate both list shapes on the JS side —
`const arr = x => Array.isArray(x) ? x : (x && Array.isArray(x.content) ? x.content : []);` — because a rule that
returns a paged envelope and one that returns a bare list are equally likely.

**Concurrency — the bridge is SYNCHRONOUS and blocks the page.** `callRule`/`callBl` post through `twin.ajax`
**without** `async: true`, and that twin call defaults to `async: false`, which selects the *synchronous* ajax
supporter — a **blocking XHR**. The whole browser tab is frozen for the duration of the call: no paint, no
scroll, no click. Design around it:

* `Promise.all([ctx.callRule(a), ctx.callRule(b)])` does **not** parallelise. It serialises *and* freezes the page
  twice. **Fetch everything in ONE rule**, and never fire bridge calls from inside a loop (`rows.forEach(r =>
  ctx.callBl(...))` locks the UI for rows × round-trip).
* A DOM write made in the same task as the call is **not painted** before the freeze — the user sees the old
  screen, then the new one, and your "Loading…" state never appears. **Yield one macrotask between showing the
  wait state and making the call**:

  ```js
  const paint = () => new Promise(r => setTimeout(r, 0));
  showLoading();                    // write the DOM
  await paint();                    // let the browser paint it
  const d = await ctx.callRule('<Screen> Data', {});   // now block
  ```
* The 30 s guard above cannot fire *while* the thread is blocked; it exists for the case where the server never
  invokes the callback at all (an unknown handler name, a lost twin).

The same truth, with the paging/table consequences worked through, is in
[24c §2.5](24c-html-data-tables-and-paging.md).

**Security posture.** Tenancy is server-derived and cannot be spoofed (realm/client come from the tenant, the
user from the page), and the transport is the authenticated Wicket session. But there is **no per-rule /
per-CRUD allowlist and no role check inside the bridge** — author JS (and any XSS on that page) can invoke every
rule and every dynamic-CRUD method the current user may run. Gate the component itself with node `roleAccess`
(`mrjun.py roleaccess set`, or the component's own context menu → **Role access** in the authoring UI) and put
real authorization in the rule. ⚠️ An HTML component does **not** access-check the `<plugin>` children it
hosts — each child is gated only by its own resolved node, so for a linked common component only the shared
node's access counts here (see [01](01-content-model-and-pages.md) §"Hidden content").

---

## 5 · `ctx.contextData` — the read-only projection

Acquisition: the enclosing `IFormContextProvider.getContextData()` first (it also
*publishes* the page attribute as a side effect), else the page attribute
`FormPlugin.LIVE_FORM_CONTEXT_DATA_ATTRIBUTE` (`"nct.live.form.contextData"`), else `null`.

The projection mirrors the Groovy binding of [09](09-groovy-hints-and-live-context.md):

```js
ctx.contextData.data.<attr>            // GLOBAL attrs
ctx.contextData.<contextAlias>.data.<attr>   // per-context attrs
ctx.contextData.<contextAlias>.<crudAlias>   // the whole entity, as raw JSON
```

* Context **identifiers** are translated to **aliases**; an unmapped identifier passes through.
* A context whose alias is literally `data` is skipped, null attrs are dropped, and the
  internal markers `_crudAlias, _crudEntityId, __actionId, __actionName, __methodParams, __currentItem__,
  __currentItemIndex__, __listItem__, __localize__` are stripped from attrs **and** crud aliases.
* **Never projected:** the rule `returnValue`, the ACL, and **the locale key** — the projection only reads
  `attrs` + `contextDataMap`.

> ⛔ **It is `{}` on a standalone page and it never refreshes.** The server projects `null` outside a
> form context, and the runtime coalesces that to `{}`. It is a **render-time snapshot**,
> deep-frozen recursively — writes are silently dropped in sloppy mode and throw in strict mode,
> and there is no `ctx.reloadContext()`. Symptom of assuming otherwise: `Cannot read properties of undefined` on
> `ctx.contextData.<alias>` and a dead component. **Always guard:**
> `const cd = ctx.contextData || {}; const row = (cd.<alias> || {}).<crudAlias>;`
> If your component needs live entity state, fetch it with `ctx.callRule` — do not read it from `contextData`.

---

## 6 · Lifecycle — mount, re-render, teardown

### 6.1 Mount

The twin's `_mountStudio()` looks up the wrapper by its **exact** id (`dokie-plug-<markupId>`, never "the first
`.dokie-plug` inside me" — a classic html plugin may contain a studio-active one), reads
`window.__dokieMounts[<domId>]` and calls `window.Dokie.mount(payload, this)`, retrying every 60 ms up to 50 times
while the runtime script is still loading. It runs on **`onDomReady` and
`onAjaxReady`** — i.e. on a full page render *and* on every Wicket AJAX re-render.

`Dokie.mount`, in order:

1. resolve the root element first (a missing node aborts *before* anything is torn down);
2. bump a **monotonic generation** for this `domId` and **synchronously tear down** the currently active
   instance — before any async work;
3. resolve the **wanted lib set** = union of every script's `libs`; **if that union is empty, fall back to ALL
   declared libs**;
4. `Promise.all` over the libs through the **page-global** cache `D.libs[name]` — first requester wins across all
   instances on the page;
5. re-check the generation and abandon if superseded; on lib failure, log and **still run the author code
   with `{}` libs**;
6. build `ctx`, re-check the generation once more, register `D._inst[domId]` and `D.plugins[name]`,
   then compile+run the concatenated scripts.

### 6.2 What a Wicket AJAX re-render does

A refresh re-initialises the plugin's content and re-renders it. Re-init rebuilds the whole document list, so
**every server-rendered `<plugin>` child is recreated with a new markupId**; the plugin component itself
survives — its wrapper `domId` is **unchanged**, which is exactly why the post-ajax re-mount lands on the same
registered instance and tears the old one down cleanly. Your author code **runs again from scratch**:
module-level state is lost, and anything you attached must be re-attached. Write scripts to be idempotent —
they are effectively a `render()` function, not an `init()`. Anything `ctx.include` inserted is removed as part of
the same cycle, so a refresh leaves no orphaned copies of an included document behind (§3.1).

### 6.3 Teardown — the leak

When an instance is torn down the runtime, in this order: marks the instance dead **first**, then runs every
cleanup you registered (each in its own `try`, so one failure cannot block the rest), then empties the cleanup
list so nothing can run twice, and finally unpublishes your `ctx.api` from the page registry — but only if the
registry still points at *this* instance. Teardown is idempotent: a second call does nothing.

Marking the instance dead **before** draining has two consequences author code can observe, and both bite the
same shape of script — one that
registers its listeners *after* its first `await`:

* **After teardown, `ctx.on(evt, fn)` silently refuses to register** and returns `ctx`. It does not throw and it
  does not warn. A dead instance must not keep answering bus events, so this is correct — but a script written as
  `const d = await ctx.callRule(…); ctx.on('<entity>:changed', reload);` loses its subscription entirely whenever a
  Wicket AJAX re-render lands before that continuation resumes — every `await` is a point where a re-mount can
  tear this instance down. Symptom: "the component stops reacting to events after the first refresh", with a clean
  console.
* **After teardown, `ctx.onCleanup(fn)` runs `fn` IMMEDIATELY** and does not store it (queueing onto a drained
  array would leak). That is the right call for a dead instance, but it means a *late* registration undoes the
  thing it was meant to protect: `const t = setInterval(poll, 30000); ctx.onCleanup(() => clearInterval(t));`
  written after an `await` clears the interval the moment it is registered, so the poller never ticks — again with
  a clean console.

> ✅ **Rule: register every `ctx.on` and `ctx.onCleanup` BEFORE the first `await`.** Do the wiring
> synchronously at the top of the script, then load data. The worked example in §11.1 is written in that order on
> purpose.

> ⛔ **Teardown fires ONLY when a new mount claims the same `domId`.** There is no
> `beforeunload` hook and no DOM-removal observer. If an ancestor re-render gives the node a **new** markupId, or
> the node is removed from the page, the old instance's cleanup **never runs**: its `setInterval`s keep firing,
> its `document`-level listeners keep matching, its library state keeps growing. Symptom: after a few navigations
> the page fires the same handler 3–4× per click, or a poller keeps hammering a rule for a screen that is no
> longer visible. `validate` cannot see it.
> **Mitigation:** register EVERY timer and every non-bus listener through `ctx.onCleanup`, and prefer **one
> delegated listener on `ctx.root`** over per-element handlers.

```js
const t = setInterval(refresh, 30000);
ctx.onCleanup(() => clearInterval(t));

const onKey = e => { if (e.key === 'Escape') closePanel(); };
document.addEventListener('keydown', onKey);
ctx.onCleanup(() => document.removeEventListener('keydown', onKey));

// ctx.on(...) is auto-removed at teardown; a raw addEventListener is NOT.
// Register it BEFORE the first await (§6.3) — after teardown ctx.on() silently refuses.
ctx.on('<entity>:changed', () => load());
```

### 6.4 `setHtml` / `showHtml` destroy server-rendered children

> ⛔ **`ctx.setHtml(...)` and `ctx.showHtml(...)` assign `root.innerHTML`.**
> `root` is the wrapper that contains the **main** document — including every `<plugin id=…>` child the server
> rendered inside it ([24b](24b-html-composition-and-plugin-tags.md)). The assignment deletes their DOM while
> Wicket still holds the components server-side: the embedded chart/table/form vanishes, and any later AJAX
> update targeting it updates nothing. Symptom: "my embedded plugin disappears the moment the component loads
> its data", and only a full page reload brings it back. `validate` does not catch it.
> **Rule: if the main document contains `<plugin>` tags, never call `setHtml`/`showHtml`.** Render into a *child*
> container instead — `ctx.root.querySelector('.x-body').innerHTML = …` — and keep the `<plugin>` slots outside
> `.x-body`.

> ✅ **To swap in a document that itself contains `<plugin>` tags, use `ctx.include` (§3.1).** It is the supported
> way: `await ctx.include('detail.html', '.x-body')` renders the document **server side**, so its `<plugin>` tags
> arrive as live components instead of inert markup, and the runtime removes what it inserted on the next
> re-render. Aim it at an **empty** container (or pass `{ mode: 'append' }`) — including *over* live components
> destroys them exactly as `setHtml` does.

`ctx.showHtml` remains a plain **client-side `innerHTML` swap and nothing more**: it does not expand `<include>`,
it does not server-render `<plugin>` (such a tag in the document it swaps in stays inert markup), and it does not
run an inline `<script>` — its `console.warn` says so and points at `ctx.include`. It now accepts **both
spellings** of the name, `ctx.showHtml('detail')` and `ctx.showHtml('detail.html')` (§2); an unknown name still
only warns.

---

## 7 · Breadcrumb actions — page-level buttons declared from author JS

### 7.1 Where page actions belong

A screen has two kinds of action. **Row/record actions** (edit this line, delete this line) belong *in* the
component, next to the thing they act on. **Page actions** — "New <Entity>", "Activate", "Export", "Back to list" —
belong in the **breadcrumb bar**, the strip under the page title where every stock plugin already puts its
Create/Import buttons (`crud.table.plugin`, `crud.tree.plugin`, the rule editor, the BPMN modeler…). Putting them
there is not cosmetic: it is the only place a user's eye already goes for "what can I do on this page", and it
keeps your component's own markup free of a home-grown toolbar that will never match the theme.

Until now only Java plugins could contribute there. `ctx.breadcrumb.*` opens it to author JS.

### 7.2 The mechanism (why it is cheap)

1. Author JS calls `ctx.breadcrumb.add({...})`. Only a **descriptor** is stored; the handler stays a JS closure.
2. Every mutation arms ONE debounce timer (`Dokie.BREADCRUMB_DEBOUNCE_MS`, default **200 ms**; a mutation stream
   faster than the debounce is force-published once the window has been open for 5× that). N calls in a burst ⇒
   **one** round-trip carrying the **complete desired set** — declarative, never incremental.
3. The flush posts `{buttonsJson}` through `twin.ajax → dokieBreadcrumb` — the same sanctioned channel as
   `callRule`, and therefore the same blocking transport (§4.4): keep the set small and do not publish in a loop.
4. The server sanitizes the set and fires the platform's `Add_Breadcrumb_Buttons` event with this plugin's
   component path as the contribution identifier. `BreadCrumbPlugin` keys contributions by that identifier and
   **replaces**, so publishing swaps *your* buttons and leaves every other plugin's alone.
5. Each button renders as a real `<button>` with an inline
   `onclick="window.Dokie&&window.Dokie.bcClick('<domId>','<key>',this,event)"`.
   **A click costs ZERO round-trips** — `D.bcClick` resolves the handler on
   the **current** instance and runs it in the browser.

Rendered markup:

```html
<button type="button" id="link1"
        class="mb-2 me-2 btn-icon btn-hover-shine btn-shadow btn-outline-2x btn btn-danger"
        title="Remove it"
        onclick="window.Dokie&amp;&amp;window.Dokie.bcClick('dokie-plug-idA','delete-plan',this,event)">
  <i class="pe-7s-trash btn-icon-wrapper"></i>Delete plan
</button>
```

### 7.3 The API

```js
ctx.breadcrumb.add(def)            // add, or REPLACE the button already registered under the same key
ctx.breadcrumb.set([def, …])       // replace the WHOLE set in one shot (best after a re-render)
ctx.breadcrumb.update(key, patch)  // patch one registered button; no-op if the key is unknown
ctx.breadcrumb.remove(key)
ctx.breadcrumb.clear()             // publishes [] -> clears THIS plugin's contribution only
ctx.breadcrumb.has(key)  -> bool
ctx.breadcrumb.keys()    -> [key,…]  // in render order
ctx.breadcrumb.flush()             // publish now, skipping the debounce
ctx.addBreadcrumbButton(def)       // alias of .add()
```
(Every mutator returns the api, so they chain.)

`def` fields:

| field | type | default | meaning |
|---|---|---|---|
| `key` | string | slug of `label`, else `btn<N>` | identity **inside this plugin instance**; re-adding the same key REPLACES and keeps the slot. Charset `[A-Za-z0-9_.:-]`, max 64 — sanitized identically in the browser and again on the server |
| `label` | string \| function | `key` | button text, rendered **HTML-escaped**, capped at 120 chars. A **function is called once, at declaration time**, and only its result travels — see below |
| `icon` | string | — | icon class, e.g. `pe-7s-trash`, `lnr-plus-circle`, `fa fa-plus`. Sanitized to `[A-Za-z0-9_ -]` (max 200) |
| `variant` | string | `primary` | `primary\|secondary\|success\|info\|warning\|danger\|light\|dark\|link`; anything else falls back to `primary` |
| `cssClass` | string | — | full class override; when set, `variant` is ignored |
| `title` | string | — | tooltip, capped at 200 |
| `order` | number | 0 | ascending; equal `order` keeps declaration order (stable) |
| `disabled` | bool | false | renders `disabled` and emits **no** `onclick` at all |
| `onClick` | function | — | `(evt) => …` with `evt = {key, el, event, ctx}` and `this === ctx`; **never leaves the browser** |
| `wait` | bool | **true** | when `onClick` returns a Promise, spin the button until it settles |
| `block` | string | — | CSS selector to cover with the blockUI overlay while that Promise is pending (document-wide — scope it, §8) |

**`label` may be a function** — `{ key: 'save', label: () => t('Save'), … }` — which is convenient when the label
comes from a message map that is populated by the fetch rule. But it is resolved **once, when you declare the
button**, and only the resulting string is stored: a function cannot survive `JSON.stringify`, so an unresolved one
would leave the button rendering its *key*. Practical consequence: a label function is **not** a live binding. When
the locale (or any state it closes over) changes, you must re-declare the set — which is what `syncBar()` in §7.4
does anyway. If the function throws, the label falls back to the key.

### 7.4 The replace-by-key idiom (master → detail navigation)

This is what makes the feature worth having: **the same key re-declared swaps the button in place**, keeping its
slot (the original declaration sequence is preserved on replace, so a relabelled button does not jump). So the bar
can follow the user as they drill in — without ever accumulating stale buttons.

```js
// ONE function that describes the bar for the CURRENT state. Call it after every state change.
function syncBar() {
  if (state.mode === 'list') {
    ctx.breadcrumb.set([
      { key: 'new',  label: t('New <entity>'), icon: 'pe-7s-plus',  variant: 'primary',
        onClick: () => openForm(null) },
      { key: 'sel',  label: t('Edit selected'), icon: 'pe-7s-pen',  variant: 'secondary',
        disabled: !state.selectedId, onClick: () => openForm(state.selectedId) }
    ]);
  } else {
    ctx.breadcrumb.set([
      // SAME keys, different labels/handlers -> the buttons morph, they do not stack.
      { key: 'new',  label: t('Save'),   icon: 'pe-7s-diskette', variant: 'success',
        onClick: async () => { await save(); state.mode = 'list'; await load(); syncBar(); } },
      { key: 'sel',  label: t('Cancel'), icon: 'pe-7s-back',     variant: 'secondary',
        onClick: () => { state.mode = 'list'; render(); syncBar(); } },
      { key: 'del',  label: t('Delete'), icon: 'pe-7s-trash',    variant: 'danger',
        title: t('Delete this <entity>'), block: '#' + ctx.root.id,   // scope it: `block` is document-wide (§8)
        onClick: async () => { await ctx.callRule('Delete <Entity>', { id: state.selectedId });
                               state.mode = 'list'; await load(); syncBar(); } }
    ]);
  }
}
```

Use `.set([...])` when you own the whole bar (the normal case — it is atomic and cannot leave a stale key);
use `.add()`/`.update(key, {...})` for a single toggle, e.g.
`ctx.breadcrumb.update('sel', { disabled: !state.selectedId })` after a row click.

### 7.5 Traps

> ⛔ **Requires studio mode — and the server enforces it.** The API lives on `ctx`, and `ctx` only exists when
> `studioModel` is non-empty, so on a classic HTML plugin there is no runtime to call it from. The bridge itself
> is **inert** on such a node as well: the `dokieBreadcrumb` listener exists but answers
> `{"ok":false,"error":"studio is not active for this component"}` and draws nothing — deliberately, because
> without a mounted instance every rendered button's `onclick` would point at a mount that does not exist
> (permanently dead buttons in the title bar). Give the node at least one script.

> ⛔ **Requires `site.breadcrumb.plugin` on the page.** The platform's event trigger walks the page and its
> children, so a page whose layout lacks the breadcrumb node **silently swallows** the
> contribution: the round-trip succeeds, `{"ok":true,"result":N}` comes back (N = the number of buttons the
> server accepted), and no button is ever drawn. The standard page scaffold created by `mrjun.py page add`
> includes it; a hand-built layout may not. `validate` does not check this. Confirm live.

> ⛔ **The handler is a closure, not a server action.** `onClick` runs entirely in the browser. Reaching the
> server is your job: `onClick: async () => { await ctx.callRule('<Action>', {id}); await load(); }`. A button
> that "does nothing" almost always has an `onClick` that forgot to `await` (or was never given one — a `def`
> without `onClick` renders a button that is inert by design).

> ⚠️ **Return the Promise.** `wait` defaults to `true`, but the spinner only arms when `onClick` **returns** a
> thenable. A fire-and-forget `onClick: () => { save(); }` gives the user no feedback for the whole
> round-trip. Make handlers `async`.

> ⚠️ **An icon-less button can never show a spinner.** The platform's wait helper anchors the spinner to the
> button's first `<i>` and, finding none, only applies `[disabled]`; the breadcrumb link emits an `<i>` only when
> `icon` is set. **Always pass an `icon`.**

> ⚠️ **Always pass an explicit ASCII `key` when the label is localized.** The auto-key is the label with
> everything outside `[A-Za-z0-9_.:-]` stripped — a
> fully non-Latin label reduces to `""` and falls back to a positional `btn<N>`, so re-declaring "the same"
> button after a language switch produces a *different* key and a duplicate slot.

> ⚠️ **Ordering across plugins is by publication order, not by `order`.** The breadcrumb plugin keeps one
> insertion-ordered map keyed by contributing plugin and flattens the values; `order` only sorts *within* your own
> set. If a `crud.table.plugin` on the same page also contributes, whoever publishes first sits first.

> ⚠️ **Caps and hardening.** Max **20** buttons per plugin instance (the excess is truncated with a server-side
> warning); duplicate keys collapse to the last declaration; unknown JSON fields are ignored on purpose so a
> version-skewed cached runtime cannot wipe the set; a button with a blank key after sanitization is dropped.

> ⛔ **Hard payload cap of 64 KB, checked BEFORE parsing — and an oversize publish yields an EMPTY set.** The
> server rejects an over-long `buttonsJson` outright (so a runaway loop cannot be deserialized into hundreds of
> MB of transient objects), and a rejected payload parses to *no buttons*, which then **replaces** your
> contribution — every button vanishes from the title bar. `{"ok":true,"result":0}` still comes back, so nothing
> in the browser looks wrong. You only reach 64 KB by putting bulk data where a descriptor belongs (a giant
> `title`, a data-URI icon, hundreds of generated buttons). Keep descriptors to labels and keys; ≤ 20 buttons of
> ordinary text is roughly 2 KB.

**Publishing is single-in-flight, and "synced" means the server said so.** Only one publish is in the air at a
time; a mutation made while one is pending simply re-arms the debounce, so the *newest* set goes out once the
current call settles. The runtime records a set as synced **only after the server's acknowledgement** — a
dropped or failed request leaves it un-synced so the next flush retries it, instead of the browser believing the
server holds a set it never received. Because richwicket's ajax has no error channel, an in-flight publish that
never gets a reply is released after **~30 s** (the same window as the rule/BL bridge); until then further
publishes only re-arm. Two authoring consequences: after a page action that also triggers a Wicket re-render,
give the bar a beat before asserting "my buttons are wrong" — and if you must publish synchronously at a known
moment, call `ctx.breadcrumb.flush()`.

**Zero-cost guarantees worth knowing:** several `add()` in one tick ⇒ one ajax; a re-mount declaring an
*identical* set ⇒ **zero** ajax, because the sync record is page-global per `domId` and the server still holds the
set — clicks keep working because `bcClick` resolves against the live instance; a
superseded mount never publishes its dead set; a component that never touches `ctx.breadcrumb` costs
nothing at all.

---

## 8 · Wait / blocking UX — which mechanism when

Three mechanisms, and picking the wrong one is the classic "spinner that never stops".

| Situation | Use | Why |
|---|---|---|
| A button **inside your HTML** whose click triggers a Wicket/bridge round-trip | markup attributes `icon-wait="true"` (+ `block-wait-selector=".sel"`) | handled globally by `common-d.js`, zero JS; auto-clears on the next `ajaxComplete` |
| A **breadcrumb** button | nothing — `wait: true` is the default | `bcClick` arms the same busy helper when the handler returns a Promise |
| Any **JS-driven** work: several bridge calls, a client-side recompute, an `await` chain | `ctx.busy(el, {block})` → call the returned `done()` | you control both ends |

**Markup attributes** (`common-d.js`): the delegated binding is
`WAIT_MARKER_SELECTOR = '[block-wait-selector], [icon-wait="true"], [icon-wait="yes"]'` with the trigger-event
whitelist `click change input blur focus keyup keydown submit`; `wait-event="change"` overrides the
default `click`. `icon-wait` overlays a spinner on the element's first `<i>` (sized from that icon's own box),
defers `[disabled]` one macrotask and starts the top `DokieProgress` bar; `block-wait-selector` raises a jQuery
blockUI overlay over **every** match of its selector. Both clear on the next global `ajaxComplete` + 200 ms.

```js
// ctx.busy: explicit start/end — the only correct choice when there may be zero ajax calls.
// FIRST arg: resolved inside ctx.root.   opts.block: resolved against the WHOLE document -> prefix it.
const done = ctx.busy('.x-refresh', { block: '#' + ctx.root.id + ' .x-body' });
try { await load(); } finally { done(); }
```

> ⛔ **Only the first argument is root-scoped; `opts.block` is not.** `ctx.busy(target)` resolves a string
> `target` with `ctx.root.querySelector(...)` — no fallback to `document`, so a selector matching something
> outside your wrapper resolves to `null` and **the button half is skipped** (no spinner, no disable). Note that
> this is *not* a full no-op: the `block` overlay is still raised and the top progress bar still starts, so a
> typo'd `target` gives you blocking visuals with no button feedback — and you must still call `done()` to clear
> them. But the `block` selector is handed to jQuery and
> matched **across the entire page**, so a generic `'.x-body'` blocks *every* component on the page that happens
> to use that class — two studio components built from the same starter markup will grey each other out, and the
> overlay of the one that is not loading never clears until its own next `done()`. **Scope the block selector to
> your instance**: either prefix it with your wrapper id as above, or give the blocked element a
> component-unique class (`<pfx>-body`, where `<pfx>` is chosen per component — the same discipline that keeps
> your CSS from leaking, [24a](24a-theming-and-dark-mode.md)).

`ctx.busy` drives the very same platform helpers by hand — `addAjaxWait`, `showTheBlockPanel`, `DokieProgress` —
and every dependency is optional, so on a page without them it degrades to a no-op instead of throwing. The
returned `done()` is idempotent: calling it twice is harmless, which is why `finally { done(); }` is safe.

> ⛔ **`icon-wait` on an element whose click makes NO ajax request hangs forever.** The cleanup is a one-shot
> `ajaxComplete` listener; with no request there is no event, and the button
> stays greyed with a spinning ring until the next unrelated ajax on the page. Symptom: "the button locks up".
> Use `ctx.busy` for pure client-side work.

> ⚠️ **Never point `block-wait-selector` (or `ctx.busy`'s `block`) at a `<table>`.** blockUI appends its overlay
> `<div>`s **into** the target; inside a table that is invalid markup and the browser hoists them out, so the
> overlay lands in the wrong place. Block a wrapping `<div>`.

---

## 9 · Localization inside a component

> `ctx` carries **no locale**. The mount payload has no user/locale/tenant field,
> and the context projection deliberately omits it (§5). This is the single most common thing builders get wrong.

**The locale reaches you exactly one way: through the rule.** The server stamps the session locale on the rule
context before executing, the Groovy executor copies it
into the thread-local `LocaleContext`, and
**`service.global.locale.getKey()`** hands it to your script, so a fetch rule can simply return it:

```groovy
// '<Screen> Data' — EXECUTION_RULE
def loc = 'en_US'
try { loc = service.global.locale.getKey() ?: 'en_US' } catch (Throwable t) { }
return [ok: true, locale: loc, rows: service.crud.<alias>.findAll([rowsInPage: 500, pageNumber: 0])]
```

> ⛔ **Do not write `context.data.localeKey` — it is always `null`.** `context.data.<name>` resolves through
> the global-data wrapper's `propertyMissing` → `contextData.getAttr("<name>")`,
> i.e. it reads the **attrs map**, and nothing ever stores the locale there. The rule then always reports the
> default language, the component silently renders in English, and (because it *looks* right in code review)
> the mistake survives — and once one rule has it, every rule pasted from it has it too, which is exactly why
> components end up sniffing the browser and letting the rule only *confirm* a language.
> `service.global.locale.getKey()` is the working call ([16](16-groovy-service-api.md),
> [20](20-localization.md)); `context.contextData.localeKey` reads the same value straight off the DTO.
> `validate` cannot catch either form.

**Recommended pattern — one message map keyed by locale, driven by `d.locale`:**

```js
const MSG = {
  en_US: { title: '<Entity> console', neu: 'New <entity>', save: 'Save', empty: 'Nothing yet' },
  hy_AM: { title: '…', neu: '…', save: '…', empty: '…' }
};
let LOC = 'en_US';
const t = k => (MSG[LOC] || MSG.en_US)[k] || (MSG.en_US[k] || k);

const d = await ctx.callRule('<Screen> Data', {});
LOC = (MSG[d.locale] ? d.locale : 'en_US');       // fall back, never crash on an unlisted locale
ctx.root.querySelector('.x-title').textContent = t('title');
syncBar();                                        // breadcrumb labels use t() too — with ASCII keys (§7.5)
```

Why a map beats the alternatives: it is one source of truth, it survives a third locale being added (add a key,
not a code path), the *same* `t()` feeds your markup, your breadcrumb labels and your empty/error states, and it
matches how the rest of the project stores per-locale text ([20](20-localization.md)).

**Row data** is localized separately: a CRUD with a `localizationField` carries `{field: {locale: text}}` in a
`jsonb` column, so display values come from the row, not from `MSG`. ⛔ **Read it under `row.localize`, never
under the DB column name.** Whatever the author called the column (`localized`, `translations`, …), the
dynamic-CRUD executor renames the CRUD's configured `localizationField` to the canonical wire key `localize` on
every read — so reaching for `row.<yourColumnName>` yields `undefined` and your helper silently falls through to
the untranslated value:

```js
const loc = (row, field) => {
  const m = row && row.localize;          // canonical wire key — NOT the CRUD's column name
  const o = (typeof m === 'string') ? (() => { try { return JSON.parse(m); } catch (e) { return null; } })() : m;
  return (o && o[field] && o[field][LOC]) || row[field];
};
```

> ⚠️ **The pattern projects reach for, and why you should not copy it.** A common bilingual shortcut hard-codes
> the second language into `data-<lang>="…"` attributes on the markup and swaps them at runtime
> (`root.querySelectorAll('[data-xx]')…el.textContent = t`), plus in-JS `L('English','<other>')` helpers, plus a
> `MON_EN`/`MON_XX` month table, plus browser sniffing (`?lng=` → `?lang=` → `lang` cookie → `<html lang>`) with
> the rule only allowed to *confirm* the language, never revoke it. It works, but: it is bilingual-only by
> construction (a third locale means editing every `data-*` attribute in every component), the default language is
> baked into the markup so the "untranslated" state is invisible, the same strings get copy-pasted across every
> component in the project, and the sniffing can disagree with the server's own locale. Note *why* it ends up
> there: rules written this way
> read the locale as `context.data.localeKey`, which is always `null` (see the ⛔ above), so the server could
> never be trusted to answer. **Drive labels from the locale the rule returns; keep the map in one place.**

---

## 9a · Per-role behaviour — "for role X, show/allow Y"

Almost every PRD contains a line of this shape: *"an approver sees the Approve button"*, *"only a
supervisor may re-open a closed record"*, *"the export button is for auditors"*. This section is the
whole recipe.

### 9a.0 Recognising the requirement — the PRD often never says "role"

Most requirements of this kind are written as **behaviour per persona**, with no permission vocabulary
at all. Learn to see them:

| What the PRD says | What it actually asks for |
|---|---|
| "the clerk sees only what concerns them, the manager sees everything" | role groups **+ row scoping** — two mechanisms, §9a.5 |
| "the manager can filter by clerk" | a filter control that exists **only** for the manager's group |
| "an approver can send it back" | one action gated by a group |
| "this screen is for the back office" | the whole page gated by a group |
| "supervisors also see the cost column" | a **field dropped from the projection** for everyone else, §9a.5 |
| "everyone can read, only the owner edits" | no group at all — an **ownership** check on the row |

> ✅ **Any noun that names a kind of person — clerk, manager, approver, inspector, auditor, cashier,
> dispatcher — is an actor, and an actor becomes a ROLE GROUP.** Two personas doing different things on
> the same screen always means: one rule that answers "what may THIS user do here", plus data that is
> already scoped before it reaches the browser.

The last row matters: "only the owner may edit" is **not** a role group. Ownership is a property of the
row (who created it, who it is assigned to), so it is checked against the current user's identity, not
their groups. A requirement can need both at once — "a clerk edits their own drafts, a supervisor edits
any".

### 9a.1 The vocabulary rule — "role" in a PRD means ROLE GROUP here

> ✅ **A requirement that says "role", "user role", "role group", "group" or "permission group" is
> implemented against a ROLE GROUP.** Read them all as the same instruction. Role groups are the unit the
> platform gives you for this: they are per-project, an administrator manages them in the project's
> security screens, and a user may hold several at once.
>
> Do not try to branch on the individual low-level roles behind them, and do not invent your own
> permission table in a CRUD — a hand-rolled table drifts from the real membership the moment an
> administrator changes something, and it is not what the rest of the platform checks.

### 9a.2 There is NO client-side check — and that is deliberate

Nothing about the current user reaches your JS. The mount payload carries the component's documents,
libraries, scripts and the read-only context projection — no user, no email, no roles, no groups.
`ctx` has no `user` and no `hasRole`.

That is not an oversight to work around. Author JS is first-party code running in the visitor's browser:
anything you check there can be edited in the console. **A browser-side check is a UI convenience, never a
protection.** The decision has to be made on the server, by a rule.

### 9a.3 The recipe — one rule returns the flags, JS only draws

Two methods on `service.security` are available inside any rule (EXECUTION, PREDICATE and VALIDATION all get
the same object), and they answer for **the user the request is executed as**:

```groovy
service.security.hasAnyRoleGroup("<GroupA>", "<GroupB>")    // AT LEAST ONE of them
service.security.hasAllRoleGroups("<GroupA>", "<GroupB>")   // EVERY one of them
```

Write ONE rule per screen that answers every question that screen asks, and return a flat map:

```groovy
// EXECUTION rule — "<Screen> Permissions"
return [
    canView   : service.security.hasAnyRoleGroup("<Viewer>", "<Approver>", "<Supervisor>"),
    canEdit   : service.security.hasAnyRoleGroup("<Editor>", "<Supervisor>"),
    canApprove: service.security.hasAllRoleGroups("<Approver>", "<Trained>"),   // both required
    canExport : service.security.hasAnyRoleGroup("<Auditor>")
]
```

> ⚠️ The same pair exists for the low-level roles behind the groups
> (`service.security.hasAnyRole` / `hasAllRoles`) — **use the roleGroup pair.** Groups are what an
> administrator actually manages per project; branching on raw roles couples your screen to internals.
>
> ⚠️ There is no bare `hasAnyRoleGroup(...)` — always write the `service.security.` prefix, or the script
> fails with a missing-method error. And do not confuse this with `service.global.*` (the YAML global
> functions, doc 16): different namespace, different thing.
>
> ⛔ **SMOKE-TEST the group check on your platform before you build a permission model on it.** Import a
> project, put `return [g: service.security.hasAnyRoleGroup('<a group you really hold>'), me:
> service.security.user()]` in one rule, and call it from a component while signed in as a member. If it
> answers `false` for a genuine member, the cause is identity plumbing, not your spelling: rules triggered
> from the UI are handed the platform's **internal user id**, while the group checker resolves users by
> identity-provider id or email, and every failure inside that lookup is swallowed into a plain `false`.
> `service.security.user().email` is unaffected — so until you have confirmed the group check on your
> platform, prefer **ownership/email comparisons** (§9a.5) for anything that must not fail open, and raise
> the group check with the platform team.

Then the component asks once and renders:

```js
const acl = await ctx.callRule('<Screen> Permissions', {});
if (acl.canApprove) { approveBtn.hidden = false; }
if (!acl.canEdit)   { form.querySelectorAll('input,select,textarea').forEach(el => el.disabled = true); }
```

> ✅ **One rule, one call, all flags.** The bridge is synchronous and blocks the tab (§4.4), so three
> permission calls freeze the page three times. Ask once, at mount, before the first `await` that draws.

### 9a.4 Hiding the control is not the protection

A hidden button is still callable: the visitor can invoke the same `ctx.callBl(...)` from the console.
Whatever the button does must ALSO be gated where it happens:

| The action | Where the real gate goes |
|---|---|
| a business-logic method (`ctx.callBl`) | inside that method's own rule — refuse when the group is missing |
| a CRUD row action / table action | the action's visibility **and** its execution rule |
| a whole page or menu entry | ⛔ there is **no** page-level gate by role group ([19](19-build-decision-procedure.md) Phase 6) — gate every action on the page **and** scope its data, and leave the quick link out of the nav for everyone else |
| a breadcrumb action button (§7) | the rule the button calls, same as any other action |

Treat the JS check as *cosmetic*: it stops an authorised user from seeing clutter, nothing more.

### 9a.5 "Sees only their own" — scope the DATA, never the drawing

This is the half that is easy to get wrong. *"A clerk sees only their own records; a manager sees all of
them and can filter by clerk"* is **two** requirements:

1. **who may do what** — role groups, §9a.3;
2. **which rows exist for this user** — decided on the server, in the fetch.

> ⛔ **Never fetch everything and hide rows in JS.** Every row still travelled to the browser, so the
> "restriction" is a `Ctrl+U` away — and the page pays for data it does not show. This is the single most
> common mistake in this pattern.

Scope it where the rows are produced. The current user is available to the rule:

```groovy
// EXECUTION rule — "<Screen> Rows"
def me      = service.security.user()                                  // id / email / firstName / lastName
def seesAll = service.security.hasAnyRoleGroup("<Manager>", "<Supervisor>")

def filter = [:]
if (!seesAll) {
    filter.assignedTo = me.email                          // a clerk: only their own, decided HERE
} else {
    def picked = context.data.getAttr('assignedTo')       // a manager: the filter THEY chose
    if (picked) { filter.assignedTo = picked }
}
return service.crud.<entity>.find(filter)
```

> ⚠️ Two things this snippet depends on. **(a)** A conditionally-populated filter map only works when the
> CRUD method's SQL type-guards its placeholders — otherwise a partial map fails with *"could not determine
> data type of parameter $1"* and nothing renders; the `COALESCE` / cast forms are in
> [24c §2.4](24c-html-data-tables-and-paging.md). **(b)** On a dynamic CRUD, `assignedTo` must be a declared
> parameter used in **both** `findAll` and `count`, or the key is silently dropped and every row comes back
> ([04](04-crud-table-plugin.md)).

and the component simply draws what it is given, plus the filter control when allowed:

```js
const acl  = await ctx.callRule('<Screen> Permissions', {});
const rows = await ctx.callRule('<Screen> Rows', { assignedTo: acl.canSeeAll ? picked : null });
clerkFilter.hidden = !acl.canSeeAll;    // the manager's "filter by clerk" control
```

Three consequences worth stating plainly:

- **The same rule serves both personas.** Do not write two screens; write one whose data rule knows who
  is asking. A second screen doubles every future change.
- **The manager's filter is an input, the clerk's scope is not.** A clerk's restriction must not be
  expressible as a parameter — if the browser can pass `assignedTo`, a clerk can pass someone else's.
  Note in the snippet above that the parameter is only consulted when `seesAll` is true.
- **Ownership is a column, so name it.** "Their own" has to map to something real on the row — the
  assignee, the author, the owning unit. If the PRD does not say which, that is a question for the
  customer, not a guess. Compare against `service.security.user().email` unless the column really stores
  the platform's internal user id (`user().id`).
- **A FIELD nobody-but-X may see is the same problem one level down.** "Supervisors also see the cost
  column" is not a JS `hidden` — the value would still be in the bridge response, one devtools tab away.
  Drop the field from the rule's projection for everyone else, exactly as you drop rows; see
  [24c](24c-html-data-tables-and-paging.md) §3.

### 9a.6 Traps

- ⛔ **Group names are data, not code.** They must name a role group that exists in the project (matching is
  case-insensitive, but nothing else is forgiven) — a wrong name is not an error, it is a silent `false`, and
  the feature disappears for everyone. Keep the names in one place
  in the rule, and use the project's real group names, not prose from the PRD.
- ⚠️ **Answers are cached per (user, group set).** A membership change is not necessarily visible on the
  next click; do not build a screen that expects an instant flip after an administrator edits groups.
- ⚠️ **An anonymous / public page has no user**, so every check answers `false`. If a screen is meant to
  be public, drive it from something other than role groups.
- ✅ **Default to hidden.** Write the JS so a failed or empty permissions response leaves privileged
  controls *off* rather than on — a rule that fails to run must not open a door.

---

## 10 · Vendoring a library file

Prefer CDN `url`s. When you must ship an actual file (offline/private lib), it rides the **`tenant-files/`**
channel of the `.mrjun` — there is no separate upload step.

* **Export:** everything in file-storage under `t/<tenantId>/…` is copied into the zip as `tenant-files/…` with the
  `t/<tenantId>/` prefix stripped. `t/42/studio/echarts/echarts.esm.js` ⇒ `tenant-files/studio/echarts/echarts.esm.js`.
* **Import:** everything under `tenant-files/…` is re-uploaded at `t/<NEW tenantId>/…`.
* **Reference:** store the asset `path` **relative** — `studio/<lib>/<file>` — and the plugin prepends the current
  tenant id at render time, producing
  `<siteContext>/dokie-asset?p=t/<tenantId>/studio/<lib>/<file>`. A legacy absolute `t/<id>/…` path is used as-is
  and therefore **breaks after import** — `validate` WARNs on it.
* **Serving:** `DokieAssetResource`, mounted at `/dokie-asset`. Guard: the path must match
  `t/<digits>/studio/<something>`, must not contain `..`, and its extension must be whitelisted — otherwise
  **HTTP 403**. The whitelist is exactly:

  ```
  js  mjs  css  json  map  svg  html  htm
  woff  woff2  ttf  otf  eot
  png  jpg  jpeg  gif  webp
  ```

  Correct MIME per extension so `<script type="module">` / dynamic `import()` accept it;
  `Cache-Control` 1 hour. A path that exists but is unreadable returns 404, not 403.

> ⛔ **Only the `studio/` subtree is servable, and only with a whitelisted extension.** `mrjun.py asset add`
> accepts *any* clean relative path (it is a generic `tenant-files/` tool), so nothing stops you from shipping
> `libs/foo/foo.js` or `studio/foo/foo.wasm` — the file imports into file-storage perfectly and then **403s** on
> every page load. The browser reports it as a failed module import; the runtime logs
> `[Dokie] library load failed for "<identifier>"` and — by design — still runs your author code with `{}` libs,
> so the symptom is "my chart library is `undefined`", not "my file is missing". `validate` cannot catch this
> (it only checks that the path is relative). **Always vendor under `studio/<lib>/<file>` with an extension from
> the list above**, and confirm the asset actually loads on a live render (§11 step 7).

> ⚠️ **File and library names are sanitized.** When a library file is uploaded through the editor UI, every
> character outside `[A-Za-z0-9._-]` in the library name and in each path segment is replaced with `_`, and the
> stored path becomes `studio/<safeLibName>/<safeRelPath>`. So a lib named `my lib` lands under `studio/my_lib/`
> and a file `Chart Data.min.js` under `Chart_Data.min.js`. If you author the `studioModel` by hand, use the
> sanitized spelling — a hand-written `path` that disagrees with the bytes' real location resolves to a valid-looking
> url that 404s.

```bash
# 1) put the file into the bundle (round-trips into nct-file-storage on import)
python3 mrjun.py asset add studio/echarts/echarts.esm.js ./echarts.esm.js --project ./app
python3 mrjun.py asset ls --project ./app       # verify what will round-trip

# 2) reference it with a RELATIVE path in the studioModel:
#    { "kind": "JS_ESM", "path": "studio/echarts/echarts.esm.js", "entry": true, "order": 0 }
```

Multi-file libs: add each file under the same `studio/<lib>/…` prefix and give each an `order`; assets **inside one
lib** load strictly sequentially. A `.woff2` alone does nothing — a `FONT` asset is loaded as a
`<link rel="stylesheet">`, so fonts must arrive through a `CSS` asset containing `@font-face`.

---

## 11 · How to create one from scratch in `.mrjun`

1. **Node.** Add an `nct.html.plugin` in the page's content container (or in a `nct.parsis.plugin` slot), with a
   **symbolic identifier** you will recognise in `ctx.name`:
   ```bash
   python3 mrjun.py node add --parent "<Page name>" --plugin nct.html.plugin \
       --name "<Screen> UI" --identifier <entity>_ui --project ./app
   ```
2. **Main markup** → `properties.html.stringValue`. **Never leave it empty** — a studio-active node with no `html`
   renders nothing at all (§2). Give every element you drive from JS a stable class under **one prefix you choose
   per component** (`<pfx>-page`, `<pfx>-body`, … — the examples below use `x-`): the same prefix keeps your CSS,
   your `ctx.busy` block selectors and your query selectors from colliding with any other component on the page.
   Keep server-rendered `<plugin>` children *outside* any container you will rewrite (§6.4).
3. **The fetch rule** — one EXECUTION rule per screen, returning `[ok, locale, …lists]`:
   ```bash
   python3 mrjun.py rule add --name "<Screen> Data" --type EXECUTION_RULE \
       --context <context-alias> --script @screen-data.groovy --project ./app
   ```
   Action rules (`Save <Entity>`, `Delete <Entity>`, …) the same way. The Studio **calls** rules, it never
   creates them → [08](08-groovy-rules-and-context.md), [11](11-business-logic-dynamic-crud.md).
4. **(only if vendoring)** `mrjun.py asset add …` (§10). Prefer CDN urls and skip this.
5. **studioModel.** Write the project JSON (§2) to a file and set it:
   ```bash
   python3 mrjun.py node set-studio <node-id-or-name> --json @studioModel.json --project ./app
   ```
6. **Validate + pack.**
   ```bash
   python3 mrjun.py validate --project ./app
   python3 mrjun.py pack ./app app.mrjun
   ```
   `validate` checks the studioModel parses, that every `libNames` entry is declared, and that asset paths are
   relative. It does **not** resolve rule names or CRUD methods — grep them by hand:
   `mrjun.py list rules --project ./app | grep '<Screen> Data'` — it *does* resolve the include graph and ERRORs
   on a cycle (§3.2), but it never expands it.
7. **Live-render.** Import, open the page, and check: the component draws, the breadcrumb buttons appear, the
   browser console is clean, the page source contains no `<!-- dokie: … -->` comment (a failed include — §3.2),
   and the screen still reads correctly on a **dark** skin ([24a](24a-theming-and-dark-mode.md)).

### 11.1 Worked example — an `<Entity>` console

**`properties.html.stringValue`** (the main document):

```html
<div class="x-page">
  <div class="x-head">
    <h2 class="x-title">…</h2>
    <!-- NO icon-wait here: the script drives this button with ctx.busy (§8). Both would arm the
         platform spinner on the same <i> and stack two rings. Pick ONE. -->
    <button type="button" class="btn btn-sm btn-secondary x-refresh">
      <i class="pe-7s-refresh-2"></i><span class="x-refresh-l">Refresh</span>
    </button>
  </div>
  <div class="x-kpis"></div>
  <div class="x-body"><div class="x-empty">Loading…</div></div>
</div>
```

**`css.byTheme["*"]`** — tokens only, no literal hex (see [24a](24a-theming-and-dark-mode.md)):

```css
.x-page   { padding: 12px; color: var(--bs-body-color); }
.x-head   { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.x-kpis   { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.x-kpi    { background: var(--current-line, var(--bs-light));
            border: 1px solid var(--bs-border-color); border-radius: .5rem; padding: 12px; }
.x-kpi b  { display: block; font-size: 1.5rem; line-height: 1.2; }
.x-kpi span { color: var(--comment, var(--bs-secondary)); font-size: .8rem; }
.x-body   { margin-top: 16px; overflow-x: auto; }
.x-empty  { color: var(--comment, var(--bs-secondary)); padding: 24px; text-align: center; }
```

**`scripts[0].code`** (`name:"main"`, `libNames: []`):

```js
// ---- state + helpers -----------------------------------------------------
const state = { rows: [], selectedId: null, busy: false };
const q  = sel => ctx.root.querySelector(sel);
const esc = s => String(s == null ? '' : s);
const arr = x => Array.isArray(x) ? x : (x && Array.isArray(x.content) ? x.content : []);

const MSG = {
  en_US: { title: '<Entity> console', refresh: 'Refresh', neu: 'New <entity>', del: 'Delete',
           empty: 'No <entity> yet', total: 'Total', open: 'Open' },
  hy_AM: { title: '…', refresh: '…', neu: '…', del: '…', empty: '…', total: '…', open: '…' }
};
let LOC = 'en_US';
const t = k => (MSG[LOC] || MSG.en_US)[k] || MSG.en_US[k] || k;

// ---- render --------------------------------------------------------------
function render() {
  q('.x-title').textContent      = t('title');
  q('.x-refresh-l').textContent  = t('refresh');

  q('.x-kpis').innerHTML = '';
  [[t('total'), state.rows.length],
   [t('open'),  state.rows.filter(r => r.status === 'open').length]
  ].forEach(([label, value]) => {
    const d = document.createElement('div');
    d.className = 'x-kpi';
    d.innerHTML = '<b></b><span></span>';
    d.querySelector('b').textContent = value;
    d.querySelector('span').textContent = label;
    q('.x-kpis').appendChild(d);
  });

  const body = q('.x-body');
  body.innerHTML = '';
  if (!state.rows.length) {
    const e = document.createElement('div'); e.className = 'x-empty';
    e.textContent = t('empty'); body.appendChild(e); return;
  }
  const table = document.createElement('table');
  table.className = 'table table-hover mb-0';
  table.innerHTML = '<thead><tr><th>#</th><th>Name</th><th>Status</th></tr></thead><tbody></tbody>';
  const tb = table.querySelector('tbody');
  state.rows.forEach(r => {
    const tr = document.createElement('tr');
    tr.dataset.id = esc(r.id);
    if (String(r.id) === String(state.selectedId)) { tr.classList.add('table-active'); }
    ['id', 'name', 'status'].forEach(f => {
      const td = document.createElement('td'); td.textContent = esc(r[f]); tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
  body.appendChild(table);
}

function fail(msg) {
  const b = q('.x-body'); b.innerHTML = '';
  const a = document.createElement('div'); a.className = 'alert alert-danger mb-0';
  a.textContent = msg; b.appendChild(a);
}

// ---- server --------------------------------------------------------------
const paint = () => new Promise(r => setTimeout(r, 0));   // let the browser draw before we block (§4.4)

async function load() {
  if (state.busy) { return; }
  state.busy = true;
  // First arg is resolved inside ctx.root; `block` is NOT — scope it to this instance (§8).
  const done = ctx.busy('.x-refresh', { block: '#' + ctx.root.id + ' .x-body' });
  await paint();
  try {
    const d = await ctx.callRule('<Screen> Data', {});      // ONE call for the whole screen — and it BLOCKS
    if (!d || d.ok === false) { return fail((d && d.message) || 'No data'); }
    LOC = MSG[d.locale] ? d.locale : 'en_US';
    state.rows = arr(d.rows);
    if (!state.rows.some(r => String(r.id) === String(state.selectedId))) { state.selectedId = null; }
    render(); syncBar();
  } catch (e) {
    fail(String((e && e.message) || e));                    // incl. "dokieCallRule timed out" after 30s
  } finally {
    done(); state.busy = false;
  }
}

// ---- breadcrumb (page-level actions) ------------------------------------
function syncBar() {
  ctx.breadcrumb.set([
    { key: 'new', label: t('neu'), icon: 'pe-7s-plus', variant: 'primary', order: 0,
      onClick: async () => { await ctx.callRule('Create <Entity>', {}); await load(); } },
    { key: 'del', label: t('del'), icon: 'pe-7s-trash', variant: 'danger', order: 1,
      disabled: !state.selectedId, block: '#' + ctx.root.id,   // scoped: `block` is document-wide (§8)
      onClick: async () => {
        await ctx.callRule('Delete <Entity>', { id: state.selectedId });
        state.selectedId = null; await load();
      } }
  ]);
}

// ---- wiring — BEFORE the first await (§6.3): after a teardown ctx.on() silently refuses ----
const onClick = e => {
  const tr = e.target.closest('tr[data-id]');
  if (tr && ctx.root.contains(tr)) {
    state.selectedId = tr.dataset.id;
    render(); ctx.breadcrumb.update('del', { disabled: false });
    return;
  }
  if (e.target.closest('.x-refresh')) { load(); }
};
ctx.root.addEventListener('click', onClick);
ctx.onCleanup(() => ctx.root.removeEventListener('click', onClick));

ctx.on('<entity>:changed', () => load());        // auto-removed at teardown
ctx.api.reload = load;                           // other components: ctx.byName('<entity>_ui').reload()

render();
await load();
```

**`<Screen> Data` (EXECUTION_RULE):**

```groovy
def page = [rowsInPage: 500, pageNumber: 0]
def loc  = 'en_US'
try { loc = service.global.locale.getKey() ?: 'en_US' } catch (Throwable t) { }   // NOT context.data.localeKey
try {
    return [ok: true, locale: loc,
            rows: service.crud.<alias>.findAll(page) ?: []]
} catch (Throwable ex) {
    return [ok: false, locale: loc,
            message: ex.getClass().getSimpleName() + ': ' + (ex.getMessage() ?: 'no message')]
}
```

---

## 12 · Constraints & gotchas

* **Empty `studioModel` ⇒ classic plugin.** Omit the property entirely for pure layout/markup nodes; a trivial
  `{"libs":[],"docs":[],"scripts":[],"css":{"byTheme":{}}}` counts as empty and buys nothing — while a
  *non*-empty one with an empty `html` property renders a blank component (§2).
* **All SELECTED scripts of one instance are ONE program.** (Which ones are selected is legacy-vs-include mode —
  §3.2.) They are concatenated with `\n;\n` into a single
  `AsyncFunction` body, so they share a scope — and a syntax error or a throw in one
  aborts all of them (`[Dokie] compile error …` / `[Dokie] runtime error …` in the console). Script names survive
  only as `//# script: <name>` comments, with no `sourceURL`, so stack traces show one anonymous VM frame.
* **No ES-module syntax in author code.** The body is a `Function`, so static `import`/`export` are syntax errors;
  dynamic `import(url)` works.
* **Script ↔ lib is by NAME**, and the linkage is fragile: if a script declares **no** libs, the runtime loads
  **all** declared libs; but as soon as *one* script declares any, libs nobody declared are **never loaded**.
  Renaming a lib does not update the `libNames` referencing it —
  `validate` ERRORs on the dangling reference.
* **Lib `order` is not a load barrier.** Libs are started concurrently; only
  the assets *inside* one lib are sequential. Two classic libs where B needs A's global can race —
  put both files in ONE lib, ordered.
* **The lib cache is page-global, first-wins.** Two components declaring the same lib name with different
  assets share whichever resolved first.
* **A failed library does not stop your code.** The runtime logs `[Dokie] library load failed …` and runs the
  author body anyway with `ctx.libs = {}` — so guard (`if (!ctx.libs.d3) { … }`) instead of assuming.
* **`ctx.byName()` cannot address a specific placement.** The plugin registry is keyed by content **identifier**
  while instances are keyed by `domId` — placing the same reusable content twice on
  a page leaves the second mount owning `Dokie.plugins[identifier]` ([24b](24b-html-composition-and-plugin-tags.md)).
* **The wrapper id is not stable across page instances.** `dokie-plug-<markupId>`
  is derived from a session-scoped Wicket sequence: page-unique and stable for the life of one component instance
  (a `refresh()` keeps it — §6.2), but different on every fresh page instance and whenever an ancestor re-render
  recreates the node. Read it at runtime as `ctx.root.id` when you need it (§8); never persist it, never write
  CSS against a literal `#dokie-plug-…`.
* **Bridge calls are synchronous and block the page** (§4.4) and reject after 30 s.
* **`ctx.contextData` is a frozen snapshot** and `{}` standalone (§5).
* **Secondary `docs[]` are no longer client-only.** A document pulled in by `<include src="x.html">` or by
  `await ctx.include('x.html', …)` is **server-rendered**, `<plugin>` tags and all (§3.1) — only `ctx.showHtml()`
  is still a bare client-side `innerHTML` swap with no `<include>` expansion, no `<plugin>` and no `<script>`
  execution (§6.4). Unchanged for every document either way: no templating, no interpolation, no escaping helper,
  no `enabled`/`order` fields, and duplicate names collapse.
* **Splitting a component does not shrink what the server parses.** The platform's HTML parse cache is keyed by
  the **whole expanded** document string, so ten small includes cost the same one large cache entry per render as
  the same markup written inline. Includes buy you structure, not a cheaper render — keep component bodies small
  for exactly the reasons you always did.
* **CSS is auto-scoped and specificity-raising.** Every selector is prefixed with the `#dokie-plug-…` id, so your
  rules outrank most host CSS but a library that portals to `document.body` (tooltips, modals, dropdowns) renders
  *outside* the scope and your CSS never reaches it. Details, the `:root/html/body` rewrite and the
  fail-open-on-malformed behaviour → [24a](24a-theming-and-dark-mode.md).
* **NOTHING checks your include graph while you hand-author it.** The rules below are enforced when a human
  saves the component in the authoring UI — which you are not using. Author them correctly yourself, and run
  `mrjun.py validate`, which now reports the three that are decidable offline: an include target that does not
  exist, an `src` with no extension, and an **enabled script that nothing includes** (so it never runs, §3.2). It
  also ERRORs on a **document→document include cycle** — the one shape that cannot be rendered at all.
  Two more are real and offline-invisible, because nothing offline expands the documents, so treat them as your
  own pre-flight list: an `<include>` written inside a `<plugin>` tag (whatever it brings in is dropped by the
  nesting rule), and a `<plugin id>` that appears more than once across the documents that can reach the screen
  (all of them bind ONE child node — and if they name different plugins, every render clears that node's stored
  configuration).
  A loop that runs *through a script* (`page.html` declares `<include src="router.js">` and `router.js` renders
  `page.html`) is legal and not an error: expansion stops at a script, so nothing can recurse, and at runtime the
  browser refuses to open a document that is already open above the target.
* **First-party trust only.** The author body shares the page's global scope (`$`, `bootstrap`, `Wicket`,
  `CodeMirror` are all reachable) and the bridge has no rule/CRUD allowlist (§4.4).

---

## 13 · Done when

**Done when:** every include resolves, and `test-scenarios.md` carries a scenario saying the component must
render with an empty browser console on the tester's import; and
the component's script-selection mode (§3.2) is the one you intended; one `<Screen> Data` rule
feeds the whole screen; every bridge call is inside `try/catch` and renders its error; page-level actions live in
the breadcrumb bar and morph by key as the user drills in; every timer/listener is registered through
`ctx.onCleanup`; the screen is readable on a dark skin; and `mrjun.py validate` exits 0.

- [ ] §1 answered honestly — a stock `crud.table.plugin` + form group genuinely cannot do this screen
- [ ] Node added with a **symbolic identifier** (`mrjun.py node add --identifier <entity>_ui`)
- [ ] `properties.html` is **not empty** (§2) and every JS-driven element has a stable class under one
      component-unique prefix
- [ ] `properties.studioModel` set with `node set-studio`; `libs`/`docs` omitted when unused
- [ ] Every `scripts[].libNames` entry names a declared lib (`validate` ERRORs otherwise)
- [ ] Vendored assets use a **relative** `path` under `studio/<lib>/<file>` with a whitelisted extension, and were
      seen to load on a live page — anything else 403s and `validate` cannot tell (§10)
- [ ] One EXECUTION rule per screen for reads; one per mutating action — all confirmed to exist by name
      (`mrjun.py list rules`)
- [ ] Every rule returns **plain maps/lists/scalars** — a non-serializable value makes the call reject (§4.4)
- [ ] The fetch rule returns `locale` from **`service.global.locale.getKey()`** (never `context.data.localeKey`,
      which is always `null` — §9), and labels come from one message map
- [ ] Every `ctx.callRule`/`ctx.callBl` is wrapped in `try/catch`; empty and error states are rendered
- [ ] **One** bridge call per interaction, never in a loop; a `paint()` yield before the call (the transport is
      blocking — §4.4)
- [ ] No `setHtml`/`showHtml` if the main document contains `<plugin>` tags — a document that carries them is
      brought in with `ctx.include`, into an empty container or with `{mode:'append'}` (§6.4, §3.1)
- [ ] Includes: every `src` carries its **extension** and resolves, and one `.js` include anywhere means **only**
      included scripts run — `validate` resolves both and ERRORs on a cycle; it never expands, so post-expansion
      duplicates stay yours (§3.1, §3.2)
- [ ] `ctx.on(...)` / `ctx.onCleanup(...)` registered **before the first `await`** (§6.3)
- [ ] Timers / non-bus listeners registered via `ctx.onCleanup`; one delegated listener on `ctx.root`
- [ ] Every `block` selector (`ctx.busy`, breadcrumb `block`) is scoped to this instance — it is matched
      document-wide (§8)
- [ ] Breadcrumb buttons: explicit ASCII `key`, an `icon`, an `async` `onClick`, ≤ 20 per instance; the page's
      layout really contains `site.breadcrumb.plugin`
- [ ] `css.byTheme` uses `"*"` + theme tokens (no literal hex); checked on `Standard` **and** a dark skin
- [ ] `mrjun.py validate --project ./app` exits 0, then `mrjun.py pack`
- [ ] **Live-rendered**: component draws, buttons appear and act, console clean

---

**See also:** [24a](24a-theming-and-dark-mode.md) (theme tokens, CSS scoping, dark mode) ·
[24b](24b-html-composition-and-plugin-tags.md) (`<plugin>`/`<include>` grammar, slots, reuse) ·
[24c](24c-html-data-tables-and-paging.md) (server-paged tables in a component) ·
[24d](24d-html-component-structure.md) (splitting one component into documents and scripts — `<include>`,
`ctx.include`, when to split) ·
[14 §1.1](14-plugin-catalog-all.md) (the classic html plugin) ·
[14a](14a-plugin-config-reference.md) (field-level config reference) ·
[01](01-content-model-and-pages.md) (content tree, pages, roleAccess) ·
[04](04-crud-table-plugin.md) (the stock table — and the one-table-per-page rule) ·
[08](08-groovy-rules-and-context.md) (rule types, context) ·
[09](09-groovy-hints-and-live-context.md) (live context data shape) ·
[11](11-business-logic-dynamic-crud.md) (dynamic CRUD methods and paging) ·
[16](16-groovy-service-api.md) (`service.*` API) ·
[19](19-build-decision-procedure.md) (when a custom component enters the plan) ·
[20](20-localization.md) (project locales and per-locale text) ·
[22](22-charts-params-and-filters.md) (charts — reach for these first) ·
[23](23-distribution-and-known-gaps.md) (what `validate` still cannot check) ·
[`tools/README.md`](tools/README.md) (`node set-studio`, `asset add`, `validate`, `pack`)
