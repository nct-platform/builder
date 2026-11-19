"""The validator's reading of who can open a file (doc 02 "Secure attachments", doc 14 §1.5 "Who can see the image",
doc 16 §2.19): a File Upload field's `accessLevel`, an image's `access`, the secure files and access records an archive
carries in tenant-files/secure/, and `service.files` in rules.

Most cases below are ones the platform accepts in silence: a level it does not read is PUBLIC - the files open for
anyone with their link - and a record it cannot read is left out - the file opens for nobody. The rest are refused
only when a rule first runs.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from mrjunkit import validate_cmds  # noqa: E402


class Recorder:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


class _Cruds:
    def __init__(self, cruds):
        self.data = {"cruds": cruds}


class _Project:
    """Just what the checks read: the bundle folder, the rules, the role groups, the dynamic CRUDs."""

    def __init__(self, root=None, rules=(), role_groups=None, cruds=None):
        self.root = root or "/nonexistent-bundle"
        self.rep = {"rules": [{"name": name, "ruleType": rule_type, "rule": {"ruleScriptStr": script}}
                              for name, rule_type, script in rules]}
        if role_groups is not None:
            self.rep["roleGroups"] = [{"name": name} for name in role_groups]
        self.cruds_file = _Cruds(cruds) if cruds else None


def text(key, value):
    """A STRING property the way an export writes it."""
    return {"arguments": {}, "localizedStringValue": {}, "key": key, "stringValue": value, "required": False,
            "propertyType": "STRING", "hidden": False}


def upload(settings_raw):
    props = {"settings": {"key": "settings", "propertyType": "STRING", "stringValue": settings_raw}}
    return {"pluginName": "dynaform.form.file.upload.field.plugin", "name": "documents-plugin", "properties": props}, props


def check_upload(settings=None, raw=None):
    node, props = upload(raw if raw is not None else json.dumps(settings))
    r = Recorder()
    validate_cmds._check_file_upload_access_level(node, props, r)
    return r


def image(url="fixed/logo.png", access=None, by_theme=None, access_prop=None):
    props = {"url": text("url", url)}
    if access is not None:
        props["access"] = text("access", access)
    if access_prop is not None:
        props["access"] = access_prop
    if by_theme is not None:
        props["perTheme"] = {"key": "perTheme", "propertyType": "BOOLEAN", "booleanValue": True}
        props["urlByTheme"] = text("urlByTheme", json.dumps(by_theme))
    return {"pluginName": "nct.image.plugin", "name": "logo-plugin", "properties": props}, props


class _Bundle(unittest.TestCase):
    """A bundle folder of its own for every test: tenant-files/ is what the checks read."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="secure-files-")
        self.addCleanup(shutil.rmtree, self.root)

    def put(self, rel, content=b"x"):
        path = os.path.join(self.root, "tenant-files", *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode("utf-8"))

    def put_record(self, rel, record):
        self.put("secure/.acl/%s.json" % rel, record if isinstance(record, str) else json.dumps(record))

    def check_image(self, node_and_props):
        node, props = node_and_props
        r = Recorder()
        validate_cmds._check_image_access(_Project(self.root), node, props, r)
        return r

    def check_files(self):
        r = Recorder()
        validate_cmds._check_secure_tenant_files(_Project(self.root), r)
        return r


