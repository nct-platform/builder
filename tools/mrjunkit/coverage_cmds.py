"""coverage — the machine-checkable "constitution" gate (doc 26 §enforcement).

The fix for "finished a huge PRD fast and shallow, skipped half of it": decompose the PRD into a PLAN
(plan.json) where every requirement is one testable row, then this command CROSS-CHECKS the built .mrjun against
that plan and FAILS (non-zero exit) if anything planned is missing or not yet marked done. Skipping is DETECTED,
not hoped-away. Grounded in spec-driven development (the spec is an executable contract) + Replit-style
smallest-task/verifier loops.

plan.json shape (each item = one testable claim):
  { "project": "...", "locales": ["hy_AM","ru_RU","en_US"],
    "items": [
      { "id": "ent-incomingDocument", "kind": "entity",   "alias": "incomingDocument", "status": "done",
        "test": "validate; db show incoming_document; crud verify" },
      { "id": "form-intake",          "kind": "form",      "name":  "Incoming Document Form", "status": "done" },
      { "id": "page-register",        "kind": "page",      "alias": "incoming-documents", "status": "done" },
      { "id": "wf-intake",            "kind": "workflow",  "name":  "incoming-document-intake", "status": "todo" },
      { "id": "mail-defect",          "kind": "mailTemplate","alias":"mailDefectSender", "status": "done" },
      { "id": "req-defect-notify",    "kind": "requirement","selector": {"kind":"mailTemplate","key":"mailDefectSender"},
        "status": "done", "note": "PRD §10.5 notify sender of a defect" }
    ] }

kinds: entity form page rule workflow mailTemplate pdfTemplate roleGroup scheduler context dashboard chart
       requirement (a generic claim resolved via an inner {kind,key} selector).
status: done | todo | building | blocked | deferred   (omitted => todo).
  - MISSING (planned artifact not in the build) & status != deferred  -> GATE FAIL
  - PRESENT but status in {todo,building,blocked}                      -> GATE FAIL (built, not verified/marked done)
  - status == deferred (an explicit, recorded decision NOT to build)  -> WARN, not a fail
  - PRESENT & status == done                                          -> OK
Exit non-zero on any GATE FAIL (unless --report-only).
"""
import json
from . import core


def _norm(s):
    return (s or "").strip().lower()


def _index(p):
    """Build {kind: {key -> display}} of everything actually in the built project."""
    idx = {k: {} for k in ("entity", "form", "page", "rule", "workflow", "mailTemplate",
                           "pdfTemplate", "roleGroup", "scheduler", "context", "chart", "dashboard")}

    cf = p.cruds_file
    for c in ((cf.data.get("cruds", []) if cf else []) or []):
        if c.get("alias"):
            idx["entity"][_norm(c["alias"])] = c["alias"]

    rep = p.rep
    def addrep(coll, kind, *keys):
        for o in (rep.get(coll, []) or []):
            if not isinstance(o, dict):
                continue
            for kf in keys:
                v = o.get(kf)
                if v:
                    idx[kind][_norm(v)] = v
    addrep("forms", "form", "name", "identifier")
    addrep("rules", "rule", "name")
    addrep("workflows", "workflow", "name")
    addrep("mailTemplates", "mailTemplate", "alias", "name")
    addrep("pdfTemplates", "pdfTemplate", "alias", "name")
    addrep("roleGroups", "roleGroup", "name")
    addrep("schedulers", "scheduler", "name")
    addrep("contexts", "context", "alias", "name")

    # pages + charts: walk the content tree. A page that (transitively, within its own layout) holds a
    # chart.js.plugin is a "dashboard".
    def page_has_chart(pagenode):
        found = [False]
        def walk(n, is_root):
            if not is_root and n.get("pluginName") == "siteMapPage":
                return
            if n.get("pluginName") == "chart.js.plugin":
                found[0] = True
            for c in (n.get("children") or []):
                walk(c, False)
        walk(pagenode, True)
        return found[0]

    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") == "siteMapPage":
            for kf in ("alias", "name"):
                v = node.get(kf)
                if v:
                    idx["page"][_norm(v)] = v
            if page_has_chart(node):
                for kf in ("alias", "name"):
                    v = node.get(kf)
                    if v:
                        idx["dashboard"][_norm(v)] = v
        elif node.get("pluginName") == "chart.js.plugin":
            v = node.get("name") or node.get("identifier")
            if v:
                idx["chart"][_norm(v)] = v
    return idx


_KIND_ALIASES = {"mailtemplate": "mailTemplate", "pdftemplate": "pdfTemplate", "rolegroup": "roleGroup"}


