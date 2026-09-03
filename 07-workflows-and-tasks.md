# Workflows, BPMN & tasks

> ⛔ **Before you draw anything: who opens a case, when, and what makes that run?** A correct BPMN starts
> nothing by itself. The four starters, the two-starters-for-one-process trap, and the three different
> button buckets on a process table are in [27](27-event-driven-process-start.md) §2 — read it before this
> file, not after. `validate` ERRORs on a workflow nothing starts and on a starter rule nothing invokes.


## What it is / when to use

> ⚠️ **Mandate (`system_prompt.txt` Operating Principle 3, [19](19-build-decision-procedure.md) Phase 11):** if the
> PRD **describes a multi-step human process** — an intake→review→approve→notify chain, hand-offs, approvals, a BPMN
> diagram, a step list — **you MUST author a workflow here.** Do NOT silently downgrade it to a few lifecycle
> actions; a process-heavy PRD that ships **zero** workflows is a defect the coverage gate ([26](26-orchestration-and-testing.md)
> §6a) will fail. A PRD deadline/boundary **timer** (there is no `bpmn:BoundaryEvent`) is realised as a **scheduler**
> ([12](12-queries-sources-schedulers-and-rest.md)); build the rest of the process as a real workflow — never drop
> the whole workflow because of one timer.

> ⛔ **`bpmnContent` must be SCHEMA-VALID, not just well-formed.** Flowable validates the XML against the BPMN 2.0
> **XSD** on save (`BpmnXMLConverter.validateModel`); a well-formed-but-schema-invalid diagram is rejected
> (*"Workflow validation failed … invalid XML"*) and **ABORTS the whole rep-objects import** — and because the
> workflow save runs **before** rules/contexts/forms/settings/mail+pdf-templates in `CmsProjectServiceImpl.initAllObjects`,
> **everything after it is silently skipped** (symptom: no workflow *and* empty charts *and* "no business-logic usages"
> *and* missing templates, all at once — from ONE bad workflow). The most common trap: **child-element ORDER on event
> elements.** BPMN 2.0 `tCatchEvent`/`tThrowEvent` require children in the order `extensionElements?, incoming*,
> outgoing*, …, eventDefinition*` — so a `<messageEventDefinition>`/`<timerEventDefinition>` must come **AFTER**
> `<incoming>`/`<outgoing>`, not before. A plain XML parse (what a naive check does) accepts any order; the XSD does
> not (`cvc-complex-type.2.4.a`). `mrjun.py validate` now ERRORs on this exact ordering — but a **live import** is
> still the real proof (validate does not run the Flowable XSD).

A workflow is an **executable BPMN 2.0 process** (engine **Flowable 7.0.1**) that lives entirely in
`rep-objects.json` under the `workflows` key. Each workflow stores an **XML diagram** (`bpmnContent`) plus a
**denormalized set of nodes** (`elements`). Nodes can be tasks (service task, user task, gateway,
events) and connections (sequence flow). Tasks bind **Groovy rules** (`rule`), **contexts**, and **forms**
through their settings.

> **🔧 Tooling.** For these entities, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of editing JSON by hand:
> `workflow add --name <s> [--context <ctx>]... [--user-task "<name>[:<formGroup>]"]... [--service-task "<name>:<rule>"]... [--gateway <name>]...`
> — generates an executable BPMN skeleton where the steps are **chained in command-line order** (you can interleave them):
> `startEvent → step1 → … → stepN → endEvent` + a consistent `elements[]` + a minimal BPMNDiagram (valid
> XML, passes `validate`). Step types:
> - `--user-task NAME` — a plain userTask (backward-compatible); `--user-task "NAME:<formGroup id|name>"` —
>   binds a form group via `flowable:userActions` (action `direct:"off"`, form group resolved in
>   `rep-objects.formGroups`).
> - `--service-task "NAME:<rule id|name>"` — a serviceTask with `flowable:delegateExpression="${ruleTask}"` +
>   `flowable:rule="<uuid>"` (rule resolved in `rep-objects.rules`; error if not found).
> - `--gateway NAME` — an `exclusiveGateway` placeholder with **one incoming + one outgoing** transition; the
>   branch forks are added **by hand** per this doc (Step 3 / §4), and each needs all three of a
>   `conditionExpression` predicate on every branch but one, the gateway's `default="<that one>"`, and a `name`
>   on every branch.
>
> Plus `workflow list`; `list workflows`; `inspect`; `show <kind> <id>`. For more complex logic (multiple
> outgoing conditional transitions from a gateway, a CSV of several `flowable:rule`s, custom `ActionDto` fields)
> refine the generated `bpmnContent` by hand per this doc. Full index and rules —
> [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.


> ⛔⛔ **Every ActionDto field in a `userActions` payload is a STRING — a JSON array or a boolean kills the
> whole task.** `validationRuleIdentifiers` is a **comma-separated String** (`UserTaskActionsDto.java`),
> `direct` is `"on"`/`"off"`, and so are `predicateIdentifier`, `formGroupIdentifier`, the two
> `onBeforeUserTask*RuleIdentifier`, `completeUserTask`, `icon`, `taskId`. Emit `["uuid"]` instead of
> `"uuid"` and Jackson fails the ENTIRE payload — the user task then renders **with no action buttons at
> all**, silently, with nothing in the log pointing at the cause (LIVE-FOUND 2026-08-07; a generator that
> built the list from a Python list of rule names is exactly how it happens). `mrjun.py validate` now ERRORs
> on any non-string value in these fields.

> **⚠️ `mrjun.py validate` now checks workflow internals — but as WARNs, and not exhaustively.**
> `_check_workflow_refs` (`validate_cmds.py`) parses `bpmnContent` and flags: a serviceTask `flowable:rule`
> that isn't an EXECUTION/VALIDATION rule; a conditional `predicateSequence.execute(...,'<uuid>')` whose UUID is
> dangling, not a PREDICATE, **empty-bodied** (fails-open to `true`), or an **empty id** (`'')`; a conditional
> `<sequenceFlow>` **missing the `flowable:sequence`/`flowable:rule` editor attributes** (re-save drops the
> condition); a userAction `formGroupIdentifier`/predicate/onBefore*/validation ref; and `contextIdentifiers`.
> Still verify by hand anything it can't reach, and treat these WARNs as must-fix (`jq` the UUIDs out of the
> XML/`elements`, grep them in the target collections):
> - each serviceTask `flowable:rule` CSV UUID → exists in `rep-objects.rules[]` (type `EXECUTION_RULE`/`VALIDATION_RULE`);
> - each userAction `formGroupIdentifier` → exists in `rep-objects.formGroups[]`; `predicateIdentifier`/
>   `onBefore*RuleIdentifier`/`validationRuleIdentifiers` UUIDs → in `rep-objects.rules[]`;
> - each conditional `conditionExpression` predicate UUID (the one inside `${predicateSequence.execute(execution, '<uuid>')}`) → a `PREDICATE` rule;
> - the workflow's `contextIdentifiers` → exist in `rep-objects.contexts[]`.
> A dangling ref here won't fail `validate`; it fails at runtime (or renders nothing).

Terminology:

- **Workflow** — a process definition (BPMN 2.0 XML + deploy into Flowable). Exported as `FlowableWorkflowDto`.
- **Process (instance)** — a runtime instance of one workflow (not exported as a definition; see `processGroups`).
- **Task** — a unit of work: automatic (`ServiceTask`, executes Groovy) or human (`UserTask`).

When you need to build this:

- A multi-step business process with human steps (approve/reject), automatic steps (recalculation,
  integration update) and conditional branching.
- Unlike direct CRUD-table actions (see [04-crud-table-plugin.md](04-crud-table-plugin.md)),
  a workflow is a **stateful** process instance with task history, assignee assignment, and variables
  (`contextData`, see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)).

> **⚠️ Use a workflow ONLY if you need at least one of:** (1) **multi-step state persisted across steps** —
> the process pauses between steps and `contextData` survives (`completeUserTask:"off"` keeps a task open,
> variables carry to the next step); (2) a **human task queue** — a UserTask that sits in an assignee/
> `candidateGroups`/`candidateUsers` inbox until someone acts on it; (3) **conditional routing between steps** —
> an exclusive/parallel/inclusive gateway branching on predicate `conditionExpression`s.
> If none apply — a single-entity operation, a one-button status change, a recalculation-on-save — **do NOT
> create a workflow.** Use a **CRUD-table action + `onBefore*` EXECUTION rule** instead (see
> [04-crud-table-plugin.md](04-crud-table-plugin.md), [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)):
> it is one rule UUID, no BPMN XML, no deploy step, no process instances to manage. **State workflows are rare** —
> `empty` ships **0** workflows, and a typical authored project carries a couple of drafts and at most one that is
> actually deployed (`deployed=true`). Don't reach for a workflow by default.

Key fact for reconstruction: **`elements` is NOT an independent data source.** It is **derived
from `bpmnContent`** by the Flowable server on every save/deploy
(`FlowableWorkflowServiceImpl.java`
`extractWorkflowElements`). Therefore the source of truth when building by hand is the **XML in `bpmnContent`**; `elements`
should be generated so that it matches it (the matching rules are below in the section "How `elements`
is derived from `bpmnContent`"). Import will re-read the XML and rebuild the nodes anyway, but a consistent `elements`
avoids desync in the UI (panels read node settings precisely from `elements`).

The worked example running through this document is a **"Service Center Workflow"** — one deployed workflow with a
service task, a user task, an exclusive gateway and conditional transitions. Substitute your own process
(claim → adjudicate → pay; declaration → inspect → release; ticket → triage → resolve): the shape is the same.

Its 17 `elements` break down as:
`1×bpmn:Process, 1×bpmn:StartEvent, 3×bpmn:ServiceTask, 2×bpmn:UserTask, 1×bpmn:ExclusiveGateway,
8×bpmn:SequenceFlow, 1×bpmn:Task` (the last is the end event, see below). That ratio is typical: **sequence flows
outnumber tasks**, and the `bpmn:Process` node itself counts as an element.

> **The walkthrough is an illustrative composite**, modernised to `localizedNames`/`localizedButtonNames`. A
> workflow of the same name ships in [`erp/initial_erp.mrjun`](erp/initial_erp.mrjun) /
> [`erp/dynamic.mrjun`](erp/dynamic.mrjun), but it is an **earlier, smaller variant** — 15 elements
> (`1×bpmn:Process, 1×bpmn:StartEvent, 2×bpmn:ServiceTask, 2×bpmn:UserTask, 1×bpmn:ExclusiveGateway,
> 7×bpmn:SequenceFlow, 1×bpmn:Task`), `deployed:false`, a gateway and an end event with **no `name`**, and
> actions still in the **legacy single-`name`** form. So `jq` the sample to learn the *shapes*, but do not expect
> it to match this walkthrough node-for-node; where they differ, **this doc is what you should author**.

## Export shape

`rep-objects.json.workflows` is an **array** of `FlowableWorkflowDto` objects. Plus `rep-objects.json.processGroups`
is an array of `ProcessGroupDto`. The schema of a single workflow:

```jsonc
{
  "message": null, "errors": null, "id": null,      // AbstractSecuredDto housekeeping fields, irrelevant on import
  "realmName": "<realm>",                            // tenant (realm)
  "clientName": "<client>",                          // project (client)
  "identifier": "6c0b4335-...-68556dc6f53e",         // workflow UUID — stable identity key
  "creationTime": "2026-07-01T15:41:50.765427Z",
  "modificationTime": "2026-07-01T15:41:50.765435Z",
  "processDefinitionId": "Process_1:6:6090a3e4-...", // Flowable id of the deployed definition; null if not deployed
  "name": "Service Center Workflow",                 // human-readable name (@NotBlank)
  "description": null,
  "externalId": "5fa50b61-...-76329eac821b",         // Flowable deployment id; null if not deployed
  "deployed": true,                                  // true after a successful deploy
  "bpmnContent": "<?xml ...>",                       // BPMN 2.0 XML — THE SOURCE OF TRUTH
  "elements": [ /* WorkflowElementDto[] — derived from bpmnContent (this is a Set, order is nondeterministic) */ ],
  "contextIdentifiers": ["fe5e9b03-...-6a01362bc553"] // context UUIDs (see 08-groovy-rules-and-context.md)
}
```

**The actual key set** of an exported workflow object (the same in every export):
`bpmnContent, clientName, contextIdentifiers, creationTime, deployed, description, elements, errors,
externalId, id, identifier, message, modificationTime, name, processDefinitionId, realmName`. Note:
**the exported DTO has no `status`/`workflowStatus`, no `latest`, no `processDefinitionKey`** —
those fields exist on the entity but do not make it into the export. Don't invent them when building by hand.

`WorkflowElementDto` (an `elements` element):

```jsonc
{
  "id": "Activity_0i94xes",                          // = the node's id in the XML
  "settings": {
    "type": "bpmn:ServiceTask",                      // BpmnTaskType (@JsonProperty), see the types table below
    "properties": [                                  // Set<ElementSettingsProperty> — a set of name/value pairs
      { "name": "id",   "value": "Activity_0i94xes", "type": null, "control": null, "order": 0 },
      { "name": "name", "value": "Update Integration", "type": null, "control": null, "order": 0 },
      { "name": "rule", "value": "694b564b-...,394a362b-...", "type": null, "control": null, "order": 0 }
      /* ... */
    ]
  }
}
```

**`elements` is a `Set<WorkflowElementDto>` (HashSet), and `properties` is a `Set<ElementSettingsProperty>`**
(`FlowableWorkflowDto.java`, `ElementSettingDto.java`). Practical consequences for building by hand:
- **Element order and property order are nondeterministic** — in the export they are in arbitrary order, and your
  `elements[]` **need not** match the XML order. The `order:0` field on all properties is a stub (no sorting
  uses it).
- **Duplicate property names collapse.** `ElementSettingsProperty` has `@EqualsAndHashCode(exclude={"value","type","control"})`
  (`ElementSettingDto.java`), i.e. equality/hash is by `name`+`order`. Don't put two properties with the same `name`.
- The only key of a node is `id`. `WorkflowElementDto` is also `@EqualsAndHashCode(exclude="settings")` (equality
  by `id`). Don't duplicate nodes with the same `id`.

`ProcessGroupDto` (a `processGroups` element) — a minimal container that groups running processes:

```jsonc
{ "message": null, "errors": null, "id": null, "realmName": "<realm>", "clientName": "<client>",
  "identifier": "b0c1f90e-...-837173d02923",
  "creationTime": "...", "modificationTime": "...",
  "name": "791029e6-...-9a702ffb6b6d", "description": "791029e6-...-9a702ffb6b6d" }
```

**`ProcessGroupDto` fields:** `id` (`null` in the export), `identifier` (UUID — the real identity key),
`name`, `description` (UUID placeholders in the default groups), `realmName`/`clientName`. Identity is
carried by `identifier`, NOT by `id`/`name`. A ProcessTable references a group via `processGroupIdentifier`
(see [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)) — so one workflow can be
shown as several filtered views (by department/category).

Every project inherits the **same two default** processGroups from `empty`, with fixed `identifier`s
(`b0c1f90e-156a-4ca4-b7bd-837173d02923` and `32d9be5f-8e28-458c-b2d8-2baf05fbd0f0`) — part of the standard skeleton
of an empty project ([12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)).
Don't duplicate them; for a new group add an element with a **new** `identifier` and meaningful `name`/`description`.

## Node types (BpmnTaskType) — full enumeration

The full enumeration of `settings.type` values (backing enum `BpmnTaskType.java`; the JSON value is set by
`@JsonProperty`). All 21 constants are listed. `BpmnTaskType.get()` matches **case-insensitively**.

> ⛔ **HARD RULE — `elements[].settings.type` may ONLY be one of the 21 `@JsonProperty` strings in the table
> below.** Any other value — most easily `bpmn:BoundaryEvent`, `bpmn:EndEvent`, `bpmn:IntermediateCatchEvent` —
> makes the platform importer throw a Jackson `InvalidFormatException` deserializing
> `FlowableWorkflowDto.elements[].settings.type`, which **aborts the ENTIRE `rep-objects.json` import**. The
> symptom is data-shaped and SCATTERED, not error-shaped: **no source is saved ("No source selected"),
> `project-db.dump` is not restored (data/dates "gone"), the context imports empty, only `dynamic-cruds.json`
> (a separate path) loads but can't work.** Verified live (`log/ui.log`:
> `Cannot deserialize value of type BpmnTaskType from String "bpmn:BoundaryEvent" … ["workflows"]->
> FlowableWorkflowDto["elements"]->WorkflowElementDto["settings"]->ElementSettingDto["type"]`).
> **End events → author as `bpmn:Task`. Boundary/timer events are NOT modellable — do not put them in
> `elements[]` at all** (and keeping a `<boundaryEvent>`/`<timerEventDefinition>` only inside `bpmnContent`
> desyncs the editor and gives no runtime timer, so avoid them entirely). `mrjun.py validate` now ERRORs on any
> `elements[].settings.type` outside this set — do not pack until it passes.

