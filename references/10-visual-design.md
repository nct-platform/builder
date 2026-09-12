# 10 · Visual design — composition, theme survival, and the tells of a generated screen

> **What this is.** How four delivered systems actually *looked*, measured rather than remembered:
> every `style=` attribute, every framework class, all 540 KB of authored CSS, all 130 chart
> containers. Every number here was re-derived from the exports themselves, not recalled.
> Read it beside [24a · theming](../24a-theming-and-dark-mode.md) (the mechanism) and
> [09 · studio components](09-studio-components.md) (the machinery of a hand-built console). This
> document is the *design* layer: what to compose, what to paint, what to never paint, and the four
> habits that make a screen read as generated.
> Sources are **A** (433 pages, 22 hand-built consoles, 540 KB of authored CSS), **B** (129 pages,
> 31 charts, 3 locales), **C** (128 pages, 87 charts), **D** (67 pages, 12 charts). Every skeleton
> below is trimmed from code that shipped; only the nouns and the class prefixes are renamed.
>
> **How the counts were taken**, because two honest numbers differ. A *plugin census* counts every
> node in the content tree (the shell repeats on every page, so a 433-page project has 433 header
> nodes). A *markup count* counts each distinct content node once, by `identifier`. Plugin censuses
> and the composition ratio below are raw; class, CSS and chart counts are distinct nodes. Where a
> figure could be read either way it says which — e.g. 185 chart plugin nodes, 168 of them distinct.

---

## 0 · The headline, and the decision that precedes every other one

**Three of the four deliveries shipped zero authored CSS.** Not "a little" — *zero*: `css.byTheme` is
empty on all 466 studio-model nodes in **B**, all 44 in **D**, all 15 in **C**. They are not ugly.
They are dense, branded, finished-looking consoles assembled entirely from the framework's card
markup, the Bootstrap grid, empty `nct.parsis.plugin` slots, and `nct.label.plugin` strings.

The fourth — **A** — hand-built **22 consoles with 540 KB of authored CSS** (474 KB of it the
shared `"*"` block, 66 KB the four per-skin blocks), and it is the one that then had to solve every
theming, density and state problem from scratch.

So the first visual decision is not *"what should this look like"*. It is **which of the two families
this screen belongs to**, and the evidence says the answer is almost always the cheap one:

| | **Family A — zero-CSS composition** | **Family B — the studio screen kit** |
|---|---|---|
| seen in | 4 of 4 deliveries (the entirety of three) | 1 of 4 |
| authored CSS | 0 bytes | 18–38 KB per screen |
| what renders the content | `crud.table.plugin`, `chart.js.plugin`, `dynaform.*`, `nct.label.plugin` | your own markup, fed by one EXECUTION rule |
| theme risk | none — you paint nothing | the whole of 24a, on you |
| localization | free (every string is a label plugin) | your problem ([09 §8.4](09-studio-components.md)) |
| when it is right | list, form, chart grid, filter+table, dashboard of panels | a workspace fusing 4+ entities with bespoke interaction on one screen |

⛔ **Choosing Family B for a list-plus-form screen is the single most expensive mistake in this
document.** It is not a styling decision — it re-parents paging, filtering, validation, localization
and role gating onto you. [09 §1](09-studio-components.md) lists the five conditions that justify it;
if none holds, §2 below is the whole design language you need.

§1–2 are Family A. §3 onward is what Family B costs and what it buys.

---

## 1 · The frame you are designing inside

### 1.1 The five-node stack

Every page in all four deliveries is the same stack. It is generated, and **three of the four carry
it byte-identically** (2 756 bytes; the fourth differs by two bytes in a logo URL):

```
siteMapPage
└── parsis.plugin
    └── Layout                     nct.html.plugin     ← the application shell, 2 756 B, DO NOT EDIT
        ├── header                 site.header.plugin
        ├── logo-plugin            nct.image.plugin
        ├── breadcrumb             site.breadcrumb.plugin
        ├── left-nav               site.kicker.plugin
        ├── parsis                 nct.parsis.plugin   ← YOUR SCREEN GOES HERE
        ├── footer                 site.footer.plugin
        └── right-kicker           site.right.kicker.plugin
```

```html
<div class="app-container app-theme-white body-tabs-shadow fixed-header fixed-sidebar">
  <div class="app-header header-shadow">…logo, hamburgers, <plugin id="header" name="site.header.plugin">…</div>
  <div class="app-main">
    <plugin id="left-nav" name="site.kicker.plugin"></plugin>
    <div class="app-main__outer"><div class="app-main__inner">
        <plugin id="breadcrumb" name="site.breadcrumb.plugin"></plugin>
        <plugin id="parsis"     name="nct.parsis.plugin"></plugin>   <!-- ← you -->
    </div><plugin id="footer" name="site.footer.plugin"></plugin></div>
  </div>
</div>
```

Four consequences shape every decision downstream:

1. **You never own the page background.** You are inside `.app-main__inner`. A component that paints a
   full-bleed background is fighting the skin, not decorating it.
2. **The breadcrumb bar above you is where page-level actions belong** — every stock plugin already
   puts Create/Import there. §6.3.
3. **Your screen is one slot.** Composition is done by nesting `nct.parsis.plugin` slots inside your
   own markup, never by stacking sibling plugins in the page's parsis.
4. `app-theme-white` on the container is a **legacy dead class**, not a theme hook
   ([24a §1.3](../24a-theming-and-dark-mode.md)). Ignore it; it is present on all five skins.

### 1.2 The composition ratio — the tell that a screen was composed, not typed

Across all four deliveries the three composition plugins appear in near **1 : 1 : 1** proportion —
`nct.html.plugin` (structure) : `nct.label.plugin` (every visible string) : `nct.parsis.plugin`
(every content hole):

| | html | label | parsis slot |
|---|---|---|---|
| A | 1 304 | 1 130 | 957 |
| B | 962 | 851 | 603 |
| C | 574 | 569 | 568 |
| D | 207 | 179 | 195 |

That ratio *is* the convention: **no visible string is ever typed into markup, and no content is ever
placed directly — both go through a plugin.** The strings then localize for free ([07](07-localization.md));
the content can be swapped without touching layout.

> **Use it as a review metric.** Open any authored html node and count. A structure node with ten
> hard-typed captions and one slot is not a layout — it is a screen that will need a code edit for
> every wording change and will never translate.

---

## 2 · Family A — the vocabulary of a console with zero authored CSS

Three deliveries used this for everything, and the fourth used it for its 400+ non-console pages.
It is roughly fifteen class names.

### 2.1 The panel

```html
<div class="main-card mb-3 card">
  <div class="card-header">
    <i class="header-icon lnr-layers icon-gradient bg-plum-plate"></i>
    <plugin id="<pfx>-row-items-hdr" name="nct.label.plugin"></plugin>
  </div>
  <div class="card-body">…</div>
</div>
```

- `main-card mb-3 card` is *the* panel, everywhere. `main-card` is untouched by all five skins and
  simply inherits `.card`; `mb-3` is the vertical rhythm. Counted 48 times across all four
  deliveries (33 + 9 + 5 + 1) and never once with a different class list.
- `card-header` always carries the icon chip **and a label plugin**, never a typed string.
- ⚠️ **`card-title` appears exactly once in all four deliveries.** The house pattern is `card-header`,
  not `card-body > card-title`. Pick `card-header` and you match the platform's own screens.

### 2.2 One gradient, forever

