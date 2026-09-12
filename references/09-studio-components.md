# 09 · Studio components — the hand-built console

> **What this is.** Field evidence from four delivered projects, read against
> [24](../24-html-component-studio.md), [24a](../24a-theming-and-dark-mode.md),
> [24b](../24b-html-composition-and-plugin-tags.md), [24c](../24c-html-data-tables-and-paging.md) and
> [24d](../24d-html-component-structure.md). Sources are **A** (433 pages, 163 CRUDs, 22 studio
> consoles), **B** (129 pages, 38 CRUDs), **C** (128 pages, 31 CRUDs, 87 charts), **D** (67 pages,
> 12 CRUDs). Every skeleton is trimmed from code that shipped; only the nouns are renamed.

---

## 1 · The census, and the decision

| | html plugin nodes | carry a `studioModel` | **studio-ACTIVE** |
|---|---|---|---|
| A | 1 304 | 142 | **22** |
| B | 962 | 466 | **0** |
| C | 574 | 15 | **0** |
| D | 207 | 44 | **0** |
| | **3 047** | 667 | **22 (0.7 %)** |

⛔ **99.3 % of `nct.html.plugin` nodes in production are CLASSIC — layout, not components.** Three of
four projects contain zero studio components. Budget the plugin as a **layout host** first and an
escape hatch second: a project reaches for the studio at most once or twice per ten pages.

⛔ **645 nodes carry a `studioModel` that is pure noise** — all the literal
`{"docs":[],"libs":[],"css":{"byTheme":{}},"scripts":[]}` that [24 §2](../24-html-component-studio.md)
calls harmless. It arrives by the hundred on auto-generated form-layout nodes and makes
`find --plugin nct.html.plugin | grep studioModel` useless for locating the real components. Strip it
from an inherited export; locate components with the audit script in §13.

**Reach for a studio component only when one of these is true** — these five survived four deliveries:

