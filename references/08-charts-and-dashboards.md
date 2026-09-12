# 08 — Charts and dashboards

> **Corrects and extends** [[22-charts-params-and-filters.md](../22-charts-params-and-filters.md)](../22-charts-params-and-filters.md).
> Doc 22 is the mechanism; this is the measured practice: **185 `chart.js.plugin` nodes across four
> deliveries — 168 of them distinct** (one delivery mounts the same chart on more than one page), counted
> and diffed. Sources are letters (§README): **C** built 8 boards / 87 charts and is
> the flagship; **B** built 4 boards / 31 charts and has the strictest colour system; **D** built 2 boards /
> 12 charts and is the cleanest to read; **A** built no chart grid at all — its 38 distinct charts are
> single tiles embedded in hand-built consoles, and it is the only delivery that solved in-canvas
> localization.
> Ratios below (`n/n`) are over the 185 nodes unless they say *distinct*.

---

## 0. What is true in all four

- Every chart's `js` opens with a **theme prelude** that reads live colours off the mounted element —
  185/185 contain `getComputedStyle`.
- The config lives in `properties.Javascript` as a JSON-encoded `ChartJsModel`; 185/185 decode cleanly.
- The embedded `replacements[].query` is the **field trim** — **409 of 429 carry the same 12 keys**, the
  other 20 (all in one delivery) carry 11 because they omit the null `id`. **Not one of the 429 carries a
  rep-object field**, which is the point: the trim, not the exact arity.
- **The author-time drill chain is never used: `futureReplacements` is absent from all 185 chart models.**
  The key does not appear at all — do not spend effort on it.
- **`schedule` is an untouched skeleton on all 185.** `{"job":{}}` on 159, `{"enabled":false,"job":{}}` on
  10, a `cooldownJob` stub on 8, absent on 8 — and `schedule.job` is empty in **185 of 185**. Nobody
  hand-authors caching.
- A chart node is **never** styled with a card frame of its own — the frame belongs to the page markup.

And in the three that have a period filter:

- the period parameter is named `Since` and compared with **`>=`** — 284 `{name:'Since'…}` placeholders,
  **284 of them preceded by `>=` and none by a bare `=`** (the 516 bare `=` in the corpus belong to other,
  equality-valued parameters);
- exactly **one** `global.replacement.plugin` per board, with **no** config;
- the chart's visible title is a **sibling `nct.label.plugin`** — **0 of their 130 charts** put a title in
  `plugins.title` (only 2 charts in the whole corpus do, both in the fourth delivery).

---

## 1. Composing a board

### 1.1 The node spine

Identical in all four; only the shaded part is yours:

```
siteMapPage  "<Board name>"
└── parsis.plugin
    └── html.plugin  "Layout"                      ← site chrome, untouched
        └── nct.parsis.plugin  "parsis"            ← THE PAGE SLOT
            ├── nct.html.plugin           "<board> header"      → h1 + muted subtitle (label nodes)
            ├── global.replacement.plugin "<board> filters"     → the filter bar, no config
            ├── nct.html.plugin           "<board> filter hint" → one muted sentence (label)
            ├── nct.html.plugin           "KPI band"            → 4 tiles
            ├── nct.html.plugin           "<board> row 1"       → card + heading + 2–3 chart cells
            └── nct.html.plugin           "<board> row 2" …
```

✅ **One `nct.html.plugin` per BAND, not one per board.** Two deliveries put the whole grid into a single
6 KB one-liner; one splits it into header / hint / KPI band / row 1 / row 2. The split wins: editing row 2
does not re-emit the KPI band, and a broken row damages one node instead of the page.

### 1.2 `<plugin id=…>` resolves on the child's `identifier`

The single most load-bearing detail, and easy to get wrong — the node also carries `id`,
`uniqueIdentifier` and `name`, and none of those is the one that matches.

```jsonc
// in the grid node's html
"<div class=\"col-md-6 col-xl-4\"><plugin id=\"r1c2\" name=\"nct.parsis.plugin\"></plugin></div>"

// the child it fills
{ "pluginName": "nct.parsis.plugin",
  "name":             "r1c2",          // author-facing; keep it the same string
  "identifier":       "r1c2",          // ← THIS is what <plugin id> matches
  "id":               "d46fe60a-…",    // surrogate, reassigned at import
  "uniqueIdentifier": "7b34145b-…" }   // refresh/drill target, unrelated
```

`identifier` is a free string, not a uuid. ✅ **Use readable slot names** — `r1c2`, `kpi3`, `row-trend-hdr`
— not generated uuids. Pair a caption to its chart by construction: cell `r1c2`, chart `r1c2`, title
`r1c2-t`, subtitle `r1c2-s`. That scheme survives being read six months later.

