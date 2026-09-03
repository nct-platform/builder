"""unpack / pack — a .mrjun is a ZIP of the export files."""

import os
import zipfile

from . import core


def cmd_unpack(args):
    src = args.file
    dst = args.dir
    if not os.path.exists(src):
        raise core.ToolError("file not found: %s" % src)
    if not zipfile.is_zipfile(src):
        raise core.ToolError("not a zip / .mrjun: %s" % src)
    os.makedirs(dst, exist_ok=True)
    with zipfile.ZipFile(src) as zf:
        # guard against path traversal
        for member in zf.namelist():
            target = os.path.realpath(os.path.join(dst, member))
            if not target.startswith(os.path.realpath(dst) + os.sep) and target != os.path.realpath(dst):
                raise core.ToolError("unsafe path in archive: %s" % member)
        zf.extractall(dst)
    core.out("unpacked %s -> %s" % (src, dst))


# Filesystem and editor droppings that must never reach an import archive: they are not export files, they
# make the entry count differ from run to run, and `.DS_Store` in particular is created by Finder every time
# the project folder is merely LOOKED AT — so it lands in the artefact without anyone editing anything.
_JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"}
_JUNK_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
_JUNK_SUFFIX = (".pyc", ".pyo", ".orig", ".rej", ".swp", "~")


def cmd_pack(args):
    src = args.dir
    dst = args.file
    if not os.path.isdir(src):
        raise core.ToolError("dir not found: %s" % src)
    files, skipped = [], []
    for base, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d not in _JUNK_DIRS]
        for name in names:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, src)
            if name in _JUNK_NAMES or name.endswith(_JUNK_SUFFIX):
                skipped.append(rel)
                continue
            files.append((full, rel))
    # deterministic order
    files.sort(key=lambda t: t[1])
    tmp = dst + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, rel in files:
            zf.write(full, rel)
    os.replace(tmp, dst)
    core.out("packed %s -> %s (%d files)" % (src, dst, len(files)))
    if skipped:
        core.out("  skipped %d non-export file(s): %s"
                 % (len(skipped), ", ".join(sorted(skipped)[:6]) + (" …" if len(skipped) > 6 else "")))
