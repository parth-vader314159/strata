#!/usr/bin/env python3
"""Capture the three console screenshots the video reel uses.

Needs the console running and Playwright installed:

    pip install playwright && playwright install chromium
    python3 strata.py console          # in another terminal
    python3 deck/video/capture.py

Writes deck/video/shots/{overview,inspector,integrity}.png, then rebuild the
reel with build_visuals.py.

If you would rather not install Playwright: open the console yourself, take
three screenshots by hand, and save them under those names. The build script
does not care how they got there.
"""

from __future__ import annotations

import sys
from pathlib import Path

SHOTS = Path(__file__).resolve().parent / "shots"
URL = "http://localhost:8400"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(__doc__)
        return 1

    SHOTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 900},
                                device_scale_factor=2)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            print(f"could not reach {URL} — is `python3 strata.py console` running?")
            return 1
        page.wait_for_selector("nav button")
        page.wait_for_timeout(1500)

        # Live counters start at zero in a fresh console process, so generate
        # some traffic before capturing the overview or every tile reads 0.
        page.get_by_text("Generate traffic").first.click()
        page.wait_for_timeout(9000)
        page.screenshot(path=str(SHOTS / "overview.png"))

        page.click('nav button[data-v="inspect"]')
        page.wait_for_timeout(1200)
        page.get_by_text("Take a recent one").first.click()
        page.wait_for_timeout(3500)
        page.screenshot(path=str(SHOTS / "inspector.png"))

        page.click('nav button[data-v="integrity"]')
        page.wait_for_timeout(1200)
        audit = page.query_selector("text=Run full audit")
        if audit:
            audit.click()
            page.wait_for_timeout(6000)
        page.screenshot(path=str(SHOTS / "integrity.png"))

        browser.close()

    for name in ("overview.png", "inspector.png", "integrity.png"):
        print(f"  wrote {SHOTS / name}")
    print("\nnow: python3 deck/video/build_visuals.py --team \"Your Team\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
