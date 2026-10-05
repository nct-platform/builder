"""Every message the platform shows a user — and the kind a user must never be shown.

A user meets an action that cannot succeed for them — wrong role, wrong state, not enough in stock, whatever the
business says — in one of three ways, and the builder chose which for every action: it is NOT OFFERED (a
predicate), it is EXPLAINED before it is submitted (a validation in its form), or it is REFUSED in the business's
own words (a direct action's message). What a user must never meet is the error underneath — the exception the
business logic threw, the database constraint that stopped the write, a stack trace, an HTTP 500. That always means
an action was offered, or a form accepted, where it should not have been.

This watcher records the text of every toast, alert, feedback message and dialog body that appears in any page of
a browser context, at the moment it appears (they leave after a few seconds), and `technical(...)` picks out the
ones with a technical signature. conftest fails the test that made one appear; a test that provokes one on purpose
says so with `@pytest.mark.technical_error_expected("<why>")`.

The signatures are deliberately ones no business message contains — an exception CLASS, a stack frame, the
database's own phrasing, a 500 — so a refusal written in the business's words never trips it, whatever the language.
"""
from __future__ import annotations

import re

# A stack frame; a qualified JVM class; the exceptions a rule or the database throws when nothing was checked first;
# Groovy's own runtime complaints; the database's own wording; an HTTP 500.
TECHNICAL = re.compile(
    r"\bat\s+[\w.$]+\([\w$]+\.(?:java|groovy|kt):\d+\)"
    r"|\b(?:java|javax|jakarta|groovy|org\.(?:springframework|hibernate|postgresql|apache)|com\.devsegment)"
    r"\.[a-z][\w.]*\.[A-Z]\w+"
    r"|\b(?:NullPointer|ClassCast|IndexOutOfBounds|ArrayIndexOutOfBounds|NumberFormat|MissingMethod"
    r"|MissingProperty|UnsupportedOperation|ConcurrentModification|Arithmetic|DataIntegrityViolation"
    r"|ConstraintViolation|JsonParse|JsonMapping|MismatchedInput|InvalidFormat|PSQL|SQL|BadSqlGrammar"
    r"|InvalidDataAccessApiUsage|LazyInitialization|TransactionSystem|GroovyRuntime|GroovyCast)Exception\b"
    r"|\bNo signature of method\b|\bCannot (?:invoke method|get property|set property)\b[^\n]*\bon null object\b"
    r"|\bNo such property:\s"
    r"|\bduplicate key value violates\b|\bviolates (?:foreign key|check|not-null|unique) constraint\b"
    r"|\bnull value in column\b|\bsyntax error at or near\b|\brelation \"[^\"]+\" does not exist\b"
    r"|\bcolumn \"[^\"]+\" does not exist\b|\bSQLState\b|\bInternal Server Error\b|\"status\"\s*:\s*5\d\d"
    # the platform's wrapping of a rule that threw during a FORM submission — 25 "Business preconditions belong
    # in a VALIDATION rule": the user's reason is buried behind rule uuids and reads like a crash
    r"|\bCould not execute rule\(s\)"
)

# An identifier in an ERROR message is the platform talking about itself, not the business talking to a user.
# (Only in errors: a success message may legitimately name what it created.)
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)

_WATCH_JS = r"""
(() => {
  if (window.__autotestFeedbackWatch) return;
  window.__autotestFeedbackWatch = true;
  const SEL = "[class*='toast'],[class*='feedback'],[class*='alert'],[role='alert'],.modal-body";
  const last = new WeakMap();
  const ERR = "[class*='error'],[class*='danger']";
  const report = (el) => {
    const t = ((el && el.innerText) || '').trim();
    if (!t || last.get(el) === t) return;
    last.set(el, t);
    const kind = (el.matches(ERR) || el.querySelector(ERR)) ? 'error' : '';
    try { window.__autotestFeedbackSink && window.__autotestFeedbackSink(t.slice(0, 2000), kind); } catch (e) {}
  };
  const scan = (node) => {
    if (!(node instanceof Element)) return;
    if (node.matches(SEL)) report(node);
    node.querySelectorAll(SEL).forEach(report);
  };
  const hostOf = (node) => {
    const el = node instanceof Element ? node : node && node.parentElement;
    return el ? el.closest(SEL) : null;
  };
  const start = () => {
    scan(document.body);
    new MutationObserver((records) => records.forEach((m) => {
      if (m.type === 'childList') { m.addedNodes.forEach(scan); const h = hostOf(m.target); if (h) report(h); }
      else { const h = hostOf(m.target); if (h) report(h); }
    })).observe(document.documentElement, {childList: true, subtree: true, characterData: true,
                                           attributes: true, attributeFilter: ['class', 'style']});
  };
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
"""


def is_technical(text: str, kind: str = "") -> bool:
    """Does this message carry a technical signature? `kind` is "error" for an error-styled message."""
    text = text or ""
    return bool(TECHNICAL.search(text) or (kind == "error" and UUID.search(text)))


class FeedbackWatch:
    """Collects every user-facing message of the contexts it is installed in, across navigations."""

    def __init__(self):
        self.messages: list[tuple] = []

    def install(self, context) -> None:
        context.expose_binding("__autotestFeedbackSink",
                               lambda _source, text, kind="": self.messages.append((kind or "", text or "")))
        context.add_init_script(script=_WATCH_JS)

    def mark(self) -> int:
        return len(self.messages)

    def since(self, mark: int) -> list[str]:
        return [text for _kind, text in self.messages[mark:]]

    def technical_since(self, mark: int) -> list[str]:
        """The technical messages shown since `mark`, each once (a toast and its container report the same text)."""
        out: list[str] = []
        for kind, text in self.messages[mark:]:
            if is_technical(text, kind) and not any(text in seen or seen in text for seen in out):
                out.append(text)
        return out
