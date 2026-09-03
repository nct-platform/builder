"""rep-objects entities: rolegroup, context, rule, query, source, formgroup, form.

Encodes hard rules §3 (id=null, link by identifier, carry realm/client) and §5
(ruleType->executor, warn on missing return)."""

import re

from . import core


# ---------------------------------------------------------------------------
# rolegroup
# ---------------------------------------------------------------------------


def cmd_rolegroup_add(args):
    p = core.Project(args.project)
    groups = p.rep.setdefault("roleGroups", [])
    if any(g.get("name") == args.name for g in groups):
        raise core.ToolError("roleGroup already exists: %s" % args.name)
    # roleGroups in the export use a numeric string id, not an identifier uuid.
    existing_ids = [int(g["id"]) for g in groups if str(g.get("id", "")).isdigit()]
    new_id = str((max(existing_ids) + 1) if existing_ids else 1000)
    obj = {"id": new_id, "name": args.name, "roles": list(args.role or [])}
    groups.append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("roleGroup added: %s (id=%s, roles=%d)" % (args.name, new_id, len(obj["roles"])))


def cmd_rolegroup_rm(args):
    p = core.Project(args.project)
    groups = p.rep.get("roleGroups", []) or []
    keep = [g for g in groups if g.get("name") != args.name]
    if len(keep) == len(groups):
        raise core.ToolError("roleGroup not found: %s" % args.name)
    p.rep["roleGroups"] = keep
    p.mark(core.F_REP)
    p.save()
    core.out("roleGroup removed: %s" % args.name)


def cmd_rolegroup_list(args):
    p = core.Project(args.project)
    for g in p.rep.get("roleGroups", []) or []:
        core.out("%-24s id=%-6s roles=%d" % (g.get("name"), g.get("id"), len(g.get("roles", []) or [])))


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------


def cmd_context_add(args):
    p = core.Project(args.project)
    contexts = p.rep.setdefault("contexts", [])
    if any(c.get("alias") == args.alias for c in contexts):
        raise core.ToolError("context alias already exists: %s" % args.alias)
    obj = core.new_rep_object(p, {
        "name": args.name,
        "alias": args.alias,
        "crudAliases": list(dict.fromkeys(args.crud or [])),
    })
    contexts.append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("context added: %s (alias=%s)\n  identifier=%s\n  crudAliases=%s"
             % (args.name, args.alias, obj["identifier"], obj["crudAliases"]))


def cmd_context_add_alias(args):
    p = core.Project(args.project)
    ctx = core.resolve_context(p, args.context)
    aliases = ctx.setdefault("crudAliases", [])
    added = []
    for a in args.alias:
        if a not in aliases:  # idempotent
            aliases.append(a)
            added.append(a)
    if added:
        ctx["modificationTime"] = core.now_iso()
        p.mark(core.F_REP)
        p.save()
    core.out("context %s: added crudAliases %s (now %d total)"
             % (ctx.get("alias") or ctx.get("name"), added or "(none, all present)", len(aliases)))


# ---------------------------------------------------------------------------
# rule
# ---------------------------------------------------------------------------

_RETURN_RE = re.compile(r"(^|\n)\s*return\b")


def cmd_rule_add(args):
    p = core.Project(args.project)
    rule_type = args.type.upper()
    if rule_type not in core.RULE_EXECUTOR:
        raise core.ToolError("unknown ruleType %r (allowed: %s)"
                             % (args.type, ", ".join(core.RULE_EXECUTOR)))
    executor = core.RULE_EXECUTOR[rule_type]
    ctx = core.resolve_context(p, args.context)
    script = core.read_value_arg(args.script) or ""

    if rule_type in ("PREDICATE", "EXECUTION_RULE") and not _RETURN_RE.search(script):
        core.out("WARNING: %s script has no top-level `return` — the template "
                 "trailer will discard a bare value. Add an explicit `return`."
                 % rule_type)

    obj = core.new_rep_object(p, {
        "name": args.name,
        "description": args.desc,
        "status": "ACTIVE",
        "ruleType": rule_type,
        "executor": executor,
        "contextIdentifiers": [ctx["identifier"]],
        "rule": {"ruleScriptStr": script},
        "hidden": None,
    })
    p.rep.setdefault("rules", []).append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("rule added: %s (%s / %s)\n  identifier=%s\n  context=%s"
             % (args.name, rule_type, executor, obj["identifier"], ctx["identifier"]))


