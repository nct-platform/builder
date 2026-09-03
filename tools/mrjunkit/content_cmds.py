"""Content-tree commands: page add/rm, node add/rm/set-settings/patch-settings,
node set-model/patch-model. Encodes the settings-vs-model hard rule (§2)."""

import copy
import json
import os
import shutil

from . import core

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "page_template.json")

# Plugins whose config lives in properties.model.stringValue (§2 / FINDINGS).
MODEL_SLOT_PLUGINS = {
    "crud.table.plugin",
    "crud.tree.plugin",
    "process.table.pluin",  # preserve the real misspelling
}

# A crud.table/tree/process node's config is ALSO mirrored into a rep-objects
# settings[] entry (join key setting.name == node.uniqueIdentifier). The runtime
# renders from properties.model (doc 04), but the platform IMPORTER still
# deserializes the mirror: SettingsDto.content is a Jackson **ObjectNode** (a JSON
# OBJECT), NOT a string. Storing a JSON *string* there aborts the entire import
# (MismatchedInputException Qss["settings"]->SettingsDto["content"]) — the
# REPORT-path never runs, so sources aren't saved and project-db.dump isn't
# restored. set-model/patch-model keep this mirror in sync (content = parsed
# OBJECT) so no one has to hand-roll it and get the type wrong.
MIRROR_SETTING_TYPE = {
    "crud.table.plugin": "CrudTable",
    "crud.tree.plugin": "CrudTree",
    "process.table.pluin": "ProcessTable",
}


def sync_crud_mirror(project, node):
    """Sync the rep-objects.settings[] mirror of a crud.table/tree/process node
    from its properties.model. content is written as a JSON OBJECT (never a
    string). Updates the mirror in place if present, else creates one. Returns
    True if rep-objects was touched (so the caller marks F_REP dirty)."""
    stype = MIRROR_SETTING_TYPE.get(node.get("pluginName"))
    if stype is None:
        return False
    uid = node.get("uniqueIdentifier")
    if not uid:
        return False
    model = core.get_inner_json(node, "model")  # parsed dict (the OBJECT form)
    settings = project.rep.setdefault("settings", [])
    for s in settings:
        if s.get("name") == uid and s.get("type") in MIRROR_SETTING_TYPE.values():
            if s.get("content") != model:
                s["content"] = model
                s["modificationTime"] = core.now_iso()
            return True
    settings.append(core.new_rep_object(project, {
        "name": uid,
        "type": stype,
        "content": model,
        "deleted": False,
    }))
    return True

# Plugins whose config lives in properties.Javascript.stringValue.
# ChartJsPlugin writes its model via ReportServiceUtils.JS_MODEL_NAME = "Javascript"
# (NOT "model"): a chart authored into `model` renders empty. Verified: real erp
# chart.js.plugin node carries properties.Javascript (~12KB) and no `model`.
# NOTE: global.replacement.plugin is NOT here — GlobalReplacementPlugin.java only
# injects a ChartJsService field, it never reads/writes JS_MODEL_NAME. Every
# global.replacement.plugin node in the exports carries ONLY the baseline
# className/styleName/tagProperties (no Javascript/model/settings blob).
JAVASCRIPT_SLOT_PLUGINS = {
    "chart.js.plugin",
}

# Plugins whose config lives in properties.filterFormModel.stringValue (inner
# JSON = a serialized FilterFormDto). FilterFormPlugin.java reads/writes it via
# getContent().getJsonProperty("filterFormModel", FilterFormDto.class, ...).
# Verified: real filter.form nodes carry properties.filterFormModel (STRING slot
# holding a JSON object), never settings/model.
FILTERFORMMODEL_SLOT_PLUGINS = {
    "dynaform.filter.form.plugin",
}

# Plugins whose config lives in properties.tabModel.stringValue (inner JSON =
# {"items":[{id,name,...}]}). Verified: every nct.tab.plugin node in a working
# project carries config ONLY in
# properties.tabModel (a STRING slot holding a JSON object), never settings/model
# — so a tab config routed to `settings` renders an empty tab strip.
TABMODEL_SLOT_PLUGINS = {
    "nct.tab.plugin",
}

