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


# Photo-avatar looks from make_anchors.py, keyed by anchor name. Paste its output here.
# Any anchor listed renders as their generated photo avatar; the rest keep their stand-in.
PHOTOS = {
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

for _show in SHOWS.values():
    for _side in ("a", "b"):
        _pid = PHOTOS.get(_show[_side]["name"])
        if _pid:
            _show[_side]["photo"] = _pid


def get_show(key):
    return SHOWS.get(key or "")