### 1.3 Hang the chart in a `nct.parsis.plugin` cell

One delivery points `<plugin id>` straight at the chart node; two wrap it in a parsis cell. ✅ **Wrap it.**
The wrapper costs one node and buys a cell you can add a caption, a "no data for this filter" label or a
drill link to — without re-emitting the grid HTML.

### 1.4 The grid, as shipped

```html
<div class="container-fluid px-0">

  <!-- KPI band: no header, four equal cells -->
  <div class="main-card mb-3 card"><div class="card-body py-3">
    <div class="row g-4 align-items-start">
      <div class="col-md-6 col-xl-3">
        <div class="text-center small text-muted text-uppercase" style="letter-spacing:.04em;">
          <plugin id="kpi1-t" name="nct.label.plugin"></plugin></div>
        <plugin id="kpi1" name="nct.parsis.plugin"></plugin>
      </div>
      <!-- ×4 -->
    </div>
  </div></div>

  <!-- a section: ONE card, a heading label, cells of UNEQUAL width -->
  <div class="main-card mb-3 card">
    <div class="card-header">
      <i class="header-icon lnr-diamond icon-gradient bg-plum-plate"></i>
      <plugin id="sec1-hdr" name="nct.label.plugin"></plugin>
    </div>
    <div class="card-body"><div class="row g-4">
      <div class="col-md-12 col-xl-5">
        <div class="d-flex justify-content-between align-items-center mb-2" style="min-height:1.6rem;">
          <span class="fw-semibold" style="font-size:.95rem;">
            <plugin id="r1c1-t" name="nct.label.plugin"></plugin></span></div>
        <plugin id="r1c1" name="nct.parsis.plugin"></plugin>
      </div>
      <div class="col-md-6 col-xl-4"> … </div>
      <div class="col-md-6 col-xl-3"> … </div>
    </div></div>
  </div>

</div>
```

Measured column vocabulary: `col-md-6 col-xl-3` (KPI) · `col-md-6 col-xl-4` (doughnut, ranked bar) ·
`col-md-12 col-xl-5` (medium bar) · `col-md-12 col-xl-7/-8` (time series, combo) · `col-md-12 col-xl-12`
(a full-width funnel). Rows run 4 / 3 / 2 / 3 / 1 — **never 2,2,2,2**.

- ✅ **`col-md-* col-xl-*`**, not `col-12 col-lg-*`: the `lg`-only pair jumps straight from full width to the
  final layout at 992 px, so a laptop gets the 1440 layout.
- ✅ **`g-4` inside cards, `mb-3` on cards** — `g-4` sets the horizontal gutter too, so it is one class
  instead of relying on the framework default.
- ⚠️ **`min-height:1.6rem` on the caption row is not decoration.** It keeps plot tops aligned when one
  caption wraps to two lines and its neighbours do not. Ragged tops read as a rendering bug.

---

## 2. The chart node

### 2.1 The verified model

```jsonc
{
  "id": "<uuid>",
  "html": "<div class=\"ck-plot\" style=\"position:relative;height:340px;padding-top:20px;\"><canvas></canvas></div>",
  "js":   "…",
  "cssByTheme": { "*": "…", "Dark": "…", "Dark Blue": "…", "Dracula": "…", "Forest": "…" },
  "schedule": { "job": {} },
  "replacements": [ … ]
}
```

Mount heights that actually work (they are why `maintainAspectRatio:false` behaves): KPI number **92–118 px**
· gauge **150 px** · standard chart **300–340 px** · wide funnel or full-row bar **380–440 px**.

### 2.2 The replacement, field for field

429 of them, all this shape:

```jsonc
{ "name": "Labels",
  "group": "$$('Labels', ['-'], 'String[]')",   // byte-for-byte the text in js
  "type": "String[]",
  "replaceStrategy": "QUERY",
  "queryIdentifier": "<Q>",
  "query": { /* exactly 12 keys */ },
  "columnName": "label",
  "defaultValue": "['-']",
  "order": 0,
  "maxItemsCount": 1000,
  /* no `futureReplacements` key — it is absent in all 185 */ }
```

The embedded query carries exactly: `aggregations, attributes, clientName, id, identifier, itemsPerPage,
name, offset, parameters, query, realmName, sourceIdentifier` — with `attributes: {}`,
`aggregations: {"aggregations":[],"groupByList":[],"orderByList":[]}`, `offset: 0`, and ✅ **`"id": null`**
(it works, matches the field list `validate` expects, and removes one more thing that can go stale).

