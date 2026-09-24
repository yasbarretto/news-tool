"""
coanchor.py — co-anchored News Channel 69 episodes.

Flow
  1. Claude writes the episode as dialogue for two named anchors.
  2. Every on-camera line renders as its own HeyGen clip, in parallel.
  3. Each story's voiceover uses the reading anchor's voice.
  4. JSON2Video assembles it with the graphics layer from graphics.py.

Running order
  open A (title card) -> open B (B's lower third)
  -> per story: anchor lead (lower third on first solo appearance) -> b-roll (chyron)
  -> close A -> close B (sign-off / AI disclosure)

Stories alternate A, B, A... regardless of what the model returns.
"""
import os, json, re
import threading, hashlib, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

import graphics as g
from phase3_pipeline import (ANTHROPIC_API_KEY, heygen_submit, heygen_await, heygen_tts,
                             Aborted, WaitTimeout, HEYGEN_ENGINE)

CONCURRENCY = int(os.environ.get("HEYGEN_CONCURRENCY", "3"))
# A recorded clip older than this is presumed dead at HeyGen and submitted fresh.
RESUME_MAX_MIN = int(os.environ.get("RESUME_MAX_MIN", "45"))
DISSOLVE = float(os.environ.get("DISSOLVE_SEC", "0.3"))  # crossfade between scenes; 0 = hard cuts
CAPTIONS = os.environ.get("CAPTIONS", "off").lower() in ("on", "1", "true")  # broadcast has no burned-in captions
CAPTION_POS = os.environ.get("CAPTION_POS", "custom")   # set to mid-bottom-center to fall back
CAPTION_X = int(os.environ.get("CAPTION_X", "960"))   # custom x is the CENTER of the line (1920/2)
CAPTION_Y = int(os.environ.get("CAPTION_Y", "640"))
WPS = 2.5  # spoken words per second, for estimates
ANCHOR_ZOOM = float(os.environ.get("ANCHOR_ZOOM", "1.0"))  # 1.08 crops HeyGen side bars if they show; 1.0 = off


# ------------------------------------------------------------------ voice preflight
# Probe each voice with a one-word TTS call instead of reading HeyGen's voice list:
# the list endpoint paginates in ways we can't rely on, and a truncated list would
# wrongly reject good voices. A probe is definitive and costs a fraction of a cent.
_VOICE_OK = {}   # voice_id -> True/False, cached for the life of the worker


def _voice_works(voice_id):
    if voice_id not in _VOICE_OK:
        try:
            heygen_tts("Checking.", voice_id)
            _VOICE_OK[voice_id] = True
        except Exception as e:
            print(f"  [voices] {voice_id} failed narration TTS: {str(e)[:160]}")
            _VOICE_OK[voice_id] = False
    return _VOICE_OK[voice_id]


def check_voices(show):
    """Fail fast, before any paid render, if an anchor's voice can't do narration TTS."""
    bad = [f"{show[k]['name']} ({show[k]['voice']})" for k in ("a", "b") if not _voice_works(show[k]["voice"])]
    if bad:
        raise RuntimeError(f"{show['title']}: voice not supported for narration TTS: {', '.join(bad)}. "
                           f"Pick a Starfish voice for this anchor in shows.py.")


# ------------------------------------------------------------------ script
def day_part(show):
    """(greeting word, 'today'/'tonight') for the show's slot. Slots are local airtimes
    in shows.py: 07:00 and 09:00 are mornings, 12:00 and 15:00 afternoons, 17:00 on evenings."""
    try:
        hour = int(str(show.get("slot", "")).split(":")[0])
    except ValueError:
        return None, None
    if 4 <= hour < 12:
        return "morning", "today"
    if 12 <= hour < 17:
        return "afternoon", "today"
    return "evening", "tonight"


_GREETING = re.compile(r"\b(good)(\s+)(morning|afternoon|evening)\b", re.I)


