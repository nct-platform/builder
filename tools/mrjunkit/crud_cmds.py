"""Dynamic CRUD commands: crud add (+scaffold-methods), crud add-method, crud list.

A dynamic CRUD lives in dynamic-cruds.json. SQL methods reference a saved query
(rep-objects.queries) by queryIdentifier, named crud_<alias>_<method> (§ naming
convention). GROOVY methods reference a rule by ruleIdentifier."""

import json

from . import core
from . import execaccess

# The standard method set of a dynamic CRUD (FINDINGS + SPEC).
STANDARD_METHODS = ["find", "findAll", "count", "get", "create", "update", "delete"]


def _find_crud(cruds, alias):
    for c in cruds:
        if c.get("alias") == alias or c.get("name") == alias:
            return c
    raise core.ToolError("crud not found: %s" % alias)


def _parse_fields(specs):
    """`name:Type` -> {fieldName, displayName, fieldType, fieldOrder}."""
    fields = []
    for i, spec in enumerate(specs or []):
        if ":" in spec:
            name, typ = spec.split(":", 1)
        else:
            name, typ = spec, "String"
        fields.append({
            "fieldName": name, "displayName": name,
            "fieldType": typ, "fieldOrder": i,
        })
    return fields


def _find_groovy_script(alias):
    return (
        "def filter = param ?: [:]\n"
        "def countResult = service.crud.%s.count()\n"
        "def total = (countResult instanceof Map ? (countResult.total ?: 0) : 0) as long\n"
        "def rows = service.crud.%s.findAll(filter) ?: []\n"
        "def rowsInPage = (filter.rowsInPage ?: 0) as int\n"
        "def pageNumber = (filter.pageNumber ?: 0) as int\n"
        "return [\n"
        "    content: rows,\n"
        "    totalElements: total,\n"
        "    totalPages: rowsInPage > 0 ? (long) Math.ceil(total / (double) rowsInPage) : 1,\n"
        "    pageNumber: pageNumber\n"
        "]\n" % (alias, alias)
    )


def _method_skeleton(method_name, method_type, order, params, returns_array,
                     query_identifier=None, rule_identifier=None, script=""):
    # A GROOVY method with a script MUST carry a ruleIdentifier or it is dead on arrival —
    # see cmd_crud_apply. `find` is the ONE exception: a blank ruleIdentifier there is the
    # auto-find sentinel the executor acts on (isAutoFindWrapper), so leave it alone.
    if method_type == "GROOVY" and script and not rule_identifier and method_name != "find":
        rule_identifier = core.new_uuid()
    return {
        "methodName": method_name,
        "methodType": method_type,
        "script": script,
        "returnType": "Object",
        "returnsArray": returns_array,
        "methodOrder": order,
        "ruleIdentifier": rule_identifier,
        "queryIdentifier": query_identifier,
        "contextIdentifiers": None,
        "returnFields": None,
        "parameters": [
            {"parameterName": pn, "parameterType": pt, "parameterOrder": i}
            for i, (pn, pt) in enumerate(params)
        ],
    }


