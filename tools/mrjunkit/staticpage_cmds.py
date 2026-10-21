"""Static pages — a page of the tree that answers with its own text or file instead of plugins.

A static page is an ordinary page node (`pluginName: siteMapPage`, same alias / parent / roleAccess) with
`pageType = "static"` and NO children. What it answers with:

  * text  — the `staticBody` property (UTF-8, at most 1 MiB), written in the export directly;
  * a file — bytes under `tenant-files/static-pages/<sha256>/<name>`, the node keeping the TENANT-RELATIVE
    path in `staticFilePath` (+ `staticFileName`, `staticFileSize`). The sha256 in the path is checked by the
    platform before it serves a byte, so the bytes must be exactly what the path says.

`staticContentType` is optional: empty means "decided by the file's name, else by the alias". Docs: 34.

Commands:
  page add-static --parent P --name N --alias app.js (--text S | --text-file F | --file F)
                  [--content-type T] [--auth | --public]
  page set-static --page P [--text S | --text-file F | --file F] [--content-type T] [--dokie]
"""

import copy
import hashlib
import os
import re

from . import core

# ---- the node shape (property names are data in the export — never rename) ----------------------------
PAGE_TYPE = "pageType"
TYPE_STATIC = "static"
TYPE_DOKIE = "dokie"
CONTENT_TYPE = "staticContentType"
BODY = "staticBody"
FILE_PATH = "staticFilePath"
FILE_NAME = "staticFileName"
FILE_SIZE = "staticFileSize"
STATIC_KEYS = (PAGE_TYPE, CONTENT_TYPE, BODY, FILE_PATH, FILE_NAME, FILE_SIZE)

STORAGE_ROOT = "static-pages"
MAX_INLINE_TEXT_BYTES = 1024 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024

# What the platform accepts as a stored path: static-pages/<64 hex>/<safe name>.
FILE_PATH_RE = re.compile(r"^static-pages/([0-9a-f]{64})/([A-Za-z0-9._ ()-]+)$")
# A header value: type/subtype, optional parameters, no line breaks.
CONTENT_TYPE_RE = re.compile(r"(?i)^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*(\s*;\s*[^;\r\n]+)*$")

# URL endings the platform hands to its static-file handler unless a STATIC page claims them. A NON-static page
# whose alias ends like this is saved fine and never opens.
FILE_LIKE_SUFFIXES = (".html", ".css", ".js", ".js.map", ".ico", ".png", ".svg", ".woff2", ".woff", ".ttf",
                      ".gif", ".map", ".jpg", ".jpeg", ".webp", ".txt", ".comssets", ".img", ".image", ".eot")


def is_static(node):
    return string_prop(node, PAGE_TYPE) == TYPE_STATIC


def string_prop(node, key):
    slot = (node.get("properties") or {}).get(key)
    if not isinstance(slot, dict):
        return None
    return slot.get("stringValue")


def long_prop(node, key):
    slot = (node.get("properties") or {}).get(key)
    if not isinstance(slot, dict):
        return None
    return slot.get("longValue")


def safe_segment(name):
    """The platform's rule for a stored file name — the same characters, so the path matches FILE_PATH_RE.
    No `+`: file storage URL-decodes the path it reads (a `+` becomes a space), so such a file is never found."""
    leaf = (name or "").replace("\\", "/").split("/")[-1].strip()
    leaf = re.sub(r"[^A-Za-z0-9._ ()-]", "-", leaf)
    leaf = leaf.replace(" ", "-")
    leaf = re.sub(r"-{2,}", "-", leaf)
    leaf = leaf.replace("-ver-", "-ver_")
    leaf = leaf.strip(".-")
    return leaf or "file"


def looks_like_file_url(alias):
    # Case-sensitive, like the platform: `About.HTML` is not handed to the static-file handler and opens.
    a = alias or ""
    return any(a.endswith(s) for s in FILE_LIKE_SUFFIXES)


# ---- writing ----------------------------------------------------------------------------------------------

def _string_slot(key, value):
    return core.make_property_slot(key, value)


def _long_slot(key, value):
    return {"key": key, "propertyType": "LONG", "required": False, "hidden": False,
            "fieldPanelClass": None, "arguments": {}, "longValue": value, "localizedStringValue": {}}


def _set(props, key, value, long_value=False):
    if value is None:
        props.pop(key, None)
    else:
        props[key] = _long_slot(key, value) if long_value else _string_slot(key, value)


def _read_text(args):
    if getattr(args, "text", None) is not None:
        return args.text
    if getattr(args, "text_file", None):
        if not os.path.isfile(args.text_file):
            raise core.ToolError("text file not found: %r" % args.text_file)
        with open(args.text_file, "rb") as fh:
            raw = fh.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise core.ToolError("%s is not UTF-8 text — pass it as --file instead" % args.text_file)
        return text
    return None


