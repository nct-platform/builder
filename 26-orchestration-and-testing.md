# 26 — Orchestration & testing (how NOT to finish a big PRD fast-and-shallow)

**Read this when the PRD is large** (many entities, forms, a workflow, dashboards, templates). It is the missing
half of [19-build-decision-procedure.md](19-build-decision-procedure.md): 19 says *what to decide, in what order*;
this doc says *how to work a big PRD without shipping bullshit* — decompose it, build **and test each small unit**,
integrate, and only call it done after a **live run**. It exists because the most common failure is finishing a
huge PRD too fast: authoring everything, running `validate` once, seeing green, and declaring victory — while the
imported project shows wrong-language menus, empty charts, a bare-`<div>` email, zero workflows, and a blank Home.

> **The one sentence.** `validate` proves the files are *shaped* right; it does **not** prove the project *works*.
> Depth over speed: decompose → build+test each module → integrate+re-test → **four offline gates green +
> a hand-over someone else can drive** → done. The live import and the UI drive are the USER's step, from the
> `test-scenarios.md` you ship beside the export — you are not given a platform and do not ask for one
> (`system_prompt.txt` OP 0/1).

---

## 1. Why fast-and-shallow happens (and the antidotes)

| Symptom the user sees | Root cause | Antidote (this doc) |
|---|---|---|
| Menu/labels in the wrong language | one string fanned across all locales; never viewed under each locale | §3 unit test "render under each locale"; [20](20-localization.md) |
| Empty charts / blank dashboard | chart query returns nothing / binding not wired; never opened | §5 live-drive; [22](22-charts-params-and-filters.md) §"eyeball" |
| Zero workflows for a process PRD | "a lifecycle is simpler than BPMN" used to skip the workflow | §2 inventory forces a workflow row per process; [07](07-workflows-and-tasks.md) |
| Bare/ugly mail & PDF | scaffold shipped as-is; no branding | §2 template rows carry a "branded, seed-quality" gate; [15](15-pdf-and-mail.md) |
| Home redirects to a blank shell | redirect target renders empty; never opened | §5 live-drive Home first; [21](21-homepage-and-redirect.md) |
| One import-abort hides 200 edits | whole project authored, validated once at the end | §4 build+validate **per module**, not once |
| "Done" that was never imported | `validate` green treated as the finish line | §5 — `validate` is one of FOUR gates, and the export must ship with a `test-scenarios.md` that says it was never run |
| White cards / unreadable text on the dark themes | a custom component's CSS was written once, against the light skin, and only ever looked at under that skin | §3 tier **T4b render under each SKIN**; [24a](24a-theming-and-dark-mode.md) |
| A custom screen that is fast on demo data and unusable on real data | a hand-built table fetched every row (`rowsInPage: 5000`) because paging was never decided | §2 inventory row per custom component names its page source; [24c](24c-html-data-tables-and-paging.md) |

The through-line: **too big a step between "I authored it" and "I checked it works".** Shrink the step.

---

## 2. Decompose the PRD (before authoring anything)

Phase 1 of [19](19-build-decision-procedure.md) already extracts the entity/actor/document/status/report/notify/
process **inventory**. Go one level further into a **task graph** you keep in a working folder (§6):

```
PRD
 └─ EPIC  (a coherent slice a user would name: "Intake & registration", "Directories", "Reporting")
     └─ USER STORY  ("As a clerk I register an incoming document and it gets a gapless code")
         └─ TASK  (a single buildable+testable unit, one row in plan.json)
```

A **TASK is the unit you build and test in one go.** Good task granularity — each maps to a phase in 19 and has
its own DONE gate:

- one **entity**: table + CHECK/FK + dynamic CRUD (7 methods) + paired queries  → test: `db show`, `validate`, `crud verify`
- one **form**: the 25-field intake form (fields, dropdowns, mandatory, events) → test: `validate` (parsis anchor, choices rules), open it live
- one **list page**: crud.table/tree + settings mirror + actions            → test: `validate` mirror, open it live, click Create/Edit
- one **workflow**: BPMN + service/user tasks + gateway + process table      → test: `validate` (BpmnTaskType/refs), start an instance live
- one **template**: a branded mail OR a branded pdfme PDF                     → test: `validate`, render it, eyeball branding/logo
- one **cross-cutting**: localization pass, nav+home, schedulers             → test: render under each locale; open Home; scheduler cron/enabled
- one **automatic start**: workflow (no start form) + process group + worklist page + candidate/claim/write-back methods + EXECUTION rule + trigger → test: run the action rule **twice** live — exactly ONE case, visible to a non-admin member of the role group passed ([27 §8.3](27-event-driven-process-start.md))

