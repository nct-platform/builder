"""Left-nav quick-link commands: quicklink list/add/add-external/rm.

The left navigation's menu is a JSON STRING in `properties.modelGroups.stringValue`
(decoding to `{"pagesModel": [PageModel, ...]}`) on a `site.kicker.plugin` node.

⚠️ THE NODE THAT ACTUALLY RENDERS IS THE SHARED COMMON ONE, NOT THE PER-PAGE ONES.
The branch ships a common virtual plugin named "Nct left nav"
(`branch.virtualPlugins[]` → its `content`, identifier `left-nav`); every page's
per-page `site.kicker.plugin` node carries a `linkContentIdentifier` pointing at that
shared node, so `PluginPanel.getContent()` resolves the render to the shared node and
the per-page `modelGroups` are DEAD DATA — never read. These commands therefore edit the
shared "Nct left nav" node (via `_target_nav_nodes`), falling back to per-page nodes only
in older exports that lack the common plugin. See ../17-left-nav-quick-links.md.
"""

import json

from . import core

LEFT_NAV_PLUGIN = "site.kicker.plugin"
LEFT_NAV_IDENTIFIER = "left-nav"
MODELGROUPS_SLOT = "modelGroups"

DEFAULT_LINK_ICON = "pe-7s-angle-right"
DEFAULT_GROUP_ICON = "globe"


# ---------------------------------------------------------------------------
# left-nav node collection + modelGroups (de)serialization
# ---------------------------------------------------------------------------


LEFT_NAV_VIRTUAL_PLUGIN_NAME = "Nct left nav"


def _iter_left_nav_nodes(root):
    """Yield every `site.kicker.plugin` node whose identifier == left-nav."""
    for node, _parent, _path in core.iter_nodes(root):
        if (node.get("pluginName") == LEFT_NAV_PLUGIN
                and node.get("identifier") == LEFT_NAV_IDENTIFIER):
            yield node


def _shared_left_nav_node(project):
    """The COMMON virtual-plugin content node that actually renders on every page.

    ⚠️ Every per-page `site.kicker.plugin` node carries a `linkContentIdentifier`
    pointing at THIS shared node (`branch.virtualPlugins[] name="Nct left nav"` → its
    `content`), so `PluginPanel.getContent()` resolves the render to it and the per-page
    `modelGroups` are DEAD DATA — never read at runtime. Quick links MUST be written here.
    Returns the shared content node dict, or None (older exports without the common plugin).
    """
    for vp in (project.branches[0].get("virtualPlugins") or []):
        if vp.get("name") == LEFT_NAV_VIRTUAL_PLUGIN_NAME and isinstance(vp.get("content"), dict):
            return vp["content"]
    return None


def _target_nav_nodes(project):
    """The node(s) to edit: the shared common left-nav if present (the one that renders),
    else fall back to the per-page kicker nodes (older exports)."""
    shared = _shared_left_nav_node(project)
    if shared is not None:
        return [shared]
    return list(_iter_left_nav_nodes(project.root_content))


def _read_model_groups(node):
    """Return the parsed `{"pagesModel": [...]}` from a left-nav node, or {}."""
    return core.get_inner_json(node, MODELGROUPS_SLOT)


def _root_own_left_nav_nodes(root):
    """left-nav nodes in the ROOT/Home page's OWN layout (do NOT descend into
    child siteMapPages). The root's own nav is the one rendered on the page the
    project 'front door' lands on, so it must be populated."""
    out = []

    def walk(n, is_root):
        if not is_root and n.get("pluginName") == "siteMapPage":
            return
        if (n.get("pluginName") == LEFT_NAV_PLUGIN
                and n.get("identifier") == LEFT_NAV_IDENTIFIER):
            out.append(n)
        for c in n.get("children") or []:
            walk(c, False)

    walk(root, True)
    return out


def _pages_model(mg):
    """Return the pagesModel list of a decoded modelGroups object (may be [])."""
    if not isinstance(mg, dict):
        return []
    pm = mg.get("pagesModel")
    return pm if isinstance(pm, list) else []


def _write_model_groups(node, mg):
    core.set_inner_json(node, MODELGROUPS_SLOT, mg)


