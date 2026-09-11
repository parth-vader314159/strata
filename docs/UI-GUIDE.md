# The console, screen by screen

Everything in the UI: what it shows, where each number comes from, what every
control does, and what to say when someone points at it.

Open it with `python3 strata.py console` → **http://localhost:8400**.

> **The sentence to lead with if you are asked to describe the console:**
> *"It is one HTML file with no build step and no external requests, backed by a
> REST API. Every screen exists to make one requirement checkable by eye rather
> than taken on trust."*

---

## Contents

- [What it is, architecturally](#what-it-is-architecturally)
- [The frame — rail, status, palette](#the-frame--rail-status-palette)
- [1 · Overview](#1--overview)
- [2 · Live stream](#2--live-stream)
- [3 · Sources](#3--sources)
- [4 · Provenance inspector](#4--provenance-inspector)
- [5 · Quarantine](#5--quarantine)
- [6 · Forge](#6--forge)
- [7 · Rewind](#7--rewind)
- [8 · Integrity](#8--integrity)
- [Roles and authentication](#roles-and-authentication)
- [Why it looks like this](#why-it-looks-like-this)
- [Questions you will actually get](#questions-you-will-actually-get)
- [One-page cheat sheet](#one-page-cheat-sheet)

---

## What it is, architecturally

| | |
|---|---|
| **One file** | `strata/app/ui/console.html` — markup, CSS and JS together. No React, no bundler, no `npm install`, no build step. |
| **Zero external references** | No CDN, no web fonts, no analytics. The favicon is an inline `data:` URI. A CI job greps for external URLs and fails the build if one appears. That is what makes requirement (j), air-gapped operation, true of the UI and not just the engine. |
| **Backed by REST** | Every screen is a `fetch` against `/api/…`. The console is just the first client; the API is documented and usable on its own at `/docs`. |
| **Live over SSE** | One `EventSource` on `/api/stream` pushes a metrics tick. Server-Sent Events rather than WebSockets because the data flows one way and SSE reconnects by itself with no client logic. |
| **Served by FastAPI** | `strata/app/api.py`, 20 endpoints, Pydantic-validated bodies. |

**If asked "why not React?"** — the console is ~870 lines and has no shared
state beyond the current view. A framework would add a build step, a
`node_modules` tree to audit, and a bundle to get across an air gap, in exchange
for nothing this screen needs. It is a deliberate scope decision, not an
inability.

---

## The frame — rail, status, palette

### The left rail

Eight views in four labelled groups. The grouping is the argument, so learn it:

| Group | Views | What the group means |
|---|---|---|
| **Operate** | Overview, Live stream, Sources | Is it running, and what is it doing right now |
| **Investigate** | Inspector, Quarantine | Follow one record; see what we refused |
| **Extend** | Forge, Rewind | Add a source; fix the past |
| **Assure** | Integrity | Prove the claims |

**If asked why those four** — they are the four things an operator actually does
with a log pipeline, in the order they do them. "Assure" is separate from
"Operate" on purpose: proving integrity is not a daily task, it is what you do
when someone challenges the data.

### Status, bottom of the rail

A coloured dot plus `N eps · N in`. Green means the SSE stream is connected and
the numbers are live; red says `stream lost — retrying`. Driven by the
`EventSource` `onmessage` / `onerror` handlers, so it reflects the actual
connection, not a guess.

Under the brand, in dev mode, a red **`DEV — NO AUTH`** badge. It appears when
`/api/health` reports `auth_mode` starting with `DEV`, which happens when no
`STRATA_SECRET`/admin token is configured. It is loud on purpose — see
[Roles](#roles-and-authentication).

### Command palette — `⌘K` / `Ctrl+K`

Eleven commands: the eight views plus *Generate traffic*, *Run full audit* and
*Reload grammars*. Arrow keys and Enter, Escape to close, and it filters as you
type. Type-to-filter is on the label, so "for" finds the Forge.

**Worth demoing** — it makes the console feel like a tool rather than a
dashboard, and it costs about thirty lines.

### Toasts

Transient bottom messages for the results of actions (`4,000 normalized, 41
quarantined`). Errors surface here too, with the server's actual `detail` string
rather than a generic failure.

---

## 1 · Overview

**The question it answers:** is the pipeline healthy, and where is the work going?

### The six stat tiles

Read left to right; each comes from `/api/overview`.

| Tile | Big number | Sub-line | Where it comes from |
|---|---|---|---|
| **Events in** | lines received this session | `N / sec` | `metrics.received`, `metrics.eps` |
| **Normalized** | percentage mapped to OCSF | `N to OCSF 1.8` | `metrics.map_rate`, `metrics.mapped` |
| **Quarantined** | count refused | *declined, not mangled* | `metrics.rejected` |
| **Ledger** | records stored | `1.14× compressed · 1/2 sealed` | `ledger.records`, `.ratio`, `.sealed`/`.strata` |
| **Grammars** | grammars loaded | `N structural families` | `grammars.length`, `families` keys |
| **Preserved** | raw megabytes ingested | `N M on disk` | `ledger.bytes_raw`, `.bytes_stored` |

**Two of these are the whole pitch and you should say so:**

- *Quarantined* is deliberately labelled **"declined, not mangled."** A high
  number here is not a failure — it is the system refusing to guess. Compare
  with a pipeline that force-fits the same lines and reports 100%.
- *Preserved* shows raw bytes **and** bytes on disk side by side, so the storage
  cost of losslessness is visible rather than hidden. The ratio tile says the
  same thing from the other direction.

**Careful with "Events in" vs "Ledger".** *Events in* counts this process's
session; *Ledger* counts everything ever stored, across restarts. They differ on
a freshly started console and that is correct, not a bug. Expect that question.

### The pipeline diagram

Six stages, drawn as SVG from live counters — not a static picture:

```
INTAKE → LEDGER → TRIAGE → READ → MAP → OUTLETS
           │                 │
           │                 └── ⌄ QUARANTINE
           └──── rewind ─────────→
```

| Stage | Number shown | Sub-label |
|---|---|---|
| Intake | `received` | bytes accepted |
| **Ledger** | `stored` | originals preserved |
| Triage | `received` | `2.67 of 10 grammars` |
| Read | `mapped + rejected` | grammar pipelines |
| Map | `mapped` | OCSF 1.8 |
| Outlets | `mapped` | lake · SIEM · json |

**The Ledger box is the only one with an orange border and fill.** That is not
decoration — it marks the source of truth. Everything downstream is a derived
view. If you only get one sentence about this diagram, that is the sentence.

**The dashed amber branch** drops from *Read* into **QUARANTINE**, carrying
`rejected`. Quarantine hangs off the pipeline rather than sitting in it, because
a quarantined record is not a failed event — it is a stored record awaiting a
grammar.

**The dashed orange path** leaves the **Ledger**, runs beneath the pipeline and
arrows back into **Read**: *rewind — re-derive history from preserved originals.*
It starts at the Ledger specifically because that is what rewind replays from.
(It used to be drawn from Intake, which was wrong and is fixed — mention it if
you want to show you audit your own diagrams.)

The SVG's width is **computed**, not hard-coded: `8 + 6·150 + 5·36 + 12`. A
hard-coded viewBox clipped the final stage; there is a comment in the source
saying so.

### Structural families

Each family with the grammars in it. The note above it is the argument:

> *Coverage is argued by structural family, not product count. A new source in a
> family we already handle is a configuration change, not a development task.*

**If asked "you only support ten vendors?"** — this panel is the answer. We
support **seven structural families**. The eleventh vendor is a YAML file if its
shape is one we already parse, and the Forge writes that YAML for you.

### Triage selectivity

A large percentage — *of classification work avoided* — plus
`2.67 of 10 grammars evaluated per line` and the number of lines triaged. All
from `triage.selectivity()`.

**Why this panel exists at all:** it is the only number on the Overview that
*improves* as you add sources. Everything else is a constant factor; this one
changes how onboarding scales. `work_avoided = 1 − (evaluated / (lines ×
grammars))`.

### Buttons

- **Generate traffic** — `POST /api/synth {count: 4000}`. Generates and ingests
  4,000 synthetic multi-vendor events. This is the demo button.
- **Run audit** — jumps to Integrity and runs a full audit.

---

## 2 · Live stream

**The question it answers:** what is coming out, right now, in one vocabulary?

Nine columns, up to 80 rows, newest first:

| Column | Meaning |
|---|---|
| `time` | The **event's own** time (`ev.time`), not receipt time — `HH:MM:SS` UTC |
| `grammar` | Which grammar claimed the line (`strata.grammar`) |
| `source` | `src_endpoint.ip:port` |
| `destination` | `dst_endpoint.ip:port` |
| `proto` | `connection_info.protocol_name` |
| `disposition` | Coloured tag from `disposition_id` |
| `bytes` | `traffic.bytes` |
| `conf` | Triage confidence, 0–1 |
| `unmapped` | **Count of residue fields kept** |

**Disposition colours:** `1 allowed` green · `2 blocked` red · `3 dropped` red ·
`8 reset` amber · `99 other` and `0 unknown` grey. Vendor words are collapsed to
these ids, and the vendor's original word is kept in the event — that is the
`keep:` clause in the grammar.

**The `unmapped` column is the one to point at.** It is a live count of fields
this event carried that no mapping claimed — and they are still there. On a
FortiGate row it is typically 13. A conventional pipeline would show nothing
because those fields no longer exist.

**Controls:** a grammar filter dropdown (populated from the loaded grammars),
and **Pause** — which stops the table refreshing so you can read a row mid-demo
without it scrolling away. Small thing, saves a live demo.

**Click any row** → loads that record into the Inspector and switches view. That
click is the bridge from "a stream of events" to "this exact event came from
these exact bytes", and it is the single most important interaction in the
console.

---

## 3 · Sources

**The question it answers:** what do we understand, and how was each one built?

| Column | Meaning |
|---|---|
| `grammar` | Grammar id, e.g. `fortigate.traffic` |
| `vendor` / `product` | Declared in the grammar |
| `family` | Structural family tag — what gates triage |
| **`compiled pipeline`** | The compiled step chain, e.g. `syslog? → kv` |
| `events` | How many lines this grammar has read this session |
| `share` | A bar, relative to the busiest grammar |

**`compiled pipeline` is the interesting column.** It shows the actual closure
chain the grammar compiled to, with `?` marking optional steps. `syslog? → kv`
means "strip a syslog header if there is one, then read key=value pairs."

**If asked how a grammar becomes code:** point here and say the YAML compiled to
*that*, once, at load — not per event. This column is the visible evidence of
the compiled-grammar decision.

**Click a row** → filters the Live stream to that grammar.

**Reload grammars** re-reads the `grammars/` directory without a restart
(maintainer only).

---

## 4 · Provenance inspector

**The question it answers:** requirement (d) — can you prove this event came
from that line? **This is the best screen in the product. Demo it.**

Enter a 64-hex record id, or **Take a recent one**, or arrive by clicking a
stream row. Calls `GET /api/record/{id}/provenance`, which **re-derives the
event from the stored bytes on the spot** — it does not read a cached event.

### Four tiles

| Tile | Shows |
|---|---|
| **Grammar** | id, version, triage confidence |
| **Shape** | structural family + the compiled step chain |
| **Field coverage** | % of the line's fields consumed by the mapping, plus `N mapped, N kept` |
| **Record** | first 16 hex of the content address — *byte-exact from the ledger* |

**Field coverage is not an error rate.** 59% does not mean 41% was lost — it
means 41% was **kept as residue**. Say this before anyone asks, because the
number looks bad out of context and is actually the point.

### Original bytes

The raw line, exactly as received, with every extracted value wrapped in a
`<mark>`. Orange marks were consumed by the mapping; amber-bordered ones are
residue.

### Byte range → OCSF field

One row per extracted value: the vendor field name on the left, the OCSF path it
became on the right, or `→ unmapped (kept)`.

**Hover either side and both light up.** The linking is two-way — hover a
highlighted span in the raw line and its field row lights; hover a field row and
the span lights. Clicking a span scrolls its row into view.

**How the byte ranges are computed** (expect this question): the endpoint
re-parses the line, then for each extracted value searches the raw text for an
occurrence that does not overlap a span already claimed. That last clause
matters — a value appearing twice highlights two distinct places rather than the
same one twice.

**The honest limitation:** it locates values by searching the text, not by
instrumenting the parser to emit offsets. For a value that genuinely appears
nowhere in the raw line — a computed or defaulted field — there is no span and
no highlight. Instrumented offsets would be exact; this is a display aid that is
correct for every value actually present in the line.

### Normalized event · Unmapped

The full OCSF document, and the residue object under *retained, never dropped*.
The residue panel is the visual proof that set-difference residue works.

---

## 5 · Quarantine

**The question it answers:** what did we refuse, and why?

The header states the principle:

> *Unknown beats wrong. A misread log parsed confidently into the wrong fields
> is more dangerous than an unparsed one, because it looks correct.*

| Column | Meaning |
|---|---|
| `verdict` | Why it was refused |
| `best guess` | The grammar that came closest, if any |
| `confidence` | Its score — below the floor, which is why we are here |
| `detail` | Human-readable reason |
| `record` | First 20 hex of the content address — **it is still stored** |

**The five verdicts** (from `Verdict` in `core/model.py`):

| Verdict | Means |
|---|---|
| `MAPPED` | Understood and normalized — never appears here |
| `UNCLAIMED` | No grammar recognised it |
| `AMBIGUOUS` | More than one grammar claimed it, none convincingly |
| `EXTRACT_FAILED` | Recognised, then a non-optional step failed |
| `INVALID` | Extracted, but the result is not valid OCSF |

**`AMBIGUOUS` is the one worth explaining.** It is the ambiguity rule made
visible: when two grammars score within 0.12 of each other, the leader's
confidence is multiplied by 0.55, which usually pushes it under the 0.70 floor.
A coin-flip becomes a visible "we don't know" rather than a silent guess.

Below the table, **Samples** — the raw lines, which are the Forge's input queue.

**Onboard these →** loads up to 250 quarantined samples into the Forge and
switches view. That button is the demo's turning point.

---

## 6 · Forge

**The question it answers:** requirements (e) and (i) — how long does a new
source take? **Do this live.**

### Inputs

*Load quarantined samples* · grammar id · vendor · product · a textarea for
pasted lines · **Analyse & propose** · **Publish grammar** (disabled until the
proposal validates) · and an elapsed-milliseconds readout.

### What comes back

Four tiles:

| Tile | Shows |
|---|---|
| **Structure** | detected family + `syslog-wrapped` or `bare payload` |
| **Fields found** | distinct fields discovered, and from how many lines |
| **Auto-mapped** | % mapped to OCSF, *by name and by value* |
| **Valid grammar** | yes/no — green or red; the error if not |

Then any **notes** (amber warnings — low-confidence guesses the human should
check), the **field profiles** table, and the **generated grammar** YAML.

### The field profiles table — the part to talk about

| Column | Meaning |
|---|---|
| `field` | The field name, or a positional label like `col_08` if the format has no names |
| `kind` | Inferred value kind: `ipv4`, `port_or_int`, `timestamp`, `mac`, `url`, `hostname`, `hexid`, `bool`, `text`… |
| `purity` | What fraction of observed values are that kind — the confidence in the inference |
| `distinct` | Cardinality, which separates an address from a constant |
| `samples` | Actual observed values |

**This table is the argument that the Forge is not magic.** It shows exactly what
it observed and how confident it is. When someone asks "how does it know column
eight is a source IP?", point at `kind=ipv4, purity=100%, distinct=137` and
explain the adjacency rule: the first two high-cardinality IPv4 fields are source
and destination in that order, and a small integer immediately after an IPv4
field is that endpoint's port.

**Publish** writes the YAML into `grammars/` and hot-reloads. The toast reports
the new active count and `restart required: false`. If the grammar fails to
compile it is **rejected and rolled back**, and the toast says so — a bad
grammar cannot take the pipeline down.

**The boundary to defend:** the Forge *proposes*, a human *publishes*. Every
inference rule is a heuristic. Auto-publishing would reintroduce exactly the
silent-wrong-mapping failure the whole project exists to prevent. And the
proposal is validated by the same schema as a hand-written grammar — no special
case, no privileged path.

---

## 7 · Rewind

**The question it answers:** we got a mapping wrong six months ago. Now what?

Three controls: a **dry run** checkbox (**checked by default**), a **limit**
(0 = all), and **Run rewind**. Output is the raw JSON result.

The result reports records replayed, re-derived, still quarantined, and the
generation number.

**Dry run defaults to on** because re-deriving is safe and emitting is the part
worth being deliberate about. Point that out — defaults are a design statement.

**What to say:** this replays the ledger through the *current* grammars and
rebuilds the derived view. **Nothing is written to the ledger** — history is not
rewritten, it is re-*read*. Running it twice produces identical output, because
record ids are content addresses, so replay is idempotent with no "did this
already run?" state to track.

**The generation counter** distinguishes a rewound event from an original one, so
you can tell which derivation pass produced any given event.

**The line that lands:** no tool that discards the raw can do this at any price.
It is about sixty lines of code — not because it is clever, but because the
architecture was built for it.

---

## 8 · Integrity

**The question it answers:** requirement (a), proven rather than claimed.

**Run full audit** calls `/api/integrity`, which reconstructs **every** stored
record from the segment files, re-hashes it, and compares against its content
address. It does not trust the index or any in-memory state.

### Four tiles

| Tile | Shows |
|---|---|
| **Byte fidelity** | `100.0000%` — `N / N exact`. Green only if fidelity is exactly 1 |
| **Merkle + chain** | `intact`, and the fault count |
| **Strata** | segment count, and how many are sealed and rooted |
| **Records** | how many were reconstructed and re-hashed |

**Fidelity is displayed to four decimal places on purpose.** 99.9999% is not
100%, and rounding to "100%" would hide a real fault. If it is not exactly 1 the
tile turns red.

### Published roots — *safe to print*

The Merkle root of each sealed stratum, with its record count. The subtitle is
the claim: a root reveals nothing about contents, so you can publish it in a
newspaper, email it to a regulator, or read it aloud. Publishing it somewhere you
do not control is what would make the archive externally verifiable — which the
design accommodates and the shipped system does not do.

### Inclusion proof

Paste a record id, press **Prove**, get the JSON proof: stratum, leaf count,
proof size in sibling hashes, the root, and whether it verified.

**The sentence:** with the record, this proof and the published root, anyone can
verify membership *without access to this machine* and **without learning
anything about any other record.** About 15 hashes for 20,000 records. That is
the difference between "trust our database" and evidence.

---

## Roles and authentication

Three roles, checked **server-side per endpoint** in `api.py`:

| Role | Level | Can do |
|---|---|---|
| `viewer` | 0 | Overview, Integrity, events, quarantine, inclusion proofs, Forge *study/propose*, read grammar source |
| `analyst` | 1 | Everything above **plus raw record content** — `/record/{id}`, `/provenance` — and ingest/synth |
| `maintainer` | 2 | Everything above plus **publish grammar**, reload, rewind, audit log |

**Three things to say about this design:**

1. **Raw log content sits behind `analyst`, not `viewer`.** Reading raw evidence
   is a privileged act and every access is audited, because *who read this
   evidence* is itself a forensic question.
2. **Publishing a grammar is `maintainer`** because it changes what the whole
   organisation is able to see. It is closer to a schema migration than a config
   edit.
3. **Checks are server-side.** A hidden button is not authorization — there is a
   comment in the source saying exactly that.

**Tokens** are HMAC-SHA256 signed, carry `role:expiry`, and are compared with
`hmac.compare_digest` — constant-time, because a naive `==` leaks the signature
one byte at a time under a timing attack.

**Dev mode.** With no admin token configured, `/api/login` hands out a
maintainer token to anyone, and the console shows a red **`DEV — NO AUTH`**
badge with `/api/health` reporting the same. Loud by design so nobody ships it
by accident. **For a demo this is fine and you should say so out loud** — "this
is running in dev mode, which is why it is telling you there is no auth."

**Audit log.** Privileged actions append to `var/out/audit.ndjson` — append-only,
so an insider who publishes a grammar leaves a trace they cannot remove from the
console.

---

## Why it looks like this

Design questions get asked more than people expect. Short answers:

**The palette.** Near-white paper `#FAFAF9`, near-black ink `#14151A`, and
**exactly one accent** — orange `#D9500C`. One accent means the orange always
means something: it marks the Ledger, the signal path, the active state. A
second accent colour would dilute it. Green, amber and red appear *only* as
status semantics (good / warning / bad), never as decoration.

**Light-first, with a dark mode** via `prefers-color-scheme`. Analysts work in
both.

**Monospace for data, sans for prose.** Every log line, record id, field name and
grammar id is monospace — because they are machine output and alignment carries
meaning. Headings and explanation are sans. The split is consistent everywhere,
including the video reel and the deck.

**The explanatory `note` paragraphs** on Overview, Quarantine and Integrity are
deliberate. This is a console a judge sees for ninety seconds; it should teach
its own argument without a narrator. In a product used daily you would demote
them to tooltips.

**No modals** except the command palette. Every destructive-ish action reports
through a toast, and the one genuinely consequential action — rewind — defaults
to a dry run rather than asking "are you sure?".

**Responsive** — the rail collapses and tables scroll horizontally inside their
panels. The page body never scrolls sideways.

---

## Questions you will actually get

**"Is this real or a mockup?"**
Real. Every number is a live API response. Press *Generate traffic* and watch
the counters move; the audit reconstructs all 20,000 records for real and takes a
visible moment doing it.

**"Why does quarantine have anything in it? Isn't that a failure?"**
No — it is the system refusing to guess. The corpus deliberately includes a
vendor format no grammar knows. A pipeline that reports 100% on that input is
force-fitting lines into the wrong fields, which is worse. Then click *Onboard
these →* and the number goes to zero in about eight milliseconds.

**"What's `unmapped`?"**
Fields the vendor sent that our mapping didn't claim — kept in OCSF's own
`unmapped` object. Computed as a set difference, so forgetting to map something
makes it visible rather than losing it. OCSF's base event class defines that
field, so we are not inventing a place to put it.

**"Field coverage is only 59% — what happened to the rest?"**
It is kept. Coverage measures what the mapping *consumed*, not what survived.
The Unmapped panel directly below shows the remainder.

**"Can I break it?"**
Paste nonsense into the Forge — you get a proposal that fails validation and the
Publish button stays disabled. Publish a broken grammar and it is rejected and
rolled back. Ask for a record id that doesn't exist and you get a 404 with a
readable message, not a stack trace.

**"How do I know the audit isn't just printing 100%?"**
Flip a byte in a segment file under `var/ledger/` and run it again. It names the
record. Offer to do it.

**"Why is there no login screen?"**
There is auth — three roles, HMAC tokens, server-side checks. It is in dev mode
right now, which is why the header says `DEV — NO AUTH` in red. Set
`STRATA_SECRET` and an admin token and `/api/login` starts demanding one.

**"What's the weakest part of the UI?"**
Answer honestly; a rehearsed "nothing" reads as not having looked. Truthfully:
the inspector locates byte ranges by searching the raw text rather than by
instrumenting the parser, so a computed or defaulted field has no highlight.
There is also no time-range filter or free-text search on the stream — it is a
live tail, not an investigation tool, and a real deployment would need both.

---

## One-page cheat sheet

| View | One sentence | Demo move |
|---|---|---|
| **Overview** | Health, throughput, and where the work goes. | Press *Generate traffic*, watch the pipeline fill. |
| **Live stream** | Normalized events in one vocabulary, with a live residue count. | Point at `unmapped`. Click a row. |
| **Sources** | Every grammar and the closure chain it compiled to. | Point at `compiled pipeline`. |
| **Inspector** | These exact bytes became these exact fields. | Hover a highlighted span. |
| **Quarantine** | What we refused, and why. Unknown beats wrong. | Explain `AMBIGUOUS`, then *Onboard these →*. |
| **Forge** | A new source in seconds, proposed then published by a human. | Show the profiles table, publish, watch the count change. |
| **Rewind** | Fix the grammar, fix the past. Nothing written to the ledger. | Run the dry run. |
| **Integrity** | 100.0000% byte-exact, provable one record at a time. | Run the audit, then prove one record. |

**Six-minute route:** Overview → *Generate traffic* → Live stream → click a row →
Inspector (hover) → Quarantine → *Onboard these* → Forge → publish → Rewind →
Integrity → prove one record.

That order is not arbitrary: it is the product's argument in sequence — *we
normalize, we keep the original, we can prove it, we refuse to guess, we can
learn, and we can fix the past.*
