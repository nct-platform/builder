"""User management (`/users`) — the screen the suite creates its test users on, as the author account.

Every scenario that a person performs is performed by a user the suite CREATED for it, holding exactly the role
groups the PRD gives that person — never by the author account, which holds Author and sees what no ordinary
role sees (a rule-started case even grants the author role a row of its own). `helpers/accounts.py` drives this
page; tests ask it for users, they do not call this page directly.

What the platform guarantees and this page relies on:

* An AUTHOR may set the password of a user they are CREATING ("Set password" in the dialog); a user created with
  a password gets no invitation — it can sign in at once.
* An address on a reserved name that can never receive mail (RFC 2606 / 6761: `*.invalid`, `*.test`,
  `*.example`, `example.com` …) is created WITH a password or not at all, and no mail is ever sent to it — so a
  notification rule firing for a test user costs nothing. The suite's users live on `@autotest.invalid`.

⛔ Located by STRUCTURE, never by caption: this is a platform screen rendered in whatever language the session is
in, and the project may run in a language none of us listed. The create button carries the `pe-7s-plus` icon, the
dialog's save the `pe-7s-diskette` one, a row's delete the `pe-7s-trash` one, the confirmation's yes the
`pe-7s-check` one; the form fields have the ids `firstName`, `lastName`, `email`, `password`, `roleGroups`.
"""
from __future__ import annotations

from helpers.env import CONFIG
from pages.base_page import BasePage

AUTHOR_GROUP = "Author"

_LAST_DIALOG = """() => [...document.querySelectorAll('.modal-content,[role=dialog],.modal-dialog')]
                        .filter(e => e.offsetParent !== null).pop() || null"""


