# 02 — Navigation and the front door

> **Corrects and extends** [[17-left-nav-quick-links.md](../17-left-nav-quick-links.md)](../17-left-nav-quick-links.md) and
> [[21-homepage-and-redirect.md](../21-homepage-and-redirect.md)](../21-homepage-and-redirect.md). Everything here was measured in four
> delivered exports before they were deleted. They are referenced only as:
>
> | | size | shape |
> |---|---|---|
> | **A** | 433 pages · 163 dynamic CRUDs · 22 hand-authored studio consoles | the large suite — and the nav anti-pattern (§7) |
> | **B** | 129 pages · 38 CRUDs · 3 locales | |
> | **C** | 128 pages · 31 CRUDs · 87 charts | analytics-dense; the reference build for gating |
> | **D** | 67 pages · 12 CRUDs · 1 workflow | small, single-domain PoC |
>
> Evidence is stated as "3 of 4", "A only", "B and C". Entity and group names below are neutral
> stand-ins (`document`, `case`, `item`, `partner`, `<Operator>`); every slot name, JSON key, uuid,
> CSS class and count is verbatim.

---

## 0. The verdict

Three of the four converge on the **same** left-nav shape, to the field: leave the platform's `Pages` drawer
exactly where the baseline put it (top-level, `order: 0`, uuid `62492f05-…`), **role-gate the whole group to
`Author`** so no end user ever sees it, remove `Home` from it, and hang the business app off **sibling
top-level groups named in the customer's own vocabulary**, each 1–9 links deep, ordered the way work flows
through the business, with the product's main screen as the **first link of the first business group**. Depth
never exceeds two (group → link). Every business page that is a top-level page is linked; nothing else is.

**All four** wire the front door identically: root `Home`, `Redirect: ""`, no alias, `chart.js.plugin` nodes
authored into Home's own parsis.

The fourth (A) did the nav the opposite way — one business "folder" with 21 children **inside** the authoring
drawer, `Home` duplicated, and a second group whose eleven entries are fake folders that navigate to a leaf.
§7 itemises what that produced, because each defect is individually tempting.

---

## 1. Constants you can rely on without looking anything up

Same values in 4 of 4 exports.

| Thing | Value |
|---|---|
| The node that renders the sidebar | `branch.virtualPlugins[]` where `name == "Nct left nav"` → `.content` (`pluginName: site.kicker.plugin`, `identifier: "left-nav"`) |
| Its `uniqueIdentifier` | `23ab2aca-20c7-4a8c-af0c-f38c9b8e01bc` |
| Every per-page kicker's `linkContentIdentifier` | `23ab2aca-20c7-4a8c-af0c-f38c9b8e01bc` — **755 / 755 nodes** across the four |
| The `Pages` group's uuid | `62492f05-4e61-42dd-a659-6a391504e843` |
| The root page's `identifier` | `34c97297-185b-41b7-a255-f37895984a1c` (this is `Home`, `parentId == null`) |
| Root page `alias` | `null` — never set |
| Root page `Redirect` | `""` (empty) |
| Root page `layout` | `Nct layout` (business pages use `Main`, generated form pages use `Form`) |

The five-node frame the root renders inside is the same generated stack as every other page — your cockpit
goes in the `parsis` slot, and the sidebar is a sibling you never touch from the page:

```
siteMapPage → parsis.plugin → Layout (html.plugin, the shell — DO NOT EDIT)
   ├── header / logo-plugin / breadcrumb
   ├── left-nav      site.kicker.plugin      ← delegates to the shared "Nct left nav"
   ├── parsis        nct.parsis.plugin       ← YOUR SCREEN
   └── footer / right-kicker
```

### 1.1 The per-page `modelGroups` copies are provably dead — with the counts that prove it

Doc 17 asserts this from source. Here is the field evidence: per-page `site.kicker.plugin` nodes, and the
length of their `modelGroups.stringValue`.

| | per-page kicker nodes | `"{}"` (2 chars) | baseline stub | the shared node's real `modelGroups` |
|---|---|---|---|---|
| A | 431 | 101 | 330 × 1512 chars | 113,744 chars |
| B | 129 | 12 | 117 × 1512 chars | 59,793 chars |
| C | 128 | 10 | 118 × 1831 chars | 60,124 chars |
| D | 67 | 10 | 57 × 1512 chars | 27,451 chars |

Decode any of those 1512-char stubs in **any** of the four shipped projects and you get the untouched factory
demo, typos and all:

```json
{"pagesModel":[{"name":"Pages","children":[
   {"name":"Sourcese"}, {"name":"Queries"}, {"name":"Dashboars"} ]}]}
```

**Four delivered customer systems, 622 populated per-page copies, not one ever updated.** That is the proof
they render nothing: if they rendered, every page in every project would show a three-item menu with two
spelling mistakes.

⛔ **A nav command that reports "updated 118 nodes" has almost certainly updated 118 dead nodes.** C's dead
copies are 1831 chars and have lost `Dashboars` — a label-removal command reached the dead copies, the
operator saw no change on the page, because there was no change to see. **The only success signal is the byte
length of the shared node's slot changing:**

```bash
jq -r '.[0].virtualPlugins[] | select(.name=="Nct left nav")
       | .content.properties.modelGroups.stringValue | length' work/branches.json
```

Run it before and after every nav edit. Equal numbers mean you edited nothing that renders.

---

## 2. The front door — 4 of 4 did the same thing

**Decision: leave `Redirect` empty and author the cockpit into Home's own parsis.** The failure it prevents is
the redirect hop that resolves to a blank shell — a dashboard page whose queries return nothing renders as an
empty page at the bare project URL, and the reporter says "I opened the project and saw no charts".

Doc 21 offers a two-rung ladder and calls rung 1 (charts on Home, blank `Redirect`) the default. **All four
took rung 1. Nobody used `Redirect` at all — not once, in 757 pages.** Doc 21 should say that: rung 2 is a
theoretical fallback, not a coin flip.

