"""What the platform's rule sandbox refuses before a rule runs (doc 08 "The rule sandbox") is an ERROR here, before
the archive is imported: inject(), annotations, reflection, processes, files, the environment, and changes to what
every project shares. A rule that computes with plain values and reaches the rest through service.* and context.*
is silent - and so is a comment, or a string that only mentions the words.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from mrjunkit import validate_cmds  # noqa: E402


class _Project:
    cruds_file = None

    def __init__(self, *scripts):
        self.rep = {"rules": [{"name": "Rule %d" % i, "ruleType": "EXECUTION_RULE", "rule": {"ruleScriptStr": s}}
                              for i, s in enumerate(scripts)]}


class _Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def sandbox(*scripts):
    report = _Report()
    validate_cmds._check_rule_sandbox(_Project(*scripts), report)
    return report


class RuleSandboxTest(unittest.TestCase):

    def test_what_rules_do_every_day_is_silent(self):
        report = sandbox("""
            def total = [1.25, 2.5].sum()
            def stamp = new java.text.SimpleDateFormat('yyyy').format(new Date())
            def qty = currentData.getField('qty', java.lang.Integer.class)
            def sum = [1, 2, 3].inject(0) { a, b -> a + b }
            def mail = 'boss@acme.com'          // an @ in a string or a comment: @nobody
            System.out.println("at ${System.currentTimeMillis()}")
            Thread.sleep(10)
            def rows = service.crud.orders.findAll()
            def r = service.crud."${alias}".get(id)
            service.notification.mail."${mailAlias}"(to, placeholders)
            def label = (fb == null) ? '' : (fb.respondsTo('asText') ? fb.asText() : fb.toString())
            def known = row.hasProperty('code')
            def c = (code == null || code instanceof Class) ? '' : code.toString()
            try { boom() } catch (e) { log("failed: " + e.class.simpleName + ' ' + e.getClass().getName()) }
            settings.default = true
            def paid = service.crud.payment.execute([actor: who, id: rid])
            if (__wf.getClass() == RuntimeException) { throw __wf }
            if (RuntimeException != __wf.getClass() || a.b.class == String || x.getClass() in [A, B]) { }
            def x = row[fieldName]
            if (x instanceof Map) { x['default'] = 1 }   // a map's key named default is data
            return [total, stamp, qty, sum, mail, rows]
            """)
        self.assertEqual([], report.errors, report.errors)

    def test_the_refusals(self):
        report = sandbox("def r = inject('rimmService')",
                         "@groovy.transform.ASTTest(value={ 1 })\ndef x = 1",
                         "return service.@realm",
                         "return it.class",
                         "return 'ls'.execute().text",
                         "return System.getenv('TOKEN')",
                         "Locale.default = Locale.CHINA",
                         "synchronized (lock) { x++ }",
                         "return new File('/etc/passwd').text",
                         "return Thread.currentThread()",
                         "return com.devsegment.nctcommon.utils.SpringBeanUtils.getBean('x')",
                         "String.mixin(Integer)")
        self.assertEqual(12, len(report.errors), "\n".join(report.errors))
        self.assertIn("rule 'Rule 0': line 1 calls inject(...) - inject() is gone", report.errors[0])
        self.assertIn("carries an annotation", report.errors[1])
        self.assertIn("reads a field past its accessors", report.errors[2])
        self.assertIn("reads .class of a value", report.errors[3])
        self.assertIn("calls execute(...) on text or a list", report.errors[4])
        self.assertIn("uses System.getenv", " ".join(report.errors))
        self.assertIn("changes a class's default", " ".join(report.errors))
        self.assertIn("takes a lock", " ".join(report.errors))
        self.assertIn("uses File", " ".join(report.errors))
        self.assertIn("uses Thread.currentThread", " ".join(report.errors))
        self.assertIn("uses com.devsegment.*", " ".join(report.errors))
        self.assertIn("calls mixin(...)", " ".join(report.errors))

    def test_the_line_is_the_rules_own(self):
        report = sandbox("def a = 1\n\nreturn System.getenv('X')")
        self.assertEqual(1, len(report.errors), report.errors)
        self.assertIn("line 3 uses System.getenv", report.errors[0])


if __name__ == "__main__":
    unittest.main()
