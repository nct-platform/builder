# Generate fields from CRUD dialog

> 📐 **Field evidence — the generated field slot as it ships:** [04-forms-actions-validation.md](references/04-forms-actions-validation.md) · [10-visual-design.md](references/10-visual-design.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.


## ⛔ Wrap the generated row in `.container` — or the form spans the whole screen

Generate-Fields emits one `nct.html.plugin` per row holding only a Bootstrap **row**:

```html
<div class="row">
  <div class="col-md-3"><plugin id="gen_col1_8f5b9729" name="nct.parsis.plugin"></plugin></div>
  …
</div>
```

A bare `.row` inherits the page width, so on a wide monitor the controls stretch from edge to
edge and a four-field form reads as four lonely inputs 1400px apart. Wrap it:

```html
<div class="container">
  <div class="row">
    <div class="col-md-3"><plugin id="gen_col1_8f5b9729" name="nct.parsis.plugin"></plugin></div>
    …
  </div>
</div>
```

`.container` gives the form a max-width and centres it. The column split stays yours to choose —
`col-md-3` ×4 for a dense register form, `col-md-4` ×3 or `col-md-6` ×2 for a short one; decide by
how many fields the form actually has, not by what the generator emitted.

> The `<plugin id=…>` tags are found anywhere in the markup (`AbstractHtmlPlugin` takes every
> `<plugin>` element with no `<plugin>` ancestor), so adding wrapper `<div>`s around them is safe —
> the slot ids keep resolving against the node's children. Just never rename an `id`: that string
> **is** the child's `identifier` ([01](01-content-model-and-pages.md#-identifier-vs-uniqueidentifier--read-this-before-you-reference-a-node)).

Measured on a delivered project: **45 generated form rows, 0 wrapped** — every form in it spanned
the full width until the wrapper was added.

---

## What it is / when to use

"**Generate fields from CRUD**" is a dialog in Site Authoring that **bulk-creates form-controls**
inside a form by reading the CRUD's fields (dtoFields for dynamic, the `@Crud` bean for static) and unfolding them into a
multi-column grid of labelled controls. This is the primary way to populate a form: instead of manually adding
each `<plugin>` and its `settings` JSON, the user ticks the fields they want, picks a control type
(Text field / Dropdown / Date picker / …) and hits **Generate** — the dialog produces a ready-made content subtree
inside the form.

> ⛔ **HARD RULE when you author a form BY HAND (not through the dialog): the field subtree MUST live under a
> DIRECT child `nct.parsis.plugin` whose `identifier` is EXACTLY `"form.parsis"`.** `FormPlugin` renders its
> fields only into that anchor — `new PluginWrapperOfContentPanel("content", getContent(), "nct.parsis.plugin",
> "form.parsis")` (`FormPlugin.java`, `FormFieldsGenerator.java ensureFormParsis`). If you put the
> `gen_row/gen_col/gen_slot/label/field` tree under a **random-uuid** parsis instead, the plugin **creates a
> fresh EMPTY `form.parsis`** next to it and **the form renders with NO fields** — a silent, data-shaped bug
> (the fields ARE in the export, they just never show; the page looks blank at `…/form-<name>`). The **filter
> form** is the same with its own anchor: `dynaform.filter.form.plugin` → a direct child
> `nct.parsis.plugin` `identifier="filter.parsis"` (`FilterFormPlugin.java`). `form.parsis`/`filter.parsis`
> are **symbolic ids that repeat across pages** (like `left-nav`/`header`) — keep them verbatim, never
> uuid-regenerate them (`content_cmds.regen_ids` already preserves them). `mrjun.py validate` now ERRORs when a
> form/filter plugin has field controls not anchored under its canonical parsis.

> **🔧 Tooling.** For these entities, run the [`tools/mrjun.py`](tools/mrjun.py) commands instead of hand-writing
> JSON: `node add` (form-field plugins under a form), `node patch-settings` (editing generated settings).
> The Generate-fields dialog as such is not reproduced by the CLI — fields are added as individual `node add` calls.
> Full index and rules — [`tools/README.md`](tools/README.md); before re-importing — `mrjun.py validate`.

For Step-2 (generating the export by hand) this doc is the **exact specification of what content
result** the dialog produces: which wrapper HTML (`<div class="mb-3">` / `col-md-*` / outer wrapper),
which label-node + field-node, which id scheme (`lbl_gen_slot_*` / `fld_gen_slot_*` / `gen_row_*` /
`gen_col*_*` / `gen_full_*`), and how each dialog column (Layout / Required / Prohibited / Default /
Info / localize) maps into the settings of the generated control. **If you write `branches.json` by hand —
reproduce exactly this structure, and the form will render the fields the same as if the dialog had generated them.**

The "how to make a dropdown / autocomplete / date field" instructions link right here. Related docs:
- rendering and settings JSON of each control individually — [02-form-controls-reference.md](02-form-controls-reference.md);
- content model, `properties`, typed property slots — [01-content-model-and-pages.md](01-content-model-and-pages.md);
- form-groups and forms where the result lands (`form.parsis` lives inside the form-page content node) — [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md);
- the RIMM rule for choices dropdown/autocomplete, contexts / `crudAliases` (what stands behind `contextIdentifier` + `crudAlias`) — [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md);
- the **choices-rule conversion contract** (a dropdown/autocomplete choices rule MUST end in `service.global.conversion.toSelectOptions[Localized]` / `toAutoCompleteOptions` — a raw `findAll` renders blank + hides Show Nav), the **partial-`findAll` untyped-`$1` trap**, the **searchable-dropdown pipeline** (`acFindAllBy<X>Like`) and **localized labels** — [02-form-controls-reference.md §4a](02-form-controls-reference.md);
- where the field list comes from (dtoFields dynamic CRUD) — [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md).

> **Static vs dynamic.** The generator is identical for both styles — it operates only on `contextIdentifier` +
> `crudAlias` + `fieldExpression` (both appear in the examples below). The only difference is
> the **source of the field list** (static: reflection over the Java DTO; dynamic: `dtoFields` from
> `dynamic-cruds.json`) and the `dataClass` (static: a real Java FQN like `com.devsegment.erp.dto.enums.CountType`;
> dynamic: platform types — `java.lang.String`, `java.lang.Integer`, `java.time.LocalDate`, `ObjectNode`).
> The generated content structure is **the same**.

> **⚠️ There is no `fieldType` field.** Older platform documentation on form fields describes a form field
> through an imaginary model `fieldType: TEXT/NUMBER/DATE/DATETIME/DROPDOWN/AUTOCOMPLETE/CHECKBOX/FILE/LIST/…`
> **This field is NOT present in the settings classes or in the export.** The "field type" = the node control's
> **`pluginName`** (`dynaform.form.text.field.plugin`, …). Numeric input = a Text field with a numeric `dataClass`; date/datetime/instant =
> a **single** datepicker plugin, distinguished by `dataClass` + `dateFormat`; checkbox/number/datetime plugins do
> not exist at all. Do not carry fabricated settings from those docs into the export (`maxLength`, `min`, `step`, `prefix`,
> `minSearchLength`, `minDate`, `maxFiles`, `checkedValue`, `dependsOnField`, …) — none of them exist in the code
> (verified by grep over `nct-dynaform`/`nct-ui`). The single source of truth is the
> settings classes listed in [02-form-controls-reference.md](02-form-controls-reference.md).

## Export shape — what actually gets produced in `branches.json`

One **Generate** call (one "batch") creates a short 8-hex `batchId` (`shortUuid()`,
`FormFieldsGenerator.java`) and splices content **inside** the form's canonical parsis
(`identifier = "form.parsis"`, `pluginName = "nct.parsis.plugin"`). The recursive node structure
(see [01-content-model-and-pages.md](01-content-model-and-pages.md)):

```
form.parsis                       nct.parsis.plugin            (the form's canonical parsis)
 ├─ gen_row_<batch>               nct.html.plugin              (one per batch; HTML = row+cols)
 │   └─ gen_col<N>_<batch>        nct.parsis.plugin            (N = 1..cols; one per column)
 │       └─ gen_slot_<batch>_<col>_<i>   nct.html.plugin       (HTML = <div class="mb-3">…)
 │           ├─ lbl_gen_slot_<batch>_<col>_<i>   nct.label.plugin   (text = LOCALIZED_STRING map)
 │           ├─ help_gen_slot_<batch>_<col>_<i>  nct.help.plugin    (helpSettings JSON — OPTIONAL)
 │           └─ fld_gen_slot_<batch>_<col>_<i>   <control plugin>   (settings JSON)
 └─ gen_full_<batch>_<i>          <control plugin>             (full-width; NO label/help/wrapper)
```

The key invariant: each `<plugin id="…" name="…">` marker carries **TWO** load-bearing attributes — its
`id` **exactly matches** the `identifier` of the corresponding child node, **AND** its `name` **exactly matches
that child node's `pluginName`**. The Jsoup pass of the html plugin during rendering
(`AbstractHtmlPlugin.constructListModel`) finds the `<plugin>` at any depth and reuses the
already-created child node by matching `identifier`, rather than creating a duplicate
(`FormFieldsGenerator.java`). **If you write the export by hand — both the id AND the name in the HTML must
match the node's `identifier` AND `pluginName`.**

> ⛔ **A missing or mismatched `name` on a `<plugin>` marker CLEARS the matched child's settings at render time —
> import-clean, renders-blank.** On an `id` hit whose stored `pluginName` differs from the marker's `name`,
> `PluginUtils.getOrCreateChildContent` (`…/cms/kicker/utils/PluginUtils.java`) does
> `child.getProperties().clear(); child.setPluginName(name)` — **wiping the field's `settings`**
> (`contextIdentifier`/`crudAlias`/`fieldExpression`/`ruleIdentifier`/…) — then rebuilds the plugin from the
> now-empty node. The render path reads the marker `name` (`AbstractHtmlPlugin.constructListModel`
> `name = plugin.attr("name")` → `getOrCreateChildContentComponent`). Result: the control renders as a
> **blank, unbound field**, or **`Not valid plugin `** when the name is blank/unknown. **What validate does and does
> not catch:** `mrjun.py validate` DOES read the marker's `name` and **ERRORs** when it disagrees with the child
> node's stored `pluginName` — that is the type-swap trap. What it cannot catch is a marker carrying **no `name`
> attribute at all**: with nothing to compare against, it passes validate/coverage/crud-verify and only breaks on
> the rendered page. So every `fld_*`/`lbl_*`/`help_*`/`gen_col*` marker MUST spell out
> `name="<the child's pluginName>"` verbatim (e.g.
> `name="dynaform.form.text.field.plugin"`, `name="nct.label.plugin"`, `name="nct.parsis.plugin"`).

> **What you will typically see in an export.** A form-heavy project is mostly `gen_row_*` batches with
> `fld_gen_*` field-nodes under them; a project whose forms were all hand-authored has none at all. Two shapes are
> rare in practice and worth knowing about before you look for them: **`gen_full_*` nodes** (they only appear when a
> full-width control — File upload / List / Comments / Gantt — is generated) and a **generated autocomplete**
> (hand-authored autocompletes are the norm: their `identifier` is a UUID rather than `fld_gen_*`, and they use
> `key != displayName`, so they do not follow the generator's `key==display` invariant). Variant C (autocomplete)
> below is therefore documented from the code — the full `AutoCompleteRimmRuleHelper` pipeline
> (`nct-ui/.../dynaform/form/controls/autocomplete/AutoCompleteRimmRuleHelper.java`) — rather than from a
> generated node. Variant D (full-width) is **how any non-wrapper control renders** — it is the
> `build` step-4 code path (`FormFieldsGenerator.java`), not a speculative shape.

### Worked example: root row `gen_row_*` (default 4 columns)

A generated row node `gen_row_025f62d5`. The value lives in `properties.html.stringValue` (the property
key is the lowercase **`html`**, and `HtmlPlugin.HTML = "html"` — confirmed from the source
`HtmlPlugin.java`):

```html
<div class="row">
  <div class="col-md-3">
    <plugin id="gen_col1_025f62d5" name="nct.parsis.plugin"></plugin>
  </div>
  <div class="col-md-3">
    <plugin id="gen_col2_025f62d5" name="nct.parsis.plugin"></plugin>
  </div>
  <div class="col-md-3">
    <plugin id="gen_col3_025f62d5" name="nct.parsis.plugin"></plugin>
  </div>
  <div class="col-md-3">
    <plugin id="gen_col4_025f62d5" name="nct.parsis.plugin"></plugin>
  </div>
</div>
```

### Worked example: slot `gen_slot_*` (label + field, no mandatory/help — "flat" form)

Node `gen_slot_025f62d5_0_0` of the same batch (`properties.html.stringValue`):

```html
<div class="mb-3">
  <plugin id="lbl_gen_slot_025f62d5_0_0" name="nct.label.plugin"></plugin>
  <plugin id="fld_gen_slot_025f62d5_0_0" name="dynaform.form.rimm.drop.down.field.plugin"></plugin>
</div>
```

Its children:
- `lbl_gen_slot_025f62d5_0_0` (`nct.label.plugin`);
- `fld_gen_slot_025f62d5_0_0` (`dynaform.form.rimm.drop.down.field.plugin`).

## Per-variant reference

### 1. `gen_row_<batch>` — root row (html plugin)

- **pluginName**: `nct.html.plugin`.
- **identifier / name**: `gen_row_<batch>` (the generator sets `name = identifier`, `createPluginContent`,
  `FormFieldsGenerator.java`).
- **`properties.html.stringValue`** (`PropertyType.STRING`, key `"html"`): the result of `buildRootRowHtml`
  (`FormFieldsGenerator.java`):
  - without a wrapper class → the string begins with `<div class="row">`, containing N blocks
    `<div class="col-md-(12/N)"><plugin id="gen_colK_<batch>" name="nct.parsis.plugin"></plugin></div>`.
  - with a wrapper class → a **separate** `<div class="<wrapperClass>">…</div>` is placed on top around the row.
    The **typical value is `container`** (Bootstrap `.container` — centers the grid with a responsive max-width +
    gutters so the fields aren't edge-to-edge); `container-fluid` for full-width; blank → the bare `.row`.
- **children**: exactly `cols` nodes of `nct.parsis.plugin` with ids `gen_col1_<batch>` … `gen_col<cols>_<batch>`.
- Generated **only if there is at least one wrapper-style spec** (otherwise there is no row — only `gen_full_*`).

Column counts and their `col-md-*` (`columnWidthClass`, `FormFieldsGenerator.java`
`normalizeColumns`):

| N (Layout) | class of each column | column ids |
|---|---|---|
| 1 | `col-md-12` | `gen_col1_<batch>` |
| 2 | `col-md-6` | `gen_col1..2_<batch>` |
| 3 | `col-md-4` | `gen_col1..3_<batch>` |
| 4 (default) | `col-md-3` | `gen_col1..4_<batch>` |
| 6 | `col-md-2` | `gen_col1..6_<batch>` |
| 12 | `col-md-1` | `gen_col1..12_<batch>` |

The Layout dropdown in the dialog header offers {1,2,3,4,6} (`layoutColumns = List.of(1, 2, 3, 4, 6)`,
`GenerateFieldsFromCrudDialog.java`), but `normalizeColumns` additionally accepts `12`; any other N →
fallback to 4 (`FormFieldsGenerator.java`). **The default and by far the most common choice is `4`**
(→ `col-md-3`, four fields per row); use it unless the PRD/layout calls for wider single-column fields (`1` →
`col-md-12`) or a denser grid.

### 2. `gen_col<N>_<batch>` — column (parsis plugin)

- **pluginName**: `nct.parsis.plugin`; **identifier/name**: `gen_col<N>_<batch>` (N from 1).
- **almost no properties** (an ordinary parsis container).
- **children**: 0..M slots `gen_slot_<batch>_<col>_<i>` (`col` is 0-indexed: `gen_col1` holds `…_0_*`).
- **Round-robin layout** (`FormFieldsGenerator.java` inside `build`): the spec at index `j` goes
  into column `j % cols` at position `j / cols`. So for 5 fields in 4 columns: col0 gets spec 0 and 4, col1 —
  spec 1, col2 — spec 2, col3 — spec 3.

### 3. `gen_slot_<batch>_<col>_<i>` — slot (html plugin)

- **pluginName**: `nct.html.plugin`; **identifier/name**: `gen_slot_<batch>_<col>_<i>`, where
  `col` = column index (0-based), `i` = position within the column (0-based).
- **`properties.html.stringValue`**: the result of `buildLabelledSlotHtml` (`FormFieldsGenerator.java`):
  - **flat** (neither mandatory nor help): `<div class="mb-3">` → `<plugin id="lbl_…">` → `<plugin id="fld_…">`.
  - **flex-header** (mandatory and/or help): inside `mb-3` — `<div class="d-flex align-items-center
    justify-content-between">` with `<span class="d-inline-flex align-items-center"><plugin id="lbl_…"/> [<span
    class="red ms-1">*</span>]</span>` and (if help) `<plugin id="help_…"/>` on the right; then `<plugin id="fld_…"/>`.
- **children** (in this order): `lbl_<slot>` (always), `help_<slot>` (if Info is filled), `fld_<slot>` (always).

**Mandatory slot** (`gen_slot_b8035f65_0_0`):

```html
<div class="mb-3">
  <div class="d-flex align-items-center justify-content-between">
    <span class="d-inline-flex align-items-center">
      <plugin id="lbl_gen_slot_b8035f65_0_0" name="nct.label.plugin"></plugin>
      <span class="red ms-1">*</span>
    </span>
  </div>
  <plugin id="fld_gen_slot_b8035f65_0_0" name="dynaform.form.rimm.drop.down.field.plugin"></plugin>
</div>
```

**Help slot** (`gen_slot_b8035f65_0_2`):

```html
<div class="mb-3">
  <div class="d-flex align-items-center justify-content-between">
    <span class="d-inline-flex align-items-center">
      <plugin id="lbl_gen_slot_b8035f65_0_2" name="nct.label.plugin"></plugin>
    </span>
    <plugin id="help_gen_slot_b8035f65_0_2" name="nct.help.plugin"></plugin>
  </div>
  <plugin id="fld_gen_slot_b8035f65_0_2" name="dynaform.form.text.field.plugin"></plugin>
</div>
```

> **🔑 The red `*` and the help "?" are CONTENT you author — NOT runtime effects of the settings.** This is the
> single easiest thing to get wrong when hand-authoring (the dialog does all of it at once; a by-hand edit must too):
> - **Mandatory `*`:** `settings.alwaysMandatory:true` only makes the field *validate* as required — it renders **no**
>   asterisk. The visible `*` is the literal `<span class="red ms-1">*</span>` you place in the slot's **flex-header**
>   HTML (above). A **flat** slot carrying only `alwaysMandatory:true` is a required field with **no visible `*`** (it
>   still blocks submit — the star is just missing).
> - **Help "?":** there is **no** `infoText`/help key on a control — `infoText` is only the dialog's intermediate
>   field. A help "?" is a **separate `nct.help.plugin` `help_*` node** (its `helpSettings` carries the localized
>   `message`, §5) placed inside the flex-header. A help message with no `help_*` node renders nothing.
>
> So to make a field **visibly required and/or helped by hand you must do BOTH** — set the setting **and** author the
> slot content: (1) build the slot as **flex-header** (not flat, 2) add the `*` span for mandatory, (3) add the
> `help_*` node for help. (The **Prohibited** and **Default** flags, by contrast, ARE pure settings — no slot-HTML
> change; §"Mapping of dialog columns".)

### 4. `lbl_gen_slot_<batch>_<col>_<i>` — label (label plugin)

`nct.label.plugin`; `identifier/name = lbl_<slot>`. Three properties (`addLabelledControl`,
`FormFieldsGenerator.java`). The **full** property slot `text` (here on
`lbl_gen_slot_025f62d5_0_0`) contains, besides `key/propertyType/localizedStringValue`, also
`fieldPanelClass/arguments/required/hidden` — like any typed property slot:

```json
{
  "text":      { "key": "text", "propertyType": "LOCALIZED_STRING",
                 "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseLocalizedTextFieldPanel",
                 "arguments": {}, "required": false, "hidden": false,
                 "localizedStringValue": { "en_US": "Lot" } },
  "tagName":   { "key": "tagName",   "propertyType": "STRING", "stringValue": "label",      "localizedStringValue": {} },
  "className": { "key": "className", "propertyType": "STRING", "stringValue": "form-label",  "localizedStringValue": {} }
}
```

> The full form of a property slot (`fieldPanelClass/arguments/required/hidden` + typed `*Value`) — see
> "Step 6" below and [01-content-model-and-pages.md](01-content-model-and-pages.md). Annotation of the values:
>
> _Note:_ the generator makes three `setProperty` calls (`text`/`tagName`/`className`), but the
> persisted node has **five** slots — `LabelPlugin` glues on its
> empty defaults `styleName`/`tagProperties` (`""`). A hand-assembled node can safely omit them.

| property | type | value | backing |
|---|---|---|---|
| `text` | `LOCALIZED_STRING` (map `locale.toString()` → text) | per-locale caption; the full `spec.localizedLabel` (auto-translated into all tenant locales) or fallback `{defaultLocale: displayName}` | `setProperty("text", map, LOCALIZED_STRING)`, `FormFieldsGenerator.java` |
| `tagName` | `STRING` | always `"label"` | |
| `className` | `STRING` | always `"form-label"` | |

The `fieldPanelClass` for `text` = `PropertyBaseLocalizedTextFieldPanel`, for `tagName`/`className` =
`PropertyBaseTextFieldPanel`.

### 5. `help_gen_slot_<batch>_<col>_<i>` — help icon (optional)

`nct.help.plugin`; `identifier/name = help_<slot>`. Created **only** when `spec.infoText` is non-empty
(`hasHelp`, `FormFieldsGenerator.java`). The message is placed into `HelpPluginSettings` under the key
`"message"` as a localized map, then the whole bean is serialized into the JSON property `helpSettings`. Three "service"
keys come from the **defaults** of `HelpPluginSettings`, not set by the generator:
`alwaysVisible=true`, `showMessageOn=CLICK` (confirmed at `HelpPluginSettings.java`
`needToBeSaved=false` — also a default, present in the serialized JSON). The **full** property slot
`helpSettings` (here on `help_gen_slot_b8035f65_0_2`):

```json
{
  "key": "helpSettings",
  "propertyType": "STRING",
  "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
  "arguments": {}, "required": false, "hidden": false, "localizedStringValue": {},
  "stringValue": "{\"alwaysVisible\":true,\"showMessageOn\":\"CLICK\",\"needToBeSaved\":false,\"localizedMap\":{\"message\":{\"ru_RU\":\"ДОЛЯ, а не %: 0,15 = 15%; точность 5, масштаб 4\",\"hy_AM\":\"ԲԱԺԻՆ, ոչ թե %՝ 0.15 = 15%; ճշգրտություն 5, մասշտաբ 4\",\"en_US\":\"SHARE, not %: 0.15 = 15%; precision 5, scale 4\"}}}"
}
```

The unpacked `stringValue`:

```json
{
  "alwaysVisible": true,
  "showMessageOn": "CLICK",
  "needToBeSaved": false,
  "localizedMap": {
    "message": {
      "en_US": "SHARE, not %: 0.15 = 15%; precision 5, scale 4",
      "ru_RU": "ДОЛЯ, а не %: 0,15 = 15%; точность 5, масштаб 4",
      "hy_AM": "ԲԱԺԻՆ, ոչ թե %՝ 0.15 = 15%; ճշգրտություն 5, մասշտաբ 4"
    }
  }
}
```

The reverse reader extracts the message from `helpSettings.localizedMap.message`
(`GeneratedFieldReader.java` — `readHelpMessage`). When assembling by hand, put `message` into **all** tenant
locales (the generator seeds them via `LocalizeService.seedLocalizedNames`); write the other three keys verbatim
(these are defaults).

> **What it renders — the question-mark help icon.** `nct.help.plugin` draws a small **help icon to the RIGHT of
> the label** (the flex-header slot of §3): `HelpPlugin.html` = `<span class="nct-help-icon"><i class="pe-7s-help1"></i></span>`
> — the Pe-7-stroke **`pe-7s-help1`** ("?") glyph (also the plugin's palette icon, `HelpPlugin.java`
> `@NctPlugin(icon="pe-7s-help1")`). Clicking the icon (or hovering, when `showMessageOn:"HOVER"`) shows the
> localized `message` in a **JS-built floating popup** `div.nct-help-popup` appended to `<body>`, positioned
> above/below the icon, driven by the help plugin's own settings — the message, the trigger, whether it is
> always visible, and the parent selector it anchors to. ⚠️ **It is NOT a Wicket
> modal** — the `400px` width you may see configured sizes the **authoring** edit-panel modal, not the runtime
> message. When `alwaysVisible:false` **and** `parentSelector` is set, the icon stays `display:none` until the
> closest ancestor matching `parentSelector` is hovered (reveal-on-parent-hover; authorable in the Help settings
> panel — the field-generator never sets `parentSelector`). A `message` in a locale missing from
> `localizedMap.message` triggers a **live nct-localization auto-translate on render** (`message()` → `getLocalized`
> → `MicroserviceTranslatedLocalizedBean` → `LocalizeService.translatePure` → `LocalizationClient`), so **seed all
> tenant locales** to avoid per-render translation calls. `HelpPluginSettings` has **three own fields** —
> `alwaysVisible` (default `true`), `showMessageOn` (default `CLICK`), `parentSelector` (default
> `null` — the generator never sets it, so it is **absent** from every generated node) — plus, inherited from its
> localized base bean, the `localizedMap` (`LocalizedBean.getLocalizedMap()`, keyed `field → {locale → text}`, here
> `message`) and `needToBeSaved` (default `false`, `MicroserviceTranslatedLocalizedBean.java`). So a generated
> help node carries exactly `{alwaysVisible, showMessageOn, needToBeSaved, localizedMap.message}` — the JSON above;
> nothing else is emitted.

### 6. `fld_gen_slot_<batch>_<col>_<i>` — the control itself (field plugin)

`pluginName` = one of the supported controls (see the table below); `identifier/name = fld_<slot>`.
The only meaningful property is `settings` (`PropertyType.STRING`, key `"settings"`), which holds
the **JSON string** of the control's settings object. Full description of each settings class and its rendering —
[02-form-controls-reference.md](02-form-controls-reference.md); here — how exactly the generator fills it.

#### Common settings fields (`populateBaseSettings`, `FormFieldsGenerator.java`)

All controls inherit `FormControlSettings` (extends `FilterControlSettings`; scope enum
`FormControlScope {GLOBAL, CONTEXT, CRUD}` — see [02-form-controls-reference.md](02-form-controls-reference.md)).
The generator always sets:

| settings key | type | value | required | default (on generation) | backing setter |
|---|---|---|---|---|---|
| `scope` | enum `FormControlScope` (string) | `CRUD` in a form; for nested list-item — the parent list's scope. **Not a free choice on a CRUD-mode form:** on a form opened from a CRUD-table/tree ACTION the runtime binds every control to that table's `contextIdentifier`+`crudAlias` whatever is persisted here, so write `CRUD` + the table's pair on every top-level control (a persisted GLOBAL/CONTEXT does not keep the value out of the row — it only makes the export disagree with runtime). **Nested list-item controls are the exception** — the re-binding never reaches into a nested form, so they keep the parent list's scope with `__temp_list_item_context__` / `__temp_item__`. GLOBAL/CONTEXT are correct only on forms opened WITHOUT a row (workflow user task, ProcessTable start/global action). | yes | `CRUD` | `setScope`|
| `contextIdentifier` | String (context **UUID**; for nested — `"__temp_list_item_context__"`) | binding to the context | yes | — | `setContextIdentifier`|
| `crudAlias` | String (CRUD alias; for nested — `"__temp_item__"`) | binding to the CRUD | yes | — | `setCrudAlias`|
| `fieldExpression` | String | path to the field (`countDate`, `plant.id`, `categoryId`, `declarationNo`, `counterparty.id`) | yes | — | `setFieldExpression`|
| `dataClass` | String (FQN) | value type; `spec.dataClassName` is preferred, otherwise `fieldClass.getName()` | yes | — | `setDataClass`|
| `name` | String | "human" name (= label by default) | yes | = displayName | `setName`|
| `filterKey` | String | mirrors `fieldExpression` (for page-parameter prefill) | yes | = `fieldExpression` | `setFilterKey`|
| `alwaysMandatory` | Boolean | `true` if the Required tick; otherwise **null** (not written) | no | null | `setAlwaysMandatory`|
| `jsonNodeExpression` | String | path inside an ObjectNode field; otherwise null | no | null | |
| `jsonNodeValueType` | String (scalar FQN) | scalar type at `jsonNodeExpression`; otherwise null | no | null | |
| `enumName` | String | enum name (enum-dropdown only); otherwise not written. **The only controlled key of the enum trio** (`CONTROLLED_KEYS_COMMON`) | no | null | |
| `enumValues` | `Map<constantName, Map<propertyName, value>>` | wire-safe snapshot of the enum constants (enum-dropdown): outer key = the constant's `name()`, inner map = property→`toString()` value. Copied verbatim from `FieldDto.enumValues`. **NOT a controlled key** — preserved (not re-overlaid) on override | no | null | |
| `enumFieldNames` | `List<String>` | property names of the snapshot (`"name"` + declared props). Copied from `FieldDto.enumFieldNames`. **NOT a controlled key** | no | null | |
| `defaultValue*` | see below | from the Default column; otherwise all null | no | null | `applyDefaultSpec`|
| `prohibitedPredicateIdentifier` | String (predicate UUID) | from the Prohibited column (Custom); otherwise null | no | null | |
| `alwaysProhibited` | Boolean | `true` if Prohibited=Always (rule-free); otherwise null | no | null | |

**⚠️ `contextIdentifier` is a UUID**, not a human-readable name. The conceptual docs show
`"service"`/`"orderContext"`; in a real export it is `"77cd568d-75b0-48e7-8fcc-d760b3a06219"` etc. Write the UUID
of an existing context (`rep-objects.contexts[].identifier`, see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)).

Also, the persisted JSON always contains the base-class defaults that the generator explicitly does **not** touch:
`mandatoryValidationMessages: {}`, `eventComponentMappings: []`, `conditionalValidations: []` (visible in all
the real examples below). In a by-hand export you can include them as empty — that is what the real runtime does too.

#### Supported controls and their field types (`buildControlSupport`, `GenerateFieldsFromCrudDialog.java`)

This is the **full and exact** set of 9 plugins that the generator writes as `ContentDomain.pluginName`
(labels from `buildControlLabels`). The "field type" = the `pluginName`, NOT a separate `fieldType` field.

| Control (UI label) | pluginName | wrapper-style? | valid Java field types (`supportedDataClasses`) |
|---|---|---|---|
| Text field | `dynaform.form.text.field.plugin` | ✅ grid | String, Integer, Long, Short, Byte, Float, Double, BigDecimal, BigInteger, Boolean, ObjectNode |
| Dropdown | `dynaform.form.rimm.drop.down.field.plugin` | ✅ grid | String, Integer, Long, Short, Float, Double, Boolean, ObjectNode, **Enum** |
| Autocomplete | `dynaform.form.rimm.autocomplete.field.plugin` | ✅ grid | String, Integer, Long, Short, Float, Double, Boolean, ObjectNode (offered in the UI row **only when the field class == String**) |
| Date picker | `dynaform.form.datepicker.field.plugin` | ✅ grid | Instant, LocalDate, LocalDateTime, ObjectNode |
| Text area | `dynaform.form.textarea.field.plugin` | ✅ grid | String, ObjectNode |
| File upload | `dynaform.form.file.upload.field.plugin` | ❌ full-width | ArrayList, ObjectNode |
| List | `dynaform.form.list.field.plugin` | ❌ full-width | ArrayList, ObjectNode |
| Comments | `dynaform.form.comments.field.plugin` | ❌ full-width | ObjectNode |
| Gantt chart | `dynaform.form.gantt.chart.plugin` | ❌ full-width | ObjectNode |

The first five (`WRAPPER_STYLE_PLUGINS`, `FormFieldsGenerator.java`) go into the column grid with a label; the other
four are full-width `gen_full_*` without label/help/wrapper.

> **`Byte`, `BigDecimal`, `BigInteger` are accepted only by Text field** (`buildControlSupport`,
> `GenerateFieldsFromCrudDialog.java`) — a field of one of those types therefore has Text field as its
> single compatible control (and thus its default). Dropdown/Autocomplete/Date-picker/Text-area do **not** list them.

> **⚠️ The generator produces a SUBSET of the form controls.** The plugins `dynaform.form.tree.picker.plugin`
> (treepicker) and `dynaform.form.groups.plugin` **exist** in the platform, but
> the Generate dialog does **not** produce them (they are not in `buildControlSupport`) — such controls are assembled by hand (see
> [02-form-controls-reference.md](02-form-controls-reference.md)). Number/datetime/checkbox plugins do not
> exist at all: numeric input = a Text field with a numeric `dataClass`; date, datetime and instant are a **single**
> datepicker plugin (the distinction is via `dataClass` LocalDate/LocalDateTime/Instant + `dateFormat`); Boolean
> is rendered through a Text field (Boolean is in its type list).

#### Variant A — Text field / Text area / Date picker (basic scalar)

Settings = a plain `FormControlSettings` (no extra fields). Worked examples:

Date picker (`fld_gen_slot_…`, `dynaform.form.datepicker.field.plugin`, on a static `inventoryCount` CRUD):
```json
{
  "scope": "CRUD",
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "inventoryCount",
  "fieldExpression": "countDate",
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  "name": "Count Date",
  "filterKey": "countDate",
  "dataClass": "java.time.LocalDate"
}
```

Text field (`dynaform.form.text.field.plugin`, on a dynamic CRUD — note `localized: true`,
which comes from the dtoField, not from the generator; enabling it has **two prerequisites** — the parent form
must be multi-language AND the CRUD must have a `@LocalizationField` ObjectNode column, the settings-panel guard
`FormControlSettingsControlPanel.java`, see [02-form-controls-reference.md](02-form-controls-reference.md)
"Localized fields" and [20-localization.md](20-localization.md)):
```json
{
  "scope": "CRUD",
  "contextIdentifier": "871f974f-e775-401a-adfc-e822110f3b99",
  "crudAlias": "product_categories_cruid",
  "fieldExpression": "name",
  "localized": true,
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  "name": "Name",
  "filterKey": "name",
  "dataClass": "java.lang.String"
}
```

> `dateFormat` (the datepicker's only own setting, `DatePickerFilterControlSettings.dateFormat`)
> the generator does **not** set (it inherits the control's default) — a *generated* datepicker has the key absent
> entirely. An explicit value such as `"DD/MM/YYYY"` / `"DD/MM/YYYY HH:mm"` (Moment.js) therefore marks a
> **hand-assembled** datepicker, not a generated one.

#### Variant B — Dropdown (rule-driven choices)

Settings = `FormControlRimmDropDownFieldSettings` (`applyFormControlSettings`, `FormFieldsGenerator.java`).
Its own hierarchy: `FormControlRimmDropDownFieldSettings extends DropdownFilterControlSettings`; the class's own fields
are `rowsInPage`, `searchEnabled`, `searchField`, `prevRuleIdentifier`, `searchRuleIdentifier`;
`ruleIdentifier`/`key`/`displayName` are inherited from `DropdownFilterControlSettings`. On top of the base fields the generator
sets:

| key | value | backing |
|---|---|---|
| `ruleIdentifier` | UUID of the execution-rule that returns the option list (`RIMM_<alias>_<key>_<display>`); generated/found in `ensureRimmRule` | `setRuleIdentifier` |
| `key` | source field whose value is stored in the form (default `"id"`). Must be **class-compatible with the FK field's Java class** (`keyFieldsForCrud` filters the source-CRUD columns by class, `GenerateFieldsFromCrudDialog.java`; `defaultKeyField` prefers `id`) — e.g. an `Integer categoryId` can only bind to an `Integer` key column | `setKey` |
| `displayName` | source field shown as the option caption (default `name`/`title`/`label`/`displayName`) | `setDisplayName` |
| `searchEnabled` | `false` (the generator does not enable search mode) | inherited default |
| `showNav` | `false` | inherited default |

> A freshly generated dropdown carries **no** `rowsInPage`, `searchField`, `prevRuleIdentifier`,
> `searchRuleIdentifier` — the generator never sets them (`FormFieldsGenerator.java`); search-enabled mode
> is a post-generation settings-panel edit. Only `ruleIdentifier`/`key`/`displayName` are the dropdown-specific
> controlled keys (`CONTROLLED_KEYS_DROPDOWN`). The `fieldExpression` is the **raw FK column** taken
> verbatim from the field list (`r.getExpression()`) — there is no `ref.id`/`ref.code` reference-path
> synthesis; which *source* column supplies the stored value is `settings.key`, not the fieldExpression.

Worked example (dynamic — a dropdown whose choices come from another CRUD, `product_categories_cruid`):
```json
{
  "searchEnabled": false,
  "ruleIdentifier": "6c918898-beb1-4c19-897d-203e0e77d4c0",
  "key": "id",
  "displayName": "label",
  "showNav": false,
  "scope": "CRUD",
  "contextIdentifier": "871f974f-e775-401a-adfc-e822110f3b99",
  "crudAlias": "product_categories_cruid",
  "fieldExpression": "categoryId",
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  "name": "Category",
  "filterKey": "categoryId",
  "dataClass": "java.lang.Integer"
}
```

**RIMM rule** (`ensureRimmRule`, `GenerateFieldsFromCrudDialog.java`): name
`RIMM_<sourceCrudAlias>_<keyField>_<displayField>` (**reused** if it already exists), `ruleType =
EXECUTION_RULE`, `executor = GroovyExecutionRule`, `status = ACTIVE`, `hidden = false`, the body is placed into
`rule.ruleScriptStr`:
```groovy
def list = service.crud.<sourceCrudAlias>.find([
  rowsInPage: 1000,
  pageNumber: 0
])
return service.global.conversion.toSelectOptions(list, "<keyField>", "<displayField>")
```

> **⚠️ The `toSelectOptions` tail is load-bearing, and never filter with a partial map.** A choices rule MUST end by
> converting rows to option pairs — return a raw `find`/`findAll` entity list and the picker shows "No results found"
> **and** the Show-Nav affordance vanishes (`mrjun.py validate` now ERRORs on it). To NARROW the options do **NOT** add
> filter keys to this `find()`/`findAll()` call: a **partial** filter map (e.g. `findAll([active:"true",
> rowsInPage:1000])`) leaves the unbound column first appearing as `$1 IS NULL` → Postgres `could not determine data
> type of parameter $1`. Use `findAll([:])` (ALL keys absent = the safe no-filter call) or the searchable-dropdown
> pipeline (`acFindAllBy<X>Like`) — see [02-form-controls-reference.md §4a](02-form-controls-reference.md).

> **⚠️ Localized CRUD → `toSelectOptionsLocalized`.** The dialog always emits **plain** `toSelectOptions`, which reads
> the base column — so for a CRUD whose display field is localized (`@LocalizationField`/`localize` column,
> `settings.localized:true`) every label is stuck in the base locale (labels stay in the project's base locale)
> regardless of the UI language switcher. Post-edit the generated rule to `toSelectOptionsLocalized(list, "<keyField>",
> "<displayField>")` (session-locale labels). See [02-form-controls-reference.md §4a](02-form-controls-reference.md)
> "Localized labels".

That is, for a by-hand export each generated dropdown needs an object in `rep-objects.json.rules[]` (see
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)), and its `identifier` — in `settings.ruleIdentifier`.
The generator does **not** set `contextIdentifiers` — a freshly generated RIMM rule has `contextIdentifiers=[]`,
because the body `service.crud.<alias>.find(...)` does not depend on the context. The exception is a
**hand-tweaked** rule: once you edit the body so the options depend on the surrounding form (a dependent /
cascading dropdown — `attrs.get('filterBy')`, a `term:` filter, a `context.<ctx>…` read), the rule carries
exactly ONE context UUID in `contextIdentifiers` (e.g. `["77cd568d-75b0-48e7-8fcc-d760b3a06219"]` — the context's
`identifier`, never an ordinal like `[1]`).

#### Variant B′ — Enum-dropdown (rule-free)

When the field is an enum and the control is a Dropdown (`enumDropdownRow`, `doGenerate`), the generator does **not** set
`ruleIdentifier` (the runtime renders the constants itself) and writes instead `enumName` + a wire-safe snapshot
`enumValues`/`enumFieldNames` (for nested forms — mandatory, see Gotchas). `key`/`displayName` here are not
sources but enum properties: `key` = the enum property whose value is **stored** (blank → `name`; the runtime
always round-trips via `constant.name()` so `key` is largely informational), `displayName` = the property used
for the **option label**. **The option label is the `displayName` property value verbatim** — or the constant's
`name()` when `displayName` is blank / missing / null — **NOT** `"<value> (CONSTANT)"`
(`RimmDropDownFieldFormControlPlugin.formatEnumOption` and `formatEnumOptionFromData`; the in-code comment at `FormFieldsGenerator.java` claiming `"<value> (CONSTANT)"` is **stale**). Worked example
(a static `inventoryCount` CRUD with a `CountType` enum column):
```json
{
  "searchEnabled": false,
  "key": "name",
  "displayName": "displayName",
  "showNav": false,
  "scope": "CRUD",
  "contextIdentifier": "77cd568d-75b0-48e7-8fcc-d760b3a06219",
  "crudAlias": "inventoryCount",
  "fieldExpression": "countType",
  "enumName": "CountType",
  "mandatoryValidationMessages": {},
  "eventComponentMappings": [],
  "conditionalValidations": [],
  "name": "Count Type",
  "filterKey": "countType",
  "dataClass": "com.devsegment.erp.dto.enums.CountType"
}
```
(Here `enumValues` is not serialized, because this is a top-level enum of a static CRUD — the runtime takes the
constants from the project-enum-registry. For dynamic / nested you must add `enumValues` + `enumFieldNames` — see Gotchas.)

A **generated** enum-dropdown that *does* carry the snapshot (node `fld_gen_slot_f8e0ae95_3_0`,
enum `BomItemCategory` on a nested bill-of-materials line item — the outer key is the constant `name()`, the inner map is
`property → value`):
```json
{
  "searchEnabled": false, "key": "name", "displayName": "displayName", "showNav": false,
  "scope": "CRUD", "contextIdentifier": "…", "crudAlias": "…", "fieldExpression": "category",
  "enumName": "BomItemCategory",
  "enumFieldNames": ["name", "displayName"],
  "enumValues": {
    "STOCK":     {"name": "STOCK",     "displayName": "Stock Item"},
    "NON_STOCK": {"name": "NON_STOCK", "displayName": "Non-Stock Item"},
    "PHANTOM":   {"name": "PHANTOM",   "displayName": "Phantom/Assembly"},
    "SERVICE":   {"name": "SERVICE",   "displayName": "Service"},
    "TEXT":      {"name": "TEXT",      "displayName": "Text Item"}
  }
}
```
So the option list here renders as `Stock Item`, `Non-Stock Item`, … (the `displayName` values verbatim), and the
stored value is the constant name (`STOCK`, …).

> **`dataClass` = real enum FQN, NOT `dynamic.<enumName>`.** Whenever the enum class is on the classpath — a static
> project, and equally a dynamic project *converted* from one — the generator writes the **real FQN**
> (`com.devsegment.erp.dto.enums.CountType`, `…dto.common.DocumentStatus`, `…BomType`), never `dynamic.*`.
> The synthetic `dynamic.<enumName>` `dataClass` is only for a
> pure-dynamic FREE/DB enum with no Java class (legacy path, `BaseFormControl.java`). Either way, keep the
> `enumValues`+`enumFieldNames` snapshot on the dropdown — that is what actually drives rendering —
> see [02-form-controls-reference.md](02-form-controls-reference.md) "Enum mode".

For enum columns to even appear in the dialog table, the field list is loaded through
`fieldClassesWithEnums()` = `ValueType.serializableTypes()` **+** `Enum.class`
(`GenerateFieldsFromCrudDialog.java`). Without `Enum.class`, enum fields silently drop out of the list.

#### Variant C — Autocomplete

Settings = `FormControlRimmAutoCompleteFieldSettings` (`FormFieldsGenerator.java`
`extends AutocompleteFilterControlSettings`, its own fields — `showChoicesOnClick`, `searchField`; inherits
`ruleIdentifier`/`key`/`displayName`/`showNav`). The generator sets:
- `ruleIdentifier` = the `RIMM_AC_*` rule created by `ensureRule` (below);
- `key` = `displayName` = `<displayField>` (AC stores what it shows — the invariant **key==display**);
- `searchField` = `<sourceSearchField>`, or `<displayField>` if not overridden;
- `showChoicesOnClick` = `true` (**hardcoded**, always).

Autocomplete is offered in the dialog's Control dropdown **only when the field's Java class == `String`**
(`compatibleControlsFor` removes AC otherwise, `GenerateFieldsFromCrudDialog.java`), so in practice a
generated AC binds to a String field. Full settings schema — [02-form-controls-reference.md](02-form-controls-reference.md).

**Generating one autocomplete field mutates the SOURCE dynamic CRUD.** Unlike the dropdown (which only writes a
rule), `AutoCompleteRimmRuleHelper.ensureRule` (`doGenerate`;
`AutoCompleteRimmRuleHelper.java`, engine) runs a **five-part pipeline** on the source CRUD,
with `Suffix = capitalize(searchField)`:

1. **SQL method** `acFindAllBy<Suffix>Like` on the CRUD (`addSqlLikeMethod`), a `LOWER … LIKE`
   query with `LIMIT 100` and the `defaultValue:''` empty-filter trick:
   `SELECT * FROM <table> WHERE LOWER(<col>) LIKE LOWER(CONCAT({name:'<searchField>',defaultValue:''}, '%')) LIMIT 100`
   (design SQL; persisted as named-param script). One String parameter `<searchField>`, `methodOrder=100`.
2. **Query** `crud_<alias>_acFindAllBy<Suffix>Like` backing that SQL (`createOrUpdateQuery`).
3. **Groovy method** `acFindBy<Suffix>Like` on the CRUD (`addGroovyLikeMethod`) — a thin pass-through
   `def filter = param ?: [:]; return service.crud.<alias>.acFindAllBy<Suffix>Like([<searchField>: (filter.<searchField> ?: '')]) ?: []`,
   `methodOrder=101`.
4. **Hidden method-rule** `crud_<alias>_acFindBy<Suffix>Like` (`saveGroovyMethodRule`, `hidden=true`)
   that backs the Groovy method.
5. **The RIMM rule** itself, named **`RIMM_AC_<crudAlias>_<searchField>`** (by `searchField`, NOT display),
   `EXECUTION_RULE` / `GroovyExecutionRule` / `ACTIVE` / `hidden=false`. Its body (`buildRuleScript`)
   calls the Groovy LIKE method + `toAutoCompleteOptions` (NOT `find()` / `toSelectOptions`):
   ```groovy
   def list = service.crud.<crudAlias>.acFindBy<Suffix>Like([<searchField>: attrs.get('filterBy')])
   return service.global.conversion.toAutoCompleteOptions(list, "<displayField>")
   ```
   (the dialog passes `localized=false`, so `toAutoCompleteOptions`, not `…Localized`).

`ensureRule` **fails on a pure-static CRUD** ("has no dynamic definition — cannot add methods") — a
generated-style autocomplete only works over a source CRUD that has a dynamic definition. For a **by-hand export**
you have two choices: (a) reproduce all five artifacts above (the two CRUD methods + Query + hidden method-rule
+ the `RIMM_AC_*` rule) so the LIKE filtering actually works; or (b) simply hand-author the AC control pointing
its `ruleIdentifier` at **any** rule that returns `toAutoCompleteOptions`-shaped data (the hand-authored
autocomplete shape — 4-key settings, `key != displayName` — is in
[02-form-controls-reference.md](02-form-controls-reference.md)).

#### Variant D — Full-width (`gen_full_<batch>_<i>`)

This is not a special case — it is **how any non-`WRAPPER_STYLE_PLUGINS` control renders**. File upload / List /
Comments / Gantt (and any future control outside the 5 wrapper-style plugins) are appended **directly** into
`form.parsis` as siblings of the row, without label, help and wrapper (`build` step-4,
`FormFieldsGenerator.java`). id = `gen_full_<batch>_<i>`.
`settings` = a base `FormControlSettings` (+ subclass-specific List/Gantt/FileUpload configuration the dialog does
not build; on override it is preserved from the preserved JSON — see controlled-keys below). They have no visual `*`/help-icon
by design (no inline label).

Subclass-setting defaults (from the settings classes, not from the generator; for reference):
- **FileUpload** `FormControlFileUploadFieldSettings`: `uploadPath="uploads/"`,
  `allowedFileTypes="pdf,doc,docx,xls,xlsx,jpg,jpeg,png,gif"`, `maxFileSize=10485760`, `allowMultiple=true`,
  `showProgress=true`. (**No** `maxFiles`/`multiple`/`showPreview`/`acceptedFileTypes` — these are fabricated from
  the concept docs.)
- **List** `ListFormControlSettings`, **Gantt** `GanttChartFormControlSettings` — configured by hand/through their
  own panels.

> `gen_full_*` nodes are rare — generated fields are wrapper-style unless you pick one of the four full-width
> controls — but the shape is the `build` step-4 code path, not a speculative reconstruction. A form whose
> generated controls are **all** full-width does not auto-enter override mode (detection keys on `gen_row_` only —
> see Override / regenerate).

## Override / regenerate (in-place regeneration)

The dialog automatically enters **override mode** when the form already has generated fields, detected by the
id prefix **`gen_row_`** only (`hasGeneratedRowsAlready` → `hasGeneratedDescendant`, recursive cycle-guarded scan,
`GenerateFieldsFromCrudDialog.java`, `GENERATED_ROW_PREFIX="gen_row_"`). **A form whose generated
controls are all full-width (`gen_full_*` — File-upload/List/Comments/Gantt only) does NOT auto-enter override**
(the checkbox stays unchecked); once override IS on, pruning still replaces both `gen_row_*` and `gen_full_*`.

Then `GeneratedFieldReader.read` **reverse-parses** the existing fields into table rows — **purely from
node data, never from the slot HTML markup**: control from the field-node's `pluginName`; label from `lbl_*.text`
(the LOCALIZED_STRING map, default-locale value + full map preserved); help from
`helpSettings.localizedMap.message` (`readHelpMessage`); order via `recoverSpecIndex`; layout columns/wrapper via
`readRowBatch`/`parseWrapperClass`; and **everything else (mandatory, default\*, prohibited, jsonNode\*, enum
picks, dropdown/AC key/display/search) from the field-node's `settings` JSON**. In particular **the
Required/mandatory flag is restored from `settings.alwaysMandatory`** (`rf.mandatory = bool(s, "alwaysMandatory")`,
`GeneratedFieldReader.java`) — **NOT** from the presence of the red `*` in the slot HTML; the `*` glyph is a
render-only artifact of `buildLabelledSlotHtml` and is never read back. Consequence for a by-hand MODIFY: to have
override-regenerate preserve a mandatory/default/prohibited, it must live in `settings` — decorating only the HTML
with a `*` is invisible to the reader.

On a repeat Generate the previous generated fields for the selected context+crud pair are **stripped out** and
replaced. Matching is per whole **`gen_row_*`/`gen_full_*` batch** by the **FIRST** field-settings `(contextIdentifier,
crudAlias)` found depth-first inside it (`pruneGeneratedForTarget` → `firstSettingsContextCrud`,
`GenerateFieldsFromCrudDialog.java`); a batch is kept-or-removed as a whole by its first field, and
**hand-authored (non-`gen_*`) controls are never pruned**. Prune runs only after specs validate non-empty
so an aborted generate never deletes anything.

**Override-merge does not overwrite the whole settings JSON — only the "controlled keys"**
(`mergeControlled`, `FormFieldsGenerator.java`; lists). All other keys of the preserved JSON
(`rowsInPage`, `searchEnabled`, `conditionalValidations`, `eventComponentMappings`, `localized`, `showNav`,
List columns, Gantt config, …) are **carried verbatim**. The controlled-keys that the generator overwrites:

- **COMMON** (`CONTROLLED_KEYS_COMMON`): `scope, contextIdentifier, crudAlias, fieldExpression,
  dataClass, name, filterKey, alwaysMandatory, jsonNodeExpression, jsonNodeValueType, enumName,
  defaultValueEnabled, defaultValueStatic, defaultValue, defaultValueLocalized, defaultValueRuleIdentifier,
  prohibitedPredicateIdentifier, alwaysProhibited`.
- **DROPDOWN** adds: `ruleIdentifier, key, displayName`.
- **AUTOCOMPLETE** adds: `ruleIdentifier, key, displayName, searchField, showChoicesOnClick`.

Note `mandatoryPredicateIdentifier` and `mandatoryValidationMessages` are **deliberately NOT controlled** — a
conditional / per-locale mandatory configured via the settings panel **survives a Generate override untouched**,
whereas the all-or-nothing `alwaysMandatory` is erased when the Required tick is off (the Generate dialog authors
only `alwaysMandatory`; see the Required column).

The key consequence: **a controlled-key absent from the fresh settings is REMOVED from the base** (`mergeControlled`
either `base.add(key,…)` when present or `base.remove(key)` when null/absent, `FormFieldsGenerator.java`).
Unticking Mandatory or clearing the JSON projection erases the previously stored value. Therefore, when assembling
by hand, write these keys only when they are enabled (see Gotcha 5). For a by-hand export you don't need to
reproduce override mode (you write the final JSON directly) — but the controlled-keys list shows which fields
**must** match the dialog's columns semantically.

**When the preserved JSON is reused as the merge base** (`reusePreserved`,
`GenerateFieldsFromCrudDialog.java`): only when `isOverrideExisting` **AND** the row was `restored`
**AND** `restoredSettingsJson` is non-blank **AND** `controlPluginName == restoredControlPluginName`. Only then is
`spec.preservedSettingsJson` non-null and `mergeControlled` overlays the controlled keys onto it; otherwise the
generator writes **fresh** settings from scratch (dropping any non-controlled advanced keys). Additionally: an
unchanged restored label reuses its full per-locale map verbatim (no re-translation) when `displayName ==
restoredDisplayLabel`; and for dropdown/AC an unchanged source `(crud+key+display[+search])` reuses the exact
existing rule identifier instead of re-deriving one.

**enum-mode gating — reader vs `doGenerate` asymmetry.** The reader computes
`rf.enumMode = DROPDOWN plugin && blank ruleIdentifier && non-blank enumName` (`GeneratedFieldReader.java`).
But `overlayRow` does **not** trust `rf.enumMode` — it re-gates enum-vs-source-CRUD on the schema condition
`row.isEnumField() && isDropdownControl(...)`, because a legacy/dynamic enum dropdown can have a blank
`enumName` (making `rf.enumMode` false) which would otherwise mis-route the restore into the source-CRUD branch and
silently drop the enum value/display picks. Practical rule for a hand-authored enum dropdown that round-trips
cleanly: set `enumName` **and** leave `ruleIdentifier` absent (an enum dropdown must have **no** `ruleIdentifier`,
else both runtime and reader take the rule branch).

### Modify an existing generated form (by hand — MODIFY-FILLED)

When a form's grid already exists in a filled `.mrjun`, do **surgical** deltas rather than regenerating (the full
MODIFY loop lives in [19-build-decision-procedure.md](19-build-decision-procedure.md); this is the entity-specific detail):

- **Add ONE field to an existing grid.** Pick a target column `gen_col<N>_<batch>` and append a new
  `gen_slot_<batch>_<col>_<i>` node as its child (`col` = N−1, 0-based; `i` = next free position in that column —
  respect the round-robin so `recoverSpecIndex` still restores order, Gotcha 4). The column is a
  `nct.parsis.plugin` with **no HTML of its own** — it renders all children automatically, so nothing else in the
  column changes; you do **not** touch the `gen_row` HTML. Inside the new slot's own `properties.html.stringValue`
  put the matching `<plugin id="lbl_<slot>" name="nct.label.plugin"></plugin>` +
  `<plugin id="fld_<slot>" name="<the field control pluginName, e.g. dynaform.form.text.field.plugin>"></plugin>`
  markers, and add those two child nodes (label + field) — the `id` **AND** `name` in the slot HTML must equal each
  child's `identifier` **AND** `pluginName` (Gotcha 1; a missing/wrong `name` clears the field's settings at render).
  Tooling: `node add` for the slot/label/field nodes; both id and name must match.
- **Change a control's source in place** (e.g. re-point a dropdown, swap an enum snapshot). Patch **only the
  controlled key(s)** on the existing `fld_*` node — `node patch-settings <id> --set ruleIdentifier=… ` /
  `--set enumValues=json:… --set dataClass=…` — leaving every non-controlled sibling key
  (`rowsInPage`, `searchEnabled`, `conditionalValidations`, `eventComponentMappings`, `localized`, `showNav`, List
  columns, Gantt config, `between*`) **untouched**. This mirrors what the dialog's `mergeControlled`
  (`FormFieldsGenerator.java`) does; the controlled-key lists are. Do not rewrite the whole
  `settings` blob — patching one key preserves the rest. **If you re-point the `fieldExpression`, re-snapshot the
  enum trio to match the new field** — the settings panel re-derives `enumValues`/`enumFieldNames`/`enumName` from
  the new field on every re-bind, snapshotting them when the field is an enum and nulling all three when it is not
  (`FormControlSettingsControlPanel.java`); a stale enum trio renders the wrong/empty options (see
  [02-form-controls-reference.md](02-form-controls-reference.md) "Enum mode"). **If you change a control's TYPE (its
  `pluginName`, e.g. Text field → Dropdown), you MUST update BOTH the `fld_*` node's `pluginName` AND the enclosing
  slot HTML's `<plugin id="fld_<slot>" name="…">` attribute to the new pluginName** — otherwise the render-time
  `name`≠`pluginName` mismatch clears the field's settings and re-types the now-empty node (top-of-doc ⛔; Gotcha 1).
- Whichever you do, run `mrjun.py validate` before re-import (id/parent integrity).

## Nested-mode (List-item sub-form)

The second dialog call — from a list-item sub-form (`ListItemFormPlugin`, "Auto add fields")
(`GenerateFieldsFromCrudDialog.java` — nested ctor, — `nestedBinding*`). Differences from form-mode:

- **No Context/CRUD pickers.** The source of the field list is the item's **fixed nested-alias** (e.g.
  `"ticket.spareParts"`), `Model.contextIdentifier` = null.
