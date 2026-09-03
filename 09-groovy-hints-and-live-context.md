# Groovy hints vs live context-data hints

## What it is / when to use

In the Groovy-rules editor (rule dialog: create/edit rule; see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md))
**TWO different autocomplete systems** operate, which merge into a single CodeMirror hint tree:

1. **Server-side HintsService hint tree** — a static tree `{context:{...}, service:{...}, validation?:{...}}`,
   built in the `nct-executor` microservice (`HintsService.buildRuleHints`) from the **definitions** of contexts
   (`contexts` / `crudAliases`), CRUD methods, and service functions (`service.security`, `service.rimm`,
   `service.global`, `service.enums`, `service.notification`, `service.report`, …). It arrives over HTTP in
   `nct-ui` (`RuleEditorField.getHints()` → Feign `UiMcpClient`), then is post-processed UI-side
   (`injectReturnFieldsFromCruds`). This tree is **always** present in any rule editor.

2. **Live context-data hints** — real values from a **live form**. When the rule dialog is opened from a form's
   settings, `FormPlugin` publishes a live `ContextDataDto` to the page. `RuleEditorField.injectLiveContextDataHints`
   reads it, and `LiveContextDataHints.inject(...)` **merges** the real attribute names/types into the
   already-fetched static tree: `context.data.*` (global), `context.<alias>.data.*` (per context),
   `context.currentData.get().*` (current element of a nested list), and overlays the live entity onto
   `context.<alias>.<crud>.data.get().*`. **Only** where `contextData` exists (form / form button).
   In the editor opened from the Rules list there is no live data → this is a **no-op**, the behavior does not change.

> For the export builder this is a **runtime editor feature**, NOT export data. There is **no** hints file in
> `.mrjun` — the tree is built on the fly from `rule.contextIdentifiers` + `rule.ruleType`. This document matters for
> Step-1 (understanding which symbols are available in Groovy → writing correct `rule.rule.ruleScriptStr`), not for
> directly patching JSON. The difference between the two systems is the key to why some symbols (`service.*`,
> `context.<ctx>.<crud>.service.find(...)`) are always visible, while others (`context.data.myAttr`) are visible only
> in the context of a live form.

> **🔧 Tooling.** For these entities run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-editing JSON:
> `show rule <id>`, `show context <id>` (hints are a runtime editor feature, not an export entity; the CLI only shows the source rule/context).
> Full index and rules — [`tools/README.md`](tools/README.md); before re-import — `mrjun.py validate`.

**Related documents:** rule and context structure — [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md);
**the full catalog of what can actually be called** (`service.*` capability surface), which is exactly what the hint tree suggests — [16-groovy-service-api.md](16-groovy-service-api.md);
the CRUD methods that end up in the tree — [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md);
where `contexts[].crudAliases` lives in the export — [08](08-groovy-rules-and-context.md); the full `.mrjun` format —
[00-export-format-and-import.md](00-export-format-and-import.md).

## Export shape

The hints are NOT stored in the export. The inputs from which the tree is built live in `rep-objects.json`:

- `rule.contextIdentifiers[]` — context UUIDs (→ `HintsService` resolves them into `ContextDto` → `alias` + `crudAliases`).
- `rule.ruleType` — `EXECUTION_RULE` | `VALIDATION_RULE` | `PREDICATE`
  (`RuleType.java`).
- `contexts[].alias`, `contexts[].crudAliases[]` — from `rep-objects.json.contexts`.

Worked input (`rep-objects.json` — a project with the usual single context `finance_context`):

```json
{"name":"Invoice Delete","ruleType":"EXECUTION_RULE","executor":"GroovyExecutionRule",
 "contextIdentifiers":["871f974f-e775-401a-adfc-e822110f3b99"]}
```

```json
{"name":"Invoice Note Size Validation","ruleType":"VALIDATION_RULE","executor":"GroovyValidationRule",
 "contextIdentifiers":["871f974f-e775-401a-adfc-e822110f3b99"]}
```

```json
{"identifier":"871f974f-e775-401a-adfc-e822110f3b99","name":"Finance Context","alias":"finance_context",
 "crudAliases":["bl","counterparties_cruid","invoice_statuses_cruid","invoices_cruid","payments_cruid", ...]}
```

> All three rep-objects share the same `contextIdentifiers`/`identifier` = `871f974f-...`. In the typical layout
> that is the project's **only** context (`jq '.contexts|length'` → `1`), and it lists **all** of the project's
> crud aliases, so any rule referencing it sees the entire CRUD set.

From this pair `HintsService.buildRuleHints("<realm>","<client>",["871f974f-..."],EXECUTION_RULE)` builds the tree.
The request shape is `RuleHintsRequestDto{contextIdentifiers[], ruleType}`; the response shape (JSON) is described below.

### JSON schema of the hint tree (response of `getRuleHints`)

