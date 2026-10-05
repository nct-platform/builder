"""Custom HTML Studio components — the screens the builder wrote by hand, tested against the PRD like any other.

A studio component (doc 24) is the builder's own HTML/CSS/JS, mounted by the platform's small runtime after a full
page render AND after every ajax re-render, fed by `ctx.callRule(...)` / `ctx.callBl(...)`. No offline gate runs
that JavaScript, so everything about it is proven here or nowhere. Its failures are quiet, which is why this page
object exists:

* ⛔ **An empty wrapper is the usual failure, not an error page.** A component whose document was dropped, whose
  script threw before rendering, or whose rule name does not resolve renders an invisible empty box — often with a
  clean console. `wait_mounted()` therefore waits for what the MOUNTED component shows — a text the PRD names
  (`text=`) or an element only real data produces (`ready=`, e.g. "tbody tr") — inside the component's own root,
  and fails with what it found. "Some child element exists" is not mounted: a spinner is a child element.
* ⛔ **A re-mounted component can fire one click N times.** Each ajax re-render mounts a new instance; a handler
  bound to a wrapper id instead of the instance fires once per mount that is still alive. Assert the EFFECT of
  one click (one new row, one counter step, one toast) — `count_effect()` helps — never only that a click worked.
* **The rule bridge rejects on failure.** `await ctx.callRule(...)` rejects instead of resolving with a wrong
  value, so a broken rule shows up as a page error or the component's own error state — `problems()` collects
  page errors, console ERRORS and failed requests seen since the component was opened (console warnings are kept
  apart in `console_warnings()`, and an aborted request — a navigation or a re-render cancelling it — is not a
  failure). If the platform itself logs an error that has nothing to do with the component, pass its pattern to
  `problems(ignore=...)` and say in the test why it is not the component's.
* **Locale, theme and role are the component's job too.** The mount payload carries no user, locale or skin; a
  component that formats or hides things per role/locale does it through its rule. Run its scenarios in every
  locale the project declares and as every role the PRD names.

`root` is a CSS selector for the component's OWN root element — the builder authored that markup, so it knows a
stable hook (an id or a dedicated class on the top element of the component's main document). Never locate a
component by the platform's generated wrapper ids: they change on every mount.

The page is shared by the whole suite, so the listeners must go when the test is done — use it as a context
manager:

    with StudioComponent(page, ".kpi-board") as board:        # listening starts here, so a failing
        board.open("dashboard", ready=".kpi-board__value")      # open() still detaches on the way out
        board.wait_text(r"Open orders")
        assert not board.problems()
"""
from __future__ import annotations

import re
import time

from helpers.env import CONFIG
from pages.base_page import BasePage


