"""Header actions and footer popups — html components in the site chrome (doc 37).

  * area `header` — icons left of the notifications bell, in their order. `kind` POPUP opens a panel under the icon
    with the item's own html component; `kind` PAGE goes to a page of the project (+ `params`) or to a `link`.
  * area `footer` — html components drawn with the footer, ALWAYS shown, placed by `side` (LEFT/RIGHT), `edge`
    (TOP/BOTTOM) and `positioning` (ABSOLUTE = by the footer, FIXED = by the screen).

⚠️ AN ITEM IS A PAGE'S OR THE BRANCH'S.
  * scope `page` — kept on the page's OWN header/footer node (every page carries its own copy, cloned from its layout),
    as the JSON text `{"items": [...]}` of the property `headerActions` / `footerPopups`; shown on that page only.
  * scope `global` — the branch's: an entry of `site-chrome.json` (`{"items": [{branch, area, uuid, order, item}]}`,
    the branch by NAME), shown on every page of the branch. Its component's `<plugin>` children hang under the hidden
    common virtual plugin `Nct header actions` / `Nct footer popups` (`branch.virtualPlugins[]`), which `add` makes.
A reader sees both in one order: every item has an `order`, given wide apart (ORDER_GAP); `mv` gives the moved item an
order between its new neighbours and leaves the rest — on every other page too — where they were.

An item's `html` + `studioModel` are EXACTLY an nct.html.plugin's `html` and `studioModel` (doc 24): the same runtime,
`<plugin>` tags, ctx.callRule / ctx.callBl, scripts, libraries, per-theme CSS. The components drawn on ONE node — a
page's on its header/footer, the global ones on the shared node — share its children, so a `<plugin id>` must not be
two plugins among them.

Commands:
  headerfooter list --area header|footer [--page P]
  headerfooter add  --area header --scope global|page [--page P] --title T [--title-loc hy_AM=…] --icon pe-7s-…
                    --kind popup|page [--size small|medium|large] [--target-page P [--params '?a=1'] | --link https://…]
                    [--html H|@file] [--studio JSON|@file] [--public | --authenticated | --role-group G …] [--id UUID]
  headerfooter add  --area footer --scope global|page [--page P] --name N [--side left|right] [--edge top|bottom]
                    [--positioning absolute|fixed] [--html …] [--studio …] [audience flags] [--id UUID]
  headerfooter set  --area A --id ID [--page P] (any add option — only what is given changes; --scope moves it)
  headerfooter rm   --area A --id ID [--page P]
  headerfooter mv   --area A --id ID --index N [--page P]
"""

import copy
import re

from . import core
from .quicklink_cmds import _resolve_page

# ---- the areas (names are data in the export and in the platform — never rename) ------------------------------
AREAS = {
    # The shared names are their own: an environment's publish matches shared components by NAME, and the project
    # templates already carry an "Nct footer" (a site footer).
    "header": {"plugin": "site.header.plugin", "shared": "Nct header actions", "property": "headerActions",
               "shared_identifier": "header-actions"},
    "footer": {"plugin": "site.footer.plugin", "shared": "Nct footer popups", "property": "footerPopups",
               "shared_identifier": "footer-popups"},
}
KINDS = ("POPUP", "PAGE")
SIZES = ("SMALL", "MEDIUM", "LARGE")
SIDES = ("LEFT", "RIGHT")
EDGES = ("TOP", "BOTTOM")
POSITIONINGS = ("ABSOLUTE", "FIXED")
SHARED_GROUP = "Layout"
# How far apart orders are given — a moved item takes one between its neighbours' and nothing else changes.
ORDER_GAP = 1000
DEFAULT_TEMPLATE = "architectui-html-pro"
PAGE_PLUGIN = "siteMapPage"

# An address a click may open — anything else (javascript:, data:) would run in the reader's page. A path of the site is
# ONE slash and a name: //host and /\host are another site's address written to look like a path.
SAFE_LINK_RE = re.compile(r"(?i)^(https?://|mailto:|tel:|/[^/\\])")
# What may follow a page's address — appended as written: a query, a fragment, more of the path; never //host.
SAFE_PARAMS_RE = re.compile(r"^(|[?#&].*|/[^/\\].*)$", re.S)
TEXT_FIELDS = ("icon", "html", "params", "link", "identifier", "name")


