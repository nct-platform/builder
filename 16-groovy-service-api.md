# 16 — Full Groovy `service.*` capability surface (what you can actually do in a script)

> 📐 **Field evidence — which service calls are load-bearing:** [03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md) · [06-security-and-roles.md](references/06-security-and-roles.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What this is / when to use

[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) describes the **rule types** (`PREDICATE`/`EXECUTION_RULE`/`VALIDATION_RULE`),
their templates and the **context model** (`context.<ctx>.<crud>.data.get()`). This document answers a different question:
**what operations are available at all inside a Groovy script** — the entire set of bindings and `service.*` namespaces,
with real method signatures, backing classes and worked examples. This is the "capability surface":
a reference for "are all the Groovy capabilities accounted for".

Open this document when you write **any** `rule.ruleScriptStr` or a GROOVY method of a dynamic CRUD
(`dynamic-cruds.json.cruds[].methods[].script`, see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md))
and need to know: how to call a CRUD method, how to convert a list into dropdown options, how to check a role, how to
send a notification/email/PDF, how to invoke another rule, how to read the enum registry, and so on.

> **The single authoritative source of the API** is the **hints tree**, which the server assembles in
> `HintsService.buildRuleHints(...)` (`HintsService.java`).
> This exact structure feeds the rule editor's autocomplete (endpoint
> `POST /api/hints/tenant/{realm}/{client}/getRuleHints`,
> `HintsController.java`
> and the MCP tool `HintsMcpTools.getRuleHints`,
> `HintsMcpTools.java`). The entire §"service.\*" below is
> a direct breakdown of this assembly. If something is not in the hints tree and not in the backing class `ServiceWrapper` — it does not exist
> in the language (see §"What is NOT there").

> **🔧 Tooling.** This document is a **language reference**, not a reference for an export entity; there is no separate
> `mrjun.py` command for the "capability surface". The rules themselves are created via
> `mrjun.py rule add --name … --type … --context … --script @f` (see
> [tools/README.md](tools/README.md) and [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md));
> GROOVY methods of a CRUD — via `crud add-method … --type GROOVY --rule <id>`
> ([11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)). The script content (`@f`) is written
> by hand from this reference.

> Related documents: [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) (rule types + context model),
> [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md) (how the hints tree becomes
> autocomplete and how server-hints differ from live-context-hints),
> [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) (`service.crud.<alias>` resolves to
> a CRUD method; delegated GROOVY methods), [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)
> (`service.rimm.*` hits saved queries; mailTemplates),
> [15-pdf-and-mail.md](15-pdf-and-mail.md) (`service.report.pdf.*` and
> `service.notification.*` in detail — PDF templates, mail templates, push),
> [02-form-controls-reference.md](02-form-controls-reference.md) and [04-crud-table-plugin.md](04-crud-table-plugin.md)
> (who calls a rule and with which `attrs`).

---

## Part 1 — Rule bindings

The Groovy script from `rule.ruleScriptStr` is spliced into the template's `execute()` at the `{{RULE_SCRIPT}}` placeholder
(`ExecutionRuleTemplate.groovy`). Before that, the runtime places a set of variables into the binding via
`prepareContextDataMap()` (`GroovyExecutionRule.java`). The full list of what the script "sees":

| Binding | Type / backing | What it is | Where it is set |
|---|---|---|---|
| `context` | `DynamicRuleContext` (via `def context = this` in the template) | The entry point into the context model: `context.<ctxAlias>.<crudAlias>.data.get()`, `context.<ctx>.data.getAttr(...)`, `context.data.*` (global attrs). Full breakdown — [08](08-groovy-rules-and-context.md). | `ExecutionRuleTemplate.groovy`; `propertyMissing` delegation → `dynamicContext` |
| `service` | `ServiceWrapper` | The main capability namespace — all of Part 2. | `GroovyExecutionRule.java` |
| `param` | `Map<String,Object>` | Parameters of a **delegated** GROOVY method of a CRUD. Populated from the `__methodParams` marker, which `ReactorServiceImpl.executeDelegatedRule` places (`ReactorServiceImpl.groovy`). Outside delegation — an empty map `[:]`. | `GroovyExecutionRule.java` |
| `attrs` | `Map<String, JsonNode>` (Jackson) | Arbitrary attributes passed by the caller: CRUD-table pagination/filters (`rowsInPage`, `pageNumber`, filter keys), `processIdentifier`, `__actionId`/`__actionName`, `filterBy`, etc. **Values are `JsonNode`**, so they are read as `attrs.get('rowsInPage')?.asInt()`, `attrs.get('filterBy')` (text). | `GroovyExecutionRule.java` |
| `contextIdentifiers` | `List<String>` | Identifiers of the contexts bound to the rule (`rule.contextIdentifiers`). | `GroovyExecutionRule.java` |
| `contextDataMap` | `Map<String, ContextData>` | Low-level access to context-data (normally you use `context.*` instead). | `GroovyExecutionRule.java` |
| `userId` | `String` | ID of the current user (see also `service.security.user()`). realm/client are **hidden** deliberately. | base — `GroovyExecutorHelper.createBaseContextDataMap` |
| `data` | `GlobalDataWrapper` | Alias for `context.data`: `data.getAttr("k")`, `data.setAttr("k", v)`, `data.foo` (read) / `data.foo = v` (write). | `ExecutionRuleTemplate.groovy` → `dynamicContext.data` (`DynamicRuleContext.groovy`) |
| `currentData` | `CrudDataDto` \| `null` | The current item of a **nested** form (List-item): `currentData.get()`, `currentData.put(obj)`, `currentData.setField('a.b', v)`, `currentData.getField('col', Type.class)`, `currentData.hasField('col')`. In the parent form — `null`. ⚠️ `currentData.getAttr(...)`/`setAttr(...)` are offered by the editor's autocomplete but do **NOT** exist on `CrudDataDto` — calling them throws `MissingMethodException`. Attributes live on the context/global scopes (`context.<ctx>.data.getAttr` / `context.data.getAttr`), never on a CRUD-data node. | `ExecutionRuleTemplate.groovy` |
| `validation` | `ValidationResultCollector` | **Only in VALIDATION_RULE.** Accumulator of errors/warnings. | `ValidationRuleTemplate.groovy` (the `validation` field) |
| `addError` / `addWarning` / `addFieldError` / `addFieldWarning` | template methods | **Only in VALIDATION_RULE.** Delegate to `validation.*` (see Part 3). | `ValidationRuleTemplate.groovy` |
| `inject(String beanName)` | template method | Restricted access to Spring beans. **Security-gated**: `contextService/reactorService/ruleService/crudReactor` are blocked in `inject` itself (`realm`/`client` are not beans, and are not accessible separately via `propertyMissing`, see the Security invariant below); a whitelist is allowed (`emailService`, `notificationService`, `validationService`, `calculationService`, `formatterService`, `dateService`) + any bean matching `*Helper`/`*Util`; `rimmService` → returns `service.rimm`. | `ExecutionRuleTemplate.groovy` |

> **Security invariant.** `realm` and `client` are **inaccessible** to the script: accessing them throws
> `SecurityException` (`ExecutionRuleTemplate.groovy`). All `service.*` proxies (rimm/security/notification/crud)
> already know realm/client internally and substitute them themselves — so in the script you **do not pass** them, even though the hints
> for `service.rimm.query(...)` formally have `realmName/clientName` in the signature (that is the signature of the underlying
> `RimmService`, while the `RimmServiceProxy` proxy overrides the 1-/2-arg variants without realm/client).

> **⚠️ Caveat — the `inject()` block-list is not the only path.** `ServiceWrapper` is class-level `@Getter`
> (`ServiceWrapper.java`), so **every** field is a reachable Groovy property — including `service.ruleService`
> `service.ruleExecutorReactor` and `service.contextData` (`ServiceWrapper.java`), all populated in
> the constructors used by every executor. `service.ruleService` hands back the **same** raw `RuleService` bean that
> `inject("ruleService")` refuses with `SecurityException`, and `service.ruleExecutorReactor`/`service.contextData`
> likewise reach the raw rule-execution reactor / `ContextDataDto`. So the `inject()` block-list only guards the
> `inject()` path, not these getters — the "these beans are blocked" framing holds for `inject()` alone. Do not
> call them: for rule reuse use `service.rule("Name")` (§2.10); the raw beans are internal, unsupported surface.

### `filter` is NOT a binding

You will often encounter `def filter = [ ... ]` in fetch rules (see the "Find — …" example below). This is a
**local variable** that the script assembles itself from `attrs`, not a runtime injection. The only same-named
`filter` in hints is the subgroup `service.global.collection.filter.*` (list-filtering utilities,
Part 2 §global). Do not confuse them.

---

## Part 2 — `service.*` namespaces

`service` is a `ServiceWrapper` (`ServiceWrapper.java`). Its fields and sub-proxies:

```
service
 ├─ crud          → service.crud.<alias>.<method>(args)      (ServiceCrudLookup/Invoker)
 ├─ global        → service.global.<group>.<fn>(args)         (GlobalFunctionsWrapper ← YAML + REST)
 ├─ security      → service.security.user()/hasAny…()         (SecurityHelper)
 ├─ rimm          → service.rimm.query(...)/run(...)          (RimmServiceProxy)
 ├─ notification  → .push.send…() / .mail.<alias>(...)        (NotificationWrapper → PushNotificationProxy + MailNotificationProxy)
 ├─ report        → service.report.pdf.get/download/email/push (ReportWrapper → PdfReportProxy)
 ├─ access        → service.access.addRoleAccess(...)…         (AccessManager)
 ├─ quota         → service.quota.mail.allowedPerDay…          (QuotaProxy)
 ├─ enums         → service.enums['Name'].list()               (EnumsWrapper)
 ├─ workflow      → .start(id, ctx[, opts]) · .list / .actions / .startActions
 │                  .contextData / .complete                    (WorkflowProxy)
 ├─ store         → .session.get/put(...) · .user.get/put(...)  (RuleStoreProxy → KeyValueStore ×2)
 ├─ rule(name)    → service.rule("Other Rule")                 (ServiceWrapper.rule)
 ├─ redirectPage  → service.redirectPage("alias/page")          (ServiceWrapper.redirectPage) EXECUTION only
 ├─ actionName    → String | null                             (which action button was pressed — localized name)
 └─ actionId      → String | null                             (stable id of the action button)
```

**Where the weight actually falls.** Audit a working project (`jq -r '.rules[].rule.ruleScriptStr' rep-objects.json`
→ grep `service.<ns>`) and the distribution is always the same shape: `service.crud.*` dominates, then
`service.global.conversion` (every dropdown ends in one), then `service.security.user`/`hasAnyRoleGroup`,
then a thin tail — `service.actionId`, `service.rimm.run`, `service.notification.push`, `service.rule(`.
The namespaces `access`/`quota`/`enums`/`report`/`store` are frequently used **zero** times in a given project
yet are fully present in the hints tree and at runtime — absence from a codebase is not absence from the
language.

---

### 2.1 `service.crud.<alias>.<method>(args)` — calling a CRUD method

The most frequent way to perform a business operation. `service.crud.<alias>` is resolved via `ServiceCrudLookup`
(`DynamicRuleContext.groovy`): when a context is **bound**, `alias` must be in the `crudAliases` of one of the
contexts; when **no** contexts are present — it is resolved across the entire CRUD registry of the realm/client
(`DynamicRuleContext.groovy`). Then `.<method>(args)` goes to `ServiceCrudInvoker.methodMissing`
→ `reactorService.executeCrudMethod(realm, client, alias, method, params, headers)`
(`ReactorServiceImpl.groovy`) over RSocket into the integration.

**Which `method`** values are available — those are the `methods[]` of the specific CRUD in `dynamic-cruds.json` (the standard set
`find`/`findAll`/`count`/`get`/`create`/`update`/`delete` + custom ones), see
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md). In hints they arrive via
`buildCrudServiceMethods` (`HintsService.java`), which makes the RSocket call `getServiceMethods`.

- **The argument** is usually a Groovy map (`[rowsInPage, pageNumber: 0]`) or a scalar id.
- **`find`** (GROOVY method) returns a page: `{content, totalElements, totalPages, pageNumber}` — see its
  implementation from the export below.
