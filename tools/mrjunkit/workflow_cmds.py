"""workflow — rep-objects.workflows[] entities (add / list).

A workflow is an executable BPMN 2.0 process (Flowable). It lives in
`rep-objects.json.workflows[]` and stores the BPMN XML (`bpmnContent`) plus a
denormalised `elements[]` array derived from it. See ../07-workflows-and-tasks.md.

`workflow add` generates a skeleton executable BPMN chaining the steps given on
the command line IN ORDER:
    startEvent -> step1 -> step2 -> ... -> stepN -> endEvent
where each step is one of --user-task / --service-task / --gateway (they may be
interleaved; the on-the-line order is preserved). It emits a matching
`elements[]` (ids consistent with the XML) and a minimal BPMNDiagram so the
modeler can open it. `processDefinitionId=null`, `deployed=false`,
`externalId=null`.

Step kinds:
  * --user-task "<name>[:<formGroup id|name>]"
      A userTask. If a formGroup is given it is resolved in rep-objects.formGroups
      and bound via a `flowable:userActions` JSON action (the ACTION-object shape
      from doc 07, `direct:"off"` opening that form group). Without a formGroup it
      is a plain userTask (backward compatible with the old `--user-task NAME`).
  * --service-task "<name>:<rule id|name>"
      A serviceTask with flowable:delegateExpression="${ruleTask}" and
      flowable:rule="<rule-uuid>". The rule is resolved in rep-objects.rules.
  * --gateway "<name>"
      An exclusiveGateway inserted in the sequence with exactly one incoming and
      one outgoing flow (a split/join placeholder). The split branches are added
      by hand afterwards, and a branch needs all THREE of: a conditionExpression
      predicate on every branch except one, the gateway's default="<that one>",
      and a name on every branch (07-workflows-and-tasks.md §4).

XML/namespaces/tags follow the Flowable template the platform's own modeler emits. The
generated `bpmnContent` is validated (xml.etree.ElementTree parse) before save.
"""

import json
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils

from . import core

# ---------------------------------------------------------------------------
# id generation (BPMN-modeler-style short ids, e.g. Event_ab12cd3)
# ---------------------------------------------------------------------------


def _short(prefix):
    # 7 lowercase-hex chars, matching the flowable/bpmn.io modeler style.
    return "%s_%s" % (prefix, core.new_uuid().replace("-", "")[:7])


# Property-set builders for elements[] — mirror the extractor output for each
# node type (see 07-workflows-and-tasks.md "Observed property sets").


def _prop(name, value):
    return {"name": name, "value": value, "type": None, "control": None, "order": 0}


def _element(node_id, bpmn_type, props):
    return {"id": node_id, "settings": {"properties": props, "type": bpmn_type}}


# ---------------------------------------------------------------------------
# ordered step graph model: start -> step1 -> ... -> stepN -> end
# ---------------------------------------------------------------------------
#
# Each step is a dict: {kind, id, name, ...kind-specific keys}
#   kind == "user"    -> optional form_group_id, user_actions (JSON string) / None
#   kind == "service" -> rule_id
#   kind == "gateway" -> (id/name only)


class _Graph:
    """Holds the ordered node/flow lists so the XML and elements[] stay in sync."""

    def __init__(self):
        self.process_id = "Process_1"
        self.start_id = _short("Event")
        self.end_id = _short("Event")
        self.steps = []   # list of step dicts, in command-line order
        self.flows = []   # list of (id, sourceRef, targetRef)

    def build(self, steps):
        # steps already carry their own node ids; chain start -> steps... -> end
        self.steps = steps
        chain = [self.start_id] + [s["id"] for s in self.steps] + [self.end_id]
        for src, tgt in zip(chain, chain[1:]):
            self.flows.append((_short("Flow"), src, tgt))

    # --- incoming/outgoing lookups for XML <incoming>/<outgoing> tags -------
    def outgoing(self, node_id):
        return [f[0] for f in self.flows if f[1] == node_id]

    def incoming(self, node_id):
        return [f[0] for f in self.flows if f[2] == node_id]


# ---------------------------------------------------------------------------
# step parsing / resolution
# ---------------------------------------------------------------------------