1. **One screen must fuse 3–8 entities into a non-tabular workspace from ONE server call** (15 of A's 22).
2. **The interaction is not "row → form"** — a board, a timeline, a paper preview, master-detail with
   one selection driving both panes.
3. **A cell is not text** — sparkline, meter, stacked pill.
4. **Page-level actions whose behaviour is code**, not a CRUD action.
5. **A printable document** the reader sends outside the company.

⛔ **Do not hand-build "list + edit one entity".** You reimplement paging, filters, validation,
localization and role gating badly, and every future field becomes a code edit inside a JS string
inside a JSON string inside an export.

> **Calibration — what the 3 047 classic nodes host** (A / B / C / D): `nct.label.plugin`
> 1 128 / 851 / 569 / 179 · text field 594 / 391 / 208 / 100 · `nct.parsis.plugin` 388 / 373 / 334 / 92 ·
> dropdown 274 / 241 / 126 / 37 · datepicker 134 / 68 / 42 / 9 · textarea 118 / 56 / 23 / 17 ·
> filter-submit 0 / 42 / 41 / 12 · `chart.js.plugin` 9 / 0 / 87 / 0 · help 0 / 78 / 0 / 26.
> **Zero across all four, in 3 047 html properties:** `<style>`, `<script>`, `<include>`, `onclick=`,
> `icon-wait`, `block-wait-selector`, `wait-event`, `vp="…"`, `commonContent`, and any
> `style="…color…"` / `style="…background…"`. Four independent deliveries converged on the same
> discipline: **markup is framework classes only, colour never appears in markup, behaviour is never
> attached in an html property.**

---

## 2 · Placement, identity, gating

All 22 sit at the same depth — `Home/<Page>/parsis/Layout/parsis/<Screen> UI`: the page's parsis holds
a **classic** html node (pure `card`/`row`/`col-*` with parsis slots) whose parsis holds the component.

| slot | value | evidence |
|---|---|---|
| `identifier` | `<pfx>_<screen>_ui` — symbolic, never a numeric fallback | 22/22 |
| `name` | `"<Screen> UI"` | 22/22 |
| `roleAccess.publicReadAccess` | `true` | **22/22 — wrong, see below** |
| `roleAccess.roleGroupAccessors` | all `view:false` | no node-level gate anywhere |

> ⛔ **Correction to [24 §4.4](../24-html-component-studio.md): the delivery did only the rule half of
> "gate the node AND the rule", and you must do both.** 86 of A's 619 rules call
> `service.security.user()`; every mutating rule opens with the guard below. It worked because the
> *page* above the component is gated and the component is read-only until a rule agrees to write. It
> is still wrong for a non-security reason: a `publicReadAccess:true` studio node makes the CSS resolve
> the skin as **`Dark` for an anonymous viewer** ([24a §1.4](../24a-theming-and-dark-mode.md)), so the
> screen you previewed signed-in on Standard is not the screen a logged-out visitor sees. The rule is
> the protection; the node is what stops an unauthorised user seeing an error-shaped screen.

```groovy
def who = null
try { who = service.security.user()?.email } catch (Throwable __t) { }
if (who == null) return [ok:false, error:'FORBIDDEN', message: T('Sign in to edit this.','…')]
```

---

## 3 · The `studioModel`, verbatim

One node, one page, one script named `main`, one lib, five CSS keys, **zero documents** — 22/22.
Empty `docs` means legacy script-selection mode ([24 §3.2](../24-html-component-studio.md)); there is
not one `<include>` in 3 047 nodes.

```jsonc
{
  "libs": [
    { "name": "uikit",                        // -> ctx.libs.uikit
      "enabled": true, "order": 0,
      "globalVar": "UiKit",                   // JS_CLASSIC: window.UiKit becomes ctx.libs.uikit
      "assets": [
        { "kind": "JS_CLASSIC", "url": null,
          "path": "studio/ui-kit/ui-kit.js",  // RELATIVE, under studio/, .js — the only servable shape
          "fileName": "ui-kit.js",
          "entry": false,                     // meaningless for JS_CLASSIC; globalVar decides
          "order": 0 } ] }
  ],
  "docs": [],
  "scripts": [
    { "name": "main", "code": "try {\n…\n} catch (err) { … }",
      "enabled": true, "order": 0, "libNames": ["uikit"] }
  ],
  "css": { "byTheme": {
      "*":         "/* the whole design, ~16 kB: tokens + an alias layer */",
      "Dracula":   "/* 644 B — six alias lines and nothing else */",
      "Forest":    "/* identical */", "Dark": "/* identical */", "Dark Blue": "/* identical */" } }
}
```

Median per component: **10 kB markup, 42 kB script, 18 kB CSS**; largest 20 kB + 120 kB.

> ⛔ **Correction to [24d §2.1](../24d-html-component-structure.md): the budget is right and the
> delivery paid for ignoring it.** Against ≤120 markup lines / ≤150 script lines / ≤6 documents, every
> one of the 22 is **8–10× over, in one file**. The post-mortem records the consequence twice: *"a
> sweep anchored on the script named `main` missed the two screens whose live script is not `main`"*,
> and *"one round fixed the error normaliser on one screen, then found three distinct shapes across 22
> — anchoring on one body would have covered 4 and silently missed 18."* **Split — and carry the
> counter-lesson: a screen is the union of its scripts, not one of them.** Every sweep, audit and grep
> must enumerate all scripts of all components programmatically.

> ⛔ **Correction to [24d §2.2](../24d-html-component-structure.md): four split scripts in LEGACY mode
> are four independent programs, not one shared scope** — because you will wrap each in `try{}` (§5.1).
> Put every shared helper in the kit lib, or keep one script. Adding a single `<include src="boot.js"/>`
> anywhere flips the component into include mode and silently drops every script you did not include.

> ⛔ **`libNames` is declared inconsistently and 6 of 22 get away with it by accident.** They declare
> `libs:[{name:"uikit"}]` with `scripts[0].libNames: []`, then call `ctx.libs.uikit`. It works only
> because the runtime loads **all** declared libs when the union of `libNames` is empty
> ([24 §6.1](../24-html-component-studio.md) step 3). Add a second script that declares any lib and
> `uikit` stops loading, silently — the `if (!kit) return;` guard then removes the breadcrumb button
> with no error. **Always name the lib in `libNames`.** `validate` will not tell you either way.

---

## 4 · The project kit — cross-cutting behaviour shipped once as a lib

**The most valuable idea in the 22, and it is in no doc.** Ship one small `JS_CLASSIC` file at
`tenant-files/studio/ui-kit/ui-kit.js` and declare it as a lib in every component; A's is 9.6 kB and
is declared in 21 of 22.

⛔ **The mistake to avoid at the same time:** A shipped the kit for the breadcrumb and still
copy-pasted a **~200-line helper preamble into all 22 scripts** — ≈4 400 duplicated lines. Put the
preamble in the kit too: `UiKit.helpers(ctx)` returning
`{q, qa, esc, errText, pick, arr, say, bind, action, L, applyLocale, setLocale}`, destructured in one
line per script.

### 4.1 Breadcrumb-by-proxy

[24 §7](../24-html-component-studio.md) documents `ctx.breadcrumb.set([...])` and stops. The
refinement: **do not write descriptors by hand — proxy the buttons the screen already has.** The
screen keeps its buttons, handlers and enable/disable logic, and gains a title-bar action for free.

```js
/* tenant-files/studio/ui-kit/ui-kit.js — kind JS_CLASSIC, globalVar "UiKit" */
(function (global) {
  'use strict';
  if (global.UiKit && global.UiKit.__v) { return; }          // page-global, idempotent

  // Screens signal "working" by disabling the button. Resolve on the FIRST `disabled` change
  // after the click, whatever state it lands in — a screen may re-enable and immediately
  // re-disable in one synchronous block (deleting the last row does exactly that), and a
  // callback reading the FINAL state never resolves, leaving the block overlay up for the
  // whole timeout.
  function waitIdle(el, maxMs) {
    return new Promise(function (resolve) {
      setTimeout(function () {                               // one macrotask: let the screen's
        if (!el.disabled) { resolve(); return; }             //   own handler set disabled first
        var timer = null, mo = new MutationObserver(function () { finish(); });
        function finish() {
          try { mo.disconnect(); } catch (e) {}
          if (timer) { clearTimeout(timer); }
          resolve();
        }
        timer = setTimeout(finish, maxMs || 30000);
        mo.observe(el, { attributes: true, attributeFilter: ['disabled'] });
      }, 0);
    });
  }

  // A screen hides an action on the button OR on the group around it (a bulk bar); both must
  // mean "not in the breadcrumb".
  function isHidden(el) {
    if (el.hidden || el.getAttribute('hidden') !== null) { return true; }
    return !!(el.closest && el.closest('[hidden]'));
  }

  function actions(ctx, spec) {
    if (!ctx || !ctx.breadcrumb || !spec || !spec.length) { return null; }   // old runtime -> no-op
    var watched = [], inFlight = false, pending = null;

    spec.forEach(function (item) {
      if (!item.sel) { return; }                       // {run:…} entries have no DOM source
      var el = ctx.root.querySelector(item.sel);
      if (!el) { return; }
      item._el = el;
      if (!item.keep) { el.style.display = 'none'; }   // hidden, NOT removed: the screen still
      watched.push(el);                                //   reads/writes it and click() still works
      if (item.watch) {                                // a group whose [hidden] gates this action
        var g = ctx.root.querySelector(item.watch);
        if (g && watched.indexOf(g) === -1) { watched.push(g); }
      }
    });

    function build() {
      var out = [];
      spec.forEach(function (item, i) {
        var el = item._el;
        if (item.sel && !el) { return; }               // declared against markup this screen lacks
        if (el && isHidden(el)) { return; }            // the screen hides it -> hide it in the bar
        out.push({
          key: item.key,
          label: (typeof item.label === 'function') ? item.label()
               : (item.label || (el ? (el.textContent||'').replace(/\s+/g,' ').trim() : item.key)),
          icon: item.icon, variant: item.variant || 'secondary', title: item.title,
          order: (typeof item.order === 'number') ? item.order : i,
          disabled: el ? !!el.disabled : !!item.disabled,
          block: item.block,
          onClick: function () {
            if (typeof item.run === 'function') { return item.run(); }
            inFlight = true;
            try { el.click(); } catch (e) { inFlight = false; sync(); throw e; }
            if (item.async === false) { inFlight = false; sync(); return undefined; }
            return waitIdle(el).then(function(){ inFlight = false; sync(); },
                                     function(){ inFlight = false; sync(); });
          }
        });
      });
      return out;
    }

    function sync() {
      // Skip while the proxied action runs: the source button flips disabled->enabled mid-call
      // and republishing that costs two round-trips for a state nobody sees.
      if (inFlight || pending) { return; }
      pending = setTimeout(function () { pending = null; ctx.breadcrumb.set(build()); }, 0);
    }
    sync();

    var mo = new MutationObserver(sync);
    watched.forEach(function (el) {
      mo.observe(el, { attributes: true, attributeFilter: ['disabled','hidden','title'],
                       childList: true, subtree: true, characterData: true });
    });
    ctx.onCleanup(function () {
      try { mo.disconnect(); } catch (e) {}
      if (pending) { clearTimeout(pending); }
    });
    return { sync: sync };
  }

  global.UiKit = { __v: 1, actions: actions, waitIdle: waitIdle };
})(window);
```

Call sites — 20 of 22. Nineteen declare one synthetic button; one proxies real controls:

```js
// the 19-screen baseline: one Refresh in the title bar, handler defined in the screen
(function () {
  var kit = ctx.libs && ctx.libs.uikit;
  if (!kit) { return; }                 // lib failed to load -> in-page buttons stay visible
  kit.actions(ctx, [
    { key: 'refresh', icon: 'pe-7s-refresh-2', variant: 'secondary', order: 99,
      label: function () { return (typeof L === 'function') ? L('Refresh','…') : 'Refresh'; },
      run:   function () { return (typeof load === 'function') ? load() : undefined; } }
  ]);
})();

// the proxying form — `sel` points at a button that already exists in properties.html
kit.actions(ctx, [
  { sel:'.doc-gen',      key:'generate', icon:'pe-7s-magic-wand',   variant:'primary',   async:false },
  { sel:'.doc-clearsel', key:'clearsel', icon:'pe-7s-close-circle', variant:'secondary',
    watch:'.doc-bulk',   async:false },
  { sel:'.doc-delsel',   key:'delsel',   icon:'pe-7s-trash',        variant:'danger',
    watch:'.doc-bulk',   block:'.doc-page' },     // component-unique class -> safe document-wide
  { key:'refresh', icon:'pe-7s-refresh-2', variant:'secondary', order:99,
    label: function(){ return L('Refresh','…'); }, run: function(){ return load(); } }
]);
```

| | hand-written `ctx.breadcrumb.set()` | `UiKit.actions()` |
|---|---|---|
| enable/disable state | re-publish on every state change | MutationObserver mirrors the source button |
| the action's logic | duplicated: button handler **and** `onClick` | one copy, in the button handler |
| spinner | `onClick` must return a real promise | `waitIdle` derives it from `disabled` |
| page with no breadcrumb plugin | buttons vanish | `!kit` → in-page buttons stay visible |
| cost across 20 screens | 20 × ~40 lines | 20 × 6 lines |

**Traps the kit encodes that [24 §7.5](../24-html-component-studio.md) does not:**

* ⛔ **Resolve the spinner on the FIRST `disabled` mutation, not on `disabled === false`.** A delete
  that empties the list re-enables and re-disables in one synchronous block; a callback reading the
  final state never resolves and the overlay covers the screen for the full 30 s timeout.
* ⛔ **Hide a proxied button with `style.display='none'`, never `remove()`.** The screen still writes
  `btn.disabled` and reads `btn.textContent`; removing it makes those writes no-ops.
* ⚠️ **`sync()` must short-circuit while the action is in flight**, or every proxied click costs two
  extra breadcrumb publishes — each a blocking round-trip — for a state nobody sees.
* ⚠️ Still yours, from the doc: the page must carry `site.breadcrumb.plugin` or the publish succeeds
  and draws nothing; an icon-less button can never show a spinner; keys must be ASCII; ≤20 buttons; a
  publish over 64 KB yields an **empty** set.

---

## 5 · The script conventions the corpus converged on

Adoption across the 22 `main` scripts:

| element | in |
|---|---|
| top-level `try { … } catch (err) { render into a known container; console.error }` | **22/22** |
| `errText` · `arr` · `applyLocale` · `setLocale` · `L(en,alt)` · `render()` · `async load()` · `BOUND` | **22/22** |
| `q` · `esc` · `pick` · `say` · `bind` | 21/22 |
| `msgClass(el, kind)` | 20/22 |
| `async action(btnSel, msgSel, rule, input, after)` | 18/22 |
| `ctx.callRule` telemetry wrapper | 17/22 |
| `load().catch(e => <primary container>.innerHTML = <error>)` as the entry point | **22/22** |

### 5.1 The outer `try {}` — and the block-scope trick nobody documents

```js
try {                                    // ← line 1 of every script
  /* … the entire program … */
} catch (err) {                          // ← last line
  var _t = ctx.root.querySelector('.<pfx>-rows');   // the screen's PRIMARY container
  if (_t) _t.textContent = 'Script error: ' + String((err && err.message) || err);
  if (window.console) console.error('<screen>', err);
}
```

It does two jobs. **First, it converts a dead component into a visible error** — without it the runtime
logs `[Dokie] runtime error in "<identifier>"`, the screen renders its static markup and does nothing,
the failure mode [24 §3](../24-html-component-studio.md) warns about, with a clean UI.

> ✅ **Second — correction to [24d §3.5 / §10](../24d-html-component-structure.md): "two scripts
> declaring `const S` ⇒ compile error, whole program dead" is true only for TOP-LEVEL declarations.**
> The corpus's two multi-script components both declare `const BOUND`, `function esc`,
> `function errText`, `function L` and (in one) `const q` and `let TASKS` in *both* scripts, and both
> work — each script's declarations sit inside its own `try {}` block. Scripts are concatenated with
> `\n;\n` into one function body, and `const`/`let` inside a block do not collide across blocks.
> **The price:** script 2 cannot see script 1's helpers — which is exactly why preambles get
> duplicated. **The rule:** wrap every script in `try {}` *and* accept that scripts are then
> independent programs sharing only `ctx`; share deliberately through `ctx.api` or `ctx.libs.<kit>`,
> never through the implicit scope.

### 5.2 The helper layer, trimmed to what earns its place

```js
const q  = (s) => ctx.root.querySelector(s);
const qa = (s) => Array.prototype.slice.call(ctx.root.querySelectorAll(s));

function esc(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

// tolerate a bare list AND a paged envelope — a rule returning either is equally likely
const arr = (x) => Array.isArray(x) ? x : (x && Array.isArray(x.content) ? x.content : []);

// reads a row field under either spelling — §8.3 explains why both exist
function pick(o, k){
  if (!o) return undefined;
  if (o[k] !== undefined) return o[k];
  return o[k.replace(/[A-Z]/g, function(c){ return '_' + c.toLowerCase(); })];
}

// ⛔ NEVER assign className on a message strip. `el.className = 'ui-msg show ok'` DELETES the
//    class the element was FOUND by — `.<pfx>-msg` becomes `ui-msg show ok` — so the next
//    q('.<pfx>-msg') returns null and say() returns in silence. With action()'s clear-before,
//    that wipe happens on the FIRST say of every action and the one carrying the RESULT can
//    never land. An empty, success-styled alert after an HTTP 200 is exactly this line.
function msgClass(el, kind){
  if (!el) return;
  el.classList.remove('show','ok','err','warn');
  el.classList.add('ui-msg');
  if (kind) el.classList.add('show', kind);
}
function say(sel, kind, msg){
  const el = q(sel);
  if (!el) return;
  if (!msg){ msgClass(el); el.innerHTML = ''; return; }   // an empty message HIDES the strip
  msgClass(el, kind);
  el.innerHTML = esc(msg);
}

// idempotent binding: render() runs many times per mount, bind() must not stack listeners
const BOUND = [];
function bind(sel, ev, fn){
  const el = typeof sel === 'string' ? q(sel) : sel;
  if (!el || el.getAttribute('data-ui-bound')) return;
  el.setAttribute('data-ui-bound', '1');
  el.addEventListener(ev, fn);
  BOUND.push([el, ev, fn]);
}
if (ctx.onCleanup) ctx.onCleanup(function(){         // registered SYNCHRONOUSLY, before any await
  BOUND.forEach(b => { b[0].removeEventListener(b[1], b[2]); b[0].removeAttribute('data-ui-bound'); });
  BOUND.length = 0;
});
```

> ✅ **`data-ui-bound` is the answer to "how do I re-render without stacking listeners".** Rows rebuilt
> by `render()` lose the attribute with the old DOM, so their handlers re-attach; the static shell keeps
> it, so its handlers attach once. Combine with **one delegated listener on the tbody** — the
> delivery's own comment: *"Delegated on the tbody, which is in the markup. The Edit buttons are
> rebuilt by render() on every load, so binding them individually would work once and then quietly
> stop."*

### 5.3 `errText` — a server shape [24 §4.4](../24-html-component-studio.md) does not list

> ⛔ **A rule that throws does not always come back as a message. It can come back as a Java identity
> hash.** The executor sends `{"ok":false,"error":"[…ExecuteResponse$ExecutionError@33872ff2]"}` — the
> `error` field is present and its **contents** are the stringified exception object; the bridge
> faithfully rejects with `new Error("[…@33872ff2]")`. **Symptom:** the screen shows a memory address
> as an explanation. `validate` catches: no. **Fix:** test what you are about to render, not whether a
> field exists, and keep the hash as a correlation token — *"it is the only thing tying a screenshot to
> a server log line"* — never as a sentence.

```js
function errText(e){
  if (!e) return 'unknown error';
  if (typeof e === 'string') return e;
  const opaque = v => /ExecutionError|ExecuteResponse\$|@[0-9a-f]{6,}\]?$/.test(String(v == null ? '' : v));
  const pre = e.message || e.error || (e.trace && e.trace[0]);
  if (pre && !opaque(pre)) return String(pre);                      // a real message: use it
  if (pre && opaque(pre))                                           // the field IS the hash
    return L('The server failed to run this action and returned no message. Reference: ','…')
         + String(pre).replace(/^.*@/, '@').slice(0, 24);
  const raw = String(e);
  if (/ExecutionError|@[0-9a-f]{6,}\]?\s*$/i.test(raw)){            // the object IS the hash
    const tag = (raw.match(/@[0-9a-f]+/i) || [''])[0];
    return L('The rule failed without returning a message — check the server log','…')
         + (tag ? (' (' + tag + ')') : '');
  }
  return raw;
}
```

### 5.4 `action()` — the one mutating-action helper (18/22)

```js
let busy = false;

async function action(btnSel, msgSel, rule, input, after){
  // ⛔ a click arriving while an earlier load() was in flight used to be DROPPED here with no
  //    message and no button state — so the PREVIOUS action's text stayed on screen and read
  //    exactly like the new one had succeeded.
  if (busy){ say(msgSel,'err', L('Still working on the last action — try again in a moment.','…')); return; }
  busy = true;
  const btn = q(btnSel);
  if (btn) btn.disabled = true;              // ← this is ALSO the breadcrumb spinner signal (§4.1)

  // ⛔ a message must never outlive the action that wrote it. Worst sighting: an operator seeing a
  //    database error after the write had actually SUCCEEDED — the obvious reaction is to retry and
  //    double-post. Cleared FIRST so a message that fails to render leaves an EMPTY strip rather
  //    than a wrong one; re-asserted AFTER after() so a reload cannot strand a stale line.
  say(msgSel, '', '');
  try {
    const r = await ctx.callRule(rule, input) || {};
    if (r.ok === false){ say(msgSel, 'err', errText(r)); return; }
    const okMsg = r.message || 'Saved.';
    say(msgSel, 'ok', okMsg);
    if (after) await after(r);               // usually: await load()
    say(msgSel, 'ok', okMsg);
  } catch (e){ say(msgSel, 'err', errText(e)); }
  finally { busy = false; if (btn) btn.disabled = false; }
}
```

### 5.5 The entry point — nothing is `await`ed at the top level

```js
/* … definitions … bind() calls … kit.actions(ctx, […]) … */
load().catch(e => {                                   // 22/22 — launched, never awaited
  q('.<pfx>-rows').innerHTML = '<tr><td colspan="7" class="ui-empty">'
    + L('Could not load documents: ','…') + esc(errText(e)) + '</td></tr>';
});
```

> ✅ **Correction in spirit to [24 §6.3](../24-html-component-studio.md): "register every `ctx.on` /
> `ctx.onCleanup` before the first await" is a discipline you can make STRUCTURAL.** The whole script
> body is synchronous; the only `await` is inside `load()`, launched with `.catch()` and never awaited.
> **There is no first await**, so every listener, cleanup and breadcrumb declaration is registered
> before any async work and a Wicket AJAX re-render landing mid-fetch cannot strand a subscription.
> **Copy the shape: define → bind → declare actions → `load().catch(render the error)`.**

> ✅ **Correction to [24 §4.4](../24-html-component-studio.md)'s `paint()` prescription: author the
> loading state in `properties.html` and the first-load yield disappears.**
> `<tbody class="<pfx>-rows"><tr><td colspan="7" class="ui-empty">Loading…</td></tr></tbody>` — the
> server already painted it, so the script's first act can be the blocking call. 21 of 22 carry no
> `paint()` helper at all. Keep the yield for a **re-fetch** triggered by a click, which the
> button-disable plus the breadcrumb spinner covers instead.

---

## 6 · Error, empty and busy states — one slot, four sentences

The primary content region carries **one** placeholder and reuses it for every non-happy state. A
screen that can only ever show one of four strings in one place cannot get its states out of sync:
**LOADING** authored in the markup · **EMPTY** written by `render()` · **ERROR** written by
`load().catch` · **CRASH** written by the whole-script catch — all into the same element.

* **Empty states are specific and name the next action when empty is the normal first-run state**:
  *"No entries yet. Add the first one on the right."* beats *"No data"*. Error prefixes are uniform:
  `Could not load <the thing>: ` + the server's message, 20 instances, one shape.
* ⛔ **A table that cannot load has to say so IN THE TABLE.** A refusal written to a message strip
  elsewhere while the tbody keeps showing the static `Loading…` produces a table that loads for ever
  with the reason somewhere else.
  ```js
  function tableFail(sel, cols, e){
    const el = q(sel); if (!el) return;
    el.innerHTML = '<tr><td colspan="' + cols + '" class="ui-empty">'
                 + L('Could not load: ','…') + esc(errText(e)) + '</td></tr>';
  }
  ```
* **A KPI with no data renders an em dash, not zero** — `—` appears 81 times in the 22 markups. `0` in
  28 px bold is a false statement.
* **Conditional chrome uses `hidden` and is invisible in the normal case** (22/22). The test: *if a
  banner is on screen in the normal case it has stopped being a banner and become a header.*
* ⚠️ **The gap the delivery left: `aria-live` appears 0 times** against 47 `aria-pressed`. The strip
  carrying every success and refusal is never announced. Add `aria-live="polite" role="status"`.

> ⛔ **Correction to [24 §8](../24-html-component-studio.md): none of the three wait mechanisms was
> used, in four projects.** Zero `ctx.busy`, zero `icon-wait`, zero `block-wait-selector`, zero
> `wait-event`. Busy is `btn.disabled = true` in a `try/finally` and nothing else. **The projects are
> right for this shape:** one line, it is the state the breadcrumb proxy reads (§4.1), and it cannot
> leave a spinner up. **Keep `ctx.busy` only for work with no button** — a background recompute — and
> remember `opts.block` is matched document-wide, so scope it with `'#' + ctx.root.id + ' …'` or a
> component-unique class.

---

## 7 · Paging — the corpus contradicts [24c](../24c-html-data-tables-and-paging.md) head-on

> ⛔ **NOT ONE of the 22 components pages on the server, and for their data size they were right.**
> **Mechanism:** the fetch rule sets the ceiling server-side — `def page = [rowsInPage: 2000,
> pageNumber: 0]` — returns everything in one envelope, and JS filters, sorts and pages the array in
> memory. `pageNumber`/`rowsInPage` never travel from the browser. **Why:** the bridge is a
> synchronous, page-freezing XHR ([24c §2.5](../24c-html-data-tables-and-paging.md)), so server paging
> turns every page turn, sort click and keystroke into a whole-tab freeze; client paging turns them
> into a `render()`.

| | client paging (what shipped) | server paging (what 24c documents) |
|---|---|---|
| page turn / sort / filter | free, instant, no freeze | one blocking round-trip each |
| first load | one call, the whole table | one call, one page |
| breaks at | ~2 000–5 000 rows (payload + `innerHTML` cost) | never |
| filter correctness | trivial — it is JS | needs type-guarded SQL ([24c §2.4](../24c-html-data-tables-and-paging.md)) |
| total count | `all.length`, always right | needs a `count` method or `totalElements` lies ([24c §7](../24c-html-data-tables-and-paging.md)) |

✅ **Jump: client-page under ~2 000 rows with a server-side `rowsInPage` ceiling; server-page above it
and accept the freeze per interaction.** Either way **put the ceiling in the rule**, so a growing table
degrades into a truncated screen rather than a 40 MB payload — and say so in the UI when you hit it.
24c §9's "25 rows, hard ceiling 200" is the budget for the *server-paged* shape.

The pager is built by `render()`, never authored:

```js
const PAGE_SIZE = 25;
let ROWS = [], page = 0;

function render(){
  const all   = ROWS.filter(matchesFilter);
  const pages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
  if (page >= pages) page = pages - 1;
  const rows  = all.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  q('.<pfx>-rows').innerHTML = rows.length ? rows.map(rowHtml).join('')
    : '<tr><td colspan="7" class="ui-empty">' + L('Nothing matches this filter.','…') + '</td></tr>';

  const box = q('.<pfx>-pager');
  box.innerHTML = all.length
    ? '<button type="button" class="ui-btn <pfx>-prev"' + (page === 0 ? ' disabled' : '') + '>'
      + L('Previous','…') + '</button>'
      + '<span class="ui-pg-of">' + (page*PAGE_SIZE+1) + '–'
      + Math.min(all.length, (page+1)*PAGE_SIZE) + L(' of ',' / ') + all.length + '</span>'
      + '<button type="button" class="ui-btn <pfx>-next"' + (page >= pages-1 ? ' disabled' : '') + '>'
      + L('Next','…') + '</button>'
    : '';
  const pv = box.querySelector('.<pfx>-prev'), nx = box.querySelector('.<pfx>-next');
  if (pv) pv.addEventListener('click', () => { page -= 1; render(); });
  if (nx) nx.addEventListener('click', () => { page += 1; render(); });
}
```

---

## 8 · How data and commands cross the boundary

**One EXECUTION rule per screen for reads, one per mutating action.** 51 distinct rules are called from
the 22 components; **all 51 are `EXECUTION_RULE`, all 51 `ACTIVE`, all 51 resolved by display NAME**
with a `(Studio)` suffix as the namespace. Every one exists — no dangling call anywhere.

> ⚠️ **Correction to [24 §4.1](../24-html-component-studio.md): the doc prefers the identifier, the
> corpus used names — take both.** All 51 rules *have* identifiers; none is called by one. The project
> bought discoverability (`grep '(Studio)'` finds the whole surface) and paid with rename fragility.
> **Call by identifier and put the `(Studio)` marker in the rule NAME anyway.**

### 8.1 The read rule, complete

```groovy
def __trace = []
try {
    def loc = 'en_US'
    try { loc = service.global.locale.getKey() ?: 'en_US' } catch (Throwable __t) { }
    def alt = !loc.startsWith('en')
    def T   = { en, other -> (alt && other) ? other : en }

    // ⛔ EACH SOURCE IS INDIVIDUALLY GUARDED. One broken table must not blank the whole screen:
    //    the failure goes into __trace, that list comes back empty, and the rest still renders.
    def safe = { cl -> try { return cl() ?: [] }
                       catch (Throwable __t) { __trace << ('src: ' + (__t.getMessage() ?: '')); return [] } }

    def page = [rowsInPage: 2000, pageNumber: 0]      // the ceiling lives HERE, not in the browser

    return [ok: true, trace: __trace, locale: loc,
            documents:   safe { service.crud.<alias>.findAll(page) },
            partners:    safe { service.crud.<lookup>.findAll(page) },
            partnersLoc: safe { service.crud.<loc_alias>.partnerLoc() }]   // §8.4
} catch (Throwable __ex) {
    return [ok: false, error: 'EXCEPTION', trace: __trace,
            message: __ex.getClass().getSimpleName() + ': ' + (__ex.getMessage() ?: 'no message')]
}
```

> ✅ **The `safe { … }` closure is the most under-documented pattern in the bundle — nothing in
> [24 §4](../24-html-component-studio.md) or [24c §3](../24c-html-data-tables-and-paging.md) suggests
> it.** A screen fusing eight entities has eight ways to fail; without it one missing table takes the
> whole console down with an exception the operator cannot act on. With it, seven regions render, the
> eighth shows its empty state, and `trace` carries the reason. **Copy it into every multi-source
> fetch rule.**

### 8.2 The envelope

| field | meaning | JS |
|---|---|---|
| `ok: true/false` | did the rule agree to answer | `if (d.ok === false) throw new Error(errText(d))` |
| `error: '<CODE>'` | machine-readable refusal (`FORBIDDEN`, `NOT_FOUND`, `NEGATIVE`, `NOTHING`, `EXCEPTION`) | rarely branched on; the code exists for the log |
| `message: '<sentence>'` | **already localized by the rule** via `T(en, alt)` | shown verbatim |
| `trace: [ … ]` | per-source failures that did not stop the answer | logged, occasionally surfaced |
| `locale: 'en_US'` | what the server says the language is | `setLocale(d.locale)` |
| `<entity>: [ … ]` | one key per list, camelCase | `arr(d.documents)` |
| `<entity>Loc: [ … ]` | localization side channel | folded in by suffix (§8.4) |

### 8.3 The write rule, and the case trap

```groovy
def id = context.data.getAttr('entityId')
if (id == null || (id as String).trim().isEmpty())
    return [ok:false, error:'NO_ENTITY', message: T('Choose a record.','…')]
def row = service.crud.<alias>.get(id as Integer)
if (row == null) return [ok:false, error:'NOT_FOUND', message: T('That record no longer exists.','…')]

// ⛔ A blank box means "leave it alone", NOT "set it to zero" — zero is a real value here and would
//    silently take a working record back to 0.
def dec = { k -> def raw = context.data.getAttr(k)
                 (raw == null || (raw as String).trim().isEmpty()) ? null : new BigDecimal(raw as String) }

def patch = [id: id as Integer], bad = []
def put = { col, val, label -> if (val == null) return
                               if (val < 0) { bad << label; return }
                               patch[col] = val }
put('target_value_per_item', dec('targetValuePerItem'), T('target value','…'))   // ← snake_case column

if (!bad.isEmpty())    return [ok:false, error:'NEGATIVE',
                               message: T('These cannot be negative: ','…') + bad.join(', ')]
if (patch.size() <= 1) return [ok:false, error:'NOTHING', message: T('Nothing to save.','…')]
service.crud.<alias>.update(patch)
return [ok:true, message: T('Saved.','…')]
```

> ⛔ **READS ARE camelCase, WRITES ARE snake_case — and the same rule does both.** The executor
> camelCases every JDBC column label on the way out
> ([24c §2.3](../24c-html-data-tables-and-paging.md)), but `create`/`update` take a map keyed by the
> **real column names**. The browser reads `row.targetValuePerItem`; the rule writes
> `target_value_per_item`, for the same field. **Symptom:** a save that silently drops a field — the key
> never matched a column and the executor has nothing to complain about. **Fix: keep the three
> spellings side by side in ONE table in the component, so they cannot drift.**
> ```js
> // read key             editor selector    rule input key       decimals
> const FIELDS = [
>   ['targetValuePerItem', '#<pfx>-target',    'targetValuePerItem', 2],
>   ['unitRate',           '#<pfx>-rate',      'unitRate',           2],
>   ['retentionDays',      '#<pfx>-retention', 'retentionDays',      0]
> ];
> FIELDS.forEach(f => { input[f[2]] = q(f[1]).value; });                     // build the payload
> FIELDS.forEach(f => { q(f[1]).value = numOrNull(pick(v, f[0])) ?? ''; });  // fill the editor
> ```

> ⚠️ **Correction to [24c §2.3](../24c-html-data-tables-and-paging.md)'s "read the camelCase key; do
> not try both cases": 21 of 22 carry a dual-case `pick()` anyway, and one channel proved them right
> (§8.4).** CamelCase is correct for CRUD rows; a rule-built map, a side-channel method or a `jsonb`
> projection can hand you either. Keep `pick()` — one function — and keep `FIELDS` so the write side
> never guesses.

### 8.4 Localization — the wire key, the side channel, the subtree trap

> ⛔ **The export declares the column `localized`; the WIRE sends `localize`.**
> [24c §2.3](../24c-html-data-tables-and-paging.md) states the rename; the corpus confirmed it on a
> capture — *"29/30/38 occurrences of `localize` and zero of `localized` in three payloads, with the
> translations present and correct inside them; the export declares `localized` in all 112 DTOs, so
> only a capture could show this."* **Read both:** `pick(row,'localize')`, falling back to
> `pick(row,'localized')`.

When the column never reaches the browser — a `jsonb` DTO arriving empty — add a **side channel**: a
second CRUD with one tiny method per entity returning `{rowId, loc}`, named `<key>Loc` in the payload
and folded in **by suffix**, so a list added to the rule later needs no JS change.

```js
function applyLocPatch(d){
  if (!d) return d;
  Object.keys(d).forEach(function(k){
    if (k.length < 4 || k.slice(-3) !== 'Loc') return;
    var base = k.slice(0, -3), rows = d[base];
    if (rows && !Array.isArray(rows) && Array.isArray(rows.content)) rows = rows.content;
    if (Array.isArray(rows) && locList(d[k]).length) mergeLoc(rows, d[k]);
  });
  return d;
}
// ⛔ A single-row side channel is a BARE OBJECT, not an array — the *Loc producers declare
//    returnsArray:false, and arr() returns [] for that because it only unwraps `.content`.
function locList(v){
  if (Array.isArray(v)) return v;
  if (v && Array.isArray(v.content)) return v.content;
  if (v && typeof v === 'object') return [v];
  return [];
}
```

The label resolver never falls back to a database code: try the **active** locale, then the tenant
default, then **any** language — a label in the wrong language still beats a storage key — and only
when the row carries no localization at all, humanise the key itself.

```js
// ✅ a storage key, not a label: no spaces, no capitals, ascii only -> 'source_type' -> 'Source Type'
function dimHuman(v){
  var s = String(v == null ? '' : v);
  if (!/^[a-z][a-z0-9_]*$/.test(s)) return s;
  return s.split('_').map(w => w ? (w.charAt(0).toUpperCase() + w.slice(1)) : w).join(' ');
}
```

> ⛔ **The locale machine in the corpus is an anti-pattern you must NOT copy —
> [24 §9](../24-html-component-studio.md) is right about why.** All 22 components sniff the page
> (`?lng=` → cookie → `<html lang>`), swap `data-<lang>` attributes, inject a `__loc` field into every
> outbound call, and let the server only *confirm* a language. Three layers, in 22 components and 136
> rules — and the whole apparatus exists because every rule read `context.data.localeKey`, which is
> **always `null`**. **Fix the rule** (`service.global.locale.getKey()`) and drive labels from one
> message map. If you inherit a project with `__loc` in it, that is the tell. **Keep exactly one thing
> from it:** the confirm-only asymmetry — *a default value is not an answer.* Treat the fallback locale
> as **unknown**, never as evidence of the default language.

> ⛔ **`el.textContent = t` on a container is a subtree delete wearing a string assignment** — and this
> applies to any translate-in-place routine, `data-*` or not. In the corpus every conditional-requirement
> marker nested in a translated `<label>` was deleted on the first draw, including one added eleven
> modules earlier that had never once rendered. **A translation key labels a piece of TEXT, not a
> subtree: retranslate this element's own text nodes and leave children alone**, and call the routine
> at the end of every `render()` (22/22 do).
> ```js
> if (el.firstElementChild){
>   let done = false;
>   for (let n = el.firstChild; n; n = n.nextSibling){
>     if (n.nodeType !== 3) continue;                 // Node.TEXT_NODE
>     if (done){ n.nodeValue = ''; continue; }        // collapse any later stray text
>     n.nodeValue = t; done = true;
>   }
>   if (!done) el.insertBefore(el.ownerDocument.createTextNode(t), el.firstChild);
>   return;
> }
> el.textContent = t;
> ```

### 8.5 Two escape hatches

**Attachments.** There is no upload API in a rule, so files go base64 through `ctx.callRule` into a
`jsonb` column, capped client-side (3 145 728 bytes) and returned the same way; the field stores
`att:<id>`, never the bytes. Read with `FileReader.readAsDataURL` and `split(',')[1]`; return via
`atob` → `Uint8Array` → `Blob` → object URL, revoked on a timer. ⚠️ The bridge is a blocking XHR, so a
3 MB upload freezes the tab for the whole round-trip — **cap hard and state the cap in the UI**.

**CSV** is built entirely client-side, and you **export `visible()`, not `ROWS`** — the operator
expects the file to match the screen. Quote only when the value contains a delimiter, join with `;`
(spreadsheet-locale safe), and prepend a BOM (`'﻿' + text`) so a spreadsheet reads UTF-8.

---

## 9 · The six component types

T1–T5 partition A's 22 (15 + 4 + 1 + 1 + 1); T6 is cross-cutting and appears inside 13 of them.

| | type | n | shape |
|---|---|---|---|
| **T1** | **Entity console** — KPI strip + filter bar + list + inline editor | **15** | one `load()`, one filter object, `render()` off an in-memory array; the editor is a sibling toggled with `hidden`, not a modal |
| **T2** | **Report screen** — tabs over read-only panels | 4 | one rule per tab, fetched **lazily on first show**, cached in a module variable, invalidated by setting it to `null` |
| **T3** | **Dashboard shell** — hand-built regions around stock chart plugins | 1 | the only node in 3 047 with `<plugin>` tags inside a studio-active component |
| **T4** | **Log / audit console** — client paging + master-detail | 1 | §7; its pager is reused inside one T1 |
| **T5** | **Printable document** — paper preview + `@media print` | 1 | see the print trap below |
| **T6** | **"Open source" affordance** beside every lookup select | 13 | §9.2 |

**T1 sub-patterns worth naming.** *KPI-as-filter*: each tile is a `<button>` with `data-kpi` and
`aria-pressed`, and clicking it toggles a filter key — one control, double duty, state announced.
*`hidden` panels, not modals*: the editor and the bulk bar are siblings toggled with `hidden` — no
modal library, no z-index, no focus trap, and the kit's `isHidden()` reads the same attribute to keep
the breadcrumb in sync. *One grid rule for the whole form*:
`display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr))`, responsive with no breakpoints.

> ⛔ **An edit form that looks like a create form destroys the record.** From the post-mortem, seen
> four times: *"a control opened a panel — or looked like a create form — while the action lived
> elsewhere. An operator presses it, sees nothing happen, and concludes the button is broken. In the
> Clone case they then edit the form they are still looking at, which is the source record, and destroy
> it."* Copy the guard literally:
> ```js
> // Save is UPDATE-ONLY: it requires an id, fetches that row and patches it. Typing a new
> // reference into "Document ref" and saving RENAMES the document you are looking at.
> const was = cur ? String(pick(cur,'ref') || '') : '';
> const now = String(q('#<pfx>-ref').value || '').trim();
> if (cur && was && now && now !== was){
>   say('.<pfx>-edit-msg','err', L('This would rename ' + was + ' to ' + now
>       + ', not create a new document — there is no new-document mode here.','…'));
>   return;
> }
> ```

> ✅ **Lazy tabs (T2) are the correct response to a blocking bridge** — one call per *visible* panel;
> fetching both up front freezes the tab twice. `setTab()` runs from a click handler, so the lazy fetch
> needs an explicit `.catch(e => tableFail(...))`: an unhandled rejection there is invisible.
> ⛔ **Report screens are where theme discipline decays** — A's five carry 14–30 bare hex literals in
> their `"*"` block against 7 in the twelve consoles, because they were written before the alias layer
> existed. **Audit the oldest screens of an inherited bundle first.**

> ✅ **T3 is the only node in 3 047 that exercises
> [24b §7.1](../24b-html-composition-and-plugin-tags.md) (a chart grid inside a hand-built shell), and
> the safety rule that makes it work is not in 24b: the script writes ONLY into empty containers it
> owns, and never into an ancestor of a `<plugin>`.** There is not one `ctx.setHtml`, `ctx.showHtml`
> or `root.innerHTML =` in the whole project, so the failure of
> [24 §6.4](../24-html-component-studio.md) / [24b §8.5](../24b-html-composition-and-plugin-tags.md) —
> embedded plugin vanishes, only a full reload brings it back — cannot occur. **Enforce it as a naming
> rule: a container the script writes to gets a `<pfx>-` class and holds nothing else; `<plugin>` tags
> live in their own cells, and the JS-owned regions and the server-owned regions are separate blocks
> of markup.**

**Micro-charts without a library** (T3 and one T1): a flex row of `<span>`s with a percentage height —
`'<span style="height:' + Math.max(2,(v/max)*100) + '%">'` over
`.ui-sparkbars{display:flex;align-items:flex-end;gap:3px;height:56px} .ui-sparkbars>span{flex:1;background:var(--ui-accent);min-height:2px}`.
✅ Right answer for a sparkline, a meter, a segmented bar and a "next N periods" strip: zero library
bytes, themed by the same tokens, and `style="height:…%"` is **layout**, which
[24a §7.3](../24a-theming-and-dark-mode.md) permits — colour never goes in `style=`. Reach for a chart
library, or better a `chart.js.plugin` child, only when you need axes.

### 9.1 The print trap (T5)

> ⛔ **`@media print` inside `css.byTheme` CANNOT hide the application shell.** The scoper recurses
> into `@media` and prefixes every selector with `#dokie-plug-<id>`
> ([24a §5.2](../24a-theming-and-dark-mode.md)); a leading `body`/`html`/`:root` is *replaced* by the
> wrapper, so `body > *:not(#me){display:none}` becomes a rule about your own wrapper and does nothing.
> **Symptom:** the printed page carries the left nav, the breadcrumb bar and the header. Your
> `@media print` can only hide things **inside** your component — which is enough for
> `.<pfx>-chrome{display:none!important}`, `page-break-inside:avoid` on rows, and
> `print-color-adjust:exact` on shaded headers.
> **Fix for anything a reader sends outside the company: write a clean document into a blank window.**
> ```js
> const w = window.open('', '_blank');
> if (!w) return;                                   // popup blocked
> w.document.write('<title>' + esc(ref) + '</title>'
>   + '<body style="font:14px/1.5 system-ui;padding:32px">'
>   + '<h2>' + esc(ref) + '</h2>' + body + '</body>');
> w.document.close(); w.focus(); w.print();
> ```
> ⚠️ Better still when the layout is fixed: render server-side through the platform's PDF templates
> ([15](../15-pdf-and-mail.md)) — with the delivery's caveat that **the default PDF font may carry no
> glyphs for a non-Latin locale**, in which case print is the only path until a font is registered.

### 9.2 T6 — the seam between a studio console and the generated pages

This exists because of an expensive failure. From the post-mortem: *"the screen shipped with three
working tabs and was reported broken anyway, in the plainest possible terms — 'there are 3 tabs here
and I can't find the place to add an item.' Nothing was failing. The feature had been specified, built
and verified one level too late: every acceptance test began 'given an item…', and the step that
produces one was owned by no requirement.* ***A fixture is a decision about who creates the row, made
silently.***"

The fix: **beside every `<select>` backed by a lookup table, a small icon button that opens the stock
CRUD page maintaining that table, in a new tab; when the user comes back, reload.**

```html
<span class="<pfx>-field">
  <select class="ui-input" id="<pfx>-partner"></select>
  <button type="button" class="<pfx>-manage" data-manage="<pfx>-partner" title="Open source">…svg…</button>
</span>
```

```js
// Paths resolve through the rendered nav, so a link always lands where the menu entry lands.
var SELF_PATH  = "<this page's alias>";
var MANAGE_URL = { "<pfx>-partner": "partners", "<pfx>-src": "database/dim/source_types" };
var awaiting = false;

function base(){                       // strip this page's alias off the current path
  var path = (window.location && window.location.pathname) || '';
  var i = path.indexOf(SELF_PATH);
  if (i >= 0) return path.slice(0, i);
  return path.charAt(path.length-1) === '/' ? path : (path + '/');
}
function open_(fieldId){
  var rel = MANAGE_URL[fieldId]; if (!rel) return;
  var url = base() + rel, w = null;
  try { w = window.open(url, '_blank'); } catch (e) { w = null; }   // a NEW TAB: navigating away
  if (!w){ window.location.href = url; return; }                    //   discards half-typed input
  awaiting = true;                                                  // popup blocked -> same tab
}

// ⛔ Depends on NOTHING but ctx — written as a self-contained IIFE because screens do not share one
//    helper set (some bind with bind(), some with on()) and calling the wrong one throws a
//    ReferenceError that takes the WHOLE script down.
(function(){
  var root = null;
  try { root = ctx.root && ctx.root.querySelector ? ctx.root.querySelector('.<pfx>-page') : null; } catch(e){}
  if (!root || root.getAttribute('data-manage-bound')) return;
  root.setAttribute('data-manage-bound','1');
  var onClick = function(e){
    var a = e.target && e.target.closest ? e.target.closest('.<pfx>-manage') : null;
    if (!a) return;
    if (e.preventDefault) e.preventDefault();
    open_(a.getAttribute('data-manage'));
  };
  root.addEventListener('click', onClick);
  if (ctx.onCleanup) ctx.onCleanup(function(){
    root.removeEventListener('click', onClick); root.removeAttribute('data-manage-bound'); });
})();

var onReturn = function(){                     // came back from the other tab -> refresh the lists
  if (!awaiting) return;
  awaiting = false;
  try { if (typeof load === 'function') load().catch(function(){}); } catch (e) {}
};
try {                                          // ⚠️ MUST go through onCleanup or the listener
  window.addEventListener('focus', onReturn);  //    survives every teardown
  if (ctx.onCleanup) ctx.onCleanup(function(){ window.removeEventListener('focus', onReturn); });
} catch (e) {}
```

> ✅ **Correction to [24 §1.2](../24-html-component-studio.md) and
> [24b §9](../24b-html-composition-and-plugin-tags.md): the doc's "keep the boring page as well" is
> right, and the corpus proves it by omission.** The consoles **replaced** the table — not one
> `crud.table.plugin` on any of the 21 studio pages. Every future field is therefore a code edit, and
> there is no boring page left to run the business when the console breaks. **Keep the generated page
> for master data, and link to it from the exact control that needed it.**
> **The obligation to write down:** *for every list a screen reads, name the rule (or the page) that
> writes it. Where neither exists, the list is a dependency on seed data and the feature is incomplete
> regardless of how well the screen behaves.*

---

## 10 · Self-instrumentation, and what it costs

17 of 22 open by **monkey-patching `ctx.callRule`** so every server interaction is timed and written to
a log table, with no logging code in the screen bodies. Idempotent, page-global, and it must never
break a screen.

```js
(function(){
  try {
    if (!ctx || typeof ctx.callRule !== 'function') return;
    var SRC = '<component identifier>';
    if (!ctx.__uiLogRaw) ctx.__uiLogRaw = ctx.callRule.bind(ctx);   // keep the ORIGINAL
    var raw = ctx.__uiLogRaw;
    function write(level, action, message, detail, ms){
      if (action === 'Log UI Event (Studio)' || action === '<Screen> Data (Studio)') return;
      try { raw('Log UI Event (Studio)', { level:level, source:SRC, action:action,   // never log the
             message: trim(message,2000), detail: trim(detail,8000), durationMs: ms, //  logger, or the
             url: (window.location && window.location.pathname) || '',               //  table fills
             build: (ctx.root.querySelector('.<pfx>-build')||{}).textContent || '' });//  with itself
      } catch (e) { /* logging must never break a screen */ }
    }
    if (ctx.__uiLogWrapped) return;                                 // wrap ONCE per instance
    ctx.__uiLogWrapped = true;
    ctx.callRule = function(name, input){
      var t0 = Date.now(), pr;
      try { pr = raw(name, input); }
      catch (e) { write('error', name, String((e && e.message) || e), {input:input}, 0); throw e; }
      if (!pr || typeof pr.then !== 'function') return pr;
      return pr.then(function(r){
        var ms = Date.now() - t0;
        if (r && r.ok === false) write('error', name, (r.message || r.error || 'refused'),
                                       {input:input, result:r}, ms);
        else                     write('info',  name, (r && r.message) || '', {input:input}, ms);
        return r;
      }, function(e){ write('error', name, String((e&&e.message)||e), {input:input}, Date.now()-t0);
                      throw e; });
    };
  } catch (e) { /* never break a screen */ }
})();
```

The collector rule swallows its own failures on purpose — `return [ok:true, logged:false, why: …]` in
its `catch`, because *a logger that throws makes every screen worse*.

> ⚠️ **Price it: every logged interaction is a SECOND blocking round-trip**, so a wrapped screen
> freezes the tab twice per action. **Jump: wrap only the `error` outcomes** — the rejection path and
> `ok === false` — unless you are actively debugging a delivery.
> ✅ **Keep the rest:** the `__uiLogWrapped` idempotence flag (scripts share one instance and the block
> is duplicated in both scripts of the multi-script components), the never-log-the-logger filter, the
> try/catch around the whole wrapper, and the **build stamp** in the markup —
> `<div class="<pfx>-build">build 2026-08-31 23:05</div>`, substituted at build time, because several
> rounds of "that fix isn't there" turned out to be an import that had not been applied yet and there
> was no way to tell by looking.

---

## 11 · The CSS contract, in one page

Five `byTheme` keys on 22/22, and **none of them is `Standard`**: the `"*"` block *is* the light
design, and the four dark skins get a patch redefining **only the alias variables**.

```css
/* css.byTheme["*"] — head of every component.
   The 4 dark skins define --background/--current-line/--foreground/--comment on :root; Standard
   does NOT. So var(--current-line, <light literal>) resolves to the theme surface on a dark skin
   and to the light literal on Standard. ONE "*" block, five skins. :root is rewritten by the
   scoper to this instance's wrapper, so the tokens land exactly on the component root. */
:root{
  --ui-surface:      var(--current-line, #ffffff);                /* cards, inputs     */
  --ui-surface-sunk: var(--background,   #f3f4f6);                /* th, wells, tracks */
  --ui-fg:           var(--bs-body-color, #1f2937);
  --ui-fg-strong:    var(--foreground,    #111827);
  --ui-mut:          var(--foreground-muted, var(--comment, #5b6472));
  --ui-bd:           var(--bs-border-color, #e5e7eb);
  --ui-bd-soft:      var(--bs-border-color-translucent, #f1f5f9);
  --ui-accent: #047857; --ui-accent-fg: #ffffff;                  /* light values,     */
  --ui-ok: #047857; --ui-warn: #92400e; --ui-bad: #b91c1c;        /*   patched per dark */
  --ui-info: #1e40af; --ui-neutral: #4338ca;                      /*   skin below       */
  --ui-shadow: 0 1px 2px 0 rgb(0 0 0/.18);
}
```

```css
/* ["Dracula"] == ["Forest"] == ["Dark"] == ["Dark Blue"] — byte-identical, 644 B. MEASURED values:
   every pair is >=4.5:1 on all four dark skins. The accent flips to a LIGHT fill with a DARK label
   — a white label on a saturated fill cannot reach 4.5:1. */
:root{ --ui-ok:#6ee7a8; --ui-warn:#fcd34d; --ui-bad:#fca5a5; --ui-info:#93c5fd;
       --ui-neutral:#c4b5fd; --ui-accent:#6ee7a8; --ui-accent-fg:#06281c; }
```

> ✅ **A legitimate refinement of [24a §6](../24a-theming-and-dark-mode.md) — copy it.** 24a's default
> is one `"*"` block, with per-skin blocks only for images, shadows, gradients and one-off rescues. The
> fifth case is real and common: **the platform's semantic tokens (`--green`/`--red`/`--cyan`/
> `--purple`) collapse to nearly the same hue on two of the four dark skins**, so a status palette
> bound to them stops carrying state and measures 2–3:1 on the card surface. **Do not bind status
> colour to a platform token at all** — put your own `--<pfx>-ok/-warn/-bad/-info` aliases in `"*"`
> with light values and re-declare *only those six lines* in each dark key: four copies of six
> declarations, not four copies of a stylesheet.
> ⚠️ The `"*"` block then carries ~7 bare hex literals and `validate` WARNs on every component. Those
> seven are the alias definitions and are correct; **read the warning, then check the rest has none.**

