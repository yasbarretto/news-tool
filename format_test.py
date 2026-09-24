"""
format_test.py — preview the network-rundown format before it goes into episodes.

Renders a ~24 second mock episode at 1080p with the NEW graphics (graphics.py):
  1. full-screen OPEN CARD: channel, show title, air date (3s)
  2. anchor on camera with the name lower third
  3. b-roll story: headline bar + DATE STRIP under it + LOCATION TAG top-left
  4. anchor on camera with the headline bar + date strip
Logo, LIVE bar and the crawl ticker come in after the open card, as they would on air.
Uses an anchor clip that already exists (no HeyGen cost) and one AI b-roll image.
Nothing in the worker changes.

  export JSON2VIDEO_API_KEY=...
  export LOGO_URL=https://automate.wideoutx.com/news69/logo.png      # optional: real logo
  python3 format_test.py
  python3 format_test.py "<another anchor clip url>"

Look for: the open card, the date strip sitting cleanly under the headline bar and above
the ticker, the location tag clear of the LIVE bar, and nothing overlapping the anchor's face.
"""
import os, sys, time

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("HEYGEN_API_KEY", "unused")

import graphics as g
from phase3_pipeline import render_movie

# Emma Chen's calm Avatar IV clip from demo_clip.py (7.7s). Pass another url if it expired.
CLIP = ("https://files2.heygen.ai/aws_pacific/avatar_tmp/daca3d0d7f114bb38c5cd0d8701dc6e6/"
        "7990f6aeef23da8eb73aeda6165b9483.mp4?Expires=1790818919&Signature=CPeL5ddPjhJl3x0PksfWdWXicKERejz9F6jSlQur6t"
        "~JVjOKP~T4zwdRBTB8QtyCIIek8PgVZIrmW4FsvrjEfCaAC56TMlXYEyLZnXWsPpVm2vwIs0~6kB2RYxqzjyhoVraTjv36sqPet0XgG67-D3E"
        "v21lmLykfS9mFIHXD5fKhZRW5d7YELPt8crU5KoS~YdTHuQmG45kWjabNxDlyp~xyFy1~87iN~mPEBDshX13ynU3jtRyjd1S45IB~pH25A-vR"
        "6A3k0E5ouzlUxtJd1l~YL5qVq5yQnGmejLkyk9gSvUr6tFbZ5pPM4PPEiIdF-jDMmcXBgRSxb~V5SoVQ~Q__&Key-Pair-Id=K38HBHX5LX3X2H")
SHOW = "The Morning Brief"
HEADLINE, CATEGORY = "Council Delays City Budget", "Local"
PLACE, SUB = "City Hall", "Thursday"
BROLL = ("Photorealistic editorial news photo of a city council chamber during a public meeting, "
         "council members seated at a curved dais, soft daylight, no readable text, no logos")
TICKER = ["City council votes to delay the budget until next month",
          "Markets steady ahead of this week's interest rate decision",
          "New transit line opens to riders this weekend",
          "Storm system expected to bring heavy rain to the coast"]
FADE = 0.3


def main():
    clip = sys.argv[1] if len(sys.argv) > 1 else CLIP
    date = g.air_date()
    video = {"type": "video", "src": clip, "resize": "cover"}
    scenes = [
        {"duration": 3.0, "elements": [g.open_card(SHOW, date)]},
        {"duration": 7.5, "elements": [dict(video), g.lower_third("Emma Chen")]},
        {"duration": 8.0, "elements": [
            {"type": "image", "model": "flux-pro", "prompt": BROLL, "resize": "cover"},
            g.chyron(CATEGORY, HEADLINE), g.date_strip(date), g.locator(PLACE, SUB)]},
        {"duration": 6.0, "elements": [dict(video), g.chyron(CATEGORY, HEADLINE), g.date_strip(date)]},
    ]
    for sc in scenes[1:]:
        sc["transition"] = {"style": "fade", "duration": FADE}
    total = sum(sc["duration"] for sc in scenes) - FADE * (len(scenes) - 1)
    after_open = scenes[0]["duration"] - FADE               # the first fade overlaps the open card

    def later(el):                                          # logo / LIVE bar: after the open, never past the end
        el["start"], el["duration"] = round(after_open, 3), round(total - after_open, 3)
        el["fade-in"] = FADE
        return el

    movie = {"resolution": "full-hd", "quality": "high", "scenes": scenes,
             "elements": [later(g.bug()), later(g.live_bar(SHOW))]
                         + g.ticker_crawl(TICKER, total, start=after_open)}
    g.check_sizes(movie)
    print(f"{SHOW} · {date} · expected length {total:.1f}s · graphics from {after_open:.1f}s")
    t = time.time()
    url = render_movie(movie)
    print(f"\ndone in {int(time.time() - t)}s -> {url}")


if __name__ == "__main__":
    main()