- **`create`/`update`** accept a DTO map; **`delete`** — an id.
- `context.<ctx>.<alias>.service.<method>(args)` — the **equivalent** context-dependent syntax (the same
  `executeCrudMethod`), see `DynamicRuleContext.groovy`. `service.crud.<alias>` is shorter and preferred.

**Worked example** — a dropdown source (rule `RIMM_counterparties_cruid`):

```groovy
def list = service.crud.counterparties_cruid.find([
  rowsInPage: 1000,
  pageNumber: 0
])
return service.global.conversion.toSelectOptionsLocalized(list, "id", "name")
```

**Worked example** — action logic (`Bill of Materials Activate`):

```groovy
def bom = context.erp_context.bill_of_materials.data.get()
if (!bom.lines) {
    throw new RuntimeException("Add at least one component before activating")
}
service.crud.bill_of_materials.activate(bom.id)
```

> **Guard-with-message (abort + toast).** The `throw` above is the load-bearing idiom, not incidental. A
> `throw new RuntimeException("<msg>")` inside an **EXECUTION_RULE** (action logic / `onBeforeStart` /
> `onBeforeComplete`) **aborts the operation** and surfaces `<msg>` to the user as an **error toast** — the
> CRUD-table UI shows the rule error verbatim via `err.getMessage()`
> (`nct-ui/.../plugin/crud/CrudTablePlugin.java` before-start, before-complete; create-flow;
> catch-all wraps it). This is the **only** way to block an action *with a message*: a **PREDICATE** can
> only hide/disable the button (returns a Boolean, shows nothing, aborts nothing). Written as-typed, so make `<msg>`
> user-facing. Expect several per project — in practice one on nearly every action that posts, submits, approves
> or activates a document ("Add at least one line before posting", "Attach the signed contract before approving").
> See [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) §"Aborting an action with a message".

**Worked example** — the implementation of a `find` GROOVY method of a dynamic CRUD
(`dynamic-cruds.json.cruds[].methods[].script`; `param` — from delegation):

```groovy
def filter = param ?: [:]
def countResult = service.crud.shipment_event_types_cruid.count()
def total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long
def rows = service.crud.shipment_event_types_cruid.findAll(filter) ?: []
def rowsInPage = (filter.rowsInPage ?: 0) as int
def pageNumber = (filter.pageNumber ?: 0) as int
return [
    content: rows,
    totalElements: total,
    totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,
    pageNumber: pageNumber
]
```

