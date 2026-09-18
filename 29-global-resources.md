# 29 · Global resources — the project's own files, `globalAssets` on the branch

> **The term.** **Global resources** is what the product, the MCP tools (`nct_globalresource_*`) and this
> toolkit (`globalresource …`) all call the same thing: the files that belong to the PROJECT rather than to
> one screen. The export format still spells the key `globalAssets` and the byte folder `webassets/` — those
> are data on disk and do not get renamed. Use "global resources" when talking to a person or writing a
> requirement; use the literal key when writing JSON.
>
> **Scope.** How a project ships its own `.js`, `.css`, `.html`, fonts and images: where the registry lives in
> a `.mrjun` (one optional key on each branch in `branches.json`), where the bytes live
> (`tenant-files/webassets/…`), what has a switch and what does not, how a stylesheet can be limited to
> particular skins, and what an archive is allowed to contain. Read it when a requirement says "on all pages" —
> a snippet that belongs to ONE screen is not this, it is [24](24-html-component-studio.md).
> **Not here:** per-component CSS and the theme tokens → [24a](24a-theming-and-dark-mode.md); a component's own
> JS, libraries and `ctx` runtime → [24](24-html-component-studio.md); the `additionalCss` page property (a
> list of URLs on one page, unrelated) → [01](01-content-model-and-pages.md).

| | |
|---|---|
| Where it lives | `branches.json` → each branch object → `globalAssets` (optional; absent means the project has none) |
| Where the bytes live | `tenant-files/webassets/<storageId>/…` in the archive, which is `t/{tenantId}/webassets/<storageId>/…` in the file storage |
| Editor | Settings → **Developer** → **Global Resources** (Author or Developer role group, customer projects only) |
| Scope of effect | every page of the project, for every visitor — **except** the sign-in, registration, set-password, invite, profile and error pages, which are the platform's own |
| Load order | one sequence for the whole project, by the `order` integer; stylesheets as `<link>`, scripts `defer`red |

> **🔧 Tooling.** Run these instead of hand-editing `branches.json` and copying files by hand — they keep the
> two halves in step (bytes into `tenant-files/`, entry onto every branch, content hash, folder tree, order):
> `globalresource add <file> [--folder P] [--on]` — one file;
> `globalresource add-zip <file> [--folder NAME]` — an archive, unpacked into a folder and ordered;
> `globalresource mkdir <path>` — an empty folder;
> `globalresource ls` — each branch's tree, marking what actually loads;
> `globalresource set <name> [--on|--off] [--rename N] [--skins "Dracula,Dark"] [--order N]`;
> `globalresource rm <name>` — a file, or a folder and everything under it.
> `validate` then checks the registry against the files actually in the bundle.

---

## 1 · The decision: is this the right place for the file?

Three questions, in order. The first "yes" is the answer.

1. **Does the code belong to one screen?** → it is a Studio component: [24](24-html-component-studio.md).
   A global script that looks for `#my-screen` and does nothing on 40 other pages is a component in the wrong
   place — it still costs a request and a parse on every one of those pages.
2. **Is it a stylesheet that restyles the whole project** (brand fonts, a corrected table density, a print
   sheet)? → here, as CSS.
3. **Is it a library or a snippet that has to be present before anything on the page runs** (an analytics tag,
   a polyfill, a widget the project uses in many places)? → here, as JavaScript.

⛔ **This is not a sandbox and nothing pretends it is.** A file registered here runs in every visitor's
browser with the page's full privileges, exactly as the author's Groovy runs on the server. The containment
described in §4 prevents COLLISIONS, not capability.

---

## 2 · One tree, and what a file's kind actually decides

**There is ONE tree.** Scripts, stylesheets, HTML fragments, fonts and images live in it together, in folders
the author makes, exactly as they arrive in the archive they usually come from. A tree per file type was the
first design and it broke the single thing that has to keep working: a stylesheet's relative
`url(../fonts/kit.woff2)` only resolves when the font sits where the stylesheet says it does.

