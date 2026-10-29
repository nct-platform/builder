"""A rule sentence passed to service.global.locale.message('…') is translated by the platform (doc 16, doc 20): the
monolingual-rule-string check must not ask for every language inside it — that would hand the translator a sentence
in three languages at once — while a plain monolingual sentence is still reported. And the platform translates only
a text it can find before the call runs — one literal of the rule, one literal of a component's `t(…)` (doc 24 §9) —
so a text glued from values is reported in both.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from mrjunkit import validate_cmds  # noqa: E402


class _Project:
    def __init__(self, scripts, locales=("ru_RU", "en_US")):
        self._locales = list(locales)
        self.rep = {"rules": [{"name": "Rule %d" % i, "rule": {"ruleScriptStr": s}} for i, s in enumerate(scripts)]}

    def locales(self):
        return self._locales


class _Report:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)


def check(*scripts, **kwargs):
    report = _Report()
    validate_cmds._check_rule_strings_multilingual(_Project(scripts, **kwargs), report)
    return report.warnings


def glued(*scripts, **kwargs):
    report = _Report()
    validate_cmds._check_rule_messages_are_literals(_Project(scripts, **kwargs), report)
    return report.warnings


def component(*scripts):
    report = _Report()
    model = {"scripts": [dict(name="s%d" % i, code=code, enabled=True) for i, code in enumerate(scripts)]}
    validate_cmds._check_studio_texts_are_literals(model, {"name": "Orders"}, report)
    return report.warnings


class RuleMessageLocalizedTest(unittest.TestCase):

    def test_a_plain_monolingual_sentence_is_still_reported(self):
        warnings = check("throw new RuntimeException('Запись в этом статусе изменить нельзя')")
        self.assertEqual(1, len(warnings))
        self.assertIn("ONE language", warnings[0])

    def test_a_sentence_the_platform_translates_is_not_judged(self):
        self.assertEqual([], check(
            "throw new RuntimeException(service.global.locale.message('Запись в статусе {0} изменить нельзя', s))",
            "return [ok: false, message: service.global.locale.message('Не удалось сохранить заказ')]"))

    def test_a_single_language_project_is_never_reported(self):
        self.assertEqual([], check("throw new RuntimeException('Запись в этом статусе изменить нельзя')",
                                   locales=("ru_RU",)))


class RuleMessageGluedFromValuesTest(unittest.TestCase):

    def test_a_text_glued_from_values_is_reported_with_its_line(self):
        warnings = glued("def n = row.number\n"
                         "throw new RuntimeException(service.global.locale.message('Запись ' + n + ' закрыта'))")
        self.assertEqual(1, len(warnings))
        self.assertIn("line 2", warnings[0])
        self.assertEqual(1, len(glued('return [message: service.global.locale.message("Запись ${n} закрыта")]')))
        self.assertEqual(1, len(glued('service.global.locale.message("""Запись ${n}""")')))

    def test_one_literal_with_placeholders_is_not_reported(self):
        self.assertEqual([], glued(
            "service.global.locale.message('Запись {0} закрыта', row.number)",
            'service.global.locale.message("Запись {0}, статус {1}", n, s)',
            "service.global.locale.message(\n    'Итого {0}',\n    a + b)",
            "service.global.locale.message(ok ? 'Принято {0}' : 'Отклонено {0}', n)",
            'service.global.locale.message("Цена \\$5 за {0}", n)',
            "def m = 'Запись {0} закрыта'\nservice.global.locale.message(m, n)",
            "// service.global.locale.message('Запись ' + n)"))

    def test_a_single_language_project_is_never_reported(self):
        self.assertEqual([], glued("service.global.locale.message('Запись ' + n)", locales=("ru_RU",)))

    def test_a_call_quoted_inside_a_string_is_none(self):
        self.assertEqual([], glued('log.info("calling service.global.locale.message(\'x\' + y)")'))


class ComponentTextsAreLiteralsTest(unittest.TestCase):

    def test_a_text_built_at_run_time_is_reported_with_its_line(self):
        warnings = component("const a = ctx.t('Total: ' + n);\nctx.t(row.label);\nctx.t(`Total: ${n}`);")
        self.assertEqual(1, len(warnings))
        self.assertIn("3 t(", warnings[0])
        self.assertIn("line 1: t('Total: ' + n)", warnings[0])
        self.assertIn("line 3:", warnings[0])

    def test_what_the_platform_translates_or_never_needs_to_is_not_reported(self):
        self.assertEqual([], component(
            "ctx.t('Total: {0}', n); ctx.t(\"Done\"); ctx.t(`Plain`); ctx.t();",
            "ctx.t(\n  'Long text',\n  n);",
            "ctx.t({ en_US: 'Draft', ru_RU: 'Черновик' });",
            "ctx.service.global.locale.message('Saved {0}', n);",
            "function t(key) { return key; }\nconst o = { message(text) { return text; } };",
            "// ctx.t('a' + b)\n/* ctx.t(label) */"))

    def test_a_component_with_its_own_t_is_left_to_it(self):
        # written before ctx.t: a key lookup over its own per-language maps, declared in one script, used in another
        self.assertEqual([], component("const t = k => (MSG[ctx.locale] || MSG.en_US)[k] || k;",
                                       "el.title = t('P_' + priority); el.textContent = t(state);",
                                       "function message(text, bad) {\n  el.textContent = text;\n}\nmessage(err, true);"))
        # ...while the runtime's own calls beside it are still judged
        self.assertEqual(1, len(component("const t = k => MSG[LOC][k];\nt(key); ctx.t(label);")))

    def test_an_alias_of_the_runtime_is_the_runtime(self):
        for alias in ("const t = ctx.t;", "const { t } = ctx;", "function t(k, ...a) { return ctx.t(k, ...a); }",
                      "const t = (k, ...a) =>\n  ctx.t(k, ...a);"):
            warnings = component(alias + "\nt(label);")
            self.assertEqual(1, len(warnings), alias)
            self.assertIn("t(label)", warnings[0], alias)

    def test_a_call_on_anything_else_belongs_to_that_thing(self):
        self.assertEqual([], component("i18n.t(key); this.message(text); L.message(text);"))
        self.assertEqual(1, len(component("ctx?.t(label); ctx\n  .t(other);")))

    def test_an_alias_survives_every_other_t_in_the_component(self):
        for other in ("const t = document.createElement('table');", "const t = ev.target;",
                      "for (const t of tabs) { draw(t); }", "function debounce(fn, ms) { let t; }",
                      "const t = performance.now();"):
            warnings = component("const t = ctx.t;\nel.textContent = t(label);\n" + other)
            self.assertEqual(1, len(warnings), other)
            self.assertIn("t(label)", warnings[0], other)
        self.assertEqual([], component("const { t } = makeI18n(MSG);\nt(key);"), "a t of its own helper")
        self.assertEqual([], component("let lang = 'ru', t = k => MSG[lang][k];\nt(key);"))

    def test_a_regex_or_a_template_is_neither_a_comment_nor_a_string(self):
        # a // inside a regex or a template literal does not blank the call after it
        self.assertEqual(1, len(component("const re = /https?:\\/\\//; ctx.t(label);")))
        self.assertEqual(1, len(component("const u = `https://x/${id}`; ctx.t(label);")))
        # an own function whose body holds a template URL is still recognised as its own
        self.assertEqual([], component("function t(k) { return `https://x/${k}`; }\nt(state);"))

    def test_a_template_inside_a_template_hides_no_call(self):
        # the platform's own reading: a nested template once inverted the scan, and "image/*" blanked the rest
        code = ("list.innerHTML = `<ul>${items.map(i => `<li>${esc(i.name)}</li>`).join('')}</ul>`;\n"
                "hint.innerHTML = `${ctx.t('Accepted files')}: image/*, application/pdf`;\n"
                "save.textContent = ctx.t(label);")
        calls = validate_cmds._untranslatable_text_calls(code)
        self.assertEqual([3], [c[0] for c in calls], calls)
        self.assertEqual([], validate_cmds._untranslatable_text_calls("el.innerHTML = '<b onclick=\"t(x)\">';"),
                         "a call inside a string is none")
        self.assertEqual(1, len(validate_cmds._untranslatable_text_calls("/* never closed\nctx.t(label);")))

    def test_a_wrapper_whose_body_follows_a_comment_or_a_blank_line_is_a_wrapper(self):
        for gap in ("\n  // short name\n", "\n\n"):
            self.assertEqual(set(), validate_cmds._own_text_functions(["const t = (k, ...a) =>" + gap + "  ctx.t(k, ...a);"]))

    def test_a_misreading_lexer_hides_no_call(self):
        self.assertEqual(1, len(validate_cmds._untranslatable_text_calls("x = a++ / 2; y = '/'; ctx.t(label);")))
        self.assertEqual(1, len(validate_cmds._untranslatable_text_calls("if (ok) /'/.test(s) && ctx.t(label);")))
        # a declaration list: the second declarator is not the arrow's body, so t stays the author's own
        self.assertEqual({"t"}, validate_cmds._own_text_functions(["const t = k => MSG[k], x = ctx.t('A');"]))

    def test_an_unclosed_call_costs_a_bounded_scan(self):
        import time
        started = time.time()
        validate_cmds._untranslatable_text_calls("\n".join("ctx.t(a, b" for _ in range(8000)))
        self.assertLess(time.time() - started, 5)

    def test_lines_are_counted_on_long_scripts_without_rescanning(self):
        code = "\n".join("ctx.t(v%d);" % i for i in range(3000))
        calls = validate_cmds._untranslatable_text_calls(code)
        self.assertEqual(3000, len(calls))
        self.assertEqual(3000, calls[-1][0])

    def test_a_disabled_script_is_not_read(self):
        report = _Report()
        validate_cmds._check_studio_texts_are_literals(
            {"scripts": [{"name": "off", "code": "ctx.t(label)", "enabled": False}]}, {"name": "Orders"}, report)
        self.assertEqual([], report.warnings)


class MarksNeedTheRuntimeTest(unittest.TestCase):

    @staticmethod
    def marks(pn, html, studio=None):
        report = _Report()
        props = {"html": {"stringValue": html}}
        if studio is not None:
            props["studioModel"] = {"stringValue": studio}
        validate_cmds._check_marks_need_the_runtime({"name": "Block"}, pn, props, report)
        return report.warnings

    def test_a_plain_block_with_marks_is_reported(self):
        self.assertEqual(1, len(self.marks("html.plugin", "<h2 data-i18n>Заказы</h2>")))
        self.assertEqual(1, len(self.marks("nct.html.plugin", "<h2 data-i18n>Заказы</h2>")))
        self.assertEqual(1, len(self.marks("nct.html.plugin", "<h2 data-i18n>Заказы</h2>", '{"scripts": []}')))

    def test_a_studio_component_or_a_block_without_marks_is_not(self):
        self.assertEqual([], self.marks("nct.html.plugin", "<h2 data-i18n>Заказы</h2>",
                                        '{"scripts": [{"name": "main", "code": ""}]}'))
        self.assertEqual([], self.marks("html.plugin", "<h2>Заказы</h2>"))


if __name__ == "__main__":
    unittest.main()