# ---------------------------------------------------------------------------
# the rules — the platform editor's own refusals, shared with `validate`
# ---------------------------------------------------------------------------


def item_problems(area, item, page_exists):
    """Why the platform's editor (and its MCP tool) would refuse `item`, or could not read it; [] when it would store
    it. `page_exists(identifier)` answers whether the project has a page with that content identifier."""
    problems = []
    for field in TEXT_FIELDS:
        if item.get(field) is not None and not isinstance(item.get(field), str):
            problems.append("%s must be text, not %s" % (field, type(item.get(field)).__name__))
    for field in ("titles", "roleAccess"):
        if item.get(field) is not None and not isinstance(item.get(field), dict):
            problems.append("%s must be an object, not %s" % (field, type(item.get(field)).__name__))
    if item.get("studioModel") is not None and not isinstance(item.get("studioModel"), dict):
        problems.append("studioModel is a JSON string or another non-object — the platform reads an object")
    if item.get("internal") is not None and not isinstance(item.get("internal"), bool):
        problems.append("internal must be true or false, not %r" % item.get("internal"))
    if problems:
        return problems
    if area == "header":
        titles = item.get("titles") or {}
        if not any(isinstance(v, str) and v.strip() for v in titles.values()):
            problems.append("no title (titles) — it is the icon's tooltip and what a screen reader says")
        if not (item.get("icon") or "").strip():
            problems.append("no icon")
        kind = item.get("kind")
        if kind not in KINDS:
            problems.append("kind must be one of %s, not %r" % (list(KINDS), kind))
        elif kind == "PAGE":
            if item.get("internal") is False:
                if not SAFE_LINK_RE.match((item.get("link") or "").strip()):
                    problems.append("link %r is not an address a click may open (https://…, mailto:…, tel:… or "
                                    "a path of this site, /…)" % item.get("link"))
            else:
                if not (item.get("identifier") or "").strip():
                    problems.append("a PAGE action without a page (identifier)")
                elif not page_exists(item.get("identifier")):
                    problems.append("the page %r it opens does not exist" % item.get("identifier"))
                if not SAFE_PARAMS_RE.match((item.get("params") or "").strip()):
                    problems.append("params %r must start with ? (or #, &, /more/of/the/path)" % item.get("params"))
        if item.get("popupSize") is not None and item.get("popupSize") not in SIZES:
            problems.append("popupSize must be one of %s" % list(SIZES))
    else:
        if not (item.get("name") or "").strip():
            problems.append("no name — only authors see it, in the list of popups")
        for field, allowed in (("side", SIDES), ("edge", EDGES), ("positioning", POSITIONINGS)):
            if item.get(field) is not None and item.get(field) not in allowed:
                problems.append("%s must be one of %s, not %r" % (field, list(allowed), item.get(field)))
    return problems


def draws_component(area, item):
    """A popup action and every footer popup draw their component; a page action is an icon and a link."""
    return area == "footer" or item.get("kind") == "POPUP"


def plugin_tags(item):
    """{id: (pluginName, vp)} of the `<plugin>` tags in the item's documents — the ones its component places."""
    docs = [item.get("html") if isinstance(item.get("html"), str) else ""]
    studio = item.get("studioModel") if isinstance(item.get("studioModel"), dict) else {}
    for doc in studio.get("docs") or []:
        if isinstance(doc, dict) and isinstance(doc.get("html"), str):
            docs.append(doc["html"])
    tags = {}
    for doc in docs:
        for match in re.finditer(r"<plugin\b([^>]*)>", doc):
            attrs = {k: (v1 if v1 is not None and q == '"' else v2)
                     for k, q, v1, v2 in ((m.group(1), m.group(2)[0], m.group(3), m.group(4))
                                         for m in re.finditer(r'(\w[\w-]*)\s*=\s*("([^"]*)"|\'([^\']*)\')',
                                                              match.group(1)))}
            if attrs.get("id"):
                tags.setdefault(attrs["id"], (attrs.get("name"), attrs.get("vp")))
    return tags


