"""Login / logout / locale switch.

⚠️ The password is read from the environment and typed by the BROWSER, never written
into a test, a fixture default, or a log line.  `.env` is git-ignored; `.env.example`
carries an empty value on purpose.

The platform's sign-in form is served by the installation (not by this project), so the
field selectors are matched defensively: id, then name, then type, then placeholder.
If a deployment renders a different form, override the three constants below — that is
the only place that needs to change.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect
from helpers.env import CONFIG
from helpers.locales import LOCALE_MENU_LABEL
from pages.base_page import BasePage

USER_SELECTORS = [
    "#username", "input[name='username']", "input[name='email']",
    "input[type='email']", "input[placeholder*='mail' i]", "input[type='text']",
]
PASS_SELECTORS = [
    "#password", "input[name='password']", "input[type='password']",
]
# The has-text() entries are the sign-in button's own captions (English, Russian); when
# none of these matches, login() falls back to pressing Enter in the password field.
SUBMIT_SELECTORS = [
    "#kc-login", "button[type='submit']", "input[type='submit']",
    "button:has-text('Sign in')", "button:has-text('Войти')", "button:has-text('Log in')",
]


class LoginPage(BasePage):
    def _first_visible(self, selectors: list[str]):
        for sel in selectors:
            loc = self.page.locator(sel).first
            try:
                if loc.count() and loc.is_visible():
                    return loc
            except Exception:
                continue
        return None

    def is_logged_in(self) -> bool:
        """Logged in == the project's own chrome is on screen.

        Two signals, because installations differ in what the header carries: the
        profile link, or failing that the left navigation menu.  Both are absent on
        the sign-in page, which is itself recognised by `/auth` in the URL.
        """
        try:
            self.settle()
        except Exception:
            pass
        if "/auth" in self.page.url:
            return False
        return (self.page.locator("a[href$='/profile']").count() > 0
                or self.page.locator(".vertical-nav-menu a").count() > 0)

    def login(self, user: str | None = None, password: str | None = None, *,
              who: str = "the author account (AUTH_USER / AUTH_PASSWORD)") -> "LoginPage":
        """Sign in; `who` names the account in every failure message (a test user, not the author)."""
        user = user or CONFIG.auth_user
        password = password or CONFIG.auth_password
        if not user or not password:
            raise RuntimeError(
                f"{who}: not set. Fill test/.env (copy from .env.example). "
                "The suite never hard-codes a credential."
            )
        self.page.goto(CONFIG.base_url, wait_until="domcontentloaded")
        if self.is_logged_in():
            return self

        u = self._first_visible(USER_SELECTORS)
        p = self._first_visible(PASS_SELECTORS)
        if u is None or p is None:
            raise AssertionError(
                f"Could not find the sign-in fields at {self.page.url} while signing in {who}. "
                "Adjust USER_SELECTORS / PASS_SELECTORS in pages/login_page.py."
            )
        u.fill(user)
        p.fill(password)
        btn = self._first_visible(SUBMIT_SELECTORS)
        (btn.click() if btn else p.press("Enter"))
        # ⛔ Do NOT judge the result on `networkidle` alone. The click starts a navigation,
        # and the wait returns against the page that is still the sign-in page — so the
        # assertion below fired while the browser was mid-redirect and reported a working
        # credential as a failed login. Wait for the URL to actually leave /auth first.
        try:
            self.page.wait_for_url(lambda url: "/auth" not in url,
                                   timeout=CONFIG.grid_timeout_ms)
        except Exception:
            pass
        self.settle()
        assert self.is_logged_in(), (
            f"Signing in {who} did not land in the project (url={self.page.url}): the page still "
            "shows the sign-in form. Check those keys in test/.env, and that the account is a user of "
            "this project."
        )
        return self

    def logout(self) -> "LoginPage":
        """Sign out of the session — through the platform's own sign-out button, found by its class.

        ⛔ Not by caption: the button is labelled in the session's language, and a caption list only ever covers
        the languages somebody thought of. Every sign-out button of the header carries `nct-logout-btn`, and its
        handler is bound to that class — so the click is the same in every language, with the user menu open or
        closed.
        """
        self.goto("", expect_chrome=False)
        clicked = self.page.evaluate(
            """() => { const b = document.querySelector('.nct-logout-btn');
                       if (!b) return false; b.click(); return true; }""")
        assert clicked, ("the header has no sign-out button (.nct-logout-btn) — the session is not signed in, or "
                         "the page is not one of the project's")
        try:
            self.page.wait_for_url(lambda url: "/auth" in url, timeout=CONFIG.grid_timeout_ms)
        except Exception:
            pass
        self.settle()
        assert not self.is_logged_in(), "pressed sign-out, but the project's chrome is still on screen"
        return self

    # ---------- locale ----------
    def current_locale_country(self) -> str:
        """The country of the language the session shows — the flag on the header's language button."""
        return self.page.evaluate(
            """() => { const f = document.querySelector('.language-icon.flag');
                       if (!f) return '';
                       return [...f.classList].find(c => /^[A-Z]{2}$/.test(c)) || ''; }""")

    def switch_locale(self, locale: str) -> "LoginPage":
        """Pick a language in the header's language menu — by its FLAG, not by its caption.

        Each item of that menu carries the flag of its locale's country (`<span class="flag … US">` for en_US) and
        the language's own name as Java spells it. The flag needs no list of captions, so it works for every
        locale a project declares; LOCALE_MENU_LABEL (helpers/locales.py) is consulted only when two of the
        project's locales share a country.

        ⛔ Do not return right after the click: a language change re-renders the whole page, so the next `goto`
        aborts a navigation that has not finished yet (`net::ERR_ABORTED`), and reading `body` hits a half-empty
        skeleton — the test then reports "the navigation did not switch" although it did. Wait until the left
        menu appears again.
        """
        country = locale.split("_", 1)[1].upper() if "_" in locale else ""
        if country and self.current_locale_country() == country:
            return self                              # already there — a switch would only re-render the page
        opener = self.page.locator("button:has(.language-icon)").first
        if not opener.count():
            raise AssertionError("the header has no language button — the page is not one of the project's")
        # ⛔ Seen live: right after a re-render the first click sometimes leaves the menu closed — click until its
        # items show, at most three times, and never on an open menu (a click would close it).
        items_shown = ".dropdown-menu .dropdown-item:has(.flag)"
        for _ in range(3):
            if self.page.evaluate(f"() => [...document.querySelectorAll('{items_shown}')]"
                                  f".some(e => e.offsetParent !== null)"):
                break
            opener.click()
            self.page.wait_for_timeout(700)
        items = self.page.locator(f".dropdown-menu .dropdown-item:has(.flag.{country})") if country else None
        if items is None or items.count() != 1:
            label = LOCALE_MENU_LABEL.get(locale)
            if not label:
                raise AssertionError(
                    f"cannot tell which language item is {locale}: "
                    + ("no item carries the flag " + country if items is not None and not items.count()
                       else "several of the project's locales share the flag " + country)
                    + " — add its caption to LOCALE_MENU_LABEL in helpers/locales.py")
            items = self.page.locator(".dropdown-menu .dropdown-item").filter(has_text=label)
        items.first.click()
        # Wait for the STATE — the header's flag showing the new country — not for a selector the old page also
        # has: the language change re-renders the whole page, and a navigation started before it ends is aborted.
        waited = 0
        while country and waited < CONFIG.grid_timeout_ms:
            self.page.wait_for_timeout(500)
            waited += 500
            try:
                if self.current_locale_country() == country and self.page.locator(".vertical-nav-menu a").count():
                    break
            except Exception:
                continue                             # the page is being replaced under the question
        self.settle()
        return self
