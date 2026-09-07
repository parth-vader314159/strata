# STRATA

**Universal log pre-processing.** Layered, legible, nothing rewritten.

Built for the Smart India Hackathon problem statement *Universal Log
Pre-processing Framework (ULPF)*. Scope: perimeter network devices.

---

## The problem, in four lines

The same fact — *this machine talked to that one and was blocked* — written
down four ways:

```
Palo Alto   1,2026/08/26 14:32:07,0142,TRAFFIC,end,2561,...,10.10.4.55,203.0.113.42,...
FortiGate   date=2026-08-26 srcip=10.10.4.55 srcport=49832 dstip=203.0.113.42 action="deny"
Suricata    {"timestamp":"2026-08-26T14:32:07","src_ip":"10.10.4.55","dest_ip":"203.0.113.42"}
Cisco ASA   %ASA-6-106023: Deny outbound TCP connection for outside:203.0.113.42/443 to ...
```

A SIEM can only correlate data that shares a vocabulary. Today somebody writes
a parser per vendor, that parser keeps the dozen fields it was told to keep,
and **the original is thrown away.** Six months later a new attack technique
makes field 38 matter, and it is gone.

STRATA gives the SIEM one vocabulary — and keeps every original byte, provably.

---

## Quick start

New to this machine? **[SETUP.md](SETUP.md)** has step-by-step instructions for
Windows, macOS and Linux.

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python3 strata.py demo        # 90 seconds, no network needed
python3 strata.py console     # http://localhost:8400
```

Containerised (requirement k): `cp .env.example .env` then `docker compose up -d`.
Air-gapped (requirement j): `./build-bundle.sh`, carry it across, `./install-offline.sh`.

---

## What is different about it

### 1. The ledger is the source of truth, not a backup

This is the bet everything else follows from. Conventional pipelines treat the
parsed event as the product and the raw log as an optional copy. STRATA inverts
it: raw bytes are canonical, immutable and content-addressed, and normalized
events are a **derived, disposable view**.

Requirement (a) then stops being a feature to bolt on and becomes a property of
the design. Requirement (d) comes free. And —

### 2. Rewind: fix the grammar, fix the past

```bash
python3 strata.py rewind --dry-run
#  records replayed  20,000
#  re-derived        20,000
#  still quarantined 0
```

Found a mapping bug six months in? Correct the YAML and re-derive every
historical event from untouched originals. **No tool that discards the raw can
do this.** It cost about sixty lines, because the architecture was built for it.

### 3. Merkle proofs — evidence without disclosure

A hash chain proves the whole archive is intact, which is useful. But to
convince somebody that *one specific line* is in the archive, a chain forces
you to hand over every other line — often exactly what you cannot do.

STRATA seals each stratum with a Merkle tree, so a single record is proven with
about log₂(n) sibling hashes:

```
stratum 1 · 20,000 leaves · proof size 15 hashes · verified
```

The verifier learns that this line is in the archive and **nothing at all about
any other line**. That is the difference between "trust our database" and
evidence.

### 4. The provenance inspector

Not "here is an identifier you could look up" — the console shows the original
bytes with **every extracted value highlighted**, each linked to the OCSF field
it became. Requirement (d) as something you can point at.

### 5. Shape-first triage — why it scales

Classifying a line by testing every grammar's rules is O(grammars) per event,
so onboarding sources makes the pipeline slower — exactly backwards. STRATA
decides a line's *structural family* in one character-counting pass and only
evaluates same-family grammars.

Measured: **2.7 of 10 grammars evaluated per line, 73% of the work avoided.**
Onboarding the fiftieth source costs the other forty-nine nothing.

### 6. Compiled grammars, not interpreted ones

A grammar is compiled once into a flat list of closures with arguments bound —
regexes compiled, column names frozen, OCSF paths pre-split, cast functions
resolved. Per event there is no branching on step type, because the step type
was fixed the moment the grammar loaded. It is the largest single throughput
win in the parse layer and costs nothing at runtime.

### 7. Unknown beats wrong

A misidentified log confidently parsed into the wrong fields is **more
dangerous** than an unparsed one, because it looks correct and nothing alerts.
Every decision carries a confidence score, ambiguity between two grammars
*lowers* it rather than hiding behind a raw number, and anything below the floor
is quarantined visibly.

---

## Architecture

```
   syslog udp/tcp/tls · file · http
                 │
                 ▼
        ┌────────────────┐
        │ 1  INTAKE      │ admission list · token bucket · observed peer
        └───────┬────────┘ truncation flag · size cap
                ▼
        ┌────────────────┐
        │ 2  LEDGER      │ ◄── SOURCE OF TRUTH
        └──┬──────────┬──┘     bytes · zstd · sha256 · Merkle-sealed strata
           │          │        nothing is ever edited or deleted
           │          └──────────────► 8  REWIND ──┐
           ▼                                        │ re-derive history
   ┌────────────────┐                               │ after a grammar fix
   │ 3  TRIAGE      │ ◄─────────────────────────────┘
   └───┬────────┬───┘  shape in one pass → same-family grammars only
       │        └── confidence < floor ──► QUARANTINE ──► 7 FORGE
       ▼                                                     │ proposes
   ┌────────────────┐                                        │ a grammar
   │ 4  READ        │ ◄──── compiled grammar plans ◄──────────┘  hot reload
   └───────┬────────┘
           ▼
   ┌────────────────┐
   │ 5  MAP         │  → OCSF 1.8 · enum collapse · residue by set difference
   └───────┬────────┘
           ▼
   ┌────────────────┐
   │ 6  OUTLETS     │  Parquet lake · CEF→SIEM · NDJSON · in-memory
   └────────────────┘

   9  AUDITOR   reconstructs from the ledger and re-hashes, independently
  10  CONSOLE   REST API · provenance inspector · RBAC · audit log