def clash_problems(area, item, beside):
    """The `<plugin id>`s `item` places as ANOTHER plugin than an item of `beside` (drawn on the same node) does —
    refused by the platform: one id is one child there."""
    if not draws_component(area, item):
        return []
    ours = plugin_tags(item)
    problems = []
    for other in beside:
        if not draws_component(area, other) or other.get("uuid") == item.get("uuid"):
            continue
        for pid, theirs in plugin_tags(other).items():
            if pid in ours and ours[pid] != theirs:
                problems.append("<plugin id=%r> is %s here and %s in item %s, drawn on the same node — give it an id "
                                "of its own" % (pid, ours[pid][0], theirs[0], other.get("uuid")))
    return problems


# ---------------------------------------------------------------------------
# where items live
# ---------------------------------------------------------------------------


def shared_virtual_plugin(project, area, branch=None):
    """The area's shared virtual plugin of `branch` (the first one by default) as the platform finds it — the one over
    a node of the area's plugin with the area's identifier; else, as it looks before it makes one, the hidden common
    one of the area's name over a node of its plugin — or None."""
    spec = AREAS[area]
    vps = [vp for vp in (branch or project.branches[0]).get("virtualPlugins") or []
           if isinstance(vp.get("content"), dict) and vp["content"].get("pluginName") == spec["plugin"]]
    return (next((vp for vp in vps if vp["content"].get("identifier") == spec["shared_identifier"]), None)
            or next((vp for vp in vps if vp.get("name") == spec["shared"] and vp.get("commonContent") is True
                     and vp.get("hidden") is True), None))


def page_node(project, page, area):
    """The page's OWN node of the area — the first node of the area's plugin in its tree, not in a page under it; the
    content it links to when it is linked — or None while the page has none."""
    queue = list(page.get("children") or [])
    while queue:
        node = queue.pop(0)
        if node.get("pluginName") == PAGE_PLUGIN:
            continue
        if node.get("pluginName") == AREAS[area]["plugin"]:
            link = node.get("linkContentIdentifier")
            # A link that leads nowhere is dropped by the platform as it draws the node: the node is then its own.
            return (_linked(project, link) if link else None) or node
        queue.extend(node.get("children") or [])
    return None


def _linked(project, unique_identifier):
    tops = [project.root_content] + [vp["content"] for vp in project.branches[0].get("virtualPlugins") or []
                                     if isinstance(vp.get("content"), dict)]
    for top in tops:
        for n, _p, _pt in core.iter_nodes(top):
            if n.get("uniqueIdentifier") == unique_identifier:
                return n
    return None


def read_items(node, area):
    """The items kept on `node` — `{"items": [...]}`, or a bare array as a hand-written export may hold."""
    data = core.get_inner_json(node, AREAS[area]["property"]) if node is not None else {}
    items = data.get("items") if isinstance(data, dict) else data
    return [it for it in (items or []) if isinstance(it, dict)]


def _write_items(node, area, items):
    clean = []
    for item in items:
        item = dict(item)
        item.pop("global", None)  # where an item is kept says it
        clean.append(item)
    core.set_inner_json(node, AREAS[area]["property"], {"items": clean})


def site_chrome_entries(project):
    """The entries of site-chrome.json — [] when the export has none."""
    jf = project.site_chrome_file
    data = jf.data if jf is not None else {}
    items = data.get("items") if isinstance(data, dict) else data
    return [it for it in (items or []) if isinstance(it, dict)]


def global_items(project, area):
    """The branch's global items of the area, each as an item dict with its uuid and order, by order."""
    branch = project.branches[0].get("name")
    items = []
    for entry in site_chrome_entries(project):
        if entry.get("branch") == branch and entry.get("area") == area and isinstance(entry.get("item"), dict):
            item = copy.deepcopy(entry["item"])
            item["uuid"] = entry.get("uuid")
            item["order"] = entry.get("order")
            items.append(item)
    items.sort(key=lambda it: (it.get("order") is None, it.get("order") or 0, str(it.get("uuid"))))
    return items


