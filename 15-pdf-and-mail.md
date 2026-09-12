# 15 — PDF templates, Mail templates, and the Groovy flow "generate PDF → send by email"

> 📐 **Field evidence — PDF and mail in production, including the font trap:** [07-localization.md](references/07-localization.md) · [05-process-and-scheduling.md](references/05-process-and-scheduling.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

## What it is / when to use

The platform can **generate PDFs from templates** and **send emails from HTML templates**, both directly from Groovy rules (`rep-objects.rules[]`, see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)). This is a separate, heavy subsystem to reach for when a project needs:

- an email to a user/role/role-group triggered by an event (registration, invitation, "intake created");
- a receipt/invoice/certificate as PDF built from CRUD data;
- "generate a PDF from a template → attach it to an email → send it to a recipient" in a single call.

The subsystem consists of **three layers**:

| Layer | Plugin / object | Where stored | Reconstructible from export? |
|---|---|---|---|
| **PDF templates** (authoring) | `report.pdf.templates.plugin` (editor page, pdfme) | DB of the **nct-pdf** service, table `pdf_templates` | **YES** — `rep-objects.pdfTemplates[]` (like mail templates); add via `pdftemplate add` |
| **PDF report (demo scaffold)** | `pdf.report.plugin` + `pdf.report.page.plugin` | content-tree in `branches.json` | Yes (these are page nodes) |
| **Mail templates** | `messaging.mail.templates.plugin` (editor page, GrapesJS) + object `rep-objects.mailTemplates[]` | **nct-messaging** DB `mail_templates`, **and exported** to `rep-objects.mailTemplates[]` | **YES** — mail templates are reconstructible |
| **Groovy API** | `service.report.pdf.*`, `service.notification.mail.*`, `service.notification.push.*` | proxy classes in **nct-executor** | — (this is runtime, not data) |

> ✅ **Key fact for building an export.** **PDF templates ARE part of `.mrjun`** — carried in `rep-objects.json` under a `pdfTemplates[]` list (of `PdfTemplateDto`), **exactly like mail templates** in `mailTemplates[]`. nct-ui (`CmsProjectServiceImpl`) exports them from the `nct-pdf` service DB (`pdf_templates`, `PdfTemplateEntity.java`) and, on import, saves each one back into nct-pdf via `PdfTemplateClient.save` under the target realm/client. So a PDF template **is** reconstructible from the export — add one with `mrjun.py pdftemplate add --alias <a> --name <s> --template @file.json` (it appends to `rep-objects.pdfTemplates[]`, created in nct-pdf on the next import). The template body itself is authored as a real **pdfme** JSON (`basePdf` + `schemas` with labels/values/tables); a bare scaffold renders blank. *(Older exports predating this feature have no `pdfTemplates` key — that's fine, it deserializes as an empty list.)* You can still create one manually via the browser authoring page or a REST POST, but that path is not portable.

---


# Part 0. Branding — templates must be POLISHED, not skeletal (READ FIRST)

Mail and PDF are the customer-facing face of the project. **A bare `<div>` email or a two-field PDF is a defect**
(`system_prompt.txt` Operating Principle 3). Two rules for every template you author:

**1. Match the quality of the STANDARD / SEED templates.** Do not hand-write a plain email or a blank pdfme
scaffold. START from a real one and re-skin it:
- **Mail:** copy the `htmlContent` of a stock template (e.g. `companyInvitation` — real structure below) and
  rewrite the text + `{{placeholders}}`, keeping its **table-based layout**: a centred 600px white card on a
  `#f4f6f9` page, a coloured **header band** with the logo, a body with a clear hierarchy, a call-to-action
  **button** (`<a>` styled as a button), and a muted **footer**. Inline all CSS (email clients strip `<style>`).
- **PDF:** copy the closest of the 15 pdfme SEEDS (§1.4) and re-skin — a header band with the logo `image` field,
  typographic hierarchy, rule lines, and a `table` field for any line items. Never ship the blank `scaffold`.

**2. BRAND it with the CUSTOMER's logo.** Get the logo in **Phase 0** (elicited — [19](19-build-decision-procedure.md)
/ `system_prompt.txt` Operating Principle 1): identify the customer from the PRD, find their logo on their website,
or ASK the user (a neutral placeholder mark is an acceptable fallback). Then embed it:

- **Simplest & self-contained — a `data:` URI** (no asset path to break on import; re-homes for free):
  - Mail: `<img src="data:image/png;base64,<...>" alt="<Customer>" height="40" style="display:block">` in the header band.
  - PDF: a pdfme `image` field whose `content` is the same `data:image/png;base64,<...>` string (field type `image`, §1.3).
- **Do NOT hand-author a `t/…` file-storage path for the logo — it is the one route that silently 404s.** A file
  you ship in `tenant-files/<relpath>` is re-homed on import to `t/<tenantId>/<relpath>`, where `<tenantId>` is a
  **number the platform assigns at import time** ([23](23-distribution-and-known-gaps.md) §1); the other shape,
  `t/<realm>-<client>/mail-templates/<file>`, only ever exists for images the **platform itself** uploaded. Either
  way the `src` you typed points at a path nothing ever wrote, and at send time it is expanded verbatim
  (`src="t/…"` → `<storage-url>/t/…`, `MailTemplateImageService`), so the recipient gets a broken image and
  nothing offline can catch it. The `data:` URI above is self-healing instead: **saving** a mail template — which
  the import does for every `mailTemplates[]` entry — uploads the inline bytes to
  `t/<realm>-<client>/mail-templates/<uuid>.png` and rewrites the `src` to that path for you. Convert an SVG logo
  to PNG first (email/pdfme want a raster) and keep it small — email clients cap total message size.
  (`mrjun.py asset add <relpath> <localfile>` is for assets referenced **relative** to the tenant root, i.e.
  HTML-Studio libraries — [24](24-html-component-studio.md) — not for mail or PDF logos.)

If you cannot obtain any logo, **ASK** — do not ship un-branded and do not silently drop the header. Localize the
template per **recipient locale** by shipping one template alias per locale (mail templates have no per-locale
field — §3.2; [20](20-localization.md)); the `mail-defect-sender`-style verbatim bodies stay verbatim.

**Copyable branded mail skeleton** (re-skin the colours to the customer; drop in the logo + your body):

```html
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;"><tr>
  <td align="center" style="padding:40px 20px;">
   <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:8px;overflow:hidden;">
    <tr><td bgcolor="#0b2e59" style="background:#0b2e59;padding:28px 40px;text-align:center;">
      <img src="data:image/png;base64,REPLACE_WITH_LOGO" alt="{{customer}}" height="40" style="display:block;margin:0 auto 8px;">
      <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">{{title}}</h1></td></tr>
    <tr><td style="padding:32px 40px;color:#333;font-size:15px;line-height:1.6;">
      <p style="margin:0 0 16px;">{{body}}</p>
      <p style="text-align:center;margin:28px 0;"><a href="{{link}}" style="background:#0b2e59;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:600;display:inline-block;">{{cta}}</a></p></td></tr>
    <tr><td style="padding:20px 40px;background:#f4f6f9;color:#8a94a6;font-size:12px;text-align:center;">{{footer}}</td></tr>
   </table></td></tr></table></body></html>
```

---

# Part 1. PDF templates (`report.pdf.templates.plugin`)

## 1.1 Authoring plugin

The `report.pdf.templates.plugin` page is an admin page with a list of PDF templates and an editor built on **pdfme** (`@pdfme/ui@6.1.2`, loaded from `https://esm.sh/`, `PdfTemplateEditorPanel.java`). In the `empty` scaffold it is already present: a top-level `siteMapPage` **"Pdf Templates"** (`identifier: f443980f-a7d9-4ddd-86de-13870ac3c89d`), inside which sits a single plugin node:

```json
{
  "id": "29891beb-6e8d-45f0-8f8e-5dd098078bcc",
  "identifier": "4b0f178d-31c5-4ade-9606-2a024f29bb49",
  "name": "Pdf Templates",
  "pluginName": "report.pdf.templates.plugin",
  "order": 0,
  "children": [],
  "properties": { "className": {…}, "styleName": {…}, "tagProperties": {…} }
}
```
*(source: `empty/branches.json`, `jq '.. | select(.pluginName=="report.pdf.templates.plugin")'`)*

