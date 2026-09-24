# 30 — The live test, the bug-fix loop, and the autotest project

> This document is the ORDER OF WORK once a project is imported into a running
> environment. It is the companion to [28-support-mode-over-mcp.md](28-support-mode-over-mcp.md),
> which covers the channel (MCP, tokens, what has no live channel); this one covers
> what you actually DO, in which order, and what you must ask the user.

## 0. The order, and why it is not negotiable

```
1  import the .mrjun            -> the project exists in the environment
2  deploy the workflows          -> service.workflow.start stops throwing
3  DRIVE every scenario in Chrome -> observe, do not assume
4  record every defect in a BUGLIST
5  fix over MCP, re-drive the SAME scenario after each fix
6  repeat 3-5 until the scenario file passes end to end
7  ONLY THEN: ask the user whether they want an autotest project
8  if yes: write it, from the scenarios that are now GREEN
```

⛔ **Step 7 comes after step 6, never before.** An autotest written while the product
is still red encodes the bugs as expectations, or lands half-red and teaches everyone
to ignore it. The suite's job is to FREEZE a state you have already proved good — not
to discover the state. If you catch yourself scaffolding tests while scenarios are
still failing, stop and go back to step 5.

⛔ **And step 3 is DRIVING, not reading the export.** Offline gates prove artefacts
exist and are well formed. Only opening the page proves it renders. Two of the worst
defects found in the field — 41 blank landing pages and seven work queues of empty
rows — left every offline gate green.

---

## 1. Importing the archive — you can do this yourself

⛔ **Correction to the old guidance.** Earlier revisions said the re-import is "a
channel the human drives". That is wrong whenever you have a browser: **the project's
own Settings page accepts the `.mrjun`**, and you are already signed in there.

```
<root>/<realm>/<client>/settings      <- import / export the project archive
```

So the loop is fully yours: edit the export -> `validate` -> `pack` -> import at
`/settings` in the browser you drive -> re-drive the scenario. Ask the user to do it
only if the page refuses you, or if the environment is one they asked to change by hand.

⚠️ **A re-import resets things the archive does not carry:**

| resets | do this after every import |
|---|---|
| workflow **deployment** (all come back `deployed: false`) | re-deploy all of them; `service.workflow.start` throws `workflow_is_not_deployed` otherwise |
| live-only edits you made over MCP but never wrote back to the export | land every fix in the EXPORT too, or the import silently reverts it |
| process instances tied to replaced rows | re-open the cases the scenarios need |

The rule that follows: **fix the export, not just the environment.** An MCP write that
is not mirrored into `work/` survives exactly until the next import.

---

## 2. The author user, author mode, and the admin drawer

### 2.1 Ask for an AUTHOR user first

Author is the only role group that can create roles and users. With it you build every
other identity the scenarios need; without it you are stuck one step in. ⛔ You never
type or ask for a password in the chat — the user signs in themselves in the window you
drive ([28](28-support-mode-over-mcp.md) §8.2).

⛔ **Never remove the `Author` group from the only author account**, not even
temporarily while testing personas. It is the role that grants roles: drop it and
nobody can grant it back.

### 2.2 Author mode — the toggle that hides half the nav

**Every project inherits the admin quick links from `initialtemplates/empty.mrjun`.**
They sit in the nav group the baseline calls `Pages` (projects often rename it —
"КОНСТРУКТОР", "Designer", …) and they are visible only when the signed-in user holds
Author **and author mode is ON**.

The toggle lives in the **«Site» header menu**, and ⚠️ its label states the ACTION, not
the current state:

| label shown | meaning |
|---|---|
| "I am not an author" / «Я не являюсь автором.» | author mode is currently **ON** — clicking turns it OFF |
| "I'm author" / «Я автор» | author mode is currently **OFF** — clicking turns it ON |

The same menu holds **"Edit site"** — the authoring page builder (drag-and-drop layout
editing). That is author tooling. It is not an end-user scenario, it is not part of the
acceptance run, and an autotest should not drive it. Knowing it exists is enough.

⚠️ Author mode is **sticky per user**. Before asserting "a clerk does not see the admin
console", switch it OFF explicitly — otherwise the previous step leaks into this one and
you report a permissions failure that is really a leftover toggle.

### 2.3 The inherited admin quick links — the full list

Relative to `<root>/<realm>/<client>`:

| path | what it is |
|---|---|
| `rules` | Groovy rules |
| `contexts` | contexts (CRUD groupings) |
| `form` | form groups |
| `workflows` | BPMN editor + **Deploy** |
| `processes` | running process instances |
| `users` | user management |
| `roles` | role groups |
| `database` | schemas, tables, sources |
| `bl` | Business Logic — dynamic CRUDs and their queries |
| `audit-logs` | platform audit |
| `mail-templates` | mail templates |
| `pdf-templates` | PDF templates |
| `schedulers` | schedulers |
| `settings` | project settings — **and where a `.mrjun` is imported/exported** |

