# Verification checklist

Hand this to a judge. Every claim is checkable in under five minutes, without
taking our word for anything.

## Before you begin

**Physically disconnect the network.** Unplug the cable, disable Wi-Fi.
Everything below must still work. That is the test.

## 1. Nothing reaches out

```bash
grep -rEn "https?://" strata/ grammars/ --include="*.py" --include="*.html" --include="*.yaml" \
  | grep -vE "(example\.(com|net|org)|malware-test\.invalid|127\.0\.0\.1|localhost|www\.w3\.org)"
grep -rn "import requests\|urllib.request\|httpx" strata/
```

Expect nothing from either. The console has no CDN link, no web font, no remote
script — the favicon is an inline data URI. CI runs both greps on every push.

## 2. Install with the network forbidden

```bash
./install-offline.sh
```

`pip` runs `--no-index --find-links=wheelhouse`, which makes reaching the
network impossible rather than merely unnecessary.

## 3. Every claim, one command each

| Claim | Command | What you should see |
|---|---|---|
| It runs | `python3 strata.py check` | 10 grammars, all compiled |
| The whole story | `python3 strata.py demo` | 8 steps, ~90 seconds |
| **(a) Lossless** | `python3 strata.py audit` | `FIDELITY 100.000000%` |
| **(a) Tamper-evident** | see §4 | audit fails and names the fault |
| **Merkle proof** | `python3 strata.py prove <record-id>` | ~15 hashes, verified |
| **(b)(c) Reading** | `python3 strata.py ingest var/samples/demo.log` | map rate ≈ 0.99 |
| **(d) Traceability** | console → Inspector | byte ranges linked to OCSF fields |
| **(e)(i) Onboarding** | §5 below | your own log file, parsed, in minutes |
| **(g) Lake** | `python3 strata.py query "SELECT vendor, count(*) FROM events GROUP BY 1"` | SQL over Parquet |
| Scale | `python3 strata.py bench --workers 4` | near-linear scaling |
| Tests | `python3 -m pytest -q` | 91 passed |

## 4. Break it on purpose

```bash
python3 strata.py demo --count 4000
python3 strata.py audit                    # 100.000000%

python3 - <<'PY'
from pathlib import Path
seg = sorted(Path("var/ledger/shard-00").glob("st-*.sl"))[0]
b = bytearray(seg.read_bytes()); b[len(b)//2] ^= 0xFF; seg.write_bytes(bytes(b))
print("flipped one bit in", seg.name)
PY

python3 strata.py audit                    # fails, names the stratum and fault
```

## 5. Bring your own log file

The real test of requirement (e). Use a format STRATA has never seen:

```bash
python3 strata.py forge /path/to/your.log --id your.source --vendor Acme --product Box
```

You get the detected structural family, a profile of every field inferred **from
its values**, and a complete grammar. Add `--write` to publish, then
`python3 strata.py ingest /path/to/your.log`. No restart, no rebuild, no code.

Or in the console: **Forge** → paste → *Analyse & propose* → *Publish*.

## 6. Fix the past

```bash
python3 strata.py rewind --dry-run
```

Every historical event re-derived from the ledger under current grammars.

## What we do NOT claim

Honesty is part of the deliverable.

- Never run against a real billion-event/day production feed. We measured
  per-node throughput and scaling efficiency and did the arithmetic; method and
  limits are in `docs/BENCHMARK.md`.
- Sample logs are **synthetic**, from published vendor field references.
  Structurally faithful; not captured traffic.
- OCSF mappings cover the fields our sources emit, not the full 1.8 schema.
- ReDoS is mitigated by a length cap, not eliminated. RE2 would eliminate it.
- No encryption at rest; single-writer per shard; fixed timezone offsets only.
  All three are deliberate and documented in `docs/ARCHITECTURE.md`.