def _build_user_actions(form_group_id, name, locales=None):
    """A minimal one-action UserTaskActionsDto (form 'a' from doc 07): open the
    form group (direct:"off"). Returns the JSON string, or None for a plain task.

    Seeds localizedNames/localizedButtonNames for EVERY tenant locale (copying the
    default text, like quicklink) — auto-translate never runs on import, so a
    default-only map would under-cover the tenant. See 20-localization.md §iv."""
    if not form_group_id:
        return None
    locs = locales or ["en_US"]
    name_map = {loc: name for loc in locs}
    action = {
        "id": core.new_uuid(),
        "localizedNames": dict(name_map),
        "localizedButtonNames": dict(name_map),
        "predicateIdentifier": None,
        "onBeforeUserTaskStartRuleIdentifier": None,
        "onBeforeUserTaskCompleteRuleIdentifier": None,
        "validationRuleIdentifiers": None,
        "direct": "off",
        "formGroupIdentifier": form_group_id,
        "taskId": None,
        "completeUserTask": "on",
        "icon": None,
        "submitForm": None,
    }
    return json.dumps({"actions": [action], "errors": []}, ensure_ascii=False)


def _resolve_steps(project, ordered_specs):
    """Turn the ordered (kind, spec) list into resolved step dicts.

    ordered_specs preserves the command-line interleaving of --user-task /
    --service-task / --gateway.
    """
    steps = []
    for kind, spec in ordered_specs:
        if kind == "user":
            # "<name>[:<formGroup id|name>]"
            name, _, fg_key = spec.partition(":")
            name = name.strip()
            fg_key = fg_key.strip()
            if not name:
                raise core.ToolError("--user-task needs a name: %r" % spec)
            form_group_id = None
            if fg_key:
                fg = core.resolve_rep(project, "formGroups", fg_key)
                form_group_id = fg["identifier"]
            steps.append({
                "kind": "user",
                "id": _short("Activity"),
                "name": name,
                "form_group_id": form_group_id,
                "user_actions": _build_user_actions(form_group_id, name, project.locales()),
            })
        elif kind == "service":
            # "<name>:<rule id|name>"  (rule is mandatory)
            name, sep, rule_key = spec.partition(":")
            name = name.strip()
            rule_key = rule_key.strip()
            if not name or not sep or not rule_key:
                raise core.ToolError(
                    "--service-task must be \"<name>:<rule id|name>\": %r" % spec)
            rule = core.resolve_rep(project, "rules", rule_key)  # errors if not found
            steps.append({
                "kind": "service",
                "id": _short("Activity"),
                "name": name,
                "rule_id": rule["identifier"],
            })
        elif kind == "gateway":
            name = spec.strip()
            if not name:
                raise core.ToolError("--gateway needs a name")
            steps.append({
                "kind": "gateway",
                "id": _short("Gateway"),
                "name": name,
            })
        else:  # pragma: no cover - guarded by the CLI action
            raise core.ToolError("unknown step kind: %r" % kind)
    return steps


# ---------------------------------------------------------------------------
# BPMN XML generation (string-built, Flowable-compatible namespaces)
# ---------------------------------------------------------------------------

_NS = (
    'xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
    'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
    'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
    'xmlns:flowable="http://flowable.org/bpmn" '
    'targetNamespace="http://bpmn.io/schema/bpmn"'
)


def _esc(s):
    return saxutils.escape(s or "", {'"': "&quot;"})


def _esc_attr(s):
    # quote an attribute value; " -> &#34; to match the real userActions encoding
    return saxutils.escape(s or "", {'"': "&#34;"})


