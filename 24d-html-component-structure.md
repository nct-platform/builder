# 24d · Structuring an HTML component — files, includes and when to split

> **Scope.** How to lay out the files of ONE `nct.html.plugin` studio component so that what you ship is a small,
> readable project instead of one enormous html string with one enormous script: the file kinds, the **default
> shape** and its line budget, `<include src="…">` wiring and the **run order** that falls out of it, naming
> rules, the split / do-not-split decision procedure, static inclusion vs runtime `ctx.include`, cycles, and a
> worked example. Read it **before** you write the first line of a component — the shape is a decision you make
> once and pay for on every later edit.
> **Not here:** the `studioModel` schema, the whole `ctx` runtime, rules/BL calls, lifecycle and breadcrumb
> actions → [24](24-html-component-studio.md); theme tokens and CSS scoping → [24a](24a-theming-and-dark-mode.md);
> the `<plugin>` **and `<include>`** tag grammar, the tag↔child binding contract and component reuse →
> [24b](24b-html-composition-and-plugin-tags.md); server-paged tables inside a component →
> [24c](24c-html-data-tables-and-paging.md).

| | |
|---|---|
| Where the files live | ONE `nct.html.plugin` node: `properties.html` (the **main document**) + `properties.studioModel` → `docs[]`, `scripts[]`, `libs[]`, `css.byTheme` |
| Static composition | `<include src="…">` — expanded **server side, textually, before parsing**, recursively |
| Two name spaces | `.html` / `.htm` → a document · `.js` / `.mjs` → a script. A `src` with **no** extension is refused, not guessed |
| Run order | **legacy** = every *enabled* script, in the studio's own ordering · **include mode** = *only* included scripts, in the order their tags appear, depth-first from `main.html` |
| Runtime composition | `await ctx.include('<doc>.html', selector[, {mode:'append'}])` — rendered server side, `<plugin>` tags and all; requires `window.Dokie.__v >= 3` |
| Limits | expansion depth 20 · 500 include tags per expansion · 2 000 000 characters of expanded output · runtime: nesting 10, 50 included documents per instance |
| Offline gate | `mrjun.py validate` resolves the graph: a **cycle is an ERROR**, a dangling / extension-less `src` and a never-included enabled script are **WARNs**. Nothing offline **expands**, so the limits and every post-expansion defect are still yours (§8) |
| Not available | includes across components (a `src` only ever addresses documents of the SAME component) · `html.localized.plugin` (no studio model, therefore no includes) |

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `node add --parent <slot> --plugin nct.html.plugin --name "<Screen> UI" --identifier <symbolic>` (the host node),
> `node set-studio <id> --json @studioModel.json` (**all** documents, scripts, libs and CSS in one write — there is
> no per-file command), `asset add <relpath> <localfile>` / `asset ls` (a vendored library file),
> `find --plugin nct.html.plugin`, `show node <id>`.
> ⚠️ There is **no** command that writes `properties.html` — the main document is hand-edited JSON
> ([24b](24b-html-composition-and-plugin-tags.md) §2.6) — and `show node` prints `studioModel` as one escaped
> string, so keep the `studioModel.json` you fed to `set-studio` as the source of truth.
> Every entity command takes `--project <unpacked-dir>` (`unpack`/`pack` take positional paths instead).
> Full index and rules — [`tools/README.md`](tools/README.md);
> before re-importing — `mrjun.py validate`, then `mrjun.py pack <dir> out.mrjun`.

---

## 1 · The mental model — a component is a small PROJECT of files

### 1.1 The five file kinds

One `nct.html.plugin` node holds a miniature source tree. Learn what each kind is *for*, because the split
decisions in §5 are all "which kind does this belong to".

| Kind | Where it lives | What it is for | When it renders / runs |
|---|---|---|---|
| **main document** | `properties.html`, addressed as `main.html` | the root markup: the containers your JS fills, the `<plugin>` slots, and the **include manifest** | always; it is the only document the platform reaches without an include |
| **document** | `studioModel.docs[].name` — e.g. `parts/toolbar` | one visual region, one fragment, or one view shown on demand | wherever it is included — statically at render, or at runtime via `ctx.include` |
| **script** | `studioModel.scripts[].name` — e.g. `render` | ONE responsibility of the component's single program | all selected scripts are concatenated into ONE `AsyncFunction` per instance ([24](24-html-component-studio.md) §3) |
| **library** | `studioModel.libs[]` — a CDN url or a vendored `studio/<lib>/<file>` | third-party code you did not write | before the scripts that name it in `libNames` ([24](24-html-component-studio.md) §2, §12; vendoring → §10) |
| **per-theme CSS** | `studioModel.css.byTheme` | every class every document uses — one block, not one per file | emitted into the page head, auto-scoped to this instance ([24a](24a-theming-and-dark-mode.md)) |

Two properties of this list decide everything else:

* **Documents and scripts are two independent name spaces.** A component may hold a document `report` *and* a
  script `report`. That is exactly why a `src` must carry an extension — the platform will not guess.
* **There is no module system.** Splitting a script into four files does not create four scopes; it creates four
  labelled sections of one program (§3.5). Splitting markup into four documents does not create four DOM
  subtrees; it creates one DOM subtree that four files contributed text to.

### 1.2 One node, one program, one DOM

Everything above lands in a single wrapper element (`ctx.root`) and a single shared JS scope. So:

* a class defined in `parts/toolbar` is styled by the same `css.byTheme["*"]` block as everything else — use
  **one CSS prefix for the whole component**, not one per file (§4, [24a](24a-theming-and-dark-mode.md));
* a `<plugin>` tag written in an included document binds to a child node of the **host** node, exactly as if you
  had written it in `main.html` (§6);
