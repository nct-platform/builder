# 30 — The automated suite, and the test-and-bugfix loop

> The automated suite is written at BUILD time, with the project and from its scenario file (the
> contract's step 7a); this document says how to write it (§6–§7) and what to do once the project is
> imported and the user asks you to test it and fix what fails (§0–§5). It is the companion to
> [28-support-mode-over-mcp.md](28-support-mode-over-mcp.md), which covers the channel (MCP, tokens,
> what has no live channel).

## 0. The order, and why it is not negotiable

```
BUILD — offline, no environment, no question asked
1  test-scenarios.md   every scenario, from the PRD                     (contract step 7)
2  test/               every scenario automated, from that file;      (contract step 7a)
                       `mrjun.py autotest check` green
TEST & BUGFIX — only when the user asks, against the live project
3  with the user's yes: import the .mrjun (§1), deploy the workflows -> queues fill, starts stop throwing
4  the owner fills test/.env; the session has the project's MCP connection
5  RUN the suite (./start.sh all), and DRIVE in a browser what it cannot see
6  triage every red: a defect of the product, of the test, or of the scenario (§5); BUGLIST
7  fix — over MCP and in the export — and re-run the same file and its neighbours
8  repeat 5-7 until the suite is green, or what remains is recorded
```

⛔ **Why the suite now comes FIRST — and why that is not the old mistake.** Earlier revisions
said: drive by hand, fix, and only then automate what you watched pass, because "a suite written
while the product is red encodes the bugs as expectations". That is true of a suite written by
WATCHING the screen — it learns `total = 0,00` from a broken page. A suite written from the
scenario file before anything ran cannot do that: every expected value comes from the PRD through
the scenarios, and the builder has never seen a screen to copy from. Where the build is wrong the
suite is red, and that red is the finding. What a blind suite DOES get wrong is its harness — a
locator, a wait, a caption — which is why §5 triages every red before anything is fixed, and why
the one forbidden move is changing an expected value to what the screen shows.

⛔ **And step 5 is still DRIVING too.** The suite proves what it asserts. It does not see a page
that lost its layout chrome, a skin that left text unreadable, the look of a printout — those are
`{manual}` scenarios, and they are driven. Offline gates prove artefacts exist and are well formed;
only opening the page proves it renders. Two of the worst defects found in the field — 41 blank
landing pages and seven work queues of empty rows — left every offline gate green.

---

## 1. Importing the archive — yours to drive, never yours to decide

**The project's own Settings page accepts the `.mrjun`**, and the browser session you drive
is already signed in there — an import needs no human hands:

```
<root>/<realm>/<client>/settings      <- import / export the project archive
```

`test/start.sh reset` drives the same page (`tools/import_project.py`), setting every switch of
the import dialog explicitly ([00](00-export-format-and-import.md), the import switches).

⛔ **But an import is never a silent step of a loop.** It REPLACES the project — content, rules,
business logic — and, with "Replace the business logic and its database" (which the reset always
sets), the project's DATA, back to the archive's dump. What the project's users entered since is
gone, and so is every live edit that was never written back to the export. So:

* **ask first, every time.** Name the project (`<root>/<realm>/<client>`), say that its data goes
  back to the archive's dump, and import only after the user's explicit yes to THAT import, in
  this session. A yes covers the import it was given for — or every reset of this test session, when
  the user says so — and never another project: a yes for a test project is not one for production;
* **prefer MCP.** A fix that has a live channel ([28](28-support-mode-over-mcp.md) §4) goes over
  MCP, with no import at all. An import is for the first landing of a build, and for what has NO
  live channel (28's honest-limits list: PDF templates, locales, assets, free enums, seed data);
* the user may always prefer to import by hand — then hand over the archive and wait.

⚠️ **An import resets things the archive does not carry:**

| resets | do this after every import |
|---|---|
| the project's **data** (with "Replace the business logic and its database") | nothing to redo — it is why the import needs the user's yes; scenarios start again from the seed rows |
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

⛔ **Never remove the `Author` group from the only author account** — and never edit the
author account's own role groups at all: the suite creates a user for every role it needs
(§2.4). Author is the role that grants roles: drop it and nobody can grant it back.

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

⚠️ **It also hides half of Project Settings.** `Layout`, `Import / Export` and `Accesses`
are gated on holding the ADMIN or NCT_AUTHOR **role**, which an author holds only while
author mode is on. With it off the settings list is `Branding · Localization ·
Integrations · Appearance · Developer`, and the missing three read exactly like a broken
build. (`Developer` is NOT in that group — it is gated on role-group MEMBERSHIP, so it
stays put whatever the toggle says.)

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

### 2.4 Creating users — and how the suite makes its people

What the platform guarantees:

* **An author sets the password of a user they create.** The Create-User dialog (First name, Last name, Email,
  Role groups) offers *Set password* to every member of a role group that carries the author role. A user
  created WITH a password gets **no invitation** and can sign in at once; one created without gets the
  invitation mail with its set-password link. (On an EXISTING account an author cannot set the password — users
  belong to the whole organization — except on a test account, below.)
* **Addresses no mail can reach are test accounts.** An address on a name RFC 2606 / 6761 reserves — `*.invalid`,
  `*.test`, `*.example`, `*.localhost`, `example.com` / `.net` / `.org` — can never receive mail. The platform
  creates an account on one only WITH a password, never queues an invitation for it, and its outbox drops every
  message to one before any provider sees it: a notification rule firing for a test user costs no bounce.
* **Deleting a user removes them from the PROJECT** (role groups and membership — the project's user quota is
  freed); the account stays in the organization. Creating the same address again re-adds that account and keeps
  its OLD password — which is why a test run never reuses an address.

How the suite uses it: **every person a scenario has is a test user the suite creates for the run** —
`helpers/accounts.py`, `as_user(...)` in a test — holding exactly the role groups the PRD gives that person, on
`zz-at-<label>-<run>-<n>@autotest.invalid`, signing in with the SAME password as the author account the run
starts with (`AUTH_PASSWORD` — it already satisfies the realm's password policy, and a person who wants to look
at what a test user saw already knows it), in a browser context of its own. The run's roster (addresses, role
groups — no passwords) is written to `test-results/test-users.json`; the users are removed when the session ends,
or kept with `KEEP_TEST_USERS=1` for a person to sign in as one and look. As many people as the scenario has: two
approvers are two labels (`as_user("Approver", label="second")`), "must NOT see" is a user without the group, an
access change mid-flow is `accounts.set_role_groups(...)`. Nothing is configured per person and nothing is
skipped for a missing account.

⛔ **The author account performs only what the PRD gives an administrator.** A business step performed by the
author proves nothing about the role it belongs to: Author sees every page and every action, and a rule-started
case grants the author role a row of its own. A test that passes as the author and fails as the clerk is exactly
the defect the suite exists to find.

When you create identities by hand in a live test, name them the same way — first name `zz-at` — so a person
scanning the project's users knows what they are, and remove them at the end.

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

| 13 | **A document's sub-grid that is blank until you save** | open a document form, press **Add line**, pick the material / roll / order line, save the LINE — and read the grid **before saving the document**. Reference columns (`material.code`, `roll.code`, `orderLine.name`) must show the code and the name at once. Blank-now-filled-after-reopen means the List control has no `onBeforeUserTaskCompleteRuleIdentifier`: the picker stored `{"id": …}` and nobody fetched the rest ([02 §7.0b](02-form-controls-reference.md)). **This is the defect class that hides from everything else in this table** — it passes `validate`, it passes `crud verify --db`, and it passes every test written against a SAVED document, because `json_agg` fills those columns on read. One delivered project had it on **12 of 12** List controls behind 400 green tests. Check the headings in the same glance: two adjacent columns titled the same mean the nested column took its label from the FK instead of the target column. |

| 14 | **A derived column that is only computed on `submit`** | the sibling of #13, one step later in the flow. Save a document WITH a line and read its register row **without sending it**: the header total, the flag, the variance must already agree with the lines. If they do not, the recompute (`recomputeTotals`, `computeLineAmounts`, a `computeX` engine method) is called from the `submit`/`post` rule only, and until the document is sent the register prints the column's DEFAULT beside the very numbers it summarises. ⛔ **Why every test missed it:** invariant tests read REGISTERS, and a register is full of seeded rows (the seeder writes derived columns itself, in Python) and already-posted rows (the engine ran). The one state nobody looks at is *saved, not sent* — and that is where the defect lives. It was found in a delivered project by a single DRAFT among sixteen posted documents: the arithmetic was right in all sixteen, the moment of running it was wrong in the one. **The fix belongs in the persist rules** (`Action Create` / `Action Update`), not in a new screen, and the list of calls should be DERIVED from the engine's own method registry so a typo stops the build instead of surfacing at a user. Put in the tail only STATUS-NEUTRAL recomputes: nothing that flips a status (`refreshSettlement` → CLOSED), nothing that belongs to an approval step (`allocateLandedCost`), nothing that writes stock movements. And do not swallow the exception — if the engine failed, the row IS inconsistent, and a silent `catch` restores exactly the defect you are closing. |

### Three ways a check lies to you — each one cost a day

**1. An observation that is identical whether the feature works or not.** "The charts are still
there after switching the theme" passes when the theme switched AND when the click missed the
control entirely — the charts were there before. "The filter returned rows for a value I took from
the grid" passes when the filter matched AND when it was silently dropped, because a dropped filter
returns the whole table. The fix is the same in both cases: **assert MOVEMENT, not survival.** The
body background must DIFFER after picking a theme; a value that matches nothing must return ZERO
rows. If you cannot name what must change, you have not written a check yet.

**2. A skip that describes the product instead of your own aim.** Three times on one project a
skip reason turned out to be false:
* *"the theme item would not click (it is in a collapsed menu)"* — there was no menu; the control
  sits in the header and the label the test searched for lives in its screen-reader `span`;
* *"no draft on the first page"* — a statement about PAGINATION, not about the data; the draft
  existed and a filter found it;
* *"no roll available for this material"* — a query showed **270** eligible rolls; the dropdown was
  empty because a cascade cannot refresh inside a line form at all.

Each one would have shipped a real defect as a documented limitation. **Before writing a skip that
blames the data, run the query that proves the data is missing.** If the query disagrees, you have
found a defect, not a limitation — and if it agrees, quote the number in the skip reason so the next
reader can check you.

Two cheap techniques that find more than clicking:

* **Sweep every page from inside the browser.** One `fetch` loop over the page aliases, parsing each
  response and reporting text nodes that match a pattern, covers 90 screens in one call — untranslated
  scripts, raw codes, English leaking into a localized UI.
* **Verify in the database, not on the screen.** After every write, read the row back. A grid can
  show a value the server never stored, and a task form can look saved when nothing was written.

**3. A test that writes must UNDO itself — and the undo has to be VERIFIED, not assumed.** A check
that reaches the saved state has to create something, and on a tenant with real records that
something is litter: the next run then judges its own leftovers, and a register full of `T1`/`1`
drafts is indistinguishable from a register full of real ones. So: create it, assert on it, delete it
by the app's own action, **and re-read the register** — the leftover set must be empty. Put the
cleanup in a `finally`, because a failed assertion has even less right to leave rows behind than a
passing one.

⛔ The undo is where the silence hides. Measured twice in one session: the row action was named
"Delete", so the cleanup pressed "Delete" in the confirmation dialog too — and that dialog's button
is "Yes". Nothing threw, the cleanup "ran", and two drafts stayed on the tenant. The assertion that
the register came back to its original set is what turned that from a discovery-in-a-week into a
failure-in-a-minute. And when you do find leftovers, remove them **through the application's own
method**, not with SQL: a soft-delete flag, a recompute and an audit row are part of what "deleted"
means here.

---

## 3. Recording defects while you drive

Write a **BUGLIST** beside the export — `work-case/BUGLIST.md`, the case notes' folder; never inside `work/`
(it would ship in the archive) and never in the library.
One row per defect, and keep it current as you fix:

```
| # | Sev | Area | Bug | Status |
| B-01 | BLOCKER | pages | ... | OPEN / FIXED / VERIFIED / WONTFIX |
```

For each defect record, in this order: **what you did, what you saw, what you expected,
the root cause once you have it, and how you proved the fix.** A buglist entry without a
reproduction is a rumour.

Also keep a **VERIFIED CORRECT** section. The things that already work are what you must
not regress while fixing the things that do not — the suite's tests for them are the ones to
re-run after every fix that touches anything they share.

---

## 4. Fixing — and re-driving

Fix over MCP, smallest change first, then **re-run the same test file** — and re-drive in the
browser whatever the suite cannot see. A green `validate` is not evidence; the re-run is.

Mirror every fix into the export (`work/`) and re-run the gate ladder:

```
validate  ->  crud verify --db  ->  pack  ->  (import — only what has no live channel, only after the user's yes, §1)  ->  re-run the suite
```

Every product defect you fix also gets a regression test named after its BUGLIST id, asserting
the exact thing that was broken (28 §8.8, family 10) — unless an existing test already failed on
it, in which case that test IS the guard.

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

## 5. ⭐ Triage — every red test is a defect of the product, the test, or the scenario

The suite exists from the build on (the contract's step 7a); nobody is asked whether to write it.
What the first run against the live project returns is therefore a mix, and the work of the
loop is telling the three apart BEFORE fixing anything:

| the red says | it is | fix |
|---|---|---|
| the project does not do what the scenario — and the PRD behind it — says | a defect of the **product** | the project (MCP + export, §4); a BUGLIST row; the red test is its regression guard |
| a locator, a wait, a caption, a page path, a fill that did not land | a defect of the **test** | the test — never its expected value |
| the scenario's arithmetic, or its reading of the PRD, is wrong | a defect of the **scenario** | `test-scenarios.md` first, with the reason written down; then the test |
| the seed rows a scenario starts from are not what the archive carries — edited by hand, consumed by an earlier run, or never imported | the **tenant drifted** — no defect of the build | with the user's yes, `./start.sh reset` (§1) and run again; never weaken the test to the data it found |

How to tell, cheapest first:

1. **Group identical failures.** Ten tests failing with the same message are one harness fault
   (an import, a fixture, a register that did not render) — never ten defects. A run of failures
   that all read a seed row differently from the archive is one drifted tenant.
2. **Reproduce the step by hand** in the browser. The product either does what the scenario says
   or it does not; a minute here saves an hour of fixing the wrong thing.
3. **Recompute the scenario's arithmetic** before calling a number wrong — with decimal arithmetic
   and the database's rounding (half away from zero), never with a calculator's float.
4. **Read the PRD sentence the scenario cites.** If the PRD demands it, the product owes it; if only
   the scenario demands it, the scenario owes a correction — say which in the BUGLIST.

⛔ **The one forbidden fix:** changing what a test expects to what the screen shows. It turns the
suite from a check of the PRD into a recording of the build's bugs, and nothing downstream can
tell the difference. A value may change only through rule 3 of the table: the scenario was wrong,
it says why, and it was corrected first.

⛔ **And green is not "nothing to report".** A scenario that passed because it is `{manual}`, or
because its test SKIPPED (no `PGDSN`, no `API_KEY`, no `--run-sends`), was not proven. `start.sh` counts the skips in its summary; the report names each one.

---

## 6. The automated suite — laid down by a command, written at build time

It lives in a `test/` folder **beside the export**, never inside it (`pack` walks the export dir;
test code must not ship in the archive). The harness is not yours to write — it is the library's,
proven on delivered projects, and one command lays it down:

```
python3 ./builder/tools/mrjun.py autotest scaffold --project ./work     # -> ./test
python3 ./builder/tools/mrjun.py autotest check    --project ./work     # the suite's offline gate
python3 ./builder/tools/mrjun.py autotest env      --project ./work     # which .env keys are set (never a value)
```

`scaffold` never overwrites what you write or fill for the project — `tests/` (with `tests/conftest.py`),
`pages/project_*.py`, `helpers/project_*.py`, `helpers/locales.py`, `README.md`, `.env.example` — or the owner's
`.env`; the rest of the harness is replaced only with `--force-infra`. So the project's own extensions go exactly
there: fixtures and markers in `tests/conftest.py` (a marker registered with
`config.addinivalue_line("markers", "<name>: <meaning>")` in `pytest_configure` — the gate reads it there), page
objects in `pages/project_<name>.py`, helpers in `helpers/project_<name>.py`.
It writes `helpers/locales.py`'s LOCALES and DEFAULT_LOCALE from the export, and creates `.env`
from `.env.example` (mode 600, values empty).

```
test/
  start.sh              THE entry point: venv, dependencies, browser, checks .env (never prints the password),
                        runs, ends with the coverage map and the count of SKIPPED tests. Modes: smoke | all |
                        reset | reset-schema | -k … ; `all --run-sends` adds the tests that send real mail
  .env.example          the keys, values EMPTY — committed
  .env                  the same keys, filled by the project's OWNER — git-ignored, mode 600, never printed
  .gitignore            .env, .venv/, test-results/ …
  README.md             how to run; the triage rule (§5); what is deliberately not automated
  requirements.txt      playwright, pytest, python-dotenv (+ psycopg for the optional database check)
  pytest.ini            --strict-markers; markers smoke auth nav i18n register form rule calc ripple workflow
                        roles prohibition report studio print api author destructive sends
  conftest.py           ONE session browser + sign-in, the module LOCALE fixture, `as_user(...)` / `accounts`
                        (the test users), the --run-destructive and --run-sends gates, the technical-error
                        trap, screenshots on failure
  helpers/  env.py      the ONLY reader of .env — CONFIG, CONFIG.url(), CONFIG.api_url(), CONFIG.require()
            accounts.py the test users: created by the author account for exactly the role groups a scenario
                        names, on @autotest.invalid, signing in with AUTH_PASSWORD in their own browsers,
                        listed in test-results/test-users.json, removed at the end (KEEP_TEST_USERS=1 keeps them)
            locales.py  LOCALES, every caption the tests use PER LOCALE — filled by you from the export
            numbers.py  parse a whole cell as a number; expected values in Decimal with database rounding;
                        assert_number compares EXACTLY (an unrounded screen value is a finding)
            db.py       read-only cross-check through PGDSN: query()/one() skip without a database (the database
                        IS the assertion); optional() returns None and warns (a second witness)
  pages/    base_page.py     waits on CONTENT, not on navigation; goto() waits for the project's chrome
                             (expect_chrome=False for a page that may refuse); has_chrome(), content_is_blank()
                             (the content area only — grids, controls, charts, text), has_500()
            driver.py        acts like a person: fills forms by their visible labels, presses row actions and
                             dialog buttons, reads grids by column caption, waits for toasts and dialogs
            login_page.py    sign-in, sign-out, the locale switch
            nav.py           the author-mode toggle and the inherited admin quick links
            register_page.py a list page: filter, grid, create, save
            queue_page.py    a work queue: task count, rows that carry data, a task's actions
            studio_page.py   a custom HTML Studio component: mounted (text= / ready=), its problems, one
                             click = one effect; a context manager, because the page is shared
            users_page.py    the users screen — create (with a password), change role groups, delete; found by
                             structure, in any language
            feedback_watch.py every message a user is shown, in every browser; the technical ones fail the test
  tools/    coverage_map.py  which scenario each test covers — and which none does
            import_project.py the reset: re-import ../project.mrjun through the project's own Settings page
  tests/    YOURS: one file per chapter of test-scenarios.md, numbered in run order; test_00_smoke.py is the
            library's sample of the conventions; tests/conftest.py for the project's fixtures and markers
```

### The `.env` — which project, and who signs in

Everything that differs between one run and another lives in ONE file, `test/.env`, and nowhere else: not in a
test, not in a page object, not in `conftest.py`, not in `start.sh`. Pointing the suite at another project — a
staging copy, a customer's tenant, a fresh import — is editing that file, never the code. `helpers/env.py` is
the only module that reads it; its keys are the ones the library's `.env.example` declares:

| key | required | meaning |
|---|---|---|
| `BASE_URL` | yes | ⛔ ALWAYS `<root>/<realm>/<client>`. The bare installation root bounces to `…/auth;jsessionid=…` and renders none of the project |
| `AUTH_USER`, `AUTH_PASSWORD` | yes | one user holding the Author role group (§2.1). Every other person a scenario has is a test user the suite creates itself (§2.4) — no other account is configured anywhere |
| `DEFAULT_LOCALE` | | the locale the suite returns to after the language tests |
| `HEADLESS`, `SLOW_MO_MS`, `DEFAULT_TIMEOUT_MS`, `GRID_TIMEOUT_MS` | | browser knobs; keep `HEADLESS=1` for every long run |
| `KEEP_TEST_USERS` | | `1` keeps the run's test users after it ends (they sign in with `AUTH_PASSWORD`; `test-results/test-users.json` lists them); default `0` removes them |
| `PGDSN` | | the read-only database cross-check (`helpers/db.py`); empty = those checks skip and say so |
| `API_KEY` | | the public-API scenarios ([32](32-public-api.md) §9); empty = they skip and say so |
| `API_BASE_URL` | | only when the API answers elsewhere than BASE_URL's installation root (a project on a domain of its own); empty = derived. Tests build every API address with `CONFIG.api_url("<slug>/…")` |

The rules around it:

* **Who fills what.** `scaffold` creates `.env` from `.env.example` with every value empty, mode 600. During a
  build nobody fills it — there is no project yet. When the user asks you to test, `BASE_URL` is yours to write
  when the folder knows the project's address (`.dokie/project.json` → `project.liveUrl`; it is an address, not
  a secret) — with `mrjun.py autotest env --base-url <it>`, which also accepts a bare origin and adds the
  realm and client. The run's knobs go the same way (`--set HEADLESS=0`). `AUTH_USER`, `AUTH_PASSWORD`, `PGDSN`
  and an `API_KEY` are written by their OWNER, into the file — `autotest env` refuses them. ⛔
  Never ask for them in the chat, never type them, never `cat` the file or print a value from it
  ([28](28-support-mode-over-mcp.md) §8.2): the test process reads it, you do not. `autotest env` tells you
  which keys are set without showing a single value.
* **Only the file counts.** The keys that say which project and who signs in are read from `.env` ONLY — a shell
  variable of the same name (another tool's `AUTH_USER`, yesterday's `BASE_URL`) is ignored, because it would
  otherwise win silently and the suite would test the wrong project as the wrong person. The knobs of one run
  (`HEADLESS`, `SLOW_MO_MS`, the timeouts, `DEFAULT_LOCALE`) may be overridden from the shell.
* **`start.sh` checks before it runs anything:** `.env` exists and `BASE_URL`, `AUTH_USER`, `AUTH_PASSWORD` are
  non-empty. It may echo `BASE_URL` and `AUTH_USER`; for the password it says only "set". `CONFIG.require()` repeats
  the check inside Python, before a browser opens — and loading `CONFIG` never fails, so wherever pytest and
  Playwright are installed `pytest --collect-only` works with no `.env` at all (a build has neither; its gate is
  `autotest check`).
* **Addresses come from `CONFIG.url()`** — `page.goto(CONFIG.url("settings"))` — and "sign-in lands inside the
  project" means the address carries `CONFIG.realm_client`. A literal host, realm or client anywhere in the suite
  is a test that silently keeps testing the old project after `.env` moved; `autotest check` flags one.
* **No secret lands in an artefact.** Sign in once per session, with tracing and video OFF (a Playwright trace
  records the text `fill` typed); `CONFIG` hides every secret from its `repr`; no fixture, log line or assertion
  message prints a password, a key or the DSN.

### ⛔ The scenario file IS the coverage map

"All the scenarios" is the promise a suite quietly breaks — eight easy files feel like finishing. So the
suite is counted, not trusted: every test cites the scenario it automates as `§N.M` in its docstring,
`tools/coverage_map.py` reads the numbered headings of `test-scenarios.md` (`## N. chapter`, `### N.M · scenario`,
`{manual: <reason>}`; chapter 0 is prose and never a scenario) and prints which scenario each test file covers
and which none does — after every run of `start.sh`, and as the gate `mrjun.py autotest check`, which also
refuses a `plan.json` row that no scenario's Covers line cites (the traceability table of chapter 0 is for the
reader and does not count) and a `plan:<id>` the plan does not have.

