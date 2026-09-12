# 18 — Wiring an EXISTING schema (with data) to dynamic CRUDs

> 📐 **Field evidence — wiring an existing schema, as four projects did it:** [03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

**What this is.** The rest of the library builds a project *forwards*: design a schema, then add cruds/forms/
pages on top. This doc covers the **reverse, and very common, scenario**: you are handed a **populated business
schema** (tables + data + constraints) and must wire it to dynamic CRUDs, so the app runs with **no compiled
service** behind it. Two shapes of it:

- **(a) You also received a complete UI** — an export whose `project-db.dump` carries the data *and* whose
  `branches.json`/`rep-objects.json` already hold pages, forms, crud tables, rules and a context listing crud
  aliases — and the only thing missing is the **dynamic-integration wiring**: a `source`, `dynamic-cruds.json`
  and the paired queries. (This is what a project whose business logic used to live in a compiled service looks
  like once the UI has been exported.) The whole doc applies as written.
- **(b) You have only the schema and its data.** Then §0/§1/§3/§5 apply unchanged — they are about deriving
  CRUDs and SQL from the tables — and the UI comes from the ordinary build order in
  [13](13-master-playbook-empty-to-dynamic-project.md); come back here for the per-column rules and the
  document header/lines shape.

This is easy to get *90% right and 10% broken*, because the broken 10% only surfaces at runtime against real
rows. The whole point of this doc is the 10%. **Read it, and run `mrjun.py validate` + `mrjun.py crud verify
--db …` (both encode these rules).**

---

## 0. Golden rule: the dump is the contract — parse ALL of it

`list-tables` shows columns only. A dynamic CRUD over an existing table must honor everything else too. Use
**`mrjun.py db show <table> --schema <s>`** — it prints columns (type / NOT NULL / default), PK, and the
**CHECK / UNIQUE / FK** constraints that live in `schema.checkConstraints[]` / `uniqueConstraints[]` /
`foreignKeys[]` — *not* in the table `ddl`, so they are trivial to miss.

| Schema fact | Where in the dump | Why it bites |
|---|---|---|
| NOT NULL, default | table `ddl` per-column | a `create` that omits a NOT NULL column with no default throws |
| **CHECK (status IN …)** | `schema.checkConstraints[]` | a lifecycle method writing a status the CHECK forbids throws **on any real row** (invisible against an empty table) |
| FK target | `schema.foreignKeys[]` | decides nested-object vs enum-string surfacing; a hard delete of a referenced row fails |
| rows (lookup tables) | table `rows[]` | the option list for an enum dropdown |

---

## 1. Per-column generation rules (create / update / findAll)

For each business table, classify every column and emit accordingly. (`mrjun.py` does not auto-emit this SQL
today — you write it, following this table; then `validate`/`crud verify` check it.)

| Column kind | findAll / get | create | update |
|---|---|---|---|
| PK **with** a DB default (`nextval(...)` / `gen_random_uuid()` / `uuid_generate*` — read it off `db show <table>`) | `t.id` | **omit the column from the INSERT entirely** — the DB fills it | — (WHERE id=:id) |
| `id` uuid PK, **no** default | `t.id` | `gen_random_uuid()` (no param) | — (WHERE id=:id) |
| **non-uuid** PK, no default (a `varchar` code, an `integer` the caller supplies) | `t.id` | `:id` — parameterize; the form supplies the value | — (WHERE id=:id) |
| `creation_time` / `modification_time` NOT NULL, no default (JPA `@PrePersist`/`@PreUpdate`) | `t.<c>` | `now()` | modification → `now()`; creation → not in SET |
| `custom_fields` jsonb | `t.custom_fields` | omit (nullable) | omit |
| `localize` jsonb (the localizationField) | `t.localize` | `:localize` | `COALESCE(:localize, localize)` |
| **business FK** `x_id` → business table | `LEFT JOIN <tgt> j ON t.x_id=j.id`, select `j.id AS x__id, j.code AS x__code, j.name AS x__name` → row `{x:{id,code,name}}` | `x_id = :x__id` (executor walks `{x:{id}}` via the `__` path) | `x_id = COALESCE(:x__id, x_id)` |
| **enum-lookup FK** `x_id` → `lookup_x` | `LEFT JOIN lookup_x lx ON t.x_id=lx.id`, select `lx.code AS x` → row `x:"CODE"` (the enum constant, flat string) | `x_id = (SELECT id FROM lookup_x WHERE code = :x)` | `x_id = COALESCE((SELECT id FROM lookup_x WHERE code=:x), x_id)` |
| `company_id` (no dropdown; single-company mode) | (as a business FK) | `COALESCE(:company__id, (SELECT id FROM company ORDER BY creation_time LIMIT 1))` | `COALESCE(:company__id, company_id)` |
| auto number (`order_number`/`document_number`/`bom_number`…) NOT NULL, not on the form | `t.<c>` | `COALESCE(NULLIF(:<c>,''), '<PREFIX>-' \|\| …unique…)` | `COALESCE(:<c>, <c>)` |
| `status` / `*_status` NOT NULL enum-varchar, set by lifecycle | `t.status` | `COALESCE(NULLIF(:status,''), '<valid default in the CHECK set>')` | `COALESCE(:status, status)` |
| plain NOT NULL (code/name/currency/dates/bools) | `t.<c>` | value, or `COALESCE(:<c>, <typed default>)` | `COALESCE(:<c>, <c>)` |
| plain nullable | `t.<c>` | `:<c>` | `:<c>` |

> ⚠️ **Three PK branches, not one — read the PK's DB default before you write `create`.** A schema you did not
> design is as likely to use a sequence-backed integer PK (`DEFAULT nextval('<schema>.<t>_id_seq'::regclass)` —
> the "dimension / sequence" style in [10-database-management.md](10-database-management.md) §"Two entity styles")
> as the JPA-style bare `uuid`. The rest of this table's rows (JPA audit preamble, `custom_fields`/`localize`
> jsonb, `company_id`, CHECK-varchar `status`) describe the uuid style; the PK rule is the one that differs.
> Emitting `gen_random_uuid()` into an integer PK fails on the **first** create with
> `column "id" is of type integer but expression is of type uuid`, and `validate` cannot see it offline — only
> `crud verify --db` or the browser will. The platform's own three-way emitter rule is in
> [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) §Step 2.

