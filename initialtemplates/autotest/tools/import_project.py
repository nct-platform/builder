"""Imports project.mrjun through the platform's UI — this is what gives the scenario
tests the same data on every run.

Why through the browser: the platform has neither an API nor a CLI for import. The only
way in is Settings → Import/Export. So "reset before the run" is not a call but a short
session of driving the page.

⛔ The import ERASES the tenant's data and restores it from the archive's dump. It runs
only when asked for explicitly: `./start.sh reset`, or this script directly.

    ./.venv/bin/python tools/import_project.py [path-to-mrjun] [--rebuild-structure] [--recreate-integration]

Every switch of the Import dialog is SET, never inherited (doc 00, "The Export and Import dialogs"): they
are defaults of a dialog, not a contract, and a script that only clicks Import imports whatever the
platform happens to default to. Each switch is found by its LABEL, set, and logged; when one that must
change is disabled, or the file does not carry its part ("Not in this file"), the import is cancelled
instead of half-done.

* "Everything" — always ON: the reset brings back every part the archive carries. "Pages, forms and
  rules" and "Database" must be among them (the content and the seed data); "Business logic" too
  whenever the file carries it — it brings the SQL each table actually runs.
* `--rebuild-structure` turns on "Rebuild the table structure from the file" (OFF otherwise). It is
  needed EXACTLY when the SCHEMA in the export changed (a column, a table or an index was added):
  without it the new SQL arrives but the column does not — and the CRUD table fails with
  `column ... does not exist`, although the import reported success. When the schema has not changed,
  leave it off: it drops the tables and builds them again from the file.
* `--recreate-integration` turns on "Recreate them from scratch" under Integration services (OFF
  otherwise) — it tears the project's integration down and builds it again, which adds minutes; a data
  reset never needs it.

⚠️ The import deploys exactly the workflows the archive marks `deployed: true`; one marked
`deployed: false` arrives as a draft, and every work queue on it stays empty until it is deployed (the
BPMN editor, or `nct_workflow_deploy` over MCP).

Returns 0 when the import ran to the end; 1 when the platform reported an error — "Import failed", or
"Imported with warnings" (a part did not land; the reason is printed) — including `Java heap space`,
which happens after a series of imports in a row.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright          # noqa: E402

from helpers.env import CONFIG                            # noqa: E402
from pages.login_page import LoginPage                    # noqa: E402
from pages.nav import Nav                                  # noqa: E402

DEFAULT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "project.mrjun")

# The import unpacks pages, rules, CRUDs, the dump and the workflows — on a live environment
# a mid-sized project took a minute and a half to two; leave a margin, but not an infinite one.
TIMEOUT_S = 420

# The dialog's labels. The platform does not translate them, so they read the same in every UI language.
EVERYTHING = "Everything"
MUST_ARRIVE = ("Pages, forms and rules", "Database")
IF_CARRIED = ("Business logic",)
REBUILD = "Rebuild the table structure from the file"
RECREATE = "Recreate them from scratch"

# Every switch of the dialog with what its label says. Read again after every click: a click repaints the whole
# block, and a box its parent unticked is unticked in the DOM only after that repaint.
_READ_SWITCHES = """() => [...document.querySelectorAll('.naf input[type=checkbox]')].map((c, i) => {
     const box = c.closest('.naf-all, .naf-head, .naf-row');
     let title = '';
     if (box) {
       const head = box.querySelector('.naf-all__title, .naf-head__title, .naf-row__title');
       const first = head && [...head.querySelectorAll('span')]
           .find(s => !s.classList.contains('naf-count') && !s.classList.contains('naf-missing'));
       title = ((first || head || {}).innerText || '').trim();
     }
     const missing = box ? ((box.querySelector('.naf-missing') || {}).innerText || '').trim() : '';
     return {i, title, missing, checked: c.checked, disabled: c.disabled};
   })"""


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def choose_parts(page, rebuild_structure: bool, recreate_integration: bool):
    """Set the open Import dialog's switches for a reset. Returns None when every switch is as it must be, else the
    reason the import must not start."""

    def switches() -> list:
        return page.evaluate(_READ_SWITCHES)

    def find(title: str):
        return next((s for s in switches() if s["title"] == title), None)

    def want(title: str, value: bool) -> str:
        """Bring the switch to the required state: "ok", "missing", "not in this file" or "stuck"."""
        s = find(title)
        if s is None:
            return "missing"
        if s["checked"] == value:
            log(f"«{title}»: {'on' if value else 'off'} (as it was)")
            return "ok"
        if s["missing"]:
            return "not in this file"
        if s["disabled"]:
            return "stuck"
        page.evaluate("(i) => [...document.querySelectorAll('.naf input[type=checkbox]')][i].click()", s["i"])
        page.wait_for_timeout(1200)
        now = find(title)
        log(f"«{title}»: set {'on' if now and now['checked'] else 'off'}")
        return "ok" if now and now["checked"] == value else "stuck"

    for s in switches():
        log(f"switch {s['title']!r} = {s['checked']}" + (" (disabled)" if s["disabled"] else "")
            + (f" — {s['missing']}" if s["missing"] else ""))

    state = want(EVERYTHING, True)
    if state != "ok":
        return f"«{EVERYTHING}» could not be turned on ({state})"
    for title in MUST_ARRIVE:
        s = find(title)
        if s is None or s["missing"]:
            return (f"«{title}» is {'not on this dialog' if s is None else 'not in this file'} — the reset needs "
                    "it (pack the whole project: mrjun.py pack work project.mrjun)")
        if not s["checked"]:
            return f"«{title}» stayed off"
    for title in IF_CARRIED:
        s = find(title)
        if s is not None and not s["missing"] and not s["checked"]:
            return f"«{title}» stayed off — without it every table keeps the SQL it runs now"
    for title, value in ((REBUILD, rebuild_structure), (RECREATE, recreate_integration)):
        state = want(title, value)
        if state == "missing" and not value:
            log(f"«{title}»: not on this dialog — nothing to switch off")
            continue
        if state != "ok":
            extra = (" (the schema in the export changed: without the rebuild the new SQL meets the old table and "
                     "the CRUD tables fail)") if title == REBUILD else ""
            return f"«{title}» could not be turned {'on' if value else 'off'} ({state}){extra}"

    summary = page.evaluate("() => ((document.querySelector('.naf-summary') || {}).innerText || '').trim()")
    if summary:
        log(f"the dialog says: {summary}")
    return None


def main(path: str, rebuild_structure: bool = False, recreate_integration: bool = False) -> int:
    if not os.path.exists(path):
        print(f"✗ file not found: {path}")
        return 1
    try:
        CONFIG.require()
    except RuntimeError as exc:
        print(f"✗ {exc}")
        return 1
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"\nImporting {os.path.basename(path)} ({size_mb:.1f} MB) into {CONFIG.base_url}"
          + ("  [+ table structure rebuild]" if rebuild_structure else "")
          + ("  [+ integration re-created]" if recreate_integration else "") + "\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=CONFIG.headless)
        # The browser locale follows the configuration (DEFAULT_LOCALE in .env) instead of a
        # hard-coded language: the suite must run in any locale the project declares.
        # Playwright wants a BCP-47 tag, so "en_US" becomes "en-US".
        ctx = browser.new_context(viewport={"width": 1680, "height": 1050},
                                  locale=CONFIG.default_locale.replace("_", "-"))
        ctx.set_default_timeout(CONFIG.timeout_ms)
        page = ctx.new_page()
        try:
            lp = LoginPage(page)
            lp.login()
            # The session opens in the project's default locale, or in whichever one the user
            # switched to last (the locale is stored on the user, on the server). Switch it to
            # the configured locale rather than a hard-coded one: the suite must run in any
            # locale the project declares. The captions matched below ("Site", "I am author")
            # are listed in every platform UI language, so they match whatever language the
            # session ends up in.
            try:
                lp.switch_locale(CONFIG.default_locale)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            log("signed in")

            # ⛔ The Import/Export page is visible only in AUTHOR mode, and that mode lives in
            # the session, not in the profile: it has to be turned on again after every sign-in.
            page.goto(CONFIG.url("settings"), wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if not page.get_by_text("Import / Export", exact=False).count():
                log("turning on author mode")
                # The page object knows how this toggle lies to a naive script (a menu that
                # ignores synthetic clicks, hidden copies of every caption, a label that names
                # the ACTION, not the state) — reuse it instead of a second copy of that logic.
                try:
                    Nav(page).set_author_mode(True)
                except AssertionError as exc:
                    print(f"✗ could not turn on author mode: {exc}")
                    return 1
                page.wait_for_timeout(2000)
                page.goto(CONFIG.url("settings"), wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

            tab = page.get_by_text("Import / Export", exact=False)
            if not tab.count():
                print("✗ the Import / Export section is not available — author mode did not turn on")
                return 1
            tab.first.click()
            page.wait_for_timeout(2000)

            # ⛔ The buttons on this page are not <button role=button> but links with the btn
            # class, so they are found by their visible text, not by role.
            def click_text(label: str, tries: int = 6) -> bool:
                for _ in range(tries):
                    ok = page.evaluate("""(t) => {
                         const els=[...document.querySelectorAll('a,button')]
                            .filter(e=>e.offsetParent && e.innerText.trim()===t);
                         if(!els.length) return false;
                         els[els.length-1].click(); return true;}""", label)
                    if ok:
                        return True
                    page.wait_for_timeout(1500)
                return False

            if not page.locator("input[type='file']").count():
                if not click_text("Import"):
                    print("✗ the Import button was not found on the Import / Export page")
                    return 1
                page.wait_for_timeout(2000)
            page.locator("input[type='file']").first.set_input_files(path)

            # The dialog opens once the file is read: one switch per part of the project, under four headings.
            deadline = time.time() + 60
            while time.time() < deadline and not page.locator(".naf input[type=checkbox]").count():
                text = page.evaluate("() => document.body.innerText")
                if "not a project export" in text:
                    print("✗ the platform says the file is not a project export, or is damaged — nothing in it "
                          "can be imported")
                    return 1
                if "Import once it has finished" in text:
                    # An export, an import, a version tag or an environment job of the project is running.
                    busy = next((l.strip() for l in text.splitlines() if "Import once it has finished" in l), "")
                    print(f"✗ the platform refuses to import now: {busy}")
                    return 1
                page.wait_for_timeout(1000)
            if not page.locator(".naf input[type=checkbox]").count():
                print("✗ the Import dialog did not open")
                return 1
            log("file uploaded, the Import dialog is open")

            refused = choose_parts(page, rebuild_structure, recreate_integration)
            if refused:
                print(f"✗ {refused}")
                print("  cancelling the import rather than importing half of what was asked for")
                click_text("Cancel")
                return 1

            if not click_text("Import"):
                print("✗ the button that confirms the import was not found")
                return 1
            log("import started, waiting for it to finish")

            started = time.time()
            deadline = started + TIMEOUT_S
            last = ""
            seen = False
            while time.time() < deadline:
                page.wait_for_timeout(5000)
                text = page.evaluate("() => document.body.innerText")
                lines = text.splitlines()
                for outcome in ("Import failed", "Imported with warnings"):
                    if outcome in text:
                        at = next(i for i, line in enumerate(lines) if outcome in line)
                        reason = " ".join(line.strip() for line in lines[at:at + 2])
                        print(f"\n✗ {reason.strip()}")
                        if "heap" in reason.lower():
                            print("  This is the environment, not the file: a series of full imports exhausted the "
                                  "JVM memory.")
                            print("  The environment needs a restart; the Retry button does not help in this state.")
                        elif outcome == "Imported with warnings":
                            print("  The project imported, but what is named above did not land — the tests would "
                                  "run on data that was not reset.")
                        return 1
                progress = ""
                # A progress line STARTS with its marker: searched anywhere, an English page's own
                # text ("Starting a case…") would read as an import that never finishes.
                for marker in ("Importing", "Restoring", "Saving", "Creating", "Deploying", "Waiting",
                               "Removing", "Configuring", "Skipping"):
                    line = next((l.strip() for l in lines if l.strip().startswith(marker)), "")
                    if line:
                        progress = line[:60]
                        break
                if progress:
                    seen = True
                    if progress != last:
                        log(progress)
                        last = progress
                if (not progress and "Export asks which parts" in text
                        and (seen or time.time() - started > 20)):
                    # the progress card has gone — the import is finished
                    print("\n✓ import finished")
                    print("  ⚠️ only the workflows the archive marks deployed: true were deployed — deploy any "
                          "draft a scenario needs")
                    return 0
            print("\n✗ the import did not finish in the allotted time")
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    flags = {"--rebuild-structure", "--recreate-integration"}
    argv = [a for a in sys.argv[1:] if a not in flags]
    raise SystemExit(main(argv[0] if argv else DEFAULT_FILE,
                          "--rebuild-structure" in sys.argv[1:],
                          "--recreate-integration" in sys.argv[1:]))
