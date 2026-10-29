# 16 — Full Groovy `service.*` capability surface (what you can actually do in a script)

> 📐 **Field evidence — which service calls are load-bearing:** [03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md) · [06-security-and-roles.md](references/06-security-and-roles.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What this is / when to use

[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) describes the **rule types** (`PREDICATE`/`EXECUTION_RULE`/`VALIDATION_RULE`),
their templates and the **context model** (`context.<ctx>.<crud>.data.get()`). This document answers a different question:
**what operations are available at all inside a Groovy script** — the entire set of bindings and `service.*` namespaces,
with real method signatures and worked examples. This is the "capability surface":
a reference for "are all the Groovy capabilities accounted for".

Open this document when you write **any** `rule.ruleScriptStr` or a GROOVY method of a dynamic CRUD
(`dynamic-cruds.json.cruds[].methods[].script`, see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md))
and need to know: how to call a CRUD method, how to convert a list into dropdown options, how to check a role, how to
send a notification/email/PDF, how to invoke another rule, how to read the enum registry, and so on.

> **The single authoritative source of the API** is the **hints tree**, which the server assembles for the rule
> editor.
> This exact structure feeds the rule editor's autocomplete (endpoint
> `POST /api/hints/tenant/{realm}/{client}/getRuleHints`
> and the MCP tool `getRuleHints`). The entire §"service.\*" below is
> a direct breakdown of this assembly. If something is not in the hints tree and not on the `service` object — it does not exist
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

The Groovy script from `rule.ruleScriptStr` is spliced into the template's `execute()` at the `{{RULE_SCRIPT}}` placeholder.
Before that, the runtime places a set of variables into the binding. The full list of what the script "sees":

