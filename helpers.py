import os
import math
import uuid
from datetime import date, datetime, time, timezone
from html import escape
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from config import INSTANCE_DIR, UPLOAD_DIR

PERSONALITY_RULES = {
    "Aries": "bold, energetic, action-driven",
    "Taurus": "steady, grounded, loyal",
    "Gemini": "curious, social, quick-minded",
    "Cancer": "protective, intuitive, empathetic",
    "Leo": "charismatic, proud, heart-led",
    "Virgo": "analytical, practical, detail-focused",
    "Libra": "harmonious, diplomatic, refined",
    "Scorpio": "intense, strategic, emotionally deep",
    "Sagittarius": "optimistic, adventurous, philosophical",
    "Capricorn": "disciplined, responsible, ambitious",
    "Aquarius": "independent, inventive, visionary",
    "Pisces": "imaginative, sensitive, spiritually tuned",
}

CAREER_RULES = {
    "Aries": "leadership, startups, athletics, emergency response",
    "Taurus": "finance, design, architecture, food or luxury industries",
    "Gemini": "media, sales, teaching, communications, product roles",
    "Cancer": "counseling, hospitality, healthcare, caregiving fields",
    "Leo": "public leadership, entertainment, branding, entrepreneurship",
    "Virgo": "analysis, engineering, medicine, operations excellence",
    "Libra": "law, diplomacy, design, client-facing strategy",
    "Scorpio": "research, psychology, cybersecurity, investigative work",
    "Sagittarius": "travel, higher education, publishing, consulting",
    "Capricorn": "management, government, finance, long-term planning",
    "Aquarius": "technology, innovation labs, social impact, science",
    "Pisces": "arts, healing, storytelling, spiritual guidance",
}

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

ZODIAC_META: Dict[str, Dict[str, str]] = {
    "Aries": {"element": "Fire", "modality": "Cardinal", "ruler": "Mars", "glyph": "\u2648"},
    "Taurus": {"element": "Earth", "modality": "Fixed", "ruler": "Venus", "glyph": "\u2649"},
    "Gemini": {"element": "Air", "modality": "Mutable", "ruler": "Mercury", "glyph": "\u264A"},
    "Cancer": {"element": "Water", "modality": "Cardinal", "ruler": "Moon", "glyph": "\u264B"},
    "Leo": {"element": "Fire", "modality": "Fixed", "ruler": "Sun", "glyph": "\u264C"},
    "Virgo": {"element": "Earth", "modality": "Mutable", "ruler": "Mercury", "glyph": "\u264D"},
    "Libra": {"element": "Air", "modality": "Cardinal", "ruler": "Venus", "glyph": "\u264E"},
    "Scorpio": {"element": "Water", "modality": "Fixed", "ruler": "Pluto", "glyph": "\u264F"},
    "Sagittarius": {"element": "Fire", "modality": "Mutable", "ruler": "Jupiter", "glyph": "\u2650"},
    "Capricorn": {"element": "Earth", "modality": "Cardinal", "ruler": "Saturn", "glyph": "\u2651"},
    "Aquarius": {"element": "Air", "modality": "Fixed", "ruler": "Uranus", "glyph": "\u2652"},
    "Pisces": {"element": "Water", "modality": "Mutable", "ruler": "Neptune", "glyph": "\u2653"},
}

STRENGTH_BLURBS = {
    "Aries": "Courageous initiative, honest drive, and the ability to start what others only dream about.",
    "Taurus": "Patient endurance, loyal devotion, and a gift for building lasting security and beauty.",
    "Gemini": "Quick learning, witty communication, and versatile problem-solving under pressure.",
    "Cancer": "Protective intuition, deep empathy, and emotional intelligence that nurtures others.",
    "Leo": "Generous warmth, creative confidence, and natural leadership that uplifts a room.",
    "Virgo": "Precision, helpfulness, and sharp improvement skills that turn chaos into order.",
    "Libra": "Diplomatic grace, aesthetic taste, and peacemaking that restores balance.",
    "Scorpio": "Emotional courage, strategic focus, and transformative insight into hidden motives.",
    "Sagittarius": "Optimistic vision, honest philosophy, and fearless exploration of new horizons.",
    "Capricorn": "Discipline, integrity, and long-game ambition that climbs with quiet strength.",
    "Aquarius": "Original thinking, humanitarian ideals, and inventive solutions ahead of the curve.",
    "Pisces": "Compassion, imagination, and spiritual sensitivity that heals through understanding.",
}

