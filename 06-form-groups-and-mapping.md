# Form Groups & form mapping

> ⛔ **`identifier` or `uniqueIdentifier`?** They are different ids with different scopes and swapping them fails silently. The rule, the source that decides it and the measured evidence: [01 — `identifier` vs `uniqueIdentifier`](01-content-model-and-pages.md#-identifier-vs-uniqueidentifier--read-this-before-you-reference-a-node).

> 📐 **Field evidence — form groups and predicate mapping in production:** [04-forms-actions-validation.md](references/04-forms-actions-validation.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / when to use

**Form group** (`formGroup`) — a named container of forms that has a **landing page**
(CMS `siteMapPage` with the `dynaform.form.groups.landingplugin` plugin) and a **routing table**
`predicateFormMapping`. When a user clicks a CRUD/Process action (Create / Edit / any custom),
the table/tree/process plugin does not open a form directly — it navigates to the group's landing page with
parameters (`?group=<fgId>&settingsName=<...>&actionId=<uuid>&crudId=<id>`). The landing plugin runs the
predicates from `predicateFormMapping` **in array order** and opens the **first** form whose predicate
returned `true`. This way a single "Edit" button can lead to different forms depending on the row's state / on which
action exactly was clicked.

**Form** (`form`) — a wrapper around a CMS page (`siteMapPage` with `dynaform.form.plugin`) that stores
`contentIdentifier` (the form page), `formGroup` (a back-reference, an **embedded copy** of the group DTO),
contexts, validators, `hiddenConfigs`, `allowDrafts`, `multiLanguage`. The configuration of the form controls themselves
lives in the content tree of the form page — see [02-form-controls-reference.md](02-form-controls-reference.md)
and [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md).

> ⚠️ **Choices-rule contract (dropdown/autocomplete controls on these forms).** A CRUD-backed
> dropdown/autocomplete control's `ruleIdentifier` EXECUTION rule MUST end by converting rows to option pairs —
> `return service.global.conversion.toSelectOptions(list,"<key>","<display>")` (localized display column →
> `toSelectOptionsLocalized`; autocomplete → `toAutoCompleteOptions`), **never** a raw `find`/`findAll` entity list
> (which renders "No results found" and hides Show Nav). Searchable dropdowns use the `acFindBy<X>Like` pipeline, and
> never call `findAll` with a PARTIAL param map (untyped-`$1`) — use `findAll([:])`. Full recipe:
> [02-form-controls-reference.md](02-form-controls-reference.md) §4a.

Use a form group when:
- you need a data entry/editing screen for a CRUD entity (dynamic CRUD — see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md));
- you need **Create and Edit of one entity to lead to the same form** (the typical case — one
  `True` predicate → one form; the form itself distinguishes create/edit by the presence of `crudId`);
- you need a **form fork** (e.g. "regular row → form A", "row in status X → form B"; or
  "action = Adjust → form A", "action = View → form B");
- you need a **process start form** or a user-task form (ProcessTable → workflow predicates — see below and
  [07-workflows-and-tasks.md](07-workflows-and-tasks.md)).

> **🔧 Tooling.** For these objects, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of manually
> editing JSON: `formgroup add --name "<Crud> Forms" --context <ctx>`,
> `form add --name <s> --formgroup <fg> --context <ctx>`, `rule add --type PREDICATE` (mapping predicate),
> `show formGroup <id>`. Full index and rules — [`tools/README.md`](tools/README.md); before
> reimport — `mrjun.py validate`.

> 🛑 **CRITICAL — `formgroup add`/`form add` leave the mapping EMPTY; there is NO command to add a pair.**
> `cmd_formgroup_add` writes `predicateFormMapping:{mapping:[]}` (`rep_cmds.py`), and `cmd_form_add`
> embeds **that same empty snapshot** as `forms[].formGroup` (`rep_cmds.py`, `"formGroup": fg`). An empty mapping →
> the landing opens nothing ("No layout/form"). After `formgroup add` + `form add`, **hand-add the pair**
> `{ "predicateIdentifier": "<TRUE_UUID | fork pred>", "formIdentifier": "<FORM_UUID>" }` to **BOTH**:
> `formGroups[<id>].predicateFormMapping.mapping` AND the embedded
> `forms[<id>].formGroup.predicateFormMapping.mapping` — keep the two copies **identical** (see the sync
> Gotcha below). Every working group carries at least one mapping pair, most of them reusing a single shared
> `True` predicate. ⚠️ **On a greenfield (empty-baseline) build there are ZERO rules** — the id
> `2566c158-...` quoted below belongs to a sample project, not to yours; you must **AUTHOR your own `True` predicate first**
> (`ruleType=PREDICATE`, `ruleScriptStr:"return true"`) and reference **its** identifier (see "Common step 0 — the
> `True` predicate" below).

> 🏗️ **The full "Create Default Actions" page structure (do this, not `--parent root`).** `formgroup add`/`form add`
> create only the rep-objects; the platform's *Create Default Actions* also builds the **CMS pages**, and you must too:
> 1. `page add --parent <CRUD TABLE page> --name "<Crud> Forms" --auth` — the **landing page** is a CHILD OF THE
>    TABLE page (NOT root). ⛔ **Never create form/landing pages with `--parent root`** — a form page at the site
>    root (`/<realm>/<alias>/form-…`) is the classic bug.
> 2. `node add --parent <that landing page> --plugin dynaform.form.groups.landingplugin` — the landing plugin
>    (a NO-CONFIG plugin: only `className`/`styleName`/`tagProperties`). The group is resolved *reverse*, by
>    `contentPageIdentifier` == the landing page's identifier.
> 3. `formgroup set --id <group> --content-page <landing identifier> --no-list` — point the group at its landing
>    and null `formGroupsPageIdentifier` (the auto-gen convention). `formgroup set` **mirrors the change into every
>    `forms[].formGroup` embedded copy** automatically.
> 4. Create each form page and `page mv --id <form page> --to-parent <table page>` so, with
>    `placeFormsNextToLanding=true`, the form page is a **SIBLING of the landing** (both children of the table page).
>    `page mv` preserves identifiers/`formModeIdentifier`, so `forms[].contentIdentifier` still resolves.
>
> **Layouts:** the **LANDING** page uses layout **`Main`**. The **FORM** page: current practice is **`Main`**
> for the form page too; older projects used **`Form`**. **Both render** — emit **`Main`** (the current
> standard; see the ⭐ canonical recipe under "How to construct").
>
> ⛔ **THE #1 hand-authoring trap — the ROUTABLE alias is the page's TOP-LEVEL `alias` field, NOT
> `properties.alias.stringValue`.** The platform routes a page by `ContentDomain.getAlias()` = the top-level
> `"alias"` JSON key (`ContentServiceImpl.calculatePageUrl` walks alias+ancestor path); `page add` sets that
> top-level field and leaves `properties.alias.stringValue` null. If you hand-build a form/landing page (e.g. via a
> generator's `mknode`) and set only `properties.alias.stringValue`, or clone the system `Landing` (which carries
> top-level `alias="landing"`) without overriding it, the page ends up with **NO / a COLLIDING top-level alias** →
> `calculatePageUrl` yields a broken URL that re-resolves to the landing → `FormGroupLandingPlugin.navigateToFormIfNeed`
> re-fires → **ERR_TOO_MANY_REDIRECTS** on `/…/landing?group=…` (import succeeds; the loop only shows when a clerk
> clicks Create/Edit). Every form page + landing page needs a **present, UNIQUE, top-level** `alias` (e.g.
> `<entity>-form`, `<entity>-form-landing`). `validate` now **ERRORs** on a form/landing page with a missing or
> colliding top-level alias, WARNs on a `dynaform.form.plugin` page parented at root, and WARNs on a group still
> pointing at the shared system `Landing`.

> ⚠️ **Where FormGroup/Form actually live.** The `formGroup`/`form` objects themselves are rep-objects (persisted in
> the nct-dynaform DB, exported to `rep-objects.json`). `branches.json` holds ONLY CMS nodes:
> the landing plugin, the form plugin, the controls. Do not look for the group/form JSON inside `branches.json` — there are only
> `pluginName` nodes there, bound to rep-objects via `?group=` (landing) and the `formModeIdentifier`
> property (form plugin).

### Static vs dynamic — does not affect these objects

The form group mechanism is **identical** for a static (compiled-bean) and a dynamic (definition-driven)
project: `formGroup`, `form`, landing node, mapping — all the same. The only difference is that
`service.crud.<alias>...` inside predicates
resolves either to a compiled `@Crud` bean (static) or to a definition from `dynamic-cruds.json`
(dynamic; see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)).

### Two naming models — auto-gen vs manual (important for dynamic)

The **Create Default Actions** button in the CRUD-table/-tree settings generates a group `"<CrudName> Forms"`,
a form `"<CrudName> Form"` and a single mapping pair `True → form`, with `placeFormsNextToLanding=true` and
`formGroupsPageIdentifier=null` (`CrudDefaultActionsService`, see below). Hand-built projects routinely differ
on every one of those points — and both shapes import and run:

| | Auto-gen (Create Default Actions) | Style 1 — hand-built, shared landing | Style 2 — hand-built, landing per group |
|---|---|---|---|
| Group name | `"<CrudName> Forms"` | `"<X> Form Group"` | free-form |
| `placeFormsNextToLanding` | `true` | `false` (form is a **child** of the landing) | mixed — chosen per group |
| `formGroupsPageIdentifier` | `null` | the shared admin "Form Groups" page | `null` |
| `multiLanguage` (per form) | `null` | `true` (localized projects) | `null` |

> ⚠️ **These are free CHOICES, not conventions — there is no "native" shape to copy.** The two hand-built
> styles above are **opposite** on almost every axis: `placeFormsNextToLanding` all-false vs per-group,
> `formGroupsPageIdentifier` the shared admin page vs null, `multiLanguage` true vs null, one shared landing vs
> a landing per group (see B1). Pick whichever fits your URL/localization needs; both import and run. **One thing
> is NOT free:** a group's `contentPageIdentifier` must never be the baseline system `Landing` — it is role-gated,
> so end-user Create/Edit is access-denied there and `validate` WARNs. Emit a landing per group.

**Don't overfit to `"<CrudName> Forms"`.** The naming convention is only for the auto-gen path; when building an
export manually the group/form name is free-form. Both flag variants are given below (Recipe A =
`placeFormsNextToLanding=true`, Recipe B = `false`).

## Export shape

Both objects live in `rep-objects.json` (see [00-export-format-and-import.md](00-export-format-and-import.md)):
`rep-objects.json.formGroups[]` and `rep-objects.json.forms[]`. The landing page, the form page and the group
list page are content-tree nodes in `branches.json[].rootContent` (see
[01-content-model-and-pages.md](01-content-model-and-pages.md)).

### `formGroups[]` — JSON schema

```
{
  "message": null, "errors": null, "id": null,       // AbstractSecuredDto housekeeping — always null in the export
  "realmName": "<realm>", "clientName": "<client>",  // multi-tenant keys
  "identifier": "<uuid>",                            // stable group id (referenced from FormDto.formGroup, mapping, from the URL ?group=)
  "creationTime": "<iso>", "modificationTime": "<iso>",
  "name": "<string>",                                // display name; auto-gen convention "<CrudName> Forms", hand-built often "<X> Form Group"
  "contextIdentifiers": ["<contextUuid>", ...],      // group contexts (see 08-groovy-rules-and-context.md)
  "contentPageIdentifier": "<pageIdentifier>|null",  // ContentDomain.identifier of the landing page (dynaform.form.groups.landingplugin)
  "formGroupsPageIdentifier": "<pageIdentifier>|null",// group-LIST page (dynaform.form.groups.plugin) — usually the shared admin "Form Groups"
  "placeFormsNextToLanding": true|false,             // where form pages are created: child of landing (false, default) / sibling of landing (true)
  "predicateFormMapping": {
    "mapping": [
      { "predicateIdentifier": "<ruleUuid>", "formIdentifier": "<formUuid>" }
      // array order = priority; NO order field; NO forms field on the group
    ]
  }
}
```

> **No `order` and `forms` fields.** `PredicateFormPair` contains ONLY `predicateIdentifier` +
> `formIdentifier` (`PredicateFormMappingDto.java`) — ordering follows the position in the array, not
> a numeric `order`. `FormGroupDto` has NO `forms` field: forms reference the group via
> `FormDto.formGroup`, and on the list page they resolve by `FormFilter.formGroupIdentifier`
> (`FormGroupLandingPlugin.java`).

### Worked example — auto-gen (`formGroups[0]` of a manufacturing project)

```json
{
  "message": null,
  "errors": null,
  "id": null,
  "realmName": "<realm>",
  "clientName": "<client>",
  "identifier": "7a4ccde7-0a44-4518-9aed-3343a090b97d",
  "creationTime": "2026-07-06T21:52:54.711659Z",
  "modificationTime": "2026-07-06T21:52:54.711667Z",
  "name": "Bill of Materials Forms",
  "contextIdentifiers": [
    "77cd568d-75b0-48e7-8fcc-d760b3a06219"
  ],
  "contentPageIdentifier": "8c62998c-15db-4157-a1de-ed6b74505d58",
  "formGroupsPageIdentifier": null,
  "placeFormsNextToLanding": true,
  "predicateFormMapping": {
    "mapping": [
      {
        "predicateIdentifier": "2566c158-01b1-4cc9-bf49-73bff0d4bab9",
        "formIdentifier": "2c18b1c2-4016-486d-a0ca-990164624782"
      }
    ]
  }
}
```

Here `2566c158-...` is the shared `True` predicate (`return true`), `2c18b1c2-...` is the form
`"Bill of Materials Form"`. This is the standard result of **Create Default Actions**: one form, always
shown (Create and Edit both lead to this same one).

### Worked example — hand-built (`"1. Declarations Form Group"` of a customs project)

The shared-landing style: `placeFormsNextToLanding=false` and a **non-empty** `formGroupsPageIdentifier`
pointing at the shared admin "Form Groups" page. ⚠️ Read it as *what an older export looks like*, not as a
template: its `contentPageIdentifier` is the role-gated baseline `Landing` (see the ⛔ under B1) — copy the
field layout, not that UUID.

```json
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "1c4e58ce-47dd-41d3-827c-cc4276797f9f",
  "creationTime": "2026-05-16T12:49:38.289099Z",
  "modificationTime": "2026-05-25T16:45:59.387180Z",
  "name": "1. Declarations Form Group",
  "contextIdentifiers": ["871f974f-e775-401a-adfc-e822110f3b99"],
  "contentPageIdentifier": "ec99a5a0-3605-4843-94ad-cf7fb4deb5a5",
  "formGroupsPageIdentifier": "e714bbd4-c6c4-49d6-a698-5608e3113317",
  "placeFormsNextToLanding": false,
  "predicateFormMapping": {
    "mapping": [
      { "predicateIdentifier": "cf1fc408-1904-4bbb-91c7-1cf383279e9e",
        "formIdentifier": "461c3f09-c66d-419b-a810-a76ff3c9750c" }
    ]
  }
}
```

> **`formGroupsPageIdentifier` = the shared admin "Form Groups".** Here `e714bbd4-c6c4-49d6-a698-5608e3113317`
> is the same `identifier` as the admin "Form Groups" page (alias `"form"`) shipped in the **empty baseline**
> (its `branches.json` carries `{name:"Form Groups", alias:"form", identifier:"e714bbd4-..."}`). That is, in
> Step 2 you do not need to create the group list page — it already exists in the empty project; just put its
> `identifier` into each group's `formGroupsPageIdentifier` (or leave it `null` — then the group won't
> show up in the admin list, but the landing still works).

