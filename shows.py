"""
shows.py — the News Channel 69 roster.

Each show has two co-anchors (a = opens the show, b = second chair), a topic that
drives which news feed it pulls, a tagline for the sign-off, and a default slot.

AVATARS ARE STAND-INS. The real anchors come from generated photo avatars; until
those arrive each anchor uses an office-set stock avatar so the look stays
consistent. Swap `avatar` for the photo-avatar id when it exists. Names on screen
come from `name`, so the lower thirds are already correct.

VOICES must be STARFISH voices. Each anchor's voice is used twice: for the avatar
clip and for the b-roll narration TTS. The avatar endpoint accepts more voices than
the TTS endpoint, so a voice can render the anchor fine and then fail narration.
Check with starfish_voices.py (GET /v3/voices?engine=starfish). The worker also
refuses a job up front if a show has a non-Starfish voice.
"""

# stand-in stock avatars (office set, all confirmed rendering)
_M = {
    "brandon": "Brandon_Office_Sitting_Front_public",
    "noah":    "Noah_standing_office_front",
    "timothy": "Timothy_sitting_office_front",
    "riley":   "Riley_sitting_office_front",
    "raul":    "Raul_standing_office_front",
    "emanuel": "Emanuel_standing_office_front",
}
_F = {
    "annie_sit":   "Annie_Office_Sitting_Front_public",
    "annie_stand": "Annie_Office_Standing_Front_public",
    "abigail":     "Abigail_standing_office_front",
    "abigail_sd":  "Abigail_standing_office_side",
}

# Starfish voices: each works for BOTH the avatar clip and the narration TTS.
# Chosen for an anchor register (clear, measured, composed). Preview before demos.
_VM = {
    "rupert":  "65ec2e63a15745d4afc8bf996e107fa2",  # Rupert - Clear & Professional
    "wesley":  "71235baf743941219dc8aa4f73deadf6",  # Wesley - Serious & Composed
    "hamish":  "31c61db6d4894da3af7ed2784507448e",  # Hamish - Thoughtful & Clear
    "edmund":  "0e2ff5b962084420879e076a2345d13f",  # Edmund - Firm & Measured
    "jasper":  "af34c02799474b2d9442858ad4672906",  # Jasper - Firm & Measured
    "marcus":  "0fadce1e82af494a93873aa38ea8d106",  # Marcus - Warm & Friendly
    "quincy":  "183f63d555524d9489de14638d530af2",  # Quincy - Firm & Measured
    "henry":   "7aed81d30cd4462da310a0e6b9c64791",  # Henry - Warm & Friendly
}
_VF = {
    "annie":     "330290724a1b470fb63153f34d4c0183",  # Annie - Lifelike (proven in production)
    "renata":    "6567750df960424fb6556202d7206640",  # Renata - Clear & Professional
    "naomi":     "2cd6a90ecc36475f90509d770f029a4b",  # Naomi - Conversational & Easygoing
    "aviva":     "db20852051724b0a9b77477079311b5d",  # Aviva - Thoughtful & Clear
    "calla":     "1ec4e0c0a74b40a1b7f71d32400200d6",  # Calla - Firm & Measured
    "maya":      "a36d4fe22037455f8a0ed6f58c64ee09",  # Maya - Bright & Energetic
    "bianca":    "0f0524764575497fa3209515a26d1701",  # Bianca - Serious & Composed
    "charlotte": "ea7f48f4f96c4261bd80124e7d2bd3b8",  # Charlotte - Calm & Soothing
}


def _gn(q):
    return f"https://news.google.com/rss/search?q={q}+when:1d&hl=en-US&gl=US&ceid=US:en"


SHOWS = {
    "morning_brief": {
        "title": "The Morning Brief", "tagline": "Real news. Brighter days.", "slot": "07:00",
        "topic": "the top tech and business stories to start the day",
        "feeds": [_gn("technology"), _gn("AI")],
        "a": {"name": "Alex Reynolds", "avatar": _M["brandon"], "voice": _VM["rupert"]},
        "b": {"name": "Emma Chen", "avatar": _F["annie_sit"], "voice": _VF["annie"]},
    },
    "america_today": {
        "title": "America Today", "tagline": "Real news. Real perspective.", "slot": "09:00",
        "topic": "the biggest US national stories",
        "feeds": [_gn("united+states")],
        "a": {"name": "Victor Marshall", "avatar": _M["timothy"], "voice": _VM["wesley"]},
        "b": {"name": "Savannah Blake", "avatar": _F["abigail"], "voice": _VF["renata"]},
    },
    "live_desk": {
        "title": "The Live Desk", "tagline": "Real news. Real conversation.", "slot": "12:00",
        "topic": "the breaking stories people are talking about right now",
        "feeds": [_gn("breaking+news")],
        "a": {"name": "Chase Harrison", "avatar": _M["noah"], "voice": _VM["hamish"]},
        "b": {"name": "Natalie Vale", "avatar": _F["annie_stand"], "voice": _VF["naomi"]},
    },
    "global_hour": {
        "title": "The Global Hour", "tagline": "Real news. A wider world.", "slot": "15:00",
        "topic": "the most important world news",
        "feeds": [_gn("world")],
        "a": {"name": "Tyler Brooks", "avatar": _M["riley"], "voice": _VM["edmund"]},
        "b": {"name": "Kimiko Tan", "avatar": _F["abigail_sd"], "voice": _VF["aviva"]},
    },
    "business_beat": {
        "title": "The Business Beat", "tagline": "Real news. Real opportunity.", "slot": "17:00",
        "topic": "markets, companies and the economy",
        "feeds": [_gn("business"), _gn("stock+market")],
        "a": {"name": "Daniel Park", "avatar": _M["raul"], "voice": _VM["jasper"]},
        "b": {"name": "Madison Rivers", "avatar": _F["abigail"], "voice": _VF["calla"]},
    },
    "sports_culture": {
        "title": "Sports & Culture", "tagline": "Real news. All angles.", "slot": "18:00",
        "topic": "sports and entertainment",
        "feeds": [_gn("sports"), _gn("entertainment")],
        "a": {"name": "Marcus Bell", "avatar": _M["emanuel"], "voice": _VM["marcus"]},
        "b": {"name": "Jordan Reese", "avatar": _F["annie_stand"], "voice": _VF["maya"]},
    },
    "prime_time": {
        "title": "Prime Time 69", "tagline": "Real news. No limits.", "slot": "20:00",
        "topic": "the day's defining stories, in depth",
        "feeds": [_gn("technology"), _gn("world")],
        "a": {"name": "Jack Weston", "avatar": _M["timothy"], "voice": _VM["quincy"]},
        "b": {"name": "Taylor Brooks", "avatar": _F["annie_sit"], "voice": _VF["bianca"]},
    },
    "nightcap": {
        "title": "The Nightcap", "tagline": "Real news. Different angle.", "slot": "22:00",
        "topic": "the day's stories, looked at from a different angle",
        "feeds": [_gn("technology"), _gn("culture")],
        "a": {"name": "Ryan Carter", "avatar": _M["noah"], "voice": _VM["henry"]},
        "b": {"name": "Sienna Monroe", "avatar": _F["abigail_sd"], "voice": _VF["charlotte"]},
    },
}


