"""Archives that carry only some parts of a project (doc 00 §"Export shape", §"Which parts a file carries"): the
platform's Export writes exactly the parts its author ticked, so a valid archive may have no branches.json, no
project-db.dump, only some rep-objects keys, and entries older archives never had. The toolkit must read every such
archive as it is: not refuse it, not report what it does not carry as "none", and never write a part it lacks.

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

from mrjunkit import core  # noqa: E402

MRJUN = os.path.join(TOOLS, "mrjun.py")
EMPTY = os.path.join(TOOLS, "..", "initialtemplates", "empty.mrjun")


def run(*args):
    return subprocess.run([sys.executable, MRJUN] + list(args), capture_output=True, text=True)


class PartialArchiveTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "proj")
        self.assertEqual(0, run("unpack", EMPTY, self.proj).returncode)
        self.rep = self.read("rep-objects.json")
        # A build never carries the API endpoint list (doc 32 §6); the baseline's own copy is not what is tested here.
        self.rep.pop("apiExposures", None)
        self.write("rep-objects.json", self.rep)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.proj, name)

    def read(self, name):
        with open(self.path(name), encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, name, data):
        os.makedirs(os.path.dirname(self.path(name)), exist_ok=True)
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def drop(self, *names):
        for name in names:
            target = self.path(name)
            if os.path.isdir(target):
                shutil.rmtree(target)
            elif os.path.exists(target):
                os.remove(target)

    def keep_rep(self, *keys):
        self.rep = {k: v for k, v in self.rep.items() if k in keys}
        self.write("rep-objects.json", self.rep)

    def parts(self):
        return {label: (importable, count) for heading, label, importable, count, _w
                in core.archive_parts(core.Project(self.proj)) if heading != "!"}

    def without_pages(self):
        self.drop("branches.json", "branch-metadata.json", "tenant-files", "favicon")

    # ------------------------------------------------------------------ validate / inspect read what is there

    def test_an_archive_without_pages_or_database_validates_and_says_what_it_lacks(self):
        self.without_pages()
        self.drop("project-db.dump", "integrations.json")
        self.keep_rep("mailTemplates", "pdfTemplates", "roleGroups", "userRoleGroupAssignments")
        self.rep["featureAccesses"] = [{"feature": "USER_MANAGEMENT", "roleGroups": ["Developer"]}]
        self.rep["userRoleGroupAssignments"] = [{"userId": "kc-1", "userEmail": "member@example.invalid",
                                                 "roleGroupId": "7", "roleGroupName": "Author"}]
        self.write("rep-objects.json", self.rep)

        res = run("validate", "--project", self.proj)
        self.assertEqual(0, res.returncode, res.stdout + res.stderr)
        self.assertIn("not in this archive: pages, forms and rules;", res.stdout)
        self.assertNotIn("BASE pages were REMOVED", res.stdout, "the target keeps its own console")
        self.assertFalse(os.path.exists(self.path("branches.json")), "a stand-in is never written")
        self.assertFalse(os.path.exists(self.path("project-db.dump")))

        out = run("inspect", "--project", self.proj).stdout
        self.assertIn("Content tree: not in this archive (no branches.json)", out)
        self.assertIn("database: no project-db.dump in this archive", out)
        self.assertIn("schemaPrefix=", out, "the re-linking metadata travels without a dump")
        self.assertIn("project-db-meta.json: no \"database\" mark", out, "the bundled baseline predates the mark")
        self.assertRegex(out, r"\n  rules\s+absent\n", "absent is not 0")
        self.assertRegex(out, r"\n  featureAccesses\s+1\n")

    def test_business_logic_without_its_database_is_not_refused_for_its_schemas(self):
        self.write("dynamic-cruds.json", {"exportVersion": 1, "enums": [{"name": "status", "kind": "FREE",
                                                                         "values": [{"name": "open"}]}],
                                          "cruds": [{"alias": "invoice", "name": "Invoice",
                                                     "sourceIdentifier": "11111111-1111-4111-8111-111111111111",
                                                     "sourceSchema": "elsewhere_app", "methods": []}]})
        with_dump = run("validate", "--project", self.proj).stdout
        self.assertIn("sourceSchema 'elsewhere_app' not found in project-db.dump", with_dump)

        self.drop("project-db.dump")
        without = run("validate", "--project", self.proj).stdout
        self.assertNotIn("not found in project-db.dump", without,
                         "without a dump the CRUDs attach to the target's own schemas on import")
        self.assertIn("  enums: 1", run("inspect", "--project", self.proj).stdout)

    def test_a_crud_needs_a_context_only_when_the_archive_carries_the_contexts(self):
        self.without_pages()
        self.keep_rep("sources", "queries", "rules")
        self.write("dynamic-cruds.json", {"exportVersion": 1, "cruds": [
            {"alias": "invoice", "name": "Invoice", "sourceIdentifier": "11111111-1111-4111-8111-111111111111",
             "sourceSchema": "x", "methods": []}]})
        self.assertNotIn("is not listed in any context.crudAliases", run("validate", "--project", self.proj).stdout)
        self.rep["contexts"] = []
        self.write("rep-objects.json", self.rep)
        self.assertIn("is not listed in any context.crudAliases", run("validate", "--project", self.proj).stdout)

    def test_a_command_that_needs_the_pages_names_the_part_the_archive_left_out(self):
        self.without_pages()
        res = run("tree", "--project", self.proj)
        self.assertNotEqual(0, res.returncode)
        self.assertIn("does not carry its pages", res.stderr)

    def test_a_stand_in_is_never_saved(self):
        self.without_pages()
        p = core.Project(self.proj)
        self.assertEqual([core.F_BRANCHES], p.stand_in_absent_parts())
        p.mark(core.F_BRANCHES)
        with self.assertRaises(core.ToolError):
            p.save()
        self.assertFalse(os.path.exists(self.path("branches.json")))

    # ------------------------------------------------------------------ the platform's evidence rules

    def test_each_part_is_carried_by_its_own_evidence(self):
        parts = self.parts()
        self.assertEqual((True, None), parts["Pages, forms and rules"])
        self.assertEqual((True, 5), parts["Mail and PDF templates"])
        self.assertFalse(parts["Public API endpoints"][0], "absent")
        self.assertTrue(parts["Database"][0], "dump together with meta")

        self.rep["apiExposures"] = None
        self.write("rep-objects.json", self.rep)
        self.assertFalse(self.parts()["Public API endpoints"][0], "null says what absent says")
        self.rep["apiExposures"] = []
        self.write("rep-objects.json", self.rep)
        self.assertEqual((True, 0), self.parts()["Public API endpoints"], "an empty list is a statement")

        self.drop("project-db.dump")
        self.assertFalse(self.parts()["Database"][0], "meta alone is no database")
        self.write("rimm-data.json", {})
        self.assertTrue(self.parts()["Database"][0], "the legacy row export is one")
        self.drop("rimm-data.json")
        self.rep["sources"] = [{"id": None, "identifier": "s1", "name": "app", "sourceType": "INTERNAL"}]
        self.write("rep-objects.json", self.rep)
        self.assertTrue(self.parts()["Database"][0], "an older file's own data sources are its database")

        meta = self.read("project-db-meta.json")
        meta["database"] = False
        self.write("project-db-meta.json", meta)
        self.assertFalse(self.parts()["Database"][0], "a file that says it carries no database carries none")
        meta["database"] = True
        self.write("project-db-meta.json", meta)
        self.assertTrue(self.parts()["Database"][0], "a database with nothing to dump is still the database")

    def test_deployment_and_processes_follow_what_they_need(self):
        self.rep["workflows"] = [{"identifier": "w", "deployed": True}]
        self.write("rep-objects.json", self.rep)
        self.assertEqual((True, 1), self.parts()["Deployment"], "without a history the current rows tell")

        self.write("workflow-history.json", {"versions": [{"deployed": False}]})
        self.assertFalse(self.parts()["Deployment"][0], "with a history only its versions count")

        self.write("processes.json", {"processes": [{"identifier": "c", "runtime": {}}]})
        self.write("process-audit-logs.json", {"logs": []})
        parts = self.parts()
        self.assertFalse(parts["Processes"][0], "processes need the deployment too")
        self.assertFalse(parts["Process audit log"][0])

        self.write("workflow-history.json", {"versions": [{"deployed": True}]})
        parts = self.parts()
        self.assertEqual((True, 1), parts["Processes"])
        self.assertTrue(parts["Process audit log"][0])

        self.write("data-audit-logs.json", {"logs": []})
        self.assertTrue(self.parts()["Data change history"][0])
        self.drop("project-db.dump")
        self.assertFalse(self.parts()["Data change history"][0], "the data change history needs the database")

    def test_a_groovy_methods_script_must_match_the_hidden_rule_the_archive_carries(self):
        script = "def x = param?.id\nreturn [done: x]\n"
        rule_id = "22222222-2222-4222-8222-222222222222"
        self.write("dynamic-cruds.json", {"exportVersion": 1, "cruds": [
            {"alias": "invoice", "name": "Invoice", "sourceIdentifier": "11111111-1111-4111-8111-111111111111",
             "methods": [{"methodName": "approve", "methodType": "GROOVY", "ruleIdentifier": rule_id,
                          "script": script, "parameters": []}]}]})
        self.rep["contexts"] = [{"id": None, "identifier": "c1", "name": "App", "alias": "app",
                                 "crudAliases": ["invoice"]}]
        rule = {"id": None, "identifier": rule_id, "name": "crud_invoice_approve", "executor": "GroovyExecutionRule",
                "ruleType": "EXECUTION_RULE", "status": "ACTIVE", "hidden": True,
                "rule": {"ruleScriptStr": script.replace("\n", "\r\n") + "  "}}
        self.rep["rules"] = [rule]
        self.write("rep-objects.json", self.rep)
        self.assertNotIn("are different texts", run("validate", "--project", self.proj).stdout,
                         "line endings and trailing blanks are the same body")

        rule["rule"]["ruleScriptStr"] = "return [done: 'old']\n"
        self.write("rep-objects.json", self.rep)
        self.assertIn("are different texts", run("validate", "--project", self.proj).stdout,
                      "the import keeps the carried rule, so the edited script would never run")

        self.rep["rules"] = []
        self.write("rep-objects.json", self.rep)
        self.assertNotIn("are different texts", run("validate", "--project", self.proj).stdout,
                         "without the rule the import builds it from the script")

    def test_an_unreadable_entry_is_evidence_of_nothing_and_the_rest_still_counts(self):
        with open(self.path("workflow-history.json"), "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        parts = core.archive_parts(core.Project(self.proj))
        flagged = [label for heading, label, *_rest in parts if heading == "!"]
        self.assertEqual(["workflow-history.json"], flagged)
        offered = {label: importable for heading, label, importable, _c, _w in parts if heading != "!"}
        self.assertFalse(offered["Version history"])
        self.assertTrue(offered["Pages, forms and rules"], "one damaged entry does not cost the rest of the file")

if __name__ == "__main__":
    unittest.main()