Two more facts: **status tints are `rgba()` over the surface**, never a token — `rgba(220,38,38,.16)`
reads on a `#ffffff` card and on a `#101b2c` one, the cheapest five-skin-safe tint there is; and
**every `@keyframes` is prefixed**, because keyframe names are page-global. 120 of the 940 distinct
selectors appear in ≥20 of the 22 blocks and 107 lines are byte-identical in all 22 — one design
system, copy-pasted 22 times. **Ship it as a CSS asset on the kit lib instead.**

---

## 12 · The working skeleton

**1 · node, gate, asset**

```bash
python3 mrjun.py node add --parent "<Layout slot>" --plugin nct.html.plugin \
    --name "<Screen> UI" --identifier <pfx>_<screen>_ui --project work
python3 mrjun.py roleaccess set <pfx>_<screen>_ui --public false \
    --rolegroup "<Group>:view" --project work
python3 mrjun.py asset add studio/ui-kit/ui-kit.js ./ui-kit.js --project work
python3 mrjun.py node set-studio <pfx>_<screen>_ui --json @studioModel.json --project work
```

**2 · `properties.html`** — one `<pfx>-` prefix on every JS target, the loading state already painted,
`<plugin>` slots (if any) outside every container the script writes:

```html
<div class="<pfx>-page">
  <div class="ui-head">
    <h1 class="ui-title">Documents</h1>
    <div class="ui-actions">
      <span class="ui-pill ui-p-bad <pfx>-badge">—</span>
      <button type="button" class="ui-btn <pfx>-export">Export CSV</button>
    </div>
  </div>

  <div class="ui-kpis <pfx>-kpi-row">
    <button type="button" class="ui-kpi <pfx>-kpi" data-kpi="open" aria-pressed="false">
      <div class="ui-kpi-l">OPEN</div><div class="ui-kpi-v <pfx>-k-open">—</div>
    </button>
  </div>

  <div class="<pfx>-filters">
    <input class="ui-input <pfx>-search" type="search" aria-label="Search" placeholder="Search …">
    <span class="<pfx>-field">
      <select class="ui-input <pfx>-f-partner"><option value="">All partners</option></select>
      <button type="button" class="<pfx>-manage" data-manage="<pfx>-f-partner" title="Open source">…</button>
    </span>
    <button type="button" class="ui-chip <pfx>-f-clear">Clear</button>
  </div>

  <div class="ui-card">
    <div class="<pfx>-bulk" hidden>
      <span class="<pfx>-bulk-n"></span>
      <button type="button" class="ui-btn ui-btn-primary <pfx>-bulk-ok">Approve</button>
      <span class="ui-msg <pfx>-bulk-msg" role="status" aria-live="polite"></span>
    </div>
    <div class="ui-tablewrap"><table class="ui-table">
      <thead><tr><th class="<pfx>-cbcol"><input type="checkbox" class="<pfx>-all" aria-label="Select all"></th>
        <th>REF</th><th>PARTNER</th><th class="ui-r">TOTAL</th></tr></thead>
      <tbody class="<pfx>-rows"><tr><td colspan="4" class="ui-empty">Loading…</td></tr></tbody>
    </table></div>
    <div class="ui-pager <pfx>-pager"></div>
  </div>

  <div class="ui-card <pfx>-editor" hidden>
    <div class="<pfx>-grid">
      <div><label class="ui-lab" for="<pfx>-target">Target value</label>
           <input class="ui-input" id="<pfx>-target" type="number" step="0.01" min="0"></div>
    </div>
    <div class="ui-msg <pfx>-edit-msg" role="status" aria-live="polite"></div>
    <div class="<pfx>-editor-acts">
      <button type="button" class="ui-btn ui-btn-primary <pfx>-save">Save</button>
      <button type="button" class="ui-btn <pfx>-cancel">Close</button>
    </div>
  </div>

  <div class="<pfx>-build" title="Build of the imported export">build …</div>
</div>
```

