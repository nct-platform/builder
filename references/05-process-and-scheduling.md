# 05 — Processes, worklists and schedulers

> **Corrects and extends** [[07-workflows-and-tasks.md](../07-workflows-and-tasks.md)](../07-workflows-and-tasks.md),
> [[27-event-driven-process-start.md](../27-event-driven-process-start.md)](../27-event-driven-process-start.md) and
> [[12-queries-sources-schedulers-and-rest.md](../12-queries-sources-schedulers-and-rest.md)](../12-queries-sources-schedulers-and-rest.md).
> Read out of four delivered exports: **21 workflows · 38 user tasks · 32 service tasks · 10 gateways ·
> 47 user-task actions · 43 schedulers · 15 `service.workflow.start` call sites.**

| | A (largest) | B | C | D (smallest) |
|---|---|---|---|---|
| workflows | 7 | 5 | 8 | 1 |
| …with a worklist page | **0** | 5 | 8 | 1 |
| …with anything that **starts** them | **0** | 5 | 8 | 1 |
| `deployed` in the export | false ×7 | true ×5 | false ×8 | true |
| distinct `<process id>` keys | `Process_1` ×6 ⛔ | `Process_1` ×5 ⛔ | unique ✅ | unique ✅ |
| schedulers | 27 | 2 | 10 | 4 |
| …with a PREDICATE gate | **0/27** | 2/2 | 10/10 | 1/4 |
| …shipped `enabled:true` | **27/27** ⛔ | 0/2 | 0/10 | 4/4 |
| …that open a case | 0 | 0 | 3 | 1 |
| atomic claim methods | 0 | 0 | 3 | 1 (+repair, +release) |

**Settled in all four — do not re-litigate per project:**

- Every scheduler is `actionType: "RUN_RULE"`. There is no other value in any export.
- Every cron is **Spring 6-field** (`sec min hour dom mon dow`). 43/43.
- `cooldownJob.expression` is **never** set (0/43). Idempotency lives in the data (§5), never in a cooldown.
- **`candidateGroups`, `candidateUsers`, `assignee`, `formKey` are empty on all 38 user tasks.** Nobody uses
  the engine's candidate inbox: who may press a button is the action's `predicateIdentifier`; who can see the
  case is the process access rows.
- **Zero** boundary events, timers, message events, parallel/inclusive gateways, call activities and
  sub-processes. The entire modelled vocabulary is `startEvent`, `userTask`, `serviceTask`,
  `exclusiveGateway`, `sequenceFlow`, `endEvent`. Plan for that and nothing else.
- `validationRuleIdentifiers` on an action: **0 of 47.** Preconditions are a `throw` inside the
  `onBeforeUserTaskCompleteRuleIdentifier` rule.
- The only `service.workflow.*` method ever called is **`start`** (15 sites). `service.workflow.list` is never
  used — including where idempotency needed an answer. The claim column won that argument every time.
- Exactly one `<startEvent>`; several `<endEvent>`s are fine and used.

---

## 1. What earns a BPMN workflow rather than a status column

Read what the four **built**, not what they drew: every workflow that survived contact with a user has all
three of — a human queue somebody works from, at least one decision the process itself makes, and a subject
that outlives a single screen. Everything with only one of those was built as a **status column + a
crud-table action + an EXECUTION rule**, and there are hundreds of those against 21 workflows.

> **The operational test:** is there a page whose whole job is *"here is the work waiting for you"*, and does
> the row on it move between people? If yes — a workflow. If the record just changes state and the same
> person carries on — a lifecycle action on the entity's own table.

Two calibration points:

- The largest delivery has 163 CRUDs and a task register with priority, due date, assignee and an automatic
  escalation ladder — and it was **right** not to make that a workflow: one row, one owner, one transition.
  It then authored five BPMN diagrams for its genuinely multi-party processes and shipped **every one inert**
  (§8). The judgement about which processes deserve a workflow was right; the follow-through was absent.
- The smallest delivery has exactly one workflow and it earns it on every count: seven human steps across
  four role groups, three decisions, a rework loop, a postpone path, and a subject that lives for days. One
  workflow, one worklist, one process group, one starter.

