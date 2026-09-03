"""Read-only inspection: inspect, tree, find, list, show."""

import json
from collections import Counter

from . import core


# ---------------------------------------------------------------------------
# inspect — counts across every file
# ---------------------------------------------------------------------------


def cmd_inspect(args):
    p = core.Project(args.project)
    root = p.root_content

    plugin_hist = Counter()
    pages = 0
    for node, _parent, _path in core.iter_nodes(root):
        pn = node.get("pluginName")
        plugin_hist[pn] += 1
        if pn == "siteMapPage":
            pages += 1

    rep = p.rep
    rules = rep.get("rules", []) or []
    rules_by_type = Counter(r.get("ruleType") for r in rules)

    contexts = rep.get("contexts", []) or []
    ctx_lines = []
    for c in contexts:
        ctx_lines.append("    %s (alias=%s) crudAliases=%d"
                         % (c.get("name"), c.get("alias"), len(c.get("crudAliases", []) or [])))

    cruds_file = p.cruds_file
    cruds = (cruds_file.data.get("cruds", []) if cruds_file else []) or []
    crud_lines = []
    for c in cruds:
        crud_lines.append("    %s (%s) methods=%d" % (c.get("alias"), c.get("name"),
                                                      len(c.get("methods", []) or [])))

    db = p.db
    schemas = db.get("schemas", []) or []
    schema_lines = []
    for s in schemas:
        schema_lines.append("    %s: %d tables, %d sequences"
                            % (s.get("name"), len(s.get("tables", []) or []),
                               len(s.get("sequences", []) or [])))

    lines = []
    lines.append("Project: %s (%s)" % (p.tenant.get("name"), p.tenant.get("alias")))
    lines.append("Locales: %s" % ", ".join(p.locales()))
    lines.append("")
    lines.append("Content tree:")
    lines.append("  pages (siteMapPage): %d" % pages)
    lines.append("  total nodes: %d" % sum(plugin_hist.values()))
    lines.append("  pluginName histogram (top 25):")
    for pn, n in plugin_hist.most_common(25):
        lines.append("    %5d  %s" % (n, pn))
    lines.append("")
    lines.append("rep-objects:")
    for coll in core.REP_COLLECTIONS:
        lines.append("  %-24s %d" % (coll, len(rep.get(coll, []) or [])))
    lines.append("  rules by type:")
    for t, n in rules_by_type.items():
        lines.append("    %-16s %d" % (t, n))
    lines.append("  contexts:")
    lines.extend(ctx_lines or ["    (none)"])
    lines.append("")
    lines.append("dynamic cruds: %d" % len(cruds))
    lines.extend(crud_lines[:60])
    lines.append("")
    lines.append("database (%s):" % db.get("database"))
    lines.extend(schema_lines or ["    (none)"])
    core.out("\n".join(lines))


# ---------------------------------------------------------------------------
# tree — siteMapPage hierarchy
# ---------------------------------------------------------------------------


def cmd_tree(args):
    p = core.Project(args.project)
    root = p.root_content
    start = root
    if args.page:
        start = core.find_node(root, args.page)

    def show(node, depth):
        indent = "  " * depth
        core.out("%s%s  [%s]  <%s>"
                 % (indent, node.get("name") or "?", node.get("pluginName"),
                    node.get("identifier")))
        for c in node.get("children", []) or []:
            show(c, depth + 1)

    if args.all:
        show(start, 0)
    else:
        # only show siteMapPage nodes for a compact site map
        def show_pages(node, depth):
            if node.get("pluginName") == "siteMapPage":
                indent = "  " * depth
                core.out("%s%s  (alias=%s)  <%s>"
                         % (indent, node.get("name") or "?", node.get("alias"),
                            node.get("identifier")))
                depth += 1
            for c in node.get("children", []) or []:
                show_pages(c, depth)
        show_pages(start, 0)


# ---------------------------------------------------------------------------
# find — locate content nodes
# ---------------------------------------------------------------------------


def cmd_find(args):
    p = core.Project(args.project)
    root = p.root_content
    matches = []
    nl = (args.name or "").lower()
    for node, _parent, path in core.iter_nodes(root):
        if args.plugin and node.get("pluginName") != args.plugin:
            continue
        if args.name and nl not in (node.get("name") or "").lower():
            continue
        if args.id and node.get("identifier") != args.id and node.get("uniqueIdentifier") != args.id:
            continue
        matches.append((node, path))
    if not matches:
        core.out("(no matches)")
        return
    for node, path in matches:
        full = "/".join(path + (node.get("name") or "?",))
        core.out("%s\n    plugin=%s identifier=%s"
                 % (full, node.get("pluginName"), node.get("identifier")))
    core.out("\n%d match(es)" % len(matches))


