"""Core helpers: project I/O, atomic writes, formatting, id generation, resolvers.

Everything the command modules build on lives here so the hard rules from
TOOLS-SPEC.md are encoded in exactly one place.
"""

import datetime
import json
import os
import sys
import tempfile
import unicodedata
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
F_WORKFLOW_HISTORY = "workflow-history.json"
F_PROCESSES = "processes.json"
F_PROCESS_AUDIT = "process-audit-logs.json"
F_DATA_AUDIT = "data-audit-logs.json"
F_RIMM_DATA = "rimm-data.json"

# The rep-objects.json collections, for READING: identifier maps, shape checks, counts.
# Every key is OPTIONAL (doc 00 §6): an export writes the keys of the parts its author ticked and leaves the
# others OUT, and an import leaves that part of the target as it is when its key is absent — so an absent key never
# says "the project has none" ([] does), and a count must not read it as 0 (`inspect` says "absent").
# `apiExposures` (the project's public API endpoints, doc 32 §6) is the key whose absence is the safe value for a
# BUILD: on import, absent or null leaves the target's endpoints untouched, a list replaces them, and [] deletes
# every endpoint together with its key bindings. So nothing may ever create this key — never
# `rep.setdefault(coll, [])` over this list, never an empty default when writing. `inspect` prints
# `api_exposures_state` for it, and `validate` refuses [] and a list.
REP_COLLECTIONS = [
    "sources", "queries", "schedulers", "workflows", "rules", "contexts",
    "formGroups", "forms", "settings", "processGroups", "roleGroups",
    "userRoleGroupAssignments", "featureAccesses", "mailTemplates", "pdfTemplates",
    "apiExposures",
]

# The parts of a .mrjun in the order the platform's Export and Import dialogs show them: (heading, label, the parts
# it can only be imported together with). An export carries exactly the parts its author ticked; an import replaces
# exactly the ticked parts the file CARRIES and leaves every other part of the target project as it is. Whether a
# file carries a part is read from the file itself (doc 00 §"Which parts a file carries") — `archive_parts` below
# mirrors those rules, so a part it reports as not carried is one the Import dialog draws "Not in this file".
ARCHIVE_PARTS = (
    ("Content", "Pages, forms and rules", ()),
    ("Content", "Mail and PDF templates", ()),
    ("Content", "Roles and access", ()),
    ("Content", "Public API endpoints", ()),
    ("Schedulers", "Schedulers", ()),
    ("Workflows", "Workflows", ()),
    ("Workflows", "Version history", ("Workflows",)),
    ("Workflows", "Deployment", ("Workflows",)),
    ("Workflows", "Processes", ("Version history", "Deployment")),
    ("Workflows", "Process audit log", ("Processes",)),
    ("Integrations", "Integration services", ()),
    ("Integrations", "Database", ()),
    ("Integrations", "Data change history", ("Database",)),
    ("Integrations", "Business logic", ()),
)
# The entries an export leaves out with their part, and the part — for the message of a command that needs one.
_PART_OF_ENTRY = {F_BRANCHES: "its pages (Pages, forms and rules)", F_DB_DUMP: "its database (Database)"}
# The parts only a REPORT project has: a project of any other kind is offered the five others alone.
REPORT_ONLY_PARTS = ("Public API endpoints", "Schedulers", "Workflows", "Version history", "Deployment",
                     "Processes", "Process audit log", "Database", "Data change history")


def _rep_list(rep, key):
    """The list under `key`, or None — an explicit null says the same as no key at all."""
    value = rep.get(key) if isinstance(rep, dict) else None
    return value if isinstance(value, list) else None


def listed_parts(labels):
    """Part labels inside a sentence, as the platform's dialogs list them: "pages, forms and rules; schedulers" —
    semicolons, because a label may hold a comma of its own."""
    return "; ".join(label[:1].lower() + label[1:] for label in labels)


