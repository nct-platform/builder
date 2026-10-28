# 35 — Semantic types, field decisions, and «data, not code»

> **Read this before Phase 2 (the schema) and again before Phase 7 (the forms)** of
> [19-build-decision-procedure.md](19-build-decision-procedure.md). Every rule below was paid for on a live delivered
> project: a settings page whose keys nobody could safely edit, a code-suggestion rule that ignored the customer's new
> category, refusals that printed `POSTED` to an Armenian reader, a translation table that was never once shown in two
> months, and a «Close» button that threw on its first real press. None of them was visible to a gate that checks shape.

**The one idea.** A column's *storage* type (`VARCHAR`, `NUMERIC`, `UUID`) says how the value is kept. Its *semantic* type
says what the value MEANS to the business — and only the semantic type decides the control, the binding, who may write
it, whether it may change, and where the list of allowed values lives. Decide the semantic type first, for every column
and every form field, and write the decision down. A builder that picks the control from the storage type ships a text box
for a key the rules select by.

---

## 1. The semantic types (decide one per column, in Phase 1b)

| # | semantic type | what tells you | where the allowed values live | control | after create |
|---|---|---|---|---|---|
| T1 | **closed enum** — a state or kind the LOGIC branches on (`status`, `movement_type`, `doc_type`) | some rule, predicate, gate or query compares it to a literal | the schema (CHECK or pg_enum) **and** a localized label table; codes are fixed by the release | dropdown (choices rule over the label table) | system-written or fixed |
| T2 | **open classifier** — a list the BUSINESS extends (categories, reasons, cost types, groups, units added later) | the customer says «we will add …», or the PRD lists examples, not a closed set | a lookup table / label vocabulary **without** a schema CHECK; validated by the app against the table | dropdown fed from the table (+ the settings screen to add rows) | editable value, codes immutable |
| T3 | **reference** to an entity (customer, material, order line) | the value is another row's id | the referenced table | FK dropdown / searchable autocomplete; `fieldExpression="ref.id"` | per lifecycle |
| T4 | **key the logic reads** — a setting key, a vocabulary name, a template alias, a role-group name | some rule reads rows BY this value | the catalogue it names (the settings rows, the vocabulary of vocabularies, the role groups) | dropdown over that catalogue | **immutable** — renaming detaches it from the logic silently |
| T5 | **series code** typed by people (`FAB-012`, `CUS-031`) | unique, with a numeric tail, people want the next one offered | the existing rows (the series are DATA) | autocomplete offering the next free code of each series in use; validation for duplicates | immutable after create |
| T6 | **document number** | generated, frozen | the numbering rule (prefix from a setting, sequence from the rows) | read-only, shows the next number before save | system-written |
| T7 | **person** (requested by, approved by, responsible) | names a human | the project's users, or a staff catalogue if the people have no accounts | user picker / autocomplete over previous values, or stamped by the system | stamped when the act happens |
| T8 | **typed scalar** — money, quantity, date, boolean, e-mail list, URL | arithmetic, comparison or format applies | the type itself | numeric / date / boolean control **with** its format check | per lifecycle |
| T9 | **free text** — names, notes, reasons | nobody computes with it | — | text / textarea | editable |

⛔ **T1 vs T2 is the decision that is made wrong most often.** A list the customer will extend MUST NOT be a schema CHECK
in a database the project role cannot alter: the settings screen then accepts a new code that every save refuses. If the
base schema already carries such a CHECK (an inherited database), the app must read the constraint and offer only what it
accepts — a business-logic method that joins the label table with `pg_get_constraintdef`, so the vocabulary opens by
itself the day the owner drops the CHECK — and the settings form must refuse a new code the database will not take, in
words. Never let a dropdown offer a value the database refuses.

⛔ **A T2 value that carries attributes** (a category's code prefix, a reason's «needs approval» flag, a cost type's
allocation method) needs those attributes as COLUMNS of its table (or derivable from the data — e.g. the prefix most
existing codes of that category carry). If the attribute sits in a rule's body, every new value is half-configured.

⛔ **A classifier with no table of its own is still a classifier.** A product group, a colour, a lender, the person in charge:
nobody computes with them, so nobody makes them a table — and then every report that groups by them splits «Սև» from «սև».
Their minimum is an **autocomplete over the values already in use** (one spelling each, the most used first; a business-logic
method `<field>InUse(term)` + a choices rule), so a new value is still typed and an old one is picked. If a rule ever selects by
the value, promote it to a real T2 vocabulary.

---

## 2. The field decision — one row per form field, BEFORE you generate the form

For every control on every form (and every filter cell), fill this row; it goes into the build notes next to the form.
Generate the form from these rows, not from the column list.

