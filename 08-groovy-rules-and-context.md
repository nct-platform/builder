# 08 — Groovy rules & the context model

> 📐 **Field evidence — what rules are actually written for:** [03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md) · [06-security-and-roles.md](references/06-security-and-roles.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / when to use

Almost all the project's dynamic logic is **Groovy rules** (`rules[]` in
`rep-objects.json`) executed by the `nct-executor` service. A rule is a short Groovy script
(`rule.ruleScriptStr`), wrapped in a template class and run with preconfigured bindings
(`context`, `service`, `param`, `validation`, `attrs`, `userId`, …). Three types:

| `ruleType` | `executor` | What it returns | Where it's used |
|---|---|---|---|
| `PREDICATE` | `GroovyPredicate` | `Boolean` (**mandatory** via `return`) | visibility/enabledness of action buttons, `prohibited`/`hidden`/`required`/`choices` predicates of form controls, form-mapping predicates of form groups, gateway routing in workflow |
| `EXECUTION_RULE` | `GroovyExecutionRule` | any value (or nothing) | fetch rules of CRUD tables, dropdown/autocomplete sources (**MUST end with `toSelectOptions*`/`toAutoCompleteOptions` — never a raw `find`/`findAll` list; see 02 §4a**), `init`/`create`/`delete`/before-start/before-complete action logic, event-mapping rules, service-task in workflow, **delegated Groovy methods of dynamic CRUDs** |
| `VALIDATION_RULE` | `GroovyValidationRule` | nothing (accumulates errors via `validation.*`) | form/field validation (`validators`, `actionValidators`), action `validationRule` |

All three types occur in a real project, and the mix is lopsided: `EXECUTION_RULE` dominates by roughly an
order of magnitude, `PREDICATE` comes second, `VALIDATION_RULE` is rare — but rare is not absent, so never
assume a type is unused before counting: `jq -r '.rules[].ruleType' rep-objects.json | sort | uniq -c`.
The rule syntax and rep-object shape are **identical** whether the CRUDs behind them are STATIC (compiled
`@Crud` beans, no `dynamic-cruds.json`) or dynamic — only the crud backing differs; see §"MODIFY-FILLED".

A rule "sees" project data through the **context model**: the `context` rep-object (`contexts[]`)
declares an `alias` (e.g. `finance_context`) and a list of `crudAliases`, and rules attach to it via
`contextIdentifiers[]`. Inside the script this yields the chained syntax
`context.<ctxAlias>.<crudAlias>.data.get()` (the current row). But the **most common** way to call
a CRUD method is the context-independent `service.crud.<crudAlias>.<method>(args)` (see §"service.crud").

