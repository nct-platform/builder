"""Numbers on screen, and the expected numbers the scenarios predict — compared EXACTLY.

Calculations are the heart of an ERP, and a calculation test fails for three reasons that have nothing to do with
the calculation. This module removes all three:

* **Reading.** A cell is "1 500,00", "1,500.00", "−3.0", "92.16 %", "֏ 12 000" — and a code such as
  `RM-A12-003` contains `-003`. ⛔ A pattern that takes "the first number in the row" read that code as −3 and
  reported a calculation defect over a row the database stored correctly. `parse_number` therefore reads a WHOLE
  cell and refuses one that is not a number, instead of fishing a number out of it. Locate the cell by its column
  caption, then parse it.
* **Rounding.** The project's SQL rounds with PostgreSQL ROUND on numeric, which rounds half AWAY from zero:
  2.025 -> 2.03. Python's round() rounds half to EVEN and works on binary floats, so round(2.025, 2) == 2.02 and
  the test "finds" a defect the system does not have. Compute every expected value with `Decimal` and
  `round_db`, from the scenario's own inputs, with the PRD's formula written out.
* **The expectation itself.** Before reporting a calculation defect, recompute the scenario's arithmetic: the
  number a test asserts is only as good as the document it came from. `assert_number` prints the formula and
  the inputs so a red run shows which side is wrong.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Everything that may decorate a number in a cell without being part of it.
_SPACES = "    '"            # NBSP, narrow NBSP, thin space, space, Swiss apostrophe
_MINUS = "−–-"                    # the minus sign, an en dash, a hyphen
_DECOR = re.compile(r"[%‰֏$€£₽¥]|\b(?:AMD|USD|EUR|RUB|GBP)\b", re.I)
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d+)*)?(?:[.,]\d+)?$")


def parse_number(text: str | None) -> Decimal | None:
    """The number a WHOLE cell holds, or None when the cell is not a number.

    Spaces of every kind and the apostrophe group thousands. Of "," and ".": when both appear, the LAST one is the
    decimal point ("1,500.25", "1.500,25"); when one of them repeats, it groups thousands ("1,500,000"); a single
    one is the decimal point ("38.628", "0.562", "33,5") — grids print quantities with three decimals far more
    often than a grouped integer without decimals. The one case this reads wrongly is a grouped integer such as
    "1,500" meaning fifteen hundred: read such a column with parse_number_in(text, decimal) instead.
    """
    return _parse(text, None)


def parse_number_in(text: str | None, decimal: str) -> Decimal | None:
    """Like parse_number, with the decimal separator fixed — ',' or '.', the session locale's."""
    if decimal not in (",", "."):
        raise ValueError("decimal must be ',' or '.'")
    return _parse(text, decimal)


def _parse(text, decimal):
    if text is None:
        return None
    s = _DECOR.sub("", str(text)).strip()
    for ch in _SPACES:
        s = s.replace(ch, "")
    if not s:
        return None
    sign = ""
    if s[0] in _MINUS or s[0] == "+":
        sign, s = ("-" if s[0] != "+" else ""), s[1:]
    elif s[-1] in _MINUS:                         # some locales print the minus after the number
        sign, s = "-", s[:-1]
    if not s or not _NUMBER.match(s):
        return None
    seps = [i for i, ch in enumerate(s) if ch in ",."]
    if not seps:
        return Decimal(sign + s)
    if decimal is None:
        kinds = {s[i] for i in seps}
        if len(kinds) == 2:
            decimal = s[seps[-1]]                 # "1,500.25" / "1.500,25"
        elif len(seps) > 1:
            decimal = ""                          # "1,500,000": grouping only
        else:
            decimal = s[seps[0]]                  # "38.628", "33,5"
    if decimal == "":
        digits = s.replace(",", "").replace(".", "")
    else:
        if s.count(decimal) > 1:
            return None
        thousands = "." if decimal == "," else ","
        digits = s.replace(thousands, "").replace(decimal, ".")
    try:
        return Decimal(sign + digits)
    except InvalidOperation:
        return None


def round_db(value, places: int) -> Decimal:
    """Round like PostgreSQL ROUND(numeric, places): half away from zero, on decimal digits, never on floats."""
    q = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)


def assert_number(actual_text: str | None, expected, places: int, *, what: str, formula: str = "",
                  inputs: dict | None = None, decimal: str | None = None) -> Decimal:
    """Assert that a cell shows EXACTLY `expected` rounded to `places` — with the formula in the failure message.

    `expected` is computed by the test from the scenario's inputs (Decimal or int, never float — a float is refused,
    it is how 2.675 becomes 2.67); `formula` and `inputs` are printed so a red run says which side is wrong: the
    system, or the scenario's arithmetic. `decimal` fixes the separator ("," or ".") for a column whose numbers
    parse_number would misread, such as grouped integers ("1,500").

    The screen value is NOT rounded before the comparison: a cell showing 2.0249 where the scenario expects 2.02
    prints an unrounded value, and that is a finding, not a match. Trailing zeros do not matter (12.5000 == 12.50).
    """
    if isinstance(expected, float):
        raise TypeError(f"{what}: compute the expected value with Decimal from the scenario's inputs, not a float "
                        f"({expected!r}) — binary floats round 2.675 down to 2.67")
    want = round_db(expected, places)
    got = _parse(actual_text, decimal) if decimal else parse_number(actual_text)
    detail = f" — {formula}" if formula else ""
    if inputs:
        detail += " with " + ", ".join(f"{k}={v}" for k, v in inputs.items())
    assert got is not None, f"{what}: the cell {actual_text!r} is not a number (expected {want}{detail})"
    if got != want and round_db(got, places) == want:
        raise AssertionError(f"{what}: shows {got} ({actual_text!r}) — more decimals than the {places} the scenario "
                             f"rounds to, so the screen prints an UNROUNDED value (expected {want}{detail})")
    assert got == want, f"{what}: shows {got} ({actual_text!r}), expected {want}{detail}"
    return got