`icon-gradient bg-plum-plate` — **39 of 39 occurrences across all four deliveries use the same
gradient class.** The framework ships a dozen (`bg-plum-plate`, `bg-happy-green`, `bg-arielle-smile`,
…) and the projects that look finished picked **one and never varied it**.

⛔ **Varying the gradient per section is the fastest way to make a console read as generated.** It
turns section headers into decoration instead of a system. One gradient per *tenant*, chosen once.

The icon inside it is an icon-font glyph chosen for the *subject*, from a small reused set:
`lnr-layers` (a collection or stock of things), `lnr-sync` (a flow or transfer), `lnr-chart-bars`
(a trend), `lnr-clock` (a deadline or latency), `lnr-alarm` (exceptions), `lnr-users` (people),
`lnr-diamond` (the headline KPI band). Small set, semantically assigned, reused across screens.

### 2.3 The grid

```html
<div class="row g-4">
  <div class="col-12 col-lg-8"><plugin id="<pfx>-cell-1" name="nct.parsis.plugin"></plugin></div>
  <div class="col-12 col-lg-4"><plugin id="<pfx>-cell-2" name="nct.parsis.plugin"></plugin></div>
</div>
```

- **Gutters:** `g-4`, or `gy-2` / `gy-3` for a vertical-only rhythm. Never a hand-written margin.
- **Breakpoint pairs actually used:** `col-6 col-lg-3` (four across → two on a tablet),
  `col-12 col-md-4` (thirds), `col-12 col-lg-8` + `col-12 col-lg-4` (the 2:1 split),
  `col-md-6 col-xl-3` (a KPI band that survives a laptop). Everything starts at `col-12` or `col-6`.
- **`h-100` appears ZERO times in all four deliveries. `he-100` appears 13 times.** This is the
  [24a §7.1](../24a-theming-and-dark-mode.md) trap and the deliveries respect it perfectly: quote them
  as the proof that **`he-100` is the house answer for equal-height cards**.

### 2.4 Density is done with padding utilities only

```html
<div class="main-card card he-100">
  <div class="card-body py-2 px-3">          <!-- compact tile -->
```

13 of one delivery's 22 `card-body`s carry `py-2 px-3`; the other 9 are default. That is the entire
density system: **default padding for content panels, `py-2 px-3` for tiles.** No custom `padding` is
ever authored in Family A — and an authored `padding` in an inline style is the first sign a screen
has started drifting out of the family.

### 2.5 The KPI tile with zero authored bytes

```html
<div class="col-6 col-lg-3">
 <div class="main-card card he-100"><div class="card-body py-2 px-3">
   <div class="small text-muted"><plugin id="<pfx>-kpi1-t" name="nct.label.plugin"></plugin></div>
   <plugin id="<pfx>-kpi1" name="nct.parsis.plugin"></plugin>       <!-- the number: a chart or a label -->
   <div class="small text-muted"><plugin id="<pfx>-kpi1-s" name="nct.label.plugin"></plugin></div>
 </div></div>
</div>
```

Caption above, value in the middle, sub-caption below; both captions `small text-muted`, which every
skin restyles correctly. The value slot is usually a single-number chart in a 92 px box (§2.7). A
complete, theme-perfect KPI tile, localized, with **zero authored bytes**.

### 2.6 The only legitimate inline style

Across all four deliveries the `style=` attributes carry, in order of frequency: `position`, `height`,
`min-height`, `padding-top`, `margin-top`, `width`, `font-size`, `letter-spacing`, `overflow`,
`display`, `flex-grow`.

**Colour-bearing `style=` declarations in authored markup: 0, in all four deliveries.** ([24a §7.3](../24a-theming-and-dark-mode.md)
says "`style=` is for layout only" — four for four. The handful a naive grep finds are
`color: var(--bs-primary, #0069B3)` inside stock template pages: residue, not authorship, and note
that even the residue is tokenised.)

Two inline styles worth copying:

```html
<!-- reserve the title row's height so charts in sibling columns stay aligned
     even when one title wraps to two lines -->
<div class="d-flex justify-content-between align-items-center mb-2" style="min-height:1.6rem;">
  <span class="fw-semibold" style="font-size:.95rem;"><plugin id="hdr_…" name="nct.label.plugin"></plugin></span>
</div>
<plugin id="…" name="chart.js.plugin"></plugin>

<!-- an uppercase kicker over a KPI: spaced, but not painted -->
<div class="text-center small text-muted text-uppercase" style="letter-spacing:.04em;">
  <plugin id="…" name="nct.label.plugin"></plugin>
</div>
```

### 2.7 Chart containers — the measured scale

Container heights, counted over the 130 chart containers that declare one:

| role | height | count |
|---|---|---|
| KPI number / sparkline | `92px`, `118px`, `150px` | 49 |
| standard panel chart | `280–340px` (`340px` alone = 31) | 60 |
| wide or tall feature chart | `360–440px` | 20 |

Always `position:relative` **plus** a fixed pixel height on the container, and
`maintainAspectRatio:false` on the chart config — present on **82 of the 91** Chart.js instances:
18/18, 55/55 and 8/8 in three deliveries, and **1 of 10 in the fourth**, which is the one that
hand-built its charts inside studio components and lost the convention on the way.

⛔ **A canvas missing either one collapses to 0 px and renders a blank panel that looks exactly like a
data failure.** This is the most common "the chart is broken" report that is not a data problem.

Where a chart carries its own title inside the container, the canvas wrapper reserves the remainder:

```html
<div class="<pfx>-plot" style="position:relative;height:320px;">
  <h6>Decision latency — against the 24 h rule</h6>
  <div style="position:relative;height:calc(100% - 1.9rem);"><canvas></canvas></div>
</div>
```

### 2.8 The generated form-field slot — do not hand-write it

The `mb-3` count (1 075 / 850 / 482 / 180) is dominated by one generated shape, identical in all four:

```html
<div class="mb-3">
  <div class="d-flex align-items-center justify-content-between">
    <span class="d-inline-flex align-items-center">
      <plugin id="lbl_gen_slot_…" name="nct.label.plugin"></plugin>
      <span class="red ms-1">*</span>                     <!-- required marker -->
    </span>
  </div>
  <plugin id="fld_gen_slot_…" name="dynaform.form.text.field.plugin"></plugin>
</div>
```

`mb-3` is the form rhythm; the label is a plugin; the required star is `<span class="red ms-1">*</span>`
(a platform class); and the label row is a flex container so a per-field hint or action can be dropped
on the right without reflowing anything.

### 2.9 Slot composition beats sibling stacking

Content-slot occupancy, counted per `nct.parsis.plugin`:

| combination inside one slot | A | B | C | D |
|---|---|---|---|---|
| `nct.html.plugin` alone (structure that nests further slots) | 434 | 434 | 408 | 110 |
| `crud.table.plugin` + `dynaform.filter.form.plugin` | **0** | 31 | 33 | 12 |
| `crud.table.plugin` alone | **129** | 0 | 0 | 0 |
| `global.replacement.plugin` + `nct.html.plugin` (a chart filter bar) | 0 | 4 | 8 | 0 |
| `dynaform.form.groups.landingplugin` | 109 | 28 | 38 | 17 |

**A contradiction to decide consciously.** Three deliveries put a `dynaform.filter.form.plugin`
directly above every `crud.table.plugin`; the fourth never did — 129 bare tables. **Jump the
filter-form way.** A table with no filter bar forces the user into column-header filtering, which is
discoverable only by someone who already knows it is there. Skip it only when the list is provably
short and will stay short.

---

