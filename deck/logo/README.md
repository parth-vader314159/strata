# Logo animation

`STRATA-logo.mp4` — 1920×1080, 9.6s, silent. Drop it on the front of the demo
video, a deck, or a landing page.

`logo.html` — the source. Open it and it plays on loop; nothing to press.

---

## What it is

The mark is the product's own argument in motion, not decoration. Six beats:

| | | |
|---|---|---|
| **1** | **Chaos** | Fragments of a dozen real vendor log formats — PAN-OS, FortiGate, CEF, LEEF, Zeek, ASA, Squid, pfSense — scattered, rotated, drifting. Individually readable, collectively useless. |
| **2** | **Strata** | They settle into ordered horizontal layers, bottom row first. One vocabulary. Nothing thrown away, just laid down. |
| **3** | **Compact** | Each layer contracts the way sediment does — into a single leaf node. |
| **4** | **Fold** | The leaves hash pairwise upward, 8 → 4 → 2 → 1. A Merkle tree building itself, with the content address each merge produces flickering beside it. |
| **5** | **Root** | The single remaining node *is* the mark. One ring, outward, once. |
| **6** | **Lockup** | Wordmark out of blur, hairline, ULPF, then the line. |

Every element is drawn to one canvas at a fixed internal 1920×1080 and scaled to
fit, so it renders identically at any window size.

## Keys

None needed. For tinkering:

| Key | Does |
|---|---|
| `R` | replay from the top |
| `L` | stop looping (plays once and holds) |
| `T` | light / dark — the paper palette works too |
| `H` | show the key hints |

Nothing is drawn over the animation by default, so a screen recording is clean.
`prefers-reduced-motion` is respected: the final lockup renders statically.

## Re-rendering

```bash
node deck/logo/render.js
```

About a minute. Needs `playwright` and `ffmpeg`. It applies the same timestamp
correction as the demo-video renderer — Chromium's screencast encoder falls
behind without a GPU and writes stretched timestamps, so the real elapsed time
is measured and the presentation timestamps rescaled by that ratio.

## Using it

- **In front of the demo video** — concatenate, or drop both on a timeline.
- **As a loop** — open `logo.html` fullscreen on a laptop at a stall.
- **Light background** — press `T`, then re-render.
- **Shorter** — the beats are a single `T` object at the top of the script; every
  duration is one number.

The palette is the product's: paper `#FAFAF9`, ink `#14151A`, one signal orange
`#D9500C` (brightened to `#FF7A33` on dark). No second accent colour anywhere,
which is what keeps the orange meaning something.
