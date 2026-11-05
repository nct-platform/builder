# 37 · Header actions and footer popups — the project's own pieces of the site chrome

> **The terms.** A **header action** is an icon in the app's top bar, left of the notifications bell, drawn exactly like
> the bell: clicking it either opens a **popup** — a panel under the icon showing the action's own html component — or
> goes to a **page** (a page of the project with parameters, or another address). A **footer popup** is an html
> component drawn with the footer and ALWAYS shown, placed by the footer or by the screen: a cookie notice, a chat
> button, an announcement strip, a feedback tab. Each item is **a page's** (shown on that page only) or **global** (the
> branch's — shown on every page of the branch).
>
> **Scope.** Where items live in the export, the shape of an item, the component it carries, who sees it, the commands
> that write them, the MCP tools that change them live, and what `validate` checks.
> **Not here:** navigation to the project's pages → the left nav ([17](17-left-nav-quick-links.md)); buttons of ONE
> screen → that screen's plugins / breadcrumb buttons; JS or CSS loaded on every page without anything drawn →
> Global resources ([29](29-global-resources.md)); building the component itself → [24](24-html-component-studio.md)
> (+ [24a](24a-theming-and-dark-mode.md) before any CSS, [24b](24b-html-composition-and-plugin-tags.md) for `<plugin>`
> tags).

| | |
|---|---|
| A page's item | the JSON text `{"items": [...]}` of the STRING property `headerActions` / `footerPopups` of the page's OWN `site.header.plugin` / `site.footer.plugin` node — shown on that page |
| A global item | an entry of **`site-chrome.json`** `{"items": [{"branch", "area", "uuid", "order", "item"}]}` — shown on every page of the branch |
| Its component | `html` + `studioModel` — **exactly** an `nct.html.plugin`'s `html` and `studioModel` |
| Header item | `titles`, `icon`, `kind` POPUP \| PAGE, `popupSize`, (PAGE) `identifier` + `params` or `link` |
| Footer item | `name`, `side` LEFT \| RIGHT, `edge` TOP \| BOTTOM, `positioning` ABSOLUTE \| FIXED |
| Order | `order` on every item — a page's and the global ones are drawn together, by it |
| Who sees it | the item's `roleAccess` — everyone when absent |

> **🔧 Tooling.** `headerfooter add --area header|footer --scope global|page [--page P] …` creates an item (and, for a
> global one that draws a component, the shared `Nct header actions` / `Nct footer popups` virtual plugin its plugins
> hang on), `set --id …` changes only the options given (`--scope` moves it), `rm`, `mv --index N`, `list [--page P]`. They refuse what the platform's editor
> refuses (§7). `validate` checks every list and entry and runs every drawn component through the html component checks
> (§8). Live, after import: MCP `nct_ui_list_header_footer_items`, `nct_ui_get_header_footer_item`,
> `nct_ui_save_header_footer_item`, `nct_ui_delete_header_footer_item`, `nct_ui_move_header_footer_item` (§9).

---

## 1 · The decision: header action, footer popup, or something else?

| The PRD says | Build |
|---|---|
| "a help / support / contact button in the header", "a quick-create button in the top bar", "a calculator / converter at hand on every screen" | a **global header action**, `kind` POPUP — its component is the panel |
| "a link to <the knowledge base / the shop / a report> in the top bar", "an icon that opens <page>" | a **global header action**, `kind` PAGE |
| "cookie consent", "an announcement / maintenance banner", "a chat / feedback button in the corner", "a notice shown when <condition>" | a **global footer popup** |
| "on the <X> screen, a help popup about it", "only the <X> page shows a promo strip" | a **page's** header action / footer popup, on that page |
| "a menu of our pages" | the left nav ([17](17-left-nav-quick-links.md)), not header actions — the header holds a few tools, not navigation |
| "a script / tracker / font on every page", nothing drawn | Global resources ([29](29-global-resources.md)) |

A header action is a TOOL — a handful at most, each one icon with a tooltip. Five icons next to the bell is a crowded
bar; a sixth is a menu that belongs in the left nav. "On every screen" is **global**; "on this screen" is the page's.
An icon carries no badge: its component is drawn only when it is first opened, so "an icon with the number of unread
<things>" is not a header action — show that count inside a component that is drawn with the page.

## 2 · Where items live — a page's and the branch's