class FileUploadAccessLevel(unittest.TestCase):

    def test_no_level_and_the_three_levels_are_clean(self):
        for settings in ({"uploadPath": "uploads/"}, {"accessLevel": None}, {"accessLevel": "PUBLIC"},
                         {"accessLevel": "PROJECT"}, {"accessLevel": "RESTRICTED"}):
            r = check_upload(settings)
            self.assertEqual((r.errors, r.warnings), ([], []), settings)

    def test_another_letter_case_is_no_level_and_says_how_to_write_it(self):
        r = check_upload({"accessLevel": "Restricted"})
        self.assertEqual(len(r.errors), 1)
        self.assertIn("PUBLIC", r.errors[0])
        self.assertIn('write "RESTRICTED"', r.errors[0])

    def test_a_word_that_is_no_level_is_an_error(self):
        r = check_upload({"accessLevel": "PRIVATE"})
        self.assertEqual(len(r.errors), 1)
        self.assertIn("is no level", r.errors[0])
        self.assertNotIn("write", r.errors[0])

    def test_a_value_that_is_no_text_loses_every_setting(self):
        for value in (True, ["RESTRICTED"], {"level": "RESTRICTED"}):
            r = check_upload({"accessLevel": value})
            self.assertEqual(len(r.errors), 1, value)
            self.assertIn("EVERY setting", r.errors[0])

    def test_malformed_settings_are_left_to_the_inner_json_check(self):
        r = check_upload(raw="{accessLevel: RESTRICTED")
        self.assertEqual((r.errors, r.warnings), ([], []))


class ImageAccess(_Bundle):

    def test_a_public_image_is_not_touched(self):
        r = self.check_image(image())
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_secure_image_in_its_library_with_its_file_is_clean_in_any_letter_case(self):
        self.put("secure/images/project/400-250/a1b2c3d4e5f60718-logo.png")
        r = self.check_image(image("secure/images/project/400-250/a1b2c3d4e5f60718-logo.png", access=" project "))
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_an_access_that_is_no_level_is_public(self):
        r = self.check_image(image(access="PRIVATE"))
        self.assertEqual(len(r.errors), 1)
        self.assertIn("reads it as PUBLIC", r.errors[0])

    def test_an_access_kept_in_another_slot_is_public(self):
        prop = text("access", "")
        prop["localizedStringValue"] = {"en": "RESTRICTED"}
        r = self.check_image(image(access_prop=prop))
        self.assertEqual(len(r.errors), 1)
        self.assertIn("not kept as a text", r.errors[0])

    def test_an_empty_access_is_the_absent_one(self):
        r = self.check_image(image(access=""))
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_secure_level_over_a_public_file_is_an_error_for_every_path(self):
        r = self.check_image(image("fixed/logo.png", access="RESTRICTED",
                                   by_theme={"Dark": "fixed/logo-light.png"}))
        self.assertEqual(len(r.errors), 2)
        self.assertTrue(all("not a file of the project's secure area" in e for e in r.errors))
        self.assertTrue(any("urlByTheme['Dark']" in e for e in r.errors))
        self.assertTrue(all("secure/images/restricted/" in e for e in r.errors))

    def test_an_absolute_url_is_no_secure_file_either(self):
        r = self.check_image(image("abs(https://example.com/a.png)", access="PROJECT"))
        self.assertEqual(len(r.errors), 1)

    def test_an_image_in_the_other_level_library_is_a_warning(self):
        self.put("secure/images/project/400-250/a.png")
        r = self.check_image(image("secure/images/project/400-250/a.png", access="RESTRICTED"))
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("in the project library", r.warnings[0])

    def test_a_secure_image_the_archive_does_not_carry_is_a_warning_whatever_the_access(self):
        for access in ("PROJECT", None):
            r = self.check_image(image("secure/images/project/400-250/gone.png", access=access))
            self.assertEqual(r.errors, [], access)
            self.assertEqual(len(r.warnings), 1, access)
            self.assertIn("shows NOTHING", r.warnings[0])

    def test_a_tenant_prefix_is_looked_through(self):
        self.put("secure/images/project/400-250/a.png")
        r = self.check_image(image("t/376/secure/images/project/400-250/a.png", access="PROJECT"))
        self.assertEqual((r.errors, r.warnings), ([], []))


