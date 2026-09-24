"""
expression_test.py — which HeyGen animation settings keep a calm anchor calm?

Renders the SAME calm photo avatar (from calm_anchors.json) with different voice
settings (see VARIANTS), then saves a contact sheet of 8 frames per clip and
checks each clip for side bars and resolution.

  export HEYGEN_API_KEY=...
  python3 expression_test.py                 # Emma Chen
  python3 expression_test.py "Marcus Bell"

Cost: 4 clips of ~4 seconds of avatar time. Output: expression_test_<name>.jpg next to
this script. Open it: each row is one setting, left to right through the clip.
"""
import os, sys, json, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image, ImageDraw

import calm_anchor as c

# Round 1 showed expression / talking_style are ignored for photo avatars (4 identical
# clips). Round 2: the face seems to follow the AUDIO, so vary only the voice side.
NEWS_LINE = "The city council voted last night to delay the budget until next month."
BIANCA = "0f0524764575497fa3209515a26d1701"   # Bianca - Serious & Composed (Starfish)

# (label, character extras, voice extras, line, voice id or None = the anchor's own voice)
VARIANTS = [
    ("A  own voice, neutral news line", {}, {}, NEWS_LINE, None),
    ("B  own voice + emotion=Serious", {}, {"emotion": "Serious"}, NEWS_LINE, None),
    ("C  own voice + emotion=Broadcaster", {}, {"emotion": "Broadcaster"}, NEWS_LINE, None),
    ("D  Bianca (Serious & Composed voice)", {}, {}, NEWS_LINE, BIANCA),
]

SWIFT = r'''
import AVFoundation
import AppKit
let asset = AVURLAsset(url: URL(fileURLWithPath: CommandLine.arguments[1]))
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero; gen.requestedTimeToleranceAfter = .zero
let dur = CMTimeGetSeconds(asset.duration)
for i in 0..<8 {
  let t = CMTime(seconds: dur * Double(i) / 8.0 + 0.05, preferredTimescale: 600)
  if let cg = try? gen.copyCGImage(at: t, actualTime: nil) {
    let rep = NSBitmapImageRep(cgImage: cg)
    try! rep.representation(using: .jpeg, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[2] + "/f\(i).jpg"))
  }
}
'''


def frames(url):
    """8 frames spread through the clip (macOS: uses AVFoundation via swift)."""
    d = tempfile.mkdtemp()
    mp4, sw = os.path.join(d, "clip.mp4"), os.path.join(d, "frames.swift")
    open(mp4, "wb").write(requests.get(url, timeout=120).content)
    open(sw, "w").write(SWIFT)
    subprocess.run(["swift", sw, mp4, d], capture_output=True, timeout=300)
    return [Image.open(os.path.join(d, f"f{i}.jpg")).convert("RGB")
            for i in range(8) if os.path.exists(os.path.join(d, f"f{i}.jpg"))]


def render(name, pid, extra, voice_extra, line, voice_id):
    body = {"video_inputs": [{"character": {"type": "talking_photo", "talking_photo_id": pid, **extra},
                              "voice": {"type": "text", "input_text": line,
                                        "voice_id": voice_id or c.VOICE[name], **voice_extra}}],
            "aspect_ratio": "16:9", "test": False}
    r = requests.post(f"{c.API}/v2/video/generate", headers=c.HJ, json=body, timeout=90).json()
    vid = (r.get("data") or {}).get("video_id")
    if not vid:
        raise RuntimeError(f"rejected: {str(r)[:300]}")
    return c.await_clip(vid)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Emma Chen"
    rec = c.load(c.OUT, {}).get(name) or {}
    pid = rec.get("photo_id")
    if not pid:
        sys.exit(f"No calm avatar for {name} yet. Run: python3 calm_anchor.py \"{name}\"")
    print(f"{name} · avatar {pid} · rendering {len(VARIANTS)} clips (2-10 min)")

    def one(v):
        label, extra, voice_extra, line, voice_id = v
        try:
            url = render(name, pid, extra, voice_extra, line, voice_id)
            fr = frames(url)
            left, right = c.side_bars(fr[0]) if fr else (-1, -1)
            size = f"{fr[0].size[0]}x{fr[0].size[1]}" if fr else "?"
            return label, url, fr, f"{size}, bars {left}/{right}px"
        except Exception as e:
            return label, None, [], f"FAILED: {str(e)[:120]}"

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
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"expression_test_{name.replace(' ', '_')}_voice.jpg")
    sheet.save(out, quality=88)
    print(f"\nsheet: {out}")


if __name__ == "__main__":
    main()