**3 · `scripts[0].code`** — the whole program, in the one order that works:

```js
try {
/* helpers §5.2–5.4 · labels driven by d.locale §8.4 · pager §7 · T6 IIFE §9.2 */

let ROWS = [], LOOKUPS = [], sel = null, page = 0;
const picked = new Set();
const F = { text:'', partner:'', kpi:'' };                     // ONE filter object

function visible(){
  return ROWS.filter(function(r){
    if (F.kpi === 'open' && !isOpen(r)) return false;
    if (F.partner && String(pick(r,'partnerId')) !== F.partner) return false;
    if (F.text && (String(pick(r,'ref')||'') + ' ' + labelOf(r)).toLowerCase()
                    .indexOf(F.text.toLowerCase()) < 0) return false;
    return true;
  });
}

async function load(){
  applyLocale();
  const d = await ctx.callRule('<Screen> Data (Studio)', {}) || {};   // ONE call, whole screen
  applyLocPatch(d);
  if (d.ok === false) throw new Error(errText(d));
  setLocale(d.locale);
  ROWS = arr(d.documents); LOOKUPS = arr(d.partners);
  fillSelects(); render();
  if (sel && !byId(ROWS, sel)) { sel = null; q('.<pfx>-editor').hidden = true; }
}

/* wiring: ALL synchronous, ALL before load() */
bind('.<pfx>-search',   'input',  e => { F.text = e.target.value; page = 0; render(); });
bind('.<pfx>-f-partner','change', e => { F.partner = e.target.value; page = 0; render(); });
bind('.<pfx>-f-clear',  'click',  () => { Object.keys(F).forEach(k => F[k]=''); syncControls(); render(); });
bind('.<pfx>-kpi-row',  'click',  e => {                       // delegated: tiles are filters
  const b = e.target.closest('.<pfx>-kpi'); if (!b) return;
  F.kpi = (F.kpi === b.dataset.kpi) ? '' : b.dataset.kpi; render();
});
bind('.<pfx>-rows', 'click', function(e){                      // delegated: rows are rebuilt
  const cb = e.target.closest('.<pfx>-cb');
  if (cb){ cb.checked ? picked.add(cb.dataset.id) : picked.delete(cb.dataset.id); render(); return; }
  const tr = e.target.closest('tr[data-id]');
  if (tr){ openEditor(tr.dataset.id); }
});
bind('.<pfx>-save', 'click', () =>
  action('.<pfx>-save', '.<pfx>-edit-msg', 'Save <Entity> (Studio)', payload(), async () => { await load(); }));
bind('.<pfx>-bulk-ok', 'click', () =>
  action('.<pfx>-bulk-ok', '.<pfx>-bulk-msg', 'Bulk Approve Documents (Studio)',
         { documentIds: Array.from(picked) }, async () => { picked.clear(); await load(); }));

(function(){ var kit = ctx.libs && ctx.libs.uikit; if (!kit) return;
  kit.actions(ctx, [{ key:'refresh', icon:'pe-7s-refresh-2', variant:'secondary', order:99,
                      label: () => L('Refresh','…'), run: () => load() }]); })();

load().catch(e => { q('.<pfx>-rows').innerHTML =
  '<tr><td colspan="4" class="ui-empty">' + esc(errText(e)) + '</td></tr>'; });

} catch (err) {
  var _t = ctx.root.querySelector('.<pfx>-rows');
  if (_t) _t.textContent = 'Script error: ' + String((err && err.message) || err);
  if (window.console) console.error('<screen>', err);
}
```

