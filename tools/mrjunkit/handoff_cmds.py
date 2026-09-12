"""handoff emit — make a DELIVERED project folder resumable by a NEW Claude Code session.

A finished build leaves a folder like this behind:

    my-project/                 <- the delivered folder (this is what `--out` defaults to)
        prmpt.txt               <- the run prompt that built it
        builder/                <- the library copy that was shipped with it
        build-plan/plan.json    <- the decomposed PRD + its status ledger
        work/                   <- the UNPACKED export (this is `--project`)
        work-case/*.md          <- the case notes: what was decided for THIS project
        project.mrjun           <- what was shipped

Everything a person needs is there, and a fresh Claude Code session still starts blind: it does not
know which folder holds the export, that `mrjun.py` exists at all, which library doc answers which
question, or that hand-writing export JSON is how blank pages get shipped. Six months later the
person who knew is gone and the next session re-derives all of it badly, or does not derive it and
hand-edits `rep-objects.json`.

`handoff emit` writes the small set of files Claude Code reads BY ITSELF on startup, so the next
session arrives oriented:

    <out>/CLAUDE.md                               auto-loaded, in the cwd AND in every ancestor
    <out>/.claude/skills/dokie-project/SKILL.md   exactly ONE skill: the router
    <out>/.dokie/project.json                     machine state, including the mode
    <out>/.gitignore                              appended to, never overwritten

Every one of those is REGENERATED from files that already exist — the export itself (via `inspect`),
`build-plan/plan.json`, the case-note folder, and the routing table in `tools/README.md`. Nothing here
is authored twice, so nothing here can drift away from the build. Re-run it after any change; the
output is byte-identical when nothing changed (there is deliberately NO timestamp in any emitted
file — a timestamp would make every run a diff and teach people to ignore the diff).

Why the emitted shape is what it is — each of these was measured against the real Claude Code binary
and is NOT a style preference:

* **Exactly ONE skill.** A skill's `description` is loaded on every single turn; its BODY costs
  nothing until the skill is invoked. Ten small skills means ten descriptions in every turn's context
  forever. So: one description, kept short, and a body that can afford to be generous.
* **The description is silently truncated at ~1535 characters** (with an ellipsis, no warning). We cap
  ours around 1200 and put the load-bearing sentence FIRST, because a truncated tail is a sentence the
  model never sees.
* **The mode is not in the description.** A description is static text baked into the skill; the mode
  changes. The description instead carries an unconditional "read ./.dokie/project.json first", and
  the mode lives in that file (and in CLAUDE.md, which is re-read every session).
* **Skills are discovered ONLY at `<project-root>/.claude/skills/<name>/SKILL.md`** — exactly one
  level deep. `.claude/skills/<group>/<name>/SKILL.md` is silently ignored: no error, no skill.
* **CLAUDE.md is merged with every ancestor's CLAUDE.md.** A delivered folder that lives inside a
  bigger repo inherits that repo's instructions too, so the emitted file says which folder it governs,
  and this command WARNS on stdout when an ancestor CLAUDE.md exists.
* **No hooks, ever.** Under `claude -p` the workspace-trust gate is bypassed and a project hook runs
  with no prompt. This folder is handed between people; an emitted hook would be arbitrary code
  execution on whoever opens it. We never write `.claude/settings.json`, and we warn if one with
  hooks is already there.
* **The credential never passes through the AI, and `emit` never writes one.** `handoff emit` writes no
  `.mcp.json` and no token file at all. The connection is configured by ONE command that reads the
  pasted block from STDIN — `handoff mcp` — because an argument is visible in `ps` to every other user
  on the machine and is recorded in shell history, while STDIN is neither. The file it writes is mode
  600 and git-ignored, and nothing in this module ever prints a credential back.
* **The MCP server key is the constant `dokie`, never the project name.** The server name becomes part
  of every tool name the model sees (`mcp__dokie__<tool>`) and therefore part of every permission
  rule; per-project names make every rule and every habit unshareable.

The library is LINKED, never copied: the router points at `builder/NN-*.md` by relative path and
re-emits the routing table parsed out of `tools/README.md`, so the library stays one copy with one
owner. (The skill file itself is generated rather than symlinked because it is per-project — it
carries this project's counts, paths and case-note index.)
"""

import json
import os
import re
import sys
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO

from . import case_cmds, core, inspect_cmds

# ---------------------------------------------------------------------------
# Fixed names. These are contracts, not preferences — see the module docstring.
# ---------------------------------------------------------------------------

DOC_SUPPORT = "28-support-mode-over-mcp.md"
SKILL_NAME = "dokie-project"          # also the directory name; Claude Code requires the two to match
MCP_SERVER_KEY = "dokie"              # becomes mcp__dokie__<tool> in every permission rule
STATE_REL = ".dokie/project.json"
STATE_SCHEMA = "dokie.project/1"
MARKDOWN_REL = "PROJECT-CONTEXT.md"

# The file that identifies a builder library root. Any doc would do; this one is the decision spine
# and is the last file anyone would delete.
LIB_MARKER = "19-build-decision-procedure.md"

# Appended to .gitignore. The settings.local.json line keeps a
# reviewer's personal permission grants out of a folder that gets handed to someone else.
GITIGNORE_ENTRIES = (".mcp.json", ".claude/settings.local.json")
GITIGNORE_HEADER = "# added by `mrjun.py handoff emit`"

# Cap for the skill description. The real truncation point is ~1535 chars; we stop well short so a
# later edit cannot silently push the tail over the edge.
DESCRIPTION_MAX = 1200

# What makes a file in the output folder OURS. Every emitted file names the command that
# regenerates it, so this doubles as the ownership marker _emit refuses to overwrite without.
GENERATED_MARKER = "handoff emit"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _rel(path, start):
    """`path` as seen from `start`, in the forward-slash form the emitted markdown/JSON uses."""
    return os.path.relpath(path, start).replace(os.sep, "/")


def _library_root(out):
    """Locate the builder library: the delivered copy first, this toolkit's own library second.

    Returns (path, delivered_inside). A delivered copy under `<out>/builder` is what we want — every
    link in the emitted files then survives the folder being zipped and handed to someone else. When
    there is none we fall back to the library this very toolkit lives in and the caller WARNS, because
    those links break the moment the folder moves.
    """
    for cand in (os.path.join(out, "builder"), out):
        if os.path.isfile(os.path.join(cand, LIB_MARKER)):
            return os.path.realpath(cand), True
    tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(tools_dir)
    if os.path.isfile(os.path.join(root, LIB_MARKER)):
        return os.path.realpath(root), False
    return None, False


def _ancestor_claude_mds(out):
    """Every CLAUDE.md ABOVE `out` — each one is merged into the session on top of ours."""
    found = []
    cur = os.path.dirname(os.path.realpath(out))
    while True:
        cand = os.path.join(cur, "CLAUDE.md")
        if os.path.isfile(cand):
            found.append(cand)
        parent = os.path.dirname(cur)
        if parent == cur:
            return found
        cur = parent


# ---------------------------------------------------------------------------
# Facts — every one of them READ, never invented
# ---------------------------------------------------------------------------

# `inspect` is the single place that knows how to count what is in an export, so we run it and read
# its report rather than counting again here: a second counter is a second thing to keep true. The
# parse is pinned to the exact lines `inspect_cmds.cmd_inspect` prints; if that output shape ever
# changes, _inventory() raises instead of quietly reporting zeros.
_RE_PAGES = re.compile(r"^  pages \(siteMapPage\): (\d+)$", re.M)
_RE_NODES = re.compile(r"^  total nodes: (\d+)$", re.M)
_RE_CRUDS = re.compile(r"^dynamic cruds: (\d+)$", re.M)
_RE_REP = re.compile(r"^  ([A-Za-z]+) +(\d+)$", re.M)
_RE_SCHEMA = re.compile(r"^    (\S+): (\d+) tables, (\d+) sequences$", re.M)

