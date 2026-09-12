# Getting started

**Read this first.** It is the only file here written for a person; everything else is written for the
AI that will do the building. Fifteen minutes now saves a day later.

---

## What this is

A reference library that lets an AI assemble a whole platform project — pages, forms, tables, database,
Groovy rules, workflows, mail and PDF templates — **directly as a `.mrjun` export file, with no browser**.
You then import that file into a running Dokie/NCT project and get a working system.

```
PRD  →  Claude Code + this library  →  project.mrjun + test-scenarios.md   ← the AI stops here
                                    →  YOU import  →  drive it  →  fix  →  re-import

              with an MCP token:    →  the AI imports too  →  YOU still drive it
```

**By default the AI hands you two files and stops.** It has no access to your platform, does not ask for one, and
never imports anything — so what you get is an export whose FILES are gated four ways, plus a `test-scenarios.md`
telling you what to click. Importing and driving it is your half, and it is where most of the remaining
quality lives — see §7.

**Optionally, you can let it do the import.** Paste an **MCP token** for the target project on the `MCP:` line of
`prmpt.txt` (§1, §4) and the AI imports the finished export itself — snapshot first, push, all three import flags
stated, then the per-object failure report — instead of handing you a file to upload (§6). Nothing else changes:
it builds offline exactly as before, passes the same four gates *before* the archive leaves the folder, writes the
same `test-scenarios.md`, and still never opens a browser. **An import is not a run**, so §7 stays yours either
way.

---

## 1. Prerequisites

| | Why |
|---|---|
| **curl + tar** | to download this library (both are standard) |
| **python3 ≥ 3.9** | `tools/mrjun.py` is stdlib-only — there is nothing to `pip install` |
| **Claude Code** (or an equivalent agent that can read files and run commands) | it does the building |
| **A Dokie/NCT project you can import into**, `type == REPORT` | ⛔ YOURS to provide. Create it from the **Empty project** template; any other type is worse than a no-op — the import skips the whole rep-objects block and the database, **and still replaces every page and every branch**, leaving screens with no queries, rules or forms behind them |
| *optional:* **an MCP token** for that project | lets the AI do the import for you (§6). ⛔ Not self-service: it is minted from an **admin/author** browser session **inside the target project** — Settings → Developer → MCP tokens — and it carries the realm and the client in its own signed claims, which is why you never hand over a URL or a login |
| **A way to read that project's logs** (or at least import errors) | the one diagnostic for the silent-failure class in §8 — again, yours to read |
| **A PRD** | you write it; see §3 |
| *optional but wanted:* `psql` on PATH, docker | for `crud verify --db`, the only gate that actually executes your SQL |

---

## 2. Folder layout

Everything lives in your project folder. The library is downloaded into `./builder` **as plain files** —
no `.git`, so it never becomes a repository inside your repository:

```bash
mkdir myproject && cd myproject
curl -fsSL https://github.com/nct-platform/builder/archive/refs/heads/main.tar.gz -o builder.tgz \
  && tar xzf builder.tgz && rm -rf ./builder && mv ./builder-main ./builder && rm -f builder.tgz
cp builder/prmpt.txt .
```

```
myproject/
├── builder/            ← the library (READ-ONLY; re-downloadable in one command)
├── prd/                ← your PRD
├── prmpt.txt           ← the run prompt, <ANGLE-BRACKET> lines filled in
├── work/               ← the unpacked export (the AI creates it)
├── work-case/          ← case notes (the AI creates it)
├── build-plan/         ← plan.json, the coverage ledger (the AI creates it)
├── project.mrjun       ← THE OUTPUT
└── test-scenarios.md   ← ships with it: what to click and what should happen (§7)
```

If `myproject/` is inside a git repo, add `/builder/` to that repo's `.gitignore`. Re-run the same `curl` command any time to refresh the library — it downloads to a file first, so a
failed download can never delete the copy you already have. Individual files are also readable directly, e.g.
`https://raw.githubusercontent.com/nct-platform/builder/main/system_prompt.txt`.

⛔ **This library is domain-neutral and must stay that way.** Nothing about your project goes in it —
`mrjun.py pack` only ever walks `./work`, so `./builder` and your notes can never leak into the `.mrjun`.

---

## 3. Write the PRD

There is no template — a markdown file or a folder of files, any language. What matters is that the
following can be read out of it **without guessing**:

