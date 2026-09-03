"""case init/add/ls — per-project notes that must NEVER live in the builder library.

The builder docs (`doc/builder/*.md`) are a REUSABLE library: they teach the platform for any
domain — banking, customs, ERP, CRM, document flow — so nothing case-specific belongs in them.
Everything you learn while building ONE project (its entities, its screen list, its decisions,
its gotchas) belongs to that project instead.

This command writes those notes into a folder that sits NEXT TO the export, never inside it:

    my-project.mrjun          <- the export you ship
    my-project-case/          <- created here: notes about THIS build
        README.md
        01-domain-model.md
        02-decisions.md

Because the folder is a sibling of the unpacked project directory, `mrjun.py pack` — which only
walks the project dir — never sweeps these notes into the .mrjun.
"""

import os
import re
import sys

from . import core

CASE_DIR_SUFFIX = "-case"

_README = """# Case notes — {name}

Everything specific to THIS build. The reusable library lives in `doc/builder/` and must stay
free of case specifics; this folder is where the case-specific half goes.

Keep here:

- the domain model in the customer's own words (entities, their real names, what each one means);
- the screen/page inventory of this project;
- decisions and their reasons — why this CRUD is a tree, why that action is a rule and not a form;
- environment facts: realm/client, database and schema names, integration names;
- gotchas that only bite this data set.

Do NOT keep here anything that would be true for every project — that is a library change, and it
belongs in `doc/builder/`, written with placeholders rather than this project's names.
"""

_TEMPLATE = """# {title}

_Case notes — {name}. Not part of the reusable builder library._

"""


def _slug(value):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip()).strip("-.")
    return s.lower()


def _case_dir(args):
    """The notes folder: `<project-dir>-case`, or an explicit --dir.

    Deliberately a SIBLING of the project directory, so `pack` cannot pick it up.
    """
    if getattr(args, "dir", None):
        return os.path.realpath(args.dir)
    project = os.path.realpath(getattr(args, "project", ".") or ".")
    parent = os.path.dirname(project)
    base = os.path.basename(project) or "project"
    return os.path.join(parent, base + CASE_DIR_SUFFIX)


def _ensure_dir(path):
    if os.path.exists(path) and not os.path.isdir(path):
        raise core.ToolError("not a directory: %s" % path)
    os.makedirs(path, exist_ok=True)


def cmd_case_init(args):
    target = _case_dir(args)
    _ensure_dir(target)
    name = os.path.basename(target)[: -len(CASE_DIR_SUFFIX)] or "project"
    readme = os.path.join(target, "README.md")
    if os.path.exists(readme) and not args.force:
        core.out("exists, kept: %s" % readme)
    else:
        core.atomic_write(readme, _README.format(name=name))
        core.out("wrote %s" % readme)
    core.out("case notes folder: %s" % target)


def cmd_case_add(args):
    target = _case_dir(args)
    _ensure_dir(target)
    slug = _slug(args.name)
    if not slug:
        raise core.ToolError("--name must contain at least one letter or digit")
    if not slug.endswith(".md"):
        slug += ".md"
    path = os.path.join(target, slug)
    if os.path.exists(path) and not args.force:
        raise core.ToolError("already exists (use --force to overwrite): %s" % path)

    if args.from_file:
        if not os.path.isfile(args.from_file):
            raise core.ToolError("file not found: %s" % args.from_file)
        with open(args.from_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = ""

    title = args.title or os.path.splitext(os.path.basename(slug))[0].replace("-", " ").strip().title()
    name = os.path.basename(target)[: -len(CASE_DIR_SUFFIX)] or "project"
    if body.strip():
        text = body if body.lstrip().startswith("#") else _TEMPLATE.format(title=title, name=name) + body
    else:
        text = _TEMPLATE.format(title=title, name=name)
    if not text.endswith("\n"):
        text += "\n"
    core.atomic_write(path, text)
    core.out("wrote %s (%d bytes)" % (path, len(text.encode("utf-8"))))


def cmd_case_ls(args):
    target = _case_dir(args)
    if not os.path.isdir(target):
        core.out("no case notes yet — run: mrjun.py case init --project <dir>")
        return
    names = sorted(n for n in os.listdir(target) if n.endswith(".md"))
    if not names:
        core.out("case notes folder is empty: %s" % target)
        return
    core.out("case notes in %s:" % target)
    for n in names:
        size = os.path.getsize(os.path.join(target, n))
        core.out("  %-40s %6d bytes" % (n, size))
