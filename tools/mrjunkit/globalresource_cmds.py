"""globalresource — the project's GLOBAL RESOURCES (Settings -> Developer -> Global Resources).

ONE tree holds everything the project ships to the browser: scripts, stylesheets, HTML fragments,
fonts, images. What a file IS decides only whether it can be SWITCHED ON — a script or a stylesheet
can, and then loads on every page of the project; everything else is stored and served for whatever
references it. A tree per file type was the first design and it broke the one thing that has to keep
working: a stylesheet's relative ``url(../fonts/kit.woff2)`` only resolves when the font sits where
the stylesheet says it does.

Two halves have to agree or the feature is silently half-present, and this module is what keeps them
in step:

  * the REGISTRY lives on each branch in ``branches.json`` as ``globalAssets`` — links and metadata
    only, never the file text;
  * the BYTES live under ``tenant-files/webassets/<storageId>/…``, which the platform re-uploads into
    nct-file-storage at ``t/<newTenantId>/webassets/<storageId>/…`` on import.

The registry stores the path RELATIVE to the tenant root for exactly that reason: the tenant id
changes on every import, so an absolute ``t/<id>/…`` link would point at the donor project's files —
and would READ them successfully, because the donor's storage still exists.

**Every branch owns its own ``storageId`` and its own copy of the bytes.** Two branches sharing a
subtree is the bug this design exists to prevent: a publish copies the registry verbatim, so both
would name the same file and an edit in the draft would rewrite what the published site serves.

See ``29-global-resources.md``.
"""

import hashlib
import os
import re
import zipfile

from . import core

ROOT = "webassets"

#: Extensions that become a LOADABLE asset — the only two kinds that have a switch.
JS_EXT = {"js", "mjs"}
CSS_EXT = {"css"}
HTML_EXT = {"html", "htm"}

#: Everything the serving endpoint will hand back at all. Anything else in an archive is skipped.
ALLOWED_EXT = {
    "js", "mjs", "css", "html", "htm", "map", "json", "txt", "csv", "xml", "svg",
    "woff", "woff2", "ttf", "otf", "eot",
    "png", "jpg", "jpeg", "gif", "webp", "avif", "ico", "bmp",
    "mp3", "mp4", "webm", "ogg", "wav",
}

#: The skins a stylesheet may be limited to. An EMPTY list means every skin, which is the default.
SKINS = ["Standard", "Dracula", "Forest", "Dark", "Dark Blue"]

#: Base libraries, most-depended-on FIRST — the list order is the rank, so jQuery before Popper
#: before Bootstrap is the contract. Second column: the globals each publishes.
KNOWN_LIBRARIES = [
    ("jquery", ["jQuery", "$"]),
    ("zepto", ["$"]),
    ("popper", ["Popper"]),
    ("bootstrap", ["bootstrap"]),
    ("lodash", ["_"]),
    ("underscore", ["_"]),
    ("moment", ["moment"]),
    ("dayjs", ["dayjs"]),
    ("luxon", ["luxon"]),
    ("d3", ["d3"]),
    ("chart", ["Chart"]),
    ("apexcharts", ["ApexCharts"]),
    ("echarts", ["echarts"]),
    ("axios", ["axios"]),
    ("vue", ["Vue"]),
    ("react", ["React"]),
    ("react-dom", ["ReactDOM"]),
    ("codemirror", ["CodeMirror"]),
    ("select2", ["$.fn.select2"]),
    ("datatables", ["$.fn.DataTable"]),
    ("toastr", ["toastr"]),
    ("sweetalert", ["Swal"]),
    ("flatpickr", ["flatpickr"]),
    ("leaflet", ["L"]),
    ("three", ["THREE"]),
    ("gsap", ["gsap"]),
    ("htmx", ["htmx"]),
]

VENDOR_DIRS = ("vendor", "vendors", "lib", "libs", "node_modules", "dist", "assets")

MAX_ENTRIES = 400
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_ENTRY_BYTES = 6 * 1024 * 1024

