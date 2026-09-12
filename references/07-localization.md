# 07 — Localization and authored content

> **Corrects and extends** [[20-localization.md](../20-localization.md)](../20-localization.md). Doc 20 tells you which export
> keys *have* a per-locale slot. This tells you which of those slots real builders fill, which they leave to
> rot, what they invent where the platform gives them no slot at all, and what a genuinely trilingual screen
> costs. Every number is a count over four delivered exports and their database dumps.

| | locales | default | pages | CRUDs | `nct.html.plugin` | charts |
|---|---|---|---|---|---|---|
| **A** | 2 | the Latin one | 433 | 163 | 1 304 | 55 |
| **B** | 3 | the non-Latin one | 129 | 38 | 962 | 31 |
| **C** | 3 | the non-Latin one | 128 | 31 | 574 | 87 |
| **D** | 3 | the Latin one | 67 | 12 | 207 | 12 |

**C is the model.** It is the only delivery where every layer agrees with every other: the CRUDs carrying a
localization column are exactly the CRUDs whose forms are `multiLanguage:true` are exactly the CRUDs with
`localized:true` controls (8 = 8 = 8); every chart is wordless with a localized heading beside it; every
CHECK vocabulary has a multilingual choices rule; every outward document exists once per language. It is also
the largest authoring effort of the four — 12 500+ locale maps for 128 pages. **D is what "we'll localize
later" looks like**: three locales declared, one delivered.

---

## 1. L0 — the locale set is one decision, made once

```json
{"locales": ["<default>", "<second>", "<third>"], "defaultLocale": "<default>", …}
```

**4/4 set `defaultLocale`, and 4/4 set it equal to `locales[0]`.** Doc 20's belt-and-braces advice is
universal practice; treat the two fields as one decision taken in Phase 0.

The choice has visible downstream consequences: a non-Latin-default delivery authors every user-visible
string in that language first — base columns, printed documents and Groovy fallbacks (`?: '<default>'`) all
follow — while a Latin-default delivery authors in the Latin language and treats the rest as a translation
pass, **a pass one of the two never made**.

⚠️ One piece of debris to recognise: a delivery with two locales carries 8 maps containing a **third** locale
key it does not offer. Extra keys import silently and render nowhere; they are platform seed residue, not
evidence the project once offered that language.

---

## 2. The five dead zones, ranked by how often they bite

Doc 20 names one (chart text). There are five, and the chart is not the worst.

### 2.1 ⛔ Page title and description — the slot nobody fills and nothing checks

`properties.pageTitle` / `pageDescription` are proper `LOCALIZED_STRING` properties:

```json
"pageTitle": { "key": "pageTitle", "propertyType": "LOCALIZED_STRING",
  "fieldPanelClass": "…PropertyBaseLocalizedTextFieldPanel",
  "localizedStringValue": {"<l1>": "…", "<l2>": "…", "<l3>": "…"} }
```

`locale fill` does not touch them and `validate` does not warn on them — and the evidence is exactly that
shape: **the only under-covered maps in two of the four deliveries are page titles and descriptions.**
Everything the toolkit checks is green everywhere; the unchecked slot is where every gap lives.

- One delivery: **0 of 67 pages** have a title in more than one language.
- Another: 48 of 433 incomplete, of which 26 are still the platform seed — the title was never edited at all.
- The two built page-by-page in the live UI have **zero** gaps, because the editor's localized-text panel
  auto-fills the other locales when the default-locale row loses focus.

✅ **Audit page meta first, not last:**

```bash
jq '[.. | objects | select(.key=="pageTitle") | .localizedStringValue | keys]
    | group_by(.) | map({keys:.[0], pages:length})' branches.json
```

Anything that is not the full locale set is a page that renders no title in that language.

### 2.2 ⛔ Groovy-returned text — no slot exists anywhere

A rule that returns `[ok:false, message:'…']`, calls `validation.addError('…')` or throws with a message has
**no per-locale slot in the export**. Doc 20 does not list this, and after labels it is the largest body of
user-visible text in a project. Two deliveries solved it, two did not (§6).

### 2.3 ⛔ `nct.html.plugin` markup — the same hole as the chart, 15× bigger