```
{
  "context": {
    "data":        { "setAttr(String key, Object value)": <methodDetails>, "getAttr(String key)": <methodDetails>, ... },
    "currentData": { "put(Object value)": <methodDetails>, "get()": <methodDetails>, "setAttr(...)": ..., "getAttr(...)": ... },
    "<contextAlias>": {
      "data": { "setAttr(...)": <methodDetails>, "getAttr(...)": <methodDetails> },
      "<crudAlias>": {
        "service": { "find(...)": <methodDetails+_returnFields?>, "get(String id)": ..., "create(...)": ..., "<customMethod>(...)": ... },
        "data":    { "put(Object value)": <methodDetails>,
                     "get()": { "<dtoField>": {"type":"<SimpleType>"}, "<nested>": { "<field>": {"type":...} } },
                     "setAttr(...)": ..., "getAttr(...)": ... }
      }
    }
  },
  "service": {
    "access":       { "addRoleAccess(String roleName)": <methodDetails>, ... },
    "rimm":         { "query(String realmName, String clientName, String queryName)": <methodDetails>, ... },
    "security":     { "user()": { "id":{"type":"String"}, "email":{"type":"String"}, "firstName":{"type":"String"}, "lastName":{"type":"String"} },
                      "hasAnyRole(String... roles)": <methodDetails>, "hasAllRoles(...)": ..., "hasAnyRoleGroup(...)": ..., "hasAllRoleGroups(...)": ... },
    "notification": { "push": { "sendText(...)": ..., ... }, "mail": { "<mailAlias>(List<String> recipients, Map<String, String> placeholders)": <methodDetails>, "<mailAlias>(List<String> recipients, String subject, Map<String, String> placeholders)": <methodDetails> } },
    "report":       { "pdf": { "get": { "<pdfAlias>(String fileName, Map<String, Object> params)": <methodDetails> },
                               "download(String fileName, List<PdfReferenceDto> pdfs)": <methodDetails>,
                               "email": { "<mailAlias>(...)": <methodDetails>, ... },
                               "push":  { "sendText(String userEmail, String message, List<PdfReferenceDto> pdfs)": <methodDetails>, ... } } },
    "global":       { "rest": { "get(String url)": <methodDetails>, ... }, "<yamlGroup>": { "<fn>(...)": <methodDetails+_returnFields> } },  // rest always; the rest from YAML
    "quota":        { "mail": {"allowedPerDay":{"type":"Integer"}, "usedToday":{"type":"Integer"}},
                      "processes": {"allowed":{"type":"Integer"}, "active":{"type":"Long"}},
                      "users":     {"allowed":{"type":"Integer"}, "current":{"type":"Long"}},
                      "schedulers":{"allowed":{"type":"Integer"}, "current":{"type":"Long"}} },
    "enums":        { "<EnumName>": { "list()": <methodDetails> } },
    "actionName":   {"type":"String"},
    "actionId":     {"type":"String"},
    "rule(String ruleName)": <methodDetails>,
    "crud":         { "<crudAlias>": { "find(...)": <methodDetails>, ... } }        // service.crud.<alias>.<method>()
  },
  "validation": { "addError(String message)": <methodDetails>, "addWarning(...)": ..., "addFieldError(...)": ..., "addFieldWarning(...)": ... }  // ONLY when ruleType==VALIDATION_RULE
}
```

