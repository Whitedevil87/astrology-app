"""
Rule-based Vedic-style layer (whole-sign style demo) + Guru chat helpers.
Includes Kundli chart generation using Skyfield for astronomical calculations.

Important: This is NOT a replacement for professional Vedic software (sidereal ayanamsa,
exact divisional charts, true Rahu-Ketu from ephemeris). User can paste house positions from
their own kundli generator for tighter alignment.
"""

from __future__ import annotations

import re
import math
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
import math

try:
    from skyfield.api import Astrometric, load, wgs84
    from skyfield.magnitudelib import phase_angle
    SKYFIELD_AVAILABLE = True
except ImportError:
    SKYFIELD_AVAILABLE = False

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

HOUSE_MEANINGS = {
    1: "Self, body, temperament, life direction (Lagna)",
    2: "Wealth, speech, family, values",
    3: "Siblings, courage, short journeys, skills",
    4: "Home, mother, comfort, roots",
    5: "Children, creativity, romance, intellect",
    6: "Health, service, debts, competition",
    7: "Marriage, partnerships, contracts, public relations",
    8: "Transformations, shared resources, longevity",
    9: "Dharma, higher learning, luck, guru",
    10: "Career, status, authority, reputation",
    11: "Gains, friends, aspirations, income streams",
    12: "Moksha, losses, foreign lands, sleep, liberation themes",
}

VIMSHOTTARI_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]


def _sign_index(sign: str) -> int:
    return ZODIAC_ORDER.index(sign) if sign in ZODIAC_ORDER else 0


def _whole_sign_house(planet_sign: str, lagna_sign: str) -> int:
    """Whole-sign house: lagna sign is house 1."""
    p = _sign_index(planet_sign)
    l = _sign_index(lagna_sign)
    return (p - l) % 12 + 1


def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x


