#!/usr/bin/env python3
"""Coverage map — which scenario of ../test-scenarios.md is covered by which test file.

Why the suite carries it: "every scenario is automated" is a promise nobody can check unless it is counted. This
script reads every scenario of the scenario file, finds the tests that cite it, and prints what would otherwise
live in someone's head: how many scenarios are covered, and WHICH are not.

⛔ It is a map of CITATIONS, not a proof of quality: a test can cite §6.3 and check one caption of it. An empty
cell is certainly a hole; a filled one is a reason to look at what is actually asserted there.

The scenario file's grammar (the build contract's step 7, "THE FORMAT"; doc 30 §6):

    ## 0. How to read this file                    chapter 0 — prose: provenance, inventories, traceability.
                                                  Chapter 0 and its sections are never scenarios.
    ## 7. <chapter title>                         a chapter; its scenarios are the ### sections numbered 7.x
    ### 7.2 · <scenario title>                    a scenario — tests cite it as §7.2
    ### 9.4 · Printed invoice matches the brand {manual: a person compares the PDF with the approved layout}
                                                  cannot be automated at ALL — the reason is required
    - **Covers:** plan:<id>, plan:<id> · PRD 4.2  inside a scenario: the plan rows it proves (read by
                                                  `mrjun.py autotest check`)

A chapter with no ### scenarios is itself one scenario. A `###` heading may carry a short prefix before the number
(`### S-6.1`), which is ignored. Any OTHER heading that carries a section number (`## 1 · …`, `### Scenario 4.2`,
`#### 4.6`) is malformed and reported — a scenario that does not parse would otherwise vanish from the count.

Tests cite a scenario as `§N.M` in a DOCSTRING (the test's, its class's or its module's); citations anywhere else
do not count. `§` is reserved for scenario numbers: cite a PRD section as "PRD 4.2" and a library doc as "doc 30
§5" — a `§` right after "PRD", "doc NN" or a closing bracket is not read as a scenario.

    python3 tools/coverage_map.py [--strict] [--scenarios PATH] [--tests DIR]

--strict exits 1 on any hole or malformed entry (see `failures`).
"""
from __future__ import annotations

import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCENARIOS = os.path.join(os.path.dirname(ROOT), "test-scenarios.md")
DEFAULT_TESTS = os.path.join(ROOT, "tests")

CHAPTER = re.compile(r"^##\s+(\d+)\.\s+(.*?)\s*$")
SCENARIO = re.compile(r"^###\s+(?:[^\s\d§]{1,8}[\u2011\u2010-])?(\d+(?:\.\d+)+)(?![\d.])\s*[·.:\u2013\u2014-]?\s*(.*?)\s*$")
HEADING = re.compile(r"^(#{2,6})\s+(.*?)\s*$")
# a heading that was MEANT as a chapter or a scenario: it opens with a number (after an optional § or a word like
# "Scenario"); at level 2 any number, deeper only a dotted one, so `#### Step 1` stays an ordinary sub-heading
LOOKS_NUMBERED = re.compile(r"^(?:(?:scenario|section|chapter|case|сценарий|раздел|глава)\s*)?§?\s?(\d+(?:\.\d+)*)(?![\w])",
                            re.I)
TAG = re.compile(r"\{\s*(prose|manual)\s*(?::\s*([^}]*))?\}\s*$", re.I)
REF = re.compile(r"§\s?(\d+(?:\.\d+)*)")
NOT_A_SCENARIO_REF = re.compile(r"(?:\bPRD|\bdocs?\s*\d+[a-z]?|[\])])\s*$", re.I)
COVERS = re.compile(r"^\s*(?:[-*]\s*)?\**\s*(?:Role\b[^\n]*?·\s*\**\s*)?Covers\b\s*\**\s*:?", re.I)
PLAN_ID = re.compile(r"plan:([A-Za-z0-9_](?:[A-Za-z0-9_.:\-]*[A-Za-z0-9_])?)")
FENCE = re.compile(r"^\s*(```|~~~)")


