# Adding a delivered project to this knowledge base

A reference project is worth ingesting when it did something none of the current entries did — a screen kind,
an orchestration shape, an access model, a way of handling scale. It is **not** worth ingesting because it is
new, large, or a customer you are proud of: a second delivery of a shape already covered adds noise, and the
next reader pays for it.

You need two things: the packed export (`project.mrjun`) and whatever the customer briefed you with (PRD, spec,
manual — any format). Put them anywhere; the prompt below takes the paths.

⛔ **The archive leaves again when the work is done.** These are live customer systems. They come in, they are
studied, the knowledge is written down domain-neutral, and the archive is deleted. Nothing customer-identifying
survives in this folder — no names, no PRD prose, no figures, no seed data, no domain vocabulary.

---

## The prompt

Paste this to the assistant, filling in the two paths and the one-line reason.

````
Ingest a new reference project into the builder knowledge base.

INPUT
- export:  <ABSOLUTE PATH>/project.mrjun
- brief:   <ABSOLUTE PATH>/prd/            (PRD / spec / manual, any format)
- why it is worth adding: <one line — the thing it does that A, B, C and D do not>

READ FIRST
- builder/references/README.md — the knowledge base you are extending, its A/B/C/D convention, and the
  ⛔ domain-neutral rule that governs every line you write
- builder/references/knowledge-graph.json — what is already known, so you add rather than repeat

PROCEDURE

1. UNPACK AND INVENTORY. `mrjun.py unpack` into a scratch dir (never into builder/). Run `inspect`, and count
   for yourself: pages, dynamic CRUDs and their methods, rules by type, queries, forms and form groups,
   workflows and whether each is deployed and reachable, schedulers and whether they are enabled, charts,
   nct.html.plugin nodes and how many are real studio components, role groups, locales, tables. Give the new
   project a letter (the next free one) and record its size signature.

2. READ THE BRIEF for WHY, not what. You want the forces that produced the shape — the question the customer
   could not answer, the constraint that decided the architecture. Never quote it; never carry its nouns
   forward.

3. STUDY IT AGAINST WHAT IS ALREADY KNOWN, slice by slice, using the existing documents as the checklist:
   solution shape · navigation and front door · CRUD conventions · forms, actions, validation · process and
   scheduling · security and roles · localization · charts and dashboards · studio components · visual design.
   For each slice ask three questions and answer them with counts, not impressions:
     - does this project CONFIRM a pattern already documented?  → raise its evidence ("3 of 4" → "4 of 5")
     - does it CONTRADICT one?                                  → say which way to jump now, and why
     - does it do something NEW?                                → new pattern, with the failure it avoids
   Read the library doc that governs each slice before judging it, and note where the doc is wrong or silent.
   Parallelise: one agent per slice, each writing a research file to the scratch dir.

4. NEUTRALISE BEFORE ANYTHING IS WRITTEN DOWN. Strip every industry noun, customer name, person, figure and
   seed value. Rename example entities to `document`/`documentLine`, `case`, `task`, `item`, `unit`, `partner`.
   Keep the SHAPE byte-exact — property slot names, JSON keys, Groovy/SQL/JS idioms, counts. A table called
   `<industry>_case` leaks as loudly as a sentence does.

5. UPDATE THE KNOWLEDGE BASE — edit the existing documents, do not append a new per-project file. A knowledge
   base grows by sharpening its rules, not by accumulating case studies. Then update
   `knowledge-graph.json`: new pattern nodes, corrected evidence counts, new edges to the library docs, and
   the new project's size signature in README.md.

6. VERIFY MECHANICALLY, THEN COLD. Build the forbidden-vocabulary list FROM THE EXPORT rather than from
   memory — tenant/realm/client strings, every CRUD alias and name, every `CREATE TABLE`/`CREATE SCHEMA`
   identifier in `project-db.dump`, and every content-node name in `branches.json`. Split those into tokens,
   drop the ones three or more unrelated projects share (they are platform vocabulary, not domain), and grep
   the changed files for what is left, plus every multi-word artefact name verbatim. Inspect each hit: a
   platform page name (`Audit Log`, `Business Logic`, `Form Groups`) stays, a domain noun goes. The result
   must be a list you have looked at line by line, not a zero you assumed. Then have a separate agent, which
   did not write the text, read it cold and answer: could someone rebuild this technique from the text alone,
   and can they tell what industry it came from? The answers must be yes and no.

7. HAND BACK a list of exactly what to delete, and say plainly what stops being verifiable once it is gone.
````

---

## What "studied" has to mean

The test is not that the document describes the project. It is that **an integrator who never saw the archive
can rebuild the technique from the text** — so every entry carries the slot names, the JSON shape, the code
skeleton and the failure it prevents. If a paragraph would still read as true after the archive is deleted but
could not be acted on, it is a summary, and summaries are what this knowledge base exists instead of.

Two habits keep it honest:

- **Count before you generalise.** One sighting is an anecdote, three are a convention, and a contradiction
  between two deliveries is a decision the reader must make consciously — say which way to jump and why.
- **Record what the deliveries do NOT do.** A library mechanism that four projects never used is a finding:
  either it is overspecified, or it is a trap. That knowledge is as useful as a pattern.
