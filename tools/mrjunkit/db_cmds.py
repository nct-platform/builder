"""project-db.dump commands: db list-schemas/list-tables, db add-schema/add-table.

project-db.dump is JSON, format nct-jdbc-dump-v1:
  {format, database, schemas:[{name, enumTypes, foreignKeys[], uniqueConstraints[],
   checkConstraints[], indexes[], tables[], sequences[], views[], functions[],
   triggers[]}]}
Each table = {name, ddl, columns[], columnTypes[], rows[], rowCount}."""

from . import core

# Friendly column type -> (SQL DDL type, JDBC type code as seen in columnTypes)
TYPE_MAP = {
    "int": ("integer", 4),
    "integer": ("integer", 4),
    "smallint": ("smallint", 5),
    "bigint": ("bigint", -5),
    "serial": ("integer", 4),
    "bigserial": ("bigint", -5),
    "text": ("text", 12),
    "varchar": ("VARCHAR(255)", 12),
    "string": ("VARCHAR(255)", 12),
    "bool": ("boolean", -7),
    "boolean": ("boolean", -7),
    "date": ("date", 91),
    "timestamp": ("timestamp", 93),
    "numeric": ("numeric", 2),
    "decimal": ("numeric", 2),
    "double": ("double precision", 8),
    "float": ("double precision", 8),
    "jsonb": ("jsonb", 1111),
    "json": ("json", 1111),
    "uuid": ("uuid", 1111),
}


# ---------------------------------------------------------------------------
# The cell contract — every value in `rows[]` is a STRING or null
# ---------------------------------------------------------------------------
# This is not a style preference, it is the restorer's signature. nct-repository
# reads the rows as
#
#     List<Map<String, String>> rows = (List<Map<String, String>>) tableDump.get("rows");
#     ...
#     String val = row.get(columns.get(i));            // <-- implicit checkcast
#     setTypedParameter(ps, i + 1, val, sqlType);      // ps.setObject(idx, val, sqlType)
#
# Generics are erased, so the cast lands on that one assignment. A JSON number or
# a JSON boolean parses to Integer/Double/Boolean and the line throws
#
#     class java.lang.Integer cannot be cast to class java.lang.String
#
# ClassCastException is not SQLException, so it misses the per-table savepoint
# catch and unwinds the WHOLE schema restore. The user is told
# "The database was NOT replaced. Schema(s) [x] were rolled back" — an import that
# looks like a database-shape problem and is really one unquoted integer.
#
# The typing is done by `columnTypes` (JDBC codes), never by the JSON type: the
# driver converts the string "1" to an integer because the parameter is bound as
# Types.INTEGER. The platform's own exporter writes `val.toString()` for every
# non-null cell, which is why no live-exported .mrjun has ever shown this.
#
# ⛔ Do not hand-roll this. Call `dump_cell` / `normalise_rows` on the way in.


def dump_cell(value):
    """One row value -> the string the restorer can cast, or None for SQL NULL.

    bool -> "true"/"false" (what Java's Boolean.toString writes), dict/list ->
    compact JSON for a json/jsonb column, everything else -> str()."""
    import datetime as _dt
    import decimal as _dec
    import json as _json
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, _dec.Decimal)):
        return str(value)
    if isinstance(value, float):
        # repr() would render 1e-05, which no numeric column parses.
        return ("%.10f" % value).rstrip("0").rstrip(".") or "0"
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return str(value)
    if isinstance(value, (dict, list)):
        return _json.dumps(value, ensure_ascii=False)
    if isinstance(value, (bytes, bytearray)):
        raise core.ToolError("binary cell values cannot ride in project-db.dump; "
                             "store base64 text or keep the file in tenant-files/")
    return str(value)


def normalise_rows(columns, rows):
    """Project every row onto `columns` and pass each cell through `dump_cell`.

    Use this for the whole `rows[]` of a table you author — it also guarantees the
    key set matches `columns` positionally, which is what the restorer indexes by."""
    out = []
    for row in rows or []:
        out.append({c: dump_cell(row.get(c)) for c in columns})
    return out


def _empty_schema(name):
    return {
        "name": name, "enumTypes": [], "foreignKeys": [], "uniqueConstraints": [],
        "checkConstraints": [], "indexes": [], "tables": [], "sequences": [],
        "views": [], "functions": [], "triggers": [],
    }


def _find_schema(db, name):
    for s in db.get("schemas", []) or []:
        if s.get("name") == name:
            return s
    return None


def cmd_db_list_schemas(args):
    p = core.Project(args.project)
    for s in p.db.get("schemas", []) or []:
        core.out("%-32s tables=%d sequences=%d"
                 % (s.get("name"), len(s.get("tables", []) or []),
                    len(s.get("sequences", []) or [])))


def cmd_db_list_tables(args):
    p = core.Project(args.project)
    for s in p.db.get("schemas", []) or []:
        if args.schema and s.get("name") != args.schema:
            continue
        for t in s.get("tables", []) or []:
            core.out("%s.%s  columns=%s"
                     % (s.get("name"), t.get("name"), ",".join(t.get("columns", []) or [])))


