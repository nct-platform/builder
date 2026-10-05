"""autotest — the automated test suite that ships with every build (doc 30; the build contract's step 7a).

    mrjun.py autotest scaffold --project ./work [--out ./test] [--force-infra]
    mrjun.py autotest check    --project ./work [--tests ./test] [--scenarios ./test-scenarios.md]
                               [--plan ./build-plan/plan.json]
    mrjun.py autotest env      --project ./work [--tests ./test] [--base-url URL] [--set KEY=VALUE ...]

`scaffold` lays down the suite's proven harness from initialtemplates/autotest/ — the runner, the configuration
that is the ONLY reader of .env, the Wicket-aware page objects, the coverage map — so a build writes TESTS, not
another harness. It never overwrites what the builder writes for the project — tests/ (with tests/conftest.py, the
project's own fixtures and markers), pages/project_*.py and helpers/project_*.py (its own page objects and
helpers), helpers/locales.py, README.md, .env.example — or the owner's .env; the rest of the harness is replaced
only with --force-infra.

`check` is the suite's offline gate. It cannot run a test (there is no project to run against during a build), so
it proves what CAN be proven without one:
  * every scenario of test-scenarios.md is cited by at least one test (`§N.M` in a docstring), or is
    {manual: <reason>}; no test cites a scenario that does not exist; no two headings share a number; no heading
    meant as a chapter or a scenario is malformed; {prose} only in chapter 0;
  * every plan.json row that is not `deferred` (and not a `context`) is cited as `plan:<id>` on the Covers line of
    a scenario — chapter 0's traceability table does not count — and no `plan:<id>` names a row the plan lacks;
  * every Python file compiles; every import of the suite's own modules resolves (the module exists and defines
    the name); every fixture a test asks for is defined; every marker a test uses is registered (pytest.ini, or
    `config.addinivalue_line("markers", ...)` in a conftest.py) — the runner uses --strict-markers, so one
    unregistered marker fails the whole run;
  * hygiene: `.env` is git-ignored, `.env.example` declares every key helpers/env.py reads and carries no secret
    value, no credential literal in the code, and addresses come from CONFIG.url() / CONFIG.api_url(), never a
    literal host.
Exit non-zero on any error.

`env` says which keys of test/.env are set — never the value of a secret or an identity — and writes the ones that
are neither: `--base-url` (the origin, or the project's whole address) and `--set KEY=VALUE` for the run's knobs.
Credentials are refused: the owner writes them into the file, nobody types them into a command line.
"""
import ast
import importlib.util
import os
import re
import shutil
import stat
import sys

from . import core, handoff_cmds

LIB_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(LIB_ROOT, "initialtemplates", "autotest")

# Never overwritten by scaffold, not even with --force-infra: what the BUILDER writes or fills for this project
# (the tests and their conftest, its own page objects and helpers, the captions per locale, the README's notes,
# the keys it declares), and the owner's secrets.
NEVER_OVERWRITE_DIRS = ("tests",)
NEVER_OVERWRITE_FILES = (".env", ".env.example", "README.md", os.path.join("helpers", "locales.py"))
NEVER_OVERWRITE_PREFIXES = (os.path.join("pages", "project_"), os.path.join("helpers", "project_"))
SKIP_NAMES = {"__pycache__", ".DS_Store", ".venv", "test-results", ".pytest_cache"}

BUILTIN_MARKERS = {"parametrize", "skip", "skipif", "xfail", "usefixtures", "filterwarnings"}
BUILTIN_FIXTURES = {"request", "tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory", "monkeypatch", "capsys",
                    "capsysbinary", "capfd", "capfdbinary", "caplog", "recwarn", "pytestconfig", "record_property",
                    "record_testsuite_property", "record_xml_attribute", "cache", "doctest_namespace", "pytester",
                    "testdir"}
PLAN_KINDS_EXEMPT = {"context"}

# test/.env: the knobs of a run may be written by `env`; the rest belongs to the project's owner.
KNOB_KEYS = ("BASE_URL", "API_BASE_URL", "DEFAULT_LOCALE", "HEADLESS", "SLOW_MO_MS", "DEFAULT_TIMEOUT_MS",
             "GRID_TIMEOUT_MS", "KEEP_TEST_USERS")