# Container/reference plugins that carry NO inner-JSON config blob at all. Their
# configuration lives in top-level scalar properties (e.g. form.plugin's
# formModeIdentifier STRING, list.item.plugin's isParsis/reuseItems BOOLEANs),
# not in a settings/model JSON slot. `node add` must NOT invent a settings slot
# for these, and rejects --settings/--model since there is nowhere to put it.
# Verified: no form.plugin / list.item.plugin node in any export carries a
# settings/model/filterFormModel blob. Likewise these three reference plugins
# carry ONLY the baseline className/styleName/tagProperties: the landing plugin binds its form group via the
# ?group= query param, the rule-script plugin binds its rule via ?rule=, and the
# global.replacement plugin's editor mutates query parameters — none persist a
# content config blob.
NO_CONFIG_SLOT_PLUGINS = {
    "dynaform.form.plugin",
    "dynaform.list.item.plugin",
    "dynaform.form.groups.landingplugin",
    "executor.rule.script.plugin",
    "global.replacement.plugin",
}

# Universal baseline STRING property slots every real plugin node carries
# (empty stringValue). Verified: 1701/1703 plugin-suffixed nodes carry all three.
BASELINE_STRING_SLOTS = ("className", "styleName", "tagProperties")


def slot_for_plugin(plugin_name):
    """Return the config slot for a plugin, or None if it has no inner-JSON slot.

    Possible slots: 'Javascript', 'model', 'filterFormModel', 'tabModel', or
    'settings'. Returns None for container/reference plugins
    (NO_CONFIG_SLOT_PLUGINS) whose config lives in top-level scalar properties,
    not an inner-JSON blob.
    """
    if plugin_name in NO_CONFIG_SLOT_PLUGINS:
        return None
    if plugin_name in JAVASCRIPT_SLOT_PLUGINS:
        return "Javascript"
    if plugin_name in FILTERFORMMODEL_SLOT_PLUGINS:
        return "filterFormModel"
    if plugin_name in TABMODEL_SLOT_PLUGINS:
        return "tabModel"
    if plugin_name in MODEL_SLOT_PLUGINS:
        return "model"
    return "settings"


# ---------------------------------------------------------------------------
# id regeneration for cloned subtrees
# ---------------------------------------------------------------------------


regen_ids = core.regen_ids          # canonical implementation lives in core
_looks_uuid = core.looks_uuid


def _content_container(page_node):
    """Return the inner nct.parsis.plugin that hosts this page's content.

    Only the page's OWN layout is searched: we never descend into nested
    siteMapPage children, since each child page owns its own content
    container (descending would drop new nodes into the wrong page).
    """
    found = []

    def walk(n, is_root):
        # Do not cross into a nested page boundary.
        if not is_root and n.get("pluginName") == "siteMapPage":
            return
        if n.get("pluginName") == "nct.parsis.plugin":
            found.append(n)
        for c in n.get("children", []) or []:
            walk(c, False)

    walk(page_node, True)
    # The page's own content container is the first one found in its layout.
    return found[0] if found else page_node


# ---------------------------------------------------------------------------
# page add / rm
# ---------------------------------------------------------------------------


def cmd_page_add(args):
    p = core.Project(args.project)
    root = p.root_content
    parent = root if args.parent in ("root", "ROOT") else core.find_node(root, args.parent)

    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as fh:
        page = json.load(fh)
    page = copy.deepcopy(page)
    regen_ids(page, p.branch_id())

    page["name"] = args.name
    alias = args.alias or _slugify(args.name)
    page["alias"] = alias
    page["order"] = core.next_order(parent)
    page["active"] = True

    # page title/description
    loc = p.default_locale()
    props = page.setdefault("properties", {})
    for key in ("pageTitle", "pageDescription"):
        slot = props.setdefault(key, {
            "fieldPanelClass": "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseLocalizedTextFieldPanel",
            "arguments": {}, "key": key, "localizedStringValue": {},
            "propertyType": "LOCALIZED_STRING", "required": False, "hidden": False,
        })
        slot.setdefault("localizedStringValue", {})[loc] = args.name
    if args.layout:
        lslot = props.setdefault("layout", core.make_property_slot("layout", ""))
        lslot["stringValue"] = args.layout

    # roleAccess: clone parent's, then apply auth/public
    page["roleAccess"] = copy.deepcopy(parent.get("roleAccess", _default_role_access()))
    if args.auth:
        page["roleAccess"]["publicReadAccess"] = False
        page["roleAccess"]["authenticatedUserAccess"] = True
    elif args.public:
        page["roleAccess"]["publicReadAccess"] = True
        page["roleAccess"]["authenticatedUserAccess"] = False

    parent.setdefault("children", []).append(page)
    p.mark(core.F_BRANCHES)
    p.save()
    container = _content_container(page)
    core.out("page added: %s (alias=%s)\n  identifier=%s\n  content container id=%s"
             % (args.name, alias, page["identifier"], container.get("identifier")))


