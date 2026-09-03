"""locale — fill per-locale text maps across the project.

`locale fill` copies each flat per-locale map's default-locale value into every
still-missing tenant locale — the deterministic equivalent of the live UI's
blur-fill, MINUS translation (it copies the source text verbatim, like
`quicklink`). Auto-translate never runs on import, so a default-only map would
under-cover the tenant; run this after hand-authoring, then `validate`.

Scope (v1): flat locale maps (see validate_cmds._FLAT_LOCALE_MAP_KEYS) inside
content-node properties.settings/model inner JSON (crud.table/tree/process
mirrors are re-synced), plus structured rep-object maps. It does NOT rewrite
workflow user-task actions embedded as escaped JSON inside bpmnContent — those
are seeded across all locales at creation time by `workflow add`. See
../20-localization.md §viii.
"""

from . import core
from .validate_cmds import _FLAT_LOCALE_MAP_KEYS


def _fill_map(d, locales, default_locale):
    """Fill missing tenant locales in a flat {locale: value} map in place.
    Only acts when every present key is a tenant locale (so a nested field-keyed
    map is never touched). Returns the number of locale slots added."""
    keys = set(d.keys())
    if not keys or not keys <= set(locales):
        return 0
    src = d.get(default_locale)
    if src is None:
        for loc in locales:
            if loc in d:
                src = d[loc]
                break
    if src is None:
        return 0
    added = 0
    for loc in locales:
        if loc not in d:
            d[loc] = src
            added += 1
    return added


def _walk_fill(obj, locales, default_locale):
    """Recurse dict/list, filling every flat per-locale map found. Returns count."""
    added = 0
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in _FLAT_LOCALE_MAP_KEYS and isinstance(val, dict):
                added += _fill_map(val, locales, default_locale)
            added += _walk_fill(val, locales, default_locale)
    elif isinstance(obj, list):
        for item in obj:
            added += _walk_fill(item, locales, default_locale)
    return added


def cmd_locale_fill(args):
    from .content_cmds import sync_crud_mirror  # lazy: avoids import cycle

    p = core.Project(args.project)
    locales = p.locales()
    default_locale = p.default_locale()
    if len(locales) < 2:
        core.out("locale fill: tenant has a single locale %s — nothing to fill"
                 % locales)
        return

    filled = 0
    nodes_touched = 0
    branches_dirty = False
    rep_dirty = False

    # 1) content-node settings/model inner JSON (+ crud mirror re-sync)
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        props = node.get("properties", {}) or {}
        node_added = 0
        model_changed = False
        for slot in ("settings", "model"):
            prop = props.get(slot)
            if not (prop and prop.get("stringValue")):
                continue
            try:
                inner = core.get_inner_json(node, slot)
            except core.ToolError:
                continue  # malformed JSON is validate's job, not ours
            c = _walk_fill(inner, locales, default_locale)
            if c:
                core.set_inner_json(node, slot, inner)
                node_added += c
                if slot == "model":
                    model_changed = True
        if node_added:
            filled += node_added
            nodes_touched += 1
            branches_dirty = True
            if model_changed and sync_crud_mirror(p, node):
                rep_dirty = True

    # 2) structured rep-object maps (forms/formGroups/mailTemplates/...), EXCEPT
    #    the `settings` mirror collection — that is kept in sync by (1) above.
    for coll, items in (p.rep or {}).items():
        if coll == "settings":
            continue
        c = _walk_fill(items, locales, default_locale)
        if c:
            filled += c
            rep_dirty = True

    if branches_dirty:
        p.mark(core.F_BRANCHES)
    if rep_dirty:
        p.mark(core.F_REP)
    p.save()
    core.out("locale fill: %d locale slot(s) filled across %d content node(s) + rep-objects "
             "(locales=%s, source=%s). Copied verbatim — translate as needed."
             % (filled, nodes_touched, locales, default_locale))


def cmd_locale_set_default(args):
    """Set tenant.json `defaultLocale` — the project's DEFAULT/authoritative language (settings-plugin
    'Default language'). Must be one of tenant.json.locales. It round-trips through the .mrjun and the
    platform import (TenantDomain.g_default_locale); drives base-column writes, form default-locale, and
    `locale fill`'s source. With no --locale, prints the current value. See ../20-localization.md."""
    p = core.Project(args.project)
    locs = p.locales()
    if not getattr(args, "locale", None):
        core.out("tenant.json defaultLocale = %r  (locales: %s; effective default = %s)"
                 % (p.tenant.get("defaultLocale"), ", ".join(locs), p.default_locale()))
        return
    if args.locale not in locs:
        raise core.ToolError("default locale %r is not in tenant.json locales %s — add it to locales first"
                             % (args.locale, locs))
    p.tenant["defaultLocale"] = args.locale
    p.mark(core.F_TENANT)
    p.save()
    core.out("tenant.json defaultLocale set to %s  (locales: %s)" % (args.locale, ", ".join(locs)))
