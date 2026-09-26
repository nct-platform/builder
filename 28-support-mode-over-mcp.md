# 28 · Support mode — changing a LIVE project over MCP

> ⛔ **`identifier` or `uniqueIdentifier`?** They are different ids with different scopes and swapping them fails silently. The rule, the source that decides it and the measured evidence: [01 — `identifier` vs `uniqueIdentifier`](01-content-model-and-pages.md#-identifier-vs-uniqueidentifier--read-this-before-you-reference-a-node).

> 📐 **Field evidence — what a delivered project looks like when you inherit it:** [README.md](references/README.md). Measured across four delivered projects, domain removed; it says which of this doc's options production chose, and where it contradicted them.

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

**Make the mirror a GATE, not a habit.** "Edit the file first" is the right order and it still fails,
because a live write is sometimes the only way to *test* a fix (a seeded default, a generated label, a
gesture) and the mirror then gets deferred "until the file is free" — and forgotten. Every gate stays green
while it is missing: `validate`, `crud verify` and `pack` check the archive's internal consistency, not
whether it agrees with the running tenant. The cheap mechanism that actually holds:

* keep a **registry** beside the export — one line per live change, with a marker string that must be
  findable in `work/` (a rule name + a distinctive fragment of its body, a settings key, a node id);
* a **checker** that greps the archive for every marker and exits non-zero on the first miss;
* run it **before every `pack`**, and treat red exactly like a failed test: do not pack, do not import.

A session that ran this check at the end found two rule fixes and a scheduler identity that existed only
on the tenant and would have been erased by the next import — with every other gate green.

**Reconcile at both ends of the session.** Run the live/local comparison when you start (someone may have
changed the project in the UI since your last session) and again when you finish. A support session that never
compared is a session that does not know what it changed.

### 4a. Table plugins keep their settings in TWO places — and only one of them is the answer

A CRUD Table, a CRUD Tree, a Process Table and a Calendar each carry their configuration twice:

* on the plugin's **content node**, as its `model` property — this is the one that is per-branch, the one the
  `.mrjun` carries, and **the one the running page renders from**;
* as a flat **settings row** keyed by that node's unique identifier — which is what lets a *different service*
  look the configuration up by identifier (the workflow service resolves a Process Table that way).

**The content is the source of truth. The row is its projection.** It has to be that way round: the row's key
has no branch in it, so a draft branch and the published branch address the same row — were the row
authoritative, editing a table on a draft would change the live page the instant you saved.

**What this means for you.** Writing the plugin's properties is the whole write; the projection is refreshed
for you. You do not write the row, and you must never try to "fix" a disagreement by writing it directly.

**The symptom this replaces.** There was a window in which writing a plugin's properties updated the content
alone. The table then rendered the new configuration — a money column formatted as money — above a settings
panel that still showed the old one, with the checkbox unticked. Worse, the panel autosaves: one touch of any
field in it wrote the panel's stale copy back over both stores and silently undid the change. If you are
working against an older platform build and see exactly that split, do not re-write the properties in a loop.
Open the plugin's settings panel once and save it — that republishes both stores from one model — then verify
and report the build as needing the fix.

**Read-back.** Read the property back from the plugin, which is the authoritative store. A read that goes to
the row is reading a copy, and on an old build a copy that may lag.

---

### 4b. Four write tools that do not do what their name suggests

**`nct_repository_execute_ddl` is also the DATA-repair channel.** `execute_query` cannot write — it wraps
your statement for paging, so an INSERT there is a syntax error. The DDL tool passes its text straight to
the driver, which runs `DELETE FROM orders` as readily as `ALTER TABLE`. It now asks before it does:

* a row-changing statement (INSERT/UPDATE/DELETE/MERGE/TRUNCATE/COPY, or a `DO`/`CALL` block) is refused
  unless you pass `allowDataChange: true`;
* one with no top-level `WHERE` — i.e. one that hits every row it can reach — needs
  `allowUnfilteredDataChange: true` as well. A `WHERE` inside a subquery does not bound the outer statement
  and does not count;
* the response reports `affectedRows`, so "it worked" is a number and not a fixed string;
* a row change is deliberately NOT written to the schema changelog: it changed rows, not structure.

Remember what a data source can be. It may point at a customer's own database on a customer's own server.
Ask for the narrowest statement that does the repair, and read the affected-row count back.

**`nct_form_update` REPLACES its list fields.** Sending `validators: ["amountCheck"]` to *add* one used to
leave the form with that one validator and silently delete the others. Replace is still the default — it is
the only way to clear a list — but you can now say what you mean with `listMode: "add"` or
`listMode: "remove"`, and the response echoes the resulting lists and names anything the write removed.
Read that summary; it is the only place a loss shows up.

**`nct_ui_create_page` creates a page with NOTHING IN IT.** `layoutName` writes the layout's NAME onto the
page and builds nothing: the shell is cloned in lazily, by the browser, the first time a human opens that
page. Until that happens the page has no parsis and no body root, so `nct_ui_add_plugin` has nothing to add
to, `nct_ui_find_body_root` finds nothing, and `nct_ui_get_page_detail` shows a page with no children —
which reads like the create failed, and it did not. Over MCP, follow every `create_page` with
`nct_ui_apply_layout_to_page`, which clones the shell in up front (§5b — and read there what that still
does not give you). `nct_ui_update_page {layoutName}` has the
same shape and a worse failure: on a page that is ALREADY built it changes the stored name and nothing else,
so the page keeps rendering the old shell and the tool reports success.

**`nct_ui_set_page_access` PATCHES, and can now be verified.** It leaves roles, groups and flags you did not
mention exactly as they were, and the response carries `ownRoleAccess` — the page's full configuration after
the write. `nct_ui_get_page_detail` returns the same field. Note the name: it is the page's OWN config. What
a visitor can actually reach is that intersected with every ancestor section's access, so a page granted to
a role inside a section that is not granted stays invisible.

---

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
| The project's global JavaScript / CSS (loaded on every page) | MCP `nct_globalresource_*` tools | available — see §5a |
| A page LAYOUT — the shell a page renders into, and building a page from one | MCP `nct_ui_*_layout*` tools | available — see §5b |
| A mail template | MCP messaging tools | available — but see §6: a re-IMPORT of templates is delete-all-then-insert, so never mix the two channels |
| A PDF template | — | **no channel** (§6) |


### 5a. The project's own files — `nct_globalresource_*`

The tools describe themselves: `tools/list` gives you their names, what each is for and when NOT to reach for
one. Nothing about them is repeated here. What follows is only what a tool description cannot tell you.

All of them take `branchId` — call `nct_branch_getActive` first. What the switches actually mean, and the
offline half of the same object, is [29-global-resources.md](29-global-resources.md).

**ONE tree holds everything** — scripts, stylesheets, HTML fragments, fonts, images — because that is the
only arrangement in which a stylesheet's relative `url(../fonts/kit.woff2)` resolves.
`nct_globalresource_settings`, `_rename` and `_delete` take an `id` that may name a FILE or a FOLDER and tell
you which it turned out to be; that is not a shortcut, it is the same tree the screen shows.

⛔ **Four things this channel does not do, or does differently from what you would assume.**

* **Creating a file does NOT switch it on.** Everything arrives switched off, here and in the screen and in the
  toolkit. A create followed by no `nct_globalresource_settings {enabled:true}` is a file nobody loads, and the
  create's own summary says so. That is deliberate: an import or a tool call must never change what a live
  site serves without somebody choosing it.
* **Only a script or a stylesheet has a switch at all.** An HTML fragment, a font and an image are stored,
  served and editable, and never loaded on their own — something has to fetch them by URL.
  `nct_globalresource_settings {enabled:…}` on one is refused with a sentence, not ignored.
* **No archive upload.** There is no `add-zip` over MCP: unpacking one has real traps (entry and size caps,
  path sanitising, dependency ordering) and they live in the upload screen and in the toolkit's
  `globalresource add-zip`, where they are exercised. Over MCP you write source. A library you were going to
  vendor as a zip is one create per file in dependency order — you are choosing that order yourself, and
  `nct_globalresource_move` is how you correct it.
* **A change needs a page RELOAD to show.** The include happens when a page is rendered; an ajax panel update
  does not re-run it. Say so in the hand-over, the same way you do for a workflow that needs a Deploy.

💡 **`nct_globalresource_suggest` before you hand anything over.** With no `assetId` it audits everything
currently switched on and answers the question you cannot answer by reading: a script that uses a global
nothing switched-on publishes, a folder switched off above a file that is ticked, a library ordered after the
plugin that needs it. All three fail in the browser and look perfectly fine in a listing.

⚠️ **The branch you write is the branch you are on.** These live on the branch, like content — so a file
created against a draft is not on the published site until that branch is published, and a branch publish
REBUILDS the published branch from the draft. §2.4's branch trap applies here unchanged.

### 5b. Page layouts — `nct_ui_*_layout*`

A layout is the SHELL a page renders into: the header, the left nav, the breadcrumb, the footer, and one slot
the page's own content goes in. The model behind it — a named virtual plugin holding one HTML string with
`<plugin>` tags — is [01](01-content-model-and-pages.md); read it before you write a shell by hand. What
follows is only what the tool descriptions cannot tell you.

`nct_ui_all_layouts` lists them with how many pages name each; `nct_ui_get_layout` gives you one in full —
the HTML, the `<plugin>` tags it places, and the pages on it. Read one before you edit one.

⛔ **Building a page is TWO steps, and only the first one is yours.** `nct_ui_apply_layout_to_page` clones the
layout's shell into the page immediately. The shell's own `<plugin>` slots — the header, the nav, and the
`nct.parsis.plugin` that page content goes into — are still only text inside the shell's `html` until the
RENDERER turns them into nodes, and it does that when the page is first opened. So straight after the call
`nct_ui_find_body_root` still finds nothing and `nct_ui_add_plugin` still has no parsis to address. Open the
page once in a browser (§8) and both start working. What the tool removes is the page having no tree at all —
not the visit.

⚠️ **A freshly built page looks half-empty, and that is NOT your doing.** Its nav renders blank and its logo
renders as a placeholder, because those slots carry per-node configuration (`modelGroups`, the image URL)
that an author fills in per page — a brand-new copy starts empty. Measured on a live project against a
control page built the lazy way: the two are byte-identical. Do not go hunting for a layout bug here.

⛔ **A page NAMES its layout. It does not follow it.** Applying a layout COPIES the shell into the page, and
from then on the page owns that copy. So:

* Editing a layout's HTML changes what pages built **from now on** look like. The forty pages already built
  keep the shell they were given and do not move. "Used by 40 pages" in the tool output is not the blast
  radius of an HTML edit — it is who breaks if you RENAME or DELETE it.
* The only way a new shell reaches a page that already exists is `nct_ui_apply_layout_to_page` with
  `replace: true`, and that **discards that page's content** before rebuilding it. On a page with authored
  content, that is a destructive operation with no undo (§2.4) — say so before you run it, and re-add the
  content yourself afterwards.

⛔ **Renaming and deleting are therefore not ordinary edits.** A page whose layout name no longer resolves
renders as an EMPTY page — not "a page missing its header", an empty one, because the header, the nav and the
footer all come from the shell too. ⚠️ Check that as a VISITOR: an author still sees the authoring toolbar,
which is the platform's own and not the page's, and that alone is enough to make a dead page look alive.

The tools stand in the way of both halves: `nct_ui_update_layout` repoints every page that named the old name
and reports the count, and `nct_ui_delete_layout` refuses while pages still name it and lists them
(`force: true` overrides, and then says which pages it stranded). Neither guard exists in the Settings
screen, so a layout renamed there may already have left pages behind — `nct_ui_all_layouts` plus a page
listing is how you find them.

⚠️ **`isLayout` is not a reliable marker, and it leaks into these tools.** [01](01-content-model-and-pages.md)
records it: the stock "Nct layout" that many pages render into has `isLayout=false`, and only `Main` and
`Form` carry the flag. `nct_ui_all_layouts`, `_get_layout`, `_update_layout` and `_delete_layout` address
FLAGGED layouts only, while the renderer — and `nct_ui_apply_layout_to_page` — resolve a name across every
virtual plugin of the branch. So a page can legitimately name a shell that `nct_ui_all_layouts` does not
list. If a page's layout is one you cannot find, look in `nct_ui_list_virtual_plugins` before concluding it
is stranded; you can still apply it by name, you just cannot edit it as a layout.

⚠️ **A shell with no `nct.parsis.plugin` is not broken.** That slot is what an author's own plugins go into,
and `nct_ui_add_plugin` needs it — but a form page or a report page puts a form or a report plugin there
instead and has nothing free to add, on purpose. The shipped "Form" starter and the stock "Pdf" layout are
both like that. The tools say which kind you are holding rather than refusing to save it; decide which one
the requirement means.

💡 **Use `nct_ui_create_layout`, not the generic virtual-plugin tools.** Before these tools existed the only
route was `create_virtual_plugin {isLayout:true}` followed by `set_virtual_plugin_root_properties {html}`,
and it produces a layout that is subtly wrong in two ways nothing tells you about: the wrong plugin type on
the shell node, and no site template on the virtual plugin — and THAT one is dereferenced for every virtual
plugin of the branch by the plugin picker, so one bad layout takes that screen down for the whole project.
`nct_ui_create_layout` takes `html`, or `templateName` from `nct_ui_list_layout_templates` to start from a
shipped shell.

⚠️ **The branch trap (§2.4) applies unchanged.** A layout edit is live for every user of the project the
moment it lands, and a `replace: true` rebuild is live and irreversible.

> **Per build.** These tools are newer than the CMS tools around them. Check `tools/list` for
> `nct_ui_apply_layout_to_page` before you plan around it; on a build without them, creating a usable page
> over MCP ends at "the customer must open it once in a browser", and that belongs in the hand-over.

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

## 6b. Writing DATA over MCP — the temp-method pattern

`nct_repository_execute_query` and `nct_repository_execute_ddl` both wrap the statement in a SELECT, so
neither can run an `UPDATE`/`INSERT`/`DELETE`. The only write channel is a **throwaway SQL method on the
relevant CRUD**: add it → execute it → delete it. Use it for data repairs the UI has no screen for (fixing a
seeded jsonb, clearing a stuck flag, backfilling a column); never leave one behind — a temp method that
survives the session becomes an unaudited write endpoint on a delivered project, and `validate` will flag it
as an orphan on the next pack.

Four facts about that pattern, each of which costs a failed execution to rediscover:

1. **`nct_bl_addSqlMethod` silently DROPS any parameters in the method DTO.** One `nct_bl_addParameter` call
   per `:placeholder`, or the very first execution dies with "No value specified for parameter 1" before the
   SQL is even parsed.
2. **`parameterOrder` IS the JDBC slot index**, not a display order. Edit the script to drop a placeholder and
   the stale parameter left behind shifts every binding after it — the symptom is a complaint about a slot
   number higher than the number of placeholders you can see.
3. **The binder infers the SQL type from the parameter NAME when it matches a column.** A scratch parameter
   called `technology_id` binds as `uuid` and rejects `""` with "Invalid UUID string" no matter what
   `parameterType` says. Name scratch parameters something no column is called (`go`, `confirm`).
4. **`nct_crud_executeMethod` takes `parameters` as a positional LIST of plain values** — `["yes"]`. A
   name/value map raises `LinkedHashMap cannot be cast to List`; a list of `{name,value}` objects binds the
   whole object and fails on the cast.

And the trap that hides inside the SQL itself: a literal `?` is a bind marker, so Postgres' jsonb existence
operators cannot appear in a method script at all — see [11](11-business-logic-dynamic-crud.md) §Gotchas for
the rewrites.

### ⛔ A GROOVY method's real code is a hidden DELEGATE rule — `updateMethod` does not touch it

A dynamic CRUD's GROOVY method executes through an auto-generated hidden rule named
`crud_<alias>_<method>`. `nct_bl_updateMethod` writes the METHOD record; the delegate keeps the
old body and keeps running it. The method reads back with the new script, a method-level diff is
clean, and nothing about the behaviour changes.

The symptom is deceptive: after "fixing" `technology.copyVersion` to carry four more fields, the
new rows came out with those four null while the fields the OLD code already passed landed fine —
which reads as "the executor ignores some parameters", not "the wrong code is running".

    method    crud_technology_copyVersion   3438 chars, has the fix
    delegate  crud_technology_copyVersion   2919 chars, does NOT               <- this one runs

So for a GROOVY method: **write the delegate rule too** (script goes in `executor`, see the trap
above), and verify by EXECUTING the method and checking its output — a read-back of the method
cannot see this. `nct_rule_findAll` needs `includeHidden: true` to list delegates at all.

SQL methods are unaffected: they carry their statement on the method record itself.

### ⛔ `nct_workflow_addElement` STRIPS `flowable:rule` from every existing serviceTask

Editing a workflow's elements over MCP does not edit the deployed definition — it creates a new
workflow VERSION and leaves the running one untouched. That is the good news, and it is the undo:
`nct_workflow_deploy` on the **pre-edit version id** overwrites the draft with the old content.

The bad news is what the serializer does on the way. Adding one SERVICE_TASK to a definition whose
rules are in the attribute form (`flowable:rule="<identifier>"`) produced:

    Bind technology      NO RULE AT ALL          <- existing
    Refresh technology   NO RULE AT ALL          <- existing
    Release version      NO RULE AT ALL          <- existing
    Return for revision  <extensionElements><flowable:rule>…   <- the one just added

The existing tasks' rules are not migrated to the extension form; they are **dropped**. Deploy that
version and every service task in the process becomes a no-op — silently, because a serviceTask
with no rule is still valid BPMN and `validateDefinition` passes it.

**Use `nct_workflow_import` instead.** It takes a complete BPMN document and replaces the definition
wholesale, so nothing is re-serialized and nothing is dropped:

    nct_workflow_export(workflowId)          -> the current XML
    ... edit the XML ...
    nct_workflow_import(workflowId, bpmnXml) -> a new version, NOT deployed
    nct_workflow_deploy(workflowId)          -> when you are ready

Three things it does that make it safe to hand to an agent:

- it **validates before writing** — a definition that fails validation leaves the stored one untouched;
- it **never deploys**, so the engine keeps running the previous deployment until you say otherwise;
- it **refuses to change the `<process id>`** unless you pass `allowProcessIdChange=true`, because running
  instances are bound to the id they started under.

And it answers with every service task and where its rule lives — `ruleSource: "attribute"` is the
form the runtime resolves; `"extensionElements"` and `"none"` both **fail loudly at runtime**, not
quietly. From the extension form the element extractor stores the list's `toString()` as the rule id,
the executor is handed that garbage and throws; with no rule at all it throws "No rule ID provided in
task configuration". Either way the exception rolls back the transaction that completed the preceding
user task — so that task reopens, and keeps reopening. That makes the import its own check on the
defect above.

⚠️ And between the edit and the rollback the workflow lists as **`deployed: false`** while the
engine is still running the previous deployment. One click on Deploy in that window ships the
rule-less definition.

So: **the element API cannot carry a change to a rule-bearing process.** If you must try it anyway,
(1) export and keep the pre-edit XML, (2) note the pre-edit version id, (3) after the edit export
the new version and check EVERY serviceTask still carries its rule, and (4) deploy the old version
id to undo. A BPMN change to a process whose service tasks call rules needs a re-import.

### ⛔ Which field carries the Groovy is PER TOOL and PER BUILD — verify it, never assume it

**`create` and `update` do not agree, and the disagreement is silent either way.**
`nct_rule_create`'s own tool description says the Groovy goes in **`executor`**. On the 2026-09
build, `nct_rule_update` takes it in **`rule.ruleScriptStr`** and leaves `executor` as the class
name — six rules were rewritten that way in one session, each read back byte-for-byte and each
changed live behaviour (a screen gesture appeared, two dead buttons started working, a generated
label changed). The asymmetry documented below was observed on an earlier build.

**So the rule is: establish the shape on the build in front of you, with one cheap probe, before you
touch anything that matters.** Pick a rule you own, add a comment line, write it, read it back, and
compare the whole body. If the body came back as the 19-character string `GroovyExecutionRule`, the
build is the one described below and you have just destroyed that rule — restore it from `work/` and
switch fields. Both failures are invisible in the tool's own response: `success: true` either way.

**Whichever field it turns out to be, never echo `executor` back from a read into a write.** That is
the single habit that makes the asymmetry harmful; a payload you build from named fields cannot have
it.

### ⛔ (earlier build) `nct_rule_update`: `executor` is ASYMMETRIC — read-modify-write DESTROYS the rule

On READ, `nct_rule_findByIdentifier` returns the Groovy source in `rule.ruleScriptStr` and puts the
**executor class name** in `executor` (`"GroovyExecutionRule"`). On WRITE, `nct_rule_update` reads the
Groovy source **from `executor`** and ignores `rule.ruleScriptStr` entirely. The two ends of the same
field mean different things.

So the natural, careful-looking pattern — fetch the rule, change one line, send it back — silently
replaces the rule's entire body with the literal string `GroovyExecutionRule`:

```python
live = findByIdentifier(ident)          # executor == "GroovyExecutionRule"
live['rule']['ruleScriptStr'] = newCode # ...ignored on write
update(rule=live)                       # -> body is now the 19-character class name
```

`update` returns **success: true**. Nothing errors, nothing logs, and the rule is destroyed. Write it
the other way round, and never echo `executor` back from a read:

```python
payload = {k: live[k] for k in ('id','name','identifier','ruleType','contextIdentifiers','description','status')}
payload['executor'] = newCode           # the Groovy source goes HERE on write
update(rule=payload)
```

**Always read back after a rule write**, and compare against what you sent — this failure is invisible
in the tool's own response. A cheap tripwire over the whole set: fetch every rule and flag any whose
live script is a few dozen characters while the archive's is hundreds; a corrupted body is always short.


⚠️ A data repair made this way lands ONLY in the live tenant. The archive's `project-db.dump` carries the same
defect until you fix it there too, or the next re-import silently reinstates it. Fix both, in the §4 order.

---

## 7. When a re-import is the only channel

Re-import is the LAST resort, not a shortcut, because it is a whole-project REPLACE: the project's objects are
deleted and rebuilt from the archive, and every UI-side change since the export goes with them.

Before doing it: take a snapshot first if the platform offers one; confirm the target project's type is the one
the archive expects (a mismatched type does not fail — it replaces every page and branch while importing none
of the rules and queries those pages reference); **set the dialog's switches explicitly rather than accepting
their defaults** — the four of them, their labels and what each one costs are in
[00](00-export-format-and-import.md) §The four switches, and the one that decides whether a SCHEMA change
arrives at all defaults to OFF; and after it finishes, read the per-object report, deploy every workflow again
(they all come back undeployed), and then check the things §6 says the report cannot see.

---

### ⛔ Import/Export is hidden until the session is in AUTHOR MODE

`Settings → Import/Export` is the only channel for everything MCP cannot reach (PDF and mail
template text, project locales, seed rows in `project-db.dump`). It is also **missing from the
Settings menu most of the time**, and its absence looks exactly like a missing privilege:

```
Settings · Branding · Template Management · General · Localization ·
Integrations · Zombie Integrations · Appearance            <- what you normally see
```

versus

```
Settings · Branding · Import/Export · Layout · Accesses · Template Management ·
General · Localization · Integrations · Zombie Integrations · Appearance · Developer
```

The four that come and go — **Import/Export, Layout, Accesses, Developer** — are gated on
**author mode**, a per-session toggle, not on a role group:

> top bar → **Կայք / Site** dropdown → **«Ես հեղինակ եմ» / "I am the author"**

Turn it on and the four items appear immediately; the page does not even reload. It is a
*different* switch from **«Խմբագրել կայքը» / "Edit site"** in the same dropdown — edit mode
gives you the page editor and the left-nav editor, and having it on does **not** bring
Import/Export back.

**Why this costs time.** The toggle resets — a fresh login, and seemingly an import, drop the
session out of author mode. The next visit to Settings then shows the short menu, and the
natural reading is "this account lost `PROJECT_EDIT`, I need to grant it a role group". On a
project whose `Administrator` persona carries the platform `ADMIN` role, acting on that reading
hands the author account privileges it must never have (see `24-role-matrix-and-admin-page-hardening`
in a project's own case notes for how that plays out). **Flip author mode first; only then
suspect roles.**

Do not confuse the three things the top bar offers:

| Control | Where | What it gates |
|---|---|---|
| «Ես հեղինակ եմ» | Site dropdown | Import/Export, Layout, Accesses, Developer in Settings |
| «Խմբագրել կայքը» | Site dropdown | the page editor + the left-nav (kicker) editor |
| branch pill (`Արտադրական`…) | top bar, right | which branch the editors write to |

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

### 8.0 ⛔ The order of the first three questions — ask, then connect, then restart

Everything below costs the user something: real records in a running tenant, a token pasted, a session
restarted. So the session does not begin by wiring anything. It begins by asking, and it asks in this
order, one step at a time — never all three at once, and never the second before the first is answered.

**1. Does the user want a live test at all?** One question, with the cost in it:

> *"Before I change anything else — do you want me to test this live? I would drive the running project
> in a browser, work through the scenarios end to end, and fix what I find. It creates real records in
> the real tenant (documents, and test roles if the scenarios need them). Yes or no — if no, I stay
> offline and you get the findings from the export alone."*

A **no** is a complete answer. Offline work still has `validate`, `crud verify --db` and `coverage`, and
the hand-over then says plainly which claims were never opened in a browser. Do not re-ask later in the
session, and do not smuggle the test in as "just checking one page".

**2. Only after a yes — ask for the credentials.** Ask for exactly what §2.2 needs and nothing more:

> *"Then I need the MCP block for this tenant: Settings → Developer → MCP tokens → copy the block.
> Paste it here and I'll wire it into this folder's own config."*

Then wire it yourself — the user pastes, you configure:

```
<the pasted block> | python3 ./builder/tools/mrjun.py handoff mcp --project ./work
python3 ./builder/tools/mrjun.py handoff browser --project ./work      # the browser driver
```

⛔ **The token belongs in the CLIENT's per-folder config, never in a file you commit.** `handoff mcp`
writes `./.mcp.json`, which is git-ignored for exactly this reason — check that it is, and if the project
keeps its config elsewhere (`claude mcp add --scope local`), use that instead. A token pasted into a note,
a case file, a commit message or a reply is a leak, and it is a leak even in a private repo. If the user
pastes a token into the chat, use it, wire it, and do not repeat it back.

**3. Then tell the user to restart — and say why.** MCP servers connect at session start, so the session
that writes the config can never use it. The sentence has to be unambiguous, because an unrestarted
session looks exactly like a broken token:

> *"Configured. Now quit Claude (Ctrl-C twice, or `/exit`) and start it again in this same folder — MCP
> servers only connect at startup, so this session cannot see the one it just created. When you're back,
> say «continue» and I'll start the live test."*

Pre-approve the servers first (§2.2) so the restart asks nothing. Then **stop**. Do not keep working in
the dead session: anything you do there has to be re-verified after the restart anyway.

⛔ **Skip all three steps when the folder is already connected.** §2.2 says it and it bears repeating here:
if `./.mcp.json` already names a working server, the session's job is to CALL it. Asking a connected user
for a token is the single clearest signal that the session did not read its own configuration.

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

### 8.1b ⛔ Correction — the re-import is YOURS to drive when you have a browser

Earlier revisions of this document said the import channel "is a re-import the human
drives". That is only true without a browser. **The project's own Settings page takes
the archive**, and the session you drive is already signed in:

```
<root>/<realm>/<client>/settings      <- import / export the .mrjun
```

So the support loop closes without handing work back: edit the export -> `validate` ->
`pack` -> import at `/settings` -> re-drive the scenario. Ask the user only if that page
refuses you, or if they asked to perform the change themselves.

⚠️ **After every import, re-deploy the workflows.** They come back `deployed: false`
and `service.workflow.start` throws until they are deployed again. And anything you
changed live over MCP but never mirrored into the export is REVERTED by the import —
which is the practical reason every fix must land in `work/` as well.

The full order of work — import, deploy, drive, buglist, fix, re-drive, and only then
the autotest project — is [30-live-test-bugfix-and-autotest.md](30-live-test-bugfix-and-autotest.md).

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

### 8.5a ⛔ Two ways the browser lies about a change you just made

A component behaves correctly, your probe says it does not, and you spend the evening fixing code that
was never broken. Both of these produce exactly that, and both are silent.

**1 · `computer` coordinates are SCREENSHOT pixels, not CSS pixels.** A screenshot comes back scaled
(1502 px wide for a 2056 px viewport — a factor of 0.73). Compute a target from `getBoundingClientRect`
and pass it straight to `computer` and you click ~370 px away from what you measured, on a real element
that reacts plausibly. Calibrate once per session instead of assuming:

```js
// hover a known screenshot point, then read what clientX the PAGE actually saw
document.addEventListener('mousemove', e => document.documentElement
  .setAttribute('data-lm', e.clientX + ',' + e.clientY), true);
// … computer hover at (1000, 500) … then:
const K = 1000 / +document.documentElement.getAttribute('data-lm').split(',')[0];
// screenshotX = cssX * K
```

⛔ And **verify the hit before the gesture**: `document.elementFromPoint(cssX, cssY)` must already
return the element you mean to hit. If it returns the thing behind it, the bug is z-order, not the
handler — do not go looking in the JS.

**2 · A BACKGROUND tab swallows clicks while still delivering mousemove.** If the human switched to
another tab, `document.visibilityState === "hidden"`: hover events still arrive and highlight things,
so the page looks alive, but `click` never fires and every click-driven assertion reports a failure.
Read the flag before you believe a negative result:

```js
JSON.stringify({vis: document.visibilityState, focus: document.hasFocus()})
```

`hidden` means **stop testing** and say so, rather than reporting "does not work".

> ⛔ And the rule that outranks both: **never verify an interaction with a synthetic event.**
> `el.dispatchEvent(new MouseEvent('click'))` reaches the handler through a path a mouse can never
> take — it ignores z-order, `pointer-events`, and overlays. It will report green on a control that is
> physically unreachable. Drive it with `computer`, or do not claim it works.

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

### 8.8 The automated test project — built after the live test, not instead of it

A live test finds bugs. It cannot stop them coming back. The drive is manual, it is slow, and the next
session repeats it from memory — so the session that drove it leaves behind a project that re-drives it
**by command**, and every scenario it proved becomes a test that fails the day someone breaks it again.

⛔ **Order matters and is not negotiable: live test and bug-fixing FIRST, the automated project after.**
Writing tests against a broken build encodes the breakage — you spend the effort teaching the suite that
`total = 0,00` is the expected value. Drive the scenarios by hand, fix what they surface, re-drive them,
and only then automate what you have already watched pass.

**Ask before building it**, the same way §8.0 asks about the live test:

> *"The live test is done and the findings are fixed. I can also leave you an automated test project —
> one command re-runs every scenario we just went through, so a regression shows up the same day. It
> lives in `test/`, needs no token of its own beyond the login, and takes me a while to write. Want it?"*

**A yes means ALL the scenarios, not a smoke test.** The value of the suite is that it covers what the
scenario file covers: every calculation with its expected number, every refusal that must stay a refusal,
every localisation that must stay translated, every report that must keep rendering. A suite that checks
the login and two pages is worse than none — it is green while the system is broken, and people trust it.

#### ⛔ What "ALL the scenarios" means — the coverage map, and the gate that enforces it

"All" is the whole point of the offer, and it is the promise an AI quietly breaks: writing eight
easy files feels like finishing. So the suite starts from a **map**, not from a blank `tests/`
folder. Read the scenario file, list every numbered section, and write the map down before the
first test — in the suite's own README, as a table:

| Scenario § | What it proves | Test file | Watched pass live |
|---|---|---|---|
| §4.1 | the inbound document posts and its total recalculates | `tests/test_05_inbound.py` | yes |
| §6.1 | the bill of materials scales by order quantity — every number | `tests/test_12_full_cycle.py` | yes |
| … | … | … | … |
| §9.2 | the rework order carries its loss cost component | `tests/test_14_…py` | **no — never opened** |

A row with no test file is not an omission to discover later; it is a line in the hand-over. A
row whose "watched pass live" is *no* is the honest version of §8.8's closing rule.

**The ten families every map must account for**, because each one hides a different class of
regression and skipping any of them makes the suite green on a broken system:

1. **the front door** — the app is up, the session signs in, the home page is not blank;
2. **navigation and access** — every section in the menu opens; every page a role group can reach
   renders; the pages it must NOT reach refuse;
3. **every register** — each list paints rows, its filter narrows, its paging advances. A register
   that renders its header and zero rows is the single most common silent break;
4. **every calculation, by its number** — the scenario file's arithmetic, compared exactly, with
   the formula written into the assertion message so a red run explains itself;
5. **every business process end to end, in ONE test per chain** — the steps only lie at the joins,
   and eight green step-tests hide a chain that never completes (this is what §6's chain test is);
6. **every refusal** — each state guard, each validation, each role denial: the action is refused
   AND the message names the reason. A refusal that stops naming the missing item is a regression;
7. **every localisation** — each locale the tenant declares: the nav, the register captions, the
   joined entity names, the enumeration labels, the refusal messages. Assert no leak of one
   language into another, and exempt proper nouns explicitly;
8. **every report and dashboard** — it returns rows, its filters narrow, it shows no raw
   enumeration codes, and its numbers agree with the register they come from;
9. **the deliberate gaps** — what the project knowingly does not do gets a test that asserts the
   CURRENT behaviour and says so in its docstring. Otherwise the next session "fixes" it by
   accident and nobody notices which promise changed;
10. **the regressions you just fixed** — one test per bug found in the live drive, named after the
    bug's id, asserting the exact thing that was broken. This is the only part of the suite whose
    value is already proven.

**What the map is worth, measured once.** On a delivered project whose suite already had 120 green
tests, writing the map took twenty minutes and named **four scenario sections with no test at all**.
One of them was not a missing test but a **missing capability**: the scenario said "register a
transfer" and the register that was supposed to do it had no create action — nothing in the system
could perform a Must requirement, and the suite had been green for days. Another section turned out
to describe a path the product never had, so the SCENARIO was wrong, not the build. Neither would
have surfaced from running the tests that existed: a suite can only fail at what it looks at.

⛔ **And when the map and the product disagree, find out which one is wrong before you fix either.**
"The scenario file says X and the product cannot do X" has two possible culprits, exactly like a
mismatched number (see the four causes below). Read the requirement the scenario cites; if the
requirement demands it, the product owes you the feature; if only the scenario demands it, the
scenario owes you a correction — and either way say so in the hand-over.

Then make the map machine-checkable: the runner's last line prints how many scenario sections have
at least one test and names the ones that do not. A number the user can read beats a claim they
cannot check — and a suite that knows its own holes is trusted where an unlabelled one is not.

**Shape**, whatever the language:

```
test/
  start.sh          # THE entry point — one command, no arguments needed
  .env.example      # BASE_URL, AUTH_USER, AUTH_PASSWORD — and .env git-ignored
  pages/            # page objects: one per screen, so a moved button is one edit
  tests/            # one file per scenario section, named after the section it covers
  tools/            # reset helpers (re-import the archive, redeploy the workflows)
  test-results/     # screenshots of failures — git-ignored
```

`start.sh` carries the whole ceremony so the user never has to know it: create the virtualenv, install the
dependencies, download the browser, check that `.env` is filled (⛔ **without printing the password**),
then run. It ends with a plain-language summary and, on failure, the likely innocent causes — a dropped
session, an import that never landed — so that a red run is diagnosable by someone who did not write it.

Give it modes, and make the safe one the default:

```
./start.sh              # everything that does not write to the tenant
./start.sh all          # including the scenarios that create records
./start.sh smoke        # "is it up and am I logged in"
./start.sh reset        # re-import the archive, redeploy the workflows, seed back to a known state
./start.sh -k lot_code  # any argument passes straight through to the runner
```

**What the tests must assert** — the same three things the live drive checked, in the same order:

1. **the number**, not the page: read the value the scenario file predicts and compare it exactly
   (`3.2960`, `92.16 %`, `7.38 %`). A test that only asserts "the page rendered" cannot fail usefully;
2. **the refusal**, by its text: a negative scenario passes when the action is refused AND the message
   names the reason. Assert the reason, not the exception — a refusal that stops naming the missing item
   is a regression the user will feel;
3. **the trace in the data**: after an action, read the row the action was supposed to write. The UI can
   report success over a swallowed exception; the database cannot.

**Then run it, and run it against the project it tests.** The suite is not delivered until you have
watched it go green on the live tenant — and a test that fails on its first honest run has found either a
bug you missed or a wrong expectation you wrote. Both matter; both get recorded and fixed before hand-over.

**A red run is a suspicion about the TEST first, and about the product second.** The first
full run of a freshly written suite reported 24 failures on a delivered project, and not one
of them was a defect. Every one looked like a serious finding — "the filter does not narrow
the register", "the calculation is wrong", "the page does not respond" — and every one was the
suite's own fault. Budget for this: the first honest run of a new suite costs a debugging
session, and the value is in what it teaches about the application.

The four causes are worth naming, because they recur:

* **State that lives on the SERVER, not in the browser.** The interface language was a user
  preference: switching it in one test — or by a human in another window — held for every test
  that followed, and they searched an English page for a Russian label. Anything the product
  stores per user (locale, author mode, a saved filter, a default warehouse) must be SET by the
  suite at the start of each file, never inherited. Declare it in the file and assert nothing
  about what came before.
* **A page object that encodes a fact which has since been fixed.** A helper looked for the
  filter button by a caption that used to be untranslated, with a comment explaining why. The
  caption got localised; the fallback selector then clicked a neighbouring button. The test
  failed with "the filter does not narrow the register" — a sentence that reads exactly like a
  product defect. When a helper carries a "this build behaves oddly" comment, re-verify the
  oddity before trusting the failure it produces.
* **Hidden siblings in the DOM.** Every row of a 15-row register carries its own hidden action
  menu. `…locator("button, a").last` and `get_by_role("link", name=…).first` both resolve to an
  invisible element in some other row, and the framework then waits out its full timeout. On a
  list, always scope to the row AND require visibility.
* **The expectation itself was wrong.** Three rows of the scenario document were mis-rounded;
  the system's arithmetic was right. ⛔ **Check the arithmetic before reporting a calculation
  defect** — the number a test asserts is only as good as the document it was copied from, and
  "the system disagrees with the spec" has two possible culprits.

The discipline that keeps this cheap: when a test goes red, reproduce the step BY HAND in the
browser first. It takes a minute, and it tells you which of the two things is broken before you
spend an hour fixing the wrong one.

**Twenty-five ways a UI assertion lies, all found on one delivered project.** They are not
about this platform's quirks — they are about how a page reports itself, and they recur:

* **A substring is not a signal.** A helper reported "server error" whenever the page contained
  `500`. Every register contains money: `1 500,00`. The working page was declared down. Match an
  error by its *signature* — the tab title, `Internal Server Error`, the framework's own error
  page — never by digits or words that legitimately appear in data.
* **`innerText` returns TRANSFORMED text.** A page that styles names with `text-transform:
  uppercase` yields `DIRECTOR` from `innerText`, not `Director`. A case-sensitive membership test
  then reports every single name as missing — which reads like "the page is empty", not like "the
  comparison is wrong". Compare case-insensitively unless the case itself is the thing under test.
* **A character's Unicode block is not its meaning.** The Armenian dram sign `֏` (U+058F) sits in
  the Armenian block, so a "does this page leak Armenian text?" check written as
  `[԰-֏]` flags every money column in every locale. Restrict such a check to LETTERS
  (`Ա-և`), and exempt the columns that hold proper nouns — a person's name and a
  company's name are not translated in any system.
* **A numeric input silently discards what it cannot parse.** `el.value = '33,5'` on an
  `<input type="number">` in an English session leaves the field **empty** — no error, no
  event, nothing in the log. The test then saved a reading with no value, the tolerance gate
  had nothing to refuse, and the run reported "the gate did not fire" about a gate that works.
  The decimal separator the field accepts follows the SESSION's locale, so a suite that runs
  in more than one language cannot hard-code either form. ⛔ **After writing a value, read it
  back**: if the field came back empty while you wrote something, retry with the other
  separator — and treat "the field is empty after I filled it" as a failure of the FILL, never
  as data.
* **A refusal message is asynchronous and transient.** The platform draws its refusal after
  the action round-trips and removes it seconds later. A test that waits a fixed four seconds
  and then reads the page reports "the refusal did not name the parameter" about a refusal that
  named it perfectly. ⛔ **Poll for the message** (short interval, generous deadline), and
  assert BOTH halves separately: the OBSERVABLE EFFECT (the step is still open, the document is
  still a draft) and the TEXT (it names the parameter that blocks it). When the effect holds
  and the text never arrives, that is a different defect — a refusal nobody can read — and it
  deserves its own sentence, not a failed assertion about the gate.

* **The biggest table on the page is not necessarily yours.** A page that hosts two
  registers — lots and reservations, counts and adjustments — has two tables, and
  "sort by innerText length and take the first" picks whichever has more rows. The test
  then reports "the lots register has no ON HAND column" and helpfully prints the
  RESERVATIONS columns. ⛔ **Choose a table by what must be IN it** (`grid("LOT CODE",
  "ON HAND")`), never by size, and say which columns you required in the failure message.
* **A tab is server-side state, exactly like the locale.** Which tab of a two-register page
  is open belongs to the USER on the server, so a tab another test selected is still
  selected in yours — and `Create` then opens the neighbouring register's form. Measured:
  a count test filled an ADJUSTMENT form and reported "System quantity: НЕ НАЙДЕНО" about a
  field that form never had. ⛔ **Select the tab explicitly at the start of every test that
  reads a register**, the same way you set the locale.
* **A label comparison is case-sensitive; the theme is not.** The project names a control
  `Source Lot`, the page prints `Source lot`, and a theme with `text-transform: uppercase`
  prints `SOURCE LOT`. An exact match then declares a present field absent. ⛔ Compare
  labels case-insensitively, trimming trailing `:` and `*`.
* **A field's TAG is a guess.** «Description» is a `textarea`, not an `input`; a picker may
  be a `select` on one form and a lookup on another. A filler that requires the tag reports
  "field not found" for a field that is right there. ⛔ Fall back between the text-ish tags
  and fail only when the LABEL is missing.
* **`goto` losing a race is not the page failing to open.** `net::ERR_ABORTED` means the
  previous page's redraw or redirect cancelled the navigation. Retry it (two or three times)
  — and when you finally report it, say it was the navigation, not the page.

* **A business code is a number to a regular expression.** A grid check that took "the first
  number in the row" as the quantity read the item code `RM-A12-003` as **−3.0** — the pattern
  `-?\d[\d ]*[.,]?\d*` finds `-003` inside it — and reported "planned requirement −3.0, expected
  3.296" about a row the database stored correctly. The failure named a calculation defect in the
  product; the defect was in the reading. ⛔ **Never locate a value by its SHAPE when the grid
  gives you a header.** Find the column by its caption (case-insensitively, with the caption in
  every locale the suite runs), then read that cell — and where the cell renders an `<input>`,
  read the field's `value`, because `innerText` of an editable cell is empty. The same trap hides
  in codes that end in digits, dates, phone numbers and lot keys: anything whose text a numeric
  pattern will happily match.

* **A synthetic click is not a click.** `element.click()` from injected JavaScript left a header
  dropdown closed: its handler wants real user input. The automation reported "the toggle is not
  there" while the toggle was plainly there. Drive through the automation framework's own click
  (it sends input through the browser protocol), and when a control still will not respond, assert
  on the OBSERVABLE EFFECT instead of the control — for an author-mode toggle, that is whether the
  admin links appeared, which is what the test cared about anyway.

The shared shape: each check asked a question the page could answer only by accident. Before
trusting a red assertion, ask what ELSE could produce exactly this output.

* **The server's clock is not your clock.** A document number stamped `PO-<yyyymmdd>-NNN` is
  built from the SERVER's date. Run the suite at 03:30 local against a UTC server and the number
  carries YESTERDAY's date — the test that derives the expected prefix from `time.strftime` on the
  test machine then reports "the order was not created" about an order that exists. Never
  reconstruct a server-generated identifier from client-side state: read it back, or accept the
  neighbouring days explicitly and say why.

* **A record that MATCHES is not a record you CREATED — and a scenario repeats its numbers.**
  The check "a finished-goods lot exists whose code matches YYMMDD-SKU-NN and whose balance is
  23.041" passed on the lot the PREVIOUS run had produced: the scenario releases the same
  quantity every time, so the previous result is indistinguishable from this one by value. The
  product was right (the new lot was numbered -02), but the assertion proved nothing about it.
  ⛔ Take a snapshot before the action and diff it after — for every record the system numbers
  itself. On one delivered project this same correction was needed three times in one day: the
  production order, the rework order, and the finished lot.

* **«The newest record with today's prefix» is not «the record this test created».** Two test
  files in one suite create the same kind of document on the same day; a third creates it as a
  side effect. A test that identifies its own record as *the highest number carrying today's
  prefix* silently adopts a NEIGHBOUR's record and then measures the scenario's numbers against
  it: the chain test read 5.2736 where the scenario says 3.296, because the order it picked up
  was someone else's 40 units instead of its own 25. The run reported a calculation defect in a
  calculation that was correct. ⛔ **Identify a server-numbered record by DIFFERENCE, not by
  maximum** — collect the numbers before the save, collect them after, take what is new; and when
  the register pages, take the difference THROUGH the register's own filter rather than off the
  first page. Then assert one field you typed yourself (the quantity you entered), so that
  adopting a foreign record fails loudly instead of quietly producing wrong numbers.

* **An INVENTED page address reads as missing data.** Four checks pointed at
  `/qc-inspections`, `/warehouses`, `/equipment`, `/reason-codes` — none of which the project
  declares (three of those registers are TABS of another page). Each opened a 404, found no
  rows, and skipped itself with "has no rows to judge": a sentence about the DATA, produced by
  a wrong URL. ⛔ **Take every path from the project's own page list**, and make the "no rows"
  skip fire only after you have proved the page exists (a title check is enough).
* **A column the register does not have makes a check disappear.** A weight-check test asked
  for four columns; the register has three (there is no "deviation, g" column at all), so the
  reader returned nothing and the test skipped with "the grid does not expose its numbers" —
  over a full register. ⛔ Read the column list from the table model, assert on what is there,
  and fail — not skip — when a column you need is genuinely absent.
* **The FIRST row is not a representative row.** Opening row #1 and finding its line grid empty
  is not "no record has lines". Two checks skipped on that, past 537 candidates. ⛔ When a check
  needs a record in a particular shape, LOOK for one (a bounded scan of the first page), and
  say how many you looked at when you give up.

* **The FIRST page of a sorted register is a biased sample.** A shop-floor register sorted by
  STAGE NUMBER shows only stage 1 on page one — and stage 1 is the incoming check, which by
  design has no measurements. Four checks concluded "no operation with readings exists in the
  current data" over 365 of 537 that have them. ⛔ Ask what the sort puts first, and go where
  the rows you need actually are (the last page, or a filter); when you give up, say how far
  you looked.
* **A pager's `li` is not its link.** Clicking the `li.page-item` whose text is `»` does
  nothing at all — the handler is on the `a.page-link` inside it. The page silently stays on
  page one, so the check reports "no such row" while looking at the wrong 15 rows. ⛔ Click the
  anchor, and verify the page actually changed before reading.
* **A grid's rows arrive after its dialog.** The dialog is drawn, its line grid fetched
  separately — and "zero rows" is ALSO a legitimate state, so the only way to tell "not yet"
  from "none" is to wait. A check that read the grid on the first look found a measurement grid
  empty on an operation that has three of them. ⛔ Poll for the rows; treat a single empty read
  as no information.

* **A page object's `open()` returns before the register is drawn.** The helper waits for the
  document, the framework then fetches the rows; a check that reads the grid (or a row's menu)
  on the next line finds nothing and skips itself with "no suitable row in the current data" —
  while the table holds 537 of them. ⛔ **Wait for the ROWS, not for the page**, and write the
  skip message so it cannot be confused with a data statement.
* **A form that opens in 4 seconds is not a form that failed to open.** The same helper
  concluded "the form does not open in this build" 1.5 s after the click. On a live stand the
  dialog arrives by AJAX in 3–6 s. ⛔ Poll for the dialog; never assert its absence on one look.

* **An EMPTY action menu is not «this row has no actions».** The row's menu is rendered by
  the framework AFTER the table; a check that reads it immediately after the rows appear finds
  zero items on a row whose menu, a second later, holds ten. The test then says "the order has
  no «Request reopen» action" — a sentence about the product, produced by reading too early.
  ⛔ **Re-ask an empty enumeration** (a menu, an option list, a grid) before concluding it is
  empty; a genuinely empty one costs a few seconds, a wrongly empty one costs a bug report.

* **The button you press must live in the form you filled.** «The last button with this caption
  on the page» reaches the register under the dialog; «the last dialog in the DOM» reaches a
  dialog that was CLOSED three steps ago and is still in the markup with a visible layout box.
  Both press something, both return success, and the form you filled is never submitted — after
  which the test works with whatever record the register happens to show. ⛔ **Mark the dialog you
  filled and press inside that mark.** And read the refusal from inside it too: a form's own
  validation prints its message in the form and raises no toast, so a rejected save and a
  successful one look identical from outside.

**A waiter that greps for the process it waits on never fires.** Queuing a long run behind
another (`until ! ps aux | grep -q pytest; do sleep 20; done; pytest …`) blocks forever: `ps`
prints the waiter's OWN command line, and that line contains the pattern. The bracket trick
(`[p]ytest`) only excludes the grep process itself, not the shell that holds the same text. Match
on something the waiter cannot contain — the interpreter path, a pid file, a lock — or check the
run's own output file instead. Worth knowing because the failure mode is silence: the queued run
simply never starts, and the session waits on nothing.

**And when ten checks fail at once, read the message before you read the product.** Ten
assertions that all say `NameError: name 'Driver' is not defined` are one missing import, not
ten defects; ten that all say "no rows" are one register that did not render. A batch of
identical failures is a property of the HARNESS with near-certainty — triage by grouping the
messages first, and only then open the application. The reverse order costs an hour and can
produce a bug report about a feature that works.

**A visible browser is a shared resource, and a long run must not use one.** Running the suite
with a window on screen (`headless=false`) is right for watching one scenario and wrong for a
25-minute sweep: a screen lock, a sleeping display, another application stealing focus, or one
stray Cmd-W ends the run with `TargetClosedError: Target page, context or browser has been
closed` — a message that reads like the application crashed. ⛔ **Default the runner to
headless** and make watching an explicit, per-command override (`HEADLESS=0 ./start.sh -k
one_test`). The tell is the SHAPE of the error, not the place: `TargetClosedError` on a
plain wait — a step that asserts nothing — is the window going away, while a product defect
fails an assertion and says what it expected. Re-run headless before you diagnose anything
else; it costs one run and removes a whole class of ghost.

**And one that is not about the page at all: a run that was KILLED is not a run that FAILED.** A
browser suite holds a real browser open for the length of the run; on a developer machine that is
competing with an IDE, a VM and a container runtime. When the system reclaims memory it kills the
process, and the output ends with no summary line at all — which looks exactly like a crash in the
last test. Make the runner say so before it starts: check free memory, warn under a threshold, and
in the failure epilogue name "the run was killed, not failed" as one of the innocent explanations.
The alternative is someone re-running a 25-minute suite three times to chase a defect that does not
exist.


### ⛔ When the data a check needs does not exist, CREATE it — or say exactly what is missing

A prohibition test can only prove a guard if the forbidden situation exists. On a delivered
project four such tests skipped themselves for weeks with "no suitable record in the current
data", and the most important one — the gate that refuses to close a production stage over a
measurement nobody approved — had therefore never run. The data was not missing by accident:
the previous run had APPROVED its own deviation, which is what a correct run does.

So a prohibition test does one of two things, and never a third:

* **it creates the situation itself**, exactly as the user would — open the measurement that has
  limits, type a value above the maximum, save, then press the action that must be refused. Then
  the guard is exercised on every run, on any tenant, from any starting state;
* **or it skips with the missing precondition SPELLED OUT** — which record, in which state, and
  which other test does create it. "No suitable data" is not a finding; "no order awaiting QC
  with issued-but-unconsumed materials, a state that exists only between two steps of the full
  cycle" is.

⛔ And the order matters: do the creating FIRST. A long reconnaissance loop that opens and closes
a dozen forms leaves the register in a state where the next read no longer works — the helper
that looked for an existing deviation before creating one made the creation fail, and the test
skipped over data it had just been shown.

### ⛔ A test that "passes" without doing anything is worse than a red one

The most expensive defect a suite can carry is not a false failure — it is a green test that
performed no action. Two shapes of it were found on one delivered project, both in tests that
had been green for days:

* **The action with a FORM was never submitted.** A row action that opens a form is confirmed
  by a button carrying THE ACTION'S OWN NAME — `Submit for approval`, `Post`, `Close` — not by
  `Save` and not by a `Yes` dialog. A test that presses the menu item and then looks for `Yes`
  does nothing at all: no case is opened, no document is posted. Its assertion («the queue did
  not grow by more than one») then holds trivially, and the suite reports success over an
  untouched system. ⛔ **After every action that opens a form, assert that the form was
  submitted** — press the button by the action's name and fail when it is not there.
* **The refusal that was never provoked.** A prohibition test that fills only two of four
  mandatory fields gets the platform's own field validation, not the business guard it means to
  check — and if it asserts merely "some feedback appeared", it passes while proving nothing.
  ⛔ Fill every mandatory field, then assert the guard's OWN words.

The general rule: for each test ask *what would fail if the feature were deleted?* If the
answer is "nothing", the test is decoration. That question found both of these in one reading.

⛔ **The suite is the second proof, never the first.** If a scenario passed only in the suite and you never
watched it in the browser, say so. Automation inherits every blind spot of the person who wrote it.
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
* **the automated suite, if one was built** (§8.8) — the one command that re-runs it, what a red run means,
  and which scenarios it does NOT cover. ⛔ Hand it over green or not at all: a suite the user first sees
  failing is a suite the user never runs again.