WEAKNESS_BLURBS = {
    "Aries": "Impatience, sharp reactions, or moving too fast before listening to quieter signals.",
    "Taurus": "Stubborn resistance to change, over-attachment to comfort, or delayed adaptation.",
    "Gemini": "Scattered focus, nervous overthinking, or difficulty sitting with one deep decision.",
    "Cancer": "Mood swings, retreat under stress, or taking feedback more personally than intended.",
    "Leo": "Pride wounds, spotlight hunger, or mistaking loyalty for unlimited attention.",
    "Virgo": "Self-criticism, worry loops, or perfect standards that delay necessary action.",
    "Libra": "People-pleasing, indecision, or avoiding hard truths to keep harmony at all costs.",
    "Scorpio": "Intensity that overwhelms others, secrecy, or control instincts during vulnerability.",
    "Sagittarius": "Over-promising, blunt honesty, or restlessness that disrupts steady progress.",
    "Capricorn": "Workaholic tendencies, emotional reserve, or fear of imperfection slowing joy.",
    "Aquarius": "Detached coolness, unpredictability, or idealism that forgets tender human needs.",
    "Pisces": "Escapism, porous boundaries, or absorbing other people's moods too easily.",
}

LUCKY_DAYS = {
    "Aries": "Tuesday",
    "Taurus": "Friday",
    "Gemini": "Wednesday",
    "Cancer": "Monday",
    "Leo": "Sunday",
    "Virgo": "Wednesday",
    "Libra": "Friday",
    "Scorpio": "Tuesday",
    "Sagittarius": "Thursday",
    "Capricorn": "Saturday",
    "Aquarius": "Saturday",
    "Pisces": "Thursday",
}

ELEMENT_COLORS = {
    "Fire": "Gold & crimson",
    "Earth": "Forest green & clay",
    "Air": "Sky blue & silver",
    "Water": "Indigo & sea glass",
}


def ensure_directories() -> None:
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in {"png", "jpg", "jpeg", "webp"}