## 3 · Family B — the studio screen kit

One delivery, 22 consoles. Everything from here is what it costs and what it bought.

### 3.1 The screen skeleton, 22 for 22

```html
<div class="ui">                                     <!-- root class: 20/22 the kit root, 2 legacy variants -->
  <div class="ui-head">                              <!-- 22/22 -->
    <h1 class="ui-title">…</h1>
    <div class="ui-actions"><span class="ui-pill …">…</span><button class="ui-btn …">…</button></div>
  </div>
  <div class="ui-kpis">…</div>                       <!-- 16/22, KPI tiles -->
  <div class="<pfx>-filters">…</div>                 <!-- 15/22, search + selects + chips -->
  <div class="ui-card">                              <!-- 22/22 -->
    <div class="ui-card-h">…</div>
    <div class="<pfx>-bulk" hidden>…</div>           <!-- bulk bar, hidden until a row is ticked -->
    <div class="ui-tablewrap"><table class="ui-table">…</table></div>   <!-- 20/22 -->
  </div>
  <div class="ui-cols">                              <!-- 17/22, the two-panel split -->
    <div class="ui-card">…edit form…</div>
    <div class="ui-card">…action form…</div>
  </div>
</div>
```

13 of 22 follow `head → kpis → card(table) → cols` exactly; the rest drop a section. Presence counts:
`ui-head` 22, `ui-card` 22, message strip 22, the `hidden` attribute 22, `ui-tablewrap` 20,
`ui-empty` 20, `ui-btn-primary` 19, `ui-cols` 17, `ui-kpis` 16, `ui-chip` 15, `aria-pressed` 15.

The two-column split exists because of a stated design obligation: **"a form opens beside the record
it changes, never on top of it."** No modals for editing — the list is on top, the editor is beside
it, and the operator can see both.

### 3.2 The measured design scale

Extracted from all 22 stylesheets. This is a real, transferable scale, and it is in **px, not rem** —
deliberately, because the component is a document inside application chrome whose root font size it
does not control.

**Type** (weights are only 600 and 700; 400 appears 9 times, purely to de-emphasise a span inside a
bold line):

| role | size | other |
|---|---|---|
| KPI value | 28–31 px | 700, `font-variant-numeric: tabular-nums`, `line-height:1.15–1.25` |
| page title `h1` | 22–23 px | 700, `letter-spacing:-.2px` on the tightest |
| card header | 15–16.5 px | 700 |
| table cell / body | 13–13.5 px | 400–500 |
| secondary / note | 12 px | muted token |
| label, caption, `th`, pill | 11–11.5 px | 600, `text-transform:uppercase`, `letter-spacing:.05–.06em` |
| micro chip / source tag | 10 px | 600 |

**Radius — three tiers only, pill / panel / control:** `999px` pills and bars (144 uses), `12px` cards
and KPI tiles (71), `10px` banners and bulk bars (49), `8px` buttons and inputs (108), `6px` small
tags (19), `4px` icon buttons (45), `50%` avatars (54).

**Gap and padding, on a 4 px grid:** gaps `8 / 10 / 12 / 16`; card `18px 20px`; KPI `16px 18px`;
`th` `10px 12px`; `td` `12px`; input `9px 11px`; button `9px 16px`, small `5px 12px`; pill `3px 10px`;
chip `7px 14px`.

**Alpha — four values, and nothing else:** `.12`–`.16` for a status fill, `.35` for its border,
`.08`–`.10` for a row state, `.22`–`.28` for a neutral track.

**Motion:** seven `transition` declarations in 540 KB of CSS, all `.12s`; three
`@media (prefers-reduced-motion: reduce)` blocks that cancel the transform. Motion is the rarest
thing in the whole stylesheet — roughly one declaration per 77 KB.

**Responsiveness: exactly ONE breakpoint**, present in 21 of the 22 files (the 22nd has no
multi-column split to collapse), doing exactly one thing:

```css
@media (max-width:900px){ .ui-cols,.ui-cols-wide{grid-template-columns:1fr;} }
```

Everything else is intrinsically responsive: `grid-template-columns:repeat(auto-fit,minmax(190px,1fr))`.

> **That is the density lesson in one line: one breakpoint for the deliberate multi-column split,
> `auto-fit`/`minmax` for everything else.** A stylesheet with four breakpoints has usually
> re-implemented `auto-fit` by hand.

### 3.3 The component vocabulary — and the prefix rule that governs it

120 shared selectors form the kit every screen carries:

| group | classes |
|---|---|
| shell | `ui` `ui-head` `ui-title` `ui-actions` |
| panel | `ui-card` `ui-card-h` `ui-cols` `ui-cols-wide` |
| KPI | `ui-kpis` `ui-kpi` `ui-kpi-l` `ui-kpi-v` |
| table | `ui-tablewrap` `ui-table` `ui-r` `ui-strong` `ui-mut` `ui-empty` `ui-rowbad` |
| status | `ui-pill` + `ui-p-{ok,warn,bad,info,neutral,grey}`, `ui-age-0…4` (escalating bands) |
| messages | `ui-banner{,-bad,-warn,-info}` `ui-alert{,-crit,-warn,-info}` `ui-msg` `.ui-msg.ok/.err/.show` |
| controls | `ui-btn` `ui-btn-primary` `ui-btn-ghost` `ui-btn-sm` `ui-full` `ui-chip` `ui-link` `ui-lab` `ui-input` `ui-input-sm` `ui-row2` |
| micro | `ui-av` (avatar) `ui-bar`/`ui-seg` (progress, stacked proportion) `ui-kv` (key/value row) `ui-listrow` `ui-note` `ui-src` `ui-rtag` |

Per-screen prefixes add only what is unique to one screen (`doc-`, `dsh-`, `tsk-`, `whs-`, …).

The kit's own header comment states the rule better than any doc can:

> *"each studio component carries its own stylesheet, and a class defined in one component does NOT
> exist in another. Writing a kit class into a second screen therefore rendered unstyled controls even
> though the markup and the data were correct. Everything used by more than one screen lives here; a
> module's own stylesheet keeps only what is unique to it."*

> ⛔ **ONE kit prefix for the whole PROJECT, plus one short prefix per screen.**
> [24d §4](../24d-html-component-structure.md) and [24a §8](../24a-theming-and-dark-mode.md) both say
> "one prefix per *component*"; followed literally, that is exactly what produced 22 divergent copies
> of one design system. §9.1 has the fix and its price.

---

## 4 · Theme survival — what the deliveries confirm, and four things they add

[24a](../24a-theming-and-dark-mode.md) is right about everything it covers. The deliveries **confirm**
most of it empirically and **add four techniques it does not have**.

### 4.1 Confirmed, with counts

| 24a rule | evidence across the four deliveries |
|---|---|
| §7.3 no colour in `style=` | **0** colour-bearing inline declarations in authored markup, 4/4 |
| §7.1 `h-100` is forbidden | `h-100`: **0** occurrences. `he-100`: 13 |
| §2 `badge-light` / a bare `badge` for status | **0** occurrences of either; status is always a project pill class or a platform plugin |
| §5.5 no inline `<style>` in an html property | **0** occurrences, 4/4 |
| §7.4 a transparent chart paper | the paper-background key is set on **all 54** charts of the library that needs it |
| §7.4 chart text follows the skin | `getComputedStyle` on **all 168** distinct chart nodes (38/38, 31/31, 87/87, 12/12); the Chart.js default-colour assignment pairs one-for-one in **all four** — 10/10, 18/18, 55/55, 8/8 = **91/91** |
| §5.1 exact skin-key spelling | 22 studio + 31 chart components carry all five keys, **0 typos** |
| §5.2 `@keyframes` names are page-global → prefix them | one `@keyframes` in 540 KB, and it is prefixed |

