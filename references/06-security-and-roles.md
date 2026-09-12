# Security and roles — the access model, as four deliveries actually built it

Measured against four delivered exports before they were archived: **A** (large suite — 433 pages / 163 CRUDs /
22 studio consoles), **B** (mid — 129 pages / 38 CRUDs), **C** (mid, analytics-dense — 128 pages / 31 CRUDs / 87
charts), **D** (small — 67 pages / 12 CRUDs). Every count below is counted, not remembered. The JSON keys,
Groovy idioms, SQL shapes and counts are verbatim; entities and personas are neutral placeholders throughout —
entities `document` / `documentLine` / `decision` / `task`, scope column `unitId`, personas `Operator`,
`Reviewer`, `Supervisor`, `Approver`, `Controller`, `Auditor`, `Liaison`, `Director`, `Partner Portal`,
alongside the platform's own `Author` / `Developer` / `System Administrator`.

Corrects [[01-content-model-and-pages.md](../01-content-model-and-pages.md)](../01-content-model-and-pages.md) §"Access — `roleAccess`",
[[16-groovy-service-api.md](../16-groovy-service-api.md)](../16-groovy-service-api.md) §2.3 and
[[12-queries-sources-schedulers-and-rest.md](../12-queries-sources-schedulers-and-rest.md)](../12-queries-sources-schedulers-and-rest.md) §4.2/§4.5/§3.2c —
see §11. Confirms [[04-crud-table-plugin.md](../04-crud-table-plugin.md)](../04-crud-table-plugin.md) §"Who sees which rows".

---

## 0. Four layers, not three, and they are not equally strong

Decide which layer carries each requirement **before** you author anything, because three of the four can be
walked around and only one of them decides what data leaves the server.

| # | Layer | Artefact | What it stops | Strength |
|---|---|---|---|---|
| 1 | Nav visibility | `site.kicker.plugin` → `modelGroups` → `PageModel.roleAccess` | the *link* appearing | cosmetic — the URL still works |
| 2 | Node access | any node's `roleAccess` (page **or** component) | the *node rendering* | real, but **disjunctive** and admin-bypassed |
| 3 | Action predicate | action `predicateIdentifier` → `GroovyPredicate` | the *button*, re-checked server-side at execute **and** at form submit | real gate on writes |
| 4 | Row scope | the table's `model.findRuleIdentifier` → `GroovyExecutionRule` | *which rows exist* for this caller | the only gate on reads |

Coverage as shipped: **C** built all four. **B** built 1+2 plus state-only predicates. **A** and **D** rely on
layer 2 alone — and in A's case layer 2 works only by accident (§3.4).

✅ **The requirement decides the layer.** "Only their own rows" is layer 4 and nothing else. "Only a supervisor
may approve" is layer 3. "This persona has no business on this screen" is layer 2 (+1 for tidiness). A sentence
answered at the wrong layer is not defence in depth, it is a hole with a lid on it.

⛔⛔ **The single most expensive finding of the study:** the layer-2 check is a **disjunction**, and the
`accessors` stanza the authoring dialog writes onto business pages grants `view:true` to ten non-authoring
platform permission roles. A persona holding any one of them opens every persona-gated page in the project,
whatever `roleGroupAccessors` says. Measured: **100 of B's 120 persona-gated pages** are open to all of its
personas for this reason. Read §3.4 before you gate anything.

---

## 1. Where each artefact lives in an export

```
rep-objects.json
  roleGroups[]                 ← the roster: {id, name, roles:[PLATFORM_ROLE,…]}
  userRoleGroupAssignments[]   ← {userId, roleGroupId, roleGroupName}
  rules[]                      ← executor "GroovyPredicate"      (layer 3)
                                 executor "GroovyExecutionRule"  (layer 4 fetch rules)
branches.json[0]
  rootContent … children[]     ← EVERY node carries roleAccess    (layer 2)
    siteMapPage                    page-level gate
    crud.table.plugin              properties.model.stringValue → JSON:
                                     findRuleIdentifier                            (layer 4)
                                     createActions/editActions/globalActions
                                       .actions[].predicateIdentifier              (layer 3)
    process.table.pluin            same three groups + userStartProcessActions
  virtualPlugins[] "<shared left nav>"
    site.kicker.plugin
      properties.modelGroups.stringValue → {"pagesModel":[{…,"roleAccess":{…}}]}    (layer 1)
dynamic-cruds.json
  cruds[].methods[]            ← findAll AND count must DECLARE the scoping parameter
```

Two facts that cost a day each if you do not know them:

⛔ **The left nav you see on every page is not on the page.** It is a shared virtual plugin, and `modelGroups` is
one long JSON string. A per-page kicker node exists too (3–4 items), but the 27–171-item business nav lives in
the virtual plugin. Parse → mutate → re-stringify; never rewrite `pagesModel` wholesale.

⛔ **The roster is in the export; the membership mostly is not.** C shipped **zero** `userRoleGroupAssignments`
behind 124 immaculately gated pages — reachable by nobody but the authoring accounts until somebody added users
by hand on the target realm. `validate` warns when an assignment names a missing group; it does **not** warn on
a group with no assignments. Count them yourself.

---

## 2. Layer 0 — the role-group roster

### 2.1 Shape

```json
{ "id": "2548",
  "name": "Reviewer",
  "roles": ["REPORT_VIEW", "REPORT_VIEW_ANY", "REPORT_EDIT"] }
```

`roles[]` are **platform permission roles**, uppercase, from a closed set of 31 (`ADMIN`, `NCT_AUTHOR`,
`PROJECT_VIEW/EDIT`, `USER_VIEW/CREATE/EDIT/DELETE`, `ROLE_GROUP_VIEW/CREATE/EDIT/DELETE`,
`REPORT_VIEW/VIEW_ANY/EDIT/EDIT_ANY`, `SOURCE_*`, `SCHEDULER_*`, `STORE_EXECUTE/_ANY`, `FILE_STORAGE_VIEW/EDIT`,
`ORGANIZARIONS_VIEW`, `ORGANIZATIONS_EDIT`, `OYO_PROJECT_CONFIGURATION` — note the canonical misspelling
`ORGANIZARIONS_VIEW`). A value outside the set **aborts the import**; `mrjun.py validate` catches it first.

✅ **The same names, lowercased, are the keys of a node's `accessors` map.** That correspondence is the hinge of
the whole disjunction problem in §3.4, and nothing in the JSON hints at it. `REPORT_VIEW` in a roster and
`report_view` on a page are the same permission.

### 2.2 Sizing and naming — 4 of 4 agree

| | roster | authoring groups | business personas | assignments | naming |
|---|---|---|---|---|---|
| A | 10 | Author, Developer | 8 | 12 | job titles, inconsistent case |
| B | 8 | Author, Developer | 6, in the customer's own language | 7 | job titles |
| C | 12 | Author, Developer, System Administrator | 9 | **0** | job titles, 1:1 with the brief's actor table |
| D | 8 | Author, Developer | 6 (incl. one external portal persona) | 7 | job titles |

✅ **Exactly two authoring groups, named `Author` and `Developer`, with `Developer` = `Author` + `ADMIN`.** 4 of
4. Do not invent other names — the platform's own scaffolding pages and the nav template already reference these
two, and they are auto-created on import if absent.

✅ **One role group per actor in the brief; named after the job; singular; title case.** C's roster is literally
the actor table of its brief, which is why every downstream grant reads as a sentence.