REQUIRED_KEYS = ("BASE_URL", "AUTH_USER", "AUTH_PASSWORD")
# (pairs, not a dict literal: `"<NAME>_KEY": "<text>"` is exactly the shape the repo's leak scan reads as a secret)
OPTIONAL_NOTES = dict((("PGDSN", "optional — the database cross-checks skip without it"),
                       ("API_KEY", "optional — the public-API tests skip without it"),
                       ("API_BASE_URL", "optional — derived from BASE_URL when empty")))


def _is_secret_key(key):
    return key == "PGDSN" or bool(re.search(r"(PASSWORD|PASSWD|SECRET|TOKEN|_KEY)$", key))


def _is_identity_key(key):
    return key == "AUTH_USER"


def _default_folder(project):
    """The delivered project folder: the PARENT of the unpacked export (./work)."""
    return os.path.dirname(os.path.abspath(project))


def _load_coverage_map():
    """The template's own coverage map — the suite and the gate read the scenario file with ONE parser. Loaded
    without writing bytecode: the library is read-only to a build, and a __pycache__ in the template would be
    one more thing to keep out of every scaffolded suite."""
    path = os.path.join(TEMPLATE, "tools", "coverage_map.py")
    spec = importlib.util.spec_from_file_location("_autotest_coverage_map", path)
    mod = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def _walk_template():
    for dirpath, dirnames, filenames in os.walk(TEMPLATE):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        for name in filenames:
            if name in SKIP_NAMES or name.endswith(".pyc"):
                continue
            src = os.path.join(dirpath, name)
            yield src, os.path.relpath(src, TEMPLATE)


def _is_protected(rel):
    first = rel.split(os.sep, 1)[0]
    return first in NEVER_OVERWRITE_DIRS or rel in NEVER_OVERWRITE_FILES or rel.startswith(NEVER_OVERWRITE_PREFIXES)


def _set_locales(text, locales, default):
    ordered = [default] + [l for l in locales if l != default]
    inner = ", ".join('"%s"' % l for l in ordered) + ("," if len(ordered) == 1 else "")
    text = re.sub(r"^LOCALES = .*$", lambda _m: "LOCALES = (%s)" % inner, text, count=1, flags=re.M)
    return re.sub(r"^DEFAULT_LOCALE = .*$", lambda _m: 'DEFAULT_LOCALE = "%s"' % default, text, count=1,
                  flags=re.M)


