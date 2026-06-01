"""
Celestial Arc — Analysis service.
Computes Vedic (sidereal) Big Three, Nakshatra, blueprint, and predictions.
All zodiac logic uses Lahiri (Chitrapaksha) sidereal positions — same default as AstroSage.
Prediction text: Simple English + light Hinglish.

Integrates:
  - vedic.dasha           (Vimshottari Dasha with exact dates)
  - vedic.panchanga       (Complete Panchanga — Tithi, Vara, Yoga, etc.)
  - vedic.ashtakavarga    (Ashtakavarga + Sarvashtakavarga)
  - vedic.kundli_matching (36-point Guna Milan + Mangal Dosha)
"""

import math
from datetime import date, datetime, time, timezone
from html import escape
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# ── New feature modules (graceful fallback if not yet deployed) ──────
try:
    from vedic.dasha import compute_dasha, current_dasha as get_current_dasha
    _DASHA_AVAILABLE = True
except ImportError:
    _DASHA_AVAILABLE = False

try:
    from vedic.panchanga import compute_panchanga, birth_panchanga
    _PANCHANGA_AVAILABLE = True
except ImportError:
    _PANCHANGA_AVAILABLE = False

try:
    from vedic.ashtakavarga import ashtakavarga_report
    _ASHTAK_AVAILABLE = True
except ImportError:
    _ASHTAK_AVAILABLE = False

try:
    from vedic.kundli_matching import compute_guna_milan, check_mangal_dosha
    _MATCHING_AVAILABLE = True
except ImportError:
    _MATCHING_AVAILABLE = False

from utils.astrology_constants import (
    PERSONALITY_RULES, CAREER_RULES, ZODIAC_ORDER, ZODIAC_META,
    STRENGTH_BLURBS, WEAKNESS_BLURBS, LUCKY_DAYS, ELEMENT_COLORS,
    NAKSHATRA_DATA, VIMSHOTTARI_ORDER, VIMSHOTTARI_PERIODS, HOUSE_MEANINGS,
)
from vedic.strength import SIGN_RULERS
from utils.astrology_math import (
    julian_day, sun_ecliptic_longitude_deg, moon_ecliptic_longitude_deg,
    ascendant_longitude_deg, _norm360,
    nakshatra_index, nakshatra_pada, nakshatra_fraction,
    moon_sidereal_longitude_deg,
)