_HTML_REF = re.compile(r"""<(?:script[^>]*\ssrc|link[^>]*\shref)\s*=\s*["']([^"']+)["']""", re.I)
_JQUERY_PLUGIN = re.compile(r"(?:\$|jQuery)\s*\.\s*fn\s*\.\s*[A-Za-z_$][\w$]*\s*=")
_EXPLICIT_GLOBAL = re.compile(r"(?:window|globalThis|self)\s*\.\s*([A-Za-z_$][\w$]*)\s*=(?!=)")
_UMD_GLOBAL = re.compile(r"global(?:This)?\s*\.\s*([A-Za-z_$][\w$]*)\s*=\s*[{(]")


# --------------------------------------------------------------------------- names and paths


def safe_segment(value):
    """One path segment, reduced to what survives every hop.

    Not cosmetic. The storage path travels to the file service as an HTTP HEADER, which is
    effectively ISO-8859-1, so a name with a space or an accent is mangled or rejected there.

    ``-ver-`` is rewritten for a second reason: Wicket's ``ResourceMapper`` strips
    ``<base>-ver-<version>`` out of the last URL segment of EVERY mapped resource request, so a file
    genuinely called ``app-ver-2.css`` would be requested as ``app.css`` and never found.
    """
    value = (value or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._\-]", "-", value)
    cleaned = re.sub(r"-{2,}", "-", cleaned).replace("-ver-", "-ver_").strip(".-")
    if not cleaned:
        return "file"
    return cleaned[-120:] if len(cleaned) > 120 else cleaned


def safe_folder(path):
    """A folder path, segment by segment. ``..`` POPS its parent rather than being dropped.

    Dropping is equally safe — neither can escape the tree — but it is quietly wrong in a way nobody
    can explain: ``vendor/../vendor/charts`` would become ``vendor/vendor/charts``.
    """
    segments = []
    for raw in (path or "").replace("\\", "/").split("/"):
        if not raw or raw == ".":
            continue
        if raw == "..":
            if segments:
                segments.pop()
            continue
        segments.append(safe_segment(raw))
    return "/".join(segments)


def safe_relative(entry_name):
    """A whole relative path with its folder structure kept. This is the zip-slip defence."""
    raw = (entry_name or "").replace("\\", "/")
    folder = safe_folder(raw.rsplit("/", 1)[0]) if "/" in raw else ""
    leaf = safe_segment(raw)
    return "%s/%s" % (folder, leaf) if folder else leaf


def extension_of(name):
    leaf = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in leaf or leaf.endswith("."):
        return ""
    return leaf.rsplit(".", 1)[-1].lower()


def kind_of(name):
    """What a file IS, from its extension. Never chosen by hand — it decides how it is served."""
    ext = extension_of(name)
    if ext in JS_EXT:
        return "JS"
    if ext in CSS_EXT:
        return "CSS"
    if ext in HTML_EXT:
        return "HTML"
    return "OTHER"


def includable(kind):
    """Only a script or a stylesheet has a switch. Everything else is served, never loaded."""
    return kind in ("JS", "CSS")


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


def storage_path(storage_id, folder, name):
    folder = safe_folder(folder)
    base = "%s/%s" % (ROOT, safe_segment(storage_id))
    return "%s/%s/%s" % (base, folder, safe_segment(name)) if folder else "%s/%s" % (base, safe_segment(name))


# --------------------------------------------------------------------------- registry


def _registry(branch):
    """The branch's registry, created (with its own storage id) the first time anything is added."""
    reg = branch.get("globalAssets")
    if not isinstance(reg, dict):
        reg = {}
        branch["globalAssets"] = reg
    reg["version"] = 3
    if not reg.get("storageId"):
        # A storage id per BRANCH. Two branches sharing one subtree means an edit in a draft rewrites
        # what the published site serves — the bug this whole shape exists to prevent.
        reg["storageId"] = core.new_uuid().replace("-", "")[:16]
    if not isinstance(reg.get("folders"), list):
        reg["folders"] = []
    if not isinstance(reg.get("assets"), list):
        reg["assets"] = []
    return reg


def _renumber(reg):
    """Order is the list position — one authority, so a hand-edited file cannot disagree with itself."""
    for i, asset in enumerate(reg["assets"]):
        asset["order"] = i
    for i, folder in enumerate(reg["folders"]):
        folder["order"] = i


def _target_branches(project, wanted):
    branches = project.branches
    if not wanted:
        return branches
    picked = [b for b in branches if b.get("name") == wanted]
    if not picked:
        raise core.ToolError("no branch called %r in branches.json (have: %s)"
                             % (wanted, ", ".join(str(b.get("name")) for b in branches)))
    return picked


