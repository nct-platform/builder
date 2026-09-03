"""pdftemplate — pdfme template scaffolding + export inclusion.

PDF templates live in the nct-pdf service DB (`pdf_templates`, PdfTemplateEntity),
BUT they ARE carried in the `.mrjun` — `rep-objects.json` has a `pdfTemplates[]`
collection (a list of `PdfTemplateDto`), exported/imported alongside mail templates
by nct-ui's `CmsProjectServiceImpl` (import saves each into nct-pdf via
`PdfTemplateClient.save`). See ../15-pdf-and-mail.md part 1.

Commands:
  - `add`      — append a pdfme template (from a JSON file) to rep-objects.pdfTemplates[]
                 so it is created in nct-pdf on import (the real, portable path).
  - `scaffold` — write a BARE standalone pdfme JSON to <file.json> (a skeleton to fill
                 in, or to import by hand); does NOT touch the project.
  - `note`     — print guidance.
"""
import json
import re

from . import core

# pdfme field types — aligned with the renderer plugin map that decides what
# actually renders (the PDF renderer's plugin registry). See 15-pdf-and-mail.md 1.3.
# NOTE: `list` is intentionally EXCLUDED — HintsService/resolveInputs acknowledge it
# but the renderer registers no `list` plugin, so a `list` field never renders.
# Shapes (line/rectangle/ellipse) are valid schema types but the extractor skips them
# (PdfFieldExtractor.java), so they take no params — decoration only.
_FIELD_TYPES = {
    "text", "multiVariableText", "image", "svg", "select", "radioGroup", "checkbox",
    "date", "time", "dateTime", "table", "line", "rectangle", "ellipse",
    "qrcode", "code128", "ean13", "ean8", "code39", "itf14", "upca", "upce",
    "japanpost", "gs1datamatrix", "pdf417", "nw7",
}

# alias pattern is strict on the platform side (PdfTemplateEditorPanel).
_ALIAS_RE = re.compile(r"^[a-z][a-zA-Z0-9]*$")

# A4 blank base PDF (mm), matching the pdfme default the seed templates use.
_A4_BASE = {"width": 210, "height": 297, "padding": [10, 10, 10, 10]}


def _text_field(name, x, y):
    return {
        "name": name,
        "type": "text",
        "position": {"x": x, "y": y},
        "width": 90,
        "height": 8,
        "rotate": 0,
        "alignment": "left",
        "verticalAlignment": "top",
        "fontSize": 12,
        "lineHeight": 1,
        "characterSpacing": 0,
        "fontColor": "#000000",
        "backgroundColor": "",
        "opacity": 1,
        "content": name,
    }


def _typed_field(name, ftype, x, y):
    """Build a minimal valid field of the requested pdfme type."""
    base = {
        "name": name,
        "type": ftype,
        "position": {"x": x, "y": y},
        "width": 90,
        "height": 8,
        "rotate": 0,
        "opacity": 1,
    }
    if ftype == "text":
        return _text_field(name, x, y)
    if ftype == "multiVariableText":
        base.update({
            "alignment": "left", "verticalAlignment": "top", "fontSize": 12,
            "lineHeight": 1, "characterSpacing": 0, "fontColor": "#000000",
            "backgroundColor": "", "fontName": "",
            "text": "{%s}" % name,
            "content": json.dumps({name: name}),
            "variables": [name],
        })
        return base
    if ftype == "image":
        base.update({"height": 20})
        return base
    if ftype == "line":
        base.update({"height": 0.3, "color": "#000000"})
        return base
    if ftype == "rectangle":
        base.update({"height": 20, "color": "#ffffff",
                     "borderColor": "#000000", "borderWidth": 0.2})
        return base
    if ftype in ("qrcode", "code128", "ean13", "ean8", "code39", "itf14",
                 "upca", "upce", "japanpost", "gs1datamatrix", "pdf417", "nw7"):
        base.update({"width": 30, "height": 30, "backgroundColor": "",
                     "barColor": "#000000", "content": name})
        return base
    if ftype == "checkbox":
        base.update({"width": 8, "height": 8, "content": "false"})
        return base
    # date/time/select/radioGroup/list/table etc. — a text-like default is valid.
    base.update({"content": ""})
    return base


def _sampledata_for(fields):
    """One row of sample data keyed by field name (skips shape-only types)."""
    row = {}
    for f in fields:
        if f["type"] in ("line", "rectangle", "image"):
            continue
        row[f["name"]] = f["name"]
    return row