> **A single landing node CAN technically serve many groups — but do not build that way.** Dispatch goes by the
> URL parameter `?group=`, so one landing page (one `dynaform.form.groups.landingplugin`) resolves any number of
> groups; that is how the admin Form Groups console works, and it is why the baseline ships exactly one
> `Landing`. For end-user Create/Edit it is the wrong shape: the shared landing you would reuse is the
> **role-gated** baseline `Landing` (access-denied for an ordinary clerk — `validate` WARNs on it), and a
> hand-made shared one gives every entity the same landing URL. Emit **one landing per group**, under that
> group's CRUD-table page — the ⭐ canonical recipe.

### `forms[]` — JSON schema

```
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "<uuid>",                            // stable form id (referenced from mapping.formIdentifier)
  "creationTime": "<iso>", "modificationTime": "<iso>",
  "formGroup": { <embedded FormGroupDto — a FULL copy of the group, WITH all housekeeping fields> },
  "contentIdentifier": "<pageIdentifier>",           // ContentDomain.identifier of the form page (siteMapPage with dynaform.form.plugin)
  "name": "<string>",                                // auto-gen "<CrudName> Form"
  "contextIdentifiers": ["<contextUuid>", ...],
  "validators": ["<ruleUuid>", ...],                 // form-level VALIDATION_RULE identifiers (usually [])
  "actionValidators": [ <FormActionValidator>, ... ],// validators bound to a specific action (usually [])
  "hiddenConfigs": [ <HiddenContentConfig>, ... ],   // predicate-based hiding/validation of content (usually [])
  "multiLanguage": true|false|null,                  // Boolean; null → false; in dynamic usually true
  "allowDrafts": true|false|null                     // Boolean; null → false; "Drafts" button in breadcrumbs
}
```

### Worked example (`forms[0]`) — the embedded `formGroup` shown IN FULL

> ⚠️ The embedded `formGroup` inside `FormDto` is a **full copy** of the group DTO, including housekeeping fields
> `message/errors/id/realmName/clientName/creationTime/modificationTime` — the key set is
> identical to the object in `formGroups[]`. Do not trim them when building manually.

```json
{
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "identifier": "6e28f9ac-e096-4c1d-be60-3a627effbac1",
  "creationTime": "2026-07-06T21:52:54.862569Z",
  "modificationTime": "2026-07-06T21:52:54.862575Z",
  "formGroup": {
    "message": null, "errors": null, "id": null,
    "realmName": "<realm>", "clientName": "<client>",
    "identifier": "b2446e3e-3788-4b7f-bca8-808520b89b6c",
    "creationTime": "2026-07-06T21:52:54.7...Z",
    "modificationTime": "2026-07-06T21:52:54.7...Z",
    "name": "Plant Forms",
    "contextIdentifiers": ["77cd568d-75b0-48e7-8fcc-d760b3a06219"],
    "contentPageIdentifier": "ec6512db-7cc3-4ad0-8f89-b7e98ada26f2",
    "formGroupsPageIdentifier": null,
    "placeFormsNextToLanding": true,
    "predicateFormMapping": {
      "mapping": [
        { "predicateIdentifier": "2566c158-01b1-4cc9-bf49-73bff0d4bab9",
          "formIdentifier": "6e28f9ac-e096-4c1d-be60-3a627effbac1" }
      ]
    }
  },
  "contentIdentifier": "44f7152c-189a-4729-9eb2-2ea734f7794c",
  "name": "Plant Form",
  "contextIdentifiers": ["77cd568d-75b0-48e7-8fcc-d760b3a06219"],
  "validators": [],
  "actionValidators": [],
  "hiddenConfigs": [],
  "multiLanguage": null,
  "allowDrafts": null
}
```

