# Demo script — 6 minutes

Rehearse three times. **Unplug the network before you start, and say so.**

---

## 0:00 — The hook (30 s, no slides)

> "Every security device in this room writes down what it saw. This is a Palo
> Alto firewall saying a connection was blocked."  *(show one line)*
> "This is a FortiGate saying exactly the same thing."  *(show another)*
>
> "A SIEM can only correlate data that shares a vocabulary, so somebody writes
> a parser per vendor. That parser keeps the twelve fields it was told to keep
> and **throws the original away.** Six months later a new attack technique
> makes field thirty-eight matter, and it is gone forever.
>
> **We built the translator that never throws anything away.**"

Pull the ethernet cable. "Everything from here runs offline."

---

## 0:30 — One command

```bash
python3 strata.py demo
```

Eight steps, ~90 seconds. Narrate while it runs.

---

## 1:00 — Claim 1: nothing is lost, and we can prove it

```bash
python3 strata.py audit
#  FIDELITY        100.000000%
#  MERKLE + CHAIN  intact
```

> "Twenty thousand events from ten vendors. Every original byte stored,
> compressed, content-addressed. An independent auditor reconstructed every
> record and re-hashed it. **Including** the lines containing invalid UTF-8 —
> that one case kills most log pipelines quietly, because they decode on
> receipt and destroy the original before it is ever stored."

---

## 1:45 — Claim 2: evidence, not just integrity

```bash
python3 strata.py prove <record-id>
#  leaves in stratum  20,000
#  proof size         15 sibling hashes
#  verified           YES
```

> "A hash chain proves the whole archive is intact. But to convince you that
> *one specific line* is in it, a chain makes me hand you every other line —
> which in a real case belongs to other people.
>
> Each stratum is sealed with a Merkle tree, so one record is proven with
> fourteen hashes. You learn that this line is in the archive and **nothing
> whatsoever** about any other. That is the difference between 'trust our
> database' and evidence."

Then break it in front of them:

```bash
python3 - <<'PY'
from pathlib import Path
seg = sorted(Path("var/ledger/shard-00").glob("st-*.sl"))[0]
b = bytearray(seg.read_bytes()); b[len(b)//2] ^= 0xFF; seg.write_bytes(bytes(b))
PY
python3 strata.py audit        # fails, names the stratum and the fault
```

> "One bit. Detected, and it tells you where."

---

## 2:45 — Claim 3: the inspector  ← *the moment they remember*

Open the console → **Inspector** → click any event.

> "Most tools give you an event id and say 'the original is over there
> somewhere'. Look at what this shows: the original bytes, with **every
> extracted value highlighted**, each one linked to the OCSF field it became.
>
> Hover a field, the bytes light up. Hover the bytes, the field lights up.
> These exact characters became this exact field. That is traceability you can
> point at rather than a promise."

---

## 3:45 — Claim 4: a new source, live

**Invite a judge to hand you a log file.** If they have none, use Quarantine.

Console → **Forge** → *Load quarantined samples* → *Analyse & propose*.

> "This format is not in our system. No grammar, no vendor documentation.
> We detect the structure, then **profile every field by its values** — not by
> its name, because positional CSV has no names. A column that is always an
> IPv4 address, followed by one that is always an integer under 65,536, is an
> endpoint and its port whatever it is called.
>
> Eight fields found, seven mapped to OCSF automatically. Proposed in seven
> milliseconds."

Click **Publish**.

> "Live. No restart, no rebuild, no code. Industry standard for onboarding a new
> log source is two to five engineer-days."

---

## 4:45 — Claim 5: fix the grammar, fix the past

```bash
python3 strata.py rewind --dry-run
#  records replayed   20,000
#  re-derived         20,000
#  still quarantined  0
```

> "Every event that was quarantined ninety seconds ago has been re-derived from
> the ledger under the new grammar. **We just corrected history.**
>
> No other tool can do this — not because it is hard, but because they all
> discarded the raw. We treat the ledger as the source of truth and the
> normalized event as a disposable view. That one inversion is why this costs
> sixty lines instead of a data-recovery project."

---

## 5:30 — Scale, honestly

```bash
python3 strata.py bench --count 60000 --workers 4
```

> "One billion events a day is 11,574 per second. We measure **11,440 per
> core**, scaling at 90% — about 7 billion a day on one eight-core machine, in
> pure Python.
>
> Three things got us there: grammars are compiled once into closures instead
> of interpreted per event; a single character-counting pass narrows ten
> grammars to under three per line, which *improves* as sources are added; and
> the hot path uses slotted dataclasses instead of paying a validation library
> per event.
>
> We did **not** rewrite in Go. The measured number already clears the
> requirement, and the time was better spent on what you just watched."

---

## 5:50 — Close

> "Ninety-one tests, organised by requirement — ask 'how do you know it's
> lossless' and the answer is a test name. And the cable has been out of this
> machine the entire time."

---

## Anticipated questions

**"Why OCSF instead of your own schema?"**
> Six weeks to build something worse, and it would undermine the one claim the
> problem statement cares most about. OCSF is Linux Foundation-governed,
> version 1.8, March 2026. Its base event class already defines `unmapped`, so
> requirements (a), (c) and (d) land on a published standard rather than our
> opinion.

**"Only ten grammars?"**
> Seven *structural families* — CSV, key=value, JSON, freeform prose,
> whitespace-delimited, CEF and LEEF. Products within a family are
> configuration, not development. Our CEF grammar onboards any CEF-speaking
> vendor in existence and reports the real vendor from the wire. And you just
> watched an eleventh source added in under ten milliseconds.

**"What if a grammar is wrong?"**
> Three answers. Low confidence is quarantined rather than guessed — and if two
> grammars both claim a line, we *lower* the confidence rather than let one
> silently win. The raw bytes are intact regardless. And you can fix the grammar
> and rewind history.
>
> Worth adding: our own ground-truth test caught exactly this. Cisco ASA writes
> "for outside:X to inside:Y", so for an outbound connection the *first* address
> is the destination. Naming captures positionally swapped source and
> destination on every ASA line — the parse succeeded, the OCSF validated, and
> every direction-based detection would have been inverted. There is a
> regression test named after it.

**"How do you stop a malicious grammar?"**
> The format cannot express anything dangerous — no expressions, no imports, no
> shell, and unknown keys are rejected rather than ignored. A grammar can only
> name a known primitive and supply arguments. The restraint *is* the control,
> and there is a test that tries to publish one with an `exec` step.

**"What stops someone flooding you to blind the SOC?"**
> Per-source token bucket, so one device cannot starve the others, and refusals
> are shown on the console rather than swallowed. A silent drop is the
> difference between having the logs and thinking you do.

**"Is this production-ready?"**
> No, and I would distrust anyone who said yes. Not done: encryption at rest,
> multi-node coordination, TLS syslog, signed grammars, and RE2 to eliminate
> ReDoS rather than mitigate it. All five are in `docs/THREAT-MODEL.md` under
> residual risks. What *is* production-grade is the storage format, the
> losslessness guarantee, the Merkle proofs and the test suite.