The node's `html` property is `propertyType: "STRING"`; its `localizedStringValue` is present and permanently
`{}`. Every word between the tags renders identically under every locale — and there are **1 304 / 962 / 574 /
207** such nodes against **55 / 31 / 87 / 12** charts. The escape hatch is real and one delivery uses it 208
times (§5.1).

### 2.4 ⛔ Chart text — confirmed, and one workaround was never built

`js`, `html` and `css` inside `properties.Javascript` are plain strings. One delivery eliminates the problem
entirely by putting all wording outside the chart (§5.2). **Nobody built the locale-parameterised replacement
query** (§5.3) — so translated *category axes* remain unsolved in all four.

### 2.5 ⛔ Printed and mailed body text — no per-locale field, only per-locale template

Mail and PDF templates carry no locale map. The only mechanism is a separate template with its own alias. Two
deliveries built the convention; two did not (§7).

---

## 3. L2 — the maps that always work, and the three ways they still fail

Across all four, `localizedNames`, `localizedButtonNames`, label `properties.text`, nav
`linkModel.localizedMap.name`, tab items and `mandatoryValidationMessages` total **~22 700 maps at ≥ 99.8 %
coverage**. `validate` covers these and it evidently works. Shapes worth copying:

```jsonc
// crud.table.plugin → properties.model.stringValue → columnSettings[]
{"id":"11b2c84a-…","localizedNames":{"<l1>":"…","<l2>":"…","<l3>":"…"},
 "fieldExpression":"occurredAt","dataClass":"java.time.LocalDateTime"}
```
1 408 of 1 408 columns carry `localizedNames` and no legacy `name`; only 2 fall back.

```jsonc
// nct.tab.plugin → items[] — THREE redundant name carriers, all three authored and consistent
{"id":"758068c4-…","name":"Open items","order":0,
 "localizedMap":{"name":{"<l1>":"…","<l2>":"…","<l3>":"…"}},
 "localizedNames":{"<l1>":"…","<l2>":"…","<l3>":"…"}}
```
Write all three; the deprecated scalar is the fallback and costs nothing.

### 3.1 ⚠️ The table model exists TWICE — mirror it or lose the translation

Every CRUD table's model is stored in `branches.json` (`properties.model.stringValue`) **and** in
`rep-objects.json` (`settings[]` where `type: "CrudTable"`). **Drift between the copies: 0 across all four.**
Hand-edit one only and the page and the settings dialog disagree — use the toolkit, which re-syncs.

The mirror also carries `orInitLocalizedNames` / `orInitLocalizedButtonNames`, exact shadow copies present in
two deliveries and absent in the two most correct ones. **Do not author them by hand and do not treat their
absence as a defect**; if they are present, keep them in sync.

### 3.2 ⛔ The blank-button bug is real and common

A CRUD `ActionDto` has no `name` field, so an action carrying only `name` renders an unlabelled button. One
delivery ships **72 of them** on real reference pages; 71 also lack `localizedButtonNames`, so the in-form
submit button is blank too. The other three: **0**.

```bash
jq '[.. | objects | select(has("direct") and has("icon")) | select(has("localizedNames")|not)] | length'
# must be 0 over BOTH branches.json and rep-objects.json
```

### 3.3 ⚠️ "Identical in every locale" has exactly two legitimate exceptions

Doc 20 warns that one value repeated across locales is not localization. True — but two sub-keys are
*supposed* to be identical, and a checker that flags them trains authors to ignore it:

- **`linkModel.localizedMap.icon`** — a CSS class name. Identical in ~1 090/1 096, 403/409, 275/280, 186/192.
- **Deliberate blank spacers** — 41 label properties authored as a single space in every locale.

### 3.4 ⛔ …and the counter-example: auto-translate rewrote the icon class names

Present identically in **all four**, on platform-seeded admin nav links:

```json
"icon": {"en_US": "pe-7s-users",  "<non-latin>": "pe-7s-<translated word>", "<other>": "pe-7s-<translated>"}
"icon": {"en_US": "pe-7s-tools",  "<non-latin>": "pe-7s <translated word>", "<other>": "pe-7s-tools"}
```

Auto-translate walked `localizedMap.icon` and machine-translated the **CSS class**. Under those locales the
items render **no icon**. Five links, four deliveries, shipped.