| `settings.type` (JSON) | enum value | Right-hand settings panel | Creatable in UI/MCP? |
|---|---|---|---|
| `bpmn:StartEvent` | `BPMN_START` | Common (no controls) | yes (`START_EVENT`) |
| `bpmn:Process` | `BPMN_PROCESS` | Common | root (auto) |
| `bpmn:Task` | `BPMN_TASK` | Common. **NB: the endEvent from the XML maps here** (`FlowableWorkflowServiceImpl.java` — "there is no separate type for EndEvent") | end-event (`END_EVENT`) |
| `bpmn:UserTask` | `BPMN_USER_TASK` | `UserTaskSettingsPanel` (userActions) | yes (`USER_TASK`) |
| `bpmn:ServiceTask` | `BPMN_SERVICE_TASK` | `ServiceTaskSettingsPanel` (delegateExpression + rule) | yes (`SERVICE_TASK`) |
| `bpmn:SendTask` | `BPMN_SEND_TASK` | Common | ⚠️ not creatable |
| `bpmn:ReceiveTask` | `BPMN_RECEIVE_TASK` | Common | ⚠️ not creatable |
| `bpmn:ManualTask` | `BPMN_MANUAL_TASK` | Common | ⚠️ not creatable |
| `bpmn:BusinessRuleTask` | `BPMN_BUSINESS_RULE_TASK` | Common | ⚠️ not creatable |
| `bpmn:ScriptTask` | `BPMN_SCRIPT_TASK` | Common | ⚠️ not creatable |
| `bpmn:CallActivity` | `BPMN_CALL_ACTIVITY` | `CallActivitySettingsPanel` (calledElement + inherit*) | yes (`CALL_ACTIVITY`) |
| `bpmn:SubProcess` | `BPMN_SUB_PROCESS` | Common | yes (`SUB_PROCESS`) |
| `bpmn:TextAnnotation` | `BPMN_TEXT_ANNOTATION` | Common (artifact) | ⚠️ not creatable |
| `bpmn:Association` | `BPMN_ASSOCIATION` | Common (artifact) | ⚠️ not creatable |
| `bpmn:SequenceFlow` | `BPMN_SEQUENCE_FLOW` | `SequenceFlowSettingsPanel` (sequence + rule + conditionExpression) | connected in the XML |
| `bpmn:ExclusiveGateway` | `BPMN_EXCLUSIVE_FLOW` | Common | yes (`EXCLUSIVE_GATEWAY`) |
| `bpmn:ParallelGateway` | `BPMN_PARALLEL_FLOW` | Common | yes (`PARALLEL_GATEWAY`) |
| `bpmn:InclusiveGateway` | `BPMN_INCLUSIVE_FLOW` | Common | yes (`INCLUSIVE_GATEWAY`) |
| `bpmn:ComplexGateway` | `BPMN_COMPLEX_FLOW` | Common | ⚠️ not creatable |
| `bpmn:EventBasedGateway` | `BPMN_EVENT_BASED_FLOW` | Common | ⚠️ not creatable |
| `bpmn:DataStoreReference` | `BPMN_DATA_STORE_REFERENCE` | Common | ⚠️ not creatable |

**What can actually be created** (10 types via MCP `createFlowElement`, `WorkflowMcpTools.java`):
`START_EVENT`, `END_EVENT`, `USER_TASK`, `SERVICE_TASK`, `EXCLUSIVE_GATEWAY`, `PARALLEL_GATEWAY`,
`INCLUSIVE_GATEWAY`, `CALL_ACTIVITY`, `SUB_PROCESS`, `BOUNDARY_EVENT`. ⚠️ Note the `BOUNDARY_EVENT` **MCP
create-code** is separate from the `BpmnTaskType` **JSON enum**: there is **no `@JsonProperty("bpmn:BoundaryEvent")`**,
so a boundary event **cannot be serialized into `elements[].settings.type` at all** — hand-authoring one there
aborts the whole import (see the HARD RULE box above). Treat `BOUNDARY_EVENT` as **not usable** when building an
export by hand. The ⚠️-marked types exist in the enum,
but **can be created neither in the UI modeler nor via MCP** — don't plan a workflow around SendTask/ReceiveTask/
ScriptTask/EventBasedGateway/ComplexGateway/ManualTask/BusinessRuleTask/TextAnnotation/Association/
DataStoreReference (they can be authored only by hand via raw XML, but there is no runtime support).

**Types invented by old docs that do NOT exist in the enum:** `IntermediateCatchEvent`, `IntermediateThrowEvent`,
`BoundaryEvent`, `EndEvent`. There is **no** `BPMN_END` in the enum — the end-event projects onto `bpmn:Task` (see above).
Older platform documentation lists these nonexistent types — **that is stale information**; don't carry it
over.

Only **4 types** have their own settings panel and, correspondingly, extra `properties` in
`elements`: ServiceTask, UserTask, SequenceFlow, CallActivity, and everything else → `CommonTaskSettingsPanel`
(only `id`/`name`). The panel is chosen by `@BpmnSettingsPanel(taskType=...)` via
`SettingsPanelFactory.getaClass` with an annotation scan (
`AnnotationUtils.findClassesWithAnnotation("com.devsegment", BpmnSettingsPanel.class)`), fallback —
`CommonTaskSettingsPanel`.

---

## Per-variant reference

Below are the nodes of the **"Service Center Workflow"** example
(as you would see them with `del(.bpmnContent)` over `rep-objects.json`), with a property walkthrough.

The `settings.properties[].name` sets the extractor emits, by type (this is the exhaustive list of what is
actually extracted):

- **bpmn:Process**: `id`, `isExecutable` (+`name`/`documentation` if set)
- **bpmn:StartEvent**: `id` (+`name`/`initiator`/`formKey` if set)
- **bpmn:Task** (end-event projection): `id` (+`name` if the end-event is named)
- **bpmn:SequenceFlow**: `id`, `sourceRef`, `targetRef`, `conditionExpression`
- **bpmn:ExclusiveGateway**: `id`, `name`
- **bpmn:ServiceTask**: `rule`, `exclusive`, `id`, `delegateExpression`, `name`, `async`, `implementationType`, `implementation`
- **bpmn:UserTask**: `exclusive`, `candidateGroups`, `id`, `name`, `async`, `userActions`, `candidateUsers`

> **Universal `documentation` property.** The extractor puts `documentation` on the process and on
> every flow element, but in practice nobody fills it in, so it is `null` → `addProperty` drops it
>, so it is not visible in the JSON. If you set `<... documentation>` in the XML, the property appears.

### 1. Service Task (`bpmn:ServiceTask`) — an automatic step that executes Groovy rules

The full node:

```json
{
  "id": "Activity_0i94xes",
  "settings": {
    "type": "bpmn:ServiceTask",
    "properties": [
      { "name": "rule", "value": "694b564b-62c5-4ef6-ab48-9df14b2e7052,394a362b-8f0e-4535-8fab-388bd38364ad", "type": null, "control": null, "order": 0 },
      { "name": "exclusive", "value": true, "type": null, "control": null, "order": 0 },
      { "name": "id", "value": "Activity_0i94xes", "type": null, "control": null, "order": 0 },
      { "name": "delegateExpression", "value": "${ruleTask}", "type": null, "control": null, "order": 0 },
      { "name": "name", "value": "Update Integration", "type": null, "control": null, "order": 0 },
      { "name": "async", "value": false, "type": null, "control": null, "order": 0 },
      { "name": "implementationType", "value": "delegateExpression", "type": null, "control": null, "order": 0 },
      { "name": "implementation", "value": "${ruleTask}", "type": null, "control": null, "order": 0 }
    ]
  }
}
```

The corresponding `bpmnContent` fragment (note: **the element is in the default namespace, with no `bpmn:`
prefix**; only `flowable:` has a prefix):

```xml
<serviceTask id="Activity_0i94xes" name="Update Integration"
             flowable:delegateExpression="${ruleTask}"
             flowable:rule="694b564b-62c5-4ef6-ab48-9df14b2e7052,394a362b-8f0e-4535-8fab-388bd38364ad">
  <incoming>Flow_09odn7z</incoming>
  <outgoing>Flow_19aqllu</outgoing>
</serviceTask>
```

Fields (`name` · type · meaning · required · default · backing):

| Property | Type | Meaning | Required? | Default | Backing |
|---|---|---|---|---|---|
| `id` | string | node id (matches the id in the XML) | yes | — | `FlowElement.getId()` (`FlowableWorkflowServiceImpl.java`) |
| `name` | string | task label; used in logs/history | no | skipped if null (`addProperty`) | `flowElement.getName()` |
| `delegateExpression` | string | which Java delegate to execute. Values come from `getDelegateExpressions` (`RimmController.java`); the only registered one is `${ruleTask}` (the token itself comes from the Spring bean name `@Component("ruleTask")`, `RimmController.java` builds the key as `${…}` from `Component.value()`; the bean is `RuleTask`, while `@JavaDelegateCnf(name="Rule Task")` only sets the display name). **Dollar-brace `${...}`, NOT `#{...}`** | yes (for a rule task) | `${ruleTask}` | `serviceTask.getImplementation()` |
| `implementation` | string | the same value as `delegateExpression` (duplicated by the extractor) | yes | `${ruleTask}` | `serviceTask.getImplementation()` |
| `implementationType` | string | Flowable implementation type | yes | `delegateExpression` | `serviceTask.getImplementationType()` |
| `rule` | string | **CSV of Groovy rule UUIDs** (order = execution order). In the XML — the `flowable:rule` attribute | no | — | the `flowable:rule` **attribute** (generic attribute loop, see "How `elements` is derived") |
| `exclusive` | boolean | Flowable exclusive flag of the activity | no | `true` | `activity.isExclusive()` |
| `async` | boolean | asynchronous execution | no | `false` | `activity.isAsynchronous()` |
| `resultVariableName` | string | result variable name (usually absent) | no | skipped if null | `serviceTask.getResultVariableName()` |

**How `rule` is set in the UI:** the `ServiceTaskSettingsPanel.java` panel shows a `delegateExpression`
dropdown; if `${ruleTask}` is chosen, a `rule` control is added (a multi-select of rules of
types `EXECUTION_RULE` and `VALIDATION_RULE`, `ruleType=[EXECUTION_RULE, VALIDATION_RULE]`, `singleSelect=false`).
Multiple rules are encoded as a CSV. When the delegate is changed to a non-`${ruleTask}` value, the `rule` control and
property are removed.

**Runtime:** `RuleTask.execute` (`RuleTask.java`) reads `rule` from the task variables, **splits on the
comma** (`ruleIds.split(",")`) and executes each rule **in order left to right**, running
**one shared** `ContextDataDto` through the chain (`context.getContextData()`). For each rule a
per-rule diff is computed and logged; the final mutated `contextData` is saved back into the
process variables (`workflowExecutionService.saveContextDataToProcessVariables`, `ContextDataDto.CONTEXT_DATA_VARIABLE_KEY`). **Access-change detection:** before execution an `AccessDto`
snapshot is taken; if a rule changed `access`, the engine updates `ProcessAccess`. Rules are of
type `EXECUTION_RULE`/`VALIDATION_RULE` (see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)).

> ⛔ **TRAP — a serviceTask rule that uses `context.<ctx>.<alias>.data` needs `<alias>` SEEDED into the process
> `contextData` FIRST, or it throws `No CRUD data available for CRUD: <alias>` (`DynamicRuleContext.groovy`).
> `.data` is evaluated on property access **before** `.get()/.put()` — a `?: [:]` fallback does NOT save you, and a
> rule cannot create the missing entry itself (`.data.put()` throws too; there is no seed-a-new-alias API).** The
> process's initial `contextData` **is the start form's contextData**, so the workflow's **start form** (the
> `process.table` `userStartProcessActions` → `formGroupIdentifier` form) MUST seed the process's main entity: give
> it **≥1 field bound `scope:"CRUD"` + `crudAlias:"<alias>"`** (any column of `<alias>`), so
> `FormPlugin.collectContextDataFromForm` creates `crudDataMap["<alias>"]`, which flows through `startProcess` into
> the process — the first serviceTask's `context.<ctx>.<alias>.data.get()/.put()` (and every downstream serviceTask
> reading the SAME entity) then works. **A start form whose fields are ALL `scope:"GLOBAL"` (attrs) seeds NOTHING —
> the first serviceTask throws.** Canonical shape: an **Intake** start form whose
> fields are all `scope:"CRUD", crudAlias:"ticket"`, with a first serviceTask that does
> `def t = context.<ctx>.ticket.data.get(); … context.<ctx>.ticket.data.put(context.<ctx>.ticket.service.create(t))`.
> A `scope:"GLOBAL"` field is fine only for **process variables** the rule reads via `context.data.getAttr(...)` —
> it never seeds a CRUD entity. (Headless start — scheduler/action, no form — must pass an initial `contextData`
> whose `crudDataMap["<alias>"]` exists; the document's exact shape and the rule that builds it are
> [27](27-event-driven-process-start.md) §4.) `validate` WARNs when a workflow's
> serviceTask uses `<alias>.data` but no start form seeds `<alias>` (`_check_workflow_start_seeds_entity`) —
> and what an unseeded alias costs is silence, not an error: the executor auto-creates an empty envelope for
> it, so `.data.get()` answers an empty map and the task computes nulls. The throw `No CRUD data available for
> CRUD: <alias>` is the other failure — a missing CONTEXT entry ([27](27-event-driven-process-start.md) §3
> step 4, §7).

