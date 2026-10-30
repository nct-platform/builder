"""service.pubsub and service.messenger are one kind of namespace - every property an alias, a few methods of their own,
channels with a handful of members - and one check reads both (doc 33 §4, doc 36 §10): refused in a predicate or a
validation rule (also through a literal call), a member or an alias that cannot exist, a call shape Groovy finds no
method for, an option nothing has.

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

    def __init__(self, *rules):
        self.rep = {"rules": [{"name": name, "ruleType": rule_type, "rule": {"ruleScriptStr": script}}
                              for name, rule_type, script in rules]}


class _Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def messenger(*scripts, rule_type="EXECUTION_RULE"):
    report = _Report()
    project = _Project(*[("Rule %d" % i, rule_type, s) for i, s in enumerate(scripts)])
    validate_cmds._check_rule_uses_messenger(project, report)
    return report


def pubsub(*scripts, rule_type="EXECUTION_RULE"):
    report = _Report()
    project = _Project(*[("Rule %d" % i, rule_type, s) for i, s in enumerate(scripts)])
    validate_cmds._check_rule_uses_pubsub(project, report)
    return report


class MessengerTest(unittest.TestCase):

    def test_the_documented_call_shapes_are_silent(self):
        report = messenger("""
            def bot = service.messenger.support
            service.messenger.support.send(chatId, 'Order **#42** shipped', [buttons: [[text: 'Yes', data: 'yes']]])
            service.messenger.support.send(chatId, 'Hi', silent: true, format: 'text')
            service.messenger.support.send(to: chatId, text: 'Hi', linkPreview: false)
            service.messenger.support.sendFile(chatId, pdf, [name: 'invoice.pdf', text: 'Your invoice'])
            service.messenger.support.sendFile(to: chatId, file: pdf, name: 'a.pdf', mimeType: 'application/pdf')
            service.messenger.support.edit(chatId, sent.id, 'Updated', buttons: ['Undo'])
            service.messenger.support.answer(message, 'Saved', alert: true)
            service.messenger.support.typing(message)
            service.messenger.support.delete(chatId, sent.id)
            service.messenger.reply(message, 'Thanks', quote: false)
            service.messenger.support.send(chatId, 'x', [template: 'order', templateParams: ['Anna']])
            def all = service.messenger.list()
            service.messenger['support'].chats()
            """)
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)

    def test_a_predicate_or_a_rule_it_calls_may_not_use_it(self):
        report = _Report()
        project = _Project(("Notify", "EXECUTION_RULE", "service.messenger.support.send(chat, 'x')"),
                           ("Can show", "PREDICATE", "service.rule('Notify')\nreturn true"),
                           ("Direct", "VALIDATION_RULE", "service.messenger.support.send(chat, 'x')"))
        validate_cmds._check_rule_uses_messenger(project, report)
        self.assertEqual(2, len(report.errors))
        self.assertIn("calls rule 'Notify', which uses service.messenger", report.errors[0])
        self.assertIn("uses service.messenger - every member throws", report.errors[1])
        self.assertIn("Send from an EXECUTION_RULE", report.errors[1])

    def test_members_that_do_not_exist(self):
        report = messenger("service.messenger.support.sendMessage(chat, 'x')",
                           "service.messenger.support.subscribe('x')",
                           "service.messenger.send(chat, 'x')")
        self.assertEqual(3, len(report.errors), report.errors)
        self.assertIn("a channel has exactly send, sendFile, reply, answer, edit, delete, typing, download and chats",
                      report.errors[0])
        self.assertIn("service.messenger has exactly list(), channel(alias) and reply(message, text)",
                      report.errors[2])

    def test_aliases_that_can_never_exist(self):
        report = messenger("service.messenger['my-bot'].send(chat, 'x')",
                           "service.messenger.names.send(chat, 'x')",
                           "service.messenger.channel('two words').send(chat, 'x')")
        self.assertEqual(3, len(report.errors), report.errors)
        self.assertIn("'my-bot' is not a legal alias", report.errors[0])
        self.assertIn("'names' is a reserved word, or a member of service.messenger itself", report.errors[1])

    def test_an_all_named_call_of_a_member_that_takes_positions(self):
        report = messenger("service.messenger.support.reply(message: m, text: 'x')",
                           "service.messenger.support.edit(chat: c, messageId: i, text: 't')",
                           "service.messenger.reply(message: m, text: 'x')")
        self.assertEqual(3, len(report.errors), report.errors)
        self.assertIn("with named arguments only - reply takes its arguments by position", report.errors[0])
        self.assertEqual([], report.warnings, "one sentence per mistake")

    def test_an_option_no_messenger_has_is_a_warning(self):
        report = messenger("service.messenger.support.send(chat, 'x', [buttns: ['a']])",
                           "service.messenger.support.send(chat, 'x', parse_mode: 'HTML')",
                           "service.messenger.support.answer(message, 'Saved', silent: true)",
                           "service.messenger.support.sendFile(chat, pdf, caption: 'x')")
        self.assertEqual([], report.errors)
        self.assertEqual(4, len(report.warnings), report.warnings)
        self.assertIn("the option 'buttns', which no messenger has", report.warnings[0])
        self.assertIn("Options: alert.", report.warnings[2])
        self.assertIn("the option 'caption'", report.warnings[3])

    def test_a_mention_in_a_string_is_not_a_use(self):
        report = messenger("return 'call service.messenger.support.post(x) to send'", rule_type="PREDICATE")
        self.assertEqual([], report.errors)


class PubSubTest(unittest.TestCase):
    """The PubSub check after it was made the namespace's: the same findings, in the same words."""

    def test_the_documented_shapes_are_silent(self):
        report = pubsub("""
            service.pubsub.plant.publish("devices/${d.serial}/command", [action: 'restart'], [qos: 1])
            service.pubsub.plant.publish(destination: 't', payload: 1, qos: 1)
            service.pubsub.list()
            """)
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)

    def test_the_same_findings_in_the_same_words(self):
        report = pubsub("service.pubsub.plant.send('t', 1)",
                        "service.pubsub.channels()",
                        "service.pubsub['my-broker'].publish('t', 1)",
                        "service.pubsub.plant.publish('t', 1, [acks: 'all'])")
        self.assertEqual(3, len(report.errors), report.errors)
        self.assertIn("calls service.pubsub.plant.send(...), which does not exist - a channel has exactly "
                      "publish(destination, payload[, options]). Receiving is a LISTENER, configured live in "
                      "Settings -> Developer -> Integrations -> PubSub", report.errors[0])
        self.assertIn("calls service.pubsub.channels(...), which does not exist - service.pubsub has exactly "
                      "list() and channel(alias); a connection is addressed as a property, "
                      "service.pubsub.<alias>.publish(...).", report.errors[1])
        self.assertIn("addresses a connection by an alias that can never exist", report.errors[2])
        self.assertEqual(1, len(report.warnings))
        self.assertIn("with the option 'acks', which no broker kind has - the call is refused at run time. Options: "
                      "qos, retain, exchange, persistent, defaultType, timeToLiveMs, key, contentType, headers (what "
                      "is fixed when the connection opens - Kafka acks, RabbitMQ confirm - is a setting of the "
                      "connection, not of a call).", report.warnings[0])

    def test_a_predicate_may_not_publish(self):
        report = pubsub("service.pubsub.plant.publish('t', 1)", rule_type="PREDICATE")
        self.assertEqual(1, len(report.errors))
        self.assertIn("Publish from an EXECUTION_RULE", report.errors[0])


if __name__ == "__main__":
    unittest.main()