def _ensure_folders(reg, path, origin, archive, actor):
    """Creates the folder and every missing folder above it. Folders are entities, not path prefixes.

    That is what lets an EMPTY folder exist and a whole vendored kit be switched off as a unit —
    which is the main reason to have folders at all.
    """
    path = safe_folder(path)
    if not path:
        return
    walked = []
    for segment in path.split("/"):
        walked.append(segment)
        here = "/".join(walked)
        if any(f.get("path") == here for f in reg["folders"]):
            continue
        folder = {
            "id": core.new_uuid(),
            "path": here,
            "enabled": True,
            "order": len(reg["folders"]),
            "origin": origin,
            "createdAt": core.now_iso(),
            "createdBy": actor or "builder",
        }
        if archive:
            folder["archive"] = archive
        reg["folders"].append(folder)


def _new_asset(reg, folder, file_name, origin, archive, actor, data):
    name = safe_segment(file_name)
    kind = kind_of(name)
    asset = {
        "id": core.new_uuid(),
        "kind": kind,
        "name": name,
        "folder": safe_folder(folder),
        "path": storage_path(reg["storageId"], folder, name),
        "sha256": sha256_of(data),
        "size": len(data),
        # ARRIVING IS NOT THE SAME AS BEING SWITCHED ON. A kit typically ships three builds of itself
        # and a demo page; deciding which of them the project loads is a decision, and making it here
        # would mean an import changed what a live site serves without anyone choosing it.
        "enabled": False,
        "order": 0,
        "origin": origin,
        # A library has to be able to publish its own global: wrapping a UMD bundle in a closure is
        # how you get "jQuery is not defined" two files later. Only something typed into the editor
        # inside the product is treated as a snippet and wrapped.
        "isolate": False,
        "updatedAt": core.now_iso(),
        "updatedBy": actor or "builder",
    }
    if archive:
        asset["archive"] = archive
    if kind == "CSS":
        # An empty list means EVERY skin, which is the default and nearly always right.
        asset["skins"] = []
    if kind == "JS":
        # Recorded here so the product's "you switched this on — it still needs jQuery" is arithmetic
        # over the registry rather than a scan of every file in storage.
        asset["provides"] = sorted(_provides_of(name, data))
    return asset


def _write_bytes(project, rel_path, data):
    dest = os.path.join(project.root, "tenant-files", *rel_path.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)


def _find(reg, needle):
    """A file or a folder, by id, by display path, or by bare name."""
    for asset in reg["assets"]:
        if needle in (asset.get("id"), _display(asset), asset.get("name")):
            return "file", asset
    for folder in reg["folders"]:
        if needle in (folder.get("id"), folder.get("path")):
            return "folder", folder
    return None, None


def _display(asset):
    folder = asset.get("folder") or ""
    return "%s/%s" % (folder, asset.get("name")) if folder else asset.get("name")


def _loads(reg, asset):
    """Its own switch AND every folder above it. The one place this question is answered."""
    if not includable(asset.get("kind")) or not asset.get("enabled"):
        return False
    path = asset.get("folder") or ""
    while path:
        folder = next((f for f in reg["folders"] if f.get("path") == path), None)
        if folder is not None and not folder.get("enabled", True):
            return False
        path = path.rsplit("/", 1)[0] if "/" in path else ""
    return True


# --------------------------------------------------------------------------- commands