> **🔧 Tooling.** For these entities, run [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `context add --name <s> --alias <s> --crud <a>...`, `context add-alias <ctx> <a>...`,
> `rule add --name <s> --type PREDICATE|EXECUTION_RULE|VALIDATION_RULE --context <ctx> --script @f`
> (executor and the missing-`return` warning are automatic), `rule rm`, `list rules/contexts`.
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.
>
> ⚠️ **`rule add` limitation:** `--context` is **mandatory**, and the command always writes exactly one
> attached context (`"contextIdentifiers": [<ctx>]`). It **cannot** produce the form
> `contextIdentifiers: []` recommended below for `service.crud`-only / role-check / `RIMM_*`
> dropdown sources. For such rules, edit `rep-objects.json` by hand per the recipe (Step 2), or
> extend the tool with a "no context" option. On an export that has no contexts yet (a fresh empty starter)
> `rule add` won't run at all — `resolve_context` will throw.

> Related documents: [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)
> (`methods[]` — SQL/Groovy, delegation), [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md)
> (autocomplete hints in the editor), [04-crud-table-plugin.md](04-crud-table-plugin.md) and
> [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) (who calls a rule and with what context),
> [02-form-controls-reference.md](02-form-controls-reference.md) (`ruleIdentifier`/`contextIdentifier`/`crudAlias`
> in form settings; also — the 51 **field validation templates**, see §"Field-based validation templates"),
> [07-workflows-and-tasks.md](07-workflows-and-tasks.md) (rules in service-task/gateway/user-task).
> ⚠️ Older platform documentation on rules, contexts and validation is **partly outdated**; where it disagrees
> with this document, the behaviour described here is what the executor actually does.

---

## Export shape — the `rule` rep-object

Rules live in `rep-objects.json` under the `rules` key (an array). Schema of one element:

```
{
  "message": null, "errors": null, "id": null,          // transient, ignored on import
  "realmName": "<realm>", "clientName": "<client>",       // tenant
  "identifier": "<uuid>",                                 // stable ID, referenced by settings/methods/actions
  "creationTime": "...", "modificationTime": "...",
  "name": "<human-readable name>",                        // service.rule("<name>") looks up BY NAME
  "description": "<desc; may carry an alias:... marker>",
  "status": "ACTIVE",                                     // ACTIVE | UNUSED | DELETED
  "ruleType": "PREDICATE|EXECUTION_RULE|VALIDATION_RULE",
  "executor": "GroovyPredicate|GroovyExecutionRule|GroovyValidationRule",
  "contextIdentifiers": ["<context uuid>", ...],          // which contexts are available as context.<alias>; often []
  "rule": { "ruleScriptStr": "<Groovy source>" },         // body; without the template wrapper
  "hidden": null                                          // null | true | false; true → hidden in the Rules list
}
```

Worked example (PREDICATE) — a generated "Required (not empty)" field predicate, as it sits in
`rep-objects.json`:

```json
{
  "realmName": "<realm>",
  "clientName": "<client>",
  "identifier": "7aafc8ad-dceb-431e-86d9-cc1a38ed22f7",
  "name": "finance_context · invoices_cruid · counterpartyName · Required (not empty)",
  "description": "alias:financeContextInvoicesCruidCounterpartyNameRequiredNotEmpty | Required (not empty) (generated from template)",
  "status": "ACTIVE",
  "ruleType": "PREDICATE",
  "executor": "GroovyPredicate",
  "contextIdentifiers": ["871f974f-e775-401a-adfc-e822110f3b99"],
  "rule": {
    "ruleScriptStr": "def v = context.finance_context.invoices_cruid.data.getField('counterpartyName', java.lang.String.class)\nreturn v == null || (v instanceof CharSequence && v.toString().trim().isEmpty()) || (v instanceof Collection && v.isEmpty()) || (v instanceof Map && v.isEmpty())"
  },
  "hidden": null
}
```

Worked example (EXECUTION, dropdown source) — **note `contextIdentifiers: []`**
(the generated naming convention for a dropdown source is `RIMM_<crudAlias>`):

```json
{
  "identifier": "…",
  "name": "RIMM_counterparties_cruid",
  "status": "ACTIVE",
  "ruleType": "EXECUTION_RULE",
  "executor": "GroovyExecutionRule",
  "contextIdentifiers": [],
  "rule": { "ruleScriptStr": "def list = service.crud.counterparties_cruid.find([\n  rowsInPage: 1000,\n  pageNumber: 0\n])\nreturn service.global.conversion.toSelectOptionsLocalized(list, \"id\", \"name\")" },
  "hidden": false
}
```

### Field-by-field (rule)

| Field | Type | Value / required | Default | Backing |
|---|---|---|---|---|
| `identifier` | String(uuid) | stable rule ID; **required** — referenced by the form's `settings.stringValue.ruleIdentifier`, the CRUD's `methods[].ruleIdentifier`, an action's `predicateIdentifier`/`onBeforeStartRuleIdentifier`/`onBeforeCompleteRuleIdentifier`. **Always a UUID**, not a slug | generated | `RuleDto.identifier` (`AbstractSecuredDto`) |
| `name` | String | required; `service.rule("<name>")` resolves **by name** (`findByName`) | — | `RuleDto.name` |
| `description` | String | opt.; auto-generated rules carry `alias:<camelCase> \| ... (generated from template)` | `null` | `RuleDto.description` |
| `status` | enum | `ACTIVE`\|`UNUSED`\|`DELETED`. Everything except `DELETED` executes; **`UNUSED` is a usage-scanner label, the rule remains fully executable** (`RuleStatus.java`). **No `INACTIVE`/`DRAFT`** | `ACTIVE` | `RuleStatus` |
| `ruleType` | enum | `PREDICATE`\|`EXECUTION_RULE`\|`VALIDATION_RULE`; determines `apply()` semantics | — | `RuleType` |
| `executor` | String | name of the `@ExecutorRule` bean: `GroovyPredicate`/`GroovyExecutionRule`/`GroovyValidationRule`; **must match `ruleType` 1:1** | — | `@ExecutorRule(name=...)` |
| `contextIdentifiers` | String[] | UUIDs of contexts from `contexts[]`; their `alias` becomes available as `context.<alias>`. **Often `[]`** — rules that only call `service.crud.<alias>` / `service.security` / `service.global` need no context (see below) | `[]` | `RuleScriptSettingsControlPanel.java` |
| `rule.ruleScriptStr` | String | script body (Groovy). **Without** the template wrapper — the executor adds it. Line breaks = `\n`, quotes = `\"` (this is a single JSON string) | — | `AbstractGroovyExecutor.java` |
| `hidden` | Boolean\|null | `true` → the rule is not shown in the Rules list. In practice `rules[]` carries only `null` and `false` — hand-written rules leave it `null`, generated ones write `false`; neither is anomalous, and `true` is vanishingly rare | `null` | `RuleDto.hidden` |

> **`contextIdentifiers: []` — the dominant pattern for dropdown sources.** In a mature project a sizeable
> minority of all rules carry an empty `contextIdentifiers`, and they are almost exclusively the
> `RIMM_<alias>_cruid` rules (dropdown sources) and `Find — …` rules. They use the
> context-**independent** path `service.crud.<alias>` (resolved against the full CRUD registry of the realm/client,
> `DynamicRuleContext.groovy`), so they need no context. Attaching a context to such a rule
> is **not needed** — see the recipe below.

### Export shape — the `context` rep-object

Under the `contexts` key (an array). Worked example:

```json
{
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "871f974f-e775-401a-adfc-e822110f3b99",
  "name": "Finance Context",
  "alias": "finance_context",
  "crudAliases": [
    "bl", "counterparties_cruid", "invoice_statuses_cruid", "invoices_cruid",
    "payment_methods_cruid", "payments_cruid", "users_cruid",
    "..."
  ]
}
```

| Field | Type | Value | Backing |
|---|---|---|---|
| `identifier` | String(uuid) | context ID; goes into `rule.contextIdentifiers[]` and into the form's `settings.contextIdentifier` | `ContextDto` (`AbstractSecuredDto.identifier`) |
| `name` | String | human-readable name | `ContextDto.name` |
| `alias` | String | **syntactic token** — `context.<alias>...` in scripts; must be a valid Groovy identifier | `ContextDto.alias` |
| `crudAliases` | String[] | list of CRUD aliases allowed within this context; the gate for `context.<alias>.<crud>` and `service.crud.<crud>` (when the rule has a context) | `ContextDto.crudAliases` |

> **One context per project — the typical pattern.** A production project normally has exactly **one** context
> (`jq '.contexts | length'` → 1; a fresh empty starter → 0), whose `crudAliases` list every dynamic CRUD alias
> plus `bl` (the Business-Logic CRUD). Rules that **need** `context.<alias>.<crud>.data` (action-visibility
> predicates, validations, form-scoped rules) reference this single context; `service.crud`-only rules
> leave `contextIdentifiers: []`. Only split into several contexts when two subsystems must genuinely not see
> each other's CRUDs — the alias gate is the only isolation the model offers.

> **`crudAliases[]` may be a SUPERSET.** The invariant is **one-directional**: every alias a rule reads via
> `context.<alias>.<crudAlias>` (and every dynamic-crud in `dynamic-cruds.json`) **must** be in `crudAliases[]`
> — `validate` errors the reverse (`validate_cmds.py`, "crud alias not listed in any context.crudAliases").
> But `crudAliases[]` may list **more** aliases than there are dynamic-cruds: it can include an alias with **no**
> `dynamic-cruds.json` entry — `bl` (the Business-Logic CRUD) always is one, and a configuration/lookup alias
> left over from an earlier iteration may be another (listed, no dynamic-crud, zero rule references).
> A superset alias is **not** an error — don't "prune" it to match the crud list.

> **MODIFY-FILLED — adding an alias to an existing context.** When a new rule needs
> `context.<ctx>.<newAlias>.data` (or `service.crud.<newAlias>` with a bound context), run
> `mrjun.py context add-alias <ctx> <newAlias>` (idempotent — re-running is a no-op; `rep_cmds.py`).
> It appends to that single context's `crudAliases[]`. **Do NOT create a second context** for this — the
> single-context layout is the norm; append to `contexts[0].crudAliases[]`.

> DB note: the `nct_rule` table has a `context_identifiers` column
> (JSONB) and `system_rule` (BOOLEAN). In the **export** the counterparts are `contextIdentifiers` and **`hidden`**
> (not `systemRule`). The `context` table stores `crud_aliases`(JSONB) and `crud_names`(JSONB); the export
> contains only `crudAliases`.

> ⚠️ **`crudAliases[]` is the ONLY crud↔context link — dynamic CRUDs carry no context reference.** A crud in
> `dynamic-cruds.json` has `alias`/`dtoFields`/`methods`/`source*` and **no `contextIdentifier`**; the sole record
> that "crud X belongs to context Y" is the alias appearing in `contexts[].crudAliases`. So if a context imports
> with an empty/short `crudAliases`, the business-logic UI shows that **context with no CRUDs**, and every rule
> resolving `context.<alias>.<crudAlias>` / `service.crud.<crudAlias>` throws at runtime:
> `No CRUD found with alias <crudAlias> in context <contextAlias>` (the executor gate, `DynamicRuleContext.groovy`).
> Two causes, in order of likelihood: (1) the **whole rep-objects import aborted** on a malformed object (a
> string-where-object; the context is a rep-object, so it was skipped along with sources/DB — see
> [00](00-export-format-and-import.md), the scattered-symptom table) — this is NOT a context-data problem, it's a
> deserialization abort, diagnose in `log/ui.log`; (2) the `crudAliases[]` genuinely omits the alias — add it with
> `mrjun.py context add-alias <ctx> <alias>`. Note the import assigns the saved context a fresh DB **id** while
> **preserving its `identifier`** — a changed id in `Saved Context … {id}` logs is not a problem.

---

## Templates and return semantics

Your `ruleScriptStr` is not run as a standalone script: the executor splices it into a **generated method** and
compiles the result. Two things follow, and both bite. Inside that method `context` is already bound (so
`context.*` works in your body), and the method **ends with an unconditional `return null` placed AFTER your
code**. There are exactly two generated shapes — one shared by PREDICATE **and** EXECUTION_RULE, one for
VALIDATION_RULE.

### The EXECUTION / PREDICATE shape

⚠️ **Key gotcha (load-bearing).** Because the generated method ends with its own `return null` *after* your
body, a script that does not `return` explicitly returns `null`. A bare final expression (`true`,
`context...status == 'DRAFT'` written without `return`) is **discarded** — Groovy's "last expression is the
value" does not apply here.

- For **PREDICATE** this is fatal: `GroovyPredicate.apply()` casts the result to
  `Boolean`; on `null`/non-Boolean it throws
  `RuleExecutionException("Predicate rule must return Boolean, but returned: null")`.
  **Always write `return <boolean expression>`.**
- For **EXECUTION_RULE** `apply()` returns the result as-is (`(R) result`). If the rule
  must return a value (dropdown source, fetch rule) — a `return` is needed. If it's a
  side-effect rule (`init`/`create`/`delete`, mutating `context.<...>.data`), there's nothing to return —
  the trailer returns `null`, and that's fine.

> This trailer is present in the current platform — it is not a legacy quirk that has since been fixed.

> **Triage of `mrjun.py validate` "no top-level `return`" warnings.** `validate` emits this as a
> **WARN** for **both** `PREDICATE` and `EXECUTION_RULE` (`tools/mrjunkit/validate_cmds.py`
> it does not distinguish them). Interpret by type:
> - On a **`PREDICATE`** the warning is a **hard error to fix** — every one. Without `return` the trailer
>   returns `null`, `apply()` throws `"must return Boolean"`, and the button/field/mapping mis-behaves. Prepend
>   `return` to the boolean expression.
> - On an **`EXECUTION_RULE`** it is **advisory**: fix only the **value-returning** ones (dropdown/`fetch`/
>   `choices`, and GROOVY `find`/`count` methods that build a page map). A pure side-effect rule
>   (`init`/`create`/`delete`, mutating `context.<...>.data`) legitimately has no `return` — leave it.

### The VALIDATION shape

Same splice, same trailer — but here the return value is **ignored**: `GroovyValidationRule.apply()` reads
not the result of `execute()`, but a fresh `ValidationResultCollector`
(`validationCollector.createValidatedObject()`), to which the script added errors/warnings via
the **`validation` binding** and the bare helpers available in a validation script:

| Helper (bare, works in a validation script) | Equivalent | Category |
|---|---|---|
| `addError(msg)` / `validation.addError(msg)` | general error | **blocks submit** |
| `addWarning(msg)` / `validation.addWarning(msg)` | general warning | does not block |
| `addFieldError(field, msg)` / `validation.addFieldError(field, msg)` | field error | **blocks submit** |
| `addFieldWarning(field, msg)` / `validation.addFieldWarning(field, msg)` | field warning | does not block |

> ⚠️ **Only these four methods exist** on `ValidationResultCollector`
> (`ValidationResultCollector.java`). There is **no** `addInfo(...)` in the code — do not use it
> (older platform documentation mentions it in error). An empty collector = validation passed.

> 🔑 **The `field` arg of `addFieldError`/`addFieldWarning` is the control's `name` (`settings.name`, the human
> label), NOT its `fieldExpression`/column and NOT a component id.** At submit `FormPlugin` lands the message on
> the control whose `getSettings().getName()` equals `field` (`FormPlugin.java`); a wrong name drops it
> silently, and a blank/absent `field` makes it a **global** (form-level) error. So you *read* the column via
> `getField('<col>', …)` but *target* the control by its label. Global (`validators`) vs action-based
> (`actionValidators`) form validation + this field-targeting → [25 §4.2](25-form-settings-validation-and-events.md).

