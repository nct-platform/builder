# 23 — Distribution, the live-debug loop & known gaps

**Read this if you (or a partner) will use `doc/builder` to build projects against a Dokie platform you did not
develop.** It answers: what ships in this folder, what you still need, how to debug a project once it's on the
platform, and where the docs are *necessary but not sufficient*.

## 1. What's bundled vs what you still need

**Bundled (portable, no codebase required):**
- The 33 numbered docs (`00`–`27`, plus the `14a`/`24a`/`24b`/`24c`/`24d` deep-dives) + `README.md` +
  `system_prompt.txt` (the knowledge) + `GETTING-STARTED.md` (start here) + `LICENSE` +
  `initialtemplates/empty-validate.txt` (the baseline's expected `validate` output) + `.github/` (the CI gates). Doc **24** = the HTML Component Studio
  (`nct.html.plugin` with JS libs / isolated scripts / `ctx.callRule`+`ctx.callBl` / per-theme CSS). A `studioModel`
  STRING property and any vendored files under `tenant-files/studio/…` **round-trip in `.mrjun` for free** (files
  re-home to the new tenant's `t/<id>/…`; asset paths are stored relative so they need no editing on import).
- `tools/mrjunkit` — the CLI (`mrjun.py`), **stdlib-only** Python 3.9+ (no `pip install`).
- `initialtemplates/empty.mrjun` — the REPORT-typed **`empty` baseline you build on**, packed. Unpack it with
  `mrjun.py unpack` and start there. (If you also have a working project of your own, unpack it beside the
  baseline: a real export is the best pattern library there is, and `jq` answers shape questions instantly.)
- `pdftemplates/` — the **15 seed pdfme templates** the platform itself serves ([15](15-pdf-and-mail.md) §"the 15
  seed templates"). Copy the closest one instead of authoring a printout from a blank canvas.
- `erp/initial_erp.mrjun` + `erp/dynamic.mrjun` — a **fictional ERP demo**, first as a static-CRUD project and
  then wired to dynamic CRUDs. The nodes quoted as "Real node (`erp`, …)" in [14](14-plugin-catalog-all.md) /
  [14a](14a-plugin-config-reference.md) / [02](02-form-controls-reference.md) come from it, so every one of them
  is checkable: unpack a copy and `mrjun.py show node <id>`.
  ⚠️ **The two ERP exports are SHAPE references, not lint-clean baselines.** They predate several `validate`
  checks and both carry hundreds of warnings; `erp/dynamic.mrjun` currently **FAILS** the gate outright — its
  Document-CRUD GROOVY `create`/`update`/`delete` read `param` while declaring `parameters: []`, exactly the
  every-value-written-NULL bug [11](11-business-logic-dynamic-crud.md) warns about. Copy node/JSON *shapes* from
  them; do not copy a pattern `validate` rejects, and do not read that FAIL as a tooling bug. **Both** ERP
  exports fail: `dynamic.mrjun` with 27 errors, `initial_erp.mrjun` with 5.
  ⛔ **The platform's old demo pages have been REMOVED from both** (`insights`, `advisory`, `ontology`,
  `reports`, and the quick links into them). They were never a reference for anything — least of all a
  dashboard, whose standard is [22](22-charts-params-and-filters.md) §2B — and leaving a 42-cell uniform grid
  painted from an index palette inside a "copy the shapes from here" archive taught exactly the wrong lesson.
  Nothing in this library holds them up as a model; if you meet them in a project you inherited, treat them
  as content to delete, not to imitate.
  ⚠️ **No bundled export is error-free, including `initialtemplates/empty.mrjun`** — it ships a handful of warnings
  and 1 error (a left-nav link with only one locale, which disappears on a single-locale tenant). Its exact output is
  recorded in [`initialtemplates/empty-validate.txt`](initialtemplates/empty-validate.txt): **diff against that
  file rather than chasing a zero** — what matters is a line that is new since you started.
ℹ️ **What you received is the whole library.** This repository *is* the distribution — there is no packaged
subset and nothing was held back. If a document refers to something you do not have, it is not missing from
your copy by accident — everything the docs ask you to open is listed above.

**Case notes ship BESIDE the export, never inside it.** This library is deliberately domain-neutral so the next
project can use it unchanged; what you learn about **one** project (its entities, its screen inventory, its
decisions and reasons, its realm/client + schema names, its data-specific gotchas) belongs to that project.
`mrjun.py case init --project <dir>` creates `<dir>-case/`, a **sibling** of the unpacked project, and
`case add --name <slug>` writes one note into it (`case ls` lists them). Because `pack` walks only the project
directory, those notes can never end up inside the `.mrjun` you hand over — and equally, they never leak back
into `doc/builder`. Rule of thumb: true for the *next* project too ⇒ a library edit, written with placeholders;
true only here ⇒ a case note. Flags — [`tools/README.md`](tools/README.md) § *Case notes*.

**NOT in this folder — you must have it:**
1. **A running Dokie platform** — MANDATORY. `doc/builder` produces a `.mrjun` *artifact*; a `.mrjun` does nothing
   until it's imported into the platform (nct-ui + microservices + Postgres). You cannot see, run, demo, or debug a
   project without it. If the recipient has **cloud platform access** and downloads the `empty` project **from that
   same platform**, the version-coupling risk (below) disappears — the baseline and the runtime match by
   construction.
2. **The platform codebase** — NOT needed to *build*: the docs already distilled the facts, and they are written
   for a reader who cannot open the source, so every claim is stated as **observable behaviour** (class and plugin
   NAMES are kept so you can talk to the platform team; source line numbers are not, because they go stale the
   moment the platform is rebuilt). The codebase is needed only to re-verify an ambiguous fact or to maintain the
   docs. On a stable cloud, you substitute **verification-by-behavior** (build → import → observe) for reading
   code — slower for the hardest cases, fine for most.
3. **A per-project PRD/spec** — the human provides *what* to build (the business requirements). The docs are *how*.

## 2. The live-debug loop (what surfaces where)

The build→run cycle: **author (offline) → `validate` (offline) → import → drive the UI → fix.**

- **`mrjun.py validate` (offline)** is your first net — it now hard-ERRORs on a growing set of runtime bugs
  *before* import (see §3 and `tools/README.md`): raw-`findAll` choices rules, a searchable dropdown whose
  `acFindBy<X>Like` pipeline is missing, import-aborting wrong-typed fields / BPMN enum values, empty-form parsis
  anchors, etc. **A clean `validate` is necessary, not sufficient** — it does not deserialize into the platform DTOs.
- **The UI surfaces most content bugs directly** — you do NOT always need logs. Typical examples, all visible in
  the browser: a dropdown showing **"No results found"** (raw-findAll choices rule); a
  toast **"could not determine data type of parameter $1"** (partial-`findAll` untyped param); a **blank page /
  error page** (render failure). Drive every new form, dropdown, table, action, workflow start once and watch.
- **`log/ui.log` is for the *scattered, data-shaped* failures** that DON'T show a clean error: after import you see
  an **empty context** ("No CRUD found with alias X in context Y"), **"No source selected"**, or **missing data**
  (dates/rows "gone"). These are almost always **one** import-abort — a rep-object field that is a JSON string where
  the platform wants an object/array, or a `workflows[].elements[].settings.type` that isn't a `BpmnTaskType`. The
  real cause is a single **Jackson `MismatchedInputException`/`InvalidFormatException` stack** in `log/ui.log` (or
  the cloud's project-log equivalent). Ensure the recipient can see **project logs or at least import errors** —
  without them, this class is guess-and-check.
- **You do NOT inherit the local dev-env bug classes.** Gradle `processResources` markup races, stale-process
  `MarkupNotFoundException`, rebuild-restart cycles are pains of
  running the platform *from source locally*. A recipient on a **stable cloud** never rebuilds the platform, so
  those don't happen — their loop is cleaner than a platform-dev's.

### 2a. When the UI shows a BLANK page and `log/ui.log` says nothing

A blank page writes **no log line** — there is no exception, the platform simply rendered an empty node. Do not
grep harder; read what was stored:

```bash
mrjun.py livediff --project ./work \
  --db "host=<host> port=5432 dbname=<platform-db> user=<user> password=<password>" --tenant <alias>
```

It resolves `nct_ui.s_tenant` (by `s_alias`) → `s_published_branch_id` → `nct_ui.s_branch_content_store.root_content`
and diffs that live tree against your packed one. The signature to look for is a page with **two** top-level
`parsis.plugin` children: one holding your Layout and content, one empty and named `siteMapPageParsis` — the
platform created the second because your clone lost the name, and it renders THAT one. The same command also prints the PACKED rep-object counts in
`initAllObjects` order so you can compare them against the platform by hand — it does not read live rep-objects,
and its exit code covers the content-tree checks only (a rep-object collection that threw takes every later
collection with it).

## 3. Version pinning (keep docs ↔ platform in sync)

The docs encode facts verified against a **specific platform build** — plugin names, DTO shapes, preserved typos
(`process.table.pluin`, `POISTGRESQL`), enum lists, the exact `acFindBy<X>Like` pipeline. A different platform
version drifts silently. Two rules:

- **Build against the platform you'll import into.** Download `empty` from that same cloud tenant (not the bundled
  copy) when versions might differ — the baseline then matches the runtime.
- **Stamp the pin.** Record the platform build these docs were last verified against and re-check on a platform
  upgrade. Fill in and keep current:

  ```
  Docs verified against platform build: <build-id>   (date: <YYYY-MM-DD>)
  ^ ask whoever handed you this library to fill both in, and re-check them after a platform upgrade: an
    unfilled or stale pin means the behaviour described here has not been re-verified against YOUR runtime.
  Re-sync procedure after a platform upgrade: re-run the build → import → drive-the-UI loop (§2) on a small
  project, fix the doc + any `validate` check that no longer matches, and re-run `validate` on every project you
  maintain (it must stay free of false positives) before relying on the update.
  ```

## 4. Known gaps — where `validate` can't help yet (so drive it live)

> ⛔ **Three things no offline gate does. Read these before you trust a green run.**
>
> 1. **Nothing in this toolkit parses or compiles Groovy.** `validate` checks that a rule is *referenced*
>    and *shaped* right; `crud verify --db` executes SQL methods only and skips GROOVY ones entirely. A rule
>    with a syntax error passes every offline gate — and, worse, an unbalanced body makes `validate` skip its
>    *other* checks on that rule. On a build with a hundred rules a syntax error is close to certain. The only
>    test is executing each rule live, and a rule that opens a case must be run **twice** (doc 27).
> 2. **`coverage --emit` self-certifies.** It derives `plan.json` *from the build*, so a plan emitted after
>    the fact always passes. The gate is only meaningful when the plan is written from the **PRD**, before or
>    during the build. Likewise `status: "deferred"` downgrades any missing row to a warning on every `kind` —
>    it is an escape hatch, not a pass.
> 3. **`coverage` never opens the object it counts.** It matches by alias/name, so a row can be satisfied by
>    an empty shell. A CASE-producing trigger needs three rows (trigger + workflow + start rule) and even then
>    nothing asserts the rule really calls `service.workflow.start` — grep the rule body before marking it done.

`validate` catches classes we've hit; it is a **growing** net, not complete. When you hit a bug it didn't catch,
that's a candidate to **add to `validate_cmds.py`** (the pattern: enumerate the artifact, assert the invariant,
ERROR on catastrophic / WARN on recoverable — always re-verify that it raises **no false positive on a known-good
project**).
The implemented net covers choices rules (dropdown/autocomplete/tree-picker),
CRUD method refs, localized-field prereqs, field predicate/validation/default refs, table/tree fetch + action + tree
config, event cascades, schedulers (rule-type + cron + enabled), sources/queries/roleGroups, PDF/mail templates,
db.dump column/sequence integrity, form-page `formModeIdentifier`, tabs, quick-links, chart param/columnName/crossFilter,
and workflow serviceTask/userTask/gateway/context refs. **Each one has a passing negative test** (it fires on a
violation) and was confirmed silent on the `empty` baseline and on the maintainers' reference builds — *not* on
the bundled ERP demos, which predate parts of the net (§1). `python3 tools/mrjun.py validate --help` and the check
list in `tools/README.md` are the authority on what is in the net today; treat any number quoted in prose as stale.
Some candidate classes are deliberately left out as *not offline-checkable without false positives* — a check that
flags a known-good project is worse than no check, so those classes are caught by the docs + a live run.

> **2026-08 addition — `_check_html_plugin_refs`.** An `html.plugin` renders a child only if its own html names
> it via `<plugin id=…>`; a cloned page whose child identifiers were regenerated keeps every node yet draws
> none of them. Caught now as an ERROR on the unambiguous signature (dangling ref + unreferenced child of the
> same plugin type = a regenerated id). This is not a theoretical class: cloning a laid-out page and regenerating
> its child identifiers can blank out every page in a build while `validate`, `coverage` and `crud verify` all
> report green — every artifact exists, none of them is wired to its neighbour. The general lesson stands: **the offline gates check that artifacts EXIST and are well-formed; only a live open
> checks that they are WIRED TO EACH OTHER.**

> **2026-09 addition — the two classes that only an IMPORT and a first click used to find.** Both shipped a
> green `validate`, and both are now in the net.
>
> 1. **`_check_platform_required_fields` + `_check_query_reference_integrity` — an object the platform
>    REJECTS at import.** The platform's DTOs declare fields mandatory that this format is happy to leave
>    blank. The one that bites: a scaffolded CRUD mints a paired query record per method, `create`/`update`/
>    `delete` later become GROOVY orchestrators, nothing ever fills those three records, and they ship as
>    `"query": ""`. Objects import in a fixed order (queries first), so on a platform that stops at the first
>    rejection the project arrives with a database and blank screens while the card says only "imported with
>    warnings". ERROR on the blank mandatory field and on a method pointing at a query that is not in the
>    export; WARN on the leftover record itself.
>
> 2. **`_check_single_slot_map_calls` — a Map argument meeting a single-slot SQL method the map does not
>    name.** The executor unpacks a one-Map argument by parameter name, but with EXACTLY ONE declared
>    parameter only if the map mentions it; otherwise it binds positionally and the whole serialized map goes
>    into that slot. This is the default shape of `count` on a table with exactly one filter — `count` is
>    `findAll` minus the paging keys, and auto-find calls both with the same map — so an empty filter bar
>    sends a map that never names the filter. On a scalar column: `invalid input syntax for type boolean:
>    "{"rowsInPage":20,…}"`. On a text column: no error at all, the comparison matches nothing, and the
>    screen shows an empty list. ERROR on the scalar shape, WARN on the silent text one.
>
> 3. **`_check_query_placeholder_shape` — a chart query that only breaks once a filter is EMPTY.** A chart
>    renders with its filters empty by default, and an unsupplied `{name:…}` is not bound to null: the engine
>    neutralises it to `1=1` and blanks every token back to the nearest `WHERE`/`AND`/`OR`, leaving whatever was
>    written after the placeholder dangling. A hand-written "empty means all" guard —
>    `AND ({name:'since'} = '' OR d.dt >= CAST({name:'since'} AS date))` — therefore ships as
>    `AND 1=1 = '' OR 1=1 AS date ) )` on the first render and every chart on the page shows an error toast. The
>    authored SQL is valid SQL, so no other gate can see it; the check applies the rewrite and ERRORs when the
>    result stops being balanced. [22](22-charts-params-and-filters.md) had documented the trap in full — the
>    build simply did the forbidden thing, which is the argument for a gate rather than a paragraph.
>
> 4. **`_check_chart_js_contract` — a chart script that never constructs.** The script is evaluated with `this`
>    bound to the plugin: the canvas is reached with `this.$find('canvas')[0]`, and the instance must be assigned
>    to `this.chart`, which the redraw path calls `.destroy()` on. A script that reaches for anything else — a
>    plausible-looking `element.querySelector('canvas')`, say — throws BEFORE `new Chart` runs, so the box renders
>    empty. This is the nastiest of the four to place: every offline gate is green, the query editor shows rows,
>    the replacement queries return data, and the dashboard is blank. Both shapes are ERRORs; every reference
>    export already satisfies them.
>
> All four were found by importing a build and opening one screen — which is the point of the general lesson
> above.
>
> ⛔ **And the lesson under the lesson.** Every one of these four was already DOCUMENTED, in this library, in
> full, before the build that broke it — the bare-operand rule and the `this.$find`/`this.chart` contract are
> both written out in [22](22-charts-params-and-filters.md) with worked examples. Prose did not stop it. What
> stops it is a gate that fails the build, which is why the rule at the top of this section — *when you hit a bug
> the net did not catch, add it to the net* — is not a nicety. A class that can only be caught by a human
> remembering a paragraph will be shipped again. The lesson they add to it: **a class that only a live run can find today is a candidate for the net
> tomorrow.** When the live run is not yours to make, the gate has to grow to cover what it would have seen.

Currently NOT caught offline (must be verified by driving the UI):
- **Semantic correctness of rule *logic*** — a rule that runs but computes the wrong value (validate checks shape,
  not business logic).
- **Chart data-binding & colors** — an empty chart (query returns nothing / param not wired) or a non-semantic
  color ramp (risk shown as two blues instead of red/amber/green) render "fine" to
  validate; eyeball them.
- **HTML Component Studio (doc 24)** — `validate` checks the `studioModel` *shape* (parses; each script's `libNames`
  are declared; vendored asset paths are relative), but it does NOT confirm a `ctx.callRule('Name')` /
  `ctx.callBl('alias','method')` actually resolves to an existing rule / BL method, nor that the author JS behaves.
  Drive it live: open the component, watch the browser console + `ui.log`. (Author JS runs **first-party** — no sandbox.)
- **`<include>` is checked as a graph, never as an expansion** — `validate` resolves every `<include src>` and
  every literal `ctx.include('…')` and ERRORs on a cycle, WARNs on a dangling or extension-less target and on an
  enabled script no reachable document includes. What it still cannot see, because nothing offline expands: an
  `<include>` written inside a `<plugin>` (everything it brings in is dropped), a `<plugin id>` that only becomes
  a duplicate after expansion, the depth-20 / 500-tag / 2 000 000-character limits, a computed
  `ctx.include(name + '.html')`, and any studio component that lives in a `virtualPlugins[]` definition rather
  than a page's own content. Each of those renders as an `<!-- dokie: … -->` comment or a silently missing
  region. Verify live: view source for `dokie:`.
- **Theme-safety of authored CSS (doc 24a)** — a hardcoded light palette in `css.byTheme["*"]` (or an inline
  `<style>` in the `html` property) imports clean, validates clean, and is unusable on the four dark skins. It is
  the easiest mistake to make at scale: one hardcoded card style, copy-pasted onto every screen of the project,
  and the re-do is every screen. There IS a
  colour-literal warning now, but it fires **only** on an `nct.html.plugin`'s `studioModel.css.byTheme`, and only
  on its all-themes (`"*"`) block. Grep before packing — [24a §9.2](24a-theming-and-dark-mode.md) gives the exact
  commands — and **open the page in all five skins**, which is the only real proof. Same for the ⛔ `h-100`
  (=`100vh`) trap.
- **A CHART's per-theme CSS is not colour-linted at all** — the chart model carries its own per-theme CSS map
  (the Css tab; the map lives beside `js`/`html` in the chart's `Javascript` property, keyed by skin name plus the
  all-themes `"*"` entry — [22](22-charts-params-and-filters.md), [14a](14a-plugin-config-reference.md)). It is a
  *different* key from the HTML studio's `css.byTheme`, and the theme-safety check reads only the studio one, so
  **the theme checklist is vacuously green for every chart in the project**: a chart whose `"*"` block paints
  `#fff` cards and `#333` text passes `validate` with zero warnings and is unreadable on the four dark skins.
  Treat charts as manually reviewed: grep the chart blobs yourself and open every dashboard in all five skins.
- **A hand-written studio ASSET path silently 403s** — `validate` only WARNs when a `studioModel` asset `path` is
  *absolute* (an absolute `t/<old-tenant-id>/…` keeps pointing at the tenant it was authored on, so it dies on
  import); it never confirms the file exists in the bundle's `tenant-files/`, and it cannot know what the platform
  will name it. Three things bite. (a) The uploader **sanitizes** the library and file-name segments to
  `[A-Za-z0-9._-]` (anything else becomes `_`), so a library authored as `My Lib` is stored under `My_Lib` — a
  hand-typed `studio/My Lib/x.js` never resolves. (b) A relative path is resolved by prepending the CURRENT
  tenant's root, so it must begin with `studio/` — `lib/x.js` lands outside the served area. (c) The asset
  endpoint serves **only** paths under the tenant's own `studio/` area that end in a front-end extension
  (js/mjs/css/json/map/svg/html, fonts, images); everything else is refused with **403**, not 404 — so a path
  pointing at, say, `studio/../dump.sql`, or at that bare `lib/x.js`, fails with a status that looks like a
  permission problem and sends you hunting in the wrong place. Prefer letting the Studio's own upload write the
  path; if you must hand-author one, mirror the sanitized shape exactly, keep it under `studio/…`, and confirm
  with `mrjun.py asset ls` that the file is really in the bundle. Verify live: a missing asset shows up as a
  console 403 and a component that renders its empty skeleton ([24 §10](24-html-component-studio.md)).
- **⛔ Chart text is a localization dead zone** — a chart's script/markup slots are plain strings with no
  per-locale map, so wording typed there shows one language to every viewer. Nothing fills it and nothing warns:
  `locale fill` has no map to fill and `validate` has no map to check. See
  [20 §iv](20-localization.md) for the rule and the three workarounds.
- **Breadcrumb contributions land nowhere on a hand-built layout** — `ctx.breadcrumb` publishes through
  `EventUtils.trigger`, which only reaches components already on the page. A page whose layout omits
  `site.breadcrumb.plugin` returns `{"ok":true}` and draws nothing. Offline-invisible; confirm live ([24 §7.5](24-html-component-studio.md)).
- **The HTML plugin's markup-parse cache grows without bound for studio-active nodes** (platform-side, not a
  bundle problem). The base HTML plugin memoizes its parse result in a process-wide map keyed by the html STRING,
  and a studio-active `nct.html.plugin` renders its html wrapped in a `#dokie-plug-<markupId>` element whose
  markupId is a **per-session sequence** — so the key is different for every page instance and the entry is never
  evicted. Harmless per request, a slow leak on a long-lived JVM with many sessions. Nothing a bundle author can
  do; listed so it is not re-diagnosed as a project bug.