**Rules for the decomposition:**
1. **Nothing in the PRD is unmapped, nothing is invented.** Every noun→entity task, every verb→rule/workflow task,
   every "email/print"→template task, every actor→roleGroup, every "dashboard"→chart tasks, every "process"→a
   **workflow task** (do not drop it — Operating Principle 3). And **every Phase-1a trigger row**
   ([19](19-build-decision-procedure.md) "Phase 1a — the TRIGGER inventory") **→ its own task and its own
   `plan.json` row**: `kind:"scheduler"` (keyed by the scheduler `name`) for a clock, `kind:"rule"` (keyed by the
   rule `name`) for a write- or service-task-triggered start. Without that row a dropped trigger is invisible to
   the coverage gate (§6a) — the workflow exists, so `coverage` is green, and nothing ever starts it.
   ⛔ **A trigger row whose PRODUCT column ([19](19-build-decision-procedure.md) Phase 1a, "What it produces")
   says CASE needs THREE plan rows, not one** — the trigger (`kind:"scheduler"` or `kind:"rule"`), the
   **workflow** it opens (`kind:"workflow"`, keyed by the workflow `name`), and its **start rule** (`kind:"rule"`
   — the EXECUTION rule that calls `service.workflow.start`). One row buys you a scheduler and nothing more:
   `coverage` indexes schedulers by `name` alone (`addrep("schedulers", "scheduler", "name")`,
   [`tools/mrjunkit/coverage_cmds.py`](tools/mrjunkit/coverage_cmds.py) line 64) and never opens the object, so a
   scheduler that only sends mail resolves exactly as well as one that opens a case — and the downgrade 19
   forbids ("a trigger whose product is a CASE is a WORKFLOW START, not a notification") ships green. Three rows
   are what make the case machine-checkable.
   ⚠️ **That is also the gate's ceiling: three rows prove the three OBJECTS exist, not that they are wired.**
   No `plan.json` row can assert "this trigger's rule actually calls `service.workflow.start`" — the whole index
   is names (`_index`, [`coverage_cmds.py`](tools/mrjunkit/coverage_cmds.py)). Wiring is checked one
   level down, so the trigger row's `test:` clause must name those checks: `validate` errors on a
   `service.workflow.start("<literal>")` that matches no `workflows[]` identifier and on the same call inside a
   PREDICATE/VALIDATION_RULE (`_check_rule_workflow_start_targets`,
   [`tools/mrjunkit/validate_cmds.py`](tools/mrjunkit/validate_cmds.py)) — but it is silent
   about a rule that never calls `start` at all, so **grep the named rule's body for `service.workflow.start`
   before you mark the trigger row `done`**, and finish on the live run-twice test
   ([27 §8.3](27-event-driven-process-start.md)).
2. **Order by dependency** (the 19 build order): DB → CRUD → context → rules → roles → forms → groups → pages →
   templates → workflows → schedulers → nav/home. A task can't start before its inputs exist.
3. **Write the acceptance test for each task WHEN you write the task** (the "test:" clause above). A task without a
   defined test is not ready to build.
4. **Record it** (§6) so progress is visible and an interrupted build resumes without re-deriving the plan.

---

## 3. The per-task test (what "tested" means for each unit)

Five test tiers, cheapest first. A task is **DONE only when its tier applies and passes**:

| Tier | Tool | Catches | Cost |
|---|---|---|---|
| T1 offline **validate** | `mrjun.py validate` | shape (parsis anchors, mirror type, choices-rule sinks, BpmnTaskType, refs, cron) **plus two wiring classes no other offline tier sees**: process-context binding, and an action rule reading its own form's field with `getAttr` on a CRUD-table form | seconds |
| T2 **targeted structural** | `db show`, `jq`, `mrjun.py show/tree/list` | this unit's specifics: column count, FK surfaced, form has N fields, action points at a real formGroup | seconds |
| T3 **crud verify** — the only gate that RUNS the SQL (§3a: a throwaway Postgres is always obtainable) | `mrjun.py crud verify --db` | real-row failures: CHECK literal, NOT NULL, FK, no-op UPDATE, an unguarded param that nulls a column | a minute |
| T4 **render under each locale** | open the page/form once per `tenant.json.locales` | wrong-language labels (the #1 loc bug), blank enum options | manual |
| T4b **render under each SKIN** — *only for pages carrying authored CSS* | switch Settings → Appearance through all five skins on that page | white/near-invisible surfaces, hardcoded palettes, `h-100` blowing a card to a full viewport ([24a §9](24a-theming-and-dark-mode.md)) | manual, minutes |
| T5 **live drive** | import + click through | empty charts, blank Home, dead dropdown, form renders no fields, workflow won't start, un-branded mail, a breadcrumb action that draws nothing ([24 §7.5](24-html-component-studio.md)) | manual |

- **T1+T2 run per task, always** (offline, fast). Do them *before* moving to the next task — a green T1 on one small
  unit localizes any failure to that unit.
- ⛔ **If the project has a workflow, T1 is not "0 errors" — it is "0 errors AND 0 process-context findings".**
  `validate`'s `_check_process_context_binding` reports a failure class that no other tier sees before
  T5: inside a running process nothing files a CRUD row, so a rule/form/column that reaches its subject
  through `context.<ctx>.<alias>.data` is empty there. **That verdict is scoped to the process path** — on a
  form opened from a CRUD-table / CRUD-tree action that same read is the correct one (next bullet). The
  artefact imports, every page renders, the SQL is
  perfect — and the first live case shows blank forms, "No X selected", a gateway stuck on its default
  branch and a worklist of empty columns. Treat each finding as a blocker; the contract is in
  [07](07-workflows-and-tasks.md) "## What a process can see".
- ⛔ **A `_check_crud_action_form_values` ERROR is a blocker too** — the mirror image of the above, on the other
  entry point. A form opened from a `crud.table`/`crud.tree` action binds every control to that table's CRUD, so
  a rule reading its own form's field with `context.data.getAttr("<field>")` gets null on every submit: the crud
  method is handed `''`, `COALESCE` keeps the old value, the form redirects and the toast says success. It
  imports fine, renders fine, drives fine and changes nothing — the ONLY offline signal is this check
  ([02](02-form-controls-reference.md) §Where the value LANDS).
- **T4/T5 are behavioral** and cannot be skipped for the finish (§5). You can batch them per *module* rather than
  per task, but they MUST happen. `validate` (T1) is necessary, not sufficient — see [23](23-distribution-and-known-gaps.md) §4
  for the exact classes it can't catch (chart data-binding, workflow runtime, localized-data coverage, semantic
  rule logic).

