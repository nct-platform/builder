#!/usr/bin/env bash
#
# Runs the project's autotests with one command.
#
#   ./start.sh                  run without the destructive tests (safe)
#   ./start.sh smoke            only the "application is alive and the session works" check
#   ./start.sh all              including the destructive tests (they write to the real tenant!)
#   ./start.sh all --run-sends  ...and the tests that SEND something real — a mail, a message, a call
#                               to another system. Never part of `all` on its own: a sent mail
#                               cannot be taken back.
#   ./start.sh reset            bring the tenant back to its initial state and run nothing
#   ./start.sh reset all        reset, then a full run "from scratch"
#   ./start.sh reset-schema all reset WITH A REBUILD OF THE TABLE STRUCTURE — for when the
#                               schema in the export changed (a column/table was added)
#   ./start.sh -k <keyword>     any other arguments go to pytest as they are
#   ./start.sh -m <marker> -x   ...and they combine
#
# After every run a COVERAGE MAP is printed: which section of ../test-scenarios.md is
# covered by which test file, and which sections are not covered at all
# (tools/coverage_map.py).
#
# The script brings the environment to a working state by itself: venv, dependencies,
# browser. It never prints the password or writes it anywhere — it only checks that it is set.
set -euo pipefail

cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"
RESULTS="test-results"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. environment
say "1/4 Environment"

if [ ! -x "$PY" ]; then
  warn "venv not found — creating $VENV"
  python3 -m venv "$VENV"
fi
ok "python: $("$PY" --version 2>&1)"

# Install the dependencies only when something is missing: otherwise every run would go to the network.
if ! "$PY" -c 'import playwright, pytest, dotenv' >/dev/null 2>&1; then
  warn "dependencies missing — installing from requirements.txt"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt
fi
ok "dependencies in place"

# The Playwright browser lives outside the venv (in the user's cache), so it is checked separately.
if ! "$PY" -m playwright install --dry-run chromium >/dev/null 2>&1; then
  die "playwright does not respond — try: $PY -m pip install -r requirements.txt"
fi
CHROMIUM_DIR="$("$PY" -m playwright install --dry-run chromium 2>/dev/null \
  | awk -F': +' '/Install location/ {print $2; exit}')"
if [ -n "${CHROMIUM_DIR:-}" ] && [ ! -d "$CHROMIUM_DIR" ]; then
  warn "browser not downloaded yet — downloading chromium (once, ~150 MB)"
  "$PY" -m playwright install chromium
fi
ok "chromium ready"

# ---------------------------------------------------------------- 2. .env
say "2/4 Settings"

[ -f .env ] || die ".env not found. Create it: cp .env.example .env && chmod 600 .env — and fill in the three lines."

# Read .env without putting the values into the log. Empty and commented-out lines are ignored.
missing=()
for var in BASE_URL AUTH_USER AUTH_PASSWORD; do
  value="$(grep -E "^${var}=" .env | tail -1 | cut -d= -f2- || true)"
  [ -n "${value//[[:space:]]/}" ] || missing+=("$var")
done
if [ ${#missing[@]} -gt 0 ]; then
  die "not filled in .env: ${missing[*]}
     BASE_URL      — always <root>/<realm>/<client>, e.g. https://<host>/<realm>/<client>
                     (the bare root redirects to /auth and does not render the project)
     AUTH_USER     — the e-mail of a user in the Author role group
     AUTH_PASSWORD — that user's password (.env is in .gitignore and never gets committed)"
fi
ok "BASE_URL: $(grep -E '^BASE_URL=' .env | tail -1 | cut -d= -f2-)"
ok "AUTH_USER: $(grep -E '^AUTH_USER=' .env | tail -1 | cut -d= -f2-)"
ok "AUTH_PASSWORD: set"

# ---------------------------------------------------------------- 3. what to run
say "3/4 What to run"

PYTEST_ARGS=()   # see the bash 3.2 note below
MODE="safe"
RESET="no"
# ⛔ `reset` is the first word, because the reset comes before any mode:
# "./start.sh reset all" means "restore the initial data, then run everything".
REBUILD=""
if [ "${1:-}" = "reset" ]; then RESET="yes"; shift; fi
# ⛔ A separate mode, not a flag: rebuilding the structure re-creates the tables, and it must
# never be asked for by accident. It is needed exactly when the SCHEMA in the export changed —
# otherwise the new SQL arrives at the old table, the import reports success, and the CRUD
# table fails.
if [ "${1:-}" = "reset-schema" ]; then RESET="yes"; REBUILD="--rebuild-structure"; shift; fi
case "${1:-}" in
  smoke) MODE="smoke"; shift ;;
  all)   MODE="all";   shift ;;
esac
# ⛔ bash 3.2 (the stock one on macOS) under `set -u` fails on "${arr[@]}" when the array is
# empty, so everywhere below it is expanded as ${arr[@]+...} — otherwise a run without
# arguments dies with "unbound variable" before the first test.
[ $# -gt 0 ] && PYTEST_ARGS+=("$@")

case "$MODE" in
  smoke)
    ok "smoke only — the application responds, sign-in works"
    PYTEST_ARGS=(-m smoke ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"})
    ;;
  all)
    warn "destructive tests are ON: they create and change records in the real tenant"
    PYTEST_ARGS=(--run-destructive ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"})
    ;;
  safe)
    ok "the full suite except the destructive tests (to include them: ./start.sh all)"
    ;;
