# 01 — Solution shapes: the four builds a brief turns into

**What this is.** Four delivered projects, abstracted into one taxonomy. Not four stories — four *shapes*, each
with a size driver, an artefact budget with real numbers, an orchestration backbone, a place the effort actually
lands, and a set of failure modes the shape invites. Read it before Phase 1 of
[[19-build-decision-procedure.md](../19-build-decision-procedure.md)](../19-build-decision-procedure.md): 19 tells you what to decide in what
order, this tells you **how big the answer is going to be and which of four things you are building**.

The four sources are referred to only as **A**, **B**, **C**, **D**. Every entity, column and rule name below is
renamed to a neutral one (`document`, `documentLine`, `case`, `task`, `item`, `unit`, `partner`, `plan`,
`warning`, `hold`, `orgUnit`). The SHAPE of every snippet is byte-exact from the delivery; only the nouns moved.

| | **A** | **B** | **C** | **D** |
|---|---:|---:|---:|---:|
| Pages | 433 | 129 | 128 | 67 |
| Dynamic CRUDs | 163 | 38 | 31 | 12 |
| Business tables | 159 | 43 | 31 | 16 |
| CRUD methods | — | 480 | 300 | 164 |
| Rules | 619 | 416 | 271 | 99 |
| Queries | — | 439 | 362 | 170 |
| Charts | 9 (+46 legacy) | 31 | **87** | 12 |
| Studio (`nct.html.plugin`) consoles | **22** | 14 (hidden) | 0 | 0 |
| BPMN workflows / deployed | 7 / **0** | 5 / 5 | 8 / **0** | 1 / 1 |
| Schedulers / enabled on export | 27 / **27** | 2 / **0** | 10 / **0** | 4 / **4** |
| Form groups | 109 | 28 | 37 | 16 |
| Nav leaves | **171** | 55 | 45 | 13 |
| Locales | 2 | 3 | 3 | 3 |
| `validate` on the shipped export | 11 err / ~1100 warn | — | 0 err / 91 warn | 29 err / 46 warn |

---

## 1 · The size metric — and the three that lie

**Decide the size from NAV LEAVES, not from pages, tables or CRUDs.** A page count predicts nothing: the ratio of
pages to CRUDs *rises* as the project shrinks (A 2.7, B 3.4, C 4.1, D 5.6), because every project pays the same
fixed console floor and the same two-pages-per-form-group tax.

The arithmetic held in all four, within two pages:

```
total pages  =  nav leaves  +  2 × form groups  +  22…28 baseline console pages
```

Check it: D `13 + 2×16 + 22 = 67` (exact). B `32 list + 28 landing + 32 form + 5 worklist + 4 dashboard + 28
console = 129` (exact). C `~29 business + 37 landings + 38 form pages + ~24 console = 128`. A `22 studio + 129
table + 141 form + 109 landing + 24 console + 8 misc = 433`.

Three consequences you can quote in a scoping conversation:

- ✅ **Form groups are half the page count.** Every group costs a landing page *and* a form page, neither of
  which belongs in the nav. C hangs 75 of its 128 pages off their console as children
  (`placeFormsNextToLanding: true`); D hangs 32 of 67. That is correct and invisible. A shipped 109 landings and
  141 form pages, and 38 of the groups point `contentPageIdentifier` at the shared **system** Landing page — an
  end-user Create/Edit on those is access-denied.
- ⛔ **The baseline console floor is 22–28 pages you did not author and must not delete.** D deleted one
  (`/sources`) and `validate` errors on it. Append to the console; never prune it.
- ⛔ **171 nav leaves is not a big project, it is a broken one.** A has one nav leaf per CRUD because it derived
  the nav from the table list. 38 of them are code lists (`Task Types`, `Pay Types`, `Unit Types`, …). B put 9
  registers on 4 nav pages and lost nothing.

**The honest size driver differs per shape, and it is never "how many tables".** §2–§5 name it.

---

## 2 · Shape S — the pilot: one decision chain, ≤ 15 aggregates *(source D)*

### What drives the size

**One algorithm and the chain of hand-offs it triggers.** Not entities. D has 16 tables because the algorithm
needs 16, and 12 of the 13 business screens exist to feed or consume one nightly computation. The brief that
produces this shape has *all* of:

- a **scheduled detector over a computed threshold** ("when the value crosses X, tell somebody");
- a **human decision with a deadline and exactly one escalation** ("24 hours, then the supervisor");
- a **chain where each step is a different party** (requester → approver → counterparty → transit → receiver →
  finance);
- **parameters that change over time and must be reconstructible** ("what setting were we on in March?");
- **a band/threshold table the customer will want to tune** without a rebuild;
- **≤ 15 aggregates.**

Any one of those missing and you are probably in Shape R. All six present and you must resist growing it.

### The budget

```
16 tables → 12 CRUDs (164 methods) → 13 business pages → 16 forms / 16 form groups
→ 99 rules (71 EXECUTION · 27 PREDICATE · 1 VALIDATION) → 170 queries (14 hand-written)
→ 1 BPMN (18 elements) · 1 process group · 1 worklist → 4 schedulers → 12 charts (10 + 2)
→ 5 mail · 3 PDF templates → 8 role groups → ~19 000 seed rows
```

Ratios that transfer: **~14 CRUD methods per CRUD**, **~8 rules per CRUD**, **~1 business page per aggregate**,
**one dashboard**, **one worklist**.

### The orchestration backbone

**Cron sweep → conditional-UPDATE claim → `service.workflow.start` → write-back.** One BPMN, and it is real:
deployed, with lanes encoded as task-name prefixes (`[SYSTEM]`, `[APPROVER]`, `[COUNTERPARTY]`), every gateway
carrying a `default` flow so only the exceptional branch needs a condition, and the rejection loop returning to
the *approval* task rather than to the start.

The case opens by itself. The worklist has **no** `userStartProcessActions` at all. Three columns and seven CRUD
methods do the work:

```sql
process_identifier   VARCHAR(64),
process_started_at   timestamp,
process_start_count  integer DEFAULT 0
```

```sql
-- claimForCase: THE CLAIM. One conditional UPDATE … RETURNING *, so of two overlapping ticks
-- exactly one wins. A Map when we won it, Groovy null when somebody else did.
UPDATE warning
   SET process_started_at = now(), process_start_count = COALESCE(process_start_count,0) + 1,
       modification_time = now()
 WHERE id = CAST(:id AS uuid) AND deleted = false
   AND status = 'NEW' AND process_started_at IS NULL
RETURNING *

-- releaseCaseClaim: hand back an orphan (claimed, but the start never finished). BOTH guards
-- repeated in the WHERE, so two overlapping repair ticks cannot both release the same row.
UPDATE warning SET process_started_at = NULL, modification_time = now()
 WHERE id = CAST(:id AS uuid)
   AND process_identifier IS NULL AND process_started_at < now() - INTERVAL '5 minutes'
RETURNING *

-- countCaseCandidates: the scheduler GATE's cheap question. The same predicate, widened by the
-- orphan clause, is findCaseCandidates / findClaimedWithoutCase.
SELECT COUNT(*) AS total FROM warning t
 WHERE t.deleted = false AND t.status = 'NEW'
   AND (t.process_started_at IS NULL
        OR (t.process_identifier IS NULL AND t.process_started_at < now() - INTERVAL '5 minutes'))
```

✅ **Five steps, always in this order: gather → claim → shape → start → mark**, and **repair first**, so a claim
left behind by a crashed tick is handed back in time for *this same pass*. The chain claim→start→mark is not
transactional; claim first, because a crash then leaves a row *claimed with no case* — detectable, repairable,
once. The other order leaves a case whose row was never marked, the next tick opens it again, and no screen can
tell the duplicates apart.

⛔ **The scheduler gate predicate must `return` explicitly.** A predicate that falls off the end returns null,
which is reported as *"Predicate rule must return Boolean, but returned: null"* and which the scheduler treats
as a **closed gate for ever**, with nothing in the UI to show for it.

```groovy
// PREDICATE — the scheduler's GATE. It may only ANSWER: service.workflow.start is refused inside a
// predicate at runtime, and the expensive work belongs in the action anyway.
def counted = service.crud.warning.countCaseCandidates()
long n = ((counted instanceof Map ? counted.total : counted) ?: 0) as long
return n > 0
```

### The distinctive move: write the state machine three times, in agreement

This is why a small project stays coherent when nobody has time to re-read it. D states every lifecycle in three
independent places and they say the same thing:

1. **In the DDL, as a CHECK constraint** — `CHECK (status = ANY (ARRAY['DRAFT','SENT','CONFIRMED','SHIPPED',
   'RECEIVED','REJECTED','CANCELLED']))`. A rule that writes an unknown status fails loudly instead of corrupting
   the register.
2. **On the row action, as a predicate named exactly after the state** — `Document Is Confirmed`,
   `Document Is Shipped`, `Version Is Draft`. One line each: `return context.<ctx>.document.data.get()?.status == 'CONFIRMED'`.
3. **Inside the transition rule, as a server-side re-check** — because a hidden button is not a guarantee:

```groovy
def doc = service.crud.document.get(docId)
if (doc.status != 'SHIPPED') {
    throw new RuntimeException("Only a SHIPPED document can be cleared (this one is " + doc.status + ")")
}
```

Shape R adds a **fourth** copy — the guarded UPDATE (§3) — and the fourth is free. Three is the minimum. The
whole state machine then reads off the table's `editActions` array as a Button / Predicate / Rule triple per
transition (`Confirm` ← `Document Is Sent` → `Confirm Document`), plus one extra guard that matters when the same
row is workable from two surfaces:

```groovy
if (row.processIdentifier != null || row.processStartedAt != null) { return false }
// ^ a case owns this record: decide it in the worklist, not from the table
```

### The other distinctive move: the brief's `if/else if` ladder becomes a table

Any brief sentence of the form *"if X ≤ a then A, else if X ≤ b then B…"* becomes a four-row register with an
`active` flag and a `sort_order`, one SQL method, one page a business user can edit, and the clause text in each
row's `description` so nobody has to reopen the brief. `NULL` in the ceiling column means "open-ended top band":

```sql
SELECT t.* FROM band_option t
 WHERE t.deleted = false AND t.active = true
   AND (t.max_input IS NULL OR CAST(:q AS numeric) <= t.max_input)
 ORDER BY t.capacity ASC
 LIMIT 1
```

### Where the effort actually goes

**Into the correctness of one algorithm, and into writing down every trap at the place it fires.** D's rule
comments *are* the design document: they cite the requirement clause, and where the build deviates from the
specification they say why. Two of them record corrections that a literal implementation would have shipped as
bugs — the specification's own formula did not sum to the target, and clamping negatives broke the sum that was
the whole point. Both were found by running the algorithm against a real-sized catalogue, not the three-item
example in the brief.

⛔ **The Groovy numeric-literal trap that only fires on real data.** `0G` is a `BigInteger` literal and `0.0G` a
`BigDecimal` one. `if (q < 0G) { q = 0G }` silently retypes `q`, and the next `q.setScale(3, …)` throws
`MissingMethodException: java.math.BigInteger.setScale()`. It only fires when a line allocates negative — which
the brief's own worked example never reaches. Write every numeric literal `0.0G`, and put a `NUM(v)` coercion
closure at the top of the rule.

### Failure modes this shape invites

| Failure | What it looked like |
|---|---|
| ⛔ **A form of `scope: GLOBAL` controls opened from a crud-table row action** | 12 side-forms. Opened from a table row action the runtime binds every control to that table's crud alias, so `context.data.getAttr('reasonDays')` is null, the CRUD method receives `''`, `COALESCE` keeps the old value — **and the action reports success while the record does not change.** The same form works from a workflow task, which is exactly why it survives testing. Fix: declare the controls `scope:"CRUD"` with the table's context + alias, or read attrs first and fall back to `context.<ctx>.<alias>.data.get()`. |
| ⛔ **The dead manual path** | A start form, its landing, its page and a seed rule exist and are referenced by nothing, because the decision to open cases only automatically was taken *after* they were built. Deleting the mechanism means deleting its pages too. |
| ⛔ **All schedulers `enabled: true`** | 4 of 4. An import into a demo tenant starts writing rows and sending mail immediately. |
| ⛔ **Nav localization on the wrong slot** | The trilingual labels went on `linkModel.localizedMap`; the sidebar reads the ITEM's own `localizedMap.name`. 13 `validate` errors, one per business link, and a monolingual sidebar in a three-locale project. Everything else about that nav is a model. |
| ⛔ **The case card cannot show a table** | Child lines reach the worklist as newline-joined strings in a read-only textarea, because a workflow user-task form binds no CRUD row — every field is `scope: GLOBAL`, `alwaysProhibited: true`, over a published attribute. Legible; not sortable, not localizable, not clickable. Any brief whose workflow forms need a real child grid needs a different answer than this shape offers. |
| ⛔ **Published attributes are copies and they drift** | A worklist column shows what the bind rule read at the *start* of the case unless every later step re-publishes: `context.data.setAttr('caseStatus', 'POSTPONED')`. |

---

## 3 · Shape R — the register-and-document system *(source B)*

### What drives the size

**The number of distinct state-changing DOCUMENTS, and the number of distinct events that move a balance.** B
models **six** balance-affecting events instead of one vague "movement" — expectation, receipt, transfer,
consumption, return, write-off, plus a finished-output receipt — and each one is a document with a header, lines,
a lifecycle and a posting engine. Twelve documents plus three flat ones is what makes it 43 tables, not the
reference data.

Recognise the brief by: a countable resource tracked as **individually identified units** rather than as a
pooled quantity per catalogue code;
cost attribution and physical quantity kept as **two separate ledgers**; the same catalogue code produced
repeatedly for different counterparties so the **cost object is the document line, not the product**; a small
role set with exactly one approver who is the only role that sees money.

### The budget

```
43 tables → 38 CRUDs (480 methods, but only ~30 distinct method NAMES) → 32 list pages
→ 28 form-group landings + 32 form pages → 416 rules → 439 queries
→ 5 BPMN (all deployed) · 5 worklists → 2 schedulers → 31 charts on 4 dashboards
→ 21 mail · 11 PDF templates → 9 read-only report CRUDs → 6 role groups
```

Ratios: **~12.6 CRUD methods per CRUD**, **~11 rules per CRUD** (the highest of the four), **~1.4 nav leaves per
CRUD** after compression, **3 methods exactly** for a report CRUD.

### The orchestration backbone

**A four-layer rule stack per document, and a guarded status transition at the bottom of it.** BPMN exists (5,
all deployed, one of them a genuine rework loop) but it delegates: every service task is
`flowable:delegateExpression="${ruleTask}"` with a comma-separated rule list in `flowable:rule`, and every
gateway condition is `${predicateSequence.execute(execution,'<predicate-id>')}`. The business question is always
a PREDICATE rule, never an expression in the diagram.

The four layers, per document:

```
1  GATE (PREDICATE)      one line: whether the button renders
                         return context.<ctx>.document.data.get()?.status == 'DRAFT'
2  PERSIST (EXECUTION)   two lines: the form-submit handler
3  LIFECYCLE (EXECUTION)  a thin "<Entity> Action <Verb>" wrapper that re-checks the guard
                         server-side and delegates to the engine BY NAME
4  ENGINE (EXECUTION, ⭐) the fat posting rule — the twelve-step skeleton below
```

✅ **The twelve-step posting engine. Copy the order; the order is the safety.**

```
 1  helper closures            NUM / ID / ROWS / SETTING / TOL / CALL
 2  actor                      def me = service.security.user(); def actor = me?.email ?: ''
 3  resolve subject            context.<ctx>.<crud>.data.get()?.id
                               ?: context.data.getAttr("subjectId")     ← so the SAME rule works
                               ?: context.data.getAttr("recordId")         from a row action, a
                               ?: param                                    service task, a scheduler
 4  load + null guard          service.crud.<crud>.get(id)
 5  status guard               if (doc.status != 'SUBMITTED') throw …
 6  role guard                 if (!service.security.hasAnyRoleGroup("Approver")) throw …
 7  period guard               SETTING('period.locked.until') vs doc.docDate
 8  business preconditions     the document-specific refusals
 9  derive                     stampLines → stampConversion → computeDerived → recomputeTotals
10  re-read + sanity           def fresh = …get(id); if (NUM(fresh.derivedQty) <= 0) throw …
11  write the ledger           service.crud.movement.create([...]) per line
12  flip status LAST           service.crud.<crud>.post([id: fresh.id, actor: actor])
13  audit                      context.data.setAttr('audit*', …); CALL("Write Audit Entry")
```

Step 12 is the discipline that makes it safe, and the SQL enforces it — **this is the fourth copy of the state
machine, and it costs one clause:**

```sql
-- <doc>.post — a guarded state transition, not a blind UPDATE
UPDATE document SET status = 'POSTED', posted_at = now(),
       posted_by = COALESCE(NULLIF(:actor,''), posted_by), modification_time = now()
 WHERE id = CAST(:id AS uuid) AND status = 'SUBMITTED' RETURNING *
```

`AND status = 'SUBMITTED'` makes a double-post a no-op instead of a corruption.

### The distinctive move: a running per-line ledger instead of a close-time recompute

The control equation the brief demanded — *transferred = consumed + returned + written-off + still open* — is
carried on the line and decremented **at post time with a delta**, by three callers each passing one non-empty
value:

```sql
-- document.settleLine  (params: id, d_used, d_returned, d_written)
UPDATE documentLine SET
  qty_used     = qty_used     + COALESCE(CAST(NULLIF(:d_used,'')     AS numeric), 0),
  qty_returned = qty_returned + COALESCE(CAST(NULLIF(:d_returned,'') AS numeric), 0),
  qty_written  = qty_written  + COALESCE(CAST(NULLIF(:d_written,'')  AS numeric), 0),
  qty_open     = qty - (qty_used + COALESCE(CAST(NULLIF(:d_used,''), 0)))
                     - (qty_returned + …) - (qty_written + …)
 WHERE id = CAST(:id AS uuid) RETURNING *
```