- **Workflow runtime behavior** — timers/boundary events, gateway predicate outcomes, four-eyes SoD — only a live
  process instance proves them.
- **An AUTOMATIC process start is offline-invisible in all three ways that matter** — a case opened by
  `service.workflow.start(...)` from a rule ([27](27-event-driven-process-start.md)) has no form and no node, so
  `validate` can only check that the rule type, the cron and the workflow identifier are right. It cannot see
  (a) whether the sweep is **idempotent** — a candidate filter, a claim method and a marker column are ordinary
  data, and a missing guard opens a fresh case for the same row on **every tick, forever**; (b) whether the
  `groupIdentifier` the rule passes is the same string the worklist node uses — a mismatch or a blank files the
  case under a dangling/no group, and a group-scoped `process.table.pluin` is an INNER join, so it disappears
  for everyone including admins; (c) whether any key **inside** the context data document is spelled right —
  nothing on the start path inspects it (the workflow identifier is checked, the document is serialized as
  given), so a mis-typed context identifier or crud alias is **accepted in silence** and surfaces much later as
  a blank field on the first user task, or as a rule throwing *"No context data available for context"*. The
  only test is running the action rule **twice by hand** and counting cases
  ([27 §8.3](27-event-driven-process-start.md)).
- **Localized *data* coverage** — validate warns on a mis-wired localized *field*, but whether every row's
  `localize` jsonb is actually populated per locale is a data question (run the bulk Localize).
- **Cross-service / RSocket / dynamic-integration** wiring, PDF/mail rendering fidelity, access-control edge cases.

> ⛔ **For studio and chart work, restate the rule as strongly as it deserves: a clean `validate` is not evidence
> that the page renders.** Everything the offline gates can see about an HTML component or a chart is that a JSON
> blob parses and that its internal references are consistent. They never execute the author's JS, never fetch an
> asset, never run a replacement query, never apply a stylesheet, and never open a skin. The three failure modes
> above — a blank component, an unreadable dark-skin dashboard, a 403 asset — all ship with `validate` at 0
> errors. **The acceptance step for every studio/chart screen is a human (or a screenshot) opening it, in each
> skin, with the browser console visible.** Budget for that; do not let a green gate stand in for it.

**Bottom line for a recipient:** with platform access + `empty` from that platform + this folder + `mrjun.py`, an
(AI) builder can produce real, working projects — the loop is complete. Success is bounded by (a) doc correctness
for that platform version, (b) visibility of import/UI errors, and (c) how much of the runtime-bug surface has been
pushed into `validate`. Grow `validate`, keep the version pin current, and ensure log/error visibility — and the
gap between "authors a `.mrjun`" and "ships a working project" stays small.
