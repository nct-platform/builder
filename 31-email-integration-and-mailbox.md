# 31 · Email — the project sending as itself, and the mailbox on a page

> **Scope.** Two halves of one integration. The project **sending as itself**: every message a rule sends
> stops leaving from the platform's address and leaves from the customer's, over their SMTP or their
> provider's HTTP API. And the project **reading mail**: a mailbox polled into the project, a full mail
> client on a page, and `service.mailbox.*` in Groovy so a rule can turn an inbox into records.
> Read it the moment a PRD says *"send from our domain"*, *"the support inbox"*, *"when a customer emails
> us, open a case"*, or *"forward the signed copy to accounting"*.
> **Not here:** designing the MESSAGE — templates, placeholders, the PDF-then-send flow →
> [15](15-pdf-and-mail.md); the Groovy surface as a whole → [16](16-groovy-service-api.md); a process that
> starts without anybody clicking Start → [27](27-event-driven-process-start.md).

---

> ## ⛔ Read this before you plan anything: **none of this is in the `.mrjun`**
>
> The mail ACCOUNTS — hostnames, logins, passwords, API keys — live in the messaging service's own store
> with their secrets encrypted, and they are **not part of an export**. Neither is the integration's on/off
> switch. There is no key in `branches.json` for them and no `mrjun.py` command that writes one, because a
> credential that travelled inside a project archive would be a credential in every copy of that archive.
>
> **What you author offline:** the Mailbox plugin node and its settings, the Groovy rules that read and
> send, and the mail templates ([15](15-pdf-and-mail.md)).
> **What the recipient does once, live, after importing:** connects the account.
>
> Plan for that. A build that assumes an inbox exists and ships with no handover step produces a page that
> is correct and empty, and nobody can tell from looking at it whether the build is broken or the mailbox
> is simply not connected yet. §8 is the handover note; write it.

| | |
|---|---|
| The switch | Settings → **Developer** → **Integrations** → **Email** (live; Author or Developer **role group**) |
| The accounts | one or more per project, each an identity to send as and optionally a mailbox to read |
| What is authorable | the Mailbox plugin node (`properties.model`), Groovy rules, mail templates |
| With nothing configured | exactly the behaviour every project has always had — the platform account sends, and a Mailbox plugin renders an empty, explained state |
| Addressed from Groovy by | the account's **name**, never its id — `service.mailbox.send(account: "Support", …)` |

---

## 1 · The decision — which halves does this PRD actually need?

Four questions. Answer them in order; each one is independent of the others, and a project can want the
first and none of the rest.

1. **Must mail leave from the customer's own address?**
   Phrases: *"from our domain"*, *"customers should reply to us"*, *"no-reply@ourcompany"*, *"our
   mail server"*, *"we already pay for SendGrid"*.
   → one account with **sending** on, made the project's default. Nothing else changes: every
   `service.notification.mail.<alias>` call you have already written starts leaving from it.

2. **Must the project READ mail?**
   Phrases: *"the support inbox"*, *"suppliers send us the invoice by e-mail"*, *"when a signed copy comes
   back"*.
   → the same or another account, with **IMAP** (or POP3, if that is genuinely all the customer's server
   offers).

3. **Must a PERSON read it inside the project?**
   Phrases: *"the agent works the queue"*, *"we want to answer without leaving the system"*.
   → a page with the **Mailbox plugin** (§6).

4. **Must a RULE read it?**
   Phrases: *"open a ticket from each message"*, *"attach the PDF to the order"*, *"reply automatically"*.
   → `service.mailbox.*` in an EXECUTION rule (§7), usually on a scheduler
   ([27](27-event-driven-process-start.md) is the doc about that shape of trigger).

3 and 4 are not alternatives and **they do not interfere with each other** — which is the whole point of
the next section.

---

## 2 · The model: a message has **two** read states, and they never touch

This is the one idea in this document that is not like every other mail system, and everything else follows
from it.

| flag | set by | asked by | what it means |
|---|---|---|---|
| **user-read** | a person opening the message in the Mailbox plugin, or the Unread button | the folder's unread badge, `is:unread` in the search box | *the team has seen it* |
| **rule-read** | `mail.markRead()` / `service.mailbox.markRead(...)` in a rule | `service.mailbox.unread()`, `is:unhandled` in the search box | *automation has processed it* |

**Neither one can silence the other, deliberately.** A colleague opening a message to look at it must not
make an overnight importer skip it, and that importer must not empty the queue's unread count while
everyone is asleep. One flag would force a choice between those two, and every project would pick wrong at
least once.