The `mapping.formIdentifier` inside the embedded `formGroup` already points at **this** form
(`6e28f9ac-...`) — this is how the two-way link closes. When building manually keep both copies
(in `forms[].formGroup` and in `formGroups[]`) consistent.

### Populated example — `multiLanguage`, `hiddenConfigs`, `validators`

These three are empty on most forms: `multiLanguage:true` on every form of a localized project, `allowDrafts`
and `validators` on the handful of forms that actually need them. Populated shapes:

```json
// hiddenConfigs (a "Stock Transfer Form" that hides a block by predicate) — HiddenContentConfig[]:
"hiddenConfigs": [
  { "predicateIdentifier": "0a09acad-8b77-4f7e-a4f7-050e3afd45a1",
    "contentIdentifiers": ["7efad281-bae1-40f5-b8f8-eaca40b67052"] }
]

// multiLanguage populated (typical form of a localized project):
"multiLanguage": true,
"allowDrafts": null,
"validators": []
```

`HiddenContentConfig` = `{predicateIdentifier: String, contentIdentifiers: List<String>}`
(`HiddenContentConfig.java`). When the predicate `predicateIdentifier` returns `true`, the bound
`contentIdentifiers` are hidden/validated on the form (this is the form-level analogue of per-control-hidden from
[02-form-controls-reference.md](02-form-controls-reference.md)).

### Landing node in the content tree (branches.json)

⛔ **The clone trap — a landing that lost its plugin renders BLANK.** Because the plugin carries no settings,
it is easy to treat the landing page as "just the Layout" and build a per-entity landing by CLONING the shared
`Landing` page. The clone keeps the chrome (header / breadcrumb / left-nav / footer) and the content
`nct.parsis.plugin` — and **drops the `dynaform.form.groups.landingplugin` that lived inside that parsis**,
because nothing references it by id: the page resolves it by position, exactly like the `siteMapPageParsis`
anchor.

Every offline gate stays green afterwards — the page exists, has a unique top-level alias, has a Layout, has a
parsis — and the failure only shows at runtime:

* the URL returns **200** and the chrome draws, with an **empty content area**;
* every crud-table **Edit** action that routes through the landing is a dead end;
* every **workflow user task** whose `userActions[].formGroupIdentifier` points at this group cannot be
  opened, so the process is UNCOMPLETABLE even though it started correctly.

Fix — the plugin needs no properties, it reads `?group=` from the URL:

```
mrjun.py node add --project <dir> --parent <landing page's content parsis> \
                  --plugin dynaform.form.groups.landingplugin
```

`validate` flags it offline (`_check_form_group_landing_plugin`), per form group.


The landing plugin **stores no group settings** — all configuration is in `formGroups[]`. The
`dynaform.form.groups.landingplugin` node has only generic CMS slots (`className`/`styleName`/`tagProperties`,
all empty — there is no `formGroupIdentifier` property), and the binding to the group goes **via
the URL parameter `?group=`**:

```json
{
  "id": "ecd27997-83a7-412d-a3c0-0c0044402783",
  "identifier": "00498512-c77d-4e3e-a4d1-82c2e87e2632",
  "uniqueIdentifier": "53c81ce8-c6cb-4425-97a2-7192add5b41c",
  "name": "Form group landing",
  "pluginName": "dynaform.form.groups.landingplugin",
  "order": 0, "active": true, "includedInParsis": false, "virtualContent": false,
  "properties": {
    "className":  { "key": "className",  "propertyType": "STRING", "stringValue": "", "required": false, "hidden": false, "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel", "arguments": {}, "localizedStringValue": {} },
    "styleName":  { "key": "styleName",  "propertyType": "STRING", "stringValue": "", "...": "..." },
    "tagProperties": { "key": "tagProperties", "propertyType": "STRING", "stringValue": "", "...": "..." }
  }
}
```

The landing plugin sits inside the `parsis` of its landing page. The landing page is a `siteMapPage`,
whose `identifier` = `formGroup.contentPageIdentifier`. A real landing page carries **8 property slots**
(not just `layout`): `Redirect`, `additionalCss`, `group`, `isParsis`, `layout`, `metaTags`,
`pageDescription`, `pageTitle` — the full siteMapPage scaffolding;
see [01-content-model-and-pages.md](01-content-model-and-pages.md) for the exact schema of each slot. Example
("Bill of Materials Forms", `identifier` = `8c62998c-...`; only the significant fields are shown below):

```json
{
  "name": "Bill of Materials Forms",
  "identifier": "8c62998c-15db-4157-a1de-ed6b74505d58",
  "alias": "bill-of-materials-forms",
  "pluginName": "siteMapPage",
  "properties": {
    "layout": { "stringValue": "Main" },
    "Redirect": { "...": "..." }, "additionalCss": { "...": "..." }, "group": { "...": "..." },
    "isParsis": { "...": "..." }, "metaTags": { "...": "..." },
    "pageDescription": { "...": "..." }, "pageTitle": { "...": "..." }
  },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true, "accessors": { "...": "..." } },
  "children": [ { "name": "parsis", "pluginName": "parsis.plugin", "children": [ /* ... landing plugin ... */ ] } ]
}
```

> ⚠️ **The shared-landing layout differs.** There the landing page is named `"Landing"` (alias
> `landing`) and its own parsis subtree carries **only** `dynaform.form.groups.landingplugin`
> (plus site chrome: header/footer/breadcrumb/kicker/image/html); there is **no** `dynaform.form.plugin`
> and no controls on the landing page itself. Every `dynaform.form.plugin` under that landing lives in a
> **child form page** (`siteMapPage`), not on the landing. The `FormDto` objects themselves also do **NOT** point
> at the landing page: `form.contentIdentifier != formGroup.contentPageIdentifier` on every form. Each form
> references a **separate child form page** (`placeFormsNextToLanding=false` → the form page is a child of the
> landing). Example: the form "1.1 Declarations Form" (`461c3f09-...`) has `contentIdentifier=029533b4-...` — a
> separate `siteMapPage` "1.1 Declarations Form" (alias `all-declarations`, layout `Form`,
> `formModeIdentifier=461c3f09`), a child of the landing `ec99a5a0-...`. Putting `dynaform.form.plugin` right on the
> landing page (then the form's `contentIdentifier` = landing) is a theoretically possible option (see Recipe B,
> B1), but no working project does that — keep the form on its own child page.

### The form page in the content tree

`form.contentIdentifier` points at a `siteMapPage` (layout `"Main"` in current practice; `"Form"` in
older projects — both render, emit `Main`) that has the **property `formModeIdentifier` = the form's identifier** set —
this is what links the page to the `FormDto` (set at
`FormGroupLandingPlugin.java` and `CrudDefaultActionsService.java`). Example ("Bill of Materials
Form", `identifier` = `15b6ffd4-...`, form `2c18b1c2-...`; the full set of property keys —
`Redirect, additionalCss, formModeIdentifier, group, isParsis, layout, metaTags, pageDescription, pageTitle`):

```json
{
  "name": "Bill of Materials Form",
  "identifier": "15b6ffd4-7ac9-42fa-bbcd-b682549de28f",
  "alias": "bill-of-materials-form",
  "pluginName": "siteMapPage",
  "properties": {
    "layout": { "stringValue": "Form" },
    "formModeIdentifier": { "stringValue": "2c18b1c2-4016-486d-a0ca-990164624782" }
  },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true }
}
```

Inside the page (in `parsis`) sits a `dynaform.form.plugin` node (its `properties` are generic slots +
`formModeIdentifier` + `isParsis`/`reuseItems`; the form configuration is set via `FormDto` + controls).

## Per-variant reference

### `FormGroupDto` — field by field

| name | type | meaning | required? | default | backing (`FormGroupDto.java`) |
|---|---|---|---|---|---|
| `identifier` | String (uuid) | stable group id | yes | server-generated | `AbstractSecuredDto.identifier` |
| `name` | String | display name (auto-gen `"<CrudName> Forms"`, usually manual) | yes (`RequiredTextField`) | — | |
| `contextIdentifiers` | List\<String\> | contexts; the first is the default context for predicates | no | `null`/empty | |
| `contentPageIdentifier` | String | `ContentDomain.identifier` of the landing page | no* | `null` | |
| `formGroupsPageIdentifier` | String | the group list page (`dynaform.form.groups.plugin`) — usually the shared admin "Form Groups" | no | `null` | |
| `placeFormsNextToLanding` | boolean | `false` (default) → form pages = **children** of landing; `true` → **siblings** of landing | no | `false` | |
| `predicateFormMapping` | `PredicateFormMappingDto` | predicate→form routing table | no | `{mapping:[]}` (lazy) | |