### 4.2 Addition 1 — the two-tier token block

Chrome binds to platform tokens; **status does not.** The full block, the accent-inversion rule and
the reason the platform's semantic tokens collapse on two dark skins are in
[09 §11](09-studio-components.md) — that is the canonical copy, do not duplicate it.

Two consequences that belong here, in the design layer:

- **The primary button inverts.** On light skins it is a dark fill with a white label; on dark skins a
  **light fill with a very dark label**. White text on an accent bright enough to read on a near-black
  page cannot reach 4.5:1. **If your primary button looks identical on both, one of the two is failing
  contrast.**
- **Cost, measured:** **755 bytes per dark key, byte-identical across all four keys in 22 of 22
  components** — about 150 bytes of declarations, the rest a comment recording the contrast ratios
  that were measured. 3.0 KB per component against a 22 KB stylesheet; the declarations alone are
  well under 1 %. There is no version of this that is expensive.

### 4.3 Addition 2 — the neutral-grey tint, arrived at independently by 4 of 4

```css
background: rgba(127,127,127,.16);   /* a pill on an unknown surface */
background: rgba(127,127,127,.22);   /* a progress track             */
```
```js
var GRID = 'rgba(128,128,128,.18)';                 // chart grid lines
Chart.defaults.borderColor = 'rgba(128,128,128,.25)';
```

Counted: 34 in **A**'s CSS, 18 in **B**'s charts, 55 in **C**'s, 8 in **D**'s. **Every delivery
arrived at it separately.**

Why it works: mid-grey at low alpha *lightens* a dark surface and *darkens* a light one by roughly the
same perceptual amount, so one literal is correct on all five skins with no token, no fallback and no
`color-mix`. It is the cheapest theme-safe fill in the system.

24a §6.1/§8 recommends `color-mix(in srgb, var(--s-border) 16%, transparent)` for the same job. Both
are right, and the split the four deliveries converged on is the rule to adopt:
**`color-mix` in CSS, `rgba(128,128,128,.18–.25)` inside a JS string** — where no CSS variable is in
scope and no browser floor can be assumed.

### 4.4 Addition 3 — `opacity` instead of a muted-colour token

```css
.<pfx>-plot h6{font-size:.82rem;letter-spacing:.02em;text-transform:uppercase;
               opacity:.75;margin:0 0 .5rem 0;font-weight:600}
```

That is one delivery's **entire** authored stylesheet — a chart title, ×12 charts. No colour at all:
the element inherits the skin's text colour and `opacity` de-emphasises it. It cannot go out of
contrast range, cannot pick a Standard-only token, and needs no fallback.

> **For muted text inside an authored component, prefer `opacity:.7–.8`** over a muted-colour token,
> unless you need the muted text to be a different *hue* rather than a different *weight*.

### 4.5 Addition 4 — the progressive-enhancement double declaration

```css
/* Two declarations on purpose: the rgba() is the universally-supported fallback, the
   color-mix() ties the ring to the live accent. A browser that does not understand
   color-mix drops that declaration and keeps the one above. */
.ui-input:focus{outline:none;border-color:var(--ui-accent);
  box-shadow:0 0 0 3px rgba(125,160,140,.28);
  box-shadow:0 0 0 3px color-mix(in srgb, var(--ui-accent) 32%, transparent);}
```

24a §8's starter kit uses `color-mix` unguarded. On an older corporate browser the whole declaration
is dropped and **the focus ring disappears** — an accessibility regression, not a cosmetic one. The
two-line form costs 40 bytes.

### 4.6 The failure mode 24a does not warn about: a typo'd alias is invisible

One delivery's own change log records it: a module shipped CSS referring to **five token names that do
not exist**. An undefined custom property with no fallback invalidates the *whole declaration* at
computed-value time, so the control rendered completely unstyled. `validate` cannot see it (it scans
for hex literals and never resolves a `var()`), the browser logs nothing, and on a busy screen
"one panel is unstyled" reads as "the data did not load".

Their own gate caught it only by counting selectors (545 → 544). Run this instead — it is a real gate
and it takes a second:

```bash
python3 - "$BUNDLE" <<'PY'
import json, re, sys
# Platform tokens that legitimately have no definition in YOUR css (24a §3.1 census)
PLATFORM = {'--background','--current-line','--foreground','--foreground-muted','--comment',
            '--purple','--pink','--green','--red','--orange','--cyan','--yellow',
            '--bs-body-bg','--bs-body-color','--bs-border-color','--bs-border-color-translucent',
            '--bs-primary','--bs-secondary','--bs-light','--bs-success','--bs-info',
            '--bs-warning','--bs-danger','--bs-dark','--bs-link-color','--bs-link-hover-color'}
bad = 0
def check(name, css):
    global bad
    t = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    defined = set(re.findall(r'(--[A-Za-z0-9-]+)\s*:', t))
    for m in re.finditer(r'var\(\s*(--[A-Za-z0-9-]+)\s*([,)])', t):
        tok, nxt = m.group(1), m.group(2)
        if nxt == ')' and tok not in defined and tok not in PLATFORM:
            print(f'  {name}: var({tok}) is undefined AND has no fallback '
                  f'-> the whole declaration is dropped'); bad += 1
def walk(n):
    p = n.get('properties') or {}
    sm = (p.get('studioModel') or {}).get('stringValue')
    if sm:
        bt = (json.loads(sm).get('css') or {}).get('byTheme') or {}
        check(n.get('name'), '\n'.join(v or '' for v in bt.values()))
    jm = (p.get('Javascript') or {}).get('stringValue')
    if jm:
        cm = json.loads(jm); bt = dict(cm.get('cssByTheme') or {})
        if (cm.get('css') or '').strip() and not (bt.get('*') or '').strip(): bt['*'] = cm['css']
        check(n.get('name'), '\n'.join(v or '' for v in bt.values()))
    for c in (n.get('children') or []): walk(c)
for br in json.load(open(sys.argv[1] + '/branches.json')): walk(br['rootContent'])
print(('FAIL: %d undefined tokens' % bad) if bad else 'OK: every var() resolves or has a fallback')
PY
```

### 4.7 The sibling obligation — a class with no rule

From the same change log, worth quoting into every review:

> *"a class applied for a visual effect is checked against the stylesheet that is supposed to give it
> one."*

They shipped a marker class through four modules and cited it in three justifications, and it never
had a CSS rule anywhere in the project. The only thing anyone ever saw was the browser's default
greying — which looked enough like a disabled state that nobody questioned it for months.

---

## 5 · States, as a visual contract

The mechanics (`classList` not `className`, the `busy` flag, `errText`, the whole-script `try/catch`)
are in [09 §5–§6](09-studio-components.md). What belongs here is the *design* rule set, because this
is where a hand-built screen most often stops looking finished.

### 5.1 One slot, four sentences

The primary content region carries **one** placeholder element, reused for every non-happy state, and
the loading text is **authored into the markup** so the first paint is never blank:

```html
<tbody class="<pfx>-rows">
  <tr><td colspan="10" class="ui-empty">Loading…</td></tr>
</tbody>
```

20 of 22 screens ship exactly that; the same cell then carries the empty sentence, the error sentence
and the crash sentence. **A screen that can only ever show one of four strings in one place cannot get
its states out of sync.** No spinner, no skeleton, no overlay.

