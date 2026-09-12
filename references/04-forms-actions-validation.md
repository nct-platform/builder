# Forms, actions & validation — what four delivered projects actually wire

Evidence base: four completed deliveries, counted before the archives were removed. They are named only by shape.

| tag | scale | character |
|---|---|---|
| **A** | 433 pages · 163 CRUDs · 145 form groups · 142 forms · 345 table actions · 1 120 form controls | broad master-data suite, hand-grown, oldest conventions, most cruft |
| **B** | 129 pages · 38 CRUDs · 32 groups · 32 forms · 214 table actions · 627 controls | every entity is a `document` with a DRAFT→APPROVED lifecycle |
| **C** | 128 pages · 31 CRUDs · 37 groups · 38 forms · 108 table actions · 234 controls | `case` handling with hard role separation and four-eyes rules |
| **D** | 67 pages · 12 CRUDs · 16 groups · 16 forms · 42 table actions · 138 controls | workflow-first: most screens are worklist tasks |

Census used throughout: **230 form groups, 228 forms, 709 CRUD-table actions, 2 119 form controls**
(+342 filter-form controls, excluded unless stated). Entity and field names below are renamed to neutral ones
(`document`, `documentLine`, `case`, `task`, `item`, `partner`); every JSON key, plugin name, Groovy idiom, CSS
class and count is byte-exact from the deliveries. Locales are written `en_US` + `<loc2>` + `<loc3>` — all four
projects ship three-locale maps.

Corrects [06-form-groups-and-mapping.md](../06-form-groups-and-mapping.md), [25-form-settings-validation-and-events.md](../25-form-settings-validation-and-events.md) and
[02-form-controls-reference.md](../02-form-controls-reference.md) where the deliveries disagree with them; each correction is called out at the
point of use and listed again in §12.

---

## 0. The census first — four keys carry the behaviour, nine documented mechanisms are dead

Read this before reaching for any mechanism. Left column is what the three library docs offer; right column is
how often four real deliveries reached for it.

| Mechanism | A | B | C | D | total | verdict |
|---|---|---|---|---|---|---|
| `settings.alwaysMandatory` | 114 | 113 | 93 | 36 | **356 controls** | the workhorse |
| red `*` in the slot HTML | 114 | 113 | 93 | 36 | **356 slots** | exact 1:1 with `alwaysMandatory`, all four |
| `settings.mandatoryValidationMessages` populated | 0 | 113 | 93 | 36 | 242 | A ships none → generic fallback text |
| `settings.alwaysProhibited` | 0 | 231 | 48 | 59 | **338 controls** | the second workhorse |
| `settings.defaultValueEnabled` (all `defaultValueStatic:true`) | 0 | 145 | 0 | 1 | 146 | static only |
| `settings.defaultValueRuleIdentifier` | 0 | 0 | 0 | 0 | **0** | documented, never used |
| `settings.prohibitedPredicateIdentifier` | 0 | 0 | 0 | 0 | **0** | documented, never used |
| `settings.mandatoryPredicateIdentifier` | 0 | 0 | 0 | 0 | **0** | documented, never used |
| `settings.conditionalValidations[]` entries | 0 | 1 | 0 | 2 | **3 in 2 119 controls** | the template catalog is ~unused |
| `settings.eventComponentMappings[]` | 0 | 22 | 0 | 1 | 23 | rare, load-bearing where present |
| `settings.between` | 0 | 21 | 0 | 0 | 21 | **filter forms only** |
| `forms[].validators` | 1 rule / 1 attach | 13 / 33 | 3 / 4 | 1 / 1 | **18 rules / 39 attachments** | the real cross-field validation |
| `forms[].actionValidators` | 0 | 0 | 0 | 0 | **0 in 228 forms** | confirmed dead |
| `forms[].hiddenConfigs` | 0 | 0 | 0 | 0 | **0 in 228 forms** | documented panel, never used |
| `forms[].allowDrafts` | 1 | 4 | 0 | 0 | 5 | deliberate, tiny |
| `forms[].multiLanguage` | 138 T / 4 null | 32 T | 8 T / 30 F | 16 T | 194 T | on unless the project is monolingual |
| action `predicateIdentifier` | **0/345** | 93/214 | **106/108** | 25/42 | 224/709 | the biggest divergence between projects |
| action `direct:true` | 92 | 133 | 44 | 20 | 289/709 (41 %) | one per state transition |
| action `onBeforeCompleteRuleIdentifier` | 274 | 187 | 106 | 41 | 608/709 | no built-in persist exists |
| action `formInModal` (always `modalWidth:"90%"`) | 0 | 24 | 64 | 0 | 88/709 | |
| action `submitForm:false` | 0 | 27 | 2 | 1 | 30/709 | always a read-only drill-down |
| `service.actionId` in any rule | 0 | 0 | 0 | 0 | **0** | the documented fork idiom is used by nobody |

**Decision:** wire form behaviour out of **four** settings keys — `alwaysMandatory`,
`mandatoryValidationMessages`, `alwaysProhibited`, static `defaultValue` — plus **form-level `validators`** for
anything cross-field and **action `predicateIdentifier`** for anything state- or role-dependent. Everything else
in the two authoring panels is rare or dead.

Distinguish the two kinds of "dead". **Avoid** (the shape itself is a trap or has a better replacement):
`actionValidators`, `service.actionId` forks, `hiddenConfigs`, `GLOBAL` scope on a table-reachable input.
**The doc oversells it** (the mechanism works, the doc just weights it as the main road):
`conditionalValidations` templates, `mandatoryPredicateIdentifier`, `prohibitedPredicateIdentifier`,
`defaultValueRuleIdentifier`, per-slot event refresh targets.

---

## 1. Form-group topology

### 1.1 The canonical shape — three of four projects agree exactly

Decision: **one group per entity, one landing page per group, form page a sibling of the landing, both children
of the CRUD-table page, both `layout:"Main"`.** This prevents the two failures that cost a whole screen — a form
page created at the site root (unroutable / colliding alias) and a group pointed at a page whose ACL the business
user fails (§1.3).

| | A | B | C | D |
|---|---|---|---|---|
| `placeFormsNextToLanding` | `false` ×145 | `true` ×32 | `true` ×37 | `true` ×16 |
| `formGroupsPageIdentifier` set | 140/145 (a shared admin page) | 0 | 0 | 0 |
| one landing per group | **no** — 108 landings for 145 groups; 38 groups share a system page | 27 for 32 (5 shared with a workflow twin) | 37 for 37 | 16 for 16 |
| form page **sibling** of its landing | 103/142 | 32/32 | 38/38 | 16/16 |
| form page **child** of its landing | 39/142 | 0 | 0 | 0 |
| page `layout` | `Main` ×210, `Form` ×40 (legacy) | `Main` | `Main` | `Main` |
| missing top-level `alias` / alias collisions | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| form plugin inside `html.plugin "Layout"` | 141/141 | 32/32 | 38/38 | 16/16 |
| `forms[].formGroup` copy diverged from `formGroups[]` | 0 | 0 | 0 | 0 |

B, C and D (85 groups) match the ⭐ canonical recipe in [06-form-groups-and-mapping.md](../06-form-groups-and-mapping.md) completely. A is the
older shared-landing style and is the only one carrying real damage. **Copy B/C/D.**

✅ The group and its embedded copy:

```json
// rep-objects.formGroups[]
{ "identifier": "<GROUP_UUID>",
  "localizedNames": { "en_US": "Document Forms", "<loc2>": "…", "<loc3>": "…" },
  "contextIdentifiers": ["<CTX_UUID>"],
  "contentPageIdentifier": "<LANDING_PAGE_UUID>",
  "formGroupsPageIdentifier": null,
  "placeFormsNextToLanding": true,
  "predicateFormMapping": { "mapping": [
     { "predicateIdentifier": "<TRUE_RULE_UUID>", "formIdentifier": "<FORM_UUID>" } ] } }

// rep-objects.forms[]
{ "identifier": "<FORM_UUID>",
  "localizedNames": { "en_US": "Document", "<loc2>": "…", "<loc3>": "…" },
  "contentIdentifier": "<FORM_PAGE_UUID>",
  "contextIdentifiers": ["<CTX_UUID>"],
  "multiLanguage": true, "allowDrafts": null,
  "validators": [], "actionValidators": [], "hiddenConfigs": [],
  "formGroup": { /* byte-identical copy of the formGroups[] entry above */ } }
```

### 1.2 Five invariants that were never broken (230 groups, 228 forms)

100 % of the time in four projects — treat these as contract, not style.

1. `forms[].formGroup` is a **byte-identical copy** of the `formGroups[]` entry, including the whole
   `predicateFormMapping`. 228/228. Nothing keeps them in sync for you; keep them equal by construction, and
   re-copy after every mapping edit.
2. Every landing plugin and every `dynaform.form.plugin` sits **inside** the page's baked `html.plugin "Layout"`
   chrome, in the content `nct.parsis.plugin`. 250/250 form plugins, 192/192 landings.
3. Every landing and form page carries a **present, unique, top-level `alias`**. 0 collisions in 733 pages.
4. Every form page's subtree carries `formModeIdentifier == form.identifier` (§1.4).
5. `form.contentIdentifier != formGroup.contentPageIdentifier` on all 228 forms — the form never lives on the
   landing page.

### 1.3 ⛔ The one live wound: pointing a group at a shared/system landing page

