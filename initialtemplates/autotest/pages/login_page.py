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
        """Sign in; `who` names the account in every failure message (a persona's keys, not the author's)."""
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
        """Sign out of the session.

        ⛔ Do NOT click the profile link: it sits in the collapsed user menu and is
        invisible, so `click()` waits the full 30 seconds for it to become visible and
        fails on the timeout — "the page is not responding" about a page that works.
        Open the project's front door instead, open the USER menu in the header (it is
        captioned with the user's name) and press its sign-out item; when that menu does
        not open, try once more through the menu's icon.
        """
        # ⛔ The profile page can be empty — it carries only the navigation; the sign-out
        # item lives in the USER menu in the header (captioned with the user's name).
        # Verified with a probe: /profile contained neither "Logout" nor "Выход".
        self.goto("")
        self.settle()
        self.page.evaluate(
            """() => {
                 const els=[...document.querySelectorAll('a,button,span,div')]
                          .filter(e=>e.offsetParent!==null);
                 // the user's name in the header: a short text near the top of the page
                 const cand=els.filter(e=>{
                    const t=(e.innerText||'').trim();
                    // ⛔ a real line break inside a JS literal is a SyntaxError
                    if(!t || t.length>40 || t.includes(String.fromCharCode(10))) return false;
                    const r=e.getBoundingClientRect();
                    return r.top < 90 && r.width < 320 && r.width > 40;
                 });
                 for (const e of cand.reverse()) { e.click(); return true; }
                 return false;
               }"""
        )
        self.page.wait_for_timeout(900)
        # The platform's own sign-out captions in each UI language (Russian, English,
        # Armenian) — data, not prose; extend if a project runs the UI in another language.
        for name in ("Выход", "Logout", "Sign out", "Ելք"):
            link = self.page.get_by_text(name, exact=False)
            for i in range(link.count()):
                el = link.nth(i)
                try:
                    if el.is_visible():
                        el.click()
                        self.settle()
                        return self
                except Exception:
                    continue
        # Fallback: open the user menu in the header and click sign-out in it
        for sel in ("header [class*='user']", "header img", "[class*='user-menu']"):
            loc = self.page.locator(sel)
            if loc.count():
                try:
                    loc.first.click()
                    self.page.wait_for_timeout(800)
                except Exception:
                    pass
                for name in ("Выход", "Logout", "Sign out", "Ելք"):
                    link = self.page.get_by_text(name, exact=False)
                    for i in range(link.count()):
                        el = link.nth(i)
                        try:
                            if el.is_visible():
                                el.click()
                                self.settle()
                                return self
                        except Exception:
                            continue
        raise AssertionError(
            "found no visible sign-out item in the header's user menu (opened by the user's "
            "name, then by the menu icon)"
        )

    # ---------- locale ----------
    def switch_locale(self, locale: str) -> "LoginPage":
        """Pick a language in the header's flag menu.

        ⛔ Do not return right after the click: a language change re-renders the whole
        page, so the next `goto` aborts a navigation that has not finished yet
        (`net::ERR_ABORTED`), and reading `body` hits a half-empty skeleton — the test
        then reports "the navigation did not switch" although it did.
        Wait until the left menu appears again.
        """
        label = LOCALE_MENU_LABEL[locale]
        self.page.locator("header img, [class*='flag']").first.click()
        self.page.wait_for_timeout(600)
        self.page.get_by_text(label, exact=False).first.click()
        self.settle()
        try:
            self.page.wait_for_selector(".vertical-nav-menu a", timeout=CONFIG.grid_timeout_ms)
        except Exception:
            pass
        self.page.wait_for_timeout(800)
        return self