### 5.2 The empty sentence names the filter or the next action

Sampled from the 22 screens, neutralised: *"No documents match these filters."* · *"No open alerts."* ·
*"No blocked tasks."* · *"No planned lines and no actuals to compare."* · *"No open document to apply
this correction to."* · *"No case yet. Add the first one on the right."*

The last shape — **an empty state that names the next action and where it is** — is the one to reach
for on any screen whose empty state is the normal first-run state. ⛔ *"No data"* is never one of the
four sentences.

Error prefixes are uniform across 20 distinct instances, one shape:
`Could not load <the thing>: ` + the server's message.

### 5.3 The message strip, and where it lives

```css
.ui-msg{display:none;margin-top:12px;font-size:13px;border-radius:8px;padding:9px 12px;}
.ui-msg.show{display:block;}
.ui-msg.ok { background:rgba(5,150,105,.14); color:var(--ui-ok);  border:1px solid rgba(5,150,105,.35);}
.ui-msg.err{ background:rgba(220,38,38,.14); color:var(--ui-bad); border:1px solid rgba(220,38,38,.35);}
```

22 of 22 screens carry one, and **always immediately above the button that causes it** — not in a
page-level toast, not at the top of the screen. The tint/border alpha pair (`.14` fill, `.35` border)
is the same pair as §3.2's scale, so a message reads as part of the same system as a status pill.

Three visual obligations the delivery learned the hard way:

1. **An empty message hides the strip.** An empty success-styled box after an HTTP 200 is a lie.
2. **A message never outlives the action that wrote it** — cleared *before* the call, re-asserted
   *after* the reload, so a failed render leaves the strip EMPTY rather than WRONG.
3. **A click arriving while the previous action is in flight gets a sentence, not silence.** The bug
   this prevents is visual: the previous action's success text stays on screen and reads exactly as if
   the new one had succeeded.

### 5.4 The placeholder that is not zero

KPI values ship as an em dash and stay one until real data arrives: `>—<` appears **81 times** in the
22 markups. The acceptance criterion behind it:

> *KPIs without underlying data render "no data", never zero.*

**A KPI showing `0` when the query returned nothing is a false statement rendered in 28 px bold.**

### 5.5 Conditional chrome must be able to disappear

```html
<!-- Hidden unless the condition actually holds, so it disappears by itself once
     resolved and never becomes furniture. -->
<div class="<pfx>-migrate" hidden>…</div>
```

The `hidden` attribute is used on 22 of 22 screens for exactly this. **The test: if a banner is on
screen in the normal case, it has stopped being a banner and become a header.**

### 5.6 The accessibility gap the deliveries left

`aria-pressed` 47 uses across 15 of the 22 consoles, `role=` 9, `title=` 53, `aria-label` on every
unlabelled input — and **`aria-live`: 0**, on a project whose own non-functional requirements claim WCAG 2.1 AA. The strip
that carries every success and every refusal is never announced. Add `aria-live="polite"` and
`role="status"` to it; it is one attribute and it is the cheapest accessibility fix in this document.

---

## 6 · Interaction affordances worth copying

### 6.1 The KPI tile that is also a filter

```html
<div class="ui-kpis <pfx>-kpi-row">
  <button type="button" class="ui-kpi <pfx>-kpi" data-kpi="overdue" aria-pressed="false">
    <div class="ui-kpi-l">OVERDUE</div>
    <div class="ui-kpi-v ui-bad <pfx>-k-over">—</div>
  </button>
  …
  <div class="ui-kpi">                     <!-- a non-interactive tile is a div, not a button -->
    <div class="ui-kpi-l">AVG DAYS TO CLOSE</div>
    <div class="ui-kpi-v <pfx>-k-days">—</div>
  </div>
</div>
```

```css
.<pfx>-kpi{appearance:none;text-align:left;cursor:pointer;font:inherit;width:100%;}
.<pfx>-kpi:hover{border-color:var(--ui-accent);}
.<pfx>-kpi[aria-pressed="true"]{border-color:var(--ui-accent);
                                box-shadow:0 0 0 2px rgb(4 120 87/.25);}
```

Four things make this work, and all four transfer:

- It is a real `<button>` — keyboard, focus and `aria-pressed` for free.
  `appearance:none; font:inherit; text-align:left; width:100%` undoes the browser's button styling in
  four declarations.
- **Interactive tiles are buttons, inert tiles are divs.** The affordance is structural, so it cannot
  drift out of sync with behaviour.
- **The pressed state is a border + ring, not a fill** — the number stays the brightest thing on the
  tile.
- `aria-pressed` carries the state, so it is not colour-only.

Motion, where a screen adds it, is gated:

```css
.<pfx>-kpi[data-kpi]{cursor:pointer;user-select:none;
  transition:border-color .12s ease,box-shadow .12s ease,transform .12s ease;}
.<pfx>-kpi[data-kpi]:hover{border-color:var(--ui-mut);transform:translateY(-1px);}
.<pfx>-kpi[data-kpi]:focus-visible{outline:2px solid var(--ui-accent);outline-offset:2px;}
@media (prefers-reduced-motion:reduce){
  .<pfx>-kpi[data-kpi]{transition:none;}
  .<pfx>-kpi[data-kpi]:hover{transform:none;}}
```

### 6.2 Filter chips — and the rule that gives a screen hierarchy

```css
.ui-chip{border-radius:999px;padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer;
  background:var(--ui-surface);color:var(--ui-fg);border:1px solid var(--ui-bd);}
.ui-chip:hover{background:var(--ui-surface-sunk);}
.ui-chip[aria-pressed="true"]{background:var(--ui-accent);color:var(--ui-accent-fg);
  border-color:var(--ui-accent);}
```

The filter bar is one flex row that wraps, mixing native inputs and chips, with the search field
taking the slack:

```css
.<pfx>-filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 16px;}
.<pfx>-filters .ui-input{width:auto;min-width:120px;margin:0;}
.<pfx>-filters .<pfx>-search{flex:1 1 260px;min-width:200px;}
```

The design rule, recorded in the delivery's own review log after the screen failed a walkthrough:

> *the view toggles and the four commands sat in one undifferentiated row of chips wearing the same
> primary colour, so the screen offered six equal-looking buttons and no hierarchy; the toggles are now
> a segmented control and **the primary colour means "this acts"**.*

⛔ **Primary colour is reserved for the control that performs an action.** A control that is merely
*selected* gets a segmented/pressed treatment, never the accent fill. Break this and a screen with six
buttons has no hierarchy no matter how good its type scale is.

### 6.3 Page-level actions belong in the breadcrumb

20 of 22 consoles publish their page actions into the breadcrumb bar rather than rendering a toolbar.
The mechanism — a shared lib that mirrors an existing DOM button into a breadcrumb descriptor,
forwards the click, and tracks label/enabled state with a `MutationObserver` — is in
[09 §4.1](09-studio-components.md).

The **design** facts:

- Icon census across all breadcrumb contributions: a refresh glyph ×20, then one each of trash, print,
  wand and close-circle. Variants: `secondary` ×22, `primary` ×1, `danger` ×1.
  **Every console gets a secondary Refresh, last in order.**
- Four screens used raw emoji as icons. Those are the inconsistency, not the convention: **use the
  icon-font class** — it inherits the theme colour and matches every stock plugin's breadcrumb button.
- **Design consequence, and it is the whole point:** the screen's own markup carries **no toolbar**.
  A hand-built toolbar is the most reliable tell that a console was hand-built, because it will never
  match the theme's buttons on all five skins.

