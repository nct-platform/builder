# 03 — Dynamic CRUD conventions that survive real data

> **Corrects and extends** [[11-business-logic-dynamic-crud.md](../11-business-logic-dynamic-crud.md)](../11-business-logic-dynamic-crud.md)
> and [[18-existing-schema-to-dynamic-wiring.md](../18-existing-schema-to-dynamic-wiring.md)](../18-existing-schema-to-dynamic-wiring.md).
> Measured over **244 CRUDs · 2 115 methods · 1 800 paired queries** in four delivered projects, referred
> to only by scale and style:
>
> | | scale | style |
> |---|---|---|
> | **A** | 163 CRUDs · 1 165 methods | **scaffold** — 160 near-identical 7-method CRUDs, integer PKs, hard delete, no filters |
> | **B** | 38 CRUDs · 480 methods | **document** — soft delete, 12 header+lines documents, 9 report CRUDs, the richest method sets |
> | **C** | 31 CRUDs · 296 methods | **queue + SLA** — soft delete, claim/expire/breach machinery, row-level scope |
> | **D** | 12 CRUDs · 174 methods | **compact document** — 4 documents, the claim quad, versioned parameters |
>
> **4/4** is a hard convention. **3/4** is a convention with one dissenter — and the dissenter is always A.
> **split** means you must decide consciously; the text says which way to jump. Entity names below are
> neutral (`document`, `documentLine`, `item`, `partner`, `case`); every slot name, SQL idiom and count is
> verbatim.

---

## 1. Five entity kinds — decide the kind before you write a method

Every one of the 244 falls into exactly one shape, and the method set follows mechanically.

| kind | count | method set | delete | typical use |
|---|---|---|---|---|
| **flat register** | 188 | canonical 7 (+ `undelete`) | soft or hard | master data |
| **register + lifecycle / queue** | 25 | canonical 8 + transitions + finders | soft | anything with a state column |
| **document (header + lines)** | 19 | canonical 8 + 5–6 line helpers + transitions + recompute | soft, GROOVY | anything with sub-rows |
| **read-only view / report** | 12 | **`find` + `findAll` + `count` only** | — | dashboards, cross-table roll-ups |
| **utility / service** | ~3 | bespoke named reads, no CRUD verbs | — | sweeps, identity lookups, migrations |

✅ **The report CRUD is the shape the library never names, and it is worth 12 of 244.** Three methods, no
table behind it: `findAll` is an inline derived query (UNION ALL / aggregate / multi-join) and `count`
wraps *the whole of findAll minus `ORDER BY`/`LIMIT`/`OFFSET`* in `SELECT COUNT(*) AS total FROM ( … ) rpt`.
It costs nothing and removes the temptation to invent a table for a screen that only reads. Alias
convention: `rpt<Subject>`.

---

## 2. The canonical method set

The shape 232 of 244 start from. Order, names, types and guards are all load-bearing.

```
methodOrder  method        type    returnsArray  parameters
   -1        find          GROOVY  false         = findAll's, exactly
    0        findAll       SQL     true          <filters…>, rowsInPage, pageNumber
    1        count         SQL     false         = findAll's minus rowsInPage/pageNumber
    2        get           SQL     false         id
    3        create        SQL     false         <every writable column, snake_case>
    4        update        SQL     false         <same as create> + id LAST
    5        delete        SQL     false         id
    6        undelete      SQL     false         id            ← soft-delete projects only
```

A document replaces 3/4/5 with GROOVY orchestrators and slots its helpers in behind them:

```
    3–5      create / update / delete   GROOVY, ruleIdentifier REQUIRED
    6–10     createHeader · updateHeader · insertLine · deleteLines · _deleteHeader   SQL
   11        undelete
   12–19     updateLine · deleteLinesExcept · findLines · insertExtraLine …
   20–29     lifecycle transitions   (submit, approve, reject, post, close, cancel …)
   30–39     derived values          (recomputeTotals, stampLines, find<X>Candidates …)
```

Verified invariants, counted:

| invariant | evidence |
|---|---|
| `find` −1 · `findAll` 0 · `count` 1 · `get` 2 · `create` 3 · `update` 4 · `delete` 5 | 4/4 · 241 CRUDs · zero exceptions |
| `undelete` = 6 on a flat CRUD, 11 when helpers occupy 6–10 | 3/3 soft-delete projects |
| `returnType` is the literal `"Object"` | **2 115 / 2 115** methods |
| `find.parameters == findAll.parameters` | 240 / 241 |
| `count.parameters == findAll.parameters − {rowsInPage, pageNumber}` | 240 / 241 |
| `get`'s SELECT list is **byte-identical** to `findAll`'s | **232 / 232** |
| every `findAll` carries an `ORDER BY` | 241 / 241 |
| `contextIdentifiers` is `null` on every method | 2 109 / 2 115 (six are `[]`) |
| every alias is in the project context's `crudAliases`, and the context lists nothing else | 4/4 · 245 aliases |

⛔ **`get` ≡ `findAll` is an invariant, not an aspiration.** Doc 11 warns that `get` "can lag `findAll`".
In 232 hand-maintained CRUDs it never does, because the projects treat the two SELECT lists as one
artefact. Gate it: `selectList(findAll) == selectList(get)`. Then a form reading `get` and a table reading
`findAll` cannot silently disagree.

**Banding.** Use `0–5 core · 6–10 line helpers · 11 undelete · 12–19 extra line ops · 20–29 transitions ·
30–39 derived`. The gaps are the point — a transition added later needs no renumbering. ⛔ Do not put the
SQL helpers at 3–8 and the GROOVY verbs at 9/10 (one project does): it breaks the `3=create, 4=update,
5=delete` reflex that holds everywhere else.

---

## 3. Naming

