"""
check_anchor.py — prove the anchor fix before a demo, with ~6 seconds of avatar time.

Renders one short line with the anchor's photo from shows.PHOTOS, sent exactly as the
worker sends it, then measures the first frame for side bars and prints the video url.

  export HEYGEN_API_KEY=...
  python3 check_anchor.py                 # Emma Chen
  python3 check_anchor.py "Marcus Bell"
"""
import os, sys, io, time, subprocess, tempfile

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")     # phase3_pipeline reads these on import
os.environ.setdefault("JSON2VIDEO_API_KEY", "unused")
os.environ["HEYGEN_TEST"] = "false"                        # a real render, like the demo

import requests
import phase3_pipeline as p
from shows import PHOTOS, SHOWS

LINE = "Good morning, and welcome to The Morning Brief. Here's what we're following today."
name = sys.argv[1] if len(sys.argv) > 1 else "Emma Chen"
anchor = next((s[k] for s in SHOWS.values() for k in ("a", "b") if s[k]["name"] == name), None)
if not anchor:
    sys.exit(f"No anchor called {name!r}")

look = PHOTOS.get(name)
# Same look every time; only the request changes. Video 28 (version 10) sent the photo id
# and nothing else. Every version since has added "expression".
def payload(expression=False, dimension=False):
    ch = {"type": "talking_photo", "talking_photo_id": look}
    if expression:
        ch["expression"] = "default"
    body = {"video_inputs": [{"character": ch,
                              "voice": {"type": "text", "input_text": LINE, "voice_id": anchor["voice"]}}],
            "aspect_ratio": "16:9", "test": False}
    if dimension:
        body["dimension"] = {"width": 1920, "height": 1080}
    return body

variants = [("ORIGINAL photo, version-8 request", payload())]


def bars(img):
    """Width of the flat light padding on the left and right of a frame, in pixels."""
    from PIL import Image
    im = Image.open(io.BytesIO(img)).convert("RGB")
    w, h = im.size

    def edge(xs):
        n = 0
        for x in xs:
            col = [im.getpixel((x, y)) for y in range(h // 5, h * 4 // 5, 8)]
            if all(min(c) > 215 for c in col):   # near-white column = padding
                n += 1
            else:
                break
        return n
    return w, h, edge(range(w)), edge(range(w - 1, -1, -1))


def first_frame(url):
    """First frame of the clip, via ffmpeg if present, else HeyGen's thumbnail."""
    try:
        out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", url, "-frames:v", "1",
                              "-f", "image2", "-vcodec", "png", "-"], capture_output=True, timeout=120)
        if out.returncode == 0 and out.stdout:
            return out.stdout
    except FileNotFoundError:
        pass
    if os.path.exists("/usr/bin/qlmanage"):          # macOS: Quick Look can thumbnail an mp4
        d = tempfile.mkdtemp()
        f = os.path.join(d, "clip.mp4")
        open(f, "wb").write(requests.get(url, timeout=120).content)
        subprocess.run(["qlmanage", "-t", "-s", "1920", "-o", d, f], capture_output=True, timeout=120)
        png = f + ".png"
        if os.path.exists(png):
            return open(png, "rb").read()
    return None


jobs = {}
for label, body in variants:
    r = requests.post("https://api.heygen.com/v2/video/generate", headers=p.HH, json=body, timeout=30).json()
    if not (r.get("data") or {}).get("video_id"):
        sys.exit(f"HeyGen rejected it: {str(r)[:400]}")
    jobs[label] = r["data"]["video_id"]
    print(f"{label}: submitted {jobs[label]}")

print("\nwaiting for HeyGen (usually 2-10 min)...")
for label, vid in jobs.items():
    d = p.wait_for(label,
                   lambda: requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={vid}",
                                        headers=p.HH, timeout=30).json().get("data"),
                   lambda d: d.get("status") == "completed" and d.get("video_url"),
                   lambda d: d.get("status") in ("failed", "error"),
                   30 * 60)
    img = first_frame(d["video_url"])
    if img is None and d.get("thumbnail_url"):
        img = requests.get(d["thumbnail_url"], timeout=60).content
    print(f"\n=== {label}")
    print(f"  video: {d['video_url']}")
    if img:
        w, h, left, right = bars(img)
        verdict = "FULL WIDTH" if max(left, right) < 5 else "HAS SIDE BARS"
        print(f"  frame {w}x{h} · left bar {left}px · right bar {right}px -> {verdict}")
    else:
        print("  (couldn't grab a frame; open the video url and look at the sides)")