* `ctx.root.querySelector('.<pfx>-body')` reaches an element contributed by any document, because by the time
  your scripts run there is only markup, not files.

### 1.3 What `<include>` is — and what it is not

`<include src="parts/toolbar.html"/>` is a **server-side textual substitution performed before the platform
parses the html**. The included document's text replaces the tag, recursively, and only then is the result
parsed. It is not a client-side fetch, not a template call, and it passes no parameters — there is no way to
give an included document a variable. If a fragment needs data, it needs your renderer script, not an include.

`<include src="data.js"/>` renders nothing at all. It is a **declaration**: "this script belongs to this
component's program" (§3).

> ✅ **An included document is NOT a client-only fragment.** Everything reachable from `main.html` through
> `<include>` — and everything a script pulls in with `ctx.include` — is **server-rendered**, so its `<plugin>`
> tags become real, live child components to any nesting depth. The "secondary documents are inert" rule survives
> in exactly one place: `ctx.showHtml`, which is still a plain client-side `innerHTML` swap that cannot render a
> `<plugin>`, cannot expand an `<include>`, and does not run a `<script>`.

---

## 2 · ⛔ The default shape you must produce

> ⛔ **ONE DOCUMENT PLUS ONE SCRIPT IS THIS PLUGIN'S DEFAULT FAILURE MODE.**
> **Mechanism:** nothing forces a split. The path of least resistance is to append to `properties.html` and to
> `scripts[0].code` until the component is a 900-line markup string and a 1 200-line function, both stored as
> escaped JSON inside an export.
> **Symptom:** you cannot find the twenty lines that own a bug; a stray `}` anywhere in the program produces one
> `[Dokie] compile error` and the component renders its static markup and then does **nothing**
> ([24](24-html-component-studio.md) §3); two edits in one week collide because everything is in one string; the
> next AI asked to change the screen rewrites the whole file and loses behaviour.
> **Caught by `validate`?** **No.** It never looks at size or structure (the graph it does check is §8).
> **Fix:** split along the budget below, before the component grows — retrofitting a split means re-deriving the
> run order of code you no longer remember.
> **Rule: decide the file layout when you create the node, and write the include manifest before the first
> feature.**

### 2.1 The budget

Two different budgets. The **floor** (§2.4) is about the whole component and decides *whether* to split at all:
under ~150 lines of markup **and** ~200 lines of script, do not split. The table below is the **ceiling per
file**, and applies only once you are above the floor. These numbers are signals, not laws — but treat crossing
one as a decision you must justify in a comment **at the top of the offending file**, in the form
`// over budget: <reason>`.

| Unit | Green | Split when |
|---|---|---|
| `main.html` | ≤ 120 lines | over 120 lines, **or** it contains 3+ visually independent regions |
| any other document | ≤ 120 lines | over 120 lines |
| any one script | ≤ 150 lines | over 150 lines, **or** it does two of {bootstrap+state, server access, rendering, event wiring} |
| documents per component | 1–6 | over **6** — a 7th document usually means two screens, not one component |
| scripts per component | 1–5 | over **5** — past `boot`/`data`/`render`/`events` plus one, split the screen instead |
| whole component | ≤ ~400 lines markup + ~600 lines JS | beyond that, re-read [24b §9](24b-html-composition-and-plugin-tags.md): half of it probably wants to be embedded stock plugins |

> ⚠️ **Splitting buys readability, not render performance.** The platform's html parse cache is keyed by the
> **whole expanded html string**, and for a studio-active node it gains a fresh key on every render
> ([24b §8.3](24b-html-composition-and-plugin-tags.md)) — so a large component split across ten documents
> produces exactly the same large cache entry per render as the same markup in one string. Includes do not make
> the cache smarter. Keep the **total expanded size** small; use the split to keep yourself sane.

### 2.2 The default layout

For anything that crosses the budget, produce this. Slash-separated names are **folders in the studio
navigator** (§4), which is why the layout reads like a directory tree:

```
main.html                 the shell: containers, <plugin> slots, and the include manifest
parts/header.html         one visual region
parts/filters.html        one visual region
parts/row.html            a repeated fragment: included ONCE into a hidden host, cloned by the renderer
views/detail.html         a region shown on demand, loaded with ctx.include
boot.js                   shared state, constants, helpers, runtime-version guard
data.js                   every ctx.callRule / ctx.callBl — and nothing else
render.js                 every DOM write — and no server call
events.js                 listeners, breadcrumb buttons, the single entry point
```

Four responsibilities is the right script split for almost every screen. `boot` first (everything else reads its
state), `data` and `render` next (they only declare functions), `events` last — it is the only file that *does*
anything at load time.

### 2.3 The `studioModel` for that layout

This is the JSON you write and hand to `mrjun.py node set-studio`. Stored names carry **no extension**; the
`src` attributes that reference them do (§4).

```jsonc
{
  "libs": [],
  "docs": [
    { "name": "parts/header",  "html": "<div class=\"pfx-head\">…</div>" },
    { "name": "parts/filters", "html": "<div class=\"pfx-filters\">…</div>" },
    { "name": "parts/row",     "html": "<div class=\"pfx-row\">…</div>" },
    { "name": "views/detail",  "html": "<div class=\"pfx-detail\">…</div>" }
  ],
  "scripts": [
    // `enabled:false` keeps a script OFF even when it is included (§3.2).
    // `order` no longer decides the run order in include mode — keep it matching the
    // include order anyway, so the navigator lists the files the way the program runs,
    // and so that a later reader who removes the last `.js` include drops back into
    // legacy mode (§3.1, where `order` IS the ordering) with the run order unchanged.
    { "name": "boot",   "code": "…", "enabled": true, "order": 0, "libNames": [] },
    { "name": "data",   "code": "…", "enabled": true, "order": 1, "libNames": [] },
    { "name": "render", "code": "…", "enabled": true, "order": 2, "libNames": [] },
    { "name": "events", "code": "…", "enabled": true, "order": 3, "libNames": [] }
  ],
  "css": { "byTheme": { "*": ".pfx-page{padding:12px;color:var(--bs-body-color)} …" } }
}
```

