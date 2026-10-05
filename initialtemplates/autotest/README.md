# Automated test suite — Python + Playwright + pytest

This suite automates **every scenario of `../test-scenarios.md`**. It was written together with the project, at
build time, from the PRD and the scenario file — before the project ran anywhere. Its expected results are the
PRD's, not a screen's: where the build has a defect, the suite is red until the defect is fixed. That is its
purpose.

## Quick start

```bash
cd test
# .env exists (mode 600, git-ignored). Fill BASE_URL, AUTH_USER and AUTH_PASSWORD in it — in the file, never in a chat.
python3 ../builder/tools/mrjun.py autotest env --project ../work   # which keys are set — it never shows a secret
./start.sh            # everything that does not write to the project
```

`start.sh` creates the virtualenv, installs the dependencies, downloads the browser, checks `.env` (it never
prints the password), runs the suite and ends with the **coverage map**: which scenario each test file covers and
which scenarios have no test.

| Command | What it does |
|---|---|
| `./start.sh` | the whole suite except the tests that write to the project |
| `./start.sh smoke` | one minute: the project is up and the sign-in works |
| `./start.sh all` | **including** the scenarios that create and change records in the real project |
| `./start.sh all --run-sends` | …and the ones that SEND something real (a mail, a message, a call to another system) — never implied by `all`: a sent mail cannot be taken back |
| `./start.sh reset` | re-import `../project.mrjun` into the project (ERASES its data) and stop |
| `./start.sh reset all` | reset, then the full run from a known state |
| `./start.sh reset-schema all` | the same, rebuilding the table STRUCTURE — needed exactly when the export's schema changed |
| `./start.sh -k <name>` | any other argument goes straight to pytest |

⚠️ After every import — `reset` included — the workflows arrive **undeployed**, and the reset does NOT deploy
them: deploy every workflow (its BPMN editor → Deploy, or `nct_workflow_deploy` over MCP) before running, or every
process scenario fails on an empty queue.

A **skipped** test is not a passed one: the run's summary counts the skips and `-ra` prints each reason. A missing
persona, `PGDSN` or `API_KEY` is a gap in `.env`; "no data" means the project drifted from the seed rows the
scenarios start from — `./start.sh reset`, then run again.

Watch one test in a visible browser — for a short look only, never for a long run:

```bash
HEADLESS=0 SLOW_MO_MS=250 ./start.sh -k <test name>
```

## `.env`

| Key | Meaning |
|---|---|
| `BASE_URL` | **always** `<root>/<realm>/<client>`. The bare installation root redirects to `…/auth;jsessionid=…` and renders none of the project. `mrjun.py autotest env --base-url <origin>` writes it |
| `AUTH_USER` / `AUTH_PASSWORD` | one user holding the **Author** role group — the only group that can hand out role groups; the suite never removes it — and every role group whose tasks the scenarios perform |
| `DEFAULT_LOCALE` | the locale the suite returns to after the language tests |
| `HEADLESS`, `SLOW_MO_MS`, `DEFAULT_TIMEOUT_MS`, `GRID_TIMEOUT_MS` | browser knobs |
| `PGDSN` | optional — read-only database cross-check of numbers and writes; empty = those checks skip and say so |
| `API_KEY` | optional — the public-API scenarios; empty = they skip and say so |
| `API_BASE_URL` | optional — only when the API answers elsewhere than BASE_URL's installation root; tests build API addresses with `CONFIG.api_url(...)` |
| `PERSONA_<NAME>_USER` / `_PASSWORD` | optional — a second person for four-eyes and "must NOT see" scenarios; missing = they skip and name the persona |

The keys that say WHICH project and WHO signs in are read from `.env` only — a shell variable of the same name is
ignored; the knobs (`HEADLESS`, `SLOW_MO_MS`, the timeouts, `DEFAULT_LOCALE`) may be overridden from the shell for
one run.

## How the suite is organised

* `tests/` — one file per chapter of the scenario file, numbered in run order. Every test cites its scenario as
  `§N.M` in its docstring; `tools/coverage_map.py` counts the citations.
* `pages/` — page objects: `driver.py` acts on forms, dialogs, row menus and grids by their visible captions;
  `register_page.py`, `queue_page.py`, `studio_page.py`, `users_page.py`, `nav.py`, `login_page.py` read their
  screens. Captions come from `helpers/locales.py`, per locale — a test never hard-codes one language.
* `helpers/` — `env.py` (the only reader of `.env`), `locales.py`, `numbers.py` (exact numbers, database-style
  rounding), `db.py` (the optional read-only cross-check: `query()` when the database IS the assertion — skips
  without one; `optional()` when it is a second witness — returns None and warns).
* `tools/` — `coverage_map.py` and `import_project.py` (the reset).
* The project's own extensions live where the harness never overwrites them: fixtures and markers in
  `tests/conftest.py` (`config.addinivalue_line("markers", "<name>: <meaning>")` in `pytest_configure`), page
  objects in `pages/project_<name>.py`, helpers in `helpers/project_<name>.py`. A layout without the standard left
  navigation sets `BasePage.CHROME = "<its own selector>"` in `tests/conftest.py`.

## When a test is red

A red test is either a defect of the product or a defect of the test — find out which before fixing either:

1. reproduce the step by hand in the browser;
2. if the product does what the scenario says, the TEST is wrong — fix the test (a locator, a wait, a caption);
3. if the product does not, it is a defect of the product — fix the project, never the expected value;
4. if the scenario's own arithmetic or requirement is wrong, correct `../test-scenarios.md` first, say why, and
   only then the test.

Innocent causes worth ruling out first: the session dropped (re-run), the import did not land (registers empty),
the workflows are not deployed (queues empty), the session language is not the one the file declares, the run was
killed for memory (the output ends with no summary line at all — that is not a failure).

## What is deliberately not automated

Listed in `../test-scenarios.md` as `{manual: <reason>}` — each with the reason and what a person checks instead.
