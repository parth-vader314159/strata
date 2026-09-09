# References and resources

Everything STRATA's design draws on, plus every third-party component it ships
with.

---

## How to read this list — please don't skip

The entries below are split by **how well each one is verified**, because that
distinction matters if a judge asks you to defend a claim.

- **[VERIFIED]** — checked during the build. Dependencies come from
  `requirements.txt`; a few URLs were confirmed by search.
- **[DESIGN BASIS]** — standards and papers the design follows, cited from
  working knowledge. They are long-standing and stable, but **the specific
  clause, section number or field name was not re-read against the source
  document while building.** If you quote one to a judge, open it first.
- **[NEEDS CHECK]** — something we could not confirm and you should verify
  before submitting. There is one of these and it is not trivial.

Nothing here was scraped, copied or vendored. All the code is original.

---

## ⚠ Verify before you submit

**[NEEDS CHECK] The OCSF version string.**

STRATA claims to target **OCSF 1.8.0** in the README, the code
(`metadata.version`), the deck, the handbook and the video. We could not confirm
that 1.8.0 exists. The most recent third-party version history we found lists
**1.6.0 (August 2025)** as released with 1.7.0 in development, and that page may
itself be out of date.

**Before submitting, open [schema.ocsf.io](https://schema.ocsf.io/), read the
version selector, and either confirm 1.8.0 or change the string.** It appears in
exactly these places:

```
strata/mapping/ocsf.py          OCSF_VERSION = "1.8.0"   ← the one that matters;
                                 it is written into every event's metadata
strata/core/model.py            docstring
strata/app/ui/console.html      3 captions
README.md                       3 mentions
docs/HANDBOOK.md                2 mentions
docs/GRAMMAR-REFERENCE.md       generated — re-run tools/gen_reference.py
tools/gen_reference.py          the header it generates
deck/build_deck.js              5 mentions — re-run `node build_deck.js` after
deck/video/…                    rebuild the reel and re-render if changed
```

`OCSF_VERSION` in `strata/mapping/ocsf.py` is the only one with runtime effect —
it is stamped into `metadata.version` on every normalized event. The rest are
prose. Change that constant first, then `grep -rn "1\.8" .` to catch the others.

A dated claim ("at version 1.8.0 as of March 2026") has already been removed
from the `mapping/ocsf.py` docstring, because it was a specific assertion we
could not stand behind.

Why this is not fatal to the design: the objects and fields STRATA maps into —
`class_uid`, `category_uid`, `src_endpoint`, `dst_endpoint`, `metadata.product`,
`disposition_id`, and crucially `unmapped` — have been stable across the whole
1.x line. The mapping is correct for OCSF 1.x; only the version *label* is in
question. But a judge who knows OCSF will spot a wrong version number, and
"we said 1.8 and it's actually 1.6" is a needless wound.

---

## Standards and specifications

| | Used for | Status |
|---|---|---|
| **OCSF — Open Cybersecurity Schema Framework**, Linux Foundation. [ocsf.io](https://ocsf.io/) · [schema.ocsf.io](https://schema.ocsf.io/) · [github.com/ocsf/ocsf-schema](https://github.com/ocsf/ocsf-schema) | The target taxonomy. Event classes, categories, `disposition_id` enums, and the base event class's `unmapped` object that justifies preserving residue. | [VERIFIED] project + URLs; [NEEDS CHECK] version |
| **RFC 3164** — The BSD syslog Protocol (2001). [datatracker.ietf.org/doc/html/rfc3164](https://datatracker.ietf.org/doc/html/rfc3164) | The legacy syslog header parser, and the reason `timeparse.py` needs an explicit year rule — RFC 3164 timestamps carry no year and no timezone. | [DESIGN BASIS] |
| **RFC 5424** — The Syslog Protocol (2009). [datatracker.ietf.org/doc/html/rfc5424](https://datatracker.ietf.org/doc/html/rfc5424) | The modern syslog header parser, structured data, and the `<PRI>` handling in `shapes.py`. | [DESIGN BASIS] |
| **RFC 6587** — Transmission of Syslog Messages over TCP. [datatracker.ietf.org/doc/html/rfc6587](https://datatracker.ietf.org/doc/html/rfc6587) | Octet-counted vs newline-delimited framing on the TCP listener. | [DESIGN BASIS] |
| **RFC 6962** — Certificate Transparency (2013). [datatracker.ietf.org/doc/html/rfc6962](https://datatracker.ietf.org/doc/html/rfc6962) | **Load-bearing.** §2.1 defines the leaf/node hash domain separation (`0x00` / `0x01` prefixes) that `store/merkle.py` implements. Without it an internal node can be presented as a leaf and an inclusion proof forged for data never stored. | [DESIGN BASIS] |
| **FIPS 180-4** — Secure Hash Standard, NIST. | SHA-256, used for record content addresses and Merkle hashing. Via Python's `hashlib`. | [DESIGN BASIS] |
| **RFC 4180** — Common Format for Comma-Separated Values. | Quoted-field splitting in the `columns` extractor. | [DESIGN BASIS] |
| **IANA Time Zone Database** | Cited as the reason STRATA *refuses* named zones: a stored timestamp must not change meaning when tzdata updates. Deliberately **not** a dependency. | [DESIGN BASIS] |

---

## Cryptography and data structures

| | Used for | Status |
|---|---|---|
| **Merkle, R.C.** — *A Digital Signature Based on a Conventional Encryption Function*, CRYPTO '87, LNCS 293. | The original Merkle tree construction behind `store/merkle.py` and its log₂(n) inclusion proofs. | [DESIGN BASIS] |
| **CVE-2012-2459** — Bitcoin block Merkle root collision via duplicated transaction hashes. | The precedent for STRATA's odd-node **promotion** rather than duplication. Padding by duplicating the last leaf lets two distinct leaf sets produce the same root. Tested in `tests/test_strata.py`. | [DESIGN BASIS] |
| **Content-addressable storage** — as in Git's object model and IPFS. | `record_id = sha256(payload)`, which yields deduplication, idempotent replay and per-record tamper evidence with no ID coordination. | [DESIGN BASIS] |
| **Event sourcing / materialized views** — Martin Fowler; Pat Helland, *Immutability Changes Everything* (CIDR 2015). | The core inversion: the ledger is the event log, normalized OCSF events are a derived, recomputable view. This is what makes `rewind` possible. | [DESIGN BASIS] |

---

## Log parsing research

| | Used for | Status |
|---|---|---|
| **He, P., Zhu, J., Zheng, Z., Lyu, M.R.** — *Drain: An Online Log Parsing Approach with Fixed Depth Tree*, IEEE ICWS 2017. | The template-mining idea in `learn/induction.py` — across many instances of one message type, constant tokens are the template and varying tokens are the variables. STRATA's implementation is simplified and clusters by structural family first. | [DESIGN BASIS] |
| **Zhu, J. et al.** — *Tools and Benchmarks for Automated Log Parsing*, ICSE-SEIP 2019 (the LogPai / logparser benchmark). | Context for why template mining alone is insufficient on positional CSV, which motivated the value-and-adjacency inference in `learn/forge.py`. | [DESIGN BASIS] |

**Note on originality:** the value-kind classifier (`kind_of`) and the adjacency
rule — *"a small integer immediately after an IPv4 field is that endpoint's
port"* — are our own. They are not from DRAIN, which mines templates and does
not attempt field semantics.

---

## Vendor log format references

The synthetic corpus in `strata/dev/synth.py` reproduces the **structure** of
these formats. Every generator was written from working knowledge of published
vendor field references, **not** by parsing captured traffic and **not** by
copying any vendor document during this build.

Say this plainly if asked: *the samples are structurally faithful and
synthetic.* It is already in the README's limitations and on the deck.

| Vendor / format | Grammar | Publisher documentation |
|---|---|---|
| Palo Alto Networks PAN-OS traffic log | `panos.traffic` | PAN-OS Administrator's Guide — Traffic Log Fields |
| Fortinet FortiGate traffic log | `fortigate.traffic` | FortiOS Log Message Reference |
| Check Point firewall log | `checkpoint.firewall` | Check Point Log Fields Guide |
| Cisco ASA syslog | `cisco.asa` | Cisco ASA Series Syslog Messages (incl. `%ASA-6-106023`) |
| Suricata EVE JSON | `suricata.alert` | Suricata User Guide — EVE JSON Output |
| Zeek `conn.log` | `zeek.conn` | Zeek Documentation — Log Files |
| Squid access log | `squid.access` | Squid Configuration Reference — `logformat` |
| pfSense `filterlog` | `pfsense.filterlog` | pfSense Documentation — Filter Log Format |
| ArcSight **CEF** | `generic.cef` | Implementing ArcSight Common Event Format (CEF) |
| IBM QRadar **LEEF** | `generic.leef` | QRadar Log Event Extended Format (LEEF) Guide |

All [DESIGN BASIS]. Field mappings are documented in
[`GRAMMAR-REFERENCE.md`](GRAMMAR-REFERENCE.md), generated from the grammars
themselves.

**The Cisco ASA direction quirk** — that in `%ASA-6-106023` the interface named
first is the *destination* on an outbound connection — is the single most
specific vendor behaviour STRATA depends on. It caused a real bug (see
`test_asa_endpoint_order_is_not_positional`). **Re-read the Cisco message
reference for 106023 before you present it**, because it is the story you will
most want to tell and the one most likely to be challenged.

---

## Software dependencies [VERIFIED]

Exactly as pinned in `requirements.txt`. All permissively licensed, all
installable from a local wheelhouse, none of them make network calls.

### Runtime

| Package | Constraint | Used for | Licence |
|---|---|---|---|
| **pydantic** | `>=2.9,<3` | Grammar-file and API-body validation at trust boundaries | MIT |
| **PyYAML** | `>=6.0` | Reading grammar files | MIT |
| **zstandard** | `>=0.22` | Per-frame compression in the ledger | BSD-3-Clause |
| **pyarrow** | `>=17.0` | Parquet output for the analytics lake | Apache-2.0 |
| **fastapi** | `>=0.115` | REST API and console backend | MIT |
| **uvicorn** | `>=0.30` | ASGI server | BSD-3-Clause |
| **duckdb** | `>=1.1` | SQL over the Parquet lake (`strata query`) | MIT |

### Standard library (no dependency added)

`hashlib` (SHA-256) · `sqlite3` (the rebuildable ledger index) · `struct`
(binary envelope packing) · `fcntl` / `msvcrt` (single-writer file lock) ·
`socketserver`, `socket` (syslog listeners) · `dataclasses`, `re`, `json`.

### Development

| Package | Constraint | Used for |
|---|---|---|
| **pytest** | `>=8.0` | The 91-test suite |

**Python 3.10+** required; developed and tested on **3.11.15**.

---

## Build and presentation tooling [VERIFIED]

Not required to run STRATA — only to rebuild the deck or the video.

| Tool | Used for | Licence |
|---|---|---|
| **pptxgenjs** | Generates `deck/STRATA-SIH-Deck.pptx` from `deck/build_deck.js` | MIT |
| **Playwright** (Chromium) | Console screenshots (`deck/video/capture.py`) and recording the video reel (`deck/video/render.js`) | Apache-2.0 |
| **FFmpeg** (libx264) | Encoding `STRATA-demo.mp4` and correcting the recorder's timestamps | LGPL/GPL |
| **Docker / Docker Compose** | Containerised deployment (requirement k) | Apache-2.0 |
| **GitHub Actions** | CI: tests, the air-gap check, docs freshness | — |

No web fonts, no CDN scripts, no external stylesheets anywhere in the console or
the video reel. That is enforced by a CI job, not just intended.

---

## AI assistance disclosure

**This project was built with substantial assistance from Claude (Anthropic).**

The git history records it: every commit carries a `Co-Authored-By: Claude`
trailer, so the record is honest and auditable rather than something to be
discovered.

**Check your competition's rules on AI assistance and declare it in whatever
form they require.** Many hackathons now permit AI tooling and ask only that you
disclose it; some require a statement in the README. What you should not do is
leave it implicit — the commit trailers are already public in the repository,
so a reviewer will find them either way, and finding them beats being told.

What you should be able to do regardless, and what actually gets marked: explain
every design decision, defend the architecture in a viva, and modify the code.
[`docs/HANDBOOK.md`](HANDBOOK.md) exists for exactly that, and Part 14 is the
list of questions a panel is most likely to ask.

---

## Sources consulted while compiling this list

- [Open Cybersecurity Schema Framework](https://ocsf.io/) — project site
- [OCSF Schema (GitHub)](https://github.com/ocsf/ocsf-schema) — schema repository
- [OCSF joins the Linux Foundation](https://www.linuxfoundation.org/press/open-cybersecurity-schema-framework-ocsf-joins-the-linux-foundation-to-optimize-critical-security-data) — governance
- [OCSF Version History](https://hub.metronlabs.com/ocsf-version-history-a-guide-to-enhancements-and-security-benefits/) — third-party version history; the basis for the [NEEDS CHECK] flag above, and possibly stale itself
- [Amazon Security Lake — OCSF](https://docs.aws.amazon.com/security-lake/latest/userguide/open-cybersecurity-schema-framework.html) — an adopter's description of the schema