class UsersPage(BasePage):
    def open(self) -> "UsersPage":
        self.goto("users")
        self.page.wait_for_selector("table", timeout=CONFIG.grid_timeout_ms)
        return self

    # ---------- reading ----------
    def user_rows(self) -> list[list[str]]:
        return self.grid_rows()

    def has_user(self, name_fragment: str) -> bool:
        """Is there a VISIBLE row showing `name_fragment`? (A failed dialog leaves its hidden error text behind in
        the table's body — seen live — and that text contains what was typed.)"""
        return bool(self.page.evaluate(
            """(name) => [...document.querySelectorAll('tbody tr')].filter(tr => tr.offsetParent !== null)
                 .some(tr => (tr.innerText || '').toLowerCase().includes(name.toLowerCase()))""", name_fragment))

    def role_groups_of(self, name_fragment: str) -> list[str]:
        """The role groups shown in the user's row — the LAST column of the platform's user list (actions, name,
        status, role groups), read from the row the name is in."""
        for row in self.grid_rows():
            if any(name_fragment.lower() in (c or "").lower() for c in row):
                return [g.strip() for g in (row[-1] or "").replace(";", ",").split(",") if g.strip()]
        return []

    # ---------- creating ----------
    def create_user(self, first: str, last: str, email: str, groups: list[str],
                    password: str | None = None) -> "UsersPage":
        """Create a user with the given role groups — with `password`, the user can sign in at once.

        Asserts the user then APPEARS in the list: "saved" without a row is not a creation, it is silence.
        """
        before = len(self.grid_rows())
        self._click_create()
        self.page.wait_for_selector("#firstName", state="visible", timeout=CONFIG.grid_timeout_ms)
        filled = self.page.evaluate(
            """([first, last, email]) => {
                 const set = (id, v) => { const e = document.getElementById(id);
                     if (!e) return false;
                     e.value = v;
                     ['input', 'change'].forEach(n => e.dispatchEvent(new Event(n, {bubbles: true})));
                     return true; };
                 return {firstName: set('firstName', first), lastName: set('lastName', last),
                         email: set('email', email)};
               }""",
            [first, last, email],
        )
        assert all(filled.values()), f"the create-user dialog lacks a field: {filled}"
        if password is not None:
            self._open_password_field()
            self.page.fill("#password", password)
        picked = self.page.evaluate(
            """(groups) => {
                 const s = document.getElementById('roleGroups');
                 if (!s) return null;
                 const out = [];
                 for (const o of [...s.options]) {
                   if (groups.some(g => o.text.trim() === g)) { o.selected = true; out.push(o.text.trim()); }
                 }
                 ['input', 'change'].forEach(n => s.dispatchEvent(new Event(n, {bubbles: true})));
                 return out;
               }""",
            groups,
        )
        assert picked is not None, "the create-user dialog has no role-group list (#roleGroups)"
        missing = set(groups) - set(picked)
        assert not missing, (
            f"role groups {sorted(missing)} are not offered in the create-user dialog — they do not exist in this "
            f"project, or the signed-in account may not grant them (only an author can grant Author). Offered "
            f"and picked: {picked}")
        # ⛔ Let Wicket register the values: it re-renders the form on field events, and a save in the same
        # millisecond submits the form before them.
        self.page.wait_for_timeout(1200)
        self._click_in_dialog("pe-7s-diskette", "save")
        said = self.toast_text(timeout_ms=5000)
        # ⛔ Wait for the dialog to GO, not a single look: the success message arrives while the dialog is still
        # fading out, and one look then reports a created user as refused (seen live).
        still_open = ""
        for _ in range(int(CONFIG.timeout_ms / 500)):
            still_open = self.page.evaluate(
                "() => { const d = (" + _LAST_DIALOG + ")(); "
                "return d ? (d.innerText || '').replace(/\\s+/g, ' ').slice(0, 300) : ''; }")
            if not still_open:
                break
            self.page.wait_for_timeout(500)
        assert not still_open, (
            f"the create-user dialog stayed open — the platform refused the user: {still_open!r} "
            f"(message: {said!r})")
        self.open()
        rows = self.grid_rows()
        assert len(rows) > before and self.has_user(last), (
            f"after saving, no user {first} {last} in the list of {len(rows)} rows — the user was not created. "
            f"The platform said: {said!r}")
        return self

    # ---------- changing ----------
    def set_role_groups(self, name_fragment: str, groups: list[str]) -> "UsersPage":
        """Give the user in the row showing `name_fragment` exactly `groups` (the others are taken away).

        For TEST users only: the author account's own groups are never edited (AuthorRoleGuard).
        """
        clicked = self.page.evaluate(
            """(name) => {
                 const row = [...document.querySelectorAll('tbody tr')].filter(tr => tr.offsetParent !== null)
                     .find(tr => (tr.innerText || '').toLowerCase().includes(name.toLowerCase()));
                 const icon = row && row.querySelector('i.pe-7s-edit');
                 const btn = icon && icon.closest('button,a');
                 if (!btn) return false;
                 btn.click(); return true;
               }""",
            name_fragment,
        )
        assert clicked, f"no user row shows {name_fragment!r} (or it has no edit button)"
        self.page.wait_for_selector("#roleGroups", state="attached", timeout=CONFIG.grid_timeout_ms)
        picked = self.page.evaluate(
            """(groups) => {
                 const s = document.getElementById('roleGroups');
                 const out = [];
                 for (const o of [...s.options]) {
                   if (o.disabled) continue;
                   o.selected = groups.some(g => o.text.trim() === g);
                   if (o.selected) out.push(o.text.trim());
                 }
                 ['input', 'change'].forEach(n => s.dispatchEvent(new Event(n, {bubbles: true})));
                 return out;
               }""",
            groups,
        )
        missing = set(groups) - set(picked)
        assert not missing, f"role groups {sorted(missing)} are not offered in the user dialog; picked: {picked}"
        self.page.wait_for_timeout(1200)
        self._click_in_dialog("pe-7s-diskette", "save")
        self.settle()
        self.open()
        shown = set(self.role_groups_of(name_fragment))
        assert shown == set(groups), f"after saving, the user's row shows the role groups {sorted(shown)}, " \
                                     f"expected {sorted(groups)}"
        return self

    # ---------- deleting ----------
    def delete_user(self, name_fragment: str) -> bool:
        """Delete the user whose row shows `name_fragment` (and confirm). False when there is no such row."""
        clicked = self.page.evaluate(
            """(name) => {
                 const row = [...document.querySelectorAll('tbody tr')].filter(tr => tr.offsetParent !== null)
                     .find(tr => (tr.innerText || '').toLowerCase().includes(name.toLowerCase()));
                 if (!row) return false;
                 const icon = row.querySelector('i.pe-7s-trash');
                 const btn = icon && icon.closest('button,a');
                 if (!btn) return false;
                 btn.click(); return true;
               }""",
            name_fragment,
        )
        if not clicked:
            return False
        self.page.wait_for_timeout(800)
        self._click_in_dialog("pe-7s-check", "confirm the deletion")
        self.settle()
        self.open()
        return not self.has_user(name_fragment)

    # ---------- the parts located by structure ----------
    def _click_create(self) -> None:
        clicked = self.page.evaluate(
            """() => {
                 const shown = i => { const b = i.closest('a,button'); return b && b.offsetParent !== null; };
                 // the page's own breadcrumb buttons first, then anywhere on the page
                 const icon = [...document.querySelectorAll('.app-page-title i.pe-7s-plus')].find(shown)
                     || [...document.querySelectorAll('i.pe-7s-plus')].find(shown);
                 if (!icon) return false;
                 icon.closest('a,button').click(); return true;
               }""")
        assert clicked, "the users page shows no create button (the `pe-7s-plus` breadcrumb button) — is the " \
                        "signed-in account an author, and is author mode on?"

    def _open_password_field(self) -> None:
        """Reveal the password field: the dialog offers it behind a link between the e-mail and the role groups."""
        if self.page.locator("#password").count() and self.page.locator("#password").is_visible():
            return
        clicked = self.page.evaluate(
            """() => {
                 const email = document.getElementById('email'), groups = document.getElementById('roleGroups');
                 if (!email) return false;
                 const form = email.closest('form') || document;
                 const link = [...form.querySelectorAll('a')].find(a => a.offsetParent !== null
                     && (email.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)
                     && (!groups || (a.compareDocumentPosition(groups) & Node.DOCUMENT_POSITION_FOLLOWING)));
                 if (!link) return false;
                 link.click(); return true;
               }""")
        assert clicked, ("the create-user dialog offers no way to set a password — the signed-in account is not an "
                         "author of this project (only an author may set the password of a user they create)")
        self.page.wait_for_selector("#password", state="visible", timeout=CONFIG.grid_timeout_ms)

    def _click_in_dialog(self, icon_class: str, what: str) -> None:
        clicked = self.page.evaluate(
            """(icon) => {
                 const dialogs = [...document.querySelectorAll('.modal-content,[role=dialog],.modal-dialog')]
                     .filter(e => e.offsetParent !== null);
                 const scope = dialogs.length ? dialogs[dialogs.length - 1] : document;
                 const i = scope.querySelector('i.' + icon);
                 const target = i && i.closest('a,button,input');
                 if (!target) return false;
                 target.click(); return true;
               }""",
            icon_class,
        )
        assert clicked, f"no button to {what} in the open dialog (looked for the `{icon_class}` icon)"


class AuthorRoleGuard:
    """⛔ Never strip the Author group from the account the suite signs in with.

    Author is the only role that can grant roles. The suite never edits the author account's own role groups —
    it creates users for the roles — so this guards against a test that tries anyway.
    """

    @staticmethod
    def assert_safe(groups: list[str]) -> None:
        if AUTHOR_GROUP not in groups:
            raise AssertionError(
                "Refusing to apply a role set without 'Author' to the signed-in account: "
                "Author is the only group that can grant roles, and dropping it would "
                "leave nobody able to restore access."
            )