# ---------------------------------------------------------------------------
# siteMapPage resolution (link target identifier)
# ---------------------------------------------------------------------------


def _resolve_page(root, key):
    """Resolve a page key to a siteMapPage node (identifier, exact name, then
    unique substring). Errors if not found or ambiguous. Only siteMapPage nodes
    are considered so a link target is always a real page.
    """
    pages = [n for n, _p, _pt in core.iter_nodes(root)
             if n.get("pluginName") == "siteMapPage"]
    by_id = [n for n in pages if n.get("identifier") == key]
    if len(by_id) == 1:
        return by_id[0]
    if len(by_id) > 1:
        raise core.ToolError("ambiguous page %r: %d matches by identifier" % (key, len(by_id)))
    by_name = [n for n in pages if (n.get("name") or "") == key]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        raise core.ToolError("ambiguous page %r: %d exact-name matches" % (key, len(by_name)))
    kl = key.lower()
    by_sub = [n for n in pages if kl and kl in (n.get("name") or "").lower()]
    if len(by_sub) == 1:
        return by_sub[0]
    if len(by_sub) > 1:
        names = ", ".join(sorted({n.get("name", "?") for n in by_sub}))[:200]
        raise core.ToolError("ambiguous page %r: %d name-substring matches (%s)"
                             % (key, len(by_sub), names))
    raise core.ToolError("siteMapPage not found: %r" % key)


# ---------------------------------------------------------------------------
# PageModel construction (group / link)
# ---------------------------------------------------------------------------


def _localized_map(locales, name, icon, per_locale=None):
    """Build linkModel.localizedMap covering every tenant locale.

    per_locale: optional {locale: label} for a PROPERLY multilingual nav (each locale its OWN text). When absent,
    `name` is used for every locale — correct only for a SINGLE-language project; for 2+ locales that produces the
    "one language shows under all locales" bug (doc 20), so pass per-locale labels (`--label-loc`) there.
    """
    if per_locale:
        default = per_locale.get(locales[0]) if locales else name
        name_map = {loc: (per_locale.get(loc) or default or name) for loc in locales}
    else:
        name_map = {loc: name for loc in locales}
    return {
        "name": name_map,
        "icon": {loc: icon for loc in locales},
    }


def _new_group(name, icon, order, name_loc=None, locales=None):
    g = {
        "order": order,
        "name": name,
        "uuid": core.new_uuid(),
        "icon": icon,
        "heading": False,
        "children": [],
    }
    # A nav GROUP heading is localized the same way a link is — via localizedMap.name. Without it the
    # heading shows the single `name` (one language) under EVERY locale (doc 20 #1 loc bug). Attach a
    # per-locale map when the caller supplies --group-loc on a multi-locale project.
    if locales:
        _attach_group_localized_map(g, name, name_loc, locales, icon)
    return g


def _attach_group_localized_map(group, name, name_loc, locales, icon):
    """Author/refresh the heading's per-locale map, MERGING over whatever is already there.

    Merging matters when a locale is added to the tenant AFTER the nav was built: the group then carries a
    map that covers only the old locales, and the heading falls back to one language under the new one. An
    explicit --group-loc value always wins; an existing value is kept; only what is still missing falls back
    to the default. (Replacing the map wholesale would throw away hand-tuned headings.)
    """
    if not locales:
        return
    have = (group.get("localizedMap") or {}).get("name") or {}
    have_icon = (group.get("localizedMap") or {}).get("icon") or {}
    default = (name_loc or {}).get(locales[0]) or have.get(locales[0]) or name
    group["localizedMap"] = {
        "name": {loc: ((name_loc or {}).get(loc) or have.get(loc) or default) for loc in locales},
        "icon": {loc: (have_icon.get(loc) or icon) for loc in locales},
    }


def _find_group(pages_model, name):
    """Return the top-level group PageModel with this name, or None. A group is
    a node with children and no linkModel."""
    for item in pages_model:
        if not isinstance(item, dict):
            continue
        if item.get("linkModel"):
            continue
        if item.get("name") == name:
            return item
    return None


def _next_order(siblings):
    if not siblings:
        return 0
    return max((s.get("order", 0) or 0) for s in siblings if isinstance(s, dict)) + 1