The plugin node has **neither** `settings` nor a `model` with its own configuration — all the work is done through the `PdfTemplateService`, which talks to nct-pdf. The slots are just the base ones (`className`/`styleName`/`tagProperties`). In other words, **the node itself "configures" nothing**: it merely renders the CRUD list of templates.

## 1.2 PDF template DTO (`PdfTemplateDto`)

`PdfTemplateDto.java` + entity `PdfTemplateEntity.java`:

| Field | Type | Meaning | Required | Validation (in the editor) |
|---|---|---|---|---|
| `name` | `String` | Display name. **Unique** per (realm, client). | yes | `RequiredTextField` + name-uniqueness check (`PdfTemplateEditorPanel.java`); unique-index `idx_pdf_template_name` |
| `alias` | `String` | Technical alias — **Groovy calls the template by it** (`service.report.pdf.get.<alias>`). Unique. | yes | `RequiredTextField` + `PatternValidator("^[a-z][a-zA-Z0-9]*$")` + alias-uniqueness check; unique-index `idx_pdf_template_alias` |
| `description` | `String` | Description (`TEXT`). | no | — |
| `active` | `Boolean` | Whether the template is active (defaults to `true`; on "Create new template" it is set to `active(true)`, `PdfTemplatesPlugin.java`). | no | `CheckBox` |
| `templateJson` | `String` | **The entire pdfme template** as a JSON string (`{ basePdf, schemas }`). Stored in `TEXT`. | yes (otherwise there is nothing to render) | `TextArea("templateJson")` |
| `fields` | `List<PdfFieldInfo>` | Placeholder fields (name+type) extracted from `templateJson`. Populated on the nct-pdf side (`PdfFieldExtractor`), in the `jsonb` column `fields`. | generated | — |
| `previewImage` | `String` | Preview (data-URI / path). | no | — |

Base fields from `AbstractSecuredDto`: `id`, `identifier`, `realmName`, `clientName`, `creationTime`, `modificationTime`, `active`.

## 1.3 Structure of `templateJson` (pdfme)

`templateJson` is a standard **pdfme Template**: an object `{ "basePdf": <object|base64>, "schemas": [ [field, field, …] ] }`, where `schemas` is an array of **pages**, each page an array of fields. **Multi-page**: `schemas` may hold more than one page; the editor supports add/duplicate/remove page (`PdfTemplateEditorPanel.js`). All 15 seeds are single-page (`[[ … ]]`). A real example from the seed template `pdftemplates/09-business-card.json`:

```json
{
  "basePdf": { … },
  "schemas": [
    [
      { "name": "leftBar", "type": "rectangle", "position": {"x":0,"y":0}, "width":4, "height":55,
        "rotate":0, "opacity":1, "color":"#2980ba", "borderColor":"#2980ba", "borderWidth":0 },
      { "name": "logo",    "type": "image", … },
      { "name": "company", "type": "multiVariableText", … },
      { "name": "name",    "type": "multiVariableText", … },
      { "name": "title",   "type": "multiVariableText", … },
      { "name": "divider", "type": "line",  … },
      { "name": "contact", "type": "multiVariableText", … },
      { "name": "qr",      "type": "qrcode", … }
    ]
  ]
}
```

Each field with a `name` becomes a **placeholder** that is filled at render time via `params` (see the Groovy flow below).

**The authoritative field-type set is the renderer's plugin map** (`nct-pdf/.../index.mjs`) — a type absent from that map does not render. It registers: `text`, `multiVariableText`, `image`, **`svg`**, `line`, `rectangle`, **`ellipse`**, `table`, the temporal/choice types `date`, `time`, `dateTime`, `checkbox`, `radioGroup`, `select`, and the 12 barcodes `qrcode`, `japanpost`, `ean13`, `ean8`, `code39`, `code128`, `nw7`, `itf14`, `upca`, `upce`, `gs1datamatrix`, `pdf417`. The editor exposes `svg`/`ellipse` in its palette (`PdfTemplateEditorPanel.js`).

- ⚠️ **`list` does NOT render.** `HintsService`/`resolveInputs` acknowledge a `list` type (it is JSON-serialized like `multiVariableText`), but **no `list` plugin is registered in the renderer** (`index.mjs` — the only `list` match is `fastify.listen`). A `list` field fails to render. Prefer `table`.
- ⚠️ **Shapes take no `params`.** `line`, `rectangle`, `ellipse` are valid **schema** types but the field extractor **skips them** (`PdfFieldExtractor.java` `SHAPE_TYPES`, returns `null`), so they never appear in `fields` and take no render-time value — they are pure decoration baked into `templateJson`.

`PdfFieldInfo` (`nct-transfer/.../pdf/PdfFieldInfo.java`): `name`, `type`, `description`, `options` (for select/radio), `columns` (for table), `variables` + `variableDefaults` (for multiVariableText), `readOnly`, `content` (default value), `sampleRows` (for table).

> ⚠️ **`fields` is server-derived — never hand-author it.** On every save the nct-pdf side re-extracts `fields` from `templateJson` (`PdfTemplateServiceImpl.java`) and re-extracts again on read, so a `fields` array you write is overwritten. Author only `basePdf` + `schemas`. (`previewImage` is a passthrough column — client-supplied, currently unpopulated by the server; not server-derived.)

### ⛔ `fontName` — the renderer has exactly ONE font, and a wrong name kills the whole render

`nct-pdf` renders through an embedded Node sidecar that calls pdfme's
`generate({ template, inputs, plugins, options })` and **never passes `options.font`**
(`nct-pdf/.../index.mjs`). pdfme therefore falls back to its built-in default font map, which
holds a single entry — **`Roboto`**. So a field's `fontName` may only ever be:

```json
"fontName": ""          // ✅ the default (Roboto) — what all 15 seeds in pdftemplates/ use
"fontName": "Roboto"    // ✅ the same thing, named
"fontName": "<anything else>"   // ⛔ 422, and NO PDF AT ALL
```

The failure is total, not cosmetic — no fallback glyphs, no partial page. The Groovy action that asked for
the PDF fails with it:

```
[422] during [POST] to [.../api/pdf-templates/internal/tenant/…/render]:
{"error":"[@pdfme/schemas] Font \"NotoSerifJP-Bold\" is not found."}
```

**Why this bites specifically.** The pdfme **Designer** (and every playground/export built on it) writes
`NotoSerifJP-Regular` and `NotoSerifJP-Bold` into every text field it produces, and previews them happily,
because the designer registers those fonts and the server does not. A template authored or exported there
looks finished and renders nowhere. Clear the font names before shipping it — or start from a seed in
[`pdftemplates/`](pdftemplates/), all of which are already `""`.

**Two consequences to design around, not to work around:**

1. **There is no bold.** pdfme does not synthesise weights: bold is a separate registered face, and none is
   registered. Emphasis in a PDF layout must come from **font size, colour, or a filled background** —
   which is what the seed templates do (a heading is bigger and white-on-navy, not "bold").
2. **A `table` schema carries its own font names**, in `headStyles`, `bodyStyles` and `columnStyles`, in
   addition to the field-level one. That is the half people miss: the text fields get cleaned and the table
   still names a font, and the render still 422s.

`mrjun.py validate` ERRORs on any `fontName` in `rep-objects.pdfTemplates[]` that is neither `""` nor
`Roboto` (`_check_pdf_template_fonts`), field-level and table-style alike.

## 1.4 Standard (seed) templates

The editor has a "load standard template" button. The list comes from nct-pdf via `PdfTemplateService.getStandardTemplateNames/getStandardTemplate` (`PdfTemplateEditorPanel.java`; the service is `nct-ui/.../service/PdfTemplateServiceImpl.java`). The templates themselves are 15 JSON files in `pdftemplates/` (`01-invoice-classic` … `15-name-tag`). These are ready-made pdfme `templateJson`s you can use as a starting point.

**To build a document PDF, COPY the closest seed file, don't author from a blank canvas.** ✅ **All 15 seeds ship with this library** in `doc/builder/pdftemplates/` — the same files the platform serves, so you can copy one, rename its fields and `pdftemplate add` it without any access to the platform codebase. (They are also reachable in a running instance from the editor's "Standard Templates" dropdown.) If you need a table of line items, start from a seed whose `has_table` shape you can see below — `01-invoice-classic`, `02-quotation`, `03-receipt-thermal`, `07-packing-slip`, `10-delivery-note` and `11-meeting-agenda` all carry a real `table` field.