**The independent re-check.** After a module is built, a *fresh* pass (a different subagent, or you re-reading from
scratch against the PRD) catches blind spots the generator+its own tests share ([19](19-build-decision-procedure.md)
Phase 14, [18](18-existing-schema-to-dynamic-wiring.md)). Ask it: "what did the PRD ask for that isn't here, and
what here renders wrong under a real run?"

### 3a. T3 for real — the disposable-Postgres SQL gate (`crud verify --db`)

**T3 is the only gate that EXECUTES the project's SQL.** T1/T2 read JSON and prove *shape*; `crud verify --db` runs
every SQL method of every dynamic CRUD against a real server — reads direct, writes inside `BEGIN … ROLLBACK`, and a
fixture row seeded from the CRUD's own `create` when the table is empty
([`tools/mrjunkit/crudverify_cmds.py`](tools/mrjunkit/crudverify_cmds.py) lines 150–177). It does **not** need the
platform running, so *"no DB was reachable"* is almost never true: a throwaway Postgres is four commands away.

> ⛔ **It shells out to the `psql` BINARY.** `crudverify_cmds.py:45` refuses before doing anything else —
> `` if not shutil.which("psql"): raise core.ToolError("psql not found on PATH (required for `crud verify --db`)") `` —
> and every statement runs as `subprocess.run(["psql", conninfo, "-q", "-v", "ON_ERROR_STOP=off", "-tAc", body])`
> (line 32). No driver, no libpq bindings: a program named `psql`, on PATH. That is the entire install requirement.

**Step 1 — a database you can throw away.** Any reachable Postgres: one the environment already runs, one the case
ships, or a fresh one. Verified from zero with:

```
docker run -d --rm --name pgprobe -e POSTGRES_PASSWORD=<password> -p 55432:5432 postgres:16-alpine
```

**Step 2 — the `psql` shim**, when no client is installed locally (the usual case — the container already has one).
Two lines put it on PATH:

```
printf '#!/bin/sh\nexec docker exec -i pgprobe psql "$@"\n' > "$BIN/psql" && chmod +x "$BIN/psql"
export PATH="$BIN:$PATH"          # $BIN = any scratch dir; `psql "<conninfo>" -tAc "select 1"` must now answer
```

> ⚠️ Two consequences of the shim, both bite exactly once. The conninfo is resolved **inside** the container, so
> `host=localhost` means *the container's own* server (the published port never enters the picture). And `-f <file>`
> is read **inside** the container — pipe SQL on **stdin** (`psql "<conninfo>" -q < load.sql`), never `-f /host/path`
> (verified: `psql: error: /host/path/load.sql: No such file or directory`).

**Step 3 — load the project's OWN schema and rows.** `project-db.dump` already holds everything: per table a `ddl`,
its `columns` and its `rows`; per schema the `foreignKeys` / `uniqueConstraints` / `checkConstraints` / `indexes` as
ready ALTER/CREATE statements ([10](10-database-management.md)). Emit them in this order — DDL, INSERTs, **then**
constraints — so you never have to topologically sort the FKs:

```python
# dump2sql.py — project-db.dump -> plain SQL on stdout;  python3 dump2sql.py <workdir>/project-db.dump <schema>
import json, sys
db = json.load(open(sys.argv[1])); want = sys.argv[2] if len(sys.argv) > 2 else None
lit = lambda v: "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"
for s in db.get("schemas", []):
    if (want and s["name"] != want) or not s.get("tables"):
        continue
    print('CREATE SCHEMA IF NOT EXISTS "%s";' % s["name"])
    for t in s["tables"]:
        print(t["ddl"].rstrip().rstrip(";") + ";")
    for t in s["tables"]:
        cols = t.get("columns") or []
        for r in t.get("rows") or []:
            print('INSERT INTO "%s"."%s" (%s) VALUES (%s);'
                  % (s["name"], t["name"], ",".join('"%s"' % c for c in cols),
                     ",".join(lit(r.get(c)) for c in cols)))
    for key in ("uniqueConstraints", "foreignKeys", "checkConstraints", "indexes"):
        for stmt in s.get(key) or []:
            print(stmt.rstrip().rstrip(";") + ";")
```

```
psql "host=localhost user=<user> password=<password> dbname=postgres" -q -c "CREATE DATABASE probe;"
python3 dump2sql.py <workdir>/project-db.dump <schema> > load.sql
psql "host=localhost user=<user> password=<password> dbname=probe" -q < load.sql 2>&1 | grep -i error   # expect: nothing
```

