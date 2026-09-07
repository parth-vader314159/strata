#!/usr/bin/env python3
"""Build deck/video/visuals.html — the self-contained slide reel for the
submission video.

Screenshots are downscaled and inlined as data URIs so the finished page is a
single file that works with no server, no network and no assets folder. Open
it, press F for fullscreen, and screen-record it.

Re-capture the screenshots first if the console has changed:

    python3 strata.py console                      # in one terminal
    python3 deck/video/capture.py                  # in another

Then:

    python3 deck/video/build_visuals.py --team "Team Name" --college "College"
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "shots"
TEMPLATE = HERE / "visuals.template.html"
OUT = HERE / "visuals.html"

# placeholder -> screenshot filename
IMAGES = {
    "__IMG_OVERVIEW__": "overview.png",
    "__IMG_INSPECTOR__": "inspector.png",
    "__IMG_INTEGRITY__": "integrity.png",
}

MAX_WIDTH = 1800          # plenty for a 1080p recording; keeps the file small


def encode(path: Path) -> str:
    """PNG -> data URI, downscaled to MAX_WIDTH if Pillow is available."""
    raw = path.read_bytes()
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        if img.width > MAX_WIDTH:
            h = round(img.height * MAX_WIDTH / img.width)
            img = img.resize((MAX_WIDTH, h), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            raw = buf.getvalue()
    except ImportError:
        pass                                    # ship the full-size original
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="STRATA")
    ap.add_argument("--college", default="")
    args = ap.parse_args()

    if not TEMPLATE.exists():
        print(f"missing template: {TEMPLATE}")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")

    missing = [n for n in IMAGES.values() if not (SHOTS / n).exists()]
    if missing:
        print("missing screenshots in deck/video/shots/: " + ", ".join(missing))
        print("run:  python3 strata.py console      (one terminal)")
        print("      python3 deck/video/capture.py  (another)")
        return 1

    for token, name in IMAGES.items():
        html = html.replace(token, encode(SHOTS / name))

    html = html.replace("__TEAM__", args.team)
    html = html.replace(" · __COLLEGE__" if not args.college else "__COLLEGE__",
                        "" if not args.college else args.college)

    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1_000_000:.1f} MB)")
    print("open it, press F for fullscreen, A to autoplay, N for cue cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