def fix_greetings(script, show):
    """Safety net: any 'Good morning/afternoon/evening' in a spoken line matches the slot.
    'Good night' (a sign-off) is left alone."""
    part, _ = day_part(show)
    if not part:
        return script

    def fix(text):
        if not isinstance(text, str):
            return text
        def same_case(word):
            if word.isupper():
                return part.upper()
            return part.capitalize() if word[0].isupper() else part
        return _GREETING.sub(lambda m: m.group(1) + m.group(2) + same_case(m.group(3)), text)

    for side in ("open", "close"):
        for k in ("a", "b"):
            if isinstance(script.get(side), dict):
                script[side][k] = fix(script[side].get(k))
    for st in script.get("stories", []):
        for k in ("lead", "narration"):
            st[k] = fix(st.get(k))
    return script


def make_coanchor_script(headlines, show, n, covered=None):
    a, b = show["a"]["name"], show["b"]["name"]
    part, when = day_part(show)
    fa, fb = a.split()[0], b.split()[0]
    prompt = f"""You are the producer of "{show['title']}" on News Channel 69, a short news show covering {show['topic']}.
It is co-anchored by {a} (anchor A, opens the show) and {b} (anchor B). Write the episode as dialogue.
The show airs at {show.get('slot', '')} local time, in the {part or 'day'}.

Today's candidate headlines:
{json.dumps(headlines, indent=2)}

ALREADY COVERED — do NOT pick these again:
{json.dumps(covered or [], indent=2)}

Return ONLY valid JSON (no markdown) in exactly this shape:
{{
  "open":  {{"a": "<{fa}'s greeting: welcome to {show['title']}, then 'I'm {a}.' One or two short sentences.>",
             "b": "<{fb}: 'And I'm {b}.' then tease the stories in one short sentence.>"}},
  "stories": [
    {{
      "anchor": "a",
      "category": "<ONE word desk label, e.g. TECH, MARKETS, WORLD, SPORTS, POLITICS>",
      "tone": "<somber if the story involves death, tragedy, disaster, violence, serious illness or loss; otherwise neutral>",
      "headline": "<chyron: 3 to 5 words, under 28 characters>",
      "lead": "<the anchor ON CAMERA introducing the story: ONE sentence>",
      "narration": "<voiceover over b-roll: 1 to 3 sentences with the facts>",
      "source_title": "<EXACT headline from the candidate list>",
      "source_link": "<that item's link, copied exactly>",
      "broll_prompts": ["<photorealistic editorial news image>", "..."]
    }}
  ],
  "close": {{"a": "<{fa}: short wrap-up line naming the show>",
             "b": "<{fb}: sign-off that ends with the tagline '{show['tagline']}'>"}}
}}

Rules:
- Exactly {n} stories, all different from each other and from the already-covered list.
- Stories alternate anchors: story 1 is "a", story 2 is "b", story 3 is "a", and so on.
- When the reading anchor changes, the incoming anchor MAY open their lead with a brief acknowledgement of the other by first name (e.g. "Thanks, {fa}."). Use it once or twice per episode, not on every story.
- source_title and source_link MUST be copied verbatim so a reviewer can verify claims.
- broll_prompts: one per roughly 4 to 5 seconds of narration. Each must depict THIS story's actual subject. Anonymous people are fine. NO real named people, NO logos or readable text, NO violent or politically charged scenes.
- Spell company and product names exactly as the company does ("OpenAI" the company is not "open AI").
- Spell out numbers and tickers as spoken ("a hundred and thirty-five dollars").
- Broadcast tone: confident, warm, tight. No filler.
- Time of day: this is a {part or 'daytime'} show. Any greeting is "Good {part or 'day'}", and any reference to the broadcast itself says "{when or 'today'}" (e.g. "here's what we're following {when or 'today'}"). Never greet with a different time of day, and never say "tonight" in a morning or afternoon show.
- A somber story is read plainly and respectfully. No wordplay, no upbeat phrasing, and the anchor does not thank or hand off cheerfully around it."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=3000,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(x.text for x in msg.content if x.type == "text")
    script = json.loads(text[text.find("{"):text.rfind("}") + 1])
    return normalize(script, show)


def normalize(script, show=None):
    """Enforce the running order the render relies on (and, given the show, the greeting)."""
    for i, st in enumerate(script.get("stories", [])):
        st["anchor"] = "a" if i % 2 == 0 else "b"
        st.setdefault("category", "News")
        if st.get("tone") not in ("somber", "neutral"):
            st["tone"] = "neutral"
    script.setdefault("open", {}).setdefault("a", "")
    script["open"].setdefault("b", "")
    script.setdefault("close", {}).setdefault("a", "")
    script["close"].setdefault("b", "")
    script["format"] = "coanchor"
    if show:
        fix_greetings(script, show)
    return script


def is_coanchor(script):
    return isinstance(script, dict) and (script.get("format") == "coanchor" or "open" in script)


# ------------------------------------------------------------------ render
def _lines(script):
    """Every on-camera line, in running order: (key, anchor, text, serious).

    `serious` picks the anchor's composed look instead of their warm one: on a somber
    story's lead, and across the whole episode when it contains one (nobody opens a
    bulletin beaming when someone has died)."""
    somber_episode = any(st.get("tone") == "somber" for st in script.get("stories", []))
    out = [("open_a", "a", script["open"]["a"], somber_episode),
           ("open_b", "b", script["open"]["b"], somber_episode)]
    for i, st in enumerate(script["stories"]):
        out.append((f"lead_{i}", st["anchor"], st["lead"], st.get("tone") == "somber"))
    out += [("close_a", "a", script["close"]["a"], somber_episode),
            ("close_b", "b", script["close"]["b"], somber_episode)]
    return [x for x in out if (x[2] or "").strip()]


def look_for(anc, serious):
    """The photo-avatar look to use. Falls back to the warm look if no composed one exists."""
    return (anc.get("photo_serious") or anc.get("photo")) if serious else anc.get("photo")


def public(script):
    """The script without our bookkeeping keys (_clips, _retries, _headlines),
    for anything that sends it to a model."""
    return {k: v for k, v in script.items() if not str(k).startswith("_")}


def _sig(text, anc, photo=None):
    """Identity of a clip: same words, same face (and expression), same voice = same clip."""
    from phase3_pipeline import HEYGEN_ENGINE   # a clip from another engine is a different clip
    raw = "|".join([str(text), str(anc.get("avatar")), str(photo), str(anc.get("voice"))]
                   + ([HEYGEN_ENGINE] if HEYGEN_ENGINE and photo else []))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def render_clips(script, show, ledger=None, save=None):
    """Render all on-camera lines. Returns {key: video_url}.

    Two phases, so one slow clip never holds up the others:
      1. SUBMIT every clip to HeyGen up front (or pick up its id from an earlier attempt).
      2. WAIT on all of them at once.
    HeyGen takes anywhere from 2 to 20+ minutes per clip. Submitting in waves of
    HEYGEN_CONCURRENCY meant the last clips weren't even sent until the first ones finished.

    ledger (dict, persisted with the job via save()) records every clip's HeyGen video id
    the moment it's submitted, and marks it done the moment it finishes. On a retry of the
    same job:
      - a clip whose words/face/voice/engine are unchanged is RESUMED by its id: finished
        clips come straight back, running ones keep going. Nothing is paid for twice.
      - anything changed, never submitted, or older than RESUME_MAX_MIN is submitted fresh.
    """
    lines = _lines(script)
    ledger = ledger if ledger is not None else {}
    lock = threading.Lock()
    abort = threading.Event()

    def record(key, **fields):
        with lock:
            ledger.setdefault(key, {}).update(fields)
            if save:
                save()

    def spec(item):
        key, who, text, serious = item
        anc = show[who]
        photo = look_for(anc, serious)
        label = f"clip {key} · {anc['name']}" + (" · composed" if serious else "")
        return anc, photo, _sig(text, anc, photo), label

    def submit(item):
        key, who, text, serious = item
        if abort.is_set():                  # job already lost: don't submit (don't pay)
            raise Aborted(f"clip {key} skipped: job already failed")
        anc, photo, sig, label = spec(item)
        vid, v3 = heygen_submit(text, anc["avatar"], anc["voice"], photo, label=label)
        record(key, sig=sig, vid=vid, v3=v3, at=time.time(), done=False)
        return vid, v3

    def start(item):
        """Phase 1: an id to wait on, and whether it came from an earlier attempt."""
        key = item[0]
        _, photo, sig, label = spec(item)
        prev = ledger.get(key) or {}
        fresh_enough = (time.time() - prev.get("at", 0)) < RESUME_MAX_MIN * 60
        if prev.get("vid") and prev.get("sig") == sig and (prev.get("done") or fresh_enough):
            print(f"  [{label}] resuming {prev['vid']}")
            # records from before this change have no "v3": the sig already pins the engine
            v3 = prev["v3"] if "v3" in prev else (bool(photo) and HEYGEN_ENGINE == "avatar_iv")
            return item, prev["vid"], v3, True
        vid, v3 = submit(item)
        return item, vid, v3, False

    def finish(item, vid, v3, resumed):
        """Phase 2: wait. A resumed clip that failed at HeyGen gets one fresh submission."""
        key = item[0]
        label = spec(item)[3]
        try:
            url = heygen_await(vid, label, abort, v3)
        except (WaitTimeout, Aborted):
            raise                           # still running: the job requeues and resumes it
        except RuntimeError as e:
            if not resumed:
                raise
            print(f"  [{label}] earlier submission failed, submitting fresh: {str(e)[:120]}")
            vid, v3 = submit(item)
            url = heygen_await(vid, label, abort, v3)
        record(key, done=True)              # recorded now, not at the end: a requeue keeps it
        return key, url

    def run(pool_size, fn, args):
        pool = ThreadPoolExecutor(max_workers=pool_size)
        futures = [pool.submit(fn, *a) for a in args]
        out = []
        try:
            for f in as_completed(futures):
                out.append(f.result())      # raises if that one failed
        except Exception:
            abort.set()                     # stop in-flight waits
            pool.shutdown(wait=True, cancel_futures=True)
            raise
        pool.shutdown(wait=True)
        return out

    started = run(CONCURRENCY, start, [(x,) for x in lines])
    return dict(run(max(1, len(started)), finish, started))


def spoken_words(script):
    return sum(len(str(t).split()) for _, _, t, _ in _lines(script))


# ------------------------------------------------------------------ assemble
class _Ticker:
    """Rotates through the day's headlines, one per ~6s, carried scene to scene."""
    EVERY = 6.0

    def __init__(self, items):
        self.items = [i for i in items if i][:8] or ["News Channel 69"]
        self.i = 0

    def _next(self):
        h = self.items[self.i % len(self.items)]
        self.i += 1
        return h

    def for_scene(self, duration=None):
        els = [g.ticker_band()]
        if not duration:                       # anchor clip: length unknown until render
            els.append(g.ticker_item(self._next()))
            return els
        n = max(1, round(duration / self.EVERY))
        seg = duration / n
        for k in range(n):
            last = k == n - 1
            els.append(g.ticker_item(self._next(), start=round(k * seg, 2),
                                     duration=-2 if last else round(seg, 2)))  # last one runs to scene end
        return els