| | `Home.Redirect` | charts in Home's parsis | `global.replacement.plugin` filter bar | `nct.label.plugin` KPI labels | `nct.parsis.plugin` grid cells |
|---|---|---|---|---|---|
| B | `""` | 9 | 1 | 23 | 10 |
| C | `""` | 13 | 1 | 19 | 1 |
| D | `""` | 10 | 1 | 3 | 11 |
| A | `""` | 9 | **0** | **0** | 1 |

✅ **Read the last three columns as the composition test.** B and D have ~10 parsis cells holding 9–10 charts
— a real grid of unequal columns; C has one parsis with 13 charts and a 19-label KPI strip above them. A has
**one** parsis, **one** html node and nine charts dropped in, no KPI strip and no filter bar. Same rung of the
ladder, opposite quality. The grid-dump is what
[[22-charts-params-and-filters.md](../22-charts-params-and-filters.md)](../22-charts-params-and-filters.md) §2B.1 exists to prevent.

✅ **One `global.replacement.plugin`, above the grid rows** (3 of 4). It is the *chart* filter bar
(`parametersOfQueryHasBeenChanged`), not `dynaform.filter.form.plugin` (whose `onFilterSubmit` only tables
listen to). Order inside the content parsis: header html → filter bar → grid-row nodes. The one project that
skipped it is the one with no KPI strip either.

⛔ **Never give the root an alias, and never document a `/home` URL.** `alias` is `null` in 4 of 4. One
project shipped a user manual printing `https://…/<project>/home` as the address of the main screen — there
is no page with alias `home` in that export, so the link 404s. The front door's URL is the **bare project
URL**: the nav link resolves through `ContentLink` → `calculatePageUrl`, which prefixes the *target's own*
alias, and the root has none. Doc 21 warns you not to alias the root; it does not warn that your own generated
README will invent the alias for you. Grep every emitted document for `/home`.

⛔ **Do not ship a front door pinned to one entity by a default param.** Two of the four put a non-empty
default into their Home charts' param map — e.g. `{"<Partner>":{"value":"<one specific partner>"}}` on 9 of 10
charts — so the cockpit opens showing one slice while the filter bar reads "all". The reviewer's first
impression is a dashboard whose numbers do not match the data. Defaults belong on a date window, nothing else;
see [[22-charts-params-and-filters.md](../22-charts-params-and-filters.md)](../22-charts-params-and-filters.md) §4.

⛔ **Gate the root PAGE as `authenticatedUserAccess: true`, and check it.** Two of the four shipped `Home`
with `publicReadAccess:false, authenticatedUserAccess:false` and **no** `roleGroupAccessors` grant at all. It
renders for their users only because the boilerplate `accessors` stanza grants `view` to holders of
`file_storage_view`, which every persona happened to hold. Tighten those role groups later and the front door
disappears for everyone. Neither doc 21 nor doc 17 mentions the root page's own `roleAccess`; the reference
build (C) has Home `authenticated:true` and everything else persona-gated.

---

## 3. The nav, in build order

### 3.1 `Pages` stays where it is — and gets gated, not moved

**Decision: keep the authoring drawer at `order: 0` with its baseline uuid, and put one `roleAccess` on the
group node.** The failure it prevents is a rewritten `pagesModel` that silently deletes `Settings`, `Database`,
`Rules`, `Business Logic`, `Mail/Pdf Templates` and `Schedulers` from every page of the project — and the
softer failure of an end user whose first impression of the product is a developer console.

All three good builds answered identically:

- `Pages` keeps `order: 0` and its baseline uuid. **Not moved, not renamed, not deleted.**
- Its `Home` child (which was `order: 0`) is removed, leaving children at `order: 1…14` with a hole at 0.
  **That order-0 hole is the fingerprint of a correct build.**
- One `roleAccess` on the group prunes all fourteen console links in a single stroke.

```jsonc
{
  "order": 0,
  "name": "Pages",
  "uuid": "62492f05-4e61-42dd-a659-6a391504e843",
  "icon": "globe",
  "heading": false,
  "roleAccess": {
    "publicReadAccess": false,
    "authenticatedUserAccess": false,
    "accessors": { "admin":      {"view":true,"edit":true,"advancedEdit":true},
                   "nct_author": {"view":true,"edit":true,"advancedEdit":true}
                   /* …26 more platform permission keys, all false — boilerplate… */ },
    "roleGroupAccessors": { "Author": {"view":true,"edit":true,"advancedEdit":true} }
  },
  "localizedMap": { "name": { "hy_AM": "Էջեր", "ru_RU": "Страницы", "en_US": "Pages" } },
  "children": [ /* Rules … Settings, order 1..14, left exactly as shipped */ ]
}
```

✅ **Because the group prunes, you do not have to touch the fourteen children.** D proves it: twelve of its
console links still carry `publicReadAccess: true` from the baseline and no operator sees them, because the
parent is gated.

⛔ **The enumerate-and-deny variant costs a line per role and breaks a persona.** B listed all eight of its
role groups on the `Pages` group and set `view: false` for the six business ones. It works — and in that same
file the customer-administrator persona got `{"view": false, "edit": true, "advancedEdit": true}`, i.e. **edit
without view**. The render check reads `view`. The persona whose entire job is the console could not open a
single console page. **Prefer the one-line `Author`-only form.** Enumerate-and-deny only when a non-author
persona genuinely needs part of the console, and then gate the individual link, not the group.

> **Correction to [[17-left-nav-quick-links.md](../17-left-nav-quick-links.md)](../17-left-nav-quick-links.md).** Gotcha 8(a) — *"you
> **should** append your business pages to that same `Pages` group"* — contradicts the doc's own ⛔ callout
> ("`Pages` IS THE AUTHOR'S DRAWER"), and 3 of 3 good builds side with the callout. **Never `--group Pages`
> for a business page.** 8(a) is right about one thing only: *append*, never replace, the blob you are editing.
> The doc never says what to do with the `Pages` group itself (role-gating is an aside in 8(c)) and it says
> business groups go first, where 3 of 3 left `Pages` first and gated it. **Jump the way the projects jumped:**
> gating is idempotent, survives a re-run of `add --group Pages`, and does not renumber the baseline.
> Reordering does none of those.