def _write_globals(project, area, items):
    """Makes the branch's global items of the area exactly `items` in site-chrome.json."""
    branch = project.branches[0].get("name")
    jf = project.ensure_site_chrome_file()
    kept = [e for e in site_chrome_entries(project) if not (e.get("branch") == branch and e.get("area") == area)]
    for item in items:
        body = {k: v for k, v in item.items() if k not in ("uuid", "order", "global")}
        entry = {"branch": branch, "area": area, "uuid": item["uuid"], "item": body}
        if item.get("order") is not None:
            entry["order"] = item["order"]
        kept.append(entry)
    jf.data = {"items": kept}
    project.mark(core.F_SITE_CHROME)


def seen(project, area, node):
    """What a reader of the page whose node of the area is `node` sees — its items and the branch's global ones, by
    order; a page's copy of a global item gives way to it. [(item, scope)]."""
    globals_ = [(it, "global") for it in global_items(project, area)]
    uuids = {it.get("uuid") for it, _s in globals_}
    own = [(it, "page") for it in read_items(node, area) if it.get("uuid") not in uuids] if node is not None else []
    both = globals_ + own
    both.sort(key=lambda pair: (pair[0].get("order") is None, pair[0].get("order") or 0))
    return both


def _ensure_shared_node(project, area):
    vp = shared_virtual_plugin(project, area)
    if vp is not None:
        return vp["content"]
    spec = AREAS[area]
    content = {
        "id": core.new_uuid(),
        "identifier": spec["shared_identifier"],
        "uniqueIdentifier": core.new_uuid(),
        "name": spec["shared_identifier"],
        "pluginName": spec["plugin"],
        "children": [],
        "properties": {},
        # Public: the node's own access is checked before any of its components is drawn; an item's audience is its own.
        "roleAccess": {"publicReadAccess": True, "authenticatedUserAccess": False, "accessors": {},
                       "roleGroupAccessors": {}},
        "order": 0,
        "active": True,
        "isBehaviour": False,
        "includedInParsis": False,
        "virtualContent": True,
        "treeOpened": False,
        "treeDisabled": False,
        "treeSelected": False,
        "branchId": project.branch_id(),
        "childPluginAdded": False,
    }
    project.branches[0].setdefault("virtualPlugins", []).append({
        "id": core.new_uuid(),
        "name": spec["shared"],
        "group": SHARED_GROUP,
        "commonContent": True,
        # Storage, not a component for the palette.
        "hidden": True,
        "isLayout": False,
        "useContentChildren": False,
        # Never null: the platform's plugin palette reads it from every virtual plugin of the branch.
        "templateNames": [_site_template(project)],
        "content": content,
    })
    project.mark(core.F_BRANCHES)
    core.out("created the shared %s node: virtual plugin %r" % (area, spec["shared"]))
    return content


def _site_template(project):
    """The site template the export's own virtual plugins are made for (tenant.json does not carry it)."""
    for vp in project.branches[0].get("virtualPlugins") or []:
        names = vp.get("templateNames")
        if isinstance(names, list) and names and names[0]:
            return names[0]
    return DEFAULT_TEMPLATE


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


class _Where:
    """The page named by --page and its node of the area (both None without --page)."""

    def __init__(self, project, args):
        self.page = _resolve_page(project.root_content, args.page) if getattr(args, "page", None) else None
        self.node = page_node(project, self.page, args.area) if self.page is not None else None
        if self.page is not None and self.node is None:
            core.out("note: page %r has no %s node of its own yet — it gets one with its layout"
                     % (self.page.get("name"), AREAS[args.area]["plugin"]))

    def require_node(self, area):
        if self.node is None:
            if self.page is None:
                raise core.ToolError("a page's own %s item needs its page: --page P" % area)
            raise core.ToolError("page %r has no %s node of its own" % (self.page.get("name"), AREAS[area]["plugin"]))
        return self.node