def cmd_rule_rm(args):
    p = core.Project(args.project)
    rule = core.resolve_rep(p, "rules", args.id)
    p.rep["rules"] = [r for r in p.rep.get("rules", []) if r is not rule]
    p.mark(core.F_REP)
    p.save()
    core.out("rule removed: %s <%s>" % (rule.get("name"), rule.get("identifier")))


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


def cmd_query_add(args):
    p = core.Project(args.project)
    source = core.resolve_rep(p, "sources", args.source)
    sql = core.read_value_arg(args.sql) or ""
    obj = core.new_rep_object(p, {
        "name": args.name,
        "query": sql,
        "sourceIdentifier": source["identifier"],
        "offset": 0,
        "itemsPerPage": args.items_per_page if args.items_per_page is not None else 20,
        "parameters": {},
        "attributes": {},
        "aggregations": {"aggregations": None, "groupByList": [], "orderByList": []},
        "wrapInPaging": None,
        "statementTimeoutSeconds": None,
        "schedule": None,
        "lastScheduledTime": None,
        "hidden": None,
    })
    p.rep.setdefault("queries", []).append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("query added: %s\n  identifier=%s\n  source=%s"
             % (args.name, obj["identifier"], source["identifier"]))
    return obj


# ---------------------------------------------------------------------------
# source
# ---------------------------------------------------------------------------


def _normalize_dbtype(project, requested):
    """Map a clean CLI dbtype onto whatever the project's sources already use.

    Real exports carry the misspelling 'POISTGRESQL'; we must not silently
    'fix' it or the import may mismatch. If existing sources use a variant we
    reuse it; otherwise fall back to the canonical spelling.
    """
    req = requested.upper()
    if req not in core.DBTYPE_CANONICAL:
        raise core.ToolError("unknown dbtype %r (allowed: %s)"
                             % (requested, ", ".join(core.DBTYPE_CANONICAL)))
    existing = {s.get("dbType", "").upper() for s in project.rep.get("sources", []) or []}
    if req == "POSTGRESQL":
        # POISTGRESQL is the ONLY value the runtime DbType enum accepts (the enum is
        # literally misspelled — DbType.java). A source with dbType "POSTGRESQL" fails to
        # deserialize on import (esp. on a greenfield empty base with 0 existing sources),
        # so ALWAYS emit the misspelling regardless of what other sources use.
        return "POISTGRESQL"
    return req


def cmd_source_add(args):
    p = core.Project(args.project)
    if any(s.get("name") == args.name for s in p.rep.get("sources", []) or []):
        raise core.ToolError("source already exists: %s" % args.name)
    obj = core.new_rep_object(p, {
        "name": args.name,
        "description": args.desc or ("Internal schema: %s" % args.schema),
        "hostName": args.host,
        "port": int(args.port),
        "dbName": args.db,
        "schemaName": args.schema,
        "userName": args.user,
        "password": args.password,
        "dbType": _normalize_dbtype(p, args.dbtype),
        "sourceType": args.source_type,
    })
    p.rep.setdefault("sources", []).append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("source added: %s (%s @ %s:%s/%s schema=%s)\n  identifier=%s"
             % (args.name, obj["dbType"], args.host, args.port, args.db, args.schema,
                obj["identifier"]))
    return obj


# ---------------------------------------------------------------------------
# formgroup / form
# ---------------------------------------------------------------------------