✅ **Personas are additive, never exclusive.** B's brief states it outright: these are system roles, not
headcount; one person may hold several. Everything downstream must therefore be `hasAnyRoleGroup(...)`, never an
`if / else if` ladder that assumes one role per person (§5.4 shows D getting this wrong).

✅ **Add a customer-side admin group, separate from `Developer`.** C is the only project with one, and it is the
pattern to copy: `Developer` is the builder's identity; **`System Administrator`** is the customer's own admin —
`ADMIN` + `NCT_AUTHOR` + `USER_*` + `ROLE_GROUP_*` but **no** `SOURCE_*`/`SCHEDULER_*`/`STORE_*`. Every
predicate in C ends `…, "System Administrator")`, so the customer can unblock their own users without the
integrator's account. A and B gate their console pages to `Author`/`Developer` only — meaning the customer
cannot administer their own users at all.

### 2.3 ⛔ The tick-everything roster — minimise `roles[]`

Two of four projects hand-tuned `roles[]`. Two shipped the Role Management UI's "select all non-admin" default,
which is exactly the 31 constants minus `{ADMIN, NCT_AUTHOR, USER_*, ROLE_GROUP_*}` = **21 roles, byte-identical
for every persona**:

```
A  five personas ==
   [FILE_STORAGE_EDIT, FILE_STORAGE_VIEW, ORGANIZARIONS_VIEW, ORGANIZATIONS_EDIT,
    OYO_PROJECT_CONFIGURATION, PROJECT_EDIT, PROJECT_VIEW, REPORT_EDIT, REPORT_EDIT_ANY,
    REPORT_VIEW, REPORT_VIEW_ANY, SCHEDULER_EDIT, SCHEDULER_EDIT_ANY, SCHEDULER_VIEW,
    SCHEDULER_VIEW_ANY, SOURCE_EDIT, SOURCE_EDIT_ANY, SOURCE_VIEW, SOURCE_VIEW_ANY,
    STORE_EXECUTE, STORE_EXECUTE_ANY]        ← B's six personas are byte-identical to this
C  Operator            [REPORT_VIEW, REPORT_VIEW_ANY]
   Reviewer            [REPORT_VIEW, REPORT_VIEW_ANY, REPORT_EDIT]
   Supervisor          [REPORT_VIEW, REPORT_VIEW_ANY, REPORT_EDIT, REPORT_EDIT_ANY]
   Auditor             [REPORT_VIEW, REPORT_VIEW_ANY]
D  Partner Portal      [REPORT_VIEW, STORE_EXECUTE, PROJECT_VIEW]
   Coordinator         [REPORT_VIEW, REPORT_EDIT, STORE_EXECUTE, FILE_STORAGE_VIEW, PROJECT_VIEW]
```

A "select all" persona can **edit data sources, create and edit schedulers, run stores and change project
configuration** — the platform consoles, not just the business screens. And it holds `FILE_STORAGE_VIEW`, which
is what defeats layer 2 (§3.4).

✅ **Hand-write `roles[]` and start from `["REPORT_VIEW", "REPORT_VIEW_ANY"]`.** Add `REPORT_EDIT` only for a
persona who authors report/chart definitions. C proves a nine-persona system runs on nothing more. Add
`STORE_EXECUTE` / `FILE_STORAGE_VIEW` only after you observe a concrete failure without them — and if you add
`FILE_STORAGE_VIEW`, you have just widened page access, so re-read §3.4.

```
python3 builder/tools/mrjun.py rolegroup add --project work --name "Reviewer" \
    --role REPORT_VIEW --role REPORT_VIEW_ANY
```

---

## 3. Layer 2 — `roleAccess` on a node

### 3.1 The two boilerplate `accessors` stanzas

Across **18,636 nodes** in the four exports there are only **7 distinct `accessors` maps**, and two of them
cover 99 %. The map is **not designed per page** — the authoring dialog writes one of two fixed stanzas — so the
only per-page decisions you actually make are `publicReadAccess`, `authenticatedUserAccess` and
`roleGroupAccessors`.

**Stanza A — "author only"** (11,527 nodes). 27 keys; `view/edit/advancedEdit` all `true` for `admin` and
`nct_author`, **all false for the other 25**:

```jsonc
"accessors": {
  "admin":      {"view": true,  "edit": true,  "advancedEdit": true},
  "nct_author": {"view": true,  "edit": true,  "advancedEdit": true},
  "user_view":  {"view": false, "edit": false, "advancedEdit": false},
  …  /* user_edit, user_create, user_delete, role_group_view/edit/create/delete,
        file_storage_view/edit, report_view/edit(+_any), source_view/edit(+_any),
        scheduler_view/edit(+_any), store_execute(+_any), oyo_project_configuration */
}
```

**Stanza B — "author + user-admin"** (3,530 nodes) — and this is **the default the dialog writes onto business
pages**: 112 of C's 124 gated pages, 100 of B's 120, 325 of A's 433. Same 27 keys, but **twelve** carry
`view:true`:

```jsonc
"admin", "nct_author"                        → view/edit/advancedEdit true
"user_view", "user_edit", "user_create", "user_delete",
"role_group_view", "role_group_edit", "role_group_create", "role_group_delete",
"file_storage_view", "file_storage_edit"     → view TRUE, edit/advancedEdit false
/* the remaining 15 keys all false */
```

Two rarer stanzas exist: a 6-key one (`admin`, `nct_author`, `user_*`) on the user-management page, and an
all-27-true one on Settings/Sources. And 3,430 nodes in A carry `"accessors": {}` with `publicReadAccess:true` —
the untouched default, i.e. public.

### 3.2 The four page policies, as shipped

| policy | JSON | A | B | C | D |
|---|---|---|---|---|---|
| public | `publicReadAccess:true` | 50 | 2 | 2 | 2 |
| authenticated | `false / true` | 315 | 1 | 2 | 45 |
| persona | `false / false` + `roleGroupAccessors[x].view:true` | 49 (all `Author` only) | **120** | **124** | 7 |
| closed | `false / false`, no group grant | 19 | 6 | 0 | 13 |

* **C is the reference** — 124 of 128 pages persona-gated, only 401/404 public and the home page authenticated;
  **B** is the same design in a smaller system.
* **A** put 315 of 433 business pages on plain *authenticated*, **D** 45 of 67, and neither used persona gating
  at all despite carrying a full roster. That is the shape you get when the access phase is skipped: the roster
  exists and nothing reads it.
* The "closed" rows are nearly all console pages (Rules, Contexts, Workflows, Database, Business Logic,
  Settings, Audit Logs, Pdf/Mail Templates, Schedulers) and that is correct. **A's and D's home page being
  closed is not** — see §3.4.

### 3.3 The canonical persona-gated page, and the three-tier convention

```jsonc
"roleAccess": {
  "publicReadAccess": false,
  "authenticatedUserAccess": false,
  "roleGroupAccessors": {
    "Author":               {"view": true, "edit": true,  "advancedEdit": true},   // authoring
    "Developer":            {"view": true, "edit": true,  "advancedEdit": true},   // authoring
    "System Administrator": {"view": true, "edit": true,  "advancedEdit": false},  // customer admin
    "Supervisor":           {"view": true, "edit": true,  "advancedEdit": false},  // works the screen
    "Reviewer":             {"view": true, "edit": true,  "advancedEdit": false},
    "Operator":             {"view": true, "edit": true,  "advancedEdit": false},
    "Auditor":              {"view": true, "edit": false, "advancedEdit": false}   // oversight, read-only
  },
  "accessors": { /* stanza A or B — see §3.1 and §3.4 */ }
}
```

