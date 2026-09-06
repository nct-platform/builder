#!/usr/bin/env python3
"""Refuse to publish anything that identifies who built this or where it runs.

This repo IS the distribution, so there is no packaging step left to hide behind: the only thing
between a stray identity and the public is this check, run on every push.

It carries NO word list. The seven structural rules below need none — an absolute home path, a
`Class.java:123` citation, a private key and a hostname are recognisable by shape. Names of people
and customers cannot be, so they come in through the `IDENTITY_WORDS` repository secret
(newline- or comma-separated, case-insensitive, matched as substrings so `rimm_<realm>_<client>`
is caught, not just the bare word). IDENTITY_EXCEPTIONS holds the few literals that contain an
identity word but are platform constants — `OYO_PROJECT_CONFIGURATION` is a role name, not a customer.

Two things are deliberately never printed: a matched identity word, and the body of a matched
secret. The CI log of a public repo is public — a check that republishes what it catches is worse
than no check.

Run locally the same way:   IDENTITY_WORDS="foo,bar" python3 .github/leakscan.py
"""
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# This file is full of the shapes it hunts for; scanning it would flag every rule below.
SKIP_FILES = {".github/leakscan.py"}
SKIP_DIRS = {".git", "__pycache__", ".idea", ".vscode", "node_modules"}
ARCHIVE_SUFFIX = (".mrjun",)
SNIFF = 8192          # bytes examined to decide text vs binary
EXCERPT = 60

# A finding from these rules prints "<redacted>" instead of the match: the match IS the secret.
REDACT = {"password assignment", "private key", "identity word"}

RULES = [
    ("absolute home path",
     re.compile(r"(?<![A-Za-z0-9_.\-])/(?:Users|home)/[A-Za-z0-9._-]+"),
     "names a machine and an account; the reader is not that user"),
    ("windows absolute path",
     re.compile(r"\b[A-Za-z]:\\(?:Users|Windows)", re.I),
     "names a specific machine"),
    # Match the SHAPE of a module path, not a hand-listed module set that goes stale. The elided
    # citation style the docs use on purpose (`<module>/.../Class.java`, no line number) is
    # deliberately NOT matched: it names a class, not a path anyone could open.
    ("platform source tree",
     re.compile(r"\b(?:mrjun-(?:db|view|service|common)|rw-core)\b"
                r"|(?<![\w.-])(?:[a-z][a-z0-9]*(?:-[a-z0-9]+)+|transit)/src\b"),
     "points into a codebase the reader does not have"),
    ("source citation",
     re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\.(?:java|kt|mjs)\s*:\s*\d+"),
     "cites a file:line nobody can open, and which rots on the next build"),
    ("private key",
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
     "a secret"),
    # The key is quoted in every JSON export ("sourcePassword": "..."), so an unquoted-key-only
    # pattern misses the shape that actually leaks. `\b\w*` keeps one start position per word:
    # an unanchored prefix makes this quadratic on long runs.
    ("password assignment",
     re.compile(r"\b\w*(?:password|passwd|secret|api[_-]?key|token)[\"']?\s*[:=]\s*"
                r"[\"'](?!<)(?!placeholder)(?!\\u003c)[^\"']{6,}[\"']", re.I),
     "a secret"),
    # The negative lookahead is what keeps this rule usable. `.local` is both an internal TLD and an
    # ordinary filename segment, so without it every mention of `settings.local.json` — a file Claude Code
    # itself writes, and one the emitted .gitignore has to name — is reported as infrastructure. A hostname
    # does not end in a file extension, so excluding that one shape costs the rule nothing: `foo.local`,
    # `svc.cluster.local` and `api.internal` all still fire.
    ("internal hostname",
     re.compile(r"\b[a-z0-9][a-z0-9-]*\.(?:svc|internal|local)"
                r"(?!\.(?:json|ya?ml|md|txt|py|js|ts|css|html?|xml|log|sh|properties|lock|toml|ini)\b)"
                r"(?:\.[a-z]+)*\b|\bmyprojects\b", re.I),
     "names infrastructure the reader cannot and should not reach"),
]

# Words that must never enter IDENTITY_WORDS, whatever the secret says. `com.devsegment.*` is the
# platform's own package namespace (>30,000 occurrences in the bundled exports) and the vendor name
# is legally required in LICENSE; a roster containing them would demand deleting the copyright line
# and three shipped archives. The secret is unreviewable, so the guard lives here.
PRODUCT_WORDS = {"devsegment", "dokie", "nct", "mrjun", "rimm", "postgres", "groovy"}