Worked VALIDATION script (`Declaration Code Size Validation`):

```groovy
def declaration = context.customs_context.declarations_cruid.data.get()
def code = declaration.declarationCode
if(code != null && code.size() > 10) {
  validation.addFieldError(
    "Declaration Code",
    "Please keep the code to 10 characters or fewer"
)
}
```

### Aborting an action with a message (`throw`)

To **block an action and show the user a message**, `throw` from an **EXECUTION_RULE** (action logic /
`onBeforeStart` / `onBeforeComplete`) — **not** from a predicate. When the rule throws, the operation aborts and
the exception message surfaces as an **error toast**: for a CRUD-table action the UI shows the rule error verbatim
via `err.getMessage()` (`CrudTablePlugin.java` before-start, before-complete; create-flow;
catch-all `nctError("Failed to execute action: " + e.getMessage())`). A **PREDICATE** cannot do this —
it only hides/disables the button (returns a Boolean, shows nothing, aborts nothing). Guard-with-message is a
load-bearing idiom: expect several per project, typically one on every action that posts, submits or activates
a document.

```groovy
def bom = context.erp_context.bill_of_materials.data.get()
if (!bom.lines) {
    throw new RuntimeException("Add at least one component before activating")
}
service.crud.bill_of_materials.activate(bom.id)
```
The same shape covers "Add at least one line before posting" on a goods issue, "Add at least one line before
submitting" on a purchase order, "Attach the signed contract before approving" on a document flow. The message is
shown **as typed** — write it user-facing. Full capability context:
[16-groovy-service-api.md](16-groovy-service-api.md) §2.1.

---

## Bindings inside the script (what's available)

The executor sets all of these as properties on the script-class instance before calling `execute()`
(`AbstractGroovyExecutor.java`; `realm`/`client` are deliberately **not** passed).
Template fields: `dynamicContext`, `userId`, `service`, `contextIdentifiers`, `contextDataMap`, `attrs`,
`param` (EXECUTION only, `ExecutionRuleTemplate.groovy`); `validation` (VALIDATION only, `ValidationRuleTemplate.groovy`).

| Binding | Type | Available in | Notes |
|---|---|---|---|
| `context` | `RuleExecutor` (`= this`) | all | entry point into the context model; `propertyMissing` delegates to `DynamicRuleContext` |
| `service` | `ServiceWrapper` | all | service facade (see below) |
| `attrs` | `Map<String,JsonNode>` | all | UI/component parameters; values are **JsonNode**, extract via `.asText()/.asInt([def])/.asLong()/.asDouble([def])/.asBoolean([def])/.isNull()`; `attrs.containsKey(k)` |
| `param` | `Map` | **EXECUTION only** | parameters of a delegated CRUD method (see §"param") |
| `validation` | `ValidationResultCollector` | **VALIDATION only** | + bare helpers `addError/addWarning/addFieldError/addFieldWarning` |
| `userId` | String | all | id of the current user |
| `currentData` | `CrudDataDto` \| `null` | all | the current item in a nested (List) form; `null` in the parent (see below) |
| `realm` / `client` | — | — | **BLOCKED** as bare variables (`SecurityException`, `ExecutionRuleTemplate.groovy`); realm/client is injected by the system |

### `context` — the context model

`context` is the `RuleExecutor` itself, whose `propertyMissing` delegates to `DynamicRuleContext`
(`ExecutionRuleTemplate.groovy`). Permitted accesses:

| Syntax | What it does | Backing |
|---|---|---|
| `context.<ctxAlias>` | context wrapper; `<ctxAlias>` must be among the attached `contextIdentifiers` | `DynamicContextWrapper` (`DynamicRuleContext.groovy`) |
| `context.<ctxAlias>.<crudAlias>` | CRUD wrapper; `<crudAlias>` must be in `context.crudAliases` | |
| `context.<ctxAlias>.<crudAlias>.data.get()` | **the current row** as a Map (JsonNode → object) | → `CrudDataWrapper` → `CrudDataDto.get()` |
| `...data.getField('col', Type.class)` | one field of the row (dot-path: `'company.id'`) | `CrudDataDto.getField` |
| `...data.getField('col', default)` | field with a default | `CrudDataDto.getField` |
| `...data.put(obj)` | replace the entire current row | `CrudDataDto.put` |
| `...data.setField('col', val)` | write one field (creates nested objects) | `CrudDataDto.setField` |
| `...data.hasField('col')` | whether the field exists | `CrudDataDto.hasField` |
| `context.<ctxAlias>.<crudAlias>.service.<method>(args)` | call a CRUD method (same path as `service.crud`) | `DynamicRuleContext.groovy` → inner `ServiceWrapper` → `executeCrudMethod` |
| `context.<ctxAlias>.data.<attr>` (read) / `= v` (write) / `.getAttr(k)` / `.setAttr(k,v)` | attributes of **this context** (CONTEXT scope) | `ContextDataWrapper` (read, write) |
| `context.data.<attr>` (read) / `= v` (write) / `.getAttr("k")` / `.setAttr("k",v)` | **global** attributes (GLOBAL scope) — persisted with the case inside a process, otherwise living as long as the document | `GlobalDataWrapper` (read, write); method syntax → `ContextDataDto.getAttr`/`setAttr` |
| `context.contextData` | raw `ContextDataDto` | |
| `context.currentData` | the current item in a nested (List) form, or `null` in the parent | `ExecutionRuleTemplate.groovy` |

> **Three form scopes** (see [02-form-controls-reference.md](02-form-controls-reference.md)):
> `scope:"GLOBAL"` ↔ `context.data.*` (`attrs`); `scope:"CONTEXT"` ↔ `context.<ctxAlias>.data.*`
> (`contextDataMap[ctx].attrs`); `scope:"CRUD"` ↔ `context.<ctxAlias>.<crudAlias>.data.*`
> (`contextDataMap[ctx].crudDataMap[alias].value`).
> `context.data.foo` (property) and `context.data.getAttr("foo")` (method) are equivalent and work
> side by side. An unknown attribute → `null`.

> ⚠️ **An attribute lives as long as the DOCUMENT that carries it — and it is tied to that one document.**
> Inside a case, the process persists its context data between nodes, so `context.data.setAttr` IS how one step
> publishes to the next (that is the pattern [07](07-workflows-and-tasks.md) mandates). Inside an open form, the
> form holds the document for as long as it is open. With neither — a scheduler tick, a headless service task,
> a rule invoked on its own — the document is built for that one execution and is gone with it.
> `service.store.session.*` / `service.store.user.*` ([16](16-groovy-service-api.md) §2.14) are the other axis:
> tied to the browser session or to the person rather than to a form or a case, and reachable from any rule,
> including one that has neither. Use an attribute to carry something along a case or a form; use the store to
> remember something about the SESSION or the USER.

> **Which of the three a submitted form value is in depends on how the form was OPENED.** From a workflow user
> task or a ProcessTable start/global action it is in the attrs — `context.data.*` for a `GLOBAL` control,
> `context.<ctx>.data.*` for a `CONTEXT` one. From a CRUD-table / CRUD-tree
> ACTION every control on the form is bound to that table's CRUD, so it is on the row
> (`context.<ctx>.<alias>.data.get()`) while `context.data.getAttr("<field>")` for that field is `null` — the
> attrs still carry the action meta `__actionId`/`__actionName` and anything an `onBeforeStart` rule set — see
> [02-form-controls-reference.md](02-form-controls-reference.md) §Where the value LANDS. The two mis-reads fail
> differently: reading the ATTRS on the action path is silent — the rule runs with `null`, writes nothing and
> still reports success — while reading the ROW off a crud form THROWS. Which throw depends on how far the
> chain gets: `No context found with alias: <ctx>` (`MissingPropertyException`, the usual case when the rule
> carries no `contextIdentifiers`), `No CRUD found with alias: <alias> in context: <ctx>`, or — when both hops
> resolve but nothing seeded `crudDataMap[<alias>]` — `RuntimeException: No CRUD data available for CRUD:
> <alias>` on the `.data` access itself. That is why the row read below catches `Throwable` and never matches
> on the message; do not trim it.
>
> A rule reachable from BOTH entry points — the normal shape when one decision is offered from the worklist and
> from the table row — reads both, **attrs first**: on the task path the attrs hold what the user just typed
> and the row read is the one that throws (that is what the `try/catch` below absorbs); on the table path the
> attrs carry no form value and the row IS the typed value.
>
> ```groovy
> def FORM = { alias, field ->
>     def v = context.data.getAttr(field)
>     if (v != null) { return v }
>     def row = null
>     try { row = context.<ctx>."${alias}".data.get() } catch (Throwable ignored) { }
>     return (row instanceof Map) ? row[field] : null
> }
> def note = FORM('<alias>', 'decisionNote')
> ```
>
> `validate` errors on a literal `getAttr("<field>")` for a field of the action's own form; reading through the
> variable above does not trip it.

#### `currentData` — nested (List) forms

