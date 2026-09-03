# 27 · Process start — who opens the case, and what makes that run

> **Scope.** The whole chain behind a PRD sentence like *"chase unanswered requests and escalate after three
> days"*: how to RECOGNISE that nobody presses anything, which of the three headless triggers to use, the order
> the objects must be built in, the EXECUTION rule that gathers rows from business logic, shapes them into a
> context data document and calls `service.workflow.start`, how to stop it opening the same case on every tick,
> how to make the case findable, and how to verify a chain that nothing offline can run.
> **Not here:** BPMN grammar, task types, the worklist page and the process binding contract →
> [07](07-workflows-and-tasks.md); the `start(...)` signature, its options and the generated snippet →
> [16](16-groovy-service-api.md) §2.12; the `ScheduleDto` export shape, the cron dialect and the two-hop
> pipeline → [12](12-queries-sources-schedulers-and-rest.md) §3; CRUD methods, `param` and the paging shapes →
> [11](11-business-logic-dynamic-crud.md); rule types, templates and return semantics →
> [08](08-groovy-rules-and-context.md); where each step sits in the build →
> [19](19-build-decision-procedure.md) Phases 11–12; per-module and live testing →
> [26](26-orchestration-and-testing.md).

| | |
|---|---|
| What can start a process | a start **FORM** (a person) **or** `service.workflow.start(...)` from an **EXECUTION_RULE** or a **CRUD GROOVY method**. Nothing else creates a CASE — a PREDICATE and a VALIDATION_RULE are refused at runtime with a named message, and a `bpmn:CallActivity` ([07](07-workflows-and-tasks.md) §7) starts an engine-side CHILD instance with no process row, so it has no worklist entry, no process group and no access rows |
| The three SYSTEM triggers | **scheduler tick** (time) · **CRUD GROOVY method** (a row was written) · **service task** (another process reached a step) |
| Which of them are HEADLESS | the scheduler tick and the CRUD GROOVY method: `contextDataMap` = **null**, no row, no form, no process. A **service task is NOT** — it receives the running case's real document (§2.3), which is the difference that decides how its rule is written |
| What a headless rule receives | `attrs` = an **empty map** · `contextDataMap` = **null** · a user only if the schedule carries one. `param` is empty on the scheduler tick, and on a CRUD GROOVY method it holds the method's declared arguments (§2.2) — that is the one thing the method path hands you |
| What still works headless | the whole `service.*` facade — `service.crud.<alias>.<m>()`, `service.rimm`, `service.notification`, `service.report`, `service.workflow.start` — plus `context.<ctx>.<alias>.service.<m>()` and `context.data.getAttr(...)` |
| What throws headless | `context.<ctx>.data` · `context.<ctx>.<alias>.data` · a bare `contextDataMap[...]` |
| The document to pass | `contextDataMap` keyed by context **IDENTIFIER** → `crudDataMap` keyed by crud **ALIAS** → the row under `value` (camelCase dtoField names, **nested**, never dot-paths), plus `attrs` inside each context and `attrs` at the root. Write `[:]`, never `[]` |
| Unknown keys | **silent, in two different ways.** A misspelled **envelope** key (`contextDataMap` / `crudDataMap` / `value` / `attrs`) is dropped by Jackson without a word; a misspelled **context identifier** or **crud alias** is a legal Map key, so it is KEPT — addressing nothing. Either way the START itself says nothing — the process is created under-seeded and a process identifier comes back — but a wrong context identifier does surface later, when the first service task reads `.data` and throws (§7) |
| The five option keys | `owner`, `roleGroups`, `emails`, `businessKey`, `groupIdentifier` — every other key is ignored without a word |
| Idempotency | **entirely the author's job.** Nothing asks "does a case already exist for this row" on your behalf. `service.workflow.list(...)` ([16](16-groovy-service-api.md) §2.13) can look, but only through a process table's INDEXED values and at a query per row — a claim column in the data is exact, free, and needs no table |
| Offline gate | `validate` checks the scheduler's rule TYPES, its cron, `enabled:true`, a literal `start("<id>")` against `workflows[]`, and ERRORs when a rule a scheduler NAMES reads the bare `contextDataMap` binding. It cannot see idempotency, the process group, a SQL method's `parameters[]`, or any key inside the document |
| Dead on arrival | import forces every workflow to `deployed:false`, so the chain throws `workflow_is_not_deployed` until somebody opens the BPMN editor and presses **Deploy** |

> **🔧 Tooling.** There is **no** `mrjun.py` command for a scheduler and **none** for a process group — both are
> hand-authored JSON in `rep-objects.json`. The rest of the chain has commands, and they must run in this order.
> Two orderings are forced, for opposite reasons:
> * ⛔ **the workflow's own service-task rules BEFORE `workflow add`** — `--service-task "<Step>:<rule>"`
>   resolves that rule immediately and **exits 1** with `rules not found` if it is absent, and there is no
>   command to wire a service task to a rule afterwards. So the very first command is a `rule add`.
> * the **business logic before the rule that calls it** (§3 steps 5→6) — the other way round `validate` WARNs
>   that the rule calls a CRUD method which does not exist, which is true, not noise.
>
> First the two columns the claim needs (§5.3): there is **no `db add-column`** — `db` has only `add-schema` /
> `add-table` / `list-*` / `show`, so an existing table is extended by hand-editing `ddl`, `columns` and
> `columnTypes` in `project-db.dump` ([10](10-database-management.md) "Gotchas"; the dump's `rows[]` are dicts
> keyed by column name, not positional arrays). Then:
> `rule add --name "<Step>" --type EXECUTION_RULE --context <ctx> --script @step.groovy` (every rule a service
> task will name — **before** the next command, which resolves them) →
> `workflow add --name "<Process>" --service-task "<Step>:<rule>" --user-task "<Step>:<FormGroup>" --context <ctx>`
> → `context add-alias <ctx> <alias>` (every alias the started process touches) →
> `query add --name crud_<alias>_find<X>Candidates --source <src> --sql @candidates.sql` then
> `crud add-method <alias> --name find<X>Candidates --type SQL --query <qid> --script @candidates.sql
> --returns-array` (the candidate list, §4.1 — **`--returns-array` is what makes it answer a plain List**;
> without the flag the method is `returnsArray:false` and answers ONE row — a Map — and the failure is nastier
> than a type error: `rows.isEmpty()` quietly answers false, `for (row in rows)` iterates the row's ENTRIES, and
> the first field read throws `No such property: id for class: java.util.LinkedHashMap$Entry`, which names
> nothing you wrote) →
> `query add --name crud_<alias>_claimFor<X> --source <src> --sql @claim.sql` (the paired query — the identifier
> it prints is the `<qid>` below) →
> `crud add-method <alias> --name claimFor<X> --type SQL --query <qid> --script @claim.sql` (the claim, §5 —
> **deliberately WITHOUT `--returns-array`**: `returnsArray:false` is what makes a row nobody won answer Groovy
> `null`, which is the whole test; the method's own `script` is the SQL that actually runs, so omitting
> `--script` ships an empty method) →
> ⛔ **hand-add that method's `parameters[]`** in `dynamic-cruds.json` —
> `{"parameterName": "id", "parameterType": "String", "parameterOrder": 0}`, one entry per `:name` in the SQL
> ([11](11-business-logic-dynamic-crud.md), "Method level"). `crud add-method` always writes `parameters: []` and
> has no flag for them; the SQL executor builds its bind map from the DECLARED parameters only and leaves an
> undeclared `:id` in the statement verbatim, so the claim throws or claims nothing on every tick — and `validate`
> checks parameters for GROOVY methods only, never for SQL ones →
> `rule add --name "<Name>" --type EXECUTION_RULE --context <ctx> --script @sweep.groovy` (the starting rule;
> `--type PREDICATE` for the scheduler's gate — `--context` is **required**, so pick the context that exposes
> every alias the rule reads, §3) → `crud apply` when the trigger is a CRUD **GROOVY** method (§4.4): such a
> method delegates to a rule by `ruleIdentifier` and is dead without one →
> hand-author `rep-objects.processGroups[]` and `rep-objects.schedulers[]` — the `ScheduleDto` JSON, field for field, is [12](12-queries-sources-schedulers-and-rest.md) §3.1, and the worklist node's own JSON (model + settings mirror + where in the page tree it must sit) is [05](05-crud-tree-and-process-table.md) "Recipe B". Both are complete; this doc does not repeat them.
> Then `mrjun.py validate --project <dir>`, and `mrjun.py pack <dir> out.mrjun`.
> Every entity command takes `--project <unpacked-dir>`. Full index — [`tools/README.md`](tools/README.md).

---

## 1 · When the PRD means this

The reader's problem here is **recognition, not syntax**. The default failure is not a broken rule — it is an AI
that gives every workflow a start form because the PRD never said "there is no form", and then ships a process
nobody ever starts. So decide it explicitly, per process, with one question:

> **At the moment the case begins, is a human pressing something that means "open THIS case"?**
> If the PRD names no click, no submit, no screen and no actor at that instant, the start is a RULE.

A human saving a **different** record is not a counter-example. An analyst who saves an assessment, an approver
who signs off, a clerk who registers an intake — there is a click, a screen and an actor at that instant, and the
start is still a RULE: the click belongs to *that* screen, this process has no screen of its own, and the trigger
is a **write** — a CRUD GROOVY method on that transition (§2.2), not a start form.

A second question picks the trigger: **what wakes it up — a clock, a write, or another process?**

