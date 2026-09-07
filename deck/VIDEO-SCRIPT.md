# STRATA — video script

For the SIH "Demo Video of the Idea" submission. Written so that someone with
no technical background understands the problem, the idea, and why it matters —
while a judge who *does* know the field still hears something they haven't heard
before.

**Main cut: 2:00.** A 60-second cut is at the bottom if the rules turn out to be
tighter.

> **No editing required.** [`video/visuals.html`](video/) is the entire visual
> track, already built — open it, press `F` then `A`, read the script aloud, and
> screen-record it in one take. The "On screen" column below describes what that
> page shows you; you do not have to make any of it. See
> [`video/README.md`](video/README.md).

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
| **0:00–0:20** | Imagine four people witness the same incident. Each one speaks a different language. A translator listens to all four, writes one short summary of each — and then throws the original statements away. *(beat)* Months later, an investigator needs one small detail. It wasn't in the summary. It's gone. | Beat 2 — four witness statements appear one by one in four languages, a small summary card forms, and the four originals grey out and drop away. |
| **0:20–0:42** | This is not a story. It's what happens inside every large computer network, a billion times a day. Every firewall, every router, every security device writes down what it saw — each in its own format. Software translates them so a security team can search them. And the originals are deleted. | Beats 3–4 — the same four log lines for real (Palo Alto, FortiGate, Suricata, Cisco ASA), one IP highlighted in each to show it sits in a different place every time. Then black: "And the originals are deleted." |
| **0:42–0:52** | So when a new kind of attack appears, and an investigator needs a detail nobody thought to keep — it's already gone. *(beat)* We built the translator that never throws anything away. | Beat 5 — the STRATA card. |
| **0:52–1:10** | STRATA reads any security device's format and rewrites it into one common language — so for the first time, everything can be searched together. | Beat 6 — the console overview, live counters and pipeline filled. |
| **1:10–1:26** | But it keeps every original too. Every byte, exactly as it arrived. And it can prove — mathematically — that a single record has not been altered, without revealing anything about any other record. | Beats 7–8 — the provenance inspector (original bytes, every value highlighted and linked to its OCSF field), then the integrity page reading 100.0000%. |
| **1:26–1:40** | Which means if we ever translate something wrongly, we can fix it — and re-translate the entire past. No other tool can do that, because no other tool kept the originals. | Beat 9 — `strata rewind`: 20,000 replayed, 20,000 re-derived, 0 quarantined, 0 bytes written. |
| **1:40–1:52** | And when a device nobody has ever seen starts sending logs, STRATA studies it and writes its own translator — in milliseconds, instead of the days an engineer would take. | Beat 10 — `strata forge`: structure detected, 8 fields found, 7 mapped, published with no restart. |
| **1:52–2:00** | Over eleven thousand events a second. More than a billion a day. On one ordinary machine, completely offline. *(beat)* STRATA. Nothing is translated away. | Beats 11–12 — the three numbers, then the end card. Hold it three seconds before you stop recording. |

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
Record your voice and the screen together in one pass; separate audio has to be
synced afterwards, and syncing is editing.

**Screen capture.** 1080p minimum. Maximise the browser window. Close
notifications, other tabs and the bookmarks bar before you start — a popup
mid-take means a retake.

**You do not need to demo live.** The reel already contains the console
screenshots and the command output, so there is no alt-tabbing, nothing to wait
for, and no risk of something failing on camera. Everything is one browser tab.

**Rehearse twice with cue cards on** (`N` in the reel), then turn them off and
record. Do not leave them on — the cue strip is part of the page and will
appear in your recording.

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