A has **38 form groups whose `contentPageIdentifier` is the empty-baseline system `Landing` page** (a child of
an admin page). That page's `roleAccess` in the same export grants `view` only to platform roles:

```json
{ "publicReadAccess": false, "authenticatedUserAccess": false,
  "roleGroupAccessors": {},
  "accessors": { "admin": {"view":true,"edit":true,"advancedEdit":true},
                 "nct_author": {"view":true,"edit":true,"advancedEdit":true},
                 "user_edit": {"view":true,"edit":false,"advancedEdit":false},
                 "user_view": {"view":true,"edit":false,"advancedEdit":false},
                 "report_edit": {"view":false,"edit":false,"advancedEdit":false} } }
```

A business user outside `admin`/`nct_author`/`user_*` clicks Create or Edit on 38 of that project's tables and is
bounced by the page ACL **before any predicate runs**. Import is green, `crud verify` is green, and the author —
who *is* `nct_author` — never sees it. **Emit a landing page per group under the CRUD-table page; never point a
`formGroups[].contentPageIdentifier` at a shared or baseline page.** Cloning that page as a source of Layout
chrome is a different thing and is fine.

### 1.4 `formModeIdentifier` — write it in BOTH places (corrects [06](../06-form-groups-and-mapping.md))

| where the property sits | A | B | C | D |
|---|---|---|---|---|
| on the form `siteMapPage` | 41 | 32 | 38 | 16 |
| on the `dynaform.form.plugin` node | 141 | 14 | 38 | 2 |

A relies almost entirely on the **plugin-level** property; B and D on the **page-level** one; C sets **both on
every form**. All three render — the platform looks for the property anywhere in the page's subtree.
[06-form-groups-and-mapping.md](../06-form-groups-and-mapping.md) calls the page property mandatory; the truthful statement is *somewhere in the
page's subtree*. C's shape is the only one that cannot be broken by a later `page mv` or by tooling that reads
only one of the two. **Write both.**

### 1.5 `placeFormsNextToLanding` is advisory once the pages exist (corrects [06](../06-form-groups-and-mapping.md))

A ships `placeFormsNextToLanding:false` on all 145 groups while **103 of its 142 form pages are siblings** of
their landing, not children. It runs. The flag tells the platform where to *create* a new form page and where to
*relocate* pages if you flip it in the UI; routing is by identifier. Do not treat a mismatch as a bug — but do
not ship one either, because flipping the flag later moves your pages.

---

## 2. `predicateFormMapping` — how a group picks a form

### 2.1 One pair is the norm

224 of 230 groups carry **exactly one** pair. Six carry two (five in B, one in C). Three carry **zero** (all in
A); none of the three is referenced by an action, so they are dead objects rather than broken buttons — an empty
mapping means the landing opens nothing.

### 2.2 ⛔ Nobody forks on `service.actionId` (corrects [06](../06-form-groups-and-mapping.md))

[06-form-groups-and-mapping.md](../06-form-groups-and-mapping.md) leads its fork recipe with `return service.actionId == '<action-uuid>'`.
**Zero rules in four projects mention `actionId` at all.** All six live forks route on **row state (+ role)**:

```groovy
// mapping predicate, project B — "is this document waiting for MY approval?"
if (context.<ctx>.<documentAlias>.data.get()?.status != 'SUBMITTED') { return false }
return service.rule("<shared approver predicate>") as boolean
```

```groovy
// mapping predicate, project C — "does this row need the variant form?"
def r = null
try { r = context.<ctx>.<caseAlias>.data.get() } catch (Throwable ignored) { }
if (!(r instanceof Map)) { return false }
return ((r.variantFlag ?: false).toString() == 'true')
```

**Jump this way: route forks on row state and role.** Three reasons the deliveries are right and the documented
idiom is a trap: the uuid must match an action id exactly, so a re-created action silently breaks the fork and
`validate` only WARNs; `service.actionId` is **not bound on the workflow branches** (there it is
`attrs.get('actionId')?.asText()`, which the doc itself documents further down), so the same group reached from a
worklist falls through to the fallback; and the state predicate you need anyway for the action's own
`predicateIdentifier` is then reusable as the mapping predicate — one truth, two consumers.

Keep `actionId` only for a pure "which button did they press" split with no state difference, and then read it
through the both-channels helper the doc gives.

### 2.3 Two ways to spell "otherwise" — jump to the explicit `True`

```json
// project B — blank predicate = fallback   (5 groups)
"predicateFormMapping": { "mapping": [
  { "predicateIdentifier": "<narrow: state+role>", "formIdentifier": "<approval twin>" },
  { "predicateIdentifier": "",                     "formIdentifier": "<main form>"     } ] }
```

```json
// project C — explicit True predicate      (1 group)   ← copy this
"predicateFormMapping": { "mapping": [
  { "predicateIdentifier": "<narrow: row has X>",   "formIdentifier": "<variant form>" },
  { "predicateIdentifier": "<True: 'return true'>", "formIdentifier": "<default form>" } ] }
```

Both run. A blank `predicateIdentifier` is indistinguishable, in the JSON and in a diff, from a pair whose
predicate was never filled in, and its semantics are subtler than they look: a blank pair is **not** evaluated in
order — it is remembered as *the* fallback (the first blank one) and applied only after the whole list failed.
One shared `True` rule (`ruleScriptStr:"return true"`, `ruleType:PREDICATE`, `executor:GroovyPredicate`) per
project costs nothing and reads as intent.

### 2.4 The pattern the forks exist for: the **approval twin**

Every one of the six live forks is the same idea: *the same record, shown twice — once to the person who writes
it, once to the person who signs it.* In B the second form is a field-for-field copy of the first with
`alwaysProhibited:true` on everything the approver may not touch:

| form | controls | of which `alwaysProhibited` |
|---|---|---|
| document type 1 — main | 20 | 4 |
| document type 1 — **approval twin** | 13 | **12** |
| document type 2 — main | 12 | 3 |
| document type 2 — **approval twin** | 12 | **12** (fully read-only) |
| document type 3 — main | 46 | 15 |
| document type 3 — **review twin** | 46 | **29** |
| document type 4 — main | 31 | 10 |
| document type 4 — **approval twin** | 31 | **19** |

✅ Recipe:

1. Copy the main form page — new page identifier, new top-level alias `form-<slug>-approval`, new
   `formModeIdentifier` — keeping the layout identical so the approver reads the same screen.
2. Set `alwaysProhibited:true` on every control except the approver's own inputs.
3. Add a second `forms[]` entry and a second `predicateFormMapping` pair **above** the default `True` pair, with
   the state+role predicate. Re-copy the group into both `forms[].formGroup` blobs.
4. Leave the list's decision buttons as **direct** actions (§4.2) — the twin is what the approver *reads*;
   the decision is still a button on the table.

Because the twin is reached through the same group, the actions that open it need no change; routing does it.

### 2.5 The mapping predicate is a chooser, not a gate

Across four projects: **211 mappings, zero role-aware mapping predicates.** Do not try to hide a form by putting
a role predicate on the mapping — if no branch matches, the user gets *no form* (a blank landing), not a refusal.
Role belongs on the action predicate (§5) and on the page ACL (§3.2).

---

## 3. The form page and the landing page

### 3.1 The page skeleton actually shipped — identical in all four

```
<CRUD-table page>            alias=<entity>s              layout=Main
 ├─ <Entity> Forms           alias=<entity>-forms         layout=Main   → dynaform.form.groups.landingplugin
 ├─ Form: <slug>             alias=form-<slug>            layout=Main   → dynaform.form.plugin (formModeIdentifier)
 └─ Form: <slug>-approval    alias=form-<slug>-approval   layout=Main   → dynaform.form.plugin (twin, optional)
```

Inside each page:

```
siteMapPage
└─ parsis (parsis.plugin)
   └─ Layout (html.plugin)
      ├─ header / logo / breadcrumb / left-nav
      ├─ parsis (nct.parsis.plugin)          ← the content area
      │  └─ dynaform.form.plugin             ← or dynaform.form.groups.landingplugin
      │     └─ form.parsis (nct.parsis.plugin, identifier EXACTLY "form.parsis")
      │        └─ gen_row_* → gen_col*_* → gen_slot_* → lbl_* + [help_*] + fld_*
      └─ footer / right-kicker
```

The form plugin's own properties are the generic four plus the link:
`{"className":"","formModeIdentifier":"<FORM_UUID>","isParsis":null,"reuseItems":null,"styleName":"","tagProperties":""}`.
The landing plugin is config-free (`className`/`styleName`/`tagProperties` only); the group is resolved in
reverse, by `contentPageIdentifier` == the landing page identifier.

### 3.2 The two access policies — and what the action predicate does not stop

| | A | B | C | D |
|---|---|---|---|---|
| form pages `authenticatedUserAccess` | `true` (103) / `true`+public (39) | **`false`** | **`false`** | `true` |
| business role groups in `roleGroupAccessors` | none | yes, per form | yes, per form | present, all-false |

⛔ **An action `predicateIdentifier` hides a button. It is not page access control.** The landing is reachable by
URL (`/…/<entity>-forms?group=<uuid>&settingsName=<uuid>&actionId=<uuid>&crudId=<id>`) and every parameter is
visible to anyone who once had the button. The predicate *is* re-evaluated server-side at execute and again at
form submit, fail-closed — so it does gate the write initiated through that action — but it gates nothing that
reaches the CRUD another way, and it never gates the page.

Where segregation of duty is real, do what B and C do — three layers:

```json
"roleAccess": {
  "publicReadAccess": false,
  "authenticatedUserAccess": false,
  "roleGroupAccessors": {
    "<Approver role>":   { "view": true, "edit": false, "advancedEdit": false },
    "<Preparer role>":   { "view": true, "edit": false, "advancedEdit": false },
    "<Supervisor role>": { "view": true, "edit": false, "advancedEdit": false }
  },
  "accessors": { "admin": {"view":true,"edit":true,"advancedEdit":true},
                 "nct_author": {"view":true,"edit":true,"advancedEdit":true},
                 "user_edit": {"view":true,"edit":false,"advancedEdit":false},
                 "user_view": {"view":true,"edit":false,"advancedEdit":false} }
}
```

1. **hide** with the action's `predicateIdentifier`;
2. **block** with `roleAccess.roleGroupAccessors` on the form page *and* on its landing page;
3. **re-assert** in the EXECUTION rule (§5.6) so a direct call, a scheduler or another rule cannot bypass it.

⚠️ Layer 2 is a **disjunction**: the boilerplate `accessors` stanza above grants `view:true` to platform roles a
business persona may also hold, and a persona created with the role-picker's "select all" default walks through
it. Measured in B: 100 of 120 persona-gated pages were open to all eight personas for exactly this reason. Trim
`accessors` on gated pages and test with a real non-admin account. D and A rely on the predicate alone: acceptable
for reference data, not for a decision that separates roles.

---

## 4. Actions

### 4.1 The lifecycle action set — the single most transferable artefact here

B repeats this verbatim for **eleven** entities; C and D repeat its skeleton. It is the answer to "what actions
does a lifecycle record need".

| list | action | `direct` | `submitForm` | `formInModal` | `formGroupIdentifier` | `predicateIdentifier` | `onBeforeCompleteRuleIdentifier` | icon | button label |
|---|---|---|---|---|---|---|---|---|---|
| `createActions` | Create | `false` | – | `true` / `90%` | `<entity>-forms` | – | `<Entity> Action Create` | `pe-7s-plus` | Save |
| `editActions` | Edit | `false` | – | `true` / `90%` | same group | `<Entity> Can Edit` | `<Entity> Action Update` | `pe-7s-pen` | Save |
| `editActions` | View | `false` | **`false`** | – | same group | – | – | `pe-7s-look` | **Back** |
| `editActions` | Submit | **`true`** | – | – | – | `<Entity> Can Submit` | `<Entity> Action Submit` | `pe-7s-upload` | Submit |
| `editActions` | Approve | **`true`** | – | – | – | `<Entity> Can Approve` | `<Entity> Action Approve` | `pe-7s-check` | Approve |
| `editActions` | Return for correction | **`true`** | – | – | – | `<Entity> Can Reject` | `<Entity> Action Reject` | `pe-7s-close-circle` | Return for correction |
| `editActions` | Reverse | **`true`** | – | – | – | `<Entity> Can Reverse` | `<Entity> Action Reverse` | `pe-7s-back` | Reverse |
| `editActions` | Close | **`true`** | – | – | – | `<Entity> Can Reverse` | `<Entity> Action Close` | `pe-7s-power` | Close |
| `editActions` | Delete | **`true`** | – | – | – | `<Entity> Can Edit` | `<Entity> Action Delete` | `pe-7s-trash` | Delete |
| `editActions` | Print | **`true`** | – | – | – | – | `Send <Entity> PDF` | `pe-7s-print` | Print |

Read the shape, not the verbs:

* **Everything that touches one record lives in `editActions`.** Only the bare Create is a `createActions`
  breadcrumb button — 218/345, 187/214, 83/108, 35/42 of the four projects' actions are `editActions`.
* **Every state transition is a `direct:true` action with an `onBeforeCompleteRuleIdentifier` and no form.**
  289 of 709 actions are direct; **not one** of them lacks a complete rule.
* **Predicate reuse is deliberate**: Delete reuses `Can Edit` (delete only while DRAFT); Close reuses
  `Can Reverse` (both need an approved record plus approver rights). Two verbs, one predicate, one truth.
* **Naming convention**: predicate `"<Entity> Can <Verb>"`, execution rule `"<Entity> Action <Verb>"`. It makes a
  200-rule project greppable and makes a missing pair obvious at a glance.

```json
// crud.table.plugin → properties.model.stringValue → editActions.actions[] — a state transition
{ "id": "<uuid>",
  "localizedNames":       { "en_US": "Approve",  "<loc2>": "…", "<loc3>": "…" },
  "localizedButtonNames": { "en_US": "Approve",  "<loc2>": "…", "<loc3>": "…" },
  "direct": true,
  "predicateIdentifier": "<PREDICATE: Document Can Approve>",
  "onBeforeCompleteRuleIdentifier": "<EXECUTION: Document Action Approve>",
  "icon": "pe-7s-check" }
```

### 4.2 Direct vs form — the three legal combinations

