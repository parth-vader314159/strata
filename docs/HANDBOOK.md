# STRATA — the handbook

Everything the system does, why it does it that way, and what you would need to
know to build it again from an empty directory.

This is the document to read before a viva. It is long on purpose: the code is
about six thousand lines, and almost every one of them is downstream of a
decision explained here. Module docstrings tell you *what* a file does;
`docs/ARCHITECTURE.md` records the decisions in brief. This explains the
*theory*, so that you could rebuild the thing without the code in front of you.

**Three ways to read it.** Skim Parts 0–2 for the shape of the idea. Read
Parts 3–10 properly — that is the engineering. Keep Parts 12–14 for the week
before submission.

---

## Contents

- [Part 0 — The problem, stated precisely](#part-0--the-problem-stated-precisely)
- [Part 1 — The one decision everything follows from](#part-1--the-one-decision-everything-follows-from)
- [Part 2 — Identity: content addressing](#part-2--identity-content-addressing)
- [Part 3 — Storage: building the ledger](#part-3--storage-building-the-ledger)
- [Part 4 — Integrity: from hashes to evidence](#part-4--integrity-from-hashes-to-evidence)
- [Part 5 — Classification: which grammar owns this line?](#part-5--classification-which-grammar-owns-this-line)
- [Part 6 — Parsing: grammars as data, compiled](#part-6--parsing-grammars-as-data-compiled)
- [Part 7 — Time, which is harder than it looks](#part-7--time-which-is-harder-than-it-looks)
- [Part 8 — Mapping to a common taxonomy](#part-8--mapping-to-a-common-taxonomy)
- [Part 9 — The Forge: inferring a grammar](#part-9--the-forge-inferring-a-grammar)
- [Part 10 — The pipeline, and rewind](#part-10--the-pipeline-and-rewind)
- [Part 11 — Serving it](#part-11--serving-it)
- [Part 12 — How you know it works](#part-12--how-you-know-it-works)
- [Part 13 — Building it from nothing](#part-13--building-it-from-nothing)
- [Part 14 — Defending it](#part-14--defending-it)
- [Appendix — vocabulary](#appendix--vocabulary)

---

## Part 0 — The problem, stated precisely

### What a log line is

A log line is a device's own account of something that happened, serialised in
whatever format its vendor chose. That is all. It has no schema you can rely
on, no guaranteed fields, and no obligation to resemble any other vendor's
output.

### Why they all differ

This is worth understanding, because the instinct is to think the industry is
merely disorganised. It is not — the divergence is *rational* for each vendor:

- A vendor's log format is designed for that vendor's own analysis tool. It
  optimises for what their product needs, not for interoperability.
- Log formats are effectively permanent. Customers write automation against
  field positions; changing the format breaks that automation, so formats
  ossify. Cisco ASA's syntax has been stable for two decades because changing
  it would be a breaking change for every customer.
- There is no market pressure to standardise. The customer who wants
  correlation buys a SIEM, and the SIEM absorbs the cost of translation.

So heterogeneity is not going away, and a framework that assumes vendors will
converge is building on sand. **Assume permanent divergence.** That assumption
is what makes onboarding cost the central design problem rather than an
afterthought.

### What normalization means

Normalization means rewriting every source's fields into one shared vocabulary,
so that "the source address" is the same field name regardless of whether the
device called it `srcip`, `src_ip`, `source-address`, `client_addr`, or column
eight. A SIEM can only correlate across sources that share a vocabulary. Without
normalization, "show me everything that talked to 203.0.113.42" is not one query
— it is one query per vendor, hand-written, and wrong the moment a new device
appears.

### The part everyone gets wrong

Here is the framing that the whole project turns on:

> **Parsing is a lossy projection, and projections are not invertible.**

When you parse a log line into twelve named fields, you have applied a function
that maps a rich object (the original bytes) onto a poorer one (a dict). The
function throws away everything it was not told to keep: fields you did not map,
whitespace, ordering, the vendor's own spelling of the action, malformed bytes,
the parts you did not understand. You cannot run that function backwards. The
information is not *hidden* — it is *gone*.

Now notice the tension in the problem statement. A ULPF is asked to do two
things that pull in opposite directions:

| Requirement | Nature |
|---|---|
| (b), (c) Normalize into a common taxonomy | Necessarily **lossy** |
| (a) Preserve the original losslessly | Necessarily **lossless** |

Most log pipelines resolve this tension by doing (b) and (c) properly and
treating (a) as "we keep a copy of the raw file somewhere, probably, for 30
days". That is not preservation; it is a backup with a retention policy, and it
is not linked to the events derived from it.

STRATA resolves it differently: **do both, but keep them in separate layers,
and make the lossless one canonical.**

That is the whole idea. Everything after this is engineering.

---

## Part 1 — The one decision everything follows from

### Two dataflows

The conventional pipeline:

```
bytes → parse → normalized event → store the event
                                   (raw kept as an optional side copy)
```

STRATA:

```
bytes → store the bytes (canonical, immutable)
              ↓
        derive the normalized event  (a view; disposable, recomputable)
```

If you have met **event sourcing** or **materialized views** in a database
course, this is exactly that idea applied to logs. The ledger is the event log;
normalized OCSF events are a materialized view over it. You never update the
view in place — you recompute it.

### Three consequences, none of which can be retrofitted

**1. Losslessness stops being a feature and becomes a property.**
Requirement (a) is not something the code does; it is what the store *is*. A
feature can regress. A property cannot regress without the system ceasing to
function, which means a bug in it is loud rather than silent. This distinction
is the whole reason to invert.

**2. Traceability is free.** Requirement (d) asks that every normalized event be
traceable to its original. In the conventional design you must invent a
correlation id, store it in both places, and hope nothing drops it. Here the
event names the bytes it came from, and *the bytes are still there*. There is
nothing to keep in sync.

**3. Rewind becomes possible.** This is the one nobody else has. Six months
after deployment you discover a mapping bug — the field you called
`dst_endpoint.port` was actually the NAT port. In a conventional pipeline you
fix it going forward and six months of history stays wrong forever, because the
inputs that would let you recompute were discarded at ingest. Here you correct
the YAML and replay. It costs about sixty lines of code, not because it is
clever but because the architecture was shaped for it.

### What it costs

Storage: roughly 1.1–1.3× the raw feed, compressed. That is the entire price.

### Why doesn't everyone do this?

Because the decision was made in about 2005, when storage cost roughly a hundred
times what it costs now, and nobody has revisited it. Discarding the raw was
correct then. It is a habit now. This is a genuinely good answer to "why hasn't
someone already built this" — the honest answer is that the constraint that
justified the old design has relaxed by two orders of magnitude and the design
did not move with it.

---

## Part 2 — Identity: content addressing

### The rule

```
record_id = sha256(payload_bytes)
```

The identity of a record **is** its content. Not a sequence number, not a UUID,
not a database primary key.

### Four properties you get for free

1. **Deduplication.** Identical bytes are the same record, by definition. No
   comparison pass, no dedup job.
2. **Idempotent replay.** Ingesting the same file twice is a no-op. This is
   what makes recovery safe: after a crash you can simply re-feed everything
   without worrying about double counting.
3. **Tamper evidence at the record level.** Change one byte and the id no longer
   matches the content. Verification is one hash.
4. **No coordination.** Two machines that see the same line independently derive
   the same id, with no shared counter and no allocation service. This matters
   the moment you shard.

### The envelope / payload split

Not everything about a record is *in* the record. Distinguish:

- **Payload** — the original bytes, exactly as they arrived. This is what gets
  hashed. Never decoded, never re-encoded, never base64'd on the way in.
- **Envelope** — facts about the receipt that the line itself does not carry:
  which channel it arrived on (UDP/TCP/file/HTTP), the observed peer address,
  the receipt timestamp in nanoseconds, whether it was truncated at the size
  cap.

The envelope is *observed*, not *claimed*. A log line can lie about its
hostname; it cannot lie about the socket it arrived on. In a forensic context
that distinction matters, so the two are stored separately and the provenance
record shows both.

### The dedup subtlety — know this one, it gets asked

Because the id covers the payload only, two byte-identical lines collapse into a
single record with a `seen` counter incremented. The occurrence *count* is
preserved; the second occurrence's *envelope* — its own receipt time and peer —
is not.

Is that a loss? For log data, mostly not: byte-identical perimeter log lines
almost always carry their own timestamp, so true duplicates are genuinely the
same event arriving twice (syslog over UDP retransmits, a collector replaying).
But be honest about the trade-off, because it is a real one:

> If per-occurrence receipt metadata mattered for your use case, you would fold
> the envelope into the digest. You would then lose deduplication and idempotent
> replay. We chose the other side of that trade, and the choice is one line of
> code to reverse.

Being able to say exactly what you gave up, and what it would cost to change
your mind, is worth more in a viva than pretending there was no trade.

---

## Part 3 — Storage: building the ledger

This is the heart of the system. If you understand this part, you understand
STRATA.

### What the store must guarantee

1. Bytes come out exactly as they went in — including invalid UTF-8, embedded
   nulls, and lines truncated at a size cap.
2. Nothing is ever edited or deleted. Append-only.
3. Any single record can be read back without touching its neighbours.
4. Tampering is detectable.
5. A crash never produces an archive that is silently wrong.

Note that (5) is doing more work than it looks. An archive that is *obviously*
broken is recoverable. An archive that is *quietly* broken is worse than no
archive at all, because you will trust it.

### Layout: strata and frames

Records live in segment files called **strata** (`st-000001.sl`). Each file
starts with a small header and then holds a sequence of independently
compressed frames:

```
st-000001.sl
┌──────────────────────────────────────────────────────────────┐
│ MAGIC(6) VERSION(1) SHARD(1)                    file header  │
├──────────────────────────────────────────────────────────────┤
│ FRAME: len(u32) │ zstd( env_len(u16) │ envelope │ payload )   │
│ FRAME: len(u32) │ zstd( ... )                                 │
│ ...                                                           │
└──────────────────────────────────────────────────────────────┘
```

Four decisions are packed into that diagram. Take them one at a time.

**Length-prefixed framing.** Each frame begins with its own byte length. This
means you can walk the file — skip, count, seek to the next record — *without
decompressing or parsing anything*. Recovery, `scan()`, and `reindex()` all rely
on it. The alternative, a delimiter byte, fails immediately for binary payloads:
you would have to escape the delimiter, which means modifying the bytes, which
is the one thing this store exists not to do.

**Per-frame compression, not per-file.** Compressing the whole file gets a
better ratio, because the dictionary spans more data. But then reading record
number 400,000 means decompressing everything before it. Per-frame compression
costs some ratio and buys O(1) random access. For a store whose entire purpose
is "show me *this* record and prove it", that is the right side of the trade.

**A packed binary envelope, not JSON.** `struct.Struct("<BBQBB")` plus two
variable-length strings. JSON would be perhaps 120 bytes where this is 14, and
would cost a parse per record on read. At a few hundred thousand records that
difference is worth the twenty lines it takes to write the packer.

**The payload is written as raw bytes inside the frame.** Never decoded, never
`.decode('utf-8', errors='replace')`, never base64. This is the single most
important line of code in the project, and it is enforced with a type check that
raises rather than coercing:

```python
if type(payload) is not bytes:
    raise TypeError(
        f"ledger.append needs bytes, got {type(payload).__name__}. "
        "Decoding before storage is precisely the bug this ledger exists "
        "to make impossible."
    )
```

Most log pipelines lose invalid UTF-8 not deliberately but incidentally: they
decode on receipt, because a `str` is more convenient than `bytes`, and by the
time anything is stored the original is already gone. Refusing `str` at the door
makes the mistake impossible rather than merely discouraged.

### The index, and why it is disposable

A SQLite table maps `record_id → (stratum, offset, length, seq)` so a lookup by
id is O(1) rather than a file scan.

The important property: **the index holds no information that is not already in
the segment files.** It is a cache. `reindex()` rebuilds it by walking the frames
from scratch. Keeping this true costs a little discipline — anything you are
tempted to store *only* in the index belongs in the frame instead — and it buys
you the ability to treat index corruption as an inconvenience rather than a
disaster.

### Crash safety: the ordering that is not negotiable

Two things must reach disk on every sync: the frame bytes, and the index rows
that point at them. The order matters, and there is a general principle
underneath it:

> **Choose the failure ordering such that the possible failure is the
> recoverable one.**

Consider a crash landing exactly between the two operations.

| Order | Crash leaves | Recoverable? |
|---|---|---|
| fsync data → commit index | records on disk the index doesn't know about | **Yes** — `scan()` reads files directly, `reindex()` rebuilds |
| commit index → fsync data | index rows pointing at bytes never written | **No** — dangling references into a hole |

So the code fsyncs the data file first and commits the index second. Reversing
those two lines produces a system that works perfectly in testing and corrupts
itself the first time a machine loses power. This is the kind of thing worth
being able to explain out loud.

### Batched durability

`fsync` plus `COMMIT` per record costs more than every other pipeline stage put
together — it is a physical operation on the storage device. So both are batched
(`sync_every`, default 2048), as every production log system does.

State the exposure precisely: **at most `sync_every` records are at risk in a
hard power loss.** Set it to 1 for per-record durability at roughly twenty times
less throughput. Note carefully what does *not* change: losslessness. The bytes
stored are identical either way; only the moment they are forced to the platter
moves.

### Single writer, enforced at the door

Concurrent appends to one segment file interleave and corrupt frames. So there
is one writer per shard, taken as an advisory `flock` when the ledger opens.

The interesting part is *where* the check lives. Before the lock existed, a
second process started up perfectly happily and then failed later, deep inside
SQLite, with `database is locked` surfacing as an anonymous HTTP 500 at request
time. The operator saw a broken server; the actual problem was that they had
started two of them. Now it fails immediately, by name, with a message that says
what to do.

The general lesson: **an architectural constraint should be checked at the point
where it is violated, not at the point where the violation eventually hurts.**

`flock` specifically, rather than a pid file, because the kernel releases it when
the process dies. A pid file goes stale after a crash and needs manual cleaning,
which is exactly the wrong thing to hand an operator at 3am.

### Scale path

Horizontal, by sharding. More shards, each with one writer. Partition by source
device rather than round-robin — that keeps one device's events in order within
a shard, which is what makes session correlation tractable later.

---

## Part 4 — Integrity: from hashes to evidence

This part is the most theoretical, and the most likely to earn marks. Work
through it slowly.

### Building blocks

A cryptographic hash `H` gives you: fixed-size output from any input,
determinism, and — the properties that matter here — **collision resistance**
(hard to find two inputs with the same hash) and **second-preimage resistance**
(given one input, hard to find a different one with the same hash). SHA-256
throughout.

### Level 1 — per-record digest

Already have it: the record id. Detects corruption of any single record.
Detects nothing about the archive as a whole — delete a record entirely and no
individual hash complains.

### Level 2 — hash chain

Chain each record's digest into the previous:

```
h₀ = H(genesis)
hₙ = H(hₙ₋₁ ‖ digestₙ)
```

Now deletion and reordering are detectable, because both change every subsequent
link. Publish `hₙ` somewhere you do not control and you have a timestamp on the
entire archive's state.

**The limitation, and it is fatal for the actual use case.** To convince a third
party that *one specific line* is in the archive, they must recompute the chain
— which means you must give them **every other record**. In a real investigation
the other records belong to other cases, other customers, other jurisdictions.
Disclosure is frequently precisely what you cannot do.

So the chain proves the archive is intact, which is useful, and cannot produce
evidence about one record without disclosing all of them, which is disqualifying.

### Level 3 — Merkle tree

Hash the records pairwise up a binary tree:

```
                    ROOT
                  /      \
             N(0,1)       N(2,3)
            /     \       /     \
          L₀      L₁     L₂     L₃
          a       b      c      d
```

To prove `c` is in the tree you supply `c` itself and the **sibling path**:
`L₃` and `N(0,1)`. The verifier computes `L₂` from `c`, combines with `L₃` to get
`N(2,3)`, combines with `N(0,1)` to get a root, and compares against the
published root. If it matches, `c` is in the tree.

Proof size is ⌈log₂(n)⌉ hashes. For 20,000 records that is 15 hashes — a few
hundred bytes.

**And the verifier learns nothing about any other record.** They see hashes,
which reveal nothing about their inputs. That is the difference between "trust
our database" and evidence.

### Two attacks you must defend against, and both are one line

These are the details that separate a Merkle tree that works from one that is
decorative. Expect to be asked.

#### Attack 1 — second preimage, defeated by domain separation

Suppose you hash naively:

```
leaf(data)   = H(data)
node(l, r)   = H(l ‖ r)
```

An attacker takes a real internal node `N = H(L₀ ‖ L₁)` and presents the
**64-byte string `L₀ ‖ L₁`** as if it were a leaf's data. Its leaf hash would be
`H(L₀ ‖ L₁)` — which equals `N`, a value genuinely in your tree. So they produce
a valid-looking inclusion proof for data you never stored.

The fix (RFC 6962, the Certificate Transparency standard):

```
leaf(data)   = H(0x00 ‖ data)
node(l, r)   = H(0x01 ‖ l ‖ r)
```

Different first byte, so a leaf hash and a node hash can never collide, so an
internal node can never masquerade as a leaf. One byte. `store/merkle.py` uses
`LEAF_PREFIX = b"\x00"` and `NODE_PREFIX = b"\x01"`, and there is a test that
forges this exact attack and asserts it is rejected.

#### Attack 2 — odd-node duplication

Trees want power-of-two leaf counts. With an odd number, what do you do with the
leftover?

The tempting answer is to duplicate it. Leaves `[a, b, c]` become `[a, b, c, c]`.
But now consider a genuine four-record archive `[a, b, c, c]`. It produces the
**same root**. Two different archives, one root — so a root no longer identifies
a unique set of records, and an attacker who can append a duplicate changes
nothing observable.

This is not hypothetical: it is the shape of CVE-2012-2459 in Bitcoin, where
duplicated transaction hashes let two distinct blocks share a Merkle root.

The fix is **promotion**: carry the odd node up a level unchanged rather than
pairing it with itself. `[a, b, c]` → `[N(a,b), L(c)]` → `root = N(N(a,b), L(c))`,
which is distinct from the four-leaf tree's root. Also tested.

### Chaining the roots

Each stratum is sealed with its own tree when it fills, and each stratum stores
its predecessor's root. So you get both properties at once:

- **per-record inclusion proofs**, from the trees
- **whole-archive continuity**, from the chain of roots

Tamper with a sealed stratum and its root no longer matches its contents; the
next stratum's stored predecessor-root then disagrees, and the break is located
to a specific stratum.

### What this proves — and what it does not

Be precise here, because overclaiming is how a security design gets taken apart.

**It proves:** the archive has not been altered since sealing; this specific
record is in this specific stratum; the strata form an unbroken sequence.

**It does not prove:** that the log line was *true* (a compromised device can
log whatever it likes — no storage system can fix that); that nothing was
withheld *before* it reached the ledger (integrity begins at ingest); that the
operator did not seal a doctored archive on day one. For that last one you need
the roots published somewhere outside the operator's control — an external
timestamp authority, a transparency log, a notarised email. The design
accommodates it; the shipped system does not include it, and you should say so
rather than let it be discovered.

---

## Part 5 — Classification: which grammar owns this line?

### The naive approach, and why it is the wrong shape

Given `G` grammars each with `R` rules, testing every grammar against every line
costs `G × R` regex operations per event. That is O(G) per event, so **onboarding
sources makes the pipeline slower** — exactly backwards for a product whose
central promise is that adding sources is easy. At fifty sources you have built
something that punishes its own success.

### The insight

> A line's **structure** is decidable far more cheaply than its **identity**.

You do not need to know a line is a FortiGate traffic log to know it is
`key=value` pairs. Counting characters tells you that. And once you know it is
`key=value`, every CSV, JSON, CEF and LEEF grammar is irrelevant and never needs
to be evaluated.

### Phase 1 — the fingerprint

One pass over the line, no regex, counting: commas, equals signs, pipes, tabs,
spaces. Plus detection of a leading syslog `<PRI>` prefix, and where the body
starts past it.

Two details worth noticing in `parse/shapes.py`:

**Why no regex.** We want six different facts. A regex gives you one match per
pass, so six facts means six passes. A single `for ch in line` loop with an
if/elif chain beats it, because the work per character is trivial and the loop
is executed once.

**Why counting starts after the `<PRI>`.** A syslog header contains a hostname,
and a hostname is full of dots and can contain hyphens; counting from the body
keeps the header from skewing the structural signal.

Then classify, **most specific first**:

```
{...}                                   → JSON
≥5 pipes and contains "CEF:"            → CEF
≥4 pipes and contains "LEEF:"           → LEEF
≥4 equals, and equals×6 ≥ word count    → KV
≥8 commas and <3 equals                 → CSV
≥4 tabs, or 5–24 mostly-numeric tokens  → DELIMITED
otherwise                               → FREEFORM
```

The ordering is load-bearing. A CEF line *also* contains `key=value` pairs in
its extension, so if you tested KV first, every CEF line would be misclassified.
Whenever you have overlapping structural predicates, the most specific must be
tested first — and you should be able to name which pairs overlap and why.

The `equals * 6 >= words` heuristic deserves a note: it asks "is this line
*mostly* key-value pairs, or does it just happen to contain an equals sign?" A
prose line mentioning `x=1` has one equals and forty words; a FortiGate line has
twenty equals and twenty-five words.

### Phase 2 — signature scoring

Grammars are bucketed by family **at load time**, so `candidates(shape)` is a
dict lookup. Only same-family grammars get their signature evaluated, and the
signature tests run cheapest-first:

1. `must` literals — a plain `in` substring test, the cheapest operation
   available, and it rejects almost everything immediately
2. `any` literals — one of these must appear
3. an optional regex — only reached by lines that already passed both

The score is the grammar's declared `weight`.

**Measured on the demo corpus: 2.67 of 10 grammars evaluated per line — 73% of
the classification work never runs.** And unlike the other optimisations in this
project, this one *improves* as sources are added: the tenth JSON grammar costs
the CSV lines nothing at all.

### FREEFORM as the catch-all

Grammars declaring `FREEFORM` are also evaluated for lines of *any* other shape.
Prose is the residual category, and a source whose shape we misjudge should get
a chance rather than being dismissed on a heuristic. This is a deliberate
softening of the optimisation, and worth knowing you made it: you traded a
little selectivity for robustness against your own fingerprinting being wrong.

### Confidence, and the ambiguity rule

Here is a piece of reasoning that is genuinely worth understanding.

Suppose two grammars both score 0.9 on a line. What is your confidence in the
winner?

The naive answer is 0.9. **The correct answer is: much lower, because you are
not confident, you are confused** — and the raw score hides that. A number that
high is actively misleading, because everything downstream will treat it as
certainty.

So:

```python
AMBIGUITY_MARGIN  = 0.12   # how close the runner-up may get
AMBIGUITY_PENALTY = 0.55   # multiplier applied when it gets closer than that
DEFAULT_FLOOR     = 0.70   # below this, quarantine
```

If the runner-up is within 0.12 of the leader, the leader's confidence is
multiplied by 0.55. A close two-horse race at 0.9 becomes 0.495, which is below
the floor, which means **quarantine**. A silent coin-flip has been turned into a
visible "we don't know".

### Why "unknown beats wrong" is a safety property, not a slogan

This is the most important idea in the classification layer, and it is the one
to lead with if a judge asks what makes your design defensible.

A log that fails to parse produces a visible gap. Somebody notices; a queue
grows; a dashboard shows a number. It is an **operational** problem, and
operational problems get fixed.

A log that is *misidentified and confidently parsed into the wrong fields*
produces something worse: an event that looks correct, validates against the
schema, populates a dashboard, and is wrong. Nothing alerts, because from the
system's point of view nothing went wrong. It will sit in the SIEM being quietly
wrong for years, and it will be believed.

The asymmetry in cost is enormous, so the system is deliberately biased toward
admitting ignorance. Quarantine is not a failure state in this design — it is
the correct output for an uncertain input, and the console treats it that way:
quarantined records are one click from the Forge, which is the tool for
resolving them.

---

## Part 6 — Parsing: grammars as data, compiled

### Why declarative

Requirements (e) and (i) — plug-and-play onboarding, and less parser-writing
effort — are the reason a grammar is a YAML file rather than a Python class. If
adding a source needs a code change, it needs a developer, a review, a test, a
release and a restart. If it needs a data file, it needs an analyst and a
reload.

### Why *deliberately weak* declarative — the security argument

This is a design decision people underrate, and it is a good one to be able to
articulate.

Grammars are untrusted input. They are written by analysts, generated by the
Forge, and — in any real deployment — pasted in from a vendor's community forum.
So the format is intentionally the least expressive thing that does the job:

- no expressions
- no imports
- no shell-outs
- no arbitrary code of any kind

A grammar can **name a known primitive and supply arguments to it, and nothing
else.** That restraint is the security control. State it plainly:

> **An expressive grammar format is remote code execution with a friendly
> name.**

Every "config" format that grew an expression language — and most eventually do
— has ended up with a sandbox escape. The way to win that game is to not have an
evaluator.

The escape hatch that remains is `regex`, and it is a real one: regular
expressions run on Python's backtracking engine, so a pathological pattern can
cause catastrophic backtracking. Mitigations in place: line length is capped at
intake, and every shipped grammar's patterns are reviewed. The proper fix is
RE2, which has no backtracking and therefore no such class of failure. Listed
honestly in the limitations.

### The primitive set

`syslog` (RFC 3164 / 5424 / auto) · `columns` · `whitespace` · `kv` · `json` ·
`regex` · `cef` · `leef` · `prefix`

Nine primitives cover every perimeter source we have tried. That is not a
coincidence — the space of serialisation choices vendors actually make is small,
even though the space of field names is enormous.

### Compilation: the idea, properly

The obvious way to execute a declarative pipeline is to walk the steps per event
and branch on step type:

```python
for step in grammar.pipeline:          # per event
    if step.kind == "columns":         # per event
        ...
    elif step.kind == "kv":            # per event
        ...
```

Look at what that does. Every one of those comparisons happens millions of times
to reach a decision **that was already fixed the moment the grammar loaded.**
The step type cannot change between events. Only the data can.

This is a classic **partial evaluation** (or *staging*) opportunity: you have a
function of two arguments, `run(grammar, line)`, where one argument varies
millions of times and the other does not vary at all. So specialise on the fixed
one, once, and get back a function of the remaining argument.

```python
def _compile_step(step):
    if step.kind == "kv":
        pattern = _kv_pattern(step.pair_sep)   # done once, at load
        lower   = step.lower_keys              # captured once
        return lambda s: X.kv(s, pattern, lower)
```

Per event the pipeline is then:

```python
for fn in plan:      # no branching, no attribute lookup, no dict lookup
    fn(state)
```

Everything hoistable is hoisted at compile time: regexes compiled, column names
frozen into tuples, cast functions resolved, OCSF dotted paths pre-split into
segment tuples, enum tables lower-cased. Measured, this is the largest single
throughput win in the parse layer, and it costs nothing at runtime because the
work happens once per grammar rather than once per line.

A bonus that matters for scaling: the compiled object is immutable, so it can be
shared across worker processes without copying.

### Optional steps

Real estates are inconsistent — some sites strip the syslog envelope upstream
and some do not, and one grammar must read both. So a step can be marked
`optional: true`, which wraps it in a guard that swallows any exception. An
optional step must never be able to fail a line.

### A story about `pair_sep` worth remembering

Most vendors separate `key=value` pairs with spaces. Check Point separates them
with `|`.

With a whitespace-assuming pattern, an unquoted Check Point value matches
greedily up to the next space — swallowing the `|` separators, so every
following pair collapses into the first value. The line parses. It produces a
record. The record is nonsense.

That is a **silent misparse producing a plausible, wrong result** — exactly the
failure class this project exists to make impossible. The fix was to make the
separator declarative (`pair_sep: "|"`), which keeps a vendor difference in the
grammar (data) rather than in the engine (code). The general principle:

> **When two sources differ, the difference belongs in data. When you put it in
> code, you have made every future source's difference a code change.**

---

## Part 7 — Time, which is harder than it looks

Timestamps look like the boring part. They are where log pipelines quietly go
wrong.

### The performance half

`datetime.strptime` re-parses its format string and rebuilds a regex **on every
call**, for the most repetitive operation in the system — the same three or four
formats, millions of times. Profiling put it among the top costs in the pipeline.

Each supported format is instead a hand-written slicer reading digits at fixed
offsets, roughly an order of magnitude faster. Fine, but that is the boring half.

### The half that actually matters

**RFC 3164 syslog timestamps look like `Aug 21 14:32:07`. That carries no year
and no timezone.**

Every implementation must invent both. The inventions are where things break:

- **Invent the year as "the current year"** and every December log read on
  2 January lands twelve months in the future. Your alerting sorts by time. The
  event is not where anyone will look for it.
- **Invent the zone as UTC** when the device sends local time and events land
  hours away from the events they should correlate with. Your incident timeline
  is wrong, and nothing tells you.

STRATA's answers:

**The year rule, stated explicitly so it is reviewable:** take the current year;
if that puts the event more than a day in the future, it belongs to last year
instead. The one-day slack means a device with a clock a few minutes fast is not
rolled back a whole year. This is correct across a New Year boundary in both
directions, and wrong only for logs replayed more than a year late — a case
where any answer is a guess, and we would rather be predictably wrong than
subtly so.

**The zone is not inferred at all.** A grammar must *declare* it. There is a
principle here that generalises well beyond timestamps:

> **Declaring an assumption makes it reviewable. Inferring one makes it a bug
> nobody can see.**

### Why named timezones are rejected

You may only declare a fixed offset (`+05:30`), never a named zone
(`Asia/Kolkata`). This looks like a limitation and is actually a correctness
requirement.

A named zone's offset depends on the tz database, which changes — governments
alter daylight saving rules with a few weeks' notice, and the IANA database ships
updates several times a year. If a stored timestamp's meaning depends on which
tzdata version is installed, **the same archive reads differently on two
machines**. For a system whose entire purpose is evidence, that is
disqualifying. A device in a DST zone declares the offset its logs actually
carry.

### A bug worth studying: separator validation

`sniff("2026/08/26 14:32:07")` returned `iso8601`.

The ISO-8601 parser sliced digits by position — characters 0–4 as the year, 5–7
as the month — without checking that the *separators* were what ISO-8601
requires. A slash-separated date has its digits in exactly the same places, so
the slicer read it happily and produced the correct instant **by luck**.

Correct answer, wrong reason — which is worse than a wrong answer, because it
made format *detection* wrong, and format detection is what the Forge uses to
propose a grammar. The fix: every parser validates its separators before
trusting its offsets.

The lesson generalises: **when you optimise by making assumptions about
structure, you must also verify the structure.** Otherwise you have not written
a fast parser, you have written a fast guesser.

### Fallback

If no declared format matches, event time falls back to the envelope's receipt
time, and `metadata.time_source` is set to `receipt_fallback`. Never silently —
an analyst querying by time is entitled to know which of those two clocks they
are looking at.

---

## Part 8 — Mapping to a common taxonomy

### What OCSF is

The **Open Cybersecurity Schema Framework** — a vendor-neutral event schema,
now under the Linux Foundation, backed by AWS, Splunk, IBM, CrowdStrike and
others. Version 1.8.0 is the target here.

The structure you need to know:

- **Category** — the broad domain (4 = Network Activity)
- **Class** — the specific event type (4001 = Network Activity)
- **Activity / disposition** — normalised enums (`disposition_id` 1 = Allowed,
  2 = Blocked, …)
- **Objects** — `src_endpoint`, `dst_endpoint`, `metadata`, and so on, each with
  defined fields
- **The base event class** — and this is the part that matters — already defines
  `unmapped` and `raw_data`

That last point is worth pausing on. OCSF *anticipates* that a mapping will not
cover every vendor field, and provides a standard place for the remainder. The
schema itself endorses the idea that discarding unmapped data is wrong. When
someone asks why you keep residue, the answer is not "we thought it was a good
idea" — it is "the schema has a field for it".

**Why OCSF over the alternatives.** CEF is ArcSight's, and is a transport format
rather than a taxonomy. Elastic Common Schema is good but Elastic's. Splunk CIM
is Splunk's. OCSF is the only one that is genuinely vendor-neutral, actively
developed, and being adopted across the industry — which is exactly what you
want for a framework whose value proposition is neutrality.

### Placement

Mappings are written as dotted paths:

```yaml
fields:
  src_endpoint.ip: srcip
  dst_endpoint.port: dstport
```

At compile time each path is split into a segment tuple once
(`("src_endpoint", "ip")`), so per event the mapper walks dicts and does nothing
else — no string splitting in the hot path.

### Enum collapse, and keeping the vendor's own word

Vendors describe the same outcome differently: `deny`, `blocked`, `drop`,
`reject`, `DENY`. OCSF wants one enum. So:

```yaml
enums:
  disposition_id:
    source: action
    table: {allow: 1, deny: 2, drop: 3}
    default: 99
    keep: disposition_orig     # ← this line
```

`keep` preserves the vendor's original string alongside the normalised id.
Without it, `deny` and `drop` become indistinguishable — both are 2 — and you
have destroyed a distinction the device thought was worth making. Normalization
should add a shared vocabulary, not remove the source's own.

Tables are lower-cased at compile time so lookup is case-insensitive without a
per-event `.lower()` call.

### Residue by set difference — the construction that cannot forget

This is a small piece of code with a disproportionately good property.

At compile time, each grammar records the set of vendor fields its mapping
consumes:

```python
self.claims = frozenset(
    [src for _, src in self.fields] + [m.source for m in e.enums.values()])
```

At map time, residue is everything else:

```python
residue = {k: v for k, v in fields.items()
           if k not in claims and k not in ignore and k != clock_field}
```

Notice what this construction makes impossible. Residue is not a list somebody
maintains — it is computed as `all_fields − consumed_fields`. If you add a
field to the mapping, it leaves residue automatically. If you *forget* to map a
field, it appears in residue automatically, where it is visible in the console.

**There is no code path in which a field is silently dropped, because dropping
would require actively removing it from both sets.** Compare this with the
alternative design — an explicit list of fields to preserve — where forgetting
to add one loses it forever and nothing tells you.

This is a general technique worth stealing: when correctness depends on not
forgetting something, arrange the code so that the forgetful case produces the
safe outcome.

### Validation

Every event is validated before it leaves — required fields present, class and
category consistent, enum values in range. Validation runs at the trust
boundary; internally, objects are slotted dataclasses with no per-construction
schema walk, because validating data you produced yourself in-process from code
you control is pure overhead.

---

## Part 9 — The Forge: inferring a grammar

### The cost being attacked

Onboarding a new log source conventionally takes two to five engineer-days: read
the vendor's field reference, hand-write regex, test against samples, discover
the edge cases, rewrite. That cost — multiplied by every source in an estate —
is what requirement (i) is about, and it is the reason organisations have
un-onboarded devices logging into a void.

The Forge turns that into: paste samples, read the proposal, correct a name or
two, publish. Minutes, no code, no restart.

### How it works, in four stages

**1. Profile.** Cluster quarantined lines by structure, then mine a template
across the cluster. The idea is the one behind DRAIN and similar log-template
miners: across many instances of the same message type, the tokens that stay
constant are the *template* and the tokens that vary are the *variables*. You do
not need to know what a field means to know that it is a field.

**2. Infer, by two independent signals.**

*By name* — a pattern table for the spellings vendors actually use:

```python
(re.compile(r"^(src|source|client|orig|local|initiator)[_.\-]?(ip|addr|address|host)$", re.I),
 "src_endpoint.ip"),
```

*By value* — and this is the one that matters. `kind_of(value)` classifies a
value from the value alone: `ipv4`, `mac`, `url`, `email`, `port_or_int`,
`epoch_or_int`, `hexid`, `float`, `timestamp`, `ipv6`, `bool`, `hostname`,
`text`.

**3. Adjacency — the key idea.** Value-kind alone is far too weak: half of
everything is a small integer. What makes it work is *position*:

> The first two high-cardinality IPv4 fields are source and destination, in that
> order. A small integer immediately following an IPv4 field is that endpoint's
> port.

That is how a human reads an unfamiliar log, and it works on **positional CSV,
where there are no names at all** — which matters enormously, because positional
CSV is most of the perimeter. Knowing a column is called `col_08` tells you
nothing; knowing that every value in it is an IPv4 address, that there are 137
distinct ones, and that the column two later is always an integer under 65536
tells you it is a source endpoint and its port.

Guards on the heuristic: `purity > 0.85` (nearly every value in the column is
that kind), `distinct > 1` (a column with one repeated value is a constant, not
an address), and adjacency limited to the next two positions.

**4. Propose.** Emit a complete YAML grammar with a confidence per field.

### Propose, never auto-publish

This boundary is a design decision, not a limitation, and it is worth defending
in exactly these terms:

> A grammar that silently starts mis-mapping a field is precisely the failure
> this project exists to eliminate. Shipping one without a human reading it
> would be self-defeating.

Every inference rule above is a heuristic and can be wrong. The Forge is
therefore a *drafting* tool: it does the tedious 90% — finding the fields,
guessing the structure, sniffing the time format, writing valid YAML — and a
human supplies the meaning a machine cannot infer.

One implementation detail with a good reason behind it: the proposal is an
ordinary grammar file, validated by **exactly the same schema** as a
hand-written one. There is no special case and no privileged path. A generated
grammar that would not pass review as a hand-written grammar does not get to
exist.

---

## Part 10 — The pipeline, and rewind

### Batching

Events arrive in batches (default 512) and stay in batches through every stage.
In Python the per-call overhead of a function is a real fraction of the work when
the work is small, so 512 lines through one loop beats 512 loops through one
line. It also lets the ledger amortise one `fsync` across a whole batch.

### The ordering that is not negotiable

```
bytes → LEDGER → triage → read → map → outlets
```

Bytes go to the ledger **first**, before anything else can fail.

The reason is worth internalising: if you parsed first and crashed, you would
have lost the evidence of what crashed you — and **the line that crashes a
parser is exactly the line an investigator most wants to see.** A malformed log
is not noise; it is frequently the most interesting thing in the file, because
it may be an attacker probing your log injection surface.

Anything can fail after the ledger write. Nothing can fail before it except the
write itself.

### Outcomes

Every record produces exactly one outcome: an `Event` (parsed and mapped), or a
`Rejection` (quarantined, with a reason). Both reference the record id. There is
no third state and no silent drop.

### Rewind

```python
for record in ledger.scan():
    fp       = fingerprint(record.text)
    decision = triage.decide(record.text, fp)
    ...re-read, re-map, re-emit
```

That is essentially the whole thing. Scan the ledger, run the current grammars
over the original bytes, replace the view. **Nothing is written to the ledger.**
History is not rewritten; it is re-*read*.

Two properties make this safe:

- **Idempotence** comes free from content addressing. Re-running rewind produces
  identical output. There is no "did this already run?" state to track.
- **A generation counter** on the provenance record tells you which derivation
  pass produced an event, so you can tell a rewound event from an original one.

`--dry-run` reports what would change without touching outlets, which is what
you would actually run first in production.

Sixty lines. That is the entire argument for the architecture: because the
ledger was never a backup, correcting three months of history is a loop rather
than a data-recovery project.

---

## Part 11 — Serving it

### Outlets

- **Parquet** — columnar, typed, the lake format. Flat scalar fields become
  typed columns; the nested `ocsf` and `unmapped` objects are stored as JSON
  strings, because Parquet's nested types are awkward across readers and a
  string round-trips everywhere. This is requirement (h): stable column names
  and real types are what make a dataset trainable rather than merely
  queryable.
- **CEF** — for SIEMs that speak it, with proper escaping and a
  `strataRecordId=` extension so an analyst in the SIEM can jump back to the
  original bytes. Traceability that survives leaving the system.
- **NDJSON** — one JSON object per line, for everything else.
- **Memory** — for tests.

`strata query "SELECT vendor, count(*) FROM events GROUP BY 1"` runs DuckDB over
the Parquet lake, which is requirement (g) demonstrated in one command.

### The API and console

FastAPI. HMAC-signed tokens, three roles, an audit log of privileged actions.
Server-Sent Events for the live stream rather than WebSockets, because the data
flows one way and SSE reconnects automatically with no client-side logic.

The endpoint worth knowing is `/api/record/{id}/provenance`. It returns the
original bytes together with byte ranges for each extracted value and the OCSF
field each became. The console renders that as the inspector: the raw line with
every extracted value highlighted, hover either side to see its counterpart.

That is requirement (d) as something you can point at, rather than an identifier
somebody could in principle look up.

### Air-gap discipline

"Runs air-gapped" is easy to claim and easy to violate by accident — one CDN
`<script>` tag in a template, one `requests` import in a helper. So it is
enforced mechanically: a CI job greps the tree for external URLs in the UI and
for network-client imports in the package, and fails the build on either.
`build-bundle.sh` produces a wheelhouse; `install-offline.sh` installs with
`--no-index`, so reaching the network is *impossible* rather than merely
unnecessary.

The favicon is an inline `data:` URI for exactly this reason.

---

## Part 12 — How you know it works

This part is the one that will most improve your marks relative to effort spent,
and it contains the single most valuable idea in the project.

### Ground truth generation

The synthetic corpus generator does not merely emit realistic log lines. For
each line it also emits **what the correct answer is** — the source IP, the
destination IP, the ports, the action.

That means you can compare the pipeline's output against known truth, field by
field, and compute an accuracy number. Not "did it parse", but "did it parse
*correctly*".

### Why this matters: parse-succeeded ≠ parse-correct

Here is the story to tell in a viva. It is the best thing in the repository.

Cisco ASA writes deny messages like:

```
%ASA-6-106023: Deny outbound TCP connection for outside:203.0.113.42/443 to inside:10.10.4.55/49832
```

Read it carefully. For an **outbound** connection, the interface named *first*
(`outside:`) is the **destination**. The grammar captured positionally — first
address seen becomes source — which is backwards for this direction.

Now consider what that bug looked like from every angle the system had:

- The line **parsed successfully.** No exception.
- The result **validated as OCSF.** Both fields are IP addresses; the schema is
  satisfied.
- The confidence score was **high** — the signature matched unambiguously.
- Every test **passed**, because the tests asserted that fields were extracted,
  not that they were right.
- 135 events were emitted with **source and destination silently swapped.**

In a real deployment that is an investigation pointing at the wrong host. It
would never have been noticed, because nothing was broken — it was just wrong.

It was caught by exactly one thing: comparing output against generator ground
truth. The fix was two direction-specific regexes keyed on which interface word
appears first. The regression test is
`test_asa_endpoint_order_is_not_positional`.

**The lesson, which is the lesson of the whole project:** a pipeline that reports
"98% parsed successfully" has told you nothing about correctness. Success rate
measures whether your code threw an exception. Accuracy requires ground truth.
If you build a log pipeline and do not have ground truth, you do not know
whether it works — you know it does not crash.

### Tests organised by requirement

Tests are grouped by problem-statement requirement rather than by module, so the
suite doubles as evidence. Asked "how do you know it's lossless?", the answer is
a test name:

```
TestRequirementA_Lossless::test_survives_invalid_utf8
```

91 tests. Every bug found during the build has a regression test marked
`REGRESSION` — those are the most valuable tests in the file, because each one
is a real mistake that produced a plausible-looking wrong answer.

### The fidelity audit

`strata audit` is an **independent** reconstruction: it re-reads every record
from the segment files, re-hashes it, and compares against the stored id. It
does not trust the index or any in-memory state. Result: 100.000000% byte-exact
across 20,000 records including deliberately invalid UTF-8 and truncated lines.

Then it verifies every Merkle root and the chain between them.

### Benchmark honesty

Measured: 11,440 eps single process, 20,819 on two workers (90.6% scaling
efficiency), on a 2-core container with outlets disabled so the number measures
the engine rather than disk speed.

The 8-core figure (~82,900 eps, ~7.2 billion events/day) is a **projection** from
measured scaling, and it is labelled as one everywhere it appears. Judges respect
the distinction and will ask if you blur it. You do not need to inflate: the
single-process number alone already clears the 11,574 eps that one billion
events per day requires.

---

## Part 13 — Building it from nothing

If you had to rebuild this from an empty directory, here is the dependency
order. Each stage is testable before the next one starts, which is what keeps a
two-week build from collapsing in the last three days.

### The order

**1. The data model.** Slotted frozen dataclasses: `Envelope`, `Record`,
`Event`, `Provenance`. Get `digest()` returning raw 32 bytes, not hex — hex
doubles the size of every id in memory and in the index for no benefit.

**2. Merkle.** `leaf_hash`, `node_hash`, `build`, `root_of`, `proof`, `verify`.
Write the domain-separation test and the odd-node test *first*. Pure functions,
no I/O, trivially testable, and everything downstream depends on them being
right.

**3. The ledger.** Framing, compression, append, get, scan, the index, sealing.
Test byte-exactness with deliberately hostile payloads — invalid UTF-8, embedded
nulls, empty lines, a 64 KB line. **This is the foundation; do not move on until
`audit` reports 100.000000%.**

**4. Shapes and fingerprinting.** Pure function, easy to test, no dependencies.

**5. Extractors.** The nine primitives, each a standalone function. Test each
against real vendor sample lines.

**6. Grammar schema and compiler.** Pydantic models with `extra="forbid"` — an
unknown key must be an error, because a silently ignored `fileds:` typo means an
author believes a mapping is live when it is not. Then the compiler.

**7. Triage.** Bucketing, scoring, the ambiguity rule.

**8. OCSF mapping.** Placement, enums, residue by set difference.

**9. The pipeline.** Wire 3→4→7→6→8 together. Preserve-before-parse.

**10. The synthetic generator *with ground truth*.** Do this before the Forge.
It is what lets you measure everything above, and it is where you will discover
your first three real bugs.

**11. The Forge.** Induction, then inference, then proposal.

**12. Rewind and the auditor.** Both are short, because everything they need
already exists.

**13. CLI, then API, then console.** Interfaces last. They are the most visible
part and the least load-bearing.

**14. Docs, deck, packaging.**

### Where the time actually goes

Not where you expect. The ledger and Merkle layer are maybe 15% of the code and
40% of the thinking. The console is 25% of the lines and almost none of the
intellectual content. Budget accordingly — and if you fall behind, cut console
polish, never ledger correctness.

### The minimum version that still demonstrates the thesis

If you had four days instead of two weeks, this is the cut:

- ledger with byte-exact storage and per-record digests
- **three** grammars, not ten (one CSV, one KV, one JSON — the three families
  that cover most of the perimeter)
- shape triage
- OCSF mapping with residue
- Merkle sealing + one inclusion proof
- **rewind** — never cut this, it is the differentiator
- a CLI demo, no web console

That still proves every claim that makes the project interesting. What you would
lose is polish and breadth, not the argument.

---

## Part 14 — Defending it

Likely questions, with answers that are true.

**"Why not just use Logstash / Fluentd / Vector?"**
They solve the parsing problem well and the preservation problem not at all —
raw is an optional side output, unlinked to the parsed event. Rewind is
impossible for all three, and it is impossible for an architectural reason, not
a missing feature. The claim is not that those tools are bad; it is that they
answered a different question.

**"Isn't storing everything expensive?"**
1.1–1.3× the raw feed, compressed. The decision to discard was made when storage
cost about a hundred times more. It is now cheaper to keep a year of raw logs
than to run the meeting about whether to keep them.

**"Python won't scale."**
One billion events per day is 11,574 eps sustained — a five-figure problem, not
a six-figure one. We measure 11,440 eps in one process and 20,819 on two, at
90.6% scaling efficiency. Compiled grammars, shape-first triage, and hand-written
time parsers are where that came from. If it ever needed a hundred times more,
the boundary to replace is the parse layer, and it is already isolated.

**"How do I know your Merkle implementation is correct?"**
Two specific attacks and their defences: second-preimage via missing domain
separation, and root collision via odd-node duplication. Both have tests that
construct the attack and assert rejection. Here is the code.

**"What stops a grammar from being malicious?"**
The format has no expressions, no imports and no shell. A grammar can name a
known primitive and pass arguments. The one residual risk is regex backtracking,
mitigated by a line-length cap and eliminated properly by RE2 — which is in the
limitations because it is not done yet.

**"Your data is synthetic."**
Yes, and it is generated from published vendor field references, so it is
structurally faithful but not captured traffic. Volunteer this before you are
asked. Offer to ingest anything they have on a USB stick — the demo runs
air-gapped, so you can.

**"What happens when a device sends garbage?"**
It is stored byte-exact and quarantined with a reason. It is not dropped and it
is not force-fit into a schema. Then the Forge is one click away, which is how
garbage becomes a new source rather than a support ticket.

**"What's the weakest part?"**
Answer honestly and specifically — a rehearsed "nothing really" reads as not
having looked. The truthful answer: OCSF coverage is partial (the fields our
sources emit, not the full 1.8 schema), and the integrity story stops at the
ledger boundary. Nothing proves the operator sealed an honest archive on day
one; that needs roots published to a party who is not you. The design
accommodates it. It is not built.

---

## Appendix — vocabulary

| Term | Meaning |
|---|---|
| **Ledger** | The append-only, content-addressed store of original bytes. The source of truth. |
| **Stratum** | One segment file of the ledger, sealed with a Merkle tree when it fills. Plural: strata. |
| **Frame** | One record on disk: length prefix + zstd(envelope + payload). |
| **Payload** | The original bytes of a log line. Hashed to form the record id. |
| **Envelope** | Observed facts about receipt — channel, peer, receipt time, truncation flag. |
| **Record** | Payload + envelope + id + position. |
| **Fingerprint** | The result of one character-counting pass: shape plus counts. |
| **Shape / family** | Structural class: json, kv, csv, cef, leef, delimited, freeform. |
| **Triage** | Choosing which grammar owns a line, and with what confidence. |
| **Grammar** | A YAML file describing how to read one source and map it to OCSF. Data, not code. |
| **Compiled grammar** | A grammar turned into a flat list of closures with arguments bound. |
| **Extraction** | The raw field dict a grammar produces before mapping. |
| **Residue** | Vendor fields no mapping claimed. Computed by set difference; preserved in OCSF `unmapped`. |
| **Provenance** | The link from an event back to its record id, grammar, version, confidence and byte ranges. |
| **Quarantine** | Where a record goes when confidence is below the floor. A correct output, not a failure. |
| **The Forge** | The tool that profiles unknown samples and proposes a grammar. |
| **Rewind** | Re-deriving all history from the ledger after a grammar changes. |
| **Auditor** | Independent reconstruction and re-hashing, proving requirement (a) continuously. |
| **Generation** | Which derivation pass produced an event. Distinguishes rewound events from originals. |
| **OCSF** | Open Cybersecurity Schema Framework. The target taxonomy. Version 1.8.0. |

---

*Companion documents:* [ARCHITECTURE.md](ARCHITECTURE.md) (decisions in brief) ·
[THREAT-MODEL.md](THREAT-MODEL.md) · [BENCHMARK.md](BENCHMARK.md) ·
[VERIFY.md](VERIFY.md) (reproduce every claim) ·
[DEMO-SCRIPT.md](DEMO-SCRIPT.md) · [GRAMMAR-REFERENCE.md](GRAMMAR-REFERENCE.md)