def archive_parts(p):
    """What the unpacked archive at `p` carries, part by part, read the way the platform's Import dialog reads it:
    [(heading, label, importable, count, words)] in ARCHIVE_PARTS order, then one ("!", entry, False, None, words) per
    JSON entry the platform could not read.

    `importable` is False both for a part the file does not carry and for one it carries without a part it needs
    (processes without the version history, say) — the dialog cannot tick either. `count` is None where the
    platform does not count. An entry whose JSON cannot be read is evidence of nothing: the part it would carry is not
    offered, and the rest of the file still is."""
    has = p.carries
    unreadable = []

    def document(name):
        """The parsed entry, or None — absent, or unreadable (and then remembered as such)."""
        if not has(name):
            return None
        try:
            return load_json_file(p.path(name), required=True).data
        except ToolError:
            unreadable.append(name)
            return None

    def elements(name, field):
        """The `field` array of a streamed document — which the platform refuses unless it is a JSON object."""
        data = document(name)
        if data is None:
            return None
        if not isinstance(data, dict):
            unreadable.append(name)
            return None
        items = data.get(field)
        return items if isinstance(items, list) else []

    rep = document(F_REP) if has(F_REP) else None
    rep = rep if isinstance(rep, dict) else {}
    meta = document(F_DB_META)
    cruds = elements(F_CRUDS, "cruds") if has(F_CRUDS) else None
    if has(F_CRUDS) and cruds is None and F_CRUDS not in unreadable:
        cruds = []
    integrations = document(F_INTEGRATIONS)
    versions = elements(F_WORKFLOW_HISTORY, "versions")
    processes = elements(F_PROCESSES, "processes")

    found = {}
    mail, pdf = _rep_list(rep, "mailTemplates"), _rep_list(rep, "pdfTemplates")
    found["Pages, forms and rules"] = (has(F_BRANCHES), None, F_BRANCHES)
    found["Mail and PDF templates"] = (mail is not None or pdf is not None, len(mail or []) + len(pdf or []),
                                       "rep-objects mailTemplates / pdfTemplates")
    for label, key in (("Roles and access", "roleGroups"), ("Public API endpoints", "apiExposures"),
                       ("Schedulers", "schedulers"), ("Workflows", "workflows")):
        items = _rep_list(rep, key)
        found[label] = (items is not None, len(items or []), "rep-objects " + key)
    found["Version history"] = (versions is not None, len(versions or []), F_WORKFLOW_HISTORY)
    # With a (readable) history only its versions count; without one, the current rows are all there is to deploy.
    marked = versions if versions is not None else (_rep_list(rep, "workflows") or [])
    deployed = sum(1 for v in marked if isinstance(v, dict) and v.get("deployed") is True)
    found["Deployment"] = (deployed > 0, deployed, "workflow version marked deployed: true")
    found["Processes"] = (processes is not None, len(processes or []), F_PROCESSES)
    found["Process audit log"] = (has(F_PROCESS_AUDIT), None, F_PROCESS_AUDIT)
    found["Integration services"] = (F_INTEGRATIONS not in unreadable and has(F_INTEGRATIONS),
                                     len(integrations) if isinstance(integrations, list) else 0, F_INTEGRATIONS)
    # An export that knows the parts SAYS whether it carries the database (`database` in the meta: the sources travel
    # with the content too, and a database with nothing to dump has no dump); an older file shows it by what it has.
    if isinstance(meta, dict) and "database" in meta:
        carried_db = meta.get("database") is True or str(meta.get("database")).lower() == "true"
        db_words = "%s says \"database\": %s" % (F_DB_META, "true" if carried_db else "false")
    else:
        own_sources = any(isinstance(s, dict) and not str(s.get("name") or "").startswith("RIMM_")
                          for s in (_rep_list(rep, "sources") or []))
        carried_db = (has(F_DB_DUMP) and meta is not None) or has(F_RIMM_DATA) or own_sources
        if has(F_DB_DUMP) and meta is not None:
            db_words = "%s together with %s" % (F_DB_DUMP, F_DB_META)
        elif has(F_RIMM_DATA):
            db_words = "the legacy %s" % F_RIMM_DATA
        elif own_sources:
            db_words = ("a data source of the project's own in rep-objects sources, and no dump: the import replaces "
                        "the target's data sources with no data behind them")
        else:
            db_words = "%s with %s, %s or a data source of the project's own" % (F_DB_DUMP, F_DB_META, F_RIMM_DATA)
        db_words += " — an older file, without the meta's \"database\" mark"
    found["Database"] = (carried_db, None, db_words)
    found["Data change history"] = (has(F_DATA_AUDIT), None, F_DATA_AUDIT)
    found["Business logic"] = (cruds is not None, len(cruds or []), F_CRUDS)

    parts, importable = [], set()
    for heading, label, needs in ARCHIVE_PARTS:
        carried, count, evidence = found[label]
        missing = [n for n in needs if n not in importable]
        if carried and not missing:
            importable.add(label)
            words = evidence
        elif carried:
            words = "carried, but it cannot be ticked: the file does not carry %s" % " or ".join(missing)
        else:
            words = "not in this archive (%s)" % ("no " + evidence if label != "Database" else evidence)
        if label == "Processes" and carried:
            running = sum(1 for c in processes if isinstance(c, dict) and c.get("runtime") is not None)
            words += ", %d running" % running
        parts.append((heading, label, carried and not missing, count, words))
    for name in unreadable:
        parts.append(("!", name, False, None, "cannot be read — the Import dialog does not offer the part it is "
                                                "evidence of (the rest of the file still is)"))
    return parts

