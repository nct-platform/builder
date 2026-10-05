"""Fixtures for the project's autotest suite.

Design notes that matter:

* ONE browser session is shared across the suite (`session` scope).  Signing in per
  test is slow and, more importantly, the platform keeps author mode per user — a
  fresh login mid-suite silently changes what the nav shows.
* Destructive scenarios (posting a document, starting a process, re-assigning role
  groups) are gated behind `--run-destructive`.  They act on real records in a real
  tenant; nothing here should surprise whoever owns that data.
* Scenarios that SEND something out of the tenant — a mail to a real inbox, a message,
  a call to another system — are marked `sends` and gated behind `--run-sends`, which
  `./start.sh all` does not imply: a write can be cleaned up, a sent mail cannot.
* A scenario that needs a DIFFERENT person — an approver who may not be the
  initiator, a role that must NOT see a page or a case — signs in as a persona from
  .env in its own browser context (`persona`), so nothing of its session leaks into
  the author's. The author account itself never loses the Author group.
* Nothing opens a browser before .env can point the suite at a project
  (`CONFIG.require()`), so `pytest --collect-only` works without any .env at all —
  wherever pytest and Playwright are installed, that is the quickest proof that every
  test file imports. (A build has neither; its offline gate is `mrjun.py autotest check`.)
"""
from __future__ import annotations

import os
import pytest
from playwright.sync_api import sync_playwright

from helpers.env import CONFIG
from pages.login_page import LoginPage
from pages.nav import Nav


def pytest_addoption(parser):
    parser.addoption("--run-destructive", action="store_true", default=False,
                     help="run tests that create/modify real records in the tenant")
    parser.addoption("--run-sends", action="store_true", default=False,
                     help="run tests that send a real mail, message or call to another system")
    parser.addoption("--locale", action="store", default=None,
                     help="force a locale for this run (one of LOCALES in helpers/locales.py)")


def pytest_collection_modifyitems(config, items):
    gates = (("destructive", "--run-destructive", "writes to a real tenant"),
             ("sends", "--run-sends", "sends a real mail, message or call out of the tenant"))
    for marker, option, why in gates:
        if config.getoption(option):
            continue
        skip = pytest.mark.skip(reason=f"needs {option} ({why})")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def playwright_instance():
    CONFIG.require()            # stop with a sentence about .env, before a browser opens
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance):
    b = playwright_instance.chromium.launch(
        headless=CONFIG.headless,
        slow_mo=CONFIG.slow_mo_ms,
        args=["--disable-dev-shm-usage"],
    )
    yield b
    b.close()


@pytest.fixture(scope="session")
def context(browser):
    ctx = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        # Follows the configuration (DEFAULT_LOCALE in .env) instead of a hard-coded
        # language: the suite must run in any locale the project declares. Playwright
        # wants a BCP-47 tag, so "en_US" becomes "en-US".
        locale=CONFIG.default_locale.replace("_", "-"),
        ignore_https_errors=True,
    )
    ctx.set_default_timeout(CONFIG.timeout_ms)
    yield ctx
    ctx.close()


@pytest.fixture(scope="session")
def page(context):
    p = context.new_page()
    yield p
    p.close()


@pytest.fixture(scope="session")
def logged_in(page) -> LoginPage:
    """Sign in once, as the author account from .env."""
    lp = LoginPage(page)
    lp.login()
    return lp


@pytest.fixture(scope="module", autouse=True)
def module_locale(request, page, logged_in):
    """Every test file starts in a KNOWN locale.

    ⛔ The locale is stored on the USER, on the server, not in the browser: switching it
    in one file (or even in another session — by a person in a neighbouring window) stays
    in force for every file after it. On a first full run this caused a long chain of
    failures in a row: the tests looked for captions in one language while the page was
    rendered in another. Captions are part of what is checked, so the language is set
    explicitly, not inherited.

    A file declares its requirement with a module constant:

        LOCALE = "en_US"

    The default is CONFIG.default_locale (DEFAULT_LOCALE in .env), not a hard-coded
    language: the suite must run in any locale the project declares.
    """
    want = getattr(request.module, "LOCALE", CONFIG.default_locale)
    lp = LoginPage(page)
    try:
        lp.switch_locale(want)
        page.wait_for_timeout(1200)
    except Exception:
        # The switcher was not found (the page is not rendered yet) — do not fail the
        # whole file: the test itself will say so if the captions turn out to be wrong.
        pass
    return want


@pytest.fixture
def nav(page, logged_in) -> Nav:
    return Nav(page)


@pytest.fixture
def at_locale(request, page, logged_in):
    """Run a test at a chosen locale and restore the default afterwards."""
    wanted = request.config.getoption("--locale") or CONFIG.default_locale
    lp = LoginPage(page)
    lp.switch_locale(wanted)
    yield wanted
    if wanted != CONFIG.default_locale:
        lp.switch_locale(CONFIG.default_locale)


@pytest.fixture
def persona(request, browser):
    """Sign in as a SECOND person, in a browser context of its own: `pg = persona("approver")`.

    For the scenarios a different person must perform — an approver who may not be the
    initiator (four eyes), a role that must NOT see a page, a case or an action. The
    account is the owner's PERSONA_<NAME>_USER / PERSONA_<NAME>_PASSWORD in .env (a
    project user holding exactly the role groups the scenario names). When .env does not
    provide it, the test SKIPS and names the persona it needs — a skip, never a pass.

    ⛔ Each persona gets its own context: its session, its locale and its author mode
    live on the server per USER, so sharing the author's page would make each identity
    inherit the other's state. For the same reason the persona's locale is SET after
    signing in (the file's LOCALE, else DEFAULT_LOCALE) — a persona keeps whatever
    language it last chose, and captions are part of what the scenarios check.
    """
    opened = []

    def _open(name: str):
        account = CONFIG.persona(name)
        if account is None:
            key = name.strip().upper()
            pytest.skip(f"needs the persona {name!r}: set PERSONA_{key}_USER and PERSONA_{key}_PASSWORD "
                        "in test/.env — a project user holding the role groups this scenario names")
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale=CONFIG.default_locale.replace("_", "-"),
            ignore_https_errors=True,
        )
        ctx.set_default_timeout(CONFIG.timeout_ms)
        opened.append(ctx)
        pg = ctx.new_page()
        key = name.strip().upper()
        lp = LoginPage(pg).login(account.user, account.password,
                                 who=f"the persona {name!r} (PERSONA_{key}_USER / PERSONA_{key}_PASSWORD)")
        want = getattr(request.module, "LOCALE", CONFIG.default_locale)
        try:
            lp.switch_locale(want)
        except Exception as exc:
            raise AssertionError(f"the persona {name!r} signed in, but its language could not be set to "
                                 f"{want}: {exc}") from exc
        return pg

    yield _open
    for ctx in opened:
        try:
            ctx.close()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _screenshot_on_failure(request, page):
    yield
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
        os.makedirs("test-results/screenshots", exist_ok=True)
        name = request.node.name.replace("/", "_")[:120]
        try:
            page.screenshot(path=f"test-results/screenshots/{name}.png", full_page=True)
        except Exception:
            pass


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())