# The order the counts are reported in. rep collections only; pages/nodes/cruds/tables are separate.
INVENTORY_REP = ["contexts", "rules", "forms", "formGroups", "queries", "sources", "workflows",
                 "schedulers", "roleGroups", "mailTemplates", "pdfTemplates", "processGroups",
                 "settings"]


def _inspect_report(workdir):
    """Run `inspect` on the workdir and capture its report as text.

    `core.out` writes to `sys.stdout`, so redirect_stdout is enough to borrow the command whole.
    """
    class _InspectArgs(object):
        def __init__(self, project):
            self.project = project
    buf = StringIO()
    with redirect_stdout(buf):
        inspect_cmds.cmd_inspect(_InspectArgs(workdir))
    return buf.getvalue()


def _inventory(workdir):
    """The real counts, from `inspect`'s own report."""
    text = _inspect_report(workdir)
    m_pages, m_cruds = _RE_PAGES.search(text), _RE_CRUDS.search(text)
    if not m_pages or not m_cruds:
        raise core.ToolError("could not read `inspect`'s report — its output shape changed. Fix the "
                             "parse in handoff_cmds._inventory rather than counting a second time.")
    rep = {k: int(v) for k, v in _RE_REP.findall(text)}
    m_nodes = _RE_NODES.search(text)
    inv = {"pages": int(m_pages.group(1))}
    if m_nodes:
        inv["contentNodes"] = int(m_nodes.group(1))
    inv["dynamicCruds"] = int(m_cruds.group(1))
    for key in INVENTORY_REP:
        inv[key] = rep.get(key, 0)
    schemas = _RE_SCHEMA.findall(text)
    if schemas:
        inv["dbSchemas"] = len(schemas)
        inv["dbTables"] = sum(int(t) for _n, t, _s in schemas)
    return inv


def _plan_facts(plan_path):
    """Read `build-plan/plan.json`: the project name, the locales and a per-kind row count.

    A plan row is a CLAIM about the build, not a pointer into it — only a minority of rows carry a
    `selector`, so `withSelector` is reported separately and the router says so out loud. What the
    rows actually resolve to is `coverage --plan`'s job, not ours.
    """
    if not plan_path or not os.path.isfile(plan_path):
        return None
    data = core.load_json_file(plan_path).data
    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise core.ToolError("plan.json must be {items:[...]} or a top-level list: %s" % plan_path)
    kinds = Counter((it.get("kind") or "?") for it in items if isinstance(it, dict))
    status = Counter((it.get("status") or "todo") for it in items if isinstance(it, dict))
    return {
        "project": data.get("project") if isinstance(data, dict) else None,
        "locales": data.get("locales") if isinstance(data, dict) else None,
        "items": len(items),
        "byKind": dict(sorted(kinds.items())),
        "byStatus": dict(sorted(status.items())),
        "withSelector": sum(1 for it in items if isinstance(it, dict) and it.get("selector")),
    }


