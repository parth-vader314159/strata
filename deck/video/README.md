# The video, with no editing

`visuals.html` is the entire visual track of the submission video — 23 animated
beats with the real console screenshots inside it. You open it, press two keys,
read the script aloud, and screen-record the result.

**There is nothing to cut together afterwards.** That is the whole point.

**It advances one phrase at a time, not one slide at a time.** Each beat is held
for exactly as long as its line takes to say, so the picture can never drift ten
seconds away from the words. And the pace is yours to set: `[` slows the whole
reel down, `]` speeds it up, live, while it runs.

---

## Do this

**1. Open it.** Double-click `visuals.html`. Any browser. No server, no
internet — it is one self-contained file.

**2. Press `F`** for fullscreen. Press **`H`** to dismiss the key hints.

**3. Start your screen recorder.** Record the whole screen.

- Windows — `Win + G` (Xbox Game Bar), or OBS
- macOS — `Cmd + Shift + 5`, "Record Entire Screen"
- Anything — OBS Studio, free

**4. Press `A`.** The slides now advance themselves, on the script's timings.
Your hands are free.

**5. Read the script.** From [`../VIDEO-SCRIPT.md`](../VIDEO-SCRIPT.md), on
your phone or a printout. Start speaking when the four witnesses appear — the
opening card is deliberately silent.

**Set your pace first.** Read the clean read aloud once against a stopwatch. If
you finish under 1:50 you're fast — press `]` a few times. Over 2:05, press `[`.
Doing this before you record is what makes the take feel locked.

**6. Stop recording** three seconds after the final card.

Done. Trim the dead air off each end in whatever app you already have, and
that is the video.

---

## Keys

| Key | Does |
|---|---|
| `A` | **autoplay** — advances on the script's own phrase timings. The one you want. |
| `[` / `]` | **slower / faster** — shifts your speaking rate by 5 wpm. Live. |
| `Space` / `→` | next phrase by hand |
| `←` | back |
| `N` | **cue cards** — the line you're saying, the next one, a clock and your current wpm |
| `R` | restart from the beginning |
| `F` | fullscreen |
| `H` | show/hide the key hints |
| `B` | show/hide the progress bar |

**`N` is for rehearsal, not for recording.** The cue strip is part of the page,
so it *will* appear in your recording if you leave it on. Rehearse with it,
press `N` again before you hit record. Same for `H` and `B`.

Autoplay and the cue cards are independent — you can rehearse with cue cards
on and autoplay off, tapping `Space` when you're ready, until the timings feel
right.

---

## If you drift off the timings

Tap `Space` to jump forward, or `←` to go back — autoplay picks up from wherever
you land. You do not need to restart.

If you find yourself consistently *ahead* of the reel, you're reading fast: stop,
press `[` two or three times, and go again. Consistently behind, press `]`.
Chasing the reel mid-take is what makes a video look out of sync; changing its
rate to match yours is the fix.

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
python3 deck/video/build_visuals.py --team "Your Team" --college "Your College"
```

`capture.py` needs Playwright (`pip install playwright && playwright install
chromium`). If you'd rather not install it, take the three screenshots by hand
and save them as `shots/overview.png`, `shots/inspector.png`,
`shots/integrity.png` — `build_visuals.py` doesn't care how they got there.

`--team` and `--college` fill in the end card. Run it once with your real team
name before you record.

---

## Files

| | |
|---|---|
| `visuals.html` | **the one you open.** Self-contained, ~1.3 MB |
| `visuals.template.html` | source, before screenshots are inlined |
| `build_visuals.py` | inlines the screenshots, fills the end card |
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