### 2. User Task (`bpmn:UserTask`) — a human step with action buttons

The full node (long UUIDs/localizations trimmed):

```json
{
  "id": "Activity_0b6e033",
  "settings": {
    "type": "bpmn:UserTask",
    "properties": [
      { "name": "exclusive", "value": true, "type": null, "control": null, "order": 0 },
      { "name": "candidateGroups", "value": "", "type": null, "control": null, "order": 0 },
      { "name": "id", "value": "Activity_0b6e033", "type": null, "control": null, "order": 0 },
      { "name": "name", "value": "Technician review", "type": null, "control": null, "order": 0 },
      { "name": "async", "value": false, "type": null, "control": null, "order": 0 },
      { "name": "userActions", "value": "{\"actions\":[ ... ],\"errors\":[]}", "type": null, "control": null, "order": 0 },
      { "name": "candidateUsers", "value": "", "type": null, "control": null, "order": 0 }
    ]
  }
}
```

`userActions` is a **JSON string** (a serialized `UserTaskActionsDto`) sitting inside `value` (double
escaping). The parsed content of node `Activity_0b6e033`:

```json
{
  "actions": [
    {
      "id": "adb54f7a-dcd0-4f9f-8e5d-b07f97e6f4a9",
      "localizedNames":       { "en_US": "Approve", "hy_AM": "Հաստատել" },
      "localizedButtonNames": { "en_US": "Approve", "hy_AM": "Հաստատել" },
      "predicateIdentifier": "8e9e0637-8acf-4b72-9ee7-454e20f5f420",
      "onBeforeUserTaskStartRuleIdentifier": null,
      "onBeforeUserTaskCompleteRuleIdentifier": "4b1404c4-e21c-4a14-81dc-caa8c57d24dd",
      "validationRuleIdentifiers": null,
      "direct": "on",
      "formGroupIdentifier": "3d362522-d30e-41d2-897f-3deaf296d678",
      "taskId": null,
      "completeUserTask": "on",
      "icon": null,
      "submitForm": null,
      "orInitLocalizedNames":       { "en_US": "Approve", "hy_AM": "Հաստատել" },
      "orInitLocalizedButtonNames": { "en_US": "Approve", "hy_AM": "Հաստատել" }
    },
    {
      "id": "92d26a7f-df99-4ad7-ba40-5cc5e97e0c25",
      "localizedNames":       { "en_US": "Reject", "hy_AM": "Մերժել" },
      "localizedButtonNames": { "en_US": "Reject", "hy_AM": "Մերժել" },
      "predicateIdentifier": "8e9e0637-8acf-4b72-9ee7-454e20f5f420",
      "onBeforeUserTaskStartRuleIdentifier": null,
      "onBeforeUserTaskCompleteRuleIdentifier": "31970c0c-f7cf-42ce-a5a8-7e8266cbd3fc",
      "validationRuleIdentifiers": null,
      "direct": "off",
      "formGroupIdentifier": "3d362522-d30e-41d2-897f-3deaf296d678",
      "taskId": null,
      "completeUserTask": "on",
      "icon": null,
      "submitForm": null,
      "orInitLocalizedNames":       { "en_US": "Reject", "hy_AM": "Մերժել" },
      "orInitLocalizedButtonNames": { "en_US": "Reject", "hy_AM": "Մերժել" }
    }
  ],
  "errors": []
}
```

The container is `UserTaskActionsDto {List<ActionDto> actions, List<ActionError> errors}`
(`UserTaskActionsDto.java`); `ActionError {predicateIdentifier, error}`. `errors` in a
definition is usually empty.

Node properties of a user task:

| Property | Type | Meaning | Required? | Default | Backing |
|---|---|---|---|---|---|
| `id`, `name`, `exclusive`, `async` | as for a service task | — | — | — | — |
| `candidateUsers` | string (CSV) | Flowable candidate users | no | `""` | `String.join(",", userTask.getCandidateUsers())` |
| `candidateGroups` | string (CSV) | Flowable candidate groups | no | `""` | `String.join(",", userTask.getCandidateGroups())` |
| `assignee` | string | explicit assignee | no | skipped if null | `userTask.getAssignee()` |
| `formKey` | string | Flowable form key | no | skipped if null | `userTask.getFormKey()` |
| `userActions` | string (JSON) | list of action buttons; in the XML — `flowable:userActions` | no | skipped if the attribute is absent | the `flowable:userActions` **attribute** (generic attribute loop), deserialized by `UserTaskActionsDto.fromJson` |

> **`candidateGroups`/`candidateUsers` value format.** Each is a **comma-separated string** (empty `""` = none),
> joined by the extractor from Flowable's candidate lists (`String.join(",", userTask.getCandidateGroups())` /
> `getCandidateUsers()`, `FlowableWorkflowServiceImpl.java`). Every workflow export checked carries only `""`, so
> there is **no live example** of the token form. In practice a user task's per-action visibility is gated not here but
> by an action `predicateIdentifier` running `service.security.hasAnyRoleGroup(...)` (§2 `ActionDto`), which the
> exports do use — prefer that over `candidateGroups`/`candidateUsers` unless you specifically need Flowable's
> candidate-inbox routing.

> **About `assignee`/`dueDate`/`priority`/timer-boundary.** In real exports a user task carries **only**
> `exclusive, candidateGroups, candidateUsers, id, name, async, userActions` — there are **NO** `dueDate`/`priority`
> properties, and no timer/boundary events appear in any workflow export checked. `assignee`/
> `candidateUsers`/`candidateGroups` **can** be set via MCP (`WorkflowMcpTools.java`), and `BOUNDARY_EVENT`
> **can be created** (its only setting is `attachedToRef`, `WorkflowMcpTools.java`), but
> `dueDate`/`priority`/`timerDuration`/`cancelActivity`/escalation are **found nowhere in the code or exports**.
> The old-doc sections about due-date/priority/escalation are **aspirational, not confirmed**. Don't carry them over.

Fields of a single `ActionDto` (backing — `UserTaskActionsDto.ActionDto`, `UserTaskActionsDto.java`):

| Field | Type | Meaning | Required? | Default | Backing/note |
|---|---|---|---|---|---|
| `id` | string (UUID) | action id | yes | — | |
| `localizedNames` | map locale→string | action label in the dropdown/history. The key is the full locale code `en_US` | yes | — |; resolved via `getLocalizedName`/`lookupLocalized` (fallback full→lang→first) |
| `localizedButtonNames` | map locale→string | submit-button label on the form (for non-direct). Empty → falls back to `localizedNames` | no | mirrors `localizedNames` |, `getLocalizedButtonName` |
| `predicateIdentifier` | string (UUID) | predicate rule: whether to show the action on this task/row | no | `null` (the string `"null"` is also treated as null, getter) | rule of type `PREDICATE` |
| `onBeforeUserTaskStartRuleIdentifier` | string (UUID) | EXECUTION rule when the task opens (for non-direct: before the form opens) | no | `null` | getter (`"null"`→null) |
| `onBeforeUserTaskCompleteRuleIdentifier` | string (UUID) | EXECUTION rule before the task completes (on click/complete) | no | `null` | getter (`"null"`→null) |
| `validationRuleIdentifiers` | string (CSV) | validation rules; all must pass | no | `null` | getter (`"null"`→null) |
| `direct` | `"on"`/`"off"` | `"on"` = direct action (no form, execute + complete immediately); `"off"` = open the form | no | — | `isDirect()` = `direct=="on"` |
| `formGroupIdentifier` | string (UUID) | the form group to open (for non-direct). May be the string `"null"` or `null` | no | — |; see [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) |
| `completeUserTask` | `"on"`/`"off"` | whether to complete the task after the action | no | `"on"` (null is normalized to `"on"` in `fromJson`; `shouldCompleteUserTask` = `!"off"`) | |
| `icon` | string | icon CSS class (e.g. `pe-7s-album`, `pe-7s-pen`, `pe-7s-check`) | no | `null` | |
| `submitForm` | boolean | for non-direct: whether to submit the form (validation+persist+complete-rule) or only run the rules. null → true | no | `null`→`true` (`shouldSubmitForm`) | |
| `formInModal` | boolean | for non-direct: `true` → the Process Table opens this action's form in a DIALOG over the table and a successful submit refreshes the table in place; `null`/`false` → navigate to the form group's page. **A boolean here, NOT `"on"`/`"off"`** — same shape as `submitForm`. | no | `null`→`false` (`shouldOpenInModal`) | |
| `modalWidth` | string | width of that dialog — any CSS length (`"90%"`, `"400px"`), applied as `max-width`. Blank → `80%`. Only read when `formInModal:true` | no | `null`→`80%` | |
| `taskId` | string | runtime field (usually `null` in a definition) | no | `null` | |
| `orInitLocalizedNames` / `orInitLocalizedButtonNames` | map | mirrors of `localizedNames`/`localizedButtonNames`, added by lazy initializer getters at serialization time (`getOrInitLocalizedNames`, `getOrInitLocalizedButtonNames`) | no | — | serialized, ignored on read as a lazy-init artifact |

> **`formInModal` is honoured wherever a Process Table renders the action** — its per-row actions (these) and
> its global/start actions. In the dialog the buttons the form page would put on its breadcrumb — the action's
> submit button, `Drafts`, and, while a List control's item form is open, that item form's own buttons —
> render at the bottom of the dialog, and a successful submit closes it and refreshes the table in place
> instead of navigating back. Nothing else opens the task's form in a dialog: a user task reached any other
> way still uses its form page.

**Semantics of `direct` / `submitForm` / `completeUserTask`:**
- `direct:"on"` — a "quick" action (typical in the process table): on click `onBeforeUserTaskCompleteRuleIdentifier`
  runs immediately and (if `completeUserTask:"on"`) the task completes, **without a form**.
  `formGroupIdentifier` may be `null`.
- `direct:"off"` — on click `formGroupIdentifier` (the form group) opens. On submit, if
  `submitForm≠false`, validations (`validationRuleIdentifiers`) + form persist + complete-rule +
  task completion run.  `submitForm=false` — only run the rules without persisting the form.

> ⛔ **RUNTIME FLOOR — the action's own `validationRuleIdentifiers` only run on a build that carries the
> 2026-08-08 `FormPlugin` fix.** Before it, the submit request carried ONLY the FORM's validators
> (`FormDto.validators`); the action's slot was read nowhere on this path, so a precondition authored per
> action never ran and its failure surfaced later as a raw *"Could not execute rule(s) …"* from the
> service task instead of a field error in the form. When you must work against an older runtime, put
> preconditions that MUST block a submit into `FormDto.validators` and guard them by state so they do not
> fire on the other actions of the same form (a form validator runs on EVERY submit of that form —
> including "send back for rework", which you rarely want to block).
>
> Design rule either way: **every precondition an action rule enforces with a `throw` should also exist as
> a validation** on the action that triggers it. The throw stays as the server-side invariant; the
> validation is what the user is supposed to see. And keep the two from duplicating — if a form validator
> already reports a condition on every submit, do not repeat it in the action validator, or the user gets
> the same message twice.
- `completeUserTask:"off"` — update the process variables but **leave the task open** (multi-step /
  draft save).

**Legacy `userActions` format.** Older workflows carry actions that
use the **old single `name` field** instead of `localizedNames`:

```json
{"actions":[{"id":"d6ca9de7-...","name":"Escalate","predicateIdentifier":"2566c158-...",
  "onBeforeUserTaskStartRuleIdentifier":null,"onBeforeUserTaskCompleteRuleIdentifier":null,
  "validationRuleIdentifiers":null,"direct":"off","formGroupIdentifier":"null","taskId":null,
  "completeUserTask":"on","icon":"pe-7s-pen"}],"errors":[]}
```

`UserTaskActionsDto` and `ActionDto` are marked `@JsonIgnoreProperties(ignoreUnknown=true)`
(`UserTaskActionsDto.java`) precisely so that legacy `name` and any unknown field don't break parsing
(one property shouldn't sink the whole parse — otherwise `fromJson` would return an empty DTO). **For new builds
use `localizedNames`/`localizedButtonNames`, not `name`.** Note: `formGroupIdentifier`
in the legacy sample is set to the string `"null"` — that's acceptable (the `"null"` string is treated as null), but it's cleaner to put
JSON null.

### 3. Sequence Flow (`bpmn:SequenceFlow`) — a transition, plain and conditional

**Plain transition** (no condition):

```json
{ "id": "Flow_19aqllu", "settings": { "type": "bpmn:SequenceFlow", "properties": [
  { "name": "id", "value": "Flow_19aqllu", "type": null, "control": null, "order": 0 },
  { "name": "sourceRef", "value": "Activity_0i94xes", "type": null, "control": null, "order": 0 },
  { "name": "targetRef", "value": "Activity_0b6e033", "type": null, "control": null, "order": 0 } ] } }
```
```xml
<sequenceFlow id="Flow_19aqllu" sourceRef="Activity_0i94xes" targetRef="Activity_0b6e033" />
```

**Conditional transition** (an exit out of an exclusive gateway; executes a predicate):

```json
{ "id": "Flow_1y7np5j", "settings": { "type": "bpmn:SequenceFlow", "properties": [
  { "name": "id", "value": "Flow_1y7np5j", "type": null, "control": null, "order": 0 },
  { "name": "sourceRef", "value": "Gateway_1wtqcro", "type": null, "control": null, "order": 0 },
  { "name": "targetRef", "value": "Event_11uhywd", "type": null, "control": null, "order": 0 },
  { "name": "conditionExpression",
    "value": "${predicateSequence.execute(execution, 'aefcf850-eeb8-4b24-83ba-6dd663ee3b52')}",
    "type": null, "control": null, "order": 0 } ] } }
```

The corresponding XML (a transition from the gateway to another branch). ⚠️ **The `flowable:sequence` +
`flowable:rule` attributes on the `<sequenceFlow>` are NOT extracted into `elements` (only `conditionExpression`
is) — but you MUST still emit them in `bpmnContent`.** They are the BPMN editor's source-of-truth for the
condition (`WorkflowBpmn2ModelerPanel.js` bakes `conditionExpression` from `sequence`+`rule`, one-way, in
the browser). WITHOUT them the editor's SequenceFlow panel shows `sequence`/`rule` **EMPTY**, and **re-opening +
saving the workflow DROPS the `<conditionExpression>`** → the flow silently goes unconditional, which breaks the
exclusive gateway's XOR routing (a no-condition flow counts as always-true, so the branch is grabbed whenever the
gateway reaches it in flow order, regardless of the intended predicate — see the Exclusive Gateway failure modes
below). Anything the modeler itself saved always
carries them; emit exactly this shape (`flowable:sequence` = the template, `flowable:rule` = the predicate UUID that
fills `%s`):