A header roll-up (`refreshSettlement`) then computes `OPEN | PARTIALLY_SETTLED | CLOSED` within a tolerance read
from a settings row, and a `flagVariances` method applies the tolerance **per line and per unit of measure**, with
the SQL literal as the safety net and the settings row as the truth:

```sql
tolerance_exceeded = (l.qty_open > CASE l.uom
    WHEN 'KG' THEN COALESCE(CAST(NULLIF(:tol_kg,'') AS numeric), 0.150)
    WHEN 'M'  THEN COALESCE(CAST(NULLIF(:tol_m,'')  AS numeric), 0.500)
    ELSE 0 END)
```

### The distinctive move: derivation in SQL, orchestration in Groovy

The single most valuable structural rule in this shape. Every derived column is produced by **one named SQL
method** — a single `UPDATE … FROM (subselect) … RETURNING *` — and the Groovy rule only sequences them, re-reads
and validates. B compiles a page of specification arithmetic into one statement that derives fourteen columns
from six typed inputs. **Typed columns and derived columns live in the same table, and the derived ones are never
writable from the form.**

A derived value with more than one source gets its own statement and a **COALESCE fallback chain**, which is the
readable way to say *measured on the real unit, else computed from the item card, else keep what is there*:

```sql
UPDATE document c SET
  ratio = COALESCE(
     (SELECT MAX(u.ratio) FROM documentUnit du JOIN unit u ON du.unit_id = u.id
       WHERE du.document_id = c.id AND u.ratio > 0),
     (SELECT ROUND(c.width * i.density / 1000, 4) FROM item i
       WHERE i.id = c.item_id AND i.density > 0),
     c.ratio)
 WHERE id = CAST(:id AS uuid) RETURNING *
```

### The method vocabulary — the most portable artefact in the shape

480 methods, ~30 distinct names, five tiers applied without exception:

```
tier 0  base 8      find* findAll count get create update delete undelete          (all 38)
tier 1  register    activate deactivate                                             (8)
tier 2  document    createHeader updateHeader insertLine deleteLines _deleteHeader
                    findLines  [+ insertExtraLine deleteExtraLines findExtraLines]  (12)
tier 3  lifecycle   submit reject post markReversed close approve cancel
                    start complete reopen fulfil                                    (as needed)
tier 4  derivation  recomputeTotals computeLineAmounts stampLines stampConversion
                    refreshSettlement refreshSystemQty flagVariances
tier 5  domain      the handful that only this brief needs
```

✅ `_deleteHeader` is **underscore-prefixed to mark it an internal primitive the UI must never call**. `find*`
returns a page, `findAll` returns rows, `find<Children>` returns a child collection. `find` is the one GROOVY
method in an otherwise-SQL CRUD and is byte-identical in all 38: read `param ?: [:]`, call `count()` and
`findAll(filter)`, and return `[content, totalElements, totalPages, pageNumber]` with
`totalPages = rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1`.

### Report-as-CRUD — the cheapest report in the platform

Nine reports, none of them a hand-built table. Each is a **dynamic CRUD with no backing table and exactly three
methods** (`find`, `findAll`, `count`) whose `findAll` is a plain `SELECT`, often a `UNION ALL` across two
tracking modes with a discriminator column. It inherits `crud.table.plugin`, the filter bar, column localisation,
paging and CSV export for free. Cost: one SQL string, one `dtoFields` list, one page.

⛔ **An `id` column is mandatory** — the table plugin keys rows on it — so select `r.id` / `l.id` even when
nothing links out.

### Policy as data

Two ordinary CRUDs carry everything the brief called configurable, and both have ordinary list pages so an
administrator tunes policy without a developer:

- `appSetting` — 32 rows, `category / setting_key / setting_value / value_type`, each row's `description` citing
  the requirement it answers. Tolerances, the locked-period date, four-eyes on/off, which role sees money, label
  dimensions, notification recipient lists, document prefixes.
- `refLabel` — **one table holding every enum in the system**: 30 vocabularies, 144 codes, 144/144 with a
  populated `localized` jsonb, plus `sort_order` and `color`. One rule shape serves every dropdown:

```groovy
def list = service.crud.refLabel.find([vocabulary: 'doc_status', rowsInPage: 200, pageNumber: 0])
return service.global.conversion.toSelectOptionsLocalized(list, "code", "label")
```

⛔ **There is no Groovy API that resolves a role group to e-mail addresses.** A settings row is the only fan-out
there is; that is why the NOTIFY category exists.

### Where the effort actually goes

**Into SQL derivation and into the four-layer stack, repeated 12 times.** 439 queries and 480 CRUD methods
against 271 KB-scale Groovy: the arithmetic is in the database and the rules are thin. Second-biggest cost:
**localisation of a three-locale, non-Latin-default tenant** — trilingual group and leaf nav maps, 78 trilingual
inline help nodes that explain the *interaction model* rather than the field, a mail template triplicated per
locale with a dynamic alias dispatch, and a 40-entry transliteration table in every PDF rule because the renderer
font cannot set the default script.

### Failure modes this shape invites

| Failure | What it looked like |
|---|---|
| ⛔ **`update` replaces all lines** | `deleteLines(id)` then re-insert from the payload. Line ids change on every save, so any `movement.doc_line_id` written before an edit points at a deleted row, and concurrent edits silently last-write-wins. A diff-based upsert keyed on `line_number` costs little. |
| ⛔ **Rules called by display name** | `service.rule("Post The Document")` — renaming a rule in the studio breaks every caller, with no static check and no error until the button is clicked. The `CALL` wrapper improves the message, it cannot prevent the break. |
| ⛔ **Status labels monolingual in tables while the vocabulary table has translations** | 112 of 112 `crud.table.plugin` status columns inline their own `enumValues` map with a single-language `displayName`; there is no `localizedNames` slot on an enum value. So an English-locale user sees English headers over default-locale status values while the *form* dropdowns render correctly. The vocabulary table is the right answer; the tables just do not read it. |
| ⛔ **Charts are monolingual by construction** | A chart node has no per-locale slot; a unit suffix baked into the JS renders in the default language under every locale. Needs a locale-aware `replacements` binding or per-locale chart nodes. |
| ⛔ **Dead configuration** | 12 `doc.prefix.*` settings rows exist and **nothing reads them** — all 17 prefixes are hardcoded in `createHeader` SQL, and 5 of the 17 have no settings row at all. An administrator editing one sees nothing change. |
| ⛔ **Both schedulers disabled** | The two proactive controls the brief asked for are built, wired to mail templates, and inert. The system is entirely pull-based in practice, and nothing in the export says so. |
| ⛔ **Document numbers random, not sequential, and not unique-constrained** | `upper(substr(replace(gen_random_uuid()::text,'-',''),1,6))` with `uniqueConstraints: 0` in the schema. No gapless sequence, no DB guarantee against a collision or a hand-typed duplicate. |
| ⛔ **Silent-ish truncation on a signed printout** | A PDF caps at 7 lines and appends *"+ 23 more line(s)"*. Honest, but a signed document that does not list everything it attests to is a weak artefact. |

---

## 4 · Shape C — the analytics-dense case system *(source C)*

### What drives the size

**The number of numbered REPORTS the brief owes an external reader, times ~11 charts each — and the number of
CLOCKS.** C has 31 entities and **87 charts**. The entity model is smaller than B's; the delivery is the same
size, because reporting is a first-class product here and not a by-product.

Recognise the brief by: **one case identity across channels**; several **statutory clocks running at once**;
**second-person approval** on the two decisions that matter; **business-owned configuration that must change
without a release**; and an external reader who will ask *"show me which of your controls acted, and when"*. If a
brief has clocks, evidence and a supervisor, it is this shape.

The system is also deliberately **narrow**: it never writes to a system of record. *"Nothing recorded alters
balances, postings or terms; execution remains with the existing systems and teams."* Say that sentence out loud
in the plan — it is what stops this shape growing into Shape X.

### The budget

```
31 tables → 31 CRUDs (8 standard + 52 custom methods) → 128 pages / 3 587 content nodes
→ 33 CRUD tables on pages (7 in one console, 7 in another, 4, 3, 3, 2, 7 standalone)
→ 41 filter forms → 108 row actions (44 direct:true) → 38 forms / 37 form groups
→ 271 rules (210 EXECUTION · 58 PREDICATE · 3 VALIDATION, ~596 KB)
→ 362 queries (321 chart · 32 KPI · 9 lookup) → 87 charts on 8 dashboards
→ 8 BPMN · 8 process groups · 8 worklists → 10 schedulers
→ 40 mail · 10 PDF templates → 12 role groups → 45 nav entries
```

Ratios: **~11 charts and 4 KPI tiles per dashboard**, **one dashboard per numbered report**, **~3.5 row actions
per table**, **~9 rules per CRUD**, **~1.7 custom CRUD methods per CRUD**.

### The orchestration backbone

