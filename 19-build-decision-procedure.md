# 19 — Build Decision Procedure (PRD → `.mrjun`)

**What this is.** The **deterministic decision spine** that turns a request into a built project. It is the
missing half of the two-step model in [README.md](README.md): the docs `00`–`18` say *how* to author each
entity; [13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md) gives
the *write order* + dependency graph; **this doc says what to DECIDE, in what order, and when a phase is DONE.**
Follow it top-to-bottom for every task. It replaces the old hand-wave "another Claude reads the PRD and writes
an instruction document" — the instruction document *is* the filled-in output of Phase 1 + the per-phase
decisions below.

**The contract (DRY).** Every phase is **Decide → Author → Done-when**. *Decide* lists the choices with a
**default** and *how to decide*. *Author* points at the exact doc section + `mrjun.py` command — it never
repeats a shape that `00`–`18` already document. *Done-when* is a checkable gate. Do not skip a gate; do not
re-derive a shape a doc already gives.

**Ground rules that hold in every phase** (full statements: `system_prompt.txt` "NON-NEGOTIABLE
INVARIANTS"): links by `identifier`
(rep `id=null`); config slots — form controls→`properties.settings`, tables→`properties.model`,
chart→`properties.Javascript`, tabs→`properties.tabModel`, filter form→`properties.filterFormModel`; preserve
the typos (`process.table.pluin`, `POISTGRESQL`, `Scheduelrs`, `Date Picher Label Field`; and keep an existing
`_cruid` alias verbatim — though that suffix is one project's convention, not a platform rule, see Phase 0); predicate/
execution Groovy bodies use an explicit `return`; `localizedNames`/`localizedButtonNames` cover **every**
`tenant.json.locales`; the receiving project must be `type == REPORT`; **prefer the `mrjun.py` command** over
hand JSON, then `validate`.

---

## Coverage map (this doc ⇄ the areas a full build must cover)

| Concern | Phase | Reference doc |
|---|---|---|
| Detect scenario, set project name/alias/domain/locales/schema | **0** | [00](00-export-format-and-import.md), [13](13-master-playbook-empty-to-dynamic-project.md) |
| Decompose PRD → entity/actor/document/status/report/notify/process inventory (**+ the chart list: derive beyond it, challenge what it names**) | **1** | this doc, [22](22-charts-params-and-filters.md) "## 2A. The specified charts are a FLOOR" |
| Database (schema, tables, PK, FK, CHECK, lines, audit cols) | **2** | [10](10-database-management.md) |
| Business logic — dynamic CRUD, SQL + Groovy methods, sources | **3** | [11](11-business-logic-dynamic-crud.md), [18](18-existing-schema-to-dynamic-wiring.md) |
| Contexts — which context, which crud aliases inside | **4** | [08](08-groovy-rules-and-context.md) |
| Rules — predicates / execution / validation, Groovy `service.*` | **5** | [08](08-groovy-rules-and-context.md), [09](09-groovy-hints-and-live-context.md), [16](16-groovy-service-api.md) |
| Role groups + page security / access | **6** | [12](12-queries-sources-schedulers-and-rest.md), [01](01-content-model-and-pages.md) |
| Forms (+ the form's content page), fields, field types & mappings, dropdowns, field events, action buttons | **7** | [02](02-form-controls-reference.md), [03](03-generate-fields-from-crud.md), [14](14-plugin-catalog-all.md) |
| Form groups (+ landing page), predicate→form mapping, create/edit actions, direct vs non-direct | **8** | [06](06-form-groups-and-mapping.md), [04](04-crud-table-plugin.md) |
| Pages, page map, access, `crud.table` / `crud.tree` / `process.table`, **multiple CRUDs in tabs** | **9** | [01](01-content-model-and-pages.md), [04](04-crud-table-plugin.md), [05](05-crud-tree-and-process-table.md), [14](14-plugin-catalog-all.md), [22](22-charts-params-and-filters.md) |
| Mail templates, PDF templates, the PDF→mail flow | **10** | [15](15-pdf-and-mail.md) |
| Workflows, tasks, user-task actions, process tables — **one worklist page per workflow, always** | **11** | [07](07-workflows-and-tasks.md), [05](05-crud-tree-and-process-table.md) |
| Schedulers — which, on what cron, calling which rule | **12** | [12](12-queries-sources-schedulers-and-rest.md) |
| **What STARTS each process** — a start form, or the SYSTEM itself: a scheduler tick / a written row / a step in another process, running a rule that gathers rows, shapes a context data document, calls `service.workflow.start` and does not re-open the same case every tick (its claim/write-back COLUMNS are Phase 2, its candidate/claim METHODS Phase 3) | **1, 1a, 2, 3, 5, 9, 11, 12** | [27](27-event-driven-process-start.md), [07](07-workflows-and-tasks.md), [16](16-groovy-service-api.md) |
| Left-nav quick links **+ the front door** (home = chart dashboard or main worklist; never empty) | **13** | [17](17-left-nav-quick-links.md), [21](21-homepage-and-redirect.md) |
| Validate → verify against real rows → pack | **14** | [tools/README.md](tools/README.md), [18](18-existing-schema-to-dynamic-wiring.md) |
| **Custom component / hand-built widget** — an `nct.html.plugin` studio project (libs, isolated JS, `ctx.callRule`/`ctx.callBl`, breadcrumb buttons, server-paged hand-built tables) | **9** | [24](24-html-component-studio.md), [24b](24b-html-composition-and-plugin-tags.md), [24c](24c-html-data-tables-and-paging.md) |
| **Authored CSS / theming** (cross-cutting) — ⛔ read BEFORE the first line of CSS: a skin is a whole-stylesheet swap, there is no theme class to select on, and neither import nor validate catches an unreadable screen | **7, 9** | [24a](24a-theming-and-dark-mode.md) |
| **Field-level plugin config** — the exact slots, defaults and editors of every plugin you place | **7–11** | [14a](14a-plugin-config-reference.md) |
| **Localization** (cross-cutting) — per-locale maps (author every `tenant.json.locales`), entity `localize`, runtime + Groovy locale, no auto-translate on import | **0, 7–9, 14** | [20](20-localization.md) |

---

## Build order — the strict, numbered sequence (do NOT reorder)

Author the phases **in this exact order**. Each step exists only after its predecessor: a rule needs a context,
a context needs a crud, a crud needs a table; a form field maps a crud column; a table action points at a form
group; a page hosts a table; a template/workflow/scheduler is fired by a rule. **Never author a later step
before the thing it references exists** — that is the whole reason for the order.

```
 0. Scenario + global params  (detect A/B/C; name/alias/locales/schema/context)
 1. Decompose PRD → inventory  (entities, actors, documents, statuses, reports, notifications, processes,
                               TRIGGERS — see 1a)
 1a. TRIGGER inventory         → what STARTS each process: FORM / SCHEDULER / CRUD METHOD / SERVICE TASK   [27]
 2. DATABASE                   → tables, PK, FK, CHECK(status sets), line tables, audit cols        [10]
 3. BUSINESS LOGIC             → dynamic CRUD + SQL/Groovy methods (+paired queries) + source        [11][18]
 4. CONTEXT                    → one context listing every crud alias                                [08]
 5. RULES                      → predicates / execution / validation (choices, lifecycle, security)  [08][16]
 6. ROLE GROUPS + PAGE ACCESS  → roleGroups + assignments + page public/authenticated                [12][01]
 7. FORMS + FIELDS + EVENTS    → the form's content PAGE + its controls (types→mappings, dropdowns, events)  [02][03]
 8. FORM GROUPS + ACTIONS      → the group's LANDING page + predicate→form mapping; create/edit actions    [06][04]
 9. BUSINESS PAGES + TABS + TABLES → crud.table/crud.tree/process.table pages; several CRUDs in tabs       [01][04][05]
10. MAIL + PDF TEMPLATES       → mail templates; PDF (pdfme) + the PDF→mail flow + its trigger        [15]
11. WORKFLOWS                  → BPMN user/service tasks + gateways; a worklist page per workflow     [07][05]
12. SCHEDULERS                 → cron → predicate → action rule                                       [12]
13. QUICK LINKS + FRONT DOOR   → sidebar links per page; home = dashboard or worklist                [17][21]
14. VALIDATE → VERIFY → PACK   → validate (0 errors) → crud verify --db → pack                        [tools]
```

> Steps 2→6 are the **data/logic backbone** (DB → CRUD → context → rules → roles); steps 7→9 are the **UI**
> (forms → form groups/actions → pages). Note a form/group owns **its own content page**: the **form page** and
> the group's **landing page** are authored in steps **7/8** (a form's `contentIdentifier` and a group's
> `contentPageIdentifier` must already exist before `form add`/`formgroup add`); step **9** is the **business/
> table** pages that host the crud tables. Steps 10→13 are the **cross-cutting features** (templates, workflows,
> schedulers, nav **+ the front door**). In **Scenario C** you run the same order, but only for the delta (see
> the addendum).

---

## Phase 0 — Detect the scenario, set global parameters

**Decide — which scenario are you in?** Run `python3 tools/mrjun.py inspect --project <dir>` first, then route:

| Signal (from `inspect` + files) | Scenario | What you do |
|---|---|---|
| Empty admin skeleton (the `empty.mrjun` shape: 0 cruds, 0 rules, no `dynamic-cruds.json`, empty business schema) + a **PRD** | **A — build from empty** | Author every phase 2→14 from the PRD. |
| Dump already has a **populated business schema** + UI (pages/forms/rules), but **no `dynamic-cruds.json`/source/paired queries** | **B — wire existing schema** | Skip DB authoring; wire dynamic CRUDs over the existing schema. Follow **[18](18-existing-schema-to-dynamic-wiring.md)** as the primary guide; use phases 3→14 for anything the wiring adds. |
| A **filled working dynamic project** (`dynamic-cruds.json` present, cruds+pages+forms populated) + a **change request** | **C — modify a filled project** | Do **not** rebuild. Run the **Scenario-C delta loop** (end of this doc): locate → decide the minimal delta → author only the delta through the relevant phases → re-validate. |

> Precondition for A/B/C alike: the **target tenant on the server** must be REPORT-typed (a **server-side** tenant property — there is **no `type` field in `tenant.json`**, so you cannot check it from the export; else import silently skips rep-objects + DB — [00](00-export-format-and-import.md)). **Base a brand-new build on the `empty` export**, which was created REPORT-typed.

**Decide — global parameters (write them down; every later phase reuses them):**

- **Project identity** — `tenant.json` `name` / `alias` / `domain` / `description`. Default: keep `empty`'s and change name/alias/domain to the PRD's product. (A/B only; C keeps them.)
- **Locales** — `tenant.json.locales`. ⚠️ **ELICIT this — ASK the user (AskUserQuestion), do not assume a default.** Which languages must the UI support? (`hy_AM`/`ru_RU`/`en_US` in any combination.) **Every** `localizedNames`/`localizedButtonNames`/nav-`localizedMap`/enum-`displayName`/column/action/field-label you author must cover **exactly** this set, each locale with its **own** translated value — **auto-translate never runs on import**, so blank or same-string-in-every-locale stays wrong (the #1 loc bug: an Armenian label copied into `en_US` shows Armenian under English). **If the user picks ONE language, author NO `localized:true` fields, NO entity `localize` jsonb, NO multi-key per-locale maps** — plain values only. Also elicit **which locale is the DEFAULT** (authoritative) — put it **first** in `locales` AND `mrjun.py locale set-default --locale <loc>` (it round-trips as `tenant.json.defaultLocale`; drives base-value writes + `locale fill`). Layer model + full export-key inventory + the nav/enum recipes → [20](20-localization.md).
- **Schema name** — one business schema (default `app_schema`, or a name from the PRD's domain, e.g. `customs_schema`, `billing_schema`). Scenario B/C: reuse the existing schema name (`db list-schemas`).
- **Alias convention** — one dynamic CRUD per entity. A `_cruid` suffix (`invoices_cruid`) is **one project's
  convention, not a platform rule**: other projects use **bare camelCase** aliases (`salesOrder`, `product`).
  For greenfield pick **one** convention and apply it to the alias **and every
  consumer** (rules, forms, tables, context). Scenario B/C: **reuse the exact aliases existing consumers already
  reference** — do not invent new ones ([18](18-existing-schema-to-dynamic-wiring.md) §4).
- **Context** — one context per project by default (Phase 4); pick its alias (default `<domain>_context`).
- **Branding / logo** — ⚠️ **ELICIT this too when the PRD implies any mail or PDF (notifications, printouts, reports).** Identify whose brand the output carries (from the PRD), source that LOGO, or ASK the user for it — with a neutral placeholder mark as the fallback. The logo is embedded in every mail + PDF template (Phase 10, [15](15-pdf-and-mail.md)); deciding it late means re-skinning every template. Record the logo source/asset.

**Done when:** scenario chosen; a one-screen "global parameters" block written (project id, **locales**,
**branding/logo**, schema, context alias); the REPORT-typed base assured by building on `empty` (server-side; not
checkable from files). **The three high-blast-radius unknowns — the LANGUAGE SET, the BRANDING/logo, and the
SCOPE/depth — are ELICITED with AskUserQuestion up front, not assumed** (`system_prompt.txt` Operating Principle 1);
"ask *or* record an assumption" is NOT enough for these — a wrong locale set, a missing logo, or a wrong scope
each forces re-touching many downstream files. **The same round carries the CHART conversation, in this order:**
run Phase 1's two chart passes first (they need only the PRD and the DDL — no user input), then send **one**
AskUserQuestion carrying the locale/branding/scope items *and* the chart items: the charts you want to ADD beyond
the ones the spec names, and your objections to the ones it does name. The deadline is **before Phase 2 authoring
starts** — an objection that arrives once Phase 9 has wired five chart nodes costs a rebuild, so it gets waved
through ([22](22-charts-params-and-filters.md) "## 2A. The specified charts are a FLOOR — propose more, and
challenge the ones you were given"). For lower-stakes silences (e.g. an individual FK-vs-scalar) record
an explicit assumption. Then **decompose** into epics → stories → tasks before authoring ([26](26-orchestration-and-testing.md)).

---

## Phase 1 — Decompose the PRD into an entity inventory

The single most important planning artifact. **Decide** the full inventory *before* authoring anything, so the
downstream phases are mechanical. Read the PRD and extract, into a table you keep:

| PRD signal → | Platform entity → | Feeds phase |
|---|---|---|
| A business noun you store/list/edit ("orders", "counterparties", "consignments") | a **table** + a **dynamic CRUD** (alias `<entity>` per the Phase-0 convention) | 2, 3 |
| A **document** ("invoice", "sales order", "BOM") = a header with repeating **line items** | a **header table** + a **lines table** (FK to header) + a CRUD whose `create/update/delete` are **GROOVY** (header + delete-lines + per-line insert), delete cascades to lines | 2, 3, 7(list sub-grid) |
| A closed **status set** / lifecycle ("Draft→Posted→Cancelled") | a **CHECK constraint** on the status column + **lifecycle EXECUTION rules** (one per transition) surfaced as table **actions** | 2, 5, 8 |
| An enum / lookup ("unit of measure", "country") | a `lookup_*`/dimension table (or a code list) + an **enum dropdown** (snapshot or choices rule) | 2, 3, 7 |
| An **actor / persona / permission tier** ("admin", "clerk", "approver") | a **roleGroup** (+ assignment) + page/action **access** + `hasAnyRoleGroup` predicates | 6 |
| A noun that is **both a stored entity AND an actor** ("Doctor", "Agent" — appears in a managed list *and* performs role/row-gated actions) | its entity table **carries an identity link** (email/`user_id`) so per-row ownership predicates work (Phase 6) | 2, 6 |
| A **printout / report** ("print invoice", "packing slip") | a **PDF template** (pdfme, by `alias`) + an EXECUTION rule/action that calls `service.report.pdf.get.<alias>` | 10 |
| A **notification** ("email the customer", "notify on approval") | a **mail template** (exported) + a rule calling `service.notification.mail.*` | 10 |
| A **multi-step process with human hand-offs / approvals** | a **workflow** (BPMN: userTask/serviceTask/gateway) + **its worklist page — a `process.table.pluin` surfacing the instances, always, not "if the PRD asks"** ([07](07-workflows-and-tasks.md) "### Step 5 — the worklist page (NOT optional)") **+ a named STARTER** (Phase 1a: `FORM` / `SCHEDULER` / `CRUD METHOD` / `SERVICE TASK`) | 11, 13 |
| A **recurring / time-based job** ("nightly expiry check", "send reminders") | a **scheduler** (cron → predicate → action rule). ⛔ **If what the job produces is a CASE and not a message** ("escalate", "open a review", "raise an incident"), the action rule STARTS A WORKFLOW — that is a trigger row, not a mail ([27](27-event-driven-process-start.md)) | 12 (+ 11, 5) |
| A **dashboard / KPI / chart** | a `chart.js.plugin` node (config in `properties.Javascript`) — `$$()` data binding to query columns; **plus, always: query params + a `global.replacement` filter bar + ≥1 click-to-cross-filter chart + a palette read off the axis's meaning** | 9 ([22](22-charts-params-and-filters.md) "### 4.6 Designing the filter SET for a dashboard", §6.1) |
| A **custom component / widget** — needs a JS **library**, or must **call rules / business logic from JS**, or a bespoke interactive UI beyond the standard plugins | an `nct.html.plugin` with a **`studioModel`** project: libs (CDN or vendored) + isolated scripts using `ctx.callRule` / `ctx.callBl` + read-only `ctx.contextData` + per-theme CSS; page-level buttons via `ctx.breadcrumb`; vendor lib files via `tenant-files/studio/…` | 9 ([24](24-html-component-studio.md), [24a](24a-theming-and-dark-mode.md), [24b](24b-html-composition-and-plugin-tags.md), [24c](24c-html-data-tables-and-paging.md)) |
| The **navigation / information architecture** ("a section per module") | **pages** (one per entity, or several CRUDs grouped into **tabs** on one page) + **left-nav quick links** | 9, 13 |

**Decide, per entity:** its columns (name/type), PK strategy, which are FKs (business vs enum), its status set (if
any), whether it is a document (header+lines), its create/edit/lifecycle actions, whether it needs a form (non-
direct) or runs an action rule (direct), and which page/tab it lives on.

**⛔ A chart list in the spec is the FLOOR, not the scope.** Two passes, both against the inventory you just
wrote: **derive** further chart candidates (every status / type / owner / period / amount axis with rows behind
it is a question someone will ask), and **challenge** each chart the spec names for the contradictions it may
carry — an axis no column supports, a breakdown with one distinct value, two charts answering the same
question, a number no decision hangs on. Record kept / dropped / proposed **with the reason**, and put the
proposals *and* the objections to the user in the Phase-0 up-front round, not after the build. Derivation
method + the full contradiction list → [22](22-charts-params-and-filters.md) "## 2A. The specified charts are a
FLOOR — propose more, and challenge the ones you were given".

### Phase 1a — the TRIGGER inventory (what STARTS what; do it with the entity inventory)

The inventory above says what is stored and what steps run. Neither says **what begins them** — and the answer
an unasked question gets is always "a person on a screen", so a PRD full of nightly checks and threshold
escalations ships as a project where every process waits for a start form nobody was told to press. **A process
with no trigger is not a late defect; it is a build that does nothing.**

**Sweep the PRD a second time for every sentence whose actor is the SYSTEM** — "nightly", "every N minutes",
"at the configured interval", "at defined points", "at 50%/80%/100% of the window", "if no response within N
days", "N days before expiry", "when the balance falls below X", "as soon as a `<row>` is registered", "when
the status becomes X", "it escalates itself", "if the reviewer rejects, a correction case is opened".

⛔ **The densest triggers are usually NOT sentences — they are TABLE ROWS**, which a sentence-shaped sweep
walks straight past. Read the cells too: an SLA/clock table's **Escalation** column ("on expiry", "50% and
100% of the window", "chase, then escalate after N attempts"), a notification matrix's **event/trigger**
column ("deadline passed"), a use-case table whose **Trigger** row names a CONDITION rather than an intention
— read that row **before** the **Actor** column, not after it — and any acceptance criterion of the form "X
passes its deadline → …". A clock row with two escalation points is **two** trigger rows; a "chase, then
escalate after N attempts" cell is a **repeating** trigger that has to count its own attempts (Phase 2 owes it
the counter).

⚠️ **An Actor naming a human does not clear the row.** When the trigger is a state the system COMPUTES — a
field the PRD's own field table marks *Derived*, a threshold, a count over other records — the named human
cannot see it until something hands it to them: their click is the SECOND step, and the FIRST step (detect the
condition, open the work item) has no actor at all. A use case whose **Trigger** reads "the data shows X" and
whose subject is *Derived* is a trigger row with **PRODUCT = CASE**, however human its **Actor** column looks.
A gate on `Actor == "System"` walks straight past exactly these rows, which is why the **Trigger** column, not
the **Actor** column, is the test.

Each one is a row:

| Trigger row column | Fill it with |
|---|---|
| **What fires it** | a clock → **scheduler** (Phase 12) · a write → **CRUD GROOVY method** (Phase 3) · a step in a process already running → **service task** (Phase 11). "The user" is not an answer *here* — but it IS an answer that has to be written down somewhere, so it goes in the process inventory's own column below, never nowhere |
| **What it must read** | the tables/columns the condition is computed from (a date that has passed, a threshold, a status). Nothing is handed to a triggered rule: it fetches its own rows, so Phase 3 owes it a **candidate method** that returns exactly the rows to act on |
| **What it produces** | a **mail/notification** · a **row written** · **a CASE** (a process instance) · a combination. ⛔ Fill this from the use case that CONSUMES the condition, never from the detection sentence alone: a requirement that says *flag it* and a use case that says somebody then *refers / reviews / escalates* it are ONE row, and its product is the CASE. A flag nobody is handed is a column, not a product — that reading is what ships a `sendAlertToRoleGroup` where the PRD asked for a work item |
| **How often it may produce it** | once per subject ever · once per period · every time the condition holds. This is the **idempotency requirement**, and it is written down here or nowhere |

⛔ **A trigger whose product is a CASE is a WORKFLOW START, not a notification.** "Escalate to `<Role Group>`",
"open a review", "raise an incident", "hand it over for a decision" all mean a process instance somebody works
off a worklist — a mail is a copy of the news, not the work item. Such a row obliges, together: a **workflow**
with **no start form** (Phase 11), an **EXECUTION rule** that gathers the rows and calls
`service.workflow.start` (Phase 5), the **idempotency plumbing** that stops it re-opening the same case on
every tick — its **columns** in Phase 2, its **methods** in Phase 3 — a **process group** + a **worklist
page** so the case is visible at all (Phases 11, 9),
and the trigger object itself (Phase 12 for a clock). Recognition test, build order and the rule to copy →
[27](27-event-driven-process-start.md).

⚠️ **Words that read automatic and are not.** "Automatically routed to the right approver", "the system
calculates the total", "the case closes when the last task completes" describe what happens INSIDE a process
that something else started — they are gateway conditions and service tasks (Phase 11), not trigger rows. Only
a sentence about the BEGINNING of the work belongs in this inventory.

Carry the result into the process inventory as one column — **"what starts it"**, exactly one of
`START ACTION` / `DOCUMENT ACTION` / `SCHEDULER` / `CRUD METHOD` / `SERVICE TASK` — which Phase 11 turns into a
start shape.

⛔ **A blank row does not fall back to anything. It ships a process that CANNOT BE STARTED** — the BPMN
deploys, the worklist renders, the task buttons work, and the case list is empty forever. Nothing builds a
start form by default; nothing builds anything by default. `validate` now ERRORs on a workflow nothing starts,
which is this column, mechanised.

| Value | What it means | What you must then build |
|---|---|---|
| `START ACTION` | **a person opens the case itself** — the case IS the unit of work, there is no document before it | one entry in `userStartProcessActions` on the worklist's `process.table` (Phase 9), `direct:"off"` + a `formGroupIdentifier` for its start form, and a PREDICATE saying who may press it. ⛔ A `direct:"on"` start action starts the case with **no context data at all** |
| `DOCUMENT ACTION` | **a person acts on a business DOCUMENT and the case tracks it** — "the employee submits the request". The commonest case in a document-driven PRD, and the one most often left off this list because it feels like an ordinary CRUD action | the lifecycle EXECUTION rule behind that row action (Phase 5) calls `service.workflow.start` after it writes the status — plus the claim column that stops a second case (Phase 2) |
| `SCHEDULER` | a clock | Phase 12's schedule + the §5 idempotency plumbing, which is **mandatory** here |
| `CRUD METHOD` | a row was written | a GROOVY method on that CRUD (Phase 3) |
| `SERVICE TASK` | another process reached a step | `flowable:rule` on the task (Phase 11) |

Whatever the value, answer the third question too — **what invokes the thing you named?** A rule is code;
something has to run it. "An EXECUTION rule starts it" is not a design until you can name the scheduler, the
action or the task that fires that rule. `validate` ERRORs on a starter rule nothing references. Full decision
table, including what happens when two starters exist for one process →
[27](27-event-driven-process-start.md) §2.

### Phase 1b — the business pass (do this BEFORE Phase 2; it changes the schema)

The inventory above answers "what is stored". This pass answers "how is it worked", and it is what separates a
usable project from a screen-per-table dump. Write the answers down — they drive the CHECK constraints (Phase 2),
the predicates (Phase 5), the form split (Phase 8) and the tab layout (Phase 9).

Per entity:

- **Lifecycle.** List the states, and for each: who moves it in, who moves it out, what is FORBIDDEN while in it.
  Every state gets a row-action predicate and a CHECK-constraint value. **A state that no action reads and no
  report filters on is not a state — delete it.**
- **The way out of every locking state.** If a state hides edit/delete, name the action that releases it and who
  may press it. No answer = records will get stuck; design one or drop the state.
- **Who ELSE reads this state.** Walk the list before adding a value: CHECK constraint · every predicate
  comparing it · every enum/label map (node model **and** settings mirror) · every report/query/chart filtering
  on it · every printout that renders it. Missing the report is the expensive one — records vanish from totals
  with no error.
- **Entry points.** For each way the user reaches this entity's form (create, edit, an action on a row, a
  process start), say what it MEANS. Two entry points with different meanings = two forms behind a
  predicate→form mapping (Phase 8), not one compromise form. **And record what each entry point BINDS:** any action on a
  `crud.table`/`crud.tree` — create as well as row — opens the form in CRUD mode — the platform binds every control on it to
  that table's `contextIdentifier` + `crudAlias`, whatever `scope` you persist — while a workflow user task or a
  `process.table` start/global action opens it with no row at all. That one answer decides how Phase 7 authors
  the controls and how the Phase-5 rule reads them back ([02](02-form-controls-reference.md) §Where the value LANDS).
- **What the user should not have to retype.** Anything the system can already identify (an existing record, the
  current date, the logged-in actor, a value derivable from another field) is a default/prefill, not a mandatory
  input. Mandatory + then discarded is a defect.

Per workplace (this drives Phase 9's page/tab layout):

- **Name the workplace, then fill it.** "Register clerk", "approver's queue", "month-end close" — one page each,
  tabs inside it for the things that person touches in the same sitting (e.g. the document register and the
  approval queue over those same documents). Do NOT derive the page list from the table list.
- **Does this process exist in the business?** Only author a workflow for a hand-off that really happens. If you
  do, decide the fate of the equivalent direct action (remove / role-gate / knowingly leave it) — otherwise the
  route you built is skippable in one click and the approval is theatre.

**Scenario B/C:** the inventory is a **diff**, not a greenfield. `inspect` + `list cruds`/`list rules`/`tree`
first; write the inventory of *what already exists*, then mark only the **delta** the request adds/changes.

**Done when:** every PRD noun maps to a table+CRUD row; every PRD verb ("approve", "print", "email", "schedule")
maps to a rule/template/workflow/scheduler row; every actor maps to a roleGroup; the page/tab layout is sketched;
**every process row carries a starter** (`FORM` / `SCHEDULER` / `CRUD METHOD` / `SERVICE TASK`) **and every "the
system does X" sentence is a trigger row** naming what fires it, what it reads, what it produces and how often it
may produce it (Phase 1a);
**the spec's chart list has been read back against the inventory (kept / objected, each with its reason) and the
extra chart candidates are listed** ([22](22-charts-params-and-filters.md) §2A).
Nothing in the PRD is unmapped; nothing is invented that the PRD did not ask for — **charts are the one
exception, and only as a PROPOSAL: you may go beyond the list, you may not silently build past it.**

---

## Phase 2 — Database  → [10](10-database-management.md)

**Decide:**
- **New schema vs modify the dump.** A/greenfield: one new business schema. B/C: **add tables/columns to the
  existing dump**, never recreate it (`db list-schemas`/`list-tables`/`show` first). **Match the sibling style**
  in a filled dump — the two you will meet are: a **lightweight** style (`integer` + sequence PKs, statuses as
  FKs to dimension tables), and a **Hibernate/ERP** style (**uuid PK with no default**, app-set, +
  `creation_time`/`modification_time` `timestamptz NOT NULL` + `created_by`/`modified_by` + `company_id` +
  `custom_fields`/`localize` jsonb + a status **CHECK**). Identify the business schema by which schema the CRUDs'
  `sourceSchema` points at, **not by name** — a business schema is often named after an integration
  (`int_<realm>_<client>_<hash>`) and reads like plumbing.
- **One table per entity**; **separate lines table** per document (FK header_id, ON DELETE handled by the CRUD, Phase 3).
- **PK** — `uuid` via `gen_random_uuid()` (default; matches the dynamic write path) or `serial` sequence for simple lists.
- **Audit columns** — `creation_time`/`modification_time` (`timestamp`, defaulted by the CRUD `now()`); a
  `company_id` if single-company; `active boolean` for soft-deletable master data.
- **CHECK constraint for every status/enum set** — list the *exact* literal values a lifecycle method will
  write. This is the #1 real-row failure: a status literal outside the CHECK throws on the first row (Phase 3/14).
- **FK type** — business FK (→ a business table, surfaced nested in Phase 3) vs enum/lookup FK (→ a `lookup_*`
  table, surfaced flat). Add the FK + a supporting index.
- **NOT NULL / defaults** — mark columns the form will not submit (Phase 3 `update` must `COALESCE` them).
- **Columns the Phase-1a trigger rows need — decide them HERE, with the schema.** Every trigger whose product
  is a CASE carries its idempotency **in the DATA**. `service.workflow.list(...)` can ask whether a case
  exists, but only through a process table's **indexed** values — so it answers only when the table indexes
  the key you would search on, and it costs a query per trigger row. A claim column is exact, free and needs
  no table
  ([27](27-event-driven-process-start.md) §5). So the table owes each such trigger a **claim state or marker
  column** that one conditional UPDATE can flip (prefer one more literal in the status CHECK over a separate
  `case_opened boolean` — the state is the claim *and* the business meaning, [27](27-event-driven-process-start.md)
  §5.3), a **`<x>_process_identifier`** column to write the started process identifier back into (there is no
  read side; that column IS the answer for every later screen, rule and tick), and — for a trigger that may fire
  repeatedly on the same row (a chase, a reminder, "escalate after N attempts") — an **attempt counter + a
  last-attempt timestamp** the candidate query filters on. Keep them **out of `dtoFields`** (Phase 3): a marker
  there turns up as a checkbox on every generated form. Then seed them **consistently** in the demo rows below —
  a row seeded mid-flight needs its state, its identifier and its counter to agree.
- **⛔ Demo-grade seed rows — decide the ROW SHAPE here, with the schema, not the night before the demo.** The
  dump ships the rows every screen is judged on, so each listed table needs enough rows to page, and **every
  axis a filter or a chart will group by (status / type / owner / period) needs several distinct values with an
  UNEVEN spread plus a date column spanning several periods** — a one-value column is a dead filter (Phase 9)
  and a flat chart, and an empty table is a blank dashboard. Row-shape contract →
  [22](22-charts-params-and-filters.md) "### 2.6 The data a chart needs (demo-grade datasets)"; how the rows go
  into `project-db.dump` (per-table `rows[]`, **all values as strings**, `sequences[].lastValue` ≥ max id) →
  [10](10-database-management.md) "## Seeding demo-grade data into the dump". There is no `db seed` command —
  `db add-table` writes DDL + `columnTypes` only (`mrjun.py db --help`).

**Author:** `db add-schema`, `db add-table --column name:type[:pk][:notnull][:default=...]`, then hand-add
CHECK/UNIQUE/FK into `schema.checkConstraints[]`/`uniqueConstraints[]`/`foreignKeys[]` (see [10](10-database-management.md);
inspect with `db show <table>`). ⚠️ `db add-table` does **not** auto-generate a sequence or a `nextval`/
`gen_random_uuid()` default (pass `:default=…` for a literal DEFAULT) — for a working sequence PK you must
hand-add `DEFAULT nextval(...)` + a `sequences[]` entry (`lastValue`≥max id), or `gen_random_uuid()` / app-set
uuid, per the chosen style. Its type map turns the aliases `varchar`/`string` into `VARCHAR(255)`; **any other
type string goes into the DDL verbatim**, so pass the real SQL type when you need a length or precision
(`note:varchar(64)`, `amount:numeric(12,2)`) — but a spelling the map does not know also takes the fallback JDBC
code `12` (VARCHAR) in `columnTypes[]`, which is what seed rows bind on, so fix those by hand
([10](10-database-management.md)).

**Done when:** every inventory entity has a table; every document has a lines table + header FK; every status
column has a CHECK covering exactly the literals Phase 5 will write; audit/`company_id`/`active` columns decided;
**every Phase-1a trigger row whose product is a CASE has its claim/marker column, its `<x>_process_identifier`
write-back column and — if it may fire repeatedly on the same row — its attempt counter + last-attempt
timestamp, none of them in `dtoFields`** ([27](27-event-driven-process-start.md) §5);
`db show` on each table matches the intended shape; **every table a page will list or a chart will read carries
demo-grade rows in the dump** — enough to page, with a spread on every axis a filter/chart groups by
([22](22-charts-params-and-filters.md) "### 2.6 The data a chart needs (demo-grade datasets)",
[10](10-database-management.md) "## Seeding demo-grade data into the dump"). ⚠️ Not machine-checkable: `validate`
never looks at the *distribution* of `rows[]` — this is a review gate you apply by reading the seeded data.

---

## Phase 3 — Business logic: dynamic CRUD + methods  → [11](11-business-logic-dynamic-crud.md), [18](18-existing-schema-to-dynamic-wiring.md)

**Decide, per CRUD (alias `<entity>` per the Phase-0 convention — `_cruid` suffix optional, bare camelCase equally valid):**
- **The 7 standard methods** — `find` (GROOVY: `count()` + `findAll(filter)`, returns the map
  `[content,totalElements,totalPages,pageNumber]`), `findAll`/`count`/`get`/`create`/`update`/`delete`. Each SQL
  method needs a **paired query** named `crud_<alias>_<method>`.
- **SQL vs GROOVY per method.** Simple CRUD → SQL. **GROOVY** when a method orchestrates (document `create/
  update/delete` = header + `deleteLines` + per-line insert), or composes/branches.
- **FK surfacing in `findAll`/`get`.** Business FK → **nested** via the `__` alias (`j.id AS product__id` →
  `{product:{id,code,name}}`); enum/lookup FK → **flat** `lookup.code` (the enum constant). A dotted UI
  expression (`product.code`, `uom.symbol`) must be surfaced by `findAll`/the lines JSON, or it renders as a raw id.
- **Write mapping.** uuid PK `gen_random_uuid()`; timestamps `now()`; `company_id` from the single active
  company; enum via `(SELECT id FROM lookup_X WHERE code=:field)`; business FK via `:root__id`; `update` uses
  `COALESCE(:v, col)` for NOT NULL columns the form omits; defaults via `COALESCE`.
- **Delete** — soft (`UPDATE active=false`) for master data, hard `DELETE` for documents; documents **cascade to
  lines** (never a bare `DELETE FROM header`).
- **Lifecycle methods** — one SQL/GROOVY method per status transition (`post`, `cancel`, `approve`, `activate`…);
  every literal it writes is in the column's CHECK (Phase 2).
- **Trigger methods — one trio per Phase-1a trigger row whose product is a CASE**
  ([27](27-event-driven-process-start.md) §4.1, §5.3), over the Phase-2 columns above: a **candidate** method
  (`returnsArray:true`, paged on `:rowsInPage`/`:pageNumber`, whose WHERE already **excludes every row this
  sweep has acted on**); an atomic **claim** (`returnsArray:false` — ONE conditional
  `UPDATE … WHERE id = :id AND <the state is still the old one>` ending in `RETURNING *`, which answers a row
  Map when this tick won and Groovy `null` when somebody else already claimed it; **never the generated
  `update`**, which SETs every non-PK column and blanks the rest of the row); and a **write-back** method for
  the started process identifier. Author all three **before** the Phase-5 rule that calls them and before any
  scheduler that could run it ([27](27-event-driven-process-start.md) §3 step 5).
  ⚠️ Declare their **`parameters[]` by hand**: `crud add-method` writes `parameters: []`, and `validate` ERRORs
  on that only for GROOVY methods — an undeclared placeholder is never turned into a bind slot, so the literal
  `:id` is sent to PostgreSQL and only `crud verify --db` (Phase 14) or the live run ever says so.
- **`dtoFields`** from the columns — **minus the Phase-2 trigger plumbing** (claim marker,
  `<x>_process_identifier`, attempt counter), which is not a form field; **`filterFields`** for the columns the
  table filters on.

**Author:** `source add --dbtype POSTGRESQL …` (serializes to `POISTGRESQL`); `crud add … --scaffold-methods`
scaffolds the 7-method **skeleton** + paired query records + the GROOVY `find` — but the findAll/count/get/
create/update/delete SQL is **placeholder** (`<table>`, `(...)`, `SET …`) and the `id` param defaults to
`Integer`; you **MUST hand-fill every query's SQL** (and override to `String` for uuid PKs) per
[11](11-business-logic-dynamic-crud.md)/[18](18-existing-schema-to-dynamic-wiring.md) before validate/verify.
`crud add-method` for lifecycle/document-helper methods; `query add` for extras. Document create/update/delete
are **GROOVY** orchestrating SQL helpers (`createHeader`/`updateHeader`/`insertLine`/`deleteLines`/`_deleteHeader`,
each a SQL method + paired query). Scenario B: follow [18](18-existing-schema-to-dynamic-wiring.md)'s FK/enum/
single-company/document recipes exactly.

**Done when:** every table has a CRUD; every SQL method has a paired `crud_<alias>_<method>` query with real SQL;
every UI field expression you plan for Phase 7/9 is surfaced by `findAll`/`get`; every document `create/update`
orchestrates lines and `delete` cascades; lifecycle literals ⊆ CHECK sets; **every Phase-1a trigger row whose
product is a CASE has its trio — candidate, atomic claim (`RETURNING *`), write-back — with `parameters[]`
declared on each** ([27](27-event-driven-process-start.md) §4.1).

---

## Phase 4 — Context  → [08](08-groovy-rules-and-context.md)

**Decide:** one context per project (default; the alias from Phase 0). **Every crud alias used anywhere**
(tables, forms, controls, rules) must appear in the context's `crudAliases[]`. Multiple contexts only if the PRD
has isolated sub-apps.

**Author:** `context add --name … --alias <ctx> --crud <alias>…`; `context add-alias <ctx> <alias>…` as CRUDs
appear. Scenario C: **add the new alias to the existing context**, do not create a second context.

**Done when:** `list contexts` shows one context whose `crudAliases[]` is the exact set of all aliases in play;
`validate` reports no "crud alias not in any context".

---

## Phase 5 — Rules  → [08](08-groovy-rules-and-context.md), [09](09-groovy-hints-and-live-context.md), [16](16-groovy-service-api.md)

**Decide — one rule type per need** (`ruleType`/`executor`; every rule carries `contextIdentifiers=[<context>]`):

| Need | Type |
|---|---|
| Action visibility (per row / per button — **not** per column, which has no such hook), gateway branch, form-mapping selector (**incl. the trivial `return true` pass-through** that every simple Create/Edit→one-form mapping needs — **author it** on a greenfield build, don't assume it exists, [06](06-form-groups-and-mapping.md) step 0), choices filter, `hasAnyRoleGroup` gate | **PREDICATE** / GroovyPredicate |
| Lifecycle transition, `onBeforeStart`/`onBeforeComplete` of an action, dropdown **choices** source, service task, PDF/mail flow | **EXECUTION_RULE** / GroovyExecutionRule |
| **Starting a process from the system** — the body a scheduler tick / a CRUD GROOVY method / a service task runs to gather rows and call `service.workflow.start(...)` — the Phase-11 shape C of a process with no start form ([27](27-event-driven-process-start.md)) | **EXECUTION_RULE** / GroovyExecutionRule |
| **Rare:** complex validation whose error/warning text must be **computed at runtime** (`validation.addFieldError/addFieldWarning`) — wired on an action's `validationRuleIdentifiers` | **VALIDATION_RULE** / GroovyValidationRule |

> **Most validation is NOT a rule — a field validates ITSELF in its settings (Phase 7).** Basic
> `pattern`/`min`/`max`/mandatory plus **`conditionalValidations[]`** (a `{predicateIdentifier, severity
> ERROR|WARNING, localized message}`; predicate-**true = invalid**, field value = `v`; predicate usually from
> the built-in template catalog — `required`/`strRegex`/`numBetween`/`dateAfter`/…). The predicate can read
> *other* submitted fields, so **cross-field** checks live here too (validation runs on submit). Reach for a
> **VALIDATION_RULE** only when the logic is genuinely complex **and** the message depends on many things.

- **Explicit `return`** in predicate/execution bodies (the template collapses a bare value to `null`).
- ⛔ **A rule that STARTS a process is an EXECUTION_RULE — never a predicate.** `service.workflow.start(...)`
  is refused at runtime inside a PREDICATE and inside a VALIDATION_RULE with a named message (*they are
  evaluated for their answer and must not create work*), and `validate` ERRORs on the call in either type.
  So a scheduler's **gate** and the rule that **opens the case** are two objects, not one: PREDICATE decides,
  EXECUTION_RULE acts. Such a rule also runs **headless** — no row, no form, no `contextDataMap` — so it
  reads everything through `service.crud.<alias>.<m>(...)`; the gather → claim → shape → start → mark body,
  and the idempotency it must carry, are in [27](27-event-driven-process-start.md) §4–§5.
- Use the **verified** API surface (`context.<ctx>.<alias>.data.get()/put()`, `.service.<m>(…)`,
  `service.crud.<alias>.<m>(…)`, `context.data.getAttr/setAttr`, `context.currentData.get()`, `service.rule("Name")`,
  `service.security.hasAnyRoleGroup(…)`, `service.rimm.run([…])`, `service.report.pdf.*`, `service.notification.*`,
  `service.global.conversion.toSelectOptions(…)`) — full list [16](16-groovy-service-api.md). Never the stale
  `context.service.<alias>`.
- **Which of the two context reads a rule uses is decided by the ENTRY POINT, not by the rule.** Behind a
  crud-table/tree action the submitted form values are on the ROW (`context.<ctx>.<alias>.data.get()`); behind a
  workflow user task or a `process.table` start action they are in the attrs (`context.data.getAttr`); a form
  group wired to BOTH reads both, **attrs first**, via the `FORM` helper in
  [08](08-groovy-rules-and-context.md). `validate` ERRORs on a literal `getAttr("<field>")` in a rule reachable
  from a crud-table action whose own form carries that field (`_check_crud_action_form_values`); a read through a
  variable — the two-path helper — is deliberately not flagged.
- **Choices dropdown source:** an EXECUTION rule **or** an `enumValues` snapshot on the control (Phase 7) — a
  `dataClass`-only enum dropdown renders blank after import. A choices rule MUST **end by converting rows to option
  pairs**: dropdown → `return service.global.conversion.toSelectOptions(service.crud.<lookup>.findAll([:]),"<key>","<display>")`
  (`toSelectOptionsLocalized` when the display field is `localized:true`, else labels stick to the project's base
  locale); autocomplete → `toAutoCompleteOptions(list,"<display>")`. A **raw** `findAll`/`find` list → picker
  shows "No results found" + hides Show Nav (`validate` ERRORs). TRAP: the default multi-optional `findAll` with a
  PARTIAL map (e.g. `[active:"true"]`) → Postgres "could not determine data type of parameter $1"; use `findAll([:])`
  or the search pipeline. Searchable → the `acFindBy<X>Like` pipeline (Phase 7 / [02](02-form-controls-reference.md) §4a).
- Rules can be authored **just-in-time** during their consuming phase (a choices rule with its dropdown, a
  form-mapping predicate with its form group, **the start rule of a shape-C process with its workflow in Phase
  11/12**) — but they all live in `rep-objects.rules[]` and need the context.

**Author:** `rule add --name … --type <T> --context <ctx> --script @f`. Naming: keep it meaningful and
consistent (e.g. `<Crud> Action <Kind>` for generated action rules).

**Done when:** every action/lifecycle/choices/validation/visibility need has a rule of the right type with an
explicit `return`; **every Phase-1a trigger row whose product is a CASE has its start rule RECORDED IN THE
PLAN — author the body in Phase 11/12, after `workflow add` has minted the workflow identifier, the process
group exists and the Phase-3 claim methods are in place** ([27](27-event-driven-process-start.md) §3 build
order): that identifier is the FIRST ARGUMENT of `service.workflow.start`, so a start rule written *here* can
only quote one that does not exist yet — `validate` ERRORs on a literal matching no workflow, while a
placeholder held in a variable or a GString is skipped by that check and throws `workflow_not_found` on the
first live tick. **When it is written it is an EXECUTION_RULE — no PREDICATE anywhere calls
`service.workflow.start`**; every `hasAnyRoleGroup("X")` name is
recorded for **Phase 6** to create (a runtime name
lookup, so the 5↔6 authoring order is flexible); `validate` is clean on rule
references.

---

## Phase 6 — Role groups & page security  → [12](12-queries-sources-schedulers-and-rest.md), [01](01-content-model-and-pages.md)

**Decide:**
- **Role groups** — one per PRD actor/persona. Author each + a `userRoleGroupAssignment` so predicates resolve.
- **Page access** — decide **deliberately**, per page, from the PRD. `publicReadAccess`/`authenticatedUserAccess`
  are the load-bearing gate (a good default for business pages is authenticated-only:
  `publicReadAccess=false`, `authenticatedUserAccess=true`). ⚠️ **A page you never set is not private by
  default** — `publicReadAccess` defaults to `true` ([01](01-content-model-and-pages.md)), so an unset business
  page is reachable anonymously. Set the flags on every page you author, and re-check the ones you copied.
  ✅ **A page CAN be restricted to a business persona** — `roleGroupAccessors` is the knob, and membership IS
  checked against the user's resolved role groups ([01](01-content-model-and-pages.md)). "Back office only" is
  `publicReadAccess=false` + `authenticatedUserAccess=false` + `"<Back Office>": {"view": true}`.
  (`accessors` is the *other* map — the platform's fixed system permission roles `admin`, `nct_author`,
  `user_view`, `user_edit`, `report_*`, `source_*`, …; a project persona can never appear there.)
  The same map on a **component's** node hides one component on an otherwise shared page
  ([01](01-content-model-and-pages.md) §"Hidden content").
  ⚠️ It gates **rendering, not data**, and it fails open while membership is unresolvable — so it is one layer,
  not the gate. Keep the other three: **(1)** hide the quick link from non-members via the nav item's own
  `roleAccess` ([17](17-left-nav-quick-links.md)) — the URL stays reachable either way,
  **(2)** gate every action with a `hasAnyRoleGroup` PREDICATE (re-checked server-side — see below);
  ⚠️ smoke-test the group check on your platform first — it is resolved against the identity provider and
  every failure is swallowed into `false`, which hides the action from members too, silently
  ([24](24-html-component-studio.md) §9a, [04](04-crud-table-plugin.md) §"Who sees which rows"),
  **(3)** scope its fetch rule so a non-member sees **zero rows**. Treat (2)+(3) as the real gate.
- Pair **every** `hasAnyRoleGroup("X")` predicate (Phase 5) with roleGroup X + an assignment.
- **Row-level ownership** ("only the *assigned* doctor can complete", "a user edits only *their* orders") is
  **not** a roleGroup — `hasAnyRoleGroup` lets *any* member act on *any* row. Enforce it with a **PREDICATE that
  compares the row's owner to the current user**: the entity must carry an identity link (an owner/`created_by`/
  email column filled at create via `service.security.user()` — [16](16-groovy-service-api.md)), and the action's
  `predicateIdentifier` checks `context.<ctx>.<alias>.data.get().ownerEmail == service.security.user().email`
  (optionally AND `hasAnyRoleGroup`). This is a per-entity decision made in Phase 1 (see the noun-is-also-an-actor note).
  ✅ For CRUD table/tree actions this really is a gate, not decoration: the platform re-evaluates the action's
  visibility predicate **server-side at execution and again at form submit**, loading the predicate id from the
  saved CRUD settings (not from the request) and **failing closed** on any error — so a crafted or stale form URL
  for a hidden action is refused.
- ⛔ **Row VISIBILITY is a DIFFERENT mechanism from row ACTIONS.** An action predicate hides a *button*; it never
  removes a row from a list. The PRD sentence "*the clerk sees only their own, the manager sees all and can filter
  by clerk*" therefore needs **both**: the predicate above **and** server-side **row scoping in the fetch rule** —

  ```groovy
  // … the generated fetch rule's pagination + attrs forwarding stays exactly as it is …
  // then, LAST, the scope:
  if (!service.security.hasAnyRoleGroup("<Manager>")) {
      filter['ownerEmail'] = service.security.user().email   // a clerk: overwrite, never default
  }
  return service.crud.<alias>.find(filter)
  ```

  Three rules, all load-bearing: the scope is written **after** the forwarded filter values so a client-supplied
  value cannot widen it; the scoping column must be a **declared parameter in BOTH `findAll` and `count`**, or the
  key is silently dropped and the list returns everything ([04](04-crud-table-plugin.md) §"ANY filter key … is
  DECORATIVE until the SQL declares it"); and **never** fetch everything and hide rows in the browser. Same
  doctrine for a *column* the viewer may not see: drop the field in the rule's projection, don't hide the cell.
  Recipes: [04](04-crud-table-plugin.md) §"Who sees which rows", [24](24-html-component-studio.md) §9a.5.

**Author:** `rolegroup add --name … --role …` (⛔ `--role` here takes a **canonical platform role constant**, see
[12 §4.4](12-queries-sources-schedulers-and-rest.md) — a made-up value aborts the import);
`roleaccess set <page> --authenticated true --role "admin:*" --role "user_view:view"`, and for a persona
`roleaccess set <page> --public false --authenticated false --rolegroup "<Back Office>:view"` (⛔ `--role`
writes the SYSTEM-role map `accessors` and `--rolegroup` writes `roleGroupAccessors` — a persona name belongs
in the second, where it is checked against membership; see the Decide box above).

**Done when:** every actor has a roleGroup + assignment; every restricted page/action has the intended access;
no `hasAnyRoleGroup` references a missing roleGroup; and **every list whose PRD says "only their own" has the
scope written in its fetch rule AND the scoping column declared in `findAll` + `count`.**

---

## Phase 7 — Forms, fields, field types, dropdowns, events, validation, form settings, action buttons  → [02](02-form-controls-reference.md), [03](03-generate-fields-from-crud.md), [25](25-form-settings-validation-and-events.md), [14](14-plugin-catalog-all.md)

A **form** (`rep-objects.forms[]`) is a wrapper; its fields live in the content node it points at
(`contentIdentifier`). **Decide, per form:**

- **Which control per column data type:**

  | Column | Control plugin |
  |---|---|
  | short text | `dynaform.form.text.field.plugin` |
  | long text | `dynaform.form.textarea.field.plugin` |
  | number | text field with numeric type/pattern (see [02](02-form-controls-reference.md)) |
  | date / date range | `dynaform.form.datepicker.field.plugin` (between/range → [02](02-form-controls-reference.md)) |
  | FK / enum dropdown | `dynaform.form.rimm.drop.down.field.plugin` |
  | large lookup, type-ahead | `dynaform.form.rimm.autocomplete.field.plugin` |
  | hierarchical parent pick | `dynaform.form.tree.picker.plugin` |
  | file / image | `dynaform.form.file.upload.field.plugin` |
  | document line items (sub-grid) | `dynaform.form.list.field.plugin` + `dynaform.list.item.plugin` |
  | boolean | a **text** field with `dataClass` `java.lang.Boolean` (there is **no** checkbox plugin) |

- **Mapping (every control):** `scope`, `crudAlias`, `contextIdentifier`, `fieldExpression` (the column, or
  dotted `product.id` for an FK), `key`, `displayName`, `dataClass`. ⛔ **`scope` follows the form's ENTRY
  POINT (Phase 1b), not the field's nature.** A form opened from a `crud.table`/`crud.tree` ACTION runs in
  CRUD mode: the platform binds every control on it to that table's `contextIdentifier`+`crudAlias` whatever
  you persist, so author the whole form with the CRUD quartet — including transient inputs no column backs (a
  reason, a note), which ride in `crudDataMap[<alias>]` as extra keys nothing persists and which the action
  rule reads from the row. `CONTEXT`/`GLOBAL` are for forms opened with NO row — a workflow user task, a
  `process.table` start/global action (Phase 11) — where the value lives in the process attrs
  ([02](02-form-controls-reference.md) §Where the value LANDS).
- **Dropdown source:** a **choices** `ruleIdentifier` (EXECUTION rule) **or** an `enumValues` snapshot. An FK
  dropdown maps `fieldExpression="ref.id"`, `key="id"` and a choices rule over the referenced CRUD — **that rule
  MUST end in `service.global.conversion.toSelectOptions(list,"<key>","<display>")`** (`toSelectOptionsLocalized`
  for a localized display field; **autocomplete** → `toAutoCompleteOptions(list,"<display>")`); a raw `findAll`/`find`
  list renders "No results found" + hides Show Nav (`validate` ERRORs). For a **searchable** dropdown/autocomplete
  (`searchEnabled`) build the platform pipeline — per (crud, searchField `X`, `Cap(X)`=first-letter-upper): SQL
  `acFindAllBy<Cap(X)>Like` (single typed `:X`, `defaultValue ''`) + Groovy wrapper `acFindBy<Cap(X)>Like` + rule
  `RIMM_FILT_<alias>_<X>` ([02](02-form-controls-reference.md) §4a). An enum dropdown needs the snapshot or it
  renders blank after import. For a **status backed only by a CHECK**
  constraint (no lookup table, no Java enum — the common inline-status case), hand-build the `enumValues`
  snapshot from the CHECK literals (see [02](02-form-controls-reference.md)).
- **Field events** — `eventComponentMappings[]`: on a DOM `eventName` (a **free-text** field — use `change`),
  optionally run execution rules (**Execute Rules Before Refresh** — a multi-select of EXECUTION rules), then
  **refresh ONE target `IRefreshable` component by `componentIdentifier`** (matched against the `uniqueIdentifier`
  of any descendant of the same FormPlugin — a field, slot, column, label, or List, not only a sibling field);
  **several refresh targets = several mappings** (one target each). Use this for dependent dropdowns /
  recompute-on-change — the usual trick is to point at the dependent field's `gen_slot_*` so re-rendering the slot
  re-runs its choices rule. Full authoring flow + dependent-dropdown recipe: [25 §3](25-form-settings-validation-and-events.md);
  shape: [02](02-form-controls-reference.md) "`eventComponentMappings[]`". Most projects ship these empty and only
  a handful of forms per project carry a real `{eventName:"change", componentIdentifier:<uuid>}` mapping — so if you
  need a dependent dropdown you are usually authoring the first one in the project, from the doc, not copying one.
- **Validation — do it HERE, in the field's own settings (this is where MOST validation lives, not in a rule):**
  mandatory via `alwaysMandatory` + `mandatoryValidationMessages` (or `mandatoryPredicateIdentifier` for
  conditional-mandatory); and **`conditionalValidations[]`** — each `{predicateIdentifier, severity:ERROR|WARNING,
  validationMessages(localized)}`, predicate-**true = invalid** (field value = `v`). **There are NO
  `pattern`/`min`/`max`/`maxLength` settings keys** — those are the `strRegex`/`numBetween`/`strLenMax`/… entries
  of the **built-in template catalog** (`required`/`strRegex`/`numBetween`/`dateAfter`/`dateWithinDays`/…).
  *"Create Validation from Template"* generates a **`GroovyPredicate`** (NOT a validation rule) referenced by the
  entry — full generated Groovy bodies + params + the 10 regex presets + ERROR/WARNING: [25 §2](25-form-settings-validation-and-events.md)
  (ids also in [02](02-form-controls-reference.md), [08](08-groovy-rules-and-context.md)). A `conditionalValidations`
  predicate may read *other* submitted fields, so **cross-field** checks belong here too (validation runs on
  submit). `WARNING` = a yellow, acknowledgeable panel; `ERROR` blocks submit. Escalate to a form-level
  **Global Validation Rule** (below) **only** when the message must be computed at runtime or must land on
  *whichever* field is at fault ([25 §4.2](25-form-settings-validation-and-events.md)).
- **Other per-field flags** — `prohibitedPredicateIdentifier`, default value (static or EXECUTION rule),
  between/range, and **Info/help text** (`showInfo`+`infoText` → an optional `help_*` `nct.help.plugin` node beside
  the label rendering a click/hover **"?" tooltip** — author it when the PRD wants inline field guidance, and cover
  all locales). Columns → [03](03-generate-fields-from-crud.md); settings shapes → [02](02-form-controls-reference.md).
- **Form-level settings (on the `FormDto`, not the control)** — decide per form: **Hidden Content Configuration**
  (`hiddenConfigs[]` — a predicate **hides** whole content nodes by their `uniqueIdentifier`, predicate-true =
  HIDDEN; the form-level analogue of per-field prohibited — "hide the approval block until submitted"); **Global
  Validation Rules** (`validators[]` — form-level `VALIDATION_RULE`s that run on submit and can
  `validation.addFieldError(<control **name**>, msg)` onto *any* field — for cross-field/context errors without
  duplicating logic per field); **Allow Drafts** (`allowDrafts` — enable when the PRD implies the form can't be
  filled in one sitting: long intake, data fetched later, multi-day KYC). All three → [25 §4](25-form-settings-validation-and-events.md);
  schema → [06](06-form-groups-and-mapping.md). ⚠️ `actionValidators` is persisted but does **not** run at
  CRUD-form submit — per-action validation is the workflow user-task action's `validationRuleIdentifiers`
  ([07](07-workflows-and-tasks.md)).
- **Action buttons** — the form's **submit is built into the FormPlugin** (an action with `submitForm:true` +
  `localizedButtonNames`), **not a separate plugin**; a *filter* form's submit is `dynaform.filter.submit.button.plugin`;
  free-standing buttons use `action.button.plugin` ([14](14-plugin-catalog-all.md)).

**Author:** a form needs a **content page** to live on — `page add` its form page first (or reuse one) and pass
it as `form add --content <formPage> --formgroup … --context …` (the form's `contentIdentifier`); the controls
are children of that page. The fast path for the fields is **Generate Fields from CRUD**
([03](03-generate-fields-from-crud.md)) — it emits each label+field pair in the `<div class="mb-3">…</div>`
wrapper with dropdown/date/mandatory/prohibited/default/info columns (⚠️ the mandatory **red `*`** and the help **"?"**
are **slot-HTML content + a separate `nct.help.plugin` node**, NOT runtime effects of `alwaysMandatory`/help settings —
you must author them, see [03 §3](03-generate-fields-from-crud.md)); then `node patch-settings` for events/tuning.
Hand-author with `node add --plugin <control> --settings` otherwise.

**Done when:** every entity that needs a form has one; **every form's field subtree is anchored under a direct
child `nct.parsis.plugin` `identifier="form.parsis"`** (filter forms → `"filter.parsis"`) — otherwise the form
renders EMPTY (silent bug; `validate` now ERRORs — [03](03-generate-fields-from-crud.md)); every column has a
control of the right type with correct mapping; every dropdown has a working source (choices rule or snapshot);
dependent-field events are wired;
document forms have a `list.field` sub-grid whose columns are surfaced by `findAll` (Phase 3); **field
validations (mandatory / `conditionalValidations` from the template catalog) set per the PRD in the field
settings** — a form-level Global Validation Rule only where a runtime-computed message or "error on whichever field
is at fault" is truly needed; prohibited/default set per the PRD; **form-level Hidden Content / Global Validation /
Allow Drafts set where the PRD needs them** ([25](25-form-settings-validation-and-events.md)).

---

## Phase 8 — Form groups, predicate→form mapping, create/edit actions  → [06](06-form-groups-and-mapping.md), [04](04-crud-table-plugin.md)

**Decide:**
- **Direct vs non-direct action.** *Direct* (`direct:true`) = no form; the button runs `onBeforeCompleteRuleIdentifier`
  immediately (use for one-click lifecycle: post/approve/activate). *Non-direct* (`direct:false`) = opens a form
  via `formGroupIdentifier` (use for create/edit and any transition that needs input). **Each lifecycle verb is
  its own action** — a pure flip (cancel/complete/check-in) is `direct`; a transition needing input (reschedule →
  new slot) is non-direct with a form — each with its own visibility `predicateIdentifier`.
  ⛔ That non-direct form runs in CRUD mode — every control on it carries the CRUD quartet (Phase 7). The
  `onBeforeCompleteRuleIdentifier` therefore reads those values from the row, `context.<ctx>.<alias>.data.get()`;
  `context.data.getAttr(...)` is null on this path (a form group ALSO opened from a workflow task reads both,
  attrs first — Phase 5) and lets a `COALESCE` update keep the old value under a success
  toast ([02](02-form-controls-reference.md) §Where the value LANDS).
- **Create vs edit actions.** Create actions instantiate; edit/lifecycle actions operate on the selected row.
  Each action: `{id, localizedNames, localizedButtonNames, icon, direct, formGroupIdentifier,
  onBeforeStartRuleIdentifier?, onBeforeCompleteRuleIdentifier?, predicateIdentifier?, validationRuleIdentifiers?,
  submitForm?}` — `validationRuleIdentifiers` is where the rare Phase-5 VALIDATION_RULE attaches (most validation
  is per-field in Phase 7, not here). (dynamic
  tables typically emit only `id/localizedNames/localizedButtonNames/icon/direct/formGroupIdentifier/
  onBeforeCompleteRuleIdentifier` — [04](04-crud-table-plugin.md)).
- **Form group config** — `contextIdentifiers`, `contentPageIdentifier`, `formGroupsPageIdentifier`,
  `placeFormsNextToLanding` (forms as siblings of the landing on one level), and
  `predicateFormMapping.mapping[{predicateIdentifier, formIdentifier}]` — the predicate chooses which form renders
  (Create/Edit usually share one form behind a **True** predicate; add branches for role/state-specific forms).
- **Visibility predicate** — `predicateIdentifier` hides an action per row/role.

**Author:** a form group needs a **landing page** (`contentPageIdentifier`) — reuse the baseline shared
`landing` page (`ec99a5a0-…`, alias `landing`, already in `empty`; one landing serves all groups via `?group=`)
or `page add` a per-group one, and pass it as `formgroup add --content-page <landing> …`. Then `formgroup add`
+ `form add` — but **neither writes the mapping pair**; the landing shows "No
layout/form" until you **hand-add** the `{predicateIdentifier:<True/fork>, formIdentifier}` pair to **both**
copies (`formGroups[].predicateFormMapping.mapping` **and** `forms[].formGroup.…mapping`, kept identical) and set
the form page's `formModeIdentifier` == form id — full recipe & shape: [06](06-form-groups-and-mapping.md).
"Create Default Actions" (same doc) scaffolds the standard Create/Edit set + naming.

**Done when:** every CRUD that needs data entry has a form group with a True-branch mapping; every table's
create/edit/lifecycle actions are decided (direct vs non-direct) and point at a real formGroup/rule/predicate;
one-click lifecycle actions are `direct` with an `onBeforeComplete` rule; **every non-direct action's form
carries the CRUD quartet on every control, and its `onBeforeComplete` rule reads the submitted values from
`context.<ctx>.<alias>.data.get()`, never `context.data.getAttr("<field>")`** — `validate`
`_check_crud_action_form_values` reports 0 findings.

---

## Phase 9 — Pages, layout, tabs, tables  → [01](01-content-model-and-pages.md), [04](04-crud-table-plugin.md), [05](05-crud-tree-and-process-table.md), [14](14-plugin-catalog-all.md)

**Decide:**
- **Page granularity — by workplace, not by table.** Start from the Phase-1b workplace list: a page is "what one
  person does in one sitting", and its tabs are the things they touch while doing it (a register + the approval
  queue over the same documents; a catalogue + its price list). One `siteMapPage` per entity is the fallback when
  no grouping applies — not the default. Two tabs no single user ever opens together belong on two pages; two
  pages a user constantly flips between belong in one tab set. Follow the PRD's IA where it states one.
- **Table plugin per page:** `crud.table.plugin` (flat list) · `crud.tree.plugin` (self-parent hierarchy,
  `findByParent`/roots — [05](05-crud-tree-and-process-table.md)) · `process.table.pluin` (workflow instances,
  Phase 11). Config in `properties.model` **and** mirrored to `rep-objects.settings[]` (`type` =
  `CrudTable`/`CrudTree`/`ProcessTable`, joined by `setting.name == node.uniqueIdentifier`).
- **Table model** — `{crudAlias, contextIdentifier, rowsPerPage, columnSettings[], filterSettings[],
  createActions, editActions, findRuleIdentifier?, importSettings?}`. Pick displayed columns (`{id,
  localizedNames, fieldExpression, dataClass}`) and filter columns.
- **⛔ EVERY table gets a FILTER FORM above it — decide its filters when you decide the table, not later.**
  Applies to `crud.table.plugin`, `crud.tree.plugin` and `process.table.pluin`. Only two exemptions, and you
  must state which one you used in the build log: **(a)** the table holds fewer rows than one page, or
  **(b)** every candidate column is a *dead filter*. A column is dead when it has ONE distinct value across
  the seeded data (a flag that is true everywhere), when it is mostly NULL (>50%, so filtering returns almost
  nothing), or when its cardinality equals the row count (1:1 — that is a drill-down link, not a filter).
  **Choose 2-4 filters per table by inspecting the ACTUAL data distribution, never by reading the column
  list:** a low-cardinality column with an even spread → dropdown; a rare but meaningful flag → boolean
  dropdown (the filter package has no checkbox control); anything above ~30 distinct values → free-text
  contains; any table whose operators work a clock or a queue → a date range.
  **The two mechanisms are different and must not be blurred** — same node, same event, different sink:
  crud/tree needs a matching **SQL parameter in `findAll` AND `count`**, process table needs a matching
  **`{token}` in `filterExpression` plus an `indexSettings[]` entry**. Mechanics + every silent-no-op trap →
  [04 §Standalone Filter Form](04-crud-table-plugin.md), [05 §filterExpression](05-crud-tree-and-process-table.md).
- **⛔ ONE table per page — tabs are the only exception, and it covers ANY two tables.** Not just two
  `crud.table.plugin`: a crud-table beside a `process.table.pluin`, or a tree beside a table, is equally
  forbidden. Same-type pairs additionally *break* (shared type-scoped Settings panel + sync channel), but the
  rule is not about the collision — a page is one workplace answering one question, and two stacked grids make
  the reader work out which one they are reading. So: second table → **its own tab, or its own page**.
  `mrjun.py validate` ERRORs on both cases. ([14 §2.3](14-plugin-catalog-all.md))
- **Multiple tables in tabs (one page).** Use `nct.tab.plugin`: its `properties.tabModel` =
  `{"items":[{"id":"<uuid>","name":"Tab Title","order":N}], "size":"SMALL"}`. **Always author
  `"size":"SMALL"`** — omit it and you get `BIG` twice over (field initialiser `TabSize.BIG`,
  `TabModel.java` — omit the key and the bar renders BIG twice over: the field's own default is BIG **and** the
  getter coerces a null back to BIG, so there is no way to get SMALL except by writing it), which is a chunky bar
  eating vertical space above every grid. Use `BIG` only for 2-3 top-level *modes*, never for section switching.
  **For each item, create a child `nct.parsis.plugin` whose `identifier` EQUALS the item's `id`** — that
  **identity**, not child order, decides which content renders in which tab (`item.order` only sorts the tab
  headers; `TabPlugin.java`). Each such parsis holds exactly ONE table (with its own `model` + settings
  mirror). One tab per table. (Mechanism, code refs, `localizedMap.name` caption storage:
  [01](01-content-model-and-pages.md) "Tabs".)
- **Layout / access** — `nct.html.plugin` Bootstrap grid + `nct.parsis.plugin` content slots; page `roleAccess`
  from Phase 6; charts via `chart.js.plugin` (config in `properties.Javascript`) — full data-binding + query
  params + filter bar + click-to-cross-filter recipe → [22](22-charts-params-and-filters.md).
- **⛔ A dashboard is never a wall of static charts.** Every dashboard/KPI page ships **(a)** a filter bar — a
  `global.replacement.plugin` node over the params its charts declare (`GlobalReplacementPlugin`; **not**
  a `dynaform.filter.form`, which drives tables, not charts — [21](21-homepage-and-redirect.md)); choose the
  filter SET the way you choose table filters, from the real data distribution (2-4 axes: status / type / owner /
  period) → [22](22-charts-params-and-filters.md) "### 4.6 Designing the filter SET for a
  dashboard"; **(b)** at least one **click-to-cross-filter** chart, so clicking a category narrows the rest of
  the page (`GlobalReplacementPlugin` → `ParamsPanel.applyFilterFromChart`,
  [22](22-charts-params-and-filters.md) §5) — and when a click should leave this page for a detail screen
  instead, [22](22-charts-params-and-filters.md) "### 5.3 Click to drill to another PAGE (when cross-filter is
  not enough)"; **(c)** a **palette chosen from
  what the axis MEANS** — one fixed hue per category reused by every chart on the page, a ramp for ordered
  magnitudes — never the library's default colour order ([22](22-charts-params-and-filters.md) §6.1). Whole
  page end-to-end: [22](22-charts-params-and-filters.md) "### Recipe E — a complete filterable dashboard page".
- **⛔ Before you write ONE line of CSS — or any `style=`, any HTML component, any chart CSS — read
  [24a](24a-theming-and-dark-mode.md).** A skin is a whole-stylesheet swap, there is **no theme class to select
  on**, and a screen that is perfect on the light skin can be white-on-white on the four dark ones. Neither
  import nor `validate` will tell you (the colour lint is a WARNING, it only reads an `nct.html.plugin`'s
  all-themes `css.byTheme["*"]` block, and it never looks at a chart's CSS at all).
- **A bespoke component** (needs a JS library, must call rules/BL from JS, a hand-built table, page-level
  buttons) → the HTML Component Studio: [24](24-html-component-studio.md) for the runtime and `ctx` surface,
  [24b](24b-html-composition-and-plugin-tags.md) for composing plugin tags inside your markup,
  [24c](24c-html-data-tables-and-paging.md) for anything that lists rows (⛔ hand-built tables must page on the
  **server** — the default temptation, `findAll` with `rowsInPage: 5000`, is what makes a demo-fast screen
  unusable on real data).

**Author:** `page add --parent root --name … --auth` (clones the layout scaffold), then **two commands per
table**: `node add --parent <slot> --plugin crud.table.plugin --name "<Screen>"` to place the node, then
`node set-model <node-id> --json @model.json` to write its config; `roleaccess set`. For tabs, add the
`nct.tab.plugin` node and one parsis+table per tab per the recipe above.

⛔ **Use `set-model`, do not hand-write the mirror.** Every table node needs a matching `rep-objects.settings[]`
entry, and **`node set-model`/`patch-model` create and update it for you** (correct `type`, `name` =
`node.uniqueIdentifier`, `content` as a JSON **object**). `node add --model` writes only `properties.model` and
leaves the mirror missing. Hand-rolling the mirror is how you get `content` as a *string*, which aborts the
whole REPORT import (Phase 14 ⛔) — so never author it by hand, and never "fix it up" afterwards: re-run
`set-model`.

**Done when:** every entity is reachable on a page with the right table type; **every authored CSS block and
every custom component was checked against [24a](24a-theming-and-dark-mode.md) and opened under at least one
dark skin as well as the light one** (a clean `validate` is not evidence — it never renders anything);
**every dashboard/KPI page carries a `global.replacement` filter bar over its charts' params, at least one
click-to-cross-filter chart, and a palette assigned by axis value rather than by series order**
([22](22-charts-params-and-filters.md) "### 4.6 Designing the filter SET for a dashboard", §6.1);
**every chart the spec named is either BUILT or carries a written objection with its evidence** (the missing
column, the distinct-value count, the chart it duplicates), **the extra candidates derived in Phase 1 each carry
a kept-or-dropped decision in writing, and the proposal list has actually been put to the user** — a dashboard
that only renders what it was handed is NOT done ([22](22-charts-params-and-filters.md) §2A);
**every table has a filter form above it in its own rendered container (or a stated exemption), and every one
of its `filterKey`s is LIVE** —
for crud/tree that means the key is declared as a parameter AND used in a `:name` predicate in **both**
`findAll` and `count`; for a process table it means the key appears as a `{token}` in `filterExpression` AND
its left-hand identifier exists in `indexSettings[]`; tables carry the correct
`crudAlias`+`contextIdentifier`, columns, filters, and Phase-8 actions; **every new table node has a matching
`rep-objects.settings[]` entry with `content` as a JSON OBJECT** — which you get for free by configuring the
node with `node set-model`, and which `validate` ERRORs on when `content` is a string; **no page carries two
tables of ANY kind outside separate tabs** — count
`crud.table.plugin` + `crud.tree.plugin` + `process.table.pluin` per container, not per type; on tabbed pages
**each `tabModel.items[].id` equals the `identifier` of a child parsis holding that tab's table** and **every
`tabModel` carries `"size":"SMALL"`**; page access set.

> Machine gate: `mrjun.py validate` ERRORs on two tables sharing a container
> (`_check_one_table_plugin_per_page`, same-type *and* mixed-type). Do not hand-wave it — if a page needs a
> second table, that is a signal to split the workplace, not to stack.

> Machine gate (charts — partial, via the PLAN): give **every spec-named chart** a `build-plan/plan.json` item
> `{"kind":"chart","name":"<the chart node's name>","status":"done"}`. `coverage` indexes each `chart.js.plugin`
> by its node `name` (`coverage_cmds.py:92-95`) and **FAILS** the gate on a planned chart with no match
> (`:164`) — so a chart you quietly dropped cannot ship. A chart you **objected to and did not build** goes in
> as `"status":"deferred"`: coverage then WARNs `DEFERRED — planned but intentionally not built (recorded)`
> instead of failing (`:161-162`) — that is how an objection is recorded machine-readably. A chart you **added**
> beyond the spec is an ORPHAN (built, unplanned) until it gets a plan item of its own (`--show-orphans`,
> `:174-181`). What no tool can check — that the objection carries evidence, that the extra candidates were
> derived at all, and that the proposals reached the user — is a **review rule**, discharged in the build log.

---

## Phase 10 — Mail & PDF templates + the PDF→mail flow  → [15](15-pdf-and-mail.md)

**Decide:**
- **Recipient resolution (decide first).** For every "email/notify actor X", decide **how X's address is
  resolved**: an owner/`created_by` column filled at create (e.g. via `service.security.user().email`), an
  explicit recipient column, or a roleGroup lookup — and make sure the CRUD **stores and surfaces** it (a
  notification with no resolvable recipient is a silent no-op).
- **Mail templates** (exported to `rep-objects.mailTemplates[]`). One per PRD notification. Set `name`, `alias`
  (`^[a-z][a-zA-Z0-9]*$`, the Groovy handle), `subject`, `htmlContent` with `{{placeholder}}`s; placeholders are
  auto-scanned. The 5 templates already in the baseline (`Company Invitation`, `Event Reminder`,
  `Password Recovery`, `sendIntakeInit`, `User Registration`) are examples of the shape.
- **PDF templates** (**portable** — they ride in `rep-objects.pdfTemplates[]` and are created in the PDF service
  on import; the browser/REST authoring path is a non-portable one-off). For each PRD printout, **copy the closest
  of the 15 seed pdfme templates** in `pdftemplates/` (`01-invoice-classic` for an
  invoice, `07-packing-slip`, `02-quotation`, `10-delivery-note`, `03-receipt-thermal`, etc.) and rename its field
  `name`s to your placeholders — faster/richer than `scaffold` from blank. A pdfme template is
  `{basePdf, schemas:[[{name,type,position,width,height,content}…]]}` with `text`/`multiVariableText`/`image`/`table`
  fields. **For a printout that lists line items, pick a seed that HAS a `table` field** (invoice/quotation/
  packing-slip/delivery-note). Give it a stable `alias` and ship it with `mrjun.py pdftemplate add --alias <a>
  --name <s> --template @file.json` — it rides in `rep-objects.pdfTemplates[]` and is created in nct-pdf on
  import (the Groovy rule references the same alias). ⚠️ For a `multiVariableText` field the render-time `params` keys
  are the field's **inner `variables` names** (e.g. `invoiceNumber`, `customerName`), **not** the field `name`
  (`info`/`billTo`); for a `table` field pass a nested list of rows.
- **The flow** — an EXECUTION rule reads the row (`context.<ctx>.<alias>.data.get()`), calls
  `service.report.pdf.get.<alias>(fileName, params)` → `PdfReferenceDto`, then `service.notification.mail.*` to
  send it. **Decide the trigger:** a CRUD table/tree action-rule ([04](04-crud-table-plugin.md)), a workflow
  user/service-task rule ([07](07-workflows-and-tasks.md)), or a scheduler ([12](12-queries-sources-schedulers-and-rest.md)
  — headless: no `userId`, so `pdf.download` is skipped, use `get`+mail).

**Author:** `mailtemplate add --name … --subject … --html @body.html`; **PDF templates ARE portable in the
`.mrjun`** — `pdftemplate scaffold <alias> --out file.json --field …` writes a skeleton pdfme JSON to fill in, then
`pdftemplate add --alias <a> --name <s> --template @file.json` appends it to `rep-objects.pdfTemplates[]` (created
in nct-pdf automatically on import; a browser/REST load is only a one-off, non-portable path — [15](15-pdf-and-mail.md)).
Wire the trigger as a Phase-5 EXECUTION rule.

**Done when:** every PRD notification has an exported mail template with the right placeholders; every printout
has a PDF template in `rep-objects.pdfTemplates[]` (via `pdftemplate add`) with an `alias` + a triggering
rule/action; the PDF→mail rule uses the verified `service.report.pdf`/`service.notification.mail` surface.

---

## Phase 11 — Workflows, tasks, process tables  → [07](07-workflows-and-tasks.md), [05](05-crud-tree-and-process-table.md)

**Decide:**
- **Do you need a workflow?** ⚠️ **If the PRD DESCRIBES a process — names steps, hand-offs, approvals, a BPMN
  diagram, an intake→review→approve→notify chain — BUILD the workflow. Do NOT silently downgrade it to lifecycle
  actions** (Operating Principle 3; a process-heavy PRD that ships zero workflows is a defect). The "a status flip
  is simpler as a direct action (Phase 8)" shortcut applies **only** when the PRD itself has just a one-click state
  change with no described process — not when the PRD hands you a diagram or a step list. If the PRD's process uses
  a **boundary/timer** (e.g. "24 h before the deadline"), that ONE element is not modellable in BPMN here — realise
  it as a **scheduler** (Phase 12) and build the rest of the process as a real workflow; never drop the whole
  workflow because of one timer.
- ⛔ **What STARTS this process? — a forced decision, per workflow, BEFORE the BPMN.** Take the answer from the
  Phase-1a trigger inventory; do not let it default. Three shapes, and only the first two have a start form
  ([07](07-workflows-and-tasks.md) "the start shapes"):

  | Shape | What begins the case | What that obliges you to author |
  |---|---|---|
  | **A** | a start **FORM** whose fields are `scope: CRUD` — the intake CREATES the subject | the start form (Phase 7) + its form group (Phase 8) |
  | **B** | a start **FORM** that PICKS an existing subject (a `GLOBAL`-scope picker) | as A, **plus** the bind rule of the binding contract below |
  | **C** | **a RULE** — `service.workflow.start("<workflowIdentifier>", <document>[, opts])`, **no form at all** | an **EXECUTION rule** (Phase 5) + its trigger (a scheduler, Phase 12 · a CRUD GROOVY method, Phase 3 · a service task in another workflow) + an **idempotency guard** (Phase 3) + a **process group** and `owner`/`roleGroups`/`emails` so the case is findable + the worklist page below |

  **How to choose — one question:** at the moment the case begins, is a human doing something? **If the PRD
  names no click, no submit, no screen and no actor at that instant — a clock, a threshold, an arriving row,
  another process — it is shape C**, and a start form is the wrong answer however natural it looks. A workflow
  has exactly ONE starter: a start form *and* a rule that starts it is a contradiction, not belt-and-braces.
  Shape C is also the only shape whose case can be **invisible** (no group ⇒ excluded from every group-scoped
  worklist) and the only one that can open the **same case on every tick** — both are the author's job, and
  neither is caught offline. The whole chain, in build order, with the rule to copy and its live acceptance run
  → [27](27-event-driven-process-start.md).
- **BPMN shape** — `startEvent → (userTask | serviceTask | exclusiveGateway)* → endEvent` with `sequenceFlow`s.
  Every exclusive gateway = one conditional branch per outcome + **one unconditional fallback named in the
  gateway's `default`** + a **`name` on every branch**; a parallel gateway takes all branches and needs no
  predicates at all ([07](07-workflows-and-tasks.md) §4).
  `serviceTask` binds rules via `flowable:delegateExpression="\${ruleTask}"` + `flowable:rule="uuid,uuid"` (order =
  execution order). `userTask` binds forms/actions via `flowable:userActions="{escaped JSON ACTION}"` (same ACTION
  object as Phase 8). Conditional gateways carry `conditionExpression` predicates (written by hand).
- **The worklist page — NOT a decision, an obligation.** **Every** workflow you author gets its own page whose
  `process.table.pluin` surfaces that workflow's instances (config in `properties.model` + settings mirror
  `type:"ProcessTable"`; attach `processGroups`) — plus a filter form above it (Phase 9) and a quick link
  (Phase 13). The only thing you decide is *whose* queue it is and which columns/filters it shows. A workflow
  with no worklist is a process the user can start and never see again: the instance runs, the task sits in the
  engine, and nothing on any screen says so. Recipe → [07](07-workflows-and-tasks.md) "### Step 5 — the worklist
  page (NOT optional)".
- ⛔ **The binding contract — decide it BEFORE you author a single task.** Inside a running process nothing
  files a CRUD row, so anything that reaches its subject through `context.<ctx>.<alias>.data` reads empty
  there — or, when the starting document seeded that alias, reads the copy taken when the case OPENED and
  never refreshed, which is worse because it answers confidently ([07](07-workflows-and-tasks.md) §4 Rule 4).
  Either way **every offline gate stays green while the live run shows blank forms and "No X selected"**.
  Four decisions, all forced:
  1. the start form's picker is `scope: GLOBAL` with `fieldExpression == "<crudAlias>Id"` — the binding
     travels in the control's value, never in a start rule's `setAttr`;
  2. the first service task runs a **bind rule** that re-publishes that id and copies the record's display
     fields into GLOBAL attributes (only a service task's context result is persisted);
  3. every task form that shows or decides on an EXISTING record is GLOBAL-scope over those attributes — a CRUD-scoped form is only ever correct when the task CREATES the record. That holds even when the same form group is ALSO wired to a crud-table/tree row action (one decision offered from both the worklist and the table), which is normal: the persisted scope governs the TASK path — leave it GLOBAL or the task form renders blank — while the table path is force-bound to that table's CRUD whatever you wrote, so what changes there is the RULE: it reads **both** — attrs first, then `context.<ctx>.<alias>.data.get()` (the `FORM` helper in [08](08-groovy-rules-and-context.md));
  4. every rule resolves through the `_rid` chain and publishes the ids it creates; every gateway predicate
     reads the record back from the database.
  Full contract + the resolver → [07](07-workflows-and-tasks.md) "## What a process can see".

**Author:** `workflow add --name … --user-task "Step:FormGroup" --service-task "Recalc:Rule" --gateway "OK?"
--context <ctx>` scaffolds a chained, valid BPMN + `elements[]`; hand-edit the gateway split branches +
`conditionExpression` per [07](07-workflows-and-tasks.md).

⛔ **Two more objects this phase authors, and NEITHER has a `mrjun.py` command** — the Done-when below demands
both, so author them here ([27](27-event-driven-process-start.md) §3 steps 2–3 and its "🔧 Tooling" note):
- the **process group** — one hand-written `rep-objects.processGroups[]` entry whose `identifier` **you** mint
  (the usual rep-object envelope with `id: null` + `identifier`/`name`/`description`; exact shape at
  [27](27-event-driven-process-start.md) §3 step 2). Leave the worklist node's `processGroupIdentifier` blank
  and the plugin mints a group at RENDER time, under an identifier no rule can ever name — every rule-started
  case then files under no group and appears on no group-scoped worklist.
- the **worklist page** — built with **Phase 9's own commands**, not a new one: `page add --parent root --name
  "<Process> queue" --alias <process>-queue --auth` → `node add --plugin dynaform.filter.form.plugin` (the
  filter sibling goes BEFORE the table) → `node add --plugin process.table.pluin` → `node set-model` (this is
  what writes the `settings[]` mirror; `node add --model` does not) → `quicklink add` (Phase 13). Full command
  list → [07](07-workflows-and-tasks.md) "### Step 5 — the worklist page (NOT optional)".

**Done when:** each PRD process is a deployed-shaped workflow whose service tasks reference real rules and user
tasks reference real form groups; gateways have condition predicates **on every branch but the `default` one,
which is named in the gateway's `default` attribute and labelled like the rest**; **EVERY workflow has a NAMED STARTER —
shape A, B or C — matching its Phase-1a trigger row, and no workflow has two** (a shape-C workflow therefore has
no start form, and its EXECUTION start rule, trigger, idempotency guard, process group and `owner`/`roleGroups`/
`emails` all exist — [27](27-event-driven-process-start.md) §9); **EVERY workflow — not just the ones whose
PRD line says "worklist" — has a worklist page: a `process.table.pluin` on its own page, with a filter form above
it (Phase 9) and a left-nav quick link (Phase 13)** ([07](07-workflows-and-tasks.md) "### Step 5 — the worklist
page (NOT optional)").

⚠️ **Neither of those two obligations is enforced by `validate` — both are HAND COUNTS.** What the toolkit
actually checks is only the **reverse** direction of each: a process table whose `model.workflowIdentifier` is
missing from `rep-objects.workflows[]` WARNs ("the worklist renders EMPTY",
`validate_cmds.py::_check_process_table_workflow_exists`), and **nothing flags a workflow with no worklist** —
so count them by hand: one worklist page per `rep-objects.workflows[]` entry.
⚠️ **And the STARTER — same story, worse consequence.** `validate` only checks the ARGUMENT of a
`service.workflow.start` call that is **already there** (`validate_cmds.py::_check_rule_workflow_start_targets`
— it resolves the literal identifier against `workflows[]`); nothing checks that a workflow has anyone to start
it, and there is no `_check_workflow_has_starter`. So count this one by hand too: `service.workflow.start(`
must occur in `rep-objects.rules[]` at least as many times as your Phase-1a inventory has **shape-C** rows, and
every shape-A/B workflow must have a start form group. **Zero start calls in a project whose inventory carries a
shape-C row is precisely the defect this phase exists to prevent** — the workflows import, `validate` comes back
green, every page renders, and nothing ever opens a case.
⛔ **`validate` must report ZERO process-context findings** (`_check_process_context_binding`): no
workflow-reachable rule resolving only through the crud context, no process form group with CRUD-scoped
read-only fields, no CRUD-scoped process-table COLUMN over an alias nothing seeded, no binding published
only by a start rule. (A `scope: CRUD` column renders exactly what the process's own context-data document
carries at `contextDataMap[<ctx>].crudDataMap[<alias>]` — so it carries nothing only when the START seeded no
entry for that alias: a picker start form (shape B), or a rule-started case whose document omitted it. A
shape-A start form seeds it from its own CRUD-scoped controls, and a seeded shape-C document seeds it too;
both render. Prefer `GLOBAL`/`CONTEXT` anyway: what a CRUD column shows is the start document's SNAPSHOT — the
plugin reads the process, never the table — so it stops agreeing with the row the moment anything updates the
row without writing the document back. An **index** is judged more strictly and ZERO is not reachable on a
shape-C project: a rule-started case passes no index settings at all, so a CRUD-scoped index over an alias only
a start RULE seeds still warns, correctly — re-scope that index to `GLOBAL` over an attribute a serviceTask
publishes rather than trying to silence it.)
Each finding is one blank screen or one step that throws on the first live run — and nothing else in the
build will tell you, because the artefact imports and every page renders.
⛔ **Every `elements[].settings.type` is a real `BpmnTaskType`** (`bpmn:StartEvent|Task|
UserTask|ServiceTask|…Gateway|CallActivity|SequenceFlow|SubProcess` — [07](07-workflows-and-tasks.md)): **end
events are `bpmn:Task`, and there is NO `bpmn:BoundaryEvent`/`bpmn:EndEvent`** — a boundary/timer event (or any
non-enum type) in `elements[]` aborts the WHOLE rep-objects import (Jackson `InvalidFormatException` → "No source
selected", DB not restored, empty context). `validate` ERRORs on it; **also do a live import + read `log/ui.log`**,
because a green `validate` is not import-proof (validate does not deserialize into the platform DTOs — Phase 14).

---

## Phase 12 — Schedulers  → [12](12-queries-sources-schedulers-and-rest.md)

**Decide:**
- **Which recurring jobs does the PRD imply?** Expiry checks, reminders, periodic recomputation, digest emails,
  **and the escalations that OPEN A CASE** — take them from the Phase-1a trigger inventory, not from a fresh
  reading of the PRD.
- A scheduler's model is **cron → check predicate → run action rule** (+ optional `cooldownJob`). It has **no**
  `queryIdentifier` — it can only run a **rule**. So each scheduler = a `job.expression` + an optional
  `predicateIdentifier` gate + `actionType:RUN_RULE` + an `actionRuleIdentifier` (an EXECUTION rule from Phase 5
  that does the work; it runs **headless** — no row context — so it loads its own rows via
  `service.crud.<alias>.find(...)`, e.g. find-expiring → send mail). ⚠️ the field is **`actionRuleIdentifier`**,
  not `ruleIdentifier` (which the platform's own obsolete doc used and does not deserialize — a scheduler with
  `ruleIdentifier` fires but runs nothing).
- **`job.expression` is a Spring 6-field cron** (`sec min hour dom mon dow`), parsed by Spring `CronTrigger` —
  use `*` and named days (`MON-FRI`), **not** Quartz `?`/`L` (they fail — and Quartz-style examples circulate, so
  double-check any cron you copy). Prefer a full literal `job.expression` with `cronType=null` over a `CronType` preset
  (presets are a wildcarded UI convenience).
- **A blank `predicateIdentifier` defaults to TRUE** — the action then fires on **every** tick (gated only by
  `cooldownJob`). Set a predicate to gate it. `cooldownJob.expression` is itself a cron: after a fire, the next
  run is blocked until that cron's next fire time (it is a timestamp, not a duration; blank ⇒ no cooldown).
  It is a mute on the whole SCHEDULE, checked **before** the predicate — never a per-row duplicate guard.
  `enabled` must be `true` for the schedule to register on startup, which is exactly why you **ship it `false`**
  unless the trigger is meant to be live the instant the project is imported (see Author below).
- **Per-recipient digest?** For "email *each* X their own list" the single action rule must **fan out**:
  `service.crud.<recipient>.findAll(...).each { r -> def rows = service.crud.<entity>.find([ownerId:r.id, ...]);
  if (rows) service.notification.mail.<tmpl>([r.email as String], [...]) }` — one scheduler, one rule, N
  personalized mails. ⚠️ **the first argument is a LIST, even for one person.** `MailNotificationProxy` does
  `args[0] as List<String>`, and Groovy coerces a bare `String` to a list of its CHARACTERS
  (`"a@b.com" as List<String>` → `[a, @, b, ., c, o, m]`), so `mail.<tmpl>(r.email, …)` addresses seven junk
  recipients instead of one person — the coercion itself never complains, and neither does `validate`
  ([16](16-groovy-service-api.md) §2.5).
  A plain "find-all-matching → one blast" rule is the simpler single-message case.
- ⛔ **The action rule does not have to send mail — it may OPEN A CASE.** `find-expiring → send mail` is the
  simple product; the other is **find-expiring → `service.workflow.start(...)`**, which puts a work item on a
  worklist somebody actually clears (Phase 1a: "escalate", "open a review", "raise an incident"). Same object —
  an EXECUTION rule, headless — but it carries three obligations mail does not: it must **shape a context data
  document** for the process (keyed by context IDENTIFIER → crud ALIAS → `value`), it must pass a
  **`groupIdentifier`** and an `owner`/`roleGroups`/`emails` or the case is invisible, and it must **claim each
  row atomically** or it opens the same case on every tick — forever, with every screen still looking correct.
  Nothing offline sees any of the three. The whole chain, the rule to copy and its live acceptance run →
  [27](27-event-driven-process-start.md).

**Author:** shape per [12](12-queries-sources-schedulers-and-rest.md) §3 (`ScheduleDto`: `job{expression,
explanation,cronType}`, `predicateIdentifier`, `actionType:RUN_RULE`, `actionRuleIdentifier`, `cooldownJob`,
`enabled`). ⛔ **Ship it `enabled:false`** unless the trigger is meant to be live the instant the project is
imported: an imported `enabled:true` scheduler with a non-blank `job.expression` registers a live cron trigger
and starts firing its side-effecting action rule on the real project straight away — and the import clears the
cooldown first, so nothing holds that first tick back (`validate` WARNs on it —
[12](12-queries-sources-schedulers-and-rest.md) §3.3).
No `mrjun.py` command exists for schedulers yet — author the predicate/action rules with
`mrjun.py rule` first, then hand-author the `rep-objects.schedulers[]` entry (exports normally ship `schedulers: []`,
so there is nothing to copy — ground the shape in the doc's code refs), then `validate`.

**Done when:** **every Phase-1a trigger row whose PRODUCT column says CASE has a scheduler whose action rule
actually contains `service.workflow.start("<workflowIdentifier>", …)`** — an action rule that ends in
`service.notification.*` for such a row is the silent downgrade this phase exists to prevent, and it satisfies
every other clause below word for word; every recurring PRD job is a scheduler with a valid cron, an action rule
that exists, and (if conditional) a predicate; the action rule is an EXECUTION rule that performs the job; the
gate is a separate PREDICATE ending in an explicit `return <Boolean>` (a broken predicate closes the gate for
good, silently); `enabled` reflects a deliberate decision, not a copy-paste; **and any action rule that starts
a process carries its idempotency guard, its `groupIdentifier` and its visibility options** ([27](27-event-driven-process-start.md)
§5–§6).

---

## Phase 13 — Wire the front door: left-nav quick links + homepage  → [17](17-left-nav-quick-links.md), [21](21-homepage-and-redirect.md)

**Decide:** which pages/sections appear in the sidebar and under which groups, AND what the bare project URL
lands on. The left-nav that renders is the SHARED `Nct left nav` common virtual plugin (`branch.virtualPlugins[]`);
per-page `site.kicker.plugin` `left-nav` nodes are dead data (each has `linkContentIdentifier`→the shared node) —
`quicklink add` targets the shared node automatically (see [17](17-left-nav-quick-links.md)). The
`Home`/root page's `Redirect` decides the landing.

**The home-page ladder — walk it in order; there is no "decide it later" rung:**

1. **The case has chartable data** (any status / type / owner / period axis with rows behind it — the usual
   case) → **Home IS the chart dashboard**: author the `chart.js.plugin` nodes into **Home's own parsis** and
   leave `Redirect` empty, so the bare URL renders the cockpit with no redirect hop that can resolve to nothing.
   Like any dashboard it ships with its `global.replacement` filter bar and a click-to-cross-filter chart
   (Phase 9) — and, being a chart Home, **no table plugin of any kind** on it (`validate` WARNs on a page that
   is both charts and tables, `validate_cmds.py::_check_one_table_plugin_per_page`).
2. **A pure queue/workflow tool with nothing worth charting** → the **main process/worklist table page** is the
   front door: `page set-redirect --page root --to <worklist-alias>`. Do **not** instead drop a table onto Home —
   a table on a Home that redirects away never renders, and a chart Home carries no tables at all.
3. **Never an empty Home**, and in either rung the home page is **itself a quick link** so a user who navigates
   away can get back. Full mechanism, layout and the two failure modes →
   [21](21-homepage-and-redirect.md) "## Choosing the front door — chart dashboard or main worklist".

**Author:**
1. `quicklink add --page … --label … --group … --icon …` for every business page (applies to every populated
   left-nav node); `quicklink add-external` for external links. Do this **last** — `page add` regenerates page
   identifiers on rebuild, and links key on the target `identifier`, so a page rebuild invalidates earlier links.
   **Two links are easy to forget and both are mandatory: the HOME page itself** (`quicklink add --page Home …`
   — the resolver accepts any `siteMapPage`, the root included: `quicklink_cmds.py::_resolve_page` over
   `core.iter_nodes`, which yields the root first) **and each workflow's worklist page** (Phase 11).
2. **(ladder rung 2 only)** `page set-redirect --page root --to <landing-alias>` — point the root at the primary
   landing page. ⚠️ On **rung 1 you set no redirect at all**: Home hosts the charts, `Redirect` stays empty, and
   that is validate-clean — the empty-Home WARN fires only when Home is redirect-less **AND** carries no landing
   plugin (`chart.js.plugin` counts: `validate_cmds.py::_check_homepage_and_nav`).
   ⛔ **Never ship an empty Home** (doc 21): a blank root reads as "only the default menu,
   none of my links" because the platform management console is injected on every page while your pages live in
   `modelGroups` — redirecting to a real content page surfaces both. Remove any demo-leftover nav links
   (`quicklink rm --label …`) so the sidebar is your pages only.

**Done when:** every business page a user should reach is a quick link under a sensible group; `quicklink list`
shows one coherent tree; the root `Redirect` resolves to a landing page (rung 2) **or** Home's own parsis holds
the dashboard with `Redirect` empty (rung 1). `validate` now gates all three — it WARNs on an empty Home / an
unlinked business page and ERRORs on a dead redirect. Plus, by review — `validate` checks none of these three:
**the home page IS the chart dashboard whenever the case has chartable data** (rung 1 beats rung 2 by default);
**the home page is itself a quick link** (the reachability check skips the root node, so an unlinked Home is
silent); **every workflow's worklist page is a quick link** (Phase 11).

---

## Phase 14 — Validate, verify, LIVE-RUN, pack  → [tools/README.md](tools/README.md), [26](26-orchestration-and-testing.md), [18](18-existing-schema-to-dynamic-wiring.md)

> This is the WHOLE-PROJECT close-out. It does not replace per-module testing: you should have `validate`d each
> unit as you built it ([26](26-orchestration-and-testing.md) §4) — this phase is the final offline gate **plus the
> live run that actually proves it works.**

1. `mrjun.py validate --project <dir>` → **0 errors** (warnings about pre-existing platform orphans are ok). It
   also runs the schema-aware dynamic-CRUD checks (CHECK-literal coverage, field-expression coverage incl. list
   sub-grids, document-delete cascade, enum-snapshot, NOT NULL inserts).
   > **`validate` does NOT check** (verify these by hand — a green `validate` is not "correct"): workflow
   > `bpmnContent` internals (`flowable:rule`/`userActions.formGroupIdentifier`/`conditionExpression`/`contextIdentifiers`
   > UUIDs); the `formGroups[]`↔`forms[].formGroup` copy sync (it DOES **WARN** — not ERROR — on a dangling mapping
   > `predicateIdentifier`/`formIdentifier`, so treat those warnings as real on a greenfield build);
   > `formModeIdentifier` == form id; `service.actionId` predicate uuid == a real action id; context
   > `crudAliases[]` coverage of every `context.<alias>.<crudAlias>` a rule reads; dump-internal integrity
   > (columns/columnTypes length, sequence existence, `lastValue`≥max id). **On an automatic process start it
   > checks the wiring and nothing behind it:** it ERRORs on a PREDICATE/VALIDATION_RULE calling
   > `service.workflow.start`, on a literal `start("<id>")` naming no workflow, on a scheduler whose
   > predicate/action rule is the wrong type, on a bad cron and on a duplicate scheduler `name`, and WARNs on
   > `enabled:true` and on a not-deployed target — but it cannot see **whether the sweep opens a case per tick**,
   > whether a `groupIdentifier` was passed, or whether a single key inside the context data document is spelled
   > right (unknown keys are dropped in silence at runtime). Those are step 5's job
   > ([27](27-event-driven-process-start.md) §8). PREDICATE "no explicit return"
   > warnings are **hard errors** (fix each); EXECUTION "no return" warnings are advisory (fix only value-
   > returning ones — fetch/choices/`find`/`count`).
   >
   > ⚠️ **validate ≠ import-safe.** validate does not deserialize into the platform DTOs, so a rep-object with the
   > wrong JSON *type* (e.g. `settings[].content` as a string instead of an `ObjectNode` object — see
   > [00](00-export-format-and-import.md)/[04](04-crud-table-plugin.md)) can pass validate yet **abort the entire
   > REPORT-path import** with a Jackson `MismatchedInputException`. The symptom is data-shaped, not error-shaped,
   > and SCATTERED (one abort skips the whole block, so several things break at once): sources unsaved ("No source
   > selected"), the **context imported empty → rules fail `No CRUD found with alias X in context Y`**,
   > `project-db.dump` not restored (data/dates "gone"), while the dynamic-CRUD replay still runs. All at once ⇒
   > one abort, not three bugs — find the Jackson stack in `log/ui.log`. validate now ERRORs on `settings[].content`
   > as a string AND on any rep-object field that is a string where that field is an object/array elsewhere, but it
   > does not deserialize into the DTOs. If you hand-edited `rep-objects.json`, do a **live import smoke-test and
   > read `log/ui.log`** — or edit via `mrjun.py node set-model`/`patch-model`, which keep the mirror correct (object).
2. If you can reach the DB, `mrjun.py crud verify --db "<conninfo>"` — it runs **every SQL method against real
   (or seeded-fixture) rows** so CHECK/NOT NULL/FK actually fire (an empty-table smoke test hides them).
3. Eyeball the [13 §5](13-master-playbook-empty-to-dynamic-project.md) checklist (localization coverage, model
   vs settings, explicit `return`, `id=null`, typos, settings mirror).
4. `mrjun.py pack <dir> <out.mrjun>`.
5. ⚠️ **LIVE IMPORT + DRIVE THE UI — the real acceptance (REQUIRED; a green `validate` is not a deliverable).**
   Import into a REPORT tenant and drive it in order ([26](26-orchestration-and-testing.md) §5, [23](23-distribution-and-known-gaps.md) §2):
   **Home renders its front door** — the charts, not a blank shell — **and its filter bar re-runs them** (pick a
   value; then click a category and watch the rest of the page narrow, [22](22-charts-params-and-filters.md) §4, §5);
   **every workflow's worklist page lists its instances**; **every nav link resolves and shows in the SELECTED language**
   (switch the locale — the #1 loc bug hides here); **every list page loads** with real column values + Create/Edit
   buttons; **every form opens with all its fields** and each dropdown is populated (not "No results"/blank);
   create/edit/lifecycle actions save — **re-open the row and read the value back; a success toast is not
   evidence** ([26](26-orchestration-and-testing.md) §5 step 4); **every workflow starts** and its tasks fire; **mail + PDF render branded**;
   **every AUTOMATIC start opens exactly ONE case** — **Deploy the workflow in the BPMN editor first** (import
   ships every workflow un-deployed, so a rule-started chain throws `workflow_is_not_deployed` until someone
   presses it, and no screen says so), then run the action rule by hand and **run it AGAIN on the same data**: a
   second case for the same subject means the idempotency guard is missing or is not atomic, and this is the only
   test that exists for it — **and the case it opened is visible in its own worklist**, with populated columns, to
   a NON-admin, non-author member of the role group the call passed (every rule-started case grants the `admin`
   and `nct_author` roles unconditionally, so testing as one of those proves nothing; and a case filed under no
   group is excluded from a group-scoped worklist for everyone, silently)
   ([27](27-event-driven-process-start.md) §8.3);
   and **`log/ui.log` is clean** of Jackson `MismatchedInputException`/`InvalidFormatException` (the scattered,
   data-shaped import-aborts). Fix → re-pack → re-drive until clean. **If you have no live platform, say so and
   label the deliverable UNVERIFIED — never imply an un-driven build works.**
5b. ⚠️ **AFTER the import, run `mrjun.py livediff --db "<platform conninfo>" --tenant <alias>`.** It diffs what
   the platform actually stored against what you packed. Two real failure classes are invisible everywhere else and
   emit **no log line**: a symbolic layout anchor regenerated on a cloned page (the platform then builds a fresh
   EMPTY node under that name, renders it, and your subtree is an unrendered orphan → a BLANK page), and a
   rep-object that threw mid-`initAllObjects` (everything after it silently skipped while the import still reports
   DONE). `livediff` diffs the content tree for the first and prints the PACKED rep-object counts in
   `initAllObjects` order for the second — it cannot read live rep-objects, so compare those counts against the
   platform yourself; its exit code covers the content-tree checks only. Do this BEFORE you start clicking — it turns "the page is empty"
   from an hours-long hunt into a one-liner.
6. Tell the user what changed, which docs/commands you used, the validate/verify result, **and the live-run result
   (what you drove and observed)** — or that it is UNVERIFIED and why.

**Done when:** `validate` = 0 errors; **`mrjun.py coverage --plan build-plan/plan.json` PASSES** (every PRD item
built and marked done — the anti-skip gate, [26](26-orchestration-and-testing.md) §6a); `crud verify` (if DB
reachable) all green; **every per-locale map (`localizedNames`/`localizedButtonNames`/`localizedStringValue`/nav
`localizedMap`/enum `displayName`/validation-message maps) and every entity `localize` jsonb covers all
`tenant.json.locales` with DISTINCT per-locale values** (no auto-translate on import; single-language ⇒ none of
these exist — [20](20-localization.md)); **every automatic start was run TWICE live and produced exactly one
case, which its worklist shows to the people the PRD names** ([27](27-event-driven-process-start.md) §8.3);
**the LIVE run (step 5) is done and clean** — or the deliverable is explicitly marked UNVERIFIED; packed.

---

## Scenario-C addendum — modifying a filled project (the delta loop)

When the input is a working dynamic project (a `.mrjun` that already has `dynamic-cruds.json`, pages and forms)
plus a change request, do **not** run phases 2→14 greenfield. Run this loop:

1. **Locate.** `inspect`, `list cruds/rules/forms/formGroups/contexts`, `tree`, `find --plugin …`, `show …` to
   understand what exists and what the request touches. Read the actual current shapes (never assume).
2. **Decide the minimal delta.** Map the change request through Phase 1 into a *diff*: which tables/columns,
   CRUD methods, rules, forms, actions, pages/tabs, templates, workflows, schedulers must be **added or changed**
   — and nothing else.
3. **Apply the delta, in dependency order** (the same phase order): DB change → CRUD/method → **add-alias to the
   existing context** → rules → roles → forms/fields → form groups/actions → pages/tabs → templates → workflows →
   schedulers → nav. **Reuse** existing forms/rules/predicates/roleGroups where they already fit; keep existing
   `identifier`s stable (don't regenerate ids for untouched nodes).
4. **Re-validate** (Phase 14) — the whole project, not just the delta — then `crud verify` and `pack`.

**Golden rule for C:** the smallest change that satisfies the request. Adding an entity is a full mini-run of
phases 2→9 for that one entity; changing a rule/field is a one-node edit + re-validate. Never rebuild what you
were given.

---

_Companions: [13](13-master-playbook-empty-to-dynamic-project.md) (write order, dependency graph, golden thread,
pitfalls), [18](18-existing-schema-to-dynamic-wiring.md) (Scenario B in depth), `system_prompt.txt` (the
one-screen operating contract that points here)._
