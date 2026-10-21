# 34 · Static pages — a page that answers with a file, not with plugins

> **The term.** A **static page** is a page of the site tree (same alias, parent and access as any page) that
> answers its URL with exactly one text or one file and a `Content-Type` — `robots.txt`, `sitemap.xml`, a web
> app manifest, a verification file, a public JSON document, a script or stylesheet at a stable address, a
> Markdown document, a logo, a PDF brochure, a font. Every other page is a **Dokie page** (plugins + layout).
>
> **Scope.** The node shape in `branches.json`, where an uploaded file's bytes live in the archive, how the
> served type is decided, what the URL is, who may open it, and what `validate` checks.
> **Not here:** files loaded on EVERY page or referenced from a stylesheet → [29](29-global-resources.md);
> code that belongs to one screen → [24](24-html-component-studio.md); the page tree itself, `roleAccess` and
> aliases → [01](01-content-model-and-pages.md).

| | |
|---|---|
| What it is | a `siteMapPage` node with `pageType: "static"` and **no children** |
| Text response | the node's `staticBody` property (UTF-8, ≤ 1 MiB) |
| File response | bytes in `tenant-files/static-pages/<sha256>/<name>`, path in `staticFilePath` — the file wins over the text |
| Content type | `staticContentType`, or empty = decided by the file's name, else the alias's extension |
| URL | the page's alias path, exactly like any page (§4) |
| Access | the page's own `roleAccess` — public, signed-in users, or role groups (§5) |

> **🔧 Tooling.** `page add-static --parent P --name N --alias robots.txt (--text S | --text-file F | --file F)
> [--content-type T] [--auth|--public]` — a new static page; `page set-static --page P [--text…|--text-file…|
> --file…] [--content-type T] [--dokie]` — change what it answers with, or turn a page into / out of a static
> one. They write the slots, hash the file into `tenant-files/static-pages/`, keep the path relative. `validate`
> then checks every static page against the bytes in the bundle. Live, after import, the same is done over
> MCP: `nct_ui_set_static_page` / `nct_ui_get_static_page`.

---

## 1 · The decision: is this a static page?

1. **Does something OUTSIDE the project's screens fetch it by URL** — a crawler, another site embedding a
   script, a partner downloading a document, a phone installing the app, a link in an email? → a static page.
2. **Must it be present on every page, or is it referenced by a stylesheet's relative `url(…)`?** → Global
   resources ([29](29-global-resources.md)), not this.
3. **Is it part of one screen?** → a component ([24](24-html-component-studio.md)).

A static page is ONE response at ONE address. Ten files of one kit are not ten static pages — that is a
Global-resources folder.

⛔ **Not a sandbox.** An HTML or SVG static page is served from the project's own origin, with the visitor's
session — exactly like an HTML component. Treat its content as code.

---

## 2 · The node

```jsonc
{
  "id": null,
  "identifier": "<uuid>", "uniqueIdentifier": "<uuid>",
  "name": "Robots",
  "pluginName": "siteMapPage",            // unchanged: a static page IS a page
  "alias": "robots.txt",                  // the last URL segment, WITH its extension
  "active": true, "order": 7,
  "children": [],                         // ⛔ none — no parsis, no layout, no pages under it
  "roleAccess": { "publicReadAccess": true, "authenticatedUserAccess": false,
                  "accessors": {}, "roleGroupAccessors": {} },
  "properties": {
    "pageType":          { "key": "pageType", "propertyType": "STRING", "stringValue": "static" },
    "staticContentType": { "key": "staticContentType", "propertyType": "STRING", "stringValue": "text/plain" },
    "staticBody":        { "key": "staticBody", "propertyType": "STRING", "stringValue": "User-agent: *\nDisallow:\n" }
  }
}
```

An uploaded file instead of text:

```jsonc
"staticFilePath": { "key": "staticFilePath", "propertyType": "STRING",
                    "stringValue": "static-pages/9f86d0…(64 hex)…/brochure-2026.pdf" },
"staticFileName": { "key": "staticFileName", "propertyType": "STRING", "stringValue": "brochure-2026.pdf" },
"staticFileSize": { "key": "staticFileSize", "propertyType": "LONG",   "longValue": 482113 }
```

and the bytes at `tenant-files/static-pages/9f86d0…/brochure-2026.pdf` in the archive.

