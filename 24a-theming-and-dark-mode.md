# 24a · Theming & dark mode — how to write CSS that survives all five skins

> 📐 **Field evidence — three of four deliveries shipped ZERO authored CSS — read this before writing any:** [10-visual-design.md](references/10-visual-design.md) · [09-studio-components.md](references/09-studio-components.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

> **Scope.** Every line of CSS **you** author into a project: an `nct.html.plugin`'s
> `studioModel.css.byTheme`, a `chart.js.plugin`'s `cssByTheme` (its **Css** tab), an inline `<style>`
> inside any `html` property, and every `style="…"` attribute on a hand-written `<div>`. Read it **before** you type the
> first `background:` of a build.
> **The one fact that decides everything:** a project ships **five skins and four of them are dark**
> (`Skin.java`). A hex literal you type is correct on **at most one** of them. So the default
> outcome of "just write nice CSS" is a component that is broken for 80 % of the theme matrix.
> **Not in this doc:** the `studioModel` schema and the JS runtime → [24](24-html-component-studio.md);
> chart-specific theming (Plotly `paper_bgcolor`, semantic chart palettes) → [22](22-charts-params-and-filters.md) §6;
> composing a body out of documents and the `<plugin>`/`<include>` grammar →
> [24b](24b-html-composition-and-plugin-tags.md); how a component is split into files →
> [24d](24d-html-component-structure.md).
> You never edit the platform's own stylesheets — this doc is only about the CSS *you* ship.

| | |
|---|---|
| The skin enum | `Skin.java` — `Standard`, `Dracula`, `Forest`, `Dark`, `Dark Blue` |
| How a skin is applied | whole-stylesheet swap in `PluginBasePage.java` (`base.css` → `theme-common.css` → `<skin>.css`). **No body class, no data-attribute** |
| Which skin is active | `PluginBasePage.resolveSkin()` (user state → tenant state → `DARK`, the platform default); a **chart** asks that same method through the shared `NctThemeCss` helper, a **studio component** resolves it itself from the **user** value only (else `Dark`) |
| Where authored CSS goes | `properties.studioModel.stringValue` → `css.byTheme` (`HtmlStudioModel`), a chart's `properties.Javascript.stringValue` → `cssByTheme` (+ the legacy `css` field, folded in as `"*"`), or an inline `<style>` in `properties.html.stringValue` (rendered **raw** by the mrjun module's `AbstractHtmlPlugin`, not nct-ui) |
| Scoping | every rule you author is prefixed with the instance's id — `#dokie-plug-<markupId>` for a studio component, `#<markupId>` for a chart. An inline `<style>` in an `html` property is **not** scoped |
| `mrjun.py validate` coverage | **three WARNINGS, zero errors:** colour literals inside a studio `studioModel` → `css.byTheme["*"]` block (`_check_theme_safe_css` in `validate_cmds.py`), an inline `<style>` in an `nct.html.plugin`'s `properties.html`, and Plotly-without-`paper_bgcolor` on charts. Everything else in this doc — a colour in `style=`, a dead `html.dark …` selector, `badge-light`, `h-100`, unbalanced braces, a misspelled `byTheme` key, and **every line of a chart's per-theme CSS** — ships silently green. Exact gap list: §9. |

> **🔧 Tooling.** There is no CSS-specific command — authored CSS rides the slots you already write:
> `node set-studio <id> --json @studioModel.json` (the whole `studioModel`, incl. `css.byTheme`),
> `node add --parent <slot> --plugin nct.html.plugin` / `node add --parent <slot> --plugin
> chart.js.plugin --model @chart.json` (`--parent` is **required**),
> `show node <id>` (read back what a node actually carries), `find --plugin nct.html.plugin`
> (enumerate every authored-HTML node before an audit), then `validate` → `pack`.
> Full index and rules — [`tools/README.md`](tools/README.md). ⚠️ `validate` catches **two** of this doc's
> own failure modes (plus the chart Plotly one) and only as **warnings** — a project whose sole problem is
> theming still exits 0 and packs, and a chart's CSS is never looked at; §9 gives the gap list and the
> grep/audit script that actually gate.

---

## 0 · Why this doc exists — projects ship white cards on a black page