```xml
<sequenceFlow id="Flow_0ffbm4d" sourceRef="Gateway_1wtqcro" targetRef="Activity_0sex5jq"
              flowable:sequence="${predicateSequence.execute(execution, '%s')}"
              flowable:rule="95d3e4de-9c48-40b4-aacd-190043064afe">
  <conditionExpression xsi:type="tFormalExpression">${predicateSequence.execute(execution, '95d3e4de-9c48-40b4-aacd-190043064afe')}</conditionExpression>
</sequenceFlow>
```

Fields:

| Property | Type | Meaning | Required? | Default | Backing |
|---|---|---|---|---|---|
| `id` | string | transition id | yes | — | |
| `name` | string | the arrow's label on the canvas. Optional in general — **required on every branch out of a decision** (§4): the engine routes on the condition, a reader routes on the label | on branches | — | `sequenceFlow.getName()` |
| `sourceRef` | string | source id | yes | — | `sequenceFlow.getSourceRef()` |
| `targetRef` | string | target id | yes | — | `sequenceFlow.getTargetRef()` |
| `conditionExpression` | string | Flowable condition. For a conditional transition = `${predicateSequence.execute(execution, '<predicateUuid>')}` | no | skipped if null | `sequenceFlow.getConditionExpression()` |
| `sequenceExpression` | string | extra extension (usually absent) | no | — | from extension `sequenceExpression` |

**How it is set in the UI:** `SequenceFlowSettingsPanel.java` — a `sequence` dropdown; when the value
`${predicateSequence.execute(execution, '%s')}` is chosen (the only one from `getSequenceExpressions`,
`RimmController.java`; the bean `predicateSequence` = `PredicateSequenceFlowExecutor`
`@JavaSequenceCnf(name="Predicate Sequence")`) the controls `rule` (predicate,
`RuleType.PREDICATE`) and `conditionExpression` (textField) are added. The plugin substitutes the
chosen predicate UUID in place of `%s`.

**Runtime:** `PredicateSequenceFlowExecutor.execute` (`PredicateSequenceFlowExecutor.java`) executes the
predicate rule by UUID. **Three outcomes — only one is the "unconditional" you might expect:**
- **id is empty/null** (`execute(execution, '')` / no predicate) → returns `true`. This is the ONLY
  "always allow" path, and it needs the id *itself* empty.
- **id is a non-empty UUID pointing at a MISSING rule** (a dangling ref — e.g. the predicate was deleted) →
  **hard runtime error**: the Feign lookup throws, the executor's catch is commented out, so the
  exception propagates and **FAILS the gateway/process transaction**. It does NOT default to false or route on.
- **id points at an EXISTING but EMPTY-bodied rule** → `ExecuteResponse.extractBooleanResult` **FAILS OPEN to
  `true`** (`ExecuteResponse.java`) → the branch is **always taken**.

So a "clear the condition to make it unconditional" edit is a trap: the correct unconditional flow is the
**ABSENCE of the `<conditionExpression>`** (a bare `<sequenceFlow>`), never an empty/dangling predicate. The result
is coerced to boolean. Several outgoing conditional transitions from an exclusive gateway = branch on the first
`true` — **for XOR logic you need exactly one unconditional default transition** (no `conditionExpression`) for the
case where all predicates returned `false`, otherwise the process hangs on the gateway — and that transition has to
be named in the gateway's own `default` attribute, or the routing depends on document order (the full contract,
including why the fallback's settings panel is empty and why every branch needs a `name`, is in §4). Like `RuleTask`, the
executor detects access changes.

> **⚠️ Two different predicate encodings (don't confuse them).** (a) **UI export** (what's in the real files): in
> `<conditionExpression>` it writes `${predicateSequence.execute(execution, '<uuid>')}`. (b) **MCP path**
> (`WorkflowMcpTools.java`): when `predicateIdentifier` is passed, it sets the extension `sequenceExpression`
> `conditionExpression = "${predicateResult}"` — **a different runtime contract**. For hand-building compatible with
> UI exports, use form (a); don't mix them.

### 4. Exclusive Gateway (`bpmn:ExclusiveGateway`) — branching

```json
{ "id": "Gateway_1wtqcro", "settings": { "type": "bpmn:ExclusiveGateway", "properties": [
  { "name": "id", "value": "Gateway_1wtqcro", "type": null, "control": null, "order": 0 },
  { "name": "name", "value": "Lalala", "type": null, "control": null, "order": 0 } ] } }
```
```xml
<exclusiveGateway id="Gateway_1wtqcro" name="Lalala">
  <incoming>Flow_1ywwz4b</incoming>
  <outgoing>Flow_0ffbm4d</outgoing>
  <outgoing>Flow_1y7np5j</outgoing>
</exclusiveGateway>
```

> That is the SHAPE the editor round-trips, not a model to copy: it has no `default` and no branch labels, which
> is exactly the gateway that gets stuck or routes on document order. The shape to author is below.

A gateway has no settings of its own (the panel is `CommonTaskSettingsPanel`, which returns an empty set of controls).
Only `id` and an optional `name` — **plus the `default` attribute, which no panel gives a designed control for.**
It is not invisible: the settings panel lists every attribute of the selected element and renders a plain labelled
row for the ones it has no control for, so a gateway that has a `default` shows a `default` row with the flow id
in it. But there is no picker, nothing says the row is load-bearing, and selecting the BRANCH — the natural move
when you are asking "why is this flow empty?" — shows nothing at all, because the attribute lives on the gateway.
To set it in the editor: select the branch, open the canvas wrench/replace menu and pick **Default flow** (stock
bpmn-js, which writes the attribute on the SOURCE element). Authoring by hand, it is yours to write and yours to
keep. The branching logic itself lives **in the outgoing

#### How the engine actually picks the exit (all element types)

One algorithm decides this for every element that has outgoing flows (`ExclusiveGatewayActivityBehavior` for XOR,
the shared `TakeOutgoingSequenceFlowsOperation` for everything else, flowable-engine 7.0.1):

1. walk the outgoing flows and keep the ones whose condition is `true` — **a flow with NO `<conditionExpression>`
   counts as `true`** — while **always skipping the flow named in the element's `default`**;
2. if that leaves nothing, take the `default` — but only if it resolves to one of **this** element's outgoing flows;
3. still nothing → **throw** `No outgoing sequence flow ... could be selected` → the case is **STUCK**.

An exclusive gateway then takes the **first** survivor; every other element takes **all** of them, one token each.
`default` is supported on activities too, not just gateways — a task with two conditional exits obeys the same rules.

#### The one correct XOR shape

```xml
<exclusiveGateway id="gw" name="Order confirmed?" default="fConfirmed"> … </exclusiveGateway>
<sequenceFlow id="fRejected"  name="Rejected"  sourceRef="gw" targetRef="…"> <conditionExpression …/> </sequenceFlow>
<sequenceFlow id="fConfirmed" name="Confirmed" sourceRef="gw" targetRef="…" />
```

one conditional branch per outcome + **exactly one unconditional fallback that the gateway names in `default`**.
Read it as `if (rejected) … else …`. The fallback carrying no predicate is **not an unfinished branch — it IS the
`else`**, and it is the only shape that neither gets stuck nor flips when the flows are re-ordered.

> **⚠️ What that looks like in the editor, and why it reads like a bug.** Select the fallback branch: alongside
> the flow's own id/sourceRef/targetRef its settings panel shows an EMPTY `sequence` dropdown and **no rule and no
> condition**, because `SequenceFlowSettingsPanel` only adds the `rule`/`conditionExpression` controls once a
> `sequence` template has been chosen, and the fallback deliberately has none. And `default` is not on this element at all — it is an
> attribute of the GATEWAY — so selecting the branch cannot show it to you. So
> on screen the `else` branch is indistinguishable from a branch somebody forgot to finish. **Two things make it legible, and both are
> the author's job:** the canvas draws the default flow with the standard **slash marker** across the start of the
> arrow (bpmn-js renders it whenever the source's `default` points at that flow — so if you do NOT see the slash,
> the `default` attribute is missing or misspelt), and **every branch out of a decision must carry a `name`**
> (`Approved`/`Rejected`, `Yes`/`No`). Two unlabelled arrows out of a diamond tell a reviewer nothing.

#### Semantics by gateway type

- **Exclusive** (`bpmn:ExclusiveGateway`) — XOR: first `true`/unconditional flow wins, `default` is the `else`.
- **Parallel** (`bpmn:ParallelGateway`) — AND: fork onto **all** branches + join waits for all. ⛔ It takes every
  outgoing flow **without evaluating conditions at all**, and it has **no fallback semantics**: a
  `conditionExpression` or a `default` on a parallel branch is dead code that reads as a decision. A parallel
  gateway therefore needs **no predicates** — that is the point of it. (Label its branches only if the labels say
  something; there is no decision to read.)
- **Inclusive** (`bpmn:InclusiveGateway`) — OR: every branch whose condition is `true`, in parallel. Same fallback
  contract as XOR: all-conditional with no `default` throws the same way the moment they are all `false`.
- `Complex`/`EventBased` — in the enum but not creatable in UI/MCP (see the types table).

Structurally, `ParallelGateway`/`InclusiveGateway` in `elements` are laid out the same way (only `id`/`name`).
⚠️ **`elements[]` does NOT carry `default`** — the platform re-derives `elements` from `bpmnContent` on every save,
and `bpmnContent` is what is deployed, so the XML is the single source of truth for it. Both the editor (bpmn-js)
and Flowable's own serializer preserve the attribute on a round-trip; nothing else will re-create it if it is lost.

`validate` (`_check_gateway_branching`) WARNs on every failure mode above: a `default` that names a flow which is
not an outgoing flow of that element, a `default` that also carries a condition (never evaluated), all-conditional
with no `default`, an unconditional fallback that is not the `default`, a second unconditional branch on an XOR,
conditions/`default` on a parallel gateway, two unconditional exits out of a plain task (an implicit **fork**, not
a choice), and unlabelled decision branches.

### 5. Start Event / End Event (`bpmn:StartEvent` / `bpmn:Task`)

```json
{ "id": "Event_1pcczlc", "settings": { "type": "bpmn:StartEvent", "properties": [
  { "name": "id", "value": "Event_1pcczlc", "type": null, "control": null, "order": 0 } ] } }
```
```xml
<startEvent id="Event_1pcczlc"><outgoing>Flow_0467z7o</outgoing></startEvent>
```

**The end event** is serialized as a node of type **`bpmn:Task`** (in this workflow — `Event_11uhywd`, name `bububu`),
because there is no separate `BpmnTaskType` for EndEvent (`FlowableWorkflowServiceImpl.java`):

```json
{ "id": "Event_11uhywd", "settings": { "type": "bpmn:Task", "properties": [
  { "name": "id", "value": "Event_11uhywd", "type": null, "control": null, "order": 0 },
  { "name": "name", "value": "bububu", "type": null, "control": null, "order": 0 } ] } }
```
```xml
<endEvent id="Event_11uhywd" name="bububu"><incoming>Flow_1y7np5j</incoming></endEvent>
```

For a StartEvent the extractor also puts `initiator`/`formKey` if set; in the example they are null →
skipped.

### 6. Process (`bpmn:Process`) — the root element

```json
{ "id": "Process_1", "settings": { "type": "bpmn:Process", "properties": [
  { "name": "isExecutable", "value": true, "type": null, "control": null, "order": 0 },
  { "name": "id", "value": "Process_1", "type": null, "control": null, "order": 0 } ] } }
```

`createProcessElement` puts `id`/`name`/`documentation`/`isExecutable`. The process `id` is the
workflow's **process key** — what a call activity's `calledElement` names (§7) and what ends up in
`processDefinitionId` on deploy as a prefix (`<process id>:6:<uuid>`, the middle number being the
Flowable deployment version; Flowable drops the prefix and leaves a bare id once the whole string would
exceed 64 characters). New diagrams are seeded with `Process_<workflow identifier>` so the key is unique
per workflow; older content still carries the shared `Process_1` the modeler used to seed and is never
rewritten — see the warning in §7. Always `isExecutable=true`.

### 7. Call Activity (`bpmn:CallActivity`) — calling another workflow

⚠️ Call activities are vanishingly rare in practice, so there is no worked example to copy.
The concept: the parent is suspended, the child process runs
to its own EndEvent, then control returns; return values flow via `context.data.setAttr(...)`
in the child → readable in the parent. Contrast with **SubProcess** (`bpmn:SubProcess`): an inline container in the **same**
process instance with scoped variables, no reuse across workflows; a CallActivity is a separate
child instance, reusable.

Per the panel code (`CallActivitySettingsPanel.java`) its `properties` in `elements` would include:

| Property | Type | Meaning | Backing |
|---|---|---|---|
| `calledElement` | string | which workflow to call — the callee's **process key**, i.e. the very string in its own `<process id="...">`. The list — `getCallableWorkflows` (`WorkflowRimmServiceImpl.java`), one option per process key, name = `"<name> (<identifier>) — Deployed / Draft / Not deployed"`. Workflows that are **not deployed yet are offered too** (see the deploy note below) | dropdown SERVICE |
| `inheritBusinessKey` | boolean | inherit the parent's business key | booleanField |
| `inheritVariables` | boolean | pass all variables (contextData) into the child process | booleanField |

In XML this is `<callActivity id="..." calledElement="<process key>" flowable:inheritVariables="true"
flowable:inheritBusinessKey="true"/>`.

