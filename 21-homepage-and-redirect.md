# 21 — Homepage & the project "front door" (`Redirect`)

> 📐 **Field evidence — what four front doors actually are:** [02-navigation-and-front-door.md](references/02-navigation-and-front-door.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / when to use

When a user opens the bare project URL (`/<realm>/<alias>` with no page path), the platform resolves the
**branch root** — the single `siteMapPage` whose `parentId` is null (named **`Home`**, stored as
`branch.rootContent`) — and renders it. **What that root shows is decided by the root page's `Redirect`
property.** Read this doc whenever you finish a project: **every project must wire its front door**, or the root
lands on an empty Home and the demo looks broken.

## How the root resolves (verified)

1. Bare URL → `PluginPage` computes zero content-alias segments → `setContent(contentService.findRootPageContent(branchId))` (`PluginPage`), which returns the `parentId==null` content. That is the `Home` node — a **structural root**, not a flag.
2. The `SiteMapPage` constructor reads the root's `Redirect` STRING property (`SiteMapPage.java`):
   - **`Redirect` non-blank** → `setResponsePage(redirect)` (the CMS overload, `PluginPage.java`): the value is treated as a **slash-separated content-alias path**, alias-matched down the child tree (`ContentDbServiceImpl.java`), and the platform issues an HTTP redirect. The browser URL becomes `/<realm>/<alias>/<path>`.
   - **`Redirect` blank** (default) → the root renders **Home's own parsis/layout content**. If Home's parsis is just the empty layout shell, the root is blank.

## The `Redirect` value format (get this exactly right)

`Redirect` is a **content-alias PATH relative to root**, e.g. `<landing-alias>` (top-level) or `parent-alias/child-alias` (nested). It is:

- **the target page's `alias`** (`ContentDomain.getAlias()`), **case-sensitive** — NOT the page `name`, NOT its `identifier`/uuid, NOT a URL, NOT a filesystem path;
- resolved by walking child `siteMapPage`s from the root, one alias segment at a time (matching is `Objects.equals` on `alias`);
- a leading `/` is tolerated but unnecessary; do NOT include the `realm/alias` prefix (added/stripped automatically).

A value that doesn't resolve is a **dead front door** (404 on the root).

## The rule

> ⛔ **Never ship an empty Home.** A finished project MUST either (a) set `Home.Redirect` to its primary landing
> page's alias (usually a dashboard/cockpit — great for demos, since opening the project drops the viewer
> straight into the KPIs), **or** (b) author real landing content into Home's parsis. Which of the two is not a
> taste call — walk the ladder in "Choosing the front door — chart dashboard or main worklist" (below): a case
> with chartable data takes **(b)** with the charts in Home's own parsis; a pure queue/workflow tool takes
> **(a)**. Option (a) is the one-property, platform-intended fix, but it is the fallback rung, not the default.
>
> ⚠️ **But "redirect set" ≠ "Home shows the dashboard".** A redirect to a chart page whose queries return nothing
> (or whose `chart.js.plugin` binding is wrong) lands the user on a **blank shell** — the exact "opened the project
> and saw no charts" report. Two consequences: **(1)** if Home IS the dashboard, prefer **option (b) — build the
> `chart.js.plugin` nodes INTO Home's own parsis** so the bare URL renders the cockpit with no redirect hop that can
> resolve to nothing. **(2)** Either way, this is NOT done until you **live-import and SEE the charts render** with
> real data ([26](26-orchestration-and-testing.md) §5; chart data-binding is one of the classes `validate` cannot
> catch — [23](23-distribution-and-known-gaps.md) §4, [22](22-charts-params-and-filters.md)). A redirect that was
> never opened in a browser is unverified.

> ⛔ **A redirect does NOT fix "my quick links don't show" — do not reach for it.** The platform
> **management console** (`Rules/Contexts/…/Settings`) is **not** injected at runtime: it is the shared
> `Nct left nav` node's own `Pages` group — ordinary `modelGroups` data — and it shows on every page because
> every page delegates to that one node. **Your** business pages go in that same **SHARED** common node
> (`branch.virtualPlugins[] name="Nct left nav"` → `content` → `properties.modelGroups`, `uniqueIdentifier`
> e.g. `23ab2aca-…`), NOT in any per-page `modelGroups`. EVERY page — including a content-blank Home and any
> redirect target — renders that one shared node via its own `site.kicker` node's `linkContentIdentifier`
> (`PluginPanel.getContent` → `findOneByUniqueIdentifier`), so the left nav looks **identical everywhere** and
> the per-page `modelGroups` are **DEAD DATA** ([17-left-nav-quick-links.md](17-left-nav-quick-links.md)).
> A redirect therefore changes only which **content** renders, never nav visibility: a blank Home shows the
> SAME populated nav as the dashboard, and pointing the redirect at a page whose *per-page* `modelGroups` you
> populated does nothing. This is easy to confirm on any project: a Home with `Redirect=""` still renders the
> full shared nav, and a Home with `Redirect="dashboard"` and its dashboard target both delegate to the very
> same shared node. **To surface your business pages you MUST populate the shared node** — `quicklink
> add` (doc 17), which targets it. The redirect does not do it. ⛔ And **append** to that node's `pagesModel`:
> the console links live in the very blob you are editing, so rewriting it wholesale deletes
> `Settings`/`Database`/`Rules`/… from the whole project ([17](17-left-nav-quick-links.md) Gotcha 8).