def _build_link(locales, label, icon, order, parent_uuid,
                identifier=None, internal=True, link=None, params=None, per_locale=None):
    link_model = {
        "icon": icon,
        "name": label,
        "internal": internal,
        "needToBeSaved": True,
        "localizedMap": _localized_map(locales, label, icon, per_locale),
    }
    if internal:
        link_model["identifier"] = identifier
    else:
        link_model["link"] = link
    if params:
        link_model["params"] = params
    page_model = {
        "order": order,
        "name": label,
        "uuid": core.new_uuid(),
        "icon": icon,
        "heading": False,
        # ⛔ THE LABEL THE SIDEBAR RENDERS COMES FROM THIS MAP, NOT FROM linkModel's.
        # A nav item is a `PageModel extends LocalizedBean`, and the label is read with
        # `getLocalized("name", locale)` — `localizedMap["name"][locale]`, falling back to the RAW
        # `name` property when the map has no entry. Localizing only the inner `linkModel` therefore
        # leaves the item showing `name` — one language — under EVERY locale, which is exactly what a
        # three-locale project looks like when it renders entirely in the first one. The platform's
        # own nav carries the map on BOTH objects (compare any baseline link: `Database`, `Rules`),
        # so both are written here. Group headings get theirs in `_attach_group_localized_map`.
        "localizedMap": {"name": dict(_localized_map(locales, label, icon, per_locale)["name"])},
        "linkModel": link_model,
        "children": [],
    }
    if parent_uuid is not None:
        page_model["parentUuid"] = parent_uuid
    return page_model


def _link_target(item):
    """Return (internal, identifier-or-url) for a link PageModel, or None if it
    is not a link."""
    lm = item.get("linkModel") if isinstance(item, dict) else None
    if not lm:
        return None
    if lm.get("internal", True):
        return (True, lm.get("identifier"))
    return (False, lm.get("link"))


def _container_for_group(pages_model, group_name, group_loc=None, locales=None):
    """Return (siblings-list, parent_uuid) for where a new link goes, creating
    the group in pages_model if group_name is given and missing. When
    group_name is None, links go at the top level (parentUuid omitted).
    group_loc/locales localize the group HEADING (adds/upgrades localizedMap)."""
    if not group_name:
        return pages_model, None
    group = _find_group(pages_model, group_name)
    if group is None:
        group = _new_group(group_name, DEFAULT_GROUP_ICON, _next_order(pages_model),
                           name_loc=group_loc, locales=locales)
        pages_model.append(group)
    elif locales and (group_loc or not group.get("localizedMap")
                      or set(locales) - set(((group.get("localizedMap") or {}).get("name") or {}))):
        # Upgrade an existing heading when it was created before --group-loc, when the caller passes explicit
        # per-locale text, or when the tenant gained a locale the stored map does not cover yet. The attach is
        # a MERGE, so nothing already authored is lost.
        _attach_group_localized_map(group, group.get("name"), group_loc, locales, group.get("icon") or DEFAULT_GROUP_ICON)
    children = group.setdefault("children", [])
    if not isinstance(children, list):
        children = []
        group["children"] = children
    return children, group.get("uuid")


def _already_has_target(siblings, internal, target):
    """Idempotency: True if a link with the same internal/target already exists
    among siblings."""
    for item in siblings:
        info = _link_target(item)
        if info is None:
            continue
        if info == (internal, target):
            return True
    return False


# ---------------------------------------------------------------------------
# quicklink list
# ---------------------------------------------------------------------------


def _render_tree(pages_model, out_lines, depth=0):
    for item in pages_model:
        if not isinstance(item, dict):
            continue
        indent = "  " * depth
        info = _link_target(item)
        if info is None:
            # group
            out_lines.append("%s[%s]" % (indent, item.get("name") or "?"))
        else:
            internal, target = info
            suffix = ("-> %s" % target) if internal else ("=> %s" % target)
            out_lines.append("%s- %s  (%s)" % (indent, item.get("name") or "?", suffix))
        kids = item.get("children") or []
        if isinstance(kids, list) and kids:
            _render_tree(kids, out_lines, depth + 1)


