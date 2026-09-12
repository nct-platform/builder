# 17 — Left-nav quick links (`site.kicker.plugin` / `modelGroups`)

> 📐 **Field evidence — the nav three deliveries converge on, and the two silent ways a grant dies:** [02-navigation-and-front-door.md](references/02-navigation-and-front-door.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> ⛔ **A nav link is localized on the ITEM, not (only) on its `linkModel`.** A nav entry is a
> `PageModel extends LocalizedBean`; the sidebar renders `getLocalized("name", locale)`, i.e.
> `localizedMap["name"][<locale>]` **on the item**, and falls back to the raw `name` property when the map
> has no entry for that locale. `linkModel.localizedMap` is a SECOND, inner map — filling only that one is
> invisible to the render, and the link then shows its `name` (one language) under every locale, which is
> what a three-locale project looks like when the whole sidebar comes out in the first language. The
> platform's own baseline links carry the map on BOTH objects — do the same. `quicklink add --label-loc`
> now writes both, and `validate` ERRORs on a link whose ITEM-level map does not cover every tenant locale.


> ⛔⛔ **THE LEFT NAV THAT RENDERS IS A SHARED "COMMON" VIRTUAL PLUGIN — NOT THE PER-PAGE KICKER NODES.**
> The branch ships a common virtual plugin named **`Nct left nav`** (`branch.virtualPlugins[]` whose
> `name == "Nct left nav"` → its `content`, `identifier: "left-nav"`; in `initialtemplates/empty.mrjun` its
> `uniqueIdentifier` is `23ab2aca-…`). **Every** page's per-page `site.kicker.plugin` node carries a
> `linkContentIdentifier` equal to **that `uniqueIdentifier`**, so `PluginPanel.getContent()` (`mrjun-cms-view
> PluginPanel`, via `findOneByUniqueIdentifier`) resolves the render to the **shared** node and the per-page
> `modelGroups` are **DEAD DATA — never read at runtime**. So: **put quick links in the `Nct left nav` common
> node's `modelGroups`**, not in per-page kicker nodes. `mrjun.py quicklink add` now does this automatically
> (targets the shared node via `_target_nav_nodes`); if you hand-edit, edit `virtualPlugins[] name="Nct left nav"` →
> `content` → `properties.modelGroups`. The console you see by default (`Home, Rules, Contexts, … Settings`) is
> the shared node's own `Pages` group — **ordinary data**, editable (and prunable / role-gateable) like any
> other item; **append** your business pages there or in a new group (e.g. `Operations`), and never rewrite
> `pagesModel` wholesale (Gotcha 8). *(Symptom this caused: quick links added "successfully" to every
> populated per-page nav never appeared — because none of those nodes render.)*

## What it is / when to use

The **left navigation** ("left-nav") in the layout is a `site.kicker.plugin` content node whose `identifier`
is the symbolic id **`left-nav`** (a layout child, like `header`/`footer`/`parsis`; see the layout wiring in
[01-content-model-and-pages.md](01-content-model-and-pages.md) and the page-template ids in the toolkit's
`page add`). Its menu — the **quick-links tree** — is NOT stored as child content nodes; it is a single JSON
string in the node's property **`modelGroups`**.

> ✅ **After building business pages, ADD THEM to the left-nav** — a page the user can't reach from the nav is
> effectively invisible. Every `crud.table` / `crud.tree` / `process.table` / dashboard page you create should
> get a `quicklink add --page <name> --group <Group>`. Note `quicklink add` only edits **already-populated**
> left-navs (it skips empty `{}` navs), and it resolves `--page` to the page's current `identifier` — so run it
> **after** all pages exist (a rebuild that regenerates page identifiers invalidates links added earlier).

> ⛔ **`Pages` IS THE AUTHOR'S DRAWER, NOT THE USER'S.** The group the baseline ships under that name holds the
> management console — Sources, Queries, Rules, Contexts, Database, Business Logic, Users, Roles, Schedulers,
> Settings, Audit Logs, Mail/PDF templates, Workflows, Processes, Form Groups. Those exist for the integrator
> who BUILDS the project, not for the clerk who USES it. Putting business pages in there buries them among
> twenty admin links and tells the end user that this product is a developer console.
>
> **So: business pages go in BUSINESS-NAMED groups**, in the words the PRD uses — "Case management",
> "Procurement", "Regulator and audit", "Stock". Group headings are localized (`--group-loc`, doc 20).
>
> ⛔ **And `Home` must be MOVED OUT of `Pages`.** Home is the product's front door — the dashboard, the main
> worklist, the screen a role lands on at login. It is not an authoring page and it must not sit in the
> authoring drawer, which is where a build that only ever calls `quicklink add` leaves it. Two commands, and
> the second one names it in business terms rather than "Home":
>
> ```bash
> mrjun.py quicklink rm  --project ./app --label Home
> mrjun.py quicklink add --project ./app --page Home --group "<first business group>" \
>          --label-loc en_US="Cockpit" --label-loc hy_AM="…" --icon pe-7s-graph2
> ```
>
> It goes **FIRST in the FIRST business group** — the top item of the sidebar, above the registers it links to
> — with a chart/dashboard icon (`pe-7s-graph2`, `pe-7s-display1`, `pe-7s-airplay`), never the generic
> `pe-7s-angle-right`. Call it what the business calls that screen ("Cockpit", "Command centre", "My work"),
> not "Home": "Home" is the node's name, not a menu label anyone asked for.
>
> While you are there, clear the baseline's own demo links out of `Pages` — it ships `Sourcese` (sic),
> `Queries` and `Dashboars` (sic), and the last one is DANGLING: it points at a page identifier the baseline
> no longer has, which is one of the warnings in `initialtemplates/empty-validate.txt`. `quicklink rm --label`
> matches the label, including the typos, and matches per-locale labels too.

> ✅ **The other half of the mandate is WORKFLOW-driven, not page-driven.** The rule above walks PAGES, so a
> worklist parked in a tab of an already-linked page satisfies it vacuously — nothing warns, because the
> reachability check warns per `siteMapPage` and the host page is linked (`_check_homepage_and_nav`,
> `validate_cmds.py`), and no quick link can address a tab anyway ([05](05-crud-tree-and-process-table.md)
> ⭐ recipe, Placement). So also walk `rep-objects.json.workflows[]`: **every workflow must have a worklist page
> that is itself a quick link** ([07](07-workflows-and-tasks.md) §"Step 5 — the worklist page (NOT optional)") —
> a workflow reachable only from a tab, a row action or the admin Processes console is one users never run. And
> **the front door page gets a quick link too**, so a user who navigated away can get back to it — as the FIRST
> item of the FIRST business group, never inside `Pages` (see the ⛔ above)
> ([21](21-homepage-and-redirect.md) §"Choosing the front door — chart dashboard or main worklist").

Read this doc when you need to **add a quick link (or a whole group) to the left nav directly in the export
file** — i.e. author/patch the `modelGroups` JSON so a re-imported project shows the link in the sidebar.

Related: the plugin itself is catalogued in [14-plugin-catalog-all.md](14-plugin-catalog-all.md)
(`site.kicker.plugin`, group `Site`); pages/content model in [01](01-content-model-and-pages.md).

## Export shape — where the tree lives

The `left-nav` node lives inside every page's materialized layout. Its config slot is
`properties.modelGroups.stringValue` — a **JSON string** (like all typed property slots; see
[01](01-content-model-and-pages.md)). Decoded, that string is:

```json
{
  "pagesModel": [ <PageModel>, <PageModel>, ... ]
}
```

`pagesModel` is an ordered list of top-level items. Each item is a **`PageModel`** that is either a **group**
(a heading/folder with `children`) or a **link** (carries a `linkModel`). Groups can nest links, and links can
themselves have `children` (sub-menu).

### `PageModel` (a tree node — group or link)

| Field | Type | Meaning |
|---|---|---|
| `order` | int | sort order among siblings |
| `name` | String | display label (default locale); localized copies live in `linkModel.localizedMap` for a **link**, or in this node's own `localizedMap` (below) for a **group** |
| `uuid` | String (uuid) | this tree node's own id (must be unique within the tree) |
| `parentUuid` | String (uuid) | uuid of the parent group; omit/`null` for a top-level item |
| `icon` | String | icon class (Pe-icon-7-stroke `pe-7s-*`, Linearicons `lnr-*`, or a plain name like `globe`) |
| `heading` | boolean | `true` = a non-clickable section heading; usually `false` |
| `linkModel` | object | present ⇒ this node is a **link** (see below); absent/`null` ⇒ this node is a **group/folder** |
| `roleAccess` | object | optional per-item `RoleAccess` (same shape as node `roleAccess`, see [01](01-content-model-and-pages.md)) — role-group membership is checked here exactly as it is on a content node; see the note below. Omit ⇒ `publicReadAccess:true` ⇒ visible to everyone |
| `localizedMap` | object | `PageModel extends LocalizedBean`, so a node carries its own `{"name":{"en_US":…,"ru_RU":…}}` (same shape as `linkModel.localizedMap`). For a **group/heading** (no `linkModel`) this is the **only** place to localize the heading label; see [20-localization.md](20-localization.md) |
| `children` | `PageModel[]` | nested items (empty `[]` for a leaf link) |

> ✅ **Hiding a link from a persona.**
> Set it on the item (or on the whole group/section, which prunes its children too):
> ```jsonc
> "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": true, "accessors": {},
>                 "roleGroupAccessors": { "<Back Office>": { "view": true, "edit": false, "advancedEdit": false } } }
> ```
> Members of `<Back Office>` (plus admin/author, who always see everything) get the link; everyone else never
> receives the markup, and a section whose every child is hidden is pruned as well. `quicklink add` does not
> write this — add it by hand to the item in the kicker model.
> ⛔ **This is navigation, NOT access control.** Hiding the link does nothing to the page: it stays reachable
> by URL until you set the same `roleGroupAccessors` on the **page node** too
> ([01](01-content-model-and-pages.md)) — and even then the real gate on data is the action predicates plus the
> scoped fetch rule ([19](19-build-decision-procedure.md) Phase 6).

### `linkModel` (present only on a link) — `IconNamedLinkModel`

| Field | Type | Meaning |
|---|---|---|
| `name` | String | link text (default locale) |
| `icon` | String | icon class |
| `identifier` | String (uuid) | **for an internal link: the `identifier` of the target `siteMapPage` content node** (resolved within the active branch) |
| `internal` | Boolean | `true` (default) ⇒ internal page link by `identifier`; `false` ⇒ external link — use `link` |
| `link` | String | external URL (used only when `internal == false`) |
| `params` | String | optional query/path params appended to the internal link (`ContentLinkByIdentifierParams.params`) |
| `needToBeSaved` | boolean | authoring housekeeping flag; set `true` on hand-authored items |
| `localizedMap` | object | per-locale values: `{"name":{"en_US":…,"ru_RU":…,"hy_AM":…}, "icon":{…}}` — cover every locale in `tenant.json.locales` |

### Real example (verbatim from `empty`, one group `Pages` with a link to the `Sources` page)

`site.kicker.plugin` node (`identifier == "left-nav"`), `properties.modelGroups.stringValue` decoded — this is
the 1512-char **per-page** copy, quoted here for its **shape**; the node you actually edit is the shared
`Nct left nav` one, whose `Pages` group holds the 15 console links (Gotcha 8):

```json
{
  "pagesModel": [
    {
      "order": 0,
      "name": "Pages",
      "uuid": "62492f05-4e61-42dd-a659-6a391504e843",
      "icon": "globe",
      "heading": false,
      "children": [
        {
          "order": 0,
          "name": "Sourcese",
          "uuid": "8b639b71-a51c-4daa-8a85-270a5484fa0e",
          "parentUuid": "62492f05-4e61-42dd-a659-6a391504e843",
          "icon": "pe-7s-server",
          "heading": false,
          "linkModel": {
            "icon": "pe-7s-server",
            "name": "Sourcese",
            "identifier": "03e4579a-f1bc-4d35-9bb2-fc5515c52c9d",
            "internal": true,
            "needToBeSaved": true,
            "localizedMap": {
              "name": { "ru_RU": "Sources", "en_US": "Sourcese", "hy_AM": "Sources" },
              "icon": { "ru_RU": "pe-7s-server", "en_US": "pe-7s-server", "hy_AM": "pe-7s-server" }
            }
          },
          "children": []
        }
      ]
    }
  ]
}
```

Here `linkModel.identifier` `03e4579a-…` is the content `identifier` of the `Sources` `siteMapPage`
(verified: it resolves to `{name:"Sources", pluginName:"siteMapPage"}`).

## How a link resolves at render (`PagesPanel`)

- **Internal** (`internal == true`): the item becomes a `ContentLink` built from
  `ContentLinkByIdentifierParams(activeBranchId, linkModel.identifier, linkModel.params)` — the platform looks
  up the content node whose `identifier == linkModel.identifier` in the current branch and links to it. So the
  **join key is the target page's `identifier`** (not its alias, not a URL).
- **External** (`internal == false`): `href = linkModel.link` (the raw URL). No external links appear in any of
  practice, but the code path exists.
- Neither resolvable ⇒ `href = "#"`.
- A **group** (no `linkModel`, has `children`) renders as a collapsible sidebar section labelled by its `name`.

## How to construct from scratch — add a quick link

To add a quick link to the left nav in an unpacked export:

1. **Find the target page's `identifier`.** The link points to a `siteMapPage` by its content `identifier`
   (e.g. via `tools/mrjun.py find --plugin siteMapPage` or `list pages`, or jq on `branches.json`). Copy that
   `identifier` — it becomes `linkModel.identifier`.
2. **Locate the ONE node that renders — the shared common left-nav.** It is the entry in
   `branches.json[0].virtualPlugins[]` whose `name == "Nct left nav"` → its `content` object
   (`pluginName: site.kicker.plugin`, `identifier: left-nav`). ⛔ Do **not** hunt for it with
   `mrjun.py find --plugin site.kicker.plugin`: `find` walks `rootContent` only, so it returns exclusively the
   per-page nodes, which are dead data (see the ⛔ callout at the top and Gotcha 1).
3. **Decode** that node's `properties.modelGroups.stringValue` (JSON string → object).
4. **Add a link item** under the desired group's `children` (or add it to `pagesModel` top-level). A link item:
   ```json
   {
     "order": <next order among siblings>,
     "name": "My Widgets",
     "uuid": "<fresh uuid4>",
     "parentUuid": "<the enclosing group's uuid, or omit if top-level>",
     "icon": "pe-7s-note2",
     "heading": false,
     "linkModel": {
       "name": "My Widgets",
       "icon": "pe-7s-note2",
       "identifier": "<target siteMapPage identifier from step 1>",
       "internal": true,
       "needToBeSaved": true,
       "localizedMap": {
         "name": { "en_US": "My Widgets", "hy_AM": "My Widgets" },
         "icon": { "en_US": "pe-7s-note2", "hy_AM": "pe-7s-note2" }
       }
     },
     "children": []
   }
   ```
   - Cover **every** locale from `tenant.json.locales` in `localizedMap.name`/`localizedMap.icon`.
   - For an **external** link: set `"internal": false` and `"link": "https://…"`, and drop `identifier`.
5. **To add a new group/folder** instead, push a `PageModel` with **no** `linkModel` and a `children` array:
   ```json
   { "order": <n>, "name": "Reports", "uuid": "<fresh uuid4>", "icon": "globe", "heading": false, "children": [ … ] }
   ```
   Give the group a fresh `uuid`; its child links set `parentUuid` to that uuid.
6. **Re-encode** the object back to a JSON string and write it into `properties.modelGroups.stringValue`.
7. **Nothing to repeat** — that one shared node serves every page. Then `validate` and `pack`.

## Gotchas

1. **The per-page `left-nav` nodes are DEAD DATA — the shared `Nct left nav` common plugin renders (see the ⛔
   callout at the top of this doc).** Each page's materialized layout contains its own `site.kicker.plugin`
   id=`left-nav`, but each has a `linkContentIdentifier` → the shared common node, so `getContent()` renders the
   shared node and the per-page `modelGroups` are never read. Edit the shared node (`virtualPlugins[] "Nct left
   nav"` → `content`), which `quicklink add` now does. *(The counts below describe the per-page nodes, which is
   why editing them looked "successful" but changed nothing.)* In `empty` there are **30** per-page nodes with **2**
   distinct states: the standard `Pages` nav (**1512 chars, 1 group**, on **18** pages **including the Home/root
   page**) and empty `{}` (**12** pages — the system/management pages). The **~19 KB "management nav" DOES
   exist**, but it is not one of those: it is the **shared** `Nct left nav` node's own `modelGroups`
   (19,474 chars in `empty`), holding the 15 management-console links (Gotcha 8). The two per-page states are
   dead copies; neither renders.
   **A quick link renders — on EVERY page — ONLY when you edit the shared `Nct left nav` common node**
   (`virtualPlugins[] name="Nct left nav"` → `content` → `properties.modelGroups`). **Editing a per-page
   `left-nav` node — even to try to customize just ONE page's sidebar — changes NOTHING at runtime**:
   `getContent()` (`PluginPanel.java`) resolves every per-page node's `linkContentIdentifier` back to
   the shared node, so the shared tree renders on all pages and the per-page `modelGroups` are never read.
   **There is NO per-page sidebar to customize.** `quicklink add` targets the shared node for you
   (`_target_nav_nodes` returns only the shared node when present). The front door only lands on the Home/root
   page if `Home.Redirect` is empty (see doc 21); the shared nav renders there like everywhere else.
2. **`modelGroups` is a JSON STRING** inside the property slot (`properties.modelGroups.stringValue`), not a
   nested object — always parse → mutate → re-stringify; never leave it malformed. Empty state is the literal
   string `"{}"`.
3. **Internal join key = target page `identifier`**, resolved within the active branch. If the identifier does
   not match a `siteMapPage` in the branch, the link renders as `href="#"`.
4. **`uuid` must be unique** within the tree; `parentUuid` must equal the enclosing group's `uuid`. `order`
   controls sibling sort.
5. **Localization:** a **link** localizes via `linkModel.localizedMap`; a **group/heading** has no `linkModel`,
   so it localizes via the `PageModel`'s **own** `localizedMap` (`PageModel extends LocalizedBean`) — the
   only way to translate a group heading. The top-level `name`/`icon` are the default-locale fallback. Cover all
   `tenant.json.locales`. See [20-localization.md](20-localization.md).
6. **`icon`** accepts Pe-icon-7-stroke (`pe-7s-*`), Linearicons (`lnr-*`), or plain names (`globe`); see the
   icon reference used across actions.
7. This node is a `site.kicker.plugin` (property slot `modelGroups`), so it is NOT reachable via
   `node add`'s `--settings`/`--model` routing — the config lives in the `modelGroups` slot. Use the `quicklink`
   tooling below (or a raw slot edit).
8. **The platform "management console" nav (`Home, Rules, Contexts, Form Groups, Workflows, Processes, Users,
   Role Management, Database, Business Logic, Audit Logs, Mail Templates, Pdf Templates, Schedulers, Settings`)
   IS `modelGroups` data — it is the shared `Nct left nav` node's own `Pages` group** (15 ordinary `PageModel`
   links, the ~19 KB blob of Gotcha 1), and you can edit it from the export. `PagesPanel.getAllModelGroups()`
   renders the sidebar as *runtime-injected groups ∪ the shared node's `modelGroups`*; the injection (an
   `Add_Model_Groups` Wicket event fired from `NctBasePlugin.onInitialize()` via a plugin's `pageGroups(...)`)
   contributes only a handful of **per-plugin action links** — "Create new source", "Create new query" and the
   like on the platform's own admin pages — never the page list. Consequences:
   (a) you **should** append your business pages to that same `Pages` group — exactly what
   `quicklink add --group "Pages"` does;
   (b) ⛔ **never replace `pagesModel` wholesale.** Parse → append → re-stringify: writing a fresh
   `{"pagesModel":[…]}` of your own links deletes Settings / Database / Rules / Business Logic / Mail & Pdf
   Templates / Schedulers from **every** page of the project, and neither `validate` nor `pack` flags it;
   (c) because they are data, you can also **prune or role-gate** them for an end-user portal — put a
   `roleAccess` on the item or on the whole `Pages` group (see the note under `PageModel`) to keep
   `Rules`/`Database`/`Business Logic`/`Settings` out of an operator's sidebar;
   (d) the console renders on every page — including one whose *per-page* `modelGroups` is empty — which is why
   a **blank root/Home with no `Redirect` looks like "only the default menu, none of my links"**: the fix is the
   front door (doc 21) + your links in the **shared** node, never a per-page edit.

> **🔧 Tooling.** `tools/mrjun.py` has left-nav commands (they find the shared node for you):
> `quicklink list` — print the quick-links tree(s); `quicklink add --page <target page id|name> …` — **append**
> an internal quick link to the shared `Nct left nav` node (fresh uuid, localizedMap for every
> `tenant.json` locale; idempotent — re-running with the same target adds nothing, and the console links already
> in the group are left intact). ⚠️ **Label localization:** `--label <s>` copies ONE string into every locale —
> correct ONLY for a single-language project. For a multilingual nav pass **`--label-loc <locale>=<text>`** per locale
> (`--label-loc en_US=Home --label-loc hy_AM=Տուն --label-loc ru_RU=Главная`); a single `--label` on a 2+-locale
> project warns, and `validate` flags a nav name identical across all locales (the "one language under all
> locales" bug — [20-localization.md](20-localization.md)). `[--group <name>] [--group-loc <locale>=<text>]
> [--icon <c>] [--params <s>]` as before. ⚠️ `--group` alone leaves the section HEADING single-language
> (Gotcha 5) — pass `--group-loc` per locale; `quicklink add` warns and `validate` flags it.
> See [tools/README.md](tools/README.md). Prefer these over hand-editing so the tree stays consistent.