`<methodDetails>` (the executor's convention; e.g. `buildCrudServiceMethods`, `formatMethodInsertText`):

```json
{ "name": "find",
  "returnType": "List<Map<String,Object>>",
  "signature": "List<Map<String,Object>> find(Map params)",
  "parameters": ["Map params"],
  "description": "...",
  "insertText": "find(\n    [\n        key: \"value\"\n    ]\n)",
  "_returnFields": { "id": "String", "name": "String" },  // added UI-side (injectReturnFieldsFromCruds)
  "argValues": { "0": { "ref": "workflows" } }            // optional — see below
}
```

`argValues` is what makes autocomplete work INSIDE a string argument. It is keyed by **zero-based argument
index as a string**, because the same logical argument sits at a different position across overloads and the
editor resolves positionally; every overload of the method contributes, and the offers are merged. The value is
one of three source forms — an inline `[{value, label, comment}]` list, `{"ref":"<setName>"}` into the payload's
root `__argValueSets` (so a list shared by several methods is carried once), or `{"keysOf":"context.data"}`,
which costs nothing extra because those keys are already in the payload. `value` is what goes between the
quotes, `label` is what the dropdown shows, `comment` is appended after the call as a block comment.
Today the platform emits only the `ref` form — two sets: `workflows` for `service.workflow.start`, and
`processTables` for `service.workflow.list` / `actions` / `startActions`. The other two source forms are what
the next annotated argument would use.

An entry may also carry **`expandsCall`**, and that is what makes a hint depend on another argument. Some picks
decide far more than themselves: choosing a workflow decides which contexts and CRUDs the context-data
argument must carry; choosing a process table decides which filter keys and indexed values a listing may be
written against. `argValues` alone cannot express that — it is resolved from the argument index and the hint
root, never from a sibling argument's typed value, and it does not resolve at all inside a Groovy map literal.
So the entry names a KIND of expansion, the editor asks the server for it, and the server rewrites the whole
call with the answers already in it. The kinds are `workflowStart` and `processTable`.

Root keys beginning `__` (today only `__argValueSets`) are payload infrastructure, not language: the editor
filters them out of the top-level suggestion list.

**The key distinction between the three node shapes** that the JS parses:
- **method-details** — a map with a `"signature"` field (String). JS treats it as a method call
  (`isMethodDetails`, `groovy-hint.js`): on an exact match of `get()`/`find(...)` it expands into
  `_returnFields`, so that `method().field` works.
- **typed leaf** — `{"type":"String"}` (no `signature`). JS calls `getTypeSpecificSuggestions(type)` →
  the list of type methods (`String`→`length()`, `trim()`, …).
- **navigable subtree** — an ordinary map of child keys (for example `get()` DTO fields, `security.user()` fields,
  `quota.mail`). JS enumerates the keys as suggestions.

## Per-variant reference

### System 1 — Server-side HintsService tree

#### `context.data.*` (global attributes) — `buildGlobalDataHints` (`HintsService.java`)

Statically contains **only methods** (returnType `ContextDataDto`):

```json
"data": {
  "setAttr(String key, Object value)": { "name":"setAttr", "returnType":"ContextDataDto",
      "signature":"ContextDataDto setAttr(String key, Object value)", "parameters":["String key","Object value"],
      "description":"Set a global attribute", "insertText":"setAttr(\n    \"key\",\n    \"value\"\n)" },
  "getAttr(String key)": { "name":"getAttr", "returnType":"Object", "signature":"Object getAttr(String key)", ... },
  "getAttr(String key, Object defaultValue)": { ... }
}
```

| Key | Node type | Meaning | Backing |
|---|---|---|---|
| `setAttr(String key, Object value)` | method-details | `context.data.setAttr("k", v)` → runtime `getAttr/setAttr` on `GlobalDataWrapper` | `HintsService.java` |
| `getAttr(String key)` | method-details | reading a global attribute | `HintsService.java` |
| `getAttr(String key, Object defaultValue)` | method-details | reading with a default | `HintsService.java` |

> The runtime sugar `context.data.<name>` / `context.data.<name> = v` (property get/set → `getAttr/setAttr`)
> **always works** (engine `DynamicRuleContext.groovy`),
> but statically the attribute names are NOT known → they are provided by System 2 below.

#### `context.currentData.*` — `buildCurrentDataHints` (`HintsService.java`)

`put(Object value)`, `get()`, `setAttr(...)`, `getAttr(...)`. Relevant only in **nested forms** (list item);
in the parent form `get()` returns null. `get()` here is method-details **without** `_returnFields`; System 2
fills in `_returnFields` with the real fields of the current element (`injectCurrentData`).

> ⚠️ **`setAttr`/`getAttr` here are a hint-tree artefact — do not write them.** At runtime `currentData`
> is a `CrudDataDto`, whose whole surface is `get()`, `put(...)`, `getField(...)`, `setField(...)`,
> `hasField(...)`; calling `getAttr`/`setAttr` on it throws `MissingMethodException`. Attributes exist only on
> the global scope (`context.data.*`) and the context scope (`context.<alias>.data.*`).

#### `context.<alias>.data.*` — `buildContextDataHints` (`HintsService.java`)

Same as `context.data.*`, but `returnType` = `ContextData`. Attribute scope = the context. The tree node key is
the context's **alias** (`hints.put(context.getAlias(), contextMap)`, `HintsService.java`).

#### `context.<alias>.<crudAlias>.service.*` — `buildCrudServiceMethods` (`HintsService.java`)

Real CRUD methods (the same ones as in `dynamic-cruds.json.cruds[].methods[]`, see
[11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)). Each method is method-details, key =
`"<name>(<Type1 p1>, <Type2 p2>)"`, `insertText` = a multi-line call with sample values
(DTO parameter → Groovy map literal). The methods are fetched over RSocket from the live integration (register-time cache or
`getServiceMethods`).

The same map is reused under `service.crud.<crudAlias>` (`HintsService.java`), so that
`context.<ctx>.<crud>.service.find(...)` ≡ `service.crud.<crud>.find(...)`.

#### `context.<alias>.<crudAlias>.data.get()` — `addCrudDataMethods` (`HintsService.java`)

`get()` — a map of the CRUD's DTO fields (**NOT** method-details: no `signature`). Dotted paths
(`"address.street"`) expand into nested maps (`HintsService.java`). A field leaf =
`{"type":"<FieldClass.getSimpleName()>"}`; no class → `"Object"`. `put(...)`, `setAttr(...)`
`getAttr(...)` — method-details (returnType `CrudDataDto`).

> ⚠️ Same artefact as for `currentData`: the `setAttr`/`getAttr` entries are **hint-only**. The wrapper behind
> `data` resolves calls reflectively against `CrudDataDto`, which has no such methods, so
> `context.<ctx>.<crud>.data.getAttr('x')` fails at runtime (`MissingMethodException`, rethrown as
> "Failed to execute data.getAttr()"). Write `getField('<col>', <Type>.class)` / `setField('<col>', v)` for
> columns, and use `context.data.*` / `context.<alias>.data.*` for attributes.

#### `service.*` — `buildServiceMap` (`HintsService.java`)

| Key | What | Backing |
|---|---|---|
| `service.access.*` | `addRoleAccess`, `removeUserAccess`, `hasRoleGroupAccess`, `getRoleAccesses()`, … | `buildAccessManagementMethods` |
| `service.rimm.*` | `query(...)`, `run(...)` (running saved queries by name) | `buildRimmServiceMethods` |
| `service.security.*` | `user()` (navigable: `id/email/firstName/lastName`, all `{type:String}`), `hasAnyRole(String... roles)`, `hasAllRoles`, `hasAnyRoleGroup`, `hasAllRoleGroups` (all `boolean`) | `buildSecurityMethods` |
| `service.notification.push.*` | `sendText`, `sendAlert`, `sendWarning`, `sendError`, `sendReminder`, `*ToRole`, `*ToRoleGroup` (see full list below) | `buildPushNotificationMethods` |
| `service.notification.mail.<alias>(...)` | **TWO overloads** per mail-template alias (see below) | `buildMailNotificationMethods` |
| `service.report.pdf.*` | PDF generation/download/delivery (see the subsection below) | `buildReportHints` → `buildPdfReportHints` |
| `service.global.rest.*` | always: `get/post/put/delete/patch/head/options` (× no-body / +Map options) | `GlobalFunctionsService.buildRestHints` |
| `service.global.<yamlGroup>.<fn>(...)` | functions from `globalFunctions.yaml` (dynamically) | `GlobalFunctionsService.processGroup` / `addFunctionHint` |
| `service.quota.{mail,processes,users,schedulers}` | typed leaves `{type:Integer/Long}` (property access) | `buildQuotaHints` |
| `service.enums.<EnumName>.list()` | the project enum registry | `buildEnumsHints` |
| `service.workflow.start(...)` | starting a process; **two overloads**, both annotating argument 0 with the `workflows` value set so the identifier autocompletes inside the quotes, and both expanding the whole call when one is picked | `buildWorkflowHints` + `attachArgValueSets` |
| `service.workflow.list / actions / startActions / contextData / complete` | working an existing case; the settings-id argument is annotated with the `processTables` value set and expands the whole call, writing that table's real filter keys and naming its indexed values | `buildWorkflowHints` + `attachArgValueSets` |
| `service.actionName` / `service.actionId` | typed leaf `{type:String}`; set when the rule is invoked from an action button | `HintsService.java` |
| `service.rule(String ruleName)` | invoking another rule by name | `HintsService.java` |
| `service.crud.<crudAlias>.<method>()` | flat synonym for `context.<ctx>.<crud>.service.<method>()` | `HintsService.java` |

##### `service.notification.mail.<alias>` — **two overloads** per alias (`HintsService.java`)

For **each** mail-template alias, `buildMailNotificationMethods` puts **two** entries (not one):

```json
"<alias>(List<String> recipients, Map<String, String> placeholders)":                 { "returnType":"void", ... },
"<alias>(List<String> recipients, String subject, Map<String, String> placeholders)": { "returnType":"void", ... }
```

The first uses the template's default subject, the second accepts a custom subject. Placeholders are sampled from
`MailTemplateAliasInfoDto.getPlaceholders()` (a bare slot `key: "key"`). The aliases are **your project's own** —
whatever `rep-objects.json.mailTemplates` defines (typically a few account-lifecycle ones such as
`userRegistration` / `passwordRecover`, plus business ones such as `invoiceIssued` or `approvalRequested`) — so
that, for example, `service.notification.mail.invoiceIssued([...], [...])` becomes available.

##### `service.notification.push.*` — full list (`HintsService.java`)

15 methods (5 base × 3 addressings):

| Method | Parameters | Return |
|---|---|---|
| `sendText` | `(String userEmail, String message)` | `void` |
| `sendAlert` | `(String userEmail, String title, String message)` | `void` |
| `sendWarning` | `(String userEmail, String title, String message)` | `void` |
| `sendError` | `(String userEmail, String title, String message)` | `void` |
| `sendReminder` | `(String userEmail, String title, String description, LocalDateTime dueDate)` | `void` |
| `sendTextToRoleGroup` | `(String roleGroupName, String message)` | `int` |
| `sendAlertToRoleGroup` | `(String roleGroupName, String title, String message)` | `int` |
| `sendWarningToRoleGroup` | `(String roleGroupName, String title, String message)` | `int` |
| `sendErrorToRoleGroup` | `(String roleGroupName, String title, String message)` | `int` |
| `sendReminderToRoleGroup` | `(String roleGroupName, String title, String description, LocalDateTime dueDate)` | `int` |
| `sendTextToRole` | `(String roleName, String message)` | `int` |
| `sendAlertToRole` | `(String roleName, String title, String message)` | `int` |
| `sendWarningToRole` | `(String roleName, String title, String message)` | `int` |
| `sendErrorToRole` | `(String roleName, String title, String message)` | `int` |
| `sendReminderToRole` | `(String roleName, String title, String description, LocalDateTime dueDate)` | `int` |

`*ToRoleGroup`/`*ToRole` return `int` (the number sent). The same 5 base names recur in
`service.report.pdf.push.*`, but with an additional trailing parameter `List<PdfReferenceDto> pdfs`.

##### `service.report.pdf.*` — PDF generation/download/delivery (`buildPdfReportHints`, `HintsService.java`)

The `service.report.pdf` tree has **four** branches:

| Branch | Shape | What | Backing |
|---|---|---|---|
| `pdf.get.<pdfAlias>(String fileName, Map<String, Object> params)` | method-details, `returnType:"PdfReferenceDto"` | build a `PdfReferenceDto` from a PDF template; one method per pdf-template alias | `buildPdfGetMethods`; sig |
| `pdf.download(String fileName, List<PdfReferenceDto> pdfs)` | method-details, `returnType:"byte[]"` — ⚠️ stale, see below | merge `PdfReferenceDto`s into one PDF (`byte[]`, + save to file storage) | `buildPdfDownloadMethod` |
| `pdf.email.<mailAlias>(...)` | **2 overloads** per mail-alias, `returnType:"void"` | send an email with PDF attachment(s): `(List<String> recipients, Map<String, String> placeholders, List<PdfReferenceDto> pdfs)` and `(…, String subject, …)` | `buildPdfEmailMethods`; sig1, sig2 |
| `pdf.push.*` | 15 methods, like push above, but with a trailing `List<PdfReferenceDto> pdfs` | the same `sendText/Alert/Warning/Error/Reminder` (`ToRole`/`ToRoleGroup`) with a PDF attachment | `buildPdfPushMethods` |

> ⚠️ **The `pdf.download` label in the hint tree is STALE.** The row above reflects what `HintsService`
> (`buildPdfDownloadMethod`) actually puts into the tree (`returnType:"byte[]"`, "merges into one PDF"),
> but the **real** `PdfReportProxy.download` (`nct-executor/.../PdfReportProxy.groovy`) is **`void`
> asynchronous fire-and-forget**: it queues a Kafka request, nct-pdf renders/merges the PDF and POSTs the bytes into a per-user
> inbox file-storage, and a UI poller opens the browser save dialog (~10 s). `byte[]` is **not returned** — do not
> assign the result of `download(...)`. Details — [16-groovy-service-api.md](16-groovy-service-api.md) §2.6.

`pdf.get` is empty if the project has no PDF templates (`safeFetchPdfAliases` returned an empty list — the normal
state of a project that has not authored any). `pdf.email`, by contrast, uses **mail** aliases
(`safeFetchMailAliases`), so `pdf.email.<yourMailAlias>(...)` entries are present **even with zero PDF
templates** — an empty `pdf.get` next to a populated `pdf.email` is expected, not a broken tree. PDF today is
the `report.pdf.templates.plugin` plugin (see [00-export-format-and-import.md](00-export-format-and-import.md);
the historical `PdfPlugin`/`PdfPagePlugin` does not exist).

##### `service.global.*` — YAML functions + always-`rest`

`service.global` = Lombok `@Getter` over the `GlobalFunctionsService.hintsStructure` field
(`GlobalFunctionsService.java`), which is populated at startup (`@PostConstruct init`) from two sources:

1. **YAML functions** — `processGroup`/`addFunctionHint` read `globalFunctions.yaml`. Groups/functions are
   dynamic (depend on the project YAML) → **not enumerable** from the export. Leaf shape —
   method-details `+_returnFields`.
2. **`service.global.rest.*` — a fixed branch, always added** by `buildRestHints`, independent of
   YAML (registered in `hintsStructure.put("rest", ...)`). Seven HTTP methods, each in two overloads:

| Key | Parameters | Return |
|---|---|---|
| `get(String url)` / `get(String url, Map options)` | url [+ `[headers, query, timeout]`] | `RestResponse` |
| `post(String url)` / `post(String url, Map options)` | url [+ `[headers, body, query, timeout]`] | `RestResponse` |
| `put(String url)` / `put(String url, Map options)` | url [+ body-options] | `RestResponse` |
| `delete(String url)` / `delete(String url, Map options)` | url [+ no-body-options] | `RestResponse` |
| `patch(String url)` / `patch(String url, Map options)` | url [+ body-options] | `RestResponse` |
| `head(String url)` / `head(String url, Map options)` | url [+ no-body-options] | `RestResponse` |
| `options(String url)` / `options(String url, Map options)` | url [+ no-body-options] | `RestResponse` |

`RestResponse` in the description has the fields `status(int)`, `ok(boolean)`, `body`(parsed JSON Map/List or String),
`text`(raw String), `headers`(Map). The body methods (`post/put/patch`) in `insertText` suggest
`[headers, body, query, timeout]`; the no-body ones (`get/delete/head/options`) — `[headers, query, timeout]`.

##### `service.quota.*` — all typed leaves (`buildQuotaHints`, `HintsService.java`)

```json
"quota": {
  "mail":       { "allowedPerDay": {"type":"Integer"}, "usedToday": {"type":"Integer"} },
  "processes":  { "allowed": {"type":"Integer"}, "active":  {"type":"Long"} },
  "users":      { "allowed": {"type":"Integer"}, "current": {"type":"Long"} },
  "schedulers": { "allowed": {"type":"Integer"}, "current": {"type":"Long"} }
}
```

This is property access (`service.quota.mail.usedToday` and so on), a fixed set — all 8 leaves are known from the code.

#### `validation.*` — only when `ruleType==VALIDATION_RULE`

`addError(String)`, `addWarning(String)`, `addFieldError(String, String)`, `addFieldWarning(String, String)`
(`buildValidationMethods`, `HintsService.java`). The result wrapper: `{context, validation, service}`
(`HintsService.java`). For `EXECUTION_RULE`/`PREDICATE` → `{context, service}`.

#### No contexts (`contextIdentifiers` empty/null) — `buildMinimalHints` (`HintsService.java`)

`context` contains only `data` + `currentData`; `service` — all the same **plus** `service.crud.<alias>` for
**every** registered CRUD (`addAllRegisteredCrudsToServiceMap`). That is, `service.crud.*` is
reachable even without any selected contexts; only `context.<alias>.*` is empty there.

### System 2 — Live context-data hints (`LiveContextDataHints`, only with a live form)

Merged into the System 1 tree **in place**, UI-side, after `injectReturnFieldsFromCruds`
(`RuleEditorField.java`). The source is the live `ContextDataDto` captured off the page. Merge targets
(`LiveContextDataHints.inject`):

| Target | From what | Method |
|---|---|---|
| `context.data.<attr>` | `live.getAttrs()` (global) | `mergeAttrs` (call) |
| `context.<alias>.data.<attr>` | `live.getContextDataMap().get(id).getAttrs()`; `id→alias` via `loadIdentifierToAlias` | `inject`, `mergeAttrs` |
| `context.<alias>.<crud>.data.get().<field>` (overlay onto the live entity) | `ContextData.crudDataMap[crudAlias].getValue()` (JsonNode) | `overlayCrudEntities` → `overlayLiveObject` |
| `context.currentData.get()._returnFields.<field>` | `crudDataMap["__temp_item__"]` in the `"__temp_list_item_context__"` context | `injectCurrentData` |

The shape of the added node (`buildNode`) is the System-2-specific shape with `displayText`:

```json
// scalar → leaf
{ "type": "String", "insertText": "status", "displayText": "status : String" }
// object → navigable via __fields
{ "type": "Object", "insertText": "order", "displayText": "order : Object",
  "__fields": { "customer": {"type":"String","insertText":"customer","displayText":"customer : String"} } }
// array-of-objects → navigable via __element (list[0].field)
{ "type": "List", "insertText": "items", "displayText": "items : List",
  "__element": { "sku": {"type":"String",...}, "qty": {"type":"Integer",...} } }
```

| Node field | Type | Meaning | Backing |
|---|---|---|---|
| `type` | String | type inference from JsonNode: text→`String`, bool→`Boolean`, int/short→`Integer`, long/bigint→`Long`, bigdec→`BigDecimal`, float→`Double`, array→`List`, null/else→`Object` | `typeName`, `LiveContextDataHints.java` |
| `insertText` | String | the **bare** attribute name — what gets inserted into the editor | `buildNode` |
| `displayText` | String | `"<name> : <Type>"` — what is shown in the dropdown | `buildNode` |
| `__fields` | Map | the object's child fields (recursion up to `MAX_DEPTH=6`) | `buildNode`; `MAX_DEPTH` |
| `__element` | Map | fields of the first object element of the list (`firstObjectElement`) | `buildNode`; `firstObjectElement` |
| `_returnFields` | Map | fields of the current list item under `currentData.get()` (like the methods) | `injectCurrentData` |

`buildNode` assigns `type/insertText/displayText` for a scalar, while the type inference itself is done by
`typeName(JsonNode)`. The object/array branches hard-code `"Object"`/`"List"` and
recursively populate `__fields`/`__element`.

**The map key is always the bare name** (`status`, `order`), so that `context.data.status.` continues navigation to
the type methods; `displayText` carries the label. Existing static entries are **not touched**: `mergeAttrs`
skips keys that are already present, `overlayLiveObject` only adds missing fields and
makes the existing leaf navigable (`navigableFields`), without rewriting scalars.

**HIDDEN_ATTR_KEYS** — 9 internal keys (`_crudAlias`, `_crudEntityId`, `__actionId`
`__actionName`, `__methodParams`, `__currentItem__`, `__currentItemIndex__`, `__listItem__`, `__localize__`)
are **never** offered in autocomplete (`isHidden`; checked in `mergeAttrs`, `addObjectFields`
`overlayLiveObject`). The runtime `getAttr/setAttr` for them still works — only the hint is suppressed.
This is an explicit set of 9 keys, NOT a rule based on the `__` prefix.

## How it reaches the browser (data flow)

1. `RuleEditorField.getHints()` → Feign `UiMcpClient.getRuleHints(realm, client, RuleHintsRequestDto)`
   (`UiMcpClient.java`) → HTTP `POST /api/hints/tenant/{realm}/{client}/getRuleHints` to the executor
   (`HintsController.java`, `@PreAuthorize("isAuthenticated()")`, JWT forwarded).
2. Executor `HintsService.buildRuleHints` → returns `{context, service, validation?}`.
3. Back in the UI: `injectReturnFieldsFromCruds(hints)` — for each CRUD alias it loads the methods
   (`bl.getCrudByAlias` → `bl.getMethods`) and puts `_returnFields` into the method entries (for `method().field`).
4. `injectLiveContextDataHints(hints)` — reads the live `ContextDataDto` off the page
   (`readLiveContextData` → `BasePage.getAttribute("nct.live.form.contextData")`). If null → return
   (dialog from the Rules list). Otherwise `LiveContextDataHints.inject(hints, live, identifierToAlias)`.
5. The rule editor field serializes the hint tree into the component's JS model.
6. `GroovyField.js` puts it into `hintOptions.serverHints = this.model.hints` and calls
   `editor.showHint(hintOptions)` on `inputRead` (after a `.` or a letter/digit).

## How `groovy-hint.js` parses the expression and walks the tree

0. **argValueHint** — checked FIRST and returns early. If the cursor is inside a single-line string literal that
   is an argument of a call the tree knows (`stringLiteralBounds` + `findEnclosingCall`), the offers are that
   argument's `argValues` and picking one replaces the whole literal content. This branch has to run before
   step 1, because step 1 treats a quote as a hard boundary and would have thrown the context away. It declines
   what it should: an interpolated GString, a slashy regex literal, a triple-quoted block.
1. **extractExpression** — scans **backwards** from the cursor, collecting a member-access chain: it walks over
   `[A-Za-z0-9_$.]` and balanced `()`/`[]` (+ Groovy `?.`/`*.`), and **any** operator/space/quote is a
   boundary. That is why hints work on `!context.a.b`, `-x.y`, `a == b.c` — a leading/infix operator is not
 glued onto the first identifier. Outside a string literal, a quote is still an unconditional boundary.
2. **resolveMultilineExpression** — stitches together multi-line chains (`.` on a new/previous line).
3. **parseChainParts** — splits on `.`, respecting parentheses and string literals (so that `format(d,"yyyy-MM-dd")`
   is not split on the dots inside the pattern). `stripChainMarker` removes a trailing `?`/`*` of `?.`/`*.`.
4. **walkServerHintChain** — walks the tree:
   - exact key match + it is method-details (`isMethodDetails`) → expand into `_returnFields`;
   - node with `__fields` → descend into `__fields` (navigation over the live object);
   - `list[0]`/`list[i]` → descend into `__element`
   - `foo(...)` without an exact key → prefix-match `"<name>("` → its `_returnFields`.
5. **getServerHintSuggestions** — resolves the chain (plus a fallback on `var x = ...`/`def x = ...`
   via `resolveVariableToHintNode`), then builds the suggestion list from the resolved node:
   - if the node has a `type` → `getTypeSpecificSuggestions(type)` (type methods);
   - otherwise it enumerates the keys. **For each value** with `insertText` **and/or** `displayText`
     it returns `{ text: value.insertText || key, displayText: value.displayText || key }` — so a
     live attribute shows `"name : Type"`, inserts the bare `name`, and the key stays bare (navigation intact).
     Entries with only `insertText` (methods) behave as before.

## How to construct from scratch (what is available in a rule → how to write `ruleScriptStr`)

The hints are built automatically from the export; you cannot "construct" them directly. The recipe is how to ensure
that the required symbols are available, and how to use them in the rule body.

**Step 1. Make `service.crud.<alias>.*` / `context.<ctx>.<alias>.*` available.** The rule must reference a
context that contains the required CRUD:

```json
// rep-objects.json → contexts[]
{ "identifier":"871f974f-e775-401a-adfc-e822110f3b99", "name":"Customs Context",
  "alias":"customs_context", "crudAliases":["declarations_cruid","consignments_cruid","users_cruid","bl"] }
// rep-objects.json → rules[]
{ "identifier":"<rule-uuid>", "name":"Declaration Delete", "ruleType":"EXECUTION_RULE",
  "executor":"GroovyExecutionRule", "contextIdentifiers":["871f974f-e775-401a-adfc-e822110f3b99"],
  "rule": { "ruleScriptStr": "..." } }
```

The tree will then give: `context.customs_context.declarations_cruid.service.find(...)`,
`context.customs_context.declarations_cruid.data.get().<dtoField>`, and the synonym `service.crud.declarations_cruid.find(...)`.
(The `ruleType`↔`executor` correspondence is a strict 1:1, see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md):
`EXECUTION_RULE`→`GroovyExecutionRule`, `PREDICATE`→`GroovyPredicate`, `VALIDATION_RULE`→`GroovyValidationRule`.)

