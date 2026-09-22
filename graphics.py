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
import html as _h

NAVY, DEEP, RED, WHITE, SILVER = "#0A1F4F", "#061233", "#D0112B", "#FFFFFF", "#C9D1DE"
FONT = "'Barlow Condensed','Arial Narrow','Helvetica Neue',Arial,sans-serif"
_HEAD = ('<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:'
         'ital,wght@0,600;0,700;0,800;1,800;1,900&display=swap" rel="stylesheet">'
         '<style>*{margin:0;padding:0;box-sizing:border-box}html,body{background:transparent;'
         f'font-family:{FONT};overflow:hidden}}</style>')


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
    """NEWS CHANNEL 69 logo bug, top-right, whole video. Swap for the PNG when it arrives."""
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
        f'<i style="width:13px;height:13px;border-radius:50%;background:{WHITE};display:inline-block;'
        f'animation:p 1.6s infinite"></i>Live</span>'
        f'<span style="background:{NAVY};color:{WHITE};font:700 29px/1 {FONT};letter-spacing:1px;'
        f'padding:10px 19px;display:flex;align-items:center;text-transform:uppercase">{esc(show_title)}</span></div>'
        '<style>@keyframes p{0%,100%{opacity:1}50%{opacity:.25}}</style>'
    )
    return _el(body, 820, 60, 58, 44, z=20)


def ticker(items, label="69 Now", seconds_per_item=7):
    """Full-width scrolling ticker, whole video. The only continuous motion on screen."""
    items = [esc(str(i).upper()) for i in items if i][:10] or ["NEWS CHANNEL 69"]  # upper THEN escape
    track = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:22px;margin-right:56px">'
        f'<i style="width:10px;height:10px;background:{RED};transform:rotate(45deg);display:inline-block"></i>{t}</span>'
        for t in items
    )
    dur = max(20, len(items) * seconds_per_item)
    body = (
        f'<div style="position:absolute;inset:0;display:flex;background:{DEEP};border-top:5px solid {RED}">'
        f'<span style="background:{RED};color:{WHITE};font:900 italic 33px/1 {FONT};padding:0 25px;'
        f'display:flex;align-items:center;flex-shrink:0;text-transform:uppercase;z-index:2">{esc(label)}</span>'
        f'<div style="overflow:hidden;flex:1;display:flex;align-items:center">'
        f'<div style="display:flex;white-space:nowrap;padding-left:38px;animation:roll {dur}s linear infinite;'
        f'font:600 31px/1 {FONT};color:{WHITE};letter-spacing:.6px">{track}{track}</div></div></div>'
        '<style>@keyframes roll{from{transform:translateX(0)}to{transform:translateX(-50%)}}</style>'
    )
    return _el(body, 1920, 97, 0, 983, z=30)


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