The consequences you design around:

- A rule's idea of "new" is **its own**. `service.mailbox.unread()` means *no rule has handled this*, and
  it keeps meaning that however much the humans read.
- **Marking read is the rule's job and nothing does it for you.** A rule that reads a message and does not
  mark it will process the same message again on the next tick, forever. This is the same shape as
  [27](27-event-driven-process-start.md)'s idempotency rule and it has the same answer: mark the thing you
  consumed, in the same run that consumed it.
- **The person-facing mailbox can show both.** The plugin's `showRuleReadState` setting draws a mark on
  every message no rule has touched yet — off for everyday use, on while somebody is building or debugging
  an automation. It is the only screen in the product where both states are visible at once.

---

## 3 · Sending — what changes, and what deliberately does not

### 3.1 Nothing you have already written changes

`service.notification.mail.<alias>(...)` is untouched — same call, same templates, same placeholders
([15](15-pdf-and-mail.md)). What changes is only **which account the message leaves through**. That is the
design: a project should be able to be built, tested and handed over, and then have its own mail switched
on, without a single rule being edited.

### 3.2 How the sender is chosen, and why every branch falls back to the platform

In order, and the first answer wins:

0. **the platform's account, whenever *"Send the mail our rules send from our account"* is off** and the
   caller named none (§3.4);
0. **the platform's account, for the platform's own four messages** — password recovery, activation,
   invitation and reminder — when *"Also send the platform's own messages from our account"* is off
   (§3.4). The message is recognised by the template's alias, so renaming a copy of "Password Recovery"
   does not turn it into the project's own mail;
1. the account the caller NAMED — `service.mailbox.send(account: "Billing", …)`, or everything after
   `service.mailbox.account("Billing")` — if it can send;
2. the project's **default sending account**;
3. the project's only sendable account, when it has exactly one — two is not an answer, and the platform
   refuses to guess between them;
4. otherwise, and whenever the integration is switched off, **the platform's own account**.

Every failure mode in that list — integration off, no default chosen, the default deleted, the account
inactive, the account has no From address — ends on the platform account rather than on an error. Mail not
going out because a settings screen was half filled in is the one outcome nobody would notice in time.

### 3.3 The outbox has states now, and a failure is a row rather than a loop

Queued mail is retried with a growing delay, up to a bounded number of attempts. A **permanent** rejection
(a refused password, a rejected recipient — SMTP's 5xx, an API's 4xx) is not retried at all: it is recorded
with the provider's own words. Permanently failed messages stay visible in the mailbox's **Outbox** folder
instead of vanishing.

That matters to you when a rule sends: **a send is queued, not performed.** The rule returns before the
message leaves, so a rule cannot branch on whether delivery worked, and should not try. If a project needs
to know, the answer is the Outbox, not a return value.

### 3.3a The master switch is a CHOICE OF SENDER, not an on/off for mail

Worth saying plainly because the screen used to say it badly: switching the integration off does not switch
mail off. Mail goes out in both positions — the switch decides **whose account it leaves from**, the
project's or the platform's. That is why the card in the Integrations list reads **"Default account"** or
**"Platform account"** rather than "Enabled"/"Off" — "default" because that is the mechanism exactly:
mail that names no account leaves through the account marked default, and why the switch itself reads *"This project's mail leaves from our
default account / the platform account"*.

Tell the customer the same way. *"Do you want mail turned on?"* invites a yes to a question nobody asked;
*"should mail come from your domain or from the platform?"* is the decision they actually have.

### 3.4 Three policy switches worth knowing before you promise anything

- **Send the mail our rules send from our account** — default ON, and the one that decides whether the
  integration changes anything about SENDING at all. Off, the connection is **receive-only**: the mailbox is
  still polled and rules still read it, while everything the project sends keeps leaving through the
  platform account exactly as it did before. That is a real configuration and not a degenerate one — a
  project that answers a support mailbox from inside the platform has no wish to move its notifications. It
  governs the DEFAULT only: a rule that writes `account: "Billing"` has asked for something specific and
  gets it.
- **Fall back to the platform when our own send fails for good** — default ON, and leave it on. The same
  queue carries *"reset your password"*. A project that mistypes its SMTP password would otherwise lock
  out exactly the people who need that message, and the way back in is the message that cannot be sent.
- **Also send the platform's own messages from our account** — default ON. Password recovery, invitations
  and reminders then come from the customer's domain too. Turn it off if the customer wants their own
  address used only for mail their own rules send.