✅ **`maxItemsCount` is a design lever, not boilerplate.** `1000` for an ordinary series; **`1` for every
KPI tile** whose query is an aggregate with no `GROUP BY` — free insurance that a later `GROUP BY` cannot
turn the tile into "the first of many"; the axis length (e.g. `12`) for a fixed-window series.

### 2.3 ⛔ `query.parameters` ships the author's last preview pick

`parameters` is a seed, and the editor writes whatever you were previewing straight into the node. Nothing
clears it. Two of four deliveries shipped one: a front board that **opens pre-filtered to a single
partner**, and another pre-filtered to one category — every KPI, every bar. A reviewer's first impression is
a dashboard whose numbers do not match the data. It is also a quiet **data-leak channel**: a real value is
baked into shipped JSON where nobody looks. The boards that were generated and never opened are clean.

**Rule: before `pack`, every embedded `query.parameters[*]` is `{}` or `{"value": null}`.**

```python
import json
d = json.load(open('work/branches.json'))
def walk(n, out):
    if n.get('pluginName') == 'chart.js.plugin':
        m = json.loads(n['properties']['Javascript']['stringValue'])
        for r in m.get('replacements') or []:
            for k, v in ((r.get('query') or {}).get('parameters') or {}).items():
                if v.get('value') not in (None, ''):
                    out.append((n['name'], k, v['value']))
    for c in n.get('children') or []: walk(c, out)
out = []; [walk(b['rootContent'], out) for b in d]
for r in out: print('SEEDED FILTER:', *r)
```

Fix by rewriting the value to `null`, not by deleting the key — the key documents which params the chart
declares.

---

## 3. The three-column contract: **Labels · Ids · Values**

The most valuable shape in the corpus. The SQL returns a display label **and** the raw code **and** the
measure; the JS binds all three.

```sql
SELECT u.name     AS unit,        -- display: human, already readable
       u.id::text AS unit_id,     -- code: what WHERE compares against
       count(*)   AS cnt
FROM   <fact> f LEFT JOIN <dimension> u ON u.id = f.unit_id
WHERE  1=1 AND f.deleted = false
  AND  to_char(f.happened_at,'YYYY-MM') >= {name: 'Since', type: 'dropdown-string',
         dropDownPopulation: {query: 'Since Lookup', value: 'period', name: 'period'}}
  AND  f.category_id::text = {name: 'Category', type: 'dropdown-string',
         dropDownPopulation: {query: 'Category Lookup', value: 'value', name: 'name'}}
GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 12
```

```js
var labels = $$('Labels', ['-'], 'String[]');   // columnName: unit
var ids    = $$('Ids',    ['-'], 'String[]');   // columnName: unit_id
var values = $$('Values', [0],   'Integer[]');  // columnName: cnt
```

It solves three problems that otherwise fight each other:

1. **Humanised axis text** — the label column can be `coalesce(<lookup>.label, <col>)`, so no
   `SCREAMING_SNAKE_CASE` reaches the screen.
2. **Semantic colour that survives filtering** — the colour map is keyed on `ids[i]`, the stable code, never
   on a translated label.
3. **A cross-filter click that matches a row** — `crossFilter('Unit', ids[i])` sends the database value.
   Doc 22 §5.2 warns that a localized label breaks the click; **this is the fix**, and it deserves to be a
   recipe rather than a warning.

The same handler serves a time axis by simply setting `var ids = null;` — then it falls back to the label,
which for a month axis *is* the value.

### Humanising an enum — two working forms

**(a) A vocabulary table, joined.** One `refLabel(vocabulary, code, label, sort_order)` register for the
whole project; `sort_order` is what makes a status axis come back in lifecycle order instead of
alphabetical. Best when the vocabulary is large or user-edited.

```sql
LEFT JOIN (SELECT * FROM <schema>.ref_label WHERE deleted = false) rl
       ON rl.vocabulary = 'category' AND rl.code = f.category
SELECT f.category AS cat_code, coalesce(rl.label, f.category) AS cat_label, …
GROUP BY 1, 2, rl.sort_order ORDER BY rl.sort_order
```

**(b) An inline `VALUES` join** — no table, no migration, and it can carry every locale so that adding a
language later changes only the SELECT:

```sql
LEFT JOIN (VALUES ('CRITICAL','<hy>','<ru>','Critical',1),
                  ('HIGH',    '<hy>','<ru>','High',    2),
                  ('MEDIUM',  '<hy>','<ru>','Medium',  3),
                  ('LOW',     '<hy>','<ru>','Low',     4)
) AS pl(code,hy,ru,en,ord) ON pl.code = f.severity
SELECT COALESCE(pl.en,'<fallback>') AS severity,
       COALESCE(f.severity,'(not assessed)') AS severity_code, count(*) AS cnt
GROUP BY 1, 2, pl.ord ORDER BY pl.ord NULLS LAST
```