def _case_index(case_dir):
    """(filename, title) for every case note, title taken from its first `# ` heading."""
    if not case_dir or not os.path.isdir(case_dir):
        return []
    rows = []
    for name in sorted(n for n in os.listdir(case_dir) if n.lower().endswith(".md")):
        title = os.path.splitext(name)[0]
        try:
            with open(os.path.join(case_dir, name), "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
        except OSError:
            pass
        rows.append((name, title))
    return rows


# ---------------------------------------------------------------------------
# The doc routing table — parsed out of tools/README.md, never re-authored
# ---------------------------------------------------------------------------

_ROUTING_HEADING = "## Builder-doc → relevant commands"
_DOC_FILE = re.compile(r"(\d{2}[a-z]?-[A-Za-z0-9._-]+\.md)")


def _split_row(line):
    """Cells of one markdown table row. Splits on unescaped `|` only — cells contain `alias\\|name`."""
    parts = re.split(r"(?<!\\)\|", line.strip())
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [c.strip() for c in parts]


def _routing_rows(lib_root=None):
    """The `Builder-doc → relevant commands` rows out of the DELIVERED library's README, or this one's.

    Reused rather than rewritten on purpose. That table already answers "which doc answers which
    question", it is maintained with the toolkit, and a second copy inside the emitter would be wrong
    within a month — and wrong in the one file a new session trusts most.

    Read from the DELIVERED copy when there is one, because that is where the emitted links point. Taking
    the table from the running toolkit while pointing the links at a delivered library is two versions
    pretending to be one: a folder carrying an older `builder/` gets a row for a doc that is not in it, and
    the link dangles in the file a fresh session opens first. Whichever library the reader will actually
    have is the one whose table they should be given.
    """
    root = lib_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme = os.path.join(root, "tools", "README.md") if lib_root else os.path.join(root, "README.md")
    if not os.path.isfile(readme):
        return []
    rows, inside, past_header = [], False, False
    with open(readme, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("## "):
                if line.strip() == _ROUTING_HEADING:
                    inside = True
                    continue
                if inside:
                    break
            if not inside:
                continue
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = _split_row(s)
            if len(cells) < 3:
                continue
            if set(cells[0]) <= set("-: "):     # the |---|---|---| separator
                past_header = True
                continue
            if not past_header:                 # the `| Doc | Topic | ... |` header
                continue
            # A source cell that forgot to escape a `|` (e.g. `[--settings|--model]`) splits into
            # four cells. Truncating to three would silently DROP the rest of that row's commands, so
            # the overflow is folded back into the last cell, escaped this time.
            if len(cells) > 3:
                cells = cells[:2] + ["\\|".join(cells[2:])]
            rows.append(cells)
    return rows


def _routing_table(lib_rel, lib_abs=None):
    """Re-render the routing rows with every `../NN-*.md` link repointed at the delivered library."""
    rows = _routing_rows(lib_abs)
    if not rows:
        return ["_(routing table unavailable — read `%s/tools/README.md`)_" % lib_rel]
    # In tools/README.md every doc link is written `](../NN-*.md)` — relative to `tools/`. Read from
    # the delivered folder instead, that same link has to point into the library copy.
    def repoint(cell):
        return cell.replace("](../", "](%s/" % lib_rel)

    out = ["| Doc | Topic | Commands |", "|---|---|---|"]
    for doc, topic, cmds in rows:
        m = _DOC_FILE.search(doc)
        doc_cell = "[`%s`](%s/%s)" % (m.group(1), lib_rel, m.group(1)) if m else doc
        out.append("| %s | %s | %s |" % (doc_cell, repoint(topic), repoint(cmds)))
    return out


_REFERENCE_ROWS = [
    ("README.md", "what the folder is, how to weigh a finding, and the rule that keeps it domain-neutral"),
    ("01-solution-shapes.md", "which shape a brief becomes, the artefact budget it carries, what to refuse to build"),
    ("02-navigation-and-front-door.md", "the nav three deliveries converge on, and the two silent ways a nav grant dies"),
    ("03-dynamic-crud-conventions.md", "the five entity kinds and the method skeleton each one needs"),
    ("04-forms-actions-validation.md", "what real forms are built from — and the mechanisms nobody used"),
    ("05-process-and-scheduling.md", "when a process earns a BPMN, how a case is opened, idempotent sweeps"),
    ("06-security-and-roles.md", "the disjunction that defeats persona gating, and row scope that fails closed"),
    ("07-localization.md", "the slots that carry locales, the dead zones, and the escape hatch for each"),
    ("08-charts-and-dashboards.md", "the label+code+measure contract, per-theme palettes, board composition"),
    ("09-studio-components.md", "when a hand-built console is justified, and the anatomy of one that works"),
    ("10-visual-design.md", "how three deliveries looked finished with ZERO authored CSS, and what to do when they cannot"),
    ("knowledge-graph.json", "the same knowledge as queryable data — pattern, rule, artefact, evidence count, anti-pattern"),
    ("INGEST-NEW-REFERENCE.md", "the prompt for folding a NEW reference project (PRD + project.mrjun) into these documents"),
]


def _reference_block(lib_rel, lib_abs=None):
    """Rows for `<library>/references/` — the measured field evidence, when it is present."""
    if lib_abs:
        import os as _os
        if not _os.path.isdir(_os.path.join(lib_abs, "references")):
            return []
    out = [
        "## 6a. Field evidence — what four DELIVERED projects actually did",
        "",
        "§6 says what the platform CAN do. These say what survived production: the shapes four delivered",
        "systems converged on, where they contradicted each other, and which documented mechanisms nobody",
        "ever used. Sources are letters and sizes — the folder names no industry and no customer on purpose,",
        "because a named domain turns a technique into a template. Weighting: seen in ONE delivery = an idea;",
        "in THREE = a convention; contradicted between two = a decision to make consciously, and the document",
        "says which way to jump.",
        "",
        "| Doc | What it settles |",
        "|---|---|",
    ]
    for fn, what in _REFERENCE_ROWS:
        out.append("| [`%s`](%s/references/%s) | %s |" % (fn, lib_rel, fn, what))
    out.append("")
    return out


# ---------------------------------------------------------------------------
# The emitted documents
# ---------------------------------------------------------------------------


def _description(name):
    """The ONE string that costs context on every turn. Load-bearing sentence first, no mode in it."""
    text = (
        "Read `./.dokie/project.json` and this folder's `CLAUDE.md` BEFORE answering anything about "
        "this folder or changing any file in it. This folder is a delivered Dokie project: an "
        "unpacked `.mrjun` export plus the plan it was built from, its case notes, and the builder "
        "library. Use it for any question or change touching %s — its pages, dynamic CRUDs, forms, "
        "Groovy rules, workflows, queries, database dump, localization, charts, PDF/mail templates, "
        "its `.mrjun` export or import, or the `mrjun.py` toolkit. It says where the export, the "
        "plan, the case notes and the library live; which library doc answers which question; which "
        "`mrjun.py` command to run instead of hand-editing export JSON; and the rules that apply to "
        "work in this folder." % (name or "this project")
    )
    if len(text) > DESCRIPTION_MAX:
        raise core.ToolError("skill description is %d chars (max %d) — Claude Code silently truncates "
                             "it at ~1535 and the tail is never read" % (len(text), DESCRIPTION_MAX))
    return text


# SKILL.md sits at <out>/.claude/skills/<name>/SKILL.md — three directories below the folder every path in
# facts is relative to. A link written as `work-case/01-x.md` from there resolves to
# .claude/skills/<name>/work-case/01-x.md and dangles. CLAUDE.md and PROJECT-CONTEXT.md sit AT <out>, so they
# need no prefix; only the skill body does.
SKILL_LINK_PREFIX = "../../../"


def _router_body(facts):
    """The skill BODY: a router, not a tutorial. Costs nothing until the skill is actually invoked."""
    f = facts
    L = []
    L.append("# %s — project router" % f["name"])
    L.append("")
    L.append("This folder is a **delivered Dokie project**: an unpacked `.mrjun` export, the plan it")
    L.append("was built from, the case notes that record what was decided, and a copy of the builder")
    L.append("library. Nothing below is authored by hand — `mrjun.py handoff emit` regenerates this")
    L.append("file from those sources, so re-run it after any change rather than editing it.")
    L.append("")
    L.append("**First: read `./.dokie/project.json`.** It carries the working `mode` and the same")
    L.append("paths in machine form. The mode decides which of §7's two rule sets applies.")
    L.append("")

    L.append("## 1. Where everything is")
    L.append("")
    L.append("| Path | What it is |")
    L.append("|---|---|")
    L.append("| `%s/` | the UNPACKED export — every `mrjun.py` command's `--project` |" % f["workdir_rel"])
    if f["mrjun_rel"]:
        L.append("| `%s` | the toolkit: `python3 %s <command> --project %s` |"
                 % (f["mrjun_rel"], f["mrjun_rel"], f["workdir_rel"]))
    if f["lib_rel"]:
        L.append("| `%s/` | the builder library — the numbered docs §6 routes to |" % f["lib_rel"])
        L.append("| `%s/tools/README.md` | the full command index (the authority is `--help`) |" % f["lib_rel"])
    if f["plan_rel"]:
        L.append("| `%s` | the decomposed PRD + status ledger (§3) |" % f["plan_rel"])
    if f["cases"]:
        L.append("| `%s/` | case notes: what was decided for THIS project (§4) |" % f["case_rel"])
    if f["mrjun_file_rel"]:
        L.append("| `%s` | the packed export that was shipped |" % f["mrjun_file_rel"])
    L.append("| `.dokie/project.json` | machine state: mode, paths, counts |")
    L.append("")
    L.append("⛔ The case notes folder is a **sibling** of the export dir, never inside it — `pack`")
    L.append("walks the export dir only, which is what keeps internal notes out of the shipped file.")
    L.append("")

    L.append("## 2. What is actually in the export")
    L.append("")
    L.append("Counted by `mrjun.py inspect --project %s`; re-run it, do not trust these numbers after"
             % f["workdir_rel"])
    L.append("a change.")
    L.append("")
    L.append("| Kind | Count |")
    L.append("|---|---|")
    for key, val in f["inventory"].items():
        L.append("| %s | %d |" % (key, val))
    L.append("")
    L.append("Tenant `%s` (alias `%s`), realm `%s`, client `%s`. Locales: %s (default `%s`)."
             % (f["name"], f["alias"], f["realm"], f["client"], ", ".join("`%s`" % x for x in f["locales"]),
                f["default_locale"]))
    L.append("")

    L.append("## 3. The plan")
    L.append("")
    if f["plan"]:
        p = f["plan"]
        L.append("`%s` — %d rows." % (f["plan_rel"], p["items"]))
        L.append("")
        L.append("| Kind | Rows |")
        L.append("|---|---|")
        for kind, n in p["byKind"].items():
            L.append("| %s | %d |" % (kind, n))
        L.append("")
        L.append("By status: %s." % ", ".join("%s %d" % (k, v) for k, v in p["byStatus"].items()))
        L.append("")
        L.append("⚠️ Only **%d of %d** rows carry a `selector`. A plan row is a CLAIM that something was"
                 % (p["withSelector"], p["items"]))
        L.append("built, matched by alias/name — it is **not** a pointer to a live object, and a row")
        L.append("marked `done` is not proof the object exists. The only thing that resolves rows")
        L.append("against the build is `mrjun.py coverage --plan %s --project %s`; run it before you"
                 % (f["plan_rel"], f["workdir_rel"]))
        L.append("repeat any claim from this table.")
    else:
        L.append("No `build-plan/plan.json` in this folder. There is no ledger to check the build")
        L.append("against; `mrjun.py coverage --emit --project %s` prints a skeleton from what is"
                 % f["workdir_rel"])
        L.append("actually built, which is the honest starting point.")
    L.append("")

    L.append("## 4. Case notes — the decisions behind this build")
    L.append("")
    if f["cases"]:
        L.append("Read these before changing anything; they hold the domain model in the customer's")
        L.append("own words, the environment facts and the gotchas that only bite this data set.")
        L.append("")
        for name, title in f["cases"]:
            L.append("- [%s](%s/%s)" % (title, f["case_rel"], name))
        L.append("")
        L.append("New findings go **here**, via `mrjun.py case add --project %s --name <slug>` — never"
                 % f["workdir_rel"])
        L.append("into the library, which must stay domain-neutral and reusable.")
    else:
        L.append("None yet. Start one with `mrjun.py case init --project %s`; anything you learn about"
                 % f["workdir_rel"])
        L.append("THIS project belongs there and not in the library.")
    L.append("")

    L.append("## 5. Never hand-write export JSON")
    L.append("")
    L.append("The export encodes rules that are invisible in the JSON: which property slot a plugin's")
    L.append("config lives in, that a non-uuid `identifier` is a layout anchor resolved BY NAME (clone")
    L.append("one and the page renders BLANK while every gate stays green), that a `project-db.dump`")
    L.append("row value must be a JSON **string** or the restore rolls the whole schema back. The")
    L.append("toolkit encodes all of them; a hand edit does not.")
    L.append("")
    L.append("So: find the command first. `python3 %s --help`, then `<command> --help` — `--help` is"
             % (f["mrjun_rel"] or "tools/mrjun.py"))
    L.append("the authority whenever prose disagrees with it. If no command exists, the doc row in §6")
    L.append("says so explicitly; that is when a hand edit is the answer, followed by `validate`.")
    L.append("")

    L.append("## 6. Which library doc answers which question")
    L.append("")
    if f["lib_rel"]:
        L.extend(_routing_table(f["lib_rel"], f.get("lib_abs")))
    else:
        L.append("_No builder library found next to this folder — ask for `builder/` to be restored._")
    L.append("")

    if f["lib_rel"]:
        _ref = _reference_block(f["lib_rel"], f.get("lib_abs"))
        if _ref:
            L.extend(_ref)

    L.append("## 7. Working rules")
    L.append("")
    L.append("Which set applies is `mode` in `./.dokie/project.json`.")
    L.append("")
    L.append("### mode = build — the project is still being assembled")
    L.append("")
    L.append("- Follow the decision spine in `19-build-decision-procedure.md`; it says which phase you")
    L.append("  are in and when that phase is done.")
    L.append("- Write the per-artefact recipe BEFORE the phase that needs it —")
    L.append("  `mrjun.py case recipes --project %s` lists which are still missing. A phase authored"
             % f["workdir_rel"])
    L.append("  without its recipe is where a build quietly comes out shallow.")
    L.append("- Keep the plan honest as you go: a row is `done` only once its test has actually run.")
    L.append("")
    L.append("### mode = support — the project is delivered and live")
    L.append("")
    L.append("- **Reproduce before you change.** Find the object first (`list`, `find`, `show`,")
    L.append("  `db show`) and say which one you are about to touch.")
    L.append("- **Smallest change.** Do not re-run a build generator over a delivered export; do not")
    L.append("  re-author an artefact to fix one field.")
    L.append("- **This folder may not be what is running.** The customer's tenant can have drifted")
    L.append("  since delivery. `livediff` (§8) is the only cheap way to see it — a blank-page orphan")
    L.append("  and a truncated import both log nothing. Assume drift until it says otherwise.")
    L.append("- **Record what you did** as a case note. The next session has only this folder.")
    L.append("")
    L.append("### always")
    L.append("")
    L.append("- The library in `%s/` is a REUSABLE library: never edit it to fit this case."
             % (f["lib_rel"] or "builder"))
    L.append("- Nothing project-specific leaves this folder, and no customer data enters the library.")
    L.append("- Offline gates prove artefacts EXIST and are well-formed. Only opening the page proves")
    L.append("  it RENDERS.")
    L.append("")

    L.append("## 8. The gate ladder")
    L.append("")
    L.append("Run it in this order after any change; each step is cheap and catches what the step")
    L.append("before it cannot see. `--db` takes a libpq conninfo string, not a bare flag.")
    L.append("")
    wd = f["workdir_rel"]
    mj = f["mrjun_rel"] or "tools/mrjun.py"
    L.append("```")
    L.append("python3 %s validate --project %s" % (mj, wd))
    L.append("python3 %s crud verify --project %s --db \"<project-db conninfo>\"" % (mj, wd))
    if f["plan_rel"]:
        L.append("python3 %s coverage --plan %s --project %s" % (mj, f["plan_rel"], wd))
    L.append("python3 %s pack %s %s" % (mj, wd, f["mrjun_file_rel"] or "project.mrjun"))
    L.append("#   import the .mrjun into the tenant, then:")
    L.append("python3 %s livediff --project %s --db \"<platform-db conninfo>\" --tenant %s"
             % (mj, wd, f["alias"] or "<alias>"))
    L.append("```")
    L.append("")
    L.append("### ⛔ Step 6 — RECONCILE WHAT ARRIVED. The import reports DONE either way.")
    L.append("")
    L.append("`validate` proves the file is well-formed; it cannot prove the platform accepted it.")
    L.append("`importDynamicCruds` is the **last** step of `initAllObjects` and it **skips in silence** —")
    L.append("a parse error in `dynamic-cruds.json` (a scalar typed `\"1.0\"` where the DTO wants the")
    L.append("integer `1` is enough) costs you the ENTIRE business-logic layer while pages, rules,")
    L.append("queries, forms, workflows, templates and the database all land normally. The project then")
    L.append("looks complete and every register renders its headers over zero rows, with")
    L.append("`No RSocket connection found for CRUD alias: <alias>` in the UI — a message that points at")
    L.append("the runtime, not at the archive. `livediff` does not cover this: it compares pages, and")
    L.append("prints rep-object counts for the PACKED side only.")
    L.append("")
    L.append("So after every import, put the two inventories side by side and compare the NUMBERS:")
    L.append("")
    L.append("```")
    L.append("python3 %s inspect --project %s      # the packed inventory" % (mj, wd))
    L.append("```")
    L.append("")
    if f["mcp"]:
        L.append("and the live side over MCP — `nct_bl_findAll` (dynamic CRUDs), `nct_query_list_queries`,")
        L.append("`nct_rule_findAll`, `nct_form_findAll`, `nct_workflow_findAll`, `nct_schedule_listJobs`,")
        L.append("`nct_messaging_listTemplates`, `nct_ui_all_pages`. Any collection whose live count is 0")
        L.append("while the packed count is not is a silent skip, not a coincidence.")
    else:
        L.append("and the live side in the console: `/bl` (dynamic CRUDs), Rules, Queries, Form Groups,")
        L.append("Workflows, Schedulers, Mail/Pdf Templates. Any collection that is empty live while the")
        L.append("packed count is not is a silent skip, not a coincidence.")
    L.append("")
    L.append("Then open ONE register and confirm it lists rows. A green gate and a rendered page are")
    L.append("different claims, and only the second one is the product.")
    L.append("")

    if f["mcp"]:
        L.append("## 9. The live tenant over MCP")
        L.append("")
        L.append("The connection lives in `./.mcp.json` — ONE folder is ONE project talking to ONE")
        L.append("tenant, and Claude Code reads that file only for the directory it sits in. It is")
        L.append("already written here; ⛔ never ask for it again, and never echo the token anywhere.")
        L.append("If `/mcp` shows no `%s` server, restart Claude Code once in this folder and" % MCP_SERVER_KEY)
        L.append("approve it — servers connect at session start.")
        L.append("")
        L.append("Every tool arrives as `mcp__%s__<tool>`, which is why the server name is fixed."
                 % MCP_SERVER_KEY)
        L.append("")
        if f["live_url"]:
            L.append("**Where to test:** %s" % f["live_url"])
            L.append("")
            L.append("⛔ Open THAT, never the bare root: the root bounces to the login form and leaves you")
            L.append("on `…/auth;jsessionid=…`, which is not this project and renders none of it.")
        else:
            L.append("**Where to test: NOT RECORDED.** Ask the user once for the project's URL")
            L.append("(`http://<host>:<port>/%s/%s`), then persist it so no later session asks again:"
                     % (f["realm"] or "<realm>", f["client"] or "<client>"))
            L.append("")
            L.append("```")
            L.append("python3 %s handoff emit --project %s --base-url http://<host>:<port>"
                     % (mj, wd))
            L.append("```")
        L.append("")
        L.append("To drive it in a real browser (support mode, %s §8):" % DOC_SUPPORT)
        L.append("")
        L.append("```")
        L.append("python3 %s handoff browser --project %s"
                 % (mj, wd))
        L.append("```")
        L.append("")
        L.append("⛔ The HUMAN logs in — never type a password and never ask for one.")
        L.append("")

    # Repoint every relative link ONCE, here, instead of at each of the ~40 places that build one:
    # a link added later cannot then forget the prefix. Absolute URLs and in-page anchors are left
    # alone, and so is anything already climbing out with "../".
    body = "\n".join(L).rstrip() + "\n"
    return re.sub(r"\]\((?!https?://|#|\.\./|/)", "](" + SKILL_LINK_PREFIX, body)


def _skill_md(facts):
    """SKILL.md = frontmatter (the per-turn cost) + the router body (free until invoked).

    The two scalar values are emitted as JSON, not as bare YAML. JSON is a strict subset of YAML, so a
    json.dumps'd string is always a valid YAML scalar — and it is the only form that stays valid no matter
    what the tenant is called. A bare scalar breaks the moment the text contains ": ", which the description
    does ("...a delivered Dokie project: an unpacked .mrjun export..."): the frontmatter then fails to parse
    and the skill is not loaded AT ALL, silently, which is the one failure this whole file exists to prevent.
    A tenant named "Acme: Fraud" would do the same to `name`. Quoting by hand would mean re-deriving YAML's
    escaping rules here; json.dumps already has them right.
    """
    return (
        "---\n"
        "name: %s\n"
        "description: %s\n"
        "---\n\n%s" % (json.dumps(SKILL_NAME), json.dumps(_description(facts["name"]), ensure_ascii=False),
                       _router_body(facts))
    )


def _claude_md(facts):
    """CLAUDE.md — short on purpose: it is loaded EVERY session, unlike the skill body."""
    f = facts
    L = []
    L.append("# %s" % f["name"])
    L.append("")
    L.append("**This file governs THIS folder** — the delivered Dokie project rooted here. Claude Code")
    L.append("also loads a `CLAUDE.md` from every ANCESTOR directory and merges it with this one; where")
    L.append("they disagree about this project, this file wins.")
    L.append("")
    L.append("Working mode: **%s**. The machine copy of everything below is `./.dokie/project.json`;"
             % f["mode"])
    L.append("it is the file to read first and the file to trust.")
    L.append("")
    L.append("## Start here")
    L.append("")
    L.append("Invoke the **`%s`** skill. It is the router: where the export, the plan, the case notes"
             % SKILL_NAME)
    L.append("and the library are, which library doc answers which question, which `mrjun.py` command")
    L.append("replaces hand-editing export JSON, and the rules for this mode.")
    L.append("")
    L.append("## The five rules that do not depend on the mode")
    L.append("")
    L.append("1. **Never hand-write export JSON.** Run a `mrjun.py` command; it encodes the rules that")
    L.append("   are invisible in the JSON. `python3 %s --help` is the authority."
             % (f["mrjun_rel"] or "tools/mrjun.py"))
    L.append("2. **`%s/` is the export.** Every command takes `--project %s`."
             % (f["workdir_rel"], f["workdir_rel"]))
    L.append("3. **Gate every change**: `validate` → `crud verify --db` → `pack` → import →")
    L.append("   `livediff --db`. Green gates prove artefacts exist; only the page proves it renders.")
    L.append("4. **Project knowledge goes in `%s/`, never in `%s/`.** The library is reusable and"
             % (f["case_rel"], f["lib_rel"] or "builder"))
    L.append("   domain-neutral; this project's names, data and decisions must not enter it.")
    L.append("5. **No credential is ever written into a file in this folder.** The MCP token lives in the")
    L.append("   client's own per-project config (`claude mcp add`, scope `local`), outside this folder.")
    L.append("   Do not paste one into a note, a config, a commit or a reply.")
    L.append("")
    L.append("Regenerate this file (and the skill) with:")
    L.append("")
    L.append("```")
    L.append("python3 %s handoff emit --project %s --mode %s"
             % (f["mrjun_rel"] or "tools/mrjun.py", f["workdir_rel"], f["mode"]))
    L.append("```")
    return "\n".join(L) + "\n"


def _markdown_doc(facts):
    """`--format markdown`: the same router as one plain document, with no Claude Code plumbing."""
    head = ("# %s — project handover\n\n"
            "Working mode: **%s**. Machine state: `./.dokie/project.json`.\n\n"
            "_Regenerate with `python3 %s handoff emit --project %s --format markdown`._\n\n---\n\n"
            % (facts["name"], facts["mode"], facts["mrjun_rel"] or "tools/mrjun.py",
               facts["workdir_rel"]))
    return head + _router_body(facts)


def _state_json(facts):
    """`.dokie/project.json` — the machine half. No timestamp: see the module docstring."""
    f = facts
    state = {
        "schema": STATE_SCHEMA,
        "generatedBy": "mrjun.py handoff emit",
        "mode": f["mode"],
        "project": {
            "name": f["name"],
            "alias": f["alias"],
            "realm": f["realm"],
            "client": f["client"],
            "locales": f["locales"],
            "defaultLocale": f["default_locale"],
            # Where this project is SERVED. rootUrl is the only part a session cannot work out for
            # itself; liveUrl is derived from it and the coordinates above at generation time, so the
            # two cannot drift — this file is regenerated from disk on every emit.
            "rootUrl": f["root_url"],
            "liveUrl": f["live_url"],
        },
        "paths": {
            "export": f["workdir_rel"],
            "library": f["lib_rel"],
            "mrjun": f["mrjun_rel"],
            "plan": f["plan_rel"],
            "caseNotes": f["case_rel"],
            "packed": f["mrjun_file_rel"],
        },
        "inventory": f["inventory"],
        "plan": f["plan"],
    }
    if f["mcp"]:
        state["mcp"] = f["mcp"]
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _emit(path, text, out_root):
    """Write only when the bytes change, so a second run is a no-op instead of a diff.

    ⛔ And never overwrite a file this command did not write. CLAUDE.md is the single most likely file in a
    delivered folder for a human to have authored by hand, and a byte comparison alone cannot tell "stale
    generated output" from "someone's project rules" — it only sees that the bytes differ, and would replace
    them without a word. Every generated file carries the regenerate line as its own marker, so the absence
    of it is unambiguous: refuse, name the file, and let the author decide.
    """
    rel = _rel(path, out_root)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            current = fh.read()
        if current == text:
            core.out("  unchanged  %s" % rel)
            return
        if GENERATED_MARKER not in current:
            raise core.ToolError(
                "%s already exists and was not written by this command (it does not mention "
                "`mrjun.py handoff emit`). Refusing to overwrite it — move or delete it first, or "
                "point --out somewhere else." % rel)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    core.atomic_write(path, text)
    core.out("  wrote      %s" % rel)


def _append_gitignore(out_root):
    """Append the entries that are missing. Never rewrites a line the user already has."""
    path = os.path.join(out_root, ".gitignore")
    existing = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            existing = fh.read()
    have = {ln.strip() for ln in existing.splitlines()}
    missing = [e for e in GITIGNORE_ENTRIES if e not in have]
    if not missing:
        core.out("  unchanged  .gitignore")
        return
    block = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    block += GITIGNORE_HEADER + "\n" + "\n".join(missing) + "\n"
    core.atomic_write(path, existing + block)
    core.out("  appended   .gitignore (%s)" % ", ".join(missing))


# ---------------------------------------------------------------------------
# handoff emit
# ---------------------------------------------------------------------------


def _recorded_state(out_root):
    """What `.dokie/project.json` already declares, or {}. Read leniently: a hand-mangled file must not
    stop the regeneration that would repair it."""
    path = os.path.join(out_root, STATE_REL)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _recorded_mode(out_root):
    """The mode this folder already declares, or None."""
    recorded = _recorded_state(out_root).get("mode")
    return recorded if recorded in ("build", "support") else None


def _recorded_root_url(out_root):
    """The live ROOT this folder already declares, or None — so it is asked for ONCE per folder."""
    root = (_recorded_state(out_root).get("project") or {}).get("rootUrl")
    return _clean_root_url(root) if root else None


def _clean_root_url(url):
    """Just the origin: scheme://host[:port]. Everything after it is a page, not the installation.

    <p>People paste what is in the address bar, and what is in the address bar during a support session is
    a PAGE — often `…/auth;jsessionid=…`, because opening the bare root bounces to the login form and the
    session id is written into the path. Keeping any of that would build a project URL that is wrong in a
    way that still loads, which is the worst kind: the session drives the login page, sees no authoring
    affordances, and reports the project as broken.
    """
    if not url:
        return None
    url = url.strip().rstrip("/")
    m = re.match(r"^(https?://[^/?#]+)", url)
    return m.group(1) if m else None


def _project_url(root_url, realm, client):
    """Where this project is served: `<root>/<realm>/<client>`, or None if the root is unknown.

    <p>Realm and client are the URL, not decoration — the platform serves every project under
    `/<realm>/<client>/…`. So the only thing a session cannot work out for itself is the origin, which is
    why that is the one thing it asks for.
    """
    if not (root_url and realm and client):
        return None
    return "%s/%s/%s" % (_clean_root_url(root_url), realm, client)


def _token_coordinates(out_root):
    """The realm and client the MCP TOKEN names, decoded from its own claims. Never the token itself.

    <p>Claims are read, NOT verified — there is no secret here and none is needed, because this is used
    for ADDRESSING (which project am I connected to) and never for authorization, which the platform does
    on its side against the signature. Decoding is what lets a session that was handed only a token still
    know where to test.

    <p>⛔ The value of reading them is the MISMATCH. The folder's export says which project it mirrors and
    the token says which project the writes will land in; when those disagree, every "fix" is applied to a
    project nobody is looking at. Nothing else in the folder can notice that.
    """
    path = os.path.join(out_root, MCP_JSON_REL)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            servers = json.load(fh).get("mcpServers") or {}
    except Exception:
        return None
    import base64
    for server in servers.values():
        token = None
        for name, value in (server.get("headers") or {}).items():
            if name.lower() == "authorization" and isinstance(value, str):
                token = value.split(None, 1)[-1].strip()
        for i, a in enumerate(server.get("args") or []):
            if a == "--header" and i + 1 < len(server["args"]):
                nm, _, val = server["args"][i + 1].partition(":")
                if nm.strip().lower() == "authorization":
                    token = val.split(None, 1)[-1].strip()
        if not token or token.count(".") < 2:
            continue
        payload = token.split(".")[1]
        try:
            raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
            claims = json.loads(raw)
        except Exception:
            continue
        if claims.get("realm") or claims.get("client"):
            return {"realm": claims.get("realm"), "client": claims.get("client")}
    return None


# ---------------------------------------------------------------------------
# handoff mcp
# ---------------------------------------------------------------------------

MCP_JSON_REL = ".mcp.json"


def _read_mcp_json(out_root):
    """What `.mcp.json` in this folder declares, or None. The ONE source of truth for the connection."""
    path = os.path.join(out_root, MCP_JSON_REL)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            servers = json.load(fh).get("mcpServers") or {}
    except Exception:
        return None
    for key, server in servers.items():
        url = server.get("url")
        if not url:
            # the stdio form carries the url inside args
            for a in server.get("args") or []:
                if isinstance(a, str) and a.startswith("http"):
                    url = a
                    break
        if url:
            return {"server": key, "url": url}
    return None


BROWSER_SERVERS = {
    # stdio, no credential, no URL — a local driver, not a tenant. Kept as a NAMED set rather than
    # accepted as free text so that one folder's live test is reproducible in another: the server key
    # becomes part of every tool name the model sees (`mcp__chrome-devtools__*`) and therefore part of
    # every permission rule, exactly like the `dokie` key above.
    "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]},
    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]},
}
DEFAULT_BROWSER = "chrome-devtools"