**Step 2. The rule body.** The symbols (all from System 1, available in any editor with this context):

```groovy
// the CRUD row entity (data.get() → the map of DTO fields; a form fills it field-centrically, a table row-wise)
def declaration = context.customs_context.declarations_cruid.data.get()
// calling a CRUD method
def rows = context.customs_context.declarations_cruid.service.find([ status: "ACTIVE" ])
// or the flat synonym
def rows2 = service.crud.declarations_cruid.find([ status: "ACTIVE" ])
// ⚠️ TRAP: a PARTIAL filter map like [status:"ACTIVE"] can fire "could not determine data type of parameter $1" (untyped $1) unless findAll is COALESCE-guarded — use findAll([:]) (all keys absent) or the acFindBy<X>Like search pipeline (02 §4a). Optional-filter SQL must be written as IS NOT DISTINCT FROM COALESCE(:p, col).
// service.*
def me = service.security.user()
if (service.security.hasAnyRole("ADMIN")) { /* ... */ }
service.rule("Some Other Rule")
// REST / global functions / reports
def resp = service.global.rest.get("https://example.com/api")   // resp.status, resp.ok, resp.body
def pdf  = service.report.pdf.get.invoice("invoice.pdf", [ id: invoice.id ])
service.report.pdf.email.invoiceIssued(["u@x.com"], [ name: "N" ], [pdf])
return true            // PREDICATE/EXECUTION: always an explicit return (see 08-groovy-rules-and-context.md)
```