# CALM photos (from worker/calm_anchor.py): each anchor's composed look, trimmed to 16:9
# and enlarged to 2752x1548, uploaded as its own photo avatar. Every one test-rendered at
# 1920x1080 with no side bars. Rendered through Avatar IV (HEYGEN_ENGINE) they stay calm;
# through the old v2 animation they grin like every other photo.
# Do NOT paste raw `make_anchors.py looks` ids here: those are 1024x608 (side bars + blur).
PHOTOS = {
    "Alex Reynolds": "0d0dc242ff4548f9b59714063007e896",
    "Emma Chen": "64963f837af6456087a9f5a76cfdc1a6",
    "Victor Marshall": "334fdcaf45c24b26b32149bd7195cac5",
    "Savannah Blake": "9d228b9dbb144dd083d8770c07839574",   # from new_look.py (her composed looks had lost her blonde hair)
    "Chase Harrison": "d22ae20fe39e41dd81341715b10758c5",
    "Natalie Vale": "8c6a9dd756ba4224a152c0d796b48f5b",
    "Tyler Brooks": "2f7bec8438a941208897e3a4f5f7b7dc",
    "Kimiko Tan": "ed472e69773445618017e65fa86b15bd",
    "Jack Weston": "64b15a108ef748feb69465336ff7a77b",
    "Taylor Brooks": "785713bd58b6485f91d0d3d838e4ca89",
    "Daniel Park": "f62f20f806dc4606bf6ebf156cff0039",
    "Madison Rivers": "746439b38ace4b318ac9dc37dae68a06",
    "Marcus Bell": "9c166b7c68384f0a9c9687afb1605b39",
    "Jordan Reese": "f3d3a8845061447e84cf6f74c7d77fb6",
    "Ryan Carter": "bf72eecea2944b9e97833fd0d4d33d29",
    "Sienna Monroe": "4e2ece3cb79544019fec48897fe6ec76",
}

# The version-8 original photos (sharp, widescreen, broad smile), kept for rollback.
PHOTOS_ORIGINAL = {
    "Alex Reynolds": "77dcf7cdf53546ebbda279d4c6a8186a",
    "Emma Chen": "e750ee24c8f54212a42f9624a90981d1",
    "Victor Marshall": "2cce600e92d64e3e94cbf6da26e37b9c",
    "Savannah Blake": "3e56cfb968a54711996f0b9d29316f6e",
    "Chase Harrison": "1f6383f626fd44e588db582855704ae4",
    "Natalie Vale": "81e59379529f4bc59384a5806efedd69",
    "Tyler Brooks": "8e4905fd568149258c79c4ab763c9309",
    "Kimiko Tan": "eedd9cc7b02a436dbfaf90c2bc9ddd86",
    "Jack Weston": "dd506e7fdf8a45a09ba545eb4a787a2f",
    "Taylor Brooks": "eb473fd98a774d1695858b9d855b6d35",
    "Daniel Park": "8b444a307803483bbdd78cd4824e4de2",
    "Madison Rivers": "2860aad2681a479fa995c3482530c14a",
    "Marcus Bell": "69ef584ec8254765816b684dc66a1e1c",
    "Jordan Reese": "d86d463076324104a11cf778021167da",
    "Ryan Carter": "1e3ad74a3a20492fb828a3e6bf898021",
    "Sienna Monroe": "3278ef50b0834b9492e69de33e634224",
}

# Composed (not smiling) looks of the SAME anchors, from `make_anchors.py looks`.
# Used for somber stories. Anchors without one fall back to their warm look.
# Composed looks are 1024x608 (HeyGen pads and upscales them: side bars + blur), so they
# are OFF. Somber stories use the same calm photo as everything else. To bring them back,
# restore the dict from worker_backup_before_revert/shows.py.
PHOTOS_SERIOUS = {}

for _show in SHOWS.values():
    for _side in ("a", "b"):
        _name = _show[_side]["name"]
        if PHOTOS.get(_name):
            _show[_side]["photo"] = PHOTOS[_name]
        if PHOTOS_SERIOUS.get(_name):
            _show[_side]["photo_serious"] = PHOTOS_SERIOUS[_name]


def get_show(key):
    return SHOWS.get(key or "")
