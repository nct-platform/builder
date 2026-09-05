# 22 — Charts, Params & Filtering-through-Params

## What it is / When to use

The deep recipe for **`chart.js.plugin`** — the platform's universal "HTML + JS + data" widget (every chart,
KPI tile, gauge, and hand-coded dashboard block is one) — plus the two things that make a chart a *live*
report: **query parameters** (a chart's SQL can take inputs) and **filtering-through-params** (a page-wide
**filter bar** + **click-to-cross-filter** that re-run every chart's query when the user picks a value).

It is the most frequent business plugin in a real project — a dashboard-heavy build easily carries dozens.
Doc 14 §2.2 is a catalog stub; **this file is the full recipe** for authoring cool, data-bound, filterable
charts directly in `.mrjun`.

| Concern | What it is | Where |
|---|---|---|
| `chart.js.plugin` node | one content node; config JSON (`ChartJsModel`) in property **`Javascript`** | §1 |
| `$$('name', default, 'Type')` | the data-binding placeholder — **in `js` only** (`html` is rendered as-is, never tokenized); one per `ChartJsReplacement` | §2 |
| `replaceStrategy` `QUERY`/`LABEL` | pull from a SQL query column, or inject a literal | §2.2 |
| **which charts to build** | the specified list is a FLOOR — derive candidates from the schema, challenge the ones you were given, propose | §2A |
| Query parameter | inline `{name:'P', type:'…', dropDownPopulation:{…}}` **in the SQL text** | §3 |
| `global.replacement.plugin` | the page filter bar (no stored config — built from the charts' query params) | §4 |
| click-to-cross-filter | clicking a bar/point sets a param and re-runs matching charts (badge is automatic) | §5 |
| drill-down (`futureReplacements`) | click a mark → deeper query via `this.showFutureQuery(label)` | §5.1 |
| drill to another **PAGE** | there is no navigate API — plain `window.location` from the chart's `onClick`; the clicked value rides the session param slot | §5.3 |
| theme-safe rendering | never a white box on a dark theme (Plotly `paper_bgcolor`, `Chart.defaults`, **per-theme `cssByTheme`**) | §6 |
| chart **colour** | which palette family the axis's MEANING demands: traffic-light · qualitative · sequential · diverging | §6.1 |
| Recipes | copy-paste JSON: single chart, filtered dashboard, cross-filter, KPI tile, **a whole dashboard page** | §7 |
| **the editor** | the **5-tab** authoring UI (HTML/JS/**Css**/Replacements/Caching) + gallery — and what each tab writes to the model | §8 |
| **Chart.js config settings** | the `new Chart(ctx,{type,data,options})` object: types, datasets, scales, plugins | §9 |
| ⛔ chart text & localization | a chart's `js`/`html` is ONE non-localized string — no per-locale map exists for a chart | Gotcha 16 |

**Everything about the underlying data substrate is already in [12](12-queries-sources-schedulers-and-rest.md)
— link, don't restate:** saved queries ([12](12-queries-sources-schedulers-and-rest.md) §1), SQL placeholder
syntax ([12](12-queries-sources-schedulers-and-rest.md) §1.4), the `FieldType` set + report-param types
([12](12-queries-sources-schedulers-and-rest.md) §9), `dropDownPopulation` & cascading dropdowns
([12](12-queries-sources-schedulers-and-rest.md) §10), aggregations ([12](12-queries-sources-schedulers-and-rest.md)
§11), and the `findControls → replaceParams` engine ([12](12-queries-sources-schedulers-and-rest.md) §15). This
doc covers only the **chart-specific glue** on top of that substrate.

---

## 1. The chart content node (`chart.js.plugin`)

A chart is **one content-tree node** whose config lives in the property named **`Javascript`** (NOT `model`,
NOT `settings`). Its `stringValue` is a GSON-serialized `ChartJsModel`. The node sits inside a page's
`nct.parsis.plugin` slot like any business plugin (see [01](01-content-model-and-pages.md)).

### 1.1 Export shape

```jsonc
// content-tree node
{
  "pluginName": "chart.js.plugin",
  "name": "Monthly Team Velocity",          // author-facing label
  "id": "<surrogate uuid>",                  // node id (mrjun tool sets null → assigned at import)
  "identifier": "<uuid>",                    // stable relation id
  "uniqueIdentifier": "<uuid>",              // target for refreshTargets / drill
  "order": 0,
  "children": [],
  "roleAccess": { /* see 01 — charts default publicReadAccess:true */ },
  "properties": {
    // className / styleName / tagProperties are the empty boilerplate every plugin carries
    "Javascript": {
      "key": "Javascript",
      "propertyType": "STRING",
      "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
      "arguments": {}, "localizedStringValue": {}, "required": false, "hidden": false,
      "stringValue": "<<< a JSON-ENCODED ChartJsModel string — see 1.2 >>>"
    }
  }
}
```

`ChartJsModel` (the decoded `Javascript.stringValue`):

```jsonc
{
  "id": "<uuid>",
  "html": "<canvas width=\"100\" height=\"100\"></canvas>",  // mount markup (canvas for Chart.js, div for Plotly)
  "js":   "…render script containing $$('name', default, 'Type') markers…",
  "css":  "",                        // legacy single CSS block — still honoured, read as cssByTheme["*"]
  "cssByTheme": {                    // per-theme CSS. Keys: "*" + exact theme names.
    "*":         ".<pfx>-tile{background:var(--current-line,var(--bs-light))}",
    "Dark Blue": ".<pfx>-tile{border-color:#4c6c94}"
  },                                 // only the "*" block + the ACTIVE theme's block are emitted, each auto-scoped
                                     // to this chart instance. Omit both keys when the chart needs no CSS.
  "schedule": { "job": {} },         // caching (§8 / Gotcha 12) — PRESENT as an empty object in real exports; a hand-authored blob may omit it (back-filled on import). Empty = no caching.
  "replacements": [ /* one ChartJsReplacement per distinct $$() name — see 1.4 */ ]
}
```

> ⛔ **The embedded `replacements[].query` must be a MINIMAL QueryDto — ONLY these ~12 fields: `id, identifier,
> realmName, clientName, name, query, sourceIdentifier, offset, itemsPerPage, parameters, attributes,
> aggregations` (with `aggregations.aggregations = []`, not `null`). Do NOT embed the whole query REP-OBJECT**
> (its rep metadata: `creationTime`/`modificationTime` Instant strings, `errors`, `message`, `hidden`, `schedule`,
> `lastScheduledTime`, `statementTimeoutSeconds`, `wrapInPaging`). The plugin reads the model through the CMS
> property store's JSON decoder, which **SWALLOWS any decode failure and hands back an EMPTY model** (the
> rep-object's `Instant` timestamps are what usually trips it) — so a query carrying those extra fields makes the chart
> render as a blank `nct.html.plugin` **"Modify html"** cell with an empty HTML/JS editor (it looks like the chart
> "lost its config", but the config is present in `properties.Javascript` — it just won't deserialize). A common
> way to hit this: a generator that does `"query": json.dumps(<the query rep-object>)` instead of a trimmed subset.
> `validate` now **ERRORs** on a chart replacement query carrying any field outside the safe set.

### 1.2 Worked example — a "Monthly Team Velocity" line chart

Pull the equivalent out of any project you have with:
`jq '[.. | objects | select(.pluginName=="chart.js.plugin")][0] | .properties.Javascript.stringValue | fromjson' branches.json`

```jsonc
{
  "id": "56b6bab4-8b66-4e53-9ac2-08c9378b7015",
  "html": "<canvas width=\"100\" height=\"100\"></canvas>",
  "js": "var deflt = [];\nconst labels = $$('Labels', deflt, 'String[]');\nconst timeline = $$('valuesf', [1], 'Integer[]');\nconst data = { labels: labels, datasets: [{ label: 'Monthly Team Velocity', data: timeline, borderColor: Utils.CHART_COLORS.red, backgroundColor: Utils.transparentize(Utils.CHART_COLORS.red, 0.5), borderWidth: 1 }] };\nconst config = { type: 'line', data: data, options: { responsive: true, scales: { y: { title: { display: true, text: 'Effort (Story Points)' }, ticks: { stepSize: 1, beginAtZero: true } } }, plugins: { legend: { display: false }, title: { display: true, text: 'Monthly Team Velocity', font: { size: 20 } } } } };\nconst ctx = this.$find('canvas')[0].getContext('2d');\nthis.chart = new Chart(ctx, config);",
  "schedule": { "job": {} },
  "replacements": [
    {
      "name": "Labels",
      "group": "$$('Labels', deflt, 'String[]')",
      "type": "String[]",
      "replaceStrategy": "QUERY",
      "queryIdentifier": "64813fd2-0855-435e-a276-054dac4b1110",
      "query": {
        "name": "A Monthly Team Velocity",
        "query": "SELECT ... TO_CHAR(changed_date, 'Mon') AS monthSN, CAST(SUM(...) AS integer) AS monthly_completed_effort FROM ... WHERE r.team_project = {name: 'Project name', type: 'dropdown-string', dropDownPopulation: {query: 'Projects Query', value: 'name', name: 'name'}} AND changed_date >= NOW() - INTERVAL '6 months' GROUP BY year, month, monthSN ORDER BY year ASC, month ASC",
        "sourceIdentifier": "da6ff14b-62b5-45aa-ad58-4e2a60af3614",
        "offset": 0, "itemsPerPage": 1000,
        "parameters": { "Project name": { "value": "<the current preview value>" } },
        "aggregations": { "aggregations": [], "groupByList": [], "orderByList": [] },
        "id": "a8307041-54ed-43fd-beff-cf592754f6dc",
        "realmName": "<realm>", "clientName": "<client>",
        "identifier": "64813fd2-0855-435e-a276-054dac4b1110"
      },
      "futureReplacements": [], "defaultValue": "deflt", "columnName": "monthsn",
      "order": 0, "maxItemsCount": 1000
    },
    {
      "name": "valuesf",
      "group": "$$('valuesf', [1], 'Integer[]')",
      "type": "Integer[]",
      "replaceStrategy": "QUERY",
      "queryIdentifier": "64813fd2-0855-435e-a276-054dac4b1110",
      "query": { /* identical QueryDto copy, same identifier */ },
      "futureReplacements": [], "defaultValue": "[1]", "columnName": "monthly_completed_effort",
      "order": 1, "maxItemsCount": 1000
    }
  ]
}
```

Read it as: the line chart's **x-axis labels** come from column `monthsn` and its **series data** from column
`monthly_completed_effort`, **both from the same parameterized query**. The `$$()` markers in `js` are what
get replaced with the fetched arrays at render time.

> ⚠️ Copy the **shape**, not the `WHERE`: this is a real export, and its `NOW() - INTERVAL '6 months'` window is
> exactly the clock-anchored form that empties out as a **frozen** dump ages (§2.6 Rule 5). Anchor a demo window
> to the data (`max(<date col>)`) or to a Period param instead.

### 1.3 `ChartJsModel` — field by field

| Field · type | Meaning | Required | Default |
|---|---|---|---|
| `id` · String | the model's uuid | yes | — |
| `js` · String | render script; data via `$$('name', default, 'Type')`; `this` = the panel. **The only field the `$$()` tokenizer looks at.** | yes | — |
| `html` · String | mount markup — `<canvas>` (Chart.js) or `<div>` (Plotly/ECharts) or `<pre class="mermaid">`. Rendered **verbatim**: `$$()` here is never substituted, and an inline `<style>` here is **global** (use `cssByTheme` instead) | yes | — |
| `css` · String | LEGACY single CSS block; still honoured — read as the `"*"` entry of `cssByTheme` when that key is absent | no | omitted |
| `cssByTheme` · Map | **per-theme CSS** — key `"*"` (all themes) or an exact theme name (`Standard` / `Dracula` / `Forest` / `Dark` / `Dark Blue`). Authored on the editor's **Css** tab, whose theme pills are generated from the platform's skin list. Only the `"*"` block **plus the active theme's block** are emitted, each auto-scoped to that chart instance (§6) | no | omitted |
| `schedule` · `ScheduleDto` | the **Caching** tab's cron — fanned onto every replacement's `query.schedule`, which makes those queries cacheable (Gotcha 12) | no | present as empty `{"job":{}}` |
| `replacements[]` · `ChartJsReplacement` | one entry per distinct `$$()` name | no | `[]` |

### 1.4 `ChartJsReplacement` — field by field

| Field · type | Meaning |
|---|---|
| `name` · String | the binding key = **1st arg of `$$(...)`** |
| `group` · String | the **exact literal `$$(...)` text** — the server does `js.replace(group, value)`, so it must match `js` byte-for-byte |
| `type` · String | a `ReplacementType` string (`String[]`, `Integer[]`, `Double[]`, `Full`, …) — determines how the value is emitted as a JS literal |
| `replaceStrategy` · enum | `QUERY` (run `query`, pull `columnName`) or `LABEL` (inject `value`); `null` = auto-discovered, not yet bound |
| `queryIdentifier` · String | identifier of the saved query (matches `query.identifier`) |
| `query` · `QueryDto` | an embedded **TRIMMED 12-field copy** of the saved query (SQL, source, params, id) — this copy is what actually runs. ⛔ Trim it: see the ⛔ in §1.1 — the rep-object emitted by `query add` carries extra fields that make the whole chart render blank |
| `columnName` · String | the result column to pull (lowercased — Postgres folds unquoted aliases); **absent for `Full`** |
| `defaultValue` · Object | arg #2 of `$$()` stored verbatim as a string (`"deflt"`, `"[1]"`, `"0"`, `"[]"`) |
| `value` · Object | the literal injected when `replaceStrategy == LABEL` — injected **raw/unquoted** unless `type` is exactly `String` (§2.3) |
| `maxItemsCount` · Integer | row cap → set as `query.itemsPerPage` before running (default **1000**) |
| `order` · int | display/eval order |
| `futureReplacements[]` · `ChartJsReplacement` | the editor-built drill chain (§5.1); `[]` in all sample charts |
| `currentFutureRepNumber` · Integer | which drill step the editor is currently showing; `null`/absent = the root replacement |

> 🔧 **Tooling.** Place the node with the generic plugin-add — the slot is auto-routed to `Javascript`
> (`chart.js.plugin` ∈ `JAVASCRIPT_SLOT_PLUGINS`), so `--model` or `--settings` both land in the right place:
> ```
> node add --parent <page/parsis id|name> --plugin chart.js.plugin --name "Monthly Team Velocity" --model @chart.json
> ```
> The `chart.json` blob itself (the `{id,html,js,replacements[]}`) is **hand-written** — there is no chart
> command and `node set-model` writes into `model` (wrong slot). Data queries via `query add` (§3).
> `validate` **does** parse the chart blob and runs several chart checks (Gotcha 10 lists exactly what it
> catches and what it still cannot) — but it can never prove the chart *renders*, so open the page.
> See [`tools/README.md`](tools/README.md).

---

## 2. Data binding — the `$$()` placeholder system

### 2.1 The grammar

The tokenizer scans **`model.js` and nothing else** for `$$(` … matching `)` and parses the inside by a naive
`split(",")`. ⛔ **`model.html` is never tokenized** — it is emitted verbatim into the page, so a `$$()` written
in the `html` reaches the browser literally and evaluates through the `window.$$` fallback (i.e. it always shows
its default). Put every data binding in `js`; keep `html` to the mount element.

```
$$('<name>', <default>, '<type>')
   └ arg0     └ arg1      └ arg2
```

- **arg0 `name`** (required) — trimmed, outer single-quotes stripped → the replacement's `name`. Binding is
  **by name**: the `$$()` and its `ChartJsReplacement.name` must match.
- **arg1 `default`** (optional) — trimmed, **quotes kept verbatim**. Stored as `defaultValue`. It is a raw JS
  expression the browser evaluates **if the server left the placeholder unsubstituted** (see 2.4).
- **arg2 `type`** (optional) — trimmed, single-quotes stripped, must equal a `ReplacementType` string.

Because splitting is a naive comma-split, **`default` must be a single element with no internal commas** — this
is why the shipped templates write `['-']`, `[1]`, `[0]`, `[100]`, `[]`, not multi-element arrays. Only a
**single** space in `$$ (` is collapsed to `$$(` (the one-space form only — two-plus spaces or a tab are **not**
handled and would break discovery, so always write `$$(` with no separating whitespace); nested `()` inside are
tolerated (paren-depth scan).
⛔ **The tokenizer normalises only the copy it scans — never the stored script.** Discovery collapses `$$ (` and
folds repeats of the same `name` onto the first occurrence's literal text, but substitution later runs against the
**untouched** stored `js` and replaces that literal text. Two consequences, both silent:
- a repeated `name` whose occurrences are **not byte-identical** (a different default, an extra space) — only the
  first spelling is substituted; the others reach the browser and fall back to their inline default;
- `$$ ('X', …)` written with whitespace — discovered, listed in the Replacements tab, and **never substituted**.

Always write `$$(` with no space, and write every occurrence of a repeated placeholder byte-for-byte the same.
(Same failure as Gotcha 1: `group` must match `js` exactly.)

### 2.2 `QUERY` vs `LABEL` strategy

| Strategy | What the server injects | Uses |
|---|---|---|
| `QUERY` | runs the replacement's `query`, pulls column `columnName` (up to `maxItemsCount` rows), builds a typed JS literal | the normal case — data from SQL |
| `LABEL` | injects the replacement's `value` — **raw, unquoted**, unless `type` is exactly `String` (see §2.3) | a fixed literal, or a value pushed by cross-filter/session |

Only **`QUERY`** replacements register their query with the filter bar (LABEL ones are skipped). So **a chart is
filterable only through its `QUERY` replacements**.

### 2.3 The type set (`ReplacementType`)

`type` decides how the fetched value(s) become a JS literal in the emitted `js`. Unknown strings fall back to
`String`.

| Scalar | Array | Emitted as |
|---|---|---|
| `String` | `String[]` | `'a'` / `['a','b']` (single-quotes escaped) |
| `Integer` `Long` `Float` `Double` `BigDecimal` | each with `[]` | `3` / `[1,2,3]` (unquoted numbers) |
| `Boolean` | `Boolean[]` | `true` / `[true,false]` |
| `Full` | — | **the whole rowset** serialized to JSON — **no `columnName`** |
| `Json` | — | the value serialized as JSON |

⛔ **Do not bind a QUERY replacement as a temporal type (`LocalDate` / `LocalTime` / `LocalDateTime`, scalar or
array) or as `Short`.** The names exist in the type list, but the fetch path has no case for them: the values are
collected into a `String` array and then handed to a converter that expects the declared type, so the replacement
fails with a *"Replacement '<name>' failed: …"* toast and the chart silently draws its `$$()` defaults. Format in
SQL instead and bind as text or number — `to_char(created_at,'YYYY-MM-DD') AS d` → `String[]`,
`CAST(qty AS integer)` → `Integer[]`. (A *scalar* date is worse than useless even when it does get through: a
non-`String` type is never quoted, so the date is spliced in as the bare token `2026-07-26` — JS arithmetic.)

Rule of thumb: axis labels → `String[]`, numeric series → `Integer[]`/`Double[]`, a KPI single number →
`Double[]` then index `[0]` in the JS (as the Plotly gauge template does), a raw table you shape in JS →
`Full`.

> **`Full` — the shape you actually get.** It is the raw rowset, not an array of plain objects: each row is
> `{cols: [ {label:'<result column>', value:<v>, tableName:'…', column:{…}}, … ]}`. So pick a column by its
> `label`:
> ```js
> const rows   = $$('data', [], 'Full');
> const pick   = (r, name) => (r.cols.find(c => c.label === name) || {}).value;
> const labels = rows.map(r => pick(r, 'monthsn'));
> const values = rows.map(r => Number(pick(r, 'cnt')));
> ```

**The SQL type does not have to match the declared type — the server coerces.** Before a fetched column value is
placed into the typed array, it is converted to the element type the replacement declares: any DB `Number` →
`Integer`/`Long`/`Float`/`Double`/`BigDecimal`, anything → its `toString()` for `String`/`String[]`, `"true"`/
`"false"` text → `Boolean`. So an `INTEGER` column bound as `Double[]` just works, and a numeric-looking text
column bound as `Integer[]` works too. What is **not** coerced: a genuinely non-numeric value for a numeric type
(it fails and surfaces as a toast, §2.4), and the `Full`/`Json` types (passed through unchanged). Prefer
declaring the type you want in JS and letting the coercion happen — except for dates and `Short`, which must be
cast in SQL (see the ⛔ above).

⚠️ **A SQL `NULL` is not dropped.** It is emitted as the token `null` inside a numeric array (`[1,null,3]` — a
gap in the series) and as the string `'null'` inside a `String[]` (a category or pie slice literally labelled
"null"). `COALESCE(<col>, 'Unspecified')` / `COALESCE(<num>, 0)` in the SQL, or filter the rows out — a
`GROUP BY` over a nullable column is the usual source.

> ⛔ **A `LABEL` value is injected RAW unless `type` is `String`.** The rule the converter applies is: *a value
> that is already text, for a type that is not `String`, is spliced into the JS verbatim*. So
> `{"replaceStrategy":"LABEL","type":"Integer","value":"42"}` emits `42` (good), and
> `{"…","type":"String[]","value":"['A','B']"}` emits `['A','B']` (good) — but
> `{"…","type":"Integer","value":"N/A"}` emits the bare token `N/A`, which is a **JS syntax error that kills the
> whole chart script**. Rule: with `type:'String'` write the plain text and let the platform quote it; with any
> other type the `value` must already be **valid JavaScript on its own**.

### 2.4 How the server substitutes (the render pipeline)

The chart service builds the rendered script (`getJsChartConfigJson(model, realm, client)`) →
1. **merge** — re-parses `$$()` from `js`, **adds** newly-seen placeholders, **removes** replacements whose name
   no longer appears, and syncs each `type`. Persisted `query`/`columnName`/`value`/`replaceStrategy` survive
   because matching is by `name`. Note what it does **not** re-sync: `group` (Gotcha 1).
2. seed `js = model.js`, then for each replacement:
   - `QUERY` → run the embedded query **with a service token** (dashboards are aggregate, not row-scoped).
     `Full` → JSON of rows; array types → pull `columnName` per row, coerce to the element type (§2.3) →
     e.g. `['Jan','Feb']` / `[1,2,3]`.
   - `LABEL` → the replacement's `value`.
   - substitute: a literal `js.replace(group, <converted value>)`. **If the value is null the `$$()` is left
     untouched** in the output (so the browser default takes over).
3. The rendered JS is exposed to the browser twin and executed with `this` bound to the chart panel, so the
   script has `this.$find(sel)`, `this.$component()`, `this.chart`, `this.crossFilter(field,value)`,
   `this.showFutureQuery(label)`.

**Design-time fallback:** the page defines `window.$$ = function(name, defaultValue){ return defaultValue; }`.
Any `$$()` left literal in the JS evaluates in-browser to **its 2nd arg (the default)** — this is how a template
renders sensible dummy data before an author binds a query, and why every `$$()` default must itself be valid JS.

**Replacement failures are visible — read the toasts.** Every replacement that throws (query error, auth
failure, a value that cannot be coerced to the declared type) is collected instead of aborting the render, and
the panel raises **up to 10 toasts**, each reading *"Error occured in chart component &lt;node name&gt;"* plus the
cause, in the form `Replacement '<name>' failed: <cause> (db value type=…, js replacement type=…)`. Two
consequences for you: (a) name your chart nodes meaningfully — the node **name** is the only locator in the
toast; (b) a chart that draws with its defaults *and* raises a toast is a **binding failure**, not an empty
dataset. Errors reported by the query itself (bad SQL, unknown column) arrive through the same channel.

**The chart body arrives in a SECOND round-trip.** A chart node first renders only an empty placeholder that
reserves the space, then its JS twin immediately fires a follow-up AJAX request that returns the real markup
(`html`) and the rendered script, which is executed at that point. Consequences you must design around:
- at page `domready` the chart's `<canvas>`/`<div>` **does not exist yet**, so a page-level script that queries
  for it at domready finds nothing — bind on the element from **inside the chart's own `js`** (which runs after
  the body arrives), or from an `nct.html.plugin` component that re-checks on its own lifecycle hooks
  ([24](24-html-component-studio.md) §6);
- a chart is never "immediately visible" for a screenshot/perf budget — expect a brief placeholder;
- because the chart script runs on *its* load (not the page's), one slow query delays only that chart.

> **The wait draws no card, and neither should your chart.** While the body is in flight the platform paints
> nothing but a slow highlight travelling across the reserved height: no border, no fill, no rounded corners, no
> title bar. It cannot do more, and deliberately does not try: whatever chrome your `html` carries is not in the
> browser during the wait, so a decorated placeholder would be the platform guessing at your design — and
> flashing a frame that then vanishes as a frameless chart lands. Hence the rule in **§6A**: a chart's `html` is
> its caption and its plot, with **no** background, border or radius. Anything a dashboard needs to look framed
> belongs to the page's own markup, which is painted in the first paint — not to a cell that is still loading.
>
> The reserved height is the box that chart rendered into **last time in this browser** (kept in `localStorage`,
> keyed by the node's `uniqueIdentifier`); 100 px on a first visit. That is why a first load steps as charts
> land and later loads do not — nothing for you to configure, but it does mean a screenshot of a first visit and
> one of a repeat visit reflow differently.

### 2.5 The chart *type* is the JS library, not a field

There is **no** `engine`/`type`/`chartType` field on `ChartJsModel`. What you draw is decided entirely by the
code in `js`, using whichever of the **four** charting libraries the chart plugin loads on every page that hosts
a chart:

| Engine | Version | Mount + init in `js` |
|---|---|---|
| **Chart.js** | 3.9.1 | `const ctx=this.$find('canvas')[0].getContext('2d'); this.chart=new Chart(ctx,{...});` — set `this.chart` (it has `.destroy()`, used by the drawer-redraw) |
| **Apache ECharts** | 5.6.0 | `var chart=echarts.init(this.$find('div')[0]); chart.setOption({...}); window.addEventListener('resize',function(){chart.resize();});` — do **not** set `this.chart` (echarts uses `.dispose()`, so the drawer-redraw's `.destroy()` would crash) |
| **Plotly** | 2.27.0 | `Plotly.newPlot(this.$find('div')[0], data, layout, {displayModeBar:false, responsive:true});` — do **not** set `this.chart` |
| **Mermaid** | 10 | `<pre class="mermaid">DEFINITION</pre>` in `html`; `mermaid.initialize({startOnLoad:false, securityLevel:'loose'}); mermaid.init(undefined, this.$find('.mermaid')[0]);` — the diagram is text, no `$$` needed |

> ⚠️ **Only the CORE libraries are loaded** (what the chart plugin injects, verbatim): `chartjs/chart.min.js` (Chart.js
> **v3.9.1**), `plotlyjs/dist/plotly.min.js`, `echarts/echarts.min.js`, `chartjs/chartjs-adapter-date-fns.bundle.min.js`
> (enables Chart.js **time** scales), `mermaid/mermaid.min.js`. The Chart.js **plugins** that ship as static files —
> `chartjs-plugin-datalabels`, `chartjs-plugin-zoom`, `chartjs-plugin-annotation`, and the `chartjs-gauge` type — are
> **NOT auto-loaded**, so a chart that references `datalabels`, a `gauge` type, zoom, or annotations renders **empty
> or throws** unless its `js`/`html` loads that plugin itself first. Prefer **core Chart.js** types (bar/horizontalBar
> via `indexAxis:'y'`, line, doughnut/pie, radar, polarArea, scatter, bubble) + core scales/legend/title/tooltip; for
> a **gauge / KPI** use a **Plotly `indicator`** (the seed KPI template does) or an ECharts `gauge`, not the Chart.js
> gauge plugin. Chart.js **data labels on bars** need the datalabels plugin → use Plotly/ECharts if you need them.

> ⛔ **The MOUNT and the SELECTOR must be emitted by ONE helper.** `js` reaches its element through
> `this.$find(sel)`, which is `this.$component().find(sel)` (`RichClass.js`) — **scoped to this chart's own
> `html`**. Two ways that goes wrong, both of which leave a blank card and speak only in the browser console:
>
> 1. **the selector names something the mount does not contain.** `this.$find('div.kpi-plot')[0]` over an
>    `html` of `<canvas></canvas>` is `undefined`, and Plotly answers
>    `Error: DOM element provided is null or undefined` (`Plotly.getGraphDiv`); Chart.js answers
>    `Canvas is null`. Nothing server-side notices — the model is valid JSON, the query binds, the page
>    renders.
> 2. **the engine and the mount tag disagree.** Chart.js draws INTO a `<canvas>`; Plotly and ECharts REPLACE
>    a `<div>` and will not take a canvas. A KPI tile is the usual casualty: it is a Plotly `indicator` living
>    among Chart.js cards, so if every card shares one mount helper it silently gets the canvas.
>
> Author the mount and the lookup together — one function, one flag (`mount(title, height, plotly=…)`) — so a
> new chart cannot pick the wrong pair. `mrjun.py validate` flags both (`_check_chart_mount_matches_engine`):
> a `$find`/`getElementById` token that appears nowhere on the chart's page, and Plotly running on a
> canvas-only mount. It is deliberately page-wide, not chart-local, because `$find` falls back to `$('body')`
> and a sibling HTML plugin may legitimately provide the element.

The editor's **template gallery** ("Start from a template") is **88 ready-made starters** (a classpath catalog
served by `ChartTemplateService`), **sectioned by engine — Chart.js 29 · Apache ECharts 20 · Plotly 24 ·
Mermaid 15** — and, within each engine, grouped by category. The category set is per engine and is whatever the
catalog carries; today: Chart.js `Comparison, Trend, Part-to-whole, Relationship, Distribution, KPI`; ECharts
the same six plus `Flow, Financial`; Plotly `Part-to-whole, Relationship, Distribution, KPI, Flow, Financial,
Geo, 3D`; Mermaid `Relationship, Flow, Hierarchy, Sequence, Project, Structure, Journey`. (Engines and
categories are read from the catalog at startup, so treat the counts as "about this many", not a contract.)
Each starter is `{key,name,category,engine,html,js,svg}` and (except Mermaid)
its `js` already uses the `$$('Name', <single-element default>, 'Type')` convention. When authoring by hand,
copy the mount pattern for your engine from the table above and add one `$$()` per data slot.

### 2.6 The data a chart needs (demo-grade datasets)

A chart is only as finished as the **rowset behind it**. The binding can be perfect — right `columnName`, right
type, no toast — and the page still reads as a stub, because a doughnut with one slice, a bar chart with two bars
and a trend with three points all say the same thing to a viewer: *nobody filled this in*. So decide **how many
marks the query must return** before you write the SQL, and check the count with SQL rather than by eye.

> ⚠️ **An empty result is NOT the design-time default (§2.4).** The `$$()` default only takes over when the value
> comes back **null** — i.e. when the replacement *failed*. A `QUERY` that legitimately returns **zero rows**:
> - for an **array** type substitutes the literal `[]` → the chart draws its axes, grid and legend with nothing
>   inside them: an empty frame, which reads as *broken*, not as "no data";
> - for a **scalar** type (a KPI tile) the fetch takes the first element of an empty array, so the replacement
>   **fails**, the panel raises the `Replacement '<name>' failed: …` toast (§2.4) **and the tile renders its
>   `$$()` default** — a plausible-looking, entirely fabricated number. Never ship a KPI whose query can return
>   no rows: shape it so it always yields exactly one (`SELECT COALESCE(sum(<measure>),0) AS v FROM …`).

**How many marks each chart form needs**

| Chart form | one "mark" = | Minimum to read as real | Comfortable | What it looks like below the minimum |
|---|---|---|---|---|
| Trend / time series (line, area) | one point per period | **6** periods | 12–24 | a 3-point line is a zig-zag with no trend — the eye reads it as placeholder art |
| Categorical bar, one series | one bar | **4** categories | 5–8 (cap ≈ 12) | 1 bar = a KPI drawn badly; 2 bars = a sentence, not a chart |
| Pie / doughnut | one slice | **3** slices | 4–6 (**never > 7**) | 1 slice = a solid ring at 100 % — the most obvious stub on any dashboard |
| Grouped / stacked bar | one bar per (category × series) | **3 categories × 2 series** | 4–6 × 2–3 | a single group, or a legend entry whose bars are all zero |
| KPI tile | one number | **1** non-null row | 1 | zero rows → toast + a fabricated default (box above) |

What follows from that table:

**Rule 1 — a status/risk axis must exercise its WHOLE vocabulary.** If `<Entity>` defines six statuses and the
seeded rows only ever use two, every chart over status draws two marks, the semantic palette (§6.1) shows two
colours, and the dashboard states — falsely — that the process has two states. Seed **at least one row for every
value of every axis you chart**, and several rows for the values that carry the story, so the bars differ in
height (all-equal bars read as fake too). The check is one query per axis:

```sql
SELECT <axis col>, count(*) FROM <schema>.<entity> GROUP BY 1 ORDER BY 2 DESC;
```
Its row count **is** the number of marks your chart will draw, and its values **are** the labels the palette will
have to map.

**Rule 2 — a dimension is only worth a FILTER if it has enough distinct values.** **≥ 3** distinct values is the
floor (the null "— All —" option is added for you, §4.5); the seeding target for a demo is **≥ 4, with ≥ 2 rows
behind each** ([10](10-database-management.md) "## Seeding demo-grade data into the dump"). A one-option dropdown
is noise; a lookup that returns **zero** options is worse — `ParamsPanel` drops that control entirely, so the bar
silently renders one filter fewer than you designed and nothing reports it (§4.5, and §4.6 for how to choose the
set). Check with `SELECT count(DISTINCT <col>) FROM <schema>.<entity>;` **before** you declare the param. A
dimension that cannot reach three values should be charted, not filtered on.

**Rule 3 — cap a long axis in SQL, and always `ORDER BY`.** `maxItemsCount` (§1.4, default **1000**) is a safety
net, not a design decision: 1000 categories is a black smear with unreadable labels. Author the cap yourself and
name it in the chart's title so the reader knows what they are seeing:

```sql
SELECT <axis col> AS label, count(*) AS cnt
FROM <schema>.<entity>
GROUP BY 1 ORDER BY 2 DESC LIMIT 8        -- title: "Top 8 <Entity> by <axis>"
```
For a **status/lifecycle** axis, order by the dimension's own `sort_order` instead of by the measure, so the same
statuses land in the same positions (and the same colours) on every chart of the page.

**Rule 4 — a trend needs one row per period, including the empty ones.** A plain `GROUP BY` omits periods with no
rows, and the chart joins the surviving points into a straight line — claiming a continuity the data does not
have. Emit the axis first, then LEFT JOIN the measure onto it:

```sql
WITH bounds AS (
  SELECT date_trunc('month', min(<date col>)) AS lo, date_trunc('month', max(<date col>)) AS hi
  FROM <schema>.<entity>
)
SELECT to_char(p.d, 'YYYY-MM') AS period, count(e.id) AS cnt
FROM bounds, generate_series(bounds.lo, bounds.hi, INTERVAL '1 month') AS p(d)
LEFT JOIN <schema>.<entity> e ON date_trunc('month', e.<date col>) = p.d
GROUP BY 1 ORDER BY 1
```
(Format the period **in SQL** and bind it as `String[]` — a temporal replacement type does not work, §2.3.)

**Rule 5 — ⛔ the time-window trap: the dump is FROZEN at build time.** The rows a chart reads ship as literal
`rows` inside `project-db.dump` ([10](10-database-management.md) "## Table — full example + annotation"); nothing
regenerates them, and the export may be imported weeks or months after you build it. Any window anchored to the
*clock* therefore empties out as the export ages — the dashboard that demoed perfectly is blank on the day it
matters:

```sql
-- ⛔ ages out: empty as soon as the export is older than the window
WHERE <date col> >= now() - INTERVAL '30 days'
-- ✅ anchor to the DATA, not the clock
WHERE <date col> >= (SELECT max(<date col>) FROM <schema>.<entity>) - INTERVAL '12 months'
-- ✅ or let the viewer choose the period — as a DROPDOWN (a scalar date param does not substitute, §3.1)
AND to_char(<date col>, 'YYYY-MM') = {name: 'Period', type: 'dropdown-string',
                                      dropDownPopulation: {query: 'Period Lookup', value: 'period', name: 'period'}}
```
The seeding half of this — spreading seeded dates across the window so every period is populated — is
[10](10-database-management.md) "## Seeding demo-grade data into the dump".

**Rule 6 — ⛔ never put a `--` comment in a saved query.** The platform does not run the query as written:
it wraps it for paging and appends the tail on the **same line** —

```sql
select pp.* from ( <your query> ) pp OFFSET 0 ROWS FETCH NEXT <itemsPerPage> ROWS ONLY
```

— and a chart generator normally collapses the query to one line before storing it. Either way a `--`
comments out everything after it: the rest of the `SELECT`, the closing paren, and the `OFFSET` clause.
Postgres answers `ERROR: syntax error at end of input`, and the cell renders
`Error occured in chart component <title>`. The tell is that the SQL reads perfectly in the generator
source, where the comment sits harmlessly on its own line — nothing offline sees the collapsed form.

```sql
-- ⛔ dies the moment the query is stored on one line
SELECT a, -- the measured value
       b FROM t
-- ✅ the block form survives both the collapse and the wrapper
SELECT a, /* the measured value */ b FROM t
-- ✅ better still: the explanation belongs in the generator, above the query
```

`validate` ERRORs on a `--` in `rep-objects.queries[].query` (string literals are stripped first).

> ✅ **The check, before you bind anything.** Run each chart's SQL with **every filter empty** (the `1=1` form,
> §3.1) and count the rows. That number is the number of marks; compare it against the table above. When it is
> under the minimum the fix is in the **data** — seed more rows, widen the window, merge tiny categories into an
> "Other" bucket — never in the chart JS. Not machine-checkable: `validate` never runs your SQL (Gotcha 10).

---

## 2A. The specified charts are a FLOOR — propose more, and challenge the ones you were given

A spec that names charts — a brief, a screen list, a ticket, one sentence from the user — states the
**minimum**. It was almost always written before anyone read the schema, so it is simultaneously **too short**
(the data model affords charts nobody thought of) and **wrong in places** (it names charts this schema cannot
compute, or computes twice). Two ways to fail, and they fail for the same reason — the author decided alone:

- **Under-delivery** — build exactly what was listed, ship, say nothing. The dashboard is only as good as a list
  written by someone who had not yet seen the columns.
- **Over-reach** — decide a listed chart is wrong and quietly build something else, or nothing. The reviewer looks
  for the chart they asked for, does not find it, and now distrusts every other number on the page.

> ⛔ **The list is a contract, not a ceiling.** Build **every** chart it names, wherever it is buildable (§2A.3
> covers "not buildable") — that is the contract. Then do the thinking the spec did not: *what else does this data
> model afford* (§2A.1) and *what in the given list is wrong* (§2A.2). Resolve neither privately: the output is a
> **proposal** (§2A.3) — never a silent substitution, never a silent omission.
> `validate` checks none of it — it has no idea what you were asked for (Gotcha 10). The one machine hold is the
> **build plan**: a chart you were given, entered as a `plan.json` item, FAILS `coverage` when it is not in the
> build, and downgrades to a recorded warning only when you mark that item `deferred`
> ([19](19-build-decision-procedure.md) Phase 9 "Machine gate (charts — partial, via the PLAN)"). Everything
> else below is a **review rule**, and the reviewer is you.

### 2A.1 Deriving candidates — a pass over the schema, not inspiration

Enumerate, do not brainstorm. `db list-tables --schema <schema>`, then `db show <table> --schema <schema>` on
every table a page will list ([10](10-database-management.md)), and test **each column** against the shapes
below — most columns match none, which is the expected outcome; a candidate is something you *find* in the DDL,
not something you think of. Then size each candidate before it costs a cell, with the two §2.6 counts on its
column: `SELECT count(DISTINCT <col>) FROM <schema>.<entity>;` (that number is the mark count) and
`SELECT <col>, count(*) FROM <schema>.<entity> GROUP BY 1 ORDER BY 2 DESC;` (that is the spread — §2.6 Rule 1).
Before the rows are seeded, read those two off the column's **CHECK vocabulary** / the seed you have planned
([10](10-database-management.md)) and re-run them for real on the second pass (§2A.3 "Do it twice"). Pick the
candidate's type from the list in **§9.1**.

| Shape you find in the data model | The chart it affords | The question it answers | When it does NOT earn its place |
|---|---|---|---|
| **A low-cardinality vocabulary column** — status / risk / type / category, 3–8 distinct values | doughnut or one-series bar (`doughnut`/`pie` ≤ 7 slices, `bar` — §9.1), coloured by **label** (§6.1) | "what is the mix, and is any bucket abnormally large?" | fewer than 3 values in the seeded data (§2.6 Rule 2), or one value holds > 90 % — that is a KPI tile, not a distribution |
| **A dated column** | line/area trend, one point per period, empty periods emitted (§2.6 Rule 4) | "is the volume rising or falling?" | the data spans < 6 periods (§2.6) — ship a "this period vs last" KPI delta instead |
| **A dated column + a due/target date** | ageing / backlog bar over buckets (`0–7 · 8–30 · 31–90 · 90+`), sequential ramp (§6.1) | "how much is past due, and how badly?" | rows close inside the first bucket (every other bar is empty), or the due date is null on most rows |
| **A numeric measure column** | three *different* charts: a KPI tile for the total (Plotly `indicator`, Recipe D); a **top-N** horizontal bar (`indexAxis:'y'`); a **concentration** view (the top N's share of the total) | "how big · who is biggest · how concentrated" | the column is an id/code that only looks numeric, or rows carry mixed units/currencies with no conversion column |
| **Two linked entities, or two ordered lifecycle states** (an FK, or a status history) | **funnel** = horizontal bar over the ordered stages, ordered by `sort_order` and not by the measure (§2.6 Rule 3); Chart.js has no funnel type (§9.1) — ECharts `funnel` if you want the taper | "where does the flow stop converting?" | the stages are not strictly ordered, or a row may skip/revisit them so the counts do not decrease — that is a mix, not a funnel |
| **An owner/assignee column** | workload bar by owner; owner × status as a **grouped** bar (stacked only if the stack is one whole — check 1) | "is the work spread, or piled on one person?" | more than ~12 owners with a long tail (cap in SQL, §2.6 Rule 3), or the column is null on most rows |
| **A threshold / target / limit column** | actual vs target as a combo bar+line (§9.1) or a Plotly bullet/indicator with a delta — **plus** a breach-**count** KPI | "are we inside the limit, and how many rows are not?" | the target is a constant nobody stored (check 2), or target and actual are in different units |
| **Two timestamps on the same row** (created→closed, submitted→decided) | cycle time: median duration per period as a line, or a duration-bucket histogram (`bar`) | "how long does it take, and is it getting faster?" | the second timestamp is null on most rows — you would be charting only the survivors: say so in the title, or drop it |
| **A second low-cardinality column on the same table** (two vocabulary columns side by side — status × type, type × owner) | cross-tab: grouped or stacked bar (category × series), one colour per series held across the whole page (§6.1) | "does the mix differ by `<the second axis>`?" | `count(DISTINCT a) * count(DISTINCT b)` exceeds ~24 marks, or one of the two has fewer than 3 values — filter on that one instead (§4.6) |

**Rank by consequence, not by variety.** A chart earns a cell only if a viewer would **do something differently**
after reading it. Write that sentence for each candidate *before* you author it:

> *"If this chart shows `<extreme>`, the viewer will `<action>`."*

If the action is "nothing", "note it", or "look at another chart", the candidate is decoration — drop it, or
demote it to a KPI tile. Then place the survivors:

- **the front door takes 3–6 charts, and 4–6 is the target** ([21](21-homepage-and-redirect.md) "## Choosing the
  front door — chart dashboard or main worklist": 3–6 charts over the case's own axes, with roughly 4–8 KPI tiles
  above them; Recipe E lays out 4–6 cells). Below 3 the page reads as a stub; past ~8 nobody reads any of them,
  and one shared filter set (§4.6) stops fitting all of them honestly;
- **the rest go on a second, themed page** — same layout shape, its own quick link
  ([17](17-left-nav-quick-links.md)) — rather than crowding the front door;
- two candidates over the **same** column are one cell, not two (check 3 below).

### 2A.2 Challenging the list you were given

Run every specified chart past these before you author it. Each is written *symptom → why it is wrong → what to
propose instead*.

**1. The chart FORM does not fit the measure.** *Symptom:* a part-to-whole form (pie, doughnut, 100 % stacked
bar) over parts that do not sum to a whole — overlapping tags, counts taken under different filters, an average
per category; a pie with more than 7 slices (§2.6, §6.1); a `line` over a nominal axis; a stacked bar whose stack
mixes unrelated measures. *Why it is wrong:* the form itself asserts a relationship — "these are shares of one
thing", "neighbouring categories are continuous" — that the data does not have, and re-ordering the axis then
changes the picture without changing a number. *Propose:* a one-series bar sorted by the measure (horizontal when
there are many categories — there the axis label does the identifying, §6.1); grouped instead of stacked; and
fold the tail into an `OTHER` row **in SQL** (§2.6 Rule 3) before you touch the form at all.

**2. The metric CANNOT be computed from this case's schema.** *Symptom:* there is no such column, no join path to
one, or it needs data the application does not own — an external benchmark, a target nobody stored, a rate whose
denominator lives in another system. *Why it is wrong:* the only two ways to "ship" it are a fabricated number (a
demo that lies, and a figure nobody can reproduce) or a hardcoded literal that no filter moves — and a frozen
dump makes that permanent (§2.6 Rule 5). *Propose:* raise it **with the evidence** — the entity, the columns you
searched, the one that is missing — and offer the nearest computable proxy (a breach **count** where a per-row
threshold does exist; a self-comparison — this period against the previous — where no external baseline exists),
plus the option of adding the column to the model ([10](10-database-management.md),
[11](11-business-logic-dynamic-crud.md)). Never fake it, and never quietly drop it.

**3. Two specified charts answer the SAME question — or answer it differently.** *Symptom:* two cells with the
same `GROUP BY` and the same measure, differing only in form (a doughnut and a bar over one `<status col>`); or
two cells that look unrelated but recompute one number over a different window, a different filter or a different
denominator, so the page states two contradictory truths (one "total" excludes cancelled rows, the other includes
them). *Why it is wrong:* the duplicate spends a cell that §2A.1 has a better candidate for; the contradiction is
worse — a viewer acts on whichever number they read first, and a cross-filter click drives the two apart, because
it re-runs only the queries that declare the clicked param (§5.2). *Propose:* keep the higher-ranked form and
spend the freed cell on a derived candidate; for a disagreement, pick **one** definition, paste it into both
queries, and name the window in both titles.

**4. The axis semantics and the colour treatment disagree.** *Symptom:* a verdict (traffic-light) palette on a
**nominal** axis — type, category, owner painted green→amber→red; or **one flat colour** across a nominal axis
that other cells also chart. *Why it is wrong:* colour is an assertion. A verdict ramp claims a good/bad ordering
the axis does not have; a single flat tone throws away the only free encoding the chart has and breaks "one
entity, one colour" across the page. §6.1 calls both defects, not style preferences. *Propose:* the family the
axis's meaning demands (§6.1: traffic-light · qualitative · sequential · diverging), keyed by **label**, never by
row position. This one is a **defect fix, not a redesign** — apply it and note it (§2A.3).

**5. The chart's `GROUP BY` is also one of its own filter params.** *Symptom:* a chart whose SQL groups by
`<col>` and also declares `{name: '<P>'}` against that same `<col>`. *Why it is wrong:* one pick — from the bar
or from a click — sets `<P>` on **every** page query that declares it, this chart's own query included (§5.2
step 2), so it re-runs as `WHERE <col> = '<value>' GROUP BY <col>` and collapses to a single mark: the chart you
filter *from* deletes itself on first use. *Propose:* make it the **selector** for that dimension — drop that one
`<P>` from its SQL, keep every other param, keep the `crossFilter('<P>', …)` handler (§4.6 "The GROUP-BY
exemption", §5).

**6. The denominator, the time window or the unit is undefined.** *Symptom:* "approval rate", "average processing
time", "share of high-risk" with no statement of *over what*, *since when*, *in what unit*; a percentage whose
base is not in the query; a duration with no unit on the axis. *Why it is wrong:* the number cannot be
reproduced, two authors compute it two different ways (check 3), and a clock-anchored window empties out as the
export ages (§2.6 Rule 5). *Propose:* pin all three in the SQL — denominator explicit, window anchored to the
data's own `max(<date col>)` or exposed as a `Period` dropdown (§4.6) — and state them in the chart's own title,
the only place a viewer can learn a scope caveat (§4.6's partial-coverage box prescribes exactly that remedy).

**7. A single number dressed as a chart, or a table dressed as a chart.** *Symptom:* a query that can only ever
return one row bound to a bar or a doughnut (one bar; a solid 100 % ring — §2.6's "below the minimum" column); or
a "chart" that is really a dozen columns of text to be read row by row. *Why it is wrong:* both waste a cell and
read as a stub — a KPI is read faster as a tile, a row list is read faster as a table. *Propose:* the number → a
Plotly `indicator` tile (Recipe D), with the SQL shaped so it always returns exactly one row (§2.6); the row list
→ the worklist/table page, never this one (no `crud.table`/`crud.tree`/`process.table` on a dashboard — Recipe E
step 4, Gotcha 10), reached from here by a drill (§5.3).

**8. The chart needs live or streaming data.** *Symptom:* "real-time", "live feed", an auto-refreshing ticker,
anything whose window is anchored to `now()`. *Why it is wrong:* the rows ship **frozen** inside `project-db.dump`
(§2.6 Rule 5); a chart re-queries only on the param-change event (§4.3) — there is no polling refresh — and the
Caching tab is a cache, not a refresh schedule (Gotcha 12). *Propose:* anchor the window to the data's own maximum
date, give the viewer a `Period` dropdown, and state in the proposal that "live" is an **environment** feature — a
scheduler refreshing the underlying table/materialised view in the deployed system
([12](12-queries-sources-schedulers-and-rest.md)) — not something a chart node can provide.

> ✅ **Which of the eight you can settle alone.** Checks **2, 5, 7** are mechanical — read the case's DDL, read
> each chart's SQL, and answer three yes/no questions: does every column the metric names exist (or is there a
> join path to it); does the `GROUP BY` column also appear in a `{name: …}` placeholder in the *same* query text;
> and can the query return more than one row at all (an aggregate with **no `GROUP BY`** returns exactly one,
> always — that is a KPI tile, not a chart). Run those three as gates before authoring. Check
> **3** is half mechanical (compare `GROUP BY` + measure + `WHERE` across the page's queries side by side) and
> half judgement. Checks **1, 4, 6, 8** need a judgement about what the axis *means*, so they are **review
> rules**: you make the call, and you write it down. `validate` catches **none** of the eight — its chart checks
> are the list in Gotcha 10, and "wrong chart for this data" is not on it.

### 2A.3 What to do with the findings

**Build what is specified wherever it is buildable.** Never substitute your own design for the one you were
given, and never omit one you were given — not because the alternative is worse, but because an unannounced
change is invisible to the only person who can approve it. Every chart in the list ends in exactly one of these
states, and four of the five produce a line for the user:

| State | When | What you do |
|---|---|---|
| **BUILT** | it is buildable and clears §2A.2 | build it; nothing to report |
| **BUILT, defect fixed** | the question and the form are right, the *presentation or the wiring* is not — palette (§6.1), an uncapped axis (§2.6 Rule 3), a clock-anchored window (§2.6 Rule 5), a `GROUP BY` that is also its own param (check 5) | fix it in place — this is library doctrine, not your redesign — and report the fix in **one line** |
| **BUILT, definition chosen** | the metric was under-specified (check 6) | pick one denominator/window/unit, put it in the chart's title, and report the choice so it can be corrected |
| **BLOCKED** | not computable from this schema (check 2), or it needs live data an export cannot carry (check 8) | never fabricate, never silently omit: report with the evidence **and** the nearest computable proxy; build the proxy only once it is agreed |
| **CHALLENGED** | the form or the measure is wrong (checks 1, 3, 7) | **build the specified chart anyway** — it is the contract — and hand back the alternative as a proposal; swap only on an explicit yes |

**Put every one of those states into the build plan, so the drop cannot be silent.** One `plan.json` item per
specified chart, `{"kind":"chart","name":"<the chart node's name>"}`: `"status":"done"` for the three BUILT
states, `"status":"deferred"` for a BLOCKED or an accepted CHALLENGE you did not build (with the reason in the
item's `note`). `coverage` then FAILS on a chart that is planned and absent, and prints the deferred one as a
recorded warning instead — the mechanics and the exact wording are
[19](19-build-decision-procedure.md) Phase 9 "Machine gate (charts — partial, via the PLAN)". A chart you **add**
gets its own item too, or it reports as an orphan (built, unplanned).

**The proposal format** — one row per proposed or challenged chart, so the user can answer each with a word:

| The question it answers | Chart form (§9.1) | Columns it reads | What a viewer does differently | Replaces / adds |
|---|---|---|---|---|
| "Who is carrying the open backlog?" | horizontal bar, top 8 (`indexAxis:'y'`) | `<entity>.<owner col>`, `count(*)` over open `<status col>` | moves work off the top bar | **adds** (cell 5) |
| "Is `<Entity>` throughput improving?" | line, 12 periods (§2.6 Rule 4) | `<entity>.<date col>` | escalates when the last 3 periods fall | **replaces** the specified pie over the same `<date col>` — 12 months is not a part-to-whole (check 1) |
| "`<Measure>` against the stored limit?" | combo bar + line, plus a breach-count KPI | `<entity>.<measure col>`, `<entity>.<limit col>` | works the breaching rows first | **adds** (second page) |

**Record it where CASE knowledge belongs — never in this library.** Proposals, objections, the definition you had
to choose and the evidence behind a BLOCKED metric are facts about **one** project. They go in the case notes — a
sibling folder of the unpacked export that `pack` can never sweep into the `.mrjun`
([23](23-distribution-and-known-gaps.md) "Case notes ship BESIDE the export, never inside it"):

```
mrjun.py case add --project <dir> --name 04-chart-review \
                  --title "Chart set — proposals & objections" --from chart-review.md
```

⛔ Nothing case-specific is ever written into `doc/builder` — this file included.

**Then put it to the user as a short decision list, not as prose.** One numbered line per item, each ending in a
question that carries your recommendation — *"3. `<metric>` needs a target column the schema does not have: add
`<col>` to `<entity>`, or drop the chart? (recommend: add)"*. Buried in paragraphs, the decision never comes back.

**Do it twice.** (1) **At design time, BEFORE authoring** — before the queries exist and the cells are laid out; a
proposal is free here and expensive once five chart nodes are wired. (2) **Again after the data is seeded**,
because numbers kill charts that looked fine on paper: run every chart's SQL with the filters empty and re-rank
against §2.6 — an axis that came back with two values, one category holding 95 %, a trend with four points. The
traffic runs both ways: a candidate you rejected at design time can become viable once the seeded data exercises
its axis. Both passes end the same way — what changed goes into the case note, the open questions go to the user.

---

## 2B. DASHBOARD CRAFT — the layout IS the deliverable

Charts are the easy half. The half that decides whether the screen reads as a product or as a report dump is
the **composition**: how the page is broken into sections, how wide each chart is, and whether the numbers a
director needs are readable in two seconds without scrolling.

This section exists because two builds of the SAME brief came out at opposite ends of that scale. Both had
correct SQL, both passed every gate, and only one of them would survive a demo. What separated them was not
effort — it was that the second one never made a single layout decision.

### 2B.1 The failure mode, named: THE GRID DUMP

Symptoms, all visible in one screenshot and none visible to `validate`:

| what the screen shows | what it means |
|---|---|
| A rigid **2-column grid**, every card identical width, identical height | nobody chose a layout; the charts were emitted in a loop |
| No page title, no one-line explanation | the reader has to infer what board they are on and that it is clickable |
| **No KPI strip** — no big numbers, no gauges | the three figures the audience actually came for are hidden inside charts |
| No sections, no headings, no icons — six anonymous cards in a column | the page has no argument; it is an inventory of queries |
| Nearly every chart is a **plain vertical bar** | one chart type used for six different questions |
| Y axis reads `0.5 / 1.5 / 2.5` on a **count** | fractional cases. Nothing is more instantly unserious |
| Category labels read `UNDER_INVESTIGATION`, `PENDING_DECISION` | raw enum keys shipped to a business audience |
| A chart with **one visible bar** | either the wrong chart for that question or demo data too thin to show it (§2.6) |

⛔ **A grid dump is a DEFECT, not a style.** Rebuild it. Every item above is fixable in the JS and the wrapper
HTML you are already writing; none of them costs a new query.

### 2B.2 The shape that works: a NARRATIVE of sections

A good board is read top to bottom as an argument, and each band answers one question:

```
  <title>            one h4 + one muted sentence that says what the board shows AND that it is clickable
  <filter bar>       global.replacement.plugin, its own card
  <KPI strip>        ONE row, 3-5 tiles: the numbers the audience came for. Big type. Gauges for rates.
  <section 1>        "WHERE THE LOSSES ARE"     — a card with a heading + icon, 3 charts of UNEQUAL width
  <section 2>        "THE MONEY STORY"          — a card with a heading + icon, 2 charts, 8/4 split
  <section 3>        "OPERATIONS"               — a card with a heading + icon, 3 charts
```

Three rules follow from that shape, and they are the ones a grid dump breaks:

1. **ONE CARD PER SECTION, not one card per chart.** A card is a band of the argument; the charts inside it
   share a heading and read together. A page of N identical single-chart cards has no argument at all.
2. **ROWS DIFFER IN COUNT AND IN WIDTH.** Across the page, use 4 tiles / 3 charts / 2 charts / 3 charts —
   not 2, 2, 2, 2. And *inside* a row the columns are unequal: a time series earns `col-xl-8`, the ranked bar
   beside it takes `col-xl-4`. Equal columns everywhere is the signature of the loop.
3. **WIDTH FOLLOWS THE CHART'S SHAPE**, never the grid's convenience:

   | chart | width | why |
   |---|---|---|
   | KPI number / gauge | `col-md-6 col-xl-3` | it is one figure; four fit on a row |
   | doughnut / pie | `col-md-6 col-xl-4` | it is square — extra width becomes empty background |
   | ranked horizontal bar (`indexAxis:'y'`) | `col-md-6 col-xl-4` … `col-xl-5` | needs height per row, not width |
   | time series / combo | `col-md-12 col-xl-7` … `col-xl-8` | the x axis is the whole point; starving it is what makes months illegible |
   | a wide table-like bar with long labels | `col-xl-12` | give it the row |

### 2B.3 The grid skeleton (copy this)

A section is an `nct.html.plugin` whose markup is the card, with one `<plugin id=… name="nct.parsis.plugin">`
per cell and a `nct.label.plugin` for the heading (a label node, so the heading is localizable — doc 20):

```html
<div class="main-card mb-3 card">
  <div class="card-header">
    <i class="header-icon lnr-chart-bars icon-gradient bg-plum-plate"></i>
    <plugin id="sec_dims_hdr" name="nct.label.plugin"></plugin>
  </div>
  <div class="card-body">
    <div class="row gy-3">
      <div class="col-md-6 col-xl-4"><plugin id="cell_severity" name="nct.parsis.plugin"></plugin></div>
      <div class="col-md-6 col-xl-4"><plugin id="cell_branch"   name="nct.parsis.plugin"></plugin></div>
      <div class="col-md-6 col-xl-4"><plugin id="cell_channel"  name="nct.parsis.plugin"></plugin></div>
    </div>
  </div>
</div>
```

The KPI strip is the same card with no header and `col-md-6 col-xl-3` cells. The money row is the same card
with `col-md-6 col-xl-8` + `col-md-6 col-xl-4`. Header icons come from the bundled Linearicons set —
`lnr-chart-bars`, `lnr-diamond`, `lnr-sync`, `lnr-users`, `lnr-alarm`, `lnr-briefcase` — with
`icon-gradient bg-plum-plate` for the tint (24b for the full HTML/plugin-tag grammar).

⛔ `col-md-*` AND `col-xl-*` together, always. `col-xl` alone collapses to full width on a laptop; `col-md`
alone never uses a wide screen. The pairs above are the tested ones.

### 2B.4 Recipes the grid dump never reaches

Four shapes carry most of the difference. All four are working code — copy and rebind.

**(a) KPI number tile** — Plotly `indicator`. One figure, big, coloured, no axes.

```js
var el=this.$find('.plot')[0];var fg=getComputedStyle(el).color;
var v=$$('Value',[0],'Double[]')[0];
var data=[{type:'indicator',mode:'number',value:v,
  number:{font:{color:'#22a7f0'},valueformat:','},
  title:{text:"Open cases",font:{size:11,color:fg}}}];
var layout={autosize:true,margin:{t:26,b:12,l:24,r:24},
  paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:fg}};
Plotly.newPlot(el,data,layout,{displayModeBar:false,responsive:true});
if(window.ResizeObserver){new ResizeObserver(function(){Plotly.Plots.resize(el);}).observe(el);}
```
html: `<div class="plot" style="position:relative;height:140px;"></div>` (no `<canvas>` — Plotly owns the div).

**(b) Gauge with target bands** — the same `indicator`, `mode:'gauge+number'`. `steps` paint the
red/amber/green bands, `threshold` draws the target line. This is how a RATE reads at a glance.

```js
gauge:{axis:{range:[0,20],tickwidth:1,tickfont:{size:10}},
  bar:{color:'#47CC29',thickness:0.7},borderwidth:0,
  steps:[{range:[0,8],color:'rgba(224,72,58,.18)'},
         {range:[8,15],color:'rgba(242,187,48,.18)'},
         {range:[15,20],color:'rgba(71,204,41,.18)'}],
  threshold:{line:{color:'#8b1a2b',width:3},thickness:0.9,value:15}}
```

**(c) Combo, dual axis** — bars for the amounts, a LINE for the percentage on a right-hand axis. One chart
that answers "how much" and "how well" together, which two separate charts never do.

```js
datasets:[
 {label:"Gross loss",data:$$('Gross',[0],'Double[]'),backgroundColor:'#e0483a',yAxisID:'y',order:2},
 {label:"Recovered", data:$$('Recovered',[0],'Double[]'),backgroundColor:'#47CC29',yAxisID:'y',order:2},
 {label:"Recovery %",data:$$('Pct',[0],'Double[]'),type:'line',borderColor:'#22a7f0',
  borderWidth:2,tension:0.3,pointRadius:2,yAxisID:'y1',order:1}],
…
scales:{ y:{beginAtZero:true,position:'left'},
         y1:{beginAtZero:true,position:'right',max:100,grid:{drawOnChartArea:false},
             ticks:{callback:function(v){return v+'%';}}} },
interaction:{mode:'index',intersect:false}
```
`order:1` on the line keeps it drawn ON TOP of the bars; `drawOnChartArea:false` stops the second axis
double-printing gridlines.

**(d) Stacked horizontal bar** — "of these, how many were severe?" in one row per category.

```js
options:{indexAxis:'y', scales:{x:{stacked:true,beginAtZero:true,ticks:{precision:0}},
                                y:{stacked:true,grid:{display:false}}}}
```

### 2B.5 The polish checklist — every chart, every time

None of these costs a query. All of them are visible in a screenshot.

- **Theme-aware text.** Never hard-code a label colour: `var fg=getComputedStyle(host).color;` and feed `fg`
  into every `ticks.color`, `title.color` and `legend.labels.color`. Grid lines `rgba(128,128,128,.18)` read
  on all five skins. A chart with black axis text is invisible on the dark theme.
- **Integer ticks on a COUNT.** `ticks:{precision:0}` — otherwise Chart.js prints `0.5 / 1.5 / 2.5` cases.
- **Money formatter on an AMOUNT.** A raw `1250000000` is unreadable:
  ```js
  ticks:{callback:function(v){var a=Math.abs(v);
    if(a>=1e9)return (v/1e9).toFixed(a>=1e10?0:1)+' bn';
    if(a>=1e6)return (v/1e6).toFixed(a>=1e7?0:1)+' mn';
    if(a>=1e3)return Math.round(v/1e3)+' k';return v;}}
  ```
- **Humanise enum labels.** `UNDER_INVESTIGATION` → `Under investigation`. Do it in the tick callback (or the
  legend's `generateLabels`), never by changing the value the click-filter sends:
  `String(this.getLabelForValue(v)).replace(/_/g,' ').toLowerCase().replace(/^./,c=>c.toUpperCase())`
- **Wrap long category labels** to at most two lines so they stop eating the plot area — split on spaces at
  ~16 characters and `return` an array of lines from the tick callback.
- **Semantic colour, consistent across the whole board.** Map the value, do not let the palette cycle:
  `{"CRITICAL":"#8b1a2b","HIGH":"#e0483a","MEDIUM":"#F2BB30","LOW":"#47CC29"}[label] || '#22a7f0'`.
  Red = loss/bad, green = recovered/good, amber = middle, blue = neutral volume. The same status must be the
  same colour in every chart on the page.
- **Legend at the bottom**, `boxWidth:10`, coloured `fg`. A right-hand legend steals width from the plot.
- **Title inside the chart**, `align:'start'` — so the chart names itself even when the card header does not.
- **Click affordance.** With `crossFilter` wired (§5), also set the cursor and a tooltip so the reader
  discovers it: `onHover` → `e.native.target.style.cursor = els.length ? 'pointer' : 'default'`, and
  `this.$find('canvas')[0].title='Click to filter'`.
- **Doughnut, not pie**, `cutout:'58%'` — the hole is where a total can live and it reads less like 1998.
- **A second measure in the tooltip.** `tooltip:{callbacks:{afterLabel:…}}` costs one more column in the same
  query and turns a count chart into two facts.

### 2B.6 COLOUR IS A DECISION, TAKEN BEFORE YOU TYPE A HEX

Two builds of the same brief differ more in colour than in anything else, and colour fails in two independent
ways: it can be **meaningless** (the reader cannot tell bad from good) and it can be **ugly** (the reader can,
but does not want to look). Both are defects. Neither is caught by a gate.

**§6.1 is the reference** — the four palette families, the verified hexes, the measured contrast and
colour-blind separations, the one-entity-one-colour rule. Read it before authoring any chart. What follows is
the part that belongs to the BOARD rather than to a chart: how to decide, and how to keep a page of eight
charts looking composed rather than assembled.

#### The decision, in four questions

Ask them of the AXIS, before writing a single `backgroundColor`. The answer picks the family; §6.1 supplies
the hexes.

| what is the axis? | example | family | ⛔ never |
|---|---|---|---|
| ordered with a **verdict** | severity, RAG, SLA, pass/fail, overdue | **traffic light** — green → amber → red → dark red, mapped BY LABEL | a rotating palette. Two blues for LOW and MEDIUM is a real shipped defect (§6.1) |
| **identity**, no order | branch, channel, department, type | **qualitative** — one distinct hue per value, §6.1's 8-slot order | traffic light. "By document type" in green/amber/red invents a verdict the data does not have |
| ordered **magnitude**, no verdict | age tier, size bucket, funnel stage | **sequential** — one hue, lightness stepped, dark = more | a rainbow. Hue jumps destroy the ordering the ramp exists to show |
| signed around a **real zero** | variance vs target, delta vs last period | **diverging** — two hues, NEUTRAL middle | a hue in the middle, or using it where there is no zero |

⛔ And the fifth question, which decides more than the other four: **is this measure the same measure as on the
chart beside it?** If yes it takes the same colour there. A dashboard is read by following one thing across
cells; loss must be red in every chart on the page, recovered green in every chart on the page.

#### The aesthetic half — restraint is what makes it look designed

Correct colour that is still ugly is still a rejected screen. Six rules, all visible in a screenshot:

1. **Few hues per board, not per chart.** A composed page uses roughly 4-6 hues in total and repeats them with
   intent. A page where every chart introduces its own new colours reads as eight unrelated pictures — which is
   precisely what happens when each chart is authored in isolation and the palette is left to cycle.
2. **One accent, and spend it on the point.** Pick the single colour that means "this is the number that
   matters" (usually the primary measure) and let everything else recede to neutrals and muted tones. A chart
   where all eight bars shout has no focus; a chart where one bar is `#e0483a` and the rest are `#9aa2ad` has
   an argument.
3. **A magnitude bar does not need eight colours.** A ranked "top N by value" is ONE series: paint it one
   colour and let the axis labels identify the rows (§6.1 says the same — a flat tone is right exactly here).
   Multi-colouring a single-series bar is the most common way a board turns into a fruit salad.
4. **Fills are solid; opacity is for area, not for a second series.** `rgba(…,.5)` under a line is right.
   Faking a second category by lightening the first is not — it collapses on the four dark skins and cannot be
   told from the first at a glance.
5. **Match the weight to the mark.** A fill can be mid-toned; a 1px line or a small point needs more contrast
   than a fill does (§6.1 measures this: `#4e79a7` is 2.8:1 on a dark card — fine filled, thin as a line, so
   raise `borderWidth` to 2-3 rather than swapping the colour).
6. **Backgrounds stay out of it.** `paper_bgcolor:'rgba(0,0,0,0)'`, no card fill from the chart, gridlines at
   `rgba(128,128,128,.18)`. Every colour the reader sees should be DATA. A chart that paints its own background
   is the one that turns into a white rectangle on four of the five skins (§6).

#### The two failures that ship most often

- **The default palette.** Writing no `backgroundColor` at all and letting Chart.js cycle its own colours.
  It is fast, it is never semantic, and it changes when the data reorders. If a chart has no explicit colour
  decision in its `js`, that decision has not been made.
- **The index array.** `backgroundColor:['#8b1a2b','#22a7f0','#63bff0',…]` assigns by POSITION, so the mapping
  rides on the query's row order — and a cross-filter dashboard re-runs its queries on every click, repainting
  the survivors each time (§6.1). Map by label, always. `validate` warns on a hex array in a chart's `js` for
  exactly this reason.

### 2B.7 The bar to clear before you call a dashboard done

Answer these against your own screen; each maps to a row of §2B.1:

1. Does the page open with a **title and one sentence** telling the reader what this is and that it filters?
2. Is there a **KPI strip** — at least three tiles, at least one of them a gauge or a rate?
3. Are there **named sections with icons**, or is it an anonymous stack of cards?
4. Do the rows **differ in chart count**, and are the columns inside them **unequal**?
5. Are there **at least four distinct chart shapes** on the board (e.g. indicator, doughnut, horizontal bar,
   combo, stacked)? Six vertical bars is one shape used six times.
6. Is every **count axis integer** and every **amount axis formatted**?
7. Is every label **human** — no `SCREAMING_SNAKE_CASE` anywhere on screen?
7b. Did every chart make a **colour decision** (§2B.6)? No default palette, no index array, the family matching
   the axis's job — and does the same measure carry the same colour in every cell of the board?
8. Does every chart **have enough data to have a shape**? A single bar is a data problem (§2.6), not a chart.
9. Would you put this screenshot in a proposal?

⛔ `validate` sees items 3, 4, 5 and half of 7b (the index-palette array) only, and only roughly. The rest is your eye — which is exactly why the
grid dump passed every gate.

## 3. Params — making a chart query filterable

A chart query becomes filterable by declaring **parameters inside the SQL text** — an inline relaxed-JSON
placeholder, parsed by the query service's placeholder processor into a
`Replacement { name, defaultValue, type, dropDownPopulation }`.

> This is the same placeholder mechanism used by every report query — **full reference in
> [12](12-queries-sources-schedulers-and-rest.md) §1.4 (syntax), §9 (`FieldType` set), §10 (`dropDownPopulation`
> & cascading), §15 (`findControls`/`replaceParams`).** Below is only what a chart author must know.

### 3.1 The inline SQL placeholder DSL

```sql
-- free typed input:
WHERE status = {name: 'Status', type: 'string'}
-- dropdown fed by another named query (the chart/filter-bar flavor):
WHERE team_project = {name: 'Project name', type: 'dropdown-string',
                      dropDownPopulation: {query: 'Projects Query', value: 'name', name: 'name'}}
```

> ### ⛔⛔ The placeholder must be a BARE right-hand operand — never wrap it
>
> Write `<column> <operator> {name: …}` and nothing else. **Do not** put the placeholder inside `COALESCE(…)`,
> `CAST(… AS …)`, a function call or extra parentheses — the query will parse fine while a filter value is set
> and blow up the moment the filter is empty.
>
> Why: an empty filter does not substitute a value, it **neutralises the whole predicate to `1=1`**:
> the engine walks back to the nearest preceding `WHERE`/`AND`/`OR`/
> `HAVING`/`ON`, sets that token to `1=1`, and then **blanks every token from there up to the placeholder**.
> Anything you wrote AFTER the placeholder survives and is left dangling:
>
> ```sql
> -- authored (looks reasonable, is fatal):
> AND d.doc_date >= COALESCE(CAST({name:'From', type:'date'} AS date), DATE '0001-01-01')
> -- what the engine ships when 'From' is empty:
> AND 1=1 AS date ) , DATE '0001-01-01' )        -->  ERROR: syntax error at or near "AS"
> ```
>
> So you never need your own null-handling: `AND col >= {name:'From', type:'date'}` already means "no filter →
> show all". LIVE-FOUND 2026-08-08 — every chart on the page rendered an error toast, and nothing offline
> caught it because the authored SQL is valid SQL; only the SUBSTITUTED form is broken. When you must check a
> chart query offline, substitute BOTH states by hand (the `1=1` rewrite and a literal value) and parse each.
>
> `validate` now performs the first half of that for you: it applies the `1=1` rewrite to every CHART query
> (the rep-object AND the copy embedded in the chart's model, which is the one the page runs) and ERRORs when
> the neutralised form stops being balanced, or when a placeholder stands on the LEFT of a comparison. It is
> scoped to charts on purpose — an autocomplete or picker query is wrapped the same way deliberately and always
> has a value, and the platform's own baseline ships three of them.
>
> ⚠️ **The gap in that gate:** it does not read a placeholder that carries a nested map, which is exactly the
> `{name:'Year', type:'dropdown-string', dropDownPopulation:{…}}` shape recommended just above. Widening it was
> tried and reverted — the keyword scan standing in for the engine's AST walk then anchors too far back on
> queries that put a placeholder inside a select-list function call, and the platform's own demo charts do that,
> so every project went red on baseline content. Check the dropdown form by eye against the same rule: bare
> right-hand operand, nothing wrapped around it.
>
> ### ⛔ For a filter-bar param, use `dropdown-string`. A scalar `date` param does NOT substitute.
>
> `setVal` only renders a **Number** (bare) or a **String** (quoted) — anything else returns null. A date
> control's value does not arrive as a String: the `val instanceof Map` branch handles it, and that branch
> substitutes **only** when the map carries `firstValue`/`lastValue` AND the SQL predicate uses `BETWEEN`
> (`type:'date-range'`). Any other date shape silently falls through and the RAND sentinel is shipped to the
> database verbatim:
>
> ```
> ERROR: column "gdgowxebwdtgyjlqevlkw1" does not exist
> ```
>
> and the bar itself then renders "Invalid date" once a value has been stored. In practice **the only param type
> that appears in a working chart filter is `dropdown-string`** — there is no working scalar-date filter. So express a period filter as a dropdown over a lookup query
> (`AND to_char(<col>, 'YYYY') = {name:'Year', type:'dropdown-string', dropDownPopulation:{…}}`), or leave the
> period out. LIVE-FOUND 2026-08-08/09.
>
> Note also that a value the user picked is **persisted into the chart node**, so a bad
> stored value survives a page reload — re-importing the project (which replaces the node) is what clears it.

- `name` — the parameter's name (**this is the string that ties everything together — see §4.2**).
- `type` — a `FieldType` ([12](12-queries-sources-schedulers-and-rest.md) §9): typed inputs
  (`string`, `number`, `date`, `date-range`, `time`, `datetime`, `datetime-range`, `checkbox` (alias `boolean`);
  full set in [12](12-queries-sources-schedulers-and-rest.md) §9) or a **`dropdown-*`** form (`dropdown-string`,
  `dropdown-instant`). There is **no** bare `instant` type — unknown/typo type strings silently fall back to a
  plain string control.
- `dropDownPopulation: {query, value, name}` — makes the filter a dropdown: run the query **named** `query`
  (resolved by name at runtime — it must also exist in the project), use column `value` as the option value and
  `name` as its label. Cascading dropdowns = pass one param's value into the next dropdown's query
  ([12](12-queries-sources-schedulers-and-rest.md) §10).

### 3.2 The `parameters` map (a seed value, not the declaration)

The query's top-level `parameters` map does **not** declare params (the SQL text does). It only holds a
**current/preview value** per param, keyed by name:

```jsonc
"parameters": { "Project name": { "value": "<the current preview value>" } }
```

This map is populated **only on the query copy embedded in a chart replacement** (never on the
standalone `rep-objects.json` query — `query add` always writes `{}`). It renders the chart's default filter
state; live values live in the session and are persisted back into the chart node when the user filters.
`QueryDto.Parameter` = `{ "value": <Object> }`.

---

## 4. Filtering-through-params (the filter bar)

### 4.1 `global.replacement.plugin` — the filter bar node

One node per dashboard page. It stores **no config at all** — only the empty `className/styleName/tagProperties`
boilerplate, `children: []`. It builds its filter controls **at runtime** from the parameters of the charts'
`QUERY` replacements on the same page.

```jsonc
{ "pluginName": "global.replacement.plugin", "name": "Global replacements",
  "children": [],
  "properties": { "className": {…""}, "styleName": {…""}, "tagProperties": {…""} } }  // no Javascript/model/settings
```

How it works:
- Each chart, on init, fires an `addFieldsToParametersPanel` event carrying the query of every **`QUERY`**
  replacement. The filter bar's `ParamsPanel` listens, asks the query service for that query's field controls
  (which parses the SQL placeholders), and renders one input per distinct param (dropdown for `dropdown-*`,
  typed input otherwise).
- On **submit**, it fires the page-wide `parametersOfQueryHasBeenChanged(changedQueries)` event.
- It is also the sink for **click-to-cross-filter** (§5).

> 🔧 **Tooling.** `node add --plugin global.replacement.plugin --parent <page/parsis>` creates it; it is in
> `NO_CONFIG_SLOT_PLUGINS`, so passing `--model`/`--settings` is **rejected**. Nothing else to author on it —
> the filtering is entirely emergent from the charts' query params. It **must be on the same Wicket page** as
> the charts (the event bus is page-scoped), or there is no filter UI and cross-filter has no target.

### 4.2 The contract — one string in five places

Filtering works because the platform matches a **parameter name** across five independent places. Pick a name
`<P>` (e.g. `Project name`) and use it **identically** in all of them:

| Where | The string | Who reads it |
|---|---|---|
| SQL placeholder | `{name: '<P>', …}` in the query text | the placeholder processor (declares the param) |
| chart replacement query's seed | `query.parameters["<P>"]` | the same processor (supplies the value at run time) |
| filter-bar control | the control's field name `<P>` (auto-derived — you never type it) | `ParamsPanel` |
| session slot | the per-project param key for `<P>` | `ParamsPanel` (restore across redraws) |
| click-to-cross-filter | `crossFilter('<P>', …)` in chart JS | the chart panel → filter bar |

If two charts declare the **same `<P>`** in their (distinct) queries, they filter **together** from one control.

### 4.3 The re-run event chain

```
filter control edited → ParamsPanel sets param.value on every bound QueryDto (+ writes session)
submit → the filter bar fires  parametersOfQueryHasBeenChanged(changedQueries)
       → each chart: if one of its replacement queries is in the changed set → save the node + refresh
       → the chart re-renders: each QUERY replacement re-runs WITH the new param → new $$() literals
       → the chart redraws with filtered data
```

### 4.4 Shared filters & cascading dropdowns

- **Shared filter across charts** — give each chart's query the same placeholder `name`; one control drives all.
  (The one chart that leaves it out on purpose is the one that `GROUP BY`s that column — §4.6 "The GROUP-BY
  exemption".)
- **Cascading dropdowns** (Country → State → City) — chain `dropDownPopulation`: the selected value of one
  param is passed as a parameter into the next dropdown's lookup query
  ([12](12-queries-sources-schedulers-and-rest.md) §10).

### 4.5 `ParamsPanel` — how the filter controls are actually built (the engine inside the bar)

The filter-bar plugin is a thin shell around **`ParamsPanel`** (the same panel report queries use) — that panel
is what turns the charts' query params into rendered filter inputs and applies user/click selections back onto
the queries. Its lifecycle:

1. **Harvest** — each chart, on init, fires `addFieldsToParametersPanel(query)` for every **QUERY** replacement
   (§4.3). `ParamsPanel` listens and for each query asks the query service for its field controls — the engine
   that parses the SQL `{name:'…', type:'…', dropDownPopulation:{…}}` placeholders into **`FieldControl`**
   objects. It also records, in a `field → [queries]` map, **every** query that declares that field — this is
   how ONE control drives ALL charts sharing the param name (§4.2).
2. **Render one control per distinct `FieldControl`**, chosen by its **`FieldType`**:

   | `FieldType` | Rendered control | Notes |
   |---|---|---|
   | `dropdown-*` (name starts `dropdown`) | `DropDownChoice` | choices from `dropDownPopulation` (§3.1); a null **"— All —"** option (`param.filter.all` bundle) clears the param → **show all** (incl. NULL-column rows). Empty choices → the control is hidden |
   | `STRING` | `TextField` | free text |
   | `INTEGER` `LONG` `SHORT` `DOUBLE` `FLOAT` `BIG_DECIMAL` | `NumberTextField` | `type` attr from `FieldType.getControlType()` |
   | `DATE` | `DatePickerField` | |
   | `DATE_RANGE` | `DateRangePickerField` | a from/to pair → SQL `BETWEEN` (doc 12 §9) |
   | `TIME` | `TimePickerField` | |
   | `DATE_TIME` | `DateTimePickerField` | |
   | `DATE_TIME_RANGE` | `DateTimeRangePickerField` | |
   | `CHECKBOX` (alias `boolean`) | `CheckBox` | |

   Every control gets a **`param-control-name`** attribute = the param name with spaces→`_`.
   That attribute is the hook the JS cross-filter badge reads (`DokieActiveFilters`, §5) to show which fields are
   filtered — so a control and its badge stay in sync regardless of whether the value came from the bar or a click.
3. **On edit** — the control writes the value into **every** bound `QueryDto.parameters[field]`, marks those
   queries changed, and persists the value into the **session** under the per-project param key. On **submit**
   the shell fires page-wide `parametersOfQueryHasBeenChanged(changedQueries)` (§4.3) → every affected chart re-runs.
4. **Session restore** — on (re)render each control seeds its value from that session slot, so a filter survives
   chart refreshes and page redraws; a deliberately-cleared (`— All —`, value `null`) param is **not** snapped
   back to the first choice.

> So: you author **nothing** on the bar. You get a working, typed, multi-chart-linked filter for a param the instant a
> chart's QUERY replacement declares it in SQL with the right `type` (§3.1). Getting the **`type`** right is what
> decides the control (a `dropdown-string` → a dropdown; a bare `date-range` → a from/to picker); a typo `type` falls
> back to a plain text box (doc 12 §9).

### 4.6 Designing the filter SET for a dashboard

The bar is **emergent** (§4.1): it renders exactly the params your charts declare — no more, no fewer. So
"designing the filter bar" is really "deciding which params to declare in which chart's SQL". The rule:

**Pick 2–4 params. Fewer is a poster; more is a form.** The default set for a dashboard over `<Entity>`:

| Slot | Typical `<P>` | The placeholder that goes in every chart's SQL | Why |
|---|---|---|---|
| **period** (always) | `Since` | `AND to_char(<date col>,'YYYY-MM') >= {name: 'Since', type: 'dropdown-string', dropDownPopulation:{…}}` | a **dropdown** — ⛔ a scalar `date` param does not substitute (§3.1), and a frozen dump needs a period control anyway (§2.6 Rule 5) — and a **lower bound**, never `=` (next paragraph) |
| **one entity dimension** | `Owner`, `Type`, `Category` | `AND <col> = {name: 'Owner', type: 'dropdown-string', dropDownPopulation:{…}}` | the axis the viewer already thinks in |
| **status** | `Status` | `AND <status col> = {name: 'Status', type: 'dropdown-string', dropDownPopulation:{…}}` | the lifecycle axis |
| (optional 4th) | the case's second qualitative axis (`Risk`, `Priority`, `Region`) | same shape | only if it clears **≥ 3 distinct values** (§2.6 Rule 2) |

Every param in the set must clear that ≥ 3 threshold, or the control is noise — and when its lookup comes back
empty it is not rendered at all (below).

**⛔ The period param is a LOWER BOUND, not an equality — and its name must say so.** The period is the one filter
that *multiplies* the rest of the set: `<Dim>` × 12 months is `<Dim>`×12 distinct filter states, and a demo-grade
dump carries only a handful of rows per cell — so an `=` period leaves most (dim, month) picks matching nothing,
and the chart draws an empty frame, which reads as broken rather than as "no data" (§2.6). A `>=` accumulates
every period from the picked one onward, so only the newest period is ever as thin as equality was. Measured
2026-08-12 against a live Postgres, one seeded table, 6 dims × 12 months = **72 filter states**, one status
doughnut per state:

| Rows in the seeded table | States returning **0 rows** (`=` → `>=`) | States under the 3-slice minimum of §2.6 (`=` → `>=`) |
|---|---|---|
| 90 | 23 → **4** | 70 → **26** |
| 150 | 9 → **0** | 65 → **19** |
| 240 | 1 → **0** | 51 → **9** |

```sql
-- ⛔ equality: exactly one month. Most picks of the cross-product are empty → blank charts
AND to_char(<date col>,'YYYY-MM') =  {name: 'Period', type: 'dropdown-string', dropDownPopulation:{…}}
-- ✅ lower bound: "everything since this month". Same lookup query, same options, same control
AND to_char(<date col>,'YYYY-MM') >= {name: 'Since',  type: 'dropdown-string', dropDownPopulation:{…}}
```

- **A plain `>=` is enough — `'YYYY-MM'` compares lexicographically.** The format is fixed-width and zero-padded,
  so text order *is* chronological (`'2026-10' >= '2026-09'`, `'2027-01' >= '2026-12'` — both true under the
  default, `C` and ICU collations). No cast, and no `date` type — which would not substitute anyway (§3.1). The
  **lookup query does not change**: it already returns the very strings being compared, and a `dropdown-string`
  value is substituted quoted.
- **⛔ The placeholder is still a BARE right-hand operand.** `>=` changes the operator, not the shape — the
  placeholder stays the last token of its predicate (§3.1). An empty pick still neutralises the whole
  `<expr> >= {…}` predicate to `1=1`: the rewrite walks back to the nearest `WHERE`/`AND`/`OR`/`HAVING`/`ON` and
  never looks at the operator.
- **Name it `Since`, not `Period` — the param name IS the control's label** ("Name the param for a human", below;
  §4.2). Under a `>=`, `Period: 2026-03` is a false caption and `Since: 2026-03` is a true one — and that same
  string is what the click-to-filter pill prints (§5). Keep the one spelling in all five places of §4.2, the
  period selector of the two-selector table below included.

**It also fixes the click (§5).** Under equality, clicking a month on the trend chart narrows every other chart on
the page to that single month — the thinnest cell in the whole cross-product, and the first click a reviewer
makes. Under a lower bound the same click reads as *"since that month"*, which is what a viewer expects a timeline
click to do, and the neighbouring charts keep their marks.

> ✅ **The check — measure the THINNEST cell of the filter cross-product before you ship the set.** One row per
> state the bar can produce; read the bottom of the list:
> ```sql
> SELECT d.dim, p.period,
>        (SELECT count(*) FROM <schema>.<entity> e
>          WHERE e.<dim col> = d.dim AND to_char(e.<date col>,'YYYY-MM') >= p.period) AS rows_in_state
> FROM       (SELECT DISTINCT <dim col> AS dim FROM <schema>.<entity>) d
> CROSS JOIN (SELECT DISTINCT to_char(<date col>,'YYYY-MM') AS period FROM <schema>.<entity>) p
> ORDER BY rows_in_state ASC LIMIT 5;   -- swap >= for = to see what an equality filter would have shipped
> ```
> One more factor per further param in the set. Compare the thinnest state against the per-form minimums in §2.6
> ("The data a chart needs"): below them the fix is in the **data** (seed more rows) or in the **set** (drop a
> param) — never in the chart JS. `>=` degenerates to `=` at the newest period, so that state is always the
> thinnest: read it first. Not machine-checkable — `validate` never runs your SQL (Gotcha 10).

> ⛔ **The silent partial-coverage trap — declare the SAME `<P>` in EVERY chart's SQL on the page.** `ParamsPanel`
> builds its `field → [queries]` map out of what the charts *harvested* (§4.5 step 1) and pushes an edited value
> into exactly those queries. A chart whose SQL does not declare `<P>` is simply **not in that list**: it never
> re-runs, it keeps showing whole-dataset numbers while its neighbours filter, and **nothing reports it** — no
> toast, no log, no `validate` check (validate only collects the page-wide *union* of declared params, Gotcha 10).
> The page quietly contradicts itself, and the contradiction is the number a viewer will act on. Only three
> outcomes are legal:
> 1. every `QUERY` replacement on the page declares `<P>`; or
> 2. a chart genuinely cannot (its source has no such column) — then **say so in that chart's own title**
>    ("… — all periods"), because the title is the only place a viewer can learn it; or
> 3. the chart **groups by** `<P>`'s column — then it must **not** declare it (the GROUP-BY exemption, next).
>
> Checkable by hand: for each `<P>`, count the distinct embedded query texts on the page containing
> `{name: '<P>'` and compare with the number of `QUERY` replacements on that page.

**The GROUP-BY exemption — the chart you filter FROM must not filter on itself.** A chart that `GROUP BY`s a
dimension must **not** declare that dimension as one of its own params; its omission is deliberate, not the
coverage hole above. The mechanics leave no choice: `ParamsPanel` harvests every chart's query into the
`field → [queries]` map (§4.5 step 1) — the harvesting chart's own query included — and a pick, from the bar or
from a click, fans the value into **every** query in that list (`applyFilterFromChart`, §5.2 step 2), after which
each chart holding a changed replacement query re-runs and redraws (§4.3). So a selector that declared `<P>`
would come back as `WHERE <col> = '<picked>' GROUP BY <col>`: exactly one group — a doughnut that is one solid
ring, a bar chart with one bar — and the only way back is clicking that single surviving mark again (the toggle,
§5.2 step 1). The selector therefore **omits that one `<P>`, declares every other param in the set, and carries
the `crossFilter('<P>', …)` handler** (§5); the viewer reads the current selection off the automatic
`Field: Value` pill, not off the chart shrinking. Take any two params of the set above — a `<Dim>` and `Period` —
and it gives the **two-selector** pattern:

| Chart | `GROUP BY` | Declares | Click handler |
|---|---|---|---|
| "Mix by `<Dim>`" — the **`<Dim>` selector** | `<dim col>` | `Period` only | `crossFilter('<Dim>', …)` |
| "Trend by period" — the **`Period` selector** | the period expression | `<Dim>` only | `crossFilter('Period', …)` |
| every other chart on the page | anything else | **`<Dim>` and `Period`** | — |

(The floor is **one** click-to-filter chart — the requirement box below, and the one Recipe E step 6 wires. A
two-selector page has two, and "two" means two charts on two params: never two `crossFilter` calls in one
handler, which is two round-trips racing each other, §5.)

Checkable by hand: for each chart, take its `GROUP BY` column and search that same query text for a `{name: …}`
placeholder on that column. A hit is the collapse bug — most of all when the chart also carries
`crossFilter('<P>', …)`, which is precisely the selector deleting itself on first click (§2A.2 check 5).

**Name the param for a human — the name IS the control's label.** The caption is rendered from the parameter name
verbatim (§4.2, §4.5): there is no separate `label` field, no message key, no localization. So write
`{name: 'Owner'}`, never `{name: 'owner_id'}` or `{name: 'p1'}` — and keep that exact spelling in every chart's
SQL, in `crossFilter('<P>', …)` (§5) and in any `parameters` seed (§3.2). The same string is what the
click-to-filter badge shows as `Field: Value`, and what `param-control-name` is derived from (spaces → `_`).

**Every dropdown param needs a lookup query that exists BY NAME.** `dropDownPopulation.query` is resolved by a
by-name lookup (case-insensitive, otherwise exact — spaces count), the query is executed, and its rows are mapped
`value` → option value, `name` → option label **by result-column name**. Recipe B hand-waves this; the shape is:

```sql
-- saved query NAME: "Owner Lookup"      ← exactly the string in dropDownPopulation.query
SELECT DISTINCT owner AS value, owner AS name    -- value and name MAY be the same column
FROM <schema>.<entity>
WHERE owner IS NOT NULL
ORDER BY 1
```
```sql
-- better when the axis has a dimension table: stable labels + a deliberate order
SELECT code AS value, label AS name
FROM <schema>.dim_status
WHERE is_active
ORDER BY sort_order
```
Create it exactly like any other query: `query add --name "Owner Lookup" --source <source> --sql @owner-lookup.sql`.
⚠️ The option **values** must be the values the filtered column actually stores (`code` here, not `label`) — the
placeholder compares them literally.

Four ways this fails, and all four make the control **vanish** rather than raise an error you cannot miss:

- **`type:'dropdown-*'` with no `dropDownPopulation` at all** — there are no choices to build, so no control;
- **the alias does not match** — Postgres folds unquoted identifiers to lower case, so `… AS Value` is the column
  `value`, and `dropDownPopulation:{value:'Value'}` matches nothing (the same trap as Gotcha 2 for `columnName`).
  The mapping then fails, is swallowed, and the choices come back empty;
- **empty choices → no control** — a lookup returning zero rows (or whose columns did not match) makes
  `ParamsPanel` drop that field: the bar renders one filter fewer, silently (§4.5);
- **a name that resolves to no query** fails the whole field-control fetch for that chart's query — an
  *"Error occurred on params panel"* toast, and **none** of that query's params get a control.

So after import, **count the controls in the rendered bar against the params you declared**; a mismatch is one of
the four above.

**A filter bar with no declared params renders nothing usable.** The node carries no config (§4.1) — adding it is
not what makes a page filterable, declaring the params is. With zero params it draws an empty strip with a bare
submit button; `validate` warns on exactly this (an inert bar, Gotcha 10).

> ⛔ **REQUIREMENT — a dashboard page is not finished until it has BOTH a working filter bar and at least one
> click-to-filter chart.** A page of static charts is a picture of the data; the interaction is what makes it a
> tool, and it is the first thing a reviewer tries. Before you call a dashboard done:
> 1. a `global.replacement.plugin` node on the page **rendering ≥ 2 controls** — rendering, not merely declared
>    (an empty lookup deletes a control without telling you);
> 2. changing one control moves **every** chart on the page — except the one that groups by that control's own
>    column, which is *supposed* to stay put (the partial-coverage trap and the GROUP-BY exemption above); a
>    second chart that ignores the control is the trap, not the exemption;
> 3. **at least one** chart wired with `this.crossFilter('<P>', …)` and its pointer/hint affordance (§5), on a
>    `<P>` the bar also exposes — and clicking the same mark again clears it.
>
> None of the three is machine-checkable: `validate` can see that a bar exists and that a `crossFilter` field is
> declared *somewhere* on the page, never that a control rendered or that a click filtered anything. This is a
> **review rule** — open the page and do all three by hand.

---

## 5. Click-to-cross-filter

Clicking a bar/point makes the whole page filter on the clicked value — it just injects a value into the
ordinary filter bar (no parallel mechanism).

**Chain** (the editor's click-filter constructor → JS `crossFilter` → server → filter bar):
1. The chart's `js` gets an engine-aware onClick appended (generated by the constructor, or hand-written):
   - **Chart.js:** `cfg.options.onClick = function(e, els){ if(els&&els.length){ this.crossFilter('<P>', this.chart.data.labels[els[0].index]); } else { this.crossFilter('<P>', null); } }.bind(this); this.chart.update();`
   - **Plotly:** bind `plotly_click` → `this.crossFilter('<P>', p.x != null ? p.x : p.label)`.
2. `crossFilter(field, value)` posts `{field, value}` to the server (and drives the top-of-page progress bar
   until the response lands).
3. The chart panel re-broadcasts it as the page-wide `applyChartFilter` event.
4. The filter bar listens for `applyChartFilter` → `ParamsPanel.applyFilterFromChart(field, value)` sets param
   `<P>` on **every page query declaring `<P>`**, writes the session slot, then fires
   `parametersOfQueryHasBeenChanged` → §4.3 → all matching charts refresh **in the same round-trip**.

**Toggle/clear:** clicking the same value again (or an empty area → `value = null`) clears the filter. `<P>`
in the snippet is the same parameter name as in the SQL placeholder (§4.2).

> ### ⛔ Chart.js: attach handlers to the CONFIG, not to `chart.options`
>
> ```js
> this.chart = new Chart(ctx, cfg);
> this.chart.options.onClick = function (e, els) { … };   // ⛔ writes into a resolved proxy
> this.chart.update();
> ```
>
> `chart.options` is **not a plain object** — it is the resolved, context-attached option proxy that
> Chart.js builds from the config, the type overrides and the defaults. Reading a key on it runs the
> scriptable-option resolver; writing one puts your value inside a structure whose lifetime and
> identity Chart.js owns. `Config` deliberately exposes the raw object separately
> (`get options() { return this._config.options; }`), which is the supported place to write.
>
> Author it into the config before the chart exists:
>
> ```js
> cfg.options = cfg.options || {};
> cfg.options.onClick = function (e, els) { … }.bind(this);
> cfg.options.onHover = function (e, els) { … };
> var ctx = this.$find('canvas')[0].getContext('2d');
> this.chart = new Chart(ctx, cfg);          // ← construct LAST
> ```
>
> and if you genuinely must add one AFTER construction (a snippet appended to somebody else's JS, where
> `cfg` is out of scope), use the raw config and let `update()` rebuild the resolver:
>
> ```js
> this.chart.config.options.onClick = function (e, els) { … }.bind(this);
> this.chart.update();                       // Config.update() → clearCache()
> ```
>
> ECharts and Plotly are unaffected — they take listeners through `ec.on(...)` / `plotly_click`, which
> is a subscription rather than an option write.
>
> ### Why this matters — the failure it actually produces
>
> A live dashboard threw this on legend-toggle and on hover, while the chart itself rendered and
> cross-filtered perfectly:
>
> ```
> Uncaught Error: Recursion detected: callback->callback
> Uncaught Error: Recursion detected: _scriptable->_scriptable
> TypeError: t.startsWith is not a function          ← inside Chart.js's OWN descriptor
>     … clone → mergeIf → Config.update → chart.update → _updateVisibility → legend onClick
> ```
>
> The chain, read out of the shipped v3.9.1 bundle:
>
> 1. `Chart` declares `get options(){return this._options}` — the RESOLVED, context-attached proxy —
>    and `set options(t){this.config.options=t}` — which writes into the RAW config.
> 2. So `chart.options = chart.options || {}` (a line that reads like a harmless guard) stores the
>    PROXY as the raw config's options.
> 3. The next `chart.update()` — which is exactly what toggling a legend entry does — runs
>    `Config.update()`, which rebuilds the scale config by cloning and merging the defaults into
>    `config.options`.
> 4. `clone()` walks the proxy. Its `get` resolves `callback` (a real function in the tick defaults)
>    and `_scriptable` (Chart.js's own descriptor) as if they were scriptable options, and each
>    resolution re-reads the same key. Chart.js detects the cycle and throws.
>
> Note the shape of the evidence, because it is what made this hard to find: the chart RENDERS, the
> click-filter WORKS, and only interaction that triggers an update dies. It looked like a data problem
> for hours. The discriminator that cracked it was the user's own observation — "the same thing works on
> another chart" — because in that project the poisoning line sat behind a `.crossFilter(` test, so only
> cross-filtering charts were affected. **If a chart works until you touch it, suspect a write into
> `chart.options`, not the data.** (LIVE-FOUND 2026-08-15, in platform code, not in an export.)
>
> `mrjun.py validate` reports a post-construction write to `this.chart.options.*` in authored chart JS.
> It stays a WARNING rather than an error: the *assignment of the whole object* is what poisons the
> config, and setting a single key is a lesser sin with a known-good alternative.

**The click SHAPE per engine — where the clicked value comes from.** Every variant ends in the same one-line
call `this.crossFilter('<P>', <value>)`; only the way you read the value out of the event differs. Chart.js
hands the handler an array of `{element, datasetIndex, index}` (that literal triple is what the bundled
`chart.min.js` v3.9.1 hit-tester pushes), so **`index` addresses `data.labels`** and **`datasetIndex` addresses
`data.datasets`**:

```js
// (a) bar / line / scatter with ONE dataset — the value is the category label
cfg.options.onClick = function (e, els) {
  this.crossFilter('<P>', (els && els.length) ? this.chart.data.labels[els[0].index] : null);
}.bind(this);

// (b) doughnut / pie — a SLICE is the same shape: an index into data.labels.
//     Clicking the hole or outside the ring gives els.length === 0 → null → clears (§5.2).
cfg.options.onClick = function (e, els) {
  this.crossFilter('<P>', (els && els.length) ? this.chart.data.labels[els[0].index] : null);
}.bind(this);

// (c) grouped / stacked bar — TWO axes sit under the pointer; filter on exactly ONE of them:
//       category (x) → this.chart.data.labels[els[0].index]
//       series        → this.chart.data.datasets[els[0].datasetIndex].label   ← the legend entry
cfg.options.onClick = function (e, els) {
  if (!els || !els.length) { this.crossFilter('<Series P>', null); return; }   // empty area → clear
  this.crossFilter('<Series P>', this.chart.data.datasets[els[0].datasetIndex].label);
}.bind(this);

// (d) ECharts (5.6.0, loaded by the plugin — §2.5): the event object carries the value ready-made.
//     Keep the instance in a LOCAL var — never this.chart (§2.5: echarts has no .destroy()).
var el = this.$find('div')[0];
var ec = echarts.init(el);
ec.setOption(option);
ec.on('click', function (p) {                  // p = {componentType, seriesName, name, dataIndex, value, …}
  this.crossFilter('<P>', p.name != null ? p.name : p.seriesName);   // p.name = category, p.seriesName = series
}.bind(this));
ec.on('mouseover', function () { el.style.cursor = 'pointer'; });    // no automatic cursor on this engine
ec.on('mouseout',  function () { el.style.cursor = ''; });
window.addEventListener('resize', function () { ec.resize(); });
```

For **(c)** the dataset `label` is the string the legend shows, so it must be the **raw DB value** of the series
column, exactly as for labels (⚠ box in §5.2) — a localized legend and a `WHERE <col> = {name:'<Series P>'}`
never meet. **One click sets ONE param:** two `crossFilter` calls in one handler are two round-trips racing
each other, and the second one re-renders on top of the first — if the reader must slice on both axes, declare
both params and let the second one come from the filter bar (§4.6). For **(d)**, ECharts gets the automatic
pill but **no** automatic cursor (§5 box above), which is why the `mouseover`/`mouseout` pair is part of the
snippet rather than optional.

> **The "Click to filter" affordance is AUTOMATIC.** You do **not** author the badge or cursor: after the rendered
> `js` runs, the panel scans that rendered text for `.crossFilter(`, reads the field name out of the first
> single-quoted argument, and injects a small **"Click to filter" pill** into the chart's container. The pill is
> injected **for every engine** (Chart.js, Plotly, ECharts, Mermaid, hand-rolled markup — when it recognises no
> canvas/plot div it falls back to the component root); the **pointer cursor + native tooltip** are added for
> **Chart.js and Plotly only**. When that field is currently filtered (from a click OR the bar), the pill also shows
> a **clear (×)** button and reads `Field: Value`; `window.DokieActiveFilters` keeps every badge's state in sync on
> any filter change (it reads the bar's `param-control-name` controls). The pill's text comes from the
> `chart.clickfilter.hint` / `chart.clickfilter.clear` message keys, so **it** is localized even though the chart's
> own text is not (Gotcha 16). Two authoring consequences: the field name must be written with **single quotes**
> (`this.crossFilter('<P>', …)`) or the badge shows no field, and a chart on a non-Chart.js/Plotly engine gets the
> pill but no cursor change — author the cursor yourself (next box).

> ⛔ **REQUIREMENT — for a click-to-filter chart, AUTHOR the pointer cursor + "Click to filter" hint IN THE CHART JS;
> do not rely only on the automatic pill.** The auto-affordance above can be invisible in practice (theme contrast,
> panel state, a custom `onClick` the scanner doesn't match), and a chart that filters on click but gives **no
> hover/pointer cue looks un-clickable** — users never discover the interaction. So any chart wired with
> `this.crossFilter(…)` MUST also, in its own `js`, (a) turn the cursor into a **pointer** while hovering a clickable
> mark, and (b) surface a **"Click to filter"** tooltip/title:
>
> ```js
> // Chart.js — pointer over clickable marks + a native "Click to filter" tooltip on the canvas
> config.options.onHover = function (e, els) {
>   if (e && e.native) e.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
> };
> // after new Chart(...):
> this.$find('canvas')[0].title = 'Click to filter';
> // Plotly equivalent: layout.hovermode='closest'; el.title='Click to filter';
> //   el.on('plotly_hover',function(){el.style.cursor='pointer';}); el.on('plotly_unhover',function(){el.style.cursor='';});
> ```
>
> Keep it localized where the project is multilingual (reuse the same `Click to filter` string per locale as the rest
> of the UI). This is belt-and-suspenders with the automatic pill — author it so the cue is guaranteed.

### 5.1 Drill-down (`futureReplacements` → `showFutureQuery`) — an AUTHOR-TIME builder, not a viewer feature

> ⛔ **Read this before you wire `showFutureQuery` into a chart a business user will click.** `showFutureQuery`
> does **not** redraw the chart in place. Clicking it **opens the chart EDITOR in a modal** — the same 95 % editor
> from §8, configured to show only the **Replacements** (and **Css**) tab with the replacements **read-only** —
> and inside that modal the platform appends a drill step for the value you clicked and runs it, showing the rows
> in the editor's results panel. It is a **drill-chain construction tool for the author**, not an end-user
> drill-down. For an end-user "click a bar to go deeper" experience use **cross-filter** (§5, which re-runs every
> chart on the page with the clicked value as a param) or a normal navigation link to a detail screen.

How the chain is actually built, so you can recognise the shape in an export:

- The chart `js` calls **`this.showFutureQuery(label)`** on a mark click; the label is posted to the server, which
  opens the editor modal and hands the label to the replacement's query-configuration panel.
- That panel appends a **new step** to the current replacement's `futureReplacements[]`, sets
  `currentFutureRepNumber` to it, and re-runs the query so the author sees the drilled rows. The step is a
  **clone of the replacement** whose SQL has been wrapped:
  `select * from (<the replacement's SQL>) qw where qw.<aggregated column> = '<clicked label>'`, with its
  aggregations cleared and `columnName` reset. The wrap only happens when the replacement's query declares an
  **aggregation whose alias matches the group-by column**; without that, the step is created but the SQL is
  unchanged (the "drill" filters nothing).
- ⛔ **The drill path requires the replacement's query to declare at least one `Group by`** — the platform reads
  the FIRST group-by entry to decide the drill column, so a replacement with an empty `groupByList` cannot serve
  a `showFutureQuery` click.
- The author's own entry point is the **Replacements → Query configuration → Group by** row: each group-by row has
  a *create future query* action that asks for a value and appends the same kind of step. The **Future
  replacements** strip next to it is a **step chooser** (breadcrumbs over the steps already built, plus remove-last
  / back-to-root) — it does not create steps, and it is hidden while `futureReplacements[]` is empty.
- Each entry in `futureReplacements[]` has the **same shape** as the parent replacement (`name/type/
  replaceStrategy/query/columnName/…`). `[]` (the default, and what a chart normally ships) = no drill.
- **Offline caveat:** `validate` does not exercise any of this. Given the mechanics above, hand-authoring a
  `futureReplacements` chain is not recommended; build "category → subcategory → detail" as **two screens** (or a
  cross-filtered dashboard) rather than a drill chain.

### 5.2 The server side of a click — `applyFilterFromChart` (toggle · fan-out · sync)

When the chart's `onClick` calls `this.crossFilter(field, value)`, the value round-trips to
`ParamsPanel.applyFilterFromChart(field, value)` (via the `applyChartFilter` event, §5 step 4). What it
does, exactly:

1. **Toggle** — reads the current session value for `field`; `newVal = (value blank OR value == current) ? null :
   value`. So clicking the **same** slice again, or clicking empty space (`value=null`), **clears** the filter.
2. **Fan-out** — for **every** query registered under `field` in `fieldQueryDtoMap` (i.e. every chart whose SQL
   declares `{name:'field'}`), it sets `query.parameters[field].value = newVal` and collects the ones that actually
   changed. This is why one click filters **all** charts that share the param name.
3. **Persist + re-run** — writes the session slot `paramKey(field)`, returns the changed queries →
   `GlobalReplacementPlugin` fires `parametersOfQueryHasBeenChanged(changed)` (§4.3) → each affected chart re-runs its
   query with the new param and redraws; then `refreshFromChart()` re-renders the bar so the dropdown reflects the
   click, and `DokieActiveFilters.refresh()` (JS) updates every badge's `Field: Value` / clear-(×) state.

> ⚠️ **The clicked VALUE must equal the DB value the param filters on.** `crossFilter('status', label)` sends the
> chart **label** (e.g. `this.chart.data.labels[i]`) as the value; the query does `WHERE status = {name:'status'}`, so
> the label must be the **actual `status` column value** (`'REGISTERED'`), not a localized/display string. If your
> chart shows localized labels, either filter on the raw value (keep labels raw) or the click won't match any row. And
> `field` must be a param some chart on the page **declares** (`{name:'field'}`) — otherwise the click is a no-op
> (`validate` warns, doc note in §4.1). This label↔column-value identity is the single most common reason a
> cross-filter "does nothing".

### 5.3 Click to drill to another PAGE (when cross-filter is not enough)

§5.1 tells you to build "category → subcategory → detail" as **two screens**. This is how the second screen gets
reached from a click — and what the platform does and does not give you for it.

**What a chart's JS can ask the SERVER to do — the complete list.** The chart panel's constructor registers
exactly **two** ajax handlers — `showFutureQuery` and `crossFilter` (two `AjaxEventListener`s in `ChartJsPanel`,
and nothing else). A `this.ajax({handler:'…'})` under any **other** name still reaches the server, finds no entry
in that component's listener map, and is **dropped with a server-side
`log.warn("No handler for event <name> in component …")`** — no browser error, no toast, no visible effect (the
ajax-post callback in `ResourceUtils`). And author JS **cannot register a handler**: that map is built in Java
when the panel is constructed, so nothing you write in `js` can add one.

⇒ **There is no navigation API. Drilling to another page is ordinary client-side navigation from the chart's own
`onClick`** — `window.location.href = …`. The rest of this section is about getting the URL and the value right.

**How a content-page URL is formed.** `/<realm>/<alias>/<content-alias path>` ([21](21-homepage-and-redirect.md),
[01](01-content-model-and-pages.md)), where the alias path is the chain of `alias`es from the root's **children**
down to the page — the root's own alias is not in it, because matching starts at the root's children
(`ContentDbServiceImpl.getContentDomain`). It is the same string `Redirect` takes.

> ⛔ **Never hardcode the `/<realm>/<alias>` prefix into chart JS.** It is not a constant: it is added only when
> the request arrived on the platform's main project URL — on a custom domain `MrjunCmsViewUtil.retrieveAlias`
> returns `""` and the pages live at `/<content-alias path>` (the mirror-image strip in
> `ContentDbServiceImpl.findPageContent` is conditional on the same comparison) — and it is **one** segment, not
> two, when the tenant's `alias` equals its `realmName` (`PluginPage`, which passes 1 instead of 2 prefix segments
> for that case). A pasted absolute URL works on your machine and 404s after the first domain change. Derive it
> from the page you are already on:
>
> ```js
> var here = window.location.pathname.replace(/\/+$/, '');       // <prefix>/<this page's alias path>
> // sibling page (both top-level, the common case): swap the last segment
> window.location.href = here.replace(/[^/]+$/, '<target-alias>');
> // nested target: cut this page's OWN alias path off the end, keep whatever prefix remains
> var prefix = here.slice(0, here.length - '<this page alias path>'.length).replace(/\/+$/, '');
> window.location.href = prefix + '/<target alias path>';
> ```
> Both alias paths are strings you already know at build time — `mrjun.py tree` lists every page as
> `Name (alias=…)`, nested, and the path is that chain of aliases read from the root's children down.

**Carrying the clicked value across.** Three routes, only the first of which needs no code on the target page:

1. ✅ **The session param slot — the supported carrier, and it is what makes a drill land pre-filtered.** A
   cross-filter click does not only touch the current page: `ParamsPanel.applyFilterFromChart` writes the value
   into the report session under the per-project param key (`NctParamUtils.paramKey(field, project)`), and
   **every chart seeds each of its query params from that same slot when it initialises**
   (`ChartJsPanel.onInitialize`). So a chart on **another page** whose SQL declares the **same `<P>`** comes up
   already filtered by the click. The drill is therefore "filter, then navigate":
   ```js
   cfg.options.onClick = function (e, els) {
     if (!els || !els.length) { return; }                       // ignore empty-area clicks on a drill chart
     var v = String(this.chart.data.labels[els[0].index]);
     var here = window.location.pathname.replace(/\/+$/, '');
     this.ajax({ handler: 'crossFilter',                        // the SAME handler this.crossFilter() posts to
                 data: { field: '<P>', value: v },
                 callback: function () { window.location.href = here.replace(/[^/]+$/, '<target-alias>'); } });
   }.bind(this);
   cfg.options.onHover = function (e, els) {             // ⛔ still required — see the box in §5
     if (e && e.native) e.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
   };
   this.chart.update();
   this.$find('canvas')[0].title = 'Open the detail list';
   ```
   The handler is posted by hand because the panel's own `crossFilter(field, value)` helper installs **its own**
   callback and takes none of yours. Three consequences to accept before you ship this:
   - ⚠️ the callback is invoked by the **server's** response (it appends `window.<obj>.<method>(…)`, guarded by an
     existence check), so if that response re-renders this very chart the method can already be gone: you get a
     `console.debug` and a filtered page that never navigates. **Test the click, don't assume it.**
   - ⚠️ **toggle still applies** (§5.2): clicking the value that is already the active filter **clears** it, so
     the target page opens unfiltered. A drill chart should therefore be a chart the reader does not use as the
     page's own filter — or accept the second-click behaviour and say so in the title.
   - the automatic "Click to filter" pill and cursor are **not** installed for this form — the panel scans the
     rendered `js` for the literal `.crossFilter(` (§5), and `validate`'s field check greps the same literal, so
     neither the pill nor the lint sees it. Author the cursor + title yourself, as above.
2. ⛔ **A query string you invent is read by nobody.** `?<P>=<value>` does **not** preset a chart filter: neither
   `ParamsPanel` nor any chart class ever touches `PageParameters` (no `PageParameters`/`ParameterUtils` reference
   exists in either). The platform's own page-to-page hand-offs use **fixed** names its own plugins are built to
   read — `group`, `settingsName`, `caller`, `actionId`, `crudId` ([04](04-crud-table-plugin.md),
   [06](06-form-groups-and-mapping.md)). A name of your own only works if a plugin on the target page reads it.
3. Trailing path segments (`aliasParams`) are collected for a page that declares `aliasParamsMaxCount`
   ([01](01-content-model-and-pages.md) "`siteMapPage` properties") — the platform keeps the unmatched tail
   instead of 404-ing (`ContentDbServiceImpl.findPageContent`) — but **consuming** them is again up to the target
   page's plugin. Not a chart mechanism; do not build a drill on it.

**Not supported — do not attempt.** A runtime drill-down via `futureReplacements`/`showFutureQuery`: that opens
the **author's** editor modal, not a viewer drill (§5.1). Registering any new ajax handler from author JS (the
two above are the whole set). Re-pointing a chart at a different query at runtime — the replacement set is fixed
on the node, and the only thing a click can change is a **param value**.

**Drill to a page, or cross-filter?**

| The reader's next question | Do | Why |
|---|---|---|
| "how does the **rest of this page** look for X?" | **cross-filter** | same grain, one round-trip, reversible by clicking again |
| "show me the **rows** behind X" | **drill** | a detail list is a different grain — and a table does not belong on a chart page ([21](21-homepage-and-redirect.md) "Home-as-dashboard", `validate` WARNs) |
| "I need different columns / actions / a form" | **drill** | the target needs plugins a dashboard cell cannot host |
| "X is one of 4–8 known categories the reader will hop between" | **cross-filter** | toggling is free; a page hop per category is not |
| the value is only meaningful **with** its siblings (share of total) | **cross-filter** | the drill throws away the comparison |

Rule of thumb: **cross-filter changes the FILTER, a drill changes the GRAIN.** Offer cross-filter first, and add
at most one drill per dashboard — to the worklist/detail page ([07](07-workflows-and-tasks.md) "Step 5 — the
worklist page (NOT optional)"). **Not machine-checkable:** `validate` never resolves a URL you built in JS, and
never opens a browser (Gotcha 10) — so every drill needs its own numbered scenario in `test-scenarios.md`,
naming what to click and what should narrow.

---

## 6. Theme-safe rendering (do NOT hardcode white)

A chart renders over the tenant's active theme (4 dark themes + 1 light). Never leave a white box or hardcode a
background hex. (See also doc 14 §2.2 and — for the full theming model —
[24a](24a-theming-and-dark-mode.md).)

- **Chart.js** (`new Chart(ctx, …)`, canvas): the canvas background is **transparent by default** → the plot area
  already inherits the theme. ⛔ **But its text and gridlines are NOT theme-aware — you must set them.** The
  bundled build (`chartjs/chart.min.js`, v3.9.1 — the core the plugin injects, §2.5) hardcodes
  `Chart.defaults.color = '#666'` and `Chart.defaults.borderColor = 'rgba(0,0,0,0.1)'`, and **nothing in the
  platform re-points them per skin** (no `Chart.defaults` assignment exists anywhere in the UI's Java or its own
  static JS). Those two feed everything on the frame: the bundle routes `scale.ticks.color` and `scale.title.color`
  to `color`, `scale.grid.color`/`scale.grid.borderColor` to `borderColor`. `#666` is a comfortable **5.7:1** on
  the light skin and only **2.2–3.1:1** on the four dark ones, and a gridline that is *black at 10 %* is invisible
  over a dark card. Read both live off the themed element, before you construct the chart:
  ```js
  var cs = getComputedStyle(this.$component()[0]);
  Chart.defaults.color = cs.color;                                  // = --bs-body-color of the ACTIVE skin
  Chart.defaults.borderColor = (cs.getPropertyValue('--bs-border-color') || '').trim()
                               || 'rgba(127,127,127,.25)';          // the hairline token; all 5 skins define it
  ```
  `Chart.defaults` is **global to the page**, so every chart that runs this computes the same pair — that is the
  intent. If you would rather not touch the global, set the same two values as `options.color` and
  `options.scales.<id>.grid.color` / `.ticks.color` on that one config instead. This is the same prescription as
  [24a](24a-theming-and-dark-mode.md) §5.6 (which owns the general rule for everything the CSS scoper cannot
  reach — a canvas is painted from JS options, not from CSS); the two docs agree, and 24a is the one to read when
  the container, not the plot, is the problem.
- **Plotly** (`Plotly.newPlot(id, data, layout)`, used for gauges/KPI tiles): `paper_bgcolor`/`plot_bgcolor`
  default to **WHITE** → the "white square report" bug on dark themes. Fix it:

1. Style the container through the model's **CSS** — the `cssByTheme` map (editor: the **Css** tab), using the
   house theme vars (verified across all 5 themes):
   ```jsonc
   "cssByTheme": {
     "*": ".kpi{ background: var(--current-line, var(--bs-light)); color: var(--bs-body-color); border: 1px solid var(--bs-border-color); border-radius:.5rem; box-shadow:0 1px 3px rgba(0,0,0,.10); overflow:hidden }"
   }
   ```
   (`--current-line` is the raised-surface color the 4 dark themes set; the light theme omits it and falls
   back to `--bs-light`.)
   **Four rules for chart CSS:**
   - **Do not write a global `<style>` into `html`** — that markup is emitted verbatim into the page, so the rule
     leaks onto every other component. `cssByTheme` is auto-scoped to the one chart instance.
   - **Write plain selectors** (`.kpi{…}`). The platform prefixes every top-level rule with the chart's own
     element id at render time; a leading `:root`/`html`/`body` is rewritten to that element, `@media`/`@supports`
     blocks are scoped inside, and `@keyframes`/`@font-face` are left alone. You cannot (and need not) know the
     generated id.
   - **CSS cannot reach inside the chart.** Chart.js and Plotly draw into a canvas/SVG the browser paints from
     JS options — colours, fonts and gridlines of the plot itself come from the chart config (§9), not CSS. Use
     `cssByTheme` for the frame: container background, border, radius, padding, KPI typography, the mount's height.
   - Prefer the `"*"` block written with theme **variables**; add a named-theme block only for the one thing a
     variable cannot express under that skin. Keys must be `"*"` or the exact theme name
     (`Standard`/`Dracula`/`Forest`/`Dark`/`Dark Blue`); a typo'd key is simply never emitted — silently.
2. Make Plotly transparent and read the font color **live** from the themed element (never a literal):
   ```js
   var el = this.$find('div')[0];
   var fg = getComputedStyle(el).color;
   var layout = { paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
                  font:{ color: fg }, margin:{t:24,b:8,l:8,r:8} };
   Plotly.newPlot(el, data, layout, {displayModeBar:false, responsive:true});
   ```
3. For semantic number colors that read on both light and dark, use the verified palette:
   terracotta `#e2725b` / red `#e0483a` / green `#47CC29` / amber `#F2BB30` / blue `#22a7f0` / rose `#d1495b`.

`validate` warns (not errors) when a chart's `js` contains `Plotly` but no `paper_bgcolor` — and it strips
comments first, so a commented-out `paper_bgcolor` no longer passes the gate.

> ⛔ **The colour lint does NOT cover chart CSS.** The theme-safe-CSS check (the one that flags hardcoded hexes
> outside `var()` fallbacks) runs only over the **HTML Component Studio's** model. A chart's `cssByTheme` — and the
> legacy `css` field — are **never colour-linted**, so a chart whose CSS paints `background:#fff` validates
> perfectly green and is a white card on four of five themes. Chart CSS is on you: review it by eye, and open the
> page under a dark theme AND the light one before you call it done.

### 6.1 Semantic categorical colors — map by LABEL, not index

> ⛔ **REQUIREMENT — color must carry the data's MEANING, not just be a palette.** Whenever a chart's categories
> have inherent good/bad or ordered semantics — risk (low/medium/high/critical), status, RAG, severity, pass/fail,
> SLA/health, on-time/overdue — the colors MUST follow that meaning as a **traffic-light ramp**: low/good → green,
> medium/warning → amber-orange, high/bad → red (critical → darker red). A reader must tell "bad" from "good" at a
> glance without reading the legend. A risk or status chart painted in a neutral/rotating palette (two blues for
> LOW and MEDIUM, etc.) is a **defect**, not a style choice. Conversely, a **nominal** axis with no good/bad ordering
> (document type, department, sender category, channel, counterparty) must **NOT** be painted green/amber/red — a
> "By type" bar chart all in green or "By retention class" all in red falsely reads as good/bad. Give nominal
> categories a **neutral qualitative palette** — a distinct color PER category drawn from blues/purples/teals/slates
> — so each is distinguishable without implying a verdict. Reserve the traffic-light colors for *meaningful* axes.

A `backgroundColor: ['#..','#..',…]` array assigns colors **by position**, so the mapping rides on the query's row
order — fragile, and it silently mis-paints when the data reorders. For a **semantic** categorical axis (risk,
status, RAG) map each slice from its **label**:

```js
var RISK={HIGH:'#e0483a',MEDIUM:'#F2BB30',LOW:'#47CC29',CRITICAL:'#8b1a2b'};   // §6 verified palette: red / amber / green
var bg=(labels||[]).map(function(l){return RISK[String(l==null?'':l).toUpperCase().trim()]||'#94a3b8';});
// …datasets:[{ …, backgroundColor: bg }]
```

> **A real shipped defect.** A "risk distribution" chart used the generic index palette
> `['#8b1a2b','#22a7f0','#63bff0',…]` → HIGH=dark-red but MEDIUM=`#22a7f0` and LOW=`#63bff0` rendered as **two
> blues**. A risk/status axis must be a traffic-light ramp mapped by label. (Labels here are raw enum names
> `HIGH/MEDIUM/LOW`; if a chart shows *localized* labels, key the map on those strings or map before localizing.)

**Colour is a BUILD-TIME decision, taken from the MEANING of the axis — it is never inherited.** Before writing a
single `backgroundColor`, name the axis's job and pick the family it implies: ordered good/bad → the traffic-light
ramp (above); plain identity → the **qualitative** palette; ordered magnitude with no verdict → a **sequential**
ramp; signed variance around a zero → a **diverging** ramp. Two mistakes are equally defects — painting a nominal
axis in traffic-light colours (the ⛔ above), and painting it in **one flat colour**: eight bars all `#4e79a7`
throws away the one free encoding the chart has, and the reader can no longer follow a category from one cell of
the dashboard to the next. A single flat tone is right in exactly one case: a **one-series** chart whose
categories are pure labels and appear on no other chart of the page (a ranked "top N" bar, a period trend).

#### Qualitative (nominal) palette

Use these **in this order**, slot 1 first:

| slot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| hex | `#4e79a7` | `#59a14f` | `#b07aa1` | `#f28e2b` | `#76b7b2` | `#e15759` | `#edc948` | `#9c755f` |
| reads as | blue | green | mauve | orange | teal | red | yellow | brown |

**Where they come from:** this is the platform's *own* chart palette, not a new house style — the 88 starters in
the template catalog (§8) paint every **series** with exactly these plus `#ff9da7`/`#bab0ac` (`#4e79a7` 202
occurrences, `#f28e2b` 106, `#59a14f` 92, `#e15759` 73, `#76b7b2` 55, `#b07aa1` 30, `#edc948` 22 — every other
hex in the catalog is a grey or white used for chrome).
What is changed here is the **order**: the starters' own sequence puts `#59a14f` next to `#e15759`, and under
deuteranope simulation that pair is ΔE 0.7 — two identical browns. The order above keeps every adjacent pair
≥ 10 ΔE apart under protan *and* deutan simulation and ≥ 19 ΔE under normal vision, so neighbouring bars/slices
stay separable for every reader. Two measured caveats:

- On the **light** skin's white card `#edc948` is only ~1.6:1 and `#76b7b2`/`#f28e2b` ~2.3–2.4:1 — fine as a
  large fill, weak as a thin mark. Keep the yellow late in the order (it only appears at 7+ categories) and
  separate pie/doughnut slices with a hairline (`borderWidth: 1` on the dataset) instead of relying on the hue.
- On the **dark** cards every slot clears 3:1 except `#4e79a7` (2.8–3.0:1). Fine as a fill; for a *line* chart
  raise `borderWidth` to 2–3 rather than swapping the colour.

Assign by a **stable key**, exactly like the traffic-light map — and since you already seeded every value of the
axis (§2.6 Rule 1), write the vocabulary out by hand:

```js
var COLOR = { '<VALUE A>':'#4e79a7', '<VALUE B>':'#59a14f', '<VALUE C>':'#b07aa1', '<VALUE D>':'#f28e2b',
              '<VALUE E>':'#76b7b2', '<VALUE F>':'#e15759', '<VALUE G>':'#edc948', 'OTHER':'#9c755f' };
var bg = (labels||[]).map(function (l) { return COLOR[String(l==null?'':l).trim()] || '#9aa2ad'; });
// …datasets:[{ …, backgroundColor: bg }]
```

The `#9aa2ad` fallback is a **build alarm, not a colour choice**: a grey bar on screen means the axis returned a
value your map does not know — fix the map (or the SQL), never the fallback.

⛔ **Max ~7–8 categories.** Past that the hues stop being tellable apart, the legend outgrows the plot, and a
doughnut becomes a colour wheel (§2.6 caps a pie at 7 slices). Group the tail in **SQL**, not in JS — keep the
top N by the measure and fold the rest into one `OTHER` row (§2.6 Rule 3) — or change form: a horizontal bar
sorted by value carries 15 categories comfortably with **one** colour, because there the axis label does the
identifying.

#### Sequential and diverging ramps

**Sequential — an ordered axis with no good/bad** (age/size/volume tiers, buckets, funnel stages, quartiles).
One hue, lightness stepped, dark = more:

```js
var TIER = ['#82afe0','#6b97c7','#5581af','#406a97'];   // 4 tiers, lightest → darkest
```

These are the starters' blue `#4e79a7` held at its hue and chroma with OKLCH lightness stepped ~0.075 per step —
one visible family, each step distinct from its neighbour. **Four steps in the middle band, not five across the
full range:** a ramp that runs white→navy has a palest step that vanishes on the light skin and a darkest step
that vanishes on the four dark ones. As measured, the pale end still clears a white card (~2.3:1) and the dark
end still clears a dark card (~2.3:1). Need six tiers? Bucket them to four in SQL. (Add `#2b5580` as a 5th, darker
step **only** for a page you know renders on the light skin.)

**Diverging — a signed axis around a meaningful zero** (variance against target/plan/budget, delta vs previous
period, above/below a threshold). Two hues + a **neutral** midpoint, never a rainbow and never a hue in the middle:

```js
var VAR5 = ['#406a97','#82afe0','#9aa2ad','#e88e8b','#e15759'];   // ← under target · neutral · over target →
```

Poles are the starters' blue and red; the midpoint `#9aa2ad` is the starters' own neutral grey. Because four of
the five skins are dark, both poles stay **mid-toned** and it is the saturation, not the darkness, that carries
distance from zero — the classic dark-ends/light-middle diverging ramp loses both ends on a dark card.
⛔ An ordered axis with **no** zero point is sequential, not diverging: a "size tier" painted blue→grey→red claims
a good/bad reading that the data does not have.

#### One entity, one colour

**The same category keeps the same colour on every chart of the page — and on the drill target.** A dashboard is
read by tracking one thing across cells; if `<VALUE B>` is green in the doughnut and orange in the bar chart, the
reader has to re-learn the legend per cell and the dashboard reads as three unrelated pictures.

- Author the map **once** and paste the identical literal into every chart's `js` on the page (fills come from a
  per-chart JS literal — there is no shared palette object, and `cssByTheme` cannot reach inside the canvas, §6).
- **A filter must not repaint the survivors.** Keyed by label, filtering 8 categories down to 3 leaves each of the
  3 in its own colour; an index palette (`backgroundColor:['#..','#..']`) re-paints them on every filter and every
  re-order — the failure this whole section opens with, and the one a **cross-filter** dashboard hits constantly
  because every click re-runs the queries (§5).
- Carry the same map to the page you **drill** to (§5.3), or the entity changes colour at the page boundary.
- Colour is never the *only* channel: on four of five skins hue collapses (24a §4 — Dracula's `--green` is a
  blue), so keep the axis labels and, for ≥ 2 series, the legend (`datasets[].label`, §9.2) switched on.
- If two charts of the same axis disagree on **order**, they will disagree on emphasis even with identical
  colours — order a status/lifecycle axis by its own `sort_order`, not by the measure (§2.6 Rule 3).

---

## 6A. Laying the cells out — the gap Bootstrap does not give you

A dashboard is a grid of chart cells, and the grid is `<div class="row">` + `<div class="col-…">`. That
gives you a horizontal gutter and **no vertical one**: Bootstrap's `.row` sets
`--bs-gutter-x: 1.5rem; --bs-gutter-y: 0`, so the columns get side padding while the rows sit flush.
The result is a page with tidy left-right gaps whose charts are welded to the ones above and
below them — which reads as broken rather than dense, and is the single most common way a
technically-correct dashboard still looks unfinished.

Two ways to give it the missing axis. **Prefer the first.**

**One grid, gutters on both axes** — the form to reach for, and the one to use *inside* a row card:

```html
<div class="row g-4">
  <div class="col-12">…</div>
  <div class="col-6 col-lg-3">…</div>   <!-- cells simply wrap; no inner rows at all -->
  <div class="col-12 col-lg-8">…</div>
</div>
```

`g-*` sets `--bs-gutter-x` AND `--bs-gutter-y`, so every cell is spaced on both axes by one class, the
cells wrap into lines by themselves, and there is no trailing margin under the last one. Inside a single
`.row` there is no "row added later" that could miss the class.

**Or put it on the chart's own wrapper**, when the layout genuinely needs separate `.row`s:

```css
.my-plot{ … ; margin-bottom: var(--bs-gutter-x, 1.5rem)}
```

Take the size from `--bs-gutter-x` rather than guessing: it is set on `.row` and inherits down, so the
vertical rhythm always equals the horizontal one, including when a theme changes it. A hardcoded
`margin-bottom:1rem` stops matching the moment anything else moves. This form has two costs: it is
per-chart rather than per-layout, it leaves a margin under the last row — and the margin now comes
from INSIDE a lazily loaded cell (§2.4), so the rows stay welded together for as long as the charts
take to arrive. Which is the real reason to prefer the first form.

(`g-*`/`gy-*` are Bootstrap 5 only. On 4, the wrapper-margin form is the one that works.)

### The rest of the visual floor

These are cheap, they are what separates "the data is right" from "this looks like a product", and
none of them is visible in a query result — only on screen:

* ⛔ **No card frame around a chart.** Do not give a chart's own `html` a background, a border or a
  rounded corner: it is a caption plus its plot, sitting straight on the page. Two reasons, and the
  first one you cannot fix from the chart side: the platform's wait placeholder draws **no** frame
  (§2.4, it cannot know whether one is coming), so a framed chart pops its box into existence when it
  lands, and a page of them assembles one lazily-loaded cell at a time; and a frame per chart is a
  border for every single thing on the page, which is the same as no borders at all.
* **Frame the ROW instead, and title it.** The frame belongs to the page's own markup, where it paints
  in the first paint — so wrap each row of the grid in the theme's card and put what that row answers in
  its header. A row of charts stops being three unrelated pictures and becomes one stated question,
  which is also where the reader looks first; the KPI row takes no header (labelled numbers explain
  themselves). Keep the row's columns exactly as the grid had them — this is a wrapper, not a re-layout:

  ```html
  <div class="main-card mb-3 card">
    <div class="card-header">
      <i class="header-icon lnr-sync icon-gradient bg-plum-plate"></i>
      <plugin id="<row-id>-hdr" name="nct.label.plugin"></plugin>
    </div>
    <div class="card-body"><div class="row g-4">
      <div class="col-12 col-md-4"><plugin id="<cell>" name="nct.parsis.plugin"></plugin></div>
      …
    </div></div>
  </div>
  ```

  The header is a `nct.label.plugin`, never text in the markup: it is the one sentence on the dashboard
  a reader actually reads, so it needs a per-locale map ([20](20-localization.md)), which inline html has
  not. Set its **`tagName` to `span`**: the plugin's default tag is `p`
  (`LocalizedHeaderPropertiesBuilder.withDefault("p")`, and a blank `tagName` also renders `p` —
  [14](14-plugin-catalog-all.md) §1.4), and the theme's `p{margin-bottom:1rem}` inside a
  `.card-header{padding:.5rem 1rem}` leaves the title sitting on a rem of dead space. The row card's own
  `mb-3` then carries the vertical rhythm, which is strictly better than a page-wide gutter while the page
  loads (§2.4).
* **One title style.** Small, uppercase, letter-spaced, `opacity:.75`, and no bigger than the numbers
  it labels. A chart title competing with its own data is noise.
* **Equal chart heights per row.** Fix the height on the chart's outer wrapper, not the canvas, so the
  row's charts align along their bottoms. Ragged bottoms read as a rendering bug. Subtract the
  caption's own box from the plot's height (`height:calc(100% - 1.9rem)` under an `<h6>`) — the
  wrapper height is authoritative, so a caption that is not subtracted pushes the plot out of it.
* **A KPI band above the charts.** Four single numbers across the top answer "how are we doing" before
  anyone reads a chart; they are also the cheapest thing on the page to compute.
* **Let the widest chart breathe.** A twelve-category bar chart in a `col-md-4` renders its labels
  rotated and unreadable — give it `col-lg-8` or a full row, and put the doughnut/short-list charts in
  the narrow cells.

`mrjun.py validate` does not check any of this: a page with zero spacing is valid content. It is a
review item — look at the rendered page, not just the JSON.

## 7. How to construct from scratch

> **Two non-negotiables for every chart you build here:** (1) if the categories carry meaning (risk/status/RAG/
> severity/health), color them **semantically** — a traffic-light ramp mapped by label, not a rotating palette
> (**§6.1**); (2) if the chart is **click-to-filter**, author the **pointer cursor + "Click to filter" hint** in its
> `js`, don't rely on the automatic pill (**§5**, Recipe C).

### Recipe A — a single QUERY-bound Chart.js chart

1. **Save the data query** ([12](12-queries-sources-schedulers-and-rest.md) §1) and note its `identifier`.
   ```
   query add --name "Velocity By Month" --source app_schema --sql @velocity.sql
   ```
   `velocity.sql` (params inline in the SQL if you want it filterable — here none):
   ```sql
   SELECT to_char(changed_date,'Mon') AS monthsn,
          CAST(SUM(effort) AS integer)  AS effort
   FROM velocity GROUP BY monthsn ORDER BY min(changed_date)
   ```
2. **Author the chart blob** `chart.json` (the `group` must match the `$$()` in `js` byte-for-byte; `columnName`
   is the **lowercased** result column):
   ```jsonc
   {
     "id": "11111111-1111-1111-1111-111111111111",
     "html": "<div style=\"position:relative;height:320px;\"><canvas></canvas></div>",
     "js": "const data={labels:$$('Labels',['-'],'String[]'),datasets:[{label:'Effort',data:$$('Values',[0],'Integer[]')}]};this.chart=new Chart(this.$find('canvas')[0].getContext('2d'),{type:'line',data:data,options:{responsive:true,maintainAspectRatio:false}});",
     "replacements": [
       { "name":"Labels","group":"$$('Labels',['-'],'String[]')","type":"String[]",
         "replaceStrategy":"QUERY","queryIdentifier":"<Velocity By Month identifier>",
         "query": { /* the TRIMMED 12-field copy below — NOT the query rep-object */ },
         "columnName":"monthsn","defaultValue":"['-']","order":0,"maxItemsCount":1000,"futureReplacements":[] },
       { "name":"Values","group":"$$('Values',[0],'Integer[]')","type":"Integer[]",
         "replaceStrategy":"QUERY","queryIdentifier":"<Velocity By Month identifier>",
         "query": { /* the same trimmed copy */ },
         "columnName":"effort","defaultValue":"[0]","order":1,"maxItemsCount":1000,"futureReplacements":[] }
     ]
   }
   ```
   The `query` inside each replacement is a **trimmed** copy of the saved query — same `identifier`, but ONLY
   the 12 fields the ⛔ in §1.1 allows. The two replacements share one query (both pull different columns from
   it), so write the object once and paste it into both. Exactly this shape, with your own values:

   ```jsonc
   {
     "id": "<the saved query's id>",                  // both id and identifier copied from the rep object
     "identifier": "<Velocity By Month identifier>",
     "realmName": "<realm>", "clientName": "<client>", // copy from any other rep object in the SAME bundle
     "name": "Velocity By Month",                      // the saved query's name
     "query": "SELECT …",                              // the SQL, verbatim
     "sourceIdentifier": "<source identifier>",
     "offset": 0, "itemsPerPage": 1000,                // itemsPerPage is overwritten by maxItemsCount at run time
     "parameters": {}, "attributes": {},
     "aggregations": { "aggregations": [], "groupByList": [], "orderByList": [] }
   }
   ```

   > **Where `realmName`/`clientName` come from.** They are the owning project's realm and client — you do not
   > invent them. Copy the pair off **any existing rep object in the same bundle**; that is exactly what
   > `mrjun.py` does when it creates one (it scans `queries`/`sources`/`rules`/`contexts`/`forms`/`formGroups`/
   > `settings` for the first object carrying a `realmName`, and only if none exists falls back to splitting
   > `tenant.json.domain` on the dot). What actually selects the data at render time is the embedded SQL plus
   > `sourceIdentifier`, so the job of this pair is simply to match the rest of the bundle.
   >
   > ⛔ **`aggregations.aggregations` must be `[]`, never `null`.** `groupByList`/`orderByList` have null-safe
   > getters; the aggregation list does not, so a `null` there throws the moment anything reads the aggregation
   > list (the drill-chain builder, §5.1). Note that `mrjun.py query add` writes `null` into the rep object —
   > fix it when you trim the copy.
3. **Place the node:** `node add --parent <page/parsis> --plugin chart.js.plugin --name "Velocity" --model @chart.json`
   then `validate` (it warns on an EMPTY `columnName`, but it cannot tell you that `queryIdentifier` points at a
   real query or that `columnName` is a real result column — eyeball those, then open the page).

### Recipe B — a filtered dashboard (filter bar + shared param)

1. Give each chart's query the **same** placeholder `name` (`{name:'Project name', type:'dropdown-string',
   dropDownPopulation:{query:'Projects Query', value:'name', name:'name'}}`) so one control filters all
   (§4.2) — with the single exception of a chart that **groups by** that same column, which must omit it
   (§4.6 "The GROUP-BY exemption"). Also create the `Projects Query` lookup query.
2. Author each chart per Recipe A (`replaceStrategy:"QUERY"`; add a seed `"parameters":{"Project name":{"value":"…"}}`
   in the embedded query if you want a default state).
3. Add the filter bar **on the same page**: `node add --parent <page/parsis> --plugin global.replacement.plugin
   --name "Filters"`. No config — it discovers `Project name` from the charts and renders a dropdown.

(That is the mechanism in three steps. **Recipe E** builds the same dashboard end-to-end — node order, data
check, colour, one click-to-filter chart, nav and the gates.)

### Recipe C — add click-to-cross-filter to a chart

Append to the chart's `js` (field = the shared param name `<P>`) — the click handler **and** the required
affordance (pointer cursor + "Click to filter" hint, §5):
```js
cfg.options.onClick = function(e, els){
  if (els && els.length) { this.crossFilter('Project name', this.chart.data.labels[els[0].index]); }
  else { this.crossFilter('Project name', null); }   // empty area → clear
}.bind(this);
cfg.options.onHover = function(e, els){        // ⛔ REQUIRED: show it's clickable
  if (e && e.native) e.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
};
this.$find('canvas')[0].title = 'Click to filter';    // ⛔ REQUIRED: discoverability hint (localize where multilingual)
```
Clicking a bar now filters the whole page on `Project name`; clicking the same value again clears it (§5).
**Never ship a click-to-filter chart without the `onHover` pointer + title** — without them it looks un-clickable.

### Recipe D — a theme-safe Plotly KPI tile

Use `html:"<div style=\"position:relative;height:160px;overflow:hidden;\"></div>"`, a single
`$$('Value',[0],'Double[]')[0]` bound to a scalar query column, and the theme-safe Plotly layout from §6
(`paper_bgcolor:'rgba(0,0,0,0)'`, live `font.color`), plus the `.kpi` container CSS in the model's
`cssByTheme["*"]` (**not** an inline `<style>` in `html` — that leaks page-wide, §6).

> ⛔ **Set `layout.height` EXPLICITLY on a Plotly tile — the height on the mount div is not enough.**
> The chart body arrives in a **second AJAX round-trip** (Gotcha 17), so at `Plotly.newPlot()` time the
> container is not always laid out yet. With only `autosize:true` Plotly then cannot measure it, falls back to
> its own default height, and the **card grows to roughly four times the tile** — a KPI strip that should be
> ~150 px eats the whole first screen, with the number stranded in the top corner and a field of empty card
> beneath it. LIVE-FOUND 2026-09-05. Give the layout a real `height:` (the mount div keeps the same number,
> plus `overflow:hidden` as the backstop), keep `autosize:true` for the width, and keep the
> `ResizeObserver → Plotly.Plots.resize` from §6.
>
> ✅ **Put no title inside the tile.** A chart's `js` is ONE non-localized string (Gotcha 16), so a `title` baked
> into the indicator is one hard-coded language on a multi-locale tenant. Caption the tile with a sibling
> `nct.label.plugin` above it — that one carries all three locales — and let the plot draw only the number.
>
> ✅ **A delta arrow is only honest when the value and the reference are measured the same way.** `mode:'number+delta'`
> invites a `delta.reference`, and the tempting reference — "the same measure over the previous 90 days" — is
> **not comparable to a lifetime total**: a tile reading `154 ▲126` is not reporting growth, it is subtracting a
> quarter from all of history. Decide which kind of number the tile is first:
>
> | kind | value | reference | example |
> |---|---|---|---|
> | **flow** — events inside a window | the last N days | the N before that | money lost, cases opened, decisions taken |
> | **stock** — how many are open now | as of the newest row | the same predicate **as of N days earlier** (`opened_at < cut AND (closed_at IS NULL OR closed_at >= cut)`) | open cases, items awaiting approval |
> | **rate** — a share | numerator ÷ denominator inside a window | the same ratio in the previous window | % within target, % answered on time |
>
> And window a **rate on the date it was SETTLED or FELL DUE**, never on the date it arrived: windowing
> "deadlines met" on the arrival date drops every recent item that is still in flight out of the denominator and
> the figure swings by tens of points (measured: 15.5 % on arrival date vs 60.0 % on deadline date, same data).
> Anchor every window to the DATA (`(SELECT max(<col>) FROM …)`), never to `now()` — the dump is frozen
> (§2.6 Rule 5). Finally, a metric shown on two boards must anchor on the **same column** on both, or the
> cockpit and its drill-down print two different numbers for one thing.

### Recipe E — a complete filterable dashboard page

Recipes A–D each build one piece. This is the whole page, in the order you actually create the nodes. It assumes
one `<Entity>`, one shared filter `<P>`, and 4–6 chart cells.

**0 — decide whether this page is the front door.** A dashboard with chartable data is normally Home; a pure
queue/workflow tool redirects to its worklist instead. Rules and the two wiring mechanisms:
[21](21-homepage-and-redirect.md) "## Choosing the front door — chart dashboard or main worklist". Decide this
**before** you create the page: a chart Home is built into the root page's own parsis with `Redirect=""`, a
non-Home dashboard is its own `siteMapPage`. Everything below is identical either way — only `--parent` changes.

**1 — the page** (skip when the dashboard IS Home; use the root page's `parsis` as the parent instead):
```
mrjun.py page add --parent root --name "<Entity> Dashboard" --alias <entity>-dashboard --auth
```

**2 — the lookup query for the filter**, before any chart, because the placeholder references it **by name**
(Gotcha 8). It must be able to return **≥ 3** options or `ParamsPanel` renders a control nobody can use
(§2.6 Rule 2, §4.6):
```
mrjun.py query add --name "<P> Lookup" --source <source> --sql \
  "SELECT DISTINCT <col> AS <col> FROM <schema>.<entity> WHERE <col> IS NOT NULL ORDER BY 1"
```

**3 — the chart queries, each declaring the SAME `<P>`.** One placeholder string, pasted byte-for-byte into every
chart's SQL — that identity is the whole filtering mechanism (§4.2), and a chart that omits it simply will not
react to the bar:
```sql
AND <col> = {name: '<P>', type: 'dropdown-string',
             dropDownPopulation: {query: '<P> Lookup', value: '<col>', name: '<col>'}}
```
Keep it a **bare right-hand operand** — no `COALESCE`, no `CAST` (⛔ §3.1) — and anchor any period window to the
data, not to `now()` (§2.6 Rule 5). Run each query with the filter empty and count the rows against the
marks-per-form table (§2.6) before binding anything.
⛔ **One chart omits `<P>`, deliberately: the one that `GROUP BY`s `<P>`'s column** — the selector you will wire
in step 6. It declares every *other* param of the set and not this one; declaring it there makes the chart filter
itself down to the single mark you just clicked (§4.6 "The GROUP-BY exemption"). That omission is the exemption,
not the silent partial-coverage hole §4.6 opens with.

**4 — the nodes, in this order** (`order` is render order; the bar must sit above the grid):

| # | node | command | why here |
|---|---|---|---|
| 1 | header `nct.html.plugin` | `node add --parent <page/parsis> --plugin nct.html.plugin --name "Header"` | title + one line of context; optional |
| 2 | **filter bar** | `node add --parent <page/parsis> --plugin global.replacement.plugin --name "Filters"` | ⛔ **above** the grid — it takes no config and is rejected if you pass `--model`/`--settings` (§4.1) |
| 3 | grid-row `nct.html.plugin` | one per row: `<div class="main-card mb-3 card">` + `card-header` + `card-body > <div class="row g-4">` of `<div class="col-…"><plugin id="<cell>" name="nct.parsis.plugin"></plugin></div>` cells | ⛔ **the card goes on the ROW, never on each chart — §6A** (and the chart's own `html` stays frameless). Layout shape: [21](21-homepage-and-redirect.md) "Home-as-dashboard" |
| 3a | row header `nct.label.plugin` | child of its row, `identifier` == the `<plugin id>` in the `card-header`, `tagName:"span"`, `text` localized | the question that row's charts answer together; a KPI row needs none (§6A) |
| 4 | cell `nct.parsis.plugin` | child of its grid row, `identifier` == the matching `<plugin id>` | one cell = one chart |
| 5 | `chart.js.plugin` | `node add --parent <cell> --plugin chart.js.plugin --model @chart-N.json` | Recipe A per chart |

⛔ **No `crud.table`/`crud.tree`/`process.table` on this page** — a dashboard is charts only; the row list goes on
the worklist page ([07](07-workflows-and-tasks.md) "Step 5 — the worklist page (NOT optional)"), and
`validate` WARNs on ≥ 3 charts sharing a page with a table (Gotcha 10).

**5 — colour each chart from the meaning of its axis** (§6.1), not from the starter you copied: status/risk →
traffic-light mapped by label; nominal identity → the qualitative slots in order, the **same map in every chart**;
ordered tiers → the sequential ramp; variance vs target → the diverging ramp. A KPI tile takes a single semantic
number colour (§6, Recipe D).

**6 — make exactly one chart click-to-filter** (Recipe C) — the one whose axis the reader will slice by, usually
the status/category doughnut, i.e. **the chart that groups by `<P>`'s column and therefore left `<P>` out of its
own SQL** (step 3 ⛔). Field name = `<P>`, single-quoted, and the **pointer cursor + hint are required**
(⛔ §5). Everything else on the page then re-runs from that one click (§5.2). If a click should open the row list
instead, that is a **drill**, not a cross-filter — §5.3.

**7 — reachability.** The dashboard needs a left-nav quick link, and so does the page it drills to:
```
mrjun.py quicklink add --page "<Entity> Dashboard" --label "<Entity> Dashboard"
```
([17](17-left-nav-quick-links.md); when the dashboard is Home, the quick link is still required — the ⚠️ box in
[21](21-homepage-and-redirect.md) — or a drill-down leaves the user with no way back.)

**8 — gate it.** `mrjun.py validate` catches the inert bar, an undeclared `crossFilter` field, a `group` that does
not match `js`, a chart+table page — all of Gotcha 10. Then **open the page**: with the filter empty, with a value
picked, after a click, and under one dark skin plus the light one. `validate` never runs your SQL and never
renders (doc [23](23-distribution-and-known-gaps.md)).

---

## 8. The chart EDITOR — the UI authoring surface (and what each tab writes)

The chart editor opens in a **95 % modal** from the chart node's edit action. **You hand-author the exact same
`ChartJsModel` it saves** — there is no hidden state. This section maps its UI to the model fields, so it's
unambiguous what a complete chart node must contain.

**Layout:**

- **Template gallery** ("Start from a template") — a picture grid grouped **by engine → category**, **88**
  starters (**chartjs 29 · plotly 24 · echarts 20 · mermaid 15**; per-engine categories listed in §2.5). Picking a
  card sets `model.js` + `model.html` from the starter (its `js` already carries `$$('Name', <single-default>,
  'Type')` markers) and jumps to the JS tab. A brand-new chart (blank `js`) opens on the gallery. **This is the
  fastest correct start: copy a starter's `js`/`html` for your engine, then bind the placeholders.**
- **Five tabs**, captioned on screen **Html · Javascript · Css · Replacements · Caching** (the config names
  behind them are `HTML`/`JS`/`CSS`/`REPLACEMENTS`/`CACHING`, each tab can be hidden and one can be preselected;
  the default is the JS tab, and the §5.1 drill view reuses the same editor with Html/Javascript/Caching hidden).
  Each tab edits exactly one model field:

  | Tab | Editor control | Writes | Notes |
  |---|---|---|---|
  | **HTML** | CodeMirror HTML editor | `model.html` | mount markup: `<canvas>` (Chart.js) · `<div>` (Plotly/ECharts) · `<pre class="mermaid">`. Rendered verbatim — no `$$()`, no `<style>` (§6) |
  | **JS** | CodeMirror JavaScript editor | `model.js` | the render script with `$$()`; editing it re-parses placeholders and **auto-syncs the Replacements list** |
  | **Css** | a **theme-pill strip** + one CodeMirror CSS editor | `model.cssByTheme[<theme>]` | see the Css tab below |
  | **Replacements** | the replacements panel (built lazily) | `model.replacements[]` | one row per distinct `$$()` name; drag to reorder stamps `order` |
  | **Caching** | the cron editor (a preset picker + a free-text pattern field) | `model.schedule` (+ fanned onto every `replacements[].query.schedule`) | makes those queries cacheable — Gotcha 12. The free-text pattern and the full preset list are **author/admin only**; an ordinary user sees a single preset |

- **The Css tab in detail.** The strip shows one pill per theme: **All themes** (the `"*"` key) followed by every
  theme the platform ships (today `Standard`, `Dracula`, `Forest`, `Dark`, `Dark Blue` — generated from the skin
  list, so a new skin appears automatically). The editor below always edits the **selected** pill's block; a pill
  is highlighted when it currently carries CSS, so you can see at a glance which themes you have overridden.
  Clearing the editor **removes** that key rather than storing an empty string. At render time only the `"*"` block
  plus the **active** theme's block are emitted, each scoped to the chart instance (§6). The model shape is
  therefore:
  ```jsonc
  "cssByTheme": {
    "*":         ".<pfx>-tile{background:var(--current-line,var(--bs-light));color:var(--bs-body-color)}",
    "Dark Blue": ".<pfx>-tile{border-color:#4c6c94}"     // only what the variable cannot express
  }
  ```
  (Choose a short `<pfx>-` class prefix per chart out of habit — the platform already scopes the block to this
  chart, but a prefix keeps your own markup readable and survives copy-paste into an `nct.html.plugin`.)
- **Click-filter constructor** — a field-name input + button that generates the engine-aware `onClick` and
  **appends it to `model.js`** (then re-syncs Replacements). This is the UI that produces the §5 cross-filter
  snippet; by hand you just write the `onClick` yourself.
- **"Show"** — a live preview: renders a real chart from the current model in a popover.

**The Replacements tab in detail** — this is where a `$$()` placeholder becomes a bound `ChartJsReplacement`:

- **Every row** shows: the placeholder **`name`** (read-only — it comes from the `$$()`), a **strategy** toggle
  **QUERY**/**LABEL**, and then either the LABEL **`value`** field or the query chooser + a **Configure** link.
  (`type` is not shown — it is taken from arg3 of the `$$()`.) Above the list, a small input + **set max count of
  items** button writes `maxItemsCount` on **every** replacement at once.
- **QUERY** row → **Configure** opens the **query-configuration pane** beside the list (not a modal), which writes
  into `replacement.query` (a whole embedded `QueryDto` copy) + `queryIdentifier`, and also holds this
  replacement's **`maxItemsCount`**:
  - **Query** — choose/edit the saved query the placeholder pulls from (plus *merge linked source/query* actions
    that re-sync the embedded copy with the saved one).
  - **`columnName`** — the result column this placeholder extracts (lowercased — see Gotcha 2).
  - **Group by / Order by / Aggregations** — write the query's `groupByList` / `orderByList` / `aggregations`
    ([12](12-queries-sources-schedulers-and-rest.md) §11): you can shape aggregation in the UI instead of in SQL.
    A **Group by** row is also the entry point that creates a drill step (§5.1).
  - **Future replacements** — the drill-step **chooser** (navigate/remove existing steps; §5.1).
  - **Copy / paste config** — a session clipboard for the aggregation block, so a second placeholder over the same
    query gets the identical group-by/aggregation shape.
- **LABEL** row → a plain text control for the literal `value` (no query, not filterable, injected raw unless
  `type` is `String` — §2.3).

**Hand-authoring parity — the checklist.** A chart node you write by hand is complete and editor-equivalent when its
`Javascript.stringValue` decodes to `{id, html, js, cssByTheme?, css?, schedule?, replacements:[…]}` where **each**
replacement has `{name, group, type, replaceStrategy, queryIdentifier, query, columnName, order, maxItemsCount,
futureReplacements}` and:
1. every `$$('name',…)` in `js` has a matching replacement whose `name` equals arg1 **and** whose `group` is the
   `$$(...)` text **byte-for-byte** (the editor keeps these synced live; by hand it's on you — Gotcha 1);
2. `type` (arg3) equals the replacement's `type` and a real `ReplacementType` (§2.3);
3. QUERY replacements carry the embedded `query` + `queryIdentifier` + `columnName`; LABEL ones carry `value`;
4. the mount in `html` matches the engine used in `js` (§2.5), and the engine's libraries are the loaded core (⚠ box in §2.5);
5. any container styling lives in **`cssByTheme`** — keys `"*"` and/or exact theme names, plain selectors, theme
   variables rather than literals — and **not** in an inline `<style>` inside `html` (§6). Nothing lints this for
   you, so check it under a dark theme and the light one.

---

## 9. Chart.js configuration settings — the `{type, data, options}` config object

Chart.js (v3.9.1) is configured entirely by the object you pass to **`new Chart(ctx, config)`** in `model.js`.
There is no separate "settings" slot — the config **is** the settings, and its data comes from `$$()` (§2). Every
Chart.js starter follows the same skeleton (verbatim shape of the 29 `chart-templates.json` chartjs starters):

```js
const ctx = this.$find('canvas')[0].getContext('2d');
this.chart = new Chart(ctx, {
  type: 'bar',                                   // §9.1 — the chart type
  data: {                                        // §9.2 — labels + one or more datasets, bound via $$()
    labels: $$('Labels', ['-'], 'String[]'),
    datasets: [{ label: 'Effort', data: $$('Values', [1], 'Double[]'),
                 backgroundColor: '#4E79A7', borderRadius: 3 }]
  },
  options: {                                     // §9.3 — everything else (layout, axes, legend, title, tooltip)
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
  }
});
```

> Always pair it with `html: "<div style=\"position:relative;height:320px;\"><canvas></canvas></div>"` — a
> **fixed-height, `position:relative` wrapper** — because `maintainAspectRatio:false` makes the canvas fill its parent;
> without a sized wrapper the chart collapses to 0 px (a common "chart is blank" cause that is NOT a data problem).

### 9.0 The full starter catalogue — all 88, by engine

Every card in the gallery, so a starter can be chosen from the docs and looked up by `key` in the
editor. The `key` is what the gallery stores; the name is what the card shows. Counts per engine:
**chartjs 29 · plotly 24 · echarts 20 · mermaid 15**.

> ⛔ **Copy a starter; do not invent the JS.** A starter's `js` already carries the right canvas handle
> for its engine, the `$$('Name', <single-default>, 'Type')` markers in the right places, and the
> construction order the engine needs. Hand-rolled chart JS is where `element.querySelector` and other
> handles that do not exist come from — and a chart whose script throws renders an empty box while its
> queries return data perfectly well.
>
> ⛔ **Except the 15 `mermaid` starters.** Their `js` is two lines that hand the block to
> `mermaid.init(undefined, this.$find('.mermaid')[0])`; the diagram itself is literal text inside
> `html`, and there is not one `$$()` slot in any of them — nothing binds to a query (§2.5). Pick one
> only for a STATIC diagram; a data-driven chart has to come from `chartjs`, `plotly` or `echarts`.
> (Verified against the shipped catalog: 73 of the 88 carry `$$()`; all 15 that do not are mermaid.)

**chartjs** (29)

| category | starters (`key`) |
|---|---|
| Comparison | Column (`column`), Bar (Horizontal) (`bar`), Grouped Bar (`grouped-bar`), Combo (Bar + Line) (`combo`), Polar Area (`polar-area`), Radar (`radar`), Waterfall (`waterfall-chartjs`), Diverging Bar (`diverging-bar`), Multi-Series Radar (`multi-radar`), Stacked Bars + Line (`mixed-stacked-line`) |
| Distribution | Histogram (`histogram`), Range Bar (`range-bar`) |
| KPI | Bullet (KPI vs Target) (`bullet-kpi`) |
| Part-to-whole | Stacked Bar (`stacked-bar`), 100% Stacked Bar (`stacked-bar-100`), Pie (`pie`), Doughnut (`doughnut`), Horizontal Stacked Bar (`horizontal-stacked`), Nested Doughnut (`nested-doughnut`) |
| Relationship | Scatter (`scatter`), Bubble (`bubble`), Scatter with Trendline (`scatter-trendline`) |
| Trend | Line (`line`), Multi-line (`multi-line`), Area (`area`), Stacked Area (`stacked-area`), Sparkline (`sparkline`), Time-Series Line (`ts-line`), Stepped Line (`stepped-line`) |

**plotly** (24)

| category | starters (`key`) |
|---|---|
| 3D | 3D Scatter (`scatter3d`), 3D Surface (`surface3d`) |
| Distribution | Box Plot (`box-plot`), Heatmap (`heatmap`), Violin Plot (`violin`), 2D Histogram (`histogram-2d`), Contour Plot (`contour`) |
| Financial | Candlestick (`candlestick`), OHLC Chart (`ohlc`) |
| Flow | Sankey Diagram (`sankey`), Waterfall (`waterfall`) |
| Geo | Choropleth Map (USA) (`choropleth-usa`), Bubble Map (Scatter Geo) (`scatter-geo-bubble`), Wind Rose (`wind-rose`) |
| KPI | Gauge (`gauge`), KPI Number (`kpi-number`), Bullet Gauge (`bullet-gauge`), KPI Number + Delta + Trend (`kpi-number-delta-trend`) |
| Part-to-whole | Funnel (`funnel`), Treemap (`treemap`), Sunburst (`sunburst`), Icicle (`icicle`) |
| Relationship | Parallel Coordinates (`parallel-coordinates`), Parallel Categories (`parallel-categories`) |

**echarts** (20)

| category | starters (`key`) |
|---|---|
| Comparison | Bar Chart (`ec-bar`), Horizontal Bar (`ec-horizontal-bar`), Radar Chart (`ec-radar`) |
| Distribution | Heatmap (`ec-heatmap`), Box Plot (`ec-boxplot`) |
| Financial | Candlestick (`ec-candlestick`) |
| Flow | Sankey Diagram (`ec-sankey`), Funnel Chart (`ec-funnel`) |
| KPI | Gauge (`ec-gauge`) |
| Part-to-whole | Stacked Bar (`ec-stacked-bar`), Pie Chart (`ec-pie`), Nightingale Rose (`ec-rose`), Treemap (`ec-treemap`), Sunburst (`ec-sunburst`) |
| Relationship | Scatter Plot (`ec-scatter`), Network Graph (`ec-graph`) |
| Trend | Line Chart (`ec-line`), Smooth Line (`ec-smooth-line`), Area Chart (`ec-area`), Stacked Area (`ec-stacked-area`) |

**mermaid** (15)

| category | starters (`key`) |
|---|---|
| Flow | Flowchart (`mermaid-flowchart`), State Diagram (`mermaid-state`), Git Graph (`mermaid-gitgraph`), Sankey Diagram (`mermaid-sankey`) |
| Hierarchy | Mindmap (`mermaid-mindmap`) |
| Journey | User Journey (`mermaid-journey`) |
| Project | Gantt Chart (`mermaid-gantt`), Timeline (`mermaid-timeline`) |
| Relationship | Entity Relationship (`mermaid-er`), Requirement Diagram (`mermaid-requirement`) |
| Sequence | Sequence Diagram (`mermaid-sequence`) |
| Structure | Class Diagram (`mermaid-class`), Quadrant Chart (`mermaid-quadrant`), Pie Chart (`mermaid-pie`), C4 Context (`mermaid-c4context`) |


### 9.1 `type` — the built-in chart types (core, all loaded)

`bar` · `line` · `doughnut` · `pie` · `radar` · `polarArea` · `scatter` · `bubble`. Everything else is one of these
with option/dataset tweaks (no separate type):

| You want | How | Starter |
|---|---|---|
| Vertical column | `type:'bar'` | Column |
| **Horizontal bar** | `type:'bar'` + `options.indexAxis:'y'` | Bar (Horizontal) |
| **Grouped bar** | `type:'bar'` + several `datasets[]` | Grouped Bar |
| **Stacked bar** | `type:'bar'` + `scales:{x:{stacked:true},y:{stacked:true}}` | Stacked Bar / 100% Stacked |
| Area | `type:'line'` + dataset `fill:true` | Area |
| Multi-line | `type:'line'` + several datasets | Multi-line |
| **Combo (bar+line)** | `type:'bar'` + a dataset with its own `type:'line'` (+ `yAxisID` for a 2nd axis) | Combo |
| Sparkline | `type:'line'`, hide axes/legend, small height | Sparkline |
| Time-series | `type:'line'` + `scales:{x:{type:'time'}}` (date-fns adapter IS loaded) | Time-Series Line |
| KPI vs target / gauge | **use Plotly `indicator`** (§6/Recipe D) — Chart.js gauge plugin is NOT loaded (§2.5 ⚠) | — |

Full starter list (copy one): Column, Bar (Horizontal), Grouped Bar, Stacked Bar, 100% Stacked Bar, Line, Multi-line,
Area, Stacked Area, Combo (Bar + Line), Pie, Doughnut, Polar Area, Radar, Scatter, Bubble, Histogram, Sparkline,
Horizontal Stacked Bar, Time-Series Line, Stepped Line, Waterfall, Diverging Bar, Bullet (KPI vs Target), Range Bar,
Nested Doughnut, Scatter with Trendline, Multi-Series Radar, Stacked Bars + Line.


### 9.2 `data` — labels + datasets (this is what you bind to `$$()`)

- **`data.labels`** — the category axis (bar/line/radar/doughnut). Bind to a **`String[]`** replacement:
  `labels: $$('Labels', ['-'], 'String[]')` → column of category names. (Scatter/bubble use no `labels`; they take
  `{x,y}` point objects — build them in JS by mapping two `Double[]` replacements, as the Scatter starter does.)
- **`data.datasets[]`** — one entry per **series**. Each has a **`data`** array bound to a numeric replacement
  (`data: $$('Values',[1],'Double[]')`) plus styling. Multiple series = multiple datasets, each with its **own**
  `$$()` (each pulls a different column, usually from the same query). Common dataset keys:

  | Key | Applies to | What |
  |---|---|---|
  | `label` | all | series name (legend/tooltip) — a `String` or a static string |
  | `data` | all | the values — bind to `Integer[]`/`Double[]` (§2.3); scatter/bubble = `[{x,y}]`/`[{x,y,r}]` |
  | `backgroundColor` | all | fill — one color (bar/line) or an **array** (doughnut/pie, one per slice — map by LABEL not index, §6.1) |
  | `borderColor` | line/radar/bar | stroke |
  | `borderWidth` / `borderRadius` | bar/doughnut | outline / rounded bars |
  | `tension` | line | curve (0 = straight, 0.3 = smooth) |
  | `pointRadius` / `pointBackgroundColor` | line/radar/scatter | marker size/color |
  | `fill` | line | `true` = area chart |
  | `stack` | bar/line | group name for stacking |
  | `type` | in a combo | override this dataset's type (`'line'` inside a `type:'bar'` chart) |
  | `yAxisID` | dual-axis combo | bind the series to a named second scale (`scales:{y1:{position:'right'}}`) |

### 9.3 `options` — layout, axes, legend, title, tooltip

| Option | Values / meaning |
|---|---|
| `responsive` | `true` — resize with the container (always set it) |
| `maintainAspectRatio` | `false` — fill the (fixed-height) wrapper; **required** with the `position:relative;height:…` `<div>` |
| `indexAxis` | `'x'` (default, vertical) or **`'y'`** (horizontal bar) |
| `plugins.legend` | `{ display: true/false, position: 'top'/'right'/'bottom'/'left' }` |
| `plugins.title` | `{ display: true, text: 'Title', font: { size: 16 } }` |
| `plugins.tooltip` | `{ enabled, callbacks:{ label:function(ctx){…} } }` — customise hover text |
| `plugins.datalabels` | ⚠ **needs the datalabels plugin, which is NOT loaded** (§2.5) — omit, or use Plotly/ECharts |
| `scales.x` / `scales.y` | `{ beginAtZero:true, stacked:true, title:{display,text}, ticks:{stepSize,callback}, type:'linear'/'category'/'time', position:'bottom'/'right', min, max, grid:{display} }` |
| `scales.r` | the **radial** scale for `radar`/`polarArea` (`{ beginAtZero:true }`) |
| `onClick` / `onHover` | function hooks — `onClick` is where **cross-filter** goes (§5); the affordance chains onto `onHover` automatically |

**Theme + color:** Chart.js canvas is transparent → inherits the theme (§6). For a semantic categorical axis
(status/risk) map `backgroundColor` **by label**, not by position (§6.1). Use the verified palette in §6, step 3.

**Binding rule of thumb (repeat of §2.3 in Chart.js terms):** `data.labels` → `String[]`; each `dataset.data` →
`Integer[]` or `Double[]`; a single KPI number → `Double[]` then `[0]` in JS. `columnName` on each replacement is the
(lowercased) result column that feeds that array.

> **ECharts / Plotly settings** follow their own libraries' option objects (`echarts` `setOption({…})`, `Plotly.newPlot(el,
> data, layout, config)`) — the `$$()` binding + theme rules are identical; only the option schema differs. Copy the
> matching starter from the gallery (§8) for the exact shape, and keep Plotly theme-safe (§6). This doc details the
> Chart.js config because it is the default engine; the other two are option-compatible with their upstream docs.

---

## Gotchas

1. **`group` must match `js` byte-for-byte.** Substitution is a literal `js.replace(group, value)`, and the
   re-parse on every render syncs `name`/`type` but **never `group`**. A stray space/quote-style difference
   between `group` and the `$$()` in `js` → no substitution → the placeholder renders as its JS default via
   `window.$$` (that series/axis is silently empty). `validate` **warns** on this one.
2. **`columnName` is lowercased.** Postgres folds unquoted identifiers, so an alias `monthSN` is column
   `monthsn`. Match the *result* column name, not the SQL alias casing.
3. **`default` must be a single element (no commas).** The tokenizer `split(",")`s the `$$()` args, so write
   `['-']`, `[1]`, `[0]`, `[]` — not `[1,2,3]`.
4. **`Full` type has no `columnName`** — it injects the whole rowset as JSON; you shape it in JS. Array types
   need `columnName`.
5. **Only `QUERY` replacements are filterable.** `LABEL` replacements never register with the filter bar,
   so a value you want the user to filter must come from a `QUERY` replacement.
6. **The filter bar stores nothing** and must be on the **same page** as the charts (the event bus is
   page-scoped). No `global.replacement.plugin` node → no filter UI and cross-filter has no target.
7. **One name in five places.** SQL placeholder `name` == query `parameters` key == filter control == session
   `paramKey` == `crossFilter('<field>')`. A typo in any one silently breaks filtering (§4.2).
8. **`dropDownPopulation.query` is resolved by name** — the lookup query must also exist in the project
   (it is referenced by `query:'Projects Query'`, not by id).
9. **`parameters` is a seed, not a declaration.** Params are declared in the SQL text; the `parameters` map only
   carries a preview/current value. `query add` always writes `{}` — populate the seed by hand on the embedded
   chart-replacement query copy if you want a default filter state.
10. **`validate` DOES vet the chart blob now — know exactly how far it goes.** It parses
    `properties.Javascript` and runs these chart checks:

    | Verdict | What it catches |
    |---|---|
    | **ERROR** | `properties.Javascript` is not valid JSON (the chart would render as a blank "Modify html" cell) |
    | **ERROR** | a replacement's embedded `query` carries any field outside the safe ~12 (§1.1 ⛔) |
    | **ERROR** | chart config written into `properties.settings`/`properties.model` instead of `Javascript` |
    | **WARN** | a QUERY replacement (not `Full`/`Json`) with an empty `columnName` |
    | **WARN** | a replacement `group` that is not a byte-for-byte substring of `js` (Gotcha 1) |
    | **WARN** | `js` uses Plotly but never sets `paper_bgcolor` (comments stripped first) |
    | **WARN** | `crossFilter('X', …)` where no chart on that page declares `{name:'X'}` in SQL |
    | **WARN** | a `global.replacement.plugin` on a page whose charts declare no SQL param (an inert bar) |
    | **WARN** | a page with ≥3 charts that also hosts a data table (a dashboard should be charts only) |

    What it still **cannot** see, and you must check by eye or live: `queryIdentifier` pointing at a query that
    exists; `columnName` matching a real **result** column of that SQL; whether the SQL parses in both its
    substituted and its `1=1`-neutralised form (§3.1 ⛔); the chart's per-theme CSS (never colour-linted, §6);
    the drill chain (§5.1); and — always — whether the page actually **renders**. A clean validate is a floor,
    never a proof (doc 23).
11. **Config lives in `properties.Javascript`, never `model`/`settings`.** `node add --plugin chart.js.plugin`
    auto-routes; `node set-model` would write the wrong slot.
12. **The Caching tab works — but it is result CACHING, not a refresh schedule.** Setting a cron on the tab
    writes `model.schedule` **and copies that same `ScheduleDto` onto every replacement's embedded
    `query.schedule`**. That copy is what does the work: when the query service runs a query that carries a
    schedule expression, it **stores the result** and serves every later identical run from that store instead of
    hitting the database. So the observable effect is: **the first render pays for the SQL, subsequent renders are
    instant.** What to expect, precisely:
    - The **cache key is the whole query, parameters included** — a different filter value is a different entry,
      so a filtered dashboard caches per filter combination and a fresh combination still hits the DB once.
    - The cron **cadence is not a refresh timer**: nothing re-executes the query when the expression fires. Cached
      rows are served until the project's query cache is cleared or the query service restarts. Treat the
      expression as "how stale I am willing to be", and pick caching only for data whose staleness is acceptable.
    - It is a **per-service in-memory** store, not shared or persisted — do not rely on it for correctness.
    - ⛔ **Do NOT hand-author caching into the `.mrjun`.** The effect needs the schedule on each *embedded*
      `replacements[].query`, but `schedule` is one of the rep-object fields that must never appear inside an
      embedded query (§1.1): it breaks the model's deserialization, which is swallowed and leaves you with a
      blank "Modify html" cell, and `validate` ERRORs on it. Ship the chart with `"schedule": {"job": {}}` on the
      model and, if you want caching, **turn it on in the live Caching tab after import** — the tab writes both
      halves consistently. For a genuinely periodic recompute, use the general scheduler
      ([12](12-queries-sources-schedulers-and-rest.md)) to refresh the underlying table/materialised view.
    - Leave `schedule` empty (`{"job":{}}`) — an empty object means "no caching", which is the right default for
      a live dashboard.
13. **Only CORE chart libraries load** (§2.5 ⚠). `chartjs-plugin-datalabels`, `chartjs-plugin-zoom`,
    `chartjs-plugin-annotation` and the `chartjs-gauge` type ship as static files but the chart plugin does **not**
    load them — a chart that references them renders empty/throws. Use core Chart.js types (§9.1); for gauges/KPI use a
    **Plotly `indicator`** or ECharts `gauge`; for on-bar data labels use Plotly/ECharts.
14. **`maintainAspectRatio:false` needs a sized wrapper.** With it (the norm), the canvas fills its parent, so the
    `html` MUST be a **`position:relative` div with an explicit height** (`<div style="position:relative;height:320px;">
    <canvas></canvas></div>`). Omit the height and the chart collapses to **0 px and shows blank** — a layout bug that
    looks exactly like a data/binding failure but isn't.
15. **The chart type is not a field.** There is no `type`/`engine`/`chartType` on `ChartJsModel` (§2.5); what draws is
    decided by the JS you write (`new Chart(ctx,{type:'…'})` / `Plotly.newPlot` / `echarts.init`). To change a chart's
    type you edit its `js`, not a setting.
16. ⛔ **Chart text is a LOCALIZATION DEAD ZONE.** A chart's config is **one non-localized string** in the node's
    `Javascript` property: there is no per-locale map for `js`/`html`/`cssByTheme`, and the plugin reads the plain
    value, never a locale-specific one. So every title, axis label, legend entry, tooltip string and annotation you
    type into `js` renders **identically in every language**. (The only localized pieces around a chart are the
    platform's own strings — e.g. the "Click to filter" badge.) Work with it, don't fight it:
    - **Best:** make the *data* carry the text — a `String[]` replacement whose SQL returns already-translated
      labels (join a translations table, or `CASE` on a locale column), so the chart is a dumb renderer. Note the
      cross-filter caveat: if labels are localized, the clicked label no longer equals the DB value (§5.2 ⚠) —
      cross-filter on the raw value instead.
    - **Acceptable:** avoid chart-internal text — no `plugins.title`, no axis titles — and put the heading in the
      surrounding page markup (a `nct.html.plugin` or the page title), which **is** localizable (doc 20).
    - **Last resort:** one chart node per language, gated by the page's locale — expensive to maintain; use only
      when a single chart must show heavily-worded content.
    Cross-reference: [20](20-localization.md) is the localization reference — chart `js`/`html` text is **outside**
    every mechanism it describes (no `localizedStringValue`, no per-locale map, no message key).
17. **The chart body arrives in a second AJAX round-trip** (§2.4). At page `domready` the chart's
    `<canvas>`/`<div>` does not exist yet — any script that expects to find it then will not. Put element code in
    the chart's own `js`.
18. **Read the toasts.** A failed replacement does not blank the page: the chart draws with its `$$()` defaults and
    the platform raises up to **10** toasts naming the **chart node** and the cause (§2.4). "Chart shows a flat
    default line + a toast" = binding/query failure, not "no data". Give every chart node a distinct, meaningful
    name so the toast identifies it.
19. **A `LABEL` value is spliced in raw** unless the declared `type` is exactly `String` (§2.3) — a non-JS value
    there is a syntax error that takes down the whole chart script.
20. **Chart CSS is scoped and un-linted.** `cssByTheme` is auto-scoped to the chart instance (so plain selectors
    are correct and an id/`:root` selector is rewritten), but nothing colour-lints it and it **cannot reach the
    canvas** — plot colours come from the chart config, not CSS (§6). An inline `<style>` in `html` is the
    opposite: global, un-themable, and it leaks onto other components.

21. **⛔ What must be valid JavaScript is the SUBSTITUTED `js`, not the text you authored.** The panel does
    `js.replace(group, value)` for every replacement and then hands the result to **`new Function(js)`**
    (`ChartJsServiceImpl.replaceJs` → `ChartJsPanel.renderChartConfig`). So a config assembled by string
    concatenation — the normal way a generator builds `var cfg = { … };` — can be **one brace short** and still
    pass every offline gate: the JSON is valid, `group` is a byte-for-byte substring (Gotcha 1 is happy), the
    export imports **0 errors**, the page loads, the query runs. The only symptom is in the browser console:

    ```
    SyntaxError: Unexpected token ';'
        at Function (<anonymous>)
        at rv.renderChartConfig (ChartJsPanel-….js:106)
    ```

    and the chart area is blank. LIVE-FOUND 2026-09-05: a generator grew a second axis on its bar template, the
    added `y:{…}` swallowed the closer that used to end the `cfg` object, and **48 of 87 charts on eight boards
    were dead** — with `validate` green and every SQL executed. The failure scales with the generator: one bad
    template kills every chart built from it, which is why it reads as "the whole dashboard is broken".

    `validate` now parses it for you (`_check_chart_js_parses`, ERROR): it substitutes each `group` — once with
    a value, once with the replacement's own `defaultValue`, because §2.4 says a failed or empty query ships the
    default — and runs `node --check` when node is on PATH, falling back to a bracket-balance scan when it is
    not. Author-side rule of thumb: **count the closers**. `var cfg = { data:{…}, options:{ plugins:{…},
    scales:{ x:{…}, y:{…} } } };` ends in `} } } };` — one for `y`'s parent `scales`, one for `options`, one for
    `cfg`, then the semicolon; adding an axis adds a `}` **inside** `scales`, never at the end.