**Eight workflows, eight process groups, eight worklists, eight `set<X>Process` methods, one claim column per
subject table. The symmetry is the design.** Five processes are opened by a person's action, three by a
scheduler; both use the same `service.workflow.start` call and the same claim guard. Every BPMN has an identical
skeleton:

```
StartEvent
  → serviceTask "Refresh the subject"  (delegateExpression ${ruleTask}, rule = a "Bind <Entity>" rule)
  → userTask
  → [optional exclusiveGateway, condition ${predicateSequence.execute(execution,'<predicate-rule-id>')}]
  → …
```

`candidateGroups` is left empty on every user task; assignment comes from the `roleGroups` argument of
`service.workflow.start`.

### The distinctive move: clocks as a modelled domain

Most projects hard-code "3 days". This one has six named clocks, a `deadlinePolicy` table with `durationValue` +
`durationUnit` + `escalationPoints` + `ownerRole`, a business-maintained `holiday` table, a `clockWarning` table
for escalation points already fired, a `breachRecord` table with a reason code, and an exception register that
reads them.

```groovy
def addWorkingDays = { java.time.LocalDateTime from, int days, Set hol ->
    def d = from; int left = days; int guard = 0
    while (left > 0 && guard < 4000) {
        guard++; d = d.plusDays(1)
        int dow = d.getDayOfWeek().getValue()
        if (dow >= 6) { continue }
        if (hol.contains(d.toLocalDate().toString())) { continue }
        left--
    }
    return d
}
def applyPolicy = { String code, java.time.LocalDateTime from, Set hol ->
    def pol = policyRow(code); if (pol == null) { return null }
    int v = ((pol.durationValue ?: 0) as Number).intValue()
    switch ((pol.durationUnit ?: 'HOURS').toString()) {
        case 'MINUTES':       return from.plusMinutes(v)
        case 'HOURS':         return from.plusHours(v)
        case 'CALENDAR_DAYS': return from.plusDays(v)
        case 'MONTHS':        return from.plusMonths(v)
        case 'WORKING_DAYS':  return addWorkingDays(from, v, hol)
    }
    return null
}
```

Three details to copy: **`guard < 4000`** stops a mis-seeded holiday table hanging the request thread; **no
statutory value is embedded in software** — a missing policy row throws rather than defaulting
(`"No deadline policy is configured for " + code + " - the business owns this value"`); and **the policy code is
composed from a state value** — `applyPolicy('TARGET_' + priority, now, hol)` — so one lookup table serves a
per-priority target without a switch in the rule.

### The distinctive move: the tabbed console over N CRUDs

The most-copyable screen in the set. One page, one `nct.tab.plugin`, N tabs, each tab an `nct.parsis.plugin`
holding exactly `dynaform.filter.form.plugin` + `crud.table.plugin` over a **different** CRUD.
`tabModel.items[i]` maps to child parsis node *i* **by order**.

```
Case workbench      7 tabs / 7 CRUDs   Case · Timeline · Trail · Control checklist ·
                                       Requests · Attachments · Evidence
Policy admin        7 tabs             every statutory number in the system
Exception registers 4 tabs             breached clocks · pending evidence · overdue · repeat parties
Pattern catalogue   3 tabs + re-score  business-owned scoring, then re-score every open case
Org reference       3 tabs
Authority desk      2 tabs
```

✅ **The auditor's screen is a worklist, not a report.** *"Auditors read the failure list, not the success
rate."* Each open exception is clickable and closable — *Record the reason* opens a reason-code form, *Close the
breach* is `direct: true`. A compliance screen that renders as a report has failed.

### The distinctive move: `_subject(alias)` — one form group for two entry paths

The most reused non-trivial helper (75 rules), and the reason 37 form groups cover 31 entities *and* 8 processes:

```groovy
// The same form group is reached from a crud-table ROW ACTION and from a WORKFLOW USER TASK.
// Table path: the submitted values are on the row, attrs are empty.
// Task path : the row is not seeded (the read throws) and the typed values are in the attrs.
// So: fetch the subject by the attr id the bind service task published, fall back to the crud
// row, then OVERLAY every attribute whose key names a field of the row.
def _subject = { String alias2 ->
    def r = null; def sid = null
    try { sid = context.data.getAttr(alias2 + 'Id') } catch (Throwable ignored) { }
    if (sid == null) { try { sid = context.data.getAttr('subjectId') } catch (Throwable ignored) { } }
    if (sid != null && !(sid.toString().trim().isEmpty())) {
        try { r = service.crud."${alias2}".get(sid.toString()) } catch (Throwable ignored) { }
    }
    if (!(r instanceof Map) || r.id == null) {
        try { r = context.<ctx>."${alias2}".data.get() } catch (Throwable ignored) { }
    }
    if (r instanceof Map) {
        new ArrayList(r.keySet()).each { k ->
            def v = null
            try { v = context.data.getAttr(k as String) } catch (Throwable ignored) { }
            if (v != null && !(v.toString().isEmpty())) { r[k] = v }
        }
    }
    return r
}
```

### Row scoping that fails closed

Twelve `Row Scope Filter - <Entity>` rules, identical in shape, wired as the table's `findRuleIdentifier`:

```groovy
def _myUnit = { ->
    def me = (service.security.user()?.email ?: '') as String
    if (me.isEmpty()) { return '00000000-0000-0000-0000-000000000000' }
    def rs = _rows(service.crud.staffUser.find([ email: me, isActive: 'true', rowsInPage: 5, pageNumber: 0 ]))
    if (rs.isEmpty()) { return '00000000-0000-0000-0000-000000000000' }   // fail CLOSED
    …
}
// Pagination + filter values arrive from the table via attrs (Jackson JsonNode).
// `param` is empty outside a delegated CRUD method, so reading it here would
// silently drop the filter form, the column filters AND the paging.
def filter = [ 'rowsInPage': attrs?.get('rowsInPage')?.asInt(),
               'pageNumber': attrs?.get('pageNumber')?.asInt() ]
attrs?.each { k, v ->
    if (k != 'rowsInPage' && k != 'pageNumber' && v != null && !v.isNull()) {
        filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText())
    }
}
// the scope is written LAST so a client-supplied value can never widen it.
if (!service.security.hasAnyRoleGroup("Oversight","Compliance","Auditor","Approvers","Administrator")) {
    filter['orgUnitId'] = _myUnit()
}
return service.crud.case.find(filter)
```

Three decisions in twenty lines: **unknown user → impossible UUID, not "all"**; **forward the whole attrs map or
lose paging and filters**; **write the scope last**. Row scoping belongs in the FETCH rule — *an action predicate
hides a button, it never removes a row from a list.*

### Separation of duties at INSTANCE level

The control is at the level of the individual case, not the role, so the predicate checks *two* identities — the
proposer on the row and the owner on the parent case — before it checks the state:

```groovy
if (!service.security.hasAnyRoleGroup("Approvers", "Administrator")) { return false }
def row = context.<ctx>.decision.data.get()
if (!(row instanceof Map) || row.id == null) { return false }
def me = (service.security.user()?.email ?: '').toLowerCase()
if (me.isEmpty()) { return false }
def parent = service.crud.case.get((row.caseId ?: row.case?.id) as String)
if (((row.proposedBy ?: '') as String).toLowerCase() == me) { return false }
def owner = ((parent?.ownerEmail ?: '') as String).toLowerCase()
if (!owner.isEmpty() && owner == me) { return false }
return ((row.state ?: '') as String) == 'PROPOSED'
```

Attach it to **both** the Approve and the Decline action, so the button is simply not there for the wrong
person — and read the row back **from the database, not from a stale form copy**.

### The dashboard template — build it once, clone it eight times