| field | column | semantic type (§1) | control plugin | binding (`fieldExpression` / `key` / `displayName` / choices rule or catalogue) | `dataClass` = storage type? | who writes it · when it is editable | default | validation |
|---|---|---|---|---|---|---|---|---|

Check the row against these, every one:

1. **Control from semantics.** T1/T2/T4 → dropdown; T3 → FK dropdown / autocomplete; T5 → autocomplete; T6 → read-only;
   a tableless classifier or a person typed by name (T2/T7) → autocomplete over the values in use;
   T8 → the typed control. A text field is right ONLY for T9 (and for a search filter over T5/T6 text).
2. **The binding resolves.** The choices rule exists, reads the catalogue that holds the values (not a copy), and ends in
   the converter the control expects (`toSelectOptions[Localized]`, `toAutoCompleteOptions`). The `key` is the stored
   column value; the `displayName` is a field the rule returns.
3. **Types agree end to end.** `dataClass` matches the DTO field type, the DTO field type matches the column, and the
   stored value matches the catalogue's key type (a code, an id, a group NAME — not a code that names a group).
4. **Who writes it.** A value the system stamps (number, approver, approval time, snapshot) is read-only on every form. A
   T4 key and a T5/T6 code are immutable after create — enforce it in a validation rule (compare with the stored row), not
   only by hiding the control.
5. **Every dropdown SEARCHES, by containment.** `searchEnabled` on the control, and the choices rule filters on `filterBy`
   — the typed text looked for INSIDE the code, the base label and every translation (`ateg` finds `material_category`, `կատեգ`
   finds «Կատեգորիա», `катег` finds «Категория»). A prefix match or a label-only match is a half search: people type the
   middle of a word, in the language they think in. With nothing typed the whole list comes back (the stored value stays
   readable). A delivered project's owner asked for exactly this on the vocabulary picker — «and everywhere it can be».
6. **The filter cell follows the field.** A register filter over a T1/T2/T4 column is the same dropdown, and its SQL is an
   exact match (`col IS NOT DISTINCT FROM COALESCE(NULLIF(:p,''), col)`), never `ILIKE '%…%'` — `doc_type` would match
   `correction_doc_type`.
7. **Per-locale.** A T1/T2 value is SHOWN by its label in the session's language — in dropdowns, in register columns, in
   refusal messages, in mails and PDFs ([20](20-localization.md)).

---

## 3. Data, not code — what never goes into a rule body

| never in a body | instead |
|---|---|
| a list of categories, prefixes, warehouse codes, role names, customer types — any value the business owns | a business-logic method that reads it (`material.codePrefixes`, `refLabel.usable`), or a setting |
| a map of a vocabulary's labels (`[DRAFT: 'Draft', POSTED: 'Posted']`) | a label helper that reads the label table in the session language, falling back to the base label, then the code |
| a raw code in a user-facing sentence (`"... (current: " + doc.status + ")"`) | the same helper: `+ LBL('doc_status', doc.status) +` |
| a role-group name for a decision the business may delegate | a setting whose VALUE names the group; the gate and the action both read it (`ROLE_OK(key, fallbackGroup)`) |
| a «who decides» check only in the action body | the same check in the button's predicate too — otherwise the button is offered to everyone and refuses on click |
| a constant read from settings AT BUILD TIME into a template | read at run time by the sending rule; if the template cannot take it (a fixed page size), it is not a setting |

**Every setting row must be read at run time, and every key a rule reads must have a row.** A setting nothing reads is a
promise the system does not keep; a key read with a fallback but never seeded runs on the fallback forever — a delivered
project mailed links to `http://localhost` for weeks that way. Keep a gate that diffs the two sets.

**A business-logic method beats a rule-side loop.** «The next code of every series», «the codes the database accepts», «the
open lines of this transfer» are SQL methods on the CRUD: one place, testable with `nct_crud_executeMethod`, reusable by
the choices rule, the default-value rule, the change event and the validation alike.

---

## 4. Helper closures — a body defines every helper it calls

Rules share small closures (`ROWS`, `NUM`, `SETTING`, `TOL`, `CALL`, `MSG`, `LBL`, `ROLE_OK`). Groovy COMPILES a call to a
closure the body never defines and throws `MissingMethodException` only when that line runs — the compiler gate stays
green, the button renders, and the first real press fails. Two rules:

* **A generator includes helpers by USE, not by hand.** Before it writes a body, it scans for `NAME(` of every known
  helper, and prepends the missing ones with their dependencies — at the start of the top-level statement that holds the
  first use (inside a closure the helper would be local to it; inside a multi-line call it would split the call).
* **A helper declares its own dependencies.** A block that silently relies on another helper (a tolerance loop that calls
  `ROWS(...)`) is the one that ships broken: make it self-contained, or list the dependency.