# ---------------------------------------------------------------------------
# list <kind>
# ---------------------------------------------------------------------------

_LIST_REP = {
    "rules": ("rules", "name"),
    "forms": ("forms", "name"),
    "formgroups": ("formGroups", "name"),
    "contexts": ("contexts", "name"),
    "queries": ("queries", "name"),
    "sources": ("sources", "name"),
    "rolegroups": ("roleGroups", "name"),
    "workflows": ("workflows", "name"),
    "settings": ("settings", "name"),
}


def cmd_list(args):
    p = core.Project(args.project)
    kind = args.kind.lower()
    if kind == "pages":
        for node, _parent, path in core.iter_nodes(p.root_content):
            if node.get("pluginName") == "siteMapPage":
                core.out("%-40s alias=%-20s %s"
                         % (node.get("name"), node.get("alias"), node.get("identifier")))
        return
    if kind == "plugins":
        hist = Counter(n.get("pluginName") for n, _p, _pt in core.iter_nodes(p.root_content))
        for pn, n in hist.most_common():
            core.out("%5d  %s" % (n, pn))
        return
    if kind == "cruds":
        cf = p.cruds_file
        cruds = (cf.data.get("cruds", []) if cf else []) or []
        for c in cruds:
            core.out("%-30s %-30s methods=%d"
                     % (c.get("alias"), c.get("name"), len(c.get("methods", []) or [])))
        return
    if kind in ("schemas",):
        for s in p.db.get("schemas", []) or []:
            core.out("%-30s tables=%d sequences=%d"
                     % (s.get("name"), len(s.get("tables", []) or []),
                        len(s.get("sequences", []) or [])))
        return
    if kind == "tables":
        for s in p.db.get("schemas", []) or []:
            for t in s.get("tables", []) or []:
                core.out("%s.%s  (%d cols)" % (s.get("name"), t.get("name"),
                                               len(t.get("columns", []) or [])))
        return
    if kind in _LIST_REP:
        coll, name_field = _LIST_REP[kind]
        for o in p.rep.get(coll, []) or []:
            extra = ""
            if coll == "rules":
                extra = "  type=%s" % o.get("ruleType")
            elif coll == "contexts":
                extra = "  alias=%s" % o.get("alias")
            core.out("%-45s %s%s" % (o.get(name_field), o.get("identifier"), extra))
        return
    raise core.ToolError("unknown list kind: %s" % args.kind)


# ---------------------------------------------------------------------------
# show <kind> <id-or-name>
# ---------------------------------------------------------------------------


def _pp(obj):
    core.out(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_show(args):
    p = core.Project(args.project)
    kind = args.kind.lower()
    key = args.key
    if kind in ("node", "page"):
        node = core.find_node(p.root_content, key)
        # For readability, replace deep children with a count summary.
        shallow = {k: v for k, v in node.items() if k != "children"}
        shallow["_childCount"] = len(node.get("children", []) or [])
        shallow["_childPlugins"] = [c.get("pluginName") for c in node.get("children", []) or []]
        # decode inner JSON slots for convenience
        for slot in ("settings", "model"):
            inner = core.get_inner_json(node, slot)
            if inner:
                shallow["_%s_decoded" % slot] = inner
        _pp(shallow)
        return
    if kind == "rule":
        _pp(core.resolve_rep(p, "rules", key))
        return
    if kind == "form":
        _pp(core.resolve_rep(p, "forms", key))
        return
    if kind == "formgroup":
        _pp(core.resolve_rep(p, "formGroups", key))
        return
    if kind == "context":
        _pp(core.resolve_context(p, key))
        return
    if kind == "query":
        _pp(core.resolve_rep(p, "queries", key))
        return
    if kind == "source":
        _pp(core.resolve_rep(p, "sources", key))
        return
    if kind == "crud":
        cf = p.cruds_file
        cruds = (cf.data.get("cruds", []) if cf else []) or []
        match = [c for c in cruds if c.get("alias") == key or c.get("name") == key]
        if not match:
            raise core.ToolError("crud not found: %s" % key)
        _pp(match[0])
        return
    raise core.ToolError("unknown show kind: %s" % args.kind)