# Literals that CONTAIN an identity word but are load-bearing platform constants, not a leak.
# They are removed from a line before the identity test, so `oyo_project_configuration` stays silent
# while `oyoai.com` on the same line would still fire.
IDENTITY_EXCEPTIONS = re.compile(r"oyo_project_configuration", re.I)

# Embedded binary — a base64 image, a hash, a long hex run — is not prose, and a short roster word
# lands inside one by chance (a 3-letter alias matched inside a PNG payload in seven pdftemplates).
# Blobs are stripped before the identity test only; the structural rules still see the whole line,
# which is what catches a credential hidden in one.
BLOB = re.compile(r"[A-Za-z0-9+/=]{40,}")


def identity_pattern():
    """One compiled alternation — a separate pass per word costs ~0.27s each."""
    raw = os.environ.get("IDENTITY_WORDS", "")
    words, ignored = [], []
    short = []
    for w in re.split(r"[,\n]", raw):
        w = w.strip()
        if not w:
            continue
        if w.lower() in PRODUCT_WORDS:
            ignored.append(w)
            continue
        if len(w) < 4:
            short.append(w)
        words.append(w)
    if short:
        print(f"  note: {len(short)} identity word(s) are shorter than 4 characters — short words "
              f"collide with ordinary text; prefer a distinctive form (a surname, a realm token)")
    if not words:
        return None, 0, ignored
    # substring, not \b-anchored: identities arrive glued (rimm_<realm>_<client>, prj_<realm>_user)
    return re.compile("|".join(re.escape(w) for w in words), re.I), len(words), ignored


def scan_text(text, where, findings, identity):
    for i, line in enumerate(text.splitlines(), 1):
        for label, pattern, why in RULES:
            m = pattern.search(line)
            if m:
                excerpt = "<redacted>" if label in REDACT else m.group(0)[:EXCERPT]
                findings.append((where, i, label, excerpt, why))
        if identity and identity.search(BLOB.sub(" ", IDENTITY_EXCEPTIONS.sub("", line))):
            findings.append((where, i, "identity word", "<redacted>",
                             "names who built this or who paid for it"))


def is_text(blob):
    return b"\x00" not in blob[:SNIFF]


def main():
    identity, n_words, ignored = identity_pattern()
    findings = []
    scanned = 0

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if rel in SKIP_FILES:
            continue

        if path.suffix.lower() in ARCHIVE_SUFFIX:
            scanned += 1
            try:
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if info.is_dir():
                            continue
                        try:
                            body = z.read(info.filename)
                        except Exception as exc:            # encrypted / corrupt member
                            findings.append((f"{rel} :: {info.filename}", 0, "unreadable archive member",
                                             type(exc).__name__, "the scanner could not read it, so nobody vetted it"))
                            continue
                        if is_text(body):
                            scan_text(body.decode("utf-8", "replace"),
                                      f"{rel} :: {info.filename}", findings, identity)
            except Exception as exc:                        # not a zip / truncated
                findings.append((rel, 0, "unreadable archive", type(exc).__name__,
                                 "the scanner could not open it, so nobody vetted it"))
            continue

        # No extension allow-list: sniff the bytes. An allow-list silently skips .xml, .groovy,
        # .properties, an extension-less file and anything spelled in capitals.
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        if not is_text(blob):
            continue
        scanned += 1
        scan_text(blob.decode("utf-8", "replace"), rel, findings, identity)

    ci = bool(os.environ.get("GITHUB_ACTIONS"))
    print(f"leakscan: {scanned} files, {len(RULES)} structural rules, "
          f"{n_words} identity word(s) from IDENTITY_WORDS")
    for w in ignored:
        print(f"  note: ignoring identity word {w!r} — it is the vendor/product namespace "
              f"(see PRODUCT_WORDS); a roster entry for it would flag the library's own content")

    if not n_words:
        msg = ("IDENTITY_WORDS is empty — only the structural rules ran; names of people and "
               "customers were NOT checked")
        # A push always has access to repository secrets, so an empty list there is a
        # misconfiguration. A fork PR never gets them, and must not be failed for it.
        if ci and os.environ.get("GITHUB_EVENT_NAME") == "push":
            print(f"::error::{msg}")
            return 1
        print(f"::warning::{msg}" if ci else f"  WARNING: {msg}")

    if not findings:
        print("PASS — no home paths, source citations, secrets, internal hosts or identities")
        return 0

    print(f"\nFAILED ({len(findings)} findings):")
    for where, line, label, match, why in findings[:200]:
        print(f"  x {where}:{line}  {label}  {match}  — {why}")
    if len(findings) > 200:
        print(f"  … and {len(findings) - 200} more")
    print("\nFix these in the repo, or add a deliberate exception to .github/leakscan.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