class SecureTenantFiles(_Bundle):

    STORED = {"version": 1, "level": "RESTRICTED", "realm": "saas", "client": "ggg", "owner": "author@example.com",
              "createdAt": 1794944557449, "updatedAt": 1794944557449,
              "grants": [{"subject": "ROLE_GROUP", "name": "Accountants", "access": "READ"},
                         {"subject": "USER", "name": "anna@example.com", "access": "EDIT"}]}

    def test_no_tenant_files_and_no_secure_area_are_clean(self):
        self.assertEqual((self.check_files().errors, self.check_files().warnings), ([], []))
        self.put("fixed/logo.png")
        r = self.check_files()
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_record_the_storage_wrote_is_clean(self):
        self.put("secure/claude-test/0c7da22468ca4880/Հաշիվ 15.pdf")
        self.put_record("claude-test/0c7da22468ca4880/Հաշիվ 15.pdf", self.STORED)
        r = self.check_files()
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_the_hand_built_records_of_doc_14_are_clean(self):
        self.put("secure/images/project/400-250/logo.png")
        self.put_record("images/project/400-250/logo.png", {"level": "PROJECT"})
        self.put("secure/images/restricted/400-250/plan.png")
        self.put_record("images/restricted/400-250/plan.png",
                        {"level": "RESTRICTED", "grants": [{"subject": "ROLE_GROUP", "name": "Staff", "access": "READ"}]})
        r = self.check_files()
        self.assertEqual((r.errors, r.warnings), ([], []))

    def record_problems(self, record):
        self.put("secure/docs/a.pdf")
        self.put_record("docs/a.pdf", record)
        return self.check_files()

    def test_a_level_not_spelled_exactly_drops_the_record(self):
        r = self.record_problems({"level": "Project"})
        self.assertEqual(len(r.errors), 1)
        self.assertIn('write "PROJECT"', r.errors[0])
        self.assertIn("opens for NOBODY", r.errors[0])

    def test_a_public_or_missing_level_drops_the_record(self):
        for record in ({"level": "PUBLIC"}, {"grants": []}, {"level": "PRIVATE"}):
            r = self.record_problems(record)
            self.assertEqual(len(r.errors), 1, record)

    def test_a_subject_or_an_access_not_spelled_exactly_drops_the_whole_record(self):
        for grant in ({"subject": "ROLEGROUP", "name": "Staff", "access": "READ"},
                      {"subject": "ROLE_GROUP", "name": "Staff", "access": "WRITE"},
                      {"subject": "role_group", "name": "Staff", "access": "READ"}):
            r = self.record_problems({"level": "RESTRICTED", "grants": [grant]})
            self.assertEqual(len(r.errors), 1, grant)
            self.assertIn("grant 1", r.errors[0])

    def test_fields_of_the_wrong_kind_make_the_record_unreadable(self):
        for record in ({"level": "PROJECT", "grants": {"subject": "USER"}}, {"level": "PROJECT", "grants": ["Staff"]},
                       {"level": "PROJECT", "createdAt": "yesterday"}, {"level": "PROJECT", "owner": {"e": 1}}):
            r = self.record_problems(record)
            self.assertEqual(len(r.errors), 1, record)

    def test_a_number_written_as_digits_is_read(self):
        r = self.record_problems({"level": "PROJECT", "version": "1", "createdAt": "1794944557449"})
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_grant_the_import_drops_is_a_warning(self):
        for grant in ({"subject": "ROLE_GROUP", "access": "READ"}, {"subject": "ROLE_GROUP", "name": " ", "access": "READ"},
                      {"subject": "ROLE_GROUP", "name": "Staff", "access": "NONE"},
                      {"name": "Staff", "access": "READ"}, {"subject": "USER", "name": "anna@example.com"}):
            r = self.record_problems({"level": "PROJECT", "grants": [grant]})
            self.assertEqual(r.errors, [], grant)
            self.assertEqual(len(r.warnings), 1, grant)
            self.assertIn("dropped by the import", r.warnings[0])

    def test_a_restricted_file_nobody_may_open_is_a_warning(self):
        r = self.record_problems({"level": "RESTRICTED"})
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("neither an owner nor a grant", r.warnings[0])

    def test_a_misspelt_key_is_ignored_by_the_storage_and_said(self):
        r = self.record_problems({"level": "RESTRICTED", "owner": "a@example.com",
                                  "grant": [{"subject": "ROLE_GROUP", "name": "Staff", "access": "READ"}]})
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("grant", r.warnings[0])
        r = self.record_problems({"level": "PROJECT", "grants": [{"subject": "ROLE_GROUP", "group": "Staff",
                                                                  "name": "Staff", "access": "READ"}]})
        self.assertEqual(len(r.warnings), 1)

    def test_a_user_named_by_no_email_is_a_warning(self):
        r = self.record_problems({"level": "RESTRICTED", "grants": [{"subject": "USER", "name": "Anna", "access": "READ"}]})
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("no e-mail", r.warnings[0])

    def test_a_record_that_is_no_json_drops_it(self):
        r = self.record_problems("{level: PROJECT")
        self.assertEqual(len(r.errors), 1)
        self.assertIn("cannot be read as JSON", r.errors[0])

    def test_a_secure_file_without_its_record_opens_for_nobody(self):
        self.put("secure/docs/a.pdf")
        self.put("secure/.DS_Store")
        r = self.check_files()
        self.assertEqual(len(r.errors), 1)
        self.assertIn("has no access record", r.errors[0])
        self.assertIn("secure/.acl/docs/a.pdf.json", r.errors[0])

    def test_a_record_without_its_file_and_a_non_record_are_warnings(self):
        self.put_record("docs/gone.pdf", {"level": "PROJECT"})
        self.put("secure/.acl/docs/notes.txt")
        r = self.check_files()
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 2)
        self.assertTrue(any("has no file" in w for w in r.warnings))
        self.assertTrue(any("is no access record" in w for w in r.warnings))

    def test_a_case_variant_of_the_area_is_refused_by_the_storage(self):
        self.put("Secure/docs/a.pdf")
        r = self.check_files()
        self.assertEqual(len(r.errors), 1)
        self.assertIn("tenant-files/Secure/", r.errors[0])
        self.assertIn("in lower case", r.errors[0])

    def test_a_case_variant_of_the_records_is_refused_by_the_storage(self):
        self.put("secure/docs/b.pdf")
        self.put("secure/.ACL/docs/b.pdf.json", json.dumps({"level": "PROJECT"}))
        r = self.check_files()
        self.assertEqual(len(r.errors), 2)
        self.assertTrue(any("secure/.ACL/" in e and "in lower case" in e for e in r.errors))
        # b.pdf has no record the storage takes, and the variant's own entries are not read as files of the area
        self.assertTrue(any("secure/docs/b.pdf has no access record" in e for e in r.errors))


