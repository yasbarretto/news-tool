"""
graphics.py — News Channel 69 on-air graphics, as JSON2Video HTML elements.

Each overlay is its own small HTML element positioned in 1920x1080 pixel space.
HTML elements render in a headless browser on a transparent background, so they
composite straight over the video. CSS animations are captured frame by frame,
which is how the ticker scrolls.

Layout (matches news69_video_frames.html):
  top-left   LIVE + show name          top-right  NEWS CHANNEL 69 bug
  lower zone ONE of: lower third | chyron | title card | sign-off
  captions   lifted above the lower zone (set in pipeline)
  bottom     ticker, full width
"""
import os
import html as _h

NAVY, DEEP, RED, WHITE, SILVER = "#0A1F4F", "#061233", "#D0112B", "#FFFFFF", "#C9D1DE"
LOGO_URL = os.environ.get("LOGO_URL", "")   # hosted PNG; falls back to the text bug
LOGO_W, LOGO_H = 112, 110

FONT = "'Barlow Condensed','Arial Narrow','Helvetica Neue',Arial,sans-serif"
_HEAD = ('<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:'
         'ital,wght@0,600;0,700;0,800;1,800;1,900&display=swap" rel="stylesheet">'
         '<style>*{margin:0;padding:0;box-sizing:border-box}html,body{background:transparent;'
         f'font-family:{FONT};overflow:hidden}}</style>')


# JSON2Video returns 414 for oversized HTML elements. The failing ticker was ~8.8 KB
# URL-encoded; everything else is ~1.2 KB. Budget well under 8 KB.
MAX_HTML = 6000


def html_size(html):
    from urllib.parse import quote
    return len(quote(html))


def check_sizes(movie):
    """Raise before rendering if any HTML element would be rejected for size."""
    too_big = []
    for where, els in [("movie", movie.get("elements", []))] + \
                      [(f"scene {i}", sc.get("elements", [])) for i, sc in enumerate(movie.get("scenes", []))]:
        for j, e in enumerate(els):
            if e.get("type") == "html":
                n = html_size(e["html"])
                if n > MAX_HTML:
                    too_big.append(f"{where} element {j}: {n:,} bytes")
    if too_big:
        raise RuntimeError("HTML graphics too large for JSON2Video (414): " + "; ".join(too_big))


def esc(s):
    return _h.escape(str(s or ""), quote=True)


def _el(body, w, h, x, y, duration=-2, start=0, fade=None, z=10):
    el = {
        "type": "html", "html": _HEAD + body,
        "position": "custom", "x": int(x), "y": int(y),
        "width": int(w), "height": int(h),
        "duration": duration, "start": start, "z-index": z,
    }
    if fade:
        el["fade-in"] = fade
        el["fade-out"] = fade
    return el


# ---------------------------------------------------------------- movie-level
def bug():
    """NEWS CHANNEL 69 logo bug, top-right, whole video.

    Uses the real logo when LOGO_URL is set, otherwise the text-built stand-in, so the
    worker still renders if the asset is missing or the host is down."""
    if LOGO_URL:
        return {"type": "image", "src": LOGO_URL, "position": "custom",
                "x": 1920 - 58 - LOGO_W, "y": 36,
                "width": LOGO_W, "height": LOGO_H,
                "duration": -2, "z-index": 20}

    body = (
        f'<div style="position:absolute;right:0;top:0;display:flex;align-items:center;gap:9px;'
        f'background:{WHITE};border-radius:9px;padding:8px 15px;box-shadow:0 6px 18px rgba(0,0,0,.28)">'
        f'<span style="font:900 italic 23px/0.95 {FONT};color:{RED};text-transform:uppercase">News<br>Channel</span>'
        f'<span style="font:900 italic 50px/1 {FONT};color:{NAVY};letter-spacing:-1px">69</span></div>'
    )
    return _el(body, 250, 100, 1920 - 58 - 250, 40, z=20)


def live_bar(show_title):
    """LIVE + show name, top-left, whole video."""
    body = (
        f'<div style="display:flex;align-items:stretch">'
        f'<span style="background:{RED};color:{WHITE};font:800 italic 29px/1 {FONT};padding:10px 17px;'
        f'display:flex;align-items:center;gap:9px;text-transform:uppercase">'
        f'<i style="width:13px;height:13px;border-radius:50%;background:{WHITE};display:inline-block"></i>Live</span>'
        f'<span style="background:{NAVY};color:{WHITE};font:700 29px/1 {FONT};letter-spacing:1px;'
        f'padding:10px 19px;display:flex;align-items:center;text-transform:uppercase">{esc(show_title)}</span></div>'
    )
    return _el(body, 820, 60, 58, 44, z=20)