**Three tiers, consistent across 967 grants in B and C:**

| tier | view | edit | advancedEdit | count in C |
|---|---|---|---|---|
| authoring (`Author`/`Developer`) | ✓ | ✓ | ✓ | 248 |
| working persona | ✓ | ✓ | | 336 |
| oversight / read-only persona | ✓ | | | 383 |

⛔ **`edit:true, view:false` grants nothing.** The render check reads `view`. B shipped exactly this on all 13 of
its console pages for its administrator persona — the persona whose whole job is user and role-group management
could not open a single console page, with no error anywhere. If you mean "may open it", you mean `view`. Only
ever add `edit`/`advancedEdit` **on top of** `view`, and honestly only for authoring groups; for a business
persona they are decoration (page authoring also needs `NCT_AUTHOR`).

⛔ **An entry with all three false is not a grant, it is a leftover.** The dialog serialises **every role group
it knows** into the map. Useful side effect: the union of keys across an export reconstructs the roster.
Dangerous side effect: stale keys are invisible while all-false — A, C and D all carry five persona names from a
starter template that exist in **no** roster. Harmless here, fatal in the nav (§4).

### 3.4 ⛔⛔ The disjunction — how every persona gate is bypassed

**The page check is `public OR authenticated OR anyAccessorRole OR anyRoleGroupAccessor`.** So a stanza-B page
grants `view` to anyone holding `user_view`, `user_edit`, `user_create`, `user_delete`,
`role_group_view/edit/create/delete`, `file_storage_view` or `file_storage_edit` — **whatever
`roleGroupAccessors` says**. Setting `roleGroupAccessors` is necessary and *not* sufficient.

Cross-referencing each project's roster `roles[]` against each page's stanza:

| project | persona-gated pages a **non-granted** persona can still open |
|---|---|
| B | **100 of 120** — every persona holds `FILE_STORAGE_VIEW` |
| A | 13 (via `FILE_STORAGE_VIEW`) + 1 (via `USER_*`) |
| D | 9 (via `FILE_STORAGE_VIEW`) |
| C | **1** — the all-true Settings page, via `REPORT_VIEW` |

C is clean **because its personas hold only `REPORT_*`**, and `report_*` is `view:false` in both common stanzas.
That is the mechanical reason §2.3 matters: the roster and the page stanza are two defaults in two different
files that multiply.

**The mirror image, in A.** Its home page is `false/false` with no group grant at all — "closed" — and it
renders for A's users *only* because stanza B grants `file_storage_view:view` and every A persona holds
`FILE_STORAGE_VIEW`. Tighten A's roster to `REPORT_VIEW` as §2.3 tells you to, and the front door disappears for
everyone. Two harmless-looking defaults silently holding the front door open.

**The check — run it on every build.** For every page with `public=false, authenticated=false`, intersect each
role group's lowercased `roles[]` with the page's `view:true` accessor keys minus `{admin, nct_author}`. Any hit
is a bypass:

```bash
python3 - <<'PY'
import json
d = json.load(open('work/rep-objects.json'))
groups = {g['name']: {x.lower() for x in g.get('roles') or []} for g in d.get('roleGroups') or []}
b = json.load(open('work/branches.json'))[0]
def walk(n):
    yield n
    for c in n.get('children') or []: yield from walk(c)
for n in walk(b['rootContent']):
    if n.get('pluginName') != 'siteMapPage': continue
    ra = n.get('roleAccess') or {}
    if ra.get('publicReadAccess') or ra.get('authenticatedUserAccess'): continue
    viewable = {k for k, v in (ra.get('accessors') or {}).items() if v.get('view')} - {'admin','nct_author'}
    granted  = {k for k, v in (ra.get('roleGroupAccessors') or {}).items() if v.get('view')}
    for g, roles in groups.items():
        if g in granted: continue
        hit = roles & viewable
        if hit: print('BYPASS', n.get('name'), '|', g, '| via', sorted(hit))
PY
```

**The fix, in order:**

1. Personas hold `REPORT_VIEW`(+`_ANY`) and nothing else (§2.3). This alone closes 99 % of it.
2. On any page whose access must be per-persona, force the stanza down to author-only:
   ```
   python3 builder/tools/mrjun.py roleaccess set <pageId> --project work \
       --public false --authenticated false \
       --role "admin:*" --role "nct_author:*" \
       --rolegroup "Reviewer:view" --rolegroup "Supervisor:view,edit"
   ```
3. Assert afterwards that no other `accessors` key has `view:true`. Verify by intersection, never by eye.

### 3.5 Two behaviours to author around

⛔ **`admin` bypasses every node check, and the roster API may agree with it** — so no authoring account can test
any layer. Full rule in §8.

⚠️ **Unresolvable membership fails OPEN at layer 2 and CLOSED at layers 3–4.** The node check keeps the legacy
grant when the identity store cannot answer; `service.security.hasAnyRoleGroup` returns `false`. During an
identity outage a persona page still renders, while every button on it vanishes and every scoped list empties.
That asymmetry is why layers 3 and 4 are the real gate and layer 2 is hygiene.

### 3.6 Component-level gating — one project, one very good use

Only **B** gated non-page nodes: **204 nodes**, all to one top-management persona, all of them monetary. Its
brief requires that the persona who records quantities never sees amounts. The build implements that as three
moves at once:

* on every shared document form, **the label node and the field node are gated as a pair** — currency, rate
  date, exchange rate, rate source, total amount, line amount, unit price, unit cost, amount before/after: 64
  `nct.label.plugin` + 54 `dynaform.form.text.field.plugin` + 6 `dynaform.form.rimm.drop.down.field.plugin` + 4
  datepickers;
* **6 `chart.js.plugin` nodes** — the KPI tiles that aggregate the same numbers;
* the matching `crud.table.plugin` **simply omits the money columns from `columnSettings`**.

```jsonc
// on the field node AND on its label node
"roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": false,
                "roleGroupAccessors": { "Director": {"view": true, "edit": false, "advancedEdit": false} },
                "accessors": { /* stanza */ } }
```

✅ That triple is the supported answer to "this persona may not see this number", because
`CrudTableColumnSettings` has **no** predicate — a column cannot be role-gated. Gate the form field, drop the
table column, and gate the chart node if the number is also aggregated.

⛔ **Gate the label too.** A gated field beside an ungated label leaves a caption floating over nothing, and
reviewers file that as a rendering bug rather than a permission.

⛔ **Component `roleAccess` is honoured inside a parsis** (which checks each child before rendering) and by each
plugin's own gate — but a per-placement grant hand-written onto the page-local stub of a **linked common
component** is read from the shared node instead. Detach from the virtual template first.

---

## 4. Layer 1 — the nav

`PageModel.roleAccess` is the same object as a node's and membership is checked the same way. Omit it and the
item defaults to `publicReadAccess:true` → visible to everyone.