| thing | convention | evidence |
|---|---|---|
| alias | bare **camelCase singular** — `item`, `salesOrder`, `deadlineBreach` | 3/4 (81 aliases); A used `<snake_plural>_cruid` for all 162 of its own |
| `name` | human title in the UI language | 4/4 |
| reads | `find` / `findAll` / `count` / `get`; extra finders `find<Predicate>` returning arrays | 4/4 |
| counters | `count<Predicate>` | B, D |
| transitions | **the verb the user clicks**: `submit`, `approve`, `reject`, `post`, `close`, `cancel`, `reopen`, `activate`, `deactivate` | 3/3 |
| internal | a leading `_` means "never call this from a rule or a button" — `_deleteHeader` is the only one, and all 16 documents spell it that way | 3/3 |
| derived | `recompute<X>` · `stamp<X>` · `refresh<X>` · `apply<X>` | B, D |
| `dtoField` | `fieldName` = camelCase of the column; `displayName` = **the raw snake column** | 4/4 |
| `filterField` | `fieldName == displayName == the findAll parameter`, camelCase in both | **487 / 487** |
| paired query | `crud_<alias>_<methodName>` | 815/815 in B/C/D |

⚠️ **`displayName` means two different things and that is not a bug.** In `dtoFields` it is the source
column (`unit_price`); in `filterFields` it is the parameter name (`docDateFrom`). A filter field whose two
slots differ is a typo.

---

## 4. The paging `find` wrapper — one script, 240 times

`find` is GROOVY, `methodOrder: -1`, `queryIdentifier: null`, **`ruleIdentifier: null`**,
`contextIdentifiers: null`, `returnFields: null`, `returnsArray: false`. Character for character in 240 of
241 CRUDs:

```groovy
def filter = param ?: [:]
def countResult = service.crud.<alias>.count()
def total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long
def rows = service.crud.<alias>.findAll(filter) ?: []
def rowsInPage = (filter.rowsInPage ?: 0) as int
def pageNumber = (filter.pageNumber ?: 0) as int
return [
    content: rows,
    totalElements: total,
    totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,
    pageNumber: pageNumber
]
```

- The body is **never executed** while `ruleIdentifier` is null — the platform's auto-find intercepts and
  runs `findAll` + `count` itself with the same argument map. Write this form anyway; it is what every
  export in the estate carries.
- **`find` still declares the full parameter list** — all filters plus paging, identical to `findAll`
  (240/241). That declaration is what tells the table plugin which filter controls exist.

⛔ **The one anti-pattern: pressing Apply on `find`.** Six CRUDs in the scaffold project have a real
`ruleIdentifier` on `find`. Five have a body byte-identical to the auto-find wrapper — they buy nothing and
cost a Groovy execution per page load. The sixth reads the caller's identity, never uses it, and declares
zero parameters on `count` against a `findAll` that declares one: if the scope were ever applied, rows
would be filtered and `totalElements` would still report the whole table.

**Leave `find.ruleIdentifier` null. Row scope belongs in a table fetch rule (§18).** The project with the
strictest row security in the corpus implements all 12 of its scopes outside the CRUD.

---

## 5. The read triad

```sql
-- findAll (uuid PK, soft delete, business ordering)
SELECT t.<col>, …, (<expr>) AS display_label
FROM <table> t
  LEFT JOIN <target> j1 ON t.<fk> = j1.id
WHERE 1=1
  AND t.deleted = false
  AND <one guarded predicate per declared filter>
ORDER BY <business key> [, <unique tiebreaker>]
LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))

-- count: the SAME WHERE, no t. alias, no JOIN, no paging
SELECT COUNT(*) AS total FROM <table> WHERE 1=1 AND deleted = false AND <same predicates>

-- get: the SAME SELECT list as findAll, no paging
… WHERE t.id = CAST(:id AS uuid) AND t.deleted = false
```

- **Paging is always cast** — 259 of 260 paginated methods. The single exception carries
  `OFFSET (:pageNumber * :rowsInPage)`, which dies with `operator is not unique: unknown * unknown` the
  moment a rule rather than the table calls it.
- **`count` never joins** (4/4). A filter on a joined column must therefore be threaded through a
  sub-SELECT in `count`, not a JOIN — and the sub-SELECT must be byte-identical in both methods.
- **`ORDER BY` the business key with a unique tiebreaker.** The scaffold project orders 158/160 by PK,
  which is meaningless on a uuid. A bare `ORDER BY t.<timestamp> DESC` shuffles rows between pages when
  timestamps tie; `ORDER BY t.applied_at DESC NULLS LAST, t.creation_time DESC` is the only fully stable
  form in the corpus.
- ✅ **`display_label`.** 33 CRUDs add one computed column — `(t.code || ' — ' || t.name) AS display_label`
  → dtoField `displayLabel: String`. Every dropdown, reference cell and printed line then names **one**
  expression instead of concatenating in three places. Only 2/4 did it; adopt it anyway.

---

## 6. Optional filters — three idioms, one rule

Every filter predicate in B/C/D **anchors its parameter to `text` with a literal `''`**, so Postgres can
type the slot when the caller sends nothing:

```sql
-- 1. equality / nullable enum column
AND t.status IS NOT DISTINCT FROM COALESCE(NULLIF(:status,''), t.status)

-- 2. substring search
AND (NULLIF(:code,'') IS NULL OR COALESCE(t.code,'') ILIKE '%' || :code || '%')

-- 3. typed column reached through a text anchor
AND t.partner_id IS NOT DISTINCT FROM COALESCE(CAST(NULLIF(:partnerId,'') AS uuid), t.partner_id)
AND t.active     IS NOT DISTINCT FROM COALESCE(CAST(NULLIF(:active,'')    AS boolean), t.active)
AND t.applied_at >= COALESCE(CAST(NULLIF(:periodFrom,'') AS timestamp with time zone), t.applied_at)
```

A belt-and-braces variant anchors twice — `COALESCE(CAST(NULLIF(CAST(:x AS text),'') AS uuid), col)`,
188 occurrences — and is immune to a wrong declared `parameterType`.

⛔ **Postfix `::uuid` casts: 0 occurrences in 2 115 methods.** All four projects use the `CAST(… AS type)`
function form. Doc 18 §3's tree recipe still spells `parent_id IS NOT DISTINCT FROM :parentId::uuid`;
nothing in the estate writes that.

**Why the anchor matters more than the caller contract.** Doc 11 says a partial filter map from a rule
binds the missing parameter as `setNull(Types.NULL)` → an untyped placeholder. It does — *unless the slot
is text-anchored*. One project proves it: 96 of 96 rule call-sites pass partial maps and it works, because
every predicate is `NULLIF(:x,'')`-anchored. So:

