"""
publisher.py — publishing half of the worker.

Called from worker.py's loop. Picks up videos whose publish time has arrived,
splices in the in-house ad (if chosen), then uploads.

Upload is MOCKED for now (marks published with a fake id) so the whole flow is
testable today. Swap `mock_upload()` for `youtube_upload()` when OAuth is ready.
"""
import os, time, json, requests
import psycopg

J2V_KEY = os.environ.get("JSON2VIDEO_API_KEY")
JH = {"x-api-key": J2V_KEY, "Content-Type": "application/json"}
MOCK = os.environ.get("MOCK_PUBLISH", "true").lower() == "true"


def conn():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def due_videos():
    """scheduled videos whose time has come, plus anything marked publish-now."""
    with conn() as c:
        return c.execute("""
            SELECT id, video_url, headline, ad_mode, ad_creative_id
            FROM public.news69_videos
            WHERE (status='publishing')
               OR (status='scheduled' AND publish_at <= now())
            ORDER BY publish_at LIMIT 5
        """).fetchall()


def get_creative(cid):
    with conn() as c:
        return c.execute("SELECT video_url, duration_sec, slot, sponsor FROM public.news69_creatives WHERE id=%s",
                         (cid,)).fetchone()


def splice_ad(video_url, creative):
    """Re-assemble: [ad spot] + [news video] via JSON2Video. Returns new URL."""
    ad_url, dur, slot, sponsor = creative
    scenes = [{"elements": [{"type": "video", "src": ad_url}]},
              {"elements": [{"type": "video", "src": video_url}]}]
    if slot == "postroll":
        scenes.reverse()
    movie = {"resolution": "full-hd", "quality": "high", "scenes": scenes}
    proj = requests.post("https://api.json2video.com/v2/movies", headers=JH, json=movie).json()["project"]
    while True:
        time.sleep(10)
        m = requests.get(f"https://api.json2video.com/v2/movies?project={proj}", headers=JH).json()["movie"]
        if m.get("status") == "done":
            return m["url"]
        if m.get("status") == "error":
            raise RuntimeError(m.get("message"))


def mock_upload(video_url, headline):
    """Stand-in for the real YouTube upload."""
    time.sleep(2)
    fake = "mock" + str(abs(hash(headline)) % 10**8)
    print(f"  [publish] MOCK upload -> youtube id {fake}")
    return fake


def youtube_upload(video_url, headline):
    """TODO: real YouTube Data API upload (OAuth, resumable upload, AI-disclosure flag)."""
    raise NotImplementedError("YouTube upload not wired yet — set MOCK_PUBLISH=true")


def run_publishing():
    for vid, video_url, headline, ad_mode, ad_creative_id in due_videos():
        print(f"[publish {vid}] {headline} · ads={ad_mode}")
        try:
            final_url = video_url
            if ad_mode == "inhouse" and ad_creative_id:
                cr = get_creative(ad_creative_id)
                if cr:
                    print(f"  [publish] splicing {cr[3]} spot ({cr[2]})")
                    final_url = splice_ad(video_url, cr)
                    with conn() as c:
                        c.execute("UPDATE public.news69_creatives SET spent = spent + 25 WHERE id=%s", (ad_creative_id,))

            yt = mock_upload(final_url, headline) if MOCK else youtube_upload(final_url, headline)

            with conn() as c:
                c.execute("""UPDATE public.news69_videos
                             SET status='published', published_at=now(), youtube_id=%s, video_url=%s
                             WHERE id=%s""", (yt, final_url, vid))
            with conn() as c:
                c.execute("INSERT INTO public.news69_events (kind,video_id,headline,detail) VALUES ('published',%s,%s,%s)",
                          (vid, headline, ("in-house ad" if ad_mode == "inhouse" else "platform ads")))
            print(f"[publish {vid}] PUBLISHED")
        except Exception as e:
            print(f"[publish {vid}] FAILED: {e}")
            with conn() as c:
                c.execute("UPDATE public.news69_videos SET publish_error=%s WHERE id=%s", (str(e)[:400], vid))