⚠️ **`COALESCE` the code column too.** A SQL `NULL` in a `String[]` binds as the literal string `'null'` and
becomes a slice labelled *null*. Coalescing both columns fixes it, and giving `'(NOT ASSESSED)'` its own
entry in the colour map makes the grey deliberate rather than a fallback.

### Two series from one query

Either pivot in SQL and bind one `$$()` per series —
`count(*) FILTER (WHERE f.severity = 'CRITICAL') AS critical` — or return a long `(key, series, value)`
triple and pivot in JS. Both ship. Prefer the SQL pivot for a fixed, small set of series (it keeps the JS
dumb); prefer the long form when the series set is data-driven.

---

## 4. Cross-filtering

34 cross-filter charts, one shape, no second dialect:

```js
cfg.options.onClick = function (e, els) {
  var v = null;
  if (els && els.length) { var i = els[0].index;
    v = (ids && ids[i] != null) ? ids[i] : this.chart.data.labels[i]; }
  this.crossFilter('<P>', v);              // v === null  ⇒  clears the filter
}.bind(this);
cfg.options.onHover = function (e, els) {
  if (e && e.native) e.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
};
var ctx = this.$find('canvas')[0].getContext('2d');
this.chart = new Chart(ctx, cfg);          // construct LAST — handlers on cfg, never on chart.options
```

Things that only surface after reading 34 of them:

- **`.bind(this)` is mandatory, and it is what makes `this.chart.data.labels` work as well.** Inside the
  bound handler `this` is the panel and `this.chart` is the field the last line assigns; both uses depend on
  the same binding.
- **One `crossFilter` per handler.** Two would be two round-trips racing.
- **The affordance is authored, never inherited** — 34/34 set the hover cursor, and the better ones also set
  `this.$find('canvas')[0].title = '<Click to filter>'`, the only hint a reader gets before hovering.
- **A board needs one selector per parameter, not one per chart.** Thirteen charts with seven handlers is
  not more interactive than nine charts with two — it is more ways to disagree.
- **Clicking empty canvas must clear.** That is what the `v = null` branch is for; without it a filter set
  by a click can only be cleared from the filter bar.

---

## 5. Colour

Distinct hexes per delivery: **14** across 87 charts (a real board palette) · **24 = 2 themed variants × 12
tokens** across 31 (the best system) · 14 with drift across 12 · 35 ad hoc across the outlier's legacy set.

### ✅ The token bridge — the one technique strictly better than doc 22

Doc 22 says "there is no shared palette object, and `cssByTheme` cannot reach inside the canvas". Both
halves are true, and one delivery found the way around them: `cssByTheme` cannot *paint* the canvas, but it
can *carry values the JS reads*. One identical block, pasted into every chart of the board:

```jsonc
"cssByTheme": {
  "*":         ".ck-plot{--c1:#173C60;--c2:#C2703A;--c3:#2E7D5B;--c4:#B98A1E;--c5:#7A5EA6;--c6:#4E93C4;--c7:#8C5A4A;--c8:#B5485A;--c-good:#2E7D5B;--c-warn:#B98A1E;--c-risk:#C2703A;--c-crit:#B5485A;--c-mute:#8A94A0;--r1:#B8D2E6;--r2:#6C96BA;--r3:#2F6FA8;--r4:#173C60;color:var(--bs-body-color);width:100%}",
  "Dark":      ".ck-plot{--c1:#6C96BA;--c2:#E08B54;--c3:#4FBF8B;--c4:#E8C25A;--c5:#A98CD6;--c6:#89C2E8;--c7:#C08A76;--c8:#E0768A;--c-good:#4FBF8B;--c-warn:#E8C25A;--c-risk:#E08B54;--c-crit:#E0768A;--c-mute:#9AA2AD;--r1:#D6E6F2;--r2:#A8C6DE;--r3:#6C96BA;--r4:#3E6D96}",
  "Dark Blue": "…identical to Dark…", "Dracula": "…", "Forest": "…"
}
```