| PRD phrasing | What it actually says | Trigger | Where in [19](19-build-decision-procedure.md) |
|---|---|---|---|
| "nightly", "daily at 02:00", "every N minutes", "at the configured interval", "periodically", "as a background job" | a clock | **SCHEDULER** → EXECUTION rule | Phase 12 (+ Phase 11 for the workflow) |
| "if no response within N days", "unpaid after N days", "N days before expiry", "chase unanswered … and escalate", "overdue", "expiring", "stale" | a clock reading business dates — **nothing fires when a date passes**, so somebody has to look | **SCHEDULER** | Phase 12 |
| "when the balance falls below X", "when X exceeds the threshold" — with no moment named | a periodic scan | **SCHEDULER** | Phase 12 |
| "the process must not be missed even if the service was down" | a clock, **plus** a backlog re-detected from the data (§5) | **SCHEDULER** | Phase 12 |
| "as soon as a `<row>` is registered / imported / received", "on receipt of", "every new `<entity>` opens a …" | the write itself | **CRUD GROOVY method** (create) → `start` | Phase 3 (method) + Phase 5 (rule) |
| "when the status becomes X", "on approval", "once the document is signed" | a write that is a **state transition** | **CRUD GROOVY method** (the transition method, guarded — an `update` fires on every save) | Phase 3 + Phase 5 |
| "if the reviewer rejects, a correction case is opened", "escalate to `<Role Group>`", "spawn a sub-case per line" | a step inside a process already running | **SERVICE TASK** rule in the first workflow | Phase 11 |
| "24 h before the deadline", a BPMN **timer / boundary** event | not modellable in this BPMN subset | **SCHEDULER** for that one element; build the rest as a real workflow | Phase 11 + 12 |
| "the clerk submits the request", "the user fills in the intake form", "`<Actor>` raises a case", "on **Create** the approval starts" | a person, on a screen | **START FORM** — shape A or B, no rule | Phase 11 (+ 7, 8) |

**Words that look automatic and are not.** "Automatically routed to the right approver", "the system calculates
the total", "the case is automatically closed when the last task completes" — these describe what happens
*inside* a process that something else started. They are gateway conditions and service tasks
([07](07-workflows-and-tasks.md)), not a trigger. Only a sentence about the **beginning** of the case decides
this doc's question.

**The inventory row.** In [19](19-build-decision-procedure.md) Phase 1 every process gets a row. Add one column
to it — **"what starts it"** — with exactly one of `FORM` / `SCHEDULER` / `CRUD METHOD` / `SERVICE TASK`, and
carry it into Phase 11. A row that says `SCHEDULER` and a workflow with a start form is a contradiction you can
see before you author anything; a row left blank is how a start form gets built by default.

---

## 2 · WHO opens the case — decide this before you draw the BPMN

⛔ **A workflow is inert. Nothing about a valid BPMN, a deployed process or a rendered worklist makes a case
exist.** A build can pass every other check in this library and ship a process that no human and no clock can
ever open: the diagram is correct, the worklist page renders, the task buttons are wired, and the case list is
empty forever. This has happened. Answer three questions, in the PRD's own words, and write the answers into
the case notes:

1. **WHO** opens a case — a person, or the system?
2. **WHEN** — on what act or what condition?
3. **WHAT MAKES THAT RUN** — if the answer is "a rule", the rule is not the answer. A rule is a body of code
   that something has to invoke. Name the invoker.

Question 3 is the one that gets skipped. "A rule starts it" is not a design; "the request's **Submit** action
runs `DO <doc> submit`, which claims the row and calls `service.workflow.start`" is.

### 2.0 The four starters

| | **User start action** | **Document lifecycle rule** | **Scheduler sweep** | **Service task** |
|---|---|---|---|---|
| PRD sentence that means this | *"the operator opens a case"* — the case IS the unit of work, there is no document before it | *"the employee submits a request"* — a business DOCUMENT exists first and the case tracks it | *"chase anything unanswered for 3 days"*, *"nightly"* | *"when the previous process reaches X"* |
| Where it lives | `userStartProcessActions` on a `process.table` node ([05](05-crud-tree-and-process-table.md)) | an `EXECUTION_RULE` behind a crud-table action's `onBeforeCompleteRuleIdentifier` | an `EXECUTION_RULE` as a schedule's `actionRuleIdentifier` ([12](12-queries-sources-schedulers-and-rest.md) §3) | an `EXECUTION_RULE` as `flowable:rule` on a `bpmn:ServiceTask` ([07](07-workflows-and-tasks.md)) |
| What invokes it | a person pressing a breadcrumb button | a person pressing a row action | the cron | the engine |
| Carries a document? | only what its start FORM collects | the row it was pressed on — the strongest binding available | whatever the sweep query found | the parent case's context |
| Idempotency | the person; nothing stops two presses | the action's own status gate (`from` states) | **none — §5 is mandatory** | one per arrival |
| Cost of getting it wrong | a case with no document behind it | none, this is the safe default when a document exists | duplicate cases on every tick | — |

**A `direct:"on"` start action starts the process IMMEDIATELY with a synthetic business key and NO context
data at all** (`ProcessTablePlugin.breadcrumbButtons` → `processService.startProcess`). If your first service
task reads an id out of `attrs`, a direct start action hands it nothing and the case is unusable. Use
`direct:"off"` with a `formGroupIdentifier` — that opens the group as a **start form** (the absence of a
`processIdentifier` is what marks it one) and the process starts carrying what the form collected.

### 2.0.1 Two starters for one process is a decision, not a bonus

If a document-driven start already exists and you ALSO add a start action, the same document can get two
cases — one from its own Submit, one from the worklist's form. Either drop one, or make the second impossible
by construction: stamp the instance id (or a `'PENDING'` claim, §5.3) on the document and make the other
starter's PREDICATE refuse while it is set. Do not rely on the two audiences not overlapping.

### 2.0.2 The buttons on a process table are THREE different things

Confusing them is why a worklist looks broken. Full field reference:
[05](05-crud-tree-and-process-table.md) §"The THREE action origins on a process table".

| Bucket | Lives in | Shown as | Shown when |
|---|---|---|---|
| `userStartProcessActions` | the `process.table` node | breadcrumb buttons above the table | always (blank predicate = allowed) |
| `globalActions` | the `process.table` node | the **row** dropdown, on every row | only while its predicate is true — a **blank `predicateIdentifier` is skipped and never rendered** |
| per-task actions | the **BPMN**, `flowable:userActions` on the `userTask` ([07](07-workflows-and-tasks.md)) | the row dropdown | only while the case is parked at that task |

So: "the row has no buttons off-task" means `globalActions` is empty; "nothing can be started from this page"
means `userStartProcessActions` is empty. Neither is a default you should reach by omission. If a case must
be openable, viewable and nudged from the worklist, that is one start action and two global actions, and each
of them needs a predicate rule authored on purpose.

### 2.0.3 What `validate` enforces

* a workflow that nothing starts — no rule calls `service.workflow.start`, no `process.table` bound to it
  carries a start action, and it is not a `callActivity` target → **ERROR**;
* a rule that calls `service.workflow.start` and is itself referenced by nothing — no scheduler, no action,
  no service task, no form → **ERROR**. This is question 3 above, mechanised;
* a `process.table` with both action buckets empty → WARN.

---

### 2.1–2.4 · The three SYSTEM triggers, and what each rule receives

All three run the same kind of object — an `EXECUTION_RULE` ([08](08-groovy-rules-and-context.md)) — and all
three reach business logic the same way, through `service.crud.<alias>.<method>(...)`. They differ in what
arrives with the invocation, and that difference is the whole cost of getting one wrong.

### 2.1 A scheduler tick — time

The schedule fires its gate over synchronous REST and then publishes its ACTION over Kafka, and that message
carries no data of its own beyond the schedule identifier, the rule identifier, the trigger time, the realm,
the client and the schedule's `serviceUserId` / `serviceUserEmail`. **No context data is attached anywhere on the path**, so the executor
builds a fresh, empty document: `attrs` is an empty map (never null — `attrs.get('x')` safely returns null),
`param` is an empty map, and `contextDataMap` is **null**, which means the two most-copied idioms in this
library — `context.<ctx>.<alias>.data.get()` and `context.<ctx>.data` — both throw on the first line. Everything
the rule works on it must fetch itself.

Three more consequences that only this trigger has:

* **The OUTCOME is never recorded anywhere.** The action is fire-and-forget: the rule's return value is
  discarded, a failure is caught and turned into a FAILURE response rather than an exception, so the Kafka tick
  is consumed and the work is simply lost. The schedule row *is* written on every fire — `lastActionTime` and
  `cooldownUntil` are set and saved whether the action succeeded or failed (§5.2) — so it proves only that the
  message was sent, never what happened to it, and no screen shows the difference. If the job must be
  observable, the rule itself has to write a row, send a mail or start a process.
* **No retry, no dead letter.** The listener auto-commits, and there is no error handler and no dead-letter
  topic: a tick whose rule FAILS is gone, and the only trace is a log line in the executor. Catch-up after
  downtime is not something to rely on either — the listener resets to `latest`, and whether a backlog is
  redelivered at all depends on the consumer group's committed offset and the broker's retention, neither of
  which the project controls. A job that must not be missed has to re-detect its own backlog **from the data**
  on the next tick — which is the same discipline idempotency needs (§5).
* **Identity is whatever the schedule carries — and it is TWO fields, with two different failures.**
  `serviceUserEmail` travels through both hops and becomes the acting user of the rule, and therefore the
  default `owner` of every process it starts: blank, and the case is owned by the project's **configured author account** — the wrong account, not no account — or, on a deployment that blanks that setting, by nobody at all (§6).
  `serviceUserId` is the field every permission check keys off: blank, and **every** `hasAnyRole` /
  `hasAllRoles` / `hasAnyRoleGroup` / `hasAllRoleGroups` short-circuits to `false` with no error — a permission
  guard copied from a UI rule silently turns the whole job into a no-op. `service.security.user()` answers an
  all-null user only when both are blank.

### 2.2 A CRUD GROOVY method — a row was written

A GROOVY method delegates to a rule by `ruleIdentifier` ([11](11-business-logic-dynamic-crud.md)), and that rule
runs with exactly the same headless shape: no context data, `contextDataMap` null. The difference is that its
arguments arrive in **`param`**, and `param` is **flat**, keyed by the method's **declared** parameter names —
snake_case on a generated create/update (`doc_number`, `partner__id`, `id`). A `value:` map inside the document
is keyed by **camelCase dtoField** names. The two shapes meet in every method-started process, and `value: param`
writes keys that no service task can ever read back.

Two behaviours make this trigger the friendlier of the two headless ones. Its failure **does** reach the caller —
the delegating runner raises `Groovy method execution failed: <messages>` — so the rule that started the chain
can still react. And identity flows: the acting user is the REST caller's email, or the calling rule's own email
when a rule made the call, so a scheduler-initiated chain carries the schedule's service identity all the way
down to the process it eventually starts.

