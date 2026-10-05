"""§1.1–§1.2 · The project opens, the author signs in, and the front door is not blank.

The smallest proof that the suite reaches the project at all — every other file assumes it, so a red run starts
here. It also shows the conventions every test file of the suite follows:

* one file per chapter of ../test-scenarios.md, named after it, numbered in run order (test_04_orders.py …);
* every test cites the scenario it automates as `§N.M` in its docstring — tools/coverage_map.py and
  `mrjun.py autotest check` count those citations, and a scenario nobody cites is a hole in the hand-over;
* the EXPECTED result comes from the scenario file (and through it from the PRD), never from what the screen
  showed: a test written from the screen encodes whatever bug was on it;
* every assertion message says what was expected, what was seen and what that means — a red run must be readable
  by someone who did not write the test;
* wait on CONTENT (rows, a heading, a toast), never on navigation: this is a Wicket application whose grids,
  dialogs and menus arrive by ajax after the page "loaded".
"""
import pytest

from helpers.env import CONFIG
from pages.base_page import BasePage


@pytest.mark.smoke
@pytest.mark.auth
def test_1_1_sign_in_lands_inside_the_project(page, logged_in):
    """§1.1 — the author account from .env signs in and lands INSIDE the project (<root>/<realm>/<client>)."""
    assert logged_in.is_logged_in(), (
        "the sign-in did not complete: the login form is still shown. Check AUTH_USER / AUTH_PASSWORD in "
        "test/.env — and that the account is a member of THIS project.")
    assert CONFIG.realm_client in page.url, (
        f"signed in, but the browser is at {page.url!r}, outside {CONFIG.realm_client!r}: BASE_URL must be the "
        "project's own address <root>/<realm>/<client>, not the installation root.")


@pytest.mark.smoke
@pytest.mark.nav
def test_1_2_front_door_is_not_blank(page, logged_in):
    """§1.2 — the project's front door renders real content: not an empty shell, not an error page."""
    home = BasePage(page).goto("", expect_chrome=False)
    assert not home.has_500(), "the front door answers with the platform's error page"
    assert home.has_chrome(), (
        f"the front door ({page.url}) renders no project frame — neither the left navigation nor the header: the "
        "session fell back to the sign-in page, or Home points at a page outside the project's layout.")
    assert not home.content_is_blank(), (
        "the front door renders its frame (menu, header) but no content — the home page's plugin did not render, "
        "or Home redirects to a page that has none (doc 21).")