def cmd_globalresource_add(args):
    """Copy one local file into the bundle and register it — switched OFF unless ``--on``."""
    project = core.Project(args.project)
    if not os.path.isfile(args.file):
        raise core.ToolError("local file not found: %r" % args.file)
    with open(args.file, "rb") as fh:
        data = fh.read()
    if not data:
        raise core.ToolError("refusing to register an empty file: %r" % args.file)

    display = safe_segment(args.name or os.path.basename(args.file))
    if extension_of(display) not in ALLOWED_EXT:
        raise core.ToolError(
            "%s is not a file this project can ship. Allowed: %s"
            % (display, ", ".join(sorted(ALLOWED_EXT))))
    folder = safe_folder(args.folder or "")

    added = []
    for branch in _target_branches(project, args.branch):
        reg = _registry(branch)
        if any((a.get("folder") or "") == folder and (a.get("name") or "").lower() == display.lower()
               for a in reg["assets"]):
            raise core.ToolError("branch %r already has %s" % (branch.get("name"), display))
        _ensure_folders(reg, folder, "MANUAL", None, args.by)
        asset = _new_asset(reg, folder, display, "UPLOAD", None, args.by, data)
        if args.on and includable(asset["kind"]):
            asset["enabled"] = True
        reg["assets"].append(asset)
        _renumber(reg)
        # Each branch owns its own copy of the bytes, under its own storage id.
        _write_bytes(project, asset["path"], data)
        added.append((branch.get("name"), asset))

    project.mark(core.F_BRANCHES)
    project.save()
    for name, asset in added:
        core.out("  %-10s %-5s %-40s %8d  -> tenant-files/%s"
                 % (name, asset["kind"], _display(asset), asset["size"], asset["path"]))
    if not includable(kind_of(display)):
        core.out("%s added to %d branch(es). It is served at its URL; nothing loads it on its own."
                 % (display, len(added)))
    elif args.on:
        core.out("%s added to %d branch(es), SWITCHED ON." % (display, len(added)))
    else:
        core.out("%s added to %d branch(es), switched OFF — `globalresource set %s --on` to load it."
                 % (display, len(added), display))


def cmd_globalresource_refresh(args):
    """Re-hash a registered file from the bytes on disk.

    The registry stores each asset's `size` and `sha256`, and the served URL carries that
    hash — the endpoint refuses bytes that do not match it, so a file edited in place
    inside `tenant-files/` 404s on every page while the tree still lists it. Editing the
    bytes is a normal thing to do (a generated lookup table, a rebuilt bundle); this is
    how the registry is told about it, without `rm` + `add` losing the file's order,
    its on/off switch and its skins.
    """
    project = core.Project(args.project)
    touched, missing = [], []
    for branch in _target_branches(project, args.branch):
        reg = _registry(branch)
        assets = reg["assets"] if args.file in (None, "", "*") else [_find(reg, args.file)]
        for asset in assets:
            if asset is None:
                continue
            abs_path = os.path.join(project.root, "tenant-files", asset["path"])
            if not os.path.isfile(abs_path):
                missing.append((branch.get("name"), _display(asset)))
                continue
            with open(abs_path, "rb") as fh:
                data = fh.read()
            new_sha, new_size = sha256_of(data), len(data)
            if asset.get("sha256") == new_sha and asset.get("size") == new_size:
                continue
            old_size = asset.get("size")
            asset["sha256"], asset["size"] = new_sha, new_size
            touched.append((branch.get("name"), _display(asset), old_size, new_size))

    if touched:
        project.mark(core.F_BRANCHES)
        project.save()
    for name, disp, old, new in touched:
        core.out("  %-10s %-40s %8s -> %-8s re-hashed" % (name, disp, old, new))
    for name, disp in missing:
        core.out("  %-10s %-40s bytes missing from the bundle" % (name, disp))
    if not touched and not missing:
        core.out("nothing to do — every registered file already matches its bytes.")


def cmd_globalresource_mkdir(args):
    """Create an empty folder. Folders exist so a whole kit can be switched off in one move."""
    project = core.Project(args.project)
    path = safe_folder(args.path)
    if not path:
        raise core.ToolError("a folder needs a name")
    touched = []
    for branch in _target_branches(project, args.branch):
        reg = _registry(branch)
        _ensure_folders(reg, path, "MANUAL", None, args.by)
        _renumber(reg)
        touched.append(str(branch.get("name")))
    project.mark(core.F_BRANCHES)
    project.save()
    core.out("folder %s created on %s" % (path, ", ".join(touched)))