def cmd_crud_add(args):
    p = core.Project(args.project)
    crud_file = p.ensure_cruds_file()
    cruds = crud_file.data.setdefault("cruds", [])
    if any(c.get("alias") == args.alias for c in cruds):
        raise core.ToolError("crud alias already exists: %s" % args.alias)

    source = core.resolve_rep(p, "sources", args.source)

    crud = {
        "alias": args.alias,
        "name": args.name,
        "localizationField": args.localization_field,
        "sourceIdentifier": source["identifier"],
        "sourceSchema": args.schema,
        "sourceHost": source.get("hostName"),
        "sourcePort": source.get("port"),
        "sourceDb": source.get("dbName"),
        "sourceUser": source.get("userName"),
        "sourcePassword": source.get("password"),
        "dtoFields": _parse_fields(args.field),
        "filterFields": [],
        "methods": [],
    }

    created_queries = []
    if args.scaffold_methods:
        _scaffold_methods(p, crud, source)
        created_queries = [q for q in p.rep.get("queries", []) or []
                           if str(q.get("name", "")).startswith("crud_%s_" % args.alias)]

    # Optionally register the new alias in a context's crudAliases in the SAME
    # call (idempotent), so a scaffolded crud passes `validate` immediately.
    ctx = None
    ctx_added = False
    if getattr(args, "context", None):
        ctx = core.resolve_context(p, args.context)
        aliases = ctx.setdefault("crudAliases", [])
        if args.alias not in aliases:
            aliases.append(args.alias)
            ctx["modificationTime"] = core.now_iso()
            ctx_added = True

    cruds.append(crud)
    p._cache[core.F_CRUDS] = crud_file
    p.mark(core.F_CRUDS)
    if args.scaffold_methods or ctx is not None:
        p.mark(core.F_REP)
    p.save()
    core.out("crud added: %s (%s) source=%s schema=%s fields=%d methods=%d"
             % (args.alias, args.name, source["identifier"], args.schema,
                len(crud["dtoFields"]), len(crud["methods"])))
    if args.scaffold_methods:
        core.out("  scaffolded methods: %s" % ", ".join(m["methodName"] for m in crud["methods"]))
        core.out("  created %d paired queries (crud_%s_<method>, empty SQL to fill in)"
                 % (len(created_queries), args.alias))
        core.out("  NOTE: fill BOTH sides of each SQL method to execute — the method.script "
                 "(uses `:param` syntax) AND its linked query.query (uses "
                 "`{name:'param',type:'integer'}` syntax); id param defaults to Integer.")
    if ctx is not None:
        ctx_name = ctx.get("alias") or ctx.get("name")
        if ctx_added:
            core.out("  registered alias %r in context %s.crudAliases" % (args.alias, ctx_name))
        else:
            core.out("  alias %r already present in context %s.crudAliases" % (args.alias, ctx_name))
    else:
        core.out("  register the alias: mrjun context add-alias <ctx> %s" % args.alias)


def _scaffold_methods(project, crud, source):
    """Create find(GROOVY) + findAll/count/get/create/update/delete(SQL) with
    paired queries named crud_<alias>_<method>."""
    alias = crud["alias"]
    page_params = [("rowsInPage", "Integer"), ("pageNumber", "Integer")]
    id_params = [("id", "Integer")]  # real cruds use Integer PKs; adjust if TEXT

    def make_query(method):
        obj = core.new_rep_object(project, {
            "name": "crud_%s_%s" % (alias, method),
            "query": "",  # empty SQL to fill in
            "sourceIdentifier": source["identifier"],
            "offset": 0,
            "itemsPerPage": 20,
            "parameters": {},
            "attributes": {},
            "aggregations": {"aggregations": None, "groupByList": [], "orderByList": []},
            "wrapInPaging": None,
            "statementTimeoutSeconds": None,
            "schedule": None,
            "lastScheduledTime": None,
            "hidden": None,
        })
        project.rep.setdefault("queries", []).append(obj)
        return obj["identifier"]

    methods = []
    # find — GROOVY
    methods.append(_method_skeleton(
        "find", "GROOVY", -1, page_params, False,
        script=_find_groovy_script(alias)))
    # findAll — SQL
    # Rule-safe paging: CAST the two paging params to integer. The platform's own emit is the untyped
    # `OFFSET (:pageNumber * :rowsInPage)`, which works from the UI table (pagination bound as typed ints)
    # but breaks the moment a Groovy/business-logic rule calls this findAll — the unbound pageNumber/rowsInPage
    # bind as untyped NULL and PG fails with `operator is not unique: unknown * unknown`. The CAST form is a
    # strict superset (correct from both the UI table AND a rule). See 11-business-logic-dynamic-crud.md.
    methods.append(_method_skeleton(
        "findAll", "SQL", 0, page_params, True,
        query_identifier=make_query("findAll"),
        script="SELECT * FROM <table> WHERE 1=1 ORDER BY id "
               "LIMIT :rowsInPage OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS integer))"))
    # count — SQL
    methods.append(_method_skeleton(
        "count", "SQL", 1, [], False,
        query_identifier=make_query("count"),
        script="SELECT COUNT(*) AS total FROM <table>"))
    # get — SQL
    methods.append(_method_skeleton(
        "get", "SQL", 2, id_params, False,
        query_identifier=make_query("get"),
        script="SELECT * FROM <table> WHERE id = :id"))
    # create — SQL
    methods.append(_method_skeleton(
        "create", "SQL", 3, [], False,
        query_identifier=make_query("create"),
        script="INSERT INTO <table> (...) VALUES (...) RETURNING *"))
    # update — SQL
    methods.append(_method_skeleton(
        "update", "SQL", 4, id_params, False,
        query_identifier=make_query("update"),
        script="UPDATE <table> SET ... WHERE id = :id RETURNING *"))
    # delete — SQL
    methods.append(_method_skeleton(
        "delete", "SQL", 5, id_params, False,
        query_identifier=make_query("delete"),
        script="DELETE FROM <table> WHERE id = :id"))
    crud["methods"] = methods