- **Controls bind to a temp location:** `settings.contextIdentifier = "__temp_list_item_context__"`,
  `settings.crudAlias = "__temp_item__"`, `settings.scope` = **the parent list's scope**
  (`nestedBindingScope`). This is exactly what a hand-assembled nested control does.
- **Per-row Choices-From-CRUD source can be ANY project CRUD** — the RIMM rule is created the same
  way, but `service.crud.<anyAlias>.find(...)`.
- **The enum snapshot is mandatory** here: a nested-collection-item enum is not indexed by the project-enum-registry, and without
  `settings.enumValues`/`enumFieldNames` the dropdown will be empty (see Gotcha 6).

The concept of nested forms and `context.currentData` — see [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md)
(older platform documentation on form fields is stale on other points but correct on the nested mechanics).

## JSON-projection (ObjectNode field → scalar)

When the field class is `ObjectNode`/`JsonNode` and the control is scalar-native (Text/Textarea/DatePicker/Dropdown/
Autocomplete), the dialog offers a **JSON projection**: `jsonNodeExpression` (path inside the node) +
`jsonNodeValueType` (scalar FQN). It is **not a separate table column** — the Path + Type inputs live **inside the
single "Choices source" cell** (col 11) as one of four mutually-exclusive sub-blocks (`projectionWrapper`, shown
when the field is JSON-shaped and the control is not JSON-native; see below). The generator writes both keys into
settings (`populateBaseSettings`); the runtime reads/writes the specific scalar inside the ObjectNode field.
For **JSON-native** controls (Comments/Gantt/FileUpload/List) there is no projection — they consume the whole
ObjectNode as-is. Both keys = null if no projection is set (and, being controlled-keys, they are erased on override
if cleared).