\* The "No landing page found" error (`FormGroupLandingPlugin.goLandingPage`) fires when
`FormDto.contentIdentifier` (the FORM's own page) is empty, and **not** when
`FormGroupDto.contentPageIdentifier` is empty. Still, for a working group specify both the group's landing page and
each form's page. `@EqualsAndHashCode` excludes `contextIdentifiers`
and `predicateFormMapping` — do not rely on equals to compare groups by mapping.

`predicateFormMapping.mapping[]` — `PredicateFormPair`:

| name | type | meaning | required? | default | backing |
|---|---|---|---|---|---|
| `predicateIdentifier` | String (uuid) | id of the PREDICATE rule; blank → the pair is treated as **fallback** | no | — | `PredicateFormMappingDto.PredicateFormPair.predicateIdentifier` |
| `formIdentifier` | String (uuid) | id of the form to go to; blank → the pair is skipped | yes | — | |

> **Order = position in the array.** The landing iterates `mapping[]` top to bottom and opens the **first**
> form whose predicate returned `true`. Pairs with a blank `predicateIdentifier` do NOT stop iteration — they
> are remembered as the `fallbackForm` (the **first** such one), and used ONLY if no predicate
> returned `true`, regardless of where the blank pair sits in the list (`FormGroupLandingPlugin.java`
>; likewise in the other three nav methods). Pairs with a blank `formIdentifier` are skipped
> entirely.

### `FormDto` — field by field

| name | type | meaning | required? | default | backing (`FormDto.java`) |
|---|---|---|---|---|---|
| `identifier` | String (uuid) | form id; referenced by `mapping.formIdentifier` | yes | server-generated | `AbstractSecuredDto.identifier` |
| `formGroup` | `FormGroupDto` | embedded **full** copy of the group (back-reference) | yes for forms in a group | — | |
| `contentIdentifier` | String | `ContentDomain.identifier` of the form page (`siteMapPage`, `layout:"Form"` + `formModeIdentifier`) | yes | — | |
| `name` | String | auto-gen `"<CrudName> Form"` | yes | — | |
| `contextIdentifiers` | List\<String\> | form contexts | no | empty (lazy) | |
| `validators` | List\<String\> | form-level VALIDATION_RULE identifiers | no | empty | |
| `actionValidators` | List\<FormActionValidator\> | validators bound to a specific action | no | empty | |
| `hiddenConfigs` | List\<HiddenContentConfig\> | predicate-based hiding/validation of form content | no | empty | |
| `multiLanguage` | Boolean | localized field values; `isMultiLanguage()` null-safe | no | `null`→`false` | |
| `allowDrafts` | Boolean | "Drafts" dropdown in breadcrumbs (save/resume a draft); `isAllowDrafts()` | no | `null`→`false` | |

`HiddenContentConfig` = `{predicateIdentifier: String, contentIdentifiers: List<String>}`
(`HiddenContentConfig.java`).
`FormActionValidator` = `{workflowIdentifier, workflowTaskId, actionId, validator}` — all String
(`FormActionValidator.java`). `actionValidators` is normally empty, but the field belongs to `FormDto`
and should be present (at least `[]`).

> **Runtime + decision guidance for these form-level settings → [25-form-settings-validation-and-events.md](25-form-settings-validation-and-events.md) §4.**
> Hidden Content (predicate-true = **HIDDEN**; `contentIdentifiers` are node **`uniqueIdentifier`**s; a CREATE-mode
> predicate reading `…data.get()` works via a seeded empty `CrudDataDto`); **Global** (`validators`) vs
> **Action-Based** (`actionValidators`) validation — the `validation.*` API and, critically,
> `addFieldError(field, msg)` where **`field` is the control's `name`** (`settings.name`), **not** its
> `fieldExpression`; ⚠️ **`actionValidators` is authored/persisted but does NOT run at CRUD-form submit** (only
> `validators` do) — the working per-action path is the user-task action's `validationRuleIdentifiers`
> ([07](07-workflows-and-tasks.md)); and **`allowDrafts`** (when to enable it — multi-session / data-fetched-later
> forms). "Create Validation from Template" (the field-level `conditionalValidations` predicates) is [25 §2](25-form-settings-validation-and-events.md).

### ACTION — two DIFFERENT `ActionDto`s (CRUD vs UserTask)

The action bound to a form group lives in the table/tree/process settings (`properties.model.stringValue`
of the table plugins — see [04-crud-table-plugin.md](04-crud-table-plugin.md),
[05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)), not in `FormDto`. There are **two
different `ActionDto` classes** with different field names — don't confuse them when building JSON manually:

| field | CRUD `ActionDto` (`CrudTableActionsDto.ActionDto`) | UserTask `ActionDto` (`UserTaskActionsDto.ActionDto`) |
|---|---|---|
| `id` | String | String |
| `localizedNames` | `Map<String,String>` (`en_US`→name) | `Map<String,String>` |
| `localizedButtonNames` | `Map<String,String>` (submit button; empty→fallback to `localizedNames`) | `Map<String,String>` |
| `icon` | String (Pe-icon class) | String |
| `formGroupIdentifier` | String (non-direct → this group) | String |
| `predicateIdentifier` | String (visibility predicate) | String |
| `direct` | **boolean** (`isDirect()` — just the value) | **String** (`isDirect()` = equals `"on"`) |
| `onBeforeStartRuleIdentifier` | String | — |
| `onBeforeCompleteRuleIdentifier` | String | — |
| `onBeforeUserTaskStartRuleIdentifier` | — | String |
| `onBeforeUserTaskCompleteRuleIdentifier` | — | String |
| `validationRuleIdentifiers` | — (none) | String (comma-separated) |
| `taskId` | — (none) | String |
| `completeUserTask` | — (none) | String (`shouldCompleteUserTask()` = NOT `"off"` → default true) |
| `submitForm` | `Boolean` (`shouldSubmitForm()` null→true) | `Boolean` (`shouldSubmitForm()` null→true) |

Key differences and semantics:
- **`direct`**: CRUD — Java `boolean` (in JSON `true`/`false`); UserTask — String `"on"`/`"off"`
  (`isDirect()`=equals `"on"`). A direct action runs **without opening a form**.
- **hook names differ**: CRUD `onBeforeStartRuleIdentifier`/`onBeforeCompleteRuleIdentifier` vs UserTask
  `onBeforeUserTaskStartRuleIdentifier`/`onBeforeUserTaskCompleteRuleIdentifier`.
- **`localizedNames`/`localizedButtonNames`** — a Map keyed by locale (`en_US`, `hy_AM`), NOT a flat
  `name` (a legacy `name` string is tolerated and ignored via `@JsonIgnoreProperties`,
  `UserTaskActionsDto.java`). Fallback lookup: full locale → language → first non-empty; an empty
  button name → `localizedNames` is used.
- **`submitForm`** (both versions, null→true): for a non-direct action controls whether the in-form button submits
  (persist + complete-rule) or only runs the rules.
- ⛔ **`onBeforeCompleteRuleIdentifier` is the PERSIST hook — not an optional extra.** For a CRUD Create/Edit/Delete
  action it points at the EXECUTION rule that actually writes the row
  (`context.<ctx>.<crud>.service.create/update/delete(...)`, context-scoped). **A create/edit form action with no
  onBeforeCompleteRule submits and SAVES NOTHING**; a direct Delete with none does nothing on click. This is what
  "Create Default Actions" wires (create→create rule, edit→update rule, delete→delete rule). Full recipe + scripts:
  [04-crud-table-plugin.md](04-crud-table-plugin.md) (the ⛔⛔ persist callout); `validate` WARNs via
  `_check_action_persist`.
- **UserTask-only**: `completeUserTask` `"off"` = save as draft (do not complete the task); `taskId`;
  `validationRuleIdentifiers`. The literal string `"null"` is cleaned to real null in the getters
  (`onBefore*`, `validationRuleIdentifiers`, `predicateIdentifier`). `UserTaskActionsDto` wraps
  `List<ActionDto> actions` + `List<ActionError> errors`.

Example action → form group (CRUD, from table settings; `direct:false` → opens `formGroupIdentifier`):
```json
{ "id": "<actionUuid>", "localizedNames": { "en_US": "Edit" }, "localizedButtonNames": { "en_US": "Save" },
  "icon": "pe-7s-pen", "direct": false, "formGroupIdentifier": "GROUP_UUID",
  "predicateIdentifier": "<visibilityPredUuid|null>",
  "onBeforeStartRuleIdentifier": null, "onBeforeCompleteRuleIdentifier": null, "submitForm": null }
```

**Action icon classes** (the Pe-icon-7-stroke set): `pe-7s-check`, `pe-7s-close`, `pe-7s-plus`, `pe-7s-pen`,
`pe-7s-trash`, `pe-7s-diskette`, `pe-7s-refresh-2`, `pe-7s-repeat`, `pe-7s-file`, `pe-7s-mail`,
`pe-7s-user`, `pe-7s-config`, `pe-7s-search`, `pe-7s-right-arrow`, `pe-7s-upload`, `pe-7s-download`.

### How the form is chosen (landing plugin dispatch)

`FormGroupLandingPlugin.initPluginContent` resolves the group by `?group=`, then
`navigateToFormIfNeed` reads the URL params and, if `settingsName`+`actionId` are set, loads
the `SettingsDto` by name and branches on `settings.getType()`:

**Directly-read URL params** (via `ParameterUtils.getStringParam`):
`group` (required), `settingsName`, `actionId`, `processIdentifier`, `crudId`. For the **dispatch path**
(navigation to a form by predicate) `crudAlias`/`workflowIdentifier`/context are NOT read as direct
URL params — they come from settings-derived navigation data
(`CrudTableNavigationData.getCrudAlias()/.getContextIdentifier()`,
`ProcessTableNavigationData.getWorkflowIdentifier()`). However `context` (and `crud`) **are read**
as direct URL params on other paths of the same plugin: for context registration
(`ensureContextRegisteredOnGroup`) and for carrying over to the form page (`goLandingPage`). When navigating to a form, params starting with
`path` are dropped (`navigateToForm`).

**Settings-type constants**: `SETTINGS_TYPE_PROCESS_TABLE = "ProcessTable"`
`SETTINGS_TYPE_CRUD_TABLE = "CrudTable"`, `SETTINGS_TYPE_CRUD_TREE = "CrudTree"`.

**Action lookup order + predicate execution method:**

| settingsType | action lookup order | nav method | executor (predicate method) | context |
|---|---|---|---|---|
| `ProcessTable` | `userStartProcessActions` (isStartForm=true) → | `navigateWithWorkflowStartPredicate` | `flowableTaskService.executePredicateForWorkflow(realm,client,workflowIdentifier,predicateId,actionId)` | user, no entity |
| | `globalActions` (isStartForm=false, needs `processIdentifier`) → otherwise Flowable task | `navigateWithWorkflowPredicate` | `flowableTaskService.executePredicate(realm,client,processIdentifier,predicateId,actionId)` | full process context |
| `CrudTable`/`CrudTree` | `createActions` (isCreateAction=true) → | `navigateWithCrudCreatePredicate` | `ruleExecutionService.executePredicateWithEmptyContext(realm,client,crudAlias,ctx,predicateId,userId,userEmail,actionId)` | user, **no CRUD row**; `service.actionId` available |
| | `editActions` (isCreateAction=false, needs `crudId`) | `navigateWithCrudPredicate` | `ruleExecutionService.executePredicateWithCrudContext(realm,client,crudAlias,crudId,ctx,predicateId,userId,userEmail,actionId)` | **loads the whole row** into `context.<ctx>.<alias>.data`; `service.actionId` |

> ### ⛔ `service.actionId` is **NOT** available in the two workflow branches — read `attrs.get('actionId')`
>
> All four branches pass `actionId` to the executor, but **not through the same channel**, and the Groovy
> handle differs. `service.actionId` is bound ONLY from the `__actionId` **attr**
> (`GroovyExecutorHelper.applyActionMeta` → `serviceWrapper.setActionId`); the workflow branches never set
> that attr — they put the id into `executionVariables` under the plain key `actionId`
> (`FlowableTaskServiceImpl.executePredicate`, `.executePredicateForWorkflow`), and
> `executionVariables` are merged into `contextData.attrs` (`RuleExecutorReactor`).
>
> | branch | how actionId travels | read it in Groovy as |
> |---|---|---|
> | ProcessTable → start action (`navigateWithWorkflowStartPredicate`) | `executionVariables["actionId"]` → `attrs` | **`attrs.get('actionId')?.asText()`** |
> | ProcessTable → global action / Flowable task (`navigateWithWorkflowPredicate`) | `executionVariables["actionId"]` → `attrs` | **`attrs.get('actionId')?.asText()`** |
> | CrudTable/CrudTree → create (`navigateWithCrudCreatePredicate`) | `contextData.attrs["__actionId"]` | `service.actionId` |
> | CrudTable/CrudTree → edit (`navigateWithCrudPredicate`) | `contextData.attrs["__actionId"]` | `service.actionId` |
>
> A mapping predicate written as `return service.actionId == '<start-action-uuid>'` therefore evaluates
> **false on the process-start path** — the loop falls through to the pair whose predicate is the
> always-true rule and opens the WRONG form, with no error anywhere. Write predicates that must work on
> both kinds of action defensively:
>
> ```groovy
> def a = ''
> try { a = attrs?.get('actionId')?.asText() ?: '' } catch (Exception ignored) { }
> if (a == null || a.isEmpty()) { try { a = (service.actionId ?: '') as String } catch (Exception ignored) { } }
> return a == '<action-uuid>'
> ```
>
> Two more traps in the same loop (`navigateWithWorkflowStartPredicate`): pairs are tried **in array
> order** and the FIRST true one wins — so a specific pair must be listed **before** the always-true pair —
> and a pair with a BLANK predicate is not evaluated at all, it is only the fallback used when nothing matched.

`userId`
(`page.user().getId()`) and `userEmail` (`page.user().getEmail()`) are added in the CRUD branches via
`getCurrentUserId()`/`getCurrentUserEmail()`. Without `settingsName`/`actionId`
the landing stays put (just shows the group's form list).

**Context for the CRUD predicate** (`navigateWithCrud*Predicate`): `settingsContextIdentifier`
from the navigation data (settings action) **takes priority**; if empty → `getContextIdentifier(formGroup,
crudAlias)` = the first of `formGroup.contextIdentifiers`; if that too is empty → the `crudAlias` itself. So in
practice the context is usually taken from the action's own settings, not from the group.

> ⚠️ Signatures are illustrative: the method names `executePredicateWith{Crud,Empty}Context` /
> `executePredicateForWorkflow` / `executePredicate` and their argument order are verbatim from
> `FormGroupLandingPlugin`; this is NOT a generic `predicateService.execute(...)`.

## How to construct from scratch

> ⭐ **Read this first — THE canonical recipe (build forms EXACTLY like this).** The two general recipes (A/B)
> below document what else imports and runs; the section immediately below is the **authoritative shape to
> replicate**, field-for-field. Copy it. Prefer it over A/B.

### ⭐ Canonical form-group recipe (live-verified)

Build **every** group the same way — this is the shape a builder/generator should emit for every entity's
Create/Edit forms.

**Per-group page structure:**

```
<CRUD-table page>                                   e.g. "<Entity> Cases"    (its own top-level alias, e.g. <entity>-monitor)
 ├─ LANDING page   name="<Entity> Forms"   alias(top-level)="<entity>-forms"   layout="Main"   hosts dynaform.form.groups.landingplugin
 └─ FORM page      name="Form: <slug>"      alias(top-level)="form-<slug>"       layout="Main"   hosts dynaform.form.plugin   (property formModeIdentifier=<FORM_UUID>)
```

- **`placeFormsNextToLanding = true` for EVERY group** → the FORM page is a **SIBLING** of the landing (BOTH are
  children of the CRUD-table page). It is **not** nested inside the landing.
- **One landing PER group** — each group's `contentPageIdentifier` is its **own** landing page (never one shared
  landing). Multiple groups may share the same CRUD-table page as their parent; each still has its own landing.
- **layout `Main` for BOTH** the landing and the form page. (Older projects use
  `Form` for the form page — both render, but `Main` is the current standard, so emit `Main`.)
- **The routable alias is the TOP-LEVEL `alias`** field on each page; `properties.alias.stringValue` stays null.
  Every landing/form-page alias is **present AND unique** — this is precisely what prevents ERR_TOO_MANY_REDIRECTS
  (see the ⛔ trap callout above).
- **`formModeIdentifier`** — a property on the FORM page, equal to the form's `identifier`. The landing has
  `formModeIdentifier=null`.

**Naming convention:**

| object | `name` | top-level `alias` |
|---|---|---|
| Form **group** (`formGroups[].name`) | `<entity>-forms` — a slug (e.g. `<entity>-forms`) | — (groups are not pages) |
| **Landing** page | `<Entity> Forms` (e.g. "<Entity> Forms") | `<entity>-forms` — **== the group name** |
| **Form** page | `Form: <slug>` (e.g. "Form: <entity>-worksheet") | `form-<slug>` (e.g. `form-<entity>-worksheet`) |

The landing's top-level alias equals the group's slug name; the form page prefixes `form-`. All are distinct from
the business/CRUD-table page aliases (`<entity>s`), so nothing collides.

**One group → multiple forms (predicate fork).** One `<entity>-forms` group can map **two** forms — a specific
predicate for the exceptional variant (an escalated review, a corrected declaration, a credit-note reversal),
then a `return true` fallback for the default (narrow predicate ABOVE `True`, array order = priority):

```json
"predicateFormMapping": { "mapping": [
  { "predicateIdentifier": "<narrow-case predicate>", "formIdentifier": "<variant form>" },
  { "predicateIdentifier": "<True>",                 "formIdentifier": "<default form>" } ] }
```

> ⛔⛔ **THE #2 hand-authoring trap — a form/landing page is NOT a bare `parsis.plugin → <plugin>`; the plugin
> lives INSIDE the page's baked LAYOUT.** Every renderable page (CRUD table, landing, form, dashboard) carries a
> baked page layout: `siteMapPage → parsis.plugin → **html.plugin name="Layout"** → [ `site.header.plugin`,
> `nct.image.plugin` (logo), `site.breadcrumb.plugin`, `site.kicker.plugin` (left-nav), **`nct.parsis.plugin
> name="parsis"` (the CONTENT area)**, `site.footer.plugin`, `site.right.kicker.plugin` ]`. The form-group
> **landing plugin** and the **`dynaform.form.plugin`** go INSIDE that content `nct.parsis.plugin`, NOT directly
> under the page's top `parsis.plugin`. A page built as a **bare** `siteMapPage → parsis.plugin →
> dynaform.form.plugin` (no `html.plugin "Layout"` chrome) **imports fine but renders at runtime as "this isn't a
> form layout / no form plugin / no fields"** — the form is completely empty (verified live; in a working form
> page the content parsis children == `[dynaform.form.plugin]`). **`page add`
> creates the page WITH this Layout baked in; `node add --plugin dynaform.form.plugin` drops the plugin into the
> content parsis.** If you hand-build via a generator, **CLONE a page that already has the Layout** (e.g. the shared
> Landing `ec99a5a0`, or any `page add` output) and inject your plugin into its content `nct.parsis.plugin` — do
> **not** emit a bare `parsis.plugin → plugin`. `validate` now **ERRORs** on a form page whose `dynaform.form.plugin`
> is outside the `html.plugin "Layout"` (`_check_form_page_layout`).

**Worked FORM page** (`Form: <slug>-variant`) — the **full** structure, Layout chrome included
(the landing page is identical except the content parsis holds `dynaform.form.groups.landingplugin` and there is no
`formModeIdentifier`):

```json
{ "name": "Form: <entity>-worksheet-variant", "alias": "form-<entity>-worksheet-variant", "pluginName": "siteMapPage",
  "properties": { "layout": { "propertyType": "STRING", "stringValue": "Main" },
                  "formModeIdentifier": { "propertyType": "STRING", "stringValue": "<FORM_UUID>" } },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true },
  "children": [ { "name": "parsis", "pluginName": "parsis.plugin", "children": [
    { "name": "Layout", "pluginName": "html.plugin", "children": [
      { "name": "header",       "pluginName": "site.header.plugin" },
      { "name": "logo-plugin",  "pluginName": "nct.image.plugin" },
      { "name": "breadcrumb",   "pluginName": "site.breadcrumb.plugin" },
      { "name": "left-nav",     "pluginName": "site.kicker.plugin" },
      { "name": "parsis", "pluginName": "nct.parsis.plugin", "children": [
        { "name": "form", "pluginName": "dynaform.form.plugin", "children": [
          { "name": "form.parsis", "pluginName": "nct.parsis.plugin", "children": [ /* gen_row → gen_col → gen_slot → field controls (doc 03) */ ] }
        ] }
      ] },
      { "name": "footer",       "pluginName": "site.footer.plugin" },
      { "name": "right-kicker", "pluginName": "site.right.kicker.plugin" }
    ] }
  ] } ] }