> ⚠️ **`calledElement` is a process KEY, never a process definition id.** Flowable resolves this attribute
> by key (`CallActivityBehavior.getProcessDefinitionByKey`) and picks the callee's latest deployed version
> for the tenant. Writing a definition id (`<key>:<version>:<dbId>`) makes the engine look up that entire
> string *as a key*, so it never matches, and the start fails with a message that reads like a deployment
> fault even though the callee is deployed in the right tenant:
> `Process definition <key>:<version>:<id> was not found in sameDeployment[false] tenantId[...]`.
> A hand-authored `.mrjun` must therefore set `calledElement` to the callee workflow's `<process id>`;
> `mrjun.py validate` checks exactly that (`_check_callactivity_resolves`). To deliberately pin one
> version — rarely what you want, since it stops tracking redeploys — set
> `flowable:calledElementType="id"` alongside the id; without that attribute the value is always read as
> a key. ⚠️ The exact mapping of CallActivity extension attributes is **not covered by an explicit
branch** of `createWorkflowElement` — a CallActivity is an `Activity`, so the common `async`/`exclusive`
plus custom extension attributes via the generic loop are captured; **`calledElement`/`inherit*` in
`elements` will have to be added by hand from the XML when building manually.** ⚠️ UNVERIFIED on real data —
treat a CallActivity as experimental and test it live before you rely on it.

> **Deploying a caller deploys its callees first.** Flowable never looks at `calledElement` before
> runtime — nothing at deploy time validates it — so a parent whose callee is still a draft deploys
> silently and only fails when someone runs it. Deploy therefore walks the call graph first
> (`FlowableWorkflowServiceImpl.deployCalledWorkflows`): every workflow reachable through a call activity
> whose latest version is not deployed is deployed **before** the caller, deepest first, each at most
> once. The workflows list's per-row Deploy button asks for confirmation and names them, because
> publishing a callee publishes whatever draft it currently holds.
> **Cycles are fine** — A calls B, B calls A, or any longer loop, including a workflow that calls itself.
> The engine has no concept of a call graph and resolves the reference lazily at runtime, so no deploy
> order is more correct than another; the walk keeps a visited set, deploys every node once and moves on.
> What the walk deliberately does **not** do is guess: a `calledElement` naming a process no workflow of
> the project declares, or one declared by **several** workflows, is logged and skipped (the caller still
> deploys) — an ambiguous key is ambiguous for the engine too, which simply runs the latest version of
> that key.
>
> ⚠️ **Process keys must be unique per workflow.** The modeler used to seed every new diagram with
> `<process id="Process_1">`, so older projects can hold several workflows sharing one key — and to
> Flowable those are ONE target. New diagrams are now stamped with `Process_<workflow identifier>`
> (`WorkflowBpmn2ModelerPanel.js`, matching the MCP tool); existing content is never rewritten, because
> renaming a deployed key would orphan running instances and every `calledElement` pointing at it. Where
> a duplicate remains, the dropdown shows the colliding workflows as ONE option that says so.

Via MCP `createFlowElement` (`WorkflowMcpTools.java`) a CallActivity **can be created** — this confirms
type support, but is not a substitute for a working example.

---

## How `elements` is derived from `bpmnContent`

This is critical for building by hand. On `saveWorkflow`/`deployWorkflow` the server parses the XML
(`BpmnXMLConverter.convertToBpmnModel`, `FlowableWorkflowServiceImpl.java`) and for each `FlowElement`
builds a `WorkflowElementDto` (`createWorkflowElement`). The rules:

1. **Node type** = `FlowElement → BpmnTaskType` (`mapFlowElementToBpmnTaskType`):
   `startEvent`→`bpmn:StartEvent`, **`endEvent`→`bpmn:Task`**, `userTask`→`bpmn:UserTask`
   `serviceTask`→`bpmn:ServiceTask`, `sequenceFlow`→`bpmn:SequenceFlow`,
   `exclusiveGateway`→`bpmn:ExclusiveGateway`, etc. Plus a separate `bpmn:Process` node for the
   `<process>` itself (`createProcessElement`).
2. **Common properties** for all: `id`, `name`, `documentation`. `addProperty` **skips
   null values** (guard) — that's why nodes without a name have no `name`, and a service task without
   a rule has no `rule`. `documentation` is skipped everywhere (always null).
3. **For an Activity** (userTask/serviceTask/callActivity/subProcess): `async`, `exclusive`.
4. **UserTask**: `assignee`, `candidateUsers` (CSV), `candidateGroups` (CSV), `formKey`. **`userActions` does
   NOT come from this branch** — it is a custom XML **ATTRIBUTE** (`flowable:userActions`, declared
   `isAttr: true` by the modeler) and is picked up by the generic attribute loop of point 8.
5. **ServiceTask**: `implementationType`, `implementation`, `resultVariableName`, `delegateExpression`
   (=`implementation`). **`rule` does NOT come from this branch either** — it is a custom XML **ATTRIBUTE**
   (`flowable:rule`, `isAttr: true`) and is picked up by the generic attribute loop of point 8.
6. **SequenceFlow**: `sourceRef`, `targetRef`, `conditionExpression`, optionally `sequenceExpression`
   from an extension.
7. **StartEvent**: `initiator`, `formKey`.
8. **Generic extension ATTRIBUTES** of any element are added by the loop (`flowElement.getAttributes()`).
   This loop runs **unconditionally for EVERY flow element** — before the `instanceof` branches below (the first,
   `if (flowElement instanceof SequenceFlow)`, comes after it). Important clarifications (verified on the data):
   - `rule` on a service task and `userActions` on a user task come from **THIS loop** — they are custom
     ATTRIBUTES on the task tag, stored under their bare local name (`rule`, `userActions`, no prefix). The
     extractor also has `getExtensionElements()` branches for both names, but with attribute-form XML those
     branches never fire — see the ⛔ below before you reach for `<extensionElements>`.
   - `flowable:sequence`/`flowable:rule` on a conditional sequence flow (example `Flow_0ffbm4d`) **do NOT make it**
     into `elements` — only `conditionExpression` is extracted (verified: the node has just
     `id`/`sourceRef`/`targetRef`/`conditionExpression`). The reason is **not** that the loop is skipped for a
     SequenceFlow (it isn't — the loop runs first, unconditionally): Flowable's **sequence-flow converter does not
     collect custom attributes at all** (the service-task/user-task converters do), so for a flow the Map the loop
     iterates is simply empty. **Emit those two attributes anyway** — the modeler needs them to keep the condition
     on re-save (canonical shape in §3 "Sequence Flow").
   - The loop picks up any genuinely generic (non-flowable) attributes of nonstandard nodes.

> ⛔ **Author `rule` and `userActions` ONLY as ATTRIBUTES on the task tag** — `flowable:rule="<uuid>[,<uuid>]"`
> on the `<serviceTask>`, `flowable:userActions="<escaped JSON>"` on the `<userTask>` (exactly what the copy-paste
> templates in this doc and `mrjun.py workflow add` emit). Writing them as an
> `<extensionElements><flowable:rule>…</flowable:rule></extensionElements>` child **silently breaks the binding**:
> the extension-element branch stores the parser object's `toString()` (a `[…ExtensionElement@…]` string, not your
> CSV), and because `ElementSettingDto`'s property set is a `HashSet` keyed on the property NAME only, the correct
> text that the generic extension pass would add later under the same name `rule` is dropped as a duplicate — the
> garbage wins. `RuleTask` then splits that string on commas, resolves no rule id, and the service task executes
> **nothing**, with no error; the user-task equivalent renders **no action buttons**. This is not a paper
> distinction: import **re-derives `elements` from the XML** (your hand-written `elements[]` is discarded), so the
> attribute form is the only thing that decides whether the binding exists — and `mrjun.py validate` only inspects
> the attribute form, so it will not warn you.

**The diagram section `<bpmndi:*>`** (coordinates `dc:Bounds`, `di:waypoint`) is NOT extracted into `elements` —
it is only for rendering in the editor. The coordinates can be anything — you will meet large negative values
(`x="-31658"`) in authored diagrams, which is normal: the canvas was simply scrolled. When building by hand, DI can be generated
formally: one `<bpmndi:BPMNShape>` per node and waypoints per transition.

---

## How to construct from scratch

The goal is to set `rep-objects.json.workflows[]` by hand so that after import you get a working workflow.

### BPMN skeleton and namespaces (important)

> ⛔ **`bpmnContent` MUST be well-formed XML — a malformed one ABORTS the ENTIRE import.** On import Flowable
> `saveWorkflowBackend` parses `bpmnContent`; if it is not well-formed — an unclosed tag, an unescaped `&`/`<`/`>`,
> or (the #1 hand-authoring mistake) a **`flowable:…` attribute used without declaring `xmlns:flowable`** — it
> throws *"Workflow validation failed … invalid XML"*, which aborts `CmsProjectServiceImpl.initAllObjects` and
> **skips everything imported AFTER workflows** — rules, contexts, form groups, forms, settings, processGroups,
> role groups and mail/PDF templates. Sources, the `project-db.dump` restore, queries and schedulers ran **earlier**
> and survive, so do NOT read this symptom as a lost database: the *"no source selected / dump not restored"*
> fingerprint belongs to a bad `elements[].settings.type` or a string `settings[].content`, which fails Jackson
> **before anything at all is saved**. So: **prefer `mrjun.py workflow add`** (it ET-parses before saving); when you hand-edit
> the XML, declare EVERY namespace you use (see the root below), close every tag, escape entities inside
> `conditionExpression`/text, and make every `sequenceFlow` `sourceRef`/`targetRef` point at a real element `id`.
> `validate` now ET-parses `bpmnContent` and ERRORs on malformed XML / missing `<process>` / dangling flow refs —
> but a green validate is still not import-proof; do a live import + read `log/ui.log`.

> ⛔ **EXACTLY ONE `<startEvent>` per `<process>`.** `BpmnValidationService` raises the ERROR
> `MULTIPLE_START_EVENTS` (*"Your workflow has multiple start events, but only one start event is allowed"*) and the
> save throws — aborting the import at the workflow step exactly like malformed XML above. (Zero start events is
> only a WARNING, `NO_START_EVENT`, but such a process can never be started.) A message/timer start event counts
> too. So do **not** model "intake from two channels" as two start events: keep the single `<startEvent>` and
> realise the alternate trigger as a **scheduler** ([12](12-queries-sources-schedulers-and-rest.md)) or as a
> separate workflow, then branch inside the process on a channel field. `mrjun.py validate` ERRORs on >1
> `<startEvent>`.

The root of `bpmnContent` (the UI-modeler shape, `targetNamespace="http://bpmn.io/schema/bpmn"`):

```xml
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
             xmlns:flowable="http://flowable.org/bpmn"
             targetNamespace="http://bpmn.io/schema/bpmn">
```

Namespace rules (as the modeler itself writes them):
- **The process body is in the default namespace, WITHOUT the `bpmn:` prefix:** `<process>`, `<startEvent>`, `<endEvent>`,
  `<serviceTask>`, `<userTask>`, `<exclusiveGateway>`, `<sequenceFlow>`, `<conditionExpression>`.
- Only `flowable:` (extensions), `bpmndi:`/`dc:`/`di:` (diagram) carry a prefix.
- ⚠️ The `settings.type` value in `elements` is **still** `bpmn:StartEvent` etc. (with a prefix) —
  this is the JSON form of the enum, not the XML.
- MCP generation (`createMinimalBpmn`, `WorkflowMcpTools.java`) uses a **different** targetNamespace
  `http://www.flowable.org/processdef`. For UI compatibility stick with `http://bpmn.io/schema/bpmn`.

### Step 0. A minimal "empty" workflow

The simplest valid workflow — an "Empty Workflow": start → end.

```json
{
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<UUID-workflow>",
  "name": "My Workflow",
  "description": null,
  "processDefinitionId": null,
  "externalId": null,
  "deployed": false,
  "bpmnContent": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<definitions xmlns=\"http://www.omg.org/spec/BPMN/20100524/MODEL\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:bpmndi=\"http://www.omg.org/spec/BPMN/20100524/DI\" xmlns:dc=\"http://www.omg.org/spec/DD/20100524/DC\" xmlns:di=\"http://www.omg.org/spec/DD/20100524/DI\" targetNamespace=\"http://bpmn.io/schema/bpmn\">\n  <process id=\"Process_1\" isExecutable=\"true\">\n    <startEvent id=\"Event_start\"><outgoing>Flow_1</outgoing></startEvent>\n    <endEvent id=\"Event_end\"><incoming>Flow_1</incoming></endEvent>\n    <sequenceFlow id=\"Flow_1\" sourceRef=\"Event_start\" targetRef=\"Event_end\" />\n  </process>\n  <bpmndi:BPMNDiagram id=\"BPMNDiagram_1\"><bpmndi:BPMNPlane id=\"BPMNPlane_1\" bpmnElement=\"Process_1\"><bpmndi:BPMNShape id=\"Event_start_di\" bpmnElement=\"Event_start\"><dc:Bounds x=\"212\" y=\"342\" width=\"36\" height=\"36\" /></bpmndi:BPMNShape><bpmndi:BPMNShape id=\"Event_end_di\" bpmnElement=\"Event_end\"><dc:Bounds x=\"402\" y=\"342\" width=\"36\" height=\"36\" /></bpmndi:BPMNShape><bpmndi:BPMNEdge id=\"Flow_1_di\" bpmnElement=\"Flow_1\"><di:waypoint x=\"248\" y=\"360\" /><di:waypoint x=\"402\" y=\"360\" /></bpmndi:BPMNEdge></bpmndi:BPMNPlane></bpmndi:BPMNDiagram>\n</definitions>",
  "elements": [
    { "id": "Process_1", "settings": { "type": "bpmn:Process", "properties": [
      { "name": "isExecutable", "value": true, "order": 0 }, { "name": "id", "value": "Process_1", "order": 0 } ] } },
    { "id": "Event_start", "settings": { "type": "bpmn:StartEvent", "properties": [
      { "name": "id", "value": "Event_start", "order": 0 } ] } },
    { "id": "Event_end", "settings": { "type": "bpmn:Task", "properties": [
      { "name": "id", "value": "Event_end", "order": 0 } ] } },
    { "id": "Flow_1", "settings": { "type": "bpmn:SequenceFlow", "properties": [
      { "name": "id", "value": "Flow_1", "order": 0 },
      { "name": "sourceRef", "value": "Event_start", "order": 0 },
      { "name": "targetRef", "value": "Event_end", "order": 0 } ] } }
  ],
  "contextIdentifiers": ["<UUID-context>"]
}
```

Notes on the minimum:
- `deployed=false`, `processDefinitionId=null`, `externalId=null` — the engine will set them on the first deploy
  (the Deploy button in the editor). Don't invent these values by hand.
- `contextIdentifiers` — the UUIDs of the contexts that rules can read/write (see
  [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)); can be `null` if the workflow uses nothing
  from a context.
- `elements` can even be omitted/left empty (you will meet placeholder workflows carrying `bpmnContent:null` and
  `elements:[]`) — import will re-read the XML anyway. But a consistent set is useful for the UI, which reads
  node settings from `elements`. The order in the array is irrelevant (`Set`).

### Step 1. Add a Service Task that executes a Groovy rule

Into `<process>` insert (between start and end, re-routing the sequenceFlows):

```xml
<serviceTask id="Activity_svc1" name="Recalculate"
             flowable:delegateExpression="${ruleTask}"
             flowable:rule="<UUID-rule-1>,<UUID-rule-2>">
  <incoming>Flow_in</incoming>
  <outgoing>Flow_out</outgoing>
</serviceTask>
```

Don't forget to declare the namespace `xmlns:flowable="http://flowable.org/bpmn"` in `<definitions>` (in the
Service Center Workflow example it's there; in the minimal "Empty" it's not, since flowable attributes aren't used).
The corresponding `elements` node is as in the "Service Task" section above: `type:"bpmn:ServiceTask"` with
`delegateExpression`/`implementation`=`${ruleTask}`, `implementationType:"delegateExpression"`, `rule` (the same
CSV), `exclusive:true`, `async:false`. The rules must exist in `rep-objects.json.rules` (type
`EXECUTION_RULE` or `VALIDATION_RULE`), with `contextIdentifiers` that include the workflow's context(s)
(see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)). The delegate value is **strictly
`${ruleTask}`** (`$`, not `#`).

