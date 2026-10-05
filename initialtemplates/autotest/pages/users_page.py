"""User management (`/users`) and role groups (`/roles`).

⚠️ The Create-User form has NO password field: the platform provisions the account and
the person sets their own secret out of band.  So an autotest can create a user and
assign role groups, but it CANNOT sign in as that user.

That is why persona/permission testing re-assigns role groups on the SIGNED-IN author
account instead, and why `AuthorRoleGuard` exists: removing the Author group from the
only author would leave nobody able to grant roles back.
"""
from __future__ import annotations

from helpers.env import CONFIG
from pages.base_page import BasePage

AUTHOR_GROUP = "Author"


class UsersPage(BasePage):
    def open(self) -> "UsersPage":
        self.goto("users")
        return self

    def user_rows(self) -> list[list[str]]:
        return self.grid_rows()

    def role_groups_of(self, name_fragment: str) -> list[str]:
        """The user's role groups — from the column found BY ITS HEADER, not from the last cell.

        ⛔ `row[-1]` is a bet that the groups come last. As soon as an actions column or a
        date ends up further right, the method returns an empty list, and the test reports
        "the user did not get the group" about a user who has it.
        """
        head = self.page.evaluate(
            """() => {
                 const ts=[...document.querySelectorAll('table')]
                          .sort((a,b)=>b.innerText.length-a.innerText.length);
                 return ts.length ? [...ts[0].querySelectorAll('thead th, thead td')]
                                     .map(h=>h.innerText.trim()) : [];
               }"""
        )
        # Fragments of the role-groups column header as the platform captions it (English,
        # Russian); add the fragment for any other language a project runs the UI in.
        idx = next((i for i, h in enumerate(head)
                    if any(w in h.lower() for w in ("role group", "ролев", "групп", "group"))), -1)
        for row in self.grid_rows():
            if not any(name_fragment.lower() in c.lower() for c in row):
                continue
            cell = row[idx] if 0 <= idx < len(row) else row[-1]
            return [g.strip() for g in cell.replace(";", ",").split(",") if g.strip()]
        return []

    def create_user(self, first: str, last: str, email: str, groups: list[str]) -> "UsersPage":
        before = len(self.grid_rows())
        # the platform's own captions of the create-user button (Russian, English)
        for name in ("Создать нового пользователя", "Create new user"):
            b = self.page.get_by_role("button", name=name, exact=False)
            if b.count():
                b.first.click()
                break
        else:
            raise AssertionError("Create-user button not found")
        self.page.wait_for_timeout(1500)
        # ⛔ Fill the fields BY id, not through `get_by_label`: the users screen is a
        # platform screen, its labels are not tied to their fields by a `for` attribute,
        # and `get_by_label` either finds no field or lands on the wrong one. "Save" then
        # submits an empty form, the platform silently creates nothing, and the test
        # reports that the user did not get the role group. Verified with a probe: filled
        # by id, the user is created.
        filled = self.page.evaluate(
            """([first, last, email]) => {
                 const set=(id, v)=>{const e=document.getElementById(id);
                     if(!e) return false;
                     e.value=v;
                     ['input','change'].forEach(n=>e.dispatchEvent(new Event(n,{bubbles:true})));
                     return true;};
                 return {firstName: set('firstName', first),
                         lastName: set('lastName', last),
                         email: set('email', email)};
               }""",
            [first, last, email],
        )
        assert all(filled.values()), (
            f"fields not found in the create-user form: {filled}. Visible fields: "
            + str(self.page.evaluate(
                """() => [...document.querySelectorAll('input,select')]
                        .filter(e=>e.offsetParent!==null).map(e=>e.id || e.name).slice(0,12)"""))
        )
        # ⛔ Pick the role group BY ITS CAPTION: the options of this list have the `value`
        # "0"…"9", and Playwright's `select_option(["<role group>"])` matches exactly the value.
        # role groups: the same list, found by id; match the option's caption, not its value ("0"…"9")
        picked = self.page.evaluate(
            """(groups) => {
                 const s=document.getElementById('roleGroups')
                      || [...document.querySelectorAll('select')].pop();
                 if(!s) return [];
                 const out=[];
                 for (const o of [...s.options]) {
                   if(groups.some(g => o.text.trim() === g)) { o.selected=true; out.push(o.text.trim()); }
                 }
                 ['input','change'].forEach(n=>s.dispatchEvent(new Event(n,{bubbles:true})));
                 return out;
               }""",
            groups,
        )
        assert sorted(picked) == sorted(groups), (
            f"role groups not found in the list: {set(groups) - set(picked)}; selected: {picked}"
        )
        # ⛔ Let Wicket catch up: it re-renders the form on the field events, and a "Save"
        # click in the same millisecond submits it before the values are registered. A
        # probe with the pause created the user; without the pause it did not.
        self.page.wait_for_timeout(1200)
        # ⛔ Look for the save button among ANY clickable elements, and VERIFY that it was
        # clicked. The users screen is a platform screen and was found NOT localized (a
        # platform defect), so its captions here are English, and the element may be a
        # `button`, an `a` or an `input[type=submit]`. An earlier version looked only for
        # a link with the Russian caption: it found none, silently clicked nothing — and
        # the test reported that the user did not get the role group, when the user had
        # not been created at all.
        # `want` holds the save captions, lower-cased (English, Russian) — platform data;
        # add the caption for any other language a project runs the UI in.
        clicked = self.page.evaluate(
            """() => {
                 const want=['save','сохранить','сохранять','submit','create','ok'];
                 const dlgs=[...document.querySelectorAll('.modal-content,[role=dialog],.modal-dialog')]
                            .filter(e=>e.offsetParent!==null);
                 const scope=dlgs.length ? dlgs[dlgs.length-1] : document;
                 const els=[...scope.querySelectorAll('a,button,input[type=submit]')]
                           .filter(e=>e.offsetParent!==null);
                 for (const e of els) {
                   const t=((e.innerText||e.value||'')+'').trim().toLowerCase();
                   if(t && want.some(w=>t===w || t.startsWith(w))) { e.click(); return t; }
                 }
                 return '';
               }"""
        )
        assert clicked, (
            "the create-user form has no save button; visible buttons: "
            + str(self.page.evaluate(
                """() => [...document.querySelectorAll('a,button,input[type=submit]')]
                        .filter(e=>e.offsetParent!==null)
                        .map(e=>((e.innerText||e.value||'')+'').trim()).filter(Boolean).slice(0,20)"""))
        )
        # ⛔ Capture both the platform's message and the state of the DIALOG: if the dialog
        # stayed open, it holds the built-in validation ("Field … is required"), and
        # without it the failure below states only the fact "not created", explaining
        # nothing. (When no dialog is open, the JS returns '(dialog closed)'.)
        said = self.toast_text(timeout_ms=5000)
        after_save = self.page.evaluate(
            r"""() => {
                 const d=[...document.querySelectorAll('.modal-content,[role=dialog],.modal-dialog')]
                          .filter(e=>e.offsetParent!==null).pop();
                 return d ? (d.innerText||'').replace(/\s+/g,' ').slice(0, 300) : '(dialog closed)';
               }"""
        )
        self.settle()
        # ⛔ And check right away that the user APPEARED: "saved" without a row in the list
        # is not a creation, it is silence. Do not check by e-mail: the list has NO e-mail
        # column (only NAME, STATUS, ROLE GROUPS), and an earlier version declared a
        # created user not created because it searched for text that never shows up on
        # the screen.
        self.open()
        rows = self.grid_rows()
        assert len(rows) > before, (
            f"after saving, the list still has {len(rows)} rows — the user was not "
            f"created. The platform said: {said!r}; the form after 'Save': {after_save!r}"
        )
        mine = [r for r in rows if any(first.lower() in (c or "").lower() for c in r)]
        assert mine, f"no user named {first!r} in the list of {len(rows)} rows"
        return self


class AuthorRoleGuard:
    """⛔ Never strip the Author group from the account the suite signs in with.

    Author is the only role that can grant roles.  Removing it from the only author
    locks the project out of its own administration, and no test is worth that.
    """

    @staticmethod
    def assert_safe(groups: list[str]) -> None:
        if AUTHOR_GROUP not in groups:
            raise AssertionError(
                "Refusing to apply a role set without 'Author' to the signed-in account: "
                "Author is the only group that can grant roles, and dropping it would "
                "leave nobody able to restore access."
            )