def _store_file(project, path):
    if not os.path.isfile(path):
        raise core.ToolError("local file not found: %r" % path)
    with open(path, "rb") as fh:
        data = fh.read()
    if not data:
        raise core.ToolError("%s is empty — an empty response is --text ''" % path)
    if len(data) > MAX_FILE_BYTES:
        raise core.ToolError("%s is %d bytes; a static page file is at most %d" % (path, len(data), MAX_FILE_BYTES))
    sha = hashlib.sha256(data).hexdigest()
    name = safe_segment(os.path.basename(path))
    rel = "%s/%s/%s" % (STORAGE_ROOT, sha, name)
    dest = os.path.join(project.root, "tenant-files", *rel.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(data)
    return rel, name, len(data)


def _apply(project, page, args, make_static=True):
    """Writes the static-page properties from the command's arguments. Only what was passed changes."""
    props = page.setdefault("properties", {})
    if getattr(args, "dokie", False):
        _set(props, PAGE_TYPE, TYPE_DOKIE)
        return "dokie"
    if make_static:
        _set(props, PAGE_TYPE, TYPE_STATIC)
    sources = [s for s in ("text", "text_file", "file") if getattr(args, s, None) is not None]
    if len(sources) > 1:
        raise core.ToolError("give ONE of --text, --text-file, --file")
    # Every check before any byte is written, so a refused command leaves no file behind in tenant-files/.
    ct = None
    if getattr(args, "content_type", None) is not None:
        ct = args.content_type.strip()
        if ct and not CONTENT_TYPE_RE.match(ct):
            raise core.ToolError("--content-type must look like type/subtype, e.g. text/javascript: %r" % ct)
    text = _read_text(args)
    if text is not None:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if text.startswith("﻿"):
            text = text[1:]
        if len(text.encode("utf-8")) > MAX_INLINE_TEXT_BYTES:
            raise core.ToolError("the text is larger than %d bytes — pass it as --file" % MAX_INLINE_TEXT_BYTES)
        _set(props, BODY, text)
        # The editor's text is served only when there is no file: a new text replaces a stored file.
        for key in (FILE_PATH, FILE_NAME, FILE_SIZE):
            props.pop(key, None)
    if getattr(args, "file", None):
        rel, name, size = _store_file(project, args.file)
        _set(props, FILE_PATH, rel)
        _set(props, FILE_NAME, name)
        _set(props, FILE_SIZE, size, long_value=True)
    if ct is not None:
        _set(props, CONTENT_TYPE, ct or None)
    return "static"


def cmd_page_add_static(args):
    p = core.Project(args.project)
    root = p.root_content
    parent = root if args.parent in ("root", "ROOT") else core.find_node(root, args.parent)
    if parent.get("pluginName") != "siteMapPage":
        raise core.ToolError("--parent must be a page")
    if is_static(parent):
        raise core.ToolError("a static page cannot contain pages — choose another --parent")
    alias = (args.alias or "").strip().strip("/")
    if not alias or "/" in alias:
        raise core.ToolError("--alias is the page's last URL segment, with its extension (e.g. robots.txt)")
    if any((c.get("alias") == alias) for c in (parent.get("children") or [])):
        raise core.ToolError("the parent already has a page with alias %r" % alias)
    if not any(getattr(args, s, None) is not None for s in ("text", "text_file", "file")):
        raise core.ToolError("give the response: --text, --text-file or --file")

    page = {
        "id": None,
        "identifier": None,
        "uniqueIdentifier": None,
        "name": args.name,
        "pluginName": "siteMapPage",
        "isBehaviour": False,
        "active": True,
        "alias": alias,
        "treeOpened": False, "treeDisabled": False, "treeSelected": False,
        "includedInParsis": False,
        "children": [],
        "properties": {},
        "order": core.next_order(parent),
        "childPluginAdded": False,
        "virtualContent": False,
    }
    page["identifier"] = core.new_uuid()
    core.regen_ids(page, p.branch_id())
    page["roleAccess"] = copy.deepcopy(parent.get("roleAccess") or {
        "publicReadAccess": False, "authenticatedUserAccess": True, "accessors": {}, "roleGroupAccessors": {}})
    if args.auth:
        page["roleAccess"]["publicReadAccess"] = False
        page["roleAccess"]["authenticatedUserAccess"] = True
    elif args.public:
        page["roleAccess"]["publicReadAccess"] = True
        page["roleAccess"]["authenticatedUserAccess"] = False
    _apply(p, page, args)

    parent.setdefault("children", []).append(page)
    p.mark(core.F_BRANCHES)
    p.save()
    core.out("static page added: %s (alias=%s)\n  identifier=%s\n  answers with: %s"
             % (args.name, alias, page["identifier"], _describe(page)))


def cmd_page_set_static(args):
    p = core.Project(args.project)
    root = p.root_content
    page = core.find_node(root, args.page)
    if page is root:
        raise core.ToolError("the site root cannot be a static page")
    if page.get("pluginName") != "siteMapPage":
        raise core.ToolError("%r is not a page" % args.page)
    if not args.dokie and any(c.get("pluginName") == "siteMapPage" for c in (page.get("children") or [])):
        raise core.ToolError("%r has pages inside it; a static page cannot — move them first" % args.page)
    kind = _apply(p, page, args)
    p.mark(core.F_BRANCHES)
    p.save()
    core.out("page %s is now %s%s" % (page.get("name"), kind,
                                     (": " + _describe(page)) if kind == "static" else ""))


def _describe(page):
    ct = string_prop(page, CONTENT_TYPE) or "(type from the name)"
    if string_prop(page, FILE_PATH):
        return "file %s, %s bytes, %s" % (string_prop(page, FILE_NAME), long_prop(page, FILE_SIZE), ct)
    body = string_prop(page, BODY) or ""
    return "text, %d bytes, %s" % (len(body.encode("utf-8")), ct)
