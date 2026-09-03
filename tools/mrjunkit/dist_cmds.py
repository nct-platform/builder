"""`mrjun.py dist` — assemble the library copy that goes to a third party, and REFUSE to if it leaks.

Why this is a command and not a convention: the library folder also holds internal material (the unpacked
reference exports, the maintenance skill, research notes) that must never leave, and every one of those carries
absolute paths from a maintainer's machine and real identities. A `--exclude-from=` flag in a shell
recipe protects nothing the day somebody zips the folder instead. This does the copy AND gates it, so a leak has
to get past a check rather than past someone's memory — including a leak introduced later, by a doc that has not
been written yet.

The gate runs on the OUTPUT, after the copy, so it sees exactly what the recipient would receive.
"""

import os
import re
import shutil

from . import core

# What ships. Everything else in the folder is internal by default — the safe direction for a deny/allow choice.
DISTRIBUTABLE = [
    "README.md",
    "system_prompt.txt",
    "prmpt.txt",
    "tools",
    "pdftemplates",
    "initialtemplates",
    "erp",
]
DOC_RE = re.compile(r"^\d\d[a-z]?-[a-z0-9-]+\.md$")

# Never copied, wherever they appear in the tree.
SKIP_NAMES = {"__pycache__", ".DS_Store", ".git", ".pytest_cache"}
# This module never ships. It carries the identity word list, which is exactly the kind of thing the gate exists
# to keep in-house; `cli.py` imports it optionally so the toolkit still works without it.
SKIP_FILES = {"dist_cmds.py"}
SKIP_SUFFIX = (".pyc", ".pyo", ".orig", ".rej", ".bak")

TEXT_SUFFIX = (".md", ".txt", ".py", ".js", ".json", ".sh", ".yml", ".yaml", ".sql", ".html", ".css",
                # a project-db.dump is plain JSON (nct-jdbc-dump-v1), not a pg_dump — scan it as text or
                # every credential and every row of demo PII inside one walks straight through the gate.
                ".dump")

# Each rule: (label, compiled pattern, why it must not ship).
LEAK_RULES = [
    # The look-behind is what stops a slash-separated word list ("…/Roles/Users/Database…") from reading as a
    # path: a real one starts at a boundary, not in the middle of another word.
    ("absolute home path", re.compile(r"(?<![A-Za-z0-9_.\-])/(?:Users|home)/[A-Za-z0-9._-]+"),
     "names the maintainer's machine and account; the recipient is not that user"),
    ("windows absolute path", re.compile(r"\b[A-Za-z]:\\\\(?:Users|Windows)", re.I),
     "names a specific machine"),
    # A hand-listed module set goes stale the moment a doc cites a new one: `nct-ui/src` and `nct-executor/src`
    # were caught while `nct-workflow/src/...`, `nct-security/src/main/resources/application.yml`,
    # `nct-schedule/src/...`, `nct-executor-common/src/...` and `exec-reactor-core/src/...` all walked through.
    # So match the SHAPE instead — any `<dashed-module>/src` (plus `transit`, the one undashed module) — and keep
    # the bare `mrjun-*` / `rw-core` module names, which leak on their own. The elided citation style the docs
    # use on purpose (`<module>/.../Class.java`, no line number) is deliberately NOT matched: it names a class,
    # not a path anyone could open, and it is the library-wide convention.
    ("platform source tree",
     re.compile(r"\b(?:mrjun-(?:db|view|service|common)|rw-core)\b"
                r"|(?<![\w.-])(?:[a-z][a-z0-9]*(?:-[a-z0-9]+)+|transit)/src\b"),
     "points into a codebase the recipient does not have"),
    ("source citation", re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\.(?:java|kt|mjs)\s*:\s*\d+"),
     "cites a file:line the recipient cannot open, and which rots"),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a secret"),
    # The key is quoted in every JSON export ("sourcePassword": "..."), so an unquoted-key-only pattern
    # matched neither shape that actually leaked. Allow the quotes, and the camelCase prefixes with them.
    ("password assignment",
     re.compile(r"\b\w*(?:password|passwd|secret|api[_-]?key|token)[\"']?\s*[:=]\s*"
                r"[\"'](?!<)(?!placeholder)(?!\\u003c)[^\"']{6,}[\"']", re.I),
     "a secret"),
    ("internal hostname",
     re.compile(r"\b[a-z0-9][a-z0-9-]*\.(?:svc|internal|local)(?:\.[a-z]+)*\b|\bmyprojects\b", re.I),
     "names infrastructure the recipient cannot and should not reach"),
]

# Names that identify WHO made this or WHO paid for it — neither belongs in a library handed to someone else.
#
# A customer name is unambiguous, so it is matched as a whole word. The MAINTAINER is not: a bare first name is
# also ordinary sample data ("Alice Brown, Bob Lee, David Park" in a meeting-agenda template), and flagging that
# trains people to ignore the gate. What actually leaks is the tenant IDENTITY, and it is always structured —
# a realm token inside a database/schema name, a `realm.client` domain, a `realmName` field, or the full name.
# So match those shapes, not the given name.
CUSTOMER_WORDS = ["andranik", "ameria", "ardshin", "kentron", "cognaize", "gmsystem", "greenhouse",
                  "ardguard", "pocbrd", "dlkie"]

MAINTAINER = "david"          # change with the maintainer
MAINTAINER_FULL = r"david[ _.\-]?mkrtchyan"

