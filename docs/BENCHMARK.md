# Throughput: method, numbers, and what they do not prove

## The arithmetic first

```
1,000,000,000 events / day  ÷  86,400 s  =  11,574 events/sec sustained
                                × 3 (typical peak factor)  ≈  35,000 eps peak
```

"Billions per day" is a five-figure events-per-second problem, not a six-figure
one. That distinction decides most of the architecture — in particular whether
a rewrite in a compiled language is necessary.

## Method

`strata.py bench` runs the complete pipeline — ledger write, triage, compiled
read, OCSF map — over a generated multi-vendor corpus with **outlets disabled**,
so the number measures the engine rather than disk write speed. Reproduce:

```bash
python3 strata.py bench --count 60000
python3 strata.py bench --count 60000 --workers 4
```

## Measured (2-core container, CPython 3.11)

| Mode | events/sec | scaling efficiency |
|---|---:|---:|
| 1 process | **11,440** | — |
| 2 processes | **20,819** | **90.6%** |

Scaling is near-linear because the pipeline is embarrassingly parallel per line
and each worker owns its own ledger shard. The ledger is single-writer **by
design** — concurrent appends to one segment would interleave and corrupt
frames — so horizontal scale comes from more shards, exactly as it would across
machines.

Projected on an 8-core host at the measured efficiency:

```
11,440 × 8 × 0.906  ≈  82,900 eps  ≈  7.2 billion events/day  on one node
```

That clears the target with a wide margin, on one machine, in pure Python.

## Where the speed came from

Three changes, in order of contribution:

**Compiled grammars.** A declarative pipeline naively walks its steps per event
and branches on step type — millions of comparisons to reach a decision fixed at
load time. Compiling each grammar once into closures with arguments bound
removes the branch, the attribute lookups and the regex re-compilation from the
hot path entirely.

**Shape-first triage.** Evaluating every grammar against every line is
O(grammars) per event. One character-counting pass narrows the candidates to a
structural family: **2.7 of 10 grammars evaluated per line, 73% of the work
avoided.** Unlike the other two, this one *improves* as sources are added.

**Slotted dataclasses in place of per-event validation.** Internal objects are
constructed once per line; a validating model charges a schema walk for each,
to validate data we produced ourselves. Pydantic stays where it belongs — at
the trust boundaries.

Batched durability matters too but is table stakes: `fsync` and `COMMIT` per
record cost more than every other stage combined, and every production log
system batches them.

## The optimisation we did NOT take

Porting the read loop to Go or Rust would give roughly another 5× per core. We
did not, because the measured Python figure already clears the requirement by
a wide margin, and the time was better spent on the Forge, Merkle proofs and
the provenance inspector. The parse layer sits behind a clean interface, so the
port remains a scheduled option rather than a rewrite.

Knowing where the ceiling is beats pretending there is not one.

## Honest limitations

- Measured on **2 cores**. The 8-core figure is a projection from measured
  scaling efficiency and is labelled as such wherever it appears.
- The corpus is **synthetic**. Real logs have longer lines and more variety, so
  expect somewhat lower throughput and better compression ratios.
- Outlets were **disabled** during measurement. With Parquet, NDJSON and CEF all
  writing, expect roughly 25–35% lower end-to-end throughput — `strata demo`
  shows that figure, and it is deliberately the slower one.
- Single-node only. Multi-node numbers would need a broker and more than one
  machine to measure honestly, so we do not quote any.
