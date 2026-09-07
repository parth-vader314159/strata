# Threat model

STRATA is not merely a data pipeline; it is the thing an attacker must defeat
to remain invisible. It sits at the network edge, accepts unauthenticated input
from anything that can reach a UDP port, and holds the organisation's forensic
evidence.

## Assets, in priority order

| # | Asset | Why it matters | Property at risk |
|---|---|---|---|
| 1 | **The ledger** | The evidence. Its value depends entirely on being provably unaltered. | Integrity |
| 2 | **SOC visibility** | If events stop flowing, the SOC is blind and does not know it. | Availability |
| 3 | **The grammar set** | Whoever controls a grammar controls what the organisation can *see*. | Integrity |
| 4 | **Raw log content** | Usernames, URLs, occasionally credentials. | Confidentiality |
| 5 | **The console** | Compromise here yields all of the above. | All three |

**Integrity outranks confidentiality here**, which is unusual and worth saying
out loud: a leaked firewall log is bad; a silently altered one destroys every
investigation that relied on it.

## Adversaries

- **External intruder covering their tracks.** The adversary that matters most.
  Wants their activity absent, unparsed, or drowned.
- **A compromised perimeter device.** Already inside the admission list. Its
  output is attacker-controlled by definition.
- **A malicious insider.** Has credentials. May edit a grammar rather than a log.
- **A curious colleague.** Not malicious; still a privacy problem.

---

## Vectors and controls

### 1. Log flooding → the SOC goes blind
Generate 100× normal volume so real events are dropped or buried. This is *the*
attack, not a side effect: availability is a security property here.

**Controls.** Per-source token bucket (`io/intake.Gate`) so one device cannot
starve the others. Refusal counts are surfaced on the console, never swallowed
— a silent drop is the difference between having the logs and believing you do.
Tested: `test_rate_limit_stops_a_flood`, `test_one_flood_does_not_starve_another_source`.

### 2. Log injection → forged events
Syslog over UDP has no authentication whatsoever. Anyone who can route a packet
to 514 can claim to be the firewall. A subtler variant: embed a newline in a
field the attacker controls so one line becomes two events.

**Controls.** Admission list. The envelope records the **observed** peer
address, which a forged line cannot control, so a forgery contradicts itself.
One input line yields exactly one event regardless of content.
Tested: `test_injected_newline_cannot_forge_a_second_event`, `test_admission_list`.

### 3. Regular-expression denial of service
Log content is attacker-influenced and reading is regex. A crafted line can
make a backtracking engine run for minutes on one input.

**Controls.** A hard line-length cap before any pattern runs, and grammar
patterns are reviewed rather than generated freely. **This is a partial
mitigation, not elimination** — Python's engine backtracks. Google RE2 would
remove the class by construction and is the documented next step; it is not a
hard dependency because it needs a compiler and we would rather ship without a
build step than claim a guarantee we only sometimes have.

### 4. Grammar poisoning → a permanent blind spot
The subtlest attack here. Change one mapping and a whole category of events
stops being recognised. Nothing alarms, because nothing broke.

**Controls.** Publishing requires the maintainer role. Every publish is written
to an append-only audit log with the actor. An invalid grammar is **rolled back
off disk** rather than left in place. And the strongest control is
architectural: because the ledger is canonical, a poisoned grammar can be
corrected and history re-derived — poisoning becomes temporary rather than
permanent.

### 5. Evidence tampering
Edit, delete, insert or reorder stored records.

**Controls.** Content addressing (`sha256(payload)` *is* the record's identity)
plus Merkle sealing per stratum and a chain of roots across strata. Any change
breaks a root, and `audit()` names the fault. Leaf/node domain separation
prevents forging a proof for data never stored.
Tested: `test_tampering_is_detected`, `test_forged_proof_is_rejected`,
`test_leaf_and_node_domain_separation`.

### 6. Malicious grammar → code execution
The Forge accepts user-supplied grammars. If the format could express arbitrary
behaviour, this would be remote code execution with a friendly name.

**Control: the format is deliberately weak.** A grammar can only name a known
primitive and supply arguments. No expressions, no imports, no shell. Unknown
keys are rejected rather than ignored; unknown step types fail schema
validation at load. *The restraint is the control.*
Tested: `test_grammar_format_cannot_express_code`, `test_unknown_keys_are_rejected_not_ignored`.

### 7. Console compromise
The highest-value surface. Auth bypass here yields everything.

**Controls.** HMAC-signed short-lived tokens compared in constant time (a naive
`==` leaks a signature one byte at a time). Roles checked **server-side per
endpoint** — a hidden button is not authorization. Secrets injected by
environment variable; no default credential exists, and dev mode announces
itself in red in the console header and in `/api/health`. Every request body is
validated. Stack traces are never returned to clients.

### 8. Privacy
Raw lines contain personal data; normalized events are far less sensitive.

**Controls.** Raw content requires the analyst role and every access is written
to the audit log — "who read this evidence" is itself a forensic question.
Merkle proofs are viewer-level because they disclose nothing about content.

---

## Residual risks we accept, and say so

- **UDP syslog cannot be authenticated.** No control fixes this; it is a
  property of the protocol. We mitigate (admission list, observed peer, rate
  limits) and recommend TLS syslog for sources that support it.
- **ReDoS is mitigated, not eliminated.** See vector 3. RE2 is the fix.
- **`sync_every` records may be lost in a hard power failure.** A deliberate,
  documented, configurable trade — see `docs/BENCHMARK.md`.
- **A maintainer can still poison a grammar.** We make it visible, audited and
  reversible rather than impossible. Signing plus a second approver is the
  documented next step.
- **No encryption at rest.** Out of scope for the time available. The frame
  format carries a version byte specifically so it can be added without
  migration.
- **OCSF validation is structural**, not a full schema validation. Validating
  every event against the complete published schema would dominate the
  pipeline; the four checks we run are the ones whose absence actually breaks a
  downstream consumer.