```jsonc
// one item inside modelGroups.pagesModel
{ "order": 7, "name": "Work queue", "uuid": "…", "parentUuid": "…", "icon": "pe-7s-note2",
  "heading": false, "linkModel": { "identifier": "<siteMapPage identifier>", … },
  "localizedMap": { "name": { "en_US": "Work queue", … } },
  "roleAccess": {
    "publicReadAccess": false, "authenticatedUserAccess": false,
    "roleGroupAccessors": { "Author": {"view":true,…}, "Reviewer": {"view":true,…}, … },
    "accessors": {}
  },
  "children": [] }
```

| | nav links | carrying `roleAccess` | mirror the page's grants? |
|---|---|---|---|
| A | 171 | 44 | no — most business links ungated |
| B | 55 | **55** | **yes, exactly** (0 mismatches) |
| C | 44 | **44** | yes, 1 mismatch |
| D | 27 | 15 | partly |

✅ **Every nav item carries the same `roleGroupAccessors` map as its target page.** Both projects that did the
access phase did this, including the console links —
`Rules / Contexts / Form Groups / Workflows / Processes / Users / Role Management / Database / Business Logic / Audit Logs / Pdf Templates / Mail Templates / Schedulers / Settings`
gated to `Author, Developer[, System Administrator]`, so an operator's sidebar contains only their own screens.
That is what turns a platform console into a product.

⛔ **Pick one school for "who else can always see this" and apply it to every item.** Three projects put the
build identities in `roleGroupAccessors` (`Author` / `Developer` / `System Administrator` appended to every
item, `accessors: {}`); one puts them in `accessors` (`admin`/`nct_author` all-true, business roles only in
`roleGroupAccessors`). Either works. The failure is an item with **neither** — gated to role groups that grant
nobody, with an empty `accessors`: an item no one can see.

**Three failure shapes, all observed:**

1. **The inert gate.** A's nav group carries `roleAccess` **with `publicReadAccess:true`**. The check
   short-circuits on public before any group is read, so the ticks do nothing. *Untick public (and, for a
   persona, authenticated) first, then grant.*
2. **The phantom persona.** A, C and D each ship a home/console link gated `false/false` to five persona names
   inherited from a starter template that exist in **no** roster. Result: the link is invisible to every real
   user and only the authoring accounts can navigate home. Nothing in `validate`, `pack` or import reports it.
   Highest-yield single check in §9:
   `set(roleGroupAccessors keys in modelGroups) − set(rep-objects.roleGroups[].name)` must be empty.
3. **Nav gated, page not.** C's home link is `false/false` while the page is `authenticated:true`. Harmless
   there, but it is the same defect pointing the other way: the nav is not access control, and a link you hid
   does not protect a URL you left open.

---

## 5. Layer 3 — action predicates

### 5.1 Wiring

```jsonc
// crud.table.plugin → properties.model.stringValue
"editActions": { "actions": [
  { "id": "…", "localizedNames": {…}, "localizedButtonNames": {…}, "icon": "pe-7s-check",
    "direct": true,                                    // no form; runs the rule straight away
    "onBeforeCompleteRuleIdentifier": "<EXECUTION rule>",
    "predicateIdentifier": "<GroovyPredicate>" },      // ← the gate
  { "id": "…", "direct": false, "formGroupIdentifier": "…", "formInModal": true,
    "modalWidth": "90%", "onBeforeCompleteRuleIdentifier": "…",
    "predicateIdentifier": "…" } ] }
```

One action, **one** `predicateIdentifier` — you cannot AND two predicates in JSON, which is why the role check
and the state check must live in the same rule or be composed in Groovy (§5.6). The platform re-evaluates the
predicate **server-side at execute and again at form submit**, loading the id from the saved settings rather
than from the request, and fails closed on error. It is a real gate, not decoration.

### 5.2 Coverage measured

| | actions | role-guarded | state-only | **no predicate** | predicates in `rules[]` |
|---|---|---|---|---|---|
| A | 347 | 0 | 0 | **345** (+2 dangling ids) | 9 |
| B | 214 | 0 | 93 | **121** | 106 |
| C | **116** | **114** | 0 | 2 | 58 |
| D | 42 | 1 | 24 | 17 | 27 |

C: 98 % of actions carry a role-aware predicate. A: every one of 347 buttons is pressable by anyone who can
reach the page. That gap is the whole distance between the two builds.

### 5.3 The canonical predicate — role first, then the row, then the state

C's 32 lifecycle predicates are the same 12-line template with three substitutions (`<groups>`, `<alias>`,
`<states>`):

```groovy
if (!service.security.hasAnyRoleGroup("Supervisor", "System Administrator")) { return false }
def r = null
def _sid = null
try { _sid = context.data.getAttr('documentId') } catch (Throwable ignored) { }
if (_sid == null) { try { _sid = context.data.getAttr('subjectId') } catch (Throwable ignored) { } }
if (_sid != null && !(_sid.toString().trim().isEmpty())) {
    try { r = service.crud.document.get(_sid.toString()) } catch (Throwable ignored) { }
}
if (!(r instanceof Map) || r.id == null) { try { r = context.<ctx>.document.data.get() } catch (Throwable ignored) { } }
if (!(r instanceof Map) || r.id == null) { return false }
def v = (r.state ?: '') as String
return ['DECIDED', 'RESPONDED', 'IN_REVIEW', 'PENDING_DECISION'].contains(v)
```

Why each line is there:

* ✅ **Role check first, `return false` on line 1.** Cheapest branch, and the predicate can never leak a row read
  to a non-member.
* ✅ **Re-read the row from the DB by id; fall back to the context copy only.** The context copy is stale at the
  form-submit re-check and absent when the predicate runs outside a populated context. C states it in a comment:
  *read back from the DB, not from a stale copy.*
* ✅ **Two attribute names** (`<entity>Id`, then `subjectId`) because the same predicate is reached from an
  entity table and from a generic subject worklist.
* ✅ **Every read wrapped in `try/catch (Throwable)` with the default `false`.** Fail closed, always: an
  exception in a predicate must hide the button, not reveal it.
* ✅ **Terminal `['A','B'].contains(v)`** rather than `!=` — see the bug in §5.5.

Read-only role gates are one line, get their own rule and are reused by many actions:

```groovy
return service.security.hasAnyRoleGroup("Supervisor", "System Administrator")                 // "Is Supervisor"
return service.security.hasAnyRoleGroup("Supervisor", "Controller", "Auditor",
                                        "Approver", "System Administrator")                   // "Is Oversight"
```

✅ **Name them `Is <Persona>`** (10 in C, 6 in B, 5 in D — a convention in 3 of 4) and **always append the
customer-admin persona** to every list, or the customer's own admin cannot use their own product.

### 5.4 ⛔ Polarity — scope the ones you don't trust, never exempt the ones you do

Two projects wrote the same idea with opposite logic:

```groovy
// C — deny by default. Anyone who is not oversight is scoped, including a user with no role at all.
if (!service.security.hasAnyRoleGroup("Supervisor", "Controller", "Auditor",
                                      "Approver", "Liaison", "System Administrator")) {
    filter['unitId'] = _myUnit()
}

// D — allow by default. ⛔ An unmapped user, or one whose group lookup fails, matches NEITHER
// arm and is left completely unscoped.
if (service.security.hasAnyRoleGroup("Partner Portal")
        && !service.security.hasAnyRoleGroup("Coordinator")
        && !service.security.hasAnyRoleGroup("Supervisor")
        && !service.security.hasAnyRoleGroup("Developer")) {
    filter['partnerEmail'] = (service.security.user()?.email ?: '__none__')
}
```

