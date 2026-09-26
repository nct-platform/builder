# doc/builder — Dynamic-CRUD Project Construction Library

A reference library that lets you **assemble an entire platform project (Dokie / NCT) directly in
`.mrjun` export files** — with no browser — and then re-import it. Focused on **dynamic CRUD integration**
(business logic inside the project: SQL/Groovy over its own DB) — whatever the domain: banking, customs,
ERP, CRM, any document-flow system.

Each file describes one platform entity: which component of the platform owns it (by class/plugin NAME, so you can
talk to the platform team — not by source line number, which goes stale on the next build), what its **exact schema
in the export** is (real JSON from actual exports), and **how to build it from scratch** (a recipe that yields the
exact JSON/HTML). The audience is a builder — human or AI — who reads these docs, **without the platform
codebase**, and **writes the export files**.

---

## Start here

| file | what it is |
|---|---|
| **[GETTING-STARTED.md](GETTING-STARTED.md)** | the human on-ramp — read this first if you have never run a build |
| **[prmpt.txt](prmpt.txt)** | the RUN PROMPT: fill in the PRD path and paste it as the task |
| **[system_prompt.txt](system_prompt.txt)** | the OPERATING CONTRACT the builder must read in full and follow — how to work, and what "done" means |
| **[references/](references/README.md)** | **what four delivered projects actually did** — the shapes that survived production, the ones the deliveries contradicted each other about, and the documented mechanisms nobody ever used. Domain-neutral by construction |

A finished build is **two files, not one**: the export `project.mrjun`, and beside it a `test-scenarios.md`
that lets whoever imports it test the running application without the builder. By default nothing in this library
imports or drives a platform — the offline gates prove the files are right, `test-scenarios.md` is how the
behaviour gets proven, by the person who owns the project. **Optionally** — an MCP token for the target project,
pasted on the `MCP:` line of `prmpt.txt` — the builder performs the **import** itself (contract step 6b: snapshot,
push, the three import flags, the per-object failure report). Nothing else changes: it still builds offline, still
passes the same four gates first, and still drives nothing. An import is not a run.
⚠️ **Not yet, anywhere.** As of CONTRACT-VERSION 2 no platform serves those import tools, so a session given a
token checks, finds them missing, says so and hands over the file — exactly like an offline one. The option is
documented because both halves are being built against it; pasting a token today changes nothing.

---

## How to use this — two steps

**Step 1 — planning (a separate Claude session).**
1. Give Claude the PRD (business requirements) + this library.
2. Claude works through **[19-build-decision-procedure.md](19-build-decision-procedure.md)** — the deterministic
   decision spine: detect the scenario (Phase 0), decompose the PRD into the full entity inventory (Phase 1), and
   make each phase's **Decide** choices. The filled-in Phase-1 inventory + per-phase decisions **are** the
   project's instruction document — there is no separate template to fill in: doc 19's own Phase-1 inventory
   table and its per-phase Decide lists **are** the format, and [26](26-orchestration-and-testing.md) gives the
   machine-checkable `plan.json` ledger that tracks it. Each phase links into the "how to do X" files below.
3. Make Claude re-check the inventory/decisions against doc 19's **Done-when** gates (what it might have missed).

**Step 2 — assembly (a different Claude session).**
1. Give Claude the **empty baseline**, which ships with this library: the packed
   `initialtemplates/empty.mrjun` (or the same project already unpacked into a folder). It is a
   REPORT-typed project skeleton — see [13 §1](13-master-playbook-empty-to-dynamic-project.md). Use it; do not
   hunt for an export elsewhere unless you are taking it from the very platform you will import
   into (see [23 §3](23-distribution-and-known-gaps.md) on version coupling).
2. Claude unpacks it into a folder.
3. Step by step, following the instruction document + [`13-master-playbook`](13-master-playbook-empty-to-dynamic-project.md),
   Claude **writes** `branches.json`, `rep-objects.json`, `dynamic-cruds.json`, `project-db.dump`.
4. ⛔ **Before typing the FIRST line of authored CSS — or any HTML component, chart CSS, layout HTML or inline
   `style=` — read [24a-theming-and-dark-mode.md](24a-theming-and-dark-mode.md).** The platform's five skins are a
   whole-stylesheet swap: there is **no theme class to select on**, so CSS that names a colour literally is
   correct on one skin and unreadable on the other four, and neither the import nor `validate` will tell you. 24a
   gives the two-level token fallback that *is* correct, the traps (`h-100` = `100vh`, inline `style=`, a global
   `<style>` block) and a copy-paste starter. Reading it costs minutes; skipping it has cost whole projects a
   re-do of every screen. Then continue into [24](24-html-component-studio.md) /
   [24b](24b-html-composition-and-plugin-tags.md) / [24c](24c-html-data-tables-and-paging.md) /
   [24d](24d-html-component-structure.md) for the component work.
