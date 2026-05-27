"""
vedic/panchanga.py
──────────────────
Complete Vedic Panchanga (Hindu almanac) for any date/time/place.

The five limbs (Pancha-anga):
  1. Vara      — Day of the week (7 days, each ruled by a planet)
  2. Tithi     — Lunar day (30 per lunar month, 1–30)
  3. Nakshatra — Moon's asterism (27 nakshatras)
  4. Yoga      — Sun+Moon longitude sum divided into 27 parts
  5. Karana    — Half-tithi (60 per lunar month, 11 fixed + 4 repeating)

Also includes:
  • Rahukalam   — Inauspicious daily period
  • Yamagandam  — Another inauspicious period
  • Abhijit     — Most auspicious Muhurta (~noon)
  • Lunar month — Chaitra, Vaisakha, etc.
  • Paksha      — Shukla (waxing) or Krishna (waning)
  • Hora        — Planetary hours

Public API
──────────
    compute_panchanga(jd, lat, lon, tz_offset) → dict
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ── Nakshatra data ───────────────────────────────────────────────────

NAKSHATRAS: List[Dict[str, Any]] = [
    {"name": "Ashwini",      "lord": "Ketu",    "deity": "Ashwini Kumaras", "symbol": "Horse head"},
    {"name": "Bharani",      "lord": "Venus",   "deity": "Yama",            "symbol": "Yoni"},
    {"name": "Krittika",     "lord": "Sun",     "deity": "Agni",            "symbol": "Razor/flame"},
    {"name": "Rohini",       "lord": "Moon",    "deity": "Brahma",          "symbol": "Chariot"},
    {"name": "Mrigashira",   "lord": "Mars",    "deity": "Soma",            "symbol": "Deer head"},
    {"name": "Ardra",        "lord": "Rahu",    "deity": "Rudra",           "symbol": "Teardrop"},
    {"name": "Punarvasu",    "lord": "Jupiter", "deity": "Aditi",           "symbol": "Quiver"},
    {"name": "Pushya",       "lord": "Saturn",  "deity": "Brihaspati",      "symbol": "Lotus/flower"},
    {"name": "Ashlesha",     "lord": "Mercury", "deity": "Nagas",           "symbol": "Serpent"},
    {"name": "Magha",        "lord": "Ketu",    "deity": "Pitrus",          "symbol": "Royal throne"},
    {"name": "Purva Phalguni","lord": "Venus",  "deity": "Bhaga",           "symbol": "Hammock/fig tree"},
    {"name": "Uttara Phalguni","lord": "Sun",   "deity": "Aryaman",         "symbol": "Bed/four legs"},
    {"name": "Hasta",        "lord": "Moon",    "deity": "Savitri",         "symbol": "Open hand"},
    {"name": "Chitra",       "lord": "Mars",    "deity": "Vishwakarma",     "symbol": "Bright jewel"},
    {"name": "Swati",        "lord": "Rahu",    "deity": "Vayu",            "symbol": "Coral/sword"},
    {"name": "Vishakha",     "lord": "Jupiter", "deity": "Indra-Agni",      "symbol": "Triumphal arch"},
    {"name": "Anuradha",     "lord": "Saturn",  "deity": "Mitra",           "symbol": "Lotus"},
    {"name": "Jyeshtha",     "lord": "Mercury", "deity": "Indra",           "symbol": "Earring/umbrella"},
    {"name": "Mula",         "lord": "Ketu",    "deity": "Nirriti",         "symbol": "Bunch of roots"},
    {"name": "Purva Ashadha","lord": "Venus",   "deity": "Apas",            "symbol": "Fan/tusk"},
    {"name": "Uttara Ashadha","lord": "Sun",    "deity": "Vishvedevas",     "symbol": "Elephant tusk"},
    {"name": "Shravana",     "lord": "Moon",    "deity": "Vishnu",          "symbol": "Three footprints"},
    {"name": "Dhanishta",    "lord": "Mars",    "deity": "Eight Vasus",     "symbol": "Drum/flute"},
    {"name": "Shatabhisha",  "lord": "Rahu",    "deity": "Varuna",          "symbol": "Empty circle"},
    {"name": "Purva Bhadrapada","lord": "Jupiter","deity":"Ajaikapada",     "symbol": "Sword/front of funeral cot"},
    {"name": "Uttara Bhadrapada","lord": "Saturn","deity":"Ahirbudhanya",   "symbol": "Twins/back of funeral cot"},
    {"name": "Revati",       "lord": "Mercury", "deity": "Pushan",          "symbol": "Fish/drum"},
]

# ── Tithi names ──────────────────────────────────────────────────────

TITHI_NAMES: List[str] = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima/Amavasya",
]

TITHI_LORDS: List[str] = [
    "Mars", "Venus", "Jupiter", "Mercury", "Sun",
    "Saturn", "Moon", "Rahu", "Sun", "Moon",
    "Mars", "Mercury", "Jupiter", "Venus", "Saturn",
]

# ── Yoga names ───────────────────────────────────────────────────────

YOGA_NAMES: List[str] = [
    "Vishkambha", "Preeti",    "Ayushman",  "Saubhagya", "Shobhana",
    "Atiganda",   "Sukarman",  "Dhriti",    "Shula",     "Ganda",
    "Vriddhi",    "Dhruva",    "Vyaghata",  "Harshana",  "Vajra",
    "Siddhi",     "Vyatipata", "Variyana",  "Parigha",   "Shiva",
    "Siddha",     "Sadhya",    "Shubha",    "Shukla",    "Brahma",
    "Indra",      "Vaidhriti",
]

YOGA_QUALITY: List[str] = [
    "Inauspicious", "Auspicious",   "Auspicious",   "Auspicious",  "Auspicious",
    "Inauspicious", "Auspicious",   "Auspicious",   "Inauspicious","Inauspicious",
    "Auspicious",   "Auspicious",   "Inauspicious", "Auspicious",  "Inauspicious",
    "Auspicious",   "Inauspicious", "Auspicious",   "Inauspicious","Auspicious",
    "Auspicious",   "Auspicious",   "Auspicious",   "Auspicious",  "Auspicious",
    "Auspicious",   "Inauspicious",
]

# ── Karana names ─────────────────────────────────────────────────────

# Fixed karanas (occur once in a lunar month)
_FIXED_KARANAS = ["Kimstughna", "Sakuni", "Chatushpada", "Naga"]
# Repeating karanas (cycle 8 times through the month)
_MOVING_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Garija", "Vanija", "Vishti"]

# ── Vara (weekday) ───────────────────────────────────────────────────

VARA_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
VARA_LORDS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
VARA_QUALITY = [
    "Auspicious for government, authority, health matters",
    "Auspicious for travel, new ventures, water-related work",
    "Auspicious for courage, surgery, land dealings",
    "Auspicious for communication, education, writing",
    "Auspicious for wealth, religious activities, expansion",
    "Auspicious for love, arts, luxury goods, marriage",
    "Auspicious for discipline, service, long-term investments",
]

# ── Lunar months ─────────────────────────────────────────────────────

LUNAR_MONTHS = [
    "Chaitra", "Vaisakha", "Jyeshtha", "Ashadha",
    "Shravana", "Bhadrapada", "Ashwin", "Kartika",
    "Margashirsha", "Pausha", "Magha", "Phalguna",
]

# ── Rahukalam timings (fraction of daylight from sunrise) ────────────

# Day of week (0=Sun..6=Sat) → rahukalam start fraction, duration fraction
_RAHUKALAM_TABLE = {
    0: 0.875,   # Sunday    — last 1/8 of day
    1: 0.125,   # Monday    — 2nd 1/8
    2: 0.750,   # Tuesday   — 7th 1/8
    3: 0.500,   # Wednesday — 5th 1/8
    4: 0.625,   # Thursday  — 6th 1/8
    5: 0.375,   # Friday    — 4th 1/8
    6: 0.250,   # Saturday  — 3rd 1/8
}

_YAMAGANDAM_TABLE = {
    0: 0.250, 1: 0.500, 2: 0.625, 3: 0.875,
    4: 0.000, 5: 0.750, 6: 0.375,
}

# ── Utility math ─────────────────────────────────────────────────────

def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x

def _sun_tropical(jd: float) -> float:
    n = jd - 2451545.0
    L = _norm360(280.460 + 0.9856474 * n)
    g = _norm360(357.528 + 0.9856003 * n)
    return _norm360(L + 1.915*math.sin(math.radians(g)) + 0.020*math.sin(math.radians(2*g)))

def _moon_tropical(jd: float) -> float:
    n = jd - 2451545.0
    L0 = _norm360(218.3164477 + 13.17639648 * n)
    Mm = _norm360(134.9633964 + 13.06499295 * n)
    Ms = _norm360(357.5291092 + 0.98560028 * n)
    D  = _norm360(297.8501921 + 12.19074912 * n)
    F  = _norm360(93.2720950  + 13.22935024 * n)
    Om = _norm360(125.0445479 - 0.05295378 * n)
    def r(x): return math.radians(x)
    return _norm360(L0 + 6.2886*math.sin(r(Mm)) + 1.2740*math.sin(r(2*D-Mm))
        + 0.6583*math.sin(r(2*D)) + 0.2136*math.sin(r(2*Mm)) - 0.1851*math.sin(r(Ms))
        - 0.1143*math.sin(r(2*F)) + 0.0588*math.sin(r(2*D-2*Mm))
        + 0.0572*math.sin(r(2*D-Ms-Mm)) + 0.0533*math.sin(r(2*D+Mm))
        - 0.0459*math.sin(r(2*D-Ms)) + 0.0410*math.sin(r(Mm-Ms))
        + 0.0347*math.sin(r(D)) - 0.0304*math.sin(r(2*F+Mm))
        - 0.0270*math.sin(r(2*D+Ms)) + 0.0175*math.sin(r(Om)))

def _lahiri_ayanamsa(jd: float) -> float:
    return 23.85305 + (50.27/3600.0) * ((jd - 2451545.0) / 365.25)

def _gmst_hours(jd: float) -> float:
    T = (jd - 2451545.0) / 36525.0
    gmst = 6.697374558 + 2400.051336*T + 0.000025862*T*T
    frac = (jd + 0.5) % 1.0
    gmst += 24.06570982441908 * frac
    return gmst % 24.0

def _sunrise_jd(jd_noon: float, lat: float, lon: float) -> float:
    """Approximate sunrise Julian Day."""
    decl = math.radians(23.45 * math.sin(math.radians(360/365*(jd_noon-2451545.0+284))))
    cos_h = -math.tan(math.radians(lat)) * math.tan(decl)
    cos_h = max(-1.0, min(1.0, cos_h))
    hour_angle = math.degrees(math.acos(cos_h))
    # Sunrise: noon - hour_angle/15 hours
    return jd_noon - hour_angle/360.0

def _sunset_jd(jd_noon: float, lat: float, lon: float) -> float:
    decl = math.radians(23.45 * math.sin(math.radians(360/365*(jd_noon-2451545.0+284))))
    cos_h = -math.tan(math.radians(lat)) * math.tan(decl)
    cos_h = max(-1.0, min(1.0, cos_h))
    hour_angle = math.degrees(math.acos(cos_h))
    return jd_noon + hour_angle/360.0

# ── Main Panchanga function ──────────────────────────────────────────

def compute_panchanga(
    jd: float,
    lat: float,
    lon: float,
    tz_offset_hours: float = 5.5,
) -> Dict[str, Any]:
    """
    Compute complete Vedic Panchanga for a given Julian Day (UT).

    Parameters
    ----------
    jd              : Julian Day (Universal Time)
    lat, lon        : Geographic coordinates
    tz_offset_hours : Local timezone offset (default: IST = +5.5)

    Returns
    -------
    Complete panchanga dictionary.
    """
    used_swisseph = False
    sun_sid = moon_sid = sun_trop = moon_trop = 0.0
    try:
        from vedic.swisseph_engine import SWISSEPH_AVAILABLE, get_planet_longitude
        if SWISSEPH_AVAILABLE:
            sun_sid = get_planet_longitude(jd, "Sun", sidereal=True, aya_type="lahiri")
            moon_sid = get_planet_longitude(jd, "Moon", sidereal=True, aya_type="lahiri")
            sun_trop = get_planet_longitude(jd, "Sun", sidereal=False)
            moon_trop = get_planet_longitude(jd, "Moon", sidereal=False)
            used_swisseph = True
    except Exception:
        pass
    if not used_swisseph:
        aya = _lahiri_ayanamsa(jd)
        sun_trop = _sun_tropical(jd)
        moon_trop = _moon_tropical(jd)
        sun_sid = _norm360(sun_trop - aya)
        moon_sid = _norm360(moon_trop - aya)

    # ── 1. VARA (Weekday) ──────────────────────────────────────
    # JD 0 = Monday noon. Weekday from JD integer + tz adjustment
    local_jd = jd + tz_offset_hours / 24.0
    weekday = int(local_jd + 1.5) % 7   # 0=Sunday, 1=Monday...
    vara = {
        "name": VARA_NAMES[weekday],
        "lord": VARA_LORDS[weekday],
        "quality": VARA_QUALITY[weekday],
        "index": weekday,
    }

    # ── 2. TITHI (Lunar day) ───────────────────────────────────
    moon_sun_diff = _norm360(moon_sid - sun_sid)
    tithi_num = int(moon_sun_diff / 12.0)   # 0-based, 0-29
    tithi_frac = (moon_sun_diff % 12.0) / 12.0
    paksha = "Shukla (Waxing)" if tithi_num < 15 else "Krishna (Waning)"
    tithi_in_paksha = tithi_num % 15          # 0-14
    tithi_name_base = TITHI_NAMES[tithi_in_paksha]
    if tithi_num == 14:
        tithi_display = "Purnima (Full Moon)"
    elif tithi_num == 29:
        tithi_display = "Amavasya (New Moon)"
    else:
        tithi_display = tithi_name_base

    tithi_lord = TITHI_LORDS[tithi_in_paksha]
    tithi = {
        "name": tithi_display,
        "number": tithi_num + 1,             # 1-based for display
        "paksha": paksha,
        "lord": tithi_lord,
        "fraction_elapsed": round(tithi_frac, 3),
        "paksha_day": tithi_in_paksha + 1,
    }

    # ── 3. NAKSHATRA (Moon's asterism) ─────────────────────────
    nak_span = 360.0 / 27.0
    nak_idx = int(moon_sid / nak_span) % 27
    nak_deg_in = moon_sid % nak_span
    nak_frac = nak_deg_in / nak_span
    pada = min(int(nak_frac * 4) + 1, 4)
    nak_data = NAKSHATRAS[nak_idx]
    nakshatra = {
        "name": nak_data["name"],
        "lord": nak_data["lord"],
        "deity": nak_data["deity"],
        "symbol": nak_data["symbol"],
        "pada": pada,
        "index": nak_idx + 1,               # 1-based
        "degree": round(nak_deg_in, 2),
        "fraction_elapsed": round(nak_frac, 3),
    }

    # ── 4. YOGA (Sun+Moon combination) ─────────────────────────
    yoga_lon = _norm360(sun_sid + moon_sid)
    yoga_idx = int(yoga_lon / (360.0/27.0)) % 27
    yoga = {
        "name": YOGA_NAMES[yoga_idx],
        "index": yoga_idx + 1,
        "quality": YOGA_QUALITY[yoga_idx],
        "longitude": round(yoga_lon, 2),
    }

    # ── 5. KARANA (Half-tithi) ─────────────────────────────────
   

    karana_num = math.floor(moon_sun_diff / 6.0)  # 0-59 for the full month
    karana_name = _karana_name(karana_num)
    karana = {
        "name": karana_name,
        "number": karana_num + 1,
    }

    # ── LUNAR MONTH ────────────────────────────────────────────
    sun_sign_idx = int(sun_sid / 30) % 12
    lunar_month = LUNAR_MONTHS[sun_sign_idx]

    # ── RAHUKALAM & YAMAGANDAM ─────────────────────────────────
    jd_noon = math.floor(jd) + 0.5 + lon/360.0 - tz_offset_hours/24.0
    sunrise = _sunrise_jd(jd_noon, lat, lon)
    sunset  = _sunset_jd(jd_noon, lat, lon)
    day_duration = sunset - sunrise   # in days

    rahu_start_frac  = _RAHUKALAM_TABLE.get(weekday, 0.875)
    yama_start_frac  = _YAMAGANDAM_TABLE.get(weekday, 0.250)

    rahu_start_jd  = sunrise + rahu_start_frac * day_duration
    rahu_end_jd    = rahu_start_jd + day_duration / 8.0
    yama_start_jd  = sunrise + yama_start_frac * day_duration
    yama_end_jd    = yama_start_jd + day_duration / 8.0
    abhijit_start  = (sunrise + sunset) / 2.0 - day_duration/16.0
    abhijit_end    = abhijit_start + day_duration/8.0

    def _jd_to_time_str(jd_val: float) -> str:
        frac = (jd_val + 0.5 + tz_offset_hours/24.0) % 1.0
        total_min = int(frac * 1440)
        h, m = divmod(total_min, 60)
        return f"{h:02d}:{m:02d}"

    timing = {
        "sunrise": _jd_to_time_str(sunrise),
        "sunset": _jd_to_time_str(sunset),
        "rahukalam": {
            "start": _jd_to_time_str(rahu_start_jd),
            "end":   _jd_to_time_str(rahu_end_jd),
            "note":  "Avoid starting new ventures during Rahukalam",
        },
        "yamagandam": {
            "start": _jd_to_time_str(yama_start_jd),
            "end":   _jd_to_time_str(yama_end_jd),
        },
        "abhijit_muhurta": {
            "start": _jd_to_time_str(abhijit_start),
            "end":   _jd_to_time_str(abhijit_end),
            "note":  "Most auspicious period of the day — excellent for important beginnings",
        },
    }

    # ── HORA (Planetary hours) ─────────────────────────────────
    hora = _compute_hora(weekday, sunrise, sunset, jd, tz_offset_hours)

    # ── AUSPICIOUSNESS SCORE ───────────────────────────────────
    score = _auspiciousness_score(vara, tithi, nakshatra, yoga)

    # ── Summary text ───────────────────────────────────────────
    summary = _panchanga_summary(vara, tithi, nakshatra, yoga, karana, score)

    return {
        "vara": vara,
        "tithi": tithi,
        "nakshatra": nakshatra,
        "yoga": yoga,
        "karana": karana,
        "lunar_month": lunar_month,
        "paksha": paksha,
        "sun_sign": _sign_name(int(sun_sid/30)),
        "moon_sign": _sign_name(int(moon_sid/30)),
        "sun_longitude": round(sun_sid, 3),
        "moon_longitude": round(moon_sid, 3),
        "timing": timing,
        "hora": hora,
        "auspiciousness_score": score,
        "summary": summary,
    }


def _sign_name(idx: int) -> str:
    signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
             "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    return signs[idx % 12]


def _karana_name(karana_num: int) -> str:
    """Return Karana name for karana number 0-59."""
    if karana_num == 0:
        return _FIXED_KARANAS[0]   # Kimstughna (only at start of Shukla Pratipada)
    elif karana_num >= 57:
        return _FIXED_KARANAS[karana_num - 57 + 1]
    else:
       return _MOVING_KARANAS[(karana_num - 1) % 7]


def _compute_hora(
    weekday: int, sunrise_jd: float, sunset_jd: float,
    current_jd: float, tz_offset: float,
) -> Dict[str, Any]:
    """Compute current planetary hour (Hora)."""
    # Day hora sequence starts from weekday planet
    _HORA_SEQ = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
    start_idx = [0, 2, 4, 6, 1, 3, 5][weekday]  # Start for each day

    day_duration = sunset_jd - sunrise_jd
    hora_duration = day_duration / 12.0

    # Time elapsed since sunrise
    elapsed = current_jd - sunrise_jd
    if 0 <= elapsed < day_duration:
        hora_num = int(elapsed / hora_duration)
        lord = _HORA_SEQ[(start_idx + hora_num) % 7]
        next_hora_start = sunrise_jd + (hora_num + 1) * hora_duration

        def _jd_time(jd_v):
            frac = (jd_v + 0.5 + tz_offset/24.0) % 1.0
            total_min = int(frac * 1440)
            h, m = divmod(total_min, 60)
            return f"{h:02d}:{m:02d}"

        return {
            "lord": lord,
            "hora_number": hora_num + 1,
            "ends_at": _jd_time(next_hora_start),
            "note": f"{lord} hora — favorable for {_hora_activity(lord)}",
        }
    return {"lord": "Unknown", "note": "Outside daytime hours"}


_HORA_ACTIVITIES = {
    "Sun":     "government, authority, health, confidence",
    "Moon":    "travel, emotions, water, family matters",
    "Mars":    "energy, sports, surgery, land deals",
    "Mercury": "communication, business, learning, writing",
    "Jupiter": "religion, teaching, wealth, marriage",
    "Venus":   "arts, romance, luxury, entertainment",
    "Saturn":  "discipline, service, agriculture, endings",
}

def _hora_activity(lord: str) -> str:
    return _HORA_ACTIVITIES.get(lord, "general activities")


def _auspiciousness_score(vara, tithi, nakshatra, yoga) -> Dict[str, Any]:
    """Score the day's auspiciousness (0–100)."""
    score = 50  # neutral baseline

    # Yoga contribution
    yoga_q = yoga.get("quality", "Inauspicious")
    score += 15 if yoga_q == "Auspicious" else -10

    # Tithi contribution
    t_num = tithi.get("paksha_day", 1)
    if t_num in {2, 3, 5, 7, 10, 11, 13}:  # generally auspicious tithis
        score += 10
    elif t_num in {4, 6, 8, 9, 12, 14}:    # generally inauspicious
        score -= 8

    # Nakshatra contribution
    nak_lord = nakshatra.get("lord", "")
    if nak_lord in {"Jupiter", "Venus", "Moon"}:
        score += 10
    elif nak_lord in {"Saturn", "Rahu", "Ketu"}:
        score -= 5

    # Vara contribution
    vara_lord = vara.get("lord", "")
    if vara_lord in {"Jupiter", "Venus"}:
        score += 10
    elif vara_lord in {"Saturn", "Mars"}:
        score -= 5

    score = max(0, min(100, score))

    if score >= 75:
        label = "Highly Auspicious"
        recommendation = "Excellent day for new beginnings, ceremonies, important decisions."
    elif score >= 55:
        label = "Moderately Auspicious"
        recommendation = "Generally good day. Avoid Rahukalam for major decisions."
    elif score >= 40:
        label = "Mixed"
        recommendation = "Proceed with caution. Use Abhijit Muhurta for important work."
    else:
        label = "Challenging"
        recommendation = "Avoid new beginnings. Good for completion, reflection, spiritual practice."

    return {"score": score, "label": label, "recommendation": recommendation}


def _panchanga_summary(vara, tithi, nakshatra, yoga, karana, score) -> str:
    return (
        f"Today is {vara['name']} ({vara['lord']}), "
        f"{tithi['paksha']} {tithi['name']} (Tithi {tithi['paksha_day']}), "
        f"Moon in {nakshatra['name']} Nakshatra Pada {nakshatra['pada']} "
        f"(lord: {nakshatra['lord']}), "
        f"{yoga['name']} Yoga ({yoga['quality']}), "
        f"{karana['name']} Karana. "
        f"Day is {score['label']}. {score['recommendation']}"
    )


# ── Birth Panchanga (from birth chart) ──────────────────────────────

def birth_panchanga(
    jd: float,
    lat: float = 0.0,
    lon: float = 0.0,
    tz_offset_hours: float = 5.5,
) -> Dict[str, Any]:
    """Full panchanga at the moment of birth."""
    return compute_panchanga(jd, lat, lon, tz_offset_hours)