def api_exposures_state(rep):
    """What `rep-objects.apiExposures` does on import (doc 32 §6), as (state, count, words).

    "absent" and "null" leave the target's endpoints and key bindings as they are — the only values a build may
    carry; "empty" ([]) deletes every endpoint of the target with its key bindings; "list" replaces the target's
    endpoints with its entries; "invalid" is no list at all, which the import cannot read.
    """
    if "apiExposures" not in rep:
        return "absent", 0, "absent — safe: the target's API endpoints stay as they are"
    value = rep.get("apiExposures")
    if value is None:
        return "null", 0, "null — safe: the target's API endpoints stay as they are"
    if not isinstance(value, list):
        return "invalid", 0, "not a list (%s) — the import cannot read it" % type(value).__name__
    if not value:
        return "empty", 0, "[] — DELETES every API endpoint of the target and every key binding on import"
    return "list", len(value), ("%d endpoint(s) — REPLACE the target's API endpoints on import; the ones not in "
                                "the list are deleted with their key bindings" % len(value))


# The descriptions for AI assistants an endpoint of `apiExposures` may carry (doc 32 §3.16, §6): `aiDescriptions`, a
# map from an operation key to its text. The operations are the table's `list` and `read`, one per action
# (`action:<ORIGIN>:<actionId>`) and one per rule-call operation (`rule:<operationId>`) — the platform derives the
# same set from the same entry, and on import drops a text under any other key and refuses the whole list for a text
# longer than this. What it stores is the text CLEANED (`api_exposure_ai_clean`), and the limit is counted on that.
API_AI_DESCRIPTION_MAX_LENGTH = 2000
# A text longer than this AS IT ARRIVES (UTF-16 units) is refused without being cleaned: four times what is stored.
API_AI_RAW_MAX_LENGTH = 4 * API_AI_DESCRIPTION_MAX_LENGTH
# The most marks (accents, vowel signs, enclosing marks) kept in a row; normalisation is quadratic in a longer run.
# The cut is made before normalising AND after it: normalising can make a run longer (one character that decomposes
# into two marks), and a text that came out above the limit would be cut again — and so rewritten — by the next save.
API_AI_MAX_MARK_RUN = 30
# More texts than this on one endpoint cannot be descriptions of its operations; the import refuses the whole list.
API_AI_MAX_TEXTS = 500
_API_ACTION_ORIGINS = {"PROCESS_TABLE": ("GLOBAL", "TASK", "START"), "CRUD_TABLE": ("ROW", "CREATE")}
# Invisible characters that carry no text and could carry hidden instructions to a model: zero-width space, the word
# joiner and its invisible operators, the deprecated format characters, the byte-order mark, the interlinear annotation
# marks, the bidi embeddings/overrides/isolates, the tag characters. (The zero-width joiners and the left/right marks
# stay: scripts and emoji sequences need them.)
_API_HIDDEN_CODE_POINTS = ((0x200B, 0x200B), (0x2060, 0x2064), (0x206A, 0x206F), (0xFEFF, 0xFEFF), (0xFFF9, 0xFFFB),
                           (0x202A, 0x202E), (0x2066, 0x2069), (0xE0000, 0xE007F))
_NO_BREAK_SPACES = "\u00a0\u2007\u202f"


def _platform_trim(text):
    """What the platform's plain trim removes: every character up to U+0020 (the store trims operation ids so)."""
    start, end = 0, len(text)
    while start < end and text[start] <= " ":
        start += 1
    while end > start and text[end - 1] <= " ":
        end -= 1
    return text[start:end]


def _id_text(value):
    """An id as the import reads it into a text field: a string as it is, a number or a boolean as its text, else None."""
    ok, text = _api_ai_text(value) if isinstance(value, (str, int, float, bool)) else (False, "")
    return text if ok else None


