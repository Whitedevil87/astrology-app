"""
Celestial Arc — Analysis service.
Computes Vedic (sidereal) Big Three, Nakshatra, blueprint, and predictions.
All zodiac logic uses KP Ayanamsa sidereal positions.
Prediction text: Simple English + light Hinglish.
"""

import math
from datetime import date, datetime, time, timezone
from html import escape
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from astrology_constants import (
    PERSONALITY_RULES, CAREER_RULES, ZODIAC_ORDER, ZODIAC_META,
    STRENGTH_BLURBS, WEAKNESS_BLURBS, LUCKY_DAYS, ELEMENT_COLORS,
    NAKSHATRA_DATA, VIMSHOTTARI_ORDER, VIMSHOTTARI_PERIODS,
)
from astrology_math import (
    julian_day, sun_ecliptic_longitude_deg, moon_ecliptic_longitude_deg,
    ascendant_longitude_deg, _norm360,
    nakshatra_index, nakshatra_pada, nakshatra_fraction,
    moon_sidereal_longitude_deg,
)

# ── Sidereal Zodiac Sign from Date (Fallback) ───────────────────────
# Approximate sidereal Sun-transit dates (KP system).
# Used ONLY when geocoding fails and we can't compute exact longitude.

_SIDEREAL_SUN_TRANSITS = [
    # (month, day, sign) — Sun enters this sidereal sign on approximately this date
    (1, 14, "Capricorn"),    # Makara
    (2, 13, "Aquarius"),     # Kumbha
    (3, 14, "Pisces"),       # Meena
    (4, 14, "Aries"),        # Mesha
    (5, 15, "Taurus"),       # Vrishabha
    (6, 15, "Gemini"),       # Mithuna
    (7, 17, "Cancer"),       # Karka
    (8, 17, "Leo"),          # Simha
    (9, 17, "Virgo"),        # Kanya
    (10, 18, "Libra"),       # Tula
    (11, 16, "Scorpio"),     # Vrishchika
    (12, 16, "Sagittarius"), # Dhanu
]


def zodiac_sign(birth_date: date) -> str:
    """Fallback sidereal Sun sign from date (approximate KP transit dates)."""
    month, day = birth_date.month, birth_date.day
    # Default: last entry covers Dec 16 onward into next year's Jan 13
    result = _SIDEREAL_SUN_TRANSITS[-1][2]  # Scorpio (Dec 16+)
    for m, d, sign in _SIDEREAL_SUN_TRANSITS:
        if (month, day) >= (m, d):
            result = sign
    return result


# ── Western / Tropical Zodiac Sign ──────────────────────────────────

_TROPICAL_SUN_TRANSITS = [
    # Standard Western tropical zodiac date boundaries
    (1, 20, "Aquarius"),
    (2, 19, "Pisces"),
    (3, 21, "Aries"),
    (4, 20, "Taurus"),
    (5, 21, "Gemini"),
    (6, 21, "Cancer"),
    (7, 23, "Leo"),
    (8, 23, "Virgo"),
    (9, 23, "Libra"),
    (10, 23, "Scorpio"),
    (11, 22, "Sagittarius"),
    (12, 22, "Capricorn"),
]


def western_zodiac_sign(birth_date: date) -> str:
    """Western/tropical Sun sign from date (standard boundaries)."""
    month, day = birth_date.month, birth_date.day
    result = "Capricorn"  # Default: Dec 22 – Jan 19
    for m, d, sign in _TROPICAL_SUN_TRANSITS:
        if (month, day) >= (m, d):
            result = sign
    return result