def _resolve(idx, kind, item):
    """Return (found_bool, matched_display_or_None). Matches on alias then name then selector.key."""
    kind = _KIND_ALIASES.get(kind, kind)
    if kind == "requirement":
        sel = item.get("selector") or {}
        return _resolve(idx, sel.get("kind", ""), {"alias": sel.get("key"), "name": sel.get("key")})
    bag = idx.get(kind)
    if bag is None:
        return None, None  # unknown kind
    for kf in ("alias", "name"):
        v = item.get(kf)
        if v and _norm(v) in bag:
            return True, bag[_norm(v)]
    # dashboard/chart with no key => "any chart present" satisfies it
    if kind in ("dashboard", "chart") and not item.get("alias") and not item.get("name"):
        return (len(bag) > 0), (next(iter(bag.values())) if bag else None)
    return False, None


def cmd_coverage(args):
    p = core.Project(args.project)
    idx = _index(p)

    if getattr(args, "emit", False):
        # bootstrap a plan skeleton from what EXISTS (status=done) — a starting ledger / coverage snapshot.
        items = []
        n = 0
        order = ["context", "entity", "rule", "roleGroup", "form", "page", "dashboard",
                 "workflow", "mailTemplate", "pdfTemplate", "scheduler"]
        for kind in order:
            for key, disp in sorted(idx.get(kind, {}).items()):
                n += 1
                row = {"id": "%s-%s" % (kind, key)[:60], "kind": kind, "status": "done"}
                row["alias" if kind in ("entity", "context") else "name"] = disp
                items.append(row)
        plan = {"project": p.tenant.get("name"), "locales": p.locales(), "items": items}
        core.out(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    if not getattr(args, "plan", None):
        raise core.ToolError("coverage needs --plan <plan.json> (or --emit to print a skeleton from the build)")
    plan = core.load_json_file(args.plan).data
    items = plan.get("items", []) if isinstance(plan, dict) else plan
    if not isinstance(items, list):
        raise core.ToolError("plan.json must be {items:[...]} or a top-level list of items")

    fails, warns, oks = [], [], []
    covered_keys = {k: set() for k in idx}
    for it in items:
        kind = _KIND_ALIASES.get(it.get("kind", ""), it.get("kind", ""))
        status = _norm(it.get("status") or "todo")
        found, disp = _resolve(idx, it.get("kind", ""), it)
        iid = it.get("id") or (it.get("alias") or it.get("name") or "?")
        if disp and kind in covered_keys:
            covered_keys[kind].add(_norm(disp))
        if found is None:
            warns.append((iid, kind, status, "unknown kind %r — not checkable" % it.get("kind")))
            continue
        if not found:
            if status == "deferred":
                warns.append((iid, kind, status, "DEFERRED — planned but intentionally not built (recorded)"))
            else:
                fails.append((iid, kind, status, "MISSING — no %s matches %r in the build" %
                              (kind, it.get("alias") or it.get("name") or (it.get("selector") or {}).get("key"))))
        else:
            if status == "done":
                oks.append((iid, kind, status, "ok -> %s" % disp))
            elif status == "deferred":
                warns.append((iid, kind, status, "present but marked deferred? -> %s" % disp))
            else:
                fails.append((iid, kind, status, "PRESENT but status=%s — build the test, mark done -> %s" % (status, disp)))

    # orphans: built artifacts not referenced by any plan item (incomplete plan / scope creep)
    orphans = []
    for kind, bag in idx.items():
        if kind == "dashboard":
            continue  # dashboards are pages; avoid double-count
        for key, disp in bag.items():
            if key not in covered_keys.get(kind, set()):
                orphans.append((kind, disp))

    core.out("coverage: %s" % (plan.get("project") or p.tenant.get("name")))
    core.out("  planned items: %d   ok: %d   FAIL: %d   warn: %d   orphan(built,unplanned): %d"
             % (len(items), len(oks), len(fails), len(warns), len(orphans)))
    if fails:
        core.out("\nGATE FAILURES (must fix before 'done'):")
        for iid, kind, status, msg in fails:
            core.out("  ✗ [%s] %s: %s" % (kind, iid, msg))
    if warns:
        core.out("\nWARNINGS:")
        for iid, kind, status, msg in warns:
            core.out("  ! [%s] %s: %s" % (kind, iid, msg))
    if orphans and getattr(args, "show_orphans", False):
        core.out("\nORPHANS (in the build, not in the plan — is the plan complete?):")
        for kind, disp in sorted(orphans):
            core.out("  ~ [%s] %s" % (kind, disp))
    elif orphans:
        core.out("\n%d built artifact(s) are not in the plan (run with --show-orphans; a complete plan should cover them)." % len(orphans))

    if fails and not getattr(args, "report_only", False):
        raise core.ToolError("coverage gate FAILED: %d item(s) missing or not marked done. Not shippable." % len(fails))
    core.out("\ncoverage gate: %s" % ("PASS" if not fails else "FAIL (report-only)"))
