"""
calm_anchor.py — give an anchor a calm, full-width, 1080p photo avatar.

Why: the original photos (2752x1536) render sharp and full width but every one is a big
smile. The composed looks from `make_anchors.py looks` are calm and the same face, but
HeyGen makes them at 1024x608, and at that size HeyGen pads them with side bars and
renders at 720p. So we:
  1. take the anchor's composed look,
  2. trim it to exactly 16:9 and enlarge it to 2752x1548 (the originals' size) locally,
  3. upload that to HeyGen as a new photo avatar,
  4. render a ~6s test clip and measure it for side bars and resolution.
Nothing is generated, so this spends no look credits: one upload plus a few seconds of
avatar time per anchor.

  export HEYGEN_API_KEY=...
  python3 calm_anchor.py "Emma Chen"     # ONE anchor first, then open the link
  python3 calm_anchor.py --all           # the rest (skips ones already done)
  python3 calm_anchor.py "Savannah Blake" --new 2   # use option 2 from new_look.py instead

Needs ~/Downloads/anchors.json (from make_anchors.py). Results go to calm_anchors.json
next to this script; at the end it prints the PHOTOS lines to paste into shows.py.
"""
import os, sys, io, json, time, subprocess, tempfile

import requests
from PIL import Image, ImageFilter

