# 20 — Localization (the hub)

> 📐 **Field evidence — the slots that really carry locales, and the dead zones:** [07-localization.md](references/07-localization.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

**What this is.** The single entry point for *"how localization works"* across the platform (Dokie / NCT /
mrjun) and, more usefully for a builder, **what you must author per locale in the export and what you cannot**.
Localization is genuinely cross-cutting: ~15 of the other docs each carry their own slice. This doc gives the
**layer model**, the **complete per-locale export-key inventory** (linking into the doc that owns each exact
JSON), and the one rule that is missing everywhere else — **hand-authoring the export gets you no
auto-translation, so you must fill every `tenant.json.locales` key yourself.**

Every claim below is stated as **behaviour you can observe in a running project or in the export JSON**.
Component names (`SiteStringResourceLoader`, `DynamicMethodExecutor`, …) are given so you can ask the platform
team a precise question — they are not paths you need to open, and no source line numbers are cited because
they go stale on every rebuild. Claims about the export shape were checked against real, working project
exports — you can re-check any of them with `jq` against your own bundle.

---

## (i) The layer model — L0 to L5

Localization is six distinct concerns. A builder editing `.mrjun` touches **L0, L2, L3** directly; **L1, L4, L5**
are runtime/platform behaviour you author *toward* but cannot fully set from the export.

| Layer | Concern | Where it lives | Author from the export? |
|---|---|---|---|
| **L0** | The **locale set** (which languages exist) | `tenant.json.locales` | **Yes** — the `locales` array (only) |
| **L1** | **Key-based UI strings** (buttons, menu chrome, framework messages) | `nct-localization` microservice DB (`translation` table) | **No** — not in the export at all |
| **L2** | **Content maps** — per-locale *authored* text (names, captions, labels) | `branches.json` / `rep-objects.json` (`localizedNames`, `localizedStringValue`, …) | **Yes** — you write every map |
| **L3** | **Entity data** — per-locale *row values* | `localize[field][locale]` inside a jsonb column, in `project-db.dump` | **Yes** (+ runtime bulk auto-fill) |
| **L4** | **Runtime resolution & rendering** — session locale → tables/forms/Groovy | runtime (session / cookie / `?lng`) | **Partially** — the `multiLanguage`/`localized` flags author the behaviour |
| **L5** | **Auto-translate** — an external MT service fills empty locales | live UI only (never on import) | **No** — understand it, then hand-fill |

**The one thing to remember:** L2/L3 maps are keyed by the full locale string (`en_US`, `hy_AM`, …). Resolvers
fall back **full-key → language-only (`en`) → first non-blank → legacy scalar** (where a deprecated scalar still
exists). Empty target-locale slots are auto-filled **only inside the live UI (L5)** — on **import there is no
translation**, so a blank locale stays blank. Author every locale.

---

## (ii) L0 — the locale set

`tenant.json.locales` is a JSON array of Java `Locale.toString()` keys — one entry per language the project
offers, in your chosen order:

```
["en_US"]                      a single-language project
["en_US","de_DE"]              two languages
["en_US","ru_RU","hy_AM"]      three; the first is the fallback when defaultLocale is unset
```

- Stored per project on the tenant: `TenantDomain` — `g_locales` (`ArrayList<Locale> locales`,
  `TenantDomain.java`)
  and `g_default_locale` (`Locale defaultLocale`). `getLocales()` falls back to
  `[SecurityLocaleUtils.defaultLocale()]` when empty.
- **DEFAULT language — `tenant.json.defaultLocale` (round-trips; SET IT).** The project has a DEFAULT/authoritative
  locale, chosen in the settings plugin ("Default language" dropdown, `LocalizationSection.java` → `TenantDomain.
  setDefaultLocale`, DB col `g_default_locale`; it auto-resets to `locales[0]` if the chosen default leaves the
  selected set). It is what base-column values, the form default-locale write (`BaseFormControl`), choices-label
  fallback, and `locale fill`'s source all key off. **It round-trips in the `.mrjun` as `tenant.json.defaultLocale`**
  (a `Locale.toString()` string, e.g. `"hy_AM"`; gson serializes/parses it): export copies it
  (`TenantServiceImpl.copyTenantForExport`), and import applies it on both paths — the content-import path
  (`ProjectServiceImpl` `else` branch) now `setDefaultLocale`s it too, guarded to `defaultLocale ∈ locales`.
  ⚠️ *Older exports omit it* (it was null when they were made, and gson skips nulls — do not conclude it "can't be
  set"). **Author it:** `mrjun.py locale set-default --locale <loc>` (must be one of `locales`). The toolkit's
  `default_locale()` = `tenant.json.defaultLocale` when set-and-valid, else `locales[0]`
  (`tools/mrjunkit/core.py`). If you don't set it, consumers fall back to `locales[0]` — so **put your authoritative
  language FIRST in `locales` AND set `defaultLocale` to it** (belt and braces).
- Global supported-locale seed for the RichWicket framework: `ReportWicketApplication` registers
  `en_US, ru_RU, hy_AM` with default `hy_AM` via `RichCoreSettings.addLocale(...).setDefaultLocale(amLocale)`
  (`ReportWicketApplication.java`). This is the
  framework default, distinct from the per-project `tenant.json.locales`.

**Builder rule:** decide `locales` in **Phase 0** ([19](19-build-decision-procedure.md)); it is a
high-blast-radius parameter — every `localizedNames`/`localizedButtonNames`/nav `localizedMap`/enum `displayName`/
caption/label you write later must cover exactly this set. ⚠️ **ASK the user (AskUserQuestion) — do NOT pick a
default** (`system_prompt.txt` Operating Principle 1). "Ask *or* record an assumption" is too weak here: a wrong
locale set re-touches every downstream entity, and — just as bad — **a single-language project that was
mistakenly built multilingual carries dead `localized` machinery** (see the single-language rule in §iv). Get the
exact set, then honour it everywhere. **Also decide WHICH of the chosen locales is the DEFAULT** (authoritative)
language — the one the PRD is written in / base values are authored in — then set it: put it **first** in
`tenant.json.locales` AND run `mrjun.py locale set-default --locale <loc>` (§ii). For a single-language project the
default is trivially that one language.

---

## (iii) L1 — key-based UI strings (understand, do NOT author)

Static UI text (button captions, menu chrome, framework messages — the strings a `<wicket:message>` or
`getString(key)` resolves) is **not** stored in `_xx.properties` files (there are **zero** locale-suffixed
`.properties` in nct-ui) and **is not in the export**. Wicket string resolution is bridged to a **localization
microservice**:

```
Wicket getString(key) / <wicket:message>
   └─ SiteStringResourceLoader (IStringResourceLoader)      SiteStringResourceLoader.java
        └─ LocalizeService.getMessage(key, locale)
             └─ Feign LocalizationClient  ── HTTP ──▶  nct-localization microservice
                  (base `/api/localization`)
                     └─ translation table (unique on kkey,target_lang)  TranslationEntity.java
                          └─ external MT service (en → target)         LocalizationServiceImpl.java
```

- Loader + registration: `SiteStringResourceLoader implements IStringResourceLoader`
  (`nct-ui/.../config/wicket/localize/SiteStringResourceLoader.java`) →
  `LocalizeService.getMessage(key, locale)`. Registered in the Wicket app:
  `ReportWicketApplication.java` (and) `getStringResourceLoaders().add(new SiteStringResourceLoader())`
  custom `Localizer` (`ReportLocalizer`), custom message resolver (`ReportMessageResolver`).
- Feign client `LocalizationClient` (`nct-ui/.../feign/LocalizationClient.java`) endpoints:
  `GET /internal/message`, `GET /internal/keys`, `POST /internal/setmessage`
  `POST /internal/translatePure`.
- The microservice module = **`nct-localization`**. Controller
  `nct-localization/.../controller/LocalizationController.java` — base `@RequestMapping("/api/localization")`,
  every endpoint `@Secured("ROLE_INTERNAL_SERVICE")`. `GET /internal/message` returns the supplied default
  **verbatim for `en_US`**; for any other locale it translates from `en` into that locale's language part
  (the segment before the `_`).
- Storage = table **`translation`**, unique on `(kkey, target_lang)`
  (`nct-localization/.../entity/TranslationEntity.java`). Engine = an **external machine-translation service** configured per deployment
  (`LocalizationServiceImpl.java`; DB-cached lookups, uncached `translatePure`). No
  LLM in the path.
- The admin UI to edit these key translations = plugin **`admin.localization.plugin`**
  (`nct-ui/.../plugin/admin/localization/LocalizationPlugin.java`), catalogued in
  [14-plugin-catalog-all.md](14-plugin-catalog-all.md).

> **Builder relevance.** These strings live in the localization-service DB, **not** in `branches.json`. A builder
> editing `.mrjun` **cannot** set them and should not hunt for them in the export. The line to keep straight:
> **UI-chrome text = L1, out of reach; content/data text = L2/L3, editable.**
>
> The real controller base is `/api/localization` with every method under `/internal/…`
> (`@Secured("ROLE_INTERNAL_SERVICE")`, `LocalizationController.java`).

---

## (iv) L2 — content / authoring per-locale maps (editable in the export)

Everything with per-locale *authored* text that you write into `branches.json` / `rep-objects.json`. The shared
editor is `LocalizedTextFieldsPanel` (`nct-ui/.../component/localized/LocalizedTextFieldsPanel.java`) — one
text field per `tenant().getLocales()`, backed by `IModel<Map<String,String>>`.

### The export-key inventory

Each row links (file-level) to the doc that owns the exact JSON shape — do not duplicate it here.

| Export key | On what | DTO / storage | Documented in |
|---|---|---|---|
| `localizedStringValue` (slot `propertyType:LOCALIZED_STRING`) | content-property text: page `pageTitle`/`pageDescription`, label `text`, link `name`/`link`/`params`, localized HTML | `ContentProperty`; `LocalizedHeaderPlugin` (mrjun) `text`; `LocalizedLinkLabelPlugin`; `html.localized.plugin` | [01](01-content-model-and-pages.md), [03](03-generate-fields-from-crud.md), [14](14-plugin-catalog-all.md) |
| `localizedNames` | CRUD table/tree **column** captions & **action** names; process-table columns; List columns; **subform** names; **tab** names; user-task actions | `CrudTableColumnSettings.java`; `CrudTableActionsDto$ActionDto.java`; `ProcessTableFormControlSettings.java`; `SubformSettings.java`; `TabModel$TabItem.java`; `UserTaskActionsDto.java` | [04](04-crud-table-plugin.md), [05](05-crud-tree-and-process-table.md), [06](06-form-groups-and-mapping.md), [07](07-workflows-and-tasks.md), [01](01-content-model-and-pages.md) |
| `localizedButtonNames` | in-form SUBMIT-button label for a **non-direct** action; CRUD import button | `CrudTableActionsDto$ActionDto.java` (falls back → `localizedNames`) | [04](04-crud-table-plugin.md), [06](06-form-groups-and-mapping.md), [07](07-workflows-and-tasks.md) |
| `localizedLabels` | Dynaform **action button** plugin label | `ActionButtonSettings.java` (editor `ActionButtonSettingsPanel.java`) | [02](02-form-controls-reference.md), [14](14-plugin-catalog-all.md) |
| `defaultValueLocalized` | form-control static default value, per locale (for `localized:true` fields) | `FormControlSettings.java` | [02](02-form-controls-reference.md), [03](03-generate-fields-from-crud.md) |
| `localizedHeaderLabel` | List form-control heading | `ListFormControlSettings.java` | [02](02-form-controls-reference.md) |
| `infoText` | generated-field help/tooltip text (map) | `GenerateFieldsFromCrudDialog.java` (editor), `RowField.infoText` | [03](03-generate-fields-from-crud.md) |
| `mandatoryValidationMessages` / `validationMessages` | localized "required" / validation error texts | `FormControlSettings.java`; `ConditionalValidation` | [02](02-form-controls-reference.md), [08](08-groovy-rules-and-context.md) |
| `helpSettings.localizedMap.message` | `nct.help.plugin` message per locale | help plugin settings | [03](03-generate-fields-from-crud.md), [14](14-plugin-catalog-all.md) |
| `localizedMap` (nested `field → locale → value`) | left-nav quick links (`linkModel.localizedMap`); tab legacy `localizedMap.name`; any `LocalizedBean` | `richwicket .../model/locale/form/LocalizedBean.java`; `TabItem extends MicroserviceTranslatedLocalizedBean` (`TabModel.java`) | [01](01-content-model-and-pages.md), [14](14-plugin-catalog-all.md), [17](17-left-nav-quick-links.md) |
| ⛔ **none — no per-locale key exists** | **chart text**: everything typed into a `chart.js.plugin`'s JS / HTML / Css tabs (title, axis titles, legend, dataset labels, tooltip strings, the HTML heading) | `ChartJsModel` in `properties.Javascript.stringValue` — `js`, `html`, `css` and each `cssByTheme` block are **plain `String`s**, no map, no `LOCALIZED_STRING` slot | ⛔ see "Chart text has NO per-locale slot" below + [22](22-charts-params-and-filters.md) |

Two per-**form**/per-**control** flags gate L3 (not maps themselves), covered under L4 below:
`multiLanguage` (`FormDto.java`, `isMultiLanguage`) and `localized` (`FormControlSettings.java`).

### ⚠️ Load-bearing rule — no legacy `name` on a CRUD `ActionDto` → the action renders **blank**

`CrudTableActionsDto$ActionDto` has **no** `name` field — its declared fields are exactly `id`, `localizedNames`,
`localizedButtonNames`, `icon`, `formGroupIdentifier`, `direct`, `predicateIdentifier`,
`onBeforeStartRuleIdentifier`, `onBeforeCompleteRuleIdentifier`, `submitForm`
(`nct-ui/.../plugin/crud/CrudTableActionsDto.java`), and `getLocalizedName(locale)` reads `localizedNames`
only. So an action authored with only a top-level `name` **renders with an empty label**. Columns and tabs
*do* keep a deprecated `name` fallback (`CrudTableColumnSettings.java`, `TabModel.java`) — actions do
not. **Author `localizedNames` (and `localizedButtonNames` for non-direct actions), covering every locale.**

### The coverage rule

**Author every `tenant.json.locales` key in every L2/L3 map.** Blank target-locale slots are auto-filled **only
in the live UI** (L5) — on **import there is no translation**. This is exactly the
[13 §5](13-master-playbook-empty-to-dynamic-project.md) checklist item "`localizedNames`/`localizedButtonNames`
cover all `tenant.json.locales`" and the [19](19-build-decision-procedure.md) Done-when gate.

### ⚠️ Two failure modes authors hit (both were live bugs — check them every build)

**1. Same string in every locale → that language shows under ALL locales.** A per-locale map filled with one
value — `{"en_US":"Ստորաբաժանումներ","ru_RU":"Ստորաբաժանումներ","hy_AM":"Ստորաբաժանումներ"}` — is **not** localized:
the English UI shows Armenian (covering all keys is necessary but **not sufficient** — the *values* must differ per
language). Two toolkit paths silently produce exactly this and MUST be corrected:

- **Nav quick links.** `quicklink add --label <one string>` fans that single label across every locale
  (`quicklink_cmds.py._localized_map` = `{loc: name for loc in locales}` — one string → all keys). For a
  multilingual project, pass **per-locale labels**: `quicklink add --page X --label-loc en_US=Employees
  --label-loc ru_RU=Сотрудники --label-loc hy_AM=Աշխատակիցներ …` (repeatable; the toolkit now warns if you pass a
  single `--label` on a 2+-locale project). Use the single `--label` only for a **single-language** project. See
  [17](17-left-nav-quick-links.md). (`validate` also WARNs when a multilingual project has an authored per-locale
  name map whose values are identical across locales.)
- **Enum dropdowns.** An `enumValues` snapshot carries ONE `displayName` per value — a single string, shown under
  every locale. For a MULTILINGUAL project, localize the options via a **choices rule** over a `localized` lookup
  table ending in `toSelectOptionsLocalized(list,"<key>","<display>",null,"<localizationField>")`
  ([02](02-form-controls-reference.md) §4a, [08](08-groovy-rules-and-context.md)) — NOT a one-string snapshot.
  A snapshot is acceptable **only** for a single-language project or a genuinely code-only value the user never
  reads in prose. (An enum backed only by a CHECK constraint that must be multilingual ⇒ promote it to a small
  `localized` lookup table + a choices rule.)

**2. SINGLE-LANGUAGE project (locales has exactly ONE entry) — author NONE of this machinery.** `localized:true`,
entity `localize`/`localized` jsonb, `multiLanguage:true`, and multi-key per-locale maps all exist to serve **2+**
locales; with one locale they are pure overhead and the very source of the "same string everywhere" confusion.
Author **plain values**: single-key maps (or the deprecated `name`/base column where allowed), **no**
`localized:true` on any field, **no** `localize` jsonb, **no** `multiLanguage:true`. This is decided by the
Phase-0 language elicitation — do not stamp `localized` reflexively.

### ⛔ Chart text has NO per-locale slot — the one dead zone in this doc

Every other authored string above has a per-locale map. **A chart does not.** A `chart.js.plugin` node keeps its
whole configuration in `properties.Javascript.stringValue`, and in that model the `js`, `html`, `css` and each
per-theme `cssByTheme` block are **plain strings** — there is no `localizedJs`, no `localizedMap`, no
`LOCALIZED_STRING` property slot anywhere in the chart model (see the [22](22-charts-params-and-filters.md) field
list). So every word typed into the JS tab — `title.text`, axis titles, legend and dataset `label`s, tooltip
callbacks — and every word in the HTML tab renders **identically under all locales**. There is nothing for
`mrjun.py locale fill` to fill and nothing for `validate` to warn about: **the gap is invisible to every offline
gate** (also listed in [23 §4](23-distribution-and-known-gaps.md)).

What *is* localized without any authoring: the platform's own chart chrome. The click-to-filter badge ("Click to
filter" / "Clear filter") is resolved through the **L1** key path (§iii), so it follows the viewer's language.

**Workarounds, best first.** Each moves the words out of the chart's own string slots:

1. **Put the wording OUTSIDE the chart.** A heading/caption authored as an `nct.label.plugin` sibling above the
   chart carries a real `LOCALIZED_STRING` `text` property (row 1 of the inventory), so it is per-locale like
   everything else. Keep the chart itself wordless: no `title` in the JS, series identified by the data. This is
   the cheapest correct answer and it is what a multilingual dashboard should do by default.
2. **Bind the remaining text as DATA, through a replacement query.** A `$$('<name>', <default>, 'String[]')`
   placeholder whose replacement uses the **Query** strategy takes its value from a SQL column — so a query that
   selects the per-locale text (e.g. the `localize`/`localized` jsonb key of §v) feeds translated category labels,
   series names and axis captions into the chart. ⚠️ **Nothing injects the session locale into a chart query.** A
   replacement query is executed with the parameter values the shared filter bar put in the session
   ([22](22-charts-params-and-filters.md)), so there is no automatic `:locale` — the locale has to arrive as an
   ordinary query parameter (a filter-bar param, with a default), or the SQL has to pick a locale itself. That
   makes this workaround good for *data-derived* labels and awkward for anything else.
3. **Build the visual as an HTML Component Studio component instead** ([24](24-html-component-studio.md)). A studio
   script's `await ctx.callRule('<Rule>')` runs the rule with the **viewer's session locale** placed in the rule
   context, so `service.global.locale.getKey()` (§vi) inside that Groovy returns `en_US`/`hy_AM`/… and the rule can
   hand back every label already translated. This is the only path on which a chart's *static* text genuinely
   follows the language. ⚠️ `ctx.callBl` carries **no** locale — use `ctx.callRule` for anything locale-aware.

For a **single-language** project none of this matters: type the text in that language and move on — one more
reason to settle `locales` in Phase 0 before any dashboard work starts.

### ⛔ A GROOVY RULE has no locale — every sentence it shows carries all of them at once

A rule cannot ask which language the caller is reading in. `service.global.locale.getKey()` answers
only where a session context reached the rule (§vi); a persist hook, an action engine, a workflow
complete-rule and a scheduler sweep have none. So every string a rule hands a user —

* `throw new RuntimeException('…')` → the red toast,
* `return [ok: true, message: '…']` → the green toast,
* an audit `note: '…'` → the register,

— must carry **every project language in the one string**, conventionally separated by ` / `:

```groovy
throw new RuntimeException('Այս կարգավիճակում փոփոխությունն արգելված է'
    + ' / Изменение в этом статусе запрещено'
    + ' / A record in this status cannot be edited')
```

When the sentence is built from values, repeat the value per language rather than appending it once:

```groovy
message: 'Ստեղծվեց ' + n + ' խմբաքանակ'
       + ' / Создано партий: ' + n
       + ' / Lots created: ' + n
```

**Why this is the most-missed layer.** Everything visible on a happy path is L2 content with a real
per-locale map, so the screens look perfect in all three languages. Rule strings only appear when
something is **refused** — a wrong status, a missing right, a blocked close — and a walkthrough that
completes successfully never sees one. Measured on a delivered MES: **170 monolingual user-facing
sentences** shipped behind screens that had been reviewed in all three languages.

Two more places the same blindness hits:

* **`hy / ru` but no `en`.** A partially translated string passes the eye of a reviewer who speaks
  the first two. Count the segments, do not read them.
* **Latin words inside the other languages.** `Պատվերը փակված է։ Պատրաստի lot՝ …` reads as unfinished
  in Armenian; so does an Armenian sentence pasted into the Russian segment.

`mrjun.py validate` reports a user-facing rule expression written in one script — it reads the whole
`+`-chain, so a message assembled per language is correctly seen as multilingual.

### ⛔ An enum column shows its raw CODE unless you point at the translated twin

`WAITING_MATERIALS`, `CHOCO_DRIED_FRUIT`, `BOX` — the same text in every language. Enum localisation
is **three** edits and the middle one is the one that gets skipped:

1. join the vocabulary in the crud's SQL and select the code as `<field>_label`;
2. publish the translation: `'<field>Label', COALESCE(rl.localize->'label', '{}'::jsonb)` inside the
   row's `localize` object;
3. **point the table column's `fieldExpression` at `<field>Label`** — the step that is forgotten,
   because after (1) and (2) the data is right and the screen still is not.

The same applies to a **joined** entity's name: the parent's `localize` needs the nested key
(`'item', jsonb_build_object('name', COALESCE(j1.localize->'name', '{}'::jsonb))`) or the column over
`item.name` prints whatever the base column holds.

### ⛔ A REPORT does not inherit any of this

A report crud is SQL over a join, so it has no `localize` column of its own and nothing localises it.
It will happily select `s.name_hy` and print Armenian to an English reader. Build the map in the
SELECT and declare it:

```sql
SELECT …,
       jsonb_strip_nulls(jsonb_build_object(
           'skuName', s.localize -> 'nameHy',
           'status',  (SELECT rl.localize -> 'label' FROM ref_label rl
                        WHERE rl.vocabulary = 'order_status' AND rl.code = po.status
                          AND rl.deleted = false LIMIT 1)
       )) AS localize
FROM …
```

then set the crud's `localizationField` to `localize` and add `localize` to its `dtoFields`. The keys
are the **DTO field names the report's columns use** — `skuName`, not `sku_name`.

### ⛔ Four platform slots have no per-locale variant at all

Beyond charts (above), these render one fixed string under every locale:

| What | Where it comes from | Remedy |
|---|---|---|
| the breadcrumb's page name | the page's `name` field | derive it from the page's localized `<title>` / a generated alias→title map, in a global script |
| a crud table's card title | the dynamic CRUD's `name` | it duplicates the breadcrumb or the tab label on a tabbed page — hide it |
| the filter submit button | `settings.buttonName`, a plain STRING | swap the caption per `document.documentElement.lang` |
| the row-actions column header | platform-rendered | same |
| a process table's card title | the workflow's `name` | a name→caption table in the same script |

All five are display-only text, so the honest fix is one small **global resource**
([29-global-resources.md](29-global-resources.md)) that reads `document.documentElement.lang` and
rewrites them. Keep it to captions the platform genuinely cannot localise — a global script that
starts rewriting *data* is a maintenance trap.

---

## (v) L3 — entity DATA localization (per-locale row values)

The value inside a data row, per locale. Structure: `localize[fieldName][localeKey] = value` (nested variant
`localize[field][jsonPath][locale]` for ObjectNode fields).

- **Canonical wire key = `localize`** — `DynamicMethodExecutor.LOCALIZATION_CANONICAL_KEY = "localize"`
  (`dynamic-integration-core/.../DynamicMethodExecutor.java`). Every UI consumer sends/reads this key.
- **Static CRUD** satisfies it by convention: a DTO field annotated `@LocalizationField`
  (`exec-reactor-core/.../crud/LocalizationField.java`) is literally named `localize`, type `ObjectNode`. Real
  annotated field: a DTO declares it directly, or inherits it from an abstract localized base DTO — either way
  the field is named `localize` and typed `ObjectNode`. `CrudReactor` enforces **exactly one**
  such `ObjectNode` field per class (`exec-reactor-core/.../crud/CrudReactor.java`; it errors both on
  multiple such fields and on a non-`ObjectNode` type).
- **Dynamic CRUD** has no Java DTO, so the author picks the underlying **jsonb column** name, stored in
  `DynamicCrudEntity.localizationField` (`dynamic-integration-core/.../entity/DynamicCrudEntity.java`). The
  executor **aliases that column to the canonical `localize`** on read (`mapRow`,
  `DynamicMethodExecutor.java`) and accepts it back under `localize` on write (the param unpacker;
  helpers `localizationFieldCamelCase`, `isLocalizationParam`). So a dynamic
  CRUD behaves identically to a static `@LocalizationField` DTO to every UI consumer.
- **Column spelling differs by project style** — projects in the wild spell the jsonb column either **`localized`**
  or **`localize`**, consistently across their CRUDs (check yours with
  `jq '.cruds[].localizationField' dynamic-cruds.json`; a CRUD with no localized data at all carries `null`).
  Both alias to the same wire key — see [10](10-database-management.md) §column style.
  Keep whichever spelling the sibling CRUDs use.

**What the stored jsonb looks like** (the map keys are the *DTO/camelCase* field names, e.g. `zoneType`, not the
DB column `zone_type`):

```json
{"name": {"en_US": "Wire Transfer", "hy_AM": "Փոխանցում"}, "termDays": {"en_US": "30", "hy_AM": "30"}, "categoryLabel": {"en_US": "Payment", "hy_AM": "Վճարում"}}
{"zoneType": {"en_US": "Bonded warehouse", "hy_AM": "Մաքսային պահեստ"}}
{"zoneType": {"en_US": "Logistics", "hy_AM": "Լոգիստիկա"}}
```

The column is `null` until localization is run for that row.

#### ⚠️ Load-bearing: a seeded key that is the COLUMN name is a translation that never applies

The camelCase note above is not cosmetic. The resolver looks the key up under the **DTO field name** the CRUD
exposes (`dtoFields[].fieldName`), so seeding the jsonb straight from the database column names produces a
column that never translates — and it fails **selectively**, which is what makes it expensive: single-word
fields (`name`, `node`, `detail`) spell the same in both conventions and work, so the register shows some
columns in the user's language and others in the authoring language, with a complete translation sitting in
the same jsonb on the same row. Nothing logs. It reads as "the translation is missing" and sends you to
look at coverage instead of at the key.

    seeded from the column      resolver looks for       result
    "main_node":     {…}        localize["mainNode"]     never applied, column stays in the authoring language
    "semi_finished": {…}        localize["semiFinished"] never applied
    "name":          {…}        localize["name"]         works — the two spellings coincide

`validate` now ERRORs on this (`_check_localize_keys`): it reads the jsonb keys out of `project-db.dump`, maps
each table to its CRUD via that CRUD's `findAll`, and reports any key that is a `displayName` (column) whose
`fieldName` is spelled differently, naming the key it should be. A key matching no field at all is a WARN —
dead weight, but harmless.

⚠️ When probing seeded coverage, remember the shape is `{field: {locale: value}}` — `localize ? 'en_US'` tests
the TOP level and reports 0 % on fully-translated data. Test `localize->'<field>' ? 'en_US'`, and see
[11](11-business-logic-dynamic-crud.md) for why that `?` cannot go in a CRUD method.

- **Per-field bulk Localize** (populate every row's `localize[field][locale]` across all locales by
  auto-translation, as a background task) = `CrudDataLocalizeService`
  (`nct-ui/.../service/CrudDataLocalizeService.java`): it pages the rows, translates via
  `localizeService.translatePure`, writes `entity["localize"][fieldExpression][localeKey]`, and persists via the
  CRUD's `update`. Driven from the DynamicCruds "Business Logic" plugin and the CRUD-table column
  "Localize" button. This is the main way real data gets translated at scale — see
  [11](11-business-logic-dynamic-crud.md).

**Builder note:** you can hand-seed the jsonb `localize`/`localized` values directly in `project-db.dump`
(matching the shape above, covering every locale), or leave it null and localize in the live UI post-import.
There is no toolkit command for it.

### The `localized:true` form-field flag — author the per-locale INPUT

L3 above is the *data*; this is the *form control* that writes it. A text/textarea/dropdown/… control reads &
writes per-locale values into `localize[fieldExpression][locale]` **only** when its settings carry
`"localized": true` (`FormControlSettings.localized`, `nct-ui/.../controls/config/FormControlSettings.java`
UI label "Localized" / "Store localized values for this field"). Three prerequisites, **all required**, or the
control silently reads/writes the base column → one language shows on every locale tab:

1. **The field:** add `"localized": true` to `properties.settings.stringValue`. (Nothing else changes: a
   localized "Name" field is ordinary text-field settings **plus** that one flag.)
2. **The form:** `multiLanguage: true` on the `FormDto` (`rep-objects.json → forms[]`) — renders the flag-tab
   locale switcher (`FormLanguageSelectorPanel`, `FormPlugin.java`); the single input rebinds to the
   selected locale.
3. **The CRUD + tenant:** the CRUD has a `@LocalizationField`/`localizationField` jsonb (L3 above) and the tenant
   has >1 locale.

**Write behaviour** (`BaseFormControl` read / write): editing in the **default** locale
writes both `localize[field][defaultLocale]` **and** the base column; a non-default locale writes only that
locale's slot; on read: current-locale value → (if missing & not default) auto-translate-from-default *and
persist* → base-column fallback.

> **Observed failure.** A form was already `multiLanguage:true`, but its "Name" field lacked `localized:true`,
> so every locale tab showed the same value — the base-locale column `<entity>.name`. Fix = add
> `"localized":true` to that one field's settings. A localized CRUD also wants its **dropdowns** on
> `toSelectOptionsLocalized` ([02](02-form-controls-reference.md) §4a) so the picker shows the viewer-locale label.

---

## (vi) L4 — runtime locale resolution & rendering

**The session locale is the render locale.** Everything below reads `getSession().getLocale()`.

- **Session locale resolution** — `PluginBasePage.defineLocale()` / `defaultLocale()`
  (`nct-ui/.../page/PluginBasePage.java`): order `?lng=` param → `?lang=` param → `lang` cookie →
  Wicket super default. **Language selector** = `HeaderLangSelectorPanel` (list = `tenant().getLocales()`
  on click `getSession().setLocale(...)` + save `lang` cookie).
- **Render consumers** call `LocalizedValueUtil.getLocalizedValue(row, field, locale)` (reads
  `row["localize"][field][locale]`, nested fallback, then the raw field —
  `nct-ui/.../utils/LocalizedValueUtil.java`): `CrudTablePlugin.java`
  `crud/tree/CrudTreePlugin.java`, `process/ProcessTablePlugin.java`
  `dynaform/form/controls/list/ListFormControlPlugin.java`. (Enum projection takes priority over value
  localization in table columns — [04](04-crud-table-plugin.md).)
- **Forms** read/write per the current form locale. A control stores localized values only when the **form** is
  `multiLanguage` (`FormDto.java`) **and** the **control** is `localized` (`FormControlSettings.java`).
  Current form locale = `getSession().getLocale()` → `tenant().getDefaultLocale()` → `locales.get(0)`
  (`FormPlugin.java`). Write-back `setLocalizedValueInCrud(...)` sets `localize[field][locale]`
  (`BaseFormControl.java`); GLOBAL/CONTEXT-scope fields use `attrs.__localize__[field][locale]` instead;
  missing locales are auto-translated on change (`translatePure`).
- **Groovy rules** get the locale from a ThreadLocal set before each rule runs: `LocaleContext.getLocaleKey()`
  (`nct-executor/.../globalfunctions/LocaleContext.java`, a `ThreadLocal<String>` set from
  `contextData.getLocaleKey()` at `rule/groovy/AbstractGroovyExecutor.java`, restored/cleared).
  Exposed to scripts as **`service.global.locale.getKey()`** (→ `en_US`/`ru_RU`; [16](16-groovy-service-api.md)).

  > ⛔ **`context.data.localeKey` is ALWAYS `null` — do not use it.** `context.data.<name>` is sugar for
  > `getAttr("<name>")` (`DynamicRuleContext.groovy` `propertyMissing` → `contextData?.getAttr(name)`),
  > and `getAttr` reads **only** the `attrs` map (`ContextDataDto.java`). `localeKey` is a *field* on
  > `ContextDataDto`, never mirrored into `attrs`, so the lookup misses every time.
  > **Symptom:** a rule returns `locale: null`, the UI silently keeps whatever default it already had, and the
  > project looks "mostly translated". It is copy-paste-prone: one author writes it, every later rule is pasted
  > from that one, and the project papers over the result by sniffing the browser language in JS.
  > `validate` does not catch this. **Fix:** `def loc = service.global.locale.getKey()`.

  Localized dropdown
  options: `service.global.conversion.toSelectOptionsLocalized(list, key, display[, localeKey,
  localizationFieldName='localize'])` (reads `item[localize][display][localeKey]` with fallback —
  [16](16-groovy-service-api.md)).
- **PDF** — the `nct-pdf` engine does **no** value localization/translation (it uses `Locale.ROOT` only for
  string-lowercasing). Any localized text in a PDF comes from the Wicket page/model that produced it. **Do not
  expect a PDF template to localize data values** — resolve the localized value in the Groovy that fills the
  template's `params`. (⚠️ UNVERIFIED that any specific PDF-producing page passes already-localized model text.)
- **Mail** — localized by **separate template per locale** (its own `alias`), **not** a per-locale field:
  `MailTemplateDto` (`nct-transfer/.../dto/MailTemplateDto.java`) has no `multiLanguage`/localized field —
  [15](15-pdf-and-mail.md) §3.3. Mail page locale is set from params → tenant default
  (`ReportMailBasePage.java`, note the deliberate typo `defalutLocale`); CMS `LocalizedBean` mail text is
  routed to the microservice by `@Primary ReportTranslationCacheServiceImpl` (cache-first, else
  `localizationClient.translatePure` — `nct-ui/.../service/ReportTranslationCacheServiceImpl.java`).

---

## (vii) L5 — the auto-translate mechanism (one engine, five entry points)

All auto-translation goes through the **external MT service**, reached the same way: `LocalizeService.translatePure` →
Feign `LocalizationClient` → `nct-localization` (`LocalizeService.java`; the engine is L1's
`LocalizationServiceImpl.java`). The five places it fires:

1. **`LocalizedTextFieldsPanel`** — on **blur of the default-locale row**, fills every still-empty target-locale
   slot. This is the L2-map editor (no button).
2. **`LocalizeService.seedLocalizedNames`** (`LocalizeService.java`) — builds a full name map, default slot
   verbatim + the rest machine-translated. Used seeding CRUD/tree **Create Default Actions**
   (`CrudTableSettingsControlPanel.java`, `CrudTreeSettingsControlPanel.java`) and generated field labels
   (`GenerateFieldsFromCrudDialog.java`, `ListFormControlSettingsPanel.java`).
3. **`BaseFormControl`** — fills the other locales when a form field value changes (L3).
4. **`CrudDataLocalizeService`** — bulk-localizes a whole column's data across all rows (L3).
5. **`ReportTranslationCacheServiceImpl`** + the key-based `generateDefaultMessage` path — mail + UI chrome
   (L1/L4).

> **Critical builder consequence (the reason for the coverage rule).** Auto-translate runs **only inside the live
> UI**. When you **hand-author the export you get NO translation** — you must write every `tenant.json.locales`
> key yourself in every L2/L3 map. A blank locale imported stays blank (it is only auto-filled if a human later
> edits it in the browser). This is why [13 §5](13-master-playbook-empty-to-dynamic-project.md) and
> [19](19-build-decision-procedure.md) demand full locale coverage.

---

## (viii) Toolkit + checklist

The `mrjun.py` toolkit reflects "no translation on import" — it never calls a translate service:

- **`quicklink`** copies the **same** text into every tenant locale (`tools/mrjunkit/quicklink_cmds.py`
  `{loc: name for loc in locales}` — verbatim copy, not translation). This *does* satisfy the coverage rule
  (every locale present), but every locale shows the default-language text until edited.
- **`workflow`** user-task actions copy the default text into **every** tenant locale
  (`tools/mrjunkit/workflow_cmds.py`, `{loc: name for loc in project.locales()}` for both
  `localizedNames` and `localizedButtonNames` — like `quicklink`).
- **`content`** page title/description write **only the default slot**
  (`tools/mrjunkit/content_cmds.py`, `loc = p.default_locale()`) — intentionally, page meta is EN-only baseline.
- `default_locale()` = `locales[0]` (`tools/mrjunkit/core.py`).

So `workflow add` and `quicklink` already cover all locales; after **`page add`** (and any hand-authored map) the
non-default locales may be **absent**. Two tools close *part* of the gap: **`mrjun.py locale fill`** (`locale_cmds.py`) copies
each flat per-locale map's default value into every missing tenant locale (content-node settings/model + crud-mirror
re-sync + structured rep-object maps; NOT `localize` jsonb, and NOT workflow actions embedded in `bpmnContent` —
those are seeded at `workflow add` time), and **`validate`** warns on any flat locale map (or workflow action map)
that misses a tenant locale (`validate_cmds.py:_FLAT_LOCALE_MAP_KEYS` + `_check_workflow_locales`).

⛔ **Neither tool touches LOCALIZED_STRING *property slots*** — `properties.pageTitle`/`pageDescription` on every
`page add`ed page, and `properties.text` on every `nct.label.plugin` (i.e. every form-field label,
[03 §4](03-generate-fields-from-crud.md)). They are filled by NOBODY and checked by NOBODY: `locale fill` reports
0 and `validate` stays green. Author every locale of those maps **by hand**. A missing locale is not a fallback:
a page title simply does not render in that language, and a label falls back to whichever language does have a
value — the "one language under all locales" bug at the top of this section.

**Localization pre-import checklist** (folds into the [13 §5](13-master-playbook-empty-to-dynamic-project.md)
and [19 Phase 14](19-build-decision-procedure.md) gates):

- [ ] Every L2 map (`localizedNames`, `localizedButtonNames`, `localizedStringValue`, `localizedLabels`,
      `defaultValueLocalized`, `localizedHeaderLabel`, `infoText`, `mandatoryValidationMessages`/
      `validationMessages`, `helpSettings.localizedMap.message`, `localizedMap`) covers **every**
      `tenant.json.locales` key. ⛔ `localizedStringValue` (page titles, labels) is neither filled by
      `locale fill` nor checked by `validate` — verify it by hand.
- [ ] No CRUD action relies on a top-level `name` — each has `localizedNames` (else it renders blank).
- [ ] Each `localized:true` control lives on a `multiLanguage:true` form.
- [ ] Dynamic CRUD `localizationField` matches the sibling style (whichever of `localized` / `localize` the
      project's other CRUDs use) and the jsonb column exists in `project-db.dump`.
- [ ] Any hand-seeded `localize`/`localized` jsonb data covers every locale (nothing gets translated on import).
- [ ] ⛔ **Charts:** on a 2+-locale project, no user-facing wording is typed into a `chart.js.plugin`'s JS/HTML
      (there is no per-locale slot — it would show one language to everyone). Headings live on an
      `nct.label.plugin`, labels arrive from the replacement query, or the visual is an HTML Studio component
      driven by `ctx.callRule` (§iv "Chart text has NO per-locale slot").

_Related: locale set + `tenant.json` → [00](00-export-format-and-import.md); the L2 shapes live in
[01](01-content-model-and-pages.md)/[02](02-form-controls-reference.md)/[03](03-generate-fields-from-crud.md)/
[04](04-crud-table-plugin.md)/[05](05-crud-tree-and-process-table.md)/[06](06-form-groups-and-mapping.md)/
[07](07-workflows-and-tasks.md); L3 in [10](10-database-management.md)/[11](11-business-logic-dynamic-crud.md)/
[18](18-existing-schema-to-dynamic-wiring.md); Groovy locale in [16](16-groovy-service-api.md); PDF/mail in
[15](15-pdf-and-mail.md); the chart dead zone in [22](22-charts-params-and-filters.md) and the HTML-studio
`ctx.callRule` escape hatch in [24](24-html-component-studio.md)._