Every page carries its OWN copy of the header and the footer: the layout is cloned into a page when the page is first
opened ([01](01-content-model-and-pages.md) "Client rendering of `layout`"). So:

- **A page's item** is kept on that copy — the first `site.header.plugin` / `site.footer.plugin` node in the page's tree
  (not in a page under it) — as `properties.headerActions` / `footerPopups` = `{"items": [ … ]}`, and shows on that page
  only. A layout's header/footer node may carry a list too: every page made from the layout afterwards starts with a
  copy of it, as its own.
- **A global item** is the branch's: an entry of `site-chrome.json` at the archive's root, travelling with the pages
  (the "Pages, forms and rules" part):

  ```json
  {"items": [
    {"branch": "master", "area": "header", "uuid": "<uuid>", "order": 0,
     "item": {"kind": "POPUP", "icon": "pe-7s-help1", "titles": {"<locale>": "Support"}, "html": "…", "studioModel": {…}}}
  ]}
  ```

  `branch` is the branch's NAME: an archive carries no branch ids, and a project's branch names are unique (Clone
  branch refuses a name that is taken), so the import gives the entries to the branch of that name. `item` is the item
  without its uuid, order and scope — the entry's. An import that takes the pages makes the branch's global items
  exactly the file's (none, when the file is absent); one that does not take them leaves them. The platform copies them
  with the branch — Clone branch, publishing a branch into another, an environment's publish (rows "Header or footer
  item"; the plugins their components place travel as the shared component `Nct header actions` / `Nct footer popups`).

A global component's `<plugin>` children need a node every page shares: the content node of the hidden common virtual
plugin **`Nct header actions`** / **`Nct footer popups`** (`branches[0].virtualPlugins[]`), found by its node — the
area's plugin with the identifier `header-actions` / `footer-popups`:

```json
{
  "id": "<uuid>", "name": "Nct header actions", "group": "Layout",
  "commonContent": true, "hidden": true, "isLayout": false, "useContentChildren": false,
  "templateNames": ["architectui-html-pro"],
  "content": {
    "id": "<uuid>", "uniqueIdentifier": "<uuid>", "identifier": "header-actions", "name": "header-actions",
    "pluginName": "site.header.plugin", "virtualContent": true, "isBehaviour": false, "active": true,
    "children": [],
    "roleAccess": {"publicReadAccess": true, "authenticatedUserAccess": false, "accessors": {}, "roleGroupAccessors": {}},
    "properties": {}
  }
}
```