def moon_sign(birth_date: date) -> str:
    """Fallback Moon sign — rough approximation from day-of-year."""
    day_of_year = birth_date.timetuple().tm_yday
    # Moon moves ~13 deg/day, completes zodiac in ~27.3 days
    # This is a very rough fallback — real calculation is in compute_hybrid_big_three
    return ZODIAC_ORDER[(day_of_year * 13 // 27) % 12]


def ascendant_sign(birth_time: time, birth_place: str) -> str:
    """Fallback ascendant — rough hash-based approximation."""
    place_score = sum(ord(ch) for ch in birth_place.lower() if ch.isalpha())
    time_bucket = birth_time.hour * 2 + (1 if birth_time.minute >= 30 else 0)
    return ZODIAC_ORDER[(place_score + time_bucket) % 12]


# ── Sign from Longitude ─────────────────────────────────────────────

def sign_from_longitude(lon_deg: float) -> str:
    """Zodiac sign from sidereal longitude (0°Aries = 0°)."""
    idx = int(_norm360(lon_deg) // 30)
    return ZODIAC_ORDER[idx % 12]


# ── Hybrid Big Three (Sidereal / KP) ────────────────────────────────

def compute_hybrid_big_three(
    birth_date: date, birth_time: time, birth_place: str,
    lat: float, lon: float, tz_name: str
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Compute sidereal Sun, Moon, Ascendant signs using KP Ayanamsa.
    Returns (profile dict, details dict).
    """
    tz = ZoneInfo(tz_name)
    dt_local = datetime(
        birth_date.year, birth_date.month, birth_date.day,
        birth_time.hour, birth_time.minute, tzinfo=tz,
    )
    dt_utc = dt_local.astimezone(timezone.utc)
    jd = julian_day(dt_utc)

    # These functions already return SIDEREAL longitudes (KP Ayanamsa applied)
    sun_lon = sun_ecliptic_longitude_deg(jd)
    moon_lon = moon_ecliptic_longitude_deg(jd)
    asc_lon = ascendant_longitude_deg(jd, lat, lon)

    # Nakshatra from sidereal Moon
    nak_idx = nakshatra_index(moon_lon)
    nak_data = NAKSHATRA_DATA[nak_idx]
    nak_pd = nakshatra_pada(moon_lon)

    profile = {
        "zodiac": sign_from_longitude(sun_lon),
        "moon_sign": sign_from_longitude(moon_lon),
        "ascendant": sign_from_longitude(asc_lon),
    }
    details = {
        "method": "kp_sidereal",
        "place_input": birth_place,
        "lat": lat, "lon": lon, "tz": tz_name,
        "local_datetime": dt_local.isoformat(),
        "utc_datetime": dt_utc.isoformat(),
        "jd": jd,
        "sun_lon_deg": sun_lon,
        "moon_lon_deg": moon_lon,
        "asc_lon_deg": asc_lon,
        "nakshatra": nak_data["name"],
        "nakshatra_lord": nak_data["lord"],
        "nakshatra_pada": nak_pd,
        "nakshatra_index": nak_idx,
    }
    return profile, details


# ── Nakshatra Info Helper ────────────────────────────────────────────

def get_nakshatra_info(moon_lon_sidereal: float) -> Dict[str, Any]:
    """Get Nakshatra name, lord, pada, and meaning from sidereal Moon longitude."""
    idx = nakshatra_index(moon_lon_sidereal)
    pada = nakshatra_pada(moon_lon_sidereal)
    data = NAKSHATRA_DATA[idx]
    return {
        "name": data["name"],
        "lord": data["lord"],
        "pada": pada,
        "meaning": data["meaning"],
        "index": idx,
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _sign_index(sign: str) -> int:
    return ZODIAC_ORDER.index(sign) if sign in ZODIAC_ORDER else 0


def harmony_matches(zodiac: str) -> str:
    meta = ZODIAC_META.get(zodiac, ZODIAC_META["Aries"])
    element = meta["element"]
    same_el = [s for s in ZODIAC_ORDER if ZODIAC_META[s]["element"] == element and s != zodiac]
    comp = {"Fire": ["Air"], "Air": ["Fire"], "Water": ["Earth"], "Earth": ["Water"]}
    bridge = [s for s in ZODIAC_ORDER if ZODIAC_META[s]["element"] in comp.get(element, ["Air"])][:4]
    pool = list(dict.fromkeys(same_el[:2] + bridge))
    return ", ".join(pool[:3])


def growth_matches(zodiac: str) -> str:
    idx = _sign_index(zodiac)
    return f"{ZODIAC_ORDER[(idx + 3) % 12]}, {ZODIAC_ORDER[(idx + 9) % 12]}"


def seasonal_transit_note(now: datetime, sun_sign: str) -> str:
    month = now.month
    seasons = {
        12: "Winter quiet — the best time for planning. Review what you want in the next phase.",
        1:  "Time for a fresh start — build small daily habits, they will compound by spring.",
        2:  "Deepen your patience — messages may come in dreams, your intuition is strong.",
        3:  "Momentum returns — embrace learning curves and stick to practical practice.",
        4:  "Season of stability — take care of your body, budget, and close allies.",
        5:  "Social energy is strong — networking and storytelling will open new doors.",
        6:  "Home and heart are priority — protect your peace and set boundaries.",
        7:  "Creative risk is supported — show yourself without too much rehearsal.",
        8:  "Refinement pays off — edit, simplify, and polish what is already working.",
        9:  "Partnerships clarify — negotiate kindly but don't lower your standards.",
        10: "Time of transformation — honestly let go of the past, trust where you lack control.",
        11: "Expansion is calling — study, travel plans, and mentors can show new paths.",
    }
    base = seasons.get(month, seasons[6])
    return f"As a {sun_sign}: {base}"


# ── Blueprint ────────────────────────────────────────────────────────

def build_blueprint(zodiac: str, moon: str, asc: str, birth_date: date) -> Dict[str, Any]:
    meta = ZODIAC_META.get(zodiac, ZODIAC_META["Aries"])
    lucky_num = (birth_date.day * 11 + birth_date.month * 13 + birth_date.year) % 88 + 3
    element = meta["element"]
    return {
        "glyph": meta["glyph"],
        "sun_sign": zodiac,
        "element": element,
        "modality": meta["modality"],
        "ruling_planet": meta["ruler"],
        "lucky_number": lucky_num,
        "lucky_day": LUCKY_DAYS.get(zodiac, "Thursday"),
        "lucky_color": ELEMENT_COLORS.get(element, "Amethyst & silver"),
        "moon_sign": moon,
        "ascendant": asc,
        "best_matches": harmony_matches(zodiac),
        "growth_signs": growth_matches(zodiac),
        "energy_focus": f"{meta['ruler']}-driven energy with {element.lower()} element steadiness",
    }


# ── Palm Analysis ────────────────────────────────────────────────────

def simulate_palm_analysis(hand_choice: str) -> str:
    hand_label = "left hand" if hand_choice == "left" else "right hand"
    line_strength = "strong and clear" if hand_choice == "right" else "soft but deep"
    return (
        f"Your {hand_label} shows {line_strength} life and heart lines. "
        "This pattern indicates emotional wisdom, a strong recovery after setbacks, "
        "and a tendency to trust intuition before logic. "
        "There is a curve in your fate line — a meaningful career pivot will become a turning point."
    )


# ── Predictions (Simple English + light Hinglish) ────────────────────

def build_prediction(
    full_name: str, birth_place: str, profile: Dict[str, str],
    palm_text: Optional[str], birth_date: date, now: datetime,
    blueprint: Dict[str, Any]
) -> Dict[str, str]:
    z = profile["zodiac"]
    m = profile["moon_sign"]
    a = profile["ascendant"]
    meta = ZODIAC_META.get(z, ZODIAC_META["Aries"])
    element = meta["element"]
    ruler = meta["ruler"]

    personality = (
        f"{full_name}, your Sun sign is {z} {blueprint['glyph']} — "
        f"{PERSONALITY_RULES.get(z, 'a rare blend of fire and wisdom')}. "
        f"Your Moon is in {m}, which means you emotionally heal and nurture with the nature of {m}. "
        f"Your Rising sign is {a} — this is how the world sees you at first glance. "
        f"This combination makes you unique — the energy of {ruler} is visible in every decision you make."
    )

    career = (
        f"In your career, your compass points towards {CAREER_RULES.get(z, 'strategy and growth')}. "
        f"The {element} element of your Sun seeks work with a tangible impact — and your {m} Moon needs meaning, not just numbers. "
        f"With your {a} ascendant, your leadership presence comes from pacing and the story of your mission. "
        f"Connected networks from places like {birth_place} can act as powerful catalysts."
    )

    love = (
        f"In love, your {m} Moon demands emotional fluency — safe words, loyal gestures, "
        f"and a partner who stays by your side even through intense feelings. "
        f"Your {z} Sun brings sincerity and self-respect. "
        f"Your {a} rising gives charm in initial attraction, but a real bond forms "
        f"when someone demonstrates steadiness. Best matches: {blueprint['best_matches']}. "
        f"Growth tension: {blueprint['growth_signs']}."
    )

    future = (
        f"The path forward is about showing your complete self — not just the convenient version. "
        f"The triad of {z}, {m}, and {a} suggests a destiny that rewards courage, "
        f"compassionate boundaries, and following your intuition. "
        f"Lucky threads: the energy of {blueprint['lucky_day']}, {blueprint['lucky_color']} tones "
        f"as mindful cues, and the number {blueprint['lucky_number']} as an anchor for synchronicity."
    )
    if palm_text:
        future += " Palm reading is also included — destiny literally passes through your hands."

    strengths = STRENGTH_BLURBS.get(z, STRENGTH_BLURBS["Aries"])
    weaknesses = WEAKNESS_BLURBS.get(z, WEAKNESS_BLURBS["Aries"])

    wellness = (
        f"For wellness, it is essential for a {z} to honor the {element.lower()} element. "
        f"Ground your stress through breathwork, walking, or a creative outlet. "
        f"Your {m} Moon stores tension in the body — prioritize sleep and emotional debriefing "
        f"with people who make you feel safe."
    )

    compatibility = (
        f"Compatibility snapshot: Your Sun seeks playmates who can match its tempo. "
        f"Easy resonance: {blueprint['best_matches']}, "
        f"while {blueprint['growth_signs']} teach lessons in compromise. "
        f"Remember — astrology shows tendencies, not verdicts. "
        f"Choose kindness and curiosity over fatalism."
    )

    seasonal_energy = seasonal_transit_note(now, z)

    return {
        "personality": personality, "career": career, "love": love,
        "future": future, "strengths": strengths, "weaknesses": weaknesses,
        "wellness": wellness, "compatibility": compatibility,
        "seasonal_energy": seasonal_energy,
    }


# ── Report HTML ──────────────────────────────────────────────────────

def build_report_html(
    name: str, profile: Dict[str, str], sections: Dict[str, str],
    palm_text: Optional[str]
) -> str:
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
        f"<h2 class='report-title'>{escape(name)} — Vedic Cosmic Brief</h2>",
        f"<p class='report-meta'>Sun {escape(profile['zodiac'])} · Moon {escape(profile['moon_sign'])} · Lagna {escape(profile['ascendant'])}</p>",
        block("\u2726", "Personality Analysis", "personality"),
        block("\u2726", "Career Path", "career"),
        block("\u2726", "Love & Relationships", "love"),
        block("\u2726", "Future Outlook", "future"),
        block("\u2600", "Core Strengths", "strengths"),
        block("\u263D", "Growth Edges", "weaknesses"),
        block("\u2727", "Wellness & Rhythm", "wellness"),
        block("\u2665", "Compatibility Notes", "compatibility"),
        block("\u25CE", "Seasonal Energy & Timing", "seasonal_energy"),
        block("\u2726", "Kundli & Chart Layer", "kundli_layer"),
        block("\u2726", "Houses (Whole-Sign)", "vedic_houses"),
        block("\u2726", "Rahu & Ketu", "rahu_ketu"),
        block("\u2726", "Dasha / Dosha Snapshot", "vimshottari_timing"),
        block("\u2726", "Remedies & Lifestyle", "remedies_lifestyle"),
        palm_block,
    ]
    rendered = "".join(html_parts)
    rendered = "".join(ch for ch in rendered if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return rendered