def _which(binary):
    """Is this executable on PATH? Reported, never installed — see cmd_handoff_browser."""
    from shutil import which
    return which(binary)


def _merge_mcp_json(out_root, new_servers):
    """Merge server entries into this folder's `.mcp.json`, preserving every entry already there.

    <p>MERGE and not replace, and the difference is not cosmetic. Two commands write this file — the
    tenant connection and the browser driver — and they are run at different times by different
    sessions. A writer that rewrote the whole document would silently drop the other one's server, so
    re-pasting a token to fix an expiry would take the live test offline, and the failure would surface
    later as a missing tool rather than as anything about the file that was just written.
    """
    path = os.path.join(out_root, MCP_JSON_REL)
    existing = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                existing = json.load(fh).get("mcpServers") or {}
        except Exception:
            # Unreadable is not empty: overwriting it would destroy a connection we cannot see.
            raise core.ToolError("%s exists but is not readable JSON. Fix or delete it before writing —"
                                 " overwriting it would drop a connection this command cannot see."
                                 % MCP_JSON_REL)
    merged = dict(existing)
    merged.update(new_servers)
    _append_gitignore(out_root)
    core.atomic_write(path, json.dumps({"mcpServers": merged}, indent=2, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path, existing, merged


def _normalise_server(server):
    """One canonical shape out of whatever the author pasted: HTTP transport, url, headers.

    <p>The platform's token panel offers two blocks. The stdio one runs `npx -y mcp-remote <url>` as a
    local bridge, and it is the wrong one here for three separate reasons: Claude Code speaks HTTP to an
    MCP server natively, so the bridge is a subprocess that buys nothing; `mcp-remote` REFUSES a plain-HTTP
    url unless the host is literally `localhost` — it matches the string, not the resolved address, so
    a plain-http host named anything but `localhost`
    is rejected even when it resolves to 127.0.0.1 — and the failure surfaces as
    `Connection closed`, naming neither the url nor the reason; and npx pulls a package from the network
    on every start. So a pasted stdio block is UNWRAPPED into the http form rather than stored as given,
    and the caller is told it happened.
    """
    if server.get("type") in ("http", "streamable-http", "sse") or server.get("url"):
        out = {"type": server.get("type") or "http", "url": server["url"]}
        if server.get("headers"):
            out["headers"] = server["headers"]
        return out, False
    args = server.get("args") or []
    url = next((a for a in args if isinstance(a, str) and a.startswith("http")), None)
    if not url:
        raise core.ToolError("this MCP entry names no URL — paste the block the platform's "
                             "Settings -> Developer -> MCP tokens panel gives you")
    headers = {}
    for i, a in enumerate(args):
        if a == "--header" and i + 1 < len(args) and ":" in args[i + 1]:
            name, _, value = args[i + 1].partition(":")
            headers[name.strip()] = value.strip()
    out = {"type": "http", "url": url}
    if headers:
        out["headers"] = headers
    return out, True


def cmd_handoff_mcp(args):
    """Write this folder's `.mcp.json` from a configuration pasted on STDIN.

    <p>Why the folder and not the client's own store. The point is that ONE folder is ONE project: a
    support engineer keeps several open, and each must talk to its own tenant with its own credential.
    `.mcp.json` is the mechanism Claude Code already has for exactly that — it is read only for the
    directory it sits in, verified: a server declared here is invisible from any other folder.
    ⛔ The consequence has to be said out loud rather than discovered: the credential is now IN the folder.
    Handing the folder to someone else hands them the token. Give them a folder without it and let them
    paste their own, or use the client's own per-project store instead.

    <p>Read from STDIN, never from an argument: `ps` shows an argument to every other user on the machine
    and the shell records it in history. Nothing here prints the credential back.
    """
    workdir = os.path.realpath(args.project or ".")
    if not os.path.isfile(os.path.join(workdir, core.F_TENANT)):
        raise core.ToolError("--project must be the UNPACKED export dir (the one holding %s): %s"
                             % (core.F_TENANT, workdir))
    out_root = os.path.realpath(args.out) if getattr(args, "out", None) else os.path.dirname(workdir)
    if not os.path.isdir(out_root):
        raise core.ToolError("--out is not a directory: %s" % out_root)
    if out_root == workdir or os.path.commonpath([out_root, workdir]) == workdir:
        raise core.ToolError("--out must not be the export dir or inside it (%s): `pack` walks that "
                             "directory, so the credential would ship inside the .mrjun." % workdir)

    raw = sys.stdin.read().strip()
    if not raw:
        raise core.ToolError("no configuration on stdin. Pipe in the JSON block from the platform's "
                             "Settings -> Developer -> MCP tokens panel.")
    try:
        parsed = json.loads(raw)
    except ValueError as e:
        raise core.ToolError("that is not valid JSON (%s). Paste the whole block, braces included." % e)

    servers = parsed.get("mcpServers") if isinstance(parsed, dict) else None
    if not servers:
        # a bare single-server object is the other thing people paste
        servers = {MCP_SERVER_KEY: parsed} if isinstance(parsed, dict) else None
    if not servers:
        raise core.ToolError("no `mcpServers` in that JSON — paste the block the panel gives you")

    out, unwrapped = {}, False
    for key, server in servers.items():
        normalised, did = _normalise_server(server)
        out[key] = normalised
        unwrapped = unwrapped or did

    path, existing, merged = _merge_mcp_json(out_root, out)

    core.out("wrote %s (mode 600, git-ignored)" % MCP_JSON_REL)
    for key, server in out.items():
        core.out("  server  %s -> %s" % (key, server["url"]))
    kept = [k for k in existing if k not in out]
    if kept:
        core.out("  kept    %s (already configured here)" % ", ".join(sorted(kept)))
    if unwrapped:
        core.out("  NOTE: the pasted block ran `npx mcp-remote`; rewritten to the native HTTP transport."
                 "\n        Claude Code speaks HTTP to an MCP server itself, and mcp-remote refuses a"
                 "\n        plain-http host that is not literally `localhost`.")
    core.out("")
    core.out("⚠️  RESTART Claude Code ONCE, in this folder, and approve the server when asked.")
    core.out("    MCP servers connect at session start, so the session that wrote this file cannot use it.")
    core.out("    Every session after that is connected and must NOT ask for the configuration again.")
    return 0


def cmd_handoff_browser(args):
    """Add a BROWSER MCP server to this folder's `.mcp.json`, so the session can drive the live project.

    <p>Why this is a separate command from `handoff mcp`. They carry different things and fail
    differently. `handoff mcp` moves a CREDENTIAL and must never touch anything but STDIN; this one adds
    a local driver with no secret in it, so it takes a plain flag, is safe to re-run, and is safe to
    print in full. Merging them behind one flag would mean the credential path grows an argument, which
    is the one thing that path may not have.

    <p>Named servers, not free text: the key becomes part of every tool name the model sees
    (`mcp__chrome-devtools__*`) and therefore part of every permission rule the user writes. A key
    chosen per folder makes every rule and every habit unshareable.

    <p>⛔ It does NOT install anything. Detecting a missing `npx` and installing it are different acts:
    the first is a fact about this machine, the second is a change to it, and a toolkit that silently
    installed software would be doing so under whatever privileges the session happens to hold. So it
    REPORTS what is missing and the exact line that fixes it, and leaves running that line to the
    session — which is answerable to the person watching it.
    """
    workdir = os.path.realpath(args.project or ".")
    if not os.path.isfile(os.path.join(workdir, core.F_TENANT)):
        raise core.ToolError("--project must be the UNPACKED export dir (the one holding %s): %s"
                             % (core.F_TENANT, workdir))
    out_root = os.path.realpath(args.out) if getattr(args, "out", None) else os.path.dirname(workdir)
    if not os.path.isdir(out_root):
        raise core.ToolError("--out is not a directory: %s" % out_root)
    if out_root == workdir or os.path.commonpath([out_root, workdir]) == workdir:
        raise core.ToolError("--out must not be the export dir or inside it (%s): `pack` walks that "
                             "directory, so the file would ship inside the .mrjun." % workdir)

    name = getattr(args, "server", None) or DEFAULT_BROWSER
    if name not in BROWSER_SERVERS:
        raise core.ToolError("unknown browser server %r — choose one of: %s"
                             % (name, ", ".join(sorted(BROWSER_SERVERS))))

    already = _read_mcp_json(out_root)
    path, existing, merged = _merge_mcp_json(out_root, {name: dict(BROWSER_SERVERS[name])})

    if name in existing:
        core.out("%s already declared %s — rewritten to the canonical entry" % (MCP_JSON_REL, name))
    else:
        core.out("added %s to %s (mode 600, git-ignored)" % (name, MCP_JSON_REL))
    core.out("  %s -> %s %s" % (name, BROWSER_SERVERS[name]["command"],
                                " ".join(BROWSER_SERVERS[name]["args"])))
    if not already:
        core.out("  NOTE: no tenant connection in this file yet. The browser drives the project through"
                 "\n        its UI, but reading and writing OBJECTS needs `handoff mcp` as well.")

    # WHERE to test. Assembled, not guessed: the coordinates come from the token when there is one
    # (it is what the writes travel on) and the origin from --base-url or what this folder already
    # recorded. Asked for once per folder and never again.
    state = _recorded_state(out_root)
    proj = state.get("project") or {}
    coords = _token_coordinates(out_root) or {}
    realm = coords.get("realm") or proj.get("realm")
    client = coords.get("client") or proj.get("client")
    root = _clean_root_url(getattr(args, "base_url", None)) or _recorded_root_url(out_root)
    live = _project_url(root, realm, client)

    if coords and proj.get("realm") and (coords.get("realm") != proj.get("realm")
                                         or coords.get("client") != proj.get("client")):
        core.out("")
        core.out("⛔ MISMATCH — this folder mirrors %s/%s but the MCP token names %s/%s."
                 % (proj.get("realm"), proj.get("client"), coords.get("realm"), coords.get("client")))
        core.out("   Every live write goes where the TOKEN says. Stop and confirm which project this is")
        core.out("   before driving anything: a fix verified here would be applied over there.")

    core.out("")
    if live:
        core.out("WHERE TO TEST: %s" % live)
        core.out("  ⛔ Open THAT, not the bare root — the root bounces to the login form and leaves you")
        core.out("     on `…/auth;jsessionid=…`, which is not this project and renders none of it.")
        if getattr(args, "base_url", None):
            core.out("  (recorded — re-run `handoff emit` to write it into .dokie/project.json)")
    else:
        core.out("WHERE TO TEST: UNKNOWN — ask the user ONCE, then record it so nobody asks again:")
        core.out("      \"what is the project's URL? something like http://<host>:<port>/%s/%s\""
                 % (realm or "<realm>", client or "<client>"))
        core.out("  then: mrjun.py handoff emit --project <workdir> --base-url http://<host>:<port>")
        if not (realm and client):
            core.out("  (realm/client are unknown too — they come from the MCP token or the export)")

    missing = [b for b in ("node", "npx") if not _which(b)]
    if missing:
        core.out("")
        core.out("⛔ MISSING ON THIS MACHINE: %s" % ", ".join(missing))
        core.out("   The server is declared but will fail to start. Install Node (which brings npx):")
        core.out("       brew install node          # macOS")
        core.out("   then re-run this command to confirm.")
    core.out("")
    core.out("⚠️  RESTART Claude Code ONCE, in this folder, and approve the server when asked.")
    core.out("    MCP servers connect at session start, so the session that wrote this file cannot use it.")
    return 0


def cmd_handoff_emit(args):
    workdir = os.path.realpath(args.project or ".")
    if not os.path.isfile(os.path.join(workdir, core.F_TENANT)):
        raise core.ToolError("--project must be the UNPACKED export dir (the one holding %s), not the "
                             "project folder around it: %s" % (core.F_TENANT, workdir))
    out_root = os.path.realpath(args.out) if getattr(args, "out", None) else os.path.dirname(workdir)
    if not os.path.isdir(out_root):
        raise core.ToolError("--out is not a directory: %s" % out_root)
    # ⛔ Never emit INTO the export. `pack` walks the export dir, so a handoff written there would be
    # shipped inside the customer's .mrjun — the router, the machine state and whatever else the
    # folder accumulates. The same reason case notes live in a SIBLING folder.
    if out_root == workdir or os.path.commonpath([out_root, workdir]) == workdir:
        raise core.ToolError(
            "--out must not be the export dir or inside it (%s): `pack` walks that directory, so the "
            "handoff would ship inside the .mrjun. Use the project folder "
            "around it, which is the default." % workdir)

    # The mode is a property of the FOLDER, not of this invocation: a re-run that forgot --mode must not
    # flip a delivered support folder back to build (or the reverse) without anyone asking for it.
    mode = getattr(args, "mode", None)
    if not mode:
        mode = _recorded_mode(out_root) or "support"
    args.mode = mode

    p = core.Project(workdir)
    realm, client = p.realm_client()
    lib_root, delivered = _library_root(out_root)
    parent = os.path.dirname(workdir)
    plan_path = os.path.join(parent, "build-plan", "plan.json")
    case_dir = case_cmds._case_dir(args)
    packed = os.path.join(parent, os.path.basename(workdir) + ".mrjun")
    if not os.path.isfile(packed):
        cands = sorted(n for n in os.listdir(parent) if n.endswith(".mrjun"))
        packed = os.path.join(parent, cands[0]) if cands else None

    facts = {
        "mode": getattr(args, "mode", None) or "support",
        "name": p.tenant.get("name") or os.path.basename(out_root),
        "alias": p.tenant.get("alias"),
        "realm": getattr(args, "realm", None) or realm,
        "client": getattr(args, "client", None) or client,
        "locales": p.locales(),
        "default_locale": p.default_locale(),
        "inventory": _inventory(workdir),
        "plan": _plan_facts(plan_path),
        "cases": _case_index(case_dir),
        "workdir_rel": _rel(workdir, out_root),
        "lib_rel": _rel(lib_root, out_root) if lib_root else None,
        # The absolute path of the DELIVERED library, so the routing table is read from the copy the
        # reader will actually have rather than from the toolkit that happens to be running.
        "lib_abs": lib_root if delivered else None,
        "mrjun_rel": _rel(os.path.join(lib_root, "tools", "mrjun.py"), out_root) if lib_root else None,
        "plan_rel": _rel(plan_path, out_root) if os.path.isfile(plan_path) else None,
        # Always the DERIVED location, even when the folder does not exist yet: it is where notes
        # belong, and `case init` creates exactly this path. `cases` (empty) says whether it is there.
        "case_rel": _rel(case_dir, out_root),
        "mrjun_file_rel": _rel(packed, out_root) if packed else None,
        "mcp": None,
        "root_url": None,
        "live_url": None,
        "token_realm": None,
        "token_client": None,
    }
    # The connection is whatever `.mcp.json` in this folder already says — one source of truth, written by
    # `handoff mcp`. Nothing is derived from a flag, so the machine state cannot disagree with the file the
    # client actually reads.
    facts["mcp"] = _read_mcp_json(out_root)
    # The coordinates the TOKEN names win over the ones the export carries, because the token is what the
    # writes actually travel on: a folder whose export says one project while its token says another would
    # otherwise report the export's name and apply every change to the other one.
    coords = _token_coordinates(out_root)
    if coords:
        facts["token_realm"] = coords.get("realm")
        facts["token_client"] = coords.get("client")
        facts["realm"] = coords.get("realm") or facts["realm"]
        facts["client"] = coords.get("client") or facts["client"]
    facts["root_url"] = (_clean_root_url(getattr(args, "base_url", None))
                         or _recorded_root_url(out_root))
    facts["live_url"] = _project_url(facts["root_url"], facts["realm"], facts["client"])

    core.out("handoff emit: %s (mode=%s, format=%s)" % (facts["name"], facts["mode"], args.format))
    core.out("  export     %s" % facts["workdir_rel"])
    core.out("  into       %s" % out_root)

    if args.format == "claude":
        _emit(os.path.join(out_root, "CLAUDE.md"), _claude_md(facts), out_root)
        _emit(os.path.join(out_root, ".claude", "skills", SKILL_NAME, "SKILL.md"),
              _skill_md(facts), out_root)
    else:
        _emit(os.path.join(out_root, MARKDOWN_REL), _markdown_doc(facts), out_root)
    _emit(os.path.join(out_root, STATE_REL), _state_json(facts), out_root)

    _append_gitignore(out_root)

    # ---- warnings: things this command deliberately does NOT fix for you ----
    ancestors = _ancestor_claude_mds(out_root)
    if ancestors and args.format == "claude":
        core.out("\nWARNING: Claude Code also loads these ancestor CLAUDE.md files and MERGES them with"
                 "\n         the one just written — read them before trusting the emitted rules:")
        for a in ancestors:
            core.out("           %s" % a)
    if lib_root and not delivered:
        core.out("\nWARNING: no builder library inside %s — the emitted doc links point at %s"
                 "\n         via a relative path and BREAK as soon as this folder is moved or zipped."
                 "\n         Copy the library to %s/builder and re-run."
                 % (out_root, lib_root, out_root))
    elif not lib_root:
        core.out("\nWARNING: no builder library found (%s) — the emitted files carry no doc routing "
                 "table." % LIB_MARKER)
    settings = os.path.join(out_root, ".claude", "settings.json")
    if os.path.isfile(settings):
        with open(settings, "r", encoding="utf-8") as fh:
            if '"hooks"' in fh.read():
                core.out("\nWARNING: %s declares hooks. This command never writes hooks on purpose: under"
                         "\n         `claude -p` the trust gate is bypassed and project hooks run with no"
                         "\n         prompt, and this folder gets handed between people. Review it."
                         % _rel(settings, out_root))
    return 0
