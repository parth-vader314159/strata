# The video, with no editing

`visuals.html` is the entire visual track of the submission video — twelve
beats, animated, with the real console screenshots already inside it. You open
it, press two keys, read the script aloud, and screen-record the result.

**There is nothing to cut together afterwards.** That is the whole point.

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

**6. Stop recording** three seconds after the final card.

Done. Trim the dead air off each end in whatever app you already have, and
that is the video.

---

## Keys

| Key | Does |
|---|---|
| `A` | **autoplay** — advances on the script's timings. This is the one you want. |
| `Space` / `→` | next beat by hand |
| `←` | back |
| `N` | **cue cards** — shows the line you should be saying, plus a running clock |
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

Tap `Space` to jump forward, or `←` to go back — autoplay picks up again from
wherever you land. You do not need to restart.

If you drift badly, stop and start over. A retake costs two minutes; fixing
timing in an editor costs an hour.

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
| 1 | SIH title card (silent — don't speak yet) | 5 |
| 2 | Four witnesses, four languages → one summary → originals discarded | 20 |
| 3 | The same four log lines, real, same IP highlighted in each | 16 |
| 4 | "And the originals are deleted." | 6 |
| 5 | STRATA reveal | 10 |
| 6 | Console overview | 18 |
| 7 | Provenance inspector — original bytes linked to fields | 10 |
| 8 | Integrity — 100.0000% byte-exact | 6 |
| 9 | `strata rewind` | 14 |
| 10 | `strata forge` — onboarding an unknown device | 12 |
| 11 | The numbers | 6 |
| 12 | End card | hold |

123 seconds of visuals against ~120 seconds of script, so each beat arrives a
touch before you need it rather than after.