## Mapping of dialog columns → settings

The dialog table has exactly **11 `<th>` columns** in this order (`GenerateFieldsFromCrudDialog.html`);
**Layout is a header control above the table, not a per-row column**, and there is **no `localize` column** (label
localization is automatic). Column → widget → Row field → settings/node effect:

| # | UI header | widget (`wicket:id`) | `Row`/`Spec` field | effect in the generated content |
|---|---|---|---|---|
| 1 | *(drag-handle)* | `SortItemBehaviour`/`SortTarget`/`SortFeedback` | row order | spec order → round-robin across columns |
| 2 | *(select-all)* | CheckBox `selectAll` | `Row.selected` | unselected rows are not generated (`doGenerate`) |
| 3 | **Field** | Label `expression` (read-only) | `Row.expression` | `settings.fieldExpression` (+ `filterKey`, which mirrors it) — **not** `dataClass` (that is col 9) |
| 4 | **Label on form** | TextField `displayLabel` (default `prettifyLabel`) | `Row.displayLabel` → `Spec.fieldDisplayName` | `lbl_*.text` (auto-seeded into all locales), `settings.name` |
| 5 | **Required** | CheckBox `mandatory` | `Row.mandatory` → `Spec.mandatory` | `settings.alwaysMandatory = true` **+** a red `*` in the slot-HTML (`buildLabelledSlotHtml`, class `.red`). *(Header says "Required"; every code field is named `mandatory`/`alwaysMandatory` — there is no field called `required`.)* |
| 6 | **Prohibited** | CheckBox `prohibited` → `prohibitAlways` (default ON) + `RuleIdentifierSelectorField`(PREDICATE) | `Row.prohibited`/`prohibitAlways`/`prohibitedPredicateIdentifier` | Always → `settings.alwaysProhibited = true` (rule-free); Custom → `settings.prohibitedPredicateIdentifier = <UUID>` (`doGenerate`; create-name `"<Crud> <Field> Prohibited Predicate"`) |
| 7 | **Info / help** | CheckBox `showInfo` → `LocalizedTextFieldsPanel infoPanel` | `Row.showInfo` + `infoText` (map locale→text) | a `help_*` node (`nct.help.plugin`) to the right of the label (flex-header slot); otherwise a "flat" slot |
| 8 | **Default** | CheckBox `hasDefault` → `defaultStatic` (default ON) + per-type static editor OR `RuleIdentifierSelectorField`(EXECUTION_RULE) | `Row.hasDefault`/`defaultStatic`/`defaultValue`/`defaultRuleIdentifier` → `DefaultSpec` | `settings.defaultValue*` (see below) |
| 9 | **Type** | Label `fieldClassName` (read-only badge) | `Row.fieldClassName` | restricts the Control choice; written into `settings.dataClass` |
| 10 | **Control** | DropDownChoice `controlPluginName` (default `compatible.get(0)`) | `Row.controlPluginName` | field-node's `pluginName` + choice of settings class |
| 11 | **Choices source** | one of four sub-blocks (see below) | `sourceCrudAlias`/`sourceKeyField`/`sourceDisplayField`/`sourceSearchField` **or** `enumValueField`/`enumDisplayField` **or** `jsonNodeExpression`/`jsonNodeValueType` | dropdown/AC → RIMM rule + `key`/`displayName`/`searchField`; enum → `key`/`displayName`; JSON → `jsonNodeExpression`/`jsonNodeValueType` |
| *(header)* | **Layout** | DropDownChoice `layoutColumns` (List.of(1,2,3,4,6); **default/typical 4**) + TextField `layoutContainerClass` (**typically `container`**) | `Model.layoutColumns`/`layoutContainerClass` | the row's column count (`col-md-(12/N)`, 4→`col-md-3`) + the outer wrapper `<div class="container">` around the `.row` |
| *(none)* | *(label localize)* | — automatic, not a column | — | `lbl_*.text` seeded into all tenant locales via `seedLocalizedLabel` → `LocalizeService.seedLocalizedNames` |