and the matching `main.html` (`properties.html.stringValue`):

```html
<div class="pfx-page">
  <include src="parts/header.html"/>
  <include src="parts/filters.html"/>
  <div class="pfx-body"><div class="pfx-empty">Loading…</div></div>
  <div class="pfx-detail-host"></div>

  <!-- the row template: included ONCE, hidden, cloned per row by render.js -->
  <div class="pfx-tpl" hidden><include src="parts/row.html"/></div>

  <!-- The program. This block IS the run order (§3.3). A .js include renders nothing. -->
  <include src="boot.js"/>
  <include src="data.js"/>
  <include src="render.js"/>
  <include src="events.js"/>
</div>
```

Note what is **not** in the manifest: `views/detail.html` is never statically included at all — it is pulled in
by `ctx.include` when the user drills in (§7). And `parts/row.html` is included exactly **once**, into a hidden
host, precisely because a repeated fragment must never become one include per repetition (§5, step 4).

> ⚠️ **Keep a row template `<div>`-based.** Everything you author is re-serialized by jsoup before it renders
> ([24b §2.1](24b-html-composition-and-plugin-tags.md)), so a bare `<tr>` parked outside a `<table>` does not
> survive the trip and your renderer finds nothing to clone. Build table rows in `render.js` instead, and reserve
> the hidden-template trick for card-shaped fragments.

### 2.4 When one file is correct

A component under **~150 lines of markup and ~200 lines of script** should be exactly one `properties.html` and
one script named `main`, with no `docs[]` and no include manifest at all. That component then runs in **legacy
mode** (§3.1) and behaves as every component built before includes existed. Splitting it produces a wiring
diagram for a card — which is its own kind of unreadable.

---

## 3 · Wiring — who includes whom, and the run order that falls out

### 3.1 Two modes, and the component picks one by accident

| | Legacy mode | Include mode |
|---|---|---|
| **Entered when** | **no** document reachable from `main.html` declares a `<include src="….js">` | **any** reachable document declares one — the `.js` **extension** decides, so a `src` that resolves to **no** script of the component still flips the mode |
| **Which scripts run** | every **enabled** script | **only** the included ones (still subject to `enabled`) |
| **In what order** | the studio's own ordering (`scripts[].order`) | the order the `<include src="….js">` tags appear, depth-first from `main.html` |

There is no switch and no flag: the first script include you write flips the whole component. Everything built
before this feature existed keeps running unchanged, because it has no js includes.

### 3.2 ⛔ The first js include disables every script you did not include

> ⛔ **THE MOMENT ONE DOCUMENT DECLARES A SCRIPT INCLUDE, EVERY SCRIPT NOBODY INCLUDED STOPS RUNNING.**
> **Mechanism:** include mode replaces "all enabled scripts" with "the included scripts, in tag order". A script
> left out of the manifest is simply not part of the program any more — `enabled: true` does not save it.
> **Symptom:** you split a working component, add `<include src="boot.js"/>` and `<include src="render.js"/>`,
> forget `events.js` — and the screen draws but nothing responds to a click. The console is clean; there is no
> error, because the code was never compiled in.
> **Caught by `validate`?** **Yes, as a WARN** — "enabled but no reachable document includes it". Read your
> WARNs; it is not an ERROR and `pack` will happily proceed (§8).
> **Fix:** every enabled script appears in the manifest exactly once; anything you want off gets
> `"enabled": false` **and** stays out of the manifest.
> **Rule: the manifest and `scripts[]` must list the same names, in the same order.**

> ⛔ **A `.js` src that resolves to NOTHING still switches the component into include mode.**
> **Mechanism:** the **extension** is the mode signal, not the resolution. Misspell the only script include —
> `src="bot.js"` when the script is stored as `boot` — and the program is **empty**: the markup renders, not one
> line of author JS runs, and the console is clean, because there is no code to fail.
> **Symptom:** a component that looks finished and is completely inert — no listeners, no data, no errors.
> **Caught by `validate`?** **Yes, as WARNs** — the missing target (`<include src='bot.js'> resolves to no script
> of this component`, which lists the real stored names), plus one saying the component is in include mode while
> **not one** script include resolves, so its program is EMPTY, plus the "enabled but nothing includes it" WARN
> for every script you have.
> **Rule: a missing-target WARN on a `.js` src never means "a fragment is missing" — it means part or all of
> your program is dead. Fix it before anything else.**

The mirror trap is quieter: an **included but disabled** script does not run either, and nothing anywhere says
so. Use `enabled:false` only as a deliberate "keep this file, don't run it".

### 3.3 Put every script include in `main.html`

A js include renders nothing, so its position in the markup is free — but its position **is** the run order. If
`parts/header.html` declares `header.js` and `main.html` declares `boot.js` *after* including that part, then
`header.js` runs **first**, before the state it depends on exists.

> ✅ **Rule: write every `<include src="….js">` in `main.html`, in one block, in the order you want them to
> run. Let no other document declare a script.** Then the run order is a list you can read in one place, and it
> cannot change because someone reordered two regions.

Only break it for a document that is genuinely optional — a view included at runtime that brings its own module
of code. Even then, keep it to one file and comment the coupling.

### 3.4 Reading the run order when you did break it

Expansion is depth-first from `main.html`, in document order. Walk the tree and append:

```
main.html
├─ <include src="parts/header.html"/>       →  descend
│    └─ <include src="header.js"/>          →  1st script
├─ <include src="parts/filters.html"/>      →  descend (declares nothing)
├─ <include src="boot.js"/>                 →  2nd script
├─ <include src="data.js"/>                 →  3rd
└─ <include src="events.js"/>               →  4th
```

