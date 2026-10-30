# 36 · Messengers — the project talking to people on Telegram, WhatsApp, Slack, Teams and the rest

> **Scope.** Two halves of one integration. A rule **sending** to people — a notification, an answer, a message with
> buttons, a file — through a messenger connection. And the project **listening**: what people write (a message, a
> `/command`, a button press, a reaction, someone joining) runs one or more rules. Read it the moment a PRD says
> *"Telegram bot"*, *"WhatsApp"*, *"customers write to us in …"*, *"notify the team in Slack / Teams / Mattermost"*,
> *"chatbot"*, *"send the invoice to the customer's Viber"*, *"a VK community"*, *"post to the channel"*, *"Matrix"*,
> *"Zulip"*, *"Rocket.Chat"*, *"Discord"*.
> **Not here:** e-mail → [31](31-email-integration-and-mailbox.md); message brokers (MQTT, Kafka …) →
> [33](33-pubsub-integration.md); another system calling the project over HTTP → [32](32-public-api.md); a process a
> message starts → [27](27-event-driven-process-start.md) (the listener's rule IS that starter); the Groovy surface as a
> whole → [16](16-groovy-service-api.md).

---

> ## ⛔ Read this before you plan anything: **none of this is in the `.mrjun`**
>
> The CONNECTIONS — which messenger, the bot token or app credentials, how it receives — and the LISTENERS (what each
> takes and which rules it runs) live in the messaging service's own store, credentials encrypted, and are **not part
> of an export**. No `branches.json` key, no `mrjun.py` command writes one.
>
> **What you author offline:** the **rules** — the ones that send, and the ones a listener runs — and what they touch
> (tables, CRUD methods, pages). **What the recipient does once, live:** adds the connection, adds the listeners, picks
> the rules by name — §9 is the handover note; write it. **When you work on a LIVE project through MCP** ([28](28-support-mode-over-mcp.md))
> you can do that part yourself with the user's credentials — §8.

| | |
|---|---|
| The switch | Settings → **Developer** → **Integrations** → **Messengers** (between Email and PubSub; Author or Developer **role group**) |
| The connections | up to 25 per project, any mix of messengers, each with its own credentials and **alias** |
| What is authorable | EXECUTION rules and CRUD GROOVY methods that send; EXECUTION rules a listener runs |
| With nothing configured | `service.messenger` is not offered in the editor; a call fails with a sentence naming the missing alias — never hangs, never writes |
| Addressed from Groovy by | the connection's **alias** — `service.messenger.<alias>.send(…)` |
| Runs where | **EXECUTION rules and CRUD GROOVY methods only.** In a predicate or a validation rule — and in any rule they call — every member refuses |
| A listener's rule runs as | the platform on its own authority, with the **author who last saved the connection on the screen** as the acting user; nobody is signed in, no browser waits |

---

## 1 · The decision — which messenger, and what the customer must have

| the customer says | kind | what they need first | receives by | worth knowing |
|---|---|---|---|---|
| *a Telegram bot, /commands, buttons* | **Telegram Bot** | a bot from @BotFather (token) | long polling (no public address) or webhook | in groups a bot sees only /commands unless privacy mode is off; a person must press Start first |
| *answer customers from our OWN Telegram account* | **Telegram account** | any account + a bot connected in Telegram's Chat Automation | polling or webhook | private chats only; Telegram allows answers within 24 h of the person's last message |
| *WhatsApp, our business number* | **WhatsApp** | a Meta app + WhatsApp Business account, number id, a never-expiring System User token, App secret | **webhook only** (needs the platform's public address) | free-form answers only within 24 h of the customer's last message; after that only **approved templates**; Meta charges templates and (since 2026-10-01) service replies beyond 1,000/month per number |
| *Viber* | **Viber** | a Viber chatbot (commercial since 2024-02: a partner contract, ≈ €115/month) and its app key | **webhook only** — and Viber refuses to SEND until the platform registered it | one-to-one only; no edit/delete; a button press arrives as a message whose text is the button's data |
| *Facebook page Messenger* | **Facebook Messenger** | a Meta app, Page id + Page token, App secret; App Review of pages_messaging for real customers | **webhook only** | 24 h answer window (7 days with the reviewed Human Agent tag); no formatting |
| *Instagram Direct* | **Instagram** | a professional account; via its Facebook Page (tokens never expire) or Instagram Login (60-day token) | **webhook only** | text ≤ 1000 BYTES; 24 h window; no formatting |
| *VK community messages* | **VK** | a community token (messages, manage, photos, documents) | long polling | writes only to people who wrote first or allowed its messages; no text formatting |
| *VK Teams / VK WorkSpace (on-premise)* | **VK Teams** | a bot from Metabot + the installation's Bot API address | long polling | Markdown or HTML; edits and deletes within 48 h |
| *Microsoft Teams* | **Teams** | an Azure Bot (single tenant) + app password — or, to post only, a Workflows webhook | webhook (the bot) | the bot cannot write first to someone it never talked to; documents are not offered |
| *Google Chat / Google Workspace* | **Google Chat** | a Chat app with a service account + a Pub/Sub subscription — or an incoming webhook to post only | Pub/Sub pull (no public address) | sees direct messages and @mentions; commands are defined in the Cloud console |
| *Slack* | **Slack** | a Slack app from the provided manifest (bot token; app-level token for Socket Mode) — or an incoming webhook to post only | Socket Mode (no public address) or the Events API | no "typing"; a slash command's answer is posted, not shown inline |
| *Discord* | **Discord** | a bot of a Developer Portal application (Message Content intent to read text) — or a channel webhook | the Gateway (no public address) | mentions never ping (`allowed_mentions` off); text ≤ 2000 |
| *Mattermost (self-hosted)* | **Mattermost** | the server address + a bot account's token | WebSocket (no public address) | no buttons/slash commands; Markdown |
| *Rocket.Chat (self-hosted)* | **Rocket.Chat** | the server address + a user id and token | WebSocket | no buttons; no typing |
| *Matrix / Element (Synapse …)* | **Matrix** | the homeserver address + an access token | /sync long polling | **encrypted rooms are not read** (the test names them); invites are joined from the bot's own homeserver by default |
| *Zulip* | **Zulip** | the server address + a bot's email and API key | event queue (long polling) | a "thread" is the topic; no reply-quote |

"No public address" kinds work on a closed on-premise installation; webhook kinds need the platform's public
`/messenger-hook/` address reachable from the internet (the installation's operator sets that up once).

---

## 2 · The model: a connection, an alias, listeners

```
connection  alias=<alias>   kind=<kind>  way=<variant>  receives by=<POLL|SOCKET|WEBHOOK>  [Active] [Rules can send] [Run rules when messages arrive]
   └ listener  takes: Messages, Commands   chats: <ids or blank>   commands: <start, help>   rules: [<rule A>] → [<rule B>]
   └ listener  takes: Button presses                                                          rules: [<rule C>]
```

- The **alias** is what rules write: letters, digits, underscore, starting with a letter, at most 40, unique in the
  project ignoring case; not a Groovy keyword nor a member of `service.messenger` (`list`, `channel`, `channels`,
  `get`, `alias`, `aliases`, `exists`, `names`, `has`, `reply`, `send`). The screen says so while it is typed.
- **Rules can send** and **Run rules when messages arrive** are independent. A send-only way of connecting (an
  incoming webhook: Slack, Discord, Teams Workflows, Google Chat) never receives.
- A **listener**: which events (MESSAGE, COMMAND, BUTTON, EDITED, REACTION, MEMBER — the kind lists the ones it
  delivers), which chats (ids, or `@handles` where the messenger has them; blank = all), which commands, an optional
  text pattern (a regular expression searched in the text, or in a pressed button's data), the rules **in order**, and
  attempts per rule.
- **One connection per credential on the installation**: one Telegram bot, one WhatsApp number, one Slack app can be
  connected once — a second receiver of the same bot makes both lose messages, so the screen refuses it.
- Credentials are write-only: never shown again; a blank box keeps the stored one. **Test connection** (right under the
  credentials) signs in and says who the connection is (the bot's @name, the page, the number) and what will fail.

---

## 3 · Nothing you have already written changes

A project without a connection behaves exactly as before; the editor does not even offer `service.messenger`. A rule
that uses it can ship before the customer connected anything — it fails with a sentence naming the alias, which is the
right failure.

---

## 4 · Sending — `service.messenger.<alias>.…`

```groovy
service.messenger.<alias>.send(chatId, 'Order **#42** shipped')                       // to, text (Markdown)
service.messenger.<alias>.send(chatId, 'Pick one', [buttons: [[text: 'Yes', data: 'yes'], [text: 'No', data: 'no']]])
service.messenger.<alias>.send(chatId, 'Hi', silent: true)                            // named options after the positionals
service.messenger.<alias>.send(to: chatId, text: 'Hi', format: 'text')                // all named
service.messenger.<alias>.sendFile(chatId, pdfBytes, [name: 'invoice.pdf', text: 'Your invoice'])
service.messenger.<alias>.sendFile(chatId, [bytes: pdfBytes, name: 'invoice.pdf'], text: 'Your invoice')
service.messenger.<alias>.sendFile(to: chatId, file: pdfBytes, name: 'invoice.pdf')  // all named
service.messenger.<alias>.sendFile(chatId, 'https://example.com/plan.pdf')           // by public https address
service.messenger.<alias>.edit(chatId, sent.id, 'Updated', buttons: [...])            // buttons are REPLACED: pass them again
service.messenger.<alias>.delete(chatId, sent.id)
service.messenger.<alias>.typing(message)                                             // before a slow answer
service.messenger.<alias>.download(message.attachments[0])                            // byte[] of a received file
service.messenger.<alias>.chats()                                                     // the chats it knows: id, type, title
service.messenger.reply(message, 'Thanks!')                                           // a listener's rule: where it came from
service.messenger.<alias>.answer(message, 'Saved', alert: true)                       // acknowledge a button press
service.messenger['<alias>'] · service.messenger.list()                               // an alias in a variable · what exists
```

`send`/`sendFile`/`reply`/`edit` return `[ok: true, id: '<message id>', chat: '<chat id>', millis: 12]` — keep `id` to
edit or delete later. Options go positionally (a map as the last argument) or named after the positionals — both work
for every member that takes options. The recipient (`to`, `chat`) is the chat's **id** (`message.chat.id`), never the
chat or the message itself (refused with a sentence) — `reply(message, …)` is the member that takes a message.
`answer(message)` on a press the messenger wants no answer to (a keyboard button such as VK's "Start") does nothing and
returns `ok`, so a rule written for every messenger may answer every press; `answer` takes one option, `alert`. A refusal throws with a sentence (*"Telegram Bot cannot … "*, *"The text is 5000 characters;
Slack takes up to 4000"*, *"'buttns' is not an option …"*).

**Options a single message may carry** — the same for every messenger: `format` (`markdown` · `html` where the kind
renders it · `text`), `buttons` (a list = one row, a list of lists = rows; a button is `[text:, data:]` (pressing it sends
a BUTTON event with that data) or `[text:, url:]`, or just a string), `replyTo` (a message id), `thread`, `silent`,
`file`. Plus the kind's own (an unknown key is an error, never ignored):

| kind | its own per-message options |
|---|---|
| Telegram Bot | `linkPreview`, `protectContent` |
| Telegram account | `linkPreview` |
| WhatsApp | `template`, `templateLanguage`, `templateParams` (a list or a map — passed as JSON), `templateComponents`, `listButton`, `linkPreview` |
| Viber | `senderName`, `senderAvatar`, `trackingData` |
| Facebook Messenger, Instagram | `humanAgent` |
| VK | `intent`, `linkPreview` |
| Slack | `linkPreview` |
| Discord | `linkPreview`, `username` (webhook) |
| Matrix | `notice` |

**What a kind can do** decides which members work: `edit`/`delete` (not WhatsApp, Viber, Messenger, Instagram),
`answer` (Telegram, VK, VK Teams, Slack, Discord), `typing`, `download`, `chats`, buttons (not Mattermost, Rocket.Chat,
Matrix, Zulip), threads. The editor's completion offers, per alias, exactly the members ITS connection can do; the
call refuses the rest in words.

**Markdown is portable.** Write ordinary Markdown (`**bold**`, `*italic*`, `` `code` ``, `[text](https://…)`); each
messenger gets its own spelling, and where it shows no formatting (VK, Messenger, Instagram) the text is sent as it
reads. HTML only where the kind lists it (Telegram, Matrix, VK Teams).

**Windows and templates.** WhatsApp, Messenger, Instagram and the Telegram account answer freely only within **24 h**
of the person's last message; WhatsApp outside it only with an **approved template**
(`send(to, '', [template: '<name>', templateLanguage: 'en_US', templateParams: ['<v1>', '<v2>']])`). Plan the PRD's
"remind the customer next week" accordingly.

---

## 5 · Listening — someone writes, rules run

### 5.1 What a rule receives

```groovy
def message   = context.data.getAttr('message')      // the event - the same shape for every messenger
def messenger = context.data.getAttr('messenger')    // alias, kind, listener, receivedAt, attempt, step, steps
```

| field of `message` | |
|---|---|
| `event` | MESSAGE · COMMAND · BUTTON · EDITED · REACTION · MEMBER |
| `type` | text, photo, document, audio, voice, video, sticker, location, contact, button, reaction, join, leave, other |
| `text` | the text (a caption for a file; the pressed button's message text) |
| `chat` | `[id, type: private / group / channel, title, username]` — `chat.id` is what `send` and the chat filter take |
| `from` | `[id, name, username, phone?, language?, bot]` |
| `command`, `args` | `/start 42` → `start`, `42` (COMMAND, kinds with commands) |
| `data`, `callbackId` | a pressed button's data, and what `answer(message)` needs (BUTTON) |
| `thread`, `replyTo` | where to answer inside a thread; the message it quoted |
| `attachments` | `[kind, id, name, mimeType, size]` — `download(message.attachments[0])` |
| `latitude`, `longitude`, `contactName`, `contactPhone` | a shared location or contact |
| `outgoing` | true = the account's OWN owner typed it elsewhere (Telegram account, WhatsApp app) — only listeners with "Also run for own messages" get those |
| `alias`, `kind` | the connection it arrived on — `service.messenger.reply(message, …)` uses it |
| `raw` | the messenger's original event, for what the common shape does not carry |

Use `context.data.getAttr(…)`, never `attrs.get(…)` (a raw JSON node). The connection's own messages are never events —
a bot never answers itself.

### 5.2 What happens to an event — the delivery contract

| situation | what happens |
|---|---|
| everything works | stored first, then acknowledged to the messenger; the rules run **in order**, each with the same event |
| the messenger delivers it again (a retry, a reconnect) | recognised, not run again |
| a rule throws | tried again (attempts per rule, 1 s → 30 s), **resuming at the rule that failed** |
| it keeps failing | given up on: marked FAILED with the error in **Recent events** (Run again re-queues it after the fix); the next event goes on |
| the rule executor is down, the rule was deleted | the event **waits** (attempts not spent) and the listener says why; it carries on when fixed |
| the service restarts between "the rule ran" and "done" | **the rules run a second time** — make them idempotent |
| a listener 10,000 events behind, or an event over 256 KB | refused and counted on the listener |

**Idempotency** as in [33](33-pubsub-integration.md) §5.2: key what the rule writes on the event's business id or on
`message.id` + `message.chat.id`, unique index + do-nothing-on-conflict.

### 5.3 The common shape — a command bot

```groovy
// Listener: takes Commands, commands: status
def message = context.data.getAttr('message')
def order = service.crud.<orderAlias>.findByNumber([number: message.args])
service.messenger.reply(message, order ? "Order **${order.number}**: ${order.status}" : "No order ${message.args}")
```

### 5.4 Per-kind receiving facts that decide the design

- **Telegram groups**: a bot sees only /commands and replies to it unless privacy mode is switched off in @BotFather.
- **Slack**: Socket Mode (default) needs no public address; the bot hears channels it was invited to.
- **Discord**: reading message text needs the Message Content intent ticked in the Developer Portal.
- **Matrix**: encrypted rooms produce no events — use unencrypted rooms for the bot.
- **WhatsApp / Messenger / Instagram / Viber / Teams / Slack Events API / Telegram on webhook**: the messenger calls the
  platform's webhook address — the connection shows it with a Copy button. Telegram and Viber are given it by the
  platform itself; WhatsApp, Messenger, Instagram, Teams and Slack's Events API need it pasted once in their console
  (WhatsApp then points each connected number at it itself).
- **Button presses** (Telegram, VK, VK Teams): answer them (`answer(message, …)`) FIRST — the button spins until then.
  On VK only presses of the platform's (callback) buttons carry `callbackId`; VK's "Start" button sends a message, so
  `answer(message)` has nothing to do there (it returns `ok` and does nothing — answering every press is safe).

---

## 6 · Canonical rules

**A. Notify a person when something happens** (an EXECUTION rule or CRUD GROOVY method in the flow that changes the record):

```groovy
def order = context.<ctx>.<orderAlias>.data.get()
service.messenger.<alias>.send(order.customerChatId, "Your order **#${order.number}** has shipped",
        [buttons: [[text: 'Track', url: order.trackingUrl]]])
```
Where the chat id comes from: a listener's rule stores `message.chat.id` with the customer the first time they write
(a `/start <customer-code>` deep link is the usual way to bind them).

**B. Ask with buttons, act on the press:**

```groovy
// send: [buttons: [[text: 'Approve', data: "approve:${req.id}"], [text: 'Reject', data: "reject:${req.id}"]]]
// listener on Button presses:
def press = context.data.getAttr('message')
service.messenger.<alias>.answer(press, 'Noted')                        // first
def (decision, id) = press.data.split(':')
service.crud.<requestAlias>.decide([id: id, decision: decision, by: press.from.id])   // idempotent by id
service.messenger.<alias>.edit(press.chat.id, press.id, "Request ${id}: ${decision}")  // removes the buttons
```

**C. A message opens a case** — the listener's rule is the *starter* of [27](27-event-driven-process-start.md): it
validates, claims the business id (`message.id`), calls `service.workflow.start(…)`. Phase 1a's starter column has a
value for it: **MESSENGER MESSAGE**.

**D. Keep a file a customer sent**: `def bytes = service.messenger.<alias>.download(message.attachments[0])`, then store it
through the project's file mechanism and reference it in the record.

**E. Post to a team channel** from a scheduler or a process step: a send-only connection (an incoming webhook) is
enough. It posts into its own channel, so the recipient is any word — `service.messenger.<alias>.send('alerts',
'**Daily report** …')`.

---

## 7 · Limits and operating facts a PRD should hear

| | |
|---|---|
| Connections per project | 25; listeners per connection 50 |
| Text per message | the kind's: Telegram 4096, WhatsApp 4096, Viber 7000, Messenger 2000, Instagram 1000 bytes, Slack 4000, Discord 2000, Teams 28 000, Google Chat 32 000, Mattermost per server (up to 262 144), Matrix 30 000, Zulip 10 000 |
| Files | up to 20 MB through the platform (the messengers' own limits are often lower) |
| Rate limits | waited out up to 3 times, ≤ 20 s each; a send that timed out is NOT repeated (it may have arrived) |
| Recent events kept | 7 days (FAILED ones re-runnable from the screen) |
| Failover when the instance holding a connection dies | up to ~60 s (events are not lost: the messenger redelivers, polling resumes) |
| Visible on the screen | state, who the connection is, last send error; per listener: received, handled, failed, last error; Recent events and Recent chats |

---

## 8 · Working on a LIVE project through MCP

When you are connected to the live project ([28](28-support-mode-over-mcp.md)), the messaging service's tools do what
the Settings screen does — same checks:

| tool | for |
|---|---|
| `nct_messaging_messengerKinds` | the kinds; with `kind` — the setup steps to give the user, the fields (which are secrets, which required), options, limits, an example |
| `nct_messaging_listMessengerConnections` / `getMessengerConnection` | aliases, kinds, state, listeners (with their rule identifiers), the webhook address |
| `nct_messaging_saveMessengerConnection` | create, or change by alias passing ONLY what changes (options/secrets merged key by key); listeners name rules by identifier (`nct_rule_findAll` / `nct_rule_create`) |
| `nct_messaging_testMessengerConnection` | prove the credentials; read the warnings aloud to the user |
| `nct_messaging_sendMessengerTestMessage` | one real message — only when the user wants it |
| `nct_messaging_messengerEvents` / `retryMessengerEvent` | what arrived, what each rule made of it, run a FAILED one again after a fix |
| `nct_messaging_messengerChats` | the chat ids a filter or a send needs |
| `nct_messaging_deleteMessengerConnection` | only on the user's explicit request |

Credentials are the **user's** — ask, never invent, never echo one back; the tools never return a stored one. A
connection created OR CHANGED through MCP has no acting user: its listeners' rules run as the platform until an author
saves it on the screen once (say so — an edit through MCP takes the previous author's name off it). A webhook connection's address: when the answer says it is not known yet, the user opens the
connection once in Settings (or the operator sets the installation's public address).

---

## 9 · What you cannot check offline, and the handover note

`validate` sees the rules, not the messenger. Drive live ([30](30-live-test-bugfix-and-autotest.md)): **Test connection**
says who it is; write to the bot and watch the listener's counters and **Recent events**; press a button; make a rule
throw once and see FAILED with the error; send twice the same command and check one record. Messenger scenarios are
**manual** in `test-scenarios.md` (no messenger in the generated suite's `.env`); never put a token in the export or the
tests.

**The handover note** — copy this shape:

> This project talks to people on **`<messenger>`**. Before it can, open **Settings → Developer → Integrations →
> Messengers**, press **Add messenger**, choose **`<messenger>`**, follow the steps shown there (they say what to create
> on the messenger's side), give it the alias **`<alias>`** — the rules expect exactly that name — paste the
> credentials and press **Test connection**. Keep **Rules can send** on. `<If it receives:>` Keep **Run rules when
> messages arrive** on, **Add listener** for **`<events>`** `<, chats …, commands …>` and choose the rule
> **`<rule name>`**. `<If it receives by webhook:>` After saving, copy the address shown under Receive into
> **`<where the steps say>`**. Until then the project sends nothing and hears nothing.

| event | connections, listeners, events |
|---|---|
| **export / environment publish** | not included |
| **re-import into a live project** | **untouched** — listeners keep pointing at the rules (identifiers are kept) |
| **the project is DELETED** | removed (webhooks taken off the messengers) |
| **a NEW project on a deleted one's realm/client** | swept on creation |

---

## 10 · What `mrjun.py validate` checks

Offline, from the rule text (comments and string literals ignored):

- **ERROR** — a PREDICATE or VALIDATION_RULE uses `service.messenger` (directly, or through a literal
  `service.rule("…")` / `service.crud.<alias>.<method>(…)` into a body that does): every member throws there.
- **ERROR** — a channel member that does not exist (`service.messenger.<alias>.post(…)`, `.sendMessage(…)`,
  `.subscribe(…)`): a channel has `send`, `sendFile`, `reply`, `answer`, `edit`, `delete`, `typing`, `download`,
  `chats`. Receiving is a **listener**, configured live.
- **ERROR** — a call on the namespace that is not `list()`, `channel(alias)` or `reply(message, text)`.
- **ERROR** — a literal alias that can never exist (`service.messenger['my-bot']`, a keyword, a reserved word).
- **WARN** — a literal option no kind has (`buttns:`, `parse_mode:`): the call is refused at run time.

It cannot know that a connection exists, which kind an alias is, or that a listener points at a rule — that is §9.

---

## 11 · Traps

| trap | what happens | what to do |
|---|---|---|
| The chat id is not known when a rule must notify someone | nothing to send to | bind it when they first write (`/start <code>` deep link) and store `message.chat.id` |
| A rule answers every message, including in a busy group | the bot spams the group | narrow the listener (chats, commands, pattern); Telegram's privacy mode helps |
| Sending to a WhatsApp/Messenger/Instagram customer days later | refused (outside the 24 h window) | a WhatsApp template; or design the PRD around the window |
| A button whose data is a whole JSON object | Telegram takes 64 bytes | put an id in the data, keep the rest in a table |
| `edit` without passing the buttons again | the buttons disappear | pass `[buttons: …]` again to keep them |
| A listener rule that only inserts | a redelivery inserts twice | idempotent writes (§5.2) |
| Not answering a press (Telegram, VK) | the button spins, the person presses again | `answer(press)` first |
| Using `service.store.session`, `redirectPage` or "the current user" in a listener's rule | nothing - nobody is signed in | read who wrote from `message.from` |
| A connection on webhook that never receives | the address was not pasted / Cloudflare blocks it | the handover says where to paste it; the operator opens `/messenger-hook/` |

---

## 12 · Never

- NEVER write a token, an app secret or a webhook address into a rule, a table, the export or a test.
- NEVER call `service.messenger` from a predicate or a validation rule.
- NEVER assume an event arrives exactly once, or in order across listeners.
- NEVER write to people who did not write first where the messenger forbids it (Telegram, Viber, VK, Meta) — the send
  is refused, and an account doing it gets banned.
- NEVER invent `rep-objects` keys for connections or listeners — there are none.