> ✅ **Free extra check.** That `grep` is the first thing that ever tests the shipped demo data against its own
> constraints: a seeded row that violates a CHECK/FK you added *later* fails **here**, not on the customer's import.
> ⛔ **The `2>&1` is load-bearing** — `psql` writes every `ERROR:` to **stderr**, and it does not stop on one
> (`ON_ERROR_STOP` is off by default), so a bare `| grep -i error` matches nothing no matter how broken the load
> is: a silent pass. Verified: `echo "SELECT no_such_fn();" | psql "<conninfo>" -q 2>/dev/null | grep -i error`
> → no match (exit 1); the same line with `2>&1` → `ERROR: function no_such_fn() does not exist`.

> ⚠️ **Load the ROWS, not just the DDL.** The verifier binds every FK-ish parameter to a **live id it reads out of
> the DB** (`SELECT id::text FROM <t> LIMIT 1`, line 64; consumed at lines 84–93). On an empty schema there are no
> ids, every FK param becomes `NULL`, and the run drowns in NOT NULL noise. Measured on one project, same commands,
> same build: **schema only → `OK: 53 FAIL: 70`**; **schema + rows → `OK: 108 FAIL: 15`**.

**Step 4 — run the gate.**

```
python3 tools/mrjun.py crud verify --db "host=localhost user=<user> password=<password> dbname=probe" \
        --project <workdir>              # --crud <alias>[,<alias>] narrows while you triage
                                         # --schema <name> if the dump carries more than one
```

```
crud verify @ host=localhost (schema <schema>)
  OK: 108   FAIL: 15   skipped(no seed row): 4
  x <alias>.findAll: invalid input syntax for type boolean: ""
  …
```

That `108 / 15 / 4` is a real run: 131 SQL methods over 12 CRUDs, of which 127 are **attempted** and 123 actually
reach the server (`_`-prefixed helpers are skipped by design before the loop, line 146 — they run through their
GROOVY caller; the 4 in the `skipped` counter are the `insertLine` methods, line 156). **All 15 triaged to the
verifier's own parameter substitution; none was a defect** — while the same gate, on the same project one edit
earlier, caught two that were **real**, of exactly the shape in the 🚨 row below.

> ⚠️ **Exit code is 1 on any FAIL** (line 189), substitution artifacts included. Do **not** wire this into an
> unattended gate the way you wire `validate` / `coverage` (§6a). It is a gate **you read**.

#### The triage — which failures are the verifier's guess, and which are yours

The verifier *fabricates* a value for every parameter (`val_for()`, lines 67–115) and string-replaces it into the
script (`subst()`, lines 117–127). It knows CHECK allowed-sets and FK targets, but it is still guessing — so **most
FAILs are its guess, not your SQL**. Classify every line before changing anything:

| Verifier says | What it actually did | Verdict | The one command that decides |
|---|---|---|---|
| `invalid input syntax for type boolean` (or `integer` / `numeric`) `: ""` | dropped a **typed** literal (`false`, `1`, `now()`, `'T'` — lines 102–114) into your `NULLIF(:p,'')` guard, so PG must coerce `''` to that type | **verifier substitution** | `psql "<c>" -tAc "SELECT NULLIF(false,'');"` → the same error; `psql "<c>" -tAc "SELECT COALESCE(CAST(NULLIF('false','') AS boolean), true);"` → `f`. The guard is fine. |
| `update or delete on table "<parent>" violates foreign key constraint … on table "<child>"` | ran your `delete` against the **first live row** (line 64) — a seeded parent that has children | **substitution** — real only if the UI truly offers Delete on a parent and nothing cascades or guards it | `psql "<c>" -tAc "SELECT count(*) FROM <schema>.<child> WHERE <fk> = (SELECT id FROM <schema>.<parent> LIMIT 1);"` → non-zero ⇒ it was the row choice |
| `duplicate key value violates unique constraint "<uq>"` on `create` | bound a **live** FK id (lines 84–93) plus a typed literal (`1`), reproducing a seeded row's unique pair | **substitution** — real only if two legitimate runtime calls can mint the same key with no next-value helper | re-run the INSERT as `BEGIN; … ROLLBACK;` with the colliding field set to a free value (`'999'`) → it inserts |
| `null value in column "<c>" … violates not-null constraint`, `<c>` a **mandatory FK on a `create`** | could not infer the param: a surfaced-FK param `<alias>__id` is looked up as column `<alias>_id` (lines 89–93), which misses whenever the FK column is named differently → falls through to `NULL` (line 115) | **substitution** — the statement fails **loudly**, nothing is corrupted; if anything is wrong it is the form (make the field mandatory), not the SQL | re-run with a live id **as a string** → it inserts. Confirm the miss with `mrjun.py db show <table>` — the FK column name won't match the param stem |
| `null value in column "<c>" … violates not-null constraint`, `<c>` written by an **UPDATE from a bare param** — `SET qty_col = qty_col + CAST(:qty AS numeric)` | bound `:qty` to `NULL` (it is not a column of the table) — precisely what the runtime does when the caller omits it | 🚨 **REAL DEFECT.** Params arrive as **strings**: absent/empty ⇒ the whole expression is NULL ⇒ the stored value is **wiped**. No offline gate can see this. | `jq -r '.cruds[]\|select(.alias=="<alias>").methods[]\|select(.methodName=="<m>").script' <workdir>/dynamic-cruds.json` — if the failing column's expression carries **no** `COALESCE(…, <fallback>)`, it is real |
| `skipped(no seed row): N` | `insertLine` always skips (it needs a parent header — line 156); anything else skips when the table has no live row **and** the CRUD has no `create` to seed from (line 176) | **neither** — *unproven* | load the rows (Step 3) and re-run; never read a skip as a pass |