Reachability is a **fixpoint**, not a single pass: a document that only ever appears as a literal in a script's
`ctx.include('views/detail.html')` call is still reachable, and its own script includes join the program too.

> ⚠️ **A script include inside a runtime-loaded document does not run when you load it.** Selection happens once,
> up front; the scripts run as one program at mount, whether or not the user ever opens that view. `ctx.include`
> inserts markup — it never executes a script.

### 3.5 One shared scope — what splitting does NOT buy you

All selected scripts are concatenated into ONE `AsyncFunction` body per instance. Consequences you must design
for:

* **`const` in `boot.js` is visible in `events.js`** — that is the whole reason the layout works. Declare shared
  state once, in the first file.
* **Two files may not declare the same top-level name.** `const S = …` in two scripts is a `SyntaxError`; the
  whole program fails to compile and the component renders static markup and does nothing.
* **Order is a real dependency.** A function *declaration* is hoisted across the whole body, but a `const`/`let`
  is not: code from an earlier file that touches a `const` declared in a later file throws
  `Cannot access 'S' before initialization` at run time. Keep `boot` first.
* **No `import` / `export`.** The body is a function, so module syntax is a syntax error; dynamic `import(url)`
  works ([24](24-html-component-studio.md) §12).
* **One throw kills everything.** Splitting files does not isolate failures — it only tells you which section to
  read.

### 3.6 Where an include is **not** expanded

`<include>` is not expanded inside `<!-- … -->`, `<script>`, `<style>` or `<textarea>`, and **is** expanded
inside `<pre>` ([24b §2.7](24b-html-composition-and-plugin-tags.md)). Two practical uses:

* **Commenting out an include really disables it** — the honest way to switch a region off, since a `docs[]`
  entry has no `enabled` flag at all.
* You **cannot** assemble a `<script>` block out of includes, and you cannot include into a `<style>`.

---

## 4 · Naming — stored names, extensions, folders, prefixes

| Kind | Stored name (`docs[].name` / `scripts[].name`) | Written in `src` | Shown in the studio |
|---|---|---|---|
| main document | *(none — it is `properties.html`)* | `main.html` | `main.html` |
| region part | `parts/header` | `parts/header.html` | `parts/header.html` |
| on-demand view | `views/detail` | `views/detail.html` | `views/detail.html` |
| script | `boot` | `boot.js` | `boot.js` |

The rules, all mechanical:

1. **Store names without an extension; write every `src` with one.** Stored names are unchanged from before this
   feature — there is no schema change and no migration — which is precisely why every existing `.mrjun` and
   every existing `ctx.showHtml('detail')` call keeps working. The studio only *displays* the extension, and its
   rename field accepts either spelling and stores the bare one. `ctx.showHtml` likewise accepts `'detail'` and
   `'detail.html'`.
2. The mechanical resolution rule — extension picks the name space, `./` is dropped, the whole `src` is also
   matched verbatim — is [24b §2.7](24b-html-composition-and-plugin-tags.md).
3. ⛔ **A slash is a display folder, not a path.** There is no directory traversal, no `..`, and **no relative
   resolution against the including document**. From inside `parts/header.html`, the sibling part is still
   `src="parts/row.html"` — always the full stored name. `src="row.html"` resolves to nothing.
4. **`main.html` addresses the `html` property.** Never create a `docs[]` entry named `main` — it is dropped.
5. **One CSS class prefix per component**, used by every document: `<pfx>-page`, `<pfx>-body`, `<pfx>-row`. All
   the markup lands in one wrapper, so per-file prefixes buy nothing and a generic class collides with the other
   component on the page — including through `ctx.busy`'s document-wide `block` selector
   ([24](24-html-component-studio.md) §8, [24a](24a-theming-and-dark-mode.md)).
6. Keep folder names semantic and few: `parts/` for fragments composed into the shell, `views/` for whole
   regions swapped in at runtime, flat names for the program. Do not mirror a JS project's `src/components/...`
   — the navigator is two levels deep at most before it stops helping.

---

## 5 · The decision procedure — do I split, and how?

**Step 1 is the only question that can stop the procedure.** Answer it first; if it is *yes*, you are done.
Otherwise apply steps 2–7 **in order and cumulatively** — they are independent questions, not alternatives — and
stop adding files when step 8 applies.

1. **Is the whole component under ~150 lines of markup and ~200 lines of script?**
   → **Do not split.** One `properties.html`, one script named `main`, no `docs[]`, no manifest (§2.4). Stop.
2. **Does the markup contain a visually independent region you can name** — a toolbar, a filter bar, a KPI
   strip, a card, a footer?
   → One document per region: `parts/<region>`, statically included from `main.html` in visual order. A region is
   worth its own document when it is ≥ 15 lines of markup **and** has a name a user would recognise (toolbar,
   filter bar, KPI strip, card, footer). Under 15 lines it stays in the shell.
3. **Is a region absent at first paint and shown on demand** — a drill-in panel, a tab body, a wizard step, the
   contents of a modal?
   → One document per view: `views/<name>`, **not** in the manifest, loaded with `ctx.include` when the user asks
   — unless the size rule of §7 sends it to a hidden static include instead.
4. **Does a fragment repeat — per row, per card, per tile?**
   → It does **not** become one include per repetition. Either build it in `render.js` with `createElement`, or
   keep `parts/row.html` as a single template you include once into a hidden container and `cloneNode(true)`.
   ⛔ Never `ctx.include` in a loop: N rows would be N server round trips.
5. **Is one script doing two of {bootstrap+state, server access, rendering, event wiring}?**
   → Split by responsibility into `boot` / `data` / `render` / `events`. This is the split that pays; splitting a
   script "by feature" before this one is done just moves the mess.
