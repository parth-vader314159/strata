# STRATA — video script

For the SIH "Demo Video of the Idea" submission. Written so that someone with
no technical background understands the problem, the idea, and why it matters —
while a judge who *does* know the field still hears something they haven't heard
before.

**Runs 1:57 at a normal speaking pace. 239 words.**

> **No editing required.** [`video/visuals.html`](video/) is the entire visual
> track, and it plays itself the moment you open it — nothing to press. Read
> this aloud over it and screen-record once.
> Setup: [`video/README.md`](video/README.md).

---

## How the timing works — read this once

The reel advances **one phrase at a time**, and each phrase is held for exactly
as long as it takes to say it — its own word count at your speaking rate. It is
not a slideshow on a fixed clock, so a visual can never be ten seconds adrift
from the words that go with it.

Your rate is adjustable **while it runs**: `[` slows everything down, `]` speeds
it up, in 5-word-per-minute steps. Default is 145.

**So don't try to match the reel. Make the reel match you.** Rehearse once at
145, and if you were rushing to keep up, press `[` three times and go again.
That single habit is what makes it feel seamless.

---

## The one rule for this video

**Do not explain the architecture.** You have two minutes. A layman cannot
absorb a pipeline diagram, and a judge does not need one — that's what the deck
is for. The video has exactly one job: make the audience *feel* the problem in
the first twenty seconds, then show them you solved it.

---

## The script

Timings are where each line **starts** if you read at 145 wpm. The first three
seconds are the silent title card — **do not speak over it.** Start on "Four
people".

| Starts | Say |
|---|---|
| **0:03** | Four people see the same accident. Each of them describes it differently. |
| **0:09** | So a translator writes one short summary of each — and throws the original statements away. |
| **0:16** | Months later, an investigator needs one detail that was never in the summary. |
| **0:22** | It's gone. |
| **0:24** | This is not a story. It is what happens inside every large network on earth, a billion times a day. |
| **0:32** | Every firewall, every router, every security device writes down what it saw. |
| **0:38** | Each one in its own language. |
| **0:41** | Software translates them so a security team can search them. And the originals are deleted. |
| **0:48** | We built the translator that never throws anything away. |
| **0:53** | STRATA reads any device's format and rewrites it into one common language, |
| **0:58** | so for the first time, everything can be searched together. |
| **1:02** | But it keeps every original too. Every byte, exactly as it arrived. |
| **1:08** | Every value you see here is linked to the exact characters it came from. |
| **1:14** | And it can prove nothing was altered — one record at a time, without revealing any other. |
| **1:22** | So when we get a translation wrong, we fix it, |
| **1:26** | and re-translate the entire past. |
| **1:29** | No other tool can. No other tool kept the originals. |
| **1:34** | And when a device nobody has ever seen starts sending logs, |
| **1:39** | STRATA studies it |
| **1:40** | and writes its own translator. Milliseconds, not engineer-days. |
| **1:44** | Eleven thousand events a second. More than a billion a day. On one ordinary machine, completely offline. |
| **1:52** | STRATA. Nothing is translated away. |

Hold the end card three seconds, then stop recording.

---

## Clean read

Record from this — the table is for reference, not for reading off. `//` marks a
pause. **Take the pauses.** They carry more weight than the words, and the reel
has already budgeted time for them.