def cmd_quicklink_list(args):
    p = core.Project(args.project)
    root = p.root_content
    nodes = _target_nav_nodes(p)
    if not nodes:
        core.out("(no left-nav nodes found)")
        return

    if args.all:
        shown = 0
        for node in nodes:
            mg = _read_model_groups(node)
            pm = _pages_model(mg)
            if not pm:
                continue
            shown += 1
            lines = ["left-nav node <%s>:" % node.get("uniqueIdentifier")]
            _render_tree(pm, lines)
            core.out("\n".join(lines))
        empties = sum(1 for n in nodes if not _pages_model(_read_model_groups(n)))
        core.out("\n%d left-nav node(s): %d populated, %d empty" % (len(nodes), shown, empties))
        return

    # Default: distinct trees, deduped by their serialized modelGroups string,
    # with the count of pages each is on.
    groups = {}  # serialized string -> [count, pages_model]
    empties = 0
    for node in nodes:
        mg = _read_model_groups(node)
        pm = _pages_model(mg)
        if not pm:
            empties += 1
            continue
        key = json.dumps(mg, ensure_ascii=False, sort_keys=True)
        if key not in groups:
            groups[key] = [0, pm]
        groups[key][0] += 1

    if not groups:
        core.out("(no populated left-nav; %d empty node(s))" % empties)
        return

    lines = []
    for i, (_key, (count, pm)) in enumerate(groups.items(), 1):
        lines.append("=== tree %d (on %d page%s) ===" % (i, count, "" if count == 1 else "s"))
        _render_tree(pm, lines)
    lines.append("")
    lines.append("%d left-nav node(s): %d distinct populated tree(s), %d empty"
                 % (len(nodes), len(groups), empties))
    core.out("\n".join(lines))


# ---------------------------------------------------------------------------
# quicklink add / add-external
# ---------------------------------------------------------------------------


def _apply_link(nodes, locales, group_name, label, icon, internal,
                target, params, per_locale=None, group_loc=None):
    """Add the link to every populated left-nav node (idempotent). Returns the
    number of nodes updated."""
    updated = 0
    for node in nodes:
        mg = _read_model_groups(node)
        pm = _pages_model(mg)
        if not pm:
            continue  # leave empty-{} navs untouched
        # mg may be a plain dict lacking a proper pagesModel list; normalize.
        if not isinstance(mg, dict):
            continue
        mg.setdefault("pagesModel", pm)
        siblings, parent_uuid = _container_for_group(pm, group_name, group_loc=group_loc, locales=locales)
        if _already_has_target(siblings, internal, target):
            continue  # idempotent: same target already present under this group
        order = _next_order(siblings)
        if internal:
            link = _build_link(locales, label, icon, order, parent_uuid,
                               identifier=target, internal=True, params=params, per_locale=per_locale)
        else:
            link = _build_link(locales, label, icon, order, parent_uuid,
                               internal=False, link=target, params=params, per_locale=per_locale)
        siblings.append(link)
        _write_model_groups(node, mg)
        updated += 1
    return updated


def _parse_label_loc(pairs):
    """['en_US=Home','hy_AM=Տուն'] -> {'en_US':'Home','hy_AM':'Տուն'}."""
    out = {}
    for item in (pairs or []):
        if "=" not in item:
            raise core.ToolError("--label-loc must be 'locale=text' (got %r)" % item)
        loc, txt = item.split("=", 1)
        out[loc.strip()] = txt
    return out


def _resolve_labels(args, locales):
    """Return (primary_label, per_locale|None). --label = one string (fine for a SINGLE locale; fans to all);
    --label-loc = per-locale (required for a correct MULTILINGUAL nav — doc 20). Warns on the multilingual trap."""
    per_locale = _parse_label_loc(getattr(args, "label_loc", None))
    label = getattr(args, "label", None)
    if not label and not per_locale:
        raise core.ToolError("give --label (single) or --label-loc locale=text (repeatable, per-locale)")
    if not label:
        label = per_locale.get(locales[0]) if locales and per_locale.get(locales[0]) else next(iter(per_locale.values()))
    if len(locales) > 1 and not per_locale:
        core.out("  WARNING: %d locales but a single --label — it is copied into EVERY locale, so the UI shows "
                 "this language under all locales (doc 20). Pass --label-loc %s=… for each locale."
                 % (len(locales), "=… --label-loc ".join(locales)))
    return label, (per_locale or None)