⚠️ **An open decision the deliveries never settled.** Every console still renders its own
`<h1 class="ui-title">` *and* sits under a breadcrumb that already names the page — two page titles
about 30 px apart. If you adopt breadcrumb actions, decide once whether the `h1` earns its place. It
does when it carries a subtitle or a live status pill (the dashboard's does: `h1` + one line of
sub-copy + an embedded status chart); otherwise the screen should start at the KPI strip.

### 6.4 Disclosure, disabling, and the two rules that keep a console honest

Both were written into the delivery's own requirements after being found repeatedly in production, and
both are interaction rules, not code rules:

> **A disclosure that does not disclose reads as a dead button.** *"A control that discloses rather
> than acts must say what it opened, bring it into view, and never share a caption with the control
> that acts. An edit form must never look like a create form."*
>
> Found four times in four unrelated modules. In one, the operator pressed *Clone…*, saw nothing
> happen, and then edited the form they were still looking at — which was the source record.

> **A disabled control and a rule that refuses are not two safeguards.** *"The greyed one is always
> the worse copy. It states the conclusion and withholds the reason; it can drift from the rule
> without anything failing… before disabling a control, look for the rule that already refuses the
> thing. If one exists, delete the disable and let the refusal speak."*

The paired positive obligation, from the same document:

> *A field that cannot be computed must say so, not disappear. Removing a field is not a message.
> Where a figure cannot be produced, the space it occupies states why.*

Its implementation is one class:

```css
.ui-note{font-size:12px;color:var(--ui-mut);line-height:1.45;margin-top:8px;}
.ui-note.ui-warn{color:var(--ui-warn);}
.ui-note.ui-bad {color:var(--ui-bad);}
```

A note under a control is where the reason goes. 12 px, muted, and it is the difference between a
console that teaches and one that stonewalls.

### 6.5 The escape hatch inside the escape hatch

Where an authored screen needs a real platform control, it embeds the plugin tag in its own markup
rather than reimplementing it:

```html
<div class="ui-head">
  <div><h1 class="ui-h1">Operations dashboard</h1><p class="ui-h2">…</p></div>
  <plugin id="<pfx>_status_pill" name="chart.js.plugin"></plugin>   <!-- live status, themed by the platform -->
</div>
```

And where a picker has no row to offer, the **create path sits inside the control**, not in a header —
present on every `<select>` fed by a lookup table:

```html
<span class="<pfx>-field">
  <select class="ui-input" id="<pfx>-partner"></select>
  <button type="button" class="<pfx>-manage" data-manage="<pfx>-partner" title="Open source">
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
  </button>
</span>
```

```css
.<pfx>-field{position:relative;display:block}
.<pfx>-field .ui-input{padding-right:52px}          /* reserve room, never overlap the caret */
.<pfx>-manage{position:absolute;right:24px;top:50%;transform:translateY(-50%);
  display:inline-flex;align-items:center;justify-content:center;
  width:22px;height:22px;padding:0;border:0;border-radius:4px;
  background:transparent;color:var(--ui-accent);cursor:pointer;line-height:0}
.<pfx>-manage:hover{background:var(--ui-surface-sunk);color:var(--ui-fg-strong)}
.<pfx>-manage:focus-visible{outline:2px solid var(--ui-accent);outline-offset:1px}
```

The obligation behind it: *"the create path belongs beside the picker that failed to offer the row,
not only in a header — the operator who cannot find their entry is looking at the dropdown."*
`right:24px` (not `right:8px`) clears the native select caret; `padding-right:52px` reserves the space
so the button never sits on top of the value.

---

## 7 · Icons — two systems, chosen by surface

| surface | system | why |
|---|---|---|
| platform markup (`card-header`, breadcrumb) | an **icon font** class | it inherits `color`, so it is theme-safe for free, and it matches every stock plugin |
| inside a studio component | **inline SVG**, `stroke="currentColor" fill="none"`, `aria-hidden="true"`, 15–16 px, `stroke-width="2"`, round caps and joins | the font classes are page-global and unscoped; an inline SVG carries no colour of its own |

49 inline SVGs in the one delivery with studio components, 0 in the other three (which have none).
**`stroke="currentColor"` is the whole trick** — the icon is whatever colour its container resolved
to, on every skin, with no token and no `byTheme` key.

Never use a badge class for status (0 occurrences in 4/4 — correctly), and never the light badge
variant, which is white on every dark skin ([24a §2](../24a-theming-and-dark-mode.md)).

---

## 8 · The paper exception, and print

The one place a hard-coded `#ffffff` / `#000000` is **correct** is a document preview, because the
thing being previewed is paper:

```css
.doc-sheet{background:#ffffff;color:#000000;margin:16px auto 0;padding:10mm;
  width:210mm;max-width:100%;box-sizing:border-box;}
.doc-sheet:empty{display:none;}                      /* an unrendered sheet is not a white slab */
.<pfx>-tbl th,.<pfx>-tbl td{border:1px solid #000;padding:3px 5px;vertical-align:middle;}
.<pfx>-tbl th{font-weight:600;text-align:center;font-size:10px;}
.<pfx>-warn{margin-top:14px;font-size:10px;color:#b91c1c;}
.<pfx>-foot{margin-top:18px;font-size:10px;color:#555;}
```

```css
@media print {
  /* only the paper survives. Everything else on the page — the application chrome, the
     left nav, the pickers — is screen furniture and must not reach the printer. */
  .doc-chrome{display:none !important;}
  .doc-sheet{margin:0;padding:0;border:0;box-shadow:none;width:auto;background:#fff;color:#000;}
  .doc-sheet[hidden]{display:none !important;}
  .<pfx>-sec,.<pfx>-items-h th,.<pfx>-items-n td{
    background:#f2f2f2 !important;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
  /* a row split across a page break makes a statutory document unusable */
  .<pfx>-tbl tr,.<pfx>-items tr,.<pfx>-box tr{page-break-inside:avoid;}
  .<pfx>-sign,.<pfx>-sum{page-break-inside:avoid;}
  @page{size:A4 portrait;margin:10mm;}
}
```

Rules of thumb:

- The sheet is `210mm` wide with `max-width:100%`, so it shrinks on a phone and keeps A4 proportions on
  a desktop.
- `:empty{display:none}` stops it being a white rectangle before data arrives.
- `print-color-adjust:exact` is **required** or the browser drops the zebra fills.
- Every row-bearing element gets `page-break-inside:avoid`.
- The document picks a font stack that actually contains the **script** it must render
  (`'DejaVu Sans', <a face covering your script>, 'Segoe UI', Arial, sans-serif`) — not the
  application's stack, which is chosen for chrome, not for glyph coverage.

⛔ `@media print` inside a scoped component **cannot hide the application shell** — the scoper
prefixes every selector with the component's wrapper, so `.app-header{display:none}` becomes a
selector that matches nothing. See [09 §9.1](09-studio-components.md) for the print trap in full.

---

## 9 · The four anti-patterns that make a screen read as generated

All four were found in the one delivery that authored CSS, all four survived to production, and all
four are cheap to avoid if you know them before you start.

### 9.1 ⛔ 26 copies of one stylesheet

540 KB of authored CSS over 22 components. **107 CSS lines are byte-identical in all 22 files**,
201 appear in at least 20 of them, and **120 of the 940 distinct selectors appear in ≥20 components**
(59 in all 22). On top of the shared kit, four screens carry a *second*, older kit under their
own prefix — a complete duplicate of the token block, card, table, KPI, button and pill rules —
because the earlier convention was "one prefix per component". The file that carries them opens with a
comment admitting it:

```
/* ---- shared screen kit, copied from the invoices console ----
   This component was authored with its own prefix and did not carry the
   kit, so kit markup rendered unstyled. The component's own rules are
   kept below, untouched. */
```

Symptoms on screen: a class works on one screen and renders unstyled on the next; two screens drift
apart on the first edit to either; a token added to the kit reaches 1 of 22 components.

**The fix the platform already supports** — and which this delivery used for JS but not for CSS.
`studioModel.libs[]` accepts a `CSS` asset ([24 §2](../24-html-component-studio.md), `kind: JS_ESM |
JS_CLASSIC | CSS | FONT`), served as a `<link rel=stylesheet>`. Split the stylesheet in three:

| layer | lives in | measured size | scoped? |
|---|---|---|---|
| the project kit — layout, type, spacing, every shared class; colour **only** via `--ui-*` | a `CSS` lib asset, declared once per component | ~20 KB, **one copy** instead of 22 | **no** — so every selector must carry the prefix, and no bare `.card`/`table`/`h1`/`button` selectors, ever |
| the token block + this screen's unique classes | `css.byTheme["*"]` | 2–6 KB per screen (the measured `"*"` blocks average 22 KB *because* they carry the duplicated kit) | yes, to the component wrapper |
| the semantic ramp per dark skin | the four dark `byTheme` keys, byte-identical in 22/22 | 755 B × 4 | yes |

The library JS proved the mechanism: one `JS_CLASSIC` asset put one implementation in tenant files
instead of fourteen copies in fourteen scripts. The same `libs[]` array takes the stylesheet.

⚠️ **Know the trade before you take it.** A `CSS` lib asset is **not** run through the studio scoper —
it is a page-global stylesheet appended at mount, after the theme's. Prefixed classes are safe (and
win at equal specificity); **one bare element selector restyles the whole application.** That is the
price of a single copy, and it is worth paying only if you can hold the prefix discipline. If you
cannot, keep the kit in `byTheme["*"]` and accept the duplication — but then **generate** the
components from one source instead of copy-pasting them.

### 9.2 ⛔ Overriding the application font

`font-family:Helvetica,Arial,sans-serif` on the root class, in 22 of 22 components. The screen
therefore renders in a different typeface from the breadcrumb directly above it, the left nav beside
it, and every stock table on the neighbouring page. On a console that fills 90 % of the viewport this
reads as *"a different app embedded in the app"* — and it is invisible to the author, who only ever
looks at their own screen.

**Set no `font-family` at all** unless the component is genuinely a document (§8 earns it, and needs a
script-specific stack anyway). Inherit: the theme's font is the one every other screen uses.

### 9.3 ⛔ `filter: brightness()` as the hover state

52 uses of `filter:brightness(.92)` on hover. It is compact and it always changes *something*, which
is why it survived. But `.92` is a light-skin instinct: on a dark skin the accent is a light tint and
darkening it moves the control **towards** the page, not away from it — the hover reads as "greyed
out".

A skin-independent hover is a translucent overlay in the direction of the text colour, or a second
accent token / `color-mix` pair. If you keep `brightness()`, know that you are trading correctness for
brevity, and check it on two dark skins before shipping.

### 9.4 ⛔ Chart CSS is the last blind spot

`validate` never reads a chart's `cssByTheme` ([24a §5.6/§9](../24a-theming-and-dark-mode.md)). Across
the four deliveries:

| | charts | with per-theme CSS |
|---|---|---|
| B | 31 | 31 — all five keys, a full light/dark palette swap |
| D | 12 | 12 — `"*"` only, and correctly so: it declares no colour at all, only `opacity` |
| A | 38 that carry a chart-level CSS slot | 15 `"*"` only, **23 with none** |
| C | 87 | **0** |

C's 87 charts are not broken — every one reads the live text colour off the mounted element and sets
the paper background and default colour from it, and its series palettes are semantic literals in the
config, which [22 §6.1](../22-charts-params-and-filters.md) says is correct. But there is no per-theme
*container* CSS anywhere, so anything the canvas does not paint — a title, an axis caption in HTML, a
legend rendered outside the canvas — is un-themed by construction.