> *(silent — title card. Breathe. Start on the witnesses.)*
>
> Four people see the same accident. Each of them describes it differently. //
>
> So a translator writes one short summary of each — and throws the original
> statements away. //
>
> Months later, an investigator needs one detail that was never in the summary.
> //
>
> **It's gone.** //
>
> This is not a story. It is what happens inside every large network on earth, a
> billion times a day. //
>
> Every firewall, every router, every security device writes down what it saw.
> Each one in its own language. //
>
> Software translates them so a security team can search them. And the originals
> are deleted. //
>
> We built the translator that never throws anything away. //
>
> STRATA reads any device's format and rewrites it into one common language, so
> for the first time, everything can be searched together. //
>
> But it keeps every original too. Every byte, exactly as it arrived. Every value
> you see here is linked to the exact characters it came from. //
>
> And it can prove nothing was altered — one record at a time, without revealing
> any other. //
>
> So when we get a translation wrong, we fix it, and re-translate the entire
> past. // No other tool can. No other tool kept the originals. //
>
> And when a device nobody has ever seen starts sending logs, STRATA studies it
> and writes its own translator. Milliseconds, not engineer-days. //
>
> Eleven thousand events a second. More than a billion a day. On one ordinary
> machine, completely offline. //
>
> **STRATA. Nothing is translated away.**

---

## What you'll see, phrase by phrase

You don't have to build any of this — the reel does it. It's here so you know
what's coming and can time your emphasis to it.

| When you say | The screen does |
|---|---|
| "Four people see the same accident" | Four witness statements land one at a time, in four languages |
| "throws the original statements away" | The four cards grey out, blur and fall; the summary settles into centre |
| "one detail that was never in the summary" | The summary shakes and a red line appears: *not recorded* |
| "It's gone." | Hard cut to black |
| "a billion times a day" | **1,000,000,000** counts up from zero |
| "writes down what it saw" | Four real log lines slide in |
| "Each one in its own language" | The same IP address ignites in all four — in a different position each time |
| "the originals are deleted" | The lines desaturate and blur away |
| "never throws anything away" | The STRATA wordmark builds letter by letter out of blur |
| "one common language" | The live console |
| "linked to the exact characters" | **The best shot in the video** — curves draw from the raw bytes down to the OCSF fields they became, one after another |
| "prove nothing was altered" | **100.0000%** counts up over the integrity page |
| "re-translate the entire past" | `strata rewind` — the counters run to 20,000 |
| "writes its own translator" | The forge output types itself out, line by line |
| "Eleven thousand events a second" | The number counts up |
| "Nothing is translated away." | End card |

---

## The 60-second cut

If the limit turns out to be one minute, use this — don't speed-read the long
one. ~125 words, about 52 seconds plus pauses. Tap `Space` to advance manually;
the phrase timings won't match, so turn autoplay off for this version.

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

**Voice.** Slower than feels natural. Record your voice and the screen together
in one pass — separate audio has to be synced afterwards, and syncing is
editing.

**Find your rate first.** Read the clean read aloud once with a stopwatch. Under
1:50 means you're fast — press `]`. Over 2:05 means press `[`. Do this *before*
you record and the whole problem disappears.

**Screen capture.** 1080p minimum, browser maximised. Close notifications, other
tabs and the bookmarks bar — a popup mid-take means a retake.

**Rehearse twice with cue cards on** (`N` shows the line you should be saying,
the next one, a clock and your current wpm). Then press `N` again to turn them
off. **They are part of the page and will appear in your recording if you leave
them on.**

**Do not say:** OCSF, Merkle tree, content-addressed, normalization, grammar,
triage, schema. Every one of those is in the deck, where it belongs.

**Do say the numbers out loud.** "Eleven thousand a second" and "a hundred
percent" land; a number that only appears on screen doesn't.

---

## Why the script is built this way

Worth knowing if you want to rewrite it.

**The analogy does all the work.** Witnesses → devices, statements → logs,
translator → parser, summary → normalized event, thrown-away originals → the
discard, investigator → analyst. One-to-one, so every later sentence lands
without further explanation.

**The problem gets 40% of the runtime.** That feels wrong and is correct. Most
hackathon videos invert this and spend ninety seconds on features nobody has
been given a reason to want.

**Rewind is the emotional peak, not the throughput number.** "We can fix the
past" is a claim a non-technical person can evaluate and be impressed by.
"11,440 events per second" is one they have to take on trust.

**The last line answers the first.** The video opens with something being thrown
away and closes with "nothing is translated away." That symmetry is why the
ending feels like an ending.