```

Both the landing and this form page are children of the **same** CRUD-table page (`<Entity> Cases`) — siblings.
The `dynaform.form.plugin` sits at `parsis.plugin → html.plugin "Layout" → nct.parsis.plugin "parsis"` — the same
place a table plugin sits on a CRUD page and the landing plugin sits on a landing page.

**Build order:** create the landing + each form page **with the Layout chrome** (clone the shared Landing / a
`page add` output — never emit a bare page), inject the `dynaform.form.plugin` (+ controls) into the content parsis,
stage them, then `page mv --to-parent <CRUD-table page>` so **neither is left at root**, set
`placeFormsNextToLanding=true`, wire the mapping, and keep `forms[].formGroup` an **exact copy** of the group.
`validate` ERRORs if any landing/form page is missing/colliding on its top-level alias
(`_check_form_group_page_aliases`) or if a form page's `dynaform.form.plugin` is outside its Layout
(`_check_form_page_layout`).

---

### General mechanism — recipes A / B (background)

Two recipes: **(A)** sibling landing (`placeFormsNextToLanding=true` — this is what the canonical recipe above
uses) and **(B)** child landing + admin group list (the shared-landing style, `placeFormsNextToLanding=false`). Both
import and run; **the canonical recipe above (variant A, per-group landing, layout Main) is what to build.**
Assume the CRUD table's parent page has `ContentDomain.identifier = PARENT_PAGE`.

### Common step 0 — the `True` predicate

If not already present, add to `rep-objects.json.rules[]` (see
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)); the body **must** be `"return true"`
(a bare `true` is discarded by the GroovyPredicate template — `CrudDefaultActionsService.java`; see
[08](08-groovy-rules-and-context.md) §"the template trailer"):

```json
{ "identifier": "TRUE_UUID", "name": "True", "description": "True", "ruleType": "PREDICATE",
  "executor": "GroovyPredicate", "status": "ACTIVE", "hidden": null,
  "contextIdentifiers": [],
  "rule": { "ruleScriptStr": "return true" } }