def _inside(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _guard_out(out, project):
    """Refuse a suite folder that would put test code into the archive, scatter the harness over the project
    folder or the library, or mix it into an unrelated folder. Real paths: a symlink or `..` must not slip past."""
    real_out, real_export = os.path.realpath(out), os.path.realpath(project)
    default = os.path.join(_default_folder(project), "test")
    if _inside(real_out, real_export):
        raise core.ToolError("the suite must live BESIDE the export, never inside it — `pack` walks the export "
                             "directory, and test code must not ship in the archive (default: %s)" % default)
    if _inside(real_export, real_out):
        raise core.ToolError("--out %s contains the export itself — the suite gets a folder of its own beside the "
                             "export (default: %s)" % (out, default))
    if _inside(real_out, os.path.realpath(LIB_ROOT)):
        raise core.ToolError("--out %s is inside the builder library — the suite belongs to the project folder "
                             "(default: %s)" % (out, default))
    # a lone .env is the owner having filled it in first — that folder is the suite's, not somebody else's
    if os.path.isdir(real_out) and [n for n in os.listdir(real_out) if n not in SKIP_NAMES and n != ".env"] and not any(
            os.path.exists(os.path.join(real_out, marker)) for marker in ("conftest.py", "pytest.ini", "start.sh")):
        raise core.ToolError("--out %s is a folder that holds files but no suite — pick an empty folder (default: "
                             "%s)" % (out, default))


def cmd_autotest_scaffold(args):
    if not os.path.isdir(TEMPLATE):
        raise core.ToolError("the library has no initialtemplates/autotest/ — refresh ./builder")
    p = core.Project(args.project)
    out = os.path.abspath(args.out or os.path.join(_default_folder(args.project), "test"))
    _guard_out(out, args.project)
    locales, default = p.locales(), p.default_locale()
    written, kept, replaced = [], [], []
    for src, rel in _walk_template():
        dst = os.path.join(out, rel)
        exists = os.path.exists(dst)
        if exists and (_is_protected(rel) or not args.force_infra):
            kept.append(rel)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        if rel == os.path.join("helpers", "locales.py"):
            text = _set_locales(text, locales, default)
        if rel == ".env.example":
            text = re.sub(r"^DEFAULT_LOCALE=.*$", "DEFAULT_LOCALE=%s" % default, text, count=1, flags=re.M)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(text)
        shutil.copymode(src, dst)
        (replaced if exists else written).append(rel)
    for rel in ("start.sh", os.path.join("tools", "coverage_map.py"), os.path.join("tools", "import_project.py")):
        path = os.path.join(out, rel)
        if os.path.exists(path):
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = os.path.join(out, ".env")
    if not os.path.exists(env):
        shutil.copyfile(os.path.join(out, ".env.example"), env)
        written.append(".env")
    os.chmod(env, 0o600)

    core.out("autotest scaffold -> %s" % out)
    core.out("  locales: %s (default %s)" % (", ".join(locales), default))
    core.out("  written: %d file(s)%s" % (len(written), "" if len(written) > 12 else
                                          (": " + ", ".join(sorted(written)) if written else "")))
    if replaced:
        core.out("  replaced (--force-infra): %s" % ", ".join(sorted(replaced)))
    if kept:
        core.out("  kept as they are: %d file(s) — tests/, pages/project_*, helpers/project_*, .env, .env.example, "
                 "README.md and helpers/locales.py are never overwritten; the rest of the harness only with "
                 "--force-infra" % len(kept))
    core.out("next: write one test file per scenario chapter into %s, citing each scenario as §N.M in the test's "
             "docstring; fill helpers/locales.py from the export; then `mrjun.py autotest check`. "
             ".env is mode 600 and git-ignored — `mrjun.py autotest env --base-url <origin>` may write BASE_URL; "
             "AUTH_USER, AUTH_PASSWORD and every other credential are filled in by the project's owner, in the "
             "file, never by you and never in a chat." % os.path.join(out, "tests"))


# ---------------------------------------------------------------------------------------------------- check

_MARK = re.compile(r"pytest\.mark\.([A-Za-z_][A-Za-z0-9_]*)")
_INI_MARKER = re.compile(r"""addinivalue_line\(\s*["']markers["']\s*,\s*[rbuf]{0,2}["']\s*([A-Za-z_][A-Za-z0-9_]*)""")
_GETENV = re.compile(r"""(?:os\.getenv|os\.environ\.get|_identity|_knob|_int)\(\s*["']([A-Z][A-Z0-9_]*)["']""")
_ENV_READ = re.compile(r"\bos\.(?:getenv|environ)\b")
_URL = re.compile(r"""["']https?://(?!localhost\b|127\.0\.0\.1\b|example\.(?:com|org|invalid)\b)[^"'\s]+["']""")
_URL_CALL = re.compile(r"""\b(?:goto|get|post|put|patch|delete|fetch|request|navigate|new_page|urlopen)\(\s*[rbuf]{0,2}$""")
_SECRET_NAME = r"[A-Za-z0-9_]*(?:password|passwd|pwd|secret|token|api_?key|bearer)[A-Za-z0-9_]*"
_SECRET_ASSIGN = re.compile(r"""(?i)(?:\b(%s)\s*[:=]\s*|["'](%s)["']\s*:\s*)[rbuf]{0,2}["']([^"'\n]{4,})["']"""
                            % (_SECRET_NAME, _SECRET_NAME))
_SECRET_FILL = re.compile(r"""(?i)\.(?:fill|type|press_sequentially)\(\s*[rbuf]{0,2}["'][^"'\n]*(?:password|passwd|pwd|secret|token)[^"'\n]*["']\s*,\s*[rbuf]{0,2}["']([^"'\n]+)["']""")
_LOGIN_LITERAL = re.compile(r"""\.login\(\s*[rbuf]{0,2}["'][^"'\n]+["']\s*,\s*[rbuf]{0,2}["'][^"'\n]+["']""")
_BEARER = re.compile(r"""["']Bearer\s+[A-Za-z0-9._~+/=-]{8,}["']""")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")
_NOT_A_SECRET_VALUE = {"password", "passwd", "text", "hidden", "current-password", "new-password", "token",
                       "secret", "none", "null", "changeme", "redacted"}


def _py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _registered_markers(tests_root, sources):
    path = os.path.join(tests_root, "pytest.ini")
    if not os.path.isfile(path):
        return None
    names, in_markers = set(), False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if re.match(r"^\s*markers\s*=", line):
                in_markers = True
                rest = line.split("=", 1)[1].strip()
                if rest:
                    names.add(rest.split(":")[0].split("(")[0].strip())
                continue
            if in_markers:
                if line.strip() and not line[0].isspace():
                    in_markers = False
                    continue
                if line.strip():
                    names.add(line.strip().split(":")[0].split("(")[0].strip())
    for path, src in sources.items():                 # a project's own markers, from its conftest.py
        if os.path.basename(path) == "conftest.py":
            names.update(_INI_MARKER.findall(src))
    return names


def _env_file(path):
    """KEY -> value of a dotenv file; a commented-out key maps to None."""
    keys = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^\s*(#)?\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=(.*)$", line.rstrip("\n"))
                if not m:
                    continue
                if m.group(1):
                    keys.setdefault(m.group(2), None)
                    continue
                value = m.group(3).strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                else:
                    value = re.sub(r"\s+#.*$", "", value)
                keys[m.group(2)] = value
    return keys


def _strip_comments(src):
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))