| the action… | shape |
|---|---|
| collects input from the user | `direct:false` + `formGroupIdentifier` + `onBeforeCompleteRuleIdentifier` (the persist rule) |
| only changes state / emits a document | `direct:true` + `onBeforeCompleteRuleIdentifier`, **no** `formGroupIdentifier` |
| only shows the record | `direct:false` + `submitForm:false` + `formGroupIdentifier`, **no** complete rule, button label **Back**/**Close** |

The library warns about `direct:false` + `submitForm:false` + `onBeforeCompleteRuleIdentifier` — a button that
navigates back and does nothing. **Zero occurrences in 709 actions**; all 30 `submitForm:false` actions are
genuine read-only drill-downs with no complete rule. The warning is right and the deliveries obey it.

### 4.3 `formInModal` — used by two of four, always identically

88 actions set `formInModal:true`, and **every single one sets `modalWidth:"90%"`**. B and C put Create *and*
Edit in the modal and leave **View on the page route** — the drill-down wants the breadcrumb and the page's
surrounding content; the editor wants the list to stay visible behind it. Nothing else varies. If you use it:
`{"formInModal": true, "modalWidth": "90%"}` on Create/Edit, off for View.

### 4.4 Labels and icons (corrects [06](../06-form-groups-and-mapping.md))

`localizedButtonNames` is a **copy** of `localizedNames` except for five deliberate pairs that recur across
projects — this is a UX convention worth stating, not just "the submit label":

| action name | button label | count |
|---|---|---|
| View | **Back** | 27 |
| Open | **Close** | 2 |
| Edit / Edit <Entity> | **Save** | 21 |
| Add / Create <Entity> | **Save** / **Add** | 102 |
| Export | **Run** | 19 |

Icon vocabulary across 709 actions — [06-form-groups-and-mapping.md](../06-form-groups-and-mapping.md)'s list omits more than half of these
(`pe-7s-edit`, `pe-7s-look`, `pe-7s-close-circle`, `pe-7s-cloud-download`, `pe-7s-print`, `pe-7s-back`,
`pe-7s-power`, `pe-7s-shield`, `pe-7s-lock`, `pe-7s-clock`, `pe-7s-shuffle`, `pe-7s-less`, `pe-7s-play`,
`pe-7s-up-arrow`):

```
pe-7s-plus 146   pe-7s-trash 127   pe-7s-edit 123   pe-7s-pen 61    pe-7s-play 36
pe-7s-check 35   pe-7s-look 30     pe-7s-close-circle 25            pe-7s-cloud-download 19
pe-7s-print 16   pe-7s-back 14     pe-7s-up-arrow 13                pe-7s-power 8
pe-7s-close 6    pe-7s-upload 4    pe-7s-less 4     pe-7s-mail 4    pe-7s-shuffle 2
pe-7s-shield 2   pe-7s-lock 2      pe-7s-refresh 2  pe-7s-clock 2   pe-7s-copy-file 2
```

Semantic map three projects agree on: `pe-7s-plus` create · `pe-7s-pen`/`pe-7s-edit` edit · `pe-7s-trash` delete ·
`pe-7s-look` **view/open (read-only)** · `pe-7s-check` approve · `pe-7s-close-circle` reject · `pe-7s-back`
reverse · `pe-7s-power` close · `pe-7s-upload` submit · `pe-7s-print` print · `pe-7s-cloud-download` export.

### 4.5 ⛔ The unfinished-action anti-pattern — 62 live instances

A carries **72 action entries (62 distinct ids across 35 CRUDs) with no `localizedNames`**, of which **61 also
have no `onBeforeCompleteRuleIdentifier`**:

```json
{ "id": "<uuid>", "icon": "pe-7s-edit", "formGroupIdentifier": "<uuid>", "direct": false }
```

```json
{ "id": "<uuid>", "name": "Edit <Entity>",     // ← legacy flat key, DROPPED by the deserializer
  "icon": "pe-7s-edit", "formGroupIdentifier": "<uuid>", "direct": false }
```

At runtime both render as a **blank menu entry** that opens a form whose Save **writes nothing**. Import,
`coverage` and `crud verify` are all green. Two rules follow:

* the CRUD `ActionDto` has **no `name` field** — only `localizedNames` / `localizedButtonNames`
  (`Map<locale,String>`). A flat `name` is silently discarded.
* a non-direct Create/Edit **must** carry `onBeforeCompleteRuleIdentifier` pointing at the rule that calls
  `context.<ctx>.<alias>.service.create/update(...)`. **There is no built-in persist.**

### 4.6 List sub-form actions use the other `ActionDto` — `direct` is a STRING (corrects [02](../02-form-controls-reference.md))

22 of 22 List controls in three projects are byte-identical. [02-form-controls-reference.md](../02-form-controls-reference.md) §7/§8 describes
the mechanism but not the template; this is the template:

```json
{ "scope":"CRUD", "contextIdentifier":"<ctx>", "crudAlias":"<parentAlias>",
  "fieldExpression":"lines", "filterKey":"lines", "name":"Lines",
  "dataClass":"java.util.List",
  "localizedHeaderLabel": {"en_US":"Document lines","<loc2>":"…","<loc3>":"…"},
  "headerIcon":"pe-7s-list",
  "createNewActions": { "actions": [
    { "id":"A", "localizedNames":{"en_US":"Add line"}, "localizedButtonNames":{"en_US":"Save"},
      "direct":"off", "icon":"pe-7s-plus", "submitForm":true } ], "errors": [] },
  "userActions": { "actions": [
    { "id":"E", "localizedNames":{"en_US":"Edit line"},   "localizedButtonNames":{"en_US":"Save"},
      "direct":"off", "icon":"pe-7s-pen", "submitForm":true },
    { "id":"D", "localizedNames":{"en_US":"Delete line"}, "localizedButtonNames":{"en_US":"Delete"},
      "direct":"on",  "icon":"pe-7s-trash" } ], "errors": [] },
  "subforms": [ { "id":"A", "localizedNames":{"en_US":"Line"} } ],
  "formIdByActionId": { "A":"A", "E":"A" },
  "columnSettings": [ { "id":"…","localizedNames":{…},"fieldExpression":"item.code",
                        "dataClass":"java.lang.String","scope":"CRUD",
                        "contextIdentifier":"<ctx>","crudAlias":"<parentAlias>" }, … ] }
```

plus **one** child node `dynaform.list.item.plugin` whose `identifier` is **`A`** (the Create action's id) — Edit
folds onto the same sub-form through `formIdByActionId`. `direct` here is the string `"off"`/`"on"`, not a
boolean, because a List uses the UserTask-shaped action DTO. Delete is the only `"on"` entry and carries no
sub-form. `allowAddDelete`, `maxItems` and `refreshOnCompleteByActionId` are never set in 22/22.

One inconsistency to settle: C writes the **child** CRUD alias into `columnSettings[].crudAlias`; B and D write
the **parent** alias, the same one the List control itself carries. **B/D are right** — the List's value is a
field of the parent row.

### 4.7 The worklist read-only combination — undocumented anywhere

Process-table `globalActions` use the UserTask DTO and combine flags the library never shows together:

```json
{ "id":"<uuid>", "localizedNames":{"en_US":"Open the subject"},
  "localizedButtonNames":{"en_US":"Open"},
  "predicateIdentifier":"<uuid>", "direct":"off", "completeUserTask":"off",
  "formGroupIdentifier":"<uuid>", "formInModal":true, "modalWidth":"90%",
  "submitForm":false, "onBeforeUserTaskCompleteRuleIdentifier":"<uuid>",
  "icon":"pe-7s-look" }
```

`direct:"off"` + `submitForm:false` + `completeUserTask:"off"` = **read the record in a dialog over the worklist
without claiming or completing the task.** That is the worklist counterpart of the table's View/Back action.
See [05-crud-tree-and-process-table.md](../05-crud-tree-and-process-table.md) and [07-workflows-and-tasks.md](../07-workflows-and-tasks.md) for the surrounding DTO.

---

## 5. Action predicates — the real gate

### 5.1 Three idioms; compose, don't copy-paste

One action carries exactly **one** `predicateIdentifier` — you cannot AND two predicates in JSON, so role and
state must be composed inside Groovy. The three shapes in production:

**(a) Role-only** — C, 106 of 108 actions carry a predicate; 41 distinct rules, four of which cover 52 uses:

```groovy
// name: "Is <Role>" — reused by 11 actions
return service.security.hasAnyRoleGroup("<Role>", "<Supervising role>", "System Administrator")
```

`hasAnyRoleGroup` is fail-closed, so an unauthenticated caller gets `false` without a guard. **Always include the
administrator role group in the list**, or your own admin loses the button too.

**(b) State-only** — B, 93 uses over 79 predicates:

```groovy
// "<Entity> Can Edit"
return context.<ctx>.<alias>.data.get()?.status == 'DRAFT'
```

**(c) State + delegated authorization** — the state list is inline, the authorization is one shared rule:

```groovy
// "<Entity> Can Reverse"
def st = context.<ctx>.<alias>.data.get()?.status
if (st != 'APPROVED' && st != '<intermediate state>' && st != 'CLOSED') { return false }
return service.rule("<shared approver predicate>") as boolean
```

The delegated rule answers only *"may this person approve?"* and is deliberately state-free:

```groovy
// shared: role + four-eyes
if (!service.security.hasAnyRoleGroup("<Approver role>") &&
    !service.security.hasAnyRoleGroup("<Administrator role>")) { return false }

def READERS = [                       // find whichever record is in scope
  ['<alias1>', { context.<ctx>.<alias1>.data.get() }],
  ['<alias2>', { context.<ctx>.<alias2>.data.get() }]
  // … one entry per entity that shares this rule …
]
def doc = null
for (rd in READERS) {
  try { def d = rd[1](); if (d != null && d.status != null) { doc = d; break } }
  catch (Throwable ignored) { }
}
if (doc == null || doc.status == null) { return false }

def mail   = (service.security.user()?.email ?: '').toString().toLowerCase()
def author = ((doc.createdBy ?: doc.submittedBy ?: '').toString()).toLowerCase()
if (!mail.isEmpty() && mail == author && !service.security.hasAnyRoleGroup("<Administrator role>")) {
    return false            // nobody approves what they wrote
}
return true
```

### 5.2 ⛔ A shared predicate must not assert state that only some callers imply

The project's own comment records the bug: an earlier version of that shared rule also asserted
`status == 'SUBMITTED'`, which made `Can Reverse` (which needs APPROVED/`<intermediate>`/CLOSED) permanently
false — **every Reverse button in the application disappeared, on eleven entities at once, with no error
anywhere.** Nothing in `validate`, import or `crud verify` can see it. *The state belongs to the caller; the role
and the four-eyes rule belong to the shared rule.*

### 5.3 Separation of duties as a visibility predicate — the shape to copy

```groovy
if (!service.security.hasAnyRoleGroup("<Deciding role>", "System Administrator")) { return false }
def row = null
try { row = context.<ctx>.<decisionAlias>.data.get() } catch (Throwable ignored) { }
if (!(row instanceof Map) || row.id == null) { return false }
def me = (service.security.user()?.email ?: '').toLowerCase()
if (me.isEmpty()) { return false }
if (((row.proposedBy ?: '') as String).toLowerCase() == me) { return false }   // not the proposer
def parent = null
try { parent = service.crud.<caseAlias>.get((row.<caseFk> ?: row.<caseObj>?.id) as String) }
catch (Throwable ignored) { }
def owner = ((parent?.ownerEmail ?: '') as String).toLowerCase()
if (!owner.isEmpty() && owner == me) { return false }                          // not the record owner
return ((row.state ?: '') as String) == 'PROPOSED'
```

**role gate → row present → identity gate(s) → state gate**, each with its own early `return false`, every
context read inside `try { } catch (Throwable ignored) { }`.

### 5.4 The row is not always in the context — the `_rid` resolver

D wraps every row lookup in a three-way resolver and caches the result back into the context. This is what makes
one predicate usable from a table row action **and** from a workflow user task — 9 of D's 16 forms are reachable
both ways:

```groovy
def _rid = { alias ->
    def row = null
    try { row = context.<ctx>."${alias}".data.get() } catch (Throwable ignored) { }
    def rid = (row instanceof Map) ? row.id : null
    if (rid == null) { rid = attrs?.get('_crudEntityId')?.asText() }      // table/worklist path
    if (rid == null) { rid = context.data.getAttr(alias + 'Id') }         // workflow path
    if (rid == null) { return null }
    context.data.setAttr(alias + 'Id', rid.toString())                    // publish for the next rule
    return rid.toString()
}
def row = null
try { row = context.<ctx>.<alias>.data.get() } catch (Throwable ignored) { }
if (!(row instanceof Map) || row.id == null || row.status == null) {
    def _id = _rid('<alias>')
    row = (_id == null) ? null : service.crud.<alias>.get(_id)            // reload it properly
}
if (row == null || row.id == null) { return false }
return (row.status == 'DRAFT')
```

`attrs.get('_crudEntityId')` — the row id the platform threads on the table path — appears in **no library doc**
and is used by every predicate and rule in that project. Add it to your resolver.

### 5.5 Layering: what runs where, and what each failure looks like

| gate | mechanism | fails how |
|---|---|---|
| button visible? | action `predicateIdentifier` | silently absent |
| page reachable? | form/landing page `roleAccess.roleGroupAccessors` | access denied |
| form submittable? | `forms[].validators` (`addFieldError`/`addError`) | red messages on the form |
| write allowed? | the EXECUTION rule's own guards | `throw new RuntimeException(...)` → a wrapped red banner |

### 5.6 Duplicate the precondition inside the execution rule

```groovy
def doc = context.<ctx>.<alias>.data.get()
if (doc == null || doc.id == null) { throw new RuntimeException("Select a record first") }
if (doc.status != 'SUBMITTED') {
    throw new RuntimeException("Only a SUBMITTED record can be approved (current: " + doc.status + ")")
}
def actor = (service.security.user()?.email ?: '').toString()
service.crud.<alias>.approve([ id: doc.id.toString(), actor: actor ])
return doc.id.toString()
```

The predicate is UX; the throw is the backstop for a scheduler, a rule-to-rule call, or a user who kept the URL.
Note the wording: a thrown message reaches the user wrapped in two uuids and two layers of platform text, so keep
it self-contained — and where a validation slot exists (§6.3), report the same precondition there too, because a
`crud.table` action has no `validationRuleIdentifiers` of its own.

---

## 6. Validation — where it lives, and where the message actually renders

### 6.1 Mandatory is 99 % of it, and it is two artefacts, not one

356 controls are mandatory. **Every one of them** is `alwaysMandatory:true` on the control **and** a red asterisk
in the slot's HTML — 1:1 in all four projects. The settings half:

```json
{ "scope": "CRUD", "contextIdentifier": "<ctx>", "crudAlias": "<alias>",
  "fieldExpression": "referenceNo", "filterKey": "referenceNo",
  "name": "Reference no.",
  "dataClass": "java.lang.String",
  "alwaysMandatory": true,
  "mandatoryValidationMessages": { "en_US": "Reference no. is required", "<loc2>": "…", "<loc3>": "…" },
  "eventComponentMappings": [], "conditionalValidations": [] }
```

The content half — the slot's `html` property, identical to the character in all four projects:

```html
<div class="mb-3">
  <div class="d-flex align-items-center justify-content-between">
    <span class="d-inline-flex align-items-center">
      <plugin id="lbl_gen_slot_<batch>_<r>_<c>" name="nct.label.plugin"></plugin>
      <span class="red ms-1">*</span>
    </span>
  </div>
  <plugin id="fld_gen_slot_<batch>_<r>_<c>" name="dynaform.form.text.field.plugin"></plugin>
</div>
```

A ships `mandatoryValidationMessages:{}` on all 114 of its mandatory controls and its users get the platform's
generic `"{fieldName} is required"`. The other three always write the full locale map. **Write the messages; a
generic one in a localized app is a visible defect.**

`mandatoryPredicateIdentifier` (conditional mandatory) is used **zero** times in 2 119 controls. When a field is
required only in one situation, the deliveries fork the form (§2.4) or check it in a form-level validator (§6.3).
[25-form-settings-validation-and-events.md](../25-form-settings-validation-and-events.md)'s routing table offers it as the natural answer for
"conditionally required" — it works, but nobody chose it, and the fork gives the approver a screen that is
*visibly* different rather than a field that mysteriously turns red.

### 6.2 `conditionalValidations` is essentially unused — and both live spellings differ from the doc

Three entries in 2 119 controls. [25](../25-form-settings-validation-and-events.md) §2 says this is "**most** of the validation in a project — do it here,
not in a form-level rule". **The evidence contradicts that flatly**: 3 control-level entries against 39
attachments of 18 form-level `VALIDATION_RULE`s. The catalog is not wrong, it is mis-weighted; almost every real
check turns out to need the row or another table, which a self-contained template predicate cannot reach cleanly.
Lead with `alwaysMandatory` + form-level `validators`, and keep the templates for genuinely single-field format
checks. When you do use one, the inversion still holds: **predicate-true = INVALID**.

The one dialog-generated entry carries the auto-name and the CRUD preamble — and a defect worth knowing: **the
generator copies the default-locale message into every locale**, so that project shipped English placeholder text
to its other two languages:

```json
{ "predicateIdentifier": "<uuid>", "severity": "ERROR",
  "validationMessages": { "en_US": "Value does not match the required pattern",
                          "<loc2>": "Value does not match the required pattern",
                          "<loc3>": "Value does not match the required pattern" } }
```
```groovy
// rule name: "<ctxAlias> · <crudAlias> · email · Match regex — email, URL, UUID, … (^[A-Za-z0-9._%+-]+@[A-…)"
def v = context.<ctx>.<alias>.data.getField('email', java.lang.String.class)
return v == null || !v.toString().matches('^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')
```

**Both hand-written entries ignore the generated preamble** and instead try `v`, then fall back to the read that
matches how the form was opened — which is what makes them survive a dual-reach form:

```groovy
// on a GLOBAL control of a form reachable from BOTH a table action and a worklist task
def raw = null
try { raw = v } catch (Throwable ignored) { }
if (raw == null) { try { raw = context.data.getAttr('deferDays') } catch (Throwable ignored) { } }
if (raw == null || raw.toString().trim() == '') { return false }   // empty is not this rule's problem
def n = null
try { n = new java.math.BigDecimal(raw.toString().trim()) } catch (Exception ignored) { return true }
return (n < 1.0G || n > 14.0G)
```

```groovy
// on a control INSIDE a list-item sub-form — the fallback read is context.currentData
def raw = null
try { raw = v } catch (Throwable ignored) { }
if (raw == null) {
    try { raw = context.currentData?.getField('approvedQty', java.math.BigDecimal.class) }
    catch (Throwable ignored) { }
}
if (raw == null || raw.toString().trim() == '') { return false }
def n = null
try { n = new java.math.BigDecimal(raw.toString().trim()) } catch (Exception ignored) { return true }
return (n < 0.0G)
```

[02-form-controls-reference.md](../02-form-controls-reference.md) mentions `context.currentData.get()` in passing;
**`context.currentData?.getField('<field>', <Type>.class)` is what a real list-item validation predicate uses.**
Both live entries spell `"severity": "ERROR"` explicitly even though it is the default, and both ship a real
three-locale `validationMessages`. Copy that.

### 6.3 Form-level `validators` — the mechanism that carries the real business rules

18 `VALIDATION_RULE`s, 39 attachments over 228 forms. Four techniques, all reusable.

**(a) One cross-cutting validator attached to every form of a family.** B attaches the same "the period is
closed" rule to **14** forms. `validators` is per-form but the rule is generic, so it discovers which record is
in scope with the same READERS probe as §5.1, and reads its threshold from a settings CRUD rather than a
constant:

```groovy
def ROWS = { res -> (res instanceof Map) ? (res.content ?: []) : (res ?: []) }
def SETTING = { String key ->
    for (s in ROWS(service.crud.appSetting.find([settingKey: key, rowsInPage: 20, pageNumber: 0]))) {
        if ((s.settingKey ?: '').toString() == key) { return s.settingValue }
    }
    return null
}
def READERS = [ ['<alias1>', { context.<ctx>.<alias1>.data.get() }],
                ['<alias2>', { context.<ctx>.<alias2>.data.get() }] ]
def doc = null
for (rd in READERS) {
    try { def d = rd[1](); if (d != null && d.id != null) { doc = d; break } } catch (Throwable ignored) { }
}
if (doc == null || doc.documentDate == null) { return }
def lockRaw = SETTING('period.closed.until')
if (lockRaw == null || lockRaw.toString().trim().isEmpty()) { return }
def lock = java.time.LocalDate.parse(lockRaw.toString().trim().substring(0, 10))
def dd   = java.time.LocalDate.parse(doc.documentDate.toString().substring(0, 10))
if (!dd.isAfter(lock)) {
    def m = "The period is closed through " + lock.toString()
    addFieldError("<Document date control name>", m)
    addError(m)
}
```

**(b) Always call `addFieldError` AND `addError` with the same text.** B does this **16 times out of 16**. The
field error marks the control; the global error is what actually renders the sentence. A field error whose name
matches nothing is dropped silently, leaving a bare "Validation failed".

**(c) ⛔ The field name is `settings.name`, matched exactly — and one project got it wrong on all four targets.**

| the rule says | the control's `settings.name` actually is |
|---|---|
| `addFieldError("Reference Note", …)` | `Reference note` |
| `addFieldError("Outcome Conclusion", …)` | `Outcome conclusion` |
| `addFieldError("Assessment Method", …)` | `Assessment method` |
| `addFieldError("Outcome Justification", …)` | **`Justification`** |

Four of four vanish silently; three of the five checks in that project's completeness gate therefore produce no
visible message at all. Two consequences: **title-casing the label inside the rule is the classic way to lose the
message**, and `settings.name` is **not localized** — in a project whose UI language is not English the field
names inside the Groovy are non-English strings, because that is what the control's `name` holds. Pick the
language of `settings.name` once per project and keep every rule in that language.

**(d) Localize a computed message with a map inside the rule.** `addError` takes a plain string and there is no
localization mechanism for a computed message — the deliveries hand-roll one, and this idiom belongs in
[25-form-settings-validation-and-events.md](../25-form-settings-validation-and-events.md) §4.2:

```groovy
def loc = service.global.locale.getKey() ?: 'en_US'
def MSG = [
  incomplete: [ en_US: 'The checklist is incomplete — complete every line.', '<loc2>': '…', '<loc3>': '…' ],
  short:      [ en_US: 'The justification must be at least %d characters.',  '<loc2>': '…', '<loc3>': '…' ] ]
def M = { k -> (MSG[k][loc] ?: MSG[k]['en_US']) }
…
validation.addFieldError("<control name>", String.format(M('short'), minLen))
```

**(e) Warnings at form level are used; warnings at control level are not.** `severity:"WARNING"` inside
`conditionalValidations`: **0 occurrences**. `addFieldWarning` / `validation.addWarning` inside a form-level
validator: used exactly where the message must name real numbers or real references —

```groovy
// tolerance breach: advisory, never blocking, and it names the numbers
if (total != null && cap != null && cap > 0.0G && (total - cap).abs() > 0.5G) {
    addFieldWarning('<Total control name>',
        'The approved total ' + total + ' deviates from the selected ' + cap +
        ' unit by ' + (total - cap).abs() + ' (tolerance 0.5).')
}
if (total != null && total <= 0.0G) {
    addFieldError('<Total control name>', 'The approved total must be greater than zero.')
}
```

```groovy
// duplicate detection: a warning that lists the offending references
validation.addWarning('This partner already has an open case within the last ' + hours +
                      ' hours: ' + refs + '. Attach the new information to it instead of creating a duplicate.')
```

**Rule of thumb the four projects converge on:** constant sentence about one field → `alwaysMandatory` +
`mandatoryValidationMessages`. Message must **name a number, a reference or a row** → a form-level
`VALIDATION_RULE`. The declarative catalog sits unused in between.

### 6.4 Both `validation.addFieldError(...)` and bare `addFieldError(...)` resolve (corrects [25](../25-form-settings-validation-and-events.md), [02](../02-form-controls-reference.md))

| project | `validation.`-qualified calls | bare calls |
|---|---|---|
| A | 1 | 0 |
| B | 15 | **32** (16 × `addFieldError` + 16 × `addError`) |
| C | 11 | 0 |
| D | 0 | **2** |

B mixes both spellings inside the same rule set, and those rules gate 14 live forms. [25](../25-form-settings-validation-and-events.md) and [02](../02-form-controls-reference.md) present
only the `validation.*` surface. Prefer the qualified form for readability; **do not "fix" an existing bare call
— it is not broken.**

### 6.5 `actionValidators` and `hiddenConfigs`: 0 / 228 (corrects [25](../25-form-settings-validation-and-events.md) §4.1)

Neither field is populated on a single form in four projects. For `actionValidators` the library already says it
does not run at CRUD-form submit; the evidence agrees by omission — leave it `[]` and put per-action validation on
the workflow user-task action's `validationRuleIdentifiers` ([07-workflows-and-tasks.md](../07-workflows-and-tasks.md)).

**Hidden Content Configuration is the bigger surprise** — a whole documented panel, the routing table's answer to
"hide/show a whole block by state", and **nobody used it**. What four teams did instead:

* the **approval twin** (§2.4) — a second form with the block *locked* rather than hidden;
* `alwaysProhibited:true` on the fields that must not be touched (338 controls);
* an action `predicateIdentifier` so the state that would hide the block never reaches that form.

Demote it: reach for Hidden Content only when a block must vanish **within one form as the user types**. For
state-dependent presentation, fork the form.

---

## 7. Control-level config as actually shipped

### 7.1 `alwaysProhibited` is how a form shows computed and workflow-owned data

338 controls. The pattern is consistent: the form shows **every** interesting column and locks the ones the user
does not own — the state field, audit stamps (`approvedBy`, `approvedAt`), snapshots, and every number a rule
computes (`amountNet`, `varianceQty`, `unitCostFinal`, `currentQty`).

The most valuable single instance is the **state field**, repeated on every lifecycle form in B:

```json
{ "scope":"CRUD", "contextIdentifier":"<ctx>", "crudAlias":"<alias>",
  "fieldExpression":"status", "filterKey":"status", "name":"Status",
  "dataClass":"java.lang.String",
  "searchEnabled": false, "ruleIdentifier":"<status choices rule>",
  "key":"code", "displayName":"label", "showNav": false,
  "alwaysProhibited": true,
  "defaultValueEnabled": true, "defaultValueStatic": true, "defaultValue": "DRAFT",
  "mandatoryValidationMessages": {}, "eventComponentMappings": [], "conditionalValidations": [] }
```

…paired with a help bubble in the same slot that names the buttons which move it:

```json
{ "alwaysVisible": true, "showMessageOn": "CLICK", "needToBeSaved": false,
  "localizedMap": { "message": {
     "en_US": "Status is not typed in — it is the record's history. It moves with the list buttons: «Submit», «Approve», «Return for correction», «Close», «Reverse».",
     "<loc2>": "…", "<loc3>": "…" } } }
```

That one slot removes the single most common support question on a lifecycle screen.

### 7.2 Defaults are static, and they serve three purposes only

146 controls, `defaultValueStatic:true` on every one, `defaultValueRuleIdentifier` on none:

| what | shape | also `alwaysProhibited`? |
|---|---|---|
| the initial state | `status: "DRAFT"` ×20, `status: "ACTIVE"` ×8, `<x>Status: "PENDING"` | yes |
| a unit code the user may change | `unit: "<U1>"` ×14, `unit: "<U2>"` ×3, `<code>: "<C1>"` ×4 | no |
| a zero-seed or placeholder for a computed field | `qtyReturned: "0"`, `varianceQty: "0"`, `amountNet: "0"`, `revisionNo: "0"`, `<snapshot>: "—"` | yes |

### 7.3 Unconfigured controls are live inputs bound to nothing

A has **7** field-control nodes whose entire settings blob is

```json
{"mandatoryValidationMessages": {}, "eventComponentMappings": [], "conditionalValidations": []}
```

— no `scope`, no `fieldExpression`, no `dataClass`. They render an input that accepts typing and discards it.
**A control node with no `scope` + `fieldExpression` is an export error, not a stub.** Grep for it before packing.

### 7.4 `between` is the date-range FILTER control (corrects [02](../02-form-controls-reference.md))

All 21 uses are date pickers on **filter** forms; never on a data-entry form. Name it as such rather than as an
exotic range mode:

```json
{ "name":"Document date", "between": true, "dataClass":"java.time.LocalDate",
  "scope":"GLOBAL", "filterKey":"documentDateFrom",
  "betweenMapping": { "scope":"GLOBAL", "contextIdentifier": null, "crudAlias": null,
                      "fieldExpression":"documentDateTo", "jsonNodeExpression": null,
                      "jsonNodeValueType": null, "filterKey":"documentDateTo" } }
```

Related: [02](../02-form-controls-reference.md)'s 63-key settings union is **field-controls-only**. `dynaform.filter.submit.button.plugin`
carries `buttonName` and `waitComponentIdentifier` on 95 live nodes — legitimately documented in
[14a-plugin-config-reference.md](../14a-plugin-config-reference.md), but outside the union [02](../02-form-controls-reference.md) calls "the only keys that can appear in
`settings.stringValue`". Scope that sentence to bound field controls.

---

## 8. Field events — two shapes, and the one that scales

23 mappings across four projects; **all** are `eventName:"change"`, **all** on a dropdown or autocomplete.

### 8.1 Whole-form repaint — 21 of 23 (corrects [25](../25-form-settings-validation-and-events.md) §3)

```json
{ "eventName": "change",
  "componentIdentifier": "<uniqueIdentifier of the form's `form.parsis` nct.parsis.plugin>",
  "executionRuleIdentifiers": [] }
```

The trigger is the parent picker; the target is the form's own `form.parsis`; **no rules at all**. Refreshing
`form.parsis` re-runs *every* dependent choices rule on the form in one ajax round trip, so you never have to
record which slot depends on which — and because a mapping is single-target, this is one mapping instead of one
per dependent field. 20 of the 21 sit on controls inside a **list-item sub-form**, where the item's own
`form.parsis` is the natural target.

[25](../25-form-settings-validation-and-events.md) recommends pointing the mapping at the *dependent field's slot* (`gen_slot_*`). That is strictly worse
for anything with more than one dependent field, and it silently rots when someone adds a third dependent field
later. **Target `form.parsis`; use the per-slot target only when the form is large enough that repainting it is
visibly slow.** Remember `componentIdentifier` is the node's `uniqueIdentifier`, not its `identifier` (the
`form.parsis` node's `identifier` is literally the string `form.parsis`).

### 8.2 Prefill from a picked record — 2 of 23

Same event plus one EXECUTION rule. Whole-header + child-lines prefill:

```groovy
// executionRuleIdentifiers[0] on the "<parent document> no." picker; target = form.parsis
def cur = null; def row = null
// BOTH steps throw: `.data` when the context has no entry for this crud, `.get()` when it is empty.
try { cur = context.<ctx>.<alias>.data } catch (Throwable ignored) { }
if (cur == null) { return null }
try { row = cur.get() } catch (Throwable ignored) { }
if (row == null) { return null }
def parent = row.<parentRef>
def pid = (parent instanceof Map) ? parent['id']?.toString() : null
if (pid == null) { return null }
def src = service.crud.<parentAlias>.get(pid)
if (src == null) { return null }
def lines = service.crud.<parentAlias>.findLines([<fk>: pid]) ?: []
def out = []
lines.eachWithIndex { l, i ->
    out << [ lineNumber: (i + 1),
             item: [id: l.itemId?.toString(), code: l.itemCode, name: l.itemName],
             qtyA: l.qty, qtyB: l.qty, qtyC: 0, unitValue: l.unitValue ]
}
row.lines = out                       // the List control fills because the CHILD ROWS are in the value
row.<cost1> = src.<cost1>
row.<cost2> = src.<cost2>
if (src.partner instanceof Map) { row.partner = src.partner }
cur.put(row)
return out.size()
```

Single-field prefill, targeting only the dependent slot:

```groovy
def d = context.<ctx>.<alias>.data
try {
    def lineId = d.getField('<ref>.id', java.lang.String.class)
    if (lineId != null && !lineId.toString().trim().isEmpty()) {
        def src = service.crud.<alias>.<lookupMethod>([<param>: lineId.toString()])
        def qty = (src instanceof Map) ? src['qtyOrdered'] : null
        if (qty != null) { d.setField('plannedQty', qty) }
    }
} catch (Throwable ignored) { }
return null
```

Both wrap every context touch in `try/catch` and return early: **a prefill rule that throws aborts the refresh**
and the user sees nothing change.

---

## 9. Scope — and the one place `GLOBAL` is right

| controls under a `dynaform.form.plugin` | CRUD | GLOBAL | none |
|---|---|---|---|
| A | 1 113 | 0 | 7 (broken stubs) |
| B | 627 | 0 | 0 |
| C | 195 | 39 | 0 |
| D | 104 | 34 | 0 |

### 9.1 `GLOBAL` on a CRUD form is legitimate for exactly one thing: the dual-reach echo band

**All 39** of C's GLOBAL controls are `alwaysProhibited:true`, and **all 39** sit on forms reachable from *both* a
table row action *and* a workflow user task. They are a read-only header band echoing the parent record —
`caseNo`, `state`, `priority`, `refNo`, `dueAt`:

```json
{ "scope":"GLOBAL", "contextIdentifier":"<ctx>",
  "fieldExpression":"caseNo", "filterKey":"caseNo",
  "dataClass":"java.lang.String", "alwaysProhibited": true,
  "mandatoryValidationMessages": {}, "eventComponentMappings": [], "conditionalValidations": [],
  "name":"Case reference" }
```

**Why it reads correctly on both paths:** name the echo field's `fieldExpression` identically to (a) the CRUD
column and (b) the attr the workflow's bind rule publishes. On the table path the platform force-binds the control
to the table's CRUD, so `caseNo` resolves to the row's `caseNo` column; on the task path `scope:GLOBAL` reads
`attrs['caseNo']`. One control, two correct readings. Every echoed `fieldExpression` in that project is a real
column of the parent CRUD — verify that when you copy the trick. D's 20 prohibited GLOBAL echoes use
workflow-only names, which is correct there because that form is worklist-only.

### 9.2 ⛔ `GLOBAL` + `context.data.getAttr()` on a table-only form silently writes nothing

D has one form reachable **only** from a table row action whose four inputs are `scope:GLOBAL` and whose action
rule reads them as attrs:

```groovy
def a = context.data.getAttr("qtyA")        // ← null on the table path
def b = context.data.getAttr("qtyB")
service.crud.<alias>.setQuantities([
    qty_a: (a == null ? '' : a.toString()),
    qty_b: (b == null ? '' : b.toString()), id: rowId])
```

On a form opened from a `crud.table` action the binding is forced to CRUD, so `getAttr` returns null, the CRUD
method receives `''`, a COALESCE-style update keeps the old value — **and the toast says success.** The same
project's other seven forms escape this only because they are *also* reachable from a user task.

**Rule:** a value the user types on a form a table action can open must be `scope:"CRUD"` and must be read from
the row. If the form is genuinely dual-reach and you need attrs, read **both**, attrs first:

```groovy
def val = null
try { val = context.data.getAttr('<field>') } catch (Throwable ignored) { }
if (val == null) { try { val = context.<ctx>.<alias>.data.get()?.<field> } catch (Throwable ignored) { } }
```

---

## 10. Drafts, multi-language, labels

**`allowDrafts:true` on 5 of 228 forms**, and the choice is coherent: all five are the *entry* form of a long
multi-section record — never a decision form, never a reference-data form, never an approval twin. Four of the
five also carry form-level validators, i.e. exactly the forms where a submit can be refused and the user needs
somewhere to park the work. Leave it `null` everywhere else.

**`multiLanguage`** is `true` on 194 of 228 forms; the one project that sets it `false` (30 forms) is the
single-language one. `localized:true` on individual controls is rare (55 controls) and only on reference-data
name/description fields whose CRUD carries the `localized` ObjectNode column ([20-localization.md](../20-localization.md)).

What `multiLanguage` does **not** cover: the **field label** is localized by the label node, not by the control —

```json
{ "className": "form-label", "tagName": "label", "styleName": "", "tagProperties": "",
  "text": { "stringValue": null,
            "localizedStringValue": { "en_US": "Document no.", "<loc2>": "…", "<loc3>": "…" } } }
```

`settings.name` stays a single string in one language and is the key `addFieldError` matches (§6.3). The label
and the name are two different strings for two different audiences; keep both.

---

## 11. Layout conventions of a form that reads well

### 11.1 The grid — two columns by default

| rows with… | A | B | C | D |
|---|---|---|---|---|
| **2** columns | 102 | 34 | 50 | 6 |
| 1 column | 0 | 19 | 24 | 4 |
| 3–4 columns | 8 | 16 | 0 | 8 |

Every 1-column row in B and C holds a textarea, a List control or a full-width block. 4-column rows appear only
on short reference-data forms. Row node (`nct.html.plugin`), `html` property:

```html
<div class="row">
  <div class="col-md-6"><plugin id="gen_col1_<batch>" name="nct.parsis.plugin"></plugin></div>
  <div class="col-md-6"><plugin id="gen_col2_<batch>" name="nct.parsis.plugin"></plugin></div>
</div>
```

One project wraps that in an extra `<div class="container">`; both render. Columns are bare `nct.parsis.plugin`
nodes with empty `className`/`styleName`/`tagProperties`.

### 11.2 The slot, in its three shipped variants

```html
<!-- plain -->
<div class="mb-3"><plugin id="lbl_…"></plugin><plugin id="fld_…"></plugin></div>

<!-- mandatory (red asterisk) -->
<div class="mb-3"><div class="d-flex align-items-center justify-content-between">
  <span class="d-inline-flex align-items-center"><plugin id="lbl_…"></plugin><span class="red ms-1">*</span></span>
</div><plugin id="fld_…"></plugin></div>

<!-- with a help bubble (asterisk, if any, goes inside the same span) -->
<div class="mb-3"><div class="d-flex align-items-center justify-content-between">
  <span class="d-inline-flex align-items-center"><plugin id="lbl_…"></plugin></span>
  <plugin id="help_…" name="nct.help.plugin"></plugin>
</div><plugin id="fld_…"></plugin></div>
```

`nct.help.plugin` is used on 104 slots in two projects and earns it: the help texts that exist are the ones that
answer *"why can't I type here"* and *"what happens if I leave this blank"*.

```json
{ "alwaysVisible": true, "showMessageOn": "CLICK", "needToBeSaved": false,
  "localizedMap": { "message": { "en_US": "Leave empty and the number is generated automatically.",
                                 "<loc2>": "…", "<loc3>": "…" } } }
```

A List control gets a slot of its own with **no label node** — its `localizedHeaderLabel` + `headerIcon` draw the
header.

### 11.3 Node naming — the only hard constraint is internal consistency

Two spellings ship and both work, because the only real constraint is that the slot HTML's `<plugin id="…">`
matches the child node's `identifier`:

* generated: `gen_row_<hex>_<r>` / `gen_col<N>_<hex>_<r>` / `gen_slot_<hex>_<r>_<c>_<i>` / `lbl_|help_|fld_` +
  the slot name;
* hand-built: a **human batch tag** — `gen_row_<entity><nn>`, `gen_slot_<entity><nn>_<c>_<i>`, with a suffix
  letter for a variant form (`…01L` for the list-item sub-form, `…R1` for a twin).

The human tag makes an export diff readable and makes "which slot is this?" answerable without opening the page.
Prefer it when you generate the export yourself. See [24-html-component-studio.md](../24-html-component-studio.md) and
[24d-html-component-structure.md](../24d-html-component-structure.md) for the surrounding node grammar.

### 11.4 Field order the projects converge on

**identity** (record no., usually read-only with a help bubble saying it is auto-generated) → **state**
(read-only dropdown, §7.1) → **date** → **partner / parent reference** (the dropdown that carries the
`change` event) → **the editable body** → **computed totals** (all `alwaysProhibited`) → **audit stamps**
(`approvedBy`, `approvedAt`, prohibited) → **free-text note** in a 1-column row → the **List** of lines in its
own full-width row, last.

---

## 12. Corrections to the library, itemized

| # | Doc | What it says | What four deliveries show | Which side is right |
|---|---|---|---|---|
| 1 | [06](../06-form-groups-and-mapping.md) | fork with `return service.actionId == '<uuid>'` | 0 uses; all 6 live forks route on row state + role | **deliveries** — the uuid link is fragile and unbound on workflow paths (§2.2) |
| 2 | [06](../06-form-groups-and-mapping.md) | page-level `formModeIdentifier` is mandatory | 141/142 forms in one project carry it on the plugin node only, and render | **both** — it must exist somewhere in the subtree; write page **and** plugin (§1.4) |
| 3 | [06](../06-form-groups-and-mapping.md) | `placeFormsNextToLanding` describes the tree | one project ships `false` with 103/142 siblings and runs | **deliveries** — the flag is advisory once pages exist (§1.5) |
| 4 | [06](../06-form-groups-and-mapping.md) | 16 action icons | 23 distinct icons in 709 actions; half the live set is missing from the list | **deliveries** — extend the list (§4.4) |
| 5 | [06](../06-form-groups-and-mapping.md) | `localizedButtonNames` = the submit label | five recurring name→button pairs (View→Back, Open→Close, Edit→Save, Add→Save, Export→Run) | **deliveries** — state the convention (§4.4) |
| 6 | [25](../25-form-settings-validation-and-events.md) §2 | `conditionalValidations` is "most of the validation in a project" | 3 entries in 2 119 controls vs 39 form-validator attachments | **deliveries** — lead with `alwaysMandatory` + `validators` (§6.2) |
| 7 | [25](../25-form-settings-validation-and-events.md) §4.1 | Hidden Content Configuration is the answer to "hide a block by state" | 0 uses in 228 forms; all four teams forked the form + `alwaysProhibited` | **deliveries** — demote it to "vanish while typing" (§6.5) |
| 8 | [25](../25-form-settings-validation-and-events.md) §4.2, [02](../02-form-controls-reference.md) | only `validation.addFieldError(...)` etc. | 34 bare `addFieldError`/`addError`/`addFieldWarning` calls run in production | **both work** — prefer qualified, never "fix" a bare call (§6.4) |
| 9 | [25](../25-form-settings-validation-and-events.md) §4.2 | (no guidance) | a computed message has no localization mechanism; projects hand-roll `service.global.locale.getKey()` + a locale map | **gap** — document the idiom (§6.3d) |
| 10 | [25](../25-form-settings-validation-and-events.md) §3 | point a `change` mapping at the dependent field's `gen_slot_*` | 21 of 23 mappings target the form's `form.parsis` and carry no rules | **deliveries** for >1 dependent field (§8.1) |
| 11 | [25](../25-form-settings-validation-and-events.md) §5 | `mandatoryPredicateIdentifier` for "conditionally required" | 0 uses; conditional requirement is solved by forking the form | **deliveries** (§6.1) |
| 12 | [25](../25-form-settings-validation-and-events.md) §2 | the template dialog writes localized messages | the dialog copies the default-locale text into every locale | **gap** — a shipped defect, fix the map by hand (§6.2) |
| 13 | [02](../02-form-controls-reference.md) | 63-key union = "the only keys in `settings.stringValue`" | `dynaform.filter.submit.button.plugin` carries `buttonName` + `waitComponentIdentifier` on 95 nodes | **scope the sentence** to bound field controls (§7.4) |
| 14 | [02](../02-form-controls-reference.md) | `context.currentData.get()` mentioned in passing | list-item validation predicates use `context.currentData?.getField('<f>', <T>.class)` | **deliveries** — document the `getField` form (§6.2) |
| 15 | [02](../02-form-controls-reference.md) | `between` = a range mode | all 21 uses are the date-range **filter** control (`<x>From`/`<x>To`, `scope:GLOBAL`) | **deliveries** — name it (§7.4) |
| 16 | [02](../02-form-controls-reference.md) §7–8 | the List mechanism | 22/22 live Lists are one byte-identical template (`direct` as `"off"`/`"on"`, `formIdByActionId` folding Edit onto Create, one child node named by the Create action id) | **deliveries** — ship the template (§4.6) |
| 17 | — | (undocumented) | `attrs.get('_crudEntityId')` is the row id on the table path; used by every rule in one project | **gap** (§5.4) |
| 18 | — | (undocumented) | worklist `direct:"off"` + `submitForm:false` + `completeUserTask:"off"` = read in a modal without claiming the task | **gap** (§4.7) |
| 19 | — | (undocumented) | unknown keys inside `properties.model` survive the export (generator provenance keys, a `__children__` blob in a control's settings). The deserializer drops them, but they persist in the JSON — and are lost the moment a human opens that settings panel | **never build tooling that depends on them** |

[25](../25-form-settings-validation-and-events.md)'s warning that a mandatory field's message can be masked by the before-complete rule's exception is
confirmed by practice: every delivery's execution rule re-throws the precondition (§5.6), so write the rule's
message for a developer and the user-facing wording in `mandatoryValidationMessages`.

---

## 13. Checklist for a new entity's forms and actions

1. **Group + pages.** One `formGroups[]` entry per entity; `placeFormsNextToLanding:true`;
   `formGroupsPageIdentifier:null`; its **own** landing page (never a shared/baseline one); landing and form page
   both `layout:"Main"`, both children of the CRUD-table page, both with a unique top-level `alias`; plugins
   inside `html.plugin "Layout"` → content `nct.parsis.plugin`.
2. **Form.** `forms[]` with `contentIdentifier` = the form page, `multiLanguage` per project, `validators:[]`,
   `actionValidators:[]`, `hiddenConfigs:[]`, `allowDrafts:null` unless it is a long entry record. Copy the group
   **verbatim** into `forms[].formGroup`. Write `formModeIdentifier` on the page **and** on the form plugin.
3. **Mapping.** One pair `True → form`. If an approver sees a different screen, add the twin and put its
   `state+role` pair **above** the `True` pair.
4. **Controls.** All `scope:"CRUD"` with the table's `contextIdentifier` + `crudAlias`; a concrete `dataClass` on
   every field; `alwaysMandatory` + a full `mandatoryValidationMessages` map **and** the red `*` in the slot HTML
   for every required field; `alwaysProhibited:true` on the state field, every computed number and every audit
   stamp; static `defaultValue` for the initial state and the unit codes; a help bubble on anything auto-generated or
   workflow-owned.
5. **Layout.** 2-column rows; textarea / List / totals in their own 1-column rows; human batch tag in node names.
6. **Actions.** `createActions`: Create only. `editActions`: Edit, View (`submitForm:false`, button **Back**),
   one `direct:true` action per state transition, then Delete, then Print/Export. Every non-direct Create/Edit and
   every direct action needs `onBeforeCompleteRuleIdentifier`. Every action needs `localizedNames` — never a flat
   `name`.
7. **Gates.** `predicateIdentifier` named `<Entity> Can <Verb>`, delegating the role/four-eyes half to one shared
   `service.rule("…")` predicate that asserts **no** state. Add `roleAccess.roleGroupAccessors` on the form and
   landing pages if the separation is real, and trim the boilerplate `accessors`. Re-throw the same precondition
   inside the execution rule.
8. **Cross-field checks.** One `VALIDATION_RULE` in `forms[].validators`; call
   `addFieldError("<exact settings.name>", m)` **and** `addError(m)` for every finding; build the locale map
   yourself; use `addFieldWarning` for advisory tolerances.
9. **Cascades.** If a picker drives other fields, one `eventComponentMappings` entry
   `{"eventName":"change","componentIdentifier":"<uniqueIdentifier of form.parsis>","executionRuleIdentifiers":[]}`
   — add a prefill rule only when you are loading a whole record.

### 13.1 Before packing — grep for the eleven failures that stay green

```bash
# forms with an empty mapping, and forms[] whose embedded group copy drifted
jq -r '.forms[] | select((.formGroup.predicateFormMapping.mapping|length) == 0)
       | "EMPTY MAPPING  " + .identifier' rep-objects.json
jq -r '.formGroups[] as $g | .forms[] | select(.formGroup.identifier == $g.identifier)
       | select((.formGroup|tojson) != ($g|tojson)) | "DRIFTED COPY   " + .identifier' rep-objects.json

# actions: no localizedNames, or non-direct with no complete rule, or submitForm:false WITH one
jq -r '.. | objects | select(has("model")) | .model.stringValue // empty' branches.json \
 | jq -s 'map(fromjson?) | map(.createActions.actions[]?, .editActions.actions[]?, .globalActions.actions[]?)
          | map(select((has("localizedNames")|not)
                    or ((.direct != true) and (.onBeforeCompleteRuleIdentifier == null))
                    or ((.submitForm == false) and (.onBeforeCompleteRuleIdentifier != null))))'
```

then by eye, over the same flattened settings:

* controls with no `scope` / no `fieldExpression` (unbound live inputs, §7.3);
* `scope:"GLOBAL"` on a form that a table action can open (§9.2);
* every `addFieldError("X", …)` target that matches no control's `settings.name`, exactly, including case (§6.3c);
* every `formGroups[].contentPageIdentifier` that points at a shared or baseline page (§1.3);
* any rule mentioning `service.actionId` (§2.2) and any `predicateIdentifier: ""` (§2.3);
* `alwaysMandatory:true` controls whose slot HTML has no `<span class="red ms-1">*</span>` (§6.1).

---

## Cross-links

* Form groups, `FormDto`, the ACTION model, the landing dispatch: [06-form-groups-and-mapping.md](../06-form-groups-and-mapping.md)
* Control settings schema and the key union: [02-form-controls-reference.md](../02-form-controls-reference.md);
  generated slots and the asterisk: [03-generate-fields-from-crud.md](../03-generate-fields-from-crud.md)
* The two authoring panels, templates, events, drafts: [25-form-settings-validation-and-events.md](../25-form-settings-validation-and-events.md)
* Table/tree/worklist actions and their DTOs: [04-crud-table-plugin.md](../04-crud-table-plugin.md), [05-crud-tree-and-process-table.md](../05-crud-tree-and-process-table.md)
* Rule types, context grammar, the `validation.*` surface: [08-groovy-rules-and-context.md](../08-groovy-rules-and-context.md),
  [16-groovy-service-api.md](../16-groovy-service-api.md); CRUD service methods: [11-business-logic-dynamic-crud.md](../11-business-logic-dynamic-crud.md)
* User-task actions and `validationRuleIdentifiers`: [07-workflows-and-tasks.md](../07-workflows-and-tasks.md)
* Page ACLs and the disjunction trap: the security layers in [19-build-decision-procedure.md](../19-build-decision-procedure.md)
* Localization of labels, messages and `localized:true` columns: [20-localization.md](../20-localization.md)