def cmd_globalresource_add_zip(args):
    """Unpack an archive into a folder of its own, keeping its layout and working out a load order.

    A folder of its own is not tidiness: it is what makes "switch this whole kit off" one click, and
    what keeps two kits from colliding on a shared ``main.css``.

    The order is decided by the strongest evidence available — the same rules the platform's own
    upload uses, so a project built here and one built in the UI come out identical:

      1. a demo page inside the archive: its ``<link>``/``<script>`` order is the library author's
         own statement of what needs what;
      2. the known-library table, in dependency order;
      3. what each script publishes and mentions;
      4. folder depth and name, so the result is at least stable.
    """
    project = core.Project(args.project)
    if not os.path.isfile(args.file):
        raise core.ToolError("local file not found: %r" % args.file)
    with open(args.file, "rb") as fh:
        raw = fh.read()

    files, pages, notes, skipped = _read_archive(raw)
    if not files:
        raise core.ToolError("the archive contained nothing this project can ship")

    files, pages, root_note = _strip_common_root(files, pages)
    if root_note:
        notes.append(root_note)

    target = safe_folder(args.folder or os.path.splitext(os.path.basename(args.file))[0]) or "library"
    archive = safe_segment(os.path.basename(args.file))

    demoted = _drop_minified_twins(files, notes)
    scripts = [p for p in files if kind_of(p) == "JS" and p not in demoted]
    sheets = [p for p in files if kind_of(p) == "CSS" and p not in demoted]

    known = set(scripts) | set(sheets)
    from_html = _order_from_html(pages, known)
    if from_html:
        notes.append("Load order taken from the archive's own HTML page.")
        ordered = _intersect_in_order(from_html, known)
    else:
        ordered = sorted(sheets, key=_heuristic_key) + _order_by_dependency(
            sorted(scripts, key=_heuristic_key), files)

    planned = ordered + sorted(p for p in files if p not in ordered)

    touched = []
    for branch in _target_branches(project, args.branch):
        reg = _registry(branch)
        if any((f.get("path") or "") == target for f in reg["folders"]):
            raise core.ToolError("branch %r already has a folder called %s — pass --folder <other name>"
                                 % (branch.get("name"), target))
        for path in planned:
            inside = path.rsplit("/", 1)[0] if "/" in path else ""
            folder = "%s/%s" % (target, inside) if inside else target
            _ensure_folders(reg, folder, "ZIP", archive, args.by)
            asset = _new_asset(reg, folder, path.rsplit("/", 1)[-1], "ZIP", archive, args.by, files[path])
            reg["assets"].append(asset)
            _write_bytes(project, asset["path"], files[path])
        _renumber(reg)
        touched.append(str(branch.get("name")))

    project.mark(core.F_BRANCHES)
    project.save()

    core.out("%s unpacked into %s/ on %s" % (archive, target, ", ".join(touched)))
    for path in planned:
        core.out("  %-5s %s" % (kind_of(path), path))
    for note in notes:
        core.out("  note: %s" % note)
    for item in skipped:
        core.out("  skipped: %s" % item)
    core.out("Nothing is switched on. Pick what this project loads, e.g.:")
    core.out("  mrjun.py globalresource set %s/<file> --on --project %s" % (target, args.project))


def cmd_globalresource_ls(args):
    """Print each branch's tree, marking what actually loads with its position in the load order."""
    project = core.Project(args.project)
    for branch in project.branches:
        raw = branch.get("globalAssets")
        name = branch.get("name")
        if not isinstance(raw, dict) or not raw.get("assets"):
            core.out("%s: no project-global assets" % name)
            continue
        reg = _registry(branch)
        core.out("%s  (storage %s)" % (name, reg.get("storageId")))
        for folder in sorted(reg["folders"], key=lambda f: f.get("path") or ""):
            core.out("      %-3s %s/" % ("[x]" if folder.get("enabled", True) else "[ ]",
                                         folder.get("path")))
        position = 0
        for asset in sorted(reg["assets"], key=lambda a: a.get("order", 0)):
            mark, box = "   ", "   "
            if includable(asset.get("kind")):
                position += 1
                box = "[x]" if asset.get("enabled") else "[ ]"
                mark = "#%-2d" % position if _loads(reg, asset) else " - "
            skins = asset.get("skins") or []
            core.out("  %s %-3s %-5s %-44s %8d  %s" % (
                mark, box, asset.get("kind"), _display(asset), asset.get("size", 0),
                ("skins: " + ", ".join(skins)) if skins else ""))
        core.out("      # = loads on every page, in that order;  - = switched off, or a folder above it is")