def cmd_page_rm(args):
    p = core.Project(args.project)
    root = p.root_content
    node = core.find_node(root, args.id)
    if node is root:
        raise core.ToolError("cannot remove the root page")
    parent = core.find_parent(root, node)
    parent["children"] = [c for c in parent["children"] if c is not node]
    p.mark(core.F_BRANCHES)
    p.save()
    core.out("page removed: %s <%s>" % (node.get("name"), node.get("identifier")))


def cmd_page_mv(args):
    """Reparent a page (and its whole subtree) to a new parent — the toolkit has no
    other move primitive. Preserves the node's identifier/uniqueIdentifier and every
    child id (so form pages keep formModeIdentifier and forms[].contentIdentifier
    still resolve); only the parent link, order, and branchId change. Used to move
    form pages off the root under their form-group landing / table page.
    """
    p = core.Project(args.project)
    root = p.root_content
    node = core.find_node(root, args.id)
    if node is None:
        raise core.ToolError("page %r not found" % args.id)
    if node is root:
        raise core.ToolError("cannot move the root page")
    new_parent = root if args.to_parent in ("root", "ROOT") else core.find_node(root, args.to_parent)
    if new_parent is None:
        raise core.ToolError("target parent %r not found" % args.to_parent)
    if new_parent is node:
        raise core.ToolError("a page cannot be its own parent")
    # guard against moving a node under its own descendant (would detach the subtree)
    for desc, _pp, _pt in core.iter_nodes(node):
        if desc is new_parent:
            raise core.ToolError("cannot move %r under its own descendant %r"
                                 % (node.get("name"), new_parent.get("name")))
    old_parent = core.find_parent(root, node)
    if old_parent is new_parent:
        core.out("page %r is already a child of %r — nothing to do"
                 % (node.get("name"), new_parent.get("name")))
        return
    old_parent["children"] = [c for c in old_parent.get("children", []) if c is not node]
    node["order"] = core.next_order(new_parent)
    node["branchId"] = new_parent.get("branchId", node.get("branchId"))
    new_parent.setdefault("children", []).append(node)
    p.mark(core.F_BRANCHES)
    p.save()
    core.out("page moved: %s <%s>  parent %r -> %r"
             % (node.get("name"), (node.get("identifier") or "")[:8],
                old_parent.get("name"), new_parent.get("name")))


# ---------------------------------------------------------------------------
# page set-redirect — wire the project "front door"
# ---------------------------------------------------------------------------


def _child_pages(node):
    """Direct child siteMapPages of a page node (skips layout plugins)."""
    return [c for c in (node.get("children") or []) if c.get("pluginName") == "siteMapPage"]


def resolve_alias_path(root, alias_path):
    """Walk root -> child by alias segment, mirroring the platform's
    ContentDbServiceImpl.getContentDomain (matching is by `alias`, case-sensitive).
    Returns the target siteMapPage node, or None if any segment doesn't resolve.
    """
    node = root
    for seg in [s for s in (alias_path or "").split("/") if s]:
        nxt = next((c for c in _child_pages(node) if c.get("alias") == seg), None)
        if nxt is None:
            return None
        node = nxt
    return node


def cmd_page_set_redirect(args):
    """Set (or clear) a siteMapPage's `Redirect` property — the platform's front-door
    mechanism. On the ROOT/Home page this decides what the bare project URL shows:
    the platform issues an HTTP redirect to the target page. The value is a
    slash-separated CONTENT-ALIAS PATH relative to root (NOT a URL / uuid / identifier);
    it is validated here against the actual content tree so a dead front door can't ship.
    """
    p = core.Project(args.project)
    root = p.root_content
    page = root if args.page in ("root", "ROOT", "home", "Home") else core.find_node(root, args.page)
    if page is None:
        raise core.ToolError("page %r not found" % args.page)

    target = (args.to or "").strip().lstrip("/")
    resolved = None
    if target:
        resolved = resolve_alias_path(root, target)
        if resolved is None:
            aliases = sorted(a for a in (c.get("alias") for c in _child_pages(root)) if a)
            raise core.ToolError(
                "redirect target %r does not resolve to a page (matching is by alias, "
                "case-sensitive, relative to root). Available top-level aliases: %s"
                % (target, ", ".join(aliases)))

    props = page.setdefault("properties", {})
    slot = props.get("Redirect")
    if not isinstance(slot, dict):
        slot = core.make_property_slot("Redirect", "")
        props["Redirect"] = slot
    slot["stringValue"] = target
    p.mark(core.F_BRANCHES)
    p.save()

    where = "%s <%s>" % (page.get("name"), (page.get("identifier") or "")[:8])
    if target:
        core.out("Redirect set on %s -> %r  (resolves to page %r)"
                 % (where, target, resolved.get("name")))
    else:
        core.out("Redirect cleared on %s (root will render its own content)" % where)