> **The rule this proves: auto-translate is field-blind.** Never put a non-prose value — a class name, a code,
> an id, a number, a colour — anywhere the translator walks. Where the bean forces you to, copy it verbatim
> into every locale and re-check after any live editing session.

---

## 4. Enum labels — the decision that separates a trilingual project from a bilingual one

### 4.1 ⛔ The `enumValues` snapshot is a one-language artefact

```jsonc
// dynaform.form.rimm.drop.down.field.plugin → settings.enumValues
{"CREATED":{"name":"CREATED","displayName":"Created"},
 "SENT":   {"name":"SENT",   "displayName":"Sent"}}
```

One `displayName` per value, no map, no slot. One delivery ships 60 of these on a bilingual project and
another 17 on a trilingual one — those dropdowns show one language to every viewer. The two best deliveries
carry **zero `enumValues` anywhere**.

⚠️ The same applies to **table columns**: enum projection takes priority over value localization, so a column
carrying an `enumValues` snapshot shows the snapshot's single `displayName` even when the row has a perfectly
good localization map. **A localized project carries `enumValues` on neither the control nor the column.**

### 4.2 ✅ The cheap answer doc 20 does not mention: an inline literal choices rule

Doc 20 says a multilingual CHECK vocabulary must be promoted to a lookup table plus a choices rule. **You do
not need the table.** 32 of one delivery's 44 localized choices rules are pure literals — no round-trip, no
migration, no seed data:

```groovy
// rule: ENUM_<snake_case_vocabulary>   ·   description: "Choices for the <vocabulary> CHECK vocabulary"
def rows = [
  [ id: 'DRAFT',    label: 'Draft',
    localize: [ label: [ <l1>: '…', <l2>: '…', en_US: 'Draft' ] ] ],
  [ id: 'ACCEPTED', label: 'Accepted',
    localize: [ label: [ <l1>: '…', <l2>: '…', en_US: 'Accepted' ] ] ],
  [ id: 'CLOSED',   label: 'Closed',
    localize: [ label: [ <l1>: '…', <l2>: '…', en_US: 'Closed' ] ] ] ]
return service.global.conversion.toSelectOptionsLocalized(rows, "id", "label")
```

Three load-bearing details:

- ⛔ **The synthetic key is `localize`, not `localized`** — even when the database column is `localized`.
  `toSelectOptionsLocalized(list, key, display[, localeKey, localizationFieldName='localize'])` defaults to
  the canonical wire key, and the CRUD executor aliases the column to `localize` on read. **Groovy always
  sees `localize`; SQL always sees the project's column spelling.** Invert it and the dropdown silently shows
  the base label in every language.
- `label` stays as a plain key — it is the fallback when the viewer's locale is missing from the map.
- One rule per vocabulary, named `ENUM_<vocabulary>`.

### 4.3 The table-driven variant, for vocabularies that are already rows

```groovy
def list = service.crud.<alias>.find([ rowsInPage: 1000, pageNumber: 0 ])
return service.global.conversion.toSelectOptionsLocalized(list, "id", "<displayField>")
```

Naming convention shared by two deliveries: `RIMM_<crudAlias>_<valueField>_<displayField>`, one per FK
dropdown, machine-generatable.

> **Decide once per project.** A CHECK vocabulary → the inline `ENUM_*` literal rule. A table → the `RIMM_*`
> rule over `find()`. **Never an `enumValues` snapshot on a 2+-locale project.**

---

## 5. The two real dead zones and the technique that closes both

### 5.1 ✅ Inline `<plugin>` + `<prop type="LOCALIZED_STRING">` — the highest-value pattern in this study

An `nct.html.plugin`'s markup can host a real content plugin with a real localized property. One delivery
does this **208 times**, all locales, 100 % coverage:

```html
<div class="mb-3">
  <plugin id="form-label" name="nct.label.plugin">
    <prop name="text" type="LOCALIZED_STRING"
          value='{"<l1>": "…", "<l2>": "…", "en_US": "State"}'></prop>
    <prop name="tagName"   value="label"></prop>
    <prop name="className" value="form-label"></prop>
  </plugin>
  <plugin id="field" name="dynaform.form.text.field.plugin"></plugin>
</div>
```

Mechanics that matter (doc 24b owns the tag grammar):