**4 · the rules** — `<Screen> Data (Studio)` (§8.1) plus one per mutating action (§8.3); all
`EXECUTION_RULE`, all `ACTIVE`, locale from `service.global.locale.getKey()`.

**5 · the gates**

```bash
python3 mrjun.py validate --project work                     # model parses; libNames resolve; paths relative
python3 mrjun.py list rules --project work | grep '(Studio)' # every called rule exists
python3 mrjun.py crud verify --db "<conninfo>" --project work
python3 mrjun.py pack work app.mrjun
```

then **live-render** and check, in this order: the component draws · the breadcrumb button appears and
acts · the console is clean · the page source contains no `<!-- dokie: … -->` · the screen reads on
**Dark** as well as Standard · a deliberate rule failure shows a sentence, not a hash · the empty state
renders when the filter matches nothing · `ctx.libs.uikit` is not `undefined` (a 403 on a vendored
asset is silent and the runtime runs your code with `{}` libs).

---

## 13 · Obligations, and the audit script

Distilled from eighteen scripted runs against a live system. Every one is a class of defect that
**survived code review and every offline gate**.

1. **A field that cannot be computed must say so, not disappear.** Removing a field is not a message.
2. **A disclosure that does not disclose reads as a dead button.** A control that *opens* something
   must say what it opened, bring it into view, and never share a caption with the control that *acts*.
