"""
worker.py — News69 background worker (runs as its own Railway service).

Loops forever:
  1) enqueue jobs based on the generation mode (off | scheduled | auto), under the daily cap
  2) claim the next queued job and run the full pipeline, writing stage/progress as it goes

Deploy as a NEW Railway service pointed at this folder.
  Start command:  python worker.py
  Env vars:  DATABASE_URL (internal is fine here), ANTHROPIC_API_KEY, HEYGEN_API_KEY,
             HEYGEN_AVATAR_ID, HEYGEN_VOICE_ID, JSON2VIDEO_API_KEY, HEYGEN_TEST=false
"""
import os, time, traceback
from datetime import datetime, timezone, timedelta

import db
from qa import run_auto_qa
from publisher import run_publishing, run_previews
from shows import get_show
import coanchor
from phase3_pipeline import WaitTimeout
from phase3_pipeline import (
    ingest, make_script, revise_script, heygen_avatar, heygen_tts, story_scene, build_movie, render_movie, estimate_cost,
)

POLL_SECONDS = 15
# A slow clip requeues the job (resuming its clips) up to this many times before failing.
JOB_RETRIES = int(os.environ.get("JOB_RETRIES", "5"))


def process(job_id, num_stories):
    job = db.get_job(job_id)
    show = get_show(job.get("show_key"))
    if not show and job.get("rework_of"):
        # reworks created before the rework route copied show_key: take it from the original
        key = db.show_key_of(job["rework_of"])
        show = get_show(key)
        if show:
            db.update_job(job_id, show_key=key)
            job["show_key"] = key
    if show:
        return process_show(job_id, job, show, num_stories)
    if coanchor.is_coanchor(job.get("script")):
        # a co-anchored script can't go through the single-anchor path (it has no intro/outro)
        db.update_job(job_id, status="failed", stage="error",
                      error="co-anchored script but no show on this job; set show_key and requeue")
        return
    return process_single(job_id, job, num_stories)


def _stage(job_id):
    def stage(label, pct):
        db.update_job(job_id, stage=label, progress=pct)
        print(f"[job {job_id}] {label} ({pct}%)")
    return stage


def _rework_script(job, stage):
    script = job["script"]
    note, cat = job.get("reject_note"), job.get("reject_category")
    if job.get("rework_mode") == "auto" and note and cat in ("script", "audio", "fact"):
        stage("revising script from note", 20)
        try:
            private = {k: v for k, v in script.items() if str(k).startswith("_")}
            script = {**revise_script(coanchor.public(script), note), **private}
        except Exception as e:
            print("  [rework] revise failed, using original script:", e)
    else:
        stage("reusing script", 20)
    return script


def _finish(job_id, script, headlines, url, cost, secs, show_title=None):
    qa = run_auto_qa(coanchor.public(script), headlines or [])
    head = script["stories"][0]["headline"]
    flags = [k for k in ("facts", "visual", "brand", "audio") if qa.get(k) == "warn"]
    db.log_event("qa", job_id, head,
                 (f"{len(flags)} flag(s): " + ", ".join(flags)) if flags else "all checks passed")
    db.update_job(job_id, status="review", stage="ready", progress=100, cost=cost,
                  headline=head, video_url=url, qa=qa, duration=f"~{int(secs)}s")
    db.log_event("generated", job_id, head,
                 f"{show_title} · entered review queue" if show_title else "entered review queue")
    print(f"[job {job_id}] DONE -> in review queue")


# ---------------------------------------------------------------- co-anchored show
def process_show(job_id, job, show, num_stories):
    stage = _stage(job_id)
    try:
        coanchor.check_voices(show)   # before anything is spent
        headlines = []
        if job.get("script"):
            script = coanchor.normalize(_rework_script(job, stage), show)
        else:
            stage(f"ingesting news · {show['title']}", 10)
            headlines = ingest(feeds=show["feeds"])
            if not headlines:
                db.update_job(job_id, status="failed", stage="error", error="no headlines from any feed")
                return
            stage("writing co-anchor script", 22)
            script = coanchor.make_coanchor_script(headlines, show, num_stories, db.recent_headlines())
            script["_headlines"] = headlines          # a requeued attempt still has them (ticker, QA)
        headlines = headlines or script.get("_headlines", [])
        # every board figure must be in its story's source, also after a rework edited the script
        for i in coanchor.validate_figures(script, headlines):
            print(f"[job {job_id}] story {i + 1}: data board dropped (figures not found in its source)")
        db.save_script(job_id, script)
        ticker_items = [h["title"] for h in headlines] or [s["headline"] for s in script["stories"]]
        coanchor.preflight_movie(script, show, ticker_items)   # validate the payload before spending

        stage("voicing narration", 32)
        narration = coanchor.voice_narration(script, show)   # cheap; fails fast on a bad voice

        stage("rendering anchors", 42)
        ledger = script.setdefault("_clips", {})
        try:
            clips = coanchor.render_clips(script, show, ledger, save=lambda: db.save_script(job_id, script))
        except WaitTimeout as e:
            tries = script.setdefault("_retries", {})
            n = tries.get(str(job_id), 0)
            if n < JOB_RETRIES:
                tries[str(job_id)] = n + 1
                db.save_script(job_id, script)
                db.update_job(job_id, status="queued", stage=f"requeued · waiting on HeyGen ({n + 1}/{JOB_RETRIES})",
                              progress=42, error=str(e)[:300])
                print(f"[job {job_id}] slow clip, requeued ({n + 1}/{JOB_RETRIES}); finished and running clips will be resumed")
                return
            raise
        avatar_secs = coanchor.spoken_words(script) / coanchor.WPS

        stage("building graphics + b-roll", 64)
        movie, narration_secs, n_images = coanchor.build_coanchor_movie(script, show, clips, ticker_items, narration)

        stage("assembling video", 80)
        url = render_movie(movie)

        stage("auto-QA", 95)
        total = avatar_secs + narration_secs
        cost = estimate_cost(script, avatar_secs, narration_secs, n_images, total,
                             fresh=not job.get("script"))
        _finish(job_id, script, headlines, url, cost, total, show["title"])
    except Exception as e:
        traceback.print_exc()
        db.update_job(job_id, status="failed", stage="error", error=str(e)[:500])
        db.log_event("rejected", job_id, None, "generation failed: " + str(e)[:80])