def cmd_globalresource_set(args):
    """Switch a file or a folder on or off, rename it, move it in the load order, pick its skins."""
    project = core.Project(args.project)
    touched = 0
    for branch in _target_branches(project, args.branch):
        reg = _registry(branch)
        what, item = _find(reg, args.name)
        if item is None:
            continue
        touched += 1

        if args.on or args.off:
            if what == "file" and not includable(item.get("kind")):
                raise core.ToolError("%s is not loaded on its own — only a script or a stylesheet has "
                                     "a switch. It is already served at its URL." % _display(item))
            item["enabled"] = bool(args.on)
        if args.rename:
            _rename(project, reg, what, item, args.rename)
        if args.skins is not None:
            if what != "file" or item.get("kind") != "CSS":
                raise core.ToolError("only a stylesheet can be limited to particular skins")
            item["skins"] = _clean_skins(args.skins)
        if args.order is not None and what == "file":
            reg["assets"].remove(item)
            reg["assets"].insert(max(0, min(args.order, len(reg["assets"]))), item)
        if what == "file":
            item["updatedAt"] = core.now_iso()
            item["updatedBy"] = args.by or "builder"
        _renumber(reg)

    if not touched:
        raise core.ToolError("no file or folder called %r on any targeted branch" % args.name)
    project.mark(core.F_BRANCHES)
    project.save()
    core.out("updated %s on %d branch(es)" % (args.name, touched))


def cmd_globalresource_rm(args):
    """Remove a file, or a folder and everything under it, bytes included."""
    project = core.Project(args.project)
    removed = 0
    for branch in _target_branches(project, args.branch):
        reg = _registry(branch)
        what, item = _find(reg, args.name)
        if item is None:
            continue
        doomed = []
        if what == "folder":
            path = item["path"]
            reg["folders"] = [f for f in reg["folders"]
                              if not (f["path"] == path or f["path"].startswith(path + "/"))]
            for asset in list(reg["assets"]):
                holder = asset.get("folder") or ""
                if holder == path or holder.startswith(path + "/"):
                    doomed.append(asset)
        else:
            doomed.append(item)
        for asset in doomed:
            reg["assets"].remove(asset)
            _delete_bytes(project, asset.get("path"))
            removed += 1
        _renumber(reg)

    if not removed:
        raise core.ToolError("no file or folder called %r on any targeted branch" % args.name)
    project.mark(core.F_BRANCHES)
    project.save()
    core.out("removed %d file(s) for %r" % (removed, args.name))


# --------------------------------------------------------------------------- edits


def _clean_skins(value):
    """``""`` means every skin; anything else is checked against the five the platform knows."""
    wanted = [s.strip() for s in (value or "").split(",") if s.strip()]
    known = {s.lower(): s for s in SKINS}
    out = []
    for skin in wanted:
        if skin.lower() not in known:
            raise core.ToolError("unknown skin %r (have: %s)" % (skin, ", ".join(SKINS)))
        if known[skin.lower()] not in out:
            out.append(known[skin.lower()])
    return out


def _rename(project, reg, what, item, new_name):
    if what == "folder":
        old = item["path"]
        parent = old.rsplit("/", 1)[0] if "/" in old else ""
        leaf = safe_segment(new_name)
        new = "%s/%s" % (parent, leaf) if parent else leaf
        if new == old:
            return
        if any(f.get("path") == new for f in reg["folders"]):
            raise core.ToolError("there is already a folder called %s here" % leaf)
        for folder in reg["folders"]:
            if folder["path"] == old or folder["path"].startswith(old + "/"):
                folder["path"] = new + folder["path"][len(old):]
        # The bytes move with the tree: a folder path IS the storage path, which is what keeps a
        # stylesheet's relative url(../fonts/…) working.
        for asset in reg["assets"]:
            holder = asset.get("folder") or ""
            if holder == old or holder.startswith(old + "/"):
                asset["folder"] = new + holder[len(old):]
                _move_bytes(project, asset, reg)
        return

    # The extension decides the kind and how the file is served, so it is preserved.
    wanted = extension_of(item["name"])
    new_leaf = safe_segment(new_name)
    if wanted and extension_of(new_leaf) != wanted:
        new_leaf = "%s.%s" % (os.path.splitext(new_leaf)[0], wanted)
    if new_leaf == item["name"]:
        return
    folder = item.get("folder") or ""
    if any(a is not item and (a.get("folder") or "") == folder
           and (a.get("name") or "").lower() == new_leaf.lower() for a in reg["assets"]):
        raise core.ToolError("there is already a file called %s here" % new_leaf)
    item["name"] = new_leaf
    _move_bytes(project, item, reg)