def clean_headline(t, limit=100):
    """Google News titles end in ' - Publisher'. Drop it, and keep ticker items short."""
    import re
    t = str(t or "").strip()
    if " - " in t:
        t = t.rsplit(" - ", 1)[0].strip()
    t = re.sub(r"^(news|breaking|update|watch|live)\s*:\s*", "", t, flags=re.I)  # "News : Update to..."
    # ~1600px of bar at 33px Barlow Condensed fits roughly 100 caps characters
    return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"


def ticker_band(label="69 Now"):
    """Ticker background + label. Static, repeated in every scene: identical pixels,
    so the hard cuts between scenes are invisible. label=None: the bar only (the crawl
    puts its label on a separate layer above the moving text)."""
    tag = (f'<span style="background:{RED};color:{WHITE};font:900 italic 33px/1 {FONT};padding:0 25px;'
           f'display:flex;align-items:center;text-transform:uppercase">{esc(label)}</span>') if label else ""
    body = (f'<div style="position:absolute;inset:0;display:flex;background:{DEEP};border-top:5px solid {RED}">'
            f'{tag}</div>')
    return _el(body, 1920, 97, 0, 983, z=30)


# ---------------------------------------------------------------- crawl ticker
# Continuous right-to-left crawl, moved by JSON2Video keyframes (the renderer moves it, so
# no CSS animation and no jitter). One loop of the day's headlines is repeated as separate
# copies back to back, each making ONE linear pass, so there is never a jump to hide.
# Tested in ticker_test.py: smooth, and it runs straight through the scene crossfades.
CRAWL_SPEED = float(os.environ.get("TICKER_SPEED", "110"))   # pixels per second
_CRAWL_LEFT, _CRAWL_Y, _CRAWL_H = 230, 988, 92                # text box, right of the label
_SEP = 11 + 56                                                # diamond + its margins


def _text_px(text):
    """Width of uppercase text at 33px Barlow Condensed 600. Calibrated in a browser against
    the real font (normal headlines ~14px a letter); slightly generous so text is never cut."""
    w = 0
    for ch in text.upper():
        w += 23 if ch in "MW" else 8 if ch in " I.,'’:;!|1-" else 15.5
    return w


def ticker_crawl(headlines, total_secs, speed=None, label="69 Now", start=0.0):
    """Movie-level crawl ticker for a whole episode: band, moving copies of the headline
    loop, and the label on top so text slides out from behind it.

    total_secs must be the episode's real length: nothing here may end after it, or
    JSON2Video stretches the video to fit (a 75s test came out 150s long).
    start: seconds before the ticker appears (e.g. after a full-screen open card)."""
    speed = speed or CRAWL_SPEED
    items = [esc(clean_headline(h).upper()) for h in headlines if h] or ["NEWS CHANNEL 69"]
    diamond = (f'<i style="width:11px;height:11px;background:{RED};transform:rotate(45deg);'
               'display:inline-block;flex-shrink:0;margin:0 28px"></i>')
    body = (f'<div style="position:absolute;inset:0;display:flex;align-items:center;'
            f'font:600 33px/1 {FONT};color:{WHITE};letter-spacing:.6px;white-space:nowrap">'
            + "".join(diamond + t for t in items) + '</div>')
    # 1% over: measured in a render, the estimate itself already runs ~1% wide. More margin
    # shows up as an extra gap where one copy of the loop hands over to the next.
    loop_w = int((sum(_text_px(clean_headline(h)) for h in headlines if h) + _SEP * len(items)) * 1.01) or 1000
    travel = 1920 - (_CRAWL_LEFT - loop_w)                      # enter at the right edge, exit behind the label
    per_copy = loop_w / speed                                   # a new copy enters every per_copy seconds
    def from_start(el):                  # band and label: from `start` to the end, never past it
        if start:
            el["start"], el["duration"] = round(start, 3), round(total_secs - start, 3)
        return el

    els = [from_start(ticker_band(label=None))]
    k = 0
    while start + k * per_copy < total_secs - 0.05:
        t0 = round(start + k * per_copy, 3)
        dur = round(min(travel / speed, total_secs - t0), 3)         # the last copy stops at the end
        el = _el(body, loop_w, _CRAWL_H, 1920, _CRAWL_Y, duration=dur, start=t0, z=31)
        el["keyframes"] = [{"time": 0, "x": 1920},
                           {"time": dur, "x": round(1920 - speed * dur, 1), "easing": "linear"}]
        els.append(el)
        k += 1
    tag = (f'<span style="position:absolute;left:0;top:0;bottom:0;display:flex;align-items:center;'
           f'background:{RED};color:{WHITE};font:900 italic 33px/1 {FONT};padding:0 25px;'
           f'text-transform:uppercase">{esc(label)}</span>')
    els.append(from_start(_el(tag, _CRAWL_LEFT, _CRAWL_H, 0, _CRAWL_Y, z=32)))
    return els


