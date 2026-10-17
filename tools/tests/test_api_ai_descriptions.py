"""The toolkit's reading of the descriptions for AI assistants an `apiExposures` entry may carry (doc 32 §3.16, §6).

These checks mirror what the platform does on import, so they are written as the same cases the platform's own tests
pin: which keys an endpoint has, what is stored of a text, how long it counts, and what `api-exposures show` and
`validate --keep-api-exposures` say. If the platform's cleaning rule or its operation keys change, this file
changes with them — it is the one place the Python mirror is compared with the rules.

Every invisible or look-alike character below is written as an escape, never typed: an editor that strips or
normalises what it cannot show would otherwise leave tests that pass while checking nothing.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import os
import sys
import unicodedata
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mrjunkit import core  # noqa: E402


def table(kind, *actions):
    return {"kind": kind, "slug": "orders", "actions": list(actions)}


def action(action_id, origin):
    return {"actionId": action_id, "origin": origin}


class OperationKeys(unittest.TestCase):
    def test_a_process_table_has_list_read_and_each_action_by_origin(self):
        entry = table("PROCESS_TABLE", action("approve", "TASK"), action("cancel", "GLOBAL"), action("new", "START"))
        self.assertEqual(core.api_exposure_ai_operation_keys(entry),
                         ["list", "read", "action:TASK:approve", "action:GLOBAL:cancel", "action:START:new"])

    def test_an_action_of_an_origin_the_kind_cannot_offer_is_not_an_operation(self):
        entry = table("CRUD_TABLE", action("archive", "ROW"), action("x", "TASK"), action("", "ROW"), "junk")
        self.assertEqual(core.api_exposure_ai_operation_keys(entry), ["list", "read", "action:ROW:archive"])

    def test_a_rule_endpoint_has_its_operations_by_trimmed_id_and_a_sign_in_has_none(self):
        rule = {"kind": "RULE", "operations": [{"operationId": " op-1 "}, {"operationId": " "}, {"ruleIdentifier": "r"}]}
        self.assertEqual(core.api_exposure_ai_operation_keys(rule), ["rule:op-1"])
        self.assertEqual(core.api_exposure_ai_operation_keys({"kind": "LOGIN"}), [])

    def test_an_id_is_trimmed_as_the_platform_trims_and_a_number_is_its_text(self):
        # String.trim() removes what is <= U+0020 and keeps a no-break space; a number read into a text field is its text
        rule = {"kind": "RULE", "operations": [{"operationId": "\u00a0op"}, {"operationId": 7}, {"operationId": "\t x \n"}]}
        self.assertEqual(core.api_exposure_ai_operation_keys(rule), ["rule:\u00a0op", "rule:7", "rule:x"])

    def test_odd_input_is_no_operation_and_no_crash(self):
        for entry in ({"kind": ["x"]}, {"kind": None}, {"kind": "CRUD_TABLE", "actions": 5},
                      {"kind": "RULE", "operations": "x"}):
            self.assertIsInstance(core.api_exposure_ai_operation_keys(entry), list)


class Cleaning(unittest.TestCase):
    clean = staticmethod(core.api_exposure_ai_clean)

    def test_line_breaks_are_one_newline(self):
        self.assertEqual(self.clean("one\r\ntwo\rthree"), "one\ntwo\nthree")

    def test_invisible_characters_that_carry_no_text_are_gone(self):
        self.assertEqual(self.clean("a\u200bb\u2060c\ufeffd\u202ee\U000e0041f"), "abcdef")

    def test_the_edges_of_every_dropped_range_are_dropped_and_the_text_beside_them_is_not(self):
        for code_point in (0x200B, 0x2060, 0x2061, 0x2064, 0x206A, 0x206F, 0xFEFF, 0xFFF9, 0xFFFB, 0x202A, 0x202D, 0x202E,
                           0x2066, 0x2067, 0x2069, 0xE0000, 0xE0020, 0xE007F):
            self.assertEqual(self.clean("a" + chr(code_point) + "b"), "ab", hex(code_point))
        self.assertEqual(self.clean("a\u205fb"), "a\u205fb")
        self.assertEqual(self.clean("a\u200cb\u200dc\u200ed\u200f"), "a\u200cb\u200dc\u200ed\u200f")
        self.assertEqual(self.clean("\u3000\u2003x\u2003\u3000"), "x")

    def test_controls_other_than_newline_and_tab_and_lone_surrogates_are_gone(self):
        self.assertEqual(self.clean("a\tb\x00\x07\nc\x85\ud800"), "a\tb\nc")

    def test_what_scripts_and_emoji_need_stays(self):
        for text in ("a\u200db\u200cc\u200ed\u200f", "\U0001f469\u200d\U0001f4bb"):
            self.assertEqual(self.clean(text), text)

    def test_normal_form_and_trimming_keep_a_no_break_space_as_the_platform_does(self):
        self.assertEqual(self.clean("cafe\u0301"), "caf\u00e9")
        self.assertEqual(self.clean("  \n x \t "), "x")
        self.assertEqual(self.clean("\u00a0x"), "\u00a0x")
        self.assertEqual(self.clean(" \u200b \r\n "), "")

    def test_cleaning_is_idempotent_because_what_is_dropped_goes_before_normalisation(self):
        # an invisible character between a letter and its accent keeps them from composing, if normalised first
        for text in ("a\u202e\u0308", "e\u200b\u0301", "A\u030a", "cafe\u0301\u202eX", "x\r\ny\u2060\u0323\u0307",
                     "\u1112\u1161\u11ab", "a\u0301\u0300\u0323", " \u200b\u0301x "):
            once = self.clean(text)
            self.assertEqual(self.clean(once), once, repr(text))
        self.assertEqual(self.clean("a\u202e\u0308"), "\u00e4")

    def test_cleaning_is_idempotent_where_normalisation_makes_more_marks(self):
        # one character that decomposes into two marks makes a run LONGER than the one that was cut before normalising
        for text in ("\u0344" * 16, "a" + "\u0344" * 16, "\u0958" + "\u0301" * 30, "a\u0344" * 40,
                     "\u0344" * 15 + "\u0301" * 2):
            once = self.clean(text)
            self.assertEqual(self.clean(once), once, repr(text))
            self.assertEqual(unicodedata.normalize("NFC", once), once)

    def test_cleaning_is_idempotent_for_every_mark_and_every_character_normalisation_changes(self):
        checked = 0
        for code_point in range(0x20000):
            ch = chr(code_point)
            category = unicodedata.category(ch)
            if category in ("Cs", "Cn"):
                continue
            if category not in ("Mn", "Me", "Mc") and unicodedata.normalize("NFC", ch) == ch:
                continue
            for length in (1, 2, 15, 16, 29, 30, 31, 45, 61):
                for text in (ch * length, "a" + ch * length, "a" + "\u0301" * length + ch):
                    once = self.clean(text)
                    self.assertEqual(self.clean(once), once, "U+%04X x%d" % (code_point, length))
                    checked += 1
        self.assertGreater(checked, 10000, "the filter must not skip the marks")

    def test_a_run_of_marks_is_cut_where_no_text_reaches(self):
        accent = "\u0301"
        at_the_cut = self.clean("a" + accent * core.API_AI_MAX_MARK_RUN)
        self.assertEqual(self.clean("a" + accent * (core.API_AI_MAX_MARK_RUN + 1)), at_the_cut)
        self.assertEqual(self.clean("a" + accent * 100000), at_the_cut)
        self.assertEqual(self.clean("a" + accent * 500 + "a" + accent * 500), at_the_cut + at_the_cut)


class Limit(unittest.TestCase):
    def problems(self, texts, entry=None):
        entry = entry or table("PROCESS_TABLE")
        entry = dict(entry, aiDescriptions=texts)
        return core.api_exposure_ai_problems({"apiExposures": [entry]})

    def test_a_line_break_counts_once_and_what_is_not_stored_does_not_count(self):
        limit = core.API_AI_DESCRIPTION_MAX_LENGTH
        self.assertEqual(self.problems({"list": "a" * (limit - 2) + "\r\nb"}), [])
        self.assertEqual(self.problems({"list": "a" * limit + "\u200b" * 10}), [])

    def test_an_emoji_is_two_units(self):
        limit = core.API_AI_DESCRIPTION_MAX_LENGTH
        self.assertEqual(self.problems({"list": "\U0001f600" * (limit // 2)}), [])
        over = self.problems({"list": "\U0001f600" * (limit // 2 + 1)})
        self.assertEqual([code for _slug, code, _key, _words in over], ["too_long"])

    def test_a_text_beyond_the_raw_bound_is_too_long_without_being_cleaned(self):
        over = self.problems({"list": "\u200b" * (core.API_AI_RAW_MAX_LENGTH + 1)})
        self.assertEqual([code for _slug, code, _key, _words in over], ["too_long"])

    def test_more_texts_than_an_endpoint_could_have_refuse_the_list(self):
        many = {"action:ROW:a%d" % i: "x" for i in range(core.API_AI_MAX_TEXTS + 1)}
        over = self.problems(many)
        self.assertEqual([(code, key) for _slug, code, key, _words in over], [("too_many", "")])
        at_the_cap = self.problems({k: "x" for k in list(many)[:core.API_AI_MAX_TEXTS]})
        self.assertNotIn("too_many", {code for _slug, code, _key, _words in at_the_cap}, "the cap itself is allowed")

    def test_a_text_over_the_limit_under_an_unknown_key_is_still_refused(self):
        over = self.problems({"nonsense": "b" * (core.API_AI_DESCRIPTION_MAX_LENGTH + 1)})
        self.assertEqual([code for _slug, code, _key, _words in over], ["too_long"])

    def test_an_unknown_key_is_only_dropped_and_a_wrong_shape_is_unreadable(self):
        self.assertEqual([code for _s, code, _k, _w in self.problems({"nope": "x"})], ["unknown_key"])
        for texts in (["x"], "x", 5):
            self.assertEqual([code for _s, code, _k, _w in self.problems(texts)], ["shape"])
        self.assertEqual([code for _s, code, _k, _w in self.problems({"list": {"a": 1}})], ["shape"])
        # numbers and booleans are read as their text, which is stored
        self.assertEqual(self.problems({"list": 5, "read": True}), [])


class ShowTag(unittest.TestCase):
    note = staticmethod(core.api_exposure_ai_note)

    def test_nothing_when_the_entry_says_nothing_and_a_count_of_what_would_be_stored(self):
        self.assertEqual(self.note({"kind": "CRUD_TABLE"}), "")
        self.assertEqual(self.note({"kind": "CRUD_TABLE", "aiDescriptions": None}), "")
        entry = {"kind": "CRUD_TABLE", "aiDescriptions": {"list": "x", "read": 5, "bogus": "y", "ignored": " "}}
        self.assertEqual(self.note(entry), "  [AI texts: 2]")

    def test_an_empty_set_clears_and_a_sign_in_stores_nothing(self):
        self.assertIn("CLEARS", self.note({"kind": "CRUD_TABLE", "aiDescriptions": {}}))
        self.assertIn("none stored", self.note({"kind": "LOGIN", "aiDescriptions": {"list": "x"}}))

    def test_a_malformed_member_says_the_archive_cannot_be_read(self):
        self.assertIn("cannot be read", self.note({"kind": "CRUD_TABLE", "aiDescriptions": ["x"]}))
        self.assertIn("cannot be read", self.note({"kind": "CRUD_TABLE", "aiDescriptions": {"list": [1]}}))


class Printing(unittest.TestCase):
    def test_a_lone_surrogate_in_a_key_does_not_crash_the_output(self):
        import io
        import contextlib
        buffer = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")
        with contextlib.redirect_stdout(buffer):
            core.out("a key \ud800 in a hand-edited archive")
        buffer.flush()
        self.assertIn(b"\\ud800", buffer.buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