def parse(text: str) -> dict:
    """Chapters, scenarios (with the plan ids of their Covers line) and malformed headings, in file order."""
    entries, malformed, fenced, current, chapter, in_covers = [], [], False, None, None, False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        m, level = CHAPTER.match(line), "chapter"
        if not m:
            m, level = SCENARIO.match(line), "scenario"
        if m:
            num, title = m.group(1), m.group(2)
            tag, reason = None, ""
            t = TAG.search(title)
            if t:
                tag, reason = t.group(1).lower(), (t.group(2) or "").strip()
                title = title[:t.start()].rstrip()
            if level == "chapter":
                chapter = num
            current = {"num": num, "title": title, "level": level, "tag": tag, "reason": reason, "line": no,
                       "chapter": num.split(".")[0], "under": chapter, "plans": []}
            entries.append(current)
            in_covers = False
            continue
        h = HEADING.match(line)
        if h:
            current, in_covers = None, False        # any other heading ends the scenario's block
            n = LOOKS_NUMBERED.match(h.group(2))
            if n and (len(h.group(1)) == 2 or "." in n.group(1)):
                malformed.append(f"line {no}: `{line.strip()[:70]}` — a chapter is `## N. <title>`, "
                                 "a scenario `### N.M · <title>`")
            continue
        if current is None:
            continue
        if COVERS.match(line):
            in_covers = True
            current["plans"].extend(PLAN_ID.findall(line.split("Covers", 1)[-1]))
        elif in_covers and line[:1].isspace() and line.strip() and not re.match(r"^\s*([-*+]|\d+[.)])\s", line):
            current["plans"].extend(PLAN_ID.findall(line))      # the Covers line wrapped onto the next one
        else:
            in_covers = False
    return {"entries": entries, "malformed": malformed}


def _docstrings(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for node in [tree] + [n for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
        doc = ast.get_docstring(node, clean=False)
        if doc:
            out.append(doc)
    return out


def refs(tests_dir: str) -> dict[str, set[str]]:
    """§ number -> the test files whose docstrings cite it."""
    found: dict[str, set[str]] = {}
    if not os.path.isdir(tests_dir):
        return found
    for dirpath, dirnames, filenames in os.walk(tests_dir):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".venv")]
        for name in sorted(filenames):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                source = fh.read()
            for doc in _docstrings(source):
                for m in REF.finditer(doc):
                    if NOT_A_SCENARIO_REF.search(doc[max(0, m.start() - 12):m.start()]):
                        continue
                    found.setdefault(m.group(1), set()).add(name)
    return found


def evaluate(parsed: dict, seen: dict[str, set[str]]) -> dict:
    """What is covered, what is a hole, and what is malformed."""
    entries = parsed["entries"]
    chapters = {e["num"]: e for e in entries if e["level"] == "chapter"}
    with_children = {e["chapter"] for e in entries if e["level"] == "scenario"}
    scenarios, holes, manual, prose, problems, numbers = [], [], [], [], [], {}
    for e in entries:
        if e["num"] in numbers:
            problems.append(f"two headings share the number §{e['num']} (lines {numbers[e['num']]} and {e['line']})")
        numbers.setdefault(e["num"], e["line"])
        is_prose = e["chapter"] == "0"
        if e["tag"] == "prose" and not is_prose:
            problems.append(f"§{e['num']} {e['title']} is tagged {{prose}} — only chapter 0 is prose; a section of "
                            "any other chapter is a scenario (or {manual: <reason>})")
        if e["level"] == "scenario" and e["chapter"] not in chapters:
            problems.append(f"§{e['num']} {e['title']} has no chapter `## {e['chapter']}. …`")
        elif e["level"] == "scenario" and e["under"] != e["chapter"]:
            problems.append(f"§{e['num']} {e['title']} sits under chapter {e['under'] or '(none)'} — a scenario's "
                            "number starts with its own chapter's")
        if e["level"] == "chapter" and e["num"] in with_children:
            continue                                    # a heading row; its scenarios are counted
        files = sorted(seen.get(e["num"], ()))
        row = dict(e, files=files)
        if is_prose:
            prose.append(row)
        elif e["tag"] == "manual":
            manual.append(row)
            if not e["reason"]:
                problems.append(f"§{e['num']} {e['title']} is {{manual}} without a reason")
        else:
            scenarios.append(row)
            if not files:
                holes.append(f"§{e['num']} {e['title']}")
    problems += [f"malformed heading, {m}" for m in parsed["malformed"]]
    unknown = sorted((n for n in seen if n not in numbers), key=lambda n: [int(x) for x in n.split(".")])
    return {"entries": entries, "scenarios": scenarios, "holes": holes, "manual": manual, "prose": prose,
            "problems": problems,
            "unknown_refs": [f"§{n} cited by {', '.join(sorted(seen[n]))}" for n in unknown]}