**Column 11 "Choices source" hosts four mutually-exclusive sub-blocks in one cell** (`html`), gated by
control + field type:
- `notApplicable` — a `—` placeholder, when none of the below apply;
- `enumWrapper` — Value (`enumValueField`) + Display (`enumDisplayField`) selects, shown iff `Row.enumField &&
  isDropdownControl(control)`;
- `sourceWrapper` — From (`sourceCrudAlias`) / Show (`sourceDisplayField`) / **Save** (`sourceKeyField`,
  **Dropdown only**) / **Search** (`sourceSearchField`, **Autocomplete only**), shown iff
  `isSourceCrudControl(control) && !isEnumDropdownRow` (saveRow, searchRow);
- `projectionWrapper` — Path (`jsonNodeExpression`) + Type (`jsonNodeValueType`), shown iff the field class is
  `ObjectNode`/`JsonNode` and the control is not JSON-native.

**Default column → `defaultValue*`** (`applyDefaultSpec`, `FormFieldsGenerator.java`
`FormControlSettings` fields: `defaultValueEnabled`/`defaultValueStatic`/`defaultValue`/`defaultValueLocalized`/
`defaultValueRuleIdentifier`). `applyDefaultSpec` clears **all five** to null when off:
- off → all five fields = null;
- static → `defaultValueEnabled=true`, `defaultValueStatic=true`, `defaultValue=<string>` **or**
  `defaultValueLocalized=<map>` (whichever is non-blank), `defaultValueRuleIdentifier=null`;
