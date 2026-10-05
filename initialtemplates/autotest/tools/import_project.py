"""Imports project.mrjun through the platform's UI — this is what gives the scenario
tests the same data on every run.

Why through the browser: the platform has neither an API nor a CLI for import. The only
way in is Settings → Import/Export. So "reset before the run" is not a call but a short
session of driving the page.

⛔ The import ERASES the tenant's data and restores it from the archive's dump. It runs
only when asked for explicitly: `./start.sh reset`, or this script directly.

    ./.venv/bin/python tools/import_project.py [path-to-mrjun] [--rebuild-structure] [--recreate-integration]

Every switch of the import dialog is SET, never inherited (doc 00, "the import switches"): they are
defaults of a dialog, not a contract, and a script that only clicks Import imports whatever the
platform happens to default to. Each switch is found by its LABEL, set, and logged; when one that
must change is disabled or missing, the import is cancelled instead of half-done.

* "Replace the business logic and its database" — always ON: it brings the SQL and the data.
* `--rebuild-structure` turns on "Rebuild the table structure" (OFF otherwise). It is needed
  EXACTLY when the SCHEMA in the export changed (a column, a table or an index was added): without
  it the new SQL arrives but the column does not — and the CRUD table fails with
  `column ... does not exist`, although the import reported success. When the schema has not
  changed, leave it off: it rebuilds the tables, i.e. it wipes the tenant's data back to the dump.
* `--recreate-integration` turns on "Recreate the integration" (OFF otherwise) — it tears the
  project's integration down and builds it again; a data reset never needs it.

⛔ An import does NOT deploy the workflows: they arrive `deployed: false`, and every work queue
stays empty until each one is deployed again (the BPMN editor, or `nct_workflow_deploy` over MCP).

Returns 0 when the import ran to the end; 1 when the platform reported an error
(including `Java heap space`, which happens after a series of imports in a row).
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


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


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
            page.wait_for_timeout(4000)
            log("file uploaded, the options dialog is open")

            # ⛔ The checkboxes of this dialog decide what exactly arrives, and stay silent when
            # something did not: "Replace the business logic and its database" governs the SQL
            # and the data, "Rebuild the table structure" the schema itself. Without the first,
            # the import reports success while the rules stay as they were; without the second,
            # the new SQL meets the old table. So the state is read TOGETHER WITH THE LABEL and
            # set to the required value explicitly, instead of trusting the defaults.
            boxes = page.evaluate(
                """() => [...document.querySelectorAll('input[type=checkbox]')].map((c, i) => {
                     let t = '';
                     const id = c.getAttribute('id');
                     if (id) { const l = document.querySelector(`label[for="${id}"]`);
                               if (l) t = l.innerText; }
                     if (!t) { let p = c.parentElement;
                               for (let k = 0; k < 4 && p && !t; k++) { t = (p.innerText || '').trim(); p = p.parentElement; } }
                     return {i, checked: c.checked, disabled: c.disabled, name: c.getAttribute('name') || '',
                             label: (t || '').split(String.fromCharCode(10))[0].slice(0, 80)};
                   })"""
            )
            for b in boxes:
                log(f"checkbox [{b['i']}] {b['label']!r} = {b['checked']}"
                    + (" (disabled)" if b["disabled"] else ""))

            def want(wicket_id: str, patterns: tuple[str, ...], value: bool, what: str) -> str:
                """Bring the switch to the required state: "ok", "missing" or "stuck". Found by its component id —
                the end of its `name` attribute, the same in every language — and only failing that by its label."""
                by_id = [b for b in boxes if (b.get("name") or "").endswith(wicket_id)]
                by_label = [b for b in boxes if any(pt in (b["label"] or "").lower() for pt in patterns)]
                match = by_id or by_label
                if not match:
                    return "missing"
                b = match[0]
                if b["checked"] == value:
                    log(f"{what}: {'on' if value else 'off'} (as it was)")
                    return "ok"
                if b["disabled"]:
                    print(f"✗ {what}: the checkbox is disabled, it cannot be turned {'on' if value else 'off'}")
                    return "stuck"
                page.evaluate(
                    """(i) => [...document.querySelectorAll('input[type=checkbox]')][i].click()""",
                    b["i"])
                page.wait_for_timeout(800)
                now = page.evaluate(
                    """(i) => [...document.querySelectorAll('input[type=checkbox]')][i].checked""",
                    b["i"])
                log(f"{what}: set {'on' if now else 'off'}")
                return "ok" if now == value else "stuck"

            # Each switch by its component id, with its caption fragments (en / ru / hy) as the fallback
            # for an installation that renamed it. A switch that must be ON and cannot be is fatal; one
            # that should stay OFF and does not exist on this installation is only logged.
            switches = (
                ("replaceBusinessLogic", ("business logic", "бизнес-логик", "բիզնես"), True,
                 "«Replace the business logic and its database»"),
                ("rebuildSchemas", ("table structure", "структур", "կառուցվածք"), rebuild_structure,
                 "«Rebuild the table structure»"),
                ("recreateIntegration", ("integration", "интеграц", "ինտեգրաց"), recreate_integration,
                 "«Recreate the integration»"),
            )
            for wicket_id, patterns, value, what in switches:
                state = want(wicket_id, patterns, value, what)
                if state == "missing" and not value:
                    log(f"{what}: not on this dialog — nothing to switch off")
                    continue
                if state != "ok":
                    if state == "missing":
                        print(f"✗ {what}: not found among {[b['label'] for b in boxes]}")
                    print("  cancelling the import rather than importing half of what was asked for")
                    if what.startswith("«Rebuild"):
                        print("  (the schema in the export changed: without the rebuild the new SQL meets the old "
                              "table and the CRUD tables fail)")
                    return 1

            if not click_text("Import"):
                print("✗ the button that confirms the import was not found")
                return 1
            log("import started, waiting for it to finish")

            deadline = time.time() + TIMEOUT_S
            last = ""
            while time.time() < deadline:
                page.wait_for_timeout(5000)
                text = page.evaluate("() => document.body.innerText")
                if "Import failed" in text:
                    reason = ""
                    for line in text.splitlines():
                        if "Import failed" in line:
                            idx = text.splitlines().index(line)
                            reason = " ".join(text.splitlines()[idx:idx + 2])
                            break
                    print(f"\n✗ the import failed: {reason.strip()}")
                    if "heap" in reason.lower():
                        print("  This is the environment, not the file: a series of full imports exhausted the JVM memory.")
                        print("  The environment needs a restart; the Retry button does not help in this state.")
                    return 1
                progress = ""
                # A progress line STARTS with its marker: searched anywhere, an English page's own
                # text ("Starting a case…") would read as an import that never finishes.
                for marker in ("Importing", "Configuring", "Deploying", "Starting"):
                    line = next((l.strip() for l in text.splitlines() if l.strip().startswith(marker)), "")
                    if line:
                        progress = line[:60]
                        break
                if progress and progress != last:
                    log(progress)
                    last = progress
                if not progress and "Export downloads the entire project" in text:
                    # the progress window has closed — the import is finished
                    print("\n✓ import finished")
                    print("  ⚠️ after an import the workflows arrive NOT deployed — re-deploy every workflow of the project")
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