> **Choices rule (dropdown / autocomplete / tree-picker options source)?** Its **last statement MUST convert** the rows to option pairs:
> `return service.global.conversion.toSelectOptions(list,"<key>","<display>")` for a dropdown/tree (localized display → `toSelectOptionsLocalized`),
> `toAutoCompleteOptions(list,"<display>")` for autocomplete. A raw `find`/`findAll` entity list renders the picker blank ("No results found") **and**
> hides Show Nav — full recipe [02 §4a](02-form-controls-reference.md).

**Step 3 (form only).** The attributes `context.data.<name>` / `context.<alias>.data.<name>` will appear in
autocomplete **only** when the dialog is opened from a form's settings (System 2). At runtime the sugar always works:

```groovy
context.data.myFlag = true            // == context.data.setAttr("myFlag", true)
def x = context.data.myFlag           // == context.data.getAttr("myFlag")
```

That is, in the rule body you can write `context.data.<name>` even if the hints did not show it — the
`DynamicRuleContext` engine resolves the property get/set into `getAttr/setAttr`. Name autocompletion is a matter of convenience, not
correctness.

## Gotchas

- **Two systems — different lifecycles.** System 1 (executor) is **static**: built from the *definitions* of
  contexts/CRUD, available in any rule editor. System 2 (live) — only when there is a live `ContextDataDto`
  on the page (form / form button). In the dialog from the Rules list `injectLiveContextDataHints` is a no-op
  (`RuleEditorField.java`), so there will be no live attribute names there — but the runtime sugar still works.