What a file IS decides **one** thing — whether it has a switch:

| kind | from the extension | has a switch? | what it does |
|---|---|---|---|
| `JS` | `.js`, `.mjs` | ✅ | switched on → loads on every page of the project |
| `CSS` | `.css` | ✅ | switched on → loads on every page, under every skin or a chosen few (§5) |
| `HTML` | `.html`, `.htm` | ❌ | stored, editable and served — **never** loaded on its own. Something has to `fetch()` it |
| `OTHER` | everything else | ❌ | fonts, images, source maps, JSON — served so that the stylesheet or script naming them resolves |

⛔ **The extension is not the author's to change.** It decides how the browser is told to interpret the bytes
and whether the file can be switched on at all, so a rename keeps it: renaming `app.js` to `app.css` would
leave a script registered as a stylesheet.

⚠️ **Nothing ever arrives switched on.** Not an upload, not an archive, not a file created over MCP, not one
added by the toolkit. A kit typically ships three builds of itself and a demo page, and deciding which of them
the project loads is a decision — one an import must never make on a live site's behalf.

### Folders are entities, not path prefixes

A folder is a real row with its own id and its own `enabled` flag. Deriving folders from file paths would be
less code and would lose the two things that matter: an EMPTY folder (created now, filled later) could not
exist, and a folder could not be switched **off as a unit** — which is the main reason to have folders at all.

**A folder's switch does not rewrite anything underneath it.** What loads is a file's own switch **AND** every
ancestor folder's. So switching `vendor/` off takes its whole subtree off every page, and switching it back on
restores exactly what was on before. That is also why a file can be ticked and still not load; the screen
shows that third state in amber rather than pretending the tick is the whole answer.

---

## 3 · `branches.json` — the `globalAssets` key