```

Module docstrings carry the detail. Design decisions:
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** ·
threat model: **[docs/THREAT-MODEL.md](docs/THREAT-MODEL.md)**.

---

## Requirement traceability

| Req | Requirement | Where | Verify with |
|---|---|---|---|
| **a** | Lossless raw preservation | `store/ledger.py` | `strata audit` → 100.000000% |
| **b** | Parse source attributes | `parse/` + 10 grammars | `strata ingest` → map rate |
| **c** | Common taxonomy | `mapping/ocsf.py` → OCSF 1.8 | every event validated |
| **d** | Traceability | provenance envelope + inspector | console → Inspector |
| **e** | Plug-and-play onboarding | `learn/forge.py` | Forge tab, no restart |
| **f** | Unified visibility | `app/` console | `strata console` |
| **g** | SIEM + lake integration | `io/outlets.py` | `strata query "SELECT …"` |
| **h** | AI/ML-ready | typed Parquet, stable names | `strata query` |
| **i** | Reduced parser effort | Forge | days → seconds, on stage |
| **j** | Air-gapped | `install-offline.sh`, CI-enforced | unplug the cable |
| **k** | Containerised | `Dockerfile`, compose | `docker compose up` |

---

## Measured

```
10 grammars · 7 structural families · 91 tests passing

20,000 synthetic events across 10 vendors
  → 98.97% normalized to OCSF 1.8 (the remainder is a format no grammar knows)
  → 100.000000% byte-exact reconstruction
  → Merkle roots and root chain intact
  → 100% field accuracy against generator ground truth
  → unknown vendor format: 8 fields found, 7 auto-mapped, onboarded in under 10 ms
  → rewind: 20,000 of 20,000 re-derived, 0 left quarantined

throughput   11,440 eps single process
             20,819 eps on 2 workers (90.6% scaling)
             ≈7.2 billion events/day projected on 8 cores

triage       2.7 of 10 grammars evaluated per line — 73% of the work avoided
air-gap      0 external references, 0 network-client imports (enforced by CI)
```

1 billion events/day is 11,574 eps sustained. Method, profiling data and honest
limits: **[docs/BENCHMARK.md](docs/BENCHMARK.md)**.

---

## Commands

```
strata.py check                    environment and grammar health
strata.py demo                     the full scripted demonstration
strata.py generate --count 50000   synthetic corpus with ground truth
strata.py ingest <file>            process a log file
strata.py audit                    requirement (a), proven
strata.py prove <record-id>        Merkle inclusion proof
strata.py rewind --dry-run         re-derive history from the ledger
strata.py forge <file> --write     propose a grammar from samples
strata.py bench --workers 4        measured throughput
strata.py query "SELECT …"         DuckDB SQL over the Parquet lake
strata.py serve                    live syslog listeners
strata.py console                  web console + REST API
```

---

## Writing a grammar

Grammars are **data, not code** — that is the decision requirements (e) and (i)
rest on. Drop a YAML file in `grammars/`, reload, done.

```yaml
id: acme.firewall
version: 1.0.0
vendor: Acme
product: FireBox
family: kv                      # structural family; gates triage

signature:                      # how do we recognise this source?
  must: ["acme-fw"]
  weight: 0.95

pipeline:                       # compiled once into closures
  - syslog: auto
    optional: true
  - kv: true
    pair_sep: "|"               # some vendors separate pairs with a pipe

coerce: {srcport: int, dstport: int}

clock:
  field: eventtime
  formats: [epoch]
  zone: UTC                     # fixed offsets only — see docs

emit:
  class: 4001
  category: 4
  fields:
    src_endpoint.ip: srcip
    dst_endpoint.ip: dstip
  enums:
    disposition_id:
      source: action
      table: {allow: 1, deny: 2, drop: 3}
      default: 99
      keep: disposition_orig    # never lose the vendor's own word
```

The format is deliberately weak: no expressions, no imports, no shell. A
grammar can only name a known primitive and supply arguments. **That restraint
is the security control** — grammars are untrusted input, and an expressive
grammar format is remote code execution with a friendly name.

Primitives: `syslog`, `columns`, `whitespace`, `kv`, `json`, `regex`, `cef`,
`leef`, `prefix`. Full reference: **[docs/GRAMMAR-REFERENCE.md](docs/GRAMMAR-REFERENCE.md)**
(generated from the grammars, and CI fails if it goes stale).

---

## Testing

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q          # 91 passed
```

Tests are organised **by requirement**, not by module, so the suite doubles as
evidence. Ask "how do you know it's lossless?" and the answer is a test name:
`TestRequirementA_Lossless::test_survives_invalid_utf8`.

Every bug found during the build has a regression test marked `REGRESSION`.
They are the most valuable tests in the file — each one is a real mistake that
produced a plausible-looking wrong answer. The best of them is
`test_asa_endpoint_order_is_not_positional`.

---

## Known limitations

Stated plainly, because pretending otherwise is how a viva goes badly.

- Sample logs are **synthetic**, generated from published vendor field
  references. Structurally faithful; not captured traffic.
- Throughput measured on 2 cores; the 8-core figure is a labelled projection
  from measured scaling efficiency.
- OCSF mappings cover the fields our sources emit, not the full 1.8 schema, and
  validation checks structure rather than the complete published schema.
- The ledger is **single-writer per shard** by design. Scale by sharding.
- No encryption at rest. The frame format carries a version byte so it can be
  added without migration.
- Timestamp zones must be fixed offsets. Named zones would make a stored
  timestamp depend on a tz-database version — unacceptable for evidence.
- Regex runs on Python's backtracking engine. Line length is capped and every
  grammar's patterns are reviewed, but RE2 would remove the class entirely.