```js
var el = this.$find('.ck-plot')[0];
var cs = getComputedStyle(el);
var V  = function (n, f) { var v = (cs.getPropertyValue(n) || '').trim(); return v || f; };
var C  = [V('--c1','#173C60'), V('--c2','#C2703A'), V('--c3','#2E7D5B'), V('--c4','#B98A1E'),
          V('--c5','#7A5EA6'), V('--c6','#4E93C4'), V('--c7','#8C5A4A'), V('--c8','#B5485A')];
var S  = { good:V('--c-good','#2E7D5B'), warn:V('--c-warn','#B98A1E'),
           risk:V('--c-risk','#C2703A'), crit:V('--c-crit','#B5485A'), mute:V('--c-mute','#8A94A0') };
var GAP = V('--current-line', V('--bs-body-bg','#ffffff'));
```

What pasted hexes cannot do: **the palette lightens on dark skins** (a legible navy on white is a hole on a
dark card); **the `V()` fallback is the light value**, so a chart still renders if the CSS block is ever
dropped; and one edit changes the whole board — it is a duplicated *table*, not thirty scattered decisions,
and a diff proves the copies agree.

### ⛔ Key the colour on the value, never on the row index

| axis kind | correct key |
|---|---|
| verdict (severity, status, on-time) | the **code**, via a literal map |
| one-series ranked bar | one flat tone |
| nominal identity (reason, category) | the **label or code** — never `i % palette.length` |

An index-keyed palette repaints every survivor the moment a cross-filter removes one category. The fix keeps
the tokens and costs two lines:

```js
// ⛔ var qual = function (labels) { return labels.map(function (l, i) { return C[i % 8]; }); };
// ✅ stable slot per value — same colour before and after a filter, on every chart of the board
var QUAL = { '<VALUE A>':0, '<VALUE B>':1, '<VALUE C>':2, '<VALUE D>':3, 'OTHER':7 };
var qual = function (labels, codes) {
  return labels.map(function (l, i) {
    var k = String((codes && codes[i] != null) ? codes[i] : l).toUpperCase().trim();
    var s = QUAL[k];
    return (s == null) ? S.mute : C[s];      // mute = "the map does not know this value"
  });
};
```

```js
// the verdict form, keyed on the raw code so a translated label cannot break it
var MAP = {"CRITICAL":"#8b1a2b","HIGH":"#e0483a","MEDIUM":"#F2BB30","LOW":"#47CC29","(NOT ASSESSED)":"#9aa2ad"};
var key = function (i) { return String(((ids && ids[i] != null) ? ids[i] : labels[i]) || '').toUpperCase().trim(); };
var bg  = (labels || []).map(function (l, i) { return MAP[key(i)] || '#9aa2ad'; });
```

✅ **The third form — colour from a threshold.** Compare each bar with two sibling series from the same
query, and draw those two as reference lines on the same chart. The bar then says *which of these are below
their own limit* instead of *how big is each one*:

```js
var bg = (val||[]).map(function (v, i) {
  var lo = Number((limitLo||[])[i]), hi = Number((limitHi||[])[i]), x = Number(v);
  if (!isFinite(x) || !isFinite(lo)) return '#94a3b8';
  return x <= lo ? '#e0483a' : (x <= hi ? '#F2BB30' : '#47CC29');
});
```

---

## 6. The prelude and the four artefact types

Every chart reads theme colours off its mount. The recommended base — tokens, then formatters, then a
shared options factory:

```js
Chart.defaults.color       = cs.color;
Chart.defaults.borderColor = V('--bs-border-color','rgba(127,127,127,.28)');
Chart.defaults.font.family = V('--bs-body-font-family','system-ui,-apple-system,"Segoe UI",sans-serif');

var nf  = new Intl.NumberFormat(undefined, {maximumFractionDigits:0});
var df  = new Intl.NumberFormat(undefined, {maximumFractionDigits:1});
var cpt = new Intl.NumberFormat(undefined, {notation:'compact', maximumFractionDigits:1});
var num = function (v) { return nf.format(Number(v||0)); };

var pick = function (m,l,f){ var k=String(l==null?'':l).trim().toUpperCase(); return m[k]||f; };
var pv   = function (c){ var p=c.parsed; if (p==null) return 0;
             if (typeof p==='number') return p;
             return (c.chart.options.indexAxis==='y') ? p.x : p.y; };   // one callback, both orientations

var GRID = { color: Chart.defaults.borderColor, drawBorder:false, tickLength:4 };
var base = function (lg) { return {
  responsive:true, maintainAspectRatio:false,
  layout:{ padding:{ top:2, right:6, bottom:0, left:0 } },
  plugins:{
    legend:{ display:!!lg, position:'bottom', align:'start',
             labels:{ usePointStyle:true, pointStyle:'rectRounded',
                      boxWidth:10, boxHeight:10, padding:12, font:{size:11} } },
    tooltip:{ displayColors:true, cornerRadius:6, padding:8,
              callbacks:{ label:function(c){
                return (c.dataset.label ? c.dataset.label+': ' : '') + num(pv(c)); } } } } };
};
```