- `type` must be the **exact** enum name `LOCALIZED_STRING`. Anything else, or absent, means `STRING` — and
  the map becomes a literal string on screen.
- `value` is a **single-quoted** attribute holding a `{locale → text}` object: single quotes outside, double
  inside, no escaping.
- Every key of `locales`, every time. Nothing fills these and nothing checks them.

The alternative — an empty slot plus a real sibling node carrying `properties.text.localizedStringValue` — is
equally correct and is what the other deliveries use (851 / 179 occurrences). The inline form keeps the
caption next to the markup that positions it, which is why hand-built filter bars use it.

⚠️ If you see 50 identical inline props reading `{"en_US":"Label"}`, that is unedited studio boilerplate — a
caption nobody wrote.

### 5.2 ✅ A wordless chart plus a localized heading sibling — 87/87 in the best delivery

```
Dashboard grid
├── chart.js.plugin   "<what it answers>"   ← no title.text; the HTML tab is structure only
├── nct.label.plugin  hdr_<uuid>            ← properties.text LOCALIZED_STRING, every locale
├── chart.js.plugin   …
└── nct.label.plugin  hdr_<uuid>
```

The chart's HTML tab contains zero words:

```html
<div class="ck-plot" style="position:relative;height:340px;padding-top:20px;"><canvas></canvas></div>
```

✅ **Name chart headings `hdr_<the chart's own identifier>`** so "which label belongs to which chart" survives
a layout edit.

The two remaining hard-coded strings in a chart config are the dataset `label` and the axis titles. The best
delivery neutralises the first by **turning the legend off** in 27 charts and simply never writes axis titles
— a `label` that never renders is not a localization defect. Compare the delivery with 12 charts carrying
`title.text` in the JS and 17 with visible words in the HTML: those titles are one language under every
locale, and no gate will ever say so.

### 5.3 ⛔ The locale-parameterised chart query — nobody built it, and here is how close they got

The correct SQL access idiom **does** appear, in three queries:

```sql
SELECT COALESCE(rc.localized->'name'->>'<locale>', rc.name, '<fallback>') AS reason, …
```

`localized -> '<camelCaseField>' ->> '<locale>'` with a `COALESCE(jsonb, base_column, literal)` chain. **All
three pin the locale literally.** Nothing injects the session locale into a chart query.

> If a brief needs translated category axes, either **(a)** add a hidden `Locale` filter-bar parameter and
> write `localized->'name'->>{name:'Locale', type:'string'}`, or **(b)** build the visual as a studio
> component (doc 09). Do not assume it will just work.

---

## 6. Groovy — three answers to "my rule returns text a human reads"

### 6.1 ✅ A message bank over the session locale

```groovy
def loc = service.global.locale.getKey() ?: '<default>'
def MSG = [
  incomplete: [ <l1>: '…', <l2>: '…', en_US: 'The record is incomplete.' ],
  evidence:   [ <l1>: '…', <l2>: '…', en_US: 'Attach the supporting document first.' ] ]
validation.addError(MSG.evidence[loc] ?: MSG.evidence.en_US)
```

This is the pattern to write for 3+ locales. For a strict two-locale project the pair-closure is tighter and
unmissable in review:

```groovy
def loc = (context.data.getAttr('__loc') ?: service.global.locale.getKey() ?: 'en_US') as String
def alt = loc.toLowerCase().startsWith('<prefix>')
def T   = { en, other -> (alt && other) ? other : en }
```

### 6.2 ⛔ `context.data.localeKey` is always null — and it spread by copy-paste

Doc 20 predicts it and the corpus confirms it: one delivery has **113 rules reading
`context.data.localeKey` and 0 reading `service.global.locale.getKey()`**. The field is null in every one of
them; those rules only work because of a second, client-supplied attribute the authors had to invent
themselves.

### 6.3 ⚠️ `ctx.callRule` does not carry the header language switch

Doc 20 §iv workaround 3 states that a studio script's `ctx.callRule` runs the rule with the viewer's session
locale, and calls it "the only path on which a chart's static text genuinely follows the language". The
authors of the largest studio layer **observed otherwise** and wrote a client-side bridge across 17 screens,
recording the reason in a code comment: the server decides its language from the session locale, which does
not follow the header switch. **Qualify the doc's claim, and pass the locale explicitly** — read it on the
client and send it as an argument:

```js
const loc = document.documentElement.lang || 'en_US';
const data = await ctx.callRule('<Screen> Data', { __loc: loc, … });
```

---

## 7. Printed and mailed documents — the alias family

There is no locale map on a mail or PDF template. The mechanism is one template per language with its own
alias, chosen by the sender:

```
<purpose>Hy   <purpose>Ru   <purpose>En          # 13 families in the best delivery, 5 in the runner-up
```

```groovy
def suffix = _localeSuffix(recipientEmail)        // look the recipient up, do not assume the session
service.report.pdf.email."${'statement' + suffix}"([recipient], [ … ], [pdf])
```

✅ **Choose the template by the recipient, not by the session.** One case can write to three people in three
languages; a `localeKey` on the case cannot express that, and a template family can.

---

## 8. Entity data — the layer where two of four are silently broken

### 8.1 The column spelling is settled: `localized`

3/3 of the deliveries that use it spell the **column** `localized`, while the **wire key stays `localize`**
(§4.2). Doc 20 offers both spellings for the column; take `localized` unless a sibling CRUD in the same
project already says otherwise.

### 8.2 It must be declared TWICE in `dynamic-cruds.json`

```jsonc
{ "alias": "holiday",
  "localizationField": "localized",                                                   // 1. the pointer
  "dtoFields": [ …,
    {"fieldOrder":3,"fieldName":"localized","displayName":"localized","fieldType":"ObjectNode"} ] }  // 2. the field
```

One delivery ships **6 CRUDs where the pointer is set and the field is absent** — and for three of them the
table has no such column either. Dead config: the executor has nothing to alias.

### 8.3 ⛔ The jsonb shape — field → locale → value, and the default locale must be present

```json
// RIGHT
{"name":        {"en_US":"New Year",       "<l1>":"…", "<l2>":"…"},
 "description": {"en_US":"A public holiday","<l1>":"…", "<l2>":"…"}}

// WRONG — locale at the top level, no field level
{"en_US": "Cotton, black", "<l2>": "…"}
```

One delivery filled **177 of 177 rows** in the wrong shape — the DDL is right, the dump looks 100 % complete,
and **176 of them are unreadable**: the lookup is `row["localize"][field][locale]`, so with a flat map the
field level is missing, the read falls through to the base column, and **every locale shows the default
language**. The project looks fully localized in the dump and is entirely monolingual on screen. Exactly one
row has the correct shape — the hand-fixed one, which is how you can tell it was a bulk seed nobody re-opened
in the browser.

✅ **Gate any hand-seeded jsonb**: every top-level key is a **camelCase field name**; every second-level key
is a **locale from `tenant.json.locales`**; the **default locale is present** and equals the base column.

### 8.4 ⛔ Localize prose only, and only on dimensions

One delivery's 839 localized rows include maps over a square-metre figure, a temperature, a code and a
**foreign-key integer** — because a bulk localize ran over every column. They are single-locale, they add
nothing, and they make "is every map covered?" impossible to answer green. The best delivery's 131 field maps
are exactly `name` (124) and `description` (7).

And **localize the dimension, never the fact.** Every localized table in all four is a reference or dimension
table; not one transaction table is localized anywhere. Transaction rows carry codes and amounts, and their
prose fields are user-entered free text nobody will translate.

### 8.5 ⛔ Never build `<field>_en` / `<field>_xx` sibling columns

One delivery runs both mechanisms at once — 21 tables with per-language sibling columns, 15 of which *also*
carry the jsonb. The other three have zero, and the reasons are concrete: the platform's localized-value
reader cannot resolve sibling columns, so a table shows both as separate columns; every rule needs
hand-written choose logic; and a third language becomes a DDL migration instead of a jsonb key. The same
project's jsonb even localizes fields named `labelEn` and `nameEn` — a translation map over a column that is
already per-language.

### 8.6 The control flag and its three-way coherence test

```jsonc
// dynaform.form.text.field.plugin → properties.settings.stringValue
{"scope":"CRUD","contextIdentifier":"…","crudAlias":"holiday","fieldExpression":"name",
 "localized": true,                       // ← the flag; nothing else changes
 "dataClass":"java.lang.String","alwaysMandatory":true,
 "mandatoryValidationMessages":{"<l1>":"…","<l2>":"…","en_US":"Name is required"}}
```