def cmd_quicklink_add(args):
    p = core.Project(args.project)
    root = p.root_content
    nodes = _target_nav_nodes(p)
    if not nodes:
        raise core.ToolError("no left-nav nodes found in this project")

    page = _resolve_page(root, args.page)
    target = page.get("identifier")
    icon = args.icon or DEFAULT_LINK_ICON
    locales = p.locales()
    label, per_locale = _resolve_labels(args, locales)
    group_loc = _parse_label_loc(getattr(args, "group_loc", None)) or None
    if args.group and len(locales) > 1 and not group_loc:
        core.out("  WARNING: group %r heading is single-language — pass --group-loc %s=… so the nav "
                 "section header localizes too (else it shows one language under all locales, doc 20)."
                 % (args.group, "=… --group-loc ".join(locales)))

    updated = _apply_link(nodes, locales, args.group, label, icon,
                          True, target, args.params, per_locale=per_locale, group_loc=group_loc)
    p.mark(core.F_BRANCHES)
    p.save()
    where = ("group %r" % args.group) if args.group else "top level"
    core.out("quick link added: %r -> page %s <%s> under %s; %d left-nav node(s) updated"
             % (label, page.get("name"), target, where, updated))
    # A link the user can't reach is invisible. The root/Home page's OWN nav is what
    # the project front door lands on — if it's empty, the CDD links won't show there.
    root_navs = _root_own_left_nav_nodes(root)
    if root_navs and not any(_pages_model(_read_model_groups(n)) for n in root_navs):
        core.out("  WARNING: the root/Home page's own left-nav is EMPTY — this link was "
                 "added only to other pages' navs. Populate the root nav, or set the "
                 "root Redirect to a page whose nav is populated (see 17-left-nav-quick-links.md).")


def cmd_quicklink_add_external(args):
    p = core.Project(args.project)
    root = p.root_content
    nodes = _target_nav_nodes(p)
    if not nodes:
        raise core.ToolError("no left-nav nodes found in this project")

    icon = args.icon or DEFAULT_LINK_ICON
    locales = p.locales()
    label, per_locale = _resolve_labels(args, locales)
    updated = _apply_link(nodes, locales, args.group, label, icon,
                          False, args.url, None, per_locale=per_locale)
    p.mark(core.F_BRANCHES)
    p.save()
    where = ("group %r" % args.group) if args.group else "top level"
    core.out("external quick link added: %r => %s under %s; %d left-nav node(s) updated"
             % (label, args.url, where, updated))


# ---------------------------------------------------------------------------
# quicklink rm
# ---------------------------------------------------------------------------


def _prune_links(pages_model, label):
    """Remove link PageModels whose name/linkModel.name matches label, at every
    depth. Returns the number removed. Groups are kept."""
    removed = 0
    kept = []
    for item in pages_model:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        info = _link_target(item)
        lm = item.get("linkModel") or {}
        is_link = info is not None
        matches = is_link and (item.get("name") == label or lm.get("name") == label)
        if matches:
            removed += 1
            continue
        kids = item.get("children")
        if isinstance(kids, list) and kids:
            removed += _prune_links(kids, label)
        kept.append(item)
    pages_model[:] = kept
    return removed


def cmd_quicklink_rm(args):
    p = core.Project(args.project)
    root = p.root_content
    nodes = _target_nav_nodes(p)
    if not nodes:
        raise core.ToolError("no left-nav nodes found in this project")

    total_removed = 0
    nodes_touched = 0
    for node in nodes:
        mg = _read_model_groups(node)
        pm = _pages_model(mg)
        if not pm or not isinstance(mg, dict):
            continue
        removed = _prune_links(pm, args.label)
        if removed:
            mg["pagesModel"] = pm
            _write_model_groups(node, mg)
            total_removed += removed
            nodes_touched += 1
    if total_removed:
        p.mark(core.F_BRANCHES)
        p.save()
    core.out("quick link removed: %r; %d link(s) across %d left-nav node(s)"
             % (args.label, total_removed, nodes_touched))