def _anchor_video(url):
    """Anchor clip, scaled past the canvas edges by ANCHOR_ZOOM.

    HeyGen returns photo-avatar clips with light bars ~2.6% wide on each side (33px of
    1280). They're pixels in the clip, so resize:"cover" can't remove them; scaling the clip
    past the frame pushes them off-canvas. Needs >= 1.055; 1.0 turns it off."""
    if ANCHOR_ZOOM <= 1.0:
        return {"type": "video", "src": url, "resize": "cover"}
    w, h = round(1920 * ANCHOR_ZOOM), round(1080 * ANCHOR_ZOOM)
    return {"type": "video", "src": url, "resize": "cover", "position": "custom",
            "x": -((w - 1920) // 2), "y": -((h - 1080) // 2), "width": w, "height": h}


def _anchor_scene(url, overlays, tick):
    # no extra-time: once the clip ends that tail renders black, which showed as a flash at every cut
    return {"elements": [_anchor_video(url)] + overlays + tick.for_scene()}


def voice_narration(script, show):
    """TTS every story's voiceover. Cheap and fast, so it runs BEFORE the anchor clips:
    a voice problem fails in seconds instead of after minutes of avatar renders."""
    return [heygen_tts(st["narration"], show[st["anchor"]]["voice"]) for st in script["stories"]]


def _broll_scene(story, narration, tick=None):
    LEAD, TAIL = 0.4, 0.5
    audio_url, dur = narration
    prompts = story.get("broll_prompts") or [story.get("headline", "news")]
    n = max(1, len(prompts))
    scene_dur = round(LEAD + dur + TAIL, 2)
    seg = scene_dur / n
    els = [{"type": "image", "model": "flux-pro", "prompt": p, "resize": "cover",
            "start": round(i * seg, 2), "duration": round(seg + 0.35, 2)} for i, p in enumerate(prompts)]
    els.append({"type": "audio", "src": audio_url, "start": LEAD})
    els.append(g.chyron(story.get("category"), story.get("headline")))
    if tick:
        els += tick.for_scene(scene_dur)
    return {"duration": scene_dur, "elements": els}, dur, n


def preflight_movie(script, show, ticker_items):
    """Build the full movie with placeholder clips and audio, and validate it BEFORE any
    paid render. Graphics size doesn't depend on the clip URLs, so this catches payload
    problems (like an oversized ticker) for free."""
    fake_clips = {line[0]: "https://preflight/clip.mp4" for line in _lines(script)}
    fake_narr = [("https://preflight/audio.mp3", 8.0) for _ in script["stories"]]
    movie, _, _ = build_coanchor_movie(script, show, fake_clips, ticker_items, fake_narr, _check=False)
    g.check_sizes(movie)


def build_coanchor_movie(script, show, clips, ticker_items, narration, _check=True):
    scenes, seen = [], set()
    narration_secs, n_images = 0.0, 0
    tick = _Ticker(ticker_items)

    if "open_a" in clips:
        scenes.append(_anchor_scene(clips["open_a"],
                                    [g.title_card(show["title"], show["a"]["name"], show["b"]["name"])], tick))
    if "open_b" in clips:
        scenes.append(_anchor_scene(clips["open_b"], [g.lower_third(show["b"]["name"])], tick))
        seen.add("b")

    for i, st in enumerate(script["stories"]):
        who = st["anchor"]
        key = f"lead_{i}"
        if key in clips:
            ov = [] if who in seen else [g.lower_third(show[who]["name"])]
            seen.add(who)
            scenes.append(_anchor_scene(clips[key], ov, tick))
        sc, dur, n = _broll_scene(st, narration[i], tick)
        scenes.append(sc)
        narration_secs += dur
        n_images += n

    if "close_a" in clips:
        scenes.append(_anchor_scene(clips["close_a"], [], tick))
    if "close_b" in clips:
        scenes.append(_anchor_scene(clips["close_b"], [g.sign_off(show["tagline"])], tick))

    caption = {"style": "classic", "max-words-per-line": 4, "position": CAPTION_POS,
               "font-family": "Barlow Condensed", "font-weight": "700", "font-size": 76,
               "line-color": "#FFFFFF", "word-color": "#FFD34D",
               "outline-color": "#000000", "outline-width": 5,
               "shadow-color": "#000000", "shadow-offset": 4}
    if CAPTION_POS == "custom":
        caption["x"], caption["y"] = CAPTION_X, CAPTION_Y

    if DISSOLVE > 0:
        # JSON2Video "fade" is a crossfade: it runs at the start of a scene and overlaps the
        # previous one. The ticker band is identical in both scenes, so it doesn't flicker.
        for sc in scenes[1:]:
            sc["transition"] = {"style": "fade", "duration": DISSOLVE}

    movie = {
        "resolution": "full-hd", "quality": "high",
        "scenes": scenes,
        "elements": [g.bug(), g.live_bar(show["title"])]
                    + ([{"type": "subtitles", "language": "auto", "settings": caption}] if CAPTIONS else []),
    }
    if _check:
        g.check_sizes(movie)
    return movie, narration_secs, n_images
