"""
ticker_test.py — try a continuous crawl ticker before touching the worker.

Renders 75 seconds at 1080p: three plain scenes with crossfades (to check the crawl runs
straight through cuts), plus the worker's crawl ticker as MOVIE-level graphics:
  * the band (navy bar + red top rule), static
  * the headline loop, repeated as copies back to back, each moved right-to-left once
    by JSON2Video keyframes (linear)
  * the red "69 NOW" label on top, so the text slides in from behind it
No worker code is changed; this only reads the graphics styles from graphics.py.

  export JSON2VIDEO_API_KEY=...
  python3 ticker_test.py            # 110 px/s
  python3 ticker_test.py 90         # slower crawl, pixels per second

Look for: smooth motion (no stutter or jumping), readable at that speed, the text
passing cleanly behind the red label, no break at the crossfades (25s, 50s), and an even
gap where the next copy of the headline loop starts (printed below).
"""
import os, sys, time

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("HEYGEN_API_KEY", "unused")

import graphics as g
from phase3_pipeline import render_movie

SPEED = float(sys.argv[1]) if len(sys.argv) > 1 else 110.0    # pixels per second
SCENE = 10.0                                                  # two scenes of this length
HEADLINES = [
    "City council votes to delay the budget until next month",
    "Markets steady ahead of this week's interest rate decision",
    "New transit line opens to riders this weekend",
    "Storm system expected to bring heavy rain to the coast",
    "Tech giants report stronger than expected quarterly earnings",
    "Local schools announce extended hours for the fall term",
]

STRIP_X, STRIP_Y, STRIP_H = 230, 988, 92   # same box the current ticker text uses
CHAR_PX = 17                                # generous width per character at 33px Barlow Condensed
SEP_PX = 70                                 # diamond + gaps between headlines


def strip_html(items):
    diamond = (f'<i style="width:11px;height:11px;background:{g.RED};transform:rotate(45deg);'
               'display:inline-block;flex-shrink:0;margin:0 28px"></i>')
    text = diamond.join(g.esc(g.clean_headline(h).upper()) for h in items)
    return (f'<div style="position:absolute;inset:0;display:flex;align-items:center;'
            f'font:600 33px/1 {g.FONT};color:{g.WHITE};letter-spacing:.6px;white-space:nowrap">'
            f'{diamond}{text}</div>')


def main():
    """Uses the worker's own graphics.ticker_crawl, over 3 scenes of 25s with crossfades,
    so it covers the handoff from one copy of the headline loop to the next."""
    total = 75.0 - 2 * 0.3      # 3 x 25s scenes, 2 crossfades that overlap the previous scene
    heads = HEADLINES + ["Senate passes bipartisan infrastructure package after marathon session",
                         "OpenAI, Nvidia and Microsoft shares climb 4% on AI demand"]
    els = g.ticker_crawl(heads, total, speed=SPEED)
    copies = [e for e in els if "keyframes" in e]
    scenes = [{"duration": 25.0, "background-color": col, "elements": []}
              for col in ("#1B2A4A", "#3A2A1B", "#1B3A2A")]
    for sc in scenes[1:]:
        sc["transition"] = {"style": "fade", "duration": 0.3}
    movie = {"resolution": "full-hd", "quality": "high", "scenes": scenes, "elements": els}
    g.check_sizes(movie)
    print(f"{len(copies)} copies of the loop · loop {copies[0]['width']}px · {SPEED:g} px/s")
    print(f"next copy enters at {copies[1]['start']:.1f}s (watch the seam there) · crossfades at ~25s and ~50s")
    print(f"expected video length {total:.1f}s (last copy ends at {max(e['start'] + e['duration'] for e in copies):.1f}s)")
    t = time.time()
    url = render_movie(movie)
    print(f"\ndone in {int(time.time() - t)}s -> {url}")


if __name__ == "__main__":
    main()
