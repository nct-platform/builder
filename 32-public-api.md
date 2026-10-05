# 32 · Public API — another system calling the project

> **Scope.** What it takes for ANOTHER system — a partner's backend, a mobile app, a customer portal, a
> nightly job somewhere else — to read the project's lists and press the project's buttons over REST: what can
> be exposed, how to author the tables, actions, forms and rules so that they answer a machine exactly as they
> answer a person, who a call acts as, what travels with an archive and what never does, and what you hand over
> so the recipient can switch it on and prove it works.
> Read it the moment a PRD says *"the partner's system submits applications"*, *"our app shows customers their
> open requests"*, *"the ERP pushes new suppliers"*, *"approve from the mobile app"*, or *"integrate with
> `<system>` over an API"*.
> **Not here:** the project calling somebody ELSE's API from a rule → [16](16-groovy-service-api.md) §2.2; a
> rule working an existing case → [16](16-groovy-service-api.md) §2.13; the process-table model and its three
> action buckets → [05](05-crud-tree-and-process-table.md); records-table actions and the fetch rule →
> [04](04-crud-table-plugin.md); form groups and routing → [06](06-form-groups-and-mapping.md); field
> validation → [02](02-form-controls-reference.md), [25](25-form-settings-validation-and-events.md); the MCP
> channel a builder uses to change a live project → [28](28-support-mode-over-mcp.md).

---

> ## ⛔ Read this before you plan anything: the KEYS are never in the `.mrjun`, and you do not author the ENDPOINTS
>
> An API **key** is a credential, shown once to the person who creates it and stored nowhere a project archive
> reaches. No export carries one, no import creates one, no environment publish copies one — and no `mrjun.py`
> command writes one, because a key inside an archive would be a key in every copy of that archive.
>
> The **endpoints** — which table is exposed, which of its operations and actions, who the calls act as — are
> configured live in **Settings → Developer → API** after import. An export of a live project does carry them,
> as `rep-objects.json` → `apiExposures`, and that key is DESTRUCTIVE on import: a list makes the target's
> endpoints exactly that list, and an empty list `[]` deletes every endpoint and every key binding the target
> has. **A build you author leaves the key out** (§6).
>
> **What you author offline:** the process tables, records tables, actions, forms, filter forms and rules the
> endpoints will expose — written the API-friendly way (§3) — and the rules a rule-call endpoint runs, each
> written as a contract (§3.15).
> **What the recipient does once, live, after importing:** creates a key per calling system, creates the
> endpoints your handover lists, binds the key to them, and gives each integrator the base URL, their key and
> the OpenAPI description that key returns (§8).
>
> Plan for that. An endpoint with no key bound answers **404** to every call, so a build whose handover forgets
> the binding step looks exactly like a build whose API is broken.

| | |
|---|---|
| Where it is configured | Settings → **Developer** → **API** (live; members of the **Author** or **Developer** role group, customer projects only — membership, not the "I am the author" switch) |
| Base URL | `https://<platform-host>/public-api/v1` — the address the API tab shows: the platform's own host. Hand over that one, not a project's custom domain |
| What can be exposed | a **Process Table** node, a **CRUD Table** node, the project's **sign-in** (one Login endpoint, path `auth`), and **rule calls** — an endpoint grouping operations, each an HTTP method and path that runs ONE rule the author picked (§3.15). Not a CRUD tree, not a CRUD method, not a query — and never a rule by its name |
| Credentials | `X-Api-Key: <key>` on every call — the calling APPLICATION. Plus `Authorization: Bearer <access token>` from the Login endpoint — the PERSON — on endpoints whose callers sign in |
| Who a call acts as | the signed-in person; or, on an endpoint the author set to *Service account*, one named project member (§4). Never anonymous |
| What a call runs | the table's OWN list, actions, forms and rules — or, on a rule call, the one rule its operation names — on the PUBLISHED branch, with the screen's checks — there is no API-only logic to write and none to bypass |
| In the `.mrjun` | endpoints: the optional `rep-objects.apiExposures` an export writes — **leave it out when you author**; keys, bindings, sessions: never |
| Offline gate | `validate` REFUSES an `apiExposures` key that is `[]` or a list (§6) — `mrjun.py api-exposures drop` removes it. It cannot see keys, bindings, or whether an endpoint will answer — nothing offline can |

> **🔧 Tooling.** There is **no** `mrjun.py` command that writes endpoints or keys, deliberately: a key cannot
> exist offline, and an endpoint authored offline would replace the target's live endpoints on import. For the
> key an export of a live project writes there are two: `mrjun.py api-exposures show` (what it would do on
> import, and the endpoints and rule-call operations it carries — `inspect` prints the same verdict, without the
> list) and `mrjun.py api-exposures drop` (removes it); `validate` refuses `[]` and a
> list until it is gone (§6). What you DO run is the ordinary chain for what the endpoints expose —
> `node add`/`node patch-model` for the tables ([04](04-crud-table-plugin.md),
> [05](05-crud-tree-and-process-table.md)), `formgroup add`/`form add` ([06](06-form-groups-and-mapping.md)),
> `rule add` ([08](08-groovy-rules-and-context.md)) — then `validate` → `pack`. Full index —
> [`tools/README.md`](tools/README.md).

---

## 1 · When the PRD means this — and what each sentence asks you to expose

The reader's problem is recognition. "API" in a PRD means three different things, and only one of them is
this document:

| PRD says | Means | This doc? |
|---|---|---|
| "the partner's system submits …", "our mobile app lets the customer …", "the portal shows …", "approve from the app" | **another system calls the project** | **yes** |
| "notify the partner's system", "push the result to the ERP", "call the scoring service" | the project calls **another** system | no — outbound REST from a rule, [16](16-groovy-service-api.md) §2.2 |
| "200 REST endpoints", "API-first", "everything has an API" | a sales sentence | no — expose the specific lists and buttons a named caller needs; nothing else is ever reachable |

Then translate each inbound sentence into **what is exposed** and **what you must build for it**:

| PRD phrasing | Exposure | Operations | What you must build (offline) |
|---|---|---|---|
| "the partner submits an application", "the portal opens a claim", "file a request from the app" | **Process table** | collection action (a START action) | a `userStartProcessActions` entry on the worklist's `process.table.pluin` with `direct:"off"` + a start form whose fields are the payload ([05](05-crud-tree-and-process-table.md), [27](27-event-driven-process-start.md) §2.0) |
| "the customer sees the status of their requests", "list my open cases in the app" | **Process table** | list, get one | columns for what the caller reads; `indexSettings` + a filter form for what they search on (§3.6) |
| "the reviewer approves from their own tool", "sign off in the mobile app" | **Process table** | item actions (TASK, GLOBAL) | the BPMN task's actions or global actions, each with a predicate that admits the caller (§3.3, §3.4) |
| "the ERP reads our price list / customer master" | **CRUD table** | list, get one | the records table, its fetch rule, and item access — an id filter the fetch rule honours (§3.7) |
| "the webshop creates the order", "the ERP pushes new suppliers" | **CRUD table** | collection action (a CREATE action) | a `createActions` entry, its form, and the before-complete rule that writes the row ([04](04-crud-table-plugin.md)) |
| "set the delivery status from the courier's system" | **CRUD table** | item action (a ROW action) | an `editActions` entry — direct, or with a form — and its writing rule |
| "users sign in to our app with their project account" | **Login** | sign in, refresh, sign out, who-am-I | nothing offline: the users and their role groups (§4) |
| "a nightly job in another system", "machine to machine, no person involved" | any of the above, callers = **service account** | — | a role group for the integration and page/predicate access for it (§4) |
| "the partner's system asks us for a price / a quote", "calculate the fee for …", "return the stock of …" | **Rule call** | an operation `GET /<slug>/<path>?<param>=…` — or `POST` with a body when the input is a document | an EXECUTION rule that reads its inputs and RETURNS the answer as data (§3.15) |
| "check whether the customer is eligible", "may this order be placed?" | **Rule call** | an operation answering `true` / `false` | a PREDICATE rule (§3.15) |
| "pre-check the application before it is sent" | **Rule call** with a form body (its `/validate` checks the form alone) — or the dry run of the action that will submit it (§2) | `POST /<slug>/<path>` | a VALIDATION rule, or a form whose validators do it (§3.15) |