# ---------------------------------------------------------------- single presenter (legacy)
def process_single(job_id, job, num_stories):
    stage = _stage(job_id)
    try:
        headlines = []
        if job.get("script"):
            script = _rework_script(job, stage)
        else:
            stage("ingesting news", 10)
            headlines = ingest()
            if not headlines:
                db.update_job(job_id, status="failed", stage="error", error="no headlines from any feed")
                return
            stage("writing script", 25)
            script = make_script(headlines, num_stories, db.recent_headlines())
        db.save_script(job_id, script)

        stage("rendering anchor", 45)
        av = job.get("avatar_id"); vo = job.get("voice_id")
        intro_url = heygen_avatar(script["intro"], av, vo)
        outro_url = heygen_avatar(script["outro"], av, vo)
        avatar_words = len(str(script["intro"]).split()) + len(str(script["outro"]).split())
        avatar_secs = avatar_words / 2.5

        stage("narration + b-roll", 60)
        story_scenes = [story_scene(s, vo) for s in script["stories"]]
        narration_secs = sum(sc.get("duration", 0) for sc in story_scenes)
        n_images = sum(len(st.get("broll_prompts") or [1]) for st in script["stories"])

        stage("assembling video", 80)
        url = render_movie(build_movie(intro_url, outro_url, story_scenes))

        stage("auto-QA", 95)
        total = avatar_secs + narration_secs
        cost = estimate_cost(script, avatar_secs, narration_secs, n_images, total,
                             fresh=not job.get("script"))
        _finish(job_id, script, headlines, url, cost, total)
    except Exception as e:
        traceback.print_exc()
        db.update_job(job_id, status="failed", stage="error", error=str(e)[:500])
        db.log_event("rejected", job_id, None, "generation failed: " + str(e)[:80])


def maybe_enqueue(s):
    """Decide whether to create a new job based on the mode."""
    if s["mode"] == "off":
        return
    if db.count_today() >= s["daily_cap"]:
        return
    last = s["last_enqueued_at"]
    due = last is None or (datetime.now(timezone.utc) - last >= timedelta(minutes=s["every_minutes"]))

    if s["mode"] == "auto":
        # keep exactly one job in flight; start the next as soon as idle (and interval elapsed)
        if db.count_active() == 0 and due:
            jid = db.enqueue_job(); db.touch_enqueued()
            print(f"[auto] enqueued job {jid}")
    elif s["mode"] == "scheduled":
        # one job per interval, regardless of queue depth
        if due:
            jid = db.enqueue_job(); db.touch_enqueued()
            print(f"[scheduled] enqueued job {jid}")


def main():
    print("News69 worker up. polling every", POLL_SECONDS, "s")
    from phase3_pipeline import HEYGEN_ENGINE, EXPRESSIVENESS
    print(f"[anchors] photo engine: {HEYGEN_ENGINE}" +
          (f" (expressiveness {EXPRESSIVENESS}, calm motion prompt)" if HEYGEN_ENGINE == "avatar_iv" else " (old v2 animation)"))
    try:
        jobs, prev = db.recover_stuck()
        if jobs:
            print(f"[recover] marked interrupted jobs failed: {jobs}")
            for j in jobs:
                db.log_event("rejected", j, None, "interrupted: worker restarted mid-job")
        if prev:
            print(f"[recover] reset half-built previews: {prev}")
    except Exception as e:
        print("[recover] skipped:", e)
    while True:
        try:
            settings = db.get_settings()
            run_previews()            # build any spliced previews the reviewer asked for
            run_publishing()          # ship anything whose publish time has arrived
            maybe_enqueue(settings)
            job_id = db.claim_next_queued()
            if job_id:
                process(job_id, settings["num_stories"])
            else:
                time.sleep(POLL_SECONDS)
        except Exception as e:
            print("worker loop error:", e)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