| Seed file | Best fit for |
|---|---|
| `01-invoice-classic.json` | invoice, bill |
| `02-quotation.json` | quote, estimate, offer |
| `03-receipt-thermal.json` | receipt (POS/thermal) |
| `04-certificate.json` | certificate, diploma, award |
| `05-business-letter.json` | letter, formal notice |
| `06-report-cover.json` | report cover page |
| `07-packing-slip.json` | packing slip |
| `08-shipping-label.json` | shipping/address label |
| `09-business-card.json` | business card |
| `10-delivery-note.json` | delivery note, waybill |
| `11-meeting-agenda.json` | agenda, minutes |
| `12-employee-id.json` | employee ID / badge |
| `13-event-ticket.json` | ticket, pass |
| `14-product-label.json` | product/price label |
| `15-name-tag.json` | name tag |

Recipe: copy the closest file, **rename its field `name`s** (and, for `multiVariableText` fields, the inner `variables` — see 1.3) to your own placeholders, save it as `file.json`, then ship it into the project with `mrjun.py pdftemplate add --alias <a> --name <s> --template @file.json` (it lands in `rep-objects.pdfTemplates[]` and is created in nct-pdf on import — see 1.5). `mrjun.py pdftemplate scaffold` is the **from-empty** alternative (a blank pdfme JSON you then flesh out) when no seed is close.

> ⛔ **`pdftemplate scaffold` output is a BARE SKELETON — it renders near-EMPTY, do NOT ship it as-is.** It emits
> only your named fields **stacked in a column with NO `content`, NO static labels, and NO design** (borders,
> title, table). A dynamic field with no param and no `content` prints blank, so a "template" made only of
> value-fields looks empty in the viewer — a real complaint. **A usable PDF template needs three things the raw
> scaffold lacks:** (1) **static-label text fields** — `{type:"text", content:"Customer", name:"lblCustomer"}`
> whose `name` is NOT a param key, so the label always shows (the render params only override the fields whose
> `name` matches a key); (2) **layout** — positioned `rectangle`/`ellipse` frames + a header/title, real
> `position`/`width`/`height`/`fontSize` per field (copy the numbers from the closest seed); (3) a **`table`
> field** for any list (`{type:"table", head:[…], headWidthPercentages:[…], content:"[[…]]"}` — the Groovy
> passes the rows as that param). **Either copy the closest seed and adapt it (preferred), or hand-author the
> full field list** (labels + values + shapes + table). Verify by rendering once — a template that's all
> value-fields is the tell.

### 1.4.1 Default templates — real structure

There is no single "default template" file — there are **three** distinct defaults, and to run the "copy a seed and rename" recipe you must see the real field shapes.

**(1) The editor's blank template** — what "Create new template" opens (the pdfme Designer is seeded with this when `templateJson` is empty), `PdfTemplateEditorPanel.js` (also):

```json
{ "basePdf": { "width": 210, "height": 297, "padding": [10, 10, 10, 10] }, "schemas": [[]] }
```

**(2) The `mrjun.py pdftemplate scaffold` default** (`tools/mrjunkit/pdf_cmds.py`: `_A4_BASE`, `sampledata` emitted via `_sampledata_for`) — same A4 blank base, one `title` text field, plus a top-level `sampledata` row **that the seeds do NOT have** (harmless — `generate` takes `inputs` separately and ignores `sampledata`, see gotcha 12):

```json
{
  "basePdf": { "width": 210, "height": 297, "padding": [10, 10, 10, 10] },
  "schemas": [[ { "name": "title", "type": "text", "position": {"x":10,"y":20}, "width":90, "height":8,
                 "rotate":0, "alignment":"left", "verticalAlignment":"top", "fontSize":12, "lineHeight":1,
                 "characterSpacing":0, "fontColor":"#000000", "backgroundColor":"", "opacity":1,
                 "content":"title" } ]],
  "sampledata": [ { "title": "title" } ]
}
```

**(3) The 15 seed templates** (`pdftemplates/01-invoice-classic.json` … `15-name-tag.json`) — the real "default templates", served by `StandardPdfTemplateService` (sorted by filename) and offered in the editor's "Standard Templates" dropdown (`PdfTemplateEditorPanel.js`, which strips the `NN-` ordering prefix for display). Their genuine structure, verbatim:

**`basePdf` is always the blank-object form (millimetres), never base64** — e.g. `09-business-card.json`:

```json
"basePdf": { "width": 85, "height": 55, "padding": [4, 4, 4, 4] }
```

**A full `text` field** (`03-receipt-thermal.json`):

```json
{ "name": "storeName", "type": "text", "content": "DOKIE STORE",
  "position": { "x": 5, "y": 8 }, "width": 70, "height": 8, "rotate": 0,
  "alignment": "center", "verticalAlignment": "middle", "fontSize": 14, "lineHeight": 1,
  "characterSpacing": 0, "fontColor": "#000000", "backgroundColor": "", "opacity": 1, "fontName": "" }
```

**A full `multiVariableText` field — the triad `text` / `content` / `variables`** (`14-product-label.json`). Note `text` uses **single-brace** `{var}` placeholders (the extractor's regex is `\{(\w+)}`, `PdfFieldExtractor.java` — NOT `{{…}}`); `content` is a **JSON string of the default values**; `variables` is the array of names (`PdfFieldExtractor.java`):

```json
{ "name": "footer", "type": "multiVariableText",
  "position": { "x": 2, "y": 35 }, "width": 56, "height": 4, "rotate": 0,
  "alignment": "center", "verticalAlignment": "middle", "fontSize": 6, "lineHeight": 1,
  "characterSpacing": 0, "fontColor": "#888888", "backgroundColor": "", "opacity": 1, "fontName": "",
  "text": "Batch: {batch}  Exp: {expiry}",
  "content": "{\"batch\":\"B-2026-0517\",\"expiry\":\"2027-05-17\"}",
  "variables": ["batch", "expiry"] }
```

→ at render, the `params` key is the **field name** `footer` and its value is a **Map of the inner variables** — `footer: [batch: "B-2026-0517", expiry: "2027-05-17"]` (serialized to the JSON string pdfme reads; see §4.1 and §4.9).

**A full `table` field — `content` is a JSON-stringified 2-D array** (`03-receipt-thermal.json`, abbreviated to the load-bearing keys):

```json
{ "name": "items", "type": "table", "position": {"x":5,"y":53}, "width":70, "height":60,
  "showHead": true, "head": ["Item", "Qty", "Price"], "headWidthPercentages": [55, 15, 30],
  "tableStyles": { "borderWidth": 0, "borderColor": "#000000" },
  "headStyles": { "fontSize": 8, "alignment": "left", "borderWidth": {"top":0,"right":0,"bottom":0.2,"left":0}, "padding": {"top":2,"right":2,"bottom":2,"left":2} },
  "bodyStyles": { "fontSize": 8, "alignment": "left" },
  "columnStyles": { "alignment": { "0": "left", "1": "center", "2": "right" } },
  "content": "[[\"Coffee\",\"2\",\"6.00\"],[\"Sandwich\",\"1\",\"8.50\"],[\"Cookie\",\"3\",\"4.50\"]]" }
```

→ `head` becomes the field's `columns`; at render, `params` accepts `items: [["Coffee","2","6.00"], …]` (positional) **or** `items: [[Item:"Coffee", Qty:"2", Price:"6.00"], …]` (keyed by column) — see §4.9.

**A full barcode field** (`03-receipt-thermal.json`; also `code128` in `12-employee-id.json`) — `content` is the encoded string, `barColor` the ink:

```json
{ "name": "qr", "type": "qrcode", "content": "https://dokie.example/r/R-2026-0001",
  "position": {"x":27,"y":160}, "width":26, "height":26, "rotate":0, "opacity":1,
  "backgroundColor": "", "barColor": "#000000" }
```

→ a barcode `params` value is a plain **String** (`qr: "https://…"`).

**Which seed has what** (verified by reading the files): every seed's `basePdf` is the `{width,height,padding}` object (none base64); `image` appears in `01`,`02`,`05`,`06`,`07`,`09`,`10`,`12`; the canonical `table` is `03-receipt-thermal`; barcodes — `12-employee-id` has `qrcode`+`code128`, `14-product-label` has `ean13`, `15-name-tag` has `qrcode`; `multiVariableText` appears in nearly all.

## 1.5 How to create a PDF template "from scratch"

> ✅ **PDF templates ARE carried in the `.mrjun`** — `rep-objects.json` has a `pdfTemplates[]` list (of
> `PdfTemplateDto`) that nct-ui exports (from nct-pdf) and imports (saves back into nct-pdf via
> `PdfTemplateClient.save`), **exactly like mail templates** (`CmsProjectServiceImpl`). **So the PORTABLE way to
> ship one is `mrjun.py pdftemplate add --alias <a> --name <s> --template @file.json`** → it appends the template
> to `rep-objects.pdfTemplates[]`, and the next project import creates it in nct-pdf (verify on
> `…/pdf-templates`). The three manual paths below are only for a **one-off load into a RUNNING nct-pdf without
> re-importing** — DON'T reach for a direct DB insert as a routine step (it's the no-browser-token fallback: the
> `save` REST is `@PreAuthorize("isAuthenticated()")`).

