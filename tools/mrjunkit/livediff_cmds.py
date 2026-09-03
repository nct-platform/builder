"""livediff — compare what the PLATFORM ACTUALLY STORED against what you packed.

The gap this closes. `validate` proves the export is well-formed, `coverage` proves nothing was
skipped, `crud verify` proves the SQL runs. None of them can tell you what the platform did with your
file on import. Two real failure classes live exactly in that gap and produce **no log line at all**:

  * a symbolic layout anchor was regenerated (e.g. `siteMapPageParsis`), so the platform CREATED a
    fresh empty node under the expected name, rendered that, and left your configured subtree beside
    it as an unrendered orphan -> a blank page, everything green offline (observed on a large real build);
  * a rep-object threw during `initAllObjects`, so every collection saved AFTER it was silently
    skipped (queries -> schedulers -> workflows -> rules -> contexts -> formGroups -> forms ->
    settings -> processGroups -> mailTemplates -> pdfTemplates) while the import still reports DONE.

Both are one query away from obvious, and invisible otherwise. Usage:

    mrjun.py livediff --project ./work \
        --db "host=<host> port=5432 dbname=<platform-db> user=<user> password=<password>" \
        --tenant <tenant-alias>

Needs `psql` on PATH (a docker shim works:  #!/bin/sh + exec docker exec -i <pg> psql "$@").
"""
import json
import subprocess

from . import core


def _psql(conninfo, sql):
    proc = subprocess.run(["psql", conninfo, "-q", "-v", "ON_ERROR_STOP=1", "-tAc", sql],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise core.ToolError("psql failed: %s" % (proc.stderr.strip()[:400] or "?"))
    return proc.stdout


def _pages(root):
    out = {}
    for n, _p, _t in core.iter_nodes(root):
        if n.get("pluginName") == "siteMapPage":
            key = n.get("alias") or n.get("name")
            if key:
                out[key] = n
    return out


def _anchors(page):
    """Non-uuid (symbolic) identifiers inside this page, excluding nested pages."""
    out = set()

    def walk(n, depth=0):
        if depth and not core.looks_uuid(n.get("identifier")):
            out.add(n.get("identifier"))
        for c in n.get("children") or []:
            if c.get("pluginName") == "siteMapPage":
                continue
            walk(c, depth + 1)
    walk(page)
    return out


def _content_children(page):
    for n, _p, _t in core.iter_nodes(page):
        if n.get("pluginName") == "nct.parsis.plugin" and n.get("name") == "parsis":
            return [c.get("pluginName") for c in (n.get("children") or [])]
    return None


def cmd_livediff(args):
    p = core.Project(args.project)
    r = core.out

    row = _psql(args.db, "SELECT s_published_branch_id FROM nct_ui.s_tenant WHERE s_alias = '%s';"
                % args.tenant.replace("'", "''")).strip()
    if not row:
        raise core.ToolError("tenant %r not found in nct_ui.s_tenant" % args.tenant)
    branch = row.splitlines()[0].strip()
    store = _psql(args.db, "SELECT content_store_id FROM nct_ui.s_branch WHERE s_id = '%s';"
                  % branch).strip()
    if not store:
        raise core.ToolError("no content_store for published branch %s" % branch)
    live_json = _psql(args.db, "SELECT root_content FROM nct_ui.s_branch_content_store "
                              "WHERE s_id = '%s';" % store)
    live_root = json.loads(live_json)

    local_pages = _pages(p.root_content)
    live_pages = _pages(live_root)
    r("livediff: tenant %s  branch %s" % (args.tenant, branch))
    r("  pages   packed=%d  live=%d" % (len(local_pages), len(live_pages)))

    problems = []
    for key in sorted(local_pages):
        if key not in live_pages:
            problems.append("page %r is in the packed project but NOT in the live tree "
                            "(import skipped or renamed it)" % key)
    for key in sorted(live_pages):
        if key not in local_pages:
            r("  ~ live-only page %r (pre-existing in the tenant, not from this project)" % key)

    for key in sorted(set(local_pages) & set(live_pages)):
        lp, vp = local_pages[key], live_pages[key]
        la, va = _anchors(lp), _anchors(vp)
        lost = la - va
        if lost:
            problems.append("page %r LOST symbolic anchors %s on import — the platform resolves "
                            "those by name; a missing one means it built a fresh empty node and your "
                            "subtree is an unrendered orphan" % (key, sorted(lost)))
        tops = [c for c in (vp.get("children") or []) if c.get("pluginName") == "parsis.plugin"]
        if len(tops) > 1:
            problems.append("page %r has %d top-level parsis.plugin children LIVE (expected 1) — the "
                            "classic orphan signature: one is rendered, the rest are dead"
                            % (key, len(tops)))
        lc, vc = _content_children(lp), _content_children(vp)
        if lc and not vc:
            problems.append("page %r: packed content container holds %s but the LIVE one is empty "
                            "-> the page renders blank" % (key, lc))

    # rep-objects: a mid-import abort silently truncates everything after the failing collection
    r("  rep-objects (packed):")
    for coll in ("queries", "schedulers", "workflows", "rules", "contexts", "formGroups",
                 "forms", "settings", "processGroups", "mailTemplates", "pdfTemplates"):
        r("      %-14s %d" % (coll, len(p.rep.get(coll) or [])))
    r("    ^ import order is exactly this; if a live count drops to 0 from here down, that "
      "collection threw and everything after it was skipped (check log/ui.log for the stack).")

    if problems:
        r("")
        r("LIVE MISMATCH (%d):" % len(problems))
        for m in problems:
            r("  x " + m)
        return 1
    r("  OK — every packed page exists live with its symbolic anchors intact.")
    return 0