def ticker_item(headline, start=0, duration=-2):
    """One headline in the ticker, fading in. Flip-style ticker: HTML elements are captured
    frame by frame from a fresh page, so CSS scrolling jitters instead of moving. Native
    fades are reliable."""
    t = esc(clean_headline(headline).upper())
    body = (
        f'<div style="position:absolute;inset:0;display:flex;align-items:center;gap:22px;'
        f'font:600 33px/1 {FONT};color:{WHITE};letter-spacing:.6px;white-space:nowrap;overflow:hidden">'
        f'<i style="width:11px;height:11px;background:{RED};transform:rotate(45deg);display:inline-block;flex-shrink:0"></i>{t}</div>'
    )
    el = _el(body, 1640, 92, 230, 988, duration=duration, start=start, z=31)
    el["fade-in"] = 0.35
    return el


# ---------------------------------------------------------------- scene-level
def title_card(show_title, name_a, name_b, duration=-2):
    """Open: show title + both anchor names."""
    body = (
        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:11px">'
        f'<span style="background:{RED};color:{WHITE};font:900 italic 69px/1 {FONT};padding:11px 46px;'
        f'text-transform:uppercase;clip-path:polygon(2% 0,100% 0,98% 100%,0 100%)">{esc(show_title)}</span>'
        f'<span style="display:flex;background:{NAVY};color:{WHITE};font:600 31px/1 {FONT};letter-spacing:1px;'
        f'padding:11px 31px;text-transform:uppercase">{esc(name_a)}'
        f'<span style="border-left:3px solid {RED};margin-left:23px;padding-left:23px">{esc(name_b)}</span></span></div>'
    )
    return _el(body, 1920, 190, 0, 745, duration=duration, fade=0.3, z=15)


def lower_third(name, role="News Channel 69 anchor", duration=5):
    """Anchor name bar. Shown for the first few seconds of each on-camera read."""
    body = (
        '<div style="display:flex;flex-direction:column">'
        f'<span style="background:{WHITE};color:{NAVY};font:800 50px/1 {FONT};padding:12px 27px 10px;'
        f'text-transform:uppercase;border-left:13px solid {RED};width:max-content">{esc(name)}</span>'
        f'<span style="background:{NAVY};color:{SILVER};font:600 26px/1 {FONT};letter-spacing:1px;'
        f'padding:10px 27px;text-transform:uppercase;border-left:13px solid {RED};width:max-content">{esc(role)}</span></div>'
    )
    return _el(body, 1100, 130, 58, 800, duration=duration, start=0.3, fade=0.3, z=15)


def chyron(category, headline):
    """Story headline during b-roll. Replaces the lower third in the same zone."""
    body = (
        '<div style="display:flex;align-items:stretch;height:100%">'
        f'<span style="background:{RED};color:{WHITE};font:900 italic 31px/1 {FONT};padding:0 21px;'
        f'display:flex;align-items:center;text-transform:uppercase">{esc(category or "News")}</span>'
        f'<span style="background:{WHITE};color:{NAVY};font:800 48px/1 {FONT};padding:0 27px;'
        f'display:flex;align-items:center;text-transform:uppercase;flex:1">{esc(headline)}</span></div>'
    )
    return _el(body, 1804, 92, 58, 836, duration=-2, fade=0.3, z=15)