6. **Is a script still over ~150 lines after (5)?**
   → Split the biggest responsibility by feature and keep the halves adjacent in the manifest. Name them
   `render/table` and `render/detail` — the same slash-is-a-folder display rule as documents (§4).
7. **Does a region carry its own `<plugin>` child** (an embedded chart, a table, a label)?
   → Fine, and often the point — but that document is then a **static** include used **exactly once** (§6).
8. **Otherwise → stop.** A fragment used once, never conditionally, containing no `<plugin>`, belongs where it
   already is. Every file you add is a name someone must resolve, a second place to look, and a chance to write a
   dangling `src`.

---

## 6 · `<plugin>` tags in a split component

Because expansion is textual and happens before parsing, a `<plugin>` tag written in an included document is a
real, live child of the **host** node at any include depth (§1.3), bound by `id` ↔ `identifier` and `name` ↔
`pluginName` — the full contract is [24b §3](24b-html-composition-and-plugin-tags.md).

> ✅ **Rule: a document that carries `<plugin>` tags is included STATICALLY and EXACTLY ONCE.** Everything that
> repeats, and everything loaded at runtime more than once, must be plugin-free.

Two traps that are 24b's to explain in full and yours to obey: including such a document **twice** duplicates its
`<plugin id>`s and both tags then resolve to one child node
([24b §2.7](24b-html-composition-and-plugin-tags.md)), and an `<include>` written between `<plugin>` and
`</plugin>` brings in nothing ([24b §5](24b-html-composition-and-plugin-tags.md)). Neither is caught offline:
both only exist after expansion, and nothing offline expands (§8).

At runtime the same care applies in reverse: `ctx.include` **replaces** its target's content by default, and
replacing a target that already holds server-rendered components destroys their DOM while the server still
tracks them — the embedded chart or table vanishes, and a later AJAX update targeting it updates nothing, with
**no console warning**: the runtime's warning fires only when the target holds another studio HTML component.
Include into an **empty** container, or pass `{mode:'append'}`. This is the same
family of mistake as `ctx.setHtml`/`ctx.showHtml` over a document containing `<plugin>` tags
([24](24-html-component-studio.md) §6.4).

---

## 7 · Static `<include>` vs runtime `ctx.include`

| | static `<include src="x.html">` | `await ctx.include('x.html', sel[, opts])` |
|---|---|---|
| **Chosen by** | you, at authoring time | your code, at runtime — from a click, a state, a role flag |
| **On screen at first paint** | yes | no |
| **Cost** | none beyond the one page render — textual substitution before parsing | **one server round trip per call**; same discipline as any bridge call ([24 §4.4](24-html-component-studio.md)): never in a loop, never per row |
| **`<plugin>` tags become live children** | yes | yes |
| **`src` / name must carry `.html`** | yes | yes |
| **Where it lands** | in place of the tag | replaces the target's content, or appends with `{mode:'append'}` |
| **Survives a component re-render** | it is part of the render | **no** — nodes it inserted are removed when the component re-renders, so nothing is orphaned; re-issue it from your re-run script if you need it back |
| **Failure** | an HTML comment carrying the diagnosis + a studio warning; the page still renders | the Promise **rejects** with an `Error` (missing document, no matching element, a cycle, a limit) and always settles — so `try/catch` it |
| **Cycle protection** | `validate` ERRORs on a document→document loop; at render the offending include degrades to a comment | refuses a document already open above the target; nesting capped at 10, 50 included documents per instance |
| **Guard needed** | none | `if ((window.Dokie.__v \|\| 0) < 3) { … }` — an older cached runtime has no `ctx.include`, and one `TypeError` aborts the whole program |

**The decision rule.** Known at render time → static. Chosen by the user → runtime. Repeated per row → neither
(§5, step 4). A pure text/data change inside a region you already drew → plain DOM writes, not an include.

```js
// events.js — a drill-in view, loaded once per selection.
async function openDetail(id) {
  const host = ctx.root.querySelector('.pfx-detail-host');
  host.innerHTML = '';                                     // empty target: include REPLACES its content
  if ((window.Dokie.__v || 0) < 3) {                       // an older cached runtime has no ctx.include
    host.textContent = 'Please reload this page (Ctrl+F5).';
    return;
  }
  try {
    await ctx.include('views/detail.html', '.pfx-detail-host');   // selector is resolved inside ctx.root first
    const d = await fetchOne(id);                          // then fill it — the document carries no data
    ctx.root.querySelector('.pfx-f-number').textContent = d.number || '';
  } catch (e) {                                            // no helper — the snippet stands on its own
    const err = document.createElement('div');
    err.className = 'alert alert-danger mb-0';
    err.textContent = String((e && e.message) || e);
    host.appendChild(err);
  }
}
```

> ⚠️ **`ctx.include` costs a round trip that a hidden static include does not.** A drill-in like the one above is
> *two* round trips (the markup, then the data).
> **The size rule.** A view under ~40 lines of markup that every user eventually opens → static include into a
> hidden container (zero extra round trips; it only grows the expanded body, which is the parse-cache key).
> Anything larger, or opened by a minority of users, or one of several mutually exclusive views →
> `ctx.include` at runtime, so it never enters the main expansion.

> ⚠️ **Only a LITERAL name is seen by the reachability analysis.** `ctx.include('views/detail.html')` makes that
> document reachable, so its own script includes join the program. `ctx.include(name + '.html')` does not — the
> document still loads at runtime, but any script it declares was never selected and never runs. Symptom: the
> view appears and is dead. Keep the name a literal string; branch on which literal you pass.

`ctx.showHtml` is a third thing and unchanged — client-side `innerHTML`, no `<plugin>`, no `<include>`, no
`<script>` (§1.3). Use `ctx.include` whenever the document must be *rendered*.

