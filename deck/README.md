# Pitch deck

`STRATA-SIH-Deck.pptx` — 15 slides, speaker notes on every one.
`STRATA-SIH-Deck.pdf` — the same deck as a handout / projector fallback.

Rebuild after editing `build_deck.js`:

```bash
node build_deck.js
```

`pptxgenjs` is the only dependency (`npm install pptxgenjs`). Nothing in the
deck is fetched at open time — no linked images, no remote fonts.

## Running order

| # | Slide | Time | Say |
|---|---|---|---|
| 1 | STRATA | 0:20 | Open cold, then pull the network cable |
| 2 | One fact, four vocabularies | 0:40 | Read two log lines aloud |
| 3 | The discard is the problem | 0:40 | Field 38, six months later |
| 4 | Architecture | 0:50 | Trace one line with your finger |
| 5 | Shape-first triage | 0:30 | The only optimisation that improves with scale |
| 6 | Throughput | 0:30 | Label the 8-core figure a projection |
| 7 | **Rewind** | 0:50 | The strongest slide — offer to run it live |
| 8 | Merkle proofs | 0:50 | Offer to break it live |
| 9 | Provenance inspector | 0:40 | Click a row instead of describing it |
| 10 | The Forge | 0:50 | Do this live; it is the crowd-pleaser |
| 11 | Unknown beats wrong | 0:40 | Tell the ASA story honestly |
| 12 | Requirement traceability | 0:15 | Do not read it aloud |
| 13 | Measured | 0:30 | Every number has a command behind it |
| 14 | Deployment + limits | 0:30 | Name your limits before the panel does |
| 15 | Close | 0:15 | End on the command, not a thank-you |

≈8 minutes with pauses. The live demo runs alongside slides 7–10; the full
script is in [../docs/DEMO-SCRIPT.md](../docs/DEMO-SCRIPT.md).

Fonts are Arial / Calibri / Courier New only, so the deck renders identically
on any machine with Office or LibreOffice — no font substitution surprises on
the venue's projector laptop.
