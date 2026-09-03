"""Static analysis for dynamic-CRUD conversions.

Shared helpers used by `validate` (and `crud verify`) to catch the class of bugs
that only bite at runtime against a populated DB:

  * a SQL method writing a status/enum literal a column's CHECK constraint forbids
    (e.g. inventoryCount.cancel -> status='CANCELLED' when the check omits it);
  * a crud.table / crud.tree / form-control / list-sub-grid field expression that
    the CRUD's findAll does not surface (e.g. line grids showing raw UUIDs because
    the nested ref json carried only {id}, not {id,code,name});
  * a create INSERT that omits a NOT NULL column with no default/COALESCE.

Everything here is best-effort text parsing over the export's own project-db.dump
and dynamic-cruds.json — it never touches a live DB (see `crud verify` for that).
"""

import re

_FK_RE = re.compile(
    r'"([^"]+)"\s+ADD CONSTRAINT\s+"[^"]+"\s+FOREIGN KEY\s+\("([^"]+)"\)\s+'
    r'REFERENCES\s+"[^"]+"\."([^"]+)"')
# CHECK (((col)::text = ANY (ARRAY['A'::.., 'B'::..]))) or CHECK ((col)::text = 'A')
_CHECK_COL_RE = re.compile(r"\(+\s*([a-z_][a-z0-9_]*)\s*\)?::text")
_CHECK_LIT_RE = re.compile(r"'([^']*)'::")
_CHECK_EQ_LIT_RE = re.compile(r"'([^']*)'")


def camel(s):
    if s is None or "_" not in s:
        return s
    out = []
    up = False
    for c in s:
        if c == "_":
            up = True
        elif up:
            out.append(c.upper())
            up = False
        else:
            out.append(c)
    return "".join(out)


def parse_ddl_columns(ddl):
    """[(name, notnull, default_present)] in DDL order from a CREATE TABLE ddl."""
    cols = []
    for line in (ddl or "").splitlines():
        line = line.strip().rstrip(",")
        m = re.match(r'"([^"]+)"\s+(.+)$', line)
        if not m:
            continue
        if line.upper().startswith(("PRIMARY KEY", "CONSTRAINT", "FOREIGN KEY", "UNIQUE", "CHECK")):
            continue
        rest = m.group(2)
        typ = re.split(r"\s+NOT NULL|\s+DEFAULT|\s+PRIMARY", rest, flags=re.I)[0].strip()
        cols.append({
            "name": m.group(1),
            "type": typ,
            "notnull": "NOT NULL" in rest.upper(),
            "default": bool(re.search(r"\bDEFAULT\b", rest, re.I)),
        })
    return cols


def build_schema_index(db):
    """Return {schema_name: {tables:{t:{columns,notnull,default}}, fks:{t:{col:target}},
    checks:{t:{col:set(allowed_literals) or None}}}}."""
    idx = {}
    for s in db.get("schemas", []) or []:
        name = s.get("name")
        tables = {}
        for t in s.get("tables", []) or []:
            tables[t.get("name")] = parse_ddl_columns(t.get("ddl", ""))
        fks = {}
        for stmt in s.get("foreignKeys", []) or []:
            m = _FK_RE.search(stmt)
            if m:
                fks.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
        checks = {}
        for cc in s.get("checkConstraints", []) or []:
            m = re.search(r'"([^"]+)"\s+ADD CONSTRAINT\s+"[^"]+"\s+CHECK\s+\((.*)\)\s*$', cc, re.S)
            if not m:
                continue
            table = m.group(1)
            body = m.group(2)
            colm = _CHECK_COL_RE.search(body)
            if not colm:
                continue
            col = colm.group(1)
            # only capture simple "IN a set of string literals" checks — the ones
            # a status/enum write must satisfy. Skip range/complex checks (allowed=None).
            lits = _CHECK_LIT_RE.findall(body) or _CHECK_EQ_LIT_RE.findall(body)
            if lits and ("ANY" in body or "=" in body):
                checks.setdefault(table, {})[col] = set(lits)
        idx[name] = {"tables": tables, "fks": fks, "checks": checks}
    return idx


# --------------------------------------------------------------------------
# findAll surfaced-field analysis
# --------------------------------------------------------------------------