def _form_groups_page_identifier(project):
    """The admin 'Form Groups' siteMapPage identifier (parent of form-group pages)."""
    for node, _parent, _path in core.iter_nodes(project.root_content):
        if node.get("pluginName") == "siteMapPage" and node.get("name") == "Form Groups":
            return node.get("identifier")
    return None


def cmd_formgroup_add(args):
    p = core.Project(args.project)
    ctx = core.resolve_context(p, args.context)
    obj = core.new_rep_object(p, {
        "name": args.name,
        "contextIdentifiers": [ctx["identifier"]],
        "contentPageIdentifier": args.content_page,
        "formGroupsPageIdentifier": _form_groups_page_identifier(p),
        "placeFormsNextToLanding": bool(args.place_next_to_landing),
        "predicateFormMapping": {"mapping": []},
    })
    p.rep.setdefault("formGroups", []).append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("formGroup added: %s\n  identifier=%s\n  context=%s"
             % (args.name, obj["identifier"], ctx["identifier"]))
    return obj


def cmd_formgroup_set(args):
    """Patch an EXISTING form group's page wiring and mirror the change into every
    form's embedded `formGroup` copy (forms[].formGroup is a whole-object copy, so the
    two must stay in sync). Used to point a group at its per-CRUD landing page and null
    the formGroupsPageIdentifier (the Create-Default-Actions convention).
    """
    p = core.Project(args.project)
    fg = core.resolve_rep(p, "formGroups", args.id)
    changed = []
    if args.content_page is not None:
        fg["contentPageIdentifier"] = args.content_page
        changed.append("contentPageIdentifier=%s" % args.content_page)
    if args.no_list:
        fg["formGroupsPageIdentifier"] = None
        changed.append("formGroupsPageIdentifier=null")
    elif args.form_groups_page is not None:
        fg["formGroupsPageIdentifier"] = args.form_groups_page
        changed.append("formGroupsPageIdentifier=%s" % args.form_groups_page)
    if args.place_next_to_landing is not None:
        fg["placeFormsNextToLanding"] = (args.place_next_to_landing == "on")
        changed.append("placeFormsNextToLanding=%s" % fg["placeFormsNextToLanding"])
    if not changed:
        raise core.ToolError("nothing to set — pass --content-page / --form-groups-page / --no-list / --place-next-to-landing")

    # Mirror the changed fields into every form's embedded formGroup copy.
    mirror_keys = [k.split("=")[0] for k in changed]
    mirrored = 0
    for form in p.rep.get("forms", []) or []:
        emb = form.get("formGroup")
        if isinstance(emb, dict) and emb.get("identifier") == fg.get("identifier"):
            for k in mirror_keys:
                emb[k] = fg.get(k)
            mirrored += 1
    p.mark(core.F_REP)
    p.save()
    core.out("formGroup set: %s <%s>\n  %s\n  mirrored into %d embedded forms[].formGroup copy(ies)"
             % (fg.get("name"), (fg.get("identifier") or "")[:8], "; ".join(changed), mirrored))
    return fg


def cmd_form_add(args):
    p = core.Project(args.project)
    ctx = core.resolve_context(p, args.context)
    fg = core.resolve_rep(p, "formGroups", args.formgroup)
    obj = core.new_rep_object(p, {
        "formGroup": fg,
        "contentIdentifier": args.content,
        "name": args.name,
        "contextIdentifiers": [ctx["identifier"]],
        "validators": [],
        "actionValidators": [],
        "hiddenConfigs": [],
        "multiLanguage": True,
        "allowDrafts": None,
    })
    p.rep.setdefault("forms", []).append(obj)
    p.mark(core.F_REP)
    p.save()
    core.out("form added: %s\n  identifier=%s\n  formGroup=%s\n  context=%s"
             % (args.name, obj["identifier"], fg["identifier"], ctx["identifier"]))
    return obj