esac

mkdir -p "$RESULTS/screenshots"

# ------------------------------------------------------- 3b. tenant reset
# Scenario tests write to the tenant: running the same scenario a second time in a row meets
# the records the first run already created, and checks the wrong thing. The reset restores
# the data from the archive's dump — the ONLY way to get an identical start; the platform has
# neither an API nor a CLI for it.
if [ "$RESET" = "yes" ]; then
  say "3b/4 Tenant reset"
  MRJUN="../project.mrjun"
  [ -f "$MRJUN" ] || die "$MRJUN not found — build the archive first:
     python3 builder/tools/mrjun.py pack work project.mrjun"
  warn "the import ERASES the tenant's data and restores it from the archive's dump"
  [ -n "$REBUILD" ] && warn "table structure rebuild is on — the schema will be created anew"
  if ! "$PY" tools/import_project.py "$MRJUN" ${REBUILD:+$REBUILD}; then
    die "the import failed — see the output above; not running tests on data that was not reset"
  fi
  ok "import finished"
  warn "after an import the workflows arrive NOT deployed"
  printf '     Re-deploy EVERY workflow of the project (Administration → Workflows → Deploy),\n'
  printf '     otherwise work queues stay empty.\n'
  if [ "$MODE" = "safe" ] && [ ${#PYTEST_ARGS[@]} -eq 0 ]; then
    say "Summary"
    ok "reset done; no tests were run (add 'all' to run them right away)"
    exit 0
  fi
fi

# ---------------------------------------------------------------- 4. run
# A full run keeps a browser open for a long time (tens of minutes on a large suite). If the
# machine is short of free memory, the system kills the process — the run breaks off WITHOUT
# a summary line, and that is easy to mistake for a test failure. Warn up front, while there
# is still time to close what is not needed.
# ⛔ Under `set -euo pipefail` a missing tool inside $(...) ends the whole script: macOS has vm_stat, Linux
# has /proc/meminfo, and neither has the other — so each is asked only where it exists.
FREE_MB=""
if [ -r /proc/meminfo ]; then
  FREE_MB="$(awk '/^MemAvailable:/ {print int($2/1024); exit}' /proc/meminfo || true)"
elif command -v vm_stat >/dev/null 2>&1; then
  FREE_MB="$( (vm_stat 2>/dev/null || true) | awk '/page size of/ {for (i=1;i<=NF;i++) if ($i ~ /^[0-9]+$/) ps=$i} /Pages free/ {gsub(/\./,"",$3); f=$3} /Pages inactive/ {gsub(/\./,"",$3); i=$3} END {if (f=="") print ""; else print int((f+i)*(ps?ps:16384)/1048576)}' || true)"
fi
if [ -n "${FREE_MB:-}" ] && [ "$FREE_MB" -lt 1500 ]; then
  warn "only ${FREE_MB} MB of free memory — the system may kill the run halfway through"
  printf '     Close heavy applications (virtual machines, IDEs) and start again.\n'
  printf '     A run that was killed prints no summary — that is not a test failure.\n'
fi

say "4/4 Run"

set +e
"$PY" -m pytest ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}
CODE=$?
set -e

# ⛔ A skipped test is NOT a passed one: the scenario behind it was not verified. pytest's exit code is 0 with
# skips, so "all green" would hide them — count them from the run's own report.
SKIPPED="$("$PY" - <<'PYEOF' 2>/dev/null || true
import xml.etree.ElementTree as ET
try:
    root = ET.parse("test-results/junit.xml").getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    print(sum(int(s.get("skipped", 0) or 0) for s in suites))
except Exception:
    print("")
PYEOF
)"

# ⛔ The last thing the run prints answers a question nothing else can check: are ALL
# sections of the scenarios covered by tests? A suite that is green and covers half of
# them is more dangerous than no suite at all — people trust it.
"$PY" tools/coverage_map.py || true

say "Summary"
if [ $CODE -eq 0 ] && [ -n "${SKIPPED:-}" ] && [ "$SKIPPED" != "0" ]; then
  warn "no failures, but ${SKIPPED} test(s) SKIPPED — their scenarios were NOT verified (reasons: the 'SKIPPED' lines above)"
  printf '     a missing persona, PGDSN or API_KEY is a gap in .env; "needs --run-destructive" / "--run-sends" is the\n'
  printf '     mode you chose; "no data" means the tenant drifted from the seed rows — ./start.sh reset, then run again.\n'
elif [ $CODE -eq 0 ]; then
  ok "all green"
elif [ $CODE -eq 5 ]; then
  warn "no test matched the filter — check the arguments"
else
  warn "there are failures — see the output above"
  shots="$(find "$RESULTS/screenshots" -name '*.png' -newermt '-10 minutes' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$shots" != "0" ] && warn "screenshots of the failed tests: $RESULTS/screenshots ($shots files)"
  printf '\n  Common causes to rule out before calling it a product bug:\n'
  printf '   • the session got logged out — run again, the suite signs in by itself;\n'
  printf '   • the project import did not land (CRUD tables are empty) — see the project case notes;\n'
  printf '   • the session language is not the one the test file expects — a file sets it with its LOCALE constant;\n'
  printf '   • the tenant drifted from the seed rows the scenarios start from — ./start.sh reset, then run again;\n'
  printf '   • a SKIPPED test is not among the failures, and not verified either — read its reason above.\n'
fi
printf '\n'
exit $CODE
