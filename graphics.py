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


def ticker_crawl(headlines, total_secs, speed=None, label="69 Now"):
    """Movie-level crawl ticker for a whole episode: band, moving copies of the headline
    loop, and the label on top so text slides out from behind it.

    total_secs must be the episode's real length: nothing here may end after it, or
    JSON2Video stretches the video to fit (a 75s test came out 150s long)."""
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
    els = [ticker_band(label=None)]
    k = 0
    while k * per_copy < total_secs - 0.05:
        start = round(k * per_copy, 3)
        dur = round(min(travel / speed, total_secs - start), 3)      # the last copy stops at the end
        el = _el(body, loop_w, _CRAWL_H, 1920, _CRAWL_Y, duration=dur, start=start, z=31)
        el["keyframes"] = [{"time": 0, "x": 1920},
                           {"time": dur, "x": round(1920 - speed * dur, 1), "easing": "linear"}]
        els.append(el)
        k += 1
    tag = (f'<span style="position:absolute;left:0;top:0;bottom:0;display:flex;align-items:center;'
           f'background:{RED};color:{WHITE};font:900 italic 33px/1 {FONT};padding:0 25px;'
           f'text-transform:uppercase">{esc(label)}</span>')
    els.append(_el(tag, _CRAWL_LEFT, _CRAWL_H, 0, _CRAWL_Y, z=32))
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