✅ **Always write `if (!hasAnyRoleGroup(<the wide roles>)) { scope }`.** The set you enumerate is the set that
sees everything; every other caller — a new persona, an unassigned account, an identity outage, a scheduler with
no principal — lands in the scoped branch. D's polarity means adding a seventh persona silently grants it the
whole table. This is the highest-leverage single line in the slice.

### 5.5 Four-eyes / separation of duties

Two independent implementations, one doctrine: **the row must carry the actor's identity, and the identity key
is the e-mail.**

```groovy
// C — a second-pair-of-eyes decision: the proposer AND the assignee of the linked parent are both refused
if (!service.security.hasAnyRoleGroup("Approver", "System Administrator")) { return false }
def row = null
try { row = context.<ctx>.decision.data.get() } catch (Throwable ignored) { }
if (!(row instanceof Map) || row.id == null) { return false }
def me = (service.security.user()?.email ?: '').toLowerCase()
if (me.isEmpty()) { return false }                                   // unknown caller → refuse
def proposer = ((row.proposedBy ?: '') as String).toLowerCase()
def parent = null
try { parent = service.crud.document.get((row.documentId ?: row.document?.id) as String) } catch (Throwable ignored) { }
def assignee = ((parent?.assigneeEmail ?: '') as String).toLowerCase()
if (proposer == me) { return false }
if (!assignee.isEmpty() && assignee == me) { return false }
return ((row.state ?: '') as String) == 'PROPOSED'
```

On a reversal action C excludes three distinct actor columns at once —
`return appliedBy != me && requestedBy != me && raisedBy != me` — and B writes the same rule with an escape
hatch for the customer's administrator:

```groovy
if (!service.security.hasAnyRoleGroup("Director") && !service.security.hasAnyRoleGroup("System Administrator")) { return false }
…                                                            // locate the row among the 11 document contexts
def mail   = (service.security.user()?.email ?: '').toLowerCase()
def author = ((doc.createdBy ?: doc.submittedBy ?: '').toString().toLowerCase())
if (!mail.isEmpty() && mail == author && !service.security.hasAnyRoleGroup("System Administrator")) { return false }
return true
```

Rules distilled from both:

* ✅ **Lower-case both sides and compare e-mails.** `user().id` is *not* the same value in a fetch rule and in an
  action predicate; the e-mail is the only key that matches on both sides.
* ⛔ **An empty `me` refuses.** `if (me.isEmpty()) { return false }` — otherwise `'' == ''` makes an anonymous
  caller look like the author, or unlike everyone, depending on the comparison.
* ✅ **The entity must carry the identity column** (`createdBy`, `submittedBy`, `proposedBy`, `appliedBy`,
  `requestedBy`, `raisedBy`, `assigneeEmail`) and it must be **written from `service.security.user().email` at
  create/act time**, in the EXECUTION rule.
* ✅ **Enforce it in the EXECUTION rule too, not only the predicate.** C re-runs the same exclusion before
  writing: the predicate hides the button, the rule refuses the write.

⛔ **The state assertion does not belong in the reusable four-eyes predicate.** B recorded the bug in a comment:
it had `doc.status != 'SUBMITTED' → false` inside the shared "may this person approve?" rule, which is also
reused by the reverse action (valid only from `POSTED`/`CLOSED`) — so **every reverse button in the application
was permanently hidden**, on nine document types at once, with no error anywhere. Split it: *role + four-eyes*
in the shared predicate, *state* in the caller.

### 5.6 Composition vs inlining — a real fork

* **B (45 rules) and D (11)** compose:
  ```groovy
  if (context.<ctx>.document.data.get()?.status != 'SUBMITTED') { return false }
  return service.rule("<approval is allowed to the approver>") as boolean
  ```
* **C (0)** inlines everything, and pays for it: its six-name oversight list appears **verbatim 30 times**
  across its rules. Rename a persona and you must find all 30.

`service.rule("Name")` resolves **by name**, runs with the same `contextData`, and is handed an **empty
`executionVariables`** — `attrs`, `param` and `service.actionId` are *not* forwarded.

✅ **Jump this way: compose the role half, inline the state half.** `Is <Persona>` / `Is Oversight` need only
`service.security`, so they are safe to call; the state check needs the row and belongs in the action's own
predicate. You get one place to edit when the roster changes and you never depend on `attrs` inside a called
rule. Cost: rule names must be unique project-wide and a rename breaks the caller silently — keep the
`Is <Persona>` names mechanical and grep before renaming.

### 5.7 What the predicate layer is **not** for

⛔ `formGroups[].predicateFormMapping.mapping[].predicateIdentifier` is a **form chooser, not a gate**: across
all four projects, **211 mappings and zero role-aware predicates**. Do not hide a form by mapping it behind a
role predicate — if no branch matches, the user gets no form at all, not a refusal, and nothing says why.

---

## 6. Layer 4 — row scope in the fetch rule

### 6.1 Wiring and coverage

The table's `model.findRuleIdentifier` points at a **`GroovyExecutionRule`**, context-free, returning a
`PageResult`. If it is absent the platform calls the generated `find` and there is **no scoping hook at all**.

| | `crud.table` nodes | with `findRuleIdentifier` | **with a scoped one** |
|---|---|---|---|
| A | 129 | 27 | 0 |
| B | 37 | 37 | 0 |
| C | 33 | 16 | **16** |
| D | 13 | 8 | 1 |

C wrote **14 near-identical `Unit Scope Filter - <Entity>` rules**, one per entity, plus the same scope inside
its export rules, its dropdown-choices rules and its exception-list rules. B, whose brief has no row-level
requirement, correctly wrote none — *no requirement, no rule* is a valid answer; *requirement, no rule* is the
defect.

### 6.2 The canonical scoped fetch rule

```groovy
def _rows = { r -> (r instanceof Map ? (r.content ?: []) : (r ?: [])) }

// Oversight roles are NOT scoped; everyone else is, and the scope is written
// AFTER the forwarded values so a client-supplied unit can never widen it.
def _myUnit = { ->
    def me = (service.security.user()?.email ?: '') as String
    if (me.isEmpty()) { return '00000000-0000-0000-0000-000000000000' }          // fail CLOSED
    def sp = service.crud.staffUser.find([ email: me, fullName: '', unitId: '', jobRole: '',
                                           isActive: 'true', rowsInPage: 5, pageNumber: 0, preferredLanguage: ''])
    def rs = _rows(sp)
    if (rs.isEmpty()) { return '00000000-0000-0000-0000-000000000000' }          // fail CLOSED
    def u = (rs[0].unitId ?: rs[0].unit?.id)
    return (u == null ? '00000000-0000-0000-0000-000000000000' : (u as String))
}

// Pagination + filter values arrive from the table via attrs (Jackson JsonNode).
// `param` is empty outside a delegated CRUD method — reading it here silently drops the
// filter form, the column filters AND the paging.
def filter = [ 'rowsInPage': attrs?.get('rowsInPage')?.asInt(),
               'pageNumber': attrs?.get('pageNumber')?.asInt() ]
attrs?.each { k, v ->
    if (k != 'rowsInPage' && k != 'pageNumber' && v != null && !v.isNull()) {
        filter[k] = v.isNumber() ? v.numberValue() : (v.isBoolean() ? v.booleanValue() : v.asText())
    }
}
// LAST: the scope. A client-supplied unitId is overwritten here, never merged.
if (!service.security.hasAnyRoleGroup("Supervisor", "Controller", "Auditor",
                                      "Approver", "Liaison", "System Administrator")) {
    filter['unitId'] = _myUnit()
}
return service.crud.document.find(filter)
```

