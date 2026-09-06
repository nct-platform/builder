# 28 · Support mode — changing a LIVE project over MCP

> **Scope.** What changes when you are handed a project that already RUNS, plus a token, instead of a PRD and a
> blank folder: how the working folder tells you which mode you are in, how the MCP channel differs from the file
> channel, the order a change must be applied in when it goes to BOTH, which kind of object travels down which
> channel, and — the part that decides whether this mode is honest — the list of things the channel cannot carry
> at all, which still need a re-import.
> **Not here:** the build itself → `system_prompt.txt` and [19](19-build-decision-procedure.md); the export
> format and what import does to a project → [00](00-export-format-and-import.md); the delta loop's *authoring*
> half (locate → minimal delta → apply only the delta) → [19](19-build-decision-procedure.md) Scenario C; the
> gate ladder for a full build → [26](26-orchestration-and-testing.md); what the offline gates structurally
> cannot see → [23](23-distribution-and-known-gaps.md).

⚠️ **Status of this document.** The channel described in §2 exists today. The pieces marked **⏳ planned** in §5
and §6 do not exist yet — an MCP call for them will return "unknown tool". Where a row is ⏳, the only channel is
a re-import (§7), and you must say so in the hand-over rather than promising a live fix. This document is
versioned with the contract; check `CONTRACT-VERSION` in `system_prompt.txt` against the platform you are
attached to.

---

## 1. Which mode you are in, and who decides

Support mode is not a feeling about the task. It is a FILE, and you read it before anything else — before you
unpack a base, because the mode decides whether there is a base to unpack.

```
./.dokie/project.json
{
  "schema": "dokie.project/1",
  "generatedBy": "mrjun.py handoff emit",
  "mode": "support",                          // "build" | "support" — the human switch
  "project": { "name": …, "alias": …, "realm": …, "client": …,
               "locales": […], "defaultLocale": … },
  "paths":   { "export": "work", "library": "builder", "mrjun": "builder/tools/mrjun.py",
               "plan": "build-plan/plan.json", "caseNotes": "work-case",
               "packed": "project.mrjun" },
  "inventory": { … counted from the export itself: pages, rules, dynamicCruds, … },
  "plan":      { "items": …, "byKind": {…}, "byStatus": {…}, "withSelector": … }
}
```

⚠️ It records the MCP **url** when one is known, and **never a token**: the credential is registered with the
client, not with the folder (§2.2), so a copy of this file leaks nothing. And there is **no timestamp**, so
re-running the generator with nothing changed produces a byte-identical file and any diff means a real change.

`mrjun.py handoff emit` writes it, and rewrites it on every run, so it cannot drift from the folder it describes.
`mode` is the human switch: flip it by hand when a build becomes a maintained project.

**Two channels, and the mode picks which are open:**

| `mode` | token present | What you do |
|---|---|---|
| `build` | no | Today's contract, unchanged. Author files, gate offline, hand over two artifacts. |
| `build` | yes | Same, plus step 6b: import the finished export once, at the end. |
| `support` | no | Scenario C on files only. You produce a `.mrjun` the user imports. |
| `support` | yes | **Dual-write** — every change lands in the local export AND in the live project (§4). |

⛔ **`support` + no token is not a degraded support mode, it is a BUILD of a delta.** Do not pretend to support a
project you cannot read. Say plainly that without a token you can only produce an archive, and that importing it
REPLACES the project — including anything the customer changed in the UI since the last export.

---

## 2. The channel

### 2.1 What the token is, and what it is not

An MCP token is a signed statement of ONE project: it carries a realm and a client and nothing else. That is
why the contract lets you ask for a token but still forbids asking for a realm, a client, a URL or a login — the
token REPLACES those questions instead of adding to them.

What the token does **not** carry, and what follows from that:

* **No branch.** ⛔ See §2.4 — this is the single most dangerous property of the channel.
* **No scope.** Any valid token can call every tool the server advertises, including `delete_page`,
  `drop_table` and `execute_ddl`. Treat a token as owner-level access to that project, and never paste one into
  a file, a chat log, a commit or a bug report.
* **No expiry, unless the issuer set one.** A token that leaks stays valid until somebody revokes it by hand.

**How the user gets one, and why it cannot be automated:** minting requires an authenticated admin/author
session in the TARGET project — Settings → Developer → MCP tokens. There is no self-service path and there
cannot be one. Tell the user this precisely, once, and do not offer to do it for them.

### 2.2 Connecting — once per folder, and the folder owns it

**One folder is one project talking to one tenant.** A support engineer keeps several open at once, and
each must carry its own credential; a connection configured globally would make "which project am I about
to change" a question of memory. So the connection lives in `./.mcp.json`, which Claude Code reads only for
the directory it sits in — verified: a server declared there is invisible from every other folder.

If the file is absent, the session asks for it once, writes it, and stops:

```
<paste the block from Settings → Developer → MCP tokens>
    | python3 ./builder/tools/mrjun.py handoff mcp --project ./work
```

The command takes either block the panel offers and stores the canonical one. If you paste the
`npx mcp-remote` variant it is **unwrapped into the native HTTP transport**, because Claude Code speaks
HTTP to an MCP server itself and `mcp-remote` refuses a plain-http host that is not literally `localhost`
— it matches the string, not the resolved address, so a plain-http host named anything but `localhost` is rejected even when it
resolves to 127.0.0.1, and the failure surfaces only as `Connection closed`.

⚠️ **Then restart Claude Code once, in this folder, and approve the server.** MCP servers connect at
session start, so the session that wrote the file cannot use it. That is one restart per folder for its
whole life; every session afterwards is connected and must never ask for the configuration again.

⛔ **The credential is now IN the folder.** The file is mode 600 and git-ignored, but handing the folder to
someone else hands them the token. Give them a folder without it and let them paste their own — or, if the
folder must travel with a working connection, mint a token scoped to what they are allowed to do (§2.1) and
treat it as disclosed the moment it leaves your machine.

### 2.3 The surface you get

You are given the platform's whole tool list, which is large. Two rules keep it usable:

1. **Read before you write, always.** Every write tool addresses an object by an identifier you must first
   discover. Inventing one produces either a silent no-op or a new object beside the one you meant.
2. **The tool descriptions are not the shape spec.** A tool that takes a `model` or `settings` argument takes a
   large nested JSON document, and the tool description says `string`. The shape lives in this library —
   [14a](14a-plugin-config-reference.md) for plugin config, [02](02-form-controls-reference.md) for form
   controls, [11](11-business-logic-dynamic-crud.md) for dynamic CRUD. ⛔ Do not improvise a shape from a tool
   description; an invented key is dropped in silence and only the field it was meant to fill is empty.

### 2.4 ⛔ THE BRANCH TRAP — read this before your first write

The token names a project but not a branch, and **the platform's MCP surface has no working way to move off the
published branch**. `getActiveBranch` returns the PUBLISHED branch; `setActiveBranch` does not work. So:

> **Every write you make over MCP is live, immediately, for every user of that project. There is no draft, no
> review step and no undo.**

What that obliges you to do:

* **Announce it before the first write.** The user must know that "let's just try it" costs a production change.
* **Make one change at a time and read it back** (§4). A batch you cannot inspect is a batch you cannot revert.
* **Prefer a window the customer agrees to** for anything touching a page, a form or a rule people are using.
* If the platform you are attached to offers a `branch` claim on the token (a newer build may), ask for a token
  issued against a working branch instead, and say why.

---

## 3. What the folder looks like in support mode

