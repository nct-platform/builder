"""Left navigation + the author drawer.

Every Dokie project INHERITS the admin quick links from `empty.mrjun`.  They live in
the nav group the baseline calls `Pages` (a project may rename that group), and
they are only visible while the signed-in user has the Author role AND author mode is
switched ON.

Author mode is a toggle in the "Site" header menu. Its caption states the ACTION, not the
current state ("I am author" while it is off, "I am not author" while it is on), and it is
written in the session's language — so this module reads neither caption. The menu is the
header dropdown whose toggle carries the `pe-7s-tools` icon; the switch is its item with the
`pe-7s-user` icon; and the STATE is judged by its effect: the inherited admin links are in the
navigation exactly while author mode is on.

The same menu holds "Edit site" — the authoring page builder. That is author tooling, not an
end-user scenario; the suite never drives it.
"""
from __future__ import annotations

from playwright.sync_api import Page
from helpers.env import CONFIG
from pages.base_page import BasePage

# Admin quick links every project inherits from the empty template.
# Paths are relative to <root>/<realm>/<client>.
ADMIN_QUICKLINKS = {
    "rules":          "Rules — Groovy rules",
    "contexts":       "Contexts",
    "form":           "Form groups",
    "workflows":      "Workflows (BPMN editor + Deploy)",
    "processes":      "Process instances",
    "users":          "Users",
    "roles":          "Role groups",
    "database":       "Database (schemas, tables, sources)",
    "bl":             "Business Logic (dynamic CRUDs, queries)",
    "audit-logs":     "Audit logs",
    "mail-templates": "Mail templates",
    "pdf-templates":  "PDF templates",
    "schedulers":     "Schedulers",
    "settings":       "Settings — also where a .mrjun is IMPORTED",
}

# Present for every signed-in user, author or not.
COMMON_LINKS = {"profile": "My profile"}

# The header's "Site" menu, and the author-mode switch inside it — located by their icons, in every language.
SITE_MENU_TOGGLE = "a.dropdown-toggle:has(i.pe-7s-tools), button.dropdown-toggle:has(i.pe-7s-tools)"


class Nav(BasePage):
    def link_paths(self) -> list[str]:
        rc = CONFIG.realm_client
        return self.page.evaluate(
            """(rc) => [...document.querySelectorAll('a[href]')]
                 .map(a => a.getAttribute('href'))
                 .filter(h => h && h.startsWith(rc))
                 .map(h => h.slice(rc.length).replace(/^\\//, ''))""",
            rc,
        )

    def visible_admin_links(self) -> set[str]:
        """The inherited admin links the LEFT NAVIGATION shows — only there: a page's own breadcrumb or buttons may
        link to /users or /settings whatever the mode is."""
        rc = CONFIG.realm_client
        paths = set(self.page.evaluate(
            """(rc) => [...document.querySelectorAll('.vertical-nav-menu a[href]')]
                 .map(a => a.getAttribute('href'))
                 .filter(h => h && h.startsWith(rc))
                 .map(h => h.slice(rc.length).replace(/^\\//, ''))""",
            rc))
        return {p for p in ADMIN_QUICKLINKS if p in paths}

    # ---------- author mode ----------
    def _open_site_menu(self) -> bool:
        """Open the "Site" menu in the header — the dropdown whose toggle carries the `pe-7s-tools` icon.

        ⛔ A synthetic `element.click()` from JS does NOT open this menu: its handler waits for real user input,
        not for a programmatically created event. So the click goes through a Playwright locator — it sends input
        through the browser protocol.
        """
        toggle = self.page.locator(SITE_MENU_TOGGLE).first
        if not toggle.count():
            return False
        # ⛔ Seen live: the first click after a page (re-)render sometimes leaves the menu closed, and a second one
        # opens it. So click until its items are visible — never more than three times, and never on a menu that
        # is already open (a click would close it).
        for _ in range(3):
            if self._site_menu_open():
                return True
            try:
                toggle.click(timeout=5000)
            except Exception:
                return False
            self.page.wait_for_timeout(700)
        return self._site_menu_open()

    def _site_menu_open(self) -> bool:
        return bool(self.page.evaluate(
            """() => { const t = document.querySelector('.dropdown-toggle:has(i.pe-7s-tools)');
                       const li = t && t.closest('li,.dropdown,.nav-item');
                       return !!li && [...li.querySelectorAll('a')].some(a => a !== t && a.offsetParent !== null); }"""))

    def author_mode_is_on(self) -> bool:
        """Whether author mode is on — judged by its OBSERVABLE EFFECT: the inherited admin links are in the
        navigation exactly while it is on. A page without the navigation is judged on the front door."""
        for attempt in (1, 2):
            try:
                if self.page.locator(".vertical-nav-menu a").count() == 0:
                    self.goto("")
                return bool(self.visible_admin_links())
            except Exception:
                if attempt == 2:
                    raise
                self.page.wait_for_timeout(1500)     # the page was re-rendering under the question
        return False

    def set_author_mode(self, on: bool) -> "Nav":
        """Author mode is sticky and lives with the user on the server — set it explicitly before any check of what
        a role can see, or the previous test leaks into the current one."""
        if self.author_mode_is_on() == on:
            return self
        if not self._open_site_menu():
            raise AssertionError("the header has no 'Site' menu (the dropdown with the pe-7s-tools icon) — the "
                                 "signed-in account is not an author of this project")
        # ⛔ A REAL click (Playwright input), not element.click() from JS: seen live, the switch ignores a synthetic
        # click — nothing happens and nothing says so.
        item = self.page.locator("li:has(.dropdown-toggle i.pe-7s-tools) a:has(i.pe-7s-user)").first
        if not item.count() or not item.is_visible():
            raise AssertionError("the 'Site' menu has no author-mode switch (the item with the pe-7s-user icon) — "
                                 "the switch is offered only to a real author of a REPORT project")
        item.click()
        # The switch re-renders the page; the admin links arrive with it — wait for the state, not for a clock.
        deadline = CONFIG.grid_timeout_ms
        waited = 0
        while waited < deadline:
            self.page.wait_for_timeout(1000)
            waited += 1000
            try:
                if self.page.locator(".vertical-nav-menu a").count() and bool(self.visible_admin_links()) == on:
                    self.settle()
                    return self
            except Exception:
                continue                             # the re-render is still under way
        raise AssertionError(f"pressed the author-mode switch, but author mode is still "
                             f"{'off' if on else 'on'} (judged by the inherited admin links in the navigation)")