- **Anchor every filter in SQL.** This is the defence you own.
- **Seed every declared key on the caller side too**, with `''` and never `null` — `''` takes the
  executor's `setString` arm and reaches the `NULLIF`; `null` leans entirely on the anchor.
- **Never ship a CRUD whose `count` has exactly one parameter.** 0 of 244 does: projects declare either
  none or ≥2. A filter set of ≥2 is structurally immune to the single-parameter positional-binding trap,
  so the cheapest fix for a one-filter table is a second filter.

**Dead filter fields.** 65 of the scaffold project's 160 CRUDs declare `filterFields` that `findAll` has no
parameter for. The control renders, the user types, the key travels, the executor ignores it, the list does
not change — silently. B/C/D: 0 mismatches in 81 CRUDs.
**Gate:** `set(filterFields.fieldName) == camel(findAll.parameters − paging)`.

---

## 7. Parameter declaration discipline

| rule | evidence |
|---|---|
| **Every GROOVY method declares `parameters[]`** — none empty | **295 / 295** |
| Every GROOVY method that is not `find` carries a `ruleIdentifier` | **54 / 54** |
| Every GROOVY `find` carries `ruleIdentifier: null` | 235 / 241 |
| `create`/`update` parameter names are snake_case (the column); paging and filters are camelCase | 4/4 |
| `update` repeats `create`'s list and appends `id` **last** | 4/4 |
| Filter parameters for boolean/uuid/date columns are declared `String` and cast in SQL | 236/236 |

⚠️ **`parameterType` is metadata, not binding.** One project declares `Instant`, `Boolean`, `Integer`,
`BigDecimal` on 223 parameters whose SQL then anchors them as text — and it runs. The executor infers the
JDBC bind from the SQL slot. What the field *does* drive is the derived `filterFields.fieldType` and the
Run dialog. Declare it honestly; put the cast in the SQL. Observed values: `String`, `Integer`,
`BigDecimal`, `Instant`, `Boolean`, `LocalDate`, and `ObjectNode` (10, on localization params) — the last
is outside the library's documented set and round-trips fine.

**`returnsArray` is set by result shape, not by method name.** 60 non-`findAll` methods are `true`.
**`returnFields`** is cosmetic — `null` on 100 % of B/C/D's 950 methods. Leave it null.

---

## 8. Foreign keys — the one split you must decide

| | **flat** | **nested** |
|---|---|---|
| projects | A (295 FK fields), C (42) | B (50), D (11) |
| dtoField | `partnerId` ← `partner_id`, `String`/`Integer` | `partner` ← `partner_id`, **`ObjectNode`** |
| SELECT alias | `j1.name AS partner_name` (single `_`) | `j1.id AS "partner__id", j1.code AS "partner__code", j1.name AS "partner__name"` |
| wire shape | `partnerName` beside `partnerId` | `{partner: {id, code, name}}` |
| write side | `:partner_id` | `CAST(NULLIF(:partner__id,'') AS uuid)` |
| form control | dropdown bound to `partnerId` | ObjectSelector bound to `partner`, reads `.name` |

**Jump nested when the entity is edited through forms with reference pickers or has sub-grids; jump flat
when the CRUD is mostly a table you read.** The two projects with real documents and pickers chose nested
for every business FK. Choose once and apply everywhere.

**The `{id, code, name}` triple.** Every nested FK lifts exactly three columns under a fixed shape, even
when the target has no column literally called `code` or `name` — the payoff is that one display
expression (`<ref>.name`) works for every reference cell in the app:

```sql
j1.id AS "sourceDoc__id", j1.doc_no AS "sourceDoc__code", j1.doc_no AS "sourceDoc__name",
j4.id AS  location__id,   j4.location_code AS location__code, j4.location_name AS location__name
```

⛔⛔ **Quote every camelCase SELECT alias.** Postgres folds unquoted identifiers to lower case, aliases
included. `j2.id AS sourceDoc__id` returns as `sourcedoc__id`, the control says
`"fieldExpression": "sourceDoc.name"`, the cell renders blank, and nothing errors. One project quotes all
132 of its camelCase aliases and leaves the all-lowercase ones bare; two others ship **208 unquoted**
against consumers that spell the camelCase form.
**Rule:** `AS "<ref>__<col>"` whenever either part contains an upper-case letter.
**Gate:** any `AS\s+[a-z_0-9]*[A-Z][A-Za-z_0-9]*` outside double quotes is a defect.

**Declare the FK both ways.** Every document orchestrator declares both names on `create`/`update`
(19/19): `<ref>__id` for the rule caller that sends `{ref:{id:…}}`, plain `<ref>` for the form dropdown
that sends a bare id string. It is free — an unsent parameter arrives absent — and it is the difference
between a working form and a NOT NULL violation naming a column the author never typed.

**`_id` is not always an FK.** In the nested projects these deliberately stay flat `<ref>Id: String`:
back-references and audit pointers (`reversal_id`, `corrected_from_id`, `source_doc_id`), polymorphic
pointers (`entity_id`, `reference_id`, `doc_line_id`), self-references (`parent_id`) — and identifiers
that are not relationships at all (a tax registration number ending in `_id`). Read
`schema.foreignKeys[]`; the suffix proves nothing. **Nested if a human picks it in a form; flat if the
machine writes it.**

---

## 9. Enums, lookups and status columns

**Zero `pg_enum` types across all four projects.** Every enum is a CHECK-constrained varchar — 208 CHECK
constraints across the four dumps — and doc 18's enum-lookup join alias `elN` appears **0 times**. Nobody
wrote `x_id = (SELECT id FROM lookup_x WHERE code = :x)` either.

```sql
-- create: a NOT NULL CHECK-varchar gets its default in the INSERT
COALESCE(NULLIF(:status,''), 'DRAFT')

-- update: never overwrite with NULL
status = COALESCE(:status, status)

-- lifecycle: a literal, guarded by the current state
SET status = 'POSTED' … WHERE … AND status = 'SUBMITTED'
```

**Every status literal in the corpus is inside its column's CHECK set — 119/119, zero violations.** Gate
it: parse `schema.checkConstraints[]`, extract the allowed set per `(table, column)`, and fail any
`SET <col> = '<literal>'` outside it.