### 3.2 Business groups — naming, count, size, order

**Decision: one top-level group per business domain, named in the customer's words, holding 1–9 links, ordered
the way work flows.** The failure it prevents is a nav generated by dumping pages into a tree — which is
exactly what A did, and why 12 of its pages are unreachable.

Every business group is a **real group**: a `PageModel` with `children` and **no `linkModel`**. In B, C and D
there are **zero** links carrying children. `heading` is `false` on every item in the corpus — the collapsible
section behaviour comes from having children and no `linkModel`, not from the flag.

| | groups (neutralised names, in shipped order) |
|---|---|
| B | Dashboards · Reference data · Demand documents · Supply documents · Unit holdings · Operations · Queues · Reports · Settings |
| C | Cases · Restrictions · External parties · Oversight · Configuration · Reports |
| D | one group, named for the single domain the PoC covers |

✅ **The nav is the product's information architecture: the manual's contents page and the nav's `pagesModel`
are the same object.** B's delivered manual has that same nine-item list as its table of contents, and its
orientation section opens *"Nine groups in the left menu. You see only the screens your role is allowed to
open."* **If you cannot write the manual's contents page from your group list, the group list is wrong.**
Write the group list *before* you build the nav — all three good builds did.

Sizing, measured:

| | business groups | business links | links per group |
|---|---|---|---|
| B | 9 | 41 | 1, 2, 2, 4, 4, 5, 6, 8, 9 |
| C | 6 | 30 | 2, 3, 4, 6, 7, 8 |
| D | 1 | 13 | 13 |

**Never more than nine links in a group; median 4–6.** A one-link group is legitimate — the group exists to
name a business domain, not to fill a quota. A single group is legitimate for a small single-domain PoC, but
13 links in one group is the top of the range; past that, split by domain.

Group order is **the order work flows through the business** — not alphabetical, not by page count:

- B: cockpit → reference/master data → demand-side documents → supply-side documents → unit holdings →
  operations → approval queues → reports → settings.
- C: case lifecycle → the containment action → external parties → oversight review → configuration →
  reports.
- D (one group, links in flow order): front door → cases → performance → warnings → requests → documents →
  dispatch → receipt → balances → item master → partners → engine configuration → routing rules.

Two of three put **Reports second-from-last** and configuration/settings last; the third puts configuration
before reports. That is the only ordering disagreement in the corpus and it does not matter. The rule that
does: **operational screens first, reference and configuration last, in flow order.**

### 3.3 The front-door link — first item of the first business group

**Decision: the link to the root page is `pagesModel[1].children[0]`.** The failure it prevents is a user who
drills into a record and has no way back to the cockpit except editing the URL.

3 of 3 did it, with a twist doc 17 does not mention: the link targets the **root page identifier**
`34c97297-185b-41b7-a255-f37895984a1c`, and because the root has no alias it resolves to the bare project URL.

| | group | `order` | label | icon |
|---|---|---|---|---|
| B | first business group (Dashboards) | 0 | "Home" in all three locales | `pe-7s-home` |
| C | first business group (Cases) | 0 | renamed to the business's word for it ("Command centre") in all three locales | `pe-7s-graph3` |
| D | the only business group | 0 | "Home" in all three locales | `pe-7s-home` |
| A | ✗ inside `Pages` at order 0, **plus a duplicate** two levels deep | 0 / 1 | "Home" + "Dashboard", same target | `pe-7s-home` / `pe-7s-graph3` |

Doc 17 tells you to rename it to what the business calls that screen. **Only one of three did.** This is a
genuine convention split, and the practical read is that renaming is a nicety while *position* is load-bearing:
the item that is first in the first business group is the front door whatever it is called. If you do rename,
rename in **all** locales, and read the icon trap in §3.5 first — the one project that renamed still shows a
house icon under every locale because of it.

### 3.4 Per-item role gating — pick one school and apply it everywhere

**Decision: gate every link; leave group headings ungated.** A heading whose children are all hidden is pruned
anyway, so gating the heading is redundant — and gating it wrongly is how you lock a persona out (§3.1).

| | items with `roleAccess` | without | of those gated, `publicReadAccess: true` |
|---|---|---|---|
| B | 56 / 65 | 9 (the group headings) | 0 |
| C | 45 / 51 | 6 (the group headings) | 0 |
| D | 17 / 29 | 12 (**all business links**) | 12 (console links, inherited) |
| A | 45 / 173 | 128 | **40** |

D left its business links ungated entirely — a deliberate simplification for a single-persona PoC, not an
example to copy into a multi-role build. Omitting `roleAccess` means `publicReadAccess: true`, i.e. visible to
everyone.

The link shape, verbatim in structure (three locales, seven role groups):

```jsonc
{
  "order": 0,
  "name": "<default-locale label>",
  "uuid": "b0e81013-85a9-49d1-bb0f-d465d8f1c7ed",
  "parentUuid": "fd709938-7980-4dd2-ac1c-590d5b2cfdb7",   // == the enclosing group's uuid
  "icon": "pe-7s-albums",
  "heading": false,
  "children": [],
  "localizedMap": { "name": { "hy_AM": "…", "ru_RU": "…", "en_US": "Management packs" } },
  "linkModel": {
    "name": "<default-locale label>",
    "icon": "pe-7s-albums",
    "identifier": "1fb9e964-ce5e-4b96-aef8-4bd9c3586073",  // target siteMapPage identifier
    "internal": true,
    "needToBeSaved": true,
    "localizedMap": {
      "name": { "hy_AM": "…", "ru_RU": "…", "en_US": "Management packs" },
      "icon": { "hy_AM": "pe-7s-albums", "ru_RU": "pe-7s-albums", "en_US": "pe-7s-albums" }
    }
  },
  "roleAccess": {
    "publicReadAccess": false,
    "authenticatedUserAccess": false,
    "accessors": {},
    "roleGroupAccessors": {
      "<Reviewer>":           {"view": true,  "edit": false, "advancedEdit": false},
      "<Auditor>":            {"view": true,  "edit": false, "advancedEdit": false},
      "<Team Lead>":          {"view": true,  "edit": true,  "advancedEdit": false},
      "<Operator>":           {"view": true,  "edit": true,  "advancedEdit": false},
      "System Administrator": {"view": true,  "edit": true,  "advancedEdit": false},
      "Author":               {"view": true,  "edit": true,  "advancedEdit": true},
      "Developer":            {"view": true,  "edit": true,  "advancedEdit": true}
    }
  }
}
```

