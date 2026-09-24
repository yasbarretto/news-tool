"""
new_look.py — generate a fresh composed look for ONE anchor, keeping their hair.

The composed-look prompt in make_anchors.py names the wardrobe but not the hair, so the
image model picked hair colour itself: all four of Savannah Blake's looks came out
brunette. This uses the same composed prompt plus the anchor's own hair description, in
their existing (trained) avatar group, so the face stays theirs.

  export HEYGEN_API_KEY=...
  python3 new_look.py "Savannah Blake"

Costs ONE look generation. Saves the 4 options to new_looks.json and a review sheet
(new_look_<name>.jpg: original photo first, then options 0-3). Then:
  python3 calm_anchor.py "Savannah Blake" --new 2     # turn option 2 into the calm photo
"""
import os, sys, io, json, time

import requests
from PIL import Image, ImageDraw

KEY = os.environ["HEYGEN_API_KEY"]
H = {"X-Api-Key": KEY, "Content-Type": "application/json"}
API = "https://api.heygen.com/v2"
STATE = os.path.expanduser(os.environ.get("ANCHORS_JSON", "~/Downloads/anchors.json"))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "new_looks.json")

# Hair exactly as each anchor was first generated (make_anchors.py ANCHORS).
HAIR = {
    "Savannah Blake": "long golden blonde hair in soft waves",
    "Madison Rivers": "long platinum blonde hair in loose waves",
    "Jordan Reese": "long honey blonde hair in soft waves",
}


def prompt(name, gender="Woman"):
    """make_anchors.serious_prompt, plus the anchor's hair (the part that drifted)."""
    wardrobe = ("Wearing a tailored dark navy blazer over a white blouse with a high neckline"
                if gender == "Woman" else
                "Wearing a tailored dark navy suit, white shirt and a dark tie")
    return ("Avatar with a solemn, grave expression delivering serious breaking news. "
            "Mouth closed, lips level and relaxed, corners of the mouth straight, "
            "brows slightly drawn together, steady direct eye contact, sombre and businesslike. "
            f"Same person with the same {HAIR[name]}, unchanged hair colour and style. "
            f"{wardrobe}. Seated at the news desk in the same studio, facing the camera, "
            "head and shoulders and upper chest in frame, hands resting on the desk.")


def call(method, path, **kw):
    for i in range(6):
        try:
            body = requests.request(method, API + path, headers=H, timeout=60, **kw).json()
            break
        except (requests.RequestException, ValueError) as e:
            print(f"    (HeyGen slow to answer, retrying: {str(e)[:80]})")
            time.sleep(10)
    else:
        raise RuntimeError(f"{path}: HeyGen didn't answer")
    if body.get("error"):
        raise RuntimeError(f"{path}: {body['error']}")
    return body.get("data") or {}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in HAIR:
        sys.exit(f'usage: python3 new_look.py "NAME"   (one of: {", ".join(HAIR)})')
    name = sys.argv[1]
    a = json.load(open(STATE)).get(name) or {}
    if not a.get("group_id") or not a.get("trained"):
        sys.exit(f"{name} has no trained avatar group in {STATE}")
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}

    gid = (done.get(name) or {}).get("generation_id")
    if gid and not (done[name].get("urls")):
        print(f"{name}: resuming generation {gid}")
    elif gid:
        print(f"{name}: already generated (delete it from new_looks.json to make another)")
    else:
        d = call("POST", "/photo_avatar/look/generate", json={
            "group_id": a["group_id"], "prompt": prompt(name),
            "orientation": "horizontal", "pose": "half_body", "style": "Realistic"})
        gid = d["generation_id"]
        done[name] = {"generation_id": gid}
        json.dump(done, open(OUT, "w"), indent=2)
        print(f"{name}: generating (one credit) · {gid}")

    deadline = time.time() + 30 * 60
    while not done[name].get("urls"):
        if time.time() > deadline:
            sys.exit("still generating after 30 min; run again later to resume")
        time.sleep(8)
        d = call("GET", f"/photo_avatar/generation/{gid}")
        if d.get("status") == "success":
            done[name]["urls"] = d.get("image_url_list") or []
            json.dump(done, open(OUT, "w"), indent=2)
        elif d.get("status") in ("failed", "error"):
            done.pop(name)
            json.dump(done, open(OUT, "w"), indent=2)
            sys.exit(f"generation failed: {d.get('msg')}")

    urls = done[name]["urls"]
    imgs = [Image.open(io.BytesIO(requests.get(u, timeout=60).content)).convert("RGB")
            for u in [a["image_urls"][a.get("pick") or 0]] + urls]
    T = (480, 270)
    sheet = Image.new("RGB", (T[0] * len(imgs), T[1] + 24), "white")
    dr = ImageDraw.Draw(sheet)
    for i, im in enumerate(imgs):
        dr.text((i * T[0] + 6, 6), "original photo" if i == 0 else f"option {i - 1}", fill="black")
        sheet.paste(im.resize(T), (i * T[0], 24))
    out = os.path.join(HERE, f"new_look_{name.replace(' ', '_')}.jpg")
    sheet.save(out, quality=90)
    print(f"\n{len(urls)} options · review sheet: {out}")
    print(f'Pick one, then:  python3 calm_anchor.py "{name}" --new <option number>')


if __name__ == "__main__":
    main()