Every board is: one `global.replacement.plugin` named *Filters* (**no stored config** — the bar is built from the
union of the page's chart query parameters), then a Bootstrap grid in which each chart's title is an
`nct.label.plugin` whose id is literally `hdr_` + the chart node's own UUID, sitting immediately above
`<plugin id="<uuid>" name="chart.js.plugin">`.

✅ **Two chart engines on purpose.** Plotly for the 32 KPI indicators (delta arrows, no axes), Chart.js for the
55 data charts. **A KPI tile's value and its comparison come from ONE query via two replacements pulling
different columns** — never two queries:

```sql
SELECT count(*) FILTER (WHERE c.state NOT IN ('CLOSED','DUPLICATE')) AS value,
       count(*) FILTER (WHERE c.state NOT IN ('CLOSED','DUPLICATE')
             AND c.opened_at < (SELECT max(opened_at) FROM case WHERE deleted = false) - interval '90 days'
             AND (c.closed_at IS NULL OR c.closed_at >= (SELECT max(opened_at) FROM case
                                          WHERE deleted = false) - interval '90 days')) AS prev
  FROM case c WHERE 1=1 AND c.deleted = false
```
```js
var v = $$('Value', [0], 'Double[]')[0];   // replacement columnName "value"
var p = $$('Prev',  [0], 'Double[]')[0];   // replacement columnName "prev", SAME query
Plotly.newPlot(el, [{ type:'indicator', mode:(p == null ? 'number' : 'number+delta'), value:v,
  number:{ font:{ size:34 }, valueformat:',.0f' },
  delta:{ reference:p, position:'bottom', increasing:{ color:'#e0483a' }, decreasing:{ color:'#47CC29' } } }],
  { height:118, margin:{t:6,b:6,l:10,r:10}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    font:{ color: getComputedStyle(el).color } }, { displayModeBar:false, responsive:true });
```

⚠️ Note `increasing` is **red** and `decreasing` **green** — on a KPI whose good direction is down. Set the delta
polarity per tile, explicitly; do not inherit it.

✅ **A chart cross-filters on the dimension it groups by.** A by-unit chart sets `Unit`, a monthly chart sets
`Since`, a by-channel chart sets `Channel`. 25 of 55 charts carry it:

```js
cfg.options.onClick = function(e, els){ var v = null;
  if (els && els.length) { var i = els[0].index; v = (ids && ids[i] != null) ? ids[i] : this.chart.data.labels[i]; }
  this.crossFilter('Since', v); }.bind(this);
cfg.options.onHover = function(e, els){ if (e && e.native) e.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default'; };
```

✅ **Chart titles are written as questions and findings, not as column names.** *"Where the target slips, by
pattern"*, *"Why proposals are declined"*, *"How early or late against the target"*, *"Share of the allowed
window used"*. Same SQL, and it is the cheapest quality difference in the whole project.

### Where the effort actually goes

**Into 362 queries and the policy layer.** Also into two habits worth more than any single artefact:

- **Every rule's `description` names the requirement ids it implements, and the rule body cites the library doc
  that governs it** — `// SHAPE C: the SYSTEM opens the case (doc 27 §4-§5)`, `// doc 15 §6: a null reference
  means no document exists`, `// doc 04 buildFindScript`. An integrator opening any rule cold learns why it
  exists and where to read more. Copy this before copying anything else.
- **Configuration under the same approval discipline as case data** — the config tables carry
  `approval_state / proposed_by / proposed_at / approved_by / approved_at / pending_note` and a *Submit for
  approval → Approve / Reject* action pair, and every configuration edit hooks a generic before-save audit that
  writes one row per changed field, stamped with the **policy version in force**.

### Failure modes this shape invites

| Failure | What it looked like |
|---|---|
| ⛔ **The entire process layer switched off** | 8 workflows `deployed: false`, 10 schedulers `enabled: false`. Five user-facing actions therefore **throw at runtime** as exported (`workflow_is_not_deployed`), the eight worklists render empty, and nothing chases anything. The register half is complete and demonstrable; the process half was built and never turned on. |
| ⛔ **Operational queries clock-anchored while dashboards are data-anchored** | Dashboards correctly anchor windows to `(SELECT max(<col>) …)`; every scheduler-facing method uses `now()`. Right for a live system, wrong for a frozen dump: against the shipped data they return nothing, so even with schedulers on, the demo shows no activity. Nothing in the export tells a new operator to re-date the seed. |
| ⛔ **No include mechanism, so "shared" code is shared by copy** | One helper prelude duplicated 101×, `_subject` 75×, and one closure whose own comment says *"the same headless closure the sweep runs"* physically exists **three** times. Fix a bug and you fix it three times. |
| ⛔ **A hook coupled to a hard-coded list** | The generic audit rule iterates `CONFIG = ['patternTable','deadlinePolicy',…]`. Add an eighth configuration table and the edit action silently audits nothing. |
| ⛔ **Leaked starter-template role groups** | The **home dashboard's** nav entry is role-gated to five role groups from a different domain's starter that do not exist in this project, so home is invisible in the menu to every real role except `Author`. Same family: six orphan queries against a source not in `sources[]`, two `processGroups` named by bare UUID, 41 placeholder labels. |
| ⛔ **Overloaded form groups** | One generic *reason + note* form is reused for *Override the priority*, *Park* and *Mark as duplicate*. Same field labels, three different meanings; the user cannot tell from the modal which one they are in. |
| ⛔ **Dashboard filter labels monolingual** | Six lookup queries build a `VALUES (code, l1, l2, l3, ord)` table with all three languages and then select `cl.l1 AS name`. The translation was written and not wired. |
| ⛔ **One register unscoped among scoped siblings** | The cross-case register has no `findRuleIdentifier` and is the one exception register that is not row-scoped. Defensible, undocumented, and it sits next to three that are. |

---

## 5 · Shape X — the suite with hand-built consoles *(source A)*

### What drives the size

**Two independent multipliers: the entity backbone, and the number of BESPOKE WORKSPACES.** A has 163 entities
*and* 22 hand-authored consoles, and the second number is the product. The generated register/form/landing layer
is the back-office cellar; the studio consoles are the shop floor.

Recognise the brief by: **one operational site running one end-to-end process**; a **mandatory parent record**
that owns every child ("no orphan records"); a **regulated output**; and an owner who asks any *two* of "what
did one unit cost to produce", "which line earns most per unit of scarce capacity", "can we prove where this came
from". Those three questions are three whole subsystems, and they are why this shape is as large as it is.

⛔ **The tell that you are in Shape X and not Shape R: a screen where a clerk fuses four or more entities into
one non-tabular workspace, and a tabbed console (Shape C's answer) would still leave them tabbing.** A picked 15
of 163 entities for that treatment; the other 148 stayed registers.

### The budget

```
159 tables → 163 CRUDs (all methods=7 generated, two hand-built) → 433 pages
  22 studio consoles · 129 crud.table registers · 141 form pages · 109 landings · 24 console · 8 misc
→ 619 rules / 942 989 chars Groovy — of which 758 750 (80 %) sit in the 136 rules named "… (Studio)"
→ 970 441 chars JS + 552 017 CSS + 210 574 HTML = 1.73 MB hand-written front-end
→ 9 chart.js nodes (all children of ONE studio console) · 0 crud.tree · 0 business process.table
→ 7 BPMN / 0 deployed → 27 schedulers / all enabled → 10 PDF · 13 mail → 10 role groups
```

Ratios: **~1 studio console per 7 entities that the console fuses**, **~6 command rules per console**, **80 % of
the Groovy in 20 % of the rules**, **~78 KB of hand-written front-end per console**.

### The orchestration backbone — and the honest observation

**BPMN is vestigial. Cron schedulers and named command rules are the engine. Say it plainly.**

| Workflow | Elements | Deployed | Has a starter |
|---|---:|---|---|
| five business lifecycles | 8–14 | **no** | one, and it is on the wrong page |
| two scratch definitions | 10 / 0 | no | none |

`grep 'service.workflow.start'` across all 619 rules returns **nothing**. Two `ProcessTable` settings bind a
`workflowIdentifier` that is not in `rep.workflows[]` at all. Both `processGroups` are named by raw UUID.
`validate` raises the doc-27 error on six of the seven. **The five business workflows are drawings of the
intended lifecycle, not running machinery.** They were useful as design artefacts and nothing in the shipped
system consults them.

What runs the business instead:

**(a) 27 cron schedulers as a batch DAG.** Every one is `actionType: RUN_RULE` with a cron expression and a
`job.explanation` that cites the requirement it implements — a small habit that makes the scheduler list readable
as a specification:

```jsonc
{ "name": "Daily compliance sweep", "actionType": "RUN_RULE", "enabled": false,
  "job": { "explanation": "A-19 daily 05:00", "expression": "0 0 5 * * *" },
  "actionRuleIdentifier": "aef05387-…" }
```

The 27 read as the operation's night shift: 00:05 hold-release; 02:00–02:50 the derivation chain (aggregate KPIs
→ allocate shared costs → rebuild the value ledger → per-plan economics → value the holdings → projection → close
the period → refresh the break-even); 05:00–05:45 the task-generating sweeps; 06:00–07:00 the ageing and overdue
sweeps; hourly overdue/aggregation/identity sync; every 5 minutes a watchdog.

✅ **Read the minute offsets as a dependency graph.** `02:10 · 02:25 · 02:30 · 02:35 · 02:40 · 02:45 · 02:50`
*are* the sequencing mechanism when the platform has no batch DAG. ⛔ And they are a fragility: nothing enforces
the order, and one slow job silently corrupts the next. If you use this pattern, make each downstream job
**verify its input's freshness** rather than trusting the clock.

**(b) Lifecycles are status columns advanced by named command rules.** No process token. Each transition is one
Groovy rule with the guard inside it, called from exactly one button.

### The distinctive move: one read rule per screen, returning the whole page in one call

Every console's `load()` is a single call. The rule returns lists, capability flags, the resolved locale and a
diagnostic trace in one map:

```groovy
return [ok: true, locale: __loc,
        scope: sc.scope, scopeWhy: sc.why, total: total, shown: rows.size(),
        myRoleGroups: myRoleGroups, trace: __trace, rows: rows,
        users:      safe { service.crud.user.findAll(page) },
        assignable: __signInCapable(safe { service.crud.user.findAll(page) }),
        plans:      safe { service.crud.plan.findAll(page) },
        statuses:   safe { service.crud.status.findAll(page) },
        canDelete: d.ok, canEdit: ePerm.ok, decidedBy: d.decidedBy, degraded: d.degraded,
        user: u?.email]
} catch (Throwable __ex) {
    return [ok: false, error: 'EXCEPTION', trace: __trace,
            message: __ex.getClass().getSimpleName() + ': ' + (__ex.getMessage() ?: 'no message')]
}
```

Two details make it work: **`safe { … }`** wraps each list so one failing read cannot blank the screen *and
appends the exception to `__trace`*, because otherwise "an empty dropdown" and "a read that quietly threw" look
identical from the browser; and **the whole body is inside `try { } catch (Throwable)` with the same map shape on
failure**, so the client has one branch, not two.

Naming convention across all 136 studio rules — copy it verbatim:

| Pattern | Count | Example |
|---|---:|---|
| `<Screen> Screen Data (Studio)` | 22 | one read rule per console |
| `<Verb> <Noun> (Studio)` | ~95 | one command, one button |
| `<Screen> Rights (Studio)` | 1 | the capability resolver |
| batch rules behind schedulers | 27 | named for the requirement they implement |
| cross-cutting services | ~8 | `Log UI Event`, `Locale Probe`, `Identity Check`, `Schema Migration Status` |

### The distinctive move: capability flags resolved server-side, with the resolution EXPLAINED

The platform's role API is **fail-closed**, so `false` everywhere is indistinguishable from "no groups". The
resolver probes, decides, and reports *which mechanism decided*:

```groovy
// Treat a positive answer as proof the API resolved; only then is it authority.
def platformUsable = apiAnswered && (isAdmin || probe.any { k, v -> v })
if (platformUsable) { ok = isAdmin || probe.any { k,v -> v } || byUser
                      decidedBy = 'platform role api' }
else                { ok = isAdmin || anyGroup || byUser
                      decidedBy = 'project store (platform role api unavailable)' }
return [ok: ok, allowed: allowed, admin: isAdmin, probe: probe, via: via,
        decidedBy: decidedBy, degraded: !platformUsable, mapped: !members.isEmpty(),
        scope: sc.scope, scopeWhy: sc.why]
```

The screen's buttons follow `canEdit`/`canDelete`; **the delete rule re-checks the same resolver server-side
regardless.** And the fallback settings store carries a hard-won note:

```groovy
// ⛔ settings.value is jsonb, so it arrives as a Jackson ObjectNode/ArrayNode — neither String
// nor List. Without this every read below returned null and every setting fell back to its
// hardcoded default. toString() on a Jackson node is valid JSON.
if (v != null && !(v instanceof String) && !(v instanceof List)) v = v.toString()
```

### The distinctive move: the client kit — one write path, one log path, one message rule

Every write on every console goes through one 30-line helper, and each of its guards is a scar:

```js
let busy = false;
async function action(btnSel, msgSel, rule, input, after){
  // ⛔ a click arriving while an earlier load() was still in flight was dropped here with no
  // message, no button state and no trace — so the PREVIOUS action's text stayed on screen
  // and read exactly like the new one had succeeded.
  if (busy){ say(msgSel,'err', L('Still working on the last action…','…')); return; }
  busy = true;
  const btn = q(btnSel); if (btn) btn.disabled = true;
  // ⛔ a message must never outlive the action that wrote it. Five sightings, the worst an
  // operator seeing a database error after a write had actually SUCCEEDED — the obvious
  // reaction is to retry and double-post. Cleared first, so a message that fails to render
  // leaves an EMPTY strip rather than a wrong one; re-asserted after after(), so a reload
  // cannot leave the wrong sentence standing.
  say(msgSel, '', '');
  try {
    const r = await ctx.callRule(rule, input) || {};
    if (r.ok === false){ say(msgSel, 'err', errText(r)); return r; }
    const okMsg = r.message || 'Saved.';
    say(msgSel, 'ok', okMsg);
    if (after) await after(r);
    say(msgSel, 'ok', okMsg);
    return r;
  } catch (e){ say(msgSel, 'err', errText(e)); }
  finally { busy = false; if (btn) btn.disabled = false; }
}
```

✅ **`errText()` must not print a memory address as though it were an explanation.** A server-side executor
failure arrives as an object with no enumerable fields whose only stringification is a Java identity hash
(`…ExecuteResponse$ExecutionError@5e20cfdf`). Match it, say what is true — *"The rule failed without returning a
message — check the server log"* — and keep the hash as the correlation token that ties a screenshot to a log line.

✅ **Wrap `ctx.callRule` once per screen** and every server call is logged with no per-action logging code:
stash the original (`if (!ctx.__logRaw) ctx.__logRaw = ctx.callRule.bind(ctx);`), stamp the reading locale onto
every input, then `pr.then(ok → write('info',…), err → write('error',…); throw)`. Two guards matter:
`if (ctx.__logWrapped) return;` makes it idempotent under re-mount, and

```js
// never log the logger, or the table fills with itself
if (action === 'Log UI Event (Studio)' || action === 'Logs Screen Data (Studio)') return;
```

### The distinctive move: theming as one all-skins block plus four tiny overrides

`css.byTheme` per component is `{"*": 15–33 KB, "<dark skin>": ~0.6–1.3 KB × 4}`. The `*` block declares every
colour as `var(--platform-token, <light literal>)` — the dark skins define those tokens on `:root` and the light
skin does not, so **one block serves five skins**. (`:root` is rewritten by `HtmlStudioCssScoper` to this
instance's wrapper, `#dokie-plug-<id>`.)

```css
:root{
  --sx-surface:      var(--current-line, #ffffff);
  --sx-surface-sunk: var(--background, #f3f4f6);
  --sx-fg:           var(--bs-body-color, #1f2937);
  --sx-fg-strong:    var(--foreground, #111827);
  --sx-mut:          var(--foreground-muted, var(--comment, #5b6472));
  --sx-bd:           var(--bs-border-color, #e5e7eb);
  --sx-accent:       #047857;  --sx-ok: #047857;  --sx-warn: #92400e;  --sx-bad: #b91c1c;
}
```

The four per-skin blocks override **only the status hues**, and the reason is recorded in the CSS: the platform
palette maps `--green`/`--cyan`/`--purple` to nearly the same hue on several dark skins, so status colour-coding
collapsed and every pair measured 2–3:1 on the card surface. The replacements are measured values, ≥4.5:1 on all
four dark skins, and the accent flips to a **light fill with a dark label** because white-on-green cannot reach
4.5:1: `--sx-ok:#6ee7a8; --sx-warn:#fcd34d; --sx-bad:#fca5a5; --sx-info:#93c5fd; --sx-accent-fg:#06281c;`

### The distinctive move: an app that diagnoses and migrates itself

One console calls `Schema Migration Status (Studio)`, `Apply Schema Migration (Studio)`, `Identity Check
(Studio)`, `Locale Probe (Studio)` and `Sync Users And Roles (Studio)`. **The operator can see who the server
thinks they are, what locale the server thinks they are reading, and whether the schema is at the expected
revision — and apply the migration — without an integrator.** Where the role API is fail-closed and the session
locale does not follow the header switch, these probes are the only way to tell a configuration problem from a
code problem.

### Where the effort actually goes

**Into 1.73 MB of hand-written front-end and 758 KB of studio Groovy.** Everything else — 163 CRUDs, 433 pages —
is generated and, mostly, unfinished. That imbalance is the shape, and §5's failure table is the bill for it.

### Failure modes this shape invites

| Failure | Count | What it means |
|---|---:|---|
| ⛔ **The generated CRUD layer is half-wired** | 71 | actions that open a form (`formGroupIdentifier` set) with **no** `onBeforeCompleteRuleIdentifier` — the form submits and **saves nothing** |
| | 63 | `delete` methods that physically `DELETE FROM` a table other tables reference by FK — the first user who deletes a row in use gets a foreign-key violation and no way forward |
| | 131 | CRUD methods whose `script` and whose saved query are **different statements** — only the script runs, but opening the method in the editor reinstalls the query's version |
| | 126 | SQL methods with `queryIdentifier` unset, so editor and runtime can drift |
| | 38 | form groups pointing `contentPageIdentifier` at the shared **system** Landing page → an end-user Create/Edit is access-denied |
| | 11 | `findAll` methods with untyped `OFFSET (:pageNumber * :rowsInPage)` — fine from the UI table, fails from a rule |
| | 1 | a `count` that does not filter the soft-delete marker its `findAll` filters → paging disagrees with the rows |
| ⛔ **The studio layer duplicates its own runtime 22–24 times** | | `errText` in 24/24 scripts, `applyLocale`/`say`/`bind`/`esc` 23/24, `action(…)` 19/24, the logging prelude 19/24. A vendored shared library exists, is loaded by 21 of 22 components, and contains **only** a breadcrumb proxy. Every cross-cutting fix is a 22-to-24-place sweep. |
| ⛔ **A sweep anchored on a name is not a sweep** | | One sweep anchored on the script named `main` and missed the only two components with a **second** script. Another fixed one helper on one screen, then found three distinct shapes across 22: *"anchoring on one body would have covered 4 and silently missed 18."* **A screen is the union of its scripts, not one of them; source order is not visibility.** |
| ⛔ **Seed data standing in for behaviour** | | A movement table carried outbound rows and the balance reconciled perfectly — and **no rule in the project wrote any of it.** The seed had been written from the specification, so it agreed with the specification, and it stood in for the behaviour through nine rounds of scenario testing. *"A balance is verified by causing a movement and re-reading it, never by inspecting a value that agrees with expectations."* |
| ⛔ **No persona gating in the content tree** | | 367 pages carry only the baseline authoring gate, 1 page carries a business role, and five of the declared role groups **do not exist in this project** — they are from a different domain's starter template. Every persona sees all 171 nav links. All real gating is Groovy-side, which is the right layer, but the nav was never given the matching `roleGroupAccessors`. |
| ⛔ **All 27 schedulers `enabled: true`** | | Importing this export into a fresh tenant starts a five-minute watchdog and a nightly period close the same night. |
| ⛔ **Dead nodes and a decorative page** | 35 | `nct.parsis.plugin` children on the home page never referenced by the HTML that owns them — still in the tree, still exported, never drawn. Plus an **empty** page that exists only so a nav folder has a target. |
| ⛔ **The archive lags its own specification** | | The requirements document ran 22 revisions past the export: tables, rules and a screen fix that are simply not in the build. **Read the post-mortem section of the specification as the more advanced artefact**; the export is the snapshot the obligations were derived *from*. |

---

## 6 · The one cross-shape rule about ledgers

⛔ **When you make a quantity move in a direction nothing moved it before, enumerate every flow that reverses
it.** Giving a store its first outbound movement silently broke a rejection rule written years earlier that had
always been correct to return no quantity — because nothing had ever removed any. Every balance that can go up must
have an enumerated list of everything that takes it back down, **written when the increase is built**.

⛔ **A register whose members carry consequences is not a register — it is a dimension.** Three intake reasons
drove two decisions through `reason == 'internal'` and `reason == 'external'`. Open that list to editing and
*reason number four* silently forfeits the claim the second branch was protecting, *"because that is what the
`else` branch happens to do."* **Before you make a list editable, enumerate every branch that compares against
its literal members and turn each one into a column on the row.**

⛔ **A dimension whose members are not the same kind of thing is not a dimension.** Three distinct strings in a
free-text location column were promoted into three entities. The tell was visible before anyone asked: two of the
three were places and the third was a *state*.

---

## 7 · Reading a brief: which shape it becomes

Score the brief on five counts, in this order. The first four are countable from the document; the fifth is a
judgement you must make out loud.

| # | Count in the brief | A | B | C | D |
|---|---|---:|---:|---:|---:|
| 1 | **Aggregates** (nouns you store, list and edit) | 159 | 43 | 31 | 16 |
| 2 | **Documents with a lifecycle** (header + lines + states) | ~12 | 12 | 4 | 4 |
| 3 | **Numbered reports owed to an external reader** | 0 | 9 | 8 | 0 |
| 4 | **Clocks / policy tables the business must edit without a release** | 1 | 2 | 7 | 3 |
| 5 | **Bespoke non-tabular workspaces** (a clerk fuses ≥4 entities, tabs would not help) | 15 | 0 | 0 | 0 |

**The routing:**

- **Row 5 > 0 → Shape X**, whatever the other rows say. A single bespoke console changes the cost structure of
  the whole delivery, because it drags in the studio kit, the theming pass, the per-screen read rule and the
  22-place-sweep problem. Price it as a subproject.
- **Row 5 = 0 and row 3 ≥ 6 → Shape C.** Reporting is the product; the entity model will come out smaller than
  you fear and the query count larger.
- **Row 5 = 0, row 3 < 6, row 2 ≥ 8 → Shape R.** The documents are the product; budget SQL derivation methods,
  not screens.
- **Row 1 ≤ 15 and there is exactly one end-to-end chain → Shape S.** Resist every request to grow it; the
  cheapest thing this shape gives you is that it stays comprehensible.

**Signals that override the counts:**

| Signal in the brief | Reads as |
|---|---|
| a **mandatory parent record** — "no orphan X" — named in the first paragraph | It decides nearly every table and screen. Name it in the plan's first paragraph too. |
| **two hard gates that are refusals, not warnings** | Refusals live in Groovy command rules, never in a disabled button. A brief that says "the system must prevent" and a build that greys out a button do not match. |
| "prove where this came from" **and** "what did one unit cost" | Two subsystems, and together they are Shape X. |
| "the business changes the numbers, not a release" | A policy CRUD with a page — count them; §7 row 4. |
| "an auditor reads the failure list" | An exception **worklist**, not a report. Each open item clickable and closable. |
| "bulk operations" | *"Assigning 200 generated items individually will end adoption in week one."* A bulk bar is not a convenience feature; it is a shape requirement. |
| a persona who is **measured by** the system rather than reading it | Offline-first, ≤3 taps, 44 px targets, default-locale-first. That persona alone can justify a studio console. |
| the owner's home screen described as "four numbers and a trend" | ⛔ *"Anything requiring interpretation has failed for this persona."* Do not put a chart grid there. |

---

## 8 · What to refuse to build

Each of these was built at least once in the four and cost more than it returned.

1. ⛔ **A BPMN diagram nobody starts.** A shipped five undeployed, unstarted workflows; C shipped eight. If you
   cannot name the starter (`START ACTION` / `DOCUMENT ACTION` / `SCHEDULER` / `CRUD METHOD` / `SERVICE TASK`)
   *and* deploy it *and* see a row in the worklist, author the status column and the command rule instead. Five
   drawings cost A real design time and bought nothing that its status columns did not already give it.
2. ⛔ **A generated register page you will not finish.** Generate the CRUD; generate the *page* only when the
   entity's create/edit/delete actions have persist rules and the form group has its own landing page. 163
   generated, ~22 finished, and the other 141 are liabilities, not fallbacks.
3. ⛔ **A second studio console before the shared kit exists.** A's single biggest avoidable cost. Write
   `errText`, `say`, `bind`, `esc`, `pick`, `action`, `applyLocale` and the logging wrapper into a vendored
   `tenant-files/studio/<kit>/` library **before the second console**, declared once per component:
   ```jsonc
   "libs": [{ "name": "sxkit", "enabled": true, "order": 0, "globalVar": "SxKit",
              "assets": [{ "kind": "JS_CLASSIC", "path": "studio/sx-kit/sx-kit.js",
                           "fileName": "sx-kit.js", "entry": false, "order": 0 }] }]
   ```
4. ⛔ **A chart without a board.** A hung 30 and 16 charts off a bare parsis on two pages and `validate` flags
   them; C's 87 charts are 8 boards × (4 KPI + 6–7 charts), each with one shared filter bar and cross-filter on
   the group-by dimension. **Derive dashboards, not charts.**
5. ⛔ **A settings row nothing reads.** B shipped 12. Grep for the key before you ship the row.
6. ⛔ **A side-form of `scope: GLOBAL` controls reachable from a crud-table row action.** It reports success and
   changes nothing. D shipped 12 of them.
7. ⛔ **A parallel mechanism when one already exists.** *"Before writing a guard, a resolver, a formatter or any
   other cross-cutting mechanism, find the existing one. Inventing a parallel one is only correct once you can
   say what the existing one gets wrong."* Three separate modules in A tried to fix one refusal; the answer was
   already in a comment older than the change request.
8. ⛔ **38 code-list links in the sidebar.** One page with a picker, or nothing.
9. ⛔ **A seeded balance.** Seed the movements and let the recompute method produce the balance, or seed nothing.
10. ⛔ **A compliance screen that renders as a report.** It has to be a worklist.

---

## 9 · Where the four deliveries correct the library

### 9.1 [19-build-decision-procedure.md](../19-build-decision-procedure.md) and [07-workflows-and-tasks.md](../07-workflows-and-tasks.md) — "a workflow + its worklist, always"

Doc 19's requirement table maps *"a multi-step process with human hand-offs / approvals"* to a BPMN workflow plus
its worklist page, *"always, not 'if the PRD asks'"*, and doc 07 §Step 5 makes the worklist an invariant.

**The deliveries say the invariant is right and the mapping is too eager.** 4 of 4 authored BPMN; 2 of 4 shipped
it entirely undeployed. A ran a 163-entity end-to-end operation with **zero** deployed workflows, on status
columns advanced by 136 named command rules and 27 cron schedulers, and that half of A works. C's eight
undeployed workflows made **five user-facing actions throw at runtime** as exported.

**Which side is right:** the docs, with one added test in front of the mapping. Before authoring a workflow, ask
**"is the case queued and claimed by somebody who does not own the row?"** If yes (B's approver, D's counterparty
and logistics steps), you need BPMN, the worklist and the starter — all three, deployed. If no — the transition
is a button on a register the same team owns — you need a status column, a predicate and a command rule, and the
BPMN is a drawing. Author the drawing in the plan document, not in `rep-objects.json`.

### 9.2 [24-html-component-studio.md](../24-html-component-studio.md) §1.2 — "the boring page still runs the business"

Doc 24 recommends keeping the entity's normal `crud.table.plugin` page and form group under a studio console, on
the grounds that *"if the component breaks, the boring page still runs the business."*

**The claim has an unstated precondition, and A shows what happens without it.** 71 of A's actions submit and
save nothing, 63 delete methods hard-`DELETE` FK-referenced rows, 38 form groups are access-denied to end users.
For most of A's 163 entities the boring page is not a fallback; it is a page that loses the user's work.

**Which side is right:** doc 24, with the precondition made explicit — *a generated register is a fallback only
after its create/edit/delete actions carry `onBeforeCompleteRuleIdentifier`, its `delete` soft-deletes, and its
form group points `contentPageIdentifier` at its own landing page.* Add the corollary: **generate CRUDs for every
table, pages for the ones you will finish.**

### 9.3 [12-queries-sources-schedulers-and-rest.md](../12-queries-sources-schedulers-and-rest.md) — `enabled: false`

Doc 12 is emphatic and correct: an imported `enabled:true` scheduler auto-registers a live `CronTrigger` and
fires immediately, so author `enabled=false`.

**Both failure directions were observed.** A shipped 27/27 enabled (a five-minute watchdog and a nightly period
close start on import). D shipped 4/4 enabled. B shipped 2/2 disabled and C 10/10 disabled — and in both of those
the entire proactive half of the system is inert, with nothing anywhere saying so.

**Which side is right:** doc 12, plus a rule it does not state — **`enabled:false` is only half a decision.** The
export must ship with a named enable list in the handover (which scheduler, what cron, what it does, in what
order), because a disabled scheduler is invisible: nothing is logged, the predicate is never even evaluated, and
the reviewer cannot tell "correctly disabled for import" from "never finished".

### 9.4 [26-orchestration-and-testing.md](../26-orchestration-and-testing.md) §1 — "zero workflows for a process PRD"

The symptom table lists *"Zero workflows for a process PRD"* with root cause *"'a lifecycle is simpler than BPMN'
used to skip the workflow"*.

**A is the counter-example and it is the largest of the four.** Zero deployed workflows was the correct outcome
there, reached for the wrong reason (seven were authored and abandoned rather than never authored). The
diagnostic is not the count; it is §9.1's queued-and-claimed test.

**Which side is right:** the deliveries. Rewrite the symptom as *"a process whose case nobody can find"* — the
observable is an empty worklist or a lifecycle with no queue, not the number of BPMN files.

### 9.5 [22-charts-params-and-filters.md](../22-charts-params-and-filters.md) §2A — "the specified chart list is a FLOOR"

Right, and under-specified about the *unit* of derivation. A derived more charts (30 and 16 on two legacy pages)
and they are stacked on a bare parsis with no filter bar, no cross-filter and no board identity; `validate` flags
them and the profile's own verdict is "leftovers, ignore". C derived to **87** and every one belongs to a
numbered board with a shared 4-parameter bar.

**Which side is right:** doc 22, with the unit corrected — **derive BOARDS, then charts within a board.** A chart
that does not belong to a board with a shared `global.replacement` filter bar is an orphan regardless of how
well-derived the question was.

### 9.6 [19-build-decision-procedure.md](../19-build-decision-procedure.md) Phase 1b — "do NOT derive the page list from the table list"

Doc 19 is right and A is the hardest number in the set against it: 163 tables → 433 pages → **171 nav leaves**,
including 38 code lists, a duplicated home, sub-headings that are also links to their first child (`validate`
reports it eleven times), and the whole business application filed inside the baseline's **authoring** drawer,
one level *deeper* than the admin links. B put 9 registers on 4 nav pages. C put 90 of 128 pages as children of
their console. D put 32 of 67 as form children and moved home out of the authoring drawer.

**Reinforcement, plus the metric:** count **nav leaves**, cap them at roughly one per *workplace*, and build the
nav **last, from the brief's own business group names**.

### 9.7 Where the deliveries contradict each other — and which way to jump

| Question | A | B / D | Jump to |
|---|---|---|---|
| **How to share Groovy** | copy-paste (24 screens) | `CALL("<rule display name>")` wrapping `service.rule(...)`, unwrapping the cause chain with a `guard++ < 12` bound | **B/D.** One rule, called by name. Accept the rename fragility and **never rename a called rule** — there is no static check and no error until the button is clicked. C's 101× duplication is the alternative and it is worse. |
| **How to share JS** | a vendored kit that does one thing, everything else copied | n/a (no studio layer) | **A's mechanism, A's discipline reversed.** Vendor the kit through `tenant-files/studio/<kit>/`, and put the helpers in it *before the second console*. |
| **How to seed** | 153 of 159 tables seeded from the specification; a balance reconciled that no rule wrote | ~19 000 rows of a year of synthetic history, produced so the boards and the SLA charts are demonstrable | **D.** Seed volume, not seed agreement. A seed written from the spec will agree with the spec and prove nothing. |
| **Where to anchor a window** | n/a | D anchors charts *and* the period lookup to `date_trunc('month', (SELECT MAX(col) …))`; C anchors charts to `MAX(data)` but sweeps to `now()` | **D.** Anchor every read-side window to the data; keep `now()` on write-side sweeps; and say in the handover that the seed must be re-dated. |
| **Where the front door lives** | duplicated: one page, two nav labels, both inside the authoring drawer | B puts home in the first business group; D moves it out of `Pages` to position 0 | **B/D.** And B's own failure is instructive: its home page's only content plugin is a platform admin widget, so the front door renders the role-group console. **Open the home page before you call the build done.** |
| **Enum labels in tables** | n/a | B has a fully translated vocabulary table that its 112 status columns do not read | **Read the vocabulary table**, or accept that list columns and form dropdowns will disagree about the same field. |

---

## 10 · The build order, per shape

Common to all four, and never reordered: schema → CRUD → context → rules → roles → forms → form groups → pages →
templates → workflows → schedulers → nav → validate. What changes is where the weight sits.

**Shape S.** Schema (16 tables, soft delete, partial unique indexes on document numbers, CHECK per status set,
snapshot columns on lines) → CRUDs by tier → the derived arithmetic as SQL methods → the five rule families
(`Find — X`, `Choices X`, `X Action Create/Update/Delete`, `X Is <Status>`, `Is <Role>`) → register pages →
business rules callable from both a row action and a service task (`_rid`) → the BPMN and its role predicates →
the claim columns, candidate/claim/repair methods, sweep rule, gate predicate, scheduler → the dashboard → the
nav → trilingual inline help on every form, explaining the *rule*.

**Shape R.** Schema in its own schema → **the vocabulary table before anything UI** → the settings table, with a
description citing the requirement each row answers, **and then actually read them** → CRUDs by tier → derivation
in SQL, orchestration in Groovy → guarded transitions (`WHERE id = :id AND status = '<expected>'`) → the
four-layer rule stack per document, with bucketed `description` prefixes so `grep` is an index into a 400-rule
codebase → nav last, fully localised at both group and leaf level.

**Shape C.** Schema with soft delete + **partial unique index per business key** (`… WHERE (deleted = false)`)
and a `is_pre_system` flag separating migrated rows from system-handled ones → the policy tables first, because
every clock reads them → the case aggregate and its child registers → **the tabbed console template, then clone
it** → the branch/row scope filter rules as `findRuleIdentifier` → the validation gates (refuse, do not warn) →
the dashboard template, then clone it eight times → the eight workflows with the identical skeleton and one claim
column each → the schedulers, each with a PREDICATE gate so the action never runs on an empty set → nav with
every entry role-gated against the brief's own access matrix.

**Shape X.** Name the **mandatory parent** and its two hard gates first → generate the CRUD backbone and finish
the ones no console will cover → **build the ledgers with their reversals in the same module** → choose the
console screens deliberately (15 of 163 entities, not 163) → **write the shared kit before the second console** →
one read rule per console, one command rule per button, both named to the convention, both returning
`[ok:…, message:…, trace:…]` → the batch chain in schedulers with explanatory `job.explanation` strings and cron
minute offsets encoding the dependency order, shipped `enabled:false` → reach for BPMN only if something actually
starts it → the nav last, from the brief's own business group names, and never inside `Pages`.


---

## Done when

- The brief has been **named as one of the shapes**, in writing, and the artefact budget that comes with that
  shape is written beside the inventory — not discovered halfway through.
- The **refuse-list is explicit**: what the PRD asks for that this shape says not to build, and why. A shape
  chosen without a refuse-list has not been chosen; it has been assumed.
- The console count is a **deliberate subset** of the entity count, and someone can say why each console
  earned its place. If the two numbers are close, the nav was derived from the table list.
- Every register that no console will cover is finished anyway — a CRUD with no screen is a gap, not a saving.
- The nav groups carry the **brief's own business names**, and nothing business-facing sits inside `Pages`.
- The build order for the chosen shape (§10) has been read, and the first thing being built is the first thing
  it names.