**Sentences that look like this and are not — say so in the plan rather than building around them:**

- *"Bulk update 500 records in one call"* — there is no multi-row execution. "Bulk" exists only as action
  DISCOVERY for up to 100 items in one call; each action runs per item. A genuine batch is ONE action whose
  before-complete rule does the work — design it on purpose; the API does not add one.
- *"Upload the scanned document with the application"* — a file-upload control is read-only through the API
  (§3.8). Agree another route with the customer (a URL field, a later upload by a person).
- *"The provider calls us back when the signature is done"* — a webhook sender that cannot attach an
  `X-Api-Key` header cannot call this API.
- *"Expose our tables as CRUD/REST"* — refuse the framing. The API exposes the **lists and buttons people use**,
  with their rules and validations. A caller never runs `findAll`, a CRUD method, a query or a rule by name — a
  rule call runs one rule the AUTHOR chose, at an address the author chose, with the inputs the author declared.

**The inventory row.** In [19](19-build-decision-procedure.md) Phase 1a, a process another system opens is
recorded by the button it presses, with **`+ API CALL`** after it — `START ACTION + API CALL` (a start action
with a start form) or `DOCUMENT ACTION + API CALL` (a records action whose rule starts the case), whether
people press that button too or not: one button is one starter, however many callers. And every list or button
a named external caller needs becomes a row in the handover table (§8). A row left out is an endpoint nobody
creates.

---

## 2 · The model: key → endpoint → table → actions → form

```
API key (the calling application)            one per calling system; bound to the endpoints it may call
  └─ endpoint  /public-api/v1/<slug>          one exposed table, addressed by the table node's uniqueIdentifier
       ├─ operations switched on              List · Get one
       ├─ actions switched on, one by one     each with an optional PINNED form out of its form group
       ├─ callers                             signed-in users (default) | a named service account
       └─ item access (records tables only)   how one row is proven to be the caller's (§3.7)
Login endpoint  /public-api/v1/auth           one per project; sessions are bound to the key they came through
Rule-call endpoint /public-api/v1/<slug>     no table: a group of operations
  ├─ operation  <METHOD> /<slug>[/<path>]    one rule (execution | predicate | validation) + its declared inputs
  ├─ callers                                 signed-in users (default) | a named service account
  └─ open to role groups (optional)          empty: everyone the callers admit | only members of these (+ admins)
```

A key opens WHOLE endpoints — every operation of a rule-call endpoint, every switched-on operation and action of a
table — never a single operation; an endpoint can have any number of keys. Two calling systems that must reach
different things get different keys bound to different endpoints.

Four properties decide most of what you will be asked about:

- **Resolved at call time, against the PUBLISHED branch.** An endpoint names its table by the node's
  `uniqueIdentifier` and nothing else. A table that keeps that identifier keeps answering wherever it moves; a
  table deleted, re-created (a copy is a new node), or present only on a draft branch answers
  `404 endpoint_not_found`. Editing a table on a draft changes nothing a caller sees until that branch is
  published.
- **Opt-in per action.** An action the table gains after the endpoint was saved stays OFF until somebody
  switches it on. Adding a button for people never widens what a key can do.
- **The screen's checks, as the caller.** Every operation passes, for the acting user, the gates the screen
  passes: the table's page (and every container between page and table) must be visible to them; the case must
  be in their worklist, the row in their fetch rule's answer (or admitted by the endpoint's item-access rule,
  §3.7); the action's predicate must say yes; the form
  routing picks the form, and it opens on what the action's before-start rule made of the item; the form's own page
  and its form group's landing page must be visible to them; then mandatory fields, conditional validations, the
  form's validators, warnings, and the action's before-complete rule — in the screen's order, which differs by
  action origin (§3.11).
- **The generated reference is the contract.** Each endpoint's reference in the API tab and
  `GET /public-api/v1/openapi.json` (OpenAPI 3.0.3) are generated from the live definition, the published table
  and its published forms. Hand those to the integrator; do not re-type field lists into a document that goes
  stale on the next form edit. `openapi.json` describes exactly what the presented KEY may call — the endpoints
  switched on and bound to it — so each integrator fetches it with their own key (§8). It describes each form as
  ANY caller of the endpoint sees it — fields only some role groups get are not in it — names no rule, and is
  written in the caller's language only where the project already stores that translation, English otherwise;
  every `x-` extension its schemas use is explained in its description. The API tab's reference is the author's
  view: the whole form, with the rules behind each check.

What an endpoint offers, per table kind:

| Operation | Request | Process table | Records (CRUD) table |
|---|---|---|---|
| List | `GET /<slug>/items?page=0&size=20&filter.<key>=<v>&include=actions` | the caller's worklist of that table, newest case first | the rows the table's fetch rule returns for the caller, in its order |
| Query | `POST /<slug>/items/query` `{"filters":{…},"page":0,"size":20,"include":["actions"]}` | the same list, filters as typed JSON | same |
| Get one | `GET /<slug>/items/<id>` | `<id>` = the process identifier | `<id>` = the row's id; needs item access (§3.7) |
| Item actions | `GET /<slug>/items/<id>/actions` | the current task's actions and the global actions, each only when its predicate admits the caller | edit actions whose predicate admits the caller for that row |
| Bulk discovery | `POST /<slug>/items/actions/lookup` `{"ids":[…]}` (≤ 100; strings or numbers) | per id: its actions, or `item_not_found` | same |
| Run an item action | `POST /<slug>/items/<id>/actions/<actionId>` `{"data":{…},"acknowledgeWarnings":false}` | completes the task / updates the case | runs the row action |
| Dry run | `…/actions/<actionId>/validate`, same body | every check incl. validation rules, against the item AS IT IS (a new one: empty); neither the before-start nor the before-complete rule runs; nothing written | same |
| Collection actions | `GET /<slug>/actions` | start actions | create actions |
| Run a collection action | `POST /<slug>/actions/<actionId>` (+ `/validate`) | starts a case → `201` | creates a row → `201` |
| Filters | `GET /<slug>/filters` | the page's filters for this caller | same |
| Sign-in | `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` | — | — |
| Description | `GET /openapi.json` | every endpoint switched on and bound to the presented key — nothing another key opens | |