**Five load-bearing details. Miss one and the scope is decorative:**

1. ✅ **Order.** The scope is assigned *after* the `attrs?.each` loop. The loop copies in whatever the page
   submitted; last write wins and it must be yours. A scope written before the loop is overwritten by a crafted
   request and nothing logs it.
2. ✅ **Overwrite, never default.** `filter['unitId'] = …`, never `filter['unitId'] = filter['unitId'] ?: …`.
3. ✅ **The scope value comes from the server, keyed by identity.** Look the caller's unit up in the DB by
   `email == user().email` — never from a request field, a session value or a mirror column. That lookup needs a
   table linking platform identity to business scope; add `staff_user(email, unit_id, job_role, is_active)`
   while you are still designing the schema, not after.
4. ⛔⛔ **The fail-closed value must be a value that matches NO row — not the empty string.** The generated SQL is
   `col IS NOT DISTINCT FROM COALESCE(CAST(NULLIF(CAST(:p AS text),'') AS uuid), col)`, i.e. **empty string
   means "no filter"**. So the natural `return ''` on "I couldn't resolve your unit" returns **everything**. C
   returns the zero UUID `'00000000-0000-0000-0000-000000000000'`; D returns the literal `'__none__'` for a text
   column. Pick a sentinel of the column's own type that cannot occur.
5. ⛔ **The scoping key is dropped unless the SQL declares it — in `findAll` AND in `count`.** A key the SQL does
   not name is silently ignored and the list returns every row: clean `validate`, no warning, no log line. Worst
   failure shape there is.

**A child table with no scope column of its own** gets the scope by subquery on the parent, with the scope as a
declared parameter:

```sql
AND document_id IN (SELECT p.id FROM document p
                    WHERE p.unit_id IS NOT DISTINCT FROM
                          COALESCE(CAST(NULLIF(CAST({name:'unitScopeId', type:'string'} AS text),'') AS uuid), p.unit_id))
```

✅ **Naming, 12/12 consistent:** the key is `unitScopeId` when the scope must be reached through a join, plain
`unitId` when the table carries the column itself.

**A purpose-built list method** takes the scope as an explicit parameter — and here the empty string is the
deliberate *unscoped* signal, the opposite convention to detail 4, because this parameter is only ever set by
the server:

```groovy
def scope = ''
if (!service.security.hasAnyRoleGroup(<oversight…>)) { scope = _myUnit() }
return service.crud.document.findOverdue([ clockCode: 'REVIEW',
        unitScopeId: scope,
        rowsInPage: (attrs?.get('rowsInPage')?.asInt() ?: 15),
        pageNumber: (attrs?.get('pageNumber')?.asInt() ?: 0) ])
```

⛔ Two conventions for one concept in one codebase is a trap of its own. Write down which parameters are
server-only, and never let a server-only scope key appear in a filter form.

### 6.3 ⛔ Scope every surface, not just the table

C applies the *same* unit scope on **four** surfaces. This is the part most builds miss, and each miss is a
complete bypass of the one that was done right:

| surface | rule | why it leaks otherwise |
|---|---|---|
| the table | `Unit Scope Filter - <Entity>` (×14) | — |
| the **dropdown / autocomplete** | same guard, `scope` into `find`, then `service.global.conversion.toSelectOptions(list,"id","docNo")` | a picker that offers every unit's rows *is* the leak, one row at a time |
| the **export** | `Export <Register>` (×15) — rebuilds the same filter, `rowsInPage: 2000`, renders a PDF **and writes an `EXPORT` audit row with the row count** | an unscoped export defeats a scoped screen in one click |
| **exception / overdue lists** | `Exception Filter - <…>` — passes `unitScopeId` into the custom SQL | the same rows under a different heading |

⛔ **A choices rule must still end in `toSelectOptions(...)`.** Scoping it does not change that; a raw `find`
result makes the picker show "No results found".

✅ **Audit the export.** C writes an audit row per export with the row count. It is the only surface where a
scope failure is otherwise invisible after the fact.

### 6.4 Never fetch-then-filter in Groovy, and never in the browser

⛔ A's worklist screen does `service.crud.task.findAll([assignedTo: null, rowsInPage: 2000, pageNumber: 0])` and
then `rows.findAll { … }` in Groovy. At least it is server-side, so nothing leaks to the client — but the row
cap silently truncates: past 2,000 rows a user stops seeing their own. Pass the scope into the SQL. Hiding rows
in JS is worse: they were already sent.

Same doctrine one level down for a **column** the viewer may not see: leave it out of the projection (§3.6),
never hide the cell.

---

## 7. Where the gate does not reach

Five holes, all present in the best of the four builds.

1. ⛔⛔ **Charts are unscoped, in every project.** C scopes 16 tables and 15 exports and **0 of its 87 charts**;
   the other three scope 0 of 55, 0 of 31 and 0 of 12. A chart is a `chart.js.plugin` bound to a query through
   the report/filter machinery; its parameters come from the filter bar and the session, all client-side, and
   **SQL has no access to `service.security`**. So a scoped list sits happily on a page whose dashboard totals
   every unit in the business. Options, in order of honesty: (a) put the dashboard on its own page and gate that
   page to the oversight personas — the only clean answer; (b) give the query a `unitScopeId` parameter and
   accept that whatever fills it is a filter, not a gate; (c) build the tile in an `nct.html.plugin` whose
   `ctx.callRule` hits a scoped EXECUTION rule. ✅ Decide this consciously, in writing, before the dashboard is
   built.
2. ⚠️ **`totalElements` can report the whole table while the rows are scoped.** Two facts collide. The generated
   `find` GROOVY body calls `service.crud.<alias>.count()` **with no argument** in 241 of 244 CRUDs — *and* that
   body is not executed while `find.ruleIdentifier` is null, because the Java auto-find intercepts and calls
   `count` with the **same** argument map as `findAll`. So the no-arg `count()` is inert for a generated `find`
   and bites the moment a script actually runs: a hand-written `find`, or any paginating rule of your own. **The
   load-bearing requirement either way is detail 5 of §6.2** — the scope key must be a declared parameter of
   `count` as well as `findAll`. In a body you write yourself: `count(filter)`, never `count()`.
3. ⛔ **Schedulers run with no principal.** All **43** schedulers across the four projects ship
   `serviceUserId: null` and `serviceUserEmail: null`, so `service.security.user()` is empty and
   `hasAnyRoleGroup` is `false` for everything. Two consequences: a `service.workflow.start` from a scheduler
   writes **no owner access row and no `owner` variable** unless you pass one — which is why C hard-codes a
   functional mailbox (`owner: 'workqueue@<domain>'`) in all eight of its sweep rules; and **a scoped fetch rule
   reused from a scheduler returns nothing**, because it takes the `!hasAnyRoleGroup` branch and then the
   fail-closed sentinel. ✅ **Share the SQL method between the screen and the sweep, never the scoped wrapper.**