### Step 2. Add a User Task with two actions (Approve/Reject)

```xml
<userTask id="Activity_review" name="Technician review"
          flowable:userActions="{&#34;actions&#34;:[ ...escaped JSON... ],&#34;errors&#34;:[]}">
  <incoming>Flow_in</incoming>
  <outgoing>Flow_out</outgoing>
</userTask>
```

where `flowable:userActions` is `UserTaskActionsDto.toJson()` with **all `"` escaped as `&#34;`**
(in the `rep-objects.json` JSON — as `\"`). A minimal `ActionDto`:

```json
{ "id": "<UUID-action>",
  "localizedNames": { "en_US": "Approve" },
  "localizedButtonNames": { "en_US": "Approve" },
  "predicateIdentifier": "<UUID-predicate-or-null>",
  "onBeforeUserTaskStartRuleIdentifier": null,
  "onBeforeUserTaskCompleteRuleIdentifier": "<UUID-exec-rule-or-null>",
  "validationRuleIdentifiers": null,
  "direct": "off",
  "formGroupIdentifier": "<UUID-formGroup-or-null>",
  "taskId": null,
  "completeUserTask": "on",
  "icon": "pe-7s-check",
  "submitForm": null }
```

Choosing `direct`:
- `direct:"on"` — the button immediately runs `onBeforeUserTaskCompleteRuleIdentifier` and (if `completeUserTask:"on"`)
  completes the task, WITHOUT a form. `formGroupIdentifier` may be `null`. (Example: the quick action "Unlock document",
  "Save draft" with `completeUserTask:"off"`.)
- `direct:"off"` — the button opens `formGroupIdentifier` (the form group, see
  [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md)); on submit (`submitForm≠false`)
  validations (`validationRuleIdentifiers`) + persist + complete-rule + task completion run.

The corresponding `elements` node: `type:"bpmn:UserTask"`, properties `id`/`name`/`exclusive:true`/`async:false`/
`candidateUsers:""`/`candidateGroups:""` and `userActions` = **the same JSON string** (in `elements` it's in `value`
as a plain string with `\"`, without `&#34;`; `&#34;` is only inside the XML attribute).

### Step 3. Add an Exclusive Gateway with conditional branching

```xml
<exclusiveGateway id="Gateway_1" name="Approved?" default="Flow_no">
  <incoming>Flow_in</incoming><outgoing>Flow_yes</outgoing><outgoing>Flow_no</outgoing>
</exclusiveGateway>
<sequenceFlow id="Flow_yes" name="Yes" sourceRef="Gateway_1" targetRef="Activity_a">
  <conditionExpression xsi:type="tFormalExpression">${predicateSequence.execute(execution, '<UUID-predicate>')}</conditionExpression>
</sequenceFlow>
<sequenceFlow id="Flow_no" name="No" sourceRef="Gateway_1" targetRef="Activity_b" />
```

In `elements`: a `bpmn:ExclusiveGateway` node (only `id`/optional `name` — **`default` lives in the XML only**) +
one `bpmn:SequenceFlow` node per branch, the conditional one carrying `conditionExpression` = exactly the same
string `${predicateSequence.execute(execution, '<UUID-predicate>')}`. The predicates are rules of type `PREDICATE`
in `rep-objects.json.rules`.

Three things make this an `if/else` instead of a coin toss, and all three are easy to leave out (§4):
**(1)** exactly ONE branch is unconditional — that is the `else`; give a second outcome its own predicate, never a
second bare flow. **(2)** the gateway's `default` names that unconditional branch, so it is taken only when every
predicate returned `false`, whatever order the flows are in — without it, routing depends on document order, and if
every branch IS conditional the process throws `No outgoing sequence flow ... could be selected` and STICKS.
**(3)** every branch has a `name`: the fallback's settings panel is empty by design, so the label and the canvas's
default-flow slash marker are the only things that tell a reader which arrow is which.

### Step 4. Mount the pages (optional)

For the workflow to be reachable in the UI, the section's admin pages must already be in `branches.json` (in an empty project
they are there by default — `siteMapPage` nodes with `workflows.plugin`, `bpmn2modeler.plugin`, `processes.plugin`,
`processes.selectedplugin`, `process.table.pluin`). Usually nothing needs to be added: the workflow appears in the
`workflows.plugin` list simply by being present in `rep-objects.json.workflows`. Process groups —
`rep-objects.json.processGroups` (in an empty project there are already two, with fixed `identifier`s).

> **⚠️ Repoint the 2 seeded `process.table.pluin` nodes.** `empty/branches.json` ships **two** "Process Table"
> nodes whose `properties.model.stringValue` carries **dangling** references (verified by `jq` over
> `empty/`): `workflowIdentifier` `6c0b4335-...` and `4009ac6c-...` (empty has **0 workflows**),
> `contextIdentifier` `fe5e9b03-...` (empty has **0 contexts**), plus `userStartProcessActions`
> `formGroupIdentifier`/`predicateIdentifier` UUIDs that also don't exist here. Their `processGroupIdentifier`s
> (`32d9be5f-...`, `b0c1f90e-...`) DO resolve (those are the two seeded groups). So when you add a workflow:
> **repoint each node's `model` `workflowIdentifier`/`contextIdentifier`/action-UUIDs at your real objects,
> or delete the nodes** — don't ship the placeholders. Full `model` field walkthrough (7 keys, `filterExpression`
> DSL, recipes) lives in [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md).

### Step 5 — the worklist page (NOT optional)

Step 4 mounts the *authoring* pages. This step mounts the page the **work** happens on, and it is not optional:
a workflow nobody can open is a workflow nobody runs.

> ⛔ **THE INVARIANT: every workflow in `rep-objects.json.workflows[]` gets EXACTLY ONE worklist page.** Never
> zero — a workflow reachable only from the author console (`processes.plugin`) is one no end user ever runs.
> One page is **THE** queue for that workflow; deliberate per-group filtered views of the same workflow are a
> separate, later decision (§`ProcessGroupDto`), not a substitute for it. The page is, in full:
> 1. a **dedicated `siteMapPage` with its own `alias`** — a real page, not a tab, not a panel bolted onto
>    someone else's page;
> 2. whose content parsis holds **exactly ONE `process.table.pluin`** whose model `workflowIdentifier` is this
>    workflow's `identifier`, with a **`dynaform.filter.form.plugin` sibling BEFORE it** in the same parsis —
>    the standing rule for every table page ([19](19-build-decision-procedure.md) Phase 9), and the only thing
>    that makes a `filterExpression` do anything at all (model shape, placement inside `html "Layout" →
>    nct.parsis.plugin "parsis"`, the `indexSettings`/`filterExpression` DSL and the filter-form recipe:
>    [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) Part 2);
> 3. plus the **`rep-objects.json.settings[]` mirror** row for that node (`type:"ProcessTable"`,
>    `name == node.uniqueIdentifier`, `content` = the SAME model as an object). Without it the table still
>    draws, but every NON-direct action opens a form with no crud metadata — it fills, submits and writes
>    nothing ([05](05-crud-tree-and-process-table.md) §Export shape);
> 4. plus a **left-nav quick link** to that page ([17-left-nav-quick-links.md](17-left-nav-quick-links.md)).

`node add` does **not** write the mirror — `node set-model` does — so set the model in a second step:

```
python3 tools/mrjun.py page add   --parent root --name "<Process> queue" --alias <process>-queue --auth --project ./app
python3 tools/mrjun.py node add   --parent "<Process> queue" --plugin dynaform.filter.form.plugin --name "<Process> filter" --project ./app
#   ^ then hand-author its filter.parsis subtree + filterKeys ([05] Part 2) — one command cannot build it
python3 tools/mrjun.py node add   --parent "<Process> queue" --plugin process.table.pluin --name "Process Table" --project ./app
python3 tools/mrjun.py node set-model <node-identifier> --json @worklist-model.json --project ./app   # ← also syncs settings[]
python3 tools/mrjun.py quicklink add --page "<Process> queue" --group "Pages" --label "<Process> queue" --project ./app
```

**A worklist nested as a secondary TAB does not count.** Two independent reasons:
- **Nobody finds it.** A quick link addresses a page: `linkModel.identifier` is the target **`siteMapPage`**'s
  identifier ([17](17-left-nav-quick-links.md) §`linkModel`), and there is no addressing scheme for "page X,
  third tab". The only route in is a person who already knows to open another page and then click across —
  which is precisely the person who does not need the queue.
- **The unlinked-page check is blind to it.** `validate`'s reachability warning walks `siteMapPage` nodes only
  (`_check_homepage_and_nav`, `tools/mrjunkit/validate_cmds.py:490-504`), so a `process.table.pluin` buried in a
  `nct.tab.plugin` of an already-linked host page produces **no warning at all** — and the one-table-per-page
  rule explicitly *permits* it, because separate tabs are that rule's only exception
  (`_check_one_table_plugin_per_page`, same file, `:1245`). "validate is clean" therefore says nothing here.
  Tabs are for a secondary view of the same work; the primary queue of a workflow is never one.

**Name the page and the link after the WORK, not after the engine.** `"<Process> queue"`, `"<Entity> cases"`,
`"<Entity> requests"` — the words a user of the case would say. Never `Processes`, `Workflows`, `Process Table`,
`BPMN`, `Monitor`: those name the platform's own admin pages from Step 4 (`processes.plugin`,
`processes.selectedplugin`, `workflows.plugin`, `bpmn2modeler.plugin`), which stay where they are, for the
author. And put the link in the **same nav group as the entity pages the workflow drives** (in a default
baseline that group is literally `Pages`, [17](17-left-nav-quick-links.md)) — somebody who opens `<Entity>` to
look at a record expects the queue that moves those records one heading away, not in a separate "Admin"
section. If this queue is the case's front door, it also gets the Home `Redirect`
([21](21-homepage-and-redirect.md) §"Choosing the front door — chart dashboard or main worklist").

#### Then prove it is not empty for anyone but you

A worklist that renders rows for its author and nothing for everyone else is the failure this rule exists to
prevent — and it is silent (no error, no log line the author sees). Three verified causes:

| Cause | Mechanism (verified in source) | Fix |
|---|---|---|
| **Process-group scoping** | The plugin puts `processGroupIdentifier` into the `ProcessFilter` **only if the group resolves** (`processGroupService.existsByIdentifier`, `initPluginContent`, `ProcessTablePlugin.java`), and the backend then requires equality on the joined group (`findAllProcesses`, `FlowableProcessServiceImpl.java`, nct-workflow). If the identifier is blank or dangling, the plugin **creates a brand-new group named after the node's `uniqueIdentifier` and rewrites the node's model** (`showProcessGroupSelectionDialog`, `ProcessTablePlugin.java`) — everything started under the previous group silently drops out, permanently. Two nodes over one workflow with two different groups likewise each show only their own rows. | ONE group per workflow, declared in `rep-objects.json.processGroups[]`, with the SAME `processGroupIdentifier` in the node model **and** in the mirror. Never ship a placeholder/dangling group id (Step 4). |
| **Missing `columnSettings`** | `columnSettings` (null → `[]`) drives one `<th>` (`columnHeaders`) and one `<td>` (`columns`) each (`ProcessTablePlugin.java`). With `[]` the table still lists a row per process, but every row is just the Actions dropdown under no headers — which every reader reports as "the page is empty". A `scope:"CRUD"`/`"CONTEXT"` column additionally needs the process's context data (bulk-prefetched via `getContextDataBulk` in the data provider); a `contextIdentifier`/`crudAlias`/`fieldExpression` that doesn't match what the workflow actually writes yields blank cells. | Author ≥3 columns that identify the case to a human (who / what / when / state) and confirm at least one non-blank cell after the first real run. `validate` catches only the coarser version: a `workflowIdentifier` absent from `rep.workflows[]` (`validate_cmds.py::_check_process_table_workflow_exists`). |
| **Per-process access rows** | `findAllProcesses` **INNER-JOINs** `accesses` and demands `access == true` plus one of USER == caller email / ROLE ∈ caller roles / ROLE_GROUP ∈ caller role groups (`FlowableProcessServiceImpl.java`, nct-workflow — the same block repeats on the `filterExpression` path). A form-started process writes exactly **one** access row — the starter, `type=USER`, `isOwner=true` (`startProcess`, same file) — and nothing in an export grants any other. The UI calls this with the **logged-in user's** token (`FeignClientInterceptor` forwards it for every non-`/internal/` URL), so a colleague who did not start the case matches no row: empty queue. | Grant on the start path: an `EXECUTION_RULE` on the workflow's first service task calls `service.access.addRoleGroupAccess("<Role Group>")` (or `addRoleAccess` / `addUserAccess`, [16](16-groovy-service-api.md) §2.7). `RuleTask` diffs `contextData.access` before/after and persists it via `processAccessService.updateAccesses` (`RuleTask.java`; the predicate path does the same, `PredicateSequenceFlowExecutor.java`). |
| **A rule-started process has no BUSINESS starter** | A process started by `service.workflow.start(...)` (shape C) is owned by whoever the rule is running as — for a scheduler tick, the schedule's `serviceUserEmail`, which travels through both hops of the pipeline. It is **not ownerless on a stock deployment**: when that is blank too, the platform falls back to **the project's configured author account** and writes ONE USER row for it (`isOwner=true`), alongside the `admin` and `nct_author` ROLE rows every programmatic start grants unconditionally (`startProcess` / `grantProgrammaticStartAccess`, `FlowableProcessServiceImpl.java`, nct-workflow). ⚠️ That fallback is a **configuration value whose in-code default is EMPTY** — a deployment that blanks it disables the fallback (the field's own javadoc: *"Blank disables the fallback and leaves the process ownerless"*), so the case gets no owner USER row and no `owner` process variable, and is reachable only by admins and authors. You cannot see that from the export, which is the reason to pass an owner rather than inherit one. So the failure is not "no access rows" but "no BUSINESS user on the case" — and that owner is also the identity a service task of the case executes as **until the first user task is completed** — after that, `RuleTask` uses the last completed user task's assignee and falls back to `owner` only when there is none (`RuleTask.java`). | Pass `owner`, `roleGroups` or `emails` in the call's options ([16](16-groovy-service-api.md) §2.12) — they are written in the same transaction as the process, so there is no window in which the case is invisible. The first-service-task grant works too, but only from the moment that task runs. Recipe: [27](27-event-driven-process-start.md) §6. |
| **A rule-started process has no process group** | Same call, different column: the group comes from the starting NODE, and a rule is not a node. With no `groupIdentifier` the process is created with `group=null`, and the group filter above is an INNER join — so a group-scoped worklist excludes it for everyone, admins included, with nothing logged. | Pass `groupIdentifier` in the options, with the SAME identifier the `process.table` node uses. |

> ⚠️ **`updateAccesses` deletes every access row of the process and recreates the submitted list**
> (`deleteAllByProcessId` then re-save, `ProcessAccessServiceImpl.java`). That is safe only because
> `contextData.access` was hydrated from the DB rows first (`getContextDataDto` →
> `processAccessService.getProcessAccess`, `WorkflowExecutionService.java`), which makes an `add*` call
> additive. A rule that assembles a fresh `AccessDto` — or calls `clearAllAccess()` — wipes the owner row too,
> and the case vanishes for its own starter.

> ⛔ **Don't mistake this for per-user scoping.** It is a grant written per process instance, not a fetch rule
> you can author, and nct-ui caches `findAllProcesses` per `(realm, client, filter)` with **no user in the key**
> (`@Cacheable` on `nct-ui/.../service/FlowableProcessServiceImpl.java`) — so one browser session proves
> nothing about what a second user sees, and you may be looking at their cached page.
> [05](05-crud-tree-and-process-table.md) is
> right that a process table **cannot** be scoped per user (use a `crud.table.plugin` with a scoped fetch rule
> for "each `<actor>` sees only their own"); treat the access join purely as a failure mode to clear.

> ⚠️ **Not machine-checkable in the direction that matters.** `validate` warns node→workflow (a process table
> bound to a workflow that isn't in the project, `validate_cmds.py::_check_process_table_workflow_exists`) and page→nav (an unlinked
> business page, `:490-504`), but **nothing warns workflow→page**: a workflow with no worklist page passes
> clean. So make it a review step — for each entry in `rep-objects.json.workflows[]`, find the
> `process.table.pluin` whose model `workflowIdentifier` equals it, confirm that node's page is a `siteMapPage`
> with an alias, and confirm a quick link points at that page.

### Modifying an existing / deployed workflow

When you MODIFY a filled `.mrjun` that already carries a workflow (scenario C in
[19-build-decision-procedure.md](19-build-decision-procedure.md)), edit the **XML in `bpmnContent`** — it is the
source of truth. To add/remove a step: insert or delete the `<serviceTask>`/`<userTask>`/`<exclusiveGateway>`
element(s), **re-route the `sequenceFlow`s** so `sourceRef`/`targetRef` (and the `<incoming>`/`<outgoing>` on
each node) still form one connected start→…→end path, and update `elements[]` to match — **or just leave
`elements` alone**, since import re-reads the XML and rebuilds the nodes anyway (`extractWorkflowElements`,
`FlowableWorkflowServiceImpl.java`). Keep the workflow's `identifier` **stable** (it is the identity key;
changing it makes a new workflow and orphans any `process.table.pluin` `workflowIdentifier` pointing at it).

**Deploy fields on re-import — you can't fake "already deployed".** Import saves every workflow through
`saveWorkflow → saveAndDeploy(dto, deploy=false)` (`FlowableWorkflowServiceImpl.java`, both the UI and the
`/internal/.../save` backend path via `saveWorkflowBackend`, `FlowableWorkflowController.java`). The
`deploy=false` branch **hard-clears** `externalId`, `processDefinitionId`, `processDefinitionKey` to `null` and
sets `deployed=false` — regardless of what your JSON said. So an imported workflow always lands as
an **un-deployed draft**; the engine assigns real deploy ids (`processDefinitionId = "Process_1:6:<uuid>"` — the
middle integer, `6`, is the Flowable **deployment version**, which the engine bumps on each re-Deploy; `externalId =
<deploymentId>`) only when someone clicks **Deploy** — either in the BPMN editor, or on the row's Deploy
button in the workflows list (`workflows.plugin`). Practical rule when
building/modifying by hand: set `deployed:false`, `processDefinitionId:null`, `externalId:null` (matches what
import forces anyway — an exported `deployed=true` is
purely informational and re-imports as a draft) and **remember to re-deploy in the UI** after import — the
workflows list shows every one of them as **Not deployed** until you do. Never
invent `Process_1:6:<uuid>`/deployment-id values.

### Process runtime context (for reference when writing rules)

Variables flow through the process: `contextData` (a serialized `ContextDataDto`,
key `ContextDataDto.CONTEXT_DATA_VARIABLE_KEY`, `RuleTask.java`) — progressively enriched at each step;
`userId`/owner; `userActionId` (which user-task action was chosen). Rules read/write `contextData`
via `context.<ctx>.data.getAttr/setAttr(...)`, `context.<ctx>.<alias>.data.get()/put(...)` (see
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)). The real enum statuses (don't invent
RUNNING/SUSPENDED/DRAFT/PUBLISHED/ARCHIVED from old docs):
- `ProcessStatus` (`ProcessStatus.java`): **`NEW, STARTED, CANCELED, DELETED, COMPLETED`** (US spelling
  `CANCELED`).
- `WorkflowStatus` (`WorkflowStatus.java`): **`ACTIVE, DELETED`** — and this field is not on the exported DTO
  anyway.

---

## What a process can see — the binding contract (read before wiring ANY workflow)

This is the single most expensive thing to get wrong, because **every offline gate stays green and the
project imports cleanly**. The symptoms show up only on a live run, and they look like unrelated bugs:
blank forms, `No <entity> selected` from a rule, a gateway that always takes the same branch, a worklist
whose columns are all empty.

### The one fact everything follows from

**A process never loads a CRUD row by itself.** A CRUD row reaches a form through
`FormPlugin.initCrudMode()`, which only runs when `resolveSettingsNavigation()` produced `crudTableNavData`
— i.e. when the launching action was found in a **crud-table** settings object. A workflow user-task action
lives in the workflow definition, and a process-table global action lives in `globalActions`; neither is a
crud-table action, so `crudTableNavData` stays null, `initCrudMode()` returns immediately, and no `crudId`
is ever resolved. The form is handed `workflowExecutionService.getContextData(processIdentifier)` and
nothing else.

So, from inside a process:

| Channel | Works? | Why |
|---|---|---|
| `contextData.attrs` (GLOBAL scope) | **yes** | serialized into the process variable and merged on every hop (`ContextDataMergeUtil`) |
| `crudDataMap[alias]` **written by the current form** | **yes** | `collectContextDataFromForm` writes CRUD-scoped control VALUES there even with no row bound — which is why CREATE works inside a workflow. Only controls the user FILLED: a null value returns early, so an untouched control seeds nothing |
| `crudDataMap[alias]` **that a rule explicitly `put` earlier** | **yes, as a SNAPSHOT** | only if the map already had an entry for that context — see the three start shapes below |
| the same map when **nothing put anything** | **no** | there is no automatic load; the fields render blank |
| `attrs._crudEntityId` | **no** | set by crud-table navigation only |

### The three start shapes — pick one deliberately

Two of them are start FORMS (A, B); the third is a RULE (C) and has no form at all — recipe in
[27](27-event-driven-process-start.md). A workflow has exactly ONE starter, so this is a choice, not a menu
to combine.

**Shape A — the intake CREATES the subject.** The start form's fields are `scope: CRUD` over the entity, so
`collectContextDataFromForm` creates `crudDataMap["<alias>"]`, and that map flows into the process. The
first service task does `…data.put(…service.create(…data.get()))`, and from then on
`context.<ctx>.<alias>.data.get()` returns the row on every later step. This is the shape the serviceTask
TRAP above documents, and it is the right one when the process itself brings the record into existence.
⚠️ What the map holds is a **snapshot**: later writes go to the database, not to the map, so any step that
changes the record must `put` it back or the next form shows stale values.

**Shape B — the subject ALREADY EXISTS and is picked.** The start form is a picker; there is nothing to
create. Here the crud map is not just empty, it **cannot be created by a rule**: with no CRUD-scoped control
on the start form, `contextDataMap[<ctx>]` itself is absent, and `context.<ctx>` throws *"No context data
available for context"* before you can reach `.data.put(...)` (`DynamicRuleContext.groovy`;
`enhanceContextDataWithCrudInfo` only fills a context entry that already exists). So in shape B **everything
runs on GLOBAL attributes** — the rest of this section is shape B, and it is the shape most "act on an
existing record" processes need.

Do not blend them: a shape-B start form with a decorative CRUD field bolted on just to conjure the map is a
phantom input the user must not touch, and it buys a snapshot that goes stale anyway.

**Shape C — a RULE starts the process, with no form at all.** `service.workflow.start("<workflowIdentifier>",
ctxMap[, opts])` from an EXECUTION rule or a CRUD GROOVY method ([16](16-groovy-service-api.md) §2.12). The
initial context data is whatever the rule passes, so unlike shape B it CAN carry a populated
`contextDataMap` — the restriction above is about what a start FORM produces, not about what the engine accepts.
This is the shape for "when X happens, open a case": a scheduler sweep, a threshold crossed in a service task, a
row created through a CRUD method.

> **The end-to-end recipe is [27](27-event-driven-process-start.md).** This section is the reference for what
> the shape IS; 27 is how to build one — recognising it from a PRD sentence that never mentions a form, picking
> among the three headless triggers, the order the objects must exist in, the rule that gathers rows from
> business logic and shapes them into the context data document, and the idempotency guard without which a
> scheduler opens a fresh case for the same row on every tick, forever.

Four things are specific to shape C and easy to get wrong:
* **Pass `groupIdentifier`.** A form-started case gets its process group from the node that started it; a
  rule-started one has no node, so with no `groupIdentifier` it is filed under NO group — and a `process.table`
  scoped to a group (the arrangement this doc prescribes) then excludes it from every worklist, silently.
* **Visibility is yours to arrange — and "never ownerless" is one config value away from false.** There is no
  submitting user; `owner` defaults to the user the rule runs as, and for a scheduler tick that is the
  schedule's `serviceUserEmail`. When even that is blank the platform falls back to **the project's configured
  author account** as owner, with its own `isOwner` USER row and its `owner` process variable
  (`FlowableProcessServiceImpl.java`, nct-workflow); admin and author ROLE access is granted on every
  programmatic start whatever happens. But that fallback is a **configuration value whose in-code default is
  empty**, and the field's javadoc says so outright — *"Blank disables the fallback and leaves the process
  ownerless"* — so on a deployment that blanks it (and the recipient's deployment is not yours) there is no
  owner row and no `owner` variable at all:
  the case is visible only to admins and authors, and every service task of it runs with **no user**. Either
  way the risk is not "nobody sees it" but "**nobody who should work it sees it**" — and with the fallback on,
  that one account is also the identity a service task executes as until the first user task completes (after
  that the last assignee wins - `RuleTask.java`), so
  `service.security.user()` inside the case returns it, not the person the case is about. Pass `owner`,
  `roleGroups` or `emails` to put the case in front of the people who must act on it —
  see the per-process access table under *"Then prove it is not empty for anyone but you"* above, and
  [16](16-groovy-service-api.md) §2.7/§2.12, [27](27-event-driven-process-start.md) §6.
* **Nothing rolls back.** The rule is not transactional, so start the process after everything that can fail.
* **Provenance is recorded for you** — `startedByRuleName`, `startedByRuleIdentifier`, and for a CRUD method
  `startedByCrudAlias` + `startedByMethodName`, as GLOBAL attributes readable via `context.data.*`.

### Rule 1 — a form opened from a task or the process table is GLOBAL-scope, except when it creates (a form opened from a crud-table row action is NOT: it is force-bound to that table's CRUD)

* A user-task form that **creates** a record: CRUD-scoped inputs are correct. The controls fill the crud
  data map, and the action's before-complete rule does `<alias>.service.create(<alias>.data.get())`.
  Read-only computed fields on such a form are blank, exactly as on any create form — that is fine.