`context.currentData.get()` returns the current list item **only** during validation/logic of that
item; in the parent form — **`null`**. The backing is a synthetic context
`__temp_list_item_context__.__temp_item__` (`ExecutionRuleTemplate.groovy`). Order: first the
parent's validation (`currentData == null`), then each item is validated separately
(`currentData == item`); field errors bind to that item's row.

### `service` — the service facade (`ServiceWrapper`)

> 📚 **Full `service.*` capability surface** — what can actually be called in a script (crud/global/security/
> rimm/report(PDF)/notification/quota/enums/access/store/`rule(name)`), with signatures and cross-flows (PDF→mail, notifications) —
> [16-groovy-service-api.md](16-groovy-service-api.md). Below is a brief facade summary.

The full surface (`@Getter` fields `ServiceWrapper.java` + the `rule()` method):
`access, rimm, security, notification, quota, global, crud, report, enums, workflow, store, actionName, actionId`
+ `rule(name)` + `redirectPage(path)`.

| Syntax | What | Available in | Backing |
|---|---|---|---|
| `service.crud.<crudAlias>.<method>(args)` | call a dynamic CRUD method (context-agnostic) — **the main data API** | all | `ServiceWrapper.crud` ← `ServiceCrudLookup` |
| `service.security.user()` | the current user (`.email`, `.id`, `.firstName`, …) | all | `SecurityHelper.user` |
| `service.security.hasAnyRole("A","B")` | true if the user has **at least one** of the roles | all | `SecurityHelper.hasAnyRole` |
| `service.security.hasAllRoles("A","B")` | true if the user has **all** the roles | all | `SecurityHelper.hasAllRoles` |
| `service.security.hasAnyRoleGroup("Author")` | true if the user is in **at least one** of the role groups — **the one you will reach for almost every time** | all | `SecurityHelper.hasAnyRoleGroup` |
| `service.security.hasAllRoleGroups("A","B")` | all role groups | all | `SecurityHelper.hasAllRoleGroups` |
| `service.rimm.run([name:..., itemsPerPage:..., parameters:[:]])` | run a saved RIMM query by name | all | `ServiceWrapper.rimm` (`RimmServiceProxy`) |
| `service.global.conversion.toSelectOptions(list,"id","label")` | list → dropdown options | all | `ServiceWrapper.global` (GlobalFunctions, YAML-defined) |
| `service.global.conversion.toSelectOptionsLocalized(list,"id","label"[,localeKey,locField])` | localized options | all | `ServiceWrapper.global` |
| `service.global.conversion.toAutoCompleteOptions(list,"label")` | list → autocomplete suggestions (single field) | all | `ServiceWrapper.global` |
| `service.global.conversion.toAutoCompleteOptionsLocalized(list,"label"[,localeKey,locField])` | localized autocomplete suggestions | all | `ServiceWrapper.global` |
| `service.enums['EnumName'].list()` | enum values | all | `ServiceWrapper.enums` (`@Setter`, snapshot per-invocation) |
| `service.notification.push.*` / `service.notification.mail.<alias>(...)` | push/mail | **EXECUTION only** | `NotificationWrapper` — built only in `GroovyExecutionRule.java` |
| `service.report.pdf.get.<alias>(...)` / `.download(...)` / `.email.<mail>(...)` / `.push.*` | PDF reports | **EXECUTION only** | `ReportWrapper`/`PdfReportProxy` — `setReport` only in `GroovyExecutionRule.java` |
| `service.quota.*` | quotas | **EXECUTION only** | `QuotaProxy` — built only in `GroovyExecutionRule.java` |
| `service.access.*` | role/user-access mutations (`addRoleAccess`, `hasRoleAccess`, …) | all | `ServiceWrapper.access` (`AccessManager`) |
| `service.workflow.start("<workflowIdentifier>", ctxMap[, opts])` | start a process; returns its identifier. First argument is the workflow **identifier** (autocompleted inside the quotes), and the workflow must be deployed | **EXECUTION only** (incl. CRUD GROOVY methods) | `WorkflowProxy` — `setWorkflow` refuses in predicate/validation |
| `service.workflow.list / actions / startActions / contextData / complete` | work an EXISTING case: page through a worklist, ask what may be done to a process, read its context data, execute an action with new data. The first argument of most of them is a **process table's Settings ID**, which makes the rule inherit that table's workflow, filter and indexes — see [16](16-groovy-service-api.md) §2.13 | **EXECUTION only** (incl. CRUD GROOVY methods) | same gate as `start` |
| `service.store.session.get/put/remove/containsKey/keys/all/clear` | key/value storage for the **browser session**, per project. Empty (put stores nothing, get answers `null`) wherever no browser session took part: a VALIDATION rule, a CRUD GROOVY method invoked directly from a page, anything a process table evaluates or runs against a case, scheduler / Kafka / MCP — see [16](16-groovy-service-api.md) §2.14 | all (but see the empty-list) | `RuleStoreProxy` → `SessionKeyValueStore` |
| `service.store.user.get/put/remove/containsKey/keys/all/clear` | the same eight methods, stored in the database **per user** and outliving the session. Empty wherever there is no acting user | all | `RuleStoreProxy` → `UserKeyValueStore` |
| `service.redirectPage("alias/page")` | send the BROWSER to another page of this project after the rule returns. Path WITHOUT the organisation, which is prepended for you; a full URL is refused. Nothing happens when no browser is waiting — see [16](16-groovy-service-api.md) §2.15 | **EXECUTION rules only** — a predicate, a validation rule and a CRUD GROOVY method all refuse it | `ServiceWrapper.redirectPage` |
| `service.rule("Rule Name")` | run another rule **by name** (`findByName`), return its `returnValue`; same `contextData` | all | `ServiceWrapper.rule` |
| `service.actionName` / `service.actionId` | name/id of the pressed action button (**`null`**, not `""`, if the rule was not invoked from a button — test `service.actionId != null`, never `!= ''`); **prefer `actionId`** (stable, locale-independent) | all | `ServiceWrapper.actionName/actionId` |

> ⚠️ **Choices-rule tail is mandatory.** Dropdown/tree pickers end their rule in `toSelectOptions*`, autocomplete
> controls in `toAutoCompleteOptions*` (the `*Localized` variant when the display column is localized); a choices rule
> that returns the raw `find`/`findAll` list instead renders **"No results found"** + hides Show Nav — full contract
> in **02 §4a**.

> ⚠️ **Role checks always go through `service.security.*`.** The canonical form is
> `service.security.hasAnyRoleGroup(...)` — e.g. a reusable `Is Approver` predicate whose whole body is
> `return service.security.hasAnyRoleGroup("Approver")`. **The bare form `hasAnyRole(...)`
> without `service.security.` does NOT work** in EXECUTION/PREDICATE scripts: the template class `RuleExecutor`
> does not implement `IRuleExecutor`, and its `methodMissing` throws `MissingMethodException`
> (`ExecutionRuleTemplate.groovy`). The `IRuleExecutor.groovy` interface is merely the contract of another
> execution path, not a mixin on the template. (Bare `addError/addFieldError/...` in **validation**
> scripts is the exception: they are explicitly defined on `ValidationRuleExecutor`,.)

> ⚠️ **`realm`/`client`** are available as `service.realm`/`service.client` getters, but **blocked**
> as bare variables (`SecurityException`, `ExecutionRuleTemplate.groovy`).

> ⚠️ **There is NO `service.feign(...)` or `service.localization(...)`** — older platform documentation
> uses them, but they do **not** exist in `ServiceWrapper`, and no working project calls them. For external services —
> `inject('emailService')`/RIMM/global functions; for validation localization — the form's per-locale `*Messages` maps
> or `service.global.locale.getKey()`.

#### `inject("beanName")` — allow/block-list (`ExecutionRuleTemplate.groovy`)

This is the **authoritative security boundary** for Spring beans:
- `inject("rimmService")` → returns a **safe proxy** `service.rimm` (not the raw bean).
- `inject("contextService"|"reactorService"|"ruleService"|"crudReactor")` → **`SecurityException`** (blocked).
- Allow-list by name: `emailService, notificationService, validationService, calculationService,
  formatterService, dateService`, plus any bean whose name ends in `Helper` or `Util`.
- Other beans load with a warning log (not recommended).

### `param` — parameters of a delegated method (EXECUTION only)

When a dynamic CRUD method has `methodType: "GROOVY"`, its call goes over RSocket to the integration,
which replies `{status:"delegated", ruleIdentifier}`, and the executor runs the attached rule,
passing the method's arguments into the **`param`** binding (Map) (`ReactorServiceImpl.groovy` →
`GroovyExecutionRule.java`, `contextDataMap.put("param", paramMap)`). This is how a `find` CRUD method
reads pagination: `def filter = param ?: [:]` → `filter.rowsInPage`/`filter.pageNumber`.

---

## How `service.crud.<alias>.<method>` resolves (dynamic)

1. `service.crud.<crudAlias>` → `ServiceCrudLookup.propertyMissing` (`DynamicRuleContext.groovy`):
   - **if the rule has NO contexts** (`contextMap.isEmpty()`) → resolve against the **full
     CRUD registry** of the realm/client via `crudReactor.getRSocketRequester(...)`; if the alias is not
     registered — `MissingPropertyException`. **This is the path of all `RIMM_*` dropdown rules
     with `contextIdentifiers: []`.**
   - **if there are contexts** → the alias must be in the `crudAliases` of at least one, otherwise
     `MissingPropertyException("No CRUD found with alias: … in any attached context")`.