4. ⚠️ **Worklist visibility is a separate grant.** `service.workflow.start` takes `roleGroups:` and that is what
   decides who sees the item in a worklist. Three of four pass it (C 8/8 start rules, B 5/5, D 1/2):
   ```groovy
   service.workflow.start([ … , owner: 'workqueue@<domain>',
                            roleGroups: ["Reviewer", "Supervisor"] ])
   ```
   ⛔ Names match **exactly**; a typo creates an access row that can never match, and nothing says so. And
   `process.table` actions carry their own `predicateIdentifier` — C's do; A's points at a rule that is not in
   `rules[]` at all. 5. ⚠️ **PDF and mail carry the data out of the app.** Nothing in the platform makes a
   template honour a row scope — the rule that builds the payload must (§6.3).

---

## 8. The test-account rule

⛔⛔ **An authoring account cannot test any layer.** `admin` bypasses every node check by design, and on at least
one deployment `hasAnyRoleGroup(<any name>)` also answered **true** for `ADMIN`/`NCT_AUTHOR` — which means
layers 3 and 4 pass for an authoring account too. Every "I checked, the gate works" performed from `Author`,
`Developer` or a customer `System Administrator` login is worth nothing, in either direction: you cannot prove a
gate holds, and you cannot prove a page is reachable.

✅ **Keep one no-role test account per persona, assigned to exactly that one role group, from the first day of
the build.** Add the `userRoleGroupAssignments` rows to the export so they survive a re-import. For each account
verify, on the running page:

* the nav shows only their sections;
* a direct URL to a page they should not have returns nothing (test the URL, not the link);
* the row count on each scoped list equals the count you get from the DB for that scope;
* the buttons they must not press are absent — and a saved form URL for an absent button is **refused on
  submit**, not merely hidden;
* one chart on each dashboard shows the number you expect for their scope (§7.1).

⛔ **Smoke-test `hasAnyRoleGroup` itself before you build a permission model on it.** It is resolved against the
identity provider and **every failure is swallowed into `false`**, which hides actions from real members with no
error anywhere. A's build is the endgame of skipping this test — see §10.

---

## 9. The review checklist

Run 1–14 against the unpacked export; they are mechanical and found real defects in three of these four
projects. 15–16 need a browser and the accounts from §8.

**Roster**

1. Every `hasAnyRoleGroup("X")` string in `rules[]` resolves to a `roleGroups[].name`. Found 1 dead name in A.
   ```bash
   python3 - <<'PY'
   import json, re, collections
   d = json.load(open('work/rep-objects.json'))
   roster = {g['name'] for g in d.get('roleGroups') or []}
   bad = collections.Counter()
   for r in d['rules']:
       body = r['rule'].get('ruleScriptStr','') if isinstance(r['rule'], dict) else ''
       for m in re.finditer(r'hasA(?:ny|ll)RoleGroups?\(([^)]*)\)', body, re.S):
           for n in re.findall(r'"([^"]+)"', m.group(1)):
               if n not in roster: bad[(r['name'], n)] += 1
   print(bad or 'OK')
   PY
   ```
2. Every `roleGroups[]` entry has at least one `userRoleGroupAssignments` row. C shipped zero.
3. `roles[]` is minimal — flag any persona holding more than `REPORT_VIEW`/`REPORT_VIEW_ANY`/`REPORT_EDIT`, and
   any non-authoring group holding `ADMIN`.

**Pages** (the disjunction audit finds the most)

4. No persona reaches a persona-gated page through `accessors` — run the script in §3.4.
5. No `edit:true, view:false` grant anywhere. 13 in B, all inert.
6. No inert gate: a node or nav item with `publicReadAccess:true` *and* a `view:true` group grant. Also flag
   `roleAccess` omitted entirely on a business page — that is public.

**Nav**

7. Every `roleGroupAccessors` key in `modelGroups.pagesModel` exists in the roster (the phantom-persona check;
   fails in 3 of 4).
8. Every gated link's grant set equals its target page's grant set. B 0 mismatches, C 1, A 2, D 1.
9. Console links are gated to the authoring + customer-admin groups. Do it by **appending** to the shared nav
   node's page group — never by replacing `pagesModel`.

**Actions and rows**

10. Every action that writes has a `predicateIdentifier`, and it resolves. A has 345 unguarded and 2 dangling
    ids.
11. Every persona-restricted predicate starts with the role check, returns `false` from it, wraps every read in
    `try/catch (Throwable)`, and re-reads the row from the DB.
12. Every list whose brief says "only their own / only their unit" has: a scoped fetch rule set as
    `findRuleIdentifier`; the scope written **after** the `attrs?.each` loop; a **non-matching sentinel** on the
    fail path; the scoping column declared in **both** `findAll` and `count`; and the polarity
    `if (!hasAnyRoleGroup(<wide>))`.
13. The same scope on the dropdown-choices rule, the export rule and any exception list over the same entity.
14. `count(filter)` — never `count()` — in any paginating body you wrote yourself.

**Live**

15. Charts: either the page is gated to the personas allowed to see the aggregate, or the chart node itself is,
    or the decision that dashboards are deliberately unscoped is written down.
16. Schedulers: any scheduler whose rule calls `service.security.*` has `serviceUserId` set, or the rule passes
    an explicit `owner`/`roleGroups` and never calls a scoped fetch rule.

---

## 10. What `validate` covers, and the checks that should exist

**Covered today:** `roleGroups[].roles` are canonical platform-role constants (the import aborts otherwise);
`userRoleGroupAssignments.roleGroupName` resolves; dangling form-group and scheduler `predicateIdentifier`;
scheduler predicate/action rule types.

**Not covered — items 1, 4, 5, 6, 7, 8, 10, 12, 13, 14 and 15 above.** Those are the checks that found every
defect in this study. Until they exist in the validator, run them by hand. In priority order, the checks worth
adding:

| check | why it earns its place |
|---|---|
| `set(roleGroupAccessors keys) ⊆ set(roleGroups[].name)`, on nodes **and** nav | phantom personas in 3 of 4; hides the front door |
| the §3.4 disjunction intersection | 100 bypassed pages in one project alone |
| `edit:true && !view` | silently inert, 13 occurrences |
| `publicReadAccess:true` together with any group grant | the gate that does nothing |
| role group with zero assignments | 124 gated pages reachable by nobody |
| dangling `predicateIdentifier` on a table/tree/process action | 2 in A |
| a `findRuleIdentifier` rule that mentions a scope key the CRUD's `count` does not declare | the silent full-table read |

**The anti-pattern gallery** — each of these shipped:

* ⛔ **The shadow permission system.** When `hasAnyRoleGroup` could not resolve on their deployment, A rebuilt
  authorisation in application data: `system_settings` rows (`task.restrict`, `task.<action>_roles`,
  `task.role_members`, `task.see_all_roles`, `task.own_tasks_only_roles`, `task.see_all_users`) plus a
  comma-separated `users.role_groups` mirror column. Its own comments record four failures: the default was
  **open** (`def restrict = false`); the mirror recorded users under the wrong id and *"sent the whole worklist
  to the browser"*; the settings are `jsonb`, arriving as Jackson `ObjectNode`/`ArrayNode` — neither `String`
  nor `List` — so *"every read returned null and every setting fell back to its hardcoded default"*, silently;
  and the restricted persona could not read `system_settings` at all, so the membership map read empty for
  exactly that user and the code fell through to the permissive branch. **If the platform API does not work,
  escalate it; do not reimplement authorisation in business tables.** If you must: default **closed**, coerce
  `jsonb` explicitly, and never let an unreadable config widen a privilege.