| Property | Rule |
|---|---|
| `pageType` | `"static"`; absent or `"dokie"` = a normal page. Switching back to `"dokie"` keeps the text and file, so switching again restores them. |
| `staticContentType` | `type/subtype[; params]`, no line breaks. Empty/absent = decided by name (§3). |
| `staticBody` | UTF-8 text, `\n` line ends, at most 1 MiB. Larger text → store it as a file. |
| `staticFilePath` | **tenant-relative**, exactly `static-pages/<sha256 of the bytes>/<name>`; `<name>` uses only `A–Z a–z 0–9 . _ ( ) -` and space — **no `+`**: the storage reads a `+` back as a space and never finds the file (`page add-static` replaces it). |
| `staticFileName` / `staticFileSize` | the file's own name (offered by "Save as") and size; at most 25 MiB. |

Everything else a page carries is ignored while it is static: `layout`, `pageTitle`, `pageDescription`,
`Redirect`, `metaTags`, `Body Class`. `aliasParamsMaxCount` still applies — set it and the same file also answers
at `/<alias>/<anything>`; leave it unset and those URLs are 404. A page that HAS pages under it cannot be made
static (the dialog, MCP and the toolkit refuse). Switching a Dokie page to static keeps its plugins; they come
back when it is switched back.

⛔ **Build a static page with `page add-static`, not `page add` + `page set-static`.** `page add` clones the full
page scaffold (parsis, layout), which a static page never renders and `validate` then warns about.

⛔ **The hash in the path is checked before a single byte is served.** Edit the bytes in `tenant-files/` and
the page answers 404 — re-add the file with `page set-static --file`, which writes a new path.
⛔ **Never `t/<id>/…`.** An import re-homes `tenant-files/` under the new project's id and rewrites nothing in
the tree; an absolute path would keep pointing at the donor project.

---

## 3 · The served content type

In order: the page's `staticContentType` → (file) the file's name → the alias's extension → `text/plain` for
text, `application/octet-stream` for a file. `staticBody` text is always sent with `charset=utf-8` (it is UTF-8)
unless the type already names a charset; an uploaded FILE is sent with no charset added — it may be a
Windows-1251 CSV — so name the charset in `staticContentType` when it matters. Text written in `staticBody` is
text whatever the alias says: a page `logo.png` whose response was TYPED is served as `text/plain`, so a binary
format always comes as a file. iCalendar (`.ics`) and vCard (`.vcf`) text is answered with the CRLF line ends
their specifications require. An uploaded text file loses a leading byte-order mark and its CRLF when it goes
into `staticBody`; when the exact bytes matter (a BOM-marked CSV for spreadsheet software), store it with
`--file`.

The response also carries `X-Content-Type-Options: nosniff` — a browser will refuse a script served as
`text/plain`. So a script page is `app.js` (or says `text/javascript`), a stylesheet `site.css`, a module
`module.mjs`, a manifest `site.webmanifest` or `application/manifest+json`.

Every common format is known by extension: text (`txt md html css js mjs ts json map webmanifest jsonld geojson
xml xsl rss atom svg csv tsv yaml yml toml ini properties env sql graphql ics vcf vtt srt diff patch tex rst adoc
pem` and source files `sh py java kt groovy cs c cpp go rb php rs swift ps1`) and binary (`png jpg jpeg gif webp
avif apng bmp ico tif heic psd eps pdf rtf doc docx xls xlsx ppt pptx odt ods odp epub woff woff2 ttf otf eot
mp3 wav ogg m4a aac flac weba mid mp4 webm ogv mov avi mkv zip gz tgz tar 7z rar bz2 xz jar apk dmg exe msi iso
wasm glb gltf stl usdz cer crt p12 sqlite parquet`). Anything else: say the type.

Caching: `ETag` from the content, `Cache-Control: no-cache` (always revalidated, answered `304` when
unchanged) — so an edit is visible on the next request, and nothing needs a version in its URL.

Other sites: a PUBLIC static page is sent `Access-Control-Allow-Origin: *`, so another site's script may
`fetch()` a public JSON document and an `@font-face` elsewhere may load a public font; `<script src>`, `<img>`
and `<link>` work from anywhere anyway. A page for signed-in readers sends no such header and is readable by
the project's own pages only. A machine-to-machine call with credentials is the public API
([32](32-public-api.md)), not a static page.

---

## 4 · The URL

Exactly the page's alias path, like any page:

- on the platform's shared host: `/<organization>/<project>/<parent aliases…>/<alias>` —
  e.g. `/acme/portal/robots.txt` for a page directly under the root;
- on the project's own domain: `/<parent aliases…>/<alias>` — e.g. `https://portal.acme.example/robots.txt`.

