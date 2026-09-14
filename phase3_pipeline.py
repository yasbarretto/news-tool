"""
Phase 3 — Full pipeline + news-style polish
============================================
Real news -> Claude picks stories (headline + multi b-roll + narration)
   -> HeyGen Annie avatar (intro/outro) + Annie TTS (narration)
   -> flux b-roll (multiple images per story, cycling)
   -> JSON2Video assembles with lower-third headlines + fade transitions + captions
   -> finished video, Annie's voice throughout.

SETUP
-----
  pip install feedparser anthropic requests
  export ANTHROPIC_API_KEY=sk-ant-...
  export HEYGEN_API_KEY=...
  export HEYGEN_AVATAR_ID=Annie_Casual_Standing_Front_2_public
  export HEYGEN_VOICE_ID=330290724a1b470fb63153f34d4c0183
  export HEYGEN_TEST=true
  export JSON2VIDEO_API_KEY=...
  export NUM_STORIES=3
  python phase3_pipeline.py
"""
import os, time, json, requests, feedparser, anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
HEY_KEY = os.environ["HEYGEN_API_KEY"]
J2V_KEY = os.environ["JSON2VIDEO_API_KEY"]
AVATAR_ID = os.environ.get("HEYGEN_AVATAR_ID", "Annie_Casual_Standing_Front_2_public")
VOICE_ID  = os.environ.get("HEYGEN_VOICE_ID", "330290724a1b470fb63153f34d4c0183")
TEST = os.environ.get("HEYGEN_TEST", "true").lower() == "true"
NUM_STORIES = int(os.environ.get("NUM_STORIES", "3"))

HH = {"X-Api-Key": HEY_KEY, "Content-Type": "application/json"}
JH = {"x-api-key": J2V_KEY, "Content-Type": "application/json"}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

FEED_URLS = [
    "https://news.google.com/rss/search?q=technology+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://feeds.arstechnica.com/arstechnica/index",
]


def ingest(limit=15):
    for url in FEED_URLS:
        try:
            resp = requests.get(url, headers=UA, timeout=20)
            items = [{"title": e.title, "summary": getattr(e, "summary", "")[:300],
                      "link": getattr(e, "link", "")}
                     for e in feedparser.parse(resp.content).entries[:limit]]
            if items:
                print(f"[ingest] {len(items)} headlines from {url.split('?')[0]}")
                return items
        except Exception as e:
            print(f"[ingest] error {url.split('?')[0]}: {e}")
    return []


def make_script(headlines, n, covered=None):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""You are a news producer for a short tech-news video hosted by an AI anchor named Annie.

Today's candidate headlines:
{json.dumps(headlines, indent=2)}

ALREADY COVERED — do NOT pick these stories again (we have published them recently):
{json.dumps(covered or [], indent=2)}

Pick the {n} MOST newsworthy tech stories that are NOT already covered above. Return ONLY valid JSON (no markdown) in exactly this shape:
{{
  "intro": "<Annie's spoken opening: one sentence teasing the {n} stories by name>",
  "stories": [
    {{
      "headline": "<SHORT on-screen headline, Title Case, max 6 words>",
      "narration": "<1-3 sentences Annie speaks for this story>",
      "source_title": "<the EXACT headline from the candidate list this story came from>",
      "source_link": "<that item's link, copied exactly>",
      "broll_prompts": ["<photorealistic editorial news image>", "..."]
    }}
  ],
  "outro": "<Annie's spoken sign-off: one short sentence>"
}}

