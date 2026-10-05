"""Shared page behaviour.

Two things about this application drive almost every helper here:

1. It is a Wicket app: a click re-renders a panel rather than navigating, so the
   suite waits on CONTENT (a row, a header, a toast) and not on page loads.
2. Registers and charts fetch asynchronously after first paint, so an empty grid a
   second after navigation is normal and is NOT a failure.
"""
from __future__ import annotations

import re

from playwright.sync_api import Page, expect
from helpers.env import CONFIG


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    # The project's chrome: the left navigation, else the header. A project whose layout draws neither sets its own
    # selector from tests/conftest.py (`BasePage.CHROME = "..."`) — that file belongs to the project and is never
    # replaced by the harness.
    CHROME = ".vertical-nav-menu a, .app-header"

    # ---------- navigation ----------
    def goto(self, path: str = "", *, expect_chrome: bool = True) -> "BasePage":
        """Open a page of the project. `expect_chrome=False` for a page that may legitimately NOT render the project
        (a prohibition scenario opening an address its role may not reach) — the test then asserts the refusal."""
        self.page.goto(CONFIG.url(path), wait_until="domcontentloaded")
        if expect_chrome:
            self.wait_for_app()
        else:
            self.settle()
        return self

    # ⛔ NEVER wait for "networkidle" in this application. It holds an open RSocket
    # connection, so the browser is never network-idle: every such wait runs to its full
    # timeout and returns nothing useful. Measured cost — a full suite run spent hours
    # asleep and finished two tests in eight minutes. Wait for the DOM, then give the
    # panel a bounded moment; anything longer is a content wait (`wait_for_rows`).
    SETTLE_MS = 1200

    def settle(self, ms: int | None = None) -> "BasePage":
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=CONFIG.timeout_ms)
        except Exception:
            pass
        self.page.wait_for_timeout(ms if ms is not None else self.SETTLE_MS)
        return self

    def has_chrome(self) -> bool:
        """The project's frame (left navigation or header) is on the page."""
        return self.page.locator(self.CHROME).count() > 0

    def wait_for_app(self) -> None:
        """The chrome is up — the left navigation (or the header) rendered. Not "some link exists": the sign-in page
        and the platform's error page have links too, and a test that carried on there failed far from the cause."""
        try:
            self.page.wait_for_selector(self.CHROME, state="attached", timeout=CONFIG.timeout_ms)
        except Exception:
            raise AssertionError(
                f"{self.page.url}: the project's chrome ({self.CHROME}) did not render — the session was signed out "
                "(the sign-in form is shown), the server answered with an error page, or this page uses a layout "
                "without the standard chrome (then set BasePage.CHROME in tests/conftest.py)") from None
        self.settle()

    # ---------- generic waits ----------
    def wait_for_rows(self, min_rows: int = 1, timeout: int | None = None):
        """Wait until a data grid actually has rows.

        Registers paint their header first and fill in over RSocket, so asserting
        immediately after navigation is the classic false negative here.
        """
        timeout = timeout or CONFIG.grid_timeout_ms
        self.page.wait_for_function(
            """(min) => {
                 const ts = [...document.querySelectorAll('table')];
                 return ts.some(t => t.querySelectorAll('tbody tr').length >= min);
               }""",
            arg=min_rows,
            timeout=timeout,
        )

    def grid_text(self) -> str:
        """innerText of the biggest table on the page — the data grid."""
        return self.page.evaluate(
            """() => {
                 const ts = [...document.querySelectorAll('table')];
                 if (!ts.length) return '';
                 ts.sort((a,b) => b.innerText.length - a.innerText.length);
                 return ts[0].innerText;
               }"""
        )

    def grid_rows(self) -> list[list[str]]:
        return self.page.evaluate(
            """() => {
                 const ts = [...document.querySelectorAll('table')];
                 if (!ts.length) return [];
                 ts.sort((a,b) => b.innerText.length - a.innerText.length);
                 return [...ts[0].querySelectorAll('tbody tr')]
                   .map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()));
               }"""
        )

    def row_containing(self, text: str):
        """The grid row that holds `text` — the anchor for a row action."""
        return self.page.locator("tr", has=self.page.get_by_text(text, exact=False)).first

    # ---------- row actions ----------
    def open_row_actions(self, row_text: str):
        """Open the action menu of the row in which `row_text` appears.

        ⛔ Do not take the caret as "the last button or link in the first cell": the
        same cell also holds the menu ITEMS themselves — hidden `<a class="nav-link">`.
        `.last` lands on a hidden item, Playwright waits 30 seconds for it to become
        visible and fails on the timeout, and that looks like "the page is not
        responding". The caret is the only element with the `dropdown-toggle` class.
        """
        row = self.row_containing(row_text)
        row.scroll_into_view_if_needed()
        caret = row.locator("td").first.locator("button.dropdown-toggle, a.dropdown-toggle")
        if caret.count():
            caret.first.click()
        else:
            # fallback: the cell's visible button (not a link — the links here are menu items)
            row.locator("td").first.locator("button").first.click()
        self.page.wait_for_timeout(600)

    def click_action(self, label: str):
        """Click an item in the OPEN row-action menu.

        ⛔ `get_by_role("link", name=…).first` does not work here: every row of the
        register has its own hidden menu with the same captions, and `.first` lands on
        another row's invisible item — a 30-second wait and a timeout. Take the FIRST
        VISIBLE one: exactly one is visible — the one whose caret was just opened.
        """
        clicked = self.page.evaluate(
            """(t) => {
                 const els=[...document.querySelectorAll('a')]
                   .filter(e=>e.offsetParent && e.innerText.trim() === t);
                 if(!els.length) return false;
                 els[0].click(); return true;
               }""",
            label,
        )
        if not clicked:
            raise AssertionError(
                f"the open row menu has no visible item {label!r}; "
                "check that the menu really is open (open_row_actions)"
            )
        self.settle()

    # ---------- feedback ----------
    # Boilerplate lines of the feedback panel: they are always there and say nothing.
    _TOAST_BOILERPLATE = ("please fix the following errors", "field validation errors",
                          "warnings:", "field warnings:", "ignore warnings")

    def toast_text(self, pattern: str = "", timeout_ms: int = 10000) -> str:
        """The platform's message — WAITED FOR, not read once.

        ⛔ A refusal arrives asynchronously (Wicket renders the panel after the server
        responds) and disappears by itself a few seconds later. Reading it "once, after
        a fixed pause" turns every refusal check into a coin toss: in time — the test is
        green; too late — "there was no refusal", i.e. a false accusation that the
        product allowed something forbidden. That is exactly how refusal checks
        reported gates as not firing while the gates worked.

        `pattern` is a regular expression: wait not for any message but for the one
        you need (the panel may show a boilerplate line before the meaningful one).
        """
        rx = re.compile(pattern, re.I) if pattern else None
        waited = 0
        while True:
            texts = self.page.evaluate(
                """() => [...document.querySelectorAll(
                     "[class*='toast'],[class*='feedback'],[class*='alert'],[role='alert']")]
                     .filter(e => e.offsetParent !== null)
                     .map(e => (e.innerText || '').trim())"""
            )
            for raw in texts:
                body = "\n".join(
                    l for l in raw.splitlines()
                    if l.strip() and l.strip() != "×"
                    and not any(b in l.strip().lower() for b in self._TOAST_BOILERPLATE)
                ).strip()
                if not body:
                    continue
                if rx is None or rx.search(body):
                    return body
            if waited >= timeout_ms:
                return ""
            self.page.wait_for_timeout(400)
            waited += 400

    def has_500(self) -> bool:
        """The page returned a server error.

        ⛔ Do not search the page text for "500": any register holds amounts and
        quantities such as "1 500,00" or "1500.0", and the check declared a working
        page broken. A real error is recognised by the tab TITLE and by the standard
        error page, not by an occurrence of three digits.
        """
        title = (self.page.title() or "")
        if re.search(r"\b(500|Internal Server Error)\b", title):
            return True
        # A RAW string: in a plain one Python turns "\b" into a backspace character, and the two "500 —"
        # forms below silently never matched.
        return self.page.evaluate(
            r"""() => {
                 const t=(document.body.innerText||'').slice(0, 1200);
                 return /Internal Server Error|HTTP ERROR 500|\b500 —|\b500 -/.test(t);
               }"""
        )

    def content_is_blank(self) -> bool:
        """The blank-landing signature: the chrome renders, the content area has nothing.

        This is exactly the defect a live test found on every `*-landing` page of a project, so it gets a first-class
        predicate rather than an ad-hoc check. Content is anything a person could read or use INSIDE the content
        area, outside the chrome (header, navigation, breadcrumb, footer): a visible grid, form control, chart
        (canvas / svg), image or frame of real size, or at least a sentence of text — a dashboard of charts and a
        studio component of figures are content too. Elements of the chrome never count: the header's search box
        once made an empty page look full.
        """
        return self.page.evaluate(
            """() => {
                 const root = document.querySelector('.app-main__inner') || document.querySelector('main')
                              || document.body;
                 const chrome = '.app-header, .app-sidebar, .vertical-nav-menu, .app-footer, .app-page-title, '
                              + '[class*="breadcrumb"], .app-drawer-wrapper';
                 const shown = e => !!(e.offsetParent || e.getClientRects().length) && !e.closest(chrome);
                 const size = e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; };
                 for (const e of root.querySelectorAll('table,input,select,textarea,canvas,svg,img,iframe,video')) {
                   if (!shown(e) || (e.tagName === 'INPUT' && e.type === 'hidden')) continue;
                   const [w, h] = size(e);
                   const media = ['CANVAS', 'SVG', 'svg', 'IMG', 'IFRAME', 'VIDEO'].includes(e.tagName);
                   if (media ? (w >= 40 && h >= 40) : (w >= 20 && h >= 12)) return false;
                 }
                 let text = '';
                 const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                 while (walk.nextNode()) {
                   const p = walk.currentNode.parentElement;
                   if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(p.tagName) || !shown(p)) continue;
                   text += walk.currentNode.textContent.replace(/\\s+/g, '');
                   if (text.length >= 20) return false;
                 }
                 return true;
               }"""
        )
