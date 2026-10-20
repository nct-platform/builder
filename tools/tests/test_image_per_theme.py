"""The validator's reading of an image's per-theme versions (`perTheme` + `urlByTheme`, doc 14 §1.5).

Every case below is one the platform accepts in silence and then renders the default image under every theme, so the
validator is the only place it can be caught.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mrjunkit import validate_cmds  # noqa: E402


class Recorder:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def image(per_theme=None, by_theme=None, by_theme_raw=None):
    props = {"url": {"key": "url", "propertyType": "STRING", "stringValue": "images/logo.png"}}
    if per_theme is not None:
        props["perTheme"] = {"key": "perTheme", "propertyType": "BOOLEAN", "booleanValue": per_theme}
    if by_theme is not None or by_theme_raw is not None:
        props["urlByTheme"] = {"key": "urlByTheme", "propertyType": "STRING",
                               "stringValue": by_theme_raw if by_theme_raw is not None else json.dumps(by_theme)}
    return {"pluginName": "nct.image.plugin", "name": "logo-plugin", "properties": props}, props


def check(node_and_props):
    node, props = node_and_props
    r = Recorder()
    validate_cmds._check_image_per_theme(node, props, r)
    return r


class PerThemeImage(unittest.TestCase):
    def test_a_classic_image_is_not_touched(self):
        r = check(image())
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_a_correct_per_theme_image_is_clean(self):
        r = check(image(True, {"Standard": "images/dark-ink.png", "Dark Blue": "images/light-ink.png"}))
        self.assertEqual((r.errors, r.warnings), ([], []))

    def test_switched_off_with_variants_kept_is_a_warning_not_an_error(self):
        r = check(image(False, {"Dark": "images/light-ink.png"}))
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("NEVER shown", r.warnings[0])

    def test_variants_without_the_switch_at_all_are_flagged(self):
        r = check(image(None, {"Dark": "images/light-ink.png"}))
        self.assertIn("perTheme is not true", r.warnings[0])

    def test_a_key_that_is_not_an_exact_skin_name_matches_nothing(self):
        r = check(image(True, {"dark": "images/a.png", "DarkBlue": "images/b.png", "Forest": "images/c.png"}))
        self.assertEqual(sorted(w.split("key ")[1].split(" ")[0] for w in r.warnings), ["'DarkBlue'", "'dark'"])

    def test_unreadable_json_and_a_non_object_are_errors(self):
        self.assertIn("not valid JSON", check(image(True, by_theme_raw="{Dark: x")).errors[0])
        self.assertIn("must be a JSON object", check(image(True, by_theme_raw='["images/a.png"]')).errors[0])

    def test_a_tenant_prefixed_or_empty_path_is_flagged(self):
        r = check(image(True, {"Dark": "t/42/7/fixed/400-250/a.png", "Forest": ""}))
        self.assertEqual(len(r.warnings), 2)
        self.assertTrue(any("tenant prefix" in w for w in r.warnings))
        self.assertTrue(any("not an image path" in w for w in r.warnings))

    def test_a_map_stored_the_way_mcp_stores_an_object_is_read_too(self):
        node, props = image(True)
        props["urlByTheme"] = {"key": "urlByTheme", "propertyType": "LOCALIZED_STRING",
                               "localizedStringValue": {"Darkk": "images/a.png"}}
        r = check((node, props))
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("'Darkk'", r.warnings[0])


if __name__ == "__main__":
    unittest.main()