# ---------------------------------------------------------------------------
# node add / rm
# ---------------------------------------------------------------------------


def cmd_node_add(args):
    p = core.Project(args.project)
    root = p.root_content
    parent = core.find_node(root, args.parent)
    # if the parent is a page, drop the node into its content container
    if parent.get("pluginName") == "siteMapPage":
        parent = _content_container(parent)

    plugin = args.plugin
    slot = slot_for_plugin(plugin)

    node = {
        "id": None,
        # A caller-supplied SYMBOLIC identifier (e.g. "filter.parsis", "form.parsis")
        # is how the platform anchors layout children; FilterFormPlugin only renders
        # fields into a direct child nct.parsis.plugin whose identifier == "filter.parsis".
        # Default to a fresh uuid when not given.
        "identifier": getattr(args, "identifier", None) or core.new_uuid(),
        "uniqueIdentifier": core.new_uuid(),
        "name": args.name or plugin,
        "pluginName": plugin,
        "children": [],
        "properties": {},
        "roleAccess": copy.deepcopy(parent.get("roleAccess", _default_role_access())),
        "order": core.next_order(parent),
        "active": True,
        "isBehaviour": False,
        "includedInParsis": False,
        "virtualContent": False,
        "treeOpened": False,
        "treeDisabled": False,
        "treeSelected": False,
        "branchId": p.branch_id(),
        "childPluginAdded": False,
    }

    # Universal baseline STRING slots that every real plugin node carries, so
    # a generated node is structurally identical to a real one (not thinner).
    for base_key in BASELINE_STRING_SLOTS:
        node["properties"][base_key] = core.make_property_slot(base_key, "")

    # settings / model / Javascript / filterFormModel / tabModel inner JSON (§2).
    # The user passes config via --settings or --model regardless of the plugin's
    # real slot; we route it to the plugin's actual config slot (e.g.
    # chart.js.plugin -> Javascript, dynaform.filter.form.plugin ->
    # filterFormModel, nct.tab.plugin -> tabModel).
    if args.settings is not None and args.model is not None:
        raise core.ToolError("pass only one of --settings/--model")
    config = args.settings if args.settings is not None else args.model
    if slot is None:
        # Container/reference plugin (form.plugin, list.item.plugin): no
        # inner-JSON config blob exists — config lives in top-level scalar
        # properties. Reject config and never seed a settings slot.
        if config is not None:
            raise core.ToolError(
                "%s has no inner-JSON config slot; its config lives in top-level "
                "properties (e.g. formModeIdentifier / isParsis / reuseItems). "
                "Set those with `node patch-*` or by hand, not --settings/--model."
                % plugin)
    elif config is not None:
        obj = core.read_json_arg(config)
        # Builder default: tabs are created SMALL (compact `nav-tabs`). The platform's TabModel
        # defaults size to BIG, which is visually heavy; author small unless a size is given.
        if slot == "tabModel" and isinstance(obj, dict) and not obj.get("size"):
            obj["size"] = "SMALL"
        core.set_inner_json(node, slot, obj)
    elif slot not in ("Javascript", "filterFormModel", "tabModel"):
        # Seed an empty slot of the correct kind so callers can patch it.
        # Javascript/filterFormModel/tabModel plugins carry NO empty slot in real
        # exports (a bare {} renders empty), so we leave it absent until config
        # is supplied.
        core.set_inner_json(node, slot, {})

    parent.setdefault("children", []).append(node)
    p.mark(core.F_BRANCHES)
    p.save()
    core.out("node added: %s (%s) -> parent %s\n  identifier=%s  config slot=%s"
             % (node["name"], plugin, parent.get("identifier"), node["identifier"],
                slot if slot is not None else "(none — top-level properties only)"))


def cmd_node_rm(args):
    p = core.Project(args.project)
    root = p.root_content
    node = core.find_node(root, args.id)
    parent = core.find_parent(root, node)
    if parent is None:
        raise core.ToolError("cannot remove the root node")
    parent["children"] = [c for c in parent["children"] if c is not node]
    p.mark(core.F_BRANCHES)
    p.save()
    core.out("node removed: %s <%s>" % (node.get("name"), node.get("identifier")))


