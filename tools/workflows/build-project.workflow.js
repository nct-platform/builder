// build-project.workflow.js — a RUNNABLE Replit-style harness for the Dokie builder.
// =====================================================================================
// The concrete answer to "how are the small pieces organized and driven?":
//   manager  = this script (deterministic control flow)
//   editors  = one build agent PER plan.json task (Replit's "smallest possible task each")
//   verifier = the Verify + Gate phases (coverage gate + independent re-checks)
//
// HONEST CONSTRAINT (why this is not a naive 20-agents-at-once fan-out): a .mrjun is ONE mutable
// workdir (branches.json / rep-objects.json / project-db.dump / dynamic-cruds.json). Concurrent
// mrjun.py edits race and corrupt it. So RESEARCH and VERIFY fan out in parallel, but the BUILD
// phase runs ONE task-agent at a time, in dependency order, each gated by `validate` — small step,
// tested, then the next. That is exactly the decompose→build-each→test-each loop, made runnable.
//
// USAGE (the main loop adapts + runs this; it does NOT auto-run):
//   1. Unpack the .mrjun into a workdir; write the Phase-0 global params + a build-plan/plan.json
//      (doc 26 §2/§6) — OR let the Plan phase below draft plan.json from the PRD.
//   2. Workflow({ scriptPath: ".../build-project.workflow.js",
//                 args: { prd: "<PRD path>", workdir: "<unpacked dir>", plan: "<build-plan/plan.json>" } })
//   3. Read the returned report; drive the live-run checklist it prints (Phase 5, doc 26 §5).
// Requires the builder present at doc/builder (system_prompt.txt + docs + tools/mrjun.py).
// =====================================================================================

export const meta = {
  name: 'build-project',
  description: 'Replit-style: decompose a PRD into small tasks, build+validate EACH, then gate coverage + live-run',
  phases: [
    { title: 'Plan',     detail: 'decompose the PRD into plan.json (one testable row per unit)' },
    { title: 'Research',  detail: 'parallel: mine shapes from the builder docs + any unpacked project you have, per kind' },
    { title: 'Build',     detail: 'SEQUENTIAL: one agent per plan task, in dep order, each gated by validate' },
    { title: 'Verify',    detail: 'parallel: independent re-checks per module vs the PRD' },
    { title: 'Gate',      detail: 'coverage gate + whole-project validate + the live-run checklist' },
  ],
}

const BUILDER = process.env.DOKIE_BUILDER || 'doc/builder'   // path to this library; override with DOKIE_BUILDER
const MRJUN = `python3 ${BUILDER}/tools/mrjun.py`
const CONTEXT = `You are the Dokie builder. FIRST read ${BUILDER}/system_prompt.txt (Operating Principles + INVARIANTS) and the phase doc it points to for this task kind. Prefer mrjun.py commands over hand-JSON. Never modify any bundle other than the workdir you were given.`

const PLAN_SCHEMA = {
  type: 'object',
  properties: {
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          kind: { type: 'string', description: 'entity|form|page|rule|workflow|mailTemplate|pdfTemplate|roleGroup|scheduler|context|dashboard|chart|requirement' },
          name: { type: 'string' },
          deps: { type: 'array', items: { type: 'string' } },
          doc: { type: 'string', description: 'the builder doc that owns this kind, e.g. 04-crud-table-plugin.md' },
          test: { type: 'string', description: 'the acceptance check for this unit (T1..T5, doc 26 §3)' },
        },
        required: ['id', 'kind'],
      },
    },
  },
  required: ['tasks'],
}

const VERDICT = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    status: { type: 'string', description: 'done | blocked' },
    validateErrors: { type: 'number' },
    note: { type: 'string' },
  },
  required: ['id', 'status'],
}

// ---- Phase 1: PLAN — decompose the PRD into plan.json (the small-piece ledger) ----
phase('Plan')
const plan = await agent(
  `${CONTEXT}\nDecompose the PRD at ${args.prd} into a build plan per doc 26 §2 and §6a. Follow Phase 1 of ` +
  `19-build-decision-procedure.md: map every noun→entity, every document→header+lines entity, every status→lifecycle, ` +
  `every actor→roleGroup, every "email/print"→template, every MULTI-STEP PROCESS→a workflow task, every report/dashboard→chart tasks. ` +
  `Order tasks by dependency (DB→CRUD→context→rules→roles→forms→groups→pages→templates→workflows→schedulers→nav/home). ` +
  `Give each task an id, kind, name, deps, the owning builder doc, and its acceptance test. ` +
  `WRITE the result as ${args.plan} in the coverage shape {project,locales,items:[{id,kind,alias|name,deps,test,status:"todo"}]}, ` +
  `then return the same tasks.`,
  { label: 'plan:decompose', phase: 'Plan', schema: PLAN_SCHEMA, effort: 'high' })

const tasks = (plan && plan.tasks) ? plan.tasks : []
log(`plan: ${tasks.length} tasks`)
if (!tasks.length) return { error: 'planning produced no tasks — inspect build-plan/plan.json' }

