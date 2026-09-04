"""argparse wiring for every command. Entry point: main()."""

import argparse
import sys

try:
    # Maintainer-only: absent from the distributed copy (it holds the leak-gate word lists), so the toolkit
    # must stay fully usable without it.
    from . import dist_cmds
except ImportError:  # pragma: no cover
    dist_cmds = None

from . import (case_cmds, content_cmds, core, coverage_cmds, crud_cmds, crudverify_cmds,
               livediff_cmds, db_cmds, inspect_cmds, locale_cmds, mail_cmds, packaging, pdf_cmds,
               quicklink_cmds, rep_cmds, roleaccess_cmds, validate_cmds,
               workflow_cmds)


def _add_project(sp):
    sp.add_argument("--project", default=".", help="unpacked export dir (default: .)")


def _bool_arg(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class _OrderedStep(argparse.Action):
    """Append (kind, value) tuples to a single shared `steps` dest so that
    --user-task / --service-task / --gateway keep their command-line order,
    even when interleaved. `kind` is passed via `const`."""

    def __call__(self, parser, namespace, values, option_string=None):
        steps = getattr(namespace, "steps", None)
        if steps is None:
            steps = []
            setattr(namespace, "steps", steps)
        steps.append((self.const, values))


def _add_dist(sub):
    sp = sub.add_parser("dist", help="assemble the third-party copy of the library and gate it for leaks")
    sp.add_argument("--library", default=".", help="library root (default: .)")
    sp.add_argument("--out", required=True, help="directory to create with the distributable copy")
    sp.add_argument("--force", action="store_true", help="replace --out if it already exists")
    sp.add_argument("--keep-on-fail", action="store_true",
                    help="keep the assembled copy even when the leak gate fails, to inspect it")
    sp.set_defaults(func=dist_cmds.cmd_dist)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mrjun",
        description="Edit UNPACKED .mrjun exports safely (stdlib only).",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="<command>")

    # -- packaging ----------------------------------------------------------
    sp = sub.add_parser("unpack", help="unzip a .mrjun into a dir")
    sp.add_argument("file")
    sp.add_argument("dir")
    sp.set_defaults(func=packaging.cmd_unpack)

    if dist_cmds is not None:
        _add_dist(sub)

    sp = sub.add_parser("pack", help="zip a dir into a .mrjun")
    sp.add_argument("dir")
    sp.add_argument("file")
    sp.set_defaults(func=packaging.cmd_pack)

    # -- inspect ------------------------------------------------------------
    sp = sub.add_parser("inspect", help="counts across every file")
    _add_project(sp)
    sp.set_defaults(func=inspect_cmds.cmd_inspect)

    sp = sub.add_parser("tree", help="siteMapPage hierarchy")
    _add_project(sp)
    sp.add_argument("--page", help="start from this page (id/name)")
    sp.add_argument("--all", action="store_true", help="show every node, not just pages")
    sp.set_defaults(func=inspect_cmds.cmd_tree)

    sp = sub.add_parser("find", help="locate content nodes")
    _add_project(sp)
    sp.add_argument("--plugin")
    sp.add_argument("--name")
    sp.add_argument("--id")
    sp.set_defaults(func=inspect_cmds.cmd_find)

    sp = sub.add_parser("list", help="list entities of a kind")
    _add_project(sp)
    sp.add_argument("kind", help="pages|plugins|rules|forms|formGroups|contexts|"
                                 "queries|sources|roleGroups|cruds|workflows|settings|"
                                 "schemas|tables")
    sp.set_defaults(func=inspect_cmds.cmd_list)

    sp = sub.add_parser("show", help="pretty-print one entity")
    _add_project(sp)
    sp.add_argument("kind", help="node|rule|form|formGroup|context|query|source|crud|page")
    sp.add_argument("key")
    sp.set_defaults(func=inspect_cmds.cmd_show)

    # -- page ---------------------------------------------------------------
    page = sub.add_parser("page", help="content-tree pages").add_subparsers(dest="sub", metavar="<sub>")
    sp = page.add_parser("add", help="add a siteMapPage")
    _add_project(sp)
    sp.add_argument("--parent", required=True, help="parent page id/name or 'root'")
    sp.add_argument("--name", required=True)
    sp.add_argument("--alias")
    grp = sp.add_mutually_exclusive_group()
    grp.add_argument("--auth", action="store_true", help="authenticated users only")
    grp.add_argument("--public", action="store_true", help="public read access")
    sp.add_argument("--layout", help="layout virtualPlugin name")
    sp.set_defaults(func=content_cmds.cmd_page_add)

    sp = page.add_parser("rm", help="remove a page")
    _add_project(sp)
    sp.add_argument("id")
    sp.set_defaults(func=content_cmds.cmd_page_rm)

    sp = page.add_parser("set-redirect", help="set a page's Redirect (the project 'front door'); on root it picks the landing page")
    _add_project(sp)
    sp.add_argument("--page", default="root", help="page id/name (NOT the content alias) or 'root' (default: root/Home)")
    sp.add_argument("--to", required=True, help="target content-alias path relative to root (e.g. cdd-cockpit); '' clears it")
    sp.set_defaults(func=content_cmds.cmd_page_set_redirect)

    sp = page.add_parser("mv", help="reparent a page (preserves identifiers); e.g. move a form page under its table page")
    _add_project(sp)
    sp.add_argument("--id", required=True, help="page id/name to move (NOT the content alias)")
    sp.add_argument("--to-parent", required=True, help="new parent page id/name (NOT the content alias) or 'root'")
    sp.set_defaults(func=content_cmds.cmd_page_mv)

    # -- node ---------------------------------------------------------------
    node = sub.add_parser("node", help="content-tree plugin nodes").add_subparsers(dest="sub", metavar="<sub>")
    sp = node.add_parser("add", help="add a plugin node")
    _add_project(sp)
    sp.add_argument("--parent", required=True, help="parent node/page id or name")
    sp.add_argument("--plugin", required=True, help="pluginName")
    sp.add_argument("--name")
    sp.add_argument("--identifier", help="symbolic identifier (e.g. filter.parsis); default = fresh uuid")
    sp.add_argument("--settings", help="inner settings JSON (@file or literal)")
    sp.add_argument("--model", help="inner model JSON (@file or literal)")
    sp.set_defaults(func=content_cmds.cmd_node_add)

    sp = node.add_parser("rm", help="remove a node")
    _add_project(sp)
    sp.add_argument("id")
    sp.set_defaults(func=content_cmds.cmd_node_rm)

    sp = node.add_parser("set-settings", help="replace properties.settings inner JSON")
    _add_project(sp)
    sp.add_argument("id")
    sp.add_argument("--json", required=True, help="@file or literal JSON")
    sp.set_defaults(func=content_cmds.cmd_node_set_settings)

    sp = node.add_parser("patch-settings", help="patch keys in properties.settings")
    _add_project(sp)
    sp.add_argument("id")
    sp.add_argument("--set", action="append", metavar="key=value",
                    help="typed: str:/num:/bool:/json:/null: prefix (default str)")
    sp.set_defaults(func=content_cmds.cmd_node_patch_settings)

    sp = node.add_parser("set-model", help="replace properties.model inner JSON")
    _add_project(sp)
    sp.add_argument("id")
    sp.add_argument("--json", required=True)
    sp.set_defaults(func=content_cmds.cmd_node_set_model)

    sp = node.add_parser("patch-model", help="patch keys in properties.model")
    _add_project(sp)
    sp.add_argument("id")
    sp.add_argument("--set", action="append", metavar="key=value")
    sp.set_defaults(func=content_cmds.cmd_node_patch_model)

    sp = node.add_parser("set-studio",
                         help="replace properties.studioModel inner JSON (HTML Component Studio: libs/docs/scripts/css; see 24)")
    _add_project(sp)
    sp.add_argument("id")
    sp.add_argument("--json", required=True, help="@file or literal JSON (the studioModel object)")
    sp.set_defaults(func=content_cmds.cmd_node_set_studio)

    # -- asset (tenant-files -> nct-file-storage) ---------------------------
    asset = sub.add_parser(
        "asset", help="tenant-files assets (round-trip into nct-file-storage under t/<tenantId>/)"
    ).add_subparsers(dest="sub", metavar="<sub>")
    sp = asset.add_parser("add", help="copy a local file into tenant-files/<relpath> (e.g. studio/<lib>/<file> for a Studio library)")
    _add_project(sp)
    sp.add_argument("relpath", help="path under t/<tenantId>/ (e.g. studio/echarts/echarts.esm.js)")
    sp.add_argument("file", help="local file to copy in")
    sp.set_defaults(func=content_cmds.cmd_asset_add)
    sp = asset.add_parser("ls", help="list tenant-files assets in the bundle")
    _add_project(sp)
    sp.set_defaults(func=content_cmds.cmd_asset_ls)

    # -- case (per-project notes, kept OUT of the reusable library) ----------
    ca = sub.add_parser(
        "case",
        help="per-project notes in a folder NEXT TO the export (never inside the .mrjun)",
    ).add_subparsers(dest="sub", metavar="<sub>")

    sp = ca.add_parser("init", help="create the <project>-case notes folder + README")
    _add_project(sp)
    sp.add_argument("--dir", help="explicit folder (default: <project-dir>-case, a sibling)")
    sp.add_argument("--force", action="store_true", help="overwrite an existing README.md")
    sp.set_defaults(func=case_cmds.cmd_case_init)

    sp = ca.add_parser("recipes", help="which per-artefact build recipes this project has written")
    sp.add_argument("--project", default=".", help="unpacked export dir (the case folder is its sibling)")
    sp.add_argument("--dir", help="explicit case folder (default: <project-dir>-case)")
    sp.set_defaults(func=case_cmds.cmd_case_recipes)

    sp = ca.add_parser("add", help="write one case note (body from --from or stdin)")
    _add_project(sp)
    sp.add_argument("--dir")
    sp.add_argument("--name", required=True, metavar="slug",
                    help="file name, e.g. 02-decisions (.md added when missing)")
    sp.add_argument("--title", help="heading used when the body has none")
    sp.add_argument("--from", dest="from_file", metavar="file", help="read the body from this file")
    sp.add_argument("--force", action="store_true", help="overwrite an existing note")
    sp.set_defaults(func=case_cmds.cmd_case_add)

    sp = ca.add_parser("ls", help="list the case notes")
    _add_project(sp)
    sp.add_argument("--dir")
    sp.set_defaults(func=case_cmds.cmd_case_ls)

    # -- roleaccess ---------------------------------------------------------
    ra = sub.add_parser("roleaccess", help="content-node roleAccess").add_subparsers(dest="sub", metavar="<sub>")
    sp = ra.add_parser("show", help="show a node's roleAccess")
    _add_project(sp)
    sp.add_argument("id")
    sp.set_defaults(func=roleaccess_cmds.cmd_roleaccess_show)

    sp = ra.add_parser("set", help="set roleAccess flags/roles")
    _add_project(sp)
    sp.add_argument("id")
    sp.add_argument("--public", type=_bool_arg)
    sp.add_argument("--authenticated", type=_bool_arg)
    sp.add_argument("--role", action="append", metavar="name:perms",
                    help="perms subset of view,edit,advancedEdit (or * = all)")
    sp.add_argument("--rolegroup", action="append", metavar="name:perms")
    sp.set_defaults(func=roleaccess_cmds.cmd_roleaccess_set)

    # -- quicklink (left-nav) -----------------------------------------------
    ql = sub.add_parser("quicklink", help="left-nav quick links (site.kicker.plugin modelGroups)").add_subparsers(dest="sub", metavar="<sub>")
    sp = ql.add_parser("list", help="print the left-nav quick-links tree(s)")
    _add_project(sp)
    sp.add_argument("--all", action="store_true",
                    help="print per-node instead of the distinct deduped trees")
    sp.set_defaults(func=quicklink_cmds.cmd_quicklink_list)

    sp = ql.add_parser("add", help="append an internal quick link to the shared 'Nct left nav' node (the one that renders)")
    _add_project(sp)
    sp.add_argument("--page", required=True, help="target siteMapPage id/name")
    sp.add_argument("--label", help="link text — ONE string, copied to every locale (use for a single-locale project)")
    sp.add_argument("--label-loc", action="append", metavar="locale=text",
                    help="per-locale label, e.g. --label-loc en_US=Home --label-loc hy_AM=Տուն (multilingual navs — doc 20)")
    sp.add_argument("--group", help="group name to nest under (created if missing); omit for top level")
    sp.add_argument("--group-loc", action="append", metavar="locale=text",
                    help="per-locale GROUP heading, e.g. --group-loc en_US=Directories --group-loc hy_AM=Տեղեկատուներ "
                         "(localizes the nav section header — omit and a multi-locale nav shows it in one language, doc 20)")
    sp.add_argument("--icon", help="icon class (default %s)" % quicklink_cmds.DEFAULT_LINK_ICON)
    sp.add_argument("--params", help="optional linkModel.params appended to the internal link")
    sp.set_defaults(func=quicklink_cmds.cmd_quicklink_add)

    sp = ql.add_parser("add-external", help="append an external (URL) quick link to the shared 'Nct left nav' node")
    _add_project(sp)
    sp.add_argument("--group", help="group name to nest under (created if missing); omit for top level")
    sp.add_argument("--label", help="link text — ONE string, copied to every locale (single-locale project)")
    sp.add_argument("--label-loc", action="append", metavar="locale=text",
                    help="per-locale label (multilingual navs — doc 20)")
    sp.add_argument("--url", required=True, help="external URL (https://...)")
    sp.add_argument("--icon", help="icon class (default %s)" % quicklink_cmds.DEFAULT_LINK_ICON)
    sp.set_defaults(func=quicklink_cmds.cmd_quicklink_add_external)

    sp = ql.add_parser("rm", help="remove quick links whose name/label matches, from all left-nav nodes")
    _add_project(sp)
    sp.add_argument("--label", required=True, help="link name/label to remove")
    sp.set_defaults(func=quicklink_cmds.cmd_quicklink_rm)

    # -- locale -------------------------------------------------------------
    loc = sub.add_parser("locale", help="per-locale text map coverage").add_subparsers(dest="sub", metavar="<sub>")
    sp = loc.add_parser("fill", help="copy each flat per-locale map's default value into every missing tenant locale (verbatim, no translation)")
    _add_project(sp)
    sp.set_defaults(func=locale_cmds.cmd_locale_fill)
    sp = loc.add_parser("set-default", help="set (or show) tenant.json defaultLocale — the project's default/authoritative language")
    _add_project(sp)
    sp.add_argument("--locale", help="a locale from tenant.json.locales (e.g. hy_AM); omit to print the current value")
    sp.set_defaults(func=locale_cmds.cmd_locale_set_default)

    # -- rolegroup ----------------------------------------------------------
    rg = sub.add_parser("rolegroup", help="rep-objects roleGroups").add_subparsers(dest="sub", metavar="<sub>")
    sp = rg.add_parser("add", help="add a project roleGroup")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--role", action="append", help="a ROLE constant (repeatable)")
    sp.set_defaults(func=rep_cmds.cmd_rolegroup_add)
    sp = rg.add_parser("rm", help="remove a project roleGroup")
    _add_project(sp)
    sp.add_argument("name")
    sp.set_defaults(func=rep_cmds.cmd_rolegroup_rm)
    sp = rg.add_parser("list", help="list project roleGroups")
    _add_project(sp)
    sp.set_defaults(func=rep_cmds.cmd_rolegroup_list)

    # -- context ------------------------------------------------------------
    ctx = sub.add_parser("context", help="rep-objects contexts").add_subparsers(dest="sub", metavar="<sub>")
    sp = ctx.add_parser("add", help="create a context (and bind crudAliases)")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--alias", required=True)
    sp.add_argument("--crud", action="append", help="crud alias to include (repeatable)")
    sp.set_defaults(func=rep_cmds.cmd_context_add)
    sp = ctx.add_parser("add-alias", help="add crud alias(es) to a context (idempotent)")
    _add_project(sp)
    sp.add_argument("context", help="context id/alias/name")
    sp.add_argument("alias", nargs="+")
    sp.set_defaults(func=rep_cmds.cmd_context_add_alias)

    # -- rule ---------------------------------------------------------------
    rule = sub.add_parser("rule", help="rep-objects rules").add_subparsers(dest="sub", metavar="<sub>")
    sp = rule.add_parser("add", help="create a rule (PREDICATE / EXECUTION_RULE / VALIDATION_RULE)")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--type", required=True, help="PREDICATE|EXECUTION_RULE|VALIDATION_RULE")
    sp.add_argument("--context", required=True, help="context id/alias/name")
    sp.add_argument("--script", required=True, help="@file or literal Groovy")
    sp.add_argument("--desc")
    sp.set_defaults(func=rep_cmds.cmd_rule_add)
    sp = rule.add_parser("rm", help="remove a rule")
    _add_project(sp)
    sp.add_argument("id")
    sp.set_defaults(func=rep_cmds.cmd_rule_rm)

    # -- query --------------------------------------------------------------
    q = sub.add_parser("query", help="rep-objects queries").add_subparsers(dest="sub", metavar="<sub>")
    sp = q.add_parser("add", help="create a saved query")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--source", required=True, help="source id/name")
    sp.add_argument("--sql", required=True, help="@file or literal SQL")
    sp.add_argument("--items-per-page", type=int)
    sp.set_defaults(func=rep_cmds.cmd_query_add)

    # -- source -------------------------------------------------------------
    src = sub.add_parser("source", help="rep-objects sources").add_subparsers(dest="sub", metavar="<sub>")
    sp = src.add_parser("add", help="create a source (INTERNAL / EXTERNAL)")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--dbtype", required=True, help="|".join(core.DBTYPE_CANONICAL))
    sp.add_argument("--host", required=True)
    sp.add_argument("--port", required=True)
    sp.add_argument("--db", required=True)
    sp.add_argument("--schema", required=True)
    sp.add_argument("--user", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--desc")
    sp.add_argument("--source-type", default="INTERNAL")
    sp.set_defaults(func=rep_cmds.cmd_source_add)

    # -- formgroup ----------------------------------------------------------
    fg = sub.add_parser("formgroup", help="rep-objects formGroups").add_subparsers(dest="sub", metavar="<sub>")
    sp = fg.add_parser("add", help="create a form group")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--context", required=True)
    sp.add_argument("--content-page", help="contentPageIdentifier (form-group landing content node)")
    sp.add_argument("--place-next-to-landing", action="store_true")
    sp.set_defaults(func=rep_cmds.cmd_formgroup_add)

    sp = fg.add_parser("set", help="patch an existing form group's page wiring (mirrors into forms[].formGroup copies)")
    _add_project(sp)
    sp.add_argument("--id", required=True, help="formGroup id/name")
    sp.add_argument("--content-page", help="set contentPageIdentifier (the per-CRUD landing page identifier)")
    sp.add_argument("--form-groups-page", help="set formGroupsPageIdentifier")
    sp.add_argument("--no-list", action="store_true", help="null the formGroupsPageIdentifier (Create-Default-Actions convention)")
    sp.add_argument("--place-next-to-landing", choices=["on", "off"], help="set placeFormsNextToLanding")
    sp.set_defaults(func=rep_cmds.cmd_formgroup_set)

    # -- form ---------------------------------------------------------------
    form = sub.add_parser("form", help="rep-objects forms").add_subparsers(dest="sub", metavar="<sub>")
    sp = form.add_parser("add", help="create a form (FormDto rep-object)")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--formgroup", required=True, help="formGroup id/name")
    sp.add_argument("--context", required=True)
    sp.add_argument("--content", help="contentIdentifier (the form page content node)")
    sp.set_defaults(func=rep_cmds.cmd_form_add)

    # -- mailtemplate -------------------------------------------------------
    mt = sub.add_parser("mailtemplate", help="rep-objects mailTemplates").add_subparsers(dest="sub", metavar="<sub>")
    sp = mt.add_parser("add", help="add a mail template")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--subject", required=True, help="email subject (may contain {{placeholder}})")
    sp.add_argument("--html", required=True, help="email HTML body (@file or literal)")
    sp.add_argument("--alias", help="Groovy handle (^[a-z][a-zA-Z0-9]*$); derived from name if omitted")
    sp.add_argument("--css", help="extra CSS (@file or literal)")
    sp.add_argument("--placeholder", action="append",
                    help="a {{placeholder}} name (repeatable); auto-scanned from html/subject if omitted")
    sp.add_argument("--desc")
    sp.set_defaults(func=mail_cmds.cmd_mailtemplate_add)
    sp = mt.add_parser("list", help="list mail templates")
    _add_project(sp)
    sp.set_defaults(func=mail_cmds.cmd_mailtemplate_list)
    sp = mt.add_parser("rm", help="remove a mail template")
    _add_project(sp)
    sp.add_argument("id", help="mailTemplate id/name/alias")
    sp.set_defaults(func=mail_cmds.cmd_mailtemplate_rm)

    # -- workflow -----------------------------------------------------------
    wf = sub.add_parser("workflow", help="rep-objects workflows (BPMN)").add_subparsers(dest="sub", metavar="<sub>")
    sp = wf.add_parser("add", help="generate a skeleton executable workflow (start -> ordered steps -> end)")
    _add_project(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--context", action="append", help="context id/alias/name (repeatable)")
    sp.add_argument("--user-task", dest="steps", action=_OrderedStep, const="user",
                    metavar='"NAME[:<formGroup id|name>]"',
                    help="a user task (repeatable); optional :formGroup binds it via "
                         "flowable:userActions. Steps chain in command-line order.")
    sp.add_argument("--service-task", dest="steps", action=_OrderedStep, const="service",
                    metavar='"NAME:<rule id|name>"',
                    help="a serviceTask running rule via flowable:delegateExpression=${ruleTask} "
                         "+ flowable:rule=<uuid> (rule resolved in rep-objects.rules).")
    sp.add_argument("--gateway", dest="steps", action=_OrderedStep, const="gateway",
                    metavar="NAME",
                    help="an exclusiveGateway placeholder (one incoming + one outgoing); "
                         "add branch conditions by hand afterwards.")
    sp.add_argument("--desc")
    sp.set_defaults(func=workflow_cmds.cmd_workflow_add)
    sp = wf.add_parser("list", help="list workflows")
    _add_project(sp)
    sp.set_defaults(func=workflow_cmds.cmd_workflow_list)

    # -- pdftemplate --------------------------------------------------------
    pdf = sub.add_parser("pdftemplate", help="pdfme templates (add -> rep-objects.pdfTemplates[]; scaffold -> file)").add_subparsers(dest="sub", metavar="<sub>")
    sp = pdf.add_parser("add", help="add a pdfme template (from a JSON file) to rep-objects.pdfTemplates[] (exported/imported with the .mrjun)")
    _add_project(sp)
    sp.add_argument("--alias", required=True, help="Groovy handle (^[a-z][a-zA-Z0-9]*$) for service.report.pdf.get.<alias>")
    sp.add_argument("--name", required=True, help="display name (unique per realm/client)")
    sp.add_argument("--template", required=True, metavar="@file.json", help="the pdfme template JSON (@file or inline)")
    sp.add_argument("--desc", help="description")
    sp.set_defaults(func=pdf_cmds.cmd_pdftemplate_add)
    sp = pdf.add_parser("scaffold", help="write a BARE standalone pdfme template JSON to a file (fill in the layout before use)")
    sp.add_argument("alias", help="template alias (^[a-z][a-zA-Z0-9]*$)")
    sp.add_argument("--out", required=True, help="output .json file (project is never touched)")
    sp.add_argument("--field", action="append", metavar="name:type",
                    help="a pdfme field (repeatable): text|multiVariableText|image|line|rectangle|qrcode|date|...")
    sp.set_defaults(func=pdf_cmds.cmd_pdftemplate_scaffold)
    sp = pdf.add_parser("note", help="print the pdfme-template guidance (they ARE carried in rep-objects.pdfTemplates[])")
    sp.set_defaults(func=pdf_cmds.cmd_pdftemplate_note)

    # -- crud ---------------------------------------------------------------
    crud = sub.add_parser("crud", help="dynamic CRUDs").add_subparsers(dest="sub", metavar="<sub>")
    sp = crud.add_parser("add", help="create a dynamic CRUD (+ --scaffold-methods)")
    _add_project(sp)
    sp.add_argument("--alias", required=True)
    sp.add_argument("--name", required=True)
    sp.add_argument("--source", required=True, help="source id/name")
    sp.add_argument("--schema", required=True, help="sourceSchema")
    sp.add_argument("--field", action="append", metavar="name:Type",
                    help="dtoField (repeatable)")
    sp.add_argument("--localization-field", default="localized")
    sp.add_argument("--context", help="context id/alias/name; appends the new alias "
                    "to that context's crudAliases in the same call (idempotent)")
    sp.add_argument("--scaffold-methods", action="store_true",
                    help="create find/findAll/count/get/create/update/delete + paired queries")
    sp.set_defaults(func=crud_cmds.cmd_crud_add)

    sp = crud.add_parser("add-method", help="add a method to a dynamic CRUD (SQL or GROOVY)")
    _add_project(sp)
    sp.add_argument("alias")
    sp.add_argument("--name", required=True)
    sp.add_argument("--type", required=True, help="SQL|GROOVY")
    sp.add_argument("--query", help="queryIdentifier (SQL methods)")
    sp.add_argument("--rule", help="ruleIdentifier (GROOVY methods)")
    sp.add_argument("--script", help="@file or literal")
    sp.add_argument("--returns-array", action="store_true")
    sp.set_defaults(func=crud_cmds.cmd_crud_add_method)

    sp = crud.add_parser("apply", help="give every GROOVY method a ruleIdentifier — the "
                                       "offline equivalent of the UI's \"Apply\" (idempotent)")
    _add_project(sp)
    sp.set_defaults(func=crud_cmds.cmd_crud_apply)

    sp = crud.add_parser("list", help="list dynamic CRUDs and their methods")
    _add_project(sp)
    sp.set_defaults(func=crud_cmds.cmd_crud_list)

    sp = crud.add_parser("verify", help="execute every SQL method against a live DB "
                                        "(reads direct, writes rolled back, fixtures seeded)")
    _add_project(sp)
    sp.add_argument("--db", required=True,
                    help='libpq conninfo, e.g. "host=localhost port=5432 dbname=prj_x '
                         'user=<user> password=<password>"')
    sp.add_argument("--schema", help="override the CRUD sourceSchema")
    sp.add_argument("--crud", help="only these aliases (comma-separated)")
    sp.set_defaults(func=crudverify_cmds.cmd_crud_verify)

    # -- livediff -----------------------------------------------------------
    sp = sub.add_parser("livediff", help="compare the LIVE imported content tree in the platform DB "
                                         "against the packed project (catches blank pages that leave "
                                         "no log line); also prints the PACKED rep-object counts")
    _add_project(sp)
    sp.add_argument("--db", required=True,
                    help='libpq conninfo for the PLATFORM db, e.g. "host=localhost port=5432 '
                         'dbname=<platform-db> user=<user> password=<password>"')
    sp.add_argument("--tenant", required=True, help="tenant alias — the segment after the realm in the project URL, "
                              "e.g. the 'dd' in /<realm>/dd/...")
    sp.set_defaults(func=livediff_cmds.cmd_livediff)

    # -- db -----------------------------------------------------------------
    db = sub.add_parser("db", help="project-db.dump").add_subparsers(dest="sub", metavar="<sub>")
    sp = db.add_parser("list-schemas", help="list schemas in project-db.dump")
    _add_project(sp)
    sp.set_defaults(func=db_cmds.cmd_db_list_schemas)
    sp = db.add_parser("list-tables", help="list tables of a schema")
    _add_project(sp)
    sp.add_argument("--schema")
    sp.set_defaults(func=db_cmds.cmd_db_list_tables)
    sp = db.add_parser("show", help="show a table's columns + CHECK/UNIQUE/FK constraints")
    _add_project(sp)
    sp.add_argument("table")
    sp.add_argument("--schema")
    sp.set_defaults(func=db_cmds.cmd_db_show)
    sp = db.add_parser("add-schema", help="add a schema to the dump")
    _add_project(sp)
    sp.add_argument("name")
    sp.set_defaults(func=db_cmds.cmd_db_add_schema)
    sp = db.add_parser("add-table", help="add a table to the dump (DDL + JDBC columnTypes)")
    _add_project(sp)
    sp.add_argument("--schema", required=True)
    sp.add_argument("--name", required=True)
    sp.add_argument("--column", action="append", required=True,
                    metavar="name:type[:pk][:notnull][:default=...]")
    sp.set_defaults(func=db_cmds.cmd_db_add_table)

    # -- validate -----------------------------------------------------------
    sp = sub.add_parser("validate", help="integrity checks (non-zero exit on errors)")
    _add_project(sp)
    sp.set_defaults(func=validate_cmds.cmd_validate)

    # -- coverage -----------------------------------------------------------
    sp = sub.add_parser("coverage", help="gate the build against a plan.json (every PRD requirement built + done)")
    _add_project(sp)
    sp.add_argument("--plan", help="plan.json: {items:[{id,kind,alias/name,status,test}]} — the decomposed PRD")
    sp.add_argument("--emit", action="store_true", help="print a plan skeleton (status=done) from what's in the build")
    sp.add_argument("--report-only", action="store_true", help="report, never non-zero exit (default: FAIL the gate)")
    sp.add_argument("--show-orphans", action="store_true", help="list built artifacts not covered by the plan")
    sp.set_defaults(func=coverage_cmds.cmd_coverage)

    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        rc = args.func(args)
        return rc if isinstance(rc, int) else 0
    except core.ToolError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except BrokenPipeError:
        return 0