⚠️ A crawler reads `robots.txt` only at a DOMAIN root, and site-verification files are looked for there too —
that works on the project's own domain only. A `sitemap.xml` may live anywhere when `robots.txt` names it or it
is submitted to the search engine, but it covers only the URLs under its own path (on the shared host:
`/<organization>/<project>/…`). Say so in the handover instead of promising search-engine behaviour.

The alias is matched exactly, case included (`README.md` ≠ `readme.md`).

⚠️ **The platform's own files win.** On the project's own domain the platform serves its assets from top-level
folders (`img`, `common`, `dokie`, `security`, `raven`, `calendar`, `checkbox`, `chartjs`, `echarts`, `mermaid`,
`codemirror5`, `architectui-html-pro` and a few more). A static page at a path that IS one of the platform's
files is never reached; do not give a top-level page one of those aliases.

⛔ **A NORMAL page whose alias ends like a file** — `.html .css .js .js.map .map .ico .png .jpg .jpeg .gif .webp
.svg .woff .woff2 .ttf .eot .txt .img .image .comssets` (exactly these, lower case) — imports fine and never
opens: those URLs go to the platform's static-file handler unless a STATIC page claims them. `validate` warns.

**Linking to a static page from a page or a component.** The prefix differs between the shared host and the
project's own domain, so a hard-coded `/<organization>/<project>/…` breaks the day the project moves to its own
domain. Link relative to the page that links (`robots.txt` from a top-level page, `../manifest.webmanifest` one
level down), and list every static page's full URL, for both hosts, in the handover.

---

## 5 · Who may open it

The page's `roleAccess`, read exactly as for any page: `publicReadAccess: true` → anyone, no sign-in;
`authenticatedUserAccess: true` → any signed-in user; otherwise the role groups with `view`. A visitor who must
sign in is sent to the sign-in page and back — except on a project that signs in through single sign-on, where
a not-signed-in visitor gets a plain `401` (a file cannot start the browser sign-in; opening any normal page of
the project first signs them in). Public pages are sent `Cache-Control: public`, the others `private`. A crawler
or another site can only fetch a PUBLIC static page. A project's own `404` / `401` page may be static and keeps
its status.

`page add-static` copies the parent's `roleAccess`; pass `--public` for anything fetched from outside.

---

## 6 · Where it shows

- **The authoring trees** open a static page's file in a new tab; it holds no pages.
- **Left nav** — only if you add a quick link to it ([17](17-left-nav-quick-links.md)); the link then opens the
  raw file. Static pages are not expected in the nav and `validate` does not ask for one.
- **Environment publish** carries the page AND its uploaded file to the other environment; a file that could not
  be copied is reported as a failed row (the page itself was published).
- **Export / import** carries both (`tenant-files/static-pages/…`).

---

## 7 · What `validate` checks

```
x page Logo (logo.png): its file tenant-files/static-pages/…/logo.png is not in this bundle — the page would answer 404. (34)
x page Logo (logo.png): tenant-files/static-pages/…/logo.png does not hash to the sha256 in its path — … (34)
x page Feed (feed.xml): staticFilePath 't/12/static-pages/…' must be static-pages/<sha256>/<name>, relative … (34)
x page App (app.js): staticContentType 'javascript' is not type/subtype (e.g. text/javascript). (34)
x page Big (big.txt): staticBody is 1300000 bytes; the limit is 1048576 — store it as a file … (34)
x page X (x) sits under the static page 'Docs' — a static page holds no pages. (34)
! page About (about.html): a normal page whose alias ends like a file — … never opens … (34)
! page App (app.js): a static page has plugin children; they are never rendered — remove them. (34)
```

---

## 8 · Known gaps

- The site ROOT cannot be static, and a static page holds no pages.
- One response per page: no per-locale variants, no templating, no query-dependent output. Content that varies
  is a rule-backed endpoint ([32](32-public-api.md)) or a Dokie page.
- Uploaded files are content-addressed and never deleted when replaced; an old version stays in storage (and
  in exports) until the project is cleaned up.
- The response is `inline`; a file meant to be saved rather than opened should simply be a type the browser
  does not display (an archive, an office document).

---

## 9 · Done when

- [ ] every file a requirement names "at a URL" is a static page with the alias it will be fetched by
- [ ] each one is public unless the requirement says who may read it
- [ ] scripts, stylesheets and manifests have a type a browser executes (§3)
- [ ] binary formats are files (`--file`), text formats are text (`--text-file`) so they stay editable
- [ ] `validate` shows no `(34)` finding
- [ ] the handover lists every static page's full URL, and says which only work on the project's own domain (§4)

**See also:** 01 §Pages (the node fields), 00 §8 (`tenant-files/`), 29 (files on every page), 17 (nav links), 32
(dynamic answers to machines).
