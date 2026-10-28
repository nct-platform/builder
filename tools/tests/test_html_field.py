"""The Html Field (doc 24e): the toolkit writes its value contract and its settings sections where the platform reads
them, and the validator catches the ways a field imports clean and then submits nothing useful — an unreadable
contract, a binding of a type the component does not declare, a component that never writes its value — and the ways
its settings sections import clean and configure nothing: a section outside a field, one that writes nothing, a
catalog list that cannot fill, a picked rule that is not there.

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

from mrjunkit import core, validate_cmds  # noqa: E402

MRJUN = os.path.join(TOOLS, "mrjun.py")
EMPTY = os.path.join(TOOLS, "..", "initialtemplates", "empty.mrjun")
PLUGIN = "dynaform.form.html.field.plugin"
SECTION = "dynaform.html.field.section.plugin"


class Recorder:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


class Project:
    def __init__(self, *nodes):
        self.root_content = {"pluginName": "siteMapPage", "name": "root", "children": list(nodes)}


def slot(key, value):
    return core.make_property_slot(key, value if isinstance(value, str) else json.dumps(value))


def field(settings, field_model=None, scripts=None, raw_field_model=None):
    props = {"settings": slot("settings", settings)}
    if raw_field_model is not None:
        props["fieldModel"] = slot("fieldModel", raw_field_model)
    elif field_model is not None:
        props["fieldModel"] = slot("fieldModel", field_model)
    if scripts is not None:
        props["studioModel"] = slot("studioModel", {"scripts": scripts})
    return {"pluginName": PLUGIN, "name": "Rating", "identifier": "fld_rating", "properties": props, "children": []}


WRITES = [{"name": "main", "enabled": True, "code": "ctx.root.addEventListener('click', () => ctx.field.set(3));"}]
BOUND_INTEGER = {"scope": "CRUD", "contextIdentifier": "c1", "crudAlias": "review", "fieldExpression": "stars",
                 "name": "Rating", "dataClass": "java.lang.Integer"}


def check(*nodes):
    r = Recorder()
    validate_cmds._check_html_field(Project(*nodes), r)
    return r


class HtmlFieldCheck(unittest.TestCase):

    def test_a_declared_type_bound_and_written_is_clean(self):
        r = check(field(BOUND_INTEGER, {"types": ["INTEGER", "LONG"]}, WRITES))
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_declaring_nothing_accepts_any_binding(self):
        r = check(field(BOUND_INTEGER, None, WRITES))
        self.assertEqual(r.warnings, [])

    def test_a_binding_of_an_undeclared_type_is_flagged(self):
        r = check(field(BOUND_INTEGER, {"types": ["STRING"]}, WRITES))
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("bound as INTEGER", r.warnings[0])

    def test_the_type_inside_a_json_column_is_the_one_compared(self):
        projected = dict(BOUND_INTEGER, dataClass="com.fasterxml.jackson.databind.node.ObjectNode",
                         fieldExpression="meta", jsonNodeExpression="rating.stars", jsonNodeValueType="java.lang.Integer")
        self.assertEqual(check(field(projected, {"types": ["INTEGER"]}, WRITES)).warnings, [])
        self.assertIn("bound as INTEGER", check(field(projected, {"types": ["OBJECT_NODE"]}, WRITES)).warnings[0])

    def test_an_untyped_binding_or_a_list_column_reads_as_the_platform_reads_it(self):
        untyped = dict(BOUND_INTEGER, dataClass=None)
        self.assertEqual(check(field(untyped, {"types": ["STRING"]}, WRITES)).warnings, [])
        listed = dict(BOUND_INTEGER, dataClass="java.util.List")
        self.assertEqual(check(field(listed, {"types": ["ARRAY_LIST"]}, WRITES)).warnings, [])

    def test_an_unreadable_contract_and_an_unknown_type_are_flagged(self):
        self.assertIn("not valid JSON", check(field(BOUND_INTEGER, raw_field_model="{types:", scripts=WRITES)).warnings[0])
        self.assertIn("must be", check(field(BOUND_INTEGER, raw_field_model='["INTEGER"]', scripts=WRITES)).warnings[0])
        r = check(field(BOUND_INTEGER, {"types": ["INTEGER", "JSON", "Integer"]}, WRITES))
        self.assertEqual(len(r.warnings), 2)
        self.assertTrue(all("not one a field can be bound as" in w for w in r.warnings))

    def test_a_component_that_never_writes_its_value_is_flagged(self):
        self.assertIn("no enabled script", check(field(BOUND_INTEGER, {"types": ["INTEGER"]})).warnings[0])
        reads_only = [{"name": "main", "code": "paint(ctx.field.value);"}]
        self.assertIn("no script that writes", check(field(BOUND_INTEGER, None, reads_only)).warnings[0])
        parked = [{"name": "main", "code": "// ctx.field.set(1);"}]
        self.assertIn("no script that writes", check(field(BOUND_INTEGER, None, parked)).warnings[0])
        off = [dict(WRITES[0], enabled=False)]
        self.assertIn("no enabled script", check(field(BOUND_INTEGER, None, off)).warnings[0])

    def test_a_write_through_an_alias_in_another_script_counts(self):
        split = [{"name": "state", "code": "const value = ctx.field;"},
                 {"name": "ui", "code": "button.onclick = () => value.set(1);"}]
        self.assertEqual(check(field(BOUND_INTEGER, None, split)).warnings, [])

    def test_the_studio_checks_cover_the_field_too(self):
        self.assertIn(PLUGIN, validate_cmds._STUDIO_PLUGINS)
        self.assertIn(PLUGIN, validate_cmds._HTML_PLUGINS)
        page = {"pluginName": "siteMapPage", "children": [{"pluginName": "nct.parsis.plugin", "children": [
            field(BOUND_INTEGER, None, WRITES)]}]}
        self.assertEqual([PLUGIN], [n["pluginName"] for n in validate_cmds._page_own_html_studio_nodes(page)])


def section(html="", scripts=None, model=None, raw_model=None, name="Appearance"):
    props = {"html": slot("html", html)}
    if scripts is not None:
        props["studioModel"] = slot("studioModel", {"scripts": scripts})
    if raw_model is not None:
        props["sectionModel"] = slot("sectionModel", raw_model)
    elif model is not None:
        props["sectionModel"] = slot("sectionModel", model)
    return {"pluginName": SECTION, "name": name, "identifier": "sec_" + name.lower(), "properties": props,
            "children": []}


class RulesProject(Project):
    def __init__(self, *nodes, rules=()):
        super().__init__(*nodes)
        self.rep = {"rules": [{"identifier": i, "ruleType": t} for i, t in rules]}


def check_sections(*nodes, rules=()):
    r = Recorder()
    validate_cmds._check_html_field_sections(RulesProject(*nodes, rules=rules), r)
    return r


def field_with(custom, *sections):
    node = field(dict(BOUND_INTEGER, custom=custom) if custom is not None else BOUND_INTEGER,
                 {"types": ["INTEGER"]}, WRITES)
    node["children"] = list(sections)
    return node


BOUND = '<input data-setting="max" type="number">'
PICKER = ('<select data-setting="rule" data-catalog="rules" data-rule-type="PREDICATE">'
          '<option value="">— none —</option></select>')


class SettingsSectionCheck(unittest.TestCase):

    def test_a_bound_section_under_its_field_is_clean(self):
        r = check_sections(field_with({"max": 5, "rule": "r1"}, section(BOUND + PICKER, model={"icon": "fa fa-star",
                           "defaults": {"max": 5}})), rules=[("r1", "PREDICATE")])
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_section_outside_a_field_configures_nothing(self):
        self.assertIn("not a child of an html field", check_sections(section(BOUND)).warnings[0])

    def test_a_section_that_writes_nothing_is_flagged_unless_a_script_writes(self):
        self.assertIn("writes nothing", check_sections(field_with(None, section("<p>Hi</p>"))).warnings[0])
        writes = [{"name": "main", "code": "btn.onclick = () => ctx.settings.set('max', 3);"}]
        self.assertEqual([], check_sections(field_with(None, section("<p>Hi</p>", writes))).warnings)
        parked = [{"name": "main", "code": "// ctx.settings.set('max', 3);"}]
        self.assertIn("writes nothing", check_sections(field_with(None, section("<p>Hi</p>", parked))).warnings[0])

    def test_custom_values_must_be_an_object(self):
        self.assertIn("settings.custom must be a JSON object",
                      check_sections(field_with([1, 2], section(BOUND))).warnings[0])
        self.assertEqual([], check_sections(field_with('{"max": 5}', section(BOUND))).warnings)

    def test_an_unreadable_section_model_is_flagged(self):
        self.assertIn("not valid JSON", check_sections(field_with(None, section(BOUND, raw_model="{icon"))).warnings[0])
        self.assertIn("ignores all of it", check_sections(field_with(None, section(BOUND, raw_model='[1]'))).warnings[0])
        self.assertIn("ignores all of it",
                      check_sections(field_with(None, section(BOUND, model={"icon": {"a": 1}}))).warnings[0])
        self.assertIn("defaults must be a JSON object",
                      check_sections(field_with(None, section(BOUND, model={"defaults": [1]}))).warnings[0])
        # an object stored as a JSON string is what the platform accepts too
        self.assertEqual([], check_sections(field_with(None, section(BOUND, model={"defaults": '{"max": 5}'}))).warnings)

    def test_a_catalog_list_that_cannot_fill_is_flagged(self):
        unknown = '<select data-setting="f" data-catalog="forms"></select>'
        self.assertIn("is not a list the catalog has", check_sections(field_with(None, section(unknown))).warnings[0])
        orphan = '<select data-setting="f" data-catalog="fields"></select>'
        self.assertIn("names no CRUD", check_sections(field_with(None, section(orphan))).warnings[0])
        followed = '<select data-setting="f" data-catalog="fields" data-crud-setting="crud"></select>'
        self.assertEqual([], check_sections(field_with(None, section(followed))).warnings)
        typo = '<select data-setting="rule" data-catalog="rules" data-rule-type="PREDICAT"></select>'
        self.assertIn("is not a rule type", check_sections(field_with(None, section(typo))).warnings[0])

    def test_a_picked_rule_must_exist_and_be_of_the_listed_type(self):
        missing = check_sections(field_with({"rule": "gone"}, section(PICKER)), rules=[("r1", "PREDICATE")])
        self.assertIn("is not a rule in rules[]", missing.warnings[0])
        wrong = check_sections(field_with({"rule": "r2"}, section(PICKER)), rules=[("r2", "EXECUTION_RULE")])
        self.assertIn("offers only PREDICATE", wrong.warnings[0])

    def test_the_sections_are_studio_components_and_never_unreferenced_children(self):
        self.assertIn(SECTION, validate_cmds._STUDIO_PLUGINS)
        r = Recorder()
        fld = field_with(None, section(BOUND))
        fld["properties"]["html"] = slot("html", '<div><plugin id="lbl" name="nct.label.plugin"></plugin></div>')
        fld["children"].append({"pluginName": "nct.label.plugin", "identifier": "lbl", "children": []})
        page = {"pluginName": "siteMapPage", "name": "p", "children": [fld]}
        validate_cmds._check_html_plugin_refs(Project(), {"pluginName": "root", "children": [page]}, r)
        self.assertEqual([], [w for w in r.warnings if "never referenced" in w])


def run(*args):
    return subprocess.run([sys.executable, MRJUN] + list(args), capture_output=True, text=True)


class FieldModelCommandTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "proj")
        self.assertEqual(0, run("unpack", EMPTY, self.proj).returncode)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def node(self, identifier):
        with open(os.path.join(self.proj, "branches.json"), encoding="utf-8") as f:
            branches = json.load(f)
        for n, _p, _t in core.iter_nodes(branches[0]["rootContent"]):
            if n.get("identifier") == identifier:
                return n
        raise AssertionError("node %s not found" % identifier)

    def test_set_field_model_writes_the_slot_the_platform_reads(self):
        pages = run("list", "pages", "--project", self.proj)
        self.assertEqual(0, pages.returncode, pages.stderr)
        page_identifier = [line for line in pages.stdout.splitlines() if line.strip()][-1].split()[-1]
        added = run("node", "add", "--parent", page_identifier, "--plugin", PLUGIN, "--name", "Rating",
                    "--identifier", "fld_rating", "--settings", json.dumps(BOUND_INTEGER), "--project", self.proj)
        self.assertEqual(0, added.returncode, added.stderr + added.stdout)
        out = run("node", "set-field-model", "fld_rating", "--json", '{"types":["INTEGER"]}', "--project", self.proj)
        self.assertEqual(0, out.returncode, out.stderr)

        node = self.node("fld_rating")
        self.assertEqual({"types": ["INTEGER"]}, json.loads(node["properties"]["fieldModel"]["stringValue"]))
        self.assertEqual("STRING", node["properties"]["fieldModel"]["propertyType"])
        self.assertEqual("java.lang.Integer",
                         json.loads(node["properties"]["settings"]["stringValue"])["dataClass"])

    def test_a_settings_section_is_a_child_of_its_field(self):
        pages = run("list", "pages", "--project", self.proj)
        page_identifier = [line for line in pages.stdout.splitlines() if line.strip()][-1].split()[-1]
        self.assertEqual(0, run("node", "add", "--parent", page_identifier, "--plugin", PLUGIN, "--name", "Rating",
                                "--identifier", "fld_rating", "--settings", json.dumps(BOUND_INTEGER),
                                "--project", self.proj).returncode)
        added = run("node", "add", "--parent", "fld_rating", "--plugin", SECTION, "--name", "Appearance",
                    "--identifier", "sec_look", "--project", self.proj)
        self.assertEqual(0, added.returncode, added.stderr + added.stdout)
        out = run("node", "set-section-model", "sec_look", "--json", '{"icon":"fa fa-star","defaults":{"max":5}}',
                  "--project", self.proj)
        self.assertEqual(0, out.returncode, out.stderr)
        patched = run("node", "patch-settings", "fld_rating", "--set", 'custom=json:{"max":7}', "--project", self.proj)
        self.assertEqual(0, patched.returncode, patched.stderr)

        fld = self.node("fld_rating")
        self.assertEqual(["sec_look"], [c["identifier"] for c in fld["children"]])
        sec = self.node("sec_look")
        self.assertEqual({"icon": "fa fa-star", "defaults": {"max": 5}},
                         json.loads(sec["properties"]["sectionModel"]["stringValue"]))
        self.assertEqual({"max": 7}, json.loads(fld["properties"]["settings"]["stringValue"])["custom"])


if __name__ == "__main__":
    unittest.main()
