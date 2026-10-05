"""Read-only access to the project's database — the second witness for every number and every write.

A screen can agree with itself and both be wrong: a register can print a derived column the server never stored, a
task form can report "saved" while nothing was written, and a total can be right on screen and wrong in the row
the reports read. When PGDSN is set in .env, the calculation, ripple and write tests read the row back from the
database and compare it with the screen and with the scenario's expected value.

PGDSN is OPTIONAL. Without it — or when the database is not reachable from the machine running the suite, which
is common: the source's host is often an internal name — there are two answers, and the test picks by what the
database is FOR in it:

* `query()` / `one()` — the database IS the assertion (a value no screen shows: a stored column, a row that must
  not exist). Without a database the test SKIPS and says why: it proved nothing, and a skip is never a pass.
* `optional()` — the screen already proved the scenario and the row is a SECOND witness. Without a database it
  returns None and the run's warning summary says the witness was missing; the screen's assertions still count.

A query that is WRONG — a misspelt table, a column that does not exist — is not a missing database: it fails the
test with the database's own message, because it is a defect of the suite.

⛔ Read-only by construction: every session sets `default_transaction_read_only = on` first. The suite proves
things THROUGH the application; a test that writes SQL proves nothing about the product and corrupts the tenant.

    PGDSN=host=<host> port=5432 dbname=<db> user=<user> password=<secret> options=-csearch_path=<schema>
"""
from __future__ import annotations

import warnings

import pytest

from helpers.env import CONFIG

try:                                    # psycopg is needed only when PGDSN is set
    import psycopg
except ImportError:                     # pragma: no cover — reported by query()
    psycopg = None


class DatabaseWitnessMissing(UserWarning):
    """The database cross-check of a test that passed on the screen could not run."""


def available() -> bool:
    return bool(CONFIG.pgdsn) and psycopg is not None


def _missing() -> str | None:
    if not CONFIG.pgdsn:
        return "PGDSN is empty in test/.env"
    if psycopg is None:
        return "PGDSN is set but psycopg is not installed (pip install -r requirements.txt)"
    return None


def _run(sql: str, params: tuple) -> list[tuple]:
    # Read-only is set AFTER connecting: an `options=` argument would replace the DSN's own
    # `options=-csearch_path=<schema>`, and every query would then read the wrong schema.
    with psycopg.connect(CONFIG.pgdsn, connect_timeout=10, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")
        with conn.cursor() as cur:
            cur.execute(sql, params or None)
            return cur.fetchall()


def _unreachable(exc: Exception) -> str:
    # The message of a connection failure can carry the DSN's host and user — never print it whole.
    return f"PGDSN is set but the database is not reachable from this machine ({type(exc).__name__})"


def query(sql: str, *params) -> list[tuple]:
    """Rows of a READ-ONLY query — or a pytest SKIP that names what is missing. For when the database IS the
    assertion."""
    why = _missing()
    if why:
        pytest.skip(f"database cross-check skipped: {why}")
    try:
        return _run(sql, params)
    except psycopg.OperationalError as exc:
        pytest.skip(f"database cross-check skipped: {_unreachable(exc)}")


def one(sql: str, *params):
    """The single value of a single-row, single-column query (None when there is no row)."""
    rows = query(sql, *params)
    return rows[0][0] if rows else None


def optional(sql: str, *params) -> list[tuple] | None:
    """Rows of a READ-ONLY query, or None (with a warning in the run's summary) when there is no database to ask.

    For a SECOND witness only — the screen already asserted the scenario:

        rows = db.optional("select total from <table> where code = %s", code)
        if rows is not None:
            assert_number(str(rows[0][0]), expected, 2, what="stored total", formula=...)
    """
    why = _missing()
    if why is None:
        try:
            return _run(sql, params)
        except psycopg.OperationalError as exc:
            why = _unreachable(exc)
    warnings.warn(DatabaseWitnessMissing(f"the database cross-check did not run: {why}"), stacklevel=2)
    return None