def covered_plan_ids(result: dict) -> set[str]:
    """The plan ids cited on the Covers line of a scenario (automated or manual) — chapter 0 does not count."""
    return {pid for row in result["scenarios"] + result["manual"] for pid in row["plans"]}


def failures(result: dict) -> list[str]:
    out = [f"no test cites {h}" for h in result["holes"]]
    out += result["problems"]
    out += [f"a test cites a scenario the file does not have: {u}" for u in result["unknown_refs"]]
    return out


def render(result: dict, color: bool = False) -> str:
    def c(code, s):
        return f"\033[{code}m{s}\033[0m" if color else s
    rows = {r["num"]: r for r in result["scenarios"] + result["manual"] + result["prose"]}
    lines = [c("1", "Scenario coverage map")]
    for e in result["entries"]:
        r = rows.get(e["num"])
        if r is None:
            lines.append(f"  {c('1', '§' + e['num'])} {e['title']}")
            continue
        indent = "    " if e["level"] == "scenario" else "  "
        if r in result["prose"]:
            lines.append(f"{indent}{c('90', '·')} §{r['num']:<6} {r['title']}  {c('90', 'chapter 0 — not a scenario')}")
        elif r["tag"] == "manual":
            lines.append(f"{indent}{c('36', 'M')} §{r['num']:<6} {r['title']}  "
                         f"{c('36', 'manual: ' + (r['reason'] or 'NO REASON GIVEN'))}")
        else:
            mark = c("32", "✓") if r["files"] else c("33", "—")
            short = ", ".join(f.replace("test_", "").replace(".py", "") for f in r["files"][:3])
            if len(r["files"]) > 3:
                short += f" (+{len(r['files']) - 3})"
            lines.append(f"{indent}{mark} §{r['num']:<6} {r['title']}  {short}")
    total = len(result["scenarios"])
    lines.append("")
    lines.append(f"  automated: {total - len(result['holes'])} of {total} scenarios"
                 f"  (+{len(result['manual'])} manual, +{len(result['prose'])} chapter-0 sections)")
    for title, items in (("NOT covered by any test", result["holes"]),
                         ("malformed or inconsistent", result["problems"]),
                         ("tests citing a scenario that does not exist", result["unknown_refs"])):
        if items:
            lines.append(f"  {title}:")
            lines += [f"    • {i}" for i in items]
    return "\n".join(lines)


def run(scenarios_path: str, tests_dir: str) -> dict:
    with open(scenarios_path, encoding="utf-8") as fh:
        parsed = parse(fh.read())
    return evaluate(parsed, refs(tests_dir))


def main(argv: list[str]) -> int:
    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default
    path = opt("--scenarios", DEFAULT_SCENARIOS)
    tests = opt("--tests", DEFAULT_TESTS)
    if not os.path.isfile(path):
        print(f"no scenario file at {path}")
        return 1
    result = run(path, tests)
    print("\n" + render(result, color=sys.stdout.isatty()))
    if not result["scenarios"] and not result["manual"]:
        print("  the scenario file has no numbered scenarios — see its grammar in this script's docstring")
        return 1 if "--strict" in argv else 0
    return 1 if ("--strict" in argv and failures(result)) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