class StudioComponent(BasePage):
    def __init__(self, page, root: str):
        super().__init__(page)
        self.root = root
        self._problems: list[str] = []
        self._warnings: list[str] = []
        self._handlers = (
            ("console", self._on_console),
            ("pageerror", self._on_pageerror),
            ("requestfailed", self._on_requestfailed),
        )
        for event, handler in self._handlers:
            page.on(event, handler)

    # ---------- what went wrong, quietly ----------
    def _on_console(self, msg):
        if msg.type == "error":
            self._problems.append(f"console.error: {msg.text[:300]}")
        elif msg.type == "warning":
            self._warnings.append(f"console.warning: {msg.text[:300]}")

    def _on_pageerror(self, exc):
        self._problems.append(f"page error: {str(exc)[:300]}")

    def _on_requestfailed(self, request):
        failure = request.failure or ""
        if "ERR_ABORTED" in failure or "NS_BINDING_ABORTED" in failure:
            return                          # cancelled by a navigation or a re-render — not a failure
        self._problems.append(f"request failed: {request.method} {request.url[:200]} ({failure})")

    def problems(self, ignore: tuple[str, ...] = ()) -> list[str]:
        """Page errors, console errors and failed requests seen since this object was created — minus the ones
        matching a regex of `ignore` (the platform's own noise, each one justified in the test)."""
        skip = [re.compile(p, re.I) for p in ignore]
        return [p for p in self._problems if not any(rx.search(p) for rx in skip)]

    def console_warnings(self) -> list[str]:
        return list(self._warnings)

    def __enter__(self) -> "StudioComponent":
        return self

    def __exit__(self, *exc) -> None:
        self.detach()

    def detach(self) -> None:
        """Stop listening — call it when the test is done with the component (the page is shared)."""
        for event, handler in self._handlers:
            try:
                self.page.remove_listener(event, handler)
            except Exception:
                pass

    # ---------- mounting ----------
    def open(self, path: str, *, text: str | None = None, ready: str | None = None,
             timeout_ms: int | None = None) -> "StudioComponent":
        self.goto(path)
        return self.wait_mounted(text=text, ready=ready, timeout_ms=timeout_ms)

    def wait_mounted(self, *, text: str | None = None, ready: str | None = None,
                     timeout_ms: int | None = None) -> "StudioComponent":
        """Wait until the component's root is visible AND shows what a mounted component shows: `text` (a regex,
        case-insensitive — a caption or a value the PRD names) and/or `ready` (a CSS selector, relative to the root,
        that only real content produces). One of the two is required."""
        if not text and not ready:
            raise TypeError("wait_mounted needs text= or ready=: say what the MOUNTED component shows — any child "
                            "element is not enough, a spinner is one")
        rx = re.compile(text, re.I) if text else None
        deadline = time.time() + (timeout_ms or CONFIG.grid_timeout_ms) / 1000
        seen = ""
        while time.time() < deadline:
            state = self.page.evaluate(
                """([sel, ready]) => { const r = document.querySelector(sel);
                   if (!r) return {found: false};
                   return {found: true, text: (r.innerText || '').trim(), children: r.children.length,
                           ready: ready ? r.querySelectorAll(ready).length : -1,
                           visible: !!(r.offsetParent || r.getClientRects().length)}; }""", [self.root, ready])
            if state.get("found"):
                seen = (f"root found ({'visible' if state['visible'] else 'NOT visible'}), {state['children']} child "
                        f"elements, {len(state['text'])} chars of text"
                        + (f", {state['ready']} × {ready!r}" if ready else "")
                        + (f"; text: {state['text'][:160]!r}" if text else ""))
                ok_text = rx is None or bool(rx.search(state["text"]))
                ok_ready = not ready or state["ready"] > 0
                if state["visible"] and ok_text and ok_ready:
                    return self
            else:
                seen = "root not in the DOM"
            self.page.wait_for_timeout(400)
        raise AssertionError(
            f"studio component {self.root!r} did not mount (waited for "
            + " and ".join(x for x in (f"text {text!r}" if text else "", f"{ready!r}" if ready else "") if x)
            + f"): {seen}. Problems seen: {self.problems() or 'none'} — an empty wrapper with a clean console "
            "usually means a dropped document, a script that threw before rendering, or a rule name that does not "
            "resolve.")

    # ---------- reading ----------
    def text(self) -> str:
        return self.page.locator(self.root).first.inner_text()

    def wait_text(self, pattern: str, timeout_ms: int | None = None) -> str:
        """Poll until the component's text matches `pattern` (a regex, case-insensitive); return the match."""
        rx = re.compile(pattern, re.I)
        deadline = time.time() + (timeout_ms or CONFIG.grid_timeout_ms) / 1000
        last = ""
        while time.time() < deadline:
            last = self.text()
            m = rx.search(last)
            if m:
                return m.group(0)
            self.page.wait_for_timeout(300)
        raise AssertionError(f"studio component {self.root!r}: no text matching {pattern!r}; "
                             f"it shows {last[:400]!r}; problems: {self.problems() or 'none'}")

    def table_rows(self, table: str = "table") -> list[list[str]]:
        """Visible body rows of a table INSIDE the component (cells as trimmed text)."""
        return self.page.evaluate(
            """([root, table]) => { const r = document.querySelector(root); if (!r) return [];
               const t = r.querySelector(table); if (!t) return [];
               return [...t.querySelectorAll('tbody tr')].filter(tr => tr.offsetParent !== null)
                 .map(tr => [...tr.cells].map(td => (td.innerText || '').trim())); }""", [self.root, table])

    # ---------- acting ----------
    def click(self, text: str, exact: bool = False) -> "StudioComponent":
        """A REAL click (browser input, not a synthetic event) on a visible element inside the component."""
        loc = self.page.locator(self.root).first.get_by_text(text, exact=exact)
        n = loc.count()
        for i in range(n):
            item = loc.nth(i)
            if item.is_visible():
                item.click()
                return self
        raise AssertionError(f"studio component {self.root!r}: no visible element with text {text!r}")

    def count_effect(self, act, measure, quiet_ms: int = 1500, timeout_ms: int | None = None) -> int:
        """How much `measure()` (e.g. lambda: len(self.table_rows())) moved after ONE call of `act()`.

        Use it to prove one click has exactly one effect — a re-mounted component that fires twice moves by two.
        It polls until the value has stopped moving for `quiet_ms` (a second handler's effect arrives a moment
        after the first), or until the timeout when nothing moves at all — then the answer is 0.
        """
        before = measure()
        act()
        deadline = time.time() + (timeout_ms or CONFIG.grid_timeout_ms) / 1000
        last, changed_at = before, None
        while time.time() < deadline:
            self.page.wait_for_timeout(250)
            now = measure()
            if now != last:
                last, changed_at = now, time.time()
            elif changed_at is not None and (time.time() - changed_at) * 1000 >= quiet_ms:
                break
        return last - before