# ── Sidereal Zodiac Sign from Date (Fallback) ───────────────────────
# Approximate sidereal Sun-transit dates (Lahiri; fallback only).
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
    """Fallback sidereal Sun sign from date (approximate Lahiri transit dates)."""
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
    """
    Fallback ascendant - called ONLY when lat/lon/tz unavailable.
    Returns 'Unknown' so UI shows clear error instead of wrong sign.
    Real ascendant is computed in compute_hybrid_big_three().
    """
    return "Unknown"


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
    Compute sidereal Sun, Moon, Ascendant using Lahiri ayanamsa (AstroSage standard).

    Uses Swiss Ephemeris when installed (arc-second accuracy); falls back to
    internal math only if pyswisseph is unavailable.
    """
    tz = ZoneInfo(tz_name)
    dt_local = datetime(
        birth_date.year, birth_date.month, birth_date.day,
        birth_time.hour, birth_time.minute, getattr(birth_time, "second", 0),
        tzinfo=tz,
    )
    dt_utc = dt_local.astimezone(timezone.utc)
    jd = julian_day(dt_utc)
    tz_offset = dt_local.utcoffset().total_seconds() / 3600.0

    method = "lahiri_approx"
    try:
        from vedic.swisseph_engine import (
            SWISSEPH_AVAILABLE,
            get_planet_longitude,
            get_ascendant,
            get_all_planet_longitudes,
        )
        if SWISSEPH_AVAILABLE:
            sun_lon = get_planet_longitude(jd, "Sun", sidereal=True, aya_type="lahiri")
            moon_lon = get_planet_longitude(jd, "Moon", sidereal=True, aya_type="lahiri")
            asc_lon = get_ascendant(jd, lat, lon, sidereal=True, aya_type="lahiri")
            all_lons = get_all_planet_longitudes(jd, sidereal=True, aya_type="lahiri")
            method = "lahiri_swisseph"
        else:
            raise ImportError("swisseph unavailable")
    except Exception:
        sun_lon = sun_ecliptic_longitude_deg(jd)
        moon_lon = moon_ecliptic_longitude_deg(jd)
        asc_lon = ascendant_longitude_deg(jd, lat, lon)
        all_lons = {}

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
        "method": method,
        "ayanamsa": "lahiri",
        "place_input": birth_place,
        "lat": lat, "lon": lon, "tz": tz_name,
        "tz_offset_hours": tz_offset,
        "local_datetime": dt_local.isoformat(),
        "utc_datetime": dt_utc.isoformat(),
        "jd": jd,
        "sun_lon_deg": sun_lon,
        "moon_lon_deg": moon_lon,
        "asc_lon_deg": asc_lon,
        "planet_longitudes": all_lons,
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


# ── Chart-accurate predictions (AstroSage-style, unique per Kundli) ───

_PLANET_LABELS = {
    "sun": "Sun", "moon": "Moon", "mars": "Mars", "mercury": "Mercury",
    "venus": "Venus", "jupiter": "Jupiter", "saturn": "Saturn",
    "rahu": "Rahu", "ketu": "Ketu",
}

_DASHA_THEMES = {
    "Sun": "authority, visibility, and father/mentor themes",
    "Moon": "emotions, home, mother, and public mood",
    "Mars": "courage, property disputes, siblings, and decisive action",
    "Mercury": "business, communication, studies, and skill-building",
    "Jupiter": "wisdom, children, dharma, and expansion",
    "Venus": "marriage, luxury, arts, and partnership income",
    "Saturn": "discipline, delays that mature you, service, and karma",
    "Rahu": "ambition, foreign links, technology, and unconventional paths",
    "Ketu": "spirituality, detachment, research, and letting go",
}


def _zodiac_index(sign: str) -> int:
    try:
        return ZODIAC_ORDER.index(sign)
    except ValueError:
        return 0


def _sign_on_house(lagna: str, house_num: int) -> str:
    if not lagna or lagna.startswith("Unknown") or house_num < 1 or house_num > 12:
        return "—"
    return ZODIAC_ORDER[(_zodiac_index(lagna) + house_num - 1) % 12]


def _lord_of_house(lagna: str, house_num: int) -> str:
    sign = _sign_on_house(lagna, house_num)
    return SIGN_RULERS.get(sign, "—") if sign != "—" else "—"


def _planets_in_house(houses: Dict[str, int], house_num: int) -> List[str]:
    hits = []
    for key, hn in (houses or {}).items():
        if hn == house_num:
            hits.append(_PLANET_LABELS.get(key, key.title()))
    return hits


def _house_phrase(house_num: int) -> str:
    return HOUSE_MEANINGS.get(house_num, f"House {house_num} themes")


def _nakshatra_meta(name: str) -> Dict[str, str]:
    for n in NAKSHATRA_DATA:
        if n["name"].lower() == (name or "").lower():
            return n
    return {}


def _dignity_label(strength: Dict[str, Any], planet: str) -> str:
    info = (strength or {}).get(planet) or {}
    dignity = info.get("dignity") or "neutral"
    strong = info.get("is_strong", False)
    if dignity == "Exalted":
        return f"{planet} is exalted (very strong)"
    if dignity == "Debilitated":
        return f"{planet} is debilitated (needs conscious effort)"
    if dignity in ("Own Sign", "Moolatrikona"):
        return f"{planet} is in {dignity.lower()} (strong)"
    if strong:
        return f"{planet} is well-placed"
    return f"{planet} is in {dignity.lower()} strength"


def _join_planets(names: List[str]) -> str:
    if not names:
        return "no major graha"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def build_vedic_prediction(
    full_name: str,
    birth_place: str,
    profile: Dict[str, str],
    palm_text: Optional[str],
    birth_date: date,
    now: datetime,
    blueprint: Dict[str, Any],
    vedic: Dict[str, Any],
) -> Dict[str, str]:
    """
    Build unique life-area readings from the user's actual Kundli:
    whole-sign houses, planetary signs, nakshatra, dasha, yogas, dignity, vargas.
    """
    lagna = profile.get("ascendant") or vedic.get("lagna_sign") or "—"
    sun_sign = profile.get("zodiac") or "—"
    moon_sign = profile.get("moon_sign") or "—"
    houses = vedic.get("houses") or {}
    signs = vedic.get("planet_signs") or {}
    strength = vedic.get("strength") or {}
    yogas = vedic.get("yogas") or {}
    vargas = vedic.get("vargas") or {}

    sun_h = houses.get("sun")
    moon_h = houses.get("moon")
    mars_h = houses.get("mars")
    merc_h = houses.get("mercury")
    venus_h = houses.get("venus")
    jup_h = houses.get("jupiter")
    sat_h = houses.get("saturn")
    rahu_h = houses.get("rahu")
    ketu_h = houses.get("ketu")

    nak = vedic.get("nakshatra") or ""
    nak_lord = vedic.get("nakshatra_lord") or ""
    nak_pada = vedic.get("nakshatra_pada") or ""
    nak_meta = _nakshatra_meta(nak)
    nak_meaning = nak_meta.get("meaning", "a distinct karmic rhythm")

    maha = vedic.get("mahadasha") or ""
    antar = vedic.get("antardasha_demo") or ""
    praty = vedic.get("pratyantardasha") or ""
    doshas = vedic.get("dosha_flags") or []

    h10_planets = _planets_in_house(houses, 10)
    h7_planets = _planets_in_house(houses, 7)
    h5_planets = _planets_in_house(houses, 5)
    h6_planets = _planets_in_house(houses, 6)
    h4_planets = _planets_in_house(houses, 4)
    h11_planets = _planets_in_house(houses, 11)
    h1_planets = _planets_in_house(houses, 1)

    sign_10 = _sign_on_house(lagna, 10)
    lord_10 = _lord_of_house(lagna, 10)
    sign_7 = _sign_on_house(lagna, 7)
    lord_7 = _lord_of_house(lagna, 7)

    d9_venus = (vargas.get("Venus") or {}).get("navamsa", "")
    d9_moon = (vargas.get("Moon") or {}).get("navamsa", "")
    d10_saturn = (vargas.get("Saturn") or {}).get("dashamsha", "")
    d10_sun = (vargas.get("Sun") or {}).get("dashamsha", "")

    yoga_names = [y.get("name", "") for y in (yogas.get("yogas") or [])[:4] if y.get("name")]

    ashtak = {}
    if signs and lagna and not str(lagna).startswith("Unknown"):
        try:
            ashtak = compute_ashtakavarga(signs, lagna, moon_sign)
        except Exception:
            ashtak = {}

    strongest_area = ""
    if ashtak.get("strongest_signs"):
        top = ashtak["strongest_signs"][0]
        strongest_area = f"{top[0]} ({top[1]} bindus in Sarvashtakavarga)"

    transit = vedic.get("transits") or {}
    conf = (transit.get("prediction_confidence") or {}).get("score")
    conf_desc = (transit.get("prediction_confidence") or {}).get("description", "")
    transit_score = transit.get("transit_score")

    personality = (
        f"{full_name}, your chart is calculated in Lahiri sidereal (same ayanamsa default as AstroSage). "
        f"Lagna (Ascendant) is {lagna} — {_house_phrase(1)}. "
        f"Sun in {sun_sign} occupies the {sun_h}th house ({_house_phrase(sun_h or 1)}); "
        f"Moon in {moon_sign} sits in the {moon_h}th house ({_house_phrase(moon_h or 4)}). "
    )
    if h1_planets and h1_planets != ["Sun"]:
        personality += f"Grahas influencing the 1st house: {_join_planets(h1_planets)}. "
    if nak:
        personality += (
            f"Birth Nakshatra {nak} (lord {nak_lord}, pada {nak_pada}) emphasizes {nak_meaning}. "
        )
    if yoga_names:
        personality += f"Active yogas include {', '.join(yoga_names)} — these sharpen your natural gifts. "

    career = (
        f"Career (10th house / Karma Bhava) falls in {sign_10}, ruled by {lord_10}. "
        f"Planets in the 10th: {_join_planets(h10_planets)} — {_house_phrase(10)}. "
        f"{_dignity_label(strength, 'Saturn')} in house {sat_h} ({signs.get('Saturn', '—')}); "
        f"Mercury in house {merc_h} ({signs.get('Mercury', '—')}) shapes skills and negotiation. "
    )
    if d10_saturn or d10_sun:
        career += (
            f"Dashamsha (D10): Sun in {d10_sun or '—'}, Saturn in {d10_saturn or '—'} "
            f"— use D10 for profession sub-themes alongside the 10th lord {lord_10}. "
        )
    if h11_planets:
        career += f"11th-house gains supported by {_join_planets(h11_planets)} ({_house_phrase(11)}). "

    love = (
        f"Marriage & partnerships (7th house) are in {sign_7}, ruled by {lord_7}. "
        f"7th-house occupants: {_join_planets(h7_planets)}. "
        f"Venus in {signs.get('Venus', '—')} (house {venus_h}) and Moon in {moon_sign} (house {moon_h}) "
        f"set emotional needs in relationships. "
    )
    if d9_venus or d9_moon:
        love += f"Navamsa (D9): Venus in {d9_venus or '—'}, Moon in {d9_moon or '—'} — key for spouse temperament. "
    love += (
        f"Synastry hints from Moon sign: harmonious with {blueprint.get('best_matches', '—')}; "
        f"growth lessons with {blueprint.get('growth_signs', '—')}."
    )

    dasha_theme = _DASHA_THEMES.get(maha, "life lessons aligned with your Moon nakshatra")
    future = (
        f"Vimshottari timing: {maha} Mahadasha → {antar} Antardasha → {praty} Pratyantardasha. "
        f"This period highlights {dasha_theme}. "
    )
    if conf is not None:
        future += f"Current transit confidence: {conf}% — {conf_desc} "
    elif transit_score is not None:
        future += f"Gochara favorability score: {transit_score}%. "
    if strongest_area:
        future += f"Strongest collective support flows through {strongest_area}. "
    if palm_text:
        future += "Palm symbolism is layered on top of this chart timing."

    strong_list = [p for p, d in strength.items() if isinstance(d, dict) and d.get("is_strong") and p not in ("Rahu", "Ketu")]
    strengths = (
        f"Chart strengths: {_join_planets(strong_list) if strong_list else 'balanced dignity across grahas'}. "
    )
    if yoga_names:
        strengths += f"Yogas {', '.join(yoga_names)} raise confidence and opportunity when you act ethically. "
    if h5_planets:
        strengths += f"5th house (Purva Punya) activated by {_join_planets(h5_planets)} — creativity and merit. "
    strengths += f"Sun–Moon–Lagna blend ({sun_sign} / {moon_sign} / {lagna}) is your signature; lean into it."

    weak_parts = []
    for p in ("Saturn", "Mars", "Mercury", "Venus", "Jupiter"):
        if ((strength.get(p) or {}).get("dignity")) == "Debilitated":
            weak_parts.append(_dignity_label(strength, p))
    if doshas:
        weak_parts.append("; ".join(doshas))
    if h6_planets:
        weak_parts.append(f"6th-house pressure from {_join_planets(h6_planets)} — manage health and conflict proactively")
    weaknesses = (
        weak_parts[0] if len(weak_parts) == 1 else
        (" ".join(weak_parts) if weak_parts else
         f"Watch overthinking when Moon occupies house {moon_h}; channel {moon_sign} emotions through routine and rest.")
    )

    wellness = (
        f"6th house (Ari Bhava): {_join_planets(h6_planets)} — {_house_phrase(6)}. "
        f"Moon in house {moon_h} ({moon_sign}) shows where stress lodges in the body; "
        f"Mars in house {mars_h} ({signs.get('Mars', '—')}) affects energy and inflammation. "
        f"Honor {ZODIAC_META.get(sun_sign, {}).get('element', 'your')} element; "
        f"lucky day {blueprint.get('lucky_day', '—')} for restorative habits."
    )

    compatibility = (
        f"7th lord {lord_7} in {sign_7} with Venus in {signs.get('Venus', '—')} (house {venus_h}) "
        f"defines partner type you attract. Moon in {moon_sign} needs emotional safety; "
        f"best elemental match signs: {blueprint.get('best_matches', '—')}. "
        f"Ketu in house {ketu_h} and Rahu in house {rahu_h} add karmic relationship lessons — "
        f"choose partners who respect your {lagna} lagna pace."
    )

    seasonal_energy = (
        f"Active dasha {maha}/{antar} colors this season: {_DASHA_THEMES.get(maha, 'steady growth')}. "
    )
    if transit.get("jupiter_transit"):
        jt = transit["jupiter_transit"]
        seasonal_energy += f"Jupiter transit: {jt.get('description', jt.get('quality', ''))}. "
    if transit.get("sade_sati", {}).get("active"):
        seasonal_energy += f"Sade Sati phase: {transit['sade_sati'].get('phase_name', 'active')} — patience and discipline. "
    else:
        seasonal_energy += seasonal_transit_note(now, sun_sign)

    return {
        "personality": personality.strip(),
        "career": career.strip(),
        "love": love.strip(),
        "future": future.strip(),
        "strengths": strengths.strip(),
        "weaknesses": weaknesses.strip(),
        "wellness": wellness.strip(),
        "compatibility": compatibility.strip(),
        "seasonal_energy": seasonal_energy.strip(),
    }


# ── Predictions (legacy sun-sign templates — fallback only) ───────────

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


# ════════════════════════════════════════════════════════════════════
# NEW FEATURE FUNCTIONS — Dasha, Panchanga, Ashtakavarga, Matching
# ════════════════════════════════════════════════════════════════════

def compute_full_dasha(moon_lon_sid: float, birth_jd: float) -> Dict[str, Any]:
    """
    Compute complete Vimshottari Dasha with exact dates.
    Returns mahadasha timeline, current running period, and predictions.

    Parameters
    ----------
    moon_lon_sid : Moon sidereal longitude (degrees)
    birth_jd     : Julian Day of birth (UT)
    """
    if not _DASHA_AVAILABLE:
        return {"error": "Dasha module not available — place dasha.py in vedic/ folder"}

    dasha_data = compute_dasha(moon_lon_sid, birth_jd)
    current = get_current_dasha(dasha_data)

    # Format the mahadasha list for API response (keep compact)
    timeline = []
    for maha in dasha_data.get("mahadasha_list", []):
        antardashas_compact = []
        for antar in maha.get("antardashas", []):
            antardashas_compact.append({
                "lord":       antar["lord"],
                "start_date": antar["start_date"],
                "end_date":   antar["end_date"],
                "months":     antar["months"],
                "is_current": antar["is_current"],
                "prediction": antar["prediction"],
                # Pratyantar only for current antardasha
                "pratyantars": antar.get("pratyantars", []) if antar["is_current"] else [],
            })
        timeline.append({
            "lord":        maha["lord"],
            "start_date":  maha["start_date"],
            "end_date":    maha["end_date"],
            "years":       maha["years"],
            "is_current":  maha["is_current"],
            "prediction":  maha["prediction"],
            "antardashas": antardashas_compact,
        })

    return {
        "birth_balance":  dasha_data["birth_balance"],
        "moon_nakshatra": dasha_data["moon_nakshatra"],
        "timeline":       timeline,
        "current": {
            "mahadasha":       current.get("mahadasha"),
            "mahadasha_ends":  current.get("mahadasha_ends"),
            "antardasha":      current.get("antardasha"),
            "antardasha_ends": current.get("antardasha_ends"),
            "pratyantar":      current.get("pratyantar"),
            "pratyantar_ends": current.get("pratyantar_ends"),
            "prediction":      current.get("prediction", ""),
        },
        "next_change": dasha_data.get("next_change", {}),
    }


def compute_birth_panchanga(
    birth_jd: float,
    lat: float,
    lon: float,
    tz_offset: float = 5.5,
) -> Dict[str, Any]:
    """
    Compute complete Panchanga (Pancha-anga) at the moment of birth.

    Returns Vara, Tithi, Nakshatra, Yoga, Karana, Rahukalam,
    Abhijit Muhurta, Hora, and auspiciousness score.
    """
    if not _PANCHANGA_AVAILABLE:
        return {"error": "Panchanga module not available — place panchanga.py in vedic/ folder"}

    return birth_panchanga(birth_jd, lat, lon, tz_offset)


def compute_ashtakavarga(
    planet_signs: Dict[str, str],
    lagna_sign: str,
    moon_sign: str,
) -> Dict[str, Any]:
    """
    Compute complete Ashtakavarga analysis.

    Parameters
    ----------
    planet_signs : dict of planet → sign name (sidereal)
    lagna_sign   : Ascendant sign
    moon_sign    : Moon sign

    Returns Bhinnashtakavarga, Sarvashtakavarga, life area scores,
    transit quality for Jupiter/Saturn, and interpretation.
    """
    if not _ASHTAK_AVAILABLE:
        return {"error": "Ashtakavarga module not available — place ashtakavarga.py in vedic/ folder"}

    report = ashtakavarga_report(planet_signs, lagna_sign, moon_sign)

    # Format Sarvashtakavarga as sign→score dict for easy frontend use
    sarva_by_sign = {}
    zodiac = [
        "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
        "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
    ]
    for i, sign in enumerate(zodiac):
        sarva_by_sign[sign] = report["sarva"][i]

    return {
        "sarva_by_sign":       sarva_by_sign,
        "total_score":         report["total_score"],
        "average_per_sign":    report["average_per_sign"],
        "sign_analysis":       report["sign_analysis"],
        "life_areas":          report["life_areas"],
        "strongest_signs":     report["strongest_signs"],
        "weakest_signs":       report["weakest_signs"],
        "planet_totals":       report["planet_totals"],
        "jupiter_transit":     report["jupiter_transit_scores"],
        "saturn_transit":      report["saturn_transit_scores"],
        "interpretation":      report["interpretation"],
        # Full Bhinna grid (for advanced display)
        "bhinna": {
            planet: {zodiac[i]: pts for i, pts in enumerate(scores)}
            for planet, scores in report["bhinna"].items()
        },
    }


def compute_compatibility(
    person1_moon_sid: float,
    person2_moon_sid: float,
    person1_planet_houses: Optional[Dict[str, int]] = None,
    person2_planet_houses: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Compute Kundli Matching (36-point Guna Milan) + Mangal Dosha.

    Parameters
    ----------
    person1_moon_sid : Person 1 (boy/groom) sidereal Moon longitude
    person2_moon_sid : Person 2 (girl/bride) sidereal Moon longitude
    person1_planet_houses : dict of planet → house number for person 1
    person2_planet_houses : dict of planet → house number for person 2
    """
    if not _MATCHING_AVAILABLE:
        return {"error": "Kundli matching module not available — place kundli_matching.py in vedic/ folder"}

    result = compute_guna_milan(person1_moon_sid, person2_moon_sid)

    # Add Mangal Dosha for both if house data available
    if person1_planet_houses:
        result["person1_mangal_dosha"] = check_mangal_dosha(person1_planet_houses)
    if person2_planet_houses:
        result["person2_mangal_dosha"] = check_mangal_dosha(person2_planet_houses)

    return result