def cmd_list(args):
    p = core.Project(args.project)
    where = _Where(p, args)
    pairs = seen(p, args.area, where.node)
    if not pairs:
        core.out("no %s items%s" % (args.area, "" if where.page else " (global ones only — --page P adds a page's)"))
        return 0
    for i, (it, scope) in enumerate(pairs):
        if args.area == "header":
            what = it.get("kind") or "?"
            if it.get("kind") == "PAGE":
                what += " -> " + (it.get("link") if it.get("internal") is False else "page %s" % it.get("identifier"))
            title = next((v for v in (it.get("titles") or {}).values() if v), "")
            core.out("%d. %s  %-6s %-14s %s  [%s]" % (i, it.get("uuid"), scope, it.get("icon") or "-", title, what))
        else:
            core.out("%d. %s  %-6s %s  [%s %s %s]" % (i, it.get("uuid"), scope, it.get("name"),
                                                      it.get("positioning") or "FIXED", it.get("edge") or "BOTTOM",
                                                      it.get("side") or "RIGHT"))
    return 0


def cmd_add(args):
    p = core.Project(args.project)
    if args.scope is None:
        raise core.ToolError("--scope is required for a new item: global (every page of the branch) or page (--page P)")
    where = _Where(p, args)
    item = {"uuid": args.id or core.new_uuid()}
    if not core.looks_uuid(item["uuid"]):
        raise core.ToolError("--id must be a uuid, not %r" % item["uuid"])
    if any(it.get("uuid") == item["uuid"] for it, _s in seen(p, args.area, where.node)):
        raise core.ToolError("there is a %s item with id %s already" % (args.area, item["uuid"]))
    _apply(p, args, item)
    orders = [it.get("order") for it, _s in seen(p, args.area, where.node) if isinstance(it.get("order"), int)]
    item["order"] = max(orders) + ORDER_GAP if orders else 0
    _store(p, args.area, where, item, args.scope, None)
    _save(p, "added %s %s item %s" % (args.scope, args.area, item["uuid"]))


def cmd_set(args):
    p = core.Project(args.project)
    where = _Where(p, args)
    item, scope = _find(p, args.area, where, args.id)
    item = copy.deepcopy(item)
    _apply(p, args, item)
    _store(p, args.area, where, item, args.scope or scope, scope)
    _save(p, "updated %s item %s%s" % (args.area, args.id,
                                       " (now %s)" % args.scope if args.scope and args.scope != scope else ""))


def cmd_rm(args):
    p = core.Project(args.project)
    where = _Where(p, args)
    item, scope = _find(p, args.area, where, args.id)
    if scope == "global":
        remaining = [it for it in global_items(p, args.area) if it.get("uuid") != args.id]
        _write_globals(p, args.area, remaining)
        vp = shared_virtual_plugin(p, args.area)
        _remove_children(vp["content"] if vp else None, args.area, item, remaining)
    else:
        node = where.require_node(args.area)
        remaining = [it for it in read_items(node, args.area) if it.get("uuid") != args.id]
        _write_items(node, args.area, remaining)
        _remove_children(node, args.area, item, remaining)
    p.mark(core.F_BRANCHES)
    _save(p, "removed %s %s item %s, with the plugins only its component placed" % (scope, args.area, args.id))