def cmd_crud_add_method(args):
    p = core.Project(args.project)
    crud_file = p.cruds_file
    if crud_file is None:
        raise core.ToolError("no dynamic-cruds.json in this project")
    cruds = crud_file.data.get("cruds", []) or []
    crud = _find_crud(cruds, args.alias)
    if any(m.get("methodName") == args.name for m in crud.get("methods", [])):
        raise core.ToolError("method already exists: %s.%s" % (args.alias, args.name))

    mtype = args.type.upper()
    if mtype not in ("SQL", "GROOVY"):
        raise core.ToolError("method type must be SQL or GROOVY")

    order = max((m.get("methodOrder", -1) for m in crud.get("methods", [])), default=-1) + 1
    script = core.read_value_arg(args.script) or ""

    query_id = None
    rule_id = None
    if mtype == "SQL":
        query_id = args.query
    else:
        rule_id = args.rule

    method = _method_skeleton(
        args.name, mtype, order, [], bool(args.returns_array),
        query_identifier=query_id, rule_identifier=rule_id, script=script)
    crud.setdefault("methods", []).append(method)
    p.mark(core.F_CRUDS)
    p.save()
    core.out("method added: %s.%s (%s, order=%d)%s"
             % (args.alias, args.name, mtype, order,
                (" query=%s" % query_id) if query_id else
                ((" rule=%s" % rule_id) if rule_id else "")))


