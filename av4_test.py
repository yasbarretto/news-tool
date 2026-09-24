"""
av4_test.py — does HeyGen's Avatar IV engine keep a calm anchor calm?

The v2 talking_photo animation (what the worker uses) grinned in every test, whatever we
sent: expression, talking_style, voice emotion, even a serious voice. HeyGen's v3 API has
the newer Avatar IV engine, which takes `expressiveness` (low/medium/high) and a
plain-English `motion_prompt` for photo avatars. Docs: https://developers.heygen.com/avatar-iv

Renders the same calm photo avatar (from calm_anchors.json) with the same news line:
  A. Avatar IV, expressiveness=low
  B. Avatar IV, expressiveness=low + calm motion prompt
Then saves a contact sheet (8 frames per clip) and checks resolution and side bars.

  export HEYGEN_API_KEY=...
  python3 av4_test.py                 # Emma Chen
  python3 av4_test.py "Marcus Bell"

Avatar IV costs more per second than the old engine; this is two ~4 second clips.
"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image, ImageDraw

import calm_anchor as c
from expression_test import frames, NEWS_LINE

CALM = ("Calm, composed TV news anchor reading a serious news story. Neutral, relaxed face "
        "with lips closed between words. No smiling, no grinning. Minimal head movement, "
        "steady eye contact with the camera.")

VARIANTS = [
    ("A  Avatar IV, expressiveness=low", {"expressiveness": "low"}),
    ("B  Avatar IV, low + calm motion prompt", {"expressiveness": "low", "motion_prompt": CALM}),
]


def render(name, pid, extra):
    body = {"type": "avatar", "avatar_id": pid, "script": NEWS_LINE, "voice_id": c.VOICE[name],
            "resolution": "1080p", "aspect_ratio": "16:9", "engine": {"type": "avatar_iv"}, **extra}
    r = requests.post(f"{c.API}/v3/videos", headers=c.HJ, json=body, timeout=90).json()
    d = r.get("data") or r
    vid = d.get("video_id")
    if not vid:
        raise RuntimeError(f"rejected: {str(r)[:400]}")
    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        time.sleep(10)
        s = c._get(f"{c.API}/v3/videos/{vid}")
        s = s.get("data") or s
        if s.get("status") == "completed" and s.get("video_url"):
            return s["video_url"]
        if s.get("status") == "failed":
            raise RuntimeError(f"failed: {s.get('failure_code')} {s.get('failure_message')}")
    raise RuntimeError("timed out (30 min)")


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Emma Chen"
    pid = (c.load(c.OUT, {}).get(name) or {}).get("photo_id")
    if not pid:
        sys.exit(f"No calm avatar for {name} yet. Run: python3 calm_anchor.py \"{name}\"")
    print(f"{name} · avatar {pid} · rendering {len(VARIANTS)} Avatar IV clips (a few minutes)")

    def one(v):
        label, extra = v
        try:
            url = render(name, pid, extra)
            fr = frames(url)
            left, right = c.side_bars(fr[0]) if fr else (-1, -1)
            size = f"{fr[0].size[0]}x{fr[0].size[1]}" if fr else "?"
            return label, url, fr, f"{size}, bars {left}/{right}px"
        except Exception as e:
            return label, None, [], f"FAILED: {str(e)[:200]}"

    with ThreadPoolExecutor(len(VARIANTS)) as ex:
        results = list(ex.map(one, VARIANTS))

    T = 240
    rows = []
    for label, url, fr, check in results:
        print(f"\n{label}: {check}\n  {url}")
        crops = []
        for f in fr:
            w, h = f.size
            box = (int(w * .33), 0, int(w * .67), int(h * .62))
            crops.append(f.crop(box).resize((T, int(T * (box[3] - box[1]) / (box[2] - box[0])))))
        rows.append((f"{label} · {check}", crops))
    th = max((r[1][0].size[1] for r in rows if r[1]), default=T)
    sheet = Image.new("RGB", (T * 8, (th + 26) * len(rows)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (text, crops) in enumerate(rows):
        y = i * (th + 26)
        d.text((6, y + 6), text, fill="black")
        for j, cimg in enumerate(crops):
            sheet.paste(cimg, (j * T, y + 26))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"av4_test_{name.replace(' ', '_')}.jpg")
    sheet.save(out, quality=88)
    print(f"\nsheet: {out}")


if __name__ == "__main__":
    main()