---

## 8 · Cycles and the offline gate — what `validate` sees, and what only the page shows

A cycle is a document that includes itself, directly or through any chain: `main.html` → `parts/a.html` →
`parts/b.html` → `parts/a.html`. It has no meaning — expansion would never terminate.

> ⛔ **A CYCLE NOW FAILS `validate`; EVERYTHING THAT NEEDS EXPANSION STILL ONLY FAILS ON THE PAGE.**
> **Mechanism:** `validate` walks each component's graph from `main.html`, resolving every `<include src>` and
> every **literal** `ctx.include('…')`. A cycle is an **ERROR**, printed as the loop path
> (`main.html -> a.html -> a.html`); a dangling `src`, an extension-less `src` and — once the component is in
> include mode — an enabled script no reachable document includes are **WARNs**, as is an include mode in which
> **no** script include resolves at all (an empty program, §3.2). A loop that runs *through a
> script* is legal and is neither an error nor a warning: expansion stops at a script, so nothing recurses, and a
> document declaring the very script that renders it is the normal shape, not a mistake.
> **Symptom of what stays hidden:** import is clean, `validate` exits 0, `pack` succeeds — and on the live page
> one region is missing, with an HTML comment `<!-- dokie: … -->` carrying the diagnosis in its place. Nothing
> throws and nothing hangs.
> **Caught by `validate`?** **Cycle: yes (ERROR). Dangling / extension-less `src` / never-included enabled
> script: yes (WARN). Anything that only exists after expansion: no.**
> **Fix:** keep the include graph a **tree of depth ≤ 2** — depth 1 = a document `main.html` includes; depth 2 =
> a document that document includes. `main.html → parts/header.html` is depth 1; nothing below depth 2 should
> exist, and `views/…` loaded by `ctx.include` does not count towards it. That makes a cycle impossible by
> construction. Then run the gate below before every `pack`.
> **Rule: `validate` green means the graph resolves; only the live page proves the expansion is what you
> meant.**

The runtime has its own guard for the dynamic half: `ctx.include` refuses a document that is already open above
the target element, caps nesting at 10, and caps a component instance at 50 included documents — each breach
rejecting the Promise rather than looping. The static expander caps depth at 20, 500 include tags per expansion
and 2 000 000 characters of output; a breach degrades to a comment plus a studio warning. If you are anywhere
near any of these numbers, the shape is wrong (§2.1), not the limit.

```bash
python3 mrjun.py validate --project ./app
```

What that leaves for you, because nothing offline **expands**: an `<include>` written inside a `<plugin>`, a
`<plugin id>` that only becomes a duplicate after expansion, the depth-20 / 500-tag / 2 000 000-character limits,
a computed `ctx.include(name + '.html')`, and any studio component that lives in a `virtualPlugins[]` definition
rather than a page's own content (the scan walks a page's own content only). Each of those is a live-page check:
open it and search the source for `dokie:` (§10).

---

## 9 · Worked example — a declaration-review console

One `nct.html.plugin` node, identifier `decl_review_ui`, CSS prefix `decl-`. Four documents, four scripts, two
rules. Nothing here is longer than the budget in §2.1.

**File list**

```
main.html            shell + include manifest
parts/toolbar        title, search box, status filter, refresh button
parts/summary        three KPI tiles
views/detail         the drill-in card — NOT in the manifest, loaded by ctx.include
boot.js              state + helpers + runtime guard
data.js              the two rule calls
render.js            all DOM writes
events.js            listeners + the entry point
```

**Include wiring and run order.** `main.html` → `parts/toolbar.html`, `parts/summary.html` (markup, spliced in
place), then the manifest. Neither part declares a script, so the run order is exactly the manifest:
`boot.js` → `data.js` → `render.js` → `events.js`. `views/detail.html` is reachable only through the literal in
`events.js`; it declares no script, so it contributes nothing to the program. It is loaded at runtime here to
show the mechanism — at 10 lines of markup it sits under the size rule of §7, so a hidden static include would
be the cheaper choice in a real build; make it runtime once it grows or once there are several such views.

**`main.html`** (`properties.html.stringValue`):

```html
<div class="decl-page">
  <include src="parts/toolbar.html"/>
  <include src="parts/summary.html"/>
  <div class="decl-body"><div class="decl-empty">Loading…</div></div>
  <div class="decl-detail-host"></div>

  <!-- the program, in run order -->
  <include src="boot.js"/>
  <include src="data.js"/>
  <include src="render.js"/>
  <include src="events.js"/>
</div>
```

**`parts/toolbar`**:

```html
<div class="decl-bar">
  <h2 class="decl-title">Declaration review</h2>
  <div class="decl-filters">
    <input type="search" class="form-control form-control-sm decl-q" placeholder="Search…">
    <select class="form-select form-select-sm decl-status">
      <option value="">All</option><option value="new">New</option><option value="held">Held</option>
    </select>
    <button type="button" class="btn btn-sm btn-secondary decl-refresh"><i class="pe-7s-refresh-2"></i></button>
  </div>
</div>
```

**`parts/summary`**:

```html
<div class="decl-kpis">
  <div class="decl-kpi" data-k="total"><b>—</b><span>Total</span></div>
  <div class="decl-kpi" data-k="held"><b>—</b><span>Held</span></div>
  <div class="decl-kpi" data-k="cleared"><b>—</b><span>Cleared</span></div>
</div>
```

**`views/detail`** — no `<plugin>` tag, because it is inserted at runtime and could be inserted again (§6):