A **rule-call endpoint** offers exactly the operations its author added, nothing else. Each operation's address is
`/<slug>` itself or up to three lower-case segments below it (`stats`, `orders/by-day`: letters and digits, words
joined by single hyphens, at most 100 characters) — no `{id}`-style path parameters: what varies goes in a query
parameter. The first segment is never `items`, `actions` or `filters` (the table operations' words), and no
segment is `validate` (the dry run's).

| Operation | Request | Answer |
|---|---|---|
| Run an operation | `<METHOD> /<slug>[/<path>]?<param>=<v>` — `GET`/`DELETE` take no body; `POST`/`PUT`/`PATCH` take the body the operation declares | `200 {"result": <the rule's answer>, "meta": {"requestId", "respondedAt", "durationMs", "method", "path"}}` |
| Dry run (form-body operations only) | `<METHOD> /<slug>[/<path>]/validate`, same body | every check of the form, NO rule: `200 {"valid": true, "warnings": […]}` or the `422` the checks find |

The same path may answer several methods; another method on it answers `405 method_not_allowed` with an `Allow`
header naming the ones it takes, a path the endpoint does not have `404 not_found`. `HEAD` runs no operation: it is
answered as a method the path does not take (`405` with the path's own `Allow`, or `404` where the endpoint has no
such path).

Item actions and Bulk discovery exist only while at least one item action is switched on for the endpoint, and
Collection actions only while a start or create action is — otherwise they answer `404 not_found`, and the
description leaves them out.

An item is `{"id", "fields": {<key>: raw}, "display": {<key>: formatted}, "meta": {…}, "actions": […]}` —
`meta` is `status`, `businessKey`, `workflowName`, `createdAt` for a case and empty for a row; `actions` only
with `include=actions`. An action is `{"id", "name", "kind", "direct", "hasForm"}`, `kind` one of `TASK`,
`GLOBAL`, `START`, `ROW`, `CREATE`.

---

## 3 · Authoring for the API — what you write differently

Everything below is something you put into the export. None of it is visible to `validate` as an API problem,
because none of it IS a problem for a person on a screen — which is exactly why it ships broken.

### 3.1 Field keys are BINDINGS, never labels

A caller sends `data.<key>` and reads `fields.<key>`, and the key is where the field is bound, spelled the way
a rule addresses it:

| where the form is opened / the column lives | key |
|---|---|
| a form opened from a CRUD table (CRUD mode), and a CRUD table column | the row's `fieldExpression` — dotted paths kept (`customer.id`) |
| a process form or column, GLOBAL scope | `fieldExpression` |
| CONTEXT scope | `<contextAlias>.<fieldExpression>` — the context's ALIAS, not its identifier |
| CRUD scope inside a process form | `<contextAlias>.<crudAlias>.<fieldExpression>` |
| a JSON-column field | the binding plus the path inside it (`meta.pricing.amount`) |
| the upper end of a Between pair | the pair's own mapping, by the same rule |

Consequences you design around:

- **A label (`name`) is free text.** Rename it whenever the business asks; no caller notices.
- **A binding is the contract.** Renaming a `fieldExpression`, a context alias or a CRUD alias renames the API
  field and breaks every caller that sends it. Settle them before the endpoints are created.
- **Bind a column and the form field that edits it the same way.** Then what a list returns under
  `fields.<key>` is exactly what an action accepts under `data.<key>`.
- **Two controls bound to the same place** get `<key>`, `<key>~2`, `<key>~3` in content order. Avoid it: a
  suffix is a key an integrator has to guess.
- **Platform attributes (`__…`) are never writable** through the API.

### 3.2 Preconditions are VALIDATION rules — a `throw` refuses without naming a field

A refusal an integrator can act on is `422 validation_failed` with one detail per problem, named by **field
key** — so their app can show it next to the right input. Only validation produces that: control validations
and the form's or the action's VALIDATION rules ([25](25-form-settings-validation-and-events.md)).
`validation.addFieldError("<control name>", …)` comes back attached to that control's key, and a
WARNING-severity check comes back as `422 warnings_require_acknowledgement` until the caller repeats the request
with `"acknowledgeWarnings": true`.

A before-start, before-complete or direct-action rule that says no by THROWING refuses the call too — on records
and process tables alike — with `422 validation_failed`, the rule's own words as the message and no field named.
It is a refusal only when the rule throws it on purpose, the way a rule says no:

```groovy
throw new RuntimeException('<words for the person acting>')
// also: IllegalStateException, IllegalArgumentException, UnsupportedOperationException, Exception
```

— one of those exact types, constructed in the rule's own code, with words. Anything else that escapes a rule is
an ERROR, not a refusal: a null dereference, a missing property or method, a failed cast, a failed database or
service call, an exception a library the rule called threw, an exception of any other type. ⛔ Those answer
`500 internal_error`: the caller learns nothing (the text names classes and data, so it stays in the server log),
cannot tell it from an outage, and will retry.

So: a problem with a FIELD → a VALIDATION rule (it runs before the before-complete rule, writes nothing and names
the field); a refusal of the whole action → `throw new RuntimeException('<words>')`; nothing else may escape a
rule.

### 3.3 Predicates must admit the API identity

Every predicate, every rule and every role-group check runs as the acting user (§4). Two consequences:

- **Identify the user by `service.security.user().email` and by role groups — never by `user().id`.** The id
  carries a different value depending on which path ran the rule, and through the API it is the e-mail.
  ([04](04-crud-table-plugin.md) already tells you to use the e-mail as the ownership key; the API makes it
  mandatory.)
- **A service account is never a member of the Author or Developer group.** A predicate that admits only those
  groups refuses every service-account call. Give the integration its own role group and admit it explicitly
  where it must act — on the table's page, on each form page and form-group landing page it submits through, in
  each action predicate, and in the process access of the cases it must see.

### 3.4 Every global action needs a predicate

A global action with a blank `predicateIdentifier` is never offered on a row — on the screen and through the API
alike, and executing it by id is refused. A start action with a blank predicate IS offered, to everyone who can
see the table. ([05](05-crud-tree-and-process-table.md) §"The THREE action origins".)

### 3.5 A direct start takes no data

A `direct:"on"` start action starts an EMPTY case ([27](27-event-driven-process-start.md) §2.0). Through the
API a direct action called with a non-empty `data` answers `422 action_takes_no_data`. If the integrator must
send anything — and they almost always must — the start action is `direct:"off"` with a start form whose
controls are that payload.

### 3.6 The page's filter form IS the API's filter list

A list operation accepts exactly the filters the table's **page** offers the caller: the filter form on the same
page as the table — not one in another tab pane — with each control's `filterKey`, verbatim, as the API's filter
key. A process table's keys usually carry the `filter_` prefix its `{token}`s use, so the integrator writes
`filter.filter_status=…`; that is the contract, not a typo to tidy later. Unknown keys and wrong types are refused
(`400 invalid_filter`), so a filter that is not on the page cannot be sent at all.

- **Process tables:** the key must be a `{token}` the `filterExpression` reads, and the field it compares must
  be in `indexSettings` ([05](05-crud-tree-and-process-table.md)). A filter the expression never reads is
  accepted and changes nothing — the generated reference says so, the integrator will not read it.
- **Records tables:** a filter key reaches the SQL only if the fetch rule passes it on and the CRUD methods
  declare it — in BOTH `findAll` and `count` ([04](04-crud-table-plugin.md)). Otherwise the filter is decorative
  on the API exactly as on the screen.
- **A Between control is two filters** — its from key and its to key — and dates are ISO 8601.
- **A rule-driven dropdown filter takes only what its choices rule offers the caller** — as on the screen, where
  the dropdown can submit nothing else. The rule runs as the caller, with the control's `rowsInPage`, on a
  document that carries only the caller's language; a value it does not return is `400 invalid_filter`, a
  choices rule that refuses the caller answers `400 invalid_filter` in its own words, and one that breaks is a
  `500`. `GET …/filters` marks every such filter `"checked": true` and lists the `options` it offers THIS caller
  now — the integrator picks from them. A filter dropdown WITH search is not checked (its choices are a query
  away): when the choices are a scope — "my branches" — make it a plain dropdown, or have the fetch rule check the
  value itself.
- **Text is taken as the filter form's input takes it** — trimmed; a blank value is no filter at all.
- A filter control that some callers cannot see is accepted only from the callers who can.

### 3.7 A records table needs item access, or it has no "Get one"

A process case is the caller's when it is in their worklist. A ROW has no such test: the CRUD's `get` loads any
id. So every operation on one row — Get one, its actions, a row action — answers `404 item_not_found` until the
endpoint says how a row is proven visible, one of:

- **Rows the list returns** — the table's fetch rule is run as the caller with an **id filter** set to the
  requested id, and that row must come back. Author for it: a filter field on the CRUD that selects one row by
  its id (`id = :id`, declared in `findAll` and `count`), passed on by the fetch rule. A fetch rule that ignores
  the key returns other rows, and the id is refused.
  ⛔ The lookup sends the id filter ALONE — none of the caller's list filters. Of the table's own filter
  defaults (`filterSettings[].defaultValue`) it keeps only those the caller cannot change — no control with that
  key on the page's filter form for them — so such a default narrows Get one exactly as it narrows the list. A
  filter the caller CAN set arrives absent, and the fetch rule and the CRUD method behind it must read an absent
  key as "no filter". One that supplies its own default for a missing key —
  `filter.status = attrs?.status ?: 'OPEN'`, or `COALESCE(:status, 'OPEN')` in the SQL — answers
  `404 item_not_found` on Get one and on the row actions of every row the caller reaches with another value:
  `filter.status=CLOSED` lists the row, and its Get one refuses it. If the fetch rule cannot work that way, prove
  rows with a predicate instead.
- **Rows a predicate admits** — a PREDICATE rule evaluated as the caller with the row in context. Use it when
  the fetch rule cannot filter by id; write it as carefully as the fetch rule's own row filter, because it IS the
  row filter for every by-id call.

The settings screen proposes *Rows the list returns* only when a filter key is literally `id` or `identifier`; for
any other key it says what the key must do — make sure yours does. A row the item access cannot prove is still
listed (the list is the fetch rule's), but with `include=actions` its `actions` is `null`, not `[]` — none of them
could run — and its Get one answers `404`. A list that shows `null` for rows the caller should reach means the item
access is wrong; the server log names the endpoint. A create's answer, too, shows the new row only where Get one
would find it: a rule that puts a record the caller may not see into the form's record never hands it over
(`item: null`).

### 3.8 Forms: what the API serves, and what it cannot

- **Served:** text, textarea, number, boolean, date/datetime, dropdown (enum or rule choices), autocomplete,
  tree picker, localized values (a string, or `{"<locale>": "<value>"}`), Between pairs.
- **Read-only through the API:** List (sub-grid), file upload, comments, Gantt. They appear in the schema
  marked `x-uiOnly`; a value sent for one is refused (`422 read_only`).
- **Not run through the API:** field events (rules a field fires when it changes on screen), in-form action
  buttons, and defaults computed by a rule. ⛔ Anything the save depends on — a computed total, a derived status,
  a looked-up name — belongs in the before-complete rule or a VALIDATION rule, never in a field event alone.
- **STATIC defaults fill every empty field, on every action** — create, edit, task and start alike. Once the
  caller's data is on the document, a field that is still empty — never filled, or sent as `null` — takes its
  control's static default, because the screen's control shows its default whenever its value is empty and the
  form submits what it shows. So a field with a static default is never saved empty: an integrator cannot clear
  it, and an edit that leaves it out fills it when it was empty. Read-only and hidden fields too — the screen's
  form submits every control it built, and an empty control submits its default. One exception: a field bound
  inside a JSON column takes its default only where the caller could write it and left it out; a `null` sent for
  it stays `null`. The schema marks every field that takes a default with `x-defaultWhenEmpty`; OpenAPI's
  `default` appears only on a create's writable fields.
- **Text is taken as the screen's inputs take it** — trimmed, and blank text is no value: it clears the field, or
  gives it its default.
- ⛔ **Keep validated controls out of tab panes, grids and nested forms on any form an endpoint will serve.** The
  screen validates them on submit and the API cannot reach them, so it refuses the whole form:
  `409 form_unavailable`.
- **Enum values** are checked against the values saved in the control's settings when the form was last saved —
  ship the `enumValues` snapshot ([02](02-form-controls-reference.md)).
- **A plain rule-driven dropdown accepts only what its choices rule offers.** On every write of that field the
  rule runs as the caller, on the document the form opens on — the item as the action's before-start rule left
  it, a new document for a start or a create — with the caller's data applied, and with the dropdown's own
  `rowsInPage` — the call that fills the dropdown on the screen — and the value sent must be one of the keys it
  returns; anything else is `422 invalid_type` (*"… must be one of the choices the field offers"*). Only a value
  the caller SENT is checked — a default the field takes never is — and the binding's problems and the choices'
  answer together, in one `422`. So a choices
  rule that returns nothing for the API identity refuses every value, one that throws its own words refuses the
  call in them (`422 validation_failed`), and one that breaks or that nobody answers is a `500`: write it to answer
  for a service account and a signed-in caller alike. A dropdown with search, an autocomplete
  and a tree picker are not checked this way (their choices are a query away) — when such a value matters, check
  it in a VALIDATION rule. The generated schema says which: every field whose choices come from a rule carries
  `x-choices.checked`, `true` or `false`.

### 3.9 Form routing decides at call time — design forks the caller can predict

A form group's `predicateFormMapping` is evaluated for the acting user and the item, exactly as on the screen
([06](06-form-groups-and-mapping.md)). The endpoint may PIN one form of the group, which is what its reference
documents; a call that routing sends to a different form is refused with `409 form_not_applicable`, naming both.
So a fork by role ("managers get the long form") is fine for an endpoint whose callers all take one branch, and
a trap for one whose callers take both. A group with no fallback form answers `409` when no predicate matches.

### 3.10 A records action that does not submit does nothing

A CRUD action whose form has `submitForm:false` — a "view" action — answers `200` with *"Nothing was submitted"*
and refuses data. It is almost never something an endpoint should offer; the settings screen warns about it.

### 3.11 Every write is a rule — in the screen's order

A records action without an `onBeforeCompleteRuleIdentifier` saves nothing — through the API exactly as on the
screen ([04](04-crud-table-plugin.md)). A process action with a form runs the way pressing its button and
submitting its form runs it — the order differs by origin, as on the screen:

| step | task action | global action | start action |
|---|---|---|---|
| 1 | the before-start rule runs on the case — nothing written yet | routing picks the form, on the case as it is | routing picks the form, for an empty document |
| 2 | routing picks the form, on what step 1 made | the before-start rule runs on the case | the before-start rule seeds the new case's document |
| 3 | the caller's data goes onto that document — hidden and read-only fields, dropdown choices and static defaults as the form opened there | same | same |
| 4 | every check: mandatory, conditional, the form's and the action's validation rules, warnings | mandatory fields only | mandatory fields only |
| 5 | the before-complete rule | the before-complete rule | the before-complete rule |
| 6 | the task completes; the case is written | every check, on what step 5 made; then the case is written | every check, on what step 5 made; then the case starts |

A refusal at any step leaves the case as it was — step 1's result included. A records form action: routing picks
the form on the row as it is (an empty context for a create), then its before-start rule, the caller's data on what
that rule made, every check, the before-complete rule — and a records rule writes when it runs, so a refusal after
the before-start rule does not undo what that rule wrote itself.

- **A dry run (`…/validate`) runs no rule.** It checks the caller's data against the item as it is — an empty
  document for a start or a create. Where a before-start rule seeds what a check reads, the dry run and the real
  call disagree; write the test scenario for the real call.
- **Two deliberate differences from the screen**, labelled per action in the generated reference: a DIRECT global
  action runs its before-start and before-complete rules through the API (the screen skips them), and an action's
  own validation rules run for global, start and direct actions too (the screen runs them for task actions only).
- **A records row action with a before-start rule is a "create child"** on the screen, and answers like a create:
  `result.itemId` and `item` are the NEW row — the one the rules left in the form's record — never the row it was
  started from (`itemId` is `null` when the rules left that one there). Have the before-complete rule put the
  created row, with its id, back into the form's record.
- **Global and start actions keep what the caller sent across the before-complete rule.** A rule that hands back a
  document of its own — the generated create rule publishes the row it wrote, in the database's flat shape —
  would otherwise lose the caller's values before the checks of step 6. As on the screen, every field the rule's
  document no longer has is put back first; a value the rule did hand back stays the rule's.
- **A global action's rules run as its form runs them** — on the document alone, with no process variables — and
  what they produce is MERGED over the case: what they leave out, the case keeps. A task action writes what its
  before-complete rule made of the submitted document, so whatever its before-start rule removed stays removed.
- **Several active instances of one task** (a multi-instance task, or parallel branches through one element) offer
  the same action once each; the API lists it once and runs it on the first instance. When the instances must be
  told apart, give each branch its own action id.

### 3.12 What a rule does for the BROWSER never reaches a caller

There is no browser: `service.redirectPage` is not delivered, `service.store.session` is an empty store, and
`service.report.pdf.download(…)` — which hands the file to the signed-in browser's download poller — reaches no
caller. Return what the caller needs as DATA — a field the action writes, which the answer's `item` (or a later
Get one) shows — and send documents by mail (`service.report.pdf.email.<alias>`, [15](15-pdf-and-mail.md)).

### 3.13 Messages in the caller's language

The caller's `Accept-Language` becomes the rule's `localeKey` — its languages tried in the caller's order of
preference, the first the project has winning — else the project's default. Validation messages and action names
are therefore localized the same way as on the screen — which means they must exist per locale
([20](20-localization.md)). The API's own checks (`unknown_field`, `invalid_type`, `read_only`, `invalid_filter`)
are worded in English, quoting labels in the caller's language. The OpenAPI document is English unless its request
names a language the project has; where its machine translation says something else than the English, the English
is right.

### 3.14 Keep the identifiers an endpoint stores stable

An endpoint stores the table node's `uniqueIdentifier`, action ids and form identifiers. Clone pages with the
toolkit (it regenerates only uuid-shaped ids, [01](01-content-model-and-pages.md)), never by hand; and put an
exposed table on a page or in a SHARED component — a table inside a non-shared virtual plugin or a layout gets
a new `uniqueIdentifier` on every export/import, and every endpoint pointing at it dangles.

### 3.15 Rules a caller calls — write each one as a contract

A rule-call operation runs one rule — execution, predicate or validation — as the acting user (§4), through the
same door a button's rule takes. Rules are not content of the published branch: the operation runs the rule as it
is NOW, so an edit to it reaches callers within seconds — test rule changes before saving them, as for any button
of a live project. (A form-body operation's FORM is read from the published branch, as every endpoint's forms
are.) Nobody sees a screen in between, so the rule IS the contract: what it reads, what it answers, how it says
no.

- **Inputs.** Query parameters the operation DECLARES — name (a letter, then letters, digits or `_`; never
  `processIdentifier`, `taskId` or `contextData`, which are the platform's), type (`string`, `integer`, `number`,
  `boolean`, `date`), required or not; any other parameter is refused (`400 bad_request`). They reach the rule as
  `attrs.<name>`, a JsonNode like every attr (`attrs.<name>?.asText()`, `.asLong()`, `.asBoolean()`,
  `.decimalValue()`; a `date` is ISO text `yyyy-MM-dd` → `LocalDate.parse(attrs.<name>.asText())`; a `number`
  arrives as a double, so one with more than 15 significant digits is refused rather than changed); one the caller
  left out — or sent blank — is ABSENT, so read optional ones null-safely. Then the body, one of three:
  - **none** — the rule runs on a document holding only the caller's language and the parameters;
  - **context data** — `{"contextData": {…}}`: the document the rule runs on, in exactly the shape a form's
    settings copy it (`localeKey`, `contextDataMap` → `<context identifier>` → `crudDataMap` → `<crud alias>` →
    `value`). Read it in the rule as the form's own rules read that form. The attributes the platform sets are
    refused in it — a name starting with `_` (`_crudEntityId`, `__actionId`…), `processIdentifier`, `taskId` — so a
    caller can never point the rule at another case or row: a rule that works on "the current case or row" gets
    that from a parameter it checks itself, never from the document. The operation's example comes from a form you
    name, or is pasted by the author — keep the form it names stable;
  - **a form's fields** — `{"data": {…}, "acknowledgeWarnings": false}`, bound through that form like a create:
    every check the screen makes (mandatory fields, conditional validations, the form's validators, warnings)
    runs BEFORE the rule, and the rule gets the document the form built. The acting user must be admitted on that
    form's page and its Form plugin, as on the screen (`403` otherwise). Only these operations have a dry run. A
    query parameter may not share a name with a field of the form (the call answers `409 form_unavailable`):
    it would reach the rule after the checks.
  A parameter wins over a body attr of the same name.
- **The answer.** An execution rule's return value is `result` — return plain data: maps, lists, strings,
  numbers, booleans (turn a GString into text with `.toString()`; it is not a string to the serializer), never a
  page redirect or a download, which reach nobody (§3.12). A predicate answers `true` / `false` — with an explicit
  `return` ([08](08-groovy-rules-and-context.md) §Templates and return semantics: a bare last expression is
  discarded); a predicate that answers anything else, an empty one included, is `500 internal_error`. A
  validation rule answers through its messages: an error refuses the call (`422 validation_failed`, the messages
  as details); only warnings → `200 {"result": {"valid": true, "warnings": […]}, "meta": {…}}` — warnings never
  refuse it.
- **Saying no.** `throw new RuntimeException("<words for the caller>")` answers `422 validation_failed` with those
  words, as in §3.2; anything else a rule throws is `500 internal_error`.
- **Methods mean something to callers.** `GET` for a question that changes nothing — clients, proxies and retries
  repeat GETs freely; `POST` (or `PUT`/`PATCH`/`DELETE` by meaning) for anything that writes. No call carries an
  idempotency key (§11): a writing rule guards itself in the data. A call whose answer was lost after the rule may
  have run (a timeout) answers `500`, never a `503` with `Retry-After` — tell integrators to check before retrying
  a write.
- **There is no page in front of it** — unless its body is a form, whose page and Form plugin gate it as on the
  screen. A table endpoint inherits the table page's access; any other rule call has only its callers, the role
  groups it is opened to (and the project's administrators), and the rule's own checks. A rule that must answer
  only for certain users, or only about the caller's own records, checks that itself.
- **The operation stores the rule's IDENTIFIER** (§3.14): deleting the rule, or re-creating it under a new
  identifier, makes that operation answer `404 endpoint_not_found`, and the endpoint's own page shows it *Broken*
  (the list of endpoints keeps showing its state from keys and switches, without asking every rule). The *Unused
  rules* scan counts a rule an endpoint calls as used — on a live project; nothing offline knows the endpoints
  (§6), so `validate` warns about a VALIDATION rule no form lists even when a rule call will run it: expected for
  such a rule — keep it.
- **Describe `result`.** The reference shows `result` as free JSON — the operation's description is where its
  shape goes; write it in the handover (§8) so the recipient can paste it.

---

## 4 · Who a call acts as — a signed-in person, or a service account

An API key identifies the APPLICATION. It is never a user: nothing a key does acts as "the key". So every
endpoint answers one question — who is acting — in one of two ways, and the handover must say which per
endpoint.

**Signed-in users (the default).** The calling app signs a project user in through the **Login endpoint**:

```
POST /public-api/v1/auth/login     {"username": "<user email>", "password": "<password>"}
→ 200 {"accessToken": "<access-token>", "tokenType": "Bearer", "expiresIn": 900,
       "refreshToken": "<refresh-token>", "refreshExpiresIn": 2592000,
       "user": {"email": "…", "firstName": "…", "lastName": "…"}}
```

- The password is the user's own project password. A project that signs in through **single sign-on** cannot
  use the Login endpoint (`403 sso_login_unsupported`): there is no password to send.
- The access token is the platform's own, short-lived (minutes); the refresh token is single-use and is replaced
  on every refresh — presenting a spent one ends the whole session, as a stolen token would. Their lifetimes
  (refresh-token validity, session maximum) are set on the Login endpoint.
- A session is bound to the key it was opened through and is refused with any other key. A user holds at most 10
  live sessions through one key; signing in again beyond that ends the oldest one.
- A wrong password, an unknown user, a user who is not a member of the project and a disabled account all answer
  the same `401 invalid_credentials`. Repeated failures lock sign-in for a while — for that account through that
  key, for that account through any key once failures pile up across keys, and from that address:
  `429 too_many_attempts` with `Retry-After`. One integrator's typos therefore never lock the account for
  another integrator's key.
- The user must be a project member with the role groups your predicates and pages expect — like any person.

**Service account (key only).** Per endpoint, the author may name ONE project member the calls act as when no
one is signed in — for machine-to-machine integrations with no person behind them. It must be a member of the
project, and it must NOT be in the Author or Developer group — nor in any role group of the administrator or
author type, or one that carries the administrator or author role. It is checked when the endpoint is saved and
again on calls (an answer is reused for at most a minute); a call it cannot act for is refused, never run as
somebody else. When a caller of such an endpoint DOES present a session, the signed-in person acts.

What that means for you, offline:

- Author a **role group for the integration** (e.g. `API Integration`) with exactly the access it needs, and
  write the handover line that asks the recipient to create the service user and put it in that group — users
  are created live.
- **A rule-call endpoint opened to role groups judges its service account like any caller.** If the account is
  in none of those groups, every call without a session answers `403 forbidden` — only signed-in members of the
  groups get through. Open the endpoint to the integration's own group (or to no group), and say so in the
  handover. The endpoint's page warns about such an account.
- **Process visibility is per user.** A caller sees the cases their e-mail, roles or role groups have access to.
  A case started through the API is owned by the acting user — exactly like a start-form case — so it is in that
  user's worklist; a service account that must ALSO see cases others started needs process access through its
  role group ([27](27-event-driven-process-start.md) §6).

---

## 5 · The wire contract, in brief

This is enough to plan and to write test scenarios. The authority is the generated reference (§2).

- **Every response** carries `X-Request-Id` — chosen by the server; trace headers a client sends (`b3`,
  `X-B3-*`, `traceparent`) are ignored — and `Cache-Control: no-store`. Every error is JSON:
  `{"error": {"code", "message", "requestId", "details": [{"field","code","message"}], "warnings": […]}}` —
  integrators branch on `code`; `message` is written for people and may change.
- **Bodies are JSON** — `Content-Type: application/json`; a form-encoded or multipart body is refused, and so is
  a body over 1 MiB, and a number in it longer than 1000 characters (`400 bad_request`). **Unknown query
  parameters and unknown body members are refused (`400`)** rather than ignored — on the sign-in operations too;
  sign-out and who-am-I take no body at all — so a misspelt `filter.stauts` cannot quietly return everything. A
  malformed `%`-escape in the query string is refused too (`400 bad_request`), never dropped.
- **Ids go in the path,** so an id containing `/`, `\` or a NUL character cannot be addressed (`400 bad_request`);
  give records ids without them.
- **Data is a patch.** On an existing item, a key left out keeps its value and an explicit `null` clears it —
  except that a field with a static default is never left empty: on every action, a field still empty once the
  data is bound takes its default (§3.8). The schema says so: `x-defaultWhenEmpty` on every field that takes one,
  OpenAPI's `default` on a create's writable fields. Unknown keys (`422 unknown_field`), wrong types
  (`422 invalid_type`) and values for read-only fields (`422 read_only`) are refused. A decimal may be sent as a
  number or as its exact text (`"12.50"`). A create whose form has a mandatory field requires `data`.
- **Dry run** (`…/validate`) runs every check — mandatory fields, conditional validations, validation rules,
  warnings — but no rule, against the item as it is (§3.11); it writes nothing and answers
  `200 {"valid": true, "warnings": […]}` or the `422` its checks find.
- **A rule that says no** (§3.2) answers `422 validation_failed` with its words; a rule that breaks answers
  `500 internal_error`.
- **A rule call answers `{"result": …, "meta": {"requestId", "respondedAt", "durationMs", "method", "path"}}`**
  (`respondedAt` in UTC, milliseconds). Its query parameters are checked before anything runs: an undeclared one,
  one given twice, a value of the wrong type or a missing required one → `400 bad_request`, each named in
  `details` (`unknown_parameter`, `invalid_value`, `invalid_type`, `required`; at most twenty named, the rest
  counted). A body sent to an operation that takes none is refused (an empty one is no body). A role group the
  endpoint is not open to → `403 forbidden`.
- **An executed action answers `{"result": {"itemId", "taskCompleted", "message"}, "item": <the item now> |
  null}`** — `taskCompleted` on process actions only; `item` is `null` when the caller can no longer see the
  item AND whenever the endpoint's *Get one* is off. A start or create answers `201`.
- **`include=actions`** gives every listed item its `actions` — `null` for a records row its item access cannot
  prove (§3.7).
- **Paging:** `page` from 0; `size` defaults to the table's own (15 otherwise), at most 200 — 50 with
  `include=actions` — and a larger size is served at the cap, not refused. **No sorting**: newest case first;
  for a records table, the fetch rule's own order.
- **Limits:** per key, a request rate and a ceiling on calls in flight at once; per project, a ceiling on calls in
  flight across all its keys (each `429 rate_limited`); per server, a ceiling on concurrent API calls
  (`503 server_busy`). Every `429` and `503` carries `Retry-After`. An integration that fires many calls in
  parallel gets `429` beyond a handful in flight — queue them.
- **Sessions:** `login` and `refresh` ignore any `Authorization` header (an expired token attached out of habit
  cannot block the refresh that replaces it); `logout` needs a LIVE access token — refresh first, then sign out.
  A session ends at its next refresh once the user's password changes or the user is signed out in the identity
  provider; a session ended on one server is refused by every other within seconds.
- **Error codes,** by status: `400` `bad_request` `invalid_json` `invalid_filter` `too_many_ids` · `401`
  `api_key_required` `invalid_api_key` `login_required` `invalid_session` `invalid_credentials` · `403`
  `forbidden` `action_not_available` `sso_login_unsupported` · `404` `not_found` `endpoint_not_found`
  `item_not_found` `action_not_found` `login_not_enabled` · `405` `method_not_allowed` (rule calls; `Allow` names
  the methods) · `409` `form_not_applicable` `form_unavailable` ·
  `422` `validation_failed` `unknown_field` `invalid_type` `read_only` `warnings_require_acknowledgement`
  `action_takes_no_data` · `429` `rate_limited` `too_many_attempts` · `500` `internal_error` · `503`
  `api_unavailable` `server_busy`.

Two answers worth recognising, because they look like bugs and are not:

- **`404 endpoint_not_found` for an endpoint that exists** — it is switched off, its table is not on the
  published branch, or the presented key is not bound to it. A key sees only its own endpoints.
- **`409 action_not_available` on a start action** — the workflow behind it is not deployed.
- **`404 endpoint_not_found` on a rule call that worked yesterday** — the rule its operation names was deleted or
  re-created under another identifier (the endpoint's page shows *Broken*).

---

## 6 · ⛔ `apiExposures` in `rep-objects.json` — leave the key OUT

An export of a live REPORT project writes a 15th key into `rep-objects.json`:

| what the export wrote | what an import does with it |
|---|---|
| **no key**, or `"apiExposures": null` (every builder archive, every archive older than the API, a non-REPORT project, an export that could not read the endpoints) | **nothing** — the target's endpoints and their key bindings stay exactly as they are |
| `"apiExposures": [ … ]` | makes the target's endpoints **exactly this list**: matched by `identifier`, kept ones keep their key bindings, endpoints the list does not have are **deleted with their bindings** |
| `"apiExposures": []` — what a project with NO endpoints exports | ⛔ **deletes every endpoint of the target and every key binding** |

⛔ **Never write the key in a build you author.** Absent — or `null`, which an import treats the same way — is
the only value that cannot hurt the project you import into.

⛔ **Check your base before you pack.** A base exported from a live project carries the key — and `[]` when
that project had no endpoints. Importing your build would then reset the target's endpoints to the base's list
(or delete them all), and the bindings it deletes come back from no archive: somebody has to rebind every key
by hand, while every integration calling those endpoints gets `404`. `validate` refuses both — an ERROR naming
what the import would do — so a build carrying the key cannot pass the offline gate. Ask, and remove it:

```bash
python3 tools/mrjun.py api-exposures show --project ./work   # absent / null = safe; [] or a list = destructive
python3 tools/mrjun.py api-exposures drop --project ./work   # removes the key; then validate again
```

Keep a list only when the purpose of the import is to restore exactly that list — then
`validate --keep-api-exposures` reports it as a warning instead of an error. If you keep the list on purpose:
do not edit entries, never invent an `identifier`, never change a `tableUid`.
The list is applied as ONE unit — one invalid entry (a malformed or reserved slug, two endpoints with one slug,
two Login endpoints, an entry without its table) refuses the whole list, changes nothing, and the import's
failure report names each refused endpoint with its reason. For recognition only, an entry looks like this:

```json
{ "id": null, "identifier": "<uuid>", "realmName": "<realm>", "clientName": "<client>",
  "kind": "PROCESS_TABLE", "name": "Open requests", "slug": "open-requests", "enabled": true,
  "tableUid": "<the process.table node's uniqueIdentifier>", "workflowIdentifier": "<workflow identifier>",
  "listEnabled": true, "readEnabled": true,
  "actions": [ { "actionId": "<start action id>", "origin": "START", "enabled": true,
                 "formIdentifier": null, "label": "New request" } ],
  "callerMode": "USER", "serviceAccountEmail": null, "itemScope": null, "login": null }
```

and a rule-call endpoint, no table:

```json
{ "id": null, "identifier": "<uuid>", "realmName": "<realm>", "clientName": "<client>",
  "kind": "RULE", "name": "<name>", "slug": "<slug>", "enabled": true, "tableUid": null,
  "operations": [ { "operationId": "<id>", "enabled": true, "method": "GET", "path": "<path>",
                    "ruleIdentifier": "<rule identifier>", "ruleName": "<rule name>", "input": "NONE",
                    "parameters": [ { "name": "<param>", "type": "DATE", "required": true } ] } ],
  "roleGroups": [], "callerMode": "USER", "serviceAccountEmail": null }
```

---

## 7 · Lifecycle — what travels, what survives

| event | endpoints | keys and key bindings | sessions |
|---|---|---|---|
| **export** | in `apiExposures` (§6), `id` nulled, `identifier` kept | never | never |
| **import of an archive without the list** (every build you author) | untouched | untouched | untouched |
| **re-import of a live export into the same project**, a **version-tag revert** | reconciled to the archive's list (§6); the import summary names every endpoint it deleted, and those that had keys bound | kept on endpoints that survive; gone with the ones deleted | unaffected unless the Login endpoint is deleted (below) |
| **a new environment** (created from an export) | arrive with the export | none — each arrives with **no key** and answers `404` until one is bound | none |
| **environment publish** | carried, as ONE list applied in one step; a refused list names the endpoint; removing an endpoint that has keys in the target is left unticked by default | never — new endpoints arrive with no key, existing ones keep theirs, and the publish review warns about both, about calls that would start acting as somebody else, and about calls that would stop answering — an endpoint with keys bound in the target whose path changes, that is switched off, or that loses an operation or an action | never |
| **a key is revoked** | keep the binding — the key shows *Revoked*, and an endpoint whose every bound key is revoked or expired shows *No live key*; calls with it answer `401 invalid_api_key` | — | every session opened through it ends |
| **the Login endpoint is switched off, deleted, or its key unbound** | — | — | sign-in and refresh refused; access tokens already issued expire within minutes. That PAUSES sessions: switched back on in time, they refresh again. Revoking the KEY is what ends them |
| **the project is deleted** | deleted | deleted | deleted |
| **a new project on a realm/client pair a deleted project used** | swept on creation | swept | swept |

So the recipient creates keys **once per environment**, and nothing short of deleting the project — or
importing an archive that carries a different endpoint list — undoes their bindings.

---

## 8 · The handover — what you deliver with the export

Two things, both written by you, both in the delivery next to `project.mrjun`.

**1. The endpoint table** — one row per endpoint the PRD needs, in the recipient's terms:

| endpoint (suggested slug) | table (page title · path) | operations | actions (form per action) | callers | item access (records) |
|---|---|---|---|---|---|
| `open-requests` | Requests · `/requests` | list, get one | `new-request` (start form *Request*), `withdraw` (direct) | signed-in users | — |
| `suppliers` | Suppliers · `/master/suppliers` | list, get one | `create` (form *Supplier*) | service account in group `API Integration` | rows the list returns, id filter `id` |
| `<rule-call slug>` | — (rule call) | `GET /<path>?<param>=…` → rule *<rule name>* (answers `<shape of result>`); `POST /<path>` context data → predicate *<rule name>* | — | signed-in users, open to role group `<group>` | — |
| Login | — | — | — | for the endpoints above whose callers sign in; refresh token 30 days, session 90 days | — |

**2. The handover note** — copy this shape:

> This project offers a REST API for `<the calling system>`. API keys never travel with the project file, so
> before anything can call it, open **Settings → Developer → API** (you need to be in the Author or Developer
> role group) and:
> 1. **Create a key** for each calling system. It is shown ONCE — copy it straight into that system's secret
>    store.
> 2. **Add the endpoints** in the table above (if this project was imported from an export of a live project,
>    check the ones that arrived instead — they arrive with no key). Turn on exactly the operations and actions
>    listed. For a **Rule call** endpoint, add each operation: its method and path, the rule, its body and its
>    query parameters, and a description of what it answers.
> 3. **Bind the key** to each of those endpoints, and to the **Login** endpoint if the callers sign in — on each
>    endpoint (its *Keys*), or all at once on the key's own page (*Endpoints this key opens*).
> 4. For a service-account endpoint: create the user `<integration user>` and add it to the role group
>    `<API Integration>` first — it must not be in Author or Developer. A **Rule call** endpoint opened to role
>    groups must list that group among them, or its calls without a session are refused.
> 5. Give each integrator the **base URL** shown at the top of the API tab and **their** key. Their contract is
>    `GET <base URL>/openapi.json` sent with that key — the call shown when the key was created — which
>    describes exactly the endpoints their key opens once step 3 is done. To hand over a file instead, use
>    **Download OpenAPI for this key** on the key's page: the switched-on endpoints that key opens. The toolbar's
>    *Download OpenAPI (all endpoints)* describes ALL of them, switched-off ones and other integrators' included.
>
> Until a key is bound, every call to an endpoint answers 404. Each endpoint shows its state in the list —
> *Live*, *No key*, *No live key*, *Broken*, *Disabled* — and *Broken* opens the reason.

---

## 9 · Test scenarios — one call per operation

Nothing offline can execute an API call, so each endpoint gets scenarios in `test-scenarios.md`
([26](26-orchestration-and-testing.md) §5), run against the imported project once the recipient has bound a key
([30](30-live-test-bugfix-and-autotest.md)). Write them as calls, with expected codes. In the autotest project the key
is `API_KEY` in `test/.env`, written there by the project's owner ([30](30-live-test-bugfix-and-autotest.md) §6) —
never a literal in a test, never asked for in a chat:

```bash
BASE='https://<platform-host>/public-api/v1'
API_KEY='<the key, as shown once when it was created>'
H_KEY="X-Api-Key: $API_KEY"
H_JSON='Content-Type: application/json'

# sign in (callers = signed-in users)                                    → 200, tokens
curl -sS -X POST "$BASE/auth/login" -H "$H_KEY" -H "$H_JSON" \
     -d '{"username":"<user email>","password":"<password>"}'
ACCESS_TOKEN='<accessToken from the answer above>'
H_USER="Authorization: Bearer $ACCESS_TOKEN"

curl -sS "$BASE/auth/me"                                   -H "$H_KEY" -H "$H_USER"   # → 200, the user
curl -sS "$BASE/<slug>/filters"                            -H "$H_KEY" -H "$H_USER"   # → 200, the filter keys
curl -sS "$BASE/<slug>/items?size=5"                       -H "$H_KEY" -H "$H_USER"   # → 200, a page
curl -sS "$BASE/<slug>/items?filter.<key>=<a value that matches one item>"  -H "$H_KEY" -H "$H_USER"
curl -sS "$BASE/<slug>/items?filter.<key>=<a value that matches none>"      -H "$H_KEY" -H "$H_USER"   # → items: []
curl -sS "$BASE/<slug>/items/<id>"                         -H "$H_KEY" -H "$H_USER"   # → 200, the item
curl -sS "$BASE/<slug>/items/<id>/actions"                 -H "$H_KEY" -H "$H_USER"   # → 200, the actions offered now
curl -sS -X POST "$BASE/<slug>/items/actions/lookup"       -H "$H_KEY" -H "$H_USER" -H "$H_JSON" \
     -d '{"ids":["<id>","<an id the user cannot see>"]}'                              # → second: item_not_found
curl -sS -X POST "$BASE/<slug>/items/<id>/actions/<actionId>/validate" -H "$H_KEY" -H "$H_USER" -H "$H_JSON" \
     -d '{"data":{"<key>":"<value>"}}'                                                # → 200 valid / 422, nothing written
curl -sS -X POST "$BASE/<slug>/items/<id>/actions/<actionId>"          -H "$H_KEY" -H "$H_USER" -H "$H_JSON" \
     -d '{"data":{"<key>":"<value>"}}'                                                # → 200, result + item
curl -sS "$BASE/<slug>/actions"                            -H "$H_KEY" -H "$H_USER"   # → 200, start/create actions
curl -sS -X POST "$BASE/<slug>/actions/<actionId>"         -H "$H_KEY" -H "$H_USER" -H "$H_JSON" \
     -d '{"data":{"<key>":"<value>"}}'                                                # → 201, the new item's id
curl -sS "$BASE/<rule-call slug>/<path>?<param>=<v>"       -H "$H_KEY" -H "$H_USER"   # → 200, {"result": …, "meta": {…}}
curl -sS -X POST "$BASE/<rule-call slug>/<path>"           -H "$H_KEY" -H "$H_USER" -H "$H_JSON" \
     -d '{"contextData":{…}}'                                                         # → 200, the rule's answer
curl -sS -X POST "$BASE/<rule-call slug>/<path>/validate"  -H "$H_KEY" -H "$H_USER" -H "$H_JSON" \
     -d '{"data":{"<key>":"<value>"}}'                                                # form-body operations: → 200 valid / 422, no rule run
curl -sS "$BASE/openapi.json"                              -H "$H_KEY"                # → 200, OpenAPI 3.0.3 of THIS key's endpoints
curl -sS -X POST "$BASE/auth/refresh" -H "$H_KEY" -H "$H_JSON" -d '{"refreshToken":"<refresh-token>"}'   # → 200
curl -sS -X POST "$BASE/auth/logout"  -H "$H_KEY" -H "$H_USER"                       # → 204
```

And the refusals, which prove the guards are on — each one is a scenario of its own:

| call | expected |
|---|---|
| any call without `X-Api-Key` | `401 api_key_required` |
| a slug the key is not bound to, or a misspelt one | `404 endpoint_not_found` |
| a signed-in-users endpoint without `Authorization` | `401 login_required` |
| an item id the user may not see | `404 item_not_found` — the same answer as a nonexistent id |
| `filter.<unknown>=x` | `400 invalid_filter` |
| `data` with a key the form does not have | `422 unknown_field` |
| a value a plain rule-driven dropdown's choices rule does not offer | `422 invalid_type`, the detail naming that field's key |
| a mandatory field left empty | `422 validation_failed`, the detail naming that field's key |
| `filter.<key>=<a value a rule-driven dropdown filter does not offer>` | `400 invalid_filter`, the detail naming that filter |
| an action whose before-complete rule throws its own words for this data | `422 validation_failed`, the rule's words |
| `data` sent to a direct action | `422 action_takes_no_data` |
| a user without the action's predicate | `403 action_not_available` (on an item) / the action absent from the list |
| a rule-call path with a method it does not take | `405 method_not_allowed`, `Allow` naming the ones it takes |
| a rule-call parameter the operation does not declare / a required one left out / `<param>=<wrong type>` | `400 bad_request`, the detail naming the parameter |
| a rule call by a user outside the role groups the endpoint is open to | `403 forbidden` |
| a rule call whose rule throws its own words | `422 validation_failed`, the rule's words |

⛔ **The edge in front of the platform may refuse some HTTP clients before the API sees them.** Cloudflare's
Browser Integrity Check answers a handful of library default user agents — Python's standard-library
`Python-urllib/3.x` is the one seen in practice — with `403` and a body of `error code: 1010`. You can tell it
apart at once: an answer from the API ALWAYS carries `X-Request-Id` and a JSON body; the edge's carries neither.
Send a normal, honest `User-Agent` that names the client (`<company>-<integration>/1.0`), or use a mainstream
HTTP client; never imitate a browser. If a legitimate client is still challenged, the operator exempts
`/public-api/` from that check at the edge.

---

## 10 · Support mode — changing a live project's API

- **There is no MCP channel for it.** No MCP tool reads or writes endpoints, keys or bindings. A person changes
  them in Settings → Developer → API; a re-import changes endpoints only when its archive carries
  `apiExposures`, and then it REPLACES the list (§6). Keys and bindings have no channel but the screen.
- **An MCP token is not an API key, and neither opens the other's door.** `/public-api/` refuses an MCP token
  and `/mcp` refuses an API key.
- **Your MCP writes change what callers get — at once.** MCP writes land on the published branch
  ([28](28-support-mode-over-mcp.md) §2.4), and endpoints read the published branch. Adding a button is safe
  (actions are opt-in, §2); **renaming a binding, an action id or a filter key, deleting an action, or moving a
  validated control into a tab pane breaks every caller using it, silently** — the screen still works. Treat
  those as API changes: say so in the hand-over, with the endpoints they touch.
- **When a caller reports a failure, ask for the `X-Request-Id`.** It names the request in the platform's
  logs, where each API call writes one line with its route, status, time, key fingerprint and user.
- **Rules an endpoint calls are in use.** The *Unused rules* scan counts them; deleting one — or changing its
  identifier — breaks the endpoint (*Broken*, `404 endpoint_not_found`). Changing what such a rule reads or
  returns is an API change: say so in the hand-over, with the endpoints that call it.
- **Read the endpoint's state before suspecting the build:** *No key* (bind one), *No live key* (every bound key
  revoked or expired), *Disabled*, or *Broken* — whose notice names the cause (table gone from the published
  branch, pinned form gone, a form the API cannot serve, item access missing or its rule deleted, a workflow that
  is not deployed, a service account that cannot act, sign-in required but no Login endpoint, a rule a rule call
  names that is gone, a query parameter named like a field of its form, none of the role groups it is opened to
  existing — a few of them gone is only a warning, and so is a service account in none of the role groups a rule
  call is opened to: every call of it without a session answers `403`). The list's pill decides from keys and
  switches alone; open the endpoint for what its rules and forms say.

---

## 11 · Known gaps — say these out loud

- **No sorting** in v1, and no offset beyond `page`/`size`.
- **No bulk execution** — discovery only, at most 100 ids per call.
- **No files** — upload and download are not part of the API; List, comments and Gantt fields are read-only.
- **No idempotency key.** A start or create retried after a timeout may run twice. Guard it in the data, as a
  sweep is guarded ([27](27-event-driven-process-start.md) §5): a business key the rule checks before it
  writes.
- **No outbound events.** The API answers calls; it never calls anyone. Use a rule with outbound REST for that.
- **CRUD trees are not exposable.**
- **A rule call has no page** (unless its body is a form): who may call it is its callers, the role groups it is
  open to and the rule's own checks — nothing on a screen. Its `result` is described as free JSON; its shape is what
  the operation's description says.
- **Field events, in-form buttons and rule-computed defaults do not run** (§3.8); **tabbed / grid / nested-form
  validated controls make a form unservable** (`409 form_unavailable`).
- **As on the screen:** a mandatory or conditional-validation predicate that fails to run counts as not
  applying. (A validation RULE that cannot run — or that answers something that is not a validation result: an
  execution rule or a predicate put in a form's validators — is an error naming it, never a pass.)
- **A dry run runs no rule** (§3.11), so it cannot see what a before-start rule would seed.
- **Parallel instances of one task** share an action, which runs on the first instance (§3.11).
- **Enumeration labels may be a snapshot** — a process-table column's display text may come from the
  enumeration copy saved with the table, and a form's allowed values from the copy saved with the form.
- **Single sign-on projects** cannot use the Login endpoint; their endpoints need a service account.
- **The API's own check messages are English** (§3.13); labels, rule words and the form's own checks follow
  `Accept-Language`.
- **Changes reach every server within about half a minute**: a revoked key or an edited endpoint stops working
  at once on the server that made the change and within that window on the others.

---

## 12 · Done when

- [ ] every inbound PRD sentence is a row of the handover table (§8) — and outbound ones went to [16](16-groovy-service-api.md) §2.2
- [ ] every exposed table is on a page or a shared component, never inside a non-shared virtual plugin or a layout
- [ ] every exposed action exists on its table, with a predicate that admits its callers (every global action has one)
- [ ] no start action that must receive data is `direct:"on"`
- [ ] every form an endpoint serves has its validated controls outside tab panes, grids and nested forms, and nothing it saves depends on a field event
- [ ] field bindings are final — `fieldExpression`, context aliases, CRUD aliases — and columns bind like the form fields that edit them
- [ ] every filter an integrator needs is a control of the table page's filter form, indexed (process) or declared in `findAll` AND `count` (records)
- [ ] every records table with Get one or row actions has an id filter its fetch rule honours, or a predicate for item access
- [ ] a role group exists for each service-account integration, admitted on the pages, forms, predicates and process access it needs — and among the role groups of every rule-call endpoint it calls that is opened to any
- [ ] `rep-objects.json` has **no** `apiExposures` key — `mrjun.py api-exposures show` prints `absent`, and `validate` passes WITHOUT `--keep-api-exposures` — unless the import is meant to restore exactly that list
- [ ] every rule a rule-call operation runs reads only declared parameters or the body its operation takes, answers plain data (or true/false, or validation messages), refuses in words a caller can act on, writes nothing on a `GET`, and checks for itself whatever a page would have gated
- [ ] the handover note and the endpoint table are in the delivery, and `test-scenarios.md` has one call per operation plus the refusals

---

**See also:** [05](05-crud-tree-and-process-table.md) (process tables, their three action buckets, index and
filter expression) · [04](04-crud-table-plugin.md) (records tables, the fetch rule, actions) ·
[06](06-form-groups-and-mapping.md) (routing) · [25](25-form-settings-validation-and-events.md) (validation) ·
[27](27-event-driven-process-start.md) §2.0 (who opens the case) · [16](16-groovy-service-api.md) §2.2 (the other
direction) · [28](28-support-mode-over-mcp.md) §5 (what has a live channel) ·
[00](00-export-format-and-import.md) §6 (`apiExposures` in `rep-objects.json`)