def cmd_crud_apply(args):
    """Give every GROOVY method a ruleIdentifier — the offline equivalent of the UI's "Apply".

    A GROOVY method does not run its own `script`. `DynamicMethodExecutor.executeGroovyMethod`
    refuses outright::

        if (method.getRuleIdentifier() == null || method.getRuleIdentifier().isBlank())
            throw new IllegalStateException("Groovy method '" + name
                    + "' has no rule identifier. Apply the CRUD first.");

    and otherwise returns `{ruleIdentifier, status: "delegated", parameters}` — the script is
    executed as an ordinary EXECUTION_RULE looked up by that identifier, with the arguments
    bound as `param`.

    In the UI that rule is written by `CrudEditorPanel.saveGroovyRule` when you press **Apply**,
    with `hidden(true)`. Hidden rules are filtered out of the export, so rep-objects.json
    carries none of them — and the importer knows this: `CmsProjectServiceImpl` re-creates each
    one from the method's own `script` (`ensureHiddenGroovyRule`). But it is guarded::

        if (isBlank(em.getRuleIdentifier()) || isBlank(em.getScript())) return;

    So the identifier is the whole hinge. Present → the platform builds the rule on import and
    the method works. Absent → the method is dead in the imported project, and every caller of
    it dies with it: a choices rule calling `service.crud.<x>.find(...)` yields an EMPTY
    dropdown, a form action calling `create` fails submission. Nothing offline can see this —
    the script is right there in the file, and `validate` used to pass.

    This writes the identifier only; there is deliberately no rule in rep-objects.json, because
    the import path is the platform's own and it is the one the UI reproduces on re-Apply.

    ⚠️ `find` is exempt. A GROOVY `find` with a BLANK ruleIdentifier is the **auto-find sentinel**:
    `isAutoFindWrapper` catches it before the delegation branch and `executeAutoFindWrapper` runs the
    sibling `findAll` + `count` in-process, assembling the PageResult itself. Its `script` is
    documentation. Giving it an identifier is not fatal — the generated rule computes the same thing —
    but it silently moves a hot path off the in-process route, so this leaves it alone.

    Idempotent. Also reports the opposite defect (identifier but no script), which makes the
    importer skip the method just the same and yields "Rule not found with identifier: <id>".
    """
    p = core.Project(args.project)
    crud_file = p.cruds_file
    if crud_file is None:
        raise core.ToolError("no dynamic-cruds.json in this project")

    wired, already, scriptless = 0, 0, []
    for crud in crud_file.data.get("cruds", []) or []:
        for m in crud.get("methods", []) or []:
            if (m.get("methodType") or "").upper() != "GROOVY":
                continue
            has_id = bool((m.get("ruleIdentifier") or "").strip())
            has_script = bool((m.get("script") or "").strip())
            if m.get("methodName") == "find" and not has_id:
                continue                                    # auto-find sentinel — see docstring
            if not has_script:
                if has_id:
                    scriptless.append("%s.%s" % (crud.get("alias"), m.get("methodName")))
                continue
            if has_id:
                already += 1
                continue
            m["ruleIdentifier"] = core.new_uuid()
            wired += 1
            core.out("  wired %s.%s -> %s"
                     % (crud.get("alias"), m.get("methodName"), m["ruleIdentifier"]))

    if wired:
        p.mark(core.F_CRUDS)
        p.save()
    for ref in scriptless:
        core.out("WARNING: %s has a ruleIdentifier but no script — the importer skips it "
                 "(ensureHiddenGroovyRule needs both), so the method fails at runtime with "
                 "\"Rule not found with identifier\". Add the script or clear the identifier."
                 % ref)
    core.out("crud apply: %d method(s) wired, %d already had an identifier" % (wired, already))


# ---------------------------------------------------------------------------
# execution access — who may RUN the CRUD's methods (doc 11 §"Execution access")
# ---------------------------------------------------------------------------


def _dynamic_crud_for_access(p, alias):
    """The dynamic CRUD `alias`, with the two refusals that explain where else access lives."""
    if alias == execaccess.BL_ALIAS:
        raise core.ToolError("'bl' is the integration's CRUD-management CRUD — it is always administrators and "
                             "authors only, and that is not configurable")
    crud_file = p.cruds_file
    cruds = ((crud_file.data.get("cruds") if crud_file and isinstance(crud_file.data, dict) else None) or [])
    for c in cruds:
        if isinstance(c, dict) and c.get("alias") == alias:
            return c
    raise core.ToolError("no dynamic CRUD with alias %r in dynamic-cruds.json. A Java (static) CRUD declares its "
                         "access in code with @CrudAccess (on the class and/or a method) — it is not in the export "
                         "and cannot be set here (doc 11 §\"Execution access\")" % alias)


def _find_method(crud, name):
    for m in crud.get("methods") or []:
        if isinstance(m, dict) and m.get("methodName") == name:
            return m
    raise core.ToolError("crud %r has no method %r (methods: %s)"
                         % (crud.get("alias"), name,
                            ", ".join(str(m.get("methodName")) for m in crud.get("methods") or []
                                      if isinstance(m, dict)) or "none"))


def _runs_with(crud, m):
    """What one method runs with, in words: its own access, or the CRUD's (inherited)."""
    acc, source = execaccess.method_effective(crud, m)
    if source == "own":
        return "own access: %s" % execaccess.describe(acc)
    stale = "" if m.get("access") is None else "  [carries an `access` that is IGNORED: inheritAccess is not false]"
    return "inherits the CRUD's: %s%s" % (execaccess.describe(acc), stale)


def _method_line(crud, m):
    return "%-28s %s" % (m.get("methodName"), _runs_with(crud, m))


