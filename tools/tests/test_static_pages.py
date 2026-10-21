"""Static pages (doc 34): the toolkit commands write the shape the platform serves, and the validator catches
every case the platform answers with a 404 or never reaches.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import hashlib
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

from mrjunkit import staticpage_cmds, validate_cmds  # noqa: E402

MRJUN = os.path.join(TOOLS, "mrjun.py")
EMPTY = os.path.join(TOOLS, "..", "initialtemplates", "empty.mrjun")


def run(*args):
    return subprocess.run([sys.executable, MRJUN] + list(args), capture_output=True, text=True)


class StaticPageCommandsTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "proj")
        self.assertEqual(0, run("unpack", EMPTY, self.proj).returncode)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def root(self):
        with open(os.path.join(self.proj, "branches.json"), encoding="utf-8") as fh:
            branches = json.load(fh)
        return branches[0]["rootContent"]

    def page(self, alias):
        return next(c for c in self.root()["children"] if c.get("alias") == alias)

    def validate(self):
        return run("validate", "--project", self.proj).stdout

    def test_text_and_file_pages_have_the_served_shape_and_validate_clean(self):
        before = self.validate()
        text = os.path.join(self.tmp, "robots.txt")
        with open(text, "wb") as fh:
            fh.write(b"\xef\xbb\xbfUser-agent: *\r\nDisallow:\r\n")
        binary = os.path.join(self.tmp, "Logo Final.png")
        with open(binary, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\nxx")
        self.assertEqual(0, run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "Robots",
                                "--alias", "robots.txt", "--text-file", text, "--public").returncode)
        r = run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "Logo",
                "--alias", "logo.png", "--file", binary)
        self.assertEqual(0, r.returncode, r.stderr)

        robots = self.page("robots.txt")
        props = robots["properties"]
        self.assertEqual("static", props["pageType"]["stringValue"])
        self.assertEqual("User-agent: *\nDisallow:\n", props["staticBody"]["stringValue"], "BOM dropped, LF")
        self.assertEqual([], robots["children"])
        self.assertTrue(robots["roleAccess"]["publicReadAccess"])

        logo = self.page("logo.png")["properties"]
        sha = hashlib.sha256(b"\x89PNG\r\n\x1a\nxx").hexdigest()
        self.assertEqual("static-pages/%s/Logo-Final.png" % sha, logo["staticFilePath"]["stringValue"])
        self.assertEqual("LONG", logo["staticFileSize"]["propertyType"])
        self.assertEqual(10, logo["staticFileSize"]["longValue"])
        self.assertTrue(os.path.isfile(os.path.join(self.proj, "tenant-files", "static-pages", sha, "Logo-Final.png")))

        self.assertEqual(before.splitlines()[2:], self.validate().splitlines()[2:],
                         "valid static pages add no finding (and are exempt from the nav-reachability warning)")

    def test_set_static_replaces_a_file_with_text_and_can_turn_back(self):
        binary = os.path.join(self.tmp, "a.pdf")
        with open(binary, "wb") as fh:
            fh.write(b"%PDF-1.4 x")
        run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "Doc",
            "--alias", "doc.pdf", "--file", binary)
        self.assertEqual(0, run("page", "set-static", "--project", self.proj, "--page", "Doc",
                                "--text", "hello", "--content-type", "text/plain").returncode)
        props = self.page("doc.pdf")["properties"]
        self.assertNotIn("staticFilePath", props, "a new text replaces the stored file")
        self.assertEqual("text/plain", props["staticContentType"]["stringValue"])
        self.assertEqual(0, run("page", "set-static", "--project", self.proj, "--page", "Doc", "--dokie").returncode)
        props = self.page("doc.pdf")["properties"]
        self.assertEqual("dokie", props["pageType"]["stringValue"])
        self.assertEqual("hello", props["staticBody"]["stringValue"], "kept for switching back")

    def test_a_plus_in_a_file_name_never_reaches_the_stored_path(self):
        # file storage URL-decodes the path it reads: a '+' would be read back as a space and never be found.
        f = os.path.join(self.tmp, "c++ guide+v2.pdf")
        with open(f, "wb") as fh:
            fh.write(b"%PDF x")
        self.assertEqual(0, run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "G",
                                "--alias", "guide.pdf", "--file", f).returncode)
        path = self.page("guide.pdf")["properties"]["staticFilePath"]["stringValue"]
        self.assertNotIn("+", path)
        self.assertTrue(staticpage_cmds.FILE_PATH_RE.match(path), path)

    def test_a_refused_command_writes_no_file(self):
        f = os.path.join(self.tmp, "a.png")
        with open(f, "wb") as fh:
            fh.write(b"\x89PNG")
        run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "A", "--alias", "a.png",
            "--file", f, "--content-type", "not a type")
        self.assertFalse(os.path.isdir(os.path.join(self.proj, "tenant-files", "static-pages")))

    def test_bad_input_is_refused(self):
        self.assertNotEqual(0, run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "X",
                                   "--alias", "x.js", "--text", "x", "--content-type", "javascript").returncode)
        self.assertNotEqual(0, run("page", "add-static", "--project", self.proj, "--parent", "root", "--name", "X",
                                   "--alias", "x.js").returncode, "no response given")
        self.assertNotEqual(0, run("page", "set-static", "--project", self.proj, "--page", "root",
                                   "--text", "x").returncode, "the root cannot be static")


class Recorder:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


class Project:
    def __init__(self, root):
        self.root = root


def slot(key, value, kind="STRING"):
    field = "longValue" if kind == "LONG" else "stringValue"
    return {"key": key, "propertyType": kind, field: value}


def page(alias, children=None, **props):
    return {"pluginName": "siteMapPage", "name": alias, "alias": alias, "children": children or [],
            "properties": {k: slot(k, v, "LONG" if k == "staticFileSize" else "STRING") for k, v in props.items()}}


class StaticPageValidationTest(unittest.TestCase):

    def check(self, root, files=None):
        tmp = tempfile.mkdtemp()
        try:
            for rel, data in (files or {}).items():
                path = os.path.join(tmp, "tenant-files", *rel.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(data)
            r = Recorder()
            validate_cmds._check_static_pages(Project(tmp), root, r)
            return r
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_or_altered_file_is_an_error(self):
        sha = hashlib.sha256(b"abc").hexdigest()
        rel = "static-pages/%s/a.bin" % sha
        root = page("", [page("a.bin", pageType="static", staticFilePath=rel, staticFileSize=3)])
        self.assertEqual([], self.check(root, {rel: b"abc"}).errors)
        self.assertEqual(1, len(self.check(root).errors), "missing")
        self.assertEqual(1, len(self.check(root, {rel: b"abd"}).errors), "bytes do not hash to the path")

    def test_paths_types_sizes_and_structure(self):
        sha = "0" * 64
        root = page("", [
            page("abs.png", pageType="static", staticFilePath="t/1/static-pages/%s/a.png" % sha),
            page("bad.js", pageType="static", staticContentType="javascript"),
            page("big.txt", pageType="static", staticBody="x" * (staticpage_cmds.MAX_INLINE_TEXT_BYTES + 1)),
            page("parent.txt", [page("child")], pageType="static", staticBody="x"),
        ])
        r = self.check(root)
        self.assertEqual(4, len(r.errors), r.errors)

    def test_a_normal_page_with_a_file_alias_is_unreachable(self):
        r = self.check(page("", [page("about.html"), page("data.json"), page("about")]))
        self.assertEqual(1, len(r.warnings), r.warnings)
        self.assertIn("about.html", r.warnings[0])

    def test_the_root_cannot_be_static(self):
        self.assertEqual(1, len(self.check(page("", pageType="static", staticBody="x")).errors))


if __name__ == "__main__":
    unittest.main()