✅ **One vocabulary table beats forty lookup CRUDs.** The document-style project factors every enum
vocabulary into a single CRUD — `refLabel(vocabulary, code, label, localized, sort_order, color)`, ordered
by `vocabulary, sort_order`, with `display_label = (vocabulary || ' — ' || code)`. One table, one CRUD, one
choices-rule shape, every dropdown in the app. The alternative — a `lookup_*` table per vocabulary — cost
the scaffold project forty near-identical CRUDs.

✅ **Keep business constants in a table, not in code.** 3/4 do: a `appSetting(setting_key, setting_value,
value_type, category)` register read through a `SETTING(key)` closure, and a policy register
(`code, duration_value, duration_unit, escalation_points, is_active`) that makes every deadline window and
escalation ladder a row rather than a constant.

---

## 10. Soft delete — a split, and the answer is soft

| | delete | undelete | read guard |
|---|---|---|---|
| A | `DELETE FROM t WHERE id = :id RETURNING *` ×160 | — | none |
| B | `UPDATE t SET deleted = true, modification_time = now()` ×27 | ×27 | 38/38 `findAll` |
| C | same ×27 (+4 hard on line tables) | ×27 | 27/31 |
| D | same ×12 | ×12 | 12/12 |

**Jump soft, and take the whole package:**

```sql
delete   : UPDATE <t> SET deleted = true,  modification_time = now() WHERE id = CAST(:id AS uuid) RETURNING *
undelete : UPDATE <t> SET deleted = false, modification_time = now() WHERE id = CAST(:id AS uuid) RETURNING *
findAll  : … WHERE 1=1 AND t.deleted = false …
count    : … WHERE 1=1 AND deleted = false …
get      : … WHERE t.id = CAST(:id AS uuid) AND t.deleted = false
create   : … , deleted, …) VALUES (…, false, …)     -- when the column has no DB default
```

Four details the library omits:

1. **`deleted` is never a `dtoField`** — 0 of 81 CRUDs in the soft-delete projects exposes it. It is a
   mechanism, not a business attribute. A user "deletes"; nobody edits a boolean called *deleted*.
2. **Child/line tables are hard-deleted and have no `undelete`.** The aggregate root owns the tombstone.
3. **`deleted` and `active`/`status` are different axes and both exist.** `deleted` means "this record was
   a mistake"; `INACTIVE` means "we no longer use it". Registers carry `activate`/`deactivate` *and*
   `delete`/`undelete`. Do not collapse them.
4. **A partial unique index is how uniqueness survives soft delete:**
   `ON CONFLICT (<key>) WHERE deleted = false DO UPDATE SET …`.

---

## 11. Audit columns

✅ **Stamp them in SQL so they cannot be forgotten** (3/4):

```sql
create : INSERT … (id, creation_time, modification_time, created_by, modified_by, …)
         VALUES (gen_random_uuid(), now(), now(), :created_by, :modified_by, …)
update : UPDATE … SET modification_time = now(), created_by = :created_by,
                      modified_by = :modified_by, <business columns> … WHERE id = CAST(:id AS uuid)
```

72/72 `create`/`createHeader` stamp `now()`; 69/72 `update` stamp `modification_time = now()`
**unconditionally, outside any COALESCE**. `created_by` / `modified_by` arrive as ordinary parameters,
filled by the calling rule from `service.security.user()?.email`.

⛔ **The anti-pattern (160/160 in one project):** `created_at` / `updated_at` declared as ordinary
parameters and written through the standard guards — `updated_at = COALESCE(:updated_at, updated_at)`. No
form submits them, so the column keeps its original value **forever**. It exists, it is in the DTO, it is
on screens, and it is a lie. Never make an audit timestamp a writable parameter.

**The localization column** (§07): 112 CRUDs use `COALESCE(:localized, localized)` on update — correct.
Twelve use a bare `:localized` on create *and* update, which **nulls the whole translation object on any
edit that does not resubmit it**, including edits made by the platform's own bulk localize task.

---

## 12. Documents (header + lines) — the full recipe

19 documents across three projects. The SQL helper set:

| helper | body |
|---|---|
| `createHeader` | `INSERT INTO <h> (id, creation_time, modification_time, created_by, modified_by, <cols>) VALUES (gen_random_uuid(), now(), now(), :created_by, :modified_by, …) RETURNING *` |
| `updateHeader` | `UPDATE <h> SET modification_time = now(), <col> = COALESCE(:col, col), … WHERE id = CAST(:id AS uuid) RETURNING *` |
| `insertLine` | `INSERT INTO <l> (id, <h>_id, creation_time, line_number, …) VALUES (gen_random_uuid(), CAST(NULLIF(:<h>_id,'') AS uuid), now(), COALESCE(:line_number, 1), …) RETURNING *` |
| `deleteLines` | `DELETE FROM <l> l WHERE l.<h>_id = CAST(:id AS uuid)` — **parameter named `id`**, so both `deleteLines(param.id)` and `deleteLines(param)` bind |
| `_deleteHeader` | `UPDATE <h> SET deleted = true, modification_time = now() WHERE id = CAST(:id AS uuid) RETURNING *` |
| `findLines` | `SELECT l.* FROM <l> l WHERE l.<h>_id = CAST(:<h>_id AS uuid) ORDER BY l.line_number` |

**The auto-number.** Every header mints its own when the form leaves it blank:

```sql
COALESCE(NULLIF(:doc_no,''),
         'DOC-' || to_char(now(),'YYYY') || '-' ||
         upper(substr(replace(CAST(gen_random_uuid() AS text),'-',''),1,6)))
```

⛔ The counter variant — `'DOC-' || year || '-' || lpad((SELECT count(*)+1 FROM <t>)::text,5,'0')` — is
racy and collides after deletes. Prefer the uuid suffix; it needs no table scan.

**Lines on the read side** — a correlated `json_agg`, each line FK expanded to the `{id, code, name}`
triple through its own `jlN` join, so no sub-grid cell shows a raw uuid:

```sql
(SELECT COALESCE(json_agg(json_build_object(
          'id', l.id, 'lineNumber', l.line_number,
          'item', json_build_object('id', l.item_id, 'code', jl1.item_code, 'name', jl1.item_name),
          'qty', l.qty, 'uom', l.uom, 'lineCost', l.line_cost
        ) ORDER BY l.line_number), CAST('[]' AS json))
 FROM <line> l LEFT JOIN item jl1 ON l.item_id = jl1.id
 WHERE l.<header>_id = t.id) AS lines
```

