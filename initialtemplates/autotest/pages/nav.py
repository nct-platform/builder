"""Left navigation + the author drawer.

Every Dokie project INHERITS the admin quick links from `empty.mrjun`.  They live in
the nav group the baseline calls `Pages` (a project may rename that group), and
they are only visible while the signed-in user has the Author role AND author mode is
switched ON.

Author mode is a toggle in the "Site" header menu («Сайт», «Կայք»).  Its label states
the ACTION, not the current state:
    "Я не являюсь автором." / "I am not an author"  -> author mode is currently ON
    "Я автор" / "I'm author"                        -> author mode is currently OFF

The same menu holds "Редактировать сайт" / "Edit site" — the authoring page builder.
That is author tooling, not an end-user scenario; the suite never drives it.
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
COMMON_LINKS = {"profile": "My profile — also the locale switch"}

# The platform's own captions in each UI language (Russian, English, Armenian) — data,
# not prose. Extend the tuples if a project runs the UI in another language.
AUTHOR_MODE_ON_LABELS = ("Я не являюсь автором", "I am not an author", "Ես հեղինակ չեմ")
AUTHOR_MODE_OFF_LABELS = ("Я автор", "I'm author", "I am author", "Ես հեղինակ եմ")
EDIT_SITE_LABELS = ("Редактировать сайт", "Edit site", "Խմբագրել կայքը")


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
        paths = set(self.link_paths())
        return {p for p in ADMIN_QUICKLINKS if p in paths}

    # ---------- author mode ----------
    # The "Site" header menu's caption in each UI language (the platform's own captions).
    SITE_MENU_LABELS = ("Сайт", "Site", "Կայք")

    def _open_site_menu(self) -> bool:
        """Open the "Site" menu in the header. Its caption depends on the locale, so all
        three are tried.

        ⛔ A synthetic `element.click()` from JS does NOT open this menu: its handler
        waits for real user input, not for a programmatically created event. Verified
        on a live page: the element is found (`a.nav-link.dropdown-toggle`), the click
        runs without an error, and the menu stays closed. So the click goes through a
        Playwright locator — it sends input through the browser protocol.
        """
        def menu_open() -> bool:
            return self.page.evaluate(
                """() => [...document.querySelectorAll('.dropdown-menu')]
                     .some(m => m.offsetParent !== null && m.innerText.trim().length > 0)"""
            )

        for cap in self.SITE_MENU_LABELS:
            loc = self.page.locator("a.dropdown-toggle, button.dropdown-toggle").filter(
                has_text=cap)
            if not loc.count():
                continue
            try:
                loc.first.click(timeout=5000)
            except Exception:
                continue
            self.page.wait_for_timeout(700)
            if menu_open():
                return True
            # Fallback: some builds open the menu on mousedown rather than on click.
            # Send the full pointer sequence, not a bare .click().
            self.page.evaluate(
                """(cap) => {
                     const el=[...document.querySelectorAll('a.dropdown-toggle,button.dropdown-toggle')]
                       .find(e=>e.offsetParent && e.innerText.trim().startsWith(cap));
                     if(!el) return;
                     for (const type of ['pointerdown','mousedown','pointerup','mouseup','click']) {
                       el.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, view:window}));
                     }
                   }""",
                cap,
            )
            self.page.wait_for_timeout(700)
            if menu_open():
                return True
        return False

    def _visible_menu_text(self) -> str:
        """The text of the VISIBLE items of the open menu, and only of those.

        ⛔ `body.inner_text()` is no use here: the menu items are in the DOM at all times,
        so they cannot tell whether the menu is open — let alone which mode the site is in.
        """
        return self.page.evaluate(
            """() => [...document.querySelectorAll('a,button,span')]
                 .filter(e=>e.offsetParent)
                 .map(e=>e.innerText.trim()).join(String.fromCharCode(10))"""
        )

    def author_mode_is_on(self) -> bool:
        """Whether author mode is on — judged by its OBSERVABLE EFFECT, not by a caption.

        ⛔ Reading the state from the toggle's caption is doubly unreliable: the menu has
        to be opened (and not every event opens it), and the caption states the ACTION,
        not the state. But author mode shows itself precisely by the inherited admin
        links appearing in the navigation — so judge by those. That is also exactly
        what the mode is switched on for.
        """
        if self.visible_admin_links():
            return True
        # No links — but this may be a page on which the navigation is not rendered.
        # Then check the menu, if it opens.
        if not self._open_site_menu():
            return False
        txt = self._visible_menu_text()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        return any(lbl in txt for lbl in AUTHOR_MODE_ON_LABELS)

    def set_author_mode(self, on: bool) -> "Nav":
        """Author mode is sticky and lives IN THE SESSION — set it explicitly before any
        check of what a role can see, or the previous test leaks into the current one.

        ⛔ Do not take the item as `get_by_text(...).first`: the same text sits hidden in
        the DOM, Playwright waits 30 seconds for it to become visible and fails on the
        timeout — and that looks like "toggle not found". Take the first VISIBLE one.
        """
        if self.author_mode_is_on() == on:
            return self
        if not self._open_site_menu():
            raise AssertionError("the header has no 'Site' menu — author mode cannot be switched")
        self.page.wait_for_timeout(700)
        wanted = AUTHOR_MODE_OFF_LABELS if on else AUTHOR_MODE_ON_LABELS
        clicked = self.page.evaluate(
            """(labels) => {
                 const el=[...document.querySelectorAll('a,button,span')]
                   .filter(e=>e.offsetParent)
                   .find(e=>labels.some(l=>e.innerText.trim().startsWith(l)));
                 if(!el) return false;
                 el.click(); return true;
               }""",
            list(wanted),
        )
        if not clicked:
            seen = [x for x in self._visible_menu_text().splitlines() if x.strip()][:14]
            raise AssertionError(
                f"the open 'Site' menu has no visible item {wanted}. "
                f"Visible: {seen}. If the user does have the Author role, the toggle's "
                "caption has changed — update AUTHOR_MODE_*_LABELS"
            )
        self.page.wait_for_timeout(3000)
        self.settle()
        return self