**Binding facts you rely on** (`DynamicMethodExecutor`): a snake `:order_number` param binds the camelCase DTO
key `orderNumber` (`toCamelCase` first); a `:x__id` param walks the nested `{x:{id}}`; `:localize` maps the
localization column; a single positional arg (id) or multiple positional args (lifecycle
`updateStatus(id, 'X')`) bind by order. Output `mapRow` camelCases every column, and a `foo__bar` alias becomes
`{foo:{bar}}`.

> **A real pg_enum (`USER-DEFINED`) status column — bind plain, no `::type` cast.** If a status column is an actual
> Postgres enum type (not the more common CHECK-constrained VARCHAR), the canonical single-table `create`/`update`
> still binds a plain `:status`: the executor resolves the enum type and binds through a `PGobject`
> (`DynamicMethodExecutor.bindAs`, fallback `lookupTargetTableColumnTypes`), so Postgres applies the input
> function. Add `:status::<enum_type>` **only** for a non-canonical write the executor can't parse a single target
> table from. Detail: [11-...](11-business-logic-dynamic-crud.md) §Gotchas /
> [10-...](10-database-management.md) §enumTypes. (ERP-style tables use CHECK-VARCHAR, not pg_enum, so this rarely
> arises here — see the `status` row in the table above.)

> ⚠️ **`update` must `COALESCE(:v, col)` NOT NULL columns the form doesn't submit** (company/status/number/
> audit) — a plain `SET col=:v` sets them NULL on edit and throws. Forms submit only their own fields.

