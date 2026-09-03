"""Core helpers: project I/O, atomic writes, formatting, id generation, resolvers.

Everything the command modules build on lives here so the hard rules from
TOOLS-SPEC.md are encoded in exactly one place.
"""

import datetime
import json
import os
import sys
import tempfile
import uuid

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ToolError(Exception):
    """A user-facing error. Printed to stderr; process exits non-zero."""


# ---------------------------------------------------------------------------
# File names inside a project directory
# ---------------------------------------------------------------------------

F_TENANT = "tenant.json"
F_BRANCH_META = "branch-metadata.json"
F_BRANCHES = "branches.json"
F_REP = "rep-objects.json"
F_DB_META = "project-db-meta.json"
F_DB_DUMP = "project-db.dump"
F_CRUDS = "dynamic-cruds.json"
F_INTEGRATIONS = "integrations.json"

REP_COLLECTIONS = [
    "sources", "queries", "schedulers", "workflows", "rules", "contexts",
    "formGroups", "forms", "settings", "processGroups", "roleGroups",
    "userRoleGroupAssignments", "mailTemplates", "pdfTemplates",
]

# ruleType -> executor  (hard rule §5)
RULE_EXECUTOR = {
    "PREDICATE": "GroovyPredicate",
    "EXECUTION_RULE": "GroovyExecutionRule",
    "VALIDATION_RULE": "GroovyValidationRule",
}

# db types as they appear in real exports. NOTE the real exports carry the
# misspelling "POISTGRESQL"; we accept clean names from the CLI and map them to
# whatever the export already uses (see normalize_dbtype).
DBTYPE_CANONICAL = ["POSTGRESQL", "MYSQL", "ORACLE", "SQLSERVER", "SNOWFLAKE"]

PROP_PANEL = "com.devsegment.mrjun.security.common.field.property.supportedfields.PropertyBaseTextFieldPanel"


def new_uuid():
    return str(uuid.uuid4())


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# JSON formatting preservation
# ---------------------------------------------------------------------------


def _detect_indent(text):
    """Return an indent value for json.dump: None (compact) or an int.

    Real exports are minified (no spaces). We preserve that. If a file was
    pretty-printed we detect the leading indent and reuse it.
    """
    # Skip leading whitespace / opening bracket
    i = 0
    n = len(text)
    while i < n and text[i] in "[{":
        i += 1
        # look at what follows the first opening bracket
        if i < n and text[i] == "\n":
            # pretty printed; count spaces on next line
            j = i + 1
            spaces = 0
            while j < n and text[j] == " ":
                spaces += 1
                j += 1
            return spaces if spaces else 2
        return None  # compact
    return None


class JsonFile:
    """A loaded JSON file that remembers its path and formatting."""

    def __init__(self, path, data, indent):
        self.path = path
        self.data = data
        self.indent = indent

    def dumps(self):
        if self.indent is None:
            return json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        return json.dumps(self.data, ensure_ascii=False, indent=self.indent)


def load_json_file(path, required=True):
    if not os.path.exists(path):
        if required:
            raise ToolError("missing file: %s" % path)
        return None
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError("malformed JSON in %s: %s" % (path, exc))
    return JsonFile(path, data, _detect_indent(text))


