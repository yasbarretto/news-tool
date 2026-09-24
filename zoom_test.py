"""
zoom_test.py — check the side-bar crop on ONE existing anchor clip, in about a minute.

Takes any finished HeyGen clip url (e.g. from check_anchor.py), assembles a 1080p video
with the anchor clip exactly as the worker now places it, and prints the result url.

  export JSON2VIDEO_API_KEY=...
  python3 zoom_test.py "<heygen clip url>"
"""
import os, sys, time

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("HEYGEN_API_KEY", "unused")

import coanchor
from phase3_pipeline import render_movie

if len(sys.argv) < 2:
    sys.exit('usage: python3 zoom_test.py "<heygen clip url>"')

el = coanchor._anchor_video(sys.argv[1])
print("anchor element:", {k: v for k, v in el.items() if k != "src"})
movie = {"resolution": "full-hd", "quality": "high", "scenes": [{"elements": [el]}]}
t = time.time()
url = render_movie(movie)
print(f"\ndone in {int(time.time() - t)}s -> {url}")
print("Open it: the sides should be the studio background edge to edge, no light bars.")