Outside that group but always present: `profile` (my profile — and the locale switch),
and the project root as Home.

⚠️ `sources` and `queries` have no quick link of their own; they live inside
`database` and `bl`.

### 2.4 Creating users — and the limit that shapes every permission test

The Create-User form carries **First name / Last name / Email / Roles groups** and
**no password field**. The platform provisions the account; the person sets their own
secret out of band.

Consequence, and it is a hard one: **an automated test cannot sign in as a user it just
created.** So persona testing does not mean "log in as the Operator". It means
re-assigning role groups on an account you can already authenticate as — keeping
`Author` at all times — and asserting what the nav and the row actions offer.

Name every identity you create so a human scanning the project later knows what it is:
`zz-test-<role>`. Keep a list and hand it over at the end.

---

## 2.5 ⭐ What to actually look for — the defect classes a walkthrough misses

Driving happy paths finds blank pages and broken saves. It does **not** find these, and every one of
them shipped in a delivered project that had already been walked through in all three languages:

| # | Class | How to see it in one pass |
|---|---|---|
| 1 | **Write buttons with no role predicate** | strip your own user down to a read-only role group (keep `Author` — it is the only group that can hand roles back) and reload a register. Create/Edit must be **absent**, not present-and-refusing. |
| 2 | **Persist rules with no role guard** | grep the export: a `<alias> Persist Create/Update/Delete` with no `hasAnyRoleGroup` is writable by anyone who reaches the form. Master data is where it is forgotten. |
| 3 | **Monolingual rule messages** | happy paths never show them. Force a refusal — edit a closed record, save without a right, post a draft twice — and read the toast in each language. |
| 4 | **Raw enum codes in grids** | scan every register for a cell matching `^[A-Z][A-Z0-9_]+$`. One fetch loop over every page beats clicking. |
| 5 | **Reports** | they have no `localize` of their own, so they print the base column. Open every report in the NON-default locale. |
| 6 | **Documents with no number** | open a Create form: if the business key is an empty mandatory field, nothing generates it. |
| 7 | **Task forms** | complete one task, then look in the DATABASE for the record the form was editing. A status that changed is not evidence the document was saved. |
| 8 | **Form layout** | open every form group at full window width. A line form in particular ships with no columns at all ([03](03-generate-fields-from-crud.md)). |

| 9 | **A value computed and never used** | grep each rule for a local that appears exactly once — at its own `def`. A half-written guard compiles, renders and passes every offline gate: the value is computed, then the comparison uses the wrong operand, or no operand at all. One delivery carried three of these at once, each one a limit that silently never applied. |
| 10 | **A guard whose input nobody writes** | the mirror image: a condition reads a column that no rule ever sets, so it is NULL everywhere and the branch is dead. Take every field a guard READS and grep the rules and crud methods for a WRITER of it; a read with no writer is a guard that has never fired. |
| 11 | **A template nobody calls** | mail and PDF templates ride in the export and look finished in the admin list, because nothing there says whether any rule invokes them. Grep the rules for each template `alias`. Delivered projects have shipped with the majority of both kinds unreferenced — every notification silent, every printout unobtainable. |
| 12 | **A uuid where a person must read or type** | scan register columns and form fields for a `fieldExpression` ending in `Id`, and filter-bar fields for a `filterKey` of the same shape. Each one is a box that asks a human for a uuid, or a column that prints one. The fix is a join in the crud SELECT plus a dropdown control — not a wider column. |

Two cheap techniques that find more than clicking:

* **Sweep every page from inside the browser.** One `fetch` loop over the page aliases, parsing each
  response and reporting text nodes that match a pattern, covers 90 screens in one call — untranslated
  scripts, raw codes, English leaking into a localized UI.
* **Verify in the database, not on the screen.** After every write, read the row back. A grid can
  show a value the server never stored, and a task form can look saved when nothing was written.

---

## 3. Recording defects while you drive

Write a **BUGLIST** beside the export (`<project>-case/BUGLIST.md`), not in the library.
One row per defect, and keep it current as you fix:

```
| # | Sev | Area | Bug | Status |
| B-01 | BLOCKER | pages | ... | OPEN / FIXED / VERIFIED / WONTFIX |
```

For each defect record, in this order: **what you did, what you saw, what you expected,
the root cause once you have it, and how you proved the fix.** A buglist entry without a
reproduction is a rumour.

Also keep a **VERIFIED CORRECT** section. The things that already work are what you must
not regress while fixing the things that do not — and they become the first assertions
of the autotest suite.

---

## 4. Fixing — and re-driving

Fix over MCP, smallest change first, then **re-drive the same scenario in the browser**.
A green `validate` is not evidence; the re-drive is.

Mirror every fix into the export (`work/`) and re-run the gate ladder:

```
validate  ->  crud verify --db  ->  pack  ->  import at /settings  ->  re-drive
```

When a fix is a class of defect rather than one instance — the same malformed call in
seven rules, the same missing plugin on 41 pages — fix them all, then add a
`validate` check so the class cannot come back. Added this way so far:

* `_check_workflow_start_document_shape`, `_check_form_group_landing_plugin`,
  `_check_rule_context_binding` — blank queues, blank landing pages, null contexts;
* `_check_persist_rule_role_guard`, `_check_write_action_predicate` — the authorisation pair;
* `_check_rule_strings_multilingual`, `_check_enum_column_shows_code` — the two localisation holes
  a walkthrough cannot see;
* `_check_business_key_is_assigned` — a document number nobody generates;
* `_check_crud_method_is_called`, `_check_choices_display_is_identifying` — written-but-never-wired,
  and pickers full of uuids.

Prove each new check against the **pre-fix** export before you trust it: it must fire there and be
silent on the fixed one. A check that reports nothing on the build it was written for is not a check.

---

## 5. ⭐ Ask before you automate

Once — and only once — the scenario file passes end to end, **ask the user**:

> The scenarios pass end to end. Do you want me to write an automated regression
> project (Python + Playwright) that freezes this state, so the next change re-proves
> it in minutes instead of an afternoon?

If they decline, stop; the buglist and the case notes are the deliverable.
If they accept, build it as described below.

---

## 6. The autotest project

Create it as a `test/` folder **beside the export**, never inside it (`pack` walks the
export dir; test code must not ship in the archive).

```
test/
  .env.example          BASE_URL + ONE author credential (.env is git-ignored)
  .gitignore
  README.md             how to run; what is deliberately NOT covered
  requirements.txt      pytest, pytest-playwright, playwright, python-dotenv
  pytest.ini            markers: smoke auth i18n nav register calc workflow roles
                                 prohibition dashboard author destructive
  conftest.py           session browser+login, locale fixture, role-group fixture,
                        --run-destructive gate, screenshot-on-failure
  helpers/  env.py      config from .env; never a literal credential
            locales.py  the locale triples every user-visible assertion goes through
  pages/    base_page.py    waits on CONTENT, not navigation; `content_is_blank()`
            login_page.py   login/logout/locale; defensive field selectors
            nav.py          author-mode toggle + the inherited admin quick links
            register_page.py filter, grid, row actions, modal
            queue_page.py   work queue: task count, "rows carry data"
            users_page.py   user CRUD + AuthorRoleGuard
  tests/    one file per scenario section, numbered in run order
```

### ⛔ First the coverage map, then the tests

The table below is the FLOOR, not the definition of done. What "all the scenarios" means —
the map from every numbered section of the scenario file to the test file that covers it, the
ten families the map must account for, and the runner line that prints the holes — is in
[28](28-support-mode-over-mcp.md) §8.8. Write the map BEFORE the first test: on a delivered
project it took twenty minutes and found four sections with no test at all, one of which was
a Must requirement the product could not perform.

### What the suite must contain, at minimum

| area | assertions |
|---|---|
| auth | login lands INSIDE `<realm>/<client>`; session survives navigation; logout then login again; author-mode toggle shows/hides the admin drawer; every inherited admin link resolves |
| nav | front door is not blank; every business page renders content (not just chrome) |
| i18n | nav switches per locale; joined entity names are translated; **no authoring-language leak** in the other locales; codes identical in all locales |
| registers | rows load; a filter narrows the grid; row actions are status-aware |
| calculations | every PRD formula, on fixed demo rows, with the exact expected numbers |
| workflows | each queue renders; **queue rows carry data**; a task action opens a populated form (not blank, not 500); pressing start twice opens ONE case |
| roles | role groups exist; create user + assign groups; persona cannot see what it must not |
| prohibitions | each guard refuses AND names the reason; a discarded write must not report success |
| dashboards | charts draw; KPI tiles resolve; filter labels localized; theme switch restyles |

### Rules the suite obeys

* **No credential in the repo.** `.env.example` ships empty; `.env` is git-ignored.
  One author user; every other identity is built through the app.
* **`AuthorRoleGuard`** — refuse any role set that drops `Author` from the signed-in
  account, and always restore the original set in a finaliser, including on failure.
* **`--run-destructive`** gates everything that writes to a real tenant. Default runs
  are read-only.
* **Wait on content.** This is a Wicket app with async grids and charts: wait for a row,
  a header, a toast — never `wait_for_navigation`. Give grids their own larger timeout.
* **Regression guards are named after the defect they caught**, with the root cause in
  the docstring. A test whose failure message explains the mechanism is worth ten that
  just say `assert False`.
* **A red run is a suspicion about the TEST first.** The first honest run of a new suite
  costs a debugging session, and most of what it reports is the suite's own fault — the
  seven ways a UI assertion lies are enumerated in [28](28-support-mode-over-mcp.md) §8.8,
  including the two that look most like product defects: a numeric field that silently
  discards a value it cannot parse, and a refusal message that is gone by the time you read
  the page. Reproduce the step BY HAND before filing anything.
* **Say what is NOT covered and why** in the README — created users cannot sign in (no
  password field), "Edit site" is author tooling, schedulers stay off by design.