| Binding | Type | What it is |
|---|---|---|
| `context` | the context model (via `def context = this` in the template) | The entry point into the context model: `context.<ctxAlias>.<crudAlias>.data.get()`, `context.<ctx>.data.getAttr(...)`, `context.data.*` (global attrs). Full breakdown — [08](08-groovy-rules-and-context.md). |
| `service` | the capability object | The main capability namespace — all of Part 2. |
| `param` | `Map<String,Object>` | Parameters of a **delegated** GROOVY method of a CRUD. Populated from the `__methodParams` marker, which the platform places on a delegated call. Outside delegation — an empty map `[:]`. |
| `attrs` | `Map<String, JsonNode>` (Jackson) | Arbitrary attributes passed by the caller: CRUD-table pagination/filters (`rowsInPage`, `pageNumber`, filter keys), `processIdentifier`, `__actionId`/`__actionName`, `filterBy`, etc.; in a rule the workflow engine runs (a service task, a sequence flow) also EVERY process variable (`owner`, `processEntityId`, `userActionId`, …). **Values are `JsonNode`**, so they are read as `attrs.get('rowsInPage')?.asInt()`, `attrs.get('filterBy')` (text). ⛔ Never WRITE `attrs.put('k', 'v')`: a value that is not a `JsonNode` makes `getAttr` fail and the rule fail AFTER it ran. Write through `context.data.setAttr('k', v)`. |
| `contextIdentifiers` | `List<String>` | Identifiers of the contexts bound to the rule (`rule.contextIdentifiers`). |
| `contextDataMap` | `Map` of context data, keyed by context identifier | Low-level access to context-data (normally you use `context.*` instead). |
| `userId` | `String` | Whoever the CALLER says the user is — and callers say different things: a row id from a screen, the owner's e-mail in a service task, the authentication name on a REST call, the acting e-mail in a delegated CRUD method. ⛔ Never use it as an identity: the person is `service.security.user().email`. realm/client are **hidden** deliberately. |
| `data` | the global-attributes object | Alias for `context.data`: `data.getAttr("k")`, `data.setAttr("k", v)`, `data.foo` (read) / `data.foo = v` (write). |
| `currentData` | CRUD-data node \| `null` | The current item of a **nested** form (List-item): `currentData.get()`, `currentData.put(obj)`, `currentData.setField('a.b', v)`, `currentData.getField('col', Type.class)`, `currentData.hasField('col')`. In the parent form `currentData` ITSELF is `null` — so `currentData.get()` throws a `NullPointerException` there (the editor's hint says "returns null in parent forms"; it does not): guard with `if (currentData != null)`. ⚠️ `currentData.getAttr(...)`/`setAttr(...)` are offered by the editor's autocomplete but do **NOT** exist on a CRUD-data node — calling them throws `MissingMethodException`. Attributes live on the context/global scopes (`context.<ctx>.data.getAttr` / `context.data.getAttr`), never on a CRUD-data node. |
| `validation` | message collector | **Only in VALIDATION_RULE.** Accumulator of errors/warnings. |
| `addError` / `addWarning` / `addFieldError` / `addFieldWarning` | template methods | **Only in VALIDATION_RULE.** Delegate to `validation.*` (see Part 3). |
| `service.validation` | — | ⛔ **Does not exist.** The collector is the binding `validation` (row above) — never a member of `service`. Written as `service.validation.addFieldError(…)` a rule dies on its first violation with `Validation rule execution failed: validation` instead of your message. `mrjun validate` rejects it. (`service.global.validation.*` below are unrelated helper functions.) |
| `inject(String beanName)` | template method | A platform service by name — **not a sandbox**. `rimmService` returns `service.rimm`; `contextService`, `reactorService`, `ruleService` and `crudReactor` throw `SecurityException`; a short list (`emailService`, `notificationService`, `validationService`, `calculationService`, `formatterService`, `dateService`) and any `*Helper`/`*Util` name are returned; ANY OTHER name prints a warning and is returned too. Do not use it: everything a rule needs is on `service.*`, and a raw service object bypasses the realm/client the proxies add. |

> **Security invariant.** `realm` and `client` are **inaccessible** to the script: accessing them throws
> `SecurityException`. All `service.*` proxies (rimm/security/notification/crud)
> already know realm/client internally and substitute them themselves — so in the script you **do not pass** them, even though the hints
> for `service.rimm.query(...)` formally have `realmName/clientName` in the signature (that is the signature of the underlying
> service, while the script-side proxy overrides the 1-/2-arg variants without realm/client).

> **⚠️ Caveat — the `inject()` block-list is not the only path.** **Every** field of `service` is a reachable
> Groovy property — including `service.ruleService`
> `service.ruleExecutorReactor` and `service.contextData`, all populated for every executor.
> `service.ruleService` hands back the **same** raw rule-service object that
> `inject("ruleService")` refuses with `SecurityException`, and `service.ruleExecutorReactor`/`service.contextData`
> likewise reach the raw rule-execution reactor / context-data object. So the `inject()` block-list only guards the
> `inject()` path, not these getters — the "these beans are blocked" framing holds for `inject()` alone. Do not
> call them: for rule reuse use `service.rule("Name")` (§2.10); the raw beans are internal, unsupported surface.

### `filter` is NOT a binding

You will often encounter `def filter = [ ... ]` in fetch rules (see the "Find — …" example below). This is a
**local variable** that the script assembles itself from `attrs`, not a runtime injection. The only same-named
`filter` in hints is the subgroup `service.global.collection.filter.*` (list-filtering utilities,
Part 2 §global). Do not confuse them.

---

## Part 2 — `service.*` namespaces

`service` is the capability object. Its fields and sub-proxies:

```
service
 ├─ crud          → service.crud.<alias>.<method>(args)
 ├─ global        → service.global.<group>.<fn>(args)
 ├─ security      → .user() · .hasAny…()
 │                  .users.create/get/list/update/setEnabled/delete/addRoleGroup/removeRoleGroup/invite
 │                  .roleGroups.list/get/create/update/delete/members
 │                                                              (users / roleGroups — EXECUTION rules and CRUD GROOVY methods only)
 ├─ rimm          → service.rimm.query(...)/run(...)
 ├─ notification  → .push.send…() / .mail.<alias>(...)
 ├─ report        → service.report.pdf.get/download/email/push
 ├─ access        → service.access.addRoleAccess(...)…
 ├─ quota         → service.quota.mail.allowedPerDay…
 ├─ enums         → service.enums['Name'].list()
 ├─ workflow      → .start(id, ctx[, opts]) · .list / .actions / .startActions
 │                  .contextData / .complete
 ├─ store         → .session.get/put(...) · .user.get/put(...)
 ├─ rule(name)    → service.rule("Other Rule")
 ├─ redirectPage  → service.redirectPage("alias/page")          EXECUTION only
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

The most frequent way to perform a business operation. `service.crud.<alias>` is resolved as follows:
when a context is **bound**, `alias` must be in the `crudAliases` of one of the
contexts; when **no** contexts are present — it is resolved across the entire CRUD registry of the realm/client.
Then `.<method>(args)` is executed as a call of that CRUD method over RSocket into the integration.

**Which `method`** values are available — those are the `methods[]` of the specific CRUD in `dynamic-cruds.json` (the standard set
`find`/`findAll`/`count`/`get`/`create`/`update`/`delete` + custom ones), see
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md). In hints they are fetched from the
CRUD's integration.

- **The argument** is usually a Groovy map (`[rowsInPage, pageNumber: 0]`) or a scalar id.
- **`find`** (GROOVY method) returns a page: `{content, totalElements, totalPages, pageNumber}` — see its
  implementation from the export below.
- **`create`/`update`** accept a DTO map; **`delete`** — an id.
- `context.<ctx>.<alias>.service.<method>(args)` — the **equivalent** context-dependent syntax (the same
  call). `service.crud.<alias>` is shorter and preferred.

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
> CRUD-table UI shows the rule error message verbatim
> (before-start, before-complete, create-flow; a catch-all wraps it). This is the **only** way to block an action *with a message*: a **PREDICATE** can
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
> to a compiled Java CRUD of the project; on a **dynamic** one — to the `methods[]` from
> `dynamic-cruds.json`. The call syntax is identical; see [11](11-business-logic-dynamic-crud.md).

> **Not re-checked.** A method's execution access is checked only at the door a call ENTERS the platform through
> (`ctx.callBl`, a table, a form, the public API, MCP). Called from a running rule, `service.crud.<alias>.<method>(...)`
> runs on the platform's authority — the rule already passed its own door. So a rule opened to anyone may write
> through a method that stays at its default (signed-in users); never open the method to make a public rule work.
> [08 §"Execution access"](08-groovy-rules-and-context.md), [11 §"Execution access"](11-business-logic-dynamic-crud.md).

---

### 2.2 `service.global.*` — utility library (YAML functions + REST)

`service.global` is the library of utility functions. Each function is a Groovy closure, compiled from
the server's function catalog (a YAML file) at startup. Plus
a REST client is registered. **This is a server-editable catalog** — the exact list = the contents of that
YAML. The full current catalog:

| Path | Signature (params → returns) | Purpose |
|---|---|---|
| `service.global.locale.getKey` | `() → String` | Session locale key (`en_US`, `ru_RU`). |
| `service.global.locale.getLocale` | `() → Locale` | Session `java.util.Locale`. |
| `service.global.locale.getLanguage` | `() → String` | Session language (`en`, `ru`); `null` without a session locale. |
| `service.global.locale.message` | `(Object text, Object... args) → String` | The text in the caller's language — machine-translated once by the platform, then remembered (the same translation memory as an html component's `ctx.t('…')`; a rule does not know the project's default language, so the translator detects the text's language — a very short text can be read as another language, so write a few words, not one). Only a string literal of the running rule is translated; a text built at run time is returned as written. `{0}`, `{1}`… from `args`, `{name}` from one Map or from named arguments (`message('{who} saved', who: name)`), filled after translating; a Map of your own translations (`[ru_RU: '…', en: '…']`) is used as given — the caller's locale, then its language, then any key of that language, then the first value. Without a session locale: a text comes back as written, a Map gives its first value. |
| `service.global.locale.localized` | `(Object row, String field, String localeKey=null) → Object` | A CRUD row's localized field: `row.localize[field]` in the locale, then its language, then any key of that language, else `row[field]`. |

**`message` — what to write.** The text in the project's DEFAULT language, as ONE string literal of the rule with
placeholders for the values: `service.global.locale.message('Record {0} is closed', row.number)`. Only the rule's own
literals are sent to the translator — `'Record ' + n + ' is closed'`, `"Record ${n} is closed"` or a text taken from
input is returned as written, because translating it would make a paid translation, a stored row and a copy of
somebody's input for every value (offline `validate` WARNs on the glued and the `${…}` forms). A literal assigned to a
variable first (`def m = 'Record {0} is closed'; message(m, n)`) counts — it is a literal of the rule. For a reader of
the text's own language the translator hands it back unchanged. Where the session locale is null (the ⛔ below: row
actions, persist hooks, schedulers) it comes back as written too — keep the all-languages string there
([20](20-localization.md)).

> ⛔ **Where the session locale is actually populated** (measured on a live stand, 2026-10-15, hy_AM/ru_RU/en_US):
> a form's **VALIDATION** rule and a dropdown's **choices** rule get it (`getKey()` = `hy_AM`…); a register's **row-action**
> rule (`onBeforeComplete…`, run by the separate *executor* service) gets **null** from `getKey()`/`getLocale()` (and
> `LocaleContextHolder` = the server's `en`), and so do persist hooks and schedulers. A message that must follow the
> user's language therefore needs a fallback — `def MSG = { hy, en, ru -> … getKey() … ; fallback hy + ' / ' + en + ' / ' + ru }`
> — and a user-visible refusal thrown from a row action will carry every language it has. Probe before promising: throw
> `'DBG ' + service.global.locale.getKey()` from a temporary rule body and read the toast.

| Path | Signature (params → returns) | Purpose |
|---|---|---|
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
| `service.global.formatting.number.format` | `(Number value, Integer decimals=null) → String` | Grouped in the caller's language (`1 234,5`; the server's without a session locale); `decimals` = exactly that many fraction digits. `formatCurrency`/`formatPercent` format in the server's language. |
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
| `service.global.rest.get` / `post` / `put` / `delete` / `patch` / `head` / `options` | `(String url)` or `(String url, Map options) → response` | HTTP calls (see below). |

> **Choices-rule terminal call.** For **any** choices rule (dropdown / tree-picker / autocomplete source) the
> **last statement** must be one of these four conversions — the raw CRUD result is never a valid return. Match
> the function to the control: `toSelectOptions*` for dropdowns and tree pickers, `toAutoCompleteOptions*` for
> autocomplete; use the `*Localized` variant when the display column is localized. Full contract:
> [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

**`toSelectOptions*` — output format.** They return a "flat" list of pairs `[[key:keyField, value:...],
[key:displayField, value:...], ...]` — 2 elements per row of the source data.
This is exactly the format that dropdown controls expect. The `Localized` variants read the localized value from
`item[localizationFieldName][displayField][localeKey]` with a fallback to the base field; the default locale
is taken from the session.

> **⚠️ INVARIANT — a choices rule MUST return this pair-list.** A dropdown / tree-picker / autocomplete choices
> rule MUST end by returning this converted pair-list as its **final statement**. Returning the raw entity list
> from `find`/`findAll` (e.g. `return service.crud.X.findAll([...]) ?: []`) makes the control render
> **"No results found"** AND hides its **Show Nav** affordance — a silent failure (`validate` now errors on it).
> Dropdown / tree → `toSelectOptions(list,"<key>","<display>")` (localized display column →
> `toSelectOptionsLocalized`); autocomplete → `toAutoCompleteOptions(list,"<display>")`. Full recipe:
> [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

**`service.global.rest.*`** — an HTTP client. The response
has fields: `status` (int), `ok` (boolean), `body` (parsed JSON Map/List **or** String),
`text` (raw String), `headers` (Map) — the same descriptions are shown in the editor hints.
`options` map: `[headers: [...], body: [...], query: [...], timeout: 30000]` — `timeout` is in
**milliseconds**; omitted it defaults to 30 000 ms and a larger value is capped at 120 000 ms.
Further built-in limits (response size, blocked private/link-local addresses) are
platform configuration; treat the numbers as shipped defaults, not a contract.

⛔ **A non-2xx answer does NOT throw** — it comes back with `ok == false` and the status. Only a timeout, an I/O
error or a refused (private / link-local) host throws. So every call checks `ok` (or `status`) itself, and a rule
that must stop on a failed call says so: `if (!r.ok) { throw new RuntimeException("<words for the user>") }`.
A Map or List `body` is sent as JSON. Helpers on the response: `getHeader(name)` (case-insensitive),
`getHeaderValues(name)`, `isRedirect()`, `isClientError()`, `isServerError()`.

**Numbers, money and lists — the traps of the utility library:**

| Call | Trap | Do instead |
|---|---|---|
| `formatting.number.round(x, n)` | returns a `Double` — binary floating point — not a `BigDecimal` | money and quantities: `(x as BigDecimal).setScale(2, java.math.RoundingMode.HALF_UP)` (half away from zero, as the database's `ROUND` on numeric) |
| `context.data.getAttr('k')` on a decimal | returns a `Double` | `getAttr('k') as BigDecimal` before any arithmetic that must be exact |
| `formatting.number.formatCurrency(x, code)` | formats with the SERVER's locale, not the user's | format in the screen or the template where the locale is known |
| `collection.transform.sortBy(list, …)`, `unique(list)` | sort / de-duplicate the list you pass IN — the caller's list changes | pass a copy: `sortBy(new ArrayList(list), …)` |
| `collection.aggregate.sum(list, field)` over text values | concatenates the strings | convert first: `list.collect { it.amount as BigDecimal }.sum()` |
| `formatting.date.*` | `java.util.Date` + `SimpleDateFormat` only | for dates in SQL and documents, pass ISO text and let the query cast it |

**Worked example** (`invoice statuses dropdown`):

```groovy
def list = context.finance_context.invoice_statuses_cruid.service.find([
  rowsInPage: 1000,
  pageNumber: 0
])
return service.global.conversion.toSelectOptionsLocalized(list, "id", "statusName")
```

---

### 2.3 `service.security.*` — the current user, role checks, and the project's people

Three layers under one name, with different rules about where they work:

| Layer | Members | Where it works |
|---|---|---|
| **the person running the rule** | `user()`, `hasAnyRole`, `hasAllRoles`, `hasAnyRoleGroup`, `hasAllRoleGroups` | every rule type |
| **the project's people** (§2.3.1) | `service.security.users.*` | EXECUTION rules and CRUD GROOVY methods only |
| **the project's role groups** (§2.3.2) | `service.security.roleGroups.*` | EXECUTION rules and CRUD GROOVY methods only |

Realm and client are already inside; `users` and `roleGroups` exist only in EXECUTION rules and CRUD GROOVY methods.

| Method | Signature | Return / behavior |
|---|---|---|
| `service.security.user()` | `{id, email, firstName, lastName} user()` | An object `{id, email, firstName, lastName}` — simply assembled from already-stored fields, does no look-up/cache itself. The `firstName/lastName` fields are populated by the runtime **before the rule starts**. |
| `service.security.hasAnyRole(...)` | `boolean hasAnyRole(String... roles)` | true if the user has **at least one** of the roles. |
| `service.security.hasAllRoles(...)` | `boolean hasAllRoles(String... roles)` | true if they have **all** roles. |
| `service.security.hasAnyRoleGroup(...)` | `boolean hasAnyRoleGroup(String... roleGroups)` | true if they have **at least one** role-group. |
| `service.security.hasAllRoleGroups(...)` | `boolean hasAllRoleGroups(String... roleGroups)` | true if they have **all** role-groups. |

> All checks are **fail-closed** and ask about the user's E-MAIL (never `userId`): with no e-mail, or no securityClient/realm/client — they return `false`
> rather than throwing.

> **There is no `service.security.roles()` and nothing that lists the current user's own role groups.** The checks
> above answer yes/no about the person running the rule, by name. To see which role groups SOMEBODY holds, read it off the
> person: `service.security.users.get("<e-mail>").roleGroups` (§2.3.1, EXECUTION rules only). In a predicate there
> is nothing to list — test membership by name (`service.security.hasAnyRoleGroup("X")`) per candidate.
> `service.security.roleGroups` (the property, plural, §2.3.2) is the project's role-group CATALOGUE, not the
> current user's.

**Worked example** — a visibility predicate (`Is Compliance Head`):

```groovy
return service.security.hasAnyRoleGroup("Compliance Head") || service.security.hasAnyRoleGroup("Author")
```

**Worked example** — `user()` in an init rule (`Invoice Init`):
`inv.createdBy = service.security.user().email`.

#### 2.3.1 `service.security.users` — add, find, rename, disable and remove the project's people

```
service.security.users
    .create(Map options)                  // add a person - WITH a password, or INVITED by e-mail
    .get(String email)                    // a member as a map, or null
    .list()                               // every member
    .update(String email, Map changes)    // firstName and/or lastName
    .setEnabled(String email, boolean enabled)
    .delete(String email)                 // out of THIS project; the account survives
    .addRoleGroup(String email, String roleGroup)
    .removeRoleGroup(String email, String roleGroup)
    .invite(String email)                 // (re)send the "choose your password" e-mail
```

Everything is keyed by **e-mail** — the only identity a script can write down — and acts on **this project's
members only**. A person who belongs to another project of the same organisation is not found here, and the
platform's own two accounts (the Developer and the Author the platform ships with) are invisible and untouchable:
no call finds them, changes them or hands them a role group, and `create` refuses their addresses.

**Where it works.** EXECUTION rules and CRUD GROOVY methods — everywhere a rule can run: a button, a
scheduler, a workflow service task, a public-API call. In a PREDICATE and in a VALIDATION rule the namespace is
present but **every member throws** `service.security.users.<member> is not available in predicates …` (`… in validation rules …` there), because
those are evaluated for their answer, possibly once per row. **The refusal follows the call**: an EXECUTION rule or
CRUD GROOVY method that a predicate or validation rule calls (`service.rule("…")`, `service.crud.<alias>.<method>()`)
throws `… is not available in rules called from predicates` — a predicate cannot borrow the people-managing rule next
door. The editor does not offer the namespace in a predicate either, and `validate` ERRORs on a DIRECT use
([19](19-build-decision-procedure.md) Phase 5; it does not follow calls).

**Who is allowed — the rule's own access, nothing else.** The project's *User Management* and *Role Management*
screens are gated by Settings → Accesses. A rule is **not**: whoever was allowed to run the rule has, through it,
whatever the rule does, exactly as with every other `service.*` call
([11 §"Execution access"](11-business-logic-dynamic-crud.md): *once a rule passed its own door, everything its
code calls is not re-checked*). Two consequences, and the second is the one that bites:

* It does not matter whether the person who triggers the rule is an author, holds any role group, or is signed in
  as an ordinary user — only that the **rule's execution access** let them run it. A rule can therefore onboard
  somebody on behalf of a clerk who has no User Management access at all. That is the point.
* ⛔ **The default execution access is "any signed-in user".** A rule that adds people, left at the default, can be
  run by every account of the project from the browser console, whatever button hides it. Set the rule's access to
  the role group(s) that administer people (`mrjun.py rule access <rule> --role-group "<Group>"`; for a CRUD GROOVY
  method, `mrjun.py crud method-access` — [11](11-business-logic-dynamic-crud.md) §"Execution access"), and put the
  button behind a predicate on the same group. `validate` WARNs on the default and ERRORs on `publicAccess: true`.
* ⛔ **The gate is the OUTERMOST rule or method a caller can start — not the one that holds the call.** A rule that
  `service.rule("Invite")`s, or `service.crud.<alias>.<method>()`s, another is not stopped by that one's access: the
  inner door is not consulted again. So restricting an inner "Invite" rule or `inviteUser` method protects it only
  from callers who reach it DIRECTLY; the page's action rule that calls it must be restricted to the same group, and
  so must every other rule or method that calls it. `validate` follows literal `service.rule("Name")` and
  `service.crud.<alias>.<method>(` calls and judges the callers too; a computed name is not followed.
* ⚠️ **Rules that nobody clicks.** A rule that runs as a workflow service task or from a scheduler has no browser
  user: the engine runs it as itself, so a restricted access does not "protect" it there — what protects it is that
  only the process definition or the schedule starts it. Test such a rule on the live project; do not assume the
  group gate applies.

**`create` — two ways to add a person.**

```groovy
// 1. INVITED: the person gets an e-mail with a link and chooses their own password.
def jane = service.security.users.create(
        email: "jane@acme-corp.com", firstName: "Jane", lastName: "Roe",
        roleGroups: ["Buyers"])

// 2. WITH A PASSWORD: you chose the way in, so nothing is mailed.
def generated = UUID.randomUUID().toString() + UUID.randomUUID().toString()   // or any long generated value
service.security.users.create(
        email: "scanner-01@acme-corp.com", firstName: "Scanner", lastName: "Station",
        password: generated, roleGroups: ["Warehouse"])
```

| Option | | |
|---|---|---|
| `email`, `firstName`, `lastName` | required | the address is lower-cased; it is the person's identity from here on |
| `password` | optional | **present ⇒ created with it, nothing mailed. Absent or blank ⇒ INVITED.** Passed on exactly as written, spaces included. ⛔ A literal in the script is stored in the rule text, which travels with every export — use it for test and machine accounts and prefer an invitation for people; never write a real person's password into a rule |
| `roleGroups` | optional | **names** of this project's role groups (matched ignoring case, like `hasAnyRoleGroup`). Every name must exist — a typo is refused with the list of the groups that do |
| `locale` | optional | language of the set-password page the invitation opens (`"hy"`, `"ru_RU"`); default the rule's own language, else the project's default |

Any other key is **refused by name** (`unknown option 'roleGroup'`): a misspelt `roleGroups` would otherwise create
the person with no groups and no error. The e-mail must be a **plain address** — exactly one `local@domain`, no
spaces or control characters, none of `/ \ ? # % ; < > " ,` — and names are **text, not markup** (no `<` or `>`, no
control characters, at most 255 characters): both travel into URLs, logs and the invitation e-mail. A rule that takes
them from a form should still check them; the refusal is the last wall, not the first.

*Invited* means: the account is created with a password nobody knows, and an e-mail built from the project's
**`userRegistration` system mail template** ([15](15-pdf-and-mail.md), placeholders `firstName` and
`activationLink`) is queued. The person follows the link, chooses a password and is signed in. A person has one
live link at a time: it stays valid until the next invitation to them replaces it, so re-inviting is also how a
link that went astray is retired. The mail is **queued, not delivered** — `create` returns once it is accepted, and an invitation that the project's
daily e-mail quota (or the mail provider) later refuses is dropped without the rule ever hearing of it. If it cannot
be QUEUED, the call throws, and the message says the account **was** created and names `invite(...)` to send it again.

*Refused before anything is created:* an unknown role group; a role group that carries `admin` or `nct_author` (§2.3.3); an
address that is **already a member** of this project (so a rule run twice does not invite twice — test with `get`
first); one of **the platform's own two accounts**; an **undeliverable address with no password** (`*.invalid`, `*.test`, `*.example`, `*.localhost`,
`example.com/.net/.org` can never receive the invitation, so they need a password — that is how test accounts are
made); the project's **user quota** (`Maximum number of users (N) reached for this project`).