Rules:
- source_title and source_link MUST be copied verbatim from the candidate item you used, so a reviewer can verify the claims.
- Exactly {n} stories, all genuinely different from each other AND from the already-covered list. If a story is the same event as a covered one, skip it and choose another.
- broll_prompts: give ONE image prompt per roughly 4-5 seconds of narration (so a short story gets 1-2, a longer one 3-4).
- Each broll_prompt must SPECIFICALLY depict THIS story's subject — the actual technology, product, company setting, place, or concept discussed (e.g. a rocket on a launch pad for a SpaceX story; rows of servers for a data-center story; a smartphone showing an app for a software story). Make them vivid, photorealistic, editorial.
- Anonymous, unnamed people ARE encouraged for a real-news feel — e.g. "a software engineer at a terminal", "a crowd of commuters looking at phones", "hands typing on a laptop", "analysts on a trading floor". Depict them generically.
- AVOID in b-roll prompts (these get rejected or look fake): recognizable REAL NAMED public figures (do not name or describe a specific real person's likeness), brand logos or readable text, and violent / weapon / protest / politically charged scenes.
- ACCURACY: spell company and product names exactly as the company does. Watch homographs — "OpenAI" (the company, one word) is NOT the same as "open AI" / "open-weight AI" (open-source models). Use whichever the story actually means. Same care for names like "DeepMind", "xAI", "Hugging Face", etc.
- headline: punchy, like a TV chyron — 3 to 5 words MAX, short and tight (e.g. "SPACEX PRICES RECORD IPO"). NOT a full sentence. Keep it well under ~28 characters.
- Conversational anchor tone. Spell out numbers/tickers as spoken ("a hundred and thirty-five dollars", "S P C X")."""
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=2500,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    script = json.loads(text[text.find("{"):text.rfind("}") + 1])
    print(f"[script] intro + {len(script['stories'])} stories + outro")
    return script


# --- unit prices (update here if vendor pricing changes) ---
PRICE = {
    "avatar_per_min": 1.00,    # HeyGen Avatar III
    "tts_per_min":    0.04,    # HeyGen TTS
    "image_each":     0.04,    # flux-pro via JSON2Video
    "render_per_sec": 0.0069,  # JSON2Video ($49.95 / 7200 credits)
    "llm_flat":       0.12,    # Claude: triage + script + auto-QA
}


def estimate_cost(script, avatar_secs, narration_secs, n_images, total_secs, fresh=True):
    """Estimate what this video actually cost, from what was really generated."""
    c = (avatar_secs / 60.0) * PRICE["avatar_per_min"]
    c += (narration_secs / 60.0) * PRICE["tts_per_min"]
    c += n_images * PRICE["image_each"]
    c += total_secs * PRICE["render_per_sec"]
    c += PRICE["llm_flat"] if fresh else PRICE["llm_flat"] * 0.4   # rework skips ingest+scripting
    return round(c, 4)


def revise_script(script, note):
    """Apply a reviewer's rejection note to an existing script."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""A reviewer rejected this news video script. Fix it according to their note.

CURRENT SCRIPT:
{json.dumps(script, indent=2)}

REVIEWER'S NOTE (this is what must be fixed):
{note}

Return ONLY the corrected script as valid JSON in the SAME shape (intro, stories[headline,narration,broll_prompts], outro).
Change only what the note asks for; leave everything else intact. Keep numbers spelled out for speech."""
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=2500,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


def heygen_avatar(text, avatar_id=None):
    payload = {"video_inputs": [{
        "character": {"type": "avatar", "avatar_id": avatar_id or AVATAR_ID, "avatar_style": "normal"},
        "voice": {"type": "text", "input_text": text, "voice_id": VOICE_ID}}],
        "aspect_ratio": "16:9", "test": TEST}
    resp = requests.post("https://api.heygen.com/v2/video/generate", headers=HH, json=payload)
    body = resp.json()
    if not body.get("data") or not body["data"].get("video_id"):
        raise SystemExit(f"[heygen error] HTTP {resp.status_code}: {json.dumps(body)[:600]}")
    vid = body["data"]["video_id"]
    while True:
        time.sleep(8)
        d = requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={vid}", headers=HH).json()["data"]
        if d.get("status") == "completed":
            return d["video_url"]
        if d.get("status") in ("failed", "error"):
            raise RuntimeError(d)


def heygen_tts(text):
    r = requests.post("https://api.heygen.com/v3/voices/speech", headers=HH,
                      json={"text": text, "voice_id": VOICE_ID}).json()
    d = r.get("data", {})
    if not d.get("audio_url"):
        raise RuntimeError(r)
    return d["audio_url"], d.get("duration", 5)


SAFE_PROMPT = "abstract futuristic technology background, glowing blue digital network, cinematic, no people, no text"

def render_movie(movie, max_retries=3):
    import re
    for attempt in range(max_retries):
        proj = requests.post("https://api.json2video.com/v2/movies", headers=JH, json=movie).json()["project"]
        while True:
            time.sleep(10)
            m = requests.get(f"https://api.json2video.com/v2/movies?project={proj}", headers=JH).json()["movie"]
            print("  json2video:", m.get("status"))
            if m.get("status") == "done":
                return m["url"]
            if m.get("status") == "error":
                msg = m.get("message", "")
                hit = re.search(r"Scene #(\d+)", msg)
                if hit and attempt < max_retries - 1:
                    idx = int(hit.group(1)) - 1
                    if 0 <= idx < len(movie["scenes"]):
                        for el in movie["scenes"][idx]["elements"]:
                            if el.get("type") == "image" and el.get("model"):
                                el["prompt"] = SAFE_PROMPT
                        print(f"  [retry] scene #{idx + 1} image flagged -> safe fallback, re-rendering")
                        break  # re-render the patched movie
                raise RuntimeError(msg)
    raise RuntimeError("render failed after retries")


def story_scene(story):
    """One story: multiple b-roll images cycling under the narration, with a lower-third headline.
    LEAD/TAIL add silence so voices don't overlap across the slide transitions."""
    LEAD, TAIL = 0.4, 0.5
    audio_url, dur = heygen_tts(story["narration"])
    prompts = story.get("broll_prompts") or [story.get("broll_prompt", "")]
    n = max(1, len(prompts))
    scene_dur = round(LEAD + dur + TAIL, 2)
    seg = scene_dur / n

    els = []
    for i, p in enumerate(prompts):
        els.append({"type": "image", "model": "flux-pro", "prompt": p, "resize": "cover",
                    "start": round(i * seg, 2), "duration": round(seg + 0.35, 2)})
    els.append({"type": "audio", "src": audio_url, "start": LEAD})
    els.append({
        "type": "text", "text": story.get("headline", "").upper(),
        "position": "custom", "x": "4%", "y": "64%", "width": "92%", "height": 90,
        "duration": -2, "fade-in": 0.3, "fade-out": 0.3,
        "settings": {
            "font-family": "Oswald", "font-size": "40px", "font-weight": "700",
            "color": "#FFFFFF", "background-color": "#C8102E",
            "vertical-position": "center", "horizontal-position": "left",
            "padding-left": "40px", "padding-right": "40px",
            "padding-top": "12px", "padding-bottom": "12px",
        },
    })
    return {"duration": scene_dur,
            "transition": {"style": "slideleft", "duration": 0.5},
            "elements": els}


def build_movie(intro_url, outro_url, story_scenes):
    return {
        "resolution": "full-hd", "quality": "high",
        "scenes": [{"comment": "intro", "transition": {"style": "slideleft", "duration": 0.5},
                    "elements": [{"type": "video", "src": intro_url, "extra-time": 0.5}]}]
                  + story_scenes
                  + [{"comment": "outro", "transition": {"style": "slideleft", "duration": 0.5},
                      "elements": [{"type": "video", "src": outro_url}]}],
        "elements": [{"type": "subtitles", "language": "auto",
                      "settings": {"style": "classic", "max-words-per-line": 4, "position": "bottom-center"}}],
    }


if __name__ == "__main__":
    headlines = ingest()
    if not headlines:
        raise SystemExit("No headlines from any feed — fix feeds before rendering (nothing spent).")

    script = make_script(headlines, NUM_STORIES)

    print("[heygen] Annie intro...")
    intro_url = heygen_avatar(script["intro"])
    print("[heygen] Annie outro...")
    outro_url = heygen_avatar(script["outro"])

    print("[heygen] story narration + b-roll...")
    story_scenes = [story_scene(s) for s in script["stories"]]

    print("[assemble] rendering final video...")
    url = render_movie(build_movie(intro_url, outro_url, story_scenes))
    print("\n=== DONE ===")
    print("Finished video:", url)

    # Phase 4: auto-QA + save to the dashboard database (only if DATABASE_URL is set)
    if os.environ.get("DATABASE_URL"):
        from qa import run_auto_qa
        import db
        print("[qa] running auto-QA...")
        qa = run_auto_qa(script, headlines)
        print("[qa]", qa)
        vid = db.insert_video(
            headline=script["stories"][0]["headline"],
            source="News69 pipeline",
            duration=f"~{NUM_STORIES * 30 + 20}s",
            video_url=url,
            qa=qa,
        )
        print(f"[db] saved as video #{vid} - now in the QA queue")
    else:
        print("(no DATABASE_URL set - skipped DB save; set it to push into the dashboard)")
