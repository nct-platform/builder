"""Header actions and footer popups (doc 37): the toolkit writes items exactly where and how the platform reads them —
a page's on its own header/footer node, the branch's global ones in site-chrome.json with their plugins on the shared
`Nct header actions` / `Nct footer popups` virtual plugin — refuses what the platform's editor refuses, keeps one order
for both, and the validator catches what a hand-written list gets wrong.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)

from mrjunkit import core, headerfooter_cmds, validate_cmds  # noqa: E402

MRJUN = os.path.join(TOOLS, "mrjun.py")
EMPTY = os.path.join(TOOLS, "..", "initialtemplates", "empty.mrjun")


def run(*args):
    return subprocess.run([sys.executable, MRJUN] + list(args), capture_output=True, text=True)


class Recorder:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


class HeaderFooterTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "proj")
        self.assertEqual(0, run("unpack", EMPTY, self.proj).returncode)
        # A page with a header and a footer of its own, as a layout gives one.
        p = core.Project(self.proj)
        page = {"id": core.new_uuid(), "uniqueIdentifier": core.new_uuid(), "identifier": "sample", "name": "Sample",
                "pluginName": "siteMapPage", "properties": {}, "children": [
                    {"id": core.new_uuid(), "uniqueIdentifier": core.new_uuid(), "identifier": "header",
                     "name": "header", "pluginName": "site.header.plugin", "properties": {}, "children": []},
                    {"id": core.new_uuid(), "uniqueIdentifier": core.new_uuid(), "identifier": "footer",
                     "name": "footer", "pluginName": "site.footer.plugin", "properties": {}, "children": []}]}
        p.root_content.setdefault("children", []).append(page)
        p.mark(core.F_BRANCHES)
        p.save()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hf(self, *args):
        return run("headerfooter", *args, "--project", self.proj)

    def project(self):
        return core.Project(self.proj)

    def page_items(self, area):
        p = self.project()
        page = next(n for n, _a, _b in core.iter_nodes(p.root_content) if n.get("identifier") == "sample")
        return headerfooter_cmds.read_items(headerfooter_cmds.page_node(p, page, area), area)

    def entries(self):
        path = os.path.join(self.proj, "site-chrome.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["items"]

    def shared(self, name):
        return next((vp for vp in self.project().branches[0].get("virtualPlugins") or [] if vp.get("name") == name),
                    None)

    def check(self):
        r = Recorder()
        validate_cmds._check_header_footer(core.Project(self.proj), r)
        return r

    def test_a_global_popup_is_an_entry_of_the_branch_and_its_plugins_get_the_hidden_shared_node(self):
        res = self.hf("add", "--area", "header", "--scope", "global", "--title", "Support", "--title-loc",
                      "hy_AM=Աջակցություն", "--icon", "pe-7s-help1", "--kind", "popup", "--size", "large",
                      "--html", "<div>Hi</div>")
        self.assertEqual(0, res.returncode, res.stderr)

        [entry] = self.entries()
        self.assertEqual(("header", "master"), (entry["area"], entry["branch"]))
        self.assertEqual({"en_US": "Support", "hy_AM": "Աջակցություն"}, entry["item"]["titles"])
        self.assertEqual(("POPUP", "LARGE"), (entry["item"]["kind"], entry["item"]["popupSize"]))
        self.assertTrue(core.looks_uuid(entry["uuid"]))
        self.assertFalse({"uuid", "order", "global"} & set(entry["item"]), "the entry's own fields hold those")
        vp = self.shared("Nct header actions")
        self.assertTrue(vp["commonContent"] and vp["hidden"])
        self.assertFalse(vp["isLayout"])
        self.assertEqual(["architectui-html-pro"], vp["templateNames"])
        self.assertEqual(("site.header.plugin", "header-actions"),
                         (vp["content"]["pluginName"], vp["content"]["identifier"]))
        self.assertTrue(vp["content"]["virtualContent"])
        self.assertEqual([], self.page_items("header"), "nothing on the page")
        r = self.check()
        self.assertEqual(([], []), (r.errors, r.warnings))

    def test_a_pages_item_is_on_its_own_header_and_needs_its_page(self):
        self.assertNotEqual(0, self.hf("add", "--area", "footer", "--name", "Cookies").returncode, "no scope")
        no_page = self.hf("add", "--area", "footer", "--scope", "page", "--name", "Cookies")
        self.assertNotEqual(0, no_page.returncode)
        self.assertIn("--page", no_page.stderr + no_page.stdout)

        res = self.hf("add", "--area", "footer", "--scope", "page", "--page", "Sample", "--name", "Cookies",
                      "--html", "<div hidden>c</div>")
        self.assertEqual(0, res.returncode, res.stderr)
        [item] = self.page_items("footer")
        self.assertEqual("Cookies", item["name"])
        self.assertNotIn("global", item, "where an item is kept says it")
        self.assertNotIn("side", item, "not written: the platform reads RIGHT/BOTTOM/FIXED for a missing one")
        self.assertEqual([], self.entries())
        self.assertIsNone(self.shared("Nct footer popups"), "a page's item needs no shared node")

    def listed(self, area):
        out = self.hf("list", "--area", area, "--page", "Sample").stdout
        names = ("Own", "First", "Second")
        return sorted((n for n in names if n in out), key=out.index)

    def test_one_order_for_both_and_mv_moves_only_the_moved_item(self):
        self.assertEqual(0, self.hf("add", "--area", "footer", "--scope", "page", "--page", "Sample", "--name", "Own",
                                    "--html", "<i>o</i>").returncode)
        for name in ("First", "Second"):
            self.assertEqual(0, self.hf("add", "--area", "footer", "--scope", "global", "--name", name,
                                        "--html", "<i>g</i>").returncode)
        orders = lambda: [e["order"] for e in self.entries()]  # noqa: E731
        self.assertEqual([0, 1000], orders(), "added with no page: after the branch's global ones, wide apart")
        self.assertEqual(["First", "Own", "Second"], self.listed("footer"), "a global item wins a tie")
        [own] = self.page_items("footer")

        res = self.hf("mv", "--area", "footer", "--id", own["uuid"], "--index", "2", "--page", "Sample")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual([0, 1000], orders(), "a page's own item moved: every other page keeps its order")
        self.assertEqual(2000, self.page_items("footer")[0]["order"])
        self.assertEqual(["First", "Second", "Own"], self.listed("footer"))

        second = self.entries()[1]["uuid"]
        self.assertEqual(0, self.hf("mv", "--area", "footer", "--id", second, "--index", "0", "--page", "Sample")
                         .returncode)
        self.assertEqual([0, -1000], orders())
        self.assertEqual(2000, self.page_items("footer")[0]["order"], "only the moved item changes")
        self.assertEqual(["Second", "First", "Own"], self.listed("footer"))

    def test_mv_numbers_the_page_again_when_its_neighbours_leave_no_room(self):
        for name in ("First", "Second"):
            self.assertEqual(0, self.hf("add", "--area", "header", "--scope", "global", "--title", name, "--title-loc",
                                        "hy_AM=" + name, "--icon", "pe-7s-star", "--kind", "popup").returncode)
        path = os.path.join(self.proj, "site-chrome.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["items"][1]["order"] = 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        self.assertEqual(0, self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Own",
                                    "--title-loc", "hy_AM=Own", "--icon", "pe-7s-star", "--kind", "popup").returncode)
        [own] = self.page_items("header")

        res = self.hf("mv", "--area", "header", "--id", own["uuid"], "--index", "1", "--page", "Sample")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual([0, 2000], [e["order"] for e in self.entries()])
        self.assertEqual(1000, self.page_items("header")[0]["order"])
        self.assertEqual(["First", "Own", "Second"], self.listed("header"))
        self.assertEqual(500, headerfooter_cmds._between(0, 1000, False, False))
        self.assertIsNone(headerfooter_cmds._between(0, 1, False, False))
        self.assertIsNone(headerfooter_cmds._between(None, 5, False, False), "a neighbour with no order")
        self.assertEqual(0, headerfooter_cmds._between(None, None, True, True))

    def test_a_header_that_links_nowhere_is_the_pages_own(self):
        p = self.project()
        page = next(n for n, _a, _b in core.iter_nodes(p.root_content) if n.get("identifier") == "sample")
        header = next(c for c in page["children"] if c["pluginName"] == "site.header.plugin")
        header["linkContentIdentifier"] = "f6357e8a-0000-4000-8000-000000000000"
        p.mark(core.F_BRANCHES)
        p.save()
        self.assertIs(header, headerfooter_cmds.page_node(p, page, "header"), "the platform drops a dead link")
        res = self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Help",
                      "--title-loc", "hy_AM=Help", "--icon", "pe-7s-help1", "--kind", "popup")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual(1, len(self.page_items("header")))

    def test_scope_moves_an_item_with_the_plugins_only_it_placed(self):
        res = self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Help", "--icon",
                      "pe-7s-help1", "--kind", "popup", "--html", "<plugin id=\"note\" name=\"nct.label.plugin\"></plugin>")
        self.assertEqual(0, res.returncode, res.stderr)
        [item] = self.page_items("header")
        p = self.project()
        page = next(n for n, _a, _b in core.iter_nodes(p.root_content) if n.get("identifier") == "sample")
        node = headerfooter_cmds.page_node(p, page, "header")
        node["children"].append({"id": core.new_uuid(), "identifier": "note", "pluginName": "nct.label.plugin",
                                 "properties": {}, "children": [], "virtualContent": False})
        p.mark(core.F_BRANCHES)
        p.save()

        res = self.hf("set", "--area", "header", "--id", item["uuid"], "--page", "Sample", "--scope", "global")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual([], self.page_items("header"))
        self.assertEqual([item["uuid"]], [e["uuid"] for e in self.entries()])
        moved = self.shared("Nct header actions")["content"]["children"]
        self.assertEqual(["note"], [c["identifier"] for c in moved])
        self.assertTrue(moved[0]["virtualContent"], "a node of the shared plugin now")

        self.assertEqual(0, self.hf("rm", "--area", "header", "--id", item["uuid"]).returncode)
        self.assertEqual([], self.entries())
        self.assertEqual([], self.shared("Nct header actions")["content"]["children"], "its plugins go with it")

    def test_a_popup_opens_under_the_icon_or_as_a_side_panel_and_a_script_action_runs_its_script(self):
        res = self.hf("add", "--area", "header", "--scope", "global", "--title", "Help", "--title-loc", "hy_AM=Help",
                      "--icon", "pe-7s-help1", "--kind", "popup", "--placement", "right", "--panel-top", "over-header",
                      "--panel-height", "content", "--animation", "zoom", "--html", "<div>Help</div>")
        self.assertEqual(0, res.returncode, res.stderr)
        [side] = self.entries()
        self.assertEqual({"popupPlacement": "RIGHT", "panelTop": "OVER_HEADER", "panelHeight": "CONTENT",
                          "popupAnimation": "ZOOM"},
                         {k: side["item"][k] for k in ("popupPlacement", "panelTop", "panelHeight", "popupAnimation")})
        self.assertNotIn("panelBottom", side["item"], "not written: the platform reads OVER_FOOTER for a missing one")

        no_script = self.hf("add", "--area", "header", "--scope", "global", "--title", "Ping", "--title-loc",
                            "hy_AM=Ping", "--icon", "pe-7s-bell", "--kind", "script")
        self.assertNotEqual(0, no_script.returncode)
        self.assertIn("no script", no_script.stderr + no_script.stdout)
        res = self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Ping",
                      "--title-loc", "hy_AM=Ping", "--icon", "pe-7s-bell", "--kind", "script", "--event", "double-click",
                      "--script", "await ctx.callRule('ping', {});")
        self.assertEqual(0, res.returncode, res.stderr)
        [script] = self.page_items("header")
        self.assertEqual(("SCRIPT", "DOUBLE_CLICK", "await ctx.callRule('ping', {});"),
                         (script["kind"], script["event"], script["script"]))
        self.assertIn("SCRIPT on double-click", self.hf("list", "--area", "header", "--page", "Sample").stdout)
        self.assertNotEqual(0, self.hf("add", "--area", "footer", "--scope", "global", "--name", "x",
                                       "--event", "click").returncode, "an event is a header field")

        self.assertEqual(0, self.hf("set", "--area", "header", "--id", script["uuid"], "--page", "Sample",
                                    "--scope", "global").returncode)
        self.assertIsNotNone(self.shared("Nct header actions"), "a global script runs in a component on the shared node")
        r = self.check()
        self.assertEqual([], r.errors)
        with open(os.path.join(self.proj, "site-chrome.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        data["items"][0]["item"]["popupPlacement"] = "TOP"
        with open(os.path.join(self.proj, "site-chrome.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        self.assertIn("popupPlacement must be one of", "\n".join(self.check().errors))

    def test_a_choice_is_taken_in_any_case_and_automatic_is_no_animation_written(self):
        res = self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Ping",
                      "--title-loc", "hy_AM=Ping", "--icon", "pe-7s-bell", "--kind", "SCRIPT", "--event", "DOUBLE_CLICK",
                      "--script", "ctx.toast.info(ctx.t('Pong'));", "--size", "large")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn("note: --size do(es) nothing for this SCRIPT action", res.stdout, "kept, and said")
        [script] = self.page_items("header")
        self.assertEqual(("SCRIPT", "DOUBLE_CLICK", "LARGE"), (script["kind"], script["event"], script["popupSize"]))

        res = self.hf("set", "--area", "header", "--id", script["uuid"], "--page", "Sample", "--kind", "Popup",
                      "--animation", "zoom", "--panel-top", "over-header")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn("--panel-top do(es) nothing for this POPUP action under the icon", res.stdout)
        self.assertEqual("ZOOM", self.page_items("header")[0]["popupAnimation"])
        self.assertEqual(0, self.hf("set", "--area", "header", "--id", script["uuid"], "--page", "Sample",
                                    "--animation", "automatic").returncode)
        self.assertNotIn("popupAnimation", self.page_items("header")[0],
                         "automatic: it slides in at a side, opens as the header's menus do under the icon")

        # A hand-written list in another spelling is read as the platform reads it.
        loose = {"titles": {"en_US": "Help"}, "icon": "pe-7s-help1", "kind": "popup", "popupPlacement": "under-icon",
                 "event": "right click"}
        self.assertEqual([], headerfooter_cmds.item_problems("header", loose, lambda i: True))
        self.assertTrue(headerfooter_cmds.draws_component("header", loose))

    def test_a_script_that_closes_what_it_did_not_open_is_refused(self):
        ok = {"titles": {"en_US": "Ping"}, "icon": "pe-7s-bell", "kind": "SCRIPT"}
        for escaping in ("}); steal(); (async function () {", "}", "foo(]", "if (a) { b();", "/* { */ }"):
            problems = headerfooter_cmds.item_problems("header", dict(ok, script=escaping), lambda i: True)
            self.assertEqual(1, len(problems), escaping)
            self.assertIn("brackets do not match", problems[0])
        for balanced in ("ctx.toast.info(')}');", 'const s = "{"; // a } in a comment',
                         "/* ) */ const t = `${a + '}'} and } and ${ {b: 1}.b }`;",
                         "if (/[)}]/.test(x)) { y = x / 2 / 3; }"):
            self.assertEqual([], headerfooter_cmds.item_problems("header", dict(ok, script=balanced), lambda i: True),
                             balanced)
        bad = self.hf("add", "--area", "header", "--scope", "global", "--title", "Ping", "--icon", "pe-7s-bell",
                      "--kind", "script", "--script", "}); steal(); (async function () {")
        self.assertNotEqual(0, bad.returncode)
        self.assertEqual([], self.entries(), "nothing written")

    def test_a_kind_and_a_scope_changed_at_once_move_the_plugins_its_kept_html_places(self):
        res = self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Help", "--icon",
                      "pe-7s-help1", "--kind", "popup", "--html", "<plugin id=\"note\" name=\"nct.label.plugin\"></plugin>")
        self.assertEqual(0, res.returncode, res.stderr)
        [item] = self.page_items("header")
        p = self.project()
        page = next(n for n, _a, _b in core.iter_nodes(p.root_content) if n.get("identifier") == "sample")
        headerfooter_cmds.page_node(p, page, "header")["children"].append(
            {"id": core.new_uuid(), "identifier": "note", "pluginName": "nct.label.plugin", "properties": {},
             "children": [], "virtualContent": False})
        p.mark(core.F_BRANCHES)
        p.save()

        res = self.hf("set", "--area", "header", "--id", item["uuid"], "--page", "Sample", "--scope", "global",
                      "--kind", "script", "--script", "ctx.toast.info('x');")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual(["note"], [c["identifier"] for c in self.shared("Nct header actions")["content"]["children"]],
                         "the html it keeps for when it is a popup again keeps its plugin, wherever it goes")
        self.assertEqual(0, self.hf("rm", "--area", "header", "--id", item["uuid"]).returncode)
        self.assertEqual([], self.shared("Nct header actions")["content"]["children"], "and takes it when it goes")

    def test_a_script_actions_texts_are_found_as_a_components_are(self):
        res = self.hf("add", "--area", "header", "--scope", "global", "--title", "Hi", "--title-loc", "hy_AM=Hi",
                      "--icon", "pe-7s-bell", "--kind", "script", "--script", "ctx.toast.info(ctx.t('Hi ' + ctx.user.name));")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn("whose text is not one string literal", "\n".join(self.check().warnings),
                      "a multilingual project translates only a literal")

    def test_what_runs_as_an_item_is_shown_is_its_components_scripts_or_a_script_actions_script(self):
        popup = {"kind": "POPUP", "studioModel": {"scripts": [{"name": "main", "code": "ctx.callRule('a', {})"},
                                                              {"name": "off", "code": "x()", "enabled": False}]},
                 "script": "kept()"}
        self.assertEqual([("main", "ctx.callRule('a', {})")], headerfooter_cmds.component_scripts("header", popup))
        self.assertEqual([("script", "kept()")],
                         headerfooter_cmds.component_scripts("header", dict(popup, kind="script")))
        self.assertEqual([], headerfooter_cmds.component_scripts("header", dict(popup, kind="PAGE")))
        self.assertTrue(headerfooter_cmds.seen_by_everyone({}))
        self.assertFalse(headerfooter_cmds.seen_by_everyone({"roleAccess": {"publicReadAccess": False}}))

    def test_a_standard_icon_takes_a_look_and_its_own_colors_only_as_colors(self):
        res = self.hf("add", "--area", "header", "--scope", "page", "--page", "Sample", "--title", "Help",
                      "--title-loc", "hy_AM=Help", "--icon", "pe-7s-help1", "--kind", "popup", "--html", "<p>Help</p>",
                      "--icon-color", "success", "--icon-style", "solid", "--icon-shape", "rounded", "--show-title",
                      "--badge", "text", "--badge-text", "New", "--pulse")
        self.assertEqual(0, res.returncode, res.stderr)
        [item] = self.page_items("header")
        self.assertEqual(("SUCCESS", "SOLID", "ROUNDED", True, "TEXT", True),
                         tuple(item.get(k) for k in ("iconColor", "iconStyle", "iconShape", "showTitle", "badge", "pulse")))
        self.assertEqual("New", next(iter(item["badgeTexts"].values())))
        self.assertEqual(0, self.hf("set", "--area", "header", "--id", item["uuid"], "--page", "Sample",
                                    "--icon-color", "automatic", "--no-show-title").returncode)
        item = self.page_items("header")[0]
        self.assertNotIn("iconColor", item, "automatic: the theme's own look")
        self.assertFalse(item["showTitle"])
        note = self.hf("set", "--area", "header", "--id", item["uuid"], "--page", "Sample", "--icon-background", "#000")
        self.assertIn("--icon-background do(es) nothing", note.stdout, "kept, and said: it needs iconColor custom")

        bad = self.hf("set", "--area", "header", "--id", item["uuid"], "--page", "Sample", "--icon-color", "custom",
                      "--icon-foreground", "red;}")
        self.assertNotEqual(0, bad.returncode)
        self.assertIn("iconColor CUSTOM needs iconBackground and iconForeground", bad.stderr + bad.stdout)
        ok = {"titles": {"en_US": "Help"}, "icon": "pe-7s-help1", "kind": "POPUP"}
        self.assertIn("badge TEXT with no badgeTexts",
                      headerfooter_cmds.item_problems("header", dict(ok, badge="text"), lambda i: True)[0])
        self.assertIn("showTitle must be true or false",
                      headerfooter_cmds.item_problems("header", dict(ok, showTitle="yes"), lambda i: True)[0])
        self.assertIn("badgeColor must be one of",
                      headerfooter_cmds.item_problems("header", dict(ok, badgeColor="CUSTOM"), lambda i: True)[0])

    def test_an_action_of_its_own_html_needs_no_icon_and_is_checked_as_a_component(self):
        res = self.hf("add", "--area", "header", "--scope", "global", "--title", "Search", "--title-loc", "hy_AM=Search",
                      "--kind", "html", "--html", "<button type=\"button\" class=\"btn btn-sm\">Go</button>",
                      "--icon-color", "danger")
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertIn("--icon-color do(es) nothing for this HTML action", res.stdout)
        [entry] = self.entries()
        self.assertEqual("HTML", entry["item"]["kind"])
        self.assertIsNotNone(self.shared("Nct header actions"), "its plugins hang on the shared node, as a popup's")
        self.assertTrue(headerfooter_cmds.draws_component("header", entry["item"]))
        self.assertIn("HTML — its own html in the header", self.hf("list", "--area", "header").stdout)
        self.assertEqual([], self.check().errors)
        no_html = self.hf("add", "--area", "header", "--scope", "global", "--title", "Empty", "--kind", "html")
        self.assertNotEqual(0, no_html.returncode)
        self.assertIn("no html", no_html.stderr + no_html.stdout)

    def test_what_the_platform_refuses_is_refused_and_nothing_is_written(self):
        bad = self.hf("add", "--area", "header", "--scope", "global", "--title", "X", "--icon", "pe-7s-star", "--kind",
                      "page", "--link", "//evil.example")
        self.assertNotEqual(0, bad.returncode)
        self.assertIn("refuse", bad.stderr + bad.stdout)
        params = self.hf("add", "--area", "header", "--scope", "global", "--title", "X", "--icon", "pe-7s-star",
                         "--kind", "page", "--target-page", "Sample", "--params", "//evil.example")
        self.assertNotEqual(0, params.returncode)
        self.assertEqual(0, self.hf("add", "--area", "footer", "--scope", "global", "--name", "A",
                                    "--html", "<plugin id=\"x\" name=\"nct.label.plugin\"></plugin>").returncode)
        clash = self.hf("add", "--area", "footer", "--scope", "global", "--name", "B",
                        "--html", "<plugin id=\"x\" name=\"nct.image.plugin\"></plugin>")
        self.assertNotEqual(0, clash.returncode, "one id as two plugins on one node")
        quoted = self.hf("add", "--area", "footer", "--scope", "global", "--name", "B",
                         "--html", "<plugin name='nct.image.plugin' id='x'></plugin>")
        self.assertNotEqual(0, quoted.returncode, "the platform reads a tag in either quotes")
        self.assertEqual(1, len(self.entries()))
        self.assertNotEqual(0, self.hf("add", "--area", "footer", "--scope", "global", "--name", "C",
                                       "--icon", "pe-7s-star").returncode, "an icon is a header field")
        mirrored = "4b5c0d3e-1111-4222-8333-944455556666"
        self.assertEqual(0, self.hf("add", "--area", "footer", "--scope", "global", "--name", "Mirrored",
                                    "--id", mirrored).returncode)
        self.assertIn(mirrored, [e["uuid"] for e in self.entries()], "--id mirrors an item made live")

    def test_the_validator_catches_what_a_hand_written_list_gets_wrong(self):
        self.assertEqual(0, self.hf("add", "--area", "footer", "--scope", "global", "--name", "Ok", "--html",
                                    "<plugin id=\"t\" name=\"nct.label.plugin\"></plugin>").returncode)
        path = os.path.join(self.proj, "site-chrome.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        first = data["items"][0]
        data["items"] += [
            {"branch": "master", "area": "footer", "uuid": first["uuid"], "item": {"name": "Same id"}},
            {"branch": "master", "area": "footer", "uuid": "u2", "item": {"name": "", "side": "MIDDLE"}},
            {"branch": "master", "area": "footer", "uuid": "u3", "item": {
                "name": "Loop", "html": "<include src=\"a.html\"/>", "studioModel": {"docs": [
                    {"name": "a", "html": "<include src=\"b.html\"/>"}, {"name": "b", "html": "<include src=\"a.html\"/>"}]}}},
            {"branch": "master", "area": "footer", "uuid": "u4", "item": {"name": "Stringly", "studioModel": "{}"}},
            {"branch": "master", "area": "footer", "uuid": "u5", "item": {
                "name": "Shares", "html": "<plugin id=\"t\" name=\"nct.label.plugin\"></plugin>"}},
            {"branch": "gone", "area": "footer", "uuid": "u6", "item": {"name": "Elsewhere"}},
            {"branch": "master", "area": "sidebar", "uuid": "u7", "item": {}},
            {"branch": "master", "area": "header", "uuid": "u8", "item": {"titles": "Support", "kind": "POPUP"}},
        ]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        p = self.project()
        page = next(n for n, _a, _b in core.iter_nodes(p.root_content) if n.get("identifier") == "sample")
        node = headerfooter_cmds.page_node(p, page, "header")
        node["properties"]["headerActions"] = core.make_property_slot("headerActions", "{\"items\": [\"x\"]}")
        p.mark(core.F_BRANCHES)
        p.save()

        r = self.check()
        text = "\n".join(r.errors)
        self.assertIn("another item of the branch has this uuid", text)
        self.assertIn("no name", text)
        self.assertIn("side must be one of", text)
        self.assertIn("cycle", text.lower())
        self.assertIn("studioModel is a JSON string", text)
        self.assertIn("area must be one of", text)
        self.assertIn("titles must be an object", text)
        self.assertIn("is not an object", text, "the page's list")
        warnings = "\n".join(r.warnings)
        self.assertIn("branch 'gone' is not in the export", warnings)
        self.assertIn("placed by 2 items", warnings)
        self.assertIn("the shared node 'Nct header actions', which the branch has not: the import makes an empty one",
                      warnings, "a drawn global popup with no node yet: the import makes it")

    def test_the_validator_takes_the_shared_node_as_the_platform_finds_it(self):
        self.assertEqual(0, self.hf("add", "--area", "header", "--scope", "global", "--title", "Help", "--icon",
                                    "pe-7s-help1", "--kind", "popup", "--html", "<div>Hi</div>").returncode)
        r = self.check()
        self.assertEqual([], r.errors)
        self.assertEqual(1, len(r.warnings), "the title has no hy_AM text")
        self.assertIn("no title for hy_AM", r.warnings[0])

        p = self.project()
        vp = self.shared("Nct header actions")
        vp_live = next(v for v in p.branches[0]["virtualPlugins"] if v.get("id") == vp.get("id"))
        vp_live["name"] = "Renamed by an author"
        vp_live["templateNames"] = []
        p.branches[0]["virtualPlugins"].append(
            {"id": core.new_uuid(), "name": "Nct header actions", "commonContent": True, "hidden": False,
             "templateNames": [], "content": {"pluginName": "nct.html.plugin", "identifier": "x", "children": []}})
        p.mark(core.F_BRANCHES)
        p.save()
        r = self.check()
        self.assertEqual(1, len(r.errors), r.errors)
        self.assertIn("other virtual plugin(s) named 'Nct header actions'", r.errors[0],
                      "found by its identifier whatever its name; [] is a list")

        p = self.project()
        vp_live = next(v for v in p.branches[0]["virtualPlugins"] if v.get("id") == vp.get("id"))
        vp_live["templateNames"] = None
        p.branches[0]["virtualPlugins"].pop()
        p.mark(core.F_BRANCHES)
        p.save()
        self.assertIn("no templateNames list", "\n".join(self.check().errors))

    def test_the_rules_are_the_platforms(self):
        ok = {"titles": {"en_US": "Help"}, "icon": "pe-7s-help1", "kind": "POPUP"}
        self.assertEqual([], headerfooter_cmds.item_problems("header", ok, lambda i: True))
        self.assertEqual(3, len(headerfooter_cmds.item_problems("header", {}, lambda i: True)))
        page = dict(ok, kind="PAGE", identifier="gone")
        self.assertIn("does not exist", headerfooter_cmds.item_problems("header", page, lambda i: False)[0])
        for link, problems in (("https://x.y", 0), ("/proj/page", 0), ("mailto:a@b.c", 0), ("javascript:x", 1),
                               ("data:text/html,x", 1), ("/", 1), ("//evil.example", 1), ("/\\evil.example", 1)):
            item = dict(ok, kind="PAGE", internal=False, link=link)
            self.assertEqual(problems, len(headerfooter_cmds.item_problems("header", item, lambda i: True)), link)
        for params, problems in (("?a=1", 0), ("#x", 0), ("/more", 0), ("", 0), ("//evil", 1), ("x", 1)):
            item = dict(ok, kind="PAGE", identifier="p", params=params)
            self.assertEqual(problems, len(headerfooter_cmds.item_problems("header", item, lambda i: True)), params)
        self.assertIn("internal must be true or false",
                      headerfooter_cmds.item_problems("header", dict(ok, internal="false"), lambda i: True)[0])


if __name__ == "__main__":
    unittest.main()
