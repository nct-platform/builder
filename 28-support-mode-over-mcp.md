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

**Kill the approval prompt while you are there.** A server declared in `./.mcp.json` is *offered*, not
trusted: Claude Code parks it at `⏸ Pending approval` until a human approves it in an interactive start.
Pre-approve it by name in `./.claude/settings.local.json` (personal, git-ignored) so the restart asks
nothing:

```json
{ "enabledMcpjsonServers": ["<tenant-server-name>", "chrome-devtools"] }
```

`handoff mcp` / `handoff browser` write `./.mcp.json`; this file is the second half, and the two together
make the restart a single keystroke. (`enableAllProjectMcpServers: true` approves every server the folder
declares — blunter, and it auto-trusts anything added later.)

> ⛔ **The existing connection IS the channel — use it, do not re-negotiate it.** If `./.mcp.json` already
> names a server, the session's job is to CALL it. Never ask for a token that is already there, never
> re-run `handoff mcp` over a working config, and never offer a re-import (§7) as the "easier" route: a
> re-import REPLACES the project, and proposing it while a live channel exists is the single most expensive
> wrong turn in this mode.
>
> **When the tools are missing, say WHICH of the two states you are in — do not call the channel broken:**
> * **Configured but not attached** — no `mcp__<server>__*` tool exists in the session, and
>   `claude mcp list` prints `⏸ Pending approval` (or nothing) for it. Cause is almost always that
>   `.mcp.json` was written *during this very session*. Fix: the pre-approval above + one restart. The
>   config is correct; do not rewrite it, and do not re-ask the user for a token to "check" it.
> * **Attached but failing** — the tools exist and the CALL returns an error. Only then is it a channel
>   problem: read the per-object error (§4) and report it.
>
> **`connected` is not `usable` — check the TOOL LIST, not the status.** A server can complete `initialize`
> (so `claude mcp get` prints `✔ Connected` and the session's init event lists it as `connected`) and still
> advertise **zero tools**, which looks exactly like "not attached" from inside the session. Get the ground
> truth without guessing — the session's own init event:
>
> ```
> claude -p "hi" --output-format stream-json --verbose | head -3
> #   → system event: .mcp_servers[] (per-server status) and .tools[] (the REAL surface)
> ```
>
> If the server is `connected` but no `mcp__<server>__*` name appears in `.tools[]`, the channel is open and
> **empty**: nothing to call, and no amount of re-configuring the client changes it. That is a server-side
> matter (is the MCP surface published for this realm/client, does the token's subject carry the role that
> exposes it) — say so plainly instead of retrying the connection, and fall back to §7 or to the browser
> channel (§8). Transport is worth one check while you are there: this platform speaks streamable **http**
> at `/mcp/rpc`; registering the same URL as `sse` fails to connect outright.

> ⛔ **Raw HTTP to the MCP URL is NOT a fallback.** These endpoints commonly sit behind a WAF that answers
> anything without a browser-shaped user-agent with `403 Cloudflare 1010 browser_signature_banned` — a
> `curl`/`urllib` probe proves nothing about the token, and forging a user-agent to get around the block is
> out of bounds. The platform's own MCP client is the only sanctioned caller: if it is not attached, attach
> it (above) rather than hand-rolling JSON-RPC.

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

## 8. Live test — driving the running project in a real browser

The MCP channel reads and writes OBJECTS. It cannot tell you whether the thing a person opens actually
works: a page can hold a perfectly-shaped plugin and still render empty, a rule can be valid Groovy and
still deny everyone, a workflow can be deployed and still strand a claimed row. Every one of those passes
`validate` and every one of them is a bug the user finds first. So a support session gets a second channel —
a real browser, driven by you — and the two together are the only way to say "fixed" and mean it.

⛔ **This is an OFFER, not a default.** Driving the live project performs real actions on a running tenant.
Propose it, say what it will do, and wait for a yes:

> *"I can test this live: I'll drive the running project in a browser, work through the scenarios, and fix
> what I find over MCP. It will create test records — and test roles if the scenarios need them — in the
> real project. Want me to?"*

### 8.1 The second server, and installing what is missing

The tenant connection (§2.2) and the browser driver are two different servers in the same `./.mcp.json`.
Add the driver with:

```
python3 ./builder/tools/mrjun.py handoff browser --project ./work
```

It merges — it never rewrites the file — so the tenant connection survives, and so does the driver when a
token is later re-pasted. If `node`/`npx` are missing the command says so and prints the line that fixes
it; **run that line yourself and re-run the command.** Installing the driver is part of the job, not a
question for the user. Then ⚠️ **restart Claude Code once** — MCP servers connect at session start, so the
session that wrote the file cannot use it.

### 8.2 Where to test, and ⛔ who logs in

**Open the PROJECT, not the installation.** The platform serves every project under
`<root>/<realm>/<client>` — `http://host:8077/saas/ardshin2`. Opening the bare root instead bounces to the
login form and leaves you on `…/auth;jsessionid=…`: a URL that loads, renders none of this project, and
looks enough like a working page to be reported as one.

You are not supposed to ask for that address if you can work it out, and usually you can:

| what | where it comes from |
|---|---|
| `realm`, `client` | the **MCP token's own claims** — decoded, not verified, because this is addressing and not authorization. Failing that, `.dokie/project.json`, failing that the export |
| the root `http://host:port` | ⛔ the only part nobody can derive. The MCP endpoint is a DIFFERENT service on a different port, so it does not tell you where the UI is |

So: if `.dokie/project.json` already records `project.liveUrl`, use it and **ask nothing**. If not, ask once
for the origin and record it, so no later session in this folder asks again:

```
python3 ./builder/tools/mrjun.py handoff emit --project ./work --base-url http://<host>:<port>
```

`handoff browser` prints the resolved address, or says exactly which half is missing. It also compares the
coordinates in the token against the ones the folder records and ⛔ **stops you on a mismatch** — the writes
travel on the token, so a folder mirroring one project while its token names another is a session verifying
a fix here and applying it there.

**Then the login: you must never type a password, and never ask for one in the chat.** Not the author's,
not a test user's, not one the user offers unprompted. Instead:

1. open the project's URL in the browser you drive;
2. ask the user to **log in themselves, in that window, as a user holding the author role**;
3. wait for them to confirm, then verify by reading the page — the authoring affordances are visible or
   they are not;
4. from that point on you are driving an already-authenticated session, which is all you ever needed.

This is not a formality that costs a turn. A credential typed into a tool call is in the transcript, and a
transcript is copied, summarised and stored. Asking the human to authenticate keeps every secret in the one
place that already holds it — their browser.

### 8.3 Why the author user comes first

Ask for **author** specifically, before anything else, because the author role is the one that can create
roles. With it you can build every other identity the scenarios need; without it you are stuck one step
into the first scenario, having already spent the setup.

Once you are in as an author, you create the rest yourself — role groups, test users, their assignments —
through the platform's own MCP tools, and you do not ask again.

⛔ **Everything you create is real and stays there.** So:

* give every test identity a name that says what it is and who made it — `zz-test-<role>` — so a human
  scanning the project's users a month later knows instantly what they are looking at;
* keep a list as you go, and hand it over at the end (§9) — what you created, and whether it can be deleted;
* never repurpose a REAL user for a test, and never change a real user's roles to make a scenario pass.
  That is not a test result, it is a production change wearing one.

### 8.4 The scenario file and the plan

The scenarios live where the rest of the run log lives — the working folder of
[26](26-orchestration-and-testing.md) §6, beside the workdir, never inside it:

```
build-plan/
  test-scenarios.md   # INPUT  — what a person is supposed to be able to do, in their words
  test-report.md      # OUTPUT — what you drove, what you saw, what you fixed
  plan.json           # the coverage ledger; a scenario that fails becomes a row
```

If `test-scenarios.md` does not exist, **write it before you drive anything**, from the plan rows and the
case notes, and show it to the user. A scenario is one sentence of intent plus the role it is performed as:

```
- [Initiator]        raise a procurement request, save it as a draft, and see it in my worklist
- [ProcurementAdmin] open that request, approve it, and see the status change
- [Initiator]        try to approve my own request — and be refused
```

That last shape matters as much as the first two. **A scenario set with no negative cases cannot detect a
permission bug** — it only ever proves that the people who should get in, get in.

⛔ **You decide the plan, and you write it down before driving.** Nobody hands you an ordered list of
checks. Order the scenarios so that each one leaves the project in a state the next one can use, put the
cheapest disproof first, and say in one line why that order. A plan invented mid-drive is a plan nobody can
review and you cannot re-run identically after a fix.

### 8.5 The loop

For each scenario, in the order you chose:

1. **Drive it** as the role it names, through the UI, exactly as a person would.
2. **Observe** — and observe the right thing. What the page renders is the finding; what the log says is
   the cause. Read both, because a button that does not appear and a button that appears and fails are two
   different bugs with two different fixes.
3. **Record it before fixing it.** A finding written down after the fix is a finding shaped by the fix. One
   row per finding in `test-report.md`: the scenario, the role, what you expected, what happened, and the
   evidence — the log line, not your reading of it.
4. **Fix it over MCP**, under the rules that already govern every support change: one change at a time, the
   local export edited too (§4), `validate` before the live write, and **read the object back** (§2.3).
   ⛔ If the fix belongs to §6 — a PDF template, a project locale, seed data — there is NO live channel:
   record it, say so, and move on rather than half-fixing it.
5. **Re-drive the SAME scenario**, whole, from its start. Not the one step you touched. A fix that repairs
   the step and breaks the one before it is the ordinary case, not the exotic one.
6. **Re-drive the scenarios that already passed** whenever a fix touched anything shared — a rule, a role
   group, a workflow. Cheap to do, and it is the only thing that catches a repair that broke a neighbour.

Stop when every scenario passes or when what remains is recorded and named. ⛔ **Never report a scenario as
passing because its fix was applied.** Applied is not verified. Only a re-drive that you watched counts,
and if you could not re-drive it, that is what the report says.

### 8.6 ⛔ What you must not drive on a live tenant

* **Anything irreversible against records you did not create** — deleting, approving, rejecting, sending.
  Real rows belong to real people. Create your own and act on those.
* **Anything that sends** — mail, notifications, integrations that call outward. A test run that emails a
  real customer is not a test. Check what a workflow node does before you trigger it, not after.
* **Bulk actions**, even on your own rows. One at a time is slower and is the only version you can undo.
* **A destructive scenario on a project the user is demonstrating from.** Ask which project you are on
  before the first write if there is any doubt — see the mode and coordinates in `.dokie/project.json` (§1).

### 8.7 When the browser is not enough

Some failures are invisible from the UI and visible instantly in the platform's own logs — a denied role
check, a silently dropped field, a rule that threw and was swallowed. If the session has access to the
service logs, read them; if it does not, say what you would have looked for. ⛔ Do not infer a cause from
the rendered page alone and then fix on that inference. A guess that happens to fix the symptom leaves the
cause in place, and it comes back in the next scenario as something that looks unrelated.

---

## 9. Finishing a support session

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

If the session drove a live test (§8), the hand-over carries three more things, and they are the ones a
person cannot reconstruct from the diff:

* **the scenario outcome** — which scenarios passed on a re-drive you watched, which failed, and which you
  never got to. ⛔ "Fix applied" is not an outcome; only a re-drive is;
* **what you created in the live project** — every `zz-test-*` role group, user and record, and whether it
  is safe to delete. A test identity nobody knows about is a permission hole nobody is looking for;
* **findings you did NOT fix**, each with its evidence and why — no live channel (§6), out of scope, or
  needing a decision that is not yours.
