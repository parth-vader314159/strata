# STRATA — video script

For the SIH "Demo Video of the Idea" submission. Written so that someone with
no technical background understands the problem, the idea, and why it matters —
while a judge who *does* know the field still hears something they haven't heard
before.

**Main cut: 2:00.** A 60-second cut is at the bottom if the rules turn out to be
tighter.

---

## The one rule for this video

**Do not explain the architecture.** You have two minutes. A layman cannot
absorb a pipeline diagram, and a judge does not need one — that's what the deck
is for. The video has exactly one job: make the audience *feel* the problem in
the first twenty seconds, then show them you solved it.

Everything below is built around that.

---

## The 2-minute script

| Time | Voiceover | On screen |
|---|---|---|
| **0:00–0:20** | Imagine four people witness the same incident. Each one speaks a different language. A translator listens to all four, writes one short summary of each — and then throws the original statements away. *(beat)* Months later, an investigator needs one small detail. It wasn't in the summary. It's gone. | Simple animation: four speech bubbles in four scripts → one small summary card → the four originals drop into a bin. Keep it plain; no stock footage. |
| **0:20–0:42** | This is not a story. It's what happens inside every large computer network, a billion times a day. Every firewall, every router, every security device writes down what it saw — each in its own format. Software translates them so a security team can search them. And the originals are deleted. | Swap the four people for four device icons. Show four **real** log lines — Palo Alto, FortiGate, Suricata, Cisco ASA — all describing the same blocked connection. Highlight the same IP address in each, in a different position. Then grey the lines out and fade them. |
| **0:42–0:52** | So when a new kind of attack appears, and an investigator needs a detail nobody thought to keep — it's already gone. *(beat)* We built the translator that never throws anything away. | The four lines vanish, leaving a black screen. Then the STRATA title card. |
| **0:52–1:10** | STRATA reads any security device's format and rewrites it into one common language — so for the first time, everything can be searched together. | Console overview. Press *Generate traffic*, let the pipeline fill. Show the vendor list on the left. |
| **1:10–1:26** | But it keeps every original too. Every byte, exactly as it arrived. And it can prove — mathematically — that a single record has not been altered, without revealing anything about any other record. | **The money shot.** The provenance inspector: the raw log line with every extracted value highlighted, hover to show each one linked to the field it became. Then cut to `strata audit` printing `FIDELITY 100.000000%`. |
| **1:26–1:40** | Which means if we ever translate something wrongly, we can fix it — and re-translate the entire past. No other tool can do that, because no other tool kept the originals. | `strata rewind` output: `20,000 replayed · 20,000 re-derived · 0 quarantined`. Let it sit on screen for a full second. |
| **1:40–1:52** | And when a device nobody has ever seen starts sending logs, STRATA studies it and writes its own translator — in milliseconds, instead of the days an engineer would take. | Forge tab: quarantined unknown lines → *Analyse & propose* → the generated YAML → *Publish*. Speed this up 2× if it runs long. |
| **1:52–2:00** | Over eleven thousand events a second. More than a billion a day. On one ordinary machine, completely offline. *(beat)* STRATA. Nothing is translated away. | Bench number, then an "AIR-GAPPED" badge or a hand unplugging an ethernet cable. End on the STRATA card. |

**Word count: ~300.** That is about 2:05 at a natural pace. If you run long, the
first thing to cut is the second sentence of the 1:26 block.

---

## Clean read

Record from this, not the table. `//` marks a pause — take it, they carry more
weight than the words.

> Imagine four people witness the same incident. Each one speaks a different
> language. A translator listens to all four, writes one short summary of each —
> and then throws the original statements away. //
>
> Months later, an investigator needs one small detail. It wasn't in the
> summary. It's gone. //
>
> This is not a story. It's what happens inside every large computer network, a
> billion times a day.
>
> Every firewall, every router, every security device writes down what it saw —
> each in its own format. Software translates them so a security team can search
> them. And the originals are deleted. //
>
> So when a new kind of attack appears, and an investigator needs a detail
> nobody thought to keep — it's already gone. //
>
> We built the translator that never throws anything away. //
>
> STRATA reads any security device's format and rewrites it into one common
> language — so for the first time, everything can be searched together.
>
> But it keeps every original too. Every byte, exactly as it arrived. And it can
> prove — mathematically — that a single record has not been altered, without
> revealing anything about any other record. //
>
> Which means if we ever translate something wrongly, we can fix it — and
> re-translate the entire past. No other tool can do that, because no other tool
> kept the originals. //
>
> And when a device nobody has ever seen starts sending logs, STRATA studies it
> and writes its own translator — in milliseconds, instead of the days an
> engineer would take. //
>
> Over eleven thousand events a second. More than a billion a day. On one
> ordinary machine, completely offline. //
>
> STRATA. Nothing is translated away.