def cmd_mv(args):
    p = core.Project(args.project)
    where = _Where(p, args)
    pairs = seen(p, args.area, where.node)
    at = next((i for i, (it, _s) in enumerate(pairs) if it.get("uuid") == args.id), None)
    if at is None:
        raise core.ToolError(_not_found(args.area, args.id, where))
    moved = pairs.pop(at)
    to = max(0, min(args.index, len(pairs)))
    pairs.insert(to, moved)
    # The platform's own rule: the moved item takes an order between its new neighbours', the rest keep theirs; when
    # they leave no room, what the page shows is numbered again, ORDER_GAP apart.
    position = {}
    room = _between(pairs[to - 1][0].get("order") if to > 0 else None,
                    pairs[to + 1][0].get("order") if to < len(pairs) - 1 else None, to == 0, to == len(pairs) - 1)
    if room is not None and all(isinstance(it.get("order"), int) for it, _s in pairs if it is not moved[0]):
        position[moved[0].get("uuid")] = room
    else:
        position = {it.get("uuid"): i * ORDER_GAP for i, (it, _s) in enumerate(pairs)}
    globals_ = global_items(p, args.area)
    if globals_:
        for it in globals_:
            it["order"] = position.get(it.get("uuid"), it.get("order"))
        _write_globals(p, args.area, globals_)
    if where.node is not None:
        own = read_items(where.node, args.area)
        for it in own:
            it["order"] = position.get(it.get("uuid"), it.get("order"))
        _write_items(where.node, args.area, own)
        p.mark(core.F_BRANCHES)
    _save(p, "moved %s item %s to place %d (order %s)" % (args.area, args.id, to, position[args.id]))


def _between(before, after, first, last):
    """An order strictly between two neighbours' (either absent at an end), or None when there is none."""
    if first and last:
        return 0 if before is None and after is None else None
    if first:
        return after - ORDER_GAP if isinstance(after, int) else None
    if last:
        return before + ORDER_GAP if isinstance(before, int) else None
    if not isinstance(before, int) or not isinstance(after, int) or after - before < 2:
        return None
    return before + (after - before) // 2


def _store(project, area, where, item, scope, previous_scope):
    """`item` stored in `scope`, moved there from `previous_scope` (None for a new one) with the plugins only its
    component placed — refused with the platform's reasons when the platform would refuse it."""
    if scope == "page":
        node = where.require_node(area)
        beside = [it for it in read_items(node, area) if it.get("uuid") != item["uuid"]]
    else:
        beside = [it for it in global_items(project, area) if it.get("uuid") != item["uuid"]]
    _refuse_problems(project, area, item, beside)
    old_node, rest = None, []
    if previous_scope == "page":
        old_node = where.require_node(area)
        rest = [it for it in read_items(old_node, area) if it.get("uuid") != item["uuid"]]
        if scope != "page":
            _write_items(old_node, area, rest)
    elif previous_scope == "global":
        rest = [it for it in global_items(project, area) if it.get("uuid") != item["uuid"]]
        vp = shared_virtual_plugin(project, area)
        old_node = vp["content"] if vp else None
        if scope != "global":
            _write_globals(project, area, rest)
    if scope == "page":
        new_node = where.node
        own = read_items(new_node, area)
        at = next((i for i, it in enumerate(own) if it.get("uuid") == item["uuid"]), None)
        if at is None:
            own.append(item)
        else:
            own[at] = item
        _write_items(new_node, area, own)
    else:
        globals_ = global_items(project, area)
        at = next((i for i, it in enumerate(globals_) if it.get("uuid") == item["uuid"]), None)
        if at is None:
            globals_.append(item)
        else:
            globals_[at] = item
        _write_globals(project, area, globals_)
        new_node = _ensure_shared_node(project, area) if draws_component(area, item) else None
    if previous_scope is not None and previous_scope != scope and old_node is not None and new_node is not None:
        _move_children(old_node, new_node, area, item, rest, scope)
    project.mark(core.F_BRANCHES)


def _find(project, area, where, item_id):
    for it in global_items(project, area):
        if it.get("uuid") == item_id:
            return it, "global"
    if where.node is not None:
        for it in read_items(where.node, area):
            if it.get("uuid") == item_id:
                return it, "page"
    raise core.ToolError(_not_found(area, item_id, where))


def _not_found(area, item_id, where):
    among = ("among the branch's global ones or page %r's" % where.page.get("name") if where.page
             else "among the branch's global ones (a page's own item needs --page P)")
    return "no %s item with id %r %s — `headerfooter list --area %s%s` lists them" % (
        area, item_id, among, area, " --page P" if where.page is None else "")


def _children_only_placed_by(node, area, item, others):
    ids = set(plugin_tags(item)) if draws_component(area, item) else set()
    for other in others:
        if draws_component(area, other):
            ids -= set(plugin_tags(other))
    return [c for c in node.get("children") or [] if c.get("identifier") in ids and not c.get("isBehaviour")]