### 3.5 The daily e-mail quota stops applying

A project that sends through its own provider is spending its own money, so the platform's per-project
daily limit is not applied to it. If a PRD leans on a send volume that the platform quota would have
blocked, the answer is "configure your own account", and it is worth saying so in the handover.

---

## 4 · Transports — SMTP, the shipped HTTP APIs, and the one you describe yourself

| transport | when |
|---|---|
| **SMTP server** | the default answer. Works with every provider and with a relay on the customer's own network, and is the only option for a mailbox on their own server |
| **Mailgun / SendGrid / Postmark / Resend / Brevo / SparkPost / Mailjet / Elastic Email / SMTP2GO / Unisender Go** | the provider's HTTP API. Reachable when outbound port 587 is blocked — which it is by default on several clouds and most corporate networks — and it returns a provider-side message id that can be traced in their dashboard |
| **Custom HTTP API** | anything else at all: a regional provider, an internal relay behind a gateway, a service that merely happens to deliver mail |

The settings screen carries a **provider picker** with the well-known hosts, ports and encryption modes
already filled in, and a note per provider saying the thing that is otherwise learned by losing an evening
(Google and Yahoo refuse your login password; Microsoft 365 needs SMTP AUTH enabled per mailbox; SendGrid's
SMTP username is the literal word `apikey`). Everything it fills stays editable.

### 4.1 The custom API, and why it exists as a first-class thing

Every shipped provider above is **one description** — a URL, an auth scheme, a body template, a response
mapping — executed by one engine. "Custom" is not a lesser path around that engine; it is the same engine
with the project's own description, so it gets the same retries, the same failure recording and the same
Test button. The practical effect: a provider that changes a field name, or a corporate gateway that wants
one extra header, is an **edit the customer can make on the day** instead of a support ticket waiting for a
platform release. The editor starts from a copy of whichever shipped provider is closest.

What a description can express, and what you can promise a customer without checking:

- **URL, method, extra headers** — any of them may carry placeholders.
- **Authentication** — bearer, HTTP Basic (with the username on the spec, or a `user:secret` pair packed
  into the key field), a named header, a query parameter, or the key appearing only inside the body.
- **Body** as JSON, form-encoded or multipart, from a template.
- **Two repeaters** — one rendered per recipient and one per attachment. This is what removes the need for
  a provider list: every JSON mail API wants recipients as an array of objects and every one of them spells
  the object differently, and a repeater with `{{email}}` in it covers all of them including the next one.
- **Response mapping** — which status range counts as success, where the message id is, where the error
  text is.

The placeholder vocabulary is offered as clickable chips above the body editor, so it does not have to be
memorised: `{{fromHeader}} {{from}} {{fromName}} {{to}} {{cc}} {{bcc}} {{toJsonArray}} {{recipients}}
{{ccRecipients}} {{bccRecipients}} {{subject}} {{html}} {{text}} {{replyTo}} {{attachments}} {{apiKey}}
{{apiDomain}}`.

> **Escaping is the engine's job, never the template author's.** A subject containing a double quote is not
> exotic; it is Tuesday. Values are escaped for the body format in force when they are substituted, so a
> quote cannot break out of a JSON string and an ampersand cannot add a form field. The placeholders that
> name a JSON SHAPE (`{{toJsonArray}}`, `{{recipients}}`, `{{attachments}}`) are inserted as JSON because
> the engine produced them; everything else is escaped. A placeholder the engine does not recognise is left
> exactly as written — a body may legitimately contain handlebars meant for something downstream.

> **Empty fields are removed before sending.** `"cc": ""` reaches several providers as a recipient with no
> address and is rejected outright, and an empty `reply_to` overrides the account's own with nothing.

**The port and the encryption are one decision, not two.** 587 is the STARTTLS port (the conversation
starts in plain text and is upgraded); 465 is encrypted from the first byte. Choosing one while the
other's port is in the box produces `Unsupported or unrecognized SSL message` — a true description of what
the library saw and a useless description of what to change. The screen moves the port with the encryption
whenever the port is a standard one, leaves a hand-typed port alone, and explains the pair when it still
disagrees. Incoming is the same: 993/995 are encrypted from the first byte, 143/110 are upgraded.

**When a provider rejects the password, read the note.** Gmail answers a correct password with
`[AUTH] Username and password not accepted.` because it wants an App Password, not the login one. The
provider's note travels with the failure for exactly this reason — the customer has not done anything
wrong, and the next step is on the provider's side.