⚠️ **`create` is once per row; `update` is not.** A start hung on a create method is naturally idempotent — the
row can only be created once. A start hung on an `update` fires on **every** save of that row. Hang it on a
dedicated **state-transition** method instead (§5), never on the generated `update`.

### 2.3 A service task — another process reached a step

This is the one trigger where the rule is **not** headless. A service-task rule always receives a non-null
document: either the process's own `contextData` variable or, when there is none, a skeleton keyed by the
workflow's declared `contextIdentifiers` with empty crud maps. So `context.<ctx>.<alias>.data` is legal here —
and `context.<ctx>.<alias>.data.get()` returns an **empty LinkedHashMap**, never null, so the emptiness test is
`if (!row)` or `row.isEmpty()`, not `if (row == null)`.

Every process variable is merged into the document's ROOT `attrs` and overrides same-named attributes from the
start document, so `attrs.get('owner')`, `attrs.get('processEntityId')` and `attrs.get('_traceId')` are free
reads — and those three names must never be used for business data. The task runs as the assignee of the last
COMPLETED user task, else the `owner` process variable, else the owner access row; in a case that has not
reached a user task yet, that is the owner the starter chose. A child process started from here therefore
inherits **this** identity unless the call passes `owner` explicitly.

⚠️ If a service task binds several rules and any one of them fails, the remaining rules still run and the task
then throws — and the throw happens before the task's context data is saved, so the whole task's document
changes are discarded while whatever the rules already wrote to the database is not.

### 2.4 Choosing

| | Scheduler tick | CRUD GROOVY method | Service task |
|---|---|---|---|
| Answers | "when time passes" | "when this row is written" | "when the case reaches this step" |
| `contextDataMap` | null | null | **non-null** (document or skeleton) |
| `param` | empty | the method's declared params | empty |
| Acting user | the schedule's `serviceUserEmail` (may be blank) | the caller's email, inherited down the chain | last completed user task's assignee, else `owner` |
| Failure is seen by | nobody (a log line) | the caller, as an exception | the process (the task throws) |
| Latency | up to one cron period | immediate, synchronous | immediate, synchronous |
| Natural idempotency | **none** — §5 is mandatory | only on `create` | one per arrival at the step |

---

## 3 · The chain, end to end — build in this order

Every arrow here is a **string** inside another object, so a step built early is a placeholder somebody must
remember to fix, and nothing offline remembers for you. Build outwards from the thing that owns the identifier.

⚠️ **This is the chain's DEPENDENCY order, not a second build order.** [19](19-build-decision-procedure.md)'s
numbered phases are the one sequence you follow ("do NOT reorder"), and they already place two of the steps
below: the **context** (step 4) is Phase 4 and the **candidate / claim / write-back methods** (step 5) are
Phase 3, over columns decided in Phase 2. They are listed here so you can CHECK that they cover this chain —
not so you build them twice. What you actually AUTHOR at this point is **1, 2, 3, 6, 7**, inside Phases 11–12:
the workflow with its process group and its worklist page (Phase 11), then the start rule — recorded in the
plan at Phase 5, bodied here, because only now does the workflow identifier it quotes exist — and its trigger
(Phase 12 for a scheduler). If step 4 or step 5 turns out to be missing, go back and add the alias or the
method in its own phase; never author it inline here.

1. **The workflow** ([19](19-build-decision-procedure.md) Phase 11, [07](07-workflows-and-tasks.md)). It must
   exist before anything quotes its identifier, because that identifier is the first argument of the call.
   *Reversed:* the rule ships with an invented identifier and throws `workflow_not_found` on its first tick —
   `validate` ERRORs on this, but only when the argument is a literal.
2. **The process group** — one entry in `rep-objects.processGroups[]` whose `identifier` **you** mint. The
   exported shape is the usual rep-object envelope with `id: null`:
   `{"message": null, "errors": null, "id": null, "realmName": "<realm>", "clientName": "<client>",
   "identifier": "<uuid>", "creationTime": "<ISO>", "modificationTime": "<ISO>", "name": "<Process> cases",
   "description": "…"}` (realm/client are re-stamped to the target tenant on import; the `identifier`
   survives). *Reversed:* if you leave the worklist node's `processGroupIdentifier` blank and let the plugin
   create the group on first render, its identifier is minted **at render time** and no rule can name it —
   every rule-started case is then filed under no group. Real exports show the auto-created shape plainly: the
   group's `name` and `description` are both the node's `uniqueIdentifier`. See
   [05](05-crud-tree-and-process-table.md) §"Process group: binding and auto-creation".
3. **The worklist page** — a `process.table.pluin` node whose model carries that same `processGroupIdentifier`
   and `workflowIdentifier`, its settings mirror, and a left-nav quick link (authored in **Phase 11**, using Phase 9's own `node add` commands, plus Phase 13's quick link). Build it now, not
   at the end: it is the only place a rule-started case is ever visible, and the only way you will see the
   chain work.
4. **The context and its crud aliases** ([19](19-build-decision-procedure.md) Phase 4). The context
   **identifier** is the key of `contextDataMap`; the crud **aliases** are the keys of `crudDataMap`. Every
   alias a service task touches must be in the context's `crudAliases[]` **and** present in the document.
   *Reversed:* the two keys fail in completely different ways. A mistyped **context identifier** means that
   context's whole entry is missing, and the first service task throws
   `No CRUD data available for CRUD: <alias>` — a long way from the rule that mis-typed it. A mistyped **crud
   alias** throws nothing at all: before any rule script runs, the executor auto-creates an EMPTY envelope for
   every alias of every attached context **that the document already carries an entry for**, so the task reads
   an empty row (`.data.get()` answers `[:]`, §2.3), computes nulls from it and writes nothing. The auto-fill
   never invents a context: a rule with two attached contexts whose document names only one gets no envelopes
   for the other (its `.data` throws, the case above), and a headless rule — whose document is null — gets none
   at all. Seed every alias the first tasks read anyway — the auto-created envelope carries no `value`, so
   everything derived from that row is null and every screen stays green while it happens.
5. **The idempotency plumbing** in business logic ([19](19-build-decision-procedure.md) Phase 3): the candidate
   method, the atomic claim method and the write-back method (§5). Build these **before** the rule that uses
   them, and before any scheduler exists that could run it.
6. **The EXECUTION rule** (Phase 5) — gather, claim, shape, start, mark (§4). Its attached context decides what
   `service.crud.<alias>` can reach: with **zero** contexts attached the alias resolves against the whole
   project registry, but as soon as **any** context is attached the lookup is gated to that context's
   `crudAliases[]`. `rule add` requires `--context`, so attach the project's own context and make sure every
   alias the rule reads is listed in it. *Reversed:* attaching a narrow context "to be tidy" makes every other
   CRUD the rule touches unreachable — `No CRUD found with alias: X in any attached context.`
7. **The trigger** last: the `rep-objects.schedulers[]` entry (Phase 12), or the CRUD method's
   `ruleIdentifier`, or the `flowable:rule` of the service task. *Reversed:* a scheduler authored before its
   claim method exists, shipped `enabled:true` with a valid cron, registers a live cron trigger the moment the
   project is imported and starts opening a case per row per tick on the real project.

⚠️ **Order matters on import too.** Schedulers are saved **before** workflows, rules, contexts, forms and
settings. A duplicate scheduler `name` throws on the second save and everything after it is silently skipped —
which is why `validate` ERRORs on it.

⚠️ **The last step is not in any file.** Import clears `externalId` / `processDefinitionId` /
`processDefinitionKey` and forces `deployed:false` on every workflow, so the chain is inert until someone opens
the BPMN editor and presses **Deploy**. Put that in the hand-over notes as an acceptance step, or the chain will
be reported as broken.

---

## 4 · The rule — gather, claim, shape, start, mark

One EXECUTION rule does five things, always in this order. Names below (`requests_cruid`, `requestContext`, the
UUIDs) are placeholders — swap in the project's own.

### 4.1 The business logic it needs first

Three methods on the CRUD ([11](11-business-logic-dynamic-crud.md)), authored before the rule:

⛔ **Bind a uuid PK as text and cast it in the statement.** `parameters[].parameterType` for a uuid id is
`String` ([11](11-business-logic-dynamic-crud.md)), so a bare `WHERE id = :id` reaches PostgreSQL as
`uuid = character varying` and the method fails by name. Write `CAST(:id AS uuid)`. The same rule applies to
every other typed parameter — a raw `:col::interval` / `:col::uuid` makes the executor infer the type and call
the converter itself, which crashes on an empty value; cast INSIDE the statement instead.

```sql
-- findEscalationCandidates  (SQL, returnsArray:true) - the CHEAP half of idempotency:
-- the WHERE excludes every row this sweep has already acted on.
SELECT * FROM requests
 WHERE state = 'SENT'
   AND sent_at < now() - COALESCE(CAST(NULLIF(:chase_interval,'') AS integer), 3) * INTERVAL '1 day'   -- the DEADLINE is data, not a literal
 ORDER BY id
 LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))

-- claimForEscalation  (SQL, returnsArray:FALSE) - the CORRECT half: one statement, so two
-- overlapping ticks cannot both win. RETURNING * is what makes the answer testable.
UPDATE requests
   SET state = 'ESCALATED', escalated_at = now()
 WHERE id = CAST(:id AS uuid) AND state = 'SENT'
 RETURNING *

-- setEscalationProcess  (SQL, returnsArray:false) - write the process identifier back onto the row.
UPDATE requests
   SET escalation_process_identifier = :escalation_process_identifier
 WHERE id = CAST(:id AS uuid)
 RETURNING *
```

⛔ **Every `:name` in those statements must be declared in the method's `parameters[]`.** The executor builds
its bind map from the DECLARED parameters alone and rewrites `:name` into a placeholder only for a name it
bound; an undeclared `:id` is handed to the database verbatim, so the claim throws or claims nothing — on every
tick, forever. `crud add-method` writes `parameters: []`, and `validate` checks parameters for GROOVY methods
only, so declaring them is hand-work and **`validate` cannot report it**. One offline gate can:
**`crud verify --db`** ([26](26-orchestration-and-testing.md) §3 T3) substitutes only the DECLARED parameters
and therefore ships the literal `:name` to PostgreSQL, where the method fails by name — so run it before you
call a hand-authored SQL method done (the 🔧 block above; [11](11-business-logic-dynamic-crud.md),
"Method level").