def _remove_children(node, area, item, others):
    if node is None:
        return
    gone = _children_only_placed_by(node, area, item, others)
    node["children"] = [c for c in node.get("children") or [] if c not in gone]


def _move_children(old_node, new_node, area, item, still_on_old, scope):
    """An item that changes sides takes the children only its component placed to the node it is drawn on now."""
    there = {c.get("identifier") for c in new_node.get("children") or []}
    moved = _children_only_placed_by(old_node, area, item, still_on_old)
    old_node["children"] = [c for c in old_node.get("children") or [] if c not in moved]
    for child in moved:
        if child.get("identifier") in there:
            continue  # the new node has its own — another item there places it
        for n, _p, _pt in core.iter_nodes(child):
            n["virtualContent"] = scope == "global"
        new_node.setdefault("children", []).append(child)


def _apply(project, args, item):
    """Writes the options given onto `item`; an option not given leaves its field as it is."""
    if args.html is not None:
        item["html"] = core.read_value_arg(args.html)
    if args.studio is not None:
        studio = core.read_json_arg(args.studio)
        if not isinstance(studio, dict):
            raise core.ToolError("--studio must be a JSON object: {libs, docs, scripts, css} (doc 24)")
        item["studioModel"] = studio
    if args.public:
        item["roleAccess"] = {"publicReadAccess": True, "authenticatedUserAccess": False, "accessors": {},
                              "roleGroupAccessors": {}}
    elif args.authenticated:
        item["roleAccess"] = {"publicReadAccess": False, "authenticatedUserAccess": True, "accessors": {},
                              "roleGroupAccessors": {}}
    elif args.role_group:
        item["roleAccess"] = {"publicReadAccess": False, "authenticatedUserAccess": False, "accessors": {},
                              "roleGroupAccessors": {g: {"view": True, "edit": False, "advancedEdit": False}
                                                     for g in args.role_group}}
    if args.area == "header":
        _apply_header(project, args, item)
    else:
        _apply_footer(args, item)


def _apply_header(project, args, item):
    if args.name or args.side or args.edge or args.positioning:
        raise core.ToolError("--name/--side/--edge/--positioning are footer fields")
    titles = item.setdefault("titles", {})
    if args.title is not None:
        titles[project.default_locale()] = args.title
    for pair in args.title_loc or []:
        if "=" not in pair:
            raise core.ToolError("--title-loc takes locale=text, got %r" % pair)
        loc, text = pair.split("=", 1)
        titles[loc.strip()] = text
    if args.icon is not None:
        item["icon"] = args.icon
    if args.kind is not None:
        item["kind"] = args.kind.upper()
    if args.size is not None:
        item["popupSize"] = args.size.upper()
    if args.target_page is not None and args.link is not None:
        raise core.ToolError("pass --target-page or --link, not both")
    if args.target_page is not None:
        page = _resolve_page(project.root_content, args.target_page)
        item["identifier"] = page.get("identifier")
        item["internal"] = True
    if args.params is not None:
        item["params"] = args.params
    if args.link is not None:
        item["link"] = args.link
        item["internal"] = False


def _apply_footer(args, item):
    if any(v is not None for v in (args.title, args.icon, args.kind, args.size, args.target_page, args.link,
                                   args.params)) or args.title_loc:
        raise core.ToolError("--title/--icon/--kind/--size/--target-page/--link/--params are header fields")
    if args.name is not None:
        item["name"] = args.name
    if args.side is not None:
        item["side"] = args.side.upper()
    if args.edge is not None:
        item["edge"] = args.edge.upper()
    if args.positioning is not None:
        item["positioning"] = args.positioning.upper()


def page_ids(project):
    """The content identifiers of the project's pages — what a header action may open."""
    return {n.get("identifier") for n, _p, _pt in core.iter_nodes(project.root_content)
            if n.get("pluginName") == PAGE_PLUGIN}