Beyond the **portable `rep-objects.pdfTemplates[]` path above** (the recommended way to ship a template inside a
`.mrjun`), a template can also be created/loaded **directly into a running nct-pdf** (one-off, not routine
authoring). The options are:

1. **Via the browser (the standard path).** Open the "Pdf Templates" page → "Create new template" → lay out the fields in the pdfme editor → set `name`, `alias` (`^[a-z][a-zA-Z0-9]*$`), save. The plugin calls `pdfTemplateService.save(realm, client, dto)` (`PdfTemplatesPlugin.java`), and the record lands in `pdf_templates` in the nct-pdf DB.

2. **Via REST** (the nct-pdf service, controller `PdfTemplateController.java`) — `POST /api/pdf-templates/tenant/{realm}/{client}/save` with a `PdfTemplateDto` body. **Save is create-or-update** — there is no separate create endpoint; it upserts by id, enforcing the name/alias unique indexes. Related paths: render at `POST …/tenant/{realm}/{client}/render`, the seed list at `GET …/tenant/{realm}/{client}/standard/names` and one seed's JSON at `…/standard/{name}`. Body shape (`templateJson`):
   ```json
   {
     "name": "Intake Receipt",
     "alias": "intakeReceipt",
     "description": "Receipt for a completed intake",
     "active": true,
     "templateJson": "{\"basePdf\":{...},\"schemas\":[[{\"name\":\"customerName\",\"type\":\"text\",...},{\"name\":\"total\",\"type\":\"text\",...}]]}"
   }
   ```
   You can take `basePdf`+`schemas` from any seed file `pdftemplates/*.json`, renaming the fields to your own placeholders.
3. **Direct DB insert** (turnkey / bulk / no browser token). PDF templates live in the nct-pdf DB — table
   **`nct_pdf.pdf_templates`** (DB `dokie`, `currentSchema=nct_pdf`; `PdfTemplateEntity.java`). Not-null
   columns: `id`, `identifier` (both any UUID string), `realm_name`, `client_name`, `name`, `alias`, `active`,
   `creation_time`, `modification_time`; the pdfme JSON goes in **`template_json`** (TEXT); `fields`
   (jsonb)/`description`/`preview_image` may be null. The unique keys are `(realm_name, client_name, name)` and
   `(realm_name, client_name, alias)` — `DELETE … WHERE realm_name=… AND client_name=… AND alias=…` first for
   idempotency. Example (one template):
   ```sql
   INSERT INTO nct_pdf.pdf_templates
     (id, identifier, realm_name, client_name, name, alias, active, template_json, creation_time, modification_time)
   VALUES (gen_random_uuid()::text, gen_random_uuid()::text, '<realm>', '<client>',
     '<Entity> Certificate', '<entity>Certificate', true, '<the pdfme JSON, single-quotes doubled>', now(), now());
   ```
   Run via `psql -h <host> -U <user> -d <platform-db> -f inserts.sql` (substitute your own host / database /
   credentials — if the platform runs in a container, exec into it first). Then refresh the "Pdf
   Templates" page to confirm the rows appear. (`realm_name`/`client_name` are the TARGET project's — the
   realm/client the `.mrjun` was imported into, **not** whatever pair the source export happened to carry.)

> 🔧 **Tooling.** **Mail templates** — `mrjun.py mailtemplate add --name <s> --subject <s> --html @f|str [--alias <s>] [--placeholder <p>]...` / `mailtemplate list` / `mailtemplate rm` (placeholders `{{...}}` are auto-scanned from html+subject; Cyrillic/Armenian are preserved). **PDF templates are ALSO exportable** (`rep-objects.pdfTemplates[]`) — `mrjun.py pdftemplate add --alias <a> --name <s> --template @file.json [--desc <s>]` appends a **real pdfme template** (authored/copied from a seed) so it is created in nct-pdf on import; `pdftemplate scaffold <alias> --out <file.json> [--field name:type]...` writes a **blank** pdfme JSON to flesh out first; `pdftemplate note` prints guidance. In Step-2, adding a PDF template is a normal build step (`pdftemplate add`), and the Groovy rule references its `alias`. Full index — [tools/README.md](tools/README.md).

---

# Part 2. PDF report `pdf.report.plugin` / `pdf.report.page.plugin` (demo scaffold)

This is a **separate, legacy scaffold** (it does not overlap with the pdfme templates from Part 1). ⚠️ **It is
no longer shipped**: the current `initialtemplates/empty.mrjun` has no `reports` page and no `pdf.report.*` node.
Older exports carry it as a demo on the page **`Home → reports → Pdf`**: a container node `html.plugin("Layout")`
contains a `pdf.report.plugin` with `identifier="pdf"`, and inside it a `pdf.report.page.plugin` with
`identifier="page-1"`. This is the "PDF report page" construct of the old mrjun report engine. It is documented
here so you can RECOGNISE it in an inherited project — never author a new one.

Shape of the `pdf.report.plugin` node (a real node from an older `empty/branches.json`):

```json
{
  "id": "b24613c8-22ed-481f-bd46-03f9cfe537fb",
  "identifier": "pdf",
  "uniqueIdentifier": "1ce2f2b4-bda7-45b0-9f06-51fe51f5f5e0",
  "name": "pdf",
  "pluginName": "pdf.report.plugin",
  "isBehaviour": false, "active": true, "order": 0,
  "properties": {
    "className":  { "propertyType":"STRING",  "stringValue":"" },
    "isParsis":   { "propertyType":"BOOLEAN", "booleanValue":false },
    "layout":     { "propertyType":"STRING",  "stringValue":"portrait",
                    "arguments":{ "choices":"[\"portrait\",\"landscape\"]" } },
    "pagesCount": { "propertyType":"INTEGER", "intValue":1 },
    "reuseItems": { "propertyType":"BOOLEAN", "booleanValue":false },
    "size":       { "propertyType":"STRING",  "stringValue":"A4",
                    "arguments":{ "choices":"[\"A1\",\"A2\",\"A3\",\"A4\",\"A5\"]" } },
    "styleName":  { "propertyType":"STRING",  "stringValue":"" },
    "tagProperties": { "propertyType":"STRING", "stringValue":"" }
  },
  "children": [ { "identifier":"page-1", "pluginName":"pdf.report.page.plugin", … } ]
}
```

Meaningful property slots of this node (all are direct typed properties, **not** a JSON string in `settings`):

| Slot | Type | Values | Meaning |
|---|---|---|---|
| `layout` | STRING (dropdown) | `portrait` \| `landscape` | Page orientation. |
| `size` | STRING (dropdown) | `A1`..`A5` | Sheet size. |
| `pagesCount` | INTEGER | `1` | Number of report pages. |
| `reuseItems` | BOOLEAN | `false` | Reuse of elements. |
| `isParsis` | BOOLEAN | `false` | Participation in the parsis mechanism (see [01-content-model-and-pages.md](01-content-model-and-pages.md)). |

`pdf.report.page.plugin` (`page-1`) has **the same set of slots**. Inside `page-1` you place ordinary content nodes (text/tables), which the old engine lays out onto the PDF.

> ⚠️ **UNVERIFIED (plugin class).** The classes `pdf.report.plugin` / `pdf.report.page.plugin` are **not found** anywhere in the platform sources (verified by search; the string is not found in the inspected jars either). Likely plugins from an mrjun dependency, but the jar provenance is not confirmed. The node shape above is **verified against real exports** and is identical in every one of them; the engine behavior cannot be reconstructed from the data.