* ⛔ **Persona gating with no assignments** — 124 immaculately gated pages, zero users.
* ⛔ **State-only predicates as the security model.** B's 93 `Can Submit/Post/Reject/Reverse` predicates check
  only `status`; any persona who reaches the page can press any of them. Combined with strict page gating that
  is coherent but coarse — the page grant becomes the only thing between a clerk and the approve button, and one
  wrong `roleGroupAccessors` entry is a full privilege escalation. Put the role in the predicate.
* ⛔ **The tick-everything roster**, ⛔ **allow-by-exclusion scoping** (§5.4), ⛔ **state inside the reusable
  four-eyes predicate** (§5.5), ⛔ **`edit` without `view`** (§3.3).

---

## 11. Where these deliveries correct the library

### [01-content-model-and-pages.md](../01-content-model-and-pages.md) §"Access — `roleAccess`"

* ⛔ **The doc says `roleGroupAccessors` "does produce a back-office-only node". Measured, it usually does not**
  — the doc never states that the four fields **OR** together, nor that the dialog fills `accessors` for you
  with ten non-authoring keys at `view:true`. **The deliveries are right and the doc is incomplete**:
  `roleGroupAccessors` is necessary and not sufficient. Add the disjunction, the two stanzas of §3.1 and the
  audit script of §3.4.
* ⛔ **The doc's third page policy — "set `view:true` for the needed keys in `accessors`" — is the instruction
  that produces the bypass.** `accessors` is the *platform-role* map and a business persona can never appear in
  it (the doc says so elsewhere). For a private business page the field you author is `roleGroupAccessors`;
  `accessors` should be pushed **down** to `admin`/`nct_author`. 4 of 4 leave `accessors` on the dialog
  boilerplate; the two that gated properly did it all in `roleGroupAccessors`.
* ⚠️ **The doc's example shows `roleGroupAccessors` entries with all three flags false** — the leftover shape,
  not a grant. Worth a line: it is how phantom personas travel between projects.
* ➕ **Add: `edit:true, view:false` grants nothing.** The doc lists the three flags without saying the render
  check reads `view`; 13 shipped grants in one project were inert for exactly this reason.
* ✅ **"Unresolved ≠ empty, fails open" and "admin bypasses everything" are confirmed** — and need the other
  half: layers 3 and 4 fail **closed** on the same condition, and on at least one deployment `hasAnyRoleGroup`
  returned `true` for authoring accounts, so "author with a non-admin account" understates it. One no-role
  account **per persona** (§8).

### [16-groovy-service-api.md](../16-groovy-service-api.md) §2.3

* ⛔ **"All checks are fail-closed" is true of `service.security.*` and false of the node-level `roleAccess`
  check**, which keeps the legacy grant when membership cannot be resolved. The two live in different docs and
  read as one guarantee. Say plainly in §2.3: *these four methods fail closed; the content-node check in [01](../01-content-model-and-pages.md)
  does not.*
* ➕ **`user().id` is not stable across rule kinds** — a fetch rule gets the signed-in principal, an action
  predicate or form rule gets the platform's internal user-row id. [04](../04-crud-table-plugin.md) says this; §2.3, where `user()` is
  defined, does not. 2 of 2 four-eyes implementations key on **`.email`, lower-cased on both sides, with an
  explicit empty-e-mail refusal**. Put that rule next to the `user()` row.
* ⚠️ **The worked example `hasAnyRoleGroup("X") || hasAnyRoleGroup("Author")` is two calls where the varargs
  form is one**, and it omits the customer-admin group. Shipped convention: one
  `hasAnyRoleGroup("<Persona>", …, "System Administrator")` in a rule named `Is <Persona>` (3 of 4) — a
  predicate that forgets the customer admin locks the customer out of their own product.
* ➕ **Add the fail-closed predicate skeleton of §5.3** — role check first with `return false`, every read in
  `try/catch (Throwable)`, row re-read from the DB, state test last. The same 12 lines appear 32 times in the
  strictest of the four builds.

### [12-queries-sources-schedulers-and-rest.md](../12-queries-sources-schedulers-and-rest.md)

* ⛔ **§4.2's worked `roleGroups[]` example is the Role Management UI's "select all non-admin" default** — the
  same 21 constants, `SCHEDULER_EDIT*`, `SOURCE_EDIT*`, `STORE_EXECUTE*`, `OYO_PROJECT_CONFIGURATION` and all —
  presented as what a persona looks like. Two of four shipped exactly that array for every persona, handing
  business users the platform consoles and, via `FILE_STORAGE_VIEW`, view access to every stanza-B page.
  **Change the example to `["REPORT_VIEW", "REPORT_VIEW_ANY"]`** and add: anything beyond `REPORT_*` must be
  justified by an observed failure.
* ➕ **§4.5 should state the full roster convention** — exactly two authoring groups (`Author`, `Developer` =
  `Author` + `ADMIN`), **plus a customer-side `System Administrator`** distinct from `Developer`, plus one group
  per actor in the brief. One of four had that group, and it is the only project whose customer can administer
  their own users.
* ➕ **§5 should carry the zero-assignment check.** `validate` warns when an assignment names a missing group but
  not when a group has no assignments; one project shipped 124 gated pages and no users.
* ➕ **§3.2c says `service.security.*` is empty without `serviceUserId`; add the two consequences** the
  deliveries paid for. `service.workflow.start` from a scheduler writes no owner access row unless you pass
  `owner`/`roleGroups` explicitly, and **a scoped fetch rule called from a scheduler returns nothing** — it
  takes the `!hasAnyRoleGroup` branch and then the fail-closed sentinel. Share the SQL method with the sweep,
  never the scoped wrapper. 43 of 43 schedulers in the corpus have a null principal.

---

## 12. Build order

1. **Roster.** One group per actor in the brief, plus `Author`/`Developer`, plus a customer-side
   `System Administrator`. `roles[] = ["REPORT_VIEW","REPORT_VIEW_ANY"]` unless proven otherwise. One
   `userRoleGroupAssignment` per test account per persona, in the export.
2. **Identity → scope table.** If any list is per-unit / per-team / per-partner, the schema needs a row linking
   the platform e-mail to the business scope (`staff_user(email, unit_id, …)`), and every scoped entity needs
   the scope column or a parent to subquery through. This is a schema decision; making it late is expensive.
3. **Identity columns on entities.** `createdBy`, plus one column per actor role the four-eyes rule must
   exclude, filled from `service.security.user().email` in the EXECUTION rule.
4. **Predicates.** One `Is <Persona>` per persona (always including the customer admin), then one per action:
   role check first, row re-read, state last.
5. **Pages.** `public:false, authenticated:false` + `roleGroupAccessors` in three tiers, and force the
   `accessors` stanza down to author-only on anything genuinely restricted. Run the §3.4 audit.
6. **Nav.** Mirror every page's grants onto its link; gate the console group; run the phantom-persona check.
7. **Fetch rules.** One scoped rule per scoped entity, plus the matching dropdown-choices, export and
   exception-list rules. Declare the scoping key in `findAll` **and** `count`.
8. **Write down the chart decision** before building the dashboard.
9. **Run §9, then §8** with real per-persona accounts. Nothing is verified until a no-role account has opened
   the URL.