## Choosing the front door — chart dashboard or main worklist

> ⛔ Two things the front door owes you beyond existing. **(1) It is COMPOSED, not emitted** — a title, a KPI
> strip, named sections, unequal columns, four distinct chart shapes; the whole standard plus working code is
> [22](22-charts-params-and-filters.md) §2B, and §2B.1 names the grid-dump failure it exists to prevent.
> **(2) Its quick link lives in a BUSINESS group, not in `Pages`** — `Pages` is the authoring console, so the
> baseline's `Home` link must be REMOVED from it and re-added, first, to the first business group, under the
> name the business uses for that screen ([17](17-left-nav-quick-links.md)).

You pick this yourself, from the case's own data model — there is nobody to ask. Walk the ladder top-down and
stop at the first rung that fires.

| # | Test on the case | Front door | Home's `Redirect` | Where the content lives |
|---|---|---|---|---|
| **1** | It has **any aggregatable data**: an entity carrying a low-cardinality axis (status / risk / type / owner) **or** a numeric column worth summing **or** a dated column worth trending | a **chart dashboard** — the **DEFAULT and preferred** answer | `""` (blank) | the `chart.js.plugin` nodes sit in **Home's own** parsis |
| **2** | Nothing on it is worth charting: a **pure single-queue workflow/approval tool**, or a **reference-data admin app** (lookup tables edited by hand) | the **main process/worklist table page** | `<worklist-alias>` | the table stays on **its own** page |
| **3** | — | **never an empty Home** — see [The rule](#the-rule) | — | — |

**Rung 1 fires far more often than it first looks, and you are expected to take it.** One status column on one
`<Entity>` is already a donut; one dated column is already a trend; one numeric column is already a KPI tile. So
3–6 charts over the case's own axes, plus the filter set designed with them, is the normal front door. "There is
not much data" is **not** a reason to fall through to rung 2 — seeding a demo-grade dataset is part of the build,
not a favour ([22](22-charts-params-and-filters.md) "§2.6 The data a chart needs (demo-grade datasets)",
[10](10-database-management.md) "Seeding demo-grade data into the dump"); design the filters at the same time
([22](22-charts-params-and-filters.md) "§4.6 Designing the filter SET for a dashboard").

**Rung 2 is a fallback, not a shortcut.** Take it only when rung 1 genuinely does not fire, and then the front
door is the page carrying the queue's `process.table.pluin` / `crud.table.plugin` — the worklist page that
[07](07-workflows-and-tasks.md) "Step 5 — the worklist page (NOT optional)" makes you build anyway. Do not
fabricate a chart page you have no columns for, and do not leave the queue unreachable because you built charts.

> ⛔ **The mechanism follows from the choice — the two are not interchangeable.**
> - **Chart dashboard → author the `chart.js.plugin` nodes INTO Home's own parsis and leave `Redirect` blank**
>   (option **(b)** of [The rule](#the-rule); `page set-redirect --page root --to ""`). No redirect hop means no
>   hop that can resolve to nothing.
>   `validate` accepts a redirect-less Home **only** when Home's own layout hosts a landing plugin, and
>   `chart.js.plugin` is one of them (`_check_homepage_and_nav`, `validate_cmds.py`) — a bare Home with neither
>   is the WARN you must never ship.
> - **Worklist → `page set-redirect --page root --to <worklist-alias>` and leave Home's parsis alone** (option
>   **(a)**). Do **not** copy the table onto Home: the worklist already exists as its own page (nav target,
>   drill-down target, [07](07-workflows-and-tasks.md) Step 5), and a second copy is a second node to keep in sync.
>
> **You cannot have both.** `SiteMapPage`'s constructor builds Home's parsis and *then*, if `Redirect` is
> non-blank, calls `setResponsePage(redirect)` (`SiteMapPage.java`) — the browser gets the target page, so a chart
> grid authored on a redirecting Home is dead weight that nobody ever sees. And the reverse is barred too: a
> `crud.table`/`crud.tree`/`process.table` may not sit on a chart Home ("Home-as-dashboard: layout & what NOT to
> put on it", below; `validate` WARNs via `_check_one_table_plugin_per_page`).

> ⚠️ **Whichever page is the front door must ALSO be a quick link** — otherwise, one drill-down later, the user
> has no way back except editing the URL. `quicklink add --page <front-door page> --label …` (doc
> [17](17-left-nav-quick-links.md)), first in the nav; for a chart home the target page **is** the root, so
> `--page Home`. That link resolves through `ContentLink` → `calculatePageUrl`, which prefixes the target's own
> alias — the stock root `Home` has **no** `alias`, so the link comes out as the bare project URL and lands on
> Home. ⛔ Do not give the root an alias: alias segments are matched only among a page's **children**
> (`ContentDbServiceImpl.getContentDomain`), so `/<realm>/<alias>/<root-alias>` would `do404()` (`PluginPage`).
> **Not machine-checkable:** `_check_homepage_and_nav` counts a redirect target as reachable and never inspects
> the root page itself, so `validate` stays silent for a front door with no quick link. It is a review rule —
> check it by eye at closeout ([19](19-build-decision-procedure.md)).

Either way the front door is **not done when the property is set**: see the "⚠️ But 'redirect set' ≠ 'Home shows
the dashboard'" callout in [The rule](#the-rule) above — you live-import and SEE it render with data.

## Home-as-dashboard: layout & what NOT to put on it

When Home IS the dashboard (option b), build it as **charts only** — KPIs + charts, **no** `crud.table`/
`crud.tree`/`process.table` (drill-down tables go on their own pages, linked from the nav) and **no**
`dynaform.filter.form` (its `onFilterSubmit` drives tables, not charts — a filter bar on a table-less dashboard
filters nothing; `chart.js.plugin` only re-queries via the query-parameter event, see
[14-plugin-catalog-all.md §2.4](14-plugin-catalog-all.md)).

> ✅ **The chart filter bar is a DIFFERENT plugin, and it DOES belong here.** What the paragraph above bars is
> `dynaform.filter.form.plugin`: its submit fires `onFilterSubmit` (`FilterSubmitButtonPlugin.java`) and the only
> listeners are `CrudTablePlugin` / `CrudTreePlugin` / `ProcessTablePlugin` — no chart ever listens. The **chart**
> filter bar is **`global.replacement.plugin`** (`GlobalReplacementPlugin.java`, a thin shell over `ParamsPanel`):
> it fires `parametersOfQueryHasBeenChanged`, which is exactly the event `ChartJsPlugin` registers for, so it
> re-runs the charts' parameterized queries. Put **one** on the dashboard, as a sibling in the same content
> `nct.parsis.plugin` (id `parsis`) **ABOVE the grid-row nodes** — order: header html → filter bar → grid rows:
> `node add --parent <page/parsis> --plugin global.replacement.plugin`. It stores **no** config (`--model` /
> `--settings` are rejected) and builds its controls from the charts' SQL params, so a bar on a page whose charts
> declare no `{name:'…'}` param is inert — `validate` WARNs. See [22](22-charts-params-and-filters.md) §4 and
> "§4.6 Designing the filter SET for a dashboard".

Layout: the content `nct.parsis.plugin` (id `parsis`) holds a header `nct.html.plugin`, then **grid-row**
`nct.html.plugin` nodes. Each grid-row's inline HTML is a Bootstrap row of `<div class="col-md-N"><plugin
id="<UUID>" name="nct.parsis.plugin"></plugin></div>` cells, and its children are `nct.parsis.plugin` cells
whose `identifier` == the matching `<plugin id>`; each cell holds one `chart.js.plugin`. KPI tiles use the
theme-safe Plotly `indicator` template; charts use Chart.js (transparent → theme-aware). A workable size is
roughly 4–8 KPI tiles above 4–6 charts, table-less; a second themed dashboard on its own page follows the same
shape.

## Tooling

```
mrjun.py page set-redirect --page root --to <landing-alias>  # wire the front door (validates the alias resolves)
mrjun.py page set-redirect --page root --to ""              # clear it (root renders Home's own content)
```

`page set-redirect` resolves the target against the actual content tree and **errors if the alias path doesn't
resolve**, so a dead front door can't ship. `validate` also enforces this: it **WARNs** when the root has no
`Redirect` (and no landing content) and **ERRORs** on a `Redirect` that doesn't resolve. Related closeout step:
[19-build-decision-procedure.md](19-build-decision-procedure.md) "wire the front door".
