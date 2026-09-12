# Form settings, validations & field events

> 📐 **Field evidence — which validation mechanisms were used and which nobody touched:** [04-forms-actions-validation.md](references/04-forms-actions-validation.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / when to use

Two authoring surfaces sit **on top of** the form controls that [02-form-controls-reference.md](02-form-controls-reference.md)
and [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) describe. They are where most of the
"business behaviour" of a data-entry screen is configured, and the concepts a PRD names most often — *required*,
*"only Mon–Fri"*, *"must be a valid email"*, *warn but let them continue*, *"when Country changes, refresh the
City dropdown"*, *"hide the approval block until it is submitted"*, *"block save unless total = sum of lines"*,
*save a half-filled form and finish tomorrow*:

- **The control "Config" accordion** — per **control**; everything here lands in the control's own
  `properties.settings.stringValue` JSON (the `FormControlSettings` object of [02](02-form-controls-reference.md)).
  Sections: **Prohibited · Default value · Mandatory · Validations · Events**.
- **The "Form Settings" panel** — per **form** (the `FormDto` rep-object of [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md));
  everything here lands in `rep-objects.forms[]`, not in the content tree. Sections: name/contexts/**Multi Language**,
  **Allow Drafts**, **Hidden Content Configuration**, **Global Validation Rules**, **Action-Based Validation Rules**.

This doc is the **deep mechanics + decision guidance** for those two surfaces. The **export schemas** already live
in 02 (control settings: `conditionalValidations[]`, `eventComponentMappings[]`, `defaultValue*`, prohibited,
mandatory) and 06 (`FormDto`: `validators`, `actionValidators`, `hiddenConfigs`, `multiLanguage`, `allowDrafts`);
the Groovy `validation.*`/rule model lives in [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md).
**This doc does not re-print those schemas** — it documents the **dialog that generates each artifact**, the **exact
Groovy each validation template emits**, the **runtime behaviour**, and **when to reach for which mechanism** so the
builder AI wires them from a PRD without inventing non-existent knobs.

> **🔧 Tooling.** These are edited with the generic node/rep commands: `node patch-settings <id> --set key=…`
> (control `conditionalValidations`/`eventComponentMappings`/prohibited/default), `rule add --type PREDICATE`
> (a validation predicate) / `--type VALIDATION_RULE` (a form-level validator), and hand-editing
> `rep-objects.forms[]` for `hiddenConfigs`/`validators`/`allowDrafts` (there is no dedicated form-settings
> command). Full index — [`tools/README.md`](tools/README.md); before re-import — `mrjun.py validate`.

## 1. The control "Config" accordion → maps to `settings` keys

Opening a form control's settings (right nav) shows **three** outer accordion items:
**Mapping** (open by default — scope / crud / field / dropdown source, all in [02](02-form-controls-reference.md)),
**Config** (a cog icon — the five sections below), and **Audit Logs**. The Config item is present on **every** bound
field control (`supportsFieldConfigs()` defaults `true`, and was deliberately decoupled from whether the control has
a live scalar component — so DatePicker / Gantt / Comments / FileUpload / List show Prohibited/Mandatory/Validations
too; `BaseFormControl.java`).

Inside Config are **five flat bordered sections** (not nested accordions), in this fixed order — each writes distinct
keys onto the same `FormControlSettings` JSON:

| # | Config section | Writes into `settings` | Full schema |
|---|---|---|---|
| 1 | **Prohibited** | `alwaysProhibited` (checkbox → `true`/absent) **or** `prohibitedPredicateIdentifier` (a **PREDICATE** rule; predicate-true ⇒ read-only) | [02 §base](02-form-controls-reference.md) |
| 2 | **Default value** | `defaultValueEnabled`; `defaultValueStatic`; static → `defaultValue` / `defaultValueLocalized`; rule → `defaultValueRuleIdentifier` (an **EXECUTION** rule) | [02](02-form-controls-reference.md), [03 "Default column"](03-generate-fields-from-crud.md) |
| 3 | **Mandatory** | `alwaysMandatory` **or** `mandatoryPredicateIdentifier` (a **PREDICATE** rule); `mandatoryValidationMessages` (per-locale) | [02 "Mandatory validation"](02-form-controls-reference.md) |
| 4 | **Validations** | `conditionalValidations[]` (each `{predicateIdentifier(**PREDICATE**), severity, validationMessages}`) — authored via **"Add Validation"** or **"Create from Template"** (§2) | [02 `conditionalValidations`](02-form-controls-reference.md) |
| 5 | **Events** | `eventComponentMappings[]` (each `{eventName, componentIdentifier, executionRuleIdentifiers[]}`) (§3) | [02 `eventComponentMappings`](02-form-controls-reference.md) |

> Sections 1–3 (Prohibited / Default / Mandatory) are also authored by the **Generate-fields dialog** columns
> (Prohibited / Default / Required) — see [03](03-generate-fields-from-crud.md). Sections 4–5 are **not** Generate
> columns; they exist only in this panel (and in a hand-authored export). All five are just keys on the settings
> JSON, so **for a by-hand export there is no "accordion" to reproduce — you write the keys directly.** The accordion
> is only where a human clicks; know the name→key map above so a PRD phrase ("this field is warn-only", "refresh X on
> change") routes to the right key.
>
> ⚠️ **Two of these are half-content, not pure settings:** the mandatory **red `*`** and the help **"?"** icon are
> **not** produced by `alwaysMandatory`/help keys — the `*` is a `<span class="red ms-1">*</span>` in the slot's
> flex-header HTML and help is a separate `nct.help.plugin` node. A by-hand field that only sets `alwaysMandatory:true`
> validates but shows **no** asterisk; author the slot content too — [03 §3](03-generate-fields-from-crud.md).

> ⚠️ **Where the mandatory check actually runs decides what the user sees.** There are two implementations:
> a local pass over the live controls (`FormPlugin.validateMandatoryFieldsLocally`) and the authoritative
> backend pass (`FormSubmissionServiceImpl` STEP 2A). A CRUD submit uses the local one; a **process start
> form / process global action** goes to the backend — but its action's `onBeforeComplete` rule runs on the
> way there. So if that rule also guards the same field (`if (x == null) throw …`), the user sees the RULE's
> exception as a red banner instead of the field-level message you configured, and the `*` field is never
> highlighted. Two consequences when authoring:
> 1. keep the rule's guard — it is the server-side backstop — but write its message for a developer, and put
>    the user-facing wording in `mandatoryValidationMessages`;
> 2. if a required field's message never appears and a rule message does instead, that is this ordering, not
>    a broken `alwaysMandatory`. (Fixed in current nct-ui: the local mandatory pass now runs before the
>    before-complete rule on those two paths.)

**The three rule types this panel references, do not mix them up:** Prohibited/Mandatory selectors take a
**PREDICATE**; a rule-mode Default takes an **EXECUTION_RULE**; Validations take a **PREDICATE** (§2 — despite the
"validation" name, a `conditionalValidations` entry points at a `GroovyPredicate`, **not** a `GroovyValidationRule`).
The form-level Global/Action validators (§4.2) are the only place a `VALIDATION_RULE`/`GroovyValidationRule` is used.

---

## 2. Validations — "Create Validation from Template"

A field validates **itself** through `settings.conditionalValidations[]`: a list of
`{predicateIdentifier, severity: ERROR|WARNING, validationMessages: {locale→text}}`. Each entry points at a
**PREDICATE** rule whose contract is **predicate-true ⇒ the value is INVALID** (`BuiltinTemplates.java`). This is
**most** of the validation in a project — do it here, not in a form-level rule (§4.2), unless the message must be
*computed* at runtime.

You get such an entry two ways in the Validations section: **"Add Validation"** (a blank row — you pick/write your
own predicate + type the messages), or **"Create from Template"** — the guided path this section documents.

### 2.1 What the dialog produces — the two artifacts

`ValidationTemplateChooserPanel` shows only templates whose `supportedTypes` contains the field's `ValueType` (from
its `dataClass`; a blank `dataClass`, or a DatePicker with no `dateFormat`, refuses to open the chooser). You pick a
template, fill its parameters, enter localized messages; **Accept** then writes **two** things:

1. **A new PREDICATE rule** in `rep-objects.rules[]` — `ruleType: "PREDICATE"`, `executor: "GroovyPredicate"`
   (`PredicateCodeGenerator.java` — **NOT** a `GroovyValidationRule`). Its `rule.ruleScriptStr` is
   **`<scope preamble>` + `"\n"` + `<template body>`** (§2.2 / §2.3). `contextIdentifiers` = `[]` for a `GLOBAL`
   field, else the chosen context's identifier (singleton) — one more reason never to author a control `GLOBAL`
   on a form opened from a CRUD-table/tree action (§2.2 has the other): the generated predicate gets **no context
   attached**, so it cannot reach `context.<ctx>.<alias>` even after the body is corrected.
2. **A `ConditionalValidation` row** appended to the control's `settings.conditionalValidations[]`:
   `predicateIdentifier` = the new rule's `identifier`; `validationMessages` = a copy of the messages you typed;
   `severity` = **not set here → defaults to `ERROR`** (`ConditionalValidation.java`). To make it a WARNING you flip
   the per-row **Severity** dropdown in the Validations list afterward (`FormControlConfigsPanel`).

So a hand-authored export reproduces the template by writing **both**: one PREDICATE rule (body per §2.3) + one entry
in the control's `conditionalValidations[]`. `mrjun.py validate` ERRORs on a `conditionalValidations` predicate that
is dangling or the wrong `ruleType`.

### 2.2 The scope preamble (binds the field value to `v`)

Every generated body reads the field value through the variable **`v`**, bound by a preamble that
`PredicateCodeGenerator` prepends per the control's `scope`:

```groovy
// scope = GLOBAL (or null):
def v = attrs.get('<fieldExpression>')
// scope = CONTEXT:
def v = context.<ctxAlias>.data.getAttr('<fieldExpression>')
// scope = CRUD:
def v = context.<ctxAlias>.<crudAlias>.data.getField('<fieldExpression>', <JavaType>.class)
// + when the control has a JSON sub-path (jsonNodeExpression), one extra line:
v = (v == null) ? null : (v.at('/<jsonNodeExpression as JSON pointer>'))
```

`<ctxAlias>`/`<crudAlias>` are the **aliases** (not UUIDs) resolved from the chosen context; `<JavaType>` is the
`dataClass`'s class literal. This is the same context-read grammar as any predicate
([08 §context](08-groovy-rules-and-context.md)).

> ⛔ **Which preamble is right is decided by how the form OPENS, not only by the persisted `scope`.** A form
> opened from a `crud.table`/`crud.tree` ACTION runs in CRUD mode: every control on it is bound to that table's
> CRUD ([02](02-form-controls-reference.md) §Where the value LANDS), so only the CRUD preamble
> (`context.<ctx>.<crud>.data.getField('<field>', <Type>.class)`) sees a value there. A control left
> `GLOBAL`/`CONTEXT` on such a form gets an `attrs.get(...)`/`getAttr(...)` preamble that returns `null`. A body
> that opens `return v == null ||` then reports a field the user DID fill in as invalid, with no way for them to
> clear it; the eleven `return v != null &&` templates (§2.3) do the reverse and pass the field silently. Outside CRUD mode — a workflow user task, a `process.table`
> start/global action — the preamble block above holds literally, one line per `scope`.

### 2.3 The full template catalog (51 templates) — generated Groovy bodies

Below is what each template's `groovyBuilder` emits as the **body** (appended after the §2.2 preamble). Placeholders:
`<name>` = a param value; a **string/text/regex** param is embedded via `quote()` (wrapped in single quotes,
backslashes doubled); a **NUMBER** param is embedded **raw**; a **MULTI_VALUES** param becomes a single-quoted Groovy
list `['a', 'b', 'c']`; a **DATE** param becomes a temporal literal (§2.3 date note). **Predicate-true = INVALID
everywhere.** (The bare template-id list also appears in [02](02-form-controls-reference.md) and
[08 §validation templates](08-groovy-rules-and-context.md) — **this table is the canonical source for the bodies +
params**.)

**Cross-type** — `required` supports **all** types; the four `*List`/`*Const` support primitive-equatable types:

| id | Display | Params | Generated body |
|---|---|---|---|
| `required` | Required (not empty) | — | `return v == null \|\| (v instanceof CharSequence && v.toString().trim().isEmpty()) \|\| (v instanceof Collection && v.isEmpty()) \|\| (v instanceof Map && v.isEmpty())` |
| `equalsConst` | Must equal value | `value`:TEXT | `return v == null \|\| v.toString() != '<value>'` |
| `notEqualsConst` | Must not equal value | `value`:TEXT | `return v != null && v.toString() == '<value>'` |
| `inList` | Must be in list | `values`:MULTI_VALUES | `return v == null \|\| !['a', 'b', 'c'].contains(v.toString())` |
| `notInList` | Must NOT be in list | `values`:MULTI_VALUES | `return v != null && ['a', 'b', 'c'].contains(v.toString())` |

**String** (`String` fields):

| id | Display | Params (default) | Generated body |
|---|---|---|---|
| `strLenBetween` | Length between | `min`(1),`max`(100) | `return v == null \|\| v.toString().length() < <min> \|\| v.toString().length() > <max>` |
| `strLenMin` | Minimum length | `min`(1) | `return v == null \|\| v.toString().length() < <min>` |
| `strLenMax` | Maximum length | `max`(255) | `return v != null && v.toString().length() > <max>` |
| `strLenExact` | Exact length | `n`(10) | `return v == null \|\| v.toString().length() != <n>` |
| `strRegex` | Match regex (email/URL/UUID/…) | `pattern`:REGEX_PRESET | `return v == null \|\| !v.toString().matches('<pattern>')` |
| `strRegexNot` | Must NOT match regex | `pattern`:REGEX_PRESET | `return v != null && v.toString().matches('<pattern>')` |
| `strStartsWith` | Starts with | `prefix`:TEXT | `return v == null \|\| !v.toString().startsWith('<prefix>')` |
| `strEndsWith` | Ends with | `suffix`:TEXT | `return v == null \|\| !v.toString().endsWith('<suffix>')` |
| `strContains` | Contains substring | `needle`:TEXT | `return v == null \|\| !v.toString().contains('<needle>')` |
| `strNotContains` | Must NOT contain | `needle`:TEXT | `return v != null && v.toString().contains('<needle>')` |
| `strUppercase` | Is UPPERCASE | — | `return v == null \|\| v.toString() != v.toString().toUpperCase()` |
| `strLowercase` | Is lowercase | — | `return v == null \|\| v.toString() != v.toString().toLowerCase()` |
| `strNoWhitespace` | No whitespace | — | `return v != null && v.toString().find(/\s/) != null` |
| `strTrimmed` | No leading/trailing WS | — | `return v != null && v.toString() != v.toString().trim()` |

**Numeric** (numeric fields):

| id | Display | Params (default) | Generated body |
|---|---|---|---|
| `numBetween` | Between (inclusive) | `min`(0),`max`(100) | `return v == null \|\| (v as Number) < <min> \|\| (v as Number) > <max>` |
| `numLt` | Less than | `n`(0) | `return v == null \|\| (v as Number) >= <n>` |
| `numLeq` | Less than or equal | `n`(0) | `return v == null \|\| (v as Number) > <n>` |
| `numGt` | Greater than | `n`(0) | `return v == null \|\| (v as Number) <= <n>` |
| `numGeq` | Greater than or equal | `n`(0) | `return v == null \|\| (v as Number) < <n>` |
| `numEq` | Equal to | `n`(0) | `return v == null \|\| ((v as Number).doubleValue() != (<n> as Number).doubleValue())` |
| `numNeq` | Not equal to | `n`(0) | `return v != null && (v as Number).doubleValue() == (<n> as Number).doubleValue()` |
| `numPositive` | Positive (> 0) | — | `return v == null \|\| (v as Number) <= 0` |
| `numNegative` | Negative (< 0) | — | `return v == null \|\| (v as Number) >= 0` |
| `numNonZero` | Must not be zero | — | `return v == null \|\| (v as Number).doubleValue() == 0.0d` |
| `numMultipleOf` | Multiple of N | `n`(1) | `return v == null \|\| ((v as Number).doubleValue() % (<n> as Number).doubleValue()) != 0.0d` |
| `numDecimalPlaces` | Decimal places ≤ N (BigDecimal/Double/Float) | `n`(2) | `if (v == null) return true;`<br>`def s = v.toString();`<br>`int idx = s.indexOf('.');`<br>`return idx >= 0 && (s.length() - idx - 1) > <n>` |

**Boolean** (`Boolean` fields): `boolMustBeTrue` → `return v == null || !(v.toString() == 'true' || v == true || v == Boolean.TRUE)`;
`boolMustBeFalse` → `return v == null || !(v.toString() == 'false' || v == false || v == Boolean.FALSE)`.

**Date** (`LocalDate`/`LocalDateTime`/`Instant`; **all require the DatePicker to have a `dateFormat`**):

| id | Display | Params | Generated body |
|---|---|---|---|
| `dateBefore` | Before specific date | `when`:DATE | `return v == null \|\| !(v).isBefore(<dateLiteral(when)>)` |
| `dateAfter` | After specific date | `when`:DATE | `return v == null \|\| !(v).isAfter(<dateLiteral(when)>)` |
| `dateBetween` | Between two dates | `from`,`to`:DATE | `if (v == null) return true;`<br>`def dv = v;`<br>`def from = <dateLiteral(from)>;`<br>`def to = <dateLiteral(to)>;`<br>`return dv.isBefore(from) \|\| dv.isAfter(to)` |
| `dateEquals` | Equal to date | `when`:DATE | `return v == null \|\| !(v).equals(<dateLiteral(when)>)` |
| `dateInPast` | Must be in the past | — | `return v == null \|\| !(v).isBefore(<nowLiteral>)` |
| `dateInFuture` | Must be in the future | — | `return v == null \|\| !(v).isAfter(<nowLiteral>)` |
| `dateToday` | Must be today | — | `if (v == null) return true;`<br>`def today = java.time.LocalDate.now();`<br>`def asDate = <v coerced to LocalDate>;`<br>`return !today.equals(asDate)` |
| `dateWeekday` | Must be Mon–Fri (LocalDate/LocalDateTime) | — | `if (v == null) return true;`<br>`def dow = <v as LocalDate>.getDayOfWeek();`<br>`return dow == java.time.DayOfWeek.SATURDAY \|\| dow == java.time.DayOfWeek.SUNDAY` |
| `dateWithinDays` | Within N days of now | `days`(7) | `if (v == null) return true;`<br>`def asDate = <v as LocalDate>;`<br>`def today = java.time.LocalDate.now();`<br>`long diff = Math.abs(java.time.temporal.ChronoUnit.DAYS.between(today, asDate));`<br>`return diff > <days>` |
| `dateOlderThanDays` | Older than N days | `days`(30) | `if (v == null) return true;`<br>`def asDate = <v as LocalDate>;`<br>`def today = java.time.LocalDate.now();`<br>`long diff = java.time.temporal.ChronoUnit.DAYS.between(asDate, today);`<br>`return diff < <days>` |

> **`dateLiteral(<raw>)` / `<nowLiteral>` depend on `dataClass`:** `LocalDate` → `java.time.LocalDate.parse('<raw>')`
> / `java.time.LocalDate.now()`; `LocalDateTime` → `java.time.LocalDateTime.parse('<iso>')` / `.now()`; `Instant` →
> `java.time.LocalDateTime.parse('<iso>').atZone(java.time.ZoneId.systemDefault()).toInstant()` / `java.time.Instant.now()`.
> Concrete `dateAfter` on a `LocalDate` field with `when="2026-01-01"`:
> `return v == null || !(v).isAfter(java.time.LocalDate.parse('2026-01-01'))`.

**JSON** (`ObjectNode`/`JsonNode` fields) — `path` is dotted, turned into a JSON pointer `/a/b`:

| id | Display | Params | Generated body |
|---|---|---|---|
| `jsonHasKey` | Has key at path | `path`:TEXT | `if (v == null) return true;`<br>`def node = v.at('/<path>');`<br>`return node == null \|\| node.isMissingNode() \|\| node.isNull()` |
| `jsonMissingKey` | Must NOT have key at path | `path`:TEXT | `if (v == null) return false;`<br>`def node = v.at('/<path>');`<br>`return node != null && !node.isMissingNode() && !node.isNull()` |

**List** (`ArrayNode`/`ArrayList` fields, e.g. a List control's value):

| id | Display | Params (default) | Generated body |
|---|---|---|---|
| `listNotEmpty` | Must not be empty | — | `return v == null \|\| (v.respondsTo('size') ? v.size() == 0 : !v.iterator().hasNext())` |
| `listSizeMin` | Min size | `n`(1) | `return v == null \|\| v.size() < <n>` |
| `listSizeMax` | Max size | `n`(10) | `return v != null && v.size() > <n>` |
| `listSizeBetween` | Size between | `min`(1),`max`(10) | `return v == null \|\| v.size() < <min> \|\| v.size() > <max>` |
| `listAllUnique` | All items unique | — | `return v != null && v.size() != v.unique(false).size()` |
| `listContains` | Must contain value | `value`:TEXT | `return v == null \|\| !v.collect{ it?.toString() }.contains('<value>')` |

> ⚠️ **Null-handling asymmetry — the single most error-prone thing here.** Read each body's **first token**: a body
> that starts **`return v == null ||`** (or `if (v == null) return true`) treats **null ⇒ INVALID** — that is every
> positive constraint, **including all Date templates** and `jsonHasKey`/`numDecimalPlaces`. A body that starts
> **`return v != null &&`** (or `if (v == null) return false`) treats **null ⇒ VALID** — it *passes* an empty field.
> There are exactly **eleven** null-passing templates (the *"must NOT…"* / MAX-bound / present-value-format variants):
> `notEqualsConst`, `notInList`, `strLenMax`, `strRegexNot`, `strNotContains`, `strNoWhitespace`, `strTrimmed`,
> `numNeq`, `listSizeMax`, `listAllUnique`, `jsonMissingKey`. If a field must be **both** non-null **and** satisfy one
> of these, add a separate `required` entry — a lone `strLenMax` (or `notInList`, `strTrimmed`, …) happily accepts an
> empty field.

### 2.4 Regex presets — the `strRegex` / `strRegexNot` `REGEX_PRESET` param

The `pattern` param (`ParamType.REGEX_PRESET`, label **"Regular expression"**, required) renders as a **free-text
field _plus_ a preset dropdown**; picking a preset writes its regex into the free-text field (which is then embedded
verbatim into `.matches('…')`). There are exactly **ten** presets (`BuiltinTemplates.commonRegexPresets()`,
 — **no IPv6**), label → regex (verbatim):

| Preset label | Regex |
|---|---|
| Email | `^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$` |
| URL (http/https) | `^https?://[^\s/$.?#].[^\s]*$` |
| Alpha only (letters) | `^[A-Za-z]+$` |
| Alphanumeric (letters + digits) | `^[A-Za-z0-9]+$` |
| Numeric (digits only) | `^[0-9]+$` |
| Hex color | `^#([A-Fa-f0-9]{6}\|[A-Fa-f0-9]{3})$` |
| UUID | `^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$` |
| IPv4 | `^((25[0-5]\|2[0-4][0-9]\|[01]?[0-9][0-9]?)\.){3}(25[0-5]\|2[0-4][0-9]\|[01]?[0-9][0-9]?)$` |
| Slug (lowercase, digits, dashes) | `^[a-z0-9-]+$` |
| Phone (E.164) | `^\+?[1-9]\d{6,14}$` |

Any other pattern is allowed by typing it directly. For a by-hand export just embed the chosen regex into the
`strRegex` body (mind `quote()`'s backslash-doubling — in the persisted `ruleScriptStr` string a `\.` becomes `\\.`).

### 2.5 Severity — ERROR vs WARNING at submit

`ValidationMessageType` has exactly two values (`ValidationMessageType.java`). At submit, `FormPlugin` runs each
`conditionalValidations` predicate via `ruleExecutionService.executePredicateWithContextData` (`FormPlugin.java`);
when it returns **true** (invalid), it branches on severity:

- **ERROR** (the default) → `hasErrors[0]=true` + a red message on the control → **hard block** (`validateForm`
  returns `!hasErrors[0]`, so submit is refused).
- **WARNING** → a **yellow, acknowledgeable** panel on the control, **no** `hasErrors` flip → the user may proceed.

Use **WARNING** for advisory / soft-policy checks ("unusually large quantity — are you sure?"); **ERROR** for hard
data rules. A new template row is ERROR unless you set it otherwise.

### 2.6 Rule naming, message interpolation, locale

- **Rule name** (auto): `"{ctxAlias} · {crudAlias} · {field} · {template display} {(paramSummary)}"`
  (`RuleNamingService.java`; alias = camelCase). The `ctx·crud` prefix is deliberate — it stops two CRUDs that
  share a `fieldExpression` from colliding onto one rule. A name clash opens `RuleConflictResolvePanel`
  (Override / Save-as-next-suffix `(2)`,`(3)`… / Rename / Cancel).
- **Messages**: default template messages interpolate `{paramId}` → the param value and `{field}` →
  `settings.fieldExpression` (`BasicValidationTemplate.java`). Keys are full locale strings (`en_US`); runtime
  lookup falls back `en_US` → `en` → `en`. Empty locales auto-fill from the default-locale message on save.

### 2.7 By-hand recipe (author a conditional validation without the dialog)

Add a "quantity must be > 0" ERROR on a CRUD text field `quantity` (context alias `billing_context`, crud
`invoice_lines`, type `BigDecimal`):

1. **Add a PREDICATE rule** to `rep-objects.rules[]` (executor `GroovyPredicate`; `contextIdentifiers` = the
   context's UUID). `ruleScriptStr` = preamble + a `numGt(0)` body:
   ```groovy
   def v = context.billing_context.invoice_lines.data.getField('quantity', java.math.BigDecimal.class)
   return v == null || (v as Number) <= 0
   ```
2. **Append to the control's `settings.conditionalValidations[]`**:
   ```json
   { "predicateIdentifier": "<the-new-rule-uuid>", "severity": "ERROR",
     "validationMessages": { "en_US": "Quantity must be greater than 0", "hy_AM": "…", "ru_RU": "…" } }
   ```
   (`severity` omitted ⇒ ERROR; a **WARNING** must be spelled out.)
3. `mrjun.py validate` — it ERRORs if `predicateIdentifier` is dangling or not `ruleType=PREDICATE`.

---

## 3. Field events — dependent fields & recompute-on-change

`settings.eventComponentMappings[]` is the **only** cascade/dependency mechanism on a control (there is no
`dependsOnField`). Each entry (`EventComponentMapping`) is:

```json
{ "eventName": "change",
  "componentIdentifier": "<uniqueIdentifier of an IRefreshable node under the same form>",
  "executionRuleIdentifiers": ["<EXECUTION-rule-uuid>", "..."] }
```

**Authoring flow (Config → Events → "Add Event Mapping"):** each added row has three widgets —
1. **Event Name** — a **free-text field** (placeholder *"e.g., onChange, onUpdate"*): there is **no fixed
   dropdown** of change/blur/click/keyup. Whatever you type is passed verbatim to Wicket's
   `AjaxFormComponentUpdatingBehavior(eventName)`, so any DOM event works (`change`, `blur`, `click`, `keyup`,
   `input`, …). **In practice use `"change"`** — it is what working forms carry, and the only event a dropdown
   (the usual trigger) reliably fires.
2. **Refresh** — a **single-select** content picker → writes **one** `componentIdentifier`. To refresh **several**
   targets you **add several mappings** (one target each); there is no multi-target select on a single mapping.
3. **Execute Rules Before Refresh (optional)** — a **multi-select** of **EXECUTION** rules →
   `executionRuleIdentifiers` (run **in order**, against the *live* form context, before the refresh; each may
   mutate the context the next rule / the refreshed component reads).

**The refresh target** (`componentIdentifier`) is matched against a node's **`uniqueIdentifier`** (NOT `identifier`),
among the descendants of the same `FormPlugin` that implement `IRefreshable` (`BaseFormControl.java`). Pickable
IRefreshable nodes: **any field control**, and the layout nodes **`nct.parsis.plugin`** (a column), **`nct.html.plugin`**
(a slot — the "partner html plugin" of a field), **`nct.label.plugin`**, `nct.link.plugin`, `nct.label.link.plugin`,
`nct.image.plugin`, `dynaform.filter.submit.button.plugin`. Refreshing a **slot or column re-renders every field inside it** — the cheap,
usual way to cascade a dependent dropdown: point the trigger field's mapping at the *slot* (`gen_slot_*`) of the
dependent field, not at the dependent field control itself.

**Runtime** (`BaseFormControl.setupEventComponentMappings`; only when `formType()==FORM` — a **filter form
ignores mappings**): for each mapping it binds `AjaxFormComponentUpdatingBehavior(eventName)` on the trigger's form
component (only if both `eventName` and `componentIdentifier` are non-blank); on fire it locates the target, runs
`executeEventRules(executionRuleIdentifiers)` (`FormPlugin.java`) — **if any rule ERRORS (its `ExecuteResponse` is not success) or throws, the refresh
is aborted** (`FormPlugin.java`) — the rule's **returned value is not inspected**, so a rule that merely
`return`s `false` does NOT abort; an empty/null list is a no-op → proceed — then calls `refresh()` on the target. `mrjun.py validate`
WARNs on a `componentIdentifier` that matches no node's `uniqueIdentifier` (dead cascade).

**Dependent-dropdown recipe** (Country → City): on the **Country** dropdown add a mapping
`{eventName:"change", componentIdentifier:<uniqueIdentifier of the City field's `gen_slot_*`>, executionRuleIdentifiers:[]}`.
The City dropdown's own choices rule reads the current Country from wherever this form binds it — the row
(`context.<ctx>.<crud>.data.get()`) on a form opened from a CRUD-table/tree action, `attrs` on a workflow-task /
process start form — so re-rendering its slot re-runs its rule with the freshly-picked Country. The same wiring serves
any dependent pair — Plant → Storage location, Counterparty → Contract, Declaration type → Customs regime.
Full schema + a worked example — [02 `eventComponentMappings[]`](02-form-controls-reference.md).

---

## 4. The Form Settings panel (form-level → `FormDto`)

The Form Settings right-panel edits the `FormDto` rep-object (`rep-objects.forms[]` — schema in
[06 `FormDto`](06-form-groups-and-mapping.md)). Its author-facing sections beyond name/contexts:

### 4.1 Hidden Content Configuration

**What it is:** hide (or reveal) whole **content nodes** on the form based on a predicate — the **form-level analogue**
of a control's `prohibitedPredicateIdentifier`, but for arbitrary content (a section, a slot, a label, a whole
sub-block), driven by one predicate that can read the current row/context. Use it for "hide the *Approval* block
until the record is submitted", "show the *Rejection reason* only when status = Rejected", etc.

**Export shape** (`FormDto.hiddenConfigs[]`, each a `HiddenContentConfig`):
```json
{ "predicateIdentifier": "<PREDICATE-rule-uuid>",
  "contentIdentifiers": ["<node uniqueIdentifier>", "..."] }
```
- **`contentIdentifiers` are node `uniqueIdentifier`s** (NOT `identifier`), despite the name. The author picks them
  with a **multi-select** content picker limited to `IRefreshable` nodes rooted at the form
  (`HiddenContentConfigPanel.java`).
- **`predicateIdentifier`** is a **PREDICATE** rule (create-name suggestion `"<formName> Hidden Content Predicate"`).

**Runtime** (`FormPlugin.manageHiddenComponents`): each config's predicate runs against **live** form state
(`buildHiddenContentPredicateContextData`, — a snapshot of current field values + the loaded entity); when it
returns **true** the config's `contentIdentifiers` are added to the page attribute `contentsToHide`, and
`ContentHighlightBehavior` sets those nodes invisible (matched by `uniqueIdentifier`). So **predicate-true =
HIDDEN**. (An author-only "Show Hidden Components" toggle reveals them while editing. The panel's "…will be validated"
wording is stale — the behaviour is show/hide.)

> ⚠️ **CREATE mode needs the empty-CRUD seed.** A predicate like `context.<ctx>.<alias>.data.get().id == null`
> ("hide until saved") would throw *"No CRUD data available for CRUD: `<alias>`"* on a **create** form (no entity
> loaded) — except `buildHiddenContentPredicateContextData` calls `ensureCrudModeEntry` which seeds an
> **empty `CrudDataDto`**, so `data.get()` returns an empty record (`.id == null` ⇒ true ⇒ hidden on create;
> edit keeps the loaded row ⇒ `.id` present ⇒ visible). A predicate **exception is fail-open** (content stays
> visible) plus an `nctError` toast — so a broken rule is distinguishable from "don't hide". (Origin:
> `project_hidden_content_predicate_crud_data`.)

**Worked example** (a "Stock Transfer Form" that hides one block, see [06](06-form-groups-and-mapping.md)):
`"hiddenConfigs": [ { "predicateIdentifier": "0a09acad-…", "contentIdentifiers": ["7efad281-…"] } ]`.

### 4.2 Global Validation Rules vs Action-Based Validation Rules

These are the **form-level** validators — real `VALIDATION_RULE` / `GroovyValidationRule` rules (unlike §2, which
generates predicates). Reach for them **only** when a check is genuinely cross-field / context-dependent **and** you
want the error to land on a field (or the form) **without duplicating the same logic on every control's
`conditionalValidations`** — e.g. "the error belongs on *whichever* field is at fault, decided from several context
values". That is exactly the case a per-field validation can't express cleanly.

**The `validation.*` API** available inside a `VALIDATION_RULE` body (`ValidationResultCollector`, bound as
`validation`; [08 §validation](08-groovy-rules-and-context.md)):

| call | effect |
|---|---|
| `validation.addError(msg)` | a **form-level** (global) error — blocks submit |
| `validation.addFieldError(field, msg)` | an error **on a specific control** — blocks submit |
| `validation.addWarning(msg)` | a form-level warning — shown, not blocking |
| `validation.addFieldWarning(field, msg)` | a warning on a specific control — shown, not blocking |

> 🔑 **`field` is the control's `name`, NOT its `fieldExpression` and NOT a component id.** At submit `FormPlugin`
> routes a field message by matching `control.getSettings().getName() == field` (`FormPlugin.java`) and renders
> it on that control (the markup id is captured *after* the match, only for focus). The control `name` is the human
> label from the Mapping tab / the generated `settings.name` (e.g. `"Base Quantity"`, `"Plant"`) — **not** the column
> `baseQuantity`/`plant.id`. Target the **name**, or the error silently lands nowhere. An empty/blank `field` ⇒ the
> message is treated as **global**.

**Global Validation Rules** = `FormDto.validators[]` (a list of `VALIDATION_RULE` identifiers). On submit,
`FormPlugin` sends `validationRuleIdentifiers(form.getValidators())` to the backend
(`FormPlugin.java` → `FormSubmissionServiceImpl.executeValidations`), which runs each and aggregates the
`validation.*` messages; they always run.

**Action-Based Validation Rules** = `FormDto.actionValidators[]`, each a `FormActionValidator`
`{workflowIdentifier, workflowTaskId, actionId, validator}` — authored via cascading **Workflow → Task → Action**
dropdowns + a `VALIDATION_RULE` picker, to bind a validator to *one specific* workflow/task/action.

> ⚠️ **Prefer `validators` (global) for CRUD-form validation. `actionValidators` is authored/persisted but the
> observed submit path runs ONLY `form.getValidators()`** — a repo-wide grep finds no runtime read of
> `getActionValidators()` outside the settings panel / `FormEntity` / MCP tooling. The **working per-action**
> validation path is a different one: the **BPMN user-task action's `validationRuleIdentifiers`** on
> `UserTaskActionsDto.ActionDto` ([06 ACTION table](06-form-groups-and-mapping.md),
> [07-workflows-and-tasks.md](07-workflows-and-tasks.md)) — that CSV of VALIDATION_RULE ids is what actually gates a
> specific user-task action. Do **not** wire an `actionValidators` entry expecting it to fire at CRUD-form submit;
> use a **global `validators`** rule that itself checks `service.actionId` if you need per-action logic, or the
> user-task action's `validationRuleIdentifiers` for a workflow task.

**Export shape** (see [06 `FormDto`](06-form-groups-and-mapping.md)): `"validators": ["<rule-uuid>"]`,
`"actionValidators": [ {"workflowIdentifier":"…","workflowTaskId":"…","actionId":"…","validator":"<rule-uuid>"} ]`.
The referenced rules are `VALIDATION_RULE`/`GroovyValidationRule` objects in `rep-objects.rules[]`
([08](08-groovy-rules-and-context.md)). Both default to `[]`.

### 4.3 Allow Drafts

**What it does:** `FormDto.allowDrafts` (Boolean, `null`⇒false via `isAllowDrafts()`). When **true** *and* the form
has a persisted id, a **"Drafts"** dropdown appears in the form breadcrumbs (`FormPlugin.java`). Saving snapshots
the **entire** live form (`captureCurrentContextData()`) into a `DraftDto.data` JSON blob with a name and an expiry
(1/3/7/14/30 days), stored server-side (Feign `DraftClient` → the dynaform service `/api/drafts`, tenant-scoped).
**Drafts save even with invalid / partially-filled input** (validation errors are discarded for the snapshot).
Resuming loads the blob and `applyContextData` repopulates the form in place and re-renders.

**When the builder AI should enable it (decision guidance):** turn `allowDrafts:true` on a form when the PRD implies
the user **cannot complete it in one sitting** — long/multi-section intake, data that must be **fetched from
elsewhere first** ("the appraiser fills what they have today, adds the valuation once it arrives"), multi-day
onboarding/KYC, anything an approver may start and hand off. Leave it off (the default) for short, complete-in-one-go
forms — a Drafts button there is clutter. It is a per-form choice; a form with **no persisted id yet** never shows the
button regardless.

### 4.4 Multi Language & contexts

`multiLanguage` and the form's contexts are also on this panel; they are covered elsewhere — Multi Language gates the
per-field `localized:true` flow ([20-localization.md](20-localization.md), [02 "Localized fields"](02-form-controls-reference.md)),
contexts feed the predicates/choices ([06](06-form-groups-and-mapping.md), [08](08-groovy-rules-and-context.md)).

### 4.5 Get context data (a button, not a setting)

**Writes nothing to `FormDto`.** There is no export shape for this and nothing to look for in a `.mrjun` — it is a
tool in the settings panel, listed here because that is where an author will meet it.

**What it does:** reads the values currently in the form and shows the **context data document the form would
send**, in a popover, with **Copy** and **Trim & copy**. Trim removes null fields and the containers left empty
by removing them — which is what makes a real payload readable, and which also means **a CRUD whose fields are
all null disappears entirely**. Use plain **Copy** whenever the document is meant to SEED a process: a service
task needs the alias present, even empty, or it throws `No CRUD data available for CRUD: <alias>`.

⚠️ **It is JSON, and a Groovy argument is not JSON.** Pasting it into a rule needs `{…}` → `[…]`, `{}` → `[:]`,
and `$` → `\$` inside any value you keep — a double-quoted Groovy literal is a GString, so a pasted `US$100`
does not compile. **Keep the keys quoted**: a context identifier is a UUID and `[ 8b21…: … ]` does not compile
either. For `service.workflow.start(...)` use the editor's **Add start process** toolbar button instead — it
writes correct Groovy ([16](16-groovy-service-api.md) §2.12). Its neighbour **Add process list** does the same
for `service.workflow.list(...)`, writing a chosen process table's real filter keys ([16](16-groovy-service-api.md)
§2.13).

**Why it matters to a builder AI.** This document is the ground truth for the paths a rule writes by hand —
`context.<ctx>.<crudAlias>.data.get()`, `context.data.getAttr(...)`, and the second argument of
`service.workflow.start(...)` ([16](16-groovy-service-api.md) §2.12). Reading a real one is faster and safer than
inferring the shape from the export.

**What it is NOT.** It performs a real form submit but with form processing off: nothing is validated, nothing is
saved, no rule runs and the page does not navigate. On a workflow start form a real submit would start a process —
which is exactly why this one does not.

**Two documents, and it says which you are looking at.** With a list-item sub-form open, the parent form is not on
screen and the item is being edited in its own copy of the context; the popover then shows the ITEM's document and
labels it. Close the item to see the parent's.

**Known gap — File Upload.** Uploaded file paths never reach the context data document at all, with or without this
button, so an upload field is absent from the output. That is a platform limitation, not a fault of this view: do
not design a rule around reading an uploaded file's path out of the context data.

---

## Decision guidance — which validation mechanism?

From a PRD sentence, route to the **narrowest** mechanism that fits (top = prefer):

| PRD says… | Use | Where |
|---|---|---|
| "X is required" | `alwaysMandatory` + `mandatoryValidationMessages` (or `mandatoryPredicateIdentifier` for *conditionally* required); the visible **red `*` is slot-HTML content** ([03 §3](03-generate-fields-from-crud.md)) | control Config → Mandatory (§1); [02](02-form-controls-reference.md) |
| "X must match/​range/​length/​date-rule …" (self-contained, on one field) | a **template** → `conditionalValidations[]` (§2). Its predicate may read *other* submitted fields too — from the same place this one is bound: the row (`context.<ctx>.<alias>.data.get()`) on a form opened from a table/tree action, `attrs` on a task/start form — so simple **cross-field** checks live here | control Config → Validations |
| "warn but let them continue" | same, `severity: WARNING` (§2.5) | control Config → Validations |
| "the error must be **computed** at runtime, or land on **whichever** field is at fault from several context values" | a **Global Validation Rule** (`validators`) using `validation.addFieldError(<control name>, msg)` (§4.2) | Form Settings → Global Validation |
| "hide/show a whole block by state" | **Hidden Content Configuration** (§4.1) | Form Settings → Hidden Content |
| "when X changes, refresh/recompute Y" | a **field event** (§3) | control Config → Events |
| "let them save and finish later" | **Allow Drafts** (§4.3) | Form Settings → Allow Drafts |

There are **no** settings keys `min`/`max`/`pattern`/`maxLength`/`readonlyPredicate`/`hiddenPredicate`/`dependsOnField`
on a control (all fiction of stale concept docs — [02 Gotchas](02-form-controls-reference.md)). Their real forms are:
`min`/`max` → the `numBetween`/`numGt`/`numLt` templates; `pattern` → `strRegex`; `maxLength`/`minLength` →
`strLenMax`/`strLenMin`; read-only → `alwaysProhibited`/`prohibitedPredicateIdentifier`; hidden → **Hidden Content
Configuration** (form-level, §4.1); depends-on → **field events** (§3).

## Gotchas

- **"Create from Template" makes a `GroovyPredicate`, not a `GroovyValidationRule`.** The generated rule is
  `ruleType:PREDICATE` / `executor:"GroovyPredicate"`, referenced by `conditionalValidations[].predicateIdentifier`
  (predicate-true = INVALID). `GroovyValidationRule` is only the §4.2 form-level `validators`/`actionValidators`
  executor (which uses `validation.*`, not a boolean return). Wiring the wrong executor = the validation never fires.
- **Severity defaults to ERROR.** A template row (or a hand-authored `conditionalValidations` entry with no
  `severity`) hard-blocks submit. Spell out `"severity":"WARNING"` for advisory checks.
- **Null-handling asymmetry** (§2.3): every body that starts `return v != null && …` passes a **null** value — the
  eleven *must-NOT* / MAX-bound / format variants (`notEqualsConst`, `notInList`, `strLenMax`, `strRegexNot`,
  `strNotContains`, `strNoWhitespace`, `strTrimmed`, `numNeq`, `listSizeMax`, `listAllUnique`, `jsonMissingKey`);
  pair with `required` when the field must also be present.
- **Event Name is free-text** — there is no offered change/blur/click/keyup list; use `"change"` (what working
  forms use). **Refresh is single-target** per mapping — several targets ⇒ several mappings. `componentIdentifier` is a
  node's **`uniqueIdentifier`**, and events only fire on a **FORM** (not a filter form).
- **Hidden `contentIdentifiers` are `uniqueIdentifier`s**, and **predicate-true = HIDDEN**; a CREATE-mode predicate
  reading `…data.get()` works only because an empty `CrudDataDto` is seeded — otherwise it throws; a broken predicate
  is **fail-open** (visible) + a toast.
- **`validation.addFieldError(field, …)` targets the control `name`**, not `fieldExpression`/component id — a wrong
  `field` silently drops the error.
- **`actionValidators` don't run at CRUD-form submit** (only global `validators` do); per-action validation belongs
  on the workflow **user-task action's `validationRuleIdentifiers`** ([06](06-form-groups-and-mapping.md), [07](07-workflows-and-tasks.md)).
- **Drafts need `allowDrafts:true` AND a saved form id**; the draft blob is the **whole** context snapshot, not a diff.
- `mrjun.py validate` covers the refs here (dangling/wrong-type `conditionalValidations` predicate, prohibited/mandatory
  predicate, rule-mode default, `eventComponentMapping.componentIdentifier` → WARN) — run it before packing.

## Cross-links

- Control settings schema (`conditionalValidations`, `eventComponentMappings`, prohibited/default/mandatory, between):
  [02-form-controls-reference.md](02-form-controls-reference.md)
- Generate-fields dialog columns (Required/Prohibited/Default/Info): [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md)
- `FormDto` schema (`validators`/`actionValidators`/`hiddenConfigs`/`multiLanguage`/`allowDrafts`) + the ACTION model:
  [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md)
- Rule types, `GroovyPredicate` vs `GroovyValidationRule`, the `validation.*` surface, context-read grammar:
  [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md), [16-groovy-service-api.md](16-groovy-service-api.md)
- User-task action `validationRuleIdentifiers` (the real per-action validation): [07-workflows-and-tasks.md](07-workflows-and-tasks.md)
- Localization of validation/mandatory messages + `localized:true`: [20-localization.md](20-localization.md)
- The build order + where forms/validation/events sit in the procedure: [19-build-decision-procedure.md](19-build-decision-procedure.md) Phase 7,
  [13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md) Step 7

## ⛔ Business preconditions belong in a VALIDATION rule, never in the EXECUTION rule alone

LIVE-FOUND 2026-08-07. An EXECUTION rule that rejects a business precondition by throwing
(`throw new RuntimeException("No accounting policy defined for year 2026")`) reaches the user as

> Form submission failed: Could not execute rule(s) '18c93919-…': Failed to execute rule
> 'Issue Action Post' (18c93919-…): Failed to execute Groovy script: <your text>

— the reason is buried behind two uuids and two layers of platform wrapping, and it reads like a
crash rather than "you are missing a setting". **Every precondition a user can fix (missing
reference row, wrong status, empty table part, insufficient stock) must be checked by a
VALIDATION_RULE that reports it with `validation.addFieldError(<control name>, msg)` AND
`validation.addError(msg)`** — the field error marks the control, the global error is what
actually shows the text (a field error whose `fieldName` matches no control on the current form
is silently dropped, leaving the bare "Validation failed").

Where a validation rule can be attached:

| Trigger | Slot | Notes |
|---|---|---|
| workflow user-task action | `ActionDto.validationRuleIdentifiers` (list of rule identifiers) | the `flowable:userActions` payload — this is the one that fixes the message above |
| form (on save) | `forms[].validators` / `forms[].actionValidators` | runs for every submit — keep DRAFT-legal states out of it |
| **crud.table row/toolbar action** | **none** — `CrudTableActionDto` has no `validationRuleIdentifiers` (04 §ActionDto) | the EXECUTION rule's throw is the ONLY mechanism; keep it as the backstop and make the message self-contained |

So the rule of thumb: **duplicate the checks** — the VALIDATION rule for a clean UX wherever a slot
exists, and keep the same guards inside the EXECUTION rule as the last line of defence (a direct
crud.table action, a scheduler, or another rule calling it directly must still be unable to write a
half-posted document).
