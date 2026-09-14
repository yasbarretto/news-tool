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
from publisher import run_publishing
from phase3_pipeline import (
    ingest, make_script, revise_script, heygen_avatar, heygen_tts, story_scene, build_movie, render_movie,
)

POLL_SECONDS = 15


def process(job_id, num_stories):
    def stage(label, pct):
        db.update_job(job_id, stage=label, progress=pct)
        print(f"[job {job_id}] {label} ({pct}%)")

    try:
        job = db.get_job(job_id)
        headlines = []

        if job.get("script"):
            # ---- REWORK: re-render from the stored script, no new story ----
            script = job["script"]
            note = job.get("reject_note")
            cat = job.get("reject_category")
            if job.get("rework_mode") == "auto" and note and cat in ("script", "audio", "fact"):
                stage("revising script from note", 20)
                try:
                    script = revise_script(script, note)
                except Exception as e:
                    print("  [rework] revise failed, using original script:", e)
            else:
                stage("reusing script", 20)
            db.save_script(job_id, script)
        else:
            # ---- FRESH: pick a new story ----
            stage("ingesting news", 10)
            headlines = ingest()
            if not headlines:
                db.update_job(job_id, status="failed", stage="error", error="no headlines from any feed")
                return

            stage("writing script", 25)
            covered = db.recent_headlines()
            script = make_script(headlines, num_stories, covered)
            db.save_script(job_id, script)

        stage("rendering anchor", 45)
        intro_url = heygen_avatar(script["intro"])
        outro_url = heygen_avatar(script["outro"])

        stage("narration + b-roll", 60)
        story_scenes = [story_scene(s) for s in script["stories"]]

        stage("assembling video", 80)
        url = render_movie(build_movie(intro_url, outro_url, story_scenes))

        stage("auto-QA", 95)
        qa = run_auto_qa(script, headlines or [])
        head = script["stories"][0]["headline"]
        flags = [k for k in ("facts", "visual", "brand", "audio") if qa.get(k) == "warn"]
        db.log_event("qa", job_id, head,
                     (f"{len(flags)} flag(s): " + ", ".join(flags)) if flags else "all checks passed")

        db.update_job(
            job_id, status="review", stage="ready", progress=100,
            headline=script["stories"][0]["headline"], video_url=url, qa=qa,
            duration=f"~{num_stories * 30 + 20}s",
        )
        db.log_event("generated", job_id, head, "entered review queue")
        print(f"[job {job_id}] DONE -> in review queue")
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
    while True:
        try:
            settings = db.get_settings()
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