# ── Enhanced build_report_html with new sections ─────────────────────

def build_report_html_v2(
    name: str,
    profile: Dict[str, str],
    sections: Dict[str, str],
    palm_text: Optional[str],
    dasha_data: Optional[Dict[str, Any]] = None,
    panchanga_data: Optional[Dict[str, Any]] = None,
    ashtakavarga_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Enhanced report HTML including Dasha timeline, Panchanga, and Ashtakavarga sections.
    Backward-compatible — falls back to build_report_html if new data not provided.
    """
    # Build base HTML
    base_html = build_report_html(name, profile, sections, palm_text)

    extra_sections: List[str] = []

    # ── Dasha section ──────────────────────────────────────────
    if dasha_data and not dasha_data.get("error"):
        cur = dasha_data.get("current", {})
        bb  = dasha_data.get("birth_balance", {})
        maha   = cur.get("mahadasha", "")
        antar  = cur.get("antardasha", "")
        prat   = cur.get("pratyantar", "")
        pred   = cur.get("prediction", "")
        maha_ends = cur.get("mahadasha_ends", "")
        antar_ends = cur.get("antardasha_ends", "")

        dasha_html = (
            '<article class="report-section-card" id="dasha-section">'
            '<div class="report-section-heading">'
            '<span class="report-icon">⏱</span><h3>Vimshottari Dasha — Exact Timeline</h3></div>'
            f"<p class='report-copy'><strong>Birth Balance:</strong> {escape(bb.get('message',''))}</p>"
            f"<p class='report-copy'><strong>Currently Running:</strong> "
            f"{escape(maha)} Mahadasha → {escape(antar)} Antardasha → {escape(prat)} Pratyantar</p>"
            f"<p class='report-copy'><strong>Mahadasha ends:</strong> {escape(maha_ends)} | "
            f"<strong>Antardasha ends:</strong> {escape(antar_ends)}</p>"
            f"<p class='report-copy'>{escape(pred)}</p>"
            "</article>"
        )
        extra_sections.append(dasha_html)

    # ── Panchanga section ──────────────────────────────────────
    if panchanga_data and not panchanga_data.get("error"):
        vara    = panchanga_data.get("vara", {})
        tithi   = panchanga_data.get("tithi", {})
        nak     = panchanga_data.get("nakshatra", {})
        yoga    = panchanga_data.get("yoga", {})
        karana  = panchanga_data.get("karana", {})
        timing  = panchanga_data.get("timing", {})
        rahu    = timing.get("rahukalam", {})
        abhijit = timing.get("abhijit_muhurta", {})
        score   = panchanga_data.get("auspiciousness_score", {})

        panch_html = (
            '<article class="report-section-card" id="panchanga-section">'
            '<div class="report-section-heading">'
            '<span class="report-icon">📅</span><h3>Birth Panchanga (Pancha-anga)</h3></div>'
            '<div class="panchanga-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0">'
            f'<div><strong>Vara:</strong> {escape(vara.get("name",""))} ({escape(vara.get("lord",""))})</div>'
            f'<div><strong>Tithi:</strong> {escape(tithi.get("name",""))} — {escape(tithi.get("paksha",""))}</div>'
            f'<div><strong>Nakshatra:</strong> {escape(nak.get("name",""))} Pada {nak.get("pada","")} ({escape(nak.get("lord",""))})</div>'
            f'<div><strong>Yoga:</strong> {escape(yoga.get("name",""))} ({escape(yoga.get("quality",""))})</div>'
            f'<div><strong>Karana:</strong> {escape(karana.get("name",""))}</div>'
            f'<div><strong>Auspiciousness:</strong> {escape(score.get("label",""))}</div>'
            '</div>'
            f"<p class='report-copy'>{escape(score.get('recommendation',''))}</p>"
            "</article>"
        )
        extra_sections.append(panch_html)

    # ── Ashtakavarga section ────────────────────────────────────
    if ashtakavarga_data and not ashtakavarga_data.get("error"):
        avg    = ashtakavarga_data.get("average_per_sign", 0)
        interp = ashtakavarga_data.get("interpretation", "")
        strong = ashtakavarga_data.get("strongest_signs", [])
        weak   = ashtakavarga_data.get("weakest_signs", [])

        strong_str = ", ".join(f"{s[0]} ({s[1]} pts)" for s in strong[:3])
        weak_str   = ", ".join(f"{s[0]} ({s[1]} pts)" for s in weak[:3])

        ashtak_html = (
            '<article class="report-section-card" id="ashtakavarga-section">'
            '<div class="report-section-heading">'
            '<span class="report-icon">⭐</span><h3>Ashtakavarga — Planetary Strength Grid</h3></div>'
            f"<p class='report-copy'><strong>Sarvashtakavarga Average:</strong> {avg}/28 per sign</p>"
            f"<p class='report-copy'><strong>Strongest Signs:</strong> {escape(strong_str)}</p>"
            f"<p class='report-copy'><strong>Challenging Signs:</strong> {escape(weak_str)}</p>"
            f"<p class='report-copy'>{escape(interp)}</p>"
            "</article>"
        )
        extra_sections.append(ashtak_html)

    if not extra_sections:
        return base_html

    # Insert extra sections before closing — find the last </article> and append after
    insert_html = "\n".join(extra_sections)
    # Append at end of base HTML
    return base_html + "\n" + insert_html