def _table_ddl_lines(ddl):
    import re
    out = []
    for line in (ddl or "").splitlines():
        s = line.strip().rstrip(",")
        m = re.match(r'"([^"]+)"\s+(.+)$', s)
        if m and not s.upper().startswith(("PRIMARY KEY", "CONSTRAINT", "FOREIGN KEY", "UNIQUE", "CHECK")):
            rest = m.group(2)
            flags = []
            if "NOT NULL" in rest.upper():
                flags.append("NOT NULL")
            dm = re.search(r"\bDEFAULT\s+(.+)$", rest, re.I)
            if dm:
                flags.append("DEFAULT %s" % dm.group(1).strip())
            typ = re.split(r"\s+NOT NULL|\s+DEFAULT|\s+PRIMARY", rest, flags=re.I)[0].strip()
            out.append((m.group(1), typ, " ".join(flags)))
    return out


def cmd_db_show(args):
    """Show a table's columns (type/NOT NULL/default) + its CHECK / UNIQUE / FK
    constraints — the schema facts a dynamic-CRUD build must honor but that
    `list-tables` (columns only) hides (e.g. a status CHECK's allowed value set)."""
    import re
    p = core.Project(args.project)
    found = False
    for s in p.db.get("schemas", []) or []:
        if args.schema and s.get("name") != args.schema:
            continue
        for t in s.get("tables", []) or []:
            if t.get("name") != args.table:
                continue
            found = True
            core.out("TABLE %s.%s  (rows=%s)" % (s.get("name"), t.get("name"), t.get("rowCount")))
            for name, typ, flags in _table_ddl_lines(t.get("ddl", "")):
                core.out("  %-28s %-24s %s" % (name, typ, flags))
            pk = re.search(r'PRIMARY KEY \(([^)]*)\)', t.get("ddl", ""))
            if pk:
                core.out("  PK: %s" % pk.group(1))
            for label, key in (("CHECK", "checkConstraints"), ("UNIQUE", "uniqueConstraints")):
                for c in s.get(key, []) or []:
                    if ('"%s"' % t.get("name")) in c:
                        core.out("  %s: %s" % (label, c[c.find("CHECK" if label == "CHECK" else "UNIQUE"):] if (
                            "CHECK" if label == "CHECK" else "UNIQUE") in c else c))
            for fkstmt in s.get("foreignKeys", []) or []:
                m = re.search(r'"%s" ADD CONSTRAINT "[^"]+" FOREIGN KEY \("([^"]+)"\) '
                              r'REFERENCES "[^"]+"\."([^"]+)"' % re.escape(t.get("name")), fkstmt)
                if m:
                    core.out("  FK: %s -> %s" % (m.group(1), m.group(2)))
    if not found:
        raise core.ToolError("table not found: %s%s"
                             % ((args.schema + ".") if args.schema else "", args.table))


def cmd_db_add_schema(args):
    p = core.Project(args.project)
    db = p.db
    if _find_schema(db, args.name):
        raise core.ToolError("schema already exists: %s" % args.name)
    db.setdefault("schemas", []).append(_empty_schema(args.name))
    p.mark(core.F_DB_DUMP)
    p.save()
    core.out("schema added: %s" % args.name)


def _parse_column(spec):
    """`name:type[:pk][:notnull][:default=...]` -> dict describing the column."""
    parts = spec.split(":")
    name = parts[0]
    raw_type = parts[1] if len(parts) > 1 else "text"
    ddl_type, jdbc = TYPE_MAP.get(raw_type.lower(), (raw_type, 12))
    col = {"name": name, "ddl_type": ddl_type, "jdbc": jdbc,
           "pk": False, "notnull": False, "default": None}
    for flag in parts[2:]:
        fl = flag.lower()
        if fl == "pk":
            col["pk"] = True
            col["notnull"] = True
        elif fl == "notnull":
            col["notnull"] = True
        elif fl.startswith("default="):
            col["default"] = flag.split("=", 1)[1]
    return col


def _build_ddl(schema, table, cols):
    lines = []
    pk_cols = [c["name"] for c in cols if c["pk"]]
    for c in cols:
        piece = '  "%s" %s' % (c["name"], c["ddl_type"])
        if c["notnull"] and not c["pk"]:
            piece += " NOT NULL"
        if c["default"] is not None:
            piece += " DEFAULT %s" % c["default"]
        lines.append(piece)
    if pk_cols:
        lines.append('  PRIMARY KEY (%s)' % ", ".join('"%s"' % c for c in pk_cols))
    return 'CREATE TABLE "%s"."%s" (\n%s\n)' % (schema, table, ",\n".join(lines))


def cmd_db_add_table(args):
    p = core.Project(args.project)
    db = p.db
    schema = _find_schema(db, args.schema)
    if schema is None:
        raise core.ToolError("schema not found: %s (add it first with db add-schema)" % args.schema)
    if any(t.get("name") == args.name for t in schema.get("tables", []) or []):
        raise core.ToolError("table already exists: %s.%s" % (args.schema, args.name))
    if not args.column:
        raise core.ToolError("at least one --column is required")

    cols = [_parse_column(c) for c in args.column]
    table = {
        "name": args.name,
        "ddl": _build_ddl(args.schema, args.name, cols),
        "columns": [c["name"] for c in cols],
        "columnTypes": [c["jdbc"] for c in cols],
        "rows": [],
        "rowCount": 0,
    }
    schema.setdefault("tables", []).append(table)
    p.mark(core.F_DB_DUMP)
    p.save()
    core.out("table added: %s.%s (%d columns)\n%s"
             % (args.schema, args.name, len(cols), table["ddl"]))