⛔ **The cron is the polling FREQUENCY. It is never the business deadline.** The cron says how often you *look*
— minutes to hours. The deadline is DATA: a column on the row, or a value read from a policy CRUD, and the
candidate query compares against it. A PRD that says the interval is configuration ("at the configured
interval", "deadlines are policy values owned by the business") forbids `INTERVAL '3 days'` inside the SQL:
declare it as a parameter — `... AND sent_at < now() - COALESCE(CAST(NULLIF(:chase_interval,'') AS integer), 3) * INTERVAL '1 day'` — or join the policy table,
so changing the policy row changes behaviour with no re-import. Encoding the deadline as the cron period ("the
deadline is 24 h, so cron = daily") is the same mistake with a worse failure: the sweep's own latency silently
*becomes* the deadline, and nothing names it as the cause.

⛔ **Never write the marker through the generated `update`.** That method SETs every non-PK column, and any
parameter absent from the map you pass is bound as SQL NULL — so `update([id: r.id, state: 'ESCALATED'])`
blanks every other column of the row. `validate` stays green; only `crud verify --db` ever sees it.

### 4.2 The rule

```groovy
// EXECUTION_RULE - the ACTION rule of the "Escalate unanswered requests" scheduler.
// Headless: no form, no row, no process. contextDataMap is null here and every
// context.<ctx>.<alias>.data read throws - everything below is FETCHED, not received.

def wfId    = "a3f2c1de-1111-4444-8888-000000000001"   // WORKFLOW identifier, never its name.
                                                      // Held in a variable ONLY for readability here:
                                                      // validate can check a LITERAL first argument
                                                      // against workflows[] and cannot check a variable
                                                      // (§8.1, §8.2). Inline it, or accept that the
                                                      // workflow_not_found guard is off for this rule.
def ctxId   = "8b21c0de-1111-4444-8888-000000000002"   // CONTEXT identifier, never its alias
def groupId = "7c40b0de-1111-4444-8888-000000000003"   // rep-objects.processGroups[].identifier

int rowsInPage = 200
int passes     = 50      // bounded: the candidate set shrinks as rows are claimed
int opened     = 0

// The DEADLINE is policy, not code (§4.1). Read it from the policy CRUD so the business can change
// it without a re-import; the literal below is only the fallback for a project that has no policy row.
def policy = service.crud.escalation_policy_cruid.get([id: 1])
String chaseInterval = (policy?.chaseInterval ?: "3 days") as String

while (passes-- > 0) {
    // The candidate method is the CHEAP half of idempotency: its WHERE excludes every row this
    // sweep has already acted on, so page 0 is always the next batch of work. A SQL method with
    // returnsArray:true answers a plain List; `find` would answer
    // [content, totalElements, totalPages, pageNumber] and you would read page.content.
    def rows = service.crud.requests_cruid.findEscalationCandidates([
            chase_interval: chaseInterval,
            rowsInPage    : rowsInPage,
            pageNumber    : 0
    ]) ?: []
    if (rows.isEmpty()) { break }

    int claimedThisPass = 0
    // `for`, not `.each`: inside a closure `return` means "next element", which reads like
    // "stop the rule" to everyone who did not write it.
    for (row in rows) {
        // THE CLAIM - one conditional statement in the database, returnsArray:false:
        //   UPDATE requests SET state = 'ESCALATED', escalated_at = now()
        //    WHERE id = CAST(:id AS uuid) AND state = 'SENT' RETURNING *
        // A Map when THIS tick won the row, Groovy null when something else already took it.
        // Without RETURNING * the method answers [affected: n] - always truthy, never a claim.
        def claimed = service.crud.requests_cruid.claimForEscalation([id: row.id])
        if (claimed == null) { continue }
        claimedThisPass++

        // Row keys are camelCase of the SQL column LABEL: doc_number reads back as docNumber.
        // claimed.doc_number is not an error - it is null, and that null lands in the document.
        def pid = service.workflow.start(wfId, [
                contextDataMap: [
                        // keyed by context IDENTIFIER; a variable key needs the parentheses
                        (ctxId): [
                                crudDataMap: [
                                        // keyed by crud ALIAS. Seed every alias the started process's
                                        // first tasks READ. A missing or misspelled one throws nothing:
                                        // the executor auto-creates an empty envelope for every alias
                                        // of an attached context, so the task quietly reads an empty
                                        // row and computes nulls from it (§3 step 4).
                                        requests_cruid: [
                                                value: [
                                                        id       : claimed.id,
                                                        docNumber: claimed.docNumber,
                                                        amount   : claimed.amount,
                                                        // nesting, never the dot-path "partner.id"
                                                        partner  : [id: claimed.partnerId]
                                                ]
                                        ]
                                ],
                                // CONTEXT-scope attributes - [:] and never []. This slot is what a
                                // `scope: CONTEXT` worklist column and a CONTEXT-scope task-form control
                                // read, so it is worth filling only when one of those exists (§6).
                                attrs: [:]
                        ]
                ],
                // process-GLOBAL attributes: what a `scope: GLOBAL` process.table column extracts
                // and what a GLOBAL-scope task form binds to. A rule-started case has no start form,
                // so nothing else ever puts an identifying value here (§6).
                attrs    : [
                        subjectId   : claimed.id as String,
                        subjectLabel: claimed.docNumber,
                        openedBy    : "escalation sweep"
                ],
                // The language this case's own correspondence goes out in. When the letters are
                // addressed to a SUBJECT (a customer, a counterparty), read it off the claimed row -
                // a literal here is the "every letter came out in one language" bug, and nothing
                // offline can see it. Omit the key entirely and everything falls back to the
                // project default (§6).
                localeKey: (claimed.preferredLocale ?: "en_US")
        ], [
                owner          : "operations@example.com",
                roleGroups     : ["Back office"],
                businessKey    : "ESC-" + claimed.docNumber,
                groupIdentifier: groupId
        ])

        // Nothing in service.* can answer "does a case exist for this row", so this column IS the
        // answer - for the next tick, for the worklist link and for the repair sweep.
        service.crud.requests_cruid.setEscalationProcess([
                id                         : claimed.id,
                escalationProcessIdentifier: pid
        ])
        opened++
    }
    if (claimedThisPass == 0) { break }
}

return opened
```

### 4.3 The traps that live in that rule

| In the code | What goes wrong | Why |
|---|---|---|
| `contextDataMap: [ … ]` written out by hand | the shortcut `[contextDataMap: contextDataMap]` starts an **empty** process here | the binding exists only when the rule RECEIVED a document; headless it is null and forwarding null is not an error. `validate` ERRORs when a rule a scheduler NAMES reads the bare binding (§8.1) |
| `(ctxId):` in parentheses | without them Groovy uses the literal string `"ctxId"` as the key | a variable map key must be parenthesised |
| `attrs: [:]` (twice) | `[]` is a Groovy **List**; Jackson refuses to read an array into the document and the call dies with *"the context data map could not be read"* | the empty map literal is `[:]` |
| `docNumber`, not `doc_number` | reads null, writes null into the document, and the process opens with a blank label | every returned row key is camelCase of the SQL column **label** |
| `claimForEscalation([id: row.id])` | a **single**-parameter method is treated positionally unless the map names that parameter — `[requestId: row.id]` would jam the whole map into the slot | the unpack test is "does the map contain this parameter's name" |
| `setEscalationProcess([id: …, escalationProcessIdentifier: …])` | either spelling binds — camelCase is tried first, then the declared snake_case name | this is the CALL side; the mismatch that bites is the READ side (row keys) and `param` inside a method body |
| `service.crud.requests_cruid` | as soon as ANY context is attached to the rule, only that context's aliases resolve | list every alias the rule reads in the attached context's `crudAliases[]` (§3) |
| the whole call, placed last | the rule is **not** transactional: a failure after the start does not undo it, and the start itself runs the new process's whole synchronous head | start after everything that can fail has succeeded |

### 4.4 The same thing from a CRUD method

```groovy
// The rule behind the GROOVY method `createRequest` of requests_cruid (its ruleIdentifier).
// Headless exactly like a scheduler tick - contextDataMap is null - but the arguments arrive
// in `param`, which is FLAT and keyed by the method's DECLARED parameter names: snake_case on
// a generated create/update. A `value:` map is keyed by camelCase dtoField names, so
// `value: param` writes keys no service task can ever read back.
def created = service.crud.requests_cruid.create(param)

// 100000.00G is a BigDecimal literal; 100000G would be a BigInteger (08, "Numbers in a rule").
if (created?.amount != null && (created.amount as BigDecimal) > 100000.00G) {
    service.workflow.start("a3f2c1de-1111-4444-8888-000000000001", [
            contextDataMap: [
                    "8b21c0de-1111-4444-8888-000000000002": [
                            crudDataMap: [
                                    requests_cruid: [value: [
                                            id       : created.id,
                                            docNumber: created.docNumber,
                                            amount   : created.amount
                                    ]]
                            ],
                            attrs      : [:]
                    ]
            ],
            attrs         : [subjectId: created.id as String, subjectLabel: created.docNumber],
            // the SUBJECT's language, not the project's - see the note in §4.2
            localeKey     : (created.preferredLocale ?: "en_US")
    ], [
            roleGroups     : ["Back office"],
            businessKey    : "REQ-" + created.docNumber,
            groupIdentifier: "7c40b0de-1111-4444-8888-000000000003"
    ])
}

return created
```

Note the quoted UUID keys: a UUID is not a legal bare Groovy identifier, so context-identifier and
process-group keys stay in quotes. Only a key held in a **variable** needs the parentheses instead.

### 4.5 The gate (a scheduler predicate is a different object)

The gate and the action must be two rules. A PREDICATE is evaluated for its answer, possibly repeatedly, and
`service.workflow.start` is refused inside one at runtime with a named message. The gate is also cheap and runs
constantly — a false predicate only stores the check time and saves, and the cooldown is recomputed **only when
the action fires** — so put the expensive work in the action, never in the gate.

```groovy
// PREDICATE - the scheduler's GATE. It may only ANSWER: service.workflow.start is refused here
// at runtime ("not available in predicates"), and so is any other way of creating work.
def counted = service.crud.requests_cruid.countEscalationCandidates()
long n = ((counted instanceof Map ? counted.total : counted) ?: 0) as long

// The explicit return is mandatory. The shared template's tail returns null, and a null is
// reported as "Predicate rule must return Boolean, but returned: null", which the scheduler
// turns into a closed gate - forever, with nothing anywhere in the UI to show for it.
return n > 0
```

Two failures point in opposite directions and neither surfaces in the UI: a **blank** `predicateIdentifier`
defaults to TRUE and the action fires on every tick; a **broken** predicate (any exception on that hop)
evaluates to FALSE and the gate is shut for good. A third is worse than either, because it half-works: pointing
`predicateIdentifier` at an **EXECUTION** rule. Every rule's return value travels back in the response, and the
gate COERCES it — a `Boolean`, the strings `"true"` / `"1"` / `"yes"`, and any non-zero `Number` open the gate;
`false`, `"no"` and `0` shut it; a global attribute named `predicateResult` or `result` is consulted next; and
only a value none of those branches recognises (a List, a Map) falls through to "the call succeeded, so true".
So the gate is **unpredictable**, not permanently open — and the expensive work runs on the gate hop, every
tick. §4.2's own sweep ends `return opened`, an int: used as a gate it would do the whole sweep, then answer
"closed" precisely when it had opened nothing. The gate must be a PREDICATE; `validate` ERRORs on the wrong rule
type — read its output.

### 4.6 One process starting another

```groovy
// EXECUTION_RULE on a serviceTask of the FIRST process. Here - and only here - the context data
// is guaranteed non-null, and every process variable is readable through attrs.
def subjectId = context.data.getAttr("subjectId")
def owner     = attrs.get("owner")?.asText()      // attrs values are JsonNode

if (context.data.getAttr("decision") == "REJECTED") {
    service.workflow.start("b7c1d2ef-1111-4444-8888-000000000004", [
            contextDataMap: ["9c32d1ef-1111-4444-8888-000000000005": [
                    crudDataMap: [requests_cruid: [value: [id: subjectId]]],
                    attrs      : [:]
            ]],
            // the started case is a NEW process: it inherits nothing from this one
            attrs         : [subjectId: subjectId, parentTraceId: context.data.getAttr("_traceId")],
            // localeKey is a FIELD of the document, not an entry in attrs: nothing ever writes a
            // "localeKey" attribute, so context.data.getAttr("localeKey") is ALWAYS null and the
            // child case would fall back to the project default. Read the field itself.
            localeKey     : context.contextData?.localeKey
    ], [
            owner          : owner,          // otherwise the child is owned by whoever THIS task runs as
            roleGroups     : ["Compliance"],
            groupIdentifier: "5a90c1ef-1111-4444-8888-000000000006"
    ])
}

return true
```

⚠️ The call is **synchronous through the child's whole non-waiting head**: its start service tasks, gateways and
their rules all run before it returns. A failure in the child's first service task therefore comes back inside
**this** rule as `service.workflow.start('<id>'): Could not execute rule(s) '<ruleIds>': <messages>` — which is
the right place for it, but it also means a chain of processes starting processes blocks all the way down, and
nothing bounds that depth.

### 4.7 What a headless rule may touch

```groovy
// What a headless rule may and may not touch. Everything on the left throws or reads null.
def safeAttr   = attrs.get("anything")          // attrs is an EMPTY map, never null -> null
def safeGlobal = context.data.getAttr("x")      // root attrs exist -> null, no exception
def safeParam  = param?.anything                // param is an empty map outside a CRUD method

def rows = service.crud.requests_cruid.findAll([:])                    // works
def one  = context.requestContext.requests_cruid.service.get([id: 1])  // works: .service, not .data

// contextDataMap                          -> null; contextDataMap['x'] throws
// context.requestContext.data              -> "No context data available for context: requestContext"
// context.requestContext.requests_cruid.data -> "No CRUD data available for CRUD: requests_cruid"
return [safeAttr, safeGlobal, safeParam, rows?.size(), one?.id]
```

⚠️ `findAll([:])` binds `rowsInPage` and `pageNumber` as SQL NULL, which makes it an **unpaged full-table read**.
That is safe as a no-filter call and unbounded as a sweep: one tick can pull the whole table into the rule and
open a case per row. Sweeps page themselves, through a dedicated candidate method.

---

## 5 · Idempotency — the default failure

> ⛔ **Nothing asks it for you.** A sweep that fires every five minutes opens a new case for the same row
> every five minutes, forever, and **every screen still looks correct**.
>
> `service.workflow.list(...)` ([16](16-groovy-service-api.md) §2.13) can be made to answer *"does a process
> already exist for this row"* — but only if a process table INDEXES the key you would search on, and only at
> the cost of a query per trigger row. That is a real option when the worklist already indexes it. It is not
> the default answer: idempotency lives in the business data, where it is exact, free, and independent of any
> screen's configuration.

### 5.1 The symptom, so you recognise it

The worklist grows by N cases per tick. No error is raised anywhere: the rule returns normally, the executor
logs one INFO line per start, `validate` is green, the forms render, the data is right. The first thing that
usually reports it is the project's process quota, as
`Maximum number of active processes (N) reached for this project` — which reads like a platform limit rather
than the duplicate storm it is. Assume you have this bug until you have built the guard.

### 5.2 What does NOT work

| Non-solution | Why it fails |
|---|---|
| `businessKey: "REQ-" + row.id` | the column has **no unique index** and the platform never checks it; a blank one is auto-filled `<owner\|system>_<uuid>`. N identical keys produce N cases. It is a **search label**, not a key |
| `cooldownJob` | it gates the **schedule**, not the row; it is a next-cron-fire **timestamp**, not a duration; it is written whether or not the fire-and-forget action succeeded; and it is checked **before** the predicate, so a cooled-down schedule does not even evaluate its gate. It both under-protects (one row that qualifies across two windows still gets two cases) and over-protects (a second qualifying row inside the window is never processed at all) |
| "put the not-yet-processed filter in the predicate" | a predicate can only hand back a **boolean**, and the two hops use different transports — sync REST for the gate, async Kafka for the action — so the rows can change in between. The gate decides whether the tick runs; it cannot exclude anything for the action |
| a blank `predicateIdentifier` plus "it will rarely match" | blank defaults to **TRUE**: the action fires on every tick from the moment the project is imported |
| read the row, check a flag in Groovy, then start | a read-then-write window. Two overlapping ticks — or one tick and a manual action doing the same thing — both read `false` and both start |
| "the import resets it" | `save()` (which import calls) wipes `cooldownUntil` / `lastActionTime` first and then registers the trigger, so an imported `enabled:true` scheduler starts with **no** cooldown and fires on its first matching tick |

### 5.3 What does work — an atomic claim in the database

One conditional statement, `returnsArray:false`, ending in `RETURNING *`:

```sql
UPDATE requests SET state = 'ESCALATED', escalated_at = now()
 WHERE id = CAST(:id AS uuid) AND state = 'SENT'
 RETURNING *
```

It answers a row **Map** when this tick won and Groovy **`null`** when somebody else already claimed it — a real
`null`, not a JSON null object, so `if (claimed == null)` is the correct test. The chain that makes it one: a
`returnsArray:false` SQL method with no result row answers the JSON null node
(`DynamicMethodExecutor.mapResultSet`), the transport serialises that to the four characters `null`
(`CrudMethodController`), and the executor parses the response with `JsonSlurper` before handing it to the
script (`ReactorServiceImpl.executeCrudMethod`) — and `JsonSlurper.parseText("null")` is Groovy `null`. That
null is the only atomic primitive this platform gives an author, and it is what closes the window between
"read the row" and "start the process". Nothing offline exercises it: §8.3 step 4 — run the rule twice, expect
one case — is the only place this is ever tested. Three rules around it:

* **`RETURNING *` is not decoration.** A SQL method that produces no result set answers `[affected: n]` — always
  truthy — so an UPDATE without it cannot be tested by a null check.
* **A dedicated method, never the generated `update`** (§4.1). And keep the marker column out of `dtoFields`, or
  it turns up as a checkbox on generated forms ([10](10-database-management.md)).
* **Prefer a state transition to a boolean flag.** `state = 'SENT' → 'ESCALATED'` is the claim *and* the
  business meaning *and* what the candidate query filters on. A separate `case_opened boolean` works, but it is
  one more thing that can disagree with the state the user sees.

Then write the returned process identifier back onto the row. There is no read side, so that column IS the
answer for every later screen, rule and tick — and it is what makes the repair sweep below possible.

### 5.4 Claim first, and own the failure you chose

The chain is not transactional, so exactly one of two failures is possible and you pick which:

* **claim → start:** a crash between them leaves a row **claimed with no case**. Detectable
  (`state = 'ESCALATED' AND escalation_process_identifier IS NULL`), repairable, and it happens once.
* **start → mark:** a crash between them leaves a **case with an unmarked row**, which the next tick claims
  again — the duplicate storm, with no way to tell the duplicates apart.

Choose claim-first, and ship the repair as a second cheap rule (its own scheduler, or a manual action on the
list page):

```groovy
// EXECUTION_RULE - the repair sweep. The chain is not transactional, so a row can be CLAIMED and
// then fail to get its case. That is the failure direction to choose: a case that was never
// opened is repairable from the data, a case opened on every tick is not.
def orphans = service.crud.requests_cruid.findClaimedWithoutProcess([
        rowsInPage: 50, pageNumber: 0
]) ?: []

for (row in orphans) {
    def pid = service.workflow.start("a3f2c1de-1111-4444-8888-000000000001", [
            contextDataMap: ["8b21c0de-1111-4444-8888-000000000002": [
                    crudDataMap: [requests_cruid: [value: [id: row.id, docNumber: row.docNumber]]],
                    attrs      : [:]
            ]],
            attrs         : [subjectId: row.id as String, subjectLabel: row.docNumber],
            localeKey     : (row.preferredLocale ?: "en_US")
    ], [
            roleGroups     : ["Back office"],
            groupIdentifier: "7c40b0de-1111-4444-8888-000000000003"
    ])
    service.crud.requests_cruid.setEscalationProcess([id: row.id, escalationProcessIdentifier: pid])
}

return orphans.size()
```

The same query is the honest answer to "the service was down and ticks were lost": the backlog is re-detected
from the data on the next tick, because the candidate query never depended on having seen the tick that created
the work.

### 5.5 When the sweep must fire more than once per row

§5.3 answers *"once per subject, ever"* — a one-way transition, `SENT → ESCALATED`, and the row is spent. That
is only one of the three answers [19](19-build-decision-procedure.md) Phase 1 demands: the other two are **once
per period** and **every time the condition holds**, and a PRD sentence like *"chase unanswered requests at the
configured interval and escalate after N attempts"* asks for both at once. Copy §5.3 for that and you ship a
one-shot escalation: the claim can fire once, so attempts 2..N never happen, and no gate anywhere notices.

A boolean marker cannot express either shape — it holds one bit, and the question has a **count** and a
**clock**. The primitive does not change; what you claim does. Make the claim per **(row, step)** instead of per
row, with the counter and the timestamp as the thing the single conditional statement wins:

```sql
-- claimNextChase  (SQL, returnsArray:FALSE) - claims attempt N of at most :max_attempts, and never
-- twice inside one :chase_interval. Both guards are in the WHERE, so two overlapping ticks cannot
-- both win - exactly the 5.3 primitive, with a counter instead of a state.
-- parameters[]: id, max_attempts, chase_interval  (declare all three - §4.1)
-- COALESCE, not chase_attempts alone: on a NULL counter the increment yields NULL and the guard
-- evaluates to NULL, which is not TRUE - the row is never claimed and nothing is ever logged.
UPDATE requests
   SET chase_attempts = COALESCE(chase_attempts, 0) + 1,
       last_chased_at = now()
 WHERE id = CAST(:id AS uuid)
   AND state = 'SENT'
   AND COALESCE(chase_attempts, 0) < :max_attempts
   AND (last_chased_at IS NULL OR last_chased_at < now() - COALESCE(CAST(NULLIF(:chase_interval,'') AS integer), 3) * INTERVAL '1 day')
 RETURNING *
```

⛔ **The `COALESCE` is the whole statement's life.** A counter column is nullable unless somebody declared it
otherwise, and every row imported before the ladder existed has NULL in it. `chase_attempts + 1` on NULL is
NULL, and `NULL < :max_attempts` is NULL — **not** TRUE — so the `WHERE` matches nothing: the claim returns
no row, the rule takes its `continue`, the reminder never goes out, the case never opens, and there is no
error anywhere to say so. That is exactly the failure class this section exists to prevent, and it survives
every offline gate. Declare the pair as `chase_attempts integer NOT NULL DEFAULT 0` and `last_chased_at
timestamptz NULL` in Phase 2 ([19](19-build-decision-procedure.md), the trigger columns) — then the
`COALESCE` is redundant, and keep it anyway, because the column contract is one hand-edit away from being
untrue and this statement fails silently when it is — and the paired candidate query (`findChaseCandidates`)
filters on the same counter, so it needs the same `COALESCE` or it hands the claim a set that is already
missing every un-chased row. `last_chased_at` **is** meant to be NULL on a row that has never been chased,
which is why its guard is an explicit `IS NULL` rather than a `COALESCE`.

`RETURNING *` answers the row **after** the increment, so the returned `chaseAttempts` is the number of the
attempt this tick won — and that one value is what lets the mail-per-tick shape and the case-once shape live in
the same rule:

```groovy
// EXECUTION_RULE - the chase ladder. ONE claim per (row, attempt): the reminder goes out on every
// tick the row qualifies for, and the CASE is opened exactly once, on the tick that crosses the
// last attempt. Same primitive as 5.3 - the claim just carries a counter and a clock.

// Policy, not code (§4.1): both values come from the business, so neither is a literal here.
def policy       = service.crud.escalation_policy_cruid.get([id: 1])
int maxAttempts  = ((policy?.maxChaseAttempts ?: 3) as Number).intValue()
String interval  = (policy?.chaseInterval ?: "24 hours") as String

def rows = service.crud.requests_cruid.findChaseCandidates([
        chase_interval: interval,
        rowsInPage    : 200,
        pageNumber    : 0
]) ?: []

int chased = 0
for (row in rows) {
    // THE CLAIM - both guards live in the WHERE, so two overlapping ticks cannot both win, and the
    // same row cannot be chased twice inside one interval. RETURNING * answers the row AFTER the
    // increment, so claimed.chaseAttempts IS the attempt number this tick won.
    def claimed = service.crud.requests_cruid.claimNextChase([
            id            : row.id,
            max_attempts  : maxAttempts,
            chase_interval: interval
    ])
    if (claimed == null) { continue }   // somebody else won it, or the interval has not elapsed yet
    chased++

    int attempt = (claimed.chaseAttempts as Number).intValue()

    // EVERY attempt sends its reminder - the "every time the condition holds" half.
    service.notification.mail.recallChaser([claimed.contactEmail as String], [
            docNumber: claimed.docNumber as String,
            attempt  : attempt as String
    ])

    // The CASE opens only on the transition that crosses the last attempt - once per row, ever.
    if (attempt >= maxAttempts) {
        def pid = service.workflow.start("a3f2c1de-1111-4444-8888-000000000001", [
                contextDataMap: ["8b21c0de-1111-4444-8888-000000000002": [
                        crudDataMap: [requests_cruid: [value: [id: claimed.id, docNumber: claimed.docNumber]]],
                        attrs      : [:]
                ]],
                attrs         : [subjectId: claimed.id as String, subjectLabel: claimed.docNumber,
                                 attempts : attempt as String],
                localeKey     : (claimed.preferredLocale ?: "en_US")
        ], [
                roleGroups     : ["Back office"],
                businessKey    : "ESC-" + claimed.docNumber,
                groupIdentifier: "7c40b0de-1111-4444-8888-000000000003"
        ])
        service.crud.requests_cruid.setEscalationProcess([
                id                         : claimed.id,
                escalationProcessIdentifier: pid
        ])
    }
}

return chased
```

Two columns, and all three answers become expressible:

| The PRD says | What the claim's WHERE holds | What opens the CASE |
|---|---|---|
| "once, when it happens" | a state transition (§5.3) | the claim itself |
| "once per period" | `last_chased_at < now() - COALESCE(CAST(NULLIF(:chase_interval,'') AS integer), 3) * INTERVAL '1 day'` | the claim itself, once per window |
| "N attempts, then escalate" | both guards above | only the tick on which `chase_attempts` reaches `:max_attempts` |

⚠️ `:max_attempts` and `:chase_interval` are **parameters**, never literals: they are policy the business owns
(§4.1). Declare **all three** — `id`, `max_attempts`, `chase_interval` — in the method's `parameters[]`: a
placeholder that is not declared is bound by nothing and reaches the database as the literal text `:name`, which
fails the whole statement, not just that clause. And the interval belongs in the SQL, not in the cron — the cron
only decides how soon after the interval elapses anybody notices.

---

## 6 · Making the case findable

A rule-started case has no starting node and no submitting user, so **everything that makes it visible is
something you passed**. Only five option keys are read; anything else — `roleGroup`, `group`,
`processGroupIdentifier` — is ignored without a word.

| Option | Obligation | What omitting it costs |
|---|---|---|
| `groupIdentifier` | **Mandatory** whenever the worklist is group-scoped, which is the arrangement [07](07-workflows-and-tasks.md) prescribes. Pass the identifier authored in `rep-objects.processGroups[]` — the same one the `process.table.pluin` node and its settings mirror carry | the case is created with `group = null`, and the worklist's INNER join on the group excludes it **for everyone, admins included**, with nothing logged. A dangling identifier behaves identically: the lookup returns null, a warning is logged server-side, the start succeeds |
| `owner` | Defaults to the user the rule runs as — for a scheduler tick, the schedule's `serviceUserEmail`. Pass it explicitly when the case belongs to somebody other than the service identity | the process is **never ownerless on a stock deployment**: with no acting user at all the platform assigns the project's **configured author account**, writes its owner access row and its `owner` process variable — so the risk there is not "nobody sees it" but "**one wrong account** owns it", and since `owner` is the identity a service task executes as until the first user task is completed (after that the last assignee wins), `service.security.user()` in the case's opening tasks returns the author, not the person it is about. ⚠️ That fallback is a **configuration value whose in-code default is EMPTY**, and blank **disables** it: on a deployment that blanks it the case gets **no owner USER row and no `owner` process variable**, and is reachable only by admins and authors ([07](07-workflows-and-tasks.md) "A rule-started process has no BUSINESS starter"). Nothing in the export tells you which of the two you are shipping onto — which is why you pass `owner`/`roleGroups`/`emails` rather than inherit one |
| `roleGroups` | The people who work the queue. Matched by **name, exactly**; a single String is accepted where a list is expected | a misspelled name produces an access row that can never match, and nothing says so. Copy the name from the project's role groups |
| `emails` | Individuals. Trimmed but **never case-folded**, and matched character-for-character against the token's `email` claim | `Anna.Smith@example.com` in the rule and `anna.smith@example.com` in the identity provider are two different rows: the case is invisible to the very person it was opened for |
| `businessKey` | A human key — `"ESC-" + docNumber`. Generated as `<owner\|system>_<uuid>` when omitted | the free-text Search box is on the **admin Processes console**, not on a worklist page, and it is a lowercase LIKE over `businessKey` alone — so a generated key costs you that console's search. A worklist has no free-text search at all: it filters through its filter form and `filterExpression` over `paramsToFilter`, which a programmatic start leaves EMPTY (see the index bullet). The key is still **not** a de-duplication key (§5) |

Four more things that decide whether the case is usable:

* **Index columns start blank; the COLUMNS do not.** A `process.table`'s index (`paramsToFilter`, and the
  `filterExpression` built on it) is filled from the start FORM's index settings; a programmatic start supplies
  none, so a rule-started case is unfilterable by index until its first user-task action backfills it. Its
  **columns** are a different mechanism and are live immediately: each one renders whatever the case's context
  data document carries **at its own scope** — `scope: GLOBAL` reads the document's root `attrs`, `scope:
  CONTEXT` reads the named context's `attrs`, `scope: CRUD` reads that alias's `value` inside that context's
  `crudDataMap`. All three resolve against the document the rule passed, so a blank column means the rule
  published nothing under the key the column names, never that the scope is wrong.
  ⛔ **Five `fieldExpression`s never reach your `attrs`:** `businessKey`, `workflowName`, `status`,
  `identifier`, `id` are intercepted by the GLOBAL branch and answered off the **process row itself**;
  everything else falls through to the document's root `attrs`. So an attribute published under one of those
  five names is not blank — it renders the *process's* value instead of yours, which reads as data that is
  merely wrong. Never publish a root attribute under one of them: prefix it (`subjectStatus`, `subjectId`).
  Prefer `scope: GLOBAL` over the root `attrs` for the identifying columns anyway, for a reason that has
  nothing to do with resolution: a CRUD column is the start document's **snapshot** of the row — the plugin
  reads the process's context data, never the table — so it stops agreeing with the row the moment anything
  writes that row without writing the document back, and it shows nothing at all for an alias the rule never
  seeded. This is why §4's document always carries an `attrs` block
  ([07](07-workflows-and-tasks.md) Rule 6, [16](16-groovy-service-api.md) §2.12,
  [05](05-crud-tree-and-process-table.md)
  §"Field-by-field: `ProcessTableFormControlSettings`").
* **admin and nct_author ROLE access is granted on every programmatic start.** Testing the worklist while
  logged in as the author proves nothing at all — that account matches a role row on every process in the
  project. Test as a member of the role group you passed, and remember that role-group membership is cached for
  about a minute after a grant.
* **Provenance is stamped for you** and cannot be forged: `startedByRuleIdentifier`, `startedByRuleName`, and
  for a CRUD method `startedByCrudAlias` + `startedByMethodName`, as root attributes written **after** your
  document. Read them downstream as `context.data.startedByRuleName` — the cheapest audit hook the chain has,
  and a good worklist column for telling a swept-in case from a human one.
* **`localeKey` belongs in the document, not the options** — and it is a top-level FIELD of the document, not
  an entry in `attrs`, so nothing ever answers it through `getAttr("localeKey")` (§4.6). Omit it and every
  localized message and mail the case sends comes out in the project's default language
  ([20](20-localization.md)). When the case's correspondence is addressed to a **subject** — a customer, a
  counterparty — the value is that subject's own language read off the claimed row
  (`localeKey: claimed.preferredLocale ?: "<default>"`), not a literal. A literal here is the "every letter came
  out in one language" bug: `validate` cannot see it, no screen shows it, and it surfaces on the first live
  send.

⚠️ A rule can never start a process in another project: the call runs against the running rule's own realm and
client. It does run under the internal service token, which is why it works on threads with no HTTP request —
a scheduler tick, a service-task callback.

---

## 7 · Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| **Nothing happens at all** — no case, no trace | the schedule never registered: `enabled` is false, or `job.expression` is blank. Registration needs **both** | set both; remember an `enabled:true` scheduler fires the moment the project is imported (§3) |
| Nothing happens, and the cron is right | the gate is shut: the predicate rule throws (any exception on that hop evaluates to **false**), or its body has no explicit `return <Boolean>` — the shared template's tail returns null and that is reported as *"Predicate rule must return Boolean, but returned: null"* | end the predicate with `return <boolean expression>` (§4.5); test it as a rule before wiring it |
| Nothing happens, intermittently | the schedule is in **cooldown**, which is checked **before** the predicate — an urgent condition arising inside the window is not noticed until it expires. `cooldownJob.expression` is a cron whose **next fire time** becomes the mute-until timestamp, so `0 0 0 * * *` means "until midnight", not "for 24 hours" | leave `cooldownJob.expression` blank and let the claim (§5) do the work |
| **It fires on every tick**, condition or not | blank `predicateIdentifier` defaults to **TRUE**; or `predicateIdentifier` points at an **EXECUTION** rule, whose return value the gate COERCES — non-zero number, `"true"`/`"1"`/`"yes"`, `Boolean` = open; `0`/`false`/`"no"` = shut; a List or a Map = "the call succeeded, so true" — so the gate is unpredictable rather than stuck, and the expensive work runs on the gate hop besides (§4.5) | author a PREDICATE and point at it; `validate` ERRORs on the wrong type |
| The rule runs and **does nothing** | it read `contextDataMap[...]` or `context.<ctx>.<alias>.data` and died on line 1 — the exception is swallowed into a FAILURE response, so all that exists is an error line in the executor log; or it guards itself with `service.security.hasAnyRoleGroup(...)` while the schedule has no `serviceUserId`, which returns **false** with no error; or it reads `param.x`, which is null in a headless rule | §2.1, §4.7. Fetch everything through `service.crud.*`; drop role guards from headless rules; set `serviceUserId`/`serviceUserEmail` on the schedule |
| `service.workflow.start is not available in predicates …` | the start was written into the gate | split trigger / gate / action into three objects (§4.5); `validate` ERRORs on it |
| `Could not find workflow with identifier '<id>'` (404) | the first argument is the workflow **name**, or a UUID from another project | use `rep-objects.workflows[].identifier`; `validate` ERRORs when the literal is not in `workflows[]` |
| `Workflow '<id>' exists but is not deployed` (409) | import forced `deployed:false` — the normal state of **every** freshly imported project | open the BPMN editor and press **Deploy**; `validate` WARNs when the target is `deployed:false` |
| `service.workflow.start: the context data must be a map, got ArrayList` | `[]` was written where the empty map `[:]` belongs | `[:]` everywhere a map is meant — both `attrs` slots included |
| `service.workflow.start: the context data map could not be read - …` | the document's shape does not bind (a list where an object belongs, a scalar under `crudDataMap`) | compare against §4.2; the three levels are `contextDataMap` → `crudDataMap` → `value` |
| `Maximum number of active processes (N) reached for this project` | the project's process quota, not your code — usually the visible end of a per-tick duplicate storm | fix idempotency (§5) before raising the quota |
| **The case opens but nobody can see it** | no `groupIdentifier` (or a dangling one) while the worklist is group-scoped; or `roleGroups` misspelled; or `emails`/`owner` differ in letter case from the login email | §6. All four are silent; the only server-side hint is a WARN naming the starting rule, and it is logged only when acting user, role groups and emails were **all** absent |
| The worklist shows rows, and **every column is blank** | on a rule-started case all three scopes DO resolve — GLOBAL from the document's root `attrs`, CONTEXT from that context's `attrs`, CRUD from the `crudDataMap` the rule seeded. Blank therefore means the rule published nothing under the key that column names: an empty root `attrs`, or a context identifier / crud alias that never matched | publish the identifying values in the document's root `attrs` and point the columns at them with `scope: GLOBAL` — not because the other scopes fail, but because a CRUD column is a snapshot that goes stale as soon as a service task writes the row (§6) |
| One column shows a value nobody published — the process's own status, id or workflow name | that column's `fieldExpression` is one of the five names the GLOBAL branch intercepts before it ever looks at your `attrs`: `businessKey`, `workflowName`, `status`, `identifier`, `id`. A GLOBAL column on one of them is **never blank** — it answers off the process row — so a root attribute of the same name is unreachable and the cell silently disagrees with the data (§6) | rename the attribute and the column together: `subjectStatus`, `subjectId`, `subjectRef` |
| The first service task throws **`No CRUD data available for CRUD: <alias>`** (from `context.<ctx>.<alias>.data`) or **`No context data available for context: <alias>`** (from `context.<ctx>.data`) | the same cause, seen through two different reads, and it is **not** a missing alias: the document has no entry under that CONTEXT's identifier — a mistyped identifier key, a rule that forwarded a null `contextDataMap` (§4.3), or a rule running headless. Note that the *context-data* message names the context's **alias** while the map key is its **identifier** — the CRUD message names the crud alias, which is the same string you wrote | fix the context identifier key, or BUILD the document instead of forwarding it. A wrong crud alias is the next row, not this one |
| A service task runs, throws nothing, and **writes nulls** | the crud ALIAS inside `crudDataMap` is missing or misspelled. Before the script runs the executor auto-creates an EMPTY envelope for every alias of every attached context **the document already has an entry for**, so `.data.get()` answers `[:]`, everything derived from the row is null, and the start reported success (§3 step 4). A context the document never mentions gets no envelopes at all — that is the row above, and it throws | seed **every** alias the first tasks read, even all-null; if you copied the document from a form's **Get context data** popover, use plain **Copy**, not **Trim & copy**, which removes all-null envelopes |
| A rule throws `No context found with alias: X` | the RULE does not list that context in its `contextIdentifiers` | attach the context, or address the CRUD as `service.crud.<alias>` |
| A rule throws `No CRUD found with alias: X in context: Y` | the alias is not in that context's `crudAliases[]` | `context add-alias <ctx> <alias>` |
| **A case per tick**, the queue grows forever, no error anywhere | there is no claim | §5 |
| The whole chain works locally and not after import | the workflow was not re-deployed; **or** the process group identifier differs between the node and the rule; **or** `serviceUserEmail` names an account that does not exist in the TARGET tenant — nothing checks that it does | §3, §6 |
| Mail from the case is in the wrong language | the start document carried no `localeKey`; or it carried a hard-coded one where the letters are addressed to a subject; or it read it with `getAttr("localeKey")`, which is always null — `localeKey` is a document FIELD, not an attribute | pass the subject's own language from the claimed row, or `context.contextData?.localeKey` when forwarding (§4.6, §6) |

---

## 8 · Verify

### 8.1 What `mrjun.py validate` catches

* the scheduler's `predicateIdentifier` is a **PREDICATE** and its `actionRuleIdentifier` an **EXECUTION_RULE**
  (wrong type = ERROR, dangling = WARN; no action rule at all = WARN);
* the cron is Spring 6-field `sec min hour dom mon dow`; a Quartz-only `?` / `L` / `W` / `#` = ERROR;
* `enabled:true` with a non-blank cron = WARN — it auto-registers and fires on import;
* a duplicate scheduler `name` = ERROR (the unique index makes the second save throw, and schedulers are saved
  before workflows, rules, contexts, forms and settings, so everything after them is skipped);
* `service.workflow.start` inside a **PREDICATE** or **VALIDATION_RULE** = ERROR;
* `service.workflow.start("<literal>")` whose identifier is in no `workflows[]` entry = ERROR; on a
  `deployed:false` workflow = WARN. Both checks also read **CRUD GROOVY method** bodies, since a method is a
  first-class caller;
* a `process.table` **column** whose `scope:"CRUD"` alias no start form and no start rule seeds = WARN; the
  same for an **index**, which is stricter — a rule-seeded alias does not clear it, because a programmatic
  start passes no index settings at all (§6). A `scope:"CRUD"` entry naming **no** `crudAlias` is a third,
  separate warning: it carries nothing whatever the case holds;
* a rule a **SCHEDULER names** — its `actionRuleIdentifier` or its `predicateIdentifier` — that reads the bare
  `contextDataMap` binding = **ERROR**. Neither scheduler hop attaches context data, so that binding is null in
  both: `[contextDataMap: contextDataMap]` starts an EMPTY process while still returning a process identifier,
  and in a gate the same read throws, which the scheduler reports as FALSE and the gate stays shut. The check
  strips comments first, leaves alone any body that declares, assigns or null-guards the name (that author
  already knows), and looks only at rules a scheduler names — an ordinary form or process rule receives a real
  document and uses the shortcut correctly.

### 8.2 What only a live run catches

Nothing offline runs a rule, so everything below stays green in a broken chain:

* **whether the chain is idempotent** — a candidate filter, a claim method and a marker column are just data;
* **whether `groupIdentifier` matches the worklist node's group** — it is a string inside a Groovy body;
* **whether the context identifier and crud aliases inside the document are the right ones** — same reason,
  and the two halves fail differently. A wrong **envelope** key (`contextDataMap` / `crudDataMap` / `value` /
  `attrs`) is dropped by Jackson without a word; a wrong crud **ALIAS** is silent too — it is auto-envelope'd
  empty and the task computes nulls (§3 step 4); the **CONTEXT IDENTIFIER** is *not* silent, but it fails late
  and far from the rule: the first service task that reads `.data` throws
  `No CRUD data available for CRUD: <alias>` (§7);
* **whether `serviceUserEmail` exists in the target tenant** — nothing checks, and the case ends up owned by an
  address nobody can log in as;
* **whether the workflow was deployed after import** — it never is, until a human does it;
* a `start(...)` whose first argument is a variable or a GString — deliberately unchecked.

One item that looks like it belongs here does **not**: **whether a hand-authored SQL method declares every
`:name` its statement binds**. `validate` never checks `parameters[]` for a SQL method, but
**`crud verify --db`** ([26](26-orchestration-and-testing.md) §3 T3) substitutes only the DECLARED parameters,
so an undeclared placeholder reaches PostgreSQL verbatim and the method FAILS by name in that gate — no live
run needed (§4.1).

### 8.3 The live acceptance run

Follow [26](26-orchestration-and-testing.md) §5, with these steps added for this chain:

1. Import. Open the **BPMN editor** and press **Deploy** on the workflow — every imported workflow is a draft.
2. Confirm the process group exists and that the worklist node's `processGroupIdentifier` is the same string the
   rule passes. Both are visible offline; check them again here because the auto-creation path rewrites the node.
3. Run the action rule **once, by hand**, from the rule editor before enabling any scheduler. Exactly **one**
   case must appear on the worklist.
4. Run it a **second** time without changing any data. Still exactly one case. **This is the idempotency test,
   and nothing else in the toolchain performs it.**
5. Enable the scheduler with a short cron, wait for two ticks, and count again.
6. Open the worklist as a user who is **not** an admin, not an author and not the account in `owner`. The case
   must be there, and its columns must be populated.
7. Open the case. Its first user task must render with real values — blank fields mean the document under-seeded
   the process (§7).

### 8.4 Reading the logs

* **`log/ui.log`** is the **import** side. What matters here: a Jackson `MismatchedInputException` /
  `InvalidFormatException` means the whole rep-objects block aborted, so your scheduler, workflow, rules and
  contexts may never have been saved at all — and the visible symptoms (an empty context, "No source selected",
  missing data) look like three unrelated bugs ([00](00-export-format-and-import.md),
  [23](23-distribution-and-known-gaps.md) §2).
* **The runtime side is in the scheduler and executor service logs**, where the recipient has them. Search for
  `[SCHEDULER]` — it logs registration, every tick, the cooldown skip, the predicate result and the Kafka send;
  and for `[EXECUTOR]` — it logs receiving the tick and whether the action rule succeeded, and it is the ONLY
  place a failed action rule is ever mentioned. A successful start also logs the rule, the process and the
  workflow.
* The one line that names an invisible case is a WARN saying a process *"was started from '<rule>' with no
  acting user, no role groups and no emails — it is reachable only by admins and authors"*. It may overstate
  the situation, but not for the obvious reason: it is logged **after** the start, and its condition tests the
  acting-user value the CALLER passed, not the owner the platform ended up assigning — so it fires just the
  same on a deployment where the author-account fallback DID give the case an owner, and it is exactly right on
  one where that fallback is blanked out (§6). It never appears if you passed even one of the three.

---

## 9 · Done when

- [ ] Every process in the Phase 1 inventory carries a **"what starts it"** value: `FORM` / `SCHEDULER` /
      `CRUD METHOD` / `SERVICE TASK` (§1)
- [ ] No workflow has both a start form and a rule that starts it — the two shapes are a choice, not a pair
- [ ] The workflow exists, and the hand-over notes say **Deploy it after import** (§3)
- [ ] `rep-objects.processGroups[]` carries the group, with the **same** identifier in the `process.table.pluin`
      node model, in its settings mirror and in the rule's `groupIdentifier` (§3, §6)
- [ ] The worklist page exists, is linked in the left nav, and every column names a scope the starting rule
      actually publishes — `scope: GLOBAL` over the root `attrs` (the default choice), or `scope: CONTEXT`
      naming the context whose `attrs` block the rule filled (§6) — and **no** root attribute is named
      `businessKey` / `workflowName` / `status` / `identifier` / `id`: a GLOBAL column on those five is answered
      off the process row, so such a column shows the process's own value and never yours (§6, §7)
- [ ] Every crud alias the started process's first tasks touch is in the context's `crudAliases[]` **and**
      present in the document, even all-null — a missing alias throws nothing, it just hands the task an empty
      row, while a missing CONTEXT entry throws in the first service task (§3 step 4, §4, §7)
- [ ] The document has both `attrs` slots (root and per context), written `[:]` and never `[]`
- [ ] `localeKey` is carried **only when the case writes to a person AND the subject has a language column** —
      read it off the claimed row; OMIT the key entirely when it does not (everything falls back to the project
      default, which is right for a case nobody writes to). Never a literal, and never through
      `getAttr("localeKey")` — it is a document FIELD, so that read is always null (§4.2, §4.6, §6)
- [ ] The starting rule is an **EXECUTION_RULE**; the scheduler's gate is a separate **PREDICATE** that ends in
      an explicit `return <Boolean>` (§4.5)
- [ ] The candidate query **excludes** what the sweep has already opened, and a dedicated `RETURNING *` claim
      method — not the generated `update` — makes the claim atomic (§5)
- [ ] Every `:name` in every hand-authored SQL method appears in that method's `parameters[]` — `crud
      add-method` writes `parameters: []`, `validate` never checks it for a SQL method, and `crud verify --db`
      is the one gate that does (§4.1)
- [ ] The idempotency requirement was written down as one of "once ever" / "once per period" / "N attempts then
      escalate", and the claim's WHERE carries the counter and the interval the last two need — with the counter
      `COALESCE`d, or declared `NOT NULL DEFAULT 0`, since a NULL counter makes the claim match nothing and say
      nothing (§5.3, §5.5)
- [ ] No business deadline is a literal inside SQL and none is encoded as the cron period — the cron is the
      polling frequency, the deadline is data (§4.1)
- [ ] The started process identifier is written back onto the row, and a repair query exists for
      "claimed, no process" (§5)
- [ ] The scheduler ships `enabled:false` unless the trigger is meant to be live the instant the project is
      imported; its cron is Spring 6-field; its `name` is unique in the project (§3, §8.1)
- [ ] **At least one** of `owner` / `roleGroups` / `emails` is passed — the author-account fallback is a
      configuration value, not a guarantee, so an omitted set can leave the case reachable only by admins and
      authors (§6)
- [ ] The case is reachable by a `roleGroups` name authored in **this** project — the only visibility key a
      file-first build can verify offline. `serviceUserId` / `serviceUserEmail` / `owner` / `emails` are all
      addresses in the TARGET tenant, and nothing in the export can check any of them, so an `owner` that does
      not exist there is exactly as unreachable as a bad `serviceUserEmail` (§2.1, §6)
- [ ] `mrjun.py validate --project <dir>` exits 0 and its scheduler / `workflow.start` findings were read (§8.1)
- [ ] **Live:** the action rule was run twice by hand and produced exactly **one** case (§8.3) — nothing else
      tests this
- [ ] **Live:** a non-admin, non-author member of the passed role group opens the worklist and sees the case
      with populated columns (§8.3)

---

**See also:** [19](19-build-decision-procedure.md) (Phases 11–12 route here) ·
[07](07-workflows-and-tasks.md) (BPMN, the worklist, shape C, the process binding contract) ·
[16](16-groovy-service-api.md) §2.12 (the `start(...)` call, its options and the generated snippet) ·
[12](12-queries-sources-schedulers-and-rest.md) §3 (`ScheduleDto`, the cron dialect, the two-hop pipeline) ·
[11](11-business-logic-dynamic-crud.md) (CRUD methods, `param`, the paging and return shapes) ·
[08](08-groovy-rules-and-context.md) (rule types, templates, return semantics, numbers) ·
[05](05-crud-tree-and-process-table.md) (`process.table.pluin`, columns, the process group) ·
[10](10-database-management.md) (the marker column, soft vs hard delete) ·
[20](20-localization.md) (`localeKey` and localized text) ·
[26](26-orchestration-and-testing.md) (per-module tests, the live acceptance loop, the coverage ledger) ·
[23](23-distribution-and-known-gaps.md) (what `validate` still cannot check) ·
[`tools/README.md`](tools/README.md) (`rule add`, `workflow add`, `crud add-method`, `validate`, `pack`)