`COALESCE(json_agg(…), CAST('[]' AS json))` matters: a document with no lines must yield `[]`, not `null`,
or the sub-grid renders nothing instead of an empty grid. Keys inside `json_build_object` are already
camelCase and bypass the row mapper, so no quoting question arises there. **`lines` is not a `dtoField`**
in any of the 19.

### The orchestrator prelude — lift this verbatim

`create`/`update`/`delete` are GROOVY with a `ruleIdentifier` (54/54), each declaring one parameter per key
the caller sends: every header column, **both** FK spellings, the `lines` key (declared
`parameterType: "String"`), and `id` on update/delete. Two projects share a byte-identical prelude, and it
is what makes the same method work from a form (Jackson `JsonNode`), from a rule (Groovy `Map`) and from a
scheduler (bare scalars):

```groovy
def _size = { c -> c == null ? 0 : ((c instanceof List) ? c.size() : (c.isNull() ? 0 : c.size())) }
def _at   = { c, i -> (c instanceof List) ? c[i] : c.get(i) }
def _num  = { ln, k -> if (ln instanceof Map) { return ln[k] }
    return (ln.has(k) && !ln.get(k).isNull()) ? ln.get(k).numberValue() : null }
def _txt  = { ln, k -> if (ln instanceof Map) { def v = ln[k]; return v == null ? null : v.toString() }
    return (ln.has(k) && !ln.get(k).isNull()) ? ln.get(k).asText() : null }
def _ref  = { ln, k -> if (ln instanceof Map) { def v = ln[k]
        return (v instanceof Map) ? (v['id']?.toString()) : (v == null ? null : v.toString()) }
    if (!ln.has(k) || ln.get(k).isNull()) { return null }
    def n = ln.get(k)
    return n.isObject() ? (n.get('id')?.isNull() ? null : n.get('id')?.asText()) : n.asText() }
def _lineNo = { ln, i -> def v = _num(ln, 'lineNumber'); return v != null ? v : (i + 1) }
def _id = { v ->
    if (v == null) { return null }
    if (v instanceof Map) { def m = v['id']; return m == null ? null : m.toString() }
    if (v instanceof CharSequence) { def s = v.toString().trim(); return s.isEmpty() ? null : s }
    if (v.respondsTo('isNull') && v.isNull()) { return null }
    if (v.respondsTo('isObject') && v.isObject()) {
        def n = v.get('id'); return (n == null || n.isNull()) ? null : n.asText() }
    if (v.respondsTo('asText')) { def s = v.asText(); return (s == null || s.trim().isEmpty()) ? null : s }
    def s = v.toString().trim(); return s.isEmpty() ? null : s }
def _fk = { k -> def v = param[k + '__id']; return _id(v != null ? v : param[k]) }
```

```groovy
def hdr = new LinkedHashMap(param)
hdr['partner__id']   = _fk('partner')
hdr['sourceDoc__id'] = _fk('sourceDoc')
def h   = service.crud.<alias>.createHeader(hdr)
def hid = (h instanceof Map) ? h.id : h?.get('id')?.asText()
def lines = param.lines
def n = _size(lines)
for (int i = 0; i < n; i++) {
    def ln = _at(lines, i)
    service.crud.<alias>.insertLine([ <header>_id: hid,
                                      line_number: _lineNo(ln, i),
                                      item_id:     _ref(ln, 'item'),
                                      qty:         _num(ln, 'qty'),
                                      note:        _txt(ln, 'note') ])
}
return service.crud.<alias>.get(hid)
```

`update` is the same with `updateHeader(hdr)`, then `deleteLines(param.id)`, then the identical loop.

Three things that are easy to get wrong:

- **`insertLine` is called with a hand-built map, never the raw line node.** Each key is named exactly as
  `insertLine`'s SQL parameter, and each value passes through `_num`/`_txt`/`_ref`.
- **The header id goes in flat** (`<header>_id: hid`) because the script holds a scalar; line **FKs** go
  through `__id` because they arrive from the sub-grid's pickers.
- ⛔ **Never write `lines.eachWithIndex { ln, i -> new LinkedHashMap(ln instanceof Map ? ln : [:]) }`.**
  A Jackson `ObjectNode` is iterable but is **not** a `java.util.Map`, so that expression silently produces
  an empty line for every submitted row: the header saves, the lines vanish, nothing errors. The
  `_size`/`_at`/`_num`/`_txt`/`_ref` accessors exist precisely to prevent it.

⛔⛔ **A soft-deleted document must NOT cascade-delete its lines.** Both library docs say `delete` must
clear the lines first. All 19 documents deliberately do not, and one says why in a comment: an `undelete`
must bring the whole document back, not an empty shell. The doc's rule is right for a **hard** delete (the
line→header FK is `NO ACTION`, so a bare header `DELETE` fails). The correct statement is conditional:
**cascade when the header row is really removed; keep the lines when the header is only flagged.**
`deleteLines` still exists — `update` calls it when it rewrites the line set.

---

## 13. Lifecycle transitions — SQL, guarded, terminal-last

A transition is a plain SQL `UPDATE`, never GROOVY: 122 across three projects, each taking `id` plus
whatever it records.

```sql
-- entry transition: guard the previous state, stamp who and when
UPDATE <t> SET status = 'SUBMITTED', submitted_at = now(),
               submitted_by = COALESCE(NULLIF(:actor,''), submitted_by),
               modification_time = now()
 WHERE id = CAST(:id AS uuid) AND status = 'DRAFT' RETURNING *

-- reverse transition: guard the state it undoes, clear what it stamped
UPDATE <t> SET status = 'DRAFT', submitted_at = NULL, submitted_by = NULL, modification_time = now()
 WHERE id = CAST(:id AS uuid) AND status = 'SUBMITTED' RETURNING *
```

**The `AND status = '<previous>'` clause is the state machine.** With it, a double-click, a stale tab or a
concurrent user produces `UPDATE 0` and `RETURNING *` yields nothing — no exception, no double posting.
Adoption is split (62/89 · 7/8 · 3/25); **jump guarded**. The cost is one clause; the failure it prevents is
a posted document posted twice.