- rule → `defaultValueEnabled=true`, `defaultValueStatic=false`, `defaultValueRuleIdentifier=<UUID>`, the rest null.

The **static editor is picked by type** (`GenerateFieldsFromCrudDialog.java`), but every editor writes the
single String key `defaultValue`:
- **Boolean field** → a checkbox → `defaultValue = "true"` / `"false"`;
- **Text-area control** (`dynaform.form.textarea.field.plugin`) → a textarea;
- **enum field** (`enumValues` non-empty) → a dropdown of the enum **constant NAMES**
  (`enumValues.keySet()`) → `defaultValue` = the chosen constant name (e.g. `"STOCK"`);
- otherwise → a plain text input.

Note the dialog's own editor **never writes `defaultValueLocalized`** — that key only round-trips through
override-restore of a field previously configured localized via the control settings panel (`doGenerate`
passes `r.getDefaultValueLocalized()` only in static mode). For a fresh by-hand static default use `defaultValue`
(a String); for a localized field use `defaultValueLocalized` (`locale.toString()` → text) — the two are mutually
exclusive in practice. More on the default-value runtime in
[02-form-controls-reference.md](02-form-controls-reference.md).

## Validation templates and Between-mode (not Generate columns, but they live in the same settings)

These mechanics surface in the **control's settings panel**, NOT as Generate-dialog columns — but they are written into the
same `FormControlSettings` JSON, so when assembling by hand you need to know about them. Full description —
[02-form-controls-reference.md](02-form-controls-reference.md). Briefly:

- **`conditionalValidations`** (List<ConditionalValidation>) — validations by predicates. There is a built-in
  library of templates (`validationtemplates/BuiltinTemplates.java`) in which "predicate-true = INVALID".
  The full list of IDs/names (cross-type `required`/`equalsConst`/`notEqualsConst`/`inList`/`notInList`; String
  `strLen*`/`strRegex`/`strStartsWith`/…; Numeric `numBetween`/`numLt`/`numMultipleOf`/`numDecimalPlaces`/…;
  Boolean `boolMustBeTrue`/`boolMustBeFalse`; Date `dateBefore`/`dateAfter`/`dateBetween`/`dateWithinDays`/…;
  JSON `jsonHasKey`/`jsonMissingKey`; List `listNotEmpty`/`listSizeMin`/…) + regex presets (Email/URL/UUID/
  IPv4/Slug/Phone…) — see [02-form-controls-reference.md](02-form-controls-reference.md). `TemplateParam.ParamType ∈ {TEXT, NUMBER, BOOLEAN, DATE,
  DATETIME, SELECT, MULTI_VALUES, REGEX_PRESET}`.
- **`mandatoryValidationMessages`** (Map<locale,String>, key = the **full locale** `"en_US"/"ru_RU"/"hy_AM"` — same
  convention as `defaultValueLocalized` and `conditionalValidations[].validationMessages`; at render the runtime reads
  `currentLocale.toString()` first and only falls back to a bare language code `"en"` if that key is absent,
  `FormPlugin.java`), `mandatoryPredicateIdentifier` — mandatoriness by predicate (unlike the rule-free `alwaysMandatory`).
  **The Generate dialog writes NEITHER.** It authors only `alwaysMandatory` (from the Required tick);
  `mandatoryValidationMessages` stays `{}` purely because `FormControlSettings` initializes the field to an empty
  map (`new FormControlSettings()`, generator never calls `setMandatoryValidationMessages`/
  `setMandatoryPredicateIdentifier`). Both are **non-controlled keys**, so a conditional / per-locale mandatory set
  via the settings panel survives a Generate override untouched. For a by-hand required field write only
  `alwaysMandatory:true`.