**Preview before you send.** The screen renders the exact request against a sample message, with the key
redacted, using the same code that sends — so the preview cannot drift from the truth. Use it while writing
a custom description; it is faster than reading a provider's documentation twice.

---

## 5 · Receiving — what a polled mailbox actually does

| setting | what to tell the customer |
|---|---|
| **IMAP** vs **POP3** | IMAP unless their server offers nothing else. IMAP has folders and stable ids, so a second poll knows what it already has; POP3's own answer to "what is new" is "here is everything". The two live at different addresses (`imap.gmail.com:993` against `pop.gmail.com:995`), and choosing a known provider moves the incoming server with the protocol — a hand-typed host is left alone |
| **Folders to read** | IMAP only — comma separated, `INBOX` by default. Naming them is deliberate: an Archive folder holds years of mail, and a first poll that walks it fetches tens of thousands of messages nobody asked for. The screen can **discover** the real folder names from the server. On POP3 the field is not shown at all: the protocol has one mailbox and no folders |
| **Import history (days)** | 0 by default — only mail that arrives from now on. Connecting a five-year-old mailbox should not import five years before anybody has decided that is wanted |
| **Mark read on the server too** | IMAP only, and off by default. The mailbox is usually also open in somebody's own mail client, and silently marking their inbox read is a surprise rather than a feature. POP3 has no read flag, so the setting is not offered there |
| **Delete after reading** | POP3 only, and only when the customer means it |
| **Keep stored mail for (days)** | a retention window, because an inbox polled for a year is a table that grows without an upper bound inside the customer's database |

Two mechanics worth knowing because they shape what you can promise:

- **A message is stored once.** Re-polling, a reconnect, a server that resets its ids — all of them land on
  the same stored message rather than a duplicate. So a rule that reads the mailbox does not have to
  de-duplicate; it has to mark what it handled (§2).
- **Conversations are grouped by the message's own reference chain**, computed when it is stored. That is
  what the reply/forward threading and the reader's conversation strip use. It is done on arrival, not at
  read time, because grouping a folder by a computed value would be a full scan on the one screen where
  that is felt.

---

## 6 · The Mailbox plugin — the node you DO author

```
pluginName : nct.mailbox.plugin
config slot: properties.model   (JSON)
per page   : ONE
```

A three-pane mail client: accounts and folders, the message list, the reading pane. It is usable with an
EMPTY config — dropped on a page and never configured it shows every account the project has, the inbox, a
reading pane and a compose button. **Every setting takes something away**, which is how a page becomes *the
support queue* rather than *everybody's mail*.

| field | type | default | what it decides |
|---|---|---|---|
| `accountIds` | array of account ids | `[]` | which accounts this page shows. **Empty means ALL** — not none. Leave it empty unless the page is meant to be one queue |
| `defaultAccountId` | string | absent | selected on arrival; absent = all together |
| `defaultFolder` | string | `INBOX` | `INBOX` / `SENT` / `OUTBOX` / `ARCHIVE` / `TRASH`, or any folder the mailbox has |
| `pageSize` | int | `30` | rows per page |
| `previewPosition` | `RIGHT` \| `BOTTOM` | `RIGHT` | where the message is read. `BOTTOM` suits a narrow page or a long list |
| `allowCompose` | boolean | `true` | the New button |
| `allowReply` | boolean | `true` | reply / reply-all / forward. Separate from compose: a read-only queue may still want replies |
| `allowDelete` | boolean | `true` | the Delete button |
| `showConversation` | boolean | `true` | the strip of other messages in the same conversation, under the reader |
| `refreshSeconds` | int | `60` | how often the browser asks whether anything new arrived. 0 is off. It asks the PLATFORM, not the mail server — the server is polled on its own schedule — so it is cheap |
| `showRuleReadState` | boolean | `false` | draws a mark on messages no rule has handled (§2). Off for everyday use; on while building an automation |
| `localizedTitles` | map, locale → string | absent | the heading, per locale ([20](20-localization.md)) |

**`accountIds` holds ids, and ids only exist once an account has been created live.** So a page authored
before the customer connects anything must leave it empty — which is also the setting that keeps working
when they later add a second account. Only narrow it when you know the ids, i.e. when changing a live
project ([28](28-support-mode-over-mcp.md)).

Placement, in the terms [01](01-content-model-and-pages.md) uses: the plugin is a page's main content, one
per page. It is a workplace, not a widget — the same rule that keeps one table to a page
([04](04-crud-table-plugin.md)) applies to it for the same reason.