`localized:true` appears only on text and textarea controls (and rarely a dropdown). For every CRUD alias:

```
has localizationField  ⟺  its form is multiLanguage:true  ⟺  it has ≥1 localized:true control
```

| | column | `multiLanguage:true` forms | CRUDs written by a localized control | verdict |
|---|---|---|---|---|
| **C** | 8 / 31 | **8 / 38** | 8 | **coherent** |
| B | 5 / 38 | 32 / 32 | 5 | data fine, 27 pointless locale switchers |
| A | 118 / 163 | 138 / 142 | 29 | **90 jsonb columns nothing ever writes** |
| D | 0 / 12 | **16 / 16** | 0 | pure theatre — a switcher on every form, nothing behind it |

✅ **Only one delivery sets `multiLanguage:false`** (30 of 38 forms). That is the discipline: the flag renders
a locale switcher, so it belongs only on a form that has something to switch — including on a multilingual
project.

---

## 9. What a third language actually costs

One trilingual screen of 132 nodes carries **91 per-locale maps of 8 distinct kinds ≈ 273 authored strings**,
none of which auto-fill on import. Multiply by the page count before promising a language, and put the number
in front of the customer during the Phase-0 elicitation — doc 19 asks which languages the UI must support but
does not tell the integrator what the answer costs.

---

## 10. Corrections to [20-localization.md](../20-localization.md)

| doc 20 says | the deliveries show | verdict |
|---|---|---|
| the chart is "the one dead zone" | the html plugin's markup is the same hole and there are 15× more of them; Groovy-returned text is a third, larger one | **add both**, and rank them by node count |
| a multilingual CHECK vocabulary must become a lookup table + choices rule | 32 inline literal `ENUM_*` rules do it with no table, no migration, no seed | **add the cheaper form and make it the default for CHECK vocabularies** |
| the localization column is spelled `localized` or `localize` | the column is `localized` 3/3; the wire key is always `localize` | **state the split as a one-liner** — Groovy sees `localize`, SQL sees the column |
| `ctx.callRule` runs the rule in the viewer's session locale | the largest studio layer observed the opposite and shipped a client-side bridge | **qualify it**; pass the locale explicitly as an argument |
| "same string in every locale" is a defect | two exceptions are legitimate — `localizedMap.icon` and deliberate blank spacers | **name the exceptions** so the check stays credible |
| — *(unstated)* | auto-translate rewrote icon **class names** in all four | **new rule**: never put a non-prose value where the translator can reach it |
| — *(unstated)* | the localization column must ALSO be a `dtoFields` entry of type `ObjectNode` | **new rule** — 6 CRUDs shipped the pointer with no field |
| — *(unstated)* | a hand-seeded jsonb in the wrong shape imports cleanly and renders monolingually | **new gate** (§8.3) |
| — *(unstated)* | localize the dimension, never the fact; prose only | **new rule**, 4/4 convention |
| — *(unstated)* | a multilingual project should still set `multiLanguage:false` on forms with nothing to switch | **new rule** |
| — *(unstated)* | page title/description is the only slot `locale fill` and `validate` both ignore | **new audit**, run it before every pack |


---

## Done when

- The locale set and the default are set on the tenant, and the default is the one the **operators** read —
  not the one the builder happens to type in.
- Every slot that *has* a per-locale map is filled for every locale: nav labels, page titles **and**
  descriptions, form and control labels, help text, mail and PDF templates.
- Every **dead zone** has its named escape hatch in place — the message bank for Groovy-returned text, the
  token/label bridge for chart text, a plugin for every visible string in authored markup. A dead zone left
  unhandled is not a gap in the platform; it is a monolingual screen you shipped.
- The **three-way coherence test** passes: the CRUDs carrying a localization column are exactly the CRUDs whose
  forms are `multiLanguage:true` are exactly the CRUDs with a localized dropdown source.
- Localization is on the **dimension, never the fact**, and only on prose — never a number, code, date or FK.
- The page **title and description** audit has been run: it is the one slot neither `locale fill` nor
  `validate` looks at.
- Someone has switched the language in the running application and read one screen of each kind end to end.
  Nothing here is verified until that has happened.