- **Entities** — in the customer's words, not as database tables
- **Actors** — who works in the system, who may do what
- **Lifecycle** — for every entity: which states exist, **who** moves it between them, what is forbidden in each,
  and how a locking state is unlocked again
- **Processes** — every multi-step procedure
- **The trigger of every process** — ⛔ exactly one of `FORM` (a person presses it) / `SCHEDULER` (a clock) /
  `CRUD METHOD` (a record appears) / `SERVICE TASK` (another process). *"A rule starts it"* is not an answer —
  a rule is code something has to invoke; name the invoker
- **Reports / dashboards**, **notifications and printouts**, **role groups**
- **Locales** — and which one is the default
- **Branding** — the customer name and a logo file, for the mail and PDF templates

**Avoid:** one screen per table (that is a defect, not a project); fields nobody ever reads; sentences whose
actor is "the system" with no schedule and no condition.

> ⚠️ **Give the AI text, not a PDF.** The build makes several passes over the PRD looking for entities,
> triggers and states; a PDF that renders as images loses tables and requirement numbering, and — because
> `coverage` compares the build against the **plan**, and the plan is written from whatever was read — anything
> lost silently never enters the gate. Convert to markdown first.
>
> ⚠️ **If your PRD defers the physical model to an annex** ("types, keys and constraints are in the solution
> design"), hand over the annex too, or every column type and every enum literal will be invented.

---

## 4. Run it

From inside `myproject/`, put the path to your PRD on the `PRD:` line of `prmpt.txt` and paste the whole file
as your first message. That is the only line you must fill in — the prompt is four coordinates and a sentence,
plus an optional fifth line, `MCP:`, which you either paste a token onto or delete.

The first thing the AI does is read the **operating contract** at the `CONTRACT:` URL. The contract tells it to
download this library into `./builder` itself, so §2 above is optional for you: do it if you want the docs on
disk to read, skip it if you don't.

**It will then ask you three things about your business — and exactly one about your environment. Answer
precisely; a wrong answer to the first three re-touches every entity:**

| | |
|---|---|
| **Locales** | list them all **and name the default**. If it is one language, say so explicitly — that switches off per-locale fields everywhere |
| **Branding** | customer name + the logo file |
| **Scope** | which modules are in this pass, which are not |
| **Import for you?** | yes plus an MCP token, or no and it stays fully offline. This is the ONLY environment question it may ask — see below |

It will also ask before deleting anything, and it will ask who opens a case when your PRD does not say.

**Then, once — before it writes a single byte — it comes back with two lists.** This is the round where you
actually steer the build, so read it properly; everything after it is construction.

| | what it is | how you answer |
|---|---|---|
| **List A — gaps** | places your PRD is silent or contradicts itself: a status named in one clause and missing from the state list, an approval with no rejection path, a report whose data nothing records. Each item quotes your own clause, says what is open, proposes one concrete option, and **takes a position — recommends it or not, with the reason** | you decide. An item nobody answers ships as a written assumption in the hand-over, never as a silent decision |
| **List B — offers** | things your PRD never asked for, because nobody writing it knew the platform makes them nearly free: an audit trail, a worklist page, an overdue clock, a PDF of a document you only described on screen. Each box says what it is in business words, what it buys, roughly what it costs, and whether it is recommended | **checkboxes — tick what you want.** Unticked is not built, and is recorded as "offered and declined" so the next person knows it was your call |

Two things this round is deliberately not. It never offers to *skip* something your PRD asks for — everything
in the PRD is mandatory and is not a checkbox. And it is about your business, never about environments: no
URLs, no realms, no logins.

**One environment question, asked once, and no others.** It may ask whether to import the finished project for
you and, if so, for an MCP token — that is the whole list. No project URL, no realm, no client, no login, no
localhost port, and never "where are your logs": the token carries the realm and the client in its own signed
claims, so it *replaces* those questions instead of adding to them, and *"no token, stay offline"* is a complete
answer that changes nothing about how the project is built. Being asked anything **else** about an environment —
or being asked where to test after you declined — is a sign of an out-of-date CONTRACT, not a question worth
answering. Point it at the current `system_prompt.txt`, and check the `CONTRACT-VERSION:` line it prints as the
first line of its first reply: connected mode is version **2**.

---

## 5. The gates, before you import

```bash
python3 ./builder/tools/mrjun.py validate  --project ./work
python3 ./builder/tools/mrjun.py coverage  --project ./work --plan build-plan/plan.json
python3 ./builder/tools/mrjun.py crud verify --db "host=… dbname=… user=… password=…" --project ./work
```

- `validate` → **0 errors** (warnings can be legitimate). Compare against
  [`initialtemplates/empty-validate.txt`](initialtemplates/empty-validate.txt): the baseline already ships
  a fixed set of warnings and 1 error (the count is in that file — do not memorise it here; it moves whenever the
  baseline is replaced), so **diff against that file rather than chasing a zero** — what matters is a *new* line.
  With a workflow in the project it is not "0 errors" but "0 errors **and** 0 process-context findings".
- `coverage` → **PASS**. This is the gate that catches *"shipped with half the forms and no workflows"* — but only
  if the plan was written from the PRD. See the three caveats in [23 §4](23-distribution-and-known-gaps.md).
- `crud verify --db` executes every SQL method against a real server. It needs the `psql` **binary**;
  [26 §3a](26-orchestration-and-testing.md) ships the complete throwaway-Postgres recipe. Read the output and
  triage every FAIL — do not wire it into an unattended gate.

> ⛔ **A green `validate` does not mean the project works.** It proves the files are *shaped* right, not that
> anything is *wired* to anything. A blank page, an empty chart, a dead dropdown, a rule that never fires and
> unreadable text on four of the five skins all pass it. Nothing here compiles Groovy — see [23 §4](23-distribution-and-known-gaps.md).

---

### What the build leaves in the folder

Besides `project.mrjun` and `test-scenarios.md`, a finished build now writes three small things so that a NEW
session opened in that folder knows where it is: `CLAUDE.md`, one skill under `.claude/skills/`, and
`.dokie/project.json`. They are GENERATED — regenerate them any time with
`python3 builder/tools/mrjun.py handoff emit --project ./work`, and never edit them by hand, because the next
regeneration overwrites them. None of them ever contains a credential: an MCP token is registered with Claude Code
itself (`claude mcp add`, scope `local`), which keeps it per project outside this folder — so handing the
folder to someone else hands them no secret. Commit them or not as you prefer; they describe the
folder, not the project.

## 6. Import

⚠️ **Today this is always yours to do, token or not.** The contract describes an AI-driven import (step 6b) and
the platform will grow the tools for it, but they do not exist yet — so a session given a token will tell you it
could not find them and hand you the file, exactly like an offline one. When they do land, the AI will take a
**snapshot tag first** (the only way back — import replaces, it never merges), push the archive, and start the
import with all three business-logic flags stated explicitly, which is the equivalent of choosing **Override**
or **Rebuild** below; its hand-over must then name the three values it passed. ⛔ And `DONE`
is not proof: mail and PDF templates fail with a log warning only and never reach the per-object report, so open
one of each before you believe it.

Doing it yourself, in your project: turn on **"I am author"** at the top, then left menu → **Settings** →
**Import/Export**, and upload `project.mrjun`.

A dialog appears **before** anything is written:

| Choice | What it does | When |
|---|---|---|
| **Override** | full import: business-schema **rows** replaced, CRUDs recreated, integration torn down and rebuilt (allow up to 10 minutes) | ⭐ **the first import, always** |
| **Rebuild** | same, but schemas are **dropped and rebuilt from the archive** — much faster, and the only choice that makes the file authoritative about *structure* | the fix loop; after any column type/drop/rename |
| **Ignore** | ⛔ **the database, CRUDs and sources are not imported at all** — only static content | only when a live database must survive |
| **Cancel** | nothing | — |

> ⛔ **`Ignore` is the dangerous one: it reports success.** The symptoms of pressing it — no data, unchanged
> CRUDs, empty sources — are identical to a completely different failure, so the post-mortem starts in the
> wrong place. Whoever drives the browser must know which button to press.
>
> ⚠️ If **Rebuild** refuses and names objects, that is not a bug — use **Override** for that project.
>
> ⚠️ **Import replaces; it never merges.** To change one field you edit the workdir and re-import the whole
> archive. Anything you fixed by hand in the UI is destroyed by the next import — always fix in `./work`.

**Right after importing:** open a table whose data you changed and confirm the new rows are there (this is the
check against `Ignore`). If contexts show no CRUDs, or rules fail with `No CRUD found with alias X in context Y`,
open **Contexts** in the UI and just re-save the context — the export is correct, do not "fix" it.

---

## 7. Drive it — this is the finish line, not the gates

The AI writes a **`test-scenarios.md`** next to `project.mrjun`: numbered scenarios with role, precondition,
steps and expected result, covering every role, every branch of every process, the prohibitions, the empty
states, the notifications and the dashboard numbers — and a separate section listing what it could **not**
verify itself. Test from that file; the order below is the sweep to do first, because these items are
load-bearing and fail in ways no offline gate can see:

1. **Home** renders real content, **charts visible**
2. **Every nav link** resolves, in the **currently selected language** — then switch locale and check again
3. **Every list page**: rows load, columns show meaningful values
4. **Every form** opens with **all** its fields and **populated** dropdowns; submit, then ⛔ **re-open the row and
   read the value back** — a success toast is not evidence
5. **Every workflow**: start it, take **every branch once**, confirm the task is visible to a **non-admin**.
   An automatic trigger must be run **twice** — you must end up with exactly **one** case, not two
6. **Mail and PDF** render **branded**
7. **All five skins** (Settings → Appearance) on any page with authored CSS; a colour that works on light can be
   invisible on dark
8. **The project log** — look for `MismatchedInputException` / `InvalidFormatException`

Fix in `./work` → `validate` → re-pack → re-import (**Rebuild**) → re-drive the fixed screens **and their
neighbours**. Repeat until clean.

This loop is yours, and the AI knows it: `test-scenarios.md` opens by saying that none of its scenarios has
been executed — and with a token it says exactly what the import did instead, which is still not a run. Hand it back the specific failures (screen, what you pressed, what you saw, and the
`log/ui.log` line if there is one) and it fixes them in the workdir and re-packs. "It doesn't work" is not
enough to act on; one screen with one symptom is.

---

## 8. Two failure shapes worth memorising

**One abort, three symptoms.** "No source selected" **and** contexts with no CRUDs **and** data missing is
**one** deserialization abort, not three bugs. Find `Cannot deserialize …` in the log.

**Blank page.** A page that opens with no menu and no header lost its layout chrome. It is invisible offline —
only a live open reveals it.

---

## 9. Expectations

- **This is a multi-session job.** The library is ~2.7 MB of prose; it is meant to be *routed into* (start at
  [19](19-build-decision-procedure.md), then [13](13-master-playbook-empty-to-dynamic-project.md)), not read
  end to end. The `branches.json` inside an export is multi-megabyte — nobody, human or model, reads it; edit it
  only through `mrjun.py`. Your continuity record between sessions is `build-plan/plan.json` plus `work-case/`.
- **Scale, for calibration.** A real delivered project of this kind runs to ~90 pages, ~20 dynamic CRUDs,
  ~180 rules, several workflows and schedulers, three locales — and got there over **three** import-and-drive
  iterations. A first pass is a first pass.
- **The library is deliberately domain-neutral.** Everything you learn about *your* project goes beside the
  export, never into this repo:
  ```bash
  python3 ./builder/tools/mrjun.py case init --project ./work
  python3 ./builder/tools/mrjun.py case add  --project ./work --name 01-domain-model
  ```

---

## 10. Where to look

| Question | File |
|---|---|
| How the AI must work (the contract) | [`system_prompt.txt`](system_prompt.txt) |
| What to decide, in what order — **start here** | [19-build-decision-procedure.md](19-build-decision-procedure.md) |
| Empty project → working project, step by step | [13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md) |
| `.mrjun` anatomy and every import pitfall | [00-export-format-and-import.md](00-export-format-and-import.md) |
| Testing, gates, the live-run order | [26-orchestration-and-testing.md](26-orchestration-and-testing.md) |
| Known gaps — what no gate catches | [23-distribution-and-known-gaps.md](23-distribution-and-known-gaps.md) |
| ⛔ Theming — **read before the first line of CSS** | [24a-theming-and-dark-mode.md](24a-theming-and-dark-mode.md) |
| What four DELIVERED projects actually did (domain removed) | [`references/`](references/README.md) — the shapes that survived production; read [`references/01`](references/01-solution-shapes.md) while the shape is being decided and [`references/10`](references/10-visual-design.md) beside 24a |
| I have another finished project to teach it from | [`references/INGEST-NEW-REFERENCE.md`](references/INGEST-NEW-REFERENCE.md) — the prompt to paste with a PRD + a `project.mrjun` |
| Every command | [`tools/README.md`](tools/README.md), `python3 ./builder/tools/mrjun.py --help` |
| The full map | [README.md](README.md) |
