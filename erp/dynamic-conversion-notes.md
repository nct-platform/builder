# The two ERP sample exports — what they demonstrate

**Domain note.** These two archives are a **sample domain** (a small manufacturing/distribution ERP), not the
frame of this library. Read them for the *mechanism*; substitute your own entities.

- **`initial_erp.mrjun`** — the sample project with a complete UI (pages, forms, crud tables, rules, one context
  listing the crud aliases) and a populated business schema in `project-db.dump`, but **no dynamic wiring**.
- **`dynamic.mrjun`** — the same project with the **dynamic-integration wiring added**, so it runs with **no
  compiled service** behind it: the business logic lives inside the project as SQL/Groovy over its own schema.

Together they are the worked example for [18](../18-existing-schema-to-dynamic-wiring.md) — "here is a populated
schema plus a UI; make it run dynamically".

## What the conversion actually added

Nothing in the existing UI changed. Only three things were added:

| Added | What it is |
|---|---|
| `rep-objects.sources[]` | one **INTERNAL** DB source pointing at the business schema inside the project DB |
| `dynamic-cruds.json` | one dynamic CRUD per business alias the UI already referenced |
| `rep-objects.queries[]` | the paired `crud_<alias>_<method>` queries the SQL methods run |

That is the whole shape of a static→dynamic conversion: the UI already speaks in `service.crud.<alias>.<method>`,
so all you owe it is a source, a CRUD per alias, and one query per SQL method.

## What each dynamic CRUD provides

- **The standard 7 methods** — `find` (GROOVY auto-find wrapper), `findAll`/`count`/`get`/`create`/`update`/
  `delete` (SQL).
- **FKs surfaced as nested objects** through the `__` alias convention (`j.id AS product__id` →
  `{product:{id,code,name}}`), so a table column `product.code` resolves.
- **Enum/lookup columns surfaced flat** next to their id, so a dropdown can show a label without a second call.
- **Soft vs hard delete per entity** — master data with an `active` flag deletes softly
  (`UPDATE … SET active=false`); documents delete hard, guarded by status.
- **Lifecycle actions** as plain SQL status transitions (`activate`/`post`/`cancel`/`approve`/`ship`/…). The
  literal written must be in the column's CHECK set.
- **Documents with line items** — `find`/`get` return a nested `lines` array (each line's FK `LEFT JOIN`ed so the
  sub-grid shows `code`/`name`, not raw ids); `create`/`update` are GROOVY methods orchestrating
  `createHeader`/`updateHeader` + `deleteLines` + per-line `insertLine`; `delete` clears the lines first.
- **The one tree CRUD** — `findByParent`/`findAllByParent`/`countByParent` filtering on
  `parent_id IS NOT DISTINCT FROM :parentId::uuid`, so `parentId = null` returns the roots.

Every one of those points is documented, with the SQL, in [18](../18-existing-schema-to-dynamic-wiring.md) and
[11](../11-business-logic-dynamic-crud.md).

## Read it as a wiring reference, not as a production ERP

Some deep multi-table side effects (stock postings, reservation rebucketing, auto goods receipts) are reduced to
their **primary visible effect** — the status or quantity change — rather than reimplemented. Standard CRUD,
master data, documents and simple status lifecycles are faithful.

## How to import

Import into a `type==REPORT` project with the business-logic integration deployed. On import the platform
restores the dump (recreating the business schema in the target DB), rebinds the INTERNAL source's database and
credentials to the target project, then applies `dynamic-cruds.json`, binding each CRUD to the live source and
creating the hidden Groovy rules for the GROOVY methods. Start from the bundled `empty` baseline — it is
REPORT-typed.
