# The video, with no editing

`visuals.html` is the entire visual track of the submission video — 23 animated
beats with the real console screenshots inside it. **It starts playing the
moment you open it and runs to the end on its own.** Nothing to press, nothing
that waits for you. You open it, read the script aloud, and screen-record.

**There is nothing to cut together afterwards.** That is the whole point.

**It advances one phrase at a time, not one slide at a time.** Each beat is held
for exactly as long as its line takes to say, so the picture can never drift ten
seconds away from the words. And the pace is yours to set: `[` slows the whole
reel down, `]` speeds it up, live, while it runs.

---

## Do this

**1. Open it.** Double-click `visuals.html`. Any browser. No server, no
internet — it is one self-contained file.

**2. Start your screen recorder.** Record the whole screen.

- Windows — `Win + G` (Xbox Game Bar), or OBS
- macOS — `Cmd + Shift + 5`, "Record Entire Screen"
- Anything — OBS Studio, free

**3. Press `F` for fullscreen — this also restarts the reel from the top,** so
you get a clean opening rather than joining part-way through. It is the only key
in the whole process, and only because browsers refuse to go fullscreen without
a real keypress. If you're happy recording the browser window as-is, skip it and
just reload the page instead.

**4. Read the script.** From [`../VIDEO-SCRIPT.md`](../VIDEO-SCRIPT.md), on
your phone or a printout. Start speaking when the four witnesses appear — the
opening card is deliberately silent.

**5. Stop recording** three seconds after the final card.

Done. Trim the dead air off each end in whatever app you already have, and
that is the video.

---

## Keys

You don't need any of these. The reel plays itself. They're here for rehearsal.

| Key | Does |
|---|---|
| `F` | fullscreen — **and restarts from the top** |
| `R` | restart and play again |
| `A` | pause / resume the automatic advance |
| `[` / `]` | **slower / faster** — shifts your speaking rate by 5 wpm. Live. |
| `Space` / `→` | next phrase by hand |
| `←` | back |
| `N` | **cue cards** — the line you're saying, the next one, a clock and your current wpm |
| `H` | show/hide the key hints |
| `B` | show/hide the progress bar |

**Nothing is shown over the reel by default** — no key hints, no progress bar,
no cue cards. They only appear if you turn them on, so a straight recording is
always clean.

**`N` is for rehearsal, not for recording.** The cue strip is part of the page,
so it *will* appear in your recording if you leave it on. Press `N` again before
you hit record. Same for `H` and `B`.

---

## If you drift off the timings

Don't chase it mid-take — that is what makes a video look out of sync. Stop,
change the reel's pace, start over. A retake costs two minutes.

Consistently *ahead* of the reel means you're reading fast: press `[` two or
three times to slow the whole thing down. Consistently behind, press `]`. Then
press `R` and go again.

Best done before you ever hit record: read the clean read aloud once against a
stopwatch. Under 1:50 → press `]`. Over 2:05 → press `[`.

---

## Recording quality

- **Record at 1080p.** Maximise the browser window first.
- **Close everything else** — notifications, other tabs, the bookmarks bar.
  A Slack popup mid-take means a retake.
- **Record the voiceover in one pass with the screen**, if your tool allows it.
  Separate audio means syncing, and syncing is editing.
- **Somewhere quiet, phone on silent.** Audio is what makes a hackathon video
  feel amateur, far more than visuals.

---

## Rebuilding the page

Only needed if the console UI changes or you want different screenshots.

```bash
python3 strata.py console            # terminal 1
python3 deck/video/capture.py        # terminal 2 — writes shots/
python3 deck/video/build_visuals.py
```

`capture.py` needs Playwright (`pip install playwright && playwright install
chromium`). If you'd rather not install it, take the three screenshots by hand
and save them as `shots/overview.png`, `shots/inspector.png`,
`shots/integrity.png` — `build_visuals.py` doesn't care how they got there.

---

## Files

| | |
|---|---|
| `visuals.html` | **the one you open.** Self-contained, ~0.8 MB |
| `visuals.template.html` | source, before screenshots are inlined |
| `build_visuals.py` | inlines the screenshots into the template |
| `capture.py` | re-captures the three console screenshots |
| `shots/` | the screenshots currently baked in |

---

## What's on each beat

| # | Beat | Secs |
|---|---|---|
| 1 | SIH title card — **silent, don't speak yet** | 0:00 |
| 2–4 | Four witnesses → summary forms → originals fall away → "not recorded" | 0:03 |
| 5 | "It's gone." | 0:22 |
| 6–8 | 1,000,000,000 counts up · four real log lines · the same IP ignites in all four | 0:24 |
| 9 | The originals blur away | 0:41 |
| 10 | STRATA wordmark builds | 0:48 |
| 11–12 | Console overview | 0:53 |
| 13–14 | Raw bytes, with curves drawing down to the OCSF fields they became | 1:02 |
| 15 | 100.0000% counts up over the integrity page | 1:14 |
| 16–18 | `strata rewind` — counters run to 20,000 | 1:22 |
| 19–21 | The unknown device, then `strata forge` typing itself out | 1:34 |
| 22 | The three numbers | 1:44 |
| 23 | End card | 1:52 |

Total 1:57 at 145 wpm. Every duration is computed from its own line's word
count, so changing your rate with `[` and `]` rescales all of them together.