`Nct footer popups` is the same over `site.footer.plugin`, identifier `footer-popups`. `headerfooter add --scope global`
makes it for an item that draws a component (a POPUP action, any footer popup), as the platform does on the first save
of one; an import of global items that draw components into a branch without it makes an EMPTY one — their plugins then
start from their `<prop>` seeds alone (§5). ⛔ Its shape: identifier `header-actions` / `footer-popups` (the platform
draws global items' components on the node it finds by it — never `header`, every page's header node is called that);
`hidden: true` and `commonContent: true`, as the platform makes it (a visible one is offered in the palettes as a
component to place on a page); `templateNames` a list (the plugin palette reads it from every virtual plugin of the
branch and one without a list takes the palette down — `[]` is enough); its own `roleAccess` public (checked before
any component on it is drawn; an item's audience is its own, §6). Its name is its own: no other virtual plugin of the
branch may be called `Nct header actions` / `Nct footer popups` (an environment's publish matches shared components
by name) — the templates' `Nct footer` is the site footer, another thing. ⛔ This virtual plugin is storage for global
items' plugins, not the left nav's kind of shared node: no page's node links to it (`linkContentIdentifier`), and
nothing keeps a list on it.

## 3 · One order

Every item has an `order` (a whole number), given wide apart — 1000 after the last. A reader of a page sees the page's
items and the global ones TOGETHER, by `order` — a global item before a page's on a tie. A new item goes after
everything the page shows (a global one made with no page, after the branch's global ones). Moving one item (the
platform's drag, `headerfooter mv`, the MCP move) gives THAT item an order between its new neighbours' and leaves every
other where it was — so moving a page's own item never shifts the global ones among another page's items. Only when
the neighbours leave no room (adjacent orders, or one without an order) is what that page shows numbered again, 1000
apart — the global ones in the branch's too. A page's copy of an item that the branch has made global (same uuid — a
layout's item copied into pages before it was made global) gives way to the global one.

## 4 · An item

Every item: `uuid` (its id — the editors and the tools address it by it), `order`, `html`, `studioModel`, `roleAccess`.

**Header action**

| field | | |
|---|---|---|
| `titles` | `{locale: text}` | the icon's tooltip and its accessible name; at least one; write every locale of the project ([20](20-localization.md)) — a reader gets their language, else the language without the country, else the project's default |
| `icon` | `pe-7s-*` class | the icon chooser's set, e.g. `pe-7s-help1`, `pe-7s-comment`, `pe-7s-calculator` |
| `kind` | `POPUP` \| `PAGE` | required |
| `popupSize` | `SMALL` \| `MEDIUM` \| `LARGE` | POPUP: the panel's width (22 / 32 / 48 rem, never wider than the screen); default MEDIUM. The height follows the component up to 75% of the screen, then it scrolls |
| `internal` | boolean | PAGE: a page of the project (default) or an address |
| `identifier` | page identifier | PAGE + internal: the page's content `identifier` (not its `uniqueIdentifier`) — the link plugin's own field |
| `params` | text | PAGE + internal: appended to the page's address as written — `?status=open`, `#part`, `/more/of/the/path`; never `//…` |
| `link` | `https://…`, `http://…`, `mailto:…`, `tel:…`, `/a/path` | PAGE + not internal. Another site's address opens in a NEW TAB; a path of this site, an e-mail address and a phone number open in place. `javascript:`, `//host`, `/\host` are refused |

**Footer popup**

| field | | |
|---|---|---|
| `name` | text | what authors know it by in the list of popups; the site never shows it; required |
| `side` | `LEFT` \| `RIGHT` | default RIGHT |
| `edge` | `TOP` \| `BOTTOM` | default BOTTOM |
| `positioning` | `ABSOLUTE` \| `FIXED` | default FIXED |

| positioning + edge | where |
|---|---|
| ABSOLUTE + TOP | on top of the footer — its bottom edge on the footer's top edge; scrolls with the page, seen with the footer |
| ABSOLUTE + BOTTOM | inside the footer, on its bottom edge — over the footer's own corner |
| FIXED + BOTTOM | the bottom of the screen, always in view — the classic cookie bar / chat corner |
| FIXED + TOP | the top of the screen — under the header while the header is in view — always in view |

LEFT / RIGHT is the edge it is flush against: the footer's, or for a FIXED one the page's content column's — beside
the left menu, never under it (the menu and the header's own panels stay over a fixed popup; dialogs over both). A
footer popup's box is EXACTLY its html: no padding, no background, no frame. Give the component's root element its
width, its margin off the edges and its look — in theme tokens ([24a](24a-theming-and-dark-mode.md)).

## 5 · The component

`html` + `studioModel` are an `nct.html.plugin`'s ([24](24-html-component-studio.md)), drawn by the html block's own
renderer — so everything an html component does works here, exactly: documents and `<include>`, scripts with `ctx`,
libraries, per-theme CSS, `ctx.t` and `data-i18n`, `ctx.callRule` / `ctx.callBl` / `ctx.service`, `<plugin>` tags
(tables, forms, charts inside a popup). What is different:

- **Which node a component is drawn on.** A page's item on the page's header/footer node; a global one on the shared
  node (§2). The components drawn on one node share its children: a `<plugin id="X">` binds to its child `X`, so two
  items there that both place `<plugin id="X">` show ONE plugin with ONE configuration (`validate` WARNs), and one
  id as TWO plugins is refused (the child would be turned into whichever was drawn last, wiping its settings). Give each
  plugin an id no other item drawn there uses. An item that changes scope takes the children only it placed along.
- **A `<plugin>` child is made the first time the component is drawn** — a footer popup on the next page view, a header
  popup on its first opening. Seed its settings with `<prop>` inside the tag ([24b](24b-html-composition-and-plugin-tags.md)
  §2.3 — a seed is written only while the key is absent); change them later on the child itself (MCP
  `nct_ui_set_plugin_properties` on its `uniqueIdentifier`, from `nct_ui_get_header_footer_item`'s `about.plugins`).
  ⛔ A GLOBAL item's children are on the shared node, which the toolkit's `node` commands do not reach: offline, its
  plugins are configured by their `<prop>` seeds alone, and a child configured live is reset by the next import of an
  export that does not carry it. A plugin that needs more than seeds → a page's item (its node is the page's), or seeds.
- **`ctx.name`** is `header-<uuid>` / `footer-<uuid>` — `ctx.byName('footer-<uuid>')` reaches a footer popup's `ctx.api`
  from another component.
- **No form's data.** An item is drawn beside whatever form a page has and is part of none: its `ctx` carries no form
  context data.
- **A header popup is drawn the FIRST time it is opened**, not with the page (its scripts, plugins and rules cost nothing
  until then), and stays as the reader left it until they leave the page. Clicks inside keep it open — and in the
  pickers and dialogs its component opens; outside, Escape and the icon close it. A Bootstrap `.modal` written into its
  html cannot be shown — the panel clips it: a dialog belongs in a footer popup or on the page. To close the panel from
  its script (after a form was sent):

  ```js
  var toggle = ctx.root.closest('.nct-header-action').querySelector('[data-bs-toggle="dropdown"]');
  bootstrap.Dropdown.getOrCreateInstance(toggle).hide();
  ```
- **A footer popup is always shown.** One that should appear only on command starts hidden in its html and is shown by
  its script — or by another component through its api:

  ```html
  <div class="notice" hidden>…</div>
  ```
  ```js
  var notice = ctx.root.querySelector('.notice');
  if (!localStorage.getItem('notice-seen')) { notice.hidden = false; }
  ctx.api.show = function () { notice.hidden = false; };
  ```
- A public page shows the header and footer to anonymous visitors: a rule a public item calls must be open to
  them ([08](08-groovy-rules-and-context.md) §Execution access) — the same rule as for any public component.

## 6 · Who sees an item

`roleAccess` as everywhere: `publicReadAccess` (everyone, the default), `authenticatedUserAccess` (every signed-in user),
`roleGroupAccessors` `{"<group>": {"view": true}}`. Everyone wins over the rest: to show an item to some groups only,
`publicReadAccess` must be `false` (`--role-group` writes that). Authors and administrators always see every item. A
PAGE action is also hidden from a reader who may not open its page — an icon that leads to "no access" is never drawn.

## 7 · Build it

```bash
# a support popup on every page, in every language of the project
mrjun.py headerfooter add --project ./app --area header --scope global --title "Support" \
         --title-loc <locale2>="<…>" --icon pe-7s-comment --kind popup --size medium \
         --html @support.html --studio @support.studio.json

# an icon that opens a page of the project with a filter — on every page, for signed-in users
mrjun.py headerfooter add --project ./app --area header --scope global --title "<Page title>" --icon pe-7s-note2 \
         --kind page --target-page "<page name or identifier>" --params "?status=open" --authenticated

# a cookie notice: fixed to the bottom of the screen, hidden until its script decides
mrjun.py headerfooter add --project ./app --area footer --scope global --name "Cookie notice" --positioning fixed \
         --edge bottom --side left --html @cookie.html --studio @cookie.studio.json

# a help popup on ONE page only
mrjun.py headerfooter add --project ./app --area header --scope page --page "<page>" --title "Help" \
         --icon pe-7s-help1 --kind popup --html @page-help.html

mrjun.py headerfooter list --project ./app --area header --page "<page>"     # what that page shows, in order
mrjun.py headerfooter set  --project ./app --area header --id <uuid> --size large            # only the size changes
mrjun.py headerfooter set  --project ./app --area header --id <uuid> --page "<page>" --scope global   # page → global
mrjun.py headerfooter mv   --project ./app --area header --id <uuid> --index 0 --page "<page>"
mrjun.py headerfooter rm   --project ./app --area footer --id <uuid>
```

The commands refuse what the platform's editor refuses: a header action without a title, an icon or a kind; a PAGE
action without a page, with a page the export does not have, with `params` that do not start with `?`, `#`, `&` or a
`/path`, or with a `link` that is not `https://`, `http://`, `mailto:`, `tel:` or a `/path`; a footer popup without a
name; one `<plugin id>` as two plugins among the items drawn on one node. `--studio` takes the `studioModel` OBJECT
(`{libs, docs, scripts, css}`, [24](24-html-component-studio.md)) — never a JSON string inside JSON. What the studio
checks (an include cycle) is `validate`'s (§8).

## 8 · What `validate` checks

ERROR: a page's list that is not `{"items": [...]}` of objects (the platform draws what it can read of it and refuses
to change it); an item without a uuid or with another item's; every editor refusal of §7 and a field of the wrong type
(`studioModel` as a JSON string, `titles` as text, `internal` as `"false"`); one `<plugin id>` as two plugins on one
node; a `site-chrome.json` that is not `{"items": [...]}`, an entry without branch / area / uuid / item or of an area
that is none; a shared virtual plugin whose node has not the identifier of §2 (no global component is drawn) or that
has no `templateNames` list; another virtual plugin of the shared name. Every drawn component then goes through the
html component checks — studio JSON, libraries, theme-safe CSS, `t('…')` literals, the global `<style>` trap, the
include graph (a cycle is an ERROR).
WARN: a list on a node of another plugin or on the shared node (nothing reads it); an entry of a branch the export has
not (the import leaves it out); `site-chrome.json` without `branches.json` (an import that takes no pages does not read
it); a `global` key in an item (where it is kept says it); one `<plugin id>` placed by two items drawn on one node; a
header item with no title for a locale of the project; global items drawing components while the branch has no shared
virtual plugin (the import makes an empty one, §2); a shared virtual plugin that is not hidden common content.

## 9 · Live — over MCP

Every tool takes `area` (`header` / `footer`) and `page` — the page whose own items are meant (its uniqueIdentifier,
identifier, alias or name; the page the user is on when not given).

| tool | |
|---|---|
| `nct_ui_list_header_footer_items` | what a reader of the page sees, in order, each in short: `id`, `global`, label, kind / icon / target or placement, who sees it, its plugin ids, its problems |
| `nct_ui_get_header_footer_item` {`id`, `part`?, `from`?} | one in full: `about` first (who sees it, the page it opens, its plugins with their `uniqueIdentifier`, the length of each part of its component) then `item` — exactly what the save takes back. A part longer than the answer: `part` = `html` \| `doc:<name>` \| `script:<name>` \| `css:<theme>`, read in pieces from `from` |
| `nct_ui_save_header_footer_item` {`item`, `id`?, `edits`?} | creates (no id; `global` required) or changes ONLY the fields passed (`null` clears one — not `global` or `accessConfig`; `global` moves it). `edits` = `[{part, find, replace}]` changes text inside a part of a stored item's component, `find` occurring exactly once — without sending the rest. Conveniences: `title` (the default language), `targetPage` (a page: uniqueIdentifier, identifier, alias or name), `link`, `accessConfig` (patched like a page's — `roles` refused, a group grant on an item everyone sees refused without `publicReadAccess: false`). Refused with the editor's reason; an include cycle and a two-plugin `<plugin id>` refused; studio warnings and shared plugin ids returned as `warnings` |
| `nct_ui_delete_header_footer_item` {`id`} | with the plugins only its component placed |
| `nct_ui_move_header_footer_item` {`id`, `index`} | 0-based in what the page shows; the moved item takes an order between its new neighbours' (§3) |

A change made live is in the project, not in your export: mirror it with `headerfooter` — `add --id <uuid>` keeps the
item's id — so the next re-import does not undo it ([28](28-support-mode-over-mcp.md)).

## 10 · Gotchas

1. **"On every page" means every page that draws the header / footer** — the pages whose layout places
   `site.header.plugin` / `site.footer.plugin`. A public page built on another footer plugin shows no footer popup.
2. **A page's item is on ITS header node.** A page with no header node of its own yet (made without its layout) has
   nowhere to keep one — apply its layout first.
3. **`identifier`, not `uniqueIdentifier`,** names a PAGE action's page in the export (the MCP tool takes any name of the
   page and stores the identifier).
4. **Repeated `<plugin id>` among items drawn on one node** = one shared plugin; one id as two plugins is refused — §5.
5. **A footer popup has no frame.** A popup whose html is a bare text line renders as a bare text line over the page.
   Style its root, in theme tokens.
6. **Header popups are lazy.** A script that must run on every page load (a tracker, a timer) does not belong in a
   header popup — it runs only once the popup is opened. Put it in a footer popup (always drawn) or in Global resources.
7. **Hidden-until-command is the author's.** The platform shows every footer popup; "only on the first visit", "only
   during maintenance", "only for this role" is the component's script (or `roleAccess` for the last one).