KEY = os.environ["HEYGEN_API_KEY"]
H = {"X-Api-Key": KEY}
HJ = {**H, "Content-Type": "application/json"}
API = "https://api.heygen.com"
STATE = os.path.expanduser(os.environ.get("ANCHORS_JSON", "~/Downloads/anchors.json"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calm_anchors.json")
LINE = "The city council voted last night to delay the budget until next month."

# Which composed look to use per anchor: the calmest one that still matches the anchor's
# face and hair (picked from the contact sheet). None = no composed look matches.
PICK = {
    "Emma Chen": 0, "Alex Reynolds": 0, "Victor Marshall": 3, "Savannah Blake": None,
    "Natalie Vale": 1, "Tyler Brooks": 1, "Kimiko Tan": 3, "Jack Weston": 0,
    "Daniel Park": 1, "Madison Rivers": 0, "Marcus Bell": 0, "Jordan Reese": 1,
    "Sienna Monroe": 0, "Taylor Brooks": 3, "Ryan Carter": 1, "Chase Harrison": 1,
}

# Voice per anchor for the test clip (same as shows.py).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
os.environ.setdefault("JSON2VIDEO_API_KEY", "unused")
from shows import SHOWS
VOICE = {s[k]["name"]: s[k]["voice"] for s in SHOWS.values() for k in ("a", "b")}


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def enlarge(url):
    """Composed look -> exact 16:9, 2752x1548, lightly sharpened. Returns JPEG bytes."""
    src = Image.open(io.BytesIO(requests.get(url, timeout=60).content)).convert("RGB")
    w, h = src.size
    th = round(w * 9 / 16)
    if th <= h:
        top = (h - th) // 2
        img = src.crop((0, top, w, top + th))
    else:                                           # wider than tall enough: trim the sides
        tw = round(h * 16 / 9)
        left = (w - tw) // 2
        img = src.crop((left, 0, left + tw, h))
    img = img.resize((2752, 1548), Image.LANCZOS).filter(
        ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()


def upload(jpeg):
    r = requests.post("https://upload.heygen.com/v1/asset", headers={**H, "Content-Type": "image/jpeg"},
                      data=jpeg, timeout=120).json()
    d = r.get("data") or {}
    key = d.get("image_key")
    if not key:
        raise RuntimeError(f"upload: no image_key in {str(r)[:300]}")
    return key


def create_avatar(name, image_key):
    r = requests.post(f"{API}/v2/photo_avatar/avatar_group/create", headers=HJ,
                      json={"name": f"N69 {name} calm", "image_key": image_key}, timeout=60).json()
    if r.get("error"):
        raise RuntimeError(f"create: {r['error']}")
    d = r.get("data") or {}
    gid, pid = d.get("group_id") or d.get("id"), d.get("id")
    if not pid:
        raise RuntimeError(f"create: no id in {str(r)[:300]}")
    # the look must finish processing before it can render
    for _ in range(60):
        looks = (_get(f"{API}/v2/avatar_group/{gid}/avatars").get("data") or {}).get("avatar_list", [])
        look = next((l for l in looks if l.get("id") == pid), None)
        if look and look.get("status") == "completed":
            return pid
        time.sleep(10)
    raise RuntimeError("avatar never finished processing (10 min)")


def frame_of(url):
    d = tempfile.mkdtemp()
    f = os.path.join(d, "clip.mp4")
    open(f, "wb").write(requests.get(url, timeout=120).content)
    subprocess.run(["qlmanage", "-t", "-s", "1920", "-o", d, f], capture_output=True, timeout=120)
    png = f + ".png"
    return Image.open(png).convert("RGB") if os.path.exists(png) else None


def side_bars(im):
    w, h = im.size

    def edge(xs):
        n = 0
        for x in xs:
            if all(min(im.getpixel((x, y))) > 215 for y in range(h // 5, h * 4 // 5, 8)):
                n += 1
            else:
                break
        return n
    return edge(range(w)), edge(range(w - 1, -1, -1))


def _get(url, tries=6):
    """GET with retries: HeyGen sometimes takes 30s+ to answer."""
    for i in range(tries):
        try:
            return requests.get(url, headers=H, timeout=60).json()
        except requests.RequestException as e:
            print(f"    (HeyGen slow to answer, retrying: {str(e)[:80]})")
            time.sleep(10)
    raise RuntimeError(f"HeyGen didn't answer after {tries} tries")


# Test clips use the engine the worker will use: Avatar IV with the calm motion prompt
# (the old v2 animation grins whatever photo it gets).
os.environ.setdefault("HEYGEN_API_KEY", KEY)
from phase3_pipeline import EXPRESSIVENESS, MOTION_PROMPT


def submit_clip(name, pid):
    body = {"type": "avatar", "avatar_id": pid, "script": LINE, "voice_id": VOICE[name],
            "resolution": "1080p", "aspect_ratio": "16:9", "engine": {"type": "avatar_iv"},
            "expressiveness": EXPRESSIVENESS, "motion_prompt": MOTION_PROMPT}
    r = requests.post(f"{API}/v3/videos", headers=HJ, json=body, timeout=90).json()
    vid = (r.get("data") or r).get("video_id")
    if not vid:
        raise RuntimeError(f"render rejected: {str(r)[:300]}")
    return vid


def await_clip(vid):
    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        time.sleep(10)
        d = _get(f"{API}/v3/videos/{vid}")
        d = d.get("data") or d
        if d.get("status") == "completed" and d.get("video_url"):
            return d["video_url"]
        if d.get("status") == "failed":
            raise RuntimeError(f"render failed: {d.get('failure_code')} {d.get('failure_message')}")
    raise RuntimeError("test clip timed out (30 min)")


def one(name, state, done, new=None):
    a = state.get(name) or {}
    pick = PICK.get(name)
    urls = a.get("serious_urls") or []
    if new is not None:                            # a look from new_look.py instead
        nl = load(os.path.join(os.path.dirname(OUT), "new_looks.json"), {}).get(name) or {}
        urls, pick = nl.get("urls") or [], f"new{new}"
        if new >= len(urls):
            print(f"  skip   {name}: no option {new} in new_looks.json (run new_look.py first)")
            return
    if pick is None or (isinstance(pick, int) and pick >= len(urls)):
        print(f"  skip   {name}: no composed look matches their face (needs a new look)")
        return
    if done.get(name, {}).get("ok") and done[name].get("look") == pick:
        print(f"  have   {name}: {done[name]['photo_id']}")
        return
    rec = done.get(name) or {}
    if rec.get("photo_id") and rec.get("look") == pick:
        pid = rec["photo_id"]                      # already uploaded + created: don't duplicate it
        print(f"  {name}: reusing avatar {pid}")
    else:
        print(f"  {name}: enlarging composed look {pick}")
        key = upload(enlarge(urls[new if new is not None else pick]))
        print(f"  {name}: uploaded, creating photo avatar")
        pid = create_avatar(name, key)
        rec = done[name] = {"photo_id": pid, "look": pick, "ok": False}
        json.dump(done, open(OUT, "w"), indent=2)
        print(f"  {name}: avatar {pid} ready")
    vid = rec.get("video_id")
    if vid:
        print(f"  {name}: resuming test clip {vid}")
    else:
        vid = rec["video_id"] = submit_clip(name, pid)
        json.dump(done, open(OUT, "w"), indent=2)
        print(f"  {name}: test clip {vid} submitted (2-10 min)")
    try:
        url = await_clip(vid)
    except RuntimeError as e:
        if "failed" in str(e):
            rec.pop("video_id", None)              # a failed clip gets resubmitted next run
            json.dump(done, open(OUT, "w"), indent=2)
        raise
    im = frame_of(url)
    if im:
        left, right = side_bars(im)
        ok = im.size == (1920, 1080) and max(left, right) < 5
        verdict = f"{im.size[0]}x{im.size[1]}, bars {left}px/{right}px -> {'GOOD' if ok else 'NOT GOOD'}"
    else:
        ok, verdict = False, "couldn't read a frame; open the link and check"
    rec.update(test_url=url, ok=ok, check=verdict)
    done[name] = rec
    json.dump(done, open(OUT, "w"), indent=2)
    print(f"  {name}: {verdict}\n    {url}")


def main():
    state = load(STATE, None)
    if state is None:
        sys.exit(f"No anchors.json at {STATE}")
    done = load(OUT, {})
    new = None
    if "--new" in sys.argv:
        new = int(sys.argv[sys.argv.index("--new") + 1])
    names = list(PICK) if "--all" in sys.argv else [a for a in sys.argv[1:]
                                                     if not a.startswith("--") and not a.isdigit()]
    if not names:
        sys.exit(__doc__)
    for name in names:
        try:
            one(name, state, done, new)
        except Exception as e:
            print(f"  FAILED {name}: {e}")
    good = {n: d["photo_id"] for n, d in done.items() if d.get("ok")}
    if good:
        print("\n# ---- calm photos that passed (send these to Claude / paste into shows.py PHOTOS) ----")
        for n, pid in good.items():
            print(f'    "{n}": "{pid}",')


if __name__ == "__main__":
    main()