- ✅ **`Intl.NumberFormat` with `notation:'compact'`** replaces a hand-rolled money formatter repeated in 87
  charts: one line instead of six, and it respects the user's locale for free.
- ✅ **Guard the prelude** (`try { … } catch (e) {}`): a prelude must never take the chart down.
- ✅ **Derive muted text and gridlines from the theme's own foreground** rather than a fixed
  `rgba(128,128,128,.18)` — parse the computed `color` and re-emit it at 0.72 / 0.14 alpha.
- ⚠️ All preludes mutate the page-global `Chart.defaults`, so **the last chart to load wins**. Keep one
  prelude per board.

**What actually gets drawn:** `bar` 76 · `indicator` 49 · `line` 17 · `doughnut` 12, plus one each of `pie`,
`polarArea`, `bubble`. **`indexAxis:'y'` on 56 of the bars — the horizontal bar is the workhorse.** Nobody
used radar, scatter, datalabels, zoom or annotation.

### KPI tiles and gauges

**Number + delta**, with a magnitude-aware unit:

```js
var v = $$('Value',[0],'Double[]')[0], p = $$('Prev',[0],'Double[]')[0];
var a = Math.abs(v||0), div = 1, unit = ' <unit>';
if      (a >= 1e9) { div = 1e9; unit = ' bn <unit>'; }
else if (a >= 1e6) { div = 1e6; unit = ' mn <unit>'; }
else if (a >= 1e3) { div = 1e3; unit = ' k <unit>'; }
Plotly.newPlot(el, [{ type:'indicator', mode:(p == null ? 'number' : 'number+delta'), value:(v||0)/div,
  number:{ font:{ color:'#e0483a', size:34 }, valueformat:'.2f', suffix:unit },
  delta:{ reference:(p==null?null:p/div), relative:false, valueformat:'.2f', position:'bottom',
          font:{size:12}, increasing:{color:'#e0483a'}, decreasing:{color:'#47CC29'} } }],
  { height:118, autosize:true, margin:{t:6,b:6,l:10,r:10},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{color:fg} },
  { displayModeBar:false, responsive:true });
if (window.ResizeObserver) new ResizeObserver(function(){ Plotly.Plots.resize(el); }).observe(el);
```

⛔ **Invert the delta colours on a "less is better" metric.** On a loss or backlog tile an increase is bad,
so `increasing` is red. The default reads backwards on half the tiles of a risk board.

**Gauge with bands and a value-driven colour** — the best KPI shape in the corpus, because the number, the
needle and the band all move together:

```js
var barc = '#9aa2ad';
if (v >=  0 && v <=  50) barc = '#e0483a';
if (v >  50 && v <=  80) barc = '#F2BB30';
if (v >  80 && v <= 100) barc = '#47CC29';
Plotly.newPlot(el, [{ type:'indicator', mode:(p == null ? 'gauge+number' : 'gauge+number+delta'), value:v,
  number:{ font:{ color:barc, size:26 }, suffix:'%', valueformat:'.1f' },
  gauge:{ axis:{ range:[0,100], tickcolor:fg, tickfont:{size:8}, tickwidth:1, nticks:5 },
          bar:{ color:barc, thickness:0.6 }, borderwidth:0, bgcolor:'rgba(0,0,0,0)',
          steps:[ {range:[0,50],  color:'rgba(224,72,58,.18)'},
                  {range:[50,80], color:'rgba(242,187,48,.18)'},
                  {range:[80,100],color:'rgba(71,204,41,.18)'} ] } }],
  { height:150, autosize:true, margin:{t:14,b:6,l:22,r:22},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{color:fg} },
  { displayModeBar:false, responsive:true });
```

`bgcolor:'rgba(0,0,0,0)'` **on the gauge** as well as `paper_bgcolor` is required — otherwise Plotly paints
the gauge's own background white.

⚠️ **Add a `ResizeObserver` to every Plotly mount.** `{responsive:true}` alone does not fire when the
*container* resizes without a window resize — which is exactly what a responsive grid column does. Only one
delivery did this; the others' tiles mis-size on first paint.

✅ **Guard every rate denominator**:
`round(100.0 * count(*) FILTER (WHERE …) / NULLIF(count(*) FILTER (WHERE …), 0), 1)`. Without `NULLIF` an
empty filter state is a division-by-zero toast, not a blank tile.

### The data-bound HTML tile