```html
<div class="decl-detail">
  <h3 class="decl-detail-t">Declaration</h3>
  <dl class="decl-dl">
    <dt>Number</dt><dd class="decl-f-number"></dd>
    <dt>Status</dt><dd class="decl-f-status"></dd>
    <dt>Consignee</dt><dd class="decl-f-consignee"></dd>
  </dl>
  <button type="button" class="btn btn-sm btn-secondary decl-close">Close</button>
</div>
```

**`boot.js`** — runs first; everything below reads `S` and the helpers:

```js
// boot.js — shared scope for the whole program. Declare state ONCE, here.
const S  = { rows: [], total: 0, page: 0, size: 25, q: '', status: '', openId: null, busy: false };
const q1 = sel => ctx.root.querySelector(sel);
const qa = sel => Array.prototype.slice.call(ctx.root.querySelectorAll(sel));
const paint = () => new Promise(r => setTimeout(r, 0));   // let the browser draw before we block (24 §4.4)

const CAN_INCLUDE = (window.Dokie.__v || 0) >= 3;         // an old cached runtime has no ctx.include
if (!CAN_INCLUDE) {
  q1('.decl-body').textContent = 'Please reload this page (Ctrl+F5).';
}
```

**`data.js`** — every server call, and no DOM:

```js
// data.js — ONE call per interaction; the bridge is blocking (24 §4.4).
async function fetchPage() {
  const r = await ctx.callRule('Declaration Page',
                               { page: S.page, size: S.size, q: S.q, status: S.status });
  if (!r || r.ok === false) { throw new Error((r && r.message) || 'No data'); }
  S.rows  = r.content || [];
  S.total = r.totalElements || 0;
  return r;
}
async function fetchOne(id) { return ctx.callRule('Declaration Detail', { id: id }); }
```

**`render.js`** — every DOM write, and no server call:

```js
// render.js — pure drawing. Never awaits.
function renderKpis(k) {
  qa('.decl-kpi').forEach(el => {
    const v = k && k[el.dataset.k];
    el.querySelector('b').textContent = (v == null ? '—' : v);
  });
}
function renderRows() {
  const body = q1('.decl-body'); body.innerHTML = '';
  if (!S.rows.length) { body.appendChild(el('div', 'decl-empty', 'Nothing to review')); return; }
  const t = document.createElement('table'); t.className = 'table table-hover mb-0';
  t.innerHTML = '<thead><tr><th>Number</th><th>Status</th><th>Consignee</th></tr></thead><tbody></tbody>';
  const tb = t.querySelector('tbody');
  S.rows.forEach(r => {
    const tr = document.createElement('tr'); tr.dataset.id = r.id;
    ['number', 'status', 'consignee'].forEach(f => tr.appendChild(el('td', '', r[f])));
    tb.appendChild(tr);
  });
  body.appendChild(t);
}
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) { n.className = cls; }
  n.textContent = (text == null ? '' : String(text));      // textContent — never innerHTML with server text
  return n;
}
function fail(msg) { const b = q1('.decl-body'); b.innerHTML = ''; b.appendChild(el('div', 'alert alert-danger mb-0', msg)); }
```

**`events.js`** — the only file that does anything at load time:

```js
// events.js — wiring BEFORE the first await (24 §6.3), then the single entry point.
const onClick = e => {
  const tr = e.target.closest('tr[data-id]');
  if (tr)                                { return openDetail(tr.dataset.id); }
  if (e.target.closest('.decl-close'))   { q1('.decl-detail-host').innerHTML = ''; S.openId = null; return; }
  if (e.target.closest('.decl-refresh')) { return load(); }
};
ctx.root.addEventListener('click', onClick);
ctx.onCleanup(() => ctx.root.removeEventListener('click', onClick));
ctx.on('declaration:changed', () => load());

async function load() {
  if (S.busy) { return; }
  S.busy = true;
  const done = ctx.busy('.decl-refresh', { block: '#' + ctx.root.id + ' .decl-body' });
  await paint();
  try { const r = await fetchPage(); renderKpis(r.kpis); renderRows(); }
  catch (e) { fail(String((e && e.message) || e)); }
  finally  { done(); S.busy = false; }
}

async function openDetail(id) {
  S.openId = id;
  const host = q1('.decl-detail-host'); host.innerHTML = '';        // empty target — include REPLACES it
  if (!CAN_INCLUDE) {                                               // guard, not decoration (§7)
    host.appendChild(el('div', 'alert alert-warning mb-0', 'Please reload this page (Ctrl+F5).'));
    return;
  }
  try {
    await ctx.include('views/detail.html', '.decl-detail-host');    // literal name (§7)
    const d = await fetchOne(id);
    q1('.decl-f-number').textContent    = d.number    || '';
    q1('.decl-f-status').textContent    = d.status    || '';
    q1('.decl-f-consignee').textContent = d.consignee || '';
  } catch (e) { host.appendChild(el('div', 'alert alert-danger mb-0', String((e && e.message) || e))); }
}

await load();                                    // the only top-level await in the program
```

**Wiring it up:**

```bash
python3 mrjun.py node add --parent "Declaration review" --plugin nct.html.plugin \
    --name "Declaration review UI" --identifier decl_review_ui --project ./app
# properties.html is hand-edited JSON — there is no CLI for it (24b §2.6)
python3 mrjun.py node set-studio decl_review_ui --json @studioModel.json --project ./app
python3 mrjun.py validate --project ./app          # include graph: cycle = ERROR, dangling src = WARN (§8)
python3 mrjun.py pack ./app app.mrjun
```

---

## 10 · Anti-patterns, and what you will actually see