- **The hints are not in the export.** Do not try to patch the "hint tree" in `.mrjun` — it does not exist. Control it via
  `rule.contextIdentifiers` + `contexts[].crudAliases`.
- **`get()` is NOT method-details, it is a field map.** In `context.<ctx>.<crud>.data.get()` the value is a map of
  DTO fields (no `signature`), so JS enumerates the fields rather than "expanding a call". And `security.user()`,
  `currentData.get()` are also navigable maps/fields. Do not confuse them with method-details (`find(...)` etc.), which
  have `_returnFields`.
- **`_returnFields` is added UI-side.** For `method().field` (`find(...).status`) the executor does NOT put `_returnFields`
  itself; they are filled in by `injectReturnFieldsFromCruds` in `nct-ui` (`RuleEditorField.java`), reading
  `bl.getMethods`. If the BL channel is unavailable — `method().field` does not resolve (the method call itself does resolve).
- **Alias vs identifier.** The hint tree is keyed by the context's **alias** (`hints.put(context.getAlias(), contextMap)`, `HintsService.java`), while the live
  `contextDataMap` is keyed by **identifier**. The bridge is `loadIdentifierToAlias` (`RuleEditorField.java`); without it
  System 2 would not be able to find the `context.<alias>` node.
- **HIDDEN_ATTR_KEYS.** 9 internal keys are never hinted (`LiveContextDataHints.java`), but
  they work at runtime. This is an explicit set, not a rule based on the `__` prefix.
