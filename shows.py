"""
shows.py — the News Channel 69 roster.

Each show has two co-anchors (a = opens the show, b = second chair), a topic that
drives which news feed it pulls, a tagline for the sign-off, and a default slot.

AVATARS ARE STAND-INS. The real anchors come from generated photo avatars; until
those arrive each anchor uses an office-set stock avatar so the look stays
consistent. Swap `avatar` for the photo-avatar id when it exists. Names on screen
come from `name`, so the lower thirds are already correct.

VOICES are HeyGen broadcaster/newscaster voices. They don't share the anchor's
name (these are fictional people), so nothing on screen claims they do.
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

# broadcaster voices from the HeyGen catalog
_VM = {
    "eric":     "ec4aa6ac882147ffb679176d49f3e41f",  # Eric - Newscaster
    "tony":     "c7ce3036f467445485d80b153c5a88a8",  # Anchorman Tony
    "jack":     "6350bb11b684400a8c820eb3f98027cc",  # Jack Sterling - Broadcaster
    "william":  "06c816b952f14fa9b3a6c42aa151f731",  # William Prescott - Broadcaster
    "canyon":   "12075274141e4fccae353873d281094e",  # Canyon Rivers - Broadcaster
    "derek":    "2ab050c62d2a4124abba78493c56fc00",  # Dynamic Derek - Broadcaster
    "norman":   "42ba66c96f244c62bec00475ab356071",  # Norman - Broadcaster
    "obi":      "42423245eb4f4c1586c396bbd035b922",  # Obi - Broadcaster
}
_VF = {
    "claire":   "5f745b3db0db43739f31499f4f0aedd6",  # Claire Lawson - Broadcaster
    "georgia":  "596d780fd5874d7983847b6a0e0c49e6",  # Georgia - Lifelike - Broadcaster
    "nora":     "f9eb1916c24a47b6a2ce5ce40c141a38",  # Narrative Nora - Broadcaster
    "ella":     "06d2e8048b9244259f89a30e36e65134",  # Energetic Ella - Broadcaster
    "derya":    "04d0ae1d0af2489ca7d3bb402a39a890",  # Derya - Lifelike - Broadcaster
    "neerja":   "66a21dedf2c842b8a516cdb264360e0e",  # Neerja - Newscaster
    "lindsay":  "c42d48651df245a48d2dee455e33e9a7",  # Reporter Lindsay
}


def _gn(q):
    return f"https://news.google.com/rss/search?q={q}+when:1d&hl=en-US&gl=US&ceid=US:en"


SHOWS = {
    "morning_brief": {
        "title": "The Morning Brief", "tagline": "Real news. Brighter days.", "slot": "07:00",
        "topic": "the top tech and business stories to start the day",
        "feeds": [_gn("technology"), _gn("AI")],
        "a": {"name": "Alex Reynolds", "avatar": _M["brandon"], "voice": _VM["eric"]},
        "b": {"name": "Emma Chen", "avatar": _F["annie_sit"], "voice": _VF["claire"]},
    },
    "america_today": {
        "title": "America Today", "tagline": "Real news. Real perspective.", "slot": "09:00",
        "topic": "the biggest US national stories",
        "feeds": [_gn("united+states")],
        "a": {"name": "Victor Marshall", "avatar": _M["timothy"], "voice": _VM["william"]},
        "b": {"name": "Savannah Blake", "avatar": _F["abigail"], "voice": _VF["georgia"]},
    },
    "live_desk": {
        "title": "The Live Desk", "tagline": "Real news. Real conversation.", "slot": "12:00",
        "topic": "the breaking stories people are talking about right now",
        "feeds": [_gn("breaking+news")],
        "a": {"name": "Chase Harrison", "avatar": _M["noah"], "voice": _VM["jack"]},
        "b": {"name": "Natalie Vale", "avatar": _F["annie_stand"], "voice": _VF["nora"]},
    },
    "global_hour": {
        "title": "The Global Hour", "tagline": "Real news. A wider world.", "slot": "15:00",
        "topic": "the most important world news",
        "feeds": [_gn("world")],
        "a": {"name": "Tyler Brooks", "avatar": _M["riley"], "voice": _VM["canyon"]},
        "b": {"name": "Kimiko Tan", "avatar": _F["abigail_sd"], "voice": _VF["derya"]},
    },
    "business_beat": {
        "title": "The Business Beat", "tagline": "Real news. Real opportunity.", "slot": "17:00",
        "topic": "markets, companies and the economy",
        "feeds": [_gn("business"), _gn("stock+market")],
        "a": {"name": "Daniel Park", "avatar": _M["raul"], "voice": _VM["derek"]},
        "b": {"name": "Madison Rivers", "avatar": _F["abigail"], "voice": _VF["neerja"]},
    },
    "sports_culture": {
        "title": "Sports & Culture", "tagline": "Real news. All angles.", "slot": "18:00",
        "topic": "sports and entertainment",
        "feeds": [_gn("sports"), _gn("entertainment")],
        "a": {"name": "Marcus Bell", "avatar": _M["emanuel"], "voice": _VM["obi"]},
        "b": {"name": "Jordan Reese", "avatar": _F["annie_stand"], "voice": _VF["ella"]},
    },
    "prime_time": {
        "title": "Prime Time 69", "tagline": "Real news. No limits.", "slot": "20:00",
        "topic": "the day's defining stories, in depth",
        "feeds": [_gn("technology"), _gn("world")],
        "a": {"name": "Jack Weston", "avatar": _M["timothy"], "voice": _VM["tony"]},
        "b": {"name": "Taylor Brooks", "avatar": _F["annie_sit"], "voice": _VF["lindsay"]},
    },
    "nightcap": {
        "title": "The Nightcap", "tagline": "Real news. Different angle.", "slot": "22:00",
        "topic": "the day's stories, looked at from a different angle",
        "feeds": [_gn("technology"), _gn("culture")],
        "a": {"name": "Ryan Carter", "avatar": _M["noah"], "voice": _VM["norman"]},
        "b": {"name": "Sienna Monroe", "avatar": _F["abigail_sd"], "voice": _VF["georgia"]},
    },
}


def get_show(key):
    return SHOWS.get(key or "")