```json
{
  "name": "master",
  "tenantId": 1,
  "rootContent": { },
  "virtualPlugins": [ ],
  "globalAssets": {
    "version": 3,
    "storageId": "a41f0c9e22b7451d",
    "folders": [
      { "id": "9c1e…", "path": "uikit", "enabled": true, "order": 0,
        "origin": "ZIP", "archive": "ui-kit.zip",
        "createdAt": "2026-09-17T09:14:02.113Z", "createdBy": "author@example.com" },
      { "id": "0b77…", "path": "uikit/fonts", "enabled": true, "order": 1, "origin": "ZIP" }
    ],
    "assets": [
      { "id": "1f0c…", "kind": "CSS", "name": "brand.css", "folder": "",
        "path": "webassets/a41f0c9e22b7451d/brand.css",
        "sha256": "<sha-256 of the bytes>", "size": 2481,
        "enabled": true, "order": 0, "origin": "EDITOR", "isolate": false,
        "skins": [],
        "updatedAt": "2026-09-17T09:14:02.113Z", "updatedBy": "author@example.com" },

      { "id": "a44e…", "kind": "JS", "name": "jquery.min.js", "folder": "uikit",
        "path": "webassets/a41f0c9e22b7451d/uikit/jquery.min.js",
        "sha256": "<sha-256 of the bytes>", "size": 89501,
        "enabled": true, "order": 1, "origin": "ZIP", "archive": "ui-kit.zip",
        "isolate": false, "provides": ["$", "jQuery"] },

      { "id": "77b2…", "kind": "OTHER", "name": "icons.woff2", "folder": "uikit/fonts",
        "path": "webassets/a41f0c9e22b7451d/uikit/fonts/icons.woff2",
        "sha256": "<sha-256 of the bytes>", "size": 14022,
        "enabled": false, "order": 2, "origin": "ZIP", "archive": "ui-kit.zip" }
    ]
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `version` | int | `3` — the single-tree shape. 1 and 2 were two trees keyed by kind and are not in the wild |
| `storageId` | string | The storage subtree **this branch owns outright** — see §4. Every path must be inside it |
| `folders[]` | array | `id`, `path` (slash-separated, relative to the root of the tree), `enabled`, `order`, `origin` (`MANUAL`/`ZIP`), optional `archive`, `createdAt`, `createdBy` |
| `assets[].id` | string | Stable identity, minted once. Every copy path (clone, publish, export, import) preserves it. Nothing else may identify a file — a rename changes the path |
| `assets[].kind` | string | `JS`, `CSS`, `HTML` or `OTHER`, **derived from the extension** — see §2 |
| `assets[].name` | string | The file's own name inside its folder |
| `assets[].folder` | string | The folder path it sits in; `""` is the root. **Every segment must be a declared folder** |
| `assets[].path` | string | Storage path **relative to the tenant root**. NEVER write `t/{id}/…` here — see §4 |
| `sha256`, `size` | string, int | Of the bytes. The hash is the cache key in the served URL AND the only thing that tells a real file from storage's placeholder, so it must match |
| `enabled` | bool | Meaningful for `JS`/`CSS` only. A file that is off keeps its bytes and its place in the order |
| `order` | int | Position in the registry's single list. A JSON **array** plus an explicit integer — object key order does not survive a `jsonb` round trip |
| `origin` | string | `EDITOR`, `UPLOAD` or `ZIP`. Informational, except that it decides `isolate` |
| `archive` | string | The archive it came from, when it came from one |
| `isolate` | bool | **JS only, and not an author-facing setting** — see §4 |
| `skins` | array | **CSS only.** Empty = every skin, which is the default — see §5 |
| `provides`, `requires` | array | Globals the script publishes / uses. Recorded so the screen's suggestions are instant — see §7 |
| `updatedAt`, `updatedBy` | string | ISO-8601 instant, and an email. A string, not a temporal type: the archive is written with plain Gson and would round-trip a date differently from the database |

⚠️ **A branch with no files has no key at all.** `globalAssets` absent, `null`, or a registry with two empty
arrays all mean the same thing and all are valid. Do not write `"globalAssets": {}` — it parses, but say what
you mean.

---

## 4 · The bytes: `tenant-files/webassets/<storageId>/…`

`tenant-files/` in the archive is the whole `t/{tenantId}` subtree of the file storage, and it is restored
under the NEW tenant id on import. So the bytes travel with the archive for free — and the two halves line up
only if `path` is the tenant-relative one:

```
tenant-files/
  webassets/
    a41f0c9e22b7451d/          ← the storage id of ONE branch
      brand.css
      uikit/                   ← the archive's own layout, preserved
        uikit.css              ←  so url(../fonts/icons.woff2) inside it resolves
        jquery.min.js
        fonts/
          icons.woff2