**Join-alias convention.** The base table is aliased `t`. In `findAll`/`get`,
**business-FK** joins are aliased **`jN`** (numbered: `j1`, `j2`, …) and **enum-lookup** joins are aliased
**`elN`** (`el3`, `el5`, …), each numbered in join order. So a business FK selects `jN.id AS x__id, jN.code AS
x__code, jN.name AS x__name` → row `{x:{id,code,name}}`; an enum-lookup selects `elN.code AS x` → flat row
`x:"CODE"`. Example (`salesOrder.get`): `LEFT JOIN company j1`, `LEFT JOIN customer j2`, `LEFT JOIN
lookup_sales_order_type el3` (→ `el3.code AS order_type`), `LEFT JOIN plant j4`. Inside a line subquery the line
FKs get their own `jlN` aliases.

> **This `__`-nested convention is the HAND-AUTHORED one — distinct from the browser's Join feature.** The
> double-underscore `jN.<col> AS x__id` alias is what makes the executor emit a nested `{x:{…}}` object
> (`DynamicMethodExecutor.mapRow`, splits on `__`). The in-browser "Join" button on a DTO field
> (`CrudJoinServiceImpl`) instead emits **single-`_` flat** aliases → a flat `<ref><Col>` label field (e.g.
> `zoneName`), and leaves `create`/`update`/`count` untouched. Full comparison + recipe:
> [11-business-logic-dynamic-crud.md § FK-join on a DTO field](11-business-logic-dynamic-crud.md#fk-join-on-a-dto-field-the-field-dialog-join-feature).
> Pick `__` here only because a form sub-object / ObjectSelector needs the nested shape.

---

## 2. Enum dropdowns need an option snapshot — the silent killer

An enum form control (`dynaform.form.rimm.drop.down.field.plugin`, `key=name`,
`dataClass=com.devsegment.<app>.dto.enums.<E>`, **no `ruleIdentifier`**) gets its options at render from the
project **DynamicEnum registry**. **Import never materializes that registry, and `Class.forName(<app enum FQN>)`
fails in a REPORT project (no app jar on the classpath).** So the dropdown renders **empty → the field cannot be
selected or saved** — even though your CRUD stores/reads the code correctly. This breaks create/edit on nearly
every entity and is *invisible* until you actually open a form.

**Fix:** inject the platform's fallback — a persisted `enumValues` snapshot — into each such control's settings:

```json
"enumValues": { "RAW": {"name":"RAW","displayName":"Raw Material"}, "FINISHED": {"name":"FINISHED","displayName":"Finished Good"}, … }
```

Source the map from the `lookup_<enum>` table's `rows` (`code` = the constant = `name`; `name` = `displayName`)
or from the app's enum source when there is no lookup table. `validate` flags every enum dropdown that has
neither `enumValues` nor a choices `ruleIdentifier`.

> ⚠️ **The OTHER option source — a CRUD-backed choices `ruleIdentifier` — has its own hard contract: the rule
> MUST END by converting rows to option pairs.** dropdown → `return
> service.global.conversion.toSelectOptions(list,"<key>","<display>")`; autocomplete →
> `toAutoCompleteOptions(list,"<display>")`. For a **LOCALIZED CRUD** (has a `localizationField`) use
> `toSelectOptionsLocalized` so labels follow the session locale — plain `toSelectOptions` always shows the
> base-locale column. **NEVER** `return service.crud.<a>.findAll([...]) ?: []`: a raw entity list renders
> **"No results found" AND hides the Show Nav affordance** (`validate` now ERRORs on it). For a **SEARCHABLE**
> dropdown build the `acFindAllBy<Cap(X)>Like` pipeline (typed `:X` param, defaultValue `''`, LIMIT 100) +
> `acFindBy<Cap(X)>Like` wrapper + `RIMM_FILT_<alias>_<X>` rule; never hand-call `findAll` with a **PARTIAL**
> param map (the unbound column surfaces as untyped `$1 IS NULL` → Postgres "could not determine data type of
> parameter $1"; `findAll([:])` with ALL keys absent is the safe no-filter call). Full recipe + naming table:
> [02-form-controls-reference.md](02-form-controls-reference.md) **§4a**.

---

## 3. Documents with line items (header + N lines)

For a `crud.table`/form over a header table whose form has a `dynaform.form.list.field.plugin` sub-grid:

- **findAll / get** must return the lines as a nested JSON array **with the sub-grid's display fields**, not just
  `{id}`. The sub-grid columns read `product.code` / `uom.name` / `lot.lotNumber`; if the line JSON carries only
  `id`, every such cell renders the **raw UUID**. Build it by LEFT-JOINing each line FK inside the subquery:
  `json_agg(json_build_object('id', l.id, 'quantity', l.quantity, 'product', json_build_object('id', l.product_id, 'code', jp.code, 'name', jp.name), …) ORDER BY l.line_number)`.
- **create / update** are GROOVY methods orchestrating SQL helpers: `create` = `createHeader` then per-line
  `insertLine`; `update` = `updateHeader` + `deleteLines` + re-`insertLine`.
- **delete MUST cascade to the lines.** The line→header FK is typically `NO ACTION` (check it in the dump), so a
  bare `DELETE FROM <header>` **FK-fails on any document that has lines** (the normal case) — whatever wrote the
  rows before did the cascade itself. Make `delete` a GROOVY method: `deleteLines(param)` then `_deleteHeader(param)` — mirroring
  `update`. (`validate` flags a document CRUD whose `delete` doesn't clear lines first.)

**The five SQL helper methods** (each a plain SQL method + its own paired query `crud_<alias>_<method>`, **no
`dtoFields`** — they are internal, not user-facing): `createHeader` (INSERT header, `RETURNING *`),
`updateHeader` (UPDATE header `WHERE id = :id`), `insertLine` (INSERT one line), `deleteLines` (`DELETE FROM
<line> WHERE <header>_id = :id`), `_deleteHeader` (`DELETE FROM <header> WHERE id = :id RETURNING *`). The
**nested `lines` array is NOT a `dtoField`** either — it is surfaced only inside the `findAll`/`get` SQL
(`json_agg(...) AS lines`); `dtoFields` list only the header's own columns.

**The three GROOVY orchestrators** (worked example: a `salesOrder` header + lines; the same three shapes fit an
invoice + invoice lines, a declaration + consignment items, or a purchase order + receipt lines):

```groovy
// create
def h = service.crud.salesOrder.createHeader(param)
def lines = param.lines ?: []
lines.eachWithIndex { ln, i ->
    if (ln.lineNumber == null) ln.lineNumber = i + 1
    ln.salesOrder = [id: h.id]
    service.crud.salesOrder.insertLine(ln)
}
return service.crud.salesOrder.get(h.id)
```
```groovy
// update
service.crud.salesOrder.updateHeader(param)
service.crud.salesOrder.deleteLines(param.id)
def lines = param.lines ?: []
lines.eachWithIndex { ln, i ->
    if (ln.lineNumber == null) ln.lineNumber = i + 1
    ln.salesOrder = [id: param.id]
    service.crud.salesOrder.insertLine(ln)
}
return service.crud.salesOrder.get(param.id)
```
```groovy
// delete
service.crud.salesOrder.deleteLines(param)
return service.crud.salesOrder._deleteHeader(param)
```

Note the two `deleteLines` call shapes: `update` passes `param.id` (a bare id) and `delete` passes `param` (the
whole map) — both bind the header id to `:id` in `DELETE … WHERE <header>_id = :id`. Each new line gets
`ln.salesOrder = [id: h.id]` so `insertLine`'s `:sales_order__id` walks the nested `{salesOrder:{id}}`. The
`createHeader` INSERT is a flat column list with `gen_random_uuid()` / `now()` for the PK+audit (that PK form
only because these tables use a bare uuid PK — against a sequence-backed PK you omit the column instead, §1),
`COALESCE`
defaults for NOT-NULL business columns (`COALESCE(NULLIF(:status,''), 'DRAFT')`, the auto-number
`COALESCE(NULLIF(:order_number,''), 'SO-' || …)`), the single-company `COALESCE(:company__id, (SELECT id FROM
company ORDER BY creation_time LIMIT 1))`, and the enum-lookup write `(SELECT id FROM lookup_sales_order_type
WHERE code = :order_type)` — i.e. exactly the §1 per-column rules. `updateHeader` `COALESCE(:v, col)`-guards
every NOT-NULL column the form may omit. `salesOrder` additionally carries SQL lifecycle methods
(`confirm`/`release`/`startPicking`/`complete`/`cancel`); `billOfMaterials` uses the same helper set plus
`activate`/`deactivate`/`createNewVersion`.

Tree CRUDs (`crud.tree.plugin`) fetch roots+children via `findByParent(filter{parentId})` — add
`findByParent` (GROOVY) + `findAllByParent`/`countByParent` (SQL, `parent_id IS NOT DISTINCT FROM :parentId::uuid`;
the `::uuid` cast lets a NULL `parentId` return roots without a type-inference error).

---

## 4. Match the static behavior exactly

- **Soft vs hard delete — decide it from the schema you can see.** A table with an `active`/`is_active` boolean
  **and** inbound FKs is soft-delete: `UPDATE … SET active=false` (which also avoids the FK-on-delete failure).
  A table with neither is hard-delete — and for documents, guard it to the draft status. A row action already
  named *Deactivate*/*Archive* in the UI you were handed is the same signal. Whatever you choose must match what
  already reads the table, or half the app stops seeing rows the other half still writes. *(If you were also
  handed the predecessor service's source, its own delete method is the fastest confirmation — but you do not
  need it.)*
- **Lifecycle methods** (`activate`/`cancel`/`post`/`ship`/`updateStatus`/…) = SQL status UPDATEs. The literal
  MUST be in the column's CHECK set (verify with `db show`). Deep multi-table side effects (stock postings,
  reservations, costing) may be simplified to the primary status/qty effect — **document which**.
- **Aliases** are whatever the context/rules/UI already reference (e.g. `product`, not `product_cruid`). Any
  suffix convention you may meet on an existing project (`<entity>_cruid` and friends) is **that project's habit,
  not a platform rule** — **bare camelCase** (`salesOrder`, `product`, `billOfMaterials`) is just as valid. The
  alias must match existing consumers **exactly**; for greenfield entities pick ONE convention and apply it to the
  alias AND every consumer.

---

## 5. Enumerate EVERY consumer, then verify against real rows

Before declaring coverage, list all consumers of each alias and confirm findAll surfaces each expression:
`crud.table`/`crud.tree` `columnSettings`, form-control `fieldExpression` (scope CRUD), **`dynaform.form.list.field`
sub-grid `columnSettings`** (the easy-to-miss one), choices rules (a dropdown/autocomplete choices rule must END
with `service.global.conversion.toSelectOptions(list,"<key>","<display>")` / `toAutoCompleteOptions(list,"<display>")`;
localized CRUD → `toSelectOptionsLocalized`; searchable → the `acFindAllBy<Cap(X)>Like` pipeline; never a raw
`findAll([...])` and never a partial filter map — see §2 and **02 §4a**), and lifecycle action rules
(`service.crud.<alias>.<method>`). `validate` cross-checks all of these.

Then **execute against a populated DB** — empty transactional tables hide CHECK / NOT NULL / FK / UPDATE-no-op
failures:

```
mrjun.py validate --project ./app          # static: CHECK-literals, coverage, delete-cascade, enum options
mrjun.py crud verify --db "host=… dbname=… user=… password=…" --project ./app   # runtime: seeds a fixture row so constraints fire
```

## 6. The bugs this doc exists to prevent (all found only against real data)

1. A lifecycle method writing a status the CHECK forbids (empty table hid it). → §0, §4; `validate` (ERROR).
2. Line-grid FK refs surfaced as `{id}` only → raw UUIDs in the sub-grid. → §3; `validate` (WARN).
3. Document `delete` not cascading to lines → FK violation on any doc with lines. → §3; `validate` (WARN).
4. Enum dropdowns with no option source → blank, unselectable fields after import. → §2; `validate` (WARN).

Every one passed a naïve empty-table smoke test. Parse the whole schema, enumerate every consumer, and verify
against seeded rows.