```
<project folder>/
|-- builder/              the library, as always — READ-ONLY
|-- work/                 the unpacked export: STILL THE SOURCE OF TRUTH for shape (§4)
|-- work-case/            case notes: why this project is the way it is
|-- build-plan/plan.json  the coverage ledger, and where you tick a finished change
|-- .dokie/project.json   the mode and the coordinates (§1)
|-- CLAUDE.md             what a fresh session reads first
|-- project.mrjun         in support mode this is the AUDIT RECORD, not the deliverable
`-- test-scenarios.md
```

⚠️ **`CLAUDE.md` is merged with any `CLAUDE.md` in a PARENT directory.** If this folder was unpacked inside
another repository, that repository's instructions are in context too and may contradict these. `handoff emit`
warns when it finds one; if you see the warning, say so rather than silently obeying whichever won.

---

## 4. The dual-write protocol

**One order, and it is not negotiable:**

```
edit ./work  →  mrjun.py validate  →  ONE MCP write  →  read it back  →  tick the plan row
```

**Why this order.** `validate` is the only thing that catches the shape traps this library exists to document —
a settings mirror written as a string, a non-enum task type, malformed BPMN — and it can only see a change that
exists in a file. A change made live first has never been validated by anything. ⛔ Never write live and
back-fill the file afterwards: that is the one ordering under which a shape defect reaches production.

**One collection, one call, then read it back.** Partial success is the NORMAL outcome of a multi-object write,
not an edge case: the successes commit, the failures are reported, and there is no transaction and no undo. A
tool that reports per-object failures is telling you the truth — treat any partial result as *stop and report*,
never as *retry the whole payload*, which re-applies the half that already worked.

**The four ways it can go wrong:**

| | What you must do |
|---|---|
| local ok, live failed | The file is ahead of the platform. Do NOT keep going. Report which object failed and why; the per-object error names the object and the field. |
| local failed, live ok | Undetectable by any check. This is why the order above puts the file first — under it, this case cannot arise. |
| both failed | Safe. Fix and repeat. |
| **partially live** | The common case. Stop. Enumerate what landed and what did not, from the read-back — not from the request you sent. |

**Reconcile at both ends of the session.** Run the live/local comparison when you start (someone may have
changed the project in the UI since your last session) and again when you finish. A support session that never
compared is a session that does not know what it changed.

---

## 5. Which channel carries which object

| You need to change… | Channel | Status |
|---|---|---|
| A page, a plugin on a page, plugin properties, page/plugin access | MCP CMS tools | available |
| A Groovy rule (any of the three types) | MCP rule tools | available |
| A dynamic CRUD: methods, parameters, DTO/filter fields | MCP `bl` tools | available |
| Database structure (table, column, index, constraint, raw DDL) | MCP repository tools | available |
| A saved query | MCP query tools | available |
| A form or a form group (metadata, mappings) | MCP form tools | available |
| A workflow definition | MCP workflow tools | available, **but see the caveat below** |
| A scheduled job | MCP schedule tools | available |
| Users and role groups | MCP security tools | available |
| Whole-project import of a `.mrjun` | toolkit push + MCP import | ⏳ planned |
| Applying one rep-object collection as a delta | MCP `project.apply` | ⏳ planned |
| Uploading an image, a logo, a favicon, a PDF asset | — | ⏳ planned (re-import only) |
| A translation / a locale | — | ⏳ planned (re-import only) |
| A mail template | MCP messaging tools | available — but see §6: a re-IMPORT of templates is delete-all-then-insert, so never mix the two channels |
| A PDF template | — | **no channel** (§6) |

⚠️ **Workflow caveat.** A workflow written over MCP is saved as a DRAFT and is never deployed by the save. A
process whose definition you changed will keep running the old one until somebody presses Deploy. Say so
explicitly in the hand-over for every workflow you touch, and check the deployed state rather than assuming it.

---

## 6. ⛔ HONEST LIMITS — what this channel cannot carry

This section is the difference between support mode and a promise you cannot keep. Everything here still
requires a re-import (§7), and a re-import REPLACES the project.

* **PDF templates.** The service that owns them publishes no MCP surface at all. This is not a permission
  setting; there is nothing to call.
* **PDF templates and role groups** are written by delete-all-then-insert paths on the IMPORT side. Applying
  a partial list does not merge — it removes every other one.
* **Mail templates are the exception worth stating precisely**: they DO have live MCP tools
  (create/update/delete one template at a time), and that is the safe way to change one. What is unsafe is
  the import path, which replaces the whole set — including the system aliases the platform sends its own
  notifications with. So: edit a mail template live, never by re-importing a partial set.
* **Data sources.** An export deliberately carries a source WITHOUT its password, so a source restored from an
  archive cannot connect until someone re-enters the credential in the UI.
* **Project locales and tenant-level settings.** No tool reads or writes them. Adding a language is not possible
  over this channel.
* **Free-form enumerations** created live never round-trip into an export. There is no local half of them, so
  they cannot participate in a dual write at all — record them in a case note or they are lost at the next
  rebuild.
* **Bulk seed data.** There is no loader for the archive's data dump; only statement-by-statement SQL.
* **Workflow diagram geometry.** A workflow authored over MCP opens on an empty canvas in the platform's own
  modeler, even though it runs.
* **Anything a person changed in the UI** since the last export. The archive does not know about it, and a
  re-import destroys it silently.

⛔ **`DONE` is not proof.** An import can report success while every mail and PDF template silently failed —
those writers log a warning and never reach the failure report. After any import, verify the things the report
cannot see, and name them in the hand-over as unverified.

---

## 7. When a re-import is the only channel

Re-import is the LAST resort, not a shortcut, because it is a whole-project REPLACE: the project's objects are
deleted and rebuilt from the archive, and every UI-side change since the export goes with them.

Before doing it: take a snapshot first if the platform offers one; confirm the target project's type is the one
the archive expects (a mismatched type does not fail — it replaces every page and branch while importing none
of the rules and queries those pages reference); state the three business-logic choices explicitly rather than
accepting a default; and after it finishes, read the per-object report and then check the things §6 says the
report cannot see.

---

## 8. Finishing a support session

A support change is not a build, and the four-gate ladder of `system_prompt.txt` does not apply to it. The
ladder for one change is shorter and stricter:

1. `mrjun.py validate` on the workdir — no NEW findings against the baseline;
2. the live write returned per-object success, and you **read the object back** and saw your change;
3. the plan row is ticked, or a new row exists if the change was not in the plan;
4. a case note records WHY, in the user's own words — a support change with no recorded reason is a change the
   next session will undo;
5. the live/local comparison at the end of the session is clean, or you have named exactly where it is not.

Then hand over: what changed, in which project and on which branch, what you verified and what you could not,
which items from §6 were involved and therefore still need a human, and — if any workflow was touched — that it
needs Deploy.