# ---------------------------------------------------------------- broadcast format (in test)
# Modelled on the FORMAT of a network rundown (open card, dated headline bar, location tag),
# drawn in News Channel 69's own style. Not wired into episodes yet: see format_test.py.
def air_date(tz=None):
    """'WEDNESDAY, SEPTEMBER 24' in the channel's time zone (SHOW_TZ)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo(tz or os.environ.get("SHOW_TZ", "America/New_York")))
    return now.strftime("%A, %B ") + str(now.day)


def open_card(show_title, date_text, duration=3.0):
    """Full-screen show open: channel name, show title, air date. Its own scene, before the
    first anchor; the movie-level graphics start after it."""
    body = (
        f'<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;'
        f'justify-content:center;gap:26px;background:radial-gradient(ellipse at 50% 42%,#15306E 0%,{NAVY} 45%,{DEEP} 100%)">'
        f'<span style="color:{SILVER};font:700 34px/1 {FONT};letter-spacing:10px;text-transform:uppercase">'
        f'News Channel <b style="color:{WHITE}">69</b></span>'
        f'<span style="background:{RED};color:{WHITE};font:900 italic 150px/1 {FONT};padding:18px 70px 22px;'
        f'text-transform:uppercase;clip-path:polygon(3% 0,100% 0,97% 100%,0 100%)">{esc(show_title)}</span>'
        f'<span style="color:{WHITE};font:700 46px/1 {FONT};letter-spacing:4px;text-transform:uppercase;'
        f'border-top:4px solid {RED};padding-top:18px">{esc(date_text)}</span></div>'
    )
    return _el(body, 1920, 1080, 0, 0, duration=duration, z=5)


def date_strip(date_text):
    """Thin dated strip under the story headline bar."""
    body = (f'<span style="position:absolute;left:0;top:0;bottom:0;display:flex;align-items:center;'
            f'background:{RED};color:{WHITE};font:700 24px/1 {FONT};letter-spacing:2px;padding:0 22px;'
            f'text-transform:uppercase">{esc(date_text)}</span>')
    return _el(body, 1200, 38, 58, 928, duration=-2, fade=0.3, z=15)


def locator(place, sub=""):
    """Where the story is: place on top, a smaller line (day, source) under it. Top-left,
    below the LIVE bar, over b-roll only."""
    subline = (f'<span style="background:{RED};color:{WHITE};font:700 22px/1 {FONT};letter-spacing:1.5px;'
               f'padding:6px 16px;text-transform:uppercase;width:max-content">{esc(sub)}</span>') if sub else ""
    body = (f'<div style="display:flex;flex-direction:column">'
            f'<span style="background:{WHITE};color:{NAVY};font:800 34px/1 {FONT};padding:9px 16px 7px;'
            f'text-transform:uppercase;width:max-content;border-left:8px solid {RED}">{esc(place)}</span>'
            f'{subline}</div>')
    return _el(body, 900, 90, 58, 122, duration=-2, fade=0.3, z=15)


# ---------------------------------------------------------------- data board + story box (in test)
# Not wired into episodes yet: see board_box_test.py.
def data_board(title, rows, subtitle="", source="", start=0, duration=-2):
    """Full-screen figures board, e.g. prices today / week ago / month ago / year ago.
    rows: 2 to 4 (label, value) pairs. Sits under the headline bar and date strip (z 12)."""
    rows = [(str(a), str(b)) for a, b in rows][:4]
    size = {2: 130, 3: 100, 4: 84}.get(len(rows), 84)
    items = "".join(
        f'<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;'
        f'border-bottom:2px solid rgba(201,209,222,.25)">'
        f'<span style="color:{SILVER};font:700 {int(size * .52)}px/1 {FONT};letter-spacing:2px;text-transform:uppercase">{esc(a)}</span>'
        f'<span style="color:{WHITE};font:800 {size}px/1 {FONT};font-variant-numeric:tabular-nums">{esc(b)}</span></div>'
        for a, b in rows)
    sub = (f'<div style="color:{WHITE};background:{RED};font:700 30px/1 {FONT};letter-spacing:3px;padding:9px 20px;'
           f'text-transform:uppercase;width:max-content;margin-top:10px">{esc(subtitle)}</div>') if subtitle else ""
    src = (f'<div style="color:{SILVER};font:600 24px/1 {FONT};letter-spacing:2px;text-transform:uppercase;'
           f'margin-top:16px;opacity:.8">Source: {esc(source)}</div>') if source else ""
    body = (
        f'<div style="position:absolute;inset:0;background:linear-gradient(160deg,#15306E 0%,{NAVY} 45%,{DEEP} 100%)">'
        # content starts at y 200: clear of the LIVE bar (y 44-104) and the location zone
        f'<div style="position:absolute;left:300px;right:300px;top:200px">'
        f'<div style="color:{WHITE};font:900 italic 68px/1 {FONT};text-transform:uppercase;border-left:14px solid {RED};'
        f'padding-left:24px">{esc(title)}</div>{sub}'
        f'<div style="margin-top:22px">{items}</div>{src}</div></div>'
    )
    el = _el(body, 1920, 1080, 0, 0, duration=duration, start=start, z=12)
    el["fade-in"] = 0.4
    return el


# Story box layout: the anchor clip slides left so the anchor sits at about a third of the
# frame; a navy wall fades in from the right over the clip's edge; the story image sits in
# a framed box on the wall.
BOX_SHIFT = 380                                  # px the anchor clip moves left
BOX = (1010, 150, 820, 462)                      # x, y, w, h of the story image (16:9)


def anchor_left(url):
    """The anchor clip, moved left for the story-box layout."""
    return {"type": "video", "src": url, "resize": "cover", "position": "custom",
            "x": -BOX_SHIFT, "y": 0, "width": 1920, "height": 1080}


def story_box(image, category="", duration=-2):
    """Wall + framed story image + category tag. image: a JSON2Video image source dict,
    e.g. {"model": "flux-pro", "prompt": ...} or {"src": url}."""
    x, y, w, h = BOX
    # The wall is a MASK: navy everywhere right of the anchor except a window exactly where
    # the box is, so nothing of the image can show outside the frame. The wall's left edge
    # fades in over the moved clip's right edge.
    left = x - 160                                   # wall starts here (the fade runs 160px)
    wx = x - left                                    # window position inside the wall element
    ww = 1920 - left
    hole = (f"M0 0 H{ww} V1080 H0 Z "
            f"M{wx} {y} V{y + h} H{wx + w} V{y} Z")  # evenodd: the second rectangle is cut out
    wall = _el(f'<div style="position:absolute;inset:0;clip-path:path(evenodd,\'{hole}\');'
               f'background:linear-gradient(90deg,rgba(6,18,51,0) 0px,rgba(6,18,51,.9) 150px,{DEEP} 420px)"></div>',
               ww, 1080, left, 0, duration=duration, z=5)
    # No "resize": with resize set, JSON2Video ignores width/height (per its docs), which is
    # why the first test showed only the image's top-left corner. Width fixed, height -1
    # (keep the image's own shape); the wall's window trims anything not exactly 16:9.
    pic = {"type": "image", "position": "custom", "x": x, "y": y, "width": w, "height": -1,
           "duration": duration, "z-index": 4, **image}
    # frame element: 50px of headroom above the box for the category tag, then the border
    tag = (f'<span style="position:absolute;left:0;top:0;height:50px;display:flex;align-items:center;'
           f'background:{RED};color:{WHITE};font:900 italic 30px/1 {FONT};padding:0 18px;'
           f'text-transform:uppercase">{esc(category)}</span>') if category else ""
    border = (f'<div style="position:absolute;left:0;right:0;top:50px;bottom:0;border:6px solid {WHITE};'
              f'box-shadow:0 14px 40px rgba(0,0,0,.5)"></div>')
    frame = _el(border + tag, w + 12, h + 12 + 50, x - 6, y - 6 - 50, duration=duration, z=6)
    return [wall, pic, frame]


def sign_off(tagline, subline="AI-generated presenters"):
    """Close: tagline doubles as the AI disclosure."""
    body = (
        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:13px">'
        f'<span style="color:{WHITE};font:900 italic 58px/1 {FONT};text-transform:uppercase;'
        f'text-shadow:0 6px 18px rgba(0,0,0,.55)">{esc(tagline)}</span>'
        f'<span style="color:{SILVER};font:600 27px/1 {FONT};letter-spacing:4px;text-transform:uppercase;'
        f'text-shadow:0 3px 10px rgba(0,0,0,.6)">{esc(subline)}</span></div>'
    )
    return _el(body, 1920, 170, 0, 760, duration=-2, fade=0.4, z=15)
