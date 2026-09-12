# references — what four delivered projects proved, with the projects removed

The library next door tells you what the platform *can* do and which slot each thing lives in. This folder
tells you what **actually survived contact with production**: the shapes four delivered systems converged on,
the ones they contradicted each other about, and the mechanisms the library documents that no delivery ever
used. It was written by reading those four exports end to end — 757 pages, 244 dynamic CRUDs, 2 115 CRUD
methods, 1 405 rules, 3 047 `nct.html.plugin` nodes, 185 charts, 21 workflows, 43 schedulers — and then the
exports were deleted.

## ⛔ The rule that governs every line here

**Nothing in this folder names an industry, a customer, or a business domain.** Not because of confidentiality
alone, but because a named domain turns a technique into a template: an assistant that has read "how the X
system did it" will reach for X's entity names and X's screen list on a brief that has nothing to do with X,
and the reader gets a worse system than if the example had never existed. So every entity in every example is
`document` / `documentLine`, `case`, `task`, `item`, `unit`, `partner`; every screen is named by its job.

If you add to this folder, hold that line — [INGEST-NEW-REFERENCE.md](INGEST-NEW-REFERENCE.md) says how.

## The four sources, as sizes only

Evidence is quoted as "3 of 4" and the sources are letters. That is deliberate: the letter tells you how much
weight a pattern carries and nothing about where it came from.

| | scale | shape in one line |
|---|---|---|
| **A** | 433 pages · 163 CRUDs · 619 rules · 22 hand-built consoles · 27 schedulers | a whole operation in one tenant, generated backbone + authored front end |
| **B** | 129 pages · 38 CRUDs · 416 rules · 5 workflows | registers and documents with derived numbers and three locales |
| **C** | 128 pages · 31 CRUDs · 271 rules · 87 charts · 8 workflows | case work with statutory deadlines and a dense analytics portfolio |
| **D** | 67 pages · 12 CRUDs · 99 rules · 1 workflow | a small, complete pilot — the shape a first delivery should have |

A pattern seen in one of them is an idea; in three, a convention; contradicted between two, a decision you
must make consciously — and the document says which way to jump.

## Read in this order

| file | what it settles |
|---|---|
| [01-solution-shapes.md](01-solution-shapes.md) | which shape a brief becomes, the artefact budget that comes with it, and what to refuse to build |
| [02-navigation-and-front-door.md](02-navigation-and-front-door.md) | the nav three deliveries converge on, the front door, and the two silent ways a nav grant dies |
| [03-dynamic-crud-conventions.md](03-dynamic-crud-conventions.md) | the five entity kinds and the method skeleton each one needs to survive real data |
| [04-forms-actions-validation.md](04-forms-actions-validation.md) | what real forms are built from — and the long list of documented mechanisms nobody used |
| [05-process-and-scheduling.md](05-process-and-scheduling.md) | when a process earns a BPMN, how a case is really opened, and idempotent sweeps |
| [06-security-and-roles.md](06-security-and-roles.md) | the disjunction that defeats persona gating, row scope that fails closed, and the review checklist |
| [07-localization.md](07-localization.md) | the slots that carry locales, the dead zones, and the escape hatch for each |
| [08-charts-and-dashboards.md](08-charts-and-dashboards.md) | the label+code+measure contract, per-theme palettes, and how a board is composed |
| [09-studio-components.md](09-studio-components.md) | when a hand-built console is justified, and the anatomy of one that works |
| [10-visual-design.md](10-visual-design.md) | how three deliveries looked finished with zero authored CSS, and what to do when they cannot |

## The machine layer

[knowledge-graph.json](knowledge-graph.json) carries the same knowledge as data: every pattern with its rule,
the artefact it lives in, how many of the four deliveries showed it, the library doc it belongs beside, and
the anti-pattern it replaces — plus the edges between them. Use it to answer questions without reading
everything:

```bash
# every pattern that governs charts, strongest evidence first
jq '[.nodes[] | select(.type=="pattern" and (.artefact|test("chart";"i")))]
    | sort_by(-.evidenceCount)' knowledge-graph.json

# where the library is contradicted by delivery evidence
jq '[.edges[] | select(.rel=="corrects")]' knowledge-graph.json

# the conventions with unanimous support
jq '[.nodes[] | select(.type=="pattern" and .evidenceCount==4) | .rule]' knowledge-graph.json
```

⚠️ The graph is an index, not the knowledge: it points at a rule, the document explains why it exists and what
breaks without it. Read the prose before acting on an edge.

⚠️ **60 of the 222 patterns carry `evidenceCount: null` and `attribution: "unrecorded"`.** The technique was
read out of a delivery, but which one was not written down at the time, and guessing afterwards would have been
worse than saying so. Treat those rules as sound and their *weight* as unknown — they are never a claim that no
delivery showed the pattern. The next ingest ([INGEST-NEW-REFERENCE.md](INGEST-NEW-REFERENCE.md)) should
re-attribute what it can and delete this paragraph when the count reaches zero.

```bash
# the unattributed ones, to re-check against a delivery you still have
jq '[.nodes[] | select(.attribution=="unrecorded") | .id]' knowledge-graph.json
```

## What is deliberately not here

- **No per-project case studies.** They were written during the study and discarded on purpose; a case study
  teaches the case, and the next brief is never that case.
- **No brief text, no screenshots, no seed data, no figures.** The technique transfers; the customer's
  material does not.
- **No claim that could not be counted.** Where the study could not settle something the document says so.

## How this folder came to exist, and how it grows

Four exports were unpacked, inventoried, and read by one agent per slice; every finding was then re-checked by
a second agent whose only job was to refute it; the surviving material was rewritten domain-neutral and
scrubbed by a third pass that never saw the sources. The same procedure, as a prompt you can paste, is in
[INGEST-NEW-REFERENCE.md](INGEST-NEW-REFERENCE.md).

Grow this folder by **sharpening the existing documents**, not by adding one per project. A fifth delivery
should mostly change numbers — "3 of 4" becomes "4 of 5" — and occasionally overturn a rule. If ingesting a
project adds only a new file, it added nothing.
