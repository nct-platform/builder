"""roleaccess show/set — the content-node roleAccess model (hard rule §4)."""

import json

from . import core

PERMS = ("view", "edit", "advancedEdit")


def _blank_perm():
    return {"view": False, "edit": False, "advancedEdit": False}


def _parse_perms(spec):
    """`view,edit` -> {view:True, edit:True, advancedEdit:False}. `*`/`all` = all."""
    perm = _blank_perm()
    spec = spec.strip()
    if spec in ("*", "all"):
        return {"view": True, "edit": True, "advancedEdit": True}
    if not spec:
        return perm
    for token in spec.split(","):
        t = token.strip()
        if t not in PERMS:
            raise core.ToolError("unknown permission %r (allowed: %s)" % (t, ",".join(PERMS)))
        perm[t] = True
    return perm


def cmd_roleaccess_show(args):
    p = core.Project(args.project)
    node = core.find_node(p.root_content, args.id)
    ra = node.get("roleAccess") or {}
    core.out("node: %s <%s>" % (node.get("name"), node.get("identifier")))
    core.out("publicReadAccess:      %s" % ra.get("publicReadAccess"))
    core.out("authenticatedUserAccess: %s" % ra.get("authenticatedUserAccess"))
    core.out("accessors (roles):")
    for role, perm in (ra.get("accessors") or {}).items():
        granted = [k for k in PERMS if perm.get(k)]
        if granted:
            core.out("    %-24s %s" % (role, ",".join(granted)))
    core.out("roleGroupAccessors:")
    for rg, perm in (ra.get("roleGroupAccessors") or {}).items():
        granted = [k for k in PERMS if perm.get(k)]
        if granted:
            core.out("    %-24s %s" % (rg, ",".join(granted)))


def cmd_roleaccess_set(args):
    p = core.Project(args.project)
    node = core.find_node(p.root_content, args.id)
    ra = node.setdefault("roleAccess", {
        "publicReadAccess": False, "authenticatedUserAccess": False,
        "accessors": {}, "roleGroupAccessors": {},
    })
    ra.setdefault("accessors", {})
    ra.setdefault("roleGroupAccessors", {})

    if args.public is not None:
        ra["publicReadAccess"] = args.public
    if args.authenticated is not None:
        ra["authenticatedUserAccess"] = args.authenticated

    for spec in args.role or []:
        name, _, perms = spec.partition(":")
        ra["accessors"][name] = _parse_perms(perms)
    for spec in args.rolegroup or []:
        name, _, perms = spec.partition(":")
        ra["roleGroupAccessors"][name] = _parse_perms(perms)

    p.mark(core.F_BRANCHES)
    p.save()
    core.out("roleAccess updated on %s <%s>" % (node.get("name"), node.get("identifier")))