def _as_list(value):
    """`value` when it is a list, else an empty one — an archive edited by hand can hold anything."""
    return value if isinstance(value, list) else []


def _rule_name(operation):
    """The identifier of the rule a rule-call operation runs, when it is text — an archive edited by hand can hold
    anything there, and only a string names a rule (a list or an object is no rule, and cannot be looked up)."""
    rule = operation.get("ruleIdentifier")
    return rule if isinstance(rule, str) else None


def _json_type(value):
    """The JSON word for a value, for messages."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    return "an array" if isinstance(value, list) else "an object"


def _is_whitespace(ch):
    """What the platform counts as white space when it trims a description and when it tests an id for blank — which
    keeps the no-break spaces, unlike Python's `str.strip()`."""
    return ch in "\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f" or (
        unicodedata.category(ch) in ("Zs", "Zl", "Zp") and ch not in _NO_BREAK_SPACES)


def _is_blank(text):
    """Whether `text` is empty or only white space, as the platform counts it."""
    return all(_is_whitespace(ch) for ch in text)


def _limit_mark_runs(text):
    """`text` with no more than `API_AI_MAX_MARK_RUN` marks in a row — the rest of a longer run is dropped."""
    kept = []
    marks = 0
    for ch in text:
        if unicodedata.category(ch) in ("Mn", "Me", "Mc"):
            marks += 1
            if marks > API_AI_MAX_MARK_RUN:
                continue
        else:
            marks = 0
        kept.append(ch)
    return "".join(kept)