What the reader gets that is worth knowing when you write the PRD response: folders with unread counts,
search with the operators people already know (`from:` `to:` `subject:` `is:unread` `is:flagged`
`has:attachment` `after:` `before:`, plus `is:unhandled` for the rule-scope flag), reply / reply-all /
forward with the original quoted, attachments, flags, archive and trash, a compose window with a rich-text
toolbar and file attachments, and a gear that goes to the account settings.

> **Remote images are blocked until the reader asks for them**, and the message body renders inside a
> sandboxed frame. Both are deliberate and neither is configurable: the body was written by whoever sent
> the message, and a tracking pixel is a remote image that tells the sender the address is live and read.

---

## 7 · `service.mailbox.*` — reading and answering mail from a rule

Full member list in [16](16-groovy-service-api.md). What matters here is the shape.

**Reading is available in every kind of rule; changing anything is available only in an EXECUTION rule.**
A predicate is evaluated for an answer, possibly once per row of a table; a validation rule runs on every
submit attempt, including the ones that fail. Marking mail handled from either would consume the inbox as a
side effect of deciding whether to draw a button. The members with side effects refuse there, with an
explanation naming the rule kind — the same arrangement `service.workflow` uses.

### 7.1 The canonical rule: an inbox into records, idempotently

```groovy
// EXECUTION rule, usually on a scheduler ([27] is the doc about that trigger).
def handled = 0

service.mailbox.unread(account: "Support", folder: "INBOX", limit: 50).each { mail ->

    // Everything this rule needs is already loaded - subject, sender, bodies, attachment metadata.
    def ticket = service.crud.ticket.create([
        subject    : mail.subject,
        fromAddress: mail.from,
        fromName   : mail.fromName,
        body       : mail.text,
        receivedAt : mail.receivedAt,
        sourceRef  : mail.messageId        // so the record can be traced back to the message
    ])

    // Attachments are fetched only when asked for: mail.attachments is metadata, bytes() is a fetch.
    mail.attachments.each { file ->
        service.crud.ticketFile.create([
            ticketId: ticket.id,
            fileName: file.fileName,
            content : file.bytes()
        ])
    }

    mail.reply("<p>Thank you — this is now ticket ${ticket.number}.</p>")

    // ⛔ The line that makes the rule safe to run every five minutes. Without it this message is
    //    processed again on the next tick, and the next, forever.
    mail.markRead()
    handled++
}

return "handled ${handled} message(s)"
```

Four things in that rule are worth copying verbatim into any variant:

1. **`limit:`**. The default is 50 and it is a default, not a cap you should raise casually — a rule that
   loads a thousand messages with their bodies is a rule that times out on the day the backlog arrives.
   Handle a slice per tick; the next tick takes the next.
2. **`markRead()` in the same iteration as the work.** Not after the loop, and not in a second rule.
3. **A traceable reference on the record** (`messageId`), so somebody can answer "where did this row come
   from" six months later.
4. **`bytes()` only for the attachments you actually store.** The metadata is free; the content is a fetch.

### 7.2 Sending from a rule, outside any template

```groovy
service.mailbox.send(
    account: "Billing",                       // by NAME; omit to use the project's default
    to     : [invoice.customerEmail],
    subject: "Invoice ${invoice.number}",
    html   : "<p>Please find invoice ${invoice.number} attached.</p>",
    attachments: [[fileName: "invoice.pdf", content: pdfBytes, contentType: "application/pdf"]]
)
```

**Which of the two sending calls to use** is a real decision, not a preference:

| use | when |
|---|---|
| `service.notification.mail.<alias>` ([15](15-pdf-and-mail.md)) | anything a designer should own — a branded notification, a statement, an invitation. The project can restyle it without a rule being touched |
| `service.mailbox.send` | text a rule composed: a reply, an operational note, a forward. There is nothing for a designer to own |

### 7.3 Traps

- ⛔ **`markRead()` is the RULE's flag.** It does not mark the message read for the people looking at the
  same mailbox, and it is not supposed to.
- ⛔ **`unread()` is not "new mail".** It is "no rule has handled this". A message a rule marked and then a
  later rule wants again needs `markUnread()`, explicitly.
- ⛔ **A reply threads, marks the original answered and files a copy** — all three. A `send()` that merely
  quotes an old message does none of them and starts a new conversation in the recipient's client.