- **Between (range) mode**: `between` (Boolean) + `betweenMapping` (BetweenFieldMapping) — available for
  DatePicker (always) and a numeric Text field; submits TWO values (from/to), type/pattern are taken from the primary
  control. This is a **panel setting, not a Generate column** — the generator does not
  set it, but override-merge does NOT touch it (it is not in the controlled-keys), so on regeneration it survives.

## How to construct from scratch (recipe for a by-hand export)

Task: add to a form (whose `form.parsis` already exists in the tree) a row of **two** fields — a Text field
`name` (String, required) and a Dropdown `categoryId` (Integer, choices from CRUD `categories` by `id`/`label`) —
in **2 columns**.

**Step 0 — pick a `batchId`.** Any 8-hex, for example `a1b2c3d4`. All ids below use it.

**Step 1 — RIMM rule for the dropdown.** Add to `rep-objects.json.rules[]` an object (see
[08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)):
```json
{
  "identifier": "<new-uuid-rule>",
  "name": "RIMM_categories_id_label",
  "ruleType": "EXECUTION_RULE",
  "executor": "GroovyExecutionRule",
  "status": "ACTIVE",
  "contextIdentifiers": [],
  "rule": { "ruleScriptStr": "def list = service.crud.categories.find([\n  rowsInPage: 1000,\n  pageNumber: 0\n])\nreturn service.global.conversion.toSelectOptions(list, \"id\", \"label\")\n" },
  "realmName": "<realm>", "clientName": "<client>", "hidden": false
}
```

> **⚠️** Keep the `toSelectOptions` tail (a raw `findAll` entity list renders blank + hides Show Nav — `validate`
> ERRORs on it), and do **not** add filter keys to this `find()` to narrow the options — a partial filter map hits the
> untyped-`$1` Postgres error; use `findAll([:])` or the searchable `acFindAllBy<X>Like` pipeline. For a localized
> display column post-edit to `toSelectOptionsLocalized`. See Variant B above and
> [02-form-controls-reference.md §4a](02-form-controls-reference.md).

**Step 2 — root row** `gen_row_a1b2c3d4` (`nct.html.plugin`), child of `form.parsis`. 2 columns →
`col-md-6`. `properties.html.stringValue`:
```html
<div class="row">
  <div class="col-md-6">
    <plugin id="gen_col1_a1b2c3d4" name="nct.parsis.plugin"></plugin>
  </div>
  <div class="col-md-6">
    <plugin id="gen_col2_a1b2c3d4" name="nct.parsis.plugin"></plugin>
  </div>
</div>
```

**Step 3 — columns.** Two `nct.parsis.plugin`: `gen_col1_a1b2c3d4`, `gen_col2_a1b2c3d4` (children of `gen_row_*`).
Round-robin for 2 fields in 2 columns: spec 0 (`name`) → col0, spec 1 (`categoryId`) → col1.

