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
* People are made, not configured. Every step a person performs in the PRD is
  performed by a TEST USER the suite creates for it, through the application, as the
  author account — holding exactly the role groups the scenario names, as many people
  as the scenario has (`as_user("Clerk")`, `accounts.user("Approver", label="second")`).
  Each signs in in a browser context of its own; all are removed when the session ends.
  The author account itself performs only what the PRD gives an administrator: it holds
  Author, and Author sees what no ordinary role sees.
* No user is ever shown a TECHNICAL error. Every message the platform shows, in every
  context, is recorded as it appears (`pages/feedback_watch.py`); a test during which a
  user saw an exception, a database constraint, a stack trace or a 500 fails — an action
  was offered, or a form accepted, where it should have been hidden or explained.
* Nothing opens a browser before .env can point the suite at a project
  (`CONFIG.require()`), so `pytest --collect-only` works without any .env at all —
  wherever pytest and Playwright are installed, that is the quickest proof that every
  test file imports. (A build has neither; its offline gate is `mrjun.py autotest check`.)
"""
from __future__ import annotations

import os
import warnings

import pytest
from playwright.sync_api import sync_playwright

from helpers.accounts import TestAccounts
from helpers.env import CONFIG
from pages.feedback_watch import FeedbackWatch
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
def feedback() -> FeedbackWatch:
    """Every message the platform showed, in every browser context of the session."""
    return FeedbackWatch()


@pytest.fixture(scope="session")
def context(browser, feedback):
    ctx = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        # Follows the configuration (DEFAULT_LOCALE in .env) instead of a hard-coded
        # language: the suite must run in any locale the project declares. Playwright
        # wants a BCP-47 tag, so "en_US" becomes "en-US".
        locale=CONFIG.default_locale.replace("_", "-"),
        ignore_https_errors=True,
    )
    ctx.set_default_timeout(CONFIG.timeout_ms)
    feedback.install(ctx)
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


@pytest.fixture(scope="session")
def accounts(browser, context, logged_in, feedback) -> TestAccounts:
    """The session's test users — created through the application by the author account, on demand, and removed
    from the project when the session ends. See helpers/accounts.py."""
    factory = TestAccounts(browser, context, feedback)
    yield factory
    left = factory.close()
    if left:
        warnings.warn(f"test users could not be removed from the project — delete them in Users: {', '.join(left)}")


@pytest.fixture
def as_user(request, accounts):
    """A page signed in as a test user holding exactly the given role groups, in the file's LOCALE:

        clerk_page = as_user("Clerk")
        approver_page = as_user("Approver", label="second")   # a DIFFERENT person in the same role

    The same role groups and label give the same user for the whole session — one sign-in, not one per test.
    """
    def _as(*role_groups: str, label: str | None = None):
        account = accounts.user(*role_groups, label=label)
        return accounts.page(account, locale=getattr(request.module, "LOCALE", CONFIG.default_locale))
    return _as


@pytest.fixture(autouse=True)
def _no_technical_error(request, feedback):
    """Fail the test during which any user was shown a technical error (see pages/feedback_watch.py)."""
    mark = feedback.mark()
    yield
    if request.node.get_closest_marker("technical_error_expected"):
        return
    shown = feedback.technical_since(mark)
    if shown:
        pytest.fail(
            "a user was shown a TECHNICAL error — an action was offered, or a form accepted, that should have been "
            "hidden (a predicate) or explained before it was submitted (a validation in its form), or a direct "
            "action's refusal is not in the business's own words:\n  "
            + "\n  ".join(m.replace("\n", " ")[:400] for m in shown),
            pytrace=False)


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
