"""crud verify --db — execute every dynamic-CRUD SQL method against a live DB.

The lesson behind this command: smoke-testing generated SQL against EMPTY tables
hides CHECK / NOT NULL / FK / cardinality failures and turns UPDATE/DELETE into
no-ops. This runs each SQL method for real — reads directly, writes inside a
transaction that is always ROLLED BACK, seeding a minimal fixture row when the
table is empty so constraints actually fire.

Requires `psql` on PATH. Connection is whatever libpq accepts, e.g.
  --db "host=<host> port=5432 dbname=<project-db> user=<user> password=<password>"
GROOVY methods are not executed here (no Groovy runtime) — use them via the app.
"""

import re
import shutil
import subprocess

from . import core, dyncheck

STD_READ = ("findAll", "count", "get", "findAllByParent", "countByParent")
_ID0 = "'00000000-0000-0000-0000-000000000000'"


def _snake(alias):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", alias).lower()


def _psql(conninfo, schema, sql):
    body = "SET search_path TO %s;\n%s" % (schema, sql)
    # -q suppresses command tags (e.g. the "SET" line) so they don't pollute
    # single-value fetches; errors still go to stderr.
    proc = subprocess.run(["psql", conninfo, "-q", "-v", "ON_ERROR_STOP=off", "-tAc", body],
                          capture_output=True, text=True)
    return proc.stdout.strip(), proc.stderr.strip()


def _first_err(stderr):
    for line in (stderr or "").splitlines():
        if "ERROR:" in line:
            return line.split("ERROR:", 1)[1].strip()
    return None