**Pair the SQL guard with a readable pre-check in the calling rule**, so the user gets a sentence rather
than a silent no-op:

```groovy
def doc = service.crud.<alias>.get(subjectId.toString())
if (doc == null)                 { throw new RuntimeException("Document not found: " + subjectId) }
if (doc.status != 'SUBMITTED')   { throw new RuntimeException("Only a SUBMITTED document can be posted (current: " + doc.status + ")") }
if ((doc.lines ?: []).isEmpty()) { throw new RuntimeException("Add at least one line before posting") }
```

✅ **Flip the state LAST.** Every posting rule follows one order, and the order is the recovery story:

```
1. business validations              → throw; nothing has changed
2. stamp snapshots onto the lines    → freeze code/name/price
3. recompute header aggregates
4. re-read the document you rewrote
5. per line: settle the source, write the ledger row
6. post(id, actor)                   → the state flip, LAST
```

If anything in 1–5 throws, the document is still `SUBMITTED` and the operator can fix and re-run. Flip
first and a half-posted document is stuck `POSTED` with no ledger behind it.

---

## 14. Derived-value methods

All SQL, all `methodOrder` 30+, all taking just `id`.

```sql
-- recomputeTotals — header aggregates from lines (12 occurrences)
UPDATE <h> h SET total_qty    = COALESCE((SELECT SUM(l.qty)       FROM <l> l WHERE l.<h>_id = h.id), 0),
                 total_amount = COALESCE((SELECT SUM(l.line_cost) FROM <l> l WHERE l.<h>_id = h.id), 0),
                 modification_time = now()
 WHERE h.id = CAST(:id AS uuid) RETURNING *
```

**`stampLines`** (8 occurrences) freezes the master data that must not move after posting —
`<x>_code_snapshot`, `source_unit_cost` — with `COALESCE(<subquery>, l.<existing>)` per column plus a
computed `line_cost = ROUND(qty * cost, 2)`. The `_snapshot` suffix tells the next reader "this is history,
not a join".

**Versioned parameters** — the triad that makes an approved number immutable:

```sql
nextVersion      : SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM <t> WHERE <parent>_id = CAST(:x AS uuid)
supersedeOthers  : UPDATE <t> SET status='SUPERSEDED', … WHERE deleted=false AND <parent>_id=CAST(:x AS uuid)
                                  AND status='ACTIVE' AND id <> CAST(:id AS uuid) RETURNING *
activate         : UPDATE <t> SET <derived cols> = ROUND(<formula>, 3), status='ACTIVE', …
                    WHERE deleted = false AND id = CAST(:id AS uuid) RETURNING *
findActiveByX    : SELECT t.* FROM <t> WHERE deleted=false AND <parent>_id=CAST(:x AS uuid)
                    AND status='ACTIVE' ORDER BY effective_from DESC, version DESC LIMIT 1
```

`activate` computing the derived columns **at activation time** rather than on read is the pattern: the
numbers a downstream calculation depends on are frozen the moment somebody approved them.

---

## 15. Queue / claim methods — the shape for scheduler-driven work

The most transferable multi-method pattern in the corpus; two projects grew it independently.

```
find<X>Candidates        SQL, array, paged  — unclaimed, oldest first
count<X>Candidates       SQL                — the badge on the screen
claimFor<X>              SQL                — atomic guarded UPDATE, sets the claim marker
set<X>Process            SQL                — attach the real process identifier
find<Claimed>Without<X>  SQL, array         — stale-claim reaper
release<X>Claim          SQL                — release a stale claim
end<X>                   SQL                — clear both markers when the process finishes
```

✅ **Use two columns, not a sentinel.** The stronger dialect keeps a claim timestamp *and* the identifier,
plus an attempt counter:

```sql
claimForCase           : UPDATE t SET process_started_at = now(),
                                      process_start_count = COALESCE(process_start_count, 0) + 1, …
                          WHERE id = CAST(:id AS uuid) AND deleted = false
                            AND status = 'NEW' AND process_started_at IS NULL RETURNING *
setCaseProcess         : UPDATE t SET process_identifier = :process_identifier, … WHERE id = CAST(:id AS uuid) RETURNING *
findClaimedWithoutCase : SELECT t.id, t.doc_no, t.process_started_at FROM t
                          WHERE t.deleted = false AND t.status = 'NEW'
                            AND t.process_started_at IS NOT NULL AND t.process_identifier IS NULL
                            AND t.process_started_at < now() - INTERVAL '5 minutes'
                          ORDER BY t.process_started_at LIMIT 50
releaseCaseClaim       : UPDATE t SET process_started_at = NULL, … WHERE id = CAST(:id AS uuid)
                          AND process_identifier IS NULL AND process_started_at < now() - INTERVAL '5 minutes' RETURNING *
endCase                : UPDATE t SET process_started_at = NULL, process_identifier = NULL, … WHERE id = CAST(:id AS uuid) RETURNING *
```

It can distinguish "claimed but the process never started" from "never claimed" — exactly what the reaper
needs — and the counter shows you a row that keeps failing. The weaker dialect writes `'CLAIMING'` into the
identifier column itself and cannot.

**`RETURNING *` on the claim is the lock.** A null return means somebody else has it; the caller moves on.
That is the whole concurrency control — no advisory locks, no `SELECT FOR UPDATE`.

**Paging for a scheduler caller** — defaults in SQL so the method can be invoked with no arguments, and
deliberately snake_case names to signal "this is not the table's method":

```sql
LIMIT  COALESCE(CAST(NULLIF(:rows_in_page,'') AS integer), 200)
OFFSET (COALESCE(CAST(NULLIF(:page_number,'') AS integer), 0) *
        COALESCE(CAST(NULLIF(:rows_in_page,'') AS integer), 200))
```

✅ **`ON CONFLICT` as the dedupe gate.** Put idempotency in the CRUD method, not the rule:

```sql
recordWarning : INSERT INTO <warning> (subject_type, subject_id, clock_code, escalation_point, …,
                                       warned_at, deleted, creation_time, modification_time)
                VALUES (COALESCE(NULLIF(:subjectType,''), 'CASE'), CAST(NULLIF(:subjectId,'') AS uuid), …,
                        now(), false, now(), now())
                ON CONFLICT DO NOTHING RETURNING *
```

