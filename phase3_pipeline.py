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


def ingest(limit=15, feeds=None):
    for url in (feeds or FEED_URLS):
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

Return ONLY the corrected script as valid JSON in EXACTLY the same shape and keys as the current script.
Change only what the note asks for; leave everything else intact. Keep numbers spelled out for speech."""
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=2500,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


# One shared background so every presenter looks like the same studio.
# STUDIO_BG can be a hex colour ("#101820") or a public image URL.
# NOTE: only applies to avatars that support background replacement — ones with a
# baked-in scene keep their own background and HeyGen ignores this.
STUDIO_BG = os.environ.get("STUDIO_BG", "")


def _bg():
    if not STUDIO_BG:
        return None
    if STUDIO_BG.startswith("http"):
        return {"type": "image", "url": STUDIO_BG}
    return {"type": "color", "value": STUDIO_BG}


# Per-attempt wait for one HeyGen clip. A normal clip renders in 1-5 min; a stuck one gets
# RESUBMITTED (a fresh submission went through in minutes when the first sat 20+ min).
HEYGEN_TIMEOUT = int(os.environ.get("HEYGEN_ATTEMPT_MIN", "10")) * 60
HEYGEN_ATTEMPTS = int(os.environ.get("HEYGEN_ATTEMPTS", "2"))
# Sending "dimension" alongside "aspect_ratio" changed how HeyGen frames a talking photo
# (video 28 was full-frame without it, cropped with it). Off unless HEYGEN_DIMENSION=on.
USE_DIMENSION = os.environ.get("HEYGEN_DIMENSION", "off").lower() in ("1", "true", "on", "yes")
CLIP_W = int(os.environ.get("HEYGEN_WIDTH", "1920"))
CLIP_H = int(os.environ.get("HEYGEN_HEIGHT", "1080"))
# Photo-avatar animation controls. We were sending none, so HeyGen chose for us —
# "happy" adds a joyful expression on top of the photo, which is why calm stills came
# back beaming. "default" keeps the face as generated; "stable" keeps movement minimal,
# which is what a news read wants.
TP_EXPRESSION = os.environ.get("TALKING_EXPRESSION", "default")     # default | happy
TP_STYLE = os.environ.get("TALKING_STYLE", "")                      # stable | expressive; "" = HeyGen default
TP_SUPERRES = os.environ.get("TALKING_SUPERRES", "off").lower() in ("1", "true", "on", "yes")
# HeyGen re-frames a talking photo around the face, which crops in against the still.
# scale < 1 pulls back; offset nudges the framing. 1.0 is HeyGen's default.
TP_SCALE = os.environ.get("TALKING_SCALE", "")                      # "" = leave it to HeyGen
TP_OFF_X = os.environ.get("TALKING_OFFSET_X", "")
TP_OFF_Y = os.environ.get("TALKING_OFFSET_Y", "")
RENDER_TIMEOUT = int(os.environ.get("RENDER_TIMEOUT_MIN", "30")) * 60
NET = 30  # seconds: per-request network timeout, so a stalled connection can't hang the worker


class WaitTimeout(RuntimeError):
    """Gave up waiting (as opposed to the service reporting a failure)."""


class Aborted(RuntimeError):
    """Another part of the job already failed, so stop waiting on this one."""


def wait_for(label, poll, is_done, is_failed, timeout, every=8, abort=None):
    """Poll until done. Retries transient errors, logs status changes, and GIVES UP at the
    deadline. The worker runs one job at a time, so an unbounded wait freezes everything.
    `abort` (a threading.Event) stops the wait early when the job is already lost."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        if abort is not None and abort.is_set():
            raise Aborted(f"{label} stopped: job already failed")
        time.sleep(every)
        try:
            d = poll() or {}
        except Exception as e:
            print(f"  [{label}] poll error, retrying: {str(e)[:140]}")
            continue
        st = d.get("status")
        if st != last:
            print(f"  [{label}] {st}")
            last = st
        if is_done(d):
            return d
        if is_failed(d):
            raise RuntimeError(f"{label} failed: {str(d)[:400]}")
    raise WaitTimeout(f"{label} timed out after {timeout // 60} min (last status: {last})")


def _heygen_await(vid, label, abort=None):
    d = wait_for(
        label,
        lambda: requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={vid}",
                             headers=HH, timeout=NET).json().get("data"),
        lambda d: d.get("status") == "completed" and d.get("video_url"),
        lambda d: d.get("status") in ("failed", "error"),   # real failure
        HEYGEN_TIMEOUT, abort=abort)
    return d["video_url"]   # status calls return a FRESH presigned url, so resuming never serves an expired one