---

## The 60-second cut

If the limit turns out to be one minute, cut to this — don't speed-read the long
one. ~125 words, which is about 52 seconds of speech plus room for the pauses.

> Imagine four witnesses to one incident, each speaking a different language. A
> translator writes a short summary of each — then throws the originals away.
> Months later an investigator needs one detail. It's gone. //
>
> That is what happens in every large network, a billion times a day. Security
> devices each write in their own format, software translates them, and the
> originals are deleted. //
>
> STRATA is the translator that never throws anything away. It rewrites every
> device's logs into one common language, and keeps every original byte — with
> proof that nothing was altered. //
>
> So if we get a translation wrong, we fix it and re-translate the entire past.
> Nobody else can. Nobody else kept the originals. //
>
> Eleven thousand events a second. Completely offline. //
>
> STRATA. Nothing is translated away.

---

## Recording notes

**Voice.** Slower than feels natural — roughly 145 words per minute. The most
common mistake in hackathon videos is rushing, and it reads as nervousness.
Record the voiceover *first*, then cut the screen recording to fit it. Doing it
the other way round means re-recording your voice to match your mouse.

**Screen capture.** 1080p minimum. Move the mouse deliberately and slowly —
fast cursor movement is unwatchable at small sizes. Zoom the browser to 125%
before recording so numbers are legible on a phone. Hide bookmarks, notifications
and any other tabs.

**Before you record, run:**

```bash
rm -rf var && rm -f grammars/meridian.gateway.yaml
python3 strata.py console
```

That resets to a clean state so the quarantine and Forge sections have something
to show. If you skip it, the unknown format is already onboarded and step four
has nothing to demonstrate.

**Rehearse the three commands** so their output is already on screen when you
need it — `audit`, `rewind --dry-run`, `bench`. Do not run them live in the
video; a five-second pause while something computes is five seconds of a
two-minute budget.

**Do not say:** OCSF, Merkle tree, content-addressed, normalization, grammar,
triage, schema. Every one of those is in the deck, where it belongs. Put OCSF
and "Merkle-sealed" on screen as small captions if you want the judge to see
you know the terms — but don't spend voiceover on them.

**Do say** the numbers out loud. "Eleven thousand a second" and "a hundred
percent" land; a number that only appears on screen doesn't.

---

## Title and end cards

**Opening card (2 seconds, before the voiceover starts):**

```
Smart India Hackathon
Universal Log Pre-processing Framework
```

**End card (hold 3 seconds):**

```
STRATA
Nothing is translated away.

Team <name> · <college>
```

Check your submission rules — some rounds require the team name and problem
statement ID on screen. If they do, put the ID on the opening card.

---

## Why the script is built this way

Worth knowing, in case you want to rewrite it.

**The analogy is doing all the work.** Witnesses → devices, statements → logs,
translator → parser, summary → normalized event, thrown-away originals → the
discard, investigator → analyst. It maps one-to-one onto the real problem, which
means every later sentence lands without further explanation.

**The problem gets 40% of the runtime.** That feels wrong and is correct. A
judge who doesn't feel the problem will not care about the solution, however
good it is. Most hackathon videos invert this ratio and spend ninety seconds on
features nobody has been given a reason to want.

**Rewind is the emotional peak, not the throughput number.** "We can fix the
past" is a claim a non-technical person can evaluate and be impressed by.
"11,440 events per second" is a claim they have to take on trust. Lead with the
one they can judge for themselves.

**The last line answers the first.** The video opens with something being thrown
away and closes with "nothing is translated away." That symmetry is why the
ending feels like an ending.