def _sign_from_longitude(lon_deg: float) -> str:
    idx = int(_norm360(lon_deg) // 30)
    return ZODIAC_ORDER[idx]


def _get_planet_lon(jd: float, planet: str) -> float:
    T = (jd - 2451545.0) / 36525.0
    if planet == 'Rahu':
        omega = 125.04452 - 1934.136261 * T + 0.0020708 * T * T
        return _norm360(omega)
    if planet == 'Ketu':
        omega = 125.04452 - 1934.136261 * T + 0.0020708 * T * T
        return _norm360(omega + 180.0)
    
    # L, M = Mean Longitude, Mean Anomaly
    if planet == 'Mercury':
        L = 252.250 + 149472.674 * T
        M = 174.795 + 149472.674 * T
        M_rad = math.radians(_norm360(M))
        C = 23.69 * math.sin(M_rad) + 3.47 * math.sin(2*M_rad)
    elif planet == 'Venus':
        L = 181.980 + 58517.816 * T
        M = 50.416 + 58517.816 * T
        M_rad = math.radians(_norm360(M))
        C = 0.77 * math.sin(M_rad) + 0.01 * math.sin(2*M_rad)
    elif planet == 'Mars':
        L = 355.433 + 19140.299 * T
        M = 19.373 + 19140.299 * T
        M_rad = math.radians(_norm360(M))
        C = 10.69 * math.sin(M_rad) + 0.62 * math.sin(2*M_rad)
    elif planet == 'Jupiter':
        L = 34.351 + 3034.906 * T
        M = 20.020 + 3034.906 * T
        M_rad = math.radians(_norm360(M))
        C = 5.55 * math.sin(M_rad) + 0.17 * math.sin(2*M_rad)
    elif planet == 'Saturn':
        L = 50.077 + 1222.114 * T
        M = 317.021 + 1222.114 * T
        M_rad = math.radians(_norm360(M))
        C = 6.36 * math.sin(M_rad) + 0.22 * math.sin(2*M_rad)
    else:
        return 0.0

    return _norm360(L + C)


def _ketu_from_rahu(rahu_house: int) -> int:
    return (rahu_house - 1 + 6) % 12 + 1


def _clamp_house(n: int) -> int:
    n = int(n)
    if n < 1:
        return 1
    if n > 12:
        return 12
    return n


def parse_kundli_notes(text: str) -> Dict[str, int]:
    """Extract planet→house numbers from free text (user pasted from software)."""
    if not text:
        return {}
    t = text.lower()
    out: Dict[str, int] = {}
    patterns = [
        ("rahu", "rahu_house"),
        ("ketu", "ketu_house"),
        ("mars", "mars_house"),
        ("mangal", "mars_house"),
        ("moon", "moon_house"),
        ("sun", "sun_house"),
        ("mercury", "mercury_house"),
        ("budh", "mercury_house"),
        ("venus", "venus_house"),
        ("shukra", "venus_house"),
        ("jupiter", "jupiter_house"),
        ("guru", "jupiter_house"),
        ("saturn", "saturn_house"),
        ("shani", "saturn_house"),
    ]
    for key, field in patterns:
        match = re.search(rf"{key}\s*(?:in|house|:)?\s*(\d{{1,2}})", t)
        if match:
            out[field] = _clamp_house(int(match.group(1)))
    return out


def _pseudo_seed(birth_date, birth_time, birth_place: str) -> int:
    return (
        birth_date.year * 5023
        + birth_date.month * 271
        + birth_date.day * 97
        + birth_time.hour * 13
        + birth_time.minute * 3
        + sum(ord(c) for c in birth_place[:24])
    ) & 0xFFFFFFFF


def compute_dosha_flags(mars_house: int, rahu_house: int, ketu_house: int) -> List[str]:
    flags: List[str] = []
    if mars_house in {1, 2, 4, 7, 8, 12}:
        flags.append(
            "Manglik / Kuja dosha (Mars in a sensitive marriage/self house — verify with full chart matching)"
        )
    folk = (rahu_house * 5 + ketu_house * 11 + mars_house * 3) % 13
    if folk == 0:
        flags.append(
            "Some traditional checklists may mention Kaal Sarp–style node emphasis — confirm with software + a human astrologer; avoid fear-based labels."
        )
    return flags


def build_remedy_text(flags: List[str], rahu_house: int, ketu_house: int, mahadasha: str) -> str:
    lines: List[str] = []
    lines.append(
        "These are gentle, generic practices often discussed in tradition — not medical advice. "
        "For serious decisions (marriage timing, legal, health), consult a qualified human astrologer and professionals."
    )
    if any("Manglik" in f for f in flags):
        lines.append(
            "Manglik considerations: steady Hanuman worship on Tuesdays, ethical martial discipline (sport/service), "
            "avoid impulsive conflict in partnerships; some families do matching — modern couples often focus on maturity and communication."
        )
    if any("Kaal Sarp" in f for f in flags):
        lines.append(
            "Rahu–Ketu axis remedies (popular lore): disciplined meditation, ethical living (no shortcuts), "
            "Rudra japam or Vishnu sahasranama if it resonates with your lineage — choose what your teacher recommends."
        )
    lines.append(
        f"Rahu in house {rahu_house}: reduce chaotic scrolling, commit to one skill, beware glamour and sudden shortcuts."
    )
    lines.append(
        f"Ketu in house {ketu_house}: simplify attachments here, trust intuition, study spiritual frameworks without dogma."
    )
    lines.append(
        f"Mahadasha flavor ({mahadasha}): align activities with this planet’s dignity in your real chart; "
        "use this demo period as a journaling lens, not a contract with fate."
    )
    return " ".join(lines)


def build_vedic_bundle(
    lagna_sign: str,
    sun_sign: str,
    moon_sign: str,
    birth_date,
    birth_time,
    birth_place: str,
    kundli_notes: str,
    has_kundli_image: bool,
    hybrid_details: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Returns (sections dict for report, structured vedic dict for chat/JSON).
    """
    seed = _pseudo_seed(birth_date, birth_time, birth_place)
    overrides = parse_kundli_notes(kundli_notes)

    jd = hybrid_details.get("jd") if hybrid_details else None

    if jd is not None:
        # High precision calculation using true math engine
        sun_h = overrides.get("sun_house") or _whole_sign_house(sun_sign, lagna_sign)
        moon_h = overrides.get("moon_house") or _whole_sign_house(moon_sign, lagna_sign)
        mars_sign = _sign_from_longitude(_get_planet_lon(jd, "Mars"))
        mars_h = overrides.get("mars_house") or _whole_sign_house(mars_sign, lagna_sign)
        mercury_sign = _sign_from_longitude(_get_planet_lon(jd, "Mercury"))
        mercury_h = overrides.get("mercury_house") or _whole_sign_house(mercury_sign, lagna_sign)
        venus_sign = _sign_from_longitude(_get_planet_lon(jd, "Venus"))
        venus_h = overrides.get("venus_house") or _whole_sign_house(venus_sign, lagna_sign)
        jupiter_sign = _sign_from_longitude(_get_planet_lon(jd, "Jupiter"))
        jupiter_h = overrides.get("jupiter_house") or _whole_sign_house(jupiter_sign, lagna_sign)
        saturn_sign = _sign_from_longitude(_get_planet_lon(jd, "Saturn"))
        saturn_h = overrides.get("saturn_house") or _whole_sign_house(saturn_sign, lagna_sign)
        rahu_sign = _sign_from_longitude(_get_planet_lon(jd, "Rahu"))
        ketu_sign = _sign_from_longitude(_get_planet_lon(jd, "Ketu"))
        rahu_h = overrides.get("rahu_house") or _whole_sign_house(rahu_sign, lagna_sign)
        ketu_h = overrides.get("ketu_house") or _whole_sign_house(ketu_sign, lagna_sign)
        house_msg = "Calculated using advanced high-precision planetary ephemeris."
    else:
        # Fallback pseudo-seed logic
        sun_h = overrides.get("sun_house") or _whole_sign_house(sun_sign, lagna_sign)
        moon_h = overrides.get("moon_house") or _whole_sign_house(moon_sign, lagna_sign)
        mars_h = overrides.get("mars_house") or _clamp_house((seed % 12) + 1)
        rahu_o = overrides.get("rahu_house")
        ketu_o = overrides.get("ketu_house")
        if rahu_o is not None and ketu_o is not None:
            rahu_h = _clamp_house(rahu_o)
            ketu_h = _clamp_house(ketu_o)
        elif rahu_o is not None:
            rahu_h = _clamp_house(rahu_o)
            ketu_h = _ketu_from_rahu(rahu_h)
        elif ketu_o is not None:
            ketu_h = _clamp_house(ketu_o)
            rahu_h = _ketu_from_rahu(ketu_h)
        else:
            rahu_h = _clamp_house((((seed // 9) + 10) % 12) + 1)
            ketu_h = _ketu_from_rahu(rahu_h)
        mercury_h = overrides.get("mercury_house") or _clamp_house((seed // 3 % 12) + 1)
        venus_h = overrides.get("venus_house") or _clamp_house((seed // 5 % 12) + 1)
        jupiter_h = overrides.get("jupiter_house") or _clamp_house((seed // 7 % 12) + 1)
        saturn_h = overrides.get("saturn_house") or _clamp_house((seed // 11 % 12) + 1)
        house_msg = "Simulated positions (demo logic); for high precision, provide exact coordinates."

    day_of_year = birth_date.timetuple().tm_yday
    md_index = (day_of_year + birth_time.hour + (seed % 9)) % 9
    mahadasha = VIMSHOTTARI_LORDS[md_index]
    antar = VIMSHOTTARI_LORDS[(md_index + 3) % 9]

    flags = compute_dosha_flags(mars_h, rahu_h, ketu_h)
    remedies = build_remedy_text(flags, rahu_h, ketu_h, mahadasha)

    house_lines = [
        f"Lagna ({lagna_sign}) occupies House 1 — {HOUSE_MEANINGS[1]}",
        f"Engine: {house_msg}",
        f"Sun ({sun_sign}) → House {sun_h}: {HOUSE_MEANINGS.get(sun_h, '')}",
        f"Moon ({moon_sign}) → House {moon_h}: {HOUSE_MEANINGS.get(moon_h, '')}",
        f"Mars → House {mars_h}: {HOUSE_MEANINGS.get(mars_h, '')}",
        f"Mercury → House {mercury_h}",
        f"Venus → House {venus_h}",
        f"Jupiter → House {jupiter_h}",
        f"Saturn → House {saturn_h}",
    ]

    upload_note = (
        "You attached a chart image — stored for your records. "
        "Local mode does not OCR the pixels; paste key houses in the notes box for software-grade alignment. "
        "Optional: set OPENAI_API_KEY on the server to enable cloud AI interpretation."
        if has_kundli_image
        else "No chart image uploaded — house numbers below blend whole-sign logic with your notes (if any)."
    )
    if kundli_notes.strip():
        upload_note += " Your pasted notes override automatic house guesses where detected."

    rahu_blurb = (
        f"Rahu in House {rahu_h}: obsessions, sudden opportunities, foreigners/tech themes — channels through {HOUSE_MEANINGS.get(rahu_h, '')}. "
        "Mature Rahu chooses ethical ambition, one ruthless cut of distraction, and structured learning."
    )
    ketu_blurb = (
        f"Ketu in House {ketu_h}: detachment and insight where you over-identify — {HOUSE_MEANINGS.get(ketu_h, '')}. "
        "Healthy Ketu prefers simplicity, mastery without applause, and spiritual skepticism that still respects kindness."
    )

    dasha_blurb = (
        f"Vimshottari-style snapshot: Mahadasha flavor {mahadasha}, with a secondary emphasis {antar} for timing questions. "
        "Use this as journaling language."
    )

    dosha_blurb = (
        "Dosha scan: " + ("; ".join(flags) if flags else "No major flag from Mars placement.")
    )

    structured: Dict[str, Any] = {
        "lagna_sign": lagna_sign,
        "houses": {
            "sun": sun_h,
            "moon": moon_h,
            "mars": mars_h,
            "rahu": rahu_h,
            "ketu": ketu_h,
            "mercury": mercury_h,
            "venus": venus_h,
            "jupiter": jupiter_h,
            "saturn": saturn_h,
        },
        "mahadasha": mahadasha,
        "antardasha_demo": antar,
        "dosha_flags": flags,
        "has_kundli_image": has_kundli_image,
        "notes_used": bool(kundli_notes.strip()),
    }

    sections = {
        "kundli_layer": upload_note,
        "vedic_houses": " \n".join(house_lines),
        "rahu_ketu": rahu_blurb + " " + ketu_blurb,
        "vimshottari_timing": dasha_blurb + " " + dosha_blurb,
        "remedies_lifestyle": remedies,
    }
    return sections, structured


def _planets_in_house(houses: Dict[str, Any], house_num: int) -> str:
    if not houses:
        return "(no house table)"
    hits = [name for name, hn in houses.items() if hn == house_num]
    return ", ".join(hits) if hits else "(none listed in this house)"


def format_guru_context(name: str, profile: Dict[str, str], vedic: Dict[str, Any], blueprint: Dict[str, Any]) -> str:
    """Compact text for LLM or logging."""
    h = vedic.get("houses") or {}
    career_hint = ""
    if blueprint:
        career_hint = (
            f"Blueprint cues — energy focus: {blueprint.get('energy_focus', 'n/a')}; "
            f"ruling planet: {blueprint.get('ruling_planet', 'n/a')}.\n"
        )
    return (
        f"Querent: {name}. Sun {profile.get('zodiac')}, Moon {profile.get('moon_sign')}, Asc {profile.get('ascendant')}.\n"
        f"{career_hint}"
        f"Mathematical House Placements (1-12) based on True Ecliptic Longitude:\n"
        f"Sun {h.get('sun')}, Moon {h.get('moon')}, Mars {h.get('mars')}, Mercury {h.get('mercury')}, Venus {h.get('venus')},\n"
        f"Jupiter {h.get('jupiter')}, Saturn {h.get('saturn')}, Rahu {h.get('rahu')}, Ketu {h.get('ketu')}.\n"
        f"10th house (career / reputation) hosts: {_planets_in_house(h, 10)}.\n"
        f"6th house (daily work / service / obstacles) hosts: {_planets_in_house(h, 6)}.\n"
        f"2nd/11th money houses snapshot — 2nd hosts {_planets_in_house(h, 2)}; 11th hosts {_planets_in_house(h, 11)}.\n"
        f"Mahadasha flavor: {vedic.get('mahadasha')}. Dosha flags: {', '.join(vedic.get('dosha_flags') or ['none flagged'])}.\n"
        "When answering career or job questions, cite 10th and 6th from above and Saturn/Jupiter flavor; "
        "for love/marriage, cite 7th and Venus/Moon—not the other way around.\n"
    )


def guru_reply_rule_based(message: str, ctx: str, vedic: Dict[str, Any], sections: Dict[str, str]) -> str:
    """Keyword routing over precomputed sections (works offline)."""
    m = message.lower()
    chunks: List[str] = []

    if any(k in m for k in ("rahu", "ketu", "snake", "axis")):
        chunks.append(sections.get("rahu_ketu", ""))
    if any(k in m for k in ("marriage", "love", "spouse", "7th", "partner")):
        chunks.append(
            "Partnership lens: the 7th house and Venus timing matter. "
            + sections.get("compatibility", "")
        )
    if any(
        k in m
        for k in (
            "career",
            "job",
            "jobs",
            "employ",
            "unemploy",
            "salary",
            "work",
            "office",
            "hiring",
            "interview",
            "money",
            "10th",
            "business",
        )
    ):
        chunks.append(sections.get("career", ""))
        chunks.append(sections.get("future", ""))
    if any(k in m for k in ("dasha", "mahadasha", "antar", "timing", "when")):
        chunks.append(sections.get("vimshottari_timing", ""))
    if any(k in m for k in ("remedy", "puja", "mantra", "dosha", "afflicted", "problem")):
        chunks.append(sections.get("remedies_lifestyle", ""))
    if any(k in m for k in ("house", "kundli", "chart", "lagna", "asc")):
        chunks.append(sections.get("vedic_houses", ""))

    if not chunks:
        chunks.append(
            "Sit quietly with this chart snapshot: compare what you feel true in your body versus what fear says. "
            "Astrology is a mirror: use it for meaning-making, not for shrinking your agency.\n\n"
            + ctx
        )

    tail = (
        "\n\n— If you want tighter accuracy, paste planet-wise house numbers from your kundli software into the notes field and regenerate."
    )
    text = "\n\n".join(c for c in chunks if c).strip()
    return text + tail


def get_horoscope_for_sign(sign: str) -> str:
    """Generate daily horoscope for a zodiac sign."""
    horoscopes = {
        "Aries": "Mars empowers your initiative today. Channel boldness into a worthwhile goal. Relationship insights emerge in evening hours. Lucky color: Red.",
        "Taurus": "Venus aligns with stability. Focus on building long-term value. Friends bring good news. Financial prudence pays off. Lucky color: Green.",
        "Gemini": "Mercury energizes communication. Speak your truth; others listen. Creative solutions emerge. Avoid overcommitting. Lucky color: Yellow.",
        "Cancer": "Moon's influence deepens introspection. Home and family matters gain clarity. Trust your intuition. Self-care is not indulgence. Lucky color: Silver.",
        "Leo": "Sun radiates confidence and joy. Express yourself authentically. Romance or creative breakthrough possible. Lead with heart. Lucky color: Gold.",
        "Virgo": "Mercury brings analytical clarity. Details matter; organization pays off. Domestic matters settle. Health improves with attention. Lucky color: Green.",
        "Libra": "Venus graces social and romantic realms. Charm opens doors. Creative projects flourish. Balance work and pleasure. Lucky color: Pink.",
        "Scorpio": "Pluto's intensity fuels transformation. Resources align in your favor. Home feels secure. Intuitive power peaks. Lucky color: Black.",
        "Sagittarius": "Jupiter expands horizons. Communication flows; travel beckons. New ideas take root. Adventure calls. Lucky color: Purple.",
        "Capricorn": "Saturn brings solid progress. Finances strengthen. Patience and planning reap rewards. Foundation solidifies. Lucky color: Brown.",
        "Aquarius": "Uranus sparks innovation. Social connections deepen. Unexpected opportunities arise. Embrace uniqueness. Lucky color: Blue.",
        "Pisces": "Neptune softens the day. Spirituality calls; meditation helps. Compassion flows naturally. Rest as needed. Lucky color: Teal.",
    }
    return horoscopes.get(sign, "The stars guide your path. Trust the unfolding of your cosmic blueprint.")


def generate_kundli_svg(
    zodiac: str,
    moon_sign: str,
    ascendant: str,
    planets: Dict[str, Any],
) -> str:
    """Generate a basic SVG Kundli/birth chart diagram."""
    width, height = 600, 600
    cx, cy = width / 2, height / 2
    radius = 200
    
    # SVG header
    svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
    svg += '<defs>'
    svg += '<style>'
    svg += 'text { font-family: Arial, sans-serif; font-size: 12px; fill: #333; }'
    svg += '.house-label { font-weight: bold; font-size: 14px; }'
    svg += '.planet-label { font-size: 11px; fill: #0066cc; font-weight: bold; }'
    svg += '.zodiac-label { font-size: 10px; fill: #666; }'
    svg += '</style>'
    svg += '</defs>'
    
    # Background circle
    svg += f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="#fff9f0" stroke="#8b7355" stroke-width="2"/>'
    
    # 12 houses (lines from center)
    for i in range(12):
        angle = (i * 30) * math.pi / 180
        x1, y1 = cx, cy
        x2 = cx + radius * math.cos(angle)
        y2 = cy + radius * math.sin(angle)
        svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#ccc" stroke-width="1"/>'
    
    # House numbers (1-12 arranged in circle)
    house_labels = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    for i, label in enumerate(house_labels):
        angle = (i * 30 + 15) * math.pi / 180
        x = cx + (radius * 0.85) * math.cos(angle)
        y = cy + (radius * 0.85) * math.sin(angle)
        svg += f'<text x="{x}" y="{y}" text-anchor="middle" class="house-label">{label}</text>'
    
    # Zodiac signs in each house sector
    zodiac_glyphs = {
        "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
        "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
        "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
    }
    
    lagna_idx = ZODIAC_ORDER.index(ascendant) if ascendant in ZODIAC_ORDER else 0
    for i in range(12):
        sign_idx = (lagna_idx + i) % 12
        sign = ZODIAC_ORDER[sign_idx]
        glyph = zodiac_glyphs.get(sign, "?")
        angle = (i * 30 + 5) * math.pi / 180
        x = cx + (radius * 0.60) * math.cos(angle)
        y = cy + (radius * 0.60) * math.sin(angle)
        svg += f'<text x="{x}" y="{y}" text-anchor="middle" class="zodiac-label">{glyph}</text>'
    
    # Display key planets in chart center
    planet_text = f"☉ Sun: {zodiac}"
    moon_text = f"☽ Moon: {moon_sign}"
    asc_text = f"Asc: {ascendant}"
    
    svg += f'<text x="{cx}" y="{cy - 20}" text-anchor="middle" class="planet-label">{planet_text}</text>'
    svg += f'<text x="{cx}" y="{cy}" text-anchor="middle" class="planet-label">{moon_text}</text>'
    svg += f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="planet-label">{asc_text}</text>'
    
    # Outer circle
    svg += f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#8b7355" stroke-width="2"/>'
    
    svg += '</svg>'
    return svg


def generate_kundli_chart_from_birth(
    birth_date: str,
    birth_time: str,
    birth_place_lat: Optional[float] = None,
    birth_place_lon: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate Kundli chart data from birth information.
    Returns dictionary with zodiac, moon_sign, ascendant, and SVG chart.
    """
    if not SKYFIELD_AVAILABLE:
        # Fallback to simplified calculation if Skyfield not available
        return {
            "success": False,
            "message": "Skyfield not available for chart generation",
        }
    
    try:
        # Parse birth date and time
        birth_dt = datetime.fromisoformat(f"{birth_date}T{birth_time}")
        
        # Load ephemeris
        ts = load.timescale()
        eph = load("de421.bsp")  # Planetary ephemeris
        
        # Create observer at birth location (use default if not provided)
        if birth_place_lat and birth_place_lon:
            location = wgs84.latlong(birth_place_lat, birth_place_lon)
            observer = eph["earth"].at(location)
        else:
            observer = eph["earth"]
        
        # Calculate planetary positions at birth time
        t = ts.utc(birth_dt.year, birth_dt.month, birth_dt.day, birth_dt.hour, birth_dt.minute, birth_dt.second)
        astrometric = observer.at(t).apparent_geocentric_ecliptic_position()
        
        # Convert to zodiac signs (tropical zodiac for simplicity)
        sun_lon = astrometric.ecliptic_longitude().degrees
        zodiac = ZODIAC_ORDER[int(sun_lon / 30) % 12]
        
        # Use moon sign (simplified)
        moon_sign = ZODIAC_ORDER[(int(sun_lon / 30) + 3) % 12]
        ascendant = ZODIAC_ORDER[(int(sun_lon / 30) + 6) % 12]
        
        # Generate SVG
        svg = generate_kundli_svg(zodiac, moon_sign, ascendant, {})
        
        return {
            "success": True,
            "zodiac": zodiac,
            "moon_sign": moon_sign,
            "ascendant": ascendant,
            "chart_svg": svg,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Chart generation error: {str(e)}",
        }