⛔ **A step whose only content is "run some Groovy" is not a reason to open a case.** The largest delivery
does recomputation, ageing, escalation and notification for a 433-page system with **zero** running
processes. Automation ≠ process.

---

## 2. How a case is really opened

All 15 start sites are **`EXECUTION_RULE`s**. Not one is a CRUD GROOVY method; not one is a start form. The
`userStartProcessActions` bucket is **empty on 14 of 14 real worklists**.

> **The strongest convention in this slice: the worklist does not start the case. The register does, or the
> clock does.**

| starter | sites | where the rule hangs | idempotency guard |
|---|---|---|---|
| **document lifecycle action** (a register row's Submit / Propose / Register) | 10 | `onBeforeCompleteRuleIdentifier` of a crud-table action | the status gate **plus** an empty write-back column |
| **scheduler sweep** | 4 | `actionRuleIdentifier` of the schedule | an atomic `UPDATE … RETURNING *` claim (§5) |
| **user-task action of another case** | 1 | `onBeforeUserTaskCompleteRuleIdentifier` | the write-back column being empty |
| **start form** | **0** | — | — |
| **service task of another case** | **0** | — | — |

Take both zeroes seriously. **Nobody built a start form**: in all four the subject of a case is a document
that already exists, so every case is opened by a rule and the subject is bound by a GLOBAL attribute the
rule publishes. Build for that by default; reach for a start form only when the case genuinely predates any
record.

And **the sub-case spawn hung off a user ACTION, not a service task.** Doc 27 nominates a service task for
"when the previous process reaches X"; putting it on the action's complete rule is strictly better — a
service task fires on every token that reaches it, an action's rule fires only on the branch a human chose,
and it can refuse in the same breath.

### 2.1 The document-action starter — the block to copy

Appears 10 times across two deliveries, the same shape every time:

```groovy
// ── inside the register action's onBeforeCompleteRuleIdentifier, AFTER the state transition ──
// 1. the status gate is what makes the ACTION legal at all
def doc = context.<ctx>.<alias>.data.get()
if (doc == null || doc.id == null) { throw new RuntimeException("Select a document first") }
if (doc.status != 'DRAFT') {
    throw new RuntimeException("Only a DRAFT document can be submitted (current: " + doc.status + ")") }
service.crud.<alias>.submit([id: doc.id.toString(), actor: actor])

// 2. the case-already-open gate — two independent forms; carry both where you can
if (context.data.getAttr('caseSubjectId') != null) { return doc.id.toString() }   // (a) we are inside the case
def fresh = service.crud.<alias>.get(doc.id.toString())
if (((fresh.caseProcessIdentifier ?: '') as String).trim().isEmpty()) {           // (b) the write-back column

    // 3. start, then write back — in that order, never reversed (§5.4)
    def pid = service.workflow.start("<workflow identifier>", [ /* §2.2 */ ], [ /* §2.2 */ ])
    service.crud.<alias>.setCaseProcess([id: fresh.id.toString(), caseProcessIdentifier: pid])
}
return doc.id.toString()
```

⚠️ Guard (a) is load-bearing only when the same rule is reachable from **inside** the case. Where the rework
round has its own rule it is belt and braces; where it does not, it is the only thing stopping a second case.

### 2.2 The start call — the shape all 15 sites share

```groovy
def pid = service.workflow.start("<workflowIdentifier>", [
    contextDataMap: [
        ("<CONTEXT IDENTIFIER, not its alias>"): [
            crudDataMap: [ <crudAlias>: [ value: [
                id     : row.id,
                docNo  : row.docNo,
                status : row.status,
                partner: [id: partnerId]      // NESTED — never the string "partner.id"
            ] ] ],
            attrs: [:]                        // [:] and never [] — a Groovy [] is a List and Jackson refuses it
        ] ],
    attrs: [
        // (i) the binding — publish it under EVERY name a later step resolves by
        caseSubjectId : row.id.toString(),
        subjectId     : row.id.toString(),
        <alias>Id     : row.id.toString(),
        // (ii) what the WORKLIST shows. ⛔ Prefix everything: never businessKey / workflowName / status /
        //      identifier / id — those five are answered off the process row and would shadow yours.
        caseSubjectLabel  : (row.docNo ?: '') + ' · ' + partnerName,
        caseDocStatus     : (row.status ?: ''),
        caseDocStatusLabel: STATUS_LABEL[row.status] ?: '',
        caseOpenedBy      : actor
    ],
    localeKey: <see below>
], [
    owner          : actor,
    roleGroups     : ["<Role Group A>", "<Role Group B>"],
    businessKey    : (row.docNo ?: ('DOC-' + row.id)),
    groupIdentifier: "<processGroups[].identifier>"
])
```

Observed across all 15: `groupIdentifier` **15/15**, always the same string as the worklist node's
`processGroupIdentifier` and its settings mirror · `roleGroups` **15/15**, always the doers *and* their head ·
`businessKey` **15/15**, always the subject's human reference, never generated · `owner` 12/15 — it is one
line, pass it · `emails` **0/15**, nobody addressed an individual.

**`localeKey` has three legitimate sources.** Doc 27 says "read it off the claimed row, never a literal"; the
honest rule is narrower — **read it off the row only when the subject has a language column.** When the case
has one language but its recipients do not, one mail template per language chosen by a recipient lookup beats
a `localeKey` on the case, because one case can write to three people in three languages.

---

## 3. The BPMN skeleton

```xml
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
             xmlns:flowable="http://flowable.org/bpmn"
             id="Definitions_<ProcessName>" targetNamespace="http://bpmn.io/schema/bpmn">

  <!-- ⛔ the process key must be UNIQUE in the project. Two deliveries shipped five and six workflows all
       keyed Process_1. Use Process_<workflow identifier> or a unique semantic key. -->
  <process id="Process_<workflow identifier>" isExecutable="true">

    <!-- name the start event after the business event, not "Start": it is the only label a monitor shows
         for the entry point -->
    <startEvent id="Event_start" name="<Business event> raised"><outgoing>Flow_01</outgoing></startEvent>

    <!-- STEP 1 IS ALWAYS A BIND SERVICE TASK (§4). Two rules in one CSV: bind, then do. -->
    <serviceTask id="Activity_bind" name="[System] Refresh the subject and compute thresholds"
                 flowable:delegateExpression="${ruleTask}"
                 flowable:rule="<bind-rule-uuid>,<compute-rule-uuid>">
      <incoming>Flow_01</incoming><outgoing>Flow_02</outgoing></serviceTask>

    <!-- task names carry the ACTOR in square brackets — the engine ignores it, the worklist reader does not,
         and it is the only place the diagram records who a step belongs to -->
    <userTask id="Activity_review" name="[<Actor>] Review the subject (24 h)"
              flowable:userActions="{&#34;actions&#34;:[ … escaped JSON … ],&#34;errors&#34;:[]}">
      <incoming>Flow_02</incoming><outgoing>Flow_03</outgoing></userTask>

    <!-- every gateway names its question AND its default -->
    <exclusiveGateway id="Gateway_decision" name="Manager action?" default="Flow_approved">
      <incoming>Flow_03</incoming><outgoing>Flow_postponed</outgoing><outgoing>Flow_approved</outgoing>
    </exclusiveGateway>

    <!-- a conditional branch carries BOTH the editor attributes AND the <conditionExpression> -->
    <sequenceFlow id="Flow_postponed" name="Postpone"
                  sourceRef="Gateway_decision" targetRef="Event_end_postponed"
                  flowable:sequence="${predicateSequence.execute(execution, &#39;%s&#39;)}"
                  flowable:rule="<predicate-uuid>">
      <conditionExpression xsi:type="tFormalExpression">${predicateSequence.execute(execution, '<predicate-uuid>')}</conditionExpression>
    </sequenceFlow>
    <sequenceFlow id="Flow_approved" name="Approve" sourceRef="Gateway_decision" targetRef="Activity_next" />

    <!-- REWORK LOOP: the reject branch targets an EARLIER user task, which grows a second <incoming> -->
    <userTask id="Activity_approve" name="[<Actor>] Review and approve">
      <incoming>Flow_04</incoming><incoming>Flow_rejected</incoming><outgoing>Flow_05</outgoing></userTask>

    <!-- IMPLICIT JOIN: two flows into one node. No merge gateway exists anywhere in the corpus. -->
    <serviceTask id="Activity_post" name="[System] Post the result">
      <incoming>Flow_a</incoming><incoming>Flow_b</incoming><outgoing>Flow_13</outgoing></serviceTask>

    <!-- several end events, each NAMED with its outcome — this is how a terminal branch reads -->
    <endEvent id="Event_end_postponed" name="Postponed"><incoming>Flow_postponed</incoming></endEvent>
    <endEvent id="Event_end"           name="Completed"><incoming>Flow_13</incoming></endEvent>
  </process>
  <bpmndi:BPMNDiagram …>…</bpmndi:BPMNDiagram>
</definitions>
```

**Diagram quality is measurable and it matters.** The best diagram carries 18 shapes, 19 edges, 47 waypoints
(2.5 per edge — real orthogonal routing) and **12 `<bpmndi:BPMNLabel>` blocks** so its branch names appear on
the canvas. One delivery shipped **0 labels across 8 diagrams**: the branch names exist in the XML and the
canvas shows bare arrows out of every diamond. Branch labels are half the job, not an optional extra.
⚠️ `<bpmndi:BPMNLabel>` must come **after** its edge's waypoints — the reverse order aborts the whole
rep-objects import. All 21 diagrams got this right; keep it that way.

---

## 4. The bind/publish spine

**The first node after the start event is always a service task whose first rule is a `Bind <Entity>` rule**
— 3 of 3 working deliveries, 14 of 14 real workflows. Two of the three go further and **repeat the bind
before every human step**, either as a node literally named *Refresh the subject* or as the second rule of
every posting task's CSV (`flowable:rule="<Post the document>,<Publish the case fields>"`).

Why it is worth the extra node: the worklist and every gateway read GLOBAL attributes, and a case that ran
for two days holds whatever the starter published unless something republishes it. Re-binding before each
human step is what keeps a worklist column and a routing predicate looking at the same reality the user is.

---

## 5. Idempotency and the claim

### 5.1 Three techniques, not equally good

| | technique | verdict |
|---|---|---|
| 1 | **conditional `UPDATE … WHERE guard RETURNING *`**, `returnsArray:false` → a Map when this tick won, `null` when it did not | **the default.** Atomic, exact, testable |
| 2 | **`INSERT … ON CONFLICT DO NOTHING RETURNING *`** over a partial unique index | **the default for "announce this exactly once"** |
| 3 | read a page, check a marker in Groovy, then write | ⛔ **avoid** — a read-then-write window and O(rows) per tick; both deliveries that did it admit the scan bound in their own comments |

### 5.2 The claim — copy the three-column layout

⛔ **The one-column sentinel** (`process_identifier = 'CLAIMING'`) is cheap and **not repairable**: a crash
between claim and start leaves `'CLAIMING'` for ever, and nothing can tell it from a claim taken a second
ago. The delivery that used it shipped no repair sweep for any of its three entities.

✅ **A claim timestamp, the identifier, and an attempt counter:**

```sql
-- claimForCase            (returnsArray:false) — process_started_at IS the claim
UPDATE <t> SET process_started_at = now(),
               process_start_count = COALESCE(process_start_count, 0) + 1,
               modification_time = now()
 WHERE id = CAST(:id AS uuid) AND deleted = false AND status = 'NEW' AND process_started_at IS NULL
 RETURNING *

-- setCaseProcess          (returnsArray:false) — the mark
UPDATE <t> SET process_identifier = :process_identifier, modification_time = now()
 WHERE id = CAST(:id AS uuid) RETURNING *

-- findClaimedWithoutCase  (returnsArray:true)  — the orphans, by age
SELECT t.id, t.doc_no, t.process_started_at FROM <t> t
 WHERE t.deleted = false AND t.status = 'NEW'
   AND t.process_started_at IS NOT NULL AND t.process_identifier IS NULL
   AND t.process_started_at < now() - INTERVAL '5 minutes'
 ORDER BY t.process_started_at LIMIT 50

-- releaseCaseClaim        (returnsArray:false) — both guards in the WHERE, so two ticks cannot both release
UPDATE <t> SET process_started_at = NULL, modification_time = now()
 WHERE id = CAST(:id AS uuid) AND process_identifier IS NULL
   AND process_started_at < now() - INTERVAL '5 minutes' RETURNING *

-- endCase                 (returnsArray:false) — release BOTH when a terminal branch allows re-entry (§6.3)
UPDATE <t> SET process_started_at = NULL, process_identifier = NULL, modification_time = now()
 WHERE id = CAST(:id AS uuid) RETURNING *
```

and the gate's counter deliberately counts the **repairable backlog** too, so the scheduler wakes for it:

```sql
SELECT COUNT(*) AS total FROM <t> t
 WHERE t.deleted = false AND t.status = 'NEW'
   AND (t.process_started_at IS NULL
        OR (t.process_identifier IS NULL AND t.process_started_at < now() - INTERVAL '5 minutes'))
```

`process_start_count` costs nothing and is the only evidence you will ever have that a subject was claimed
twice. ⚠️ Every `:name` in these methods must appear in `parameters[]` — `crud add-method` writes
`parameters: []` and `validate` does not check a SQL method's parameters.

### 5.3 `ON CONFLICT DO NOTHING` — the primitive nobody documents

For *say this exactly once*, the claim is an INSERT:

```sql
INSERT INTO <warning> (subject_type, subject_id, subject_reference, clock_code, escalation_point,
                       due_at, warned_at, notified, deleted, creation_time, modification_time)
VALUES (COALESCE(NULLIF(:subjectType,''), 'CASE'), CAST(NULLIF(:subjectId,'') AS uuid),
        COALESCE(NULLIF(:subjectReference,''), '-'), COALESCE(NULLIF(:clockCode,''), 'DEADLINE'),
        COALESCE(CAST(NULLIF(:escalationPoint,'') AS integer), 50),
        CAST(NULLIF(:dueAt,'') AS timestamptz), now(), NULLIF(:notified,''), false, now(), now())
ON CONFLICT DO NOTHING RETURNING *
```

```sql
CREATE UNIQUE INDEX uq_<warning>_subject_clock_point
    ON <schema>.<warning> USING btree (subject_type, subject_id, clock_code, escalation_point)
    WHERE (deleted = false);
```

Three things make it work, and each is easy to lose:

- the index is **partial**, so the INSERT **must** set `deleted = false` explicitly or the row falls outside
  the index and the conflict never fires;
- **bare `ON CONFLICT DO NOTHING`** (no conflict target) arbitrates on *any* unique index — which is what you
  want when the arbiter is partial;
- **`RETURNING *` with `returnsArray:false`** is what turns "nothing inserted" into Groovy `null`.

### 5.4 Claim first, repair separately — and repair BEFORE you sweep

Both sweeping deliveries chose **claim → start → mark**. The reasoning, in one of their comments: a crash
leaves a row *claimed with no case* — detectable, repairable, once — where the other order leaves a case
whose row was never marked, which the next tick opens again with no way to tell the duplicates apart.

```groovy
// EXECUTION_RULE — the scheduler ACTION. Always: repair → gather → claim → shape → start → mark.
CALL("Repair <Entity> Case Claims")            // ← FIRST, so a crashed tick's claim is back in time for this pass

int rowsInPage = 200, passes = 25, opened = 0
while (passes-- > 0) {
    // page 0 every time on purpose: the candidate query already excludes everything this sweep claimed
    def rows = service.crud.<alias>.findCaseCandidates([rows_in_page: rowsInPage.toString(),
                                                        page_number : '0']) ?: []
    if (rows.isEmpty()) { break }
    int claimedThisPass = 0
    // `for`, not `.each`: inside a closure `return` means "next element", which reads like "stop the rule"
    for (row in rows) {
        def claimed = service.crud.<alias>.claimForCase([id: row.id?.toString()])
        if (claimed == null) { continue }                       // somebody else won it
        claimedThisPass++
        def started = service.workflow.start("<wfId>", [ /* §2.2 */ ], [ /* §2.2 */ ])
        def pid = (started instanceof Map)                       // the return shape is not guaranteed
                ? (started.identifier ?: started.processIdentifier ?: started.id) : started
        service.crud.<alias>.setCaseProcess([process_identifier: pid?.toString(), id: claimed.id?.toString()])
        opened++
    }
    if (claimedThisPass == 0) { break }                          // the page was taken by somebody else
}
return opened
```

The repair **hands rows back rather than starting cases** — exactly one place in a project opens a case:

```groovy
def orphans = service.crud.<alias>.findClaimedWithoutCase([:]) ?: []
int released = 0
for (row in orphans) {
    if (service.crud.<alias>.releaseCaseClaim([id: row.id?.toString()]) == null) { continue }
    released++ }
return released
```

---

## 6. Schedulers

### 6.1 The record, field for field

```jsonc
{ "errors": null, "message": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid you mint>",
  "name": "<Area> — escalate unanswered requests",   // UNIQUE in the project; a duplicate aborts the import
  "actionType": "RUN_RULE",                          // the only value in 43/43
  "enabled": false,                                  // §6.2
  "job":         { "explanation": "Weekdays 08:20 — open an escalation case per request past the configured attempts",
                   "cronType": null, "expression": "0 20 8 * * MON-FRI" },
  "cooldownJob": { "explanation": null, "cronType": null, "expression": null },   // never set, 43/43
  "predicateIdentifier":  "<PREDICATE rule uuid>",   // the gate
  "actionRuleIdentifier": "<EXECUTION_RULE uuid>",   // the work
  "serviceUserEmail": "<service account in the TARGET tenant>",
  "serviceUserId": null,
  "cooldownUntil": null, "lastActionTime": null, "lastPredicateCheckTime": null }
```

✅ **`job.explanation` is the field that earns its keep.** Use it as the design record, not a label: *"Every
5 minutes — open a case for every NEW subject that has none yet. The case starts when the daily job finds the
condition, not when somebody presses Start. The cron is only how often we LOOK; the condition is the gate plus
the candidate query."* It is the only place the cron-is-not-the-deadline decision is written down.

⛔ **`serviceUserId` is `null` in 43/43 even where `serviceUserEmail` is set.** It is the field every
`hasAnyRole*` check keys off, so **a headless rule must not contain a role guard** — it silently returns
`false` and the job becomes a no-op. Confirmed by absence: not one of the 14 headless sweep rules calls
`hasAnyRoleGroup`, while nearly every UI rule does.

### 6.2 Ship `enabled: false`

Three of four do. An `enabled:true` schedule registers its cron the moment the project is imported and fires
on the first matching tick — against production data, before anybody has deployed the workflows it starts.
The one delivery that ships `true` is a pilot whose whole point is the automatic case, and it paid the tax by
making its case-opening rule tolerant of an undeployed workflow (§6.4).

**Ship `false`, and put "enable the schedules" in the hand-over next to "deploy the workflows".**

### 6.3 One entity, several schedules

The corpus never puts two jobs in one schedule. Four over one entity, and the division is the model:

| schedule | cron | what it does | why separate |
|---|---|---|---|
| daily check | `0 0 0 * * *` | recompute positions, raise one warning per subject | the business event |
| open cases | `0 */5 * * * *` | claim + start a case per un-cased warning | idempotent, so the daily check can also call it inline |
| escalate unanswered | `0 0 * * * *` | 24 h with no decision → flag + notify the supervisor | different audience, different cadence |
| resume postponed | `0 10 0 * * *` | postponement elapsed → subject back to `NEW` | **this is the BPMN timer that does not exist** |

⛔ **A sweep must not write a field a running case's gateway routes on.** There is no way to cancel a case
from a rule (`service.workflow` has only `start`), so a sweep that changes the routing column steers a case a
human is standing in — the gateway takes the wrong branch, the case closes with nothing done, and the claim
stays set for ever. **Sweeps write annotation columns** (`escalated`, `attempts`, `last_chased_at`); **the
case writes the state column.**

✅ **And the mirror: when a terminal branch is meant to allow re-entry, release the claim on that branch.**
The postpone path ends with `endCase([id: …])` so that when the resume sweep brings the subject back to `NEW`,
a **fresh** case opens for the new decision cycle. Without it the subject stays claimed for ever and comes
back with nowhere to be worked.

### 6.4 Chaining, and making a job observable

Call one rule from another rather than duplicating a sweep, and wrap the call so a failure names the callee
instead of arriving as a nested proxy exception:

```groovy
def CALL = { String rn ->
    try { return service.rule(rn) }
    catch (Throwable t) {
        def root = t; int guard = 0
        while (root.cause != null && root.cause != root && guard++ < 12) { root = root.cause }
        throw new RuntimeException("rule '" + rn + "' failed: " + root.class.simpleName +
                                   (root.message ? ': ' + root.message : '')) } }
```

Isolate the one call that can legitimately fail on a fresh import — every workflow lands as an undeployed
draft, and a chain that is not deployed yet must not take the nightly job down with it:

```groovy
int casesOpened = 0; String caseError = null
try { casesOpened = (CALL("Open Cases") ?: 0) as Integer }
catch (Throwable t) { caseError = (t.message ?: t.class.simpleName) }
service.crud.<runLog>.finish([status: (caseError == null ? 'SUCCESS' : 'FAILED'),
                              message: … + (caseError == null ? '' : ' Cases NOT opened: ' + caseError),
                              id: runId])
```

✅ **A scheduler's outcome is recorded nowhere by the platform.** The two best deliveries each write a
**run-log row** (`started_at`, `finished_at`, counts, `status`, `message`). If the job must be observable, the
rule has to make it observable.

### 6.5 The gate

10 of 16 gated schedules use one shape — the candidate query with `rowsInPage: 1`:

```groovy
// PREDICATE — the gate. It may only ANSWER: service.workflow.start is refused here at runtime, and the
// expensive work belongs in the action anyway (the gate runs every tick, the action only when it opens).
//
// ⛔ The explicit `return` is mandatory. A predicate that falls off the end returns null, which is reported
// as "Predicate rule must return Boolean, but returned: null" and treated as a CLOSED gate — for ever, with
// nothing in the UI to show for it.
def rows = service.crud.<alias>.findCandidates([maxAttempts: maxAtt, rowsInPage: 1, pageNumber: 0])
return !((rows instanceof Map ? (rows.content ?: []) : (rows ?: [])).isEmpty())
```

The other shape is a dedicated `count*` method. **Prefer `count*` when the candidate query is expensive or
joins; prefer `LIMIT 1` when it is the same statement**, because then the gate cannot drift from the action.
⚠️ A gate that must scan in Groovy has to bound itself explicitly — one page, return on the first hit. A gate
must stay cheap.

---

## 7. The worklist page

**Invariant, 14/14 in the three working deliveries:** one workflow → exactly one `process.table.pluin` node →
on its own `siteMapPage` with its own alias → with a `settings[]` mirror whose `name` is the node's
`uniqueIdentifier` → linked from a **business** nav group.

```jsonc
{ "workflowIdentifier":     "<the workflow's identifier>",
  "processGroupIdentifier": "<the SAME string the starting rule passes>",
  "columnSettings": [
    { "localizedNames": {"en_US": "Case", …},        "dataClass": "java.lang.String",
      "scope": "GLOBAL", "fieldExpression": "businessKey" },
    { "localizedNames": {"en_US": "Subject", …},     "scope": "GLOBAL", "fieldExpression": "caseSubjectLabel" },
    { "localizedNames": {"en_US": "Doc status", …},  "scope": "GLOBAL", "fieldExpression": "caseDocStatusLabel" },
    { "localizedNames": {"en_US": "Case state", …},  "scope": "GLOBAL", "fieldExpression": "status" },
    { "localizedNames": {"en_US": "Opened by", …},   "scope": "GLOBAL", "fieldExpression": "startedByRuleName" } ],
  "indexSettings": [
    { "indexName": "docStatus", "scope": "GLOBAL", "fieldExpression": "caseDocStatus", "dataClass": "java.lang.String" },
    { "indexName": "docNo",     "scope": "GLOBAL", "fieldExpression": "caseDocNo",     "dataClass": "java.lang.String" } ],
  "filterExpression": "ignoreNull(docStatus=={filter_docStatus}) && ignoreNull(docNo=={filter_docNo})",
  "userStartProcessActions": { "actions": [], "errors": [] },
  "globalActions":           { "actions": [ /* at most one read-only viewer */ ], "errors": [] } }
```

- **Columns: 3–6, never more.** A worklist row answers *who / what / when / what state* and nothing else.
- **Exactly two index entries** in 14/14, with the same two-clause `filterExpression`, and every `filter_*`
  key has a matching control on a `dynaform.filter.form.plugin` sibling.
- **`userStartProcessActions` is empty** on all 14.
- **`globalActions` is empty or holds exactly one read-only viewer.** Never more.

✅ **Jump `scope: "GLOBAL"` for columns.** A `CRUD`-scoped column reads the `crudDataMap` snapshot the
starting rule passed and the plugin never re-reads the table — so the first service task that updates the
record leaves the column showing the value the case opened with. One delivery scoped all its columns CRUD
while its own bind rule was republishing the same fields into GLOBAL attributes on every step; the attributes
were already there, the columns just did not read them.

---

## 8. The inert-workflow defect, and the check that finds it

The largest delivery shipped **seven workflows, zero deployed, six with nothing that starts them, and no
worklist page** — five well-drawn diagrams that no user could ever reach. Nothing in the export says so:
`validate` is green, the Workflows console lists them, and the only symptom is a queue that never fills.

**The mechanical check:** grep each `workflows[].identifier` across the unpacked export and expect **≥ 3
hits** — the definition, the worklist node's model, and its `settings[]` mirror. One hit means the workflow
exists and nothing points at it.

Two more from the same family:

- **A duplicate `<process id>`.** Two deliveries keyed five and six workflows `Process_1`. Give every process
  a unique key.
- **A branch with no label on the canvas.** Names in the XML plus zero `<bpmndi:BPMNLabel>` blocks means the
  monitor shows bare arrows out of every diamond.

---

## 9. Corrections to the library

| the library says | the deliveries show | verdict |
|---|---|---|
| doc 07: a multi-step process with human hand-offs → a workflow plus its worklist, always | 4/4 authored BPMN; 2/4 shipped it entirely undeployed and unreachable | **put a test in front of the rule** (§1): is the case *queued and claimed by somebody who does not own the row*? If not, ship a status column + predicate + command rule and leave the BPMN in the plan |
| doc 27 §2.3: a service task is how one process starts another | the corpus does it from a user action's complete rule | **deliveries right** — it fires only on the branch a human chose, and it can refuse in the same rule |
| doc 27 §6: read `localeKey` off the claimed row, never a literal | three legitimate sources are in use | **narrow the rule**: off the row only when the subject has a language column; otherwise one mail template per language |
| doc 12: author `enabled:false` | correct, but only half the decision — both failure directions were observed (27/27 enabled; 12 disabled with the entire proactive half inert and nothing saying so) | **extend**: ship `false` **and** hand over a named enable list |
| doc 26 §1: "zero workflows for a process PRD" is a symptom of a lifecycle being simpler than BPMN | the largest delivery is the counter-example: zero deployed workflows was the right outcome there | **the observable is an empty worklist or a lifecycle with no queue**, not the count of BPMN files |
| — *(unstated)* | `service.workflow.list` is never used; the claim column always won | **document it**: idempotency lives in the data |
| — *(unstated)* | which branch a gateway's `default` should point at | **new rule**: the default is where the process lands when the predicate could not decide — make it the reversible branch, the one that asks a human, or the one that ends the case. Never the branch that spends money or moves stock |
| — *(unstated)* | a sweep that writes the routing column steers a running case | **new rule** (§6.3): sweeps write annotation columns; the case writes state |
| — *(unstated)* | no way to detect an inert workflow | **new gate** (§8): every workflow identifier must appear ≥ 3 times in the export |


---

## Done when

- Every workflow in the export is either **deployed and reachable** — its identifier appears at least three
  times (definition, start site, worklist) — or it has been deleted from the export and moved back to the plan.
  An undeployed BPMN is not a half-built feature; it is a screen that silently does nothing.
- Every process has a **named starter** (form, scheduler, CRUD method or service task) and a worklist page
  that surfaces its instances.
- **Idempotency lives in the data**: a claim column, not a `list`-then-decide read. The claim is taken in the
  same statement that selects the candidate.
- Every `RUN_RULE` scheduler carries a **PREDICATE gate** so the action never fires on an empty set, ships
  `enabled: false`, and is handed over with a **named enable list** — both failure directions have been seen
  in production.
- Every gateway `default` points at the **reversible** branch: the one that asks a human, or ends the case.
  Never the one that spends money or moves stock.
- Sweeps write **annotation** columns; only the case writes state.
- The case-opening rule tolerates an **undeployed** workflow on a fresh import instead of taking the nightly
  job down with it.