def _looks_like_secret(value):
    v = value.strip()
    if v.lower() in _NOT_A_SECRET_VALUE or re.fullmatch(r"[A-Z][A-Z0-9_]*", v):
        return False                                   # an input type, a placeholder, an env key's NAME
    if re.search(r"[\s<>{}$]", v) or "[" in v or v.startswith(("#", ".", "input", "//", "http")):
        return False                                   # a sentence, a template, a CSS selector, an address
    return True


def _credential_findings(rel, code):
    found = []
    for m in _SECRET_ASSIGN.finditer(code):
        if _looks_like_secret(m.group(3)):
            found.append("%s holds what looks like a credential literal (%s=…)" % (rel, m.group(1) or m.group(2)))
    for m in _SECRET_FILL.finditer(code):
        if _looks_like_secret(m.group(1)):
            found.append("%s types a literal into a password field" % rel)
    if _LOGIN_LITERAL.search(code):
        found.append("%s signs in with literal credentials (.login(\"…\", \"…\")) — the author signs in with "
                     "LoginPage.login(), everyone else is a test user the suite creates (as_user / helpers/accounts.py)"
                     % rel)
    if _BEARER.search(code) or _JWT.search(code):
        found.append("%s carries a literal token" % rel)
    return [f + " — credentials live in test/.env only" for f in found]


# --- the suite's own imports and fixtures, checked without running anything ---------------------------------------

def _local_roots(tests_root):
    names = set()
    for name in os.listdir(tests_root):
        if name in SKIP_NAMES or name.startswith("."):
            continue
        full = os.path.join(tests_root, name)
        if os.path.isdir(full):
            names.add(name)
        elif name.endswith(".py"):
            names.add(name[:-3])
    return names


def _module_file(tests_root, dotted):
    base = os.path.join(tests_root, *dotted.split("."))
    for cand in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.isfile(cand):
            return cand
    return base if os.path.isdir(base) else None


def _target_names(node):
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        out = set()
        for elt in node.elts:
            out |= _target_names(elt)
        return out
    return set()


def _defined_names(tree):
    """Names a module defines at its top level (None when a star import makes that unknowable)."""
    names = set()
    blocks = list(tree.body)
    while blocks:
        node = blocks.pop(0)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                names |= _target_names(t)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            names |= _target_names(node.target)
        elif isinstance(node, ast.Import):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if any(a.name == "*" for a in node.names):
                return None
            names |= {a.asname or a.name for a in node.names}
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            for field in ("body", "orelse", "finalbody", "handlers"):
                for sub in getattr(node, field, []) or []:
                    blocks.extend(sub.body if isinstance(sub, ast.ExceptHandler) else [sub])
    return names