3. **A guard must test the absence that actually occurs.** `startDate == null` does not guard a form —
   an untouched input arrives as `""`; `!CACHE` conflates *never fetched* with *failed*, which made one
   load failure permanent. Absent, empty and failed are three conditions, not one.
4. **An unforced value crossing a string boundary serialises as its object** — an exception as its
   identity hash (§5.3), an object as `[object Object]`. Force at the source.
5. **A sweep anchored on a name is not a sweep, and a fix applied where you happened to look is not a
   fix.** Enumerate the surface programmatically — every script on every component — then assert over
   that enumeration.

```python
# every nct.html.plugin node in an unpacked export, classified
import json, re
def walk(node, page, acc):
    if node.get('pluginName') == 'siteMapPage':
        page = node.get('alias')
    if node.get('pluginName') == 'nct.html.plugin':
        p = node.get('properties') or {}
        acc.append({'page': page, 'name': node.get('name'), 'identifier': node.get('identifier'),
                    'html': (p.get('html') or {}).get('stringValue') or '',
                    'sm':   (p.get('studioModel') or {}).get('stringValue') or ''})
    for c in node.get('children') or []:
        walk(c, page, acc)

acc = []
walk(json.load(open('branches.json'))[0]['rootContent'], None, acc)

def active(sm):
    if not sm.strip() or sm.strip() == 'null': return False
    m = json.loads(sm)
    css = (m.get('css') or {}).get('byTheme') or {}
    return bool(m.get('libs') or m.get('docs') or m.get('scripts')) \
        or any((v or '').strip() for v in css.values())

print('html nodes       :', len(acc))
print('studio-ACTIVE    :', sum(1 for a in acc if active(a['sm'])))
print('empty studioModel:', sum(1 for a in acc if a['sm'].strip() and not active(a['sm'])))
print('inline <style>   :', sum(1 for a in acc if re.search(r'<style', a['html'], re.I)))  # must be 0
print('colour in style= :', sum(1 for a in acc if re.search(r'style="[^"]*(?:color|background)', a['html'])))
```

