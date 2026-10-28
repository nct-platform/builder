# 24e · Html Field — a form control whose input you build as a studio component

> **Scope.** The one form control whose input YOU write: `dynaform.form.html.field.plugin` renders a studio
> component — your HTML, scripts, per-theme CSS and libraries — where a stock control would draw its input, and
> binds that component to a form value exactly like a stock control. This document carries ONLY the delta: the
> value contract (`properties.fieldModel`), the value API your script uses (`ctx.field`), how a value travels from
> the script to the record, the field's OWN settings — sections of its settings drawer you build like the component
> (`ctx.settings`, §5) — and the traps of those seams.
> **Not here** — and not repeated: everything about the component itself (the `studioModel` schema, documents,
> includes, `<plugin>` tags, the whole `ctx` runtime, `ctx.callRule`/`ctx.callBl`, lifecycle, CSS) →
> [24](24-html-component-studio.md), [24a](24a-theming-and-dark-mode.md), [24b](24b-html-composition-and-plugin-tags.md),
> [24d](24d-html-component-structure.md); everything about the control's binding (scope, CRUD mode, `dataClass`,
> mandatory / conditional validation, prohibition, default value, event mappings, localization, where a value
> LANDS) → [02](02-form-controls-reference.md). An Html Field obeys both, unchanged.
> ⚠️ **New control.** Documented from the platform's behaviour, not yet from a delivered form — the same footing
> [02](02-form-controls-reference.md) gives the Gantt chart.

| | |
|---|---|
| Plugin name | `dynaform.form.html.field.plugin` — display name "Html Field", UI group "Form Controls" |
| Config slots | `properties.settings` — the ordinary form-control settings ([02](02-form-controls-reference.md)) plus ONE key of its own, `custom`: the values its settings sections wrote (§5) · `properties.html` + `properties.studioModel` — the component, exactly as on an `nct.html.plugin` ([24](24-html-component-studio.md) §2) · `properties.fieldModel` — the value contract (§2) |
| The value | ONE value of the bound type — what the form submits, validates and stores for this field |
| Script surface | `ctx.field` (§3) and `ctx.settings` (§5) — every other `ctx.*` member works as in [24](24-html-component-studio.md) §3; needs runtime `window.Dokie.__v >= 4` (`ctx.field`) / `>= 5` (`ctx.settings`) |
| Public API | a writable field of the bound type ([32](32-public-api.md)) — the same strict conversion as the screen (§4.1) |
| Children | the nodes its own `<plugin>` tags address, as on an html block ([24b](24b-html-composition-and-plugin-tags.md)) — never another form control (§7) — and its settings sections (§5) |

> **🔧 Tooling.** `node add --parent <slot> --plugin dynaform.form.html.field.plugin --name "<Field>" --identifier <fld_…> --settings @settings.json`
> (the node, with its binding — the same settings JSON as any control), `node set-studio <id> --json @studioModel.json`
> (the component), **`node set-field-model <id> --json '{"types":["INTEGER"]}'`** (the value contract); a settings
> section: `node add --parent <fld_…> --plugin dynaform.html.field.section.plugin --name "<Title>" --identifier <sec_…>`,
> `node set-studio <sec_…>`, **`node set-section-model <sec_…> --json '{"icon":"…","defaults":{…}}'`**, and the
> values it wrote: `node patch-settings <fld_…> --set 'custom=json:{…}'` (replaces the WHOLE `custom` object);
> `show node <id>`, `validate`. ⚠️ There is **no** command that writes `properties.html` — hand-edit it, as for an html block
> ([24b](24b-html-composition-and-plugin-tags.md) §2.6) — and `show node` prints `studioModel` and `fieldModel` as
> escaped strings; keep the JSON files you fed in as the source of truth. Full index — [`tools/README.md`](tools/README.md).

---

## 1 · When it is the right control — and when it is not

**Reach for it only when no stock control draws the input.** The ten stock field controls
([02](02-form-controls-reference.md) §Choosing a control) each bring choices paging, search, rule-checked options,
read-only rendering and a public-API shape for free; an Html Field brings exactly what you write. Ask the meaning
question of [02](02-form-controls-reference.md) first; this control is the answer only when the answer is "an
input whose INTERACTION no stock control has":

| The field is… | Html Field, bound as | Not |
|---|---|---|
| a rating, a score drawn as stars / a slider with a live label | `INTEGER` / `BIG_DECIMAL` | a text field the user types a digit into |
| a colour, a swatch from a fixed palette | `STRING` (`#rrggbb`) | a dropdown of colour names |
| a signature, a drawn sketch | `STRING` (a data URL) or `OBJECT_NODE` (strokes) | a file upload of a scanned image |
| a point or area on a map / on a floor plan / on an image | `OBJECT_NODE` (`{"lat":…,"lng":…}`) | two number fields |
| a reference to another CRUD's row picked as a card (avatar, name, contact), searched as you type | `OBJECT_NODE` — the relation field itself (§2.1) | a dropdown, when a plain list of labels is enough |
| a weekly schedule, a grid of on/off cells, a seat or slot picker | `OBJECT_NODE` / `ARRAY_NODE` | a textarea of comma-separated values |
| a duration typed as `1h 30m`, a quantity with a unit switch | `LONG` (minutes) / `OBJECT_NODE` | a text field holding free text the rules then parse |
| formatted text — markdown, a code snippet | `STRING` | — (a text area if plain text is enough) |

**Not this control:**

* **a choice among server data** (a customer, a product, a status) — a dropdown / autocomplete / tree picker
  pages, searches and, through the API, refuses an option that is not offered; an Html Field does none of that;
* **a whole screen** — a studio component on a page ([24](24-html-component-studio.md) §1); a form field is one
  value;