When a tile needs several unrelated facts, a chip, and a branch on "did anything come back", a Plotly
indicator cannot do it and a canvas is the wrong tool. Bind `Full`, render markup:

```js
var C = this.$component();
var rows = asRows($$('rows', [], 'Full'));
var r = (rows && rows.length) ? rows[0] : null;
var resolved = r && (pick(r, '<a column>') !== null);   // a row arrived but no column resolved ⇒ wrong shape
if (!r || !resolved) {
  C.find('.kpi').html('<div class="kpi-label">'+LBL+'</div><div class="kpi-value">--</div>');
} else {
  C.find('.kpi').html('<div class="kpi-label">'+LBL+'</div>'
    + '<div class="kpi-value">'+ fmt(pick(r,'<a column>'),0) +' <unit></div>'
    + '<div class="kpi-sub"><span class="chip green">'+ sub +'</span></div>');
}
```

Two habits: **escape everything that came from the database** before it reaches `.html()`, and
**distinguish "no rows" from "rows arrived but no column resolved"** — that check is what turns a silent `0`
into a diagnosable state. Style the tile through `cssByTheme` (scoped), never an inline `<style>` in `html`
(global — one delivery's own comment records moving a `<style>` out of a panel after it styled the other
fifteen).

---

## 7. Per-locale text — the dead zone and the three ways round it

Doc 22 is right that a chart's `js` / `html` / `cssByTheme` is one non-localized string. What the corpus
does about it:

| the string is… | technique | why |
|---|---|---|
| board title, section heading, chart title, chart subtitle, filter hint | **a sibling `nct.label.plugin`** | genuinely localizable, and where a scope caveat belongs |
| an axis category or legend entry that is a *data value* | **bring it from SQL**, keyed by locale | keeps the chart a dumb renderer; the only form that scales past three vocabularies |
| dataset label, axis unit, tooltip prefix, empty-state message | **an `L(en, hy, ru)` map in the chart's `js`** | nothing else reaches inside the plot |
| the caption on a filter control | **nothing works** | the caption is the parameter name verbatim — choose a name that reads acceptably and keep it identical in all five places |

The label node, with the two properties that matter:

```jsonc
{ "pluginName": "nct.label.plugin", "identifier": "r1c1-t",
  "properties": {
    "tagName":   { "stringValue": "h6" },   // ⛔ set it — the default <p> margin ruins a card header
    "className": { "stringValue": "mb-0" },
    "text": { "stringValue": "", "localizedStringValue": { "en_US": "…", "hy_AM": "…", "ru_RU": "…" } } } }
```

⛔ **Never put a chart title in the chart's `html`.** One delivery did, in all 12 charts, while its section
headings were proper multilingual label nodes — so the board shows translated headings above untranslated
chart titles the moment the user switches language. Keep the nesting, empty the heading, put a label node
above the chart:

```html
<div class="ck-plot" style="position:relative;height:340px;">
  <div style="position:relative;height:calc(100% - 1.9rem);"><canvas></canvas></div>
</div>
```

⛔ **And never `plugins.title`** — only 2 of the 185 charts use it, and neither is on a board. Doc 22 §2B.5 suggests a title inside the chart;
that advice contradicts its own locale gotcha and every delivery.

---

## 8. What separates a chart that reads from one that does not

Everything here is visible in a screenshot and costs no extra query.

| | the failure when absent |
|---|---|
| `ticks:{precision:0}` on a **count** axis | the axis prints `0.5 / 1.5 / 2.5` of a thing that cannot be halved |
| a compact tick callback on an **amount** axis | a raw `1250000000` on every gridline |
| `tooltip.callbacks.label` naming the measure | "1 : 47" with no unit |
| a **second fact** in the tooltip (share of total) | a count chart stays only a count chart |
| a two-line wrapper on long categories | rotated, clipped, unreadable names |
| `legend:{display:false}` on a one-series chart | a legend that says "Cases" above a chart titled "Cases" |
| `position:'bottom'` on a multi-series legend | a right-hand legend eats a quarter of the plot width |
| `grid:{display:false}` on the category axis | gridlines that mean nothing |
| `interaction:{mode:'index', intersect:false}` on combo/stacked | the reader must hit a 2 px line to get a tooltip |
| hover cursor + canvas `title` on a clickable chart | nobody discovers the interaction |
| an explicit **empty state** | an empty frame reads as broken rather than as "no rows" |

