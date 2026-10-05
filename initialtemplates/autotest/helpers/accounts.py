"""Test users — created by the suite itself, as the author account, for exactly the role groups a scenario names.

A business process is performed by PEOPLE in ROLES, and how many there are is the PRD's business, not the
harness's: one flow has a single clerk, the next a requester, two approvers on different levels, a warehouse
keeper and someone who must NOT see the case at all — and some have no second person whatsoever. So the suite has
no fixed cast. A scenario asks for the people it needs and the suite makes them, through the application, signed
in as the author account from .env:

    clerk = accounts.user("Clerk")                      # a user holding exactly the Clerk role group
    boss  = accounts.user("Approver", label="level-2")  # a second, DIFFERENT person in the same role
    page  = accounts.page(clerk)                        # signed in, in a browser of its own

(`as_user("Clerk")` in conftest does both in one call and sets the file's LOCALE.)

What the platform guarantees and this module relies on:
* an author may set the password of a user they CREATE, and a user created with a password gets no invitation;
* an address on a reserved name (RFC 2606 / 6761 — the suite uses `@autotest.invalid`) receives no mail at all,
  ever, and is created WITH a password or not at all. Notification rules firing for test users cost nothing;
* re-creating an address the organization already knows only re-adds that user to the project and keeps its OLD
  password — so every run uses addresses of its own (the run id is in each one), never a fixed list.

Every test user signs in with the SAME password as the author account the run starts with (AUTH_PASSWORD in
test/.env): it already satisfies whatever password policy the realm enforces, and a person who wants to look at
what a test user saw signs in with the password they already know — nothing new to store or hand over.

Every user is named so a person scanning the user list knows what it is — first name `zz-at`, last name
`<label>-<run>-<n>` — and the run's roster (addresses, role groups) is written to test-results/test-users.json
(no passwords: each one is AUTH_PASSWORD). The users are removed from the project when the session ends, which
also frees the project's user quota — unless KEEP_TEST_USERS=1 keeps them for a person to sign in and look.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

from helpers.env import CONFIG

DOMAIN = "autotest.invalid"
FIRST_NAME = "zz-at"


@dataclass(frozen=True)
class TestAccount:
    __test__ = False                          # a value, not a pytest test class

    label: str
    email: str
    first: str
    last: str
    role_groups: tuple
    password: str = field(repr=False)

    @property
    def name(self) -> str:
        """What the platform's user list shows for this user."""
        return f"{self.first} {self.last}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24] or "user"


class TestAccounts:
    """The session's test users: created on first request, signed in on demand, removed at the end."""

    __test__ = False                          # not a pytest test class, whatever its name says

    def __init__(self, browser, author_context, feedback=None):
        self.browser = browser
        self.author_context = author_context
        self.feedback = feedback
        self.run = time.strftime("%m%d%H%M") + secrets.token_hex(2)
        self._users: dict = {}
        self._pages: dict = {}
        self._admin = None

    # ---------- users ----------
    def user(self, *role_groups: str, label: str | None = None) -> TestAccount:
        """The test user holding exactly `role_groups` — created on the first request, the same one after it.

        Two different people in the same role (four eyes, a second approver) are two labels.
        """
        if not role_groups:
            raise ValueError("name the role groups the user holds — a user with none can see nothing")
        label = _slug(label or "-".join(role_groups))
        key = (tuple(sorted(role_groups)), label)
        if key not in self._users:
            n = len(self._users) + 1
            last = f"{label}-{self.run}-{n}"
            account = TestAccount(
                label=label,
                email=f"{FIRST_NAME}-{last}@{DOMAIN}",
                first=FIRST_NAME,
                last=last,
                role_groups=tuple(role_groups),
                password=CONFIG.auth_password,
            )
            # Registered BEFORE it is created: if creating it fails half-way (the user exists, the check after it
            # did not pass), the end of the session must still find it and remove it — seen live.
            self._users[key] = account
            self._write_roster()
            with self._users_screen() as users:
                users.create_user(account.first, account.last, account.email, list(role_groups),
                                  password=account.password)
        return self._users[key]

    def set_role_groups(self, account: TestAccount, *role_groups: str) -> None:
        """Change what a test user holds — for the scenarios where access is granted or taken away mid-flow.

        The user's open session learns it within seconds (the platform re-reads role groups periodically); re-open
        the page before asserting what it shows."""
        with self._users_screen() as users:
            users.set_role_groups(account.last, list(role_groups))

    # ---------- signing in ----------
    def page(self, account: TestAccount, locale: str | None = None):
        """A page signed in as `account`, in a browser context of its own, in `locale` (default DEFAULT_LOCALE).

        ⛔ Its own context: session, language and author mode live per user and per session, so sharing the author's
        page would make each identity inherit the other's state.
        """
        from pages.login_page import LoginPage

        pg = self._pages.get(account.email)
        if pg is None or pg.is_closed():
            ctx = self.browser.new_context(
                viewport={"width": 1600, "height": 1000},
                locale=(locale or CONFIG.default_locale).replace("_", "-"),
                ignore_https_errors=True,
            )
            ctx.set_default_timeout(CONFIG.timeout_ms)
            if self.feedback is not None:
                self.feedback.install(ctx)
            pg = ctx.new_page()
            LoginPage(pg).login(account.email, account.password,
                                who=f"the test user {account.name} ({', '.join(account.role_groups)})")
            self._pages[account.email] = pg
        LoginPage(pg).switch_locale(locale or CONFIG.default_locale)
        return pg

    # ---------- the end of the session ----------
    def close(self) -> list[str]:
        """Close every test user's browser and remove the users from the project (unless KEEP_TEST_USERS=1).
        Returns what is left in the project."""
        for pg in self._pages.values():
            try:
                pg.context.close()
            except Exception:
                pass
        self._pages.clear()
        left = []
        if CONFIG.keep_test_users:
            return [a.name for a in self._users.values()]
        if self._users:
            try:
                with self._users_screen() as users:
                    for account in self._users.values():
                        try:
                            if users.has_user(account.last) and not users.delete_user(account.last):
                                left.append(account.name)
                        except Exception:
                            left.append(account.name)
            except Exception:
                left = [a.name for a in self._users.values()]
        if self._admin is not None:
            try:
                self._admin.close()
            except Exception:
                pass
        return left

    # ---------- the roster ----------
    def _write_roster(self) -> None:
        """test-results/test-users.json: who this run created — to sign in as one and look (the password is
        AUTH_PASSWORD), or to find a leftover. Git-ignored with the rest of test-results/."""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test-results",
                            "test-users.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        roster = [{k: v for k, v in asdict(a).items() if k != "password"} for a in self._users.values()]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"run": self.run, "signs_in_with": "AUTH_PASSWORD (test/.env)", "users": roster}, fh,
                      ensure_ascii=False, indent=2)

    # ---------- the author's own tab ----------
    @contextmanager
    def _users_screen(self):
        """The users screen, in a tab of the author's session of its own — a test's page is never navigated away.

        It needs author mode, which the platform keeps per USER: it is switched on for the visit and back off
        afterwards if it was off, so a test that counts the navigation's links does not find the admin ones.
        """
        from pages.nav import Nav
        from pages.users_page import UsersPage

        if self._admin is None or self._admin.is_closed():
            self._admin = self.author_context.new_page()
        nav = Nav(self._admin)
        was_on = nav.author_mode_is_on()
        if not was_on:
            nav.set_author_mode(True)
        try:
            yield UsersPage(self._admin).open()
        finally:
            if not was_on:
                nav.set_author_mode(False)
