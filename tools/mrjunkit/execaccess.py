"""Execution access — who may RUN a rule, a dynamic CRUD, or one CRUD method (doc 08 §"Execution access",
doc 11 §"Execution access").

One object, the same shape wherever it is stored::

    {"publicAccess": false, "authenticatedUserAccess": true, "roleGroups": ["Sales"]}

* `rep-objects.json`   `rules[].access`
* `dynamic-cruds.json` `cruds[].access` — the CRUD's, inherited by every method that does not have its own
* `dynamic-cruds.json` `cruds[].methods[].inheritAccess` + `.access` — the method's own, read ONLY when
  `inheritAccess` is `false`

`publicAccess` = anyone, anonymous visitors included; `authenticatedUserAccess` = any signed-in user; otherwise the
members of `roleGroups` (exact project role-group names). Administrators and authors may always run anything, so
neither flag and no group = administrators and authors only.

⛔ ABSENT / null means **signed-in users** — the default of every rule and CRUD, and of every archive exported
before the setting existed. So the toolkit never writes the key unless asked: a command run without an access
flag leaves the file exactly as it was, and opening something to anonymous visitors is always an explicit act.

A Java (static) CRUD declares its access in code (`@CrudAccess`) — it is not in the export, and nothing here
edits it. The integration's own CRUD-management CRUD (`bl`) is always administrators and authors only.
"""

from . import core

ACCESS_KEYS = ("publicAccess", "authenticatedUserAccess", "roleGroups")
FLAG_KEYS = ("publicAccess", "authenticatedUserAccess")

# The CLI's three named levels. Role groups are the fourth, given with --role-group.
LEVELS = ("anyone", "signed-in", "authors")

# The CRUD-management CRUD of every integration: fixed to administrators and authors, not configurable.
BL_ALIAS = "bl"


def add_access_args(sp, what):
    """--access / --role-group on a parser. `what` names the artefact in the help text."""
    sp.add_argument("--access", choices=LEVELS,
                    help="who may run the %s: anyone (anonymous visitors included) | signed-in (any signed-in "
                         "user — the platform default) | authors (administrators and authors only)" % what)
    sp.add_argument("--role-group", dest="role_groups", action="append", metavar="NAME",
                    help="members of this project role group may run the %s (repeatable; exact name). Role "
                         "groups mean NEITHER flag — do not combine with --access. Administrators and authors "
                         "may always run it" % what)


def access_from_args(args):
    """The access object the flags ask for, or None when no access flag was given."""
    level = getattr(args, "access", None)
    groups = [g.strip() for g in (getattr(args, "role_groups", None) or []) if g and g.strip()]
    if getattr(args, "role_groups", None) and not groups:
        raise core.ToolError("--role-group needs a non-blank role-group name")
    if level and groups:
        raise core.ToolError("--access %s and --role-group are exclusive: role groups are read only when neither "
                             "flag is set (anyone / signed-in), and 'authors' means no group at all. Pass one or "
                             "the other." % level)
    if groups:
        return {"publicAccess": False, "authenticatedUserAccess": False, "roleGroups": list(dict.fromkeys(groups))}
    if level == "anyone":
        return {"publicAccess": True, "authenticatedUserAccess": False, "roleGroups": []}
    if level == "signed-in":
        return {"publicAccess": False, "authenticatedUserAccess": True, "roleGroups": []}
    if level == "authors":
        return {"publicAccess": False, "authenticatedUserAccess": False, "roleGroups": []}
    return None


def is_public(access):
    """True only for an explicit `publicAccess: true` — absent/null is signed-in users, never public."""
    return isinstance(access, dict) and access.get("publicAccess") is True


def describe(access, default_words="signed-in users — the default (no access set)"):
    """One human line for an access value (absent/null included)."""
    if access is None:
        return default_words
    if not isinstance(access, dict):
        return "INVALID (%s, not an object)" % type(access).__name__
    if access.get("publicAccess") is True:
        return "anyone (anonymous visitors included)"
    if access.get("authenticatedUserAccess") is True:
        return "signed-in users"
    groups = access.get("roleGroups") if isinstance(access.get("roleGroups"), list) else []
    groups = [g for g in groups if isinstance(g, str) and g.strip()]
    if groups:
        return "members of role group(s) %s (+ administrators and authors)" % ", ".join(groups)
    return "administrators and authors only"


def shape_problems(value):
    """Why `value` is not a valid access object — [] when it is (None counts as valid: it is the default)."""
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["is %s, not an object {publicAccess, authenticatedUserAccess, roleGroups}"
                % type(value).__name__]
    problems = []
    unknown = sorted(k for k in value if k not in ACCESS_KEYS)
    if unknown:
        problems.append("has unknown key(s) %s (allowed: %s) — the platform ignores them, so whatever they were "
                        "meant to say is not applied" % (", ".join(unknown), ", ".join(ACCESS_KEYS)))
    for k in FLAG_KEYS:
        if k in value and value[k] is not None and not isinstance(value[k], bool):
            problems.append("%s is %r (%s), not a boolean" % (k, value[k], type(value[k]).__name__))
    groups = value.get("roleGroups")
    if groups is not None:
        if not isinstance(groups, list):
            problems.append("roleGroups is %s, not a list of role-group names" % type(groups).__name__)
        else:
            bad = [g for g in groups if not isinstance(g, str)]
            if bad:
                problems.append("roleGroups holds non-string value(s) %s" % ", ".join(repr(b) for b in bad[:3]))
    return problems


def project_role_groups(rep):
    """The role-group NAMES the export defines (rep-objects.roleGroups — what `rolegroup list` prints)."""
    return {g.get("name") for g in (rep.get("roleGroups") or []) if isinstance(g, dict) and g.get("name")}


def unknown_groups(access, known):
    if not isinstance(access, dict) or not isinstance(access.get("roleGroups"), list):
        return []
    return [g for g in access["roleGroups"] if isinstance(g, str) and g.strip() and g not in known]


def ignored_groups(access):
    """Role groups listed next to a flag that makes them irrelevant (they are read only when neither is set)."""
    if not isinstance(access, dict) or not isinstance(access.get("roleGroups"), list):
        return None, []
    groups = [g for g in access["roleGroups"] if isinstance(g, str) and g.strip()]
    for k in FLAG_KEYS:
        if access.get(k) is True and groups:
            return k, groups
    return None, []


def method_effective(crud, method):
    """(access, source) a dynamic CRUD method actually runs with: its own when inheritAccess is false, else the
    CRUD's. `source` is 'own' or 'inherited'."""
    if isinstance(method, dict) and method.get("inheritAccess") is False:
        return method.get("access"), "own"
    return (crud.get("access") if isinstance(crud, dict) else None), "inherited"


def warn_unknown_groups(p, access):
    """Print a WARNING for role groups the export does not define (they match nobody until the group exists)."""
    missing = unknown_groups(access, project_role_groups(p.rep))
    if missing:
        core.out("WARNING: role group(s) %s are not in this export's roleGroups (%s) — until a group of that EXACT "
                 "name exists, it matches nobody and only administrators and authors may run this. "
                 "(mrjun.py rolegroup list)"
                 % (", ".join(missing), ", ".join(sorted(project_role_groups(p.rep))) or "none defined"))
