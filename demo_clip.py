"""
demo_clip.py — one short on-air clip of an anchor, made exactly the way an episode is.

Runs the worker's own code end to end for a single on-camera line:
  1. the anchor clip, rendered by phase3_pipeline.heygen_avatar with Avatar IV switched on
     (HEYGEN_ENGINE=avatar_iv) and the anchor's calm photo from calm_anchors.json,
  2. assembled by JSON2Video with the real graphics: LIVE bar, NEWS CHANNEL 69 logo,
     the anchor's lower third and the ticker.
Prints the finished video link. Nothing is written to the database or the dashboard.

  export HEYGEN_API_KEY=...
  export JSON2VIDEO_API_KEY=...
  export LOGO_URL=https://automate.wideoutx.com/news69/logo.png    # optional: the real logo
  python3 demo_clip.py                       # Emma Chen, The Morning Brief
  python3 demo_clip.py "Marcus Bell"
"""
import os, sys, json, time

os.environ["HEYGEN_ENGINE"] = "avatar_iv"          # must be set before the worker code loads
os.environ["HEYGEN_TEST"] = "false"
os.environ.setdefault("ANTHROPIC_API_KEY", "unused")

import phase3_pipeline as p
import coanchor as c
import graphics as g
from shows import SHOWS

LINE = ("Good morning, I'm {name}. Today, city leaders are weighing a delay to next "
        "year's budget, and we'll walk you through what it means for you.")
TICKER = ["City council weighs budget delay to next month",
          "Markets steady ahead of this week's rate decision",
          "New transit line opens to riders this weekend"]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Emma Chen"
    show = next((s for s in SHOWS.values() if name in (s["a"]["name"], s["b"]["name"])), None)
    if not show:
        sys.exit(f"No anchor called {name!r}")
    anc = show["a"] if show["a"]["name"] == name else show["b"]
    calm = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "calm_anchors.json")))
    photo = (calm.get(name) or {}).get("photo_id")
    if not photo:
        sys.exit(f"No calm photo for {name} yet. Run: python3 calm_anchor.py \"{name}\"")

    t0 = time.time()
    print(f"{name} · {show['title']} · calm photo {photo} · engine {p.HEYGEN_ENGINE}")
    print("1/2 anchor clip at HeyGen (usually 2-10 min)...")
    clip = p.heygen_avatar(LINE.format(name=name), anc["avatar"], anc["voice"], photo, label=f"demo · {name}")

    print("2/2 assembling with on-air graphics at JSON2Video (1-3 min)...")
    tick = c._Ticker(TICKER)
    scene = c._anchor_scene(clip, [g.lower_third(name)], tick)
    movie = {"resolution": "full-hd", "quality": "high", "scenes": [scene],
             "elements": [g.bug(), g.live_bar(show["title"])]}
    g.check_sizes(movie)
    url = p.render_movie(movie)

    print(f"\ndone in {int(time.time() - t0)}s")
    print(f"  anchor clip only:   {clip}")
    print(f"  finished on-air:    {url}")


if __name__ == "__main__":
    main()