def cmd_crud_verify(args):
    if not shutil.which("psql"):
        raise core.ToolError("psql not found on PATH (required for `crud verify --db`)")
    p = core.Project(args.project)
    cf = p.cruds_file
    cruds = (cf.data.get("cruds", []) if cf else []) or []
    if not cruds:
        raise core.ToolError("no dynamic-cruds.json in this project")
    idx = dyncheck.build_schema_index(p.db)
    schema = args.schema or cruds[0].get("sourceSchema")
    sidx = idx.get(schema) or {}
    tables, fks, checks = sidx.get("tables", {}), sidx.get("fks", {}), sidx.get("checks", {})

    # live reference data: one id per business table, one code per lookup table
    ids, codes = {}, {}
    for tname in tables:
        if tname.startswith("lookup_"):
            out, _ = _psql(args.db, schema, "SELECT code FROM %s.%s LIMIT 1" % (schema, tname))
            codes[tname] = (out.splitlines()[-1].strip() if out else None) or None
        elif tname not in ("databasechangelog", "databasechangeloglock"):
            out, _ = _psql(args.db, schema, "SELECT id::text FROM %s.%s LIMIT 1" % (schema, tname))
            ids[tname] = (out.splitlines()[-1].strip() if out else None) or None

    def val_for(tbl, pname):
        if pname == "rowsInPage":
            return "5"
        if pname == "pageNumber":
            return "0"
        if pname == "parentId":
            return "NULL"
        # ANY column constrained by a CHECK allowed-set must receive a LEGAL literal, not the
        # 'T' sentinel below — otherwise every enum-ish column that isn't named `*_status`
        # (kind, method, doc_kind, partner_role, …) reports a false CHECK violation.
        allowed = (checks.get(tbl) or {}).get(pname)
        if allowed:
            return "'%s'" % sorted(allowed)[0]
        if pname in ("lotStatus", "qcStatus", "status") or pname.endswith("_status"):
            return "NULL"
        if pname == "currency":
            return "'USD'"
        # a param that IS an FK column of this table (snake, e.g. `nomenclature_id`) must get a
        # LIVE id from the target table; a random uuid would fail the FK.
        if pname in fks.get(tbl, {}):
            v = ids.get(fks[tbl][pname])
            return "'%s'" % v if v else "NULL"
        if "__" in pname:
            root = pname.split("__")[0]
            tgt = fks.get(tbl, {}).get(root + "_id")
            v = ids.get(tgt) if tgt else None
            return "'%s'" % v if v else "NULL"
        col = pname + "_id"
        if col in fks.get(tbl, {}) and fks[tbl][col].startswith("lookup_"):
            c = codes.get(fks[tbl][col])
            return "'%s'" % c if c else "NULL"
        ci = next((c for c in tables.get(tbl, []) if c["name"] == pname), None)
        if not ci or not ci["notnull"]:
            return "NULL"
        t = ci["type"].lower()
        if "char" in t or "text" in t:
            return "'T'"
        if "num" in t or "int" in t or "double" in t:
            return "1"
        if "bool" in t:
            return "false"
        if "date" in t or "timestamp" in t:
            return "now()"
        if "uuid" in t:
            # a NOT NULL uuid that is not an FK (a document reference, a correlation id).
            # A LITERAL, not gen_random_uuid(): the canonical write guard is
            # CAST(NULLIF(:x,'') AS uuid) and NULLIF(<uuid function>, '') fails to type-check.
            return _ID0
        return "NULL"

    def subst(tbl, sql, params, row_id=None):
        for prm in sorted(params or [], key=lambda x: -len(x["parameterName"])):
            pn = prm["parameterName"]
            if pn == "id" and row_id:
                v = row_id
            elif pn == "id":
                v = "'%s'" % ids.get(tbl) if ids.get(tbl) else _ID0
            else:
                v = val_for(tbl, pn)
            sql = re.sub(r":" + re.escape(pn) + r"(?![\w])", v, sql)
        return sql

    only = set(args.crud.split(",")) if getattr(args, "crud", None) else None
    INSERTS = ("create", "createHeader")
    ok = fails = skipped = 0
    problems = []
    for c in cruds:
        alias = c.get("alias")
        if only and alias not in only:
            continue
        tbl = _snake(alias)
        rid = "'%s'" % ids[tbl] if ids.get(tbl) else None
        methods = c.get("methods", []) or []
        seed = next((m for m in methods if m.get("methodName") in INSERTS
                     and m.get("methodType") == "SQL"), None)
        for m in methods:
            if m.get("methodType") != "SQL":
                continue
            name = m.get("methodName")
            if name.startswith("_"):
                continue  # internal helper (e.g. _deleteHeader) — run via its GROOVY caller
            sql = subst(tbl, m.get("script", "") or "", m.get("parameters"), row_id=rid)
            if name in STD_READ:
                _, err = _psql(args.db, schema, sql.rstrip().rstrip(";") + ";")
            elif name in INSERTS or name == "deleteLines":
                # a real INSERT (or a by-parent DELETE) exercises CHECK/NOT NULL/FK.
                _, err = _psql(args.db, schema,
                               "BEGIN;\n" + sql.rstrip().rstrip(";") + ";\nROLLBACK;")
            elif name == "insertLine":
                skipped += 1  # needs a parent header row (exercised via the doc create flow)
                continue
            else:
                # update / delete / _deleteHeader / lifecycle: needs an existing row.
                # Use a real one, else seed a fixture via the CRUD's own INSERT inside
                # the same transaction so CHECK/NOT NULL constraints actually fire.
                if rid:
                    _, err = _psql(args.db, schema,
                                   "BEGIN;\n" + sql.rstrip().rstrip(";") + ";\nROLLBACK;")
                elif seed is not None:
                    seed_sql = subst(tbl, seed.get("script", "") or "", seed.get("parameters"))
                    seed_sql = re.sub(r"RETURNING\s+\*", "RETURNING id", seed_sql, flags=re.I)
                    if "RETURNING" not in seed_sql.upper():
                        seed_sql = seed_sql.rstrip().rstrip(";") + " RETURNING id"
                    m_sql = subst(tbl, m.get("script", "") or "", m.get("parameters"),
                                  row_id="(SELECT id FROM __seed)")
                    combined = ("BEGIN;\nWITH __seed AS (%s)\n%s;\nROLLBACK;"
                                % (seed_sql.rstrip().rstrip(";"), m_sql.rstrip().rstrip(";")))
                    _, err = _psql(args.db, schema, combined)
                else:
                    skipped += 1
                    continue
            e = _first_err(err)
            if e:
                fails += 1
                problems.append((alias, name, e[:100]))
            else:
                ok += 1

    core.out("crud verify @ %s (schema %s)" % (args.db.split()[0] if args.db else "?", schema))
    core.out("  OK: %d   FAIL: %d   skipped(no seed row): %d" % (ok, fails, skipped))
    for a, n, e in problems:
        core.out("  x %s.%s: %s" % (a, n, e))
    return 1 if fails else 0
