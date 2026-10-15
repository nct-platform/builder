# 33 · PubSub — the project talking to message brokers (MQTT, RabbitMQ, Kafka, ActiveMQ)

> **Scope.** Two halves of one integration. A rule **publishing** a message to a broker the customer already
> runs — a command to a device, an event for another system, a record for a stream. And the project
> **listening**: a broker's topic or queue wired to one or more rules, so that the arrival of a message IS the
> trigger — sensor readings into records, an event from another system opening a case, a Kafka topic bridged
> into a queue. Read it the moment a PRD says *"the devices report to an MQTT broker"*, *"we publish to our
> RabbitMQ / Kafka / ActiveMQ"*, *"when another system sends an event, create …"*, *"IoT"*, *"telemetry"*,
> *"message queue"*, or *"integrate with <system> over a queue/bus"*.
> **Not here:** another system calling the project over HTTP → [32](32-public-api.md); mail →
> [31](31-email-integration-and-mailbox.md); a process that starts without anybody clicking Start (the rule
> a listener runs usually IS that starter) → [27](27-event-driven-process-start.md); the Groovy surface as a
> whole → [16](16-groovy-service-api.md).

---

> ## ⛔ Read this before you plan anything: **none of this is in the `.mrjun`**
>
> The CONNECTIONS — kind, version, host, port, credentials, certificate, the Publish and Listen switches —
> and the LISTENERS (what each listens to and which rules it runs) live in the messaging service's own
> store, with the password encrypted, and are **not part of an export**. There is no key in `branches.json`
> for them and no `mrjun.py` command that writes one: a credential that travelled inside a project archive
> would be a credential in every copy of that archive.
>
> **What you author offline:** the **rules** — the ones that publish, and the ones a listener runs — and
> everything those rules touch (tables, CRUD methods, pages that show the records a listener creates).
> **What the recipient does once, live, after importing:** adds the connection, adds the listeners, and picks
> the rules by name.
>
> Plan for that. A build that assumes a broker is connected and ships with no handover step produces rules
> that are correct and a project that never receives a message, and nobody can tell from looking at it
> whether the build is broken or the broker is simply not connected yet. §8 is the handover note; write it.

| | |
|---|---|
| The switch | Settings → **Developer** → **Integrations** → **PubSub** (live; Author or Developer **role group**) |
| The connections | any number per project (up to 25), of any mix of kinds, each with its own host, credentials and **alias** |
| What is authorable | EXECUTION rules (publishing; run by a listener), and what they read and write |
| With nothing configured | `service.pubsub` does not appear in the editor's completion, and a call to it fails with a sentence saying there is no such connection — it never hangs and never writes anywhere |
| Addressed from Groovy by | the connection's **alias**, never its host — `service.pubsub.plant.publish(…)` |
| Runs where | **EXECUTION rules only.** A predicate and a validation rule get the namespace and every member refuses |
| A listener's rule runs as | the platform on its own authority (like a scheduler tick), with the **author who last saved the connection** as the acting user — nobody is signed in and no browser is waiting |

---

## 1 · The decision — which halves, and which broker?

Answer in order; each is independent of the others, and a project can want the first without the second.

1. **Must the project SEND to a broker?** *"command the device"*, *"publish an event for the ERP"*,
   *"push the status to our bus"*.
   → a connection with **Publish** on, and `service.pubsub.<alias>.publish(…)` in an EXECUTION rule (§4).
2. **Must the project REACT to what arrives?** *"when a sensor reports"*, *"when the other system sends an
   order"*, *"the gateway posts its readings"*.
   → a connection with **Listen** on, one **listener** per topic/queue, and an EXECUTION rule per thing
   to do (§5).
3. **Which broker?** The PRD or the customer names it — do not choose one for them. Use this table to
   recognise it and to know what the **version** field means:

| the customer says | kind | the version box | default port (TLS) |
|---|---|---|---|
| *MQTT, Mosquitto, EMQX, HiveMQ, AWS IoT Core, device gateway, sensors* | **MQTT** | a real choice: **3.1.1** (the safe default — every broker and nearly every device gateway speaks it) or **5.0** (newer brokers; adds shared subscriptions and session expiry) | 1883 (8883) |
| *RabbitMQ, AMQP, exchanges, queues* | **RabbitMQ** | none — AMQP 0-9-1 is spoken by every RabbitMQ 3.x and 4.x; the box shows it read-only | 5672 (5671) |
| *Kafka, topics, event streaming, Confluent, MSK* | **Kafka** | none — the client negotiates with the broker, 0.10 up to 4.x; the box shows it read-only | 9092 (9093) |
| *ActiveMQ, JMS, Artemis, OpenWire* | **ActiveMQ** | **Classic 5.x / 6.x** or **Artemis 2.x** — one client reaches both over OpenWire; the choice only tells it how to behave toward Artemis. The Host box takes a failover pair or cluster as a comma-separated list | 61616 (61617) |

**"Version" means the protocol the connection speaks, not the broker's release.** Only MQTT has two
protocols to choose between; the others negotiate on their own, which is why their box is read-only. The
platform was exercised against Mosquitto 1.6 and 2.0 (3.1.1 and 5.0), RabbitMQ 3.8 / 3.13 / 4.x, Kafka 3.7 /
3.9 / 4.0, ActiveMQ Classic 5.15 / 5.18 / 6.1 and Artemis 2.40 — with the same client for each kind. A PRD
that names an older or newer release than those is not a reason to promise anything different; it is a
reason to say in the handover note that **Test connection** is the proof.

4. **Do the devices speak to the platform, or to a broker?** Always a broker. The platform is a CLIENT of the
   customer's broker; it does not accept connections from devices. A PRD that says "devices connect to the
   platform over MQTT" needs a broker in between, and that broker is the customer's decision.

---

## 2 · The model: a connection, an alias, listeners

```
connection  alias=plant   kind=MQTT 3.1.1   host=broker.example.com:1883   [Publish ✔]  [Listen ✔]
   └ listener  source=sensors/#   reads as=Detect automatically   rules: [Store reading] → [Check alarm]
   └ listener  source=alarms/+    reads as=JSON                   rules: [Page the on-call]
```

- The **alias** is the name rules use: letters, digits and underscores, starting with a letter, at most 40,
  **unique within the project ignoring case**. It cannot be a Groovy keyword nor one of the members of
  `service.pubsub` itself (`list`, `channel`, `aliases`, `channels`, `get`, `alias`, `exists`, `names`, `has`).
  The screen says so while it is typed. Choose it like a variable name: `plant`, `erpBus`, `orders_kafka`.
- **Publish** and **Listen** are independent switches. A connection that only listens is not offered to
  rules; one that only publishes holds no listening connection.
- A **listener** is one subscription: a *source* (what the kind calls it — an MQTT topic filter, a RabbitMQ
  queue, a Kafka topic or several, an ActiveMQ `queue:NAME` / `topic:NAME`), how its messages are *read*,
  the **rules to run in order**, and how many *attempts* each rule gets.