**Step 4 — slot col0** `gen_slot_a1b2c3d4_0_0` (`nct.html.plugin`, child of `gen_col1_a1b2c3d4`), required →
flex-header with `*`. `html`:
```html
<div class="mb-3">
  <div class="d-flex align-items-center justify-content-between">
    <span class="d-inline-flex align-items-center">
      <plugin id="lbl_gen_slot_a1b2c3d4_0_0" name="nct.label.plugin"></plugin>
      <span class="red ms-1">*</span>
    </span>
  </div>
  <plugin id="fld_gen_slot_a1b2c3d4_0_0" name="dynaform.form.text.field.plugin"></plugin>
</div>
```
Slot children: label `lbl_gen_slot_a1b2c3d4_0_0` (`text`={`en_US`:`Name`}, `tagName`=`label`,
`className`=`form-label`) and field `fld_gen_slot_a1b2c3d4_0_0` with `settings`:
```json
{ "scope":"CRUD","contextIdentifier":"<ctx-uuid>","crudAlias":"<thisCrud>",
  "fieldExpression":"name","name":"Name","filterKey":"name","dataClass":"java.lang.String",
  "alwaysMandatory":true,"mandatoryValidationMessages":{},"eventComponentMappings":[],"conditionalValidations":[] }
```

**Step 5 — slot col1** `gen_slot_a1b2c3d4_1_0` (`nct.html.plugin`, child of `gen_col2_a1b2c3d4`), not required →
flat. `html`:
```html
<div class="mb-3">
  <plugin id="lbl_gen_slot_a1b2c3d4_1_0" name="nct.label.plugin"></plugin>
  <plugin id="fld_gen_slot_a1b2c3d4_1_0" name="dynaform.form.rimm.drop.down.field.plugin"></plugin>
</div>
```
Label `lbl_gen_slot_a1b2c3d4_1_0` (`text`={`en_US`:`Category`}). Field `fld_gen_slot_a1b2c3d4_1_0`
(`dynaform.form.rimm.drop.down.field.plugin`) with `settings`:
```json
{ "searchEnabled":false,"ruleIdentifier":"<new-uuid-rule>","key":"id","displayName":"label","showNav":false,
  "scope":"CRUD","contextIdentifier":"<ctx-uuid>","crudAlias":"<thisCrud>","fieldExpression":"categoryId",
  "name":"Category","filterKey":"categoryId","dataClass":"java.lang.Integer",
  "mandatoryValidationMessages":{},"eventComponentMappings":[],"conditionalValidations":[] }
```

> **Show Nav.** The line above mirrors the generator default `"showNav":false`; for a CRUD/enum-backed dropdown
> **set `"showNav":true`** to expose the "open source" affordance — it renders only once the rule is canonical
> `toSelectOptions*`-shaped (Step 1 above is). See [02-form-controls-reference.md §4a](02-form-controls-reference.md)
> "Show Nav — turn it ON".

**Step 6 — `settings` is written as a STRING property.** Each `settings`/`html`/`helpSettings`/`text` lives in a
typed property slot (see [01-content-model-and-pages.md](01-content-model-and-pages.md)) — with fields
`key`, `propertyType`, `fieldPanelClass`, `arguments`, `required`, `hidden` and a typed `*Value`. For example:
```json
"settings": { "key":"settings","propertyType":"STRING","required":false,"hidden":false,
              "fieldPanelClass":"com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel",
              "arguments":{},
              "stringValue":"<escaped JSON string of the settings object>","localizedStringValue":{} }
```
and the label's `text` — `"propertyType":"LOCALIZED_STRING"` with `"localizedStringValue":{"en_US":"Name"}` and
`fieldPanelClass` = `PropertyBaseLocalizedTextFieldPanel`.

The result is identical to what the dialog would have produced: on render the form will find the `<plugin>` markers by id,
reuse the created nodes, and draw a row of two fields.

## Gotchas

1. **The id AND the name in the HTML must match the child node's `identifier` AND `pluginName`.** The html plugin's
   Jsoup pass matches `<plugin id="X" name="P">` to a child by `identifier == X`; a mismatch → a duplicate or an
   empty spot (`FormFieldsGenerator.java`). This applies to **all** levels: `gen_col*`, `gen_slot`, `lbl_`
   `help_`, `fld_`. ⛔ **The `name` is equally load-bearing:** on an `id` hit whose stored `pluginName` ≠ the marker's
   `name`, `PluginUtils.getOrCreateChildContent` does `child.getProperties().clear();
   child.setPluginName(name)` — **wiping the field's `settings`** and re-typing the node from the marker `name`
   (render path reads `name = plugin.attr("name")`, `AbstractHtmlPlugin.constructListModel`). A nameless or
   stale-name marker therefore renders a **blank, unbound control** (or `Not valid plugin ` when the name is
   blank/unknown). `validate` ERRORs on a **stale** name (it compares the marker's `name` with the child's stored
   `pluginName`); a marker with **no `name` at all** has nothing to compare against and passes
   validate/coverage/crud-verify, breaking only at render (see the top-of-doc ⛔). Every marker must spell out
   `name="<child pluginName>"` verbatim.

2. **The content must lie INSIDE `form.parsis`, not as a sibling.** The form renders exactly its own canonical
   parsis (`identifier="form.parsis"`, `pluginName="nct.parsis.plugin"`; `ensureFormParsis`,
   `FormFieldsGenerator.java`). Rows/full-width nodes as siblings of the parsis are ignored. If there is no parsis yet —
   create it first.

3. **The property key is the lowercase `html`, not `HTML`.** In the export it is `properties.html.stringValue`
   (`HtmlPlugin.HTML == "html"`, confirmed from the source
   `mrjun .../HtmlPlugin.java`) — this is the **property key** inside `properties`, not a separate
   node field (the node has no top-level `HTML` field; verified with `jq keys`).

4. **Round-robin, not row-by-row.** The order of fields in the columns is `spec j → column j % cols, position
   j / cols` (`FormFieldsGenerator.java`). When assembling by hand, lay out the specs the same way, otherwise the
   override reader (`recoverSpecIndex`, `GeneratedFieldReader.java`) will restore the order incorrectly.
   The `col` in the id `gen_slot_<batch>_<col>_<i>` is **0-based**, whereas the column name `gen_col<N>` is **1-based**
   (`gen_col1` holds slots `…_0_*`).

5. **`alwaysMandatory` / `alwaysProhibited` / `defaultValue*` / `jsonNode*` are written only when enabled;
   otherwise they are absent.** The generator sets `null`, and `Gson` omits them. Do not add these keys "just in case" —
   they are part of `CONTROLLED_KEYS_COMMON` (`FormFieldsGenerator.java`), and override-merge
   (`mergeControlled`) treats a missing key as "off" and erases the preserved value.

6. **Enum-dropdown: for nested/dynamic the `enumValues`+`enumFieldNames` snapshot is mandatory.** A top-level static
   enum is rendered from the project-enum-registry even without a snapshot, but **a nested-collection-item enum and a dynamic
   FREE/DB enum — no**: without `settings.enumValues` (map `constant → {property → value}`) and `enumFieldNames`
   the runtime fails on `Class.forName(dataClass)` (the enum lives only in the integration service) → an empty dropdown
 (`populateBaseSettings`). An enum-dropdown has
   **no** `ruleIdentifier` (otherwise the runtime goes down the rule branch, not the enum branch).

7. **"Always prohibited" is a rule-free flag, NOT a "True" predicate.** Previously Always set a predicate
   returning `true`, and the runtime invoked the executor on every render of every prohibited field (17 fields = 17
   network calls for a constant). Now Always = `settings.alwaysProhibited=true` without a rule
 (`doGenerate`). Write the flag, not the UUID of a "True" rule.
   On **override-restore**, a legacy field still carrying the old "True"-predicate UUID in
   `prohibitedPredicateIdentifier` is detected (`resolveTruePredicateId(false)`, `GenerateFieldsFromCrudDialog.java`),
   shown as "Always", and rewritten to `alwaysProhibited=true` on the next generate. `resolveTruePredicateId(true)`
   *can* create a "True" `GroovyPredicate` but **no fresh-generate path calls it** — never write a "True"-predicate
   UUID for a by-hand Always; write `alwaysProhibited:true`. Three by-hand states: not prohibited → **neither** key;
   Always → `alwaysProhibited:true` (no predicate); Custom → `prohibitedPredicateIdentifier:<PREDICATE-uuid>` (no flag).

8. **A wrapper CSS class is a SEPARATE outer `<div>`, not a class on the `row` itself.** A non-empty Layout wrapper
   wraps `<div class="row">` in `<div class="<wrapperClass>">…</div>` (`buildRootRowHtml`,
   `FormFieldsGenerator.java`). The reader distinguishes a wrapper from an unwrapped row by the class of the FIRST `<div>`: `"row"`
   = no wrapper, otherwise = wrapper (`parseWrapperClass`, `GeneratedFieldReader.java`). Do not write
   `<div class="row container">` — write the nesting. The class is sanitized (`sanitizeCssClass`).
   NB: the `Model.layoutContainerClass` field comment (`GenerateFieldsFromCrudDialog.java`) is **stale** —
   it says the class is appended onto the row, but `buildRootRowHtml` wraps the row in a separate `<div>`; trust the
   code, not the comment.

9. **The column count must divide 12 evenly** (1/2/3/4/6/12), otherwise `normalizeColumns` falls back to 4
   (`FormFieldsGenerator.java`). `col-md-*` = `col-md-(12/N)`. The dialog dropdown offers {1,2,3,4,6};
   12 is only reachable programmatically/through the override reader.

10. **`filterKey` always mirrors `fieldExpression`** (`populateBaseSettings`) — do not leave it empty,
    otherwise the control's page-parameter prefill will stop working on reuse.

11. **The node's `name` = its `identifier`** (`createPluginContent`) — not critical for rendering, but that's what the
    generator does; keep them equal for authoring-UI determinism. Every generated node (row / col / slot / label /
    help / field) also carries node-level **`active: true`** and the batch's **`branchId`**
    (`createPluginContent`) — **a by-hand node must set `active:true` or it will not render.**

12. **`contextIdentifier` in settings is a UUID, not a name.** Take the `identifier` of an existing context from
    `rep-objects.contexts[]`. Nested-mode writes `"__temp_list_item_context__"` instead of a UUID +
    `crudAlias="__temp_item__"`.

13. **One Generate call = one `contentService.save`.** The generator assembles the whole subtree in memory (`attach`,
    `FormFieldsGenerator.java`) and saves it all at once (otherwise O(saves × branch size)).
    For a by-hand export this is irrelevant (you write the JSON directly), but it explains why all nodes of one
 batch share a common `branchId` and consistent `parentId`.

14. **`fieldType` does not exist.** The field type = `pluginName`. Do not carry fabricated settings from the
    concept docs (`maxLength`/`min`/`step`/`prefix`/`minDate`/`maxFiles`/`checkedValue`/`dependsOnField`/…) into the export — not
    one of them exists in the settings classes (see the top ⚠️ block and
    [02-form-controls-reference.md](02-form-controls-reference.md)).
