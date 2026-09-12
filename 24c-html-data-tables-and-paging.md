# 24c · Data tables in an HTML component — server-side paging, sorting, filtering

> 📐 **Field evidence — how paging was really done — the corpus contradicts this doc:** [09-studio-components.md](references/09-studio-components.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> Read this **before** you hand-write a `<table>` inside an `nct.html.plugin` studio component.
> Scope: the data contract between a custom widget and the platform (what you may call, what comes back),
> the reference page rule, the reference script, the reference markup, and the performance budget.
> It EXTENDS [24](24-html-component-studio.md) (the studio itself: `studioModel`, `ctx.*`, libs, CSS)
> and does **not** repeat it. If the answer is "just use the table plugin" — that is [04](04-crud-table-plugin.md),
> and §1 below tells you when it is.
>
> ⛔ **A hand-built table that fetches every row is a demo, not a screen.** The single most common failure mode
> in hand-built studio tables is a data rule of the shape
> `findAll([rowsInPage: 1000|2000|5000, pageNumber: 0])` with **no** `count`, **no** `totalElements`, **no**
> pager and **no** filter pushed down: a fixed page size big enough to "cover" the seeded data, `pageNumber`
> pinned at `0`, and not one call to `count` or to the paged `find` wrapper anywhere in the component. It looks
> perfect on a seeded table of a dozen rows and dies on 130 000. Audit your own build with one grep over the
> rules your screens call: every `findAll(` must take its page size and page number from the caller, and every
> screen that shows a total must reach `count`.

| | |
|---|---|
| Host plugin | `nct.html.plugin` with a non-empty `properties.studioModel` — [24](24-html-component-studio.md), [14 §1.1](14-plugin-catalog-all.md) |
| Data in | `await ctx.callRule('<rule>', {…})` → the studio's rule bridge (`HtmlStudioSupport.executeRule`); `await ctx.callBl(alias, method, args)` → `executeBl` → `ReactorCrudService.executeCrudMethod` |
| Page envelope | `{content, totalElements, totalPages, pageNumber}` — assembled in Java by `DynamicMethodExecutor.executeAutoFindWrapper` |
| Transport | one **blocking** Wicket round-trip per call (the runtime posts through richwicket's `ajax`, whose `async` defaults to `false`; the sync supporter's callback script sets `setAsynchronous(false)`) |
| Config slots | script → `studioModel.scripts[].code`; CSS → `studioModel.css.byTheme["*"]`; markup → `properties.html.stringValue` |

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `node add --parent <page> --plugin nct.html.plugin --name "<Screen> UI" --identifier <symbolic>` (the host node),
> `node set-studio <id> --json @studioModel.json` (script + CSS; the CLI picks the `studioModel` slot),
> `rule add --name "<Screen> Page" --type EXECUTION_RULE --context <ctx> --script @page.groovy` (the data source),
> `crud add-method <alias> --name findAll --type SQL --query <qid> --returns-array` / `query add` (the paged SQL),
> `crud verify --db "<libpq conninfo>"` (runs every SQL method against a live DB — the only offline way to prove
> the paging/sort SQL actually executes), `find --plugin nct.html.plugin`, `show node <id>`.
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.
>
> ⛔ `validate` parses `studioModel` and checks four things: the JSON is well-formed, every `libNames`
> entry references a **declared** library, vendored asset paths are relative, and the component's `<include>`
> graph resolves (a cycle is an ERROR) — plus the colour lint over
> `css.byTheme["*"]` ([24a](24a-theming-and-dark-mode.md)). It does **not** resolve the rule name you pass to
> `ctx.callRule`, does not know your table exists, and does not count it against the one-table-per-page rule
> (that check looks at the three table *plugins* only). Every gate in this doc that says "validate: no" means
> *you* are the gate.

---

## 1 · Decide first: do NOT hand-build this table

`crud.table.plugin` already ships everything below — server-side paging through a fetch rule, a filter form,
row actions, header ("create") actions, Excel import, column localization, per-row action predicates
([04](04-crud-table-plugin.md)). Every hour you spend re-implementing it is an hour of untested code that no
`validate` check protects. Hand-building is justified by **layout the table plugin cannot express** — not by
"I want it to look nicer".

| The screen is… | Build it as | Why |
|---|---|---|
| rows + filters + row actions + create/edit forms | `crud.table.plugin` → [04](04-crud-table-plugin.md) | paging, filter form, actions, import, localization are config, not code |
| a hierarchy (parent → children) | `crud.tree.plugin` → [05](05-crud-tree-and-process-table.md) | `findByParent`, no LIMIT/OFFSET at all |
| process instances / tasks | `process.table.pluin` → [05](05-crud-tree-and-process-table.md) | filter tokens + index settings are built in |
| numbers, trends, KPI tiles | `chart.js.plugin` → [22](22-charts-params-and-filters.md) | a dashboard carries **no** table |
| **grouped rows** (a group header row that spans the table, collapsible sections) | hand-built | the plugin renders one flat `<tr>` per row |
| **a cell that is not text** (sparkline, progress bar, stacked badges, thumbnail strip) | hand-built | a cell is a formatted string or a boolean icon (the table plugin renders it through `BooleanIconColumnUtils`), never a template |
| **master–detail in one viewport** (list left, live detail right, one selection driving both) | hand-built | two plugins cannot share a selection without a page round-trip |
| **a board / timeline / calendar-like arrangement of rows** | hand-built (or `calendar.plugin`, which is registered in the platform but not yet covered by these docs) | not a table shape at all |
| **a table whose columns come from data** (pivot, matrix, one column per period) | hand-built | `columnSettings` is a fixed authored list |

**Business judgement.** A hand-built table is a *product decision to own code forever*. Take it when the layout is
the point (an operator stares at this screen all day and the arrangement is what makes them fast). Refuse it when
the motivation is cosmetic — restyle with theme tokens instead ([24a](24a-theming-and-dark-mode.md), [22 §6](22-charts-params-and-filters.md)).
If you take it, take it **whole**: paging, count, filter and sort pushed to SQL, from the first commit. Retrofitting
paging into a component that assumed "all rows are in `ROWS`" is a rewrite of every render function.

> ⛔ **A hand-built table counts against the ONE-TABLE-PER-PAGE rule — and `validate` cannot see it.**
> Mechanism: the one-table check only counts the three table *plugins* (`crud.table.plugin`, `crud.tree.plugin`,
> `process.table.pluin`), so an `nct.html.plugin` rendering a `<table>` is invisible to it. Symptom the user
> sees: two grids of the same entity on one page, disagreeing — the custom one filtered, the plugin one not —
> and no error anywhere. This is the normal way the pair arises: an author builds the custom screen *next to*
> the plugin table it was meant to replace, one such pair per entity — `<Entity>` list beside `<Entity>` grid —
> and every offline gate stays green because the checker never sees the hand-built one.
> **Rule:** the page hosting your component carries **no** table plugin, unless each sits in its own
> `nct.tab.plugin` tab. Full doctrine — [04](04-crud-table-plugin.md) opening block / [14 §2.3](14-plugin-catalog-all.md).

**Done when (decision):** you can name the layout feature the table plugin cannot express, in one sentence, and the
page carries no other table.

---

## 2 · The data contract — what the server can page, and what reaches JS

### 2.1 The two doors, and why only one of them is the right one

Author JS reaches the server through exactly two **data** bridges — the `dokieCallRule` and `dokieCallBl`
handlers registered by the html plugin. (There is a third, `dokieBreadcrumb`, but it carries chrome, not data —
§8.)

| | `ctx.callBl(alias, method, args)` | `ctx.callRule(name, input)` |
|---|---|---|
| Reaches | one dynamic-CRUD method, verbatim | an EXECUTION rule = arbitrary Groovy |
| Args | positional array; a single object is wrapped as a one-element list | one object; injected as `context.data.getAttr('input')` **plus** one attr per top-level field (a field literally named `input` cannot clobber the whole-payload attr — the reserved one is written last) |
| Joins / derived columns / N tables | ❌ one call per table | ✅ one call, server-side |
| Shapes the payload | ❌ returns whatever the SQL selects | ✅ returns exactly what the table renders |
| Enforces authorization | whatever the CRUD allows the logged-in user | ✅ you write the filter |
| Cost | N calls = N **blocking** round-trips | 1 |

⛔ **Use ONE EXECUTION rule per table render.** `ctx.callBl` is fine for a single mutation (`create`, `delete`) and
for a throwaway lookup; it is the wrong source for a screen. Neither bridge has an allowlist — the BL bridge runs
any `alias.method` the current user may run (it goes through the *user-authenticated* `ReactorCrudService` path)
and the rule bridge runs any ACTIVE rule resolved by identifier or **exact** (case-insensitive) display name.
Whatever the browser names, the server executes; so the *rule* is where the row filter, the column projection and
the page-size ceiling belong.

### 2.2 The paged CRUD contract (the part you must not re-derive)

A dynamic CRUD's scaffolded methods ([11](11-business-logic-dynamic-crud.md) owns the schema):

```sql
-- findAll  (SQL, returnsArray:true, params: <filters…>, rowsInPage, pageNumber)
SELECT * FROM <t> WHERE 1=1 <filter>
ORDER BY <pk>
LIMIT :rowsInPage
OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))

-- count    (SQL, params: <filters…>)  — the SAME filter predicate, no paging
SELECT COUNT(*) AS total FROM <t> WHERE 1=1 <filter>
```

⚠️ That is the form **you must write**, not the form the platform hands you. The in-app emitter writes the
paging as the placeholder-object syntax
`LIMIT {name: 'rowsInPage', type: 'integer'} OFFSET ({name: 'pageNumber', type: 'integer'} * {name: 'rowsInPage', type: 'integer'})`
in the saved **query**, and the `methods[].script` twin (the text the executor actually runs) is that same SQL
with each placeholder object rewritten to a bare `:name` — i.e. the **untyped** `OFFSET (:pageNumber * :rowsInPage)`.
Untyped paging is fine when the UI table calls `findAll` (the pager binds real ints) and explodes the moment a
**rule** calls it — transcribe both sides in the CAST form above, in `methods[].script` *and* in the linked
query — [11 §"the six SQL methods"](11-business-logic-dynamic-crud.md).

`find` is the seventh, **GROOVY** method with `ruleIdentifier: null` — a sentinel. The executor recognises it
(`isAutoFindWrapper`) and never runs the Groovy: it calls the sibling `findAll` and `count` **with the same
parameter map** and assembles the envelope in Java:

```json
{ "content": [ … ], "totalElements": 1240, "totalPages": 50, "pageNumber": 0 }
```

Facts you will rely on, each verified:

- `find` **requires** a sibling `findAll` — otherwise `IllegalStateException`.
- **No `count` method ⇒ `totalElements = rows.size()`** — see the trap in §7.
- `rowsInPage`/`pageNumber` for the envelope are read from the **first map argument**;
  `totalPages = ceil(total / rowsInPage)`, or `1` when `rowsInPage <= 0`.
- `count`'s `total` is read from `{total: n}` or `[{total: n}]`.

> ⛔ **The Java wrapper only runs while `find.ruleIdentifier` is blank.** Mechanism: `isAutoFindWrapper` demands
> *all three* of `methodName == "find"`, `methodType == GROOVY` and a null/blank `ruleIdentifier`. Fill that
> field in and the sentinel stops matching: the Groovy branch runs and **delegates to that rule** — the method's
> own `script` is dead text in *both* branches, so reading it tells you nothing about what will happen. Two
> consequences. (1) `findAll` and `count` are no longer guaranteed to see the same map: that rule decides, and
> the two hand-rolled wrapper shapes in circulation disagree — the in-app generator emits `count(filter)` (over
> a map merged from the declared params, so every key exists) while the `mrjun` scaffold emits `count()` with
> **no argument**, i.e. an *unfiltered* total beside a filtered page. (2) The rule can simply be absent — a
> `find.ruleIdentifier` pointing at a rule that no longer exists in the bundle is a common leftover of deleting
> or renaming a rule. Check yours before you trust `totalElements`: `mrjun.py show crud <alias>` → `methods[]` →
> `find.ruleIdentifier` must be `null`. `validate` catches: no.

### 2.3 What the rows actually look like in JS

Rows are built column-by-column from the JDBC result set (the executor's `mapRow`):

- **every column label is camelCased** — `<entity>_name` → `<entity>Name`, the join alias
  `<parent>_<entity>_name` → `<parent><Entity>Name`. Read the camelCase key; do not "try both cases".
- an alias containing `__` becomes a **nested object** — `category__id` → `row.category.id` (each segment is
  camelCased on its own).
- the CRUD's `localizationField` column is renamed to the canonical key **`localize`**.
- **every value is converted in the executor, not by Jackson later** (its `setLeafValue`): a `json`/`jsonb`
  column is *parsed* into a real object (which is why `row.localize` is a Map you can index, not a string), a
  `date` becomes `"2026-08-10"`, a `timestamp` becomes **`Instant.toString()`** — UTC, with a trailing `Z` and
  whatever fractional seconds the column carries: `"2026-08-10T09:15:00Z"` — and a `uuid` and every unrecognised
  type become `value.toString()`.

> ⚠️ **The localized column is `row.localize`, never `row.<localizationField>`.** Mechanism: `mapRow` rewrites the
> column name when it equals the CRUD's `localizationField`. Symptom: your per-locale labels silently never
> appear and every row shows the base-language value. The usual form of the bug: the component reads
> `row.<localizationField>` (the DB column name, e.g. `localized`) — even with a case-insensitive helper it is
> not the string `localize`, so the lookup misses on every row and the whole screen quietly falls back to the
> base language. `validate` catches: no.

Then the whole return value is Jackson-serialized by the bridge's own mapper — `JavaTimeModule`,
`WRITE_DATES_AS_TIMESTAMPS` **disabled** — so a temporal value the **rule itself** creates (a `LocalDate`, an
`Instant`) also arrives as an ISO-8601 string, never epoch millis. CRUD row values were already strings before
this point (above), so the two paths agree — but they do **not** agree on shape: a `date` column gives
`"2026-08-10"` while a `timestamp` column gives `"2026-08-10T09:15:00Z"`. Format in the rule (§3) or in JS;
never `esc(r.someTimestamp)` straight into a cell.

⚠️ **Return only what Jackson can serialize** — plain maps, lists, strings, numbers, booleans, dates. A result
the mapper cannot write is deliberately turned into the *error* envelope (`result is not serializable: …`)
rather than a literal `null`, so `await ctx.callRule(...)` **rejects** instead of resolving with a wrong value.
The projection step in §3 is what keeps you on the safe side of this.

The success envelope is `{"ok":true,"result":…}` and the runtime resolves the promise with `result` alone;
`{"ok":false,"error":…}` **rejects** with `new Error(error)`, where the text is the rule's error list — i.e. a
raw Postgres message can reach the browser. Show it in your error state; do not `alert()` it at the user
unchanged.

### 2.4 ⛔ The partial-filter-map crash

```groovy
// CRUD declares filter params status + assignedTo; you pass only paging:
service.crud.<alias>.findAll([rowsInPage: 25, pageNumber: 0])
```

Mechanism, in two steps. The executor unpacks a single map argument by declared parameter name, storing `null` for
every name the map does not carry, and later binds each such slot as `stmt.setNull(idx, Types.NULL)` — OID 0,
i.e. *unspecified*. Separately, the placeholder rewriter replaces **each occurrence** of `:name` with its own `?`,
so a hand-written `(:status IS NULL OR col = :status)` becomes `(? IS NULL OR col = ?)` — two independent slots,
and the first one sits in `? IS NULL`, where Postgres has nothing to infer a type from. (`col = ?` alone would
have been fine: the column supplies the type. It is the bare `? IS NULL` arm, and untyped `? * ?` arithmetic,
that fail.) The platform's own default-method emitter documents exactly this reasoning next to the COALESCE form
it generates.
Symptom the user sees: the table never renders and the promise rejects with
`could not determine data type of parameter $1` (or, for untyped paging arithmetic,
`operator is not unique: unknown * unknown`). `validate` catches: partially — it flags this pattern for *choices*
rules only ([11](11-business-logic-dynamic-crud.md) gotchas); for a studio component it catches nothing.

**You cannot fix this from the caller** — an absent key and an explicit `[status: null]` take the *same* branch
and bind the same unspecified NULL. The fix is
in the method SQL; both of these forms give Postgres the type and are verified in the field:

```sql
-- (a) the canonical emitter form (what the in-app "default methods" generator writes)
AND <col> IS NOT DISTINCT FROM COALESCE({name: '<camelCol>', type: '<t>'}, <col>)

-- (b) the CAST-guarded form, equally common in hand-written findAll SQL
AND (CAST(:assignedTo AS varchar) IS NULL OR t.assigned_to = CAST(:assignedTo AS varchar))
```

and paging is **always** transcribed in the CAST form (`LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))`)
— [11](11-business-logic-dynamic-crud.md) §"the six SQL methods".

⚠️ Two more Postgres-semantics traps at the edges of the same SQL: **omitting** `rowsInPage` binds `LIMIT NULL`,
which Postgres reads as *no limit* — you silently fetch the whole table; passing `0` binds `LIMIT 0` — you get an
empty page with `totalPages: 1`. Always send a positive, server-clamped integer (§3).

### 2.5 One call, one blocking round-trip

**This is the canonical statement of bridge concurrency for the whole library** — [24](24-html-component-studio.md)
§4.4 points here.

`ctx.callRule`/`callBl` post through the component's ajax twin **without** asking for `async`, and richwicket's
`ajax` defaults `async` to `false`. That selects the *sync* supporter, whose callback script sets
`setAsynchronous(false)` on the Wicket request attributes — a genuinely **synchronous XHR**. (The async supporter
exists precisely so that other traffic — e.g. each lazily-loaded chart — does *not* block; the studio bridge is
not on that path.) The bridge is therefore **not "queued but non-blocking"**: it stops the main thread until the
server replies. Consequences you must design around:

- `Promise.all([ctx.callRule(a), ctx.callRule(b)])` does **not** parallelise — it serialises **and** freezes the
  page twice. One call per interaction.
- **Never fire bridge calls in a loop** (one per row, one per lookup table): N calls = N freezes, and the tab is
  unresponsive for their sum. Fold the work into one rule instead (§3).
- The 30 s guard inside the runtime's `bridge()` cannot fire while the thread is blocked; it exists for the case
  where the server never invokes the callback at all — e.g. an unknown handler name, which only logs
  `No handler for event …` server-side.
- A DOM write made in the same task as the call is **not painted** before the block. Yield one macrotask between
  "show the loading state" and the call (`await new Promise(r => setTimeout(r, 0))`, the `paint()` helper in §4).

---

## 3 · The page rule (EXECUTION) — full reference

One rule, one screen, one call per render. It owns paging limits, the sort whitelist, the filter map, the row
filter, and the projection into the exact view model the table renders. Add it with
`mrjun.py rule add --name "<Screen> Page" --type EXECUTION_RULE --context <ctx> --script @page.groovy`.

```groovy
// <Screen> Page — EXECUTION_RULE, context <ctx>
// Called from the component as: ctx.callRule('<Screen> Page', {page, size, sortKey, sortDir, filters})
// Returns ONE page of ONE table: the rows the screen renders, plus the numbers the pager needs.

def input = context.data.getAttr('input') ?: [:]          // the whole JS payload, under the reserved attr

// 1 · paging — clamp on the SERVER; the browser is an untrusted caller
int size = (input.size ?: 25) as int
if (size < 1)   { size = 25 }
if (size > 200) { size = 200 }                            // hard ceiling: a screen, never a dump
int page = (input.page ?: 0) as int
if (page < 0)   { page = 0 }

// 2 · sort — a CLOSED whitelist; anything else falls back to the deterministic default
def SORTABLE = ['id', 'name', 'status', 'dueDate']
String sortKey = (input.sortKey ?: 'id') as String
if (!SORTABLE.contains(sortKey)) { sortKey = 'id' }
String sortDir = ((input.sortDir ?: 'asc') as String).equalsIgnoreCase('desc') ? 'desc' : 'asc'

// 3 · filters — one key per declared param, blank -> null. Presence does NOT protect you from §2.4
//     (absent and explicit-null bind the same untyped NULL); the SQL form does. Keep the keys anyway:
//     "" would otherwise filter for name = '' instead of "no filter".
def f = (input.filters instanceof Map) ? input.filters : [:]
def nz = { v -> (v == null || (v instanceof String && v.trim().isEmpty())) ? null : v }
def filter = [
    rowsInPage : size,
    pageNumber : page,
    sortKey    : sortKey,
    sortDir    : sortDir,
    status     : nz(f.status),
    q          : nz(f.q)
]
// Row-level authorization belongs HERE, not in JS. Compare against whatever the ownership column holds —
// usually the email (user().id is the platform's INTERNAL user-row id, rarely what a business row stores):
// if (!service.security.hasAnyRoleGroup('<Manager>')) { filter.assignedTo = service.security.user().email }

// 4 · ONE paged fetch: content + totalElements in a single round-trip
//     find() = the auto-paged wrapper: findAll + count, same filter — but ONLY while the CRUD's find
//     method has ruleIdentifier: null (§2.2 trap). Verify it once.
def result = service.crud.<alias>.find(filter) ?: [:]
def rows   = (result.content ?: []) as List
long total = (result.totalElements ?: 0) as long

// 5 · locale — JS has none; the bridge passes the page locale into the rule, and the executor puts it in
//     the thread-local LocaleContext that service.global.locale.getKey() reads.
//     ⛔ NOT context.data.localeKey — that is an ATTRS lookup and nothing ever writes it (always null).
def loc = service.global.locale.getKey() ?: 'en_US'
def label = { row, field, fallback ->
    def m = row?.localize                                  // the canonical key, whatever the column is called
    if (m instanceof String) { try { m = new groovy.json.JsonSlurper().parseText(m) } catch (Throwable t) { m = null } }
    def per = (m instanceof Map) ? m[field] : null
    (per instanceof Map && per[loc]) ? per[loc] : fallback
}

// 6 · project: only the columns the table draws, under stable names
def today = java.time.LocalDate.now().toString()
def content = rows.collect { r ->
    [ id      : r.id,
      name    : label(r, 'name', r.name),
      status  : r.status,
      zone    : r.zoneName,                                // from a LEFT JOIN in findAll — never an N+1 in JS
      amount  : r.amount,
      dueDate : r.dueDate,
      overdue : (r.dueDate != null && (r.dueDate as String) < today && r.status != 'done') ]
}

return [ ok         : true,
         content    : content,
         total      : total,
         totalPages : size > 0 ? (long) Math.ceil(total / (double) size) : 1L,
         page       : page,
         size       : size,
         sortKey    : sortKey,
         sortDir    : sortDir,
         locale     : loc ]
```

Why each block earns its place:

1. **Clamping on the server** is the only clamp there is. `size` arrives from a browser you do not control; a
   devtools console can send `{size: 500000}` and the bridge will happily run it.
2. **The whitelist lives in Groovy, not JS** — §6.
3. **`nz` normalises, it does not protect.** `""` (an empty search box) becomes `null` = "no filter", which is what
   the COALESCE/CAST predicate expects — without it you filter for `name = ''` and get an empty grid. What it
   cannot do is prevent §2.4: an untyped NULL is bound whether the key is present or absent, so the SQL still has
   to carry the COALESCE/CAST form.
4. **`find`, not `findAll`+`count` by hand.** With a true sentinel `find` (§2.2) both run off the *same* map in one
   integration call, so the count cannot disagree with the page (§7). If your CRUD needs a shape `find` cannot give
   (multi-table aggregation), run a saved query instead:
   `service.rimm.run([name:'<query>', itemsPerPage: size, offset: page*size, parameters:[…]])` — `name`,
   `itemsPerPage`, `offset` and `parameters` are the `QueryByNameRequest` fields;
   it returns a plain `List`, so **there is no total** and you owe the user one of §7's honest fallbacks —
   [16 §2.4](16-groovy-service-api.md), [12](12-queries-sources-schedulers-and-rest.md).
5. **Locale server-side, through `service.global.locale.getKey()`.** `ctx` carries no locale at all; the rule is
   the only place that knows it, and that accessor is the only supported way to read it — see the ⛔ below.
6. **Projection is the payload budget.** 25 rows × 6 fields is a few kB; 25 raw entities with 30 columns and a
   `localize` blob each is 50×. It is also the only way a column the user must not see stays off the wire —
   dropping the field here is the *only* real gate for "supervisors also see the cost column"; hiding the `<td>`
   in JS leaves the value in the response ([24](24-html-component-studio.md) §9a.5) — and it is what guarantees
   the return value is Jackson-serializable (§2.3).

> ⛔ **Read the locale as `service.global.locale.getKey()`. `context.data.localeKey` is ALWAYS `null`.**
> Mechanism: `context.data.<name>` is sugar for `getAttr("<name>")`, which reads only the rule's **attrs** map;
> `localeKey` is a *field* on the context-data DTO, not an attr, and nothing ever writes an attr by that name.
> The executor copies that DTO field into a thread-local locale context before it runs your script, and
> `service.global.locale.getKey()` is the accessor that reads it (the localizing helpers such as
> `service.global.conversion.toSelectOptionsLocalized` default to the same source). Symptom: `loc` is null, the
> `?: 'en_US'` fallback fires on every call, and a fully translated project renders one language — with no error
> anywhere. Cross-references: [20 §"Groovy"](20-localization.md) and
> [24 §4](24-html-component-studio.md) carry the same ⛔. It is the single most-copied mistake in studio data
> rules — one author writes it, every later rule is pasted from that one, and the project ships a one-language
> UI. Grep your own rules for `localeKey` before you translate anything. `validate` catches: no.
> (If you prefer reading the DTO directly, `context.contextData.localeKey` is the same value — but the global
> accessor is the one the rest of this library uses.)

**Done when:** calling the rule with `{page:0,size:25}` and with `{page:1,size:25}` from the rule editor returns
**different** ids, and `total` matches `SELECT count(*)` for the same filter.

---

## 4 · The component script — fetch, render, page, sort, filter

Goes into `studioModel.scripts[0].code` (`mrjun.py node set-studio`). It assumes the markup of §5.
Every DOM listener is registered through the `on()` helper so it dies with the instance: the runtime auto-removes
`ctx.on` **bus** listeners only, never a raw `addEventListener` — undoing those is what `ctx.onCleanup` is for.

⚠️ Register every listener and cleanup **before the first `await`**. After teardown the runtime refuses new
`ctx.on(...)` registrations outright and runs a `ctx.onCleanup(fn)` **immediately** instead of queueing it — both
are deliberate (a drained teardown list would otherwise leak), and both make late registration silently useless.
The script below does all of its registering synchronously, then calls `reload()` last, which is the shape to
copy ([24 §6](24-html-component-studio.md)).

```js
// ---------------------------------------------------------------- <entity> table
const RULE = '<Screen> Page';                       // MUST match the rule's exact display name or identifier

const q    = (s) => ctx.root.querySelector(s);
const esc  = (v) => String(v == null ? '' : v)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const errText = (e) => e == null ? 'unknown error'
  : (typeof e === 'string' ? e : (e.message || e.error || 'request failed'));
// The bridge is a BLOCKING round-trip, so a DOM write in the same task never paints. Yield one macrotask.
const paint = () => new Promise((r) => setTimeout(r, 0));

const S = { page: 0, size: 25, sortKey: 'id', sortDir: 'asc', filters: { q: '', status: '' } };

let seq   = 0;        // request token — only the newest reply may render
let alive = true;     // false after teardown
let timer = null;     // debounce handle

const wrap  = q('[data-role="wrap"]');
const body  = q('[data-role="rows"]');
const pager = q('[data-role="pager"]');
const note  = q('[data-role="note"]');

function on(el, type, fn) {                          // add + auto-remove at teardown
  if (!el) { return; }
  el.addEventListener(type, fn);
  ctx.onCleanup(() => el.removeEventListener(type, fn));
}
ctx.onCleanup(() => { alive = false; clearTimeout(timer); });

// ---------------------------------------------------------------- fetch
function schedule(ms) {                              // debounce: typing must not fire a call per keystroke
  clearTimeout(timer);
  timer = setTimeout(reload, ms == null ? 300 : ms);
}

async function reload() {
  const my = ++seq;                                  // in-flight guard
  wrap.setAttribute('aria-busy', 'true');
  body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Loading…</td></tr>';
  await paint();                                     // let the row above actually appear
  try {
    const res = await ctx.callRule(RULE, {
      page: S.page, size: S.size,
      sortKey: S.sortKey, sortDir: S.sortDir,
      filters: S.filters
    });
    if (!alive || my !== seq) { return; }             // torn down, or a newer request owns the view
    if (!res || res.ok === false) { fail(res && res.error); return; }
    render(res);
  } catch (e) {
    if (!alive || my !== seq) { return; }
    fail(errText(e));
  } finally {
    if (alive && my === seq) { wrap.removeAttribute('aria-busy'); }
  }
}

function fail(msg) {
  body.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-4">'
                 + esc(msg || 'Could not load data') + '</td></tr>';
  pager.innerHTML = '';
  note.textContent = '';
}

// ---------------------------------------------------------------- render
function render(res) {
  const rows = Array.isArray(res.content) ? res.content : [];
  S.page = Number(res.page) || 0;                    // trust the SERVER's clamped values, not the local ones
  S.size = Number(res.size) || S.size;

  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">'
                   + (S.filters.q || S.filters.status ? 'Nothing matches this filter.' : 'No records yet.')
                   + '</td></tr>';
  } else {
    body.innerHTML = rows.map((r) =>
      '<tr data-id="' + esc(r.id) + '">'
      + '<td>' + esc(r.name) + '</td>'
      + '<td>' + esc(r.zone) + '</td>'
      + '<td><span class="badge bg-' + (r.status === 'done' ? 'success' : 'secondary') + '">'
          + esc(r.status) + '</span></td>'
      + '<td class="text-end">' + esc(r.amount) + '</td>'
      + '<td' + (r.overdue ? ' class="text-danger"' : '') + '>' + esc(r.dueDate) + '</td>'
      + '<td class="text-end">'
        + '<button type="button" class="btn btn-sm btn-outline-secondary" data-act="open" '
        +   'aria-label="Open ' + esc(r.name) + '"><i class="pe-7s-look"></i></button>'
      + '</td>'
      + '</tr>').join('');
  }

  // header sort indicators
  ctx.root.querySelectorAll('th[data-sort]').forEach((th) => {
    const active = th.getAttribute('data-sort') === res.sortKey;
    th.setAttribute('aria-sort', active ? (res.sortDir === 'desc' ? 'descending' : 'ascending') : 'none');
    th.classList.toggle('is-sorted', active);
    th.classList.toggle('is-desc', active && res.sortDir === 'desc');
  });

  renderPager(res);
}

function renderPager(res) {
  const total = Number(res.total) || 0;
  const pages = Math.max(1, Number(res.totalPages) || 1);
  const from  = total === 0 ? 0 : S.page * S.size + 1;
  const to    = Math.min(total, (S.page + 1) * S.size);
  note.textContent = total === 0 ? '0 records'
    : (from + '–' + to + ' of ' + total.toLocaleString());

  const btn = (p, label, disabled, current) =>
    '<li class="page-item' + (disabled ? ' disabled' : '') + (current ? ' active' : '') + '">'
    + '<button type="button" class="page-link" data-page="' + p + '"'
    + (disabled ? ' disabled' : '') + '>' + label + '</button></li>';

  const around = [];
  for (let p = Math.max(0, S.page - 2); p <= Math.min(pages - 1, S.page + 2); p++) {
    around.push(btn(p, String(p + 1), false, p === S.page));
  }
  pager.innerHTML = '<ul class="pagination pagination-sm mb-0">'
    + btn(S.page - 1, '‹', S.page <= 0, false)
    + around.join('')
    + btn(S.page + 1, '›', S.page >= pages - 1, false)
    + '</ul>';
}

// ---------------------------------------------------------------- interaction (delegated: innerHTML is replaced)
on(pager, 'click', (e) => {
  const b = e.target.closest('[data-page]');
  if (!b || b.disabled) { return; }
  S.page = Number(b.getAttribute('data-page'));
  schedule(0);
});

on(ctx.root.querySelector('thead'), 'click', (e) => {
  const th = e.target.closest('th[data-sort]');
  if (!th) { return; }
  const key = th.getAttribute('data-sort');
  S.sortDir = (S.sortKey === key && S.sortDir === 'asc') ? 'desc' : 'asc';
  S.sortKey = key;
  S.page = 0;                                        // a new order invalidates the offset
  schedule(0);
});

on(q('[data-role="search"]'), 'input', (e) => {
  S.filters.q = e.target.value;
  S.page = 0;
  schedule(300);                                     // one call per pause, not per keystroke
});

on(q('[data-role="status"]'), 'change', (e) => {
  S.filters.status = e.target.value;
  S.page = 0;
  schedule(0);
});

on(body, 'click', (e) => {                           // row actions — §8
  const b = e.target.closest('[data-act]');
  if (!b) { return; }
  const id = b.closest('tr').getAttribute('data-id');
  if (b.getAttribute('data-act') === 'open') { openDetail(id, b); }
});

// The screen owns its own actions; the §8 idioms go here. Stubbed so this block runs as written.
async function openDetail(id, btnEl) { /* §8 (a): ctx.busy + await ctx.callRule('<Detail> …', {id}) */ }

reload();
```

Notes that are not obvious:

- **The in-flight guard (`seq`) is 3 lines and you keep it.** Today the transport is synchronous (§2.5) so replies
  cannot overtake each other — but the guard also drops the reply of a request whose component was torn down and
  remounted by a Wicket AJAX re-render (each mount bumps a generation and tears the previous instance down),
  which otherwise writes into a detached DOM and burns a render.
- **Never `ctx.setHtml`/`ctx.showHtml` to refresh rows.** Both assign to `ctx.root.innerHTML` — that destroys the
  whole component, including every server-rendered `<plugin>` child (from the main document **or** from any
  document pulled in by `<include>`/`ctx.include`), and every listener you
  bound. Write into the `<tbody>` you own.
- **`S.page` is re-read from the reply**, so the server's clamp wins and a stale local page cannot desync the pager.
- Debounce values: `0` for a deliberate click (page/sort/select) so it feels instant, `300 ms` for typing.

---

## 5 · The markup — theme-correct, scrollable, accessible

Goes into `properties.html.stringValue` — the "main" document, the one slot that is *not* listed in
`studioModel.docs` ([24 §2](24-html-component-studio.md)); its `<plugin>` tags are server-rendered before your
scripts run ([24 §3](24-html-component-studio.md), §6.4) — **and so are those of every document reached through
`<include src="….html">` or `await ctx.include('….html', …)`**, because an included document is substituted into
the markup server side *before* it is parsed, which makes a `<plugin>` written in it an ordinary live child node
([24d](24d-html-component-structure.md)). Only `ctx.showHtml` stays client-only: it swaps `innerHTML`, so it can
render neither a `<plugin>` nor an `<include>`. The markup below may therefore equally live in a `docs[]` entry
that `main.html` pulls in with `<include>`.
Use classes **all five skins already restyle** (`.card`, `.table`, `.table-hover`, `.badge bg-*`,
`.pagination`/`.page-link`, `.form-control`, `.form-select`, `.btn`/`.btn-outline-*`, `.text-muted`) so the
component follows the theme for free — the token contract itself is [24a](24a-theming-and-dark-mode.md),
[22 §6](22-charts-params-and-filters.md) and [14 §2.2](14-plugin-catalog-all.md); do not restate a palette here and
do not hardcode a hex.

```html
<div class="main-card mb-3 card">
  <div class="card-body">
    <h5 class="card-title d-flex align-items-center justify-content-between">
      <span>[entity] list</span>          <!-- [entity] = placeholder; a bare <entity> is parsed as an element -->
      <span data-role="note" class="small text-muted">&nbsp;</span>
    </h5>

    <div class="row g-2 mb-3">
      <div class="col-sm-6 col-md-4">
        <label class="form-label visually-hidden" for="tbl-q">Search</label>
        <input id="tbl-q" data-role="search" type="search" class="form-control form-control-sm"
               placeholder="Search…" autocomplete="off">
      </div>
      <div class="col-sm-4 col-md-3">
        <label class="form-label visually-hidden" for="tbl-status">Status</label>
        <select id="tbl-status" data-role="status" class="form-select form-select-sm">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="done">Done</option>
        </select>
      </div>
    </div>

    <div data-role="wrap" class="tbl-wrap">
      <table class="table table-hover align-middle mb-0">
        <caption class="visually-hidden">List of [entity] records</caption>
        <thead>
          <tr>
            <th scope="col" data-sort="name"    aria-sort="none" tabindex="0">Name</th>
            <th scope="col">Zone</th>
            <th scope="col" data-sort="status"  aria-sort="none" tabindex="0">Status</th>
            <th scope="col" class="text-end">Amount</th>
            <th scope="col" data-sort="dueDate" aria-sort="none" tabindex="0">Due</th>
            <th scope="col" class="text-end">&nbsp;</th>
          </tr>
        </thead>
        <tbody data-role="rows">
          <tr><td colspan="6" class="text-center text-muted py-4">Loading…</td></tr>
        </tbody>
      </table>
    </div>

    <nav data-role="pager" class="mt-3 d-flex justify-content-end" aria-label="Pagination"></nav>
  </div>
</div>
```

and the component CSS (`studioModel.css.byTheme["*"]` — one block, tokens only; the studio scopes every selector
to this component's wrapper id, [24](24-html-component-studio.md), [24a](24a-theming-and-dark-mode.md)). Prefix
the classes you invent with a per-component prefix (`<pfx>-`, e.g. `tbl-`) so nothing leaks even where the scoper
is bypassed:

```css
/* the table scrolls, the PAGE never does */
.tbl-wrap { overflow-x: auto; max-height: 60vh; overflow-y: auto; }

/* sticky header: must be OPAQUE or rows scroll through it */
.tbl-wrap thead th {
  position: sticky; top: 0; z-index: 2;
  background: var(--current-line, var(--bs-light));
  color: var(--bs-body-color);
  box-shadow: inset 0 -1px 0 var(--bs-border-color);
  white-space: nowrap;
}
.tbl-wrap th[data-sort] { cursor: pointer; user-select: none; }
.tbl-wrap th[data-sort]::after { content: '↕'; opacity: .35; margin-left: .35rem; font-size: .8em; }
.tbl-wrap th.is-sorted::after  { content: '↑'; opacity: 1; }
.tbl-wrap th.is-sorted.is-desc::after { content: '↓'; }
/* the busy attribute sits ON .tbl-wrap (§4 sets it there) — no descendant combinator */
.tbl-wrap[aria-busy="true"] .table { opacity: .6; transition: opacity .15s; }
```

Requirements this markup encodes:

- **Horizontal scroll is on the wrapper, never the page.** A table wider than the parsis column must scroll
  inside `.tbl-wrap`; a page that scrolls sideways is a bug on every laptop.
- **A vertical cap (`max-height`) plus a sticky header** keeps the pager on screen. Do **not** use `h-100` — in
  ArchitectUI it resolves to `height:100vh`, not `100%` ([24a](24a-theming-and-dark-mode.md)); the full-height
  helper is `he-100`.
- **`colspan` on the empty/loading/error row** must equal the column count, or the state row breaks the grid.
- **a11y minimum:** `<caption class="visually-hidden">`, `<th scope="col">`, `aria-sort` on sortable headers
  (updated in `render()`), `aria-busy` on the wrapper while loading, `type="button"` on every in-row button
  (a bare `<button>` inside a form submits it), and an `aria-label` on icon-only buttons.
- **`badge` always with a `bg-*`** — a bare `.badge` has no background in Bootstrap 5, and `.badge-light` renders a
  white pill on all four dark skins ([24a](24a-theming-and-dark-mode.md)).

---

## 6 · Sorting and filtering: push it down, or don't offer it

**Default: push both to SQL.** A sort or a filter applied in JS re-orders/hides *the 25 rows you already hold* —
so "sort by amount" shows the largest of page 1, not the largest overall, and "status = open" empties a page that
has 900 open rows on page 7. That is the single most common wrong-answer bug in a hand-built table, and it looks
like a working feature.

| Do it in JS only when… | Do it in SQL otherwise |
|---|---|
| the whole result set is already on the client **by construction** (a bounded child list: the ≤50 lines of one document, one plan's tasks) | any list whose size is data-dependent |
| the ordering is presentational (group headers, a "pinned first" row you computed) | any ordering the user chose from a header |
| the filter is a view toggle over the loaded page ("hide empty rows") | any filter over the entity |

### The filter path

Filter values ride in `input.filters` → the rule maps them into the `find` map (§3 step 3) → the CRUD's `findAll`
**and** `count` must apply the same predicate, which is what keeps the pager honest. The in-app emitter builds one
`filterWhere` fragment and weaves the *same* one into both methods, so choosing a column as a filter column there
gets you the COALESCE form on both sides ([11](11-business-logic-dynamic-crud.md)).
A free-text search box needs its own parameter, e.g.

```sql
AND (CAST(:q AS varchar) IS NULL OR <t>.name ILIKE '%' || CAST(:q AS varchar) || '%')
```

> ⛔ **A `mrjun`-scaffolded `count` has NO filter — it counts the whole table.** Mechanism:
> `crud add --scaffold-methods` emits `count` with an **empty parameter list** and
> `SELECT COUNT(*) AS total FROM <table>`, while `findAll` gets `rowsInPage`/`pageNumber` (in the CAST form).
> Whatever filter you then add to `findAll`, `count` never sees it. Symptom the user
> sees: filter to 3 matches, and the line still reads "1–3 of 1 240" with 50 pages in the pager, most of them
> empty. Fix: add the same predicate **and the same parameters** to `count` when you fill in its SQL —
> `crud verify --db` executes both and will show you the two row counts. `validate` catches: no.

Reset `S.page = 0` on every filter change (the script does) — otherwise the user sits on page 7 of a result set
that now has 2 pages and sees an empty table.

### The sort path — and where the whitelist lives

There is **no string-splice seam into SQL anywhere in this stack**: dynamic-CRUD methods bind `:name` parameters
through JDBC (the executor rewrites each `:name` to a `?` and binds it), saved queries are run by name
(`service.rimm.run`, [16 §2.4](16-groovy-service-api.md)), and no `service.sql` namespace exists
([16 §"What is NOT there"](16-groovy-service-api.md)). So a column name coming from the browser cannot be
concatenated into SQL even if you try — classic ORDER-BY injection is structurally impossible here.

That is **not** a reason to skip the whitelist. An unvalidated `sortKey` falls through every `CASE` arm, the
`ORDER BY` degenerates, and Postgres is then free to return rows in **any** order — so page 2 can repeat rows from
page 1 and skip others. The whitelist belongs in the **rule** (§3 step 2), because the JS copy is editable by
anyone with devtools and the rule is the only thing the bridge actually executes.

Express the sort as two bound parameters over a fixed set of expressions, and always end with the PK so the order
is total:

```sql
-- findAll, with sortKey/sortDir added to parameters[] (see [11] for the method schema)
SELECT … FROM <t> WHERE 1=1 <filter>
ORDER BY
  CASE WHEN CAST(:sortKey AS varchar) = 'name'    AND CAST(:sortDir AS varchar) = 'asc'  THEN <t>.name    END ASC,
  CASE WHEN CAST(:sortKey AS varchar) = 'name'    AND CAST(:sortDir AS varchar) = 'desc' THEN <t>.name    END DESC,
  CASE WHEN CAST(:sortKey AS varchar) = 'dueDate' AND CAST(:sortDir AS varchar) = 'asc'  THEN <t>.due_date END ASC,
  CASE WHEN CAST(:sortKey AS varchar) = 'dueDate' AND CAST(:sortDir AS varchar) = 'desc' THEN <t>.due_date END DESC,
  <t>.id
LIMIT :rowsInPage
OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))
```

Rules for this block: one `CASE` **per column** (never mix a date and a text column in one `CASE` — the arms must
share a type), every parameter `CAST` (§2.4), the parameter names **declared in `parameters[]`** (the rewriter only
substitutes `:name` for a *declared* name, so an undeclared `:sortKey` is left in the SQL verbatim and Postgres
rejects it), and the PK last. Keep the sortable set small — 2–4 columns is a
table, 12 is a spreadsheet nobody asked for. Index the columns you expose: an unindexed `ORDER BY` over a large
table turns every page into a full sort.

⚠️ Unlike the filter forms in §2.4, **this shape is rare in the wild** — most projects never expose a sortable
column at all. It is mechanically sound — each occurrence of the parameter becomes its own typed `?` slot —
but treat it as a recommendation rather than a field-proven snippet: run
`mrjun.py crud verify --db "<conninfo>"` against a real DB before you build a screen on it.

> ⚠️ **`ORDER BY` must be stable across pages.** Mechanism: `LIMIT/OFFSET` re-executes the query per page; if the
> ordering has ties and no tiebreaker, Postgres may place tied rows differently each time. Symptom: a row appears
> on page 1 *and* page 2 while another never appears. Fix: always append the PK. `validate` catches: no —
> `crud verify --db` proves the SQL *runs*, not that it is deterministic.

---

## 7 · Total counts and the "1–25 of 1 240" line

The count comes from the CRUD's `count` method, executed by the `find` wrapper with the **same** parameter map as
`findAll`, and surfaces as `totalElements`. Render it as a range, not just a page
number — "1–25 of 1 240" tells the user how much is behind the screen; "page 1 of 50" does not.

```js
const from = total === 0 ? 0 : S.page * S.size + 1;
const to   = Math.min(total, (S.page + 1) * S.size);
note.textContent = total === 0 ? '0 records' : (from + '–' + to + ' of ' + total.toLocaleString());
```

> ⛔ **No `count` method ⇒ `totalElements` is the size of the page you just fetched.**
> Mechanism: the auto-find wrapper initialises `total = rows.size()` and only overwrites it when a `count`
> method exists. Symptom the user sees: "1–25 of 25" on a table of 130 000
> rows, one page in the pager, and no way to reach the rest — with no error anywhere. `validate` catches: no.
> Check with `mrjun.py show crud <alias>` that `count` is in `methods[]`, or scaffold it
> (`crud add --scaffold-methods`, [11](11-business-logic-dynamic-crud.md)) — and then read §6: a scaffolded
> `count` exists but is **unfiltered**, which turns this trap into the subtler "the total ignores the filter" one.

When the entity genuinely has no cheap count (a huge table, or a query you cannot COUNT without a full scan),
do **not** fake the number. Two honest fallbacks:

- **Fetch `size + 1` rows**, render `size`, and show "1–25 of 25+" with a working "next" whenever the extra row
  came back. Cost: nothing.
- **Show no total at all**: "‹ Prev · Page 3 · Next ›", disabling "next" on a short page. Correct, boring, fast.

`totalPages` is `ceil(total/size)` — recompute it in the rule (§3) rather than trusting a client
calculation, and clamp the requested page to it, or a user who bookmarks `page=999` gets an empty grid.

---

## 8 · Row actions and page-level actions

**Two idioms, and they are not interchangeable.**

**(a) In-row button → `ctx.callRule`.** The button lives in the row you rendered; the handler is delegated from the
`<tbody>` (§4) so it survives every re-render.

```js
async function remove(id, btnEl) {
  if (!confirm('Delete this record?')) { return; }
  // ⚠️ Only the FIRST argument is resolved inside ctx.root. `block` is selected across the WHOLE document,
  // so a bare '[data-role="wrap"]' would grey out every other component that happens to use the same
  // selector. Scope it to this instance's own wrapper id.
  const done = ctx.busy(btnEl, { block: '#' + ctx.root.id + ' [data-role="wrap"]' });
  try {
    await ctx.callRule('Delete <Entity>', { id: id });
    await reload();                                                // refetch: the page contents changed
  } catch (e) {
    fail(errText(e));
  } finally {
    done();
  }
}
```

`ctx.busy(el, {block})` drives the platform's own indicators by hand and hands back the `done()` you must call:
spinner over the element's first `<i>`, blockUI over the `block` selector, top progress bar. It exists because the
declarative markup attributes (`icon-wait="true"` / `block-wait-selector`) clear themselves shortly after the next
global `ajaxComplete`, which is the wrong lifetime for author code.

> ⛔ **`opts.block` is NOT scoped to your component.** Mechanism: `ctx.busy` resolves its *first* argument inside
> `ctx.root`, but hands `block` to a page-wide jQuery selector. A generic selector (`.card`, `[data-role="wrap"]`,
> `.tbl-wrap`) therefore overlays every matching element on the page, including other components'. Symptom: two
> panels grey out when one deletes a row. Fix: prefix with the instance id (`'#' + ctx.root.id + ' …'`) or use a
> `<pfx>-`prefixed class unique to this component. `validate` catches: no.

> ⛔ **Never point `block` (or `block-wait-selector`) at a `<table>`.** Mechanism: blockUI appends its overlay
> layers **into** the blocked element, so a `<table>` gets `<div>` children — invalid content the browser
> re-parents. Symptom: the overlay renders above or outside the table, and the layout jumps. Point it at the
> wrapper `<div>` instead. `validate` catches: no.
>
> ⚠️ **A wait indicator needs an `<i>`.** The platform's `addAjaxWait` inserts the spinner before the element's
> first `<i>` and hides that icon; with no `<i>` the button is only `[disabled]`. An icon-less "Delete" button
> therefore looks frozen rather than busy. Also remember §2.5: paint before you block.

**(b) Page-level action → the breadcrumb bar.** "New <entity>", "Export", "Refresh" do not belong inside the
table card — declare them as breadcrumb buttons from the same script and they render in the page-title bar next to
the plugin-contributed ones:

```js
ctx.breadcrumb.set([
  { key: 'new',     label: 'New <entity>', icon: 'pe-7s-plus',    variant: 'primary',
    onClick: () => openCreate() },
  { key: 'refresh', label: 'Refresh',      icon: 'pe-7s-refresh', variant: 'secondary',
    onClick: async () => { await reload(); } }            // async ⇒ the button spins until it settles
]);
```

Mutations in one burst collapse into a single debounced round-trip, and re-declaring an identical set costs zero
(the runtime remembers the last set the server **acknowledged**, page-globally, so a Wicket re-render that re-runs
your script does not re-publish). The full API, the `def` fields and the constraints (studio mode required, a
`site.breadcrumb.plugin` must be on the page, always pass an ASCII `key` when the label is localized) are in
[24](24-html-component-studio.md). Keep an explicit `key` per button — it is the identity used for replace.

**Optimistic vs refetch.** Refetch (`await reload()`) is the default: the server just changed the data, the count
may have changed, and your page may now be short. Optimistic local mutation (patching the row in `S`/the DOM
without a round-trip) is justified only for a **cosmetic, reversible** change that cannot alter membership or
ordering — e.g. a "seen" flag on a row you are still showing. Anything that can move a row across a page boundary
(status, sort key, delete, create) must refetch. After deleting the last row of the last page the refetch comes
back empty, so clamp — inside `render()` (§4), immediately after `rows` is computed and `S.page` re-read from the
reply, before anything is written to the `<tbody>`:

```js
if (!rows.length && S.page > 0) { S.page--; return reload(); }   // in render(), after S.page = Number(res.page)
```

---

## 9 · Performance budget

Numbers to design against, and where they come from:

| Budget | Value | Why |
|---|---|---|
| Rows rendered per page | **25** (the stock table plugin's own default is 15) | one screen of `innerHTML` builds in single-digit ms |
| Hard ceiling clamped in the rule | **200** | above this, a "print the whole list" request is a report, not a screen — [15](15-pdf-and-mail.md) |
| Fields per row on the wire | only what the table draws | the rule projects (§3 step 6) |
| Bridge calls per user interaction | **1** | each one blocks the main thread (§2.5) |
| Bridge calls on a timer | **0** (never poll a table) | a poll freezes the page on every tick |

**Why 1 000–5 000-row fetches are the wrong default**, concretely: each row is a JSON object serialized by Jackson,
shipped through a **synchronous** XHR, parsed, then turned into HTML string concatenation. At 2 000 rows ×
20 columns the payload is megabytes, the main thread is blocked for the whole server round-trip *and* the parse,
the `<tbody>` gets tens of thousands of DOM nodes, and every subsequent sort or filter re-renders all of it.
Projects get away with it right up to go-live, because a demo database holds a few hundred rows per table and a
flagship screen holds a dozen. The failure is not gradual: it is invisible in the demo and total in production,
and by then the render code assumes the full array.

**Virtualisation is the last resort, not the fix.** Windowing the DOM (render 30 of 5 000) does not reduce the
payload, the parse, or the memory — it only hides the DOM cost. Reach for it *after* server paging, and only for a
genuinely continuous surface (an infinite log/timeline where paging is the wrong metaphor). If you do:
`overflow-y` + fixed row height + an absolutely positioned spacer, and keep server paging underneath as
"load more".

**Two cheap wins before anything clever:** (1) build rows with one `innerHTML` assignment (an array `.map().join('')`)
rather than per-row `appendChild` — the script in §4 does; (2) let SQL do the joins (`LEFT JOIN … AS zone_name`,
which surfaces camelCased as `row.zoneName` — §2.3) instead of fetching lookup tables into JS and
matching with `Array.find` per row — that is an N×M loop plus one extra blocking call per lookup table.

---

## 10 · Traps

> ⛔ **The rule name in `ctx.callRule` is resolved by identifier or EXACT display name — nothing else.**
> Mechanism: the bridge tries `findByIdentifier` first, then accepts only a case-insensitive **exact** NAME match
> and deliberately never falls back to the first fuzzy hit. Symptom: the promise rejects with
> `Rule not found: <name>` and the table shows your error state — a renamed rule breaks the screen with no import
> error. `validate` catches: **no** (it checks the studio JSON shape, not rule references). Prefer passing the
> rule **identifier**, or grep the bundle for the literal name after any rename.

> ⛔ **`ctx.setHtml` / `ctx.showHtml` destroy the component.** Both assign `ctx.root.innerHTML`; every listener you
> registered dies and every server-rendered `<plugin>` child — from the main document **or** from an included one —
> is gone until the next server
> render. Symptom: the table works once, then the pager stops responding (or an embedded chart vanishes). Write
> into the `<tbody>`. `validate` catches: no.

> ⛔ **Partial filter map / untyped paging → the table never renders.** §2.4. Symptom: rejected promise carrying
> `could not determine data type of parameter $1` or `operator is not unique: unknown * unknown`.
> Fix in the method SQL (COALESCE or CAST form), not in the caller. `validate` catches: only in the choices-rule
> shape; `mrjun.py crud verify --db` executes the SQL and *does* surface it.

> ⛔ **No `count` ⇒ "1–25 of 25" forever.** §7. `validate` catches: no.

> ⛔ **A `count` that exists but ignores the filter ⇒ a pager full of empty pages.** §6 — the `mrjun` scaffold
> emits `SELECT COUNT(*) AS total FROM <table>` with no parameters. `validate` catches: no.

> ⛔ **`find` with a non-blank `ruleIdentifier` is not the paged wrapper at all.** §2.2 — `findAll` and `count`
> stop being guaranteed to share the map, and the referenced rule may not even be in the bundle.
> `validate` catches: no.

> ⛔ **`context.data.localeKey` is always `null`; read the locale with `service.global.locale.getKey()`.** §3.
> Symptom: a fully translated project renders one language. `validate` catches: no.

> ⚠️ **Sorting/filtering the page you already hold gives wrong answers**, confidently. §6.

> ⚠️ **The localized column arrives as `row.localize`**, not under its DB name. §2.3. Symptom: every row shows the
> base language. `validate` catches: no.

> ⚠️ **A DOM listener bound with `addEventListener` is never removed for you.** The runtime auto-removes only
> `ctx.on` **bus** listeners; everything else must go through `ctx.onCleanup`, and teardown only runs when a *new*
> mount claims the same component wrapper id. Symptom after a few AJAX re-renders: one click fires the handler N
> times (N deletes, N reloads). Register before the first `await` — afterwards `ctx.on` refuses and `ctx.onCleanup`
> fires immediately (§4). `validate` catches: no.

> ⚠️ **`Promise.all` of two bridge calls freezes the page twice.** §2.5. Symptom: the whole tab is unresponsive
> for seconds and no spinner animates.

> ⚠️ **`ctx.busy`'s `block` selector is page-wide**, unlike its first argument. §8. Symptom: an unrelated
> component greys out with yours.

---

## 11 · Done when

**Done when:** paging, sorting and filtering all happen on the **server**, the count line shows a real total from
`count` under the same filter, one bridge call serves each interaction, and the table is proven live — page 2
holds different rows, the empty/loading/error states render inside the table, and the whole thing is legible on a
dark skin.

The evidence, in order:

- `mrjun.py validate` exits clean, and `mrjun.py crud verify --db "<conninfo>"` reports OK for the CRUD's
  `findAll` and `count` (including the sort `CASE` block).
- `mrjun.py show crud <alias>` shows `find.ruleIdentifier: null` (§2.2) and a `count` whose `parameters[]` match
  `findAll`'s filter parameters (§6).
- The page rule, called with `{page:0,size:25}` and `{page:1,size:25}`, returns **different** ids, and `total`
  equals `SELECT count(*)` under the same filter.
- Live on the page: page 2 shows different rows; the count line reads "26–50 of N" with the real N; clicking a
  header flips the arrow **and** changes which rows are on page 1 (proof the sort is server-side); typing in the
  search box fires **one** call after the pause and resets to page 1; clearing all filters returns the full count;
  the empty state, the error state (temporarily rename the rule) and the loading state all render inside the table
  with the right `colspan`.
- The table scrolls inside its wrapper on a 1280px viewport — the **page** does not scroll sideways — and the
  component is legible on `Standard` **and** on a dark skin (switch in Settings → Appearance).
- The page hosting the component carries no `crud.table.plugin` / `crud.tree.plugin` / `process.table.pluin`
  outside its own tab.

**Checklist:**

- [ ] §1 decision recorded: the layout feature the table plugin cannot express (§1)
- [ ] CRUD has `findAll` (CAST paging), `count` carrying **the same filter predicate AND the same `parameters[]`**, `find` (GROOVY sentinel, `ruleIdentifier: null` — verified, not assumed) (§2.2)
- [ ] Optional filters written in the COALESCE or CAST-guarded form; sortable columns in one `CASE` each; `ORDER BY` ends with the PK; sortable columns are indexed (§2.4, §6)
- [ ] `<Screen> Page` EXECUTION rule: clamps `size` (≤200) and `page`, whitelists `sortKey`/`sortDir`, normalises blank filters to `null`, calls `find` once, projects the view model (dates formatted, not raw `…Z` timestamps), returns `{content,total,totalPages,page,size,sortKey,sortDir}` — plain maps/lists/scalars only (§3)
- [ ] The rule reads the locale as **`service.global.locale.getKey()`** — `context.data.localeKey` appears nowhere (§3)
- [ ] Row-level authorization applied in the rule, not in JS (§3)
- [ ] Script: one call per interaction (never a call per row); `seq` in-flight guard; `alive` flag + `ctx.onCleanup`; every listener and cleanup registered **before the first `await`**; debounce 300 ms on typing / 0 on clicks; `paint()` before the blocking call; every DOM listener registered through `on()`; delegation from `<tbody>`/`<thead>`/pager; no `ctx.setHtml` (§4)
- [ ] Markup: `overflow-x` wrapper, sticky opaque header, `colspan`-correct empty/loading/error rows, `scope="col"`, `aria-sort`, `aria-busy`, `type="button"`, icon buttons carry `aria-label` and an `<i>` (§5)
- [ ] CSS in `css.byTheme["*"]` uses theme tokens only — no hex, no `h-100`, no bare `.badge`, no `.badge-light` (§5)
- [ ] Sorting and filtering are pushed down to the SQL, never applied to the page you already hold (§6)
- [ ] The total comes from `count` under the same filter — no `count`, no real "1–25 of N" line (§7)
- [ ] Row actions refetch after mutation (or justify the optimistic patch); page-level actions declared via `ctx.breadcrumb` with explicit ASCII keys (§8)
- [ ] `block` selectors point at a `<div>`, never a `<table>`, and are scoped to this instance (`'#' + ctx.root.id + ' …'`) (§8)
- [ ] The per-interaction budget holds: one round trip, ≤200 rows on the wire, no `Promise.all` of two bridge calls (§9)
- [ ] Rule referenced by identifier (or the exact name grepped after any rename) (§10)
- [ ] `mrjun.py validate --project ./app` exits 0 and `crud verify --db` is green, then `mrjun.py pack` (§10)

---

**See also:** [24](24-html-component-studio.md) (the studio: `studioModel`, `ctx.*`, libs, breadcrumb API) ·
[24a](24a-theming-and-dark-mode.md) (theme tokens, skins, the CSS scoper) ·
[04](04-crud-table-plugin.md) (the table plugin you are choosing not to use) ·
[05](05-crud-tree-and-process-table.md) (tree / process table) ·
[11](11-business-logic-dynamic-crud.md) (dynamic CRUD, method + query schema, paging SQL) ·
[08](08-groovy-rules-and-context.md) (rule types, `context`, aborting with a message) ·
[16](16-groovy-service-api.md) (`service.crud.*`, `service.rimm.*`, `service.security.*`) ·
[12](12-queries-sources-schedulers-and-rest.md) (saved queries as a page source) ·
[20](20-localization.md) (locale model, the `localize` map) ·
[22](22-charts-params-and-filters.md) (charts + theme-safe rendering) ·
[19](19-build-decision-procedure.md) (where a custom component enters the build) ·
[26](26-orchestration-and-testing.md) (live verification tiers) ·
[`tools/README.md`](tools/README.md) (`node set-studio`, `crud verify`, `validate`, `pack`)