5. The user re-imports the `.mrjun` and gets an implementation of their requirements. (With an MCP token Claude
   will import it and report the per-object result — once the platform serves those tools; today it does not,
   see the note above.) The *driving* stays the user's either way.

**This library is reusable; your project's knowledge is not part of it.** The docs here teach the platform for
**any** domain, so nothing case-specific may be written into them. Everything you learn while building **one**
project — its entities in the customer's own words, its screen inventory, why this CRUD became a tree, its
realm/client and schema names, the gotchas that only bite this data set — goes next to that project's export:

```
mrjun.py case init --project ./app                       # creates ./app-case/ with a README
mrjun.py case add  --project ./app --name 01-domain-model # one note (body from --from or stdin)
mrjun.py case ls   --project ./app
```

`./app-case/` is a **sibling** of the unpacked project, so `mrjun.py pack` — which walks only the project dir —
never sweeps those notes into the `.mrjun` you ship. (You can move the folder with `--dir`; if you do, keep it
**outside** the project directory, or `pack` will pick it up.) The test for where something belongs: if it would be true
for the *next* project too, it is a library change (written with placeholders, not this customer's names); if it
is only true here, it is a case note. Full flags — [`tools/README.md`](tools/README.md) § *Case notes*.

> **Start reading here → [19-build-decision-procedure.md](19-build-decision-procedure.md)** (the decision spine:
> which scenario, what to decide in what order, when each phase is done), then
> **[13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md)** (build
> order, dependency graph, checklist, pitfalls). The rest of the files are references the two link into —
> except **[24a](24a-theming-and-dark-mode.md)**, which is not a reference to look things up in but a
> **prerequisite to read before you author any CSS at all**.

---

## 📐 `references/` — what four delivered projects actually did

The numbered docs tell you what the platform **can** do and which slot each thing lives in.
[`references/`](references/README.md) tells you what **survived contact with production**: four delivered
systems were unpacked and read end to end — 757 pages, 244 dynamic CRUDs, 2 115 CRUD methods, 1 405 rules,
3 047 `nct.html.plugin` nodes, 185 charts, 21 workflows, 43 schedulers — and every finding was re-checked by a
second pass whose only job was to refute it. The exports were then deleted; only the technique remains.

**⛔ Nothing in that folder names an industry, a customer or a business domain.** Not for confidentiality
alone: a named domain turns a technique into a template, and an assistant that has read "how the X system did
it" will reach for X's entity names on a brief that has nothing to do with X. Sources are letters (**A**–**D**)
and sizes; every entity in every example is `document` / `documentLine`, `case`, `task`, `item`, `unit`,
`partner`. **Hold that line if you add to it.**

| file | what it settles |
|---|---|
| [references/01-solution-shapes.md](references/01-solution-shapes.md) | which shape a brief becomes, the artefact budget that comes with it, and what to refuse to build |
| [references/02-navigation-and-front-door.md](references/02-navigation-and-front-door.md) | the nav three deliveries converge on, the front door, and the two silent ways a nav grant dies |
| [references/03-dynamic-crud-conventions.md](references/03-dynamic-crud-conventions.md) | the five entity kinds and the method skeleton each one needs to survive real data |
| [references/04-forms-actions-validation.md](references/04-forms-actions-validation.md) | what real forms are built from — and the long list of documented mechanisms nobody used |
| [references/05-process-and-scheduling.md](references/05-process-and-scheduling.md) | when a process earns a BPMN, how a case is really opened, and idempotent sweeps |
| [references/06-security-and-roles.md](references/06-security-and-roles.md) | the disjunction that defeats persona gating, row scope that fails closed, and the review checklist |
| [references/07-localization.md](references/07-localization.md) | the slots that carry locales, the dead zones, and the escape hatch for each |
| [references/08-charts-and-dashboards.md](references/08-charts-and-dashboards.md) | the label+code+measure contract, per-theme palettes, and how a board is composed |
| [references/09-studio-components.md](references/09-studio-components.md) | when a hand-built console is justified, and the anatomy of one that works |
| [references/10-visual-design.md](references/10-visual-design.md) | how three deliveries looked finished with **zero authored CSS**, and what to do when they cannot |
| [references/knowledge-graph.json](references/knowledge-graph.json) | the same knowledge as data — 429 nodes, 936 edges: every pattern with its rule, its artefact, how many of the four showed it, the library doc it belongs beside, and the anti-pattern it replaces |
| [references/INGEST-NEW-REFERENCE.md](references/INGEST-NEW-REFERENCE.md) | **the prompt to paste when you have a new reference project (a PRD + a `project.mrjun`)** — it folds the new evidence into the existing documents instead of adding a per-project file |

**How to weigh a finding.** A pattern seen in one delivery is an idea; in three, a convention; contradicted
between two, a decision you must make consciously — and the document says which way to jump.

**When to read it.** Doc 19 Phase 1 (which shape) → `references/01`. Before any CSS → `references/10` with 24a.
Before hand-building a console → `references/09` §1, which will usually tell you not to. Every numbered doc
carries a 📐 banner pointing at its own field evidence.

```bash
# every pattern that governs charts, strongest evidence first
jq '[.nodes[] | select(.type=="pattern" and (.artefact|test("chart";"i")))]
    | sort_by(-.evidenceCount)' references/knowledge-graph.json

# where the library is contradicted by delivery evidence
jq '[.edges[] | select(.rel=="corrects")]' references/knowledge-graph.json
```

⚠️ The graph is an index, not the knowledge: it points at a rule, the document explains why it exists and
what breaks without it.

---

## 🔧 Tooling: `tools/mrjun.py` (run instead of generating JSON by hand)

To **avoid writing JSON by hand** (and breaking it), the set includes a standalone `python3` CLI
[`tools/mrjun.py`](tools/mrjun.py) (stdlib, no dependencies) — it edits an **unpacked** export and
encodes all the "hard rules" (settings vs model, `id=null` + relations by `identifier`, fresh uuids,
`ruleType→executor`, preserving the typo `process.table.pluin`, atomic writes, `ensure_ascii=False`).
**Index of every command + a "doc → commands" mapping → [`tools/README.md`](tools/README.md).**
(The toolkit grows; `python3 tools/mrjun.py --help` is always the authority for what exists and what it takes.)

```
python3 tools/mrjun.py unpack app.mrjun ./app     # unpack
python3 tools/mrjun.py inspect --project ./app     # what's inside (counts for everything)
python3 tools/mrjun.py page add --parent root --name "Invoices" --auth --project ./app
python3 tools/mrjun.py roleaccess set <id> --authenticated true --role "admin:*" --role "user_view:view" --project ./app
python3 tools/mrjun.py source add --name app_schema --dbtype POSTGRESQL --host <host> --port 5432 --db <db> --schema app_schema --user <user> --password <placeholder> --project ./app
python3 tools/mrjun.py crud add --alias invoices --name "Invoices" --source app_schema --schema app_schema --context app_context --scaffold-methods --project ./app
python3 tools/mrjun.py workflow add --name "Declaration Review" --user-task "Intake:Declaration Forms" --project ./app  # needs the form group to exist first
python3 tools/mrjun.py mailtemplate add --name "Order Shipped" --subject "Order {{orderNo}} shipped" --html @body.html --project ./app
python3 tools/mrjun.py pdftemplate scaffold intakeReceipt --out intake.json --field counterpartyName:text  # skeleton pdfme JSON to fill in
python3 tools/mrjun.py pdftemplate add --alias intakeReceipt --name "Intake Receipt" --template @intake.json  # → rep-objects.pdfTemplates[] (portable in .mrjun)
python3 tools/mrjun.py validate --project ./app    # integrity checklist before re-import
python3 tools/mrjun.py pack ./app app.mrjun         # pack back up
```

**Rule:** if an entity is created/changed/deleted, first check whether there is a command for it in
[`tools/README.md`](tools/README.md); run it. There are commands for e.g. `workflow`/`mailtemplate`/
`pdftemplate` (`workflow add`, `mailtemplate add`, `pdftemplate scaffold`+`add` — `add` is what ships it in the `.mrjun`). Hand-written JSON is only for when there is no
command: e.g. complex workflow gateway logic (multiple conditional outgoing flows +
`conditionExpression` — `workflow add --gateway` gives only a one-to-one placeholder, the split branches
are written by hand, see [07](07-workflows-and-tasks.md)) or fine-tuning schedulers. Each doc
below contains a **"🔧 Tooling"** block with commands specific to its entity. After edits, always run
`validate`.

---

## Table of contents

| # | File | About |
|---|---|---|
| — | [Glossary](#glossary--platform-words-used-from-page-one) | **Platform words** (parsis, kicker, virtual plugin, branch, content alias, RIMM, twin, IRefreshable, REPORT project) — read once before the docs |
| 19 | [19-build-decision-procedure.md](19-build-decision-procedure.md) | **Decision spine — start here.** The deterministic procedure: which scenario (empty / wire-existing / modify-filled), then what to DECIDE, in what order, and when each phase is DONE — routing into the docs below |
| — | [13-master-playbook-empty-to-dynamic-project.md](13-master-playbook-empty-to-dynamic-project.md) | **Main playbook:** empty project → dynamic-CRUD project, step by step, with links to everything below |
| 00 | [00-export-format-and-import.md](00-export-format-and-import.md) | Anatomy of `.mrjun`; schema of each file; export/import; the `type==REPORT` gate; static vs dynamic at the file level |
| 01 | [01-content-model-and-pages.md](01-content-model-and-pages.md) | Content tree, nodes, `properties`, pages (`siteMapPage`), tabs, layout HTML, `roleAccess`/hidden, virtualPlugins |
| 02 | [02-form-controls-reference.md](02-form-controls-reference.md) | All form controls: settings JSON + HTML + mapping/validation/events/default/prohibited/between |
| 03 | [03-generate-fields-from-crud.md](03-generate-fields-from-crud.md) | "Generate fields from CRUD": generation of each field, the exact HTML wrapper, all dialog columns |
| 04 | [04-crud-table-plugin.md](04-crud-table-plugin.md) | CRUD Table plugin: settings (`model`), columns, filters, actions (default/custom, direct/non-direct), import, fetch-rule |
| 05 | [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md) | CRUD Tree + Process Table (deltas relative to CRUD Table); ProcessTable settings, indexSettings, filterExpression |
| 06 | [06-form-groups-and-mapping.md](06-form-groups-and-mapping.md) | Form Groups, landing, predicate→form mapping, Create Default Actions, rule naming |
| 07 | [07-workflows-and-tasks.md](07-workflows-and-tasks.md) | Workflows, BPMN, elements, user task settings, all task types, processes |
| 08 | [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) | The 3 types of Groovy rules + templates + context model; how a rule reads context in crud/process/form/list |
| 09 | [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md) | Groovy hints (server `HintsService`) vs live context-data hints — what the difference is |
| 10 | [10-database-management.md](10-database-management.md) | Database Management plugin + `project-db.dump` (schema/table/column/index/constraint/sequence/trigger); auto-generation |
| 11 | [11-business-logic-dynamic-crud.md](11-business-logic-dynamic-crud.md) | Business Logic plugin: dynamic CRUD, dtoFields, filterFields, methods (SQL/Groovy), sources; **dynamic vs static** |
| 12 | [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) | Queries, sources, schedulers, roleGroups, settings, mailTemplates, project settings |
| 14 | [14-plugin-catalog-all.md](14-plugin-catalog-all.md) | **Full plugin catalog** — each `pluginName` one by one: HTML (`nct.html`), label/image/link/help/tab, `action.button`, `chart.js`, `global.replacement`, all `admin.*`/system plugins (deep chart data-binding + params + filters → [22](22-charts-params-and-filters.md)) |
| 14a | [14a-plugin-config-reference.md](14a-plugin-config-reference.md) | **Field-level config reference for every plugin name except two** (`calendar.plugin` is covered in doc 14 only; `nct.mailbox.plugin` in doc 31) — each one's settings panel + editor + JSON config slot + **field-by-field** table, source-grounded (plugin class + editor + config DTO). The chart-doc depth, for every plugin — use to hand-author any node's config exactly |
| 15 | [15-pdf-and-mail.md](15-pdf-and-mail.md) | **PDF templates** (`report.pdf.templates`/`pdf.report`) + **Mail templates** + the Groovy flow "PDF from template → send by email" |
| 16 | [16-groovy-service-api.md](16-groovy-service-api.md) | **The full Groovy `service.*` capability surface** — what you can actually do in a script (crud/global/security/rimm/report/notification/enums/**workflow.start**/**store**/**mailbox**/…) + notifications + cross-flows + the session- and user-scoped key/value stores, and the namespaces that only LOOK like they exist |
| 17 | [17-left-nav-quick-links.md](17-left-nav-quick-links.md) | **Left-nav quick links** — how to add a quick link / group to the sidebar by authoring the `modelGroups` quick-links tree on `site.kicker.plugin` (`left-nav`) in the export |
| 18 | [18-existing-schema-to-dynamic-wiring.md](18-existing-schema-to-dynamic-wiring.md) | **Reverse scenario:** wiring an EXISTING populated schema + complete UI to dynamic CRUDs (the static→dynamic conversion). CHECK/NOT NULL/audit/single-company handling, enum-dropdown option snapshots, document lines + delete cascade, and verifying against **real rows** (the bug classes an empty-table smoke test misses) |
| 20 | [20-localization.md](20-localization.md) | **Localization hub:** the L0–L5 layer model, the export-key inventory, key-based UI strings + the `nct-localization` microservice, entity-data `localize`, runtime resolution + Groovy locale, auto-translate + the hand-authoring coverage rule |
| 21 | [21-homepage-and-redirect.md](21-homepage-and-redirect.md) | **Homepage & redirect** — the project front door: how the bare root URL resolves + the `Redirect` content-alias path; never ship an empty Home |
| 22 | [22-charts-params-and-filters.md](22-charts-params-and-filters.md) | **Charts, params & filtering-through-params** — `chart.js.plugin` (config in `properties.Javascript`), `$$()` data binding + `ChartJsReplacement` queries, query params, the `global.replacement` filter bar, click-to-cross-filter, theme-safe rendering |
| 23 | [23-distribution-and-known-gaps.md](23-distribution-and-known-gaps.md) | **Distribution, the live-debug loop & known gaps** — what's bundled vs what a recipient still needs (platform/codebase/PRD), where bugs surface (UI vs `log/ui.log`), version pinning docs↔platform, and the runtime-bug classes `validate` can't catch yet (drive them live) |
| 24 | [24-html-component-studio.md](24-html-component-studio.md) | **HTML Component Studio** — `nct.html.plugin` extended into a component project: a **JS-library + isolated-script + per-theme-CSS** unit that **calls the project's rules & business logic from JS** (`ctx.callRule`/`ctx.callBl`), reads a frozen `ctx.contextData`, promotes page actions into the **breadcrumb** (`ctx.breadcrumb`), and vendors lib files via `tenant-files/studio/…`, pulls further documents in server-rendered with `await ctx.include('<doc>.html', sel)`, and decides **which** scripts run (legacy = every enabled one; include mode = only the included ones). Toolkit: `node set-studio`, `asset add`. Purely additive (no `studioModel` ⇒ classic raw HTML) |
| 24a | [24a-theming-and-dark-mode.md](24a-theming-and-dark-mode.md) | **Theming & dark mode — read this before writing ANY authored CSS.** The five skins are a whole-stylesheet swap (no theme class to select on), so the only correct tools are the platform's own classes and a **two-level token fallback** (`var(--current-line, var(--bs-light))`). Token census per skin, the real palette in hex, `css.byTheme` + what the scoper does to your selectors, the `h-100`/`!important`/inline-`style=` traps, and a copy-paste starter CSS block. The doc that stops white cards on a black page |
| 24b | [24b-html-composition-and-plugin-tags.md](24b-html-composition-and-plugin-tags.md) | **Composition** — embedding plugins in authored HTML (`<plugin id name vp>` + `<prop>`/`<behavior>` grammar), the ⛔ tag-id ↔ child-`identifier` binding, `<prop>` being a **seed** not a setting, why nested `<plugin>` is dropped (and why `<include>` is what composes *documents*, while node depth is what nests *plugins*), and the four ways to **reuse a whole component** across pages (shared VP / clone VP / duplicate node / `ctx.byName`) with what each really does to identity |
| 24c | [24c-html-data-tables-and-paging.md](24c-html-data-tables-and-paging.md) | **Data tables in an HTML component** — when NOT to hand-build one, the paged CRUD contract (`rowsInPage`/`pageNumber` → `{content,totalElements,…}`), the reference page-rule + fetch/render/pager/sort JS with an in-flight guard, pushing sort/filter down to SQL (and the sort-column whitelist), row vs page actions, and the performance budget that a 5 000-row fetch blows |
| 24d | [24d-html-component-structure.md](24d-html-component-structure.md) | **Component structure** — how to split ONE `nct.html.plugin` into documents and scripts: `<include src="detail.html">` (substituted **server side, before parsing**, so an included document's `<plugin>` tags are real child nodes) and `<include src="boot.js">` (which author scripts run), `ctx.include` at runtime vs the client-only `ctx.showHtml`, names stored without an extension but addressed with one, and when a component is worth splitting at all |
| 25 | [25-form-settings-validation-and-events.md](25-form-settings-validation-and-events.md) | **Form settings, validations & field events** — the control **Config accordion** (Prohibited/Default/Mandatory/Validations/Events) + the **Form Settings** panel (FormDto). Deep-dives **"Create Validation from Template"** (the 51 templates' generated `GroovyPredicate` bodies, params, the 10 regex presets, ERROR/WARNING), **field events** (event → Execute-Rules-Before-Refresh → refresh fragment; several targets = several mappings), **Hidden Content Configuration**, **Global vs Action-Based validation** (`validation.addFieldError(control-name,…)`), **Allow Drafts**, and **Get context data** (read what the live form would actually send) — with decision guidance so a PRD phrase routes to the right knob |
| 26 | [26-orchestration-and-testing.md](26-orchestration-and-testing.md) | **Orchestration & testing — how NOT to finish a big PRD fast-and-shallow.** Decompose a PRD (epics→stories→small units) into a **`plan.json` coverage ledger**; build + TEST each unit; the **`mrjun.py coverage` gate** that FAILS (non-zero) on any missing/untested item (the machine-checkable "constitution" that catches "shipped zero workflows / half the forms"); the **live-import acceptance loop**; the working folder; parallelism (Workflow tool) where it helps and the sequential-build limit; and **graphify** for the comprehension layer (`tools/setup-graphify.sh`). Grounded in Replit-agent + spec-driven-development practice |
| 27 | [27-event-driven-process-start.md](27-event-driven-process-start.md) | **When the SYSTEM opens the case — the process nobody clicks Start on.** Read it the moment the PRD says "nightly", "if no response within N days", "N days before expiry" or "when the record is approved": that process has **no start form**, and giving it one is the default failure. The recognition test + a PRD-phrase → trigger table; the **three system triggers** (scheduler tick / CRUD GROOVY method / service task) and what each rule does and does NOT get — the first two are HEADLESS (`contextDataMap` is null), while a service task receives the running case's real document; the build order (workflow → process group → worklist → context aliases → claim → EXECUTION rule → trigger); the worked rule that **gathers rows from business logic → shapes a context-data document → `service.workflow.start` → marks the row**; **idempotency as the author's own job** (nothing anywhere asks whether a case already exists, so an unguarded sweep opens a new case on every tick, forever); the five option keys that decide who ever sees the case; and the live acceptance run — nothing offline can execute this chain |
| 28 | [28-support-mode-over-mcp.md](28-support-mode-over-mcp.md) | **Support mode — changing a LIVE project over MCP.** The delta to `system_prompt.txt` for a project that already RUNS: how `.dokie/project.json` picks the mode and the CHANNEL (files-only vs dual-write); what an MCP token is and — decisively — what it is NOT (one project, no branch, no scope, so **every write lands on the PUBLISHED branch with no draft and no undo**); the working folder; the one order a dual write may go in (edit → `validate` → ONE live write → read it back) and the four ways it can half-happen; a per-object table of which change travels down which channel; **page layouts over MCP** (§5b) — why `create_page` leaves a page with nothing in it and `apply_layout_to_page` is the second half of it, why applying a layout COPIES it so an edit never reaches a built page, and why renaming or deleting one is the dangerous edit; and the **honest-limits list** — PDF templates, locales, assets, free enums and seed data have no live channel at all and still need a re-import, which REPLACES the project |
| 29 | [29-global-resources.md](29-global-resources.md) | **Global resources: the project's own files — js, css, html, fonts, images, in ONE tree, loaded on EVERY page.** Read it the moment a requirement says "on all pages" (a brand stylesheet, an analytics tag, a vendored widget) — and read §1 first, because a script that belongs to ONE screen is [24](24-html-component-studio.md), not this. The optional `globalAssets` key on each branch in `branches.json`; ONE folder tree holding every kind of file, because that is the only arrangement in which a stylesheet's relative `url(../fonts/…)` resolves; what a file's kind decides — only a script or a stylesheet has a SWITCH, an html fragment and a font are served and never loaded; folders as entities, so a whole vendored kit switches off as a unit without rewriting the flags underneath; **nothing ever arrives switched on**; one storage subtree per BRANCH, so an edit in a draft cannot rewrite what the published site serves; a stylesheet limited to particular skins (empty = all, the default); the single load order and how an uploaded archive is ordered; the dependency suggestions ("you switched this on — it still needs jQuery"); and the gaps worth saying out loud (environment PUBLISH does not carry them; every file rides in every future archive and tag). Toolkit: `globalresource add`, `add-zip`, `mkdir`, `ls`, `set`, `rm`. Not a sandbox, and the doc says so |
| 30 | [30-live-test-bugfix-and-autotest.md](30-live-test-bugfix-and-autotest.md) | **The live test, the bug-fix loop, and the autotest project — the ORDER OF WORK once a project is imported.** Import -> deploy the workflows -> DRIVE every scenario in a real browser -> BUGLIST -> fix over MCP -> re-drive -> repeat until the scenario file passes -> **and only then ask the user whether to build an autotest project**. ⛔ Corrects the old claim that the re-import is the human's job: the project's own `/settings` page takes the `.mrjun` and you are already signed in there, so the loop is yours to close — but a re-import resets workflow DEPLOYMENT and reverts any live MCP write you never mirrored into the export. Covers **author mode**: every project inherits the admin quick links from `empty.mrjun`, they are visible only with the Author role AND author mode ON, the toggle's label states the ACTION not the state ("I am not an author" = it is currently ON), the mode is STICKY per user so a persona check must switch it off explicitly, and "Edit site" is the authoring page builder — author tooling, never an acceptance scenario. Lists all 14 inherited admin paths (`rules contexts form workflows processes users roles database bl audit-logs mail-templates pdf-templates schedulers settings`, plus `profile`). Names the constraint that shapes every permission test: the Create-User form has **no password field**, so an autotest can create a user but can never sign in as one — personas are tested by re-assigning role groups on the account you can already authenticate as, **never dropping `Author`**, which is the only group that can grant roles. Then the autotest project itself: `test/` beside the export (never inside — `pack` walks the export dir), `.env` with ONE author credential and nothing secret in the repo, the page-object layout, the nine areas the suite must assert, `--run-destructive` gating, waiting on CONTENT not navigation in a Wicket app, and naming each regression guard after the defect it caught |
| 31 | [31-email-integration-and-mailbox.md](31-email-integration-and-mailbox.md) | **Email — the project sending as ITSELF, and a mailbox on a page.** Read it the moment a PRD says "from our domain", "the support inbox", or "when a customer emails us, open a case". ⛔ Opens with the fact that decides the whole plan: the mail ACCOUNTS, their credentials and the on/off switch are **not in the `.mrjun`** — they are configured live after import, so a build that assumes an inbox produces a page that is correct and empty. What you DO author: the `nct.mailbox.plugin` node (field-by-field), the Groovy rules, the templates. The model at the centre of it: a message has **two independent read states**, one for people and one for rules, so a colleague glancing at a message cannot make an importer skip it and an overnight importer cannot empty somebody's unread count. Then: how the sender is chosen and why every failure falls back to the platform account; the outbox's retries and its permanent-vs-transient split; the three policy switches (whether the project's OWN mail leaves from its account at all — off makes the integration receive-only; platform fallback — leave it ON, the same queue carries password resets; and whether the platform's own system mail uses the customer's address); transports, from SMTP through ten shipped provider APIs to a **custom HTTP API the customer describes themselves** (placeholders, per-recipient and per-attachment repeaters, escaping that is the engine's job and never the template author's, and a preview rendered by the code that actually sends); what a polled mailbox does about folders, history, duplicates and retention; and `service.mailbox.*` in a rule with the canonical inbox-to-records rule — including the `markRead()` that is the only thing standing between it and reprocessing the same message forever |

---

## Glossary — platform words used from page one

These are platform coinages. They appear all over the library (and in conversations with the platform team), so
learn them once here; each one has an owning doc that goes deeper.

| Term | What it means | Owning doc |
|---|---|---|
| **parsis** | A content **slot**. A `parsis.plugin` / `nct.parsis.plugin` node renders its child nodes in place — it is the container you drop a table, form or component into. A page's real content always hangs off one. | [01](01-content-model-and-pages.md) |
| **kicker** | The platform's side chrome. `site.kicker.plugin` is the **left navigation** on a rendered page (the quick-links tree lives in its `modelGroups` property), `site.right.kicker.plugin` the right panel. In authoring, the same word names the settings panels that slide in beside a selected node. | [17](17-left-nav-quick-links.md), [01](01-content-model-and-pages.md) |
| **virtual plugin** / **VP** | A reusable content subtree registered on the branch (`branches.json` → `virtualPlugins`) rather than on one page. A `<plugin vp="…">` tag instantiates it, so one definition can appear on many pages. | [01](01-content-model-and-pages.md), [24b](24b-html-composition-and-plugin-tags.md) |
| **branch** | A versioned content tree inside the project. `branches.json` carries them; exactly one is the **published** branch that the site renders. | [00](00-export-format-and-import.md), [01](01-content-model-and-pages.md) |
| **content alias** | The URL segment of a page node (its top-level `alias` field). A slash-separated path of aliases addresses a page — which is exactly what the root `Redirect` property holds. | [01](01-content-model-and-pages.md), [21](21-homepage-and-redirect.md) |
| **RIMM** | The platform's own shared/lookup data source, living in a per-project schema named `rimm_<realm>_<client>` (platform users, reference lists). Groovy reaches it through `service.rimm.*`. ⛔ A RIMM source is **recreated on import** — never put it in the export. | [12](12-queries-sources-schedulers-and-rest.md) |
| **twin** | The browser-side JS object paired with a server-side component: the server emits a per-component init script that creates the twin, and your JS calls back through it (`twin.ajax(…)`). You only meet the word when writing component JS. | [24](24-html-component-studio.md) |
| **IRefreshable** | The interface a component implements to be re-rendered on demand (`refresh()`). Field events and list actions target one by its `uniqueIdentifier`, which is why "refresh target" fields want that id and not `identifier`. | [02](02-form-controls-reference.md), [25](25-form-settings-validation-and-events.md) |
| **REPORT project** | The project **type** recorded in `tenant.json`. Dynamic-CRUD projects are REPORT-typed, and several import steps run only for that type — which is why you build on the REPORT-typed `empty` baseline. | [00](00-export-format-and-import.md), [13](13-master-playbook-empty-to-dynamic-project.md) |
| **dynamic CRUD** | Business logic defined **inside the project** (SQL/Groovy methods stored in `dynamic-cruds.json`) instead of compiled Java in a separate service. This library is about the dynamic path. | [11](11-business-logic-dynamic-crud.md) |

---

## Key facts (common to the whole library)

- **`.mrjun` = ZIP.** Files: `tenant.json`, `branch-metadata.json`, `branches.json` (the content tree),
  `rep-objects.json` (backend objects, 14 collections), `project-db.dump` (`nct-jdbc-dump-v1`),
  `project-db-meta.json`, `integrations.json` (the pinned Business Logic integration — without it the dynamic
  CRUDs have nothing to bind to), `dynamic-cruds.json` (dynamic only), `favicon/`, `tenant-files/`.
- **Content tree:** each node = `{pluginName, properties, children, roleAccess, identifier, order, …}`.
  A form control's config is a JSON string in `properties.settings.stringValue`; a table's config is in
  `properties.model.stringValue`.
- **Relations are by `identifier` (UUID).** In rep-objects `id = null` (relations by `identifier`). In content-tree
  nodes `id` is a non-empty surrogate UUID, distinct from `identifier` (see [01](01-content-model-and-pages.md)
  §"id vs identifier"). When creating nodes the mrjun tool sets `id=null`, relying on assignment at import time.
- **Static vs dynamic:** a **static** project's business logic is compiled Java `@Crud` in a separate service — no
  `dynamic-cruds.json`, a DB dump without the business schema, and it is **not** reconstructable from the export.
  A **dynamic** project keeps the logic inside the project (`dynamic-cruds.json` + the real business schema in the
  dump + queries + source; fully reconstructable). **We document dynamic.**
- **3 types of rules:** `PREDICATE/GroovyPredicate`, `EXECUTION_RULE/GroovyExecutionRule`,
  `VALIDATION_RULE/GroovyValidationRule`. The body is in `rule.ruleScriptStr`.
- **Choices rules (dropdown / autocomplete / tree-picker options) MUST convert rows to option pairs:** the
  EXECUTION rule behind a `settings.ruleIdentifier` ends in
  `return service.global.conversion.toSelectOptions(list,"<key>","<display>")` (dropdown/tree-picker;
  localized display field → `toSelectOptionsLocalized`, else labels stay in the project's base locale) or
  `toAutoCompleteOptions(list,"<display>")` (autocomplete). Returning a raw `service.crud.X.findAll(...)`/`find(...)`
  entity list makes the picker show **"No results found"** AND hides the **Show Nav** affordance (`validate` now
  ERRORs on this). Call `findAll([:])` (ALL keys absent) — never a PARTIAL param map, whose unbound `:col` first
  appears as `$1 IS NULL` → Postgres *"could not determine data type of parameter $1"*; a searchable dropdown uses
  the `acFindAllBy<X>Like` pipeline. **Full recipe + naming table → [02 §4a](02-form-controls-reference.md).**
- **Plugin catalog — 66 `pluginName` in the `@PluginConfig` registry** (64 nct-ui + 2 mrjun; see [01](01-content-model-and-pages.md);
  a real project's export typically uses ≈60 of them); the typo `process.table.pluin` is real.

---

## Provenance

Every statement in this library was cross-checked against the platform source (the Dokie application, the mrjun
CMS library and the richwicket UI framework) and against real, working project exports. The build the library was
last verified against is stamped in [23 §3](23-distribution-and-known-gaps.md). Where older platform documentation
diverges from the code or from what an export actually contains, the code/export takes priority — the prose docs
are outdated in places (wrong paths, invented plugins, a `.dokie` extension instead of `.mrjun`).

When you need ground truth for your own project, the authority is **your** unpacked export: `jq` over
`branches.json` / `rep-objects.json` / `dynamic-cruds.json` answers "what does this really look like" faster than
any prose, and `python3 tools/mrjun.py inspect --project ./app` prints the counts for everything in it.