- **Orphan aliases are skipped.** If a context lists a CRUD alias that is not in the executor's live registry
  (a legacy context, an integration that is still starting up), it will not make it into the tree
  (`HintsService.java`) — it disappears from the dropdown until the integration re-registers.
- **`service.crud.*` is broader than the contexts.** Even without any selected contexts (`buildMinimalHints`),
  `service.crud.<alias>.<method>()` is available for all registered CRUDs, because runtime reachability
  is not limited to the bound contexts. Only `context.<alias>.*` is empty there.
- **`service.global` is two-part.** `service.global.rest.*` is a fixed branch (`buildRestHints`,
  `GlobalFunctionsService.java`), always present, independent of `globalFunctions.yaml`. The other groups
  `service.global.<group>.<fn>` come from YAML, are dynamic, and cannot be enumerated from the export. `service.global` is a
  Lombok `@Getter` over the `hintsStructure` field, not a hand-written method.
- **`service.report.pdf.email` uses mail aliases, `pdf.get` uses pdf aliases.** That is why `pdf.email.*` can be
  non-empty in a project that has no PDF templates at all. The PDF plugin today is `report.pdf.templates.plugin`.
- **`service.notification.mail` gives 2 overloads per alias** (`HintsService.java`): with and without a subject.
  Not "one method per alias".
- **`displayText` requires support in JS.** A System 2 leaf carries `insertText`+`displayText`; `getServerHintSuggestions`
  (`groovy-hint.js`) shows `displayText`, inserts `insertText`, and the map key is bare. Method entries
  (only `insertText`) behave as before — backward compatibility.
- **The hint tree is cached in the JS model at render time** — selecting a different context on an
  already-open editor does not re-fetch it; re-render the field.
- **Only `RuleEditorField`, not `GroovyMethodEditorField`.** Live hints are merged only in the rule editor;
  the CRUD method editor (`GroovyMethodEditorField`) has no live form data.
- **The PREDICATE enum string.** In `RuleHintsRequestDto`/`rule.ruleType` a predicate is `PREDICATE` (not
  `PREDICATE_RULE`), see `RuleType.java`; the javadoc in HintsService sometimes writes `PREDICATE_RULE` inaccurately.
  An unknown string → the default `EXECUTION_RULE` (`parseRuleType`, `HintsService.java`).