```

⛔ **Never persist an absolute `t/{id}/…` path anywhere.** The import re-homes every stored file under a new
tenant id and rewrites **nothing** inside the registry, so an absolute path survives the import intact — and
then reads, successfully, from the DONOR project, because the donor's storage still exists. There is no error
and nothing to notice.

⛔ **Anything outside `webassets/<storageId>/` is refused by the serving endpoint**, deliberately: the
project's database dump and its version-tag snapshots live one directory up, under the same `t/{id}/`.

### One storage subtree per BRANCH

Two branches never share a subtree. Cloning or publishing a branch mints a new `storageId` and copies the
tree. That costs one directory copy and buys the thing that matters: **editing a file in a draft cannot
rewrite what the published site is serving.** Sharing the bytes and being careful was tried first and produced
exactly that bug — a publish copies the registry verbatim, so both branches named the same file, a save in the
draft changed the published page's script, and the published branch's recorded hash then pointed at content
that no longer existed.

### Containment — what "prefixes so nothing collides" actually means

| Concern | What the platform does |
|---|---|
| A script's top-level `var`/`function` becoming a global | **`isolate`** — the file is served wrapped in an IIFE with a `try`/`catch`. **Decided by where the file came from, not by a checkbox:** something typed into the editor is a snippet and is wrapped; anything uploaded or unpacked is a library and is not, because a UMD bundle has to be able to publish its own global — wrapping it is how you get "jQuery is not defined" two files later |
| An error in one of these files breaking the platform's JS | Each file is its own `<script>` tag, so a throw in one cannot stop another. A trap installed before all of them logs anything that comes out of a project file as `[project asset] <file>: …` and keeps it out of the platform's own error handling |
| Overwriting a name the platform owns | The trap samples `window` before the project's deferred scripts run and again after `DOMContentLoaded`, and reports what was added. It reports rather than restores — silently undoing an author's assignment is the worse surprise |
| A stylesheet reaching parts of the page it should not | **Nothing, by design.** A project stylesheet is emitted after everything else the page contributed, so an unscoped rule beats the platform's own at equal specificity across every screen of the project. That is what a brand stylesheet is for — but it is worth deciding rather than discovering: a vendored `bootstrap.min.css` uploaded whole will restyle the builder's chrome too. Scope it in the sheet itself (`.my-app .table { … }`) when that is not what you want |

---

## 5 · A stylesheet can be limited to particular skins

`skins` is a list of skin NAMES — `Standard`, `Dracula`, `Forest`, `Dark`, `Dark Blue`.

* **Empty means EVERY skin**, and that is the default and almost always right: a project stylesheet is about
  the project, not about the palette it is being viewed in.
* A non-empty list is the exception — a sheet that patches one theme's colours, or overrides something only
  the dark skins define.

It is applied at **include time**: a sheet keyed to `Dracula` is not merely inert under `Standard`, it is not
sent at all. And a project that has any skin-keyed sheet makes the theme switcher fall back to a full page
reload instead of swapping the skin's `<link>` in place — the swap cannot exchange a sheet that was chosen on
the server when the page was rendered.

⚠️ **Names, not an enum.** A project exported from an installation that has a skin this one does not must keep
the name so the sheet comes back when it is imported home again. An unrecognised name simply matches nothing —
which means a typo is a sheet that loads **nowhere**. `validate` warns about names outside the five.

⛔ **A script is never filtered by skin.** A script that behaved differently per theme would be invisible on
the screen that configures it; read the CSS variables at runtime instead ([24a](24a-theming-and-dark-mode.md)).

---

## 6 · Order

One sequence for the whole project, by `order` — stylesheets and scripts numbered together. Stylesheets are
emitted as `<link>`, scripts as `defer`red `<script>`, so their relative order among themselves is what
matters and the browser handles the two kinds independently.

Load order is **independent of the folder tree**: a library in `vendor/` can load before application code at
the root. That is why the screen shows each loadable file's position as a number — without it, moving a file
past one in another folder is a gesture with no visible result.

`defer` is what puts the project's scripts after the platform's own — the platform's libraries (Bootstrap,
toastr, the jQuery plugins) are ordinary `<script>` tags at the end of the body and run during parsing, while
deferred scripts run after it, in declared order. A project script may therefore assume `$`, `$.fn.*` and
`bootstrap` exist. It may **not** assume the DOM is finished being built — a CMS page keeps rendering panels
over ajax long afterwards.

When an archive is unpacked, the order is worked out rather than guessed, strongest evidence first:

1. **a demo page inside the archive**, if there is one — its `<link>`/`<script>` order is the library author's
   own statement of what needs what, and beats anything inferable. It is trusted only when it actually
   describes most of what the archive contains (one tag pointing at a CDN is not an ordering);
2. otherwise a ranked heuristic: stylesheets first; known base libraries in dependency order
   (jQuery → Popper → Bootstrap → …); vendored directories before application ones; shallower before deeper;
3. then a dependency pass: a file that publishes a known global is placed before every file that mentions it,
   and a jQuery plugin lands after jQuery. A cycle keeps the heuristic order rather than failing.

The result is a starting point. `order` is author-owned and the screen has up/down controls on every row.

---

## 7 · The suggestions — what the screen offers when you switch something on

Switching a script on is the moment an author is most likely to be one file short and least likely to know
which one: a minified bundle does not announce that it needs jQuery, it simply throws. So every script's
published and used globals are recorded on its registry entry when its bytes are written (`provides` /
`requires`), and the question "what else does this need?" becomes arithmetic over the registry rather than a
scan of every file in storage.

Four checks, offered as suggestions a human accepts or ignores — **nothing is ever switched on automatically**:

1. a folder switched **off above** the file (it is on and still does not load);
2. a global it uses that nothing switched-on publishes, and a switched-off file in this project that does —
   followed transitively, so turning on a plugin can offer the whole chain underneath it;
3. a provider that is on but ordered **after** the file that needs it (fails in the browser exactly like a
   missing file, and looks fine in a listing);
4. the stylesheet half of a kit whose script you just switched on.

Over MCP the same four run as `nct_globalresource_suggest` — with no `assetId` it audits everything
currently switched on. Run it before handing work over.

---

## 8 · What an archive may contain

* `.js` and `.css` are registered and can be switched on.
* `.html` is stored, editable and served — and read for its load order (§6). It is never loaded on its own.
* fonts, images, `.map`, `.json`, `.txt`, `.svg` are stored so relative references resolve, and never loaded.
* A single wrapping folder (`kit-1.2.3/`) is unwrapped — nearly every kit is zipped inside one.
* When an archive ships both `x.js` and `x.min.js`, the plain one is ordered last with a note: they are the
  same program and loading both runs it twice.
* Caps: 400 entries, 20 MB unpacked, 6 MB per entry.
* Everything lands in **one folder of its own**, named by the author or after the archive. That is what makes
  "switch this whole kit off" one click, and what keeps two kits from colliding on a shared `main.css`.

---

## 9 · Known gaps — say these out loud rather than discovering them

* ⛔ **Environment publish does not carry these files.** Creating an environment does (it is a full export and
  import); a later dev→prod *publish* moves definitions only and copies no bytes at all. The publish plan
  raises a CAUTION naming how many files differ, so it is visible rather than silent — but the fix is to add
  the file in the target, or to recreate the environment.
* ⚠️ **Every file is inside every future archive, and inside every version tag.** `tenant-files/` is the whole
  tenant subtree, and a tag is itself an archive stored in that subtree. A 5 MB vendored kit is 5 MB in every
  snapshot from then on — and, because each branch owns its own copy, once per branch.
* ⚠️ **Deleting a file deletes its bytes.** There is no reference counting and none is needed: a branch owns
  its subtree, so the only registry that could have named the file is the one that just stopped. To stop a
  file loading without losing it, switch it off.
* ⚠️ **A saved change needs a page reload to be seen.** The include happens when a page is rendered; an ajax
  panel update does not re-run it.

---

## 10 · Done when

- [ ] the requirement really is "on every page" — otherwise it is [24](24-html-component-studio.md)
- [ ] `globalAssets` is `version: 3` with a `storageId`, a `folders[]` array and an `assets[]` array
- [ ] every `assets[].folder` is a declared folder, and every folder's parent is declared too
- [ ] every `path` is `webassets/<storageId>/…`, tenant-relative, never `t/{id}/…`
- [ ] every `path` has a matching file under `tenant-files/`, and `sha256`/`size` match its bytes
- [ ] only `JS` and `CSS` entries are `enabled`; fonts, images and HTML fragments are not
- [ ] `kind` agrees with the extension on every entry, and no name contains `-ver-`
- [ ] a stylesheet with a `skins` list names only skins this platform has — a typo loads nowhere
- [ ] the load order puts every library before what uses it (`globalresource ls` shows the numbers)
- [ ] the project does not rely on an environment publish to move these

---

**See also:** [00-export-format-and-import.md](00-export-format-and-import.md) §3 (`branches.json`) and §8
(`tenant-files/`) · [24-html-component-studio.md](24-html-component-studio.md) (per-component JS/CSS) ·
[24a-theming-and-dark-mode.md](24a-theming-and-dark-mode.md) (the skin tokens a project stylesheet should use)
· [28-support-mode-over-mcp.md](28-support-mode-over-mcp.md) §5a (the same object over MCP)