* **several values** — one Html Field edits ONE field. Two values are two fields (or one `OBJECT_NODE` value
  that the record stores as one JSON column — decide that with the schema, [02](02-form-controls-reference.md)
  "The column type follows the control").

---

## 2 · Export shape — the node and its value contract

A field node is a form control node ([02](02-form-controls-reference.md) §Node shape) that also carries a
component. It sits wherever a stock control would — under the form's `form.parsis`, usually in a generated
`gen_row_*` → col → slot wrapper ([03](03-generate-fields-from-crud.md)):

```json
{
  "identifier": "fld_rating", "name": "Rating",
  "pluginName": "dynaform.form.html.field.plugin",
  "children": [],
  "properties": {
    "settings":    { "key": "settings",    "propertyType": "STRING", "stringValue": "{\"scope\":\"CRUD\",\"contextIdentifier\":\"<ctx-uuid>\",\"crudAlias\":\"review\",\"fieldExpression\":\"stars\",\"alwaysMandatory\":true,\"mandatoryValidationMessages\":{\"en_US\":\"Rate it\"},\"name\":\"Rating\",\"filterKey\":\"stars\",\"dataClass\":\"java.lang.Integer\"}" },
    "html":        { "key": "html",        "propertyType": "STRING", "stringValue": "<div class=\"x-stars\" role=\"radiogroup\" aria-label=\"Rating\">…</div>" },
    "studioModel": { "key": "studioModel", "propertyType": "STRING", "stringValue": "{\"scripts\":[{\"name\":\"main\",\"code\":\"…\",\"enabled\":true,\"order\":0,\"libNames\":[]}],\"css\":{\"byTheme\":{\"*\":\"…\"}}}" },
    "fieldModel":  { "key": "fieldModel",  "propertyType": "STRING", "stringValue": "{\"types\":[\"INTEGER\",\"SHORT\",\"LONG\"]}" },
    "className": { "key": "className", "propertyType": "STRING", "stringValue": "" },
    "styleName": { "key": "styleName", "propertyType": "STRING", "stringValue": "" },
    "tagProperties": { "key": "tagProperties", "propertyType": "STRING", "stringValue": "" }
  }
}
```

* **`settings`** — a form control's settings: the base keys of [02](02-form-controls-reference.md), plus `custom` —
  the values its settings sections wrote (§5). `dataClass` decides the type your script receives (table below) — set
  it, as on every control.
* **`html` + `studioModel`** — exactly [24](24-html-component-studio.md) §2. ⛔ A component with no script never
  writes a value (§3); `validate` WARNs.
* **`fieldModel`** — `{"types": [ <type>, … ]}`: the value types your script handles. The form's settings offer
  the author only fields of these types, and the studio's Value tab warns while the binding is another. **Absent or
  empty = any type** (no restriction declared). A name not in the table below is ignored — never an error — so a
  typo silently widens the field to every type; `validate` WARNs.

### 2.1 The types — what `fieldModel` declares, what `dataClass` binds, what the script sees

| `fieldModel.types[]` | the `dataClass` it admits | `ctx.field.value` in the script | `ctx.field.set(…)` also accepts (converted for you) |
|---|---|---|---|
| `STRING` | `java.lang.String` | string | a number or boolean (as text) |
| `INTEGER` / `SHORT` / `BYTE` | `java.lang.Integer` / `java.lang.Short` / `java.lang.Byte` | number | numeric text (`"42"`) |
| `LONG` / `BIG_INTEGER` | `java.lang.Long` / `java.math.BigInteger` | number (exact up to 2⁵³) | text — and send TEXT to keep every digit (`"9007199254740993"`) |
| `DOUBLE` / `FLOAT` | `java.lang.Double` / `java.lang.Float` | number | numeric text |
| `BIG_DECIMAL` | `java.math.BigDecimal` | number | text — send TEXT to keep every digit (`"0.10"`) |
| `BOOLEAN` | `java.lang.Boolean` | boolean | `"true"` / `"false"` |
| `LOCAL_DATE` | `java.time.LocalDate` | `"2026-01-31"` | a `Date` (its LOCAL date) |
| `LOCAL_DATE_TIME` | `java.time.LocalDateTime` | `"2026-01-31T09:30"` (seconds only when not zero) | a `Date` (its LOCAL date-time) |
| `INSTANT` | `java.time.Instant` | `"2026-01-31T09:30:00Z"` | a `Date`, epoch milliseconds, ISO text with `Z` or an offset |
| `OBJECT_NODE` | `com.fasterxml.jackson.databind.node.ObjectNode` | object | — |
| `ARRAY_NODE` | `com.fasterxml.jackson.databind.node.ArrayNode` | array | — |
| `ARRAY_LIST` | `java.util.List` (real nodes write this, as for File Upload / List) | array | — |

* **No `dataClass`** — the value is untyped JSON: the script receives whatever is stored and may write any JSON.
  `JSON` cannot be declared in `fieldModel`; a field bound this way never warns.
* **A value inside a JSON column** — bind an `ObjectNode` field with `jsonNodeExpression` + `jsonNodeValueType`
  ([02](02-form-controls-reference.md)): the script receives the type at that path (`ctx.field.type` says which).
  The settings offer that projection unless every type the field accepts is a JSON or list type: declare
  `OBJECT_NODE` alone (or with `ARRAY_NODE` / `ARRAY_LIST`) and the field binds the WHOLE column, like the
  Comments and Gantt controls.