# ---------------------------------------------------------------------------
# set-settings / patch-settings / set-model / patch-model
# ---------------------------------------------------------------------------


def _set_slot(args, slot):
    p = core.Project(args.project)
    node = core.find_node(p.root_content, args.id)
    obj = core.read_json_arg(args.json)
    if not isinstance(obj, (dict, list)):
        raise core.ToolError("%s replacement must be a JSON object or array" % slot)
    core.set_inner_json(node, slot, obj)
    p.mark(core.F_BRANCHES)
    if slot == "model" and sync_crud_mirror(p, node):
        p.mark(core.F_REP)
    p.save()
    core.out("%s replaced on node %s <%s>" % (slot, node.get("name"), node.get("identifier")))


def _patch_slot(args, slot):
    p = core.Project(args.project)
    node = core.find_node(p.root_content, args.id)
    obj = core.get_inner_json(node, slot)
    if not isinstance(obj, dict):
        raise core.ToolError("cannot patch keys: properties.%s is not a JSON object" % slot)
    for pair in args.set or []:
        key, val = core.parse_typed_kv(pair)
        obj[key] = val
    core.set_inner_json(node, slot, obj)
    p.mark(core.F_BRANCHES)
    if slot == "model" and sync_crud_mirror(p, node):
        p.mark(core.F_REP)
    p.save()
    core.out("%s patched on node %s <%s>: %s"
             % (slot, node.get("name"), node.get("identifier"),
                ", ".join(pp.split("=", 1)[0] for pp in (args.set or []))))


def cmd_node_set_settings(args):
    _set_slot(args, "settings")


def cmd_node_patch_settings(args):
    _patch_slot(args, "settings")


def cmd_node_set_model(args):
    _set_slot(args, "model")


def cmd_node_patch_model(args):
    _patch_slot(args, "model")


def cmd_node_set_studio(args):
    """Replace properties.studioModel inner JSON on an nct.html.plugin node — the HTML
    Component Studio project (libs/docs/scripts/css). See 24-html-component-studio.md for
    the schema and the ctx.callRule / ctx.callBl runtime API. Same STRING-holds-JSON slot
    mechanism as set-model, so it round-trips in .mrjun for free."""
    _set_slot(args, "studioModel")


# ---------------------------------------------------------------------------
# asset — tenant-files (round-trip into nct-file-storage under t/<tenantId>/)
# ---------------------------------------------------------------------------


def _tenant_files_dir(project):
    return os.path.join(project.root, "tenant-files")


def cmd_asset_add(args):
    """Copy a local file into the bundle's tenant-files/<relpath>. On import the platform
    re-uploads everything under tenant-files/ into nct-file-storage at t/<newTenantId>/<relpath>
    (CmsProjectServiceImpl.importFilesRecursively). For an HTML Component Studio library use
    relpath studio/<lib>/<file>, then reference {"kind":..,"path":"studio/<lib>/<file>"} in the
    plugin's studioModel — the path is stored RELATIVE to the tenant root, so it stays valid
    after import re-homes the file under the new tenant id (see 24-html-component-studio.md)."""
    p = core.Project(args.project)
    rel = (args.relpath or "").replace("\\", "/").strip().lstrip("/")
    segs = [s for s in rel.split("/") if s]
    if not segs or any(s in (".", "..") for s in segs):
        raise core.ToolError("relpath must be a clean relative path (no '..'): %r" % args.relpath)
    if not os.path.isfile(args.file):
        raise core.ToolError("local file not found: %r" % args.file)
    dest = os.path.join(_tenant_files_dir(p), *segs)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(args.file, dest)
    core.out("asset added: tenant-files/%s  (<- %s)   => imports to  t/<tenantId>/%s"
             % ("/".join(segs), args.file, "/".join(segs)))


def cmd_asset_ls(args):
    """List the files under the bundle's tenant-files/ (what will round-trip to nct-file-storage)."""
    p = core.Project(args.project)
    base = _tenant_files_dir(p)
    if not os.path.isdir(base):
        core.out("(no tenant-files/ in this bundle)")
        return
    found = False
    for dirpath, _dirs, files in os.walk(base):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, f), base).replace(os.sep, "/")
            core.out("t/<tenantId>/%s   (%d bytes)" % (rel, os.path.getsize(os.path.join(dirpath, f))))
            found = True
    if not found:
        core.out("(tenant-files/ is empty)")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _slugify(name):
    out = []
    prev_dash = False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-") or "page"


def _default_role_access():
    return {"publicReadAccess": False, "authenticatedUserAccess": True,
            "accessors": {}, "roleGroupAccessors": {}}