def atomic_write(path, text):
    """Write text to path atomically (temp file + os.replace)."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".mrjun-tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_json_file(jf):
    atomic_write(jf.path, jf.dumps())


# ---------------------------------------------------------------------------
# Project — lazy loader/saver of all export files
# ---------------------------------------------------------------------------


class Project:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        if not os.path.isdir(self.root):
            raise ToolError("project dir not found: %s" % root)
        self._cache = {}
        self._dirty = set()

    def path(self, name):
        return os.path.join(self.root, name)

    def _get(self, name, required=True):
        if name not in self._cache:
            self._cache[name] = load_json_file(self.path(name), required=required)
        jf = self._cache[name]
        if jf is None and required:
            raise ToolError("missing file: %s" % self.path(name))
        return jf

    # typed accessors -------------------------------------------------------
    @property
    def tenant(self):
        return self._get(F_TENANT).data

    @property
    def rep_file(self):
        return self._get(F_REP)

    @property
    def rep(self):
        return self.rep_file.data

    @property
    def branches_file(self):
        return self._get(F_BRANCHES)

    @property
    def branches(self):
        return self.branches_file.data

    @property
    def root_content(self):
        return self.branches[0]["rootContent"]

    @property
    def db_file(self):
        return self._get(F_DB_DUMP)

    @property
    def db(self):
        return self.db_file.data

    @property
    def cruds_file(self):
        return self._get(F_CRUDS, required=False)

    @property
    def integrations(self):
        """integrations.json as a list (empty when the project has no integrations).

        Carries the link between an integration and the source rows that hold its data
        (`dataSourceIdentifiers`) — which is what the import rebinds to the target tenant's own
        integration schema. See doc 00 §9.
        """
        jf = self._get(F_INTEGRATIONS, required=False)
        data = jf.data if jf is not None else []
        return data if isinstance(data, list) else []

    def ensure_cruds_file(self):
        """Return the dynamic-cruds JsonFile, creating it if absent."""
        jf = self._get(F_CRUDS, required=False)
        if jf is None:
            jf = JsonFile(self.path(F_CRUDS), {"exportVersion": 1, "cruds": []}, None)
            self._cache[F_CRUDS] = jf
        return jf

    # dirty tracking --------------------------------------------------------
    def mark(self, name):
        self._dirty.add(name)

    def save(self):
        for name in self._dirty:
            save_json_file(self._cache[name])
        self._dirty.clear()

    # tenant-derived identity ----------------------------------------------
    def realm_client(self):
        """Return (realmName, clientName), copied off an existing rep object
        if possible, else derived from the tenant domain/alias.
        """
        for coll in ("queries", "sources", "rules", "contexts", "forms",
                     "formGroups", "settings"):
            for obj in self.rep.get(coll, []) or []:
                if isinstance(obj, dict) and obj.get("realmName"):
                    return obj["realmName"], obj.get("clientName")
        domain = self.tenant.get("domain", "")
        if "." in domain:
            realm, client = domain.split(".", 1)
            return realm, client
        alias = self.tenant.get("alias", "app")
        return alias, alias

    def locales(self):
        return list(self.tenant.get("locales", ["en_US"]))

    def default_locale(self):
        """The project's DEFAULT language (the "authoritative" locale — base column values, form
        default-locale writes, `locale fill` source). Prefer tenant.json `defaultLocale` when set and
        valid; otherwise fall back to locales[0]. `defaultLocale` round-trips through the .mrjun
        (tenant.json) and the platform import (TenantDomain.g_default_locale) — see 20-localization.md."""
        locs = self.locales()
        dl = self.tenant.get("defaultLocale")
        if dl and dl in locs:
            return dl
        return locs[0] if locs else "en_US"

    def branch_id(self):
        return self.root_content.get("branchId")

    def rimm_source_identifier(self):
        meta = self._get(F_DB_META, required=False)
        if meta:
            return meta.data.get("rimmSourceIdentifier")
        return None


# ---------------------------------------------------------------------------
# Content-tree traversal
# ---------------------------------------------------------------------------



def looks_uuid(s):
    """True for a uuid4-shaped identifier. Anything else is a SYMBOLIC identifier."""
    if not isinstance(s, str) or len(s) != 36:
        return False
    parts = s.split("-")
    return len(parts) == 5 and all(all(ch in "0123456789abcdefABCDEF" for ch in p) for p in parts)


def regen_ids(node, branch_id=None):
    """Give a CLONED content subtree fresh identifiers — the ONLY correct way to clone.

    ⛔ Do not reimplement this in a generator. The rule is not "keep a list of symbolic ids":
    it is **regenerate ONLY uuid-shaped identifiers, keep every non-uuid identifier verbatim.**

    A non-uuid identifier is a page-scoped LAYOUT ANCHOR the runtime resolves by bare name —
    `siteMapPageParsis` (the page's content container), `Layout`, `parsis`, `header`, `logo-plugin`,
    `breadcrumb`, `left-nav`, `footer`, `right-kicker`, `form.parsis`, `filter.parsis`, the
    `<plugin id="…">` targets inside any html. Regenerate one and the platform does NOT fail: it
    creates a fresh EMPTY node under the expected name, renders that, and your configured subtree
    becomes an unrendered orphan — a BLANK PAGE that exports, imports and validates perfectly.
    Symbolic ids are MEANT to repeat across pages; that is not a collision.

    - id               -> None   (rep/content nodes always carry id=null)
    - identifier       -> uuid4 ONLY when it already looks like a uuid
    - uniqueIdentifier -> uuid4 always
    - branchId         -> set when given
    """
    node["id"] = None
    if looks_uuid(node.get("identifier")):
        node["identifier"] = new_uuid()
    node["uniqueIdentifier"] = new_uuid()
    if branch_id is not None:
        node["branchId"] = branch_id
    for ch in node.get("children", []) or []:
        regen_ids(ch, branch_id)
    return node

def iter_nodes(node, parent=None, path=()):
    """Yield (node, parent, path) for node and every descendant.

    path is a tuple of ancestor names (excluding node itself).
    """
    yield node, parent, path
    child_path = path + (node.get("name") or node.get("identifier"),)
    for child in node.get("children", []) or []:
        yield from iter_nodes(child, node, child_path)


def find_node(root, key):
    """Resolve a content node by identifier, then exact name, then unique
    substring of name. Raises ToolError if not found or ambiguous.
    """
    if key in ("root", "ROOT"):
        return root
    by_id = []
    by_uid = []
    by_name = []
    by_sub = []
    kl = key.lower()
    for node, _parent, _path in iter_nodes(root):
        if node.get("identifier") == key:
            by_id.append(node)
        if node.get("uniqueIdentifier") == key or node.get("id") == key:
            by_uid.append(node)
        name = node.get("name") or ""
        if name == key:
            by_name.append(node)
        elif kl and kl in name.lower():
            by_sub.append(node)
    for bucket, label in ((by_id, "identifier"), (by_uid, "uid"), (by_name, "name")):
        if len(bucket) == 1:
            return bucket[0]
        if len(bucket) > 1:
            raise ToolError("ambiguous node %r: %d matches by %s" % (key, len(bucket), label))
    if len(by_sub) == 1:
        return by_sub[0]
    if len(by_sub) > 1:
        names = ", ".join(sorted({n.get("name", "?") for n in by_sub}))[:200]
        raise ToolError("ambiguous node %r: %d name-substring matches (%s)" % (key, len(by_sub), names))
    raise ToolError("content node not found: %r" % key)


def find_parent(root, node):
    for n, parent, _path in iter_nodes(root):
        if n is node:
            return parent
    return None


def node_path(root, node):
    for n, _parent, path in iter_nodes(root):
        if n is node:
            return "/".join(path + (node.get("name") or node.get("identifier") or "?",))
    return "?"


def next_order(parent):
    kids = parent.get("children", []) or []
    if not kids:
        return 0
    return max((k.get("order", 0) or 0) for k in kids) + 1


# ---------------------------------------------------------------------------
# rep-objects resolution
# ---------------------------------------------------------------------------


def resolve_rep(project, collection, key, name_field="name"):
    """Resolve a rep object by identifier, exact name, then unique substring."""
    items = project.rep.get(collection, []) or []
    return _resolve_in_list(items, key, name_field, collection)


def _resolve_in_list(items, key, name_field, label):
    by_id = [o for o in items if o.get("identifier") == key or o.get("id") == key]
    if len(by_id) == 1:
        return by_id[0]
    if len(by_id) > 1:
        raise ToolError("ambiguous %s %r by identifier" % (label, key))
    by_name = [o for o in items if o.get(name_field) == key]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        raise ToolError("ambiguous %s %r: %d exact-name matches" % (label, key, len(by_name)))
    kl = key.lower()
    by_sub = [o for o in items if kl and kl in str(o.get(name_field, "")).lower()]
    if len(by_sub) == 1:
        return by_sub[0]
    if len(by_sub) > 1:
        raise ToolError("ambiguous %s %r: %d substring matches" % (label, key, len(by_sub)))
    raise ToolError("%s not found: %r" % (label, key))


def resolve_context(project, key):
    """Resolve a context by identifier, alias, or name."""
    items = project.rep.get("contexts", []) or []
    by_id = [o for o in items if o.get("identifier") == key]
    if len(by_id) == 1:
        return by_id[0]
    by_alias = [o for o in items if o.get("alias") == key]
    if len(by_alias) == 1:
        return by_alias[0]
    return _resolve_in_list(items, key, "name", "context")


# ---------------------------------------------------------------------------
# Argument value helpers
# ---------------------------------------------------------------------------


def read_value_arg(val):
    """A CLI value that may be '@file' (read file) or a literal string."""
    if val is None:
        return None
    if val.startswith("@"):
        p = val[1:]
        if not os.path.exists(p):
            raise ToolError("file not found: %s" % p)
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    return val


def read_json_arg(val):
    """A CLI value that may be '@file' or inline JSON; returns parsed object."""
    raw = read_value_arg(val)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolError("invalid JSON: %s" % exc)


def parse_typed_kv(pair):
    """Parse a `key=value` with optional type prefix into (key, pyvalue).

    Accepts: key=str:hello, key=num:5, key=bool:true, key=json:[1,2], key=null:
    Bare `key=value` is treated as a string. Also `str:`/`num:` etc allowed
    without a prefix delimiter when the value itself looks typed.
    """
    if "=" not in pair:
        raise ToolError("expected key=value, got %r" % pair)
    key, raw = pair.split("=", 1)
    key = key.strip()
    if ":" in raw:
        typ, rest = raw.split(":", 1)
        typ = typ.strip().lower()
        if typ == "str":
            return key, rest
        if typ == "num":
            return key, _parse_num(rest)
        if typ == "bool":
            return key, rest.strip().lower() in ("1", "true", "yes", "on")
        if typ == "null":
            return key, None
        if typ == "json":
            try:
                return key, json.loads(rest)
            except json.JSONDecodeError as exc:
                raise ToolError("invalid json value for %s: %s" % (key, exc))
    return key, raw


def _parse_num(s):
    s = s.strip()
    try:
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    except ValueError:
        raise ToolError("not a number: %r" % s)


# ---------------------------------------------------------------------------
# Property-slot helpers (settings vs model — hard rule §2)
# ---------------------------------------------------------------------------


def make_property_slot(key, string_value):
    return {
        "key": key,
        "propertyType": "STRING",
        "required": False,
        "hidden": False,
        "fieldPanelClass": PROP_PANEL,
        "arguments": {},
        "stringValue": string_value,
        "localizedStringValue": {},
    }


def get_inner_json(node, slot):
    """Return the parsed inner JSON of properties.<slot>.stringValue, or {}."""
    props = node.get("properties", {}) or {}
    prop = props.get(slot)
    if not prop:
        return {}
    sv = prop.get("stringValue")
    if not sv:
        return {}
    try:
        return json.loads(sv)
    except json.JSONDecodeError as exc:
        raise ToolError("malformed inner JSON in properties.%s of node %s: %s"
                        % (slot, node.get("identifier"), exc))


def set_inner_json(node, slot, obj):
    """Serialize obj into properties.<slot>.stringValue, creating the slot."""
    props = node.setdefault("properties", {})
    text = json.dumps(obj, ensure_ascii=False)
    if slot in props and isinstance(props[slot], dict):
        props[slot]["stringValue"] = text
    else:
        props[slot] = make_property_slot(slot, text)


# ---------------------------------------------------------------------------
# rep object scaffolding (id=null, realm/client, timestamps)
# ---------------------------------------------------------------------------


def new_rep_object(project, extra):
    realm, client = project.realm_client()
    ts = now_iso()
    obj = {
        "message": None,
        "errors": None,
        "id": None,
        "realmName": realm,
        "clientName": client,
        "identifier": new_uuid(),
        "creationTime": ts,
        "modificationTime": ts,
    }
    obj.update(extra)
    return obj


def out(msg):
    sys.stdout.write(msg + "\n")