* **An enum column** binds as `STRING` (the constant's name), as on every control.
* **A relation of a dynamic CRUD** — the `ObjectNode` field named after the related row (`customer` on an order, stored
  as the `customer_id` column) — binds as `OBJECT_NODE` and is the related row's DTO: it reads as `{"id": …, "code": …,
  "name": …}`, and a write needs only the related row's `id` — any object carrying it is accepted and the record stores
  that id (write the whole row the field picked: the card can show it until the next render). A stock dropdown binds the
  same relation as `customer.id` (`STRING`); two controls bound to one relation both submit — keep one.
* An empty string, an invalid `Date` and a non-finite number written with `set` are **no value** (`null`) for every
  type.

---

## 3 · `ctx.field` — the value API

`ctx.field` exists in every script of a field component (`null` in an html block). All of the component's scripts
share the ONE object.

| Member | Meaning |
|---|---|
| `ctx.field.value` | the current value, shaped by the table in §2.1; `null` = no value. **Read-only** — an assignment does nothing but warn in the console |
| `ctx.field.set(value)` | write the value; returns `true` when the field holds it. Fires `change` — what the field's event mappings listen to. A `set` that does not change the value fires nothing |
| `ctx.field.set(value, {silent: true})` | write without firing `change` — for a stream of edits (typing, dragging) … |
| `ctx.field.commit()` | … then announce it once: fires `change` if the value moved since the last announcement |
| `ctx.field.onChange(fn)` | `fn(value, previous)` after every `set` that changed the value, from any script of the component; returns the function that unregisters it |
| `ctx.field.type` | the bound type — a §2.1 name (`'INTEGER'`, `'OBJECT_NODE'`, …), or `'JSON'` with no `dataClass` |
| `ctx.field.types` | the types `fieldModel` declares (empty = any) |
| `ctx.field.readOnly` | the field is drawn read-only (prohibited) — draw it so; `set` is refused and nothing is submitted |
| `ctx.field.required` | always mandatory (`alwaysMandatory`). A requirement a predicate decides is checked at submit and is NOT known here |
| `ctx.field.errors` | the messages the last submit left on this field (`[]` when none) |
| `ctx.field.name` | the field's `settings.name` — what the form's messages call it |

The component's root also carries the state for your CSS: `dokie-field-readonly` (+ `aria-readonly`) while
read-only, `dokie-field-invalid` (+ `aria-invalid`) while the last submit's errors stand. The first `set` clears
the errors, the class and the form's own error tooltip.

### 3.1 The lifecycle — one rule: draw from `value`, write with `set`

* **On every render** your program runs again from the top (a form refresh, a language switch, an event mapping that
  refreshes this field, a failed submit — [24](24-html-component-studio.md) §6): read `ctx.field.value`, draw it.
  Component state that is not in the value does NOT survive a render — keep what matters IN the value.
* **On every user change**, `ctx.field.set(newValue)` — that is the only way a value reaches the form. A script
  that draws but never writes submits only the value the field was rendered with.
* **Never `set` a value the user did not make, on mount.** `set` fires `change`; an event mapping that refreshes
  this very field re-renders it, and a value that differs on every mount (a timestamp, a random id) loops. A
  default belongs in the settings (`defaultValueEnabled` — [02](02-form-controls-reference.md)), which arrives as
  `ctx.field.value` with no event.
* **Read-only:** when `ctx.field.readOnly`, draw without the interaction (or with it visibly disabled).

### 3.2 Worked example — a star rating (`INTEGER`)

`properties.html` (the main document — the root of the component, scoped CSS hooks under one prefix):

```html
<div class="x-rating" role="radiogroup" aria-label="Rating">
  <button type="button" class="x-star" data-v="1" aria-label="1 star">★</button>
  <button type="button" class="x-star" data-v="2" aria-label="2 stars">★</button>
  <button type="button" class="x-star" data-v="3" aria-label="3 stars">★</button>
  <button type="button" class="x-star" data-v="4" aria-label="4 stars">★</button>
  <button type="button" class="x-star" data-v="5" aria-label="5 stars">★</button>
  <button type="button" class="x-clear" aria-label="Clear rating">×</button>
</div>
```

`studioModel.scripts[0].code`:

```js
const stars = Array.from(ctx.root.querySelectorAll('.x-star'));
const clear = ctx.root.querySelector('.x-clear');

function paint(v) {
  stars.forEach(s => {
    const on = v != null && Number(s.dataset.v) <= v;
    s.classList.toggle('x-on', on);
    s.setAttribute('aria-checked', String(on));
    s.disabled = ctx.field.readOnly;
  });
  clear.hidden = ctx.field.readOnly || v == null;
}

paint(ctx.field.value);                               // model -> UI, on every render
ctx.field.onChange(paint);                            // every write, from any script, repaints