*An address that already has an account in the organisation* (it belongs to another project of it) is **added to
this project and keeps its own password** — the `password` you passed is ignored, and the result says so
(`existingAccount: true`). Without a `password` such a person is **still invited** (`invited: true`): the e-mail is
how they learn they were added, and its link lets them choose a NEW password for the whole account, every project
of the organisation included. The organisation's accounts are shared by all its projects, which is also why `update`
cannot change a password (below).

**What it returns** — the new member, as a map, plus two flags: `invited` (an invitation e-mail was queued) and
`existingAccount` (the address already had an account in the organisation; the platform's own answer, not a guess):

```groovy
[email: "jane@acme-corp.com", firstName: "Jane", lastName: "Roe", enabled: true,
 roleGroups: ["Buyers"], invited: true, existingAccount: false]
```

There is no internal id in any of these maps, on purpose; the e-mail is the key for every other call.

**Reading.**

| Call | Answers |
|---|---|
| `get("jane@acme-corp.com")` | the member map, or `null` — never an exception for "not found" |
| `list()` | every member, platform accounts excluded. It costs a lookup per member behind the scenes: use it to find or report, never inside a loop over rows |

**Changing.**

| Call | Does | Leaves alone |
|---|---|---|
| `update(email, [firstName: "Janet", lastName: "Doe"])` — or `update(email, firstName: "Janet")` | renames. What you do not mention stays | role groups, password, the address. Names belong to the **organisation**: the person is renamed in every project of it |
| `setEnabled(email, false)` | stops them signing in **and ends the sessions the identity provider holds for them**; `true` lets them in again | role groups, history. ⚠️ The switch is the **organisation's**: a person disabled here cannot sign in to *any* project of it. ⚠️ A token already issued keeps working until it expires (hours, not seconds), so this is "no new sign-in", not "gone this instant" |
| `addRoleGroup(email, "Buyers")` | gives one more group; idempotent | the groups they already hold |
| `removeRoleGroup(email, "Buyers")` | takes one away; idempotent. Roles another of their groups still grants are kept | the others |
| `invite(email)` | queues the e-mail with a fresh link (it replaces the earlier one) — for somebody who lost the first one, or needs a **new password, which a rule may not set for them**. Refused for an address no mail can reach. Counts against the project's daily e-mail quota | everything else |
| `delete(email)` | takes them **out of this project**: their role groups here, their membership, and their `service.store.user` rows (§2.14). `false` when they were not a member. Refused for the project's **owner** (the owner is a property of the project, not a membership). Open sessions are not ended — `setEnabled(email, false)` first if you need that | **the account** — they may belong to other projects, and can be added again |

⛔ There is no way to set an existing account's password from a rule, and no way to change an address: accounts
are shared by the whole organisation, so either would let one project take over a person's sign-in to all the
others. A rule that needs somebody to have a new password calls `invite(email)` — the link goes to the mailbox
that owns the address.

⛔ There is no way to delete the account itself (the person from the organisation). `delete` is "remove from this
project", which is what the User Management screen's Delete does too.

**Errors** are ordinary exceptions with a plain sentence — `service.security.users.create: jane@… is already a
member of this project …`, `service.security.users.create failed: Maximum number of users (5) reached for this
project` — so `try { … } catch (Exception e) { … e.message … }` can show them. Nothing is half-done on a refusal
that happens before the account exists, and a password the organisation's password policy refuses
(`… The password was not accepted: Invalid password: minimum length 8.`) creates nothing: the account is removed
again, so the retry starts clean.

**Worked example — an approved request becomes an account** (an EXECUTION rule behind an action; access:
the role group that approves):

```groovy
def request = context.hr.request.data.get()
// The group comes from a FORM FIELD: never pass it on as it is. An explicit list is the check that cannot be
// forgotten, and it is the list the form's dropdown must be filled from (not from roleGroups.list()).
def GRANTABLE = ["Buyers", "Warehouse", "Accountants"]
if (!GRANTABLE.contains(request.roleGroup)) {
    throw new IllegalArgumentException("Role group '${request.roleGroup}' cannot be requested here")
}
def existing = service.security.users.get(request.workEmail)
if (existing == null) {
    service.security.users.create(
            email: request.workEmail, firstName: request.firstName, lastName: request.lastName,
            roleGroups: [request.roleGroup])                 // invited by e-mail
} else if (!existing.roleGroups.contains(request.roleGroup)) {
    service.security.users.addRoleGroup(request.workEmail, request.roleGroup)
}
```

**Worked example — a leaver:**

```groovy
service.security.users.removeRoleGroup(leaver.email, "Approvers")
service.security.users.setEnabled(leaver.email, false)     // no new sign-in; their identity-provider sessions end
```

**Timing — nothing here is instant, and the delays differ by who is asking.** Page and action access in the web
tier follows a role-group change in about **5 seconds**. A `service.security.hasAnyRole…` / `hasAnyRoleGroup…`
check **inside a rule or predicate** is remembered by the rule engine for up to **30 seconds** — a rule that
calls `addRoleGroup(…)` and then asks `hasAnyRoleGroup(…)` about the same person can read the old answer. The
role-group LIST that the Role Management screen and the user dialog show is cached for up to about **80 seconds**,
so a group a rule has just created or renamed can be missing from it until then — a refresh does not help before the
cache expires. `service.security.user().firstName/lastName` is remembered for up to **6 minutes**, so a person
renamed by `update(…)` can still be greeted by the old name until then. The user list itself (`get`, `list`) is
current.

**The invitation needs the project to have been opened once.** The web tier writes the invitation, and it can find
the project (realm and client → project) only after the project's first page has been served; a rule that invites
on a project nobody has opened since import logs an error and mails nothing. The author opening the project once is
enough. The web tier also checks, before it makes the link, that the account really is at the address the rule
named — a request that does not describe a real account of the project is dropped with a log line.

#### 2.3.2 `service.security.roleGroups` — the project's role groups

```
service.security.roleGroups
    .list()                                // [[name: "Buyers", roles: ["report_view"]], …]
    .get(String name)                      // one group, or null
    .create(String name, List roles)       // roles spelled as hasAnyRole spells them
    .update(String name, Map changes)      // [name: "New", roles: [...]] - what you do not mention stays
    .delete(String name)                   // false when there was no such group
    .members(String name)                  // the e-mails of everybody who holds it
```

A role group is a name and a list of **roles**; people hold groups, and checks like `hasAnyRoleGroup("Buyers")`
test the name. Roles are written as in `hasAnyRole` — lower case, `report_view`, `scheduler_edit`, `user_create` …
(any case is accepted; an unknown one is refused with the list of the valid roles, because a role silently dropped
makes a group that grants less than its author meant). ⚠️ The EXPORT writes the same roles as enum constants —
`roleGroups[].roles` holds `REPORT_VIEW`, `NCT_AUTHOR`, `ADMIN` — while a rule writes the role's name, `report_view`;
copying one spelling into the other works for every role whose constant is just the upper-cased name — except two
that are spelled differently: the constant `ORGANIZARIONS_VIEW` (sic) is the role `organization_view`, and
`ORGANIZATIONS_EDIT` is `organization_edit`; the standard business groups of the sample projects carry both. The
refusal's list is the authority for the rest. Groups are matched by **name, ignoring case**; `members` refuses a
name that matches no group instead of answering "nobody".

```groovy
service.security.roleGroups.create("Warehouse", ["report_view", "source_view"])
service.security.users.addRoleGroup("scanner-01@acme-corp.com", "Warehouse")
```

**What a group's holders keep.** A person's roles in the identity provider are written when a group is *given* to
them and taken back when it is *taken from* them — never when the group itself is edited. So the platform treats
the two edits differently, on purpose:

* `delete("Warehouse")` first **takes the group off everybody who holds it** (one by one — that is what revokes the
  roles it granted), then deletes it. If taking it off somebody fails, the group is not deleted and the call can be
  repeated.
* `update("Warehouse", [roles: […]])` that **changes the roles of a group people hold is refused**, with the number
  of holders and what to do. Narrowing or widening it for the people in it means: take it from them, update it,
  give it back —

  ```groovy
  def holders = service.security.roleGroups.members("Warehouse")
  holders.each { service.security.users.removeRoleGroup(it, "Warehouse") }
  service.security.roleGroups.update("Warehouse", [roles: ["report_view"]])
  holders.each { service.security.users.addRoleGroup(it, "Warehouse") }
  ```

  — or create a new group and move them over. A **rename**, or "changing" the roles to what they already are, is
  always allowed; so is changing a group nobody holds.

Settings → Accesses, the access of pages and menu links, and the **execution access of rules and CRUD methods**
(`access.roleGroups`) name a role group by its **NAME**, and so does every `hasAnyRoleGroup("…")` literal in a
script. Renaming a group therefore drops the grants it had — a rule that renames "People Admin" silently locks the
invite rule to authors — and a group created later under the name of a deleted one **inherits** what the deleted one
was granted. Do not reuse the name of a group you delete, and re-grant (and re-edit the literals) after a rename. The role
checks that read the group (`hasAnyRoleGroup`, page and action access) follow the timings under §2.3.1; those that
read the person's roles may lag, as there.

#### 2.3.3 What a rule may NOT hand out

A rule is run by whoever its execution access admits — by default every signed-in user — not necessarily by an
author, and an author is, in effect, code running on the platform. The User Management screen refuses to hand an
author group to anybody who is not an author; a rule cannot know who it acts for, so, regardless of the rule's
access:

* **`admin`** — the Developer's authority — can be neither put into a role group by a rule (`create`, `update`)
  nor given to a person by one (`create`'s `roleGroups`, `addRoleGroup`) if the group carries it.
* **`nct_author`** — makes its holder an author of the project — **the same**: a rule can neither put it into a
  group nor give a person a group that carries it, and a role group that carries **either** role cannot be changed
  or deleted by a rule: those are the groups the project's own authority rests on (the `Author` group is one). The
  platform enforces this on its own side too, not only in the script. Authors are made on the User Management
  screen, by an author.
* **Removing** a group or switching a person off is allowed for everybody visible — taking authority away is not
  the risk. That includes the person running the rule; design the rule with that in mind. The project's **owner**
  can be switched off or stripped of role groups, but not removed (`delete` refuses them).

Each refusal is an exception naming the group and the rule that applies. Groups that carry those roles are
defined in the export (`mrjun.py rolegroup add`) or on the Role Management screen — never from a rule.

---

### 2.4 `service.rimm.*` — running saved queries (RIMM)

Hits the saved `queries[]` from
`rep-objects.json` (see [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md)).
realm/client are substituted by the proxy automatically.

| Method | Signature (in the script) | Purpose |
|---|---|---|
| `service.rimm.query(name)` | `List query(String queryName)` | Query by name without parameters. |
| `service.rimm.query(name, params)` | `List query(String queryName, Map<String,Object> parameters)` | Query by name with parameters. |
| `service.rimm.query(requestMap)` | `List query(Map<String,Object> requestMap)` | Query via a map config. |
| `service.rimm.run(request)` | `List run(<request object>)` | Run via a request object. |
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

Two sub-namespaces `push` and `mail`. A detailed
breakdown (email templates, severity, storage) — [15-pdf-and-mail.md](15-pdf-and-mail.md).

#### `service.notification.push.*`

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

#### `service.notification.mail.<alias>(...)`

A dynamic proxy: **the method name = the alias of the mail template** (via `methodMissing`). Two signatures:

```groovy
// with the template's default subject:
service.notification.mail.<alias>(List<String> recipients, Map<String,String> placeholders)
// with a custom subject:
service.notification.mail.<alias>(List<String> recipients, String subject, Map<String,String> placeholders)
```

`placeholders` — a map of template placeholders. The aliases come from the project's mail templates
and land in hints. The list of a project's mail templates — `rep-objects.mailTemplates`
(a fresh empty starter already ships a handful of account-lifecycle ones), see
[12](12-queries-sources-schedulers-and-rest.md).

Example call forms:

```groovy
service.notification.mail.welcomeEmail(["user@example.com"], [firstName: "John", lastName: "Doe"])
service.notification.mail.welcomeEmail(["user@example.com"], "Custom Subject", [firstName: "John"])
```

---

### 2.6 `service.report.pdf.*` — generating PDFs from templates

Full breakdown of
PDF templates and fields — [15-pdf-and-mail.md](15-pdf-and-mail.md). Four
sub-namespaces:

| Call | Signature | What it does |
|---|---|---|
| `service.report.pdf.get.<alias>(fileName, params[, lang])` | `<PDF reference> get.<alias>(String fileName, Map<String,Object> params[, String lang])` | Prepares a PDF reference for the `<alias>` template; `params` — template fields; the optional `lang` — the language of the document (BCP-47: `"hy"`, `"ka"`, `"zh-Hant"`): the PDF's `/Lang`, the default language of its date fields, the regional Han font. Aliases — from the project's PDF templates. |
| `service.report.pdf.download(fileName, pdfs)` | `void download(String fileName, List pdfs)` | **Asynchronous, fire-and-forget**: queues a Kafka download request; the PDF service renders + merges the PDFs into one and POSTs the bytes into the per-user inbox file-storage; a UI poller picks it up and opens the browser save dialog (every 20 s). The `byte[]` is **not** returned. |
| `service.report.pdf.email.<mailAlias>(recipients, [subject,] placeholders, pdfs)` | `void` | An email by the mail template `<mailAlias>` with PDF attachments. |
| `service.report.pdf.push.send…(…, pdfs)` | like push, + a `List` of PDF references (`pdfs`) as the last argument | A push notification with a PDF attachment: `sendText/sendAlert/sendWarning/sendError/sendReminder` + `*ToRole`/`*ToRoleGroup`. |

The form from hints: attachments are built as a list of PDF references, for example
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

### 2.7 `service.access.*` — who sees a case (process access)

Every case — a process instance — carries **access rows**: `type` = `USER` (an e-mail), `ROLE` or `ROLE_GROUP`, a
value, an `isOwner` flag and an `access` (enabled) flag. A process table lists a case to a caller when ONE enabled
row matches them: their e-mail (exact, case-sensitive), one of their roles, or one of their role groups. Those rows
are the case-level access list of every queue an ERP has — who sees a purchase request while it waits for approval,
who sees it once it moved on to finance, whether the requester still sees it afterwards. `service.access.*` edits
them. It works over the rows loaded into the rule's document.

⛔ **WHERE an edit is saved — read this before writing one.** The rows are copied into the rule's document before
the rule runs; the methods edit that copy, and exactly two places write it back:

| the rule runs as… | access edits are |
|---|---|
| a BPMN **service task**'s rule (`${ruleTask}`) — and any `service.rule(...)` it calls | **saved**, after all the task's rules succeeded |
| a gateway's **sequence-flow predicate** | **saved** (a predicate may run once per conditional flow — keep access edits out of predicates anyway) |
| a user-task ACTION's complete or start rule (the form's submit) | discarded |
| a process-table action — a task or a global action — pressed without a form | discarded |
| a start form's rules; `service.workflow.complete(...)`; a CRUD table / tree / form rule; a scheduler; a CRUD GROOVY method; any predicate or validation rule outside a sequence flow | discarded |

Everywhere in the lower rows the calls **return `true` and change nothing**. Hence the one rule of every access
change: **the user task's action DECIDES, the service task right after it APPLIES** — the action's complete rule
records the decision (and who took it) in the document, the next service task reads it and edits the access. The
only other writer is `service.workflow.start(…, [owner:, roleGroups:, emails:])`, which writes the new case's rows
together with the case (§2.12).

How the save works: the service task's rules run in order and the task stops at the first one that fails — then
NOTHING is saved; otherwise, when the list differs from what was loaded, every row of the case is deleted and the
edited list is written back (a new item is `isOwner=false`, `access=true`). A failed save is only logged; the task
still completes.

| Method | Effect | Pitfall |
|---|---|---|
| `addRoleGroupAccess(name)`, `addRoleAccess(role)`, `addUserAccess(email)` → `boolean` | appends `{type, value (trimmed), isOwner:false, access:true}` unless an ENABLED row of that type and value exists (then returns `false`) | exact, case-sensitive matching: `Anna@acme.com` and `anna@acme.com` are two rows, and the person whose identity provider says the other spelling sees nothing; a DISABLED row of the same value does not count, so a second row is added |
| `removeRoleGroupAccess(name)`, `removeRoleAccess(role)`, `removeUserAccess(email)` → `boolean` | deletes EVERY row of that type and value, whatever its flags | `removeUserAccess(<the owner's e-mail>)` deletes the OWNER row — `restoreOwnerAccess()` then has nothing to restore |
| `hasRoleGroupAccess`, `hasRoleAccess`, `hasUserAccess(…)` → `boolean`; `getRoleGroupAccesses()`, `getRoleAccesses()`, `getUserAccesses()` → `List<String>` | read ENABLED rows only (the owner row counts) | meaningful only where the rows were loaded — service tasks, sequence flows, a case's action rules and visibility predicates; empty in CRUD, scheduler and start-form rules |
| `removeOwnerAccess()` / `restoreOwnerAccess()` → `int` | `access=false` / `true` on the owner row(s), which are KEPT; returns how many changed | the owner still sees the case through any OTHER matching row — a role group they belong to |
| `clearAllAccess()` | empties the list — saved as "delete every row" | the case is then invisible to everyone; a form-started case has no admin/author rows to fall back on |
| `getAccessCount()`, `hasAnyAccess()` | count rows, disabled ones included | |
| `accessDto` (not offered by the editor) | the live list: `accessDto.accesses`, items with `type`, `accessValue`, `isOwner`, `access` | the only way to move the `isOwner` flag (recipe 4) |

There is no `setOwner`, and no method reaches ANOTHER case: a rule edits the case it runs in.

**Who the rule is.** A service task runs as the case's OWNER — its starter, or the `owner` passed to
`service.workflow.start` — for the whole life of the case: the platform never assigns a user task to the person who
completes it, so the "last assignee" the engine would prefer is always empty (unless the BPMN hard-codes one).
`service.security.user()` inside a service task is therefore NOT the approver. Capture the actor in the action's
complete rule — it runs as the person who pressed the button: `context.data.setAttr('decidedBy',
service.security.user().email)`.

**Access rows decide what is LISTED, not what may be DONE.** Executing an action checks that the caller is signed in
and that the action's visibility predicate passes — never the access rows. Every action therefore needs a predicate
that admits exactly the people who may press it: their role group and, where the case moves between queues, the
queue attribute the service tasks maintain (recipe 2c). A predicate on a case can read the rows too:
`service.access.hasRoleGroupAccess('<Finance>')`.

**Who is on a new case.** A case started from a form gets ONE row — its starter, `USER`, `isOwner=true` — and
nothing else: no colleague, no admin, no author sees it until a rule grants it. A case started by
`service.workflow.start(...)` gets its `owner`, the `roleGroups`/`emails` passed, and always the ROLE rows
`admin` and `nct_author` (§2.12). Grant the groups that work the case in the workflow's FIRST service task — or in
the start options.

**Recipes** — the full pattern, with its BPMN and its worklists, is [07](07-workflows-and-tasks.md) "Stage-wise case
access".

```groovy
// 1. Open the case to the groups that work it — the workflow's FIRST service task
service.access.addRoleGroupAccess('<Requesters>')
service.access.addRoleGroupAccess('<Approvers>')
context.data.setAttr('queue', 'APPROVAL')
return null
```

```groovy
// 2a. The Approve action's complete rule — runs as the APPROVER; an access call here would be discarded
context.data.setAttr('decision', 'APPROVED')
context.data.setAttr('decidedBy', service.security.user().email)
return null
```

```groovy
// 2b. The service task right after that user task — runs as the OWNER; its access edits ARE saved
if (context.data.getAttr('decision') != 'APPROVED') { return null }
service.access.removeRoleGroupAccess('<Approvers>')
service.access.addRoleGroupAccess('<Finance>')
context.data.setAttr('queue', 'FINANCE')
return null
```

```groovy
// 2c. The visibility predicate of every Finance action — the rows hide the case, this is what refuses the press
return context.data.getAttr('queue') == 'FINANCE' && service.security.hasAnyRoleGroup('<Finance>')
```

```groovy
// 3. Hide the case from its initiator once submitted (a service task) — the row is kept, so it can come back
service.access.removeOwnerAccess()            // NOT removeUserAccess(<initiator>): that deletes the owner row
return null
```

```groovy
// 4. Make another person the case's owner (a service task). There is no setOwner: edit the live list.
def to = (context.data.getAttr('newOwnerEmail') ?: '') as String
if (!to) { return null }
service.access.addUserAccess(to)
service.access.accessDto.accesses.each { a ->
    if (a.isOwner && a.accessValue != to) { a.isOwner = false; a.access = false }   // drop `a.access = false` to keep the old owner seeing it
    if (a.type?.name() == 'USER' && a.accessValue == to) { a.isOwner = true; a.access = true }
}
return null
// This moves the owner ROW. The `owner` process variable — the identity every service task runs as — stays the starter.
```

⛔ **The anti-pattern:** `service.access.addRoleGroupAccess('<Finance>')` in the Approve action's complete rule. It
returns `true`, the toast says the request was approved, and nobody in Finance ever sees it.
---

### 2.8 `service.quota.*` — project limits (read-only)

Read-only; `allowed*` may be `null` (no limit). Available in EXECUTION
rules, service tasks and CRUD methods; in a PREDICATE or a VALIDATION rule `service.quota` is `null` (the editor
offers it there anyway — [09](09-groovy-hints-and-live-context.md) "Where the hints and the runtime disagree"). The
values are refreshed at most every ten seconds per project; when they cannot be read, the numbers are `null` / `0`.

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

---

### 2.9 `service.enums['Name'].list()` — the project's enum registry

A snapshot of the registry is taken once per rule run. Access both via brackets and via
a property:

```groovy
def rows = service.enums['OrderStatus'].list()   // bracket form
def rows = service.enums.OrderStatus.list()       // property form
```

`list()` → `List<Map<String,Object>>`, one row per constant. Only the `name` key is
guaranteed to be present; the other keys (e.g. `displayName`
`intCode` for an INTEGER-enum) + any extra fields are taken from the registry entry and are in the row
only if they are set in the enum registry. A single enum also has
`getName()`, `getKind()`, `getBaseType()`, `getFieldNames()` and `service.enums.Status.ACTIVE` (a constant →
map). Cross-capability: `service.enums['X'].list()` → `service.global.conversion.toSelectOptions(rows,
"name", "displayName")` → dropdown.

`service.enums.names()` returns the `Set<String>` of **all** registered enum names — for
iterating the registry. It is **runtime-only**: the hints tree emits only `list()` per enum,
so `names()` works at runtime but **never autocompletes**.

---

### 2.10 `service.rule("Name")` — a rule invokes a rule

`service.rule(String ruleName)` finds a rule **by name** (in the current
realm/client) and executes it **with the same `contextData`** (realm, client, userId, contextData). It returns
the `returnValue` of the invoked rule. Useful for reusing predicates.

**Worked example** (`Can Unlock`):

```groovy
return service.rule("Is Author") && !service.rule("Document is Unlocked")
```

> Resolution is **by name only** (not by identifier) — rule names must be unique in the project, otherwise
> the rule picked is not deterministic. The invoked rule runs on the **same document object**, both ways: it sees and
> can change the caller's `attrs`, CRUD data and access rows, and whatever it changes the caller sees after the
> call (in a service task its access edits are saved with the task's, §2.7). `param` is NOT passed — the caller
> consumed it — and no process variables are merged in. The callee runs with ITS OWN kind's surface (a predicate
> called from an execution rule still has no `service.workflow`), as the same user.
>
> ⚠️ The callee's execution access is **not** checked: once the outer rule passed its door, `service.rule(...)` runs
> on the platform's authority. A public rule (`anyone`) may call a signed-in-only or role-group rule — the intended
> shape — which also means the OUTER rule's access is the whole gate for everything it calls
> ([08 §"Execution access"](08-groovy-rules-and-context.md)).

---

### 2.11 `service.actionName` / `service.actionId` — which button was pressed

String fields, populated when a rule is launched by an **action button**
of a CRUD-table/tree/process-table (read from `attrs.__actionId`/
`attrs.__actionName`). Outside the action context — `null`. Use `actionId`
(stable) for comparisons; `actionName` is the localized caption.

⚠️ **Also pushed by the FORM.** The open form tags
`contextData.attrs` with `__actionName`/`__actionId` for **every rule it runs** — so a form opened
by a crud-table action OR by a workflow user-task action can discriminate on which button opened it.
And the action meta is available in **all three rule types** (execution, predicate, validation) — so `service.actionId` is readable from a
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

**A case another SYSTEM opens through the project's public API needs no new `start` call.** The API presses a
button that already exists, exactly as a person would: the worklist's start action — the case is then created
by its start form, owned by the caller, and no rule calls `start` — or a document's create/row action, whose
lifecycle rule calls `start` as it does for a person ([32](32-public-api.md) §1,
[27](27-event-driven-process-start.md) §2.0).

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

There is no third slot: a CRUD envelope carries **only** `value` (it has no `attrs` field). Writing
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

`validate` flags this offline — it is not something to rediscover by
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
  whose in-code default is empty** (blank disables the fallback and leaves the process
  ownerless), so a deployment that blanks it produces **no owner access row and no `owner` variable at all** —
  the case is then reachable only through the admin / author ROLE grants, and its service tasks run with no
  user. Nothing in the export shows you which deployment you are on, which is the argument for passing `owner`
  rather than inheriting one. With the fallback on, the thing to guard against is not "nobody sees it" but
  "**one wrong account** owns it": that same account is the identity EVERY service task of the case executes as — the
  platform never assigns user tasks, so no completed task ever takes over (§2.7) — so `service.security.user()`
  inside the case answers the author, not the person the case is about. Admins
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
- **`service.access.*` cannot reach the new process.** A rule edits the access of the case it runs IN — and saves
  it only from a service task or a sequence flow (§2.7). Grant the new case's access through the options above,
  or from the new process's own first service task.

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

**The same backend, called from outside.** A partner system working a process table through the project's
public API ([32](32-public-api.md)) reaches what `list`, `actions` and `complete` reach — the same worklist, the
same action resolution, the same Start and Complete rules — plus the chosen form's mandatory fields and
validators, as the acting user. Your rules need no API branch, with two exceptions that make them headless for
that call: `service.store.session` holds nothing and `service.redirectPage` is not delivered (§2.14, §2.15).

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

Two stores with one interface: `session` and `user`. Available in **all
three rule types**, so both members are always PRESENT — never null, never absent by rule type —
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
 ├─ session   → values that live as long as the user's BROWSER session
 └─ user      → values stored in the database for the ACTING USER
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
`service.store.user['branch'] = id` writes.

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
`LinkedHashMap` / `ArrayList`. An arbitrary object is not what a key/value scratchpad
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

In both cases `put` stores nothing and `get` answers `null`, **including within the same script**.
That is deliberate: a store that remembered a write for the rest of the rule and
then dropped it would make one script behave differently from a page and from a cron, with the difference
surfacing later and somewhere else.

#### Where the keys in autocomplete come from

A store key is invented by whoever writes the rule; nothing declares it up front. So the editor completes a key
from a **catalogue of keys that have actually been written** — the executor records each key (and the type last
stored under it) the first time a rule writes it, per scope, and the hint payload carries
them under its own root node so they are completable in every rule type
(see [09](09-groovy-hints-and-live-context.md)).

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
| A page with tabs | Name the tab: `service.redirectPage("orders/card?id=" + id + "&tab=<tab id>")`. Without it the page opens on the tab the user used last on that tab set — remembered per tab-set node, not per record, so another record's tab ([14a](14a-plugin-config-reference.md) §`nct.tab.plugin` → «Which tab opens»). The id is the tab item's `id`; a value that matches no tab is ignored. |

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
  replaces the page itself, and only the LAST navigation scheduled for a request is kept — so a
  `redirectPage` in that action's rule is discarded with nothing logged. Use it from actions that stay on the
  page (a direct action, a form's before/after rule, an HTML component's `ctx.callRule`).
- **Wrong path, blank page.** Nothing validates that the page exists — the value is an in-app path, and the
  browser simply goes there. Copy the alias and the content path from the page's URL.
- **A rule reached without a browser is silent about it.** Same shape as `service.store.session`: a scheduler
  cannot navigate anybody, and the call neither throws nor warns.
- **Not for downloads.** `service.report.pdf.download` (§2.6) has its own delivery; redirecting to a file URL is
  not how the platform hands over bytes.

---

### 2.16 `service.mailbox.*` — reading and answering the project's own mail

Full picture, including everything that is configured LIVE rather than authored, in
[31](31-email-integration-and-mailbox.md). This is the member list.

```
service.mailbox
    .account(String name)          // the same mailbox, narrowed to ONE account - see below
    .unread()                      // messages NO RULE has handled yet, newest first, limit 50
    .unread(Map options)           // the same, narrowed
    .find(Map options)             // any search across the project's mail
    .get(String id)
    .unreadCount()  .unreadCount(Map options)
    .accounts()                    // [[name:…, address:…, active:…, canSend:…, canReceive:…, isDefault:…], …]
    .markRead(x)   .markUnread(x)  // x = a message, an id, or a list of either
    .flag(x)       .unflag(x)
    .archive(x)    .trash(x)       .move(x, "FOLDER")
    .send(Map options)
```

**Say WHICH mailbox once, not in every call.** A project with two accounts can pass `account:` to each
call, and then the one call that forgets reads — or answers from — the wrong mailbox:

```groovy
def support = service.mailbox.account("Support")          // the name from Settings
support.unread(limit: 20).each { message ->
    // … turn it into a record …
    message.markRead()
}
support.send(to: message.from, subject: "Re: " + message.subject, text: "Got it.")
```

Everything after `account(...)` is about that account unless a call names another one — it sets a default,
it does not forbid anything. Two more reasons to prefer it: the editor completes the name from the
project's real accounts as soon as you type the opening quote (a key inside an options map cannot be
completed at all), and `accounts()` is the list if you want to loop over all of them.

