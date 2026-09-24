"""
board_box_test.py — preview the DATA BOARD and the ANCHOR + STORY BOX layouts.

Renders ~15 seconds at 1080p (nothing in the worker changes):
  1. anchor + story box: the anchor clip slides left, a navy wall fades in from the right,
     the story image sits in a framed box with a category tag; headline bar + date strip
  2. b-roll with a DATA BOARD: the image first, then a full-screen figures board fades in
     at 2.5s; headline bar, date strip and location tag stay on top
Logo, LIVE bar and the crawl ticker run across both. Reuses an existing anchor clip (no
HeyGen cost) and generates two AI images.

  export JSON2VIDEO_API_KEY=...
  export LOGO_URL=https://automate.wideoutx.com/news69/logo.png      # optional
  python3 board_box_test.py
  python3 board_box_test.py "<another anchor clip url>"

Look for: the anchor's face and shoulders fully clear of the box and wall, no visible
edge where the clip was moved, the board readable at a glance, and nothing colliding
with the headline bar or ticker.
"""
import os, sys, time

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("HEYGEN_API_KEY", "unused")

import graphics as g
from phase3_pipeline import render_movie
from format_test import CLIP, TICKER

SHOW = "The Business Beat"
FADE = 0.3
BOX_IMG = ("Photorealistic editorial news photo of a gas station price sign at dusk beside fuel pumps, "
           "cars refuelling, no readable brand names or logos")
BROLL = ("Photorealistic editorial news photo of a driver refuelling a car at a busy gas station, "
         "daylight, shallow depth of field, no readable brand names or logos")
BOARD = dict(title="National average gas prices", subtitle="Regular unleaded", source="Sample data",
             rows=[("Today", "$3.42"), ("Week ago", "$3.38"), ("Month ago", "$3.51"), ("Year ago", "$3.69")])
CATEGORY, HEADLINE = "Markets", "Gas Prices Tick Higher"


def main():
    clip = sys.argv[1] if len(sys.argv) > 1 else CLIP
    date = g.air_date()
    scenes = [
        {"duration": 7.5, "elements": [g.anchor_left(clip)]
            + g.story_box({"model": "flux-pro", "prompt": BOX_IMG}, CATEGORY)
            + [g.chyron(CATEGORY, HEADLINE), g.date_strip(date)]},
        {"duration": 8.0, "transition": {"style": "fade", "duration": FADE}, "elements": [
            {"type": "image", "model": "flux-pro", "prompt": BROLL, "resize": "cover"},
            g.data_board(start=2.5, duration=5.5, **BOARD),
            g.chyron(CATEGORY, HEADLINE), g.date_strip(date),
            {**g.locator("Nationwide", date.split(",")[0]), "duration": 2.5}]},   # hides when the board comes in
    ]
    total = sum(sc["duration"] for sc in scenes) - FADE * (len(scenes) - 1)
    movie = {"resolution": "full-hd", "quality": "high", "scenes": scenes,
             "elements": [g.bug(), g.live_bar(SHOW)] + g.ticker_crawl(TICKER, total)}
    g.check_sizes(movie)
    print(f"{SHOW} · expected length {total:.1f}s · story box 0-7.5s · data board from ~9.7s")
    t = time.time()
    url = render_movie(movie)
    print(f"\ndone in {int(time.time() - t)}s -> {url}")


if __name__ == "__main__":
    main()