```groovy
def w = service.crud.<warning>.recordWarning([ … ])
if (w == null) { return 0 }        // already warned at this point — say nothing
// …only now send the mail
```

That one line is what stops a 30-minute sweep from mailing the same person 48 times a day.

**Deadline finders** — the window comes from the policy table, not a constant:

```sql
findAtRisk  : SELECT *, EXTRACT(EPOCH FROM (target_at - now()))/3600.0 AS hours_left FROM <t>
               WHERE deleted = false AND state IN (…) AND target_at IS NOT NULL AND done_at IS NULL
                 AND target_at > now()
                 AND target_at < now() + COALESCE(CAST(NULLIF(:withinHours,'') AS integer), 2) * INTERVAL '1 hour'
               ORDER BY target_at LIMIT :rowsInPage OFFSET (…)
markOverdue : UPDATE <t> SET state='OVERDUE', modification_time=now()
               WHERE id = CAST(NULLIF(:id,'') AS uuid) AND state IN ('OPEN','IN_PROGRESS') RETURNING *
```

A `NOT EXISTS` against the escalation table inside the finder makes "don't tell me twice" the finder's job
rather than the rule's.

---

## 16. Guarding writes to NOT NULL columns

| target | write |
|---|---|
| NOT NULL text with a default | `COALESCE(NULLIF(:status,''), 'DRAFT')` |
| NOT NULL numeric | `COALESCE(:total_qty, 0::numeric)` |
| NOT NULL integer | `COALESCE(CAST(NULLIF(:version,'') AS integer), 1)` |
| NOT NULL boolean | `COALESCE(CAST(NULLIF(:is_active,'') AS boolean), false)` |
| any NOT NULL column on `update` | `COALESCE(:c, c)` |
| **nullable** column on `update` | **bare `:c`** — deliberate, so a cleared field clears |
| nullable uuid FK | `CAST(NULLIF(:x__id,'') AS uuid)` |
| NOT NULL uuid FK on `update` | `COALESCE(CAST(NULLIF(:x__id,'') AS uuid), x_id)` |

The asymmetry is intentional and consistent — wrapping a nullable column in `COALESCE` makes it impossible
to erase a value from the UI. Classify each column once, then write the matching guard.

---

## 17. `create` and the three PK branches

| PK shape | `create` | `get.id` type |
|---|---|---|
| `integer … DEFAULT nextval(...)` | **omit `id`** from the INSERT | `Integer` |
| `uuid`, **no** DB default | `INSERT … (id, …) VALUES (gen_random_uuid(), …)` | `String` |
| `uuid` **with** a DB default | **omit `id`** | `String` |

All three occur. **Read the PK's default off `db show <table>` before writing `create`** — emitting
`gen_random_uuid()` into a serial column fails on the first insert with *column "id" is of type integer but
expression is of type uuid*, and no offline gate sees it.

---

## 18. Row scope — the fetch rule, not the CRUD

The reference implementation keeps `find` in its plain form and puts the scope in a **table fetch rule**:

```groovy
def _rows = { r -> (r instanceof Map ? (r.content ?: []) : (r ?: [])) }

def _myScope = { ->
    def me = (service.security.user()?.email ?: '') as String
    if (me.isEmpty()) { return '00000000-0000-0000-0000-000000000000' }        // fail CLOSED
    def rs = _rows(service.crud.appUser.find([ email: me, fullName: '', orgUnitId: '',
                                               isActive: 'true', rowsInPage: 5, pageNumber: 0 ]))
    if (rs.isEmpty()) { return '00000000-0000-0000-0000-000000000000' }        // fail CLOSED
    def u = (rs[0].orgUnitId ?: rs[0].orgUnit?.id)
    return (u == null ? '00000000-0000-0000-0000-000000000000' : (u as String)) }

// Paging and filters arrive from the table via attrs (Jackson JsonNode).
// `param` is EMPTY outside a delegated CRUD method — reading it here silently drops
// the filter form, the column filters AND the paging.
def filter = [ 'rowsInPage': attrs?.get('rowsInPage')?.asInt(),
               'pageNumber': attrs?.get('pageNumber')?.asInt() ]
attrs?.each { k, v ->
    if (k != 'rowsInPage' && k != 'pageNumber' && v != null && !v.isNull()) {
        filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText()) } }
// the scope is written LAST so a client-supplied value can never widen it
if (!service.security.hasAnyRoleGroup("<oversight>", "<oversight>")) { filter['orgScopeId'] = _myScope() }
return service.crud.<alias>.find(filter)
```

The five rules that make it correct, verified across all 12 scoped CRUDs:

1. **The scope key is a declared parameter of BOTH `findAll` and `count`.** Otherwise rows come back scoped
   and `totalElements` reports the whole table.
2. **The scope is written after the forwarded filters**, so a crafted client filter cannot widen it.
3. **It fails closed** — an unresolvable user gets an all-zero uuid that matches nothing, never `null`
   (which the `COALESCE(…, col)` guard reads as "no filter" = see everything).
4. **Read `attrs`, not `param`** — a fetch rule is not a delegated CRUD method.
5. **The predicate uses the same `COALESCE`/`NULLIF` guard as any other filter**, so the privileged path
   (key absent) is a no-op:
   `AND t.partner_id IN (SELECT p.id FROM partner p WHERE p.org_unit_id IS NOT DISTINCT FROM COALESCE(CAST(NULLIF(CAST(:orgScopeId AS text),'') AS uuid), p.org_unit_id))`

Name the key `<scope>ScopeId` when it must be reached through a join and plain `<scope>Id` when the table
carries the column itself.

---

## 19. Every SQL method is stored twice — keep the copies equal

The `:name` form in `methods[].script` is what runs; the `{name:'x', type:'y'}` form in the paired query is
what the editor loads. Three projects keep them perfectly aligned (815/815). The scaffold project shows
both failure modes, and both are silent:

1. **Drift (131 methods).** The paired query carries a newer SELECT than the method does — an extra display
   column that never reaches the wire, because the executor runs `methods[].script`. Whoever fixed the SQL
   fixed the wrong copy. Worse in reverse: the next person who merely *opens* that method in the editor
   loads the query's version, and saving reverts the running SQL.