The three-tier convention holds across ~967 grants in B and C: authoring groups (`Author`/`Developer`) get
`view+edit+advancedEdit`; a working persona gets `view+edit`; an oversight persona gets `view` only. For a
business persona `edit`/`advancedEdit` on a *nav item* are decoration — the render reads `view`.

⛔ **Two schools of "who else can always see this", and they are not interchangeable.**
- **A / C / D:** `accessors: {}` and the build identities added as **role groups** — `Author`, `Developer`,
  `System Administrator` appended to every item's `roleGroupAccessors` (C: `Author` on 45/45 items,
  `System Administrator` 43, `Developer` 43).
- **B:** `roleGroupAccessors` holds **only** business roles, and the build identities come from
  `accessors: {"admin": {…true}, "nct_author": {…true}}` — present on 56/56 gated items.

Either works. **Pick one and apply it to every item**, because the failure mode is an item with neither:
gated to role groups that grant nobody, with an empty `accessors`, is an item **nobody can see**. Doc 17
documents `roleAccess` on a nav item but not these two schools; mixing them is how §3.4.2 happens.

✅ **Mirror the target page's grant set onto the link.** B: 55/55 links carry the same `roleGroupAccessors`
map as their target page, 0 mismatches. C: 44/44, 1 mismatch. That includes the console links, which B and C
also gated individually to `Author, Developer[, System Administrator]` on top of the group gate. Belt and
braces is cheap here and it makes the two layers auditable against each other.

⛔ **The nav is navigation, not access control.** Hiding a link does nothing to the page: it stays reachable by
URL until the same grant is on the page node, and the real gate on data is the action predicate plus the scoped
fetch rule. One project shipped a link gated `false/false` over a page left `authenticated:true` — harmless
there, fatal in the other direction.

#### 3.4.1 ⛔ Silent killer #1 — `publicReadAccess: true` makes the whole role map inert

The check is a **disjunction**, evaluated in order:

```
public OR authenticated OR anyAccessorRole OR anyRoleGroupAccessor
```

The first `true` wins. So an item with `publicReadAccess: true` **and** a carefully ticked
`roleGroupAccessors` short-circuits on public before any group is read: the ticks do nothing, and the item is
visible to everyone including anonymous visitors. It looks gated in the JSON and in the authoring dialog. It
is not gated at all.

A shipped this on its `Pages` group — `publicReadAccess: true` plus a role list — so every end user saw
`Rules`, `Contexts`, `Database`, `Business Logic`, `Schedulers`. **40 of the 45 items in A that carry a
`roleAccess` at all set `publicReadAccess: true`.** The gate was decorative across the whole file.

✅ **Untick public (and, for a persona gate, authenticated) FIRST, then grant.** The only correct combination
for a gated item is `publicReadAccess:false, authenticatedUserAccess:false` plus grants. And the only correct
use of `publicReadAccess:true` is a link you *deliberately* want everyone to see, in which case write nothing
else:

```json
"roleAccess": { "publicReadAccess": true, "authenticatedUserAccess": false }
```

Neither doc 17 nor `validate` flags the inert combination. Make it a gate — the script in §3.4.2 does both.

#### 3.4.2 ⛔ Silent killer #2 — a grant to a role group that does not exist

Cross-check every `roleGroupAccessors` key against `rep-objects.json.roleGroups[].name`. **In three of the
four exports the check fails, and it fails on the same five names** — a persona set inherited from an earlier
starter template that nobody rewrote. None of the five is a role group in any of the four projects (their real
rosters are 10, 8, 12 and 8 entirely different names).

The reason it survives review: the authoring dialog serialises **every role group it knows** into the map, so
stale keys usually sit there all-false and harmless. They become fatal the moment someone ticks `view` on one
— and they sit on exactly the nav items an integrator inherits rather than creates.

| | items carrying the phantom roles | consequence |
|---|---|---|
| C | the **front-door link** (phantoms + `Author`, `accessors: {}`) | the front door is visible **only to `Author`**. Every business persona opens the app and cannot see the link to its own cockpit. |
| D | the `Users` console link | invisible to everyone but `Author`; harmless — it is inside the gated drawer anyway |
| A | the `Pages` **group**, the `Home` link, the `Users` link | see §7.2 |

✅ **Make this a gate, not a review item.** After any nav edit,
`set(all roleGroupAccessors keys) − set(rep-objects.roleGroups[].name)` must be empty. A non-empty difference
is either a dead grant (item hidden from a persona that should see it) or a typo. Neither `validate` nor
`pack` catches it today, and it shipped to production in 3 of 4 projects — including on a front-door link.

```python
import json
br, rep = json.load(open("work/branches.json")), json.load(open("work/rep-objects.json"))
roster = {g["name"] for g in (rep.get("roleGroups") or [])}
nav = next(v for v in br[0]["virtualPlugins"] if v["name"] == "Nct left nav")
model = json.loads(nav["content"]["properties"]["modelGroups"]["stringValue"])

def walk(items):
    for it in items:
        yield it
        yield from walk(it.get("children") or [])

used = set()
for it in walk(model["pagesModel"]):
    ra = it.get("roleAccess") or {}; rga = ra.get("roleGroupAccessors") or {}
    used |= set(rga)
    if ra.get("publicReadAccess") and any(v.get("view") for v in rga.values()):
        print("INERT GATE:", it["name"])                       # §3.4.1
    if any(v.get("edit") and not v.get("view") for v in rga.values()):
        print("EDIT WITHOUT VIEW:", it["name"])                # §3.1
print("PHANTOM ROLE GROUPS:", sorted(used - roster) or "none") # §3.4.2
```