def _refuse_problems(project, area, item, beside):
    pages = page_ids(project)
    problems = item_problems(area, item, lambda identifier: identifier in pages)
    problems += clash_problems(area, item, beside)
    if problems:
        raise core.ToolError("the platform would refuse this %s item: %s" % (area, "; ".join(problems)))


def _save(project, message):
    project.save()
    core.out(message)


def register(sub, add_project):
    """`headerfooter list|add|set|rm|mv` (doc 37); `add_project` adds the CLI's own --project option."""
    hf = sub.add_parser("headerfooter", help="header actions / footer popups — a page's or the branch's (doc 37)"
                        ).add_subparsers(dest="sub", metavar="<sub>")

    def common(sp, item_fields):
        add_project(sp)
        sp.add_argument("--area", required=True, choices=sorted(AREAS))
        sp.add_argument("--page", help="the page whose OWN items are meant (identifier, name or unique substring); "
                                       "without it: the branch's global items")
        if item_fields:
            sp.add_argument("--scope", choices=["global", "page"],
                            help="global — every page of the branch (site-chrome.json); page — --page's own. Required "
                                 "to add; on set, moves the item")
            sp.add_argument("--title", help="header: the title in the project's default language (the icon's tooltip)")
            sp.add_argument("--title-loc", action="append", metavar="LOCALE=TEXT", help="header: a title per locale")
            sp.add_argument("--icon", help="header: a pe-7s-* icon class, e.g. pe-7s-help1")
            sp.add_argument("--kind", choices=["popup", "page", "POPUP", "PAGE"], help="header: what a click does")
            sp.add_argument("--size", choices=["small", "medium", "large", "SMALL", "MEDIUM", "LARGE"],
                            help="header popup width (default medium)")
            sp.add_argument("--target-page", help="header PAGE: the page it opens (identifier, name or unique substring)")
            sp.add_argument("--params", help="header PAGE: appended to the page's address, e.g. ?status=open")
            sp.add_argument("--link", help="header PAGE: https://… (a new tab), mailto:…, tel:… or /a/path (in place)")
            sp.add_argument("--name", help="footer: the name authors know it by")
            sp.add_argument("--side", choices=["left", "right", "LEFT", "RIGHT"], help="footer (default right)")
            sp.add_argument("--edge", choices=["top", "bottom", "TOP", "BOTTOM"], help="footer (default bottom)")
            sp.add_argument("--positioning", choices=["absolute", "fixed", "ABSOLUTE", "FIXED"],
                            help="footer: by the footer (absolute) or by the screen (fixed, default)")
            sp.add_argument("--html", help="the component's main document, or @file")
            sp.add_argument("--studio", help="the component's studioModel JSON {libs, docs, scripts, css}, or @file")
            who = sp.add_mutually_exclusive_group()
            who.add_argument("--public", action="store_true", help="everyone sees it (the default for a new item)")
            who.add_argument("--authenticated", action="store_true", help="every signed-in user sees it")
            who.add_argument("--role-group", action="append", metavar="GROUP", help="only these role groups (+ authors)")

    sp = hf.add_parser("list", help="what a reader of --page sees (its own + the branch's global ones), in order")
    common(sp, False)
    sp.set_defaults(func=cmd_list)
    sp = hf.add_parser("add", help="add an item at the end (global: makes the shared Nct header actions / Nct footer popups node)")
    common(sp, True)
    sp.add_argument("--id", help="the item's uuid — to mirror one made live; a new one by default")
    sp.set_defaults(func=cmd_add)
    sp = hf.add_parser("set", help="change the options given of one item; --scope moves it")
    common(sp, True)
    sp.add_argument("--id", required=True)
    sp.set_defaults(func=cmd_set)
    sp = hf.add_parser("rm", help="remove one item, with the plugins only its component placed")
    common(sp, False)
    sp.add_argument("--id", required=True)
    sp.set_defaults(func=cmd_rm)
    sp = hf.add_parser("mv", help="move one item to a 0-based position in what --page shows")
    common(sp, False)
    sp.add_argument("--id", required=True)
    sp.add_argument("--index", required=True, type=int)
    sp.set_defaults(func=cmd_mv)