2. `.method(args)` → `ServiceCrudInvoker.methodMissing` → `reactorService.executeCrudMethod(...)`.
3. `executeCrudMethod` (`ReactorServiceImpl.groovy`) makes an RSocket request to the integration
   that owns the alias (`crud.<realm>.<client>.<token>.<crudAlias>.execute`).
4. Response:
   - ordinary JSON → returned as a Groovy object;
   - `{status:"delegated", ruleIdentifier}` → the corresponding Groovy method rule is executed
     (`executeDelegatedRule`), parameters → `param`.

Example chain: the GROOVY `find` of a CRUD calls the SQL `count` and `findAll` of that same CRUD —
this is the body of `invoices_cruid.find` in `dynamic-cruds.json`:

```groovy
def filter = param ?: [:]
def countResult = service.crud.invoices_cruid.count()
def total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long
def rows = service.crud.invoices_cruid.findAll(filter) ?: []
def rowsInPage = (filter.rowsInPage ?: 0) as int
def pageNumber = (filter.pageNumber ?: 0) as int
return [
    content: rows,
    totalElements: total,
    totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,
    pageNumber: pageNumber
]
```

> `context.<ctx>.<crud>.service.<m>()` and `service.crud.<crud>.<m>()` are **the same path**
> (`reactorService.executeCrudMethod`); the second is shorter and needs no attached context, and it is
> **the form you should default to** — `context.<ctx>.<crud>.service.*` earns its keep only when the rule is
> already reading `.data` from that same context.
> The canonical `find` call: `service.crud.<alias>.find([rowsInPage, pageNumber:0])`. Mongo-style
> operators (`['$gte':…]`, `['$regex':…]`) are **not** part of this API — filtering is SQL, written in the
> CRUD's own methods (see [11](11-business-logic-dynamic-crud.md)); don't reach for them here.

---

## How `context.<ctx>.<crud>.data` gets populated in various places

`data.get()` reads a two-level map: the outer key is the **context identifier**, the inner key is the
**CRUD alias**. So for `context.<ctx>.<crud>_cruid.data.get()` to return a row, the calling surface must
have filed that row under exactly those two keys. Both must match what the rule asks for — a row filed
under a different context identifier is invisible to the expression, and `data.get()` simply returns
nothing.

Behavior by surface type:

| Surface | What's placed into `data` | contextIdentifier | Source |
|---|---|---|---|
| **CRUD table** (row action / visibility predicate / fetch / before-start / before-complete) | **the full row entity** (loaded by id) | `model.getContextIdentifier()`, empty → `crudAlias` (`CrudTablePlugin.java`) | `executePredicateWithCrudContext` / `executeRuleWithCrudContext` |
| **CRUD tree** | same as the table | as above | `CrudTreePlugin` (same service) — see [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) |
| **Process table** (`process.table.pluin`) | the current process row, analogous to the table | as above | the same `RuleExecutionService` |
| **Form** (prohibited/hidden/required/choices/validation) | form field values (field-centric); in CREATE mode — an empty seed | the form's `settings.contextIdentifier`, `crudAlias` from settings | `FormPlugin`; in CREATE it seeds an empty `CrudDataDto` |
| **Form "Run" in the rule editor** | **the entity by id** (the full row, including non-form fields like `status`) | as for the form | `FormPlugin.LIVE_FORM_CONTEXT_DATA_ATTRIBUTE` (published by `FormPlugin.java`) → `RuleEditPanel` reads it (`RuleEditPanel.java`) → `workflowExecutionService.execute(...)` |
| **List item** (nested form) | the current item is available as `context.currentData` (the special `__temp_list_item_context__.__temp_item__`) — both in the item's VALIDATION rules and in the list action's **On Before Complete** EXECUTION rule, which runs after validation and before the line is merged into the parent list, so `context.currentData.setField('a.b', v)` there decides what the list actually stores | — | `ExecutionRuleTemplate.groovy`; `ListItemFormPlugin.handleSubmit` → `executeBeforeCompleteRule` |
| **Workflow** (service-task / gateway / user-task) | ⛔ whatever the START put in the document, and nothing more: the process's own `attrs`, plus any `crudDataMap` the start seeded — a start form's own CRUD-scoped controls, or the document a rule passed to `service.workflow.start`. **Never a row the process fetched itself.** See below. | as configured | see [07-workflows-and-tasks.md](07-workflows-and-tasks.md) |

⛔ **The workflow row is the one that catches people out, so read it twice.** A RUNNING process files no
entity of its own into `crudDataMap`. There is no code path that does: a user-task action is not in a
crud-table settings object, so `FormPlugin.initCrudMode()` never runs and no `crudId` is ever resolved; a
process-table global action has no row at all.

That is not the same as "the document is empty". It holds exactly what the START wrote into it: a start form's
own CRUD-scoped controls (shape A), or the `crudDataMap` a rule passed to `service.workflow.start` (shape C —
[27](27-event-driven-process-start.md) §4.2). Both survive into the process and both are what a task form, a
gateway predicate and a `scope: CRUD` process-table column read. What is missing is only the FETCH: nothing
refreshes that document from the table afterwards, so it is a snapshot that ages. The three start shapes are
in [07](07-workflows-and-tasks.md).

So a rule, predicate or form that reaches its subject through `context.<ctx>.<alias>.data` alone works on a
crud table and is **silently empty inside a process**: the form renders blank, the rule throws its "no
record selected" branch, the gateway predicate returns false and the token takes the `default` exit without
any error anywhere. The full contract, the `_rid` resolver and the checklist are in
[07-workflows-and-tasks.md](07-workflows-and-tasks.md) → *What a process can see*. `mrjun.py validate` catches
part of it — it WARNs on a CRUD-scoped process-table column whose alias no start form and no start rule
seeds, and on CRUD-scoped read-only fields on a process form — but a rule that resolves only through the crud
context is a finding it reports, not a build it can stop.

