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
    # The filter button's caption in all three locales — the platform's own captions;
    # extend the tuple if a project runs the UI in another language. ⛔ This used to hold
    # only the Armenian «Ֆիլտր», with a comment saying "this build does not localize the
    # button" — that stopped being true once the platform localized it, and the fallback
    # selector "the first button of the form" started pressing the neighbouring button.
    # From the outside the test looked like a product defect — "the filter does not
    # narrow the results" — while the filter worked and the wrong button was pressed.
    FILTER_CAPTIONS = ("Фильтр", "Filter", "Ֆիլտր")

    def filter_by(self, label: str, value: str) -> "RegisterPage":
        """Type `value` into the filter field with the visible label `label`, then submit the form."""
        field = self.page.get_by_label(label, exact=False)
        if not field.count():
            field = self.page.locator(f"xpath=//*[contains(text(),'{label}')]/following::input[1]")
        field.first.fill(value)
        self.submit_filter()
        return self

    def submit_filter(self) -> "RegisterPage":
        clicked = self.page.evaluate(
            """(caps) => {
                 const els=[...document.querySelectorAll('a,button')]
                   .filter(e=>e.offsetParent && caps.includes(e.innerText.trim()));
                 if(!els.length) return false;
                 els[0].click(); return true;
               }""",
            list(self.FILTER_CAPTIONS),
        )
        if not clicked:
            btn = self.page.locator("form button[type='submit'], form a.btn").first
            btn.click()
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
        return self

    # ---------- create / edit ----------
    def click_create(self) -> "RegisterPage":
        # the platform's own "Create" caption in each UI language
        for name in ("Создать", "Create", "Ստեղծել"):
            b = self.page.get_by_role("button", name=name, exact=False)
            if b.count():
                b.first.click()
                self.page.wait_for_timeout(1500)
                return self
        raise AssertionError("Create button not found")

    def save_modal(self) -> "RegisterPage":
        # the platform's own "Save" captions in each UI language (two Russian spellings)
        for name in ("Сохранить", "Сохранять", "Save", "Պահպանել"):
            b = self.page.get_by_role("link", name=name, exact=False)
            if b.count():
                b.first.click()
                self.settle()
                return self
        raise AssertionError("Save button not found in modal")

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