def _move_bytes(project, asset, reg):
    """Rewrites the stored path and moves the file with it."""
    old = asset.get("path")
    new = storage_path(reg["storageId"], asset.get("folder") or "", asset["name"])
    if old == new:
        return
    src = os.path.join(project.root, "tenant-files", *old.split("/"))
    dst = os.path.join(project.root, "tenant-files", *new.split("/"))
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)
        _prune_empty(project, os.path.dirname(src))
    asset["path"] = new


def _delete_bytes(project, rel_path):
    if not rel_path:
        return
    target = os.path.join(project.root, "tenant-files", *rel_path.split("/"))
    if os.path.isfile(target):
        os.remove(target)
        _prune_empty(project, os.path.dirname(target))


def _prune_empty(project, folder):
    """Walk the now-empty directories back up to tenant-files.

    A bundle that still carries the folder a file was moved OUT of is not broken, but it is a lie
    about what the project contains — and the next reader of the archive cannot tell the leftover
    from a folder somebody meant to leave empty.
    """
    stop = os.path.join(project.root, "tenant-files")
    folder = os.path.abspath(folder)
    while folder.startswith(stop) and folder != stop:
        try:
            if os.listdir(folder):
                return
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)


# --------------------------------------------------------------------------- archive


def _read_archive(raw):
    import io

    files, pages, notes, skipped = {}, {}, [], []
    total = 0
    count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if name.startswith("__MACOSX/") or name.rsplit("/", 1)[-1].startswith("."):
                    continue
                count += 1
                if count > MAX_ENTRIES:
                    skipped.append("more than %d files — the rest was ignored" % MAX_ENTRIES)
                    break
                if info.file_size > MAX_ENTRY_BYTES:
                    skipped.append("%s (larger than %d MB)" % (name, MAX_ENTRY_BYTES // (1024 * 1024)))
                    continue
                data = zf.read(info)
                total += len(data)
                if total > MAX_TOTAL_BYTES:
                    skipped.append("the archive unpacks to more than %d MB — the rest was ignored"
                                   % (MAX_TOTAL_BYTES // (1024 * 1024)))
                    break
                path = safe_relative(name)
                ext = extension_of(path)
                if ext not in ALLOWED_EXT:
                    skipped.append("%s (not a web asset)" % name)
                    continue
                files[path] = data
                if ext in HTML_EXT:
                    # Kept as a file AND read for its load order: a kit's demo page is the library
                    # author's own answer to "in what order do these load", and beats re-deriving it.
                    pages[path] = data
    except zipfile.BadZipFile as exc:
        raise core.ToolError("not a readable zip: %s" % exc)
    return files, pages, notes, skipped


def _strip_common_root(files, pages):
    """Unwrap the single ``kit-1.2.3/`` folder nearly every archive is zipped inside."""
    root = None
    for path in files:
        if "/" not in path:
            return files, pages, None
        first = path.split("/", 1)[0]
        if root is None:
            root = first
        elif root != first:
            return files, pages, None
    if root is None:
        return files, pages, None
    cut = len(root) + 1
    return ({p[cut:]: d for p, d in files.items()},
            {p[cut:]: d for p, d in pages.items() if p.startswith(root + "/")},
            'Unwrapped the archive\'s single top folder "%s".' % root)


def _drop_minified_twins(files, notes):
    """``x.js`` next to ``x.min.js`` is the same program; loading both runs it twice."""
    demoted = set()
    for path in list(files):
        leaf = path.rsplit("/", 1)[-1].lower()
        if not (leaf.endswith(".min.js") or leaf.endswith(".min.css")):
            continue
        twin = path.replace(".min.js", ".js").replace(".min.css", ".css")
        if twin != path and twin in files:
            demoted.add(twin)
            notes.append("%s is stored but ordered last — the archive also ships its minified twin." % twin)
    return demoted


def _order_from_html(pages, known):
    best = []
    for page, data in pages.items():
        try:
            text = data.decode("utf-8", "replace")
        except Exception:
            continue
        base = page.rsplit("/", 1)[0] if "/" in page else ""
        order = []
        for ref in _HTML_REF.findall(text):
            resolved = _resolve(base, ref)
            if resolved and resolved in known and resolved not in order:
                order.append(resolved)
        if len(order) > len(best):
            best = order
    # One script tag pointing at a CDN is not an ordering: require that the page described most of
    # what the archive actually contains before trusting it over the heuristics.
    return best if known and len(best) * 2 >= len(known) else []


def _resolve(base, ref):
    ref = (ref or "").strip()
    if not ref or ref.startswith(("http://", "https://", "//", "data:")):
        return None
    ref = ref.split("?", 1)[0].split("#", 1)[0]
    segs = [] if ref.startswith("/") or not base else [s for s in base.split("/") if s]
    for seg in ref.split("/"):
        if not seg or seg == ".":
            continue
        if seg == "..":
            if segs:
                segs.pop()
            continue
        segs.append(seg)
    return safe_relative("/".join(segs))


def _intersect_in_order(order, candidates):
    picked = [p for p in order if p in candidates]
    rest = sorted([p for p in candidates if p not in picked], key=_heuristic_key)
    return picked + rest


def _named_after(leaf, library):
    """Named after the library, not merely starting with the same letters.

    ``chartjs-plugin-datalabels.js`` is not Chart.js and must not inherit its rank.
    """
    if not leaf.startswith(library):
        return False
    if len(leaf) == len(library):
        return True
    return not leaf[len(library)].isalpha()


def _matching_library(path):
    """The LONGEST matching entry, not the first.

    The table holds both ``react`` and ``react-dom`` and ``react`` comes first, so a first-match rule
    would make ``react-dom.production.min.js`` claim to provide React itself — and the dependency
    pass drops the edge between two files that publish the same global, leaving the UMD build ordered
    before the library it needs.
    """
    leaf = path.rsplit("/", 1)[-1].lower()
    best = -1
    for i, (name, _globals) in enumerate(KNOWN_LIBRARIES):
        if _named_after(leaf, name) and (best < 0 or len(name) > len(KNOWN_LIBRARIES[best][0])):
            best = i
    return best


def _provides_of(name, data):
    """The globals a script appears to publish — recorded so the product's suggestions are instant."""
    provides = set()
    match = _matching_library(name)
    if match >= 0:
        provides.update(KNOWN_LIBRARIES[match][1])
    try:
        head = data[:512 * 1024].decode("utf-8", "replace")
    except Exception:
        return provides
    provides.update(_EXPLICIT_GLOBAL.findall(head))
    provides.update(_UMD_GLOBAL.findall(head))
    return {g for g in provides if len(g) > 1 or g in ("$", "_")}


def _heuristic_key(path):
    match = _matching_library(path)
    rank = match if match >= 0 else len(KNOWN_LIBRARIES)
    lower = path.lower()
    vendor = 0 if any(lower.startswith(d) or ("/" + d) in lower for d in VENDOR_DIRS) else 1
    return (rank, vendor, path.count("/"), path)


def _order_by_dependency(scripts, files):
    if len(scripts) < 2:
        return scripts
    provides, heads = {}, {}
    for path in scripts:
        match = _matching_library(path)
        provides[path] = set(KNOWN_LIBRARIES[match][1]) if match >= 0 else set()
        heads[path] = files[path][:64 * 1024].decode("utf-8", "replace")

    needs = {}
    for path in scripts:
        source = heads[path]
        want = set()
        for other in scripts:
            if other == path:
                continue
            for g in provides[other]:
                if g in provides[path]:
                    continue  # publishes the same global — a variant, not a consumer
                if _mentions(source, g):
                    want.add(other)
                    break
        if _JQUERY_PLUGIN.search(source):
            want.update(o for o in scripts if o != path and "jQuery" in provides[o])
        needs[path] = want

    ordered, placed = [], set()
    progress = True
    while progress and len(ordered) < len(scripts):
        progress = False
        for path in scripts:
            if path in placed or not needs[path] <= placed:
                continue
            ordered.append(path)
            placed.add(path)
            progress = True
    ordered.extend(p for p in scripts if p not in placed)  # a cycle keeps the heuristic order
    return ordered


def _mentions(source, global_name):
    if not source or not global_name:
        return False
    if global_name in ("$", "_"):
        # A bare sigil matches inside strings and minified identifiers; require a call or a member
        # access so `_` in `a_b` does not invent a dependency.
        return (global_name + "(") in source or (global_name + ".") in source
    return re.search(r"\b%s\b" % re.escape(global_name), source) is not None