⚠️ From a form you cannot read `status` and other non-form fields via the field-centric `contextData` (they
aren't there). For action predicates the table/tree load the **full entity**, so
`context.<ctx>.<crud>.data.get().status` works there. The same asymmetry explains why a predicate that works
on a row action fails when the identical rule is reused inside a form — and why the same rule reused on a
**gateway** is worse than broken: there the map may be present but STALE (a copy taken when the case opened),
so instead of failing it answers confidently with last week's value. A rule that decides on record state is
therefore not portable between a table and a gateway, however identical the question sounds.

When a rule is invoked from an action button, the caller also places `service.actionId`/
`service.actionName` via `attrs.__actionId`/`__actionName` — so a form-mapping predicate can write
`return service.actionId == '<uuid>'`.

### Data-availability matrix in a predicate (behavioral — verify at runtime)

| Invocation source | Entity data | Process vars | User info |
|---|---|---|---|
| Workflow Task Action | ⛔ **no** — resolve the id from a process var and `service.crud.<alias>.get(id)` | yes | yes |
| Workflow Start Form | no | no | yes |
| CRUD Edit Action | yes | no | yes |
| CRUD Create Action | no (empty seed) | no | yes |
| Gateway Routing | ⛔ **no** — same. Unseeded, a predicate that reads the crud context is silently ALWAYS FALSE; **seeded** (a start document that publishes the subject — the only channel a case with no start form has), it is silently ALWAYS THE VALUE AT CASE START, because `contextDataMap` is a copy in a process variable that nothing refreshes. Either way one branch becomes unreachable. Resolve the id from it if you like, then `service.crud.<alias>.get(id)` | yes | yes |
| Field Visibility/Mandatory | depends on the form context | depends | yes |
| Filter Form | no | no | no |

Hence — **null-safe predicates**: in CREATE mode `context.<ctx>.<crud>.data.get()` returns an empty
seed, so `data.get()?.status == 'DRAFT'` (with `?.`) is safer than direct field access.

### Context merge on task completion (workflow)

On `task-complete` the context is merged by `ContextDataMergeUtil.mergeContextData(target, source)`:
`access` = override; GLOBAL/CONTEXT `attrs` = source overrides target; CRUD = **field-level deep
merge** (source fields are overlaid onto target; a primitive/array = full replacement). Important for
before-complete rules that write a partial entity. (Verify against the running platform before relying on the
exact deep-merge semantics.)

---

## Field-based validation templates (form control, 51 templates)

**This is where MOST field validation belongs — not in a `VALIDATION_RULE`.** A **form control validates
itself declaratively** via the "Validation Template" dropdown in its own field settings (stored in the control's
`conditionalValidations[]`, each `{predicateIdentifier, severity ERROR|WARNING, localized message}` —
[02-form-controls-reference.md](02-form-controls-reference.md)). It generates a **predicate** on the field; the
contract is **predicate-true = INVALID** (`BuiltinTemplates.java`). This is the **opposite polarity** to
the form's `validationPredicate`, where **true = valid** — be sure to distinguish them. The predicate can read
**other** submitted fields, so **cross-field** checks live here too (validation runs on submit). Reach for a
hand-written `VALIDATION_RULE` (below) **only** when the logic is genuinely complex **and** the error/warning
text must be **computed at runtime** and depends on many things. The full set
(`BuiltinTemplates.java` → `registerAll`; 51 registrations; in parentheses — the param-id):

- **Cross-type**: `required`, `equalsConst`(`value`), `notEqualsConst`(`value`), `inList`(`values`), `notInList`(`values`).
- **String**: `strLenBetween`, `strLenMin`, `strLenMax`, `strLenExact`, `strRegex`(`pattern`), `strRegexNot`(`pattern`), `strStartsWith`(`prefix`), `strEndsWith`(`suffix`), `strContains`(`needle`), `strNotContains`(`needle`), `strUppercase`, `strLowercase`, `strNoWhitespace`, `strTrimmed`.
- **Numeric**: `numBetween`, `numLt`, `numLeq`, `numGt`, `numGeq`, `numEq`, `numNeq`, `numPositive`, `numNegative`, `numNonZero`, `numMultipleOf`, `numDecimalPlaces`.
- **Boolean**: `boolMustBeTrue`, `boolMustBeFalse`.
- **Date**: `dateBefore`, `dateAfter`, `dateBetween`, `dateEquals`, `dateInPast`, `dateInFuture`, `dateToday`, `dateWeekday`, `dateWithinDays`, `dateOlderThanDays`.
- **JSON**: `jsonHasKey`(`path`), `jsonMissingKey`(`path`).
- **List**: `listNotEmpty`, `listSizeMin`, `listSizeMax`, `listSizeBetween`, `listAllUnique`, `listContains`(`value`).

A template's compatibility with a field is filtered by `ValueType` (`ValidationTemplateRegistry.forType(type)`).
`ValueType` (full enum): `JSON, OBJECT_NODE, ARRAY_NODE, STRING, INTEGER, LONG, DOUBLE, FLOAT, SHORT,
BYTE, BIG_DECIMAL, BIG_INTEGER, BOOLEAN, ARRAY_LIST, INSTANT, LOCAL_DATE, LOCAL_DATE_TIME`. Sets:
NUMERIC = {INTEGER,LONG,SHORT,BYTE,FLOAT,DOUBLE,BIG_DECIMAL,BIG_INTEGER}; DATE_ALL =
{INSTANT,LOCAL_DATE,LOCAL_DATE_TIME}; STRING_ONLY={STRING}; BOOLEAN_ONLY={BOOLEAN}.

> The details of generating these predicates and their place in the form's `settings.stringValue` are in
> [02-form-controls-reference.md](02-form-controls-reference.md). Field-based mandatoriness
> (`alwaysMandatory` + `mandatoryMessages` per-locale) and `mandatoryPredicate` are there too.

---

## Worked examples of each type

**PREDICATE — a "required" control (field-emptiness check):**
```groovy
def v = context.finance_context.invoices_cruid.data.getField('counterpartyName', java.lang.String.class)
return v == null || (v instanceof CharSequence && v.toString().trim().isEmpty()) || (v instanceof Collection && v.isEmpty()) || (v instanceof Map && v.isEmpty())
```

**PREDICATE — "always true" (generated as a template):**
```groovy
return true
```

**PREDICATE — role check (a reusable `Is Approver`):**
```groovy
return service.security.hasAnyRoleGroup("Approver")
```

**PREDICATE — action by entity status:**
```groovy
return context.erp_context.bill_of_materials.data.get().status == 'DRAFT'
```

**EXECUTION — dropdown source via `service.crud` (contextIdentifiers: [], no explicit context):**
```groovy
def list = service.crud.counterparties_cruid.find([
  rowsInPage: 1000,
  pageNumber: 0
])
return service.global.conversion.toSelectOptions(list, "id", "name")
```

**EXECUTION — the same dropdown via an explicit context (when a context is attached):**
```groovy
def list = context.finance_context.counterparties_cruid.service.find([
  rowsInPage: 1000,
  pageNumber: 0
])
return service.global.conversion.toSelectOptionsLocalized(list, "id", "name")
```

> **`toSelectOptions` vs `toSelectOptionsLocalized`.** Use `…Localized` whenever the display column is a localized
> field (has a `localize` map) so labels follow the session locale; plain `toSelectOptions` always shows the
> base-locale column value. Either way the conversion tail is **mandatory** — a raw `find`/`findAll`
> list renders blank + hides Show Nav (**02 §4a**).

**EXECUTION — `create` logic (mutates the row, side-effect, no `return` needed):**
```groovy
def created = context.crm_context.accounts_cruid.service.create(context.crm_context.accounts_cruid.data.get())
context.crm_context.accounts_cruid.data.put(created)
```

**EXECUTION — `init` logic (set service fields before saving):**
```groovy
def inv = context.finance_context.invoices_cruid.data.get()
inv.createdAt = java.time.Instant.now()
inv.updatedAt = java.time.Instant.now()
inv.createdBy = service.security.user().email
context.finance_context.invoices_cruid.data.put(inv)
```
⚠️ A classic bug in this exact rule shape: the script says `context.finance_context.invoices.data.get()`
while the context lists `invoices_cruid`. The alias in the script must match `crudAliases[]`
**character for character**, or it fails at runtime with `MissingProperty` (gotcha #5). Truncated/"prettier"
spellings of an alias are the single most common cause.

**EXECUTION — `delete` logic:**
```groovy
context.erp_context.purchase_orders.service.delete(context.erp_context.purchase_orders.data.get().id)
```

**EXECUTION — running a saved RIMM query:**
```groovy
return service.rimm.run([
	name: "rimm_all_users",
  	itemsPerPage: 100,
	parameters: [:]
])
```

**VALIDATION — field error:**
```groovy
def declaration = context.customs_context.declarations_cruid.data.get()
def code = declaration.declarationCode
if(code != null && code.size() > 10) {
  validation.addFieldError("Declaration Code", "Please keep the code to 10 characters or fewer")
}
```

---

## How to construct from scratch — a concrete recipe

Task: build an **execution-rule source** for a dropdown that returns a list of counterparties
(`counterparties_cruid`) as `id → name` options.

### Step 1. Make sure the CRUD is registered

The dropdown source uses `service.crud.counterparties_cruid.find(...)` — the context-independent path.
The alias `counterparties_cruid` must exist in `dynamic-cruds.json.cruds[]` (see
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)) and its integration must be
connected. **No context is needed for this rule** — leave `contextIdentifiers: []`.

### Step 2. Add an element to `rules[]` (dropdown source, WITHOUT a context)

```json
{
  "realmName": "<realm>",
  "clientName": "<client>",
  "identifier": "11111111-2222-3333-4444-555555555555",
  "name": "RIMM_counterparties_cruid_id_name",
  "description": null,
  "status": "ACTIVE",
  "ruleType": "EXECUTION_RULE",
  "executor": "GroovyExecutionRule",
  "contextIdentifiers": [],
  "rule": {
    "ruleScriptStr": "def list = service.crud.counterparties_cruid.find([\n  rowsInPage: 1000,\n  pageNumber: 0\n])\nreturn service.global.conversion.toSelectOptions(list, \"id\", \"name\")"
  },
  "hidden": false
}
```

Key rules when generating the JSON by hand:
- **⚠️ CHOICES-RULE CONTRACT (load-bearing).** A dropdown/tree/autocomplete source MUST end by converting rows to
  option pairs, never return a raw entity list: dropdown/tree → `return service.global.conversion.toSelectOptions(list,"<key>","<display>")`
  (localized CRUD → `toSelectOptionsLocalized`), autocomplete → `return service.global.conversion.toAutoCompleteOptions(list,"<display>")`.
  A raw `service.crud.<a>.findAll(...)`/`find(...)` renders **"No results found"** AND hides the Show-Nav affordance
  (`validate` now **errors** on this). For a **searchable** dropdown use the `acFindAllBy<Cap(X)>Like` SQL +
  `acFindBy<Cap(X)>Like` wrapper + `RIMM_FILT_<alias>_<X>` rule pipeline — full recipe + naming table in **02 §4a**.
- `ruleType` and `executor` are **consistent** (`EXECUTION_RULE` ↔ `GroovyExecutionRule`).
- The script has an **explicit `return`** — otherwise the trailer `if(true){return null;}` returns `null` and the dropdown is empty. Two more empty-dropdown causes: (a) the rule returned the raw `find`/`findAll` list instead of piping it through `service.global.conversion.toSelectOptions*`/`toAutoCompleteOptions` → **"No results found"** + no Show-Nav; (b) for a **localized** CRUD, plain `toSelectOptions` was used instead of `toSelectOptionsLocalized`, so labels always show the base locale. See **02 §4a**.
- In `ruleScriptStr`, line breaks = `\n`, quotes = `\"` (this is a single JSON string).
- `contextIdentifiers: []` — a `service.crud`-only source needs no context (this is the pattern of every
  `RIMM_*` rule; resolution goes against the full CRUD registry, `DynamicRuleContext.groovy`).
- `identifier` — a new unique **UUID** (not a slug); the dropdown control's `settings.stringValue.ruleIdentifier`
  will reference it (see [02-form-controls-reference.md](02-form-controls-reference.md) and
  [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md)).

### Step 3. Reference it from the control

In the form dropdown control's settings (`properties.settings.stringValue`, a JSON string) set
`"ruleIdentifier": "11111111-2222-3333-4444-555555555555"`, `"crudAlias": "counterparties_cruid"`.
The control settings' `contextIdentifier` is only needed if the rule reads `context.<ctx>.<crud>.data`
(sources don't read it).

### Recipe: predicate for action visibility (context needed)

Here the rule reads the **row** via `context.<ctx>.<crud>.data`, so a context is **mandatory**:

```json
{
  "identifier": "aaaa1111-2222-3333-4444-555555555555",
  "name": "Invoice Can Edit",
  "status": "ACTIVE",
  "ruleType": "PREDICATE",
  "executor": "GroovyPredicate",
  "contextIdentifiers": ["871f974f-e775-401a-adfc-e822110f3b99"],
  "rule": { "ruleScriptStr": "return context.finance_context.invoices_cruid.data.get()?.status == 'DRAFT'" },
  "hidden": null
}
```
`invoices_cruid` **must** be in `finance_context.crudAliases`. When executed from a CRUD table the
executor places the full row into `data`, and `apply()` casts the result to `Boolean` → a `return` is required.
`?.` — in case of CREATE mode (empty seed).

### Recipe: role-check predicate (no context needed)

```json
{
  "identifier": "cccc3333-...",
  "name": "Is Approver",
  "status": "ACTIVE",
  "ruleType": "PREDICATE",
  "executor": "GroovyPredicate",
  "contextIdentifiers": [],
  "rule": { "ruleScriptStr": "return service.security.hasAnyRoleGroup(\"Approver\")" },
  "hidden": null
}
```

### Recipe: field validation rule (context needed)

> Use this **only for the rare complex case** (a runtime-computed message that depends on many things). For
> ordinary and even cross-field checks, prefer declarative field self-validation (`conditionalValidations`, the
> template catalog above) — see "Field-based validation templates".


```json
{
  "identifier": "bbbb2222-3333-4444-5555-666666666666",
  "name": "Product Name Length Validation",
  "status": "ACTIVE",
  "ruleType": "VALIDATION_RULE",
  "executor": "GroovyValidationRule",
  "contextIdentifiers": ["871f974f-e775-401a-adfc-e822110f3b99"],
  "rule": { "ruleScriptStr": "def name = context.erp_context.products_cruid.data.getField('productName', java.lang.String.class)\nif (name != null && name.length() > 50) {\n  validation.addFieldError('Product Name', 'Too long')\n}" },
  "hidden": null
}
```
No return is needed — only `validation.addFieldError(...)` matters (or the bare `addFieldError(...)`). Note the
script **reads** the column `productName` (`getField('productName', …)`) but **targets** the control by its **name**
`'Product Name'` (`settings.name`) — see the 🔑 note above; a global-vs-action-validator walkthrough is
[25 §4.2](25-form-settings-validation-and-events.md).

---

## MODIFY-FILLED: editing rules in an already-filled export (scenario C)

**First establish which kind of export you were handed.** Two exports of the same functional system can look
identical at the rules level yet be **different projects**: one with **no `dynamic-cruds.json`** is the
**STATIC** compiled-`@Crud` flavour (`service.crud.<alias>` resolves to a Java bean whose body is *not* in the
export — gotcha #17); one **with** `dynamic-cruds.json` carries its CRUD methods in full and is the flavour you
can actually modify end-to-end. The rules, the contexts and the rule **syntax/shape** are the same either way —
only the crud backing differs, and that decides whether a change is doable in the export at all.
(Full delta loop → [19-build-decision-procedure.md](19-build-decision-procedure.md).)

Before editing a filled export, **run `mrjun.py validate` FIRST** and treat these pre-existing findings as
**bugs to fix**, not baseline noise — a hand-grown project of any size normally ships some of each:

- **PREDICATE-missing-`return`** — expect a meaningful fraction of `PREDICATE` rules to have no top-level
  `return`; each throws `"must return Boolean"` at runtime. Fix per the triage above: prepend `return` to the
  boolean expression.
- **Mislabeled EXECUTION as `PREDICATE`** — grep the broken PREDICATE bodies for a **mutating**
  `service.crud.<alias>.<verb>()` call. A rule named like a predicate (`… Can Deactivate`) whose body is
  `service.crud.<alias>.deactivate(...)` is a state-changing call with no boolean, wrongly typed `PREDICATE`.
  Prepending `return` will **not** fix it; it should be an `EXECUTION_RULE` (action logic / on-before-complete),
  not a visibility predicate. The rest are usually genuine predicates (`status` comparisons,
  `service.actionId == …`) that only need `return`.
- **`EXECUTOR_MISMATCH`** (`ruleType` ↔ `executor` inconsistent, `validate` **errors** it,
  `validate_cmds.py`). Exports rarely ship these, but a hand edit introduces them easily — always
  re-`validate` after editing.

---

---

## Numbers in a rule — and why a failed rule says only "null"

Four of the cheapest mistakes in a rule body are also four of the most expensive to diagnose, because the
platform erases the evidence. Read this before writing any rule that multiplies, divides, rounds or
allocates.

### The reporting problem: a nested rule's failure arrives as the word "null"

`service.rule("<name>")` executes the named rule through `java.lang.reflect.Method.invoke`
(`ServiceWrapper.rule()`, `nct-executor-common`). When the nested rule throws, reflection wraps it in an
`InvocationTargetException`, and the wrapper reports **`e.getMessage()`** of *that* — which is always
`null`. So every failure inside a nested rule reaches the user as:

```
Failed to execute rule 'Outer' (…): Failed to execute Groovy script: Failed to execute rule 'Inner': null
```

The word "null" carries **no information about the cause**: it is not a NullPointerException, not a null
value, not a missing binding. The real exception is `e.getCause().getCause()` and it is not written to any
log the builder can read. Unwrap it yourself — one helper, defined once per rule that calls another:

```groovy
def CALL = { String rn ->
    try { return service.rule(rn) }
    catch (Throwable t) {
        def root = t
        int guard = 0
        while (root.cause != null && root.cause != root && guard++ < 12) { root = root.cause }
        def m = root.message
        throw new RuntimeException("rule '" + rn + "' failed: " + root.class.simpleName + (m ? ': ' + m : ''))
    }
}
```

Then `CALL("Allocate Quantities")` reports `rule 'Allocate Quantities' failed: MissingMethodException: No
signature of method: java.math.BigInteger.setScale()` instead of `null`, and the next question is obvious.

### Trap 1 — `0G` is a **BigInteger** literal, `0.0G` is a BigDecimal one

This is the one that costs a session. In Groovy `0G` is `java.math.BigInteger`; only `0.0G` is
`BigDecimal`. Mixed arithmetic promotes (`BigInteger + BigDecimal → BigDecimal`), so the wrong literal is
invisible in every expression that adds — and lethal in the one that clamps:

```groovy
def q = someBigDecimal
if (q < 0G) { q = 0G }                       // ⛔ q is now a BigInteger
return q.setScale(2, java.math.RoundingMode.HALF_UP)
//     ^ MissingMethodException: java.math.BigInteger.setScale()
```

It fires only on the branch that clamps, so a two-row fixture never reaches it, `validate` used not to see
it, and it ships. **Write every decimal literal with a decimal point: `0.0G`, `1.0G`, `100.0G`.**
`validate` now ERRORs on a bare `<n>G` in a body that does decimal work.

### Trap 2 — the only two exceptions with a `null` message are numeric

`new BigDecimal("")` and `'' as BigDecimal` throw a `NumberFormatException` whose `getMessage()` is
**null** — and combined with the reporting problem above, that is a completely blank error. Worse, the
usual guard does not cover it:

```groovy
def d = (row.qty ?: 0) as BigDecimal        // ⛔ Elvis catches '' (falsy) but NOT ' ' (truthy)
def c = new BigDecimal(ctx.getAttr('cap'))  // ⛔ an attribute is '' far more often than absent
```

Context attributes, workflow variables and form fields are empty or blank strings constantly. Route every
value through one coercion helper instead — it is also the only place `new BigDecimal(...)` is correct:

```groovy
def NUM = { v ->
    if (v == null) { return 0.0G }
    if (v instanceof BigDecimal) { return v }
    if (v instanceof Number) { return new BigDecimal(v.toString()) }
    def s = v.toString().trim()
    if (s.isEmpty()) { return 0.0G }
    try { return new BigDecimal(s) }
    catch (Exception e) { throw new RuntimeException('Expected a number, got \'' + s + '\'') }
}
```

`NUM(x)` always returns a BigDecimal, never a BigInteger, and turns garbage into a message that names the
value. `validate` WARNs on `new BigDecimal(<runtime value>)` and on `(x ?: 0) as BigDecimal` — and stays
silent once the body defines a helper that trims and defaults.

### Trap 3 — `.divide()` with one argument

`a.divide(b)` throws `ArithmeticException: Non-terminating decimal expansion` the first time the division
does not come out even (1/3, 2/7 …). Always pass a scale and a rounding mode:
`a.divide(b, 10, java.math.RoundingMode.HALF_UP)`. `validate` WARNs on the single-argument form.

### Trap 4 — a clamp breaks the total, and the total is usually the point

Any rule that distributes a fixed amount across lines — an order across items, a cost across a receipt, a
budget across departments — is written so the parts sum to the whole. Clamping a negative part to zero
**adds** to the total, so the sum silently exceeds the whole, and moving the difference onto the largest
line cannot absorb it once the surplus is bigger than that line. The shape that holds:

```
1. compute the raw parts (they sum to the whole by construction)
2. clamp the negatives to zero        → the total can now only be TOO BIG
3. if total > whole: scale every surviving part by whole/total
4. drop the parts that came out zero  (a line ordering nothing is not a line)
5. put the rounding remainder on the largest part
```

Assert it, in the rule and in the offline check: `sum(parts) == whole`, `min(part) >= 0`. A fixture with
two or three rows will satisfy the identity by accident; a real catalogue will not.

### The offline gate

`mrjun.py validate` covers all four (`_check_groovy_numeric_traps`): trap 1 as an **ERROR**, traps 2 and 3
as **WARN**s, over every rule body *and* every dynamic-CRUD GROOVY method. Comments and string literals are
stripped first, so a doc comment quoting the wrong form is never reported. What it cannot check is trap 4 —
that one is arithmetic, and it belongs in the project's own offline verifier.

---

## Gotchas

1. **Always `return` in a PREDICATE.** The template trailer `if(true){return null;}` overrides a bare
   final expression; `GroovyPredicate.apply()` will throw `"Predicate rule must return Boolean, but
   returned: null"`. The same for EXECUTION rules that must *return* a value (dropdown/fetch).
 (`ExecutionRuleTemplate.groovy`, `GroovyPredicate.java`.)
2. **PREDICATE and EXECUTION use the same template file** (`ExecutionRuleTemplate.groovy`, class
   `RuleExecutor`). The difference is only in `apply()` semantics (Boolean cast vs raw). There is no separate `PredicateTemplate`.
3. **`executor` must match `ruleType`.** `PREDICATE`↔`GroovyPredicate`,
   `EXECUTION_RULE`↔`GroovyExecutionRule`, `VALIDATION_RULE`↔`GroovyValidationRule`
   (`@ExecutorRule` in `GroovyPredicate.java`, `GroovyExecutionRule.java`, `GroovyValidationRule.java`).
4. **`context.<alias>` requires an attachment.** The context alias must be in `rule.contextIdentifiers[]`,
   otherwise `MissingPropertyException("Context '<alias>' not found...")` (`ExecutionRuleTemplate.groovy`).
   But a rule using **only** `service.crud`/`service.security`/`service.global` needs no context —
   leave `contextIdentifiers: []` (this is the norm for `RIMM_*` dropdown sources).
5. **`<crudAlias>` must be in `context.crudAliases`** (when a context is attached) — otherwise `MissingProperty`
   on the CRUD wrapper (`DynamicRuleContext.groovy`) or on `service.crud` with a context.
   Classic bug: an init rule writes `context.<ctx>.invoices` while the context lists `invoices_cruid` → fails.
6. **`data.get()` is empty if the caller didn't fill `crudDataMap[crudAlias]`.** From a form
 in CREATE mode, you need to seed an empty `CrudDataDto`, otherwise
   `RuntimeException("No CRUD data available for CRUD: <alias>")` (`DynamicRuleContext.groovy`).
   Write `data.get()?.field` in predicates that can be invoked in CREATE.
7. **contextIdentifier vs crudAlias.** The UI places the row under the `contextIdentifier` key (empty →
   under `crudAlias`) (`CrudTablePlugin.java`, `RuleExecutionServiceImpl.java`). If the control
   settings' `contextIdentifier` is not set, and the rule writes `context.<ctxAlias>.<crud>...`,
   but the data was placed under the `<crudAlias>` key, the read returns empty. Keep `contextIdentifier`
   consistent between the form settings and the rule body.
8. **`realm`/`client` are unavailable** as bare variables in a script — access throws `SecurityException`
   (`ExecutionRuleTemplate.groovy`). Available as `service.realm`/`service.client`.
9. **`service.rule("Name")` looks up by `name`, not by id** (`ServiceWrapper.java` → `findByName`).
   Keep rule names unique, otherwise the call may resolve to the wrong rule.
10. **`service.crud.<alias>.find` is a Groovy method** that internally calls the SQL methods `count`/
    `findAll` of the same CRUD via delegation; parameters (`rowsInPage`/`pageNumber`) arrive as
    `param` (`ReactorServiceImpl.groovy`, `GroovyExecutionRule.java`). Without `rowsInPage`
    pagination won't work (on SQL filters, see [11](11-business-logic-dynamic-crud.md)). **TRAP (untyped-`$1`):** for a dropdown/fetch source call
    `find([rowsInPage,pageNumber:0])` or `findAll([:])` (ALL keys absent). NEVER call the default
    multi-optional-param `findAll` with a **partial** column-filter map (e.g. `findAll([active:"true", rowsInPage])`)
    — the first unbound optional param renders as `$1 IS NULL` with no type and Postgres errors
    `could not determine data type of parameter $1`. Correct optional-filter SQL uses `IS NOT DISTINCT FROM COALESCE(:p, col)`.
11. **Compilation is cached by the SHA-256 of the body** (`AbstractGroovyExecutor.java`). Identical
    `ruleScriptStr` = one compiled class; to change behavior, change the rule text.
12. **`RuleStatus` is `ACTIVE`/`UNUSED`/`DELETED`**, NOT `INACTIVE`/`DRAFT` (older platform docs are wrong).
    `UNUSED` is a usage-scanner label, the rule remains executable (`RuleStatus.java`).
13. **Role checks — only `service.security.hasAny/AllRole(s)` and `hasAny/AllRoleGroup(s)`.** Bare
    `hasAnyRole(...)` in EXECUTION/PREDICATE does not work (`RuleExecutor.methodMissing` throws,
    `ExecutionRuleTemplate.groovy`). Bare `addError/addFieldError/...` work **only** in
    VALIDATION (`ValidationRuleTemplate.groovy`).
14. **No `service.feign(...)` / `service.localization(...)`** — older platform docs invented them.
    Use `inject('emailService')` / RIMM / `service.global` / per-locale `*Messages` maps.
15. **`param` is EXECUTION only**, `validation` is VALIDATION only. Predicates have neither.
    The `notification`/`report`/`quota` facades are built **only** for EXECUTION
    (`GroovyExecutionRule.java`); in a predicate/validation `service.notification`/`service.report`
    `service.quota` = `null`. `service.store` is **not** in that list — both members are wired by all
    three executors (`GroovyExecutorHelper.applyStore`), so they always EXIST and a store that cannot reach
    anything answers empty rather than throwing. (A `put` past a limit — key over 255 chars, value over ~64 K
    characters, nesting over 32, the 201st session key, the 501st user key for one person, a number past 38
    digits, a value that is not JSON-shaped — IS refused, naming the key. A decimal reads back a `BigDecimal`
    with its scale, a whole number an `Integer`, a date its ISO TEXT — see
    [16](16-groovy-service-api.md) §2.14 for the full table.) But
    `service.store.session` is EMPTY unless a browser session took part: in a VALIDATION rule, in a CRUD GROOVY
    method invoked directly from a page, in anything a process table evaluates or runs against a case, and in
    anything headless. `service.store.user` is empty only where there is no acting user.
    [16](16-groovy-service-api.md) §2.14.
16. **`attrs` is a `Map<String,JsonNode>`.** Don't compare a JsonNode directly — extract:
    `attrs.filterBy?.asText()`, `attrs._crudEntityId?.asText()`. Known keys (illustrative, not
    exhaustive): `filterBy`, `rowsInPage`, `pageNumber`, `processIdentifier`, `_crudAlias`,
    `_crudEntityId`, `__actionId`, `__actionName`. There is **no** `entityId` and **no**
    `processInstanceId` attr — the process id is `attrs.processIdentifier`, the edited row's id is
    `attrs._crudEntityId`; the invented names read back `null` silently.
17. **Static vs dynamic.** In a STATIC project `service.crud.<alias>.<m>()` resolves over RSocket to
    the compiled `@Crud` bean of that microservice — the rule alone suffices, but the business method
    is not in the export (it's in the code). In a dynamic project the target method is described in `dynamic-cruds.json`
    (`methods[]`) and is **exported in full** — see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).
    The rule syntax is identical for both styles.
18. **The rule's `transient` fields** (`message`,`errors`,`id`) are `null` in the export; on import
    identity is held by `identifier`, not by `id`.
19. **Guard-with-message = `throw` from an EXECUTION rule.** `throw new RuntimeException("msg")` in an
    EXECUTION rule (action logic / `onBeforeStart` / `onBeforeComplete`) aborts the action and shows `msg` as an
    error toast (`CrudTablePlugin.java`). A PREDICATE cannot show a message or abort — it only
    hides/disables the button. See §"Aborting an action with a message (`throw`)".