2. **Cross-wiring (126 methods).** One CRUD's methods point at another CRUD's query records — the signature
   of a CRUD duplicated in the UI without re-minting its queries. Opening and saving one now overwrites the
   other's SQL.

```
for every SQL method m of crud c:
    assert query[m.queryIdentifier].name == "crud_" + c.alias + "_" + m.methodName
    assert normalise(placeholders_to_colon(query[m.queryIdentifier].query)) == normalise(m.script)
```

---

## 20. The source block

**All 244 CRUDs carry `sourcePassword: null`, and so does every `sources[]` record** (4/4, no exceptions).
The export scrubs credentials; the import takes live ones from `sources[]` by `sourceIdentifier`. The other
seven fields are filled identically on every CRUD.

⛔ **A `sourceIdentifier` that resolves to nothing in `sources[]` is a dead CRUD.** One project points a
CRUD at a second source whose UUID appears in no `sources[]` record: on import there is nothing to take
credentials from, the snapshot password is `null`, and every SQL method on it fails at connect time.
**Gate:** `{crud.sourceIdentifier} ⊆ {source.identifier}`.

---

## 21. Where the deliveries contradict the library — and who is right

| # | the library says | the deliveries do | verdict |
|---|---|---|---|
| 1 | `sourcePassword` is "in plaintext in the export"; fill all 8 fields | `null` in 244/244 CRUDs and 5/5 sources | **deliveries right.** Fill seven; never write a credential into an export |
| 2 | a document `delete` MUST cascade to its lines | 16/16 soft-delete documents deliberately keep them | **deliveries right, doc incomplete.** Cascade on hard delete; keep on soft |
| 3 | an FK dtoField is `<ref>Id`, "never `<ref>`" | 61 FK dtoFields are the bare `<ref>` with `ObjectNode`, as those projects' default | **both right — it is a project-level decision.** Choose once (§8) |
| 4 | enum-lookup FK writes as `(SELECT id FROM lookup_x WHERE code = :x)`, joined as `elN` | **0 occurrences**; every enum is a CHECK-varchar, vocabularies live in one register | **deliveries right** for a schema you are designing; keep the doc's rule only where `lookup_*` tables already exist |
| 5 | tree predicate `parent_id IS NOT DISTINCT FROM :parentId::uuid` | 0 postfix casts in 2 115 methods | **deliveries right.** Use `CAST(NULLIF(:x,'') AS uuid)` |
| 6 | `returnsArray` true for `findAll`, false for the rest | 60 non-`findAll` methods are true | **deliveries right.** Set it by result shape |
| 7 | the single-parameter `count` trap is "the DEFAULT shape" | 0 of 244 has a one-parameter `count` | **doc right about the mechanism, wrong about frequency.** Make it a design rule: never ship a CRUD with exactly one filter |
| 8 | never `(:col IS NULL OR col = :col)` | the anchored form of it is in use and works | **doc right about the bare form, over-broad about the shape.** The load-bearing part is the text anchor, not the operator |
| 9 | seed every declared filter key on the caller side | 96/96 call-sites pass partial maps and work | **doc right, state the reason.** Anchoring makes partial maps safe; seeding is the second line. Seed with `''`, never `null` |
| 10 | "`get` can lag `findAll`" (a hazard) | byte-identical in 232/232 | **promote to an invariant with a gate** |
| 11 | localization column on update → `COALESCE(:localized, localized)` | 112 follow it; 12 use a bare `:localized` and null the translations | **doc right.** Always COALESCE it |
| 12 | alias suffix is "that project's habit" | 81 bare camelCase singular vs 162 suffixed | **pick camelCase singular** — it reads correctly in `service.crud.<alias>.<method>()` |
| 13 | *(unstated)* | 208 unquoted camelCase SELECT aliases, consumers spelling the camelCase form | **new rule.** `AS "<ref>__<col>"` whenever either part has an upper-case letter |
| 14 | *(unstated)* | `deleted` is a dtoField in 0 of 81 | **new rule.** Keep the tombstone out of the DTO |
| 15 | *(unstated)* | `filterFields.fieldName == displayName` in 487/487 | **new rule**, and a free gate |
| 16 | *(unstated)* | audit timestamps stamped in SQL (3/4) vs writable parameters (1/4, where they never change) | **new rule.** Stamp in SQL |

---

## 22. Offline gates worth running on any dynamic export

Each caught something real; none needs a database.

```
 1. selectList(findAll) == selectList(get)                              # 0 failures in 232 — keep it that way
 2. find.parameters == findAll.parameters                               # 1 failure
 3. count.parameters == findAll.parameters - {rowsInPage, pageNumber}   # 1 failure
 4. filterFields == camel(findAll.parameters - paging), fieldName == displayName   # 65 failures
 5. every SQL method has a query named crud_<alias>_<method>            # 126 failures
 6. query body (placeholders → :name) == methods[].script               # 131 failures
 7. no crud_* query orphaned; no query body blank                       # 150 orphans
 8. crud.sourceIdentifier ∈ sources[].identifier                        # 1 failure
 9. no  OFFSET (:pageNumber * :rowsInPage)  — require the CAST form     # 1 failure
10. no unquoted SELECT alias containing an upper-case letter            # 208 failures
11. no glued keyword:  /[A-Za-z0-9_)'"](WHERE|FROM|SET |RETURNING|JOIN)\b/   # 3 broken methods
12. every GROOVY method that mentions `param` declares parameters[]     # 0 failures
13. every GROOVY method except `find` has a ruleIdentifier              # 0 failures
14. every GROOVY `find` has ruleIdentifier == null                      # 6 failures
15. every SET <col> = '<literal>' is inside that column's CHECK set     # 0 failures
16. every alias appears in exactly one context's crudAliases            # 0 failures
17. soft-delete CRUD: `deleted` guard on findAll AND count AND get; `deleted` absent from dtoFields
18. no count() declares exactly one parameter
19. every `<ref>__id` parameter has a sibling plain `<ref>` parameter
20. lifecycle UPDATE writing a status literal carries a current-state predicate
```

Gates 11 and 14 are the cheapest wins: three methods in the corpus are **syntactically broken SQL**
(`… FROM <table>WHERE …`, `… modification_time = now()WHERE id = …`) and throw on first call. `validate`
cannot see them; `crud verify --db` can; a 20-character regex can.
