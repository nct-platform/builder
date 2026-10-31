"""validate — automates the reimport checklist. Exits non-zero on errors."""

import hashlib
import html
import json
import os
import re

from . import core
from . import dyncheck
from . import staticpage_cmds

# Flat per-locale text maps: {localeKey: value}. Their top-level keys ARE tenant
# locale strings — so a coverage check (must cover every tenant locale) is valid.
# Nested maps (localizedMap = field->locale->value) and wrapped LOCALIZED_STRING
# property slots are deliberately EXCLUDED (their top keys are field names, not
# locales) to avoid false positives. See 20-localization.md §iv.
_FLAT_LOCALE_MAP_KEYS = {
    "localizedNames", "localizedButtonNames", "localizedLabels",
    "localizedHeaderLabel", "defaultValueLocalized",
    "mandatoryValidationMessages", "validationMessages",
}

_RETURN_RE = re.compile(r"(^|\n)\s*return\b")


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def _collect_identifiers(rep):
    ids = {}
    for coll in core.REP_COLLECTIONS:
        ids[coll] = {o.get("identifier") for o in rep.get(coll, []) or [] if isinstance(o, dict)}
    return ids


def cmd_validate(args):
    p = core.Project(args.project)
    # An export carries the parts its author ticked (doc 00 §"Export shape"): one without pages has no branches.json,
    # one without the database no project-db.dump. Both are valid; every check reads the parts that ARE there, and a
    # reference into a part the file does not carry is resolved by the import in the target project, not here.
    not_carried = p.stand_in_absent_parts()
    rep = p.rep
    r = Report()

    # A wrong-typed rep-object field aborts the platform's import before anything is applied, and it
    # also breaks every check below (they all read these shapes). Report it alone and stop.
    _check_rep_object_field_types(p, r)
    _check_dynamic_cruds_envelope(p, r)
    if r.errors:
        core.out("\nERRORS (%d):" % len(r.errors))
        for e in r.errors:
            core.out("  x %s" % e)
        core.out("\nFAIL — malformed export file; the remaining checks were not run.")
        return 1

    # -- rep-objects.apiExposures: absent or null is the only value a build may carry (doc 32 §6) --
    _check_api_exposures(p, r, getattr(args, "keep_api_exposures", False))

    ids = _collect_identifiers(rep)
    context_ids = ids["contexts"]
    query_ids = ids["queries"]
    queries_by_id = {q.get("identifier"): q for q in rep.get("queries", []) or []}
    source_ids = ids["sources"]
    formgroup_ids = ids["formGroups"]
    form_ids = ids["forms"]
    rule_ids = ids["rules"]
    rules_by_id = {x.get("identifier"): x for x in rep.get("rules", []) or [] if isinstance(x, dict)}

    # crud aliases declared across all contexts
    all_ctx_aliases = set()
    for c in rep.get("contexts", []) or []:
        all_ctx_aliases.update(c.get("crudAliases", []) or [])

    crud_file = p.cruds_file
    cruds = (crud_file.data.get("cruds", []) if crud_file else []) or []
    crud_aliases = {c.get("alias") for c in cruds}

    # -- rep object id must be null (§3) ------------------------------------
    for coll in ("sources", "queries", "rules", "contexts", "forms", "formGroups"):
        for o in rep.get(coll, []) or []:
            if o.get("id") is not None:
                r.err("%s %r has non-null id (%s); rep-objects must have id=null"
                      % (coll[:-1], o.get("name") or o.get("identifier"), o.get("id")))

    # -- settings[].content must be a JSON OBJECT, not a string -------------
    # The importer reads a settings record's `content` as a JSON object node. A
    # JSON *string* there aborts the WHOLE import (a type-mismatch error on
    # settings[].content) — the REPORT-path never runs, so
    # sources aren't registered ("No source selected") and project-db.dump isn't
    # restored (data/dates appear lost). This is distinct from the node's
    # properties.model.stringValue, which IS a JSON string — do not confuse them.
    # `node set-model`/`patch-model` keep this mirror correct automatically.
    for s in rep.get("settings", []) or []:
        if isinstance(s.get("content"), str):
            r.err("settings %r (type %s): content is a JSON string but "
                  "a settings record's content must be a JSON object — a string here "
                  "aborts the platform import (type-mismatch error). "
                  "Parse it to an object before packing (or use `node set-model`, "
                  "which syncs the mirror correctly)."
                  % (s.get("name"), s.get("type")))

    # -- generalized rep-object field type consistency (catch the whole class) --
    # validate does NOT deserialize into the platform DTOs, so ANY rep-object field
    # that is a JSON *string* where the platform expects an object/array
    # aborts the ENTIRE rep-objects import (a type-mismatch error).
    # Because one bad object skips the whole block, the symptoms are scattered and
    # data-shaped, NOT error-shaped: empty context + rules failing "No CRUD found with
    # alias X in context Y", "No source selected", project-db.dump not restored (data
    # gone). We can't see the DTO field types, but we CAN flag internal inconsistency:
    # if a field is an object/array in SOME elements of a collection and a bare string
    # in another, the string one is almost certainly wrong-typed. (The settings.content
    # check above additionally covers the always-object case even when every element is
    # a string.) Diagnose the real thing in the platform's log/ui.log trace.
    for coll in core.REP_COLLECTIONS:
        items = [o for o in rep.get(coll, []) or [] if isinstance(o, dict)]
        if len(items) < 2:
            continue
        structural = set()
        for o in items:
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    structural.add(k)
        singular = coll[:-1] if coll.endswith("s") else coll
        for o in items:
            for k in structural:
                if isinstance(o.get(k), str):
                    r.err("%s %r: field %r is a JSON string but is a JSON object/array in "
                          "other %s elements — a wrong-typed rep-object field aborts the "
                          "WHOLE rep-objects import (type-mismatch error; "
                          "scattered symptoms: empty context, 'No source selected', missing "
                          "data). Fix the field's type before packing."
                          % (singular, o.get("name") or o.get("identifier"), k, coll))

    # -- rules: executor mapping + missing return (§5) ----------------------
    for rule in rep.get("rules", []) or []:
        rt = rule.get("ruleType")
        exp = core.RULE_EXECUTOR.get(rt)
        if exp and rule.get("executor") != exp:
            r.err("rule %r: ruleType %s should have executor %s, got %s"
                  % (rule.get("name"), rt, exp, rule.get("executor")))
        for ci in rule.get("contextIdentifiers", []) or []:
            if ci not in context_ids:
                # Dangling rule->context refs occur in shipped, importable exports
                # (the platform imports them fine), matching the tolerance already
                # granted to orphaned
                # formGroup mappings / crud groovy rules / queries -> warn, not err.
                r.warn("rule %r references dangling contextIdentifier %s" % (rule.get("name"), ci))
        if rt in ("PREDICATE", "EXECUTION_RULE"):
            # `rule` should be an object {ruleScriptStr}; guard against a malformed
            # string (already flagged by the type-consistency check) so validate
            # reports cleanly instead of crashing.
            rr = rule.get("rule")
            if isinstance(rr, dict):
                script = rr.get("ruleScriptStr", "") or ""
                if not _RETURN_RE.search(script):
                    r.warn("rule %r (%s) has no top-level `return`" % (rule.get("name"), rt))

    # -- queries: sourceIdentifier ------------------------------------------
    # Some sources are platform-internal and never appear in sources[] (e.g. the
    # default Rimm*/Countries queries in the baseline). So a dangling source is a
    # warning, EXCEPT when it names a source that WAS defined in this export but
    # is now missing — still just a warning to avoid false failures on baselines.
    rimm_src = p.rimm_source_identifier()
    # A source an INTEGRATION provides is legitimately absent from sources[]: the import creates it
    # from integrations.json.dataSourceIdentifiers (doc 00 §9), so it is not dangling.
    integrations = p.integrations
    declared_data_sources = set()
    for ig in integrations:
        if isinstance(ig, dict):
            for sid in (ig.get("dataSourceIdentifiers") or []):
                if isinstance(sid, str) and sid.strip():
                    declared_data_sources.add(sid)
    for q in rep.get("queries", []) or []:
        si = q.get("sourceIdentifier")
        if si and si not in source_ids and si != rimm_src and si not in declared_data_sources:
            r.warn("query %r references sourceIdentifier %s not in sources[] "
                   "(ok if platform-internal)" % (q.get("name"), si))

    # -- integration data sources (doc 00 §9) -------------------------------
    # The trap this catches is the one that ships a statically integrated project with dead charts:
    # the integration's data schema is created PER PROJECT at the target, so a query bound to the
    # source the project was BUILT against keeps reading the builder's database after import — which
    # in the target is unreachable or, worse, present and empty. Declaring the source in
    # integrations.json is what makes the import rebind it.
    used_source_ids = {q.get("sourceIdentifier") for q in (rep.get("queries", []) or [])
                       if q.get("sourceIdentifier")}
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "chart.js.plugin":
            continue
        blob = core.get_inner_json(node, "Javascript")
        if isinstance(blob, dict):
            for repl in (blob.get("replacements") or []):
                qq = repl.get("query") or {}
                if qq.get("sourceIdentifier"):
                    used_source_ids.add(qq["sourceIdentifier"])
    for sid in sorted(declared_data_sources):
        if sid not in used_source_ids and sid not in source_ids:
            r.warn("integrations.json declares data source %s, but no query or chart embed uses it "
                   "and sources[] has no row for it — the declaration binds nothing (doc 00 §9)" % sid)
    has_internal_integration = any(isinstance(ig, dict) and not ig.get("external")
                                   for ig in integrations)
    if has_internal_integration:
        sources_by_id = {s.get("identifier"): s for s in (rep.get("sources", []) or [])}
        for sid in sorted(used_source_ids - declared_data_sources):
            src = sources_by_id.get(sid)
            if src is None or src.get("sourceType") == "INTERNAL" or sid == rimm_src:
                continue  # INTERNAL rows are repointed at the target's own project DB by the import
            r.warn("this project ships an INTERNAL integration, and its queries read source %r "
                   "(%s://%s/%s.%s) which is NOT declared in integrations.json.dataSourceIdentifiers — "
                   "on import those queries keep pointing at that database instead of the target's own "
                   "integration schema. Declare it if the integration is what provides this data "
                   "(doc 00 §9)"
                   % (src.get("name"), str(src.get("sourceType")).lower(), src.get("hostName"),
                      src.get("dbName"), src.get("schemaName")))

    # -- forms / formGroups -------------------------------------------------
    for fg in rep.get("formGroups", []) or []:
        for ci in fg.get("contextIdentifiers", []) or []:
            if ci not in context_ids:
                r.err("formGroup %r dangling contextIdentifier %s" % (fg.get("name"), ci))
        # Mapping refs to deleted predicates/forms are tolerated by the platform
        # (real working exports carry orphaned mappings) -> warn, don't fail.
        for m in (fg.get("predicateFormMapping") or {}).get("mapping", []) or []:
            if m.get("predicateIdentifier") and m["predicateIdentifier"] not in rule_ids:
                r.warn("formGroup %r mapping references dangling predicateIdentifier %s"
                       % (fg.get("name"), m["predicateIdentifier"]))
            if m.get("formIdentifier") and m["formIdentifier"] not in form_ids:
                r.warn("formGroup %r mapping references dangling formIdentifier %s"
                       % (fg.get("name"), m["formIdentifier"]))
    for form in rep.get("forms", []) or []:
        for ci in form.get("contextIdentifiers", []) or []:
            if ci not in context_ids:
                r.err("form %r dangling contextIdentifier %s" % (form.get("name"), ci))

    # -- dynamic cruds ------------------------------------------------------
    for crud in cruds:
        alias = crud.get("alias")
        # Only when the archive carries the contexts: without them (they travel with the pages) the import keeps the
        # target's contexts, each still exposing the CRUDs it exposed that the target has (doc 00 §"Re-linking").
        if isinstance(rep.get("contexts"), list) and alias not in all_ctx_aliases:
            r.err("crud alias %r is not listed in any context.crudAliases" % alias)
        si = crud.get("sourceIdentifier")
        # the rimm/platform source is valid even though it isn't in sources[]
        if si and si not in source_ids and si != rimm_src:
            r.warn("crud %r references sourceIdentifier %s not in sources[] "
                   "(ok if platform-internal)" % (alias, si))
        for m in crud.get("methods", []) or []:
            if m.get("methodType") == "SQL" and m.get("queryIdentifier"):
                if m["queryIdentifier"] not in query_ids:
                    r.err("crud %r method %r references dangling queryIdentifier %s"
                          % (alias, m.get("methodName"), m["queryIdentifier"]))
                else:
                    _check_sql_mirror(alias, m, queries_by_id.get(m["queryIdentifier"]), r)
            if m.get("methodType") == "GROOVY" and m.get("ruleIdentifier"):
                # A GROOVY method's ruleIdentifier MAY be missing from rep-objects.rules[]: a platform export
                # carries the hidden rule there (with the business logic), but an archive built by hand does not,
                # and the importer then creates it from the method's own `script`. So "not in rule_ids"
                # is only a defect when there is no script either — and that case is reported
                # by _check_groovy_method_rule_identifier, which knows why.
                if m["ruleIdentifier"] not in rule_ids and not (m.get("script") or "").strip():
                    r.warn("crud %r method %r references dangling ruleIdentifier %s"
                           % (alias, m.get("methodName"), m["ruleIdentifier"]))
                # When the archive DOES carry that rule, the import saves it as it is and builds the rule from the
                # script only when the project has none — so the rule's body is what the method runs, and a script
                # edited without its rule (or the reverse) changes nothing.
                carried = rules_by_id.get(m["ruleIdentifier"])
                if carried is not None and (m.get("script") or "").strip() and _script_text(
                        (carried.get("rule") or {}).get("ruleScriptStr") if isinstance(carried.get("rule"), dict)
                        else None) != _script_text(m.get("script")):
                    r.err("crud %r method %r: its `script` and the rule it runs (rep-objects.rules %r, the same "
                          "ruleIdentifier) are different texts — the import saves that rule as rules[] carries it and "
                          "builds the rule from the script only when the project has none, so the method would run "
                          "the RULE's body. Change both together, or delete the rule from rules[] so the import builds "
                          "it from the script. (00 §The hidden Groovy rule)"
                          % (alias, m.get("methodName"), carried.get("name") or m["ruleIdentifier"]))
        # source schema must exist in project-db.dump — when the archive carries one. Without it the business logic
        # is imported onto the target's OWN schemas (doc 00 §"Re-linking"), which only the target can answer for.
        schema = crud.get("sourceSchema")
        if schema and not p.is_stand_in(core.F_DB_DUMP) and not _schema_exists(p, schema):
            r.err("crud %r sourceSchema %r not found in project-db.dump" % (alias, schema))

    # -- dynamic-CRUD runtime-correctness checks (schema-aware) -------------
    if cruds:
        _check_dynamic_cruds(p, cruds, r)
        _check_groovy_method_params(cruds, r)
        _check_enum_dropdowns(p, r)
        _check_dropdown_model_binding(p, r)
    _check_choices_rules(p, r)
    _check_choices_pair_keys(p, r)
    _check_crud_method_refs(p, r)
    # -- a GROOVY method without a ruleIdentifier never runs its own script (empty dropdowns) --
    _check_groovy_method_rule_identifier(p, r)
    # -- `<ref>__id` alone: a form dropdown sends a scalar, the FK lands NULL --
    _check_groovy_fk_param_shapes(p, r)
    # -- a physical DELETE on a referenced table, or a soft-delete marker nobody reads --
    _check_soft_delete_discipline(p, r)
    # -- mutating chart.options after construction: dies on the first hover --
    _check_chartjs_option_mutation(p, r)
    # -- Groovy numeric traps: every one of them reaches the user as the bare word "null" --
    _check_groovy_numeric_traps(p, r)
    # -- `?:` over a payload key: every Jackson node is falsy, so the FK lands NULL --
    _check_groovy_jsonnode_truth(p, r)
    # -- a pdfme template naming a font the renderer does not have: it prints in the default font, not as designed --
    _check_pdf_template_fonts(p, r)
    # -- a `--` comment in a saved query eats the paging wrapper the platform appends --
    _check_query_line_comments(p, r)
    _check_platform_required_fields(p, r)
    _check_query_reference_integrity(p, r)
    _check_single_slot_map_calls(p, r)
    _check_autofind_needs_count(p, r)
    _check_query_placeholder_shape(p, r)
    _check_chart_js_contract(p, r)
    _check_filter_form_layout(p, r)
    _check_dashboard_layout(p, r)
    _check_dashboard_composition(p, r)
    _check_chart_colour_by_index(p, r)
    _check_localized_fields(p, r)
    _check_column_format_keys(p, r)
    _check_date_format_tokens(p, r)
    _check_money_field_typing(p, r)
    _check_unclearable_optional_fields(p, r)
    _check_field_rule_refs(p, r)
    _check_table_fetch_rules(p, r)
    _check_event_mappings(p, r)
    _check_sources_queries_roles(p, r)
    _check_schedulers(p, r)
    _check_templates(p, r)
    _check_db_dump(p, r)
    _check_table_action_refs(p, r)
    # -- a Create/Edit/Delete action with no persist rule → the form submits and saves NOTHING --
    _check_action_persist(p, r)
    _check_settings_mirror(p, r)
    # -- project-global .js/.css: registry on the branch vs the bytes in tenant-files --
    _check_global_resources(p, r)
    # -- process.table: flat-name (blank button) + model-vs-editor-mirror drift --
    _check_process_table(p, r)
    # -- a process.table / settings bound to a workflow that isn't in the project → empty worklist / orphan config --
    _check_process_table_workflow_exists(p, r)
    # -- a process nothing can start, or a starter rule nothing ever invokes --
    _check_process_start_wiring(p, r)
    # -- a process-table column reading a value nothing ever puts there --
    _check_process_column_sources(p, r)
    _check_tree_config(p, r)
    # -- a flat findAll with untyped `OFFSET (:pageNumber * :rowsInPage)` that a RULE calls → unknown*unknown --
    _check_findall_paging_untyped(p, r)
    _check_form_linkage(p, r)
    _check_form_control_config(p, r)
    # -- an Html Field: value contract unreadable / binding of an undeclared type / a script that never writes it --
    _check_html_field(p, r)
    _check_html_field_sections(p, r)
    _check_workflow_refs(p, r)
    # -- a workflow serviceTask uses <alias>.data but the start form seeds no CRUD entity -> No CRUD data available --
    _check_workflow_start_seeds_entity(p, r)
    # -- service.workflow.start("<identifier>") pointing at a workflow that is missing or not deployed --
    _check_rule_workflow_start_targets(p, r)
    # -- service.security.users / .roleGroups: refused in a predicate, a member that does not exist, a rule that
    #    adds people left open to every signed-in user (or to anyone) --
    _check_rule_manages_people(p, r)
    # -- service.pubsub: refused in a predicate / validation rule, a member or an alias that cannot exist, an option
    #    no broker kind has --
    _check_rule_uses_pubsub(p, r)
    # -- service.messenger: the same - refused in a predicate / validation rule, a member or an alias that cannot exist,
    #    an all-named call of a member that takes positions, an option no messenger has --
    _check_rule_uses_messenger(p, r)
    # -- what the rule sandbox refuses before a rule runs: inject(), annotations, reflection, processes, files, the
    #    environment, changes to what every project shares (doc 08 "The rule sandbox") --
    _check_rule_sandbox(p, r)
    # -- a hand-built start document with the context/attrs at the ROOT -> dropped in silence, blank queues --
    _check_workflow_start_document_shape(p, r)
    # -- a rule using context.* while its own contextIdentifiers is empty -> null context, runtime throw --
    _check_rule_context_binding(p, r)
    # -- execution access (who may RUN a rule / CRUD / method): shape, unknown role groups, ignored settings --
    _check_execution_access_shape(p, cruds, r)
    # -- a rule an anonymous visitor triggers on a public page, not opened to anyone -> refused, the form dies --
    _check_public_page_rule_access(p, cruds, r)
    # -- a persist rule with no hasAnyRoleGroup -> anyone who reaches the form can write the entity --
    _check_persist_rule_role_guard(p, r)
    # -- a write action with no predicate -> the button shows for every role and fails only on Save --
    _check_write_action_predicate(p, r)
    # -- ANY action whose own rule refuses by role group, with no predicate -> offered to roles it refuses --
    _check_action_refused_by_role(p, r)
    # -- a grid column over a raw enum whose translated *Label twin already exists in localize --
    _check_enum_column_shows_code(p, cruds, r)
    # -- a rule showing the user a message in ONE language while the project is multilingual --
    _check_rule_strings_multilingual(p, r)
    # -- a locale.message(…) text glued from values -> never translated, every reader gets it as written --
    _check_rule_messages_are_literals(p, r)
    # -- a choices rule mapping options by 'id' -> raw uuids in the picker --
    _check_choices_display_is_identifying(p, r)
    # -- a mandatory document number nobody generates -> typed by hand, duplicated, drifting --
    _check_business_key_is_assigned(p, r)
    # -- a crud method nothing calls -> a step that was written and never wired --
    _check_crud_method_is_called(p, cruds, r)
    # -- a Groovy name read above its own `def` -> "Context 'x' not found", the action never runs --
    # -- `service.validation` does not exist: the collector is the binding `validation` --
    _check_rule_service_validation(p, r)
    _check_groovy_var_used_before_def(p, r)
    # -- a Groovy name never declared at all -> the same "Context 'x' not found", on the first run --
    _check_groovy_duplicate_def(p, r)
    # -- a create call that omits a NOT NULL column's parameter: throws on EVERY call --
    _check_crud_create_call_not_null(p, r)
    _check_groovy_undefined_identifier(p, r)
    # -- a user-task action with no complete rule -> the task closes and the record is untouched --
    _check_user_task_action_has_complete_rule(p, r)
    # -- a SCHEDULER's own rule forwarding the null `contextDataMap` binding -> an EMPTY process, silently --
    _check_scheduler_rule_context_data_map(p, r)
    # -- anything a PROCESS touches that still reaches its subject through the CRUD context -> blank / null --
    _check_process_context_binding(p, r)
    # -- a callActivity whose calledElement matches no workflow process key -> sub-process can't start --
    _check_callactivity_resolves(p, r)
    # -- how a token leaves a node: fallback contract, dead predicates, implicit forks, unlabelled branches --
    _check_gateway_branching(p, r)
    # -- a gateway predicate that answers from the case's stale context snapshot -> one branch is dead --
    _check_gateway_predicate_reads_record(p, r)
    _check_tabs(p, r)
    _check_chart_bindings(p, r)
    # -- a chart whose js selects an element its own html does not contain / a Plotly chart on a canvas --
    _check_chart_mount_matches_engine(p, r)
    # -- a chart replacement group that isn't a byte-for-byte substring of js → that series renders empty --
    _check_chart_group_in_js(p, r)
    # -- a chart whose js stops being valid JS once $$() is substituted → blank chart, console-only --
    _check_chart_js_parses(p, r)
    # -- a replacement type outside ReplacementType silently becomes String -> quoted numbers --
    _check_chart_replacement_type(p, r)
    # -- a Plotly tile with no explicit layout.height -> the card inherits Plotly's default --
    _check_plotly_explicit_height(p, r)
    _check_chart_query_embeds(p, r)
    _check_quicklinks(p, r)
    _check_localized_maps_distinct(p, r)
    # -- an entity localize jsonb keyed by the COLUMN name instead of the DTO field name --
    _check_localize_keys(p, r)
    # -- 35-semantic-types-and-field-decisions.md: the semantic type decides the control, data never lives in code --
    _check_text_control_on_coded_column(p, r)
    _check_localize_flat_shape(p, r)
    _check_rule_label_copy(p, r)
    _check_helper_closure_undefined(p, r)
    _check_rule_lists_business_codes(p, r)
    _check_case_variant_values(p, r)
    _check_dropdown_not_searchable(p, r)
    _check_server_clock_today(p, r)
    _check_literal_runs_into_word(p, r)
    _check_flag_as_text(p, r)
    _check_alias_case_split(p, r)
    # -- a VALIDATION_RULE no form wires: a check the team believes is running --
    _check_orphan_validation_rules(p, r)
    # -- a GROOVY method delegating to a rule the export never carried --
    _check_method_rule_delegates(p, r)
    _check_workflow_xml(p, r)
    _check_admin_base_pages(p, r)
    _check_action_forks(p, r)
    _check_chart_page_params(p, r)
    # -- the folder's entry point (CLAUDE.md + the project skill) is what `handoff emit` would write NOW --
    _check_entry_point_current(p, r)

    # -- content tree checks ------------------------------------------------
    locales = set(p.locales())
    root = p.root_content
    for node, _parent, _path in core.iter_nodes(root):
        pn = node.get("pluginName")
        props = node.get("properties", {}) or {}
        # settings-vs-model misuse
        from .content_cmds import MODEL_SLOT_PLUGINS, JAVASCRIPT_SLOT_PLUGINS
        if pn in MODEL_SLOT_PLUGINS and "settings" in props and "model" not in props:
            r.err("node %r (%s) stores config in properties.settings but this "
                  "plugin uses properties.model" % (node.get("name"), pn))
        # chart.js.plugin config must live in the Javascript slot; config
        # authored into settings/model renders empty.
        if pn in JAVASCRIPT_SLOT_PLUGINS and "Javascript" not in props:
            for wrong in ("settings", "model"):
                wp = props.get(wrong)
                if wp and wp.get("stringValue"):
                    r.err("node %r (%s) stores config in properties.%s but this "
                          "plugin uses properties.Javascript" % (node.get("name"), pn, wrong))
        # Plotly charts default paper_bgcolor/plot_bgcolor to WHITE -> a white box that
        # clashes with a dark theme ("white square reports" bug). A theme-aware chart sets
        # paper_bgcolor transparent (Chart.js is already transparent). See doc 14 §2.2.
        if pn in JAVASCRIPT_SLOT_PLUGINS and props.get("Javascript", {}).get("stringValue"):
            try:
                _cm = json.loads(props["Javascript"]["stringValue"])
            except json.JSONDecodeError:
                _cm = {}
            _js = (_cm.get("js") or "")
            # Comments must be stripped before the test: a chart that carries a COMMENTED-OUT
            # `// paper_bgcolor: "lavender",` still renders on Plotly's default WHITE canvas, but the
            # substring is present so the naive check passed it. A real project shipped 13 gauges that
            # way — white boxes on every dark skin, with this gate reporting clean.
            _js_live = re.sub(r"/\*.*?\*/", "", _js, flags=re.S)
            _js_live = re.sub(r"(?m)^\s*//.*$", "", _js_live)
            if "Plotly" in _js_live and "paper_bgcolor" not in _js_live:
                r.warn("chart %r uses Plotly but never sets paper_bgcolor -> renders a WHITE "
                       "box that clashes with dark themes. Set paper_bgcolor/plot_bgcolor "
                       "'rgba(0,0,0,0)' + theme font color (doc 14 §2.2)." % node.get("name"))
        if pn and pn.startswith("dynaform.form.") and pn.endswith(".plugin") \
                and "model" in props and "settings" not in props:
            r.warn("node %r (%s) stores config in properties.model but form "
                   "controls use properties.settings" % (node.get("name"), pn))
        # inner JSON well-formedness
        for slot in ("settings", "model"):
            prop = props.get(slot)
            if prop and prop.get("stringValue"):
                try:
                    json.loads(prop["stringValue"])
                except json.JSONDecodeError as exc:
                    r.err("node %r (%s): malformed inner JSON in properties.%s: %s"
                          % (node.get("name"), pn, slot, exc))
        # HTML Component Studio (properties.studioModel): must parse; each script's libNames must reference a
        # DECLARED library; vendored asset paths must be RELATIVE (so they survive import). See doc 24.
        sm = props.get("studioModel")
        if sm and sm.get("stringValue"):
            model = None
            try:
                model = json.loads(sm["stringValue"])
            except json.JSONDecodeError as exc:
                r.err("node %r (%s): malformed studioModel JSON: %s" % (node.get("name"), pn, exc))
            if isinstance(model, dict):
                lib_names = {l.get("name") for l in (model.get("libs") or []) if isinstance(l, dict)}
                for scr in (model.get("scripts") or []):
                    if not isinstance(scr, dict):
                        continue
                    for ln in (scr.get("libNames") or []):
                        if ln not in lib_names:
                            r.err("node %r studioModel: script %r references undeclared library %r (declared: %s)"
                                  % (node.get("name"), scr.get("name"), ln,
                                     ", ".join(sorted(n for n in lib_names if n)) or "none"))
                for lib in (model.get("libs") or []):
                    if not isinstance(lib, dict):
                        continue
                    for a in (lib.get("assets") or []):
                        if isinstance(a, dict) and a.get("path") and str(a["path"]).startswith("t/"):
                            r.warn("node %r studioModel: asset path %r is absolute; prefer a path RELATIVE to the "
                                   "tenant root (studio/<lib>/<file>) so it survives import (doc 24 §10)"
                                   % (node.get("name"), a["path"]))
                _check_theme_safe_css(model, node, r)
                if pn in _STUDIO_PLUGINS and len(locales) > 1:
                    _check_studio_texts_are_literals(model, node, r)
        if pn in ("html.plugin", "nct.html.plugin") and len(locales) > 1:
            _check_marks_need_the_runtime(node, pn, props, r)
        # An inline <style> in the html property is GLOBAL (it is not scoped like css.byTheme) and is the
        # usual home of a hardcoded light palette. See doc 24a §5.5.
        _html_prop = props.get("html")
        if pn in _STUDIO_PLUGINS and _html_prop and "<style" in (_html_prop.get("stringValue") or ""):
            r.warn("node %r: inline <style> in properties.html is GLOBAL — it leaks onto every other component "
                   "on the page and cannot be per-theme. Move it to studioModel.css.byTheme, which is scoped to "
                   "#dokie-plug-<id> (doc 24a §5.5)." % node.get("name"))
        if pn == "nct.image.plugin":
            _check_image_per_theme(node, props, r)
        # localizedNames in inner config (column/action captions) should cover
        # tenant locales. Page meta title/description are intentionally EN-only in
        # the baseline, so we do NOT check LOCALIZED_STRING property slots here.
        for slot in ("settings", "model"):
            prop = props.get(slot)
            if not (prop and prop.get("stringValue")):
                continue
            try:
                inner = json.loads(prop["stringValue"])
            except json.JSONDecodeError:
                continue
            _check_localized_names(inner, node, locales, r)

    # -- workflow user-task action locale coverage (bpmnContent embedded JSON) --
    _check_workflow_locales(rep, locales, r)

    # -- workflow element types must be task-type enum values (import-abort guard) --
    _check_workflow_element_types(rep, r)
    _check_user_action_payloads(rep, r)

    # -- form/filter plugins must anchor their fields at form.parsis/filter.parsis --
    _check_form_parsis_anchor(p, r)
    _check_list_field_subforms(p, r)
    _check_list_action_rules(p, r)
    # -- workflow graph reachability: every node must reach an end event --
    _check_workflow_reachability(rep, r)
    # -- workflow DI layout: no overlapping shapes / no edge through a node box --
    _check_workflow_diagram(rep, r)
    # -- homepage front door + business pages reachable from the nav --
    _check_homepage_and_nav(p, root, r)
    # -- form pages / form-group landings must sit under their table page --
    _check_form_page_structure(p, root, r)
    _check_form_group_page_aliases(p, root, r)
    # -- a form page must carry the baked page Layout (else the form renders empty at runtime) --
    _check_form_page_layout(p, root, r)
    # -- a form-group LANDING page that lost its landingplugin when cloned -> blank page, dead task actions --
    _check_form_group_landing_plugin(p, root, r)
    # -- a CRUD-table action's rule reading its own form's fields from the attrs (always null there) --
    _check_crud_action_form_values(p, root, r)
    # -- an html.plugin draws a child ONLY if its own html names it (cloning + regenerated ids = blank pages) --
    _check_html_plugin_refs(p, root, r)
    # -- a studio component's <include> graph: a cycle never renders; a dangling/extension-less src renders nothing --
    _check_html_includes(p, root, r)
    # -- a page renders its content from the child parsis named 'siteMapPageParsis'; lose it -> blank page --
    _check_page_top_parsis(p, root, r)
    # -- a STATIC page answers with its own text or file: the file must be in the bundle, byte-exact (doc 34) --
    _check_static_pages(p, root, r)
    # -- content nodes cloned from another export must have id=null (no foreign/duplicate ids) --
    _check_content_node_ids(root, r)
    # -- a content-node field that is a STRING where it is an object/array elsewhere aborts the import --
    _check_content_node_field_types(root, r)
    # -- at most ONE crud.table / crud.tree / process.table per page; no crud table on a dashboard --
    _check_one_table_plugin_per_page(root, r)
    # -- authored tabs render SMALL; BIG (or an omitted size) is a chunky bar nobody chose --
    _check_tab_size(root, r)

    # -- process.table.pluin typo must be preserved -------------------------
    plugin_names = {n.get("pluginName") for n, _p, _pt in core.iter_nodes(root)}
    if "process.table.plugin" in plugin_names:
        r.err("found 'process.table.plugin' — the real export uses the "
              "misspelling 'process.table.pluin'; do not 'fix' it")

    # -- report -------------------------------------------------------------
    core.out("validate: %s" % p.tenant.get("alias"))
    if not_carried:
        missing = [label for heading, label, importable, _c, _w in core.archive_parts(p)
                   if heading != "!" and not importable]
        core.out("  not in this archive: %s — nothing of them was checked, and a reference into one of them is "
                 "resolved by the import in the target project (`inspect` lists what the file carries)"
                 % core.listed_parts(missing))
    if r.warnings:
        core.out("\nWARNINGS (%d):" % len(r.warnings))
        for w in r.warnings:
            core.out("  ! %s" % w)
    if r.errors:
        core.out("\nERRORS (%d):" % len(r.errors))
        for e in r.errors:
            core.out("  x %s" % e)
        core.out("\nFAIL")
        return 1
    core.out("\nOK — no errors (%d warnings)" % len(r.warnings))
    return 0


def _check_api_exposures(p, r, keep):
    """`apiExposures` is the one rep-objects key whose PRESENCE is destructive (doc 32 §6): on import a list makes
    the target's API endpoints exactly that list and [] deletes every endpoint with its key bindings — bindings no
    archive brings back. An export of a live project writes it, so a base taken from one carries it into the build
    unless somebody removes it. Refused unless restoring exactly that list is the import's purpose."""
    state, _count, words = core.api_exposures_state(p.rep)
    if state in ("absent", "null"):
        return
    if state == "invalid":
        r.err("rep-objects.apiExposures is %s. Remove the key — `mrjun.py api-exposures drop` — a build "
              "leaves it out (doc 32 §6)." % words)
    elif keep:
        r.warn("rep-objects.apiExposures: %s — kept on purpose (--keep-api-exposures, doc 32 §6)." % words)
        for slug, method, path, rule in core.api_exposure_missing_rules(p.rep):
            r.warn("rep-objects.apiExposures: the rule call %s /%s%s runs rule %s, which rules[] does not have — "
                   "after import that operation answers 404 endpoint_not_found until it exists (doc 32 §3.15)."
                   % (method, slug, "/" + path if path else "", rule))
        for slug, code, key, words in core.api_exposure_ai_problems(p.rep):
            (r.warn if code == "unknown_key" else r.err)(
                "rep-objects.apiExposures: /%s aiDescriptions%s %s (doc 32 §3.16, §6)."
                % (slug, "[%s]" % key if key else "", words))
    else:
        r.err("rep-objects.apiExposures: %s. A build leaves this key out: it is what an export of a LIVE project "
              "writes, never something to author. Remove it — `mrjun.py api-exposures drop` — or, only when "
              "the import is MEANT to make the target's endpoints exactly this list, run validate with "
              "--keep-api-exposures (doc 32 §6)." % words)


def _prop_string_value(node, key):
    slot = (node.get("properties") or {}).get(key)
    return slot.get("stringValue") if isinstance(slot, dict) else None


def _hosts_form_or_landing_plugin(page):
    """True if this page's OWN layout hosts a form or form-group-landing plugin (do NOT
    descend into nested child siteMapPages). Such pages are reached via Create/Edit
    actions / the form-group landing, not the left-nav, so they are not 'unreachable'."""
    targets = {"dynaform.form.plugin", "dynaform.form.groups.landingplugin"}

    def walk(n, is_root):
        if not is_root and n.get("pluginName") == "siteMapPage":
            return False
        if n.get("pluginName") in targets:
            return True
        return any(walk(c, False) for c in (n.get("children") or []))

    return walk(page, True)


def _check_homepage_and_nav(p, root, r):
    """Gate the two 'front door' bugs:
      * root/Home has no Redirect and no landing content -> the bare URL is blank (WARN).
      * a Redirect that doesn't resolve to a real page -> dead front door (ERROR on root, WARN elsewhere).
      * a freshly-built business page not reachable from any populated nav or redirect -> invisible (WARN).
    See 21-homepage-and-redirect.md and 17-left-nav-quick-links.md.
    """
    from . import content_cmds, quicklink_cmds

    if p.is_stand_in(core.F_BRANCHES):
        return  # no pages in the archive: the import keeps the target's own front door and nav

    # (1) root/Home Redirect (the project front door). No Redirect is FINE when Home hosts its own
    # landing content (e.g. a dashboard) — only warn when Home is BOTH redirect-less AND empty.
    redirect = (_prop_string_value(root, "Redirect") or "").strip()
    if not redirect:
        home_plugins = _page_own_plugins(root)
        # `nct.html.plugin` counts: an authored HTML component IS landing content, and it is the
        # only shape a Home page can have in a project with no dynamic CRUDs to build a dashboard
        # from (a marketing front door, a static welcome screen). `html.plugin` deliberately does
        # NOT count — that one is the page LAYOUT, present on every page, so accepting it would make
        # this gate always pass.
        _LANDING = ("chart.js.plugin", "crud.table.plugin", "crud.tree.plugin", "process.table.pluin",
                    "process.table.plugin", "dynaform.form.plugin", "dynaform.form.groups.landingplugin",
                    "dynaform.filter.form.plugin", "nct.html.plugin")
        if not any(home_plugins.get(pn, 0) for pn in _LANDING):
            r.warn("root/Home page has no Redirect set AND no landing content — the bare project URL "
                   "renders an empty page. Point it at a landing page: `page set-redirect --to <alias>` "
                   "(e.g. a dashboard), or author real content into Home's parsis. Never ship an empty "
                   "Home (21-homepage-and-redirect.md).")
    elif content_cmds.resolve_alias_path(root, redirect.lstrip("/")) is None:
        r.err("root/Home Redirect %r does not resolve to a page (alias path, case-sensitive) — "
              "the front door would 404. Fix with `page set-redirect`." % redirect)

    # (2) any other page's Redirect must resolve too
    for node, _pp, _pt in core.iter_nodes(root):
        if node is root or node.get("pluginName") != "siteMapPage":
            continue
        rd = (_prop_string_value(node, "Redirect") or "").strip()
        if rd and content_cmds.resolve_alias_path(root, rd.lstrip("/")) is None:
            r.warn("page %r Redirect %r does not resolve to a child page (dead redirect)"
                   % (node.get("name"), rd))

    # (3) business pages must be reachable from a populated nav (or be a redirect target).
    # Read the SHARED "Nct left nav" common node (the one that actually renders — quick links are
    # written there) AND the per-page kicker nodes (older exports / fallback), so the reachability
    # check matches runtime instead of the dead per-page modelGroups.
    linked = set()
    nav_nodes = list(quicklink_cmds._iter_left_nav_nodes(root))
    shared_nav = quicklink_cmds._shared_left_nav_node(p)
    if shared_nav is not None:
        nav_nodes.append(shared_nav)

    # Every identifier the export actually carries — content nodes AND the virtual plugins, because a
    # link may legitimately point into a shared/virtual subtree.
    known_ids = set()
    for _n, _pp, _pt in core.iter_nodes(root):
        if _n.get("identifier"):
            known_ids.add(_n["identifier"])
    for _br in p.branches:
        for _vp in (_br.get("virtualPlugins") or []):
            _c = _vp.get("content")
            if isinstance(_c, dict):
                for _n, _pp, _pt in core.iter_nodes(_c):
                    if _n.get("identifier"):
                        known_ids.add(_n["identifier"])

    for nav in nav_nodes:
        # ⛔ Only the node that RENDERS may be judged for broken links. Every per-page
        # `site.kicker.plugin` carries a `modelGroups` copy that the platform never reads — each page
        # resolves its nav through the shared virtual plugin instead — so a stale link left in one of
        # those copies is dead data, not a broken menu. Reading them for REACHABILITY (above) is
        # generous and harmless; reporting them as dangling is 14 false errors on a baseline whose menu
        # is perfectly fine.
        renders = shared_nav is None or nav is shared_nav
        pm = quicklink_cmds._pages_model(quicklink_cmds._read_model_groups(nav))
        seen_labels = {}
        target_labels = {}

        def _collect(items):
            for it in items:
                info = quicklink_cmds._link_target(it)
                if info and info[0]:            # internal link -> target identifier
                    linked.add(info[1])
                    target = info[1]
                    label = it.get("name") or (it.get("linkModel") or {}).get("name") or "?"
                    # A link is rendered as a page lookup BY IDENTIFIER in the active branch. When the
                    # lookup misses, the URL builder has no page to build from and emits the site root,
                    # so the item still renders — with its icon and its label — and quietly goes to "/".
                    # Nothing errors, in the log or on screen; the user just never reaches the screen.
                    if renders and target and target not in known_ids:
                        r.err("left-nav link %r points at %s, which is not a node in this export — the "
                              "URL builder falls back to the site root, so the item renders normally and "
                              "goes to `/`. Re-point it at the page's identifier "
                              "(17-left-nav-quick-links.md)." % (label, target))
                    # Two links with the same label in one tree is the signature of a nav phase that
                    # APPENDS on a re-run: the stale copy keeps the identifiers of pages that were
                    # regenerated, so half the menu silently goes to the root.
                    # Count by TARGET, not by label: a link may carry no display name at all (the
                    # baseline ships several), and two entries pointing at the same page is the shape
                    # that matters — an appended stale copy points at the OLD identifier, so the pair
                    # shows up as one dangling error plus one live link with the same label.
                    if target:
                        seen_labels[target] = seen_labels.get(target, 0) + 1
                        target_labels.setdefault(target, label)
                _collect(it.get("children") or [])

        _collect(pm)
        root_identifier = root.get("identifier")
        for target, n in (sorted(seen_labels.items()) if renders else []):
            # The ROOT page is the one target many links legitimately share — a "Home" entry, the
            # logo, a group's landing row. Only a repeated BUSINESS page is the stale-copy signature.
            if n > 1 and target != root_identifier:
                r.warn("left-nav carries %d links pointing at the same page %s (%r) — a nav phase "
                       "that appends instead of replacing leaves a stale copy behind. "
                       "(17-left-nav-quick-links.md)" % (n, target, target_labels.get(target) or "?"))
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") != "siteMapPage":
            continue
        rd = (_prop_string_value(node, "Redirect") or "").strip()
        if rd:
            tgt = content_cmds.resolve_alias_path(root, rd.lstrip("/"))
            if tgt is not None:
                linked.add(tgt.get("identifier"))

    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") != "siteMapPage" or node is root:
            continue
        if node.get("id") is not None:
            continue  # built-in/system page (platform-managed nav)
        name = node.get("name") or ""
        alias = node.get("alias") or ""
        if name.startswith("Form:") or alias.startswith("form-"):
            continue  # form pages are reached via form flows, not the sidebar
        if _hosts_form_or_landing_plugin(node):
            continue  # form-group landing / form pages are reached via Create/Edit actions
        if staticpage_cmds.is_static(node):
            continue  # a static page is a FILE (robots.txt, app.js) fetched by URL, not a screen in the nav
        if node.get("identifier") not in linked:
            r.warn("business page %r (alias %s) is not referenced by any quick link or redirect "
                   "target — users can't reach it from the nav (17-left-nav-quick-links.md)."
                   % (name, alias))

    # (4) NAV LOCALIZATION: on a multi-locale project the GROUP HEADINGS must be localized too, not just the
    # links. A group node (a page node) renders its header from localizedMap.name; with none
    # — or the same string in every locale — the section header shows ONE language under all locales (the #1 loc
    # bug, doc 20). That is exactly what `quicklink add --group <name>` alone produces; the fix is --group-loc.
    locales = p.locales()
    if len(locales) > 1:
        seen_groups = set()

        seen_links = set()

        def _walk_groups(items):
            for it in items:
                if not isinstance(it, dict):
                    continue
                if it.get("linkModel"):
                    # ⛔ A LINK node is localized the same way its group heading is, and on the SAME
                    # object: the sidebar renders the item's localized "name" for the locale, i.e.
                    # `localizedMap["name"][locale]` on the ITEM, falling back to the raw `name`
                    # property. Localizing only the inner `linkModel.localizedMap` is invisible to
                    # that call — the item then shows its `name` (one language) under EVERY locale,
                    # which is what a three-locale project looks like when the whole sidebar renders
                    # in the first one. The platform's own baseline links carry the map on both.
                    lm = it.get("linkModel") or {}
                    lname = (it.get("name")
                             or ((lm.get("localizedMap") or {}).get("name") or {}).get(locales[0])
                             or lm.get("name") or "?")
                    key = (lname, lm.get("identifier") or lm.get("link"))
                    if key not in seen_links:
                        seen_links.add(key)
                        nm = (it.get("localizedMap") or {}).get("name") or {}
                        vals = [nm.get(l) for l in locales if nm.get(l)]
                        if len(vals) < len(locales):
                            inner = (lm.get("localizedMap") or {}).get("name") or {}
                            extra = ("  (the inner linkModel.localizedMap IS filled in — it is the "
                                     "wrong object; copy it onto the item)"
                                     if len([1 for l in locales if inner.get(l)]) == len(locales) else "")
                            r.err("left-nav link %r has no item-level localizedMap.name for all %d "
                                  "locales (got %s) — the sidebar reads localizedMap.name off the ITEM "
                                  "(a page node) and falls back to the raw `name`, "
                                  "so this link shows ONE language under every locale.%s "
                                  "(17-left-nav-quick-links.md / doc 20)"
                                  % (lname, len(locales), nm or "{}", extra))
                        elif len(set(vals)) == 1:
                            r.warn("left-nav link %r carries the SAME text %r in all %d locales — "
                                   "author one label per locale with `quicklink add --label-loc "
                                   "<locale>=<text>` (doc 20)." % (lname, vals[0], len(locales)))
                if not it.get("linkModel"):  # a GROUP node (link nodes have linkModel)
                    gname = it.get("name") or ""
                    if gname and gname not in ("Pages", "Site") and gname not in seen_groups:
                        seen_groups.add(gname)
                        nm = (it.get("localizedMap") or {}).get("name") or {}
                        vals = [nm.get(l) for l in locales if nm.get(l)]
                        if len(vals) < len(locales) or (len(vals) > 1 and len(set(vals)) == 1):
                            r.warn("left-nav group heading %r is NOT localized across all %d locales "
                                   "(localizedMap.name=%s) — the section header then shows one language under "
                                   "every locale (doc 20). Author it with `quicklink add --group-loc "
                                   "<locale>=<text>` (17-left-nav-quick-links.md)." % (gname, len(locales), nm))
                _walk_groups(it.get("children") or [])

        # ⛔ Only the SHARED `Nct left nav` node renders. The per-page `site.kicker.plugin`
        # copies carry a stale `modelGroups` that nobody reads (they point at the shared one via
        # `linkContentIdentifier`), and the pristine baseline's copies still hold a 3-link model
        # from years ago — checking them reports defects in dead data on EVERY project.
        for nav in ([shared_nav] if shared_nav is not None else nav_nodes):
            _walk_groups(quicklink_cmds._pages_model(quicklink_cmds._read_model_groups(nav)))


def _own_layout_hosts(page, plugin_name):
    """True if the page's OWN layout hosts plugin_name (not descending into child pages)."""
    def walk(n, is_root):
        if not is_root and n.get("pluginName") == "siteMapPage":
            return False
        if n.get("pluginName") == plugin_name:
            return True
        return any(walk(c, False) for c in (n.get("children") or []))
    return walk(page, True)


def _check_form_page_structure(p, root, r):
    """Enforce the Create-Default-Actions page structure (see 06-form-groups-and-mapping.md):
      * a form page (hosts dynaform.form.plugin) must NOT be a direct child of root/Home (WARN);
      * a formGroup.contentPageIdentifier must not point at the shared system 'Landing' page (WARN).
    """
    root_children = {id(c) for c in (root.get("children") or [])}
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") != "siteMapPage" or node is root:
            continue
        if id(node) in root_children and _own_layout_hosts(node, "dynaform.form.plugin"):
            r.warn("form page %r is a direct child of root/Home — move it under its CRUD table page "
                   "(page mv), next to its form-group landing (06-form-groups-and-mapping.md). "
                   "Never create form/landing pages with --parent root." % node.get("name"))

    # shared system 'Landing' page (under 'Form Groups') — the wrong contentPageIdentifier target
    shared_landing = None
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") == "siteMapPage" and node.get("name") == "Landing" \
                and node.get("alias") == "landing":
            shared_landing = node.get("identifier")
            break
    if shared_landing:
        for fg in p.rep.get("formGroups", []) or []:
            if fg.get("contentPageIdentifier") == shared_landing:
                r.warn("form group %r points contentPageIdentifier at the shared system 'Landing' page — "
                       "give it a per-CRUD landing under its table page and `formgroup set --content-page "
                       "<landing> --no-list` (an end-user Create/Edit routed to the system Landing is "
                       "access-denied). (06-form-groups-and-mapping.md)" % fg.get("name"))


def _check_form_group_page_aliases(p, root, r):
    """IMPORT-RUNS-BUT-LOOPS (ERROR). A form group's LANDING page (`contentPageIdentifier`) and each of its
    FORM pages (`forms[].contentIdentifier`) MUST carry a NON-EMPTY, UNIQUE **top-level** `alias`. The platform
    routes a page by the **top-level** `alias` JSON field, NOT `properties.alias.stringValue`;
    `page add` and the working reference (`doc/builder/erp/initial_erp.mrjun`) set the top-level one and leave
    `properties.alias.stringValue` null. A form/landing page with a MISSING top-level alias, or one that COLLIDES
    with another page (e.g. every per-group landing cloned from the system 'Landing' inherits `alias="landing"`),
    makes the platform build a broken/ambiguous page URL that re-resolves to the landing →
    the landing's redirect-to-form re-fires → **ERR_TOO_MANY_REDIRECTS** on `/landing?group=…`.
    `validate` cannot see this (it doesn't drive the URL router); this check makes it offline-catchable. (06)."""
    pages, alias_count = {}, {}
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") == "siteMapPage":
            pages[node.get("identifier")] = node
            a = node.get("alias")
            if a:
                alias_count[a] = alias_count.get(a, 0) + 1
    fg_pages = {}   # page identifier -> (role, owner-name)
    for fg in p.rep.get("formGroups", []) or []:
        lp = fg.get("contentPageIdentifier")
        if lp:
            fg_pages.setdefault(lp, ("landing", fg.get("name")))
    for form in p.rep.get("forms", []) or []:
        cp = form.get("contentIdentifier")
        if cp:
            fg_pages.setdefault(cp, ("form", form.get("name")))
    for pid, (role, owner) in fg_pages.items():
        node = pages.get(pid)
        if node is None:
            continue  # page not in branches — flagged by other checks
        a = node.get("alias")
        if not a:
            r.err("form-group %s page %r (%r) has NO top-level `alias` — the platform routes by "
                  "the top-level `alias` (NOT properties.alias.stringValue); missing → a broken URL "
                  "that re-resolves to the landing → 302 redirect-loop (ERR_TOO_MANY_REDIRECTS) on "
                  "/landing?group=. Set a UNIQUE top-level alias. (06-form-groups-and-mapping.md)"
                  % (role, node.get("name"), owner))
        elif alias_count.get(a, 0) > 1:
            r.err("form-group %s page %r (%r) top-level alias %r COLLIDES with %d other page(s) — page aliases "
                  "must be UNIQUE for routing (a per-group landing cloned from the system 'Landing' inherits "
                  "alias='landing'; override it). A colliding form/landing alias → 302 redirect-loop. "
                  "(06-form-groups-and-mapping.md)" % (role, node.get("name"), owner, a, alias_count[a] - 1))


def _find_desc(node, plugin_name, name=None, _root=True):
    """DFS within a page's OWN layout (does not descend into nested child siteMapPages) for a node with
    pluginName==plugin_name (and, if given, name==name). Returns the node or None."""
    if not isinstance(node, dict):
        return None
    if not _root and node.get("pluginName") == "siteMapPage":
        return None
    if node.get("pluginName") == plugin_name and (name is None or node.get("name") == name):
        return node
    for c in node.get("children") or []:
        found = _find_desc(c, plugin_name, name, False)
        if found is not None:
            return found
    return None


def _check_form_page_layout(p, root, r):
    """RENDERS-EMPTY (ERROR). A form page (`forms[].contentIdentifier`) must carry the baked page LAYOUT — an
    `html.plugin` named `'Layout'` (site.header / logo / breadcrumb / left-nav / a content `nct.parsis.plugin` /
    footer / right-kicker) — with the `dynaform.form.plugin` INSIDE that content parsis, exactly like every page
    produced by `page add`. A **bare**
    `siteMapPage → parsis.plugin → dynaform.form.plugin` (no Layout chrome) IMPORTS FINE but renders at runtime as
    "not a form layout / no form plugin / no fields" — only a live open reveals it, so `validate` must catch it
    offline. Fix: build the form page by CLONING a page that already has the Layout (e.g. the shared Landing) and
    injecting the form plugin into its content parsis, or use `page add` + `node add`. (06 ⭐ canonical recipe)."""
    pages = {}
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") == "siteMapPage":
            pages[node.get("identifier")] = node
    for form in p.rep.get("forms", []) or []:
        node = pages.get(form.get("contentIdentifier"))
        if node is None:
            continue  # missing page flagged elsewhere
        fp = _find_desc(node, "dynaform.form.plugin")
        if fp is None:
            continue  # no form plugin — absent/other-page problem, not this check
        layout = _find_desc(node, "html.plugin", "Layout")
        if layout is None or _find_desc(layout, "dynaform.form.plugin") is None:
            r.err("form %r page %r has its dynaform.form.plugin OUTSIDE the page Layout — a bare "
                  "parsis.plugin->dynaform.form.plugin with no `html.plugin 'Layout'` chrome IMPORTS FINE but "
                  "renders at runtime as 'not a form layout / no form plugin / no fields' (only a live open shows "
                  "it). The form plugin must sit at siteMapPage->parsis.plugin->html.plugin 'Layout'->"
                  "nct.parsis.plugin 'parsis'->dynaform.form.plugin, exactly like `page add` output. "
                  "Clone a page WITH the Layout and inject the form plugin into its content parsis. "
                  "(06-form-groups-and-mapping.md - canonical recipe)" % (form.get("name"), node.get("alias")))


_WF_START_CALL_RE = re.compile(r"service\.workflow\.start\s*\(\s*[^,]+,\s*([A-Za-z_]\w*)\s*[,)]")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# `doc['key'] = ...` / `doc["key"] = ...` — a key assigned at the ROOT of the start document
_DOC_ROOT_PUT_RE = r"""(?<![\w.]){var}\s*\[\s*['"]([^'"]+)['"]\s*\]\s*="""
# the only keys the platform reads at the document root (16-groovy-service-api.md 2.12)
_WF_DOC_ROOT_KEYS = {"contextDataMap", "attrs", "localeKey"}


def _check_rule_context_binding(p, r):
    """RUNTIME-THROW (ERROR). A rule whose script touches `context.data` or `context.<ctxAlias>` needs that
    context listed in its own **`contextIdentifiers`**. With an EMPTY `contextIdentifiers` the executor
    attaches no context, `context.data` is null, and the first `getAttr` / `setAttr` throws - which surfaces
    far from the rule: a serviceTask aborts mid-process, an `onBeforeUserTaskStart` bind rule takes the task
    form down with an HTTP 500, a PREDICATE on a gateway answers by exception and the token stops.

    It is easy to produce: `rule add` defaults `contextIdentifiers` to empty, and a rule that only ever ran
    through a form (where the document arrives with the request) looks fine until the same rule is wired to a
    workflow element, which passes no document of its own.

    Fix: `rule add --context <ctxIdentifier>` at authoring time, or set `contextIdentifiers` on the existing
    rule. (08-groovy-rules-and-context.md, 16-groovy-service-api.md)"""
    rep = p.rep
    ctx_aliases = {c.get("alias") for c in (rep.get("contexts") or []) if c.get("alias")}
    for rule in rep.get("rules", []) or []:
        if rule.get("contextIdentifiers"):
            continue
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if not src:
            continue
        used = []
        if re.search(r"(?<![\w.])context\.data\b", src):
            used.append("context.data")
        for a in sorted(ctx_aliases):
            if re.search(r"(?<![\w.])context\.%s\b" % re.escape(a), src):
                used.append("context.%s" % a)
        if not used:
            continue
        r.err("rule %r (%s) reads %s but its `contextIdentifiers` is EMPTY - no context is attached at "
              "runtime, so `context.data` is null and the first getAttr/setAttr THROWS. That surfaces far "
              "from here: a serviceTask aborts mid-process, an onBeforeUserTaskStart bind rule takes the "
              "task form down with a 500, a gateway PREDICATE answers by exception and the token stops. "
              "Attach the context: `rule add --context <ctxIdentifier>` (or set contextIdentifiers on the "
              "existing rule). (08-groovy-rules-and-context.md)"
              % (rule.get("name"), rule.get("ruleType"), ", ".join(used[:3])))


def _check_workflow_start_document_shape(p, r):
    """SILENT-DATA-LOSS (ERROR). The document handed to `service.workflow.start(wfId, doc[, opts])` has
    EXACTLY three root keys: **`contextDataMap`** (keyed by context IDENTIFIER -> `crudDataMap` / `attrs`),
    **`attrs`** (the process's GLOBAL attributes) and the optional **`localeKey`**. Unknown root keys are
    **DROPPED, not rejected** - the start succeeds and returns a process identifier either way.

    So a hand-built document of the shape

        def doc = [:]
        doc['<contextIdentifier>'] = ['crudDataMap': [alias: ['value': row]]]   // WRONG: context at the root
        doc['subjectId'] = id                                                   // WRONG: attr at the root
        doc['orderNo']   = row.orderNo

    starts a process that carries **neither the CRUD rows nor the GLOBAL attributes**. The damage is entirely
    downstream and never points back here:

      * the worklist (`process.table.pluin`) renders its `scope: GLOBAL` columns EMPTY - a queue of blank rows;
      * a task form's `GLOBAL`-scope controls come up empty;
      * an `onBeforeUserTaskStart` bind rule finds no `subjectId`, cannot resolve the record, and the task
        form fails to open (HTTP 500) - so the user task is UNCOMPLETABLE;
      * a serviceTask reading `context.<ctx>.<alias>.data` gets an empty envelope and computes nulls.

    The correct shape nests both levels:

        def doc = [
            'contextDataMap': [ (ctxId): ['crudDataMap': [alias: ['value': row]], 'attrs': [:]] ],
            'attrs': [ subjectId: id, orderNo: (row.orderNo ?: '') as String ]
        ]

    This flags a root assignment whose key is a context identifier (a UUID, or one that matches a context in
    the export) or any key outside the three the platform reads.
    (16-groovy-service-api.md 2.12, 27-event-driven-process-start.md)"""
    rep = p.rep
    ctx_ids = {c.get("identifier") for c in (rep.get("contexts") or []) if c.get("identifier")}
    for rule in rep.get("rules", []) or []:
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if "service.workflow.start" not in src:
            continue
        for m in _WF_START_CALL_RE.finditer(src):
            var = m.group(1)
            put_re = re.compile(_DOC_ROOT_PUT_RE.format(var=re.escape(var)))
            bad_ctx, bad_attr = [], []
            for km in put_re.finditer(src):
                key = km.group(1)
                if key in _WF_DOC_ROOT_KEYS:
                    continue
                if key in ctx_ids or _UUID_RE.match(key):
                    bad_ctx.append(key)
                else:
                    bad_attr.append(key)
            if not bad_ctx and not bad_attr:
                continue
            bits = []
            if bad_ctx:
                bits.append("the CONTEXT entry %s is assigned at the document ROOT instead of under "
                            "`contextDataMap`" % ", ".join(repr(k) for k in sorted(set(bad_ctx))))
            if bad_attr:
                shown = sorted(set(bad_attr))
                bits.append("the GLOBAL attribute(s) %s%s sit at the document ROOT instead of under `attrs`"
                            % (", ".join(repr(k) for k in shown[:6]),
                               " (+%d more)" % (len(shown) - 6) if len(shown) > 6 else ""))
            r.err("rule %r builds the `service.workflow.start` document %r with the WRONG SHAPE - %s. Unknown "
                  "root keys are DROPPED IN SILENCE: the start still returns a process id, but the case "
                  "carries no CRUD rows and no GLOBAL attrs, so the worklist columns render EMPTY, a task "
                  "form's GLOBAL controls come up blank, and an onBeforeUserTaskStart bind rule cannot "
                  "resolve the subject - the user task then fails to open (500) and is UNCOMPLETABLE. "
                  "Nest it: doc = ['contextDataMap': [ (ctxId): ['crudDataMap': [<alias>: ['value': row]], "
                  "'attrs': [:]] ], 'attrs': [<the worklist's GLOBAL columns>]]. "
                  "(16-groovy-service-api.md 2.12, 27-event-driven-process-start.md)"
                  % (rule.get("name"), var, "; ".join(bits)))


def _check_form_group_landing_plugin(p, root, r):
    """RENDERS-EMPTY (ERROR). A form group's LANDING page (`contentPageIdentifier`) must carry the
    **`dynaform.form.groups.landingplugin`** inside its content parsis. That plugin IS the landing: it resolves
    `?group=` and, when opened with navigation params (`settingsName`+`actionId`, `crudId`/`processIdentifier`),
    evaluates `predicateFormMapping` and FORWARDS to the matching form page. Without it the URL resolves, the
    page returns 200, the chrome (header / breadcrumb / left-nav / footer) draws — and the content area is
    BLANK, so every crud-table Edit action and every **workflow user task** that routes through this landing
    is a dead end.

    This is the clone trap: the plugin sits in the shared system `Landing` page's parsis and is resolved BY
    NAME, so a per-entity landing built by cloning that page keeps the Layout and loses the slot child. Every
    offline gate stays green (the page exists, has a Layout, has a unique alias, has a parsis) and only opening
    the page — or pressing a workflow task action — reveals it.

    Fix: `node add --parent <landing page's content parsis> --plugin dynaform.form.groups.landingplugin`.
    The plugin needs no properties; it reads everything from the query string.
    (06-form-groups-and-mapping.md, 14a-plugin-config-reference.md)"""
    pages = {}
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") == "siteMapPage":
            pages[node.get("identifier")] = node
    for fg in p.rep.get("formGroups", []) or []:
        node = pages.get(fg.get("contentPageIdentifier"))
        if node is None:
            continue  # missing page flagged elsewhere
        if _find_desc(node, "dynaform.form.groups.landingplugin") is None:
            r.err("form-group %r landing page %r carries NO `dynaform.form.groups.landingplugin` — the page "
                  "returns 200 and draws its chrome, but the content area is BLANK and every Edit action / "
                  "workflow user task routed through it is a DEAD END. The plugin is resolved by name inside "
                  "the shared 'Landing' page's parsis, so a cloned landing silently loses it while every "
                  "offline gate stays green. Add it to the page's content parsis: `node add --parent "
                  "<parsis> --plugin dynaform.form.groups.landingplugin` (it needs no properties). "
                  "(06-form-groups-and-mapping.md)" % (fg.get("name"), node.get("alias")))


def _check_static_pages(p, root, r):
    """A STATIC page (`pageType: "static"`) answers at its alias with exactly its `staticBody` text or its
    uploaded file. Everything here either makes the platform answer 404 / the wrong bytes, or is unreachable:

    - ERROR the file path is not `static-pages/<sha256>/<name>`, is not in `tenant-files/`, or its bytes do not
      hash to the sha256 in the path — the platform checks that hash before it serves a byte (file storage
      answers a missing path with a placeholder image, so the hash is the only proof);
    - ERROR the site root is static, a page sits UNDER a static page, the content type is not type/subtype,
      the text is over 1 MiB (store it as a file);
    - WARN a static page with plugin children (never rendered), an unknown `pageType` value (read as a normal
      page), a NORMAL page whose alias ends like a file (`.js`, `.png`, `.txt`, `.html`…) — that URL is handed to
      the platform's static-file handler and the page never opens. (34-static-pages.md)"""
    sp = staticpage_cmds
    for node, parent, _pt in core.iter_nodes(root):
        if node.get("pluginName") != "siteMapPage":
            continue
        where = "page %s (%s)" % (node.get("name"), node.get("alias") or "-")
        raw_type = sp.string_prop(node, sp.PAGE_TYPE)
        if raw_type not in (None, "", sp.TYPE_STATIC, sp.TYPE_DOKIE):
            r.warn("%s: pageType %r is neither 'static' nor 'dokie' — it is read as a normal page. (34)"
                   % (where, raw_type))
        if parent is not None and sp.is_static(parent):
            r.err("%s sits under the static page %r — a static page holds no pages. (34)"
                  % (where, parent.get("name")))
        if not sp.is_static(node):
            if node is not root and sp.looks_like_file_url(node.get("alias")):
                r.warn("%s: a normal page whose alias ends like a file — that URL goes to the platform's "
                       "static-file handler and this page never opens. Make it a static page "
                       "(`page set-static`) or drop the extension. (34)" % where)
            continue
        if node is root:
            r.err("%s: the site root cannot be a static page. (34)" % where)
        if any(c.get("pluginName") != "siteMapPage" for c in (node.get("children") or [])):
            r.warn("%s: a static page has plugin children; they are never rendered — remove them. (34)" % where)
        ct = (sp.string_prop(node, sp.CONTENT_TYPE) or "").strip()
        if ct and not sp.CONTENT_TYPE_RE.match(ct):
            r.err("%s: staticContentType %r is not type/subtype (e.g. text/javascript). (34)" % (where, ct))
        body = sp.string_prop(node, sp.BODY) or ""
        if len(body.encode("utf-8")) > sp.MAX_INLINE_TEXT_BYTES:
            r.err("%s: staticBody is %d bytes; the limit is %d — store it as a file (`page set-static --file`). (34)"
                  % (where, len(body.encode("utf-8")), sp.MAX_INLINE_TEXT_BYTES))
        path = sp.string_prop(node, sp.FILE_PATH)
        if not path:
            continue
        m = sp.FILE_PATH_RE.match(path)
        if not m:
            r.err("%s: staticFilePath %r must be static-pages/<sha256>/<name>, relative to the tenant root "
                  "(never t/<id>/…) — the platform refuses anything else. (34)" % (where, path))
            continue
        disk = os.path.join(p.root, "tenant-files", *path.split("/"))
        if not os.path.isfile(disk):
            r.err("%s: its file tenant-files/%s is not in this bundle — the page would answer 404. (34)"
                  % (where, path))
            continue
        with open(disk, "rb") as fh:
            data = fh.read()
        if hashlib.sha256(data).hexdigest() != m.group(1):
            r.err("%s: tenant-files/%s does not hash to the sha256 in its path — the platform refuses it and "
                  "answers 404. Re-add the file with `page set-static --file`. (34)" % (where, path))
        size = sp.long_prop(node, sp.FILE_SIZE)
        if size not in (None, len(data)):
            r.warn("%s: staticFileSize %s but the file is %d bytes. (34)" % (where, size, len(data)))


def _check_page_top_parsis(p, root, r):
    """RENDERS-EMPTY (ERROR). A `siteMapPage` renders its content from the child `parsis.plugin` whose
    `identifier` is the well-known symbolic **`siteMapPageParsis`**. That id is NOT referenced from any html —
    the page resolves it by name — so it survives no "preserve what the html references" rule and is trivially
    lost when a page is built by CLONING another page and regenerating identifiers.

    When it is missing the platform does not fail: it CREATES A FRESH EMPTY `siteMapPageParsis` and renders that,
    while the cloned subtree (Layout, charts, tables, the lot) sits beside it as an unrendered orphan. The page is
    blank, the export is complete, `validate`/`coverage`/`crud verify` are all green, and the live DOM shows TWO
    `parsis.plugin` children. Diagnosed exactly that way on a large real build, where the majority of pages rendered blank.

    Fix: add `siteMapPageParsis` to the identifiers your clone helper preserves, alongside `left-nav` / `parsis` /
    `form.parsis` / `filter.parsis` / `Layout`. (01-content-model-and-pages.md ⛔⛔ THE CLONING TRAP)"""
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") != "siteMapPage":
            continue
        tops = [c for c in (node.get("children") or []) if c.get("pluginName") == "parsis.plugin"]
        where = "%s (%s)" % (node.get("name"), node.get("alias") or "-")
        if not tops:
            continue  # a page with no top parsis at all is flagged by the layout checks
        if not any(c.get("identifier") == "siteMapPageParsis" for c in tops):
            r.err("page %s: its top-level parsis.plugin does not carry the symbolic identifier "
                  "'siteMapPageParsis' (got %s) — the page resolves its content container BY THAT NAME, so the "
                  "platform will create a fresh EMPTY one, render it, and leave your whole subtree as an "
                  "unrendered orphan: the page shows BLANK. Preserve 'siteMapPageParsis' when cloning a page. "
                  "(01-content-model-and-pages.md)"
                  % (where, ", ".join(repr(c.get("identifier")) for c in tops)))
        elif len(tops) > 1:
            r.err("page %s: %d top-level parsis.plugin children — exactly one ('siteMapPageParsis') is rendered, "
                  "the others are unrendered orphans. (01-content-model-and-pages.md)" % (where, len(tops)))


# A studio component: a node whose `html` + `studioModel` are rendered by the studio runtime — the html block, the
# Html Field (a form control that renders the very same component on its own node) and an Html Field's settings
# section (a child of the field, drawn in its settings drawer) — doc 24e. Every studio check (include graph, scoped
# CSS, rule references) applies to all three.
_HTML_FIELD = "dynaform.form.html.field.plugin"
_HTML_FIELD_SECTION = "dynaform.html.field.section.plugin"
_STUDIO_PLUGINS = ("nct.html.plugin", _HTML_FIELD, _HTML_FIELD_SECTION)
# Every node that draws its children from `<plugin id=…>` tags in its `html`.
_HTML_PLUGINS = ("html.plugin",) + _STUDIO_PLUGINS
_PLUGIN_TAG = re.compile(r"<plugin[^>]*>")
_PLUGIN_ID = re.compile(r'\bid="([^"]+)"')
_PLUGIN_NAME = re.compile(r'\bname="([^"]+)"')


def _html_of(node):
    return ((node.get("properties") or {}).get("html") or {}).get("stringValue") or ""


def _check_html_plugin_refs(p, root, r):
    """RENDERS-EMPTY (ERROR + WARN). An `html.plugin`/`nct.html.plugin` renders ONLY its own `html` string; a
    child node is drawn if and only if that html contains `<plugin ... id="<child.identifier>">`. A child with no
    matching tag stays in the tree, imports fine and validates fine — and is NEVER DRAWN.

    The killer case is CLONING a laid-out page and regenerating identifiers: the baked page Layout addresses SEVEN
    children by name (`header`, `logo-plugin`, `breadcrumb`, `left-nav`, `parsis`, `footer`, `right-kicker`), so a
    clone helper that preserves only a hardcoded subset silently strips the chrome off EVERY page. That shipped
    once on a large real build — every page lost its chrome — with `validate` 0-errors, `coverage` 150/150 and
    `crud verify` 149-OK all green, because nothing offline looked at the html↔children relationship.

    ERROR is raised only on the unambiguous signature — a dangling `<plugin id>` PAIRED with an unreferenced child
    of the SAME pluginName under the same html node, i.e. that child's identifier was regenerated. That signature
    never occurs in a healthy project and appears in the thousands once the bug is present. Everything else is a
    WARN, because an html may legitimately reference an optional plugin that is absent, or hold a child it
    deliberately does not draw (the base palette's `Card layout` p2/p3/p4).

    Fix when cloning: never regenerate an identifier that any html in the subtree references — collect
    `<plugin ... id="X">` across the subtree and preserve those, instead of a hardcoded symbolic list.
    (01-content-model-and-pages.md "How an html.plugin renders its children")"""
    for page, _pp, _pt in core.iter_nodes(root):
        if page.get("pluginName") != "siteMapPage":
            continue
        where = "%s (%s)" % (page.get("name"), page.get("alias") or "-")
        for node, _a, _b in core.iter_nodes(page):
            if node.get("pluginName") not in _HTML_PLUGINS:
                continue
            html = _html_of(node)
            if "<plugin" not in html:
                continue
            wanted = {}
            for tag in _PLUGIN_TAG.findall(html):
                m = _PLUGIN_ID.search(tag)
                if m:
                    nm = _PLUGIN_NAME.search(tag)
                    wanted[m.group(1)] = nm.group(1) if nm else None
            # An Html Field's settings sections are its children too, drawn in its settings drawer — never by its html.
            kids = {c.get("identifier"): c.get("pluginName") for c in (node.get("children") or [])
                    if not (node.get("pluginName") == _HTML_FIELD and c.get("pluginName") == _HTML_FIELD_SECTION)}
            unref = [(k, v) for k, v in kids.items() if k not in wanted]
            for rid, rplugin in wanted.items():
                if rid in kids:
                    # TYPE-SWAP TRAP: the tag binds BOTH id and type. On a mismatch mrjun rewrites the node
                    # to the html's type and CLEARS its properties (the child's properties
                    # are cleared and its plugin name reset), so the authored
                    # settings blob is gone at render time — a form control silently loses its
                    # scope/crudAlias/fieldExpression and stops mapping to anything.
                    if rplugin and kids[rid] != rplugin:
                        r.err("page %s: html %r addresses <plugin id=%r name=%r> but that child node is a %r — "
                              "on a type mismatch mrjun CLEARS the node's properties and reverts it to the "
                              "html's plugin, so the authored settings are lost and the control renders as the "
                              "OLD type bound to nothing. Changing a node's pluginName is a TWO-PLACE edit: the "
                              "node AND the `name=` of its <plugin> tag. (01-content-model-and-pages.md)"
                              % (where, node.get("name"), rid, rplugin, kids[rid]))
                    continue
                regenerated = any(rplugin is None or up == rplugin for _uk, up in unref)
                if regenerated:
                    r.err("page %s: html %r references <plugin id=%r name=%r> which is NOT one of its children, "
                          "while it HAS an unreferenced child of that same plugin type — the child's identifier "
                          "was regenerated, so this slot RENDERS BLANK. When cloning a laid-out subtree, preserve "
                          "every identifier any html in it references (Layout addresses header/logo-plugin/"
                          "breadcrumb/left-nav/parsis/footer/right-kicker by name). "
                          "(01-content-model-and-pages.md)" % (where, node.get("name"), rid, rplugin))
                else:
                    r.warn("page %s: html %r references <plugin id=%r> that is not a child and exists nowhere in "
                           "the page — that slot renders nothing (ok if the plugin is deliberately optional). "
                           "(01-content-model-and-pages.md)" % (where, node.get("name"), rid))
            for k, kp in unref:
                r.warn("page %s: child %s %r of html %r is never referenced by that html — it is INVISIBLE at "
                       "runtime (still in the tree, still exported, never drawn). "
                       "(01-content-model-and-pages.md)" % (where, kp, k, node.get("name")))


# --- <include> graph of an HTML Component Studio component ---------------------------------------------
# An `<include src="…">` in a document is a SERVER-SIDE textual substitution before parsing, so whatever it
# brings in (a `<plugin>` tag included) behaves exactly as if it had been typed into the including document.
# The name space it addresses is the component's OWN: 'main' = properties.html.stringValue, plus every
# studioModel.docs[] and studioModel.scripts[] entry. There is no cross-component include and no directory
# traversal — a slash inside a name is a display folder in the studio navigator, not a path.
_INCLUDE_TAG = re.compile(r"<include\b[^>]*>", re.I)
_INCLUDE_SRC = re.compile(r"""(?<![\w-])src\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.I)
# Regions where an include is NOT expanded. (It IS expanded inside <pre>, so an include shown as example
# text there must be written escaped — this scanner deliberately matches that behaviour.)
_INCLUDE_SKIP = re.compile(r"<!--.*?-->"
                           r"|<script\b[^>]*>.*?</script\s*>"
                           r"|<style\b[^>]*>.*?</style\s*>"
                           r"|<textarea\b[^>]*>.*?</textarea\s*>", re.I | re.S)
# Runtime document inclusion from author JS. Only a STRING LITERAL is visible offline; a computed argument
# is left alone rather than guessed.
_CTX_INCLUDE = re.compile(r"\b(?:ctx|this)\s*\.\s*include\s*\(\s*(?:'([^']*)'|\"([^\"]*)\")")
_DOC_EXT = (".html", ".htm")
_SCRIPT_EXT = (".js", ".mjs")


def _include_srcs(doc_html):
    """Every `<include src=…>` of one document, in source order, skipping the regions the platform skips.
    All three spellings parse (`<include …/>`, `<include …></include>`, `<include …>`), quoted or not."""
    body = _INCLUDE_SKIP.sub(" ", doc_html or "")
    out = []
    for tag in _INCLUDE_TAG.findall(body):
        m = _INCLUDE_SRC.search(tag)
        if not m:
            continue
        src = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if m.group(3):
            src = src.rstrip("/")          # unquoted value of a self-closing tag: <include src=x.html/>
        if src:
            out.append(src)
    return out


def _ctx_include_srcs(code):
    """Every LITERAL `ctx.include('…')` / `this.include('…')` of one script, in source order."""
    live = re.sub(r"/\*.*?\*/", "", code or "", flags=re.S)
    live = re.sub(r"(?m)^\s*//.*$", "", live)
    return [(a or b).strip() for a, b in _CTX_INCLUDE.findall(live) if (a or b).strip()]


def _resolve_include(src, docs, scripts):
    """THE resolution rule, used identically for a static tag and for a runtime `ctx.include`:
      1. a leading './' is dropped; no known extension ⇒ unresolved (kind None);
      2. the extension picks the name space (.html/.htm ⇒ document, .js/.mjs ⇒ script) and the REST of the
         src is matched against the STORED names verbatim (stored names are extension-less: `detail`,
         `charts/bar`, `boot`);
      3. if that misses, the WHOLE src is matched verbatim too — so a document an author literally named
         `report.html` is reachable as src="report.html".
    Returns (kind, name); name is None when the name space is known but nothing matches."""
    s = (src or "").strip()
    if s.startswith("./"):
        s = s[2:]
    low = s.lower()
    if low.endswith(_DOC_EXT):
        kind, names = "doc", docs
    elif low.endswith(_SCRIPT_EXT):
        kind, names = "script", scripts
    else:
        return None, None
    bare = s[:s.rfind(".")]
    if bare in names:
        return kind, bare
    if s in names:
        return kind, s
    return kind, None


def _include_label(name, kind):
    """Stored names are extension-less; the studio DISPLAYS them with one. Report the displayed spelling."""
    low = (name or "").lower()
    if kind == "doc":
        return name if low.endswith(_DOC_EXT) else name + ".html"
    return name if low.endswith(_SCRIPT_EXT) else name + ".js"


def _page_own_html_studio_nodes(page):
    """Studio component nodes (`_STUDIO_PLUGINS`) in a page's OWN content (never descending into a child
    siteMapPage, so a component is diagnosed once, under the page that really owns it)."""
    out = []

    def w(n):
        for c in n.get("children") or []:
            if c.get("pluginName") == "siteMapPage":
                continue
            if c.get("pluginName") in _STUDIO_PLUGINS:
                out.append(c)
            w(c)

    w(page)
    return out


def _check_html_includes(p, root, r):
    """INCLUDE GRAPH (ERROR + WARN). An `nct.html.plugin` that carries a `studioModel` may split its markup
    across documents and pull them together with `<include src="…">` (server-side textual substitution, so an
    included `<plugin>` tag becomes a real live child) and declare which author scripts belong to the
    component with `<include src="…​.js">`. Nothing about that graph is checked at import time: a cycle, a
    dangling target or an extension-less `src` imports perfectly cleanly and only shows up when the page is
    opened, as an HTML comment where the content should be — a component that renders as a hole, with every
    other offline gate green.

    ERROR on a CYCLE only. It is the one failure the expansion cannot degrade around, it is invisible in any
    single document (each file looks fine on its own), and the studio itself refuses to save it — so a cyclic
    graph can only ever arrive from hand-authored JSON, i.e. exactly what this toolkit writes.

    WARN on the recoverable three, each of which renders that document's include as an HTML comment and
    otherwise leaves the page alive: a target that exists in neither name space; an `src` with no extension
    (documents and scripts are two INDEPENDENT name spaces — one component may hold a document `report` and a
    script `report` — so an extension-less `src` cannot choose and is refused rather than guessed); and an
    enabled script that no reachable document includes while the component DOES use script includes (as soon
    as one reachable document declares one, only included scripts run, so that script silently never
    executes; with no script include anywhere the legacy rule holds — every enabled script runs — and nothing
    is warned). What declares include mode is the EXTENSION, not the resolution: an `src` ending `.js`/`.mjs`
    switches the component over even when it names no script of this component — so a single misspelt script
    include in a component whose whole manifest is that one tag leaves the program EMPTY (markup renders, no
    JS runs, console clean), which gets its own WARN.

    Reachability is a fixpoint from `main.html`: a document pulled in by an included script's literal
    `ctx.include('x.html')` contributes its own includes too.
    (24b-html-composition-and-plugin-tags.md, 24-html-component-studio.md)"""
    for page, _pp, _pt in core.iter_nodes(root):
        if page.get("pluginName") != "siteMapPage":
            continue
        where = "%s (%s)" % (page.get("name"), page.get("alias") or "-")
        for node in _page_own_html_studio_nodes(page):
            sm = ((node.get("properties") or {}).get("studioModel") or {}).get("stringValue")
            if not sm:
                continue                      # classic raw-HTML component: no document space, no includes
            try:
                model = json.loads(sm)
            except (json.JSONDecodeError, TypeError):
                continue                      # already ERRORed as malformed studioModel JSON
            if not isinstance(model, dict):
                continue
            comp = node.get("name") or node.get("identifier")

            # -- the document space: 'main' IS the html property; a docs[] entry named 'main' is ignored --
            docs = {"main": _html_of(node)}
            for d in model.get("docs") or []:
                if not isinstance(d, dict):
                    continue
                nm = d.get("name")
                if nm and nm != "main":
                    docs[nm] = d.get("html") or ""
            scripts, enabled = {}, {}
            for s in model.get("scripts") or []:
                if not isinstance(s, dict):
                    continue
                nm = s.get("name")
                if not nm:
                    continue
                scripts[nm] = s.get("code") or ""
                enabled[nm] = s.get("enabled", True) is not False
            if len(docs) == 1 and not scripts:
                continue

            # -- edges: document -> documents, document -> scripts (declares the program) -----------------
            # `declares` is the MODE signal and it is the EXTENSION, not the resolution: a src ending .js/.mjs
            # puts the component in include mode even when it names no script of this component (the platform
            # does exactly that, so a typo must not fall back to "run everything" — it must show up as an
            # empty program). Mis-spell the only script include and NOTHING runs.
            doc_edges, script_edges, script_decl = {}, {}, {}
            for dn, dh in docs.items():
                de, se, declares = [], [], False
                for src in _include_srcs(dh):
                    kind, target = _resolve_include(src, docs, scripts)
                    if kind == "script":
                        declares = True
                    if kind is None:
                        r.warn("page %s: html component %r, document %s: <include src=%r> carries no "
                               ".html/.htm/.js/.mjs extension — documents and scripts are two independent "
                               "name spaces, so the extension is what selects one; an extension-less src is "
                               "refused and the tag renders an HTML comment instead of the content. "
                               "(24b-html-composition-and-plugin-tags.md)"
                               % (where, comp, _include_label(dn, "doc"), src))
                    elif target is None:
                        r.warn("page %s: html component %r, document %s: <include src=%r> resolves to no %s "
                               "of this component — %s. An src addresses THIS component's own space only "
                               "(%s: %s); stored names are extension-less, so `src=\"detail.html\"` finds the "
                               "document named `detail`. (24b-html-composition-and-plugin-tags.md)"
                               % (where, comp, _include_label(dn, "doc"), src,
                                  "document" if kind == "doc" else "script",
                                  "that slot renders an HTML comment and brings in nothing" if kind == "doc"
                                  else "the .js EXTENSION still switches this component into include mode, so "
                                       "the program is built WITHOUT this script (a script include renders "
                                       "nothing on the page either way)",
                                  "documents" if kind == "doc" else "scripts",
                                  ", ".join(sorted(_include_label(n, kind)
                                                   for n in (docs if kind == "doc" else scripts))) or "none"))
                    else:
                        (de if kind == "doc" else se).append(target)
                doc_edges[dn] = de
                script_edges[dn] = se
                script_decl[dn] = declares

            # -- a script's literal ctx.include() pulls in further documents (documents only) --------------
            script_docs = {}
            for sn, code in scripts.items():
                sd = []
                for src in _ctx_include_srcs(code):
                    kind, target = _resolve_include(src, docs, scripts)
                    if kind != "doc":
                        r.warn("page %s: html component %r, script %s: ctx.include(%r) — the document name "
                               "must carry .html (ctx.include renders a DOCUMENT server-side; it cannot take "
                               "a script). The call rejects at runtime and nothing is inserted. "
                               "(24-html-component-studio.md)"
                               % (where, comp, _include_label(sn, "script"), src))
                    elif target is None:
                        r.warn("page %s: html component %r, script %s: ctx.include(%r) names no document of "
                               "this component (%s) — the call rejects at runtime and the host element stays "
                               "empty. (24-html-component-studio.md)"
                               % (where, comp, _include_label(sn, "script"), src,
                                  ", ".join(sorted(_include_label(n, "doc") for n in docs))))
                    else:
                        sd.append(target)
                script_docs[sn] = sd

            # -- CYCLE: the expansion never terminates -> ERROR ---------------------------------------------
            state, stack, seen = {}, [], set()

            def dfs(dn):
                state[dn] = 1
                stack.append(dn)
                for t in doc_edges.get(dn, []):
                    if state.get(t) == 1:
                        loop = stack[stack.index(t):] + [t]
                        key = frozenset(loop)
                        if key not in seen:
                            seen.add(key)
                            r.err("page %s: html component %r has an <include> CYCLE %s — the expansion "
                                  "never terminates, so that branch renders an HTML comment instead of the "
                                  "documents, and the studio refuses to save the component at all. No single "
                                  "document reveals it: read the graph, and make sure an included document "
                                  "never includes one of its own includers. "
                                  "(24b-html-composition-and-plugin-tags.md)"
                                  % (where, comp, " -> ".join(_include_label(x, "doc") for x in loop)))
                    elif state.get(t, 0) == 0:
                        dfs(t)
                stack.pop()
                state[dn] = 2

            for dn in docs:
                if state.get(dn, 0) == 0:
                    dfs(dn)

            # -- which scripts actually run: reachability from main.html is a FIXPOINT ---------------------
            reach, todo, included = {"main"}, ["main"], []
            include_mode = False
            while todo:
                dn = todo.pop(0)
                if script_decl.get(dn):
                    include_mode = True                   # the EXTENSION flips the mode, resolved or not
                for sn in script_edges.get(dn, []):
                    if sn not in included:
                        included.append(sn)
                    for t in script_docs.get(sn, []):      # a script's ctx.include feeds reachability back
                        if t not in reach:
                            reach.add(t)
                            todo.append(t)
                for t in doc_edges.get(dn, []):
                    if t not in reach:
                        reach.add(t)
                        todo.append(t)
            if include_mode:
                if not included and scripts:
                    r.warn("page %s: html component %r: a <include src=\"….js\"> puts this component in "
                           "include mode, but NOT ONE script include resolves — so the component's program "
                           "is EMPTY: the markup renders, no author JS runs at all, and the browser console "
                           "stays clean. Fix the misspelt src(es) above (scripts: %s). "
                           "(24d-html-component-structure.md)"
                           % (where, comp,
                              ", ".join(sorted(_include_label(n, "script") for n in scripts))))
                for sn in scripts:
                    if enabled.get(sn, True) and sn not in included:
                        r.warn("page %s: html component %r: script %s is ENABLED but no reachable document "
                               "includes it. This component uses script includes, so ONLY included scripts "
                               "run — this one never executes. Add <include src=\"%s\"> to a document "
                               "reachable from main.html, or disable the script. "
                               "(24-html-component-studio.md)"
                               % (where, comp, _include_label(sn, "script"), _include_label(sn, "script")))


# Query fields safe to embed in a chart replacement (matches the working base charts; anything beyond this is
# the query REP-OBJECT's metadata, which breaks chart-config deserialization — see _check_chart_query_embeds).
_SAFE_CHART_QUERY_KEYS = {"id", "identifier", "realmName", "clientName", "name", "query", "sourceIdentifier",
                         "offset", "itemsPerPage", "parameters", "attributes", "aggregations"}


def _check_chart_query_embeds(p, r):
    """RENDERS-EMPTY ('Modify html') (ERROR). A `chart.js.plugin` embeds a query record in each
    `replacements[].query` of the chart config (in `properties.Javascript`). The plugin reads that config
    and SWALLOWS a deserialization failure, returning an EMPTY model — so the chart renders as a blank `nct.html.plugin`
    "Modify html" cell with an empty HTML/JS editor. Embedding the FULL query REP-OBJECT (its rep metadata:
    `creationTime`/`modificationTime` Instant strings, `errors`, `message`, `hidden`, `schedule`,
    `lastScheduledTime`, `statementTimeoutSeconds`, `wrapInPaging`) breaks that nested-query deserialization.
    The working base charts embed ONLY the 12 query fields. ERROR on any extra key OR unparseable Javascript.
    validate can't catch this offline otherwise (it doesn't deserialize into the platform's records). (22)."""
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "chart.js.plugin":
            continue
        jv = node.get("properties", {}).get("Javascript") or {}
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            model = json.loads(sv)
        except Exception as e:
            r.err("chart.js.plugin %s properties.Javascript is not valid JSON (%s) — the chart renders empty. "
                  "(22-charts-params-and-filters.md)" % (node.get("identifier"), e))
            continue
        for repl in (model.get("replacements") or []):
            q = repl.get("query")
            if not isinstance(q, dict):
                continue
            extra = sorted(set(q.keys()) - _SAFE_CHART_QUERY_KEYS)
            if extra:
                r.err("chart.js.plugin %s replacement %r embeds a query carrying extra rep-object field(s) %s — "
                      "these break the chart config's deserialization (the plugin swallows the failure → "
                      "EMPTY model → the chart renders a blank 'Modify html' cell). Embed ONLY the 12 query "
                      "fields (id/identifier/realmName/clientName/name/query/sourceIdentifier/offset/itemsPerPage/"
                      "parameters/attributes/aggregations). (22-charts-params-and-filters.md)"
                      % (node.get("identifier"), repl.get("name"), extra))
                break


def _check_content_node_field_types(root, r):
    """A content-node field that is a JSON *string* where it is an object/array on other nodes.

    branches.json is deserialized field by field, with no leniency:
    a string where an object is declared throws
        JsonSyntaxException: Expected BEGIN_OBJECT but was STRING at line 1 column N path $[0].rootContent...
    and the platform aborts the WHOLE project import (ui.log: "Project import orchestration failed",
    "Import FAILED for realm=..."). Nothing is written, so there is no partial-import symptom to
    chase — the import just fails.

    The usual cause is a staging placeholder that was never substituted (e.g. roleAccess left as
    "<<< copy it from the parent >>>"). We can't see the DTO field types, so — as with the
    rep-object check above — we flag internal inconsistency: a field that is structural on other
    nodes and a bare string here is almost certainly wrong-typed.
    """
    structural = set()
    for node, _pp, _pt in core.iter_nodes(root):
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                structural.add(k)
    structural.discard("properties")  # properties.* slots are checked by their own rules
    for node, _pp, _pt in core.iter_nodes(root):
        for k in structural:
            if isinstance(node.get(k), str):
                val = node[k]
                r.err("content node %r <%s> (%s): field %r is a JSON string (%r) but is a JSON "
                      "object/array on other nodes — GSON throws 'Expected BEGIN_OBJECT but was "
                      "STRING' and the platform aborts the ENTIRE project import. Fix the field's "
                      "type before packing (roleAccess: copy the parent node's object)."
                      % (node.get("name"), node.get("identifier"), node.get("pluginName"), k,
                         val[:60] + ("..." if len(val) > 60 else "")))


def _check_content_node_ids(root, r):
    """A content node's persisted `id` is a per-project DB primary key. A NEW node authored
    by the toolkit must have id=null so the platform assigns one on import. Two failure modes
    this catches:
      * DUPLICATE non-null id — e.g. a subtree CLONED N times from a reference export keeps the
        template's real ids on every copy → the importer drops/collides the copies (the classic
        "no filter form after import" bug). -> ERROR.
      * a filter-form / form subtree carrying any non-null id (almost always a stale clone id). -> WARN.
    """
    from collections import Counter
    ids = Counter()
    for node, _pp, _pt in core.iter_nodes(root):
        nid = node.get("id")
        if nid:
            ids[nid] += 1
    dupes = {i: c for i, c in ids.items() if c > 1}
    for i, c in dupes.items():
        r.err("duplicate content node id %s appears %d times — a node subtree was cloned without "
              "nulling its `id`. New content nodes MUST have id=null (the platform assigns ids on "
              "import); a duplicate/foreign id makes the importer drop the copies." % (i, c))

    def subtree_has_nonnull_id(page_node):
        bad = []
        def w(n):
            if n.get("id"):
                bad.append((n.get("pluginName"), n.get("id")))
            for c in n.get("children") or []:
                w(c)
        w(page_node)
        return bad
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") in ("dynaform.filter.form.plugin", "dynaform.form.plugin"):
            bad = subtree_has_nonnull_id(node)
            bad = [b for b in bad if b[1] not in dupes]  # dupes already ERRORed
            if bad:
                r.warn("%s subtree carries non-null content id(s) %s — if this was CLONED from another "
                       "export, null every `id` (keep identifier/uniqueIdentifier fresh) or the import "
                       "drops it." % (node.get("pluginName"), [b[1] for b in bad][:3]))


# plugin types whose authoring machinery (Settings-panel nav name + settings sync channel) is
# TYPE-scoped and broadcast page-wide, so two instances of the SAME type on one page collide:
# the 2nd Settings registration evicts the 1st (can't configure it) and any settings change syncs
# into every instance's model (both collapse onto one CRUD). Same for crud.tree / process.table.
# Different types together are fine (distinct keys). See 14-plugin-catalog-all.md §"one per type".
_ONE_PER_PAGE_TYPES = ("crud.table.plugin", "crud.tree.plugin",
                       "process.table.pluin", "process.table.plugin")
_CHART_PLUGINS = ("chart.js.plugin",)


def _page_own_plugins(page):
    """pluginName -> count, for plugins in a page's OWN content (not descending into child pages)."""
    from collections import Counter
    counts = Counter()
    def w(n):
        for c in n.get("children") or []:
            if c.get("pluginName") == "siteMapPage":
                continue
            pn = c.get("pluginName")
            if pn:
                counts[pn] += 1
            w(c)
    w(page)
    return counts


def _tables_by_container(page):
    """Count type-scoped table plugins per CONTAINER within a page (not descending into child
    siteMapPages). A `nct.tab.plugin` splits its content into per-tab containers — two same-type
    tables in DIFFERENT tabs are fine, so each direct tab-pane parsis is its own container."""
    from collections import defaultdict, Counter
    containers = defaultdict(Counter)
    def w(n, container):
        for c in n.get("children") or []:
            pn = c.get("pluginName")
            if pn == "siteMapPage":
                continue
            if pn in _ONE_PER_PAGE_TYPES:
                containers[container][pn] += 1
            if pn == "nct.tab.plugin":
                # each tab pane (a direct nct.parsis.plugin child) is its own container
                for pane in c.get("children") or []:
                    if pane.get("pluginName") == "nct.parsis.plugin":
                        w(pane, pane.get("uniqueIdentifier") or id(pane))
                    else:
                        w(pane, container)
            else:
                w(c, container)
    w(page, "__page__")
    return containers


def _check_tab_size(root, r):
    """An authored `tabModel` should carry `"size": "SMALL"`.

    BIG is what you get by ACCIDENT, never by choice: the field's default is `TabSize.BIG`
    and a null size is coerced to BIG, so simply omitting the key renders
    the chunky full-height bar that eats vertical space above every grid. SMALL is the compact
    `nav-tabs` strip the platform's own screens use — a hand-authored tab node should be SMALL almost every time.

    WARN (not ERROR): BIG is legitimate for 2-3 top-level *modes*, just not for section switching.
    Negative-tested: zero false positives on known-good projects."""
    def walk(n, alias=None):
        if n.get("pluginName") == "siteMapPage":
            alias = n.get("alias")
        yield n, alias
        for c in n.get("children") or []:
            yield from walk(c, alias)

    for n, alias in walk(root):
        if n.get("pluginName") != "nct.tab.plugin":
            continue
        raw = ((n.get("properties") or {}).get("tabModel") or {}).get("stringValue")
        try:
            size = (json.loads(raw).get("size") or "") if raw else ""
        except Exception:
            continue
        if size.upper() != "SMALL":
            r.warn("tab node %r on page %r has tabModel size %s — author \"size\": \"SMALL\". Omitting "
                   "the key does NOT give you a neutral default: the field's default is TabSize.BIG "
                   "and a null size is coerced to BIG, so you get the chunky bar "
                   "that eats vertical space above every grid. Use BIG only for 2-3 top-level MODES, "
                   "never for section switching. (14-plugin-catalog-all.md §1.8)"
                   % (n.get("identifier"), alias or "-", ("%r" % size) if size else "ABSENT"))


def _check_one_table_plugin_per_page(root, r):
    """ONE table per page — the ONLY exception is separate TABS. This holds for ANY two table
    plugins, whether or not they are the same type.

    Two reasons, and they are independent:
      * SAME type (two crud.tables, two trees, two process tables) — a hard technical collision:
        they share a type-scoped Settings panel + sync channel that broadcast page-wide, so the 2nd
        is unconfigurable and they cross-bind.
      * MIXED types (e.g. a crud.table next to a process.table) — no key collision, but it is still
        forbidden: a page is one workplace answering one question, and two stacked grids force the
        reader to work out which one they are looking at. Put each in its own `nct.tab.plugin` tab,
        or on its own page.

    Every tab pane is its own container here, so tables in DIFFERENT tabs are OK, while two anywhere
    else on the page (stacked, or two grid cells) ERROR. Also: a DASHBOARD (charts) should carry NO
    crud/tree/process table — put drill-down tables on their own pages and link to them."""
    def walk_pages(page):
        yield page
        for c in page.get("children") or []:
            if c.get("pluginName") == "siteMapPage":
                yield from walk_pages(c)
    for page in walk_pages(root):
        label = page.get("name") or page.get("alias") or page.get("identifier")
        # 1) >1 table in one container (i.e. not separated into different tabs) -> ERROR
        for container, cnts in _tables_by_container(page).items():
            same_type = [(pn, n) for pn, n in cnts.items() if n > 1]
            for pn, n in same_type:
                r.err("page %r has %d %s on one page NOT separated into tabs — two same-type tables "
                      "may share a page ONLY when each sits in its own nct.tab.plugin tab (they share "
                      "a page-wide type-scoped Settings panel + live-sync channel, so otherwise the "
                      "2nd is unconfigurable and they cross-bind). Put each in its own tab, or its own "
                      "page. (14-plugin-catalog-all.md §2.3)" % (label, n, pn))
            if not same_type and sum(cnts.values()) > 1:
                r.err("page %r stacks %d tables of DIFFERENT types in one container (%s) — one page "
                      "carries ONE table. Different types do not collide on the sync key, but a page "
                      "is one workplace answering one question and two stacked grids leave the reader "
                      "guessing which is which. Put each in its own nct.tab.plugin tab, or give each "
                      "its own page. (14-plugin-catalog-all.md §2.3)"
                      % (label, sum(cnts.values()),
                         ", ".join("%s x%d" % (pn, n) for pn, n in sorted(cnts.items()))))
        # 2) a chart dashboard should not also host a data table -> WARN
        counts = _page_own_plugins(page)
        n_charts = sum(counts.get(cp, 0) for cp in _CHART_PLUGINS)
        n_tables = sum(counts.get(pn, 0) for pn in _ONE_PER_PAGE_TYPES)
        if n_charts >= 3 and n_tables >= 1:
            r.warn("page %r is a dashboard (%d charts) but also hosts %d data table(s) — dashboards "
                   "should be charts only; move the table(s) to their own page(s) and link to them. "
                   "(A dynaform filter drives tables via onFilterSubmit, NOT charts — so a filter on a "
                   "table-less dashboard is inert too.) (14-plugin-catalog-all.md)" % (label, n_charts, n_tables))


def _schema_exists(project, name):
    return any(s.get("name") == name for s in project.db.get("schemas", []) or [])


_UPDATE_TBL_RE = re.compile(r"\bUPDATE\s+([a-z_][a-z0-9_]*)\s+SET", re.I)
_INSERT_TBL_RE = re.compile(r"\bINSERT\s+INTO\s+([a-z_][a-z0-9_]*)\s*\(([^)]*)\)", re.I)


def _sql_write_tables(sql):
    tabs = set(_UPDATE_TBL_RE.findall(sql or ""))
    for m in _INSERT_TBL_RE.finditer(sql or ""):
        tabs.add(m.group(1))
    return tabs


def _parse_insert(sql):
    m = _INSERT_TBL_RE.search(sql or "")
    if not m:
        return None, set()
    cols = {c.strip() for c in m.group(2).split(",") if c.strip()}
    return m.group(1), cols


def _parse_inserts(sql):
    """EVERY `INSERT INTO t (cols…)` in one script, as (table, {cols}).

    One method writes more than one table: a posting engine inserts the movement AND
    the balance row, and the column list of the second one is where the omission hides.
    `_parse_insert` sees only the first statement, which is why the NOT NULL check that
    used it missed a column that made posting fail on every single call.
    """
    out = []
    for m in _INSERT_TBL_RE.finditer(sql or ""):
        out.append((m.group(1), {c.strip() for c in m.group(2).split(",") if c.strip()}))
    return out


def _expr_resolves(expr, kind, roots, leaves, list_keys):
    root = expr.split(".")[0]
    leaf = expr.split(".")[-1] if "." in expr else None
    if kind == "list-col":
        keys = set().union(*list_keys.values()) if list_keys else set()
        if root not in keys:
            return False
        if leaf and leaf not in keys:
            return False
        return True
    if root not in roots:
        return False
    if leaf and leaf not in leaves:
        return False
    return True


def _check_enum_dropdowns(p, r):
    """In a dynamic-integration project the DynamicEnum registry is empty after
    import and Class.forName(<integration enum FQN>) fails (no jar on the report
    classpath), so an enum dropdown that carries only dataClass — no enumValues
    snapshot and no choices ruleIdentifier — renders BLANK: the field can't be
    picked or saved. Warn on each such control."""
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.form.rimm.drop.down.field.plugin":
            continue
        try:
            st = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        dc = st.get("dataClass") or ""
        # an integration enum FQN (not java.lang.String used by FK-id dropdowns)
        if "." not in dc or dc.startswith("java.") or dc == "java.lang.String":
            continue
        if st.get("enumValues") or st.get("ruleIdentifier"):
            continue
        r.warn("enum dropdown %r (dataClass %s) has no enumValues snapshot and no "
               "choices ruleIdentifier — it will render blank after import (add a "
               "settings.enumValues option map or a choices rule)"
               % (st.get("fieldExpression") or node.get("name"), dc.split(".")[-1]))



def _check_dropdown_model_binding(p, r):
    """A rule-backed dropdown must be bound to the SCALAR key, not to the joined object.

    The control renders a plain ``<select>`` whose option values are the POSITION of each
    choice, and it decides which one is selected by matching the field's current value
    against the option's `key`. Bind `fieldExpression` to the object (`customer`, dataClass
    ObjectNode) and there is nothing to match: the row's value is a partial object built by
    the SELECT's join, never equal to a full choice row. Nothing is reported — the browser
    simply shows option #0.

    That is the whole defect, and it is not cosmetic: the control submits whatever it
    displays. Re-saving a record the user only meant to look at silently re-points the
    foreign key to the FIRST entry of the list. It bites hardest in LINE forms, where a
    parent save rewrites every line, so one careless edit can re-point a whole document.

    Bind to `<field>.id` (dataClass java.lang.String) — the same shape the platform's own
    field generator writes for header controls — and the value is the scalar the option key
    is compared with. See 02-form-controls-reference.md §7.
    """
    OBJECT_CLASSES = ("com.fasterxml.jackson.databind.node.ObjectNode",)
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.form.rimm.drop.down.field.plugin":
            continue
        try:
            st = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        fe = st.get("fieldExpression") or ""
        key = st.get("key") or ""
        if not fe or not key:
            continue
        if (st.get("dataClass") or "") not in OBJECT_CLASSES:
            continue
        if fe.endswith("." + key):
            continue
        r.err("dropdown %r is bound to the OBJECT %r (dataClass ObjectNode) while it keys its "
              "options on %r — the control cannot match the row's value to an option, so it "
              "renders the FIRST entry and saving re-points the foreign key to it. Bind it to "
              "%r. (02-form-controls-reference.md \u00a77)"
              % (node.get("name") or fe, fe, key, fe + "." + key))


_SERVICE_CRUD_RE = re.compile(r"service\.crud\.(\w+)\.")
_CHOICES_CONVERTER_RE = re.compile(r"\bto(?:SelectOptions|AutoCompleteOptions)(?:Localized)?\s*\(")
# A choices rule is VALID when it produces option pairs by ANY of: the toSelectOptions*/
# toAutoCompleteOptions* converters, a RIMM query (service.rimm.run — returns option rows), or a
# literal [[key:…, value:…], …] option list (static options). All three shapes occur in working projects.
_OPTION_PRODUCER_RE = re.compile(
    r"\bto(?:SelectOptions|AutoCompleteOptions)(?:Localized)?\s*\("
    r"|service\.rimm\.run\s*\("
    r"|\[\s*key\s*:")
# a RAW entity fetch returned as-is (the fackap) — a crud find*/findAll*/findByParent with none of the
# producers above (find\w* covers find, findAll, findByParent, findAllByParent used by the tree picker).
_RAW_FETCH_RE = re.compile(r"service\.crud\.\w+\.find\w*\s*\(")
_FINDALL_ARGS_RE = re.compile(r"\.findAll\(\s*\[([^\]]*)\]")
# The tree picker is a choices control too: its ruleIdentifier fetches CHILDREN by attrs.get('parentId')
# and MUST still end in toSelectOptions* (erp's RIMM_TREE_* rules do). It was previously excluded.
_CHOICE_PLUGINS = ("dynaform.form.rimm.drop.down.field.plugin",
                   "dynaform.form.rimm.autocomplete.field.plugin",
                   "dynaform.form.tree.picker.plugin")
_PAGING_KEYS = {"rowsInPage", "pageNumber"}


def _check_choices_rules(p, r):
    """A dropdown/autocomplete CHOICES rule (settings.ruleIdentifier) MUST convert its rows into
    option pairs via service.global.conversion.toSelectOptions[Localized] (dropdown) /
    toAutoCompleteOptions[Localized] (autocomplete). This is the single most common builder fackap:
    returning a raw `service.crud.X.findAll(...)` entity list makes the picker show "No results found"
    (the runtime convertToValueMap can only pair rows that came through toSelectOptions*) AND hides the
    "Show Nav" affordance (ChoicesRuleShape stops recognizing it). Also caught:
      * a choices rule that calls `.findAll([<filter-key>...])` DIRECTLY with a partial param map —
        the default multi-optional findAll leaves the other `:col` unbound, first-appearing in
        `$1 IS NULL`, so Postgres throws "could not determine data type of parameter $1" at render.
        Use the search pipeline `acFindBy<Cap(X)>Like` (single typed param) or `find([:])`.
      * a dropdown whose SOURCE crud is LOCALIZED (has a localizationField jsonb) but the rule uses
        plain `toSelectOptions` — options then show the base column only (e.g. always the base locale,
        the "labels stuck on the base locale" bug); it must use `toSelectOptionsLocalized`.
    All three were the 2026-07-27 CDD-cockpit bugs. See 02-form-controls-reference.md §4a.
    (Treepicker findRules return raw rows to the tree data provider by design and are NOT checked here.)
    """
    rules_by_id = {}
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule")
        if isinstance(rr, dict):
            rules_by_id[rule.get("identifier")] = (rule.get("name"), rr.get("ruleScriptStr", "") or "")
    # (crudAlias, fieldExpression) pairs whose form control stores per-locale values
    # (settings.localized == true) — the precise signal that a dropdown over that field
    # must render localized labels. Using the CRUD-level localizationField alone would
    # false-positive on a localized CRUD whose *display* field isn't itself localized
    # (e.g. a customer legal name).
    localized_fields = set()
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName", "") or ""
        if not (pn.startswith("dynaform.form.") and pn.endswith(".plugin")):
            continue
        try:
            fst = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        if fst.get("localized") is True and fst.get("crudAlias") and fst.get("fieldExpression"):
            localized_fields.add((fst["crudAlias"], fst["fieldExpression"]))

    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") not in _CHOICE_PLUGINS:
            continue
        try:
            st = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        rid = st.get("ruleIdentifier")
        if not rid or rid not in rules_by_id:
            continue  # enum-bound (enumName) or dangling ref (flagged elsewhere)
        rname, body = rules_by_id[rid]
        field = st.get("fieldExpression") or st.get("name") or node.get("name")
        is_ac = node.get("pluginName").endswith("autocomplete.field.plugin")
        # (1) MUST produce option pairs. Valid producers: toSelectOptions*/toAutoCompleteOptions*, a
        #     RIMM query (service.rimm.run), or a literal [[key:…, value:…], …] list. The fackap is a
        #     RAW crud find/findAll returned with NONE of those. (A body with neither a producer nor a
        #     raw fetch is some shape we don't model — skip it rather than false-ERROR.)
        if not _OPTION_PRODUCER_RE.search(body):
            if _RAW_FETCH_RE.search(body):
                want = "toAutoCompleteOptions[Localized]" if is_ac else "toSelectOptions[Localized]"
                r.err("choices rule %r (field %r) returns a RAW entity list — it MUST produce option pairs "
                      "(service.global.conversion.%s, or service.rimm.run, or a literal [[key,value],…] list). "
                      "A raw findAll/find yields \"No results found\" AND hides Show Nav. "
                      "(02-form-controls-reference.md §4a)" % (rname, field, want))
            continue
        # (2) partial-findAll untyped-$1 trap
        for m in _FINDALL_ARGS_RE.finditer(body):
            keys = {k.split(":")[0].strip() for k in m.group(1).split(",") if ":" in k}
            if keys - _PAGING_KEYS:
                r.warn("choices rule %r calls .findAll([...]) with filter key(s) %s — the default "
                       "multi-optional findAll with a PARTIAL param map throws Postgres \"could not "
                       "determine data type of parameter $1\" at render. Use the acFindBy<X>Like search "
                       "pipeline or find([:]). (02-form-controls-reference.md §4a)"
                       % (rname, sorted(keys - _PAGING_KEYS)))
                break
        # (3) the display field is LOCALIZED but the rule uses plain toSelectOptions
        src = _SERVICE_CRUD_RE.search(body)
        display = st.get("displayName")
        if src and display and (src.group(1), display) in localized_fields and "Localized" not in body:
            r.warn("choices rule %r shows the LOCALIZED field %s.%s but uses plain toSelectOptions — "
                   "labels show the base column only (e.g. always the base locale, the \"always "
                   "base locale\" bug). Use toSelectOptionsLocalized so options follow the session locale. "
                   "(02 §4a / 20-localization.md)" % (rname, src.group(1), display))


_CONVERTER_START_RE = re.compile(r"\bto(SelectOptions|AutoCompleteOptions)(?:Localized)?\s*\(")
# The converters' Enum branch does NOT emit the positional argument names — it emits these synthetic
# sentinels, and the Choices-From-CRUD dialog wires enum-mode controls to them (globalFunctions.yaml).
_ENUM_SENTINELS = {"__key", "__display"}


def _strip_groovy_noise(body):
    """Drop // comments and triple-quoted blocks so dead/embedded text can't fake a converter call."""
    body = re.sub(r'"""[\s\S]*?"""', '""', body)
    body = re.sub(r"'''[\s\S]*?'''", "''", body)
    return re.sub(r"//[^\n]*", "", body)


def _split_top_level_args(s):
    """Split a Groovy argument list on TOP-LEVEL commas (quote-, escape- and nesting-aware)."""
    out, depth, cur, quote, esc = [], 0, "", None, False
    for ch in s:
        if quote:
            cur += ch
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote, cur = ch, cur + ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur)
    return [a.strip() for a in out]


def _str_lit(a):
    a = (a or "").strip()
    return a[1:-1] if len(a) >= 2 and a[0] in "\"'" and a[-1] == a[0] else None


def _converter_pairs(body):
    """Every (keyField, displayField) pair-key tuple a rule body puts on the wire.

    Ground truth is the converter source — the platform's `globalFunctions.yaml`, which declares:
        toSelectOptions(result, keyField, displayField)
        toSelectOptionsLocalized(result, keyField, displayField, localeKey=null, localizationFieldName='localize')
        toAutoCompleteOptions(result, field)
        toAutoCompleteOptionsLocalized(result, field, localeKey=null, localizationFieldName='localize')
    whose body is, per row:
        list.add([key: keyField,     value: item[keyField]])
        list.add([key: displayField, value: item[displayField]])
    So pair keys are the LITERAL argument strings taken POSITIONALLY. The trailing locale /
    localizationField arguments of the *Localized variants are plumbing, never pair keys — collecting
    "every string literal in the call" mis-reads them, so parse positionally.
    """
    body = _strip_groovy_noise(body)
    out = []
    for m in _CONVERTER_START_RE.finditer(body):
        i = m.end() - 1  # index of '('
        depth, j, quote, esc = 0, i, None, False
        while j < len(body):
            ch = body[j]
            if quote:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            continue  # unbalanced — don't guess
        args = _split_top_level_args(body[i + 1:j])
        if m.group(1) == "AutoCompleteOptions":
            if len(args) >= 2 and _str_lit(args[1]) is not None:
                f = _str_lit(args[1])
                out.append((f, f))          # autocomplete: key == display
        elif len(args) >= 3:
            k, d = _str_lit(args[1]), _str_lit(args[2])
            if k is not None and d is not None:
                out.append((k, d))
    return out


def _dto_field_maps(p):
    """{alias: (set(fieldName), {displayName: fieldName})} for the dynamic CRUDs.

    fieldName is the DTO *expression* the runtime resolves (camelCase); displayName is the
    snake_case DB column, addressable only inside SQL.
    """
    crud_file = p.cruds_file
    cruds = (crud_file.data.get("cruds", []) if crud_file else []) or []
    out = {}
    for c in cruds:
        fields = c.get("dtoFields") or []
        out[c.get("alias")] = ({f.get("fieldName") for f in fields},
                               {f.get("displayName"): f.get("fieldName") for f in fields})
    return out


def _check_choices_pair_keys(p, r):
    """The choices PAIR-KEY contract — the two halves the shape check above cannot see.

    `toSelectOptions(list,"K","D")` does NOT emit one map per row. Per globalFunctions.yaml it emits a
    FLAT pairwise list — two entries per row: {key:"K", value:row[K]}, {key:"D", value:row[D]}. The
    platform's value projector walks that list matching the entry's
    `key` against the control's settings.key / settings.displayName by LITERAL string equality, and
    emits an option only once BOTH sides are non-null. Three independent mistakes each silently yield
    an EMPTY picker — no exception, no log line, and a rule preview still looks populated:

      (1) FIELD-NAME CASE — K/D must be the DTO field expression (dtoFields[].fieldName, camelCase),
          never the DB column (dtoFields[].displayName, snake_case). `row["full_name"]` on a record
          exposing `fullName` is null, so every display value is null and all pairs are dropped.
      (2) SETTINGS DRIFT — settings.key/displayName must EXACTLY equal the emitted pair keys. The
          scaffold default is key="id", displayName="name"; the moment the rule keys on anything else
          (a business `code`, `businessKey`, `fullName`, `institution`…) nothing matches. The
          platform's choices generator keeps both sides in lockstep — it writes the SAME two strings into
          the rule body and the settings — so any drift is hand-authoring.
      (3) UNSET — a rule-bound picker with key/displayName absent. They have no defaults,
          and a null key never equals "id" for any entry, so the map comes back empty exactly as in (2).

    All three shipped together in one 2026-08 export (a Customer dropdown rendered zero
    options while its rule happily returned 120 rows). See 02-form-controls-reference.md §4a.
    """
    rules_by_id = {}
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule")
        if isinstance(rr, dict):
            rules_by_id[rule.get("identifier")] = (rule.get("name"), rr.get("ruleScriptStr", "") or "")
    dto = _dto_field_maps(p)

    # -- (1) converter field args must be DTO fieldNames, not DB columns ----------------
    # Attribute the option rows to the crud of the LAST service.crud.<alias> before the converter
    # call (a rule may fetch a lookup first and the option rows second); skip when the body touches
    # several cruds and we cannot tell, rather than ERROR against the wrong one.
    bad_arg_rules = set()
    for rid, (rname, body) in sorted(rules_by_id.items()):
        clean = _strip_groovy_noise(body)
        pairs = _converter_pairs(body)
        if not pairs:
            continue
        aliases = _SERVICE_CRUD_RE.findall(clean)
        if not aliases or len(set(aliases)) != 1:
            continue  # zero or ambiguous source — not resolvable offline
        alias = aliases[0]
        if alias not in dto:
            continue
        field_names, by_display = dto[alias]
        for key, display in pairs:
            for role, fld in (("key", key), ("display", display)):
                if not fld or fld in field_names or fld in _ENUM_SENTINELS:
                    continue
                if fld in by_display:
                    bad_arg_rules.add(rid)
                    r.err("choices rule %r passes the DB COLUMN %r as its %s field to the option "
                          "converter — the runtime resolves item[<fieldName>], so the value comes "
                          "back NULL and the picker renders EMPTY. Use %r (crud %r "
                          "dtoFields.fieldName). (02-form-controls-reference.md §4a)"
                          % (rname, fld, role, by_display[fld], alias))
                else:
                    r.warn("choices rule %r passes %r as its %s field but crud %r has no such "
                           "dtoField (ok if the rows come from a custom service method that adds "
                           "it). (02-form-controls-reference.md §4a)" % (rname, fld, role, alias))

    # -- (2)/(3) control settings.key/displayName must equal the emitted pair keys ------
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") not in _CHOICE_PLUGINS:
            continue
        try:
            st = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        rid = st.get("ruleIdentifier")
        if not rid:
            continue
        field = st.get("fieldExpression") or st.get("name") or node.get("name")
        if rid not in rules_by_id:
            r.err("choices control %r references ruleIdentifier %s which matches NO rule in this "
                  "export — the picker has no source and renders EMPTY. "
                  "(02-form-controls-reference.md §4a)" % (field, rid))
            continue
        rname, body = rules_by_id[rid]
        pairs = _converter_pairs(body)
        if not pairs:
            continue  # rimm.run / literal-list producer — pair keys aren't derivable offline
        if rid in bad_arg_rules:
            continue  # part 1 already told the author to rewrite these args; don't print a
                      # second message quoting the WRONG (pre-fix) name to mirror.
        got = (st.get("key"), st.get("displayName"))
        if got == (None, None):
            r.err("choices control %r is bound to rule %r but sets NEITHER key NOR displayName — "
                  "they have no defaults, so convertToValueMap matches nothing and the picker "
                  "renders EMPTY. Set key/displayName to %s. (02-form-controls-reference.md §4a)"
                  % (field, rname, " or ".join(repr(pr) for pr in sorted(set(pairs)))))
            continue
        if got in set(pairs):
            continue
        # Report the whole pair: per-role matching would accept a key from one converter call
        # combined with a display from another, which no single call ever emits.
        r.err("choices control %r settings (key=%r, displayName=%r) matches no pair emitted by its "
              "rule %r (which emits %s) — convertToValueMap pairs by LITERAL key match, so the "
              "picker renders EMPTY and existing rows show the raw stored value instead of a label. "
              "(02-form-controls-reference.md §4a)"
              % (field, got[0], got[1], rname,
                 ", ".join("(key=%r, displayName=%r)" % pr for pr in sorted(set(pairs)))))


_CRUD_CALL_RE = re.compile(r"service\.crud\.(\w+)\.(\w+)\s*\(")
_AC_METHOD_RE = re.compile(r"^acFind(?:All)?By\w+Like$")
_DEFAULT_CRUD_METHODS = {"find", "findAll", "count", "get", "create", "update", "delete"}


def _dynamic_crud_methods(p):
    """{alias: set(methodName)} for the DYNAMIC cruds only (static @Crud beans aren't enumerable
    from an export). Returns ({}, []) when there is no dynamic-cruds.json."""
    crud_file = p.cruds_file
    cruds = (crud_file.data.get("cruds", []) if crud_file else []) or []
    by_alias = {c.get("alias"): {m.get("methodName") for m in (c.get("methods") or [])} for c in cruds}
    return by_alias, cruds


def _outside_coercion_helper(code):
    """Blank out any closure that is itself a numeric coercion helper.

    `new BigDecimal(<runtime value>)` is exactly right INSIDE such a helper — that is the one place the
    trimming and defaulting happen. A project that routes its numbers through one should therefore be
    silent, not warned once per rule that uses it. The signature is a closure body that both trims and
    tests for empty, which no ordinary arithmetic does.
    """
    out, i = [], 0
    for m in re.finditer(r"=\s*\{", code):
        start = m.end() - 1
        depth, j = 0, start
        while j < len(code):
            if code[j] == "{":
                depth += 1
            elif code[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        block = code[start:j + 1]
        if ".trim()" in block and ("isEmpty()" in block or "== ''" in block or '== ""' in block):
            out.append(code[i:start])
            i = j + 1
    out.append(code[i:])
    return "".join(out)

def _check_query_line_comments(p, r):
    """A saved query may not contain a `--` line comment. It eats the paging wrapper.

    The platform does not execute a saved query as written: it wraps it for paging, appending the tail on
    the SAME line —

        select pp.* from ( <the query> ) pp OFFSET 0 ROWS FETCH NEXT <itemsPerPage> ROWS ONLY

    (one string-format call). A `--` on the query's LAST line therefore comments out
    the wrapper's own closing paren and OFFSET clause: Postgres answers `ERROR: syntax error at end of
    input`, the cell renders "Error occured in chart component <title>", and nothing offline sees it —
    the SQL reads perfectly in the generator source, where the comment sits on its own line.

    Only the last line is checked, and that is deliberate. A `--` on an EARLIER line of a multi-line
    stored query comments out only the rest of that line, which is ordinary, legal SQL — and multi-line
    stored queries are the norm (most of the queries in the library's own reference exports are
    multi-line). Erroring on all of them would block a build over a breakage that cannot happen.

    A generator that collapses its SQL to one line puts everything on the last line, so there the rule is
    "no `--` at all" — which is why chart generators should use the block form `/* … */` or keep the
    explanation in the generator source. String literals are stripped before matching, so a `--` inside
    quoted text is not reported.
    """
    for q in p.rep.get("queries", []) or []:
        sql = q.get("query")
        if not isinstance(sql, str) or not sql:
            continue
        without_strings = re.sub(r"'(?:''|[^'])*'", " ", sql)
        last_line = without_strings.rsplit("\n", 1)[-1]
        if "--" in last_line:
            r.err("query %r ends with a `--` line comment — the platform appends its paging wrapper "
                  "( `) pp OFFSET … FETCH NEXT …` ) on that same line, so the comment eats it and Postgres "
                  "reports `syntax error at end of input`. Use /* … */ or move the comment into the "
                  "generator. (22)" % q.get("name"))

def _check_rep_object_field_types(p, r):
    """A rep-object field that is a JSON OBJECT/ARRAY on its siblings but a serialized STRING here.

    This is the whole import-abort class in one shape. The platform reads `rep-objects.json` into its
    DTOs; a field typed as an object that arrives as a string is a type-mismatch error
    while the file is still being READ, so nothing in the archive is applied — not the sources, not the
    database dump. The user sees an import that "did nothing", with no object named anywhere.

    It is easy to produce by hand: serialize a nested value once too often (`json.dumps` on something
    that was already a dict) and the file still looks plausible. The signature is unambiguous, which is
    why this can be an ERROR rather than a guess — the SAME field on the SAME kind of object is an
    object/array everywhere else, and the outlier's string parses back into an object/array.

    Runs FIRST, and `cmd_validate` stops on it: every later check reads these shapes, so continuing
    would bury this error under a traceback from whichever check happened to touch the field."""
    for coll in core.REP_COLLECTIONS:
        objs = [o for o in (p.rep.get(coll) or []) if isinstance(o, dict)]
        if len(objs) < 2:
            continue
        structured = set()
        for o in objs:
            for field, value in o.items():
                if isinstance(value, (dict, list)) and value:
                    structured.add(field)
        for o in objs:
            label = o.get("name") or o.get("identifier") or "?"
            for field in sorted(structured):
                value = o.get(field)
                if not isinstance(value, str) or not value.strip():
                    continue
                try:
                    parsed = json.loads(value)
                except Exception:
                    continue  # ordinary text that merely shares a name — not this bug
                if not isinstance(parsed, (dict, list)):
                    continue
                # The settings mirror is the best-known member of this class and has its own
                # wording in the docs and in the regression test — keep saying it that way.
                lead = ("settings %r: content is a JSON string" % label
                        if (coll, field) == ("settings", "content")
                        else "%s %r: field %r is a JSON string" % (coll.rstrip("s"), label, field))
                r.err("%s but is a JSON object/array on every other %s in this export. The platform reads "
                      "rep-objects.json into its DTOs before anything is applied, so this one "
                      "field aborts the ENTIRE import — no sources, no database restore, no objects, "
                      "and nothing named in the UI. Store the value itself, not a serialized copy of "
                      "it. (00-export-format-and-import.md)" % (lead, coll.rstrip("s")))


def _check_dynamic_cruds_envelope(p, r):
    """The `dynamic-cruds.json` envelope — the one file whose type errors cost you the whole BL layer.

    The dynamic-CRUD import starts by parsing the file into an envelope (`exportVersion` + `cruds`).
    The platform reads `exportVersion` into an integer field, so a STRING there — `"1"` and especially `"1.0"`,
    which does not even coerce — throws while the file is still being read. The import continues: this is
    the LAST step of the import, so pages, rules, queries, contexts, forms, workflows, templates and
    the database all arrive and only the business logic is missing. What the user sees is a complete
    project whose every register renders its headers over zero rows, whose Business Logic console is empty,
    and whose scoped-fetch rules die with `No RSocket connection found for CRUD alias: <alias>` — a symptom
    that points at the runtime, not at a two-character type error in the archive.

    Nothing else reports it: `pack` does not read the file's types, the import's own report does not name
    the step it skipped, and the platform logs a parse failure the operator never sees.

    The toolkit writes the correct shape (`core.py`: `{"exportVersion": 1, "cruds": []}`); this catches a
    file that was hand-edited or produced by something else. (00-export-format-and-import.md §7,
    11-business-logic-dynamic-crud.md)"""
    crud_file = p.cruds_file
    if crud_file is None:
        return                                    # legitimately absent: static project, or bl not deployed
    data = crud_file.data
    if not isinstance(data, dict):
        r.err("dynamic-cruds.json: top level is %s, not an object — the importer parses it into "
              "an envelope {exportVersion, cruds}. (00-export-format-and-import.md §7)"
              % type(data).__name__)
        return

    version = data.get("exportVersion")
    if version is None:
        r.err("dynamic-cruds.json: no 'exportVersion'. It must be the integer 1.")
    elif isinstance(version, bool) or not isinstance(version, int):
        r.err("dynamic-cruds.json: exportVersion is %r (%s) but must be the INTEGER 1. The platform reads it "
              "into an int field, so this throws while the envelope is being parsed and the "
              "importer skips EVERY dynamic CRUD — silently, and last, so the rest of the project "
              "imports and only the business logic is missing. Registers then render headers over zero "
              "rows and scoped-fetch rules fail with \"No RSocket connection found for CRUD alias\"."
              % (version, type(version).__name__))

    cruds = data.get("cruds")
    if cruds is None:
        r.err("dynamic-cruds.json: no 'cruds' array — the envelope expects {exportVersion, cruds}.")
    elif not isinstance(cruds, list):
        r.err("dynamic-cruds.json: 'cruds' is %s, not an array." % type(cruds).__name__)
    else:
        for c in cruds:
            if not isinstance(c, dict):
                r.err("dynamic-cruds.json: a cruds[] entry is %s, not an object." % type(c).__name__)
                continue
            alias = c.get("alias") or "?"
            for field in ("alias", "name", "sourceIdentifier"):
                if not isinstance(c.get(field), str) or not (c.get(field) or "").strip():
                    r.err("dynamic-cruds.json: crud %r has no usable %r — the importer needs it to "
                          "create the CRUD and bind it to a live source." % (alias, field))
            if not isinstance(c.get("methods"), list):
                r.err("dynamic-cruds.json: crud %r has no 'methods' array." % alias)


def _check_platform_required_fields(p, r):
    """Fields the platform's own DTOs declare `@NotBlank` / `@NotNull`. A blank one is not a shape
    problem this format can see — it is a 400 the moment the archive is imported, and the objects
    import in a FIXED order (queries, then workflows, rules, contexts, form groups, forms, settings,
    process groups), so on a platform that stops at the first rejection everything queued behind it is
    skipped. The project then arrives with a database and nothing else: every screen blank, and the
    only clue a card that says "imported with warnings".

    The shape that produces it without anyone noticing: a scaffolded CRUD mints a paired query record
    per method, and `create`/`update`/`delete` are later turned into GROOVY orchestrators. Those three
    methods carry `queryIdentifier: null`, nothing ever fills their query records, and they ship as
    `"query": ""`. Nothing else in the build looks at a query body."""
    required = {
        "queries": ("query", ("name", "query")),
        "workflows": ("workflow", ("name",)),
        "roleGroups": ("role group", ("name", "roles")),
        "sources": ("source", ("name", "hostName", "port", "dbName", "schemaName",
                               "userName", "dbType")),
    }
    for coll, (singular, fields) in required.items():
        for obj in p.rep.get(coll, []) or []:
            if not isinstance(obj, dict):
                continue
            label = obj.get("name") or obj.get("identifier") or "?"
            for field in fields:
                value = obj.get(field)
                # @NotNull (a list/map field) is satisfied by an EMPTY collection — only @NotBlank
                # string fields reject blankness. Treating an empty list as missing would flag a role
                # group that legitimately grants nothing yet.
                if value is None or (isinstance(value, str) and not value.strip()):
                    r.err("%s %r has a blank %r — the platform declares it mandatory, so the import "
                          "REJECTS this object and everything imported after it may be skipped. Fill it "
                          "in, or (for a query record left behind when its method became GROOVY) delete "
                          "the record. (12-queries-sources-schedulers-and-rest.md, "
                          "11-business-logic-dynamic-crud.md)" % (singular, label, field))


def _check_query_reference_integrity(p, r):
    """A dynamic-CRUD method's `queryIdentifier` must resolve, and a `crud_*` query record should have
    a method behind it. A dangling identifier is silent — the method simply never runs the SQL the
    author is looking at in the editor — and an unreferenced `crud_*` record is the leftover of a
    method that changed type, which is where blank bodies come from."""
    _, cruds = _dynamic_crud_methods(p)
    if not cruds:
        return
    by_id = {q.get("identifier"): q for q in p.rep.get("queries", []) or [] if isinstance(q, dict)}
    referenced = set()
    for c in cruds:
        for m in c.get("methods", []) or []:
            qid = m.get("queryIdentifier")
            if not qid:
                continue
            referenced.add(qid)
            if qid not in by_id:
                r.err("dynamic CRUD %r method %r points at query %s, which is not in the export — the "
                      "method has no SQL to run and fails at the first call."
                      % (c.get("alias"), m.get("methodName"), qid))
    # Only the LEFTOVER shape is worth a word: the CRUD is still here and still has a method of that
    # name, but the method no longer runs SQL — so its record is dead weight and, if it was never
    # filled, the blank body above rejects the whole archive. A record whose alias no longer exists at
    # all is a fossil of a deleted/renamed CRUD, harmless and none of this check's business.
    live = {}
    for c in cruds:
        for m in c.get("methods", []) or []:
            live[("crud_%s_%s" % (c.get("alias"), m.get("methodName")))] = m
    for q in p.rep.get("queries", []) or []:
        if not isinstance(q, dict):
            continue
        name = q.get("name") or ""
        method = live.get(name)
        if method is None or q.get("identifier") in referenced:
            continue
        if method.get("methodType") == "SQL":
            # Still a SQL method — the record holds its statement and the pairing is simply not
            # recorded on the method. Telling the author to delete it would delete working SQL.
            r.warn("query %r is the paired record of SQL method %r but the method does not reference "
                   "it (`queryIdentifier` is unset) — the method still runs its own `script`, so the "
                   "editor and the runtime can drift apart. Point the method at the record."
                   % (name, method.get("methodName")))
            continue
        r.warn("query %r is the paired record of dynamic CRUD method %r, which no longer runs SQL "
               "(methodType=%s) — nothing will ever fill this record. Delete it before packing: an "
               "unfilled one is `\"query\": \"\"`, which the import REJECTS. "
               "(11-business-logic-dynamic-crud.md)"
               % (name, method.get("methodName"), method.get("methodType")))


LOCALIZATION_CANONICAL_KEY = "localize"


def _to_camel_case(name):
    """`snake_case` -> `snakeCase`, the executor's own rule: uppercase the letter after each `_`,
    leave a name without underscores alone."""
    if not name or "_" not in name:
        return name or ""
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)

# ⛔ NOT _MAP_KEY_RE — that name is bound again further down this file, and the LAST module-level
# binding wins for both call sites. A same-named constant here is dead code that reads as live.
_ARG_MAP_KEY_RE = re.compile(r"[\[,]\s*['\"]?([A-Za-z_]\w*)['\"]?\s*:")
_SCALAR_PARAM_TYPES = {"boolean", "integer", "int", "long", "short", "double", "float",
                       "bigdecimal", "biginteger", "uuid", "date", "time", "timestamp",
                       "localdate", "localtime", "localdatetime", "instant"}


def _balanced_call_arg(text, start):
    """The argument text of a call whose opening paren sits at `start - 1`."""
    depth, i = 1, start
    while i < len(text) and depth:
        if text[i] in "([":
            depth += 1
        elif text[i] in ")]":
            depth -= 1
        i += 1
    return text[start:i - 1].strip() if depth == 0 else None


def _known_map_keys(arg, body):
    """Every key the argument map is known to carry, or None when it cannot be read statically.

    ⛔ None means "undecidable", and the caller stays SILENT on it. That distinction is the whole
    safety of this check: a map is seeded in Groovy half a dozen ways — a literal, `m.key = v`,
    `m.put('key', v)`, `m << [k: v]`, `m += [...]`, a reassignment — and reading only the literal
    while a later statement adds the missing key turns a correct rule into a reported defect. So
    every shape this scanner does not model makes it hand back None rather than a short answer."""
    if arg.startswith("["):
        return set(_ARG_MAP_KEY_RE.findall(arg))
    if re.fullmatch(r"[A-Za-z_]\w*", arg or ""):
        name = re.escape(arg)
        # More than one binding of the same local, or a `<-` style merge: stop reading.
        if len(re.findall(r"(?<![\w.])%s\s*=(?!=)" % name, body)) > 1:
            return None
        if re.search(r"(?<![\w.])%s\s*(?:<<|\+=|\.putAll\s*\()" % name, body):
            return None
        m = re.search(r"def\s+%s\s*=\s*\[" % name, body)
        if not m:
            return None
        literal = _balanced_call_arg(body, m.end())
        if literal is None:
            return None
        keys = set(_ARG_MAP_KEY_RE.findall("[" + literal + "]"))
        keys |= set(re.findall(r"%s\[\s*['\"]([A-Za-z_]\w*)['\"]\s*\]\s*=(?!=)" % name, body))
        keys |= set(re.findall(r"%s\.([A-Za-z_]\w*)\s*=(?!=)" % name, body))
        keys |= set(re.findall(r"%s\.put\s*\(\s*['\"]([A-Za-z_]\w*)['\"]" % name, body))
        return keys
    return None


# ⛔ NOT _PLACEHOLDER_RE — that name is already taken further down the file for `{{mustache}}`
# slots, and a second module-level binding silently wins over the first.
_QUERY_PARAM_HEAD_RE = re.compile(r"\{\s*name\s*:\s*['\"]?([A-Za-z_]\w*)['\"]?")
_NEUTRALISE_KEYWORDS = re.compile(r"\b(WHERE|AND|OR|HAVING|ON)\b", re.I)
# A span the keyword scan anchored inside a select-list expression. The scan is a token
# approximation of the engine's AST walk; on `CASE WHEN … THEN … END` it latches the WHEN and the
# span it reports is an expression, not a predicate. Every such span is discarded — the wrapped
# placeholder this check exists for never sits inside one.
_SELECT_LIST_KEYWORDS = re.compile(r"\b(CASE|WHEN|SELECT)\b", re.I)


def _mask_sql_text(sql):
    """`sql` with every string literal and comment blanked to spaces, offsets preserved.

    A `(` inside `'a (b'` or inside `-- note (` is DATA. Counting it as an opened paren is how the
    placeholder scan reported a wrapped placeholder on a query that has none."""
    out = list(sql)
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            end = min(j + 1, n)
        elif c == "-" and sql.startswith("--", i):
            end = sql.find("\n", i)
            end = n if end < 0 else end
        elif c == "/" and sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            end = n if end < 0 else end + 2
        else:
            i += 1
            continue
        for k in range(i, end):
            if out[k] != "\n":
                out[k] = " "
        i = end
    return "".join(out)


def _query_placeholders(sql, masked=None):
    """(text, start, end) for every `{name: …}` slot, nested braces and all.

    A brace-DEPTH scan, not a regex: the recommended period filter is
    `{name:'Since', type:'dropdown-string', dropDownPopulation:{query:…}}`, and a pattern that
    refuses to cross a nested brace cannot see it at all — which made the whole check blind to
    exactly the filters doc 22 tells authors to write."""
    masked = _mask_sql_text(sql) if masked is None else masked
    # The HEAD is matched on the real text — masking blanks the quoted `'since'` and the pattern
    # would never match — while the brace DEPTH is counted on the mask, so a `}` inside a literal
    # cannot close the slot early. Same length, so the offsets are the same in both.
    for m in _QUERY_PARAM_HEAD_RE.finditer(sql):
        if masked[m.start()] != "{":
            continue          # the whole slot sits inside a literal or a comment: not code
        depth, i = 0, m.start()
        while i < len(masked):
            if masked[i] == "{":
                depth += 1
            elif masked[i] == "}":
                depth -= 1
                if depth == 0:
                    yield sql[m.start():i + 1], m.start(), i + 1
                    break
            i += 1


def _dangling_placeholder_spans(sql):
    """Placeholders whose neutralisation would leave a construct OPENED before them dangling.

    The engine's "no value supplied" rewrite walks back to the nearest WHERE/AND/OR/HAVING/ON, blanks
    every token from there to the placeholder and writes `1=1`. Whatever was written AFTER the
    placeholder survives. So the failure is precise: if the blanked span OPENS a parenthesis it does
    not close — `AND (`, `AND ... CAST(`, `AND COALESCE(` — then that paren's closer is still sitting
    in the tail with nothing to close, and the statement stops parsing.

    Counting the span's open depth (rather than re-balancing the whole rewritten statement) is what
    makes this safe on a real query: the keyword scan is a token approximation of an AST walk, and on
    a query with an `AND` inside a `CASE` in the select list it anchors too early. A wrong anchor
    produces a span with SURPLUS closers, never surplus openers — so it is silently ignored, while the
    genuine "I wrapped my placeholder" shape still reports.
    """
    out = []
    masked = _mask_sql_text(sql)
    for text, start, _end in _query_placeholders(sql, masked):
        head = masked[:start]
        kw = None
        for k in _NEUTRALISE_KEYWORDS.finditer(head):
            kw = k
        span = head[kw.end():] if kw else head
        if _SELECT_LIST_KEYWORDS.search(span):
            continue          # anchored inside an expression, not a predicate — see the constant
        depth = span.count("(") - span.count(")")
        if depth > 0:
            out.append((text, sql[len(head) - len(span):start].strip()[:60]))
    return out


def _chart_query_sources(p):
    """(label, sql) for every query a chart actually runs — the rep-object AND the copy embedded in
    the chart's own model, which is the one the page executes."""
    wanted, out = set(), []
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "chart.js.plugin":
            continue
        raw = _prop_string_value(node, "Javascript") or _prop_string_value(node, "model") or ""
        if not raw.strip().startswith("{"):
            continue
        try:
            model = json.loads(raw)
        except Exception:
            continue
        for rep in model.get("replacements") or []:
            if not isinstance(rep, dict):
                continue
            if rep.get("queryIdentifier"):
                wanted.add(rep["queryIdentifier"])
            emb = rep.get("query")
            if isinstance(emb, dict) and emb.get("query"):
                out.append(("chart %r embedded query %r"
                            % (node.get("name"), emb.get("name") or "?"), emb["query"]))
    for q in p.rep.get("queries", []) or []:
        if isinstance(q, dict) and q.get("identifier") in wanted and q.get("query"):
            out.append(("query %r" % (q.get("name") or q.get("identifier")), q["query"]))
    return out


_CHART_CANVAS_RE = re.compile(r"this\s*\.\s*\$find\s*\(")
_CHART_INSTANCE_RE = re.compile(r"this\s*(?:\.\s*chart|\[\s*['\"]chart['\"]\s*\])\s*=(?!=)")
# `const self = this` before a callback is idiomatic and works exactly as well — the plugin is still
# the receiver. Failing it outright would red-flag a chart that renders.
# ⛔ `this` and NOTHING ELSE on the right. `var ctx = this.$find('canvas')[0]` also starts with
# `= this`, and treating `ctx` as a receiver made `ctx.chart = new Chart(...)` — assigning the
# instance to a local instead of to the plugin, which is the exact defect the check exists for —
# read as satisfying the contract.
_CHART_THIS_ALIAS_RE = re.compile(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*this\s*(?![\w.\[(])")


def _chart_receivers(js):
    """`this` plus every local the script captured it into."""
    return ["this"] + _CHART_THIS_ALIAS_RE.findall(js)


def _chart_reaches_canvas(js):
    return any(re.search(r"%s\s*\.\s*\$find\s*\(" % re.escape(rx), js)
               for rx in _chart_receivers(js))


def _chart_assigns_instance(js):
    return any(re.search(r"%s\s*(?:\.\s*chart|\[\s*['\"]chart['\"]\s*\])\s*=(?!=)"
                         % re.escape(rx), js)
               for rx in _chart_receivers(js))


def _check_filter_form_layout(p, r):
    """A filter bar's fields need a LAYOUT, or they stack down the page one per line.

    The shape the platform expects is in 04-crud-table-plugin.md: inside the form's
    `nct.parsis.plugin identifier="filter.parsis"` goes an `nct.html.plugin` whose markup is a
    row of column cells, each holding a `<plugin id="…" name="nct.parsis.plugin">` that the field
    nodes hang off::

        <div class="row"><div class="col-md-4"><plugin id="first" name="nct.parsis.plugin"></plugin></div>…

    Without it every control is a full-width block: a five-field filter becomes five stacked rows above
    the table, and the screen reads as unfinished. Nothing else notices — the form is well-formed, the
    fields bind, the filter works. It is only ugly, and ugly is not something the other gates can see.

    WARN, not ERROR: a single-field filter legitimately needs no grid, and this is a presentation
    decision the author is allowed to make deliberately."""
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.filter.form.plugin":
            continue
        anchor_node = next((c for c in node.get("children") or []
                            if c.get("pluginName") == "nct.parsis.plugin"
                            and c.get("identifier") == "filter.parsis"), None)
        if anchor_node is None:
            continue          # a missing anchor is a different, louder problem
        children = list(anchor_node.get("children") or [])
        if any(c.get("pluginName") in ("nct.html.plugin", "html.plugin") for c in children):
            continue
        # ⛔ FIELD controls only. A submit button, a label or a table sitting in the same anchor is
        # not a field, and counting it both defeats the single-field exemption (one control beside a
        # button looked like two) and printed a count the author cannot reconcile with the screen.
        fields = [c for c in children
                  if str(c.get("pluginName") or "").startswith("dynaform.form.")
                  and c.get("pluginName") != "dynaform.filter.submit.button.plugin"]
        if len(fields) < 2:
            continue          # one control needs no grid
        r.warn("filter form %r puts its %d controls straight into `filter.parsis` with no layout — "
               "each renders full width, so the bar is one stacked row per field. Wrap them in an "
               "`nct.html.plugin` row of `col-*` cells, one `<plugin id=… name=\"nct.parsis.plugin\">` "
               "per cell (04-crud-table-plugin.md)." % (node.get("name"), len(fields)))


_COL_RE = re.compile(r"\bcol-(?:xs|sm|md|lg|xl|xxl)-(\d{1,2})\b")


_CHART_CONSTRUCTORS = ("new Chart(", "Plotly.newPlot(", "Plotly.react(", "echarts.init(",
                       "mermaid.init(", "mermaid.run(")


def _draws_a_chart(js):
    """⛔ A `chart.js.plugin` node is not necessarily a chart.

    The plugin is also the platform's general-purpose HTML+JS widget, and real projects use it for
    collapsible panels, banners and other decoration that draws nothing. Counting those toward a
    dashboard makes every count wrong — and makes the shape census report a page of accordions as
    "one chart shape". Only a node that actually CONSTRUCTS something is a chart."""
    return any(c in (js or "") for c in _CHART_CONSTRUCTORS)


def _chart_shape(js):
    """The visual FAMILY of a chart script — what the reader sees, not which library drew it."""
    t = (js or "")
    low = t.lower()
    if "type:'indicator'" in t.replace(" ", "") or '"indicator"' in t:
        return "gauge" if "gauge" in low else "indicator"
    m = re.search(r"type\s*:\s*['\"](\w+)['\"]", t)
    base = (m.group(1).lower() if m else "")
    if base in ("doughnut", "pie", "polararea", "radar", "scatter", "bubble", "line"):
        return base
    if base == "bar":
        if re.search(r"type\s*:\s*['\"]line['\"]", t[t.find("datasets"):] if "datasets" in t else ""):
            return "combo"
        if "stacked:true" in t.replace(" ", ""):
            return "stacked-bar"
        if re.search(r"indexAxis\s*:\s*['\"]y['\"]", t):
            return "hbar"
        return "bar"
    if "mermaid" in low:
        return "diagram"
    if "plotly" in low:
        return "plotly-" + (base or "other")
    return base or "other"


_HEX_ARRAY_RE = re.compile(
    r"(background|border|hover(?:Background|Border))Color\s*:\s*\[\s*"
    r"((?:['\"]#[0-9A-Fa-f]{3,8}['\"]\s*,\s*){1,}['\"]#[0-9A-Fa-f]{3,8}['\"])\s*,?\s*\]",
    re.I)


def _check_chart_colour_by_index(p, r):
    """A colour array assigns BY POSITION, so the mapping rides on the query's row order.

    `backgroundColor:['#8b1a2b','#22a7f0','#63bff0',…]` looks deliberate and is not: the third slice is that
    blue only while the third row is what it was when the author looked. Re-order the SQL, add a category,
    or — the case that bites hardest — click a cross-filter, which RE-RUNS every query on the board, and the
    survivors are repainted. The shipped defect doc 22 §6.1 opens with came from exactly this: HIGH landed on
    dark red while MEDIUM and LOW landed on two blues, so a risk chart no longer read as a risk chart.

    Map from the LABEL instead — `var C={'HIGH':'#e0483a',…}; labels.map(l => C[l] || '#9aa2ad')` — which is
    stable under any order and makes an unknown value show up as a grey build alarm.

    WARN: a single-series chart whose slice order is genuinely fixed can use an array and be right. It is the
    one colour failure a file can see at all — the rest of §2B.6 (is the family right for this axis? is the
    same measure the same colour across the board?) needs eyes. (22-charts-params-and-filters.md §6.1, §2B.6)"""
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "chart.js.plugin":
            continue
        raw = _prop_string_value(node, "Javascript") or _prop_string_value(node, "model") or ""
        if not raw.strip().startswith("{"):
            continue
        try:
            js = json.loads(raw).get("js") or ""
        except Exception:
            continue
        if not _draws_a_chart(js):
            continue
        m = _HEX_ARRAY_RE.search(js)
        if not m:
            continue
        n_colours = m.group(2).count("#")
        if n_colours < 3:
            continue          # two fixed series (e.g. a stacked pair) is a deliberate, stable choice
        r.warn("chart %r paints %d colours from an INDEX array (%sColor:[…]) — the mapping rides on the "
               "query's row order, so adding a category or clicking a cross-filter repaints the survivors. "
               "Map by label: `var C={'<VALUE>':'#..',…}; labels.map(function(l){return C[l]||'#9aa2ad';})`. "
               "(22-charts-params-and-filters.md §6.1)"
               % (node.get("name") or node.get("identifier"), n_colours, m.group(1)))


def _check_dashboard_composition(p, r):
    """A dashboard is COMPOSED. A GRID DUMP passes every other gate and is still a defect.

    Judged PER PAGE, because a dashboard is a page — a project's chart count summed over three screens says
    nothing about any of them. For each page carrying enough charts to be a board, three things a file CAN
    see: no big-number tile anywhere on it, one chart shape answering every question, and a grid whose every
    cell is the same width. Those are the three that separated the two builds doc 22 §2B compares. The rest
    of that page — its title, its humanised labels, its integer ticks — is visible only on screen, which is
    why §2B.6 ends with "would you put this screenshot in a proposal?".

    WARN throughout: a deliberately austere board is a defence, and a file cannot hear it.
    (22-charts-params-and-filters.md §2B)"""

    def pages(node, page=None):
        if node.get("pluginName") == "siteMapPage":
            page = node
        yield node, page
        for c in node.get("children") or []:
            yield from pages(c, page)

    charts_by_page, widths_by_page = {}, {}
    for node, page in pages(p.root_content):
        if page is None:
            continue
        key = id(page)
        if node.get("pluginName") == "chart.js.plugin":
            raw = _prop_string_value(node, "Javascript") or _prop_string_value(node, "model") or ""
            if not raw.strip().startswith("{"):
                continue
            try:
                js = json.loads(raw).get("js") or ""
            except Exception:
                continue
            if not _draws_a_chart(js):
                continue          # a decoration node, not a chart — see _draws_a_chart
            charts_by_page.setdefault(key, (page, []))[1].append((node, js))
        elif node.get("pluginName") in ("nct.html.plugin", "html.plugin"):
            html = _prop_string_value(node, "html") or _prop_string_value(node, "Html") or ""
            if "nct.parsis.plugin" in html:
                widths_by_page.setdefault(key, []).extend(
                    w for w in _COL_RE.findall(html) if w != "12")

    for key, (page, charts) in charts_by_page.items():
        if len(charts) < 4:
            continue                 # not a board; nothing to compose
        label = page.get("alias") or page.get("name") or "?"

        shapes, has_number = set(), False
        for _n, js in charts:
            shape = _chart_shape(js)
            shapes.add(shape)
            if shape in ("indicator", "gauge"):
                has_number = True

        if shapes and len(shapes) < 3:
            r.warn("page %r: %d charts, %d chart shape(s) (%s) — one shape answering every question reads as "
                   "a report dump, not a board. Doc 22 §2B.6 asks for at least four: an indicator or gauge, a "
                   "doughnut, a ranked horizontal bar, and a combo or stacked bar."
                   % (label, len(charts), len(shapes), ", ".join(sorted(shapes))))

        if not has_number:
            r.warn("page %r has %d charts and no KPI tile — no big number, no gauge. The figures the audience "
                   "came for are buried inside charts. Open with a strip of 3-5 `indicator` tiles, at least "
                   "one of them a gauge (22-charts-params-and-filters.md §2B.4a/b)." % (label, len(charts)))

        # ⛔ Judged over the whole PAGE, never row by row. An even row is fine and common — a KPI strip IS
        # 4x col-3 and a three-chart section IS 3x col-4. What no laid-out board has is ONE width used
        # everywhere: that is the loop's signature, and on the build this was written from it was col-6
        # from the top of the page to the bottom.
        cells = widths_by_page.get(key) or []
        if len(cells) >= 4 and len(set(cells)) == 1:
            r.warn("page %r: every laid-out cell is the same width (col-*-%s, %d cells) — one column width "
                   "for a whole board is what a loop produces, not a layout. Width follows the chart's "
                   "shape: a time series earns col-xl-8, the ranked bar beside it col-xl-4, a KPI tile "
                   "col-xl-3 (22-charts-params-and-filters.md §2B.2)." % (label, cells[0], len(cells)))


def _check_dashboard_layout(p, r):
    """Charts dropped straight onto a page with no layout read as a wall, not as a dashboard.

    A page carrying several `chart.js.plugin` nodes as direct siblings inside one parsis renders them
    stacked at full width, edge to edge, with no card, no section heading and no row — which is what a
    dashboard looks like when nobody laid it out. The composition the platform's own screens use is an
    `nct.html.plugin` per section, with `main-card` / `card-header` / `card-body` and a `row` of `col-*`
    cells, each cell a `<plugin name="nct.parsis.plugin">` a chart hangs off
    (24b-html-composition-and-plugin-tags.md, 22-charts-params-and-filters.md).

    ERROR on the ROOT page, WARN anywhere else. The root is the front door — the first screen anyone
    opens, and the one a customer judges the whole delivery by; doc 21 spells its shape out. A child
    page may legitimately be plain, and the shipped baseline has one that is."""
    # ⛔ The front door is what the bare project URL RESOLVES to, not the root node. Doc 21 gives two
    # shapes and they are equally recommended: Home carries the dashboard itself, or Home carries
    # `Redirect=<alias>` and the dashboard lives on that page. Judging by tree position alone let the
    # second shape — the one a project is just as likely to take — past the gate entirely.
    from . import content_cmds          # local: the module-level namespace does not carry it

    front_doors = [p.root_content]
    redirect = (_prop_string_value(p.root_content, "Redirect") or "").strip()
    if redirect:
        target = content_cmds.resolve_alias_path(p.root_content, redirect.lstrip("/"))
        if target is not None:
            front_doors.append(target)

    def _page_own_content(page):
        """Every node belonging to THIS page — its own subtree, minus any nested page."""
        own, stack = set(), [page]
        while stack:
            n = stack.pop()
            own.add(id(n))
            for c in n.get("children") or []:
                if c.get("pluginName") == "siteMapPage":
                    continue
                stack.append(c)
        return own

    front_door_nodes = set()
    for page in front_doors:
        front_door_nodes |= _page_own_content(page)

    def _inside_root_page(target):
        """True when the node belongs to a FRONT-DOOR page's own content."""
        return id(target) in front_door_nodes

    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") not in ("nct.parsis.plugin", "parsis.plugin"):
            continue
        charts = [c for c in node.get("children") or []
                  if c.get("pluginName") == "chart.js.plugin"]
        if len(charts) < 3:
            continue
        message = ("%d charts hang directly off parsis %r with no layout between them — they render "
                   "stacked at full width, with no card, heading or row. Compose them the way "
                   "21-homepage-and-redirect.md §Home-as-dashboard describes: a header "
                   "`nct.html.plugin`, then grid-row `nct.html.plugin` nodes whose markup is a row of "
                   "`<div class=\"col-md-N\"><plugin id=… name=\"nct.parsis.plugin\"></plugin></div>` "
                   "cells, one chart per cell." % (len(charts), node.get("identifier")))
        if _inside_root_page(node):
            r.err("THE FRONT DOOR: " + message)
        else:
            r.warn(message)


def _check_chart_js_contract(p, r):
    """A Chart.js script must reach its canvas through {@code this.$find('canvas')[0]} and assign the
    instance to {@code this.chart}.

    Neither is decoration. The chart script is evaluated with `this` bound to the plugin — `$find` is
    how it is given its own DOM, and there is no `element` (or `document`-wide search) it may rely on.
    A script that reaches for anything else throws BEFORE `new Chart` is ever called, so the box renders
    empty — with the replacement queries returning data perfectly well, which is what makes it so hard
    to place: every offline gate is green, the query editor shows rows, and the dashboard is blank.

    And the redraw path calls `.destroy()` on `this.chart`; an unassigned instance leaks a canvas on
    every re-render and eventually the chart stops updating.

    ERROR, because a chart that never constructs is indistinguishable from one with no data. Every
    reference export satisfies both — this is the shape the platform's own templates use.
    (22-charts-params-and-filters.md)"""
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "chart.js.plugin":
            continue
        raw = _prop_string_value(node, "Javascript") or _prop_string_value(node, "model") or ""
        if not raw.strip().startswith("{"):
            continue
        try:
            js = (json.loads(raw).get("js") or "")
        except Exception:
            continue
        if "new Chart(" not in js:
            continue          # not a Chart.js chart (Plotly, mermaid, a hand-drawn gauge)
        label = node.get("name") or node.get("identifier")
        if not _chart_reaches_canvas(js):
            r.err("chart %r does not reach its canvas with `this.$find('canvas')[0]` — the script is "
                  "evaluated with `this` bound to the plugin and is given no other handle on its own "
                  "DOM, so it throws before `new Chart` runs and the chart renders EMPTY while its "
                  "queries return data. (22-charts-params-and-filters.md)" % label)
        if not _chart_assigns_instance(js):
            r.err("chart %r never assigns `this.chart` — the redraw path calls `.destroy()` on it, so "
                  "the instance leaks a canvas on every re-render and the chart stops updating. "
                  "(22-charts-params-and-filters.md)" % label)


def _check_query_placeholder_shape(p, r):
    """A CHART query's `{name:…}` placeholder must be a BARE right-hand operand — never wrapped.

    A chart runs with its filters EMPTY by default, and an unsupplied placeholder is not bound to
    null: it is NEUTRALISED. The engine walks back to the nearest WHERE/AND/OR/HAVING/ON, blanks every
    token from there to the placeholder and writes `1=1` — leaving everything AFTER the placeholder
    dangling. So a hand-written "empty means all" guard like

        AND ({name:'since'} = '' OR d.dt >= CAST({name:'since'} AS date))

    ships as `AND 1=1 = '' OR 1=1 AS date ) )` on the very first render, and every chart on the page
    shows an error toast. The authored SQL is valid SQL, which is why nothing else offline sees it.

    Write `<column> <operator> {name: …}` and nothing else — no CAST, no COALESCE, no extra parens, no
    self-authored guard: an unsupplied placeholder ALREADY means "no filter". A period filter has to
    be a `dropdown-string` over a lookup query, or be left out (22-charts-params-and-filters.md).

    Scope is deliberately CHART queries only. An autocomplete or picker query is wrapped the same way
    on purpose and always has a value — the platform's own baseline ships three of them."""
    for label, sql in _chart_query_sources(p):
        placeholders = list(_query_placeholders(sql))
        if not placeholders:
            continue
        dangling = _dangling_placeholder_spans(sql)
        if dangling:
            ph, span = dangling[0]
            r.err("%s wraps a {name:…} placeholder (in CAST/COALESCE/parentheses). A chart renders with "
                  "its filters EMPTY, and an empty placeholder is neutralised to `1=1` with everything "
                  "back to the nearest WHERE/AND/OR blanked — the `(` opened in `%s` loses its opener "
                  "and the statement stops parsing. Write `<column> <operator> %s` and nothing else. "
                  "(22-charts-params-and-filters.md)" % (label, span, ph[:40]))
            continue
        for _text, _start, end in placeholders:
            tail = sql[end:end + 4].lstrip()
            if tail[:2] in ("<=", ">=", "<>", "!=") or tail[:1] in ("=", "<", ">"):
                r.err("%s puts a {name:…} placeholder on the LEFT of a comparison. Empty, it becomes "
                      "`1=1 %s…`, which does not parse. The placeholder is only ever the right-hand "
                      "operand. (22-charts-params-and-filters.md)" % (label, tail[:2].strip()))
                break


def _check_autofind_needs_count(p, r):
    """An auto-paged `find` (GROOVY, no `ruleIdentifier`) without a sibling `count` makes the pager lie.

    The wrapper calls `findAll`, then `count` for the total — and when there is no `count` method it
    falls back to `rows.size()`. The total then equals the size of the CURRENT page, so `totalPages`
    computes to 1 and the table shows one page of results however many rows the table really holds.
    Nothing errors, and on a small demo data set it even looks right."""
    _, cruds = _dynamic_crud_methods(p)
    for c in cruds:
        names = {m.get("methodName"): m for m in (c.get("methods") or []) if isinstance(m, dict)}
        find = names.get("find")
        if not find or find.get("methodType") != "GROOVY":
            continue
        if (find.get("ruleIdentifier") or "").strip():
            continue  # a real hidden rule — it decides its own totals
        if "findAll" in names and "count" not in names:
            r.warn("dynamic CRUD %r has an auto-paged 'find' and a 'findAll' but NO 'count' — the wrapper "
                   "falls back to the page size for totalElements, so the pager reports one page no matter "
                   "how many rows exist. Add the sibling count method. "
                   "(11-business-logic-dynamic-crud.md)" % c.get("alias"))


def _check_single_slot_map_calls(p, r):
    """A Map argument must never meet a SQL method whose parameter list is a SINGLE slot the map does
    not name.

    When a caller passes one Map, the executor unpacks it by parameter name — always with two or more
    declared parameters, but with EXACTLY ONE only if the map actually mentions that parameter. If it
    does not, the call falls back to POSITIONAL binding and the whole serialized map is bound into
    that one slot.

    This is the default shape of `count` on a table with exactly one filter: `count`'s parameter list
    is `findAll`'s minus the paging keys, and the auto-paged `find` calls `count` with the SAME
    argument map as `findAll`. A user who has typed nothing into the filter bar therefore sends
    `{"rowsInPage":20,"pageNumber":0}` and the map never mentions the filter. On a scalar column the
    request dies — `invalid input syntax for type boolean: "{"rowsInPage":20,…}"`. On a text column
    nothing errors at all: the comparison runs against that JSON text, matches nothing, and the screen
    shows an empty list — indistinguishable from "there is no data yet".

    The fix is on the caller side: seed the map with EVERY declared filter key, `null` where the user
    supplied nothing. A null means "no filter" to the usual `IS NULL OR` guard, so naming the key
    changes no result and removes the fallback. Seeding inside a conditional does NOT count — a scope
    block that runs only for non-privileged users leaves the key absent for everyone else."""
    _, cruds = _dynamic_crud_methods(p)
    if not cruds:
        return
    declared = {}
    for c in cruds:
        for m in c.get("methods", []) or []:
            declared[(c.get("alias"), m.get("methodName"))] = (
                m.get("methodType"),
                [(x.get("parameterName"), x.get("parameterType"))
                 for x in (m.get("parameters") or []) if isinstance(x, dict)])

    sources = []
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule")
        if isinstance(rr, dict):
            sources.append(("rule %r" % rule.get("name"), rr.get("ruleScriptStr", "") or ""))
    for c in cruds:
        for m in c.get("methods", []) or []:
            if m.get("methodType") == "GROOVY" and m.get("script"):
                sources.append(("crud %r method %r" % (c.get("alias"), m.get("methodName")),
                                m.get("script") or ""))

    seen = set()
    for label, body in sources:
        for hit in _CRUD_CALL_RE.finditer(body):
            alias, method = hit.group(1), hit.group(2)
            arg = _balanced_call_arg(body, hit.end())
            if not arg:
                continue
            keys = _known_map_keys(arg, body)
            if keys is None:
                continue
            # the auto-paged `find` fans out to findAll AND count with the same argument
            targets = [(alias, "findAll"), (alias, "count")] if method == "find" else [(alias, method)]
            for target in targets:
                info = declared.get(target)
                if not info:
                    continue
                mtype, plist = info
                if mtype != "SQL" or len(plist) != 1:
                    continue
                slot, ptype = plist[0]
                if not slot:
                    continue
                # The executor accepts the slot under several spellings: the name itself, its
                # camelCase form, the ROOT of a `<ref>__id` join path (the caller sends {ref:{id:…}}),
                # and the canonical localization key. Matching only the literal name reports correct
                # code as broken.
                accepted = {slot, _to_camel_case(slot)}
                if "__" in slot:
                    accepted.add(slot.split("__", 1)[0])
                    accepted.add(_to_camel_case(slot.split("__", 1)[0]))
                accepted.add(LOCALIZATION_CANONICAL_KEY)
                if accepted & keys:
                    continue
                key = (label, target, slot)
                if key in seen:
                    continue
                seen.add(key)
                scalar = (ptype or "").strip().lower() in _SCALAR_PARAM_TYPES
                where = ("via the auto-paged find" if method == "find" else "directly")
                if scalar:
                    r.err("%s calls service.crud.%s.%s(...) %s with a map that never names its ONLY "
                          "parameter %r (%s) — the executor binds the whole serialized map into that "
                          "slot and PostgreSQL answers `invalid input syntax for type %s`. Seed the key "
                          "in the map literal with null. (11-business-logic-dynamic-crud.md)"
                          % (label, target[0], target[1], where, slot, ptype,
                             (ptype or "?").lower()))
                else:
                    r.warn("%s calls service.crud.%s.%s(...) %s with a map that never names its ONLY "
                          "parameter %r (%s) — the executor binds the whole serialized map into that "
                          "slot. On a text column this does not error: the comparison matches nothing "
                          "and the screen shows an empty list. Seed the key in the map literal with "
                          "null. (11-business-logic-dynamic-crud.md)"
                          % (label, target[0], target[1], where, slot, ptype))


# The `fontName` values the PDF renderer has: the selectable families of the platform's font set, each in four
# styles ("" is the default, Roboto). A snapshot of the platform's font manifest -- when the platform adds a family,
# add it here and in 15-pdf-and-mail.md.
_PDF_FONT_FAMILIES = ("Roboto", "Noto Sans", "Noto Serif")
_PDF_FONT_STYLES = ("", " Bold", " Italic", " Bold Italic")
PDF_FONT_NAMES = frozenset(family + style for family in _PDF_FONT_FAMILIES for style in _PDF_FONT_STYLES)


def _pdf_template_font_names(templateJson):
    """Every font name a pdfme template asks for, the way the renderer reads a template: in each schema of every page and
    in the static schemas of the base PDF, each `fontName` wherever it sits in the schema (a field, a `table`'s
    headStyles / bodyStyles / columnStyles); and, in an inline-markdown field only, the faces of `fontVariants` -- the
    bold and italic faces that `**bold**` draws with. A `fontName` anywhere else in the JSON is not read by the
    renderer, and neither is `fontVariants` of a field that is not inline markdown. A name that is not text (a number,
    an object) is no font either: it is returned as its JSON text. `null` is no name."""
    try:
        node = json.loads(templateJson) if isinstance(templateJson, str) else templateJson
    except (ValueError, RecursionError):
        # not JSON at all (or nested deeper than the parser reads): read the text the way the check always did
        return set(re.findall(r'"fontName"\s*:\s*"([^"]*)"', templateJson))
    if not isinstance(node, dict):
        return set()
    schemas = []
    pages = node.get("schemas")
    for page in pages if isinstance(pages, list) else []:
        schemas.extend(page if isinstance(page, list) else [page])
    base = node.get("basePdf")
    if isinstance(base, dict) and isinstance(base.get("staticSchema"), list):
        schemas.extend(base["staticSchema"])

    def text_of(value):
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    names = set()
    for schema in (s for s in schemas if isinstance(s, dict)):
        pending = [schema]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "fontName" and child is not None:
                        names.add(text_of(child))
                    elif isinstance(child, (dict, list)):
                        pending.append(child)
            elif isinstance(value, list):
                pending.extend(child for child in value if isinstance(child, (dict, list)))
        variants = schema.get("fontVariants")
        if schema.get("textFormat") == "inline-markdown" and isinstance(variants, dict):
            # (a variant is named when it is truthy the way the renderer's JavaScript reads it: an empty list or object is a name that no font has)
            names.update(text_of(variants[style]) for style in ("bold", "italic", "boldItalic") if style in variants and not (variants[style] in (None, "", False, 0) and not isinstance(variants[style], (list, dict))))
    return names


def _shown_name(name, limit=80):
    """A font name for a message: quoted, so that one with a space at its end can be seen, and cut when it is long."""
    text = repr(name)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _check_pdf_template_fonts(p, r):
    """A pdfme template should name a font the RENDERER has: one of PDF_FONT_NAMES, or "" for the default.

    A name the renderer does not have used to fail the WHOLE render (422 `[@pdfme/schemas] Font "<name>" is not
    found.`, no PDF at all). It no longer does: the field is drawn in the default font and the render log says
    `UNKNOWN_FONT` with the alias, the field and the name. That is still a template that does not look the way its
    author designed it, hence a WARN -- and the commonest cause is a template exported from pdfme's own online
    playground, which writes `NotoSerifJP-Regular` / `NotoSerifJP-Bold` into every text field. (A deployment can
    switch on a strict mode in which an unknown name fails the render again.)

    This also covers `headStyles` / `bodyStyles` / `columnStyles` inside a `table` schema, which carry their own
    `fontName` and are the half people forget, and `fontVariants` (the faces inline markdown uses). It reads a template
    the way the renderer does (see _pdf_template_font_names): what the renderer ignores is not warned about.
    """
    for tpl in _list_of(p.rep, "pdfTemplates"):
        raw = tpl.get("templateJson") if isinstance(tpl, dict) else None
        if not raw:
            continue
        names = sorted(n for n in _pdf_template_font_names(raw) if n and n not in PDF_FONT_NAMES)
        if names:
            # (a template can name any number of fonts, of any length)
            shown = ", ".join(_shown_name(n) for n in names[:20]) + (" (and %d more)" % (len(names) - 20) if len(names) > 20 else "")
            r.warn("pdfTemplate %r names font(s) %s -- not in the renderer's font set (%s). Each such field prints "
                   "in the default font (Roboto) and the render logs UNKNOWN_FONT. Use one of those names, or "
                   "\"\" for the default; a template exported from pdfme's own playground carries "
                   "NotoSerifJP-* -- clear them. (15)"
                   % (tpl.get("alias") or tpl.get("name"), shown, ", ".join(sorted(PDF_FONT_NAMES))))


def _check_groovy_numeric_traps(p, r):
    """Four ways a Groovy rule that does arithmetic dies at runtime while every offline gate stays green.

    All four are invisible in review because the failing expression READS correctly, and three of them
    surface to the user as the literal text "null" on a platform build that predates the unwrapping fix —
    the nested-rule call went through a reflective invocation and reported the wrapper
    exception's message, which is always null, so the message a user got for ANY failure inside
    a nested rule was `Failed to execute rule '<name>': null` (a current build says what the nested rule threw, except
    for an exception that carries no message of its own). There is nothing to grep for. Hence this check.

    1. **`0G` is a BigInteger literal, `0.0G` a BigDecimal one.** ⇒ ERROR when the body does decimal work.
       `if (q < 0G) { q = 0G }` silently retypes `q`, and the next `q.setScale(2, HALF_UP)` throws
       `MissingMethodException: java.math.BigInteger.setScale()`. It only fires on the branch that clamps —
       so a two-row fixture never reaches it and a real catalogue does.

    2. **`new BigDecimal(<runtime value>)`** ⇒ WARN. `new BigDecimal("")` is the only NumberFormatException
       in the numeric surface whose `getMessage()` is null. Context attributes and workflow variables are
       empty strings far more often than they are absent.

    3. **`(x ?: 0) as BigDecimal`** ⇒ WARN. Elvis catches `''` (falsy) but NOT `' '` (a truthy
       whitespace-only string), and `' ' as BigDecimal` throws the same null-message exception.

    4. **`.divide(y)` with one argument** ⇒ WARN. Non-terminating decimal expansion throws
       ArithmeticException; a scale and a RoundingMode are not optional in money code.

    The fix for 2 and 3 is one helper the rule defines once and uses everywhere — see
    08-groovy-rules-and-context.md "Numbers in a rule". Comments and string literals are stripped before
    matching, so a doc comment that quotes the wrong form is never reported.
    """
    bigint = re.compile(r"(?<![\w.])\d+G(?![\w])")
    decimal_work = re.compile(r"BigDecimal|setScale|\.multiply\(|\.divide\(")
    new_bd = re.compile(r"new BigDecimal\(\s*(?![\"'])")
    elvis_bd = re.compile(r"\?\:\s*0\s*\)?\s*as BigDecimal")
    div_bare = re.compile(r"\.divide\(\s*[^,()]+\s*\)")

    def _code_only(src):
        """Strip // and /* */ comments and string literals — a quoted example is not code."""
        src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
        src = re.sub(r"//[^\n]*", " ", src)
        src = re.sub(r"'''.*?'''|\"\"\".*?\"\"\"", " ", src, flags=re.S)
        src = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", " ", src)
        return src

    bodies = []
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule")
        if isinstance(rr, dict) and rr.get("ruleScriptStr"):
            bodies.append(("rule %r" % rule.get("name"), rr["ruleScriptStr"]))
    _by_alias, _cruds = _dynamic_crud_methods(p)
    for crud in _cruds:
        for m in crud.get("methods", []) or []:
            if m.get("methodType") == "GROOVY" and m.get("script"):
                bodies.append(("crud %r method %r" % (crud.get("alias"), m.get("methodName")),
                               m["script"]))

    for where, body in bodies:
        code = _code_only(body)
        hits = bigint.findall(code)
        if hits and decimal_work.search(code):
            r.err("%s uses the BigInteger literal(s) %s in decimal code — Groovy's `<n>G` is a BigInteger "
                  "and `<n>.0G` a BigDecimal, so a value clamped to `0G` throws "
                  "MissingMethodException on the next .setScale()/.multiply(). Write `0.0G`. (08)"
                  % (where, ", ".join(sorted(set(hits)))))
        if new_bd.search(_outside_coercion_helper(code)):
            r.warn("%s builds a BigDecimal from a runtime value — `new BigDecimal('')` throws a "
                   "NumberFormatException with a NULL message, which reaches the user as the bare word "
                   "\"null\". Coerce through a helper that trims and defaults instead. (08)" % where)
        if elvis_bd.search(code):
            r.warn("%s uses `(x ?: 0) as BigDecimal` — Elvis catches '' but not a whitespace-only ' ', "
                   "which then throws the same null-message NumberFormatException. (08)" % where)
        if div_bare.search(code):
            r.warn("%s calls .divide() with one argument — a non-terminating decimal expansion throws "
                   "ArithmeticException; pass a scale and a RoundingMode. (08)" % where)

# An UPDATE that marks a row instead of deleting it — the shape every soft delete takes.
_SOFT_DELETE_RE = re.compile(
    r"\bUPDATE\b[\s\S]{0,200}?\bSET\b[\s\S]{0,120}?\b(?:deleted|is_deleted|archived|deleted_at)\b\s*=",
    re.I)


# A key that names a REFERENCE — the only kind whose value can be a Jackson object
# node, and therefore the only kind an Elvis chain silently discards.
_REF_KEY_RE = re.compile(r"(?:^|[a-z])(?:[Ii]d|__id|[Rr]ef)$")


def _check_groovy_jsonnode_truth(p, r):
    """`?:` over a payload key — the chain that silently throws a good FK away.

    Groovy decides the truth of an object by calling its own `asBoolean()`, and Jackson's
    `JsonNode.asBoolean()` answers **false** for every node that is not a boolean node. So a
    `TextNode` holding a uuid, an `ObjectNode` holding `{"id": "..."}` and an `ArrayNode`
    holding ten rows are ALL falsy. Measured on a live tenant:

        def n = new ObjectMapper().readTree('{"id":"abc"}')
        (n ? 'T' : 'F')        // F
        (n ?: 'FELLTHROUGH')   // FELLTHROUGH
        n.get('id').asText()   // abc

    Therefore `_id(row['item'] ?: row['item__id'] ?: row['itemId'])` discards the value that IS
    there, walks on to two absent keys and yields null — and the INSERT writes NULL into the FK.
    Inside the try/catch that wraps a line loop the user sees a green "saved", the header lands,
    and every line is gone with no message anywhere.

    It bites NESTED rows first: the executor converts top-level textual/number/boolean parameters
    to plain Java values, so header fields arrive as String and behave, while elements of a
    `lines` array arrive as raw nodes. A document whose header saves while its lines vanish is
    this bug, every time.

    ERROR on a same-variable candidate chain (`x['a'] ?: x['b']`) — that shape has no innocent
    reading. WARN on a lone `<payload var>['k'] ?: <default>`, the same trap wherever the key can
    carry an object or a reference.

    Fix — walk the candidates without asking a node for its truth:

        def _pick = { m, List ks ->
            for (k in ks) { if (m.containsKey(k)) { def v = _id(m[k]); if (v != null) { return v } } }
            return null }

    (11-business-logic-dynamic-crud.md, "Document CRUD variant")
    """
    PAYLOAD_VARS = ("param", "params", "src", "row", "ln", "line", "payload", "attrs", "hdr", "dto")
    chain = re.compile(r"(\w+)\[\s*'([^']+)'\s*\]\s*\?:\s*\1\[\s*'([^']+)'\s*\]")
    lone = re.compile(r"\b(%s)\[\s*'([^']+)'\s*\]\s*\?:" % "|".join(PAYLOAD_VARS))

    def _code_only(src):
        src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
        src = re.sub(r"//[^\n]*", " ", src)
        return src

    bodies = []
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule")
        if isinstance(rr, dict) and rr.get("ruleScriptStr"):
            bodies.append(("rule %r" % rule.get("name"), rr["ruleScriptStr"]))
    _by_alias, _cruds = _dynamic_crud_methods(p)
    for crud in _cruds:
        for m in crud.get("methods", []) or []:
            if m.get("methodType") == "GROOVY" and m.get("script"):
                bodies.append(("crud %r method %r" % (crud.get("alias"), m.get("methodName")),
                               m["script"]))

    for where, body in bodies:
        code = _code_only(body)
        # Only a CRUD delegate body sees raw Jackson nodes: `param` is bound by
        # GroovyExecutionRule, and it converts ONLY top-level textual/number/boolean values.
        # A map that came back from `service.crud.*` — or a form's context data — holds plain
        # Java values, and Elvis over it is harmless. So the ERROR is scoped to delegate
        # bodies; everywhere else the same shape is worth a look, not a failed gate.
        is_delegate = re.search(r"\bparam\b", code) is not None
        seen = set()
        for var, a, b in chain.findall(code):
            if (var, a, b) in seen:
                continue
            seen.add((var, a, b))
            if is_delegate and var in PAYLOAD_VARS:
                r.err("%s chains payload keys with Elvis: `%s['%s'] ?: %s['%s']`. Every Jackson "
                      "node is FALSY in Groovy (JsonNode.asBoolean() answers for it), so a "
                      "present {id: ...} is thrown away and the FK lands NULL — the header saves "
                      "and the lines vanish with no message. Walk the candidates instead: "
                      "`_pick(%s, ['%s', '%s'])`. (11)" % (where, var, a, var, b, var, a, b))
            elif _REF_KEY_RE.search(a) or _REF_KEY_RE.search(b):
                r.warn("%s chains keys with Elvis: `%s['%s'] ?: %s['%s']`. Harmless while %r holds "
                       "plain Java values; fatal the moment it holds a Jackson node, because every "
                       "node is falsy in Groovy. Test `!= null` if it can. (11)"
                       % (where, var, a, var, b, var))
        if is_delegate:
            for var, key in sorted(set(lone.findall(code))):
                if (var, key) in {(v, a) for v, a, _b in seen}:
                    continue
                # Only REFERENCE keys are worth a line: a scalar column (lineNumber, status,
                # docNo) arrives as a plain Java value and Elvis over it behaves.
                if not _REF_KEY_RE.search(key):
                    continue
                r.warn("%s writes `%s['%s'] ?: ...` — that key names a reference, and a Jackson "
                       "node is falsy in Groovy, so the default ALWAYS wins. Test `!= null`. (11)"
                       % (where, var, key))


def _check_crud_method_refs(p, r):
    """Every `service.crud.<alias>.<method>(...)` call in a rule body or a GROOVY method script must
    resolve to a REAL method on that dynamic CRUD (its registered methods + the 7 defaults) — a missing
    method throws a runtime `MissingMethodException` when the rule/method runs. The exact 2026-07-27 bug:
    a searchable-dropdown rule called `service.crud.segmentNode.acFindByNameLike(...)` before the
    `acFindAllByNameLike` SQL + `acFindByNameLike` Groovy pipeline was generated, so the picker just showed
    "No results". Search-pipeline `acFind…Like` methods are **ERRORs** (they are always wired to a live
    dropdown → a blank picker); any other missing method is a **WARN** (author typo / a to-be-added method).
    STATIC cruds (no `dynamic-cruds.json` entry) are skipped — their methods are compiled Java, not listed."""
    methods_by_alias, cruds = _dynamic_crud_methods(p)
    if not methods_by_alias:
        return
    sources = []
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule")
        if isinstance(rr, dict):
            sources.append(("rule %r" % rule.get("name"), rr.get("ruleScriptStr", "") or ""))
    for c in cruds:
        for m in c.get("methods", []) or []:
            if m.get("methodType") == "GROOVY" and m.get("script"):
                sources.append(("crud %r method %r" % (c.get("alias"), m.get("methodName")), m.get("script") or ""))
    for label, body in sources:
        seen = set()
        for mt in _CRUD_CALL_RE.finditer(body):
            alias, method = mt.group(1), mt.group(2)
            if alias not in methods_by_alias:
                continue  # static / unknown crud — not enumerable here
            if method in methods_by_alias[alias] or method in _DEFAULT_CRUD_METHODS:
                continue
            if (alias, method) in seen:
                continue
            seen.add((alias, method))
            if _AC_METHOD_RE.match(method):
                r.err("%s calls service.crud.%s.%s() but that CRUD has no such method — the searchable-dropdown "
                      "pipeline (acFindAllBy<X>Like SQL + acFindBy<X>Like Groovy wrapper) was NOT generated. Runtime "
                      "MissingMethodException → the picker shows \"No results\". Build the pipeline "
                      "(02-form-controls-reference.md §4a)." % (label, alias, method))
            else:
                have = ", ".join(sorted(m for m in methods_by_alias[alias] if m)[:6])
                r.warn("%s calls service.crud.%s.%s() but dynamic CRUD %r has no such method (has: %s…) — runtime "
                       "MissingMethodException. Add the method or fix the name." % (label, alias, method, alias, have))


def _check_groovy_method_rule_identifier(p, r):
    """A GROOVY dynamic-CRUD method does NOT run the `script` sitting next to it. It runs a rule,
    looked up by `ruleIdentifier`, with the arguments bound as `param` —
    the method executor refuses before it looks at anything else, with the error
    "Groovy method '<name>' has no rule identifier. Apply the CRUD first."

    In the UI that rule is written by the **Apply** button (saved as a hidden rule).
    A platform export carries it in rep-objects.json (with the business logic) and then that rule is what runs; an
    archive built by hand legitimately carries none of them — the IMPORTER creates each one from the method's own
    `script` (on import) when the project has no rule of that identifier yet. That creation is guarded: it is
    skipped when the identifier OR the script is blank,
    so the identifier is the entire hinge, and BOTH halves have to be present:

    * **script, no identifier** ⇒ ERROR. The importer skips the method and every call to it dies.
      The symptom is never the method's own name: a choices rule calling
      `service.crud.<x>.find(...)` renders an **empty dropdown**, a form action calling `create`
      reports `Form submission failed: … Groovy method 'create' has no rule identifier.` A project
      authored file-first has this on EVERY Groovy method — nothing else in the toolchain notices,
      because the script is present and correct.
    * **identifier, no script, and the identifier resolves to nothing** ⇒ ERROR. Same guard, opposite
      half: no rule is created and the call fails with `Rule not found with identifier: <id>`. (An
      identifier with no script that DOES resolve to a rule in `rep-objects.rules[]` is fine — that
      is a method delegating to a hand-authored visible rule.)

    Fix either one with `mrjun.py crud apply`. Do NOT "fix" it by writing the rule into
    rep-objects.json — the importer owns that object, and a second copy drifts from the script.

    ⚠️ **`find` is exempt.** A GROOVY `find` with a BLANK ruleIdentifier is the documented **auto-find
    sentinel**: the executor catches it ahead of the rule-delegation branch and
    runs the sibling `findAll` + `count` in-process. Its `script` is
    documentation, not the thing that executes. Flagging it would be a false positive on the single
    most common method in every project (11 §Step 3, Variant A).

    Note what is NOT a finding: a `ruleIdentifier` with no matching entry in `rep-objects.rules[]`
    is the CORRECT shipped shape (that rule is hidden and lives only in the executor's DB).
    """
    _by_alias, cruds = _dynamic_crud_methods(p)
    rule_ids = {x.get("identifier") for x in (p.rep.get("rules", []) or [])}
    for crud in cruds:
        alias = crud.get("alias")
        for m in crud.get("methods", []) or []:
            if (m.get("methodType") or "").upper() != "GROOVY":
                continue
            name = m.get("methodName")
            has_id = bool((m.get("ruleIdentifier") or "").strip())
            has_script = bool((m.get("script") or "").strip())
            if name == "find" and not has_id:
                continue                                    # auto-find sentinel — see docstring
            if has_script and not has_id:
                r.err("crud %r method %r is GROOVY with a script but no ruleIdentifier — the method "
                      "never runs its script. Callers fail with \"Groovy method '%s' has no rule "
                      "identifier. Apply the CRUD first.\", and a choices rule calling it just shows "
                      "an EMPTY dropdown. Run `mrjun.py crud apply`. (11 §Apply)"
                      % (alias, name, name))
            elif has_id and not has_script and m.get("ruleIdentifier") not in rule_ids:
                r.err("crud %r method %r is GROOVY with a ruleIdentifier but no script — the importer "
                      "skips it (ensureHiddenGroovyRule needs both), so calls fail with \"Rule not "
                      "found with identifier: %s\". Add the script or clear the identifier. (11 §Apply)"
                      % (alias, name, (m.get("ruleIdentifier") or "").strip()))


def _check_groovy_fk_param_shapes(p, r):
    """A GROOVY method that declares only `<ref>__id` gets NULL from a form dropdown.

    A business FK is written as `:<ref>__id` (11 §Document CRUD variant), and the executor fills that
    parameter by WALKING the path — it splits `purchaseOrder__id` into
    `purchaseOrder` -> `id` and descends through the submitted map, returning null as soon as a
    segment is not a nested object.

    That requires the caller to have sent a nested OBJECT, which an engine rule passing
    `{purchaseOrder: {id: …}}` does. A FORM does not: a dropdown bound to the nested dtoField
    (`fieldExpression: "purchaseOrder"`, `dataClass: java.lang.String`) puts the bare id STRING there.
    The walk finds a string instead of an object, returns null, the positional fallback finds neither
    `purchaseOrder__id` nor `purchaseOrderId` at the top level, the parameter is never set — and the
    INSERT writes NULL into the FK column. On a NOT NULL column that is
    `null value in column "po_id" … violates not-null constraint`, naming a column the author never
    typed; on a nullable one it is worse, because the row saves with a silently empty reference.

    Nothing offline sees it: the SQL is correct, the parameter IS declared, and the script reads.

    Fix — declare BOTH names and reconcile them in the script before calling the header helper. The
    extra declaration is free (an undeclared-by-the-caller parameter simply arrives absent), so this
    is safe to do unconditionally::

        parameters: [ …, "purchaseOrder__id", "purchaseOrder", … ]

        def _id = { v ->
            if (v == null) { return null }
            if (v instanceof Map) { def m = v['id']; return m == null ? null : m.toString() }
            if (v instanceof CharSequence) { def s = v.toString().trim(); return s.isEmpty() ? null : s }
            if (v.respondsTo('isNull') && v.isNull()) { return null }
            if (v.respondsTo('isObject') && v.isObject()) {
                def n = v.get('id'); return (n == null || n.isNull()) ? null : n.asText() }
            if (v.respondsTo('asText')) { def s = v.asText(); return (s == null || s.trim().isEmpty()) ? null : s }
            def s = v.toString().trim(); return s.isEmpty() ? null : s }
        def _fk = { k -> def v = param[k + '__id']; return _id(v != null ? v : param[k]) }

        def hdr = new LinkedHashMap(param)
        hdr['purchaseOrder__id'] = _fk('purchaseOrder')
        service.crud.goodsReceipt.createHeader(hdr)

    ERROR when a form control is actually bound to that `<ref>` on that CRUD — then it is not a risk,
    it is a submit that will fail. WARN otherwise: a method only ever called by rules works as-is, but
    the first form built over it will break, and the declaration costs nothing.
    """
    by_alias, cruds = _dynamic_crud_methods(p)
    if not cruds:
        return
    # (crudAlias, fieldExpression) of every form control in the project
    bound = set()
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName", "") or ""
        if not (pn.startswith("dynaform.form.") and pn.endswith(".plugin")):
            continue
        try:
            st = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        alias, expr = st.get("crudAlias"), st.get("fieldExpression")
        if alias and expr:
            bound.add((alias, expr))

    for crud in cruds:
        alias = crud.get("alias")
        for m in crud.get("methods", []) or []:
            if (m.get("methodType") or "").upper() != "GROOVY":
                continue
            names = {q.get("parameterName") for q in (m.get("parameters") or [])}
            for name in sorted(n for n in names if n and "__" in n):
                ref = name.split("__")[0]
                if ref in names:
                    continue
                msg = ("crud %r method %r declares %r but not the plain %r — a form dropdown bound to "
                       "that field sends the bare id STRING, walkParamPath needs a nested OBJECT and "
                       "returns null, so the FK column is written NULL (\"null value in column … "
                       "violates not-null constraint\"). Declare both names and resolve them in the "
                       "script. (11 §Document CRUD variant)"
                       % (alias, m.get("methodName"), name, ref))
                if (alias, ref) in bound:
                    r.err(msg + " A form control IS bound to %s.%s, so this submit fails." % (alias, ref))
                else:
                    r.warn(msg)


_SOFT_MARKERS = ("deleted", "is_deleted", "archived", "deleted_at")
_FROM_TBL_RE = re.compile(r"\bFROM\s+([a-zA-Z_][\w]*)", re.I)
_DELETE_TBL_RE = re.compile(r"\bDELETE\s+FROM\s+([a-zA-Z_][\w]*)", re.I)


def _check_soft_delete_discipline(p, r):
    """Deleting a row that something still references fails in the user's face, and a half-applied
    soft delete is worse — the row comes back.

    Three defects, all of which look fine offline:

    1. **A referenced table whose `delete` physically deletes.** The first user who tries it gets
       `ERROR: update or delete on table "supplier" violates foreign key constraint
       "fk_item_supplier_id" on table "item"`, and there is nothing they can do about it: the child
       rows are the point of the parent. Referenced tables need a marker, not a DELETE. (ERROR.)

    2. **A table that HAS a marker whose reads do not use it.** The delete succeeds, the user is told
       it worked, and the row is still in the list. Half a soft delete is worse than none, because it
       silently claims to have done something. (ERROR.)

    3. **A marker plus a plain UNIQUE.** The deleted row keeps its key reserved forever — retire
       `SUP-002` and that code can never be used again, which is not what "deleted" means to anyone.
       Postgres cannot make a table CONSTRAINT partial, so it has to become
       `CREATE UNIQUE INDEX … WHERE deleted = false` in `indexes`. (WARNING.)

    4. **The marker exposed as a dtoField.** It lands on generated forms as a "Deleted" checkbox and in
       every table's column chooser; a user who ticks it has silently performed a delete. (WARNING.)

    Deciding WHICH entities are soft is a judgement call the author must make per entity — an inbound
    FK forces it, but a ledger, an effective-dated version or a configuration row referenced only by
    code needs it too, and a document LINE deliberately does not. See 10 §"Deleting a row".
    """
    _by_alias, cruds = _dynamic_crud_methods(p)
    if not cruds or not p.db:
        return
    try:
        idx = dyncheck.build_schema_index(p.db)
    except Exception:
        return

    hard_referenced = []
    for crud in cruds:
        alias = crud.get("alias")
        schema = crud.get("sourceSchema")
        sidx = idx.get(schema) or {}
        tables = sidx.get("tables") or {}
        if not tables:
            continue
        methods = {m.get("methodName"): m for m in (crud.get("methods") or [])}

        # the CRUD's own table, taken from the SQL it actually runs
        tbl = None
        for nm in ("findAll", "count", "get"):
            m = methods.get(nm)
            if m and m.get("methodType") == "SQL":
                mt = _FROM_TBL_RE.search(m.get("script", "") or "")
                if mt and mt.group(1) in tables:
                    tbl = mt.group(1)
                    break
        if not tbl:
            continue
        cols = {c.get("name") for c in (tables.get(tbl) or [])}
        marker = next((c for c in _SOFT_MARKERS if c in cols), None)

        referenced = any(tbl in (fkmap or {}).values()
                         for fkmap in (sidx.get("fks") or {}).values())

        # (1) a referenced table that is physically deleted — collected, reported once (below)
        if referenced and not marker:
            for nm in ("delete", "_deleteHeader", "deleteHeader"):
                m = methods.get(nm)
                if m and m.get("methodType") == "SQL" and _DELETE_TBL_RE.search(m.get("script", "") or ""):
                    hard_referenced.append("%s.%s (%s)" % (alias, nm, tbl))
                    break

        if not marker:
            continue

        # (2) a marker nobody reads
        for nm in ("findAll", "count", "get"):
            m = methods.get(nm)
            if not m or m.get("methodType") != "SQL":
                continue
            if marker not in (m.get("script", "") or ""):
                r.err("crud %r method %r does not filter on %r, but %s carries that soft-delete marker — "
                      "a deleted row is still returned, so the delete silently does nothing the user can "
                      "see. (10 §Deleting a row)" % (alias, nm, marker, tbl))

        # (3) a plain UNIQUE alongside the marker
        for sch in (p.db.get("schemas") or []):
            if sch.get("name") != schema:
                continue
            for u in (sch.get("uniqueConstraints") or []):
                if re.search(r'"%s"\s+ADD CONSTRAINT' % re.escape(tbl), u):
                    r.warn("%s has the soft-delete marker %r but keeps a plain UNIQUE (%s) — a deleted "
                           "row reserves its key forever, so the code can never be reused. Make it "
                           "`CREATE UNIQUE INDEX … WHERE %s = false` in `indexes`. (10 §Deleting a row)"
                           % (tbl, marker, u.split("ADD CONSTRAINT")[-1].strip()[:60], marker))

        # (4) the marker exposed to forms
        if any((f.get("displayName") == marker or f.get("fieldName") == marker)
               for f in (crud.get("dtoFields") or [])):
            r.warn("crud %r exposes the soft-delete marker %r as a dtoField — it becomes a \"Deleted\" "
                   "checkbox on every generated form and a column in the table chooser, and ticking it "
                   "performs a delete. Drop it from dtoFields. (10 §Deleting a row)" % (alias, marker))

    # ONE finding, not one per CRUD: a scaffolded project has this on every dimension table at once,
    # and sixty identical errors is a report people learn to skip rather than a decision they make.
    if hard_referenced:
        shown = ", ".join(hard_referenced[:6])
        more = "" if len(hard_referenced) <= 6 else " … and %d more" % (len(hard_referenced) - 6)
        r.err("%d CRUD method(s) physically DELETE from a table that other tables reference by foreign "
              "key: %s%s. The first user who deletes a row that is actually in use gets \"update or "
              "delete on table … violates foreign key constraint\" and has no way forward. Decide per "
              "entity: give the ones that must be deletable a `deleted boolean NOT NULL DEFAULT false`, "
              "mark instead of deleting, filter every read, and make their UNIQUEs partial. "
              "(10 §Deleting a row)" % (len(hard_referenced), shown, more))


_CHART_JS_PROP = "Javascript"
_NEW_CHART_RE = re.compile(r"\bnew\s+Chart\s*\(")
_CHART_OPT_WRITE_RE = re.compile(r"\bthis\.chart\.options\.(\w+)\s*=")


def _check_chartjs_option_mutation(p, r):
    """Writing to `chart.options` after `new Chart(...)` mutates a structure Chart.js owns.

    In Chart.js 3 `chart.options` is not a plain object — it is the resolved, context-attached option
    proxy. Assigning into it (the usual case is a click-filter: `this.chart.options.onClick = …;
    this.chart.update();`) leaves that proxy inside the scope chain. The next hover rebuilds a resolver
    for the animation options, and `_descriptors` reads the `_scriptable` descriptor THROUGH the
    resolver instead of as a plain value; `_scriptable` is itself a function, so it gets called as a
    scriptable option, and that call reads `_scriptable` again::

        Uncaught Error: Recursion detected: _scriptable->_scriptable
            at Ie (_descriptors) → Re (_attachContext) → createResolver
            → _resolveAnimations → setHoverStyle → _updateHoverStyles → _handleEvent

    The chart RENDERS correctly and the first click even works — it dies only when someone moves the
    mouse across it or toggles a series in the legend, because only the hover path builds a resolver
    with the animation descriptor defaults that carry `_scriptable`. Nothing offline sees it: the JS is
    valid, the config is valid, and the page looks finished.

    Author the handlers into the config instead — `cfg.options.onClick = …` BEFORE `new Chart(ctx, cfg)`
    — and drop the trailing `chart.update()`; there is nothing to re-apply. (22 §5)

    ECharts/Plotly are not affected: they take listeners through `ec.on(...)` / `plotly_click`, which is
    a subscription rather than an option write, so only the Chart.js shape is reported.
    """
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "chart.js.plugin":
            continue
        props = node.get("properties") or {}
        js = ((props.get(_CHART_JS_PROP) or {}).get("stringValue") or "") if isinstance(props, dict) else ""
        if not js:
            continue
        ctor = _NEW_CHART_RE.search(js)
        if not ctor:
            continue                                   # not a Chart.js construction we can reason about
        for m in _CHART_OPT_WRITE_RE.finditer(js):
            if m.start() < ctor.start():
                continue                               # written before construction — harmless
            r.warn("chart %r assigns this.chart.options.%s AFTER `new Chart(...)`. chart.options is the "
                   "RESOLVED, context-attached option proxy — Chart.js owns its identity and reading a "
                   "key on it runs the scriptable resolver. Write to the CONFIG instead: `cfg.options` "
                   "before the constructor, or `this.chart.config.options` + chart.update() when the "
                   "code is appended after it. (WARNING, not an error: this is bad practice with a "
                   "known-good alternative — it has NOT been shown to cause a specific failure. 22 §5)"
                   % (node.get("name") or node.get("identifier"), m.group(1)))
            break


_NUMERIC_COLUMN_CLASSES = {
    "java.lang.Integer", "java.lang.Long", "java.lang.Short", "java.lang.Byte",
    "java.lang.Double", "java.lang.Float", "java.math.BigDecimal", "java.math.BigInteger",
    "int", "long", "short", "byte", "double", "float",
}

_TEMPORAL_COLUMN_CLASSES = {
    "java.time.LocalDate", "java.time.LocalDateTime", "java.time.Instant",
}

_MONEY_FORMATS = {"US", "EUROPEAN", "SPACE_COMMA", "SPACE_DOT", "SWISS", "INDIAN", "PLAIN"}

_COLUMN_TABLE_PLUGINS = ("crud.table.plugin", "crud.tree.plugin", "process.table.pluin")

# ------------------------------------------------- dateFormat is MOMENT, not Java
# The dateFormat field is an autocomplete over "the platform's curated moment.js
# pattern catalogue" and the runtime formatter "understands any
# moment pattern" — so a pattern typed by hand is accepted verbatim, INCLUDING one that is
# not moment at all. A Java/`SimpleDateFormat` pattern therefore never errors; it renders.
_MOMENT_DATE_CATALOGUE = {
    "DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD", "DD-MM-YYYY", "DD.MM.YYYY",
    "MMMM DD, YYYY", "MMM DD, YYYY", "DD MMMM YYYY", "DD MMM YYYY", "YYYY/MM/DD",
}
_MOMENT_DATETIME_CATALOGUE = {
    "DD/MM/YYYY HH:mm:ss", "DD/MM/YYYY HH:mm", "MM/DD/YYYY HH:mm:ss", "MM/DD/YYYY HH:mm",
    "YYYY-MM-DD HH:mm:ss", "YYYY-MM-DDTHH:mm:ss", "YYYY-MM-DD HH:mm",
    "DD-MM-YYYY HH:mm:ss", "DD.MM.YYYY HH:mm:ss", "DD/MM/YYYY hh:mm:ss A",
    "DD/MM/YYYY hh:mm A", "MM/DD/YYYY hh:mm:ss A", "MM/DD/YYYY hh:mm A",
    "MMMM DD, YYYY HH:mm:ss", "MMM DD, YYYY HH:mm:ss", "DD MMMM YYYY HH:mm:ss",
}
_MOMENT_CATALOGUE = _MOMENT_DATE_CATALOGUE | _MOMENT_DATETIME_CATALOGUE

_FORM_DATE_PLUGINS = ("dynaform.form.datepicker.field.plugin",
                      "dynaform.filter.datepicker.field.plugin")

# ---------------------------------------------------------------- money typing
# A money value must be held in a NUMERIC type, and BigDecimal is the only one that
# is exact. These name fragments are how a money field announces itself; the UNIT
# fragments below veto the match, because a name can carry both ("totalSeconds",
# "priceListLength") and the unit is the one that decides what the number IS.
_MONEY_NAME_TOKENS = (
    "price", "amount", "cost", "salary", "wage", "rate", "fee", "fare", "tariff",
    "balance", "earning", "payment", "payout", "revenue", "turnover", "discount",
    "tax", "vat", "charge", "budget", "premium", "deposit", "refund", "subtotal",
    "grandtotal", "nettotal", "duty", "commission", "penaltyamount", "bonus",
)
# Physical quantities and counters. If one of these appears the field is NOT money,
# however money-ish the rest of the name looks.
_NON_MONEY_UNIT_TOKENS = (
    "second", "minute", "hour", "day", "week", "month", "year", "duration", "time",
    "count", "qty", "quantity", "pieces", "pcs", "units", "number", "index", "order",
    "pct", "percent", "ratio", "length", "width", "height", "depth", "weight",
    "meter", "metre", "gram", "litre", "liter", "volume", "area", "size", "grade",
    "id", "code", "level", "step", "version", "score", "rating", "temperature",
    # names that denote a KIND of money thing rather than an amount of money
    "profile", "type", "kind", "category", "group", "policy", "scheme", "template",
    "currency", "method", "mode", "status", "flag", "name", "label", "title",
    "description", "comment", "note", "reference",
)
# A money amount is a SCALAR. These declared types mean the field is a nested object or a
# collection — a relation to a record, never an amount — so the name heuristic must not fire.
_RELATION_CLASSES = {"ObjectNode", "ArrayNode", "com.fasterxml.jackson.databind.node.ObjectNode",
                     "com.fasterxml.jackson.databind.node.ArrayNode", "java.util.List",
                     "java.util.Map", "java.util.Set"}
_EXACT_MONEY_CLASSES = {"java.math.BigDecimal", "BigDecimal"}
_INEXACT_MONEY_CLASSES = {"java.lang.Double", "java.lang.Float", "double", "float",
                          "Double", "Float"}
_NUMERIC_ANY = _NUMERIC_COLUMN_CLASSES | {
    "BigDecimal", "BigInteger", "Integer", "Long", "Short", "Byte", "Double", "Float",
}


def _split_field_name(name):
    """`monthlySalary` / `monthly_salary` / `MONTHLY_SALARY` -> ['monthly', 'salary']."""
    out, cur = [], ""
    for ch in str(name):
        if not ch.isalnum():
            if cur:
                out.append(cur.lower())
            cur = ""
        elif ch.isupper() and cur and not cur[-1].isupper():
            out.append(cur.lower())
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur.lower())
    return out


def _looks_like_money(name):
    """True when the field name's HEAD NOUN announces a money value.

    Only the last token decides, and that is the whole point. A money name routinely carries a
    non-money qualifier (`monthlySalary`, `dayRate`, `secondRate` — per month, per day, per
    second, all of them money), while a quantity name routinely carries a money-ish qualifier
    (`priceListLength`, `bundlesTotal`). Scanning the WHOLE name gets both of those wrong; the
    head noun says what the number IS and the qualifier only says what it is per."""
    tokens = _split_field_name(name)
    if not tokens:
        return False
    head = tokens[-1]
    if any(tok in head for tok in _NON_MONEY_UNIT_TOKENS):
        return False
    return any(tok in head for tok in _MONEY_NAME_TOKENS)


_SELF_COALESCE = re.compile(
    r"\b(\w+)\s*=\s*COALESCE\s*\(\s*(?:CAST\s*\(\s*)?NULLIF\s*\(\s*(?:CAST\s*\()?\s*:\s*\w+"
    r"[^,]*?,\s*''\s*\)(?:\s*AS\s+[\w ]+\s*\))?\s*,\s*\1\s*\)", re.I)


def _check_unclearable_optional_fields(p, r):
    """An optional field the user can EDIT but can never BLANK again.

    `col = COALESCE(CAST(NULLIF(:col,'') AS t), col)` in an `update` means "keep the old value when
    the parameter arrives empty". That is right for a column the form does not carry — without it
    every save would wipe it. It is wrong for a column the form DOES carry, because a cleared input
    arrives as `''` too: the old value is restored, the form redirects, and the toast says saved.
    The user watches their deletion undo itself with no error anywhere.

    So this WARNs only where both things are true: the column is NULLABLE, and a form control binds
    to it. That pairing is the whole signal — neither half alone is a defect.

    The fix is to drop the COALESCE for that column (`col = CAST(NULLIF(:col,'') AS t)`) once you have
    checked that every form able to call this `update` carries the field; if two forms carry different
    subsets, the column must stay guarded and the partial form is the thing to fix."""
    crud_file = p.cruds_file
    cruds = ((crud_file.data.get("cruds") or []) if crud_file else [])
    if not cruds:
        return

    # which (alias, field) a form control actually binds to
    on_form = set()
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName")
        if not (isinstance(pn, str) and pn.startswith("dynaform.form.") and pn.endswith(".field.plugin")):
            continue
        try:
            st = core.get_inner_json(node, "settings")
        except core.ToolError:
            continue
        alias, fe = st.get("crudAlias"), st.get("fieldExpression")
        if alias and fe:
            on_form.add((alias, fe.split(".")[0]))

    nullable = _dump_nullable_columns(p)
    for crud in cruds:
        if not isinstance(crud, dict):
            continue
        alias = crud.get("alias") or "?"
        for m in (crud.get("methods") or []):
            if m.get("methodName") != "update" or m.get("methodType") != "SQL":
                continue
            sql = m.get("script") or ""
            tm = re.search(r"UPDATE\s+([\w.]+)", sql, re.I)
            table = tm.group(1).split(".")[-1] if tm else None
            for col in _SELF_COALESCE.findall(sql):
                if nullable and nullable.get((table, col)) is not True:
                    continue
                field = _snake_to_camel(col.strip("_"))
                base = field[:-2] if field.endswith("Id") else field
                if (alias, field) in on_form or (alias, base) in on_form:
                    r.warn("crud %r update keeps %r with COALESCE(..., %s) while a form control binds to "
                           "it — the user can set that field but never clear it: a blanked input arrives "
                           "as '' and the old value is restored, with a success toast and no error. Drop "
                           "the COALESCE for this column if every form calling this update carries the "
                           "field. (11-business-logic-dynamic-crud.md)" % (alias, col, col))


def _snake_to_camel(c):
    parts = [x for x in c.split("_") if x]
    return parts[0] + "".join(x.capitalize() for x in parts[1:]) if parts else c


def _dump_nullable_columns(p):
    """{(table, column): is_nullable} read out of each table's DDL in project-db.dump.

    Returns {} when the dump is absent or unreadable — the caller then skips the nullability
    half of its test rather than guessing."""
    out = {}
    try:
        db = p.db
    except Exception:
        return out
    if not isinstance(db, dict):
        return out
    for schema in (db.get("schemas") or []):
        for t in (schema.get("tables") or []):
            ddl = t.get("ddl") or ""
            table = t.get("name")
            if not (ddl and table):
                continue
            body = ddl[ddl.find("(") + 1:]
            for line in body.split("\n"):
                line = line.strip().rstrip(",")
                cm = re.match(r'"(\w+)"\s+\S', line)
                if cm:
                    out[(table, cm.group(1))] = "NOT NULL" not in line.upper()
    return out


def _check_money_field_typing(p, r):
    """A money field must be NUMERIC, and BigDecimal is the only exact choice.

    Money held in a String sorts lexicographically ("9" > "10"), cannot be summed, and — the
    part that bites in the UI — silently disables every money display key, because `money:true`
    is gated on a numeric `dataClass` at render (see `_check_column_format_keys`, which catches
    the opposite mistake). Money held in a Double/Float is binary floating point: 0.1 + 0.2 is
    not 0.3 and cents drift once the values are added up.

    So this walks the three places a money field gets a declared type — table columns, form
    controls and dynamic-CRUD dtoFields — and warns when the declared type is not numeric, or
    is numeric but inexact.

    Both warnings are name-driven heuristics, so they are WARN and never ERROR: `_looks_like_money`
    requires a money token AND the absence of a unit token, which is what keeps `totalSeconds`,
    `allowancePct` and `chainLength` out of it."""
    def _flag(where, label, declared, kind):
        if declared in _EXACT_MONEY_CLASSES or declared in _RELATION_CLASSES:
            return
        if declared in _INEXACT_MONEY_CLASSES:
            r.warn("%s %r is a money field typed %s — binary floating point loses cents once "
                   "values are summed; use java.math.BigDecimal. (10-database-management.md)"
                   % (kind, "%s.%s" % (where, label), declared))
        elif declared not in _NUMERIC_ANY:
            r.warn("%s %r is a money field typed %r — money must be numeric (preferably "
                   "java.math.BigDecimal): a non-numeric type sorts as text, cannot be summed, "
                   "and silently disables money/currency display, which is gated on a numeric "
                   "dataClass at render. (04-crud-table-plugin.md)"
                   % (kind, "%s.%s" % (where, label), declared or None))

    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName")
        if pn in _COLUMN_TABLE_PLUGINS:
            try:
                model = core.get_inner_json(node, "model")
            except core.ToolError:
                continue
            where = node.get("name") or node.get("identifier") or pn
            for c in (model.get("columnSettings") or []):
                if not isinstance(c, dict):
                    continue
                fe = c.get("fieldExpression") or ""
                leaf = str(fe).split(".")[-1]
                if _looks_like_money(leaf):
                    _flag(where, fe, (c.get("dataClass") or "").strip(), "table column")
        elif isinstance(pn, str) and pn.startswith("dynaform.form.") and pn.endswith(".field.plugin"):
            try:
                st = core.get_inner_json(node, "settings")
            except core.ToolError:
                continue
            fe = st.get("fieldExpression") or st.get("key") or ""
            leaf = str(fe).split(".")[-1]
            if _looks_like_money(leaf):
                where = node.get("name") or node.get("identifier") or pn
                _flag(where, fe, (st.get("dataClass") or "").strip(), "form control")

    crud_file = p.cruds_file
    for crud in ((crud_file.data.get("cruds") or []) if crud_file else []):
        if not isinstance(crud, dict):
            continue
        alias = crud.get("alias") or "?"
        for f in (crud.get("dtoFields") or []):
            if not isinstance(f, dict):
                continue
            fn = f.get("fieldName")
            if _looks_like_money(fn):
                _flag(alias, fn, (f.get("fieldType") or "").strip(), "crud field")



def _check_column_format_keys(p, r):
    """Table-column money/date display keys are gated on `dataClass` at RENDER — a mismatch is
    silently ignored, not reported, so the column just draws its raw value and nobody knows why.

    `money:true` only renders for a numeric dataClass (Integer/Long/Short/Byte/Double/Float/
    BigDecimal/BigInteger + primitives); `dateFormat` only renders for LocalDate/LocalDateTime/
    Instant. `moneyFormat` must be one of US/EUROPEAN/SPACE_COMMA/SPACE_DOT/SWISS/INDIAN/PLAIN
    (anything else falls back to US) and `moneyDecimals` must be 0..6 (outside that it is clamped).

    The `dynaform.form.list.field.plugin` sub-grid is a special case: its column panel never writes
    a `dataClass` at all, so EVERY dataClass-gated capability there (boolean icons, right-alignment,
    money, dateFormat) is dormant unless the column is hand-written with one.
    See 04-crud-table-plugin.md and 05-crud-tree-and-process-table.md."""
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName")
        is_list = pn == "dynaform.form.list.field.plugin"
        if pn not in _COLUMN_TABLE_PLUGINS and not is_list:
            continue
        try:
            model = core.get_inner_json(node, "settings" if is_list else "model")
        except core.ToolError:
            continue
        where = node.get("name") or node.get("identifier") or pn
        for c in (model.get("columnSettings") or []):
            if not isinstance(c, dict):
                continue
            label = ((c.get("localizedNames") or {}).get("en_US")
                     or c.get("name") or c.get("fieldExpression") or "?")
            data_class = (c.get("dataClass") or "").strip()
            money = c.get("money") is True
            date_format = (c.get("dateFormat") or "").strip()

            if is_list and (money or date_format):
                r.warn("%s %r column %r sets money/dateFormat, but the List field's column panel "
                       "never writes a dataClass and both are gated on it — the cell renders raw. "
                       "Hand-write the column's dataClass too. (14a-plugin-config-reference.md)"
                       % (pn, where, label))
            elif money and data_class not in _NUMERIC_COLUMN_CLASSES:
                r.warn("%s %r column %r sets money:true but dataClass is %r — money renders only for "
                       "a numeric dataClass, so the cell draws the raw number. "
                       "(04-crud-table-plugin.md)"
                       % (pn, where, label, data_class or None))
            elif date_format and data_class not in _TEMPORAL_COLUMN_CLASSES:
                r.warn("%s %r column %r sets dateFormat %r but dataClass is %r — the pattern renders "
                       "only for java.time.LocalDate/LocalDateTime/Instant, so the cell draws the raw "
                       "stored value. (04-crud-table-plugin.md)"
                       % (pn, where, label, date_format, data_class or None))

            mf = c.get("moneyFormat")
            if mf and mf not in _MONEY_FORMATS:
                r.warn("%s %r column %r has moneyFormat %r — not one of %s; the runtime falls back "
                       "to US. (04-crud-table-plugin.md)"
                       % (pn, where, label, mf, "/".join(sorted(_MONEY_FORMATS))))

            md = c.get("moneyDecimals")
            if isinstance(md, int) and not (0 <= md <= 6):
                r.warn("%s %r column %r has moneyDecimals %d — outside 0..6; the runtime clamps it. "
                       "(04-crud-table-plugin.md)" % (pn, where, label, md))



def _check_date_format_tokens(p, r):
    """`dateFormat` is a **moment.js** pattern. A Java / `SimpleDateFormat` pattern is accepted
    verbatim and then RENDERS AS GARBAGE — no error, no log, nothing to grep for.

    The tell is lowercase `y`: moment has no `yyyy` token, so it emits the four characters
    literally. Lowercase `dd` is a moment token, but it means *minified weekday name* ("Mo"),
    not day-of-month. So the very common Java pattern `dd.MM.yyyy` renders as::

        dd.11.yyyy          <- "dd" literal-ish, month 11 substituted, "yyyy" literal

    On a **date picker form control** that string is written into the input's `value` (the field
    has no placeholder), so the user sees a filled box of nonsense, the calendar opens on
    "January 1926" with NaN cells, and anything typed is appended to the junk. On a **table
    column** the cell just draws the same mess.

    Valid patterns come from the platform's curated moment.js catalogue; the defaults are `DD/MM/YYYY` for
    `LocalDate` and `DD/MM/YYYY HH:mm:ss` for `LocalDateTime`/`Instant`.

    See 02-form-controls-reference.md §5 and 04-crud-table-plugin.md."""

    def _judge(fmt, data_class, where, label):
        f = (fmt or "").strip()
        if not f:
            return
        if "y" in f:
            r.err("%s %s dateFormat %r is a JAVA pattern — `dateFormat` is moment.js, which has "
                    "no `yyyy` token and reads `dd` as a WEEKDAY name. It renders literally "
                    "(e.g. `dd.MM.yyyy` -> `dd.11.yyyy`) into the field's VALUE, with no error "
                    "anywhere. Use %r. (02-form-controls-reference.md §5)"
                    % (where, label, f,
                       "DD/MM/YYYY HH:mm:ss" if data_class in (
                           "java.time.LocalDateTime", "java.time.Instant") else "DD/MM/YYYY"))
            return
        if re.search(r"(?<![A-Za-z])d{1,4}(?![A-Za-z])", f):
            r.warn("%s %s dateFormat %r uses lowercase `d` — in moment that is a WEEKDAY name, "
                   "not the day of the month (which is `D`/`DD`). "
                   "(02-form-controls-reference.md §5)" % (where, label, f))
        if f not in _MOMENT_CATALOGUE:
            r.warn("%s %s dateFormat %r is not in the platform's curated catalogue "
                   "— legal, but verify it renders. "
                   "(02-form-controls-reference.md §5)" % (where, label, f))
        elif data_class in ("java.time.LocalDateTime", "java.time.Instant") \
                and f in _MOMENT_DATE_CATALOGUE:
            r.warn("%s %s dateFormat %r is date-only but the field is %s — the time component is "
                   "silently dropped on display. (02-form-controls-reference.md §5)"
                   % (where, label, f, data_class))

    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName")
        where = "%s %r" % (pn, node.get("name") or node.get("identifier") or "?")

        if pn in _FORM_DATE_PLUGINS:
            try:
                cfg = core.get_inner_json(node, "settings")
            except core.ToolError:
                cfg = None
            if isinstance(cfg, dict):
                _judge(cfg.get("dateFormat"), (cfg.get("dataClass") or "").strip(),
                       where, "field %r" % (cfg.get("fieldExpression") or "?"))

        is_list = pn == "dynaform.form.list.field.plugin"
        if pn in _COLUMN_TABLE_PLUGINS or is_list:
            try:
                model = core.get_inner_json(node, "settings" if is_list else "model")
            except core.ToolError:
                continue
            if not isinstance(model, dict):
                continue
            for c in (model.get("columnSettings") or []):
                if not isinstance(c, dict):
                    continue
                label = ((c.get("localizedNames") or {}).get("en_US")
                         or c.get("name") or c.get("fieldExpression") or "?")
                _judge(c.get("dateFormat"), (c.get("dataClass") or "").strip(),
                       where, "column %r" % label)



def _check_localized_fields(p, r):
    """A form control with `settings.localized:true` writes/reads per-locale values in the CRUD's
    `localize` jsonb — but it SILENTLY falls back to the base column (one language on every locale tab,
    the "labels stuck on the base locale" bug) unless ALL of: (a) the bound CRUD has a `localizationField`
    jsonb, (b) the enclosing form is `multiLanguage`, (c) the tenant has >1 locale. Each missing
    prerequisite is a WARN (the page still renders — it just isn't localized). See 20-localization.md."""
    loc_field = {c.get("alias"): c.get("localizationField")
                 for c in (p.cruds_file.data.get("cruds", []) if p.cruds_file else []) or []}
    n_locales = len(set(p.locales()))

    def _localized_settings(subtree):
        for n, _pp, _pt in core.iter_nodes(subtree):
            pn = n.get("pluginName", "") or ""
            if not (pn.startswith("dynaform.form.") and pn.endswith(".plugin")):
                continue
            try:
                st = core.get_inner_json(n, "settings")
            except core.ToolError:
                continue
            if st.get("localized") is True:
                yield st

    # (a) CRUD localizationField + (b) tenant locales — per localized field
    for st in _localized_settings(p.root_content):
        field = st.get("fieldExpression") or st.get("name")
        alias = st.get("crudAlias")
        if alias and alias in loc_field and not loc_field.get(alias):
            r.warn("form field %r has \"localized\":true but its dynamic CRUD %r has NO localizationField "
                   "(localize jsonb) — per-locale values have nowhere to persist and the field silently reads the "
                   "base column. Add a localizationField or remove localized:true. (20-localization.md)"
                   % (field, alias))
        if n_locales <= 1:
            r.warn("form field %r has \"localized\":true but the tenant has <=1 locale — localization is a no-op "
                   "(add locales to tenant.json). (20-localization.md)" % field)

    # (c) enclosing form must be multiLanguage — scan each non-multiLanguage form's content subtree
    id_to_node = {}
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        nid = n.get("identifier")
        if nid and nid not in id_to_node:
            id_to_node[nid] = n
    for f in p.rep.get("forms", []) or []:
        if f.get("multiLanguage"):
            continue
        cnode = id_to_node.get(f.get("contentIdentifier"))
        if cnode is None:
            continue
        for st in _localized_settings(cnode):
            field = st.get("fieldExpression") or st.get("name")
            r.warn("form %r is NOT multiLanguage but contains a localized field %r — the field silently reads the "
                   "base column (per-locale values never render or persist). Set the form multiLanguage:true, or "
                   "remove localized:true from the field. (20-localization.md)" % (f.get("name"), field))


# canonical ReportRole set (31; includes the canonical typo ORGANIZARIONS_VIEW) — the exact set used across
# every ground-truth export, so zero-false-positive on the reference set.
_REPORT_ROLES = {
    "ADMIN", "FILE_STORAGE_EDIT", "FILE_STORAGE_VIEW", "NCT_AUTHOR", "ORGANIZARIONS_VIEW", "ORGANIZATIONS_EDIT",
    "OYO_PROJECT_CONFIGURATION", "PROJECT_EDIT", "PROJECT_VIEW", "REPORT_EDIT", "REPORT_EDIT_ANY", "REPORT_VIEW",
    "REPORT_VIEW_ANY", "ROLE_GROUP_CREATE", "ROLE_GROUP_DELETE", "ROLE_GROUP_EDIT", "ROLE_GROUP_VIEW",
    "SCHEDULER_EDIT", "SCHEDULER_EDIT_ANY", "SCHEDULER_VIEW", "SCHEDULER_VIEW_ANY", "SOURCE_EDIT", "SOURCE_EDIT_ANY",
    "SOURCE_VIEW", "SOURCE_VIEW_ANY", "STORE_EXECUTE", "STORE_EXECUTE_ANY", "USER_CREATE", "USER_DELETE",
    "USER_EDIT", "USER_VIEW",
}
_SOURCE_TYPES = {"INTERNAL", "EXTERNAL", "INTEGRATION", "SYSTEM"}
_QUARTZ_DOM_RE = re.compile(r"^(?:\d+[LW]|L|W)$", re.I)


def _blank(v):
    return v is None or v == "null" or (isinstance(v, str) and not v.strip())


def _script_text(code):
    """A Groovy body for comparing two copies of it: line endings and trailing blanks do not make it another body."""
    if not isinstance(code, str):
        return ""
    return "\n".join(line.rstrip() for line in code.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()


def _check_sources_queries_roles(p, r):
    """rep-object enum / duplicate-key / required-field integrity (import-abort or won't-persist):
      * source dbType must be exactly 'POISTGRESQL', sourceType in {INTERNAL,EXTERNAL,INTEGRATION,SYSTEM} (import-abort);
      * duplicate query names (unique (realm,client,name) — the 2nd won't persist);
      * query with null/blank sourceIdentifier (source_identifier NOT NULL);
      * roleGroups roles must be canonical ReportRole values (import-abort);
      * userRoleGroupAssignments.roleGroupName must resolve (else the binding is silently dropped -> WARN)."""
    from collections import Counter
    rep = p.rep
    for s in rep.get("sources", []) or []:
        if s.get("dbType") is not None and s.get("dbType") != "POISTGRESQL":
            r.err("source %r dbType %r is not 'POISTGRESQL' (the only DbType value — the typo is canonical); import aborts. (12 §2.3)" % (s.get("name"), s.get("dbType")))
        if s.get("sourceType") is not None and s.get("sourceType") not in _SOURCE_TYPES:
            r.err("source %r sourceType %r not in %s; import aborts. (12 §2.3)" % (s.get("name"), s.get("sourceType"), sorted(_SOURCE_TYPES)))
    for nm, c in Counter(q.get("name") for q in rep.get("queries", []) or [] if q.get("name")).items():
        if c > 1:
            r.err("query name %r appears %d times — the unique (realm,client,name) index drops the duplicate on import. (12 §1.3)" % (nm, c))
    for q in rep.get("queries", []) or []:
        if _blank(q.get("sourceIdentifier")):
            r.err("query %r has a null/blank sourceIdentifier (source_identifier is NOT NULL) — the row won't persist. (12 §1.3)" % q.get("name"))
    for rg in rep.get("roleGroups", []) or []:
        for role in rg.get("roles", []) or []:
            if role not in _REPORT_ROLES:
                r.err("roleGroup %r role %r is not a canonical ReportRole value — import aborts. (12 §4.4)" % (rg.get("name"), role))
    grp_names = {g.get("name") for g in rep.get("roleGroups", []) or []} | {"Author", "Developer"}
    for a in rep.get("userRoleGroupAssignments", []) or []:
        if a.get("roleGroupName") and a["roleGroupName"] not in grp_names:
            r.warn("userRoleGroupAssignment roleGroupName %r matches no role group (nor Author/Developer) — the binding is silently dropped. (12 §5.4)" % a["roleGroupName"])


def _check_cron_expr(expr, label, r):
    expr = expr.strip()
    if expr.startswith("@"):
        return
    fields = expr.split()
    if len(fields) != 6:
        r.err("scheduler %s cron %r has %d fields, not 6 (Spring: sec min hour dom mon dow). (12 §3.2)" % (label, expr, len(fields)))
        return
    for f in fields:
        if f == "?" or "#" in f or _QUARTZ_DOM_RE.match(f):
            r.err("scheduler %s cron %r uses a Quartz-only token %r (?, L, W, or #) — the Spring cron parser rejects it. (12 §3.2)" % (label, expr, f))
            return


# The scheduler record's fields plus the common base/error fields. Anything else is dropped on import.
_ABSTRACT_DTO_KEYS = {"message", "errors", "id", "realmName", "clientName", "identifier",
                      "creationTime", "modificationTime"}
_SCHEDULE_DTO_KEYS = _ABSTRACT_DTO_KEYS | {
    "name", "job", "predicateIdentifier", "actionType", "actionRuleIdentifier", "cooldownJob",
    "enabled", "cooldownUntil", "lastActionTime", "lastPredicateCheckTime",
    "serviceUserId", "serviceUserEmail"}


def _check_schedulers(p, r):
    """A scheduler's predicateIdentifier must be a PREDICATE and actionRuleIdentifier an EXECUTION_RULE (wrong
    type = ERROR, dangling = WARN); its cron must be Spring-6-field (Quartz ?/L/W/# = ERROR); enabled:true with a
    cron auto-fires on import (WARN); scheduler `name` is unique per project (duplicate = ERROR).
    **A missing/blank `job.expression` → ERROR** (the platform skips cron registration: the schedule never fires);
    **`actionType` missing or not RUN_RULE → ERROR** (the editor's dropdown is setNullValid(false), so it shows
    empty and cannot be saved); **any key that is not a field of a scheduler record → ERROR** — the import
    ignores unknown properties, so an invented field name is dropped in complete silence."""
    from collections import Counter
    types = _rule_types(p)
    for nm_, c in Counter(s.get("name") for s in p.rep.get("schedulers", []) or [] if s.get("name")).items():
        if c > 1:
            r.err("scheduler name %r appears %d times — the unique (realm,client,name) index makes the 2nd save "
                  "THROW on import, and schedulers are saved before workflows/rules/contexts/forms/settings, so "
                  "everything after them is silently skipped. (12 §3.2)" % (nm_, c))
    for s in p.rep.get("schedulers", []) or []:
        nm = s.get("name") or s.get("identifier")
        pid = s.get("predicateIdentifier")
        if not _blank(pid):
            if pid not in types:
                r.warn("scheduler %r predicateIdentifier %s does not exist in rules[]. (12 §3.2)" % (nm, pid))
            elif types[pid] != "PREDICATE":
                r.err("scheduler %r predicateIdentifier %s is ruleType %s, not PREDICATE. (12 §3.2)" % (nm, pid, types[pid]))
        aid = s.get("actionRuleIdentifier")
        if _blank(aid):
            r.warn("scheduler %r has no actionRuleIdentifier — nothing runs. (12 §3.2)" % nm)
        elif aid not in types:
            r.warn("scheduler %r actionRuleIdentifier %s does not exist in rules[] — nothing runs. (12 §3.2)" % (nm, aid))
        elif types[aid] != "EXECUTION_RULE":
            r.err("scheduler %r actionRuleIdentifier %s is ruleType %s, not EXECUTION_RULE. (12 §3.2)" % (nm, aid, types[aid]))
        # ⛔ ABSENCE, not just wrongness. Everything below used to be guarded by
        # `if isinstance(job, dict)`, so a scheduler with NO `job` at all passed every check in
        # silence — which is the exact shape a hand-authored scheduler takes when its author writes
        # a top-level `cronExpression` (not a field of a scheduler record). The import drops the
        # unknown key, `job` stays null, and the platform logs
        # "has no cron expression, skipping cron registration": the schedule imports, looks right
        # in the list, and never fires once.
        unknown = sorted(set(s.keys()) - _SCHEDULE_DTO_KEYS)
        if unknown:
            r.err("scheduler %r carries %s, which %s not a field of a scheduler record — the import ignores "
                  "unknown properties, so %s DROPPED IN SILENCE and the field it was "
                  "meant to fill stays empty. The real names are %s. (12 §3.1)"
                  % (nm, ", ".join(repr(u) for u in unknown),
                     "are" if len(unknown) > 1 else "is",
                     "they are" if len(unknown) > 1 else "it is",
                     ", ".join(sorted(_SCHEDULE_DTO_KEYS - _ABSTRACT_DTO_KEYS))))
        job = s.get("job")
        if not isinstance(job, dict) or not (job.get("expression") or "").strip():
            r.err("scheduler %r has no job.expression — the cron lives in the nested `job` object "
                  "({expression, explanation, cronType}), and without it "
                  "the platform skips cron registration entirely: the schedule "
                  "imports and NEVER FIRES. (12 §3.1)" % nm)
        at = s.get("actionType")
        if at != "RUN_RULE":
            r.err("scheduler %r actionType is %r — the only legal value is the literal \"RUN_RULE\" "
                  "(ActionType has exactly one constant). The editor's Action Type dropdown is "
                  "setNullValid(false), so a missing one renders EMPTY and the scheduler cannot be "
                  "saved from the UI without re-picking it. (12 §3.1)" % (nm, at))
        for jk in ("job", "cooldownJob"):
            job2 = s.get(jk)
            if isinstance(job2, dict) and isinstance(job2.get("expression"), str) and job2["expression"].strip():
                _check_cron_expr(job2["expression"], "%r %s" % (nm, jk), r)
        job = s.get("job")
        if s.get("enabled") is True and isinstance(job, dict) and (job.get("expression") or "").strip():
            r.warn("scheduler %r enabled:true — it auto-registers and fires its action on import; set enabled:false unless it's meant to run live. (12 §3.3)" % nm)


_PREDICATE_REF_KEYS = ("prohibitedPredicateIdentifier", "hiddenPredicateIdentifier",
                       "requiredPredicateIdentifier", "mandatoryPredicateIdentifier",
                       "choicesPredicateIdentifier")


def _rule_types(p):
    return {r.get("identifier"): r.get("ruleType") for r in p.rep.get("rules", []) or [] if r.get("identifier")}


def _iter_control_settings(p):
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        pn = n.get("pluginName", "") or ""
        if not (pn.startswith("dynaform.form.") and pn.endswith(".plugin")):
            continue
        try:
            st = core.get_inner_json(n, "settings")
        except core.ToolError:
            continue
        yield n, pn, st


def _check_field_rule_refs(p, r):
    """A form control's settings reference rules that must EXIST and be the RIGHT ruleType — dangling or
    wrong-type renders the field fine but the guard/validation/default silently never fires:
    prohibited/hidden/required/mandatory/choices `PredicateIdentifier` + `conditionalValidations[].predicateIdentifier`
    → a PREDICATE; `validationRule` → a VALIDATION_RULE; `defaultValueRuleIdentifier` (rule-mode default) → an
    EXECUTION_RULE. WARN (matches the existing dangling-ref convention; the page still renders). Skips null/'null'."""
    types = _rule_types(p)

    def check(field, key, rid, want):
        if not (rid and isinstance(rid, str) and rid != "null"):
            return
        if rid not in types:
            r.warn("field %r %s %s does not exist in rules[] — the guard/validation/default silently never fires. "
                   "(02-form-controls-reference.md / 08-groovy-rules-and-context.md)" % (field, key, rid))
        elif want and types[rid] != want:
            r.warn("field %r %s %s is ruleType %s, not %s — it silently misbehaves."
                   % (field, key, rid, types[rid], want))

    for n, pn, st in _iter_control_settings(p):
        field = st.get("fieldExpression") or st.get("name") or n.get("name")
        for k in _PREDICATE_REF_KEYS:
            check(field, k, st.get(k), "PREDICATE")
        check(field, "validationRule", st.get("validationRule"), "VALIDATION_RULE")
        for cv in st.get("conditionalValidations") or []:
            if isinstance(cv, dict):
                check(field, "conditionalValidations.predicateIdentifier", cv.get("predicateIdentifier"), "PREDICATE")
        if st.get("defaultValueStatic") is False:
            check(field, "defaultValueRuleIdentifier", st.get("defaultValueRuleIdentifier"), "EXECUTION_RULE")


def _check_table_fetch_rules(p, r):
    """A `crud.table`/`crud.tree`/`process.table` `findRuleIdentifier`/`fetchRuleIdentifier` (in `properties.model`)
    must resolve to a real rule — a dangling one means the table/tree can't fetch its rows and renders empty. ERROR."""
    rule_ids = set(_rule_types(p))
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") not in ("crud.table.plugin", "crud.tree.plugin", "process.table.pluin"):
            continue
        prop = (n.get("properties") or {}).get("model")
        if not (isinstance(prop, dict) and prop.get("stringValue")):
            continue
        try:
            md = json.loads(prop["stringValue"])
        except json.JSONDecodeError:
            continue
        if not isinstance(md, dict):
            continue
        for k in ("findRuleIdentifier", "fetchRuleIdentifier"):
            rid = md.get(k)
            if rid and isinstance(rid, str) and rid != "null" and rid not in rule_ids:
                r.err("%s %r %s %s does not exist in rules[] — the table/tree can't fetch its rows (renders empty). "
                      "(04-crud-table-plugin.md / 05-crud-tree-and-process-table.md)"
                      % (n.get("pluginName"), n.get("name"), k, rid))


def _check_event_mappings(p, r):
    """A form control's `eventComponentMappings[].componentIdentifier` is the change-event refresh target — it must
    equal some existing node's `uniqueIdentifier` (NOT `identifier`), else the dependent/cascade refresh is silently
    dead: the control works, but changing it re-renders nothing. WARN. (BaseFormControl matches uniqueIdentifier.)"""
    uids = set()
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        u = n.get("uniqueIdentifier")
        if isinstance(u, str):
            uids.add(u)
    for n, pn, st in _iter_control_settings(p):
        for m in st.get("eventComponentMappings") or []:
            if not isinstance(m, dict):
                continue
            ci = m.get("componentIdentifier")
            if ci and isinstance(ci, str) and ci not in uids:
                r.warn("field %r eventComponentMapping targets componentIdentifier %s — no node has that "
                       "uniqueIdentifier, so the change-event refresh is dead (the dependent field never "
                       "re-renders). (02-form-controls-reference.md §eventComponentMappings)"
                       % (st.get("fieldExpression") or st.get("name") or n.get("name"), ci))


# The renderer's plugin map, per 15-pdf-and-mail.md §"authoritative
# field-type set": the drawing/text/choice types AND the twelve barcode types. The barcodes
# were missing here, so every qrcode/code128/ean13 field was reported as rendering blank.
_PDFME_FIELD_TYPES = {"text", "multiVariableText", "image", "svg", "line", "rectangle", "ellipse", "table",
                      "date", "time", "dateTime", "checkbox", "radioGroup", "select",
                      "qrcode", "japanpost", "ean13", "ean8", "code39", "code128",
                      "nw7", "itf14", "upca", "upce", "gs1datamatrix", "pdf417"}
_PDF_FIELD_TYPES_TEXT = ", ".join(sorted(_PDFME_FIELD_TYPES))


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _pdf_field_problems(field, where, named=True):
    """What makes the renderer refuse a pdfme field -- and then the WHOLE PDF fails, not just the field (pdfme checks the template before it draws
    anything: `[@pdfme/common] Invalid argument`). Read off the renderer (pdfme 6.1.2), not off a guess: a field must be an object with a `name`
    (text; a page written the legacy way, as an object keyed by field name, has the name in the key), a `type` that is one of the renderer's, a
    `position` with numbers `x` and `y`, numbers `width` and `height`; `readOnly`, if there, a boolean; `rotate`, if there, a number. What it lets
    pass: an empty name, a negative width, duplicate names, keys it does not know, a `fontSize` in text, an `alignment` or `textFormat` it does not know
    and a `direction` that is not auto/ltr/rtl (read as auto)."""
    if not isinstance(field, dict):
        return ["%s is not an object" % where]
    problems = []
    if named and not isinstance(field.get("name"), str):
        problems.append("%s has no text `name`" % where)
    ftype = field.get("type")
    if not isinstance(ftype, str):
        problems.append("%s has no text `type`" % where)
    elif ftype not in _PDFME_FIELD_TYPES:
        hint = " -- use 'table'" if ftype == "list" else ""
        problems.append("%s has type %s, which the renderer does not have (it has: %s)%s" % (where, _shown_name(ftype, 40), _PDF_FIELD_TYPES_TEXT, hint))
    position = field.get("position")
    if not (isinstance(position, dict) and _is_number(position.get("x")) and _is_number(position.get("y"))):
        problems.append("%s has no `position` with numbers x and y" % where)
    for key in ("width", "height"):
        if not _is_number(field.get(key)):
            problems.append("%s has no number `%s`" % (where, key))
    if "readOnly" in field and not isinstance(field["readOnly"], bool):
        problems.append("%s has a `readOnly` that is not true/false" % where)
    if "rotate" in field and not _is_number(field["rotate"]):
        problems.append("%s has a `rotate` that is not a number" % where)
    return problems


def _pdf_base_problems(base):
    """The base of a pdfme template is a blank page -- numbers `width` and `height` and `padding` of four numbers (and a list `staticSchema`, if
    there) -- or a PDF, given as text. Anything else makes the renderer refuse the template."""
    if isinstance(base, str):
        return [] if base.strip() else ["`basePdf` is an empty text"]
    if not isinstance(base, dict):
        return ["`basePdf` is neither a blank page ({width, height, padding}) nor a PDF"]
    problems = ["`basePdf` has no number `%s`" % key for key in ("width", "height") if not _is_number(base.get(key))]
    padding = base.get("padding")
    if not (isinstance(padding, list) and len(padding) == 4 and all(_is_number(x) for x in padding)):
        problems.append("`basePdf.padding` is not four numbers")
    if "staticSchema" in base and not isinstance(base["staticSchema"], list):
        problems.append("`basePdf.staticSchema` is not a list")
    return problems


def _pdf_template_problems(obj):
    """Why the renderer refuses a pdfme template as a whole (see _pdf_field_problems): a base that is a blank page or a PDF (_pdf_base_problems),
    `schemas` a list of pages, a page a list of fields (or, the legacy way, an object whose values are fields)."""
    problems = _pdf_base_problems(obj.get("basePdf"))
    schemas = obj.get("schemas")
    if not isinstance(schemas, list):
        return problems + ["`schemas` is not a list of pages"]
    for number, page in enumerate(schemas, 1):
        if isinstance(page, list):
            for index, field in enumerate(page, 1):
                problems.extend(_pdf_field_problems(field, "field %d of page %d" % (index, number)))
        elif isinstance(page, dict):
            for key, field in page.items():
                problems.extend(_pdf_field_problems(field, "field %s of page %d" % (_shown_name(key, 30), number), named=False))
        else:
            problems.append("page %d is not a list of fields" % number)
    return problems


_AUTO_MAIL_ALIASES = {"userRegistration", "passwordRecover", "companyInvitation", "eventReminder"}
_PDF_GET_RE = re.compile(r"service\.report\.pdf\.get\.(\w+)")
_MAIL_ALIAS_RE = re.compile(r"service\.(?:report\.pdf\.email|notification\.mail)\.(\w+)")
_PLACEHOLDER_RE = re.compile(r"\{\{([^{}]*)\}\}")
_NEXTVAL_RE = re.compile(r"nextval\('[^']*?\.?\"?([A-Za-z0-9_]+)\"?'::regclass\)")


def _list_of(rep, key, r=None):
    """A collection of the project's export, as a list: what is not a list is no collection (an ERROR, when there is a report to say it on)."""
    value = rep.get(key)
    if isinstance(value, list):
        return value
    if value is not None and r is not None:
        r.err("%s is not a list. (15)" % key)
    return []


def _check_templates(p, r):
    """PDF/mail template integrity: duplicate alias/name (2nd won't save → ERROR); a pdfme `templateJson` that is
    invalid JSON or lacks basePdf/schemas → ERROR; one the renderer refuses (`schemas` not a list of pages of
    fields, a field without a text name, one of the renderer's types, a position and a size, or of an unknown type —
    `list` is not one, use `table`) → ERROR, because then the WHOLE PDF fails; no fields at all → WARN (blank);
    a mail `{{placeholder}}` with a non-word char (incl. surrounding spaces) that is never substituted → WARN; a
    rule referencing `service.report.pdf.get.<alias>` / mail alias with no backing template → WARN."""
    from collections import Counter
    rep = p.rep
    mails = [m for m in _list_of(rep, "mailTemplates", r) if isinstance(m, dict)]
    pdfs = [t for t in _list_of(rep, "pdfTemplates", r) if isinstance(t, dict)]
    for coll in ("mailTemplates", "pdfTemplates"):
        for i, x in enumerate(_list_of(rep, coll), 1):
            if not isinstance(x, dict):
                r.err("%s[%d] is not an object. (15)" % (coll, i))
    for coll, items in (("mailTemplate", mails), ("pdfTemplate", pdfs)):
        for key in ("alias", "name"):
            for v, c in Counter(x.get(key) for x in items if isinstance(x.get(key), str) and x.get(key)).items():
                if c > 1:
                    r.err("%s %s %r appears %d times — duplicate key; the 2nd won't save. (15 §3.5)" % (coll, key, v, c))
    for t in pdfs:
        tj = t.get("templateJson")
        obj = None
        if isinstance(tj, str):
            try:
                obj = json.loads(tj)
            except (json.JSONDecodeError, RecursionError):  # (the parser gives up on a text nested deeper than it reads)
                r.err("pdfTemplate %r templateJson is not valid JSON, or is nested too deep to be a template. (15)" % t.get("alias"))
                continue
        elif isinstance(tj, dict):
            obj = tj
        if not isinstance(obj, dict) or "basePdf" not in obj or "schemas" not in obj:
            r.err("pdfTemplate %r templateJson missing basePdf/schemas (not a pdfme template). (15)" % t.get("alias"))
            continue
        problems = _pdf_template_problems(obj)
        if problems:
            r.err("pdfTemplate %r is refused by the renderer, so every render of it fails as a whole (no PDF at all): %s%s. (15)"
                  % (t.get("alias"), "; ".join(problems[:3]), " (and %d more)" % (len(problems) - 3) if len(problems) > 3 else ""))
            continue
        schemas = obj["schemas"]
        if not any((page if isinstance(page, list) else list(page.values())) for page in schemas):
            r.warn("pdfTemplate %r has no fields on any page — renders blank. (15)" % t.get("alias"))
    for m in mails:
        for fld in ("htmlContent", "subject"):
            # Strip HTML comments first — a `{{...}}` inside <!-- ... --> (e.g. an author note about placeholder
            # scanning) is never rendered, so it must not be flagged as an unsubstituted placeholder.
            content = re.sub(r"<!--.*?-->", "", m.get(fld) or "", flags=re.DOTALL)
            for mt in _PLACEHOLDER_RE.finditer(content):
                inner = mt.group(1)
                if inner and (inner != inner.strip() or re.search(r"[^A-Za-z0-9_ ]", inner)):
                    r.warn("mailTemplate %r %s placeholder {{%s}} has a non-word char / surrounding space — it is never substituted. (15)" % (m.get("alias"), fld, inner))
    mail_aliases = {m.get("alias") for m in mails if isinstance(m.get("alias"), str)} | _AUTO_MAIL_ALIASES
    pdf_aliases = {t.get("alias") for t in pdfs if isinstance(t.get("alias"), str)}
    sources = [("rule %r" % rl.get("name"), (rl.get("rule") or {}).get("ruleScriptStr", "") if isinstance(rl.get("rule"), dict) else "")
               for rl in _list_of(rep, "rules") if isinstance(rl, dict)]
    for label, body in sources:
        for mt in _PDF_GET_RE.finditer(body or ""):
            if mt.group(1) not in pdf_aliases:
                r.warn("%s references service.report.pdf.get.%s but no PDF template has that alias. (15 §4.8)" % (label, mt.group(1)))
        for mt in _MAIL_ALIAS_RE.finditer(body or ""):
            if mt.group(1) not in mail_aliases:
                r.warn("%s references mail alias %s but no mail template has it. (15 §4.8)" % (label, mt.group(1)))


def _check_db_dump(p, r):
    """project-db.dump integrity: **any `rows[]` cell that is not a JSON string or null → ERROR** (the restore
    casts every cell to String; a JSON number/boolean throws ClassCastException, which escapes the per-table
    savepoint and rolls back the WHOLE schema — "The database was NOT replaced"); a non-numeric `columnTypes`
    entry or `sequences[].lastValue` → ERROR (both are read as `Number`); a table whose `columns` and
    `columnTypes` parallel arrays differ in length → ERROR; a DDL `DEFAULT nextval('<seq>')` naming a sequence
    not in that schema's `sequences[]` → ERROR; a dump `database` name disagreeing with project-db-meta.json /
    a crud's sourceDb → WARN."""
    try:
        db = p.db
    except Exception:
        return
    if not isinstance(db, dict):
        return
    dbname = db.get("database")
    import os
    meta_path = p.path("project-db-meta.json")
    if dbname and os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            if meta.get("databaseName") and meta["databaseName"] != dbname:
                r.warn("project-db.dump.database %r != project-db-meta.json.databaseName %r. (10)" % (dbname, meta["databaseName"]))
        except (ValueError, OSError):
            pass
    if dbname:
        for c in (p.cruds_file.data.get("cruds", []) if p.cruds_file else []) or []:
            if c.get("sourceDb") and c["sourceDb"] != dbname:
                r.warn("crud %r sourceDb %r != dump database %r (import rebinds INTERNAL sources, but a stale name can leak). (10)" % (c.get("alias"), c["sourceDb"], dbname))
    # Every cell of every table, against the restorer's own signature. See the block comment
    # over db_cmds.dump_cell: restoreSingleSchema reads rows as List<Map<String,String>> and
    # assigns each cell to a `String val`, so a JSON number/boolean throws ClassCastException
    # there. That is NOT an SQLException, so it escapes the per-table savepoint catch and
    # unwinds the WHOLE schema — the import reports "The database was NOT replaced.
    # Schema(s) [x] were rolled back ... Cause: class java.lang.Integer cannot be cast to
    # class java.lang.String" and not one business row lands. Nothing else in this toolkit sees
    # it: `db verify`/`crud verify` load the dump with Python's json, where 1 and "1" behave
    # alike, and every dump EXPORTED by the platform is string-typed by construction
    # (`val.toString()`), so only a hand-built or generated dump can carry it.
    bad_cells = []
    for sch in db.get("schemas", []) or []:
        seqs = {s.get("name") for s in sch.get("sequences", []) or []}
        for sq in sch.get("sequences", []) or []:
            lv = sq.get("lastValue")
            if lv is not None and (isinstance(lv, bool) or not isinstance(lv, (int, float))):
                r.err("sequence %s.%s lastValue is %s, must be a JSON NUMBER — the restore reads it as (Number). (10)"
                      % (sch.get("name"), sq.get("name"), type(lv).__name__))
        for t in sch.get("tables", []) or []:
            cols = t.get("columns") or []
            ctypes = t.get("columnTypes") or []
            if len(cols) != len(ctypes):
                r.err("table %s.%s: %d columns but %d columnTypes (must be parallel arrays). (10)" % (sch.get("name"), t.get("name"), len(cols), len(ctypes)))
            for ct in ctypes:
                if isinstance(ct, bool) or not isinstance(ct, (int, float)):
                    r.err("table %s.%s columnTypes carries %r — every entry must be a JSON NUMBER (a JDBC java.sql.Types code); the restore reads them as List<Number>. (10)"
                          % (sch.get("name"), t.get("name"), ct))
                    break
            for mt in _NEXTVAL_RE.finditer(t.get("ddl") or ""):
                if mt.group(1) not in seqs:
                    r.err("table %s.%s DDL DEFAULT nextval references sequence %r not in this schema's sequences[]. (10)" % (sch.get("name"), t.get("name"), mt.group(1)))
            for row in t.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                for col, val in row.items():
                    if val is None or isinstance(val, str):
                        continue
                    bad_cells.append(("%s.%s" % (sch.get("name"), t.get("name")), col,
                                      type(val).__name__, val))
    if bad_cells:
        where = {}
        for tbl, col, tname, val in bad_cells:
            where.setdefault((tbl, col, tname), [0, val])[0] += 1
        shown = sorted(where.items(), key=lambda kv: -kv[1][0])
        r.err("project-db.dump carries %d row value(s) that are NOT strings — the restore does "
              "`String val = row.get(col)` and a JSON %s throws ClassCastException, which is not an "
              "SQLException, so the ENTIRE schema rolls back and the import reports \"The database "
              "was NOT replaced\". Every cell must be a JSON string or null; the JDBC codes in "
              "columnTypes do the typing (\"1\" -> integer). Fix at the source with "
              "db_cmds.normalise_rows(columns, rows) / db_cmds.dump_cell(v). Offenders: %s. (10 / 00 §7)"
              % (len(bad_cells), shown[0][0][2],
                 "; ".join("%s.%s %s x%d e.g. %r" % (k[0], k[1], k[2], v[0], v[1])
                           for k, v in shown[:8])
                 + (" ; +%d more" % (len(shown) - 8) if len(shown) > 8 else "")))


_OBJNODE = "com.fasterxml.jackson.databind.node.ObjectNode"
# dataClass whitelists for the UNAMBIGUOUS single-variant controls only (verified against every reference export).
# Dropdown/Text/Autocomplete/List/File accept many classes and are deliberately excluded.
_DATACLASS_WHITELIST = {
    "dynaform.form.datepicker.field.plugin": {"java.time.Instant", "java.time.LocalDate", "java.time.LocalDateTime", _OBJNODE, None},
    "dynaform.form.textarea.field.plugin": {"java.lang.String", _OBJNODE, None},
    "dynaform.form.comments.field.plugin": {_OBJNODE, None},
    "dynaform.form.gantt.chart.plugin": {_OBJNODE, None},
}

# The value type a form control's dataClass binds it as — the names an Html Field declares in `fieldModel.types`
# and its script reads as `ctx.field.type` (doc 24e §2). No dataClass is JSON: any value, as stored.
_VALUE_TYPE_BY_DATACLASS = {
    "java.lang.String": "STRING",
    "java.lang.Integer": "INTEGER",
    "java.lang.Long": "LONG",
    "java.lang.Short": "SHORT",
    "java.lang.Byte": "BYTE",
    "java.math.BigInteger": "BIG_INTEGER",
    "java.lang.Double": "DOUBLE",
    "java.lang.Float": "FLOAT",
    "java.math.BigDecimal": "BIG_DECIMAL",
    "java.lang.Boolean": "BOOLEAN",
    "java.time.LocalDate": "LOCAL_DATE",
    "java.time.LocalDateTime": "LOCAL_DATE_TIME",
    "java.time.Instant": "INSTANT",
    _OBJNODE: "OBJECT_NODE",
    "com.fasterxml.jackson.databind.node.ArrayNode": "ARRAY_NODE",
    "java.util.List": "ARRAY_LIST",
    "java.util.ArrayList": "ARRAY_LIST",
    "com.fasterxml.jackson.databind.JsonNode": "JSON",
}
# What an Html Field may declare: every type a field can be bound as except the untyped JSON node.
_HTML_FIELD_TYPES = frozenset(v for v in _VALUE_TYPE_BY_DATACLASS.values() if v != "JSON")
# A component program that writes its value: it names the field and calls a writer — ctx.field.set(v), or an alias
# (`const f = ctx.field; … f.set(v)`), possibly in another of the component's scripts.
_FIELD_REF_RE = re.compile(r"\bfield\b")
_FIELD_WRITE_RE = re.compile(r"\.\s*(?:set|commit)\s*\(")


def _check_form_control_config(p, r):
    """Per-control config sanity: a Date-Picker/Text-Area/Comments/Gantt whose `dataClass` isn't one it can render
    → **ERROR** (blank control); a dropdown carrying BOTH `enumName` and a `ruleIdentifier` (an enum dropdown must
    have no choices rule) → WARN; `between:true` with no `betweenMapping` → WARN (range TO side unbound); a
    rule-mode default (`defaultValueStatic:false`) with no `defaultValueRuleIdentifier` → WARN; an enum dropdown
    whose `key`/`displayName` names a property absent from its `enumValues` snapshot → WARN (silent fallback)."""
    for n, pn, st in _iter_control_settings(p):
        field = st.get("fieldExpression") or st.get("name") or n.get("name")
        wl = _DATACLASS_WHITELIST.get(pn)
        if wl is not None and st.get("dataClass") not in wl:
            r.err("field %r (%s) dataClass %r is not a class this control renders (%s) — the control renders blank. (02-form-controls-reference.md)"
                  % (field, pn.split(".")[-3], st.get("dataClass"), sorted(x for x in wl if x)))
        if pn == "dynaform.form.text.field.plugin" and not (st.get("dataClass") or "").strip():
            r.warn("text field %r has NO dataClass — the platform treats the value as a raw JSON node, so the "
                   "value renders JSON-QUOTED in the form (\"Value\" instead of Value, e.g. edit an existing row). "
                   "Every working export sets a concrete class: use java.lang.String for text, "
                   "java.lang.Integer/Long/Boolean for numeric/bool. (02-form-controls-reference.md / 03)" % field)
        if pn == "dynaform.form.rimm.drop.down.field.plugin" and st.get("enumName") and st.get("ruleIdentifier"):
            r.warn("enum dropdown %r has BOTH enumName and a ruleIdentifier — an enum dropdown must carry no choices rule (the enum snapshot IS the source). (02)" % field)
        if st.get("between") is True and not st.get("betweenMapping"):
            r.warn("field %r has between:true but no betweenMapping — the range's TO bound is unmapped. (02)" % field)
        if st.get("defaultValueEnabled") is True and st.get("defaultValueStatic") is False and _blank(st.get("defaultValueRuleIdentifier")):
            r.warn("field %r has a rule-mode default (defaultValueStatic:false) but no defaultValueRuleIdentifier — the default is silently never applied. (02)" % field)
        if st.get("enumName") and isinstance(st.get("enumValues"), dict) and st["enumValues"]:
            props = set(st.get("enumFieldNames") or [])
            for inner in st["enumValues"].values():
                if isinstance(inner, dict):
                    props |= set(inner.keys())
            for k in ("key", "displayName"):
                v = st.get(k)
                if v and v != "name" and props and v not in props:
                    r.warn("enum dropdown %r %s %r is not a property in the enumValues snapshot (%s) — silent fallback to the constant name. (02)"
                           % (field, k, v, sorted(props)[:6]))


def _html_field_bound_type(st):
    """The type an Html Field's binding hands its script: the type inside a JSON column when it projects into one,
    STRING for an enum-bound field, the dataClass's type otherwise, JSON with no dataClass — the platform's own
    resolution. None for a class this table does not know (nothing to compare)."""
    if st.get("jsonNodeExpression") and st.get("dataClass") in (_OBJNODE, "com.fasterxml.jackson.databind.JsonNode") \
            and st.get("jsonNodeValueType"):
        return _VALUE_TYPE_BY_DATACLASS.get(st.get("jsonNodeValueType"))
    if st.get("enumName") or (isinstance(st.get("enumValues"), dict) and st["enumValues"]):
        return "STRING"
    if not st.get("dataClass"):
        return "JSON"
    return _VALUE_TYPE_BY_DATACLASS.get(st.get("dataClass"))


def _check_html_field(p, r):
    """HTML FIELD (WARN). An Html Field (`dynaform.form.html.field.plugin`, doc 24e) is a form control whose input
    is a studio component, and what it submits is exactly what its script writes with `ctx.field.set(…)`. The
    platform reads the field's value contract leniently and converts the submitted value strictly by the binding,
    so each of these imports clean and surfaces only on a live submit:
      * a `fieldModel` that is not `{"types": [...]}`, or a type in it that no field can be bound as (`JSON`
        included — it cannot be declared) — the platform ignores it, so the field accepts ANY type;
      * a binding (its dataClass, or its jsonNodeValueType inside a JSON column) of a type the component does not
        declare — the script is handed a type it was not written for (the studio's Value tab warns the same);
      * no enabled script, or none that ever writes the value (`field` + a `.set(`/`.commit(` call anywhere in the
        component's program, which all its scripts share) — the field only ever submits the value it was drawn
        with, so nothing the user does reaches the record."""
    for n, pn, st in _iter_control_settings(p):
        if pn != _HTML_FIELD:
            continue
        name = st.get("name") or n.get("name") or n.get("identifier")
        props = n.get("properties") or {}

        declared = set()
        raw = (props.get("fieldModel") or {}).get("stringValue")
        if raw:
            try:
                model = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                model = None
                r.warn("html field %r: fieldModel is not valid JSON (%s) — the platform ignores it and the field "
                       "accepts ANY type. (24e §2)" % (name, exc))
            if model is not None:
                types = model.get("types") if isinstance(model, dict) else None
                if not isinstance(model, dict) or (types is not None and not isinstance(types, list)):
                    r.warn("html field %r: fieldModel must be {\"types\": [<type>, …]} — the platform ignores it and "
                           "the field accepts ANY type. (24e §2)" % name)
                else:
                    for t in types or []:
                        if isinstance(t, str) and t in _HTML_FIELD_TYPES:
                            declared.add(t)
                        else:
                            r.warn("html field %r: fieldModel type %r is not one a field can be bound as (%s) — "
                                   "the platform ignores it. (24e §2)"
                                   % (name, t, ", ".join(sorted(_HTML_FIELD_TYPES))))

        bound = _html_field_bound_type(st)
        if declared and bound and bound != "JSON" and bound not in declared:
            r.warn("html field %r is bound as %s (dataClass %r) but its fieldModel declares only %s — the script is "
                   "handed a type it was not written for. Declare it, or bind a field of a declared type. (24e §2)"
                   % (name, bound, st.get("dataClass"), ", ".join(sorted(declared))))

        scripts = []
        sm = (props.get("studioModel") or {}).get("stringValue")
        try:
            studio = json.loads(sm) if sm else None
        except (json.JSONDecodeError, TypeError):
            studio = None                     # already reported as malformed studioModel JSON
        if isinstance(studio, dict):
            scripts = [s for s in studio.get("scripts") or []
                       if isinstance(s, dict) and s.get("enabled") is not False]
        program = "\n".join(_strip_groovy_comments(s.get("code") or "") for s in scripts)
        if not (_FIELD_REF_RE.search(program) and _FIELD_WRITE_RE.search(program)):
            r.warn("html field %r has %s — it only ever submits the value it was drawn with, so nothing the user "
                   "does reaches the record. Write the value with ctx.field.set(value). (24e §3)"
                   % (name, "no enabled script" if not scripts else "no script that writes ctx.field"))


_SETTING_ATTR_RE = re.compile(r"""\bdata-setting\s*=\s*(?:"([^"]+)"|'([^']+)')""")
_SELECT_TAG_RE = re.compile(r"<select\b[^>]*>", re.I)
_SETTINGS_WRITE_RE = re.compile(r"\bsettings\s*\.\s*(?:set|commit)\s*\(")
_CATALOG_KINDS = ("rules", "cruds", "fields", "methods", "contexts")
_CATALOG_RULE_TYPES = ("PREDICATE", "EXECUTION_RULE", "VALIDATION_RULE")


def _tag_attr(tag, name):
    m = re.search(r"""\b%s\s*=\s*(?:"([^"]*)"|'([^']*)')""" % re.escape(name), tag)
    return None if not m else (m.group(1) if m.group(1) is not None else m.group(2))


def _enabled_program(node):
    """Every enabled script of a studio component, comments stripped, as the one program they are."""
    sm = ((node.get("properties") or {}).get("studioModel") or {}).get("stringValue")
    try:
        studio = json.loads(sm) if sm else None
    except (json.JSONDecodeError, TypeError):
        studio = None                         # reported elsewhere as a malformed studioModel
    scripts = [] if not isinstance(studio, dict) else [
        s for s in studio.get("scripts") or [] if isinstance(s, dict) and s.get("enabled") is not False]
    return "\n".join(_strip_groovy_comments(s.get("code") or "") for s in scripts)


def _check_html_field_sections(p, r):
    """HTML FIELD SETTINGS (WARN). An Html Field's own settings are written by its settings sections — child nodes
    `dynaform.html.field.section.plugin` drawn in the field's settings drawer (doc 24e §5) — into
    `settings.custom`, which the field's script reads as `ctx.settings`. Each of these imports clean and shows only in
    the drawer or at run time:
      * `settings.custom` that is not a JSON object — the platform drops it, so the field reads only defaults;
      * a section that is not a child of an Html Field — no drawer draws it, it configures nothing;
      * a `sectionModel` that is not {"icon": …, "defaults": {…}} — ignored: no icon, no defaults;
      * a section that writes nothing — no `data-setting` control and no `ctx.settings.set(…)`;
      * a `<select data-catalog>` the catalog cannot fill — an unknown kind, a rule type that does not exist (the
        catalog refuses it), `fields`/`methods` with neither `data-crud` nor `data-crud-setting` (stays empty);
      * a rule picked through `data-catalog="rules"` that is not in rules[], or not of the type the list asks for —
        the drawer shows it as missing and the field's script calls a rule that is not there."""
    types = _rule_types(p)
    for node, parent, _path in core.iter_nodes(p.root_content):
        pn = node.get("pluginName")
        if pn == _HTML_FIELD:
            try:
                st = core.get_inner_json(node, "settings")
            except core.ToolError:
                continue
            custom = st.get("custom") if isinstance(st, dict) else None
            if isinstance(custom, str):
                try:
                    custom = json.loads(custom)
                except json.JSONDecodeError:
                    custom = False
            if custom is not None and not isinstance(custom, dict):
                r.warn("html field %r: settings.custom must be a JSON object of the values its settings sections "
                       "wrote — the platform drops anything else, and the field reads only the defaults. (24e §5)"
                       % (st.get("name") or node.get("name")))
            continue
        if pn != _HTML_FIELD_SECTION:
            continue
        title = node.get("name") or node.get("identifier")
        field_custom = {}
        if not parent or parent.get("pluginName") != _HTML_FIELD:
            r.warn("settings section %r is not a child of an html field (%s) — no settings drawer draws it, so it "
                   "configures nothing. (24e §5)" % (title, _HTML_FIELD))
        else:
            try:
                pst = core.get_inner_json(parent, "settings")
            except core.ToolError:
                pst = {}
            c = pst.get("custom") if isinstance(pst, dict) else None
            if isinstance(c, str):
                try:
                    c = json.loads(c)
                except json.JSONDecodeError:
                    c = None
            field_custom = c if isinstance(c, dict) else {}

        raw = ((node.get("properties") or {}).get("sectionModel") or {}).get("stringValue")
        if raw:
            try:
                model = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                model = None
                r.warn("settings section %r: sectionModel is not valid JSON (%s) — ignored: no icon, no defaults. "
                       "(24e §5)" % (title, exc))
            if model is not None and (not isinstance(model, dict)
                                      or isinstance(model.get("icon"), (dict, list))):
                r.warn("settings section %r: sectionModel must be {\"icon\": \"<css classes>\", \"defaults\": "
                       "{<key>: <value>}} — the platform ignores all of it: no icon, no defaults. (24e §5)" % title)
            elif isinstance(model, dict) and model.get("defaults") is not None:
                defaults = model["defaults"]
                if isinstance(defaults, str):           # the platform unwraps an object stored as a JSON string
                    try:
                        defaults = json.loads(defaults)
                    except json.JSONDecodeError:
                        defaults = None
                if not isinstance(defaults, dict):
                    r.warn("settings section %r: sectionModel.defaults must be a JSON object — the platform drops "
                           "them (the icon stays), so every key it writes reads only the script's fallback. "
                           "(24e §5)" % title)

        html = _html_of(node)
        keys = {a or b for a, b in _SETTING_ATTR_RE.findall(html)}
        if not keys and not _SETTINGS_WRITE_RE.search(_enabled_program(node)):
            r.warn("settings section %r writes nothing — no data-setting control in its html and no "
                   "ctx.settings.set(…) in its scripts, so the field's settings never change. (24e §5)" % title)

        for tag in _SELECT_TAG_RE.findall(html):
            kind = _tag_attr(tag, "data-catalog")
            if kind is None:
                continue
            kind = kind.strip().lower()
            key = _tag_attr(tag, "data-setting")
            if kind not in _CATALOG_KINDS:
                r.warn("settings section %r: data-catalog=%r is not a list the catalog has (%s) — the list stays "
                       "as written. (24e §5)" % (title, kind, ", ".join(_CATALOG_KINDS)))
                continue
            if kind in ("fields", "methods") and _tag_attr(tag, "data-crud") is None \
                    and _tag_attr(tag, "data-crud-setting") is None:
                r.warn("settings section %r: data-catalog=%r on %r names no CRUD (data-crud=\"<alias>\" or "
                       "data-crud-setting=\"<key>\") — the list stays empty. (24e §5)" % (title, kind, key))
            wanted = [t.strip().upper() for t in (_tag_attr(tag, "data-rule-type") or "").split(",") if t.strip()]
            bad = [t for t in wanted if t not in _CATALOG_RULE_TYPES]
            if kind == "rules" and bad:
                r.warn("settings section %r: data-rule-type %s is not a rule type (%s) — the catalog refuses the "
                       "list. (24e §5)" % (title, ", ".join(bad), ", ".join(_CATALOG_RULE_TYPES)))
            picked = field_custom.get(key) if key else None
            if kind == "rules" and isinstance(picked, str) and picked:
                if picked not in types:
                    r.warn("html field settings: %r = %r (picked in section %r) is not a rule in rules[] — the "
                           "drawer shows it as missing and the field's script calls a rule that is not there. "
                           "(24e §5)" % (key, picked, title))
                elif wanted and not bad and types.get(picked) not in wanted:
                    r.warn("html field settings: %r = %r (picked in section %r) is a %s, but the list offers only "
                           "%s. (24e §5)" % (key, picked, title, types.get(picked), ", ".join(wanted)))


_TABLE_PLUGINS = ("crud.table.plugin", "crud.tree.plugin", "process.table.pluin")


def _iter_table_models(p):
    """yield (node, pluginName, model_dict) for every crud.table/crud.tree/process.table node."""
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") not in _TABLE_PLUGINS:
            continue
        prop = (n.get("properties") or {}).get("model")
        if not (isinstance(prop, dict) and prop.get("stringValue")):
            continue
        try:
            md = json.loads(prop["stringValue"])
        except json.JSONDecodeError:
            continue
        if isinstance(md, dict):
            yield n, n["pluginName"], md


def _actions(md, *groups):
    for g in groups:
        grp = md.get(g)
        acts = grp.get("actions") if isinstance(grp, dict) else (grp if isinstance(grp, list) else [])
        for a in acts or []:
            if isinstance(a, dict):
                yield g, a


def _id_index(p):
    idx = {}
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        i = n.get("identifier")
        if isinstance(i, str) and i not in idx:
            idx[i] = n
    return idx


def _check_table_action_refs(p, r):
    """crud.table/crud.tree action integrity: a Create/Edit action's `formGroupIdentifier` that resolves to no
    formGroup → **ERROR** (the button opens nothing); its `onBeforeStartRuleIdentifier`/`onBeforeCompleteRuleIdentifier`/
    `predicateIdentifier` that resolves to no rule → WARN (silent); `direct` written as the wrong JSON type
    (bool for crud tables, 'on'/'off' string for process tables) → WARN. Also process.table globalActions with a
    blank predicateIdentifier → WARN (fail-closed: never shown, cannot execute)."""
    rule_ids = set(_rule_types(p))
    fg_ids = {f.get("identifier") for f in p.rep.get("formGroups", []) or []}
    for n, pn, md in _iter_table_models(p):
        nm = n.get("name")
        if pn in ("crud.table.plugin", "crud.tree.plugin"):
            for g, a in _actions(md, "createActions", "editActions"):
                fgi = a.get("formGroupIdentifier")
                if fgi and isinstance(fgi, str) and fgi.strip() and fgi not in fg_ids:
                    r.err("%s %r %s action %r formGroupIdentifier %s resolves to no formGroup — the button opens nothing. (06-form-groups-and-mapping.md)"
                          % (pn, nm, g, a.get("id"), fgi))
                for rk in ("onBeforeStartRuleIdentifier", "onBeforeCompleteRuleIdentifier", "predicateIdentifier"):
                    v = a.get(rk)
                    if v and isinstance(v, str) and v.strip() and v not in rule_ids:
                        r.warn("%s %r action %r %s %s resolves to no rule — the guard/hook silently never runs. (04/05)"
                               % (pn, nm, a.get("id"), rk, v))
                if a.get("direct") is not None and not isinstance(a.get("direct"), bool):
                    r.warn("%s %r action %r `direct` is %s, not a bool (crud tables use a boolean). (04/05)"
                           % (pn, nm, a.get("id"), type(a.get("direct")).__name__))
        else:  # process.table.pluin
            for g, a in _actions(md, "userStartProcessActions", "globalActions"):
                if a.get("direct") is not None and not isinstance(a.get("direct"), str):
                    r.warn("process.table %r action %r `direct` is %s, not a string 'on'/'off'. (05)"
                           % (nm, a.get("id"), type(a.get("direct")).__name__))
            for g, a in _actions(md, "globalActions"):
                if _blank(a.get("predicateIdentifier")):
                    r.warn("process.table %r globalAction %r has a blank predicateIdentifier — it is NEVER shown and cannot execute (fail-closed: the plugin skips predicate-less globalActions both when listing and when executing them). Give it a predicate; use a `return true` PREDICATE rule for always-visible. (05)"
                           % (nm, a.get("id")))


def _check_action_persist(p, r):
    """SUBMITS-BUT-SAVES-NOTHING (WARN). A crud.table/crud.tree **Create/Edit/Delete** action must carry an
    `onBeforeCompleteRuleIdentifier` that actually WRITES to the DB. The platform's "Create Default Actions"
    wires create -> a create rule, edit -> an update rule, delete(direct) -> a delete rule, each
    `context.<ctx>.<crud>.service.create/update/delete(...)`. **A create/edit form action with NO
    onBeforeCompleteRule opens, fills, submits — and saves NOTHING** (silent; import/validate/coverage/crud-verify
    all pass). A direct action with neither a form group nor an onBeforeCompleteRule does nothing on click. Only a
    live open reveals it — so flag it offline. (06-form-groups-and-mapping.md / 04-crud-table-plugin.md)
    Also WARNs the other way round: `submitForm==false` + an `onBeforeCompleteRuleIdentifier` is a DEAD rule —
    submitForm:false skips validation AND rule execution and just redirects back, so the button is a Back with
    the action's branding. Deliberately NOT flagged: `submitForm==false` with no rule (a legitimate read-only
    drill-down); process.table userStartProcessActions (persist via the workflow); actions with neither a form
    group nor `direct`."""
    for node, pn, md in _iter_table_models(p):
        if pn == "process.table.pluin":
            continue  # workflow-start / global actions persist via the process, not onBeforeComplete
        alias = md.get("crudAlias") or node.get("name")
        for grp, a in _actions(md, "createActions", "editActions", "deleteActions"):
            name = (a.get("localizedNames") or {}).get("en_US") or a.get("id", "")[:8]
            is_direct = a.get("direct") in (True, "on")
            has_fg = bool(a.get("formGroupIdentifier"))
            submits = a.get("submitForm") is not False
            if a.get("onBeforeCompleteRuleIdentifier"):
                if not is_direct and not submits:
                    r.warn("action %r on CRUD %r has submitForm:false AND an onBeforeCompleteRuleIdentifier — that "
                           "rule NEVER runs. submitForm:false skips validation AND rule execution and redirects "
                           "back, so the button is a Back with the action's branding. An action that must fire a "
                           "rule has to be direct:true (or drop submitForm). (04-crud-table-plugin.md)"
                           % (name, alias))
                continue  # has a persist/complete hook — refs checked by _check_table_action_refs
            if has_fg and submits:
                r.warn("action %r on CRUD %r opens a form (formGroupIdentifier set) but has NO "
                       "onBeforeCompleteRuleIdentifier — the form submits and SAVES NOTHING. Wire a persist rule "
                       "(EXECUTION_RULE, context-scoped: `context.<ctx>.<crud>.service.create/update(...)`), like "
                       "Create Default Actions. (06-form-groups-and-mapping.md / 04-crud-table-plugin.md)"
                       % (name, alias))
            elif is_direct and not has_fg:
                r.warn("direct action %r on CRUD %r has neither a form group nor an onBeforeCompleteRuleIdentifier "
                       "— clicking it does nothing (a Delete needs `context.<ctx>.<crud>.service.delete(...data.get().id)`). "
                       "(06-form-groups-and-mapping.md / 04-crud-table-plugin.md)" % (name, alias))


def _check_settings_mirror(p, r):
    """Every crud.table/crud.tree/process.table node must have a `rep-objects.settings[]` mirror keyed by
    `setting.name == node.uniqueIdentifier`. The table itself renders from properties.model, not from the mirror;
    without the mirror a form opened from one of its actions gets no action/breadcrumb context and the author-side
    settings panel opens empty. WARN."""
    setting_names = {s.get("name") for s in p.rep.get("settings", []) or []}
    for n, pn, _md in _iter_table_models(p):
        if n.get("id") is not None:
            continue  # inherited baseline scaffold (non-null id) — not builder-authored; only NEW nodes (id=null) need a fresh mirror
        uid = n.get("uniqueIdentifier")
        if uid and uid not in setting_names:
            r.warn("%s %r has no settings[] mirror (no entry with name==%s) — it still renders (from "
                   "properties.model), but forms opened from its actions lose their action/breadcrumb context "
                   "and the settings panel opens empty. (12 §6.1)" % (pn, n.get("name"), uid))


def _check_process_table(p, r):
    """process.table.pluin traps (05):
    (a) a userStartProcessAction/globalAction with a flat `name` and no `localizedNames` renders a BLANK button
        (the user-task action record ignores `name`);
    (b) the node model is OUT OF SYNC with its rep-objects.settings mirror — the runtime renders the model
        but the author-side SETTINGS PANEL reads the mirror by uniqueIdentifier,
        so a stale mirror shows baseline-placeholder junk in the editor."""
    settings_by_name = {s.get("name"): s for s in p.rep.get("settings", []) or [] if s.get("type") == "ProcessTable"}
    for n, pn, md in _iter_table_models(p):
        if pn != "process.table.pluin":
            continue
        nm = n.get("name")
        for grp in ("userStartProcessActions", "globalActions"):
            for a in ((md.get(grp) or {}).get("actions") or []):
                if isinstance(a, dict) and a.get("name") and not a.get("localizedNames"):
                    r.warn("process.table %r %s action %r uses a flat `name` and no `localizedNames` — the user-task "
                           "action record ignores `name`, so the button renders BLANK. Use `localizedNames` (a per-locale "
                           "Map). (05-crud-tree-and-process-table.md)" % (nm, grp, a.get("name")))
        mir = settings_by_name.get(n.get("uniqueIdentifier"))
        if mir is not None and isinstance(mir.get("content"), dict):
            mfe, sfe = (md.get("filterExpression") or ""), (mir["content"].get("filterExpression") or "")
            if mfe != sfe:
                r.warn("process.table %r model filterExpression %r != its settings-mirror content %r — the editor "
                       "settings panel (reads the mirror) shows a stale/different filter than the page renders. Sync "
                       "settings[name==node.uniqueIdentifier].content to the model. (05-crud-tree-and-process-table.md)"
                       % (nm, mfe, sfe))


def _check_tree_config(p, r):
    """crud.tree config: `parentFieldExpression` is a dotted DTO path but `parentFilterFieldExpression` is blank
    (a DTO path can't double as a flat filter key), or BOTH blank (no parent-child filtering) → WARN; a tree over
    a DYNAMIC crud whose methods lack `findByParent` → WARN (children never load)."""
    methods_by_alias, cruds = _dynamic_crud_methods(p)
    crud_by_alias = {c.get("alias"): c for c in cruds}
    rules_by_id = {rr.get("identifier"): rr for rr in p.rep.get("rules", []) or []}
    raw_uuid_cast = re.compile(r"IS\s+NOT\s+DISTINCT\s+FROM\s*:\w+::uuid", re.IGNORECASE)
    param_mult = re.compile(r":\w+\s*\*\s*:\w+")
    for n, pn, md in _iter_table_models(p):
        if pn != "crud.tree.plugin":
            continue
        pfe = md.get("parentFieldExpression") or ""
        pffe = md.get("parentFilterFieldExpression") or ""
        if not pfe.strip() and not pffe.strip():
            r.warn("crud.tree %r has neither parentFieldExpression nor parentFilterFieldExpression — no parent-child filtering. (05)" % n.get("name"))
        elif not pffe.strip() and "." in pfe:
            r.warn("crud.tree %r parentFieldExpression %r is a dotted DTO path but parentFilterFieldExpression is blank — a DTO path can't double as a flat filter key. (05)" % (n.get("name"), pfe))
        alias = md.get("crudAlias")
        if alias and alias in methods_by_alias and "findByParent" not in methods_by_alias[alias]:
            r.warn("crud.tree %r crud %r has no findByParent method — children never lazy-load. (05/11)" % (n.get("name"), alias))
        # EXPAND-RENDERS-EMPTY (WARN): the tree's FETCH RULE must route children to findByParent — a plain
        # find()/findAll() is WHERE 1=1, can't filter by parent, AND gets an extra undeclared parentId param on
        # expand, so expanding a node re-renders the tree EMPTY. The rule must `return
        # service.crud.<alias>.findByParent(filter)` with an explicit parentId (null=roots). Mirrors the platform's
        # the rule the platform auto-creates for a crud.tree. (05)
        frid = md.get("findRuleIdentifier")
        rule = rules_by_id.get(frid) if frid else None
        script = ((rule.get("rule") or {}).get("ruleScriptStr") or "") if rule else ""
        if script and alias and ".findByParent(" not in script and (".find(" in script or ".findAll(" in script):
            r.warn("crud.tree %r fetch rule %r calls service.crud.%s.find(...) but NOT findByParent(...) — find() is "
                   "WHERE 1=1 and can't filter children by parent, so EXPANDING a node re-renders the tree EMPTY. "
                   "The tree fetch rule must `return service.crud.%s.findByParent(filter)` with an explicit parentId "
                   "(null=roots, id=children). (05-crud-tree-and-process-table.md)"
                   % (n.get("name"), (rule.get("name") if rule else frid), alias, alias))
        # ROOT-FETCH-CRASHES (WARN): the parent-filter SQL binds parentId with a RAW `:<x>::uuid` cast. The root
        # fetch sends parentId as null/empty/`{}` (the tree's Map-arg unpack turns a null parent into an empty JSON
        # object); a raw `::uuid` cast makes the executor infer a uuid param and run UUID.fromString("{}") →
        # "Invalid UUID string" → the tree renders EMPTY / "no records found". Bind parentId as TEXT and cast
        # in-SQL. (05/11)
        crud = crud_by_alias.get(alias) if alias else None
        for m in ((crud.get("methods") or []) if crud else []):
            mn = (m.get("methodName") or "")
            sql = m.get("script") or ""
            if "parent" not in mn.lower() or (m.get("methodType") or "").upper() != "SQL":
                continue
            if raw_uuid_cast.search(sql):
                r.warn("crud.tree %r method %r filters the parent with a RAW `:<param>::uuid` cast — the ROOT fetch "
                       "sends parentId as null/empty/`{}`, and a raw ::uuid cast makes the executor run "
                       "UUID.fromString(\"{}\") → \"Invalid UUID string\" → the tree renders EMPTY / \"no records "
                       "found\". Bind parentId as TEXT and cast in-SQL: `IS NOT DISTINCT FROM "
                       "CAST(NULLIF(:parentId,'') AS uuid)` — the only shape that survives a null root parent. "
                       "(05-crud-tree-and-process-table.md / 11)" % (n.get("name"), mn))
                break
            if param_mult.search(sql):
                r.warn("crud.tree %r method %r multiplies two bind params (`:x * :y`, e.g. a paginated "
                       "`OFFSET (:pageNumber * :rowsInPage)`) — Postgres can't infer the operand types and fails with "
                       "'operator is not unique: unknown * unknown'. A tree's findByParent needs NO pagination (it "
                       "returns ALL children of a node) — drop the LIMIT/OFFSET; use a single-param SQL "
                       "`... WHERE parent_id IS NOT DISTINCT FROM CAST(NULLIF(:parentId,'') AS uuid) ORDER BY …`. "
                       "(05-crud-tree-and-process-table.md)" % (n.get("name"), mn))
                break


# A rule reaching a crud's findAll/find in EITHER calling convention:
#   service.crud.<alias>.findAll(   |   context.<ctx>.<alias>.service.findAll(   (also .find, which wraps findAll)
_FINDALL_REACH_RE = re.compile(r"(?:service\.crud\.(\w+)\.(?:findAll|find)|\.(\w+)\.service\.(?:findAll|find))\s*\(")


def _check_findall_paging_untyped(p, r):
    """A FLAT (non-tree) dynamic-CRUD findAll whose method `script` pages with the untyped
    `OFFSET (:pageNumber * :rowsInPage)` works from the UI table (paging bound as typed ints) but BREAKS the
    instant a RULE calls that crud's findAll/find (assemble / choices / fetch rules) — the rule leaves
    pageNumber/rowsInPage unbound → untyped NULL → Postgres `operator is not unique: unknown * unknown`.
    `_check_tree_config` already covers the tree `findByParent` variant; this covers a plain findAll reached from a
    rule in EITHER calling convention (`service.crud.X.findAll` or `context.<ctx>.X.service.findAll`). Fix: CAST
    both paging params in the method script (and saved query). (11-business-logic-dynamic-crud.md)"""
    _, cruds = _dynamic_crud_methods(p)
    if not cruds:
        return
    param_mult = re.compile(r":\w+\s*\*\s*:\w+")
    untyped = {}  # alias -> methodName whose script has untyped param-multiply paging
    for c in cruds:
        alias = c.get("alias")
        for m in c.get("methods") or []:
            if (m.get("methodType") or "").upper() != "SQL":
                continue
            if param_mult.search(m.get("script") or ""):
                untyped.setdefault(alias, m.get("methodName") or "findAll")
    if not untyped:
        return
    for rule in p.rep.get("rules", []) or []:
        script = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        flagged = set()
        for mt in _FINDALL_REACH_RE.finditer(script):
            alias = mt.group(1) or mt.group(2)
            if alias in untyped and alias not in flagged:
                flagged.add(alias)
                r.warn("rule %r calls findAll/find on dynamic-crud %r, whose %r method pages with the UNTYPED "
                       "`OFFSET (:pageNumber * :rowsInPage)` — a rule leaves pageNumber/rowsInPage unbound (untyped "
                       "NULL), so Postgres fails with 'operator is not unique: unknown * unknown'. Cast in the method "
                       "script AND the saved query: `OFFSET (CAST(:pageNumber AS integer) * CAST(:rowsInPage AS "
                       "integer))` — a strict superset, correct from the UI table AND a rule. "
                       "(11-business-logic-dynamic-crud.md)"
                       % (rule.get("name") or rule.get("identifier"), alias, untyped[alias]))



def _check_process_start_wiring(p, r):
    """**Who starts this process, and what makes THAT run?**

    A workflow is inert. Something has to call `service.workflow.start` or press a
    `userStartProcessActions` button, and a build can satisfy every other check in this file while
    shipping a process no human and no clock can ever open — the BPMN is valid, the worklist
    renders, the task actions are wired, and the case list is permanently empty.

    Two failures, both ERROR:
      * a workflow that **nothing starts** — no rule calls `service.workflow.start`, and no
        process.table bound to it carries a start action;
      * a rule that starts a process but is itself **never invoked** — not a scheduler's
        `actionRuleIdentifier`, not a table/global/start action's rule, not a `flowable:rule` on a
        service task, not referenced from any form. Authoring the starter and forgetting to wire it
        is the same defect one step further in.

    Also WARNs a process.table whose `userStartProcessActions` AND `globalActions` are both empty:
    legal, but then the worklist can only ever offer what the current task exposes.
    """
    workflows = p.rep.get("workflows") or []
    if not workflows:
        return
    rules = p.rep.get("rules") or []
    start_re = re.compile(r"service\.workflow\.start\s*\(")

    # --- who calls start() -------------------------------------------------
    starters = []
    for ru in rules:
        body = ((ru.get("rule") or {}).get("ruleScriptStr")) or ""
        if start_re.search(_strip_groovy_comments(body)):
            starters.append(ru)

    # --- which process tables carry a start button -------------------------
    start_buttons = {}          # workflowIdentifier -> [node name, ...]
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") not in ("process.table.pluin", "process.table.plugin"):
            continue
        raw = ((n.get("properties") or {}).get("model") or {}).get("stringValue")
        if not raw:
            continue
        try:
            m = json.loads(raw)
        except ValueError:
            continue
        wid = m.get("workflowIdentifier")
        starts = ((m.get("userStartProcessActions") or {}).get("actions")) or []
        globals_ = ((m.get("globalActions") or {}).get("actions")) or []
        if starts and wid:
            start_buttons.setdefault(wid, []).append(n.get("name") or n.get("identifier"))
        if not starts and not globals_:
            r.warn("process.table %r has NO userStartProcessActions and NO globalActions — the only "
                   "buttons its rows can ever show are the per-task ones from the BPMN's "
                   "flowable:userActions, and nothing can be started from this page. That is legal "
                   "(a case opened by a rule elsewhere still lands here), but say so deliberately. "
                   "(05 §The THREE action origins)" % (n.get("name") or n.get("identifier")))

    # A rule that names a workflow literally is attributed to it; one that holds the id in a
    # variable (doc 27's own example does) cannot be attributed, so it counts for every workflow —
    # better a missed ERROR than a false one.
    lit = re.compile(r"service\.workflow\.start\s*\(\s*[\"']([0-9a-fA-F-]{36})[\"']")
    # A sub-process is started by its PARENT, not by a rule or a button:
    # `<callActivity calledElement="<process key>">`. Collect every key any workflow calls and
    # treat a workflow whose own `<process id>` is among them as started. Deliberately generous —
    # several exports give every workflow the same `Process_1` key, so this can over-match, and
    # over-matching only SUPPRESSES an error, which is the safe direction for a gate.
    called = set()
    for _wf in workflows:
        for _k in re.findall(r'<callActivity[^>]*calledElement="([^"]*)"', _wf.get("bpmnContent") or ""):
            called.add(_k)
    for wf in workflows:
        wid = wf.get("identifier")
        named = set()
        for ru in starters:
            body = _strip_groovy_comments(((ru.get("rule") or {}).get("ruleScriptStr")) or "")
            found = set(lit.findall(body))
            if not found or wid in found:
                named.add(ru.get("name") or ru.get("identifier"))
        _own = re.search(r'<process[^>]*id="([^"]*)"', wf.get("bpmnContent") or "")
        if named or wid in start_buttons or (_own and _own.group(1) in called):
            continue
        r.err("workflow %r has NOTHING that starts it: no rule calls service.workflow.start and no "
              "process.table bound to it carries a userStartProcessActions button. The BPMN will "
              "deploy, the worklist will render, and the case list will stay empty forever. Decide "
              "WHO opens a case and WHEN — a user pressing a start action, a lifecycle rule on the "
              "document that begins the process, a scheduler sweep, or a service task in another "
              "process — and wire exactly one of them. (An admin can still start a case by hand "
              "from the console's Processes page; that is a diagnostic, not a design.) "
              "(27 §2 / 05 §The THREE action origins)"
              % (wf.get("name") or wid))

    # --- and what invokes the starter rule itself --------------------------
    if not starters:
        return
    hay = json.dumps(p.branches, ensure_ascii=False)
    hay += json.dumps({k: v for k, v in p.rep.items() if k != "rules"}, ensure_ascii=False)
    for ru in starters:
        rid = ru.get("identifier")
        if not rid:
            continue
        if hay.count(rid):
            continue
        # not referenced by a scheduler, an action, a BPMN service task, a form — anywhere
        r.err("rule %r calls service.workflow.start but NOTHING invokes it — it is not a "
              "scheduler's actionRuleIdentifier, not a table / global / start action's rule, not a "
              "flowable:rule on a service task, and not referenced by any form. A starter that is "
              "never run is the same as no starter. Decide what makes it fire. (27 §2.4)"
              % (ru.get("name") or rid))



_GLOBAL_PROCESS_FIELDS = ("businessKey", "workflowName", "status", "identifier", "id")


def _check_crud_action_form_values(p, root, r):
    """**Does the action's rule read the submitted values from where its own entry point put them?**

    Where a submitted form field lands depends on HOW the form was opened, and the two entry points
    disagree:

    | the form was opened from | the control binds to | the rule reads |
    |---|---|---|
    | a CRUD-table / CRUD-tree ACTION | the action's CRUD — the platform puts every control on that form in CRUD scope over the table's `crudAlias` + `contextIdentifier`, whatever the persisted `scope` says | `context.<ctx>.<alias>.data.get()` |
    | a workflow user task, a ProcessTable start/global action | the process document | `context.data.getAttr("<field>")` |

    A rule reachable from a CRUD-table action that reads its own form's field with `getAttr` therefore
    gets **null on every submit**. Nothing throws: the CRUD method is handed `''`, its
    `COALESCE(NULLIF(:x,''), x)` keeps the old value, the form redirects and the toast says the action
    succeeded — while the record did not change. That is why this must be caught offline; live it reads
    as "submit does nothing", which is indistinguishable from a permission or a status-guard problem.

    ERROR on every literal `getAttr("<field>")` of a field that belongs to the action's own form. The
    helper below reads the attrs through a VARIABLE, so a rule already written for both paths does not
    trip this.

    A form group wired to BOTH kinds of entry point — the same form as a task action AND as a row action,
    which is the normal way to offer "decide it from the worklist or straight from the table" — needs BOTH
    reads, attrs first: on the task path the attrs hold what the user just typed while the row still holds
    the stale database values; on the table path the attrs are empty and the row IS the typed value.

        def FORM = { alias, field ->
            def v = context.data.getAttr(field)
            if (v != null) { return v }
            def row = null
            try { row = context.<ctx>."${alias}".data.get() } catch (Throwable ignored) { }
            return (row instanceof Map) ? row[field] : null
        }

    LIMIT: this covers ONLY the rule an action names in `onBeforeCompleteRuleIdentifier` — the sole rule that
    runs after the submit. An `onBeforeStartRuleIdentifier` rule is never inspected (it fires at form DISPLAY,
    before anything is typed, so the attrs-vs-row question does not arise there). A rule wired to a CONTROL
    (a conditional validation, a mandatory/prohibited predicate, a rule-driven default) receives the control's
    own value as `v`, so it does not depend on the scope — but if such a rule reaches for ANOTHER field of the
    same form with `getAttr`, it hits the same null. Nothing checks that yet; read cross-field values off the
    row there too.

    Also WARNs on a control that is not CRUD-scoped on a form ONLY reachable from a CRUD-table action:
    the runtime binds it to the action's CRUD regardless, so the persisted GLOBAL/CONTEXT makes the export
    disagree with what the form actually does. (02 §Where the value lands, 04, 08)
    """
    settings = [s for s in (p.rep.get("settings") or [])
                if s.get("type") in ("CrudTable", "CrudTree") and isinstance(s.get("content"), dict)]
    if not settings:
        return

    forms_by_group = {}
    for form in (p.rep.get("forms") or []):
        gid = ((form.get("formGroup") or {}).get("identifier")
               if isinstance(form.get("formGroup"), dict) else form.get("formGroupIdentifier"))
        if gid:
            forms_by_group.setdefault(gid, []).append(form)

    pages = {}
    for node, _pp, _pt in core.iter_nodes(root):
        if node.get("pluginName") == "siteMapPage":
            pages[node.get("identifier")] = node

    def controls_of(page):
        """Every form control the page OWNS. A nested list-item form keeps its own binding (it targets
        the list's temp CRUD), so its subtree is not part of the action's form."""
        out = []

        def walk(n):
            for c in (n.get("children") or []):
                if (c.get("pluginName") or "") == "dynaform.list.item.plugin":
                    continue
                pn = c.get("pluginName") or ""
                if "dynaform.form." in pn and "field" in pn:
                    raw = ((c.get("properties") or {}).get("settings") or {}).get("stringValue")
                    if raw:
                        try:
                            out.append(json.loads(raw))
                        except ValueError:
                            pass
                walk(c)

        walk(page)
        return out

    rules_by_id = {ru.get("identifier"): ru for ru in (p.rep.get("rules") or []) if ru.get("identifier")}

    # Which groups are ALSO reachable without a CRUD row: a ProcessTable action or a workflow task.
    process_blob = json.dumps([s.get("content") for s in (p.rep.get("settings") or [])
                               if s.get("type") == "ProcessTable"], ensure_ascii=False)
    process_blob += json.dumps([w.get("bpmnContent") or "" for w in (p.rep.get("workflows") or [])],
                               ensure_ascii=False)

    seen = set()
    seen_groups = set()
    for s in settings:
        model = s.get("content") or {}
        alias = model.get("crudAlias")
        if not alias:
            continue
        label = model.get("name") or s.get("name") or alias
        actions = []
        for key in ("editActions", "createActions"):
            actions += ((model.get(key) or {}).get("actions") or [])
        for act in actions:
            if not isinstance(act, dict):
                continue
            gid = act.get("formGroupIdentifier")
            rid = act.get("onBeforeCompleteRuleIdentifier")
            if not gid or not rid:
                continue
            rule = rules_by_id.get(rid)
            if rule is None:
                continue                       # dangling rule id is reported by the linkage check
            body = _strip_groovy_comments(((rule.get("rule") or {}).get("ruleScriptStr")) or "")
            fields = {}
            for form in forms_by_group.get(gid, []):
                page = pages.get(form.get("contentIdentifier"))
                if page is None:
                    continue
                for st in controls_of(page):
                    expr = (st.get("fieldExpression") or "").strip()
                    if expr:
                        fields.setdefault(expr, st.get("scope"))
            if not fields:
                continue
            act_name = ((act.get("localizedNames") or {}).get("en_US")
                        or act.get("name") or act.get("id") or "?")
            dual = gid in process_blob
            for expr, scope in sorted(fields.items()):
                if not re.search(r'getAttr\s*\(\s*["\']%s["\']\s*\)' % re.escape(expr), body):
                    continue
                key = (rid, expr)
                if key in seen:
                    continue
                seen.add(key)
                both = (" This form is ALSO opened without a CRUD row (a task/process action), so read BOTH,"
                        " attrs first, then the row." if dual else "")
                msg = ("%s action %r opens form group %s, whose rule %r reads the form field %r with "
                       "context.data.getAttr(...). Opened from this action the platform binds every control "
                       "on that form to %r, so the attr is null on every submit: the CRUD method gets '', "
                       "COALESCE keeps the old value, and the action reports success while the record does "
                       "not change. Read it from the row: context.<ctx>.%s.data.get().%s"
                       % (label, act_name, gid, rule.get("name"), expr, alias, alias, both))
                r.err(msg)
            if not dual and gid not in seen_groups:
                seen_groups.add(gid)
                off = sorted(e for e, sc in fields.items() if sc and sc != "CRUD")
                if off:
                    r.warn("%s action %r opens form group %s, where %d control(s) are not CRUD-scoped (%s). "
                           "The form is reachable ONLY from CRUD-table actions, where the runtime binds every "
                           "control to %r anyway — the persisted scope makes the export disagree with what the "
                           "form does, and it is what makes a rule reach for the attrs instead of the row. "
                           "Write scope:'CRUD' with the table's contextIdentifier + crudAlias. "
                           "(02 §Where the value LANDS)"
                           % (label, act_name, gid, len(off), ", ".join(off[:6]), alias))


def _check_process_column_sources(p, r):
    """**Does anything ever put a value where this column reads from?**

    The process table switches on the column's `scope`, and each branch reads a
    DIFFERENT part of the process's stored context-data document:

    | scope | reads |
    |---|---|
    | `GLOBAL` | `contextData.attrs[fieldExpression]` — after intercepting five process-row names (`businessKey`, `workflowName`, `status`, `identifier`, `id`) |
    | `CONTEXT` | `contextDataMap[ctx].attrs[fieldExpression]` |
    | `CRUD` | `contextDataMap[ctx].crudDataMap[alias].value` → `getField(fieldExpression)` |

    Nothing reconciles the three. A column pointed at a slot nobody fills renders empty on every row
    forever, and an empty worklist column reads as missing data rather than as a wiring mistake — so
    it survives review. Three findings:

    * a `GLOBAL` column whose attr **no rule ever writes** — not in a `service.workflow.start`
      `attrs:` literal, not via `context.data.setAttr` → **ERROR**, blank forever;
    * a `GLOBAL` column whose attr is written **only inside a start call's `attrs:`** and never
      re-published by a service task → WARN: the cell is a copy of the record frozen at case start.
      Either add the bind rule that re-publishes it on each step, or read the field where it already
      lives with a `CRUD`-scoped column (the only branch that localizes and projects enums);
    * a `CRUD` column whose `fieldExpression` root is in **no** `crudDataMap` literal for that alias →
      WARN naming the key, because a `crudDataMap` seeded by hand tends to carry the fields somebody
      thought of rather than the fields the columns ask for.
    """
    tables = []
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") not in ("process.table.pluin", "process.table.plugin"):
            continue
        raw = ((n.get("properties") or {}).get("model") or {}).get("stringValue")
        if not raw:
            continue
        try:
            tables.append((n.get("name") or n.get("identifier"), json.loads(raw)))
        except ValueError:
            pass
    if not tables:
        return

    bodies = [_strip_groovy_comments(((ru.get("rule") or {}).get("ruleScriptStr")) or "")
              for ru in (p.rep.get("rules") or [])]
    blob = "\n".join(bodies)

    # WHERE an attr is published matters as much as whether. A bind rule wired to ONE service task
    # writes the value once and never again — which is a snapshot with extra steps, and the exact
    # shape that reads as "we followed the GLOBAL advice" while behaving like the CRUD snapshot that
    # advice exists to avoid. So count the distinct BPMN tasks whose rules write each name.
    rule_by_id = {ru.get("identifier"): ru for ru in (p.rep.get("rules") or []) if ru.get("identifier")}
    tasks_by_attr = {}
    for wf in (p.rep.get("workflows") or []):
        xml = wf.get("bpmnContent") or ""
        for tm in re.finditer(r"<(?:serviceTask|userTask)\b[^>]*>", xml):
            tag = tm.group(0)
            tid = re.search(r'\sid="([^"]*)"', tag)
            rules_attr = re.search(r'flowable:rule="([^"]*)"', tag)
            if not (tid and rules_attr):
                continue
            for rid in rules_attr.group(1).split(","):
                ru = rule_by_id.get(rid.strip())
                if not ru:
                    continue
                body = _strip_groovy_comments(((ru.get("rule") or {}).get("ruleScriptStr")) or "")
                for nm in re.findall(r"setAttr\s*\(\s*['\"]([A-Za-z0-9_]+)['\"]", body):
                    tasks_by_attr.setdefault(nm, set()).add(tid.group(1))
    setattr_names = set(re.findall(r"setAttr\s*\(\s*['\"]([A-Za-z0-9_]+)['\"]", blob))
    # keys of every `attrs: [ ... ]` literal — the start document's own attribute block
    start_attr_names = set()
    for m in re.finditer(r"attrs\s*:\s*\[", blob):
        chunk = blob[m.end():m.end() + 4000]
        depth = 1
        for i, ch in enumerate(chunk):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    chunk = chunk[:i]
                    break
        start_attr_names |= set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", chunk))
    # keys of every `<alias>: [ value: [ ... ] ]` block inside a crudDataMap literal
    crud_seeds = {}
    for m in re.finditer(r"crudDataMap\s*:\s*\[", blob):
        chunk = blob[m.end():m.end() + 6000]
        for am in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\[\s*value\s*:\s*\[", chunk):
            inner = chunk[am.end():am.end() + 3000]
            depth = 1
            for i, ch in enumerate(inner):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        inner = inner[:i]
                        break
            crud_seeds.setdefault(am.group(1), set()).update(
                re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", inner))

    for tname, model in tables:
        for c in (model.get("columnSettings") or []):
            if not isinstance(c, dict):
                continue
            scope = c.get("scope")
            expr = (c.get("fieldExpression") or "").strip()
            label = ((c.get("localizedNames") or {}).get("en_US")
                     or c.get("name") or expr or "?")
            if not expr:
                continue
            if scope == "GLOBAL":
                if expr in _GLOBAL_PROCESS_FIELDS:
                    continue
                if expr not in setattr_names and expr not in start_attr_names:
                    r.err("process.table %r column %r is GLOBAL over attr %r, and NO rule ever writes "
                          "that attr — not in a service.workflow.start `attrs:` literal and not via "
                          "context.data.setAttr. GLOBAL reads contextData.attrs[%r], so this column is "
                          "blank on every row, forever. (05 §How scope determines the value source)"
                          % (tname, label, expr, expr))
                elif len(tasks_by_attr.get(expr) or ()) <= 1:
                    where = ("written ONLY in the start call's `attrs:`"
                             if expr not in setattr_names else
                             "published at exactly ONE point in the process (%s)"
                             % ", ".join(sorted(tasks_by_attr.get(expr) or ())))
                    r.warn("process.table %r column %r is GLOBAL over attr %r, which is %s — nothing "
                           "re-publishes it, so the cell shows a copy of the record frozen at that "
                           "moment and drifts from what every other screen shows. Either re-publish it "
                           "on each step (the bind rule wired to more than one task), or make the column "
                           "CRUD-scoped over the field where the value actually lives — the CRUD branch "
                           "is also the only one that localizes and projects enums. "
                           "(05 §How scope determines the value source)"
                           % (tname, label, expr, where))
            elif scope == "CRUD":
                alias = c.get("crudAlias")
                if not alias or alias not in crud_seeds:
                    continue          # the alias-level case is reported by the CRUD-seeding check
                root = expr.split(".")[0]
                if root not in crud_seeds[alias]:
                    r.warn("process.table %r column %r is CRUD-scoped over %s.%s, but no crudDataMap "
                           "literal in any rule puts %r into that alias (it seeds %s). Unless a start "
                           "FORM control fills it, the column is blank on every row. (05)"
                           % (tname, label, alias, expr, root,
                              ", ".join(sorted(crud_seeds[alias])[:8]) or "nothing"))


def _check_process_table_workflow_exists(p, r):
    """A process.table (or its settings mirror) that binds a `workflowIdentifier` NOT present in rep.workflows[]
    renders an EMPTY worklist — the workflow was never imported/created (usually a stale template leftover). Also
    flags orphan ProcessTable settings pointing at a non-existent workflow. (05/07/12)"""
    valid = {w.get("identifier") for w in p.rep.get("workflows", []) or []}
    if not valid:
        return
    for n, pn, md in _iter_table_models(p):
        if pn not in ("process.table.pluin", "process.table.plugin"):
            continue
        wf = md.get("workflowIdentifier")
        if wf and wf not in valid:
            r.warn("process.table %r binds workflowIdentifier %r not in rep.workflows[] — the worklist renders EMPTY "
                   "(stale template leftover; that workflow was never imported). Point it at an existing workflow or "
                   "remove the page. (05-crud-tree-and-process-table.md)" % (n.get("name"), wf))
    for s in p.rep.get("settings", []) or []:
        c = s.get("content")
        if not isinstance(c, dict):
            continue
        wf = c.get("workflowIdentifier")
        if wf and wf not in valid:
            r.warn("ProcessTable settings %r binds workflowIdentifier %r not in rep.workflows[] — an orphan "
                   "process-table config (stale template leftover). Remove it from rep.settings[]. (12-queries-sources-schedulers-and-rest.md)"
                   % (s.get("name"), wf))


_SQL_QPARAM_RE = re.compile(r"\{\s*name\s*:\s*'([^']*)'\s*(?:,\s*type\s*:\s*'[^']*'\s*)?\}")
_SQL_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _sql_shape(sql, query_form):
    """Normalise one of the two stored forms of a statement so that the pair compares equal exactly when it
    is the same statement.

    Both placeholder syntaxes collapse to `?<name>?` — keeping the NAME, so a renamed parameter is still a
    difference, while the `type` tag (which the two forms do not always agree on, and which the platform
    treats as optional) is dropped. String literals, dollar-quoted bodies and comments are copied through
    untouched: `to_char(now(), 'HH24:MI')` must not have its `:MI` read as a parameter, or two byte-identical
    statements would compare unequal — a check that fires on identical text is worse than no check at all."""
    src = sql or ""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == "'":                                   # string literal, '' escapes a quote
            j = i + 1
            while j < n:
                if src[j] == "'":
                    if j + 1 < n and src[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(src[i:j])
            i = j
            continue
        if c == "$":                                   # dollar-quoted body: $tag$ … $tag$
            m = re.match(r"\$[A-Za-z_0-9]*\$", src[i:])
            if m:
                tag = m.group(0)
                end = src.find(tag, i + len(tag))
                end = n if end < 0 else end + len(tag)
                out.append(src[i:end])
                i = end
                continue
        if src.startswith("--", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" ")
            i = j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(" ")
            i = j
            continue
        if query_form and c == "{":
            m = _SQL_QPARAM_RE.match(src, i)
            if m:
                out.append("?%s?" % m.group(1))
                i = m.end()
                continue
        if not query_form and c == ":" and not src.startswith("::", i) and not (i and src[i - 1] == ":"):
            m = _SQL_IDENT_RE.match(src, i + 1)
            if m:
                out.append("?%s?" % m.group(0))
                i = m.end()
                continue
        out.append(c)
        i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _check_sql_mirror(alias, method, query, r):
    """A dynamic CRUD stores each SQL method TWICE: `methods[].script` in `:name` form — the version the
    executor actually runs — and a saved query in `rep-objects.json.queries[]` in `{name:'x',type:'y'}` form.
    Only the script is executed, so a hand-edit to the script alone LOOKS like it worked... until somebody
    opens that method in the CRUD editor, which reloads the script FROM the query and saves it back. The old
    statement is then reinstalled, silently, by a screen the author only opened to look at. Nothing else in
    the toolchain compares the pair. -> WARN (07 / 11-business-logic-dynamic-crud.md)."""
    if query is None:
        return
    a = _sql_shape(method.get("script"), False)
    b = _sql_shape(query.get("query"), True)
    if a == b or (not a and not b):
        return
    r.warn("crud %r method %r: `script` and its saved query %r are DIFFERENT statements — only the script "
           "runs, but opening the method in the CRUD editor reloads the script from the query and saves it "
           "back, which reinstalls the query's version. Keep the pair in sync.\n      script: %s\n      "
           "query : %s (11-business-logic-dynamic-crud.md)"
           % (alias, method.get("methodName"), query.get("name"), a[:180], b[:180]))


def _check_callactivity_resolves(p, r):
    """A bpmn:CallActivity's `calledElement` must equal the process KEY (`<process id="...">`) of an existing
    workflow, else the sub-process cannot start at runtime (Flowable: no process definition for that key). (07)"""
    proc_keys = set()
    key_re = re.compile(r'<(?:\w+:)?process\s+[^>]*\bid="([^"]+)"')
    call_re = re.compile(r'<(?:\w+:)?callActivity\b[^>]*\bcalledElement="([^"]+)"')
    for w in p.rep.get("workflows", []) or []:
        for m in key_re.finditer(w.get("bpmnContent") or ""):
            proc_keys.add(m.group(1))
    for w in p.rep.get("workflows", []) or []:
        for m in call_re.finditer(w.get("bpmnContent") or ""):
            called = m.group(1)
            if called not in proc_keys:
                r.warn("workflow %r callActivity calledElement=%r matches no workflow process key (`<process id=...>`) "
                       "in this project — the SAR/sub-process won't start at runtime. Add the called workflow or fix "
                       "the calledElement. (07-workflows-and-tasks.md)" % (w.get("name"), called))


# Every BPMN element that can carry outgoing sequence flows. Used to walk a workflow as a GRAPH instead of
# scraping the XML with attribute-order-sensitive regexes: `bpmnContent` is authored by the builder on one
# line, re-serialized MULTI-LINE by the platform's modeler on every save, and may carry `name=` before
# `sourceRef=` — a regex tuned to one of those shapes silently matches NOTHING on the others, which turns a
# check into a no-op that still reports "clean".
_BPMN_NODE_TAGS = {
    "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent",
    "task", "userTask", "serviceTask", "scriptTask", "sendTask", "receiveTask", "manualTask",
    "businessRuleTask", "callActivity", "subProcess", "transaction",
    "exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway", "complexGateway",
}


def _bpmn_parse(xml_str):
    """`bpmnContent` -> (nodes, flows, shapes, edges), independent of formatting and attribute order.

    nodes/flows map id -> Element; shapes maps a node id -> (x, y, w, h); edges maps a flow id ->
    [(x, y), ...] waypoints. Returns None when the XML does not parse — `_check_workflow_xml` is the
    check that reports that, as an ERROR, and it should not be reported twice."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return None
    nodes, flows, shapes, edges = {}, {}, {}, {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        eid = el.get("id")
        if tag == "sequenceFlow" and eid:
            flows[eid] = el
        elif tag in _BPMN_NODE_TAGS and eid:
            nodes[eid] = el
        elif tag == "BPMNShape":
            b = next((c for c in el if c.tag.split("}")[-1] == "Bounds"), None)
            if b is not None and el.get("bpmnElement"):
                try:
                    shapes[el.get("bpmnElement")] = tuple(
                        float(b.get(k) or 0) for k in ("x", "y", "width", "height"))
                except (TypeError, ValueError):
                    pass
        elif tag == "BPMNEdge":
            pts = []
            for w in el:
                if w.tag.split("}")[-1] == "waypoint":
                    try:
                        pts.append((float(w.get("x")), float(w.get("y"))))
                    except (TypeError, ValueError):
                        pts = []
                        break
            if pts and el.get("bpmnElement"):
                edges[el.get("bpmnElement")] = pts
    return nodes, flows, shapes, edges


def _bpmn_edge_label(el):
    """The `<bpmndi:BPMNLabel><dc:Bounds>` of a BPMNShape/BPMNEdge, or None."""
    lab = next((c for c in el if c.tag.split("}")[-1] == "BPMNLabel"), None)
    if lab is None:
        return None
    b = next((c for c in lab if c.tag.split("}")[-1] == "Bounds"), None)
    if b is None:
        return None
    try:
        return tuple(float(b.get(k) or 0) for k in ("x", "y", "width", "height"))
    except (TypeError, ValueError):
        return None


def _has_condition(flow_el):
    return flow_el is not None and any(c.tag.split("}")[-1] == "conditionExpression" for c in flow_el)


def _check_gateway_predicate_reads_record(p, r):
    """⛔ The subtlest way a gateway can look like a decision and never make one.

    A predicate on a gateway runs INSIDE a case, and the `context.<ctx>.<alias>.data` it can read there is not
    the record: it is `contextDataMap`, a copy kept in a process variable. Nothing refreshes it when a rule or
    a form writes the row — the engine hands the predicate whatever was last written into that variable. So
    the CRUD-table idiom

        try { row = context.<ctx>.<alias>.data.get() } catch (Throwable ignored) { }
        if (!(row instanceof Map) || row.id == null || row.<field> == null) { …read the record… }
        return (row.<field> == '<STATE>')

    — read the filed row, fall back to a real read only when nothing useful is filed — behaves in two
    completely different ways on a gateway, and WHICH one you get is decided somewhere else entirely:

      * nothing seeded that alias → the map is absent, the fallback runs, the predicate is correct;
      * something seeded it → and a case with no start form MUST seed it, because the starting document is
        the only channel it has to publish its subject — the fast path answers from the copy taken when the
        case opened. The field is frozen at its opening value, the predicate returns the same answer for the
        life of the case, ONE branch is taken for ever and the other is unreachable code that still reads as
        a decision on the diagram.

    Nothing in the BPMN shows it. The branch, its predicate, its label and the gateway's `default` are all
    exactly right; only what the predicate is allowed to believe is wrong. On a CRUD table the same idiom is
    correct and cheap — the filed row IS the row on screen — which is why this is flagged only for predicates
    a WORKFLOW GATEWAY decides on.

    ✅ On a gateway: resolve the id from the snapshot (ids do not go stale), then read the record
    unconditionally — `def row = service.crud.<alias>.get(id)`. -> WARN (07-workflows-and-tasks.md §4,
    08-groovy-rules-and-context.md).

    Flagged when the snapshot variable reaches a `return` and the re-read into it is missing or conditional;
    silent when the snapshot is used only to resolve an id, and when the re-read is unconditional (directly
    or through a local that was itself read from the crud)."""
    rules_by_id = {rr.get("identifier"): rr for rr in p.rep.get("rules", []) or []}
    # `row` (or any name) assigned from a context snapshot, then a re-read that sits behind a condition.
    snap_re = re.compile(r"(\w+)\s*=\s*context\.\w+\.(\w+)\.data\.get\(\)")
    for wf in p.rep.get("workflows", []) or []:
        xml = wf.get("bpmnContent") or ""
        if not xml:
            continue
        for pid in sorted(set(re.findall(r"predicateSequence\.execute\(execution,\s*'([0-9a-fA-F-]+)'\)", xml))):
            rr = rules_by_id.get(pid)
            if rr is None:
                continue                      # dangling — _check_workflow_refs reports that
            body = (rr.get("rule") or {}).get("ruleScriptStr") or ""
            src = _strip_groovy_comments(body)
            for m in snap_re.finditer(src):
                var, alias = m.group(1), m.group(2)
                after = src[m.end():]
                # Does the snapshot reach the ANSWER? If the body only takes an id off it and returns a
                # value read from somewhere else, there is nothing to flag — that is the correct shape.
                if not re.search(r"return\b[^\n]*\b%s\s*[.?\[]" % re.escape(var), after):
                    continue
                # It does. Then the only thing that makes it safe is an UNCONDITIONAL re-read into the same
                # variable before that return — either straight from the crud, or through a local that was
                # itself read from the crud. Anything else (a re-read behind an `if`/ternary, or no re-read
                # at all) means the answer can come from the copy.
                fresh_locals = set(re.findall(r"(?:def\s+)?(\w+)\s*=\s*[^\n]*service\.crud\.%s\.\w+\("
                                              % re.escape(alias), after))
                pat = [r"%s\s*=\s*[^\n]*service\.crud\.%s\.\w+\(" % (re.escape(var), re.escape(alias))]
                for loc in sorted(fresh_locals):
                    if loc != var:
                        pat.append(r"%s\s*=\s*%s\b" % (re.escape(var), re.escape(loc)))
                reread = None
                for p in pat:
                    mm = re.search(p, after)
                    if mm is not None and (reread is None or mm.start() < reread.start()):
                        reread = mm
                if reread is not None:
                    between = after[:reread.start()]
                    eol = after.find("\n", reread.start())
                    rhs = after[reread.start():eol if eol >= 0 else len(after)]
                    # `?` marks a ternary or an elvis (`snapshot ?: read()`, "use the copy if it is there") —
                    # both make the re-read conditional. `?.` is safe navigation and means nothing here.
                    conditional = "if" in between or re.search(r"\?(?!\.)", between + rhs)
                    if not conditional:
                        continue              # unconditional re-read: correct
                how = ("with the real read behind a condition" if reread is not None
                       else "with no read of the record at all")
                r.warn("workflow %r gateway predicate %r answers from the case's context SNAPSHOT when one "
                       "is present (`%s = context.….%s.data.get()`, %s). "
                       "Inside a case that snapshot is a copy taken when the case opened and nothing "
                       "refreshes it — if the starting document seeded `%s` (a case with no start form has "
                       "to), the predicate returns the SAME answer for the life of the case, so one branch "
                       "is taken for ever and the other is unreachable while still reading as a decision. "
                       "Resolve the id from the snapshot, then read the record UNCONDITIONALLY "
                       "(`service.crud.%s.get(id)`). (07-workflows-and-tasks.md §4)"
                       % (wf.get("name"), rr.get("name"), var, alias, how, alias, alias))
                break


def _check_gateway_branching(p, r):
    """Everything that decides WHICH way a token leaves a node — and every way that decision can be silently
    wrong. All WARN (none of it blocks the import; all of it changes what the process does at runtime).

    How Flowable 7 picks the outgoing flow (`ExclusiveGatewayActivityBehavior` for XOR, the shared
    `TakeOutgoingSequenceFlowsOperation` for everything else): it walks the outgoing flows, keeps the ones
    whose condition is true — a flow with NO `<conditionExpression>` counts as true — and always SKIPS the
    flow named in the element's `default` attribute while doing so. Only if that leaves nothing does it fall
    back to the `default`. Nothing left and no default that resolves to one of THIS element's outgoing flows
    → it throws *"No outgoing sequence flow ... could be selected"* and the case is stuck. An exclusive
    gateway then takes the FIRST survivor; every other element takes ALL of them (one token each).

    So the correct XOR is: one conditional branch per outcome, plus ONE unconditional fallback that the
    gateway names in `default="<flowId>"`. The fallback carrying no predicate is not an unfinished branch —
    it IS the `else`, and it is the only shape that cannot get stuck or flip with document order.

    What this flags:
      * `default` naming a flow that is NOT an outgoing flow of that element (typo, or the branch was
        rerouted) — the fallback silently stops existing and the element throws when every condition is
        false;
      * `default` naming a flow that ALSO carries a `<conditionExpression>` — that condition is never
        evaluated (dead logic that reads as live);
      * all branches conditional and no `default` → stuck the moment every predicate returns false;
      * an unconditional fallback that is NOT the `default` → routing depends on document ORDER, so any
        editor re-order changes it;
      * more than one unconditional branch on an exclusive gateway → all but the first are dead;
      * conditions (or a `default`) on a PARALLEL gateway — Flowable takes every branch there WITHOUT
        evaluating conditions, so the predicate is dead code that reads as a decision;
      * two or more unconditional flows out of a plain TASK — that is an implicit parallel FORK (a token per
        branch), not a choice; a choice needs an exclusiveGateway;
      * UNLABELLED branches out of a decision. The engine routes on the condition, a reader routes on the
        `name`: two unlabelled arrows out of a diamond say nothing, and the fallback's settings panel is
        empty BY DESIGN (it has no predicate to show), so without a label there is nothing on screen that
        says which branch is which. (07-workflows-and-tasks.md §4)"""
    for wf in p.rep.get("workflows", []) or []:
        parsed = _bpmn_parse(wf.get("bpmnContent") or "")
        if parsed is None:
            continue
        nodes, flows, _shapes, _edges = parsed
        nm = wf.get("name")
        for nid, el in sorted(nodes.items()):
            kind = el.tag.split("}")[-1]
            outs = [f for fid, f in sorted(flows.items()) if f.get("sourceRef") == nid]
            if len(outs) < 2:
                continue
            out_ids = [f.get("id") for f in outs]
            uncond = [f for f in outs if not _has_condition(f)]
            conds = [f for f in outs if _has_condition(f)]
            dflt = el.get("default")
            where = "%s %s" % (kind, nid)

            if kind == "parallelGateway":
                if conds:
                    r.warn("workflow %r %s: branch(es) %s carry a <conditionExpression>, but a PARALLEL "
                           "gateway takes every outgoing flow WITHOUT evaluating conditions — the predicate "
                           "is dead code that reads as a decision. Use an exclusiveGateway to choose, or drop "
                           "the condition. (07-workflows-and-tasks.md §4)"
                           % (nm, where, [f.get("id") for f in conds]))
                if dflt:
                    r.warn("workflow %r %s: a PARALLEL gateway has no fallback semantics, so default=%r is "
                           "never used — it reads as an if/else that does not exist. (07-workflows-and-tasks.md §4)"
                           % (nm, where, dflt))
                continue
            if kind in ("eventBasedGateway", "complexGateway"):
                continue

            # -- the fallback contract (exclusive/inclusive gateways and any node with conditional exits) --
            decides = kind in ("exclusiveGateway", "inclusiveGateway") or bool(conds)
            if dflt and dflt not in out_ids:
                r.warn("workflow %r %s: default=%r is NOT one of its outgoing flows (%s) — Flowable cannot "
                       "fall back to it, so the moment every condition is false the process THROWS 'No "
                       "outgoing sequence flow ... could be selected' and the case is stuck. Point `default` "
                       "at the unconditional branch. (07-workflows-and-tasks.md §4)" % (nm, where, dflt, out_ids))
            elif dflt and _has_condition(flows.get(dflt)):
                r.warn("workflow %r %s: default=%r ALSO carries a <conditionExpression> — the fallback is "
                       "skipped while conditions are evaluated, so that predicate NEVER runs. Make the "
                       "default branch unconditional (that is what makes it the `else`). "
                       "(07-workflows-and-tasks.md §4)" % (nm, where, dflt))
            if not dflt and decides:
                if not uncond:
                    r.warn("workflow %r %s has %d outgoing flows, ALL conditional, and NO `default` — the "
                           "moment every condition is false Flowable throws 'No outgoing sequence flow ... "
                           "could be selected' and the case is STUCK. Give it one unconditional fallback and "
                           "name it in default=\"<flowId>\". (07-workflows-and-tasks.md §4)"
                           % (nm, where, len(outs)))
                else:
                    r.warn("workflow %r %s has an unconditional fallback (%s) that is NOT the `default` — an "
                           "unconditional flow counts as true, so routing depends on document ORDER and any "
                           "editor re-order silently changes it. Set default=%r on the element. "
                           "(07-workflows-and-tasks.md §4)"
                           % (nm, where, uncond[0].get("id"), uncond[0].get("id")))
            if kind == "exclusiveGateway" and len(uncond) > 1:
                r.warn("workflow %r %s has %d unconditional outgoing flows (%s) — an exclusive gateway takes "
                       "the FIRST true one, so all but one are dead. Keep exactly one fallback. "
                       "(07-workflows-and-tasks.md §4)"
                       % (nm, where, len(uncond), [f.get("id") for f in uncond]))
            if kind not in ("exclusiveGateway", "inclusiveGateway") and len(uncond) > 1:
                r.warn("workflow %r %s has %d unconditional outgoing flows — every element that is not an "
                       "exclusive gateway takes ALL of them, so this is an implicit parallel FORK (one token "
                       "per branch), not a choice. Route the choice through an exclusiveGateway. "
                       "(07-workflows-and-tasks.md §4)" % (nm, where, len(uncond)))

            # -- the half a human reads --
            if decides:
                unnamed = [f.get("id") for f in outs if not (f.get("name") or "").strip()]
                if unnamed:
                    r.warn("workflow %r %s: branch(es) %s have no `name` — the modeler draws identical "
                           "unlabelled arrows and the fallback's settings panel is empty by design (it has no "
                           "predicate), so nothing on screen says which branch is which. Name every branch "
                           "(`Approved`/`Rejected`, `Yes`/`No`). (07-workflows-and-tasks.md §4)"
                           % (nm, where, unnamed))


def _strip_groovy_comments(src):
    """Blank out `//` and `/* */` comments, keeping every other character in place.

    Positions are preserved (comment characters become spaces) so a caller can still report offsets, and string
    literals are walked rather than skipped so a `//` inside a URL or a `/*` inside a message is left alone.
    Commented-out code must not be validated: an author who parks a call behind `//` while debugging has not
    written a broken project, and a checker that says otherwise teaches them to distrust it."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"":
            # Triple-quoted blocks first: they may legitimately contain a lone quote.
            triple = src[i:i + 3]
            if triple in ("'''", '"""'):
                end = src.find(triple, i + 3)
                end = n if end < 0 else end + 3
                out.append(src[i:end])
                i = end
                continue
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c or src[j] == "\n":
                    j += 1
                    break
                j += 1
            out.append(src[i:j])
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _rule_script(rule):
    """The Groovy body of a rep-objects rule, or "" — never an exception.

    `rules[].rule` is an OBJECT in a healthy export, but a broken one can carry a JSON string there, and that is
    exactly the shape `validate` exists to report: a checker that dies on it reports nothing at all, including
    the type error itself."""
    rr = rule.get("rule") if isinstance(rule, dict) else None
    script = rr.get("ruleScriptStr") if isinstance(rr, dict) else None
    return script if isinstance(script, str) else ""


def _check_rule_workflow_start_targets(p, r):
    """`service.workflow.start("<workflowIdentifier>", ...)` addresses a workflow by identifier, so a typo or a
    workflow that never made it into the export is a runtime 404 nothing else catches — the call compiles, the
    editor's autocomplete is not consulted at build time, and the rule only fails when it actually runs.
    Also warns when the target exists but is `deployed:false`, which throws `workflow_is_not_deployed`.
    (16-groovy-service-api.md)"""
    # Both sources, because a CRUD GROOVY method is a first-class caller of start() and its body lives in
    # dynamic-cruds.json - the hidden rule it delegates to is absent from rep-objects.rules[] in a hand-built archive
    # (a platform export carries it, with the same body).
    bodies = [(where, body, rule_type) for where, body, rule_type, _access, _is_method in _groovy_bodies(p)]
    if not bodies:
        return
    rep = p.rep
    workflows = rep.get("workflows", []) or []
    # Latest-wins: an export can carry several versions of one workflow, and the deployed flag that matters is
    # whichever version the engine would resolve.
    deployed_by_id = {}
    for wf in workflows:
        wid = wf.get("identifier")
        if not wid:
            continue
        deployed_by_id[wid] = bool(wf.get("deployed")) or deployed_by_id.get(wid, False)
    # Either quote style: Groovy accepts both, and an author copying from a hint will not always keep ours.
    # Triple-quoted literals are not matched and are therefore unchecked - a deliberate gap, since nothing
    # generates them and the alternative is a regex that mis-parses the ordinary case.
    call_re = re.compile(r"""service\.workflow\.start\(\s*(['"])([^'"]+)\1""")
    # Any call at all, however its first argument is written. The rule-kind check below must not depend on the
    # identifier being a literal: doc 16's own example holds it in a variable, and a predicate that starts a
    # process is refused at runtime whether or not the target is knowable here.
    any_call_re = re.compile(r"service\.workflow\.start\s*\(")
    for where, body, rule_type in bodies:
        # Comments out first: a parked-out call is not a defect, and flagging one would make `validate`
        # unusable as the reimport gate tools/README.md sells it as.
        body = _strip_groovy_comments(body)
        if not any_call_re.search(body):
            continue
        if rule_type in ("PREDICATE", "VALIDATION_RULE"):
            # Refused at runtime: those are evaluated for their answer, possibly repeatedly, so they must not
            # create work. Caught here because the author would otherwise only find out on the first run.
            r.err("%s is a %s and calls service.workflow.start(...) — that is refused at runtime. Start the "
                  "process from an EXECUTION_RULE or a CRUD GROOVY method. (16-groovy-service-api.md)"
                  % (where, rule_type))
            continue
        for _quote, target in call_re.findall(body):
            if "$" in target:
                continue  # a GString computes the identifier at runtime; nothing to check statically
            if target not in deployed_by_id:
                r.err("%s calls service.workflow.start(\"%s\") but no workflow in rep-objects.workflows[] "
                      "has that identifier — the call throws workflow_not_found at runtime. The first argument "
                      "is the workflow IDENTIFIER, not its name. (16-groovy-service-api.md)"
                      % (where, target))
            elif not deployed_by_id[target]:
                r.warn("%s calls service.workflow.start(\"%s\") on a workflow that is not deployed — the "
                       "call throws workflow_is_not_deployed until it is. (16-groovy-service-api.md)"
                       % (where, target))


# What `service.security` really has (doc 16 §2.3). The checks answer about the person running the rule and exist in
# every rule type; `users` and `roleGroups` manage the project's people and exist only in an EXECUTION rule or a CRUD
# GROOVY method (the runtime wires a refusing variant into a predicate and a validation rule).
_SECURITY_CHECK_MEMBERS = ("user", "hasAnyRole", "hasAllRoles", "hasAnyRoleGroup", "hasAllRoleGroups")
_PEOPLE_MEMBERS = {
    "users": ("create", "get", "list", "update", "setEnabled", "delete", "addRoleGroup", "removeRoleGroup", "invite"),
    "roleGroups": ("list", "get", "create", "update", "delete", "members"),
}
# The members that CHANGE something. The others (`get`, `list`, `members`) only read - which still discloses the
# project's people to whoever may run the rule, but is not "managing" them.
_PEOPLE_MUTATING_MEMBERS = {
    "users": ("create", "update", "setEnabled", "delete", "addRoleGroup", "removeRoleGroup", "invite"),
    "roleGroups": ("create", "update", "delete"),
}
_PEOPLE_REF_RE = re.compile(r"\bservice\s*\.\s*security\s*\.\s*(users|roleGroups)\b")
_PEOPLE_MEMBER_RE = re.compile(r"\bservice\s*\.\s*security\s*\.\s*(users|roleGroups)\s*\.\s*([A-Za-z_]\w*)")
_SECURITY_CALL_RE = re.compile(r"\bservice\s*\.\s*security\s*\.\s*([A-Za-z_]\w*)\s*\(")
_PEOPLE_DOC = "(16-groovy-service-api.md §2.3.1)"

_SAFE_NAV_RE = re.compile(r"\?\s*\.")
_QUOTED_PROPERTY_RE = re.compile(r"""\.\s*(['"])(\w+)\1""")
_SUBSCRIPT_PROPERTY_RE = re.compile(r"""\[\s*(['"])(\w+)\1\s*\]""")
_NAMESPACE_GETTER_RE = re.compile(r"\bsecurity\s*\.\s*get(Users|RoleGroups)\s*\(\s*\)")


def _fold_property_chain(code):
    """A `service.<namespace>.<member>` chain however it was spelled: `service?.pubsub?.plant`,
    `service.pubsub."plant"` and `service.pubsub['plant']` all reach the same member at runtime, and a check that
    only knew the plain dotted form would let any of them past. Folded to `service.pubsub.plant`. Analysis only -
    the script is not changed. A subscript that is not a plain word (`['my-broker']`) is left as it is."""
    code = _SAFE_NAV_RE.sub(".", code)
    code = _QUOTED_PROPERTY_RE.sub(r".\2", code)
    return _SUBSCRIPT_PROPERTY_RE.sub(r".\2", code)


def _security_chain(code):
    """The same property chain, however it was spelled: `service?.security?.users`, `service.security."users"`,
    `service.security['users']` and the getter `service.security.getUsers()` all reach the same namespace at
    runtime, and a check that only knew the plain dotted form would let any of them past. Folded to
    `service.security.users`. Analysis only - the script is not changed. A chain broken across a variable
    (`def s = service.security` ... `s.users.create(...)`) is NOT followed; that is the limit of a text check."""
    code = _fold_property_chain(code)
    return _NAMESPACE_GETTER_RE.sub(lambda m: "security." + m.group(1)[0].lower() + m.group(1)[1:], code)


class _Body(tuple):
    """One Groovy body of the export. A plain 5-tuple - (where, body, rule_type, access, is_method), the shape every
    check has always unpacked - that also remembers what OTHER bodies call it by: `rule_name` for a rule
    (`service.rule("<name>")` resolves by NAME) and `method_ref` for a CRUD GROOVY method
    (`service.crud.<alias>.<method>(...)`)."""
    rule_name = None
    method_ref = None


def _groovy_bodies(p):
    """Every Groovy body the export carries, as (where, body, rule_type, access, is_method): the rules in
    `rep-objects.rules[]` and the GROOVY methods of the dynamic CRUDs.

    A CRUD GROOVY method runs as an EXECUTION rule whatever its hidden rule says, and its caller is checked against
    the METHOD's execution access (inherited from the CRUD unless `inheritAccess` is false) - never against the
    hidden rule's. The hidden rule it delegates to is absent from `rules[]` in a hand-built archive; a platform export
    carries it there, with the same body (`validate` ERRORs when the two differ)."""
    from . import execaccess

    bodies = []
    for rule in p.rep.get("rules", []) or []:
        rr = rule.get("rule") if isinstance(rule, dict) else None
        if isinstance(rr, dict) and rr.get("ruleScriptStr"):
            body = _Body(("rule %r" % rule.get("name"), rr["ruleScriptStr"], rule.get("ruleType"),
                          rule.get("access"), False))
            body.rule_name = rule.get("name")
            bodies.append(body)
    _by_alias, cruds = _dynamic_crud_methods(p)
    for crud in cruds:
        for m in crud.get("methods", []) or []:
            if m.get("methodType") == "GROOVY" and m.get("script"):
                access, _source = execaccess.method_effective(crud, m)
                body = _Body(("crud %r method %r" % (crud.get("alias"), m.get("methodName")),
                              m["script"], "EXECUTION_RULE", access, True))
                body.method_ref = (crud.get("alias"), m.get("methodName"))
                bodies.append(body)
    return bodies


# Members every Groovy object has. `service.security.users.with { create(...) }` and `.toString()` are valid Groovy,
# not a member that does not exist - and a closure delegate can do ANYTHING the namespace can.
_OBJECT_MEMBERS = ("with", "tap", "toString", "hashCode", "equals", "getClass", "inspect", "dump", "identity",
                   "getMetaClass", "getProperties", "metaClass", "properties", "class")

# `service.rule("Name")` with a literal name, and `service.crud.<alias>.<method>(`. A name built at run time is not
# followed - nothing static can say which rule it is.
_RULE_CALL_RE = re.compile(r"""\bservice\s*\.\s*rule\s*\(\s*(['"])([^'"\n]+)\1\s*\)""")
_CRUD_CALL_RE = re.compile(r"\bservice\s*\.\s*crud\s*\.\s*([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(")


def _blank_strings(code):
    """The same text with the CONTENT of every string literal replaced by spaces (quotes and newlines stay), except
    the code inside a double-quoted string's `${...}`, which is code and is kept.

    The people checks look for `service.security.users...` as CODE. A help text that mentions it
    (`"to add somebody call service.security.users.create(...)"`) is not a call, and in a predicate it would be an
    ERROR that blocks the import for a sentence. Comments are already gone; this removes the other place the
    name can appear without being used."""
    out = []
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        if c not in "'\"":
            out.append(c)
            i += 1
            continue
        triple = code[i:i + 3]
        quote = triple if triple in ("'''", '"""') else c
        out.append(quote)
        i += len(quote)
        interpolates = c == '"'
        while i < n:
            if code.startswith(quote, i):
                out.append(quote)
                i += len(quote)
                break
            ch = code[i]
            if ch == "\\":
                out.append(" ")
                if i + 1 < n:
                    out.append("\n" if code[i + 1] == "\n" else " ")
                i += 2
                continue
            if ch == "\n" and len(quote) == 1:
                out.append(ch)         # an unterminated one-line string ends at the line
                i += 1
                break
            if interpolates and code.startswith("${", i):
                depth, j = 1, i + 2
                while j < n and depth:
                    depth += {"{": 1, "}": -1}.get(code[j], 0)
                    j += 1
                closed = depth == 0
                out.append("  " + _blank_strings(code[i + 2:j - 1 if closed else j]) + (" " if closed else ""))
                i = j
                continue
            out.append(ch if ch == "\n" else " ")
            i += 1
    return "".join(out)


def _people_code(body):
    """(folded, blanked): the body without comments and with the spellings of the security chain folded
    (`_security_chain`) - and the same with every string literal blanked. Calls to follow are read from the first
    (their argument IS a string); everything about `service.security.users` is read from the second."""
    folded = _security_chain(_strip_groovy_comments(body))
    return folded, _blank_strings(folded)


def _literal_callees(folded, blanked, by_rule, by_method):
    """The bodies one body CALLS by a literal name: `service.rule("Name")` and `service.crud.<alias>.<method>(`.
    `folded` is the body with its strings intact (the rule's name is one), `blanked` the same with the strings
    emptied (so a call mentioned in a help text is not a call)."""
    found = []
    for m in _RULE_CALL_RE.finditer(folded):
        if blanked.startswith("service", m.start()) and by_rule.get(m.group(2)) is not None:
            found.append(by_rule[m.group(2)])
    for m in _CRUD_CALL_RE.finditer(blanked):
        if by_method.get((m.group(1), m.group(2))) is not None:
            found.append(by_method[(m.group(1), m.group(2))])
    return found


def _reacher(hits, callees_of):
    """`reaches(entry)`: the first body among `hits` that `entry` is, or can reach through literal calls - else None.

    A rule called from a rule is not a different rule: what is refused, or what needs guarding, in the one at the
    end of the chain is that of everything that can start it."""
    reached = {}

    def reaches(entry, trail=frozenset()):
        key = id(entry)
        if key in hits:
            return entry
        if key in reached:
            return reached[key]
        if key in trail:
            return None                    # a cycle adds nothing
        for callee in callees_of(entry):
            hit = reaches(callee, trail | {key})
            if hit is not None:
                reached[key] = hit
                return hit
        if not trail:
            reached[key] = None            # a "no" worked out inside a cycle may be wrong; only a top-level one is final
        return None

    return reaches


def _check_rule_manages_people(p, r):
    """`service.security.users` / `service.security.roleGroups` - the ways a script goes wrong (doc 16 §2.3).

    ERROR - a PREDICATE or a VALIDATION_RULE that refers to either namespace. The runtime wires a refusing variant
    there (they are evaluated for an answer, possibly once per row), so the first evaluation throws; the author
    would only find out when the first user opens the page. The same for one that CALLS (`service.rule("X")`,
    `service.crud.<alias>.<method>(...)`, literal names) a body that manages people: the refusal follows the call.

    ERROR - a member that does not exist: `service.security.users.find(...)`, `.setPassword(...)`,
    `service.security.roleGroups.assign(...)` ... The names an author guesses by analogy are exactly the ones that are
    not there, and the failure is a `MissingMethodException` on the first run. Also a CALL
    `service.security.<name>(...)` that is none of the five checks (`service.security.roles()`, `.createUser(...)`).

    ERROR - an EXECUTION rule or CRUD GROOVY method that manages people (or calls one that does) and whose execution
    access is `publicAccess: true`: an anonymous visitor could then add accounts and role groups to the project.
    WARN - the same with the DEFAULT access (absent / null / signed-in users): every account of the project can
    run it from the browser console whatever button hides it - the Settings -> Accesses grants guard the User and
    Role Management SCREENS, not rules, so the rule's own access is the only gate there is. And that gate is the
    OUTERMOST rule or method a caller can start: a rule called from a rule is not checked again, so restricting
    the inner one does not protect it from a default-access rule that calls it - which is why the callers are
    judged too. A rule that only READS the people (`get`, `list`, `members`) is told apart in the wording: if
    everybody who can run it is meant to see that list, accept the warning and record why.

    Comments and string literals are blanked first: a call parked behind `//`, or a help text that mentions the
    name, is not a defect. The limits of a text check: the namespace passed through a variable
    (`def s = service.security`), a computed rule name, and `.with {}` on `service` or `service.security`."""
    from . import execaccess

    entries = _groovy_bodies(p)
    code_of = {id(e): _people_code(e[1]) for e in entries}
    answer_only = ("PREDICATE", "VALIDATION_RULE")
    refers = {id(e) for e in entries if _PEOPLE_REF_RE.search(code_of[id(e)][1])}
    manages = {id(e) for e in entries if id(e) in refers and e[2] not in answer_only}
    by_rule = {e.rule_name: e for e in entries if e.rule_name}
    by_method = {e.method_ref: e for e in entries if e.method_ref}

    def effect_of(entry):
        used = sorted(set(_PEOPLE_MEMBER_RE.findall(code_of[id(entry)][1])))
        # A reference the check cannot read members from (the namespace handed around, `.with {}`) is the worse case.
        changes = (not used) or any(member in _PEOPLE_MUTATING_MEMBERS[namespace] or member in _OBJECT_MEMBERS
                                    or member not in _PEOPLE_MEMBERS[namespace]
                                    for namespace, member in used)
        return used, changes

    reaches = _reacher(manages, lambda entry: _literal_callees(*code_of[id(entry)], by_rule, by_method))

    def judge_access(where, who, access, does, target, via):
        """The ERROR / WARN about who may run a rule that manages people - or reaches one."""
        if execaccess.shape_problems(access):
            return                       # reported by _check_execution_access_shape; there is no level to judge here
        subject = "%s %s (service.security.users / .roleGroups)" % (where, does) if via is None else (
            "%s calls %s, which %s (service.security.users / .roleGroups) - a rule called from a rule is not "
            "checked again, so the access you gave %s does not protect it here -" % (where, via, does, via))
        if execaccess.is_public(access):
            r.err("%s and %s execution access is publicAccess:true - ANYONE, anonymous visitors included, could %s. "
                  "Open it to the role group that administers people. %s"
                  % (subject, who, "add accounts and role groups to this project" if "manages" in does
                     else "read the names, addresses and role groups of everybody in this project", _PEOPLE_DOC))
        elif access is None or (isinstance(access, dict) and access.get("authenticatedUserAccess") is True):
            r.warn("%s and %s execution access lets ANY signed-in user run it - the default (a clerk can call it from "
                   "the browser console whatever button hides it). The Settings -> Accesses grants guard the "
                   "User/Role Management screens, not rules, so the access of the OUTERMOST rule or method a "
                   "caller can start is the only gate: set it to the role group that administers people (%s)%s. %s"
                   % (subject, who, "mrjun.py crud method-access" if target else "mrjun.py rule access --role-group",
                      " - or, if everybody who may run it is meant to see this list, accept this warning and record "
                      "why" if "reads" in does else "", _PEOPLE_DOC))

    for entry in entries:
        where, _body, rule_type, access, is_method = entry
        folded, code = code_of[id(entry)]

        for name in sorted(set(_SECURITY_CALL_RE.findall(code))):
            if name not in _SECURITY_CHECK_MEMBERS and name not in _OBJECT_MEMBERS:
                r.err("%s calls service.security.%s(...), which does not exist - service.security answers user() and "
                      "the four hasAny/All checks (%s); people are managed through service.security.users / "
                      ".roleGroups, which are properties, not methods. %s"
                      % (where, name, ", ".join(_SECURITY_CHECK_MEMBERS), _PEOPLE_DOC))

        who = "the method's" if is_method else "the rule's"

        if id(entry) not in refers:
            # It never names the namespace itself - but it may call something that does.
            target = reaches(entry, frozenset())
            if target is None:
                continue
            if rule_type in answer_only:
                r.err("%s is a %s and calls %s, which manages people - the refusal follows the call, so every member "
                      "throws 'is not available in rules called from %s' there (those rules are evaluated for an "
                      "answer, possibly once per row). Do it from an EXECUTION_RULE or a CRUD GROOVY method that "
                      "something DOES start. %s"
                      % (where, rule_type, target[0],
                         "predicates" if rule_type == "PREDICATE" else "validation rules", _PEOPLE_DOC))
                continue
            _used, changes = effect_of(target)
            judge_access(where, who, access, "manages people" if changes else "reads the project's people",
                         is_method, target[0])
            continue

        if rule_type in answer_only:
            r.err("%s is a %s and uses service.security.users / service.security.roleGroups - every member throws "
                  "'is not available in %s' there (those rules are evaluated for an answer, possibly once per row). "
                  "Manage people from an EXECUTION_RULE or a CRUD GROOVY method. %s"
                  % (where, rule_type, "predicates" if rule_type == "PREDICATE" else "validation rules", _PEOPLE_DOC))
            continue

        used, changes = effect_of(entry)
        for namespace, member in used:
            if member not in _PEOPLE_MEMBERS[namespace] and member not in _OBJECT_MEMBERS:
                r.err("%s calls service.security.%s.%s(...), which does not exist - service.security.%s has "
                      "exactly: %s. %s"
                      % (where, namespace, member, namespace, ", ".join(_PEOPLE_MEMBERS[namespace]), _PEOPLE_DOC))
        judge_access(where, who, access, "manages people" if changes else "reads the project's people",
                     is_method, None)


# `service.pubsub` (doc 33 §4, doc 16 §2.17) and `service.messenger` (doc 36 §4, doc 16 §2.18) are the same kind of
# object: a namespace whose every PROPERTY is the alias of a connection configured live in Settings -> Developer ->
# Integrations, whose few METHODS are its own (`list()`, `channel(alias)`, ...), and whose channels answer a handful of
# members. Both exist in every rule type, but only an EXECUTION rule or a CRUD GROOVY method may use them: in a
# predicate or a validation rule every member throws. The alias rules, the member names and the option names mirror the
# platform's own (what the Settings screen accepts as an alias, what each proxy has, the options a single call may
# carry) - the validator is stdlib-only and cannot read them, so this is the one place they are repeated.
_ALIAS_LANGUAGE_WORDS = frozenset((
    "abstract as assert boolean break byte case catch char class const continue def default do double else enum "
    "extends false final finally float for goto if implements import in instanceof int interface long native new "
    "null package private protected public return short static strictfp super switch synchronized this threadsafe "
    "throw throws trait transient true try var void volatile while yield record sealed permits metaclass "
    "properties binding delegate owner").split())
_ALIAS_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}$")
_NAMED_KEY_RE = re.compile(r"""\s*(?P<key>[A-Za-z_]\w*|'[ ]*'|"[ ]*")\s*:(?!:)""")


class _OptionCall(object):
    """How one member takes its options: the positional that is the options map (`options_at`, 0-based), the words of
    the member's all-named form (`call_keys`; None when it has none - an all-named call then finds no method), and the
    words it takes besides the namespace's options (`extra`; `only` replaces the options altogether)."""

    def __init__(self, options_at, call_keys=None, extra=(), only=None):
        self.options_at = options_at
        self.call_keys = call_keys
        self.extra = tuple(extra)
        self.only = None if only is None else tuple(only)

    def legal(self, options):
        return self.only if self.only is not None else tuple(options) + self.extra


# A member that takes no options at all (`delete`, `typing`): only how it is called is checked.
_NO_OPTIONS = _OptionCall(99, only=())


class _AliasNamespace(object):
    """One `service.<name>` namespace, as the checks need to know it."""

    def __init__(self, name, namespace_members, channel_members, reserved, options, doc, verb, kind_word,
                 settings_place, channel_shape, option_note, namespace_calls, channel_calls, positional_only):
        self.name = name
        self.ref = re.compile(r"\bservice\s*\.\s*%s\b" % name)
        self.namespace_members = namespace_members
        self.channel_members = channel_members
        self.reserved = reserved
        self.options = options
        self.doc = doc
        self.verb = verb                          # "Publish" / "Send"
        self.kind_word = kind_word                # "broker kind" / "messenger"
        self.settings_place = settings_place      # "PubSub" / "Messengers"
        self.channel_shape = channel_shape        # what a channel has, in words
        self.option_note = option_note            # said after the list of options
        self.namespace_calls = namespace_calls    # namespace member -> _OptionCall
        self.channel_calls = channel_calls        # channel member -> _OptionCall
        self.positional_only = positional_only    # members an all-named call finds no method for
        self.channel_re = re.compile(
            r"\bservice\s*\.\s*%s\s*"
            r"(?:\.\s*(?P<prop>[A-Za-z_]\w*)(?!\s*\()"
            r"|(?P<sub>\[\s*(['\"])[^'\"\n]*\3\s*\])"
            r"|\.\s*channel\s*\(\s*(?P<arg>(['\"])[^'\"\n]*\5)\s*\))"
            r"\s*\.\s*(?P<member>[A-Za-z_]\w*)" % name)
        self.namespace_call_re = re.compile(r"\bservice\s*\.\s*%s\s*\.\s*([A-Za-z_]\w*)\s*\(" % name)
        self.property_re = re.compile(r"\bservice\s*\.\s*%s\s*\.\s*([A-Za-z_]\w*)(?!\s*\()" % name)
        self.channel_arg_re = re.compile(r"\bservice\s*\.\s*%s\s*(?:\[\s*(['\"])([^'\"\n]*)\1\s*\]"
                                         r"|\.\s*channel\s*\(\s*(['\"])([^'\"\n]*)\3\s*\))" % name)

    def namespace_shape(self):
        members = [m + ("(alias)" if m == "channel" else "(message, text)" if m == "reply" else "()")
                   for m in self.namespace_members]
        return members[0] if len(members) == 1 else ", ".join(members[:-1]) + " and " + members[-1]

    def alias_problem(self, alias):
        """Why `alias` can never be the alias of a connection, or None. The same rules the Settings screen applies."""
        if not _ALIAS_RE.match(alias):
            return ("'%s' is not a legal alias - it must start with a letter and use only letters, digits and "
                    "underscores, at most 40" % alias)
        lowered = alias.lower()
        if lowered in _ALIAS_LANGUAGE_WORDS or lowered in self.reserved:
            return ("'%s' is a reserved word, or a member of service.%s itself - no connection can have that alias"
                    % (alias, self.name))
        return None


_PUBSUB_OPTIONS = ("qos", "retain", "exchange", "persistent", "defaultType", "timeToLiveMs", "key", "contentType",
                   "headers")
_PUBSUB = _AliasNamespace(
    name="pubsub",
    namespace_members=("list", "channel"),
    channel_members=("publish", "alias"),
    reserved=("list", "aliases", "channels", "channel", "get", "alias", "exists", "names", "has"),
    # What a single publish call may carry besides its destination and payload: the options a message can have in any
    # of the four kinds, and the three every kind takes. (Kafka `acks` and RabbitMQ `confirm` are the CONNECTION's.)
    options=_PUBSUB_OPTIONS,
    doc="(33-pubsub-integration.md §4, 16-groovy-service-api.md §2.17)",
    verb="Publish",
    kind_word="broker kind",
    settings_place="PubSub",
    channel_shape="publish(destination, payload[, options])",
    option_note=" (what is fixed when the connection opens - Kafka acks, RabbitMQ confirm - is a setting of the "
                "connection, not of a call)",
    namespace_calls={},
    channel_calls={"publish": _OptionCall(2, ("destination", "topic", "queue", "routingKey", "payload"))},
    positional_only=())

# The generic options of every messenger, then each kind's own per-message ones (the catalog's per-call send fields).
_MESSENGER_TO_KEYS = ("to", "chat", "chatId", "channel", "recipient", "phone")
_MESSENGER_TEXT_KEYS = ("text", "message", "body")
_MESSENGER = _AliasNamespace(
    name="messenger",
    namespace_members=("list", "channel", "reply"),
    channel_members=("send", "sendFile", "reply", "answer", "edit", "delete", "typing", "download", "chats", "alias"),
    reserved=("list", "channel", "channels", "get", "alias", "aliases", "exists", "names", "has", "reply", "send"),
    options=("format", "buttons", "replyTo", "thread", "silent", "file",
             "humanAgent", "intent", "linkPreview", "listButton", "notice", "protectContent", "senderAvatar",
             "senderName", "template", "templateComponents", "templateLanguage", "templateParams", "trackingData",
             "username"),
    doc="(36-messenger-integration.md §4, 16-groovy-service-api.md §2.18)",
    verb="Send",
    kind_word="messenger",
    settings_place="Messengers",
    channel_shape="send, sendFile, reply, answer, edit, delete, typing, download and chats",
    option_note="",
    namespace_calls={"reply": _OptionCall(2, extra=("quote",))},
    channel_calls={
        "send": _OptionCall(2, _MESSENGER_TO_KEYS + _MESSENGER_TEXT_KEYS),
        "sendFile": _OptionCall(2, _MESSENGER_TO_KEYS + ("file",),
                                extra=_MESSENGER_TEXT_KEYS + ("name", "mimeType", "kind")),
        "reply": _OptionCall(2, extra=("quote",)),
        "edit": _OptionCall(3),
        "delete": _OptionCall(2),
        "answer": _OptionCall(2, only=("alert",)),
    },
    positional_only=("reply", "edit", "delete", "typing"))


def _split_top_level(blanked, start, end):
    """The (start, end) spans of the comma-separated pieces of blanked[start:end], nesting respected. Strings are
    already emptied, so a comma or a bracket inside one cannot confuse it."""
    spans, depth, begin = [], 0, start
    for i in range(start, end):
        ch = blanked[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            spans.append((begin, i))
            begin = i + 1
    if blanked[begin:end].strip():
        spans.append((begin, end))
    return spans


def _closing_paren(blanked, open_at):
    """Index of the `)` that closes the `(` at `open_at`, or None when the text ends first."""
    depth = 0
    for i in range(open_at, len(blanked)):
        if blanked[i] in "([{":
            depth += 1
        elif blanked[i] in ")]}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _named_key(folded, blanked, start, end):
    """(key, value_start) when blanked[start:end] is `key: value` (a quoted key counts), else None."""
    m = _NAMED_KEY_RE.match(blanked, start, end)
    if not m:
        return None
    return folded[m.start("key"):m.end("key")].strip("'\""), m.end()


def _call_option_keys(folded, blanked, open_at, call):
    """(keys, all_named) for one call: the keys it spells out as (key, is_option) - literal ones only - and whether every
    argument is named. A key built at run time, a variable holding the options map, a spread: nothing static can say
    what they hold, so they are left alone."""
    close = _closing_paren(blanked, open_at)
    if close is None:
        return [], False
    pieces, positional, named = _split_top_level(blanked, open_at + 1, close), [], []
    for start, end in pieces:
        key = _named_key(folded, blanked, start, end)
        if key:
            named.append(key[0])
        else:
            positional.append((start, end))
    # `publish(destination: 't', payload: 1, qos: 1)` is the call form, where destination and payload are the call's
    # own words. Next to positional arguments the named ones are Groovy's leading options map instead.
    all_named = bool(named) and not positional
    call_keys = call.call_keys or ()
    keys = [(key, not (all_named and key in call_keys)) for key in named]
    # A map literal: the options (at their position), or - alone - the whole call.
    maps = []
    if len(positional) == 1 and len(pieces) == 1 and call.call_keys is not None:
        maps.append((positional[0], True))
    elif len(positional) > call.options_at:
        maps.append((positional[call.options_at], False))
    for (start, end), whole_call in maps:
        text = blanked[start:end].strip()
        if not (text.startswith("[") and text.endswith("]")):
            continue
        inner_start = blanked.index("[", start) + 1
        inner_end = blanked.rindex("]", start, end)
        for a, b in _split_top_level(blanked, inner_start, inner_end):
            key = _named_key(folded, blanked, a, b)
            if key:
                keys.append((key[0], not (whole_call and key[0] in call_keys)))
    return keys, all_named


def _check_rule_uses_pubsub(p, r):
    """`service.pubsub` - the ways a script goes wrong (doc 33 §4, doc 16 §2.17).

    ERROR - a PREDICATE or a VALIDATION_RULE that uses the namespace, or CALLS (`service.rule("X")`,
    `service.crud.<alias>.<method>(...)`, literal names) a body that does: every member throws there, because those
    rules are evaluated for an answer, possibly once per row, and a message sent as a side effect of drawing a button
    is a message nobody decided to send. The author would only find out when the first user opens the page.

    ERROR - a member that does not exist: `service.pubsub.<alias>.send(...)` / `.subscribe(...)` / `.consume(...)`
    (a channel has `publish`; receiving is a LISTENER, configured live, not something a rule does) and a CALL on the
    namespace that is neither `list()` nor `channel(alias)` (`service.pubsub.channels()`, `service.pubsub.plant(...)`).

    ERROR - an alias that can never exist: `service.pubsub['my-broker']`, `service.pubsub.channel('my broker')`, a
    reserved word (`service.pubsub.names`, `service.pubsub.get`).

    WARN - a literal option in `publish(...)` that no broker kind has (`qoss: 1`, `retained: true`, and `acks`, which
    belongs to the connection): the call is refused at run time. Whether the option belongs to THIS connection's kind
    is not known offline, and the run-time message lists the ones that do.

    It cannot know that an alias is connected, that a listener points at a rule, or that a rule is idempotent: that is
    the handover (doc 33 §8). Comments and string literals are blanked first. The limits of a text check: the
    namespace passed through a variable (`def b = service.pubsub.plant`), a computed rule name or alias, and
    `.with {}` on `service` or `service.pubsub`."""
    _check_rule_uses_alias_namespace(p, r, _PUBSUB)


def _check_rule_uses_messenger(p, r):
    """`service.messenger` - the same checks as `service.pubsub` (doc 36 §10, doc 16 §2.18).

    ERROR - a PREDICATE or a VALIDATION_RULE that uses it, directly or through a literal `service.rule("X")` /
    `service.crud.<alias>.<method>(...)`: every member throws there.

    ERROR - a channel member that does not exist (`.post(...)`, `.sendMessage(...)`, `.subscribe(...)`: a channel has
    send, sendFile, reply, answer, edit, delete, typing, download and chats - receiving is a LISTENER), and a call on
    the namespace that is not `list()`, `channel(alias)` or `reply(message, text)`.

    ERROR - an alias that can never exist (`service.messenger['my-bot']`, a keyword, a member of the namespace).

    ERROR - `reply` / `edit` / `delete` / `typing` called with named arguments only: they take their arguments by
    position (options may follow as `name: value`), and Groovy finds no method for a lone map.

    WARN - a literal option no messenger has (`buttns:`, `parse_mode:`; `answer` takes only `alert`): refused at run
    time. Whether the option is THIS connection's kind's is not known offline - the run-time message lists those."""
    _check_rule_uses_alias_namespace(p, r, _MESSENGER)


# What the rule sandbox refuses before a rule runs (doc 08 "The rule sandbox"). The platform's own check resolves
# types and reads every name; these are the mistakes an author - or an older document - actually makes, found before
# the archive is imported rather than when the rule first runs.
_SANDBOX_REFUSALS = (
    (re.compile(r"(?<![\w$.])System\s*\.\s*(?!(?:currentTimeMillis|nanoTime|lineSeparator|identityHashCode|"
                r"arraycopy|out|err)\b)([A-Za-z_]\w*)"),
     "uses System.{0} - a rule may read the clock and write to System.out, nothing else of System"),
    (re.compile(r"(?<![\w$.])Thread\s*\.\s*(?!sleep\b)([A-Za-z_]\w*)"), "uses Thread.{0} - only Thread.sleep(ms)"),
    (re.compile(r"(?<![\w$.])inject\s*\("),
     "calls inject(...) - inject() is gone: everything a rule may use is on service.*"),
    (re.compile(r"(?<![.\w$])@\s*[A-Za-z_$]"),
     "carries an annotation - an annotation runs code while the rule is compiled, so none is allowed"),
    (re.compile(r"\.\s*@"), "reads a field past its accessors (.@)"),
    # value.class / value.getClass() is fine for its NAME (e.class.simpleName in a message), compared with a type
    # (e.getClass() == RuntimeException - see _CLASS_COMPARED), and instanceof for any type.
    (re.compile(r"(?:\b[a-z_$][\w$]*|[)\]])\s*\??\.\s*class\b(?!\s*\??\.\s*(?:simpleName|name|canonicalName|typeName|"
                r"getSimpleName|getName|getCanonicalName|getTypeName)\b|\s*(?:===?|!==?|!?in\b))"),
     "reads .class of a value - test what it is with instanceof, or ask its name (.class.simpleName)"),
    (re.compile(r"(?<![\w$])(getClass(?!\s*\(\s*\)\s*\??\.\s*(?:simpleName|name|canonicalName|typeName|"
                r"getSimpleName|getName|getCanonicalName|getTypeName)\b|\s*\(\s*\)\s*(?:===?|!==?|!?in\b))|forName|newInstance|invokeMethod|getMetaClass|"
                r"setMetaClass|getProperties|getMetaPropertyValues|dump|mixin|setDefault|addShutdownHook|evaluate|"
                r"toURL|getenv|setAccessible|getDeclaredFields?|getDeclaredMethods?)\s*\("),
     "calls {0}(...) - reflection, a process, a URL or what every project shares"),
    # Groovy's execute() on text or a list starts a process; a CRUD's execute() (service.crud.payment.execute) is its own.
    (re.compile(r"(?:['\"\]]|\bnew\s+String\s*\[[^\]]*\]\s*\{[^}]*\})\s*\.\s*execute\s*\("),
     "calls execute(...) on text or a list - that starts a process"),
    (re.compile(r"(?<![\w$])metaClass\b"), "uses metaClass"),
    (re.compile(r"(?<![\w$])synchronized\s*\("), "takes a lock (synchronized)"),
    # A CLASS's default (Locale.default = ...) is the JVM's; a map's key named default is data.
    (re.compile(r"\b[A-Z][\w$]*\s*\.\s*default\s*=(?!=)"),
     "changes a class's default - the JVM-wide default every project shares"),
    (re.compile(r"\b(java\.io|java\.nio\.file|java\.net|java\.lang\.reflect|java\.lang\.invoke|org\.springframework|"
                r"com\.devsegment)\.(?!(?:URLEncoder|URLDecoder)\b)\w+"),
     "uses {0}.* - a rule computes with plain values and reaches the rest through service.* and context.*"),
    (re.compile(r"(?<![\w$.])new\s+(File|URL|URI|Socket|ServerSocket|ProcessBuilder|GroovyShell|GroovyClassLoader|"
                r"Thread|FileInputStream|FileOutputStream|FileReader|FileWriter|RandomAccessFile)\s*\("),
     "uses {0} - files, network and processes are not a rule's: read and write through service.* and context.*"),
    (re.compile(r"(?<![\w$.])(Runtime|GroovyShell|Eval|ProcessBuilder|ClassLoader)\s*\."), "uses {0}"),
)


def _class_compared_before(code, start):
    """Whether the class read starting at `start` is the right-hand side of a comparison - `RuntimeException ==
    e.getClass()`, `T != a.b.class`: compared, never held. The receiver chain before it is stepped over."""
    before = re.sub(r"[\w$.?\s]*$", "", code[max(0, start - 200):start])
    return bool(re.search(r"(?:===?|!==?)$", before))


def _check_rule_sandbox(p, r):
    """ERROR for what the platform's rule sandbox refuses before the rule runs - an author's code runs in a service
    that serves every project, so a rule may compute with plain values and reach the rest through service.* and
    context.*, nothing else. Comments and the text of strings are not code: an e-mail address in a message is not an
    annotation."""
    for where, body, _rule_type, _access, _is_method in _groovy_bodies(p):
        code = _blank_strings(_strip_groovy_comments(body))
        reported, taken = set(), []
        for pattern, refusal in _SANDBOX_REFUSALS:
            for match in pattern.finditer(code):
                what = refusal.format(*[g for g in match.groups() if g is not None]) if match.groups() else refusal
                # One sentence per mistake: System.getenv is one, though two of the patterns see it.
                if what in reported or any(match.start() < end and start < match.end() for start, end in taken):
                    continue
                if ("getClass" in what or ".class" in what) and _class_compared_before(code, match.start()):
                    continue
                reported.add(what)
                taken.append(match.span())
                line = code.count("\n", 0, match.start()) + 1
                r.err("%s: line %d %s. The platform refuses the rule before it runs ('This rule may not do what it "
                      "asks'); see doc 08 'The rule sandbox'." % (where, line, what))


def _check_rule_uses_alias_namespace(p, r, ns):
    """The checks of `_check_rule_uses_pubsub` / `_check_rule_uses_messenger`, for the namespace `ns` describes."""
    entries = _groovy_bodies(p)
    code_of = {id(e): (lambda folded: (folded, _blank_strings(folded)))(_fold_property_chain(_strip_groovy_comments(e[1])))
               for e in entries}
    answer_only = ("PREDICATE", "VALIDATION_RULE")
    refers = {id(e) for e in entries if ns.ref.search(code_of[id(e)][1])}
    uses = {id(e) for e in entries if id(e) in refers and e[2] not in answer_only}
    by_rule = {e.rule_name: e for e in entries if e.rule_name}
    by_method = {e.method_ref: e for e in entries if e.method_ref}
    reaches = _reacher(uses, lambda entry: _literal_callees(*code_of[id(entry)], by_rule, by_method))
    space = "service." + ns.name

    for entry in entries:
        where, _body, rule_type, _access, _is_method = entry
        folded, code = code_of[id(entry)]

        if rule_type in answer_only:
            kind = "predicates" if rule_type == "PREDICATE" else "validation rules"
            if id(entry) in refers:
                r.err("%s is a %s and uses %s - every member throws 'is not available in %s' there (those "
                      "rules are evaluated for an answer, possibly once per row, and a message is a side effect). "
                      "%s from an EXECUTION_RULE or a CRUD GROOVY method that something DOES start. %s"
                      % (where, rule_type, space, kind, ns.verb, ns.doc))
            else:
                target = reaches(entry)
                if target is not None:
                    r.err("%s is a %s and calls %s, which uses %s - the refusal follows the call, so "
                          "every member throws 'is not available in rules called from %s' there. %s from an "
                          "EXECUTION_RULE or a CRUD GROOVY method that something DOES start. %s"
                          % (where, rule_type, target[0], space, kind, ns.verb, ns.doc))
            continue
        if id(entry) not in refers:
            continue

        reported = set()

        def report_once(text, level=r.err):
            if text not in reported:
                reported.add(text)
                level(text)

        def check_options(call, member_text, open_at, member):
            keys, all_named = _call_option_keys(folded, code, open_at, call)
            if all_named and member in ns.positional_only:
                report_once("%s calls %s(...) with named arguments only - %s takes its arguments by position "
                            "(options may follow as name: value), and Groovy finds no method for a lone map. %s"
                            % (where, member_text, member, ns.doc))
                return
            if call is _NO_OPTIONS:
                return
            legal = call.legal(ns.options)
            for key, is_option in keys:
                if is_option and key not in legal:
                    report_once("%s calls %s(...) with the option '%s', which no %s has - the call is refused at run "
                                "time. Options: %s%s. %s"
                                % (where, member_text, key, ns.kind_word, ", ".join(legal), ns.option_note, ns.doc),
                                r.warn)

        # -- a call on the namespace that is not one of its methods --
        for m in ns.namespace_call_re.finditer(code):
            name = m.group(1)
            if name not in ns.namespace_members and name not in _OBJECT_MEMBERS:
                report_once("%s calls %s.%s(...), which does not exist - %s has exactly %s; a connection is "
                            "addressed as a property, %s.<alias>.%s(...). %s"
                            % (where, space, name, space, ns.namespace_shape(), space, ns.channel_members[0], ns.doc))
            elif name in ns.namespace_calls:
                check_options(ns.namespace_calls[name], space + "." + name, m.end() - 1, name)

        # -- a literal alias that can never exist --
        for m in ns.property_re.finditer(code):
            name = m.group(1)
            if name not in ns.namespace_members and name not in _OBJECT_MEMBERS:
                problem = ns.alias_problem(name)
                if problem:
                    report_once("%s uses %s.%s: %s. %s" % (where, space, name, problem, ns.doc))
        for m in ns.channel_arg_re.finditer(folded):
            if not code.startswith("service", m.start()):
                continue
            alias = m.group(2) if m.group(2) is not None else m.group(4)
            problem = ns.alias_problem(alias.strip())
            if problem:
                report_once("%s addresses a connection by an alias that can never exist: %s. %s"
                            % (where, problem, ns.doc))

        # -- what is called on a channel, and with which options --
        for m in ns.channel_re.finditer(code):
            member = m.group("member")
            name = m.group("prop") or "<alias>"
            if member in _OBJECT_MEMBERS:
                continue
            if member not in ns.channel_members:
                report_once("%s calls %s.%s.%s(...), which does not exist - a channel has exactly %s. Receiving "
                            "is a LISTENER, configured live in Settings -> Developer -> Integrations -> %s, not "
                            "something a rule does. %s"
                            % (where, space, name, member, ns.channel_shape, ns.settings_place, ns.doc))
                continue
            after = re.compile(r"\s*\(").match(code, m.end())
            if not after:
                continue
            call = ns.channel_calls.get(member, _NO_OPTIONS if member in ns.positional_only else None)
            if call is not None:
                check_options(call, "%s.%s.%s" % (space, name, member), after.end() - 1, member)


# `crudDataMap: [ <alias>: [ value: <row> ] ]` inside the document literal a rule hands to
# `service.workflow.start(...)`. A rule-started case seeds the process's context data ITSELF, and every surface
# that reads a process resolves against that document — a scope=CRUD process-table column reads
# contextDataMap[ctx].crudDataMap[alias] for a scope=CRUD column, and a form control at scope=CRUD reads the same
# place. So an alias the starter seeded DOES render, and a project with no start form at all (27) must not be
# warned about every one of them. (27-event-driven-process-start.md §4.2, §6)
_CRUD_DATA_MAP_OPEN_RE = re.compile(r"""(?<![\w.$])['"]?crudDataMap['"]?\s*:\s*\[""")
# Keys of the map, once nested levels are blanked out: `alias:`, `'alias':`, `"alias":`. A computed key —
# `(aliasVar):` — is left out on purpose: nothing static can say which alias it is.
_MAP_KEY_RE = re.compile(r"""(?:\[|,)\s*['"]?([A-Za-z_]\w*)['"]?\s*:""")


def _top_level_of_bracket_block(text, start):
    """The `[...]` beginning at `start`, with everything NESTED inside it replaced by spaces.

    Positions are preserved so the caller can still regex it; blanking the nested levels is what makes a plain
    key regex safe on a document literal that is three maps deep."""
    depth, out, i = 0, [], start
    while i < len(text):
        ch = text[i]
        if ch in "[{(":
            depth += 1
            out.append(ch if depth == 1 else " ")
        elif ch in "]})":
            out.append(ch if depth == 1 else " ")
            depth -= 1
            if depth == 0:
                return "".join(out)
        else:
            out.append(ch if depth <= 1 else " ")
        i += 1
    return "".join(out)  # unbalanced literal: parse what there is rather than throwing the whole check away


def _document_seeded_crud_aliases(p):
    """Crud aliases any rule (or CRUD GROOVY method) seeds into a start document it passes to
    `service.workflow.start(...)`.

    Only bodies that actually call `start(` are read: a `crudDataMap` key elsewhere is some other document.
    Comments are stripped first, for the same reason every other Groovy check strips them."""
    bodies = [_rule_script(rule) for rule in p.rep.get("rules", []) or []]
    _by_alias, cruds = _dynamic_crud_methods(p)
    for crud in cruds:
        for m in crud.get("methods", []) or []:
            if m.get("methodType") == "GROOVY" and m.get("script"):
                bodies.append(m["script"])
    aliases = set()
    for body in bodies:
        body = _strip_groovy_comments(body)
        if "service.workflow.start" not in body:
            continue
        for m in _CRUD_DATA_MAP_OPEN_RE.finditer(body):
            block = _top_level_of_bracket_block(body, m.end() - 1)
            aliases |= set(_MAP_KEY_RE.findall(block))
    return aliases


# The bare `contextDataMap` binding, read as an EXPRESSION. Deliberately NOT matched: `contextDataMap:` and
# `'contextDataMap':` (a map KEY — the outermost key of the document a headless rule must BUILD, so flagging it
# would flag the correct answer), and `<something>.contextDataMap` (a property of a document the rule fetched or
# assembled itself).
_BARE_CONTEXT_DATA_MAP_RE = re.compile(r"""(?<![\w.$'"])contextDataMap\b(?!['"]?\s*:)""")
# An author who declares, assigns or null-guards the name owns it. The rule script is spliced into a method body,
# so `def contextDataMap = ...` is a LOCAL that shadows the null field; an assignment fills the field before it is
# read; and `?.` / `?:` / `!= null` / `if (contextDataMap)` are somebody who already knows it can be null.
_OWNED_CONTEXT_DATA_MAP_RE = re.compile(
    r"""(?<![\w.$])(?:def|var|final|Map(?:<[^<>]*>)?)\s+contextDataMap\b"""
    r"""|(?<![\w.$'"])contextDataMap\s*(?:=(?!=)|\?\.|\?:|[!=]=\s*null)"""
    r"""|\bif\s*\(\s*contextDataMap\s*[)&|]"""
)


def _check_scheduler_rule_context_data_map(p, r):
    """A scheduler hands its rules NOTHING: the gate goes over REST and the action over Kafka, and neither hop
    attaches context data — the message carries the schedule, the rule, the tenant and the schedule's service
    user, no more. The executor then builds a fresh document whose `contextDataMap` is null, so in a scheduler's
    own rules the binding of that name is null, always.

    That is silent in the one place it matters most. `[contextDataMap: contextDataMap]` — the shortcut every
    form rule forwards its document with — starts a process seeded with NOTHING: the call succeeds, returns a
    process identifier, and the case dies at its first serviceTask with `No CRUD data available for CRUD:
    <alias>`, a long way from the rule that caused it. In a predicate the same read throws, the gate hop turns
    the exception into FALSE, and the schedule never fires again.

    Only rules a scheduler NAMES are checked (`schedulers[].actionRuleIdentifier` / `predicateIdentifier`) — an
    ordinary form or process rule receives a real document and uses the shortcut correctly. Comments are stripped
    first, and a body that declares, assigns or null-guards the name is left alone: that author already knows.
    (27-event-driven-process-start.md §2.1, §4.3 for the action, §4.5 for the gate)"""
    scheds = p.rep.get("schedulers", []) or []
    if not scheds:
        return
    rules_by_id = {rr.get("identifier"): rr for rr in p.rep.get("rules", []) or [] if isinstance(rr, dict)}
    seen = set()
    for s in scheds:
        nm = s.get("name") or s.get("identifier")
        for slot, key in (("action", "actionRuleIdentifier"), ("gate", "predicateIdentifier")):
            rid = s.get(key)
            rule = rules_by_id.get(rid) if rid else None
            if not rule or rid in seen:
                continue
            body = _rule_script(rule)
            if not body:
                continue
            # Comments out first: a parked-out line is not a defect, and a checker that says otherwise stops
            # being usable as the reimport gate.
            body = _strip_groovy_comments(body)
            if not _BARE_CONTEXT_DATA_MAP_RE.search(body) or _OWNED_CONTEXT_DATA_MAP_RE.search(body):
                continue
            seen.add(rid)
            # The two slots fail in opposite directions, so one remedy cannot serve both: the action must BUILD a
            # document, the gate must never build one at all (service.workflow.start is refused in a predicate).
            if slot == "action":
                remedy = ("`contextDataMap[...]` throws, and the `[contextDataMap: contextDataMap]` forwarding "
                          "shortcut starts an EMPTY process while still returning a process identifier (the case "
                          "then fails at its first serviceTask with 'No CRUD data available for CRUD: <alias>'). "
                          "Fetch the rows the rule needs with service.crud.<alias>.<method>(...) and build the "
                          "document literal from them — contextDataMap: [ (<contextIdentifier>): [ crudDataMap: "
                          "[ <alias>: [ value: <row> ] ], attrs: [:] ] ], attrs: [:]. "
                          "(27-event-driven-process-start.md §2.1, §4.3)")
            else:
                remedy = ("`contextDataMap[...]` throws on the synchronous REST hop the gate is evaluated over, "
                          "the scheduler reports any exception on that hop as FALSE, and the gate is then shut for "
                          "good with nothing in the UI to show for it. A gate may only ANSWER: count the candidates "
                          "with service.crud.<alias>.<countMethod>(...) or service.rimm.query(...) and end in an "
                          "explicit `return <boolean>`. It must never build or forward a document — the work "
                          "belongs in the action rule, and service.workflow.start is refused inside a predicate at "
                          "runtime. (27-event-driven-process-start.md §2.1, §4.5)")
            r.err("scheduler %r %s rule %r reads the bare `contextDataMap` binding — a scheduler tick attaches NO "
                  "context data on either hop, so that binding is null in this rule: %s"
                  % (nm, slot, rule.get("name"), remedy))


def _check_workflow_start_seeds_entity(p, r):
    """A workflow serviceTask that reads/writes `context.<ctx>.<alias>.data` needs `<alias>` SEEDED into the process
    contextData first. Unseeded, the executor auto-creates an EMPTY envelope for it (RuleExecutorReactor
    enhanceContextDataWithCrudInfo, for every alias of every attached context the document already has an entry
    for), so `.data.get()` answers an empty map and the task computes NULLS - silently. The throw
    `No CRUD data available for CRUD: <alias>` belongs to the harder case: the CONTEXT entry itself is missing
    (a mistyped context identifier, or a headless rule whose document is null). The
    process's initial contextData is the START form's contextData when a form starts it — a rule using
    `service.workflow.start(...)` supplies it directly instead, which is why the headless skip below is a skip
    and not a pass. So the workflow's start form (process.table `userStartProcessActions` -> formGroup -> form)
    must have >=1 field `scope=CRUD` + `crudAlias=<alias>`. This flags
    the FIRST serviceTask(s) after the StartEvent whose `.data` alias is not seeded by any start form (start-form
    fields all scope=GLOBAL, or binding a different crud). (07-workflows-and-tasks.md)"""
    rep = p.rep
    workflows = rep.get("workflows", []) or []
    if not workflows:
        return
    rules_by_id = {rr.get("identifier"): rr for rr in rep.get("rules", []) or []}
    forms_by_id = {f.get("identifier"): f for f in rep.get("forms", []) or []}
    fg_by_id = {g.get("identifier"): g for g in rep.get("formGroups", []) or []}
    node_by_id = {n.get("identifier"): n for n, _pp, _pt in core.iter_nodes(p.root_content)}
    start_fg = {}  # workflowId -> {start formGroup ids}
    for s in rep.get("settings", []) or []:
        c = s.get("content")
        if not isinstance(c, dict) or not c.get("workflowIdentifier"):
            continue
        for a in ((c.get("userStartProcessActions") or {}).get("actions") or []):
            if a.get("formGroupIdentifier"):
                start_fg.setdefault(c["workflowIdentifier"], set()).add(a["formGroupIdentifier"])
    # flag only the entity the first serviceTask WRITES BACK (`.data.put(`/`.setField(`) — that is the process
    # entity that MUST be seeded; a guarded read (`cid ? svc.get : X.data.get()`) is a fallback, not proof of need.
    data_alias_re = re.compile(r"context\.\w+\.(\w+)\.data\.(?:put|setField)\(")

    def props_of(el):
        return {pr.get("name"): pr.get("value") for pr in ((el.get("settings") or {}).get("properties") or [])}

    for wf in workflows:
        wfid = wf.get("identifier")
        node_type, flows, svc_rule, start_id = {}, {}, {}, None
        for el in wf.get("elements", []) or []:
            t = (el.get("settings") or {}).get("type")
            pr = props_of(el)
            nid = pr.get("id")
            if not nid:
                continue
            node_type[nid] = t
            if t == "bpmn:SequenceFlow":
                flows.setdefault(pr.get("sourceRef"), []).append(pr.get("targetRef"))
            elif t == "bpmn:ServiceTask":
                svc_rule[nid] = pr.get("rule") or ""
            elif t == "bpmn:StartEvent":
                start_id = nid
        if start_id is None:
            continue
        # BFS from the StartEvent; collect the first serviceTask(s) on each path (stop descending past one)
        first_svc, seen, q = set(), set(), [start_id]
        while q:
            cur = q.pop(0)
            if cur in seen:
                continue
            seen.add(cur)
            for tgt in flows.get(cur, []):
                if node_type.get(tgt) == "bpmn:ServiceTask":
                    first_svc.add(tgt)
                else:
                    q.append(tgt)
        needed = set()
        for sid in first_svc:
            for rid in str(svc_rule.get(sid, "")).split(","):
                rule = rules_by_id.get(rid.strip())
                script = ((rule.get("rule") or {}).get("ruleScriptStr") or "") if rule else ""
                needed.update(data_alias_re.findall(script))
        if not needed or wfid not in start_fg:
            continue  # no first-task .data usage, or no start form group found (headless) -> skip
        seeded, found_form = set(), False
        for fgid in start_fg[wfid]:
            fg = fg_by_id.get(fgid)
            for m in ((fg or {}).get("predicateFormMapping") or {}).get("mapping", []) or []:
                form = forms_by_id.get(m.get("formIdentifier"))
                cnode = node_by_id.get(form.get("contentIdentifier")) if form else None
                if not cnode:
                    continue
                found_form = True
                for n, _pp, _pt in core.iter_nodes(cnode):
                    pn = n.get("pluginName") or ""
                    if not (pn.startswith("dynaform.form.") and "field" in pn):
                        continue
                    sv = ((n.get("properties") or {}).get("settings") or {}).get("stringValue")
                    if not sv:
                        continue
                    try:
                        d = json.loads(sv)
                    except Exception:
                        continue
                    if d.get("scope") == "CRUD" and d.get("crudAlias"):
                        seeded.add(d["crudAlias"])
        if not found_form:
            continue
        for alias in sorted(needed - seeded):
            r.warn("workflow %r: its first serviceTask reads/writes context.<ctx>.%s.data, but the start form seeds no "
                   "CRUD entity for %r (start-form fields are scope=GLOBAL, or bind a different crud) — so the "
                   "serviceTask reads an EMPTY row and writes nulls from it, with no error anywhere (the throw "
                   "'No CRUD data available for CRUD: %s' belongs to a missing CONTEXT entry, not a missing "
                   "alias). Give "
                   "the start form >=1 field scope=CRUD + crudAlias=%r (any column) so collectContextDataFromForm seeds "
                   "it into the process contextData. (07-workflows-and-tasks.md)"
                   % (wf.get("name"), alias, alias, alias, alias))



def _check_process_context_binding(p, r):
    """A running process files no CRUD row of its own: every surface that reaches its subject through
    `context.<ctx>.<alias>.data` shows only what the case's context data DOCUMENT was seeded with — the start
    form's contextData, or the document a rule passed to `service.workflow.start` (27). Seeded by neither, the
    surface is empty. Invisible to every other gate — the project imports, the pages render, and the user gets
    blank forms and "No X selected" exceptions on the first live case.

    Why nothing files it: a workflow user-task action is not in the process table's settings, so
    the form finds it in neither `userStartProcessActions` nor `globalActions`,
    leaves the table-navigation data empty, and the form's CRUD mode returns immediately — no `crudId`, no
    CRUD entity data is loaded. A process-table GLOBAL action has the same shape with no row at all. What a process
    DOES carry is `contextData.attrs`, persisted as a process variable and merged on every hop.

    Five findings, all mechanical:
      (a) a workflow-reachable rule that needs an EXISTING record but offers no attrs fallback (a CREATE rule
          is exempt: the form's own CRUD-scoped controls fill the crud data map, and there is no id yet);
      (b) a form group opened by a workflow user-task / process-table action whose form carries CRUD-scoped
          READ-ONLY fields — they render blank (exempt for a create-only group, and for a "shape A" alias the
          start form seeds and a serviceTask `put`s back — see 07);
      (c) a process.table column or index with `scope: CRUD` over an alias nothing seeds — the column renders
          `contextDataMap[<ctx>].crudDataMap[<alias>]` of the case's own document, so an unseeded alias is
          blank in every row (and a seeded one is the start document's snapshot — see 27 §6);
      (d) a process attribute a workflow rule resolves by that NOTHING in the project ever writes;
      (e) a binding published ONLY by a process START action's before-complete rule — that rule runs against
          the FORM's context, so on some platform builds it never reaches the new instance.
    (07-workflows-and-tasks.md, 05-crud-tree-and-process-table.md)"""
    rep = p.rep
    rules_by_id = {rr.get("identifier"): rr for rr in rep.get("rules", []) or []}
    rules_by_name = {rr.get("name"): rr for rr in rep.get("rules", []) or []}
    fg_name = {g.get("identifier"): g.get("name") for g in rep.get("formGroups", []) or []}
    fg_by_id = {g.get("identifier"): g for g in rep.get("formGroups", []) or []}
    forms_by_id = {f.get("identifier"): f for f in rep.get("forms", []) or []}
    node_by_id = {n.get("identifier"): n for n, _pp, _pt in core.iter_nodes(p.root_content)}

    def props_of(el):
        return {pr.get("name"): pr.get("value") for pr in ((el.get("settings") or {}).get("properties") or [])}

    def form_field_settings(fgid):
        out = []
        fg = fg_by_id.get(fgid)
        for m in ((fg or {}).get("predicateFormMapping") or {}).get("mapping", []) or []:
            form = forms_by_id.get(m.get("formIdentifier"))
            cnode = node_by_id.get(form.get("contentIdentifier")) if form else None
            if not cnode:
                continue
            for n, _pp, _pt in core.iter_nodes(cnode):
                pn = n.get("pluginName") or ""
                if not (pn.startswith("dynaform.form.") and "field" in pn):
                    continue
                sv = ((n.get("properties") or {}).get("settings") or {}).get("stringValue")
                if not sv:
                    continue
                try:
                    out.append(json.loads(sv))
                except json.JSONDecodeError:
                    continue
        return out

    reach_rules, opened = set(), {}

    def note_action(where, a):
        for k in ("onBeforeUserTaskStartRuleIdentifier", "onBeforeUserTaskCompleteRuleIdentifier",
                  "predicateIdentifier"):
            if a.get(k):
                reach_rules.add(a[k])
        for rl in str(a.get("validationRuleIdentifiers") or "").split(","):
            if rl.strip():
                reach_rules.add(rl.strip())
        if a.get("formGroupIdentifier"):
            label = (a.get("localizedNames") or {}).get("en_US") or a.get("name") or a.get("id")
            opened.setdefault(a["formGroupIdentifier"], []).append(
                (where, label, a.get("onBeforeUserTaskCompleteRuleIdentifier")))

    for wf in (rep.get("workflows") or []):
        for el in (wf.get("elements") or []):
            t = (el.get("settings") or {}).get("type")
            pr = props_of(el)
            if t == "bpmn:ServiceTask" and pr.get("rule"):
                for x in str(pr["rule"]).split(","):
                    if x.strip():
                        reach_rules.add(x.strip())
            elif t == "bpmn:UserTask" and pr.get("userActions"):
                try:
                    payload = json.loads(pr["userActions"])
                except json.JSONDecodeError:
                    continue
                for a in (payload.get("actions") or []):
                    if isinstance(a, dict):
                        note_action("%s %r" % (wf.get("name"), pr.get("id")), a)
            elif t == "bpmn:SequenceFlow":
                m = re.search(r"'([0-9a-f-]{36})'", str(pr.get("conditionExpression") or ""))
                if m:
                    reach_rules.add(m.group(1))

    process_models = [(n, md) for n, pn, md in _iter_table_models(p) if pn == "process.table.pluin"]
    for n, md in process_models:
        for grp in ("userStartProcessActions", "globalActions"):
            for a in ((md.get(grp) or {}).get("actions") or []):
                if isinstance(a, dict):
                    note_action("process.table %r %s" % (n.get("name"), grp), a)

    if not reach_rules and not opened and not process_models:
        return

    changed = True
    while changed:
        changed = False
        for rid in list(reach_rules):
            rule = rules_by_id.get(rid)
            if not rule:
                continue
            for nm in re.findall(r'service\.rule\("([^"]+)"\)', _rule_script(rule)):
                tgt = rules_by_name.get(nm)
                if tgt and tgt.get("identifier") not in reach_rules:
                    reach_rules.add(tgt["identifier"])
                    changed = True

    reads_crud_re = re.compile(r"context\.\w+\.[\"']?\$?\{?(\w+)\}?[\"']?\.data")
    # Aliases a rule puts into a start document. A case started that way DOES carry them, and 27 §3 step 4 tells
    # the service tasks to read exactly those - so a shape-C project must not be warned about its own design.
    rule_seeded = _document_seeded_crud_aliases(p)
    for rid in sorted(reach_rules):
        rule = rules_by_id.get(rid)
        if rule is None:
            continue
        body = _rule_script(rule)
        read_aliases = set(reads_crud_re.findall(body))
        if not read_aliases or ".service.create(" in body or "context.data.getAttr" in body:
            continue
        unseeded = sorted(read_aliases - rule_seeded)
        if not unseeded:
            continue
        r.warn("rule %r is reachable from a workflow and resolves its record only through "
               "context.<ctx>.<alias>.data for %s — that reads the PROCESS's context data document, which a "
               "running process never files a row into, so it reads as an EMPTY map (never null) unless the start form or the starting "
               "rule seeded that alias into it — and no rule in this export does. Check the start form, or "
               "seed it in the document you pass to service.workflow.start "
               "(27-event-driven-process-start.md §4.2), or fall back to "
               "context.data.getAttr('<alias>Id') and publish that attribute wherever the record is created. "
               "(08-groovy-rules-and-context.md)"
               % (rule.get("name"), ", ".join(unseeded)))

    start_seeded = set()
    for _n, md in process_models:
        for a in ((md.get("userStartProcessActions") or {}).get("actions") or []):
            for d2 in form_field_settings((a or {}).get("formGroupIdentifier")):
                if d2.get("scope") == "CRUD" and d2.get("crudAlias"):
                    start_seeded.add(d2["crudAlias"])
    put_back = set()
    for rid in reach_rules:
        rule = rules_by_id.get(rid)
        if rule is None:
            continue
        put_back |= set(re.findall(r"context\.\w+\.(\w+)\.data\.put\(",
                                   _rule_script(rule)))
    # A start FORM's alias only stays usable if a serviceTask writes it back, hence the intersection. A
    # RULE-seeded alias needs no put-back: the starter wrote it into the document the process was created with,
    # and every reader (column, form control) resolves against that document.
    carried = (start_seeded & put_back) | rule_seeded
    # A process.table COLUMN needs no put-back at all: it renders the case's context data document, and both a
    # start form's contextData and a rule's start document land there whole.
    # (The form's document is serialized into the process variable at start.)
    seeded_for_columns = start_seeded | rule_seeded
    # An INDEX is a different mechanism and diverges here. Indexed values are extracted only when the start
    # carries indexSettings (and again after each action) - and the PROGRAMMATIC
    # start builder never sets them. So a rule-seeded alias buys a column, but buys an index nothing: it stays
    # unfilterable until a user task submits and backfills it.
    seeded_for_indexes = start_seeded

    for fgid, uses in sorted(opened.items(), key=lambda kv: fg_name.get(kv[0]) or kv[0]):
        if fg_by_id.get(fgid) is None:
            continue
        creates_only = any(crid for _w, _l, crid in uses) and all(
            ".service.create(" in _rule_script(rules_by_id.get(crid))
            for _w, _l, crid in uses)
        if creates_only:
            continue
        display = {d.get("fieldExpression") for d in form_field_settings(fgid)
                   if d.get("scope") == "CRUD" and d.get("alwaysProhibited") and d.get("fieldExpression")
                   and d.get("crudAlias") not in carried}
        if display:
            r.warn("form group %r is opened from a process (%s) and shows CRUD-scoped READ-ONLY fields %s — a "
                   "process form is bound to no row, so every one of them renders BLANK. Publish the values as "
                   "GLOBAL attributes from a serviceTask rule and make the card's fields scope=GLOBAL. "
                   "(07-workflows-and-tasks.md)"
                   % (fg_name.get(fgid) or fgid,
                      "; ".join("%s/%s" % (w, l) for w, l, _c in uses), sorted(display)))

    for n, md in process_models:
        for key in ("columnSettings", "indexSettings"):
            seeded_here = seeded_for_columns if key == "columnSettings" else seeded_for_indexes
            noun = "column" if key == "columnSettings" else "index"
            for c in (md.get(key) or []):
                if not (isinstance(c, dict) and c.get("scope") == "CRUD"
                        and c.get("crudAlias") not in seeded_here):
                    continue
                if not c.get("crudAlias"):
                    # the process table takes the CRUD branch only when contextIdentifier, crudAlias AND
                    # fieldExpression are all non-blank, so this one is blank whatever the case carries.
                    r.warn("process.table %r %s %r is scope=CRUD but names no crudAlias — the process "
                           "table fills a CRUD column only when contextIdentifier, "
                           "crudAlias and fieldExpression are all set, so this %s carries nothing whatever "
                           "the case's context data holds. Set the alias, or use scope=GLOBAL over an "
                           "attribute a serviceTask publishes. (05-crud-tree-and-process-table.md)"
                           % (n.get("name"), key, c.get("fieldExpression"), noun))
                    continue
                if key == "columnSettings":
                    r.warn("process.table %r %s %r is scope=CRUD over alias %r — the process table "
                           "renders it from contextDataMap[<ctx>].crudDataMap[<alias>] of "
                           "the case's OWN context data document, and nothing in this export puts that alias "
                           "there: no start form seeds it, no rule starts a case seeded with it, and a running "
                           "process files no row of its own. So the column is blank in every row. Seeding it "
                           "(27-event-driven-process-start.md §4.2) makes it render, but only as the start "
                           "document's SNAPSHOT — it stops agreeing with the row the moment anything updates "
                           "it. Prefer scope=GLOBAL over an attribute a serviceTask publishes. "
                           "(05-crud-tree-and-process-table.md)"
                           % (n.get("name"), key, c.get("fieldExpression"), c.get("crudAlias")))
                else:
                    r.warn("process.table %r %s %r is scope=CRUD over alias %r — indexed values are extracted "
                           "only from a start that CARRIES indexSettings, and again after each action. No "
                           "start form seeds this alias, and a rule-started case passes no index settings at "
                           "all, so nothing ever fills this index and every filter over it matches nothing. "
                           "Index a GLOBAL attribute a serviceTask publishes instead. "
                           "(05-crud-tree-and-process-table.md, 27-event-driven-process-start.md §6)"
                           % (n.get("name"), key, c.get("fieldExpression"), c.get("crudAlias")))

    start_rule_ids = set()
    for _n, md in process_models:
        for a in ((md.get("userStartProcessActions") or {}).get("actions") or []):
            if isinstance(a, dict) and a.get("onBeforeUserTaskCompleteRuleIdentifier"):
                start_rule_ids.add(a["onBeforeUserTaskCompleteRuleIdentifier"])

    published, published_durably = set(), set()
    for rule in (rep.get("rules") or []):
        body = _rule_script(rule)
        got = set(re.findall(r'setAttr\(\s*"(\w+)"', body))
        got |= set(re.findall(r"setAttr\(\s*'(\w+)'", body))
        got |= set(re.findall(r"context\.data\.(\w+)\s*=", body))
        published |= got
        if rule.get("identifier") not in start_rule_ids:
            published_durably |= got
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        pn = n.get("pluginName") or ""
        if not (pn.startswith("dynaform.form.") and "field" in pn):
            continue
        sv = ((n.get("properties") or {}).get("settings") or {}).get("stringValue")
        if not sv:
            continue
        try:
            d = json.loads(sv)
        except json.JSONDecodeError:
            continue
        if d.get("scope") == "GLOBAL" and d.get("fieldExpression") and not d.get("alwaysProhibited"):
            published.add(d["fieldExpression"])
            published_durably.add(d["fieldExpression"])

    for rid in sorted(reach_rules):
        rule = rules_by_id.get(rid)
        if rule is None:
            continue
        body = _rule_script(rule)
        needs = {alias + "Id" for alias in
                 re.findall(r"_rid\(\s*'(\w+)'", body) + re.findall(r'_rid\(\s*"(\w+)"', body)}
        needs |= set(re.findall(r'getAttr\(\s*"(\w+)"', body))
        needs |= set(re.findall(r"getAttr\(\s*'(\w+)'", body))
        for key in sorted(needs - published):
            r.warn("rule %r is reachable from a workflow and resolves by the process attribute %r, but NOTHING "
                   "in the project ever writes it — no rule setAttr(%r, ...) and no GLOBAL form control with "
                   "that fieldExpression. Inside a process this resolves to null and the step fails with its "
                   "\"no record selected\" message. Either name the start form's picker %r (a GLOBAL control "
                   "publishes under its own fieldExpression) or setAttr it from the serviceTask that creates "
                   "the record. (07-workflows-and-tasks.md)"
                   % (rule.get("name"), key, key, key))
        for key in sorted((needs & published) - published_durably):
            r.warn("rule %r resolves by the process attribute %r, and the ONLY thing that writes it is a "
                   "process START action's before-complete rule. That rule runs against the FORM's context, "
                   "not the process's, so on any platform build that does not carry the rule's context into "
                   "the new instance the attribute never arrives and the first step fails. Publish it from the "
                   "start form's own control instead: give the picker scope=GLOBAL and fieldExpression %r — a "
                   "control's value IS the process's initial contextData. (07-workflows-and-tasks.md)"
                   % (rule.get("name"), key, key))


def _check_form_linkage(p, r):
    """A `rep.forms[]` form must (a) have its content page carry a `formModeIdentifier` == the form's identifier
    somewhere in the subtree (else the form page renders no form → ERROR), and (b) its embedded `form.formGroup`
    copy must match the canonical `formGroups[]` entry (a desynced predicateFormMapping routes to the wrong
    form → WARN)."""
    idx = _id_index(p)
    fg_by_id = {g.get("identifier"): g for g in p.rep.get("formGroups", []) or []}
    for f in p.rep.get("forms", []) or []:
        cid = f.get("contentIdentifier")
        page = idx.get(cid) if cid else None
        if page is not None:
            found = False
            for sub, _pp, _pt in core.iter_nodes(page):
                fm = (sub.get("properties") or {}).get("formModeIdentifier")
                val = fm.get("stringValue") if isinstance(fm, dict) else None
                if val == f.get("identifier"):
                    found = True
                    break
            if not found:
                r.err("form %r content page carries no formModeIdentifier == the form identifier %s in its subtree — the page renders no form. (06)"
                      % (f.get("name"), f.get("identifier")))
        g = f.get("formGroup")
        if isinstance(g, dict) and g.get("identifier"):
            rec = fg_by_id.get(g["identifier"])
            if rec is None:
                r.warn("form %r embedded formGroup %s has no canonical formGroups[] entry. (06)" % (f.get("name"), g["identifier"]))
            else:
                gm = (g.get("predicateFormMapping") or {}).get("mapping")
                rm = (rec.get("predicateFormMapping") or {}).get("mapping")
                if gm != rm:
                    r.warn("form %r embedded formGroup.predicateFormMapping diverges from the canonical formGroups[] entry — the form may route to the wrong variant. (06)" % f.get("name"))


def _check_workflow_refs(p, r):
    """Workflow (bpmnContent + workflow record) reference integrity — a dangling / wrong-ruleType ref means
    that step silently does nothing (a serviceTask that never runs its rule, a gateway that can't route, a
    userTask that opens no form). All WARN (consistent with the existing dangling-ref tolerance):
      * the workflow's contextIdentifiers → contexts[];
      * serviceTask flowable:rule (CSV) → an EXECUTION_RULE/VALIDATION_RULE (a PREDICATE is wrong);
      * gateway sequenceFlow `predicateSequence.execute(execution,'<uuid>')` → a PREDICATE;
      * userTask userActions formGroupIdentifier → formGroups[]; predicate/onBeforeUserTaskStart|Complete/validation refs → rules[] of the right type."""
    types = _rule_types(p)
    rule_ids = set(types)
    rules_by_id = {rr.get("identifier"): rr for rr in p.rep.get("rules", []) or []}
    ctx_ids = {c.get("identifier") for c in p.rep.get("contexts", []) or []}
    fg_ids = {f.get("identifier") for f in p.rep.get("formGroups", []) or []}

    def chk_rule(wf, rid, kind, allowed):
        rid = (rid or "").strip()
        if not rid or rid == "null":
            return
        if rid not in rule_ids:
            r.warn("workflow %r %s %s resolves to no rule — the step silently does nothing. (07-workflows-and-tasks.md)" % (wf, kind, rid))
        elif allowed and types[rid] not in allowed:
            r.warn("workflow %r %s %s is ruleType %s, not %s. (07-workflows-and-tasks.md)" % (wf, kind, rid, types[rid], "/".join(sorted(allowed))))

    for wf in p.rep.get("workflows", []) or []:
        nm = wf.get("name")
        for ci in wf.get("contextIdentifiers", []) or []:
            if ci and ci not in ctx_ids:
                r.warn("workflow %r contextIdentifier %s resolves to no context. (07)" % (nm, ci))
        xml = wf.get("bpmnContent") or ""
        # ONLY a serviceTask's flowable:rule is an EXECUTION/VALIDATION rule. A conditional <sequenceFlow> may ALSO
        # carry flowable:rule (the editor round-trip attr) pointing at a PREDICATE — do not mis-flag those here;
        # they're validated via the predicateSequence.execute(...) check below.
        for m in re.finditer(r'<(?:\w+:)?serviceTask\b[^>]*?\bflowable:rule="([^"]+)"', xml):
            for rid in m.group(1).split(","):
                chk_rule(nm, rid, "serviceTask rule", {"EXECUTION_RULE", "VALIDATION_RULE"})
        # EMPTY predicate id — the editor emits `execute(execution, '')` when `rule` is cleared but the `sequence`
        # template is kept; the branch can't route on a real condition.
        if re.search(r"predicateSequence\.execute\(execution,\s*''\s*\)", xml):
            r.warn("workflow %r has a conditional sequenceFlow with an EMPTY predicate id "
                   "`predicateSequence.execute(execution, '')` — set a real PREDICATE rule id, or drop the "
                   "conditionExpression entirely for an unconditional default. (07-workflows-and-tasks.md)" % nm)
        for m in re.finditer(r"predicateSequence\.execute\(execution,\s*'([0-9a-fA-F-]+)'\)", xml):
            pid = m.group(1)
            chk_rule(nm, pid, "gateway sequenceFlow predicate", {"PREDICATE"})
            # An EXISTING-but-EMPTY-bodied PREDICATE FAILS OPEN to `true` at runtime → the branch is ALWAYS taken.
            rr = rules_by_id.get(pid)
            if rr and not ((rr.get("rule") or {}).get("ruleScriptStr") or "").strip():
                r.warn("workflow %r conditional predicate %s exists but its body is EMPTY — an empty PREDICATE "
                       "FAILS OPEN to `true` (the branch is ALWAYS taken). Give it a body ending in `return <bool>`. "
                       "(07-workflows-and-tasks.md)" % (nm, pid))
        # Editor round-trip: a conditional <sequenceFlow> using predicateSequence.execute MUST also carry
        # `flowable:sequence` + `flowable:rule` attributes, else the BPMN editor shows the condition EMPTY and a
        # re-save DROPS it (the flow goes unconditional → then hard-errors on the now-dangling predicate).
        for sf in re.finditer(r"<(?:\w+:)?sequenceFlow\b[^>]*>.*?</(?:\w+:)?sequenceFlow>", xml, re.DOTALL):
            block = sf.group(0)
            if "predicateSequence.execute" in block and "flowable:sequence" not in block:
                fid = re.search(r'\bid="([^"]+)"', block)
                r.warn("workflow %r conditional sequenceFlow %s has a <conditionExpression> predicate but NO "
                       "flowable:sequence/flowable:rule attributes — the BPMN editor shows sequence/rule EMPTY and a "
                       "re-save DROPS the condition (flow becomes unconditional). Emit "
                       "flowable:sequence=\"${predicateSequence.execute(execution, '%%s')}\" + "
                       "flowable:rule=\"<predicate-uuid>\" on the <sequenceFlow> (XML shape in 07). "
                       "(07-workflows-and-tasks.md)" % (nm, fid.group(1) if fid else "?"))
        blob = html.unescape(xml).replace('\\"', '"')
        for m in re.finditer(r'"formGroupIdentifier"\s*:\s*"([^"]+)"', blob):
            fgi = m.group(1)
            if fgi and fgi != "null" and fgi not in fg_ids:
                r.warn("workflow %r userTask formGroupIdentifier %s resolves to no formGroup — the task opens no form. (07)" % (nm, fgi))
        for key, allowed in (("predicateIdentifier", {"PREDICATE"}),
                             ("onBeforeUserTaskStartRuleIdentifier", {"EXECUTION_RULE"}),
                             ("onBeforeUserTaskCompleteRuleIdentifier", {"EXECUTION_RULE"})):
            for m in re.finditer(r'"%s"\s*:\s*"([^"]+)"' % key, blob):
                chk_rule(nm, m.group(1), "userTask " + key, allowed)
        for m in re.finditer(r'"validationRuleIdentifiers"\s*:\s*"([^"]+)"', blob):
            for rid in m.group(1).split(","):
                chk_rule(nm, rid, "userTask validationRule", {"VALIDATION_RULE"})


def _check_tabs(p, r):
    """Each `nct.tab.plugin` tabModel `items[].id` must equal a child `nct.parsis.plugin` identifier — the identity
    (not order) picks the tab's content, so an id with no matching parsis is a silently empty tab. WARN."""
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") != "nct.tab.plugin":
            continue
        tm = (n.get("properties") or {}).get("tabModel")
        sv = tm.get("stringValue") if isinstance(tm, dict) else None
        if not sv:
            continue
        try:
            items = json.loads(sv).get("items", []) or []
        except json.JSONDecodeError:
            continue
        parsis = {c.get("identifier") for c in (n.get("children") or []) if c.get("pluginName") == "nct.parsis.plugin"}
        for it in items:
            tid = it.get("id") if isinstance(it, dict) else None
            if tid and tid not in parsis:
                r.warn("tab plugin %r item id %s has no child nct.parsis.plugin with that identifier — the tab renders empty. (14 §tabs)" % (n.get("name"), tid))


def _check_chart_bindings(p, r):
    """A `chart.js.plugin` QUERY-strategy replacement (a scalar/array type, not Full/Json) with an empty
    `columnName` pulls nothing from the query — the series is silently empty. WARN."""
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") != "chart.js.plugin":
            continue
        jv = (n.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            cm = json.loads(sv)
        except json.JSONDecodeError:
            continue
        for rp in cm.get("replacements", []) or []:
            if isinstance(rp, dict) and rp.get("replaceStrategy") == "QUERY" and rp.get("type") not in ("Full", "Json") \
                    and not (rp.get("columnName") or "").strip():
                r.warn("chart %r QUERY replacement (type %s) has an empty columnName — nothing to pull from the query. (22)" % (n.get("name"), rp.get("type")))


def _check_chart_mount_matches_engine(p, r):
    """A chart's `html` is its MOUNT and its `js` picks the element out of that mount. When the two disagree
    the chart draws nothing and says so only in the browser console — every offline gate stays green, the
    page renders, and there is simply a blank card.

    Two mismatches, both mechanical:
      (a) the js looks up an element by class/id (`this.$find('div.kpi-plot')`, `getElementById('x')`) that
          the chart's own `html` does not contain → the lookup yields `undefined` and Plotly throws
          "DOM element provided is null or undefined" (`Plotly.getGraphDiv`), Chart.js "Canvas is null";
      (b) the ENGINE and the mount tag disagree — Plotly replaces a `<div>` and refuses a `<canvas>`, while
          Chart.js needs a `<canvas>`. A Plotly chart whose html only offers a canvas is the same blank card.
    (22-charts-params-and-filters.md)"""
    sel_re = re.compile(r"""\$find\(\s*['"]([^'"]+)['"]\s*\)|getElementById\(\s*['"]([^'"]+)['"]\s*\)""")

    def page_markup(node):
        """All markup on the node's PAGE. `$find` is `this.$component().find(sel)` but falls back to
        `$('body')` when the component element is missing (RichClass.js), and `getElementById` is always
        document-wide — so an element a SIBLING plugin renders on the same page is a legitimate target.
        Only warn when the token exists nowhere on the page."""
        stack, page = [(p.root_content, None)], None
        while stack:
            cur, pg = stack.pop()
            here = cur if cur.get("pluginName") == "siteMapPage" else pg
            if cur is node:
                page = here
                break
            for c in (cur.get("children") or []):
                stack.append((c, here))
        if page is None:
            return ""
        out = []
        for m, _a, _b in core.iter_nodes(page):
            props = m.get("properties") or {}
            v = props.get("html")
            if isinstance(v, dict) and v.get("stringValue"):
                out.append(v["stringValue"])          # nct.html.plugin markup
            jv = props.get("Javascript")              # a sibling chart's MOUNT (its model.html) — markup too
            if isinstance(jv, dict) and jv.get("stringValue"):
                try:
                    out.append((json.loads(jv["stringValue"]) or {}).get("html") or "")
                except json.JSONDecodeError:
                    pass                              # never the js: a selector naming itself proves nothing
        return "\n".join(out)

    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") != "chart.js.plugin":
            continue
        jv = (n.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            cm = json.loads(sv)
        except json.JSONDecodeError:
            continue
        html, js = (cm.get("html") or ""), (cm.get("js") or "")
        if not js:
            continue
        scope = None                            # page markup, resolved lazily (only when a token is missing)
        for m in sel_re.finditer(js):
            sel = (m.group(1) or m.group(2) or "").strip()
            if not sel or sel in ("div", "canvas", "svg", "*"):
                continue                       # a bare tag lookup, not a named hook
            toks = [sel] if m.group(2) else re.findall(r"[.#]([\w-]+)", sel)
            for tok in toks:
                if tok in html:
                    continue
                if scope is None:
                    scope = page_markup(n)
                if tok in scope:
                    continue                   # rendered by a sibling plugin on the same page — legitimate
                if m.group(2):
                    r.warn("chart %r js looks up getElementById(%r) but nothing on its page carries that id — "
                           "the element is undefined and the chart engine throws instead of drawing. (22)"
                           % (n.get("name"), tok))
                else:
                    r.warn("chart %r js selects %r but neither its own html nor anything else on its page "
                           "contains %r — the lookup yields undefined and the engine throws (\"DOM element "
                           "provided is null or undefined\"). Emit the mount and the selector from ONE helper "
                           "so they cannot drift. (22)" % (n.get("name"), sel, tok))
        if "Plotly." in js and "<canvas" in html and "<div" not in html.split("<canvas")[0][-200:]:
            r.warn("chart %r runs PLOTLY but its html mounts a <canvas> — Plotly replaces a <div> and will not "
                   "draw into a canvas. Mount a <div> for Plotly, a <canvas> for Chart.js. (22)" % n.get("name"))


def _check_chart_group_in_js(p, r):
    """EMPTY-CHART (WARN). A `chart.js.plugin` renders by `js.replace(replacement.group, fetchedValue)`;
    the replacements merge re-syncs only `name`/`type`, **never `group`**. So each
    replacement's `group` — its exact `$$(name, default, type)` placeholder text — MUST be a **byte-for-byte
    substring of `js`**. A single stray space or quote-style diff (stored group `$$('Labels', [], 'String[]')` vs
    js `$$('Labels',[],'String[]')`) makes the replace a no-op: the placeholder survives to the browser, where
    `window.$$(name,default)` returns the inline default and that series/axis renders EMPTY. Imports 0-err;
    only a live open shows the blank chart. (22-charts-params-and-filters.md / 14a-plugin-config-reference.md)"""
    for n, _pp, _pt in core.iter_nodes(p.root_content):
        if n.get("pluginName") != "chart.js.plugin":
            continue
        jv = (n.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            cm = json.loads(sv)
        except json.JSONDecodeError:
            continue
        js = cm.get("js") or ""
        for rp in cm.get("replacements", []) or []:
            if not isinstance(rp, dict):
                continue
            g = rp.get("group")
            if isinstance(g, str) and g.strip() and g not in js:
                r.warn("chart %r replacement %r group %r is NOT a byte-for-byte substring of the js — "
                       "js.replace(group,value) is a no-op, so this series/axis renders EMPTY (a stray space or "
                       "quote-style diff between the stored group and the js `$$(...)` placeholder is enough). Make "
                       "the group IDENTICAL to its `$$(...)` text in js. (22-charts-params-and-filters.md / 14a)"
                       % (n.get("name"), rp.get("name"), g))


def _js_unbalanced(src):
    """Balance {} () [] outside strings, template literals and comments. Returns a short reason or None.

    This is the fallback when `node` is not on PATH. It is deliberately conservative: it reports only a
    bracket that is closed too many times or left open at EOF, which is the failure that a hand-built
    config string produces and the only one worth an ERROR without a real parser."""
    stack = []
    i, n = 0, len(src)
    pairs = {")": "(", "]": "[", "}": "{"}
    while i < n:
        ch = src[i]
        if ch in "\"'`":
            quote = ch; i += 1
            while i < n:
                if src[i] == "\\": i += 2; continue
                if src[i] == quote: break
                i += 1
            i += 1; continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n": i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            i = src.find("*/", i + 2)
            if i < 0: return "unterminated /* */ comment"
            i += 2; continue
        if ch in "([{":
            stack.append((ch, i))
        elif ch in ")]}":
            if not stack:
                return "a stray %r at offset %d closes a bracket that was never opened" % (ch, i)
            op, _at = stack.pop()
            if op != pairs[ch]:
                return "%r at offset %d closes a %r" % (ch, i, op)
        i += 1
    if stack:
        op, at = stack[0]
        line = src.count("\n", 0, at) + 1
        return "%r opened on line %d is never closed (%d bracket(s) left open at end of script)" % (op, line, len(stack))
    return None


def _check_chart_js_parses(p, r):
    """RENDER-FATAL (ERROR). The panel runs a chart through `new Function(js)` AFTER textually replacing
    every `$$(...)` group with the fetched value (done by the chart renderer).
    So the thing that must be valid JavaScript is the SUBSTITUTED text, not the authored one — and nothing else
    in this file looks at it: `_check_chart_group_in_js` only proves the group is a substring.

    A config assembled by string concatenation (the normal way a generator builds `var cfg = {...};`) can be one
    brace short and still pass every other gate: the export imports 0-error, the page loads, and the only symptom
    is `SyntaxError: Unexpected token ';'` in the browser console with the chart area blank. LIVE-FOUND 2026-09-05
    on a dashboard where 48 of 87 charts were dead this way.

    Both states 22 §2.4 names are checked: values present, and the DEFAULT (query failed or returned no rows).
    Uses `node --check` when node is on PATH — a real parse; otherwise falls back to a bracket-balance scan."""
    import shutil, subprocess, tempfile, os
    node = shutil.which("node")
    for n_, _pp, _pt in core.iter_nodes(p.root_content):
        if n_.get("pluginName") != "chart.js.plugin":
            continue
        jv = (n_.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            cm = json.loads(sv)
        except json.JSONDecodeError:
            continue
        js = cm.get("js") or ""
        if not js.strip():
            continue
        reps = [x for x in (cm.get("replacements") or []) if isinstance(x, dict)]
        for mode in ("value", "default"):
            src = js
            for rp in reps:
                g = rp.get("group")
                if not (isinstance(g, str) and g.strip()):
                    continue
                if mode == "default":
                    v = rp.get("defaultValue")
                    v = v if isinstance(v, str) and v.strip() else "[]"
                else:
                    v = '["a","b"]' if str(rp.get("type") or "").startswith("String") else "[1,2]"
                src = src.replace(g, v)
            if node:
                fd, path = tempfile.mkstemp(suffix=".js")
                try:
                    with os.fdopen(fd, "w") as f:
                        f.write(src)
                    res = subprocess.run([node, "--check", path], capture_output=True, text=True)
                    if res.returncode:
                        msg = ""
                        for line in (res.stderr or "").splitlines():
                            if "Error" in line:
                                msg = line.strip(); break
                        r.err("chart %r does not parse once its $$() placeholders are substituted (%s state): %s "
                              "— the panel runs `new Function(js)` on the SUBSTITUTED text, so this chart renders "
                              "nothing and only the browser console says so. (22-charts-params-and-filters.md)"
                              % (n_.get("name"), mode, msg or "SyntaxError"))
                        break
                finally:
                    try: os.unlink(path)
                    except OSError: pass
            else:
                why = _js_unbalanced(src)
                if why:
                    r.err("chart %r is not balanced once its $$() placeholders are substituted (%s state): %s "
                          "— the panel runs `new Function(js)` on the SUBSTITUTED text, so this chart renders "
                          "nothing. Install node for a full parse. (22-charts-params-and-filters.md)"
                          % (n_.get("name"), mode, why))
                    break


_REPLACEMENT_TYPES = {
    "String", "Integer", "Long", "Float", "Double", "BigDecimal", "Boolean", "Full", "Json",
    "String[]", "Integer[]", "Long[]", "Float[]", "Double[]", "BigDecimal[]", "Boolean[]",
}


def _check_chart_replacement_type(p, r):
    """SILENT-WRONG-TYPE (WARN). `type` decides how the fetched value becomes a JS literal, and an
    **unknown string falls back to `String`** (22 §2.3) — so `Number[]`, `Int[]`, `Numeric[]` or a typo emit a
    QUOTED array, `["1","2"]`, where the chart expected numbers.

    A plain bar survives it (Chart.js coerces), which is why it hides for months; a **stacked axis, a
    dual-axis combo, a 100% stack, a line or a filled area does not** — it sums strings, or scales to a bound
    computed from text. The fix is one word in the replacement and touches no query.
    LIVE-FOUND 2026-09-05: a generator bound every numeric series as `Number[]`; nothing complained until the
    same nodes were reshaped into combos and stacks."""
    for n_, _pp, _pt in core.iter_nodes(p.root_content):
        if n_.get("pluginName") != "chart.js.plugin":
            continue
        jv = (n_.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            cm = json.loads(sv)
        except json.JSONDecodeError:
            continue
        for rp in cm.get("replacements", []) or []:
            if not isinstance(rp, dict):
                continue
            t = rp.get("type")
            if isinstance(t, str) and t.strip() and t.strip() not in _REPLACEMENT_TYPES:
                r.warn("chart %r replacement %r declares type %r, which is not a ReplacementType — unknown "
                       "strings fall back to String, so this series is emitted as a QUOTED array and any "
                       "shape that computes with it (stacked, dual-axis, 100%% stack, line, area) reads text. "
                       "Legal: String/Integer/Long/Float/Double/BigDecimal/Boolean (+[]), Full, Json. "
                       "(22-charts-params-and-filters.md §2.3)"
                       % (n_.get("name"), rp.get("name"), t))


def _check_plotly_explicit_height(p, r):
    """BLOWN-LAYOUT (WARN). A Plotly chart whose `layout` carries no `height` relies on the container being
    measurable at `newPlot()` time — and the chart body arrives in a SECOND ajax round-trip (22 Gotcha 17), so
    it often is not. Plotly then falls back to its own default height and the CARD inherits it: a KPI strip
    that should be ~150 px tall takes ~580 px and pushes the whole board below the fold, with the number
    stranded at the top of an empty box. Nothing else reports it — the export imports 0-error and every query
    runs. LIVE-FOUND 2026-09-05. Fix: pass a real `height:` in the layout (keep `autosize:true` for width).
    (22-charts-params-and-filters.md Recipe D)"""
    for n_, _pp, _pt in core.iter_nodes(p.root_content):
        if n_.get("pluginName") != "chart.js.plugin":
            continue
        jv = (n_.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            continue
        try:
            cm = json.loads(sv)
        except json.JSONDecodeError:
            continue
        js = cm.get("js") or ""
        if "Plotly.newPlot" not in js:
            continue
        if re.search(r"\bheight\s*:", js):
            continue
        r.warn("chart %r is a Plotly plot whose layout sets no `height` — at newPlot() the container may not "
               "be laid out yet (the body arrives in a second ajax round-trip), so Plotly falls back to its "
               "own default height and the card grows to several times the tile. Set layout.height explicitly "
               "and keep autosize for the width. (22-charts-params-and-filters.md Recipe D)" % n_.get("name"))


def _check_workflow_xml(p, r):
    """IMPORT-ABORTING (ERROR). A workflow whose `bpmnContent` is not well-formed XML — a malformed tag, an
    unescaped `&`/`<`, or an UNDECLARED namespace prefix (e.g. hand-authored `flowable:...` without the
    `xmlns:flowable`) — is rejected by Flowable when the workflow is saved at import: *"Workflow validation failed …
    invalid XML"*, which **ABORTS the ENTIRE rep-objects import**, so
    settings/rules/context/db all silently fail to import. The other workflow checks read `bpmnContent` as a
    STRING (regex); this one PARSES it. Also flags a `<process>`-less model and dangling `sequenceFlow` refs
    (Flowable rejects both). Empty `bpmnContent` is skipped (a draft workflow — imports as a no-op)."""
    import xml.etree.ElementTree as ET
    for wf in p.rep.get("workflows", []) or []:
        nm = wf.get("name")
        xml_str = (wf.get("bpmnContent") or "").strip()
        if not xml_str:
            continue  # empty/draft bpmnContent imports as a no-op (known-good in refs) — do not flag
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            r.err("workflow %r bpmnContent is NOT well-formed XML (%s) — Flowable rejects it at import "
                  "('invalid XML'), ABORTING the whole rep-objects import. Fix the BPMN XML "
                  "(declare xmlns:flowable, escape &/</>, close every tag). (07-workflows-and-tasks.md)" % (nm, e))
            continue
        ids, flows = set(), []
        has_process = False
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag == "process":
                has_process = True
            eid = el.get("id")
            if eid:
                ids.add(eid)
            if tag == "sequenceFlow":
                flows.append((el.get("sourceRef"), el.get("targetRef"), eid))
        if not has_process:
            r.err("workflow %r bpmnContent has no <process> element — Flowable rejects it (aborts import). (07)" % nm)
        for src, tgt, fid in flows:
            for ref, kind in ((src, "sourceRef"), (tgt, "targetRef")):
                if ref and ref not in ids:
                    r.err("workflow %r sequenceFlow %r %s=%r points to no element id — Flowable rejects the "
                          "model (aborts import). (07)" % (nm, fid, kind, ref))
        # SINGLE START EVENT per process. The platform's BPMN validation counts every
        # <startEvent> in a <process> and REJECTS >1 ("only one start event is allowed"),
        # which the workflow save surfaces as a service error that ABORTS the whole rep-objects
        # import (everything after the workflow in the import order — rules/contexts/forms/settings/mail+pdf
        # templates — is silently skipped). A message/timer start still counts. Model an alternate trigger
        # (mail intake, deadline timer) as a SCHEDULER, not a second startEvent. (07-workflows-and-tasks.md)
        for proc in root.iter():
            if proc.tag.split("}")[-1] != "process":
                continue
            starts = [c for c in list(proc) if c.tag.split("}")[-1] == "startEvent"]
            if len(starts) > 1:
                names = ", ".join((s.get("name") or s.get("id") or "?") for s in starts)
                r.err("workflow %r process %r has %d start events (%s) — the platform allows only ONE "
                      "(multiple start events); Flowable rejects it, ABORTING the whole "
                      "rep-objects import (rules/contexts/forms/templates after the workflow are skipped). Keep a "
                      "single <startEvent>; realise any alternate trigger as a scheduler. (07-workflows-and-tasks.md)"
                      % (nm, proc.get("id"), len(starts), names))
        # BPMN 2.0 XSD child ORDER on event elements: tCatchEvent/tThrowEvent require
        # (extensionElements?, incoming*, outgoing*, dataIn/Out*, eventDefinition*) — an <*EventDefinition>
        # placed BEFORE an <incoming>/<outgoing> is WELL-FORMED (ET accepts it) but SCHEMA-INVALID:
        # Flowable's XSD validateModel throws cvc-complex-type.2.4.a and rejects the workflow, ABORTING the
        # whole rep-objects import (everything after the workflow in the import order — rules/contexts/forms/
        # settings/mail+pdf templates — is silently skipped). This is exactly what a plain ET-parse misses.
        _EVENT_TAGS = {"startEvent", "endEvent", "intermediateCatchEvent",
                       "intermediateThrowEvent", "boundaryEvent"}
        for el in root.iter():
            if el.tag.split("}")[-1] not in _EVENT_TAGS:
                continue
            kids = [c.tag.split("}")[-1] for c in list(el)]
            io_idx = [i for i, k in enumerate(kids) if k in ("incoming", "outgoing")]
            ed_idx = [i for i, k in enumerate(kids) if k.lower().endswith("eventdefinition")]
            if io_idx and ed_idx and min(ed_idx) < max(io_idx):
                r.err("workflow %r <%s id=%r> has an eventDefinition BEFORE an incoming/outgoing child "
                      "(order %s) — well-formed XML but INVALID per the BPMN 2.0 XSD; Flowable rejects it "
                      "(cvc-complex-type.2.4.a), ABORTING the whole rep-objects import (rules/contexts/forms/"
                      "templates after the workflow are skipped). Emit <incoming>/<outgoing> BEFORE "
                      "<*EventDefinition>. (07-workflows-and-tasks.md)" % (nm, el.tag.split("}")[-1], el.get("id"), kids))
        # The same class of trap one level down, in the DIAGRAM. BPMN DI orders a <bpmndi:BPMNEdge> as
        # `di:waypoint+` then an OPTIONAL <bpmndi:BPMNLabel>, and a <bpmndi:BPMNShape> as a <dc:Bounds> then
        # an optional <bpmndi:BPMNLabel>. A label emitted BEFORE the geometry — the natural mistake when you
        # add branch labels to an existing diagram by hand — is well-formed XML that ET accepts and the XSD
        # REJECTS, so Flowable refuses the workflow and ABORTS the whole rep-objects import with it.
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag not in ("BPMNEdge", "BPMNShape"):
                continue
            kids = [c.tag.split("}")[-1] for c in list(el)]
            geom = "waypoint" if tag == "BPMNEdge" else "Bounds"
            g_idx = [i for i, k in enumerate(kids) if k == geom]
            l_idx = [i for i, k in enumerate(kids) if k == "BPMNLabel"]
            # The geometry is not optional either: the XSD wants `di:waypoint` at least TWICE on an edge and
            # exactly one `dc:Bounds` on a shape. Missing or short, the model is rejected the same way — and
            # with a label present but no geometry at all the ordering test below would never even look.
            need = 2 if tag == "BPMNEdge" else 1
            if len(g_idx) < need:
                r.err("workflow %r <bpmndi:%s bpmnElement=%r> has %d <%s> child(ren), the BPMN DI schema "
                      "requires %s — Flowable rejects the model (cvc-complex-type) and ABORTS the whole "
                      "rep-objects import. (07-workflows-and-tasks.md §4)"
                      % (nm, tag, el.get("bpmnElement"), len(g_idx), geom,
                         "at least 2" if need == 2 else "exactly 1"))
            if g_idx and l_idx and min(l_idx) < max(g_idx):
                r.err("workflow %r <bpmndi:%s bpmnElement=%r> puts <bpmndi:BPMNLabel> BEFORE its %s (order "
                      "%s) — well-formed XML but INVALID per the BPMN DI schema (%s is `%s` followed by an "
                      "OPTIONAL BPMNLabel); Flowable rejects the model and ABORTS the whole rep-objects "
                      "import. Move the label to be the LAST child. (07-workflows-and-tasks.md §4)"
                      % (nm, tag, el.get("bpmnElement"), geom, kids, tag,
                         "di:waypoint+" if tag == "BPMNEdge" else "dc:Bounds"))


# Admin/system "management console" pages that ship in the REPORT base. The builder ADDS business pages; it must
# NEVER delete these. HARD set = present in every REPORT base ever shipped (zero-FP ERROR). SOFT set = shipped
# by the current `empty` base but not by older ones (WARN — an old base legitimately lacks them).
# The MANAGEMENT CONSOLE — the pages the platform itself routes to. Removing one breaks a feature.
# ⛔ `advisory`, `insights`, `ontology`, `pdf` and `reports` were once in this list and are NOT console
# pages: they were demo screens wired to a sample dataset the platform does not ship, and a project
# created from a baseline that still carries them starts life with ~20 charts querying tables that do
# not exist. A baseline is entitled to drop them, so their absence is not an error — and never was.
_ADMIN_BASE_ALIASES_REQUIRED = {
    "401", "404", "audit-logs", "contexts", "database", "form", "landing",
    "processes", "profile", "queries", "query", "roles", "rules", "schedulers", "script",
    "sources", "users", "workflow", "workflows",
}
_ADMIN_BASE_ALIASES_SOFT = {"settings", "pdf-templates", "mail-templates", "bl"}


def _check_admin_base_pages(p, r):
    """The base project ships the management console (Settings, Rules, Form Groups + Landing, PDF/Mail Templates,
    Sources, Queries, Contexts, Workflows, Schedulers, Roles, Users, Database, Business Logic, …). Removing them
    breaks `/settings`, the form-group `?group=` landing, template management, etc. The builder must ADD pages,
    never delete the base skeleton. ERROR on a missing REQUIRED admin alias; WARN on a missing SOFT one."""
    if p.is_stand_in(core.F_BRANCHES):
        return  # the archive carries no pages: the import leaves the target's own, console included, as they are
    aliases = {n.get("alias") for n, _pp, _pt in core.iter_nodes(p.root_content)
               if n.get("pluginName") == "siteMapPage" and n.get("alias")}
    missing_req = sorted(_ADMIN_BASE_ALIASES_REQUIRED - aliases)
    if missing_req:
        r.err("admin/system BASE pages were REMOVED from the project: %s — the builder must ADD business pages, "
              "NEVER delete the management console (they back /settings, the form-group landing, template/rule "
              "admin). Rebuild on a fresh base and only append. (01-content-model-and-pages.md)"
              % ", ".join(missing_req))
    missing_soft = sorted(_ADMIN_BASE_ALIASES_SOFT - aliases)
    if missing_soft:
        r.warn("admin base pages absent (present in the current `empty` base): %s — if you deleted them, restore "
               "(don't remove the console); if your base is older, ignore. (01)" % ", ".join(missing_soft))


def _check_localized_maps_distinct(p, r):
    """The #1 localization bug (doc 20): a MULTILINGUAL project with an authored per-locale NAME map whose values
    are IDENTICAL across every locale — so that one language shows under all locales (e.g. `quicklink add --label`
    fanning an Armenian label into en_US/ru_RU too). WARN, conservatively: only when the map covers 2+ locales,
    every value is byte-identical, AND that value contains a NON-ASCII letter (Armenian/Cyrillic/… — a legit
    all-English label like "Home" or "Acme - Web Page" is left alone, keeping this zero-false-positive on the
    reference exports). Scans nav quick-link names + crud.table/tree column & action localizedNames."""
    locales = p.locales()
    if len(locales) < 2:
        return
    seen = set()

    def suspicious(m):
        if not isinstance(m, dict):
            return None
        vals = [m.get(loc) for loc in locales if m.get(loc) not in (None, "")]
        if len(vals) < 2:
            return None
        if len(set(vals)) != 1:
            return None
        v = vals[0]
        if not any(ord(c) > 127 and c.isalpha() for c in v):
            return None  # all-ASCII identical (e.g. a proper noun / "Home") — not the bug
        return v

    def flag(v, where):
        if (v, where) in seen:
            return
        seen.add((v, where))
        r.warn("localized map %s has the SAME value %r in every locale — the UI shows this language under all "
               "locales. Author distinct per-locale text (nav: --label-loc; enum: a localized choices rule). (20)"
               % (where, v))

    # nav quick links
    from . import quicklink_cmds
    nav_nodes = list(quicklink_cmds._iter_left_nav_nodes(p.root_content))
    sh = quicklink_cmds._shared_left_nav_node(p)
    if sh is not None:
        nav_nodes.append(sh)
    def walk_pm(items):
        for it in (items or []):
            if isinstance(it, dict):
                lm = (it.get("linkModel") or {}).get("localizedMap") or {}
                v = suspicious(lm.get("name"))
                if v:
                    flag(v, "nav link %r" % (it.get("name") or v))
                walk_pm(it.get("children"))
    for n in nav_nodes:
        try:
            mg = quicklink_cmds._read_model_groups(n)
            walk_pm(quicklink_cmds._pages_model(mg))
        except Exception:
            continue

    # crud.table/tree column + action localizedNames
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") not in ("crud.table.plugin", "crud.tree.plugin"):
            continue
        try:
            m = core.get_inner_json(node, "model")
        except core.ToolError:
            continue
        for c in (m.get("columnSettings") or []):
            v = suspicious(c.get("localizedNames"))
            if v:
                flag(v, "table column %r" % (c.get("fieldExpression") or v))
        for grp in ("createActions", "editActions"):
            for a in ((m.get(grp) or {}).get("actions") or []):
                v = suspicious(a.get("localizedNames"))
                if v:
                    flag(v, "table action %r" % v)


def _check_quicklinks(p, r):
    """A left-nav quick link whose internal `linkModel.identifier` resolves to no `siteMapPage` is a dead link. WARN."""
    from . import quicklink_cmds
    smp = {n.get("identifier") for n, _pp, _pt in core.iter_nodes(p.root_content) if n.get("pluginName") == "siteMapPage"}
    nav_nodes = list(quicklink_cmds._iter_left_nav_nodes(p.root_content))
    shared = quicklink_cmds._shared_left_nav_node(p)
    if shared is not None:
        nav_nodes.append(shared)
    seen = set()

    def collect(items):
        for it in items or []:
            info = quicklink_cmds._link_target(it)
            if info and info[0] and info[1] and info[1] not in smp and info[1] not in seen:
                seen.add(info[1])
                nm = it.get("name") if isinstance(it, dict) else "?"
                r.warn("left-nav quick link %r targets siteMapPage %s which does not exist — dead link. (17)" % (nm, info[1]))
            collect(it.get("children") if isinstance(it, dict) else None)

    for nav in nav_nodes:
        collect(quicklink_cmds._pages_model(quicklink_cmds._read_model_groups(nav)))


_PARAM_DECL_RE = re.compile(r"\{\s*name\s*:\s*['\"]([^'\"]+)['\"]")
_CROSSFILTER_RE = re.compile(r"(?:this\.)?crossFilter\(\s*['\"]([^'\"]+)['\"]")


def _page_own_charts(page):
    """chart.js.plugin nodes in a page's OWN layout (not descending into child siteMapPages)."""
    out = []

    def w(n):
        for c in n.get("children") or []:
            if c.get("pluginName") == "siteMapPage":
                continue
            if c.get("pluginName") == "chart.js.plugin":
                out.append(c)
            w(c)
    w(page)
    return out


def _check_chart_page_params(p, r):
    """Page-level chart wiring (the 'one string in five places' class): a `crossFilter('X', …)` click whose field
    X is declared as a SQL param by NO chart on the same page never filters (WARN); a `global.replacement.plugin`
    filter bar on a page whose charts declare no `{name:'…'}` param has nothing to build a control from (WARN)."""
    def pages(page):
        yield page
        for c in page.get("children") or []:
            if c.get("pluginName") == "siteMapPage":
                yield from pages(c)

    def chart_js(node):
        jv = (node.get("properties") or {}).get("Javascript")
        sv = jv.get("stringValue") if isinstance(jv, dict) else None
        if not sv:
            return None
        try:
            return json.loads(sv)
        except json.JSONDecodeError:
            return None

    for page in pages(p.root_content):
        charts = _page_own_charts(page)
        if not charts:
            continue
        declared = set()
        crossfilters = []  # (chartName, field)
        for c in charts:
            cm = chart_js(c)
            if not isinstance(cm, dict):
                continue
            for rp in cm.get("replacements", []) or []:
                q = ((rp.get("query") or {}).get("query") if isinstance(rp.get("query"), dict) else None) or ""
                for m in _PARAM_DECL_RE.finditer(q):
                    declared.add(m.group(1))
            for m in _CROSSFILTER_RE.finditer(cm.get("js") or ""):
                crossfilters.append((c.get("name"), m.group(1)))
        for cname, field in crossfilters:
            if field not in declared:
                r.warn("chart %r crossFilter('%s', …) but no chart on this page declares '%s' as a {name:'%s'} SQL param — the click never filters. (22 §5)"
                       % (cname, field, field, field))
        if _own_layout_hosts(page, "global.replacement.plugin") and not declared:
            r.warn("page %r hosts a filter bar (global.replacement.plugin) but no chart on it declares any {name:'…'} SQL param — the bar is inert. (22 §4)" % (page.get("name") or page.get("alias")))


def _check_action_forks(p, r):
    """A form-group fork predicate `return service.actionId == '<uuid>'` whose uuid is not the id of any real table
    or workflow action never matches — the mapping is dead. WARN."""
    act_ids = set()
    for n, pn, md in _iter_table_models(p):
        for g, a in _actions(md, "createActions", "editActions", "globalActions", "userStartProcessActions"):
            if a.get("id"):
                act_ids.add(a["id"])
    for wf in p.rep.get("workflows", []) or []:
        blob = html.unescape(wf.get("bpmnContent") or "").replace('\\"', '"')
        for m in re.finditer(r'"id"\s*:\s*"([0-9a-fA-F-]{36})"', blob):
            act_ids.add(m.group(1))
    fork_re = re.compile(r"service\.actionId\s*==\s*'([0-9a-fA-F-]{36})'")
    for rule in p.rep.get("rules", []) or []:
        if rule.get("ruleType") != "PREDICATE":
            continue
        body = (rule.get("rule") or {}).get("ruleScriptStr", "") if isinstance(rule.get("rule"), dict) else ""
        for m in fork_re.finditer(body):
            if m.group(1) not in act_ids:
                r.warn("predicate %r forks on service.actionId == '%s' but that uuid is no table/workflow action id — the fork never matches. (06)" % (rule.get("name"), m.group(1)))



def _check_groovy_method_params(cruds, r):
    """⛔⛔ A GROOVY crud method whose script reads `param` MUST declare parameters[].

    `param` inside the delegated rule is built ONLY from methods[].parameters:
    the method executor fills its result map by iterating the declared parameters
    (both the record-unpack branch and the positional fallback), so with `parameters: []`
    it stays empty, the platform never even sends the `__methodParams` marker
    (`if (parameters)` is false for an empty map) and GroovyExecutionRule binds an EMPTY
    HashMap. The whole form payload is dropped and the INSERT writes NULLs —
    "null value in column ... violates not-null constraint" on the very first save.

    LIVE-FOUND 2026-08-07. Offline gates cannot see it: the shape is valid, the SQL is
    valid, and `crud verify` substitutes parameters itself instead of going through the
    Groovy binding. The auto-find sentinel (`find` with ruleIdentifier == null) is
    executed in-process by Java and is deliberately exempt.
    """
    for crud in cruds:
        alias = crud.get("alias")
        for m in crud.get("methods", []) or []:
            if m.get("methodType") != "GROOVY":
                continue
            if not (m.get("ruleIdentifier") or "").strip():
                continue                      # auto-find sentinel — handled in Java
            script = m.get("script") or ""
            if not re.search(r"\bparam\b", script):
                continue                      # takes no arguments — legitimately param-less
            if not (m.get("parameters") or []):
                r.err("crud %r GROOVY method %r reads `param` but declares parameters: [] — "
                      "`param` arrives EMPTY at runtime and every value it forwards is written "
                      "as NULL. Declare one parameter per key the caller sends. "
                      "(11-business-logic-dynamic-crud.md, Document CRUD variant)"
                      % (alias, m.get("methodName")))


def _check_list_field_subforms(p, r):
    """⛔ A dynaform.form.list.field.plugin opens a form for an action only if the
    `dynaform.list.item.plugin` CHILD named by `getRenderFormId(actionId)`
    (= `formIdByActionId[actionId]` or, absent a mapping, the action id itself) exists.

    ERROR shapes:
      * `subforms` serialized as a JSON OBJECT (`{}`) — it is a list of subform records, so
        the settings parser fails the whole settings blob and the control falls back to defaults: no columns,
        no actions, no line can ever be added.
      * a `formIdByActionId` value that is not a child identifier (e.g. the literal "create") —
        `getRenderFormId` returns it verbatim and the action opens a blank auto-created form.

    A null/absent `subforms` is the LEGACY shape and still renders (the fallback keys the form
    on the action id) — warn, don't error; an action-less display-only list is fine with
    `subforms: []`. Shapes verified against doc/builder/erp/initial_erp.mrjun.
    """
    for node, _pa, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.form.list.field.plugin":
            continue
        try:
            st = core.get_inner_json(node, "settings") or {}
        except Exception:
            continue
        label = node.get("name") or node.get("identifier")
        subs = st.get("subforms")
        if subs is not None and not isinstance(subs, list):
            r.err("list field %r: `subforms` must be a JSON ARRAY of {id, localizedNames} — "
                  "with %r the parser fails the whole settings blob and the control falls back to "
                  "defaults: the sub-grid renders with NO columns and NO action buttons. "
                  "(02-form-controls-reference.md)" % (label, type(subs).__name__))
        kids = {c.get("identifier") for c in (node.get("children") or [])
                if c.get("pluginName") == "dynaform.list.item.plugin"}
        mapping = st.get("formIdByActionId") or {}
        for aid, fid in mapping.items():
            if fid not in kids:
                r.err("list field %r: formIdByActionId[%s] = %r is not the identifier of any "
                      "child dynaform.list.item.plugin %s — that action renders no form. "
                      "(02-form-controls-reference.md)" % (label, aid, fid, sorted(kids)))
        # every NON-DIRECT action must resolve to an existing list-item child (direct actions
        # open no form at all). A miss is the legacy/orphan shape: the action opens a blank,
        # auto-created list-item with no fields.
        actions = []
        for slot in ("createNewActions", "userActions"):
            actions += ((st.get(slot) or {}).get("actions") or [])
        for a in actions:
            aid = (a or {}).get("id")
            if not aid or str((a or {}).get("direct")).lower() in ("on", "true"):
                continue
            if aid in mapping:
                continue                       # already reported above when it misses
            if aid not in kids:
                r.warn("list field %r: action %s has no `formIdByActionId` entry and no child "
                       "dynaform.list.item.plugin with identifier %s — it opens a BLANK "
                       "auto-created form. Add the child (or map the action to an existing "
                       "sub-form) and declare it in `subforms`. "
                       "(02-form-controls-reference.md)" % (label, aid, aid))
        if subs is None and actions:
            r.warn("list field %r: `subforms` is null (legacy shape). It still renders — the "
                   "form is keyed on the action id — but the author panel shows no reusable "
                   "sub-forms and orphan cleanup only protects declared ones. Emit "
                   "`subforms: [{id, localizedNames}, …]`, one entry per non-direct action. "
                   "(02-form-controls-reference.md)" % label)


def _check_list_action_rules(p, r):
    """⛔/! A List control's actions carry the SAME action-record payload as a user
    task, and the same two traps apply — but they live in a content settings JSON, so the user-task
    check (`_check_user_action_payloads`) never sees them.

    1. **TYPES.** Every one of these fields is declared **String**. A JSON array or boolean makes the parser
       fail the payload, and the List then renders with no action buttons at all.
    2. **DANGLING RULE REFS.** The settings panel resolves a stored rule id by identifier — no type filter, but
       no fallback either: an id that does not exist in the target tenant shows the field **EMPTY**, and
       nothing runs at submit. LIVE-FOUND 2026-08-07: a rule wired in the file but never imported looks
       exactly like "the setting was never saved". Warn (not error), because an author may legitimately
       point at a rule that already lives in the tenant and is not part of this export.

    The picker itself lists only rules of the slot's own type,
    so a type mismatch still displays but can never be re-picked in the UI — warned separately.
    """
    STRING_FIELDS = ("validationRuleIdentifiers", "direct", "predicateIdentifier",
                     "formGroupIdentifier", "onBeforeUserTaskStartRuleIdentifier",
                     "onBeforeUserTaskCompleteRuleIdentifier", "completeUserTask", "icon", "taskId")
    EXPECTED_TYPE = {"predicateIdentifier": "PREDICATE",
                     "onBeforeUserTaskStartRuleIdentifier": "EXECUTION_RULE",
                     "onBeforeUserTaskCompleteRuleIdentifier": "EXECUTION_RULE"}
    types = _rule_types(p)

    def _check_ref(label, action_name, field, ident, want):
        if ident not in types:
            r.warn("list field %r action %r: %s = %s is not a rule in this export — the settings panel "
                   "will show that field EMPTY and nothing runs (ok only if the rule already exists in "
                   "the target tenant). (02-form-controls-reference.md)"
                   % (label, action_name, field, ident))
        elif want and types[ident] != want:
            r.warn("list field %r action %r: %s points at a %s rule, but that slot expects %s — the "
                   "picker lists only %s rules, so the value cannot be re-selected in the UI. "
                   "(02-form-controls-reference.md)"
                   % (label, action_name, field, types[ident], want, want))

    for node, _pa, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.form.list.field.plugin":
            continue
        try:
            st = core.get_inner_json(node, "settings") or {}
        except Exception:
            continue
        label = node.get("name") or node.get("identifier")
        for bucket in ("createNewActions", "userActions"):
            holder = st.get(bucket)
            if holder is not None and not isinstance(holder, dict):
                # The parser expects an action-list object here; anything else fails the parse of
                # the WHOLE list-control settings, so the control loses columns and actions at once.
                r.err("list field %r: `%s` is %s, but it must be an action-list object "
                      "{\"actions\": [...], \"errors\": []} — the settings JSON fails to parse and the "
                      "control renders with nothing configured. (02-form-controls-reference.md)"
                      % (label, bucket, type(holder).__name__))
            if not isinstance(holder, dict):
                continue
            for a in (holder.get("actions") or []):
                if not isinstance(a, dict):
                    continue
                name = (a.get("localizedNames") or {}).get("en_US") or a.get("id")
                for f in STRING_FIELDS:
                    v = a.get(f)
                    if v is None or isinstance(v, str):
                        continue
                    r.err("list field %r action %r: `%s` is %s, but an action record declares it String — "
                          "the parser fails the whole payload and the List renders with NO action buttons. "
                          "(02-form-controls-reference.md)" % (label, name, f, type(v).__name__))
                for f, want in EXPECTED_TYPE.items():
                    v = a.get(f)
                    if isinstance(v, str) and v.strip() and v.strip() != "null":
                        _check_ref(label, name, f, v.strip(), want)
                csv = a.get("validationRuleIdentifiers")
                if isinstance(csv, str):
                    for ident in [x.strip() for x in csv.split(",") if x.strip() and x.strip() != "null"]:
                        _check_ref(label, name, "validationRuleIdentifiers", ident, "VALIDATION_RULE")



def _check_localize_keys(p, r):
    """An entity `localize` jsonb is keyed by the DTO FIELD name, not the column name.

    The resolver swaps a row's value for `localize[<dtoField>][<locale>]`, and it looks
    that key up under the field name the CRUD exposes — `mainNode`, not `main_node`. Seed
    the jsonb straight from the database column names and the single-word fields still
    work (`name`, `node`, `detail` spell the same in both conventions) while every
    multi-word one silently keeps rendering the authoring language. Nothing logs; the
    column simply never translates, which reads as "the translation is missing" and sends
    you looking in the wrong place.
    """
    dump = p.db                       # Project.db is already the parsed dump
    cf = p.cruds_file                 # ...but dynamic-cruds.json is optional
    if not isinstance(dump, dict) or cf is None:
        return
    cruds = (cf.data or {}).get("cruds") or []
    # table -> crud, via the table each findAll reads
    tbl2crud = {}
    for c in cruds:
        for m in c.get("methods") or []:
            if m.get("methodName") != "findAll" or not m.get("script"):
                continue
            mm = re.search(r"\bFROM\s+([a-z_][a-z0-9_]*)", m["script"], re.I)
            if mm:
                tbl2crud.setdefault(mm.group(1), c)
            break
    for sch in dump.get("schemas") or []:
        for t in sch.get("tables") or []:
            cols = t.get("columns") or []
            crud = tbl2crud.get(t.get("name"))
            locf = (crud or {}).get("localizationField") or "localize"
            if locf not in cols or not crud:
                continue
            fields = {f.get("fieldName") for f in (crud.get("dtoFields") or [])}
            col2field = {f.get("displayName"): f.get("fieldName")
                         for f in (crud.get("dtoFields") or [])}
            keys = set()
            for row in t.get("rows") or []:
                v = row.get(locf)
                if not v:
                    continue
                try:
                    obj = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    continue
                if isinstance(obj, dict):
                    keys |= set(obj)
            for k in sorted(keys - fields):
                want = col2field.get(k)
                if want and want != k:
                    r.err("table %r: %s key %r is the COLUMN name — the resolver looks it "
                          "up by the DTO field name, so this translation is never applied. "
                          "Rename the key to %r." % (t.get("name"), locf, k, want))
                else:
                    r.warn("table %r: %s carries key %r, which is not a field of crud %r — "
                           "that translation is dead weight."
                           % (t.get("name"), locf, k, crud.get("alias")))



def _check_orphan_validation_rules(p, r):
    """A VALIDATION_RULE no form lists in `validators` can never fire.

    Unlike an unused EXECUTION rule — which a button, a workflow or another rule might still
    reach — a validation rule has exactly one entry point: `forms[].validators`. Written, tested,
    committed, and wired nowhere, it is a check the team believes is running. Nothing else in the
    project references it, so nothing else can warn.
    """
    try:
        ro = p.rep
    except Exception:
        return
    rules = ro.get("rules") or []
    forms = ro.get("forms") or []
    wired = set()
    for f in forms:
        for v in (f.get("validators") or []):
            wired.add(v if isinstance(v, str) else (v or {}).get("identifier"))
    # A rule-call endpoint's operation is the other entry point (doc 32 §3.15) — visible here only when the
    # archive keeps the endpoint list; a build never carries it, hence the wording below.
    wired |= core.api_exposure_rule_identifiers(ro)
    for rule in rules:
        if rule.get("ruleType") != "VALIDATION_RULE":
            continue
        ident = rule.get("identifier")
        if ident and ident not in wired:
            r.warn("validation rule %r is listed in no form's `validators` — it fires only from a form's "
                   "validators or as a rule-call endpoint's operation (doc 32 §3.15). If a rule call on the live "
                   "project runs it, keep it; otherwise add it to the form it was written for, or delete it."
                   % rule.get("name"))



def _check_method_rule_delegates(p, r):
    """A GROOVY crud method may delegate to a RULE — and that rule is the executable body.

    `method.ruleIdentifier` points at the rule the method actually runs; `method.script` is only a
    copy the editor shows. Two things go wrong and neither is visible anywhere else:

    1. **The rule is not in the export.** The method imports fine, its `ruleIdentifier` resolves to
       nothing, and the method fails at runtime. Found exactly this on a delivered project: six
       methods — including `customerOrder.create` / `update` / `delete`, the whole Orders write
       path — referenced rules that `rep-objects.rules[]` never carried. `validate` was green,
       `crud verify --db` was green, and a re-import would have silently removed the register's
       ability to save anything.
    2. **The two copies drift.** Pushing a new `script` over MCP does NOT update the delegate, so
       the archive can hold the new body while the runtime keeps executing the old one.

    Same family as the method-script / saved-query pair, and it needs the same discipline.
    """
    try:
        ro = p.rep
        cf = p.cruds_file
    except Exception:
        return
    if not isinstance(ro, dict) or cf is None:
        return
    rules = {rule.get("identifier"): rule for rule in (ro.get("rules") or [])}
    for crud in ((cf.data or {}).get("cruds") or []):
        for m in (crud.get("methods") or []):
            ident = m.get("ruleIdentifier")
            if not ident:
                continue
            rule = rules.get(ident)
            if rule is None:
                # ⛔ A GROOVY method that carries its own `script` and a `ruleIdentifier` is the
                # HIDDEN-DELEGATE shape this very toolkit writes — see `crud_cmds.cmd_crud_apply`:
                # an archive built here carries no hidden rule, "and the importer knows this: it creates
                # each one from the method's own `script` … there is deliberately no rule in
                # rep-objects.json."
                #
                # So the reference is not dangling: the platform creates the rule on import from the
                # identifier plus the script. Flagging it made `validate` contradict `crud_apply` and
                # cost 36 of 62 errors on a delivered project where creating those very records
                # demonstrably works. Without a `script` there is genuinely nothing to re-create
                # from — that stays an error.
                if (m.get("script") or "").strip():
                    continue
                r.err("crud %r method %r delegates to rule %s, which is NOT in rep-objects.rules[] "
                      "and the method carries NO `script` to re-create it from — the method imports "
                      "with a dangling reference and fails at runtime. Export the rule (it is "
                      "usually hidden, so list it with includeHidden), or give the method its "
                      "script so `ensureHiddenGroovyRule` can rebuild the delegate on import."
                      % (crud.get("alias"), m.get("methodName"), ident))
                continue
            body = ((rule.get("rule") or {}).get("ruleScriptStr") or "").strip()
            script = (m.get("script") or "").strip()
            if script and body and script != body:
                r.warn("crud %r method %r: its `script` and its delegate rule %r are DIFFERENT "
                       "bodies. The RULE is what executes; `script` is the copy the editor shows. "
                       "Keep them in step, or the archive documents code that never runs."
                       % (crud.get("alias"), m.get("methodName"), rule.get("name")))


def _check_dynamic_cruds(p, cruds, r):
    """Schema-aware checks that catch runtime-only failures a purely empty-table
    smoke test misses. See dyncheck.py for the rationale."""
    try:
        idx = dyncheck.build_schema_index(p.db)
    except Exception:
        return
    try:
        consumers = dyncheck.crud_consumers(p)
    except Exception:
        consumers = {}
    for crud in cruds:
        alias = crud.get("alias")
        sidx = idx.get(crud.get("sourceSchema")) or {}
        checks = sidx.get("checks", {})
        tables = sidx.get("tables", {})
        methods = crud.get("methods", []) or []
        # (1) a SQL method that writes a status/enum literal the CHECK forbids will
        #     throw on any real row (invisible against an empty table) -> ERROR.
        for m in methods:
            if m.get("methodType") != "SQL":
                continue
            sql = m.get("script", "") or ""
            for tbl in _sql_write_tables(sql):
                tcheck = checks.get(tbl) or {}
                if not tcheck:
                    continue
                for col, lit in dyncheck.literal_column_writes(sql):
                    allowed = tcheck.get(col)
                    if allowed is not None and lit not in allowed:
                        r.err("crud %r method %r writes %s=%r into %s, but its CHECK "
                              "constraint allows only {%s}"
                              % (alias, m.get("methodName"), col, lit, tbl,
                                 ", ".join(sorted(allowed))))
        # (2) ANY INSERT omitting a NOT NULL column with no default -> WARN.
        #
        # ⛔ This used to look at three method NAMES (`create`, `createHeader`,
        # `insertLine`) and therefore missed every INSERT written inside an engine —
        # which is where the interesting ones live. Measured on a delivered project:
        # the inventory-count posting engine inserted a stock movement without
        # `uom_id`, a NOT NULL column, so posting a count failed for every count
        # ever made; the register rendered, the action offered itself, and the only
        # trace was a PostgreSQL message inside a rule nobody reads. The caller is
        # Groovy and cannot see the schema, so nothing but this check looks.
        for m in methods:
            if m.get("methodType") != "SQL":
                continue
            for tbl, ins_cols in _parse_inserts(m.get("script", "")):
                for c in tables.get(tbl, []) or []:
                    if c["name"] == "id" or c["default"] or not c["notnull"]:
                        continue
                    if c["name"] not in ins_cols:
                        r.warn("crud %r %s: NOT NULL column %r of %s is not in the INSERT "
                               "(needs a value/COALESCE default) — the caller is Groovy and "
                               "does not see the schema, so this fails at runtime with a "
                               "PostgreSQL message from inside a rule"
                               % (alias, m.get("methodName"), c["name"], tbl))
        # (2b) a document CRUD (has insertLine/deleteLines) whose delete does not
        #      clear child lines first will FK-fail on any doc that has lines -> WARN.
        mnames = {m.get("methodName") for m in methods}
        if "deleteLines" in mnames and "insertLine" in mnames:
            dele = next((m for m in methods if m.get("methodName") == "delete"), None)
            if dele is not None:
                dsql = dele.get("script", "") or ""
                cascades = (dele.get("methodType") == "GROOVY" and "deleteLines" in dsql) \
                    or ("_line" in dsql or "_component" in dsql)  # a CTE/multi-table delete
                # A SOFT delete must NOT clear the lines: the header is only marked, so removing its
                # lines would leave a restorable document with nothing in it, and the FK it is being
                # warned about is never touched because no row is removed. Detect it by what the
                # delete chain actually writes — the header helper marking a column instead of
                # deleting the row.
                header_del = next((m for m in methods
                                   if m.get("methodName") in ("_deleteHeader", "deleteHeader")), None)
                soft = bool(_SOFT_DELETE_RE.search(dsql)) or (
                    header_del is not None and bool(_SOFT_DELETE_RE.search(header_del.get("script", "") or "")))
                if soft:
                    cascades = True
                if not cascades:
                    r.warn("crud %r: delete does not remove child lines first; it will "
                           "FK-fail on any document that has lines (mirror update: call "
                           "deleteLines then delete the header)" % alias)
        # (2c) a bare SQL alias carrying an upper-case letter is folded to lower
        #      case by Postgres, so the row arrives spelled differently from every
        #      camelCase consumer (table column, form control, Groovy rule) and the
        #      value silently renders blank. Quote the alias to keep the case.
        for m in methods:
            if m.get("methodType") != "SQL":
                continue
            lost = dyncheck.case_losing_aliases(m.get("script", "") or "")
            if lost:
                r.warn("crud %r method %r: SQL alias(es) %s are NOT quoted, so Postgres "
                       "folds them to lower case and the row arrives as %s — every "
                       "camelCase consumer then reads null. Quote them: AS \"%s\"."
                       % (alias, m.get("methodName"), ", ".join(sorted(set(lost))[:4]),
                          ", ".join(sorted({x.lower() for x in lost})[:4]),
                          sorted(set(lost))[0]))
        # (2d) a literal `?` is a JDBC BIND MARKER, so Postgres' jsonb existence
        #      operators (`?`, `?|`, `?&`) silently add parameter slots the
        #      platform never fills. The method then dies at runtime with
        #      "No value specified for parameter N" pointing at a slot that
        #      does not exist in the author's mental model of the statement.
        for m in methods:
            if m.get("methodType") != "SQL":
                continue
            qs = dyncheck.jdbc_question_marks(m.get("script", "") or "")
            if qs:
                r.err("crud %r method %r: %d literal '?' in the SQL — JDBC counts each "
                      "one as a bind marker, so the method fails with \"No value specified "
                      "for parameter N\". If these are jsonb existence operators, rewrite "
                      "them: `a ? 'k'` -> `a->'k' IS NOT NULL`, `a ?| ARRAY[..]` -> "
                      "`jsonb_exists_any(a, ARRAY[..])`, `a ?& ARRAY[..]` -> "
                      "`jsonb_exists_all(a, ARRAY[..])`."
                      % (alias, m.get("methodName"), len(qs)))
        # (3) every UI field expression must be surfaced by findAll -> WARN.
        find_all = next((m for m in methods if m.get("methodName") == "findAll"), None)
        cons = consumers.get(alias) or []
        if find_all and cons:
            fa_sql = find_all.get("script", "") or ""
            tbl_m = re.search(r"\bFROM\s+([a-z_][a-z0-9_]*)\s+t\b", fa_sql, re.I) \
                or re.search(r"\bFROM\s+([a-z_][a-z0-9_]*)", fa_sql, re.I)
            tcols = [c["name"] for c in tables.get(tbl_m.group(1), [])] if tbl_m else None
            roots, leaves, list_keys = dyncheck.surfaced_fields(fa_sql, tcols)
            # A LINE grid is filled from the record the FORM opened — the `get` method — not
            # from the register query. Embedding the whole lines aggregate in `findAll` as well
            # makes every register page carry the lines of every row it lists, which is what
            # turns a 15-row page into megabytes and, on a loaded server, into a timeout and an
            # empty grid. So look for the line keys in `get` too, and only warn when NEITHER
            # method surfaces them.
            get_m = next((m for m in methods if m.get("methodName") == "get"), None)
            if get_m:
                _, _, get_list_keys = dyncheck.surfaced_fields(get_m.get("script", "") or "", tcols)
                for k, v in (get_list_keys or {}).items():
                    list_keys.setdefault(k, set()).update(v)
            seen = set()
            for expr, kind in cons:
                if (expr, kind) in seen:
                    continue
                seen.add((expr, kind))
                if not _expr_resolves(expr, kind, roots, leaves, list_keys):
                    r.warn("crud %r: UI %s expression %r is not surfaced by findAll "
                           "(would render blank / raw id)" % (alias, kind, expr))


# -- theme-safe authored CSS --------------------------------------------------------------------------------

def _check_theme_safe_css(model, node, r):
    """Warn when an authored CSS block hardcodes a palette instead of going through theme tokens.

    A skin is a whole-stylesheet swap with no theme class to select on (doc 24a §1.3), so the ONLY correct way
    to colour authored markup is a two-level fallback -- `var(--current-line, var(--bs-light))` -- or a per-skin
    `css.byTheme` block. A block that paints with literals imports clean, validates clean, and is unusable on
    the four dark skins: white cards on a black page. That is exactly how a shipped project broke fourteen
    screens at once, so it is worth a gate.

    Deliberately a WARN, not an ERROR: a literal is legitimate inside a var() fallback, on a brand fill whose
    foreground is fixed, and in rgba() tints -- all of which are excluded below. What survives the exclusions is
    a bare literal on a colour property, which is nearly always the bug.
    """
    # Both levels must be shape-checked: a JSON-valid `"css": "oops"` (a string, not an object) used to raise
    # AttributeError here and abort the ENTIRE validate run — every other check for the whole project lost,
    # exit != 0, zero findings printed. A validator must never be the thing that fails.
    css_node = model.get("css")
    css = css_node.get("byTheme") if isinstance(css_node, dict) else None
    if not isinstance(css, dict):
        return
    # Custom properties that every per-skin block overrides are already handled: the "*" value is just the
    # light-skin case, which is what a literal is FOR. Flagging them would flag the documented fix.
    per_skin = [v for k, v in css.items()
                if k != "*" and isinstance(v, str) and v.strip()]
    overridden = None
    for block in per_skin:
        names = set(re.findall(r"(--[A-Za-z0-9_-]+)\s*:", block))
        overridden = names if overridden is None else (overridden & names)
    overridden = overridden or set()
    for theme, block in css.items():
        if not isinstance(block, str) or not block.strip():
            continue
        # ONLY the all-themes block. A per-skin block exists precisely so an author can name a colour that
        # only makes sense under that skin — flagging a literal there would be flagging the correct answer.
        if theme != "*":
            continue
        body = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        offenders = []
        for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", body):
            before = body[max(0, m.start() - 200):m.start()]
            # inside a var(...) fallback -> fine, that IS the idiom
            if "var(--" in before[-90:]:
                continue
            if m.group(0).lower() in ("#fff", "#ffffff", "#000", "#000000"):
                continue      # on-accent foreground / scrim: readable on every skin by construction
            # the literal is the light value of a custom property that every per-skin block re-declares
            decl = re.search(r"(--[A-Za-z0-9_-]+)\s*:[^;{}]*$", before)
            if decl and decl.group(1) in overridden:
                continue
            offenders.append(m.group(0))
        if offenders:
            uniq = sorted(set(offenders))
            r.warn("node %r studioModel.css.byTheme[%r]: %d colour literal(s) outside a var() fallback "
                   "(%s%s) -- this block is single-theme and will render light-on-dark on 4 of the 5 skins. "
                   "Use var(--current-line, <light>) / var(--bs-body-color) etc., or add per-skin blocks "
                   "(doc 24a §3, §8)."
                   % (node.get("name"), theme, len(offenders), ", ".join(uniq[:6]),
                      ", ..." if len(uniq) > 6 else ""))


def _check_localized_names(obj, node, locales, r):
    """Recurse inner config JSON; warn on any flat per-locale text map (see
    _FLAT_LOCALE_MAP_KEYS) that is partially filled (has some but not all tenant
    locales). The `set(keys) <= locales` guard skips nested maps (localizedMap
    field->locale->value) so we never false-positive on a field-keyed dict."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in _FLAT_LOCALE_MAP_KEYS and isinstance(val, dict) and val \
                    and set(val.keys()) <= locales:
                missing = locales - set(val.keys())
                if missing:
                    r.warn("node %r %s missing locales %s"
                           % (node.get("name"), key, sorted(missing)))
            _check_localized_names(val, node, locales, r)
    elif isinstance(obj, list):
        for item in obj:
            _check_localized_names(item, node, locales, r)


# The platform's task-type enum values. workflows[].elements[].settings.type MUST be one of these — anything else
# (notably bpmn:BoundaryEvent and bpmn:EndEvent) makes the import abort the ENTIRE
# rep-objects import. End events must be authored as "bpmn:Task"; boundary/timer events
# are NOT modellable at all.
_BPMN_TASK_TYPES = {
    "bpmn:StartEvent", "bpmn:Process", "bpmn:Task", "bpmn:UserTask", "bpmn:ServiceTask",
    "bpmn:SendTask", "bpmn:ReceiveTask", "bpmn:ManualTask", "bpmn:BusinessRuleTask",
    "bpmn:ScriptTask", "bpmn:CallActivity", "bpmn:SubProcess", "bpmn:TextAnnotation",
    "bpmn:Association", "bpmn:SequenceFlow", "bpmn:ExclusiveGateway", "bpmn:ParallelGateway",
    "bpmn:InclusiveGateway", "bpmn:ComplexGateway", "bpmn:EventBasedGateway", "bpmn:DataStoreReference",
}


def _has_form_field_descendant(node):
    for n, _p, _pt in core.iter_nodes(node):
        pn = n.get("pluginName", "") or ""
        if pn.startswith("dynaform.form.") and pn.endswith("field.plugin"):
            return True
        if pn in ("dynaform.form.list.field.plugin", "dynaform.filter.submit.button.plugin"):
            return True
    return False


def _check_form_parsis_anchor(p, r):
    """A dynaform.form.plugin renders its fields ONLY into a DIRECT child
    nct.parsis.plugin whose identifier is EXACTLY 'form.parsis'. A
    dynaform.filter.form.plugin needs 'filter.parsis'.
    If the field controls are placed under a randomly-uuid'd parsis instead, the
    plugin creates a FRESH EMPTY anchor and the form/filter renders with NO fields
    — a silent, data-shaped bug that `validate` otherwise misses. -> ERROR."""
    anchors = {"dynaform.form.plugin": "form.parsis",
               "dynaform.filter.form.plugin": "filter.parsis"}
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        anchor = anchors.get(node.get("pluginName"))
        if not anchor:
            continue
        if not _has_form_field_descendant(node):
            continue  # an empty form/filter with no fields — nothing to anchor
        kids = node.get("children", []) or []
        anchor_child = next((c for c in kids
                             if c.get("identifier") == anchor
                             and c.get("pluginName") == "nct.parsis.plugin"), None)
        if anchor_child is None:
            r.err("%s %r has field controls but NO direct child nct.parsis.plugin "
                  "with identifier %r — the form renders EMPTY (the plugin renders "
                  "fields only into that anchor; a uuid parsis is ignored). Set the "
                  "inner parsis identifier to exactly %r."
                  % (node.get("pluginName"), node.get("name") or node.get("identifier"),
                     anchor, anchor))
        elif not _has_form_field_descendant(anchor_child):
            r.err("%s %r has field controls placed OUTSIDE its %r anchor — move them "
                  "UNDER the %r parsis or they will not render."
                  % (node.get("pluginName"), node.get("name") or node.get("identifier"),
                     anchor, anchor))


def _check_workflow_reachability(rep, r):
    """Every non-end node must have an outgoing sequence flow AND a path to an end event. A user/service task
    whose only exit loops back with no terminal path traps the token forever (the case can never complete),
    and a node nothing points at is a step that will never run. Walks the parsed graph, so it is independent
    of how the XML happens to be formatted. -> WARN (structural, not import-breaking)."""
    for wf in rep.get("workflows", []) or []:
        parsed = _bpmn_parse(wf.get("bpmnContent") or "")
        if parsed is None:
            continue
        nodes, flows, _shapes, _edges = parsed
        nm = wf.get("name")
        succ = {}
        for f in flows.values():
            succ.setdefault(f.get("sourceRef"), []).append(f.get("targetRef"))
        ends = {n for n, el in nodes.items() if el.tag.split("}")[-1] == "endEvent"}
        starts = {n for n, el in nodes.items() if el.tag.split("}")[-1] == "startEvent"}
        if not ends:
            r.warn("workflow %r has no endEvent — no path can complete" % nm)
            continue

        def reaches_end(u):
            seen, stack = set(), [u]
            while stack:
                x = stack.pop()
                if x in ends:
                    return True
                if x in seen:
                    continue
                seen.add(x)
                stack += succ.get(x, [])
            return False

        seen, stack = set(), list(starts)
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack += succ.get(x, [])
        for n in sorted(nodes):
            if n in ends:
                continue
            if not succ.get(n):
                r.warn("workflow %r node %r has no outgoing sequenceFlow — the process traps here (can never "
                       "complete)" % (nm, n))
            elif not reaches_end(n):
                r.warn("workflow %r node %r cannot reach any endEvent — the process can never complete from "
                       "here (e.g. a loop with no terminal exit)" % (nm, n))
        if starts:
            for n in sorted(set(nodes) - seen):
                if nodes[n].tag.split("}")[-1] == "boundaryEvent":
                    continue                                   # attached, not reached by a sequence flow
                r.warn("workflow %r node %r is not reachable from the start event — that step never runs" % (nm, n))


def _check_workflow_diagram(rep, r):
    """The BPMN editor/monitor renders the stored `<bpmndi:*>` diagram AS-IS (no auto-layout on load). So a
    lazy diagram shows as overlapping boxes, lines cutting through task shapes, or a branch label parked on
    top of a node. Flag: (a) two node shapes whose bounds overlap, (b) an axis-aligned edge segment that
    passes through a NON-endpoint node box, (c) an edge label box that overlaps a node box, (d) a node or
    flow with no diagram element at all (it renders at the origin, on top of everything). -> WARN (visual,
    not import-breaking)."""
    def seg_hits(x1, y1, x2, y2, bx, by, bw, bh, pad=2):
        bx, by, bw, bh = bx + pad, by + pad, bw - 2 * pad, bh - 2 * pad
        if bw <= 0 or bh <= 0:
            return False
        if x1 == x2:
            return (bx <= x1 <= bx + bw) and not (max(y1, y2) <= by or min(y1, y2) >= by + bh)
        if y1 == y2:
            return (by <= y1 <= by + bh) and not (max(x1, x2) <= bx or min(x1, x2) >= bx + bw)
        return False  # diagonal segments not analysed

    def overlaps(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)

    for wf in rep.get("workflows", []) or []:
        xml = wf.get("bpmnContent") or ""
        if "BPMNPlane" not in xml:
            continue
        parsed = _bpmn_parse(xml)
        if parsed is None:
            continue
        nodes, flows, boxes, edges = parsed
        nm = wf.get("name")
        # (d) missing diagram elements
        for nid in sorted(set(nodes) - set(boxes)):
            r.warn("workflow %r node %r has no <bpmndi:BPMNShape> — the editor draws it at the origin, on top "
                   "of the diagram" % (nm, nid))
        for fid in sorted(set(flows) - set(edges)):
            r.warn("workflow %r sequenceFlow %r has no <bpmndi:BPMNEdge> — the editor draws it as a straight "
                   "line across whatever is in the way" % (nm, fid))
        # (a) overlapping node shapes
        items = sorted((k, v) for k, v in boxes.items() if k in nodes)
        seen_ov = set()
        for i, (a, ab) in enumerate(items):
            for b, bb in items[i + 1:]:
                if overlaps(ab, bb):
                    key = tuple(sorted((a, b)))
                    if key not in seen_ov:
                        seen_ov.add(key)
                        r.warn("workflow %r diagram: node shapes %r and %r overlap — lay them out with clear "
                               "spacing (the editor renders the stored diagram)" % (nm, a, b))
        # (b) edges through a non-endpoint node box
        crossed = set()
        for fid, pts in sorted(edges.items()):
            f = flows.get(fid)
            src, tgt = (f.get("sourceRef"), f.get("targetRef")) if f is not None else (None, None)
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                for el, box in items:
                    if el in (src, tgt) or (fid, el) in crossed:
                        continue
                    if seg_hits(x1, y1, x2, y2, *box):
                        crossed.add((fid, el))
                        r.warn("workflow %r diagram: edge %r passes THROUGH node %r — route it around "
                               "(adjacent edges orthogonal in the column gap; skip/loop edges through a clear "
                               "channel below all nodes, verticals in the inter-column gaps)" % (nm, fid, el))
        # (c) a branch label parked on a node
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        for el in root.iter():
            if el.tag.split("}")[-1] != "BPMNEdge":
                continue
            lb = _bpmn_edge_label(el)
            if lb is None:
                continue
            for nid, box in items:
                if overlaps(lb, box):
                    r.warn("workflow %r diagram: the label of edge %r sits on node %r — move its "
                           "<bpmndi:BPMNLabel> bounds clear of every shape" % (nm, el.get("bpmnElement"), nid))
                    break


def _check_user_action_payloads(rep, r):
    """⛔ Every action record inside a `flowable:userActions` payload must match the declared TYPES.

    An action record declares
    `validationRuleIdentifiers`, `direct`, `predicateIdentifier`, `formGroupIdentifier`,
    `onBeforeUserTask*RuleIdentifier`, `completeUserTask`, `icon` ALL as **String**. A JSON array
    (e.g. `"validationRuleIdentifiers": ["uuid"]`) or a boolean `direct` makes the parser fail the WHOLE
    payload, and the user task then renders **with no action buttons at all** — the task is unusable and
    nothing in the log points at the cause. LIVE-FOUND 2026-08-07.
    """
    STRING_FIELDS = ("validationRuleIdentifiers", "direct", "predicateIdentifier",
                     "formGroupIdentifier", "onBeforeUserTaskStartRuleIdentifier",
                     "onBeforeUserTaskCompleteRuleIdentifier", "completeUserTask", "icon", "taskId")
    for wf in (rep.get("workflows", []) or []):
        for el in (wf.get("elements", []) or []):
            for prop in ((el.get("settings") or {}).get("properties") or []):
                if prop.get("name") != "userActions":
                    continue
                try:
                    payload = json.loads(prop.get("value") or "{}")
                except Exception:
                    r.err("workflow %r element %r: userActions payload is not valid JSON — the user task "
                          "renders with no actions. (07-workflows-and-tasks.md)"
                          % (wf.get("name"), el.get("id")))
                    continue
                for a in (payload.get("actions") or []):
                    for f in STRING_FIELDS:
                        v = a.get(f)
                        if v is None or isinstance(v, str):
                            continue
                        r.err("workflow %r element %r action %r: `%s` is %s, but an action record declares it "
                              "as String — the parser fails the WHOLE userActions payload and the user task "
                              "renders WITHOUT ANY ACTIONS. Use a comma-separated string (%s). "
                              "(07-workflows-and-tasks.md)"
                              % (wf.get("name"), el.get("id"), a.get("name"), f,
                                 type(v).__name__,
                                 '"a,b"' if f.endswith("Identifiers") else '"on"/"off"'))


def _check_workflow_element_types(rep, r):
    """workflows[].elements[].settings.type must be a task-type enum value. An
    unknown type (bpmn:BoundaryEvent, bpmn:EndEvent, bpmn:IntermediateCatchEvent, …)
    makes the platform importer throw an invalid-format error while
    deserializing elements[].settings.type, which aborts the
    ENTIRE rep-objects import: the whole REPORT-path never runs, so sources aren't
    saved ("No source selected"), project-db.dump isn't restored (data/dates "gone"),
    and the context imports empty. Symptom is data-shaped and SCATTERED, not
    error-shaped — the real cause is one bad enum value here. -> ERROR."""
    for wf in rep.get("workflows", []) or []:
        for el in wf.get("elements", []) or []:
            if not isinstance(el, dict):
                continue
            t = (el.get("settings") or {}).get("type")
            if t is not None and t not in _BPMN_TASK_TYPES:
                r.err("workflow %r element %r: settings.type %r is NOT a valid task-type "
                      "enum value — it ABORTS the entire rep-objects import (invalid-format "
                      "error) so sources/DB/context all fail to import. "
                      "Author end events as 'bpmn:Task'; boundary/timer events are "
                      "unsupported. Allowed: %s"
                      % (wf.get("name"), el.get("id"), t, ", ".join(sorted(_BPMN_TASK_TYPES))))
        # bpmnContent boundary/timer XML deploys in Flowable but has no element-model
        # representation and desyncs the editor -> WARN (the elements[] check above is
        # the hard import-abort case).
        blob = wf.get("bpmnContent") or ""
        for tag in ("boundaryEvent", "timerEventDefinition", "intermediateCatchEvent"):
            if "<" + tag in blob:
                r.warn("workflow %r bpmnContent contains <%s> — timers/boundary events "
                       "are not backed by the platform's element model; keep them out of "
                       "elements[] and expect no runtime timer behavior" % (wf.get("name"), tag))


_WF_LOCALE_MAP_RE = re.compile(
    r'"(localizedNames|localizedButtonNames)"\s*:\s*(\{[^{}]*\})')


def _check_workflow_locales(rep, locales, r):
    """Scan workflow bpmnContent for embedded user-task action maps (stored as
    escaped/entity-encoded JSON inside the BPMN string) and warn on any
    localizedNames/localizedButtonNames that misses a tenant locale. Conservative:
    only warns on a map it can parse AND whose keys are all tenant locales."""
    for wf in rep.get("workflows", []) or []:
        blob = wf.get("bpmnContent") or ""
        if not blob:
            continue
        text = html.unescape(blob).replace('\\"', '"')
        for m in _WF_LOCALE_MAP_RE.finditer(text):
            key, raw = m.group(1), m.group(2)
            try:
                d = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(d, dict) and d and set(d.keys()) <= locales:
                missing = locales - set(d.keys())
                if missing:
                    r.warn("workflow %r action %s missing locales %s"
                           % (wf.get("name"), key, sorted(missing)))


def _check_global_resources(p, r):
    """The project's own files — the two halves have to agree.

    Everything here is a way for the feature to be silently half-present after an import, which is
    the worst shape: the registry looks right in the export and the page loads nothing, or worse,
    loads a grey placeholder image where a stylesheet used to be. File storage answers a path it does
    not have with a generated JPEG and a 200, so "the import did not complain" proves nothing.
    """
    try:
        branches = p.branches
    except Exception:
        return
    for branch in branches or []:
        if not isinstance(branch, dict):
            continue
        reg = branch.get("globalAssets")
        if reg in (None, ""):
            continue
        label = "branch %r" % branch.get("name")
        if not isinstance(reg, dict) or not isinstance(reg.get("assets"), list):
            r.err("%s globalAssets must be {\"version\":3,\"storageId\":…,\"folders\":[…],"
                  "\"assets\":[…]} — an object with ARRAYS (jsonb does not keep object key order, "
                  "and the load order is the whole point)" % label)
            continue

        storage = reg.get("storageId") or ""
        if not storage:
            r.err("%s globalAssets has no storageId. Every branch owns "
                  "webassets/<storageId>/ outright: without one, two branches name the same files "
                  "and an edit in the draft rewrites what the published site serves" % label)
        if storage and not re.fullmatch(r"[A-Za-z0-9._-]+", storage):
            r.err("%s globalAssets storageId %r is not safe in a path" % (label, storage))

        folders = reg.get("folders")
        if folders is not None and not isinstance(folders, list):
            r.err("%s globalAssets.folders must be an array" % label)
            folders = []
        folders = [f for f in (folders or []) if isinstance(f, dict)]
        folder_paths = set()
        for folder in folders:
            path = folder.get("path") or ""
            if not path:
                r.err("%s has a folder with no path — the root is not a folder" % label)
                continue
            if not folder.get("id"):
                r.err("%s folder %r has no id" % (label, path))
            if path in folder_paths:
                r.err("%s folder %r is declared twice" % (label, path))
            folder_paths.add(path)
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            if parent and parent not in folder_paths and not any(
                    f.get("path") == parent for f in folders):
                r.err("%s folder %r has no parent folder %r. Folders are entities, not path "
                      "prefixes: a missing one cannot be switched off, and the screen cannot draw "
                      "the file underneath it" % (label, path, parent))

        seen_paths, seen_ids, orders = {}, set(), []
        for asset in reg["assets"]:
            if not isinstance(asset, dict):
                r.err("%s has a globalAssets entry that is not an object" % label)
                continue
            name = asset.get("name") or asset.get("id") or "<unnamed>"
            kind = asset.get("kind")
            path = asset.get("path") or ""
            folder = asset.get("folder") or ""
            display = ("%s/%s" % (folder, name)) if folder else name

            if kind not in ("JS", "CSS", "HTML", "OTHER"):
                r.err("%s asset %r: kind must be JS, CSS, HTML or OTHER (got %r)"
                      % (label, display, kind))
            if not asset.get("id"):
                r.err("%s asset %r has no id — the id is the identity every copy path preserves; "
                      "a path changes on every rename and cannot stand in for it" % (label, display))
            elif asset["id"] in seen_ids:
                r.err("%s asset %r reuses an id already in the registry" % (label, display))
            else:
                seen_ids.add(asset["id"])

            if folder and folder not in folder_paths:
                r.err("%s asset %r sits in folder %r, which the registry does not declare. The "
                      "screen draws the tree from the FOLDERS, so this file is invisible in it"
                      % (label, display, folder))

            if not path:
                r.err("%s asset %r has no path" % (label, display))
                continue
            if path.startswith("t/"):
                r.err("%s asset %r: path must be RELATIVE to the tenant root (%r). The import "
                      "re-homes every stored file under a NEW tenant id while rewriting nothing "
                      "inside the registry, so an absolute path keeps reading — successfully — from "
                      "the DONOR project" % (label, display, path.split("/", 2)[-1]))
            if not path.startswith("webassets/"):
                r.err("%s asset %r: path must start with webassets/ — the serving endpoint refuses "
                      "anything else, deliberately (the project's database dump lives one directory "
                      "up)" % (label, display))
            elif storage and not path.startswith("webassets/%s/" % storage):
                r.err("%s asset %r: path %r is not inside this branch's own storage subtree "
                      "webassets/%s/. A branch that names another branch's files is the shape a "
                      "publish turns into a live site changing under its readers"
                      % (label, display, path, storage))
            if ".." in path.split("/"):
                r.err("%s asset %r: path contains '..'" % (label, display))
            expected_leaf = path.rsplit("/", 1)[-1]
            if name and expected_leaf != name:
                r.warn("%s asset %r is stored as %r — the tree shows the name, the browser fetches "
                       "the path, and a rename that moved only one of them is why they differ"
                       % (label, display, expected_leaf))

            disk = os.path.join(p.root, "tenant-files", *path.split("/"))
            if not os.path.isfile(disk):
                r.err("%s asset %r points at tenant-files/%s, which is not in this bundle — the "
                      "page would load a placeholder image, with a 200" % (label, display, path))
            else:
                size = os.path.getsize(disk)
                if asset.get("size") not in (None, size):
                    r.warn("%s asset %r records size %s but the file is %d bytes"
                           % (label, display, asset.get("size"), size))
                recorded = asset.get("sha256") or ""
                if recorded:
                    with open(disk, "rb") as fh:
                        actual = hashlib.sha256(fh.read()).hexdigest()
                    if actual != recorded:
                        r.err("%s asset %r: sha256 does not match tenant-files/%s. The served URL "
                              "carries that hash and the endpoint refuses bytes that do not match, "
                              "so this file would 404 on every page" % (label, display, path))
                else:
                    r.err("%s asset %r has no sha256 — the URL is built from it, and it is the only "
                          "thing that tells a real file from storage's placeholder"
                          % (label, display))

            if path in seen_paths and seen_paths[path] != display:
                r.warn("%s: %r and %r point at the same file; it would be loaded twice"
                       % (label, seen_paths[path], display))
            seen_paths[path] = display

            if asset.get("skins") and kind != "CSS":
                r.err("%s asset %r: skins applies to a stylesheet only" % (label, display))
            for skin in (asset.get("skins") or []):
                if skin not in _WEBASSET_SKINS:
                    r.warn("%s asset %r names skin %r, which this platform does not have — it "
                           "simply matches nothing, so the sheet loads nowhere"
                           % (label, display, skin))
            if kind not in ("JS", "CSS") and asset.get("enabled"):
                r.warn("%s asset %r is kind %s but is marked enabled — only a script or a "
                       "stylesheet is loaded on its own. Fonts, images and HTML fragments are "
                       "served for whatever references them" % (label, display, kind))
            if asset.get("isolate") and kind != "JS":
                r.err("%s asset %r: isolate applies to JavaScript only" % (label, display))
            if kind in ("JS", "CSS", "HTML") and _globalresource_kind_of(name) != kind:
                r.err("%s asset %r is registered as %s but its extension says %s. The extension "
                      "decides how the browser is told to interpret the bytes"
                      % (label, display, kind, _globalresource_kind_of(name)))
            if "-ver-" in name:
                r.err("%s asset %r contains '-ver-'. Wicket strips <base>-ver-<version> out of the "
                      "last URL segment of every mapped resource request, so this file would be "
                      "asked for under a different name and never found" % (label, display))
            orders.append(asset.get("order"))

        if any(o is None for o in orders):
            r.err("%s: every globalAssets entry needs an explicit integer order — it is what makes "
                  "the load order survive a jsonb round trip" % label)
        elif len(set(orders)) != len(orders):
            r.warn("%s: two globalAssets entries share an order; the load order is then arbitrary"
                   % label)


#: The skins a stylesheet may name. An empty list means every skin, which is the default.
_WEBASSET_SKINS = ("Standard", "Dracula", "Forest", "Dark", "Dark Blue")


def _check_image_per_theme(node, props, r):
    """An image's own version per theme (doc 14 §1.5): `perTheme` + `urlByTheme`, a JSON object skin name -> path.

    Every mistake here is SILENT on the platform: an unreadable map is treated as empty, a key that is not an exact
    skin name matches nothing, and a filled map without `perTheme: true` is kept but never shown. Each of those
    imports clean and renders the default `url` under every theme — the very thing the author was trying to avoid.
    """
    name = node.get("name")
    by_theme = props.get("urlByTheme")
    if not isinstance(by_theme, dict):
        return
    if isinstance(by_theme.get("localizedStringValue"), dict) and not by_theme.get("stringValue"):
        variants = by_theme["localizedStringValue"]   # what the MCP property setter stores for an object
    else:
        raw = by_theme.get("stringValue")
        if raw in (None, ""):
            return
        try:
            variants = json.loads(raw)
        except (TypeError, ValueError) as exc:
            r.err("image %r: urlByTheme is not valid JSON (%s) — the platform reads it as EMPTY, so every theme "
                  "shows the default url (doc 14 §1.5)" % (name, exc))
            return
    if not isinstance(variants, dict):
        r.err("image %r: urlByTheme must be a JSON object {skin name: image path}, got %s — read as EMPTY "
              "(doc 14 §1.5)" % (name, type(variants).__name__))
        return
    for skin, path in variants.items():
        if skin not in _WEBASSET_SKINS:
            r.warn("image %r: urlByTheme key %r is not a skin — keys are the exact names %s, so this entry "
                   "matches nothing (doc 14 §1.5)" % (name, skin, ", ".join(_WEBASSET_SKINS)))
        if not isinstance(path, str) or not path.strip():
            r.warn("image %r: urlByTheme[%r] is not an image path — that theme shows the default url "
                   "(doc 14 §1.5)" % (name, skin))
        elif path.startswith("t/"):
            r.warn("image %r: urlByTheme[%r] = %r carries a tenant prefix; store it tenant-stripped like url, or "
                   "it points at the EXPORTING project's files after import (doc 14 §1.5)" % (name, skin, path))
    per_theme = props.get("perTheme") if isinstance(props.get("perTheme"), dict) else {}
    on = per_theme.get("booleanValue") is True or str(per_theme.get("stringValue")).strip().lower() == "true"
    if variants and not on:
        r.warn("image %r: urlByTheme is filled but perTheme is not true — the per-theme images are kept but "
               "NEVER shown; set perTheme {\"propertyType\":\"BOOLEAN\",\"booleanValue\":true} (doc 14 §1.5)"
               % name)


def _globalresource_kind_of(name):
    leaf = (name or "").rsplit("/", 1)[-1].lower()
    if leaf.endswith(".js") or leaf.endswith(".mjs"):
        return "JS"
    if leaf.endswith(".css"):
        return "CSS"
    if leaf.endswith(".html") or leaf.endswith(".htm"):
        return "HTML"
    return "OTHER"


# ---------------------------------------------------------------------------
# Authorisation, localisation and picker checks.
#
# Added after a delivered multilingual MES passed every gate above while
# shipping: 87 write buttons with no role predicate, 45 persist rules with no
# role guard, 13 grids printing raw enum codes in all three languages, 200+
# monolingual user-facing strings, and pickers listing raw uuids. None of them
# is visible on a happy-path walkthrough, which is exactly why they survive.
# ---------------------------------------------------------------------------

_PERSIST_RE = re.compile(r"^(\w+) Persist (Create|Update|Delete)$")
_ROLE_GUARD_RE = re.compile(r"hasAnyRoleGroup\s*\(([^)]*)\)")
# an action that only shows a record is not a write and needs no role predicate
_READ_ONLY_ACTION_NAMES = {
    "view", "show", "open", "trace", "print", "export", "download", "preview",
    "\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440", "\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c", "\u043f\u0435\u0447\u0430\u0442\u044c", "\u044d\u043a\u0441\u043f\u043e\u0440\u0442",
}


def _table_model(node):
    raw = ((node.get("properties") or {}).get("model") or {}).get("stringValue")
    if not raw:
        return None
    try:
        m = json.loads(raw)
    except ValueError:
        return None
    return m if isinstance(m, dict) else None


def _persist_role_guards(rep):
    """alias -> the role groups its persist rules demand (absent when never guarded)."""
    out = {}
    for rule in rep.get("rules", []) or []:
        m = _PERSIST_RE.match(rule.get("name") or "")
        if not m:
            continue
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        roles = set()
        for g in _ROLE_GUARD_RE.finditer(src):
            roles.update(re.findall(r'"(\w+)"', g.group(1)))
        if roles:
            out.setdefault(m.group(1), set()).update(roles)
    return out


def _check_persist_rule_role_guard(p, r):
    """SECURITY (ERROR). A `<alias> Persist Create|Update|Delete` rule is the last thing between a
    form and the table. Without a `service.security.hasAnyRoleGroup(...)` check, ANY user who can
    reach the page can write the entity - a read-only role included, and a user who reached the form
    by URL rather than through a button you hid.

    Hiding the button is a courtesy, not an authorisation control. The guard belongs in the rule,
    where no client can skip it. (12-queries-sources-schedulers-and-rest.md)"""
    for rule in (p.rep.get("rules") or []):
        m = _PERSIST_RE.match(rule.get("name") or "")
        if not m:
            continue
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if not src or "hasAnyRoleGroup" in src:
            continue
        if not re.search(r"service\.crud\.\w+\.(create|update|delete)\s*\(", src):
            continue
        r.err("rule %r writes %r but checks NO role group - everyone who can open the form can "
              "create/update/delete this entity, and a read-only role that reaches the form by URL "
              "is not stopped either. Guard the write: `if (!service.security.hasAnyRoleGroup("
              "\"<Role>\", \"Administrator\")) { throw new RuntimeException(<trilingual message>) }`. "
              "(12-queries-sources-schedulers-and-rest.md)" % (rule.get("name"), m.group(1)))


def _check_write_action_predicate(p, r):
    """SECURITY + UX (ERROR). A `crud.table.plugin` create/edit action with no `predicateIdentifier`
    is rendered for EVERY user who can see the page. When the entity's persist rule does carry a role
    guard, that is the worst of both worlds: a read-only user sees Create and Edit, fills the form,
    presses Save and is told they are not authorised.

    A role matrix is normally written as "the button must be ABSENT, not present and inert", so give
    every write action a predicate over the SAME role set the persist rule demands. Read-only actions
    (View / Trace / Print) are exempt. (04-crud-table-plugin.md)"""
    guards = _persist_role_guards(p.rep)
    if not guards:
        return
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "crud.table.plugin":
            continue
        model = _table_model(node)
        if not model:
            continue
        alias = model.get("crudAlias")
        roles = guards.get(alias)
        if not roles:
            continue
        for kind in ("createActions", "editActions"):
            for act in ((model.get(kind) or {}).get("actions") or []):
                if act.get("predicateIdentifier"):
                    continue
                names = act.get("localizedNames") or {}
                label = str(names.get("en_US") or names.get("ru_RU") or act.get("id") or "?")
                if label.strip().lower() in _READ_ONLY_ACTION_NAMES:
                    continue
                r.err("crud table %r action %r has NO predicateIdentifier, while %r persist rules "
                      "demand %s - the button is shown to every role and only fails on Save. Point "
                      "the action at a PREDICATE rule returning `service.security.hasAnyRoleGroup(%s)`. "
                      "(04-crud-table-plugin.md)"
                      % (alias, label, alias, "+".join(sorted(roles)),
                         ", ".join('"%s"' % x for x in sorted(roles))))


_ACTION_GROUPS = ("createActions", "editActions", "deleteActions", "createNewActions", "globalActions",
                  "userStartProcessActions")
_ACTION_RULE_KEYS = ("onBeforeStartRuleIdentifier", "onBeforeCompleteRuleIdentifier",
                     "onBeforeUserTaskStartRuleIdentifier", "onBeforeUserTaskCompleteRuleIdentifier")
_ROLE_CHECK_RE = re.compile(r"has(?:Any)?RoleGroups?\s*\(([^)]*)\)")
_REFUSAL_RE = re.compile(r"\bthrow\b|\badd(?:Field)?Error\s*\(")


def _iter_all_actions(p):
    """yield (where, group, crud_alias, action) for every action a user can press: crud table / tree / process
    table action groups and every BPMN user task's actions (group "userActions", no crud alias)."""
    for n, pn, md in _iter_table_models(p):
        for grp, a in _actions(md, *_ACTION_GROUPS):
            yield "%s %r" % (pn, n.get("name")), grp, md.get("crudAlias"), a
    for wf in (p.rep.get("workflows") or []):
        for el in (wf.get("elements") or []):
            settings = el.get("settings") or {}
            if settings.get("type") != "bpmn:UserTask":
                continue
            props = {x.get("name"): x.get("value") for x in (settings.get("properties") or [])}
            try:
                payload = json.loads(props.get("userActions") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            for a in (payload.get("actions") or []) if isinstance(payload, dict) else []:
                if isinstance(a, dict):
                    yield "workflow %r task %r" % (wf.get("name"), props.get("id")), "userActions", None, a


def _check_entry_point_current(p, r):
    """RESUME (WARN). A fresh session resumes a project folder from `CLAUDE.md`, the one project skill and
    `.dokie/project.json` — the files `handoff emit` writes — and from nothing else, at whatever moment the last
    session ran out of context. Missing, the next session starts blind; not what `handoff emit` would write now,
    it starts from a map of a build that has moved on, which is worse, because it is believed. Only a PROJECT
    FOLDER is checked — the export's parent holding the library (`builder/`) or a recorded mode
    (`.dokie/project.json`); an export validated on its own has no entry point to keep. Read-only: the check
    regenerates in memory and compares. (system_prompt OP 7c, steps 1 and 7b)"""
    workdir = os.path.realpath(p.root)
    folder = os.path.dirname(workdir)
    state = os.path.join(folder, ".dokie", "project.json")
    if not (os.path.isdir(os.path.join(folder, "builder")) or os.path.isfile(state)):
        return
    cmd = "python3 ./builder/tools/mrjun.py handoff emit --project ./%s" % os.path.basename(workdir)
    if not os.path.isfile(state):
        r.warn("this project folder has no CLAUDE.md, project skill or .dokie/project.json yet - a session that "
               "runs out of context leaves the next one nothing to resume from. Run `%s --mode build` before "
               "authoring anything (step 1), and again after every unit of work (step 7b)" % cmd)
        return
    from . import handoff_cmds
    try:
        stale = handoff_cmds.stale_files(workdir)
    except core.ToolError:
        return
    if stale:
        r.warn("%s %s not what `handoff emit` would write now - the next session would resume from a map of a "
               "build that has moved on. Re-run `%s` (it keeps the recorded mode)"
               % (", ".join(stale), "is" if len(stale) == 1 else "are", cmd))


def _check_action_refused_by_role(p, r):
    """UX (WARN). An action whose own rule refuses by ROLE GROUP, while the action has no predicate, is offered to
    every role the rule then turns away: the user presses it — or fills its whole form — and only then learns it was
    never theirs. WHO may do something is known before the click, so it belongs in the action's PREDICATE, which
    hides it from everyone else; the rule keeps its check as the server-side guard (a hidden button is a courtesy,
    the rule is the authorisation). Covers every action a user can press: crud table and tree actions, process
    table start and global actions, BPMN user-task actions. A refusal that depends on the DATA rather than on the
    role is not this check's business — that one is a design decision per action (system_prompt OP 5i: hide,
    explain in the form, or refuse a direct action in the business's words). (25 "An action that cannot run")"""
    rules_by_id = {x.get("identifier"): x for x in (p.rep.get("rules") or []) if isinstance(x, dict)}
    # crud tables' create/edit actions over a role-guarded entity are already an ERROR (_check_write_action_predicate)
    guarded = _persist_role_guards(p.rep)

    def role_refusal(rule_id):
        """None when the rule does not refuse by role; else the role groups it names (maybe none, if computed)."""
        body = _strip_groovy_comments(_rule_script(rules_by_id.get((rule_id or "").strip()) or {}))
        if not (_REFUSAL_RE.search(body) and _ROLE_CHECK_RE.search(body)):
            return None
        roles = set()
        for g in _ROLE_CHECK_RE.findall(body):
            roles.update(re.findall(r"[\"']([^\"']+)[\"']", g))
        return roles

    seen = set()
    for where, grp, alias, a in _iter_all_actions(p):
        if a.get("predicateIdentifier"):
            continue
        if grp in ("createActions", "editActions") and where.startswith("crud.table.plugin") and alias in guarded:
            continue
        rule_ids = [a.get(k) for k in _ACTION_RULE_KEYS if a.get(k)]
        rule_ids += [x.strip() for x in str(a.get("validationRuleIdentifiers") or "").split(",") if x.strip()]
        found = [x for x in (role_refusal(rid) for rid in rule_ids) if x is not None]
        if not found:
            continue
        roles = sorted(set().union(*found))
        label = str((a.get("localizedNames") or {}).get("en_US") or a.get("name") or a.get("id") or "?")
        if (where, grp, label) in seen:
            continue
        seen.add((where, grp, label))
        r.warn("%s %s action %r refuses by role group in its own rule (%s) but has NO predicate - every other role "
               "is offered it and turned away only after pressing it. Give it a PREDICATE over the same role groups "
               "(`service.security.hasAnyRoleGroup(%s)`); keep the rule's check as the server-side guard. "
               "(25 \"An action that cannot run\")"
               % (where, grp, label, ", ".join(roles) or "a computed role-group check",
                  ", ".join('"%s"' % x for x in roles) or '"<Role>"'))


def _check_enum_column_shows_code(p, cruds, r):
    """LOCALISATION (WARN). The crud's SQL already joins `ref_label` for a field and publishes the
    translation under `localize['<field>Label']`, but the table column still points at the RAW field -
    so the grid prints WAITING_MATERIALS / RAW_MATERIAL in every language while the translated
    twin sits unused one key away. Point the column at `<field>Label`. (20-localization.md)"""
    labelled = {}
    for crud in (cruds or []):
        fields = set()
        for m in (crud.get("methods") or []):
            src = m.get("script") or ""
            if "localize" not in src:
                continue
            fields.update(re.findall(r"'(\w+)Label'\s*,\s*COALESCE\(\s*\w+\.localize", src))
        if fields:
            labelled[crud.get("alias")] = fields
    if not labelled:
        return
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "crud.table.plugin":
            continue
        model = _table_model(node)
        if not model:
            continue
        have = labelled.get(model.get("crudAlias"))
        if not have:
            continue
        for col in (model.get("columnSettings") or []):
            fe = col.get("fieldExpression")
            if fe in have:
                r.warn("crud table %r column %r shows the RAW enum code, but the crud already "
                       "publishes a translated %r under localize - the grid reads the same in every "
                       "locale. Point the column at %r. (20-localization.md)"
                       % (model.get("crudAlias"), fe, fe + "Label", fe + "Label"))


_ARMENIAN_RE = re.compile(r"[\u0530-\u058F]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{3,}")
# where a rule hands the user a sentence: a thrown message, a returned `message:`, an audit `note:`
_USER_STRING_HEADS = (
    re.compile(r"RuntimeException\(\s*"),
    re.compile(r"(?<![\w.])message\s*:\s*"),
    re.compile(r"(?<![\w.])note\s*:\s*"),
)
_GROOVY_STR_RE = re.compile(r"'((?:[^'\\\n]|\\.)*)'")
# `service.global.locale.message(` — a sentence the platform translates into the caller's language.
_LOCALE_MESSAGE_RE = re.compile(r"\blocale\s*\.\s*message\s*\(")


def _expression_after(src, start):
    """The whole expression that begins at `start` — a message is usually BUILT, not written:

        'Խմբաքանակ ' + lot.lotCode + ' / Партия ' + lot.lotCode + ' / Lot ' + lot.lotCode

    Looking at one literal of that would call a perfectly trilingual message monolingual, so the
    scan has to end where the expression does: a `,` or a closing bracket at depth 0."""
    depth = 0
    i = start
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "'":
            i += 1
            while i < n and src[i] != "'":
                i += 2 if src[i] == "\\" else 1
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        elif ch == "\n" and depth == 0:
            # A message is often laid out one language per line. The expression continues when the
            # line ENDS with an operator *or* when the next non-blank line STARTS with one:
            #     'hy text'
            #           + ' / ru text'
            #           + ' / en text'
            tail = src[:i].rstrip()
            nxt = src[i + 1:]
            nxt = nxt[:200].lstrip()
            if not (tail.endswith(("+", "?", ":", "(", "&&", "||"))
                    or nxt.startswith(("+", "?", ":", "&&", "||"))):
                break
        i += 1
    return src[start:i]


def _check_rule_strings_multilingual(p, r):
    """LOCALISATION (WARN). A sentence a Groovy rule hands a user either carries ALL the project's
    languages at once — conventionally `hy / ru / en` — or, in a rule that runs in the reader's locale (a
    component's ctx.callRule, a validation rule, a choices rule), is one literal passed to
    `service.global.locale.message('…')`, which the platform translates. Persist hooks, register row
    actions, workflow tasks and schedulers have no reader locale, so only the first way works there.

    This flags a user-facing expression whose text is written in only ONE script. It is the most
    common localisation hole in a multilingual project precisely because the screens look perfect:
    the monolingual text only appears when something is REFUSED, which no happy-path walkthrough
    reaches. The whole expression is read, not one literal, so a message assembled by `+` from
    per-language fragments is correctly seen as multilingual. (20-localization.md)

    A sentence passed to `service.global.locale.message('…')` is not judged: the platform translates it
    wherever a session locale reaches the rule — and asking for every language inside it would only hand the
    translator a sentence in three languages at once. Whether THIS rule gets a locale cannot be seen offline
    (doc 16 lists which rules do)."""
    locales = set(p.locales() or [])
    if len(locales) < 2:
        return
    seen = set()
    for rule in (p.rep.get("rules") or []):
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if not src:
            continue
        for head in _USER_STRING_HEADS:
            for m in head.finditer(src):
                expr = _expression_after(src, m.end())
                if _LOCALE_MESSAGE_RE.search(expr):
                    continue
                lits = [g for g in _GROOVY_STR_RE.findall(expr)]
                text = " ".join(lits).strip()
                if len(text) < 8:
                    continue
                if " / " in text:
                    continue
                scripts = (bool(_ARMENIAN_RE.search(text)) + bool(_CYRILLIC_RE.search(text))
                           + bool(_LATIN_WORD_RE.search(text)))
                if scripts != 1:
                    continue
                if not (_ARMENIAN_RE.search(text) or _CYRILLIC_RE.search(text)):
                    continue      # a bare Latin token is usually a code, not prose
                key = (rule.get("name"), text[:60])
                if key in seen:
                    continue
                seen.add(key)
                r.warn("rule %r hands the user a sentence written in ONE language only: %r. Write every "
                       "project language into it ('%s') — or, in a rule that runs in the reader's locale (a "
                       "component's ctx.callRule, a validation rule, a choices rule), pass it as one literal to "
                       "service.global.locale.message('…'), which the platform translates. (20-localization.md)"
                       % (rule.get("name"), text[:70], " / ".join(sorted(locales))))


def _groovy_string_end(src, i):
    """The index just past the Groovy string literal that opens at `i` — single, double or triple quoted."""
    q = src[i]
    if src.startswith(q * 3, i):
        end = src.find(q * 3, i + 3)
        return len(src) if end < 0 else end + 3
    j = i + 1
    while j < len(src) and src[j] != q and src[j] != "\n":
        j += 2 if src[j] == "\\" else 1
    return min(j + 1, len(src))


def _groovy_first_argument(src, start):
    """The first argument of the call whose `(` ends at `start`: the string literals at its top level, and whether
    a top-level `+` glues something to them."""
    depth, i, n = 0, start, len(src)
    literals, plus = [], False
    while i < n:
        c = src[i]
        if c in "'\"":
            j = _groovy_string_end(src, i)
            if depth == 0:
                literals.append(src[i:j])
            i = j
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and c == ",":
            break
        elif depth == 0 and c == "+":
            plus = True
        i += 1
    return literals, plus


_GSTRING_DOLLAR_RE = re.compile(r"(?<!\\)\$")


def _blank_groovy_strings(src):
    """A Groovy script with the TEXT of its '…', "…" and triple-quoted strings blanked out (quotes and positions kept):
    what is left is code."""
    out, i, n = list(src), 0, len(src)
    while i < n:
        if src[i] in "'\"":
            end = _groovy_string_end(src, i)
            q = 3 if src.startswith(src[i] * 3, i) else 1
            for k in range(i + q, max(i + q, end - q)):
                if out[k] != "\n":
                    out[k] = " "
            i = end
        else:
            i += 1
    return "".join(out)


def _check_rule_messages_are_literals(p, r):
    """LOCALISATION (WARN). `service.global.locale.message(text, values…)` translates its text only when the text is
    ONE literal of the rule (doc 16): a sentence built at run time is never sent to the translator — that would be a
    paid translation, a stored row and a copy of somebody's input for every value. So a text glued from values,
    `message('Record ' + n + ' is closed')` or `message("Record ${n} is closed")`, reaches every reader as written.
    The values belong in placeholders: `message('Record {0} is closed', n)`. A variable that holds a literal of the
    rule counts as that literal, so a bare name is never reported."""
    if len(set(p.locales() or [])) < 2:
        return
    for rule in (p.rep.get("rules") or []):
        src = _strip_groovy_comments(((rule.get("rule") or {}).get("ruleScriptStr") or ""))
        code = _blank_groovy_strings(src)        # a call quoted inside a string ("calling …message(…)") is none
        lines, line, counted = [], 1, 0
        for m in _LOCALE_MESSAGE_RE.finditer(code):
            literals, plus = _groovy_first_argument(src, m.end())
            gstring = any(lit.startswith('"') and _GSTRING_DOLLAR_RE.search(lit) for lit in literals)
            if not (gstring or (plus and literals)):
                continue
            line += src.count("\n", counted, m.start())
            counted = m.start()
            lines.append(line)
        if lines:
            r.warn("rule %r: %d service.global.locale.message(…) call(s) handed a text glued from values (line %s) "
                   "— only ONE literal of the rule is translated, so every reader gets these as written. Write the "
                   "sentence as one literal with placeholders and pass the values after it: "
                   "message('Record {0} is closed', row.number). (16-groovy-service-api.md)"
                   % (rule.get("name"), len(lines), ", ".join(str(n) for n in lines[:5]) + (", …" if len(lines) > 5 else "")))


# `t(…)` / `message(…)` in a studio script — the runtime's text function under every name it goes by: `ctx.t`,
# `ctx.service.global.locale.message`, and a bare `t` / `message` unless the component declares that name itself (an
# author's own key lookup over per-language maps; an alias `const t = ctx.t` is not its own) — and the one argument
# shape the platform translates: ONE string literal (a template literal without `${…}`), then `,` or `)`. Kept in
# step with the platform's own reading of a script (doc 24 §9).
_STUDIO_TEXT_CALL_RE = re.compile(r"(?<![\w$])(?:t|message)\s*\(")
# A FUNCTION the author names t / message — `function t(…)`, `t = k => …`, `const t = (k, ...a) => …`; a t holding
# anything else (an element, a timer, a loop's item) leaves the name to the runtime.
_OWN_FUNCTION_RE = re.compile(
    r"(?<![\w$.])function\s*\*?\s*(t|message)\s*\("
    r"|(?<![\w$.])(t|message)\s*=(?![=>])\s*(?:async\s+)?(?:function\b|\([^()]*\)\s*=>|[\w$]+\s*=>)")
# The runtime's function under the author's name for it: `const t = ctx.t`, `= ….locale.message`.
_TEXT_ALIAS_RE = re.compile(
    r"(?<![\w$.])(t|message)\s*=(?![=>])\s*(?:ctx\s*\.\s*t|[\w$.\s]*locale\s*\.\s*message)(?![\w$])")
_DESTRUCTURED_RE = re.compile(r"\{([^{}]*)\}\s*=(?![=>])\s*([\w$.]*)")
_BOUND_NAME_RE = re.compile(r"(?<![\w$])(t|message)(?![\w$])(?!\s*:)")
_RUNTIME_TEXT_FUNCTION_RE = re.compile(r"(?<![\w$])ctx\s*\.\s*t(?![\w$])|(?<![\w$])locale\s*\.\s*message(?![\w$])")
_STUDIO_TEXT_LITERAL_RE = re.compile(
    r"""\s*(?:'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\$]|\\.|\$(?!\{))*`)\s*[,)]""", re.S)
_EMPTY_CALL_RE = re.compile(r"\s*\)")
_BRACE_AHEAD_RE = re.compile(r"\s*\{")
_FUNCTION_BEHIND_RE = re.compile(r"(?:^|[^\w$])function\s*\*?\s*$")
_MAX_DECLARATION_CHARS = 10000
_MAX_DECLARATIONS = 200
_REGEX_AFTER_WORDS = frozenset(("return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
                                "case", "do", "else", "yield", "await"))


_MAX_TEMPLATE_DEPTH = 32
_MAX_CALL_CHARS = 2000
_MAX_REGEX_CHARS = 512


def _js_quote_end(js, i):
    """The index just past the '…' / "…" string that opens at `i` (a quote ends at a line break)."""
    q, j, n = js[i], i + 1, len(js)
    while j < n and js[j] != q and js[j] != "\n":
        j += 2 if js[j] == "\\" else 1
    return min(j + 1, n)


_STATEMENT_HEADS = frozenset(("if", "while", "for", "with"))


def _js_statement_head_before(js, close):
    """Whether the `)` at `close` ends the head of `if` / `while` / `for` / `with` (a regex may follow it)."""
    depth, i, stop = 0, close, max(0, close - _MAX_DECLARATION_CHARS)
    while i >= stop:
        c = js[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                j = i - 1
                while j >= 0 and js[j].isspace():
                    j -= 1
                end = j + 1
                while j >= 0 and (js[j].isalnum() or js[j] in "_$"):
                    j -= 1
                return js[j + 1:end] in _STATEMENT_HEADS
        i -= 1
    return False


def _js_regex_may_start(js, i):
    """Whether a `/` at `i` opens a regex: it stands where an expression starts, not after an operand."""
    j = i - 1
    while j >= 0 and js[j].isspace():
        j -= 1
    if j < 0:
        return True
    if js[j] in "+-" and j > 0 and js[j - 1] == js[j]:
        return False                      # a++ / 2: the end of an operand
    if js[j] == ")":
        return _js_statement_head_before(js, j)   # if (ok) /re/.test(s)
    if js[j] in "(,=:[!&|?{};+-*%<>~^":
        return True
    if not (js[j].isalnum() or js[j] in "_$"):
        return False
    start = j
    while start > 0 and (js[start - 1].isalnum() or js[start - 1] in "_$"):
        start -= 1
    return js[start:j + 1] in _REGEX_AFTER_WORDS


def _js_regex_end(js, i):
    """The index just past the regex opening at `i`, or -1 when it does not close on its line, soon enough."""
    in_class, j, stop = False, i + 1, min(len(js), i + _MAX_REGEX_CHARS)
    while j < stop:
        c = js[j]
        if c == "\n":
            return -1
        if c == "\\":
            j += 2
            continue
        if in_class:
            in_class = c != "]"
        elif c == "[":
            in_class = True
        elif c == "/":
            return j + 1
        j += 1
    return -1


def _js_blank(out, js, start, end):
    for k in range(max(0, start), min(end, len(js))):
        if js[k] != "\n":
            out[k] = " "


def _js_walk_template(js, i, out, literals, depth):
    """A template literal from its opening backtick: its text, and its `${…}` walked as the code it is."""
    j, n = i + 1, len(js)
    while j < n:
        c = js[j]
        if c == "`":
            return j + 1
        if c == "\\":
            if literals:
                _js_blank(out, js, j, j + 2)
            j += 2
        elif c == "$" and j + 1 < n and js[j + 1] == "{" and depth < _MAX_TEMPLATE_DEPTH:
            j = _js_walk_code(js, j + 2, out, literals, depth + 1, True)
        else:
            if literals and c != "\n":
                out[j] = " "
            j += 1
    return n


def _js_walk_code(js, i, out, literals, depth, in_template):
    """Code from `i` to the end — or, inside a template's `${…}`, to just past the brace that closes it."""
    braces, n = 0, len(js)
    while i < n:
        c = js[i]
        if c in "'\"":
            end = _js_quote_end(js, i)
            if literals:
                _js_blank(out, js, i + 1, end - 1)
            i = end
        elif c == "`":
            i = _js_walk_template(js, i, out, literals, depth)
        elif js.startswith("//", i):
            end = js.find("\n", i)
            end = n if end < 0 else end
            _js_blank(out, js, i, end)
            i = end
        elif js.startswith("/*", i):
            end = js.find("*/", i + 2)
            if end < 0:
                i += 2                    # never closes: the lexer is lost, leave the rest as it is
            else:
                _js_blank(out, js, i, end + 2)
                i = end + 2
        elif c == "/" and _js_regex_may_start(js, i):
            end = _js_regex_end(js, i)
            if end > 0 and literals:
                _js_blank(out, js, i + 1, end - 1)
            i = end if end > 0 else i + 1
        else:
            if in_template and c == "{":
                braces += 1
            elif in_template and c == "}":
                if braces == 0:
                    return i + 1
                braces -= 1
            i += 1
    return n


def _js_blanked(src, literals):
    """A studio script with its comments blanked out — and, with `literals`, the TEXT of its string, template and regex
    literals too (their quotes, and a template's `${…}` code, stay) — every other character in place. Read by a small
    JavaScript lexer, as the platform reads it: a `//` in a URL, a quote in a regex, a `/*` inside `image/*`, a template
    nested in another's `${…}` are each read for what they are; a `/*` that never closes is not blanked."""
    src = (src or "").replace("\r\n", "\n").replace("\r", "\n")
    out = list(src)
    _js_walk_code(src, 0, out, literals, 0, False)
    return "".join(out)


def _strip_js_comments(src):
    """A studio script with its comments blanked out, its literals kept (`_js_blanked`)."""
    return _js_blanked(src, False)


def _js_code_only(src):
    """A studio script with its comments and the text of its literals blanked out — only code is left."""
    return _js_blanked(src, True)


def _js_call_end(js, i):
    """The index just past the `)` closing the call whose argument list starts at `i` in a code-only text — read for a
    bounded length."""
    depth, n = 0, min(len(js), i + _MAX_CALL_CHARS)
    while i < n:
        c = js[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return i + 1
            depth -= 1
        i += 1
    return n


def _js_goes_on(js, line_break):
    """Whether a statement goes on past this line break: the code before it (blank and commented-out lines skipped)
    ends in `=` / `=>`, or a `{` opens what follows."""
    j = line_break - 1
    while j >= 0 and js[j].isspace():
        j -= 1
    open_end = j >= 0 and (js[j] == "=" or (js[j] == ">" and j > 0 and js[j - 1] == "="))
    return open_end or bool(_BRACE_AHEAD_RE.match(js, line_break))


def _js_statement_end(js, i):
    """Where the declaration whose head ends at `i` ends in a code-only text: the first `;`, closing bracket or line
    break outside brackets (a line ending in `=` / `=>`, or followed by one opening with `{`, goes on) — read for a
    bounded length."""
    depth, stop = 0, min(len(js), i + _MAX_DECLARATION_CHARS)
    while i < stop:
        c = js[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif depth == 0 and (c in ";," or (c == "\n" and not _js_goes_on(js, i))):
            return i                      # a comma: the next declarator of a list is not this one's body
        i += 1
    return min(i, len(js))


def _own_text_functions(codes):
    """The names among `t` / `message` a component makes its OWN function — an author's `const t = k => MSG[lang][k]`,
    a `function message(text, bad) {…}`, a `t` destructured out of its own i18n helper. Its bare calls of such a name
    are its own, whose argument is a key or anything else, never a text for the platform. The runtime's function under
    the author's name wins over any of that — an alias (`const t = ctx.t`, `const { t } = ctx`) or a wrapper that hands
    the call on (`(k, ...a) => ctx.t(k, ...a)`) — and a `t` that is no function (`const t = ev.target`, a loop's
    item, `let t;`) changes nothing. The scripts of a component run as one program, so the names are the component's.
    Kept in step with the platform's own reading."""
    own, runtimes = set(), set()
    for code in codes:
        js = _js_code_only(code)
        runtimes.update(m.group(1) for m in _TEXT_ALIAS_RE.finditer(js))
        for seen, m in enumerate(_OWN_FUNCTION_RE.finditer(js)):
            if seen >= _MAX_DECLARATIONS:
                break
            declared = m.group(1) is not None
            start = m.end() - 1 if declared else m.end()       # a declaration's match ends inside its "("
            body_end = _js_statement_end(js, start)
            reads_runtime = _RUNTIME_TEXT_FUNCTION_RE.search(js, start, body_end)
            (runtimes if reads_runtime else own).add(m.group(1) or m.group(2))
        for seen, m in enumerate(_DESTRUCTURED_RE.finditer(js)):
            if seen >= _MAX_DECLARATIONS:
                break
            source = m.group(2)
            for bound in _BOUND_NAME_RE.finditer(m.group(1)):
                name = bound.group(1)
                runtime = source == "ctx" if name == "t" else source.endswith("locale")
                (runtimes if runtime else own).add(name)
    return own - runtimes


def _is_runtime_text_call(js, at, own):
    """Whether the `t(` / `message(` call named at `at` is the runtime's: `ctx.t(…)`, `….locale.message(…)`, or the
    bare name unless the component makes it its own (`own`). A call on anything else (`i18n.t(…)`) is that thing's."""
    name = "message" if js.startswith("message", at) else "t"
    i = at - 1
    while i >= 0 and js[i].isspace():
        i -= 1
    if i < 0 or js[i] != ".":
        return name not in own
    i -= 1
    if i >= 0 and js[i] == "?":
        i -= 1                                        # ctx?.t(
    while i >= 0 and js[i].isspace():
        i -= 1
    end = i + 1
    while i >= 0 and (js[i].isalnum() or js[i] in "_$"):
        i -= 1
    return js[i + 1:end] == ("ctx" if name == "t" else "locale")


def _untranslatable_text_calls(code, own=None):
    """(line, call) of every `t(…)` / `message(…)` call in `code` whose text is not one literal. Not such a call:
    `t()`, the per-language map `t({en_US: '…', ru_RU: '…'})` (it carries its own translations), a function DEFINED
    under either name (`function t(key)`, a `message(text) {…}` method), and a call that is not the runtime's (the
    author's own `t`, `i18n.t(…)`). `own`: the names the component makes its own — by default, this script's."""
    text = _strip_js_comments(code)       # the literals still there, to tell one from a built text
    program = _js_code_only(code)         # only code: no call is found inside a string
    own = _own_text_functions([code]) if own is None else own
    found, line, counted = [], 1, 0
    for m in _STUDIO_TEXT_CALL_RE.finditer(program):
        if not _is_runtime_text_call(program, m.start(), own) or _STUDIO_TEXT_LITERAL_RE.match(text, m.end()) \
                or _EMPTY_CALL_RE.match(program, m.end()) or _BRACE_AHEAD_RE.match(program, m.end()):
            continue
        if _FUNCTION_BEHIND_RE.search(program[max(0, m.start() - 40):m.start()]) \
                or _BRACE_AHEAD_RE.match(program, _js_call_end(program, m.end())):
            continue
        line += program.count("\n", counted, m.start())
        counted = m.start()
        end = text.find("\n", m.start())
        call = text[m.start():len(text) if end < 0 else end].strip()
        found.append((line, call if len(call) <= 80 else call[:80] + "…"))
    return found


def _studio_model_runs(props):
    """Whether a node's studio model makes the page run the component runtime — any library, document, script or
    styling in it (an empty model renders the html as written)."""
    raw = (props.get("studioModel") or {}).get("stringValue")
    try:
        model = json.loads(raw) if raw else None
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(model, dict):
        return False
    if any(model.get(k) for k in ("libs", "docs", "scripts")):
        return True
    by_theme = (model.get("css") or {}).get("byTheme") if isinstance(model.get("css"), dict) else None
    return isinstance(by_theme, dict) and any(isinstance(v, str) and v.strip() for v in by_theme.values())


def _check_marks_need_the_runtime(node, pn, props, r):
    """LOCALISATION (WARN). A `data-i18n` mark is applied by the studio runtime (doc 24 §9). A plain html block — an
    `html.plugin`, or an `nct.html.plugin` without a studio model — renders its markup as written, so its marks are
    never translated and every reader sees the default language."""
    html = (props.get("html") or {}).get("stringValue") or ""
    if "data-i18n" not in html or (pn == "nct.html.plugin" and _studio_model_runs(props)):
        return
    r.warn("node %r (%s) marks text with data-i18n, but it is a plain html block: no runtime runs there, so the "
           "marks are never applied and every reader sees the default language. Make it a studio component (an "
           "nct.html.plugin with a studioModel — a script is enough). (24-html-component-studio.md §9)"
           % (node.get("name"), pn))


def _check_studio_texts_are_literals(model, node, r):
    """LOCALISATION (WARN). A studio component in a multilingual project writes its texts once, in the project's
    default language, and the platform translates them before the page runs — which it can do only for a text it
    finds in the source: the first argument of a `t(…)` / `message(…)` call that is ONE string literal, or a
    `data-i18n` mark (doc 24 §9). `ctx.t('Total: ' + n)`, `ctx.t(row.label)` and `ctx.t(`Total: ${n}`)` reach every
    reader as written — unless the very same words also appear as a literal or a mark somewhere in the component.
    A component that declares its own `t` / `message` (written before `ctx.t`, over its own per-language maps) means
    its own function by the bare name: those calls are not judged."""
    scripts = [s for s in model.get("scripts") or [] if isinstance(s, dict) and s.get("enabled") is not False]
    own = _own_text_functions(s.get("code") for s in scripts)
    for scr in scripts:
        calls = _untranslatable_text_calls(scr.get("code"), own)
        if not calls:
            continue
        r.warn("node %r script %r: %d t(…)/message(…) call(s) whose text is not one string literal — %s. The "
               "platform finds a text before the page runs only as ONE literal, so these stay as written in every "
               "language. Write ctx.t('Total: {0}', n); a text taken from data is translated only when the same "
               "words also appear as a t('…') literal or under data-i18n. (24-html-component-studio.md §9)"
               % (node.get("name"), scr.get("name"), len(calls),
                  "; ".join("line %d: %s" % c for c in calls[:3]) + ("; …" if len(calls) > 3 else "")))


def _check_choices_display_is_identifying(p, r):
    """UX (WARN). A choices rule that maps its options by `id` puts raw uuids in the picker. Build a
    readable label in the rule and point the control's `displayName` at that field instead.
    (02-form-controls-reference.md 4a)"""
    for rule in (p.rep.get("rules") or []):
        if not (rule.get("name") or "").startswith("Choices "):
            continue
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        m = re.search(r'toSelectOptions\w*\(\s*\w+\s*,\s*"(\w+)"\s*,\s*"([\w.]+)"\s*\)', src)
        if not m or m.group(2) != "id":
            continue
        r.warn("choices rule %r maps its options by 'id' - the picker shows raw uuids. Build a "
               "readable label in the rule and pass that field (and set the control's displayName to "
               "match). (02-form-controls-reference.md 4a)" % rule.get("name"))


# Only a NUMBER is flagged. A catalogue code (`*Code`) is a value a human
# chooses and should stay typed; `orderNo` / `docNo` / `ncrNo` / `movementNo` are sequential and
# must not be. A lot code is usually generated too, but its shape varies too much to assume.
_BUSINESS_KEY_RE = re.compile(r"^(?:[a-z][A-Za-z]*)?(?:No|Number)$")


def _check_business_key_is_assigned(p, r):
    """FUNCTIONAL (WARN). A document's business key — `orderNo`, `docNo`, `lotCode`, `ncrNo` — is
    mandatory on the form and nothing generates it, so every user types it by hand. That is not a
    cosmetic gap:

      * two people create the same number and the second save fails (or, with no unique index,
        succeeds and the register now has a duplicate key);
      * the format drifts the moment a second person types one;
      * every requirement of the form "the system assigns a unique number" is unmet while the screens
        look complete.

    Assign it where it cannot be skipped: a `nextNo`-style SQL method that reads the current maximum
    for the period, called from the entity's `Persist Create` rule when the field arrives blank — and
    then take `alwaysMandatory` off the control, since the system, not the user, fills it.
    (11-business-logic-dynamic-crud.md)"""
    rep = p.rep
    # which field each form control binds, per crud alias
    mandatory = {}
    for node, _pp, _pt in core.iter_nodes(p.root_content):
        pn = node.get("pluginName") or ""
        if not pn.startswith("dynaform.form."):
            continue
        raw = ((node.get("properties") or {}).get("settings") or {}).get("stringValue")
        if not raw or not raw.lstrip().startswith("{"):
            continue
        try:
            m = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(m, dict) or not m.get("alwaysMandatory"):
            continue
        alias, fe = m.get("crudAlias"), m.get("fieldExpression")
        if not alias or not fe or "." in fe:
            continue
        if not _BUSINESS_KEY_RE.match(fe):
            continue
        mandatory.setdefault(alias, set()).add(fe)
    if not mandatory:
        return
    creates = {}
    for rule in (rep.get("rules") or []):
        m = _PERSIST_RE.match(rule.get("name") or "")
        if m and m.group(2) == "Create":
            creates[m.group(1)] = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
    for alias, fields in sorted(mandatory.items()):
        src = creates.get(alias)
        if src is None:
            continue
        for fe in sorted(fields):
            snake = re.sub(r"([A-Z])", lambda mm: "_" + mm.group(1).lower(), fe)
            if re.search(r"\b(?:payload|row|doc|hdr)\s*\[\s*'(?:%s|%s)'\s*\]\s*=" % (re.escape(fe), re.escape(snake)), src):
                continue
            if "nextNo" in src or "nextval" in src or "lpad(" in src.lower():
                continue
            r.warn("crud %r: %r is MANDATORY on the form and its Persist Create rule never assigns "
                   "it — every document number is typed by hand, so two users can produce the same "
                   "one and the format drifts. Generate it (a `nextNo` SQL method called from the "
                   "persist rule when the field is blank) and drop alwaysMandatory from the control. "
                   "Check the entity's LOT/BATCH code the same way — it is generated too, but its "
                   "shape varies too much for this check to assume. (11-business-logic-dynamic-crud.md)"
                   % (alias, fe))


# the generator scaffolds these; nothing has to call them by name
_SCAFFOLD_METHODS = {
    "find", "findAll", "count", "get", "create", "update", "delete",
    "createHeader", "updateHeader", "insertLine", "deleteLines", "findLines", "_deleteHeader",
}


def _check_crud_method_is_called(p, cruds, r):
    """WIRING (WARN). A hand-written crud method that no rule, form or table references is not
    "spare capacity" — nine times out of ten it is a step somebody meant to wire and did not, and the
    feature it belongs to is quietly absent while every screen looks complete.

    The one that cost a delivery: a `buildLinesFromTemplate`-style method existed, was correct,
    and was called by nothing — so every inspection saved with an EMPTY checklist, the certificate
    PDF had no indicators, and the "any failed checkpoint?" branch downstream always answered no.

    Either call it or delete it. (11-business-logic-dynamic-crud.md)"""
    if not cruds:
        return
    haystack = json.dumps(p.rep, ensure_ascii=False)
    try:
        haystack += json.dumps(p.branches_file.data, ensure_ascii=False)
    except Exception:
        pass
    for crud in cruds:
        alias = crud.get("alias")
        for m in (crud.get("methods") or []):
            name = m.get("methodName")
            if not name or name in _SCAFFOLD_METHODS:
                continue
            if ("service.crud.%s.%s" % (alias, name)) in haystack:
                continue
            if re.search(r'"%s"' % re.escape(name), haystack):
                continue            # referenced by name from a model/settings blob
            r.warn("crud %r method %r is called by NOTHING — no rule, no form, no table. A method "
                   "nobody invokes is usually a step that was written and never wired, and the "
                   "feature it belongs to is missing while the screens look complete. Call it or "
                   "delete it. (11-business-logic-dynamic-crud.md)" % (alias, name))


_GROOVY_NAME_RE = re.compile(r"[A-Za-z_]\w*")
_GROOVY_DEF_AT_RE = re.compile(r"\bdef\s+([A-Za-z_]\w*)")
_GROOVY_KEYWORDS = {
    "def", "if", "else", "for", "while", "return", "new", "try", "catch", "finally", "throw",
    "instanceof", "as", "in", "null", "true", "false", "this", "it", "switch", "case", "break",
    "continue", "class", "import", "assert", "each", "String", "Map", "List", "Integer", "Long",
    "BigDecimal", "Object", "Boolean", "Throwable", "RuntimeException", "LinkedHashMap",
    "long", "int", "double", "float", "boolean", "byte", "short", "char", "void", "var",
}

# a declaration the simple scanner does not see as one: `def a = 1, b = 2` (only `a` is matched by
# the `def <name>` pattern) and `long n = ...` / `BigDecimal x = ...` (a TYPE, not `def`). Both
# declare a local; missing them turns a correct rule into a false "never declared" report.
_GROOVY_DECL_LINE_RE = re.compile(
    r"^\s*(?:def|var|long|int|double|float|boolean|byte|short|char|String|Map|List|Integer|"
    r"Long|BigDecimal|Object|Boolean)\s")
_GROOVY_ASSIGN_RE = re.compile(r"\b([A-Za-z_]\w*)\s*=(?!=)")


_GROOVY_CATCH_PARAM_RE = re.compile(r"\bcatch\s*\(\s*[\w.]+(?:\s*\|\s*[\w.]+)*\s+(\w+)\s*\)")
_GROOVY_FOR_PARAM_RE = re.compile(r"\bfor\s*\(\s*(?:def\s+|final\s+|[\w.<>\[\]]+\s+)?(\w+)\s*(?::|=|\bin\b)")
_GROOVY_CLOSURE_PARAM_RE = re.compile(r"\{\s*([A-Za-z_][\w,\s]*?)\s*->")


def _groovy_extra_decls(src):
    """Every name a simple `def <name>` pattern does not reach but Groovy still declares:
    the second half of `def a = 1, b = 2`, a typed local (`long n = …`), a `catch (Throwable e)`
    parameter, a `for (x : xs)` variable and a closure's own parameters."""
    out = {}
    for m in _GROOVY_CATCH_PARAM_RE.finditer(src):
        out.setdefault(m.group(1), m.start(1))
    for m in _GROOVY_FOR_PARAM_RE.finditer(src):
        out.setdefault(m.group(1), m.start(1))
    for m in _GROOVY_CLOSURE_PARAM_RE.finditer(src):
        for nm in m.group(1).split(","):
            nm = nm.strip().split(" ")[-1]
            if nm:
                out.setdefault(nm, m.start(1))
    pos = 0
    for line in src.splitlines(keepends=True):
        if _GROOVY_DECL_LINE_RE.match(line):
            for m in _GROOVY_ASSIGN_RE.finditer(line):
                out.setdefault(m.group(1), pos + m.start(1))
        pos += len(line)
    return out


_GROOVY_CTRL_OPENERS = ("if", "for", "while", "switch", "catch", "try", "else", "finally", "do", "synchronized")


def _groovy_block_is_control(src, brace_pos):
    """True when the `{` at brace_pos opens an if/for/while/try/catch/else body rather than a
    closure. A control body runs INLINE, in the enclosing scope - so a name used inside it resolves
    exactly like one written at top level, and a missing declaration throws there just the same.
    A closure body is different: it runs later, so a name in it may legally sit above its `def`."""
    j = brace_pos - 1
    while j >= 0 and src[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return False
    if src[j] == ")":
        # walk back over the balanced (...) and look at the keyword in front of it
        depth = 0
        while j >= 0:
            if src[j] == ")":
                depth += 1
            elif src[j] == "(":
                depth -= 1
                if depth == 0:
                    break
            j -= 1
        j -= 1
        while j >= 0 and src[j] in " \t\r\n":
            j -= 1
    end = j + 1
    while j >= 0 and (src[j].isalnum() or src[j] == "_"):
        j -= 1
    return src[j + 1:end] in _GROOVY_CTRL_OPENERS


def _groovy_top_level_scan(src):
    """(top-level `def` positions, top-level bare-name uses) with comments, strings and closure
    bodies removed. An if/try/for body is NOT removed: it runs inline in the same scope, which is
    where a copied-in block hides an undeclared name."""
    defs, uses = {}, []
    ctrl_stack = []
    i, n, depth = 0, len(src), 0
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i)
            i = n if j < 0 else j + 2
            continue
        if ch == "/":
            # a slashy regex literal: /^[A-Z]+-\d{2}$/ — its \d would otherwise read as a name
            k = i - 1
            while k >= 0 and src[k] in " \t":
                k -= 1
            if k < 0 or src[k] in "=~(,[:?{;&|!+":
                j = i + 1
                while j < n and src[j] not in "\n":
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == "/":
                        j += 1
                        break
                    j += 1
                i = j
                continue
        if ch in "'\"":
            q = ch
            triple = src[i:i + 3] == q * 3
            i += 3 if triple else 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if triple and src[i:i + 3] == q * 3:
                    i += 3
                    break
                if not triple and src[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            # a control body keeps the enclosing scope; a closure body is skipped
            depth += 0 if _groovy_block_is_control(src, i) else 1
            ctrl_stack.append(_groovy_block_is_control(src, i))
            i += 1
            continue
        if ch == "}":
            if ctrl_stack:
                if not ctrl_stack.pop():
                    depth -= 1
            else:
                depth -= 1
            i += 1
            continue
        # ⛔ parentheses do NOT hide a name: `foo(bar)` and `((x ?: y) as String)` evaluate
        # bar/x/y right here, in this scope. Counting them as depth was what let an undeclared
        # name inside a call or a cast slip past every offline gate.
        if ch.isalpha() or ch == "_":
            m = _GROOVY_NAME_RE.match(src, i)
            word = m.group(0)
            if depth == 0:
                if word == "def":
                    d = _GROOVY_DEF_AT_RE.match(src, i)
                    if d:
                        defs.setdefault(d.group(1), d.start(1))
                        i = d.end(1)
                        continue
                elif word not in _GROOVY_KEYWORDS:
                    before = src[i - 1] if i else " "
                    after = src[m.end():m.end() + 1]
                    if before != "." and after not in (".", ":"):
                        uses.append((word, i))
            i = m.end()
            continue
        i += 1
    return defs, uses


def _check_rule_service_validation(p, r):
    """RUNTIME-THROW (ERROR). `service.validation` does not exist. The message collector of a VALIDATION_RULE is the
    binding `validation` (and the bare helpers `addError` / `addFieldError` / ...), NOT a member of `service`
    (08-groovy-rules-and-context.md "The VALIDATION shape", 16-groovy-service-api.md Part 3).

    Writing it the way `service.crud` / `service.rule` are written is the natural slip, and it is silent until a
    document actually violates the rule: the rule then dies with the platform's

        Failed to execute rule '<name>': Validation rule execution failed: validation

    instead of the sentence the author wrote, while the save is still refused - so every test that only checks
    "the save was refused" stays green. Measured on a delivered ERP: 7 of its 13 validation rules (15 call sites).

    Fix: `validation.addFieldError("<control name>", "<message>")`, or the bare `addFieldError(...)`. Strings and
    comments are ignored, so a message that quotes the wrong spelling does not trigger this."""
    for rule in (p.rep.get("rules") or []):
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if "service.validation" not in src and "service . validation" not in src:
            continue
        code = _strip_groovy_noise(src)
        code = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', code)
        code = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", code)
        if re.search(r"\bservice\s*\.\s*validation\b", code):
            r.err("rule %r calls `service.validation...` - there is no such member. A validation rule's collector is the "
                  "binding `validation` (or the bare helpers `addError` / `addFieldError`): write "
                  "`validation.addFieldError(\"<control name>\", \"<message>\")`. As written, a violation does not show "
                  "your message - the platform prints \"Validation rule execution failed: validation\" and still refuses "
                  "the save. (08-groovy-rules-and-context.md \"The VALIDATION shape\")" % rule.get("name"))


def _check_groovy_var_used_before_def(p, r):
    """RUNTIME-THROW (ERROR). Groovy resolves a bare identifier that has no `def` *yet* against the
    rule's CONTEXT, not against a local - so reading a variable above the line that declares it does
    not give null, it throws:

        Failed to execute rule '<name>': Context 'before' not found. Available contexts must be
        attached to the rule via contextIdentifiers.

    which reads like a context-wiring problem and is not one. The action simply never runs.

    It is produced by an ordinary edit - inserting a status guard above the line that computes the
    status - and it is invisible to every offline gate. Measured on a delivered MES: **68 action
    rules**, i.e. every state transition in the project, dead from the first day; the screens looked
    finished because the buttons were there and the confirm dialog appeared.

    Fix: move the `def` above its first use. (08-groovy-rules-and-context.md)"""
    for rule in (p.rep.get("rules") or []):
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if not src or "def " not in src:
            continue
        try:
            defs, uses = _groovy_top_level_scan(src)
        except Exception:
            continue
        for word, pos in uses:
            at = defs.get(word)
            if at is None or at <= pos:
                continue
            r.err("rule %r reads %r at line %d but declares it with `def` at line %d. Groovy looks a "
                  "not-yet-declared name up in the rule's CONTEXT, so this throws \"Context '%s' not "
                  "found\" and the whole action never runs - an error that points at context wiring "
                  "and has nothing to do with it. Move the `def` above its first use. "
                  "(08-groovy-rules-and-context.md)"
                  % (rule.get("name"), word, src[:pos].count("\n") + 1,
                     src[:at].count("\n") + 1, word))
            break


_GROOVY_SCRIPT_GLOBALS = {
    "service", "context", "param", "params", "binding", "out", "log", "args", "result",
    # bound by the platform in a generated fetch / row-scope rule (the filter-bar payload)
    "attrs",
}


_GROOVY_DEF_RE = re.compile(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)")


_CRUD_CREATE_CALL_RE = re.compile(
    r"service\.crud\.([A-Za-z_]\w*)\.(create|insert|insertLine|createHeader|createLine)\s*\(\s*\[")


def _map_literal_keys(src, open_idx):
    """TOP-LEVEL keys of the Groovy map literal that starts at `open_idx` (the '[').

    Returns (keys, ok). `ok` is False when the literal cannot be read honestly — an
    unbalanced tail, or a spread (`*:other`) that adds keys this reader cannot see.
    A check that guesses in those cases produces noise, and noise is what makes people
    stop reading `validate`.
    """
    depth, i, n = 0, open_idx, len(src)
    body_start = open_idx + 1
    while i < n:
        c = src[i]
        if c in "[(":
            depth += 1
        elif c in "])":
            depth -= 1
            if depth == 0:
                body = src[body_start:i]
                if "*:" in body:
                    return set(), False
                keys, d = set(), 0
                for m in re.finditer(r"[\[\](){}]|([A-Za-z_]\w*)\s*:", body):
                    tok = m.group(0)
                    if tok in "[({":
                        d += 1
                    elif tok in "])}":
                        d -= 1
                    elif m.group(1) and d == 0:
                        keys.add(m.group(1))
                return keys, True
        elif c in "'\"":
            q = c
            i += 1
            while i < n and src[i] != q:
                i += 2 if src[i] == "\\" else 1
        i += 1
    return set(), False


def _check_crud_create_call_not_null(p, r):
    """RUNTIME-THROW (WARNING). The caller of a create method cannot see the schema.

    An INSERT can list every NOT NULL column and still fail on every call: the column is
    bound to a PARAMETER, and the Groovy that calls the method decides whether that
    parameter gets a value. Nothing in between looks at the two together — the SQL is
    valid, the rule compiles, `validate` is green, the button renders — and the failure
    arrives as a PostgreSQL message from inside a rule:

        ERROR: null value in column "uom_id" of relation "stock_movement"
        violates not-null constraint

    Measured on a delivered project: posting an inventory count had never once worked.
    The unit of measure belongs to the LOT, the engine did not read it, and
    `stock_movement.uom_id` is NOT NULL — so the count completed, the register showed it
    as posted, and the balance never moved. The previous version of this check looked at
    the INSERT alone and saw nothing wrong, because nothing IS wrong with the INSERT.

    The check reads the create method's own INSERT to learn which parameter feeds which
    column, then looks at every literal map a rule passes to that method. It accepts both
    spellings of a reference key — `uom_id` and the platform's paired form `uom__id`
    (11-business-logic-dynamic-crud.md) — and stays quiet on anything it cannot read
    exactly: a map built in a variable, a spread, a value that is `COALESCE`d in the SQL.

    Fix: give the caller the value (read it from the row that owns it, and refuse with a
    human message when it is missing) — never make the column nullable to silence this.
    (11-business-logic-dynamic-crud.md)"""
    crud_file = p.cruds_file
    cruds = (crud_file.data.get("cruds", []) if crud_file else []) or []
    if not cruds:
        return
    try:
        idx = dyncheck.build_schema_index(p.db)
    except Exception:
        return

    # alias -> method -> {column: parameter}
    need = {}
    for crud in cruds:
        sidx = idx.get(crud.get("sourceSchema")) or {}
        tables = sidx.get("tables", {})
        for m in crud.get("methods", []) or []:
            if m.get("methodType") != "SQL":
                continue
            sql = m.get("script", "") or ""
            for tbl, cols in _parse_inserts(sql):
                cols_l = [c.lower() for c in cols]
                for c in tables.get(tbl, []) or []:
                    if c["name"] == "id" or c["default"] or not c["notnull"]:
                        continue
                    if c["name"].lower() not in cols_l:
                        continue        # reported by the INSERT check itself
                    # a column whose VALUE is a literal or COALESCE needs no caller key
                    val = re.search(
                        r"[(,]\s*%s\s*(?=[,)])" % re.escape(c["name"]), sql, re.I)
                    need.setdefault(crud.get("alias"), {}).setdefault(
                        m.get("methodName"), {})[c["name"]] = tbl

    if not need:
        return
    for rule in (p.rep.get("rules") or []):
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if "service.crud." not in src:
            continue
        for call in _CRUD_CREATE_CALL_RE.finditer(src):
            alias, method = call.group(1), call.group(2)
            cols = (need.get(alias) or {}).get(method)
            if not cols:
                continue
            keys, ok = _map_literal_keys(src, src.index("[", call.end() - 1))
            if not ok:
                continue
            for col, tbl in sorted(cols.items()):
                alts = {col, col.lower()}
                if col.endswith("_id"):
                    alts.add(col[:-3] + "__id")
                    alts.add(_snake_to_camel(col[:-3]) + "__id")
                alts.add(_snake_to_camel(col))
                if not (alts & keys):
                    r.warn("rule %r calls %s.%s without %r — %s.%s is NOT NULL with no "
                           "default, so this call throws \"null value in column\" from "
                           "PostgreSQL at runtime. The caller cannot see the schema; only "
                           "this pairing can. (11-business-logic-dynamic-crud.md)"
                           % (rule.get("name"), alias, method, col, tbl, col))


def _snake_to_camel(name):
    head, *rest = name.split("_")
    return head + "".join(w[:1].upper() + w[1:] for w in rest)


def _check_groovy_duplicate_def(p, r):
    """COMPILE-FAIL (ERROR). Two `def` of the SAME name in the SAME block do not shadow one
    another in Groovy — they stop the script from compiling at all:

        Failed to compile Groovy script: startup failed:
        RULE_Script_…: 338: The current scope already contains a variable of the name __cySeq
        @ line 338, column 5.   def __cySeq = '01'

    The rule then never runs — not the second half, the WHOLE rule — and the message points at a
    line number inside a generated script nobody has open. Measured on a delivered project: the
    close engine of the production order, i.e. the one action the whole month of work leads up to,
    dead because two independent fixes each introduced a helper named `__cySeq` — one a numbering
    closure shared by six engines, the other a local lot sequence. Both authors were right; the
    collision belonged to neither.

    This is what makes it worth a check rather than a review: the two `def`s are usually hundreds of
    lines apart, each looks correct in its own paragraph, and no offline gate reads scope. The check
    compares the BLOCK PATH, not the nesting depth — `list.each { def x = … }` twice is legal,
    because those are two different blocks at the same depth.

    Fix: rename the one whose meaning is narrower (`__cyLotSeq`), never the one that is shared.
    (08-groovy-rules-and-context.md)"""
    for rule in (p.rep.get("rules") or []):
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if not src or "def " not in src:
            continue
        try:
            body = _strip_groovy_noise(src)
        except Exception:
            continue
        seen, stack, counter, reported = {}, [0], [0], set()
        i, n = 0, len(body)
        while i < n:
            c = body[i]
            if c == "{":
                counter[0] += 1
                stack.append(counter[0])
                i += 1
                continue
            if c == "}":
                if len(stack) > 1:
                    stack.pop()
                i += 1
                continue
            m = _GROOVY_DEF_RE.match(body, i)
            if m:
                key = (tuple(stack), m.group(1))
                if key in seen and m.group(1) not in reported:
                    reported.add(m.group(1))
                    r.err("rule %r declares `def %s` twice in the SAME block (line %d and line %d). "
                          "Groovy refuses to compile that — \"The current scope already contains a "
                          "variable of the name %s\" — and the rule does not run AT ALL, not just "
                          "its second half. Rename the narrower one. "
                          "(08-groovy-rules-and-context.md)"
                          % (rule.get("name"), m.group(1),
                             body[:seen[key]].count("\n") + 1, body[:m.start()].count("\n") + 1,
                             m.group(1)))
                seen.setdefault(key, m.start())
                i = m.end()
                continue
            i += 1


def _check_groovy_undefined_identifier(p, r):
    """RUNTIME-THROW (ERROR). The sibling of the used-above-its-`def` bug, and the one that is
    easier to write: a top-level name that is **never declared in the rule at all**.

    Groovy resolves it exactly the same way — against the rule's CONTEXT — so it throws

        Failed to execute rule '<name>': Context 'po' not found

    and the action dies on its first line of real work. It happens when a block is copied between
    rules (`po` exists in the engine you copied FROM and not in the one you pasted INTO), or when a
    variable is renamed in one place. Nothing offline sees it: the script compiles, `validate` is
    green, the button renders, and the failure shows up only when a user presses it.

    Conservative by construction — it reports a bare name only when ALL of these hold: it is used at
    depth 0, it is not a method call (`foo(`), it is not capitalised (class names), it is not a
    Groovy keyword, and it is not one of the script globals the platform binds (`service`,
    `context`, `param`, …). Fix: declare it, or read it from where it actually lives.
    (08-groovy-rules-and-context.md)"""
    for rule in (p.rep.get("rules") or []):
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        if not src:
            continue
        try:
            defs, uses = _groovy_top_level_scan(src)
        except Exception:
            continue
        extra = _groovy_extra_decls(src)
        seen = set()
        for word, pos in uses:
            if word in defs or word in extra or word in seen:
                continue
            if word in _GROOVY_SCRIPT_GLOBALS or word[:1].isupper() or word[:1] == "_":
                continue
            # ⛔ The FIRST NON-SPACE character after the name, however far away it is. A fixed
            # two-character window silently gave up on aligned code: `roleGroups     : [...]` left
            # the window holding two spaces, so neither the call test below nor the map-key test
            # ever saw anything. Scan instead of peeking.
            after = src[pos + len(word):].lstrip()[:1]
            if after == "(":
                continue
            # A KEY of a map literal is not a read: `[roleGroups: [...], entity_id : x]` names the
            # slot, it does not look anything up in the context. The check missed this only when the
            # author ALIGNED the colons — in ONE literal `entity_table: 'x'` was skipped and
            # `entity_id   : y` was flagged — because the two-character window after the word held
            # `  ` and never reached the colon. The `.lstrip()` above already tolerates the spaces;
            # what was missing is the colon itself in the accept list.
            #
            # A ternary (`cond ? foo : bar`) is the one shape this now lets through, and that is the
            # cheap direction to be wrong in: the check is conservative by construction (it already
            # skips every capitalised name and every call), a false POSITIVE fails a release gate on
            # correct code, and a false negative costs one runtime error in a script its author is
            # writing at that moment. Measured on a real project: 19 of 62 `validate` errors were
            # this one shape.
            if after == ":":
                continue
            seen.add(word)
            r.err("rule %r reads %r at line %d and never declares it. Groovy looks an undeclared "
                  "name up in the rule's CONTEXT, so this throws \"Context '%s' not found\" the "
                  "moment the action runs - the script compiles, the button renders, and the work "
                  "never happens. Declare it (or read the value from where it really lives). "
                  "(08-groovy-rules-and-context.md)"
                  % (rule.get("name"), word, src[:pos].count("\n") + 1, word))
            break


def _check_user_task_action_has_complete_rule(p, r):
    """SILENT-NO-OP (ERROR). A user-task action with no `onBeforeUserTaskCompleteRuleIdentifier`
    completes the BPMN task and does **nothing else**. The token moves, the row leaves the worklist,
    the user sees no error — and the record the case is about is untouched: not approved, not closed,
    not rejected.

    That is the most expensive shape of bug in a workflow project, because the happy path *looks*
    like it worked. Measured on a delivered MES: **9 of 17 task actions**, which made four whole
    flows decorative — a recipe could be submitted for approval and never approved.

    Every action that decides something needs a rule that writes that decision.

    ⛔ …but the rule does not have to hang on the ACTION. A flow may legitimately let the button do
    nothing but complete the task, and write the decision in a **ServiceTask downstream**, with the
    gateway telling the branches apart by the status the *other* branch changed («still SUBMITTED ==
    approved»). That design is symmetric on purpose: the refusing branch carries the rule, the
    approving one is the fall-through. Flagging it cost 7 of 62 errors on a delivered project where
    all seven approving branches had a writing ServiceTask below them. So the ERROR now stands only
    when NOTHING downstream of the task can write: no reachable ServiceTask with rules.
    (07-workflows-and-tasks.md)"""
    for w in (p.rep.get("workflows") or []):
        elements = w.get("elements") or []
        # graph over sequence flows + which ids are ServiceTasks that actually carry rules
        edges, writers = {}, set()
        for e in elements:
            st = e.get("settings") or {}
            props = {x.get("name"): x.get("value") for x in (st.get("properties") or [])}
            if st.get("type") == "bpmn:SequenceFlow":
                src, dst = props.get("sourceRef"), props.get("targetRef")
                if src and dst:
                    edges.setdefault(src, []).append(dst)
            elif st.get("type") == "bpmn:ServiceTask" and (props.get("rule") or "").strip():
                if props.get("id"):
                    writers.add(props["id"])

        def _writes_downstream(start):
            seen_ids, queue = set(), list(edges.get(start, []))
            while queue:
                node = queue.pop()
                if node in seen_ids:
                    continue
                seen_ids.add(node)
                if node in writers:
                    return True
                queue.extend(edges.get(node, []))
            return False

        for e in elements:
            st = e.get("settings") or {}
            if st.get("type") != "bpmn:UserTask":
                continue
            props = {x.get("name"): x.get("value") for x in (st.get("properties") or [])}
            raw = props.get("userActions")
            if not raw:
                continue
            try:
                actions = (json.loads(raw) or {}).get("actions") or []
            except ValueError:
                continue
            downstream = _writes_downstream(props.get("id")) if props.get("id") else False
            for a in actions:
                if a.get("onBeforeUserTaskCompleteRuleIdentifier"):
                    continue
                names = a.get("localizedNames") or {}
                label = names.get("en_US") or names.get("ru_RU") or a.get("id") or "?"
                if downstream:
                    r.warn("workflow %r task %r action %r has no onBeforeUserTaskCompleteRule. A "
                           "ServiceTask downstream does carry rules, so the decision can be written "
                           "there — check that it is, and that the gateway tells the branches apart "
                           "by something this action changes. (07-workflows-and-tasks.md)"
                           % ((w.get("name") or "?"), props.get("name") or props.get("id"), label))
                    continue
                r.err("workflow %r task %r action %r has NO onBeforeUserTaskCompleteRule and NO "
                      "rule-carrying ServiceTask downstream — pressing it completes the task and "
                      "changes NOTHING about the record: no approval, no status, no audit. The case "
                      "leaves the worklist and the happy path looks finished. Wire the rule that "
                      "writes the decision. (07-workflows-and-tasks.md)"
                      % ((w.get("name") or "?"), props.get("name") or props.get("id"), label))


# ---------------------------------------------------------------------------
# Execution access — who may RUN a rule / a dynamic CRUD / one method (08 §"Execution access", 11)
# ---------------------------------------------------------------------------

_ACCESS_DOC = "(08-groovy-rules-and-context.md §\"Execution access\")"
_CRUD_ACCESS_DOC = "(11-business-logic-dynamic-crud.md §\"Execution access\")"


def _check_execution_access_shape(p, cruds, r):
    """SHAPE (ERROR) + IGNORED / UNMATCHED SETTINGS (WARN) of every execution-access value in the export.

    `rules[].access`, `cruds[].access` and `cruds[].methods[].{inheritAccess, access}` all hold the one object
    `{publicAccess, authenticatedUserAccess, roleGroups}` (execaccess.py). Absent / null is the platform default —
    signed-in users — and is never reported.

    ERROR: not an object, an unknown key (the platform's reader skips it, so a typo such as `public` silently
    leaves the artefact at signed-in users), a flag that is not a boolean, `roleGroups` that is not a list of
    strings, an `inheritAccess` that is not a boolean.

    WARN: a role group the export does not define (it matches nobody until a group of that EXACT name exists);
    role groups next to a flag that makes them irrelevant; `inheritAccess: false` with no `access` (= signed-in
    users — almost never what was meant by switching inheritance off); an `access` on a method that still
    inherits (ignored); an `access` on a hidden rule (a CRUD method's body — ignored, the METHOD decides)."""
    from . import execaccess

    known = execaccess.project_role_groups(p.rep)

    def common(label, value, doc):
        problems = execaccess.shape_problems(value)
        for pr in problems:
            r.err("%s: access %s. Expected {\"publicAccess\": bool, \"authenticatedUserAccess\": bool, "
                  "\"roleGroups\": [\"<role group>\", …]} or no key at all (= signed-in users). %s"
                  % (label, pr, doc))
        if problems:
            return False
        missing = execaccess.unknown_groups(value, known)
        if missing:
            r.warn("%s: access names role group(s) %s that this export does not define (roleGroups: %s) — until "
                   "a group of that EXACT name exists it matches nobody, and only administrators and authors may "
                   "run it. %s" % (label, ", ".join(repr(g) for g in missing),
                                    ", ".join(sorted(known)) or "none", doc))
        flag, ignored = execaccess.ignored_groups(value)
        if flag:
            r.warn("%s: access sets %s=true AND lists roleGroups %s — role groups are read only when neither flag "
                   "is set, so they are ignored here. %s" % (label, flag, ", ".join(ignored), doc))
        return True

    for rule in p.rep.get("rules", []) or []:
        if not isinstance(rule, dict) or rule.get("access") is None:
            continue
        label = "rule %r" % (rule.get("name") or rule.get("identifier"))
        if common(label, rule.get("access"), _ACCESS_DOC) and rule.get("hidden") is True:
            r.warn("%s is hidden (the body of a CRUD GROOVY method) and carries an access — it is IGNORED: only "
                   "the platform and authors run a hidden rule directly, and whoever calls the method is checked "
                   "against the METHOD's access (mrjun.py crud method-access). %s" % (label, _CRUD_ACCESS_DOC))

    for crud in cruds or []:
        if not isinstance(crud, dict):
            continue
        alias = crud.get("alias")
        if crud.get("access") is not None:
            common("crud %r" % alias, crud.get("access"), _CRUD_ACCESS_DOC)
        for m in crud.get("methods") or []:
            if not isinstance(m, dict):
                continue
            label = "crud %r method %r" % (alias, m.get("methodName"))
            inherit = m.get("inheritAccess")
            if inherit is not None and not isinstance(inherit, bool):
                r.err("%s: inheritAccess is %r (%s), not a boolean (true/absent = the CRUD's access, false = the "
                      "method's own). %s" % (label, inherit, type(inherit).__name__, _CRUD_ACCESS_DOC))
                continue
            acc = m.get("access")
            if acc is not None and not common(label, acc, _CRUD_ACCESS_DOC):
                continue
            if inherit is False and acc is None:
                r.warn("%s: inheritAccess is false but the method has no access of its own — that means signed-in "
                       "users, whatever the CRUD says. If that is the intent, say it explicitly (mrjun.py crud "
                       "method-access %s %s --access signed-in); otherwise --inherit. %s"
                       % (label, alias, m.get("methodName"), _CRUD_ACCESS_DOC))
            elif inherit is not False and acc is not None:
                r.warn("%s: carries an access (%s) but still inherits the CRUD's (inheritAccess is %s) — the "
                       "method's own access is read ONLY when inheritAccess is false, so it is ignored. Set it with "
                       "mrjun.py crud method-access, which writes both. %s"
                       % (label, execaccess.describe(acc), "absent" if "inheritAccess" not in m else inherit,
                          _CRUD_ACCESS_DOC))


_CALL_RULE_LIT_RE = re.compile(r"""\bcallRule\s*\(\s*(['"`])((?:\\.|(?!\1).)+?)\1""")
_CALL_BL_LIT_RE = re.compile(r"""\bcallBl\s*\(\s*(['"`])([\w.-]+)\1\s*,\s*(['"`])([\w.-]+)\3""")
_JS_STR_LIT_RE = re.compile(r"""(['"`])((?:\\.|(?!\1)[^\\\n])*)\1""")


def _node_visible(node):
    """A node's OWN view gate for an anonymous visitor: no roleAccess (= `new RoleAccess()`, public) or
    publicReadAccess not false. Access is not inherited (01 §"Access — roleAccess")."""
    ra = node.get("roleAccess") if isinstance(node, dict) else None
    return not isinstance(ra, dict) or ra.get("publicReadAccess", True) is not False


def _anonymous_nodes(p):
    """(node, page) for every content node an ANONYMOUS visitor's render of a PUBLIC page reaches.

    A page is public by its own roleAccess (not by its parent's). Inside it, a node renders when it and every
    node above it up to the page pass their own view gate. A page-local stub of a common component
    (`linkContentIdentifier`) renders the SHARED node — gated by the shared node's own access — so the shared
    subtree is walked in its place, once per page that uses it."""
    by_uid = {}
    for br in p.branches or []:
        if not isinstance(br, dict):
            continue
        for vp in br.get("virtualPlugins") or []:
            c = vp.get("content") if isinstance(vp, dict) else None
            if isinstance(c, dict):
                for n, _pp, _pt in core.iter_nodes(c):
                    if isinstance(n.get("uniqueIdentifier"), str):
                        by_uid.setdefault(n["uniqueIdentifier"], n)
    out = []

    def walk(node, page, public, stack):
        if not isinstance(node, dict):
            return
        if node.get("pluginName") == "siteMapPage":
            page, public = node, _node_visible(node)
        elif not public or not _node_visible(node):
            return
        else:
            out.append((node, page))
            target = by_uid.get(node.get("linkContentIdentifier"))
            if target is not None and id(target) not in stack and _node_visible(target):
                walk(target, page, True, stack | {id(target)})
        for ch in node.get("children") or []:
            if isinstance(ch, dict) and (public or ch.get("pluginName") == "siteMapPage"):
                walk(ch, page, public, stack)

    root = p.root_content
    if isinstance(root, dict):
        walk(root, root, _node_visible(root), frozenset())
    return out


def _json_strings(obj, key=None):
    """Every (key, string) leaf of a parsed JSON value."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _json_strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _json_strings(v, key)
    elif isinstance(obj, str):
        yield key, obj


def _check_public_page_rule_access(p, cruds, r):
    """REFUSED ON A PUBLIC PAGE (WARN). The executor checks who may run a rule at its rule door, whoever calls —
    and an anonymous visitor passes only an access with `publicAccess: true`. Absent / null is signed-in users.
    So once the platform carries execution access, EVERY rule an anonymous visitor triggers is refused
    (`ACCESS_DENIED` "Not authorized to run this rule") until it is opened to anyone: the public form will not
    submit, the dropdown is empty, the studio component's `ctx.callRule` rejects. Nothing offline or at import
    says so — the page renders, and fails on the first click of the first visitor who is not signed in.

    Found from the PAGE side, over every node a public page renders to an anonymous visitor (`_anonymous_nodes`):
      * any rule identifier in a node's config (form-control predicates / validation / default-value / choices
        rules, table fetch rules and action rules, buttons …) — an exact rule-uuid match, so never a guess;
      * a form whose content node is on such a page: its `validators` / `actionValidators`; a form group whose
        landing page is public: its predicate→form mapping predicates;
      * an `nct.html.plugin` studio script: `ctx.callRule('<name or identifier>'…)` literals, and — weaker, said
        so in the message — a string literal that IS the exact name of an EXECUTION rule (the shape of a helper
        `<helper>(ctx, '<rule>', …)` or a `{ kind: '<rule>' }` table that ends in `ctx.callRule`). Comments are
        skipped;
      * `ctx.callBl('<alias>', '<method>'…)` literals: here the METHOD must be open to anyone — reported apart,
        because the better fix is a rule (24 §4.3).

    Hidden rules (CRUD method bodies) are skipped: their callers are governed by the method. Nested calls are not
    re-checked, so the CRUD methods a public rule calls stay at their default — never open them to fix this.
    WARN, not ERROR: an older platform ignores the key, and a project may deliberately keep a rule signed-in only
    on a page whose anonymous visitors never reach that control."""
    from . import execaccess

    rules = [x for x in (p.rep.get("rules") or []) if isinstance(x, dict) and x.get("identifier")]
    if not rules:
        return
    by_id = {x["identifier"]: x for x in rules}
    by_lname = {}
    for x in rules:
        if isinstance(x.get("name"), str):
            by_lname.setdefault(x["name"].strip().lower(), x)
    exec_by_name = {x.get("name"): x for x in rules
                    if x.get("ruleType") == "EXECUTION_RULE" and x.get("hidden") is not True
                    and isinstance(x.get("name"), str) and len(x["name"].strip()) >= 3}

    refs = {}           # rule identifier -> {page label: set((kind, where))}
    bl_refs = {}        # (alias, method) -> {page label: set((kind, where))}

    def page_label(page):
        return str(page.get("name") or page.get("alias") or page.get("identifier") or "?")

    def add(store, key, page, kind, where):
        store.setdefault(key, {}).setdefault(page_label(page), set()).add((kind, where))

    anon = _anonymous_nodes(p)
    node_ids = {}       # identifier of a node an anonymous visitor's render reaches -> its page
    page_ids = {}       # identifier of a public page that renders something -> the page
    form_pages = {}     # identifier of a public page on which a dynaform.form.plugin renders anonymously -> page

    def index(store, obj, page):
        for k in ("identifier", "uniqueIdentifier"):
            if isinstance(obj.get(k), str):
                store.setdefault(obj[k], page)

    for node, page in anon:
        index(node_ids, node, page)
        index(page_ids, page, page)
        if node.get("pluginName") == "dynaform.form.plugin":
            index(form_pages, page, page)
        what = "%s %r" % (node.get("pluginName"), node.get("name") or node.get("identifier"))
        props = node.get("properties") or {}
        if not isinstance(props, dict):
            continue
        for slot, prop in props.items():
            sv = prop.get("stringValue") if isinstance(prop, dict) else None
            if not isinstance(sv, str) or not sv.strip():
                continue
            if sv.strip() in by_id:
                add(refs, sv.strip(), page, "config", "%s %s" % (what, slot))
                continue
            if sv.lstrip()[:1] not in ("{", "["):
                continue
            try:
                inner = json.loads(sv)
            except ValueError:
                continue
            if slot == "studioModel" and isinstance(inner, dict):
                for scr in inner.get("scripts") or []:
                    if not isinstance(scr, dict) or scr.get("enabled") is False:
                        continue
                    code = _strip_groovy_comments(scr.get("code") or "")
                    where = "%r/%s" % (node.get("name") or node.get("identifier"), scr.get("name"))
                    called = set()
                    for m in _CALL_RULE_LIT_RE.finditer(code):
                        tok = m.group(2).strip()
                        rule = by_id.get(tok) or by_lname.get(tok.lower())
                        if rule is not None:
                            called.add(rule["identifier"])
                            add(refs, rule["identifier"], page, "callRule", where)
                    for m in _CALL_BL_LIT_RE.finditer(code):
                        add(bl_refs, (m.group(2), m.group(4)), page, "callBl", where)
                    for m in _JS_STR_LIT_RE.finditer(code):
                        rule = exec_by_name.get(m.group(2)) or by_id.get(m.group(2))
                        if rule is not None and rule["identifier"] not in called:
                            add(refs, rule["identifier"], page, "named", where)
                continue
            for key, val in _json_strings(inner):
                if val in by_id:
                    add(refs, val, page, "config", "%s %s" % (what, key or slot))

    # forms whose form renders on a public page (`contentIdentifier` names the form PAGE — 06), form groups whose
    # landing page is public (the mapping predicates pick the form to open)
    for form in p.rep.get("forms") or []:
        if not isinstance(form, dict):
            continue
        cid = form.get("contentIdentifier")
        page = form_pages.get(cid) or node_ids.get(cid)
        if page is None:
            continue
        own = {k: v for k, v in form.items() if k != "formGroup"}
        for key, val in _json_strings(own):
            if val in by_id and val != form.get("identifier"):
                add(refs, val, page, "form", "%r %s" % (form.get("name"), key))
    for fg in p.rep.get("formGroups") or []:
        if not isinstance(fg, dict):
            continue
        page = page_ids.get(fg.get("contentPageIdentifier")) or node_ids.get(fg.get("contentPageIdentifier"))
        if page is None:
            continue
        for mp in ((fg.get("predicateFormMapping") or {}).get("mapping") or []) \
                if isinstance(fg.get("predicateFormMapping"), dict) else []:
            rid = mp.get("predicateIdentifier") if isinstance(mp, dict) else None
            if rid in by_id:
                add(refs, rid, page, "formgroup", repr(fg.get("name")))

    def pages_words(places):
        names = sorted(places)
        head = ", ".join(repr(n) for n in names[:3])
        return head + (" (+%d more)" % (len(names) - 3) if len(names) > 3 else "")

    kind_words = (
        ("config", "referenced by the config of %s"),
        ("form", "referenced by form %s"),
        ("formgroup", "a mapping predicate of form group %s"),
        ("callRule", "called with ctx.callRule from studio script %s"),
        ("callBl", "called from studio script %s"),
        ("named", "named in a string literal of studio script %s (passed to ctx.callRule through a helper?)"),
    )

    def how_words(places):
        seen = {}
        for hs in places.values():
            for kind, where in hs:
                seen.setdefault(kind, set()).add(where)
        parts = []
        for kind, text in kind_words:
            wheres = sorted(seen.get(kind) or ())
            if wheres:
                parts.append(text % (wheres[0] + (" (+%d more)" % (len(wheres) - 1) if len(wheres) > 1 else "")))
        return "; ".join(parts)

    for rid, places in sorted(refs.items(), key=lambda kv: str(by_id[kv[0]].get("name"))):
        rule = by_id[rid]
        if rule.get("hidden") is True or execaccess.is_public(rule.get("access")):
            continue
        name = rule.get("name") or rid
        r.warn("rule %r (%s) runs for ANONYMOUS visitors of public page(s) %s — %s — but its access is %s. On a "
               "platform with execution access every visitor who is not signed in is REFUSED (ACCESS_DENIED \"Not "
               "authorized to run this rule\"): the form does not submit, the list stays empty, the call rejects. "
               "Open the rule to anyone — mrjun.py rule access %s --access anyone — and leave the CRUD methods it "
               "calls at their default: nested calls are not re-checked. %s"
               % (name, rule.get("ruleType"), pages_words(places), how_words(places),
                  execaccess.describe(rule.get("access")),
                  rid if not isinstance(rule.get("name"), str) else "'%s'" % rule["name"].replace("'", "'\\''"),
                  _ACCESS_DOC))

    cruds_by_alias = {c.get("alias"): c for c in cruds or [] if isinstance(c, dict)}
    for (alias, method), places in sorted(bl_refs.items()):
        crud = cruds_by_alias.get(alias)
        if crud is None:
            r.warn("ctx.callBl(%r, %r) on public page(s) %s (%s): an anonymous visitor passes only a method open "
                   "to anyone — for a Java CRUD that is @CrudAccess(publicAccess = true) on the method or class, "
                   "which exposes it to every visitor with devtools. Prefer ctx.callRule on a rule opened to "
                   "anyone that calls the method (nested calls are not re-checked). "
                   "(24-html-component-studio.md §4.3)"
                   % (alias, method, pages_words(places), how_words(places)))
            continue
        m = next((x for x in crud.get("methods") or [] if isinstance(x, dict) and x.get("methodName") == method),
                 None)
        if m is None:
            continue
        acc, source = execaccess.method_effective(crud, m)
        if execaccess.is_public(acc):
            continue
        r.warn("ctx.callBl(%r, %r) on public page(s) %s (%s), but the method runs with %s (%s) — an anonymous "
               "visitor is REFUSED (HTTP 403 \"Not authorized to run %s.%s\"). Opening the METHOD to anyone exposes "
               "it to every visitor with devtools; prefer ctx.callRule on a rule opened to anyone that calls it, "
               "and keep the method at its default. (24-html-component-studio.md §4.3)"
               % (alias, method, pages_words(places), how_words(places), execaccess.describe(acc), source,
                  alias, method))



# ---------------------------------------------------------------------------------------------------------------------
# 35-semantic-types-and-field-decisions.md — the checks that catch a field built from its STORAGE type, and business data
# written into code. Each was a defect on a delivered project that every shape check passed.
# ---------------------------------------------------------------------------------------------------------------------
_CHECK_COL_RX = re.compile(r'ALTER TABLE "[^"]+"\."([^"]+)" ADD CONSTRAINT "[^"]+" CHECK \(\(\(([a-z_][a-z0-9_]*)\)::text = ANY')
_FK_COL_RX = re.compile(r'ALTER TABLE "[^"]+"\."([^"]+)" ADD CONSTRAINT "[^"]+" FOREIGN KEY \("([^"]+)"\)')
_CHECK_VALS_RX = re.compile(r"'([^']*)'::character varying")


def _dump_tables(p):
    dump = p.db if isinstance(getattr(p, "db", None), dict) else {}
    return [t for sch in dump.get("schemas") or [] for t in sch.get("tables") or []], dump


def _coded_columns(p):
    """(table, column) -> ('check', {allowed values}) | ('fk', None), from the dump's constraint statements."""
    _tables, dump = _dump_tables(p)
    out = {}
    for sch in dump.get("schemas") or []:
        for stmt in sch.get("checkConstraints") or []:
            m = _CHECK_COL_RX.search(stmt or "")
            if m:
                out[(m.group(1), m.group(2))] = ("check", set(_CHECK_VALS_RX.findall(stmt)))
        for stmt in sch.get("foreignKeys") or []:
            m = _FK_COL_RX.search(stmt or "")
            if m:
                out.setdefault((m.group(1), m.group(2)), ("fk", None))
    return out


def _crud_columns(p):
    """crud alias -> (table, {dtoFieldName: column}) — the table read off the crud's findAll."""
    cf = p.cruds_file
    out = {}
    for c in ((cf.data or {}).get("cruds") or []) if cf is not None else []:
        table = None
        for m in c.get("methods") or []:
            if m.get("methodName") == "findAll" and m.get("script"):
                mm = re.search(r"\bFROM\s+([a-z_][a-z0-9_]*)", m["script"], re.I)
                table = mm.group(1) if mm else None
                break
        if table:
            out[c.get("alias")] = (table, {f.get("fieldName"): f.get("displayName") for f in c.get("dtoFields") or []})
    return out


def _check_text_control_on_coded_column(p, r):
    """ERROR. A text or textarea control bound to a column whose values are CODED — a CHECK allowed-value set (a closed
    enum) or a foreign key (a reference). Somebody types a code by hand that a rule selects by: the settings form of a
    delivered project took a vocabulary NAME as free text, and a typo detached the label from the data with no error.
    The control is a dropdown over the catalogue that holds the values (35 §1-§2). A READ-ONLY text control over a code
    is reported as a WARN: it shows the raw code instead of its label."""
    coded = _coded_columns(p)
    cruds = _crud_columns(p)
    if not coded or not cruds:
        return
    seen = set()
    for node, _parent, _path in core.iter_nodes(p.root_content):
        if node.get("pluginName") not in ("dynaform.form.text.field.plugin", "dynaform.form.textarea.field.plugin"):
            continue
        st = core.get_inner_json(node, "settings")
        if not isinstance(st, dict) or not st.get("crudAlias"):
            continue
        tc = cruds.get(st.get("crudAlias"))
        if not tc:
            continue
        table, cols = tc
        col = cols.get(st.get("fieldExpression")) or st.get("fieldExpression")
        kind = coded.get((table, col))
        if not kind or (table, col) in seen:
            continue
        seen.add((table, col))
        what = "a CHECK allowed-value set" if kind[0] == "check" else "a foreign key"
        msg = ("control %r writes %s.%s as free text, but the column carries %s: a coded value is chosen from its catalogue, "
               "never typed (35-semantic-types-and-field-decisions.md §2)" % (node.get("name"), table, col, what))
        if st.get("alwaysProhibited"):
            r.warn(msg + " — the control is read-only, so it shows the raw code instead of its label")
        else:
            r.err(msg)


def _check_case_variant_values(p, r):
    """WARN. An EDITABLE text control over a column whose rows already hold the same value in two spellings that differ only
    in case or outer blanks («Սև» and «սև», «Black » and «black»). The column is an OPEN classifier (35 §1, T2/T7: a group,
    a colour, a person in charge) typed by hand: every report that groups by it splits one value in two. Make the control an
    autocomplete over the values already in use (one spelling each, the most used first); the field stays free text, so a new
    value is still typed — the second spelling of an old one is not. Found on a delivered project: 22 materials, 7 colours twice."""
    cruds = _crud_columns(p)
    tables, _dump = _dump_tables(p)
    if not cruds or not tables:
        return
    rows_of = {t.get("name"): t.get("rows") or [] for t in tables}
    seen = set()
    for node, _parent, _path in core.iter_nodes(p.root_content):
        if node.get("pluginName") not in ("dynaform.form.text.field.plugin", "dynaform.form.textarea.field.plugin"):
            continue
        st = core.get_inner_json(node, "settings")
        if not isinstance(st, dict) or not st.get("crudAlias") or st.get("alwaysProhibited"):
            continue
        tc = cruds.get(st.get("crudAlias"))
        if not tc:
            continue
        table, cols = tc
        col = cols.get(st.get("fieldExpression")) or st.get("fieldExpression")
        if (table, col) in seen:
            continue
        seen.add((table, col))
        spellings = {}
        for row in rows_of.get(table) or []:
            v = row.get(col) if isinstance(row, dict) else None
            if isinstance(v, str) and v.strip():
                spellings.setdefault(v.strip().lower(), set()).add(v)
        twice = sorted(k for k, vs in spellings.items() if len(vs) > 1)
        if twice:
            r.warn("control %r types %s.%s by hand and the rows already spell %d value(s) two ways (%s) — an open classifier: "
                   "make it an autocomplete over the values in use (35 §1 T2/T7)" % (node.get("name"), table, col, len(twice),
                                                                                  ", ".join(twice[:3])))


def _check_dropdown_not_searchable(p, r):
    """WARN. An editable dropdown fed by a choices rule that cannot search: the control lacks `searchEnabled`, or its rule never
    reads `filterBy` (Select2 then narrows nothing). People type the middle of a word, in their own language — a delivered project's
    owner asked for containment search on every list (35 §2 rule 5). One line per rule, counting its controls."""
    bodies = {x.get("identifier"): ((x.get("rule") or {}).get("ruleScriptStr") or "") for x in p.rep.get("rules") or []}
    names = {x.get("identifier"): x.get("name") for x in p.rep.get("rules") or []}
    off, deaf = {}, {}
    for node, _parent, _path in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.form.rimm.drop.down.field.plugin":
            continue
        st = core.get_inner_json(node, "settings")
        if not isinstance(st, dict) or st.get("alwaysProhibited") or not st.get("ruleIdentifier"):
            continue
        rid = st["ruleIdentifier"]
        if rid not in bodies:
            continue
        if not st.get("searchEnabled"):
            off[rid] = off.get(rid, 0) + 1
        elif "filterBy" not in bodies[rid]:
            deaf[rid] = deaf.get(rid, 0) + 1
    for rid, n in sorted(off.items(), key=lambda x: str(names.get(x[0]))):
        r.warn("%d dropdown(s) over rule %r cannot be searched (no searchEnabled) — 35 §2 rule 5" % (n, names.get(rid)))
    for rid, n in sorted(deaf.items(), key=lambda x: str(names.get(x[0]))):
        r.warn("rule %r ignores filterBy: its %d searchable dropdown(s) never narrow — 35 §2 rule 5" % (names.get(rid), n))


_SERVER_TODAY = re.compile(r"CURRENT_DATE|LocalDate\.now\(\s*\)|LocalDateTime\.now\(\s*\)|to_char\(\s*now\(\)\s*,\s*'YYYY")


def _check_server_clock_today(p, r):
    """WARN. «Today» read off the server's clock (UTC): `CURRENT_DATE`, `LocalDate.now()`, the year `to_char(now(),'YYYY')`. For a
    customer east of Greenwich that is yesterday every night until local midnight reaches UTC — a delivered project dated lots,
    documents and report ages a day early from 00:00 to 04:00 and numbered 1 January's documents with last year (35 §4a). Route
    every «today» through one business-time-zone expression. One line per rule / method."""
    for x in p.rep.get("rules") or []:
        if _SERVER_TODAY.search((x.get("rule") or {}).get("ruleScriptStr") or ""):
            r.warn("rule %r takes «today» from the server clock (UTC) — use the business time zone (35 §4a)" % x.get("name"))
    cruds = ((p.cruds_file.data or {}).get("cruds") or []) if getattr(p, "cruds_file", None) else []
    for c in cruds:
        for m in c.get("methods") or []:
            if _SERVER_TODAY.search(m.get("script") or ""):
                r.warn("method %s.%s takes «today» from the server clock (UTC) — use the business time zone (35 §4a)"
                       % (c.get("alias"), m.get("methodName")))


def _literal_then_word(body):
    """Places where a Groovy string literal is followed by an identifier with no operator between (`as`/`in`/`instanceof` aside)."""
    i, n, out = 0, len(body), []
    while i < n:
        c = body[i]
        if body.startswith("//", i):
            j = body.find("\n", i)
            i = n if j < 0 else j
            continue
        if body.startswith("/*", i):
            j = body.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if body.startswith("'''", i) or body.startswith('"""', i):
            j = body.find(body[i:i + 3], i + 3)
            i = n if j < 0 else j + 3
        elif c in "'\"":
            j = i + 1
            while j < n and body[j] != c:
                j += 2 if body[j] == "\\" else 1
            i = j + 1
        else:
            i += 1
            continue
        m = re.match(r"[ \t]*([A-Za-z_][A-Za-z0-9_]*)", body[i:i + 40])
        if m and m.group(1) not in ("as", "in", "instanceof"):
            out.append(body[max(0, i - 30):i + 20].replace("\n", " "))
    return out


def _check_literal_runs_into_word(p, r):
    """ERROR. A string literal followed by a bare word: `'<td style="font-family:'Helvetica Neue',…'` closes the literal at the
    inner quote and Groovy reads `Helvetica Neue …` as a command chain. It COMPILES — the compiler gate is green — and throws
    `MissingPropertyException` the first time the line runs: a delivered project's mismatch digest never went out (35 §4a)."""
    for x in p.rep.get("rules") or []:
        for hit in _literal_then_word((x.get("rule") or {}).get("ruleScriptStr") or ""):
            r.err("rule %r: a string literal runs into a bare word (…%s…) — escape the quote (35 §4a)" % (x.get("name"), hit))


def _check_flag_as_text(p, r):
    """WARN. A yes/no field rendered as a text field: it prints `true` / `false` in every language. A flag is a read-only choice
    over a yes/no vocabulary on a form, and a column with trueIcon/falseIcon in a grid (35 §4a)."""
    for node, _parent, _path in core.iter_nodes(p.root_content):
        if node.get("pluginName") != "dynaform.form.text.field.plugin":
            continue
        st = core.get_inner_json(node, "settings")
        if isinstance(st, dict) and st.get("dataClass") == "java.lang.Boolean":
            r.warn("field %r (%s) is a yes/no value shown as text — it prints true/false (35 §4a)"
                   % (st.get("name"), st.get("fieldExpression")))


def _check_alias_case_split(p, r):
    """ERROR. One reference aliased both unquoted (`AS expenseCategory__name`, folded to lower case) and quoted
    (`AS "expenseCategory__kind"`): the platform builds two nested objects and the columns over one of them are blank (35 §4a)."""
    cruds = ((p.cruds_file.data or {}).get("cruds") or []) if getattr(p, "cruds_file", None) else []
    for c in cruds:
        for m in c.get("methods") or []:
            sql = m.get("script") or ""
            quoted = {x.group(1) for x in re.finditer(r'AS "([A-Za-z0-9]+)__[A-Za-z0-9]+"', sql)}
            plain = {x.group(1) for x in re.finditer(r"AS ([A-Za-z0-9]+)__[A-Za-z0-9]+\b", sql)}
            for ref in sorted(q for q in quoted & plain if q != q.lower()):
                r.err("method %s.%s aliases %s both quoted and unquoted — its leaves split into two objects (35 §4a)"
                      % (c.get("alias"), m.get("methodName"), ref))


def _check_localize_flat_shape(p, r):
    """ERROR. A seeded localized jsonb whose TOP-LEVEL keys are locales (`{"en_US": …, "ru_RU": …}`). The resolver reads
    `localize[<dtoField>][<locale>]`, so this translation is never shown — in no register, no dropdown, no session — and
    nothing logs it. A delivered project ran two months with every seeded label and name in its authoring language in the
    English and Russian sessions, while the rows its users created through the forms translated fine (35 §5)."""
    tables, _dump = _dump_tables(p)
    loc_rx = re.compile(r"^[a-z]{2}_[A-Z]{2}$")
    for t in tables:
        for col in ("localize", "localized"):
            if col not in (t.get("columns") or []):
                continue
            for row in t.get("rows") or []:
                v = row.get(col) if isinstance(row, dict) else None
                if not v:
                    continue
                try:
                    obj = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    continue
                if isinstance(obj, dict) and any(loc_rx.match(k) for k in obj):
                    r.err("table %r: %s is keyed by LOCALE at the top (%s) — the platform reads {<dtoField>: {<locale>: …}}, "
                          "so these translations are never shown (35 §5, 20-localization.md)" % (t.get("name"), col, sorted(obj)[:3]))
                    break


def _check_rule_label_copy(p, r):
    """WARN. A map literal in a rule whose keys are values of ONE CHECK allowed-value set and whose values read as labels
    (`[DRAFT: 'Սևագիր', POSTED: 'Անցկացված']`). It is a second copy of the vocabulary's labels: renamed in the label table,
    it keeps the old word. Show a coded value through a helper that reads the label table in the session language (35 §3)."""
    sets = [vals for (_t, _c), (kind, vals) in _coded_columns(p).items() if kind == "check" and vals]
    if not sets:
        return
    lit = re.compile(r"\[\s*((?:'?[A-Za-z_][A-Za-z0-9_]*'?\s*:\s*'[^'\n]*'\s*,\s*)+'?[A-Za-z_][A-Za-z0-9_]*'?\s*:\s*'[^'\n]*')\s*\]")
    for rule in p.rep.get("rules") or []:
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        for m in lit.finditer(src):
            pairs = re.findall(r"'?([A-Za-z_][A-Za-z0-9_]*)'?\s*:\s*'([^'\n]*)'", m.group(1))
            keys = {k for k, _v in pairs}
            if len(keys) >= 2 and any(keys <= s for s in sets) and any(re.search(r"[^\x00-\x7f]|\s", v) for _k, v in pairs):
                r.warn("rule %r keeps its own map of vocabulary labels %s — read them from the label table instead "
                       "(35 §3)" % (rule.get("name"), sorted(keys)[:4]))
                break


def _check_helper_closure_undefined(p, r):
    """ERROR. `NAME(...)` called in a rule that never defines `def NAME = {`, while another rule of the project does — a
    helper closure copied by use and not by definition. Groovy compiles the call and throws MissingMethodException when the
    line runs: a delivered project's «Close» button failed on its first real press, with the compiler gate green (35 §4)."""
    rules = p.rep.get("rules") or []
    top_def = re.compile(r"(?m)^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{")
    helpers = set()
    for rule in rules:
        helpers |= set(top_def.findall(((rule.get("rule") or {}).get("ruleScriptStr") or "")))
    for rule in rules:
        src = ((rule.get("rule") or {}).get("ruleScriptStr") or "")
        own = set(re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*=", src))
        for name in sorted(helpers - own):
            if re.search(r"(?<![\w.$])%s\(" % re.escape(name), src):
                r.err("rule %r calls %s(...) but never defines it (other rules do) — it throws MissingMethodException "
                      "the first time that line runs; include the helper's definition (35 §4)" % (rule.get("name"), name))


def _check_rule_lists_business_codes(p, r):
    """WARN. A rule or SQL method that quotes two or more codes seeded in a catalogue (`*_code` columns of the dump: warehouse
    codes, category or series prefixes). Those are rows the business owns: a new one is invisible to the code that lists the
    old ones (a code-suggestion rule ignored the customer's new category). Read them with a business-logic method (35 §3)."""
    tables, _dump = _dump_tables(p)
    codes = set()
    for t in tables:
        for col in t.get("columns") or []:
            if not col.endswith("_code"):
                continue
            for row in t.get("rows") or []:
                v = row.get(col) if isinstance(row, dict) else None
                if isinstance(v, str) and 2 <= len(v) <= 40:
                    codes.add(v)
                    if "-" in v:
                        codes.add(v.split("-")[0])
    if not codes:
        return
    bodies = [("rule", rl.get("name"), ((rl.get("rule") or {}).get("ruleScriptStr") or "")) for rl in p.rep.get("rules") or []]
    cf = p.cruds_file
    for c in ((cf.data or {}).get("cruds") or []) if cf is not None else []:
        for m in c.get("methods") or []:
            bodies.append(("method", "%s.%s" % (c.get("alias"), m.get("methodName")), m.get("script") or ""))
    for kind, name, src in bodies:
        hit = set(re.findall(r"'([A-Za-z0-9][A-Za-z0-9_-]{1,39})'", src)) & codes
        if len(hit) >= 2:
            r.warn("%s %r names business codes %s in its body — read them from their table (35 §3)" % (kind, name, sorted(hit)[:5]))