The grammar is strict because a scenario that does not parse would vanish from the count without a word:

* a heading meant as a chapter or a scenario but written another way — `## 1 · …`, `### Scenario 4.2`,
  `### §4.3`, `#### 4.6` — is an ERROR; so is `{prose}` outside chapter 0, a scenario whose number does not start
  with its chapter's (`### 5.2` under `## 4.`), and two headings with one number;
* `§` is reserved for scenario numbers and counted ONLY in docstrings (the test's, its class's, its module's) —
  a comment or a string does not claim a scenario. Cite a PRD section as "PRD 4.2" and a library doc as
  "doc 30 §5": a `§` right after "PRD" or "doc NN" is not read as a scenario. On a delivered project the first such map took twenty minutes and named four scenario sections
with no test at all — one of them a Must requirement the product could not perform. A map the user can read
beats a claim they cannot check, and a suite that knows its own holes is trusted where an unlabelled one is not.

---

## 7. Writing the tests blind — one pattern per scenario family

The suite is written before the project ever ran, by someone who has never seen its screens. That is its
strength (it cannot copy a bug from a screen) and its risk (every locator is a prediction). Write it so the
first run's red is mostly the PRODUCT's: locate by what you authored, wait for content, assert what must change.
Read [28](28-support-mode-over-mcp.md) §8.8 — the ways a UI assertion lies — before the first file.

| family (contract step 7) | the test |
|---|---|
| front door, navigation | `test_00_smoke.py` (§1.1, §1.2) as the library ships it; then every page of the export's own page list opens with its menu and header (`has_chrome()`) and is not blank (`content_is_blank()`); the author-mode toggle shows and hides the inherited admin links. The chrome's PRESENCE is automated; whether it LOOKS right on every skin is a `{manual}` line |
| registers (m) | open the page, wait for ROWS (`wait_for_rows`), read columns by caption — `drv.grid("<caption>", "<caption>")` picks the table by the columns it must have (never "the biggest table": next to a larger register it returns the wrong one); every filter control: a value present in the data narrows, a value present nowhere returns ZERO rows; paging moves to different rows; each row action offered exactly in the states and to the roles the scenario names — and its absence asserted where it must be absent |
| forms (n) | `driver.fill([...])` by visible label — assert its result: a field it reports `NOT FOUND` or `NO OPTION …` is a failure of the fill, never data; every mandatory field refused empty BY ITS OWN MESSAGE; every default present on open; every dropdown's options (cascade: change the parent, the child's options change); save, RE-OPEN, read every value back; with lines: the line grid before the document is saved (doc 26 §5 4a), the derived header before it is sent (4b) |
| rules in action (o) | a predicate twice — in the state where it is true (the action is offered) and where it is false (it is ABSENT), changing only the condition it reads; an execution rule by its effects: the rows it wrote (screen after re-open, and `helpers/db.py`), the numbers it moved, the case it opened — run TWICE, still one case — the access it changed; a validation rule by each message, provoked with every other mandatory field filled |
| processes (p) | ONE test per path, start to end event: start the case (form / direct / the triggering rule), and for each step open — as a test user holding exactly the role that owns it (`as_user(...)`) — that role's queue (`QueuePage`), assert the task is there with its data, act (`driver`), assert the status after it and the ripple; two people in one role (the PRD forbids the initiator to approve) are two labels; parametrize nothing that hides which path failed — one named test per path |
| calculations and dependencies (q) | the expected number computed IN the test from the scenario's inputs with the PRD's formula — `Decimal`, `round_db` — and compared with `assert_number(cell, expected, places, what=…, formula=…, inputs=…)`; then the same value from the database when `PGDSN` is set; every dependent read after the action (forward), and again after the reversal (backward); the invariants asserted after every write; a record the server numbered found by DIFFERENCE (before/after), never "the newest" |
| studio components (r) | `with StudioComponent(page, "<the root selector you authored>") as c: c.open(path, text=<a caption the PRD names>, ready=<a selector only real data produces>)` — content, not an empty wrapper (a spinner is a child element too); each control clicked for real and its result read from the component; `count_effect(...) == 1` for an action after a re-render; the empty and error states; paging across pages; each locale; `problems()` empty at the end |
| access (s) | the person who should gain or lose access OPENS the list — a test user holding exactly that role (`as_user(...)`), its groups changed mid-flow with `accounts.set_role_groups(...)` where the scenario hands access over — and the case or row is present or absent; a "must NOT see" is asserted on the list, the direct URL and the row action, not on one of them |
| actions — availability (t) | per action and per role: present where the PRD offers it, ABSENT where it does not (a user without the role, a state that makes it meaningless); per situation in which it cannot run, exactly the decided outcome — the validation's own words on the form (field-level where a field is the cause), or a direct action's worded refusal — provoked by exactly that condition; and on no path any technical error (the suite fails one by itself, `feedback_watch.py`) |
| automatic starts, schedulers ([27](27-event-driven-process-start.md)) | the trigger produced the way the PRD says — the record created or the status set that a rule reacts to; where the trigger is a scheduler, its rule run by hand from the project's rule console (author mode) as [27](27-event-driven-process-start.md) §8.3 does by hand — then run AGAIN on the same data: still exactly ONE case, and it is in the worklist of a NON-admin member of its role group |
| order, repetition, concurrency (g) | the same action twice (a double click, a re-submit, a retried request) has ONE effect; steps out of order are refused; the same record saved from two browser contexts ends as the PRD says (the second refused, or merged) — never silently overwritten |
| prohibitions (f) | the forbidden situation CREATED by the test (not hoped for in the data), the action pressed, and BOTH halves asserted: the effect did not happen (the record is unchanged) and the refusal names the reason in its own words — polled, because the message arrives late and leaves early |
| locales (k) | the same assertions per locale in `helpers/locales.py`, the file's `LOCALE` constant set explicitly; no text of one language leaking into another (letters only — a currency sign is not a language), codes in `NEVER_TRANSLATED` identical in all |
| reports, dashboards (j) | rows present; filters narrow; no raw enumeration code; each number equal to its source register or to the database — never "a chart rendered" |
| printouts, mail (i) | the action that produces the PDF is offered and the download arrives (`page.expect_download()`), with the document's number in its text where it can be read; a mail is proven by the record the platform keeps of it or by the rule that sends it — and a test that makes a REAL mail, message or outside call leave the project is `@pytest.mark.sends` (runs only with `--run-sends`); the LOOK of either is `{manual}` |
| public API (32 §9) | one call per operation the handover lists, the refusals with their codes, a write read back; SKIP — never pass — without `API_KEY` |
| data and cleanup | read-only tests start from the SEED rows the export's `project-db.dump` carries — you authored them, so their codes and values are known before the project ever runs, and `./start.sh reset` restores them. Seed rows are READ-ONLY: a test that must change one creates its own copy first. Every destructive test runs under `@pytest.mark.destructive` with its own records named `zz-at-<scenario>-…`, cleans up through the application's own action in a `finally`, and re-reads the register to prove the cleanup (§2.5, check 3). ⛔ No test depends on another — each runs alone and in any order (`-k` one test; a re-run of one file); a chain turns one red into ten |