The three numbers that matter: **studio-ACTIVE** (the hand-built surface you now own), **inline
`<style>`** (must be zero — an unscoped `<style>` in an html property restyles the whole application),
and **colour in `style=`** (each one needs a per-theme `!important` rescue and can never be themed).

---

## 14 · Where four deliveries contradict the library, consolidated

| # | doc says | four deliveries did | jump |
|---|---|---|---|
| 1 | [24d §2](../24d-html-component-structure.md): split above ~150 markup / ~200 script lines; ≤6 docs; four single-responsibility scripts | **one document, one script, 22/22**; median 42 kB of JS in one `main`; zero `docs[]`, zero `<include>` in 3 047 nodes | **The doc is right and the project paid for it. Split** — and remember a screen is the union of its scripts, so every sweep must enumerate all of them |
| 2 | [24d §3.5](../24d-html-component-structure.md): two scripts declaring `const S` ⇒ compile error, whole program dead | both multi-script components declare the same `const`/`function` names in **both** scripts and work | **The rule holds only at top level.** A per-script `try{}` gives each its own block scope — at the price that scripts can no longer see each other's helpers |
| 3 | [24c](../24c-html-data-tables-and-paging.md): server-side paging is the contract | **client paging over a fully-fetched array; the ceiling (`rowsInPage: 2000`) in the rule** | **Client-page under ~2 000 rows** — the bridge is a blocking XHR and every server page turn freezes the tab. Server-page above it. Ceiling in the rule either way |
| 4 | [24c §2.3](../24c-html-data-tables-and-paging.md): read the camelCase key, do not try both cases | 21/22 carry a dual-case `pick()` | **Keep `pick()`** — CRUD rows are camelCase, but a rule-built map or a side channel can be either, and writes are snake_case. Declare all three spellings in one `FIELDS` table |
| 5 | [24 §8](../24-html-component-studio.md): three wait mechanisms — `icon-wait`, breadcrumb `wait`, `ctx.busy` | **none of the three**, in four projects; busy = `btn.disabled = true` in try/finally | **The projects are right for this shape.** One line, it is the state the breadcrumb proxy reads, and it cannot leave a spinner up. Keep `ctx.busy` for work with **no** button |
| 6 | [24 §4.1](../24-html-component-studio.md): prefer the rule identifier | **all 51 calls by display name**, `(Studio)` as a namespace | **Call by identifier; keep the `(Studio)` marker in the name.** Both, at no cost |
| 7 | [24 §4.4](../24-html-component-studio.md): gate the node **and** the rule | **`publicReadAccess:true` on 22/22**; all gating in the rules | **Do both.** A public studio node also forces the CSS to resolve as `Dark` for anonymous viewers |
| 8 | [24 §4.4](../24-html-component-studio.md): the envelope is `{ok:false,error:"…"}` or a serialization error | a third shape exists — `error` holding a Java identity hash | **Add the opaque branch to `errText`**; keep the hash as a correlation token, not a sentence (§5.3) |
| 9 | [24 §4.4](../24-html-component-studio.md): `paint()` yield before every blocking call | 21/22 carry no `paint()` — `Loading…` is authored in `properties.html` | **Author the loading state in the markup.** Keep the yield for a click-triggered re-fetch |
| 10 | [24 §6.3](../24-html-component-studio.md): register `ctx.on`/`onCleanup` before the first await | 22/22 have **no** top-level await at all | **Make it structural**: define → bind → declare actions → `load().catch(...)` |
| 11 | [24 §9](../24-html-component-studio.md): drive labels from `service.global.locale.getKey()`; do not copy `data-<lang>` + browser sniffing | **the exact anti-pattern in all 22**, because the rules read the always-`null` `context.data.localeKey` | **Fix the rule, then one message map.** Keep only the confirm-only asymmetry: a default is not an answer |
| 12 | [24 §11.1](../24-html-component-studio.md): `createElement` + `textContent` | `innerHTML` template strings with `esc()` on every interpolation, 22/22 | **Either, never mixed.** The template form is far more readable for a 12-column row; its safety rests entirely on `esc()`, so put `esc()` in the kit and grep for unescaped `+ pick(` before shipping |
| 13 | [24a §6](../24a-theming-and-dark-mode.md): one `"*"` block; per-skin only for images/shadows/gradients/rescues | **five keys on 22/22** — `"*"` plus four identical dark patches | **Follow the projects.** Platform status tokens collapse to one hue on two dark skins. Patch **only** the alias lines |
| 14 | [24b §4](../24b-html-composition-and-plugin-tags.md): `<prop>` is a seed, not a setting | C seeds 583 localized captions inline; B and D seed **zero** | **Seed only captions you never expect to change.** Anything a customer may edit belongs on the child node |
| 15 | [24 §1.2](../24-html-component-studio.md) / [24b §9](../24b-html-composition-and-plugin-tags.md): keep the entity's normal table page; host, don't redraw | **the console replaced the table** — not one `crud.table.plugin` on any of the 21 studio pages | **Follow the doc, with the projects' refinement:** keep the generated page for master data and link to it from the exact control that needs it (§9.2) |