**Recommendation for building a project:** to generate PDFs in a new (dynamic) project **use pdfme templates (Part 1) + the Groovy API (Part 3)**, not this legacy scaffold. Keep `pdf.report.plugin` as is on the `reports/Pdf` demo page (or delete it together with the page if you don't need the demo). Do not create new `pdf.report.plugin` nodes by hand — the engine is undocumented.

---

# Part 3. Mail templates (`messaging.mail.templates.plugin` + `rep-objects.mailTemplates[]`)

## 3.1 Authoring plugin

The `messaging.mail.templates.plugin` page is an admin CRUD for mail templates with a **visual HTML editor, GrapesJS** (`MailTemplateEditorPanel.java`, preset `grapesjs-preset-newsletter`). In the `empty` scaffold it is a top-level `siteMapPage` **"Mail Templates"**. The plugin node, like the PDF one, has only base slots (`className`/`styleName`/`tagProperties`) — the whole configuration lives not in the node but in the `mailTemplates[]` objects.

## 3.2 The `rep-objects.mailTemplates[]` object — full shape

**Like PDF templates, mail templates are exported** into `rep-objects.json` in the `mailTemplates[]` array (key `mailTemplates`). The `empty` baseline ships **5 templates**: `Company Invitation`, `Event Reminder`, `Password Recovery`, `sendIntakeInit`, `User Registration` (`jq '.mailTemplates | length'` → `5`). **Four** of those (`companyInvitation`, `eventReminder`, `passwordRecover`, `userRegistration`) are the auto-seeded **system** templates that exist in every project — deleting one from the export is pointless (the import re-creates it, §3.6), and your own templates must not reuse their names or aliases (§3.5). Only `sendIntakeInit` is a baseline extra.

The full object (the baseline's `sendIntakeInit`, the most compact one):

```json
{
  "id": null,
  "identifier": "28b15560-5da6-4c17-8059-0d8f9b663ee3",
  "realmName": "<realm>",
  "clientName": "<client>",
  "name": "sendIntakeInit",
  "alias": "sendIntakeInit",
  "subject": "Intake Init",
  "description": "Intake Init",
  "active": true,
  "placeholders": ["firstName", "lastName"],
  "htmlContent": "<body style=\"box-sizing: border-box; margin: 0;\">…Hi {{firstName}} {{lastName}},…</body>",
  "cssContent": "* { box-sizing: border-box; } body {margin: 0;}#itl3k{width:79px;height:78px;}",
  "gjsData": "{\"dataSources\":[],\"assets\":[{\"type\":\"image\",\"src\":\"t/<realm>-<client>/mail-templates/4c8d52c8-….png\",…}],\"styles\":[…],\"pages\":[…]}",
  "message": null,
  "errors": null,
  "creationTime": "…",
  "modificationTime": "…"
}
```

Fields (`MailTemplateDto.java` + entity `nct-messaging/.../MailTemplateEntity.java`):

| Field | Type | Meaning | Required | Validation (in the editor) |
|---|---|---|---|---|
| `name` | `String` | Display name. Unique per (realm, client). | yes | `RequiredTextField` + uniqueness (`MailTemplateEditorPanel.java`) |
| `alias` | `String` | **Technical alias — Groovy sends the email by it** (`service.notification.mail.<alias>`). Unique. | yes | `RequiredTextField` + `PatternValidator("^[a-z][a-zA-Z0-9]*$")` + uniqueness |
| `subject` | `String` | Default email subject. May contain `{{placeholder}}` (e.g. `"You've been invited to {{companyName}}"`). | no | `TextField("subject")` |
| `description` | `String` | Description. | no | `TextArea` |
| `active` | `Boolean` | Whether it is active (defaults to `true`; "Create new template" → `active(true)`, `MailTemplatesPlugin.java`). | no | `CheckBox` |
| `htmlContent` | `String` | **The final HTML of the email body** with `{{name}}` placeholders. This is exactly what is rendered + the placeholders are substituted. | yes | `TextArea("htmlContent")` |
| `cssContent` | `String` | CSS extracted by GrapesJS. | no | `TextArea("cssContent")` |
| `gjsData` | `String` | The internal GrapesJS project JSON (to re-open in the editor): `{dataSources, assets, styles, pages, …}`. When sending it is **not used** — `htmlContent` is sent. | no | `TextArea("gjsData")` |
| `placeholders` | `List<String>` | List of placeholder names the template expects (for Groovy hints and as an insertion example). | no, but needed for UX | filled automatically from `{{…}}` |

Base fields from `AbstractSecuredDto`: `id` (`null` in the export — linked by `identifier`), `identifier`, `realmName`, `clientName`, `creationTime`, `modificationTime`; plus the transport fields `message`, `errors` (always `null` in the export).

Placeholders of the baseline's templates (the four auto-seeded system ones + the extra `sendIntakeInit`) — list
your own with `jq -r '.mailTemplates[] | "\(.alias): \(.placeholders)"' rep-objects.json`:

```
companyInvitation: ["firstName","companyName","invitationLink"]
eventReminder:     ["guestName","eventName","eventTime","location","eventLink"]
passwordRecover:   ["firstName","resetLink"]
sendIntakeInit:    ["firstName","lastName"]
userRegistration:  ["firstName","activationLink"]
```

## 3.3 How placeholders get into the email

In `htmlContent` (and `subject`) placeholders are written as `{{name}}`. Example from the real `sendIntakeInit.htmlContent`:

```html
<h2 id="idk8a" …>Hi {{firstName}} {{lastName}},</h2>
<p id="i9b3n" …>You did intake init</p>
```

When sending, Groovy passes a `Map<String,String> placeholders` whose values are substituted into `{{firstName}}`, `{{lastName}}`. Localization here is done at the level of separate templates (its own alias per locale); a `localizedStringValue`/multilanguage field is **absent** in `MailTemplateDto` itself (unlike form controls).

## 3.4 How to create a mail template "from scratch" (in the export)

A mail template **is reconstructible** — it is added as an element of `rep-objects.mailTemplates[]`. Recipe:

1. Take any stock object as a skeleton (e.g. `sendIntakeInit` from the baseline's `rep-objects.json`).
2. Set `id: null`, a fresh `identifier` (uuid4), the project's `realmName`/`clientName`.
3. `name` (unique), `alias` (`^[a-z][a-zA-Z0-9]*$`, unique) — Groovy will call it by alias.
4. `subject` (may contain `{{…}}`), `description`, `active: true`.
5. `htmlContent` — the body HTML with `{{placeholder}}`. The easiest way is to take the `htmlContent` of a stock template and rewrite the text/placeholders. Image assets (logo) in the baseline's `sendIntakeInit` live at `t/<realm>-<client>/mail-templates/<uuid>.png` — that path is written **by the platform** when it processes an inline `data:` image on save, so do not copy or invent a `t/…` `src`: ship your own logo as a `data:` URI (Part 0) or drop the `<img>`.
6. `cssContent` — minimal (`* { box-sizing: border-box; } body {margin: 0;}`) or copy it from the skeleton.
7. `gjsData` — you can leave it `"{}"`, `null`/omit it, or copy it from the skeleton; it does not affect sending (only `htmlContent` matters). The `mailtemplate add` command leaves it `null`. Without valid `gjsData`, the visual editor will simply open the email as "raw" HTML.
8. `placeholders` — list all `{{…}}` occurring in `htmlContent`/`subject` so the Groovy hints know about them.

A minimal valid object:

```json
{
  "id": null,
  "identifier": "11111111-2222-3333-4444-555555555555",
  "realmName": "<realm>",
  "clientName": "<client>",
  "name": "Invoice Issued",
  "alias": "invoiceIssued",
  "subject": "Invoice {{invoiceNo}} is ready",
  "description": "Notify a counterparty that an invoice has been issued",
  "active": true,
  "placeholders": ["firstName", "invoiceNo", "dueDate"],
  "htmlContent": "<body><h2>Hi {{firstName}},</h2><p>Invoice <b>{{invoiceNo}}</b> is attached; payment is due on {{dueDate}}.</p></body>",
  "cssContent": "* { box-sizing: border-box; } body { margin: 0; }",
  "gjsData": "{}"
}
```

> 🔧 **Tooling.** Faster than by hand is a command (see the 🔧 Tooling callout at the end of Part 1 and [tools/README.md](tools/README.md)): `mrjun.py mailtemplate add --name <s> --subject <s> --html @f|str [--alias <s>] [--css @f|str] [--placeholder <p>]... [--desc <s>]` adds an exportable mail template to `rep-objects.mailTemplates[]` — `alias` is validated by `^[a-z][a-zA-Z0-9]*$` (or derived from `--name`), placeholders `{{…}}` are auto-scanned from html/subject (if not set explicitly), and `gjsData` is left `null` (it does not affect sending — `htmlContent` is what matters). Then `mrjun.py validate` and `pack`. Editing the JSON above by hand is a **fallback** (the same pattern as for other rep-objects: `id:null`, references by `identifier`), not the only path.

## 3.5 Modifying a filled project (adding a template to a working `.mrjun`)

Adding a template to an already-populated project is **append-only** and does not disturb the content tree:

- **Mail template.** `mrjun.py mailtemplate add …` appends one object to `rep-objects.mailTemplates[]` with `id:null` and a fresh `identifier` (`mail_cmds.py` via `core.new_rep_object`, which sets `id:None`, `core.py`); **nothing in `branches.json` changes**. First run `mrjun.py mailtemplate list` and **dedupe by `alias`** (and `name`) — both are unique per (realm, client), the platform save rejects a duplicate, and the tool itself raises `mailTemplate alias/name already exists` before writing (`mail_cmds.py`).
- **PDF printout.** A new PDF template **rides in `.mrjun`** via `pdftemplate add` (Part 1) and is created in nct-pdf on import. Note the alias is unique per realm/client in the `nct-pdf` DB (`pdf_templates`); the import upserts by deleting the realm/client's existing PDF templates first, so a re-import replaces rather than collides. If a template with that alias already exists and you are NOT re-importing, the Groovy `service.report.pdf.get.<alias>` call already resolves — no new template needed.

## 3.6 Seed & auto-seeded mail templates

Mail templates have the same "start from a ready-made one" affordance as the PDF seeds — from **two** sources:

**(a) "Load standard template" seeds** — the mail-template editor has a **"load standard template"** picker listing five ready-made HTML bodies the platform ships: **`invoice`**, **`newsletter`**, **`welcome`**, **`password-reset`**, **`task-assignment`**. These are *editor starting points* — loading one only fills the editor HTML; nothing is saved until you save a template. They are **not** auto-created and do **not** appear in an export by themselves.

**(b) System templates — auto-seeded per (realm, client)** — four "stock" templates are created automatically the first time a realm/client is provisioned: `SystemMailTemplateService.ensureSystemTemplates` iterates `SystemMailTemplateDefinition.values()` and creates any that are missing (`SystemMailTemplateService.java`, `createFromDefinition`, resources `mailtemplates/system/*.html`). The four definitions are `userRegistration`, `passwordRecover`, `companyInvitation`, `eventReminder` (`SystemMailTemplateDefinition.java`; `eventReminder` is the template `calendar.plugin` sends reminders through by default — [14](14-plugin-catalog-all.md)). Because they are auto-seeded, **every export contains them** as `rep-objects.mailTemplates[]` entries (shown in §3.2 as `Company Invitation` / `Event Reminder` / `Password Recovery` / `User Registration`). The seeding also runs **after every import**, so deleting one of the four from `rep-objects.mailTemplates[]` does not remove it from the target project — it comes back with the platform's own HTML.

This is why `jq '.mailTemplates|length'` on any export returns **at least 4**: every project carries the 4 auto-seeded system templates, and anything above that number is the project's own custom template (in the `empty` baseline that extra is `sendIntakeInit`). Placeholders are re-scanned from the HTML on seed with the same `\{\{(\w+)}}` pattern (`SystemMailTemplateService.java`).

---

# Part 4. Groovy flow: generate a PDF → send by email / push

This is the runtime part (nct-executor). In any **EXECUTION_RULE** (see [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md)) the `service` object is available with the branches `service.report.pdf.*`, `service.notification.mail.*`, `service.notification.push.*`. The full surface is authoritatively listed in `HintsService.java` (this is what also generates the autocomplete in the rule editor, [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md)).

## 4.1 `service.report.pdf.get.<pdfAlias>(fileName, params)` → `PdfReferenceDto`

Builds a **reference to a PDF** (does not render immediately). `<pdfAlias>` is the `alias` of a PDF template (Part 1). Implementation — `PdfTemplateGetProxy.methodMissing` (`PdfReportProxy.groovy`):

```groovy
def ref = service.report.pdf.get.intakeReceipt(
    "intake-42.pdf",
    [ customerName: "John Doe", total: "1250.00" ]   // keys = field names from templateJson
)
// -> PdfReferenceDto{ alias:"intakeReceipt", fileName:"intake-42.pdf", params:[...] }
```

- Signature (hint): `PdfReferenceDto <alias>(String fileName, Map<String, Object> params)` (`HintsService.java`).
- `params` — a map `field-name-from-templateJson → value`. For barcodes the value is a string; for `table`/`list` — nested lists, etc. (value examples — `HintsService.java`).
- Returns a `PdfReferenceDto` (`nct-transfer/.../pdf/PdfReferenceDto.java`: `alias`, `fileName`, `params`). This is a "deferred" reference — rendering happens later, at `email`/`push`/`download`.

> ⚠️ **`params` is ALWAYS keyed by the field `name` — including `multiVariableText`; its value is a NESTED map of the field's inner variables.** The render side (`PdfRenderServiceImpl.resolveInputs`, `nct-pdf/.../service/PdfRenderServiceImpl.java`) iterates `params`, resolves each **key against the field `name`** (`byName`, keyed by `PdfFieldInfo::getName`), and dispatches by that field's `type`: for `multiVariableText` it does `toJsonString(value)` — i.e. the value is a `Map` of the inner variables, serialized to the JSON string pdfme reads. The autocomplete generator agrees (`HintsService.buildPdfParamsSample`/`buildMultiVariableTextSample`, `nct-executor/.../service/HintsService.java`, which emit `fieldName: [innerVar: "…"]`). So for `01-invoice-classic.json` field `info` (multiVariableText, `variables:["invoiceNumber","invoiceDate","dueDate"]`) and field `billTo` (`variables:["customerName",…]`) you pass **`[ info: [invoiceNumber:"INV-42", invoiceDate:"…", dueDate:"…"], billTo: [customerName:"John Doe", …] ]`** — keyed by the field names `info`/`billTo`, each value a nested variable map. **NOT** the flattened `[invoiceNumber:…, customerName:…]`. Per-type rules for the other kinds: a `table` field (`items`, `head:["Item","Qty","Unit Price","Total"]`) takes a **2-D list of rows** — positional `items:[["Widget","2","10.00","20.00"], …]` or column-keyed `items:[[Item:"Widget", Qty:"2", …], …]` (`toTableJsonString`); an `image` field takes a `data:` URL, a bare file-storage path, or `abs(<storage-url>)` — an arbitrary http URL renders blank (`resolveImage`); a barcode field takes a plain **String**. **Any field you omit renders its template `content` default, not blank** — see the Gotchas.

## 4.2 `service.report.pdf.email.<mailAlias>(recipients, [subject,] placeholders, pdfs)`

**The main "PDF → email" flow.** `<mailAlias>` is the `alias` of a mail template (Part 2). Implementation — `PdfMailDispatcher.methodMissing` (`PdfReportProxy.groovy`): it renders each `PdfReferenceDto` in nct-pdf (`renderInternal`, `merge=false`), wraps it in a `MailAttachmentDto{fileName, contentType:"application/pdf", content}`, and sends a `SendMailByAliasRequest` via `mailTemplateFeignClient.sendByAliasInternal`.

Two signatures (`HintsService.java`):

```
void <mailAlias>(List<String> recipients, Map<String, String> placeholders, List<PdfReferenceDto> pdfs)
void <mailAlias>(List<String> recipients, String subject, Map<String, String> placeholders, List<PdfReferenceDto> pdfs)
```

## 4.3 Full worked example — "generate a PDF from a template and email it to a recipient/role"

EXECUTION_RULE (e.g. invoked from a CRUD action "Send Receipt" or from a process):

```groovy
// 1) Gather the row data (see reference: context.<ctx>.<alias>.data.get())
def intake = context.app_context.intakes.data.get()

// 2) Build a PDF reference from the template alias 'intakeReceipt' with placeholder params
def pdf = service.report.pdf.get.intakeReceipt(
    "intake-${intake.id}.pdf",
    [
        customerName: intake.customerName,
        total:        intake.total as String,
        date:         intake.createdAt as String
    ]
)

// 3a) Send by email using the mail-template alias 'invoiceIssued' to a specific address,
//     with the PDF as an attachment, using the default subject from the template:
service.report.pdf.email.invoiceIssued(
    [ intake.customerEmail ],                 // recipients
    [ firstName: intake.customerName, invoiceNo: intake.number, dueDate: intake.dueDate as String ], // placeholders
    [ pdf ]                                   // pdfs (attachments)
)

return true
```

Sending **to everyone in a role-group** with the same PDF — via the push branch (see 4.5) or via an ordinary email send (`service.notification.mail.*` does not support attachments — attachments are only on `service.report.pdf.email.*`).

With a custom subject:

```groovy
service.report.pdf.email.invoiceIssued(
    [ intake.customerEmail ],
    "Receipt for intake #${intake.id}",       // subject override
    [ firstName: intake.customerName ],
    [ pdf ]
)
```

## 4.4 `service.report.pdf.download(fileName, pdfs)` — download in the browser

Asynchronously (Kafka `PdfDownload.REQUEST`) renders+merges the PDF and puts it into the per-user inbox of the file storage; a UI timer (~10s) picks it up and triggers a save dialog (`PdfReportProxy.groovy`). Signature hint: `byte[] download(String fileName, List<PdfReferenceDto> pdfs)` (`HintsService.java`). Requires a user context (`userId`) — works from a rule launched by a user.

```groovy
service.report.pdf.download("report.pdf", [ pdf1, pdf2 ])   // merges into one file and offers it for download
```

## 4.5 `service.report.pdf.push.<method>(…, pdfs)` — push notification with a PDF

Renders the PDF, puts it into storage, sends a push with a download link (`PdfPushDispatcher`, `PdfReportProxy.groovy`). Full list of methods (`HintsService.java`), each one being like the same-named push but with an extra `List<PdfReferenceDto> pdfs` parameter at the end:

| Method | Return | Parameters (before `pdfs`) |
|---|---|---|
| `sendText` | void | `String userEmail, String message` |
| `sendAlert` / `sendWarning` / `sendError` | void | `String userEmail, String title, String message` |
| `sendReminder` | void | `String userEmail, String title, String description, LocalDateTime dueDate` |
| `sendTextToRoleGroup` | int | `String roleGroupName, String message` |
| `sendAlertToRoleGroup` / `sendWarningToRoleGroup` / `sendErrorToRoleGroup` | int | `String roleGroupName, String title, String message` |
| `sendReminderToRoleGroup` | int | `String roleGroupName, String title, String description, LocalDateTime dueDate` |
| `sendTextToRole` / `sendAlertToRole` / `sendWarningToRole` / `sendErrorToRole` / `sendReminderToRole` | int | as above, but `String roleName` |

```groovy
service.report.pdf.push.sendAlertToRoleGroup(
    "Reviewers", "New intake receipt", "Receipt is ready",
    [ pdf ]
)   // returns the number of recipients
```

## 4.6 `service.notification.mail.<alias>(recipients, [subject,] placeholders)` — email WITHOUT an attachment

Just sending a mail template without a PDF. Implementation — `MailNotificationProxy.methodMissing` (`MailNotificationProxy.groovy`). Two signatures (`HintsService.java`):

```groovy
// default subject from the template:
service.notification.mail.userRegistration(
    [ user.email ],
    [ firstName: user.firstName, activationLink: link ]
)
// custom subject:
service.notification.mail.userRegistration(
    [ user.email ], "Welcome!", [ firstName: user.firstName, activationLink: link ]
)
```

## 4.7 `service.notification.push.<method>(…)` — push WITHOUT a PDF

The same set of methods as in 4.5, but without `pdfs` (`PushNotificationProxy.java`, hints `HintsService.java`). A rule body (`ruleType: EXECUTION_RULE`) that sends one personal and one group notification:

```groovy
service.notification.push.sendAlert(service.security.user().email, 'Intake registered',
                                    'Intake #1042 has been registered and is awaiting review')
service.notification.push.sendAlertToRoleGroup('Reviewers', 'New intake to review',
                                    'Intake #1042 is waiting in the review queue')
```

Note how rarely this surface is used in practice: most projects never call `service.notification`/`service.report` at all, so treat the hint list — not another project's rules — as the authority on what exists.

## 4.8 How the alias wiring works (important for building)

```
Groovy: service.report.pdf.get.<pdfAlias>(...)         ─── pdfAlias = PdfTemplateDto.alias  (rep-objects.pdfTemplates[], IN the export; stored in the nct-pdf DB after import)
Groovy: service.report.pdf.email.<mailAlias>(...)      ─┐
Groovy: service.notification.mail.<mailAlias>(...)      ├─ mailAlias = MailTemplateDto.alias (rep-objects.mailTemplates[], IN the export)
                                                        ─┘
```

- `<pdfAlias>` is resolved **dynamically** (`methodMissing`) — the rule compiles even if the PDF template does not exist; the error surfaces at runtime during render. So ship both together: put the rule in the export AND add the matching PDF template with `pdftemplate add` (or, if it is not in the `.mrjun`, create it in nct-pdf beforehand via browser/REST) so the alias resolves at render time.
- `<mailAlias>` — also `methodMissing`; a mail template with this alias goes into `rep-objects.mailTemplates[]`, so the wiring is fully reconstructible from the export.
- The hints (`HintsService.buildPdfGetMethods`/`buildMailNotificationMethods`) pull the aliases from the services via Feign (`getAliasInfoInternal`, `getAliasInfo`) — if there are no templates, the branch is simply empty in the autocomplete, but `methodMissing` will still invoke the method.

## 4.9 How `params` become render inputs (by field type)

This is the actual runtime contract of `service.report.pdf.get.<alias>(fileName, params)`. When a PDF is finally rendered (inside `email`/`push`/`download`), nct-pdf's `PdfRenderServiceImpl.resolveInputs` (`nct-pdf/.../service/PdfRenderServiceImpl.java`) walks the `params` map and transforms **each value according to that field's type**:

- The map is keyed by field **`name`**. Each key is looked up in `byName` (field-name → `PdfFieldInfo`, built from the server-derived `fields`); the value is then serialized per `PdfFieldInfo.getType()`.
- **`null` / empty-string values are skipped** — the designed-in default fills in instead (see backfill below).

| Field type | `params` value shape | Serialization (`resolveInputs`) |
|---|---|---|
| `text`, barcodes, `date`/`time`/`dateTime`, `checkbox`, `select`, `radioGroup` | plain `String` | value as-is |
| `multiVariableText` | **`Map`** of the field's inner variables | `toJsonString(value)` → JSON string |
| `table` | `List<Map>` (keyed by column) **or** `List<List>` (positional) **or** a JSON string | `toTableJsonString(value, columns)` → JSON of a 2-D string array |
| `list` | `Map`/`List` | `toJsonString` — **but `list` has no renderer plugin, so it fails to render** (see §1.3) |
| `image` | `data:` URL, bare file-storage path, or `abs(<storage-url>/…)` | `resolveImage(value)` |

**`table` (`toTableJsonString`).** A `List<Map>` is projected onto the field's `columns` (from the template's `head`); key matching is exact first, then whitespace/case-tolerant (`"Unit Price"`, `"UnitPrice"`, `"unitprice"` all hit the same cell). A `List<List>` is taken positionally and padded to column count. An already-serialized JSON string passes through.

**`image` (`resolveImage`/`toFileStoragePath`).** A `data:` URL passes through unchanged. A bare relative path (`t/realm-client/uploads/x.png`) or an `abs(<storage-base>/x)` / absolute-URL-inside-the-storage-base is fetched from nct-file-storage and inlined as a base64 data URL. **Anything else — e.g. an arbitrary `http(s)://` URL — returns blank** (returns `null` → `""`); the renderer never fans out arbitrary HTTP. The autocomplete hint suggests the `abs(...)` form (`HintsService.java`). The bare-path forms only work for a file the **platform** stored (a runtime upload, or an editor upload under `t/<realm>-<client>/…`) — a file you shipped in `tenant-files/` lands under the numeric tenant id assigned at import, which you cannot know while authoring, so for anything you ship yourself pass a `data:` URL (same trap as the mail logo, Part 0).

**Designed-in `content` backfill.** After the loop, `resolveInputs` backfills every field's template `content` default for any key the rule **omitted** (`extractDefaultContents`). So an omitted field renders the seed's sample value, **not** blank — this is the copy-a-seed footgun in gotcha 11.

**`fields` drive all of the above and are server-derived.** The per-type branch keys off `PdfFieldInfo.getType()`; `fields` is auto-extracted from `templateJson` on every save (`PdfTemplateServiceImpl.java`) and re-extracted on read. You never author `fields` by hand — but if extraction fails (invalid JSON, unknown shape), the type is `null` and serialization silently degrades to "value as-is".

---

# Part 5. Triggering the send (wiring the EXECUTION rule)

The Groovy flow above is just a rule body. Its script text is stored at `rep-objects.rules[].rule.ruleScriptStr` (the nested path in the file is `.rule.rule.ruleScriptStr`), the rule reads its row via `context.<ctx>.<alias>.data.get()` (see [08](08-groovy-rules-and-context.md)). To make it actually fire, wire that rule from one of **three** places:

1. **CRUD table/tree action-rule** — a per-action `EXECUTION_RULE` on a `crud.table.plugin` / `crud.tree.plugin` action (e.g. a "Send Receipt" button). The action carries the `ruleIdentifier`; on click the row is loaded and the rule runs with `context.<ctx>.<alias>.data.get()` bound to that row. See [04-crud-table-plugin.md](04-crud-table-plugin.md) / [05-crud-tree-and-process-table.md](05-crud-tree-and-process-table.md).
2. **Workflow user/service-task rule** — an `EXECUTION_RULE` attached to a BPMN user-task or service-task; runs when the process reaches that step, with the process/task context bound. See [07-workflows-and-tasks.md](07-workflows-and-tasks.md).
3. **Scheduler** — a cron `ScheduleDto` (`admin.schedulers.plugin`) that on cron checks a predicate and runs the rule. See [12-queries-sources-schedulers-and-rest.md#3-schedulers](12-queries-sources-schedulers-and-rest.md). **Headless**: the scheduler passes its `serviceUserId` as the executor `userId` (`SchedulerExecutionServiceImpl.java`); if `serviceUserId` is blank there is **no user context**, so `service.report.pdf.download` is silently skipped (`PdfReportProxy.groovy`, gotcha 10). Use `get` + `email`/`push` from a scheduler (those need no userId); `download` only works from a user-launched rule (path 1/2) or a scheduler with a `serviceUserId` set.

---

## Gotchas

1. **PDF templates ARE in the export** (`rep-objects.pdfTemplates[]`), like mail templates — append one with `mrjun.py pdftemplate add … --template @file.json` and it is created in nct-pdf on import. Two caveats: (a) the `--template` JSON must be a **real pdfme layout** (a bare scaffold renders a blank PDF); (b) `pdfTemplates` is null/absent in older exports that predate the feature — harmless, it loads as an empty list. The browser/REST path still works for a one-off load into a running nct-pdf but is not portable.

2. **The alias pattern is strict.** Both PDF and mail aliases are validated by `^[a-z][a-zA-Z0-9]*$` (`PdfTemplateEditorPanel.java`, `MailTemplateEditorPanel.java`): starts with a lowercase letter, then letters/digits, **no** underscores/hyphens/dots. `intake_receipt` — invalid, `intakeReceipt` — OK.

3. **Uniqueness of name and alias** per (realm, client) — unique indexes (`PdfTemplateEntity.java`, similarly for `mail_templates`). Two templates with the same alias will not save.

4. **PDF attachments are only on `service.report.pdf.email.*` and `service.report.pdf.push.*`.** `service.notification.mail.<alias>(...)` does **not** accept attachments (there is no `pdfs` parameter, `MailNotificationProxy.groovy`). To attach a PDF to an email — only `service.report.pdf.email.<alias>(recipients, placeholders, pdfs)`.

5. **PDF `params` ≠ email `placeholders`.** PDF `get` takes `Map<String,Object> params` (keys = field `name`s from `templateJson`). The email takes `Map<String,String> placeholders` (keys = `{{…}}` from `htmlContent`). These are two different maps; in the "PDF→email" combination both are filled.

6. **`get` renders nothing.** `service.report.pdf.get.<alias>(...)` only returns a `PdfReferenceDto`. The actual render (call to nct-pdf) happens only inside `email`/`push`/`download`. If a rule assembled a `PdfReferenceDto` and never passed it anywhere — no PDF is generated.

7. **`gjsData` is not sent.** `htmlContent` is sent. `gjsData` is only needed so the visual editor (GrapesJS) can re-open the email in the builder (`MailTemplateEditorPanel.java`). You can set `"{}"`, and the email will still go out correctly.

8. **`{{placeholder}}` without spaces.** In the stock templates it is exactly `{{firstName}}`. The list in `placeholders[]` must match what actually appears in `htmlContent`/`subject`, otherwise the hint inserts a wrong key, and an unfilled `{{x}}` stays in the email as is.

9. **`pdf.report.plugin` — legacy, not for new projects.** This is the old mrjun report engine (the class is not in the sources). For new dynamic projects use pdfme (`report.pdf.templates.plugin`) + the Groovy API. Keep the demo node `reports/Pdf` as is or delete it together with the page.

10. **`download`/per-user push require a user context** (`userId`): from a rule launched by the system/scheduler without a user, `download` is silently skipped (`PdfReportProxy.groovy`). Sending an email (`email`) does not require a userId and works from background rules too.

11. **Omitting a PDF `param` renders the seed's sample, not blank (copy-a-seed footgun).** `resolveInputs` backfills every field's designed-in template `content` for any key the rule didn't supply (`PdfRenderServiceImpl.java`, `extractDefaultContents`). So if you copy a seed and forget a field, you ship the seed's demo value (`company:"Dokie Ltd"`, `name:"Maria Johnson"`, …). To blank a field or use your own value you must **pass the param** or **clear that field's `content`** in the template. Passing `null`/`""` also falls back to the default (such values are skipped).

12. **`pdftemplate scaffold` writes a `sampledata` key the seeds don't have.** `mrjun.py pdftemplate scaffold` emits a top-level `sampledata` row (`pdf_cmds.py`, helper `_sampledata_for`); the 15 seeds have none. Harmless — the render request sends `inputs` separately and `sampledata` is ignored — but don't treat it as part of the pdfme contract. The scaffold's blank base (`_A4_BASE = {210,297,[10,10,10,10]}`, `pdf_cmds.py`) matches the editor's blank default (§1.4.1).

13. **Per-user push Alert/Warning/Error/Reminder have no download chip — the URL goes into the message body.** `service.report.pdf.push.sendAlert/sendWarning/sendError/sendReminder` (the per-user, non-`ToRole*` variants) render+store the PDF but then **append the download URL into the message text** (`PdfReportProxy.groovy`, `appendDownloadLink`) because those push types lack a downloadable slot. **Only the `sendText` family** — per-user `sendText`, `sendTextToRole`, `sendTextToRoleGroup` — carries a proper downloadable payload (`sendDownloadable`, `PdfReportProxy.groovy`). The Alert/Warning/Error/Reminder **role and role-group** variants also append the URL into the message body via `appendDownloadLink`, exactly like their per-user counterparts.

14. **Mail `{{placeholder}}` allows only `[A-Za-z0-9_]`.** Both nct-messaging matchers use `\{\{(\w+)}}` (`MailTemplateServiceImpl.java`, `SystemMailTemplateService.java`): no dots, hyphens, or spaces inside the braces. `{{first.name}}` / `{{first-name}}` are never substituted and stay literal in the email.

> ℹ️ **Localization.** The nct-pdf engine does **not** localize values — it fills placeholders with whatever strings the rule passes. Localized text in a PDF (or email) comes only from the producing Wicket page/model choosing the locale-appropriate value before calling `get`/`email`. See [localization](20-localization.md).

---

## See also

- [08-groovy-rules-and-context.md](08-groovy-rules-and-context.md) — rule types, `EXECUTION_RULE`, reading `context.<ctx>.<alias>.data.get()`.
- [09-groovy-hints-and-live-context.md](09-groovy-hints-and-live-context.md) — `HintsService` as the source of autocomplete (including `service.report.pdf.*`, `service.notification.*`).
- [12-queries-sources-schedulers-and-rest.md](12-queries-sources-schedulers-and-rest.md) — other `rep-objects` (sources/queries/settings) next to `mailTemplates`.
- [01-content-model-and-pages.md](01-content-model-and-pages.md) — the content-node model, `properties` slots, `siteMapPage` (the "Pdf Templates"/"Mail Templates"/`reports/Pdf` pages).
- [00-export-format-and-import.md](00-export-format-and-import.md) — anatomy of `.mrjun`, where `rep-objects.json` lives.