def make_upload_filename(original_name: str) -> str:
    ext = original_name.rsplit(".", 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"


def parse_date(date_value: str) -> date:
    return datetime.strptime(date_value, "%Y-%m-%d").date()


def parse_time(time_value: str) -> time:
    return datetime.strptime(time_value, "%H:%M").time()


def zodiac_sign(birth_date: date) -> str:
    month, day = birth_date.month, birth_date.day
    if (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "Capricorn"
    if (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "Aquarius"
    if (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return "Pisces"
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "Aries"
    if (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "Taurus"
    if (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "Gemini"
    if (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "Cancer"
    if (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "Leo"
    if (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "Virgo"
    if (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "Libra"
    if (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "Scorpio"
    return "Sagittarius"


def moon_sign(birth_date: date) -> str:
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    day_of_year = birth_date.timetuple().tm_yday
    return signs[(day_of_year // 30) % len(signs)]


def ascendant_sign(birth_time: time, birth_place: str) -> str:
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    place_score = sum(ord(ch) for ch in birth_place.lower() if ch.isalpha())
    time_bucket = birth_time.hour * 2 + (1 if birth_time.minute >= 30 else 0)
    return signs[(place_score + time_bucket) % len(signs)]


def _deg_to_rad(x: float) -> float:
    return x * math.pi / 180.0


def _rad_to_deg(x: float) -> float:
    return x * 180.0 / math.pi


def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x


def _norm24(x: float) -> float:
    x = x % 24.0
    return x + 24.0 if x < 0 else x


def julian_day(dt_utc: datetime) -> float:
    if dt_utc.tzinfo is None:
        raise ValueError("dt_utc must be timezone-aware")
    dt = dt_utc.astimezone(timezone.utc)
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    return float(jd)


def sun_ecliptic_longitude_deg(jd: float) -> float:
    n = jd - 2451545.0
    L = _norm360(280.460 + 0.9856474 * n)
    g = _norm360(357.528 + 0.9856003 * n)
    lam = L + 1.915 * math.sin(_deg_to_rad(g)) + 0.020 * math.sin(_deg_to_rad(2 * g))
    return _norm360(lam)


def moon_ecliptic_longitude_deg(jd: float) -> float:
    n = jd - 2451545.0
    L0 = _norm360(218.316 + 13.176396 * n)
    Mm = _norm360(134.963 + 13.064993 * n)
    Ms = _norm360(357.529 + 0.9856003 * n)
    D = _norm360(297.850 + 12.190749 * n)
    lam = (
        L0
        + 6.289 * math.sin(_deg_to_rad(Mm))
        + 1.274 * math.sin(_deg_to_rad(2 * D - Mm))
        + 0.658 * math.sin(_deg_to_rad(2 * D))
        + 0.214 * math.sin(_deg_to_rad(2 * Mm))
        - 0.186 * math.sin(_deg_to_rad(Ms))
    )
    return _norm360(lam)


def gmst_hours(jd: float) -> float:
    T = (jd - 2451545.0) / 36525.0
    gmst = 6.697374558 + 2400.051336 * T + 0.000025862 * T * T
    frac_day = (jd + 0.5) % 1.0
    gmst += 24.06570982441908 * frac_day
    return _norm24(gmst)


def ascendant_longitude_deg(jd: float, lat_deg: float, lon_deg: float) -> float:
    eps = _deg_to_rad(23.439291)
    lat = _deg_to_rad(lat_deg)
    lst = _deg_to_rad(_norm360((gmst_hours(jd) * 15.0) + lon_deg))
    num = math.sin(lst) * math.cos(eps) - math.tan(lat) * math.sin(eps)
    den = math.cos(lst)
    lam = math.atan2(num, den)
    return _norm360(_rad_to_deg(lam))


def sign_from_longitude(lon_deg: float) -> str:
    idx = int(_norm360(lon_deg) // 30)
    return ZODIAC_ORDER[idx]


def compute_hybrid_big_three(
    birth_date: date,
    birth_time: time,
    birth_place: str,
    lat: float,
    lon: float,
    tz_name: str,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    tz = ZoneInfo(tz_name)
    dt_local = datetime(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        birth_time.hour,
        birth_time.minute,
        tzinfo=tz,
    )
    dt_utc = dt_local.astimezone(timezone.utc)
    jd = julian_day(dt_utc)
    sun_lon = sun_ecliptic_longitude_deg(jd)
    moon_lon = moon_ecliptic_longitude_deg(jd)
    asc_lon = ascendant_longitude_deg(jd, lat, lon)
    profile = {
        "zodiac": sign_from_longitude(sun_lon),
        "moon_sign": sign_from_longitude(moon_lon),
        "ascendant": sign_from_longitude(asc_lon),
    }
    details = {
        "method": "hybrid_approx",
        "place_input": birth_place,
        "lat": lat,
        "lon": lon,
        "tz": tz_name,
        "local_datetime": dt_local.isoformat(),
        "utc_datetime": dt_utc.isoformat(),
        "jd": jd,
        "sun_lon_deg": sun_lon,
        "moon_lon_deg": moon_lon,
        "asc_lon_deg": asc_lon,
    }
    return profile, details


def _sign_index(sign: str) -> int:
    return ZODIAC_ORDER.index(sign) if sign in ZODIAC_ORDER else 0


def harmony_matches(zodiac: str) -> str:
    meta = ZODIAC_META.get(zodiac, ZODIAC_META["Aries"])
    element = meta["element"]
    same_element = [s for s in ZODIAC_ORDER if ZODIAC_META[s]["element"] == element and s != zodiac]
    complementary = {
        "Fire": ["Air"],
        "Air": ["Fire"],
        "Water": ["Earth"],
        "Earth": ["Water"],
    }
    other_el = complementary.get(element, ["Air"])
    bridge = [s for s in ZODIAC_ORDER if ZODIAC_META[s]["element"] in other_el][:4]
    pool = list(dict.fromkeys(same_element[:2] + bridge))
    return ", ".join(pool[:3])


def growth_matches(zodiac: str) -> str:
    idx = _sign_index(zodiac)
    square_a = ZODIAC_ORDER[(idx + 3) % 12]
    square_b = ZODIAC_ORDER[(idx + 9) % 12]
    return f"{square_a}, {square_b}"


def seasonal_transit_note(now: datetime, sun_sign: str) -> str:
    month = now.month
    seasons = {
        12: "Winter quiet invites planning; review what you want before the next surge.",
        1: "A reset favors fresh systems—small rituals now compound through spring.",
        2: "Patience deepens intuition; notice messages in dreams and synchronicities.",
        3: "Momentum returns; say yes to learning curves you can practice in public.",
        4: "Stability season: nurture your body, budget, and consistent allies.",
        5: "Social sparks return—networking and storytelling open doors faster than perfection.",
        6: "Home and heart take priority; protect your peace like infrastructure.",
        7: "Creative risk is supported; let yourself be seen without endless rehearsal.",
        8: "Refinement pays off—edit, simplify, polish what already works.",
        9: "Partnerships clarify; negotiate kindly but keep your standards clean.",
        10: "Transformation asks honesty; release control where trust works better.",
        11: "Expansion calls—study ideas, travel plans, and mentors can reroute you.",
    }
    base = seasons.get(month, seasons[6])
    return f"As a {sun_sign}, {base} Timing improves when action matches emotional truth."


def build_blueprint(zodiac: str, moon: str, asc: str, birth_date: date) -> Dict[str, Any]:
    meta = ZODIAC_META.get(zodiac, ZODIAC_META["Aries"])
    lucky_number = (birth_date.day * 11 + birth_date.month * 13 + birth_date.year) % 88 + 3
    element = meta["element"]
    return {
        "glyph": meta["glyph"],
        "sun_sign": zodiac,
        "element": element,
        "modality": meta["modality"],
        "ruling_planet": meta["ruler"],
        "lucky_number": lucky_number,
        "lucky_day": LUCKY_DAYS.get(zodiac, "Thursday"),
        "lucky_color": ELEMENT_COLORS.get(element, "Amethyst & silver"),
        "moon_sign": moon,
        "ascendant": asc,
        "best_matches": harmony_matches(zodiac),
        "growth_signs": growth_matches(zodiac),
        "energy_focus": f"{meta['ruler']}-styled drive with {element.lower()} element steadiness",
    }


def simulate_palm_analysis(hand_choice: str) -> str:
    hand_label = "left hand" if hand_choice == "left" else "right hand"
    line_strength = "strong and etched" if hand_choice == "right" else "soft but deep"
    return (
        f"Your {hand_label} shows {line_strength} life and heart lines. This pattern suggests emotional wisdom, "
        "strong resilience after setbacks, and a tendency to trust intuition before logic. "
        "A slight curve near the fate line indicates a meaningful career pivot that becomes your turning point."
    )


def build_prediction(
    full_name: str,
    birth_place: str,
    profile: Dict[str, str],
    palm_text: Optional[str],
    birth_date: date,
    now: datetime,
    blueprint: Dict[str, Any],
) -> Dict[str, str]:
    z = profile["zodiac"]
    m = profile["moon_sign"]
    a = profile["ascendant"]
    meta = ZODIAC_META.get(z, ZODIAC_META["Aries"])
    element = meta["element"]

    personality = (
        f"{full_name}, the veil lifts on a signature that is unmistakably {z} {blueprint['glyph']}: "
        f"{PERSONALITY_RULES.get(z, 'a rare blend of fire and wisdom')}. "
        f"Your emotional story is painted by a {m} Moon—this is how you nurture, remember, and heal. "
        f"Rising as {a}, you broadcast a first impression that can charm rooms, test boundaries, or quietly command respect—"
        "often before you say a single polished sentence."
    )

    career = (
        f"Your vocational compass tilts toward arenas tied to {CAREER_RULES.get(z, 'strategy and craft')}. "
        f"The {element.lower()} element in your Sun wants work with tangible impact; your {m} Moon needs meaning, not only metrics. "
        f"With {a} on the ascendant, leadership shows up through presence, pacing, and the story you tell about your mission. "
        f"Places and networks echoing the spirit of {birth_place} can act like catalysts when you are ready to claim the next level."
    )

    love = (
        f"In love, your {m} Moon asks for emotional fluency: safe words, loyal gestures, and a partner who does not vanish when feelings intensify. "
        f"Your {z} Sun brings heat, sincerity, and non-negotiable self-respect. "
        f"{a} rising adds charisma in early attraction, but your real bond blooms when someone proves steadiness over performance. "
        f"Harmonious archetypes to explore: {blueprint['best_matches']}. Growth-oriented tension may arrive with {blueprint['growth_signs']}—"
        "not punishment, but accelerators that sharpen clarity."
    )

    future = (
        f"The path ahead favors showing up as the whole version of yourself—not only the convenient one. "
        f"The triad of {z}, {m}, and {a} suggests a destiny that rewards courage, compassionate boundaries, and a willingness to reroute when intuition whispers 'not this.' "
        f"Lucky threads this year: lean into {blueprint['lucky_day']} energy, {blueprint['lucky_color']} tones as mindful cues, and the number {blueprint['lucky_number']} as a playful synchronicity anchor."
    )
    if palm_text:
        future += (
            " The palm layer adds a tactile prophecy: destiny here moves through your hands—what you build, touch, and repair becomes part of the spell."
        )

    strengths = STRENGTH_BLURBS.get(z, STRENGTH_BLURBS["Aries"])
    weaknesses = WEAKNESS_BLURBS.get(z, WEAKNESS_BLURBS["Aries"])

    wellness = (
        f"Wellness for {z} thrives when the {element.lower()} element is honored. "
        "Ground glittering stress with breathwork, walking rhythm, or a creative outlet that cannot be graded. "
        f"Your {m} Moon may store tension in the body like memory—prioritize sleep sanctuaries and emotional debriefs with people who feel safe."
    )

    compatibility = (
        f"Compatibility snapshot: your Sun seeks playmates of the mind and heart who match your tempo. "
        f"Easy resonance often appears with {blueprint['best_matches']}, while {blueprint['growth_signs']} may teach lessons about compromise, trust, and bold honesty. "
        "Remember: astrology highlights tendencies, not verdicts—choose kindness and curiosity over fatalism."
    )

    seasonal_energy = seasonal_transit_note(now, z)

    return {
        "personality": personality,
        "career": career,
        "love": love,
        "future": future,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "wellness": wellness,
        "compatibility": compatibility,
        "seasonal_energy": seasonal_energy,
    }


def build_report_html(name: str, profile: Dict[str, str], sections: Dict[str, str], palm_text: Optional[str]) -> str:
    palm_block = ""
    if palm_text:
        palm_block = (
            '<article class="report-section-card">'
            '<div class="report-section-heading"><span class="report-icon">\u270B</span><h3>Palm Reading Insight</h3></div>'
            f"<p class='report-copy'>{escape(palm_text)}</p>"
            "</article>"
        )

    def block(icon: str, title: str, key: str) -> str:
        body = escape(sections.get(key, ""))
        return (
            '<article class="report-section-card">'
            f'<div class="report-section-heading"><span class="report-icon">{icon}</span><h3>{escape(title)}</h3></div>'
            f"<p class='report-copy'>{body}</p>"
            "</article>"
        )

    html_parts = [
        f"<h2 class='report-title'>{escape(name)} — Cosmic Brief</h2>",
        f"<p class='report-meta'>Sun {escape(profile['zodiac'])} · Moon {escape(profile['moon_sign'])} · Asc {escape(profile['ascendant'])}</p>",
        block("\u2726", "Personality Analysis", "personality"),
        block("\u2726", "Career Path", "career"),
        block("\u2726", "Love & Relationships", "love"),
        block("\u2726", "Future Outlook", "future"),
        block("\u2600", "Core Strengths", "strengths"),
        block("\u263D", "Growth Edges", "weaknesses"),
        block("\u2727", "Wellness & Rhythm", "wellness"),
        block("\u2665", "Compatibility Notes", "compatibility"),
        block("\u25CE", "Seasonal Energy & Timing", "seasonal_energy"),
        block("\u2726", "Kundli & chart layer", "kundli_layer"),
        block("\u2726", "Houses (whole-sign demo)", "vedic_houses"),
        block("\u2726", "Rahu & Ketu", "rahu_ketu"),
        block("\u2726", "Dasha / dosha snapshot", "vimshottari_timing"),
        block("\u2726", "Remedies & ethical lifestyle", "remedies_lifestyle"),
        palm_block,
    ]
    rendered = "".join(html_parts)
    rendered = "".join(ch for ch in rendered if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return rendered