if (!ctx.field.readOnly) {
  ctx.root.addEventListener('click', e => {           // one delegated listener on the root
    const star = e.target.closest('.x-star');
    if (star) { ctx.field.set(Number(star.dataset.v)); }   // UI -> model
    if (e.target.closest('.x-clear')) { ctx.field.set(null); }
  });
}
```

`studioModel.css.byTheme["*"]` — theme tokens only ([24a](24a-theming-and-dark-mode.md)):

```css
.x-rating { display: inline-flex; gap: .25rem; align-items: center; }
.x-star { border: 0; background: none; font-size: 1.5rem; line-height: 1; color: var(--bs-secondary-color, #6c757d); cursor: pointer; }
.x-star.x-on { color: var(--bs-warning, #ffc107); }
.x-star:disabled { cursor: default; }
.x-clear { border: 0; background: none; color: var(--bs-secondary-color, #6c757d); }
```

`fieldModel`: `{"types":["INTEGER","SHORT","LONG"]}` — and the field's `dataClass` is one of them.

### 3.3 Worked example — a JSON value (`OBJECT_NODE`): a pickup point on a map

The value is the object; the record stores it in a `jsonb` column bound with `dataClass` `ObjectNode`
(`fieldModel` `{"types":["OBJECT_NODE"]}`). The map library is declared once (`libs[]`, [24](24-html-component-studio.md)
§2) and listed in the script's `libNames`:

```js
const L = ctx.libs.leaflet;
const at = ctx.field.value;                                   // {"lat":…,"lng":…} or null
const map = L.map(ctx.root.querySelector('.x-map')).setView(at ? [at.lat, at.lng] : [0, 0], at ? 15 : 2);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
let pin = at ? L.marker([at.lat, at.lng]).addTo(map) : null;
ctx.onCleanup(() => map.remove());                            // a re-render must not leave the old map alive

if (!ctx.field.readOnly) {
  map.on('click', e => {
    const point = { lat: +e.latlng.lat.toFixed(6), lng: +e.latlng.lng.toFixed(6) };
    pin ? pin.setLatLng(e.latlng) : (pin = L.marker(e.latlng).addTo(map));
    ctx.field.set(point);
  });
}
```

### 3.4 A stream of edits — `silent` + `commit`

An editor that changes on every keystroke must not fire the field's events on every keystroke:

```js
editor.on('change', () => ctx.field.set(editor.getValue(), { silent: true }));
editor.on('blur',   () => ctx.field.commit());
```

The value is always current in the field — a submit in between still carries the last keystroke; only the
`change` announcement waits for `commit`.

---

## 4 · Where the value goes — submit, validation, events

### 4.1 Submit and conversion

The form submits the field's value with every other field's. The server converts it **strictly** by the bound
type — the same conversion the public API applies to a request body: a fraction for an integer, a number outside
its type's range, a date that is not ISO, an array for an object, a string for a number that is not numeric text —
each is **refused**, the form is not submitted, and the field gets the message, in these words:

| bound type | the message on the field |
|---|---|
| `STRING` | Must be a string. |
| `INTEGER` | Must be an integer between -2147483648 and 2147483647. |
| `LONG` / `SHORT` / `BYTE` | Must be an integer between `<min>` and `<max>`. |
| `BIG_INTEGER` | Must be an integer. |
| `DOUBLE` / `FLOAT` | Must be a number within the range of a double / of a float. |
| `BIG_DECIMAL` | Must be a number, or a number as text. |
| `BOOLEAN` | Must be true or false. |
| `LOCAL_DATE` | Must be an ISO date (yyyy-MM-dd). |
| `LOCAL_DATE_TIME` | Must be an ISO local date-time (yyyy-MM-ddTHH:mm:ss, no offset). |
| `INSTANT` | Must be an ISO date-time with Z or an offset (yyyy-MM-ddTHH:mm:ssZ). |
| `OBJECT_NODE` | Must be a JSON object. |
| `ARRAY_NODE` / `ARRAY_LIST` | Must be a JSON array. |

That message reaches `ctx.field.errors` on the re-render that follows, and the form draws it under the component.
A wrong shape is a bug in your script, not a user error — test every path that calls `set` (§8).

**Text is taken as every text control takes it**: trimmed, and a blank text is no value. (A `STRING` value with
meaningful leading or trailing whitespace does not survive — as in a text area.)

**A decimal keeps every significant digit** (it never passes through a double); trailing zeros are normalised as
everywhere the platform stores a decimal (`12.50` is stored as `12.5`).

### 4.2 Mandatory, validation, prohibition, default — unchanged

The field's settings work exactly as on a stock control ([02](02-form-controls-reference.md)): `alwaysMandatory` /
`mandatoryPredicateIdentifier`, `conditionalValidations`, `prohibitedPredicateIdentifier` / `alwaysProhibited`,
the default value, form-level VALIDATION rules. Two consequences of the value being yours:

* **What counts as empty for "mandatory"**: `null`, a blank text, and an empty `ARRAY_LIST`. An empty object `{}`
  and an empty `ARRAY_NODE` `[]` are VALUES — a mandatory field holding one passes. Write `null` for "nothing
  picked".
* **Prohibited** renders the component with `ctx.field.readOnly === true` and submits nothing at all — the field
  keeps what it had, whatever the script does.

### 4.3 Event mappings

`eventComponentMappings` ([02](02-form-controls-reference.md)) wire to the field's value, and the only event the
value fires is **`change`** — on every `set` that changes it, and on `commit()`. A mapping with any other
`eventName` (`blur`, `click`, `input`) never fires. A mapping's execution rules see the new value: it is in the
form's document by the time they run.

### 4.4 The public API

An Html Field on a form exposed through the public API ([32](32-public-api.md)) is a writable field of the bound
type, converted with the same rules as §4.1 — a request carries the value your script would have written. Its
mandatory, read-only and default settings apply there as on the screen. Anything the component does with
`ctx.callRule` while the user edits does NOT run for an API caller — put logic a submit depends on in the action's
rule, not in the component.

### 4.5 Filter forms

Placed in a filter form, the field writes the filter key like any filter control (`filterKey`); with no `dataClass`
its value is text there.

---

## 5 · Settings sections — the field's own settings, built like the field

A component with knobs — how many stars, which palette, which rule supplies its options, which CRUD it reads —
should not hard-code them: the same component placed twice, or reused on another form, needs other values, and the
person configuring a form is not the person who wrote the script. **Settings sections** are the field's own items in
its settings drawer (the panel that opens when the author clicks the field), after the stock Mapping and Config
items. Each one is a studio component like the field itself — your HTML, scripts, CSS — and what it writes, the field's
script reads:

```
settings drawer of the field        field node
  ▸ Mapping   (stock)
  ▸ Config    (stock)
  ▾ Rating    ← section 1 ─────────┐   properties.settings.custom = {"maxStars": 7, "allowClear": false, "capRule": "<rule-uuid>"}
  ▸ Data      ← section 2 ─────────┤        ▲ written by the sections, saved with the field's settings
                                    │        │
                                    │   the field's script:  ctx.settings.get('maxStars', 5)
                                    └── children of the field node: dynaform.html.field.section.plugin
```

Use them for **anything an author decides per field** — never for the field's VALUE (that is `ctx.field`, the
record's data) and never for a secret: the values are written into every page the field is drawn on.

### 5.1 Export shape — sections are children of the field

Abridged — `…` stands for content left out; every property is a STRING holding JSON text, as everywhere:

```jsonc
{
  "identifier": "fld_rating", "name": "Rating",
  "pluginName": "dynaform.form.html.field.plugin",
  "properties": {
    "settings":    { "key": "settings", "propertyType": "STRING", "stringValue": "{\"scope\":\"CRUD\",…,\"dataClass\":\"java.lang.Integer\",\"custom\":{\"maxStars\":7,\"allowClear\":false}}" },
    "html": { … }, "studioModel": { … }, "fieldModel": { … }
  },
  "children": [
    {
      "identifier": "sec_rating", "name": "Rating",
      "pluginName": "dynaform.html.field.section.plugin",
      "children": [],
      "properties": {
        "html":         { "key": "html",         "propertyType": "STRING", "stringValue": "<div class=\"row g-3\">…data-setting…</div>" },
        "studioModel":  { "key": "studioModel",  "propertyType": "STRING", "stringValue": "{\"scripts\":[…],\"css\":{\"byTheme\":{\"*\":\"…\"}}}" },
        "sectionModel": { "key": "sectionModel", "propertyType": "STRING", "stringValue": "{\"icon\":\"pe-7s-star\",\"defaults\":{\"maxStars\":5,\"allowClear\":true}}" }
      }
    }
  ]
}
```

* **A section is a child node** of the field, `pluginName` `dynaform.html.field.section.plugin`, in the order the
  drawer shows them. Its **`name` is the drawer item's title**. A section node anywhere else is drawn in no drawer
  (placed on a page it still renders, from its own defaults, and saves nothing).
* **`html` + `studioModel`** — exactly [24](24-html-component-studio.md) §2, and every rule of an html block applies
  (prefix your classes, theme-token CSS, `<plugin>` tags ↔ children). Its scripts run **in the drawer only** — never in
  the field, never on the form.
* **`sectionModel`** — `{"icon": "<css classes>", "defaults": {<key>: <value>, …}}`. `icon` is the item's icon (absent =
  a generic cog); `defaults` is **what each key this section writes holds while nobody has set it**. Declare a default
  for every key — the section's controls show it and the field's script reads it, so the two never disagree.
* **`settings.custom`** (on the FIELD) — a JSON object: the values written so far. Absent = nothing written. It is
  saved, exported and imported with the rest of the settings; a copied field carries its sections AND its values.

**What a key reads**, in the field and in every section alike: the value in `custom` if there is one, else the
`defaults` of the field's sections (merged in section order — a later section's default for the same key wins), else
the fallback the script passes. All sections share ONE object: give each key one owner and a name that says what it
is (`maxStars`, `optionsRule`, not `value`, `rule2`).

### 5.2 `ctx.settings` and `ctx.catalog`

| Member | In a section (drawer) | In the field |
|---|---|---|
| `ctx.settings.get(key, fallback)` | the key's value (§5.1 order) | same |
| `ctx.settings.values` / `.defaults` | every key / the merged defaults (copies) | same |
| `ctx.settings.set(key, value)` · `set({k: v, …})` | writes and **saves at once**; `null`/`undefined` removes a key (its default returns); values must be JSON | refused (returns `false`) — the field reads |
| `ctx.settings.set(…, {silent: true})` + `ctx.settings.commit()` | write on every keystroke/drag, save once | — |
| `ctx.settings.onChange(fn)` | `fn(values, changedKeys)` after any section's write (this one's included) | never fires — a save draws the field again |
| `ctx.settings.render()` | draws the `data-setting` controls a script added | — |
| `ctx.settings.editable` | `true` | `false` |
| `ctx.catalog.rules({type})` | `[{identifier, name, type, description}]` — `type`: `PREDICATE` / `EXECUTION_RULE` / `VALIDATION_RULE`, one or an array | `ctx.catalog` is `null` |
| `ctx.catalog.cruds()` | `[{alias, name}]` | |
| `ctx.catalog.fields(alias)` | `[{expression, label, type}]` (`type` as in §2.1) | |
| `ctx.catalog.methods(alias)` | `[{name, returnType, parameters: [{name, type}], readonly}]` | |
| `ctx.catalog.contexts()` | `[{identifier, alias, name, cruds}]` | |

`ctx.catalog` lists what the signed-in AUTHOR sees (it answers authors only) — the same lists the platform's own
pickers show. A list call is a promise (`await` it); each list is fetched once per drawing of the section.
`ctx.settings` is `null` in an html block.

### 5.3 Controls bound for you — `data-setting`

Most sections need no script at all. A control with **`data-setting="<key>"`** shows the key's value and, when the
author changes it, writes it (and the drawer saves) — typed by the control:

| Control | The value written |
|---|---|
| `<input data-setting="label">`, `<textarea>`, `<select>` | text (`""` removes the key) |
| `<input type="number" data-setting="maxStars">`, `type="range"` | a number (empty removes the key; an unreadable entry, or one outside the control's `min`/`max`, is refused and marked `is-invalid`) — still clamp in the field's script: a value can also arrive from an import |
| `<input type="checkbox" data-setting="allowClear">` | `true` / `false` |
| `<input type="radio" name="size" value="s" data-setting="size">` (one per option, same `data-setting`) | the checked one's `value` |
| `<select multiple data-setting="tags">` | an array of the selected values (none removes the key) |
| a text input, `<textarea>` or single `<select>` with `data-setting-type="number"` / `"boolean"` / `"json"` | that type — `json` parses the text (invalid JSON is refused and marked); a checkbox, radio or multiple select keeps its own type and ignores the attribute |

**Lists of the project's artefacts — `data-catalog`.** A `<select data-setting="…" data-catalog="<kind>">` fills
itself from `ctx.catalog`, AFTER the options its markup already has (keep a `<option value="">— none —</option>`
first). What is stored is what the field's script hands to the bridges:

| `data-catalog` | stores | narrow / depend with |
|---|---|---|
| `rules` | the rule's **identifier** (survives a rename) | `data-rule-type="EXECUTION_RULE"` (comma-separated) |
| `cruds` | the CRUD **alias** | — |
| `fields` | the field's **expression** | `data-crud="<alias>"`, or `data-crud-setting="<key>"` to follow the CRUD another control picked (the list refills when it changes) |
| `methods` | the business-logic method's **name** | `data-crud` / `data-crud-setting`, as for `fields` |
| `contexts` | the context's **identifier** | — |

A stored value the project no longer has (a deleted rule, a renamed field) stays selected and is shown as
**missing** — never silently replaced (a list that failed to load shows it plainly).

**Emptying a control removes its key — and a removed key reads its default.** So a key that HAS a default cannot be
set to "nothing" by emptying a control: picking `— none —` brings the default back. When "none" must be a choice of
its own, give the key no default, or make none a real value (`<option value="none">`) the field's script understands.

### 5.4 Worked example — the star rating's own settings

The §3.2 rating, configurable: how many stars, whether it can be cleared, and an optional rule that decides how many
stars a record allows (an `EXECUTION_RULE` the author picks). One section, no script.

Section `html` (the section node, `name` "Rating"):

```html
<div class="x-rset row g-3">
  <div class="col-6">
    <label class="form-label">Stars</label>
    <input type="number" min="3" max="10" class="form-control" data-setting="maxStars">
  </div>
  <div class="col-6 d-flex align-items-end">
    <div class="form-check">
      <input type="checkbox" class="form-check-input" data-setting="allowClear">
      <span class="form-check-label">Can be cleared</span>
    </div>
  </div>
  <div class="col-12">
    <label class="form-label">Rule that caps the stars (optional)</label>
    <select class="form-select" data-setting="capRule" data-catalog="rules" data-rule-type="EXECUTION_RULE">
      <option value="">— none —</option>
    </select>
  </div>
</div>
```

`sectionModel`: `{"icon": "pe-7s-star", "defaults": {"maxStars": 5, "allowClear": true}}`

The field's script, built from the settings instead of fixed markup (its `html` is just `<div class="x-rating" role="radiogroup" aria-label="Rating"></div>`):

```js
// The settings, clamped: an author can type any number, the section does not enforce min/max.
const max = Math.min(10, Math.max(3, Math.round(Number(ctx.settings.get('maxStars', 5)) || 5)));
const allowClear = ctx.settings.get('allowClear', true) === true;
const capRule = ctx.settings.get('capRule');               // a rule identifier, or undefined
const box = ctx.root.querySelector('.x-rating');

let cap = max;
if (capRule) {
  try {
    cap = Math.min(max, Number(await ctx.callRule(capRule, { value: ctx.field.value })) || max);
  } catch (e) { console.warn('cap rule failed', e); }      // the field keeps working without it
}

box.innerHTML = Array.from({ length: max }, (_, i) =>
  `<button type="button" class="x-star" data-v="${i + 1}" aria-label="${i + 1} stars">★</button>`
).join('') + (allowClear ? '<button type="button" class="x-clear" aria-label="Clear rating">×</button>' : '');

// Query AFTER building: the buttons did not exist before.
const stars = Array.from(box.querySelectorAll('.x-star'));
const clear = box.querySelector('.x-clear');              // null when clearing is off

function paint(v) {
  stars.forEach(s => {
    const on = v != null && Number(s.dataset.v) <= v;
    s.classList.toggle('x-on', on);
    s.setAttribute('aria-checked', String(on));
    s.disabled = ctx.field.readOnly || Number(s.dataset.v) > cap;
  });
  if (clear) { clear.hidden = ctx.field.readOnly || v == null; }
}

paint(ctx.field.value);
ctx.field.onChange(paint);

if (!ctx.field.readOnly) {
  box.addEventListener('click', e => {
    const star = e.target.closest('.x-star');
    if (star && !star.disabled) { ctx.field.set(Number(star.dataset.v)); }
    if (clear && e.target.closest('.x-clear')) { ctx.field.set(null); }
  });
}
```

Changing "Stars" in the drawer saves the field's settings and draws the field again with the new count — the author
sees the result on the form at once.

### 5.5 Binding the field to rules, CRUDs and business logic

The section PICKS, the field CALLS — through the bridges of [24](24-html-component-studio.md) §4, which check the
artefact's own access for whoever views the form (§4.1 / §4.2 "Access" there):

| The section stores (`data-catalog`) | The field's script |
|---|---|
| a rule identifier (`rules`) | `await ctx.callRule(ctx.settings.get('optionsRule'), { … })` |
| a CRUD alias + a method name (`cruds` + `methods` with `data-crud-setting`) | `await ctx.callBl(ctx.settings.get('crud'), ctx.settings.get('loader'), [ … ])` |
| a CRUD alias + a field expression (`cruds` + `fields`) | the name of the property to read in what the method returns (`row[ctx.settings.get('labelField')]`) |

`methods` lists the CRUD bean's methods AND the methods defined on a dynamic CRUD. A list method of a dynamic CRUD
(`find`) answers a PAGE, not an array: call it with `[{rowsInPage: 500, pageNumber: 0}]` and read `.content` (accept both
shapes: `Array.isArray(r) ? r : r.content`). Load the list once per drawing, when the field first needs it, and look a
stored `{id}` up in it to draw the full row — never `set` the looked-up row on mount.

Guard the empty case — a field placed but not yet configured has no rule: draw a short note
(`Choose a rule in this field's settings`) for an author instead of failing. A rule or method the field calls runs
with the VISITOR's rights, not the author's: open its access to whoever the form is for.

### 5.6 The section's own script

Write one only for what the controls cannot do — a live preview, a value computed from several controls, a control
that appears for one choice only:

```js
// show the "palette" row only while the colour mode is "palette"
const row = ctx.root.querySelector('.x-palette-row');
const sync = values => { row.hidden = values.colorMode !== 'palette'; };
sync(ctx.settings.values);
ctx.settings.onChange(sync);                                  // any section's write, this one's included
```

Never `ctx.settings.set` on mount — the drawer saves every write, and the field draws itself again on every save.

### 5.7 What else to know

* **A save draws the field again.** Component state that is not in the field's value is lost on every settings
  change (§3.1) — that is the point: the author sees the new behaviour at once.
* **One object, every section.** A second section that writes the same key overwrites the first's; a key nobody
  writes any more stays in `custom` (deleting a section keeps its values) — set it to `null` from a section to drop it.
* **Defaults are not written.** Opening a section saves nothing; only a change does. A key nobody has written keeps
  following its default — change the section's default later and the field follows it while it never set the key;
  write the value to pin it.
* **A section is drawn only in the field's drawer, for an author** — so `ctx.catalog` and the section's scripts never
  run for the form's visitors.
* **Buttons inside a section never submit the drawer** (an untyped `<button>` becomes `type="button"`); give them
  `type="button"` anyway.
* **`window.Dokie.__v < 5`** (a cached older runtime) has no `ctx.settings` — guard as in §7.

---

## 6 · Building one in `.mrjun`

1. **Settings** — the binding, as for any control ([02](02-form-controls-reference.md) §How to construct). Take the
   field's `dataClass` from the CRUD's field type; it must be a §2.1 class.
2. **Node** — under the form's `form.parsis` (in the slot a stock control would take):
   ```bash
   python3 mrjun.py node add --parent <slot> --plugin dynaform.form.html.field.plugin \
       --name "Rating" --identifier fld_rating --settings @rating-settings.json --project ./app
   ```
3. **Main markup** → ADD the `html` property to that node — `node add` creates none — in the envelope of
   [24b](24b-html-composition-and-plugin-tags.md) §2.6 (never empty — [24](24-html-component-studio.md) §2).
4. **Component** — scripts, CSS, libraries:
   ```bash
   python3 mrjun.py node set-studio fld_rating --json @rating-studio.json --project ./app
   ```
5. **Value contract** — the types the script handles, including the bound one:
   ```bash
   python3 mrjun.py node set-field-model fld_rating --json '{"types":["INTEGER","SHORT","LONG"]}' --project ./app
   ```
6. **Settings sections** (when the component has knobs, §5) — one node per drawer item, under the FIELD:
   ```bash
   python3 mrjun.py node add --parent fld_rating --plugin dynaform.html.field.section.plugin \
       --name "Rating" --identifier sec_rating --project ./app
   # ADD its html property (the data-setting controls; envelope: 24b §2.6), then:
   python3 mrjun.py node set-studio sec_rating --json @rating-section-studio.json --project ./app   # only if it has a script
   python3 mrjun.py node set-section-model sec_rating --json '{"icon":"pe-7s-star","defaults":{"maxStars":5,"allowClear":true}}' --project ./app
   # optional — pre-set values. This REPLACES the whole custom object: list every key you pre-set.
   python3 mrjun.py node patch-settings fld_rating --set 'custom=json:{"maxStars":7,"allowClear":false}' --project ./app
   ```
7. **Label** — the field's visible caption is a separate `nct.label.plugin` beside it, as for every control
   ([03](03-generate-fields-from-crud.md)); the component's own `aria-label` is for assistive technology.
8. **Validate + pack**, then **live-test** (§8).

---

## 7 · Gotchas — what imports clean and still misbehaves

* **Every checkbox on a page is redrawn as a switch** — yours too. An `<input type="checkbox">` in the component
  becomes the platform's toggle unless it carries `class="no-nice-checkbox"`.
* **Give every `<button>` in the component `type="button"`.** The field sits INSIDE the form, where a button without
  a type is a SUBMIT button. The runtime makes every untyped button of the component a plain button when it mounts
  and keeps a later one from submitting (`__v >= 5`), but a button your script inserts as raw HTML still counts as the
  form's default button for Enter until it is clicked once — and an older runtime does none of it.
* **No `<form>` inside the component.** The browser ignores a form start tag inside another form, so a submit
  handler of yours never runs. Inputs the component uses for its own drawing are fine — they are posted with the
  form and ignored; the value travels only through `ctx.field.set`.
* **No form control inside the component** (`<plugin name="dynaform.form.…">` in its HTML): it would bind and
  validate on its own, the API would not see it, and the field would edit two values. Compose fields side by side.
* **`window.Dokie.__v < 4`** (a browser holding a cached older runtime) has no `ctx.field` — the first
  `ctx.field.value` throws and the component draws nothing; below 5 there is no `ctx.settings`. Guard as
  [24](24-html-component-studio.md) §3 shows: `if ((window.Dokie.__v || 0) < 5) { ctx.root.textContent = 'Please
  reload this page.'; return; }`.
* **`ctx.field.value` is a COPY, on every read.** Mutating what you read — or the object you passed to `set` — changes
  nothing: build the new value and write it with `set`.
* **A refused value keeps the field unsubmitted, not empty.** After a failed submit the field re-renders with the
  value the user left (`ctx.field.value` = what your script wrote) and the message in `ctx.field.errors` — draw it,
  do not reset it.
* **`required` is static.** A field made mandatory by a predicate shows `required === false`; the submit still
  enforces it.
* **One value, one scale of precision.** A JavaScript number holds integers exactly only up to 2⁵³ and decimals as
  binary fractions: send `LONG`, `BIG_INTEGER` and `BIG_DECIMAL` values as TEXT when every digit matters (§2.1).
* **A localized field** (`localized: true` on a multi-language form, [02](02-form-controls-reference.md)) holds one
  value per language; switching the form's language re-renders the field with that language's value.
* **The html block's rules apply in full** — one prefix for every class, CSS from theme tokens, listeners and
  timers through `ctx.onCleanup`, no `setHtml` over `<plugin>` children ([24](24-html-component-studio.md) §6,
  [24a](24a-theming-and-dark-mode.md)).

---

## 8 · Testing — through the component, judged by the record

A test drives the field as a person does — through the component's own UI (click the third star, drag the pin) —
and asserts what the RECORD holds after the submit, not what the component draws. The field's value is also
readable in the page as the hidden `input` inside the field's control element (JSON text, empty = no value), which
is what a test reads to assert "the field now holds X" before submitting. Cover, for each field: the value written
by every interaction, a cleared value, the read-only rendering (`prohibited`), the mandatory message when nothing
is picked, and — when the form is exposed — the same value sent through the public API ([30](30-live-test-bugfix-and-autotest.md)).

---

## 9 · What `validate` checks — and what it cannot

| Caught offline | By |
|---|---|
| `fieldModel` that is not JSON / not `{"types": [...]}` | WARN — the platform ignores it and the field accepts ANY type |
| a `fieldModel` type that is not a §2.1 name (`JSON` and misspellings included) | WARN — ignored |
| a binding (`dataClass`, or `jsonNodeValueType` inside a JSON column) of a type `fieldModel` does not declare | WARN — the script is handed a type it was not written for |
| no enabled script, or no script that writes `ctx.field` | WARN — the field only ever submits the value it was drawn with |
| `settings.custom` that is not a JSON object | WARN — the platform drops it; the field reads only defaults |
| a settings section that is not a child of an Html Field | WARN — no drawer draws it |
| a `sectionModel` that is not JSON, not an object, or has an object/array `icon` | WARN — ignored entirely: no icon, no defaults |
| `sectionModel.defaults` that is not a JSON object (an object stored as a JSON string is fine) | WARN — the defaults are dropped, the icon stays |
| a section with no `data-setting` control and no `ctx.settings.set(…)` | WARN — it writes nothing |
| a `data-catalog` kind the catalog lacks, a `data-rule-type` that is no rule type, `fields`/`methods` with no `data-crud`/`data-crud-setting` | WARN — the list cannot fill |
| a rule picked through `data-catalog="rules"` (its key in `custom`) that is not in `rules[]`, or not of the listed type | WARN — the drawer shows it missing; the field calls a rule that is not there |
| everything [24](24-html-component-studio.md) §2/§3.2 checks for a component — for the field AND each section: `studioModel` parses, `libNames` declared, relative asset paths, theme-safe CSS, the `<include>` graph, `<plugin>` tags ↔ children | as for an html block |

**Not caught — yours to test live:** a script that writes the wrong shape (refused only on submit, §4.1); a value
`set` on mount that loops with an event mapping (§3.1); the component's look in read-only and invalid state; a key
the field reads that no section writes (it only ever reads its default); a rule or method the field calls that the
form's visitors may not run; every runtime error in your scripts.

---

## 10 · Done when

- [ ] §1 answered — no stock control draws this input
- [ ] The binding is complete (scope, context, CRUD, `fieldExpression`) and `dataClass` is a §2.1 class
- [ ] `fieldModel.types` declares every type the script handles — the bound one included
- [ ] `properties.html` is not empty; every class is under one component prefix
- [ ] The script draws from `ctx.field.value` on every render and writes ONLY user changes with `ctx.field.set`
      (no `set` on mount); a stream of edits uses `{silent: true}` + `commit()`
- [ ] "Nothing picked" writes `null`, not `{}` / `[]`
- [ ] `ctx.field.readOnly` is honoured — no interaction while prohibited
- [ ] `ctx.field.errors` (or the `dokie-field-invalid` class) is drawn
- [ ] Event mappings on this field use `eventName: "change"`
- [ ] Every knob an author sets per field is a settings section key (§5) — with a default in `sectionModel`, read in
      the field with `ctx.settings.get(key, fallback)`; nothing secret is in the settings
- [ ] Rules, CRUDs, fields and methods are PICKED in a section (`data-catalog`) and called by the field; an
      unconfigured field draws a note instead of failing
- [ ] `mrjun.py validate` shows none of the §9 warnings
- [ ] Live-tested through the component, asserted on the stored record (§8)

---

**See also:** [24](24-html-component-studio.md) (the component: studioModel, `ctx`, lifecycle) ·
[02](02-form-controls-reference.md) (settings, binding, validation, events — unchanged here) ·
[24a](24a-theming-and-dark-mode.md) (CSS) · [24b](24b-html-composition-and-plugin-tags.md) (`<plugin>` tags) ·
[03](03-generate-fields-from-crud.md) (the slot and label a field sits in) · [32](32-public-api.md) (the field
through the API) · [30](30-live-test-bugfix-and-autotest.md) (testing) · [`tools/README.md`](tools/README.md)
(`node set-field-model`, `node set-section-model`, `node set-studio`, `validate`)