**The fix for the real one** is the guard the same build already uses everywhere else — an absent delta becomes a no-op:

```sql
-- before: an omitted/empty :qty nulls the column for that row
SET qty_col = qty_col + CAST(:qty AS numeric)
-- after:
SET qty_col = qty_col + COALESCE(CAST(NULLIF(:qty,'') AS numeric), 0)
```

> 🔧 **The rule that resolves most FAILs: the platform binds every parameter as a STRING.** That is why the generated
> guards read `COALESCE(CAST(NULLIF(:p,'') AS <type>), <fallback>)`, and why a *typed* literal breaks them.
> **Before believing a failure, re-run the statement with string literals** — `'1'`, `'true'`, `''` for "not sent".
> If it passes, the defect was the verifier's substitution: its `val_for()` is the only place typed literals appear.

**What this gate proves:** every SQL method parses; its tables and columns exist; writes survive the real
CHECK / NOT NULL / UNIQUE / FK against seeded data; and any parameter reaching a NOT NULL column unguarded is named.
**What it does not prove:** GROOVY methods are **not executed at all** (no Groovy runtime — `crudverify_cmds.py:11`);
that the CRUD is wired to a page/rule/form and that the caller binds these parameters — it "proves the SQL is valid,
NOT that the executor binds it the same way" ([11](11-business-logic-dynamic-crud.md)); paging determinism
([24c](24c-html-data-tables-and-paging.md)); and anything behavioral. It sits **between** the offline gates (T1
`validate`, T2 `db show`/`jq`) and the live run (T4/T5, §5) and replaces neither end. Drop the container when done
(`docker rm -f pgprobe`).

---

## 4. The build loop (module by module — never all-then-validate)

```
for each MODULE (an epic's worth of tasks, in dependency order):
    for each TASK in the module:
        author it (mrjun.py command > hand-JSON)          # 19 + the pointed-to doc
        T1 validate  → 0 errors                            # fix before moving on
        T2 targeted structural check for this unit
    # module integration:
    T1 validate the WHOLE project (not just the delta)     # catches cross-unit breakage early
    T4 render the module's pages under each locale
    independent re-check the module vs the PRD             # §3
    mark this module's plan.json rows done; coverage --plan # §6a — gate: nothing in the module skipped
# whole-project acceptance:
    T3 crud verify --db  (§3a — spin up a throwaway PG; then TRIAGE every FAIL)
    mrjun.py coverage --plan build-plan/plan.json          # §6a — MUST pass: every PRD item built + done
    T5 write test-scenarios.md + the independent re-derivation  # §5 — the hand-over IS the finish line
    (the import + drive is the USER's step, from that file)
```

Why per-module validate matters: authoring 200 nodes then validating once means a single import-abort (a mis-typed
`settings.content`, a bad BpmnTaskType) surfaces as a scattered, data-shaped failure with no pointer to which edit
caused it ([23](23-distribution-and-known-gaps.md) §2). Validate after each unit and the blast radius is one unit.

---

## 5. The acceptance sweep — what the person who imports it drives, in this order

> **In support mode you can drive this sweep yourself.** A session connected to a live project adds a
> browser MCP server and works through the scenarios in a real browser, fixing what it finds over MCP —
> [28](28-support-mode-over-mcp.md) §8. The order below is still the order; the difference is only who is
> holding the mouse. ⛔ The login is not part of what you drive: the human authenticates, always (§8.2).