// ---- Phase 2: RESEARCH — parallel shape-mining for the kinds present (safe: read-only) ----
phase('Research')
const kinds = [...new Set(tasks.map(t => t.kind))]
const researchKinds = kinds.filter(k => ['entity', 'form', 'page', 'workflow', 'mailTemplate', 'pdfTemplate', 'dashboard', 'rule'].includes(k))
await parallel(researchKinds.map(k => () =>
  agent(`${CONTEXT}\nMine the EXACT export shape for a "${k}" from ${BUILDER}/erp/initial_erp.mrjun (the sample bundle) and the ` +
        `owning builder doc. Produce a short copyable recipe (real JSON/Groovy + the mrjun.py command). This feeds the Build phase; ` +
        `write it to build-plan/shapes-${k}.md and return a 1-line confirmation.`,
        { label: `research:${k}`, phase: 'Research', effort: 'medium' })))

// ---- Phase 3: BUILD — SEQUENTIAL, one agent per task, each gated by validate ----
// (sequential await, NOT parallel — one shared workdir; this is the small-step build+test loop.)
phase('Build')
const done = new Set()
const built = []
// simple dependency-respecting order: iterate; a task whose deps are all done goes next.
const remaining = [...tasks]
let guard = remaining.length * 3
while (remaining.length && guard-- > 0) {
  const i = remaining.findIndex(t => (t.deps || []).every(d => done.has(d)))
  const task = remaining.splice(i < 0 ? 0 : i, 1)[0]   // if a dep cycle, take the head and let the agent cope
  const v = await agent(
    `${CONTEXT}\nBuild ONLY this one task into the workdir ${args.workdir}: id=${task.id} kind=${task.kind} name=${task.name || ''}. ` +
    `Follow ${BUILDER}/${task.doc || '19-build-decision-procedure.md'}. Author it (mrjun.py command preferred). ` +
    `THEN gate it: run \`${MRJUN} validate --project ${args.workdir}\` and fix until 0 errors (pre-existing platform-internal ` +
    `orphan warnings are ok). Do its unit test if defined: ${task.test || '(validate + a targeted structural check)'}. ` +
    `Finally set this task's status to "done" in ${args.plan}. Return {id,status,validateErrors,note}. ` +
    `Do NOT build any other task; do NOT modify anything outside the workdir.`,
    { label: `build:${task.id}`, phase: 'Build', schema: VERDICT, effort: 'high' })
  built.push(v)
  if (v && v.status === 'done') done.add(task.id)
  else log(`BLOCKED: ${task.id} — ${v && v.note ? v.note : 'see agent log'}`)
}

// ---- Phase 4: VERIFY — parallel independent re-checks per module vs the PRD ----
phase('Verify')
const epics = [...new Set(tasks.map(t => (t.id.split('-')[0] || 'misc')))]
const rechecks = await parallel(epics.map(e => () =>
  agent(`${CONTEXT}\nIndependent re-check (a FRESH read, doc 26 §3): for the "${e}" slice of the PRD at ${args.prd}, ` +
        `open ${args.workdir} with mrjun.py inspect/tree/list/show and answer: what did the PRD ask for in this slice that ` +
        `is NOT in the build, and what present item renders/behaves wrong (wrong-language label, blank dropdown/chart, missing ` +
        `action)? Return a bullet list of concrete gaps (empty if none).`,
        { label: `verify:${e}`, phase: 'Verify', effort: 'high' })))

// ---- Phase 5: GATE — coverage + validate + the live-run checklist ----
phase('Gate')
const gate = await agent(
  `${CONTEXT}\nRun the whole-project gates on ${args.workdir}:\n` +
  `  ${MRJUN} validate --project ${args.workdir}     (must be 0 errors)\n` +
  `  ${MRJUN} coverage --project ${args.workdir} --plan ${args.plan} --show-orphans   (must PASS: no MISSING, no non-done)\n` +
  `Report both results verbatim. If coverage FAILS or validate has errors, LIST exactly which tasks are missing/incomplete ` +
  `(those go back to the Build phase). Then print the REQUIRED live-run checklist the human/main-loop must drive next ` +
  `(doc 26 §5): Home renders charts; nav resolves in EACH selected language; every form opens with populated dropdowns; ` +
  `actions + workflow starts run; mail/PDF render branded; log/ui.log clean. Conclude with DONE (gates pass, live-run pending) ` +
  `or NOT-DONE (list the blockers).`,
  { label: 'gate:coverage', phase: 'Gate', effort: 'high' })

return {
  tasks: tasks.length,
  built: built.filter(b => b && b.status === 'done').length,
  blocked: built.filter(b => b && b.status !== 'done').map(b => b && b.id),
  gaps: rechecks.filter(Boolean),
  gate,
  note: 'Gates are offline. The build is NOT done until the printed live-run checklist is driven (doc 26 §5).',
}