`mrjun validate` reports a call to a helper that some other rule defines and this one does not (§6).

---

## 4a. Five defects that every gate passes — check them by hand on every project

All four shipped on a delivered project with green compile, import and coverage gates; each was found only by reading a
screen or running a body.

* **The business day is the customer's.** The database and the rule runtime run in UTC, so `CURRENT_DATE`,
  `LocalDate.now()` and `to_char(now(),'YYYY')` are *yesterday* for a customer east of Greenwich until their local
  midnight passes in UTC (Yerevan: 00:00–04:00 every night; a document numbered on 1 January at 01:00 got last year's
  number). Decide the business time zone in Phase 1, define ONE expression for «today» per language
  (`CAST(now() AT TIME ZONE '<tz>' AS date)`, `LocalDate.now(ZoneId.of('<tz>'))`) and route every «today» through it:
  default dates of a document, the year inside a document number, report ages, overdue flags, scheduler cutoffs, lot and
  batch numbers, the «printed on» line of a PDF. Gate: no rule body or SQL method may contain the server-clock forms.
* **A yes/no column is a flag, not text.** Rendered as a text field it prints `true`/`false` in every language. On a form a
  flag is a read-only choice over a yes/no vocabulary (or a checkbox where the user sets it); in every grid — registers,
  document lines, reports — a flag column carries `trueIcon`/`falseIcon`. Decide it in the field row (§2) like any other
  coded value.
* **Markup inside a Groovy string literal.** A mail or PDF rule that builds HTML in a single-quoted literal and embeds a
  quoted CSS value (`font-family:'Helvetica Neue'`) closes the literal early; Groovy then reads the rest as a command chain
  — it COMPILES, and throws `MissingPropertyException` the first time the line runs. Escape text for the literal it goes
  into, at the one place a generator substitutes it. Gate: a string literal followed by a bare word with no operator
  between them is never intended.
* **One reference, one spelling of its aliases.** Postgres folds an unquoted alias to lower case (`expenseCategory__name` →
  `expensecategory__name`) and keeps a quoted one (`"expenseCategory__kind"`). Mix the two for one camelCase reference and the
  platform builds TWO nested objects; the DTO field binds to one, and every column over the other's leaves is blank (a delivered
  project's expense register showed no expense type for a week). Quote all of a reference's aliases or none.
* **A derived value has a WHEN.** A column the system computes (net quantity after returns, a line amount, a total) must be
  computed on SAVE as well as on posting — and the seed data hides the gap, because the seeder writes derived columns
  itself. Every derived column needs a test on a row created through the UI, read back before submission.

## 5. Translations of DATA — the shape the platform reads

A row's localized jsonb is `{"<dtoField>": {"<locale>": "<text>"}}` — field first, then locale; the key is the DTO
(camelCase) field name ([20](20-localization.md)). A flat `{"en_US": "...", "ru_RU": "..."}` is accepted by the database,
shown by nothing, and reported by nobody: every value stays in the authoring language in every session. Rows created
through the platform's own forms are written correctly, so a project ends up half-translated — the seeded half silent.

A register column over a T1 value renders the enum snapshot's single `displayName` in every language: localize it through
the label twin (join the label table in `findAll`, publish its translation in the row's `localize` object, point the
column at the twin — [20](20-localization.md) §L4).

---

## 6. What `mrjun validate` checks for this doc

| check | level | catches |
|---|---|---|
| `_check_text_control_on_coded_column` | ERROR | a text/textarea control bound to a column that has a CHECK allowed-value set or a foreign key — a coded value typed by hand |
| `_check_localize_flat_shape` | ERROR | a seeded localized jsonb whose top-level keys are locales — the translation is never shown |
| `_check_rule_label_copy` | WARN | a map literal in a rule whose keys are values of one CHECK set and whose values read as labels — a second copy of the vocabulary |
| `_check_helper_closure_undefined` | ERROR | `NAME(...)` called where another rule defines `def NAME = {` and this one does not — throws on the first run |
| `_check_rule_lists_business_codes` | WARN | a rule that quotes two or more codes seeded in a catalogue table (`*_code` columns) — business data in code |
| `_check_dropdown_not_searchable` | WARN | an editable dropdown whose control lacks `searchEnabled`, or whose choices rule never reads `filterBy` — people type the middle of a word (§2 rule 5) |
| `_check_case_variant_values` | WARN | an editable text control over a column whose rows spell one value two ways («Սև» / «սև») — an open classifier (T2/T7) typed by hand; make it an autocomplete over the values in use |

They are necessary, not sufficient: the field decision table (§2) is the design; these only catch its most expensive
omissions after the fact.