`validate` never imports; it does not deserialize into the platform DTOs, and no offline gate opens a page. So
the deliverable is proven by a live run — **but not by yours.** You do not have a platform and you do not ask
for one (the contract's Operating Principle 0); the person who ran you owns the project and drives it with the
`test-scenarios.md` you write. This section is therefore the SPEC for that file: the order below is the order
its scenarios must appear in, because it fails fast on the load-bearing screens. Anything you cannot prove
offline belongs here as a numbered scenario, phrased so someone who never read the PRD can execute it and tell
pass from fail ([23](23-distribution-and-known-gaps.md) §2 is the reference for what goes wrong at each step).

1. **Home / front door** — the bare project URL must render real content: the dashboard's charts are visible
   (not a blank shell, not a redirect to nothing). If Home IS the dashboard, prefer building the charts **into
   Home** over redirecting ([21](21-homepage-and-redirect.md)).
2. **Nav** — every quick link resolves, grouped correctly, and shows in the **currently selected language** — switch
   the UI locale and confirm labels change (the #1 localization bug hides here; [20](20-localization.md)).
3. **Every list page** — table loads rows; columns show surfaced values (not raw ids / blank); Create/Edit/lifecycle
   buttons appear with the right labels.
4. **Every form** — opens with ALL its fields (not a blank page = broken `form.parsis` anchor); each dropdown is
   populated (not "No results found" = raw-findAll choices rule; not blank = missing enum snapshot); submit saves.
   ⛔ For a form opened from a table/tree row action, "saves" means **re-open the row and read the value back** —
   a rule that reads its own form field with `getAttr` instead of `context.<ctx>.<alias>.data.get()` redirects,
   toasts success and changes nothing ([02](02-form-controls-reference.md) §Where the value LANDS).
5. **Every workflow** — start an instance; user-task actions and service-task rules fire; the process table lists it.
   A workflow with **no start form** is started by running its EXECUTION rule by hand instead, and must be run
   **twice**: still exactly ONE case, and it must be visible to someone who is not an admin/author
   ([27 §8.3](27-event-driven-process-start.md)).
6. **Templates** — trigger a mail and a PDF; they render branded (logo, layout), placeholders substituted.
7. **`log/ui.log`** — scan for the scattered import-aborts (Jackson `MismatchedInputException`/`InvalidFormatException`)
   that show as "No source selected" / empty context / "data gone" rather than a clean error.

Every one of the seven is a scenario in `test-scenarios.md`, with its expected result written down. Your own
finish line is the four offline gates (`validate`, `crud verify --db`, `coverage --plan`, the independent
acceptance re-derivation) plus this file — and the hand-over must say, in one unambiguous sentence, that the
export **has not been imported or run anywhere**. A build described as "done" that was never driven reads as
tested; a build described as "gated offline, not yet driven" sets the reader up to find, in twenty minutes,
exactly the layout, dropdown and locale faults the file gates structurally cannot see.

---

## 6. The working folder (task graph + per-module log)

Keep the plan and status OUTSIDE the export (never pollute the `.mrjun` workdir). Put it next to the workdir, e.g.
`<workdir>/../build-plan/`:

```
build-plan/
  inventory.md        # Phase-1 inventory (entities, actors, documents, statuses, reports, notifications, processes)
  plan.json           # the coverage ledger (below) — the single source of truth for progress
  modules/<epic>.md   # per-module spec + its T1..T5 test log + independent-recheck notes
  test-report.md      # the final live-run report (what was driven, what was seen, what was fixed)
```

Durable project knowledge — the domain model in the customer's words, the screen inventory, decisions and their
reasons, environment facts — belongs in `<workdir>-case/` (`mrjun.py case init` / `case add`,
[23](23-distribution-and-known-gaps.md) §1), not here and not in the library. Keep `build-plan/` for the plan
and the run log.

`plan.json` — the coverage ledger: one row per buildable unit (each a single testable claim, spec-driven style),
in the shape the enforcement gate (§6a) reads:

```json
{ "project": "<Project>", "locales": ["hy_AM","ru_RU","en_US"],
  "items": [
    { "id": "ent-incomingDocument", "kind": "entity", "alias": "incomingDocument",
      "deps": ["ent-counterparty","ent-orgUnit","ent-documentType"],
      "test": "validate; db show incoming_document; crud verify",
      "status": "done",
      "result": "0 errors; 25 cols; CHECK×6; live: register produced code Մ-08-26-1" },
    { "id": "wf-intake", "kind": "workflow", "name": "incoming-document-intake", "status": "todo",
      "test": "validate; start an instance live" },
    { "id": "req-defect-notify", "kind": "requirement", "selector": {"kind":"mailTemplate","key":"mailDefectSender"},
      "status": "done", "note": "PRD §10.5 — notify sender of a defect" }
  ] }
```

`kind` ∈ `entity form page rule workflow mailTemplate pdfTemplate roleGroup scheduler context dashboard chart
requirement`. `status` ∈ `done | todo | building | blocked | deferred`. It is deliberately **plain JSON**, not a
database — survives interruption, diffs cleanly, and the Workflow tool (§7) + the coverage gate (§6a) read/write
it. The `.claude` Task tools (TaskCreate/TaskUpdate) are a fine live progress mirror, but `plan.json` is the
durable, **machine-checked** record.

### 6a. The coverage GATE — enforcement, not a request (`mrjun.py coverage`)

Prose ("please decompose and test") does not stop a fast-and-shallow build — the previous contract already said
"validate + live-debug" and a huge PRD still shipped with wrong-language menus, zero workflows, and bare templates.
What stops it is a **machine check that fails**. `plan.json` is the *executable contract*
(spec-driven development: the spec constrains what counts as done; GitHub Spec Kit's "constitution" rejects
work that lowers coverage); `mrjun.py coverage` **enforces** it:

```
mrjun.py coverage --project <workdir> --plan build-plan/plan.json     # the gate: non-zero exit on any gap
mrjun.py coverage --project <workdir> --emit  > build-plan/plan.json  # bootstrap a skeleton from the build
mrjun.py coverage --project <workdir> --plan … --show-orphans         # built-but-unplanned (is the plan complete?)
```

It cross-checks every `plan.json` item against the actual `.mrjun`:
- **MISSING** (a planned entity/form/page/rule/**workflow**/template/role/scheduler/dashboard not in the build) &
  status ≠ `deferred` → **GATE FAIL** (non-zero exit). This is exactly what would have caught the "zero workflows"
  defect: a plan row `{kind:"workflow", …}` with no matching workflow **fails the build**.
  ⚠️ **`dashboard` and `chart` rows MUST carry an `alias` or a `name`** — a keyless one is satisfied by *any*
  chart anywhere in the build, and the `empty` baseline already ships demo dashboards holding dozens of charts,
  so a keyless row marked `done` passes on an untouched project. Key every chart/dashboard row to the page alias
  or chart name you actually authored.
  ⚠️ **The gate proves an object EXISTS; it never opens it.** Every kind is indexed by alias/name only
  (`_index`, [`tools/mrjunkit/coverage_cmds.py`](tools/mrjunkit/coverage_cmds.py)), so a scheduler
  that only sends mail satisfies a `kind:"scheduler"` row as fully as one that opens a case. Anything whose
  VALUE is its behaviour needs its products planned as their own rows too — a CASE-producing trigger owes the
  gate three (§2 rule 1) — and its behaviour checked by `validate` + the live run, in the row's `test:` clause.
- **PRESENT but status `todo`/`building`/`blocked`** → **GATE FAIL** (built but not tested/marked done — you must
  run its test and set `done`).
- **status `deferred`** (an explicit, recorded decision NOT to build, e.g. a class-IV item) → WARN, not a fail.
- **ORPHANS** (built but not in the plan) → info: either scope creep, or your plan is incomplete (platform-baseline
  admin pages/rules show here — plan only your own items).

**The rule:** the build is not "done" until `mrjun.py coverage --plan plan.json` **passes** (Phase 14 / §8). Derive
`plan.json` from the PRD (Phase 1) *before* authoring, set each row `done` only after its test (§3) passes, and run
the gate at every module boundary and at the end.

---

## 7. Orchestration — parallelism where it helps (and the honest limit)

A big PRD tempts you to "run 20 agents and build it all at once." **The build itself is largely sequential**: one
mutable workdir (`branches.json`, `rep-objects.json`, `project-db.dump`, `dynamic-cruds.json`), and concurrent
agents editing the same files corrupt each other. So parallelism is for the parts that DON'T share the workdir:

**Parallelise (safe, high value):**
- **Research fan-out** — mine shapes from the docs and from any unpacked project you already have before
  building (what a working crud.table model / workflow / branded template looks like). Independent reads.
- **Independent artifact generation** — a branded PDF JSON, a mail HTML, a chart config, a SQL method body: pure
  functions of a spec, generated in parallel, then inserted sequentially.
- **Per-module verification** — after building, fan out T4/T5-style checks and independent re-checks across modules.
- **The final adversarial audit** — several fresh agents each drive a slice and report defects.

**Do NOT parallelise:** concurrent `mrjun.py` edits to one project (they race on the JSON files). If you truly must
build independent sub-projects in parallel, give each its own workdir (or a git worktree) and merge — usually not
worth it for one `.mrjun`.

**The tool + a runnable harness.** Use the **Workflow tool** (deterministic `pipeline`/`parallel` over agents). A
ready, adaptable **Replit-style harness** ships at [`tools/workflows/build-project.workflow.js`](tools/workflows/build-project.workflow.js) —
run it with `Workflow({scriptPath:".../build-project.workflow.js", args:{prd, workdir, plan}})`. It IS the
decompose→build-each→test-each loop made runnable, mapping onto Replit's roles:
- **manager** = the script's deterministic control flow;
- **editor agents** = one Build-phase agent **per `plan.json` task** ("the smallest possible task each"), run
  **sequentially in dependency order**, each gated by `validate` before the next — because the workdir is shared,
  the Build phase does NOT parallelise (the honest limit above);
- **verifier** = the Verify phase (parallel independent re-checks) + the Gate phase (`coverage` + `validate`).

Adapt the task list / docs per your PRD; the harness prints the required live-run checklist at the end (it does not
itself drive the browser — §5). A typical shape (what the harness encodes):

```
phase 'Research'   : parallel readers → shapes for {db, cruds, forms/tables, rules, templates, workflow, charts}
phase 'Build'      : SEQUENTIAL (main loop): decompose → author module by module, T1/T2 each unit
phase 'Verify'     : parallel per-module T4 renders + independent re-checks; collect defects
phase 'Handover'   : test-scenarios.md + independent re-derivation (§5). The user imports and drives.
```

Prefer a declarative **generator** (a small Python script that turns one schema/spec into DB + CRUDs + queries, or
one field-list into a whole form subtree) over hundreds of hand edits — it is more consistent and re-runnable, and
its output still goes through the same T1..T5 gates.

### 7.1 Two layers — don't conflate them

Separate **COMPREHENSION** (understanding the platform codebase + these docs) from **BUILD ORCHESTRATION**
(decompose → author → test the `.mrjun`). Different problems, different tools:

| Layer | Problem | Tool |
|---|---|---|
| **Comprehension** | verify a mechanism across this library's ~30 cross-linked docs (and, *if* you have a platform checkout, its sources too): how locale resolves, how a plugin reads its config, which DTO a field maps to) — today done by grep + reading | a **knowledge graph** of the codebase & docs — **graphify** (see 7.2) |
| **Build orchestration** | turn one PRD into a tested `.mrjun`: decompose, author module-by-module, fan out research/verify | the **Workflow tool** + `plan.json` + the **coverage gate** (§2, §4, §6a, §7 above) |

### 7.2 graphify — adopt it for the comprehension layer

**graphify** (`github.com/Graphify-Labs/graphify`, Apache-2.0) is a Claude-Code **skill** that turns a codebase +
its docs / SQL schemas / PDFs into a **queryable knowledge graph** via deterministic tree-sitter AST parsing (no
vector store; every edge tagged EXTRACTED vs INFERRED). It is **worth adopting here** for exactly the pain the R&D
fan-out hits — traversing relationships instead of grepping.

**For you (the builder):** graph **this library** — `/graphify .` over the folder you were given — a concept map
of plugins, settings, cruds, rules and localization layers with its cross-references made traversable.

**For library maintainers only:** a second graph over the platform and CMS source trees, used to re-verify a
doc's claims against the code. That requires a platform checkout, which is **not** part of this library
([23](23-distribution-and-known-gaps.md) §1) — skip it.

**Bounds (be honest about what it does NOT do):** graphify does not author, `validate`, or import a `.mrjun`, and
it does not run the build. It is a *read/understand* accelerator. The **build+test loop stays the Workflow tool +
`plan.json`** (§4–§7). So: graphify for comprehension; do **not** try to make it the orchestrator.

**Install — via a checked-in script, never by hand** (honors "no manual installs"): run
[`tools/setup-graphify.sh`](tools/setup-graphify.sh). It **installs** the latest graphify (`uv`/`pipx`) and
registers the `/graphify` skill — it does **not** build any graph. Build the docs graph yourself, inside Claude
Code and from this folder: `/graphify .` (refresh it with `/graphify . --update`, not by re-running the script);
the platform-source graph above is maintainers-only, so skip it. The script is idempotent — re-run it only to
upgrade graphify. Pin the version it installed alongside the platform build pin
([23](23-distribution-and-known-gaps.md) §3).

**LangChain / a bespoke Neo4j graph DB: not recommended.** Orchestration is already covered by the Workflow tool
(deterministic pipeline/parallel/loops, no new runtime); a hand-rolled graph DB re-implements what graphify gives
for free. The toolkit stays **stdlib-only** ([23](23-distribution-and-known-gaps.md) §1) — graphify is an optional
*comprehension* aid installed out-of-band by the setup script, not a runtime dependency of `mrjun.py`.

---

## 8. Definition of done (the gate before you tell the user "done")

- [ ] Language set, branding/logo, and scope were **asked** up front (Operating Principle 1), not assumed.
- [ ] Every PRD noun/verb/actor/process/report/notification is a row in `plan.json` — **including a workflow for
      every multi-step process** and **branded templates for every notification/printout**.
- [ ] **`mrjun.py coverage --plan build-plan/plan.json` PASSES** (§6a) — no MISSING item, no item still
      `todo`/`building`/`blocked`; any `deferred` item is an explicit, stated decision. This is the machine gate
      that makes "nothing skipped" checkable, not hoped.
- [ ] **Every Phase-1a trigger whose PRODUCT is a CASE ends in `service.workflow.start`** — its three plan rows
      are there (trigger + workflow + start rule, §2 rule 1), the named rule's body really contains the call
      (`coverage` indexes names, it cannot see the call), and the rule carries its idempotency guard — a
      candidate filter, an atomic claim and a marker column — because nothing offline can run it twice for you.
      The run-twice test itself ("still exactly ONE case, visible to a non-admin") is scenario material for
      `test-scenarios.md` ([27 §8.3](27-event-driven-process-start.md)). A CASE row whose rule ends in
      `service.notification.*` is a downgrade, not a build.
- [ ] Each unit passed T1 (`validate` 0 errors) + T2; the whole project passes `validate`; **`crud verify --db` was
      run** against a throwaway Postgres (§3a — "no DB" is not an excuse) and **every remaining FAIL is triaged** to
      the verifier's own substitution, not left unread.
- [ ] Rendered under **each** `tenant.json.locales` — labels change with the locale (no one-language-under-all bug);
      a single-language project has **no** `localized` fields.
- [ ] **Written down for the tester, because no gate can reach it**: Home renders charts; nav resolves in the
      selected language; every form opens with fields + populated dropdowns; actions run; every writing row
      action submitted **and its row re-opened showing the new value** (a success toast is not evidence —
      §5 step 4); workflow starts run; mail/PDF render branded; `log/ui.log` clean. Each of these is a
      numbered scenario in `test-scenarios.md`, not something you tick off yourself.
- [ ] **Every workflow has an end-to-end scenario, one case per branch**, written for the tester: start it, and
      on EVERY user task read the form before pressing the button (a form whose fields are blank is a binding
      fault, not a data gap), and take each gateway branch at least once (a predicate that is silently false
      looks exactly like "the flow went that way"). `validate` must report 0 process-context findings before
      that scenario is worth anyone's time.
- [ ] An **independent re-check** found nothing missing vs the PRD.
- [ ] The user report states what was built, the result of each of the four offline gates, and — in one plain
      sentence — that the export has not been imported or run anywhere, pointing at `test-scenarios.md` for
      what to click first.

If any box is unchecked, it is **not done** — say what remains rather than implying completion.

---

_Companions: [19](19-build-decision-procedure.md) (the phase spine + DONE gates), [13](13-master-playbook-empty-to-dynamic-project.md)
(write order + checklist), [23](23-distribution-and-known-gaps.md) (the live-debug loop + what `validate` can't catch),
`system_prompt.txt` (Operating Principles 0–4)._