- ⛔ **Reply-all excludes the account itself**, and that is load-bearing: this mailbox is polled, so a reply
  including its own address comes back and can be replied to again. Do not reconstruct the recipient list
  by hand unless you reproduce that.
- ⛔ **Naming an account that does not exist raises an error**, so a renamed account fails where the author
  can see it rather than quietly sending from the default.

---

## 8 · What you cannot check offline, and the handover note

`validate` sees the plugin node and the rules. It cannot see whether a mailbox exists, whether a password
is right, or whether anything was ever polled — none of that is in the bundle. So:

**What the offline gate does NOT catch, and you must therefore drive live** ([30](30-live-test-bugfix-and-autotest.md)):

- that the account authenticates at all (the settings screen has **Test connection** and **send a test
  message**; use both — an SMTP account is proven by connecting, an HTTP API account only by sending);
- that the folder names are the ones the server actually has (the screen can discover them);
- that a message arrives, is stored, and appears in the plugin;
- that the rule marks what it handled — which you see by running the scheduler twice and checking nothing
  is processed a second time.

### 8.1 The password the customer will bring is the wrong one

Every free provider worth connecting now refuses the mailbox password over IMAP and SMTP and wants an
**app password** instead — a separate 16-character secret generated in the account's security settings.
This is the single most common reason a correctly built integration does not work on handover day, so say
it before they try:

- **Gmail** — needs 2-Step Verification on, then an app password at *myaccount.google.com/apppasswords*.
- **Yahoo** — *Account Security → External connections → Create app password*. The button is greyed out on
  accounts Yahoo does not consider eligible; the tooltip says so, and no setting on our side changes it.
- **iCloud** — an app-specific password from *appleid.apple.com*, and the two legs want DIFFERENT
  usernames: IMAP takes only the part before the `@`, SMTP takes the whole address.
- **Microsoft 365, Yandex, Zoho, Fastmail** — the same idea, their own menu.

Two traps that make a right password look wrong:

1. **The spaces are not part of it.** Providers display the app password in groups of four. The platform
   strips whitespace for the providers that work this way, but a customer typing it into anything else
   will be told the password is invalid.
2. **Repeated failures lock the account out temporarily.** Yahoo answers
   `535 5.7.0 (#AUTH005) Too many bad auth attempts` and keeps answering it *whatever you send next* — so
   after fixing the password, WAIT before testing again, or the right password looks wrong too. The
   incoming leg is usually not locked the same way, so **Receiving** is the faster half to test first.

**The handover note to write into the delivery** — copy this shape:

> This project sends and reads mail through your own account. Before it can do either, open
> **Settings → Developer → Integrations → Email**, add an account (pick your provider from the list — most
> settings fill themselves in), press **Test connection**, make it the default, and switch the integration
> on. Until then, mail leaves from the platform's address and the Mail page stays empty. The rules that
> read the inbox expect the account to be named **`<name you used in the rules>`**.

### What a re-import does to a connected mailbox: **nothing**

Worth stating on its own, because doc [30](30-live-test-bugfix-and-autotest.md) has you re-importing the
same project repeatedly while fixing it, and the question arrives the first time a customer has already
connected their mail.

| event | what happens to the accounts, the stored mail and the switch |
|---|---|
| **export** | not included. The archive carries mail TEMPLATES and nothing else mail-shaped |
| **re-import into a live project** | **untouched.** The import wipes and re-creates DEFINITIONS - forms, rules, contexts, queries, templates - and mail accounts are configuration, not a definition. They survive every re-import, which is the only behaviour that makes the fix loop usable |
| **environment publish / a tag** | not carried. An environment connects its own account, or sends through the platform |
| **the project is DELETED** | removed - accounts, credentials, stored messages, poll positions and queued mail, all of it. Leaving encrypted credentials behind for a project that no longer exists is the kind of remnant nobody goes looking for |
| **a NEW project on a realm/client pair a deleted project used** | swept on creation, so the new project cannot inherit the previous occupant's mailbox |

So the accounts are configured **once**, by the recipient, and they stay configured. Nothing you do to the
export can create them and nothing short of deleting the project removes them.

**Known gaps, said out loud:**

- accounts, credentials and the on/off switch are **not** in an export, so they do not travel with a
  re-import, an environment publish or a tag — they are configured once per installation of the project;
- a rule cannot ask whether a queued message was ultimately delivered; the Outbox is the answer;
- there is no inbound webhook or push — mail arrives on a poll, so "instant" in a PRD means "within the
  poll interval", and that interval is a setting the customer controls.