Run the same intersection over `hasAnyRoleGroup("…")` string literals in `rep-objects.json.rules[]` while you
are there — the same stale names turn up in Groovy.

### 3.5 Localization — on **both** maps, and never on the icon

**Decision: the item-level `localizedMap.name` is what renders; write the identical object into
`linkModel.localizedMap` as well.** The failure it prevents is a three-locale project whose entire sidebar
comes out in one language.

Items missing at least one tenant locale in their **item-level** `localizedMap.name`:

| | locales | items missing a locale | which |
|---|---|---|---|
| C | hy_AM, ru_RU, en_US | **0 / 51** | — |
| A | en_US, hy_AM | **0 / 173** | — |
| B | hy_AM, en_US, ru_RU | 1 / 65 | the `Pages` heading only (baseline, gated anyway) |
| D | en_US, hy_AM, ru_RU | 14 / 29 | the `Pages` heading, `Users`, and **all 12 business links** |

D's twelve business links carry a complete three-locale `linkModel.localizedMap` and **no item-level
`localizedMap` at all** — the exact bug doc 17's opening ⛔ warns about. Under the two non-default locales that
sidebar renders its twelve business entries in the default language. Two projects that did it right prove the
fix costs nothing: copy the same `{"name": {…}}` object into both places.

> **Correction to [[17-left-nav-quick-links.md](../17-left-nav-quick-links.md)](../17-left-nav-quick-links.md) Gotcha 5.** It says *"a
> **link** localizes via `linkModel.localizedMap`; a **group/heading** has no `linkModel`, so it localizes via
> the `PageModel`'s own `localizedMap`."* That framing contradicts the doc's own opening callout and it is
> what produced D's bug. The correct rule: **the render reads the ITEM-level map for both groups and links**;
> `linkModel.localizedMap` is a second inner map. Fill both, always, for every tenant locale.

⛔ **Do NOT localize the `icon` map — and audit what the baseline handed you.** All four exports carry the
*same* corrupted icon translations on the baseline console links, because a naive localization pass ran the
whole `localizedMap` through a translator and it translated the CSS class values too:

```jsonc
"Users":     { "icon": { "en_US": "pe-7s-users",  "ru_RU": "pe-7s-пользователи", "hy_AM": "pe-7s-օգտատերեր" } }
"Rules":     { "icon": { "en_US": "pe-7s-tools",  "ru_RU": "pe-7s-tools",        "hy_AM": "pe-7s գործիքներ" } }
"Workflows": { "icon": { "en_US": "pe-7s-repeat", "ru_RU": "pe-7s-repeat",       "hy_AM": "pe-7s-կրկնություն" } }
"Processes": { "icon": { "en_US": "pe-7s-play",   "ru_RU": "pe-7s-play",         "hy_AM": "pe-7s-խաղ" } }
"Contexts":  { "icon": { "en_US": "pe-7s-box2",   "ru_RU": "pe-7s-box1",         "hy_AM": "pe-7s-box1" } }
```

`pe-7s գործիքներ` is not a class; under that locale the icon is simply absent. 6–7 such entries per project,
in **4 of 4**. **The `icon` map must be the identical class string in every locale, or omitted entirely.**
(Icon-class identity holds in 1090/1096 and 403/409 of the hand-authored entries — the misses are always these
baseline ones.)

⛔ **And a stale localized icon silently overrides the plain one.** C's front-door link sets
`icon: "pe-7s-graph3"` on both the item and the `linkModel` — the deliberate dashboard icon doc 17 asks for —
while its `linkModel.localizedMap.icon` still says `pe-7s-home` in all three locales, left over from when the
item was called "Home". **Renaming or re-iconing a link is three edits, not one:** `name`, `localizedMap.name`
(both objects), **and** `localizedMap.icon` (both objects).

Neither doc mentions either icon trap.

### 3.6 Icons

**Decision: every hand-authored item gets an icon, and the icon is semantic.**

| | items with no/blank `icon` | links with no `linkModel.icon` |
|---|---|---|
| B | 1 | 1 |
| C | 1 | 1 |
| D | 1 | 1 |
| A | **46** | **35** |

The single miss in the three good projects is the same baseline link (`Audit Logs`, which ships iconless).
Two flavours of group icon are in evidence:

- **C and D:** business groups keep the default `globe`. Cheap, and fine — the heading is text.
- **B:** every group gets a meaningful icon. Better, and it is what makes a collapsed sidebar usable:
  `pe-7s-graph2` dashboards · `pe-7s-box2` reference data · `pe-7s-note2` demand documents · `pe-7s-note`
  supply documents · `pe-7s-box1` unit holdings · `pe-7s-tools` operations · `pe-7s-repeat` queues ·
  `pe-7s-news-paper` reports · `pe-7s-config` settings.

Link icons are semantic, not decorative, and the corpus vocabulary is consistent enough to reuse wholesale:
`pe-7s-home`/`pe-7s-graph2`/`pe-7s-graph3` front door and dashboards · `pe-7s-note2`/`pe-7s-note` documents
and requests · `pe-7s-cart` documents that order something · `pe-7s-box1`/`pe-7s-box2` items and holdings ·
`pe-7s-users`/`pe-7s-user` partners and people · `pe-7s-check` approvals · `pe-7s-news-paper` reports ·
`pe-7s-config`/`pe-7s-tools` configuration · `pe-7s-repeat` reversals and recurring processes ·
`pe-7s-lock`/`pe-7s-key` restrictions · `pe-7s-back` returns · `pe-7s-trash` write-offs · `pe-7s-timer`
deadlines · `pe-7s-attention` exceptions · `pe-7s-albums` grouped outputs.

✅ **Repeating one icon across a whole group is a signal, not laziness.** B uses `pe-7s-news-paper` for **all
nine** of its report links — "these are all the same kind of thing". Never `pe-7s-angle-right`.

### 3.7 What is a nav target and what is not

**Decision: a nav link points at a top-level page (a direct child of root) and nothing else.** The failure it
prevents is a sidebar full of generated form pages and drill-down leaves.