- **A connection is held by exactly one instance of the service.** Several instances share the database and
  agree, through a lease, on who listens to a given connection; if the holder dies, another takes over
  within about a minute. This is what stops every message being handled twice. (Messages published to the
  broker in that gap are the broker's to keep — see MQTT sessions in §5.4.)
- Credentials are stored encrypted and **never shown again**: the password box is empty on every re-open and
  a blank box on save means *keep the stored one*. **Test connection** may use the stored password only while
  the host, port and user name are unchanged — change any of them and it asks for the password again, so a
  stored credential is never sent to an address nobody saved. TLS has no "ignore certificate errors" switch — a
  broker with a private CA is trusted by pasting its certificate; this is deliberate.
- **What the broker remembers is tied to the connection, not to its alias.** A Kafka consumer group's offsets, an
  MQTT persistent session, an ActiveMQ durable subscription all hang off an identifier the platform derives
  from the connection's internal id, so renaming the alias (fixing a typo) does not abandon them or replay a
  topic from the start.
- The platform refuses to connect to link-local addresses (the range that holds cloud metadata services) and,
  on an installation that has switched it on, to loopback and private networks. A refusal says so on the form.

---

## 3 · Nothing you have already written changes

A project with no connection behaves exactly as before: no listening connection exists, nothing reaches a
broker, and the editor does not even offer `service.pubsub`. Adding the integration changes nothing for a rule
that does not use it, and a rule that does use it can be shipped **before** the customer has connected a
broker — it will fail with a sentence that names the alias and says where to add it, which is the right
failure.

---

## 4 · Publishing — `service.pubsub.<alias>.publish(…)`

```groovy
service.pubsub.plant.publish('sensors/room1/command', [setpoint: 21.5])                  // destination, payload
service.pubsub.plant.publish('sensors/room1/command', [setpoint: 21.5], [qos: 1, retain: true])   // + options
service.pubsub.plant.publish('sensors/room1/command', [setpoint: 21.5], qos: 1)         // named options after the positionals
service.pubsub.plant.publish(destination: 'sensors/room1/command', payload: [setpoint: 21.5], qos: 1)
service.pubsub['plant'].publish(…)         // the same object — for an alias held in a variable
service.pubsub.list()                      // [[alias:, kind:, version:, description:], …] — what CAN publish
```

It returns `[ok: true, reference: '…', millis: 12, bytes: 38]` — `reference` is the broker's own position when
it has one (a Kafka `topic-partition@offset`, a JMS message id, an exchange/routing key).

**The destination is the kind's own word:**

| kind | destination means | options a single call may pass (all optional) |
|---|---|---|
| MQTT | the topic. No wildcards (`+`/`#` are for subscribing) | `qos` (0/1/2, default from the connection), `retain` (true/false) |
| RabbitMQ | the **routing key**; with the default exchange that is the queue name | `exchange` (default from the connection), `persistent` |
| Kafka | the topic | `key` (the record key — what partitions the stream) |
| ActiveMQ | `queue:NAME` or `topic:NAME`; a bare NAME uses the connection's default type | `defaultType`, `persistent`, `timeToLiveMs` |

Every kind also takes `headers` (a map; MQTT 5.0 sends them as user properties, 3.1.1 has nowhere to put them
and drops them) and `contentType`. The connection's Publish section also holds settings that are fixed when
the connection to the broker is opened — RabbitMQ's *wait for confirmation*, Kafka's *acks* — and those are
**not** options of a call. **An option the kind does not have, or that a call cannot change, is refused with
the list of the ones it does** — `service.pubsub.plant.publish('t', x, [exchange: 'e'])` on an MQTT connection
says so instead of quietly ignoring it. Option values are checked like the screen checks the defaults
(`qos: 7` is refused).

**The payload.** A string goes as text. A map, a list or any other object goes as **JSON**. A number or a
boolean goes as its text (`21.5`). A `byte[]` goes as binary. `null` is an empty message. The limit is 1 MB
(an installation can change it). What the receiving end sees is exactly those bytes — if the other system
expects a different envelope, build the string yourself (`groovy.json.JsonOutput.toJson(...)` for JSON of a
particular shape).

**What "published" means**, per kind — the call returns when the broker has taken the message, not when anyone
has read it: MQTT QoS 1/2 waits for the broker's acknowledgement (QoS 0 is fire-and-forget by definition),
RabbitMQ waits for the publisher confirm (on by default, a setting of the connection), Kafka waits for the
acknowledgements the connection asks for (`acks=all` by default), ActiveMQ persistent messages are written
before the call returns.

**When it fails the rule fails** — with a sentence, not a stack trace: the alias that does not exist (and
which ones do), a connection that is switched off or has Publish off (and where to change that), a refused
option, a broker that did not answer (with the broker's own words and, where the failure is a known mistake, a
hint: the TLS switch not matching the port, rejected credentials, a name that does not resolve). A
connection that was dropped since the last publish is reopened once automatically, so the rule that happens
to publish first after a broker restart is not the one that finds out.

> **⛔ Publishing is a side effect, so only an EXECUTION rule may do it.** A predicate or a validation rule
> may be evaluated many times for one answer — once per table row, once per submit attempt — and a message
> sent as a side effect of drawing a button is a message nobody decided to send. In those the namespace
> exists and **every** member throws an explanation. This includes an execution rule called **from** a
> predicate with `service.rule("…")`. `mrjun.py validate` reports it (§9).
> A CRUD GROOVY method runs as an execution rule and may publish.

**Hints.** In an execution rule the editor completes `service.pubsub.`, then the project's aliases, then the
three `publish` forms with the destination's name and an example written for that kind. Option keys inside a
map cannot be completed (the editor cannot offer map keys), so they are listed in the method's description.

---

## 5 · Listening — a message arrives, rules run

### 5.1 What a rule receives

The rule is an ordinary EXECUTION rule. It reads two attributes:

```groovy
def message = context.data.getAttr('message')     // the payload — see "reads as" below
def meta    = context.data.getAttr('pubsub')      // where it came from
```

**Use `context.data.getAttr(…)`, not `attrs.get(…)`.** The attributes are stored as JSON; `getAttr` turns them
back into Groovy values (a JSON object into a map, an array into a list, a number into a number),
`attrs.get` hands you the raw JSON node. (The same mechanism the autocomplete rules use for the text typed so
far: `attrs.get('filterBy')`.)

**"Message is read as"** is set per listener and decides what `message` is:

| reads as | `message` is | a message that does not fit |
|---|---|---|
| **Detect automatically** (default) | a JSON object/array → **Map/List**; a plain number of at most 15 digits → **Integer/Long/number**; `true`/`false` → **Boolean**; anything else → **String**; bytes that are not valid UTF-8 text → a **Base64 string** | never fails |
| **Text** | always a String, even if it looks like JSON or a number | not valid UTF-8 → failed |
| **JSON** | a Map/List/value | not valid JSON → failed |
| **Number** | an Integer/Long/number | not a number → failed |
| **Binary** | the bytes as a Base64 String | never fails |

"Detect" is deliberately cautious with numbers: `007`, `1e5`, `+5` and any digit string longer than 15 are left
as **strings** (a 16-digit id turned into a rounded number is a bug nobody can see). Choose *Number* to force
one and *Text* to forbid it. A decimal compares like any number (`message.temp > 30`) — test the value, not its
class.

**`pubsub`** is a map: `alias`, `kind`, `source` (the listener's filter/queue), `listener` (its name), `destination`
(the topic/routing key/queue the message ACTUALLY arrived on — more specific than a wildcard filter), `key` (a
Kafka record key or JMS message id), `headers` (a map), `receivedAt` (ISO instant), `redelivered`, `qos`,
`retained`, and `step` / `steps` (which rule of the chain this is, from 1).

*Create rule* on a listener opens the rule editor already holding those two lines and a comment explaining
them.

### 5.2 What happens to a message — the delivery contract

| situation | what happens |
|---|---|
| everything works | the rules run **in order**, each with the same message; **then** the broker is told the message is handled |
| a rule throws | it is tried again (**Attempts per rule**, default 3, after 1 s, 2 s, 4 s …). The retry **resumes at the rule that failed**; rules before it do not run again |
| a rule runs out of time (the executor answered, then the rule did not finish within about 2 minutes) | this is the **rule's** failure and spends an attempt — it may well still be running, so a rule a message triggers must be short; hand heavy work to a queue or a scheduler |
| a rule keeps failing | after its attempts the message is **given up on**: the chain stops there (later rules do not run), the broker is told it is handled so it cannot block everything behind it, and the failure is counted and shown on the listener (*failed*, *last error*) |
| the message is not what the listener says (invalid JSON in a JSON listener, over 1 MB) | dropped at once and counted — no retry changes its bytes |
| the rule executor is down or unreachable | the message **waits** — attempts are not spent on an outage — with a growing pause (to 30 s), and the listener shows why. When the executor is back the backlog is processed in order. Nothing is dropped |
| the rule was **deleted** (or the platform's own credentials are refused) | the same: the message waits, and the listener says *"The rule … no longer exists. Pick another rule for this listener, or restore it"*. Fix the listener and it carries on |
| one message occupies the listener for 10 minutes (an installation setting) | the platform closes that connection and opens it again, so the broker offers the message again; nothing behind it is handled or acknowledged in the meantime |
| the service stops or crashes between "the rules finished" and "the broker was told" | the broker offers the message again — **the rules run a second time** |
| an MQTT listener is too far behind (1000 messages waiting) | the newest messages are dropped and counted rather than letting memory grow without limit; the listener says *too far behind*. (RabbitMQ, Kafka and ActiveMQ slow the broker down instead: nothing is fetched faster than it is handled) |

That is **at-least-once** delivery, and it has one consequence the author must own:

> **⛔ Write listener rules so that running twice for the same message is harmless.** A retry after a failure,
> a redelivery after a restart and a duplicate sent by the other system all run the rule again.
> The same discipline [27](27-event-driven-process-start.md) §5 states for opening cases: key the work on
> something the message carries — a business id in the payload, the Kafka `key`, a header — and have the rule
> check or claim it (a unique column and `INSERT … ON CONFLICT DO NOTHING` in a CRUD method is the cheap,
> race-free way). A rule that only ever inserts will insert the message twice.

- **Order.** One listener handles its messages one at a time in the order the broker delivers them. Two
  listeners are independent of each other and run in parallel. Kafka orders per partition (use a record
  `key` to keep related messages together); the others per queue/topic.
- **What a listener's rule cannot do:** nobody is signed in and no browser waits, so
  `service.store.session` stores nothing, `service.redirectPage` does nothing, and access checks that depend
  on "the current user's role" see the **author** who last saved the connection. A rule that must act on
  behalf of the message's sender has to take that from the payload, not from the session.
- **What it can do:** everything an execution rule does when nobody is watching — write through CRUDs,
  call other rules, send mail, start a process (`service.workflow.start`, see [27](27-event-driven-process-start.md)),
  **publish to a broker** (including the same one: a rule may answer a message on another topic. Do not publish
  to a topic the same listener listens to — that is a loop).

### 5.3 The common shape

A device reports, the rule stores it once, and raises a case when something is wrong:

```groovy
// Rule "Store reading" — listener on sensors/+/temperature, reads as JSON
def reading = context.data.getAttr('message')                 // [id: 'r-8812', temp: 31.5]
def topic   = context.data.getAttr('pubsub').destination      // sensors/room1/temperature
def room    = topic.split('/')[1]

// idempotent: `insertIfNew` is the PROJECT's own CRUD method, SQL `INSERT … ON CONFLICT (external_id) DO NOTHING`
// over a unique index on external_id - so the second run of the same message writes nothing
service.crud.reading.insertIfNew([externalId: reading.id, room: room, temp: reading.temp])
```

### 5.4 Per-kind listener options — and the one that decides whether you lose messages

| kind | source | options worth knowing |
|---|---|---|
| MQTT | topic filter: `+` one level, `#` the rest (`sensors/#`) | **QoS** (default 1); **Shared subscription group** (5.0 only) — several consumers of one group split the messages instead of each getting all of them |
| RabbitMQ | the queue name | **Create the queue if missing** (a durable queue; with an optional exchange binding and key), **Prefetch**. Without *create*, a missing queue is reported on the listener, not created |
| Kafka | a topic, several separated by commas, or `regex:PATTERN` | **Consumer group** (default: one per listener), **Where to start** — *latest* (only new records) or *earliest*, applied the first time the group reads the topic; afterwards it continues where it stopped |
| ActiveMQ | `queue:NAME` / `topic:NAME` (bare = queue) | **Durable subscription name** (topics only — without one a topic subscriber misses what is sent while it is away), **Message selector** (SQL-92 on headers) |

> **⛔ MQTT and "while the platform was away".** The connection's **Clean session** switch (default **on**) means
> the broker forgets this client between connections, so a message published while the platform was
> restarting, or while another instance was taking over (§2), is **gone**, and a QoS 1 message the platform
> had received but not yet finished is not offered again. For telemetry that does not matter. For anything
> that must not be lost, switch **Clean session off** (the broker then keeps the subscription and queues
> QoS 1/2 messages for the stable client id the connection uses) and use QoS 1 or 2 on the listener — and the
> publisher must publish at QoS 1 or 2 too, because a QoS 0 message is never queued. Say which of the two
> the PRD means, in the handover note.

The other three brokers keep what has not been acknowledged by design (a queue, a consumer group's offset, a
durable subscription), so there the delivery contract of §5.2 holds without any switch.

---

## 6 · Canonical rules

**A. Publish a command from a button** (EXECUTION rule, an action on a table row):

```groovy
def device = context.fleet.device.data.get()
def result = service.pubsub.plant.publish("devices/${device.serial}/command",
        [action: 'restart', requestedBy: service.security.user().email], [qos: 1])
if (!result.ok) { throw new Exception('The broker did not take the command') }   // ok is false only on a refusal that did not throw
```

**B. Bridge one broker to another** — a Kafka topic into MQTT, through two connections, no code between:

```groovy
// listener on Kafka topic 'orders' (reads as JSON), rule:
def order = context.data.getAttr('message')
service.pubsub.plantFloor.publish("floor/orders/${order.line}", order, [qos: 1])
```

**C. A message opens a case** — the listener's rule is the *starter* of [27](27-event-driven-process-start.md):
it validates the message, claims the business id, and calls `service.workflow.start(…)`. Phase 1a's starter
column has a new value for it: **BROKER MESSAGE**.

**D. Acknowledge back** — answer on a reply topic with the same correlation id (`meta.key` or a header).

---

## 7 · Limits and operating facts a PRD should hear

| | |
|---|---|
| Connections per project | 25 |
| Listeners per connection | 50 |
| Message size | 1 MB, both ways |
| Live listening connections per installation instance | 500 (configurable) |
| A rule's time to run | about 2 minutes per attempt (the platform's read timeout) |
| Failover when the instance holding a connection dies | up to ~60 s |
| Publishing | a connection is kept open and reused; idle ones close after 5 minutes |
| Not offered | WebSockets for MQTT; AMQP 1.0; broker-side TLS client certificates; Kafka OAUTHBEARER |
| Visible on the screen | per connection: state (listening / connecting / failing / not listening), last error; per listener: received, processed, failed, last message time, last error |

---

## 8 · What you cannot check offline, and the handover note

`validate` sees the rules. It cannot see whether a broker exists, whether a password is right, whether the
topic's name matches what the devices publish, or whether a message was ever received — none of that is in the
bundle. What the offline gate does NOT catch, and you must therefore drive live ([30](30-live-test-bugfix-and-autotest.md)):

- the connection authenticates: **Test connection** reports *Connected*, names what it reached (a Kafka
  cluster id, RabbitMQ's version, the MQTT protocol level, the ActiveMQ flavour), and warns when a listener's
  queue or topic does not exist yet;
- a message published to the source arrives in the rule: publish one by hand with the broker's own tool, watch
  the listener's *received* and *processed* counters move, and read the record the rule wrote;
- the rule is **idempotent**: publish the same message twice and check one record;
- a rule that fails is visible: make it throw once, see *failed* count and *last error* appear;
- publishing: run the publishing rule and subscribe to the destination with the broker's own tool.

A test that needs a live broker belongs in `test-scenarios.md` as a **manual scenario** with the exact commands
(`mosquitto_pub -t sensors/room1/temperature -m '{"temp":21.5}'`, `kafka-console-producer`, …) and the expected
result (the record the rule wrote, the counter that moved). The generated suite ([30](30-live-test-bugfix-and-autotest.md)
§6) has no broker in its `.env` and no key for one, so it does not drive a broker: it covers what the messages
*produce* — the pages that list the records a listener's rule creates, the buttons whose rules publish — and a
scenario that needs the broker itself is recorded as not automated, never as passed. Never put a broker's address
or password in the export or the tests.

**The handover note to write into the delivery** — copy this shape:

> This project talks to your message broker. Before it can, open **Settings → Developer → Integrations →
> PubSub**, press **Add connection**, choose **`<kind>`** (version **`<version>`**), give it the alias
> **`<alias>`** — the rules expect exactly that name — fill in the broker's host and credentials, and press
> **Test connection**. Then switch **Publish** on (`<which rules publish>`) and **Run rules when messages arrive**
> on, add a listener on **`<topic/queue>`**, read as **`<format>`**, and choose the rule **`<rule name>`** for it.
> Until then the project publishes nothing and receives nothing. `<If MQTT and loss matters:>` Switch **Clean
> session off** and use QoS 1 on the listener, or messages sent while the platform restarts are lost.

**A re-import into a live project does not touch connections or listeners** — they are configuration, not
definitions, and they survive every re-import (the only behaviour that makes the fix loop of [30](30-live-test-bugfix-and-autotest.md)
usable). A listener points at its rules by identifier, and an import keeps rule identifiers, so the binding
survives too; if a rule is ever deleted and created again under a new identifier the listener waits and says
so on its card — pick the rule again.

| event | what happens to the connections, listeners and their counters |
|---|---|
| **export** | not included |
| **re-import into a live project** | **untouched** — and listening continues |
| **environment publish / a tag** | not carried; an environment connects its own broker |
| **the project is DELETED** | removed — connections, credentials, listeners, live connections |
| **a NEW project on a realm/client pair a deleted project used** | swept on creation, so it cannot inherit the previous occupant's listeners |

---

## 9 · What `mrjun.py validate` checks

Offline, from the rule text (comments and string literals are ignored):

- **ERROR** — a PREDICATE or VALIDATION_RULE uses `service.pubsub` (directly, or through `service.rule("…")` /
  `service.crud.<alias>.<method>(…)` with a literal name that does): every member throws there.
- **ERROR** — `service.pubsub.<alias>.<member>(…)` where the member is not `publish` (`send`, `subscribe`,
  `consume`, `publishAsync` …): a channel has exactly `publish`. Subscribing is a **listener**, configured live
  in the screen, not something a rule does.
- **ERROR** — `service.pubsub.list()` / `service.pubsub.channel(…)` misspelled as another member of the
  namespace (`service.pubsub.aliases()`, `.channels()` …): it has exactly `list()` and `channel(alias)`.
- **ERROR** — a literal alias that can never exist (`service.pubsub['my-broker']`, a Groovy keyword).
- **WARN** — `publish(...)` with a *named* option no kind has (`qoss: 1`): the call would be refused at run time.

It cannot know that an alias is connected, that a listener points at the rule, or that a rule is idempotent.
That is §8.

---

## 10 · Traps

| trap | what happens | what to do |
|---|---|---|
| A rule that only inserts | the retry, the redelivery or the other system's duplicate inserts the message twice | key on a business id; unique index + do-nothing-on-conflict (§5.2) |
| `attrs.get('message')` | a raw JSON node, not a Groovy value | `context.data.getAttr('message')` |
| Publishing to the topic the same listener listens to | an endless loop that fills the broker | publish to a different topic; filter by `meta.destination` |
| A PRD that says "the platform must not lose a message" with MQTT left at defaults | messages sent while the platform restarts are gone | Clean session off + QoS 1/2 (§5.4), and say so in the handover |
| Many rules in one listener doing independent things | one failing rule stops the rules behind it for that message | one listener per concern, or order the chain so the must-succeed rule is first |
| A very slow rule on a busy topic | the listener falls behind and drops | keep the rule short; hand heavy work to a queue or a scheduler (publish a job message, process it elsewhere) |
| Using `service.store.session` or `redirectPage` in a listener's rule | nothing happens — nobody is signed in | take what you need from the payload |
| An alias like `my-broker` | cannot be read as `service.pubsub.my-broker` | letters, digits, underscore |
| Two connections with the same MQTT client id | the broker disconnects one of them in a loop | leave **Client ID** blank — the platform derives a stable, distinct one per role |

---

## 11 · Never

- NEVER write connection details, hosts or passwords into a rule, a table or a test — they are the customer's live
  configuration, and a rule reaches a broker by alias only.
- NEVER call `service.pubsub` from a predicate or a validation rule.
- NEVER assume a message arrives exactly once, or in order across listeners.
- NEVER promise "no message is ever lost" without choosing the broker settings that make it true (§5.4) and
  naming them in the handover.
- NEVER write `rep-objects` keys for connections or listeners — there are none, and an invented one is dropped.
- NEVER make a listener's rule depend on who is signed in.