def _identity_patterns():
    m = re.escape(MAINTAINER)
    return [
        (re.compile(MAINTAINER_FULL, re.I), "maintainer name"),
        (re.compile(r"\b(?:prj|rimm|system|int)_" + m + r"_\w+", re.I), "maintainer tenant in a db/schema name"),
        (re.compile(r"\b" + m + r"\.[a-z0-9_-]+\b", re.I), "maintainer tenant domain"),
        (re.compile(r'"(?:realmName|realm)"\s*:\s*"' + m + r'"', re.I), "maintainer realm"),
    ]

IDENTITY_PATTERNS = _identity_patterns()


def _skip(name):
    return name in SKIP_NAMES or name in SKIP_FILES or name.endswith(SKIP_SUFFIX)


def _sources(root):
    """The distributable entries that actually exist, resolved against the library root."""
    picked = []
    for name in sorted(os.listdir(root)):
        if _skip(name):
            continue
        if name in DISTRIBUTABLE or DOC_RE.match(name):
            picked.append(name)
    return picked


def _copy(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if _skip(n)])
    else:
        shutil.copy2(src, dst)


def _scan_text(path, rel, findings):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return
    for label, pattern, why in LEAK_RULES:
        for m in pattern.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            findings.append((rel, line, label, m.group(0)[:80], why))
    for word in CUSTOMER_WORDS:
        for m in re.finditer(r"\b" + re.escape(word) + r"\b", text, re.I):
            line = text.count("\n", 0, m.start()) + 1
            findings.append((rel, line, "customer name", m.group(0), "identifies a customer to a third party"))
    for pattern, label in IDENTITY_PATTERNS:
        for m in pattern.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            findings.append((rel, line, label, m.group(0)[:60], "identifies the maintainer to a third party"))


def _scan_binary(path, rel, findings):
    """A .mrjun is a zip of JSON — the identity strings inside it reach the reader just the same."""
    import zipfile
    try:
        zf = zipfile.ZipFile(path)
    except Exception:
        return
    for info in zf.infolist():
        if info.is_dir() or info.file_size > 20_000_000:
            continue
        if not info.filename.endswith((".json", ".dump", ".txt", ".xml")):
            continue
        try:
            text = zf.read(info).decode("utf-8", "ignore")
        except Exception:
            continue
        for word in CUSTOMER_WORDS:
            n = len(re.findall(r"\b" + re.escape(word) + r"\b", text, re.I))
            if n:
                findings.append((rel + " :: " + info.filename, 0, "customer name", word + f" x{n}",
                                 "identifies a customer to a third party"))
        for pattern, label in IDENTITY_PATTERNS:
            found = pattern.findall(text)
            if found:
                findings.append((rel + " :: " + info.filename, 0, label,
                                 str(found[0])[:60] + f" x{len(found)}", "identifies the maintainer to a third party"))
        for label, pattern, why in LEAK_RULES:
            if label in ("absolute home path", "windows absolute path", "private key",
                         # the two rules added for the 2026-09 sweep have to reach INSIDE an archive too:
                         # every project-db.dump ships as a .mrjun member, and the internal host that
                         # leaked (`myprojects:8077`) sat in a branches.json member, not a loose file.
                         "password assignment", "internal hostname"):
                found = pattern.findall(text)
                if found:
                    findings.append((rel + " :: " + info.filename, 0, label, str(found[0])[:80], why))


def audit(root):
    """Every leak in the tree at `root`, as (file, line, kind, match, why)."""
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip(d)]
        for name in sorted(filenames):
            if _skip(name):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if name.endswith(TEXT_SUFFIX):
                _scan_text(path, rel, findings)
            elif name.endswith(".mrjun"):
                _scan_binary(path, rel, findings)
    return findings


def cmd_dist(args):
    root = os.path.abspath(args.library)
    out = os.path.abspath(args.out)
    if not os.path.isdir(root):
        raise core.ToolError("not a directory: %s" % root)
    if os.path.exists(out):
        if not args.force:
            raise core.ToolError("output already exists: %s (use --force to replace it)" % out)
        shutil.rmtree(out)

    picked = _sources(root)
    if not any(DOC_RE.match(p) for p in picked):
        raise core.ToolError("no numbered docs under %s — is that the library root?" % root)

    os.makedirs(out)
    for name in picked:
        _copy(os.path.join(root, name), os.path.join(out, name))

    excluded = sorted(n for n in os.listdir(root) if n not in picked and not _skip(n))
    files = sum(len(f) for _, _, f in os.walk(out))
    print("assembled %s" % out)
    print("  copied   : %d entries, %d files" % (len(picked), files))
    print("  left out : %s" % (", ".join(excluded) or "(nothing)"))

    findings = audit(out)
    if not findings:
        print("  leak gate: PASS — no absolute paths, source citations, identities or secrets")
        return 0

    print("\nLEAK GATE FAILED (%d finding%s):" % (len(findings), "" if len(findings) == 1 else "s"))
    for rel, line, kind, match, why in findings[:60]:
        where = "%s:%d" % (rel, line) if line else rel
        print("  x %-52s %-18s %-28s %s" % (where, kind, match, why))
    if len(findings) > 60:
        print("  … and %d more" % (len(findings) - 60))
    if args.keep_on_fail:
        print("\nkept %s for inspection (--keep-on-fail)" % out)
    else:
        shutil.rmtree(out)
        print("\nremoved %s — fix the findings in the library, then re-run" % out)
    return 1