```

> The auto-gen "True" predicate has an **empty** `contextIdentifiers: []` (`return true` reads no context).
> Context for such a predicate is optional; the full form of a PREDICATE rule is
> in [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).

### Recipe A — sibling landing (auto-gen style, `placeFormsNextToLanding=true`)

**A1. Landing page** — a new `siteMapPage` under `PARENT_PAGE`, layout `"Main"`, authenticated-only access
(`CrudDefaultActionsService.applyAuthenticatedUsersAccess`; a fresh `RoleAccess` is public by default —
set both flags explicitly), alias via `AliasUtils.uniqueChildAlias` (a slug of the name, unique among siblings).
Inside `parsis` — a `dynaform.form.groups.landingplugin` node (empty generic properties). Remember the
`identifier` as `LANDING_PAGE`.

```json
{ "identifier": "LANDING_PAGE", "name": "Product Forms", "alias": "product-forms",
  "pluginName": "siteMapPage",
  "properties": { "layout": { "propertyType": "STRING", "stringValue": "Main" } },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true },
  "children": [ { "name": "parsis", "pluginName": "parsis.plugin",
    "children": [ { "identifier": "LANDING_PLUGIN_UUID", "name": "Form group landing",
                    "pluginName": "dynaform.form.groups.landingplugin",
                    "properties": { "className": {"...":"..."}, "styleName": {"...":"..."}, "tagProperties": {"...":"..."} } } ] } ] }
```

**A2. Form page** — a `siteMapPage`, layout `"Main"`, authenticated-only. Since
`placeFormsNextToLanding=true`, the page is created as a **sibling** of the landing (also under `PARENT_PAGE`;
`resolveFormPageParent`). Set the property `formModeIdentifier = FORM_UUID`. The `dynaform.form.plugin`
goes INSIDE the page's baked Layout chrome (controls are filled separately —
[03-generate-fields-from-crud.md](03-generate-fields-from-crud.md)). Remember the `identifier` as `FORM_PAGE`.

> ⛔ The form page MUST carry the full Layout chrome — identical to the Worked FORM page / ⛔ #2 trap above:
> `dynaform.form.plugin` sits INSIDE the content `nct.parsis.plugin "parsis"` of `html.plugin "Layout"`, **never**
> directly under the page's top `parsis.plugin`. A bare `parsis.plugin → dynaform.form.plugin` imports fine but
> renders **empty** ("not a form layout / no form plugin / no fields") and `mrjun.py validate`
> (`_check_form_page_layout`) **ERRORs**. Build it by **CLONING** a page that already has the Layout (a `page add`
> output or the shared Landing) and injecting the form plugin into its content `nct.parsis.plugin` — do not emit a
> bare page.

```json
{ "identifier": "FORM_PAGE", "name": "Product Form", "alias": "product-form",
  "pluginName": "siteMapPage",
  "properties": {
    "layout": { "propertyType": "STRING", "stringValue": "Main" },
    "formModeIdentifier": { "propertyType": "STRING", "stringValue": "FORM_UUID" } },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true },
  "children": [ { "name": "parsis", "pluginName": "parsis.plugin", "children": [
    { "name": "Layout", "pluginName": "html.plugin", "children": [
      { "name": "header",       "pluginName": "site.header.plugin" },
      { "name": "logo-plugin",  "pluginName": "nct.image.plugin" },
      { "name": "breadcrumb",   "pluginName": "site.breadcrumb.plugin" },
      { "name": "left-nav",     "pluginName": "site.kicker.plugin" },
      { "name": "parsis", "pluginName": "nct.parsis.plugin", "children": [
        { "name": "form", "pluginName": "dynaform.form.plugin", "children": [
          { "name": "form.parsis", "pluginName": "nct.parsis.plugin", "children": [ /* gen_row → gen_col → gen_slot → field controls (doc 03) */ ] }
        ] }
      ] },
      { "name": "footer",       "pluginName": "site.footer.plugin" },
      { "name": "right-kicker", "pluginName": "site.right.kicker.plugin" }
    ] }
  ] } ] }