```js
function wrap2(s){ s = String(s == null ? '' : s);
  if (s.length <= 18) return s;                        // Chart.js accepts an ARRAY of lines
  var cut = s.lastIndexOf(' ', Math.ceil(s.length/2) + 6);
  if (cut < 6) cut = Math.ceil(s.length/2);
  return [s.slice(0, cut).trim(), s.slice(cut).trim()]; }
var disp = (labels||[]).map(wrap2);   // bind disp as data.labels …
// … and keep labels/ids for the click, so the wrap never reaches crossFilter
```

```js
// share-of-total tooltip — turns a doughnut into two facts
cfg.options.plugins.tooltip.callbacks.label = function (c) {
  var t = c.dataset.data.reduce(function (a, b) { return a + Number(b || 0); }, 0);
  return c.label + ': ' + num(c.parsed) + (t ? ' (' + df.format(100 * c.parsed / t) + ' %)' : '');
};
```

**The SQL half of "reads well":** `LIMIT 12` on every ranked bar (an uncapped one is a wall) ·
`ORDER BY <sort_order>` for a lifecycle axis and `ORDER BY <measure> DESC` for a ranked one, never
alphabetical · `COALESCE` on both the label and the code · `WHERE 1=1 AND …` so every predicate is uniformly
`AND` and the generated SQL stays diffable · `deleted = false` on **every** fact and dimension — 130/130,
and the safest form on a six-join query is an inline `(SELECT * FROM <t> WHERE deleted = false)` sub-select
so a later join cannot forget it.

---

## 9. The audit set — run before calling a board done

```
 1. every embedded query.parameters[*] is {} or {"value": null}        # 2 of 4 shipped a seeded filter
 2. every chart has a sibling label node for its title; no plugins.title; no <h*> inside the chart html
 3. every multi-series dataset carries a `label`                        # otherwise the legend prints "undefined"
 4. every cross-filter handler is .bind(this), has the null-clearing branch, and sets the hover cursor
 5. one global.replacement.plugin per board; every chart's params ⊆ the bar's params
 6. colour is keyed on a value, never on the row index
 7. every Plotly mount has a ResizeObserver
 8. every rate denominator is wrapped in NULLIF(…, 0)
 9. `deleted = false` on every fact and dimension in every chart query
10. `maxItemsCount: 1` on every single-value KPI
11. no chart node carries its own card frame
12. the board renders on the narrowest supported width — check col-md-* is present, not col-lg-* alone
```

---

## 10. Corrections to [22-charts-params-and-filters.md](../22-charts-params-and-filters.md)

| doc 22 says | the deliveries show | verdict |
|---|---|---|
| `cssByTheme` cannot reach inside the canvas, and there is no shared palette | it cannot *paint* the canvas but it can *carry tokens the JS reads*; one delivery does this on all 31 charts | **extend the doc.** The token bridge is strictly better than pasted hexes |
| a localized label breaks the cross-filter click (a warning) | the Labels·Ids·Values contract fixes it, and 26 charts use it | **promote the warning to a recipe** |
| put the chart title inside the chart, `align:'start'` | 2 of 185 do, neither on a board; it contradicts the doc's own locale gotcha | **doc wrong.** The title is a sibling label node |
| the author-time drill chain (`futureReplacements`) | the key is absent from all 185 chart models | **document it as unused**; the corpus drills with `window.location` from the click handler |
| `maxItemsCount` exists | nobody documents `1` for a KPI, which is free insurance | **add the recommendation** |
| — *(unstated)* | `query.parameters` ships the author's last preview value, and two deliveries shipped a pre-filtered board | **new rule + a pre-pack audit** |
| — *(unstated)* | `{responsive:true}` does not fire on container-only resize | **new rule.** `ResizeObserver` on every Plotly mount |
| — *(unstated)* | the `<plugin id>` slot matches the child's `identifier`, not `id`/`name`/`uniqueIdentifier` | **state it once, in bold** |


---

## Done when

- Every chart honours the **Labels · Ids · Values** contract, so the visible label can be localized without
  breaking the cross-filter click.
- Every chart opens with the **theme prelude** — live colour read off the mounted element — and, where it
  paints a palette, reads it from a `cssByTheme` **token bridge** rather than pasted hex literals.
- Every visible chart title is a **sibling label node**, not a title inside the canvas.
- `query.parameters` has been **scrubbed before packing**: it ships the author's last preview value, and two
  deliveries shipped a board pre-filtered to whatever the builder was looking at.
- Every Plotly mount has a **`ResizeObserver`** — `{responsive:true}` does not fire on a container-only resize.
- Every KPI query carries **`maxItemsCount: 1`**.
- One `global.replacement.plugin` per board, no config, and the period parameter compared with `>=`.
- The board has been opened on **Standard and on a dark skin**, and the numbers have been read against the
  register they come from. A chart that renders is not a chart that is right.