def files_check(*rules, role_groups=None, cruds=None):
    r = Recorder()
    validate_cmds._check_rule_uses_files(_Project(rules=rules, role_groups=role_groups, cruds=cruds), r)
    return r


def rule(script, rule_type="EXECUTION_RULE", name="Save documents"):
    return name, rule_type, script


class RulesUseFiles(unittest.TestCase):

    def test_the_documented_calls_are_silent(self):
        r = files_check(rule("""
            def record = context.client.documents.data.get()
            service.files.grant(record.documents, roleGroups: ['Accountants'], access: 'READ')
            service.files.grant(roleGroups: ['Accountants'], access: 'READ')
            service.files.grant(context.client.documents, users: [record.ownerEmail], access: 'EDIT')
            service.files.grant('t/376/secure/images/restricted/400-250/a.png', roleGroups: ['accountants'])
            service.files.grant(record.documents, [roleGroups: ['Accountants', 'Staff'], access: 'edit'])
            service.files.revoke(roleGroups: ['Accountants'], files: record.documents)
            def found = service.files.find()
            def who = service.files.access(record.documents)
            return found
            """), role_groups=["Accountants", "Staff"])
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_predicate_a_validation_rule_or_a_rule_they_call_may_not_use_it(self):
        r = files_check(rule("service.files.grant(x, roleGroups: ['Staff'])\nreturn 1", name="Grant"),
                        rule("return service.files.find(x).size() > 0", "PREDICATE", "Can open"),
                        rule("service.files.access(x)", "VALIDATION_RULE", "Check"),
                        rule("service.rule('Grant')\nreturn true", "PREDICATE", "Indirect"))
        self.assertEqual(len(r.errors), 3)
        self.assertTrue(any("'Can open'" in e and "PREDICATE" in e for e in r.errors))
        self.assertTrue(any("'Check'" in e and "VALIDATION_RULE" in e for e in r.errors))
        self.assertTrue(any("'Indirect'" in e and "refusal follows the call" in e for e in r.errors))

    def test_a_member_that_does_not_exist_in_any_spelling(self):
        r = files_check(rule("service.files.list()\nservice?.files?.share(x, roleGroups: ['A'])\n"
                             "service.files['allow'](x)\nservice.files.with { grant(x, users: ['a@b.c']) }"))
        self.assertEqual(sorted(e.split("service.files.")[1].split(",")[0] for e in r.errors),
                         ["allow", "list", "share"])

    def test_an_option_that_does_not_exist_or_an_access_on_a_revoke_is_refused(self):
        r = files_check(rule("service.files.grant(x, groups: ['Staff'])\n"
                             "service?.files?.grant([roles: ['Staff']])\n"
                             "service.files.revoke(x, roleGroups: ['Staff'], access: 'READ')"))
        self.assertEqual(len(r.errors), 3)
        self.assertTrue(any("'groups'" in e for e in r.errors))
        self.assertTrue(any("'roles'" in e for e in r.errors))
        self.assertTrue(any("takes no access:" in e for e in r.errors))

    def test_an_access_that_is_neither_read_nor_edit_is_refused(self):
        r = files_check(rule("service.files.grant(x, roleGroups: ['Staff'], access: 'WRITE')\n"
                             "service.files.grant(x, roleGroups: ['Staff'], access: ' Read ')\n"
                             "service.files.grant(x, roleGroups: ['Staff'], access: level)"))
        self.assertEqual(len(r.errors), 1)
        self.assertIn("'WRITE'", r.errors[0])

    def test_a_call_in_a_comment_or_a_text_is_no_call(self):
        r = files_check(rule("// service.files.list()\n/* service.files.grant(x, groups: ['A']) */\n"
                             "def help = 'call service.files.share(x) to share'\nreturn help"),
                        rule("// service.files.grant(x, roleGroups: ['A'])\nreturn true", "PREDICATE", "Can open"))
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_grant_to_a_role_group_the_project_has_not_is_one_warning_per_name(self):
        r = files_check(rule("service.files.grant(x, roleGroups: ['Accountants'])\n"
                             "service.files.grant(y, roleGroups: ['accountants', 'Staff'], access: 'READ')\n"
                             "service.files.revoke(x, roleGroups: ['Gone'])"),
                        role_groups=["Staff"])
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("'Accountants'", r.warnings[0])

    def test_role_groups_are_not_judged_when_the_archive_carries_none(self):
        r = files_check(rule("service.files.grant(x, roleGroups: ['Accountants'])"))
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_crud_method_must_say_on_what(self):
        crud = {"alias": "documents", "methods": [
            {"methodName": "share", "methodType": "GROOVY",
             "script": "service.files.grant(roleGroups: ['Staff'], access: 'READ')"},
            {"methodName": "shareThese", "methodType": "GROOVY",
             "script": "service.files.grant(param.files, roleGroups: ['Staff'])\n"
                       "service.files.revoke(roleGroups: ['Staff'], files: param.old)"}]}
        r = files_check(cruds=[crud])
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("'share'", r.warnings[0])
        self.assertIn("session store", r.warnings[0])


if __name__ == "__main__":
    unittest.main()
