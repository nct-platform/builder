"""A CRUD register: filter bar, data grid, row actions, edit modal."""
from __future__ import annotations

from helpers.env import CONFIG
from pages.base_page import BasePage


class RegisterPage(BasePage):
    """`path` is the register's alias under <root>/<realm>/<client>."""

    def __init__(self, page, path: str):
        super().__init__(page)
        self.path = path

    def open(self) -> "RegisterPage":
        self.goto(self.path)
        return self

    # ---------- filtering ----------
    # The filter button's caption is the PROJECT's (the filter submit button's own setting, per locale) — so it is
    # found through the form of the field just filled, or by the caption the builder recorded in
    # helpers/locales.py. These platform defaults are only the last resort. ⛔ "The first button of the form" once
    # pressed the neighbouring button, and the test reported "the filter does not narrow" about a filter that
    # worked.
    FILTER_CAPTIONS = ("Фильтр", "Filter", "Ֆիլտր")

    def filter_by(self, label: str, value: str, button: str | None = None) -> "RegisterPage":
        """Type `value` into the filter field with the visible label `label`, then submit THAT field's form."""
        field = self.page.get_by_label(label, exact=False)
        if not field.count():
            field = self.page.locator(f"xpath=//*[contains(text(),'{label}')]/following::input[1]")
        field.first.fill(value)
        own_submit = field.first.locator("xpath=ancestor::form[1]//button[@type='submit']")
        if button is None and own_submit.count() == 1 and own_submit.first.is_visible():
            own_submit.first.click()
            self._wait_rerender()
            return self
        self.submit_filter(button)
        return self

    def submit_filter(self, caption: str | None = None) -> "RegisterPage":
        """Press the filter button — by `caption` (the project's, from helpers/locales.py) when given."""
        captions = [caption] if caption else list(self.FILTER_CAPTIONS)
        clicked = self.page.evaluate(
            """(caps) => {
                 const els=[...document.querySelectorAll('a,button')]
                   .filter(e=>e.offsetParent && caps.includes(e.innerText.trim()));
                 if(!els.length) return false;
                 els[0].click(); return true;
               }""",
            captions,
        )
        if not clicked:
            if caption:
                raise AssertionError(f"no visible filter button {caption!r}")
            btn = self.page.locator("form button[type='submit']").first
            btn.click()
        self._wait_rerender()
        return self

    def _wait_rerender(self) -> None:
        # ⛔ Wait for the RE-RENDER, not a fixed pause: Wicket answers with AJAX, and on a
        # loaded server the 1200 ms of `settle()` sometimes run out before the response.
        self.page.wait_for_timeout(1200)
        try:
            self.page.wait_for_function(
                "() => !document.querySelector('.wicket-ajax-indicator[style*=\"visible\"]')",
                timeout=8000)
        except Exception:
            pass
        self.settle()

    # ---------- create / edit ----------
    def click_create(self, caption: str | None = None) -> "RegisterPage":
        """Press the register's create action — by ITS caption (the project's action, from helpers/locales.py),
        falling back to the platform's default captions only when none is given."""
        for name in ([caption] if caption else ["Создать", "Create", "Ստեղծել"]):
            for role in ("button", "link"):
                b = self.page.get_by_role(role, name=name, exact=False)
                if b.count():
                    b.first.click()
                    self.page.wait_for_timeout(1500)
                    return self
        raise AssertionError(f"create action {caption or '(platform default caption)'!r} not found")

    def save_modal(self) -> "RegisterPage":
        """Press the open dialog's save — the button with the `pe-7s-diskette` icon, in any language."""
        clicked = self.page.evaluate(
            """() => { const d = [...document.querySelectorAll('.modal-content,[role=dialog],.modal-dialog')]
                         .filter(e => e.offsetParent !== null).pop();
                       const i = d && d.querySelector('i.pe-7s-diskette');
                       const b = i && i.closest('a,button');
                       if (!b) return false; b.click(); return true; }""")
        if not clicked:
            for name in ("Сохранить", "Сохранять", "Save", "Պահպանել"):
                b = self.page.get_by_role("link", name=name, exact=False)
                if b.count():
                    b.first.click()
                    break
            else:
                raise AssertionError("the open dialog has no save button")
        self.settle()
        return self

    def column_values(self, header: str) -> list[str]:
        """Every cell under the column whose header matches `header`."""
        return self.page.evaluate(
            """(h) => {
                 const ts=[...document.querySelectorAll('table')];
                 if(!ts.length) return [];
                 ts.sort((a,b)=>b.innerText.length-a.innerText.length);
                 const t=ts[0];
                 const hs=[...t.querySelectorAll('thead th')].map(x=>x.innerText.trim().toUpperCase());
                 const i=hs.findIndex(x=>x.includes(h.toUpperCase()));
                 if(i<0) return [];
                 return [...t.querySelectorAll('tbody tr')]
                   .map(tr=>tr.querySelectorAll('td')[i])
                   .filter(Boolean).map(td=>td.innerText.trim());
               }""",
            header,
        )
