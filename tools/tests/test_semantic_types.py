"""Semantic types and «data, not code» (doc 35): each validate check fires on the defect it was written for — every one of
them a defect a delivered project shipped — and stays silent on the corrected shape.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from mrjunkit import validate_cmds as V  # noqa: E402


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


class CrudsFile:
    def __init__(self, cruds):
        self.data = {"cruds": cruds}


class Project:
    def __init__(self, rules=(), tables=(), checks=(), fks=(), cruds=(), nodes=()):
        self.rep = {"rules": [{"name": n, "rule": {"ruleScriptStr": b}} for n, b in rules]}
        self.db = {"schemas": [{"name": "s", "tables": list(tables), "checkConstraints": list(checks),
                                "foreignKeys": list(fks)}]}
        self.cruds_file = CrudsFile(list(cruds))
        self.root_content = {"name": "root", "children": list(nodes)}


CHECK_CAT = ('ALTER TABLE "s"."item" ADD CONSTRAINT "item_category_check" CHECK (((category)::text = ANY '
             "(ARRAY[('FABRIC'::character varying)::text, ('BUTTON'::character varying)::text])))")
CHECK_ST = ('ALTER TABLE "s"."doc" ADD CONSTRAINT "doc_status_check" CHECK (((status)::text = ANY '
            "(ARRAY[('DRAFT'::character varying)::text, ('POSTED'::character varying)::text])))")
ITEM_CRUD = {"alias": "item", "methods": [{"methodName": "findAll", "script": "SELECT * FROM item t"}],
             "dtoFields": [{"fieldName": "category", "displayName": "category"}, {"fieldName": "name", "displayName": "name"}]}


def control(plugin, field, readonly=False):
    st = {"crudAlias": "item", "fieldExpression": field}
    if readonly:
        st["alwaysProhibited"] = True
    return {"name": "fld_" + field, "pluginName": plugin, "children": [],
            "properties": {"settings": {"stringValue": json.dumps(st)}}}


class SemanticTypeChecksTest(unittest.TestCase):

    def run_check(self, fn, p):
        r = Report()
        fn(p, r)
        return r

    def test_a_coded_column_typed_by_hand_is_an_error_and_a_dropdown_is_not(self):
        bad = Project(checks=[CHECK_CAT], cruds=[ITEM_CRUD],
                      nodes=[control("dynaform.form.text.field.plugin", "category")])
        self.assertEqual(1, len(self.run_check(V._check_text_control_on_coded_column, bad).errors))
        ro = Project(checks=[CHECK_CAT], cruds=[ITEM_CRUD],
                     nodes=[control("dynaform.form.text.field.plugin", "category", readonly=True)])
        r = self.run_check(V._check_text_control_on_coded_column, ro)
        self.assertEqual((0, 1), (len(r.errors), len(r.warnings)))
        good = Project(checks=[CHECK_CAT], cruds=[ITEM_CRUD],
                       nodes=[control("dynaform.form.rimm.drop.down.field.plugin", "category"),
                              control("dynaform.form.text.field.plugin", "name")])
        self.assertEqual(0, len(self.run_check(V._check_text_control_on_coded_column, good).errors))

    def test_a_translation_keyed_by_locale_at_the_top_is_an_error(self):
        flat = {"name": "item", "columns": ["id", "name", "localized"],
                "rows": [{"id": "1", "name": "Կտոր", "localized": json.dumps({"en_US": "Fabric", "ru_RU": "Ткань"})}]}
        self.assertEqual(1, len(self.run_check(V._check_localize_flat_shape, Project(tables=[flat])).errors))
        nested = {"name": "item", "columns": ["id", "name", "localized"],
                  "rows": [{"id": "1", "localized": json.dumps({"name": {"en_US": "Fabric", "ru_RU": "Ткань"}})}]}
        self.assertEqual(0, len(self.run_check(V._check_localize_flat_shape, Project(tables=[nested])).errors))

    def test_a_copy_of_the_labels_in_a_rule_is_reported(self):
        copy = Project(checks=[CHECK_ST], rules=[("submit", "def ST = [DRAFT: 'Սևագիր', POSTED: 'Անցկացված']\nreturn ST")])
        self.assertEqual(1, len(self.run_check(V._check_rule_label_copy, copy).warnings))
        codes_only = Project(checks=[CHECK_ST], rules=[("gate", "def M = [DRAFT: 'X', POSTED: 'Y']\nreturn M")])
        self.assertEqual(0, len(self.run_check(V._check_rule_label_copy, codes_only).warnings))

    def test_a_helper_called_but_defined_only_elsewhere_is_an_error(self):
        helper = "def ROWS = { res -> res ?: [] }\n"
        p = Project(rules=[("has it", helper + "for (s in ROWS(x)) { }"),
                           ("lacks it", "def y = 1\nfor (s in ROWS(service.crud.a.find([:]))) { }")])
        r = self.run_check(V._check_helper_closure_undefined, p)
        self.assertEqual(1, len(r.errors))
        self.assertIn("lacks it", r.errors[0])

    def test_business_codes_listed_in_a_rule_are_reported(self):
        cat = {"name": "item", "columns": ["id", "item_code"],
               "rows": [{"id": "1", "item_code": "FAB-001"}, {"id": "2", "item_code": "BTN-002"}]}
        p = Project(tables=[cat], rules=[("suggest", "def P = ['FAB', 'BTN']\nreturn P"),
                                         ("fine", "return service.crud.item.codePrefixes()")])
        r = self.run_check(V._check_rule_lists_business_codes, p)
        self.assertEqual(1, len(r.warnings))
        self.assertIn("suggest", r.warnings[0])

    def test_one_value_spelled_two_ways_in_a_typed_column_is_reported(self):
        mat = {"name": "item", "columns": ["id", "name", "color"],
               "rows": [{"id": "1", "color": "Սև"}, {"id": "2", "color": "սև"}, {"id": "3", "color": "Սպիտակ"}]}
        crud = {"alias": "item", "methods": [{"methodName": "findAll", "script": "SELECT * FROM item t"}],
                "dtoFields": [{"fieldName": "color", "displayName": "color"}]}
        typed = Project(tables=[mat], cruds=[crud], nodes=[control("dynaform.form.text.field.plugin", "color")])
        r = self.run_check(V._check_case_variant_values, typed)
        self.assertEqual(1, len(r.warnings))
        self.assertIn("սև", r.warnings[0])
        auto = Project(tables=[mat], cruds=[crud], nodes=[control("dynaform.form.rimm.autocomplete.field.plugin", "color")])
        self.assertEqual(0, len(self.run_check(V._check_case_variant_values, auto).warnings))

    def test_a_dropdown_that_cannot_search_is_reported(self):
        rule = ("RIMM_x", "return service.global.conversion.toSelectOptions([], 'id', 'name')")
        node = control("dynaform.form.rimm.drop.down.field.plugin", "category")
        st = json.loads(node["properties"]["settings"]["stringValue"]); st["ruleIdentifier"] = "rid-x"
        node["properties"]["settings"]["stringValue"] = json.dumps(st)
        p = Project(rules=[rule], nodes=[node]); p.rep["rules"][0]["identifier"] = "rid-x"
        self.assertEqual(1, len(self.run_check(V._check_dropdown_not_searchable, p).warnings))
        st["searchEnabled"] = True; node["properties"]["settings"]["stringValue"] = json.dumps(st)
        self.assertIn("ignores filterBy", self.run_check(V._check_dropdown_not_searchable, p).warnings[0])
        p.rep["rules"][0]["rule"]["ruleScriptStr"] = "def q = attrs?.get('filterBy')\nreturn []"
        self.assertEqual(0, len(self.run_check(V._check_dropdown_not_searchable, p).warnings))

    def test_today_from_the_server_clock_is_reported(self):
        p = Project(rules=[("r", "def d = java.time.LocalDate.now().toString()")],
                    cruds=[{"alias": "doc", "methods": [{"methodName": "create",
                                                         "script": "INSERT INTO doc (d) VALUES (COALESCE(:d, CURRENT_DATE))"}]}])
        self.assertEqual(2, len(self.run_check(V._check_server_clock_today, p).warnings))
        ok = Project(rules=[("r", "def d = java.time.LocalDate.now(java.time.ZoneId.of('Asia/Yerevan'))")],
                     cruds=[{"alias": "doc", "methods": [{"methodName": "create", "script":
                             "INSERT INTO doc (d) VALUES (COALESCE(:d, CAST(now() AT TIME ZONE 'Asia/Yerevan' AS date)))"}]}])
        self.assertEqual(0, len(self.run_check(V._check_server_clock_today, ok).warnings))

    def test_a_literal_closed_by_an_inner_quote_is_reported(self):
        bad = Project(rules=[("mail", "def cell = { v -> '<td style=\"font-family:'Helvetica Neue',Arial\">' + v + '</td>' }")])
        self.assertEqual(1, len(self.run_check(V._check_literal_runs_into_word, bad).errors))
        good = Project(rules=[("mail", "def cell = { v -> '<td style=\"font-family:\\'Helvetica Neue\\',Arial\">' + v + '</td>' }\n"
                                       "def x = 'a' as String\nif ('k' in m) { return 'y' }")])
        self.assertEqual(0, len(self.run_check(V._check_literal_runs_into_word, good).errors))

    def test_a_flag_shown_as_text_is_reported(self):
        node = control("dynaform.form.text.field.plugin", "requiresApproval")
        st = json.loads(node["properties"]["settings"]["stringValue"]); st["dataClass"] = "java.lang.Boolean"
        node["properties"]["settings"]["stringValue"] = json.dumps(st)
        self.assertEqual(1, len(self.run_check(V._check_flag_as_text, Project(nodes=[node])).warnings))
        st["dataClass"] = "java.lang.String"; node["properties"]["settings"]["stringValue"] = json.dumps(st)
        self.assertEqual(0, len(self.run_check(V._check_flag_as_text, Project(nodes=[node])).warnings))

    def test_one_reference_aliased_in_two_spellings_is_reported(self):
        bad = Project(cruds=[{"alias": "expense", "methods": [{"methodName": "findAll", "script":
              'SELECT j1.name AS expenseCategory__name, j1.kind AS "expenseCategory__kind" FROM expense t'}]}])
        self.assertEqual(1, len(self.run_check(V._check_alias_case_split, bad).errors))
        good = Project(cruds=[{"alias": "expense", "methods": [{"methodName": "findAll", "script":
               'SELECT j1.name AS "expenseCategory__name", j1.kind AS "expenseCategory__kind", j2.id AS stage__id FROM expense t'}]}])
        self.assertEqual(0, len(self.run_check(V._check_alias_case_split, good).errors))


if __name__ == "__main__":
    unittest.main()