> **⚠️ `findAll` partial-map trap.** Here `findAll` receives the **full** delegated param map (pagination +
> forwarded filters) and the result is wrapped into a **page map** — it is *not* dropdown options. Two cautions
> when lifting this shape: (1) a dropdown/autocomplete source must additionally pipe the rows through
> `toSelectOptions*`/`toAutoCompleteOptions` — never return the raw list; (2) never hand-build a **PARTIAL**
> column-filter map for `findAll` (e.g. `findAll([active:"true"])`) — the first unbound optional param renders as
> `$1 IS NULL` with no type and Postgres errors `could not determine data type of parameter $1`. Use `find(...)`
> (pagination-only) or `findAll([:])` (all keys absent). See [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

**Worked example** — a CRUD-table fetch rule that assembles `filter` from `attrs` (`Find — Bill of Materials`):

```groovy
// Pagination + filter values arrive from the table via attrs (Jackson JsonNode).
def filter = [
    'rowsInPage': attrs?.get('rowsInPage')?.asInt(),
    'pageNumber': attrs?.get('pageNumber')?.asInt()
]
// Forward any other filter values (filter form + configured filters):
attrs?.each { k, v ->
    if (k != 'rowsInPage' && k != 'pageNumber' && v != null && !v.isNull()) {
        filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText())
    }
}
//   filter['assignedTo'] = service.security.user().id
return service.crud.bill_of_materials.find(filter)
```

> **Static vs dynamic.** In `service.crud.product.find(...)` on a **static** project, `product` resolves
> to a compiled Java `@Crud` bean (`ProductCrud`); on a **dynamic** one — to the `methods[]` from
> `dynamic-cruds.json`. The call syntax is identical; see [11](11-business-logic-dynamic-crud.md).

---

### 2.2 `service.global.*` — utility library (YAML functions + REST)

`service.global` is a `GlobalFunctionsWrapper`, built from the hierarchy `GlobalFunctionsService.functionHierarchy`
(`GroovyExecutionRule.java`). Each function is a Groovy closure, compiled from
`globalFunctions.yaml` at startup (`GlobalFunctionsService.java`). Plus
a REST client is post-registered. **This is a server-editable catalog** — the exact list = the contents of the
YAML. The full current catalog (verbatim from `globalFunctions.yaml`):

| Path | Signature (params → returns) | Purpose |
|---|---|---|
| `service.global.locale.getKey` | `() → String` | Session locale key (`en_US`, `ru_RU`). |
| `service.global.locale.getLocale` | `() → Locale` | Session `java.util.Locale`. |
| `service.global.conversion.toSelectOptions` | `(Object result, String keyField, String displayField) → List` | CRUD result/list → key-value list for a **dropdown**. |
| `service.global.conversion.toSelectOptionsLocalized` | `(Object result, String keyField, String displayField, String localeKey=null, String localizationFieldName='localize') → List` | Same + localized `display` (fallback to the base field). |
| `service.global.conversion.toAutoCompleteOptions` | `(Object result, String field) → List` | List → suggestions for **autocomplete** (single field). |
| `service.global.conversion.toAutoCompleteOptionsLocalized` | `(Object result, String field, String localeKey=null, String localizationFieldName='localize') → List` | Same + localization. |
| `service.global.conversion.toMap` | `(List list, String keyField) → Map` | List → map by key field. |
| `service.global.validation.isEmail` | `(String value) → Boolean` | E-mail format. |
| `service.global.validation.isNotBlank` | `(String value) → Boolean` | Not null/empty/whitespace. |
| `service.global.validation.isNumeric` | `(String value) → Boolean` | Digits only (`-?\d+(\.\d+)?`). |
| `service.global.validation.isInRange` | `(Number value, Number min, Number max) → Boolean` | In range (inclusive). |
| `service.global.formatting.date.format` | `(Date date, String pattern) → String` | Date formatting (`SimpleDateFormat`). |
| `service.global.formatting.date.parse` | `(String dateString, String pattern) → Date` | Parse a string into a date. |
| `service.global.formatting.date.now` | `() → Date` | Current date/time. |
| `service.global.formatting.date.addDays` | `(Date date, int days) → Date` | Add days. |
| `service.global.formatting.number.formatCurrency` | `(Number amount, String currencyCode) → String` | As currency. |
| `service.global.formatting.number.formatPercent` | `(Number value) → String` | As percent (0.5 → 50%). |
| `service.global.formatting.number.round` | `(Number value, int decimals) → Number` | Round to N decimals. |
| `service.global.formatting.text.capitalize` | `(String value) → String` | First letter uppercase. |
| `service.global.formatting.text.truncate` | `(String value, int maxLength, String suffix) → String` | Truncate + suffix. |
| `service.global.collection.filter.byField` | `(List list, String fieldName, Object value) → List` | Filter by field value. |
| `service.global.collection.filter.notNull` | `(List list) → List` | Remove `null`. |
| `service.global.collection.filter.byCondition` | `(List list, Closure condition) → List` | Filter by closure. |
| `service.global.collection.transform.pluck` | `(List list, String fieldName) → List` | Extract a single field from each. |
| `service.global.collection.transform.groupBy` | `(List list, String fieldName) → Map` | Group by field. |
| `service.global.collection.transform.sortBy` | `(List list, String fieldName, boolean ascending) → List` | Sort by field. |
| `service.global.collection.transform.unique` | `(List list, String fieldName) → List` | Unique by field. |
| `service.global.collection.aggregate.sum` | `(List list, String fieldName) → Number` | Sum of a field. |
| `service.global.collection.aggregate.avg` | `(List list, String fieldName) → Number` | Average of a field. |
| `service.global.collection.aggregate.count` | `(List list, String fieldName, Object value) → Integer` | Count where field == value. |
| `service.global.rest.get` / `post` / `put` / `delete` / `patch` / `head` / `options` | `(String url)` or `(String url, Map options) → RestResponse` | HTTP calls (see below). |

> **Choices-rule terminal call.** For **any** choices rule (dropdown / tree-picker / autocomplete source) the
> **last statement** must be one of these four conversions — the raw CRUD result is never a valid return. Match
> the function to the control: `toSelectOptions*` for dropdowns and tree pickers, `toAutoCompleteOptions*` for
> autocomplete; use the `*Localized` variant when the display column is localized. Full contract:
> [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

**`toSelectOptions*` — output format.** They return a "flat" list of pairs `[[key:keyField, value:...],
[key:displayField, value:...], ...]` — 2 elements per row of the source data (`globalFunctions.yaml`).
This is exactly the format that dropdown controls expect. The `Localized` variants read the localized value from
`item[localizationFieldName][displayField][localeKey]` with a fallback to the base field; the default locale
is taken from `LocaleContext` (the session).

> **⚠️ INVARIANT — a choices rule MUST return this pair-list.** A dropdown / tree-picker / autocomplete choices
> rule MUST end by returning this converted pair-list as its **final statement**. Returning the raw entity list
> from `find`/`findAll` (e.g. `return service.crud.X.findAll([...]) ?: []`) makes the control render
> **"No results found"** AND hides its **Show Nav** affordance — a silent failure (`validate` now errors on it).
> Dropdown / tree → `toSelectOptions(list,"<key>","<display>")` (localized display column →
> `toSelectOptionsLocalized`); autocomplete → `toAutoCompleteOptions(list,"<display>")`. Full recipe:
> [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

**`service.global.rest.*`** — an HTTP client registered in `registerRestClient()`
(`GlobalFunctionsService.java`), backing — `RestClientWrapper`
(`RestClientWrapper.groovy`). The response
`RestResponse` has fields: `status` (int), `ok` (boolean), `body` (parsed JSON Map/List **or** String),
`text` (raw String), `headers` (Map) — see the descriptions in `buildRestHints` (`GlobalFunctionsService.java`).
`options` map: `[headers: [...], body: [...], query: [...], timeout: 30000]` — `timeout` is in
**milliseconds**; omitted it defaults to 30 000 ms and a larger value is capped at 120 000 ms.
Further built-in limits (response size, blocked private/link-local addresses) live in
`RestClientConfig`; treat the numbers as shipped defaults, not a contract.

**Worked example** (`invoice statuses dropdown`):

```groovy
def list = context.finance_context.invoice_statuses_cruid.service.find([
  rowsInPage: 1000,
  pageNumber: 0
])
return service.global.conversion.toSelectOptionsLocalized(list, "id", "statusName")
```

---

### 2.3 `service.security.*` — current user and roles

Backing — `SecurityHelper` (`SecurityHelper.java`), realm/client/userId already inside.

| Method | Signature | Return / behavior |
|---|---|---|
| `service.security.user()` | `CurrentUser user()` | An object `{id, email, firstName, lastName}` (`SecurityHelper.java`) — simply assembles `CurrentUser` from already-stored fields, does no look-up/cache itself. The `firstName/lastName` fields are populated by the runtime **higher up the stack**, when constructing `SecurityHelper`. |
| `service.security.hasAnyRole(...)` | `boolean hasAnyRole(String... roles)` | true if the user has **at least one** of the roles. |
| `service.security.hasAllRoles(...)` | `boolean hasAllRoles(String... roles)` | true if they have **all** roles. |
| `service.security.hasAnyRoleGroup(...)` | `boolean hasAnyRoleGroup(String... roleGroups)` | true if they have **at least one** role-group. |
| `service.security.hasAllRoleGroups(...)` | `boolean hasAllRoleGroups(String... roleGroups)` | true if they have **all** role-groups. |

> All checks are **fail-closed**: if securityClient/userId/realm/client are not set — they return `false`
> (`SecurityHelper.java`) rather than throwing.

> **You cannot list a user's roles.** `SecurityHelper` exposes only `user()` + the four `hasAny/All*` boolean
> checks (`SecurityHelper.java`) — there is **no** `roles()`/`roleGroups()`/`getRoles()`. To branch on a
> role you must **test** membership by name (`service.security.hasAnyRoleGroup("X")`) per candidate; the natural
> guess `service.security.roles()` does not exist.

**Worked example** — a visibility predicate (`Is Compliance Head`):

```groovy
return service.security.hasAnyRoleGroup("Compliance Head") || service.security.hasAnyRoleGroup("Author")
```

**Worked example** — `user()` in an init rule (`Invoice Init`):
`inv.createdBy = service.security.user().email`.

---

### 2.4 `service.rimm.*` — running saved queries (RIMM)

Backing — `RimmServiceProxy` (`RimmServiceProxy.java`); hits the saved `queries[]` from
`rep-objects.json` (see [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)).
realm/client are substituted by the proxy automatically.

| Method | Signature (in the script) | Purpose |
|---|---|---|
| `service.rimm.query(name)` | `List query(String queryName)` | Query by name without parameters (`RimmServiceProxy.java`). |
| `service.rimm.query(name, params)` | `List query(String queryName, Map<String,Object> parameters)` | Query by name with parameters. |
| `service.rimm.query(requestMap)` | `List query(Map<String,Object> requestMap)` | Query via a map config. |
| `service.rimm.run(request)` | `List run(QueryByNameRequest request)` | Run via a DTO request. |
| `service.rimm.run(requestMap)` | `List run(Map<String,Object> requestMap)` | **The most frequent** — run via a map. |

The `run`/`query` map form accepts the keys `name`, `itemsPerPage`, `parameters:[...]` (see the example).

**Worked example** (`All_users`):

```groovy
return service.rimm.run([
	name: "rimm_all_users",
  	itemsPerPage: 100,
	parameters: [:]
])
```

**Worked example with a parameter from `attrs`** (`Rimm Counterparty`):

```groovy
return service.rimm.run(
    [
        name: "Rimm Counterparty Start With",
        itemsPerPage: 100,
        parameters: [counterparty: attrs.get('filterBy')]
    ]
);
```

> **This is the search-term wiring for a `searchEnabled` dropdown/autocomplete, not a complete one.**
> `attrs.get('filterBy')` carries the user's typed term; the RIMM result must still be piped through
> `service.global.conversion.toSelectOptions(list,"<key>","<display>")` (autocomplete → `toAutoCompleteOptions`).
> For the CRUD-side platform pipeline (`acFindAllBy<Cap(X)>Like` SQL method + `acFindBy<Cap(X)>Like` Groovy wrapper +
> rule `RIMM_FILT_<alias>_<X>`) see [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

> Cross-capability: **RIMM query → dropdown.** `service.rimm.run([...])` returns a list; pass it to
> `service.global.conversion.toSelectOptions(list, "key", "display")` — you get dropdown options.

---

### 2.5 `service.notification.*` — push and e-mail

Backing — `NotificationWrapper` (`NotificationWrapper.java`): two sub-namespaces `push` and `mail`. A detailed
breakdown (email templates, severity, storage) — [15-pdf-and-mail.md](15-pdf-and-mail.md).

#### `service.notification.push.*` — `PushNotificationProxy` (`PushNotificationProxy.java`)

**To a single user (by e-mail):**

| Method | Signature | Severity / behavior |
|---|---|---|
| `sendText` | `void sendText(String userEmail, String message)` | Plain text. |
| `sendAlert` | `void sendAlert(String userEmail, String title, String message)` | INFO. |
| `sendWarning` | `void sendWarning(String userEmail, String title, String message)` | WARNING. |
| `sendError` | `void sendError(String userEmail, String title, String message)` | ERROR. |
| `sendReminder` | `void sendReminder(String userEmail, String title, String description, LocalDateTime dueDate)` | Reminder with a date. |
| `sendDownloadable` | `void sendDownloadable(String userEmail, String message, String fileName, String downloadUrl)` | Text + a clickable file (used by PDF-push). |

**Broadcast to a role-group** (return `int` — how many were sent):
`sendTextToRoleGroup(roleGroupName, message)`, `sendAlertToRoleGroup(roleGroupName, title, message)`
`sendWarningToRoleGroup(...)`, `sendErrorToRoleGroup(...)`
`sendReminderToRoleGroup(roleGroupName, title, description, dueDate)`.

**Broadcast by role** (return `int`):
`sendTextToRole(roleName, message)`, `sendAlertToRole(...)`, `sendWarningToRole(...)`
`sendErrorToRole(...)`, `sendReminderToRole(roleName, title, description, dueDate)`.

> ⚠️ **A broadcast to a role GROUP is a copy of the news, never the work item.** A role group is a queue of
> people; if the message tells them that something is waiting for them to act on, the thing they are supposed
> to act on does not exist yet. That is a CASE — `service.workflow.start` (§2.12) into a worklist somebody
> clears — and the push is at most its notification. Sending only the push leaves the work in an inbox nobody
> can filter, assign or close. Recognition test and the whole chain →
> [27](27-event-driven-process-start.md); the inventory row that decides it →
> [19](19-build-decision-procedure.md) Phase 1a.

**Worked example** (`Send Intake Notification`) — the FYI half of a case a rule has already opened, not a
substitute for it:

```groovy
def pid = service.workflow.start(reviewWorkflowId, ctx, [
    groupIdentifier: complianceGroupId, roleGroups: ['Compliance Head'],
    businessKey: 'INT-' + intakeNumber])                    // the work item: §2.12
service.notification.push.sendAlert(service.security.user().email, 'Intake registered',
    'Your intake has been registered and is awaiting review')     // to the submitter — pure FYI
service.notification.push.sendAlertToRoleGroup('Compliance Head', 'Intake ' + intakeNumber + ' registered',
    'The review case is on your worklist')                        // points AT the case, does not replace it
```

> Cross-capability: **notify a role on an event.** Attach an EXECUTION rule with
> `service.notification.push.sendAlertToRoleGroup('<RoleGroup>', title, msg)` to an event-mapping / on-before-complete
> action (see [04](04-crud-table-plugin.md), [06](06-form-groups-and-mapping.md)). `service.security.user().email`
> gives you the "self" recipient. If the event is "somebody now has to decide/review/act", the rule owes a
> `service.workflow.start` first and the push second — the warning above.

#### `service.notification.mail.<alias>(...)` — `MailNotificationProxy` (`MailNotificationProxy.groovy`)

A dynamic proxy: **the method name = the alias of the mail template** (via `methodMissing`). Two signatures:

```groovy
// with the template's default subject:
service.notification.mail.<alias>(List<String> recipients, Map<String,String> placeholders)
// with a custom subject:
service.notification.mail.<alias>(List<String> recipients, String subject, Map<String,String> placeholders)
```

`placeholders` — a map of template placeholders. The aliases arrive from `mailTemplateFeignClient.getAliasInfo`
and land in hints (`HintsService.java`). The list of a project's mail templates — `rep-objects.mailTemplates`
(a fresh empty starter already ships a handful of account-lifecycle ones), see
[12](12-queries-sources-schedulers-and-rest.md).

Example call forms (from the backing class's javadoc, `MailNotificationProxy.groovy`):

```groovy
service.notification.mail.welcomeEmail(["user@example.com"], [firstName: "John", lastName: "Doe"])
service.notification.mail.welcomeEmail(["user@example.com"], "Custom Subject", [firstName: "John"])
```

---

### 2.6 `service.report.pdf.*` — generating PDFs from templates

Backing — `ReportWrapper` (`ReportWrapper.java`) → `PdfReportProxy`
(`PdfReportProxy.groovy`). Wired in by a post-constructor (`GroovyExecutionRule.java`). Full breakdown of
PDF templates and fields — [15-pdf-and-mail.md](15-pdf-and-mail.md). Four
sub-namespaces:

| Call | Signature | What it does |
|---|---|---|
| `service.report.pdf.get.<alias>(fileName, params)` | `PdfReferenceDto get.<alias>(String fileName, Map<String,Object> params)` | Prepares a `PdfReferenceDto` for the `<alias>` template; `params` — template fields (`PdfReportProxy.groovy` inner `PdfTemplateGetProxy`). Aliases — from the project's PDF templates. |
| `service.report.pdf.download(fileName, pdfs)` | `void download(String fileName, List<PdfReferenceDto> pdfs)` | **Asynchronous, fire-and-forget**: queues a Kafka download request; nct-pdf renders + merges the PDFs into one and POSTs the bytes into the per-user inbox file-storage; a UI poller picks it up and opens the browser save dialog (~10 s). The `byte[]` is **not** returned. |
| `service.report.pdf.email.<mailAlias>(recipients, [subject,] placeholders, pdfs)` | `void` | An email by the mail template `<mailAlias>` with PDF attachments (`PdfMailDispatcher`). |
| `service.report.pdf.push.send…(…, pdfs)` | like push, + `List<PdfReferenceDto> pdfs` as the last argument | A push notification with a PDF attachment: `sendText/sendAlert/sendWarning/sendError/sendReminder` + `*ToRole`/`*ToRoleGroup` (`PdfPushDispatcher`). |

The form from hints (`HintsService.java`): attachments are built as a list of `PdfReferenceDto`, for example
`[ service.report.pdf.get.<alias>("<alias>.pdf", [:]) ]`.

> Cross-capability: **PDF from a template → e-mail.** A single call:
> ```groovy
> def ref = service.report.pdf.get.invoice("invoice.pdf", [orderNo: order.id, total: order.total])
> service.report.pdf.email.invoiceMail(["client@example.com"], [name: order.customer], [ref])
> ```
> — generate a PDF and attach it to an email by a mail template (see [15](15-pdf-and-mail.md)).
> Projects often use `service.report.*` nowhere in their scripts; the namespace is active regardless, so treat
> "nobody here calls it" as a gap to exploit, not evidence it is unavailable.

---

### 2.7 `service.access.*` — process access management

Backing — `AccessManager` (`AccessManager.java`); operates on the `AccessDto` of the current process (processId from
`attrs.processIdentifier`, `GroovyExecutionRule.java`). Relevant for the workflow/process context
([07-workflows-and-tasks.md](07-workflows-and-tasks.md)).

| Method | Signature | Purpose |
|---|---|---|
| `addRoleAccess` | `boolean addRoleAccess(String roleName)` | Grant access to a role. |
| `removeRoleAccess` | `boolean removeRoleAccess(String roleName)` | Revoke. |
| `hasRoleAccess` | `boolean hasRoleAccess(String roleName)` | Check. |
| `getRoleAccesses` | `List<String> getRoleAccesses()` | All roles with access. |
| `addRoleGroupAccess`/`removeRoleGroupAccess`/`hasRoleGroupAccess`/`getRoleGroupAccesses` | as above, for a role-group |. |
| `addUserAccess`/`removeUserAccess`/`hasUserAccess`/`getUserAccesses` | `String userEmail` |. |
| `removeOwnerAccess`/`restoreOwnerAccess` | `int (…)()` | Disable/enable owner access. |
| `clearAllAccess` | `void clearAllAccess()` | Remove all entries. |
| `getAccessCount` | `int getAccessCount()` | Number of entries. |
| `hasAnyAccess` | `boolean hasAnyAccess()` | Whether there are any entries. |

---

### 2.8 `service.quota.*` — project limits (read-only)

Backing — `QuotaProxy` (`QuotaProxy.java`). Read-only; `allowed*` may be `null` (no limit).

```
service.quota.mail.allowedPerDay      // Integer | null
service.quota.mail.usedToday          // int
service.quota.processes.allowed       // Integer | null
service.quota.processes.active        // long
service.quota.users.allowed           // Integer | null
service.quota.users.current           // long
service.quota.schedulers.allowed      // Integer | null
service.quota.schedulers.current      // long
```

(hints — `HintsService.java`; field types are defined in the `QuotaProxy` static classes.)

---

### 2.9 `service.enums['Name'].list()` — the project's enum registry

Backing — `EnumsWrapper` (`EnumsWrapper.java`), a snapshot of the registry is taken once per rule run
(`GroovyExecutionRule.java` → `GroovyExecutorHelper.buildEnumsWrapper`). Access both via brackets and via
a property:

```groovy
def rows = service.enums['OrderStatus'].list()   // bracket form (EnumsWrapper.getAt)
def rows = service.enums.OrderStatus.list()       // property form (propertyMissing)
```

`list()` (`EnumsWrapper.java`) → `List<Map<String,Object>>`, one row per constant. Only the `name` key is
guaranteed to be present (via `putIfAbsent`); the other keys (e.g. `displayName`
`intCode` for an INTEGER-enum) + any extra fields are taken via `putAll(entry.getValue())` and are in the row
only if they are set in the enum registry. `SingleEnumWrapper` also has
`getName()`, `getKind()`, `getBaseType()`, `getFieldNames()` and `service.enums.Status.ACTIVE` (a constant →
map). Cross-capability: `service.enums['X'].list()` → `service.global.conversion.toSelectOptions(rows,
"name", "displayName")` → dropdown.

`service.enums.names()` (`EnumsWrapper.java`) returns the `Set<String>` of **all** registered enum names — for
iterating the registry. It is **runtime-only**: the hints tree emits only `list()` per enum (`buildEnumsHints`,
`HintsService.java`), so `names()` works at runtime but **never autocompletes**. (Its javadoc mislabels
it `service.enums.list()`; the real method is `names()`.)

---

### 2.10 `service.rule("Name")` — a rule invokes a rule

`ServiceWrapper.rule(String ruleName)` (`ServiceWrapper.java`) finds a rule **by name** (in the current
realm/client) and executes it **with the same `contextData`** (realm, client, userId, contextData). It returns
the `returnValue` of the invoked rule. Useful for reusing predicates.

**Worked example** (`Can Unlock`):

```groovy
return service.rule("Is Author") && !service.rule("Document is Unlocked")
```

> Resolution is **by name only** (not by identifier) — rule names must be unique in the project, otherwise
> behavior depends on `findByName`. The invoked rule sees the same `contextData` (context.*), but
> `attrs`/`param` are **NOT passed** — it is executed with an empty `executionVariables`
> (`new HashMap<>()`, `ServiceWrapper.java`). Do not rely on `attrs`/`service.actionId` inside the
> invoked rule.

---

### 2.11 `service.actionName` / `service.actionId` — which button was pressed

String fields (`ServiceWrapper.java`), populated when a rule is launched by an **action button**
of a CRUD-table/tree/process-table (`GroovyExecutorHelper.applyActionMeta`, reads `attrs.__actionId`/
`attrs.__actionName`, `GroovyExecutorHelper.java`). Outside the action context — `null`. Use `actionId`
(stable) for comparisons; `actionName` is the localized caption.

⚠️ **Also pushed by the FORM.** `FormPlugin.tagContextDataWithActionMeta` (`FormPlugin.java`) tags
`contextData.attrs` with `__actionName`/`__actionId` for **every rule the open form runs** — so a form opened
by a crud-table action OR by a workflow user-task action can discriminate on which button opened it.
And `applyActionMeta` is wired in **all three executors** — `GroovyExecutionRule.java`
**`GroovyPredicate.java`**, `GroovyValidationRule.java` — so `service.actionId` is readable from a
PREDICATE too. That is what makes per-action read-only fields possible; see
[02-form-controls-reference.md](02-form-controls-reference.md) "Read-only depending on the action".

**Real pattern** (form-mapping predicate; see [06](06-form-groups-and-mapping.md)):

```groovy
return service.actionId == '9f1c…-uuid'
```

---

### 2.12 `service.workflow.start(...)` — a rule starts a process

**EXECUTION_RULE and CRUD GROOVY methods only.** Those are the only editors that offer it — the hint tree omits
`service.workflow` for a PREDICATE and a VALIDATION_RULE, and the **Add start process** toolbar button is
absent there. Written by hand anyway, it refuses at runtime with a message: those rules are evaluated for their
answer, possibly more than once, and must not create work. `validate` flags it too.

**This section is the CALL; the chain around it is [27](27-event-driven-process-start.md)** — how to tell from
a PRD that nobody presses anything, which of the three headless triggers fires the rule (a scheduler tick, a
CRUD GROOVY method, a service task), the order the workflow / process group / worklist / context / rule must be
built in, the rule that gathers rows from business logic and shapes them into the document below, and the
idempotency without which a scheduler opens the same case on every tick. Read `27` before authoring one; read
this section for what each argument means.

```groovy
String start(String workflowIdentifier, Map contextData)
String start(String workflowIdentifier, Map contextData, Map options)
```

Returns the **process identifier** of the new process — the same value a process table shows. Nothing puts it
into the NEW process's own attributes: the start writes the context data document plus the platform's own
`owner` / `processEntityId` / trace-id process variables, and nothing else, so a rule running INSIDE the new
case cannot read it back as `attrs.processIdentifier`. Keep the returned value in the calling rule if anything
downstream needs it — writing it onto the row the case was opened for is also what makes the start idempotent
([27](27-event-driven-process-start.md) §5).

**First argument — the workflow IDENTIFIER, not its name.** The name is editable and not unique; the identifier
survives a rename and an export/import. The workflow must be **deployed** or the call throws.

> 💡 **You do not type this call by hand.** In the rule editor, type the opening quote of the first argument:
> this project's workflows are offered by name. Pick one and the WHOLE call is written for you — that
> workflow's contexts, each context's CRUDs, every field null and every list empty, plus an options block
> listing the project's real role groups and process groups. The **Add start process** toolbar button does the
> same through a dialog when you want to choose which CRUDs to include. Everything below describes what that
> generated code means, so you can edit it — not something you must produce from memory.

**Second argument — the initial context data**, in the same shape a context data document has on the wire:

```groovy
def pid = service.workflow.start("a3f2c1de-…", [   /* Customer onboarding */
    contextDataMap: [
        "8b21…-context-identifier": [               /* Customers */
            crudDataMap: [
                customer: [
                    value: [ name: null, email: null, tags: [] ]
                ]
            ],
            attrs: [:]                              // this CONTEXT's attributes
        ]
    ],
    attrs: [:]                                      // the process's GLOBAL attributes
])
```

Note the three levels and what keys them: `contextDataMap` by context **identifier**, `crudDataMap` by crud
**alias**, and each CRUD's row under `value`. Dot-paths are NOT interchangeable with nesting — write
`value: [ address: [ city: null ] ]`, not `value: [ "address.city": null ]`.

**Filling it in.** The generated skeleton gives you every field of every CRUD the workflow can reach, set to
null. Assign the ones the process needs and delete the rest — a CRUD you leave all-null still seeds its alias,
which is what keeps `context.<ctx>.<alias>.data` addressable in a service task.

**The two `attrs` slots.** The generator emits both, always, empty when it has nothing to seed — they are the
only place a rule-started case can publish anything that is not a CRUD row:

| Slot | What it is | What reads it |
|---|---|---|
| `attrs` at the **root** of the document | the process's **global** attributes | a rule: `context.data.<key>` / `context.data.getAttr("<key>")` · a `process.table.pluin` column with `scope: GLOBAL` (every `fieldExpression` other than `businessKey`/`workflowName`/`status`/`identifier`/`id` falls through to these) · a process **index** with `scope: GLOBAL` · a `GLOBAL`-scope control on a task form |
| `attrs` inside a **context** entry | that context's own attributes | a rule: `context.<ctxAlias>.data.<key>` / `.getAttr("<key>")` · a column, an index or a form control with `scope: CONTEXT` naming that context |

There is no third slot: a CRUD envelope carries **only** `value` (`CrudDataDto` has no `attrs` field). Writing
`crudDataMap: [ customer: [ value: […], attrs: […] ] ]` loses those attributes in silence — unknown keys in this
document are dropped, not rejected — and a service task then reads back nothing.

⛔ **The shape a hand-built document gets wrong, and what it costs.** Both levels must be NESTED. Writing the
context entry or the global attributes at the document ROOT is the single most expensive mistake on this call,
because unknown root keys are **dropped, not rejected** — `start` still returns a process identifier:

```groovy
// ⛔ WRONG — every key below is silently discarded
def doc = [:]
doc['<contextIdentifier>'] = ['crudDataMap': [order: ['value': row]]]   // context at the ROOT
doc['subjectId'] = id                                                   // attr at the ROOT
doc['orderNo']   = row.orderNo

// ✅ RIGHT
def doc = [
    'contextDataMap': [ ('<contextIdentifier>'): ['crudDataMap': [order: ['value': row]], 'attrs': [:]] ],
    'attrs': [ subjectId: id, orderNo: ((row.orderNo ?: '') as String) ]
]
```

The case then carries neither the CRUD rows nor the GLOBAL attributes, and **nothing at the start site says
so**. What you see instead, all of it a long way downstream:

| Symptom | Why |
|---|---|
| the worklist renders a column of BLANK rows | `process.table.pluin` columns at `scope: GLOBAL` read the root `attrs` |
| a task form's GLOBAL controls come up empty | same slot |
| **the task form fails to open — HTTP 500** | `onBeforeUserTaskStart` bind rule finds no `subjectId`, cannot resolve the record |
| a serviceTask computes nulls | `context.<ctx>.<alias>.data` is the empty auto-created envelope |

`validate` flags this offline (`_check_workflow_start_document_shape`) — it is not something to rediscover by
opening a queue.

**Fill them rather than delete them.** A form-started case gets its global attributes from the start form's
`GLOBAL`-scope controls; a rule has no form, so unless the call publishes them the case arrives with nothing but
CRUD rows — a worklist of blank columns and task forms of empty fields. Put the values that IDENTIFY the case
(the subject's id, its label, what opened it) in the root `attrs`, the ones that belong to one context in that
context's `attrs`, and point the worklist's columns at them by scope
([05](05-crud-tree-and-process-table.md)). They render immediately; indexed FILTERING is a separate thing and
still starts empty (see the gotchas below).

**Write `[:]`, never `[]`.** An empty Groovy `[]` is a LIST, and Jackson refuses to read an array into the
document: the call dies with `service.workflow.start: the context data map could not be read - …`. The same
applies to an empty `contextDataMap` and an empty `value`.

One more root key sits beside `attrs`: **`localeKey`** (`"en_US"`, `"ru_RU"`, …). Every rule in the case seeds
its locale from it, so omit it and the mail and messages a rule-started case sends come out in the project's
default language ([20](20-localization.md)).

There is a shortcut, `[ contextDataMap: contextDataMap ]`, which forwards the running rule's own document. It
works only in a rule that RECEIVED one — a form rule, a crud-table rule, a service-task rule. In a **CRUD
GROOVY method** or a **scheduler-triggered rule** there is no such document and `contextDataMap` reads as
**null**, silently: the process then starts empty and the first service task that touches
`context.<ctx>.<alias>.data` fails a long way from the cause. There, fill the skeleton field by field:

```groovy
def ctxId = "8b21…-context-identifier"
service.workflow.start("a3f2c1de-…", [
    contextDataMap: [
        (ctxId): [ crudDataMap: [ order: [ value: [
            docNumber: param.doc_number,
            amount:    param.amount
        ] ] ] ]
    ],
    attrs: [ subjectLabel: param.doc_number ]   // what the worklist's GLOBAL column will show
])
```

Two shapes meet here and they are keyed differently — do not pass one where the other belongs. **`param` is
flat**: one key per entry declared in the method's `parameters[]`, named exactly like the SQL placeholder, so
snake_case on create/update (`doc_number`, `partner__id`, `lines`, `id`) — see
[11](11-business-logic-dynamic-crud.md). A `value` map is keyed by **camelCase dtoField** names, which is what
the **Get context data** popover shows. `value: param` would therefore write keys the process cannot read.

**To find out what a form produces**, open it and use **Get context data** in its settings
([25](25-form-settings-validation-and-events.md) §4.5). Two things to know before pasting:
- The popover shows **JSON**, which is not a Groovy argument. Three conversions: `{…}` → `[…]`, `{}` → `[:]`,
  and `$` → `\$` inside any value you keep (or single-quote that value) — a double-quoted Groovy literal is a
  GString, so a pasted price like `"US$100"` either fails to compile or silently interpolates. **Leave the keys
  quoted** — `"8b21…": [ … ]` is a valid Groovy map key, and unquoting a UUID would not compile. (Only a key
  held in a VARIABLE needs anything extra: parenthesise it, `(ctxId): [ … ]`.) The **Add start process**
  toolbar button writes all of this for you.
- Use plain **Copy**, not **Trim & copy**, when the document is meant to SEED the process. Trim removes CRUD
  envelopes whose fields are all null — and a service task needs the alias PRESENT, even empty, or it throws
  `No CRUD data available for CRUD: <alias>`.

**Third argument — options.** All optional, and all about the same question: **who will ever see this case,
and where.** A started process that nobody can find is the most common way this call is got wrong, so the
generated snippet fills this block with the project's real values rather than leaving placeholders.

| Key | Meaning |
|---|---|
| `owner` | Email to start on behalf of. Defaults to the user the rule is running as; when there is no user at all — a scheduler tick whose schedule carries no `serviceUserEmail`, a CRUD method on a headless thread — the platform falls back to the project's configured author account **where that setting is filled in** (its in-code default is empty; blank = an ownerless case, see the gotchas). Trimmed but never case-folded: it is matched character-for-character against the login email. |
| `roleGroups` | Role group NAMES whose members may see the process. The snippet lists every group the project has — **delete the ones that should not see it**, rather than looking names up. |
| `emails` | Individual users who may see the process. Trimmed and never case-folded either — the worklist matches the row character-for-character against the login email. A single String is accepted where a list is expected. |
| `businessKey` | Business key of the new process; generated when omitted. |
| `groupIdentifier` | Which **worklist** the case appears in — see below. |

**What a process group actually is.** Not a property of the process, and nothing to do with permissions: it is
the bucket a `process.table` node is bound to. Each such node carries a `processGroupIdentifier` and shows
**only the cases of its own group**, so the group decides *on which screen* your case turns up. One workflow
can have several worklists — "Incoming", "Escalations", "Mine" — and they are told apart by exactly this.

That makes it **required whenever a `process.table` is scoped to a group**, which is the norm
([07](07-workflows-and-tasks.md) prescribes one group per workflow). Omit it and the case is created with no
group; the worklist's INNER join on the group excludes it, and it is invisible to everyone including admins,
with nothing logged. A form-started case gets its group from the node that started it — a rule has no node, so
it must say.

Admins and authors always have access, whatever is passed. Access rows are de-duplicated, so listing the owner
again is harmless.

```groovy
def pid = service.workflow.start("a3f2c1de-…", ctx, [
    owner:           service.security.user().email,
    roleGroups:      ["Back office"],
    businessKey:     "ORD-" + orderNumber,
    groupIdentifier: "7c40…-process-group"
])
```

**Gotchas**

- **Not a transaction.** The rule is not transactional, so a failure LATER in the same rule does not undo the
  start. Start the process last, once everything that can fail has succeeded.
- **Synchronous.** The call returns only after the new process has run its whole synchronous head — its start
  service tasks, gateways and their rules. A chain of rules starting processes that start processes blocks the
  whole way down, and nothing bounds that depth.
- **Never merge an all-null skeleton into a RUNNING process.** The generated skeleton is for a fresh start;
  merging nulls over a live context erases what service tasks have already computed.
- **Who can see it — never ownerless on a stock deployment.** `owner` defaults to the user the rule is running
  as — for a scheduler tick that is the schedule's `serviceUserEmail`, which travels through both hops of the
  pipeline — and when even that is blank the platform assigns **the project's configured author account**,
  writing its owner access row and the `owner` process variable. ⚠️ That fallback is a **configuration value
  whose in-code default is empty** (the field's javadoc: *"Blank disables the fallback and leaves the process
  ownerless"*), so a deployment that blanks it produces **no owner access row and no `owner` variable at all** —
  the case is then reachable only through the admin / author ROLE grants, and its service tasks run with no
  user. Nothing in the export shows you which deployment you are on, which is the argument for passing `owner`
  rather than inheriting one. With the fallback on, the thing to guard against is not "nobody sees it" but
  "**one wrong account** owns it": that same account is the identity a service task executes, until the first user task completes,
  as, so `service.security.user()` inside the case answers the author, not the person the case is about. Admins
  and authors have access whatever is passed — which also means testing a worklist as an author proves nothing.
  Pass `roleGroups`/`emails` for the people who must actually work it. A warning naming the rule is logged only
  when the call carried no acting user, no role groups and no emails.
- **`roleGroups` are matched by NAME, exactly.** A misspelled group produces an access row that can never
  match, and no error says so — copy the name from the project's role groups rather than retyping it.
- **Indexed filtering starts blank.** A process's indexed values (`paramsToFilter`, and every filter built on
  them) are extracted when the process STARTS and again after each action execution, from whichever index
  settings that start or action carried; the programmatic start passes none at all, so a rule-started case is
  excluded by any filter over an index until the first user-task submission backfills it.
  Its displayed COLUMNS are a different mechanism and are live immediately: each one renders whatever THIS
  call's document carries at the column's own scope — `GLOBAL` from the document's root `attrs`, `CONTEXT` from
  `contextDataMap[ctx].attrs`, `CRUD` from that alias's `value` in `contextDataMap[ctx].crudDataMap`. All three
  resolve, so a blank column means the document published nothing under the key the column names. Prefer
  `GLOBAL` for the identifying columns anyway: a CRUD column is a **snapshot** of what you passed and goes
  stale the moment a service task writes the row ([05](05-crud-tree-and-process-table.md),
  [27](27-event-driven-process-start.md) §6).
- **Provenance is stamped for you.** The started process's global attrs carry `startedByRuleIdentifier` and
  `startedByRuleName`, plus `startedByCrudAlias` and `startedByMethodName` when a CRUD Groovy method started
  it. They are readable as `context.data.startedByRuleName`. Setting those keys yourself does nothing — they
  are written last, after the supplied document.
- **`service.access.*` cannot reach the new process.** It operates on `attrs.processIdentifier`, which is the
  process the rule is IN. Grant access through the options above, or from the new process's own first service
  task.

---

### 2.13 `service.workflow.list / actions / contextData / complete / cancel` — a rule works an existing case

**Same gate as `start` (§2.12): EXECUTION_RULE and CRUD GROOVY methods only.** The whole namespace is absent
from a predicate and a validation rule, and refuses at runtime if written there by hand.

Where `start` opens a case, these seven find one, ask what may be done to it, read its data, act on it, end it, and name the case the rule is already in:

```groovy
Map    list(String processTableSettingsId, Map filterValues[, Map options])
List   actions(String processIdentifier[, String processTableSettingsId])
List   startActions(String processTableSettingsId)
Map    contextData(String processIdentifier)
Map    complete(String processIdentifier, String actionId, Map contextData[, Map options])
Map    cancel(String processIdentifier[, String reason])
String currentProcessIdentifier()
```

#### `cancel(...)` — ending a case

The closing half of `start`. Until it existed a rule could open a case but never close one, and an abandoned
case had to be left running forever.

```groovy
service.workflow.cancel(pid, "rejected at review — version returned to DRAFT")
```

Answers `[success: true, alreadyEnded: false, status: "CANCELED", message: "…"]`. Three behaviours to know
before writing the rule:

- **Cancelling a case that has ALREADY finished succeeds**, with `alreadyEnded: true`. A retry, or two branches
  that both decide to abandon, is not an error.
- **A rule may NOT cancel the case it is itself running inside.** The engine is mid-transaction on that case, so
  the delete would come back later as an unrelated locking failure. The call refuses with a 409 naming the
  remedy: to end a case from within itself, route the branch to a **terminate end event** in the BPMN — that is
  what "this case ends here" means to the engine.
- **The reason is stored** as Flowable's deletion reason on the historic process instance. Nothing in the
  platform UI surfaces it yet, so today it is recoverable only from the engine's history tables — still worth
  filling in, but do not rely on a user ever seeing it.

#### `currentProcessIdentifier()` — which case am I in

```groovy
def pid = service.workflow.currentProcessIdentifier()
```

Before it existed there was no way to ask, so every service task re-published its own subject id as a GLOBAL
attribute on every step purely so the next rule could tell what it was working on. That bookkeeping can go.

**Where it answers.** In rules the ENGINE runs — service tasks and gateway predicates — and on the
process-table action path. It answers `null` in a CRUD Groovy method, in the scheduler, and on paths that do
not stamp the case. So use it to NAME the case you are already working on; do not branch on null-vs-value, and
do not pass it to `cancel` expecting a guaranteed id.

> The value is stamped per execution and deliberately never stored in the case document. That matters: a
> document is routinely copied into a new case (`contextData(A)` then `start(w, thatDocument)`), and an
> identity that persisted would tell case B it was case A — after which `cancel(currentProcessIdentifier())`
> would destroy a live, unrelated case.

#### The settings ID, and why it is the first argument

A **process table** already declares everything a listing needs: which workflow, which process group, how it
filters, and what it indexes. Restating that in a rule is not just tedious — it drifts. So the rule NAMES the
table instead, by its **Settings ID**, and inherits all of it.

Copy the ID from the table's own settings panel: **Process Table settings → Workflow binding → Settings ID**,
with the copy button beside it. It is stable across branches and survives an export/import.

> 💡 **You do not type these calls by hand.** In the rule editor, type the opening quote of the settings-id
> argument: this project's process tables are offered by name. Pick one and the WHOLE call is written for you —
> that table's real filter keys, one per line, and a comment naming the values it indexes. The **Add process
> list** toolbar button does the same through a dialog, and takes a pasted ID for when you already have one.

**Every one of these calls except `startActions` also works with no settings ID at all** — pass `null` and
state what you need in the options instead (`workflowIdentifier`, `groupIdentifier`, `expression`). You then
inherit nothing, which is the right answer when the rule is not mirroring any worklist. Three things are only
reachable WITH an ID, because they exist nowhere else: **`startActions`** itself, a table's **global actions**,
and the **index settings** that say how to rebuild a process's indexed values after an action.

> ⚠️ **Blank is not the same as wrong.** A blank ID means "no table" and is legal. An ID that names no table is
> REFUSED, on purpose: inheriting nothing would silently drop the workflow, the group AND the filter expression
> at once, and `list` would return a strictly wider set than the worklist it was told to mirror — plausible,
> larger, and impossible to tell from the right answer. It is a UUID you pasted; a typo is the expected mistake.
>
> A table whose **settings panel has never been opened** may have no saved settings under its ID at all. Open
> it once (that is also where you copy the ID from) and it is written.

#### `list` — one page of processes

Returns a map: `content` (the rows), `totalElements`, `totalPages`, `pageNumber`, `rowsInPage`. Each row has
`identifier`, `processInstanceId`, `businessKey`, `status`, `workflowIdentifier`, `workflowName`,
`processGroupIdentifier`, `processGroupName`, `ownerEmail`, `creationTime` and `indexes`.

```groovy
def page = service.workflow.list("<settingsId>", [
    filter_status: "ACTIVE"
], [
    page: 0,
    size: 50
])
page.content.each { row ->
    log.info("${row.businessKey} — ${row.indexes.customerName}")
}
```

| Option | Meaning |
|---|---|
| `page` / `size` | zero-based page; size defaults to 15 and is **capped at 200** |
| `workflowIdentifier` / `groupIdentifier` / `expression` | override what the table says |
| `status` | `NEW`, `STARTED`, `COMPLETED`, `CANCELED`. An unknown value is refused, not ignored |
| `search` | case-insensitive substring of the **business key only** |
| `asUser` | list as somebody other than the user running the rule |
| `allUsers` | skip access scoping and list every process of the project |

**Three things about filtering that are easy to get wrong:**

1. **`filterValues` keys are the `{placeholder}` names from the table's expression**, without the braces —
   exactly the Filter Keys its filter form controls carry. The generated call writes them out for you.
2. **An expression with no filter values filters nothing.** That is the evaluator's own rule, not a choice made
   here: an expression built only of literals is a silent no-op. A blank value is dropped, so an unfilled key
   behaves as an empty field on the filter form does.
3. **Expressions match a process's INDEXED values only** — the ones the table's Process Indexes declare, which
   is what each row's `indexes` map contains. A value the table does not index cannot be filtered on, however
   it is spelled, and it does not fail — it matches nothing.

**A rule with no user must say so.** A listing is access-scoped, and a scheduler-triggered rule has no user at
all. Rather than quietly returning an empty page, the call is refused unless `allUsers: true` is passed.

#### `actions` — what may be done to this case, right now

Returns a list of maps: `id`, `name`, `icon`, `source` (`USER_TASK`, `GLOBAL` or `START`), `taskId`, `direct`,
`completesTask`, `formGroupIdentifier`.

"Right now" is the point: an action is offered only when its **visibility predicate** evaluates true for this
process, so this cannot be answered from the workflow definition. Without a settings ID you get the user-task
actions of the node the process is sitting on. With one you also get that table's **global** actions — which
live only in its settings and are otherwise invisible. `startActions` returns the third kind, the buttons that
open a NEW case; executing one is a `start(...)`.

> A global action with **no** visibility predicate is never offered — by a process table either. It would
> otherwise be available on every case in every state, which is almost never what was configured.

#### `contextData` + `complete` — read, change, act

`contextData(processIdentifier)` returns the case's document in the same shape `start` takes, so the natural
thing to write is also the correct thing:

```groovy
def open = service.workflow.list("<settingsId>", [ filter_status: "PENDING" ], [ size: 200 ])
open.content.each { row ->
    def approve = service.workflow.actions(row.identifier, "<settingsId>")
                          .find { it.name == "Approve" }
    if (!approve) return                                  // not available on this case right now

    def ctx = service.workflow.contextData(row.identifier)
    ctx.contextDataMap."<contextIdentifier>".crudDataMap.order.value.approvedBy = service.security.user().email
    ctx.attrs.decision = "APPROVED"

    service.workflow.complete(row.identifier, approve.id, ctx, [
        settingsIdentifier: "<settingsId>"
    ])
}
```

`complete` does what pressing that button and submitting its form does, in this order: the action's
**onBeforeUserTaskStart** rule, then your data, then its **validation rules**, then its
**onBeforeUserTaskComplete** rule, then the task. Returns `success`, `taskCompleted`, `message` and — for a
form action — `formGroupIdentifier`.

| Option | Meaning |
|---|---|
| `settingsIdentifier` | required to reach a GLOBAL action at all; also what rebuilds the indexed values afterwards |
| `merge` | `false` to REPLACE the document instead of merging into it. Default merges |
| `completeUserTask` | `false` to write the data and run the rules without moving the token |
| `localeKey` | e.g. `"ru_RU"` — the locale the case's rules and messages use |
| `asUser` | act as somebody other than the user running the rule |

**What it will refuse to do, and why:**

- **An action that is not currently available.** It is re-resolved through the same visibility check a person
  faces. A rule cannot execute what a person could not.
- **A global action with no settings ID.** There is nowhere else to look for it.
- **An action of the process the rule is itself running inside.** That re-enters the engine from inside the
  transaction already running the rule, and fails much later as a locking error with nothing pointing at the
  cause. Move the process with the workflow instead.
- **Data that fails the action's validation rules.** The messages come back in the error.

**Four quieter behaviours worth knowing:**

- **`merge` is the default because replace loses data silently.** A document assembled by hand carries only the
  CRUDs the author thought about, and the service task after this one reads the others.
- **Without a settings ID the indexed values are left ALONE, not rebuilt.** Writing them REPLACES the whole
  indexed document, so rebuilding it from index settings that were not supplied would blank every value the
  worklist filters on — and the case would vanish from its own list. Stale beats invisible.
- **With `merge: false`, the action's validation rules still see a MERGED document.** Validation runs the way a
  form's does, and a form is always a partial document laid over the case's own — there is no "validate exactly
  this and nothing else" mode. So a rule that replaces a document to REMOVE something can pass a validation
  that checks the thing is present. If a validation guards what you are removing, remove it with `merge` on
  and an explicit null instead.
- **`access` is read-only here.** `contextData(...)` returns it, and the merge accepts an edit, but nothing
  applies it: the next read rebuilds `access` from the process's access rows. Grant visibility with the
  options on `start(...)`, or from a service task of the case.

`taskCompleted` is reported separately from `success` on purpose: an action configured not to complete its
task, and a global action (which has no task), both succeed without moving the process. A loop that waits for
the node to change has to read the right one.
---

### 2.14 `service.store.*` — key/value storage that outlives the rule

Backing — `RuleStoreProxy` (`RuleStoreProxy.java`), holding two implementations of one interface
(`KeyValueStore.java`): `SessionKeyValueStore` for `session`, `UserKeyValueStore` for `user`. Wired in **all
three executors** (`GroovyExecutionRule.java`, `GroovyValidationRule.java`, `GroovyPredicate.java` via
`GroovyExecutorHelper.applyStore`), so both members are always PRESENT — never null, never absent by rule type —
in an EXECUTION rule, a PREDICATE, a VALIDATION rule and a CRUD GROOVY method alike. A store that cannot reach
anything answers empty rather than throwing; a `put` past one of the limits below is a different matter and IS
refused, naming the key.

> ⚠️ **`user` works everywhere there is an acting user; `session` only where a browser session took part.**
> That distinction is not about the rule TYPE, it is about how the rule was reached — the exact list is under
> "When a store is empty on purpose" below, and it is worth reading before you choose a scope.

**Not the same axis as the attribute scopes.** The three attribute scopes of doc
[08](08-groovy-rules-and-context.md) — `context.data.*` (GLOBAL), `context.<ctx>.data.*` (CONTEXT),
`context.<ctx>.<crud>.data.*` (CRUD) — belong to a DOCUMENT: they travel along a case (the process persists its
context data between nodes, which is how one step publishes to the next — [07](07-workflows-and-tasks.md)) or
live for as long as a form is open, and with neither they last exactly one execution. `service.store.*` belongs
to the SESSION or to the PERSON instead, is reachable from any rule — including one with no form and no case —
and nothing joins it to a row. Carry something along a case in an attribute; remember something about this
browser session or this user in the store.

```
service.store
 ├─ session   → values that live as long as the user's BROWSER session   (SessionKeyValueStore)
 └─ user      → values stored in the database for the ACTING USER        (UserKeyValueStore)
```

| Scope | Lives | Shared with | Dies when |
|---|---|---|---|
| `service.store.session` | the browser session, **per project** | every tab of that browser session that is in the SAME project | the session ends (logout, timeout, server restart) |
| `service.store.user` | a database row per (project, user, key) | every session that person opens, now and later | the rule removes it, the person is removed from the project, or the project is deleted |

Both scopes are scoped to the project: one browser session can have tabs open in two different organisations,
and neither can see the other's store.

#### The eight methods (identical in both scopes)

| Method | Signature | Behaviour |
|---|---|---|
| `get` | `Object get(String key)` | the stored value, or `null` when the key was never written |
| `get` | `Object get(String key, Object defaultValue)` | …or `defaultValue` when there is none |
| `put` | `Object put(String key, Object value)` | stores; returns the **previous** value or `null`. `put(k, null)` **removes** |
| `remove` | `Object remove(String key)` | removes; returns the previous value or `null` |
| `containsKey` | `boolean containsKey(String key)` | always agrees with `get(key) != null` |
| `keys` | `List<String> keys()` | every key currently stored, sorted |
| `all` | `Map<String,Object> all()` | everything, as a plain map. It is a **copy** — writing to it stores nothing |
| `clear` | `void clear()` | removes everything in that scope |

The Groovy subscript form works too and is the same store: `service.store.user['branch']` reads,
`service.store.user['branch'] = id` writes (`KeyValueStore.getAt/putAt`).

> ✅ **One interface, two scopes.** Moving a key from `session` to `user` is a one-word edit — the method list,
> the null semantics and the value shapes are identical by construction. Choose `session` for "for as long as
> this person is here" (a wizard step, a picked filter, a cached lookup) and `user` for "the next time they log
> in too" (a preference, a last-used value, a per-user watermark).

#### Worked examples

```groovy
// Remember what the user picked, in this browser session only.
service.store.session.put("selectedBranchId", context.crm.branch.data.get().id)

// …and read it back from a completely different rule of the same session.
def branchId = service.store.session.get("selectedBranchId")
if (branchId) {
    return service.crud.order.findByBranch(branchId)
}
return service.crud.order.findAll([:])
```

```groovy
// A per-user preference that survives logout, read by the rule that actually uses it.
service.store.user.put("defaultBranchId", 7)

// Read with a default so the first-ever run works.
def branchId = service.store.user.get("defaultBranchId", 0)
```
> ⚠️ Pick a preference some RULE can act on. A CRUD table's page size, for instance, is a static plugin setting
> with no rule hook, so storing a per-user `rowsPerPage` would change nothing — a store-driven page size means a
> hand-built HTML table that pages itself ([24c](24c-html-data-tables-and-paging.md)).

```groovy
// A per-user watermark, so a scheduled digest never re-sends what it already sent.
// NOTE the scope: a scheduler tick has no browser session, so `session` would be empty there — `user` is the
// scope that works headlessly, and only when the tick carries an acting user.
def since = service.store.user.get("lastDigestAt")          // an ISO string, or null on the very first run
def rows  = service.crud.ticket.findChangedSince(since)
service.store.user.put("lastDigestAt", service.global.formatting.date.format(
        service.global.formatting.date.now(), "yyyy-MM-dd HH:mm:ss"))
```

```groovy
// Structures round-trip as structures.
service.store.session.put("filter", [status: "OPEN", branch: 7])
def filter = service.store.session.get("filter")   // a Map again, not a String
```

#### Values must be JSON-shaped

A session value crosses the wire between the web tier and the executor; a user value is a `jsonb` column. Both
carry a `String`, a number, a `boolean`, a `List` or a `Map`, and both hand a structure back as a
`LinkedHashMap` / `ArrayList` (`StoreValueCodec.java`). An arbitrary object is not what a key/value scratchpad
is for — put its id in, not the object.

**What each type reads back as.** Identical in both scopes — that is the point of the table:

| You store | You get back | |
|---|---|---|
| `"text"`, `true`, a `List`, a `Map` | the same | a Map comes back a `LinkedHashMap`, a list an `ArrayList` |
| `42` — or any whole number | `Integer` | a `Long` too big for `Integer` stays `Long`; past `Long` it is a `BigInteger` |
| `1.50` — a **decimal literal, which in Groovy is a `BigDecimal`** | `BigDecimal`, scale intact | `1.50` stays `1.50`, not `1.5` |
| a `Double` or `Float` — e.g. the result of `/` on two doubles | `BigDecimal` | the store has no `Double`: every fractional number comes back a `BigDecimal` |
| a `Date`, `LocalDate`, `LocalDateTime` | `String` — its ISO text | see the gotcha below |
| a `UUID`, a single character, a `GString` | `String` | |
| an enum constant | `String` — its `name()` | |

Decimals keep their exact type and scale on purpose, at every depth — a `Map` of prices comes back a `Map` of
`BigDecimal`s. Money survives a store round trip: `0.1 + 0.2` is `0.3`, and a thousand additions of `0.01` make
exactly `10.00`. Whole numbers are deliberately NOT promoted, because a Groovy integer literal is an `Integer`
and `[1, 2, 3].contains(id)` is false for a `Long`. In both cases the store returns the type your own literal
would have produced.

**Numbers have a ceiling:** 10 000 digits, and the decimal point at most 10 000 places away from them. That is a
safety limit, not a business one — it is far past any money, quantity or measurement, and it exists because a
number like `1E+2147483647` is thirteen characters to write and impossible to read: adding to it or printing it
throws, in some later rule, with an error nobody can trace back to the `put`. `NaN` and `Infinity` are refused
for the same reason — JSON cannot carry them, so they would be stored as the *words* `"NaN"` and `"Infinity"`.

#### When a store is empty on purpose

Both scopes are **always objects, never null** — there is nothing to null-check before calling them. What
changes is whether they can reach anything:

**`service.store.user` is empty** whenever the execution names no acting user — a service task that runs before
anybody is assigned. A scheduler tick is NOT such a case: it runs as the schedule's service user, which is why
`user` is the scope to reach for in anything headless.

**`service.store.session` is empty** wherever no browser session took part. It is live in:

- ✅ an EXECUTION rule or a PREDICATE launched from a page — an action button, a fetch rule, a choices rule, a
  CRUD-table/tree row-visibility predicate, a form's mapping or hidden-content predicate, a form's
  before/after rule, `ctx.callRule` from an HTML component;
- ✅ a rule those rules call with `service.rule("…")`, and a CRUD GROOVY method they call with
  `service.crud.<alias>.<method>()` — the store travels down the whole chain.

and empty in:

- ⛔ a **VALIDATION rule** — form submission goes through the workflow service, which carries the form's context
  data and no session;
- ⛔ a **CRUD GROOVY method invoked directly from a page** (a table listing, a form save, a run-method dialog).
  The CRUD API carries no context data at all. The SAME method sees the store when a rule called it;
- ⛔ anything a PROCESS TABLE evaluates (a row, global or start-action predicate) and any rule run against a
  CASE by process identifier (a task action, a service task) — those requests carry a process or a workflow,
  not a session;
- ⛔ a scheduler tick, a Kafka message, an MCP call, anything headless.

In both cases `put` stores nothing and `get` answers `null`, **including within the same script**
(`DetachedKeyValueStore.java`). That is deliberate: a store that remembered a write for the rest of the rule and
then dropped it would make one script behave differently from a page and from a cron, with the difference
surfacing later and somewhere else.

#### Where the keys in autocomplete come from

A store key is invented by whoever writes the rule; nothing declares it up front. So the editor completes a key
from a **catalogue of keys that have actually been written** — the executor records each key (and the type last
stored under it) the first time a rule writes it, per scope (`StoreKeyEntity.java`), and the hint payload carries
them under its own root node so they are completable in every rule type
(`HintsService.attachStoreKeys`; see [09](09-groovy-hints-and-live-context.md)).

> ⚠️ **A brand-new key completes only after the rule that writes it has run once.** Autocomplete cannot offer a
> key nothing has ever stored; that would be offering a guess. Type it in full the first time.

> ⛔ **A COMPUTED key pollutes the catalogue permanently.** `put("case:" + id, …)` records one catalogued key per
> case, forever — the catalogue has no idea the key was generated. The editor is protected (only the most
> recently written keys are offered, and only a bounded number of them) but the rows stay. Prefer one key
> holding a map to a key per row.

#### Gotchas

- **`session` is per BROWSER session and per PROJECT, not per tab and not per page.** Two tabs of one login on
  the same project share it. A key written by one tab is read by the other — usually what is wanted,
  occasionally a surprise. Two tabs in two different organisations do NOT share it.
- **A key is at most 255 characters, in both scopes,** and a longer one is refused at the `put`.
- **A decimal keeps its type and its scale; a whole number comes back an `Integer`.** See the table above —
  this is what makes `[1.50].contains(store.get("fee"))` work, which it would not if money came back a
  `Double`.
- **Both scopes are capped: 200 keys in `session`, 500 keys per person in `user`.** A `put` that would add a
  key past the limit is refused — the message names the scope and the count rather than the key, because the
  problem is the number of keys, not the one you happened to write last; updating a key already held always works, so a rule cannot
  start failing on a value it already owns. The two limits differ because the costs differ — the session scope
  travels with every rule execution, while the user scope is rows in a database shared by every project on the
  installation. Both exist to refuse the same mistake: **a key per row of your data.** `put("case:" + id, …)`
  inside a rule that runs per row will always reach the cap. That data belongs in a CRUD table; the store is
  for ids, flags and preferences.
- **`user` is keyed by the acting user's e-mail, case-insensitively.** Change a person's e-mail address and
  their stored values do not follow. (Roles and identity work the same way — see §2.3.)
- **⛔ A date comes back as TEXT, and the two ways that bite are silent.** `store.get("lastRun") + 1` appends
  the character `1` to the string instead of adding a day, and comparing two ISO strings compares them
  letter by letter — which is right while the offset is the same and wrong the moment it is not
  (`"…T10:00+04:00" > "…T09:00+00:00"` is true as text and false as time). Parse it before you use it, or
  store the epoch millis (`date.time`) and keep a number.
- **`put(key, null)` removes.** It does not store a null. `containsKey` and `get(key) != null` therefore always
  agree, in both scopes.
- **`all()` is a copy.** `service.store.user.all().put("x", 1)` stores nothing; use `put`.
- **Do not depend on the KEY ORDER of a stored map.** `session` gives it back in the order you wrote it;
  `user` gives it back in the order the database chose. Same keys, same values — different iteration order.
  Read a stored map by key, never by position.
- **`clear()` clears the whole scope for that person / that session,** not just the keys this rule wrote.
- **Concurrent writes are last-write-wins per key.** Each execution carries the session snapshot it started
  with and applies what it changed; a key the rule never touched is left alone, so a second tab's key is not
  destroyed, but two rules writing the SAME key race.
- **Everything in the SESSION store travels with every rule execution, both ways.** It costs an empty map on
  every rule while nothing has been written — an empty map is always sent when there is a browser session, and
  that is what lets the first write land — and the whole map once something has. Keep ids and flags in it, not
  payloads: put the id in the store and fetch the row with `service.crud.*`. A single value is capped at about
  64 K CHARACTERS of serialized JSON (so less for non-Latin text) and the session scope at 200 keys; a `put`
  past either is refused, naming the key.
- **A session write is kept only if the rule COMPLETES; a user write is kept as soon as it is made.** A failing
  rule answers with no context data at all, so the session map never travels home and everything it wrote is
  lost — while a `service.store.user.put` made two lines earlier is already a committed row. If a flag must
  survive a failure, it belongs in `user`.
- **Store values are runtime data and never travel in a `.mrjun`.** An export carries rules, not what they
  stored, so a project created fresh starts with both stores empty. An import over an EXISTING project
  deliberately KEEPS what is stored — those values could not be carried or restored by an export, so wiping
  them on every import would destroy them — and only deleting the project drops them.
- **Removing a person from a project deletes their `user` values in it.** The rows are keyed by e-mail address,
  and an address outlives a membership — it can be re-invited or reassigned — so they are cleared with the
  membership rather than left for whoever holds that address next. Their values in OTHER projects are
  untouched: the store is per project.

---

### 2.15 `service.redirectPage("alias/page")` — send the browser to another page

Backing — `ServiceWrapper.redirectPage` (`ServiceWrapper.java`), applied by `RulePageRedirect` (`RulePageRedirect.java`).

**EXECUTION rules only.** A PREDICATE and a VALIDATION rule refuse it with an explanation, for the same reason
they refuse `service.workflow.start` (§2.12): they are evaluated for an answer, possibly once per row of a
table. A **CRUD GROOVY method refuses it too** — its result is read for the return value alone, so nothing
carries an instruction from it back to a browser; redirect from the RULE that called the method. The editor does
not offer the member in any of those three places, so the hint and the runtime agree.

```groovy
service.redirectPage("orders/queue")     // -> https://<host>/<organisation>/orders/queue
service.redirectPage("/orders/queue")    // the leading slash makes no difference
```

**The path is everything AFTER the organisation** — the project alias plus the page's content path. The
organisation (the realm segment of the URL) is prepended for you, because a rule is deliberately never told
which realm it runs in: `realm` and `client` throw `SecurityException` in a script (see the Security invariant
in Part 1), and the realm is a fact about the browser's URL rather than about the rule. It is prepended only
where the deployment's URLs actually carry it — a project served on its own domain has no organisation segment,
and the same rule works there unchanged.

| Aspect | Behaviour |
|---|---|
| When it happens | AFTER the rule returns. The rest of the script still runs — this is a request to navigate, not a `return`. |
| Called twice | The last path wins. |
| `null` or `""` | Cancels a redirect asked for earlier in the same execution. |
| No browser waiting | Nothing happens. Not an error. |
| Where it is DELIVERED | An EXECUTION rule launched from a page — an action button, a form's before/after rule, `ctx.callRule` — and anything that rule calls with `service.rule(…)`. |
| Where it is NOT delivered | A rule run against a CASE by process identifier (a workflow task action, a **process-table** action, a service task) and anything headless (scheduler, Kafka, MCP). Those requests carry a process, not a browser — the same list as `service.store.session` in §2.14. |
| A full URL | **Refused at the call**, with an exception. So is a `..` segment, a backslash, a percent escape and a control character — a page path holds letters, digits and `- . _ ~ / ? # & = : @ + , ; ! $ ( ) *` and nothing else. A rule that could send a browser anywhere would be an open redirect served from the customer's own domain. |
| A query string | Allowed: `service.redirectPage("orders/queue?status=OPEN")`. |

**Worked example** — an action that creates a case and takes the user to the worklist:

```groovy
def caseId = service.workflow.start("wf-order-review", [ /* … */ ])
service.crud.order.markOpened(caseId)
service.redirectPage("orders/queue")
return caseId
```

**Worked example** — branch on which button was pressed (§2.11):

```groovy
if (service.actionId == '9f1c…-uuid') {
    service.redirectPage("orders/detail")
}
return true
```

#### Gotchas

- **It is a redirect, not a `setResponsePage`.** The browser loads the target page fresh; anything the current
  page held in memory is gone. Values that must survive the jump go in `service.store.session` (§2.14). The
  order INSIDE the script does not matter — the navigation happens after the rule returns, and the store is
  written back first either way.
- **A case never carries a redirect, and a redirect never survives into one.** Handing
  `service.contextData` to `service.workflow.start/complete` is safe: what the workflow service receives is a
  sanitised COPY, and your own document keeps its pending redirect. A rule run FROM a case never delivers one
  either — see the table above.
- **An action that already navigates wins, silently.** A CRUD-table or tree action that opens a form group
  replaces the page itself, and Wicket keeps only the LAST navigation scheduled for a request — so a
  `redirectPage` in that action's rule is discarded with nothing logged. Use it from actions that stay on the
  page (a direct action, a form's before/after rule, an HTML component's `ctx.callRule`).
- **Wrong path, blank page.** Nothing validates that the page exists — the value is an in-app path, and the
  browser simply goes there. Copy the alias and the content path from the page's URL.
- **A rule reached without a browser is silent about it.** Same shape as `service.store.session`: a scheduler
  cannot navigate anybody, and the call neither throws nor warns.
- **Not for downloads.** `service.report.pdf.download` (§2.6) has its own delivery; redirecting to a file URL is
  not how the platform hands over bytes.

---

## Part 3 — `validation.*` (VALIDATION_RULE only)

In a validation rule, the `ValidationRuleTemplate.groovy` template places the `validation` collector and provides 4
delegate methods. The script **returns nothing** — it accumulates messages; the framework
displays them at the field/form. See also [08](08-groovy-rules-and-context.md) and §"Field-based validation templates"
in [02](02-form-controls-reference.md).

| Method (in the script) | Delegates to | Effect |
|---|---|---|
| `addError(String message)` | `validation.addError(message)` | A general form error (`ValidationRuleTemplate.groovy`). |
| `addWarning(String message)` | `validation.addWarning(message)` | A general warning. |
| `addFieldError(String fieldName, String message)` | `validation.addFieldError(...)` | An error at a specific field. |
| `addFieldWarning(String fieldName, String message)` | `validation.addFieldWarning(...)` | A warning at a field. |

In hints these 4 methods live under the `validation` key (`HintsService.java`, `buildValidationMethods`) —
but **only** when `ruleType == VALIDATION_RULE`. For EXECUTION/PREDICATE there is no `validation` key in hints.

The canonical form:

```groovy
if (!context.userContext.user.data.get().email) {
    addFieldError("Email", "Email is required")
}
def amount = context.<ctx>.<crud>.data.getField('amount', java.math.BigDecimal.class)
if (amount != null && amount > 10000) {
    addWarning("Large transaction - review recommended")
}
```

The first argument is the **control's `settings.name`** (the label as authored — a generated control for column
`email` gets the name `Email`), **not** the column / `fieldExpression`: a name matching no control makes the
message vanish silently while still blocking submit, a blank one makes it form-level. See
[08](08-groovy-rules-and-context.md) §"The VALIDATION shape" and
[25 §4.2](25-form-settings-validation-and-events.md).

---

## How to construct a call from scratch (recipe)

You write **only the script body** (`rule.ruleScriptStr` or `methods[].script`). The template wrapper, bindings and
resolution are done by the runtime. Step by step:

1. **Choose the rule type** (see [08](08-groovy-rules-and-context.md)):
   - you need a `Boolean` for visibility/enablement/mapping → `PREDICATE` (mandatory `return <expr>`);
   - you need to perform an action / return data (fetch, dropdown source, CRUD GROOVY method, action logic) →
     `EXECUTION_RULE`;
   - you need to validate a form → `VALIDATION_RULE` (no `return`, only `addFieldError`/…).
2. **Bind the context.** For `service.crud.<alias>` and `context.<ctx>.<alias>` to resolve, the rule must
   have `contextIdentifiers = [<context>]`, and `<alias>` must be in the `crudAliases` of that context (for `service.crud`
   with an **empty** context list, resolution goes across the whole registry, `DynamicRuleContext.groovy`). See
   [08](08-groovy-rules-and-context.md).
3. **Read the input:** pagination/filters — from `attrs` (values are `JsonNode`: `attrs.get('rowsInPage')?.asInt()`);
   the delegated method's parameters — from `param` (`param ?: [:]`); the current row — from
   `context.<ctx>.<alias>.data.get()` or `currentData.get()` (nested forms).
4. **Perform the operation** with the appropriate Part 2 namespace. Frequent recipes:
   - **CRUD fetch → dropdown:** `service.crud.<alias>.find([rowsInPage, pageNumber:0])` →
     `service.global.conversion.toSelectOptionsLocalized(list, "id", "name")` → `return` (plain `toSelectOptions`
     for a non-localized display column). **Always** end in a `toSelectOptions*`/`toAutoCompleteOptions` pair-list —
     a raw `find`/`findAll` entity list breaks the control ("No results found" + no Show Nav).
   - **CRUD fetch → autocomplete:** `service.crud.<alias>.find([rowsInPage, pageNumber:0])` →
     `service.global.conversion.toAutoCompleteOptions(list, "<display>")` → `return`.
   - **Searchable dropdown:** build the platform pipeline per (crud, searchField `X`, `Cap(X)`=first-letter-upper):
     SQL method `acFindAllBy<Cap(X)>Like` (single typed `:X` param, `defaultValue ''`, `LIMIT 100`) + Groovy wrapper
     `acFindBy<Cap(X)>Like` + rule `RIMM_FILT_<alias>_<X>` (reads the typed term from `attrs.get('filterBy')`), ending
     in `toSelectOptions*`/`toAutoCompleteOptions`. Never hand-call the default multi-optional `findAll` with a
     PARTIAL param map. Full naming table: [02-form-controls-reference.md](02-form-controls-reference.md) §4a.
   - **RIMM query → dropdown:** `service.rimm.run([name:"...", itemsPerPage, parameters:[...]])` →
     `service.global.conversion.toSelectOptions(list, "key", "display")`.
   - **role check (predicate):** `return service.security.hasAnyRoleGroup("Author")`.
   - **notify a role on an event:** `service.notification.push.sendAlertToRoleGroup("Ops", "T", "M")`.
   - **PDF → e-mail:** `def r = service.report.pdf.get.tpl("f.pdf", [...]); service.report.pdf.email.mailTpl([...],[...],[r])`.
   - **invoke another rule:** `return service.rule("Is Author") && ...`.
   - **send the user to another page after an action:** `service.redirectPage("orders/queue")` — §2.15,
     EXECUTION rules only, path WITHOUT the organisation.
   - **remember something between rules:** `service.store.session.put("selectedBranchId", id)` (this browser
     session) or `service.store.user.put("rowsPerPage", 50)` (this person, forever) — §2.14. Reading always
     takes a default: `service.store.user.get("rowsPerPage", 25)`.
5. **Return correctly.** PREDICATE **must** `return <boolean>` (a bare `true` in the template is discarded — see
   [08](08-groovy-rules-and-context.md), §"Templates and return semantics"). EXECUTION may return
   anything (map, list, scalar) or nothing. VALIDATION returns nothing.
6. **Do not access realm/client** — `SecurityException`. The proxies are already tenant-scoped.

---

## Gotchas

- **Choices rules MUST convert to option pairs.** A dropdown / tree-picker / autocomplete source that returns a
  raw `find`/`findAll` entity list renders **"No results found"** and hides its **Show Nav** affordance (`validate`
  now errors on it). End with `service.global.conversion.toSelectOptions*` (dropdown/tree; `toSelectOptionsLocalized`
  for a localized display column) or `toAutoCompleteOptions*` (autocomplete). See [02-form-controls-reference.md](02-form-controls-reference.md) §4a.
- **`findAll` partial-map trap.** Passing a **PARTIAL** param map to the default multi-optional `findAll`
  (e.g. `findAll([active:"true", rowsInPage])`) leaves an unbound param as `$1 IS NULL` → Postgres
  `could not determine data type of parameter $1`. Use `find([rowsInPage, pageNumber:0])` or `findAll([:])`
  (all keys absent); never a partial column-filter map to a naive `findAll`. See [02-form-controls-reference.md](02-form-controls-reference.md) §4a.
- **`attrs` is `JsonNode`, not raw values.** `attrs.get('x')` returns a `JsonNode`; use
  `.asInt()`/`.asText()`/`.numberValue()`/`.isNull()` (`GroovyExecutionRule.java`; example
  `Find — Bill of Materials`). A direct comparison `attrs.get('x') == 5` will not work.
- **`param` is empty outside delegation.** It is populated only when a CRUD GROOVY method is invoked via delegation
  (`ReactorServiceImpl.groovy` places `__methodParams`, `GroovyExecutionRule.java` unwraps). In
  a normal rule `param == [:]`. The idiom `def filter = param ?: [:]`.
- **`filter` is not a binding.** It is your local variable. The only `filter` in the API is
  `service.global.collection.filter.*`.
- **`service.rimm.query(...)` in hints shows `realmName, clientName`** in the signature — that is the signature of the
  underlying `RimmService`. In the script call the overridden proxy variants **without** realm/client:
  `service.rimm.query("name")`, `service.rimm.run([...])` (`RimmServiceProxy.java`).
- **`service.notification` without `.push`/`.mail`** does not work: the `send*` methods live on
  `service.notification.push.*`, emails — on `service.notification.mail.<alias>(...)`. (Note the full path in the
  §2.5 example: `service.notification.push.sendAlert(...)`.)
- **`service.rule("Name")` resolves by NAME.** Duplicate rule names → non-deterministic selection. Keep names
  unique.
- **`service.enums['Name']` returns `null` if the enum is not registered** (`EnumsWrapper.getAt` returns null)
  — it does not throw. Check for null before `.list()`.
- **`service.actionId`/`actionName` = null** if the rule was not invoked by an action button (fetch, dropdown,
  validation). Do not rely on them in fetch rules.
- **PREDICATE: only `return <Boolean>`.** Because of the template's trailer `if(true){return null;}`
  (`ExecutionRuleTemplate.groovy`), a bare `true` as the last line is discarded → `null` → "must return
  Boolean". Always write `return`.
- **`inject(...)` is heavily restricted.** Most beans are blocked (`ExecutionRuleTemplate.groovy`).
  Do not count on pulling `reactorService`/`crudReactor` through it — use `service.crud.*`.
- **`service.global.*` is a server-editable catalog (YAML).** The function list = the current
  `globalFunctions.yaml`. When the platform version changes, cross-check against the file, not this table.
- **`service.redirectPage` takes the path WITHOUT the organisation** and refuses a full URL. It navigates after
  the rule returns, so write anything the destination needs into `service.store.session` first. §2.15.
- **`service.store.*` and the attribute scopes are different axes, not better and worse.** An attribute belongs
  to a document — it travels along a CASE (persisted in the process's variables between nodes) or lives while a
  form is open, and with neither it lasts one execution. The store belongs to the session or to the person and
  is reachable from any rule. Do not rewrite a workflow's `context.data.setAttr` publish into the store: nothing
  joins a store key to a case. §2.14.
- **`service.store.session` is empty in a scheduler, a Kafka handler, an MCP call and a headless service
  task**, and `service.store.user` is empty wherever there is no acting user. In both cases `put` stores
  nothing and `get` answers `null` — never an exception, and never a half-working store. Pick `user` for
  anything a scheduler must remember. §2.14.

---

## What is NOT there (do not make it up)

Verified against `ServiceWrapper` (the only backing of `service`) and the hints tree — and you can re-verify on any
project with `jq` over `ruleScriptStr` and `methods[].script`: **the following namespaces do NOT exist in the
language** —

- **`service.feign.*`** — not a `ServiceWrapper` field, not in hints, never resolvable at runtime. External HTTP —
  via `service.global.rest.*` (Part 2.2). ⚠️ There is no separate "feign clients" API for scripts.
- **`service.integration.callExternal(...)`** — does not exist. Calling external services = `service.global.rest.*`
  (REST) or `service.crud.<alias>.<method>()` (an external system wrapped by a dynamic CRUD/integration).
- **`service.crudimport.*`** — not a `ServiceWrapper` field and not in hints. CRUD-import is a UI feature/controller
  (`CrudImportController`), not a Groovy-script binding.
- **`service.localization.*` / the `localization` binding** — does not exist. The session locale is available via
  `service.global.locale.getKey()`/`getLocale()`; localized options — via
  `service.global.conversion.toSelectOptionsLocalized(...)`.

The namespaces most likely to be **guessed by analogy** — also confirmed absent:

- **`service.data`** — does not exist. `data` is a **top-level binding** (`data.getAttr(...)`) and `context.data.*`
  (global attrs) — [08](08-groovy-rules-and-context.md); a reader who knows `context.data` may wrongly try
  `service.data`. There is no `service.data`.
- **`service.http` / `service.sql`** — no such namespaces. HTTP is `service.global.rest.*` (§2.2); SQL / data access
  is `service.crud.<alias>.<method>()` (§2.1) or `service.rimm.*` (§2.4).
- **`service.process`** — no such binding. `service.workflow` is where processes live, and it has exactly eight
  members: `start` (§2.12), and `list` / `actions` / `startActions` / `contextData` / `complete` / `cancel` /
  `currentProcessIdentifier` (§2.13). There is no `service.workflow.startProcess(...)`, no
  `getProcess(...)`, no `raiseMessage(...)` — those appear in older notes and were never implemented; use
  `list(...)` to find a case and `contextData(...)` to read one. `cancel` and `currentProcessIdentifier` are recent: on an older platform build they are absent, and the whole namespace is offered
  only to EXECUTION rules and CRUD Groovy methods.
  Process-access mutation is `service.access.*` (§2.7, operating on `attrs.processIdentifier` — i.e. the
  process the rule is ALREADY in, never one it just started).
- **`service.mail` (bare)** — must be `service.notification.mail.<alias>(...)` (§2.5); neither `service.mail` nor
  `service.notification` alone (without `.push`/`.mail`) resolves anything.
- **`service.redirect` / `service.navigate` / `service.goToPage` / `service.setResponsePage`** — none of these
  exist. There is exactly ONE way to move a browser and it is `service.redirectPage("alias/page")` (§2.15),
  EXECUTION rules only, taking an in-app path and never a URL. There is no `service.redirectUrl` and no way to
  open an external site from a rule.
- **`service.session` / `service.cache` / `service.prefs` / `service.state` / `service.storage`** — none of these
  exist. There is exactly ONE key/value namespace and it is `service.store`, with exactly two members:
  `service.store.session` and `service.store.user` (§2.14). `service.store.global` and `service.store.project`
  do not exist either — a value shared by everybody is a CRUD row, not a store key.

If you need one of these capabilities — it is implemented with the existing means (`service.global.rest`,
`service.crud`, `service.rimm`, `service.global.locale`/`conversion.*`), not an imaginary namespace. Everything that is actually
available is listed in Part 2 and reflected in `ServiceWrapper.java` + `HintsService.buildServiceMap`
(`HintsService.java`).