**Options for `unread` / `find`:** `account` (the account's NAME), `folder`, `limit` (default 50), `page`,
`from`, `to`, `subject`, `search`, `sinceDays`, `since`, `until`, `flagged`, `hasAttachments`,
`oldestFirst`, `includeBody`. The text options match with `%` as the wildcard: `from: "%@acme.com"`.

**Options for `send`:** `to` (required), `cc`, `bcc`, `subject`, `html`, `text`, `account`, `replyTo`,
`attachments` (`[[fileName:…, content: bytes, contentType:…], …]`), `storeInSent`, and `inReplyTo` — the id
of a message in THIS project, which puts the outgoing mail in that conversation and marks the original
answered. An id belonging to another project is refused at the door. `message.reply(html)` does all of that
for you; pass `inReplyTo` only when you are composing the answer yourself.

**Each message** carries `id subject from fromName to cc replyTo text html snippet receivedAt sentAt folder
account messageId userRead ruleRead flagged hasAttachments attachments`, and answers
`markRead() markUnread() flag() unflag() archive() trash() reply(html) replyAll(html) forward(to, html)`
and `attachment("name.pdf")`. An attachment answers `fileName contentType size inline skipped` for free and
`bytes()` as a fetch.

All of that is in the editor's completion, not only here: `service.mailbox.get(id).` lists the members, and
so does `unread()[0].`. Inside `each { message -> … }` the completion stops, because the editor cannot know
what a closure's parameter is — index into the list while exploring, then write the loop.

> **⛔ The two read flags are independent, and this namespace only ever touches one of them.**
> `unread()` means *no rule has handled this* and `markRead()` records *a rule has*. What a PERSON has
> opened in the Mailbox plugin is a separate flag that nothing here reads or writes — and vice versa. That
> is the point: a colleague glancing at a message must not make an importer skip it, and an overnight
> importer must not empty somebody's unread count. See [31 §2](31-email-integration-and-mailbox.md).

> **⛔ Marking is the rule's own job.** A rule that reads a message and does not mark it processes that same
> message again on the next tick, forever. Mark it in the same iteration that consumed it — the same
> discipline [27](27-event-driven-process-start.md) states for case creation, and for the same reason.

**Where it works.** Reading is available in **every** rule type; the members with side effects
(`markRead`, `markUnread`, `flag`, `unflag`, `archive`, `trash`, `move`, `send`, `reply`, `forward`) work
only in an **EXECUTION rule** and refuse elsewhere with an explanation. A predicate is evaluated for an
answer, possibly once per row; a validation rule runs on every submit attempt. Consuming an inbox as a side
effect of deciding whether to draw a button is not a thing anybody meant to write.

**`send` vs `service.notification.mail.<alias>` (§2.5)** — a real decision: the template call is for
anything a designer should own (a branded notification, a statement), because the project can restyle it
without a rule being touched; `service.mailbox.send` is for text a rule composed, where there is nothing
for a designer to own.

**With nothing configured** the namespace still exists and answers empty: `unread()` returns `[]`,
`accounts()` returns `[]`, and `send` reaches the platform's own account the way it always did. A rule
written against it is therefore safe to ship before the customer has connected a mailbox.

---

### 2.17 `service.pubsub.*` — publishing to the customer's message brokers

Full picture — what a listener is, the delivery contract, what is configured LIVE rather than authored — in
[33](33-pubsub-integration.md). This is the member list.

```
service.pubsub
    .<alias>.publish(String destination, Object payload)                  // alias = the connection's name in Settings
    .<alias>.publish(String destination, Object payload, Map options)
    .<alias>.publish(Map call)                                            // destination:, payload:, + options
    .['alias']  .channel("alias")                                         // the same object, for an alias held in a variable
    .list()                                                               // [[alias:, kind:, version:, description:], …]
```

```groovy
service.pubsub.plant.publish('sensors/room1/command', [setpoint: 21.5])                       // a Map goes out as JSON
service.pubsub.plant.publish('sensors/room1/command', [setpoint: 21.5], [qos: 1, retain: true])
service.pubsub.erpBus.publish('orders-created', order.id as String, [key: order.customerId])   // Kafka: the record key
```

A channel has exactly **one** member, `publish`. There is no `send`, `subscribe` or `consume` — *receiving* is a
**listener**, configured live, which runs an EXECUTION rule per message (§5 of [33](33-pubsub-integration.md)), and
that rule reads the message with `context.data.getAttr('message')`.

**The destination is the kind's own word** — an MQTT topic, a RabbitMQ routing key, a Kafka topic, an ActiveMQ
`queue:NAME` / `topic:NAME`. **Options differ by kind** (MQTT `qos` `retain`; RabbitMQ `exchange` `persistent`;
Kafka `key`; ActiveMQ `defaultType` `persistent` `timeToLiveMs`; every kind `headers` `contentType`) and an option
the kind does not have is refused with the list of the ones it does. The table is in [33 §4](33-pubsub-integration.md).

**The payload:** text as text; a Map, List or other object as JSON; a number or boolean as its text; a `byte[]`
as binary; limit 1 MB. The call returns `[ok: true, reference: …, millis: …, bytes: …]` once the broker has taken
the message, and **throws** (a sentence naming the alias and the broker's own words) when it did not.

**The alias is the connection's name, not its address.** It is letters, digits and underscores, so
`service.pubsub.plant` reads as a property. A connection that is not there fails with the aliases that are. With
**no connection configured the namespace is absent from the editor's completion** — and a rule written against it
is safe to ship before the customer connects a broker: it fails with a sentence, never hangs, never writes anywhere.

**Where it works.** **EXECUTION rules and CRUD GROOVY methods only.** In a PREDICATE or a VALIDATION_RULE the
namespace exists and **every** member throws — they may run many times for one answer, and a message sent as a side
effect of drawing a button is a message nobody decided to send. This includes an execution rule called **from**
a predicate with `service.rule("…")`. `mrjun.py validate` reports it.

> **⛔ A listener's rule runs at-least-once.** A retry, a redelivery after a restart and the other system's own
> duplicate all run it again — write it so that the second run is harmless ([33 §5.2](33-pubsub-integration.md)).

---

## Part 3 — `validation.*` (VALIDATION_RULE only)

In a validation rule, the validation template places the `validation` collector and provides 4
delegate methods. The script **returns nothing** — it accumulates messages; the framework
displays them at the field/form. See also [08](08-groovy-rules-and-context.md) and §"Field-based validation templates"
in [02](02-form-controls-reference.md).

| Method (in the script) | Delegates to | Effect |
|---|---|---|
| `addError(String message)` | `validation.addError(message)` | A general form error. |
| `addWarning(String message)` | `validation.addWarning(message)` | A general warning. |
| `addFieldError(String fieldName, String message)` | `validation.addFieldError(...)` | An error at a specific field. |
| `addFieldWarning(String fieldName, String message)` | `validation.addFieldWarning(...)` | A warning at a field. |

In hints these 4 methods live under the `validation` key —
but **only** when `ruleType == VALIDATION_RULE`. For EXECUTION/PREDICATE there is no `validation` key in hints.

The collector also answers questions — not offered by the editor, but there: `validation.hasErrors()`,
`hasWarnings()`, `hasMessages()`, `getMessageCount()`, `getErrors()`, `getWarnings()`, `getAllMessages()`,
`clear()`. Use them instead of counting by hand — e.g. add a summary warning only when field errors were found.
The field argument of `addFieldError` / `addFieldWarning` is the control's `settings.name`.

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
   with an **empty** context list, resolution goes across the whole registry). See
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
   - **add / re-group / disable a person from the app:** `service.security.users.create(email:…, firstName:…,
     lastName:…, roleGroups:["Buyers"])` (invited by e-mail; add `password:` to skip the invitation),
     `.addRoleGroup(…)`, `.setEnabled(…, false)`, `.delete(…)` — §2.3.1. EXECUTION rules and CRUD GROOVY methods
     only, and ⛔ set the rule's **execution access** to the role group that administers people: the default lets
     every signed-in user run it.
   - **notify a role on an event:** `service.notification.push.sendAlertToRoleGroup("Ops", "T", "M")`.
   - **PDF → e-mail:** `def r = service.report.pdf.get.tpl("f.pdf", [...]); service.report.pdf.email.mailTpl([...],[...],[r])`.
   - **invoke another rule:** `return service.rule("Is Author") && ...`.
   - **send the user to another page after an action:** `service.redirectPage("orders/queue")` — §2.15,
     EXECUTION rules only, path WITHOUT the organisation.
   - **remember something between rules:** `service.store.session.put("selectedBranchId", id)` (this browser
     session) or `service.store.user.put("rowsPerPage", 50)` (this person, forever) — §2.14. Reading always
     takes a default: `service.store.user.get("rowsPerPage", 25)`.
   - **turn an inbox into records:** `service.mailbox.unread(account:"Support", limit:50).each { m -> … ;
     m.markRead() }` — §2.16, EXECUTION rules only for the marking, and the `markRead()` is what stops the
     next tick processing the same message again.
   - **publish to a message broker (MQTT, RabbitMQ, Kafka, ActiveMQ):** `service.pubsub.plant.publish("devices/${d.serial}/command",
     [action:"restart"], [qos:1])` — §2.17, EXECUTION rules only; `plant` is the alias of a connection the recipient
     adds live ([33](33-pubsub-integration.md)). There is nothing to call for *receiving*: that is a listener.
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
  `.asInt()`/`.asText()`/`.numberValue()`/`.isNull()` (example
  `Find — Bill of Materials`). A direct comparison `attrs.get('x') == 5` will not work.
- **`param` is empty outside delegation.** It is populated only when a CRUD GROOVY method is invoked via delegation
  (the platform passes the parameters in on delegation). In
  a normal rule `param == [:]`. The idiom `def filter = param ?: [:]`.
- **`filter` is not a binding.** It is your local variable. The only `filter` in the API is
  `service.global.collection.filter.*`.
- **`service.rimm.query(...)` in hints shows `realmName, clientName`** in the signature — that is the signature of the
  underlying service. In the script call the overridden proxy variants **without** realm/client:
  `service.rimm.query("name")`, `service.rimm.run([...])`.
- **`service.notification` without `.push`/`.mail`** does not work: the `send*` methods live on
  `service.notification.push.*`, emails — on `service.notification.mail.<alias>(...)`. (Note the full path in the
  §2.5 example: `service.notification.push.sendAlert(...)`.)
- **`service.security.users.*` and `.roleGroups.*` are EXECUTION-only and THROW elsewhere.** In a predicate or a
  validation rule they exist and refuse with `… is not available in predicates` (they are evaluated for an
  answer, possibly once per row) — and so does an execution rule that such a rule *calls* (`… in rules called from
  predicates`). `validate` ERRORs on a direct call; it does not follow calls. §2.3.1.
- **A rule that manages people is as open as its execution access — and the default is "any signed-in user".**
  The Settings → Accesses grants gate the User Management SCREEN, not rules: whoever may run the rule has, through
  it, everything it does. Set `rule access` (or the CRUD method's access) to the role group that administers
  people, and put the button behind a predicate on it. `validate` WARNs on the default. §2.3.1.
- **`users.create` is not idempotent.** A person who is already a member is refused, so a rule that can run twice
  starts with `users.get(email)`. `addRoleGroup`, `removeRoleGroup` and `roleGroups.delete` ARE idempotent.
- **A role group's roles are written to people when the group is GIVEN, not when it is edited.** `delete(group)`
  takes it off its holders first; `update(group, [roles: …])` on a group people hold is refused until you take it
  from them (§2.3.2). Grants made in Settings → Accesses and on pages name a group by NAME: a rename drops them,
  and a re-created group of the same name inherits them.
- **The User Management dialog — and the invitee's set-password page — save a person's WHOLE list of role
  groups.** A dialog opened (or a set-password page loaded) before a rule ran `addRoleGroup` / `removeRoleGroup`
  for the same person puts the old list back when it is saved. Rules that change groups are for processes, not for
  editing while somebody has that person's dialog open.
- **A `password` passed to `create` is ignored for an address that already has an account in the organisation**
  (it keeps its own); the result's `existingAccount` says so. Do not mail credentials on the strength of the
  password you passed — mail them only when `existingAccount` is `false`.
- **There is no way to set an existing account's password, change an address, or delete the account itself.**
  New password ⇒ `invite(email)`; `delete(email)` means "out of THIS project"; `setEnabled` is the
  ORGANISATION's switch. §2.3.1.
- **`service.rule("Name")` resolves by NAME.** Duplicate rule names → non-deterministic selection. Keep names
  unique.
- **`service.enums['Name']` returns `null` if the enum is not registered** (the lookup returns null)
  — it does not throw. Check for null before `.list()`.
- **`service.actionId`/`actionName` = null** if the rule was not invoked by an action button (fetch, dropdown,
  validation). Do not rely on them in fetch rules.
- **PREDICATE: only `return <Boolean>`.** Because of the template's trailer `if(true){return null;}`,
  a bare `true` as the last line is discarded → `null` → "must return
  Boolean". Always write `return`.
- **`inject(...)` is heavily restricted.** Most beans are blocked.
  Do not count on pulling `reactorService`/`crudReactor` through it — use `service.crud.*`.
- **`service.global.*` is a server-editable catalog (YAML).** The function list = the current
  `globalFunctions.yaml`. When the platform version changes, cross-check against the hints tree, not this table.
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

Verified against the `service` object and the hints tree — and you can re-verify on any
project with `jq` over `ruleScriptStr` and `methods[].script`: **the following namespaces do NOT exist in the
language** —

- **`service.feign.*`** — not a member of `service`, not in hints, never resolvable at runtime. External HTTP —
  via `service.global.rest.*` (Part 2.2). ⚠️ There is no separate "feign clients" API for scripts.
- **`service.integration.callExternal(...)`** — does not exist. Calling external services = `service.global.rest.*`
  (REST) or `service.crud.<alias>.<method>()` (an external system wrapped by a dynamic CRUD/integration).
- **`service.crudimport.*`** — not a member of `service` and not in hints. CRUD-import is a UI feature,
  not a Groovy-script binding.
- **`service.localization.*` / the `localization` binding** — does not exist. The session locale is available via
  `service.global.locale.getKey()`/`getLocale()`/`getLanguage()`; a sentence in the caller's language — via
  `service.global.locale.message('…')`; a row's localized field — via `service.global.locale.localized(row, field)`;
  localized options — via `service.global.conversion.toSelectOptionsLocalized(...)`.

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
  Process-access mutation is `service.access.*` (§2.7: on the case the rule is ALREADY in, never one it just
  started — and saved only from a service task or a sequence flow).
- **`service.mail` (bare)** — must be `service.notification.mail.<alias>(...)` (§2.5); neither `service.mail` nor
  `service.notification` alone (without `.push`/`.mail`) resolves anything.
- **`service.redirect` / `service.navigate` / `service.goToPage` / `service.setResponsePage`** — none of these
  exist. There is exactly ONE way to move a browser and it is `service.redirectPage("alias/page")` (§2.15),
  EXECUTION rules only, taking an in-app path and never a URL. There is no `service.redirectUrl` and no way to
  open an external site from a rule.
- **`service.mailbox.inbox` / `service.mailbox.folders` / `service.mail.read`** — none of these. The mailbox
  namespace is flat: `unread`, `find`, `get`, `unreadCount`, `accounts` and the mutating members listed in
  §2.16, with the folder given as an OPTION (`folder: "INBOX"`) rather than as a sub-namespace. There is
  also no way to ask whether a queued message was ultimately delivered — a send is queued, not performed.
- **`service.pubsub.<alias>.send` / `.subscribe` / `.consume` / `.on(...)`, `service.mqtt`, `service.kafka`,
  `service.rabbit`, `service.amqp`, `service.jms`** — none of these. One namespace, `service.pubsub`; a channel
  has exactly `publish(destination, payload[, options])` (§2.17). A rule never subscribes: a **listener**
  configured live in Settings → Developer → Integrations → PubSub calls the rule when a message arrives
  ([33](33-pubsub-integration.md) §5). `service.pubsub.list()` and `.channel(alias)` are the only other members.
- **`service.users` / `service.user` / `service.security.createUser(...)` / `service.security.deleteUser(...)` /
  `service.security.roles()` / `service.security.roleGroups()` (a call) / `service.security.groups`** — none of
  these (`service.security.roleGroups` is a property holding the namespace of §2.3.2, never a call).
  Managing people is `service.security.users` with exactly nine members (`create`, `get`, `list`, `update`,
  `setEnabled`, `delete`, `addRoleGroup`, `removeRoleGroup`, `invite`) and role groups is
  `service.security.roleGroups` with exactly six (`list`, `get`, `create`, `update`, `delete`, `members`) —
  §2.3.1–2.3.2. There is **no** `users.find(...)` (use `get(email)` or filter `list()`), **no**
  `users.setPassword/changePassword/resetPassword` (use `invite`), **no** `users.deleteAccount` (the account
  belongs to the organisation), **no** `users.add/remove` (those are `create` and `delete`), and **no**
  `roleGroups.assign/add` (a group is given to a person with `users.addRoleGroup`).
- **`service.session` / `service.cache` / `service.prefs` / `service.state` / `service.storage`** — none of these
  exist. There is exactly ONE key/value namespace and it is `service.store`, with exactly two members:
  `service.store.session` and `service.store.user` (§2.14). `service.store.global` and `service.store.project`
  do not exist either — a value shared by everybody is a CRUD row, not a store key.

If you need one of these capabilities — it is implemented with the existing means (`service.global.rest`,
`service.crud`, `service.rimm`, `service.global.locale`/`conversion.*`), not an imaginary namespace. Everything that is actually
available is listed in Part 2 and reflected in the hints tree.
