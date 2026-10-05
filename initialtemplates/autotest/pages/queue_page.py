"""A workflow work queue (`process.table.pluin`).

Two defects found in live testing shaped this object, and both are asserted here so a
regression is caught rather than described:

* the queue listed tasks with EVERY data column empty — the start rule published its
  document with the context and the attrs at the ROOT, where unknown keys are dropped;
* pressing a task action landed on a blank `*-landing` page (missing landing plugin),
  and later on an HTTP 500 once the landing forwarded.
"""
from __future__ import annotations

from helpers.env import CONFIG
from pages.base_page import BasePage


class QueuePage(BasePage):
    def __init__(self, page, path: str):
        super().__init__(page)
        self.path = path

    def open(self) -> "QueuePage":
        self.goto(self.path)
        return self

    def task_count(self) -> int:
        return self.page.evaluate(
            """() => {
                 const ts=[...document.querySelectorAll('table')];
                 if(!ts.length) return 0;
                 ts.sort((a,b)=>b.innerText.length-a.innerText.length);
                 return ts[0].querySelectorAll('tbody tr').length;
               }"""
        )

    def rows_have_data(self) -> bool:
        """True when at least one non-ACTIONS cell carries text.

        A queue whose rows are all blank is the first defect above: the operator cannot
        tell one case from another.
        """
        rows = self.grid_rows()
        if not rows:
            return False
        return any(any(c.strip() for c in row[1:]) for row in rows)

    def open_task_actions(self, row_index: int = 0) -> bool:
        """Open the action menu of a queue row.

        ⛔ `…locator("button, a").last` picks an INVISIBLE element: every row has its own
        collapsed menu, `.last` lands on one of its items, and Playwright waits the full
        30 seconds for it to become visible and fails on the timeout — "the page is not
        responding" about a page that works. Click the VISIBLE toggle, and only in its
        own row.
        """
        ok = self.page.evaluate(
            """(i) => {
                 const ts=[...document.querySelectorAll('table')]
                          .sort((a,b)=>b.innerText.length-a.innerText.length);
                 if(!ts.length) return false;
                 const tr=[...ts[0].querySelectorAll('tbody tr')][i];
                 if(!tr) return false;
                 const td=tr.querySelector('td');
                 if(!td) return false;
                 const el=[...td.querySelectorAll('button,a')].find(e=>e.offsetParent!==null);
                 if(!el) return false;
                 el.click(); return true;
               }""",
            row_index,
        )
        self.page.wait_for_timeout(800)
        return bool(ok)