def _bpmn_xml(g):
    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<definitions %s>' % _NS)
    L.append('  <process id="%s" isExecutable="true">' % g.process_id)

    # startEvent
    L.append('    <startEvent id="%s">' % g.start_id)
    for f in g.outgoing(g.start_id):
        L.append('      <outgoing>%s</outgoing>' % f)
    L.append('    </startEvent>')

    # endEvent
    L.append('    <endEvent id="%s">' % g.end_id)
    for f in g.incoming(g.end_id):
        L.append('      <incoming>%s</incoming>' % f)
    L.append('    </endEvent>')

    # steps (in order)
    for s in g.steps:
        sid = s["id"]
        if s["kind"] == "user":
            attrs = ' id="%s" name="%s"' % (sid, _esc(s["name"]))
            if s.get("user_actions"):
                attrs += ' flowable:userActions="%s"' % _esc_attr(s["user_actions"])
            L.append('    <userTask%s>' % attrs)
            for f in g.incoming(sid):
                L.append('      <incoming>%s</incoming>' % f)
            for f in g.outgoing(sid):
                L.append('      <outgoing>%s</outgoing>' % f)
            L.append('    </userTask>')
        elif s["kind"] == "service":
            L.append('    <serviceTask id="%s" name="%s" '
                     'flowable:delegateExpression="${ruleTask}" '
                     'flowable:rule="%s">'
                     % (sid, _esc(s["name"]), _esc(s["rule_id"])))
            for f in g.incoming(sid):
                L.append('      <incoming>%s</incoming>' % f)
            for f in g.outgoing(sid):
                L.append('      <outgoing>%s</outgoing>' % f)
            L.append('    </serviceTask>')
        elif s["kind"] == "gateway":
            L.append('    <exclusiveGateway id="%s" name="%s">'
                     % (sid, _esc(s["name"])))
            for f in g.incoming(sid):
                L.append('      <incoming>%s</incoming>' % f)
            for f in g.outgoing(sid):
                L.append('      <outgoing>%s</outgoing>' % f)
            L.append('    </exclusiveGateway>')

    # sequenceFlows
    for fid, src, tgt in g.flows:
        L.append('    <sequenceFlow id="%s" sourceRef="%s" targetRef="%s" />'
                 % (fid, src, tgt))

    L.append('  </process>')

    # -- minimal BPMNDiagram: lay nodes out left-to-right on one row --------
    L.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    L.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="%s">' % g.process_id)
    # ordered nodes for layout: start, steps..., end
    ordered = [(g.start_id, "event")]
    for s in g.steps:
        ordered.append((s["id"], "gateway" if s["kind"] == "gateway" else "task"))
    ordered.append((g.end_id, "event"))
    centers = {}
    x = 160
    y_center = 120
    for node_id, kind in ordered:
        if kind == "event":
            w, h = 36, 36
        elif kind == "gateway":
            w, h = 50, 50
        else:
            w, h = 100, 80
        bx = x
        by = y_center - h // 2
        centers[node_id] = (bx + w // 2, by + h // 2)
        L.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s">' % (node_id, node_id))
        L.append('        <dc:Bounds x="%d" y="%d" width="%d" height="%d" />' % (bx, by, w, h))
        if kind == "task":
            L.append('        <bpmndi:BPMNLabel />')
        L.append('      </bpmndi:BPMNShape>')
        x += w + 60
    for fid, src, tgt in g.flows:
        sx, sy = centers.get(src, (0, y_center))
        tx, ty = centers.get(tgt, (0, y_center))
        L.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">' % (fid, fid))
        L.append('        <di:waypoint x="%d" y="%d" />' % (sx, sy))
        L.append('        <di:waypoint x="%d" y="%d" />' % (tx, ty))
        L.append('      </bpmndi:BPMNEdge>')
    L.append('    </bpmndi:BPMNPlane>')
    L.append('  </bpmndi:BPMNDiagram>')
    L.append('</definitions>')
    return "\n".join(L)


# ---------------------------------------------------------------------------
# elements[] generation — one entry per BPMN node/flow, ids match the XML
# ---------------------------------------------------------------------------


def _elements(g):
    els = []
    # bpmn:Process (root)
    els.append(_element(g.process_id, "bpmn:Process", [
        _prop("isExecutable", True),
        _prop("id", g.process_id),
    ]))
    # bpmn:StartEvent
    els.append(_element(g.start_id, "bpmn:StartEvent", [
        _prop("id", g.start_id),
    ]))
    # bpmn:Task  (end event projects onto bpmn:Task — no BPMN_END in the enum)
    els.append(_element(g.end_id, "bpmn:Task", [
        _prop("id", g.end_id),
    ]))
    # per-step nodes
    for s in g.steps:
        sid = s["id"]
        if s["kind"] == "user":
            props = [
                _prop("exclusive", True),
                _prop("candidateGroups", ""),
                _prop("id", sid),
                _prop("name", s["name"]),
                _prop("async", False),
                _prop("candidateUsers", ""),
            ]
            if s.get("user_actions"):
                # in elements[] the userActions JSON is a plain string (\" not &#34;)
                props.append(_prop("userActions", s["user_actions"]))
            els.append(_element(sid, "bpmn:UserTask", props))
        elif s["kind"] == "service":
            els.append(_element(sid, "bpmn:ServiceTask", [
                _prop("rule", s["rule_id"]),
                _prop("exclusive", True),
                _prop("id", sid),
                _prop("delegateExpression", "${ruleTask}"),
                _prop("name", s["name"]),
                _prop("async", False),
                _prop("implementationType", "delegateExpression"),
                _prop("implementation", "${ruleTask}"),
            ]))
        elif s["kind"] == "gateway":
            els.append(_element(sid, "bpmn:ExclusiveGateway", [
                _prop("id", sid),
                _prop("name", s["name"]),
            ]))
    # bpmn:SequenceFlow
    for fid, src, tgt in g.flows:
        els.append(_element(fid, "bpmn:SequenceFlow", [
            _prop("id", fid),
            _prop("sourceRef", src),
            _prop("targetRef", tgt),
        ]))
    return els


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_workflow_add(args):
    p = core.Project(args.project)
    workflows = p.rep.setdefault("workflows", [])
    if any(w.get("name") == args.name for w in workflows):
        raise core.ToolError("workflow name already exists: %s" % args.name)

    # ordered/interleaved steps: the CLI OrderedStep action appended (kind, spec)
    # tuples to args.steps in command-line order. Fall back to the legacy
    # args.user_task list if the ordered list is absent (backward compat).
    ordered_specs = getattr(args, "steps", None)
    if not ordered_specs:
        ordered_specs = [("user", n) for n in (getattr(args, "user_task", None) or [])]

    steps = _resolve_steps(p, ordered_specs)

    g = _Graph()
    g.build(steps)

    bpmn = _bpmn_xml(g)
    # hard requirement: emit well-formed XML (validate before writing)
    try:
        ET.fromstring(bpmn)
    except ET.ParseError as exc:
        raise core.ToolError("generated BPMN XML is not well-formed: %s" % exc)

    elements = _elements(g)

    # --context -> contextIdentifiers (resolve each; null if none given)
    context_ids = None
    if args.context:
        context_ids = []
        for key in args.context:
            ctx = core.resolve_context(p, key)
            if ctx["identifier"] not in context_ids:
                context_ids.append(ctx["identifier"])

    obj = core.new_rep_object(p, {
        "name": args.name,
        "description": args.desc,
        "bpmnContent": bpmn,
        "elements": elements,
        "contextIdentifiers": context_ids,
        "externalId": None,
        "processDefinitionId": None,
        "deployed": False,
    })
    workflows.append(obj)
    p.mark(core.F_REP)
    p.save()

    # confirmation
    def _label(s):
        if s["kind"] == "user":
            return "user:%s%s" % (s["name"], " (form)" if s.get("form_group_id") else "")
        if s["kind"] == "service":
            return "service:%s (rule)" % s["name"]
        return "gateway:%s" % s["name"]

    chain = " -> ".join(["start"] + [_label(s) for s in steps] + ["end"])
    counts = {"user": 0, "service": 0, "gateway": 0}
    for s in steps:
        counts[s["kind"]] += 1
    core.out(
        "workflow added: %s\n  identifier=%s\n  steps=%d (userTasks=%d serviceTasks=%d gateways=%d)\n  %s\n  elements=%d  deployed=false"
        % (args.name, obj["identifier"], len(steps),
           counts["user"], counts["service"], counts["gateway"], chain, len(elements)))
    if counts["gateway"]:
        core.out("  NOTE: exclusiveGateway(s) emitted with one incoming + one outgoing flow only. Adding the\n"
                 "        split branches by hand needs all THREE of (07-workflows-and-tasks.md §4):\n"
                 "          1. a <conditionExpression> predicate on every branch EXCEPT one — that one is the `else`;\n"
                 "          2. default=\"<id of that unconditional branch>\" on the <exclusiveGateway> — without it the\n"
                 "             routing falls back to document ORDER, and if every branch is conditional the case\n"
                 "             THROWS 'No outgoing sequence flow ... could be selected' and sticks;\n"
                 "          3. a name= on EVERY branch — the fallback shows no rule and no condition (by design: it\n"
                 "             has none), and `default` lives on the GATEWAY, so the label and the canvas\n"
                 "             default-flow slash marker are all a reader gets from the branch itself.\n"
                 "        `validate` (_check_gateway_branching) WARNs on each of the three — warnings, so it still\n"
                 "        exits 0; read them.")
    if context_ids:
        core.out("  contextIdentifiers=%s" % context_ids)
    return obj


def cmd_workflow_list(args):
    p = core.Project(args.project)
    workflows = p.rep.get("workflows", []) or []
    for w in workflows:
        core.out("%-32s deployed=%-5s elements=%-3d %s"
                 % (w.get("name"), w.get("deployed"),
                    len(w.get("elements", []) or []), w.get("identifier")))
    if not workflows:
        core.out("(no workflows)")