In B, C and D: **0 of 55 / 44 / 27 links** point at a page nested deeper than depth 1. Deeper pages exist in
quantity — they are the generated form pages and the drill-down targets — and they are reached from the table,
never from the sidebar.

The page-alias convention that makes this checkable from the alias alone, seen in all three:

| alias prefix | meaning | nav target? | counts |
|---|---|---|---|
| `form-…` | a generated form page | ✗ never | B 32, C 38, D 16 |
| `wl-…` | a workflow worklist page | ✓ always | C 8 |
| `rpt-…` | a report page | ✓ always | B 9, C 7 |
| (none) | register / dashboard / master data | ✓ if top-level | — |

A has **no `form-` prefix at all** (355 of its 433 aliases carry no prefix) and 42 of its nav links point at
depth-2 / depth-3 pages. The two facts are related: with no namespace, nothing distinguishes a form page from a
register page, and the nav generator could not tell them apart. Neither doc mentions the prefixes; adopt them
on day one, they cost nothing and they make three separate checks mechanical.

### 3.8 Reachability — the closeout number

**Decision: every business page that is a top-level page has a quick link; the only unlinked depth-1 pages are
the platform's own leftovers.** "Every business page is linked" is unmeasurable as written; this makes it a
set difference.

| | top-level pages | linked | unlinked | the unlinked ones |
|---|---|---|---|---|
| D | 30 | 26 | 4 | `Profile`, `Queries`, `401`, `404` |
| C | 48 | 43 | 5 | `Sources`, `Profile`, `Queries`, `401`, `404` |
| B | 64 | 54 | 10 | `Sources`, `Queries`, `Profile`, `Branches`, `Insights`, `Advisory`, `Ontology`, `reports`, `401`, `404` |
| A | 133 | 116 | 17 | the same leftovers **plus 12 real business pages** |

✅ **The allowlist, verified as an exact match in 3 of 3 good projects:**

```
unlinked depth-1 pages ⊆ { Profile, Sources, Queries, Branches, Insights,
                           Advisory, Ontology, reports, 401, 404 }
```

Anything else in that set is an orphaned screen. Neither doc gives this list; it is the single cheapest
closeout check in the whole nav.

### 3.9 Every workflow gets a worklist page, and every worklist page gets a link