_AS_RE = re.compile(r"\bAS\s+([a-z_][a-z0-9_]*)", re.I)
_TCOL_RE = re.compile(r"\bt\.([a-z_][a-z0-9_]*)")
_KEY_RE = re.compile(r"'([A-Za-z_][A-Za-z0-9_]*)'\s*,")


def surfaced_fields(findall_sql, table_columns=None):
    """Parse a findAll SELECT and return:
      roots         - top-level field names the row exposes (camelCase)
      nested_leaves - leaf names reachable under any nested "__" ref object
      list_keys     - {"*": set(keys)} every json key inside the lines/components
                      subqueries (top-level line fields AND nested ref sub-keys)

    `table_columns` (snake) lets a `SELECT *` / `SELECT t.*` findAll resolve — it
    surfaces every column, so we add them all to roots.
    """
    sql = findall_sql or ""
    roots = set()
    nested_leaves = set()
    # Every 'key', inside a json_build_object is a line-grid field (incl. nested
    # ref sub-keys like code/name). json_build_object appears ONLY in the line
    # subqueries, so collecting them across the whole SQL is safe and robust.
    list_key_set = {camel(k) for k in _KEY_RE.findall(sql)}
    # Strip the line subqueries so their inner tokens don't pollute header roots.
    header = re.sub(r"json_agg\(.*?'\[\]'::json\)", " ", sql, flags=re.S | re.I)
    for a in _AS_RE.findall(header):
        parts = a.split("__")
        roots.add(camel(parts[0]))
        if len(parts) > 1:
            nested_leaves.add(camel(parts[-1]))
    for c in _TCOL_RE.findall(header):
        roots.add(camel(c))
    if table_columns and re.search(r"SELECT\s+(?:t\.)?\*", sql, re.I):
        for c in table_columns:
            roots.add(camel(c))
    return roots, nested_leaves, {"*": list_key_set}


# --------------------------------------------------------------------------
# CRUD content consumers (what the UI reads/writes per alias)
# --------------------------------------------------------------------------

def crud_consumers(project):
    """Return {alias: [(expression, kind)]} gathered from crud.table/tree column
    settings, form-control fieldExpressions (CRUD scope), and — crucially — the
    dynaform.form.list.field sub-grid columnSettings (a consumer easy to miss)."""
    from . import core
    out = {}

    def add(alias, expr, kind):
        if alias and expr:
            out.setdefault(alias, []).append((expr, kind))

    for node, _p, _path in core.iter_nodes(project.root_content):
        pn = node.get("pluginName", "") or ""
        if pn in ("crud.table.plugin", "crud.tree.plugin"):
            m = core.get_inner_json(node, "model")
            a = m.get("crudAlias")
            for c in m.get("columnSettings", []) or []:
                add(a, c.get("fieldExpression"), "table-col")
        elif pn == "dynaform.form.list.field.plugin":
            st = core.get_inner_json(node, "settings")
            a = st.get("crudAlias")
            for c in st.get("columnSettings", []) or []:
                add(a, c.get("fieldExpression"), "list-col")
        elif pn.startswith("dynaform.form.") and pn.endswith("field.plugin"):
            st = core.get_inner_json(node, "settings")
            if st.get("scope") == "CRUD":
                add(st.get("crudAlias"), st.get("fieldExpression"), "form-ctrl")
    return out


# --------------------------------------------------------------------------
# SQL literal writes -> (column, literal) pairs
# --------------------------------------------------------------------------

_SET_LIT_RE = re.compile(r"\b([a-z_][a-z0-9_]*)\s*=\s*'([^']*)'")


def literal_column_writes(sql):
    """Yield (column, literal) for `col = 'LITERAL'` writes in an UPDATE/INSERT.
    Best-effort: catches the SET col='X' and simple assignments used by lifecycle
    status methods. Ignores COALESCE/NULLIF wrappers (defaults, not hard writes)."""
    for m in _SET_LIT_RE.finditer(sql or ""):
        col, lit = m.group(1), m.group(2)
        # skip when wrapped by COALESCE/NULLIF just before (a defaulting expr, not a hard write)
        pre = sql[max(0, m.start() - 12):m.start()].upper()
        if "COALESCE" in pre or "NULLIF" in pre:
            continue
        yield col, lit
