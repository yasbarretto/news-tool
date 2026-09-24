"""db.py — Postgres helpers for the worker + pipeline."""
import os, json
import psycopg


def get_conn():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


# ---- settings ----
def get_settings():
    with get_conn() as c:
        r = c.execute("SELECT mode, every_minutes, daily_cap, num_stories, last_enqueued_at "
                      "FROM public.news69_settings WHERE id=1").fetchone()
    if not r:
        return {"mode": "off", "every_minutes": 60, "daily_cap": 10, "num_stories": 3, "last_enqueued_at": None}
    return {"mode": r[0], "every_minutes": r[1], "daily_cap": r[2], "num_stories": r[3], "last_enqueued_at": r[4]}


def touch_enqueued():
    with get_conn() as c:
        c.execute("UPDATE public.news69_settings SET last_enqueued_at=now() WHERE id=1")


# ---- job queue ----
def enqueue_job():
    with get_conn() as c:
        row = c.execute("INSERT INTO public.news69_videos (status, stage, progress, source) "
                        "VALUES ('queued','queued',0,'News69 pipeline') RETURNING id").fetchone()
        return row[0]


def claim_next_queued():
    """Atomically grab the oldest queued job (safe if >1 worker)."""
    with get_conn() as c:
        row = c.execute("""
            UPDATE public.news69_videos SET status='processing', stage='starting', progress=5
            WHERE id = (SELECT id FROM public.news69_videos WHERE status='queued'
                        ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
            RETURNING id
        """).fetchone()
        return row[0] if row else None


def update_job(vid, **fields):
    if fields.get("qa") is not None:
        fields["qa"] = json.dumps(fields["qa"])
    cols = ", ".join(f"{k}=%s" for k in fields)
    vals = list(fields.values()) + [vid]
    with get_conn() as c:
        c.execute(f"UPDATE public.news69_videos SET {cols} WHERE id=%s", vals)


def count_active():
    with get_conn() as c:
        return c.execute("SELECT count(*) FROM public.news69_videos "
                         "WHERE status IN ('queued','processing')").fetchone()[0]


def count_today():
    with get_conn() as c:
        return c.execute("SELECT count(*) FROM public.news69_videos "
                         "WHERE created_at::date = (now() at time zone 'utc')::date").fetchone()[0]


def recent_headlines(limit=25):
    """Headlines we've already covered — used to avoid duplicate stories."""
    with get_conn() as c:
        rows = c.execute(
            "SELECT headline FROM public.news69_videos "
            "WHERE headline IS NOT NULL AND created_at > now() - interval '3 days' "
            "ORDER BY created_at DESC LIMIT %s", (limit,)
        ).fetchall()
    return [r[0] for r in rows]


def log_event(kind, video_id=None, headline=None, detail=None):
    """Write an entry to the dashboard activity feed. Never blocks the pipeline."""
    try:
        with get_conn() as c:
            c.execute(
                "INSERT INTO public.news69_events (kind, video_id, headline, detail) VALUES (%s,%s,%s,%s)",
                (kind, video_id, headline, detail),
            )
    except Exception as e:
        print("[events] log failed:", e)


def get_job(vid):
    """Job row details needed to decide fresh-generate vs rework."""
    with get_conn() as c:
        r = c.execute(
            "SELECT script, reject_note, reject_category, rework_of, rework_mode, avatar_id, voice_id, show_key "
            "FROM public.news69_videos WHERE id=%s", (vid,)
        ).fetchone()
    if not r:
        return {}
    return {"script": r[0], "reject_note": r[1], "reject_category": r[2],
            "rework_of": r[3], "rework_mode": r[4], "avatar_id": r[5], "voice_id": r[6], "show_key": r[7]}


def show_key_of(vid):
    """The show a video belongs to, or None."""
    with get_conn() as c:
        r = c.execute("SELECT show_key FROM public.news69_videos WHERE id=%s", (vid,)).fetchone()
    return r[0] if r else None


def save_script(vid, script):
    with get_conn() as c:
        c.execute("UPDATE public.news69_videos SET script=%s WHERE id=%s", (json.dumps(script), vid))


def recover_stuck():
    """On worker start, nothing can still be in flight: any job left 'processing' was cut off
    by a restart or crash and would otherwise sit there forever (only 'queued' jobs are picked
    up). Marks them failed with a clear reason, and resets half-built previews.
    Assumes ONE worker service, which is how News69 runs."""
    with get_conn() as c:
        jobs = c.execute(
            "UPDATE public.news69_videos SET status='failed', stage='error', "
            "error='interrupted: worker restarted mid-job' WHERE status='processing' RETURNING id"
        ).fetchall()
        prev = c.execute(
            "UPDATE public.news69_videos SET preview_status='error' "
            "WHERE preview_status='building' RETURNING id"
        ).fetchall()
    return [r[0] for r in jobs], [r[0] for r in prev]