Doc 17's second mandate, measured against `rep-objects.json.workflows[]` and pages carrying
`process.table.pluin` (note the platform's own spelling of the plugin name):

| | workflows | `process.table` pages | of those, quick-linked |
|---|---|---|---|
| C | 8 | 8 | **8** |
| B | 5 | 5 | **5** |
| D | 1 | 1 | **1** |
| A | 7 | **1** | 1 |

Three projects hit 1 : 1 : 1 exactly. **A queue's group follows who works it, not the fact that it is a
queue:** C names its worklists `wl-*`, files the routine ones under the case-lifecycle group and puts the
exception queues (deadline breach, expiry, escalation) under the oversight group. B puts all five in a group
literally called *Queues*. Either grouping is defensible. A's 7 workflows with one worklist page — and that
page a legacy leftover — means six workflows can only be started from a row action or the admin `Processes`
console.

---

## 4. Copy-paste: the whole correct nav

```jsonc
{ "pagesModel": [

  /* 0 — the authoring drawer: untouched, gated, Home removed (children now order 1..14) */
  { "order": 0, "name": "Pages", "uuid": "62492f05-4e61-42dd-a659-6a391504e843", "icon": "globe",
    "heading": false,
    "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": false,
                    "accessors": { /* baseline block, admin + nct_author true */ },
                    "roleGroupAccessors": { "Author": {"view":true,"edit":true,"advancedEdit":true} } },
    "localizedMap": { "name": { "<loc1>": "…", "<loc2>": "…", "<loc3>": "Pages" } },
    "children": [ /* Rules … Settings, order 1..14, left exactly as shipped */ ] },

  /* 1 — first business group: the cockpit and its sibling dashboards */
  { "order": 1, "name": "<Dashboards, in the customer's word>",
    "uuid": "<fresh uuid4>", "icon": "pe-7s-graph2", "heading": false,
    "localizedMap": { "name": { "<every tenant locale>": "…" } },
    "children": [
      { "order": 0,                                     /* ← THE FRONT DOOR */
        "name": "<Cockpit>", "uuid": "<fresh>", "parentUuid": "<this group's uuid>",
        "icon": "pe-7s-graph3", "heading": false, "children": [],
        "localizedMap": { "name": { "<every locale>": "…" } },
        "linkModel": { "name": "<Cockpit>", "icon": "pe-7s-graph3",
                       "identifier": "34c97297-185b-41b7-a255-f37895984a1c",   /* the root page */
                       "internal": true, "needToBeSaved": true,
                       "localizedMap": { "name": { "<every locale>": "…" },
                                         "icon": { "<every locale>": "pe-7s-graph3" } } },
        "roleAccess": { "publicReadAccess": false, "authenticatedUserAccess": false,
                        "accessors": {},
                        "roleGroupAccessors": { /* every persona that uses the product,
                                                   + your chosen build-identity school */ } } }
      /* … 1–8 more dashboard links … */
    ] },

  /* 2..n — one group per business domain, in the order work flows, 1–9 links each */
  { "order": 2, "name": "<Reference data>", "uuid": "<fresh>", "icon": "pe-7s-box2",       "children": [ … ] },
  { "order": 3, "name": "<Documents>",      "uuid": "<fresh>", "icon": "pe-7s-note2",      "children": [ … ] },
  { "order": 4, "name": "<Queues>",         "uuid": "<fresh>", "icon": "pe-7s-repeat",     "children": [ … ] },
  { "order": 5, "name": "<Reports>",        "uuid": "<fresh>", "icon": "pe-7s-news-paper", "children": [ … ] },
  { "order": 6, "name": "<Settings>",       "uuid": "<fresh>", "icon": "pe-7s-config",     "children": [ … ] }
] }
```

Edit it in place — parse → mutate → re-stringify — never rewrite the blob:

```bash
python3 - <<'PY'
import json
p = "work/branches.json"; br = json.load(open(p))
nav = next(v for v in br[0]["virtualPlugins"] if v["name"] == "Nct left nav")
slot = nav["content"]["properties"]["modelGroups"]
m = json.loads(slot["stringValue"]); before = len(slot["stringValue"])
# … mutate m["pagesModel"] here …
slot["stringValue"] = json.dumps(m, ensure_ascii=False)
json.dump(br, open(p, "w"), ensure_ascii=False, indent=2)
print("modelGroups:", before, "->", len(slot["stringValue"]))   # must differ
PY
```

---

## 5. Two structural traps that render fine and break later

⛔ **`parentUuid` is bookkeeping, so a wrong one is invisible.** `PagesPanel` renders by walking `children`;
nothing at render time reads `parentUuid`. C's front-door link sits physically inside the first business
group's `children` but carries `"parentUuid": "62492f05-4e61-42dd-a659-6a391504e843"` — the `Pages` group's
uuid, the fingerprint of a link added to `Pages` by tooling and then hand-spliced into the business group
without fixing the field. It is the only such item in 318 nav items across the four projects, so treat it as
the rare accident it is, but check it: **`parentUuid` must equal the uuid of the array you are in, at every
depth.**

⛔ **Duplicate `order` among siblings.** Gaps are fine — C's top level runs 0, 2, 3, 4, 5, 6, 7 after a group
was deleted and renders correctly, because sibling sort is by `order` and a hole changes nothing. Duplicates
are not: C has two `order: 0` items in its first business group, so the front door's position depends on array
order rather than on the field that is supposed to control it. A has the same collision inside `Pages`.

---

## 6. Where the library docs are wrong or silent

**[[17-left-nav-quick-links.md](../17-left-nav-quick-links.md)](../17-left-nav-quick-links.md)**

1. **Gotcha 8(a) — "append your business pages to that same `Pages` group" — is wrong**, and contradicts the
   doc's own ⛔ callout. 3 of 3 good builds used sibling business groups. §3.1.
2. **Silent on what to do with `Pages` itself.** Keep it at `order: 0`, gate the *group* to `Author` — the
   highest-value nav edit in a build, and it deserves a numbered step, not option 8(c). §3.1.
3. **"Business groups go first" is contradicted 3 of 3.** Gating is idempotent and does not renumber the
   baseline; reordering is neither. Jump with the field. §3.1.
4. **Gotcha 5's localization rule contradicts the doc's own opening ⛔** and is what produced D's
   one-language sidebar. The item-level map renders, for groups *and* links. §3.5.
5. **Silent on the phantom-role failure** — shipped in 3 of 4, once on a front-door link; no doc text and no
   `validate` rule for `roleGroupAccessors` key ∉ `rep-objects.roleGroups[].name`. §3.4.2.
6. **Silent on the inert gate:** `publicReadAccess:true` alongside grants makes the grants dead. §3.4.1.
7. **Silent on the two build-identity schools**; mixing them yields an item nobody can see. §3.4.
8. **Silent on `localizedMap.icon`** — localization passes translate CSS class names (corrupted in 4 of 4),
   and a stale localized icon overrides a freshly-set `icon`. §3.5.
9. **Silent on the depth rule** (two levels), **on sizing and naming** (1–9 links, group list written first
   and equal to the manual's contents page), **on the `form-`/`wl-`/`rpt-` alias prefixes**, and **on the
   closeout allowlist** that makes "every business page is linked" measurable. §3.2, §3.7, §3.8.
10. **The tooling note oversells verification.** A label-removal command reached only the dead per-page copies
    in one project and reported success. The only success signal is the shared node's byte length. §1.1.

**[[21-homepage-and-redirect.md](../21-homepage-and-redirect.md)](../21-homepage-and-redirect.md)**

11. **The ladder should say rung 1 is what everyone does.** 4 of 4 authored the cockpit into Home and left
    `Redirect` empty; `Redirect` was used zero times in 757 pages. §2.
12. **It does not say what a *good* rung 1 looks like.** The tell is ~10 `nct.parsis.plugin` grid cells, a KPI
    strip of `nct.label.plugin` nodes and one `global.replacement.plugin` above the grid rows (3 of 4) — not
    nine charts in one parsis. §2.
13. **It warns not to alias the root, but not that your own documentation will invent the alias.** A shipped
    manual printed `/<project>/home`; no such alias exists, so the link 404s. §2.
14. **Silent on the root PAGE's own `roleAccess`.** 2 of 4 shipped a "closed" Home that renders only via an
    `accessors` side-door; tighten the role groups and the front door vanishes for everyone. §2.
15. **Silent on default chart params on the front door** — 2 of 4 opened their cockpit pinned to one entity. §2.
16. **Its "front door must also be a quick link" rule is under-specified.** Position is load-bearing:
    `pagesModel[1].children[0]`, `linkModel.identifier == 34c97297-…`. The corpus failure is not a missing
    link but a *hidden* one, worked around with a duplicate. §3.3, §7.2.

> **One CSS note the nav owns.** The sidebar is screen furniture: any page that produces a printable document
> must remove it, or the print carries the app chrome. Wrap your own controls in a `.doc-chrome` class rather
> than hunting the platform's generated classes, and emit
> `@media print { .doc-chrome{display:none!important} @page{size:A4 portrait;margin:10mm} }`. Full print
> recipe in [[24-html-component-studio.md](../24-html-component-studio.md)](../24-html-component-studio.md).

---

## 7. The anti-pattern — A's nav, itemised

**Shape:** 2 top-level items, 171 links, depth 3, 12 links-with-children, 45/173 items gated and 40 of those
inert. 433 pages and 163 dynamic CRUDs were built, and then the navigation was **generated by dumping every
page into a tree instead of designing an information architecture**. The three good projects each wrote the
group list first — in one case it is literally the user manual's contents page — and the nav fell out of it.

### 7.1 The whole business app is one item inside the authoring drawer

`Pages` children are: `Home` (order 0), **one business folder (order 0, 21 children)**, then the fourteen
console links. So the business application is a *sibling of `Rules` and `Schedulers`*, one collapse away from
invisible, and it shares an `order` with `Home`.

**And the item it hangs off is a link to an empty page.** That folder targets a real top-level page whose
content parsis has **zero children** — no table, no chart, no html. Clicking the folder that holds the entire
product navigates to a blank screen.

> The failure: the end user's first impression of the product is a developer console with one expandable
> folder in it, and the folder's own page is empty.

### 7.2 `Home` is duplicated, and the duplicate is the only one that works

Two nav items point at the root `34c97297-…`:

| item | where | `roleAccess` | who sees it |
|---|---|---|---|
| `Home`, `pe-7s-home` | `Pages`, order 0 | phantom roles + `Author`, `accessors: {}` | **`Author` only** |
| `Dashboard`, `pe-7s-graph3` | inside the business folder, order 1, **depth 3** | `null` | everyone |

Cause and effect: the front-door link was gated to five role groups that do not exist (§3.4.2), so business
users could not see it, so somebody added a second one deeper in the tree with no gate at all rather than
fixing the first. **Two links to one page is the symptom; a dead role grant is the disease.** A has 12 such
duplicate targets in total.

### 7.3 The second group's eleven entries are fake folders

Every child of that group is a **link that carries children**, and in 10 of the 11 cases the link's
`identifier` is **the identifier of its own first child**:

```jsonc
{ "name": "Code lists", "icon": "",                        // ← blank icon
  "linkModel": { "identifier": "3b42bb53-…", "icon": "pe-7s-notebook" },
  "children": [ { "name": "<first lookup table>", "linkModel": { "identifier": "3b42bb53-…" } },  // ← same page
                /* …37 more… */ ] }
```

Clicking "Code lists" does not expand a section — it navigates to the first lookup table's register, which
then also appears beneath it in the tree.

> The failure: section headings are supposed to be inert; here half of them teleport you to an arbitrary leaf.
> **A group is a `PageModel` with `children` and no `linkModel`. If you find yourself giving a folder a
> `linkModel`, you wanted a group.**

`Code lists` alone holds **38** children — four times the largest group in any good project — and those
children are depth-3 pages nested under an intermediate page, which is why A is the only project whose nav
links deeper than depth 1 (42 links do).

### 7.4 Platform leftovers promoted into the business nav

A sub-group named `Platform` contains `Sources`, `Queries` and `Profile` — the datasource console, the query
console and the user-profile page. In the other three projects those are precisely the pages deliberately left
unlinked (§3.8). Here they were adopted as product features.

### 7.5 The gating is decorative

- The `Pages` group carries `publicReadAccess: true` **and** five phantom role groups: the public flag makes
  the whole console visible to everyone, the role list grants nobody anything. Worst of both.
- 40 of the 45 items that carry a `roleAccess` at all set `publicReadAccess: true`.
- 128 of 173 items have no `roleAccess`.
- Exactly two items out of 173 have a phantom-free grant.

### 7.6 The measurable consequences

- **12 business pages orphaned** — built, and unreachable from the sidebar.
- **6 of 7 workflows have no worklist page**, so six workflows can only be started from a row action or the
  admin `Processes` console.
- **No `form-` alias namespace**, so nothing distinguishes a form page from a register page — part of why the
  nav ended up pointed at depth-3 pages.
- 46 items with no icon, 35 links with no `linkModel.icon`, duplicate `order` in `Pages`, and one baseline
  console link silently re-pointed at a different page.

---

## 8. Closeout checklist

Run against the shared `Nct left nav` node's decoded `modelGroups`, plus the page tree and `rep-objects.json`.

1. `virtualPlugins[name=="Nct left nav"].content.properties.modelGroups.stringValue` is the **only** nav you
   edited, and its byte length changed.
2. `pagesModel[0]` is `Pages`, uuid `62492f05-…`, `publicReadAccess: false`, granting `Author` (plus
   admin/nct_author via `accessors`). Its children run `order: 1…14` — the order-0 hole is correct.
3. Every other top-level item is a **group**: has `children`, has **no** `linkModel`.
4. Tree depth ≤ 2. Zero links carrying children.
5. Group names are the customer's words, in flow order, 1–9 links each; the list reads as the manual's
   contents page.
6. `pagesModel[1].children[0]` is the front-door link: `linkModel.identifier == 34c97297-…`, a dashboard icon,
   and a grant to every persona that uses the product.
7. Root page: `Redirect == ""`, `alias == null`, `chart.js.plugin` nodes in its own parsis, one
   `global.replacement.plugin` above the grid rows, a KPI strip, and `authenticatedUserAccess: true` on the
   page node.
8. No emitted README, manual or mail template prints a `/home` URL.
9. Every item carries `localizedMap.name` covering **every** `tenant.json.locales` entry — on the **item**,
   not only in `linkModel`.
10. Every `localizedMap.icon` value is the identical CSS class in every locale (audit the baseline's
    `Users`/`Rules`/`Workflows`/`Processes`/`Contexts` entries; they arrive corrupted).
11. `set(roleGroupAccessors keys) ⊆ set(rep-objects.roleGroups[].name)`. No exceptions.
12. No item has `publicReadAccess: true` together with a `view: true` grant.
13. No grant is `edit: true, view: false`.
14. Build identities are granted the same way on every item — either `accessors.admin/nct_author`, or
    `roleGroupAccessors.Author/Developer/System Administrator` — never neither.
15. Each gated link's grant set equals its target page's grant set.
16. Every item has an `icon`; every group has an icon better than `globe` if you can spare the minute.
17. `parentUuid` == the enclosing group's `uuid`, everywhere. No duplicate `order` among siblings.
18. Every link targets a **depth-1** page. No `form-*` page is a nav target.
19. Unlinked depth-1 pages ⊆ `{Profile, Sources, Queries, Branches, Insights, Advisory, Ontology, reports,
    401, 404}`.
20. `count(workflows) == count(process.table pages) == count(worklist quick links)`.
21. Open the bare project URL in a browser, signed in as a **non-author test account per persona**, and look
    at the sidebar. Everything above is necessary; only this is sufficient — `admin` and `Author` bypass every
    gate, so testing while signed in as either proves nothing.