def heygen_avatar(text, avatar_id=None, voice_id=None, photo_id=None, label="heygen", abort=None,
                  resume_vid=None, on_submit=None):
    """Render one avatar clip.

    resume_vid: a clip already submitted (and paid for) by an earlier attempt of this job.
                We pick it back up instead of submitting a duplicate.
    on_submit:  called with the new video id the moment it's submitted, so the job can
                record it before waiting. With it, a slow clip is never resubmitted here;
                the job requeues and resumes it instead.
    """
    # photo_id = a generated photo-avatar look (talking_photo); otherwise a stock avatar
    if photo_id:
        # Baseline = what rendered video 28 correctly: the look, the expression, nothing else.
        # Everything below is opt-in, because each one changed HeyGen's framing or sharpness.
        character = {"type": "talking_photo", "talking_photo_id": photo_id,
                     "expression": TP_EXPRESSION}
        if TP_STYLE:
            character["talking_style"] = TP_STYLE
        if TP_SUPERRES:
            character["super_resolution"] = True
        if TP_SCALE:
            character["scale"] = float(TP_SCALE)
        if TP_OFF_X or TP_OFF_Y:
            character["offset"] = {"x": float(TP_OFF_X or 0), "y": float(TP_OFF_Y or 0)}
    else:
        character = {"type": "avatar", "avatar_id": avatar_id or AVATAR_ID, "avatar_style": "normal"}
    scene = {
        "character": character,
        "voice": {"type": "text", "input_text": text, "voice_id": voice_id or VOICE_ID},
    }
    bg = _bg()
    if bg:
        scene["background"] = bg
    payload = {"video_inputs": [scene], "aspect_ratio": "16:9", "test": TEST}
    if USE_DIMENSION:
        payload["dimension"] = {"width": CLIP_W, "height": CLIP_H}

    if resume_vid:
        print(f"  [{label}] resuming {resume_vid}")
        try:
            return _heygen_await(resume_vid, label, abort)
        except (WaitTimeout, Aborted):
            raise                                   # still running: the job requeues and resumes again
        except RuntimeError as e:
            print(f"  [{label}] earlier submission failed, submitting fresh: {str(e)[:120]}")

    attempts = 1 if on_submit else HEYGEN_ATTEMPTS
    for attempt in range(1, attempts + 1):
        if abort is not None and abort.is_set():  # never submit (and pay) for a lost job
            raise Aborted(f"{label} not submitted: job already failed")
        resp = requests.post("https://api.heygen.com/v2/video/generate", headers=HH, json=payload, timeout=NET)
        body = resp.json()
        if "resolution" in json.dumps(body).lower() and payload.get("dimension", {}).get("width", 0) > 1280:
            print(f"  [{label}] 1080p not allowed on this plan, falling back to 720p")
            payload["dimension"] = {"width": 1280, "height": 720}
            resp = requests.post("https://api.heygen.com/v2/video/generate", headers=HH, json=payload, timeout=NET)
            body = resp.json()
        if not body.get("data") or not body["data"].get("video_id"):
            # RuntimeError, not SystemExit: the worker catches Exception, so one bad
            # HeyGen response fails one job instead of killing the whole worker loop.
            raise RuntimeError(f"[heygen error] HTTP {resp.status_code}: {json.dumps(body)[:600]}")
        vid = body["data"]["video_id"]
        print(f"  [{label}] submitted {vid}" + (f" (attempt {attempt})" if attempt > 1 else ""))
        if on_submit:
            on_submit(vid)
        try:
            return _heygen_await(vid, label, abort)
        except WaitTimeout as e:
            if attempt == attempts:
                raise WaitTimeout(f"{e} · gave up after {attempt} attempt{'s' if attempt > 1 else ''}")
            print(f"  [{label}] stuck at HeyGen, resubmitting")


def heygen_tts(text, voice_id=None):
    r = requests.post("https://api.heygen.com/v3/voices/speech", headers=HH,
                      json={"text": text, "voice_id": voice_id or VOICE_ID}, timeout=NET).json()
    d = r.get("data", {})
    if not d.get("audio_url"):
        raise RuntimeError(r)
    return d["audio_url"], d.get("duration", 5)


SAFE_PROMPT = "abstract futuristic technology background, glowing blue digital network, cinematic, no people, no text"

def render_movie(movie, max_retries=3):
    import re
    for attempt in range(max_retries):
        resp = requests.post("https://api.json2video.com/v2/movies", headers=JH, json=movie, timeout=NET).json()
        proj = resp.get("project")
        if not proj:
            raise RuntimeError(f"json2video rejected the movie: {str(resp)[:400]}")
        m = wait_for(
            "json2video",
            lambda: requests.get(f"https://api.json2video.com/v2/movies?project={proj}",
                                 headers=JH, timeout=NET).json().get("movie"),
            lambda m: m.get("status") in ("done", "error"),   # errors handled below (retry logic)
            lambda m: False,
            RENDER_TIMEOUT, every=10)
        if m.get("status") == "done":
            return m["url"]
        msg = m.get("message", "")
        hit = re.search(r"Scene #(\d+)", msg)
        if hit and attempt < max_retries - 1:
            idx = int(hit.group(1)) - 1
            if 0 <= idx < len(movie["scenes"]):
                for el in movie["scenes"][idx]["elements"]:
                    if el.get("type") == "image" and el.get("model"):
                        el["prompt"] = SAFE_PROMPT
                print(f"  [retry] scene #{idx + 1} image flagged -> safe fallback, re-rendering")
                continue  # re-render the patched movie
        raise RuntimeError(msg)
    raise RuntimeError("render failed after retries")


def story_scene(story, voice_id=None):
    """One story: multiple b-roll images cycling under the narration, with a lower-third headline.
    LEAD/TAIL add silence so voices don't overlap across the slide transitions."""
    LEAD, TAIL = 0.4, 0.5
    audio_url, dur = heygen_tts(story["narration"], voice_id)
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
                      "settings": {
                          "style": "classic",
                          "max-words-per-line": 4,
                          "position": "bottom-center",
                          "line-color": "#FFFFFF",
                          "word-color": "#FFD34D",      # highlighted spoken word
                          "outline-color": "#000000",   # hard edge — the real legibility win
                          "outline-width": 5,
                          "shadow-color": "#000000",    # soft drop shadow under that
                          "shadow-offset": 4,
                      }}],
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