```

**A3. `formGroups[]`** — `placeFormsNextToLanding:true`, `formGroupsPageIdentifier:null`, one `True → form` pair.
**A4. `forms[]`** — the form; `formGroup` is a **full** copy of the object from A3 (with housekeeping fields + the same
mapping pair). `form.contentIdentifier = FORM_PAGE` (the form page from A2 — sibling of landing), and
`formGroup.contentPageIdentifier = LANDING_PAGE`. (For the exact JSON structure — see variant B below; the differences
of variant A: `placeFormsNextToLanding:true` and the form page is a sibling, but the form's `contentIdentifier` in both
recipes points at a **separate** form page `FORM_PAGE`, not at the landing.)

### Recipe B — child landing + admin list (shared-landing style)

**B1. Landing page** — like A1, but the group's `placeFormsNextToLanding` will be `false`, so the form page
will become a **child** of this landing: the landing page itself carries only the landing plugin, and the form
controls are on a separate child page
(the form's `contentIdentifier` = `FORM_PAGE`, parent = `LANDING_PAGE`). Theoretically you could instead
put `dynaform.form.plugin` + `formModeIdentifier` right on the landing page (then the form's `contentIdentifier`
= `LANDING_PAGE`) — no working project does that.

> ⛔ **Do NOT reuse the baseline `Landing` page (`ec99a5a0-3605-4843-94ad-cf7fb4deb5a5`) as a group's
> `contentPageIdentifier`.** The empty baseline does ship that "Landing" `siteMapPage` (alias `landing`, parsis
> carrying `dynaform.form.groups.landingplugin`), and the baseline `dynaform.form.groups.plugin` console even
> defaults to it (`ContentChooserPanelModel {"editorPageContentIdentifier":"ec99a5a0-…"}`, so groups created in
> the admin Form Groups list inherit it) — but that is the **author-console default, not the shape for end-user
> Create/Edit**. It is a child of the admin `Form Groups` page and role-gated
> (`publicReadAccess:false`, `authenticatedUserAccess:false`, `accessors` = admin/author/user_* roles only), so a
> clerk sent there by a Create/Edit button gets access-denied. `validate` **WARNs** on a group still pointing at
> it. Do B1 for real: give each group its **own** landing page under the CRUD-table page, as in the ⭐ recipe.
> (Cloning that page as a source of Layout chrome is a different thing and is fine — see the ⛔⛔ #2 trap.)

**B2. Form page** — a `siteMapPage`, layout `"Main"`, authenticated-only, exactly like A2 (same full Layout
chrome — see the ⛔ callout under A2), but since `placeFormsNextToLanding=false`, the page is created as a
**child** of the landing (parent = `LANDING_PAGE`, `resolveFormPageParent`). Set the property
`formModeIdentifier = FORM_UUID`. The `dynaform.form.plugin` goes INSIDE the content `nct.parsis.plugin` of
`html.plugin "Layout"` (controls are filled separately —
[03-generate-fields-from-crud.md](03-generate-fields-from-crud.md)). Remember the `identifier` as `FORM_PAGE`.

> ⛔ Same trap as A2 — a bare `parsis.plugin → dynaform.form.plugin` (no `html.plugin "Layout"` chrome) imports
> fine but renders **empty** and `mrjun.py validate` (`_check_form_page_layout`) **ERRORs**. CLONE a page that
> already has the Layout and inject the form plugin into its content `nct.parsis.plugin`.

```json
{ "identifier": "FORM_PAGE", "name": "Product Form", "alias": "product-form",
  "pluginName": "siteMapPage",
  "properties": {
    "layout": { "propertyType": "STRING", "stringValue": "Main" },
    "formModeIdentifier": { "propertyType": "STRING", "stringValue": "FORM_UUID" } },
  "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true },
  "children": [ { "name": "parsis", "pluginName": "parsis.plugin", "children": [
    { "name": "Layout", "pluginName": "html.plugin", "children": [
      { "name": "header",       "pluginName": "site.header.plugin" },
      { "name": "logo-plugin",  "pluginName": "nct.image.plugin" },
      { "name": "breadcrumb",   "pluginName": "site.breadcrumb.plugin" },
      { "name": "left-nav",     "pluginName": "site.kicker.plugin" },
      { "name": "parsis", "pluginName": "nct.parsis.plugin", "children": [
        { "name": "form", "pluginName": "dynaform.form.plugin", "children": [
          { "name": "form.parsis", "pluginName": "nct.parsis.plugin", "children": [ /* gen_row → gen_col → gen_slot → field controls (doc 03) */ ] }
        ] }
      ] },
      { "name": "footer",       "pluginName": "site.footer.plugin" },
      { "name": "right-kicker", "pluginName": "site.right.kicker.plugin" }
    ] }
  ] } ] }
```

**B3. `formGroups[]`** — a group with landing, admin list and one `True → form` pair:

```json
{ "identifier": "GROUP_UUID", "name": "Product Form Group",
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "contextIdentifiers": ["CTX_UUID"],
  "contentPageIdentifier": "LANDING_PAGE",
  "formGroupsPageIdentifier": "e714bbd4-c6c4-49d6-a698-5608e3113317",
  "placeFormsNextToLanding": false,
  "predicateFormMapping": { "mapping": [
    { "predicateIdentifier": "TRUE_UUID", "formIdentifier": "FORM_UUID" } ] } }
```

> `formGroupsPageIdentifier` = the `identifier` of the admin "Form Groups" page shipped in the empty baseline
> (alias `form`, `e714bbd4-...`). Do not create a new list page — use the existing one.
> Want to hide the group from the admin list — set `null`.

**B4. `forms[]`** — the form; `formGroup` is a **full** copy of B3 (all housekeeping fields + the same mapping pair,
`formIdentifier=FORM_UUID`); `multiLanguage:true` — as in a localized project:

```json
{ "identifier": "FORM_UUID", "name": "Product Form",
  "message": null, "errors": null, "id": null,
  "realmName": "<realm>", "clientName": "<client>",
  "contentIdentifier": "FORM_PAGE",
  "contextIdentifiers": ["CTX_UUID"],
  "formGroup": { "identifier": "GROUP_UUID", "name": "Product Form Group",
    "message": null, "errors": null, "id": null,
    "realmName": "<realm>", "clientName": "<client>",
    "contextIdentifiers": ["CTX_UUID"],
    "contentPageIdentifier": "LANDING_PAGE",
    "formGroupsPageIdentifier": "e714bbd4-c6c4-49d6-a698-5608e3113317",
    "placeFormsNextToLanding": false,
    "predicateFormMapping": { "mapping": [
      { "predicateIdentifier": "TRUE_UUID", "formIdentifier": "FORM_UUID" } ] } },
  "validators": [], "actionValidators": [], "hiddenConfigs": [],
  "multiLanguage": true, "allowDrafts": null }
```

**B5. Bind the action to the group.** In the CRUD-table/-tree settings (`properties.model.stringValue`) each
Create/Edit action specifies `formGroupIdentifier = GROUP_UUID` (CRUD `ActionDto` — see the table above and
[04-crud-table-plugin.md](04-crud-table-plugin.md)). On click, the table navigates to the landing with
`?group=GROUP_UUID&settingsName=<...>&actionId=<uuid>&crudId=<id>` — the landing picks a form by predicate.

### Recipe: fork "Create/Edit → form A, View → form B"

A group with multiple pairs in `mapping` (e.g. "Material Reservation Forms" / "Production Order Forms"). Add a
second PREDICATE of the form `return service.actionId == '<VIEW_ACTION_UUID>'` (name by convention
`"<Crud> <FormGroup> → <Action> [Mapping Predicate]"`, `PredicateFormMappingField.java`), put its
pair **above** the `True` pair (array order = priority) and point it at the second form:

```json
"predicateFormMapping": { "mapping": [
  { "predicateIdentifier": "VIEW_PRED_UUID", "formIdentifier": "VIEW_FORM_UUID" },
  { "predicateIdentifier": "TRUE_UUID",       "formIdentifier": "MAIN_FORM_UUID" } ] }
