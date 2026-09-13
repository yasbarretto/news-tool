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