> **Decide per chart: either it declares zero colour outside the canvas (D's `opacity:.75` title is
> the model), or it gets a `cssByTheme` palette (B's model, below). Nothing offline will tell you
> which one you have.**

B's model, the cleanest chart-theming pattern in the four deliveries — **four ramps named by role**:

```css
/* cssByTheme["*"]  — the light ramp, on the chart's own container class */
.<pfx>-plot{--c1:#173C60;--c2:#C2703A;--c3:#2E7D5B;--c4:#B98A1E;--c5:#7A5EA6;--c6:#4E93C4;
            --c-good:#2E7D5B;--c-warn:#B98A1E;--c-risk:#C2703A;--c-crit:#B5485A;--c-mute:#8A94A0;
            --r1:#B8D2E6;--r2:#6C96BA;--r3:#2F6FA8;--r4:#173C60;      /* sequential ramp */
            --div-up:#B5485A;--div-down:#173C60;                       /* diverging pair  */
            color:var(--bs-body-color);width:100%}
/* ["Dark"] == ["Dracula"] == ["Forest"] == ["Dark Blue"] — the same ramp, lifted */
.<pfx>-plot{--c1:#6C96BA;--c2:#E08B54;--c3:#4FBF8B;--c4:#E8C25A;--c5:#A98CD6;--c6:#89C2E8;
            --c-good:#4FBF8B;--c-warn:#E8C25A;--c-risk:#E08B54;--c-crit:#E0768A;--c-mute:#9AA2AD;
            --r1:#D6E6F2;--r2:#A8C6DE;--r3:#6C96BA;--r4:#3E6D96;
            --div-up:#E0768A;--div-down:#6C96BA}
```

```js
// js — read the ramp off the container, never hard-code it here
var el = this.$find('.<pfx>-plot')[0], cs = getComputedStyle(el);
var V  = function(n,f){ var v=(cs.getPropertyValue(n)||'').trim(); return v||f; };
var S  = { good:V('--c-good','#2E7D5B'), warn:V('--c-warn','#B98A1E'),
           crit:V('--c-crit','#B5485A'), base:V('--r4','#173C60') };
var LAY = { paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
            font:{ color:cs.color, family:V('--bs-body-font-family','system-ui,-apple-system,sans-serif') },
            margin:{t:4,b:4,l:4,r:4}, autosize:true };
```

Categorical `--c1…c8`, semantic `--c-good/warn/risk/crit/mute`, sequential `--r1…r4`, diverging
`--div-up/--div-down`. The dark ramp is the light ramp lifted in lightness and slightly desaturated;
the **role names never change**, so supporting a new skin never touches the JS.

(⚠️ `--bs-body-font-family` is defined on 0 of 5 skins per [24a §3.1](../24a-theming-and-dark-mode.md),
so that `V()` call always takes its fallback. Harmless *because a fallback was written* — a bare
`var(--bs-body-font-family)` would have dropped the whole `font` object. §4.6 again.)

---

## 10 · The design checklist

Everything here is either something the deliveries got right and you should copy, or something they
got wrong and you should not repeat. It extends [24a §10](../24a-theming-and-dark-mode.md).

**Choosing the family**

- [ ] This screen genuinely needs authored CSS. *(Three of four deliveries needed none. If it is a
      list, a form, a chart grid or a filter+table, it does not — see [09 §1](09-studio-components.md).)*
- [ ] The panel is `main-card mb-3 card` with a `card-header`, one icon glyph in **the project's
      single** gradient class, and the header text as an `nct.label.plugin`, not a typed string.
- [ ] Content sits in `nct.parsis.plugin` slots, one per cell, so it can be swapped without touching
      layout.
- [ ] Every `crud.table.plugin` has a `dynaform.filter.form.plugin` above it in the same slot.
- [ ] Equal-height tiles use `he-100`. `h-100` appears nowhere.
- [ ] Density is `card-body py-2 px-3` on tiles, default padding on content panels. No authored
      `padding`.
- [ ] The html : label : slot ratio on the page is roughly 1 : 1 : 1. No visible string is typed into
      markup.

**Authored CSS**

- [ ] **One kit prefix for the whole project**, plus a short per-screen prefix for what is unique to
      one screen. Not one kit per component.
- [ ] Chrome colours bind two-level (`var(--current-line, #fff)`); **status colours are your own
      literals in `"*"`, redefined in all four dark keys** — audit that the two sets match one for one.
- [ ] The primary button's foreground **inverts** between light and dark skins.
- [ ] Every `var(--x)` either resolves or carries a fallback (§4.6 gate). An undefined alias silently
      un-styles the whole control.
- [ ] Every class the markup uses has a rule in the stylesheet that is supposed to give it one (§4.7).
- [ ] `color-mix()` is paired with an `rgba()` declaration above it.
- [ ] No `font-family`, unless the component is a document.
- [ ] Muted text is `opacity:.7–.8`, or the muted token — never a grey literal.
- [ ] Neutral tints are `rgba(127,127,127,.10–.28)` (or `color-mix` from a token); status tints are
      `rgba(<hue>,.12–.16)` with a `.35` border.
- [ ] One `@media` breakpoint for the deliberate multi-column split;
      `repeat(auto-fit,minmax(Npx,1fr))` for everything else.
- [ ] Wide tables get an `overflow-x:auto` wrapper **and** a `min-width` on the table, so columns do
      not crush before the scrollbar appears.
- [ ] Every `@keyframes` name is prefixed — keyframe names are page-global.

**States**

- [ ] The primary content slot ships `Loading…` as authored markup, and the same slot carries the
      empty, error and script-crash sentences.
- [ ] The empty sentence names the filter or the next action. Never "No data".
- [ ] The error sentence is `Could not load <the thing>: ` + the server's message.
- [ ] The whole script is wrapped in one `try/catch` whose `catch` writes into the UI, not only the
      console.
- [ ] The message strip is manipulated with `classList`, never `className`; an empty message hides it;
      it is cleared before an action and re-asserted after the reload.
- [ ] One module-level `busy` flag; the button is disabled for the duration; a click while busy gets a
      sentence, not silence.
- [ ] A KPI with no data shows `—`, never `0`.
- [ ] Conditional chrome uses the `hidden` attribute and disappears by itself. It never becomes
      furniture.
- [ ] The message strip carries `aria-live="polite"` and `role="status"`.

**Interaction**

- [ ] Interactive tiles are `<button>` with `aria-pressed`; inert tiles are `<div>`.
- [ ] The pressed state is a border/ring, not a fill; the number stays the brightest thing.
- [ ] Primary colour means "this acts". Selection uses a segmented/pressed treatment.
- [ ] Page-level actions are published to the breadcrumb (`secondary`, and every console gets a
      Refresh last in order). **The component's markup carries no toolbar.**
- [ ] A control that discloses says what it opened, brings it into view, and does not share a caption
      with the control that acts.
- [ ] Before disabling a control, find the rule that already refuses; if it exists, delete the disable
      and let the refusal speak. If you keep the disable, the reason sits beside it in a note class.
- [ ] A create path sits beside the picker that failed to offer the row.
- [ ] Icons inside a component are inline SVG with `stroke="currentColor"` and `aria-hidden="true"`;
      icons in platform markup are icon-font classes.

**Charts**

- [ ] Container has `position:relative` **and** a pixel height from the scale (§2.7);
      `maintainAspectRatio:false` is set.
- [ ] Either the chart declares zero colour outside the canvas, or it carries a `cssByTheme` palette
      with role-named ramps read back via `getComputedStyle` (§9.4).
- [ ] The chart's visible title is a sibling label plugin, not a config title
      ([08](08-charts-and-dashboards.md)).

---

## 11 · Where this contradicts or extends the library

| doc | what the evidence says to change |
|---|---|
| [24a §6](../24a-theming-and-dark-mode.md) | Add the **two-tier token block** as a named pattern, not an exception. The current list of legitimate per-skin uses (image / shadow / gradient / one-skin rescue) is missing the one **every** project needs: the semantic status ramp. Give the measured cost (755 B per dark key, byte-identical in 22/22, ~150 B of it declarations) and the accent-inversion rule. |
| [24a §8](../24a-theming-and-dark-mode.md) | The starter kit says "rename the prefix per component". Change to **one prefix per project**. Add the `libs[] kind:"CSS"` sharing route with its unscoped caveat, drop `font-family` from the root class, and pair the `color-mix` focus ring with an `rgba` fallback. |
| [24a §9](../24a-theming-and-dark-mode.md) | Add the **undefined-`var()` gate** (§4.6). It catches a class of silent, total un-styling that the hex-literal check cannot see, in ~25 lines. |
| [24a §3.2](../24a-theming-and-dark-mode.md) | Add `opacity` as the first choice for muted text, and `rgba(128,128,128,.10–.28)` as the token-free neutral tint — used independently by 4 of 4, and the only option inside a JS string. |
| [24 §7](../24-html-component-studio.md) | Add the **breadcrumb action proxy** ([09 §4.1](09-studio-components.md)): a shared lib that mirrors an existing DOM button into a descriptor and forwards the click. It is what lets 20 screens keep their own action logic and still carry no toolbar. |
| [24 §4.4](../24-html-component-studio.md) | Codify the **state vocabulary**: one slot, four sentences; `Loading…` authored into the markup; `classList` not `className`; an empty message hides the strip; one `busy` flag; em dash, never zero; `aria-live` on the strip. |
| [22 §6](../22-charts-params-and-filters.md) | Add the container-height scale (92–150 / 280–340 / 360–440 px), the mandatory `maintainAspectRatio:false`, the `calc(100% - 1.9rem)` title reservation, and the **four role-named ramps** in `cssByTheme` read back with `getComputedStyle`. |
| **this doc, §1–2** | Nothing in the library describes **Family A** — the zero-CSS console that three of four deliveries are made of: the frame, the panel/grid/slot/label vocabulary, the `he-100` and `py-2 px-3` density rules, and the 1:1:1 ratio as the tell that a screen was composed rather than typed. It is the most-used pattern in production and was the least documented. |

---

## 12 · Done when

- The screen belongs to a family **on purpose**, and if it is Family B one of
  [09 §1](09-studio-components.md)'s five conditions is written down.
- Nothing visible is a typed string; nothing placed is a bare child.
- The §4.6 gate prints `OK`, and the hex-literal warnings from `validate` are exactly the token
  aliases and nothing else.
- The screen has been opened on **Standard and on two dark skins**, and the primary button, the status
  pills and the hover state were looked at on each — offline gates cannot see any of the four
  anti-patterns in §9.
- Someone who did not build it can name the empty state, the error state and the busy state without
  reading the code.