def _import_findings(tests_root, trees):
    local, cache, errors = _local_roots(tests_root), {}, []

    def names_of(path):
        if path not in cache:
            if os.path.isdir(path):
                cache[path] = None                      # a namespace package: anything below it is a module
            else:
                tree = trees.get(path)
                names = _defined_names(tree) if tree is not None else None
                if names is not None and os.path.basename(path) == "__init__.py":
                    names |= {n[:-3] if n.endswith(".py") else n for n in os.listdir(os.path.dirname(path))}
                cache[path] = names
        return cache[path]

    for path, tree in trees.items():
        rel, aliases = os.path.relpath(path, tests_root), {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] not in local:
                        continue
                    target = _module_file(tests_root, a.name)
                    if target is None:
                        errors.append("%s:%d imports %s, which the suite does not have" % (rel, node.lineno, a.name))
                    elif a.asname:
                        aliases[a.asname] = target
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                if node.module.split(".")[0] not in local:
                    continue
                target = _module_file(tests_root, node.module)
                if target is None:
                    errors.append("%s:%d imports from %s, which the suite does not have" % (rel, node.lineno,
                                                                                           node.module))
                    continue
                for a in node.names:
                    if a.name == "*":
                        continue
                    sub = _module_file(tests_root, node.module + "." + a.name)
                    if sub is not None:
                        aliases[a.asname or a.name] = sub
                        continue
                    have = names_of(target)
                    if have is not None and a.name not in have:
                        errors.append("%s:%d imports %s from %s, which does not define it"
                                      % (rel, node.lineno, a.name, node.module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
                have = names_of(aliases[node.value.id])
                if have is not None and node.attr not in have:
                    errors.append("%s:%d uses %s.%s, which %s does not define" % (
                        rel, node.lineno, node.value.id, node.attr,
                        os.path.relpath(aliases[node.value.id], tests_root)))
    return sorted(set(errors))


def _is_fixture(dec):
    target = dec.func if isinstance(dec, ast.Call) else dec
    return (isinstance(target, ast.Attribute) and target.attr == "fixture") or (
        isinstance(target, ast.Name) and target.id == "fixture")


def _fixtures_in(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if _is_fixture(dec):
                    alias = None
                    if isinstance(dec, ast.Call):
                        for kw in dec.keywords:
                            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                alias = kw.value.value
                    names.add(alias or node.name)
    return names


def _parametrized(func):
    names = set()
    for dec in func.decorator_list:
        if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "parametrize"
                and dec.args):
            first = dec.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names |= {n.strip() for n in first.value.split(",") if n.strip()}
            elif isinstance(first, (ast.List, ast.Tuple)):
                names |= {e.value for e in first.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return names


def _requested(func):
    a = func.args
    positional = a.posonlyargs + a.args
    without_default = positional[:len(positional) - len(a.defaults)] if a.defaults else positional
    return [x.arg for x in without_default if x.arg not in ("self", "cls")]


def _fixture_findings(tests_root, trees):
    shared = set(BUILTIN_FIXTURES)
    for path, tree in trees.items():
        if os.path.basename(path) == "conftest.py":
            shared |= _fixtures_in(tree)
    errors = []
    for path, tree in trees.items():
        name = os.path.basename(path)
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        known, rel = shared | _fixtures_in(tree), os.path.relpath(path, tests_root)
        funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.startswith("Test")):
            funcs += [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for func in funcs:
            if not (func.name.startswith("test") or any(_is_fixture(d) for d in func.decorator_list)):
                continue
            for arg in _requested(func):
                if arg not in known and arg not in _parametrized(func):
                    errors.append("%s:%d %s asks for the fixture %r, which no conftest.py and not the file itself "
                                  "defines" % (rel, func.lineno, func.name, arg))
    return errors


def _norm_plan_id(pid):
    return re.sub(r"\s+", "-", str(pid).strip()).lower()


def cmd_autotest_check(args):
    folder = _default_folder(args.project)
    tests_root = os.path.abspath(args.tests or os.path.join(folder, "test"))
    scenarios = os.path.abspath(args.scenarios or os.path.join(folder, "test-scenarios.md"))
    plan_path = args.plan or os.path.join(folder, "build-plan", "plan.json")
    errors, warnings = [], []

    if not os.path.isdir(tests_root):
        raise core.ToolError("no suite at %s — run `mrjun.py autotest scaffold --project %s` first"
                             % (tests_root, args.project))
    if not os.path.isfile(scenarios):
        raise core.ToolError("no scenario file at %s — the build contract's step 7 writes it first" % scenarios)

    # 1. scenarios <-> tests
    cmap = _load_coverage_map()
    result = cmap.run(scenarios, os.path.join(tests_root, "tests"))
    if not result["scenarios"] and not result["manual"]:
        errors.append("test-scenarios.md has no numbered scenario: chapters are `## N. <title>`, scenarios "
                      "`### N.M · <title>` (see tools/coverage_map.py in the suite)")
    errors += cmap.failures(result)
    suite_map = os.path.join(tests_root, "tools", "coverage_map.py")
    if not os.path.isfile(suite_map):
        errors.append("the suite has no tools/coverage_map.py — start.sh prints the map after every run; "
                      "re-run `autotest scaffold`")
    elif open(suite_map, encoding="utf-8").read() != open(os.path.join(TEMPLATE, "tools", "coverage_map.py"),
                                                          encoding="utf-8").read():
        warnings.append("tools/coverage_map.py differs from the library's — `autotest scaffold --force-infra` "
                        "refreshes the harness (tests/ and .env are never touched)")

    # 2. plan rows <-> the Covers lines of scenarios
    if os.path.isfile(plan_path):
        with open(scenarios, encoding="utf-8") as fh:
            anywhere = {_norm_plan_id(x) for x in cmap.PLAN_ID.findall(fh.read())}
        covered = {_norm_plan_id(x) for x in cmap.covered_plan_ids(result)}
        plan = core.load_json_file(plan_path).data
        items = plan.get("items", []) if isinstance(plan, dict) else plan
        known, missing = set(), []
        for it in items or []:
            if not isinstance(it, dict) or not it.get("id"):
                continue
            pid = _norm_plan_id(it["id"])
            known.add(pid)
            if (it.get("status") or "").lower() == "deferred" or it.get("kind") in PLAN_KINDS_EXEMPT:
                continue
            if pid not in covered:
                where = " (cited in the file, but not on any scenario's Covers line)" if pid in anywhere else ""
                missing.append("%s (%s)%s" % (it["id"], it.get("kind", "?"), where))
        if missing:
            errors.append("%d plan row(s) no scenario covers — cite each as `plan:<id>` on the Covers line of the "
                          "scenario that proves it (chapter 0's traceability table does not count): %s"
                          % (len(missing), ", ".join(missing[:40]) + (" …" if len(missing) > 40 else "")))
        unknown = sorted(anywhere - known)
        if unknown:
            errors.append("test-scenarios.md cites plan id(s) that plan.json does not have: %s — a typo, or a row "
                          "the plan lost" % ", ".join("plan:" + u for u in unknown[:40]))
    else:
        warnings.append("no plan.json at %s — the plan-to-scenario check was skipped (pass --plan)" % plan_path)

    # 3. the code: it compiles, its own imports and fixtures resolve, its markers exist, it holds no secret
    sources, trees = {}, {}
    for path in _py_files(tests_root):
        with open(path, encoding="utf-8") as fh:
            sources[path] = fh.read()
    markers = _registered_markers(tests_root, sources)
    if markers is None:
        errors.append("no pytest.ini in the suite — the markers and the test path live there")
    for path, src in sorted(sources.items()):
        rel = os.path.relpath(path, tests_root)
        try:
            trees[path] = ast.parse(src, path)
            compile(src, path, "exec")
        except SyntaxError as exc:
            errors.append("%s does not compile: line %s: %s" % (rel, exc.lineno, exc.msg))
            trees.pop(path, None)
            continue
        if markers is not None:
            for name in sorted(set(_MARK.findall(src)) - markers - BUILTIN_MARKERS):
                errors.append("%s uses @pytest.mark.%s, which neither pytest.ini nor a conftest.py registers "
                              "(--strict-markers fails the whole run)" % (rel, name))
        if rel.replace(os.sep, "/") == "helpers/env.py":
            continue
        code = _strip_comments(src)
        errors += _credential_findings(rel, code)
        for m in _URL.finditer(code):
            if _URL_CALL.search(code[max(0, m.start() - 40):m.start()]):
                errors.append("%s opens the literal address %s — use CONFIG.url(...) / CONFIG.api_url(...), so the "
                              "suite follows .env" % (rel, m.group(0)[:60]))
            else:
                warnings.append("%s has a literal address %s — if the suite navigates there, use CONFIG.url(...)"
                                % (rel, m.group(0)[:60]))
        if _ENV_READ.search(code):
            warnings.append("%s reads the environment itself — configuration comes from CONFIG (helpers/env.py "
                            "is the only reader of .env, and it ignores shell variables for identities)" % rel)
    errors += _import_findings(tests_root, trees)
    errors += _fixture_findings(tests_root, trees)

    # 4. the configuration
    gi = os.path.join(tests_root, ".gitignore")
    if not os.path.isfile(gi) or ".env" not in [l.strip() for l in open(gi, encoding="utf-8")]:
        errors.append(".env is not git-ignored in %s" % gi)
    example = _env_file(os.path.join(tests_root, ".env.example"))
    env_py = os.path.join(tests_root, "helpers", "env.py")
    if os.path.isfile(env_py):
        read = set(_GETENV.findall(open(env_py, encoding="utf-8").read()))
        undeclared = sorted(read - set(example))
        if undeclared:
            errors.append(".env.example does not declare %s, which helpers/env.py reads" % ", ".join(undeclared))
    else:
        errors.append("the suite has no helpers/env.py — the only reader of .env")
    for key, value in sorted(example.items()):
        if value and _is_secret_key(key):
            errors.append(".env.example carries a value for %s — the example is committed; a secret lives only "
                          "in .env, filled in by the owner" % key)
        elif value and _is_identity_key(key):
            warnings.append(".env.example names an account in %s — the example is committed; leave it empty"
                            % key)
    env = os.path.join(tests_root, ".env")
    if not os.path.isfile(env):
        warnings.append(".env does not exist — `mrjun.py autotest env` creates it from .env.example (mode 600); "
                        "its owner fills it")
    elif os.stat(env).st_mode & 0o077:
        warnings.append(".env is readable by others — chmod 600 %s" % env)
    for rel in ("start.sh", "conftest.py", "requirements.txt"):
        if not os.path.isfile(os.path.join(tests_root, rel)):
            errors.append("the suite has no %s" % rel)

    core.out(cmap.render(result))
    core.out("")
    for w in warnings:
        core.out("WARN  %s" % w)
    for e in errors:
        core.out("ERROR %s" % e)
    core.out("autotest check: %d error(s), %d warning(s)" % (len(errors), len(warnings)))
    return 1 if errors else 0


# ---------------------------------------------------------------------------------------------------- env

def _project_coordinates(folder, project):
    """(realm, client, liveUrl) of this folder's project: what .dokie/project.json records (the MCP token's
    coordinates win there — an import into another project), else the export's own."""
    recorded = (handoff_cmds._recorded_state(folder).get("project") or {})
    if recorded.get("realm") and recorded.get("client"):
        return recorded["realm"], recorded["client"], recorded.get("liveUrl")
    try:
        realm, client = core.Project(project).realm_client()
    except Exception:
        realm, client = None, None
    return realm, client, recorded.get("liveUrl")


def _base_url(value, folder, project):
    m = re.match(r"^\s*(https?://[^/?#;\s]+)(/[^?#;\s]*)?", value or "")
    if not m:
        raise core.ToolError("--base-url takes an address that starts with http:// or https:// — the origin "
                             "(http://host:port) or the project's whole address (<origin>/<realm>/<client>)")
    origin = m.group(1)
    segments = [s for s in (m.group(2) or "").split("/") if s]
    if "auth" in segments:
        segments = segments[:segments.index("auth")]
    realm, client, _live = _project_coordinates(folder, project)
    notes = []
    if len(segments) >= 2:
        if realm and client and (segments[0], segments[1]) != (realm, client):
            notes.append("the address names %s/%s, this folder's project is %s/%s — right after an import into "
                         "another project; otherwise the suite would test the wrong one"
                         % (segments[0], segments[1], realm, client))
        realm, client = segments[0], segments[1]
    elif not (realm and client):
        raise core.ToolError("only an origin was given and the realm/client are unknown — pass the project's whole "
                             "address, <origin>/<realm>/<client>")
    return "%s/%s/%s" % (origin, realm, client), notes


def _write_env(path, changes):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    pending = dict(changes)
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=", line)
        if m and m.group(1) in pending:
            lines[i] = "%s=%s" % (m.group(1), pending.pop(m.group(1)))
    lines += ["%s=%s" % (k, v) for k, v in pending.items()]
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(path + ".tmp", path)


def cmd_autotest_env(args):
    folder = _default_folder(args.project)
    tests_root = os.path.abspath(args.tests or os.path.join(folder, "test"))
    example_path, env_path = os.path.join(tests_root, ".env.example"), os.path.join(tests_root, ".env")
    if not os.path.isfile(example_path):
        raise core.ToolError("no .env.example in %s — run `mrjun.py autotest scaffold --project %s` first"
                             % (tests_root, args.project))
    created = False
    if not os.path.isfile(env_path):
        shutil.copyfile(example_path, env_path)
        created = True
    os.chmod(env_path, 0o600)

    changes, notes = {}, []
    if args.base_url:
        changes["BASE_URL"], notes = _base_url(args.base_url, folder, args.project)
    for item in args.set or []:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise core.ToolError("--set takes KEY=VALUE, e.g. --set HEADLESS=0")
        if key not in KNOB_KEYS:
            raise core.ToolError("%s is not a setting of the run — the account and the credentials (AUTH_USER, "
                                 "AUTH_PASSWORD, PGDSN, API_KEY) are written into test/.env by the project's owner, "
                                 "in the file, never through a command line or a chat" % key)
        if key == "BASE_URL":
            value, more = _base_url(value, folder, args.project)
            notes += more
        changes[key] = value.strip()
    if changes:
        _write_env(env_path, changes)

    example, env = _env_file(example_path), _env_file(env_path)
    gi = os.path.join(tests_root, ".gitignore")
    ignored = os.path.isfile(gi) and ".env" in [l.strip() for l in open(gi, encoding="utf-8")]
    core.out("autotest env -> %s%s (mode %o, %s)" % (env_path, " — CREATED from .env.example" if created else "",
                                                    os.stat(env_path).st_mode & 0o777,
                                                    "git-ignored" if ignored else "NOT git-ignored"))
    empty_required = []
    for key in list(example) + [k for k in env if k not in example]:
        value = env.get(key)
        if value is None:
            state = "commented out" if key in env else "missing from .env"
        elif not value:
            state = "EMPTY"
        elif key in KNOB_KEYS:
            state = value
        else:
            state = "set"
        if key in REQUIRED_KEYS and not value:
            empty_required.append(key)
            state += " — required; " + ("`autotest env --base-url <origin>` writes it" if key == "BASE_URL" else
                                        "its owner fills it in the file")
        elif not value and key in OPTIONAL_NOTES:
            state += " (%s)" % OPTIONAL_NOTES[key]
        core.out("  %-20s %s" % (key, state))
    stale = sorted(k for k in env if k.startswith("PERSONA_"))
    if stale:
        core.out("NOTE  %s: the suite no longer reads personas — it creates the users a scenario needs itself "
                 "(helpers/accounts.py); delete these lines" % ", ".join(stale))
    _realm, _client, live = _project_coordinates(folder, args.project)
    if "BASE_URL" in empty_required and live:
        core.out("  this folder records the project at %s — `mrjun.py autotest env --project %s --base-url %s`"
                 % (live, args.project, live))
    for n in notes:
        core.out("NOTE  %s" % n)
    if changes:
        core.out("written: %s" % ", ".join(sorted(changes)))
    return 1 if empty_required else 0