* A user-task form that **shows or decides on an existing** record, reached only from a task or the process table: in shape B **every field is `scope: GLOBAL`** reading an attribute a rule published. A CRUD-scoped read-only field renders blank — and that is not a styling problem, it is a form that tells the user nothing and asks them to approve it. (⚠️ The moment the SAME form group is also opened from a crud-table/tree action, that path re-binds every control to the table's CRUD whatever the persisted scope says — the persisted scope still decides the TASK path, so keep those fields `scope: GLOBAL` there and have the rule read attrs first, then the row: [02](02-form-controls-reference.md) §Where the value LANDS.)
  (In shape A the same field renders, from whatever the last `data.put` left in the map.)
* Consequence: a workflow cannot host a line-editing screen for an existing document. Put the editor on the
  entity's own CRUD page (where the table really does bind the row) and let the workflow step be the
  **decision**, over a read-only card that shows the numbers.

### Rule 2 — the process start form binds by `<crudAlias>Id`

The new instance's initial `contextData` **is the start form's `contextData`**
(`FormSubmissionServiceImpl.startWorkflowProcess` serializes it into `CONTEXT_DATA_VARIABLE_KEY`). So the
subject has to travel in a **control's own value**:

> the start form carries a `scope: GLOBAL` picker whose **`fieldExpression` is exactly `<crudAlias>Id`**
> (crud alias `loanApplication` → `loanApplicationId`; `incomingDocument` → `incomingDocumentId`),
> populated by a choices rule.

Then every downstream rule resolves it with the standard `context.data.getAttr('<alias>Id')` fallback and
nothing else has to be wired. **Do not rely on the start action's before-complete rule to `setAttr` the
binding**: that rule runs against the FORM's context, and whether its result is carried into the new
instance depends on the platform build. Use the rule for *validation* ("is this subject still workable?"),
never for *binding*. `mrjun.py validate` reports a binding published only by a start rule.

### Rule 3 — publish every id you create, resolve every id you need

One resolver, pasted into every rule that acts on a record:

```groovy
def _rid = { alias ->
    def row = null
    try { row = context.<ctx>."${alias}".data.get() } catch (Throwable ignored) { }   // crud table row action
    def rid = (row instanceof Map) ? row.id : null
    if (rid == null) { rid = attrs?.get('_crudEntityId')?.asText() }                  // form submit
    if (rid == null) { rid = context.data.getAttr(alias + 'Id') }                     // process variable
    if (rid == null) { return null }
    context.data.setAttr(alias + 'Id', rid.toString())    // <- publish, so the NEXT step can resolve it
    return rid.toString()
}
```

and, in every rule that **creates** a record the workflow will act on later:

```groovy
context.data.setAttr("<alias>Id", newId)
```

`data.get()` throws when nothing was filed, so it is always inside `try/catch` — and so is the `.data`
property access itself, which throws separately when the context has no entry for that crud at all.

### Rule 4 — a gateway predicate must resolve like a rule

A predicate written as "read the filed row, return `row.status == 'X'`" is not wrong on a crud table — it
is wrong inside a process in one of two ways, and which one depends on whether anything seeded that alias into
the case: nothing seeded, it is **always false**; the alias seeded, it is **always the value the record had when
the case opened** (the box below). Neither is ever an error: the token silently takes one exit. Every conditional branch collapses to one path and nobody sees a stack
trace. So a gateway predicate resolves the id and **reads the record**:

```groovy
def _id = _rid('<alias>')
def row = (_id == null) ? null : service.crud.<alias>.get(_id)
if (row == null || row.id == null) { return false }
return (row.status == 'X')
```

> **⛔ Do NOT add the crud-table "fast path" here** — the shape that reads `context.<ctx>.<alias>.data.get()`
> first and only falls back to a real read when nothing useful is filed. It is correct and cheap on a table,
> where the filed row IS the row on screen. On a gateway it is a decision made on a **stale copy**:
> `context.<ctx>.<alias>.data` inside a case is `contextDataMap`, kept in a PROCESS VARIABLE, and **nothing
> refreshes it** when a rule or a form writes the row — the engine hands the predicate whatever was last
> written there. Which behaviour you get is then decided somewhere else entirely: if nothing seeded that
> alias the map is absent, the fallback runs and the predicate is right; but **a case with no start form has
> to seed it** (the starting document is its only channel for publishing its subject — §"a rule starts a
> process"), and then the fast path answers from the copy taken when the case opened. The field is frozen at
> its opening value, the predicate returns the same answer for the life of the case, **one branch is taken
> for ever and the other is unreachable code that still reads as a decision on the diagram**. Nothing in the
> BPMN shows it: the branch, its predicate, its label and the `default` are all exactly right. Using the
> snapshot for the **id** is fine (ids do not go stale) — that is what `_rid` does. `validate`
> (`_check_gateway_predicate_reads_record`) WARNs when a gateway predicate's answer can come from it.

`service.crud` **is** available in a PREDICATE (`GroovyPredicate` compiles with the same
`ExecutionRuleTemplate.groovy` and gets `setCrud(...)`); `service.notification` / `service.report` are not.

### Rule 5 — the display attributes come from a SERVICE TASK

Only a service task's context result is written back to the process
(`RuleTask` → `saveContextDataToProcessVariables`). So the pattern for "the user task must show the
record" is:

1. the first service task after the start event runs a **bind** rule: it resolves `<alias>Id`, re-publishes
   it under every name later steps use, and copies the record's human-readable fields into GLOBAL
   attributes with a stable prefix (`caseX…`, `applicationX…`);
2. each later service task that produces a new record publishes **its** id and **its** display attributes
   the same way;
3. one read-only GLOBAL card form is opened by every step that needs to show the case. It fills up as the
   case advances; a blank block downstream simply means the case has not reached that stage yet.

⚠️ **Refresh what you publish.** An attribute is a copy, not a view. A step that changes the record's
status must re-publish it (`context.data.setAttr('caseStatus', 'POSTPONED')`) or the card and the worklist
keep showing the value the bind rule read. The same trap as shape A's snapshot, one level up.

### Rule 6 — process-table columns are GLOBAL

`ProcessTablePlugin.extractColumnValue` resolves **all three** scopes against the process's stored
context-data document: `GLOBAL` from its root `attrs` — past five names intercepted first and taken off the
process row itself (`businessKey`, `workflowName`, `status`, `identifier`, `id`) — `CONTEXT` from
`contextDataMap[ctx].attrs`, `CRUD` from `contextDataMap[ctx].crudDataMap[alias]` → `value`. So a CRUD-scoped
column (or `indexSettings` entry) is blank **only when nothing seeded that alias** — which is precisely the
shape-B case this section is about, since a picker start form creates no `contextDataMap` entry at all. Shape
A seeds it from the form's own CRUD-scoped controls, and a shape-C rule seeds it from the document it passes
([27](27-event-driven-process-start.md) §6, [05](05-crud-tree-and-process-table.md)).

Author the columns GLOBAL anyway, for a reason that holds in all three shapes: what the CRUD branch reads is
the document's **snapshot** of the row, and the plugin never reads the table — so the first service task that
updates the record leaves the column showing the value the start put there. Only the GLOBAL attributes the
bind rule re-publishes (Rule 5) stay true. Same for `indexSettings`, which feed `filterExpression`.

> Note on the index: `paramsToFilter` is refreshed when the process starts and after each action
> execution, from the context available at that moment. A brand-new instance may therefore be filterable
> only after its first action — the columns are always live, the filter catches up.

### The checklist (and the gate)

Before shipping any workflow:

- [ ] the start form's picker is `scope: GLOBAL`, `fieldExpression == "<crudAlias>Id"`;
- [ ] no form group reached ONLY from a user task / global action shows CRUD-scoped read-only fields, unless that action creates (a group also opened from a crud-table action keeps those fields GLOBAL too — the persisted scope decides only the task path; the table path forces CRUD whatever you wrote);
- [ ] every workflow-reachable rule resolves the *id* through `_rid` — whose last leg IS `context.data.getAttr('<alias>Id')` — never through the crud context alone; and if the same rule is also wired to a crud-table/crud-tree action, it reads the form's *values* **attrs first, then the row** (`context.<ctx>.<alias>.data.get()`) — on the task path the attrs hold what the user typed, on the table path the attrs are empty and the row IS the typed value (the `FORM` helper, [08](08-groovy-rules-and-context.md));
- [ ] every id a rule creates is `setAttr`-published;
- [ ] every gateway predicate reads the record back from the database;
- [ ] every process-table column/index is `scope: GLOBAL`;
- [ ] no global action on the process table opens a CRUD form group (it has no row — see
      [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)).

`python3 mrjun.py validate` checks most of this mechanically (`_check_process_context_binding`) and names
the rule, the form group and the column; the dual-wired read is `_check_crud_action_form_values`, which ERRORs
on a literal `getAttr("<field>")` but by design cannot see a read done through a variable — the
attrs-first-then-row shape stays yours to get right. Treat every one of its findings as a blocker: each corresponds to
a screen that is blank or a step that throws on the first live run.

---

## Gotchas

1. **`bpmnContent` is the source of truth; `elements` is derived.** The server re-reads the XML on every save/deploy
   (`extractWorkflowElements`, `FlowableWorkflowServiceImpl.java`). If you edit by hand — edit the XML and
   keep `elements` in agreement; on a mismatch the XML wins.
2. **`elements` and `properties` are a `Set` (HashSet).** The order is nondeterministic (doesn't match the XML — that's
   normal), and properties with the same `name` collapse (`@EqualsAndHashCode` by `name`+`order`,
   `ElementSettingDto.java`). Don't duplicate nodes by `id` or properties by `name`.
3. **`endEvent` in the XML becomes `bpmn:Task` in `elements`**. Don't be alarmed and don't "fix" it —
   there is no separate `BpmnTaskType` for the end event (`BPMN_END` doesn't exist).
4. **`addProperty` skips null.** A missing property (`name`, `rule`, `assignee`, `documentation`) in
   `elements` is normal, not an error (guard). Don't add `{"name":"rule","value":null}`.
5. **`userActions` — double escaping.** Inside `elements[].properties.value` it's a string with `\"`; inside
   the XML attribute `flowable:userActions` the same quotes are `&#34;`. Easy to mix up the levels.
6. **`rule` in a service task is a CSV.** Multiple rules = `"uuid1,uuid2"`; `RuleTask` splits on the comma
   (`RuleTask.java`) and executes them in order, sharing one `contextData`. The order in the string = the execution
   order.
7. **The only supported `delegateExpression` is `${ruleTask}`** (dollar-brace, not `#{...}`),
   the only `sequence` is `${predicateSequence.execute(execution, '%s')}`. Both come from registered
   beans (`RimmController.java`); there are no other values in the dropdowns. Don't invent arbitrary
   delegates.
8. **`conditionExpression` vs `flowable:sequence`/`flowable:rule`.** The UI writes into the XML of a conditional transition BOTH
   `<conditionExpression>` (what Flowable actually executes) AND the duplicate attributes
   `flowable:sequence="...'%s'"` + `flowable:rule="<uuid>"` (see the `Flow_0ffbm4d` example). Into `elements`
   only `conditionExpression` is extracted. For execution `conditionExpression` alone is enough; the duplicates are
   for re-rendering in the editor. **Don't confuse** the UI form `${predicateSequence.execute(...)}` with the MCP form
   `${predicateResult}` (`WorkflowMcpTools.java`) — different contracts.
9. **`deployed`/`processDefinitionId`/`externalId` are set by the engine.** When building by hand set
   `deployed:false` and the other two `null`. Their concrete values (`Process_1:6:<uuid>`, a deployment UUID)
   are generated by Flowable at deploy time and shouldn't be invented. The exported DTO has **no**
   `status`/`workflowStatus`/`latest`/`processDefinitionKey` — don't add them.
10. **`predicateIdentifier`/`formGroupIdentifier`/rule fields may be the string `"null"`** in legacy data;
    the `ActionDto` getters treat `"null"` as `null`. For new data put
    JSON `null`. Use `localizedNames`/`localizedButtonNames`, not legacy `name`.
11. **`processGroups` in an empty project already contains two default elements** with fixed `identifier`s
    (`b0c1f90e-...`, `32d9be5f-...`) and UUID placeholders in `name`/`description`. Don't duplicate them; for a new
    group add an element with a new `identifier` and meaningful `name`/`description`. Identity is carried by
    `identifier` (the exported `id` = null).
12. **The coordinates in `<bpmndi:*>` are irrelevant for EXECUTION** and may be negative (values like
    `x="-31658"` are common) — but they are **NOT irrelevant for the VIEWER**: the BPMN editor/monitor renders the stored
    `<bpmndi:*>` **as-is** (bpmn-js does not auto-layout an existing diagram). ⚠️ So a lazy DI (all nodes at the
    same/near coordinates, or straight 2-waypoint diagonal edges between different lanes) renders as an
    **unreadable pile of overlapping boxes and lines crossing through nodes** — a real complaint from users.
    **Author a proper layered layout:** one `<bpmndi:BPMNShape>` per node with **non-overlapping** `dc:Bounds`
    (rank = left-to-right column via longest-path, branches on separate vertical lanes, ~180px column / ~130px
    lane spacing; events 36×36, gateways 50×50, tasks ~110×70), and **orthogonal** edge waypoints. ⛔ **No edge
    may pass THROUGH a task/gateway box.** The routing rule that guarantees this: an **adjacent-rank** edge exits
    the source on its right and enters the target on its left with the vertical bend at the mid-x **inside the
    empty gap between the two columns** (never over a node); a **skip-rank** edge (target >1 column away) OR a
    **loop-back/back** edge is routed through a **clear channel BELOW every node**, and — critically — its
    vertical drop/rise segments sit at **x = column-center ± half-a-column (an inter-column GAP), NOT straight
    down the source column** (a straight drop hits any node sitting in a lower lane of the same column, e.g. a
    second gateway under the first). One shape per node + waypoints per transition is the bare minimum for it to
    draw at all; layout quality (no overlaps, no lines through boxes) is on you. `mrjun.py validate` now WARNs on
    overlapping node shapes and on any axis-aligned edge segment that crosses a non-endpoint node box.
12b. **Every node must be able to reach an end event, and every non-end node must have an outgoing
    `sequenceFlow`.** A user/service task whose only outgoing loops back (e.g. an `outreach` task that just
    returns to a gateway with no terminal branch) **traps the process forever** — the token can never complete.
    Give every loop a terminal exit (an action + a gateway branch to a service task → `endEvent`). `mrjun.py
    validate` now WARNs on a node that can't reach an end or has no outgoing flow.
12c. **A branch out of a decision needs THREE things, and the editor shows you only one of them.** The condition
    is what the engine routes on; the gateway's `default` is what makes the fallback an `else` instead of an
    order-dependent coin toss; the `name` is the only thing a reviewer can read. The settings panels show
    neither of the last two — an empty `sequence` dropdown for the fallback and no `default` control anywhere
    (`default` shows only as a plain attribute row on the GATEWAY; set it from the canvas wrench/replace
    menu — **Default flow**) — so both
    are the author's job and nothing in the property sheets will remind you. On the canvas the fallback is
    marked with the standard default-flow **slash** across the start of the arrow: no slash means no `default`.
    Label a branch pair the way the question is asked (`Approved`/`Rejected`, `Yes`/`No`) and put the `name`
    between `id` and `sourceRef`, which is where both the editor and Flowable's serializer write it, so a
    round-trip is a no-op diff. If you also author `<bpmndi:BPMNLabel>` bounds for the branch (recommended — the
    viewer renders the stored diagram as-is), it must be the **LAST** child of its `<bpmndi:BPMNEdge>`, after the
    waypoints: the DI schema is `waypoint+` then an optional `BPMNLabel`, and the other order is well-formed XML
    that the XSD still rejects — which fails the workflow at import and **aborts the whole rep-objects import**
    with it. See §4. `mrjun.py validate` WARNs on the branching half (`_check_gateway_branching`) and
    **ERRORs** on the label-order half (`_check_workflow_xml`), because that one does not merely mis-route a
    case, it stops the whole import.
13. **Namespace trap:** the process body is WITHOUT the `bpmn:` prefix (default ns), while `settings.type` in `elements`
    is WITH the `bpmn:` prefix (the JSON form of the enum). Old docs that write `<bpmn:serviceTask>` in the XML are stale (S6).
14. **Timer/boundary/due-date/priority — not confirmed.** `BOUNDARY_EVENT` can be created, but only with
    `attachedToRef` (`WorkflowMcpTools.java`); there is no plumbing for `timerDuration`/`cancelActivity`/`dueDate`
    `priority` in the code or exports. Don't design around them.
15. **Non-creatable node types.** SendTask/ReceiveTask/ScriptTask/EventBasedGateway/ComplexGateway/ManualTask/
    BusinessRuleTask/TextAnnotation/Association/DataStoreReference are in the enum, but can be created neither in the UI nor
    MCP and have no runtime delegates — don't use them.