```

The View action (`service.actionId == VIEW_ACTION_UUID`) will open the View form, while Create/Edit fall through to `True`
→ the main form. A worked predicate body:
`"return service.actionId == '3e3dfced-52ee-4edf-b3c7-b97131485087'"` (rule "Material Reservation Material
Reservation Forms → Adjust Reservation [Mapping Predicate]"). **`VIEW_ACTION_UUID` must match the `id`
of the View action in the table settings** — otherwise `service.actionId` won't match (see Gotchas).

## Naming conventions (auto-gen path)

These conventions are applied ONLY by the **Create Default Actions** path / the create dialogs. When building
manually the names are technically free-form — but for a **consistent, collision-free** build, follow the ⭐
canonical convention (group `<entity>-forms`, landing `<Entity> Forms`/alias `<entity>-forms`, form page
`Form: <slug>`/alias `form-<slug>`) under "How to construct" rather than inventing per-entity names.

- **Group:** `"<CrudName> Forms"` — `CrudDefaultActionsService.formGroupNameFor`
  (`crudName + " Forms"`); the same method is reused by the "Create Form Group" dialog
  (`FormGroupCreatePanel.suggestGroupName`). `<CrudName>` — the CRUD display name, otherwise the alias.
- **Form:** `"<CrudName> Form"` (`CrudDefaultActionsService.java`). The "Create new form" dialog on the
  landing suggests the same: it strips `" Forms"` from the group name, appends `" Form"`, de-dups with `" 2"`,
  `" 3"`… (`FormGroupLandingPlugin.suggestFormName`).
- **`True` predicate:** exactly `"True"`, body `"return true"` (`CrudDefaultActionsService.java`; duplicate logic in `FormEditorPanel.ensureTruePredicateId`).
- **Action-based mapping predicate:** `"<Crud> <FormGroup> → <Action> [Mapping Predicate]"`, body
  `"return service.actionId == '<uuid>'"` (`PredicateFormMappingField.java`
  `withActionRuleCreator`). From the form's create dialog the predicate defaults to the shared `True`, and the new one's name is
  `"<FormName> Mapping Predicate"` (`FormEditorPanel.java`
  `RuleNameSuggestion.join(form.getName(), "Mapping Predicate")`).
- **Page alias:** a slug of the name (`lowercase`, space→`-`, everything except `[a-z0-9-]` stripped), unique
  among siblings with a `-2`, `-3`… suffix (`AliasUtils.slug` / `uniqueChildAlias`). A non-ASCII
  name (Armenian/Russian) collapses to `""` → a fallback is used (`"form"` / `"form-group"`).

## Gotchas

> ⚠️ **These form-group wiring bugs are silent at import — `validate` is what catches them; do not ship
> without running it.** It checks: `forms[].formGroup` against the canonical `formGroups[]` entry (warn on a
> diverged `predicateFormMapping`, `_check_form_linkage`); an action's `formGroupIdentifier` resolving to no
> group (**err**, `_check_table_action_refs`); the form page carrying `formModeIdentifier == form.identifier`
> somewhere in its subtree (**err**, `_check_form_linkage`); a `service.actionId == '<uuid>'` fork whose uuid
> is no real action id (warn); the top-level alias of every landing/form page and the `dynaform.form.plugin`
> sitting inside its Layout (**err**); and — the one that silently eats submits — a rule wired to a
> CRUD-table/tree action that reads its own form's field with `context.data.getAttr("<field>")` (**err**,
> `_check_crud_action_form_values`; the same check warns on a control left GLOBAL/CONTEXT on a form only
> reachable from such an action). What each failure looks like live is in the Gotchas below.

- **`predicateFormMapping.mapping` is ordered by position.** The first matching predicate wins; pairs with
  an empty `predicateIdentifier` are only a fallback (the first blank, applied after a full scan with no match).
  Put narrow predicates above `True` (`FormGroupLandingPlugin.java`). **There is no numeric
  `order` field** — order is set solely by position in the array.
- **A bare `true` in a predicate does not work.** The GroovyPredicate template ends with `if(true){return null;}`,
  so a `true` body is discarded → the predicate returns `null` ("must return Boolean"). Always use
  `"return true"` / `"return <expr>"` (`CrudDefaultActionsService.java`; see
  [08](08-groovy-rules-and-context.md)).
- **`service.actionId` is empty in the CRUD-create branch if not threaded.** `service.actionId == '<uuid>'`
  will return false if the landing didn't pass `actionId`. On a correctly wired page it works because the table puts
  `actionId` in the URL, and `navigateWithCrud{Create,}Predicate` thread it into
  `executePredicateWith{Empty,Crud}Context(... actionId)`. When building manually make sure the
  action in the table settings has the same `id` as the `<uuid>` in the predicate
  (see `project_formgroup_predicate_actionid`).
- **Form-page alias collision.** Two form pages under the same parent with the same `(parentId, alias)`
  shadow each other in the CMS URL index (`BranchContentIndex` — a HashMap, last one wins): the first form
  will start opening the second (empty) one. Always use `AliasUtils.uniqueChildAlias`, not a bare slug
  (`AliasUtils.java`; see `project_formpage_alias_collision`).
- **`placeFormsNextToLanding` determines the form page's PARENT, not the layout.** `false` (default) → the form is a
  child of the landing; `true` → the form is a sibling of the landing (under the landing's parent). **Flipping the flag on an existing
  group moves the already-created pages:** this is done by `FormPagePlacementUtil.relocateFormPages`
  via the **4-arg** `contentService.save(branchId, parent, child, index)` — it is this call that actually
  moves the node (mutates the parent's children, then `removeDuplicateChildren` detaches the node from the old
  parent, `FormPagePlacementUtil.java`). A naive `formPage.setParentId(newId)` + flat
  `save(branchId, formPage)` does **NOT move** the node (replaceContentInTree swaps it in place under the old
  parent). When building manually just place the form page under the correct parent right away.
- **The landing node does not store `?group`.** A single landing plugin serves any group — which one exactly is decided by the
  URL parameter `?group=<identifier>`. Without it the landing shows "Please navigate this page from form group
  list" (`FormGroupLandingPlugin.java`). The table buttons / `FormsPanel.goLandingPage` add `group`
  automatically.
- **`formGroup` inside `FormDto` is a FULL duplicated copy** (with housekeeping fields). Keep it
  synchronized with the record in `formGroups[]` (especially `predicateFormMapping`). A divergence →
  `FormPagePlacementUtil.findFormsInGroup` tries to recover the forms from both sources (filter +
  mapping), but do not create the desync.
- **`formModeIdentifier` on the form page is mandatory.** Without the property `formModeIdentifier = <formId>` on the
  `siteMapPage` (or on the landing page itself in the dynamic layout) the form plugin does not know which `FormDto`
  to render. Both the landing and default-actions set it.
- **The empty project already contains the infrastructure.** Its `branches.json` has an admin "Form Groups" page
  (`alias:"form"`, `identifier:"e714bbd4-c6c4-49d6-a698-5608e3113317"`), which hosts
  `dynaform.form.groups.plugin` **and** `dynaform.form.groups.landingplugin`; its `rep-objects.json` has
  `formGroups:[]`, `forms:[]`. In Step 2 don't build the admin list page — just add
  `formGroups[]`/`forms[]` (with `formGroupsPageIdentifier = e714bbd4-...`) and the business landing/form pages.
  The `dynaform.form.groups.plugin` (group-list) node itself carries a `ContentChooserPanelModel` JSON property
  `{editorPageContentIdentifier}` — the **default landing page** copied into a group created/edited from this list
  page (`FormGroupsPlugin.java`); the baseline sets it, so keep it verbatim if you clone the node. (Same slot as
  `workflows.plugin`/`executor.rule.list.plugin` — see [07](07-workflows-and-tasks.md), [14](14-plugin-catalog-all.md).)
- **Two `ActionDto`s.** The CRUD and UserTask `ActionDto`s are DIFFERENT classes with different hook-field names and a different
  `direct` type (boolean vs `"on"/"off"` String). When editing settings by hand cross-check with the table above,
  otherwise the field is silently ignored.
- **`process.table.pluin`** — a real typo in the `pluginName` of the process-table plugin; use the string
  exactly like this (see [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)).
- **Static vs dynamic does not affect these objects.** `formGroup`, `form`, the landing node, mapping — identical in
  a static (compiled-bean) and a dynamic (definition-driven) project. Only the resolution of
  `service.crud.<alias>` inside predicates differs
  (see [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)).

## List control sub-forms (editable Create/Edit item forms)

A **List** form control (`dynaform.form.list.field.plugin` — see
[02-form-controls-reference.md](02-form-controls-reference.md) §7) renders a nested table with its own
Create/Edit actions. Those actions do **not** go through a form group / landing / `predicateFormMapping` — the
List embeds each editable form **inline**, as a `dynaform.list.item.plugin` child node of the List node. It is a
form container in its own right (`ListItemFormPlugin`, `group="Forms"`, `hideInKicker=true`) — hence covered here
too — but wired by id-linkage, not by a mapping table.

> 🛑 **Load-bearing invariant — without the matching list-item node, a List's Create/Edit button opens no form.**
> On click, `ListFormControlPlugin` resolves `formIdentifier = getRenderFormId(actionId)`
> (= `formIdByActionId[actionId] ?? actionId`, `ListFormControlSettings.java`
> `ListFormControlPlugin.java` create edit) and renders the `dynaform.list.item.plugin` **child of
> the List node whose `identifier` equals that `formIdentifier`**. So for every create/edit action
> there MUST be a child list-item node with `identifier == getRenderFormId(actionId)`, and that node must hold a
> `nct.parsis.plugin id="form.parsis"` grid whose fields bind to the temp context
> `__temp_list_item_context__` / `__temp_item__`. A hand-built List missing this renders a table whose
> Create/Edit buttons open an empty form (or nothing).

The list-item node has **no `settings` slot** — its `properties` keys are
`className`/`isParsis`/`styleName`/`tagProperties`. When an action is mapped through a `SubformSettings`, the id
== `SubformSettings.id`; an unmapped (legacy) action falls back to its own id. Two shapes you will meet in the
wild:

- **Legacy (no subforms):** List `e3d63a5b-…` — `subforms:null`, `formIdByActionId:null`,
  `createNewActions[0].id=58d4dbc0-…`; its single child list-item has `identifier=58d4dbc0-…` (== the action id).
- **Shared forms (Create + Edit → ONE form):** List `bb3c9d5e-…` — `subforms:[{id:c167f25e-…},{id:635a4d36-…}]`,
  `formIdByActionId:{c167f25e-…→c167f25e-…, 635a4d36-…→c167f25e-…}`; two child list-item nodes exist —
  `c167f25e-…` (the shared form rendered for both Create and Edit) and `635a4d36-…` (a legacy/orphan, no longer
  rendered).

```
dynaform.form.list.field.plugin   id=bb3c9d5e…   (subforms:[c167f25e, 635a4d36]; formIdByActionId:{c167f25e→c167f25e, 635a4d36→c167f25e})
 ├─ dynaform.list.item.plugin      id=c167f25e…   ← SHARED form (Create + Edit); props: className/isParsis/styleName/tagProperties — NO settings
 │   └─ nct.parsis.plugin          id="form.parsis"
 │       └─ gen_row_<batch> …      (generated grid; fields use __temp_list_item_context__ / __temp_item__)
 └─ dynaform.list.item.plugin      id=635a4d36…   ← legacy/orphan (Edit now resolves to c167f25e)
```

Full per-control detail, the node shape, and inner-field examples — [02-form-controls-reference.md](02-form-controls-reference.md)
§8. Generating the inner grid (from a list-item sub-form's "Auto add fields") —
[03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) "Nested-mode".

## Cross-links

- Form controls, per-control mapping/validation/events/hidden: [02-form-controls-reference.md](02-form-controls-reference.md)
- Generating form fields from CRUD: [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md)
- Actions in a CRUD table (settings, `properties.model.stringValue`): [04-crud-table-plugin.md](04-crud-table-plugin.md)
- CRUD tree / Process table (`process.table.pluin`, workflow-start actions): [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md)
- Workflow / user-task actions and their predicates: [07-workflows-and-tasks.md](07-workflows-and-tasks.md)
- Predicates, `service.actionId`, context: [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)
- Dynamic CRUD and resolution of `service.crud.<alias>`: [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md)
- Export format, `rep-objects.json`, `tenant.json`: [00-export-format-and-import.md](00-export-format-and-import.md)
- Content tree, `siteMapPage`, `properties`, `roleAccess`: [01-content-model-and-pages.md](01-content-model-and-pages.md)
- ⚠️ Older platform documentation on form groups, landings, forms and actions is partially outdated. What is
  wrong in it: the `order` field in mapping (does not
  exist), the `forms` field on the group (does not exist), a flat `name` on the action (really
  `localizedNames`/`localizedButtonNames`), a single `"on"/"off"` `direct` (in CRUD — boolean), the absence of
  `placeFormsNextToLanding`/`allowDrafts`/`submitForm`.