| Anti-pattern | The symptom you will see |
|---|---|
| One `properties.html` and one script, both grown past a thousand lines | one stray `}` produces `[Dokie] compile error` and the component renders its markup and does nothing; nobody can locate the region that owns a bug |
| Split into files, then forgot one in the manifest | the screen draws but does not react. Console clean — that script was never compiled in (§3.2) |
| An included script left `"enabled": false` | same silence, one file further along; nothing reports it (an enabled script nobody includes is the mirror case, and that one is a `validate` WARN — §8) |
| Two scripts declaring `const S` | `[Dokie] compile error`, whole program dead — the shared scope is one scope (§3.5) |
| Code in an early file touching a `const` from a later file | `Cannot access 'S' before initialization` at run time (§3.5) |
| A script include written inside a part instead of `main.html` | the run order silently changes when someone reorders two regions (§3.3) |
| `src="row.html"` from inside `parts/list.html` when the name is `parts/row` | an HTML comment where the fragment should be; nothing in the console — a `validate` WARN offline (§4, §8) |
| `src="parts/row"` — no extension | the same comment plus a studio warning: the platform will not guess between the document and a script of that name — also a `validate` WARN (§4, §8) |
| `src="bot.js"` when the script is stored as `boot` | that script is dropped from the program, and if it was the only script include the component runs **no JS at all** — markup only, console clean; `validate` WARNs (§3.2) |
| A part containing a `<plugin>`, included twice | two slots that always show the same thing; if `name=` disagrees, the child's properties are cleared on every render (§6) |
| `<include>` written between `<plugin …>` and `</plugin>` | the fragment is simply absent — no element, no error (§6) |
| `ctx.include` per row inside a loop | one server round trip per row; the tab freezes and the list takes seconds to appear (§7) |
| `ctx.include` into a container that already holds a `<plugin>` child | the embedded chart/table vanishes and never returns until a full page reload; no console trace at all — the only symptom is the component disappearing (§6) |
| `ctx.include(name + '.html')` | the view loads and is dead — its script was never selected (§7) |
| `ctx.showHtml('parts/row')` expecting includes or plugins to work | an empty region; the raw `<include>` tag sits in the DOM doing nothing, plus the runtime's own warning (§7) |
| A hand-authored cycle | `validate` **fails** with the loop path (`main.html -> a.html -> a.html`); ignore it and one region on the live page is an HTML comment (§8) |
| A 40-line component split into six files | you now maintain a wiring diagram for a card (§2.4) |

**The live check that catches most of this in ten seconds:** open the page, view source, and search for
`dokie:`. Every include failure — missing target, missing extension, cycle, limit — leaves an
`<!-- dokie: … -->` comment exactly where the content should have been.

---

## 11 · Done when

**Done when:** the component is a small readable project — a shell plus named parts plus four single-responsibility
scripts — whose run order can be read off one block in `main.html`; every `src` resolves; nothing is included
twice that carries a `<plugin>`; the include graph is a shallow tree; and the live page contains no
`<!-- dokie: … -->` comment.

- [ ] The layout was decided **before** the first feature; `main.html` carries the include manifest (§2)
- [ ] No document over ~120 lines, no script over ~150 lines, and nothing split below ~150 total lines (§2)
- [ ] Documents are named `parts/…` / `views/…`, **without** extensions; every `src` carries `.html` or `.js` (§4)
- [ ] Every `src` is the FULL stored name — no relative sibling reference, no `..`, no leading `./` (§4)
- [ ] No `docs[]` entry is named `main`; the main document is `properties.html` (§4)
- [ ] Every script include is written in `main.html`, in one block, in run order; no part declares a script (§3)
- [ ] `scripts[]` and the manifest list the same names, in the same order, and `order` matches (§3)
- [ ] Every enabled script is included exactly once — include mode drops the ones you forgot (§3)
- [ ] No two scripts declare the same top-level `const`/`let`/`function`; `boot` is first (§3)
- [ ] Every `<plugin>` tag lives in `main.html` or in a document included statically **exactly once** (§6)
- [ ] No `<include>` inside a `<plugin>`, and no `<plugin>` inside a `<plugin>` (§6)
- [ ] Repeated fragments are cloned or built by the renderer — never one `ctx.include` per row (§5, §7)
- [ ] Every `ctx.include` target is empty or uses `{mode:'append'}`, and never contains a `<plugin>` child (§6)
- [ ] Author code guards `if ((window.Dokie.__v || 0) < 3)` before the first `ctx.include`, and `try/catch`es it (§7)
- [ ] Every `ctx.include(...)` name is a **literal** string (§7)
- [ ] The include graph is a tree of depth ≤ 2 from `main.html` — depth 1 = included by `main.html`, depth 2 =
      included by one of those; `views/…` pulled at runtime does not count (§8)
- [ ] One CSS prefix `<pfx>-` across every document, and `css.byTheme["*"]` covers the classes of every part (§4)
- [ ] `mrjun.py validate --project ./app` exits 0 **and** its include WARNs were read, not skipped — knowing it
      never expands, so post-expansion defects and the limits are yours (§8)
- [ ] **Live-rendered:** every region drew, page source contains no `dokie:` comment, console clean (§10)

---

**See also:** [24](24-html-component-studio.md) (`studioModel`, the `ctx` runtime, rules/BL, lifecycle, breadcrumb) ·
[24a](24a-theming-and-dark-mode.md) (theme tokens, CSS scoping, the five skins) ·
[24b](24b-html-composition-and-plugin-tags.md) (the `<plugin>`/`<include>` grammar, the binding contract, reuse) ·
[24c](24c-html-data-tables-and-paging.md) (server-paged tables inside a component) ·
[14 §1.1](14-plugin-catalog-all.md) (the classic html plugin) ·
[01](01-content-model-and-pages.md) (content tree, pages, identifiers) ·
[19](19-build-decision-procedure.md) (when a custom component enters the plan) ·
[23](23-distribution-and-known-gaps.md) (what `validate` still cannot check) ·
[`tools/README.md`](tools/README.md) (`node set-studio`, `asset add`, `validate`, `pack`)