def cmd_crud_access(args):
    """Show or set a dynamic CRUD's CRUD-level access (cruds[].access); every inheriting method runs with it."""
    p = core.Project(args.project)
    crud = _dynamic_crud_for_access(p, args.alias)
    access = execaccess.access_from_args(args)
    if args.show and (access is not None or args.default):
        raise core.ToolError("--show only prints; drop it to change the access")
    if args.default and access is not None:
        raise core.ToolError("--default removes the access (= signed-in users); it cannot be combined with "
                             "--access / --role-group")

    if access is None and not args.default:
        core.out("crud: %s (%s)" % (crud.get("alias"), crud.get("name")))
        core.out("  access: %s" % execaccess.describe(crud.get("access")))
        if crud.get("access") is not None:
            core.out("  raw: %s" % json.dumps(crud.get("access"), ensure_ascii=False))
        core.out("  methods:")
        for m in crud.get("methods") or []:
            if isinstance(m, dict):
                core.out("    " + _method_line(crud, m))
        return 0

    before = execaccess.describe(crud.get("access"))
    if args.default:
        if "access" not in crud:
            core.out("crud %s: access already absent — signed-in users (the default)" % crud.get("alias"))
            return 0
        crud.pop("access")
    else:
        crud["access"] = access
        execaccess.warn_unknown_groups(p, access)
    p.mark(core.F_CRUDS)
    p.save()
    own = [m.get("methodName") for m in crud.get("methods") or []
           if isinstance(m, dict) and m.get("inheritAccess") is False]
    core.out("crud access set: %s\n  access=%s\n  was=%s\n  inherited by every method except: %s"
             % (crud.get("alias"), execaccess.describe(crud.get("access")), before,
                ", ".join(own) if own else "(none — all inherit)"))
    return 0


def cmd_crud_method_access(args):
    """Show or set ONE dynamic CRUD method's access: --inherit (the CRUD's; the default) or its own."""
    p = core.Project(args.project)
    crud = _dynamic_crud_for_access(p, args.alias)
    m = _find_method(crud, args.method)
    access = execaccess.access_from_args(args)
    if args.inherit and access is not None:
        raise core.ToolError("--inherit makes the method run with the CRUD's access; it cannot be combined with "
                             "--access / --role-group")
    if args.show and (access is not None or args.inherit):
        raise core.ToolError("--show only prints; drop it to change the access")
    ref = "%s.%s" % (crud.get("alias"), m.get("methodName"))

    if access is None and not args.inherit:
        core.out("method: %s" % ref)
        core.out("  inheritAccess: %s" % m.get("inheritAccess"))
        core.out("  runs with: " + _runs_with(crud, m))
        if m.get("access") is not None:
            core.out("  raw access: %s" % json.dumps(m.get("access"), ensure_ascii=False))
        core.out("  crud access: %s" % execaccess.describe(crud.get("access")))
        return 0

    before = _runs_with(crud, m)
    if args.inherit:
        # Absent IS inherit (absent/null/true all mean "the CRUD's"), and a leftover `access` would only be
        # read the day someone flips inheritAccess to false — remove both.
        if "inheritAccess" not in m and "access" not in m:
            core.out("method %s: already inherits the CRUD's access (%s)"
                     % (ref, execaccess.describe(crud.get("access"))))
            return 0
        m.pop("inheritAccess", None)
        m.pop("access", None)
    else:
        m["inheritAccess"] = False
        m["access"] = access
        execaccess.warn_unknown_groups(p, access)
    p.mark(core.F_CRUDS)
    p.save()
    core.out("method access set: %s\n  runs with: %s\n  was: %s"
             % (ref, _runs_with(crud, m), before))
    return 0


def cmd_crud_list(args):
    p = core.Project(args.project)
    crud_file = p.cruds_file
    cruds = (crud_file.data.get("cruds", []) if crud_file else []) or []
    if not cruds:
        core.out("(no dynamic cruds)")
        return
    for c in cruds:
        core.out("%-30s %-30s source=%s schema=%s methods=%d"
                 % (c.get("alias"), c.get("name"), c.get("sourceIdentifier"),
                    c.get("sourceSchema"), len(c.get("methods", []) or [])))