def cmd_pdftemplate_scaffold(args):
    alias = args.alias
    if not _ALIAS_RE.match(alias):
        raise core.ToolError(
            "invalid alias %r: must match ^[a-z][a-zA-Z0-9]*$ (no _ - . )" % alias)

    specs = []
    if args.field:
        for raw in args.field:
            if ":" not in raw:
                raise core.ToolError("expected name:type, got %r" % raw)
            name, ftype = raw.split(":", 1)
            name = name.strip()
            ftype = ftype.strip()
            if ftype not in _FIELD_TYPES:
                raise core.ToolError("unknown field type %r (allowed: %s)"
                                     % (ftype, ", ".join(sorted(_FIELD_TYPES))))
            specs.append((name, ftype))
    if not specs:
        # sensible default single text field so the template is renderable
        specs = [("title", "text")]

    fields = []
    y = 20
    for name, ftype in specs:
        fields.append(_typed_field(name, ftype, 10, y))
        y += 15

    template = {
        "basePdf": dict(_A4_BASE),
        "schemas": [fields],
        "sampledata": [_sampledata_for(fields)],
    }

    text = json.dumps(template, ensure_ascii=False, indent=2)
    core.atomic_write(args.out, text)

    core.out("pdfme template written: %s (alias=%s, %d field(s))"
             % (args.out, alias, len(fields)))
    core.out("  fields: %s" % ", ".join("%s:%s" % (n, t) for n, t in specs))
    core.out("")
    core.out("NOTE: this is a BARE skeleton (labels+positions are placeholders) — it")
    core.out("renders nearly blank. FILL IN a real layout, then ship it INTO the project:")
    core.out("  mrjun.py pdftemplate add --alias %s --name '<Name>' --template @%s"
             % (alias, args.out))
    core.out("    -> appends to rep-objects.pdfTemplates[]; created in nct-pdf on import.")
    core.out("Then Groovy calls it by alias: service.report.pdf.get.%s(fileName, params)" % alias)


def cmd_pdftemplate_note(args):
    core.out("PDF templates live in nct-pdf (DB table `pdf_templates`), but they ARE")
    core.out("carried in the .mrjun: `rep-objects.json` has a `pdfTemplates[]` list")
    core.out("(PdfTemplateDto), exported/imported alongside mail templates by nct-ui")
    core.out("(`CmsProjectServiceImpl`; import saves each into nct-pdf via PdfTemplateClient).")
    core.out("")
    core.out("How to add one to a project (the PORTABLE path):")
    core.out("  mrjun.py pdftemplate add --alias <a> --name <s> --template @file.json")
    core.out("    -> appends it to rep-objects.pdfTemplates[]; created in nct-pdf on import.")
    core.out("  Author `file.json` as a REAL pdfme template (basePdf + schemas with")
    core.out("  static-label fields + positioned value fields + tables) — copy the closest")
    core.out("  seed in doc/builder/pdftemplates/*.json, or `pdftemplate")
    core.out("  scaffold` a bare skeleton and FILL IN the layout (a raw scaffold renders blank).")
    core.out("")
    core.out("Other ways (non-portable / manual): the browser 'Pdf Templates' page, or a")
    core.out("REST POST of a PdfTemplateDto to nct-pdf PdfTemplateController.")
    core.out("")
    core.out("How Groovy calls a PDF template (by alias):")
    core.out("  def pdf = service.report.pdf.get.<alias>(fileName, params)   // params keys = field names")
    core.out("  service.report.pdf.email.<mailAlias>(recipients, placeholders, [pdf])  // PDF as attachment")
    core.out("  service.report.pdf.download(fileName, [pdf])                // download in browser")
    core.out("The <alias> resolves dynamically (methodMissing): the rule compiles even")
    core.out("if the PDF template does not exist yet — it must exist in nct-pdf at runtime.")


def cmd_pdftemplate_add(args):
    """Append a pdfme template (from a JSON file) to rep-objects.pdfTemplates[] so
    the platform creates it in nct-pdf on import (exported/imported like a mail
    template). Idempotent: replaces an existing entry with the same alias/name."""
    p = core.Project(args.project)
    if not _ALIAS_RE.match(args.alias):
        raise core.ToolError("alias must match ^[a-z][a-zA-Z0-9]*$ (Groovy handle "
                             "for service.report.pdf.get.<alias>)")
    raw = core.read_value_arg(args.template)
    if raw is None:
        raise core.ToolError("--template is required (@file.json or inline pdfme JSON)")
    try:
        tj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise core.ToolError("template is not valid JSON: %s" % exc)
    if not (isinstance(tj, dict) and "basePdf" in tj and "schemas" in tj):
        raise core.ToolError("not a pdfme template — needs top-level 'basePdf' and 'schemas'")
    schemas = tj.get("schemas")
    nfields = len(schemas[0]) if isinstance(schemas, list) and schemas and isinstance(schemas[0], list) else 0
    if nfields == 0:
        core.out("WARNING: template has 0 fields on page 1 — it will render blank. "
                 "Author a real layout (labels + values + shapes) — see 15-pdf-and-mail.md.")

    pdfs = p.rep.setdefault("pdfTemplates", [])
    pdfs[:] = [t for t in pdfs
               if t.get("alias") != args.alias and t.get("name") != args.name]
    obj = core.new_rep_object(p, {
        "name": args.name,
        "alias": args.alias,
        "description": args.desc,
        "active": True,
        "templateJson": json.dumps(tj, ensure_ascii=False),
        "fields": None,
        "previewImage": None,
    })
    pdfs.append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("pdfTemplate added: %s (alias=%s, %d fields) -> rep-objects.pdfTemplates[]\n"
             "  identifier=%s\n  imported into nct-pdf on the next project import "
             "(referenced from Groovy by service.report.pdf.get.%s)"
             % (args.name, args.alias, nfields, obj["identifier"], args.alias))