This is the failure mode this document exists to prevent, in the shape it actually takes: a project
hand-authors its flagship UI as a set of `nct.html.plugin` screens (`<pfx>_<screen>_ui`, where `<pfx>` is the
project's own short prefix), and every one of them is styled like this:

```css
/* excerpt of what shipped — one CSS blob, copy-pasted byte-identically into most of the screens */
.<pfx>-kpi   { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:16px 18px; }
.<pfx>-kpi-l { font-size:11px; color:#6b7280; font-weight:600; }
.<pfx>-kpi-v { font-size:28px; font-weight:700; color:#111827; }
.<pfx>-card  { background:#fff; border:1px solid #e5e7eb; box-shadow:0 1px 2px 0 rgb(0 0 0/.05); }
.<pfx>-btn-primary { background:#10b981; color:#fff; }
.<pfx>-warn  { color:#92400e; }
```

What such a bundle looks like when you audit it (run the script in §9 on **your own** bundle and read the
same columns):

| What to look for | What a broken bundle shows |
|---|---|
| `css.byTheme` keys per component | exactly one — `"*"` — i.e. one look for all five skins |
| distinct CSS blobs | far fewer than components: one blob copy-pasted everywhere |
| CSS custom properties / theme tokens used | **none** |
| `prefers-color-scheme` blocks | **none** |
| hex literals per node (`html` + `css`) | dozens each |
| nodes that *also* carry an inline `<style>` in `properties.html` | several — and that CSS is **global**, not scoped |
| a component whose `studioModel` is `{"libs":[],"docs":[],"scripts":[],"css":{"byTheme":{}}}` | `isEmpty()` → the studio never activates, so there is **no wrapper and no scoping**, and its inline `<style>` leaks page-wide |

Result: on **Standard** (the one light skin) the screens looked designed. On **Dracula, Forest, Dark
and Dark Blue** — one of which is what the default user sees, because a dark skin is the fallback everywhere
(both the page's skin resolution and the studio component's) — every card is a white slab floating on a
near-black page, the `#111827` headings on `#fff` sit inside a `#13181b` page, and the platform's own
chrome around them (breadcrumb, sidebar, table) is correctly dark. The screens are *unusable* on 4 of
the 5 skins, and **nothing offline objected**: at the time the validator had no authored-CSS check at all.
It has one now — `mrjun.py validate --project ./app` prints one `css.byTheme` colour-literal warning per
offending component plus one per inline `<style>`. They are *warnings*: a build full of them is still
"OK — no errors". Offline gates narrow the blast radius; only §9 closes it.

The fix is not "add four more `byTheme` blocks". It is §2 (paint nothing) and §3 (tokens). Both cost
less to write than the hardcoded version.

---

## 1 · The five skins — what actually loads, and what you therefore cannot select

### 1.1 The enum

`Skin.java` — the `getName()` string is the canonical id **everywhere** (the stored user
setting, the org allow-list, and the `css.byTheme` key). Spaces matter.

| constant | `getName()` | `getBackgroundColor()` | stylesheet (`getCsses()`) | light/dark |
|---|---|---|---|---|
| `STANDARD` | `Standard` | `#f8f9fa` | `/architectui-html-pro/themes/standard.css` | **light** |
| `DRACULA` | `Dracula` | `#282a33` | `themes/dracula.css` | dark |
| `FOREST` | `Forest` | `#161817` | `themes/forest.css` | dark |
| `DARK` | `Dark` | `#080e19` | `themes/dark.css` | dark ← **the platform default and the fallback** |
| `DARK_BLUE` | `Dark Blue` | `#13181b` | `themes/dark-blue.css` | dark |

`Skin.byName()` (`Skin.java`) returns `DARK` for *any* unknown string — a typo in a stored
value never errors, it silently becomes Dark. `Skin.allNames()` is what the studio's
CSS tab lists (`HtmlStudioPanel.java`), so those five strings plus `"*"` are the **only**
legal `css.byTheme` keys.

### 1.2 Load order — three stylesheets, in this order, always

Every plugin-hosting page emits exactly three stylesheets, in a fixed order: first `base.css`, then —
for the ArchitectUI look — `theme-common.css`, then the stylesheet(s) of the **active skin**. Nothing
else is injected between them, so the last one always wins on equal specificity.

1. **`base.css`** — ArchitectUI + Bootstrap 5.0-era defaults, **24 508 lines**. Defines the `--bs-*`
   fallbacks near the top of the file (`--bs-primary:#3f6ad8`, `--bs-success:#3ac47d`, `--bs-info:#16aaff`,
   `--bs-warning:#f7b924`, `--bs-danger:#d92550`, `--bs-light:#eeeeee`, `--bs-dark:#343a40`).
   *(5.0-era, not 5.3: it ships `.btn-close`, `.form-floating`, `--bs-gutter-x`, but none of
   `--bs-body-font-family` / `--bs-border-radius` / `--bs-link-color-rgb` / `--bs-heading-color`.)*
2. **`theme-common.css`** (617 lines) — structure + `var()`-driven colour, loaded for **every**
   skin. Near-literal-free by construction: almost every colour in it is a `var()` with a fallback rather
   than a bare hex. It is the house reference implementation of the fallback idiom (§3.2).
3. **`<skin>.css`** — the whole visual identity. Ships **after** the other two, so it wins on equal
   specificity.

> ⛔ **YOUR HEAD CSS IS EMITTED *BEFORE* ALL THREE, NOT AFTER.**
> **Mechanism:** Wicket 9.11 renders header contributions **child-first**
> (Wicket's default is `ChildFirstHeaderRenderStrategy`: application headers → **child** headers →
> *then* the root component). The three
> stylesheets come from `PluginBasePage.renderHead` — the **page**, i.e. the root — so they are written
> last; your `CssHeaderItem.forCSS(...)` from a studio component is written
> **first**.
> **Consequence:** at *equal* specificity the theme wins over your head CSS. What actually saves you is
> the scoper's `#dokie-plug-<id>` prefix (+100 specificity, §5.2) — **not** source order. Un-prefix a rule
> and it loses to the theme even though you "wrote it later".
> **The one exception:** an inline `<style>` inside `properties.html` sits in the **body**, after the whole
> head, so it *does* win at equal specificity — which is exactly why an unscoped body `<style>` restyles the
> rest of the application (§5.3, §5.5).
> Against the theme's `!important` blocks you lose in every case. See §7.2.

### 1.3 ⛔ A skin is a whole-stylesheet swap — there is **no** theme class on `<html>` or `<body>`

> ⛔ **YOU CANNOT WRITE `body.dark-theme .x`, `html[data-theme="dark"] .x`, OR ANY ANCESTOR-THEME SELECTOR.**
> **Mechanism:** `addCss` (`PluginBasePage.java`) renders a plain
> `<link href="/architectui-html-pro/themes/dark-blue.css?v=…">`. The *only* per-skin DOM write in the
> whole page is an inline background colour on `<body>`:
> `document.body.style.backgroundColor='#13181b'` (`PluginBasePage.java`). The `bodyClassScript`
> next to it comes from the page's own **"Body Class"** content property, not from the skin
> (`PluginBasePage.java`); `app-theme-white` on `.app-container` is a static legacy ArchitectUI
> class, not a skin hook — it is hardcoded in 9 static page markups (e.g. `NctInternalErrorPage.html`),
> styled at `base.css`, and **no Java anywhere writes it**.
> **Symptom you see:** the selector simply never matches. Your dark-mode block is dead CSS; the
> component renders in whatever the un-prefixed rules said — i.e. light.
> **Caught by `validate`?** **No.** Authored CSS is *scanned* for colour literals (§9) but never **parsed** —
> no selector ever reaches a check, so a dead theme selector lints identically to a live one.
> **The supported discriminator** is the `css.byTheme` key (§5) and nothing else. And even inside a
> studio component `html.dark .foo` cannot work, because the scoper rewrites it onto the wrapper — §5.3.

### 1.4 Which skin is active — per **user**, not per project

The active skin is resolved in a fixed order of precedence, and the **first** answer wins:

1. the **signed-in user's** own stored skin preference;
2. otherwise the **project-level** stored value;
3. otherwise the platform default, **`Dark`**.

Any failure along the way (no user, unreadable state) falls through to that same default — so an
anonymous visitor always lands on `Dark`.

- There are **two** switchers, and both write the same per-user `skin` state value:
  - the **switch in the application header** — Dark ⇄ Standard only. A skin that is neither (Dracula,
    Forest, Dark Blue) renders the switch in its *dark* state, and one click moves the user to
    Standard; the click after that lands on Dark, not back on the third skin. It is hidden for an
    anonymous visitor, who has no per-user row to write.
  - **Project Settings → Appearance** — a `DropDownChoice("skins")` bound to
    `stateService.getUserValue/setUserValue(userId, "skin", …)` (`AppearanceSection.java`),
    followed by `refreshPage()`. This is the only place the other three skins can be reached.
  Both end in `refreshPage()`: **switching a skin is a full page reload**, never an AJAX restyle,
  because the skin is one `<link>` chosen in `renderHead` and an AJAX header contribution can only
  add a second stylesheet, not replace the first.
- Consequence for a studio component: its per-theme CSS is emitted in `renderHead`
  so it is decided *at page render*. There is no client-side theme event
  to react to, and nothing in `ctx` tells author JS which skin is active
  (the mount payload carries no skin — see [24](24-html-component-studio.md)).
- The two authored-CSS surfaces do **not** resolve the skin identically. A studio component's
  `activeSkinName()` reads the **user** value only and returns `Dark` when there is no page user; a
  chart goes through the shared helper, which calls the page's `resolveSkin()` (user → tenant → `Dark`).
  ⚠️ **A public / anonymous page therefore renders your studio component's CSS as `Dark` no matter
  what.** If you author a public landing screen and only ever preview it signed-in on `Standard`, you have
  never seen what your visitors see.
- ⚠️ The tenant branch of `resolveSkin()` is inert in practice: the platform's own Appearance screen writes
  only the per-**user** value, and nothing in the codebase writes a tenant `skin` state value. Do not design
  around a "project default theme" — there is none you can set from a `.mrjun`.

**Business judgement.** Because the skin is a per-viewer preference you cannot pin, *"we will only
support the light theme"* is not an available decision. Any component you ship is going to be looked at
on a dark skin by someone, probably on the very first demo. Budget for it in the first draft of the CSS,
not as a fix-up pass.

---

## 2 · RULE 1 — do not paint at all

The cheapest theme-safe CSS is the CSS you don't write. Every class below is restyled by all four dark
themes and left at correct light defaults by Standard, so it is **already correct on 5/5** with zero
authored colour. Build your markup out of these first, and only reach for §3 tokens for the gaps.

| Need | Use | Verified |
|---|---|---|
| Panel / raised surface | `class="main-card mb-3 card"` (the house pattern) or plain `card` + `card-header` / `card-body` / `card-footer` / `card-title` | every theme defines `.card` twice and the **later** block wins (§7.2), and each also restyles `.card-title`; `.main-card` is untouched by all five themes and simply inherits `.card` |
| Table | `class="table table-hover"` (+ `table-striped`, `table-bordered`, `table-sm`) | every theme sets the `--bs-table-*` locals **inside** `.table`; Standard additionally paints the row hover with a literal rule |
| Buttons | `btn btn-primary` / `-secondary` / `-success` / `-danger` / `-warning` / `-info`, all `btn-outline-*`, `btn-link` | the whole family is rewritten per theme — `.btn-primary`, `-secondary`, `-warning`, `-success`, `-danger`, `-info` and every `.btn-outline-*` have their own block in each of the five theme files |
| Status pill | `badge bg-primary` / `bg-secondary` / `bg-success` / `bg-danger` / `bg-warning` / `bg-info` | `.badge.bg-secondary` is explicitly hardened in each dark theme, as is `.bg-success` |
| Inline message | `alert alert-info` / `-success` / `-warning` / `-danger` | every dark theme restyles the whole `.alert*` family |
| Secondary text | `class="text-muted"` (or `small`) | `dark-blue.css` → `var(--comment)`; `base.css` → `#6c757d` |
| Form field | `form-control` / `form-select` / `form-label` / `form-check` | `dark-blue.css` restyles `.form-control, .form-select, input[type=…], textarea, select` as one group |
| Menus / lists / accordions | `dropdown-menu` + `dropdown-item`, `list-group-item`, `accordion-*`, `modal-content`/`-header`/`-body`/`-footer`, `popover-*` | all restyled per dark theme (e.g. `.list-group-item`, `.accordion-*`, `.dropdown-menu` blocks in `dark-blue.css`) |
| Layout | Bootstrap grid (`row`, `col-md-*`, `g-3`), spacing utilities (`mb-3`, `p-3`, `gap-2`), `d-flex`, `text-end` | structural only — no colour, safe everywhere |
| Full height | **`he-100`**, `he-auto`, `h-sm` | `base.css` — and see the `h-100` trap, §7.1 |

Three things look safe and are not:

> ⛔ **`.badge-light` IS WHITE ON EVERY DARK SKIN.**
> **Mechanism:** `base.css` sets `.badge-light{background:#fff}` and **no theme overrides it
> unscoped** — the only overrides in the four dark files are `.mcp-tools-panel .badge-light`
> (`dark-blue.css`, `dark.css`, `forest.css`, `dracula.css`), which cannot reach
> your markup.
> **Symptom:** a white pill with (usually) white or near-white text on a dark card — an unreadable blob.
> **Caught by `validate`?** No.
> **Fix:** `badge bg-secondary` (hardened per theme) or `badge bg-primary`.

> ⚠️ **A bare `<span class="badge">` is WHITE TEXT ON NOTHING.** Bootstrap 5's `.badge`
> (`base.css`) sets `color:#fff` and **no** background; ArchitectUI's second `.badge` block
> (a second `.badge` block later in the same file) only adds padding/uppercase. So a bare badge is invisible on **Standard** and merely
> unstyled on the dark skins. Always pair `badge` with a `bg-*`.

> ⚠️ **`bg-light` is a DARK surface on a dark skin.** `dark-blue.css` sets
> `.bg-light{background-color:var(--current-line)!important;color:var(--foreground)!important}` plus a
> whole rescue block right after it forcing `.bg-light .text-muted`, `label`, `small`, `strong` to
> `--foreground`. This is *correct* behaviour — but never read `bg-light` as "light"; never pair it with
> a hardcoded dark text colour.

**Business judgement — when do you write CSS at all?** Use the visual builder + platform plugins for
anything that is a list, a form, a tab set, or a KPI over a query — [04](04-crud-table-plugin.md),
[02](02-form-controls-reference.md), [22](22-charts-params-and-filters.md). Author CSS only for the
*shape* of a bespoke screen the plugins cannot express (a custom grid of tiles, a timeline, a
side-by-side compare), and even then: layout, spacing and typography are yours; **colour should still
come from the classes above or the tokens in §3.** If your authored CSS block contains more colour
declarations than layout declarations, you are re-implementing the theme and you will lose.

---

## 3 · RULE 2 — the token contract

When you must paint (a tile background, a hairline, an accent), bind to a CSS custom property. But the
five skins do **not** define the same variables, so a bare `var()` is a trap in both directions. The
table below is a definition census over the five theme files (`grep -c '^\s*<token>:'`) plus `base.css`.

### 3.1 The census

| token | defined in | what to write |
|---|---|---|
| `--bs-body-bg` | **5/5** (`standard.css`, `dark-blue.css`, …) | `var(--bs-body-bg)` |
| `--bs-body-color` | **5/5** (`standard.css`, `dark-blue.css`) | `var(--bs-body-color)` |
| `--bs-border-color` | **5/5** (`standard.css`, `dark-blue.css`, literal `#3d3d3d` in `dark.css`) | `var(--bs-border-color)` |
| `--bs-border-color-translucent` | **5/5** | `var(--bs-border-color-translucent)` |
| `--bs-primary` | **5/5** (`standard.css`, `dark-blue.css`) | `var(--bs-primary)` |
| `--bs-secondary` | **5/5** (`standard.css`, `dark-blue.css`) | `var(--bs-secondary)` |
| `--bs-light` | **5/5** (`standard.css #f4f7fb`; dark = `var(--current-line)`, `dark-blue.css`; `base.css #eeeeee`) | as a **fallback** only — see §3.2 |
| `--bs-link-color` / `--bs-link-hover-color` | **5/5** | `var(--bs-link-color)` |
| `--bs-success` / `-info` / `-warning` / `-danger` / `-dark` | 4/5 in themes, **but `base.css` defines all of them** → effectively 5/5 | `var(--bs-danger)` etc. |
| `--background` | **4/5** — dark only | `var(--background, var(--bs-body-bg))` |
| `--current-line` | **4/5** — dark only | `var(--current-line, var(--bs-light))` |
| `--foreground` | **4/5** — dark only | `var(--foreground, var(--bs-body-color))` |
| `--foreground-muted` | **4/5** — dark only | `var(--foreground-muted, var(--bs-secondary))` |
| `--comment` | **4/5** — dark only | `var(--comment, var(--bs-secondary))` |
| `--purple` / `--pink` | **4/5** — dark only | `var(--purple, var(--bs-primary))` |
| `--green` / `--red` / `--orange` / `--cyan` / `--yellow` | **4/5** — dark only | `var(--green, var(--bs-success))`, `var(--red, var(--bs-danger))`, … |
| `--bs-table-hover-bg` / `--bs-table-hover-color` | **4/5** at `:root` (dark only; Standard sets the row hover with a literal rule instead) | don't read it — tint it yourself, §8 |
| `--nct-aw-*` | **5/5** (`standard.css`, `dark-blue.css`) | only for floating panels/toolbars |
| `--nct-tb-*` | **4/5** — dark only (`dark-blue.css`) | needs a fallback |
| `--bs-tertiary-bg` | **1/5 — Standard only** (`standard.css`) | ⛔ never lead with it — §3.4 |
| `--bs-secondary-bg` | **1/5 — Standard only** (`standard.css`) | ⛔ never lead with it |
| `--bs-primary-rgb` / `--bs-light-rgb` / `--bs-secondary-rgb` | **1/5 — Standard only** (`standard.css`) | ⛔ `rgba(var(--bs-primary-rgb), .1)` is invalid on all 4 dark skins |
| `--bs-secondary-color`, `--bs-emphasis-color`, rest of the Bootstrap 5.3 token set | **0/5** and 0 in `base.css` | do not use — ArchitectUI's base is Bootstrap 5.0-era |

### 3.2 The canonical idiom — two levels, dark token first

**A lookup table, not a paste-in rule** — these are ten *separate* declarations, one per need; they carry
no selector and six of them set `color`, so pasting the block verbatim into a rule leaves you with one
`color`. Pick the line you need (or lift them into `--s-*` aliases on your root class, as §8 does).

```css
/* the whole contract: pick ONE line per need — this is not a rule you paste */
background:   var(--bs-body-bg);                                  /* page canvas          */
background:   var(--current-line, var(--bs-light));               /* raised surface/card  */
color:        var(--bs-body-color);                               /* primary text         */
color:        var(--comment, var(--bs-secondary));                /* muted / secondary    */
border:       1px solid var(--bs-border-color);                   /* hairline             */
color:        var(--purple, var(--bs-primary));                   /* accent               */
color:        var(--green, var(--bs-success));                    /* positive             */
color:        var(--orange, var(--bs-warning));                   /* warning              */
color:        var(--red,   var(--bs-danger));                     /* negative             */
color:        var(--cyan,  var(--bs-info));                       /* informational        */
```

The house implementation of exactly this is `theme-common.css` (the CRUD-join panel), which
even carries the reasoning in a comment right above it:

```css
.crud-join-section {                                        /* theme-common.css */
    background-color: var(--current-line, #f8f9fa);
    color:            var(--foreground,   #212529);
    border-color:     var(--comment,      #dee2e6) !important;
}
```

### 3.3 Why the fallback direction works

`var(--a, <fallback>)` uses `<fallback>` **only when `--a` is not defined on any ancestor**.

- On a **dark** skin, `--current-line` *is* defined (`dark-blue.css` = `#262f36`), so the fallback
  is never consulted → you get the dark surface.
- On **Standard**, `--current-line` is *not* defined anywhere, so the fallback fires → you get
  `--bs-light` = `#f4f7fb` (`standard.css`) → a light surface.

One declaration, correct on 5/5, no `byTheme` block. This only works in this order: **dark-only token
first, `--bs-*` second.** A three-level form (`var(--current-line, var(--bs-light, #f4f7fb))`) is
harmless and slightly safer if you also want a value when the stylesheets fail to load.

### 3.4 ⛔ The reverse trap — a Standard-only token renders LIGHT on every dark skin

> ⛔ **`var(--bs-tertiary-bg, #eef2f8)` / `--bs-secondary-bg` / `rgba(var(--bs-primary-rgb), .12)` ARE
> LIGHT-ONLY.**
> **Mechanism:** these are defined **only** in `standard.css` — census above, 0 hits in
> `dracula/forest/dark/dark-blue.css` and 0 in `base.css`. Written with the usual light literal
> fallback, all four dark skins take the **literal** → a `#eef2f8` panel on a `#13181b` page. Written
> *bare*, the declaration is invalid at computed-value time and the property falls back to
> inherited/initial — usually transparent, which is at least survivable but not what you designed.
> `rgba(var(--bs-primary-rgb), .12)` is worse: the whole `rgba()` is invalid on dark skins, so the
> declaration is dropped entirely.
> **Symptom:** "segments/tiles render on a white background" on every dark skin, while Standard looks
> perfect — the exact bug this trap is named after.
> **Caught by `validate`?** **No** — and note *why*: the literal-hex check deliberately skips any hex that
> sits inside a `var()` fallback (`validate_cmds.py`), which is precisely the shape of this bug. The
> `rgba(var(--bs-primary-rgb), .12)` form has no hex at all, so nothing can see it.
> **Fix:** always lead with the dark-only token —
> `var(--current-line, var(--bs-tertiary-bg, #eef2f8))`, `var(--comment, var(--bs-secondary, #6c757d))`.
> For a translucent accent tint use `color-mix(in srgb, var(--bs-primary) 14%, transparent)`, which
> needs no `-rgb` companion.

> ⚠️ **A bare dark-only token is a silent no-op on Standard.** `background: var(--current-line)` with no
> fallback is simply dropped on Standard, so the tile inherits whatever is under it — usually the page
> gradient. The component looks "flat and borderless" on the light skin and nobody notices until a
> customer opens it. Always two levels.

---

## 4 · The palette, in hex, per skin

Read from the five theme files. Use it to sanity-check a design, **not** to copy hexes into your CSS.

| role | Standard | Dracula | Forest | Dark | Dark Blue |
|---|---|---|---|---|---|
| page bg (`--bs-body-bg`) | `#eef2f7` | `#282a33` | `#161817` | `#080e19` | `#13181b` |
| body gradient (actual paint) | `#e6ebf2→#eef2f7→#dee4ec` (`standard.css`) | from `--background` | idem | **flat `#080e19` + two fixed radial washes** (`dark.css` rich section) | from `--background` |
| `Skin.getBackgroundColor()` (inline on `<body>`) | `#f8f9fa` | `#282a33` | `#161817` | `#080e19` | `#13181b` |
| raised surface (`--current-line`) | *(undefined)* → `--bs-light` `#f4f7fb` | `#44475a` | `#2c302e` | `#101b2c` | `#262f36` |
| effective `.card` bg (winning block) | `#ffffff→#fbfcfe` `!important` (`standard.css`) | `rgba(68,71,90,.6→.4)` (`dracula.css`) | `rgba(42,46,44,.6→.4)` (`forest.css`) | **flat `#101b2c`** + 1px hairline + inset top highlight (`dark.css` rich section) | `rgba(36,45,52,.6→.4)` (`dark-blue.css`) |
| border (`--bs-border-color`) | `#c4cdd9` | `#6272a4` (`=--comment`) | `#4a6852` | `#22385a` (literal) | `#5f7188` (`=--comment`) |
| primary text (`--bs-body-color`) | `#495057` (tables `#24292f`) | `#f8f8f2` | `#e2ebe5` | `#e9eff7` | `#e2e6eb` |
| muted (`--comment` / `.text-muted`) | `#6c757d` (`base.css`) | `#6272a4` | `#4a6852` | `#8a9db4` | `#5f7188` |
| muted-on-surface (`--foreground-muted`) | n/a | `rgba(248,248,242,.65)` | `rgba(226,235,229,.72)` | `rgba(233,239,247,.72)` | `rgba(226,230,235,.72)` |
| accent (`--bs-primary` = `--purple`) | `#5B89C3` | `#5a7a9f` | `#4c9460` | `#2f8fd6` | `#4c6c94` |
| accent hover (`--pink`) | `#4A76A8` (link hover) | `#5a7a9f` | `#6aac7a` | `#6fbdf0` | `#6a88ac` |
| success (`--green`) | `#3ac47d` (`base.css`); `.btn-success` `#28a745` (`standard.css`) | **`#4a7fa8` (blue!)** | `#4c9460` | `#59c26a` | **`#4c6c94` (blue!)** |
| warning (`--orange`) | `#f7b924` (`base.css`); `.btn-warning` `#E8A658` (`standard.css`) | `#ffb86c` | `#d4a862` | `#e0a33c` | `#d4a862` |
| danger (`--red`) | `#d92550` (`base.css`); `.btn-danger` `#dc3545` (`standard.css`) | `#ff5555` | `#c86868` | `#e05a52` | `#c86868` |
| info (`--cyan`) | `#16aaff` (`base.css`) | `#5a7a9f` | `#4da898` | `#46b6d9` | `#4d82a8` |
| table row hover | `#eef3f8` (`standard.css`) | `#414863` | `#323634` | `rgba(47,143,214,.14)` wash | `#2b353d` |
| table header bg | `#f6f8fa` (`standard.css`) | `--current-line` | `--current-line` | **transparent** — an uppercase kicker + one hairline (`dark.css` rich section) | `--current-line` |
| selected row (`--bs-table-active-bg`, set inside `.table`) | `rgba(91,137,195,.16)` (`standard.css`) | `rgba(90,122,159,.38)` (`dracula.css`) | `rgba(76,148,96,.28)` (`forest.css`) | `rgba(47,143,214,.26)` (`dark.css`) | `rgba(76,108,148,.32)` (`dark-blue.css`) |

> ⚠️ **Hue does not carry state on the dark skins.** In **Dracula** `--green` is `#4a7fa8` (a blue) and
> `--cyan == --pink == --purple == #5a7a9f`, so *info*, *hover accent* and *primary* are literally the
> same colour; in **Dark Blue** `--green == --purple == #4c6c94`. A "green = OK / blue = info" design
> collapses on both. (**Dark** does not collapse — it separates primary `#2f8fd6` from success
> `#59c26a` — but you cannot rely on that, because the same component renders on the others too.) **Always pair a state colour with an icon, a word, or a shape** (a dot, a border,
> a `badge` with a label). This is the same rule doc [22](22-charts-params-and-filters.md) §6.1 states
> for charts, applied to component chrome.

Input fields on the four dark skins are heavily restyled with `!important`
(`dark-blue.css`: gradient `#181e22→#0c0f12`, `3px solid #3c516a`, `color:#e2e6eb`; **Dark** overrides
that again at the end of its own file with a flat `#0c1422` well, a **1px** `rgba(168,200,232,.52)`
edge and a 3px brand focus ring). Do not try to restyle `.form-control` yourself; use it as-is or
wrap it — whatever you write, one of the five skins already writes `!important` over it.

---

## 5 · Per-theme CSS in an `nct.html.plugin` — `css.byTheme` and the scoper

§5.1–§5.5 are written for an `nct.html.plugin` that carries a `studioModel`
(schema → [24](24-html-component-studio.md) §2); a `chart.js.plugin` gets the **same** contract through
the same scoper — §5.6. What is rendered **raw and unscoped** is markup: an inline `<style>` in an
`html` property, and a `<style>` inside a chart's `html` — §5.5.

### 5.1 Keys and emission

```jsonc
"css": {
  "byTheme": {
    "*":         "…",   // ALWAYS emitted   (HtmlStudioModel.StudioCss.ALL_THEMES = "*", HtmlStudioModel.java)
    "Standard":  "…",   // emitted ONLY when the viewer's skin is Standard
    "Dark Blue": "…"    // exact Skin.getName() — space included
  }
}
```

At render time the platform emits your per-theme CSS scoped to the component's own wrapper element,
in this order:

```css
/* 1. the "*" block, scoped */      #dokie-plug-<markupId> .your-rule { … }
/* 2. the ACTIVE skin's block, scoped, second — so it wins */
```

Nothing is emitted when the CSS is empty or the wrapper has no id.

- Exactly **two** blocks are ever emitted: `"*"` first, then the active skin. There is no cascade, no
  merge, no "all dark themes" group — the skin block simply comes later, so it wins at equal specificity.
- Keys that are neither `"*"` nor the *current* skin name are **never emitted**. A typo
  (`"DarkBlue"`, `"dark blue"`) is silently ignored — no error, no warning, and no `validate` check either:
  the literal-hex check never questions a key, and in fact only ever reads the `"*"` block (§9), so a block
  under a misspelled skin is not even scanned — it lints clean and renders for nobody.
- `scope` = `#dokie-plug-<the component's markup id>`, and the wrapper element is
  added only when the studio is active. The id changes across renders when the markupId
  changes; that is fine for CSS, which is re-emitted in the same `renderHead`.
- The CSS is emitted into the page head at **page-render** time, so the per-theme choice is frozen then.
  There is no restyle on a theme switch, because switching the theme reloads the page anyway.

### 5.2 What the scoper does to your selectors

The scoper is a brace/paren/string/comment-aware rewriter. Exact behaviour:

| you write | you get |
|---|---|
| `.kpi { … }` | `#dokie-plug-x .kpi { … }` (the default: scope + descendant) |
| `#dokie-plug-x .kpi { … }` (already scoped) | unchanged |
| `:root { --a: 1 }` | `#dokie-plug-x { --a: 1 }` |
| `body { background: … }` | `#dokie-plug-x { background: … }` |
| `body .kpi`, `html > .kpi`, `:root .kpi` | `#dokie-plug-x .kpi` etc. — the leading `:root`/`html`/`body` token is **replaced** by the scope |
| `html.dark .kpi` | `#dokie-plug-x.dark .kpi` — **concatenated onto the wrapper** |
| `.a, .b` | `#dokie-plug-x .a, #dokie-plug-x .b` (the comma split respects parens and brackets, so `:is(a,b)` and `[x=","]` survive) |
| `@media (max-width:700px) { .kpi{…} }` | prelude kept, **body recursed** and scoped |
| `@supports`, `@container`, `@layer`, `@scope` | same recursion |
| `@keyframes spin { … }` | **emitted unchanged, UNSCOPED** — the name is page-global |
| `@font-face`, `@page`, `@font-feature-values` | **unchanged, unscoped** |
| `@import`, `@charset` | passed through verbatim |
| unbalanced `{`/`}` | scoping aborts and **the RAW, unscoped CSS is returned** (fail-safe) |

Two consequences worth internalising:

- Scoping adds an **id** to every selector (specificity +100). Your rules easily beat Bootstrap and the
  theme's plain-class rules — but they still lose to the theme's `!important` blocks (§7.2).
- `@keyframes` names are **global**. Two studio components that both define `@keyframes spin` collide
  page-wide, last one loaded wins. Prefix animation and font-family names with your component prefix.

### 5.3 ⛔ An ancestor-theme selector is impossible **by construction** — this is why `byTheme` exists

> ⛔ **`html.dark .card` / `body[data-theme] .card` INSIDE `css.byTheme` CAN NEVER MATCH.**
> **Mechanism:** a leading `:root`/`html`/`body` is rewritten **onto** the scope. `html.dark .card` becomes `#dokie-plug-x.dark .card` — meaning *"the wrapper element
> itself must carry class `dark`"*. It never does: the wrapper is emitted as
> `<div id="dokie-plug-…" class="dokie-plug" …>` and never carries a theme class. Combine that with §1.3
> (there is no theme class on `<html>`/`<body>` in the first place) and the rule is doubly dead.
> **Symptom:** the block silently does nothing. Your component keeps the `"*"` styling on every skin —
> which, if the `"*"` block was written light-first, means white cards on dark pages.
> **Caught by `validate`?** No.
> **Fix:** put the variant in `css.byTheme["Dark Blue"]` etc. — or, far better, express it once in `"*"`
> with tokens (§6).

> ⛔ **A MALFORMED CSS BLOCK LEAKS GLOBALLY.**
> **Mechanism:** an unbalanced brace makes the scoper give up and return the **raw** string ("fail safe" —
> unscoped author CSS is no worse than a raw `<style>`). That raw string is then rendered into the page head.
> **Symptom:** one component's `.card{…}` or `.table{…}` suddenly restyles the entire application —
> the sidebar, the breadcrumb, other plugins. Extremely confusing, because the component itself may look fine.
> **Caught by `validate`?** **No.** The studioModel *JSON* is parsed and the
> CSS **text** is scanned for colour literals, but nothing counts braces — a block can be
> both token-perfect (zero warnings) and unbalanced (globally leaking) at the same time.
> **Fix:** never write bare element selectors (`.card`, `table`, `h1`, `button`) in authored CSS — always
> a prefixed class. Then even a leak is survivable. And count your braces: paste the block through any
> CSS formatter before shipping.

### 5.4 `:root` in a studio block — the one good use

Because `:root { … }` is rewritten to the wrapper (§5.2), a `:root` block inside `css.byTheme` is
the clean way to declare **local aliases** for the token cascade: they are defined on the wrapper and
inherited by everything inside the component, and they cannot escape. That is what §8's starter block
does. What you **cannot** do is publish a custom property to the rest of the page.

### 5.5 Which surfaces are scoped — and which are rendered raw

| surface | how it renders | scoped? |
|---|---|---|
| `nct.html.plugin` **with** `studioModel` → `css.byTheme` | emitted into the page **head** as one CSS header item per instance | **yes**, `#dokie-plug-<id>` |
| `nct.html.plugin`/`html.plugin` **without** `studioModel`, inline `<style>` in `properties.html` | the html property is written **raw into the page body** (escaping off) | **no** (and `validate` warns — but only for `nct.html.plugin`) |
| `chart.js.plugin` markup (`properties.Javascript` → the model's `html`) | rendered raw into the page body (the panel writes the `html` string with escaping off) | **no** |
| `chart.js.plugin` → the model's **`cssByTheme`** map, and the legacy single **`css`** field folded into it | ✅ emitted per theme and scoped to the chart instance — see §5.6 | **yes**, `#<chart markupId>` |
| `style="…"` attribute anywhere | inline style | n/a — and it beats every stylesheet, §7.3 |

> ⚠️ **A classic (non-studio) html plugin has no CSS slot.** If it needs more than utility classes,
> either keep it to §2 classes + Bootstrap utilities, or promote the node to a studio component
> (add a `studioModel` with just `css.byTheme` — `libs`/`docs`/`scripts` may stay empty; the studio
> activates as soon as the `studioModel` is not empty) so your CSS is scoped. **Do not** start
> sprinkling inline `<style>` blocks with bare selectors — that is exactly the "unscoped leak" failure
> mode of §5.3, just without the malformed input. `validate` warns on **any** `<style` inside
> `properties.html` of an `nct.html.plugin`; treat that warning as an error.

> ⚠️ **A portalled child escapes the scope.** Anything a library appends to `document.body` (tooltips,
> modals, date pickers, dropdown menus) renders **outside** `#dokie-plug-<id>`, so none of your scoped
> CSS applies to it. Configure such a library to render in-place, or accept the platform's default look.

---

### 5.6 The same contract on a `chart.js.plugin`

A chart has its own per-theme slot: `properties.Javascript.stringValue` → `cssByTheme` (keys `"*"` + the exact
`Skin.getName()` strings), authored on the editor's **Css** tab. It is emitted the same way — `"*"` plus the
ACTIVE skin only, each scoped to `#<chart markupId>` (`ChartJsPlugin.renderAuthorCss` → `NctThemeCss.forActiveTheme`,
the helper the HTML studio also uses). The legacy single `css` field is still honoured: `effectiveCssByTheme()`
folds it in as the `"*"` (all-themes) block **when the map has no non-blank `"*"` entry of its own**, so a chart
authored before the Css tab existed keeps working, and a `"*"` you type on the tab wins over it. Same scoper, so
everything in §5.2 (`:root` → the wrapper, `@keyframes` stays global, a malformed block falls back to RAW) applies
verbatim; the same key spelling rules as §5.1 apply, because the tab is built from `"*"` + `Skin.allNames()`.

> ⚠️ **Chart CSS is a lint blind spot.** `validate`'s colour-literal check reads a node's `studioModel` only, so
> **nothing** vets a chart's `cssByTheme`/`css` — the checklist in §10 is vacuously green for charts. Apply §3's
> token contract there by hand, and put the chart's block through the §9.2 greps yourself.

> ⛔ **A `<style>` block inside a chart's `html` is GLOBAL** — same trap as §5.5. One audited delivery had a SINGLE
> panel carry the `<style>` that fifteen sibling panels depended on; the moment you scope it, the other fifteen lose
> their styling. When you move such a block into `cssByTheme`, give it to **every** node that uses those classes.
> `validate` warns on an inline `<style>` in an `nct.html.plugin` html property but not (yet) in a chart's.

⚠️ **CSS cannot reach inside the canvas.** Axis labels, legends and the Plotly paper are painted by the charting
library, not styled by CSS. Those must be set in the chart's **js**: for Chart.js v3 `Chart.defaults.color` /
`Chart.defaults.borderColor`, for Plotly `layout.paper_bgcolor = layout.plot_bgcolor = 'rgba(0,0,0,0)'` plus
`layout.font.color`. Read the value live off the component so it follows the skin —
`getComputedStyle(this.$component()[0]).color` — rather than hard-coding one per theme. See
[22 §6](22-charts-params-and-filters.md).

---

## 6 · DECISION RULE — `"*"` + tokens, or per-theme blocks?

**Default and strongly preferred: one `"*"` block written entirely in tokens.**

Use a per-skin key **only** when the design is genuinely *different* per theme, not merely
differently-coloured. Concretely, only these justify a `byTheme` key:

- a raster **image / logo / illustration** that needs a light and a dark variant;
- a **shadow or glow** that must invert (`0 1px 2px rgba(0,0,0,.16)` reads as nothing on `#13181b`;
  a dark skin may want a lighter inner border instead);
- a **gradient or texture** whose stops cannot be derived from a token;
- a one-off **contrast rescue** for a single skin (e.g. Dracula's `--current-line` `#44475a` is much
  lighter than the other three, so a `.06` overlay disappears there).

Everything else — background, text, border, accent, state colours — is a token. Reasons:

| `"*"` + tokens | per-theme blocks |
|---|---|
| 1 block to write and maintain | 5 blocks, and 4 of them are near-copies |
| a new skin added to `Skin.java` works for free | a new skin renders with the `"*"` block only |
| impossible to get "one skin forgotten" | the classic bug: 4 keys filled, 1 forgotten |
| ~40 lines | ~200 lines, drifting apart on the first edit |

> **Rule of thumb.** If you are about to write the same block five times with five different hexes,
> you wanted a token. If you find yourself writing `css.byTheme["Standard"]` **first**, stop — you are
> designing for the minority skin.

### 6.1 Worked example — a KPI card + table, rewritten

**Before** (what shipped — `css.byTheme` = `{"*": …}` only; unusable on 4/5 skins):

```css
/* ✗ BEFORE — a real shipped css.byTheme["*"] block: 10 distinct hexes, 0 tokens */
.cmp-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:16px;margin-bottom:16px;}
.cmp-kpi{background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 1px 2px 0 rgb(0 0 0/.05);padding:16px 18px;}
.cmp-kpi-l{font-size:11px;letter-spacing:.06em;color:#6b7280;font-weight:600;}
.cmp-kpi-v{font-size:28px;font-weight:700;margin-top:6px;color:#111827;}
.cmp-warn{color:#92400e;} .cmp-bad{color:#b91c1c;} .cmp-good{color:#059669;}

.cmp-scroll{overflow-x:auto;}
.cmp-tbl{width:100%;border-collapse:collapse;font-size:13px;}
.cmp-tbl th{text-align:left;font-size:11px;letter-spacing:.05em;color:#6b7280;
  background:#f3f4f6;padding:10px 12px;border-bottom:1px solid #e5e7eb;font-weight:600;}
.cmp-tbl td{padding:12px;border-bottom:1px solid #f1f5f9;vertical-align:middle;}
.cmp-strong{font-weight:600;color:#111827;}
.cmp-muted{color:#6b7280;font-size:12px;}
.cmp-empty{color:#94a3b8;text-align:center;padding:18px;}
```

**After** (same `"*"` key, same visual intent, correct on 5/5 — zero hex literals):

```css
/* ✓ AFTER — identical layout, colour bound to tokens */
.cmp-root{
  --s-surface: var(--current-line, var(--bs-light, #f4f7fb));
  --s-text:    var(--foreground,   var(--bs-body-color, #212529));
  --s-muted:   var(--comment,      var(--bs-secondary, #6c757d));
  --s-border:  var(--bs-border-color, #dee2e6);
  --s-ok:      var(--green,  var(--bs-success, #3ac47d));
  --s-warn:    var(--orange, var(--bs-warning, #f7b924));
  --s-bad:     var(--red,    var(--bs-danger,  #d92550));
  color: var(--s-text);
}
.cmp-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; }
.cmp-kpi  { background:var(--s-surface); border:1px solid var(--s-border); border-radius:.75rem;
            padding:1rem 1.125rem; }
.cmp-kpi-l{ font-size:.6875rem; letter-spacing:.06em; font-weight:600; text-transform:uppercase;
            color:var(--s-muted); }
.cmp-kpi-v{ font-size:1.75rem; font-weight:700; margin-top:.375rem; color:var(--s-text);
            font-variant-numeric:tabular-nums; }
.cmp-good { color:var(--s-ok); }  .cmp-warn { color:var(--s-warn); }  .cmp-bad { color:var(--s-bad); }

.cmp-tbl        { width:100%; border-collapse:collapse; }
.cmp-tbl th     { font-size:.6875rem; text-transform:uppercase; letter-spacing:.04em; font-weight:600;
                  color:var(--s-muted); text-align:left; padding:.625rem .75rem;
                  border-bottom:1px solid var(--s-border);
                  background:color-mix(in srgb, var(--s-border) 22%, transparent); }
.cmp-tbl td     { padding:.625rem .75rem; color:var(--s-text);
                  border-bottom:1px solid color-mix(in srgb, var(--s-border) 55%, transparent); }
.cmp-tbl tr:hover td { background:color-mix(in srgb, var(--s-border) 18%, transparent); }
```

What changed, and why it is now correct:

- `#fff` → `var(--current-line, var(--bs-light))` — dark surface on 4 skins, `#f4f7fb` on Standard (§3.3).
- `#6b7280`/`#111827` → `--comment`/`--foreground` with `--bs-*` fallbacks — text contrast now follows
  the surface it sits on, instead of assuming white.
- `#e5e7eb`/`#f1f5f9` (the two greys used for the card border and the row hairline) → `var(--bs-border-color)`
  and a `color-mix` of it — 5/5, no fallback needed.
- `#059669`/`#92400e`/`#b91c1c` → `--green`/`--orange`/`--red` with `--bs-success/-warning/-danger`
  fallbacks. (And per §4, pair `.cmp-bad` with an icon — on Dracula and Dark Blue "green" is a blue.)
- The `#f3f4f6` table-header fill and a **new** row-hover tint are derived with `color-mix` from an
  existing token instead of a literal grey, so they are subtle on both a `#f4f7fb` and a `#262f36`
  surface. `color-mix` needs no `-rgb` companion (§3.4).
- `box-shadow` dropped: it is invisible on the four dark skins and the border already separates the tile.
  If you want depth, put it in a per-theme block — that is a *legitimate* `byTheme` use (§6).

**Cost, measured:** the "after" block is 1 752 B / 28 lines against the shipped 1 042 B / 16 lines — about
**+70 %**, and it buys 5 skins instead of 1. Compare it against the honest alternative (the same design as
five per-skin blocks, ≈5 × 1 kB): it is a third of the size and there is no fifth block to forget.

---

## 7 · Layout traps that break authored markup

### 7.1 ⛔ `h-100` is `height:100vh`, not `100%`

> ⛔ **`class="card h-100"` MAKES A CARD EXACTLY ONE VIEWPORT TALL.**
> **Mechanism:** two same-specificity `!important` rules; the later wins.
> `base.css` `.h-100{height:100% !important}` (Bootstrap sizing) is overridden by
> **`base.css` `.h-100{height:100vh !important}`** (ArchitectUI helpers). Because `.card` is a
> flex column and `.card-body` is `flex:1 1 auto`, the content pins
> to the top of a viewport-tall box.
> **Symptom:** every card on a row is identically, absurdly tall regardless of content; a "equal-height
> cards" row turns into a full-screen scroll per card.
> **Caught by `validate`?** No.
> **Fix:** use **`he-100`** (`base.css`, `height:100%`, no `!important`), `he-auto`,
> or `h-sm` (`150px`). `h-100` appears **zero times** in the `.mrjun` templates shipped with this
> library — treat it as forbidden.

### 7.2 ⛔ Each theme defines `.card` **twice**; the second one carries `!important`

> ⛔ **A SCOPED `.my-wrap .card{background:…}` LOSES TO THE THEME.**
> **Mechanism:** all five theme files declare `.card` **twice** — an early structural block and a much
> later visual one. The **second** block sets `background: linear-gradient(…) !important`, in
> `standard.css` exactly as in the four dark files. Same story for `.card-header`.
> **Symptom:** you override `.card` inside your component, the border/padding change takes, the
> **background does not**. Looks like a caching problem; it is not.
> **Caught by `validate`?** No.
> **Fix (in order of preference):** (1) don't restyle `.card` — use your own `.<pfx>-card` class, which
> is what §8 does; (2) if you must, add `!important` to the background line only; (3) never restyle
> `.card` from *unscoped* CSS — you would change every card in the app (§5.3).

### 7.3 ⛔ `style="…"` beats every stylesheet — never put a colour in one

> ⛔ **AN INLINE COLOUR CANNOT BE THEMED, ONLY PATCHED.**
> **Mechanism:** inline styles outrank author stylesheets; the only cure is a per-theme rule with
> `!important`. The platform's own tree still carries the scars: `CommentsFieldFormControlPlugin.html`
> `style="background-color: #f8f9fa"`, `LayoutManagementPanel.html` `#f8f9fa`,
> `UserActionsFieldPanel.html` `style="background: #eee"` — each forced a per-theme rescue block, e.g.
> `dark-blue.css` `.comments-control-container .reply-section{background-color:var(--background)!important;
> border:1px solid var(--comment)!important}` (that one selector prefix appears **39 times** in
> `dark-blue.css`, purely to undo inline literals).
> **Symptom:** a bright slab inside an otherwise dark screen; no CSS you write in `css.byTheme` removes
> it without `!important`.
> **Caught by `validate`?** No.
> **Fix:** `style=` is for **layout only** (`style="width:120px"`, `style="grid-column:span 2"`). Every
> colour goes in a class. Grep for it before shipping — §9.

### 7.4 ⚠️ Charts: Plotly paints white paper

`Plotly.newPlot` defaults `paper_bgcolor`/`plot_bgcolor` to **white** → a white square on the four dark
skins. Chart.js canvases are transparent and already safe. Full recipe (transparent paper + reading
`font.color` live from a themed element) is in [22](22-charts-params-and-filters.md) §6; `validate`
warns when a chart's `js` mentions `Plotly` without `paper_bgcolor` (`validate_cmds.py`) — one of
the three theme warnings in the validator (§9).

⚠️ **Two notes on 22 §6 that this doc owns.** (1) Chart *container* CSS has a real home: the chart model's
per-theme `cssByTheme` map, authored on the editor's **Css** tab, and the legacy single `css` field, which is
folded in as the `"*"` block — both are emitted scoped to the chart instance (§5.6). Do **not** put container
CSS in the chart's `html`: a `<style>` there is global. (2) Chart **series** colours are the one place literal
hexes are correct (22 §6.1 requires a semantic ramp mapped by label); they live in the model's `js`, which none
of this doc's rules or greps should be applied to — see the §9.2 note.

### 7.5 ⚠️ Contrast inside the dark skins is not uniform

The four dark skins' raised surfaces span **21 L\***. `--current-line` is `#101b2c` (Dark, CIE
**L\*9.6**), `#262f36` (Dark Blue, **18.8**), `#2c302e` (Forest, **19.4**) and `#44475a`
(Dracula, **30.6**). Dark is now the DEEPEST of the four and Dracula is more than three times its
relative luminance, so the spread a tint has to survive is wider than it was when three of them
clustered at 18–19. A tint that reads as a subtle zebra on Dark is invisible on Dracula, and one
tuned on Dracula disappears on Dark. Derive tints with `color-mix` from a
token (§6.1) rather than a fixed `rgba(255,255,255,.03)`, and if one skin genuinely needs a different
value, that is the legitimate case for a `byTheme["Dracula"]` block (§6).

---

## 8 · Starter CSS block — copy, rename the prefix, ship

A complete, token-only component kit. **Paste it into `css.byTheme["*"]`** of an `nct.html.plugin`'s
`studioModel` (see [24](24-html-component-studio.md) §2 for how the JSON is written), rename the
`cmp-` prefix to your entity (`orders-`, `intake-`, …), and add the root class to your wrapper element:

```html
<div class="cmp-root">…your markup…</div>
```

Renaming matters: the prefix `cmp-` is free across `base.css` and all five theme files (0 hits), but
two components on one page sharing a prefix will collide if either one is **unscoped** (§5.5).

**Classes this block defines** — `cmp-root`, `cmp-head`, `cmp-title`, `cmp-sub`, `cmp-actions`;
`cmp-card`, `cmp-card-h`, `cmp-card-b`, `cmp-card-f`; `cmp-kpis`, `cmp-kpi`, `cmp-kpi-l`, `cmp-kpi-v`,
`cmp-kpi-d`; `cmp-scroll`, `cmp-tbl`, `cmp-num`, `cmp-empty`; `cmp-form`, `cmp-field`, `cmp-label`,
`cmp-input`, `cmp-hint`; `cmp-btn`, `cmp-btn-primary`, `cmp-btn-ghost`, `cmp-btn-danger`, `cmp-btn-sm`;
`cmp-chip`, `cmp-chip-ok`, `cmp-chip-warn`, `cmp-chip-bad`, `cmp-chip-info`;
`cmp-good`, `cmp-warn`, `cmp-bad`, `cmp-muted`.

```css
/* ============================================================================
   <pfx> component kit — theme-safe primitives. Rename `cmp-` per component.
   Rules: colour ONLY via the --s-* aliases below; layout/typography free-form.
   Correct on Standard / Dracula / Forest / Dark / Dark Blue with ONE block.
   ============================================================================ */

/* --- 0 · resolve the token cascade once, on the component root ------------- */
/*     (in a studio css.byTheme block you may equally write `:root{…}` — the
        scoper rewrites it onto the wrapper — see §5.2)                    */
.cmp-root{
  --s-bg:        var(--background,       var(--bs-body-bg, #fff));
  --s-surface:   var(--current-line,     var(--bs-light, #f4f7fb));
  --s-text:      var(--foreground,       var(--bs-body-color, #212529));
  --s-muted:     var(--comment,          var(--bs-secondary, #6c757d));
  --s-muted-2:   var(--foreground-muted, var(--bs-secondary, #6c757d));
  --s-border:    var(--bs-border-color, #dee2e6);
  --s-accent:    var(--purple,  var(--bs-primary, #3f6ad8));
  --s-accent-2:  var(--pink,    var(--bs-link-hover-color, #4A76A8));
  --s-ok:        var(--green,   var(--bs-success, #3ac47d));
  --s-warn:      var(--orange,  var(--bs-warning, #f7b924));
  --s-bad:       var(--red,     var(--bs-danger,  #d92550));
  --s-info:      var(--cyan,    var(--bs-info,    #16aaff));
  /* derived tints — no *-rgb token needed, works on all 5 skins */
  --s-hair:      color-mix(in srgb, var(--s-border) 55%, transparent);
  --s-zebra:     color-mix(in srgb, var(--s-border) 16%, transparent);
  --s-hover:     color-mix(in srgb, var(--s-accent) 12%, transparent);
  --s-r:         .625rem;          /* radius */
  --s-gap:       1rem;
  color: var(--s-text);
  font-variant-numeric: tabular-nums;
}

/* --- 1 · screen header ----------------------------------------------------- */
.cmp-head{ display:flex; align-items:flex-start; justify-content:space-between;
           gap:var(--s-gap); flex-wrap:wrap; margin:0 0 1.125rem; }
.cmp-title{ font-size:1.375rem; font-weight:700; margin:0; color:var(--s-text); line-height:1.25; }
.cmp-sub{ font-size:.8125rem; color:var(--s-muted); margin:.25rem 0 0; }
.cmp-actions{ display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; }

/* --- 2 · card / panel (own class — never restyle .card, §7.2) -------------- */
.cmp-card{ background:var(--s-surface); border:1px solid var(--s-border);
           border-radius:var(--s-r); margin-bottom:var(--s-gap); overflow:hidden; }
.cmp-card-h{ display:flex; align-items:center; justify-content:space-between; gap:.75rem;
             padding:.875rem 1.125rem; border-bottom:1px solid var(--s-hair);
             font-size:.9375rem; font-weight:700; color:var(--s-text); }
.cmp-card-b{ padding:1.125rem; }
.cmp-card-f{ padding:.75rem 1.125rem; border-top:1px solid var(--s-hair);
             font-size:.8125rem; color:var(--s-muted); }

/* --- 3 · KPI tiles --------------------------------------------------------- */
.cmp-kpis{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
           gap:var(--s-gap); margin-bottom:var(--s-gap); }
.cmp-kpi{ background:var(--s-surface); border:1px solid var(--s-border);
          border-radius:var(--s-r); padding:1rem 1.125rem; }
.cmp-kpi-l{ font-size:.6875rem; letter-spacing:.06em; text-transform:uppercase;
            font-weight:600; color:var(--s-muted); }
.cmp-kpi-v{ font-size:1.75rem; font-weight:700; line-height:1.15; margin-top:.375rem;
            color:var(--s-text); }
.cmp-kpi-d{ font-size:.75rem; margin-top:.25rem; color:var(--s-muted); }

/* --- 4 · table ------------------------------------------------------------- */
.cmp-scroll{ overflow-x:auto; }                     /* wide tables scroll, page never does */
.cmp-tbl{ width:100%; border-collapse:collapse; font-size:.875rem; }
.cmp-tbl th{ position:sticky; top:0; z-index:1; text-align:left; white-space:nowrap;
             font-size:.6875rem; letter-spacing:.04em; text-transform:uppercase; font-weight:600;
             color:var(--s-muted); background:var(--s-zebra);
             padding:.625rem .75rem; border-bottom:1px solid var(--s-border); }
.cmp-tbl td{ padding:.625rem .75rem; color:var(--s-text); border-bottom:1px solid var(--s-hair);
             vertical-align:middle; }
.cmp-tbl tbody tr:hover td{ background:var(--s-hover); }
.cmp-num{ text-align:right; font-variant-numeric:tabular-nums; }
.cmp-empty{ padding:2.5rem 1rem; text-align:center; color:var(--s-muted); font-size:.875rem; }

/* --- 5 · form -------------------------------------------------------------- */
.cmp-form{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:.875rem; }
.cmp-field{ display:flex; flex-direction:column; gap:.3125rem; min-width:0; }
.cmp-label{ font-size:.75rem; font-weight:600; color:var(--s-muted); }
.cmp-input{ width:100%; padding:.5rem .625rem; font-size:.875rem; border-radius:.375rem;
            color:var(--s-text); background:var(--s-bg);
            border:1px solid var(--s-border); outline:none; }
.cmp-input::placeholder{ color:var(--s-muted); opacity:.8; }
.cmp-input:focus{ border-color:var(--s-accent);
                  box-shadow:0 0 0 3px color-mix(in srgb, var(--s-accent) 30%, transparent); }
.cmp-input[disabled]{ opacity:.55; cursor:not-allowed; }
.cmp-hint{ font-size:.75rem; color:var(--s-muted); }

/* --- 6 · buttons ----------------------------------------------------------- */
.cmp-btn{ display:inline-flex; align-items:center; gap:.375rem; cursor:pointer;
          padding:.5rem .9375rem; font-size:.8125rem; font-weight:600; line-height:1.2;
          border-radius:.4375rem; border:1px solid transparent;
          background:transparent; color:var(--s-text); }
.cmp-btn:focus-visible{ outline:2px solid var(--s-accent); outline-offset:2px; }
.cmp-btn[disabled]{ opacity:.55; cursor:default; }
.cmp-btn-primary{ background:var(--s-accent); border-color:var(--s-accent);
                  color:color-mix(in srgb, var(--s-accent) 12%, #fff); }
.cmp-btn-primary:hover:not([disabled]){ background:var(--s-accent-2); border-color:var(--s-accent-2); }
.cmp-btn-ghost{ background:transparent; border-color:var(--s-border); color:var(--s-text); }
.cmp-btn-ghost:hover:not([disabled]){ background:var(--s-hover); }
.cmp-btn-danger{ background:transparent; border-color:var(--s-bad); color:var(--s-bad); }
.cmp-btn-danger:hover:not([disabled]){
          background:color-mix(in srgb, var(--s-bad) 14%, transparent); }
.cmp-btn-sm{ padding:.3125rem .625rem; font-size:.75rem; }

/* --- 7 · chips / status ---------------------------------------------------- */
.cmp-chip{ display:inline-flex; align-items:center; gap:.3125rem;
           padding:.1875rem .5rem; border-radius:999px; font-size:.6875rem; font-weight:700;
           letter-spacing:.02em; text-transform:uppercase; white-space:nowrap;
           color:var(--s-text); border:1px solid var(--s-border); background:var(--s-zebra); }
.cmp-chip::before{ content:""; width:.4375rem; height:.4375rem; border-radius:50%;
                   background:currentColor; opacity:.9; }   /* shape, not only hue — §4 */
.cmp-chip-ok  { color:var(--s-ok);   border-color:color-mix(in srgb, var(--s-ok) 45%, transparent);
                background:color-mix(in srgb, var(--s-ok) 14%, transparent); }
.cmp-chip-warn{ color:var(--s-warn); border-color:color-mix(in srgb, var(--s-warn) 45%, transparent);
                background:color-mix(in srgb, var(--s-warn) 14%, transparent); }
.cmp-chip-bad { color:var(--s-bad);  border-color:color-mix(in srgb, var(--s-bad) 45%, transparent);
                background:color-mix(in srgb, var(--s-bad) 14%, transparent); }
.cmp-chip-info{ color:var(--s-info); border-color:color-mix(in srgb, var(--s-info) 45%, transparent);
                background:color-mix(in srgb, var(--s-info) 14%, transparent); }

/* --- 8 · text helpers ------------------------------------------------------ */
.cmp-good { color:var(--s-ok); }
.cmp-warn { color:var(--s-warn); }
.cmp-bad  { color:var(--s-bad); }
.cmp-muted{ color:var(--s-muted); }

/* --- 9 · responsive -------------------------------------------------------- */
@media (max-width: 700px){                 /* @media recurses and is scoped — §5.2 */
  .cmp-head{ flex-direction:column; align-items:stretch; }
  .cmp-kpis{ grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
  .cmp-card-b{ padding:.875rem; }
}
```

Notes on the block:

- **13 hexes, 12 of them third-level `var()` fallbacks** — those fire only if a stylesheet fails to load.
  The 13th is the `#fff` in `.cmp-btn-primary`'s `color-mix()`: a fixed on-accent foreground, readable on
  all five accents by construction (which is also why `validate` excludes `#fff`/`#000`, §9). The block
  produces **zero** warnings from the `css.byTheme` literal check.
- `.cmp-scroll` exists because a wide table must scroll **inside its own container**; the page body must
  never scroll horizontally.
- `.cmp-chip::before` gives every status chip a **dot** so the state is legible even where the theme's
  "green" is a blue (§4).
- `--s-hair` / `--s-zebra` / `--s-hover` are derived from tokens, so they stay subtle on a `#f4f7fb`
  surface and on a `#44475a` one.
- If you need depth (shadow) or an image swap, that — and only that — goes in a `byTheme["<Skin>"]`
  block (§6).

---

## 9 · Verification — five skins, then a grep

**First, what the offline gate does and does not do.** `mrjun.py validate` has exactly three theme
warnings — **no errors**, so a project full of them still prints `OK — no errors` and packs:

| # | check | where it looks | catches | blind to |
|---|---|---|---|---|
| 1 | colour literals in authored CSS (`_check_theme_safe_css`) | a node's **`properties.studioModel`** → `css.byTheme`, and inside it **only the `"*"` block** | a bare `#e5e7eb` / `#6b7280` on any property in the all-themes block | every per-skin block (`"Standard"`, `"Dark Blue"`, … — skipped **by design**: a literal there is the documented fix); `#fff`, `#ffffff`, `#000`, `#000000` (deliberately excluded); **any** hex within 90 characters after a `var(--` — so §3.4's `var(--bs-tertiary-bg, #eef2f8)` passes; a literal that is the light value of a custom property every per-skin block re-declares; `rgb()`/`rgba()`/`hsl()`/named colours (`white`, `whitesmoke`); **a chart's `cssByTheme`/`css`, which lives in `properties.Javascript` and is never read by this check at all** (§5.6) |
| 2 | inline `<style>` in `properties.html` | nodes whose `pluginName` is exactly `nct.html.plugin` | any `<style` in that html property | the same markup on a classic `html.plugin`; a `<style>` inside a chart's `html`; a colour in a `style=` **attribute** |
| 3 | Plotly without `paper_bgcolor` | a chart's `js` (comments stripped first) | `js` that mentions `Plotly` and never `paper_bgcolor` | everything else about a chart, **including all of its CSS** |

Everything else in this doc is invisible to it: a dead `html.dark …` selector, a misspelled `byTheme`
key, `badge-light`, a bare `badge`, `h-100`, an unbalanced brace, an inline `style="background:#fff"`,
and — the whole of §5.6 — a chart's per-theme CSS, hex literals and all.
Checks 1–3 are also **warnings**, so they cannot fail a build. §9.1 and §9.2 are the actual gate.

*(Sanity check on the failed export audited in §0: 14 × check 1 + 4 × check 2, and it still reported the
build as failing only on an unrelated CRUD error. Sanity check the other way: the §8 starter kit and the
§6.1 "after" block both produce **zero** warnings from check 1.)*

### 9.1 Look at it in all five

1. Sign in (an **anonymous** page always renders the platform default, `Dark`, §1.4 — you cannot see
   the others there).
2. The header switch moves between **Dark** and **Standard** in one click. For the other three:
   **Project Settings → Appearance → Skin** (`AppearanceSection.java`), pick a skin, save.
   Either way the page fully reloads (`refreshPage()`).
   ⚠️ **The picker may not offer all five.** Choices come from the appearance section's `resolveThemeChoices()`: if the
   organization stores an explicit available-themes list, only that subset is shown (plus whatever the user
   currently has). `Skin.byName()` still resolves any stored value, and `css.byTheme` still lists all five
   (`HtmlStudioPanel.java`) — so a skin you cannot select is still a skin someone can be on. If the
   list is restricted, widen it in the Organizations admin for the duration of the review.
3. Order to test — **not** alphabetical:
   1. **Standard** — the only light skin, and the one where every dark-only token disappears. Catches
      "flat/borderless" (a bare `var(--current-line)`, §3.4) instantly.
   2. **Dark** — the platform default and the fallback for everyone who never touched the setting, and
      the deepest ground of the five (`--current-line` L\*9.6). This is what a demo audience sees.
   3. **Dracula** — the other end: its raised surface (`#44475a`, L\*30.6) is three times Dark's relative
      luminance (§7.5); catches tints that were tuned too subtle at one end or too strong at the other.
   4. **Dark Blue** and **Forest** — these two cluster at L\* 18.8–19.4 between the extremes, so they
      mostly confirm each other; scan them for text that quietly relied on a light background.
4. On each skin check, in this order: card/tile **background vs page**, **text contrast** on that
   background, **borders visible at all**, **table header + hover**, **input fields**, **buttons**,
   **status chips**, and any **embedded chart** (white paper? → [22](22-charts-params-and-filters.md) §6).
5. If the component is public, also open it **signed out** and confirm it looks right on Dark.

### 9.2 Grep the bundle before you pack

Run against the **unpacked** export dir. `validate` covers at most checks 1–3 above, and only as warnings.
⚠️ `branches.json` is one giant minified line (`wc -l` = 0), so **never use `grep -c`** (it counts lines,
and the answer is always `1`). Always `grep -o … | wc -l`.

```bash
BUNDLE=./app

# 1) Every colour literal, ranked. NOTE: this greps the whole file, so chart series
#    palettes in properties.Javascript (legitimate — doc 22 §6.1) show up too: the stock
#    initial_erp template already returns 73 x 'color: #0069B3' with zero authored CSS.
#    Judge only the literals the per-node audit below attributes to a css/html slot.
grep -oE 'background:[^;"]*#[0-9a-fA-F]{3,8}|color:[^;"]*#[0-9a-fA-F]{3,8}' "$BUNDLE/branches.json" \
  | sort | uniq -c | sort -rn | head -30

# 2) The three headline offenders, counted properly.
printf 'white bg   : %s\n' "$(grep -oE 'background(-color)?: *#(fff|ffffff|FFF|FFFFFF)\b' "$BUNDLE/branches.json" | wc -l)"
printf 'near-black : %s\n' "$(grep -oE 'color: *#(000|000000|111827|1f2937|0f172a)\b'      "$BUNDLE/branches.json" | wc -l)"
printf 'badge-light: %s\n' "$(grep -o  'badge-light'                                       "$BUNDLE/branches.json" | wc -l)"

# 3) Inline style= carrying a colour (§7.3), and the h-100 trap (§7.1).
#    The `.{0,3}` absorbs the JSON escaping (style=\" …).
grep -oE 'style=.{0,3}[^"\\]{0,120}#[0-9a-fA-F]{3,8}' "$BUNDLE/branches.json" | head -20
grep -oE 'class=.{0,3}[^"\\]{0,120}\bh-100\b'         "$BUNDLE/branches.json" | head -20

# 4) Ancestor-theme selectors / media queries that can never work (§1.3, §5.3).
grep -ioE '(html|body)[.[][a-z_-]*(dark|light|theme)[a-z_-]*|prefers-color-scheme|data-theme' \
  "$BUNDLE/branches.json" | sort | uniq -c
```

Greps **2, 3 and 4 must come back `0`/empty** — verified on the stock `initial_erp` template shipped with
this library: `0 / 1 / 0`, then nothing, then nothing (the stray near-black is a chart label). Grep 1 is the
ranked overview; subtract the chart rows and it must be empty too. On the failed export audited in §0 the
same greps return a long ranked list of grey/white literals and a high white-background count. Two of four
clean is not a pass.

Then the per-node audit — which node, which plugin, how many literals, and which `byTheme` keys:

```bash
python3 - "${BUNDLE:-./app}" <<'PY'      # BUNDLE carries over from the block above
import json, re, sys
b = json.load(open(sys.argv[1] + '/branches.json'))
rows = []
def walk(n):
    p    = n.get('properties') or {}
    html = (p.get('html') or {}).get('stringValue') or ''
    css, keys = '', []
    sm = (p.get('studioModel') or {}).get('stringValue')
    if sm:                                     # nct.html.plugin -> studioModel.css.byTheme
        try:
            bt = (json.loads(sm).get('css') or {}).get('byTheme', {}) or {}
        except Exception:
            bt, keys = {}, keys + ['<malformed studioModel>']
        keys += list(bt.keys())
        css  += '\n'.join(v or '' for v in bt.values())
    jsm = (p.get('Javascript') or {}).get('stringValue')
    if jsm:                                    # chart.js.plugin -> cssByTheme (+ legacy css, + its html)
        try:
            cm = json.loads(jsm)
        except Exception:
            cm, keys = {}, keys + ['<malformed chart model>']
        bt = dict(cm.get('cssByTheme') or {})
        if (cm.get('css') or '').strip() and not (bt.get('*') or '').strip():
            bt['*'] = cm['css']                # the legacy field renders AS the "*" block (§5.6)
        keys += list(bt.keys())
        css  += '\n'.join(v or '' for v in bt.values())
        html += cm.get('html') or ''           # NOT cm['js'] — series palettes are legitimately literal
    hexes = re.findall(r'#[0-9a-fA-F]{3,8}\b', css + html)
    if hexes or keys:
        rows.append((len(hexes), str(n.get('name')), str(n.get('pluginName')), keys))
    for c in (n.get('children') or []):
        walk(c)
for br in b:
    walk(br['rootContent'])
rows.sort(key=lambda r: (-r[0], r[1]))
print(f"{'hex':>4}  {'node':38}  {'plugin':22}  byTheme keys")
for h, name, plugin, keys in rows[:40]:
    print(f"{h:>4}  {name[:38]:38}  {plugin[:22]:22}  {keys}")
print(f"\n{len(rows)} authored-CSS/markup nodes; "
      f"{sum(1 for r in rows if r[0] > 0)} still carry hex literals")
PY
```

**How to read it.** A node with `byTheme` keys `['*']` **and** a high hex count is the §0 failure mode
verbatim, and a project that has one usually has one per authored component. Target state: hex count 0,
keys `['*']` (plus a named skin only where §6 justifies it).

A `chart.js.plugin` row with **no** `byTheme` keys and a non-zero hex count means the colour is sitting in
the chart's `html` instead of its per-theme CSS — usually a global `<style>` block (§5.6). Both reference
exports shipped with this library are in exactly that state: every hex the script reports on
`initialtemplates/empty` and the withdrawn ERP demo comes from chart html, topped by a `#0069B3` brand fill
inside a `<style>` that leaks page-wide. Treat those rows as work items on a chart you own, and remember
that this is the one audit `validate` cannot do for you (§9 table, row 1).

---

## 10 · Done when

**Done when:** the component has been *seen* on all five skins by a human or a screenshot, and the
bundle grep in §9.2 reports **0 hex literals** in `css.byTheme` and **0 colours** in `style=`.
Offline gates cannot certify this: `mrjun.py validate` emits only the three **warnings** in §9 — it never
fails a build on colour, it reads only a studio node's `css.byTheme["*"]`, it excludes `#fff`/`#000` and
every hex inside a `var()` fallback, and it never looks at `style=`, at a chart's CSS, at selectors, or at
braces. A green validate proves nothing about theming.

- [ ] `mrjun.py validate` shows **zero** `css.byTheme` colour-literal warnings and **zero** inline-`<style>`
      warnings (§9) — necessary, nowhere near sufficient.
- [ ] No colour literal in `css.byTheme["*"]`, in any inline `<style>`, or in any `style=` attribute
      (§9.2 greps return 0).
- [ ] Every colour is `var(<dark-token>, var(--bs-*))` — two levels, dark token first (§3.2).
- [ ] No `--bs-tertiary-bg`, `--bs-secondary-bg` or `*-rgb` token used as the leading value (§3.4).
- [ ] Surfaces/tables/buttons/badges/alerts/inputs use the platform classes wherever possible (§2);
      `badge-light` and bare `badge` are absent (§2 ⛔).
- [ ] No `h-100` anywhere; full-height uses `he-100` (§7.1).
- [ ] Component-owned classes are prefixed (`<pfx>-…`); no bare `.card`, `.table`, `h1`, `button`
      selectors in authored CSS (§5.3, §7.2).
- [ ] `css.byTheme` keys are exactly `"*"` and, if any, one of `Standard` / `Dracula` / `Forest` /
      `Dark` / `Dark Blue` — spelled character-for-character (§5.1).
- [ ] A per-skin block exists **only** for a genuinely different design (image / shadow / gradient /
      one-skin contrast rescue), never as a colour copy of `"*"` (§6).
- [ ] Braces balanced — pasted through a CSS formatter (a malformed block leaks globally, §5.3 ⛔).
- [ ] `@keyframes` / `@font-face` / custom `font-family` names are prefixed (they are page-global, §5.2).
- [ ] Wide content scrolls in its own `overflow-x:auto` container, not the page.
- [ ] Status is carried by an icon/dot/word, not by hue alone (§4).
- [ ] Every `chart.js.plugin` you authored keeps its container CSS in the **Css** tab (`cssByTheme`), not in a
      `<style>` inside the chart's html, and that CSS obeys §3 — **nothing offline checks it** (§5.6, §9).
- [ ] Any embedded chart is transparent-paper ([22](22-charts-params-and-filters.md) §6).
- [ ] If the page is public, it was checked **signed out** (renders Dark, §1.4).

**See also:** [24](24-html-component-studio.md) (studioModel schema, the `ctx` runtime API, vendoring
libs) · [22](22-charts-params-and-filters.md) (the chart editor's tabs, Plotly transparency, semantic
chart palettes) · [14](14-plugin-catalog-all.md) §1.1 (how `nct.html.plugin` html + `<plugin>` tags render)
· [01](01-content-model-and-pages.md) (content properties, Bootstrap grid inside `html`, the
identifier↔`<plugin id>` contract) · [04](04-crud-table-plugin.md) (use the real table plugin instead
of hand-styling one) · [19](19-build-decision-procedure.md) (when a bespoke component is the right
answer at all) · [`tools/README.md`](tools/README.md) (`node set-studio`, `show node`, `validate`).