For every test, before moving on: **what would fail if the feature were deleted?** If the answer is
"nothing", the test is decoration — the press that never submitted the form, the refusal that was never
provoked (28 §8.8). Rewrite it until deleting the feature turns it red.

### Rules the suite obeys

* **No credential in the repo.** `.env.example` ships with empty values; `.env` is git-ignored and is the only
  place the project's address and the author's credentials live. Every other person is a test user the suite
  creates for the run (§2.4) — its password generated, held in memory, never written.
* **Business steps run as the role, never as the author.** The author account creates users, switches author
  mode and performs what the PRD gives an administrator — nothing else. The author's own role groups are never
  edited (`AuthorRoleGuard.assert_safe(groups)` refuses a set without `Author`).
* **No user ever sees a technical error.** `pages/feedback_watch.py` records every message every browser of the
  session is shown; a test during which one carried an exception, a database constraint, a stack trace, a 500 or
  the platform's rule-failure wrapping fails — the action should have been hidden or explained (25 "An action that
  cannot run"). A test that provokes one on purpose says so: `@pytest.mark.technical_error_expected("<why>")`.
* **`--run-destructive`** gates everything that writes to a real tenant; **`--run-sends`** everything that sends
  something out of it (`./start.sh all` does not imply it). Default runs are read-only.
* **Wait on content.** This is a Wicket application with async grids, dialogs, menus and charts: wait for a row,
  a heading, a toast — never `wait_for_navigation`. Give grids their own, larger timeout. Re-ask an empty
  enumeration before believing it.
* **State the server keeps per user is SET, never inherited** — the locale (the file's `LOCALE`), author mode,
  the selected tab of a multi-register page.
* **Regression guards are named after the defect they caught**, with the root cause in the docstring. A test
  whose failure message explains the mechanism is worth ten that just say `assert False`.
* **A red run is triaged before anything is fixed** (§5) — and never repaired by changing an expected value to
  what the screen shows.
* **Say what is NOT automated and why** — each `{manual}` scenario with what a person checks instead; skipped
  checks (no `PGDSN`, no `API_KEY`, no `--run-sends`) named in the run's report, never counted as
  passed. A test that skips for "no data" means the project drifted from its seed rows: that is a finding about
  the TENANT (reset it, §5), never a reason to weaken the test.