def api_exposure_ai_clean(text):
    """A description as the platform stores it (doc 32 §3.16): line breaks as `\\n`; without control characters other
    than the line break and the tab, without lone surrogates and without the invisible characters above; with no more
    than `API_AI_MAX_MARK_RUN` marks in a row; in normal form (NFC); trimmed. The ORDER is the contract: what is dropped
    goes first, so that normalisation sees the text that will be stored, and the run of marks is cut before AND after
    normalising — so that cleaning the result again changes nothing. The limit is counted on this."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    visible = []
    for ch in text:
        category = unicodedata.category(ch)
        code_point = ord(ch)
        if category == "Cs" or (category == "Cc" and ch not in "\n\t") or any(
                low <= code_point <= high for low, high in _API_HIDDEN_CODE_POINTS):
            continue
        visible.append(ch)
    cleaned = _limit_mark_runs(unicodedata.normalize("NFC", _limit_mark_runs("".join(visible))))
    start, end = 0, len(cleaned)
    while start < end and _is_whitespace(cleaned[start]):
        start += 1
    while end > start and _is_whitespace(cleaned[end - 1]):
        end -= 1
    return cleaned[start:end]


def _utf16_units(text):
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _api_ai_length(text):
    """Characters as the platform counts them: UTF-16 units, which is also what a browser's `maxlength` counts — of the
    text as stored. A text longer than `API_AI_RAW_MAX_LENGTH` as it arrives is too long without being cleaned."""
    raw = _utf16_units(text)
    return raw if raw > API_AI_RAW_MAX_LENGTH else _utf16_units(api_exposure_ai_clean(text))


def _api_ai_text(value):
    """(readable, text): how the import reads one value of `aiDescriptions` — a string as it is, a number or a boolean
    as its text (they are coerced: the platform keeps the literal as written, which this toolkit cannot see, so a
    number's length is only approximate), null as no text. An object or an array cannot be read."""
    if value is None:
        return True, ""
    if isinstance(value, str):
        return True, value
    if isinstance(value, bool):
        return True, "true" if value else "false"
    if isinstance(value, (int, float)):
        return True, json.dumps(value)
    return False, ""


def api_exposure_ai_operation_keys(entry):
    """The keys a description for AI assistants of this `apiExposures` entry can be stored under (doc 32 §3.16):
    nothing for a sign-in endpoint."""
    kind = entry.get("kind")
    keys = []
    if not isinstance(kind, str):
        return keys
    if kind in _API_ACTION_ORIGINS:
        keys += ["list", "read"]
        for action in _as_list(entry.get("actions")):
            action_id = _id_text(action.get("actionId")) if isinstance(action, dict) else None
            if action_id is not None and not _is_blank(action_id) and action.get("origin") in _API_ACTION_ORIGINS[kind]:
                keys.append("action:%s:%s" % (action["origin"], action_id))
    elif kind == "RULE":
        for operation in _as_list(entry.get("operations")):
            operation_id = _id_text(operation.get("operationId")) if isinstance(operation, dict) else None
            if operation_id is not None and _platform_trim(operation_id):
                # the store trims an operation's id
                keys.append("rule:%s" % _platform_trim(operation_id))
    return keys


def api_exposure_ai_note(entry):
    """The tag `api-exposures show` appends to an endpoint for its descriptions for AI assistants: nothing when the
    entry has no member for them (an archive from before descriptions existed, or a null: the import keeps what the
    target has), what the import would store otherwise — the number of texts under keys the endpoint has — and none
    at all (`{}`, only blank texts, only keys it does not have) means the import CLEARS the target's."""
    texts = entry.get("aiDescriptions")
    if texts is None:
        return ""
    if not isinstance(texts, dict):
        return "  [AI texts: not a map — the archive cannot be read, the whole import fails]"
    known = set(api_exposure_ai_operation_keys(entry))
    count = 0
    for key, value in texts.items():
        readable, text = _api_ai_text(value)
        if not readable:
            return "  [AI texts: a value is not text — the archive cannot be read, the whole import fails]"
        if key in known and _utf16_units(text) <= API_AI_RAW_MAX_LENGTH and api_exposure_ai_clean(text):
            count += 1
    if entry.get("kind") == "LOGIN" and texts:
        return "  [AI texts: none stored — a sign-in endpoint has no operations]"
    return "  [AI texts: %s]" % (count if count else "none — the import CLEARS the target's")


def api_exposure_ai_problems(rep):
    """(slug, code, key, words) for each problem in the `aiDescriptions` of a `rep-objects.apiExposures` list.
    "shape" (not a map, or a value that is an object or an array) makes the archive unreadable: the whole import
    fails. "too_long" and "too_many" (more texts than `API_AI_MAX_TEXTS`) make the import refuse the whole list.
    "unknown_key" (an operation the entry does not have) is only dropped by it. Empty for anything that is not a
    list."""
    value = rep.get("apiExposures")
    if not isinstance(value, list):
        return []
    problems = []
    for entry in value:
        if not isinstance(entry, dict) or entry.get("aiDescriptions") is None:
            continue
        slug = entry.get("slug") if isinstance(entry.get("slug"), str) else "?"
        texts = entry["aiDescriptions"]
        if not isinstance(texts, dict):
            problems.append((slug, "shape", "", "is %s, not a map of texts — the archive cannot be read, the whole "
                             "import fails" % _json_type(texts)))
            continue
        if len(texts) > API_AI_MAX_TEXTS:
            problems.append((slug, "too_many", "", "has %d texts, more than an endpoint can have operations (at most "
                             "%d) — the import REFUSES the whole list" % (len(texts), API_AI_MAX_TEXTS)))
            continue
        known = set(api_exposure_ai_operation_keys(entry))
        for key, item in texts.items():
            readable, text = _api_ai_text(item)
            if not readable:
                problems.append((slug, "shape", key, "is %s, not text — the archive cannot be read, the whole import "
                                 "fails" % _json_type(item)))
            elif _api_ai_length(text) > API_AI_DESCRIPTION_MAX_LENGTH:
                problems.append((slug, "too_long", key, "is longer than %d characters — the import REFUSES the "
                                 "whole list" % API_AI_DESCRIPTION_MAX_LENGTH))
            elif key not in known:
                problems.append((slug, "unknown_key", key, "names an operation this endpoint does not have — the "
                                 "import drops the text"))
    return problems


def api_exposure_lines(rep):
    """One line per endpoint of a `rep-objects.apiExposures` list (doc 32 §6) — and, for a rule call, one per
    operation with the rule it runs, flagged when `rules[]` does not have it (after import that operation
    answers 404 until the rule exists; a switched-off one is never called). Empty for anything that is not a
    list."""
    value = rep.get("apiExposures")
    if not isinstance(value, list):
        return []
    known = {r.get("identifier") for r in (rep.get("rules") or []) if isinstance(r, dict)}
    lines = []
    for e in value:
        if not isinstance(e, dict):
            lines.append("  ? an entry that is not an object (%s) — the import refuses the whole list"
                         % type(e).__name__)
            continue
        slug = e.get("slug") if isinstance(e.get("slug"), str) else "?"
        lines.append("  %-13s /%s  %s%s%s" % (e.get("kind"), slug, json.dumps(e.get("name"), ensure_ascii=False),
                                              "" if e.get("enabled") else "  [off]", api_exposure_ai_note(e)))
        if e.get("kind") != "RULE":
            continue
        for op in _as_list(e.get("operations")):
            if not isinstance(op, dict):
                continue
            rule = _rule_name(op)
            path = op.get("path") or ""
            lines.append("      %-6s /%s%s  -> rule %s%s, body %s%s" % (
                op.get("method"), slug, "/" + path if path else "", rule,
                " (%s)" % op["ruleName"] if op.get("ruleName") else "", op.get("input") or "NONE",
                "" if op.get("enabled", True) else "  [off]"))
            if rule and rule not in known:
                if op.get("enabled", True):
                    lines.append("         ! rule %s is not in rules[] — this operation answers 404 "
                                 "endpoint_not_found until it exists" % rule)
                else:
                    lines.append("         (rule %s is not in rules[] — the operation is off, nobody calls it)"
                                 % rule)
    return lines


def api_exposure_missing_rules(rep):
    """(slug, method, path, rule identifier) of every switched-on rule-call operation whose rule `rules[]` lacks."""
    value = rep.get("apiExposures")
    if not isinstance(value, list):
        return []
    known = {r.get("identifier") for r in (rep.get("rules") or []) if isinstance(r, dict)}
    missing = []
    for e in value:
        if not isinstance(e, dict) or e.get("kind") != "RULE":
            continue
        for op in _as_list(e.get("operations")):
            if isinstance(op, dict) and op.get("enabled", True) and _rule_name(op) and _rule_name(op) not in known:
                missing.append((e.get("slug"), op.get("method"), op.get("path") or "", _rule_name(op)))
    return missing


def api_exposure_rule_identifiers(rep):
    """Every rule a rule-call operation of `rep-objects.apiExposures` names — empty when the key is not a list."""
    value = rep.get("apiExposures")
    if not isinstance(value, list):
        return set()
    return {_rule_name(op) for e in value if isinstance(e, dict) and e.get("kind") == "RULE"
            for op in _as_list(e.get("operations")) if isinstance(op, dict) and _rule_name(op)}


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
    except ValueError as exc:
        # JSONDecodeError, and the ValueError Python raises for a number literal of thousands of digits
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
        self._stand_ins = set()

    def path(self, name):
        return os.path.join(self.root, name)

    def carries(self, name):
        """True when the archive has this entry (a file or a folder) on disk — a stand-in does not count."""
        return os.path.exists(self.path(name))

    def stand_in_absent_parts(self):
        """For READ-ONLY commands. An export that left its pages out has no branches.json, one that left the database
        out no project-db.dump — both are valid archives (doc 00 §"Export shape"), and an import of either leaves
        the target's own pages / database as they are. So that every check still reads the parts that ARE there,
        an empty content tree and an empty dump stand in for the absent ones, IN MEMORY: `save` refuses to write a
        stand-in. Returns the entries stood in for."""
        stood = []
        for name, data in ((F_BRANCHES, [{"name": "master", "virtualPlugins": [],
                                          "rootContent": {"children": [], "properties": {}}}]),
                           (F_DB_DUMP, {"format": "nct-jdbc-dump-v1", "schemas": []})):
            if name not in self._cache and not self.carries(name):
                self._cache[name] = JsonFile(self.path(name), data, None)
                self._stand_ins.add(name)
                stood.append(name)
        return stood

    def is_stand_in(self, name):
        return name in self._stand_ins

    def _get(self, name, required=True):
        if name not in self._cache:
            if required and name in _PART_OF_ENTRY and not self.carries(name):
                raise ToolError("missing file: %s — this archive does not carry %s (an export that left that part "
                                "out); `inspect` and `validate` read it as it is" % (self.path(name),
                                                                                       _PART_OF_ENTRY[name]))
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
        stand_ins = sorted(self._dirty & self._stand_ins)
        if stand_ins:
            raise ToolError("refusing to write %s: this archive does not carry it, and what was read in its place "
                            "is an in-memory stand-in" % ", ".join(stand_ins))
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
    # A name or a key in a hand-edited archive may hold a lone surrogate, which a terminal cannot encode: show it escaped.
    try:
        sys.stdout.write(msg + "\n")
    except UnicodeEncodeError:
        sys.stdout.write((msg + "\n").encode("utf-8", "backslashreplace").decode("utf-8"))
