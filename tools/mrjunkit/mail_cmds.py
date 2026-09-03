"""mailtemplate — rep-objects.mailTemplates[] entities (add / list / rm).

Mail templates are exportable: they live in `rep-objects.json.mailTemplates[]`
(PDF templates ride in `rep-objects.pdfTemplates[]` the same way) and are
linked only by `identifier`, with
`id=null` and `realmName`/`clientName` copied off a sibling (hard rule §3).
See ../15-pdf-and-mail.md part 3 for the reference model.
"""

import re

from . import core

# alias pattern is strict on the platform side (MailTemplateEditorPanel):
# starts with a lowercase letter, then letters/digits — no _ - . (§15 gotcha 2).
_ALIAS_RE = re.compile(r"^[a-z][a-zA-Z0-9]*$")
# {{placeholder}} tokens found in htmlContent/subject.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def _default_alias(name):
    """Derive a valid camelCase alias from a display name (best-effort)."""
    parts = re.split(r"[^A-Za-z0-9]+", name.strip())
    parts = [p for p in parts if p]
    if not parts:
        return "mailTemplate"
    first = parts[0]
    alias = first[:1].lower() + first[1:]
    for p in parts[1:]:
        alias += p[:1].upper() + p[1:]
    # ensure it starts with a lowercase letter
    if not alias or not alias[0].isalpha():
        alias = "m" + alias
    alias = alias[:1].lower() + alias[1:]
    return alias


def cmd_mailtemplate_add(args):
    p = core.Project(args.project)
    templates = p.rep.setdefault("mailTemplates", [])

    alias = args.alias or _default_alias(args.name)
    if not _ALIAS_RE.match(alias):
        raise core.ToolError(
            "invalid alias %r: must match ^[a-z][a-zA-Z0-9]*$ (no _ - . ); "
            "pass --alias with a camelCase handle" % alias)

    if any(t.get("name") == args.name for t in templates):
        raise core.ToolError("mailTemplate name already exists: %s" % args.name)
    if any(t.get("alias") == alias for t in templates):
        raise core.ToolError("mailTemplate alias already exists: %s" % alias)

    html = core.read_value_arg(args.html) or ""
    css = core.read_value_arg(args.css)  # None if not given
    subject = args.subject or ""

    # Placeholders: explicit --placeholder wins; otherwise auto-scan {{...}}.
    if args.placeholder:
        placeholders = list(dict.fromkeys(args.placeholder))
    else:
        found = _PLACEHOLDER_RE.findall(html) + _PLACEHOLDER_RE.findall(subject)
        placeholders = list(dict.fromkeys(found))

    obj = core.new_rep_object(p, {
        "name": args.name,
        "alias": alias,
        "subject": subject,
        "htmlContent": html,
        "cssContent": css,          # null when unset — matches real stock templates
        "gjsData": None,            # hand-built template; htmlContent still sends
        "placeholders": placeholders,
        "description": args.desc,
        "active": True,
    })
    templates.append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("mailTemplate added: %s (alias=%s)\n  identifier=%s\n  placeholders=%s"
             % (args.name, alias, obj["identifier"], placeholders))
    return obj


def cmd_mailtemplate_list(args):
    p = core.Project(args.project)
    templates = p.rep.get("mailTemplates", []) or []
    for t in templates:
        core.out("%-28s alias=%-22s active=%-5s placeholders=%s"
                 % (t.get("name"), t.get("alias"), t.get("active"),
                    t.get("placeholders") or []))
    if not templates:
        core.out("(no mail templates)")


def _resolve_mailtemplate(project, key):
    """Resolve a mailTemplate by identifier, exact name, or exact alias."""
    items = project.rep.get("mailTemplates", []) or []
    by_id = [t for t in items if t.get("identifier") == key or t.get("id") == key]
    if len(by_id) == 1:
        return by_id[0]
    by_alias = [t for t in items if t.get("alias") == key]
    if len(by_alias) == 1:
        return by_alias[0]
    if len(by_alias) > 1:
        raise core.ToolError("ambiguous mailTemplate %r by alias" % key)
    return core._resolve_in_list(items, key, "name", "mailTemplate")


def cmd_mailtemplate_rm(args):
    p = core.Project(args.project)
    tpl = _resolve_mailtemplate(p, args.id)
    p.rep["mailTemplates"] = [t for t in p.rep.get("mailTemplates", []) if t is not tpl]
    p.mark(core.F_REP)
    p.save()
    core.out("mailTemplate removed: %s (alias=%s) <%s>"
             % (tpl.get("name"), tpl.get("alias"), tpl.get("identifier")))