**Beyond the docs entirely** — add these to your own kit: the project kit as a studio lib (§4);
breadcrumb-by-proxy (§4.1); the per-script `try{}` (§5.1); `safe { … }` per source in the fetch rule
(§8.1); `data-<pfx>-bound` binding plus one delegated listener per rebuilt container (§5.2); the
`<key>Loc` suffix channel (§8.4); `dimHuman()` (§8.4); flexbox micro-charts (§9); base64 attachments
through `ctx.callRule` (§8.5); the telemetry wrapper and the build stamp (§10).

---

## 15 · Done when

- [ ] §1 answered honestly — a stock table plugin plus a form group genuinely cannot do this screen,
      and you can name the layout feature in one sentence
- [ ] Node has a **symbolic identifier**, and `roleaccess set` was run on it — not only on the page
- [ ] `properties.html` is not empty, every JS target carries one `<pfx>-` class, and the loading state
      is authored in the markup
- [ ] Every `scripts[].libNames` names its lib; the vendored kit is under `studio/<lib>/<file>` and was
      **seen to load** on a live page
- [ ] Each script is wrapped in a top-level `try{}` that renders the error into the primary container
- [ ] No top-level `await`; the entry point is `load().catch(render the error)`
- [ ] Every listener, timer and the breadcrumb declaration registered synchronously, through `bind()` /
      `ctx.onCleanup`
- [ ] One EXECUTION rule for the read, one per mutating action, all called **by identifier**, all
      confirmed to exist
- [ ] The fetch rule guards every source with `safe { … }`, carries the `rowsInPage` ceiling, and reads
      the locale with `service.global.locale.getKey()`
- [ ] Reads camelCase, writes snake_case, both spellings plus the editor selector in one `FIELDS` table
- [ ] Message strips use `classList`, never `className`; an empty message hides the strip; a message is
      cleared before the action and re-asserted after the reload
- [ ] Loading, empty, error and crash all render into the **same** slot; the empty sentence names the
      filter or the next action; KPIs with no data render `—`, never `0`
- [ ] Paging is client-side under the rule's ceiling, or server-side above it — decided consciously
- [ ] `css.byTheme` is one `"*"` block plus four dark keys patching **only** the status aliases; no
      colour in `style=`; every `@keyframes` prefixed
- [ ] The screen reads on **Dark**; a deliberate rule failure shows a sentence, not a hash;
      `mrjun.py validate` exits 0 and every WARN was read
